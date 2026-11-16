"""HotZone FM — 保管區 (safety vault) and 操作紀錄 (operation journal).

Rule: nothing the program does may make a file disappear without a copy, except a delete the user confirmed three
times. Before anything is overwritten / replaced / removed, the old item is MOVED (same volume = an instant rename,
no extra space, no copying) into

    <volume>\\.HotZoneVault\\keep\\<yyyymmdd>\\<id>\\<original name>        (kept vault.days, default 30)
    <volume>\\.HotZoneVault\\review\\<id>\\<original name>                  (older: waits for the user to decide)

with a record of where it came from and WHY (also written next to it as <id>.json, so the vault is readable even
without the database). If the backup move fails, the destructive action is not done.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import threading
import time
import uuid

from hz_common import DATA_DIR, IS_WIN, norm, drive_of, mount_point, unique_name, fmt_size
import hz_win as W

VAULT_NAME = '.HotZoneVault'
DB = DATA_DIR / 'safety.sqlite3'


class VaultError(Exception):
    pass


def vault_root(path):
    p = norm(path)
    if IS_WIN:
        if p.startswith('\\\\'):                                   # \\server\share\...
            parts = p.split('\\')
            base = '\\'.join(parts[:4])
        else:
            base = os.path.splitdrive(p)[0] + '\\'
    else:
        base = mount_point(p)
    return os.path.join(base, VAULT_NAME)


def in_vault(path):
    s = norm(path)
    return (os.sep + VAULT_NAME + os.sep) in s + os.sep


class Vault:
    def __init__(self, settings, log):
        self.S = settings; self.log = log; self.lock = threading.RLock()
        # which installation a record belongs to: another copy of the program (another folder / Windows user) uses the
        # same X:\.HotZoneVault, and must never adopt - and then restore or purge - this one's items, nor we its
        self.inst = hashlib.sha1(str(DATA_DIR).lower().encode('utf-8', 'replace')).hexdigest()[:12]
        self.db = sqlite3.connect(str(DB), check_same_thread=False, timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY, t REAL, orig TEXT, vpath TEXT, size INTEGER, is_dir INTEGER,
                           reason TEXT, action TEXT, stage TEXT, stage_t REAL, extra TEXT)''')
        self.db.execute('CREATE INDEX IF NOT EXISTS items_stage ON items(stage, t)')
        self.db.execute('''CREATE TABLE IF NOT EXISTS journal(n INTEGER PRIMARY KEY AUTOINCREMENT, t REAL, kind TEXT, text TEXT, detail TEXT)''')
        self.db.execute('CREATE INDEX IF NOT EXISTS journal_t ON journal(t)')
        self.db.commit()

    def close(self):
        try: self.db.close()
        except Exception: pass

    # ------------------------------------------------------------------ journal
    def note(self, kind, text, detail=None):
        with self.lock:
            self.db.execute('INSERT INTO journal(t, kind, text, detail) VALUES(?,?,?,?)',
                            (time.time(), kind, text, json.dumps(detail, ensure_ascii=False) if detail is not None else None))
            self.db.commit()

    def journal(self, q='', kind='', before=None, limit=300):
        sql = 'SELECT n, t, kind, text, detail FROM journal WHERE 1=1'; args = []
        if q: sql += ' AND (text LIKE ? OR detail LIKE ?)'; args += [f'%{q}%', f'%{q}%']
        if kind: sql += ' AND kind = ?'; args.append(kind)
        if before: sql += ' AND n < ?'; args.append(int(before))
        sql += ' ORDER BY n DESC LIMIT ?'; args.append(int(limit))
        with self.lock:
            rows = self.db.execute(sql, args).fetchall()
        return [{'n': r[0], 't': r[1], 'kind': r[2], 'text': r[3], 'detail': json.loads(r[4]) if r[4] else None} for r in rows]

    # ------------------------------------------------------------------ stash
    def _size(self, p):
        try:
            if os.path.isdir(p) and not os.path.islink(p):
                tot = 0
                for root, ds, fs, _links in W.walk(p):
                    for f in fs:
                        try: tot += os.path.getsize(os.path.join(root, f))
                        except OSError: pass
                return tot
            return os.path.getsize(p)
        except OSError:
            return 0

    def _prepare_root(self, vr):
        if not os.path.isdir(vr):
            os.makedirs(W.lp(vr), exist_ok=True)
            try:
                with open(os.path.join(vr, '這是 HotZone FM 的保管區.txt'), 'w', encoding='utf-8') as f:
                    f.write('HotZone FM 在覆蓋、取代、刪除檔案之前，會先把原本的檔案移到這裡保管。\n'
                            'keep\\   = 保管中（預設 30 天）\nreview\\ = 超過保管期限，等你在程式的「保管區」頁面決定\n'
                            '每個項目旁邊的 .json 寫著它原本的位置和原因。請不要手動刪除這個資料夾。\n')
            except OSError:
                pass
            if IS_WIN: W.set_attrs(vr, 0x2 | 0x4)                         # hidden + system

    def stash(self, path, reason, action, extra=None):
        """Move `path` into its volume's vault. Returns the record. Raises VaultError (the caller must then NOT
        continue with the destructive action)."""
        p = norm(path)
        if not os.path.lexists(W.lp(p)): raise VaultError(f'找不到要保管的項目：{p}')
        if in_vault(p): raise VaultError('已經在保管區裡')
        vr = vault_root(p)
        iid = time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
        try:
            self._prepare_root(vr)
            d = os.path.join(vr, 'keep', time.strftime('%Y%m%d'), iid)
            os.makedirs(W.lp(d), exist_ok=True)
            is_dir = os.path.isdir(p) and not os.path.islink(p)
            size = self._size(p)
            vp = os.path.join(d, os.path.basename(p.rstrip('\\/')) or 'item')
        except OSError as e:
            raise VaultError(f'無法放進保管區（{e.strerror or e}），為了安全，這個動作取消了')
        rec = {'id': iid, 't': time.time(), 'orig': p, 'vpath': vp, 'size': size, 'is_dir': int(is_dir), 'reason': reason,
               'action': action, 'stage': 'keep', 'stage_t': time.time(), 'extra': extra, 'inst': self.inst}
        js = os.path.join(d, iid + '.json')
        try:                                                        # 1. the record goes down first (both places)
            with open(W.lp(js), 'w', encoding='utf-8') as f:
                json.dump(rec, f, ensure_ascii=False, indent=1); f.flush(); os.fsync(f.fileno())   # on disk before the move
            with self.lock:
                self.db.execute('INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?,?,?)', (iid, rec['t'], p, vp, size, int(is_dir), reason, action, 'moving',
                                                                                  rec['stage_t'], json.dumps(extra, ensure_ascii=False) if extra else None))
                self.db.commit()
        except Exception as e:
            try: os.remove(W.lp(js)); os.rmdir(W.lp(d))
            except OSError: pass
            raise VaultError(f'無法記錄保管項目（{e}），為了安全，這個動作取消了')
        try:                                                        # 2. move it
            os.rename(W.lp(p), W.lp(vp))
        except OSError as e:
            try:
                with self.lock: self.db.execute('DELETE FROM items WHERE id=?', (iid,)); self.db.commit()
            except Exception: pass
            try: os.remove(W.lp(js)); os.rmdir(W.lp(d))
            except OSError: pass
            raise VaultError(f'無法放進保管區（{e.strerror or e}），為了安全，這個動作取消了')
        try:                                                        # 3. mark it kept (if this fails, reconcile() fixes it)
            with self.lock:                                         # (one commit for both: 3 -> 2 per item)
                self.db.execute("UPDATE items SET stage='keep' WHERE id=?", (iid,))
                self.db.execute('INSERT INTO journal(t, kind, text, detail) VALUES(?,?,?,?)',
                                (time.time(), 'vault', f'放進保管區：{p}', json.dumps({'reason': reason, 'action': action, 'vault': vp, 'size': size}, ensure_ascii=False)))
                self.db.commit()
        except Exception:
            try: self.log.warn('vault', f'保管區資料庫暫時寫不進去，項目已安全放好，稍後自動補記：{vp}')
            except Exception: pass
        return rec

    def roots(self):
        """Every vault folder we know of: one per volume."""
        out = set()
        if IS_WIN:
            import string
            for c in string.ascii_uppercase[2:]:
                r = f'{c}:\\{VAULT_NAME}'
                try:
                    if os.path.isdir(r): out.add(r)
                except OSError: pass
        try:
            with self.lock: origs = [r[0] for r in self.db.execute('SELECT DISTINCT substr(orig, 1, 260) FROM items LIMIT 5000')]
            for o in origs:
                try:
                    r = vault_root(o)
                    if os.path.isdir(r): out.add(r)
                except Exception: pass
        except Exception:
            pass
        return sorted(out)

    def reconcile(self, min_age=300):
        """Make the database agree with the disk: rows left half-done ('moving') and vault folders that have a
        .json record but no row (database was locked / full at the time). Nothing is ever deleted here."""
        fixed = 0
        with self.lock:
            # a young 'moving' row may belong to a stash happening right now (record written, move not yet done)
            rows = self.db.execute("SELECT id, orig, vpath FROM items WHERE stage='moving' AND t < ?", (time.time() - min_age,)).fetchall()
        for iid, orig, vp in rows:
            if os.path.lexists(W.lp(vp)): st = 'keep'
            elif os.path.lexists(W.lp(orig)): st = None
            else: st = 'missing'
            with self.lock:
                if st: self.db.execute('UPDATE items SET stage=? WHERE id=?', (st, iid))
                else: self.db.execute('DELETE FROM items WHERE id=?', (iid,))
                self.db.commit()
            fixed += 1
        # rows whose file is not where the database says: a stage change (keep -> review) cut short by a crash moved
        # the file but not the record. Find it by its id folder and repair the record (never call it 'missing' blindly).
        with self.lock: rows = self.db.execute("SELECT * FROM items WHERE stage IN ('keep','review','missing')").fetchall()
        for r in rows:
            it = self._row(r)
            if it['exists']: continue
            vp = self._find_moved(it)
            if vp:
                self._set_stage(it['id'], 'review' if os.sep + 'review' + os.sep in vp else 'keep', vp); fixed += 1
        with self.lock: known = {r[0] for r in self.db.execute('SELECT id FROM items')}
        for vr in self.roots():
            for stage in ('keep', 'review'):
                base = os.path.join(vr, stage)
                if not os.path.isdir(base): continue
                cands = []
                for a in os.listdir(base):
                    pa = os.path.join(base, a)
                    if a.endswith('.json'): cands.append((base, a)); continue
                    if not os.path.isdir(pa): continue
                    for b in os.listdir(pa):
                        pb = os.path.join(pa, b)
                        if os.path.isdir(pb):
                            for c in os.listdir(pb):
                                if c.endswith('.json'): cands.append((pb, c))
                        elif b.endswith('.json'): cands.append((pa, b))
                for d, jf in cands:
                    iid = jf[:-5]
                    if iid in known: continue
                    try:
                        with open(os.path.join(d, jf), encoding='utf-8') as f: rec = json.load(f)
                        if rec.get('inst') and rec['inst'] != self.inst: continue   # another installation's item
                        vp = os.path.join(d, os.path.basename(rec['vpath']))
                        if not os.path.lexists(W.lp(vp)): continue
                        with self.lock:
                            self.db.execute('INSERT OR IGNORE INTO items VALUES(?,?,?,?,?,?,?,?,?,?,?)', (iid, rec['t'], rec['orig'], vp, rec.get('size', 0),
                                            int(rec.get('is_dir', 0)), rec.get('reason', ''), rec.get('action', ''), stage, rec.get('stage_t', rec['t']),
                                            json.dumps(rec.get('extra'), ensure_ascii=False) if rec.get('extra') else None))
                            self.db.commit()
                        known.add(iid); fixed += 1
                    except Exception:
                        continue
        if fixed: self.note('vault', f'保管區自我檢查：補回 {fixed} 筆紀錄', None)
        return fixed

    # ------------------------------------------------------------------ views
    def _row(self, r):
        days = float(self.S.get('vault.days') or 30)
        d = {'id': r[0], 't': r[1], 'orig': r[2], 'vpath': r[3], 'size': r[4], 'is_dir': bool(r[5]), 'reason': r[6], 'action': r[7],
             'stage': r[8], 'stage_t': r[9], 'extra': json.loads(r[10]) if r[10] else None}
        d['days_left'] = max(0.0, days - (time.time() - d['stage_t']) / 86400) if d['stage'] == 'keep' else None
        d['exists'] = os.path.lexists(W.lp(d['vpath']))
        return d

    def items(self, stage='keep', q='', offset=0, limit=300, action=''):
        where = ' WHERE stage = ?'; args = [stage]
        if q: where += ' AND (orig LIKE ? OR reason LIKE ?)'; args += [f'%{q}%', f'%{q}%']
        if action: where += ' AND action = ?'; args.append(action)
        with self.lock:
            rows = self.db.execute('SELECT * FROM items' + where + ' ORDER BY t DESC LIMIT ? OFFSET ?', args + [int(limit), int(offset)]).fetchall()
            tot = self.db.execute('SELECT COUNT(*), COALESCE(SUM(size),0) FROM items' + where, args).fetchone()
            acts = self.db.execute('SELECT action, COUNT(*), COALESCE(SUM(size),0) FROM items WHERE stage = ? GROUP BY action', (stage,)).fetchall()
        return {'items': [self._row(r) for r in rows], 'total': tot[0], 'size': tot[1], 'actions': [list(x) for x in acts]}

    def stats(self):
        with self.lock:
            rows = self.db.execute("SELECT stage, COUNT(*), COALESCE(SUM(size),0) FROM items GROUP BY stage").fetchall()
        return {r[0]: {'n': r[1], 'size': r[2]} for r in rows}

    def size_on(self, letter):
        """Bytes kept in the vault of one drive ('K:' or a mount point)."""
        with self.lock:
            rows = self.db.execute("SELECT orig, size FROM items WHERE stage IN ('keep','review')").fetchall()
        lt = letter.rstrip('\\/').lower()
        return sum(sz or 0 for o, sz in rows if drive_of(o).rstrip('\\/').lower() == lt)

    def get(self, iid):
        with self.lock:
            r = self.db.execute('SELECT * FROM items WHERE id = ?', (iid,)).fetchone()
        if not r: raise ValueError('找不到這個保管項目')
        return self._row(r)

    def _set_stage(self, iid, stage, vpath=None):
        with self.lock:
            if vpath: self.db.execute('UPDATE items SET stage=?, stage_t=?, vpath=? WHERE id=?', (stage, time.time(), vpath, iid))
            else: self.db.execute('UPDATE items SET stage=?, stage_t=? WHERE id=?', (stage, time.time(), iid))
            self.db.commit()

    # ------------------------------------------------------------------ actions
    def restore(self, iid, to=None):
        it = self.get(iid)
        if it['stage'] not in ('keep', 'review', 'missing'): raise ValueError('這個項目已經處理過了')
        if not it['exists']:
            found = self._find_moved(it)
            if found: self._set_stage(iid, it['stage'] if it['stage'] != 'missing' else 'keep', found); it = self.get(iid)
        if not it['exists']: raise ValueError('保管區裡找不到這個檔案（可能被手動刪除了）')
        dst = norm(to) if to else it['orig']
        os.makedirs(W.lp(os.path.dirname(dst)), exist_ok=True)
        base, ext = os.path.splitext(dst)
        if it['is_dir']: base, ext = dst, ''
        alt = lambda: unique_name(f'{base} (還原){ext}')
        if os.path.lexists(W.lp(dst)): dst = alt()
        src = it['vpath']
        for _ in range(100):
            try:
                W.rename_noreplace(src, dst); break                  # never replaces anything
            except FileExistsError:
                dst = alt()
            except OSError as e:
                if getattr(e, 'errno', 0) != 18 and getattr(e, 'winerror', 0) != 17: raise   # only "other drive" goes on
                tmp = os.path.join(os.path.dirname(dst), f'.{uuid.uuid4().hex[:12]}.hzrestore')
                if os.path.isdir(src): shutil.copytree(W.lp(src), W.lp(tmp), symlinks=True)
                else: shutil.copy2(W.lp(src), W.lp(tmp))
                for _ in range(100):
                    try: W.rename_noreplace(tmp, dst); break
                    except FileExistsError: dst = alt()
                if os.path.isdir(src): shutil.rmtree(W.lp(src))
                else: os.remove(W.lp(src))
                break
        else:
            raise ValueError('找不到可以還原的名稱')
        self._cleanup_dir(it['vpath'])
        self._set_stage(iid, 'restored')
        self.note('restore', f'從保管區還原：{dst}', {'id': iid, 'orig': it['orig'], 'reason': it['reason']})
        return dst

    def extend(self, iid):
        it = self.get(iid)
        if it['stage'] == 'review':
            vp = self._move_stage(it, 'keep')
            self._set_stage(iid, 'keep', vp)
        else:
            self._set_stage(iid, 'keep')
        self.note('vault', f'延長保管：{it["orig"]}', {'id': iid})

    def purge(self, iid, why='你在保管區按了永久刪除'):
        it = self.get(iid)
        if it['stage'] not in ('keep', 'review'): raise ValueError('這個項目已經處理過了')
        if it['exists']:
            p = W.lp(it['vpath'])
            if os.path.isdir(p) and not os.path.islink(p): shutil.rmtree(p)
            else:
                try: os.remove(p)
                except PermissionError: W.set_attrs(it['vpath'], 0x80); os.remove(p)
        self._cleanup_dir(it['vpath'])
        self._set_stage(iid, 'purged')
        self.note('purge', f'永久刪除（保管區）：{it["orig"]}', {'id': iid, 'why': why, 'size': it['size']})

    def _cleanup_dir(self, vpath):
        d = os.path.dirname(vpath)
        try:
            for f in os.listdir(d):
                if f.endswith('.json'): os.remove(os.path.join(d, f))
            os.rmdir(d)
            os.rmdir(os.path.dirname(d))                                    # the yyyymmdd folder, when empty
        except OSError:
            pass

    def _find_moved(self, it):
        """Where an item's file really is when it is not at its recorded path: <vault>/<keep|review>/[date/]<id>/<name>."""
        try: vr = vault_root(it['orig'])
        except Exception: return None
        name = os.path.basename(it['vpath'])
        for stage in ('review', 'keep'):
            base = os.path.join(vr, stage)
            cands = [os.path.join(base, it['id'])]
            try: cands += [os.path.join(base, d, it['id']) for d in os.listdir(W.lp(base)) if d != it['id']]
            except OSError: pass
            for c in cands:
                p = os.path.join(c, name)
                if os.path.lexists(W.lp(p)): return p
        return None

    def _move_stage(self, it, stage):
        vr = vault_root(it['orig'])
        d = os.path.join(vr, stage, time.strftime('%Y%m%d') if stage == 'keep' else '', it['id'])
        os.makedirs(W.lp(d), exist_ok=True)
        vp = os.path.join(d, os.path.basename(it['vpath']))
        if os.path.normcase(os.path.abspath(vp)) == os.path.normcase(os.path.abspath(it['vpath'])): return vp   # already there
        os.rename(W.lp(it['vpath']), W.lp(vp))
        old_dir = os.path.dirname(it['vpath'])
        try:
            js = os.path.join(old_dir, it['id'] + '.json')
            if os.path.exists(js): shutil.move(js, os.path.join(d, it['id'] + '.json'))
        except OSError:
            pass
        self._cleanup_dir(it['vpath'])
        return vp

    def maintain(self):
        """Items older than vault.days -> review area (the user decides there). Called every hour."""
        days = float(self.S.get('vault.days') or 30)
        cutoff = time.time() - days * 86400
        with self.lock:
            rows = self.db.execute("SELECT * FROM items WHERE stage='keep' AND stage_t < ?", (cutoff,)).fetchall()
        n = 0
        for r in rows:
            it = self._row(r)
            try:
                if not it['exists']:
                    found = self._find_moved(it)                            # a crash between file move and record update
                    if found and os.sep + 'review' + os.sep in found:
                        self._set_stage(it['id'], 'review', found); n += 1; continue
                    if found: self._set_stage(it['id'], 'keep', found); it['vpath'] = found; it['exists'] = True
                if it['exists']:
                    vp = self._move_stage(it, 'review'); self._set_stage(it['id'], 'review', vp)
                else:
                    self._set_stage(it['id'], 'missing')
                n += 1
            except OSError as e:
                self.log.warn('vault', f'移到待確認區失敗：{it["vpath"]}：{e}')
        if n: self.note('vault', f'{n} 個項目保管超過 {days:g} 天，移到「待你決定」', None)
        return n

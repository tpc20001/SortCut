"""HotZone FM — undo (Ctrl+Z) for rename, new folder / file, move and copy.

  rename        -> rename back
  new folder    -> remove it again (only while it is still empty)
  new file      -> remove it again (only while it is still empty)
  move (same drive)  -> rename every moved item back (instant)
  move (other drive) -> a move job back to where it came from
  copy          -> the copies that did not exist before go into the vault
  delete (into the vault) -> restored from the vault to where they were (a name in use gets ' (還原)')
"""
from __future__ import annotations

import os
import threading
import time
import uuid

from hz_common import DATA_DIR, IS_WIN, atomic_write_json, read_json
import hz_win as W

FILE = DATA_DIR / 'undo.json'
MAX = 60


class Undo:
    def __init__(self, eng):
        self.eng = eng; self.lock = threading.Lock()
        self.stack = read_json(FILE, []) or []

    def _save(self):
        try: atomic_write_json(FILE, self.stack[-MAX:], indent=None)
        except Exception: pass

    def push(self, kind, text, data):
        with self.lock:
            self.stack.append({'id': uuid.uuid4().hex[:8], 't': time.time(), 'kind': kind, 'text': text, 'data': data})
            self.stack = self.stack[-MAX:]; self._save()

    def list(self):
        with self.lock: return list(reversed(self.stack[-20:]))

    # ------------------------------------------------------------------ recording
    def job_done(self, j):
        kind = j.get('kind')
        if kind == 'move' and j.get('same') and j.get('pairs'):
            n = len(j['pairs'])
            self.push('move_same', f'移動 {n} 個項目到 {os.path.basename(j["dst"].rstrip(chr(92) + "/")) or j["dst"]}', {'pairs': j['pairs']})
        elif kind == 'move' and j.get('tops'):
            pairs = [[s, d] for s, d, existed in j['tops'] if not existed]
            if pairs: self.push('move_cross', f'移動 {len(pairs)} 個項目到 {j["dst"]}', {'pairs': pairs})
        elif kind == 'vault' and j.get('vault_ids') and not (j.get('opts') or {}).get('from_undo'):
            n = len(j['vault_ids'])
            self.push('vault_delete', f'刪除 {n} 個項目（放進保管區）', {'ids': j['vault_ids']})
        elif kind == 'copy' and j.get('tops'):
            seen = set(); created = []
            for s, d, existed in j['tops']:
                if not existed and d not in seen: seen.add(d); created.append(d)
            if created: self.push('copy', f'複製 {len(created)} 個項目到 {j["dst"]}', {'created': created})

    # ------------------------------------------------------------------ undo
    def undo(self, uid=None):
        with self.lock:
            if not self.stack: raise ValueError('沒有可以復原的動作')
            e = self.stack[-1] if uid is None else next((x for x in self.stack if x['id'] == uid), None)
            if e is None: raise ValueError('找不到這個動作')
            self.stack.remove(e); self._save()
        try:
            msg = self._do(e)
        except Exception:
            with self.lock: self.stack.append(e); self._save()
            raise
        self.eng.log.info('undo', f'復原：{e["text"]}')
        return {'ok': True, 'text': e['text'], 'msg': msg}

    def _do(self, e):
        k, d = e['kind'], e['data']; touch = self.eng.index.touch
        if k == 'rename':
            new, old = d['new'], d['old']
            import hz_fileops as F
            if os.path.lexists(W.lp(old)) and not (os.name == 'nt' and old.lower() == new.lower()): raise ValueError(f'原本的名稱已經被使用：{os.path.basename(old)}')
            F.rename(new, os.path.basename(old)); touch(new); touch(old)
            return ''
        if k in ('mkdir', 'newfile'):
            p = d['path']
            if not os.path.lexists(W.lp(p)): return '已經不在了'
            if k == 'mkdir':
                if os.listdir(W.lp(p)): raise ValueError('資料夾裡已經有東西，不能復原（請自己刪除）')
                os.rmdir(W.lp(p))
            else:
                if os.path.getsize(W.lp(p)) > 0: raise ValueError('檔案已經有內容，不能復原（請自己刪除）')
                os.remove(W.lp(p))
            touch(p); return ''
        if k == 'batch_rename':
            import hz_fileops as F
            items = [[new, os.path.basename(old)] for old, new in d['pairs'] if os.path.lexists(W.lp(new))]
            done = F.batch_rename(items)
            for a, b in done: touch(a); touch(b)
            return f'{len(done)} 個已改回'
        if k == 'move_same':
            done = 0; fails = []
            for src, dst in reversed(d['pairs']):
                if not os.path.lexists(W.lp(dst)): fails.append(dst); continue
                if os.path.lexists(W.lp(src)): fails.append(src); continue
                os.makedirs(W.lp(os.path.dirname(src)), exist_ok=True)
                try: W.rename_noreplace(dst, src)
                except FileExistsError: fails.append(src); continue
                touch(dst); touch(src); done += 1
            return f'{done} 個已移回' + (f'，{len(fails)} 個無法移回' if fails else '')
        if k == 'move_cross':
            by = {}
            for src, dst in d['pairs']:
                if os.path.lexists(W.lp(dst)): by.setdefault(os.path.dirname(src), []).append(dst)
            for parent, items in by.items():
                os.makedirs(W.lp(parent), exist_ok=True)
                self.eng.queue.add('move', items, parent)
            return f'已加入佇列：移回 {sum(len(v) for v in by.values())} 個項目'
        if k == 'copy':
            items = [p for p in d['created'] if os.path.lexists(W.lp(p))]
            if not items: return '複本已經不在了'
            self.eng.queue.add('vault', items, opts={'reason': '你按了「復原」：取消剛才的複製', 'from_undo': True})
            return f'已把 {len(items)} 個複本放進保管區'
        if k == 'vault_delete':
            done = 0; fails = 0
            for iid in d['ids']:
                try:
                    r = self.eng.vault.restore(iid); done += 1
                    if isinstance(r, str): touch(r)
                except Exception:
                    fails += 1
            if not done and fails: raise ValueError('保管區裡已經找不到這些項目（可能已經還原或永久刪除）')
            return f'{done} 個已從保管區放回原處' + (f'，{fails} 個找不到' if fails else '')
        raise ValueError('不支援的動作')

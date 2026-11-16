"""HotZone FM — 資料夾比較／同步 (FastCopy "Sync", FreeFileSync style).

Compare folder A with folder B by relative path: size + modification time (fast), optionally content (MD5).
The sync itself never deletes or overwrites anything directly: copies go through the transfer queue (an
overwritten file goes to the vault first), and "mirror" puts files that exist only on the target side into the
target drive's vault with the reason written down.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time

from hz_common import IS_WIN, norm, is_under
import hz_win as W

SKIP_DIRS = {'.HotZoneVault', '$RECYCLE.BIN', 'System Volume Information'}
TIME_SLACK = 2.0                                       # FAT / exFAT keep times in 2-second steps


def _unlp(r):
    if IS_WIN and r.startswith('\\\\?\\'): return r[4:] if not r.startswith('\\\\?\\UNC\\') else '\\' + r[7:]
    return r


def _scan(root, stop, prog, bad):
    """bad (out): relative folders / files that could not be read or are links -> never mirrored away on the other side"""
    out = {}
    top = ('\\\\?\\' + os.path.abspath(root) if not root.startswith('\\\\') else '\\\\?\\UNC\\' + root[2:]) if IS_WIN else root
    def onerr(e):
        fn = getattr(e, 'filename', '') or ''
        try: bad.add(os.path.relpath(_unlp(fn), root))
        except ValueError: bad.add('.')
    for r, dirs, files, links in W.walk(top, onerror=onerr):
        if stop.is_set(): raise InterruptedError
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        r = _unlp(r)
        for d in links: bad.add(os.path.relpath(os.path.join(r, d), root))
        if IS_WIN:                                       # 'name.' / 'name ' (from a NAS / Linux): Windows paths would hit
            odd = [d for d in dirs if d.endswith(('.', ' '))]       # 'name' instead -> never touch them, report them
            for d in odd: bad.add(os.path.relpath(os.path.join(r, d), root))
            if odd: dirs[:] = [d for d in dirs if d not in odd]
        for f in files:
            if f.endswith(('.hzpart', '.hzupload')) or f.startswith('.hzren_'): continue
            p = os.path.join(r, f)
            if IS_WIN and f.endswith(('.', ' ')): bad.add(os.path.relpath(p, root)); continue
            try: st = os.stat(W.lp(p))
            except OSError:
                bad.add(os.path.relpath(p, root)); continue
            rel = os.path.relpath(p, root)
            out[rel.lower() if IS_WIN else rel] = (rel, st.st_size, st.st_mtime)
        prog(len(out))
    return out


def _md5(p, stop):
    h = hashlib.md5()
    with open(W.lp(p), 'rb') as f:
        while True:
            if stop.is_set(): raise InterruptedError
            b = f.read(4 * 1024 * 1024)
            if not b: return h.hexdigest()
            h.update(b)


class Comparer:
    def __init__(self, eng):
        self.eng = eng; self.th = None; self.stop_ev = threading.Event()
        self.st = {'state': 'idle', 'msg': '', 'a': '', 'b': '', 't': 0, 'rows': [], 'counts': {}}

    def start(self, a, b, content=False):
        if not str(a or '').strip() or not str(b or '').strip(): raise ValueError('請輸入左右兩個資料夾')
        a, b = norm(a), norm(b)
        if not os.path.isdir(a) or not os.path.isdir(b): raise ValueError('兩邊都要是存在的資料夾')
        if is_under(a, b) or is_under(b, a): raise ValueError('兩個資料夾不能一個在另一個裡面')
        self.cancel()
        self.stop_ev = threading.Event()
        self.st = {'state': 'running', 'msg': '列出檔案…', 'a': a, 'b': b, 't': time.time(), 'rows': [], 'counts': {}, 'content': content}
        self.th = threading.Thread(target=self._run, args=(a, b, content, self.stop_ev), name='HZ-Compare', daemon=True); self.th.start()
        return self.status()

    def cancel(self):
        self.stop_ev.set()
        if self.th and self.th.is_alive(): self.th.join(3)

    def _run(self, a, b, content, stop):
        st = self.st
        try:
            W.thread_background(True)
            badA, badB = set(), set()
            A = _scan(a, stop, lambda n: st.update(msg=f'列出左邊… {n:,} 個檔案'), badA)
            B = _scan(b, stop, lambda n: st.update(msg=f'列出右邊… {n:,} 個檔案'), badB)
            st['bad_a'] = sorted(badA)[:200]; st['bad_b'] = sorted(badB)[:200]; st['bad_n'] = len(badA) + len(badB)
            rows = []; counts = {'left': 0, 'right': 0, 'lnew': 0, 'rnew': 0, 'diff': 0, 'same': 0, 'err': 0}
            keys = sorted(set(A) | set(B))
            for i, k in enumerate(keys):
                if stop.is_set(): raise InterruptedError
                la, lb = A.get(k), B.get(k)
                if la and not lb: s = 'left'
                elif lb and not la: s = 'right'
                else:
                    dt = la[2] - lb[2]
                    if la[1] == lb[1] and abs(dt) <= TIME_SLACK: s = 'same'
                    elif abs(dt) <= TIME_SLACK: s = 'diff'              # same time, different size
                    else: s = 'lnew' if dt > 0 else 'rnew'
                    if content and s in ('same', 'lnew', 'rnew') and la[1] == lb[1]:
                        st['msg'] = f'比對內容… {i:,} / {len(keys):,}'
                        try:
                            same = _md5(os.path.join(a, la[0]), stop) == _md5(os.path.join(b, lb[0]), stop)
                            if same and s != 'same': s = 'same'                   # only the time differs
                            elif not same and s == 'same': s = 'diff'
                        except OSError:
                            s = 'err'                                             # unreadable (locked): left alone
                counts[s] += 1
                if s != 'same' or len(rows) < 2000:
                    rows.append({'rel': (la or lb)[0], 's': s, 'la': la[1:] if la else None, 'lb': lb[1:] if lb else None})
            st.update(state='done', rows=rows, counts=counts, msg=f'左邊 {len(A):,} 個、右邊 {len(B):,} 個檔案', took=time.time() - st['t'])
        except InterruptedError:
            st.update(state='canceled', msg='已取消')
        except Exception as e:
            st.update(state='error', msg=str(e))

    def status(self, limit=3000, only=''):
        st = dict(self.st)
        rows = st.get('rows') or []
        if only: rows = [r for r in rows if r['s'] in only.split(',')]
        st['total_rows'] = len(rows); st['rows'] = rows[:limit]
        return st

    # ---------------------------------------------------------------- sync
    def plan(self, direction, mirror=False):
        """direction 'ab' (A -> B), 'ba' (B -> A) or 'both' (newer wins). -> {'copy': [[src, dst], ...], 'vault': [paths]}"""
        st = self.st
        if st.get('state') != 'done': raise ValueError('請先比較')
        a, b = st['a'], st['b']; cp = []; rm = []; skipped = 0; unsafe = 0
        bad_src = set(st.get('bad_a' if direction == 'ab' else 'bad_b') or [])
        bad_a, bad_b = set(st.get('bad_a') or []), set(st.get('bad_b') or [])        # links / unreadable on each side
        if st.get('bad_n', 0) > 200 and mirror: raise ValueError('有太多讀不到的位置，為了安全不做鏡像；請先處理權限問題再比較一次')
        key = (lambda x: x.lower()) if IS_WIN else (lambda x: x)
        def under(rel, bad):
            r = key(rel)
            return any(r == key(b_) or r.startswith(key(b_).rstrip('\\/') + os.sep) or b_ == '.' for b_ in bad)

        def now(p):
            try: x = os.stat(W.lp(p)); return (x.st_size, x.st_mtime) if os.path.isfile(W.lp(p)) else None
            except OSError: return None
        for r in st['rows']:
            s, rel = r['s'], r['rel']
            pa, pb = os.path.join(a, rel), os.path.join(b, rel)
            if s == 'same': continue
            la, lb = now(pa), now(pb)                                          # the comparison may be hours old: look again
            if (la[0] if la else None, la[1] if la else None) != (tuple(r['la']) if r['la'] else (None, None)) or \
               (lb[0] if lb else None, lb[1] if lb else None) != (tuple(r['lb']) if r['lb'] else (None, None)):
                skipped += 1; continue                                         # changed since: skip, the user compares again
            if s == 'err': continue
            # mirror = the target becomes identical: the source wins even where the target is newer
            if direction in ('ab', 'both') and (s == 'left' or s == 'lnew' or (s in ('diff', 'rnew') and direction == 'ab' and (s == 'diff' or mirror))):
                if under(rel, bad_b): unsafe += 1                          # the target is (inside) a link: would write elsewhere
                else: cp.append([pa, pb])
            if direction in ('ba', 'both') and (s == 'right' or s == 'rnew' or (s in ('diff', 'lnew') and direction == 'ba' and (s == 'diff' or mirror))):
                if under(rel, bad_a): unsafe += 1
                else: cp.append([pb, pa])
            if mirror and direction == 'ab' and s == 'right':
                if under(rel, bad_src): unsafe += 1                          # the source side could not be read there
                else: rm.append(pb)
            if mirror and direction == 'ba' and s == 'left':
                if under(rel, bad_src): unsafe += 1
                else: rm.append(pa)
        return {'copy': cp, 'vault': rm, 'a': a, 'b': b, 'skipped_changed': skipped, 'skipped_unreadable': unsafe}

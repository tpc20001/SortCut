"""HotZone FM — duplicate files: same size (from the index, instant) -> same first+last 64 KB -> same full hash.

Runs as one background job at a time; reading is paced like the transfer queue (it can be a lot of hard-disk
reading: the disk is used at most the queue's usage %) and uses background I/O priority. Hard links of one file are
not reported as duplicates (deleting one would free nothing)."""
from __future__ import annotations

import hashlib
import os
import threading
import time

from hz_common import norm, is_under, IS_WIN, fmt_size
import hz_win as W

PART = 64 * 1024
SKIP_PARTS = ('.hotzonevault', '$recycle.bin', 'system volume information', 'recycler')   # never offered as duplicates


def _skip(p):
    low = p.replace('\\', '/').lower().split('/')
    return any(x in SKIP_PARTS for x in low)


class DupeFinder:
    def __init__(self, eng):
        self.eng = eng; self.th = None; self.stop_ev = threading.Event()
        self.st = {'state': 'idle', 'msg': '', 'progress': 0.0, 'groups': [], 'path': '', 't': 0, 'files': 0, 'wasted': 0}
        self.rm = {'state': 'idle'}; self.rm_th = None; self.lock = threading.Lock()

    def status(self, limit=400, per_group=300):
        with self.lock:
            d = dict(self.st); groups = list(d['groups'])
        d['ngroups'] = len(groups)
        d['groups'] = [dict(g, files=g['files'][:per_group], nfiles=len(g['files'])) if len(g['files']) > per_group else g
                       for g in groups[:limit]]                              # (one group of 200k files crashed the page)
        d['rm'] = dict(self.rm)
        return d

    # ------------------------------------------------------------------ removing (into the vault)
    def remove(self, paths):
        """Put chosen duplicates into the vault - only after checking, right now, on this side:
        each one is still the file that was found (size + time) and is byte-for-byte identical to a copy of its group
        that is NOT being removed, still there and unchanged. Groups are never emptied, whatever the page sends."""
        if self.th and self.th.is_alive(): raise ValueError('還在找重複檔案，請等它完成')
        if self.rm.get('state') == 'running' and self.rm_th and self.rm_th.is_alive(): raise ValueError('上一批還在檢查中')
        want = {norm(p) for p in paths if p}
        if not want: raise ValueError('沒有勾選任何檔案')
        self.rm = {'state': 'running', 'msg': '確認檔案…', 'progress': 0.0, 'queued': 0, 'refused': [], 't': time.time()}
        self.stop_ev = threading.Event()
        self.rm_th = threading.Thread(target=self._remove, args=(want,), name='HZ-DupesRemove', daemon=True); self.rm_th.start()
        return dict(self.rm)

    def _same_now(self, p, size, mtime):
        try: st = os.stat(W.lp(p))
        except OSError: return False
        return os.path.isfile(W.lp(p)) and st.st_size == size and abs(st.st_mtime - mtime) <= 2

    def _equal(self, a, b):
        with open(W.lp(a), 'rb') as fa, open(W.lp(b), 'rb') as fb:
            while True:
                if self.stop_ev.is_set(): raise InterruptedError
                t0 = time.monotonic(); x = fa.read(4 * 1024 * 1024); y = fb.read(4 * 1024 * 1024)
                self._pace(time.monotonic() - t0)
                if x != y: return False
                if not x: return True

    def _remove(self, want):
        rm = self.rm; ok = []; refused = []
        try:
            W.thread_background(True)
            with self.lock: groups = list(self.st['groups'])
            todo = [(g, [f for f in g['files'] if norm(f['path']) in want]) for g in groups]
            todo = [(g, sel) for g, sel in todo if sel]
            known = {norm(f['path']) for g, sel in todo for f in sel}
            for p in want - known: refused.append({'path': p, 'why': '不在這次找到的重複檔案裡（請重新找一次）'})
            total = sum(len(sel) for g, sel in todo) or 1; n = 0
            for g, sel in todo:
                keep = [f for f in g['files'] if norm(f['path']) not in want and self._same_now(f['path'], g['size'], f['mtime'])]
                if not keep:
                    for f in sel: refused.append({'path': f['path'], 'why': '同一組沒有其他還在、而且沒被改過的檔案，為了安全留著'})
                    n += len(sel); continue
                ref = keep[0]['path']
                for f in sel:
                    n += 1; rm['progress'] = n / total; rm['msg'] = f'逐位元組確認 {n:,} / {total:,}…'
                    if not self._same_now(f['path'], g['size'], f['mtime']):
                        refused.append({'path': f['path'], 'why': '找到之後被修改、移動或刪除過，沒有動它'}); continue
                    try: same = self._equal(f['path'], ref)
                    except OSError as e: refused.append({'path': f['path'], 'why': f'讀不到：{e.strerror or e}'}); continue
                    if not same: refused.append({'path': f['path'], 'why': f'內容和 {ref} 不完全一樣（只比對開頭結尾時可能誤判），沒有動它'}); continue
                    ok.append(f['path'])
            if ok:
                jid = self.eng.queue.add('vault', ok, opts={'reason': '重複檔案：你在「重複檔案」頁刪除（已逐位元組確認，同一組還留著相同的檔案）'})
                rm['job'] = jid
            gone = {norm(p) for p in ok}
            with self.lock:                                              # the results no longer list what went to the vault
                out = []
                for g in self.st['groups']:
                    fs = [f for f in g['files'] if norm(f['path']) not in gone]
                    if len(fs) > 1: out.append(dict(g, files=fs, wasted=g['size'] * (len(fs) - 1)))
                self.st['groups'] = out; self.st['wasted'] = sum(x['wasted'] for x in out)
            rm.update(state='done', queued=len(ok), refused=refused[:500], nrefused=len(refused), progress=1.0,
                      msg=f'{len(ok):,} 個放進保管區' + (f'，{len(refused):,} 個沒有動（見下方原因）' if refused else ''))
        except InterruptedError:
            rm.update(state='canceled', msg='已停止，沒有放進保管區', refused=refused[:500])
        except Exception as e:
            self.eng.log.exc('dupes', 'remove'); rm.update(state='error', msg=str(e))

    def start(self, path, min_size=1024 * 1024, full=True):
        if self.th and self.th.is_alive(): raise ValueError('已經在找了')
        if self.rm_th and self.rm_th.is_alive(): raise ValueError('正在確認要刪除的檔案，請稍候')
        self.stop_ev = threading.Event(); self.rm = {'state': 'idle'}
        self.st = {'state': 'running', 'msg': '列出檔案…', 'progress': 0.0, 'groups': [], 'path': path, 't': time.time(), 'files': 0, 'wasted': 0,
                   'min': min_size, 'full': full}
        self.th = threading.Thread(target=self._run, args=(path, min_size, full), name='HZ-Dupes', daemon=True); self.th.start()

    def cancel(self):
        self.stop_ev.set()

    def _files(self, path, min_size):
        out = None
        if path:
            out = self.eng.index.subtree_files(path)
        else:
            out = []
            for key in list(self.eng.index.vols):
                fs = self.eng.index.all_files(key, min_size)
                if fs: out.extend((p, s, 0) for p, s in fs)
        if out is None:                                                      # not indexed: walk
            out = []
            for root, ds, fs, _links in W.walk(path):                     # never into junctions
                if self.stop_ev.is_set(): break
                ds[:] = [d for d in ds if d != '.HotZoneVault']
                for f in fs:
                    p = os.path.join(root, f)
                    try: st = os.stat(p); out.append((p, st.st_size, st.st_mtime))
                    except OSError: pass
        return [(p, s) for p, s, *_ in out if s >= max(1, min_size) and p and not _skip(p)]   # (empty files: nothing to save)

    def _pace(self, busy):
        pct = max(10, min(100, int(self.eng.S.get('transfer.usage_pct') or 80)))
        if pct < 100 and busy > 0: self.stop_ev.wait(busy * (100 - pct) / pct)

    def _hash(self, path, part):
        h = hashlib.md5(); t0 = time.monotonic()
        with open(W.lp(path), 'rb') as f:
            if part:
                h.update(f.read(PART))
                try:
                    size = os.fstat(f.fileno()).st_size
                    if size > PART: f.seek(max(PART, size - PART)); h.update(f.read(PART))   # (64-128 KB used to be half-compared)
                except OSError:
                    pass
                self._pace(time.monotonic() - t0)
            else:
                while True:
                    if self.stop_ev.is_set(): raise InterruptedError
                    t0 = time.monotonic(); b = f.read(4 * 1024 * 1024)
                    if not b: break
                    h.update(b); self._read += len(b)
                    self._pace(time.monotonic() - t0)
        return h.hexdigest()

    def _run(self, path, min_size, full):
        W.thread_background(True)
        st = self.st; self._read = 0
        try:
            files = self._files(path, min_size)
            st['files'] = len(files)
            by = {}
            for p, s in files: by.setdefault(s, []).append(p)
            cands = [(s, ps) for s, ps in by.items() if len(ps) > 1]
            n = sum(len(ps) for _, ps in cands); done = 0
            st['msg'] = f'{len(files):,} 個檔案裡，{n:,} 個大小相同，比對開頭與結尾…'
            groups = []
            for s, ps in cands:
                sub = {}
                for p in ps:
                    if self.stop_ev.is_set(): raise InterruptedError
                    try: sub.setdefault(self._hash(p, True), []).append(p)
                    except (OSError, InterruptedError) as e:
                        if isinstance(e, InterruptedError): raise
                    done += 1
                    st['progress'] = 0.3 * done / max(1, n)
                for k, g in sub.items():
                    if len(g) > 1: groups.append((s, g))
            if full:
                total = sum(s * len(g) for s, g in groups); self._read = 0
                st['msg'] = f'完整比對 {len(groups):,} 組（{fmt_size(total)}）…'
                final = []
                for s, g in sorted(groups, key=lambda x: -x[0] * (len(x[1]) - 1)):
                    sub = {}
                    for p in g:
                        try: sub.setdefault(self._hash(p, False), []).append(p)
                        except InterruptedError: raise                       # (a subclass of OSError: a stop looked like 'none found')
                        except OSError: pass
                        st['progress'] = 0.3 + 0.7 * self._read / max(1, total)
                    final += [(s, gg) for gg in sub.values() if len(gg) > 1]
                groups = final
            out = []
            for s, g in groups:
                items = []; seen = set()
                for p in g:
                    try: st_ = os.stat(W.lp(p)); mt = st_.st_mtime; ident = (st_.st_dev, st_.st_ino) if st_.st_ino else None
                    except OSError: mt = 0; ident = None
                    if ident and ident in seen: continue                     # a hard link of a file already listed
                    if ident: seen.add(ident)
                    items.append({'path': p, 'mtime': mt, 'hot': self.eng.hot.is_hot(p)})
                if len(items) > 1: out.append({'size': s, 'files': items, 'wasted': s * (len(items) - 1), 'partial': not full})
            out.sort(key=lambda x: -x['wasted'])
            if self.stop_ev.is_set(): raise InterruptedError
            st.update(groups=out, wasted=sum(x['wasted'] for x in out), state='done', progress=1.0,
                      msg=f'找到 {len(out):,} 組重複檔案，可以省下 {fmt_size(sum(x["wasted"] for x in out))}' + ('' if full else '（只比對開頭與結尾：可能相同，刪除前會逐位元組確認）'))
            self.eng.log.info('dupes', st['msg'])
        except InterruptedError:
            st.update(state='canceled', msg='已停止')
        except Exception as e:
            self.eng.log.exc('dupes', 'scan'); st.update(state='error', msg=str(e))

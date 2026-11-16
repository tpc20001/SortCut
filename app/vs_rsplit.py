"""🚚 R 碟清空搬移（V0.5.85）：把一顆硬碟（預設 R:）的所有檔案分到兩顆硬碟，搬完 R 是空的.

使用者要把 R（NAS 級）交給 TikLive，上面的檔案分到兩顆 4 TB，之後直接在 4 TB 上繼續用（不用再搬一次）。
規則（一定要確認，不能馬虎）：
- 開始前：SortCut 和 FileCompare 所有背景工作先暫停（不再讀 R），搬完自動恢復。
- 分法：R 最上層的資料夾為單位，大的先放、放進目前剩比較多的那顆；一個資料夾比一顆的空間還大就拆到下一層。
  位置照舊：R:\\A\\b.mp4 → S:\\A\\b.mp4（只換磁碟代號），分類資料夾、VideoSIFT（初剪、歸檔）都一樣。
- 每個檔：複製（同時算原檔指紋）→ 寫進硬碟（FlushFileBuffers）→ **不經過快取**整檔讀回新檔再算一次指紋 →
  兩個指紋一樣、原檔沒被改過 → 紀錄（SortCut、FileCompare）改到新位置、預覽圖跟著搬 → 最後才刪 R 上的原檔。
  比對不一樣：刪掉新的那份、原檔留在 R、記在「沒搬成的」。
- 兩條線同時跑：複製到 A 碟的同時，驗證 B 碟剛寫好的那個（每顆硬碟同時只做一件事，不會互搶）。
- 進度存在資料庫（rsplit.sqlite3），關掉程式、熱更新、當機都會從剩下的接著搬。
- 全部搬完：R 上的空資料夾清掉；影片庫和整理的資料夾清單把 R 拿掉、換成兩顆新的；兩顆的紀錄寫到硬碟上。
沒有 Qt。
"""
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import threading
from collections import deque
import time
from pathlib import Path

IS_WIN = os.name == 'nt'
SKIP_TOP = {'$recycle.bin', 'system volume information', 'recycler', 'found.000'}
MARGIN = 30e9                                                                   # 每顆留 30 GB 不塞滿
CHUNK = 8 << 20
FILL_MIN = 20e9                                                                 # 「塞滿」只塞到剩 20 GB；再小就不拆了，剩下的整個資料夾放另一顆


def DR(X):
    """磁碟代號 → 根目錄（測試時會換掉）."""
    return str(X)[:1].upper() + ':\\'


def L(p):
    """長路徑（超過 260 字）也能開."""
    p = str(p)
    if IS_WIN and not p.startswith('\\\\?\\') and len(p) > 1 and p[1] == ':': return '\\\\?\\' + p
    return p


def _reg():
    d = getattr(sys, '_vs_rsplit', None)
    if not isinstance(d, dict): d = {'obj': None}; setattr(sys, '_vs_rsplit', d)
    return d


def fmt_b(b):
    b = float(b or 0)
    for u in ('B', 'KB', 'MB', 'GB', 'TB'):
        if abs(b) < 1024 or u == 'TB': return f'{b:.0f} {u}' if u in ('B', 'KB') else f'{b:.1f} {u}'
        b /= 1024


def read_nocache(path, cb=None):
    """不經過 Windows 快取，直接從硬碟整檔讀一次，回傳 blake2b 指紋（真的驗證硬碟上的資料，不是記憶體裡剛寫的那份）."""
    h = hashlib.blake2b(digest_size=32)
    if IS_WIN:
        try:
            import ctypes
            from ctypes import wintypes
            k = ctypes.windll.kernel32
            k.CreateFileW.restype = ctypes.c_void_p; k.VirtualAlloc.restype = ctypes.c_void_p
            fh = k.CreateFileW(L(path), 0x80000000, 0x1, None, 3, 0x20000000 | 0x08000000, None)   # GENERIC_READ, SHARE_READ, OPEN_EXISTING, NO_BUFFERING|SEQUENTIAL
            if fh and fh != ctypes.c_void_p(-1).value:
                buf = k.VirtualAlloc(None, CHUNK, 0x3000, 0x04)                  # 對齊的記憶體（不經快取讀一定要對齊）
                try:
                    got = wintypes.DWORD(0)
                    while True:
                        if not k.ReadFile(ctypes.c_void_p(fh), ctypes.c_void_p(buf), CHUNK, ctypes.byref(got), None): raise OSError(f'ReadFile 失敗 {k.GetLastError()}')
                        n = got.value
                        if n == 0: break
                        h.update(ctypes.string_at(buf, n))
                        if cb: cb(n)
                        if n < CHUNK: break
                    return h.hexdigest()
                finally:
                    k.VirtualFree(ctypes.c_void_p(buf), 0, 0x8000); k.CloseHandle(ctypes.c_void_p(fh))
        except Exception: h = hashlib.blake2b(digest_size=32)
    with open(L(path), 'rb', buffering=0) as f:                                 # 非 Windows（測試）或上面失敗
        while True:
            b = f.read(CHUNK)
            if not b: break
            h.update(b)
            if cb: cb(len(b))
    return h.hexdigest()


class RSplit:
    def __init__(self, E):
        self.E = E; self.stop_req = False; self.run = False; self.th = []; self.cur = {'copy': '', 'verify': '', 'copy_t': '', 'verify_t': ''}
        self.speed = 0.0; self._win = []; self.err = ''
        self.dbp = Path(E.data) / 'rsplit.sqlite3'; self.lock = threading.RLock()
        self.vq = []; self.vcv = threading.Condition()
        # V0.5.87 速度控制、每個檔的進度
        from collections import deque
        self.iolock = threading.Lock(); self.serial = False; self.pct = 100; self.pct_why = ''; self.f_copy = {}; self.f_ver = {}
        self.taken = set(); self.f_copies = {}; self._tl = threading.local(); self.ncopy = 1
        self.io_w = {}; self.io_r = deque(maxlen=4000); self.hist = {}                           # V0.5.96 每顆硬碟自己算的讀寫速度（Windows 計數器拿不到時用）
        self.recent = deque(maxlen=120); self.donew = deque(maxlen=4000); self.io = deque(maxlen=4000); self.plog = deque(maxlen=40)
        self.kick_t = 0.0; self.act_base = 0.0; self.busy_since = 0.0; self.mode_t = 0.0; self.mrate = {}; self.probe = None; self.sess_b = 0

    # ---------------------------------------------------------------- 資料庫（進度）
    def db(self):
        c = getattr(self, '_c', None)
        if c is None:
            c = self._c = sqlite3.connect(str(self.dbp), check_same_thread=False, timeout=30)
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY, src TEXT, dst TEXT, size INTEGER, tgt TEXT, st INTEGER DEFAULT 0, err TEXT, h TEXT)')
            c.execute('CREATE INDEX IF NOT EXISTS i_st ON items(st, tgt)')
            c.execute('CREATE INDEX IF NOT EXISTS i_sz ON items(st, tgt, size)'); c.execute('PRAGMA synchronous=NORMAL'); c.commit()   # V0.5.97
        return c

    def q(self, sql, a=()):
        with self.lock: return self.db().execute(sql, a).fetchall()

    def x(self, sql, a=()):
        with self.lock:
            c = self.db(); c.execute(sql, a); c.commit()

    def meta(self, k, d=None):
        r = self.q('SELECT v FROM meta WHERE k=?', (k,))
        return json.loads(r[0][0]) if r else d

    def set_meta(self, k, v): self.x('INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)', (k, json.dumps(v, ensure_ascii=False)))

    # ---------------------------------------------------------------- 計畫
    def drives(self):
        out = []
        try: letters = sorted(set(self.E.vol_letters().values()))
        except Exception: letters = []
        if not letters: letters = [c for c in 'DEFGHIJKLMNOPQRSTUVWXYZ' if os.path.exists(DR(c))]
        letters = [c for c in letters if c != 'C']
        for X in letters:
            try:
                du = shutil.disk_usage(DR(X))
                try: lb = self.E.vol_label(DR(X)) or ''
                except Exception: lb = ''
                out.append({'X': X, 'label': lb, 'used': du.total - du.free, 'free': du.free, 'total': du.total})
            except Exception: pass
        return out

    def _drv_stats(self, P):
        """V0.5.96 R／U／V 三顆：忙碌 %、讀、寫 MB/s（Windows 的計數器，SortCut 本來每 2 秒就在量，這裡只是拿來看，不另外多問）."""
        S = P.get('src') or 'R'; T = list(P.get('tgts') or []); busy = {}; rw = {}
        try:
            import vs_yield
            y = vs_yield.get(); sm = (y.sample or {}) if y is not None else {}
            busy = sm.get('disk') or {}; rw = sm.get('disk_rw') or {}
            W_ = getattr(y, 'win', None) if y is not None else None
            if W_ is not None and busy and any(X + ':' not in busy for X in [S] + T) and time.time() - getattr(self, '_pdh_t', 0) > 60:
                self._pdh_t = time.time()                                        # V0.5.98 後來才接上的硬碟（V:）Windows 計數器裡沒有 → 重建一次
                try: W_._pdh_init()
                except Exception: pass
        except Exception: pass
        out = []
        for X in [S] + T:
            k = X + ':'; r_ = rw.get(k)
            if r_ is not None: rd, wr, src = r_[0], r_[1], 'win'
            else:
                rd = self._win_rate(self.io_r, 5) if X == S else 0.0
                wr = self._win_rate(self.io_w.get(X) or (), 5) if X != S else 0.0; src = 'self'
            role = '來源' if X == S else ('已分類・倉庫' if P.get('mode') == 'cls' and X == T[0] else '還沒分類・工作' if P.get('mode') == 'cls' else '目的')
            out.append({'X': X, 'role': role, 'busy': round(float(busy[k])) if k in busy else None, 'rd': rd, 'wr': wr, 'src': src})
        return out

    def _win_rate(self, dq, win):
        now = time.time(); return sum(n for t, n in list(dq) if now - t < win) / win if self.run else 0.0

    def _drives_c(self):
        c = getattr(self, '_dc', None)
        if not c or time.time() - c[0] > 30: c = self._dc = (time.time(), self.drives())
        return c[1]

    def _skip_rel(self, rel):
        """不搬（或另外處理）的：資源回收筒…、.vsdata 裡的預覽圖（跟著紀錄走）、硬碟上的紀錄檔（新硬碟會自己重寫）."""
        parts = rel.lower().split(os.sep)
        if parts[0] in SKIP_TOP: return True
        if len(parts) >= 2 and parts[0] == 'videosift' and parts[1] == '.vsdata':
            if len(parts) == 3: return True                                      # .vsdata 底下直接放的檔（files.sqlite3、pack.json…）
            if len(parts) >= 3 and parts[2] in ('thumbs', 'filecompare'): return True
        return False

    CLS_TOP = ('filecompare_分類', 'videosift')                                   # 已分類：整理分好的、初剪／歸檔

    def _tagged(self, root):
        """整理裡「分好、搬過」的檔（分類有設別的位置的，不在 FileCompare_分類 底下）→ 也算已分類."""
        out = set(); FE = self.fe()
        if FE is None: return out
        try:
            for (p,) in FE.db.q('SELECT f.path FROM vc_tag t JOIN files f ON f.id=t.fid WHERE t.moved=1'):
                p = str(p or '')
                if p[:len(root)].lower() == root.lower(): out.add(os.path.normcase(p[len(root):]))
        except Exception: pass
        return out

    def plan(self, src, tgts, mode='auto'):
        if getattr(self, 'planning', False): return {'ok': False, 'message': '已經在算了，等一下'}
        self.planning = True; t0 = time.time()
        try:
            r = self._plan(src, tgts, mode)
            try: self.E.log.w(f"🚚 R 碟搬移「先算一下」：{time.time() - t0:.0f} 秒・{r.get('n', 0):,} 個檔・{r.get('message', '') or 'OK'}")
            except Exception: pass
            return r
        finally: self.planning = False; self.pmsg = ''

    def _plan(self, src, tgts, mode='auto'):
        """只讀：算出每個資料夾放哪顆、空間夠不夠；同時把要搬的檔案清單存起來（開始時就不用再算）.
        mode='auto' 兩顆平均；mode='cls'（V0.5.86）已分類放目的 ①、還沒分類放目的 ②（② 放不下的從大的資料夾開始補到 ①）."""
        S = str(src)[:1].upper(); T = [str(t)[:1].upper() for t in tgts if t]; mode = 'cls' if mode == 'cls' else 'auto'
        if len(T) != 2 or len(set(T + [S])) != 3: return {'ok': False, 'message': '來源和兩顆目的要是三顆不同的硬碟'}
        if self.state() in ('run', 'pause'): return {'ok': False, 'message': '搬到一半，不能重算（要先「清掉這次的紀錄」）'}
        root = DR(S)
        if not os.path.isdir(root): return {'ok': False, 'message': f'{S}: 沒接著'}
        tagged = self._tagged(root) if mode == 'cls' else set()
        G = {'cls': {'sizes': {}, 'files': []}, 'unc': {'sizes': {}, 'files': []}}; files = []; nf = 0; tot = 0
        gen = self.pgen = getattr(self, 'pgen', 0) + 1; self.pmsg = f'讀 {S}: 上的檔案…'; last = time.time()
        stack = ['']                                                             # V0.5.89 用 scandir（大小直接拿，不用每個檔再問一次硬碟）
        while stack:
            rel_d = stack.pop()
            try: it = list(os.scandir(L(os.path.join(root, rel_d) if rel_d else root)))
            except Exception: continue
            for e in it:
                rel = os.path.join(rel_d, e.name) if rel_d else e.name
                try:
                    if e.is_dir(follow_symlinks=False):
                        if rel_d == '' and e.name.lower() in SKIP_TOP: continue
                        if rel.lower().replace('/', os.sep) == os.path.join('videosift', '.vsdata', 'thumbs'): continue
                        stack.append(rel); continue
                    if not e.is_file(follow_symlinks=False): continue
                    if self._skip_rel(rel): continue
                    sz = e.stat(follow_symlinks=False).st_size
                except Exception: continue
                parts = rel.split(os.sep)
                is_cls = mode == 'cls' and ((len(parts) > 1 and parts[0].lower() in self.CLS_TOP) or os.path.normcase(rel) in tagged)
                g = G['cls' if is_cls else 'unc']; files.append((rel, sz, is_cls)); nf += 1; tot += sz
                if is_cls and not (len(parts) > 1 and parts[0].lower() in self.CLS_TOP): g['files'].append((rel, sz)); continue   # 單獨的已分類檔：一個一個放
                for i in range(1, len(parts)):                                  # 每一層資料夾的總大小
                    k = os.sep.join(parts[:i]); g['sizes'][k] = g['sizes'].get(k, 0) + sz
                g.setdefault('byd', {}).setdefault(os.path.dirname(rel), []).append((rel, sz))
            if time.time() - last > 1:
                last = time.time(); self.pmsg = f'讀 {S}: 上的檔案：{nf:,} 個、{fmt_b(tot)}…'
                if self.pgen != gen: return {'ok': False, 'message': '取消了'}
        self.pmsg = f'讀完 {nf:,} 個檔、{fmt_b(tot)}，算怎麼分…'
        free = {}
        for t in T:
            try: free[t] = shutil.disk_usage(DR(t)).free - MARGIN
            except Exception: return {'ok': False, 'message': f'{t}: 沒接著'}
        rem = dict(free); assign = []

        import heapq

        def place(g, pref, fill=False):
            """fill=True：先盡量塞滿第一順位那顆（放不下就先拆到下一層；那顆剩不到 20 GB 就不再拆）. V0.5.89 用 heap（幾十萬個檔也很快）."""
            sizes = g['sizes']; byd = g.get('byd') or {}; kids = {}
            for k in sizes: kids.setdefault(os.path.dirname(k), []).append(k)
            loose = {d: sum(x[1] for x in L_) for d, L_ in byd.items()}
            H = []; seq = [0]

            def push(rel, sz, kind): seq[0] += 1; heapq.heappush(H, (-sz, seq[0], rel, kind))
            for k in kids.get('', []): push(k, sizes[k], 'dir')
            for r_, z_ in g['files']: push(r_, z_, 'file')
            if loose.get(''): push('', loose[''], 'loose')
            while H:
                nz, _q, rel, kind = heapq.heappop(H); sz = -nz
                P_ = pref(); t = next((x for x in P_ if sz <= rem[x]), None)
                split_ok = (kind == 'dir' and (kids.get(rel) or len(byd.get(rel, [])) > 1)) or (kind == 'loose' and len(byd.get(rel, [])) > 1)
                if fill and t is not None and t != P_[0] and split_ok and rem[P_[0]] > FILL_MIN: t = None
                if t: assign.append((rel, kind, t, sz)); rem[t] -= sz; continue
                if kind == 'dir' and kids.get(rel):
                    for k in kids[rel]: push(k, sizes[k], 'dir')
                    if loose.get(rel): push(rel, loose[rel], 'loose')
                    continue
                if kind in ('dir', 'loose') and len(byd.get(rel, [])) > 1:             # 同一層的檔太多放不下：一個一個分（同一個資料夾會分在兩顆）
                    for r_, z_ in byd[rel]: push(r_, z_, 'file')
                    continue
                return f'空間不夠：「{rel or "根目錄的檔"}」{fmt_b(sz)} 放不進任何一顆（兩顆各剩 {", ".join(f"{x}: {fmt_b(free[x])}" for x in T)}）'
            return ''
        if mode == 'cls':
            e_ = place(G['cls'], lambda: [T[0], T[1]]) or place(G['unc'], lambda: [T[1], T[0]], fill=True)
        else:
            e_ = place(G['unc'], lambda: sorted(T, key=lambda x: -rem[x]))
        if e_: return {'ok': False, 'message': e_, 'total': tot, 'free': free}
        amap = {(a[0], a[1]): a[2] for a in assign}

        def tgt_of(rel):
            if (rel, 'file') in amap: return amap[(rel, 'file')]
            par = os.path.dirname(rel)
            if (par, 'loose') in amap: return amap[(par, 'loose')]
            p2 = par
            while p2:
                if (p2, 'dir') in amap: return amap[(p2, 'dir')]
                p2 = os.path.dirname(p2)
            return amap.get(('', 'loose')) or T[0]
        self.pmsg = f'存清單（{nf:,} 個檔）…'; TG = {rel: tgt_of(rel) for rel, _z, _c in files}   # V0.5.91 先算好再鎖資料庫（不要讓畫面等）
        rows = [(root + rel, DR(TG[rel]) + rel, sz, TG[rel]) for rel, sz, _c in files]
        with self.lock:
            c = self.db(); c.execute('DELETE FROM items'); c.execute('DELETE FROM meta')
            c.executemany('INSERT INTO items(src,dst,size,tgt) VALUES(?,?,?,?)', rows); c.commit()
        per = {t: 0 for t in T}; pern = {t: 0 for t in T}
        for t, n, b in self.q('SELECT tgt, COUNT(*), TOTAL(size) FROM items GROUP BY tgt'): per[t] = b; pern[t] = n
        cls_b = sum(z for _r, z, c_ in files if c_); cls_n = sum(1 for f_ in files if f_[2])
        spill = sum(1 for _r, z, c_ in files if mode == 'cls' and not c_ and TG[_r] == T[0]); spill_b = sum(z for _r, z, c_ in files if mode == 'cls' and not c_ and TG[_r] == T[0])
        P = {'ok': True, 'mode': mode, 'src': S, 'tgts': T, 'n': nf, 'total': tot, 'free': {t: free[t] + MARGIN for t in T}, 'per': per, 'pern': pern,
             'cls_n': cls_n, 'cls_b': cls_b, 'unc_n': nf - cls_n, 'unc_b': tot - cls_b, 'spill_n': spill, 'spill_b': spill_b,
             'units': [{'rel': a[0] or '（根目錄的檔）', 'kind': a[1], 'tgt': a[2], 'b': a[3]} for a in sorted(assign, key=lambda a: (a[2], -a[3]))][:3000], 't': time.time()}
        self.set_meta('plan', P); self.set_meta('state', 'planned')
        return P

    # ---------------------------------------------------------------- 開始／暫停／停
    def state(self):
        try: return self.meta('state', '') or ''
        except Exception: return ''

    def start(self):
        P = self.meta('plan')
        if not P: return {'ok': False, 'message': '先按「🔍 先算一下」'}
        if self.state() == 'run' and self.run: return {'ok': False, 'message': '已經在搬了'}
        if self.run: return {'ok': False, 'message': '還在把手上的做完（收尾中），等畫面寫「已停好」再按繼續'}
        for t in [P['src']] + P['tgts']:
            if not os.path.isdir(DR(t)): return {'ok': False, 'message': f'{t}: 沒接著（硬碟代號是不是換了？上面可以改）'}
        bad = [c for c in self.vol_check() if not c['ok']]
        if bad: return {'ok': False, 'message': '硬碟對不上：' + '、'.join(f"{c['X']}:（{c['role']}）" + (f" 應該是現在的 {c['found']}:" if c.get('found') else ' 找不到原本那顆') for c in bad) + '。先在上面「💽 硬碟代號」改好再繼續'}
        self._remember_vols()
        self._prepare(P); self.set_meta('state', 'run')
        if not self.meta('t0'): self.set_meta('t0', time.time())
        self.E.log.w(f"🚚 R 碟清空搬移開始：{P['src']}: → {P['tgts'][0]}: ＋ {P['tgts'][1]}:（{P['n']:,} 個檔、{fmt_b(P['total'])}）")
        self.kick(); return {'ok': True, 'message': '開始搬了（背景跑，可以關畫面）'}

    def _prepare(self, P):
        """暫停所有背景工作（不讀 R）、兩顆新硬碟加進影片庫和整理的清單（紀錄才有地方掛）."""
        E = self.E
        if not self.meta('paused'):
            was = [k for k, _i, _n in E.BG_KINDS if E.bg_pause.get(k)]; self.set_meta('paused', {'vs': was, 'fc': []})
            for k, _i, _n in E.BG_KINDS:
                if k != 'move':
                    try: E.bg_set_pause(k, True, '🚚 R 碟清空搬移中'); E.bg_stop_now(k)       # 正在做的也停（放回排隊），不再讀 R
                    except Exception: pass
            FE = self.fe()
            if FE is not None:
                wf = [k for k in getattr(FE, 'FC_KINDS', ()) if FE.bg_pause.get(k)]; m = self.meta('paused'); m['fc'] = wf; self.set_meta('paused', m)
                for k in list(getattr(FE, 'FC_KINDS', ())):
                    try: FE.bg_set_pause(k, True, '🚚 R 碟清空搬移中'); FE.bg_stop_now(k)
                    except Exception: pass
                try:                                                             # 🗜 瘦身正在轉的：停掉（之後要從 4 TB 上重新選）
                    SL = getattr(FE, 'slim', None)
                    if SL is not None and SL.st.get('run'): SL.st['cancel'] = True; m = self.meta('paused'); m['slim'] = True; self.set_meta('paused', m)
                except Exception: pass
        R = [str(x) for x in E.cfg.get('roots') or []]
        for t in P['tgts']:
            nr = DR(t)
            if not any(str(r)[:1].upper() == t for r in R):
                R.append(nr); sn = E.vol_serial(nr)
                if sn: vol = dict(E.cfg.get('root_vol') or {}); vol[nr] = sn; E.cfg.set('root_vol', vol)
        E.cfg.set('roots', R)
        FE = self.fe()
        if FE is not None:
            for t in P['tgts']:
                if not any(str(r)[:1].upper() == t for r in FE.fc_list('roots')):
                    try: FE.fc_list_add('roots', DR(t))
                    except Exception: pass

    def ctl(self, a, d_=None):
        if a == 'pause':                                                        # V0.5.99 溫和暫停：不拿新的；手上正在搬的（大檔、排好的小檔）做完、確認完才停
            self.no_new = True; self.set_meta('state', 'pause'); self._remember_vols()
            try: self.E.log.w('🚚 R 碟搬移：暫停（手上的做完再停；之後要按「繼續」才會再搬）')
            except Exception: pass
            return {'ok': True, 'message': '⏸ 暫停：手上正在搬的做完就停（畫面會寫「已停好」），之後不會自己開始'}
        if a == 'remap': return self.remap(d_ or {})
        if a in ('resume', 'start'): return self.start()
        if a == 'reset' and self.state() in ('planned', 'done', 'pause', ''):
            if self.run: return {'ok': False, 'message': '還在停（手上的檔做完），等一下再按'}
            if self.meta('paused'): self._restore('🚚 R 碟搬移紀錄清掉了')
            self.x('DELETE FROM items'); self.x('DELETE FROM meta'); return {'ok': True, 'message': '清掉了'}
        return {'ok': False, 'message': '現在不能這樣做'}

    # ---------------------------------------------------------------- V0.5.99 硬碟代號：記住每顆的序號，重開機代號跑掉也認得出來
    def _vser(self, X):
        try: return self.E.vol_serial(DR(X)) or ''
        except Exception: return ''

    def _remember_vols(self):
        P = self.meta('plan') or {}
        if not P.get('src'): return
        V = dict(P.get('vols') or {}); ch = False
        for X in [P['src']] + list(P.get('tgts') or []):
            if X not in V and os.path.isdir(DR(X)):
                sn = self._vser(X)
                if sn:
                    try: lb = self.E.vol_label(DR(X)) or ''
                    except Exception: lb = ''
                    V[X] = {'sn': sn, 'label': lb}; ch = True
        if ch: P['vols'] = V; self.set_meta('plan', P)

    def vol_check(self):
        """每顆（來源、①、②）：現在這個代號還是不是原本那顆；不是的話，原本那顆現在在哪個代號."""
        P = self.meta('plan') or {}; V = P.get('vols') or {}; out = []
        if not P.get('src'): return out
        T = list(P.get('tgts') or []); roles = {P['src']: '來源'}
        for i, t in enumerate(T): roles[t] = ('① 已分類' if i == 0 else '② 還沒分類') if P.get('mode') == 'cls' else f'目的 {"①②"[i]}'
        letters = [c for c in 'DEFGHIJKLMNOPQRSTUVWXYZ' if os.path.isdir(DR(c))]
        for X in [P['src']] + T:
            want = (V.get(X) or {}).get('sn', ''); now = self._vser(X) if os.path.isdir(DR(X)) else ''
            ok = bool(os.path.isdir(DR(X))) and (not want or not now or now == want)
            found = ''
            if not ok and want:
                found = next((Y for Y in letters if self._vser(Y) == want), '')
            out.append({'X': X, 'role': roles.get(X, ''), 'label': (V.get(X) or {}).get('label', ''), 'want': want, 'now': now, 'ok': ok, 'found': found})
        return out

    def remap(self, M):
        """把這次搬移裡的磁碟代號換掉（舊 → 新）：搬移清單、分法、SortCut、整理的紀錄一起改；檔案本身不動."""
        M = {str(a)[:1].upper(): str(b)[:1].upper() for a, b in (M or {}).items() if a and b and str(a)[:1].upper() != str(b)[:1].upper()}
        if not M: return {'ok': False, 'message': '沒有要換的'}
        if self.run: return {'ok': False, 'message': '還在收尾，等「已停好」再改'}
        if self.state() not in ('pause', 'planned'): return {'ok': False, 'message': '要先暫停才能改代號'}
        for b in M.values():
            if not os.path.isdir(DR(b)): return {'ok': False, 'message': f'{b}: 沒接著'}
        sw = lambda v: (M[v[:1].upper()] + v[1:]) if v and v[:1].upper() in M else v
        with self.lock:                                                          # 搬移清單（先加 # 再換，A↔B 互換也不會亂）
            c = self.db()
            for a, b in M.items():
                c.execute("UPDATE items SET src='#'||?||substr(src,2) WHERE upper(substr(src,1,1))=?", (b, a))
                c.execute("UPDATE items SET dst='#'||?||substr(dst,2) WHERE upper(substr(dst,1,1))=?", (b, a))
                c.execute("UPDATE items SET tgt='#'||? WHERE tgt=?", (b, a))
            c.execute("UPDATE items SET src=substr(src,2) WHERE substr(src,1,1)='#'"); c.execute("UPDATE items SET dst=substr(dst,2) WHERE substr(dst,1,1)='#'")
            c.execute("UPDATE items SET tgt=substr(tgt,2) WHERE substr(tgt,1,1)='#'"); c.commit()
        P = self.meta('plan') or {}
        P['src'] = sw(P.get('src', '')); P['tgts'] = [sw(t) for t in P.get('tgts') or []]
        for k in ('per', 'pern', 'free'):
            if isinstance(P.get(k), dict): P[k] = {sw(x): v for x, v in P[k].items()}
        for u in P.get('units') or []: u['tgt'] = sw(u.get('tgt', ''))
        if isinstance(P.get('vols'), dict): P['vols'] = {sw(x): v for x, v in P['vols'].items()}
        self.set_meta('plan', P)
        E = self.E; msg = []
        try:                                                                     # SortCut（影片庫、分級、預覽圖、轉檔紀錄）
            r = E.drive_remap(M); msg.append(f"SortCut {r.get('n', 0):,} 部")
        except Exception: E.log.err('🚚 改代號：SortCut')
        FE = self.fe()
        if FE is not None:                                                       # 整理（指紋、分類、搬移紀錄）
            try:
                with FE.db.lock:
                    c = FE.db.con; n = 0
                    for a, b in M.items():
                        n += c.execute("UPDATE files SET path='#'||?||substr(path,2), root=CASE WHEN upper(substr(root,1,1))=? THEN ?||substr(root,2) ELSE root END, "
                                       "qpath=CASE WHEN upper(substr(qpath,1,1))=? THEN ?||substr(qpath,2) ELSE qpath END WHERE upper(substr(path,1,1))=?", (b, a, b, a, b, a)).rowcount
                        for tb, col in (('vc_tag', 'dst'), ('moves', 'src'), ('moves', 'dst')):
                            try: c.execute(f"UPDATE {tb} SET {col}='#'||?||substr({col},2) WHERE upper(substr({col},1,1))=?", (b, a))
                            except Exception: pass
                    c.execute("UPDATE files SET path=substr(path,2) WHERE substr(path,1,1)='#'")
                    for tb, col in (('vc_tag', 'dst'), ('moves', 'src'), ('moves', 'dst')):
                        try: c.execute(f"UPDATE {tb} SET {col}=substr({col},2) WHERE substr({col},1,1)='#'")
                        except Exception: pass
                    c.commit()
                for r_ in list(FE.fc_list('roots')):
                    if str(r_)[:1].upper() in M:
                        try: FE.fc_list_del('roots', r_)
                        except Exception: pass
                        try: FE.fc_list_add('roots', sw(str(r_)))
                        except Exception: pass
                msg.append(f'整理 {n:,} 個')
            except Exception:
                try: FE.db.con.rollback()
                except Exception: pass
                E.log.err('🚚 改代號：整理')
        txt = '💽 代號改好：' + '、'.join(f'{a}: → {b}:' for a, b in M.items()) + (f"（{'、'.join(msg)}的紀錄跟著改）" if msg else '')
        E.log.w('🚚 ' + txt); self._dc = None
        return {'ok': True, 'message': txt + '。確認沒問題再按「▶ 繼續」'}

    def fe(self):
        F = sys.modules.get('fc_app'); FE = getattr(F, 'ENG', None) if F else None
        return FE if type(FE).__name__ == 'Engine' else None

    def kick(self):
        if self.run: return
        self.stop_req = False; self.no_new = False; self.run = True; self.kick_t = time.time(); self.act_base = float(self.meta('act', 0) or 0); self.mode_t = time.time()
        T = list((self.meta('plan') or {}).get('tgts') or [])
        try: self.x('UPDATE items SET st=0 WHERE st=5')                             # 上次搬到一半（關掉、更新）的放回去
        except Exception: pass
        self.taken = set(); self.f_copies = {}; self._tl = threading.local()
        if self.vmode() == 'quick' and T:
            # V0.5.98 每顆目的硬碟：1 條「寫」（硬碟一次只寫一個地方最快，不會一直跳來跳去）＋ 3 條「從 R 先讀好小檔」放記憶體排隊；
            # 小檔不再一個一個強制寫進硬碟（那是最慢的地方），一批（300 個或 256 MB）寫完一起確認、一起改紀錄、一起刪 R 的
            self.sq = {t: {'q': deque(), 'cv': threading.Condition(), 'b': 0, 'rd': 3} for t in T}; self.ncopy = len(T)
            th_ = [threading.Thread(target=self._writer, args=(t,), name=f'RSplitWrite-{t}', daemon=True) for t in T]
            th_ += [threading.Thread(target=self._sreader, args=(t,), name=f'RSplitRead-{t}{k}', daemon=True) for t in T for k in range(3)]
        else:
            W_ = [(t, k == 0) for t in T for k in range(4)]                       # V0.5.97 每顆 4 條（1 大檔＋3 小檔）
            self.ncopy = len(W_) or 1
            th_ = [threading.Thread(target=self._copier, args=(t, b_), name=f'RSplitCopy-{t}{"大" if b_ else "小"}{i_}', daemon=True) for i_, (t, b_) in enumerate(W_)] \
                or [threading.Thread(target=self._copier, name='RSplitCopy', daemon=True)]
        self.th = th_ + \
                  [threading.Thread(target=self._verifier, name='RSplitVerify', daemon=True), threading.Thread(target=self._pacer, name='RSplitPace', daemon=True)]
        for t in self.th: t.start()

    def act(self):
        return self.act_base + ((time.time() - self.kick_t) if self.run and self.kick_t else 0)

    # ---------------------------------------------------------------- 速度：手動百分比／🧠 智能（V0.5.87）
    def cfg_pace(self):
        c = self.E.cfg
        return max(5, min(100, int(c.get('rs_pct') or 100))), c.get('rs_smart') is not False, (c.get('rs_serial') or 'auto')

    def set_pace(self, d):
        c = self.E.cfg
        if 'pct' in d: c.set('rs_pct', max(5, min(100, int(d['pct']))))
        if 'smart' in d: c.set('rs_smart', bool(d['smart']))
        if 'serial' in d and d['serial'] in ('auto', 'one', 'two'): c.set('rs_serial', d['serial'])
        if 'verify' in d and d['verify'] in ('quick', 'full'): c.set('rs_verify', d['verify'])
        self._decide(); return {'ok': True, 'message': ('比對：' + ('⚡ 快速（單向，抽查）' if self.vmode() == 'quick' else '🔎 完整（整檔讀回）')) if 'verify' in d else f'{"🧠 智能" if self.cfg_pace()[1] else "手動"}：現在 {self.pct}%'}

    def _rate(self, dq, win):
        now = time.time(); b = sum(n for t, n in dq if now - t < win)
        t0 = min([t for t, n in dq if now - t < win] or [now])
        return b / max(5.0, min(win, now - t0, now - (self.kick_t or now) + 0.001)) if b else 0.0

    def _decide(self):
        """每 3 秒：算這一刻要用幾 %、要不要兩顆一起跑。TikLive 一定優先（手動也一樣）；溫度高就慢；硬碟一直 100% 又變慢就改一次一個."""
        man, smart, ser = self.cfg_pace(); now = time.time()
        base = 100 if smart else man; why = '🧠 智能：全速' if smart else f'✋ 手動 {man}%'; caps = []
        busy = {}; temp = None
        try:
            import vs_yield
            y = vs_yield.get()
            if y is not None and y.on:
                S_ = y.sample or {}; G = y.gov
                # V0.5.93 搬檔幾乎只用硬碟（CPU 只用一點點算指紋）：TikLive 的等級是給轉檔那種吃 CPU／顯示卡的工作用的，
                # 這裡只在「TikLive 也在用這幾顆硬碟」或「CPU 真的快滿」時才讓，不然 TikLive Lv2 就把搬移壓到 20% → 一秒只搬幾 MB
                D = S_.get('disk') or {}; P = self.meta('plan') or {}; mine = [P.get('src', 'R')] + list(P.get('tgts') or [])
                for X in mine:
                    if X + ':' in D: busy[X] = round(float(D[X + ':']))
                shared = {X for X in mine if X + ':' in set(S_.get('tk_drives') or ())}
                if y.tk_pids and shared: caps.append((max(10, int(y.level) * 10), f'🤝 TikLive 也在用 {"、".join(sorted(shared))}: → 讓它（Lv {y.level}）'))
                if getattr(G, 'burst', False) and shared: caps.append((60, '🤝 TikLive 正要開始錄影／轉檔（先讓一下）'))   # V0.5.98 不共用硬碟就不用讓
                if y.read_alert(): caps.append((30, '⚡ TikLive 斷電警報'))
                cpu = S_.get('cpu')
                if cpu is not None and float(cpu) >= 95: caps.append((30, f'🔥 CPU 快滿了（{float(cpu):.0f}%）'))
                elif cpu is not None and float(cpu) >= 88: caps.append((60, f'🔥 CPU 很忙（{float(cpu):.0f}%）'))
            H = getattr(y, 'heat', None) if y is not None else None
            if H is not None:
                T_ = [float(v) for k, v in (H.sens or {}).items() if isinstance(v, (int, float)) and 'gpu' not in str(k).lower()]
                temp = max(T_) if T_ else None
                if H.state == 'hot': caps.append((20, H.why or '🌡 太熱'))
                elif H.state in ('warm', 'rest'): caps.append((50, H.why or '🌡 溫度偏高'))
            if temp is not None and temp >= 85: caps.append((20, f'🌡 CPU {temp:.0f}°C 太熱'))
            elif temp is not None and temp >= 78: caps.append((50, f'🌡 CPU {temp:.0f}°C 偏熱'))
        except Exception: pass
        for p_, w_ in caps:
            if p_ < base: base = p_; why = w_
        # 兩顆一起跑／一次一個
        rate = self._rate(self.io, 60)
        if ser == 'one': self.serial = True
        elif ser == 'two': self.serial = False
        elif smart:
            hot = any(v >= 97 for v in busy.values())
            self.busy_since = (self.busy_since or now) if hot else 0.0
            md = 'one' if self.serial else 'two'
            if now - self.mode_t > 90 and rate: self.mrate[md] = rate if md not in self.mrate else self.mrate[md] * 0.7 + rate * 0.3
            if self.probe and now - self.mode_t > 180:                            # 試另一種 3 分鐘：比較快就留著，不然換回來
                a_, b_ = self.mrate.get('one', 0), self.mrate.get('two', 0); keep = 'one' if a_ > b_ * 1.1 else 'two'
                self.serial = keep == 'one'; self.probe = None; self.mode_t = now
                self.plog.append((now, f'比過了：一次一個 {fmt_b(a_)}/s、兩顆一起 {fmt_b(b_)}/s → 用{"一次寫一顆" if self.serial else "兩顆同時寫"}'))
            elif not self.probe and not self.serial and self.busy_since and now - self.busy_since > 20 and rate < 0.6 * max(self.mrate.get('two', 0), 1):
                self.serial = True; self.mode_t = now; self.probe = 'one'; self.plog.append((now, f'硬碟一直 100% 又變慢（{fmt_b(rate)}/s）→ 先試一次一個'))
            elif not self.probe and now - self.mode_t > 900:                     # 每 15 分鐘試一下另一種（硬碟狀況會變，例如 SMR 硬碟快取滿了）
                self.serial = not self.serial; self.mode_t = now; self.probe = 'one' if self.serial else 'two'
                self.plog.append((now, f'試試看{"一次一個" if self.serial else "兩顆一起"}（3 分鐘後比速度）'))
        old = self.pct; self.pct = max(5, int(base)); self.pct_why = why; self.busy = busy; self.temp = temp
        if old != self.pct: self.plog.append((now, f'{old}% → {self.pct}%：{why}'))

    def _pacer(self):
        k = 0
        while self.run:
            try: self._decide()
            except Exception: pass
            try:                                                                 # V0.5.96 曲線圖：每 3 秒記一點（最多 100 點 ≈ 5 分鐘）
                for D_ in self._drv_stats(self.meta('plan') or {}):
                    self.hist.setdefault(D_['X'], deque(maxlen=100)).append((round(time.time()), D_['busy'], round(D_['rd']), round(D_['wr'])))
            except Exception: pass
            k += 1
            if k % 20 == 0:
                try: self.set_meta('act', self.act())
                except Exception: pass
            time.sleep(3)
        if self.kick_t:
            try: self.set_meta('act', self.act())
            except Exception: pass

    def _slow(self, dt):
        """照百分比放慢：做了 dt 秒，就休息 dt × (100/% − 1) 秒（硬碟、CPU 一起降）."""
        p = self.pct
        if p < 100 and dt > 0: time.sleep(min(3.0, dt * (100.0 / p - 1)))

    # ---------------------------------------------------------------- 兩條線：複製／驗證
    def _low(self):
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadPriority(ctypes.windll.kernel32.GetCurrentThread(), -1)
        except Exception: pass

    def _next(self, busy_tgt):
        """下一個要複製的：先挑「驗證那條沒在用」的那顆硬碟（兩顆輪流寫，一顆寫、另一顆讀回比對）."""
        if getattr(self, 'no_new', False): return None
        P = self.meta('plan') or {}; T = list(P.get('tgts') or [])
        last = getattr(self, 'last_t', '')                                       # V0.5.94 兩顆輪流寫（一個檔 U、下一個 V…），兩顆都在動、不會一顆一直被寫到滿載
        order = sorted(T, key=lambda t: (t == busy_tgt, t == last))
        for t in order:
            r = self.q('SELECT id, src, dst, size, tgt FROM items WHERE st=0 AND tgt=? ORDER BY id LIMIT 1', (t,))
            if r: return r[0]
        return None

    def _gate(self):
        """一次一個：複製和比對輪流用硬碟."""
        class _G:
            def __init__(s, o): s.o = o; s.l = None
            def __enter__(s):
                if s.o.serial: s.o.iolock.acquire(); s.l = s.o.iolock
            def __exit__(s, *a):
                if s.l is not None: s.l.release()
        return _G(self)

    BIG = 64 << 20

    def _claim(self, tgt, big):
        """V0.5.97 拿下一個要搬的（標成「處理中」=5，幾條線不會拿到同一個）. 大檔線拿最大的；小檔線照順序拿小檔（大檔線沒事做時也拿小檔）."""
        if getattr(self, 'no_new', False): return None                          # 暫停中：不拿新的
        with self.lock:
            c = self.db()
            if big: r = c.execute('SELECT id, src, dst, size, tgt FROM items WHERE st=0 AND tgt=? AND size>=? ORDER BY size DESC LIMIT 1', (tgt, self.BIG)).fetchone()
            else: r = None
            if r is None: r = c.execute('SELECT id, src, dst, size, tgt FROM items WHERE st=0 AND tgt=? AND size<? ORDER BY id LIMIT 1', (tgt, self.BIG)).fetchone()
            if r is None and not big: r = None
            if r is not None: c.execute('UPDATE items SET st=5 WHERE id=?', (r[0],)); c.commit()
            return r

    SBUF = 256 << 20

    def _sreader(self, t):
        """先從 R 把小檔整個讀進記憶體，排給那顆的「寫」（最多先讀 256 MB）."""
        self._low(); Q = self.sq[t]
        try:
            while not self.stop_req and not getattr(self.E, 'stop_all', False):
                with Q['cv']:
                    while Q['b'] >= self.SBUF and not self.stop_req: Q['cv'].wait(1)
                it = self._claim(t, False)
                if it is None or it[3] >= self.BIG:
                    if it is not None: self.x('UPDATE items SET st=0 WHERE id=? AND st=5', (it[0],))
                    break
                iid, s, d, sz, _t = it
                try:
                    st_ = os.stat(L(s))
                    with open(L(s), 'rb') as f: data = f.read()
                    now = time.time(); self.io_r.append((now, len(data))); self._tick(len(data))
                except FileNotFoundError: self.x("UPDATE items SET st=4, err='原檔已經不在' WHERE id=?", (iid,)); continue
                except Exception as ex: self._fail(iid, s, f'讀 R 失敗：{type(ex).__name__}: {ex}', sz, t); continue
                with Q['cv']: Q['q'].append((iid, s, d, sz, data, st_)); Q['b'] += len(data); Q['cv'].notify_all()
        finally:
            with Q['cv']: Q['rd'] -= 1; Q['cv'].notify_all()

    def _writer(self, t):
        """一顆目的硬碟一條：有排好的小檔就一直寫（不強制每個都寫進硬碟），一批一起確認；沒小檔就搬大檔（邊讀邊寫）."""
        self._low(); Q = self.sq[t]; batch = []; bt0 = 0.0; bb = 0; dirs = set(); me = threading.current_thread().name
        try:
            while not self.stop_req and not getattr(self.E, 'stop_all', False):
                it = None
                with Q['cv']:
                    if Q['q']: it = Q['q'].popleft(); Q['b'] -= len(it[4]); Q['cv'].notify_all()
                if it is not None:
                    try:
                        with self._gate():
                            d2 = self._wsmall(it, dirs)
                        if d2: batch.append((it[0], it[1], d2, it[3], it[4])); bb += it[3]; bt0 = bt0 or time.time()
                    except InterruptedError: break
                    except Exception as ex: self._fail(it[0], it[1], f'寫入失敗：{type(ex).__name__}: {ex}', it[3], t)
                    if len(batch) >= 300 or bb >= (128 << 20) or (batch and time.time() - bt0 > 3): self._commit(batch, t); batch = []; bb = 0; bt0 = 0.0
                    continue
                if batch: self._commit(batch, t); batch = []; bb = 0; bt0 = 0.0
                big = self._claim(t, True)
                if big is not None and big[3] < self.BIG and Q['rd'] > 0:
                    self.x('UPDATE items SET st=0 WHERE id=? AND st=5', (big[0],)); big = None   # 小檔交給讀的那幾條
                if big is None:
                    with Q['cv']:
                        if Q['rd'] <= 0 and not Q['q']: break
                        Q['cv'].wait(0.5)
                    continue
                iid, s, d, sz, _t = big; t0 = time.time(); ok_ = False
                F = {'name': os.path.basename(s), 'src': s, 'dst': d, 'tgt': t, 'size': sz, 'done': 0, 't0': t0, 'wait': self.serial, 'big': True}
                self.f_copies[me] = F; self._tl.F = F; self.f_copy = F; self.last_t = t
                try:
                    with self._gate():
                        F['wait'] = False; F['t0'] = time.time(); h, d2 = self._copy(s, d)
                    self.x('UPDATE items SET st=1, dst=?, h=? WHERE id=?', (d2, h, iid)); ok_ = True
                    self._ver(iid, s, d2, sz, t, h, time.time() - t0, inline=True)
                except InterruptedError: break
                except FileNotFoundError: self.x("UPDATE items SET st=4, err='原檔已經不在' WHERE id=?", (iid,)); ok_ = True
                except Exception as ex: self._fail(iid, s, f'複製失敗：{type(ex).__name__}: {ex}', sz, t); ok_ = True
                finally:
                    if not ok_:
                        try: self.x('UPDATE items SET st=0 WHERE id=? AND st=5', (iid,))
                        except Exception: pass
                    self.f_copies.pop(me, None); self._tl.F = None
                    if self.f_copy is F: self.f_copy = next(iter(self.f_copies.values()), {})
        finally:
            try:
                if batch: self._commit(batch, t)
            except Exception: pass
            with Q['cv']:                                                        # 沒寫的放回去（下次重搬）
                left = list(Q['q']); Q['q'].clear(); Q['b'] = 0
            for x_ in left:
                try: self.x('UPDATE items SET st=0 WHERE id=? AND st=5', (x_[0],))
                except Exception: pass
            self.f_copies.pop(me, None)
            with self.vcv:
                self.ncopy -= 1
                if self.ncopy <= 0: self.vq.append(None)
                self.vcv.notify_all()

    def _wsmall(self, it, dirs):
        iid, s, d, sz, data, st_ = it
        if self.stop_req: raise InterruptedError
        t0 = time.time()
        if os.path.exists(L(d)):
            if os.path.getsize(L(d)) == len(data):
                with open(L(d), 'rb') as f:
                    if f.read() == data: return d                                   # 上次已經寫好
            b, e = os.path.splitext(d); i = 2
            while os.path.exists(L(f'{b} ({i}){e}')): i += 1
            d = f'{b} ({i}){e}'
        dd = os.path.dirname(d)
        if dd not in dirs: os.makedirs(L(dd), exist_ok=True); dirs.add(dd)
        tmp = d + '.vsmove'
        with open(L(tmp), 'wb') as f: f.write(data)
        try: os.utime(L(tmp), ns=(st_.st_atime_ns, st_.st_mtime_ns))
        except Exception: pass
        os.replace(L(tmp), L(d))
        now = time.time(); n = len(data)
        try: self.io_w.setdefault(d[:1].upper(), deque(maxlen=4000)).append((now, n))
        except Exception: pass
        F_ = self.f_copies[threading.current_thread().name] = {'name': os.path.basename(d), 'src': s, 'dst': d, 'tgt': d[:1].upper(), 'size': n, 'done': n, 't0': t0, 'wait': False, 'small': True}
        self.f_copy = F_
        self._slow(now - t0)
        return d

    def _vflush(self, X):
        """整顆硬碟一次寫進去（要系統管理員權限）；不行就回 False，改成一個一個檔."""
        if not IS_WIN: return False
        try:
            import ctypes
            k = ctypes.windll.kernel32; k.CreateFileW.restype = ctypes.c_void_p
            h = k.CreateFileW('\\\\.\\' + X + ':', 0x40000000, 0x3, None, 3, 0, None)
            if not h or h == ctypes.c_void_p(-1).value: return False
            try: return bool(k.FlushFileBuffers(ctypes.c_void_p(h)))
            finally: k.CloseHandle(ctypes.c_void_p(h))
        except Exception: return False

    def _commit(self, batch, t):
        """一批小檔：確定寫進硬碟 → 大小、內容抽查（跟記憶體裡讀到的比，不再讀 R）→ 一起改紀錄 → 刪 R 的 → 標好."""
        if not batch: return
        if not self._vflush(t):
            for _i, _s, d, _z, _b in batch:
                try:
                    fd = os.open(L(d), os.O_RDWR | getattr(os, 'O_BINARY', 0))
                    try: os.fsync(fd)
                    finally: os.close(fd)
                except Exception: pass
        good = []
        for iid, s, d, sz, data in batch:
            try:
                n = os.path.getsize(L(d)); ok = n == len(data)
                if ok:
                    B = 1 << 20; offs = sorted({0, max(0, n // 2 - B // 2), max(0, n - B)})
                    with open(L(d), 'rb') as f:
                        for o in offs:
                            f.seek(o)
                            if f.read(B) != data[o:o + B]: ok = False; break
                if not ok:
                    try: os.remove(L(d))
                    except Exception: pass
                    self._fail(iid, s, '新硬碟上的檔跟原檔不一樣（已刪掉新的那份，原檔留著）', sz, t); continue
                good.append((iid, s, d, sz))
            except Exception as ex: self._fail(iid, s, f'確認失敗：{type(ex).__name__}: {ex}', sz, t)
        self._records_many([(s, d) for _i, s, d, _z in good])
        done = []; now = time.time()
        for iid, s, d, sz in good:
            try:
                try: os.chmod(L(s), 0o666)
                except Exception: pass
                os.remove(L(s))
            except FileNotFoundError: pass
            except Exception as ex: self._fail(iid, s, f'已經複製好也確認過，但原檔刪不掉（{ex}）', sz, t); continue
            done.append((d, iid)); self.donew.append((now, sz)); self.sess_b += sz
            self.recent.append({'n': os.path.basename(d), 'd': d, 'b': sz, 't': t, 'ok': 1, 'ts': now, 'dc': 0, 'dv': 0})
        if done:
            with self.lock:
                c = self.db(); c.executemany('UPDATE items SET st=2, dst=? WHERE id=?', done); c.commit()

    def _records_many(self, pairs):
        """一批一起改紀錄（整理那邊一次寫完，不要每個檔都等一次資料庫）."""
        if not pairs: return
        VEXT = getattr(self.E, 'VIDEO_EXT', None) or {'.mp4', '.mov', '.mkv', '.avi', '.m4v', '.wmv', '.flv', '.ts', '.mts', '.m2ts', '.webm', '.3gp', '.mpg', '.mpeg', '.vob', '.rmvb', '.rm', '.asf', '.f4v', '.dv'}
        for s, d in pairs:                                                       # SortCut 只有影片（很少）：照舊一個一個
            if os.path.splitext(s)[1].lower() in VEXT: self._records(s, d, fc=False)
        FE = self.fe()
        if FE is None: return
        try:
            roots = list(FE.fc_list('roots'))
            with FE.db.lock:
                c = FE.db.con; ids = []
                for s, d in pairs:
                    r = c.execute('SELECT id FROM files WHERE path=?', (s,)).fetchone()
                    if not r: continue
                    fid = int(r[0]); rt = next((x for x in roots if str(x)[:1].upper() == d[:1].upper()), d[:2].upper() + '\\')
                    c.execute('DELETE FROM files WHERE path=? AND id!=?', (d, fid))
                    c.execute('UPDATE files SET path=?, root=?, qpath=CASE WHEN qpath=? THEN ? ELSE qpath END WHERE id=?', (d, rt, s, d, fid))
                    ids.append((d, fid, s))
                try: c.executemany('UPDATE vc_tag SET dst=? WHERE fid=? AND dst=?', ids)
                except Exception: pass
                try: c.executemany('UPDATE moves SET dst=? WHERE fid=? AND dst=?', ids)
                except Exception: pass
                c.commit()
        except Exception:
            try: FE.db.con.rollback()
            except Exception: pass
            try: self.E.log.err('🚚 R 碟搬移：一批改整理的紀錄')
            except Exception: pass

    def _copier(self, tgt=None, big=True):
        """V0.5.97 每顆目的硬碟 4 條：1 條搬大檔（≥64 MB，一直線寫最快）、3 條搬小檔（小檔大部分時間花在開檔、建資料夾，多條一起才快）.
        ⚡ 快速確認直接在這條線做完（不用排隊等另一條）."""
        self._low(); me = threading.current_thread().name
        try:
            while not self.stop_req and not getattr(self.E, 'stop_all', False):
                with self.vcv:
                    while len(self.vq) >= 6 and not self.stop_req: self.vcv.wait(1)
                if tgt: it = self._claim(tgt, big)
                else: it = self._next((self.f_ver or {}).get('tgt') or '')
                if it is None: break
                iid, s, d, sz, t = it; t0 = time.time(); self.last_t = t
                F = {'name': os.path.basename(s), 'src': s, 'dst': d, 'tgt': t, 'size': sz, 'done': 0, 't0': t0, 'wait': self.serial, 'big': big}
                self.f_copies[me] = F; self._tl.F = F; self.f_copy = F
                self.cur.update(copy=s, copy_t=t); ok_ = False
                try:
                    with self._gate():
                        F['wait'] = False; F['t0'] = time.time()
                        h, d2 = self._copy(s, d)
                    if h is None: continue
                    self.x('UPDATE items SET st=1, dst=?, h=? WHERE id=?', (d2, h, iid)); ok_ = True
                    if self.vmode() == 'quick': self._ver(iid, s, d2, sz, t, h, time.time() - t0, inline=True)
                    else:
                        with self.vcv: self.vq.append((iid, s, d2, sz, t, h, time.time() - t0)); self.vcv.notify_all()
                except InterruptedError: break
                except FileNotFoundError: self.x("UPDATE items SET st=4, err='原檔已經不在' WHERE id=?", (iid,)); ok_ = True
                except Exception as ex: self._fail(iid, s, f'複製失敗：{type(ex).__name__}: {ex}', sz, t); ok_ = True
                finally:
                    if not ok_:
                        try: self.x('UPDATE items SET st=0 WHERE id=? AND st=5', (iid,))   # 中斷：放回去，下次重搬
                        except Exception: pass
                    self.f_copies.pop(me, None); self._tl.F = None
                    if self.f_copy is F: self.f_copy = next(iter(self.f_copies.values()), {})
        finally:
            with self.vcv:
                self.ncopy -= 1
                if self.ncopy <= 0: self.vq.append(None)
                self.vcv.notify_all()

    def _copy(self, s, d):
        """複製到 d（先寫 .vsmove 再改名），一邊算原檔指紋；目的地已經有一樣的（上次搬到一半）就直接用."""
        st = os.stat(L(s))
        if os.path.exists(L(d)):
            if os.path.getsize(L(d)) == st.st_size:
                hs = read_nocache(s, self._vcb(None))
                if hs == read_nocache(d, self._vcb(None)): return hs, d               # 上次已經複製好（還沒刪原檔就停了）
            b, e = os.path.splitext(d); i = 2
            while os.path.exists(L(f'{b} ({i}){e}')): i += 1
            d = f'{b} ({i}){e}'
        os.makedirs(L(os.path.dirname(d)), exist_ok=True); tmp = d + '.vsmove'; h = hashlib.blake2b(digest_size=32)
        import queue
        Q = queue.Queue(maxsize=4); err = []; quit_ = []

        def reader():                                                            # V0.5.93 一邊讀 R、一邊寫新硬碟（不是讀完一塊才寫一塊），指紋也在這邊算
            try:
                with open(L(s), 'rb', buffering=0) as fi:
                    while not quit_:
                        b = fi.read(CHUNK)
                        if b: h.update(b)
                        Q.put(b)
                        if not b: return
            except BaseException as ex: err.append(ex); Q.put(None)
        rt = threading.Thread(target=reader, name='RSplitRead', daemon=True); rt.start()
        try:
            with open(L(tmp), 'wb', buffering=0) as fo:
                while True:
                    if self.stop_req or getattr(self.E, 'stop_all', False): raise InterruptedError
                    t1 = time.time(); b = Q.get()
                    if b is None and err: raise err[0]
                    if not b: break
                    fo.write(b); n = len(b); self._tick(n); now_ = time.time(); self.io_r.append((now_, n))
                    try: self.io_w.setdefault(d[:1].upper(), deque(maxlen=4000)).append((now_, n))
                    except Exception: pass
                    F_ = getattr(getattr(self, '_tl', None), 'F', None) or self.f_copy
                    if F_: F_['done'] = F_.get('done', 0) + n
                    self._slow(time.time() - t1)
                fo.flush(); os.fsync(fo.fileno())                                # 確定寫進硬碟（不是還在記憶體）
            rt.join(5)
            try: shutil.copystat(L(s), L(tmp))
            except Exception: pass
            os.replace(L(tmp), L(d)); return h.hexdigest(), d
        except BaseException:
            quit_.append(1)
            try:
                while True: Q.get_nowait()
            except Exception: pass
            rt.join(5)
            try: os.remove(L(tmp))
            except Exception: pass
            raise

    def _vcb(self, F):
        """讀回比對時每讀一塊：記進度、照百分比放慢、要停就停."""
        last = [time.time()]

        def cb(n):
            now = time.time(); self.io.append((now, n))
            if F is not None: F['done'] = F.get('done', 0) + n
            self._slow(now - last[0])
            if self.stop_req and F is not None and F.get('stoppable'): raise InterruptedError
            last[0] = time.time()
        return cb

    def _tick(self, n):
        now = time.time(); self.io.append((now, n)); self._win.append((now, n)); self._win = [w for w in self._win if now - w[0] < 10]
        self.speed = sum(w[1] for w in self._win) / max(1.0, now - self._win[0][0]) if self._win else 0.0

    def _verifier(self):
        self._low()
        while True:
            with self.vcv:
                while not self.vq: self.vcv.wait(1)
                it = self.vq.pop(0); self.vcv.notify_all()
            if it is None: break
            iid, s, d, sz, t, h, dc = it; self._ver(iid, s, d, sz, t, h, dc)
        for iid, s, d, sz, h, t in self.q('SELECT id, src, dst, size, h, tgt FROM items WHERE st=1'):   # 剩下 st=1（上次複製好、還沒比對）的也比對完
            if self.stop_req: break
            self._ver(iid, s, d, sz, t, h, 0)
        self.act_base = self.act(); self.kick_t = 0.0
        try: self.set_meta('act', self.act_base)
        except Exception: pass
        self.run = False
        if not self.stop_req and self.state() == 'run':
            left = self.q('SELECT COUNT(*) FROM items WHERE st IN (0,1,5)')[0][0]
            if left == 0: self._finish()

    def _ver(self, iid, s, d, sz, t, h, dc, inline=False):
        if inline:                                                               # ⚡ 快速：在複製那條線直接確認、改紀錄、刪 R 的
            t0 = time.time()
            try:
                if self._verify_one(iid, s, d, sz, h):
                    now = time.time(); self.donew.append((now, sz)); self.sess_b += sz
                    self.recent.append({'n': os.path.basename(d), 'd': d, 'b': sz, 't': t, 'ok': 1, 'ts': now, 'dc': round(dc, 1), 'dv': round(now - t0, 1)})
            except Exception as ex: self._fail(iid, s, f'確認失敗：{type(ex).__name__}: {ex}', sz, t)
            return
        t0 = time.time(); self.f_ver = {'name': os.path.basename(d), 'src': s, 'dst': d, 'tgt': t, 'size': sz, 'done': 0, 't0': t0, 'wait': self.serial}
        self.cur.update(verify=d, verify_t=t)
        try:
            G_ = self._gate() if self.vmode() == 'full' else _NoGate()               # ⚡ 快速確認只讀幾 MB：不用排隊
            with G_:
                self.f_ver['wait'] = False; self.f_ver['t0'] = time.time()
                ok = self._verify_one(iid, s, d, sz, h)
            if ok:
                now = time.time(); self.donew.append((now, sz)); self.sess_b += sz
                self.recent.append({'n': os.path.basename(d), 'd': d, 'b': sz, 't': t, 'ok': 1, 'ts': now, 'dc': round(dc, 1), 'dv': round(now - t0, 1)})
        except Exception as ex: self._fail(iid, s, f'比對失敗：{type(ex).__name__}: {ex}', sz, t)
        finally: self.cur.update(verify='', verify_t=''); self.f_ver = {}

    def _verify_one(self, iid, s, d, sz, h):
        if not os.path.exists(L(s)):
            self.x("UPDATE items SET st=4, err='原檔已經不在' WHERE id=?", (iid,)); return False
        if os.path.getsize(L(d)) != os.path.getsize(L(s)): raise IOError('大小不一樣')
        if self.vmode() == 'quick':                                              # V0.5.94 ⚡ 快速：不整檔讀回（單向）；寫進硬碟後確認大小、抽 5 段跟原檔比
            ok = self._sample_same(s, d, sz)
        else:
            if not h: h = read_nocache(s, self._vcb(None))
            ok = read_nocache(d, self._vcb(self.f_ver)) == h                     # 🔎 完整：不經快取整檔讀回新硬碟
        if not ok:
            try: os.remove(L(d))
            except Exception: pass
            self._fail(iid, s, '新硬碟上的檔跟原檔不一樣（已刪掉新的那份，原檔留著）', sz); return False
        if os.path.getsize(L(s)) != sz: raise IOError('原檔在搬的時候被改了')
        self._records(s, d)
        try:
            try: os.chmod(L(s), 0o666)
            except Exception: pass
            os.remove(L(s))
        except Exception as ex: self._fail(iid, s, f'已經複製好也比對過，但原檔刪不掉（{ex}）', sz); return False
        self.x('UPDATE items SET st=2, dst=? WHERE id=?', (d, iid)); return True

    def vmode(self):
        return 'full' if self.E.cfg.get('rs_verify') == 'full' else 'quick'

    def _sample_same(self, s, d, sz):
        """⚡ 快速確認：頭、1/4、中間、3/4、尾各 1 MB（新硬碟那邊不經快取讀），跟原檔一樣才算."""
        B = 1 << 20; offs = sorted({0, max(0, sz // 4 - B // 2), max(0, sz // 2 - B // 2), max(0, sz * 3 // 4 - B // 2), max(0, sz - B)})
        with open(L(s), 'rb', buffering=0) as a_, open(L(d), 'rb', buffering=0) as b_:
            for o in offs:
                a_.seek(o); b_.seek(o)
                if a_.read(B) != b_.read(B): return False
        if self.f_ver: self.f_ver['done'] = sz
        return True

    def _fail(self, iid, s, why, sz=0, t=''):
        self.x('UPDATE items SET st=3, err=? WHERE id=?', (why[:300], iid))
        try: self.recent.append({'n': os.path.basename(s), 'd': s, 'b': sz, 't': t, 'ok': 0, 'ts': time.time(), 'err': why[:120]})
        except Exception: pass
        try: self.E.log.w(f'🚚 R 碟搬移：{s} 沒搬（{why}）')
        except Exception: pass

    # ---------------------------------------------------------------- 紀錄跟著過去
    def _records(self, s, d, fc=True):
        E = self.E
        try:                                                                     # SortCut：分級、初剪、預覽圖都沿用
            VEXT = getattr(E, 'VIDEO_EXT', None) or {'.mp4', '.mov', '.mkv', '.avi', '.m4v', '.wmv', '.flv', '.ts', '.mts', '.m2ts', '.webm', '.3gp', '.mpg', '.mpeg', '.vob', '.rmvb', '.rm', '.asf', '.f4v', '.dv'}
            r = E.db.one('SELECT id FROM files WHERE path=?', (s,)) if os.path.splitext(s)[1].lower() in VEXT else None   # V0.5.97 不是影片就不用查（也不再整張表比大小寫）
            if r:
                fid = int(r[0])
                dup = E.db.one('SELECT id FROM files WHERE path=? AND id!=?', (d, fid))
                if dup is not None: E.db.x('DELETE FROM files WHERE id=?', (int(dup[0]),))
                rt = E.root_of(d) or os.path.dirname(d)
                E.db.x('UPDATE files SET path=?, folder=?, name=?, root=?, missing=0 WHERE id=?', (d, os.path.dirname(d), os.path.basename(d), rt, fid))
                try: E._mv_thumb_follow(fid, d)
                except Exception: pass
        except Exception:
            try: E.log.err(f'🚚 R 碟搬移：改 SortCut 紀錄 {s}')
            except Exception: pass
        FE = self.fe() if fc else None
        if FE is not None:                                                       # FileCompare：指紋、拍攝資訊、分類都沿用（不用重算）
            try:
                r = FE.db.one('SELECT id FROM files WHERE path=?', (s,))
                if r:
                    fid = int(r[0]); rt = d[:2].upper() + '\\'
                    rt = next((x for x in FE.fc_list('roots') if str(x)[:1].upper() == d[:1].upper()), rt)
                    if FE.db.one('SELECT id FROM files WHERE path=?', (d,)): FE.db.x('DELETE FROM files WHERE path=? AND id!=?', (d, fid))
                    FE.db.x('UPDATE files SET path=?, root=? WHERE id=?', (d, rt, fid))
                    try: FE.db.x('UPDATE files SET qpath=? WHERE id=? AND qpath=?', (d, fid, s))
                    except Exception: pass
                    try: FE.db.x('UPDATE vc_tag SET dst=? WHERE fid=? AND dst=?', (d, fid, s))
                    except Exception: pass
                    try: FE.db.x('UPDATE moves SET dst=? WHERE fid=? AND dst=?', (d, fid, s))
                    except Exception: pass
            except Exception:
                try: E.log.err(f'🚚 R 碟搬移：改整理的紀錄 {s}')
                except Exception: pass

    def map_path(self, p):
        """R 上的舊路徑 → 搬到哪（給轉檔、初剪紀錄用）."""
        r = self.q('SELECT dst FROM items WHERE lower(src)=lower(?) AND st=2', (str(p),))
        return r[0][0] if r else None

    # ---------------------------------------------------------------- 收尾
    def _finish(self):
        E = self.E; P = self.meta('plan') or {}; S = P.get('src', 'R'); root = DR(S)
        try:                                                                     # 轉檔／初剪紀錄裡的舊路徑
            for r in E.db.q("SELECT id, cv_src, cv_del, cv_out FROM files WHERE upper(substr(cv_src,1,2))=? OR upper(substr(cv_del,1,2))=? OR upper(substr(cv_out,1,2))=?", (S + ':',) * 3):
                v = [(self.map_path(x) or x) if x else x for x in (r['cv_src'], r['cv_del'], r['cv_out'])]
                E.db.x('UPDATE files SET cv_src=?, cv_del=?, cv_out=? WHERE id=?', (*v, r['id']))
            for r in E.db.q("SELECT id, out FROM cuts WHERE upper(substr(out,1,2))=?", (S + ':',)):
                o = self.map_path(r['out'])
                if o: E.db.x('UPDATE cuts SET out=? WHERE id=?', (o, r['id']))
        except Exception:
            try: E.log.err('🚚 R 碟搬移：改轉檔／初剪紀錄')
            except Exception: pass
        for dp, dn, fn in os.walk(L(root), topdown=False):                       # 空資料夾清掉
            if os.path.normcase(os.path.normpath(dp)) == os.path.normcase(os.path.normpath(L(root))): continue
            try:
                if not os.listdir(dp): os.rmdir(dp)
            except Exception: pass
        failed = self.q('SELECT COUNT(*) FROM items WHERE st=3')[0][0]
        if not failed:                                                           # 都搬好了：影片庫／整理的清單把 R 拿掉（之後 R 給 TikLive，不要再掃它）
            R = [str(x) for x in E.cfg.get('roots') or [] if str(x)[:1].upper() != S]; E.cfg.set('roots', R)
            FE = self.fe()
            if FE is not None:
                for r in FE.fc_list('roots'):
                    if str(r)[:1].upper() == S:
                        try: FE.fc_list_del('roots', r)
                        except Exception: pass
        self._restore('🚚 R 碟搬移完成')
        try: E.pack_export_due(force=True, why='（R 碟搬移完成）')
        except Exception: pass
        self.set_meta('state', 'done'); self.set_meta('t1', time.time())
        v = self.view()
        msg = f"🚚 R 碟清空搬移完成：搬好 {v['done_n']:,} 個、{fmt_b(v['done_b'])}；沒搬成 {v['fail_n']:,} 個；{S}: 還剩 {v['left_n']:,} 個檔"
        try: E.log.w(msg); E.remap_msg = msg
        except Exception: pass

    def _restore(self, why):
        """背景工作恢復成搬之前的樣子."""
        E = self.E
        m = self.meta('paused') or {}
        for k, _i, _n in E.BG_KINDS:                                             # 背景工作恢復成搬之前的樣子
            if k != 'move' and k not in (m.get('vs') or []):
                try: E.bg_set_pause(k, False, why)
                except Exception: pass
        FE = self.fe()
        if FE is not None:
            for k in list(getattr(FE, 'FC_KINDS', ())):
                if k not in (m.get('fc') or []):
                    try: FE.bg_set_pause(k, False, why)
                    except Exception: pass
        self.set_meta('paused', None)

    # ---------------------------------------------------------------- 給畫面
    def left_on_src(self, S):
        n = 0; b = 0; ex = []
        for dp, dn, fn in os.walk(L(DR(S))):
            if os.path.normcase(os.path.normpath(dp)) == os.path.normcase(os.path.normpath(L(DR(S)))): dn[:] = [d for d in dn if d.lower() not in SKIP_TOP]
            for f in fn:
                n += 1
                try: b += os.path.getsize(os.path.join(dp, f))
                except Exception: pass
                if len(ex) < 8: ex.append(os.path.join(dp, f).replace('\\\\?\\', ''))
            if n > 50000: break
        return n, b, ex

    def view(self):
        P = self.meta('plan') or {}; st = self.state(); T = list(P.get('tgts') or [])
        agg = {}
        for t, s_, n, b in self.q('SELECT tgt, st, COUNT(*), TOTAL(size) FROM items GROUP BY tgt, st'):
            s_ = 0 if s_ == 5 else s_; o_ = agg.get((t, s_), (0, 0)); agg[(t, s_)] = (o_[0] + n, o_[1] + b)
        g = lambda s_, t=None: (sum(v[0] for (tt, ss), v in agg.items() if ss == s_ and (t is None or tt == t)), sum(v[1] for (tt, ss), v in agg.items() if ss == s_ and (t is None or tt == t)))
        dn, db = g(2); fn_, fb = g(3); pn, pb = g(0); cn, cb = g(1); sn, sb = g(4)
        tot_b = float(P.get('total') or 0); left_b = pb + cb
        V = {'ok': True, 'state': st, 'run': self.run, 'planning': getattr(self, 'planning', False), 'pmsg': getattr(self, 'pmsg', ''), 'plan': P, 'done_n': dn, 'done_b': db, 'fail_n': fn_, 'pend_n': pn + cn, 'pend_b': left_b, 'gone_n': sn,
             'pct': round(db * 100 / tot_b, 2) if tot_b else 0, 'speed': self.speed if self.run else 0, 'eta': (left_b / self.speed) if self.run and self.speed > 1e6 else 0,
             'cur': dict(self.cur), 'per': {t: {'done_n': g(2, t)[0], 'done_b': g(2, t)[1], 'pend_n': g(0, t)[0] + g(1, t)[0], 'pend_b': g(0, t)[1] + g(1, t)[1], 'fail_n': g(3, t)[0]} for t in T},
             'fails': [{'src': r[0], 'err': r[1]} for r in self.q('SELECT src, err FROM items WHERE st=3 ORDER BY id DESC LIMIT 100')], 't0': self.meta('t0'), 't1': self.meta('t1'),
             'drives': self._drives_c(), 'err': self.err, 'left_n': 0}
        now = time.time(); act = self.act(); man, smart, ser = self.cfg_pace()
        r10 = self._rate(self.donew, 600); avg = db / act if act > 10 else 0.0; rate = r10 or avg
        eta = left_b / rate if rate > 1e5 and st == 'run' else 0
        fp = lambda F: ({**{k: F.get(k) for k in ('name', 'dst', 'src', 'tgt', 'size', 'done', 'wait')}, 'pct': round(100.0 * F.get('done', 0) / F['size'], 1) if F.get('size') else 100.0,
                         'sec': round(now - F.get('t0', now), 1), 'bps': F.get('done', 0) / max(0.5, now - F.get('t0', now))} if F else None)
        nxt = [{'name': os.path.basename(r[0]), 'b': r[1], 't': r[2]} for r in self.q('SELECT src, size, tgt FROM items WHERE st=0 ORDER BY id LIMIT 6')] if st in ('run', 'pause') else []
        V.update({'act': act, 'avg': avg, 'rate': rate, 'eta': eta, 'fin_at': now + eta if eta else 0, 'io': self._rate(self.io, 15) if self.run else 0, 'sess_b': self.sess_b,
                  'f_copy': fp(self.f_copy), 'f_copies': [fp(F_) for F_ in list(getattr(self, 'f_copies', {}).values())], 'f_ver': fp(self.f_ver), 'recent': list(self.recent)[-60:][::-1], 'next': nxt,
                  'pace': {'verify': self.vmode(), 'pct': self.pct if self.run else (100 if smart else man), 'why': self.pct_why, 'man': man, 'smart': smart, 'serial': self.serial, 'ser': ser,
                           'busy': getattr(self, 'busy', {}), 'temp': getattr(self, 'temp', None), 'log': [f'{time.strftime("%H:%M", time.localtime(t))} {w}' for t, w in list(self.plog)[-8:][::-1]]}})
        V['drv'] = self._drv_stats(P); V['draining'] = bool(self.run and st != 'run')
        if st in ('pause', 'planned') and not self.run:
            try: V['vols'] = self.vol_check()
            except Exception: V['vols'] = []
        for D_ in V['drv']: D_['h'] = [list(x[1:]) for x in self.hist.get(D_['X'], ())]
        if st == 'done':
            c = getattr(self, '_left_c', None)
            if not c or time.time() - c[0] > 60:
                try: c = self._left_c = (time.time(), self.left_on_src(P.get('src', 'R')))
                except Exception: c = (time.time(), (0, 0, []))
            V['left_n'], V['left_b'], V['left_ex'] = c[1]
        return V


class _NoGate:
    def __enter__(self): return self
    def __exit__(self, *a): return False


def get(E=None):
    R = _reg(); o = R.get('obj')
    if o is None and E is not None: o = R['obj'] = RSplit(E)
    return o


def boot(E):
    """開程式／熱更新：舊的那個先停（做完手上的檔），再用新的接著搬."""
    R = _reg(); old = R.get('obj')

    def go():
        if old is not None:
            old.stop_req = True; t0 = time.time()
            while old.run and time.time() - t0 < 300: time.sleep(1)
        o = R['obj'] = RSplit(E)
        try:
            if o.state() == 'run': o.E.log.w('🚚 R 碟清空搬移：接著搬（剛開程式／更新）'); o._remember_vols(); o._prepare(o.meta('plan')); o.kick()
            elif o.state() == 'pause': o.E.log.w('🚚 R 碟清空搬移：暫停中（不會自己開始；硬碟對好後按「▶ 繼續」）')
        except Exception: pass
    threading.Thread(target=go, name='RSplitBoot', daemon=True).start()

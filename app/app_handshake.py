"""🤝 程式握手（apphs/1）：同一台電腦上的幾個程式互相說「我現在要做什麼、用了多少」，誰需要就讓誰先跑。

這個檔是共用的：SortCut 和 FusionStitch 用的是同一份，**整個檔直接複製過去就能用**（只用 Python 標準函式庫、沒有 Qt）。
完整規則看 app\\HANDSHAKE_握手協定.md。

用法：
    import app_handshake as HS
    hs = HS.Handshake('FusionStitch', 'FusionStitch', '1.2.03', port=8361, state=my_state)   # my_state() 回傳下面 STATE 的格式
    hs.start()
    d = hs.decide()        # {'mode': 'alone'|'lead'|'yield'|'split', 'peer', 'why', 'cpu_cap', 'nvenc_cap', 'no_new_heavy'}
    ...照 d 限制自己的重工作（FFmpeg 同時幾個、CPU 上限、NVENC 條數、新的重工作開不開）
    hs.stop()              # 關程式時（會刪掉自己的檔，對方就知道你不在了）

怎麼交換：每個程式每 2 秒把自己的狀態寫到 %LOCALAPPDATA%\\AppHandshake\\<app>.json（先寫暫存檔再改名，不會讀到一半），
並讀別人的檔。超過 10 秒沒更新、或 pid 已經不在 → 當作不在。不用網路、不用開埠、熱更新也不會斷。
"""
import json
import os
import tempfile
import threading
import time
from pathlib import Path

PROTO = 'apphs/1'
EVERY = 2.0            # 幾秒寫一次
STALE = 10.0           # 幾秒沒更新算不在
LOSE_CPU = 20.0        # 讓路的那邊：重工作最多用整台 CPU 的 %
SPLIT_CPU = 45.0       # 平分：各自最多用整台 CPU 的 %
WANT_TXT = {0: '閒著', 1: '背景小工作', 2: '在做重工作', 3: '使用者在等'}


def folder():
    base = os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()
    p = Path(base) / 'AppHandshake'
    try: p.mkdir(parents=True, exist_ok=True)
    except Exception: pass
    return p


def pid_alive(pid):
    try: pid = int(pid)
    except (TypeError, ValueError): return False
    if pid <= 0: return False
    if os.name == 'nt':
        try:
            import ctypes
            from ctypes import wintypes as W
            k = ctypes.WinDLL('kernel32', use_last_error=True)
            k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]; k.OpenProcess.restype = W.HANDLE
            k.GetExitCodeProcess.argtypes = [W.HANDLE, ctypes.POINTER(W.DWORD)]; k.CloseHandle.argtypes = [W.HANDLE]
            h = k.OpenProcess(0x1000, False, pid)                                 # PROCESS_QUERY_LIMITED_INFORMATION
            if not h: return False
            try:
                c = W.DWORD(); ok = k.GetExitCodeProcess(h, ctypes.byref(c)); return bool(ok) and c.value == 259   # STILL_ACTIVE
            finally: k.CloseHandle(h)
        except Exception: return True
    try: os.kill(pid, 0); return True
    except OSError: return False


def lead_of(a, b):
    """兩邊算出來一定一樣：want 大的先；一樣看 prio（使用者設的，大的先）；再一樣 → 平分（回 None）.
    want 0（閒著）的那邊不用讓、也不用搶."""
    wa, wb = int(a.get('want') or 0), int(b.get('want') or 0)
    if wa != wb: return a if wa > wb else b
    pa, pb = int(a.get('prio') if a.get('prio') is not None else 5), int(b.get('prio') if b.get('prio') is not None else 5)
    if pa != pb: return a if pa > pb else b
    return None


class Handshake:
    def __init__(self, app, name='', ver='', port=0, state=None):
        self.app = str(app); self.name = name or self.app; self.ver = str(ver); self.port = int(port or 0)
        self.state = state or (lambda: {}); self.stop_ = False; self.me = {}; self.others = {}; self.err = ''; self.t = 0.0
        self.path = folder() / f'{self.app}.json'; self.th = None

    # ---------------------------------------------------------------- 寫自己、讀別人
    def _me(self):
        try: S = dict(self.state() or {})
        except Exception as ex: S = {}; self.err = f'state：{ex}'[:160]
        return {'proto': PROTO, 'app': self.app, 'name': self.name, 'ver': self.ver, 'pid': os.getpid(), 'port': self.port,
                'host': os.environ.get('COMPUTERNAME', ''), 't': time.time(), 'on': S.get('on', True) is not False,
                'want': max(0, min(3, int(S.get('want') or 0))), 'prio': max(0, min(10, int(S.get('prio') if S.get('prio') is not None else 5))),
                'what': str(S.get('what') or '')[:120], 'use': dict(S.get('use') or {}), 'max': dict(S.get('max') or {}),
                'mode': (self.decide().get('mode') if self.me else 'alone')}

    def write(self):
        self.me = self._me(); tmp = self.path.with_suffix('.tmp')
        try:
            tmp.write_text(json.dumps(self.me, ensure_ascii=False), encoding='utf-8'); os.replace(tmp, self.path); self.err = ''
        except Exception as ex: self.err = f'寫不進去：{ex}'[:160]

    def read(self):
        O = {}; now = time.time()
        try:
            for p in folder().glob('*.json'):
                if p.stem.lower() == self.app.lower(): continue
                try: d = json.loads(p.read_text(encoding='utf-8'))
                except Exception: continue
                if not str(d.get('proto', '')).startswith('apphs/'): continue
                if now - float(d.get('t') or 0) > STALE or not pid_alive(d.get('pid')): continue
                O[str(d.get('app') or p.stem)] = d
        except Exception as ex: self.err = f'讀不到：{ex}'[:160]
        self.others = O; self.t = now
        return O

    def peers(self):
        now = time.time()
        return [d for d in self.others.values() if now - float(d.get('t') or 0) <= STALE and d.get('on', True) is not False]

    # ---------------------------------------------------------------- 誰先
    def decide(self):
        """回自己現在要怎麼做。兩邊各自算，結果一定對得起來（規則一樣、資料一樣）."""
        me = self.me or {}; P = self.peers()
        if not me.get('on', True) or not P:
            return {'mode': 'alone', 'peer': '', 'why': '沒有別的程式要讓' if me.get('on', True) else '握手關著', 'cpu_cap': None, 'nvenc_cap': None, 'no_new_heavy': False, 'peers': [self._brief(p) for p in P]}
        worst = None
        for p in P:                                                              # 有好幾個的話：照最嚴的那個
            L = lead_of(me, p); w = int(p.get('want') or 0); mine = int(me.get('want') or 0)
            if L is None: r = ('split', 1) if min(w, mine) >= 2 else ('alone', 0)       # 兩邊都在做重工作、優先一樣 → 平分；不然各做各的
            elif L is p: r = ('yield', 2) if w >= 2 else ('alone', 0)                  # 對方只在做背景小工作：不用讓
            else: r = ('lead', 0) if w >= 1 else ('alone', 0)
            if worst is None or r[1] > worst[0][1]: worst = (r, p)
        (mode, _sev), p = worst; nm = p.get('name') or p.get('app'); w = int(p.get('want') or 0)
        mx_nv = int((p.get('max') or {}).get('nvenc') or (me.get('max') or {}).get('nvenc') or 8)
        p_nv = int((p.get('use') or {}).get('nvenc') or 0)
        out = {'mode': mode, 'peer': nm, 'peer_want': w, 'peer_what': p.get('what', ''), 'cpu_cap': None, 'nvenc_cap': None, 'no_new_heavy': False, 'peers': [self._brief(x) for x in P]}
        if mode == 'yield':
            out.update(cpu_cap=LOSE_CPU, nvenc_cap=max(0, min(2, mx_nv - p_nv)), no_new_heavy=w >= 2,
                       why=f'讓 {nm} 先跑（它{WANT_TXT.get(w, "")}' + (f'：{p.get("what")}' if p.get('what') else '') + '）')
        elif mode == 'split':
            out.update(cpu_cap=SPLIT_CPU, nvenc_cap=max(1, mx_nv // 2), why=f'跟 {nm} 平分（兩邊都{WANT_TXT.get(w, "")}、優先一樣）')
        elif mode == 'lead':
            out.update(why=f'這邊先跑，{nm} 讓路（它{WANT_TXT.get(w, "")}）')
        else: out.update(why=f'{nm} 閒著，照常跑')
        return out

    @staticmethod
    def _brief(p):
        return {'app': p.get('app'), 'name': p.get('name'), 'ver': p.get('ver'), 'want': p.get('want'), 'prio': p.get('prio'), 'what': p.get('what'),
                'use': p.get('use'), 'age': round(time.time() - float(p.get('t') or 0), 1), 'mode': p.get('mode')}

    # ---------------------------------------------------------------- 背景
    def _loop(self):
        while not self.stop_:
            try: self.read(); self.write()
            except Exception as ex: self.err = str(ex)[:160]
            time.sleep(EVERY)

    def start(self):
        if self.th is not None and self.th.is_alive(): return self
        self.stop_ = False; self.th = threading.Thread(target=self._loop, name='AppHandshake', daemon=True); self.th.start()
        return self

    def stop(self, remove=True):
        self.stop_ = True
        if remove:
            try: self.path.unlink()
            except Exception: pass

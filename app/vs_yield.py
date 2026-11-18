"""🤝 讓路給 TikLive：右上角 Lv 1～10（V0.5.71）.

TikLive 和這套是兩個不相關的程式，但同一台電腦上 CPU／RAM／顯示卡／硬碟一律 TikLive 優先：
- 這邊不會被「停掉」，而是降到最低（Lv 1＝背景同時只做 1 個、FFmpeg 每秒只跑 2 成時間）。
- 看的是「真的還剩多少」，不是「TikLive 有沒有開」：TikLive 開著但不忙 → 照樣高速；TikLive 吃很兇 → 才降。
- Lv 10 也不會把通道吃滿：每一項都留一段給 TikLive 臨時要用（顯示卡留 2 成、NVENC 留 2 條…），
  而且 TikLive 最近 10 分鐘用過的高峰，有一半先空著不碰。TikLive 一說「我要開始錄／轉了」（tiklive.json 的 burst），
  這邊 2 秒內就先退到 Lv 2～3，等量到真實數字再慢慢加回去（降：馬上；升：每 8 秒最多 +1，剛降過 20 秒內不升）。

兩邊怎麼講話（不用網路、不用裝東西）：C:\\ProgramData\\ResLink\\
- tiklive.json：TikLive 每 2 秒寫（pid、版本、在錄幾間、轉檔／字幕在不在跑、用哪幾顆硬碟、burst 到幾點）
- sortcut.json：這邊每 2 秒寫（等級、為什麼、這邊用了多少）→ TikLive 左下角顯示「SC Lv3」
TikLive 還沒更新（沒有 tiklive.json）也照樣有用：用程式名稱找 TikLive，量它整串程式（含 FFmpeg、whisper）用的 CPU／顯示卡。

量法（Windows 內建，不用 psutil）：每個程式的 CPU＝GetProcessTimes；每個程式的顯示卡＝PDH「GPU Engine」（跟工作管理員一樣，
分 3D／Compute／VideoEncode／VideoDecode）；硬碟忙碌＝PDH LogicalDisk；NVENC 條數＝nvidia-smi。
沒有 Qt。演算法（Gov）是純函式，Linux 也能測。
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

IS_WIN = os.name == 'nt'
VER = 1
LINK_DIR = Path(os.environ.get('ProgramData') or r'C:\ProgramData') / 'ResLink'
TK_FILE = 'tiklive.json'
SC_FILE = 'sortcut.json'
TK_NAMES = ('tiklivemonitor.exe', 'tiklive.exe', 'tiklivemonitor_gui.exe')
MEDIA_NAMES = ('ffmpeg.exe', 'ffprobe.exe', 'ffmpeg', 'ffprobe')
DUTY = {10: 1.0, 9: 1.0, 8: 1.0, 7: 1.0, 6: 0.9, 5: 0.8, 4: 0.65, 3: 0.5, 2: 0.35, 1: 0.2}     # FFmpeg 每秒能跑幾成時間
COL = {1: '#e5484d', 2: '#e5484d', 3: '#f76b15', 4: '#f76b15', 5: '#f5a524', 6: '#f5a524', 7: '#8bc34a', 8: '#45d483', 9: '#2ecc71', 10: '#2ecc71'}

# ---------------------------------------------------------------- 等級演算法（純函式，可以測）
# cap：整台電腦「全部加起來」最多到幾 %（剩下的永遠留給 TikLive 臨時用）；full：這邊 Lv 10 時大概會用多少（一邊跑一邊學）
CAPS = {'cpu': 85.0, 'gpu': 80.0, 'enc': 75.0, 'dec': 80.0, 'vram': 85.0}
FULL0 = {'cpu': 55.0, 'gpu': 55.0, 'enc': 65.0, 'dec': 45.0, 'vram': 25.0}
NAMES = {'cpu': 'CPU', 'gpu': '顯示卡', 'enc': '顯示卡編碼（NVENC）', 'dec': '顯示卡解碼', 'vram': '顯示卡記憶體', 'ram': 'RAM', 'disk': '硬碟', 'nvenc': 'NVENC 條數'}


class Gov:
    """每 2 秒給一份量測 → 算出 Lv 1～10 和原因。降：馬上；升：慢慢來."""
    RISE_EVERY = 8.0; RISE_COOL = 20.0; PEAK_WIN = 600.0

    def __init__(self, max_level=10, nvenc_limit=8):
        self.level = 5; self.target = 5; self.why = '剛開始，先用中間的速度'; self.t_drop = 0.0; self.t_rise = 0.0; self.t_hi = 0.0
        self.full = dict(FULL0); self.tk_hist = deque(maxlen=400); self.max_level = int(max_level); self.nvenc_limit = int(nvenc_limit)
        self.detail = {}; self.hist = deque(maxlen=180); self.log = deque(maxlen=60); self.burst = False

    def _learn(self, s):
        """這邊實際用了多少 ÷ 目前等級 → 推 Lv 10 會用多少（慢慢平均，只在真的有在做事時學）."""
        f = max(0.1, self.level / 10.0)
        for k in self.full:
            v = s.get(k + '_vs')
            if v is None or v < 3: continue
            est = min(100.0, v / f); self.full[k] = 0.8 * self.full[k] + 0.2 * max(FULL0[k] * 0.5, est)      # 不會學到太小（突然有大工作也不會一下吃滿）

    def _tk_reserve(self, s, now):
        """TikLive 最近 10 分鐘用過的高峰 − 現在用的 → 先空一半給它（它隨時會再回到高峰）."""
        self.tk_hist.append((now, {k: float(s.get(k + '_tk') or 0) for k in CAPS}))
        while self.tk_hist and now - self.tk_hist[0][0] > self.PEAK_WIN: self.tk_hist.popleft()
        R = {}
        for k in CAPS:
            pk = max([h[k] for _t, h in self.tk_hist] + [0.0]); cur = float(s.get(k + '_tk') or 0)
            R[k] = max(0.0, min(25.0, 0.5 * (pk - cur)))
        return R

    def step(self, s, now=None):
        now = time.time() if now is None else now
        tk = s.get('tk') or {}; tk_on = bool(s.get('tk_seen') or tk)
        self._learn(s); R = self._tk_reserve(s, now); L = {}; why = {}
        for k, cap in CAPS.items():
            if not tk_on: cap = min(95.0, cap + 10.0)                                       # 這台沒有 TikLive：只要不把電腦吃滿就好
            sysv = s.get(k)
            if sysv is None: continue
            vs = float(s.get(k + '_vs') or 0); others = max(0.0, float(sysv) - vs)          # 不是這邊用的（TikLive＋其他程式）
            room = cap - R.get(k, 0.0) - others                                              # 這邊最多還能用多少
            lv = int(math.floor(10.0 * room / max(5.0, self.full[k]))) if room > 0 else 1
            L[k] = max(1, min(10, lv))
            if L[k] < 10:
                tkv = float(s.get(k + '_tk') or 0)
                why[k] = f'{NAMES[k]} 現在 {float(sysv):.0f}%（' + (f'TikLive {tkv:.0f}%、' if tk_on else '') + f'這邊 {vs:.0f}%）' + (f'，再留 {R[k]:.0f}% 給 TikLive 的高峰' if R.get(k, 0) >= 3 else '')
        ram = s.get('ram')
        if ram is not None:
            L['ram'] = max(1, min(10, int(10 - (float(ram) - 75.0) / 1.5))) if ram > 75 else 10
            if L['ram'] < 10: why['ram'] = f'RAM 用到 {float(ram):.0f}%'
        D = s.get('disk') or {}; shared = set(s.get('vs_drives') or ()) & set(s.get('tk_drives') or ())
        dl = 10
        for d in shared:                                                                  # 這邊和 TikLive 用同一顆硬碟：TikLive 要錄影，硬碟留給它
            b = D.get(d)
            if b is None: continue
            x = 10 if b < 45 else max(1, int(10 - (b - 45) / 4.5))
            if x < dl: dl = x; why['disk'] = f'{d} 碟 TikLive 也在用（忙 {b:.0f}%）'
        L['disk'] = dl
        ns = s.get('nvenc_used')
        if ns is not None:
            free = self.nvenc_limit - int(ns)                                                  # 總條數（已經含這邊的）
            L['nvenc'] = 10 if free >= 4 else (6 if free >= 3 else (3 if free >= 2 else 1))
            if L['nvenc'] < 10: why['nvenc'] = f'NVENC 只剩 {max(0, free)} 條（上限 {self.nvenc_limit}，留 2 條給 TikLive）'
        tgt = min(L.values()) if L else 10; tgt = min(tgt, self.max_level); bound = min(L, key=L.get) if L else ''
        bt = float(tk.get('burst_until') or 0)
        self.burst = bt > now
        if self.burst and tgt > 3:
            tgt = 3; bound = 'burst'; why['burst'] = f'TikLive 說要開始「{tk.get("burst_why") or "做事"}」：先退開，量到真的數字再加回來'
        if tk.get('watch') and float(tk.get('watch') or 0) > now - 120 and tgt > 7:
            tgt = 7; bound = 'watch'; why['watch'] = '有人在看 TikLive（手機／回放）：留多一點給它，畫面才順'
        if tk_on and s.get('cpu') is None and s.get('gpu') is None: tgt = min(tgt, 3); bound = 'blind'; why['blind'] = '量不到電腦用量，TikLive 開著：保守用 Lv 3'
        self.target = tgt; old = self.level
        if tgt < self.level:
            self.level = tgt; self.t_drop = now; self.t_hi = 0.0                            # 降：馬上
        elif tgt > self.level:
            self.t_hi = self.t_hi or now
            if now - self.t_drop >= self.RISE_COOL and now - self.t_hi >= self.RISE_EVERY and now - self.t_rise >= self.RISE_EVERY:
                self.level += 1; self.t_rise = now                                         # 升：每 8 秒最多 +1
        else: self.t_hi = 0.0
        if self.level >= 10: self.why = '電腦還很空：全速（每一項仍留一段給 TikLive，不會吃滿）'
        elif bound in why: self.why = why[bound]
        elif self.level >= self.max_level and self.max_level < 10: self.why = f'你設定最高 Lv {self.max_level}'
        elif self.level < tgt: self.why = f'慢慢加速中（目標 Lv {tgt}）'
        else: self.why = '照目前的空間'
        if self.level != old: self.log.append((now, old, self.level, self.why))
        self.detail = {'L': L, 'why': why, 'R': {k: round(v, 1) for k, v in R.items()}, 'full': {k: round(v, 1) for k, v in self.full.items()}, 'bound': bound}
        self.hist.append((now, self.level))
        return self.level


# ---------------------------------------------------------------- Windows 量測（ctypes，不用另外裝）
class _Win:
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.c = ctypes; self.w = wintypes; self.k = ctypes.windll.kernel32; self.ncpu = os.cpu_count() or 1
        self.prev = {}; self.pdh = None; self.q = None; self.cg = None; self.cd = None; self.cm = None
        try: self.ntdll = ctypes.windll.ntdll
        except Exception: self.ntdll = None
        try: self.gdi = ctypes.windll.gdi32
        except Exception: self.gdi = None
        self._pdh_init()

    def _pdh_init(self):
        c = self.c
        try:
            pdh = c.WinDLL('pdh.dll'); q = c.c_void_p()
            if pdh.PdhOpenQueryW(None, None, c.byref(q)) != 0: return
            g = c.c_void_p(); d = c.c_void_p(); m = c.c_void_p()
            pdh.PdhAddEnglishCounterW(q, '\\GPU Engine(*)\\Utilization Percentage', None, c.byref(g))
            pdh.PdhAddEnglishCounterW(q, '\\LogicalDisk(*)\\% Idle Time', None, c.byref(d))
            pdh.PdhAddEnglishCounterW(q, '\\GPU Process Memory(*)\\Dedicated Usage', None, c.byref(m))
            rb = c.c_void_p(); wb = c.c_void_p()                                         # V0.5.96 每顆硬碟讀／寫幾 MB/s（R 碟搬移畫面用）
            try:
                pdh.PdhAddEnglishCounterW(q, '\\LogicalDisk(*)\\Disk Read Bytes/sec', None, c.byref(rb))
                pdh.PdhAddEnglishCounterW(q, '\\LogicalDisk(*)\\Disk Write Bytes/sec', None, c.byref(wb))
            except Exception: rb = wb = None
            pdh.PdhCollectQueryData(q)
            self.pdh, self.q, self.cg, self.cd, self.cm = pdh, q, g, d, m; self.crb, self.cwb = rb, wb
        except Exception: self.pdh = None

    def _arr(self, counter, large=False):
        c = self.c

        class VAL(c.Structure): _fields_ = [('CStatus', c.c_ulong), ('v', c.c_longlong if large else c.c_double)]

        class ITEM(c.Structure): _fields_ = [('name', c.c_wchar_p), ('v', VAL)]
        size = c.c_ulong(0); cnt = c.c_ulong(0); FMT = (0x00000400 if large else 0x00000200) | 0x00008000
        self.pdh.PdhGetFormattedCounterArrayW(counter, FMT, c.byref(size), c.byref(cnt), None)
        if not size.value: return []
        buf = c.create_string_buffer(size.value)
        if self.pdh.PdhGetFormattedCounterArrayW(counter, FMT, c.byref(size), c.byref(cnt), buf) != 0: return []
        it = c.cast(buf, c.POINTER(ITEM))
        return [(it[i].name or '', it[i].v.v) for i in range(cnt.value) if it[i].v.CStatus in (0, 1)]

    def procs(self):
        """[(pid, ppid, exe 小寫)]."""
        c = self.c; w = self.w

        class PE(c.Structure):
            _fields_ = [('dwSize', w.DWORD), ('cntUsage', w.DWORD), ('th32ProcessID', w.DWORD), ('th32DefaultHeapID', c.c_void_p), ('th32ModuleID', w.DWORD),
                        ('cntThreads', w.DWORD), ('th32ParentProcessID', w.DWORD), ('pcPriClassBase', c.c_long), ('dwFlags', w.DWORD), ('szExeFile', c.c_wchar * 260)]
        self.k.CreateToolhelp32Snapshot.restype = c.c_void_p
        h = self.k.CreateToolhelp32Snapshot(2, 0); out = []
        if not h or h == c.c_void_p(-1).value: return out
        try:
            e = PE(); e.dwSize = c.sizeof(PE)
            ok = self.k.Process32FirstW(c.c_void_p(h), c.byref(e))
            while ok:
                out.append((int(e.th32ProcessID), int(e.th32ParentProcessID), str(e.szExeFile).lower()))
                ok = self.k.Process32NextW(c.c_void_p(h), c.byref(e))
        finally: self.k.CloseHandle(c.c_void_p(h))
        return out

    def _open(self, pid, acc=0x1000):
        self.k.OpenProcess.restype = self.c.c_void_p
        return self.k.OpenProcess(acc, False, int(pid))

    def cpu_of(self, pids, now):
        """這一串程式加起來用了整台電腦幾 % CPU."""
        c = self.c; w = self.w; tot = 0.0
        for pid in pids:
            h = self._open(pid)
            if not h: continue
            try:
                a, b, k_, u = w.FILETIME(), w.FILETIME(), w.FILETIME(), w.FILETIME()
                if not self.k.GetProcessTimes(c.c_void_p(h), c.byref(a), c.byref(b), c.byref(k_), c.byref(u)): continue
                f = lambda x: (x.dwHighDateTime << 32) | x.dwLowDateTime
                cr = f(a); t = f(k_) + f(u); p = self.prev.get(pid)
                self.prev[pid] = (now, t, cr)
                if p and p[2] == cr and now > p[0]: tot += max(0.0, (t - p[1]) / 1e7 / (now - p[0]) / self.ncpu * 100.0)
            finally: self.k.CloseHandle(c.c_void_p(h))
        return min(100.0, tot)

    def prune(self, alive):
        for pid in [p for p in self.prev if p not in alive]: self.prev.pop(pid, None)

    def gpu(self, groups):
        """groups：{'vs': set(pid), 'tk': set(pid)} → 整台和每一串的 3D/Compute/編碼/解碼 %、專用記憶體（位元組）."""
        if not self.pdh: return None
        if self.pdh.PdhCollectQueryData(self.q) != 0: return None
        per = {}                                                                        # (luid, eng, who) → %
        for name, v in self._arr(self.cg):
            m = re.search(r'pid_(\d+)_luid_(0x[0-9A-Fa-f]+_0x[0-9A-Fa-f]+).*engtype_(\w+)', name)
            if not m: continue
            pid = int(m.group(1)); luid = m.group(2).upper(); eng = m.group(3).lower()
            who = next((g for g, S in groups.items() if pid in S), 'x')
            for key in ((luid, eng, '*'), (luid, eng, who)): per[key] = per.get(key, 0.0) + float(v)
        if not per: return {'gpu': 0.0, 'enc': 0.0, 'dec': 0.0}
        tot = {}
        for (luid, eng, who), v in per.items():
            if who == '*': tot[luid] = tot.get(luid, 0.0) + v
        luid = max(tot, key=tot.get)                                                    # 最忙的那張（通常是 NVIDIA）
        KIND = {'gpu': ('3d', 'compute', 'compute_0', 'compute_1', 'cuda', 'graphics_1'), 'enc': ('videoencode',), 'dec': ('videodecode',)}
        out = {}
        for who in ['*'] + list(groups):
            for k, engs in KIND.items():
                vals = [v for (l_, e, w_), v in per.items() if l_ == luid and w_ == who and (e in engs or (k == 'gpu' and e.startswith('compute')))]
                v = min(100.0, max(vals) if vals else 0.0)
                out[k if who == '*' else f'{k}_{who}'] = v
        try:
            mem = {}
            for name, v in self._arr(self.cm, large=True):
                m = re.search(r'pid_(\d+)_luid', name)
                if not m: continue
                pid = int(m.group(1)); who = next((g for g, S in groups.items() if pid in S), 'x'); mem[who] = mem.get(who, 0) + int(v)
            out['vram_b'] = mem
        except Exception: pass
        return out

    def disk_rw(self):
        """{'R:': (讀 B/s, 寫 B/s)}."""
        rb, wb = getattr(self, 'crb', None), getattr(self, 'cwb', None)
        if not self.pdh or not rb or not wb: return {}
        R_ = {n.upper(): float(v) for n, v in self._arr(rb) if re.fullmatch(r'[A-Za-z]:', n or '')}
        W_ = {n.upper(): float(v) for n, v in self._arr(wb) if re.fullmatch(r'[A-Za-z]:', n or '')}
        return {k: (R_.get(k, 0.0), W_.get(k, 0.0)) for k in set(R_) | set(W_)}

    def disks(self):
        if not self.pdh: return {}
        return {n.upper(): max(0.0, min(100.0, 100.0 - float(v))) for n, v in self._arr(self.cd) if re.fullmatch(r'[A-Za-z]:', n or '')}

    def _cr(self, job, pct):
        c = self.c; w = self.w

        class CR(c.Structure): _fields_ = [('ControlFlags', w.DWORD), ('CpuRate', w.DWORD)]
        x = CR(); x.ControlFlags = 0; x.CpuRate = 0
        if pct is not None: x.ControlFlags = 0x1 | 0x4; x.CpuRate = int(max(1, min(100, float(pct))) * 100)   # ENABLE | HARD_CAP；CpuRate 以 1/100 % 計
        if not self.k.SetInformationJobObject(c.c_void_p(job), 15, c.byref(x), c.sizeof(x)): raise OSError(f'SetInformationJobObject 失敗 {self.k.GetLastError()}')

    def free_main(self):
        """V0.5.83 修：0.5.79～0.5.82 把「主程式自己」也放進限速的工作物件 → 一熱就連畫面、手機網頁都一起被壓到 2%（502 連不上）。
        工作物件沒辦法把程式拿出來，只能把那個舊的設成不限速。"""
        for k_ in ('job', 'mjob'):                                               # 熱更新：上一個留下的上限也先放開，等這次算好再設
            j = _reg().get(k_)
            if j:
                try: self._cr(j, None)
                except Exception: pass

    def job_cap(self, pct):
        """🌡 控溫：只把這邊開的 FFmpeg（子程式）放進工作物件、CPU 硬上限 pct%；主程式（畫面、手機網頁）永遠不限速（V0.5.83）."""
        c = self.c; R_ = _reg()
        job = R_.get('mjob')
        if job is None:
            self.k.CreateJobObjectW.restype = c.c_void_p; job = self.k.CreateJobObjectW(None, None)
            if not job: raise OSError('CreateJobObject 失敗')
            R_['mjob'] = job; R_['mjob_pids'] = set()
        self._cr(job, pct)
        return True

    def job_add(self, pids):
        """新開的 FFmpeg 放進限速的工作物件（2 秒檢查一次）."""
        R_ = _reg(); job = R_.get('mjob')
        if not job: return
        done = R_.setdefault('mjob_pids', set())
        for pid in list(pids):
            if pid in done: continue
            h = self._open(pid, 0x0100 | 0x0001 | 0x1000)                              # SET_QUOTA | TERMINATE | QUERY_LIMITED
            if h:
                try: self.k.AssignProcessToJobObject(self.c.c_void_p(h), self.c.c_void_p(job))
                except Exception: pass
                finally: self.k.CloseHandle(self.c.c_void_p(h))
            done.add(pid)
        R_['mjob_pids'] = done & set(pids)

    def suspend(self, pid, on):
        if not self.ntdll: return False
        h = self._open(pid, 0x0800)                                                     # PROCESS_SUSPEND_RESUME
        if not h: return False
        try: return (self.ntdll.NtSuspendProcess if on else self.ntdll.NtResumeProcess)(self.c.c_void_p(h)) == 0
        finally: self.k.CloseHandle(self.c.c_void_p(h))

    def lower(self, pid):
        """這邊的 FFmpeg：CPU 最低優先、硬碟讀寫最低優先、顯示卡排程最低（TikLive 要用的時候它先上）."""
        h = self._open(pid, 0x0200 | 0x1000 | 0x0400)                                   # SET_INFORMATION | QUERY_LIMITED | QUERY
        if not h: return
        c = self.c
        try:
            try: self.k.SetPriorityClass(c.c_void_p(h), 0x40)                           # IDLE_PRIORITY_CLASS
            except Exception: pass
            try:
                v = c.c_ulong(0); self.ntdll.NtSetInformationProcess(c.c_void_p(h), 33, c.byref(v), 4)   # ProcessIoPriority = Very Low
            except Exception: pass
            try:
                pass   # V0.5.78 拿掉「顯示卡排程最低」：1060 上 Kernel-Power 41 突然重開機變多，先排除跟顯示卡驅動有關的動作
            except Exception: pass
        finally: self.k.CloseHandle(c.c_void_p(h))


def _tree(P, roots):
    kids = {}
    for pid, pp, _n in P: kids.setdefault(pp, []).append(pid)
    out = set(); st = [r for r in roots if r]
    while st:
        x = st.pop()
        if x in out: continue
        out.add(x); st += kids.get(x, [])
    return out


# ---------------------------------------------------------------- 主迴圈（每 2 秒）
class Yield:
    def __init__(self, E=None, ver=''):
        self.E = E; self.ver = str(ver); self.stop = False; self.gov = Gov(); self.sample = {}; self.tk = None; self.tk_pids = set(); self.vs_pids = set()
        self.media = set(); self.lowered = set(); self.suspended = set(); self.win = None; self.err = ''; self.t = 0.0; self.nv_t = 0.0; self.nv = None
        self.on = True
        try:
            import vs_heat; self.heat = vs_heat.Heat()                           # V0.5.81 🌡 轉檔看溫度＋自己學
            if E is not None: vs_heat.Heat.table(E.db); self.heat.learn(E.db)
        except Exception: self.heat = None
        if IS_WIN:
            threading.Thread(target=self._loop, name='VsYield', daemon=True).start()
            threading.Thread(target=self._duty, name='VsYieldDuty', daemon=True).start()

    # ---- 設定
    def cfg(self, k, d=None):
        try: v = self.E.cfg.get(k) if self.E is not None else None
        except Exception: v = None
        return d if v is None else v

    @property
    def level(self):
        return int(self.gov.level) if self.on else 10

    def mult(self):
        return self.level / 10.0

    def cap(self, kind, n):
        """後台同時做幾個：Lv 10＝照設定，Lv 1＝1 個；🌡 控溫時最多 1 個（可以慢）."""
        try:
            n = int(n)
            if n > 1 and (self.thermal_on() or (self.on and self.read_alert())): return 1
            if not self.on or n <= 1: return n
            return max(1, int(math.ceil(n * self.mult())))
        except Exception: return n

    def hold(self, kind):
        """要不要先不開新的（只有 TikLive 說「要開始了」而且已經 Lv 1 時，轉檔／瘦身先不開新的；跑到一半的照跑、只是變慢）."""
        al = self.read_alert() if self.on else None
        if al and kind in ('conv', 'slim', 'enc'):                              # ⚡ 斷電警報：轉檔／瘦身不開新的（stop 和 min 都是，比較保險）
            return f"⚡ TikLive 斷電警報（24 小時內 {al.get('n24', '?')} 次）：轉檔／瘦身先不開新的，到 {time.strftime('%m-%d %H:%M', time.localtime(float(al['until'])))}"
        if not self.on: return ''
        if kind in ('conv', 'slim', 'enc') and self.gov.level <= 2 and self.tk_pids: return f'🤝 讓路給 TikLive（Lv {self.gov.level}）：轉檔／瘦身先不開新的，跑到一半的照跑完　{self.gov.why}'   # V0.5.78 不再暫停 FFmpeg，改成低等級時不開新的
        if kind in ('conv', 'slim', 'enc') and (self.gov.detail.get('L') or {}).get('nvenc', 10) <= 1: return '🤝 NVENC 條數不夠，留給 TikLive'
        H = getattr(self, 'heat', None)
        if H is not None and kind in ('conv', 'slim', 'enc'):
            w_ = H.hold(kind)
            if w_: return w_
        t_ = self.gpu_hot() if kind in ('conv', 'slim', 'enc') else 0
        if t_: return f'🌡 顯示卡 {t_:.0f}°C，超過控溫設定：轉檔／瘦身先不開新的，涼下來再繼續'
        return ''

    # ---- TikLive 那邊寫的
    def tk_cfg(self):
        """V0.6.07 這台要不要讓路給 TikLive（另一台沒跑 TikLive：取消勾選；智能調速、%、控溫照樣有）."""
        return self.cfg('yield_tk') is not False

    def read_tk(self):
        if not self.tk_cfg(): return None
        try:
            p = LINK_DIR / TK_FILE
            if not p.exists(): return None
            J = json.loads(p.read_text(encoding='utf-8'))
            return J if time.time() - float(J.get('t') or 0) < 12 else None
        except Exception: return None

    # ---- ⚡ TikLive 的斷電警報（V0.5.80，ResLink 斷電警報協定）：C:\ProgramData\ResLink\alert.json
    def read_alert(self):
        """有效的警報（until 還沒到、沒被解除）：{'id','mode': 'min'|'stop','until','n24','msg',...}；TikLive 沒開也讀得到."""
        if not self.tk_cfg(): return None                                        # V0.6.07 不讓路給 TikLive：它的斷電警報也不管
        now = time.time(); c = getattr(self, '_al_c', (0.0, None))
        if now - c[0] < 5: return c[1]
        al = None
        try:
            p = LINK_DIR / 'alert.json'
            if p.exists():
                j = json.loads(p.read_text(encoding='utf-8'))
                if isinstance(j, dict) and float(j.get('until') or 0) > now and not j.get('cleared') and j.get('kind', 'power_loss') == 'power_loss': al = j
        except Exception: al = None
        if al is None:                                                           # tiklive.json 裡也有一份
            try:
                a2 = (getattr(self, 'tk', None) or {}).get('alert')
                if isinstance(a2, dict) and float(a2.get('until') or 0) > now and not a2.get('cleared'): al = a2
            except Exception: pass
        if self.cfg('alert_follow') is False: al = None                            # 設定可以不理（不建議）
        self._al_raw = al
        if al and al.get('mode') != 'stop' and self.cfg('alert_min_follow') is not True:
            al = None                                                            # V0.5.82 照使用者：第一次斷電只記錄、繼續轉；24 小時內 2 次（stop）才停轉檔
        self._al_c = (now, al)
        A_ = getattr(self, '_al_raw', None)
        if A_ and getattr(self, '_al_seen', None) != A_.get('id') and self.E is not None:
            self._al_seen = A_.get('id'); al_ = al; al = A_
            try: self.E.log.w(f"⚡ TikLive 斷電警報：{'停止轉檔' if al.get('mode') == 'stop' else '降到最低'}，到 {time.strftime('%m-%d %H:%M', time.localtime(float(al['until'])))}（24 小時內斷電 {al.get('n24', '?')} 次）：{al.get('msg', '')}")
            except Exception: pass
            al = al_
        return al

    def _alert_conv(self, al):
        """V0.5.82 24 小時內斷電 2 次（stop）：轉檔立刻停（正在轉的放回排隊），警報結束自動繼續."""
        E = self.E
        if E is None: return
        try:
            A_ = getattr(self, '_al_raw', None)                                  # 第一次斷電：自動改用保守模式（控溫開），繼續轉
            if A_ and A_.get('mode') != 'stop' and self.cfg('alert_cons_id') != A_.get('id'):
                E.cfg.set('alert_cons_id', A_.get('id')); E.cfg.set('thermal_on', True)
                E.log.w('⚡ 第一次斷電：改用保守模式（控溫：CPU 預算、有空才轉、轉完休息、一熱就停）繼續轉；24 小時內再斷一次就停轉檔')
            done = self.cfg('alert_conv_paused')
            if al and al.get('mode') == 'stop' and done != al.get('id'):
                E.cfg.set('alert_conv_paused', al.get('id')); E.bg_stop_now('conv')
                E.log.w(f"⚡ 24 小時內斷電 {al.get('n24', '?')} 次：轉檔停了（正在轉的放回排隊），警報結束自動繼續")
            elif not al and done:
                E.cfg.set('alert_conv_paused', None); E.bg_set_pause('conv', False, '斷電警報結束')
                E.log.w('⚡ 斷電警報結束：轉檔繼續')
        except Exception: pass

    def alert_did(self, al):
        if al.get('mode') != 'stop' and self.cfg('alert_min_follow') is not True:
            return '第一次斷電：改用保守模式繼續轉（CPU 預算 45%、這邊最多 15%、有空才轉、轉完休息、一熱就停）；24 小時內第 2 次就停轉檔'
        return ('轉檔／瘦身不開新的、CPU 上限 2%、Lv 1、同時只做 1 個' if al.get('mode') == 'stop' else 'Lv 1、CPU 上限 2%、同時只做 1 個') + f"（到 {time.strftime('%m-%d %H:%M', time.localtime(float(al['until'])))}）"

    def write_sc(self):
        try:
            LINK_DIR.mkdir(parents=True, exist_ok=True); s = self.sample
            J = {'v': VER, 't': time.time(), 'app': 'SortCut', 'ver': self.ver, 'pid': os.getpid(), 'on': self.on, 'level': self.level, 'target': self.gov.target,
                 'why': self.gov.why, 'duty': (DUTY.get(self.level, 1.0) if self.cfg('yield_suspend') is True else 1.0), 'use': {k: round(float(s.get(k + '_vs') or 0), 1) for k in ('cpu', 'gpu', 'enc', 'dec')},
                 'drives': sorted(s.get('vs_drives') or ())}
            self.read_alert(); al = getattr(self, '_al_raw', None)
            if al: J['alert_ack'] = {'id': al.get('id'), 'mode': al.get('mode'), 'did': self.alert_did(al), 't': time.time()}   # ⚡ 跟 TikLive 說「收到了、照做了」
            try: J['th'] = {'on': self.thermal_on(), 'cap': (getattr(self, 'th', {}) or {}).get('set')}
            except Exception: pass
            tmp = LINK_DIR / (SC_FILE + '.tmp'); tmp.write_text(json.dumps(J, ensure_ascii=False), encoding='utf-8'); os.replace(str(tmp), str(LINK_DIR / SC_FILE))
        except Exception as ex: self.err = f'寫 sortcut.json：{ex}'

    def _vs_drives(self):
        out = set()
        try:
            for x in self.E.drive_busy():
                if x.get('busy'): out.add(x['d'] + ':')
        except Exception: pass
        try:
            F = sys.modules.get('fc_app'); FE = getattr(F, 'ENG', None) if F else None
            if FE is not None and getattr(FE, 'fc_active', None):
                for J in list(FE.fc_active.values()):
                    p = str(J.get('path') or J.get('root') or '')
                    if len(p) > 1 and p[1] == ':': out.add(p[0].upper() + ':')
        except Exception: pass
        return out

    def _nvenc(self):
        """NVENC 現在總共開了幾條（這台電腦全部程式）：6 秒問一次 nvidia-smi."""
        now = time.time()
        if now - self.nv_t < 6: return self.nv
        self.nv_t = now
        smi = shutil.which('nvidia-smi') or (r'C:\Windows\System32\nvidia-smi.exe' if Path(r'C:\Windows\System32\nvidia-smi.exe').exists() else '')
        if not smi: self.nv = None; return None
        try:
            r = subprocess.run([smi, '--query-gpu=encoder.stats.sessionCount', '--format=csv,noheader,nounits'], capture_output=True, timeout=6,
                               creationflags=0x08000000, stdin=subprocess.DEVNULL)
            self.nv = int(r.stdout.decode('utf-8', 'ignore').strip().splitlines()[0]) if r.returncode == 0 else None
        except Exception: self.nv = None
        return self.nv

    def measure(self):
        W = self.win; now = time.time(); tk = self.read_tk(); s = {'tk': tk}
        P = W.procs(); me = os.getpid()
        roots = ([int(tk['pid'])] if tk and tk.get('pid') else [pid for pid, _pp, n in P if n in TK_NAMES]) if self.tk_cfg() else []   # V0.6.07 不讓路給 TikLive：當作這台沒有它
        self.tk_pids = _tree(P, roots) - {me}; vs = _tree(P, [me]) - self.tk_pids; self.vs_pids = vs
        self.media = {pid for pid, _pp, n in P if pid in vs and pid != me and n in MEDIA_NAMES}
        s['tk_seen'] = bool(self.tk_pids)
        try:
            Pf = getattr(self.E, 'perf', None); s['cpu'] = float(Pf.cpu) if Pf is not None else None; s['ram'] = float(Pf.ram) if Pf is not None else None
            g = getattr(Pf, 'gpu', None) or {}
            if g.get('mem_t'): s['vram'] = 100.0 * float(g['mem']) / float(g['mem_t']); s['_vram_t'] = float(g['mem_t']) * 1024 * 1024
        except Exception: pass
        s['cpu_vs'] = W.cpu_of(vs, now); s['cpu_tk'] = W.cpu_of(self.tk_pids, now); W.prune(vs | self.tk_pids)
        G = W.gpu({'vs': vs, 'tk': self.tk_pids})
        if G:
            for k in ('gpu', 'enc', 'dec'):
                s[k] = G.get(k); s[k + '_vs'] = G.get(k + '_vs'); s[k + '_tk'] = G.get(k + '_tk')
            vb = G.get('vram_b') or {}
            if s.get('_vram_t'):
                s['vram_vs'] = 100.0 * vb.get('vs', 0) / s['_vram_t']; s['vram_tk'] = 100.0 * vb.get('tk', 0) / s['_vram_t']
        s['disk'] = W.disks(); s['vs_drives'] = self._vs_drives()
        try: s['disk_rw'] = W.disk_rw()
        except Exception: s['disk_rw'] = {}
        s['tk_drives'] = {str(x).upper()[:2] for x in (tk or {}).get('drives') or [] if len(str(x)) >= 2}
        s['nvenc_used'] = self._nvenc()
        s['_n_media'] = len(self.media)
        return s

    def _apply_lower(self):
        for pid in list(self.media - self.lowered):
            try: self.win.lower(pid)
            except Exception: pass
            self.lowered.add(pid)
        self.lowered &= self.media | set(self.suspended)

    def _loop(self):
        try: self.win = _Win()
        except Exception as ex: self.err = f'量不到：{ex}'; return
        try: self.win.free_main()                                                # V0.5.83 舊版把主程式也限速了：先放開
        except Exception: pass
        last_log = 0
        try:                                                                     # V0.5.82 一次性：控溫回到「沒設過」（＝關），先全力轉檔測 99% 有沒有用
            if self.E is not None and not self.cfg('v0582_reset'):
                self.E.cfg.set('thermal_on', None); self.E.cfg.set('v0582_reset', 1); self.E.log.w('🌡 控溫先關掉（最大處理器狀態 99% 測試；要再開到右上角 Lv）')
        except Exception: pass
        while not self.stop:
            try:
                self.on = self.cfg('yield_on') is not False
                self.gov.max_level = max(1, min(10, int(self.cfg('yield_max') or 10))); self.gov.nvenc_limit = max(2, int(self.cfg('nvenc_limit') or 8))
                self.sample = self.measure(); self.tk = self.sample.get('tk'); old = self.gov.level
                self.gov.step(self.sample); self.t = time.time()
                al = self.read_alert()
                if al and self.on:                                                    # ⚡ 斷電警報：直接 Lv 1
                    self.gov.level = 1; self.gov.target = 1; self.gov.t_drop = time.time(); self.gov.why = '⚡ TikLive 斷電警報：' + self.alert_did(al)
                self._alert_conv(al if self.on else None)
                if self.tk_pids: self._apply_lower()
                self._heat()
                self._thermal()
                try: self.win.job_add(self.media)                                 # 新開的 FFmpeg 放進限速組（主程式不放）
                except Exception: pass
                self.write_sc()
                if self.gov.level != old and self.E is not None and time.time() - last_log > 20:
                    last_log = time.time()
                    try: self.E.log.w(f'🤝 讓路等級 Lv {old} → Lv {self.gov.level}：{self.gov.why}')
                    except Exception: pass
            except Exception as ex: self.err = str(ex)[:200]
            time.sleep(2.0)
        self._resume_all()

    # ---- 🌡 控溫（V0.5.79）：主機板電源 IC 會過熱斷電 → 整台電腦的 CPU 壓在預算內，這邊只用剩下的（可以慢）
    def thermal_on(self):
        v = self.cfg('thermal_on')
        return bool(v) if v is not None else False                              # V0.5.82 預設關（改用 99% 關 Turbo，照使用者：先回到事發前、全力轉檔測試）

    def _thermal(self):
        s = self.sample or {}; al = self.read_alert() if self.on else None; on = self.thermal_on() or bool(al); self.th = getattr(self, 'th', {'cap': None, 'set': None, 'err': ''})
        try: mf = float(getattr(sys, '_vs_mf', {}).get('until') or 0) > time.time()
        except Exception: mf = False
        if mf:                                                                   # V0.6.08 🛟 主程式優先：這邊的 FFmpeg 先壓到 5%
            if self.th.get('set') != 5.0:
                try: self.win.job_cap(5.0); self.th.update(set=5.0, cap=5.0, err='')
                except Exception as ex: self.th['err'] = str(ex)[:120]
            return
        if not on:
            hc = getattr(self, 'heat_cap', None)                                 # V0.5.82 控溫關著：只有溫度太高時才壓（一熱就停）
            if hc is not None:
                if self.th.get('set') is None or abs(hc - self.th['set']) >= 2:
                    try: self.win.job_cap(hc); self.th.update(set=round(hc, 1), cap=round(hc, 1), err='')
                    except Exception as ex: self.th['err'] = str(ex)[:120]
            elif self.th.get('set') is not None:
                try: self.win.job_cap(None); self.th.update(set=None, cap=None)
                except Exception as ex: self.th['err'] = str(ex)[:120]
            return
        budget = float(self.cfg('thermal_cpu') or 45); mx = float(self.cfg('thermal_vs_max') or 15); mn = 2.0
        cpu = s.get('cpu'); vs = float(s.get('cpu_vs') or 0)
        others = max(0.0, float(cpu) - vs) if cpu is not None else budget
        cap = max(mn, min(mx, budget - others))                                # 整台 ≤ 預算；這邊最多 mx%、最少 2%（不會停）
        if self.gov.level <= 2: cap = min(cap, 5.0)
        if al: cap = mn                                                          # ⚡ 斷電警報：CPU 上限最低
        hc = getattr(self, 'heat_cap', None)
        if hc is not None: cap = max(mn, min(cap, hc))                           # 🌡 涓流／一熱就停
        old = self.th.get('set')
        if old is None or abs(cap - old) >= 2 or (cap <= mn + 0.1 and old > mn + 0.1):
            try: self.win.job_cap(cap); self.th.update(set=round(cap, 1), err='')
            except Exception as ex: self.th['err'] = str(ex)[:120]
        self.th.update(cap=round(cap, 1), budget=budget, others=round(others, 1), vs_max=mx)

    def _heat(self):
        """🌡 轉檔看溫度：控溫開著才管；算出 heat_cap（None＝不管），給 _thermal 用."""
        H = getattr(self, 'heat', None); self.heat_cap = None
        if H is None: return
        try:
            on = self.thermal_on() or bool(self.read_alert())
            cf = lambda k: (on if k == 'heat_full' else self.cfg(k))                 # V0.5.82 一熱就停一直開；有空才轉／轉完休息只在保守模式（控溫開）
            H.read_sensors()
            g = (getattr(getattr(self.E, 'perf', None), 'gpu', None) or {}).get('temp')
            W = H.watched(g, self.cfg); s = self.sample or {}
            n = len(getattr(self.E, 'cv_active', None) or {}); nm = [str(v.get('name') or '') for v in list((getattr(self.E, 'cv_active', None) or {}).values())]
            try:
                F = sys.modules.get('fc_app'); FE = getattr(F, 'ENG', None) if F else None; sl = getattr(FE, 'slim', None)
                if sl is not None and (sl.st or {}).get('src'): n += 1; nm.append(os.path.basename(str(sl.st.get('src'))))
            except Exception: pass
            budget = float(self.cfg('thermal_cpu') or 45); cpu = s.get('cpu')
            spare = (budget - max(0.0, float(cpu) - float(s.get('cpu_vs') or 0))) if cpu is not None else None
            self.heat_cap = H.step(time.time(), W, n, spare, cf, getattr(self.E, 'db', None), '、'.join(nm)[:200])
        except Exception as ex: self.err = f'溫度：{ex}'[:160]

    def gpu_hot(self):
        """顯示卡溫度超過設定：轉檔／瘦身先不開新的."""
        try:
            g = getattr(self.E.perf, 'gpu', None) or {}; t = float(g.get('temp') or 0); lim = float(self.cfg('thermal_gpu') or 75)
            return t if (self.thermal_on() and t >= lim) else 0
        except Exception: return 0

    def _duty(self):
        """Lv 6 以下：這邊的 FFmpeg 每秒停一下（暫停不是關掉，什麼都不會丟），讓出來的時間給 TikLive."""
        while not self.stop:
            try:
                d = DUTY.get(self.level, 1.0) if (self.on and self.cfg('yield_suspend') is True) else 1.0   # V0.5.78 預設不再暫停 FFmpeg（正在用顯示卡編碼的程式一直被暫停，可能讓驅動卡住 → 重開機）；🧪 才開
                if d >= 0.999 or not self.media or self.win is None: self._resume_all(); time.sleep(0.5); continue
                L = list(self.media)
                for pid in L:
                    if self.win.suspend(pid, True): self.suspended.add(pid)
                time.sleep(1.0 - d)
                self._resume_all(); time.sleep(d)
            except Exception: self._resume_all(); time.sleep(1.0)
        self._resume_all()

    def _resume_all(self):
        for pid in list(self.suspended):
            try: self.win.suspend(pid, False)
            except Exception: pass
            self.suspended.discard(pid)

    def close(self):
        self.stop = True
        try: self._resume_all()
        except Exception: pass                                                   # 🌡 CPU 上限留著：熱更新後新的那個接手（同一個工作物件）

    # ---- 給畫面
    def view(self):
        s = self.sample or {}; tk = self.tk or {}; G = self.gov
        f = lambda k: (None if s.get(k) is None else round(float(s[k]), 1))
        Pf_ = getattr(self.E, 'perf', None)
        cpu_src = {'src': getattr(Pf_, 'cpu_src', ''), 'old': getattr(Pf_, 'cpu_old', None)}
        return {'on': self.on, 'tk_cfg': self.tk_cfg(), 'cpu_src': cpu_src, 'level': self.level, 'target': G.target, 'why': G.why, 'col': COL.get(self.level, '#888'), 'duty': (DUTY.get(self.level, 1.0) if self.cfg('yield_suspend') is True else 1.0),
                'tk': bool(s.get('tk_seen')), 'tk_link': bool(tk), 'tk_ver': tk.get('ver'), 'tk_rec': tk.get('rec'), 'tk_conv': tk.get('conv'), 'tk_stt': tk.get('stt'),
                'burst': G.burst, 'max': G.max_level,
                'use': {k: {'all': f(k), 'tk': f(k + '_tk'), 'vs': f(k + '_vs')} for k in ('cpu', 'gpu', 'enc', 'dec', 'vram')}, 'ram': f('ram'),
                'nvenc': s.get('nvenc_used'), 'nvenc_limit': G.nvenc_limit, 'media': s.get('_n_media', 0), 'L': G.detail.get('L'), 'R': G.detail.get('R'),
                'log': [f'{time.strftime("%H:%M:%S", time.localtime(t))} Lv {a}→{b}：{w}' for t, a, b, w in list(G.log)[-12:]][::-1], 'err': self.err,
                'hist': [b for _a, b in list(G.hist)[-90:]], 'th_on': self.thermal_on(), 'th': dict(getattr(self, 'th', {}) or {}),
                'th_cpu': float(self.cfg('thermal_cpu') or 45), 'th_vs': float(self.cfg('thermal_vs_max') or 15), 'th_gpu': float(self.cfg('thermal_gpu') or 75),
                'gpu_temp': (getattr(getattr(self.E, 'perf', None), 'gpu', None) or {}).get('temp'), 'alert': self.read_alert(), 'heat': (self.heat.view() if getattr(self, 'heat', None) is not None else None)}


def _reg():
    """放在 sys 上（熱更新重新載入這個檔也找得到舊的那個）."""
    d = getattr(sys, '_vs_yield', None)
    if not isinstance(d, dict): d = {'obj': None}; setattr(sys, '_vs_yield', d)
    return d


def start(E, ver=''):
    """開一個（熱更新：舊的那個先停、把暫停中的 FFmpeg 放開，再開新的）."""
    Y = _reg(); old = Y.get('obj')
    if old is not None:
        try: old.close()
        except Exception: pass
    y = Yield(E, ver); Y['obj'] = y
    return y


def get():
    return _reg().get('obj')


def cap(kind, n):
    y = get()
    try: return y.cap(kind, n) if y is not None else n
    except Exception: return n


def hold(kind):
    try:                                                                        # V0.5.85 🚚 R 碟清空搬移中：所有新工作先不開（不讀 R、硬碟留給搬移）
        R_ = getattr(sys, '_vs_rsplit', None); o_ = (R_ or {}).get('obj')
        if o_ is not None and o_.run: return '🚚 R 碟清空搬移中：其他背景工作先停，搬完自動恢復'
    except Exception: pass
    y = get()
    try: return y.hold(kind) if y is not None else ''
    except Exception: return ''


def view():
    y = get()
    try: return y.view() if y is not None else {'on': False, 'level': 10, 'why': '還沒開始', 'col': COL[10]}
    except Exception as ex: return {'on': False, 'level': 10, 'why': f'讀不到：{ex}', 'col': COL[10]}

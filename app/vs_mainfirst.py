"""🛟 主程式優先（V0.6.08）：畫面和手機連線永遠比背景工作重要。沒有 Qt。

1. 優先序（Windows，預設開，cfg 'main_first'）：
   - 整個程式 ABOVE_NORMAL（贏過 360 轉檔這類一般程式）。開出去的 FFmpeg 照舊低優先（不會跟著變高）。
   - 畫面執行緒、手機網頁的執行緒：再高一級；其他背景執行緒（掃描、預覽圖、指紋、讀資料…）：最低一級（≈一般程式），
     所以 CPU 100% 的時候，搶得到 CPU 的是畫面和手機，不是背景補資料。
   - 不會「暫停」Python 背景執行緒（暫停拿著鎖的執行緒會整個卡死），只是排在後面。
2. 卡了就退（cfg 'mf_lag_ms'，預設 400 毫秒）：
   - 畫面心跳（每 100 毫秒）慢了超過門檻，或手機的請求卡超過 2.5 秒 → 馬上「🛟 主程式優先」：
     SortCut 和整理的背景工作全部不開新的、同時只做 1 個、這邊的 FFmpeg CPU 壓到 5%。
   - 順了 20 秒以後才照順序慢慢放回來（每項間隔 10 秒）；又卡就再延長。
"""
import os
import sys
import threading
import time

IS_WIN = os.name == 'nt'
HOLD_SEC = 20.0                         # 順了多久才放回來
WEB_LIMIT = 2.5                         # 手機的請求卡多久算卡
WEB_SKIP = ('upload', 'export', 'zip', 'log', 'pkg', 'backup', 'download', 'video', 'media', 'stream', 'file')   # 本來就會比較久的（上傳、匯出、看影片…）不算


def _reg():
    d = getattr(sys, '_vs_mf', None)
    if not isinstance(d, dict):
        d = {'beat': time.time(), 'until': 0.0, 'since': 0.0, 'why': '', 'n': 0, 'last': 0.0, 'web': {}, 'log': [], 'max_lag': 0.0, 'prio': {}, 'th': None, 'engs': []}
        setattr(sys, '_vs_mf', d)
    return d


def active():
    """現在是不是「主程式優先」（背景先退開）."""
    try: return float(getattr(sys, '_vs_mf', {}).get('until') or 0) > time.time()
    except Exception: return False


def beat():
    """畫面執行緒每 100 毫秒叫一次（QTimer）."""
    R = _reg(); R['beat'] = time.time(); R['ui'] = True


def web_begin(path):
    R = _reg(); k = threading.get_ident(); R['web'][k] = (time.time(), str(path or ''))
    return k


def web_end(k):
    R = _reg(); v = R['web'].pop(k, None)
    if v and _web_counts(v[1]):
        dt = time.time() - v[0]
        if dt >= WEB_LIMIT: trip(f'手機的請求等了 {dt:.1f} 秒（{v[1][:40]}）')


def _web_counts(path):
    p = str(path or '').lower()
    return p.startswith('/api/') and not any(x in p for x in WEB_SKIP)


def _cfg(k, d=None):
    for E in list(_reg().get('engs') or []):
        try:
            v = E.cfg.get(k)
            if v is not None: return v
        except Exception: pass
    return d


def enabled(): return _cfg('main_first', True) is not False


def trip(why):
    """畫面／手機卡了：背景馬上退開（已經在退就延長）."""
    if not enabled(): return
    R = _reg(); now = time.time(); new = R['until'] <= now
    R['until'] = now + HOLD_SEC; R['why'] = why; R['last'] = now
    if new:
        R['since'] = now; R['n'] += 1
        R['log'] = (R['log'] + [(now, why)])[-30:]
        for E in list(R.get('engs') or []):
            try: E.log.w(f'🛟 主程式優先：{why} → 背景工作先不開新的、FFmpeg 壓到 5%（順了 {HOLD_SEC:.0f} 秒再慢慢放回來）')
            except Exception: pass


def _release():
    """順了：照先後順序慢慢放回來."""
    now = time.time(); L = list(_reg().get('engs') or [])
    F = getattr(sys.modules.get('fc_app'), 'ENG', None)                         # 整理（FileCompare）也一起慢慢放回來
    if F is not None and F not in L: L.append(F)
    for E in L:
        try:
            ks = E.bg_prio() if hasattr(E, 'bg_prio') else [k for k, _i, _n in E.BG_KINDS]
            for i, k in enumerate(ks): E.bg_ramp[k] = now + i * 10
            E.log.w('🛟 主程式順了：背景工作照順序慢慢放回來')
        except Exception: pass


def attach(E):
    """引擎開好時叫（SortCut 和整理都要）：之後看門狗才找得到它們."""
    R = _reg(); L = [x for x in R['engs'] if x is not E and getattr(x, 'alive', lambda: True)()]
    L.append(E); R['engs'] = L[-4:]
    _start()


# ---------------------------------------------------------------- 優先序（Windows）
_K = None


def _k32():
    """自己的一份 kernel32（設好 64 位元的參數型別，不影響別的檔案用 windll.kernel32）."""
    global _K
    if _K is None:
        import ctypes
        from ctypes import wintypes as W
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.GetCurrentProcess.restype = W.HANDLE
        k.SetPriorityClass.argtypes = [W.HANDLE, W.DWORD]; k.SetPriorityClass.restype = W.BOOL
        k.OpenThread.argtypes = [W.DWORD, W.BOOL, W.DWORD]; k.OpenThread.restype = W.HANDLE
        k.SetThreadPriority.argtypes = [W.HANDLE, ctypes.c_int]; k.SetThreadPriority.restype = W.BOOL
        k.CloseHandle.argtypes = [W.HANDLE]; k.CloseHandle.restype = W.BOOL
        _K = k
    return _K


def _set_proc_prio(on):
    if not IS_WIN: return
    try:
        k = _k32(); k.SetPriorityClass(k.GetCurrentProcess(), 0x00008000 if on else 0x00000020)   # ABOVE_NORMAL／NORMAL
    except Exception: pass


def _set_thread_prio(native_id, pri):
    if not IS_WIN: return True
    try:
        k = _k32()
        h = k.OpenThread(0x0020 | 0x0040, False, int(native_id))              # THREAD_SET_INFORMATION | THREAD_QUERY_INFORMATION
        if not h: return False
        try: return bool(k.SetThreadPriority(h, int(pri)))
        finally: k.CloseHandle(h)
    except Exception: return False


def kind_of(t):
    """這條執行緒是「互動」（畫面、手機）還是背景."""
    if t is threading.main_thread(): return 'ui'
    n = t.name or ''
    if 'Web' in n or n.startswith(('VsUiWatchdog', 'MainFirst')): return 'ui'
    return 'bg'


def _apply_prio():
    R = _reg(); on = enabled(); P = R['prio']; alive = set()
    for t in threading.enumerate():
        nid = getattr(t, 'native_id', None)
        if not nid: continue
        alive.add(nid); want = (1 if kind_of(t) == 'ui' else -2) if on else 0   # ABOVE_NORMAL／LOWEST／NORMAL
        if P.get(nid) != want and _set_thread_prio(nid, want): P[nid] = want
    for nid in list(P):
        if nid not in alive: P.pop(nid, None)
    if R.get('proc_on') != on: _set_proc_prio(on); R['proc_on'] = on


# ---------------------------------------------------------------- 看門狗
def _loop():
    R = _reg(); t_prio = 0.0; was = False
    while True:
        try:
            time.sleep(0.1); now = time.time()
            lag = now - float(R.get('beat') or now); lim = max(0.15, float(_cfg('mf_lag_ms', 400) or 400) / 1000.0)
            R['max_lag'] = max(lag, R['max_lag'] * 0.98)
            if R.get('ui') and lim <= lag < 600: trip(f'畫面慢了 {lag * 1000:.0f} 毫秒')
            for k, (t0, p) in list(R['web'].items()):
                if now - t0 >= WEB_LIMIT and _web_counts(p): trip(f'手機的請求等了 {now - t0:.1f} 秒（{p[:40]}）')
            act = R['until'] > now
            if was and not act: _release()
            was = act
            if now - t_prio >= 3.0: t_prio = now; _apply_prio()
        except Exception: time.sleep(1)


def _start():
    R = _reg(); th = R.get('th')
    if th is not None and th.is_alive(): return
    th = threading.Thread(target=_loop, name='MainFirst', daemon=True); R['th'] = th; th.start()


def view():
    R = _reg(); now = time.time()
    return {'on': enabled(), 'active': R['until'] > now, 'left': max(0, round(R['until'] - now)), 'why': R['why'], 'n': R['n'],
            'lag_ms': round((now - float(R.get('beat') or now)) * 1000), 'max_lag_ms': round(R['max_lag'] * 1000), 'lim_ms': int(_cfg('mf_lag_ms', 400) or 400),
            'log': [f'{time.strftime("%H:%M:%S", time.localtime(t))} {w}' for t, w in R['log'][-10:]][::-1]}

"""🤝 程式握手（apphs/1，規則第 3 版）：同一台電腦上的幾個程式互相說「我現在要做什麼、用了多少」，誰需要就讓誰先跑。

這個檔是共用的：SortCut、FusionStitch、ComfyRemote 用的是同一份，**整個檔直接複製過去就能用**（只用 Python 標準函式庫、沒有 Qt）。
完整規則看 HANDSHAKE_握手協定.md。

用法（跟第 1 版一樣，舊的呼叫都不用改）：
    import app_handshake as HS
    hs = HS.Handshake('FusionStitch', 'FusionStitch', '2.20.0', port=8361, state=my_state)   # my_state() 回傳下面 STATE 的格式
    hs.start()
    d = hs.decide()        # {'mode': 'alone'|'lead'|'yield'|'split', 'peer', 'why', 'cpu_cap', 'nvenc_cap', 'no_new_heavy', ...}
    hs.stop()              # 關程式時（會刪掉自己的檔，對方就知道你不在了）；熱更新時 hs.stop(remove=False)

怎麼交換：每個程式每 2 秒把自己的狀態寫到 %LOCALAPPDATA%\\AppHandshake\\<app>.json（先寫暫存檔再改名，不會讀到一半），
並讀別人的檔。超過 10 秒沒更新、或 pid 已經不在 → 當作不在。不用網路、不用開埠、熱更新也不會斷。

規則第 2 版新增：
  * 🆙 誰新就用誰的規則：每個程式把自己這份檔放到 AppHandshake\\lib\\app_handshake_r<RULES>.py。
    兩邊都用資料夾裡**最新的規則版本**來算 decide()，所以只要更新其中一邊，另一邊下一輪（2 秒內）就照新規則做，
    不用兩邊都更新。改規則的人：把 RULES 加 1（同一個 RULES 不要放兩種內容）。
  * ⚖ 分配拉桿（兩邊共用）：AppHandshake\\policy.json 的 share（例如 FusionStitch 40、SortCut 60），
    兩邊都在做重工作時照這個比例分；任何一邊改，兩邊一起變（最後改的為準）。
  * 🧑‍💻 留給使用者：有人在用這台電腦（鍵盤／滑鼠 idle_min 分鐘內動過）時，兩邊合起來只用 100 − reserve %
    （預設留 40%：平分時 50/50 → 30/30）。

規則第 3 版（SortCut V0.6.15 寫的；三個程式：SortCut、FusionStitch、ComfyRemote）：
  * 🧑‍💻 永遠留 reserve3 %（預設 10%）給使用者隨時操作電腦 → 大家合起來最多用 90%。
  * ⚡ 優先程式（policy 'first'，預設 ComfyRemote）一在做重工作：它拿 first_cap %（預設 80%），
    其他程式都降到 yield_cap %（預設 5%），新的重工作先不開（跑到一半的慢慢跑）。ComfyRemote 通常幾分鐘就做完，做完大家回來。
  * ⚖ 平常（沒有優先程式在跑）：在做重工作的程式照 share 比例分 90%（預設一樣 → SortCut 45%、FusionStitch 45%）；
    只有一個在做重工作 → 它拿 90%。沒在做重工作的程式（閒著或小工作）最多 10%。
  * ☑ 這台有誰（policy 'members'，三個程式的設定畫面都能勾）：沒勾的程式就算開著也不算進來。
  * 回傳的 cpu_cap＝這個程式的重工作最多用整台 CPU 的幾 %（顯示卡、硬碟照同一個比例放慢）；alloc＝每個程式分到的 %（給畫面顯示）。
  * mode：'lead'（優先程式自己）、'yield'（讓優先程式）、'split'（照比例分，包含只有自己在做也是 90%）、'alone'（沒人要分）。
    第 2 版的程式只看 yield／split 的 cpu_cap，所以第 3 版把「要限制」的情況都回 yield 或 split，舊程式照樣聽得懂。
"""
import json
import os
import tempfile
import threading
import time
from pathlib import Path

PROTO = 'apphs/1'
RULES = 3              # 規則版本：改 decide 的規則就加 1（越大越新）
EVERY = 2.0            # 幾秒寫一次
STALE = 10.0           # 幾秒沒更新算不在
LOSE_CPU = 20.0        # 讓路的那邊：重工作最多用整台 CPU 的 %
SPLIT_CPU = 45.0       # （第 1 版用的平分上限；第 2 版改成看 policy）
WANT_TXT = {0: '閒著', 1: '背景小工作', 2: '在做重工作', 3: '使用者在等'}
POLICY_DEFAULT = {'share': {}, 'reserve': 40, 'idle_min': 3, 'reserve_on': True,
                  'reserve3': 10, 'first': ['ComfyRemote'], 'first_cap': 80, 'yield_cap': 5, 'members': {}}   # 第 3 版加的
APPS = ['SortCut', 'FusionStitch', 'ComfyRemote']                                  # 已知會握手的程式（畫面上的「這台有誰」）


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


def idle_seconds():
    """這台電腦的鍵盤／滑鼠多久沒動（秒）；不是 Windows → None。兩邊讀到的是同一個值."""
    if os.name != 'nt': return None
    try:
        import ctypes

        class LII(ctypes.Structure):
            _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]
        li = LII(); li.cbSize = ctypes.sizeof(LII)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)): return None
        return max(0.0, ((ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000.0)
    except Exception: return None


# ---------------------------------------------------------------- ⚖ 共用設定（拉桿）
def policy():
    """AppHandshake\\policy.json：{'share': {app: %}, 'reserve': %, 'idle_min': 分, 'reserve_on': bool, 't', 'by'}."""
    P = dict(POLICY_DEFAULT); P['share'] = {}
    try:
        d = json.loads((folder() / 'policy.json').read_text(encoding='utf-8'))
        if isinstance(d, dict): P.update({k: v for k, v in d.items() if k in ('share', 'reserve', 'idle_min', 'reserve_on', 't', 'by', 'reserve3', 'first', 'first_cap', 'yield_cap', 'members')})
    except Exception: pass
    try: P['share'] = {str(k): max(5, min(95, float(v))) for k, v in dict(P.get('share') or {}).items()}
    except Exception: P['share'] = {}
    try: P['reserve'] = max(0, min(80, float(P.get('reserve') if P.get('reserve') is not None else 40)))
    except Exception: P['reserve'] = 40
    try: P['idle_min'] = max(0.5, min(60, float(P.get('idle_min') or 3)))
    except Exception: P['idle_min'] = 3
    P['reserve_on'] = P.get('reserve_on') is not False
    try: P['reserve3'] = max(0, min(50, float(P.get('reserve3') if P.get('reserve3') is not None else 10)))
    except Exception: P['reserve3'] = 10
    try: P['first_cap'] = max(10, min(95, float(P.get('first_cap') or 80)))
    except Exception: P['first_cap'] = 80
    try: P['yield_cap'] = max(1, min(30, float(P.get('yield_cap') or 5)))
    except Exception: P['yield_cap'] = 5
    P['first'] = [str(x) for x in (P.get('first') if isinstance(P.get('first'), list) else ['ComfyRemote'])]
    P['members'] = {str(k): bool(v) for k, v in dict(P.get('members') or {}).items()}
    return P


def set_policy(by='', **kw):
    """改共用設定（兩邊都會照新的做）。例：set_policy('FusionStitch', share={'FusionStitch': 40, 'SortCut': 60})、
    set_policy(by, reserve=40)、set_policy(by, reserve_on=False)。回傳新的設定."""
    P = policy()
    for k in ('share', 'reserve', 'idle_min', 'reserve_on', 'reserve3', 'first', 'first_cap', 'yield_cap', 'members'):
        if k in kw and kw[k] is not None:
            if k == 'share': P['share'] = {**P.get('share', {}), **{str(a): float(v) for a, v in dict(kw[k]).items()}}
            elif k == 'members': P['members'] = {**P.get('members', {}), **{str(a): bool(v) for a, v in dict(kw[k]).items()}}
            else: P[k] = kw[k]
    P['t'] = time.time(); P['by'] = str(by)
    p = folder() / 'policy.json'; tmp = p.with_suffix('.tmp')
    try: tmp.write_text(json.dumps(P, ensure_ascii=False), encoding='utf-8'); os.replace(tmp, p)
    except Exception: pass
    return policy()


def share_of(app, peers, P=None):
    """這邊在「兩邊都在做重工作」時分到整份的幾 %（沒設過 → 大家一樣）."""
    P = P or policy(); S = P.get('share') or {}
    mine = float(S.get(app, 50))
    tot = mine + sum(float(S.get(str(p.get('app')), 50)) for p in peers)
    return 100.0 * mine / tot if tot > 0 else 50.0


def lead_of(a, b):
    """兩邊算出來一定一樣：want 大的先；一樣看 prio（使用者設的，大的先）；再一樣 → 平分（回 None）.
    want 0（閒著）的那邊不用讓、也不用搶."""
    wa, wb = int(a.get('want') or 0), int(b.get('want') or 0)
    if wa != wb: return a if wa > wb else b
    pa, pb = int(a.get('prio') if a.get('prio') is not None else 5), int(b.get('prio') if b.get('prio') is not None else 5)
    if pa != pb: return a if pa > pb else b
    return None


def _brief(p):
    return {'app': p.get('app'), 'name': p.get('name'), 'ver': p.get('ver'), 'want': p.get('want'), 'prio': p.get('prio'), 'what': p.get('what'),
            'use': p.get('use'), 'age': round(time.time() - float(p.get('t') or 0), 1), 'mode': p.get('mode'), 'rules': p.get('rules', 1)}


def member(app, pol):
    """這台有沒有勾這個程式（沒設過＝有）."""
    return (pol.get('members') or {}).get(str(app), True) is not False


def decide_with(me, P, pol=None, idle=None):
    """規則本體（第 3 版：三個程式、留 10% 給使用者、ComfyRemote 優先 80%）。me＝自己的狀態、P＝還在的別人、pol＝policy()、idle＝idle_seconds().
    回傳 mode／peer／why／cpu_cap／nvenc_cap／no_new_heavy（跟第 1、2 版一樣），另外多 alloc／budget／share／first."""
    if not pol or 'first' not in pol: pol = policy()                            # 舊版（第 2 版）的程式傳進來的設定沒有第 3 版的欄位 → 自己重讀
    P = [p for p in P if member(p.get('app'), pol)]
    budget = 100.0 - float(pol.get('reserve3') if pol.get('reserve3') is not None else 10)
    ycap = float(pol.get('yield_cap') or 5); fcap = min(budget, float(pol.get('first_cap') or 80)); firsts = set(pol.get('first') or [])
    mx_nv = int((me.get('max') or {}).get('nvenc') or 8)
    base = {'cpu_cap': None, 'nvenc_cap': None, 'no_new_heavy': False, 'peers': [_brief(p) for p in P], 'rules': RULES,
            'user_active': bool(idle is not None and idle < float(pol.get('idle_min') or 3) * 60), 'budget': round(budget, 1), 'share': None, 'alloc': {}, 'first': None}
    if not me.get('on', True) or not P:
        return {**base, 'mode': 'alone', 'peer': '', 'why': '沒有別的程式要讓' if me.get('on', True) else '握手關著'}
    every = [me] + P; heavy = [x for x in every if int(x.get('want') or 0) >= 2]
    nm = lambda x: x.get('name') or x.get('app')
    me_h = int(me.get('want') or 0) >= 2
    fh = [x for x in heavy if str(x.get('app')) in firsts]
    S = pol.get('share') or {}; w = lambda x: max(1.0, float(S.get(str(x.get('app')), 50)))
    alloc = {}
    if fh:                                                                       # ⚡ 優先程式在跑：它 80%，其他 5%
        for x in every: alloc[str(x.get('app'))] = round(fcap / len(fh), 1) if x in fh else ycap
        if me in fh:
            c = alloc[str(me.get('app'))]
            return {**base, 'alloc': alloc, 'first': nm(me), 'mode': 'lead', 'peer': '、'.join(nm(x) for x in P), 'cpu_cap': c, 'nvenc_cap': max(1, int(round(mx_nv * c / 100.0))),
                    'why': f'⚡ 這邊優先：用 {c:.0f}%，其他程式降到 {ycap:.0f}%，留 {100 - budget:.0f}% 給你'}
        f0 = fh[0]
        return {**base, 'alloc': alloc, 'first': nm(f0), 'mode': 'yield', 'peer': nm(f0), 'peer_want': int(f0.get('want') or 0), 'peer_what': f0.get('what', ''),
                'cpu_cap': ycap, 'nvenc_cap': 1, 'no_new_heavy': True,
                'why': f'⚡ {nm(f0)} 優先（它在做' + (f'：{f0.get("what")}' if f0.get('what') else '重工作') + f'）→ 這邊降到 {ycap:.0f}%，新的先不開'}
    light = min(10.0, budget)
    tw = sum(w(x) for x in heavy) or 1.0
    for x in every: alloc[str(x.get('app'))] = round(budget * w(x) / tw, 1) if x in heavy else light
    if not heavy:
        return {**base, 'alloc': alloc, 'mode': 'alone', 'peer': '', 'why': '大家都閒著，照常跑'}
    if me_h:
        c = alloc[str(me.get('app'))]; others = [x for x in heavy if x is not me]
        return {**base, 'alloc': alloc, 'mode': 'split', 'peer': '、'.join(nm(x) for x in others), 'share': round(100 * w(me) / tw, 1), 'cpu_cap': c,
                'nvenc_cap': max(1, int(round(mx_nv * c / 100.0))),
                'why': (f'跟 {"、".join(nm(x) for x in others)} 分：這邊 {c:.0f}%' if others else f'只有這邊在做重工作：用 {c:.0f}%') + f'（留 {100 - budget:.0f}% 給你）'}
    h0 = heavy[0]
    return {**base, 'alloc': alloc, 'mode': 'yield', 'peer': nm(h0), 'peer_want': int(h0.get('want') or 0), 'peer_what': h0.get('what', ''),
            'cpu_cap': light, 'nvenc_cap': max(1, int(round(mx_nv * light / 100.0))), 'no_new_heavy': False,
            'why': f'{"、".join(nm(x) for x in heavy)} 在做重工作：這邊的小工作最多 {light:.0f}%'}


def decide_with_r2(me, P, pol=None, idle=None):
    """規則本體（第 2 版，留著參考）。me＝自己的狀態、P＝還在的別人（list）、pol＝policy()、idle＝idle_seconds().
    回傳的欄位跟第 1 版一樣（舊程式照用），另外多 share／budget／user_active."""
    pol = pol or policy()
    active = idle is not None and idle < float(pol.get('idle_min') or 3) * 60
    budget = 100.0 - float(pol.get('reserve') or 0) if (active and pol.get('reserve_on', True)) else 100.0
    base = {'cpu_cap': None, 'nvenc_cap': None, 'no_new_heavy': False, 'peers': [_brief(p) for p in P], 'rules': RULES,
            'user_active': bool(active), 'budget': round(budget, 1), 'share': None}
    if not me.get('on', True) or not P:
        return {**base, 'mode': 'alone', 'peer': '', 'why': '沒有別的程式要讓' if me.get('on', True) else '握手關著'}
    worst = None
    for p in P:                                                                  # 有好幾個的話：照最嚴的那個
        L = lead_of(me, p); w = int(p.get('want') or 0); mine = int(me.get('want') or 0)
        if L is None: r = ('split', 1) if min(w, mine) >= 2 else ('alone', 0)       # 兩邊都在做重工作、優先一樣 → 照拉桿分
        elif L is p: r = ('yield', 2) if w >= 2 else ('alone', 0)                  # 對方只在做背景小工作：不用讓
        else: r = ('lead', 0) if w >= 1 else ('alone', 0)
        if worst is None or r[1] > worst[0][1]: worst = (r, p)
    (mode, _sev), p = worst; nm = p.get('name') or p.get('app'); w = int(p.get('want') or 0)
    mx_nv = int((p.get('max') or {}).get('nvenc') or (me.get('max') or {}).get('nvenc') or 8)
    p_nv = int((p.get('use') or {}).get('nvenc') or 0)
    out = {**base, 'mode': mode, 'peer': nm, 'peer_want': w, 'peer_what': p.get('what', '')}
    heavy_peers = [x for x in P if int(x.get('want') or 0) >= 2 and lead_of(me, x) is None]
    if mode == 'yield':
        out.update(cpu_cap=min(LOSE_CPU, budget), nvenc_cap=max(0, min(2, mx_nv - p_nv)), no_new_heavy=w >= 2,
                   why=f'讓 {nm} 先跑（它{WANT_TXT.get(w, "")}' + (f'：{p.get("what")}' if p.get('what') else '') + '）')
    elif mode == 'split':
        sh = share_of(str(me.get('app')), heavy_peers or [p], pol); cap = budget * sh / 100.0
        out.update(share=round(sh, 1), cpu_cap=round(cap, 1), nvenc_cap=max(1, int(round(mx_nv * sh / 100.0))),
                   why=f'跟 {nm} 分：這邊 {sh:.0f}%' + (f'（有人在用電腦，留 {100 - budget:.0f}% 給你 → 這邊 {cap:.0f}%）' if budget < 100 else ''))
    elif mode == 'lead':
        out.update(why=f'這邊先跑，{nm} 讓路（它{WANT_TXT.get(w, "")}）')
    else: out.update(why=f'{nm} 閒著，照常跑')
    return out


# ---------------------------------------------------------------- 🆙 誰新就用誰的規則
def lib_dir():
    p = folder() / 'lib'
    try: p.mkdir(parents=True, exist_ok=True)
    except Exception: pass
    return p


def publish(src=None):
    """把這份檔放到 lib\\app_handshake_r<RULES>.py（已經有同一版就不動）."""
    try:
        src = Path(src or __file__); dst = lib_dir() / f'app_handshake_r{RULES}.py'
        if not dst.exists():
            tmp = dst.with_suffix('.tmp'); tmp.write_bytes(src.read_bytes()); os.replace(tmp, dst)
    except Exception: pass


_LIB = {'n': 0, 'mod': None, 'mt': 0.0, 'err': '', 't': 0.0}


def newest_rules():
    """資料夾裡最新、而且比這份新的規則（module）；沒有就 None。每 10 秒看一次."""
    now = time.time()
    if now - _LIB['t'] < 10: return _LIB['mod'] if _LIB['n'] > RULES else None
    _LIB['t'] = now
    best = (RULES, None)
    try:
        for f in lib_dir().glob('app_handshake_r*.py'):
            try: n = int(f.stem.rsplit('_r', 1)[1])
            except Exception: continue
            if n > best[0]: best = (n, f)
    except Exception: pass
    n, f = best
    if f is None: _LIB.update(n=0, mod=None); return None
    try:
        mt = f.stat().st_mtime
        if _LIB['n'] == n and _LIB['mt'] == mt and _LIB['mod'] is not None: return _LIB['mod']
        import importlib.util
        spec = importlib.util.spec_from_file_location(f'app_handshake_r{n}', str(f)); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        if int(getattr(m, 'RULES', 0)) != n or not callable(getattr(m, 'decide_with', None)): raise ValueError('不是握手規則檔')
        _LIB.update(n=n, mod=m, mt=mt, err='')
        return m
    except Exception as ex:
        _LIB.update(n=0, mod=None, err=f'第 {n} 版規則載入失敗：{ex}'[:160])
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
        m = newest_rules()
        return {'proto': PROTO, 'app': self.app, 'name': self.name, 'ver': self.ver, 'pid': os.getpid(), 'port': self.port,
                'host': os.environ.get('COMPUTERNAME', ''), 't': time.time(), 'on': S.get('on', True) is not False,
                'want': max(0, min(3, int(S.get('want') or 0))), 'prio': max(0, min(10, int(S.get('prio') if S.get('prio') is not None else 5))),
                'what': str(S.get('what') or '')[:120], 'use': dict(S.get('use') or {}), 'max': dict(S.get('max') or {}),
                'rules': int(getattr(m, 'RULES', RULES)) if m else RULES, 'rules_own': RULES,
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
                if p.stem.lower() in (self.app.lower(), 'policy'): continue
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
        """回自己現在要怎麼做。用資料夾裡最新的規則算（兩邊規則一樣、資料一樣 → 結果對得起來）."""
        me = self.me or {}; P = self.peers(); pol = policy(); idle = idle_seconds()
        m = newest_rules()
        if m is not None:
            try:
                d = dict(m.decide_with(me, P, pol, idle)); d.setdefault('rules', int(getattr(m, 'RULES', 0))); d['rules_from'] = 'lib'
                return d
            except Exception as ex: self.err = f'新規則出錯，先用自己的：{ex}'[:160]
        d = decide_with(me, P, pol, idle); d['rules_from'] = 'own'
        return d

    _brief = staticmethod(_brief)

    # ---------------------------------------------------------------- 背景
    def _loop(self):
        publish()
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

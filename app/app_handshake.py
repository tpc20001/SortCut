"""🤝 程式握手（apphs/1，規則第 4 版）：同一台電腦上的幾個程式互相說「我現在要做什麼、用了多少」，誰需要就讓誰先跑。

這個檔是共用的：SortCut、FusionStitch、ComfyRemote 用的是同一份（第 4 版起三邊統一用這份），**整個檔直接複製過去就能用**（只用 Python 標準函式庫、沒有 Qt）。
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

規則第 3 版（ComfyRemote V0.3.40 帶來的，三個程式：ComfyRemote／FusionStitch／SortCut，另一台還有 TikLive）：
  * 設定另外放 AppHandshake\\policy3.json（舊版的 set_policy 改 policy.json 不會把第 3 版的設定弄掉）：
      members      這台電腦「有參與」的程式（勾選的才算；沒勾的就算開著也不管它、它也不受限）；空的＝看到誰算誰
      normal       平常的分配權重，預設 FusionStitch 45、SortCut 45（只有一個在做重工作 → 它拿全部預算）
      reserve      永遠留給使用者的 %（預設 10：45＋45＋10）
      boost_app    最優先的程式（預設 ComfyRemote：生圖很快、通常幾分鐘就做完）
      boost        它在做事（want ≥ 2）時拿幾 %（預設 80），其他在做重工作的各拿 boost_others（預設 5）：80＋5＋5＋10
      lv           每個程式自己的上限 Lv 1～10（右上角 Lv 畫面設的）：cpu_cap 不超過 Lv × 10 %
  * decide_with 回傳的欄位跟第 2 版一樣，cpu_cap 一律有值（照上面算出來的 %），另外多 lv／alloc（每個程式現在分到幾 %）／members。
"""
import json
import os
import tempfile
import threading
import time
from pathlib import Path

PROTO = 'apphs/1'
RULES = 5              # 規則版本：改 decide 的規則就加 1（越大越新）
EVERY = 2.0            # 幾秒寫一次
STALE = 10.0           # 幾秒沒更新算不在
LOSE_CPU = 20.0        # 讓路的那邊：重工作最多用整台 CPU 的 %
SPLIT_CPU = 45.0       # （第 1 版用的平分上限；第 2 版改成看 policy）
WANT_TXT = {0: '閒著', 1: '背景小工作', 2: '在做重工作', 3: '使用者在等'}
# 規則第 5 版（SortCut V0.6.18）：使用者要「CPU／顯示卡不要閒著」
#   * 🧑‍💻 有人在用電腦（鍵盤／滑鼠 3 分鐘內動過）才留 reserve %；沒人在用 → 大家合起來可以用到 100%。
#   * 🧊 卡住偵測：優先程式（ComfyRemote）說「在做事」(want≥2)，可是超過 stall_sec（預設 5 分鐘）沒有進度
#     （它自己寫的 progress_t 沒變；舊版沒寫就看它從什麼時候開始忙），而且這段時間顯示卡也沒有別人在用（ComfyUI 沒在跑）
#     → 當作卡住：不讓它了，大家回到平常的分配；並在自己的狀態檔寫 nudge＝{'ComfyRemote': 時間} 提醒它（它可以跳過、重試、或回報 want 0）。
#   * ♻ 用不完的分出去：在做重工作的程式，如果有寫 use.cpu 而且用不到分給它的（差超過 10%），差的那一段分給其他還在做的。
#   * 新欄位（狀態檔）：idle（鍵盤滑鼠多久沒動，秒）、busy_since（自己從什麼時候開始 want≥2）、progress_t（自己最後一次有進度的時間，程式自己給）、
#     seen（觀察：{'gpu_hi_t': 最後一次看到顯示卡被「別人」用超過 15% 的時間, 'busy_since': {app: 看到它開始忙的時間}}）、nudge。
#     舊版的程式不寫這些也照樣能算（缺的就跳過那一項）。
# 規則第 4 版（SortCut V0.6.17）：以 ComfyRemote V0.3.40 的第 3 版（policy3.json）為準，三邊統一。改的地方：
#   * 共用設定檔格式不同也不會出錯（policy.json 的 members 有人寫成清單、有人寫成字典；讀不懂就用預設，絕不讓「寫自己的狀態」失敗）
#     ── 第 3 版時 SortCut 就是因為讀 policy.json 出錯，狀態檔一直沒更新，另外兩個看不到它。
#   * 算規則出錯也照樣寫自己的狀態（mode 寫 alone），別人才知道你還活著。
#   * 優先程式（boost_app，預設 ComfyRemote）在做事時，其他程式 no_new_heavy＝True（新的重工作先不開，跑到一半的照跑但降到 boost_others %）。
POLICY_DEFAULT = {'share': {}, 'reserve': 40, 'idle_min': 3, 'reserve_on': True}


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
        if isinstance(d, dict): P.update({k: v for k, v in d.items() if k in ('share', 'reserve', 'idle_min', 'reserve_on', 't', 'by')})
    except Exception: pass
    try: P['share'] = {str(k): max(5, min(95, float(v))) for k, v in dict(P.get('share') or {}).items()}
    except Exception: P['share'] = {}                                            # 第 4 版：格式不對就當沒設
    try: P['reserve'] = max(0, min(80, float(P.get('reserve') if P.get('reserve') is not None else 40)))
    except Exception: P['reserve'] = 40
    try: P['idle_min'] = max(0.5, min(60, float(P.get('idle_min') or 3)))
    except Exception: P['idle_min'] = 3
    P['reserve_on'] = P.get('reserve_on') is not False
    return P


def set_policy(by='', **kw):
    """改共用設定（兩邊都會照新的做）。例：set_policy('FusionStitch', share={'FusionStitch': 40, 'SortCut': 60})、
    set_policy(by, reserve=40)、set_policy(by, reserve_on=False)。回傳新的設定."""
    P = policy()
    for k in ('share', 'reserve', 'idle_min', 'reserve_on'):
        if k in kw and kw[k] is not None:
            if k == 'share': P['share'] = {**P.get('share', {}), **{str(a): float(v) for a, v in dict(kw[k]).items()}}
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


def decide_with_v2(me, P, pol=None, idle=None):
    """第 2 版的規則（第 3 版的 policy3 被關掉時用）。me＝自己的狀態、P＝還在的別人（list）、pol＝policy()、idle＝idle_seconds().
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


# ---------------------------------------------------------------- ⚖ 第 3 版：三個程式、勾選誰參與、最優先的程式
POLICY3_DEFAULT = {'on': True, 'members': [], 'normal': {'FusionStitch': 45, 'SortCut': 45, 'TikLive': 45}, 'reserve': 10,
                   'boost_app': 'ComfyRemote', 'boost': 80, 'boost_others': 5, 'lv': {}, 'stall_sec': 300, 'idle_min': 3}
KNOWN = (('ComfyRemote', 'ComfyRemote'), ('FusionStitch', 'GoPro Fusion 360（FusionStitch）'), ('SortCut', 'SortCut'), ('TikLive', 'TikLive'))


def policy3():
    """AppHandshake\\policy3.json（第 3 版的設定；跟舊的 policy.json 分開）."""
    P = json.loads(json.dumps(POLICY3_DEFAULT))
    try:
        d = json.loads((folder() / 'policy3.json').read_text(encoding='utf-8'))
        if isinstance(d, dict):
            for k in POLICY3_DEFAULT:
                if k in d: P[k] = d[k]
            for k in ('t', 'by'):
                if k in d: P[k] = d[k]
    except Exception: pass
    try: P['members'] = [str(x) for x in (P.get('members') or [])]
    except Exception: P['members'] = []
    try: P['normal'] = {str(k): max(1.0, min(100.0, float(v))) for k, v in dict(P.get('normal') or {}).items()}
    except Exception: P['normal'] = dict(POLICY3_DEFAULT['normal'])
    def num(k, lo, hi):
        try: P[k] = max(lo, min(hi, float(P.get(k))))
        except Exception: P[k] = float(POLICY3_DEFAULT[k])
    num('reserve', 0, 60); num('boost', 10, 95); num('boost_others', 0, 40); num('stall_sec', 60, 3600); num('idle_min', 0.5, 60)
    try: P['lv'] = {str(k): max(1, min(10, int(v))) for k, v in dict(P.get('lv') or {}).items()}
    except Exception: P['lv'] = {}
    P['boost_app'] = str(P.get('boost_app') or ''); P['on'] = P.get('on') is not False
    return P


def set_policy3(by='', **kw):
    """改第 3 版的設定（三個程式一起照新的做）。例：set_policy3('ComfyRemote', members=['ComfyRemote', 'SortCut'])、
    set_policy3(by, normal={'FusionStitch': 45, 'SortCut': 45})、set_policy3(by, lv={'SortCut': 6})、set_policy3(by, reserve=10, boost=80)."""
    P = policy3()
    for k, v in kw.items():
        if k not in POLICY3_DEFAULT or v is None: continue
        if k in ('normal', 'lv'): P[k] = {**P.get(k, {}), **{str(a): b for a, b in dict(v).items()}}
        else: P[k] = v
    P['t'] = time.time(); P['by'] = str(by)
    p = folder() / 'policy3.json'; tmp = p.with_suffix('.tmp3')
    try: tmp.write_text(json.dumps(P, ensure_ascii=False), encoding='utf-8'); os.replace(tmp, p)
    except Exception: pass
    return policy3()


def _num(x):
    try: return float(x)
    except Exception: return None


def prep5(states, P3, now=None):
    """第 5 版的前處理（純函式）：有沒有人在用電腦 → 預算；優先程式是不是卡住了 → 當作沒在忙."""
    now = time.time() if now is None else now
    idles = [v for v in (_num(st.get('idle')) for st in states.values()) if v is not None]
    active = (min(idles) < float(P3.get('idle_min') or 3) * 60) if idles else True
    budget = 100.0 - float(P3['reserve']) if active else 100.0
    stall = float(P3.get('stall_sec') or 300); B = P3.get('boost_app') or ''; stalled = []
    sB = states.get(B)
    if sB and int(sB.get('want') or 0) >= 2:
        seen = [st.get('seen') or {} for st in states.values() if isinstance(st.get('seen'), dict)]
        bs = [_num(sB.get('busy_since'))] + [_num((x.get('busy_since') or {}).get(B)) for x in seen]
        bs = [v for v in bs if v]
        ref = _num(sB.get('progress_t')) or (min(bs) if bs else None)
        gpu_hi = max([_num(x.get('gpu_hi_t')) or 0.0 for x in seen] or [0.0])
        u = sB.get('use') or {}
        own_busy = (_num(u.get('gpu')) or 0) > 10 or (_num(u.get('cpu')) or 0) > 10
        if ref and now - ref > stall and now - gpu_hi > stall and not own_busy: stalled.append(B)
    S2 = {a: ({**st, 'want': 0} if a in stalled else st) for a, st in states.items()}
    return S2, budget, active, stalled


def conserve5(A, states, budget):
    """第 5 版：在做重工作的程式用不到分給它的（有寫 use.cpu、差超過 10%）→ 差的那段分給其他還在做的（CPU／顯示卡不要閒著）."""
    heavy = [a for a, st in states.items() if a in A and int(st.get('want') or 0) >= 2]
    sur = 0.0; rec = []
    for a in heavy:
        u = _num((states[a].get('use') or {}).get('cpu'))
        if u is not None and A[a]['cap'] - (u + 10.0) > 0: sur += A[a]['cap'] - (u + 10.0)
        else: rec.append(a)
    if sur >= 5 and rec:
        add = sur / len(rec)
        for a in rec:
            c = min(budget, A[a]['cap'] + add)
            if c > A[a]['cap'] + 0.5: A[a] = {**A[a], 'cap': round(c, 1), 'why': A[a]['why'] + f'（別人用不完的 +{c - A[a]["cap"]:.0f}%）'}
    return A


def alloc3(states, P3=None):
    """每個程式現在分到整台的幾 %（cpu_cap）。states＝{app: 狀態}（含自己），只看有參與的。純函式，三個程式算出來一樣.
    回傳 {app: {'cap': %, 'mode': ..., 'why': ...}}。"""
    P3 = P3 or policy3(); M = P3['members']; budget = 100.0 - P3['reserve']
    S = {a: s for a, s in states.items() if (not M or a in M) and s.get('on', True) is not False}
    heavy = [a for a, s in S.items() if int(s.get('want') or 0) >= 2]
    lv = lambda a: P3['lv'].get(a, 10) * 10.0
    out = {}
    B = P3['boost_app']
    if B in heavy and len(heavy) > 1:                                            # 最優先的程式在做事：它拿 boost，其他各 boost_others
        others = [a for a in heavy if a != B]; o = P3['boost_others']
        cb = min(P3['boost'], lv(B), budget - o * len(others)); rest = budget - cb
        W = {a: max(o, min(lv(a), rest * P3['normal'].get(a, 45) / max(1.0, sum(P3['normal'].get(x, 45) for x in others)) if cb < P3['boost'] else o)) for a in others}
        out[B] = {'cap': round(cb, 1), 'mode': 'lead', 'why': f'這邊最優先：{cb:.0f}%（其他的各 {o:.0f}%，留 {P3["reserve"]:.0f}% 給你）'}
        for a in others: out[a] = {'cap': round(W[a], 1), 'mode': 'yield', 'why': f'{B} 在做事、最優先 → 這邊 {W[a]:.0f}%'}
    elif len(heavy) > 1:                                                         # 平常：照 normal 的權重分
        tot = sum(P3['normal'].get(a, 45) for a in heavy)
        for a in heavy:
            c = min(lv(a), budget * P3['normal'].get(a, 45) / tot)
            out[a] = {'cap': round(c, 1), 'mode': 'split', 'why': '一起做：這邊 ' + f'{c:.0f}%（' + '、'.join(f'{x} {budget * P3["normal"].get(x, 45) / tot:.0f}%' for x in heavy if x != a) + f'，留 {P3["reserve"]:.0f}% 給你）'}
    elif heavy:
        a = heavy[0]; c = min(lv(a), budget); out[a] = {'cap': round(c, 1), 'mode': 'lead' if len(S) > 1 else 'alone', 'why': f'只有這邊在做重工作：{c:.0f}%（留 {P3["reserve"]:.0f}% 給你）'}
    for a, s in S.items():
        if a not in out:
            c = min(lv(a), budget if not heavy else max(P3['boost_others'], 5.0)); w = int(s.get('want') or 0)
            out[a] = {'cap': round(c, 1), 'mode': 'alone', 'why': ('閒著' if w == 0 else '背景小工作') + (f'（{c:.0f}%）' if heavy else '')}
    return out


def decide_with(me, P, pol=None, idle=None):
    """規則本體（第 3 版）。欄位跟第 2 版一樣，另外多 lv／alloc／members／p3。policy3 的 on＝False → 用第 2 版."""
    P3 = policy3()
    if not P3.get('on', True): d = decide_with_v2(me, P, pol, idle); d['rules'] = RULES; return d
    app = str(me.get('app') or ''); M = P3['members']
    base = {'cpu_cap': None, 'nvenc_cap': None, 'no_new_heavy': False, 'peers': [_brief(p) for p in P], 'rules': RULES, 'user_active': False,
            'budget': round(100.0 - P3['reserve'], 1), 'share': None, 'members': M, 'lv': P3['lv'].get(app, 10), 'alloc': {}, 'p3': True}
    if not me.get('on', True): return {**base, 'mode': 'alone', 'peer': '', 'why': '握手關著'}
    if M and app not in M: return {**base, 'mode': 'alone', 'peer': '', 'why': '這台電腦的握手沒有勾這個程式（不參與，不受限）'}
    states = {app: me}
    for p in P: states.setdefault(str(p.get('app') or ''), p)
    states, budget5, active5, stalled5 = prep5(states, P3)                      # 第 5 版：沒人在用 → 預算 100；優先程式卡住 → 不讓它
    P3x = {**P3, 'reserve': 100.0 - budget5}
    A = conserve5(alloc3(states, P3x), states, budget5)
    if stalled5:
        for a_, v_ in A.items():
            if a_ in stalled5: A[a_] = {**v_, 'why': f'說在忙，可是 {P3.get("stall_sec", 300) / 60:.0f} 分鐘沒有進度、顯示卡也沒在跑 → 當作卡住，大家不讓它了'}
    base.update(budget=round(budget5, 1), user_active=active5, stalled=stalled5)
    mine = A.get(app) or {'cap': budget5, 'mode': 'alone', 'why': ''}
    others = [p for p in P if (not M or str(p.get('app')) in M)]
    top = max(others, key=lambda p: int(p.get('want') or 0), default=None)
    mx_nv = int((me.get('max') or {}).get('nvenc') or (top or {}).get('max', {}).get('nvenc') or 8)
    cap = float(mine['cap'])
    return {**base, 'mode': mine['mode'], 'peer': (top.get('name') or top.get('app')) if top else '', 'peer_want': int(top.get('want') or 0) if top else 0,
            'peer_what': (top or {}).get('what', ''), 'cpu_cap': cap, 'share': cap, 'nvenc_cap': max(1, int(round(mx_nv * cap / 100.0))),
            'no_new_heavy': mine['mode'] == 'yield' and P3['boost_app'] in A and A[P3['boost_app']].get('mode') == 'lead',
            'why': (mine['why'] + (f'；{"、".join(stalled5)} 好像卡住了（沒進度），先不讓它' if stalled5 and app not in stalled5 else '')), 'alloc': {a: v['cap'] for a, v in A.items()}}


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
                'rules': int(getattr(m, 'RULES', RULES)) if m else RULES, 'rules_own': RULES, 'lv': S.get('lv'),
                **self._obs5(S),
                'mode': self._mode_safe()}

    def _obs5(self, S):
        """第 5 版的觀察欄位（給大家判斷「有沒有人在用電腦」「優先程式是不是卡住」）."""
        now = time.time(); O = getattr(self, '_o5', None)
        if O is None: O = self._o5 = {'busy_since': 0.0, 'gpu_hi_t': 0.0, 'peer_busy': {}, 'nudge': {}}
        w = int(S.get('want') or 0)
        if w >= 2: O['busy_since'] = O['busy_since'] or now
        else: O['busy_since'] = 0.0
        g = _num(S.get('gpu_other'))                                             # 程式自己量的：整台顯示卡（3D／Compute）扣掉自己用的
        if g is not None and g >= 15: O['gpu_hi_t'] = now
        for a, p in list(self.others.items()):
            if int(p.get('want') or 0) >= 2: O['peer_busy'][a] = O['peer_busy'].get(a) or now
            else: O['peer_busy'].pop(a, None)
        try:
            D = getattr(self, '_last_d', None) or {}
            for a in D.get('stalled') or []: O['nudge'][a] = O['nudge'].get(a) or now     # 提醒卡住的那個（它自己決定跳過／重試／回報沒在忙）
            for a in list(O['nudge']):
                if a not in (D.get('stalled') or []): O['nudge'].pop(a, None)
        except Exception: pass
        out = {'idle': idle_seconds(), 'busy_since': O['busy_since'] or None, 'seen': {'gpu_hi_t': O['gpu_hi_t'] or None, 'busy_since': dict(O['peer_busy'])}, 'nudge': dict(O['nudge'])}
        if S.get('progress_t'): out['progress_t'] = _num(S.get('progress_t'))
        return out

    def _mode_safe(self):
        """第 4 版：算規則出錯也要能寫出自己的狀態（不然別人會以為你沒開）."""
        if not self.me: return 'alone'
        try: d = self.decide(); self._last_d = d; return d.get('mode') or 'alone'
        except Exception as ex: self.err = f'算規則出錯（照樣寫狀態）：{ex}'[:160]; return 'alone'

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
                if not isinstance(d, dict) or not str(d.get('proto', '')).startswith('apphs/'): continue
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
        try: d = decide_with(me, P, pol, idle); d['rules_from'] = 'own'
        except Exception as ex:
            self.err = f'算規則出錯：{ex}'[:160]
            d = {'mode': 'alone', 'peer': '', 'why': f'算規則出錯：{ex}'[:120], 'cpu_cap': None, 'nvenc_cap': None, 'no_new_heavy': False, 'peers': [_brief(p) for p in P], 'rules': RULES, 'rules_from': 'own', 'alloc': {}}
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

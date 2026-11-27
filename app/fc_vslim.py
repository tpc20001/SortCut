"""🗜 影片瘦身（V0.1.34；V0.4.62 改成 VS V0.4.59 的「🎯 畫質目標」方式，不准 import Qt）.

很大、還是舊編碼（H.264／MPEG-4…）的影片轉成 H.265（HEVC）。

🎯 畫質目標（跟 VS 一樣的設定）：
  ① 每一部先從片長 10%／30%／50%／70%／90% 各取 2 秒，用不同畫質（CQ 18～40）試轉，
     跟原檔同一段比 SSIM（短邊最多 1080 比），取中間值；二分法找「中間值 ≥ 0.985」裡最省的 CQ
  ② 位元率上限＝原檔影像位元率的 95%（不會比原檔大）
  ③ 整部轉完再抽 3 個地方比 SSIM：低於底線 0.975 → CQ 降 3 重轉（最多 2 次）；還是不到底線 → 不用轉好的、原檔不動
  ④ 低於 0.90 一律放棄；轉完沒有比原檔小 8% 以上也放棄（原檔不動）

安全規則（不會弄丟東西）：
  • 新檔叫「原檔名_h265.mp4」放在同一個資料夾；長度要對、真的變小、畫質過關才算成功
  • 成功了原檔搬到「轉檔後隔離區」（可以復原）；不成功只刪「這次自己做出來的新檔」，原檔不動
  • 硬碟剩的空間不夠（少於原檔大小＋1 GB）就不做
"""
import os, re, json, subprocess, threading, time

import fc_fcore as fcore

QUAL = {'auto': ('🎯 照畫質自動（SSIM ≥ 0.985，跟 VS 一樣）', 0, 0),
        'hq': ('固定：高畫質（檔案省比較少）', 22, 24), 'std': ('固定：一般', 26, 28), 'small': ('固定：省空間（畫質稍降）', 30, 32)}   # (名字, x265 crf, 硬體 cq)
TARGET = ((480, 1.2e6), (720, 2.5e6), (1080, 5e6), (1440, 9e6), (99999, 16e6))        # 每種高度：H.265 大概需要的位元率
GOOD = ('hevc', 'h265', 'av1', 'vp9')                                                   # 已經是新編碼：不用轉
SUFFIX = '_h265'                                                            # 新檔名＝原檔名_h265.mp4（V0.4.61；以前是 _瘦身）
OLD_SUFFIX = ('_瘦身', '_h265')
# VS V0.4.59 的設定（cv_target 0.985、底線 floor 0.975、CQ 18～40、從 28 開始、5 段 × 2 秒、抽查 3 段、CQ 降 3 重轉最多 2 次）
TGT, FLOOR, ABORT = 0.985, 0.975, 0.90
CAP_K = {'h264': 0.6, 'hevc': 0.9, 'h265': 0.9, 'mpeg2video': 0.35, 'mpeg1video': 0.35, 'mpeg4': 0.45, 'msmpeg4v3': 0.45, 'msmpeg4v2': 0.45,
         'wmv3': 0.45, 'wmv2': 0.45, 'vc1': 0.5, 'vp8': 0.6, 'vp9': 0.9, 'av1': 1.0}
INTER = ('tt', 'bb', 'tb', 'bt')


def _nw(): return fcore.NO_WINDOW | (0x00004000 if os.name == 'nt' else 0)


def estimate(size, dur, h, codec):
    """估計轉完多大：原本的一半，或「這個解析度大概要的位元率」，取比較小的；但不會小於原本的 25%."""
    if not dur or dur <= 0: return size
    br = next(b for hh, b in TARGET if (h or 1080) <= hh)
    est = min(size * (0.5 if codec in ('h264', 'avc1', '') else 0.35), dur * br / 8)
    return int(max(size * 0.25, est))


def ssim_size(w, h):
    """比畫質用的大小：短邊最多 1080（跟 VS 一樣；縮太小看不到壓縮痕跡，分數會太寬鬆）."""
    w, h = int(w or 0), int(h or 0)
    if not w or not h: return 1280, 720
    if w <= h: tw = min(w, 1080); th = int(round(h * tw / w / 2)) * 2
    else: th = min(h, 1080); tw = int(round(w * th / h / 2)) * 2
    return max(2, tw - tw % 2), max(2, th - th % 2)


def ssim_lavfi(W, H, deint=False):
    return (f'[0:v]setpts=PTS-STARTPTS,{"bwdif=0," if deint else ""}scale={W}:{H}:flags=bicubic,setsar=1,format=yuv420p[a];'
            f'[1:v]setpts=PTS-STARTPTS,scale={W}:{H}:flags=bicubic,setsar=1,format=yuv420p[b];[a][b]ssim')


def _med(V):
    V = sorted(V); n = len(V)
    return None if not n else (V[n // 2] if n % 2 else (V[n // 2 - 1] + V[n // 2]) / 2)


def src_vbr(info):
    """原檔「影像」的位元率（bps）；讀不到就用 檔案大小 ÷ 長度，扣掉聲音估（跟 VS 一樣）."""
    try: v = int(float(info.get('vbr') or 0))
    except Exception: v = 0
    try:
        sz = float(info.get('size') or 0); d = float(info.get('dur') or 0); tot = sz * 8 / d if sz and d > 1 else 0
    except Exception: tot = 0
    if tot and (not v or v >= tot * 0.97):
        na = max(1, int(info.get('na') or 0)) if info.get('na') is not None else 1; v = int(max(tot * 0.5, tot - 160000 * na))
    return int(v)


class Slim:
    def __init__(self, E, old=None):
        self.E = E; self.st = old.st if old is not None else {}; self.enc = old.enc if old is not None else None
        self.tst = old.tst if old is not None and hasattr(old, 'tst') else {}           # 🧪 試轉的狀態
        self._tbl = False

    # ---------------------------------------------------------------- 紀錄（轉好的、SSIM）
    def _table(self):
        if self._tbl: return
        self.E.db.x("CREATE TABLE IF NOT EXISTS slim_done(id INTEGER PRIMARY KEY, t REAL, fid INTEGER, nfid INTEGER, mid INTEGER, src TEXT, dst TEXT, "
                    "osz INTEGER, nsz INTEGER, q INTEGER, ssim REAL, spot REAL, how TEXT, enc TEXT, note TEXT, viewed REAL DEFAULT 0, undone INTEGER DEFAULT 0)")
        self._tbl = True

    def cfg(self):
        C = self.E.cfg
        def f(k, d, lo, hi):
            try: return min(hi, max(lo, float(C.get(k) or d)))
            except Exception: return d
        return {'target': f('slim_target', TGT, 0.95, 0.995), 'floor': f('slim_floor', FLOOR, 0.90, 0.995)}

    # ---------------------------------------------------------------- 哪些值得轉
    def candidates(self, min_mb=200, limit=500, which='all'):
        """which（V0.4.61）：all 全部／tagged 已分類（不含 Delete 類）／moved 已經搬進分類資料夾的／wait 分好還沒搬的／untagged 還沒分類的."""
        E = self.E; out = []; tot = [0, 0, 0]
        T = {}
        if which != 'all':
            try:
                dc = E.vc.del_cat(); T = {fid: (cat, mv) for fid, cat, mv in E.db.q('SELECT fid, cat, moved FROM vc_tag')}
                if dc: T = {f: v for f, v in T.items() if v[0] != dc} if which != 'untagged' else T
            except Exception: T = {}
        def ok_(fid):
            if which == 'all': return True
            if which == 'untagged': return fid not in T
            v = T.get(fid)
            if not v: return False
            return which == 'tagged' or (which == 'moved' and v[1]) or (which == 'wait' and not v[1])
        R = self.ratio()
        for r in E.db.q("SELECT id, path, size, dur, w, h, vcodec, taken FROM files WHERE state='' AND kind='video' AND size>=? AND dur>5 "
                        "AND health NOT IN ('broken','partial','zero') ORDER BY size DESC", (int(min_mb) * 1000000,)):
            if not ok_(r['id']): continue
            c = (r['vcodec'] or '').lower()
            if any(g in c for g in GOOD) or any(x in os.path.basename(r['path']) for x in OLD_SUFFIX): continue
            est = estimate(r['size'], r['dur'], r['h'], c)
            if R[1] >= 3: est = int(r['size'] * R[0])                            # 已經轉過幾部：照實際平均比例估
            save = r['size'] - est
            if save < 50e6 or save < r['size'] * 0.2: continue
            tot[0] += 1; tot[1] += r['size']; tot[2] += save
            if len(out) < limit: out.append(dict(dict(r), est=est, save=save, br=int(r['size'] * 8 / r['dur'])))
        return {'ok': True, 'rows': out, 'n': tot[0], 'bytes': tot[1], 'save': tot[2], 'st': self.status(), 'ratio': R,
                'enc': self.enc, 'qual': {k: v[0] for k, v in QUAL.items()}, 'q': self.E.cfg.get('slim_q') or 'auto', 'cfg': self.cfg()}

    def status(self):
        return dict({k: v for k, v in self.st.items() if k != 'ids'}, test=dict(self.tst))

    def ratio(self):
        """已經轉好的平均變成原檔的幾 %：(比例, 幾部)."""
        try:
            self._table(); r = self.E.db.one("SELECT SUM(nsz), SUM(osz), COUNT(*) FROM slim_done WHERE undone=0 AND osz>0")
            if r and r[2]: return [float(r[0]) / float(r[1]), int(r[2])]
        except Exception: pass
        return [0.5, 0]

    # ---------------------------------------------------------------- 轉好的清單（像 VS 的「轉檔完成」）
    def done_list(self, flt='all', q='', limit=500):
        self._table(); E = self.E; C = self.cfg()
        R = [dict(r) for r in E.db.q("SELECT * FROM slim_done ORDER BY id DESC LIMIT 5000")]
        for r in R:
            r['name'] = os.path.basename(r['dst'] or ''); sc = r['spot'] or r['ssim'] or 0; r['score'] = sc
            r['new_ok'] = bool(r['dst']) and os.path.exists(fcore.lp(r['dst']))
            m = E.db.one('SELECT dst, undone FROM moves WHERE id=?', (r['mid'],)) if r['mid'] else None
            r['orig_q'] = bool(m) and not m['undone'] and os.path.exists(fcore.lp(m['dst']))       # 原檔還在轉檔後隔離區
        act = [r for r in R if not r['undone']]
        F = {'all': lambda r: not r['undone'], 'warn': lambda r: not r['undone'] and r['score'] < C['target'] - 1e-9,
             'unseen': lambda r: not r['undone'] and not r['viewed'], 'undone': lambda r: r['undone']}
        L = [r for r in R if F.get(flt, F['all'])(r) and (not q or q.lower() in r['name'].lower())]
        osz = sum(r['osz'] or 0 for r in act); nsz = sum(r['nsz'] or 0 for r in act)
        return {'ok': True, 'rows': L[:limit], 'n': len(act), 'osz': osz, 'nsz': nsz, 'cfg': C,
                'warn': sum(1 for r in act if r['score'] < C['target'] - 1e-9), 'unseen': sum(1 for r in act if not r['viewed']),
                'undone': sum(1 for r in R if r['undone']), 'qn': sum(1 for r in act if r['orig_q'])}

    def seen(self, ids):
        self._table(); ids = [int(i) for i in ids or []]
        for i in ids: self.E.db.x('UPDATE slim_done SET viewed=? WHERE id=?', (time.time(), i))
        return {'ok': True}

    def revert(self, ids):
        """↩ 還原：原檔從轉檔後隔離區搬回原位；_h265 新檔搬進轉檔後隔離區（不刪，可以再復原）；分類跟回原檔."""
        self._table(); E = self.E; ok = 0; bad = []
        for i in [int(x) for x in ids or []]:
            r = E.db.one('SELECT * FROM slim_done WHERE id=? AND undone=0', (i,))
            if not r: continue
            r = dict(r)
            if not r['mid']: bad.append(f'{os.path.basename(r["src"])}：沒有搬移紀錄'); continue
            u = E.fc_undo([r['mid']])
            if not u.get('done'): bad.append(u.get('message') or '原檔搬不回來'); continue
            try:
                E.db.x("UPDATE OR IGNORE vc_tag SET fid=?, dst=CASE WHEN moved=1 THEN ? ELSE dst END WHERE fid=?", (r['fid'], r['src'], r['nfid']))
                E.db.x("UPDATE OR IGNORE vc_pet SET fid=? WHERE fid=?", (r['fid'], r['nfid']))
            except Exception: E.log.err('🗜 還原：分類跟回原檔')
            if r['nfid'] and os.path.exists(fcore.lp(r['dst'])):
                k, m = E.fc_quar(r['nfid'], '轉檔還原', os.path.basename(r['src']), fcore.CONV_QUAR_NAME)
                if not k: bad.append(f'{os.path.basename(r["dst"])}：新檔搬不進隔離區（{m}），兩個都在原資料夾')
            E.db.x('UPDATE slim_done SET undone=1 WHERE id=?', (i,)); ok += 1
        E.fc_kick()
        return {'ok': ok > 0 or not bad, 'message': f'↩ 還原了 {ok} 部（原檔搬回原位、_h265 放進轉檔後隔離區）' + (f'；{len(bad)} 部沒辦法：{bad[0]}' if bad else '')}

    # ---------------------------------------------------------------- 用哪個編碼器（先試顯示卡）
    def pick_enc(self):
        if self.enc: return self.enc
        ff = self.E.ff()[0]
        if not ff: return None
        for enc in ('hevc_nvenc', 'hevc_qsv', 'hevc_amf', 'libx265'):
            try:
                r = subprocess.run([ff, '-hide_banner', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=10', '-t', '0.5', '-c:v', enc, '-f', 'null', '-'],
                                   capture_output=True, timeout=30, creationflags=_nw(), stdin=subprocess.DEVNULL)
                if r.returncode == 0: self.enc = enc; self.E.log.w(f'🗜 影片瘦身：用 {enc}'); return enc
            except Exception: pass
        return None


    def vargs(self, enc, q, cap, v10):
        """跟 VS 一樣的壓縮參數；回傳幾種做法（前面的失敗就換下一種）：[{'pre','v','name'}]."""
        q = int(q); P = []
        if enc == 'hevc_nvenc':
            pf = ['-pix_fmt', 'p010le', '-profile:v', 'main10'] if v10 else ['-pix_fmt', 'yuv420p', '-profile:v', 'main']
            cp = ['-maxrate', str(cap), '-bufsize', str(cap * 2)] if cap else []
            P.append({'pre': ['-hwaccel', 'cuda'], 'name': 'NVENC', 'v': ['-c:v', 'hevc_nvenc', '-preset', 'p5', '-tune', 'hq', '-rc', 'vbr', '-cq', str(q), '-b:v', '0',
                      '-spatial_aq', '1', '-temporal_aq', '1', '-rc-lookahead', '32'] + cp + pf + ['-tag:v', 'hvc1']})
            P.append({'pre': [], 'name': 'NVENC（基本）', 'v': ['-c:v', 'hevc_nvenc', '-preset', 'p5', '-rc', 'vbr', '-cq', str(q), '-b:v', '0'] + cp + pf + ['-tag:v', 'hvc1']})
        elif enc == 'hevc_qsv':
            cp = ['-maxrate', str(cap), '-bufsize', str(cap * 2)] if cap else []
            P.append({'pre': [], 'name': 'Intel QSV', 'v': ['-c:v', 'hevc_qsv', '-preset', 'slower', '-global_quality', str(q)] + cp + ['-pix_fmt', 'p010le' if v10 else 'nv12', '-tag:v', 'hvc1']})
        elif enc == 'hevc_amf':
            P.append({'pre': [], 'name': 'AMD AMF', 'v': ['-c:v', 'hevc_amf', '-quality', 'quality', '-rc', 'cqp', '-qp_i', str(q), '-qp_p', str(q)] +
                      (['-maxrate', str(cap)] if cap else []) + ['-pix_fmt', 'yuv420p', '-tag:v', 'hvc1']})
        xp = 'log-level=error' + (f':vbv-maxrate={cap // 1000}:vbv-bufsize={cap * 2 // 1000}' if cap else '')
        P.append({'pre': [], 'name': 'CPU x265', 'v': ['-c:v', 'libx265', '-preset', 'medium', '-crf', str(q), '-pix_fmt', 'yuv420p10le' if v10 else 'yuv420p', '-x265-params', xp, '-tag:v', 'hvc1']})
        return P

    # ---------------------------------------------------------------- 讀影片資訊
    def probe(self, path):
        fp = self.E.ff()[1]
        rc, o, _e = fcore.run([fp, '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', fcore.lp(path)], 60)
        try: j = json.loads(o or '{}')
        except Exception: return {}
        S = j.get('streams') or []; v = next((s for s in S if s.get('codec_type') == 'video' and not (s.get('disposition') or {}).get('attached_pic')), None)
        fo = j.get('format') or {}
        if not v: return {}
        def fr(x):
            try: a, b = str(x or '0/1').split('/'); return float(a) / float(b) if float(b) else 0.0
            except Exception: return 0.0
        I = {'w': int(v.get('width') or 0), 'h': int(v.get('height') or 0), 'vcodec': str(v.get('codec_name') or '').lower(), 'pix': str(v.get('pix_fmt') or ''),
             'field': str(v.get('field_order') or ''), 'fps': fr(v.get('avg_frame_rate')) or fr(v.get('r_frame_rate')) or 30.0,
             'na': sum(1 for s in S if s.get('codec_type') == 'audio'), 'vstart': float(v.get('start_time') or 0)}
        try: I['vbr'] = int(v.get('bit_rate') or 0)
        except Exception: I['vbr'] = 0
        try: I['dur'] = float(fo.get('duration') or v.get('duration') or 0)
        except Exception: I['dur'] = 0.0
        try: I['size'] = int(fo.get('size') or 0) or os.path.getsize(fcore.lp(path))
        except Exception: I['size'] = 0
        return I

    def _vf(self, I):
        vf = []
        if I.get('field') in INTER: vf.append('bwdif=0')
        if (I.get('w', 0) % 2) or (I.get('h', 0) % 2): vf.append('scale=trunc(iw/2)*2:trunc(ih/2)*2')
        return vf

    def _cap(self, I):
        """位元率上限：🎯 自動＝原檔影像位元率的 95%（不會比原檔大）；固定畫質＝照編碼種類的比例（H.264 60%…）."""
        vb = src_vbr(I)
        return int(vb * 0.95) if vb else 0

    # ---------------------------------------------------------------- 比 SSIM
    def ssim_run(self, ins, lavfi):
        ff = self.E.ff()[0]; cmd = [ff, '-hide_banner', '-nostdin']
        for pre, f in ins: cmd += ['-threads', str(max(2, (os.cpu_count() or 4) * 3 // 4))] + list(pre) + ['-i', fcore.lp(f)]
        cmd += ['-lavfi', lavfi, '-f', 'null', '-']
        _rc, _o, e = fcore.run(cmd, 900); m = re.findall(r'All:([0-9.]+)', e or '')
        return float(m[-1]) if m else None

    def tq_search(self, src, I, S=None, J=None):
        """🎯 每一部先拿 5 段樣本試，找「SSIM 中間值 ≥ 目標」最省的 CQ（跟 VS tq_search 一樣）.
        回傳 {'q','ssim','pred','bps','ok','tried','sec','V'} 或 None."""
        t0 = time.time(); E = self.E; ff = E.ff()[0]; enc = self.pick_enc(); C = self.cfg(); target = C['target']
        dur = float(I.get('dur') or 0)
        if dur <= 0 or not enc: return None
        vf = self._vf(I); W, H = ssim_size(I.get('w'), I.get('h')); cap = self._cap(I); v10 = '10' in I.get('pix', '')
        seg = 2.0 if dur >= 20 else max(0.5, dur / 8)
        pts = [dur * f for f in (0.1, 0.3, 0.5, 0.7, 0.9)] if dur >= 12 else [max(0.0, dur / 2 - seg / 2)]
        fr = float(I.get('fps') or 30.0)
        pts = [(int(x * fr) + 0.5) / fr for x in pts]                          # 落在一格的正中間：原檔和樣本才會從同一格開始
        d = E.data / 'slim_tq'; d.mkdir(parents=True, exist_ok=True); cache = {}; tag = f'{os.getpid()}_{threading.get_ident()}'
        LF = ssim_lavfi(W, H, 'bwdif=0' in vf)

        def score(q):
            if q in cache: return cache[q][0]
            V = []; B = 0; n = 0
            for k, x in enumerate(pts):
                if (J or {}).get('cancel') or E.stop_all: raise InterruptedError
                out = str(d / f'tq_{tag}_{k}.mp4'); ok = False
                for pl in self.vargs(enc, q, cap, v10):
                    cmd = [ff, '-hide_banner', '-nostdin', '-loglevel', 'error', '-y'] + pl['pre'] + ['-ss', f'{x:.6f}', '-t', f'{seg:.3f}', '-i', fcore.lp(src),
                           '-map', '0:v:0', '-an', '-sn', '-dn'] + (['-vf', ','.join(vf)] if vf else []) + pl['v'] + ['-fps_mode', 'passthrough', out]
                    rc, _o, e = fcore.run(cmd, 900)
                    if rc != 0 and 'fps_mode' in (e or ''): i = cmd.index('-fps_mode'); cmd[i:i + 2] = ['-vsync', '0']; rc, _o, e = fcore.run(cmd, 900)
                    if rc == 0 and os.path.exists(out) and os.path.getsize(out) > 0: ok = True; break
                if not ok: continue
                B += os.path.getsize(out); n += 1
                v = self.ssim_run([(['-ss', f'{x:.6f}', '-t', f'{seg:.3f}'], src), ([], out)], LF)
                if v is not None: V.append(v)
                try: os.remove(out)
                except OSError: pass
            if not V: cache[q] = (None, 0, []); return None
            med = _med(V); bps = B * 8 / (seg * n) if n else 0; cache[q] = (med, bps, V)
            msg = f'🎯 試 CQ {q}：SSIM {med:.4f}（{", ".join(f"{v:.3f}" for v in V)}），影像約 {bps / 1e6:.2f} Mbps'
            E.log.w(f'{msg}　{os.path.basename(src)}')
            if S is not None: S['phase'] = f'🎯 找最省的設定：CQ {q} → {med:.3f}'; S.setdefault('tried', {})[str(q)] = round(med, 4)
            return med
        Hh = (E.cfg.get('slim_hist') or {}).get(I.get('vcodec', '')) or []
        start = int(sorted(Hh)[len(Hh) // 2]) if Hh else 28
        lo, hi, best = 18, 40, None; q = max(lo, min(hi, start)); it = 0
        while lo <= hi and it < 7:
            v = score(q); it += 1
            if v is not None and v >= target: best = q; lo = q + 1
            else: hi = q - 1
            q = (lo + hi) // 2
        if best is None: ok = False; best = min([k for k, x in cache.items() if x[0] is not None] or [18])
        else: ok = True
        med, bps, V = cache.get(best, (None, 0, []))
        if med is None: return None
        vb = src_vbr(I); ab = max(0.0, float(I.get('size') or 0) * 8 / dur - vb) if vb else 0.0
        pred = int((bps + ab) * dur / 8)
        if ok:
            HH = dict(E.cfg.get('slim_hist') or {}); kk = I.get('vcodec', ''); HH[kk] = (list(HH.get(kk) or []) + [best])[-30:]; E.cfg.set('slim_hist', HH)
        r = {'q': best, 'ssim': med, 'bps': bps, 'pred': pred, 'ok': ok, 'target': target, 'V': V, 'cap': cap, 'enc': enc,
             'tried': {k: x[0] for k, x in sorted(cache.items())}, 'sec': time.time() - t0, 'cmp': f'{W}×{H}'}
        E.log.w(f'🎯 畫質目標 {target:.3f}：{os.path.basename(src)} → 用 CQ {best}（樣本 SSIM {med:.4f}{"" if ok else "，最好也沒到目標"}），'
                f'預估整部 {fcore_fmt(pred)}（原檔 {fcore_fmt(I.get("size"))}），試了 {len(cache)} 種，花 {r["sec"]:.0f} 秒（{W}×{H} 比）')
        return r

    def spot_check(self, src, out, I, n=3, seg=2.0):
        """轉完抽 n 個地方各 2 秒比 SSIM 取中間值；先在中間那點試「不位移／照影像起點位移」挑最像的對齊方式，每點再前後差一格試（跟 VS 一樣）. 失敗回傳 0."""
        try:
            dur = float(I.get('dur') or 0); o = self.probe(out); ds = float(I.get('vstart') or 0); do = float(o.get('vstart') or 0)
            W, H = ssim_size(I.get('w'), I.get('h')); LF = ssim_lavfi(W, H, I.get('field') in INTER)
            fps = float(o.get('fps') or I.get('fps') or 30.0); fd = 1.0 / max(1.0, fps)

            def one(c, sh):
                return self.ssim_run([(['-ss', f'{max(0.0, c + sh):.6f}', '-t', f'{seg:.2f}'], src), (['-ss', f'{max(0.0, c):.6f}', '-t', f'{seg:.2f}'], out)], LF)
            pts = [dur * (k + 1) / (n + 1) for k in range(n)] if dur > seg * 3 else [0.0]
            pts = [(int(max(0.0, min(c, max(0.0, dur - seg))) * fps) + 0.5) / fps for c in pts]
            mid = pts[len(pts) // 2]; cands = []
            for sh in (0.0, round(ds - do, 6), round(do - ds, 6)):
                if all(abs(sh - x) > 0.01 for x, _v in cands): cands.append((sh, one(mid, sh)))
            good = [(a, b) for a, b in cands if b is not None]
            if not good: return 0.0
            sh, vmid = max(good, key=lambda x: x[1])
            for y in (sh - fd, sh + fd):
                x = one(mid, y)
                if x is not None and x > vmid: vmid = x
            V = []
            for c in pts:
                if c == mid: V.append(vmid); continue
                L_ = [x for x in (one(c, y) for y in (sh, sh - fd, sh + fd)) if x is not None]
                if L_: V.append(max(L_))
            v = _med(V) or 0.0
            self.E.log.w(f'🔍 抽查畫質：{os.path.basename(src)} → SSIM {v:.4f}（{", ".join(f"{x:.3f}" for x in V)}；位移 {sh:+.3f}s）'); return v
        except Exception: self.E.log.err('🗜 抽查畫質'); return 0.0

    # ---------------------------------------------------------------- 🧪 試轉（只找設定、不動檔案）
    def test(self, fid):
        if self.tst.get('run'): return {'ok': False, 'message': '已經在試了'}
        r = self.E.db.one("SELECT id, path FROM files WHERE id=? AND state=''", (int(fid),))
        if not r: return {'ok': False, 'message': '找不到這部'}
        self.tst.clear(); self.tst.update(run=True, fid=int(fid), name=os.path.basename(r['path']), phase='準備中…', tried={})
        def go():
            S = self.tst
            try:
                I = self.probe(r['path'])
                if not I: raise RuntimeError('讀不到影片資訊')
                tq = self.tq_search(r['path'], I, S, S)
                if not tq: raise RuntimeError('樣本都轉不出來')
                S.update(res={'q': tq['q'], 'ssim': tq['ssim'], 'ok': tq['ok'], 'pred': tq['pred'], 'osz': I.get('size'), 'sec': tq['sec'], 'cmp': tq['cmp'],
                              'tried': {str(k): v for k, v in tq['tried'].items()}, 'enc': tq['enc'], 'V': tq['V']}, phase='')
            except InterruptedError: S['err'] = '停止了'
            except Exception as ex: S['err'] = str(ex); self.E.log.err('🧪 試轉')
            finally: S['run'] = False
        threading.Thread(target=go, name='VSlimTest', daemon=True).start()
        return {'ok': True, 'message': '🧪 試轉中：5 段樣本找最省、畫質還在 0.985 以上的設定（大約 1～3 分鐘，檔案不會動）'}

    # ---------------------------------------------------------------- 開始（背景，一部一部來）
    def start(self, ids, q=None):
        if self.st.get('run'): return {'ok': False, 'message': '已經在轉了'}
        ids = [int(x) for x in ids or []]
        if not ids: return {'ok': False, 'message': '沒有選影片'}
        q = q if q in QUAL else (self.E.cfg.get('slim_q') or 'auto'); self.E.cfg.set('slim_q', q)
        self.st.clear(); self.st.update(run=True, n=0, total=len(ids), ok=0, bad=0, keep=0, saved=0, cur='', pct=0, cancel=False, err=[], q=q, phase='', done=[])
        threading.Thread(target=self._job, args=(ids, q), name='VSlim', daemon=True).start()
        return {'ok': True, 'message': f'🗜 開始瘦身 {len(ids):,} 部（' + ('🎯 每部先找最省、畫質 ≥ 0.985 的設定' if q == 'auto' else QUAL[q][0]) + '；背景做，可以隨時停）'}

    def _job(self, ids, q):
        E = self.E; S = self.st; t = E.task('op', '🗜 影片瘦身')
        try:
            enc = self.pick_enc()
            if not enc: raise RuntimeError('找不到可以用的 H.265 編碼器（FFmpeg 太舊？）')
            S['enc'] = enc
            for fid in ids:
                if S.get('cancel') or E.stop_all: break
                while E.quiet_now() and not (S.get('cancel') or E.stop_all):                # 🌙 設了「這段時間不跑背景」：等時間到再轉（V0.1.82）
                    S['cur'] = f"🌙 等到 {int(E.cfg.get('quiet_to') or 0)} 點再繼續"; time.sleep(30)
                while not (S.get('cancel') or E.stop_all):
                    _h = getattr(__import__('sys').modules.get('fc_core'), 'EXT_HOLD', {}).get('enc')
                    try: _w = str(_h() or '') if _h else ''
                    except Exception: _w = ''
                    if not _w: break
                    S['cur'] = f'⏳ {_w}'; time.sleep(10)
                if S.get('cancel') or E.stop_all: break
                S['n'] += 1; S['tried'] = {}
                try:
                    ok, msg = self._one(fid, enc, q)
                    if ok: S['ok'] += 1
                    elif msg.startswith('KEEP:'): S['keep'] += 1; S['err'].append(msg[5:])
                    else: S['bad'] += 1; S['err'].append(msg)
                except InterruptedError: break
                except Exception as ex: S['bad'] += 1; S['err'].append(str(ex)); E.log.err('🗜 影片瘦身')
                S['err'] = S['err'][-50:]
                t['msg'] = f"{S['n']}／{S['total']}・省了 {fcore_fmt(S['saved'])}"
            msg = (f"瘦身好 {S['ok']:,} 部、省了 {fcore_fmt(S['saved'])}" + (f"，{S['keep']} 部畫質／大小不划算、保留原檔" if S['keep'] else '') +
                   (f"，{S['bad']} 部沒成功（原檔沒動）" if S['bad'] else '') + ('（停止）' if S.get('cancel') else ''))
            E.done(t, 'done', msg); E.oplog('影片瘦身', msg); S['msg'] = msg
        except Exception as ex: E.log.err('🗜 影片瘦身'); E.done(t, 'fail', str(ex)); S['msg'] = str(ex)
        finally: S['run'] = False; S['cur'] = ''; S['src'] = ''; S['phase'] = ''; E.fc_kick()

    def _encode(self, src, tmp, I, plans, dur, label):
        """整部轉；照順序試幾種做法. 回傳 (成功, 錯誤訊息)."""
        E = self.E; S = self.st; ff = E.ff()[0]; vf = self._vf(I); err = ''
        for pl in plans:
            S['phase'] = f'{label}（{pl["name"]}）'; S['pct'] = 0
            cmd = [ff, '-hide_banner', '-v', 'error', '-y', '-progress', 'pipe:1', '-nostats'] + pl['pre'] + ['-i', fcore.lp(src), '-map', '0:v:0', '-map', '0:a?',
                   '-map_metadata', '0', '-sn', '-dn', '-movflags', '+faststart+use_metadata_tags', '-max_muxing_queue_size', '4096'] + \
                  (['-vf', ','.join(vf)] if vf else []) + pl['v'] + ['-c:a', 'aac', '-b:a', '160k', fcore.lp(tmp)]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=_nw(), stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace')
            eb = []
            th = threading.Thread(target=lambda: eb.append(p.stderr.read()), daemon=True); th.start()
            try:
                for line in p.stdout:
                    if S.get('cancel') or E.stop_all: p.kill(); raise InterruptedError
                    m = re.match(r'out_time_(?:us|ms)=(\d+)', line)
                    if m and dur: S['pct'] = min(99, int(int(m.group(1)) / 1e6 / dur * 100))
                p.wait(timeout=60); th.join(5); err = ((eb[0] if eb else '') or '')[-300:]
            except InterruptedError:
                _rm(tmp); raise
            except Exception as ex:
                p.kill(); err = str(ex)
            if p.returncode == 0 and os.path.exists(fcore.lp(tmp)) and os.path.getsize(fcore.lp(tmp)) > 0: return True, ''
            _rm(tmp); E.log.w(f'🗜 轉檔用 {pl["name"]} 失敗：{src}：{err.strip()[:200]}')
        return False, err

    def _one(self, fid, enc, q):
        E = self.E; S = self.st; C = self.cfg(); self._table()
        r = E.db.one("SELECT * FROM files WHERE id=? AND state=''", (fid,))
        if not r: return False, f'#{fid}：找不到（可能已經搬走）'
        r = dict(r); src = r['path']; S['cur'] = os.path.basename(src); S['src'] = src; S['pct'] = 0; S['phase'] = '讀影片資訊'
        if not os.path.exists(fcore.lp(src)): return False, f'{src}：檔案不見了'
        _x = getattr(__import__('sys').modules.get('fc_core'), 'EXT_HOLD', {}).get('conv')   # 嵌在 SortCut 裡：VS 轉檔已經排了這部就不重複轉
        if _x:
            try: _w = str(_x(src) or '')
            except Exception: _w = ''
            if _w: return False, f'KEEP:{os.path.basename(src)}：{_w}'
        dst = os.path.splitext(src)[0] + SUFFIX + '.mp4'
        if os.path.exists(fcore.lp(dst)): return False, f'{dst}：已經有了'
        try:
            free = __import__('shutil').disk_usage(fcore.lp(os.path.dirname(src))).free
            if free < r['size'] + 1e9: return False, f'{src}：硬碟空間不夠（剩 {fcore_fmt(free)}）'
        except OSError: pass
        I = self.probe(src) or {}
        I.setdefault('size', r['size']); I['size'] = I.get('size') or r['size']
        if not I.get('dur'): I['dur'] = float(r['dur'] or 0)
        if not I.get('w'): I.update(w=r['w'] or 0, h=r['h'] or 0)
        dur = float(I.get('dur') or 0); v10 = '10' in I.get('pix', ''); tmp = dst + '.part.mp4'
        tq = None; how = q
        if q == 'auto' and dur > 0:
            S['phase'] = '🎯 找最省的設定中…'
            tq = self.tq_search(src, I, S, S)
        if tq and not tq['ok'] and tq['ssim'] < C['floor']:                      # 樣本最好（CQ 18）都到不了底線：整部轉也一樣，直接保留原檔（省時間）
            return False, f'KEEP:{os.path.basename(src)}：樣本最好只到 SSIM {tq["ssim"]:.3f}（CQ {tq["q"]}），到不了底線 {C["floor"]}，不轉、原檔不動'
        if tq:
            qq = int(tq['q']); cap = tq['cap']; how = 'auto'
        else:
            _n, crf, cq = QUAL.get(q if q != 'auto' else 'std', QUAL['std']); qq = crf if enc == 'libx265' else cq; how = q if q != 'auto' else 'std'
            vb = src_vbr(I); cap = int(max(300000, vb * CAP_K.get(I.get('vcodec', ''), 0.5))) if vb else 0
        ok, err = self._encode(src, tmp, I, self.vargs(enc, qq, cap, v10), dur, f'轉檔 CQ {qq}')
        if not ok: return False, f'{src}：轉檔失敗 {err.strip()[:200]}'

        def check_len():
            nd = float((self.probe(tmp) or {}).get('dur') or 0)
            if dur and (not nd or abs(nd - dur) > max(2.0, dur * 0.01)): return None
            return nd or dur
        nd = check_len()
        if nd is None: _rm(tmp); return False, f'{src}：轉出來的長度不對，原檔沒動'
        # 🔍 抽查畫質（低於底線就 CQ 降 3 重轉，最多 2 次；跟 VS 一樣）
        spot = None; tries = 0
        while True:
            S['phase'] = f'🔍 抽查畫質中（CQ {qq}）'; S['pct'] = 100
            spot = self.spot_check(src, tmp, I) or None
            if spot is None or spot >= C['floor'] or tries >= 2 or how != 'auto' or qq <= 18: break
            tries += 1; old = qq; qq = max(18, qq - 3); _rm(tmp)
            E.log.w(f'🔍 抽查沒過：{os.path.basename(src)} CQ {old} → SSIM {spot:.4f} < 底線 {C["floor"]}，改用 CQ {qq} 重轉（第 {tries} 次）')
            ok, err = self._encode(src, tmp, I, self.vargs(enc, qq, cap, v10), dur, f'重轉 CQ {qq}（第 {tries} 次）')
            if not ok: return False, f'{src}：抽查沒過、重轉也失敗，原檔沒動'
            nd = check_len()
            if nd is None: _rm(tmp); return False, f'{src}：重轉的長度不對，原檔沒動'
        if spot is not None and (spot < ABORT or (how == 'auto' and spot < C['floor'])):
            _rm(tmp); return False, f'KEEP:{os.path.basename(src)}：畫質到不了底線（CQ {qq} 還是 SSIM {spot:.3f} < {C["floor"] if how == "auto" else ABORT}），不用轉好的、原檔不動'
        ns = os.path.getsize(fcore.lp(tmp))
        if ns <= 0 or ns >= r['size'] * 0.92:
            _rm(tmp); return False, f'KEEP:{os.path.basename(src)}：轉好 {fcore_fmt(ns)} 沒有變小（原檔 {fcore_fmt(r["size"])}，{ns * 100 // max(1, r["size"])}%），保留原檔'
        try: os.utime(fcore.lp(tmp), (r['mtime'], r['mtime']))
        except OSError: pass
        os.replace(fcore.lp(tmp), fcore.lp(dst))
        ok, m = E.fc_quar(fid, '轉檔原檔', os.path.basename(dst), fcore.CONV_QUAR_NAME)   # 原檔留著，放「轉檔後隔離區」（跟一般隔離區分開）（V0.4.61）
        if not ok: _rm(dst); return False, f'{src}：原檔搬不到隔離區（{m}），新檔已刪、原檔沒動'
        mid = None
        try: mid = (E.db.one('SELECT MAX(id) FROM moves WHERE fid=?', (fid,)) or [None])[0]
        except Exception: pass
        keep = ('taken', 'date_src', 'name_date', 'make', 'model', 'software', 'gps', 'lat', 'lon', 'src', 'w', 'h', 'mp', 'motion')
        try:
            E.db.x(E.UPSERT, (dst, r['root'], ns, r['mtime'], '.mp4', 'video', time.time()))
            E.db.x(f"UPDATE files SET {', '.join(k + '=?' for k in keep)}, dur=?, vcodec='hevc', meta=1, health='ok' WHERE path=?", [r.get(k) for k in keep] + [nd or dur, dst])
        except Exception: E.log.err('🗜 新檔寫進資料庫')
        nf = None
        try:                                                                          # 🎞 分類、電腦看過的內容跟著新檔（V0.4.61：以前瘦身後新檔變成沒分類）
            nf = E.db.one("SELECT id FROM files WHERE path=?", (dst,))
            if nf and nf[0] != fid:
                E.db.x("UPDATE OR IGNORE vc_tag SET fid=?, dst=CASE WHEN moved=1 THEN ? ELSE dst END WHERE fid=?", (nf[0], dst, fid))
                E.db.x("UPDATE OR IGNORE vc_pet SET fid=? WHERE fid=?", (nf[0], fid))
        except Exception: E.log.err('🗜 分類跟著新檔')
        _sl = getattr(__import__('sys').modules.get('fc_core'), 'EXT_HOLD', {}).get('slimmed')   # 嵌在 SortCut 裡：VS 那筆接手新檔
        if _sl:
            try: _sl(src, dst, int(r['size'] or 0), int(ns or 0))
            except Exception: pass
        note = (f'🎯 自動選 CQ {tq["q"]}（樣本 SSIM {tq["ssim"]:.3f}{"" if tq["ok"] else "，沒到目標"}，找了 {tq["sec"]:.0f} 秒）' if tq else f'固定 {QUAL.get(how, QUAL["std"])[0]}') + \
               (f'；抽查沒過重轉 {tries} 次 → CQ {qq}' if tries else '')
        try:
            E.db.x('INSERT INTO slim_done(t,fid,nfid,mid,src,dst,osz,nsz,q,ssim,spot,how,enc,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (time.time(), fid, nf[0] if nf else None, mid, src, dst, r['size'], ns, qq, (tq or {}).get('ssim') if not tries else None, spot, how, enc, note))
        except Exception: E.log.err('🗜 瘦身紀錄')
        S['saved'] += r['size'] - ns; S['pct'] = 100
        E.log.w(f'🗜 {src}：{fcore_fmt(r["size"])} → {fcore_fmt(ns)}（CQ {qq}，SSIM {spot or (tq or {}).get("ssim") or 0:.3f}）'); return True, ''


def _rm(p):
    """只刪「這次自己做出來、還沒用的」暫存檔／新檔."""
    try: os.remove(fcore.lp(p))
    except OSError: pass


def fcore_fmt(b):
    b = float(b or 0)
    return f'{b / 1e9:.2f} GB' if b >= 1e9 else f'{b / 1e6:.0f} MB'

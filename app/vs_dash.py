"""📊 三邊各自的一頁總覽（V0.5.68）：SortCut（10 秒剪輯）／FileCompare（整理）／H265（瘦身）.

每個都是「一次查完」：幾個 SQL 合在一起、算好放 20 秒快取（手機、電腦一直刷新也不會一直查資料庫）。
沒有 Qt，電腦版和手機（網頁）都叫這裡。數字的意思：
- n＝部數、b＝位元組、today＝今天 +幾、d7＝最近 7 天每天幾個（舊→新）
"""
import os
import shutil
import time

_C = {}


_RUN = {}


def _cache(key, fn, ttl=20, wait=4.0):
    """V0.5.92 電腦很忙時不讓畫面一直等：最多等 4 秒，算不完就先給上一次的數字（標「舊的」），算好了下次就是新的."""
    import threading
    c = _C.get(key)
    if c and time.time() - c[0] < ttl: return c[1]
    th = _RUN.get(key)
    if th is None or not th.is_alive():
        def run():
            try: v = fn(); _C[key] = (time.time(), v)
            except Exception: pass
        th = _RUN[key] = threading.Thread(target=run, name=f'Dash-{key}', daemon=True); th.start()
    th.join(wait)
    c = _C.get(key)
    if c:
        v = c[1]
        if th.is_alive() and isinstance(v, dict): v = dict(v); v['stale'] = round(time.time() - c[0]); v['busy'] = '⏳ 電腦很忙，先顯示上一次的數字（背景限流中）'
        return v
    return {'ok': False, 'busy': 1, 'message': '⏳ 電腦很忙（背景限流中），總覽數字還在算，馬上自動再試…'}


def _days(q, a=()):
    """最近 7 天（含今天）每天幾個：[(MM-DD, 數字)]，沒有的補 0."""
    have = {str(r[0]): float(r[1] or 0) for r in q}
    out = []
    for i in range(6, -1, -1):
        d = time.strftime('%Y-%m-%d', time.localtime(time.time() - i * 86400))
        out.append([d[5:], have.get(d, 0)])
    return out


def _disk(paths):
    """這幾個資料夾在哪幾顆硬碟：每顆的剩下／全部."""
    seen = {}; out = []
    for p in paths:
        d = os.path.splitdrive(str(p))[0] or str(p)[:1]
        if not d or d in seen: continue
        seen[d] = 1
        try: u = shutil.disk_usage(d + os.sep if d.endswith(':') else str(p)); out.append({'d': d.upper(), 'free': u.free, 'total': u.total})
        except Exception: pass
    return out




def _today0():
    t = time.localtime(); return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))


# ------------------------------------------------------------------ 🎬 SortCut（10 秒一張、分級、初剪）
def vs(E):
    def f():
        db = E.db; t0 = _today0(); w7 = t0 - 6 * 86400
        r = db.one("SELECT COUNT(*), TOTAL(size), TOTAL(grade!=''), TOTAL(th_state=2), TOTAL(cut_n>0), TOTAL(cut_n), TOTAL(fav>0), TOTAL(grade='F'), TOTAL(CASE WHEN grade='F' THEN size ELSE 0 END) "
                   "FROM files WHERE missing=0")
        n, b, graded, th, cutf, cuts, fav, fn_, fb = [float(x or 0) for x in r]
        G = {k: 0 for k in ('S', 'A', 'E', 'F')}
        for g, c in db.q("SELECT grade, COUNT(*) FROM files WHERE missing=0 AND grade!='' GROUP BY grade"):
            if g in G: G[g] = int(c)
        today = int((db.one("SELECT COUNT(*) FROM files WHERE grade!='' AND grade_t>=?", (t0,)) or [0])[0] or 0)
        cut_today = int((db.one("SELECT COUNT(*) FROM cuts WHERE state=2 AND t>=?", (t0,)) or [0])[0] or 0)
        d7 = _days(db.q("SELECT date(grade_t,'unixepoch','localtime') d, COUNT(*) FROM files WHERE grade!='' AND grade_t>=? GROUP BY d", (w7,)))
        R = []
        for root in list(E.cfg.get('roots') or []):
            rr = db.one("SELECT COUNT(*), TOTAL(grade!=''), TOTAL(size) FROM files WHERE missing=0 AND root=?", (str(root),)) or (0, 0, 0)
            R.append({'name': str(root), 'n': int(rr[0] or 0), 'done': int(rr[1] or 0), 'b': float(rr[2] or 0)})
        R.sort(key=lambda x: -x['n'])
        return {'ok': True, 'kind': 'vs', 'n': int(n), 'b': b, 'graded': int(graded), 'th': int(th), 'cutf': int(cutf), 'cuts': int(cuts), 'fav': int(fav),
                'F_n': int(fn_), 'F_b': fb, 'G': G, 'today': today, 'cut_today': cut_today, 'd7': d7, 'roots': R[:6],
                'disk': _disk([x['name'] for x in R]), 't': time.time()}
    return _cache('vs', f)


# ------------------------------------------------------------------ 🗜 H265（轉檔、瘦身、SSIM）
def h265(E, FE=None):
    def f():
        db = E.db; t0 = _today0(); w7 = t0 - 6 * 86400; hv = ','.join(getattr(E, 'HEVC', ("'hevc'", "'h265'")))
        C = {'hevc': [0, 0.0], 'h264': [0, 0.0], 'other': [0, 0.0], 'unk': [0, 0.0]}
        for k, c, s in db.q(f"SELECT CASE WHEN lower(vcodec) IN ({hv}) THEN 'hevc' WHEN lower(vcodec) IN ('h264','avc','avc1') THEN 'h264' "
                            f"WHEN vcodec='' OR vcodec IS NULL THEN 'unk' ELSE 'other' END k, COUNT(*), TOTAL(size) FROM files WHERE missing=0 GROUP BY k"):
            C[k] = [int(c), float(s or 0)]
        cv = db.one("SELECT COUNT(*), TOTAL(cv_osz), TOTAL(cv_nsz), AVG(NULLIF(cv_ssim,0)) FROM files WHERE cv_state=3 AND cv_osz>0") or (0, 0, 0, None)
        q = db.one("SELECT COUNT(*), TOTAL(size) FROM files WHERE cv_state=1") or (0, 0)
        bad = int((db.one("SELECT COUNT(*) FROM files WHERE cv_state IN (4,5)") or [0])[0] or 0)
        try: W_, A_ = E.conv_where(kind='all'); cand = db.one(f"SELECT COUNT(*), TOTAL(size) FROM files WHERE {W_}", A_) or (0, 0)
        except Exception: cand = (C['h264'][0] + C['other'][0], C['h264'][1] + C['other'][1])
        osz, nsz = float(cv[1] or 0), float(cv[2] or 0); ratio = (nsz / osz) if osz else 0.45
        today = db.one("SELECT COUNT(*), TOTAL(MAX(cv_osz-cv_nsz,0)) FROM files WHERE cv_state=3 AND cv_t>=?", (t0,)) or (0, 0)
        d7 = _days(db.q("SELECT date(cv_t,'unixepoch','localtime') d, TOTAL(MAX(cv_osz-cv_nsz,0)) FROM files WHERE cv_state=3 AND cv_t>=? GROUP BY d", (w7,)))
        sl = {'n': 0, 'save': 0.0, 'today': 0}
        if FE is not None:
            try:
                r = FE.db.one("SELECT COUNT(*), TOTAL(MAX(osz-nsz,0)), AVG(NULLIF(ssim,0)) FROM slim_done WHERE undone=0") or (0, 0, None)
                sl = {'n': int(r[0] or 0), 'save': float(r[1] or 0), 'ssim': r[2], 'today': int((FE.db.one("SELECT COUNT(*) FROM slim_done WHERE undone=0 AND t>=?", (t0,)) or [0])[0] or 0)}
            except Exception: pass
        return {'ok': True, 'kind': 'h265', 'codec': C, 'done': int(cv[0] or 0), 'osz': osz, 'nsz': nsz, 'saved': max(0.0, osz - nsz), 'ssim': cv[3],
                'queue': int(q[0] or 0), 'queue_b': float(q[1] or 0), 'running': len(getattr(E, 'cv_active', None) or {}), 'bad': bad,
                'cand': int(cand[0] or 0), 'cand_b': float(cand[1] or 0), 'est_save': float(cand[1] or 0) * max(0.0, 1 - ratio), 'ratio': ratio,
                'today': int(today[0] or 0), 'today_save': float(today[1] or 0), 'd7': d7, 'slim': sl, 'disk': _disk(list(E.cfg.get('roots') or [])), 't': time.time()}
    return _cache('h265', f)


# ------------------------------------------------------------------ 🗂 FileCompare（整理、16 格分類）
def fc(FE):
    def f():
        C = FE.fc_counts() if hasattr(FE, 'fc_counts') else {}
        db = FE.db; t0 = _today0(); w7 = t0 - 6 * 86400
        cats = [{'name': str(r[0]), 'color': str(r[1] or ''), 'n': int(r[2] or 0), 'b': float(r[3] or 0), 'wait': int(r[4] or 0)} for r in db.q(
            "SELECT c.name, c.color, COUNT(t.fid), TOTAL(f.size), TOTAL(t.moved=0) FROM vc_cat c LEFT JOIN vc_tag t ON t.cat=c.id LEFT JOIN files f ON f.id=t.fid "
            "GROUP BY c.id ORDER BY c.ord, c.id")]
        tagged = int((db.one("SELECT COUNT(*) FROM vc_tag t JOIN files f ON f.id=t.fid WHERE f.kind='video'") or [0])[0] or 0)
        tag_b = float((db.one("SELECT TOTAL(f.size) FROM vc_tag t JOIN files f ON f.id=t.fid WHERE f.kind='video'") or [0])[0] or 0)   # V0.5.88 也看大小
        vid_b = float((db.one("SELECT TOTAL(size) FROM files WHERE kind='video'") or [0])[0] or 0)
        today = int((db.one("SELECT COUNT(*) FROM vc_tag WHERE t>=?", (t0,)) or [0])[0] or 0)
        d7 = _days(db.q("SELECT date(t,'unixepoch','localtime') d, COUNT(*) FROM vc_tag WHERE t>=? GROUP BY d", (w7,)))
        roots = list(FE.fc_list('roots')) if hasattr(FE, 'fc_list') else []
        try:
            import vs_fcdel as FD
            dl = FD.info(FE); dl = {'n': dl['n'], 'b': dl['bytes'], 'wait': dl['wait']}
        except Exception: dl = {'n': 0, 'b': 0, 'wait': 0}
        keys = ('files', 'bytes', 'photos', 'videos', 'dup_groups', 'dup_files', 'dup_bytes', 'broken', 'partial', 'zero', 'quar_n', 'quar_bytes', 'meta_done', 'media',
                'hash_done', 'hash_total', 'health_done', 'rep_ok')
        packs = []
        if not roots:
            try:
                import vs_fcpack
                packs = [{'X': x, 'pc': j.get('pc'), 't': j.get('t'), 'files': j.get('files'), 'tagged': j.get('tagged')} for x, j in vs_fcpack.find()]
            except Exception: pass
        return {'ok': True, 'kind': 'fc', 'packs': packs, **{k: C.get(k, 0) for k in keys}, 'cats': cats, 'tagged': tagged, 'tag_b': tag_b, 'vid_b': vid_b, 'today': today, 'd7': d7,
                'roots': roots, 'disk': _disk(roots), 'del': dl, 't': time.time()}
    return _cache('fc', f)

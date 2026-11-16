"""📦 資料夾包＋🧩 相關的排一起（V0.2.14）：讓四萬多部影片可以「一組一組」審，不用一部一部。
- 資料夾包：你以前自己整理過、有取名字的資料夾（例如 2020-日本旅遊）→ 整包一起看、整包放到「已篩選」（保留資料夾結構）
- 排一起：照資料夾包、照類型（檔名樣式＋手機＋直橫＋解析度）、照同一段時間
不准 import Qt；只用 V0.1.21 啟動器有的模組（見 rel.py 檢查）。"""
import os, re, time
import fc_fcore as fcore

KEEP_CAT = '已篩選'

# 不算「有取名字」的資料夾（手機、程式自動建的；全部小寫比對）
GENERIC = {
    'dcim', 'camera', 'cameras', 'movies', 'movie', 'video', 'videos', 'vid', 'vids', 'clip', 'clips', 'media', 'files', 'data', 'temp', 'tmp', 'misc',
    'photo', 'photos', 'pictures', 'picture', 'pics', 'images', 'image', 'download', 'downloads', 'screenrecorder', 'screenrecord', 'screenrecords',
    'screen recordings', 'screenshots', 'screenshot', 'whatsapp', 'whatsapp video', 'whatsapp videos', 'whatsapp animated gifs', 'telegram', 'telegram video',
    'line', 'line_video', 'wechat', 'weixin', 'micromsg', 'tencent', 'snapchat', 'instagram', 'facebook', 'messenger', 'tiktok', 'douyin', 'capcut', 'kwai',
    'new folder', 'new folder (2)', 'untitled', 'others', 'other', 'sdcard', 'storage', 'emulated', 'internal storage', 'phone', 'android', 'private', 'my videos',
    'gopro', 'dji', 'dji album', 'insta360', 'ydxj', 'normal', 'event', 'parking', 'front', 'rear', 'mp4', 'mov', 'raw', 'edited', 'export', 'exports', 'output',
    '影片', '視頻', '视频', '相機', '相机', '照片', '相片', '圖片', '图片', '下載', '下载', '螢幕錄影', '屏幕录制', '录屏', '截圖', '截图', '新資料夾', '新增資料夾',
    '新建文件夹', '未命名', '其他', '其它', '內部儲存空間', '我的影片', '相簿', '相册', '影音', '錄影', '录像', '行車紀錄器', '行车记录仪', 'filecompare_分類',
    'filecompare_問題影片', '_filecompare_待確認', 'found.000', 'lost.dir', '$recycle.bin', 'system volume information',
}
GENERIC_RE = re.compile(r'^(\d{3}[a-z_]{4,8}|\d{3}media|\d{3}gopro|\d{3}_?fuji|\d{3}canon|\d{3}nikon|\d{3}_panA|recup_dir\.\d+|dir\d+|file\d+|folder\d+|part\d+|disk\d*|drive\d*|\.\w+)$', re.I)
# 「整台手機／整顆硬碟倒出來」的資料夾：不當成一包（太雜），裡面更深的有名字資料夾才是包
DUMP = ('backup', 'back up', '備份', '備分', '备份', '手機', '手机', '硬碟', '硬盘', '複製', '复制', '待整理', '整理', '匯出', '导出', 'xiaomi', 'samsung', 'iphone',
        'ipad', 'huawei', 'oppo', 'vivo', 'asus', 'sony', 'pixel', 'gigabyte', 'sd卡', 'sdcard', '記憶卡', '存储卡', '電腦', '电脑', '雜', '杂', '全部', '所有', 'recup', 'photorec',
        '資料', '资料', '檔案', '档案', 'recovered', 'recovery', '救援', '還原', '恢复', 'disk', 'drive', 'old', 'misc', 'dump', 'all ')
WORD_RE = re.compile(r'[^\W\d_]', re.U)


def rootnorm(r):
    p = os.path.normpath(str(r or ''))
    d, rest = os.path.splitdrive(p)
    if d and rest in ('', '\\', '/'): return d + os.sep                               # R:\
    return p.rstrip('\\/') or p


def is_named(name):
    """有取名字的資料夾：去掉數字、日期、符號後還有字，而且不是手機／程式自動建的那種名字."""
    n = (name or '').strip(); lo = n.lower()
    if not n or lo in GENERIC or GENERIC_RE.match(n): return False
    rest = re.sub(r'[\d\s_\-.,()\[\]{}#~!@&+=\'"]+', '', n)
    if not WORD_RE.search(rest): return False                                      # 只有數字／日期
    if rest.lower() in GENERIC or re.sub(r'[\d_\-. ]+', ' ', lo).strip() in GENERIC: return False   # Camera2、DCIM_1、Video 2…
    cjk = sum(1 for ch in rest if ord(ch) > 0x2E80)
    return cjk >= 1 or len(rest) >= 3


def is_dump(name):
    lo = (name or '').lower()
    return any(w in lo for w in DUMP)


def has_date(name):
    return bool(re.search(r'(19|20)\d{2}([\-._ /年]?\d{1,2})?', name or ''))


def name_sig(fname):
    """檔名樣式：VID_20200101_123456.mp4 → VID_#_#；Screenrecorder-2021-… → Screenrecorder-#."""
    b = os.path.splitext(os.path.basename(fname or ''))[0]
    s = re.sub(r'\d+', '#', b); s = re.sub(r'(#[\-_. ]?)+#', '#', s); s = re.sub(r'\(#\)$', '', s).strip(' _-.')
    if len(s) > 24: s = s[:24]
    return s or '#'


FRIENDLY = [(re.compile(r'^(screen|screenrecord|螢幕|录屏|屏幕)', re.I), '📱 螢幕錄影'), (re.compile(r'^VID-#-WA', re.I), '💬 WhatsApp'),
            (re.compile(r'^(line_|LINE)', re.I), '💬 LINE'), (re.compile(r'^(YDXJ|NORM|EVNT|PARK|REC_|EMER|MOVI#)', re.I), '🚗 行車紀錄器'),
            (re.compile(r'^(G[HXLP]#|GOPR|GP#)', re.I), '🎥 GoPro'), (re.compile(r'^DJI', re.I), '🚁 DJI'), (re.compile(r'^(lv_#|capcut|剪映)', re.I), '✂ CapCut／剪映'),
            (re.compile(r'^(mmexport|wx_camera|微信)', re.I), '💬 微信'), (re.compile(r'^(telegram|tg_)', re.I), '💬 Telegram'), (re.compile(r'^(trim|TRIM)', re.I), '✂ 剪過的'),
            (re.compile(r'^(VID_#|VID#|IMG_#|PXL_#|MVIMG|#_#|#)$', re.I), '📷 手機相機'), (re.compile(r'^(MOV_|C#|MAH#|DSC|MVI_|P#)', re.I), '📸 相機')]
FRIENDLY_DIR = {'whatsapp video': '💬 WhatsApp', 'whatsapp': '💬 WhatsApp', 'line': '💬 LINE', 'line_video': '💬 LINE', 'telegram': '💬 Telegram', 'telegram video': '💬 Telegram',
                'screenrecorder': '📱 螢幕錄影', 'screenrecord': '📱 螢幕錄影', 'screen recordings': '📱 螢幕錄影', '螢幕錄影': '📱 螢幕錄影', 'wechat': '💬 微信', 'weixin': '💬 微信',
                'micromsg': '💬 微信', 'messenger': '💬 Messenger', 'instagram': '📸 Instagram', 'tiktok': '🎵 抖音／TikTok', 'douyin': '🎵 抖音／TikTok', 'capcut': '✂ CapCut／剪映'}


def friendly(path, sig):
    """影片從哪來（看得懂的名字）：先看資料夾（WhatsApp Video、Screenrecorder…），再看檔名樣式."""
    for part in reversed(re.split(r'[\\/]', os.path.dirname(path or ''))[-3:]):
        f = FRIENDLY_DIR.get(part.lower())
        if f: return f
    for rx, nm in FRIENDLY:
        if rx.search(sig or ''): return nm
    return ''


def res_bucket(w, h):
    w, h = int(w or 0), int(h or 0)
    if not w or not h: return ''
    o = '直' if h > w else ('方' if h == w else '橫')
    s = min(w, h)
    q = '4K' if s >= 2000 else '1440p' if s >= 1400 else '1080p' if s >= 1000 else '720p' if s >= 700 else '480p' if s >= 460 else '小'
    return f'{o}{q}'


class VGroup:
    def __init__(self, E):
        self.E = E; self._pk = {}; self._cache = (0, None); self._mark = {}; self._kids = {}
        try:                                                                      # vc_tag.sub：整包搬時保留「包名＼子資料夾」
            have = {r[1] for r in E.db.q('PRAGMA table_info(vc_tag)')}
            if have and 'sub' not in have: E.db.x("ALTER TABLE vc_tag ADD COLUMN sub TEXT DEFAULT ''")
            if have and 'auto' not in have: E.db.x("ALTER TABLE vc_tag ADD COLUMN auto INTEGER DEFAULT 0")   # 1＝程式自動標的（分類過的檔，它的重複副本 → Delete；V0.2.66）
            E.db.x('CREATE TABLE IF NOT EXISTS vg_skip(path TEXT PRIMARY KEY, t REAL)')
            E.db.x('CREATE TABLE IF NOT EXISTS vg_mark(path TEXT PRIMARY KEY, on_ INTEGER, t REAL)')
            if not E.cfg.get('vc_sub_v225'):                                          # V0.2.25：分類資料夾裡照原本的資料夾名（只改一次；之後在設定改回來就照你的）
                if (E.cfg.get('vc_sub') or '') == '': E.cfg.set('vc_sub', 'dir')
                E.cfg.set('vc_sub_v225', 1)
            if not E.db.one('SELECT id FROM vc_cat WHERE name=?', (KEEP_CAT,)):           # 「已篩選」一直都有（一部一部審時也可以直接按）
                o = (E.db.one('SELECT COALESCE(MAX(ord),0)+1 FROM vc_cat') or [1])[0]
                E.db.x('INSERT INTO vc_cat(name,dest,color,ord,t) VALUES(?,?,?,?,?)', (KEEP_CAT, '', '#45d483', o, time.time()))
        except Exception: E.log.err('📦 資料夾包：資料表')

    # ------------------------------------------------------------ 資料夾包
    def roots(self):
        """要整理的資料夾（R:\\ 這種磁碟根目錄要保留最後的 \\，不然 os.path.join('R:', 'x') 會變成 'R:x'）."""
        return [rootnorm(r) for r in self.E.fc_list('roots')]

    def _prep(self):
        """每個資料夾底下「有取名字、有照片影片」的子資料夾（判斷是不是「分類用的資料夾」，例如 旅遊／2020-日本、旅遊／2021-沖繩）."""
        if getattr(self, '_kids_t', 0) > time.time() - 300: return                   # 5 分鐘算一次就好（V0.2.59：少吃電腦）
        K = {}; seen = set()
        for d0 in {os.path.dirname(p) for (p,) in self.E.db.q("SELECT path FROM files WHERE state='' AND kind IN ('video','photo')")}:
            d = d0
            while d not in seen:
                seen.add(d)
                par = os.path.dirname(d)
                if par == d or not par: break
                nm = os.path.basename(d)
                if is_named(nm) and not is_dump(nm): K.setdefault(par, set()).add(nm)
                d = par
        self._kids = K; self._kids_t = time.time(); self._pk = {}
        try: self._mark = {os.path.normpath(p).lower(): o for p, o in self.E.db.q('SELECT path, on_ FROM vg_mark')}
        except Exception: self._mark = {}

    def pack_of(self, d):
        """影片所在資料夾 → 它屬於哪一包：從上往下，第一個「有取名字、不是整台倒出來」的資料夾。
        但如果它名字沒有日期、底下又有 2 個以上有名字的子資料夾（像「旅遊」裡有「2020-日本」「2021-沖繩」），就再往下一層。沒有就 ''."""
        d = os.path.normpath(d or '')
        if d in self._pk: return self._pk[d]
        self._prep()
        R = self.roots(); top = next((r for r in sorted(R, key=len, reverse=True) if fcore.under(d, r)), None)
        rel = d[len(top):].strip('\\/') if top else ''
        parts = [x for x in re.split(r'[\\/]', rel) if x] if top else []
        out = ''; cur = top or ''
        for i, nm in enumerate(parts):
            cur = os.path.join(cur, nm)
            if nm.lower().startswith('filecompare_') or nm.lower() == KEEP_CAT: break
            mk = self._mark.get(os.path.normpath(cur).lower())
            if mk == 1: out = cur; break                                             # 你自己說「這是一包」
            if mk == 0: continue                                                     # 你自己說「不是一包」
            if is_named(nm) and not is_dump(nm):
                kids = self._kids.get(cur, set())
                if not has_date(nm) and sum(1 for k_ in kids if has_date(k_)) >= 2 and i + 1 < len(parts) and parts[i + 1] in kids: continue   # 「旅遊」底下有「2020-日本」「2021-沖繩」→ 拆開；「婚禮」底下「Ceremony」「Party」→ 不拆
                out = cur; break
        self._pk[d] = out; return out

    def _rows(self, kinds=('video',)):
        kw = ','.join(f"'{k}'" for k in kinds)
        return self.E.db.q(f"SELECT f.id, f.path, f.size, f.kind, COALESCE(f.taken, f.mtime), f.dur, t.cat, t.moved FROM files f LEFT JOIN vc_tag t ON t.fid=f.id "
                           f"WHERE f.state='' AND f.kind IN ({kw}) AND f.size>0 AND f.health NOT IN ('broken','partial','zero')")

    def packs(self, show='todo', q='', o=''):
        """所有資料夾包：{path,name,n（影片）,todo（還沒分的影片）,np（照片）,b,t0,t1,cover[...],score,dated,skip}，有影片的才列."""
        c = self._cache
        if c[1] is not None and time.time() - c[0] < 300: P = c[1]                    # 5 分鐘（V0.3.69：以前 90 秒，40 萬筆每次要算好幾秒）；整包分類、復原時會清掉重算
        else:
            self._kids_t = 0; self._pk = {}; P = {}; DC = {}
            try: PS = self.E.pet.pet_ids()                                           # 🐾 每包有幾部有貓狗（V0.4.03）
            except Exception: PS = set()
            for fid, path, size, kind, tk, dur, cat, moved in self._rows(('video', 'photo')):
                d_ = os.path.dirname(path); pk = DC.get(d_)
                if pk is None: pk = DC[d_] = self.pack_of(d_) or ''
                if not pk: continue
                g = P.setdefault(pk, {'path': pk, 'name': os.path.basename(pk), 'n': 0, 'todo': 0, 'np': 0, 'b': 0, 't0': 0, 't1': 0, 'vids': [], 'dur': 0, 'pet': 0})
                g['b'] += size or 0
                if tk: g['t0'] = min(g['t0'] or tk, tk); g['t1'] = max(g['t1'], tk)
                if kind == 'video':
                    g['n'] += 1; g['dur'] += dur or 0; g['vids'].append((tk or 0, fid))
                    if cat is None: g['todo'] += 1
                    if fid in PS: g['pet'] += 1
                else: g['np'] += 1
            for g in P.values():
                v = sorted(g.pop('vids')); k = min(8, len(v))
                g['cover'] = [v[int(i * (len(v) - 1) / max(1, k - 1))][1] for i in range(k)] if v else []
                g['dated'] = has_date(g['name'])
                g['score'] = (2 if g['dated'] else 0) + (1 if 3 <= g['n'] <= 400 else 0) + (1 if g['t1'] - g['t0'] < 45 * 86400 else 0)
            self._cache = (time.time(), P)
        S = {r[0] for r in self.E.db.q('SELECT path FROM vg_skip')}
        L = [dict(g, skip=g['path'] in S) for g in P.values() if g['n']]
        if show == 'todo': L = [g for g in L if g['todo'] and not g['skip']]
        elif show == 'skip': L = [g for g in L if g['skip']]
        elif show == 'done': L = [g for g in L if not g['todo']]
        if q: ql = q.lower(); L = [g for g in L if ql in g['path'].lower()]
        K = {'n': lambda g: (-g['todo'], g['path'].lower()), 'new': lambda g: (-(g['t1'] or 0), g['path'].lower()), 'old': lambda g: ((g['t0'] or 9e12), g['path'].lower()),
             'name': lambda g: (g['name'].lower(), g['path'].lower()), 'big': lambda g: (-g['b'], g['path'].lower())}
        L.sort(key=K.get(o, lambda g: (-g['score'], -g['todo'], g['path'].lower())))
        return L

    def warm(self):
        """背景先算好資料夾包（總覽建議、分類頁提示用），不讓畫面等."""
        if getattr(self, '_bgrun', False): return
        self._bgrun = True

        def job():
            try: self.packs('all')
            except Exception: pass
            finally: self._bgrun = False
        import threading; threading.Thread(target=job, name='VGroupWarm', daemon=True).start()

    def pack_brief(self, d):
        """看單部影片時：它在哪一包、那包還有幾部沒審（用快取，舊了就背景重算，不讓畫面等）."""
        p = self.pack_of(os.path.dirname(d) if os.path.splitext(d)[1] else d)
        if not p: return None
        c = self._cache
        if c[1] is None: self.warm()                                                # 只有還沒算過才背景算（V0.2.59：不要每分鐘重算）
        g = (c[1] or {}).get(p)
        return {'path': p, 'name': os.path.basename(p), 'n': g['n'] if g else 0, 'todo': g['todo'] if g else 0, 'np': g['np'] if g else 0}

    def pack_info(self, path):
        p = os.path.normpath(path or ''); return next((g for g in self.packs('all') if g['path'].lower() == p.lower()), None)

    def pack_ids(self, path, kinds=('video',), only_todo=False):
        pre = os.path.normpath(path).rstrip('\\/') + os.sep; kw = ','.join(f"'{k}'" for k in kinds)
        R = self.E.db.q(f"SELECT f.id, f.path, t.cat, t.moved, f.kind, f.dur FROM files f LEFT JOIN vc_tag t ON t.fid=f.id WHERE f.state='' AND f.kind IN ({kw}) AND f.size>0 "
                        f"AND (f.path LIKE ? ESCAPE '^' OR f.path LIKE ? ESCAPE '^') ORDER BY COALESCE(f.taken, f.mtime), f.path", (fcore.like_esc(pre) + '%', fcore.like_esc(pre.replace('\\', '/')) + '%'))
        return [r for r in R if not (only_todo and r[2] is not None)]

    def pack_dups(self, path):
        """這包裡有幾個檔在包外面也有一模一樣的、大多在哪（看內容時顯示，提醒先處理重複）."""
        pre = fcore.like_esc(os.path.normpath(path).rstrip('\\/')); like = (pre + '\\%', pre + '/%')
        R = self.E.db.q("SELECT size, hash FROM files WHERE state='' AND hash IS NOT NULL AND hash NOT LIKE '!%' AND (path LIKE ? ESCAPE '^' OR path LIKE ? ESCAPE '^')", like)
        if not R: return {'n': 0, 'b': 0, 'where': []}
        H = {(sz, h) for sz, h in R}; W = {}; n = 0; b = 0; seen = set()
        for sz, h, p in self.E.db.q("SELECT f.size, f.hash, f.path FROM files f JOIN (SELECT DISTINCT size, hash FROM files WHERE state='' AND hash IS NOT NULL AND hash NOT LIKE '!%' AND (path LIKE ? ESCAPE '^' OR path LIKE ? ESCAPE '^')) k "
                                    "ON k.size=f.size AND k.hash=f.hash WHERE f.state='' AND NOT (f.path LIKE ? ESCAPE '^' OR f.path LIKE ? ESCAPE '^')", like + like):
            if (sz, h) in H and (sz, h) not in seen: seen.add((sz, h)); n += 1; b += sz or 0
            d = os.path.dirname(p); W[d] = W.get(d, 0) + 1
        top = sorted(W.items(), key=lambda kv: -kv[1])[:3]
        return {'n': n, 'b': b, 'where': [{'path': d, 'n': k} for d, k in top]}

    def ensure_cat(self, name=KEEP_CAT):
        r = self.E.db.one('SELECT id FROM vc_cat WHERE name=?', (name,))
        if r: return r[0]
        self.E.vc.cat_add(name); r = self.E.db.one('SELECT id FROM vc_cat WHERE name=?', (name,)); return r[0] if r else 0

    def pack_tag(self, path, cat=0, photos=True, keep_tree=True, only_todo=False):
        """整包分類：cat=0 → 「已篩選」。keep_tree＝搬的時候保留「包名＼原本的子資料夾」（不會全部倒在一起）。已經搬過的不動."""
        p = os.path.normpath(path or '').rstrip('\\/')
        if not p: return {'ok': False, 'message': '沒有指定資料夾'}
        cat = int(cat or 0) or self.ensure_cat()
        c = self.E.db.one('SELECT name FROM vc_cat WHERE id=?', (cat,))
        if not c: return {'ok': False, 'message': '沒有這個分類'}
        R = self.pack_ids(p, ('video', 'photo') if photos else ('video',), only_todo); now = time.time(); W = []; base = os.path.basename(p)
        for fid, fp, tc, mv, _k, _d in R:
            if mv: continue
            try: rel = os.path.relpath(os.path.dirname(fp), p) if keep_tree else ''
            except ValueError: rel = ''
            if rel.startswith('..') or os.path.isabs(rel): rel = ''                    # 防呆：算不出來就放在包名底下
            sub = base if rel in ('.', '') else os.path.join(base, rel)
            W.append((fid, cat, now, sub if keep_tree else ''))
        self.E.db.xm("INSERT INTO vc_tag(fid,cat,t,moved,sub,auto) VALUES(?,?,?,0,?,0) ON CONFLICT(fid) DO UPDATE SET cat=excluded.cat, t=excluded.t, sub=excluded.sub, auto=0 WHERE vc_tag.moved=0", W)
        try: self.E.vc.dup_to_delete([x[0] for x in W])
        except Exception: self.E.log.err('🗑 重複副本 → Delete')
        self._cache = (0, None)
        nv = sum(1 for r in R if not r[3])
        self.E.log.w(f'📦 整包分類：{p} → {c[0]}（{len(W):,} 個）'); self.E.oplog('整包分類', f'{p} → {c[0]}：{len(W):,} 個')
        return {'ok': True, 'n': len(W), 'cat': cat, 'ids': [x[0] for x in W], 'message': f'✔ 「{base}」整包 {len(W):,} 個分到「{c[0]}」' + ('（搬的時候保留資料夾）' if keep_tree else '') + '，按 🚚 搬 才會搬'}

    def pack_tag_many(self, paths, cat=0):
        """勾選好幾包，一次整包分類＋只搬這幾包（V0.2.28）."""
        ids = []; n = 0; names = []
        for p in paths or []:
            r = self.pack_tag(p, cat)
            if r.get('ok'): ids += r.get('ids') or []; n += 1; names.append(os.path.basename(os.path.normpath(p)))
        return {'ok': bool(n), 'n': n, 'ids': ids, 'message': f'✔ {n} 包（{len(ids):,} 個）分好了：' + '、'.join(names[:5]) + ('…' if len(names) > 5 else '')}

    def pack_untag(self, path):
        R = self.pack_ids(path, ('video', 'photo')); ids = [(r[0],) for r in R if r[2] is not None and not r[3]]
        self.E.db.xm('DELETE FROM vc_tag WHERE fid=? AND moved=0', ids); self._cache = (0, None)
        return {'ok': True, 'n': len(ids), 'message': f'↶ 取消 {len(ids):,} 個的分類'}

    def mark(self, path, on):
        """自己指定：on=1 這個資料夾是一包、0 不是一包、-1 取消（照自動判斷）."""
        p = os.path.normpath(path or '').rstrip('\\/')
        if not p: return {'ok': False, 'message': '沒有指定資料夾'}
        if int(on) < 0: self.E.db.x('DELETE FROM vg_mark WHERE path=?', (p,))
        else: self.E.db.x('INSERT OR REPLACE INTO vg_mark(path,on_,t) VALUES(?,?,?)', (p, int(on), time.time()))
        self._kids_t = 0; self._cache = (0, None); self._pk = {}
        nm = os.path.basename(p)
        return {'ok': True, 'message': {1: f'📦 「{nm}」當成一包了', 0: f'🚫 「{nm}」不當成一包了', -1: f'↶ 「{nm}」照自動判斷'}[max(-1, min(1, int(on)))]}

    def progress(self):
        """🎞 審片進度（V0.2.23）：影片總數、已審（分好）、已搬、待審、今天、速度、預估剩多久、還沒審的資料夾包."""
        o = lambda sql, a=(): (self.E.db.one(sql, a) or [0])[0] or 0
        tot = o("SELECT COUNT(*) FROM files f WHERE f.state='' AND f.kind='video' AND f.size>0 AND f.health NOT IN ('broken','partial','zero')")
        tag = o("SELECT COUNT(*) FROM vc_tag t JOIN files f ON f.id=t.fid WHERE f.kind='video' AND f.state=''")
        mv = o("SELECT COUNT(*) FROM vc_tag t JOIN files f ON f.id=t.fid WHERE f.kind='video' AND t.moved=1")
        sp = self.E.vc.speed(); todo = max(0, tot - tag)
        pc = self._cache[1]
        P = [g for g in (pc or {}).values() if g['todo']]                           # 只用算好的（V0.2.61：不在這裡觸發重算）
        return {'ok': True, 'total': tot, 'tagged': tag, 'moved': mv, 'todo': todo, 'today': sp.get('today', 0), 'week': sp.get('week', 0), 'per': sp.get('per', 0),
                'eta': round(todo * sp['per']) if sp.get('per') else 0, 'packs': len(P), 'pack_v': sum(g['todo'] for g in P)}

    def recent(self, limit=60):
        """最近整包搬過的（可以整包搬回原處）：[{name, cat, cname, n, t}]."""
        C = {r[0]: r[1] for r in self.E.db.q('SELECT id, name FROM vc_cat')}; G = {}
        for fid, sub, cat, t in self.E.db.q("SELECT fid, sub, cat, t FROM vc_tag WHERE moved=1 AND COALESCE(sub,'')!=''"):
            nm = re.split(r'[\\/]', sub)[0]; g = G.setdefault((cat, nm), {'name': nm, 'cat': cat, 'cname': C.get(cat, ''), 'n': 0, 't': 0}); g['n'] += 1; g['t'] = max(g['t'], t or 0)
        return sorted(G.values(), key=lambda g: -g['t'])[:limit]

    def pack_back(self, name, cat):
        """整包搬回原處：分類搬過去的那些檔搬回原本的位置，而且變回「還沒審」."""
        F = [r[0] for r in self.E.db.q("SELECT fid, sub FROM vc_tag WHERE moved=1 AND cat=? AND COALESCE(sub,'')!=''", (int(cat),)) if re.split(r'[\\/]', r[1])[0] == name]
        if not F: return {'ok': False, 'message': '找不到這包（可能已經搬回去了）'}
        M = []
        for i in range(0, len(F), 500):
            part = F[i:i + 500]
            M += [r[0] for r in self.E.db.q(f"SELECT MAX(id) FROM moves WHERE undone=0 AND reason LIKE '分類：%' AND fid IN ({','.join('?' * len(part))}) GROUP BY fid", part)]
        r = self.E.fc_undo(M)
        self.E.db.xm('DELETE FROM vc_tag WHERE fid=? AND moved=0', [(f,) for f in F]); self._cache = (0, None)
        self.E.oplog('整包搬回原處', f'{name}：{r.get("message", "")}')
        return {'ok': r.get('ok'), 'message': f'↶ 「{name}」整包搬回原處：' + r.get('message', '') + '（變回還沒審）'}

    def pack_skip(self, path, on=True):
        p = os.path.normpath(path or '')
        if on: self.E.db.x('INSERT OR REPLACE INTO vg_skip(path,t) VALUES(?,?)', (p, time.time()))
        else: self.E.db.x('DELETE FROM vg_skip WHERE path=?', (p,))
        return {'ok': True, 'message': '⏭ 這包先跳過（「跳過的」裡找得到）' if on else '↶ 放回清單'}

    # ------------------------------------------------------------ 🧩 相關的排一起
    MODES = [('', '不分組'), ('pack', '📦 資料夾包／資料夾'), ('type', '🎬 同類型（檔名、手機、直橫）'), ('time', '📅 同一段時間'), ('dir', '📁 同資料夾'), ('sim', '👯 相似影片（同一部的不同版本）'), ('geo', '📍 同一個地方（有 GPS 的）'), ('szsug', '📏 大小區間＋同類先排（每 100MB 一組，組裡建議同一類的排一起）')]

    @staticmethod
    def size_bucket(b):
        """大小區間：100MB 以下每 10MB、2GB 以下每 100MB、再大每 500MB → (下限, 上限) MB."""
        m = (b or 0) / 1e6; st = 10 if m < 100 else 100 if m < 2000 else 500; lo = int(m // st) * st; return lo, lo + st

    def _szsug(self, ids, order=''):
        """📏 大小區間＋同類先排（V0.4.58）：照大小分組（600～700MB 一組），組裡面電腦建議同一類的排一起，再來是電腦看到同樣內容的，最後照大小."""
        S = set(ids); SZ = {}
        for kd in ('video', 'photo'):
            if kd == 'photo' and len(SZ) >= len(S): break
            for fid, sz in self.E.db.q(f"SELECT id, size FROM files WHERE kind='{kd}' AND state=''"):
                if fid in S: SZ[fid] = sz or 0
        ck = (len(ids), ids[0] if ids else 0, tuple(self.E.db.one('SELECT COUNT(*), MAX(t) FROM vc_tag') or ()))
        c = getattr(self, '_szc', None)
        if c and c[0] == ck and time.time() - c[1] < 120: HC = c[2]
        else:
            HC = {}
            try:
                for r in self.E.vc.hint_many(ids, dry=True).get('rows') or []:
                    for f in r.get('ids') or []: HC[f] = r['cid']
            except Exception: HC = {}
            self._szc = (ck, time.time(), HC)
        try: PM = self.E.vc._pet_map()
        except Exception: PM = {}
        C = {c_['id']: c_['name'] for c_ in self.E.vc.cats()}; CO = {cid: i for i, cid in enumerate(C)}
        asc = order == 'size_asc'; K = {}; lab = {}; CNT = {}
        for f in ids:
            lo, hi = self.size_bucket(SZ.get(f, 0)); K[f] = lo
            lab[lo] = f'📏 {lo:,}～{hi:,} MB' if hi < 1000 else f'📏 {lo / 1000:g}～{hi / 1000:g} GB'
            if f in HC: d = CNT.setdefault(lo, {}); d[HC[f]] = d.get(HC[f], 0) + 1
        keyorder = sorted(set(K.values()), reverse=not asc)
        for k in keyorder:
            d = CNT.get(k)
            if d: lab[k] += '・💡 ' + '、'.join(f'{C.get(cid, "?")} {n}' for cid, n in sorted(d.items(), key=lambda x: -x[1])[:3])
        def ck_(f):
            pt = sorted(PM.get(f) or ())
            return (0 if f in HC else 1, -CNT.get(K[f], {}).get(HC.get(f), 0), CO.get(HC.get(f), 999), (0, pt[0]) if pt else (1, ''), SZ.get(f, 0) if asc else -SZ.get(f, 0))
        gi = {k: i for i, k in enumerate(keyorder)}
        new = sorted(ids, key=lambda f: (gi[K[f]], ck_(f)))
        return new, [lab[k] for k in keyorder], [gi[K[f]] for f in new], ['' for _ in keyorder]

    def group(self, ids, mode, order=''):
        """ids 重新排：同一組的排在一起 → (新順序 ids, 組名清單, 每部的組號, 每組的資料夾包路徑)."""
        if not mode or not ids: return ids, [], [], []
        if mode == 'szsug': return self._szsug(ids, order)
        S = set(ids); F = {}
        SZ = {}
        for kd in ('video', 'photo'):                                               # 先讀影片；不夠才讀照片（V0.3.55：以前每次都讀 40 幾萬張照片）
            if kd == 'photo' and len(F) >= len(S): break
            for fid, path, w, h, make, model, tk, sz, du in self.E.db.q(f"SELECT id, path, w, h, make, model, COALESCE(taken, mtime), size, dur FROM files WHERE kind='{kd}' AND state=''"):
                if fid in S: F[fid] = (path, w, h, ((make or '') + ' ' + (model or '')).strip(), tk or 0); SZ[fid] = (sz or 0, du or 0)
        order_ = {fid: i for i, fid in enumerate(ids)}; K = {}; lab = {}; pk = {}
        SG = {}
        if mode == 'sim':
            try: SG = {fid: gid for gid, fid in self.E.db.q('SELECT gid, fid FROM simv_grp')}
            except Exception: SG = {}
        GEO = {}
        if mode == 'geo':                                                           # 📍 同一個地方（V0.3.67）：有 GPS 的照 5 公里左右分
            for fid, la, lo in self.E.db.q("SELECT id, lat, lon FROM files WHERE state='' AND lat IS NOT NULL AND lon IS NOT NULL AND NOT (lat=0 AND lon=0)"):
                if fid in S: GEO[fid] = (round(la * 20) / 20, round(lo * 20) / 20)
        if mode == 'time':
            L = sorted((F[i][4], i) for i in ids if i in F); g = -1; last = None
            for tk, fid in L:
                if last is None or tk - last > 4 * 3600 or time.strftime('%Y%m%d', time.localtime(last)) != time.strftime('%Y%m%d', time.localtime(tk)):
                    g += 1; lab[g] = time.strftime('%Y-%m-%d %H:%M', time.localtime(tk)) if tk else '不知道日期'
                K[fid] = (g, tk); last = tk
            for fid in ids:
                if fid not in K: K[fid] = (10 ** 9, 0); lab[10 ** 9] = '不知道日期'
            cnt = {}
            for k, _t in K.values(): cnt[k] = cnt.get(k, 0) + 1
            M = {}                                                                  # 不到 3 部的時段，同一個月的併在一起（V0.2.46）
            for f, (k, tk) in list(K.items()):
                if cnt.get(k, 0) < 3 and k != 10 ** 9 and tk:
                    ym = time.strftime('%Y-%m', time.localtime(tk)); mk = M.get(ym)
                    if mk is None: mk = M[ym] = 10 ** 8 + int(ym.replace('-', '')); lab[mk] = f'{ym} 零散的'
                    K[f] = (mk, tk)
            first = {}
            for f, (k, tk) in K.items(): first[k] = min(first.get(k, 9e18), tk or 9e18)
            keyorder = sorted(set(k for k, _ in K.values()), key=lambda k: (first[k], k))
        else:
            for fid in ids:
                path, w, h, dev, tk = F.get(fid, ('', 0, 0, '', 0))
                if mode == 'pack':
                    d = os.path.dirname(path); p = self.pack_of(d); key = (0, p.lower()) if p else (1, d.lower())
                    lab[key] = ('📦 ' + os.path.basename(p)) if p else ('📁 ' + (os.path.basename(d) or d)); pk[key] = p
                elif mode == 'sim':
                    gid = SG.get(fid)
                    if gid is not None: key = (0, gid); lab[key] = f'👯 相似影片 #{gid}'
                    else:
                        d = os.path.dirname(path); key = (1, d.lower()); lab[key] = '📁 ' + (os.path.basename(d) or d)
                elif mode == 'dir':
                    d = os.path.dirname(path); key = d.lower(); lab[key] = '📁 ' + (os.path.basename(d) or d)
                elif mode == 'geo':
                    g_ = GEO.get(fid)
                    if g_: key = (0, g_); lab[key] = f'📍 {g_[0]:.2f}, {g_[1]:.2f}'
                    else: key = (1, ''); lab[key] = '📍 沒有位置資訊'
                else:
                    sig = name_sig(path); fr = friendly(path, sig); key = (fr or sig, dev, res_bucket(w, h))
                    lab[key] = (fr if fr else '🎬 ' + sig.replace('#', '…')) + ''.join('・' + x for x in (dev, res_bucket(w, h)) if x)
                K[fid] = (key, tk)
            cnt = {}
            for k, _ in K.values(): cnt[k] = cnt.get(k, 0) + 1
            if mode in ('pack', 'dir'):                                              # 不到 3 部的一般資料夾，併到上一層（V0.2.47；資料夾包不併）
                small = {k for k, n in cnt.items() if n < 3 and not pk.get(k)}
                if len(small) > 1:
                    for f in list(K):
                        k = K[f][0]
                        if k in small:
                            d = os.path.dirname(F.get(f, ('',))[0]); par = os.path.dirname(d)
                            nk = (1, par.lower() + '\x00') if mode == 'pack' else par.lower() + '\x00'
                            lab[nk] = '📁 ' + (os.path.basename(par) or par) + '（零散的子資料夾）'; K[f] = (nk, K[f][1])
                    cnt = {}
                    for k, _ in K.values(): cnt[k] = cnt.get(k, 0) + 1
            if mode == 'type':                                                      # 太大的組（>150 部）再照年月分（V0.2.48），一組看得完
                big = {k for k, n in cnt.items() if n > 150}
                if big:
                    for f in list(K):
                        k, tk = K[f]
                        if k in big:
                            ym = time.strftime('%Y-%m', time.localtime(tk)) if tk else '？'; nk = k + (ym,); lab[nk] = lab[k] + f'・{ym}'; K[f] = (nk, tk)
                    cnt = {}
                    for k, _ in K.values(): cnt[k] = cnt.get(k, 0) + 1
            if mode == 'type':                                                      # 不到 3 部的小組併成「零散的」，放最後（V0.2.45）
                small = {k for k, n in cnt.items() if n < 3}
                if len(small) > 1:
                    MK = ('~零散',); lab[MK] = f'🎲 零散的（每種不到 3 部，共 {len(small)} 種）'
                    for f in list(K):
                        if K[f][0] in small: K[f] = (MK, K[f][1])
                    cnt = {}
                    for k, _ in K.values(): cnt[k] = cnt.get(k, 0) + 1
                keyorder = sorted(cnt, key=lambda k: (k == ('~零散',), -cnt[k], str(k)))       # 同類型：大組先（一次處理最多部）
            else: keyorder = sorted(cnt)
        if mode in ('time', 'geo'):                                                 # 同一段時間／同一個地方：組名加上「大多在哪個資料夾」
            DC = {}
            for f, (k, _t) in K.items():
                pth = F.get(f, ('',))[0]
                if pth: c = DC.setdefault(k, {}); b = os.path.basename(os.path.dirname(pth)); c[b] = c.get(b, 0) + 1
            for k, c in DC.items():
                if k in lab and c: b = max(c.items(), key=lambda x: x[1])[0]; lab[k] = (f'📅 {lab[k]}' if mode == 'time' else lab[k]) + f'・📁 {b}'
        if order in ('size', 'size_asc', 'dur', 'dur_asc'):                          # 大→小／長→短：整組加起來大的組排上面，組裡面也照大小（V0.2.67）
            ix = 0 if order.startswith('size') else 1; tot = {}
            for f in ids: k = K[f][0]; tot[k] = tot.get(k, 0) + SZ.get(f, (0, 0))[ix]
            rev = not order.endswith('_asc')
            keyorder = sorted(keyorder, key=lambda k: (-tot.get(k, 0) if rev else tot.get(k, 0), str(k)))
            for k in keyorder:
                if k in lab and tot.get(k): lab[k] = lab[k] + ((f'・共 {tot[k] / 1e9:.1f} GB' if tot[k] >= 1e9 else f'・共 {tot[k] / 1e6:.0f} MB') if ix == 0 else f'・共 {tot[k] / 60:.0f} 分鐘')
            gi = {k: i for i, k in enumerate(keyorder)}
            new = sorted(ids, key=lambda f: (gi[K[f][0]], order_[f]))
        else:
            gi = {k: i for i, k in enumerate(keyorder)}
            new = sorted(ids, key=lambda f: (gi[K[f][0]], K[f][1], order_[f]))
        names = [lab.get(k, '') for k in keyorder]; packs = [pk.get(k, '') for k in keyorder]
        return new, names, [gi[K[f][0]] for f in new], packs

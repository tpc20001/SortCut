"""HotZone FM — 圖片分類 without any AI model: every picture in the chosen folders is analysed once in the
background (Pillow, plus OpenCV for face detection when it is installed) and stored in Data\\images.sqlite3.

  colour       main colours (紅 橙 黃 綠 青 藍 紫 粉 棕 黑 白 灰) with their share, brightness, saturation
  look         dHash (64-bit perceptual hash) -> "looks like this one", series (相近套圖) = close in time + similar look
  EXIF         date taken, camera make / model, GPS present
  shape        width / height, portrait / landscape / square, screenshot guess, blur score
  faces        number of faces (classic OpenCV Haar cascade, no neural network)

Re-analysis only happens when a file's size or modification time changed. Paced like the other background jobs.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time

from hz_common import DATA_DIR, IS_WIN, norm, is_under
import hz_win as W
import hz_words as WD

DB = DATA_DIR / 'images.sqlite3'
EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.tif', '.tiff', '.jfif'}
COLORS = ['紅', '橙', '黃', '綠', '青', '藍', '紫', '粉', '棕', '黑', '白', '灰']
COLOR_HEX = {'紅': '#e53935', '橙': '#fb8c00', '黃': '#fdd835', '綠': '#43a047', '青': '#00acc1', '藍': '#1e88e5', '紫': '#8e24aa',
             '粉': '#f48fb1', '棕': '#8d6e63', '黑': '#111111', '白': '#f5f5f5', '灰': '#9e9e9e'}
SCREEN_SIZES = {(1920, 1080), (2560, 1440), (3840, 2160), (1366, 768), (1536, 864), (1440, 900), (1280, 720), (1600, 900), (2560, 1600),
                (1170, 2532), (1179, 2556), (1290, 2796), (1080, 2400), (1080, 2340), (1440, 3200), (1242, 2688), (828, 1792), (750, 1334), (1284, 2778)}


def color_name(h, s, v):
    """HSV (0-1) -> one of COLORS."""
    if v < 0.16: return '黑'
    if s < 0.13: return '白' if v > 0.85 else '灰'
    if s < 0.28 and v > 0.9: return '白'
    hd = h * 360
    if (hd < 20 or hd >= 345) and v < 0.55 and s > 0.35: return '棕'
    if 20 <= hd < 45 and v < 0.6: return '棕'
    if hd < 12 or hd >= 345: return '粉' if (s < 0.5 and v > 0.75) else '紅'
    if hd < 40: return '橙'
    if hd < 68: return '黃'
    if hd < 160: return '綠'
    if hd < 195: return '青'
    if hd < 255: return '藍'
    if hd < 290: return '紫'
    return '粉' if s < 0.65 or v > 0.7 else '紫'


def dhash(gray_img):
    from PIL import Image
    im = gray_img.resize((9, 8), Image.BILINEAR)
    px = list(im.getdata()); v = 0
    for r in range(8):
        for c in range(8):
            v = (v << 1) | (1 if px[r * 9 + c] > px[r * 9 + c + 1] else 0)
    return v - (1 << 63) if v >= (1 << 63) else v                              # signed 64-bit for SQLite


def hamming(a, b):
    return ((a ^ b) & 0xFFFFFFFFFFFFFFFF).bit_count()


_face = {'ok': None, 'path': None}
_face_tl = threading.local()                                              # one classifier per thread (not thread-safe)


def face_detector():
    if _face['ok'] is None:
        try:
            import cv2
            p = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
            ok = not cv2.CascadeClassifier(p).empty()
            _face.update(ok=ok, path=p if ok else None)
        except Exception:
            _face.update(ok=False)
    if not _face['ok']: return None
    clf = getattr(_face_tl, 'clf', None)
    if clf is None:
        import cv2
        clf = _face_tl.clf = cv2.CascadeClassifier(_face['path'])
    return clf


_big_sem = threading.Semaphore(1)


def _taken(dt):
    m = re.match(r'(\d{4})[:\-](\d\d)[:\-](\d\d)[ T](\d\d):(\d\d):(\d\d)', str(dt or ''))
    if not m: return None
    try: return time.mktime(time.strptime(' '.join(m.groups()), '%Y %m %d %H %M %S'))
    except Exception: return None


def _rgb8(im):
    """RGB with 8 bits per channel. 16-bit / 32-bit greyscale (scans, astro, medical) would otherwise be clipped to
    white by convert('RGB'): every such picture would look the same (and be offered as near-duplicates)."""
    if im.mode in ('I;16', 'I;16B', 'I;16L', 'I;16N'):
        return im.convert('I').point(lambda v: v / 257.0).convert('L').convert('RGB')
    if im.mode == 'I':
        lo, hi = im.getextrema(); top = 65535 if hi > 255 else 255
        return im.point(lambda v: v * 255.0 / top).convert('L').convert('RGB')
    if im.mode == 'F':
        lo, hi = im.getextrema(); rng = (hi - lo) or 1
        return im.point(lambda v: (v - lo) * 255.0 / rng).convert('L').convert('RGB')
    return im.convert('RGB')


def analyse(path, faces=True):
    from PIL import Image, ImageOps, ImageStat, ImageFilter
    st = os.stat(W.lp(path))
    r = {'path': path, 'size': st.st_size, 'mtime': st.st_mtime}
    import hz_thumbs as _TH
    _TH._limits(Image)
    with Image.open(W.lp(path)) as im:
        r['w'], r['h'] = im.size
        px = r['w'] * r['h']; jpeg = im.format == 'JPEG'
        huge = px > 60_000_000 and not jpeg                                 # PNG/TIFF scans: decoding needs GBs
        exif = {}
        try:
            ex = im.getexif()
            if ex:
                sub = ex.get_ifd(0x8769) if hasattr(ex, 'get_ifd') else {}
                dt = sub.get(36867) or sub.get(36868) or ex.get(306)
                exif = {'make': str(ex.get(271) or '').strip('\x00 ').strip(), 'model': str(ex.get(272) or '').strip('\x00 ').strip(),
                        'dt': str(dt or '').strip('\x00 '), 'gps': bool(ex.get_ifd(0x8825)) if hasattr(ex, 'get_ifd') else False, 'orient': ex.get(274)}
        except Exception:
            pass
        r['taken'] = _taken(exif.get('dt'))
        try: im.draft('RGB', (512, 512))
        except Exception: pass
        if huge:                                                    # metadata + search words only, no pixel analysis
            r.update(c1=None, colors=None, bright=None, sat=None, dhash=None, blur=None, shot=0, faces=None,
                     make=exif.get('make', ''), model=exif.get('model', ''), gps=int(bool(exif.get('gps'))))
            r['words'], r['wlen'] = WD.words_of(path, WD.meta_text(path))
            return r
        if exif.get('orient') in (5, 6, 7, 8): r['w'], r['h'] = r['h'], r['w']
        try: im = ImageOps.exif_transpose(im)
        except Exception: pass
        if getattr(im, 'is_animated', False): im.seek(0)
        if not jpeg and px > 4_000_000:                                    # big PNG/TIFF: one at a time, shrink right away
            with _big_sem:
                im.thumbnail((1024, 1024)); rgb = _rgb8(im)
        else:
            rgb = _rgb8(im)
    small = rgb.copy(); small.thumbnail((96, 96))
    hsv = small.convert('HSV')
    counts = {c: 0 for c in COLORS}; n = 0; ssum = 0; vsum = 0
    for (hh, ss, vv) in hsv.getdata():
        c = color_name(hh / 255, ss / 255, vv / 255); counts[c] += 1; n += 1; ssum += ss; vsum += vv
    top = sorted(((c, k / max(1, n)) for c, k in counts.items() if k), key=lambda x: -x[1])
    # the colour you notice: strongest chromatic colour with a fair share beats a grey background
    chroma = [x for x in top if x[0] not in ('黑', '白', '灰') and x[1] >= 0.12]
    r['c1'] = chroma[0][0] if chroma and (top[0][0] in ('黑', '白', '灰') and chroma[0][1] >= 0.2 or top[0][0] not in ('黑', '白', '灰')) else top[0][0]
    r['colors'] = [[c, round(p, 3)] for c, p in top[:5]]
    r['bright'] = round(vsum / max(1, n) / 255, 3); r['sat'] = round(ssum / max(1, n) / 255, 3)
    gray = rgb.convert('L'); g256 = gray.copy(); g256.thumbnail((256, 256))
    r['dhash'] = dhash(gray)
    try: r['blur'] = round(ImageStat.Stat(g256.filter(ImageFilter.FIND_EDGES)).var[0], 1)
    except Exception: r['blur'] = None
    name = os.path.basename(path).lower()
    no_camera = not exif.get('make') and not exif.get('model')
    r['shot'] = int(bool(re.search(r'screenshot|螢幕擷取|截圖|スクリーンショット|screen ?shot|snip', name)) or
                    (no_camera and path.lower().endswith('.png') and ((r['w'], r['h']) in SCREEN_SIZES or (r['h'], r['w']) in SCREEN_SIZES)))
    r['make'] = exif.get('make', ''); r['model'] = exif.get('model', ''); r['gps'] = int(bool(exif.get('gps')))
    extra = ' '.join(x for x in (r.get('make'), r.get('model'), 'screenshot 截圖' if r.get('shot') else '') if x)
    try: r['words'], r['wlen'] = WD.words_of(path, (WD.meta_text(path) + ' ' + extra).strip())
    except Exception: r['words'], r['wlen'] = WD.words_of(path, extra)
    r['faces'] = None
    if faces:
        clf = face_detector()
        if clf is not None:
            try:
                import numpy as np
                g = gray.copy(); g.thumbnail((640, 640)); arr = np.asarray(g)
                found = clf.detectMultiScale(arr, scaleFactor=1.15, minNeighbors=6, minSize=(max(24, min(arr.shape) // 14),) * 2)
                r['faces'] = int(len(found))
            except Exception:
                r['faces'] = None
    return r


def exif_taken(path):
    """Date taken from EXIF only (reads the header, not the pixels). None when there is none."""
    try:
        from PIL import Image
        with Image.open(W.lp(path)) as im:
            ex = im.getexif()
            if not ex: return None
            sub = ex.get_ifd(0x8769) if hasattr(ex, 'get_ifd') else {}
            return _taken(sub.get(36867) or sub.get(36868) or ex.get(306))
    except Exception:
        return None


class ImageLibrary:
    def __init__(self, eng):
        self.eng = eng; self.S = eng.S; self.log = eng.log
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(DB), check_same_thread=False, timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS img(path TEXT PRIMARY KEY, folder TEXT, name TEXT, size INTEGER, mtime REAL, w INTEGER, h INTEGER,
            taken REAL, make TEXT, model TEXT, gps INTEGER, c1 TEXT, colors TEXT, bright REAL, sat REAL, blur REAL, dhash INTEGER, faces INTEGER,
            shot INTEGER, analyzed REAL, err TEXT)''')
        self.db.execute('CREATE TABLE IF NOT EXISTS star(path TEXT PRIMARY KEY, t REAL)')    # favourites survive re-analysis
        cols = {r[1] for r in self.db.execute('PRAGMA table_info(img)')}
        if 'words' not in cols: self.db.execute('ALTER TABLE img ADD COLUMN words TEXT')
        if 'wlen' not in cols: self.db.execute('ALTER TABLE img ADD COLUMN wlen INTEGER')
        for ix in ('folder', 'c1', 'taken', 'faces', 'shot', 'model'):
            self.db.execute(f'CREATE INDEX IF NOT EXISTS img_{ix} ON img({ix})')
        self.db.commit()
        self.ver = 0; self._tcache = {}
        self.st = {'state': 'idle', 'done': 0, 'total': 0, 'msg': '', 'rate': 0.0, 'cur': ''}
        self.stop_ev = threading.Event(); self.wake = threading.Event(); self.paused = False
        self.th = threading.Thread(target=self._loop, name='HZ-Images', daemon=True)

    def start(self):
        self.th.start(); return self

    def stop(self):
        self.stop_ev.set(); self.wake.set(); self.th.join(5)
        try: self.db.close()
        except Exception: pass

    def folders(self):
        return [norm(f) for f in (self.S.get('images.folders') or []) if f]

    # ------------------------------------------------------------------ background analysis
    def _list(self, folder):
        files = None
        try: files = self.eng.index.subtree_files(folder)
        except Exception: files = None
        if files is not None:
            return [(p, s, m) for p, s, m in files if os.path.splitext(p)[1].lower() in EXTS and '.HotZoneVault' not in p]
        out = []
        for root, ds, fs in os.walk(folder):
            ds[:] = [d for d in ds if d != '.HotZoneVault']
            for f in fs:
                if os.path.splitext(f)[1].lower() in EXTS:
                    p = os.path.join(root, f)
                    try: st = os.stat(p); out.append((p, st.st_size, st.st_mtime))
                    except OSError: pass
        return out

    def _loop(self):
        W.thread_background(True)
        while not self.stop_ev.is_set():
            try:
                if not self.S.get('images.enabled') or not self.folders() or self.paused:
                    self.st.update(state='paused' if self.paused else 'idle', msg='' if self.folders() else '還沒有設定要分析的資料夾')
                    self.wake.wait(10); self.wake.clear(); continue
                self._pass()
            except Exception:
                self.log.exc('images', 'loop'); self.wake.wait(60)
            self.wake.wait(600); self.wake.clear()

    def _pass(self):
        self.st.update(state='listing', msg='列出圖片…')
        files = []; seen_f = set(); missing = []
        K = (lambda p: p.lower()) if IS_WIN else (lambda p: p)              # 'E:\photos' typed vs 'E:\Photos' on disk
        flist = self.folders()
        for f in flist:
            if any(g != f and K(norm(g)) != K(norm(f)) and is_under(f, g) for g in flist): continue   # inside another listed folder
            if not os.path.isdir(W.lp(f)): missing.append(f); continue      # disk unplugged / folder renamed: keep its results
            for x in self._list(f):
                k = K(x[0])
                if k not in seen_f: seen_f.add(k); files.append(x)
        with self.lock:
            known = {K(r[0]): (r[1], r[2], r[0]) for r in self.db.execute('SELECT path, size, mtime FROM img')}
        todo = [(p, s, m) for p, s, m in files if known.get(K(p)) is None or known[K(p)][0] != s or abs((known[K(p)][1] or 0) - m) > 1]
        alive = {K(p) for p, s, m in files}
        gone = [v[2] for k, v in known.items() if k not in alive and any(is_under(v[2], f) for f in flist)
                and not any(is_under(v[2], m) for m in missing)]
        self.st['missing'] = missing
        if missing: self.log.warn('images', '這些資料夾暫時找不到（硬碟沒接上？），保留它們的分析結果：' + '、'.join(missing))
        if len(gone) > 0.5 * len(known) > 1000:                            # half the library 'vanished': a disk is missing,
            self.log.warn('images', f'有 {len(gone):,} 張圖片暫時找不到（硬碟沒接上？），先不刪除它們的分析結果')
            gone = []                                                       # not 200k deleted pictures
        if gone:
            with self.lock:
                self.db.executemany('DELETE FROM img WHERE path=?', [(p,) for p in gone]); self.db.commit(); self.ver += 1
        self.st.update(state='running' if todo else 'done', done=0, total=len(todo), msg=f'{len(files):,} 張圖片，要分析 {len(todo):,} 張' if todo else f'{len(files):,} 張圖片都分析好了')
        faces = bool(self.S.get('images.faces'))
        pct = max(10, min(100, int(self.S.get('images.usage_pct') or 60)))
        nthreads = max(1, min(8, int(self.S.get('images.threads') or 1), (os.cpu_count() or 2)))
        batch = []; blk = threading.Lock(); t_rate = [time.time(), 0]; it_q = iter(enumerate(todo)); ql = threading.Lock()

        def worker():
            W.thread_background(True)
            while not self.stop_ev.is_set() and not self.paused:
                while self.eng.queue_busy_any() and self.S.get('images.yield_queue') and not self.stop_ev.is_set():
                    self.st['msg'] = '傳輸佇列在工作，先暫停分析'; self.stop_ev.wait(3)
                with ql:
                    nxt = next(it_q, None)
                if nxt is None: return
                i, (p, s, m) = nxt
                t0 = time.monotonic()
                try:
                    r = analyse(p, faces); r['err'] = None
                except Exception as e:
                    r = {'path': p, 'size': s, 'mtime': m, 'err': str(e)[:200]}
                r['analyzed'] = time.time(); r['folder'] = os.path.dirname(p); r['name'] = os.path.basename(p)
                busy = time.monotonic() - t0
                with blk:
                    batch.append(r)
                    self.st['done'] += 1; self.st['cur'] = p; t_rate[1] += 1
                    if time.time() - t_rate[0] > 3: self.st['rate'] = t_rate[1] / (time.time() - t_rate[0]); t_rate[0] = time.time(); t_rate[1] = 0
                    if len(batch) >= 50: self._save(batch); batch.clear()
                if pct < 100: self.stop_ev.wait(busy * (100 - pct) / pct)
        ths = [threading.Thread(target=worker, name=f'HZ-Img{k}', daemon=True) for k in range(nthreads)]
        for t in ths: t.start()
        for t in ths: t.join()
        if batch: self._save(batch)
        if self.paused: self.st.update(state='paused', msg=f'已暫停（完成 {self.st["done"]:,} / {self.st["total"]:,} 張）', cur=''); return
        if self.st['state'] == 'running': self.st.update(state='done', msg=f'分析完成：{self.st["done"]:,} 張', cur='')
        self._backfill_words()

    def _backfill_words(self):
        """Pictures analysed by an older version have no search text yet: read just the embedded text (fast)."""
        with self.lock:
            todo = [r[0] for r in self.db.execute('SELECT path FROM img WHERE words IS NULL AND err IS NULL')]
        if not todo: return
        self.st.update(state='running', done=0, total=len(todo), msg=f'建立文字找圖索引：{len(todo):,} 張')
        rows = []
        for i, p in enumerate(todo):
            if self.stop_ev.is_set() or self.paused: break
            try: w, n = WD.words_of(p, WD.meta_text(p))
            except Exception: w, n = WD.words_of(p, '')
            rows.append((w, n, p)); self.st['done'] = i + 1
            if len(rows) >= 200:
                with self.lock: self.db.executemany('UPDATE img SET words=?, wlen=? WHERE path=?', rows); self.db.commit(); self.ver += 1
                rows = []
        if rows:
            with self.lock: self.db.executemany('UPDATE img SET words=?, wlen=? WHERE path=?', rows); self.db.commit(); self.ver += 1
        self.st.update(state='done', msg='文字找圖索引完成', cur='')

    def _save(self, rows):
        flist = self.folders()                                             # a folder removed while analysing: not saved
        rows = [r for r in rows if any(is_under(r['path'], f) for f in flist)]
        if not rows: return
        cols = ['path', 'folder', 'name', 'size', 'mtime', 'w', 'h', 'taken', 'make', 'model', 'gps', 'c1', 'colors', 'bright', 'sat', 'blur', 'dhash', 'faces', 'shot', 'analyzed', 'err', 'words', 'wlen']
        vals = []
        for r in rows:
            r = dict(r); r['colors'] = json.dumps(r.get('colors'), ensure_ascii=False) if r.get('colors') is not None else None
            vals.append([r.get(c) for c in cols])
        with self.lock:
            self.db.executemany(f'INSERT OR REPLACE INTO img({",".join(cols)}) VALUES({",".join("?" * len(cols))})', vals); self.db.commit(); self.ver += 1

    # ------------------------------------------------------------------ queries
    def _where(self, f):
        w = ['err IS NULL']; a = []
        if f.get('scope'):
            sc = norm(f['scope']).rstrip('\\/'); esc_ = sc.replace('!', '!!').replace('%', '!%').replace('_', '!_')
            w.append('(folder = ?' + (' COLLATE NOCASE' if IS_WIN else '') + " OR folder LIKE ? ESCAPE '!')"); a += [sc, esc_ + os.sep + '%']
        if f.get('color'):
            cs = f['color'] if isinstance(f['color'], list) else [f['color']]
            if f.get('color_any'): w.append('(' + ' OR '.join(['colors LIKE ?'] * len(cs)) + ')'); a += [f'%"{c}"%' for c in cs]
            else: w.append('c1 IN (' + ','.join('?' * len(cs)) + ')'); a += cs
        o = f.get('orient')
        if o == 'portrait': w.append('h > w * 1.05')
        elif o == 'landscape': w.append('w > h * 1.05')
        elif o == 'square': w.append('w <= h * 1.05 AND h <= w * 1.05')
        if f.get('faces') == '0': w.append('faces = 0')
        elif f.get('faces') == '1': w.append('faces = 1')
        elif f.get('faces') == '2': w.append('faces >= 2')
        elif f.get('faces') == 'any': w.append('faces >= 1')
        if f.get('shot') in ('1', '0'): w.append('shot = ?'); a.append(int(f['shot']))
        if f.get('blur') == 'blurry': w.append('blur IS NOT NULL AND blur < 120')
        elif f.get('blur') == 'sharp': w.append('blur >= 400')
        if f.get('bright') == 'dark': w.append('bright < 0.3')
        elif f.get('bright') == 'light': w.append('bright > 0.7')
        if f.get('model'): w.append('model = ?'); a.append(f['model'])
        if f.get('gps') in ('1', '0'): w.append('gps = ?'); a.append(int(f['gps']))
        if f.get('year'): w.append("strftime('%Y', COALESCE(taken, mtime), 'unixepoch', 'localtime') = ?"); a.append(str(f['year']))
        if f.get('month'): w.append("strftime('%m', COALESCE(taken, mtime), 'unixepoch', 'localtime') = ?"); a.append(str(f['month']).zfill(2))
        if f.get('minpx'): w.append('w * h >= ?'); a.append(int(f['minpx']))
        if f.get('star'): w.append('path IN (SELECT path FROM star)')
        if f.get('q'):
            for term in self.terms(f['q']):
                ids = self._text_ids(term)
                if ids is None: continue
                w.append(('rowid NOT IN' if term['neg'] else 'rowid IN') + ' (SELECT value FROM json_each(?))'); a.append(ids)
        return ' AND '.join(w), a

    def _text_ids(self, term):
        """rowids matching one search word (synonyms / colour / holiday dates), as a JSON list. Cached until the
        library changes, so paging and re-sorting are instant."""
        key = (term['word'].lower(), self.ver)
        hit = self._tcache.get(key)
        if hit is not None: return hit
        ors = []; a = []
        needles = [p.strip('%') for syn in term['syn'] for p in WD.like_patterns(syn)]
        for nd in dict.fromkeys(needles): ors.append('instr(words, ?) > 0'); a.append(nd)
        if term['color']: ors.append('c1 = ?'); a.append(term['color'])
        hol = WD.holiday_ranges(term['head']) if term['head'] else None
        if isinstance(hol, tuple):
            md = "strftime('%m-%d', taken, 'unixepoch', 'localtime')"
            if hol[0] <= hol[1]: ors.append(f'(taken IS NOT NULL AND {md} BETWEEN ? AND ?)'); a += [hol[0], hol[1]]
            else: ors.append(f'(taken IS NOT NULL AND ({md} >= ? OR {md} <= ?))'); a += [hol[0], hol[1]]
        elif isinstance(hol, list):
            for t0, t1 in hol: ors.append('(taken BETWEEN ? AND ?)'); a += [t0, t1]
        if not ors: return None
        with self.lock:
            ids = json.dumps([r[0] for r in self.db.execute('SELECT rowid FROM img WHERE ' + ' OR '.join(ors), a)])
        if len(self._tcache) > 64: self._tcache.clear()
        self._tcache[key] = ids
        return ids

    @staticmethod
    def terms(q):
        """'聖誕節 紅 -狗' -> [{word, syn, head, color, neg}]   (space = AND, leading - = NOT)"""
        out = []
        for raw in re.findall(r'-?"[^"]+"|\S+', str(q or '')):
            neg = raw.startswith('-') and len(raw) > 1
            t = raw[1:] if neg else raw
            t = t.strip('"')
            if not t: continue
            syn, head, col = WD.expand(t)
            out.append({'word': t, 'syn': syn, 'head': head, 'color': col, 'neg': neg})
        return out

    def query(self, f, offset=0, limit=600):
        where, a = self._where(f)
        order = {'taken': 'COALESCE(taken, mtime) DESC', 'name': 'name', 'size': 'size DESC', 'bright': 'bright DESC', 'sat': 'sat DESC',
                 'folder': 'folder, name', 'px': 'w * h DESC'}.get(f.get('sort'), 'COALESCE(taken, mtime) DESC')
        with self.lock:
            tot = self.db.execute(f'SELECT COUNT(*) FROM img WHERE {where}', a).fetchone()[0]
            rows = self.db.execute(f'SELECT path, w, h, taken, mtime, c1, colors, faces, shot, model, size, words, wlen FROM img WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?',
                                   a + [int(limit), int(offset)]).fetchall()
        terms = [t for t in self.terms(f.get('q')) if not t['neg']] if f.get('q') else []
        items = []
        for r in rows:
            it = {'path': r[0], 'w': r[1], 'h': r[2], 'taken': r[3], 'mtime': r[4], 'c1': r[5], 'colors': json.loads(r[6]) if r[6] else [],
                  'faces': r[7], 'shot': r[8], 'model': r[9], 'size': r[10]}
            if terms: it['why'] = '；'.join(x for x in (self._why(t, r) for t in terms) if x)
            items.append(it)
        st_ = self.stars_of([x['path'] for x in items])
        for x in items:
            if x['path'] in st_: x['star'] = 1
        out = {'total': tot, 'items': items}
        if terms: out['terms'] = [{'word': t['word'], 'also': [x for x in t['syn'] if x != t['word'].lower()][:14], 'color': t['color'],
                                   'holiday': bool(t['head'] and WD.HOLIDAYS.get(t['head']))} for t in terms]
        return out

    @staticmethod
    def _why(t, r):
        words, wlen, c1, taken = r[11] or '', r[12] or 0, r[5], r[3]
        y = WD.why(words, t['syn'], wlen)
        if y: return y
        if t['color'] and c1 == t['color']: return f'主色是{c1}'
        if t['head'] and WD.HOLIDAYS.get(t['head']) and taken: return f'拍攝日期 {time.strftime("%Y/%m/%d", time.localtime(taken))} 在{t["word"]}期間'
        return ''

    def facets(self, f):
        where, a = self._where({k: v for k, v in f.items() if k in ('scope',)})
        out = {}
        with self.lock:
            out['colors'] = dict(self.db.execute(f'SELECT c1, COUNT(*) FROM img WHERE {where} GROUP BY c1', a).fetchall())
            out['models'] = self.db.execute(f"SELECT model, COUNT(*) FROM img WHERE {where} AND model != '' GROUP BY model ORDER BY 2 DESC LIMIT 30", a).fetchall()
            out['years'] = self.db.execute(f"SELECT strftime('%Y', COALESCE(taken, mtime), 'unixepoch', 'localtime') y, COUNT(*) FROM img WHERE {where} GROUP BY y ORDER BY y DESC", a).fetchall()
            out['faces'] = dict(self.db.execute(f"SELECT CASE WHEN faces IS NULL THEN 'na' WHEN faces = 0 THEN '0' WHEN faces = 1 THEN '1' ELSE '2' END, COUNT(*) FROM img WHERE {where} GROUP BY 1", a).fetchall())
            r = self.db.execute(f'''SELECT SUM(shot = 1), SUM(shot = 0), SUM(blur IS NOT NULL AND blur < 120), SUM(blur >= 400),
                                     SUM(bright < 0.3), SUM(bright > 0.7), SUM(gps = 1), SUM(w * h >= 8000000) FROM img WHERE {where}''', a).fetchone()
            out['shots'], out['noshots'], out['blurry'], out['sharp'], out['dark'], out['light'], out['gps'], out['bigpx'] = [x or 0 for x in r]
            out['stars'] = self.db.execute(f'SELECT COUNT(*) FROM img WHERE {where} AND path IN (SELECT path FROM star)', a).fetchone()[0]
            out['total'] = self.db.execute(f'SELECT COUNT(*) FROM img WHERE {where}', a).fetchone()[0]
            out['orient'] = dict(self.db.execute(f"SELECT CASE WHEN h > w * 1.05 THEN 'portrait' WHEN w > h * 1.05 THEN 'landscape' ELSE 'square' END, COUNT(*) FROM img WHERE {where} GROUP BY 1", a).fetchall())
        out['face_engine'] = face_detector() is not None
        return out

    def similar(self, path, limit=200, max_dist=18, scope=''):
        with self.lock:
            r = self.db.execute('SELECT dhash, colors FROM img WHERE path = ?', (path,)).fetchone()
            if not r or r[0] is None: raise ValueError('這張還沒分析')
            where, a = self._where({'scope': scope})
            rows = self.db.execute(f'SELECT path, dhash, colors, w, h, taken, mtime, c1 FROM img WHERE {where} AND dhash IS NOT NULL', a).fetchall()
        h0 = r[0]; c0 = dict(json.loads(r[1] or '[]'))
        scored = []
        for p, hsh, cols, w, hh, tk, mt, c1 in rows:
            d = hamming(h0, hsh)
            if d > max_dist: continue
            cd = sum(abs(c0.get(k, 0) - v) for k, v in dict(json.loads(cols or '[]')).items()) if cols else 1
            scored.append((d + cd * 10, p, w, hh, tk, mt, c1, d))
        scored.sort()
        return [{'path': p, 'w': w, 'h': hh, 'taken': tk, 'mtime': mt, 'c1': c1, 'dist': d} for s, p, w, hh, tk, mt, c1, d in scored[:limit]]

    def series(self, scope='', gap=180, max_dist=22, min_size=3, limit=500):
        """相近套圖: pictures of one folder taken close together that look alike -> groups."""
        where, a = self._where({'scope': scope})
        with self.lock:
            rows = self.db.execute(f'SELECT path, folder, COALESCE(taken, mtime), dhash, w, h, c1 FROM img WHERE {where} AND dhash IS NOT NULL ORDER BY folder, 3', a).fetchall()
        groups = []; cur = []
        for row in rows:
            if cur:
                last = cur[-1]
                same = row[1] == last[1] and abs(row[2] - last[2]) <= gap and (hamming(row[3], last[3]) <= max_dist or abs(row[2] - last[2]) <= 3)
                if not same:
                    if len(cur) >= min_size: groups.append(cur)
                    cur = []
            cur.append(row)
        if len(cur) >= min_size: groups.append(cur)
        groups.sort(key=lambda g: -len(g))
        return [{'folder': g[0][1], 't0': g[0][2], 't1': g[-1][2], 'n': len(g), 'items': [{'path': x[0], 'w': x[4], 'h': x[5], 'c1': x[6]} for x in g]}
                for g in groups[:limit]]

    def taken_of(self, paths):
        """{path: date taken} for the batch-rename {taken} token: the analysis database first, then the EXIF header."""
        out = {}
        with self.lock:
            for i in range(0, len(paths), 500):
                chunk = paths[i:i + 500]
                for p, t in self.db.execute(f'SELECT path, taken FROM img WHERE path IN ({",".join("?" * len(chunk))})', chunk):
                    if t: out[p] = t
        for p in paths:
            if p not in out and os.path.splitext(p)[1].lower() in EXTS:
                t = exif_taken(p)
                if t: out[p] = t
        return out

    def set_star(self, paths, on):
        with self.lock:
            if on: self.db.executemany('INSERT OR REPLACE INTO star VALUES(?,?)', [(norm(p), time.time()) for p in paths])
            else: self.db.executemany('DELETE FROM star WHERE path=?', [(norm(p),) for p in paths])
            self.db.commit()
        return True

    def move_stars(self, pairs):
        """Files were renamed / moved: their favourites (and folders' favourites inside) follow them."""
        if not pairs: return
        with self.lock:
            have = self.db.execute('SELECT COUNT(*) FROM star').fetchone()[0]
            if not have: return
            for old, new in pairs:
                old, new = norm(old), norm(new)
                self.db.execute('UPDATE OR REPLACE star SET path=? WHERE path=?', (new, old))
                pre = old.rstrip('\\/') + os.sep
                for (p,) in self.db.execute('SELECT path FROM star WHERE substr(path, 1, ?) = ?', (len(pre), pre)).fetchall():
                    self.db.execute('UPDATE OR REPLACE star SET path=? WHERE path=?', (new.rstrip('\\/') + os.sep + p[len(pre):], p))
            self.db.commit()

    def stars_of(self, paths):
        with self.lock:
            out = set()
            for i in range(0, len(paths), 500):
                ch = paths[i:i + 500]
                out |= {r[0] for r in self.db.execute(f'SELECT path FROM star WHERE path IN ({",".join("?" * len(ch))})', ch)}
        return out

    def forget(self, folder):
        """A folder was removed from the analysis list: drop its results (the pictures themselves are not touched)."""
        sc = norm(folder).rstrip('\\/'); esc_ = sc.replace('!', '!!').replace('%', '!%').replace('_', '!_')
        if any(is_under(sc, f) for f in self.folders()): return 0                # still covered by a parent folder
        with self.lock:
            n = self.db.execute('DELETE FROM img WHERE folder = ?' + (' COLLATE NOCASE' if IS_WIN else '') + " OR folder LIKE ? ESCAPE '!'", (sc, esc_ + os.sep + '%')).rowcount
            self.db.commit(); self.ver += 1
        return n

    def neardupes(self, scope='', max_dist=4, limit=2000):
        """近似重複: the same picture saved twice (resized, re-compressed, converted, a few pixels cropped).
        dHash split into 4 bands of 16 bits -> two pictures within 3 bits always share a band (pigeonhole), so only
        pictures sharing a band are compared. Plus: same aspect ratio (±3%) and similar colours.
        The suggested keeper = most pixels, then sharpest, then biggest file, then oldest."""
        where, a = self._where({'scope': scope})
        with self.lock:
            rows = self.db.execute(f'SELECT path, dhash, w, h, size, blur, mtime, colors, c1 FROM img WHERE {where} AND dhash IS NOT NULL AND w > 0 AND h > 0', a).fetchall()
        nb = max(2, min(5, int(max_dist) + 1))                              # d+1 bands: any pair within d bits shares one
        cuts = [round(64 * k / nb) for k in range(nb + 1)]
        bands = [dict() for _ in range(nb)]
        for i, r in enumerate(rows):
            u = r[1] & 0xFFFFFFFFFFFFFFFF
            for b in range(nb): bands[b].setdefault((u >> cuts[b]) & ((1 << (cuts[b + 1] - cuts[b])) - 1), []).append(i)
        parent = list(range(len(rows)))
        def find(x):
            while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
            return x
        cols = [dict(json.loads(r[7] or '[]')) for r in rows]
        for b in range(nb):
            for bucket in bands[b].values():
                if len(bucket) < 2 or len(bucket) > 400: continue           # a huge bucket = flat images (all black etc.)
                for x in range(len(bucket)):
                    i = bucket[x]; ri = rows[i]; ar_i = ri[2] / ri[3]
                    for y in range(x + 1, len(bucket)):
                        j = bucket[y]
                        if find(i) == find(j): continue                    # already together (no memory per pair)
                        rj = rows[j]
                        if abs(ar_i - rj[2] / rj[3]) > 0.03 * ar_i: continue
                        if hamming(ri[1], rj[1]) > max_dist: continue
                        if sum(abs(cols[i].get(k, 0) - cols[j].get(k, 0)) for k in set(cols[i]) | set(cols[j])) > 0.35: continue
                        parent[find(i)] = find(j)
        groups = {}
        for i in range(len(rows)): groups.setdefault(find(i), []).append(i)
        out = []
        for g in groups.values():
            if len(g) < 2: continue
            g = [i for i in g if os.path.exists(W.lp(rows[i][0]))]           # already moved away since the last pass
            if len(g) < 2: continue
            items = [{'path': rows[i][0], 'w': rows[i][2], 'h': rows[i][3], 'size': rows[i][4], 'blur': rows[i][5], 'mtime': rows[i][6], 'c1': rows[i][8]} for i in g]
            items.sort(key=lambda x: (-(x['w'] * x['h']), -(x['blur'] or 0), -(x['size'] or 0), x['mtime'] or 0))
            items[0]['keep'] = True
            out.append({'n': len(items), 'save': sum(x['size'] or 0 for x in items[1:]), 'items': items})
        out.sort(key=lambda g: -g['save'])
        return out[:limit]

    def status(self):
        with self.lock:
            n = self.db.execute('SELECT COUNT(*) FROM img WHERE err IS NULL').fetchone()[0]
        return dict(self.st, analyzed=n, folders=self.folders(), paused=self.paused, face_engine=face_detector() is not None)

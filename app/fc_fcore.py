"""FileCompare 的工具函式（不准 import Qt）：掃描資料夾、算指紋、損毀檢查、縮圖、隔離（搬檔／復原）。
引擎（core.Engine）在背景執行緒呼叫這些；畫面和手機網頁都不直接碰檔案。

安全規則：
- 從來不刪使用者的檔案。「隔離」＝同一顆硬碟內搬到 <磁碟>:\\_FileCompare_待確認\\<原因>\\<原本的路徑>，可以復原。
- 長路徑（超過 260 字）一律加 \\\\?\\ 前綴。
"""
import os, re, time, hashlib, shutil, struct, subprocess, mmap
from pathlib import Path

PHOTO = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp', '.bmp', '.gif', '.tif', '.tiff', '.nef', '.dng', '.cr2', '.cr3', '.arw', '.raf', '.rw2'}
VIDEO = {'.mp4', '.mov', '.m4v', '.avi', '.mkv', '.3gp', '.wmv', '.mts', '.m2ts', '.flv', '.webm', '.mpg', '.mpeg'}
RAW = {'.nef', '.dng', '.cr2', '.cr3', '.arw', '.raf', '.rw2'}
QUAR_NAME = '_FileCompare_待確認'
CONV_QUAR_NAME = '_FileCompare_轉檔後隔離區'                                   # 🗜 影片瘦身（轉 H.265）的原檔另外放，不跟一般隔離區混（V0.4.61）
REPAIR_NAME = '_FileCompare_修復結果'
SKIP_DIRS = {'$recycle.bin', 'system volume information', QUAR_NAME.lower(), CONV_QUAR_NAME.lower(), REPAIR_NAME.lower(), 'filecompare_問題影片', '.vsdata', '_vs_tmp'}      # 🧹 delete／check video／repeat 跟隔離區一樣不再掃
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
HEAD = 65536


def kind_of(ext):
    e = (ext or '').lower()
    return 'photo' if e in PHOTO else 'video' if e in VIDEO else ''


def lp(p):
    """Windows 長路徑：C:\\... → \\\\?\\C:\\...（已經有前綴、或不是 Windows 就不動）."""
    p = str(p)
    if os.name != 'nt' or p.startswith('\\\\?\\'): return p
    p = os.path.abspath(p)
    return '\\\\?\\UNC\\' + p[2:] if p.startswith('\\\\') else '\\\\?\\' + p


def unlp(p):
    p = str(p)
    return '\\\\' + p[8:] if p.startswith('\\\\?\\UNC\\') else p[4:] if p.startswith('\\\\?\\') else p


def run(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=NO_WINDOW | (0x00004000 if os.name == 'nt' else 0), stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout.decode('utf-8', 'replace'), r.stderr.decode('utf-8', 'replace')
    except subprocess.TimeoutExpired: return -9, '', '逾時'
    except Exception as ex: return -1, '', f'{type(ex).__name__}: {ex}'


# ---------------------------------------------------------------- 掃描
def walk(root):
    """一層一層往下找檔案：產生 (路徑, 大小, 修改時間, 副檔名)。跳過資源回收筒、系統資料夾、隔離區、捷徑型資料夾（junction）."""
    stack = [str(root)]
    while stack:
        d = stack.pop()
        try: it = os.scandir(lp(d))
        except OSError: continue
        with it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.name.lower() in SKIP_DIRS: continue
                        st = e.stat(follow_symlinks=False)
                        if getattr(st, 'st_file_attributes', 0) & 0x400: continue      # reparse point（junction／symlink）
                        stack.append(os.path.join(d, e.name))
                    elif e.is_file(follow_symlinks=False):
                        st = e.stat(follow_symlinks=False)
                        yield os.path.join(d, e.name), st.st_size, st.st_mtime, os.path.splitext(e.name)[1].lower()
                except OSError: continue


# ---------------------------------------------------------------- 指紋（比對重複：大小一樣才算；先比頭尾，頭尾也一樣才讀完整個檔）
def qhash(path, size):
    h = hashlib.sha1(str(size).encode())
    with open(lp(path), 'rb') as fh:
        h.update(fh.read(HEAD))
        if size > HEAD * 2: fh.seek(size - HEAD)
        h.update(fh.read(HEAD))
    return h.hexdigest()


def fhash(path, stop=None):
    h = hashlib.sha1()
    with open(lp(path), 'rb') as fh:
        while True:
            b = fh.read(4 << 20)
            if not b: break
            h.update(b)
            if stop is not None and stop(): raise InterruptedError
    return h.hexdigest()


# ---------------------------------------------------------------- FFmpeg
def find_ff(root=None):
    """ffmpeg.exe／ffprobe.exe：程式資料夾 → AppBuilder 快取 → PATH。回傳 (ffmpeg, ffprobe)，找不到是 ''."""
    cands = []
    if root: cands.append(Path(root))
    la = os.environ.get('LOCALAPPDATA')
    if la: cands.append(Path(la) / 'AppBuilder' / 'ffmpeg711')
    out = []
    for n in ('ffmpeg', 'ffprobe'):
        f = next((str(c / (n + '.exe')) for c in cands if (c / (n + '.exe')).is_file()), '') or shutil.which(n) or ''
        out.append(f)
    return tuple(out)


IGNORE_ERR = re.compile(r'deprecated pixel format|Application provided invalid, non monotonically|No accelerated colorspace|Last message repeated', re.I)


FF_TAG = re.compile(r'\[[\w,]+ @ (0x)?[0-9a-fA-F]+\]\s*')


def _errs(txt):
    return [FF_TAG.sub('', ln).strip() for ln in (txt or '').splitlines() if ln.strip() and not IGNORE_ERR.search(ln)]


# ---------------------------------------------------------------- 損毀檢查
def _jpeg_check(data):
    """JPEG 結構：SOI → 各段（照長度跳過，裡面的小縮圖不會誤判）→ SOS → 第一個 FFD9＝結尾。
    結尾後面還有資料沒關係（小米／三星的動態照片會把影片接在後面）."""
    if data[:2] != b'\xff\xd8': return 'broken', '不是 JPEG 開頭（內容可能被別的資料蓋掉）'
    i, n, sos = 2, len(data), -1
    while i + 4 <= n:
        if data[i] != 0xFF: return 'broken', f'JPEG 結構壞掉（第 {i:,} 位元組）'
        m = data[i + 1]
        if m == 0xFF: i += 1; continue
        if m == 0xD9: return 'broken', 'JPEG 沒有影像資料'
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7: i += 2; continue
        ln = struct.unpack('>H', data[i + 2:i + 4])[0]
        if m == 0xDA: sos = i + 2 + ln; break
        i += 2 + ln
    if sos < 0: return 'broken', 'JPEG 找不到影像資料（檔案太短或被截斷）'
    eoi = data.find(b'\xff\xd9', sos)
    if eoi < 0: return 'partial', f'結尾不完整（只救回 {n / 1e6:.1f} MB，後半段可能灰掉／缺一塊）'
    body = data[sos:eoi]
    if len(body) > 65536:
        z = body.count(b'\x00' * 4096)
        if z * 4096 > len(body) * 0.25: return 'partial', f'影像資料有一大段是 0（約 {z * 4096 * 100 // len(body)}%，畫面可能缺一塊）'
    return 'ok', ''


def pixel_stats(px):
    """48×48 RGB → (綠色比例, 最多的那個顏色的比例)。缺資料的 JPEG 解碼後會被填成綠色（FFmpeg）或灰色."""
    n = len(px) // 3
    if n == 0: return -1.0, -1.0
    g = 0; C = {}
    for i in range(n):
        r, gg, b = px[3 * i], px[3 * i + 1], px[3 * i + 2]
        if r < 40 and 100 < gg < 170 and b < 40: g += 1
        k = (r >> 4, gg >> 4, b >> 4); C[k] = C.get(k, 0) + 1
    return round(g / n, 3), round(max(C.values()) / n, 3)


def check_photo_ex(path, size, ff='', deep=True):
    """回傳 (狀態, 說明, 綠色比例)：ok／partial（部分損毀，可能還看得到）／broken（打不開）／zero（0 位元組）。綠色比例 -1＝沒算."""
    if size == 0: return 'zero', '0 位元組（沒有內容）', -1.0
    ext = os.path.splitext(path)[1].lower()
    try:
        with open(lp(path), 'rb') as fh: data = fh.read() if size <= 80 << 20 else fh.read(HEAD)
    except OSError as ex: return 'broken', f'讀不到：{ex.strerror or ex}', -1.0
    if not data[:HEAD].strip(b'\x00'): return 'broken', '開頭全是 0（救援時沒救到內容）', -1.0
    st, msg = 'ok', ''
    if ext in ('.jpg', '.jpeg'): st, msg = _jpeg_check(data)
    elif ext == '.png':
        if data[:8] != b'\x89PNG\r\n\x1a\n': st, msg = 'broken', '不是 PNG 開頭'
        elif b'IEND' not in data[-64:]: st, msg = 'partial', '結尾不完整（下半部可能缺）'
    if st == 'broken' or not deep or not ff or ext in RAW: return st, msg, -1.0
    try:
        r = subprocess.run([ff, '-hide_banner', '-v', 'error', '-i', path, '-frames:v', '1', '-vf', 'scale=48:48:flags=area,format=rgb24', '-f', 'rawvideo', '-'],
                           capture_output=True, timeout=90, creationflags=NO_WINDOW | (0x00004000 if os.name == 'nt' else 0), stdin=subprocess.DEVNULL)
        rc, px, err = r.returncode, r.stdout, r.stderr.decode('utf-8', 'replace')
    except subprocess.TimeoutExpired: rc, px, err = -9, b'', '逾時'
    except Exception as ex: rc, px, err = -1, b'', f'{type(ex).__name__}: {ex}'
    E = _errs(err)
    if rc != 0 and not E: E = [f'FFmpeg 結束碼 {rc}']
    if rc != 0 or not px: return 'broken', '打不開：' + ' / '.join(E[:2])[:300], -1.0
    green, dom = pixel_stats(px)
    if green >= 0.9: return 'broken', f'畫面幾乎全是綠色（{int(green * 100)}%）：只救回一點點內容，看不到東西', green
    if green >= 0.25: return 'partial', f'畫面有 {int(green * 100)}% 是綠色：缺了一大塊' + ('（' + msg + '）' if msg else ''), green
    if dom >= 0.985 and st == 'ok': return 'partial', '整張幾乎是同一個顏色：可能是空白或壞掉的圖', green
    if E and st == 'ok': return 'partial', '解碼有錯誤：' + ' / '.join(E[:2])[:300], green
    return st, msg, green


def check_photo(path, size, ff='', deep=True):
    st, msg, _g = check_photo_ex(path, size, ff, deep); return st, msg


def probe_dur(fp, path):
    rc, out, err = run([fp, '-hide_banner', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', path], 60)
    try: d = float((out or '').strip().splitlines()[0])
    except Exception: d = 0.0
    return rc, d, _errs(err)


def check_video(path, size, ff='', fp='', deep=True):
    """回傳 (狀態, 說明, 長度秒)。抽頭、中間、尾巴各 2 秒解碼（不用整部播完）."""
    if size == 0: return 'zero', '0 位元組（沒有內容）', 0.0
    try:
        with open(lp(path), 'rb') as fh: head = fh.read(HEAD)
    except OSError as ex: return 'broken', f'讀不到：{ex.strerror or ex}', 0.0
    if not head.strip(b'\x00'): return 'broken', '開頭全是 0（救援時沒救到內容）', 0.0
    if not fp or not ff: return 'ok', '（沒有 FFmpeg，只檢查了開頭）', 0.0
    rc, dur, E = probe_dur(fp, path)
    if rc != 0 or dur <= 0:
        try:
            with open(lp(path), 'rb') as fh: sig = fh.read(12)[4:8]
        except OSError: sig = b''
        txt = ' '.join(E)
        if 'moov atom not found' in txt:
            why = '影片索引（moov）不見了：檔案被截斷，或救援時沒救完整' if sig == b'ftyp' else '開頭不是影片格式（救援時救到別的資料）'
        else: why = '讀不到影片長度：' + ' / '.join(E[:2])[:200] if E else '讀不到影片長度'
        return 'broken', '打不開：' + why, 0.0
    if not deep: return 'ok', '', dur
    pts = sorted({0.0, round(dur / 2, 2), round(max(0.0, dur - 3), 2)}); bad = []
    for t in pts:
        rc, _o, err = run([ff, '-hide_banner', '-v', 'error', '-ss', f'{t:.2f}', '-i', path, '-t', '2', '-map', '0:v:0?', '-f', 'null', '-'], 120)
        e = _errs(err)
        if rc != 0 and not e: e = [f'FFmpeg 結束碼 {rc}']
        if e: bad.append((t, e))
    if not bad: return 'ok', '', dur
    if len(bad) == len(pts): return 'partial', f'抽查 {len(pts)} 段都有解碼錯誤（可能整部都壞）：' + bad[0][1][0][:200], dur
    return 'partial', '、'.join(f'{int(t // 60)}:{int(t % 60):02d}' for t, _e in bad) + ' 附近解碼有錯誤：' + bad[0][1][0][:200], dur


# ---------------------------------------------------------------- 拍攝資訊（EXIF／影片標籤／檔名日期／來源）：之後篩選、按年月整理、找相似照片用
def _exif_date(s):
    m = re.match(r'\s*(\d{4})[:\-](\d{2})[:\-](\d{2})[ T](\d{2}):(\d{2}):(\d{2})', str(s or ''))
    if not m: return None
    try:
        y = int(m.group(1))
        if not 1990 <= y <= 2100: return None
        return time.mktime((y, int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6)), 0, 0, -1))
    except (ValueError, OverflowError): return None


def parse_exif(t):
    """TIFF／EXIF 區塊 → {make, model, software, dt, orient, w, h, lat, lon}。壞掉的 EXIF 就回傳讀得到的部分."""
    M = {}
    if t[:2] == b'II': e = '<'
    elif t[:2] == b'MM': e = '>'
    else: return M
    SZ = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}
    def u16(o): return struct.unpack(e + 'H', t[o:o + 2])[0]
    def u32(o): return struct.unpack(e + 'I', t[o:o + 4])[0]
    def ifd(off):
        D = {}
        if off <= 0 or off + 2 > len(t): return D
        for k in range(min(u16(off), 400)):
            p = off + 2 + k * 12
            if p + 12 > len(t): break
            tag, typ, cnt = u16(p), u16(p + 2), u32(p + 4); n = SZ.get(typ, 1) * cnt
            vo = p + 8 if n <= 4 else u32(p + 8)
            if vo + n > len(t): continue
            raw = t[vo:vo + n]
            if typ == 2: D[tag] = raw.split(b'\x00')[0].decode('utf-8', 'replace').strip()
            elif typ == 3: D[tag] = struct.unpack(e + 'H' * cnt, raw)[0] if cnt == 1 else struct.unpack(e + 'H' * cnt, raw)
            elif typ in (4, 9): D[tag] = struct.unpack(e + ('I' if typ == 4 else 'i') * cnt, raw)[0] if cnt == 1 else None
            elif typ in (5, 10): D[tag] = [a / b if b else 0.0 for a, b in zip(*[iter(struct.unpack(e + ('I' if typ == 5 else 'i') * (2 * cnt), raw))] * 2)]
            else: D[tag] = raw[:8]
        return D
    try:
        I0 = ifd(u32(4))
        M.update(make=I0.get(0x010F, ''), model=I0.get(0x0110, ''), software=I0.get(0x0131, ''), orient=I0.get(0x0112) if isinstance(I0.get(0x0112), int) else 0)
        EX = ifd(I0[0x8769]) if isinstance(I0.get(0x8769), int) else {}
        M['dt'] = _exif_date(EX.get(0x9003) or EX.get(0x9004) or I0.get(0x0132))
        if isinstance(EX.get(0xA002), int) and isinstance(EX.get(0xA003), int): M['w'], M['h'] = EX[0xA002], EX[0xA003]
        G = ifd(I0[0x8825]) if isinstance(I0.get(0x8825), int) else {}
        if isinstance(G.get(2), list) and isinstance(G.get(4), list) and len(G[2]) == 3 and len(G[4]) == 3:
            lat = G[2][0] + G[2][1] / 60 + G[2][2] / 3600; lon = G[4][0] + G[4][1] / 60 + G[4][2] / 3600
            if str(G.get(1, 'N')).upper().startswith('S'): lat = -lat
            if str(G.get(3, 'E')).upper().startswith('W'): lon = -lon
            if abs(lat) > 0.0001 or abs(lon) > 0.0001: M['lat'], M['lon'] = round(lat, 6), round(lon, 6)
    except Exception: pass
    return M


def jpeg_meta(data):
    """JPEG 開頭（EXIF、尺寸、是不是動態照片）."""
    M = {}; i, n = 2, len(data)
    if data[:2] != b'\xff\xd8': return M
    while i + 4 <= n:
        if data[i] != 0xFF: break
        m = data[i + 1]
        if m == 0xFF: i += 1; continue
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7: i += 2; continue
        ln = struct.unpack('>H', data[i + 2:i + 4])[0]; seg = data[i + 4:i + 2 + ln]
        if m == 0xE1 and seg[:6] == b'Exif\x00\x00' and 'dt' not in M: M.update(parse_exif(seg[6:]))
        elif m == 0xE1 and b'ns.adobe.com/xap' in seg[:40] and (b'MicroVideo' in seg or b'MotionPhoto' in seg): M['motion'] = 1
        elif m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF) and len(seg) >= 5:
            M['h'], M['w'] = struct.unpack('>HH', seg[1:5])
        if m == 0xDA: break
        i += 2 + ln
    if M.get('orient') in (5, 6, 7, 8) and M.get('w'): M['w'], M['h'] = M['h'], M['w']     # 直拍：EXIF 轉向後的寬高
    return M


def png_meta(data):
    return {'w': struct.unpack('>I', data[16:20])[0], 'h': struct.unpack('>I', data[20:24])[0]} if data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24 else {}


def probe_meta(fp, path):
    """FFprobe：寬高、長度、編碼、建立時間、所有標籤（抖音的 vid:、手機廠牌…）."""
    rc, out, _e = run([fp, '-hide_banner', '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', '-select_streams', 'v:0', path], 60)
    M = {}
    try: j = __import__('json').loads(out or '{}')
    except Exception: return M
    st = (j.get('streams') or [{}])[0] if j.get('streams') else {}; fo = j.get('format') or {}
    tags = {str(k).lower(): str(v) for k, v in dict(fo.get('tags') or {}, **(st.get('tags') or {})).items()}
    w, h = int(st.get('width') or 0), int(st.get('height') or 0)
    rot = 0
    try: rot = int(float(tags.get('rotate') or next((sd.get('rotation') for sd in st.get('side_data_list') or [] if 'rotation' in sd), 0) or 0))
    except Exception: pass
    if abs(rot) in (90, 270): w, h = h, w
    M.update(w=w, h=h, vcodec=str(st.get('codec_name') or ''), tags=tags)
    try: M['dur'] = float(fo.get('duration') or st.get('duration') or 0)
    except Exception: pass
    ct = tags.get('com.apple.quicktime.creationdate') or tags.get('creation_time') or ''
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})', ct)
    if m and 1990 <= int(m.group(1)) <= 2100:
        try:
            import calendar
            tt = tuple(int(x) for x in m.groups()) + (0, 0, -1)
            M['dt'] = calendar.timegm(tt) if (ct.endswith('Z') or 'creation_time' in tags and ct == tags.get('creation_time') and not re.search(r'[+-]\d{2}:?\d{2}$', ct)) else time.mktime(tt)
        except Exception: pass
    M['make'] = tags.get('com.apple.quicktime.make') or tags.get('com.android.manufacturer') or tags.get('make') or ''
    M['model'] = tags.get('com.apple.quicktime.model') or tags.get('com.android.model') or tags.get('model') or ''
    M['software'] = tags.get('com.apple.quicktime.software') or tags.get('encoder') or tags.get('software') or ''
    loc = tags.get('location') or tags.get('com.apple.quicktime.location.iso6709') or ''
    g = re.match(r'([+-]\d+\.\d+)([+-]\d+\.\d+)', loc)
    if g: M['lat'], M['lon'] = float(g.group(1)), float(g.group(2))
    return M


NAME_DATES = [
    (re.compile(r'(?:mmexport|wx_camera_|_|^)(1[3-7]\d{11})(?!\d)'), 'ms'),                 # 微信等：13 位數毫秒時間
    (re.compile(r'(?<!\d)((?:199[5-9]|20[0-3]\d))[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])(?:[ _\-T.]?([01]\d|2[0-3])[-_.:]?([0-5]\d)[-_.:]?([0-5]\d))?(?!\d)'), 'ymd'),
    (re.compile(r'(?<!\d)(1[3-7]\d{8})(?!\d)'), 's'),                                        # 10 位數秒
]


def name_date(name):
    """檔名裡的日期（IMG_20220101_120000、Screenshot_2022-01-01、mmexport1640000000000…）."""
    b = os.path.splitext(os.path.basename(name))[0]
    for rx, k in NAME_DATES:
        m = rx.search(b)
        if not m: continue
        try:
            if k == 'ms': return int(m.group(1)) / 1000.0
            if k == 's': return float(m.group(1))
            g = [int(x) if x else 0 for x in m.groups()]
            return time.mktime((g[0], g[1], g[2], g[3], g[4], g[5], 0, 0, -1))
        except (ValueError, OverflowError): continue
    return None


SRC_NM = {'camera': '📷 手機／相機拍的', 'screenshot': '🖥 截圖', 'douyin': '🎵 抖音', 'inshot': '✂ InShot 剪輯', 'capcut': '✂ 剪映／CapCut', 'wechat': '💬 微信／LINE 等',
          'edited': '🎨 修圖／編輯過', 'recovered': '🛟 救援軟體救回（檔名被改掉）', 'thumb': '🗂 手機縮圖快取（.thumbnails）', 'download': '⬇ 下載／不明來源'}
RECOVER_NAME = re.compile(r'^(img|vid|mov|mp4)_\d+x\d+(x\d+)?_\d+|^(file|f|_)\d{5,}$|^\d{6,8}$|^[0-9a-f]{8}-[0-9a-f]{4}-', re.I)
RECOVER_DIR = re.compile(r'深度[扫掃]描|丢失文件|遺失檔案|丟失文件|recovered|easeus|recuva|photorec|diskgenius|\\found\.\d+\\|lost\.dir', re.I)
EDIT_SW = re.compile(r'photoshop|lightroom|snapseed|meitu|美[图圖]|醒[图圖]|picsart|vsco|faceu|b612|wink|beautycam|polarr|gimp|canva|snow', re.I)
CAMERA_NAME = re.compile(r'^(img|vid|dsc|dscn|dscf|mvimg|pxl|pano|burst|p\d{7}|dji|gopr|gp\d|lrv|mov|mvi|sam|cimg|photo|video)[_\-]?\d', re.I)


def classify(name, kind, M):
    n = os.path.basename(name).lower(); sw = (M.get('software') or '').lower(); tags = ' '.join(f'{k}={v}' for k, v in (M.get('tags') or {}).items()).lower()
    full = unlp(name).lower(); stem = os.path.splitext(n)[0]
    if re.search(r'[\\/](\.thumbnails|\.thumbs|thumbnails|\.thumbcache|cache[\\/]+thumb)', full): return 'thumb'
    if not (M.get('make') or M.get('model')) and (RECOVER_NAME.match(stem) or RECOVER_DIR.search(full)): return 'recovered'
    if n.startswith('inshot') or 'inshot' in sw: return 'inshot'
    if 'capcut' in sw or '剪映' in sw or 'capcut' in n or '剪映' in n or 'capcut' in tags: return 'capcut'
    if re.search(r'screenshot|screen_shot|screen shot|screenrecord|screen_record|截[图圖屏]|螢幕擷取|擷取畫面|snipaste|屏幕录制|螢幕錄製', n): return 'screenshot'
    if 'vid:v0' in tags or 'douyin' in tags or 'aweme' in tags or 'douyin' in n or '抖音' in n or re.match(r'^v[0-9a-z]{4}g[0-9a-z]{16,}', n): return 'douyin'
    if n.startswith(('mmexport', 'wx_camera', 'microsoft', 'line_', 'messenger', 'received_', 'telegram', 'signal-')): return 'wechat'
    if EDIT_SW.search(sw): return 'edited'
    if M.get('make') or M.get('model') or CAMERA_NAME.match(n) or 'com.android' in tags or 'com.apple.quicktime' in tags: return 'camera'
    return 'download'


def dhash(ff, path):
    """相似照片的指紋（64 位元）：縮成 9×8 灰階，比左右亮暗。看起來一樣的照片（被壓縮過、改過大小）指紋會很接近."""
    if not ff: return ''
    try:
        r = subprocess.run([ff, '-hide_banner', '-v', 'error', '-i', path, '-frames:v', '1', '-vf', 'scale=9:8:flags=area,format=gray', '-f', 'rawvideo', '-'],
                           capture_output=True, timeout=60, creationflags=NO_WINDOW | (0x00004000 if os.name == 'nt' else 0), stdin=subprocess.DEVNULL)
        px = r.stdout[:72]
        if len(px) < 72: return ''
        bits = 0
        for y in range(8):
            for x in range(8): bits = (bits << 1) | (1 if px[y * 9 + x] > px[y * 9 + x + 1] else 0)
        return f'{bits:016x}'
    except Exception: return ''


def read_meta(path, size, kind, ff='', fp='', want_dhash=True):
    """一個檔案的所有資訊 → dict（給資料庫）：taken（拍攝時間）、date_src（exif／video／name／mtime）、src（來源）…"""
    ext = os.path.splitext(path)[1].lower(); M = {}
    try:
        if kind == 'photo' and ext in ('.jpg', '.jpeg', '.png'):
            with open(lp(path), 'rb') as fh: head = fh.read(512 * 1024)
            M = jpeg_meta(head) if ext != '.png' else png_meta(head)
        if (kind == 'video' or (kind == 'photo' and not M.get('w'))) and fp and size > 0: M = dict(probe_meta(fp, path), **{k: v for k, v in M.items() if v})
    except OSError: pass
    nd = name_date(path); dt = M.get('dt')
    try: mt = os.path.getmtime(lp(path))
    except OSError: mt = 0.0
    taken, dsrc = (dt, 'exif' if kind == 'photo' else 'video') if dt else ((nd, 'name') if nd else (mt, 'mtime'))
    src = classify(path, kind, M)
    w, h = int(M.get('w') or 0), int(M.get('h') or 0)
    return {'taken': taken, 'date_src': dsrc, 'name_date': nd or 0, 'make': str(M.get('make') or '')[:60], 'model': str(M.get('model') or '')[:80], 'software': str(M.get('software') or '')[:80],
            'w': w, 'h': h, 'mp': round(w * h / 1e6, 2), 'gps': 1 if 'lat' in M else 0, 'lat': M.get('lat'), 'lon': M.get('lon'), 'src': src, 'vcodec': M.get('vcodec', ''),
            'motion': int(M.get('motion') or 0), 'mdur': float(M.get('dur') or 0),
            'dhash': dhash(ff, path) if want_dhash and kind == 'photo' and size > 0 and ext not in RAW else ''}


# ---------------------------------------------------------------- 🛠 修復／救出（原檔完全不動；結果放在 <磁碟>:\_FileCompare_修復結果\<原本的路徑>\）
def repair_dir(path):
    drv, rest = os.path.splitdrive(unlp(path))
    return os.path.join(drv + '\\', REPAIR_NAME, rest.lstrip('\\/'))


def _sos_after(mm, i, n):
    """從 SOI（i）照長度跳過各段，回傳影像資料開始的位置；不是 JPEG 結構就回傳 -1."""
    j = i + 2
    while j + 4 <= n and mm[j] == 0xFF:
        m = mm[j + 1]
        if m == 0xFF: j += 1; continue
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7: j += 2; continue
        ln = struct.unpack('>H', mm[j + 2:j + 4])[0]
        if ln < 2: return -1
        if m == 0xDA: return j + 2 + ln
        j += 2 + ln
    return -1


def carve_jpegs(path, out_dir, min_size=30000, limit=800, stop=None, skip0=False):
    """在檔案裡找完整的 JPEG（救援軟體常把好幾張照片混成一個檔；照片裡也有內嵌的小縮圖）→ 001.jpg、002.jpg…。回傳 [(路徑, 大小, sha1)]."""
    res = []; seen = set()
    with open(lp(path), 'rb') as fh:
        try: mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        except (ValueError, OSError): return res
        try:
            n = len(mm); i = 0
            while len(res) < limit:
                i = mm.find(b'\xff\xd8\xff', i)
                if i < 0: break
                if stop is not None and stop(): raise InterruptedError
                if i == 0 and skip0: i = 3; continue
                s = _sos_after(mm, i, n)
                e = mm.find(b'\xff\xd9', s, min(n, s + (60 << 20))) if s > 0 else -1
                if e < 0: i += 3; continue
                if e + 2 - i < min_size: i += 3; continue
                blob = mm[i:e + 2]; h = hashlib.sha1(blob).hexdigest()
                if h not in seen:
                    seen.add(h); op = os.path.join(out_dir, f'{len(res) + 1:03d}.jpg'); os.makedirs(lp(out_dir), exist_ok=True)
                    with open(lp(op), 'wb') as o: o.write(blob)
                    res.append((op, len(blob), h))
                i = e + 2
        finally: mm.close()
    return res


def find_mp4_inside(path, out, stop=None):
    """開頭不是影片、但後面藏著一段完整的 MP4（救援時接錯資料）→ 從那裡切出來存成新檔，能播才留."""
    with open(lp(path), 'rb') as fh:
        try: mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        except (ValueError, OSError): return None
        try:
            i = 8
            while True:
                i = mm.find(b'ftyp', i)
                if i < 0: return None
                if stop is not None and stop(): raise InterruptedError
                sz = struct.unpack('>I', mm[i - 4:i])[0]
                if 12 <= sz <= 64 and mm[i + 4:i + 8].isalnum() and mm.find(b'moov', i, len(mm)) > 0:
                    os.makedirs(lp(os.path.dirname(out)), exist_ok=True)
                    with open(lp(out), 'wb') as o:
                        p = i - 4
                        while p < len(mm): o.write(mm[p:p + (16 << 20)]); p += 16 << 20
                    return out
                i += 4
        finally: mm.close()


def _copy_app1(src, fixed):
    """修好的照片補回原本的 EXIF（拍攝日期、相機）."""
    try:
        with open(lp(src), 'rb') as fh: head = fh.read(256 * 1024)
        segs = []; i = 2
        while i + 4 <= len(head) and head[i] == 0xFF and head[i + 1] not in (0xDA, 0xD9):
            ln = struct.unpack('>H', head[i + 2:i + 4])[0]
            if head[i + 1] == 0xE1 and head[i + 4:i + 10] == b'Exif\x00\x00': segs.append(head[i:i + 2 + ln])
            i += 2 + ln
        if not segs: return
        with open(lp(fixed), 'rb') as fh: d = fh.read()
        with open(lp(fixed), 'wb') as fh: fh.write(d[:2] + b''.join(segs) + d[2:])
    except Exception: pass


def img_dims(path):
    try:
        with open(lp(path), 'rb') as fh: head = fh.read(512 * 1024)
        M = jpeg_meta(head) if head[:2] == b'\xff\xd8' else png_meta(head)
        return int(M.get('w') or 0), int(M.get('h') or 0)
    except OSError: return 0, 0


def crop_green(ff, src, out):
    """部分損毀的照片：下面被填成綠色的那一段裁掉，存成新檔。回傳保留的比例（沒有綠色帶就回傳 None）."""
    if not ff: return None
    try:
        r = subprocess.run([ff, '-hide_banner', '-v', 'error', '-i', src, '-frames:v', '1', '-vf', 'scale=64:200:flags=area,format=rgb24', '-f', 'rawvideo', '-'],
                           capture_output=True, timeout=90, creationflags=NO_WINDOW | (0x00004000 if os.name == 'nt' else 0), stdin=subprocess.DEVNULL)
    except Exception: return None
    px = r.stdout; W, H = 64, 200
    if len(px) < W * H * 3: return None
    G = [pixel_stats(px[y * W * 3:(y + 1) * W * 3])[0] for y in range(H)]
    k = H
    while k > 0 and G[k - 1] >= 0.6: k -= 1
    if (H - k) / H < 0.03 or k < H * 0.05: return None
    keep = k / H
    run([ff, '-hide_banner', '-v', 'error', '-y', '-i', src, '-frames:v', '1', '-vf', f'crop=iw:trunc(ih*{keep:.4f}/2)*2:0:0', '-q:v', '2', out], 120)
    return keep if os.path.isfile(lp(out)) and os.path.getsize(lp(out)) > 1000 else None


def repair(path, size, kind, ff='', fp='', stop=None, known=None):
    """試著修復／救出。回傳 (結果清單 [{type, path, size, note}], 一句話說明)。
    type：fixed（修好的完整檔）、frame（影片擷取的畫面）、carved（從檔案裡挖出來的照片）、found（從裡面切出來的影片）。
    known(size, sha1)：如果這個內容在你的硬碟上已經有了，回傳那個路徑（就不另外存）."""
    od = repair_dir(path); stem = os.path.splitext(os.path.basename(path))[0]; ext = os.path.splitext(path)[1].lower(); outs = []; dup = 0; notes = []
    try:
        with open(lp(path), 'rb') as fh: head = fh.read(16)
    except OSError as ex: return [], f'讀不到：{ex.strerror or ex}'
    if size == 0: return [], '0 位元組：裡面什麼都沒有，救不回來'
    jpeg0, mp40 = head[:2] == b'\xff\xd8', head[4:8] == b'ftyp'
    if kind == 'photo':
        if ff and (jpeg0 or ext == '.png'):
            out = os.path.join(od, f'{stem}_修復.jpg'); os.makedirs(lp(od), exist_ok=True)
            rc, _o, _e = run([ff, '-hide_banner', '-v', 'error', '-y', '-i', path, '-frames:v', '1', '-q:v', '2', out], 120)
            if os.path.isfile(lp(out)) and os.path.getsize(lp(out)) > 1000:
                _copy_app1(path, out); w, h = img_dims(out)
                cr = os.path.join(od, f'{stem}_修復_裁掉綠色.jpg'); keep = crop_green(ff, path, cr)
                if keep:
                    _copy_app1(path, cr); cw, ch = img_dims(cr)
                    outs.append({'type': 'fixed', 'path': cr, 'size': os.path.getsize(lp(cr)), 'note': f'✂ 裁掉下面綠色的部分（{cw}×{ch}，保留上面 {int(keep * 100)}%）：最好用的版本'})
                outs.append({'type': 'fixed', 'path': out, 'size': os.path.getsize(lp(out)), 'note': f'修好的完整照片（{w}×{h}；缺的部分是綠色，但所有看圖軟體都打得開）'})
        mins = 3000
    else:
        if ff and fp and mp40:
            out = os.path.join(od, f'{stem}_修復.mp4'); os.makedirs(lp(od), exist_ok=True)
            run([ff, '-hide_banner', '-v', 'error', '-y', '-err_detect', 'ignore_err', '-fflags', '+genpts+discardcorrupt', '-i', path, '-map', '0:v?', '-map', '0:a?',
                 '-c', 'copy', '-movflags', '+faststart', out], 1800)
            _rc, dur, _E = probe_dur(fp, out) if os.path.isfile(lp(out)) else (1, 0, [])
            if dur > 0: outs.append({'type': 'fixed', 'path': out, 'size': os.path.getsize(lp(out)), 'note': f'重新包裝成能播放的影片（{int(dur // 60)}:{int(dur % 60):02d}，壞掉的片段會跳過）'})
            else:
                try: os.remove(lp(out))
                except OSError: pass
            _rc, dur0, _E = probe_dur(fp, path)
            if dur0 > 0:
                fd = os.path.join(od, f'{stem}_畫面'); os.makedirs(lp(fd), exist_ok=True); step = max(1.0, dur0 / 24)
                run([ff, '-hide_banner', '-v', 'error', '-y', '-err_detect', 'ignore_err', '-i', path, '-vf', f"fps=1/{step:.2f},scale='min(1920,iw)':-2", '-q:v', '2', os.path.join(fd, '%03d.jpg')], 1800)
                for f in sorted(os.listdir(lp(fd))):
                    q = os.path.join(fd, f); outs.append({'type': 'frame', 'path': q, 'size': os.path.getsize(lp(q)), 'note': '影片擷取的畫面'})
                if not os.listdir(lp(fd)): os.rmdir(lp(fd))
            elif not dur > 0: notes.append('影片索引（moov）不見了：要用 untrunc 配同一支手機拍的正常影片才有機會修')
        if not mp40:
            got = find_mp4_inside(path, os.path.join(od, f'{stem}_找到的影片.mp4'), stop)
            if got:
                _rc, dur, _E = probe_dur(fp, got) if fp else (1, 0, [])
                if dur > 0: outs.append({'type': 'found', 'path': got, 'size': os.path.getsize(lp(got)), 'note': f'檔案後面藏著一段完整的影片（{int(dur // 60)}:{int(dur % 60):02d}）'})
                else:
                    try: os.remove(lp(got))
                    except OSError: pass
        mins = 30000
    cd = os.path.join(od, f'{stem}_挖出的照片')
    for op, sz, h in carve_jpegs(path, cd, mins, 800, stop, skip0=(kind == 'photo' and jpeg0)):
        same = known(sz, h) if known else None
        if same: dup += 1; os.remove(lp(op)); continue
        st, msg = check_photo(op, sz, ff, True) if ff else _jpeg_check(open(lp(op), 'rb').read())
        if st == 'broken': os.remove(lp(op)); continue
        w, h = img_dims(op); small = w * h < 400 * 300 if w else sz < 60000
        note = (f'內嵌小縮圖（{w}×{h}，很小：相機順便存的縮小版，主圖壞得很嚴重時才用得到）' if kind == 'photo' and small else f'挖出來的照片（{w}×{h}）') + ('（部分損毀）' if st == 'partial' else '')
        outs.append({'type': 'carved', 'path': op, 'size': sz, 'note': note})
    for d in (cd, od):
        try:
            if os.path.isdir(lp(d)) and not os.listdir(lp(d)): os.rmdir(lp(d))
        except OSError: pass
    if not outs: rmdirs_up(od, os.path.splitdrive(unlp(od))[0] + '\\')                # 什麼都沒救出：連空的上層資料夾也收掉
    n = {k: sum(1 for o in outs if o['type'] == k) for k in ('fixed', 'frame', 'carved', 'found')}
    parts = [f'修好 {n["fixed"]} 個' if n['fixed'] else '', f'擷取 {n["frame"]} 張畫面' if n['frame'] else '', f'挖出 {n["carved"]} 張照片' if n['carved'] else '',
             f'找到 {n["found"]} 段影片' if n['found'] else '', f'另外 {dup} 張你硬碟上已經有了（沒另存）' if dup else '']
    msg = '、'.join(p for p in parts if p) or '沒救出東西'
    return outs, msg + ('；' + '；'.join(notes) if notes else '')


# ---------------------------------------------------------------- 縮圖（照片、影片都用 FFmpeg：壞掉的照片也能看到還剩多少）
def make_thumb(ff, src, dst, w=320, kind='photo', t=0.0):
    if not ff: return False
    Path(dst).parent.mkdir(parents=True, exist_ok=True); tmp = str(dst) + '.tmp.jpg'
    vf = f"scale='min({int(w)},iw)':-2"
    pre = ['-ss', f'{max(0.0, t):.2f}'] if kind == 'video' and t > 0 else []
    rc, _o, _e = run([ff, '-hide_banner', '-v', 'error', '-y'] + pre + ['-i', src, '-frames:v', '1', '-vf', vf, '-q:v', '4', tmp], 60)
    if (rc != 0 or not os.path.isfile(tmp)) and pre:
        rc, _o, _e = run([ff, '-hide_banner', '-v', 'error', '-y', '-i', src, '-frames:v', '1', '-vf', vf, '-q:v', '4', tmp], 60)
    if os.path.isfile(tmp) and os.path.getsize(tmp) > 0: os.replace(tmp, str(dst)); return True
    try: os.remove(tmp)
    except OSError: pass
    return False


# ---------------------------------------------------------------- 隔離（搬到同一顆硬碟的 _FileCompare_待確認）
def quar_root(path, name=None):
    drv = os.path.splitdrive(unlp(path))[0] or os.path.splitdrive(os.path.abspath(unlp(path)))[0]
    return drv + '\\' + (name or QUAR_NAME)


def quar_dst(path, reason, name=None):
    p = unlp(path); drv, rest = os.path.splitdrive(p)
    if name: return os.path.join(quar_root(p, name), rest.lstrip('\\/'))          # 轉檔後隔離區：直接照原本的資料夾結構放
    return os.path.join(quar_root(p), re.sub(r'[\\/:*?"<>|]', '_', reason or '其他'), rest.lstrip('\\/'))


def free_name(dst):
    if not os.path.exists(lp(dst)): return dst
    b, e = os.path.splitext(dst)
    for i in range(1, 10000):
        c = f'{b}_{i}{e}'
        if not os.path.exists(lp(c)): return c
    raise RuntimeError('同名的檔案太多')


MOVED = {'fn': None}                                                         # SortCut 設的：搬了之後通知它


def move(src, dst, rename=True):
    """同一顆硬碟內搬檔（瞬間完成、不佔空間）。dst 有同名的：rename=True 就加 _1、_2…；False 就失敗。回傳真正的 dst."""
    if not os.path.exists(lp(src)): raise FileNotFoundError(f'找不到 {src}')
    if os.path.exists(lp(dst)):
        if not rename: raise FileExistsError(f'已經有同名的檔案：{dst}')
        dst = free_name(dst)
    os.makedirs(lp(os.path.dirname(dst)), exist_ok=True)
    os.replace(lp(src), lp(dst))
    f_ = MOVED.get('fn')                                                       # 嵌在 SortCut 裡：VS 的紀錄跟著搬
    if f_ is not None:
        try: f_(str(src), str(dst))
        except Exception: pass
    return dst


def rmdirs_up(d, stop):
    """搬走之後：往上把變空的資料夾拿掉（到 stop 為止，不含 stop）."""
    d = os.path.normpath(d); stop = os.path.normpath(stop)
    while len(d) > len(stop) and d.lower().startswith(stop.lower()):
        try: os.rmdir(lp(d))
        except OSError: return
        d = os.path.dirname(d)


def like_esc(s):
    """資料庫 LIKE 用：_ 和 % 本來是萬用字元（資料夾名常有 _，例如 VID_2020、recup_dir.1），要跳脫，配合 ESCAPE '^'（V0.2.41）."""
    return str(s).replace('^', '^^').replace('%', '^%').replace('_', '^_')


def under(path, folder):
    a = os.path.normcase(os.path.normpath(path)); b = os.path.normcase(os.path.normpath(folder)).rstrip('\\/')
    return a == b or a.startswith(b + os.sep)

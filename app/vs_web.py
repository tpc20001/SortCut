"""SortCut 手機網頁（V0.1.49）：用手機透過 Tailscale 遙控電腦上的 SortCut。

和你其他程式錯開（不會互相蓋掉）：
  - 本機只聽 127.0.0.1:<埠>（預設 8461），Tailscale 用「自己的」HTTPS 埠＝本機埠 + 1000（預設 9461）：
        tailscale serve --bg --https=9461 http://127.0.0.1:8461
  - 只設定／關掉自己這個埠，從來不碰 443 根目錄（TikLive 在用）、也不跑 serve reset（不會清掉 FusionStitch 等其他程式的設定）。

伺服器是自己寫的小型 HTTP（只用 socket／threading，啟動器 EXE 裡一定有），每個連線一條背景執行緒，不會卡住電腦的畫面。
碰到畫面的動作（清單更新、切到封面、熱更新）一律交給畫面執行緒（ui）。
"""
import os, sys, re, json, time, socket, threading, hashlib, base64, struct, zlib, subprocess, shutil, traceback, urllib.parse
from pathlib import Path

WEB_VERSION = 1
MAX_BODY = 64 * 1024 * 1024
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
GRADES = ('S', 'A', 'E', 'F', '')
CT = {'.mp4': 'video/mp4', '.m4v': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm', '.mkv': 'video/x-matroska', '.avi': 'video/x-msvideo',
      '.ts': 'video/mp2t', '.flv': 'video/x-flv', '.wmv': 'video/x-ms-wmv', '.mpg': 'video/mpeg', '.mpeg': 'video/mpeg', '.3gp': 'video/3gpp', '.jpg': 'image/jpeg', '.png': 'image/png'}
LAB_TOGGLES = None                                                              # 由 app 給（LAB_LIST）


def https_port(local_port):
    """規則：Tailscale HTTPS 埠＝本機埠 + 1000（TikLive 用 443、FusionStitch 9361、SortCut 9461）."""
    return int(local_port) + 1000


def pin_hash(pin, salt):
    return hashlib.sha256((salt + '|' + str(pin)).encode('utf-8')).hexdigest()


def pin_ok_format(pin):
    return bool(re.fullmatch(r'[^\s]{4,20}', str(pin or '')))


def rand_hex(n=16):
    return os.urandom(n).hex()


def same(a, b):
    a = str(a).encode(); b = str(b).encode()
    if len(a) != len(b): return False
    r = 0
    for x, y in zip(a, b): r |= x ^ y
    return r == 0


# ------------------------------------------------------------------ PNG 圖示（不用 PIL：自己畫）
def make_icon_png(size):
    """深藍漸層圓角方塊＋青色底片框＋白色播放三角形。Android 安裝 App 需要 PNG（192／512）."""
    S = size; rad = S * 0.22; rows = []
    tri = [(S * 0.40, S * 0.32), (S * 0.40, S * 0.68), (S * 0.70, S * 0.50)]
    def in_tri(x, y):
        (x1, y1), (x2, y2), (x3, y3) = tri
        d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        a = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / d; b = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / d
        return a >= 0 and b >= 0 and a + b <= 1
    for y in range(S):
        row = bytearray(b'\x00')
        for x in range(S):
            dx = max(rad - x, 0, x - (S - 1 - rad)); dy = max(rad - y, 0, y - (S - 1 - rad))
            if dx * dx + dy * dy > rad * rad: row += b'\x0b\x0f\x14\xff'; continue      # 角落：maskable 也好看（背景色）
            t = (x + y) / (2 * S); r = int(16 + 20 * t); g = int(40 + 50 * t); b = int(70 + 80 * t)
            cx, cy = x - S / 2, y - S / 2; ring = (S * 0.30) ** 2 <= cx * cx + cy * cy <= (S * 0.34) ** 2
            if in_tri(x, y): r, g, b = 245, 250, 255
            elif ring: r, g, b = 77, 201, 255
            row += bytes((r, g, b, 255))
        rows.append(bytes(row))
    raw = zlib.compress(b''.join(rows), 9)
    def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', S, S, 8, 6, 0, 0, 0)) + chunk(b'IDAT', raw) + chunk(b'IEND', b'')


# ------------------------------------------------------------------ Tailscale
def tailscale_exe():
    exe = shutil.which('tailscale') or ''
    for c in (os.path.expandvars(r'%ProgramFiles%\Tailscale\tailscale.exe'), r'C:\Program Files\Tailscale\tailscale.exe', r'C:\Program Files (x86)\Tailscale\tailscale.exe'):
        if not exe and c and os.path.isfile(c): exe = c
    return exe


def tailscale_run(args, timeout=10):
    exe = tailscale_exe()
    if not exe: return -1, '找不到 tailscale（這台電腦還沒裝 Tailscale？）'
    try:
        p = subprocess.run([exe] + list(args), capture_output=True, timeout=timeout, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
        return p.returncode, (p.stdout + p.stderr).decode('utf-8', 'replace')
    except subprocess.TimeoutExpired: return -9, '逾時（Tailscale 沒回應；如果要登入，請看電腦右下角的 Tailscale）'
    except Exception as ex: return -1, f'{type(ex).__name__}: {ex}'


def tailscale_info(local_port):
    """{'installed', 'dns'（電腦名稱.xxx.ts.net）, 'ip', 'serving'（自己的 HTTPS 埠有沒有設好）, 'url'}."""
    out = {'installed': bool(tailscale_exe()), 'dns': '', 'ip': '', 'serving': False, 'url': '', 'others': []}
    if not out['installed']: return out
    rc, s = tailscale_run(['status', '--json'], 6)
    if rc == 0:
        try:
            j = json.loads(s[s.index('{'):]); me = j.get('Self') or {}
            out['dns'] = str(me.get('DNSName') or '').rstrip('.'); ips = me.get('TailscaleIPs') or []; out['ip'] = next((i for i in ips if '.' in i), ips[0] if ips else '')
        except Exception: pass
    hp = https_port(local_port)
    rc, s = tailscale_run(['serve', 'status', '--json'], 6)
    if rc == 0 and '{' in s:
        try:
            j = json.loads(s[s.index('{'):]); tcp = j.get('TCP') or {}
            out['serving'] = str(hp) in {str(k) for k in tcp.keys()}
            out['others'] = sorted(str(k) for k in tcp.keys() if str(k) != str(hp))          # 其他程式用的埠（只是顯示，不動它們）
        except Exception: pass
    if out['dns']: out['url'] = f'https://{out["dns"]}:{hp}/'
    return out


def tailscale_serve_on(local_port):
    hp = https_port(local_port)
    return tailscale_run(['serve', '--bg', f'--https={hp}', f'http://127.0.0.1:{int(local_port)}'], 40)


def tailscale_serve_off(local_port):
    return tailscale_run(['serve', f'--https={https_port(local_port)}', 'off'], 20)


# ------------------------------------------------------------------ 伺服器

VS_FC_HINTS = {12: '🎞 每部影片 16 格一次看完、按數字分到資料夾；SortCut 已經做好預覽圖的直接拿來用，不會再讀一次影片。要剪片段 → ②「檔案總管＋初剪」。',
               19: '🗜 影片瘦身＝從整理掃到的影片挑大的瘦身；要整批轉 H.265 用 ③「🔁 轉檔」。兩邊都是 SSIM 畫質目標，同一部不會兩邊都轉；SortCut 轉檔中時這裡會先等（不搶顯示卡）。',
               2: '🔁 這裡用指紋比對，有「最佳解」、搬到隔離區可以復原 → 建議以這裡為主；HotZone 的「👯 重複檔」是另一套，不用兩邊都跑。',
               4: '🧺 整理搬走的、修不好的都在這裡（可以復原）；HotZone 刪掉的在 ④「🛟 HotZone 保管區」。',
               3: '🩺 損毀檢查會把影片整部解碼一次（很花硬碟時間）；SortCut 在用同一顆硬碟時它會自動讓路。',
               1: '⚙ 這裡是整理（FileCompare）自己的背景工作；SortCut 的在「🖥 後台狀態」（那頁最上面也有一行整理的摘要）。「全部暫停／全部繼續」兩邊一起；SortCut 在用同一顆硬碟時，這裡的項目會寫「🤝 讓 SortCut 先用」。',
               6: '📜 這是整理（FileCompare）的 LOG；SortCut 的在「設定與說明 → LOG」。SortCut LOG 頁按「📤 匯出最近 7 天」會兩邊一起打包。',
               22: '🧾 這裡是整理（FileCompare）搬過的檔（分類、隔離、依日期整理…），可以搬回；SortCut 自己的待刪、歸檔、轉檔記在 ②「📒 操作紀錄」。',
               14: '🖼 相似／連拍是「長得像」的照片一組一組挑。要找「聖誕節」這種內容：現在可以用 ⑥「📅 依日期整理」「🗓 時間軸」（例如 12 月下旬），或 HotZone 的「🎨 圖片分類」；AI 看懂照片內容的搜尋之後會加（放 🧪 實驗功能）。'}   # V0.5.18 電腦版、手機共用


def yield_api(S, req):
    """V0.5.71 🤝 讓路等級（SortCut／整理兩邊網頁共用）."""
    import vs_yield as Y_
    if req.method != 'GET':
        if S.is_ro(req): return {'ok': False, 'message': '👀 這支手機是唯讀登入：只能看，不能改'}
        d = req.json() or {}; E = S.E()
        if 'on' in d: E.cfg.set('yield_on', bool(d['on']))
        if 'tk' in d: E.cfg.set('yield_tk', bool(d['tk']))                         # V0.6.07 這台要不要讓路給 TikLive
        if 'max' in d: E.cfg.set('yield_max', max(1, min(10, int(d['max']))))
        if 'nv' in d: E.cfg.set('nvenc_limit', max(2, min(16, int(d['nv']))))
        if 'th_on' in d: E.cfg.set('thermal_on', bool(d['th_on']))                 # V0.5.79 🌡 控溫
        if 'th_cpu' in d: E.cfg.set('thermal_cpu', max(15, min(95, int(d['th_cpu']))))
        if 'th_vs' in d: E.cfg.set('thermal_vs_max', max(2, min(60, int(d['th_vs']))))
        if 'th_gpu' in d: E.cfg.set('thermal_gpu', max(50, min(95, int(d['th_gpu']))))
        if 'hs_on' in d: E.cfg.set('hs_on', bool(d['hs_on']))                     # V0.6.10 🤝 跟別的程式握手（FusionStitch）
        if 'hs_prio' in d: E.cfg.set('hs_prio', max(0, min(10, int(d['hs_prio']))))
        if 'hs_comfy' in d: E.cfg.set('hs_comfy', bool(d['hs_comfy']))             # V0.6.25 🎨 自動看 ComfyUI
        try:                                                                    # V0.6.17 握手共用設定（policy3.json，三個程式一起變）
            import vs_yield as VY_; mem = {}
            if isinstance(d.get('hs_members'), dict): mem.update({str(k): bool(v) for k, v in d['hs_members'].items()})
            for k_, v_ in d.items():
                if str(k_).startswith('hs_m_'): mem[str(k_)[5:]] = bool(v_)
            if 'tk' in d: mem['TikLive'] = bool(d['tk'])
            pk = VY_.hs_set_pol(members=mem or None, reserve3=d.get('hs_reserve'), first_cap=d.get('hs_first_cap'), yield_cap=d.get('hs_yield_cap'), share_sc=d.get('hs_share_sc'))
            if pk: E.log.w(f'🤝 握手共用設定：{pk}')
        except Exception as ex: E.log.w(f'🤝 握手共用設定沒存到：{ex}')
        if 'hs_boost' in d: E.cfg.set('hs_boost_until', (time.time() + max(0, min(480, int(d['hs_boost']))) * 60) if int(d['hs_boost']) > 0 else 0)
        try: E.log.w(f'🤝 手機改讓路設定：{d}')
        except Exception: pass
    v = Y_.view(); v['ok'] = True; return v

class Req:
    def __init__(self, method, path, query, headers, body, peer):
        self.method = method; self.path = path; self.query = query; self.headers = headers; self.body = body; self.peer = peer

    def q(self, k, d=''):
        v = self.query.get(k)
        return v[0] if v else d

    def json(self):
        try: return json.loads(self.body.decode('utf-8') or '{}')
        except Exception: return {}

    def cookie(self, k):
        for part in (self.headers.get('cookie') or '').split(';'):
            a, _, b = part.strip().partition('=')
            if a == k: return urllib.parse.unquote(b)
        return ''

    def client(self):
        if self.peer in ('127.0.0.1', '::1'):                                    # 只有本機的代理（Tailscale serve）帶的 X-Forwarded-For 才相信（區網的人可以亂填來躲過錯太多次的限制）
            return (self.headers.get('x-forwarded-for') or self.peer or '').split(',')[0].strip()
        return self.peer or ''


class Resp:
    def __init__(self, code=200, body=b'', ctype='application/json; charset=utf-8', headers=None, file=None, rng=None):
        self.code = code; self.body = body; self.ctype = ctype; self.headers = headers or {}; self.file = file; self.rng = rng


def jresp(obj, code=200, headers=None):
    return Resp(code, json.dumps(obj, ensure_ascii=False, default=str).encode('utf-8'), headers=headers)


REASON = {200: 'OK', 302: 'Found', 204: 'No Content', 206: 'Partial Content', 304: 'Not Modified', 400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found',
          413: 'Payload Too Large', 416: 'Range Not Satisfiable', 429: 'Too Many Requests', 500: 'Internal Server Error'}


class WebServer:
    """get_eng()／get_win()：目前的引擎和主視窗（熱更新後自動是新的）；ui(fn)：交給畫面執行緒；app_mod()：目前的 app 模組（熱更新用）."""

    def __init__(self, get_eng, get_win, ui, app_mod, version, lab_list=()):
        self.E = get_eng; self.W = get_win; self.ui = ui; self.app_mod = app_mod; self.version = version; self.lab_list = list(lab_list)
        self.sock = None; self.th = None; self.stop = False; self.port = 0; self.bind = ''; self.err = ''; self.fails = {}; self.n_conn = 0; self.lock = threading.Lock()
        self.jobs = {}; self._icons = {}; self.started_t = 0; self.reqs = 0

    # ---- 開關
    def start(self, port, lan=False):
        self.close()
        self.port = int(port); self.bind = '0.0.0.0' if lan else '127.0.0.1'; self.err = ''
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if os.name == 'nt' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'): s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)     # Windows：不要跟別的程式共用同一個埠
            else: s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.bind, self.port)); s.listen(32); s.settimeout(1.0)
        except OSError as ex:
            self.err = f'埠 {self.port} 不能用（{ex.strerror or ex}）：可能被你別的程式佔用了，請在設定換一個（例如 {self.port + 10}）'
            self._log('⚠ 手機網頁開不起來：' + self.err); return False
        self.sock = s; self.stop = False; self.started_t = time.time()
        self.th = threading.Thread(target=self._loop, name='VsWeb', daemon=True); self.th.start()
        self._log(f'手機網頁開了：{self.bind}:{self.port}（Tailscale HTTPS 用 {https_port(self.port)}）'); return True

    def close(self):
        self.stop = True; s = self.sock; self.sock = None
        if s is not None:
            try: s.close()
            except Exception: pass
            self._log(f'手機網頁關了（埠 {self.port}）')
        if self.th is not None and self.th is not threading.current_thread():
            try: self.th.join(2.5)
            except Exception: pass
        self.th = None

    @property
    def running(self): return self.sock is not None and not self.stop

    def _log(self, m):
        try: self.E().log.w(m)
        except Exception: pass

    def _loop(self):
        s = self.sock
        while not self.stop and s is not None:
            try: c, addr = s.accept()
            except socket.timeout: continue
            except OSError: break
            if self.n_conn > 48: c.close(); continue
            threading.Thread(target=self._conn, args=(c, addr), name='VsWebConn', daemon=True).start()

    # ---- 一個連線（一個請求，回完就關）
    def _conn(self, c, addr):
        with self.lock: self.n_conn += 1
        try:
            c.settimeout(30); f = c.makefile('rb')
            line = f.readline(65536).decode('latin-1').strip()
            if not line: return
            parts = line.split(' ')
            if len(parts) < 2: return
            method, target = parts[0].upper(), parts[1]; H = {}; t_dead = time.time() + 20; nh = 0
            while True:
                h = f.readline(65536); nh += 1
                if nh > 100 or time.time() > t_dead: return                     # 標頭太多、慢慢滴（佔著連線不放）：直接斷
                if not h or h in (b'\r\n', b'\n'): break
                k, _, v = h.decode('latin-1').partition(':'); H[k.strip().lower()] = v.strip()
            try: n = int(H.get('content-length') or 0)
            except ValueError: n = -1
            if n < 0: self._send(c, Resp(400, b'bad length', 'text/plain')); return
            if n > MAX_BODY: self._send(c, Resp(413, b'too big', 'text/plain')); return
            if n > (1 << 20):                                                   # 還沒登入的不收大的內容（免得被灌爆記憶體）
                ck = ''
                for part in (H.get('cookie') or '').split(';'):
                    a_, _, b_ = part.strip().partition('=')
                    if a_ == 'vs_t': ck = urllib.parse.unquote(b_)
                tk = H.get('x-vs-token') or ck
                if not (tk and any(same(tk, x) for x in (self.E().cfg.get('web_tokens') or []))): self._send(c, Resp(413, b'too big', 'text/plain')); return
            body = f.read(n) if n else b''
            u = urllib.parse.urlsplit(target); path = urllib.parse.unquote(u.path)
            req = Req(method, path, urllib.parse.parse_qs(u.query), H, body, addr[0] if addr else '')
            self.reqs += 1
            try: import vs_mainfirst as MF_; mk_ = MF_.web_begin(path)                  # V0.6.08 🛟 手機的請求卡太久 → 背景先退
            except Exception: MF_ = None
            try: r = self.route(req)
            except Exception as ex:
                self._log(f'手機網頁錯誤：{method} {path}\n{traceback.format_exc()}'); r = jresp({'ok': False, 'message': f'{type(ex).__name__}: {ex}'}, 500)
            finally:
                if MF_ is not None:
                    try: MF_.web_end(mk_)
                    except Exception: pass
            try:                                                                    # V0.6.40 大的回應壓縮再送（手機頁 380 KB → 120 KB、清單 JSON 小 5～10 倍；同一份只壓一次）
                if not getattr(r, 'file', None) and len(r.body) > 16384 and 'gzip' in (H.get('accept-encoding') or '') and 'Content-Encoding' not in (r.headers or {}) \
                        and any(x in (r.ctype or '') for x in ('json', 'html', 'javascript', 'text/', 'css', 'svg')):
                    import zlib
                    k_ = (len(r.body), zlib.crc32(r.body)); GZ = self.__dict__.setdefault('_gz', {})
                    z_ = GZ.get(k_)
                    if z_ is None:
                        zo = zlib.compressobj(1 if len(r.body) > 1000000 else 6, zlib.DEFLATED, 31); z_ = zo.compress(r.body) + zo.flush()
                        if len(r.body) > 100000 and 'html' in (r.ctype or ''):
                            if len(GZ) > 8: GZ.clear()
                            GZ[k_] = z_
                    r.body = z_; r.headers = dict(r.headers or {}); r.headers['Content-Encoding'] = 'gzip'; r.headers['Vary'] = 'Accept-Encoding'
            except Exception: pass
            self._send(c, r, method == 'HEAD')
        except Exception: pass
        finally:
            try: c.close()
            except Exception: pass
            with self.lock: self.n_conn -= 1

    def _send(self, c, r, head=False):
        H = {'Content-Type': r.ctype, 'Connection': 'close', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer'}
        H.setdefault('Cache-Control', 'no-store')
        H.update(r.headers)
        if r.file is not None:
            p, a, b, total = r.file
            H['Content-Length'] = str(b - a + 1); H['Accept-Ranges'] = 'bytes'
            if r.code == 206: H['Content-Range'] = f'bytes {a}-{b}/{total}'
        else: H['Content-Length'] = str(len(r.body))
        head_b = f'HTTP/1.1 {r.code} {REASON.get(r.code, "OK")}\r\n' + ''.join(f'{k}: {v}\r\n' for k, v in H.items()) + '\r\n'
        c.sendall(head_b.encode('latin-1', 'replace'))
        if head: return
        if r.file is None: c.sendall(r.body); return
        p, a, b, total = r.file; left = b - a + 1
        with open(p, 'rb') as fh:
            fh.seek(a)
            while left > 0 and not self.stop:
                chunk = fh.read(min(256 * 1024, left))
                if not chunk: break
                c.sendall(chunk); left -= len(chunk)

    # ---- 登入
    def authed(self, req):
        toks = (self.E().cfg.get('web_tokens') or []) + (self.E().cfg.get('web_tokens_ro') or [])
        t = req.headers.get('x-vs-token') or req.cookie('vs_t') or req.q('t')
        return bool(t) and any(same(t, x) for x in toks)

    def _tok_meta(self, tok, req, ro):
        """V0.4.31 📱 記住每支手機什麼時候、從哪裡、用什麼瀏覽器登入（只存 token 前 8 碼）."""
        try:
            M = dict(self.E().cfg.get('web_tok_meta') or {}); ua = req.headers.get('user-agent', '')
            dev = 'iPhone' if 'iPhone' in ua else 'iPad' if 'iPad' in ua else 'Android' if 'Android' in ua else 'Windows' if 'Windows' in ua else 'Mac' if 'Mac OS' in ua else '其他'
            M[tok[:8]] = {'t': time.time(), 'last': time.time(), 'ip': req.client(), 'dev': dev, 'ua': ua[:120], 'ro': bool(ro)}
            self.E()._new_login = (time.time(), dev, req.client(), bool(ro))   # V0.4.32 電腦跳提醒
            live = {x[:8] for x in (self.E().cfg.get('web_tokens') or []) + (self.E().cfg.get('web_tokens_ro') or [])} | {tok[:8]}
            self.E().cfg.set('web_tok_meta', {k: v for k, v in M.items() if k in live})
        except Exception: pass

    def tok_seen(self, req):
        """每支手機最後一次用的時間（10 分鐘寫一次就好）."""
        try:
            t = req.headers.get('x-vs-token') or req.cookie('vs_t') or req.q('t')
            if not t: return
            M = self.E().cfg.get('web_tok_meta') or {}; m = M.get(t[:8])
            if m and time.time() - float(m.get('last') or 0) > 600: M = dict(M); M[t[:8]] = dict(m, last=time.time(), ip=req.client()); self.E().cfg.set('web_tok_meta', M)
        except Exception: pass

    def tok_list(self):
        M = self.E().cfg.get('web_tok_meta') or {}; out = []
        for ro, L in ((False, self.E().cfg.get('web_tokens') or []), (True, self.E().cfg.get('web_tokens_ro') or [])):
            for t in L: m = M.get(t[:8]) or {}; out.append({'k': t[:8], 'ro': ro, 'dev': m.get('dev', '（舊的，沒記錄）'), 'ip': m.get('ip', ''), 't': m.get('t', 0), 'last': m.get('last', 0)})
        return sorted(out, key=lambda x: -float(x['last'] or 0))

    def tok_revoke(self, k):
        E = self.E(); n = 0
        for key in ('web_tokens', 'web_tokens_ro'):
            L = list(E.cfg.get(key) or []); L2 = [t for t in L if t[:8] != k]; n += len(L) - len(L2); E.cfg.set(key, L2)
        if n: self._log(f'手機網頁：登出一支手機（{k}…）')
        return n

    def fc_route(self, req):
        """🗂 整理（FileCompare）手機版：頁面放在 /fc/，API 走 /fc/api/…，用 SortCut 的登入（不用另外的 PIN、不用另外的埠）."""
        p = req.path
        if p in ('/fc', '/fc/index.html'): return Resp(302, b'', 'text/plain', {'Location': '/fc/'})
        try:
            import fc_app as F
            from PySide6.QtWidgets import QApplication
            ok_ = type(getattr(QApplication.instance(), '_fc_eng', None)).__name__ == 'Engine'
        except Exception as ex: F = None; ok_ = False; err_ = str(ex)
        if p == '/fc/':
            if not self.authed(req): return Resp(302, b'', 'text/plain', {'Location': '/'})
            if F is None or not ok_: return Resp(200, '<meta name="viewport" content="width=device-width"><meta http-equiv="refresh" content="3"><body style="background:#0e1116;color:#ccc;font-family:sans-serif;padding:20px">🗂 整理（FileCompare）還在準備（電腦開程式後約 5 秒，這頁 3 秒後自動重試）…<br><br><a style="color:#4dc9ff" href="/fc/">重新整理</a>　<a style="color:#4dc9ff" href="/">← 回 SortCut</a></body>'.encode('utf-8'), 'text/html; charset=utf-8')
            r = F.embed_web().page(); h = r.body.decode('utf-8')
            for q_ in ("'", '"', '`'): h = h.replace(q_ + '/api/', q_ + '/fc/api/')
            h = re.sub(r'<link rel="manifest"[^>]*>', '', h)
            # 嵌在 SortCut 裡：FileCompare 自己的「更新好了」、手機網頁／線上更新設定、登出卡片都跟著 SortCut，這裡不重複出現
            h = h.replace('setTimeout(whatsNew,1500)', '0')
            h = h.replace("['about','📱','手機網頁','版本、登出','phone'],", '')
            h = h.replace("\n  ['upd','🆕','線上更新','上傳更新包、退回前一版','pc'],", '\n  ')
            h = h.replace('<div class="tgh tgx">帳號</div>', '<div class="tgh tgx" hidden>帳號</div>').replace('<button class="wsCard" data-tl="logout"', '<button hidden class="wsCard" data-tl="logout"')
            h = h.replace("SCUR=LS.get('scat','look');", "SCUR=LS.get('scat','look');if(SCUR==='about'||SCUR==='upd')SCUR='look';")
            # V0.5.18 跟電腦版一樣：快速分類／影片瘦身／重複檔／隔離區／損毀檢查上面一行「跟 SortCut／HotZone 哪裡重疊、該用哪個」
            h = h.replace('<head>', '<head><script>try{const u_=JSON.parse(localStorage.getItem("vs_ui")||"{}");let m_=u_.mode||"dark";if(m_==="auto"){const h_=new Date().getHours();m_=(h_>=7&&h_<19)?"light":"dark"}'
                          'localStorage.setItem("app_mode",JSON.stringify(m_))}catch(e){}</script>', 1)                 # V0.5.30 深色／淺色跟著 SortCut
            h = re.sub(r'(<span class="mu" id="ver">)V[^<]*(</span>)', lambda m_: m_.group(1) + 'V' + str(self.version) + m_.group(2), h, count=1)   # V0.5.66 右上版本＝SortCut
            h = h.replace("'log','diag','upd']", "'log','diag']", 1); h = h.replace('const rest=TOOLS.flatMap(([,L])=>L).filter(x=>!used.has(x[0]));', "const rest=TOOLS.flatMap(([,L])=>L).filter(x=>!used.has(x[0])&&x[0]!=='upd');", 1)                       # V0.5.21 工具裡的「🆕 線上更新」也拿掉（更新跟著 SortCut）
            h = h.replace('function show(){clearInterval(TIMER);', 'function show(){clearInterval(TIMER);try{window.VSH&&VSH(CUR)}catch(e){};', 1)
            h = h.replace('<div id="v"></div></main>', '<div id="vshint" hidden style="display:flex;gap:8px;align-items:flex-start;margin:6px 10px 0;padding:8px 10px;border:1px solid #2f9bff55;'
                          'border-radius:10px;background:#2f9bff14;font-size:12.5px;line-height:1.45"><span id="vsht" style="flex:1"></span><button id="vshx" style="background:none;border:0;color:inherit;font-size:15px;cursor:pointer">✕</button></div><div id="v"></div></main>', 1)
            HJ = {'vc': VS_FC_HINTS[12], 'tool:slim': VS_FC_HINTS[19], 'tool:dup': VS_FC_HINTS[2], 'tool:q': VS_FC_HINTS[4], 'tool:hl': VS_FC_HINTS[3], 'tool:sim': VS_FC_HINTS[14], 'tool:bg': VS_FC_HINTS[1], 'tool:ops': VS_FC_HINTS[22], 'tool:log': VS_FC_HINTS[6]}
            try:                                                                  # V0.5.57 整理還沒設定任何資料夾：總覽上面提醒「舊資料要在電腦上匯入」
                if not list(F.ENG.cfg.get('roots') or []):                          # 沒有要整理的資料夾：分類畫面中間那句「全部分好了」換成「去哪裡加資料夾」
                    h = h.replace("這裡沒有影片${VC.f==='todo'&&VI.cats.length?'（全部分好了 🎉）':''}", '還沒有要整理的資料夾，所以這裡沒有影片<br><br>📁 在這裡直接加（例如 R:\\\\ 或 R:\\\\手機照片），加好會開始掃描，掃到的影片就出現在這裡：<div style="display:flex;gap:6px;justify-content:center;margin:10px auto;max-width:440px"><input id="vcnr" placeholder="R:\\\\" style="flex:1;min-width:0;padding:9px 11px;border-radius:10px"><button class="pill acc" onclick="VSADD()">＋ 加入並掃描</button></div><span style="font-size:12px">（也可以在「📊 總覽」最下面「① 要整理的資料夾」加；電腦上是 ①「整理總覽」）</span>', 1)
                if not list(F.ENG.cfg.get('roots') or []): HJ['vc'] = '📁 還沒有要整理的資料夾，所以這裡沒有影片：到「📊 總覽」拉到最下面「① 要整理的資料夾」，打路徑（例如 R:\\ 或 R:\\手機照片）按「＋ 加入」，再按「▶ 開始掃描」，掃到的影片就會出現在這裡。電腦上是 ①「整理總覽」。'
                if not list(F.ENG.cfg.get('roots') or []): HJ['home'] = '📥 舊電腦用過 FileCompare？把舊的 Data 資料夾複製到這台電腦，在電腦的 SortCut 按「📥 匯入舊 FileCompare 資料」，重開就接上（R 碟代號要一樣）。新開始的話按下面「去設定」加要整理的資料夾。'
            except Exception: pass
            hint_js = ('<script>(function(){const H=' + json.dumps(HJ, ensure_ascii=False) + ';let K="";const off=()=>{try{return JSON.parse(localStorage.getItem("vsHintOff")||"[]")}catch(e){return []}};'
                     'window.VSH=function(k){K=k;const b=document.getElementById("vshint");if(!b)return;const t=H[k];if(!t||off().includes(k)){b.hidden=true;b.style.display="none";return}'
                     'document.getElementById("vsht").textContent=t;b.hidden=false;b.style.display="flex"};'
                     'document.addEventListener("click",e=>{if(!e.target.closest("#vshx"))return;const L=off();L.push(K);try{localStorage.setItem("vsHintOff",JSON.stringify(L))}catch(x){}VSH(K)});'
                     'setTimeout(()=>{try{VSH(CUR)}catch(e){}},800);'
                     'const GB=b=>(b/1e9>=1000?(b/1e12).toFixed(2)+" TB":(b/1e9).toFixed(1)+" GB");'
                     'window.VSDEL=async function(){const j=await api("/fc/api/vs_delinfo");if(!j.ok)return;'
                     'if(j.st.run)return toast("🗑 刪除中 "+j.st.msg);if(!j.n)return toast("Delete 裡沒有已經搬好的檔"+(j.wait?"（還有 "+j.wait+" 部沒搬，先按 🚚 搬）":""));'
                     'const dv=Object.entries(j.drives).map(([d,b])=>d+" "+GB(b)).join("、");'
                     'if(!confirm("🗑 永久刪除「"+j.cats.join("／")+"」分類裡已經搬好的檔\\n\\n"+j.n.toLocaleString()+" 個，共 "+GB(j.bytes)+"（"+dv+"）\\n"+(j.wait?"還沒搬的 "+j.wait+" 部不會刪（要刪先按 🚚 搬）\\n":"")+"\\n不經過資源回收筒，刪了救不回來。確定？"))return;'
                     'if((prompt("最後確認：輸入「刪除」兩個字")||"").trim()!=="刪除")return toast("沒有刪");'
                     'const r=await api("/fc/api/vs_delpurge",{n:j.n});toast(r.message);if(!r.ok)return;'
                     'const t=setInterval(async()=>{const k=await api("/fc/api/vs_delinfo");VSDC(k);if(!k.st.run){clearInterval(t);toast("🗑 "+k.st.msg+"，空出 "+GB(k.st.b));try{show()}catch(e){}}},2000)};'
                     'window.VSDC=function(j){let c=document.getElementById("vsdel");const S=document.getElementById("sysFab")||document.querySelector("header .bar");if(!S)return;'
                     'if(!c){c=document.createElement("button");c.id="vsdel";c.type="button";c.style.cssText="border-color:#ff6b6b;color:#ffb3b3";c.onclick=()=>VSDEL();S.appendChild(c)}'
                     'const show_=j&&(j.n>0||(j.st&&j.st.run));c.style.display=show_?"":"none";if(show_)c.textContent=j.st&&j.st.run?"🗑 刪除中 "+j.st.msg:"🗑 Delete "+GB(j.bytes)};'
                     'const dl=async()=>{try{VSDC(await api("/fc/api/vs_delinfo"))}catch(e){}};setTimeout(dl,1200);setInterval(dl,60000);'
                     'window.VSADD=async function(){const e=document.getElementById("vcnr");const v=e?e.value.trim():"";if(!v)return toast("先輸入資料夾路徑（例如 R:\\\\）");'
                     'const r=await api("/fc/api/fc_run",{a:"add",which:"roots",p:v});toast(r.message||(r.ok?"加好了":"加不進去"));if(r.ok===false)return;await api("/fc/api/fc_run",{a:"scan"});toast("▶ 開始掃描 "+v+"（背景做，掃到的影片會出現在這裡）");setTimeout(()=>location.reload(),2500)};'
                     'const mv=()=>{const b=document.getElementById("vsback"),L=document.querySelector("header .bar .logo");if(b&&L&&!b.classList.contains("inh")){b.classList.add("inh");L.parentNode.insertBefore(b,L)}};setTimeout(mv,300);setTimeout(mv,1500)})();</script>')
            back = ''                                                             # V0.5.68 「← SortCut」換成左上角三段切換（下面）
            back += '<style>#sysbar button[data-t="up"],button[data-t="up"]{display:none!important}main{padding-bottom:64px}#vsback.inh{position:static!important;margin-right:8px;padding:4px 10px!important;font-size:12px!important;box-shadow:none!important;flex:0 0 auto}body.vcmode #vsback.inh .vbl{display:none}</style>'   # 更新在 SortCut 裡管
            back += hint_js
            import vs_dashui as DZ                                                # V0.5.68 🎛 三段切換＋📊 一頁總覽（跟 SortCut 網頁同一份）
            msw = ('<div class="msw" id="msw" data-m="fc" role="tablist" aria-label="切換"><i class="msw-k"></i>' + ''.join(
                f'<button type="button" role="tab" data-m="{k}" class="{"on" if k == "fc" else ""}" title="{n}：{t}"><b>{ic}</b><span>{n}</span></button>'
                for k, ic, n, t in (('vs', '🎬', 'VideoSift', '10 秒剪輯、分級'), ('fc', '🗂', 'FileCompare', '16 格分類整理'), ('h265', '🗜', 'H265', 'SSIM 轉檔瘦身'))) + '</div>')
            h = h.replace('<header><div class="bar"><div class="logo">', '<header><div class="bar">' + msw + '<div class="logo" style="margin-left:10px">', 1)
            back += ('<style>' + DZ.CSS + 'header .bar .msw{margin-right:4px}@media (max-width:620px){header .bar .logo{display:none}header .bar>.msw{width:100%!important}#sysFab .lvb{height:auto;padding:4px 9px;margin:0;color:var(--lc)!important;border-color:var(--lc)!important}#sysFab .lvb .lvbars{display:none}}</style><script>' + DZ.JS +
                     "(function(){try{const T=TABS.find(t=>t[0]==='home');if(T){const old=T[2];window.dzFull=()=>old(false);"
                     "T[2]=function(again){if(again)return;dzShow(document.getElementById('v'),'fc',u=>api(u))}}}catch(e){console.log(e)}})();</script>"
                     "<script>(function(){try{const ins=()=>{const ph=matchMedia('(max-width:620px)').matches,F_=document.getElementById('sysFab'),B=document.querySelector('header .bar'),M_=document.getElementById('msw');"   # V0.5.71 🤝 右上角 Lv（手機放在上面那排浮動按鈕裡）
                     "let el=document.getElementById('lvb');if(!el){if(!B||(ph&&!F_))return;const d=document.createElement('span');d.innerHTML=lvHTML();el=d.firstElementChild}"
                     "if(ph){if(F_&&el.parentNode!==F_)F_.appendChild(el)}else if(M_&&M_.parentNode===B){if(el.previousSibling!==M_)B.insertBefore(el,M_.nextSibling)}else if(B&&!el.parentNode)B.appendChild(el);if(LVV)lvSet(LVV)};"
                     "ins();[300,900,2000,4000].forEach(t=>setTimeout(ins,t));addEventListener('resize',ins);"
                     "lvStart(b=>api('/fc/api/vs_yield',b))}catch(e){console.log(e)}})();</script>")
            h = h.replace('</body>', back + '</body>', 1) if '</body>' in h else h + back
            return Resp(200, h.encode('utf-8'), 'text/html; charset=utf-8')
        if p.startswith('/fc/api/'):
            sub = p[3:]; name = sub[5:].split('/')[0]
            if not self.authed(req): return jresp({'ok': False, 'message': '要先輸入 PIN', 'login': True}, 401)
            if name == 'hello': return jresp({'ok': True, 'ver': str(self.version), 'name': '整理', 'authed': True, 'pin_set': True})
            if name in ('login', 'logout', 'update', 'update_up', 'update_dl', 'update_rollback', 'pin', 'web'): return jresp({'ok': False, 'message': '這個在 SortCut 裡面管（設定／版本與更新）'}, 403)
            if req.method != 'GET' and self.is_ro(req): return jresp({'ok': False, 'message': '👀 這支手機是唯讀登入：只能看，不能改'}, 403)
            if F is None or not ok_: return jresp({'ok': False, 'message': '🗂 整理（FileCompare）還在準備，等幾秒再試'}, 503)
            if name == 'vs_yield': return jresp(yield_api(self, req))            # V0.5.71 🤝 整理頁右上角也有 Lv
            if name == 'vs_fcpack':                                              # V0.5.69 💽 硬碟上的整理紀錄：找／接上
                import vs_fcpack as FP
                if req.method == 'GET': return jresp({'ok': True, 'packs': [{'X': x, **j} for x, j in FP.find(F.ENG)]})
                X_ = str((req.json() or {}).get('X') or '')[:1].upper()
                if not X_ or not any(x == X_ for x, _j in FP.find(F.ENG)): return jresp({'ok': False, 'message': '找不到那顆硬碟的整理紀錄'})
                import app as A_
                r_ = FP.use(X_, A_.fc_root()); r_['message'] += '（在電腦上重開 SortCut，或電腦版整理頁上面按「🔄 現在重開換上」）'; return jresp(r_)
            if name in ('vs_delinfo', 'vs_delpurge'):                              # V0.5.67 🗑 永久刪除 Delete 分類（已經搬好的）
                import vs_fcdel as FD
                if name == 'vs_delinfo': return jresp(FD.info(F.ENG))
                d_ = req.json() if hasattr(req, 'json') else {}
                inf = FD.info(F.ENG)
                if int((d_ or {}).get('n') or -1) != inf['n']: return jresp({'ok': False, 'message': f'數字對不上（現在是 {inf["n"]:,} 個），重新整理再按一次'})
                E_ = self.E()
                def gone_(p_):
                    try: E_.db.x('UPDATE files SET missing=1 WHERE path=?', (p_,))
                    except Exception: pass
                return jresp(FD.purge(F.ENG, lp=getattr(sys.modules.get('fc_fcore'), 'lp', None), on_gone=gone_, log=E_.log.w))
            S = F.embed_web(); fn = getattr(S, 'api_' + name.replace('-', '_'), None)
            if fn is None: return jresp({'ok': False, 'message': f'沒有這個功能：{name}'}, 404)
            import fc_web as FW
            r = fn(FW.Req(req.method, sub, req.query, req.headers, req.body, req.peer))
            if getattr(r, 'file', None):                                        # FileCompare 的大檔（影片、圖）→ SortCut 的分段傳送
                try: tot = os.path.getsize(r.file)
                except Exception: tot = 0
                return Resp(r.code, b'', r.ctype, dict(r.headers), file=(r.file, int(r.a), int(r.a) + int(r.n) - 1, tot))
            return Resp(r.code, r.body, r.ctype, dict(getattr(r, 'headers', None) or {}))
        return Resp(404, b'not found', 'text/plain')

    def is_ro(self, req):
        """V0.4.30 👀 用唯讀 PIN 登入的手機：只能看，不能改."""
        t = req.headers.get('x-vs-token') or req.cookie('vs_t') or req.q('t')
        return bool(t) and any(same(t, x) for x in (self.E().cfg.get('web_tokens_ro') or []))

    def login(self, req):
        E = self.E(); d = req.json(); cl = req.client(); n, t0 = self.fails.get(cl, (0, 0))
        if n >= 5 and time.time() - t0 < 300: return jresp({'ok': False, 'message': '錯太多次，請 5 分鐘後再試'}, 429)
        h = E.cfg.get('web_pin_hash'); salt = E.cfg.get('web_pin_salt') or ''
        if not h: return jresp({'ok': False, 'message': '電腦上還沒設定 PIN：到 設定 → 📱 手機網頁 設一個'}, 403)
        rh = E.cfg.get('web_pin_ro_hash') if (E.cfg.get('lab') or {}).get('web_ro') else None   # V0.4.30 👀 唯讀 PIN
        if rh and not same(pin_hash(str(d.get('pin', '')), salt), h) and same(pin_hash(str(d.get('pin', '')), E.cfg.get('web_pin_ro_salt') or ''), rh):
            self.fails.pop(cl, None); tok = rand_hex(24); E.cfg.set('web_tokens_ro', list(E.cfg.get('web_tokens_ro') or [])[-19:] + [tok]); self._tok_meta(tok, req, True)
            self._log(f'手機網頁：👀 唯讀登入（{cl}，{req.headers.get("user-agent", "")[:80]}）')
            return jresp({'ok': True, 'token': tok, 'ro': True}, headers={'Set-Cookie': f'vs_t={tok}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Strict'})
        if not same(pin_hash(str(d.get('pin', '')), salt), h):
            self.fails[cl] = (n + 1, time.time()); self._log(f'手機網頁：PIN 錯誤（{cl}，第 {n + 1} 次）')
            return jresp({'ok': False, 'message': 'PIN 不對' + (f'（再錯 {4 - n} 次會鎖 5 分鐘）' if n >= 1 else '')}, 401)
        self.fails.pop(cl, None); tok = rand_hex(24); L = list(E.cfg.get('web_tokens') or [])[-19:] + [tok]; E.cfg.set('web_tokens', L); self._tok_meta(tok, req, False)
        self._log(f'手機網頁：登入成功（{cl}，{req.headers.get("user-agent", "")[:80]}）')
        return jresp({'ok': True, 'token': tok}, headers={'Set-Cookie': f'vs_t={tok}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Strict'})

    # ---- 靜態
    def icon(self, size):
        if size not in self._icons:                                              # V0.1.58 新圖示（資料夾＋放大鏡）；檔案不在就用舊的畫法
            fn = {512: 'vs_icon_512.png', 192: 'vs_icon_192.png', 'mask': 'vs_icon_mask.png'}.get(size)
            try: self._icons[size] = (Path(__file__).resolve().parent / fn).read_bytes()
            except Exception: self._icons[size] = make_icon_png(size if isinstance(size, int) else 512)
            self._icons[size] = self._pc_badge_png(self._icons[size], size == 'mask')
        return Resp(200, self._icons[size], 'image/png', {'Cache-Control': 'no-cache'})

    def _pc_badge_png(self, data, mask=False):
        """V0.2.27 手機 App 圖示右下角加這台電腦的顏色＋第一個字（失敗就用原本的圖示）."""
        try:
            from PySide6.QtGui import QImage, QPainter, QColor, QFont, QPen
            from PySide6.QtCore import QRectF, Qt, QBuffer, QByteArray, QIODevice
            E = self.E(); img = QImage.fromData(data)
            if img.isNull(): return data
            S = img.width(); d = S * (0.40 if mask else 0.44); x = S - d - S * (0.12 if mask else 0.02)
            p = QPainter(img); p.setRenderHint(QPainter.Antialiasing); r = QRectF(x, x, d, d)
            p.setPen(QPen(QColor('#0b0e13'), max(2, S * 0.035))); p.setBrush(QColor(E.pc_color())); p.drawEllipse(r)
            f = QFont(); f.setPixelSize(int(d * 0.56)); f.setBold(True); p.setFont(f); p.setPen(QColor('#0b0e13')); p.drawText(r, Qt.AlignCenter, (E.pc_name() or '?')[:1].upper()); p.end()
            ba = QByteArray(); buf = QBuffer(ba); buf.open(QIODevice.WriteOnly); img.save(buf, 'PNG'); out = bytes(ba.data())
            return out or data
        except Exception: return data

    def manifest(self):
        nm_ = ''
        try: nm_ = self.E().pc_name()
        except Exception: pass
        m = {'name': f'SortCut {nm_}'.strip(), 'short_name': f'SortCut {nm_}'.strip()[:24], 'start_url': './', 'scope': './', 'display': 'standalone', 'orientation': 'portrait',
             'background_color': '#0b0f14', 'theme_color': '#0b0f14', 'id': 'videosift-phone', 'lang': 'zh-TW',
             'icons': [{'src': 'icon-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'}, {'src': 'icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
                       {'src': 'icon-mask.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'}]}
        return Resp(200, json.dumps(m, ensure_ascii=False).encode('utf-8'), 'application/manifest+json; charset=utf-8')

    def sw(self):
        js = ("const V='vs-%s';self.addEventListener('install',e=>self.skipWaiting());"
              "self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(K=>Promise.all(K.filter(k=>k!==V).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));"
              "self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET'||u.pathname.startsWith('/api/')||u.pathname.startsWith('/fc/api/'))return;"
              "e.respondWith(fetch(e.request).then(r=>{if(r.ok&&(u.pathname==='/'||u.pathname.endsWith('.png'))){const c=r.clone();caches.open(V).then(x=>x.put(e.request,c));}return r;})"
              ".catch(()=>caches.match(e.request).then(r=>r||new Response('<h3 style=\"font-family:sans-serif;color:#ccc;background:#0b0f14\">連不到電腦（Tailscale 有開嗎？電腦開著嗎？）</h3>',{headers:{'Content-Type':'text/html; charset=utf-8'}}))));});") % self.version
        return Resp(200, js.encode('utf-8'), 'application/javascript; charset=utf-8', {'Service-Worker-Allowed': '/'})

    def page(self):
        import vs_webpage
        html = vs_webpage.PAGE.replace('__VER__', str(self.version))
        try:                                                                     # V0.2.27 最上面寫是哪一台電腦
            E = self.E(); nm_ = re.sub(r'[`$\\\'"]', '', str(E.pc_name())).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'); col = E.pc_color()
            tag = f'<span class="pcn" style="color:{col}">● {nm_}</span>'
            html = html.replace('alt="">SortCut</div>', 'alt="">SortCut ' + tag + '</div>').replace('border-radius:11px">SortCut</div>', 'border-radius:11px">SortCut ' + tag + '</div>')
            html = html.replace('<title>SortCut</title>', f'<title>SortCut {nm_}</title>')
        except Exception: pass
        return Resp(200, html.encode('utf-8'), 'text/html; charset=utf-8')

    # ---- 路由
    def route(self, req):
        p = req.path
        if p in ('/', '/index.html'): return self.page()
        if p == '/manifest.webmanifest': return self.manifest()
        if p == '/sw.js': return self.sw()
        if p in ('/icon-192.png', '/icon-512.png', '/favicon.ico'): return self.icon(512 if '512' in p else 192)
        if p in ('/icon-mask.png', '/apple-touch-icon.png'): return self.icon('mask')
        if p == '/fc' or p.startswith('/fc/'): return self.fc_route(req)            # V0.5.00 🗂 整理（FileCompare）的手機版
        if p == '/api/hello': return jresp({'ok': True, 'ver': self.version, 'authed': self.authed(req), 'ro': self.is_ro(req), 'pin_set': bool(self.E().cfg.get('web_pin_hash'))})
        if p == '/api/login' and req.method == 'POST': return self.login(req)
        if not p.startswith('/api/'): return Resp(404, b'not found', 'text/plain')
        if not self.authed(req): return jresp({'ok': False, 'message': '要先輸入 PIN', 'login': True}, 401)
        self.tok_seen(req)
        if req.method != 'GET' and self.is_ro(req): return jresp({'ok': False, 'message': '👀 這支手機是唯讀登入：只能看，不能改（要改請用一般 PIN 登入）'}, 403)   # V0.4.30
        name = p[5:].split('/')[0]; fn = getattr(self, 'api_' + name.replace('-', '_'), None)
        if fn is None: return jresp({'ok': False, 'message': f'沒有這個功能：{name}'}, 404)
        return fn(req)

    # ================================================================ API
    def _ui(self, fn):
        try: self.ui(fn)
        except Exception: pass

    def _pc_rows(self, ids, **kw):
        """手機改了分級／記號：電腦清單、標籤列、資料夾樹跟著更新."""
        def go():
            try:
                B = self.W().browse
                for i in ids: B._upd_row(int(i), **kw)
                B.lst.viewport().update(); B.load_chips(); B.tree_relabel()
                if B.cur and B.cur.get('id') in ids:
                    for k, v in kw.items(): B.cur[k] = v
                    if 'grade' in kw:
                        for kk, x in B.gb.items(): x.setChecked(kk == (kw['grade'] or ''))
            except Exception: pass
        self._ui(go)

    def _pc_reload(self):
        def go():
            try: B = self.W().browse; B.load_list(); B.load_tree()
            except Exception: pass
        self._ui(go)

    def api_rsplit(self, req):
        """V0.5.85 🚚 R 碟清空搬移：GET 看進度；POST {a: plan|start|pause|resume|reset, src, t1, t2}."""
        import vs_rsplit as RS
        E = self.E(); o = RS.get(E)
        if req.method == 'GET' and req.q('lite'):                               # V0.6.52 每一頁的小通知用（很輕）
            Q = o.mq() or {}
            P = o.meta('plan') or {} if Q.get('state') == 'run' else {}
            return jresp({'ok': True, 'mq': {k: Q.get(k) for k in ('state', 'notice', 'msg', 'i')}, 'step': P.get('step', ''), 'st': o.state() if Q else ''})
        if req.method != 'GET':
            if self.is_ro(req): return jresp({'ok': False, 'message': '👀 這支手機是唯讀登入：只能看，不能改'})
            d = req.json() or {}; a = d.get('a', '')
            try:
                if a == 'speed': r = o.set_pace(d)
                elif a == 'plan': r = o.plan(d.get('src') or 'R', [d.get('t1'), d.get('t2')], d.get('mode') or 'auto')
                elif a == 'mq_scan': r = o.mq_scan(d.get('X'))                                       # V0.6.35 📋 多步搬移
                elif a == 'mq_create': r = o.mq_create(d.get('X'), d.get('Y'), d.get('Z'), d.get('only') or [])
                elif a == 'mq_go': r = o.mq_go()
                elif a.startswith('mq_'): r = o.mq_ctl(a[3:])
                else: r = o.ctl(a, d.get('map') if a == 'remap' else None)
            except Exception as ex: E.log.err('🚚 R 碟搬移'); r = {'ok': False, 'message': f'出錯：{ex}'}
            E.log.w(f'🚚 手機／網頁按了 R 碟搬移：{a} → {r.get("message", "") or ("OK" if r.get("ok") else "")}')
            return jresp(r)
        return jresp(o.view())

    def api_yield(self, req):
        """V0.5.71 🤝 讓路給 TikLive：GET 看等級；POST {on, max, nv} 改設定."""
        return jresp(yield_api(self, req))

    def api_dash(self, req):
        """V0.5.68 📊 一頁總覽：k=vs（10 秒剪輯）／h265（瘦身）／fc（整理）；一次算好、20 秒快取."""
        import vs_dash as D
        k = req.q('k', 'vs')
        F = sys.modules.get('fc_app'); FE = getattr(F, 'ENG', None) if F else None
        if type(FE).__name__ != 'Engine': FE = None
        try:
            if k == 'fc':
                if FE is None: return jresp({'ok': False, 'message': '🗂 整理還在準備，等幾秒'})
                return jresp(D.fc(FE))
            if k == 'h265': return jresp(D.h265(self.E(), FE))
            return jresp(D.vs(self.E()))
        except Exception as ex:
            self.E().log.err('📊 總覽'); return jresp({'ok': False, 'message': f'總覽讀不到：{ex}'})

    def api_state(self, req):
        E = self.E(); I = E.info(); s = E.scan_st; J = E.jobs_view()           # V0.6.67 不再每次強制重算（電腦、手機、網頁版一起看時共用同一份）
        th = [{'id': k, 'name': Path(v.get('path') or '').name, 't0': v.get('t0'), 'pct': v.get('pct')} for k, v in list(E.th_active.items())]
        L = {k: bool((E.cfg.get('lab') or {}).get(k)) for k, _n, _v in self.lab_list}
        return jresp({'ok': True, 'ver': self.version, 'time': time.strftime('%H:%M:%S'), 'info': I, 'scan': {'running': s.get('running'), 'n': s.get('n'), 'cur': s.get('cur', '')},
                      'th_active': th, 'th_paused': bool(E.th_paused), 'th_on': bool(E.cfg.get('th_on')), 'cv_paused': bool(E.cv_paused),
                      'jobs': {'cut_active': J['cut_active'], 'conv': J['conv'], 'cv_wait': J['cv_wait'], 'op_active': J['op_active'], 'cuts': J['cuts'][:20]},
                      'offline': sorted((getattr(E, 'offline', None) or {}).keys()), 'db': {k: v for k, v in (getattr(E, 'db_health', None) or {}).items() if k in ('ok', 'msg')},
                      'disks': [{k: d.get(k) for k in ('label', 'media', 'busy', 'th', 'cv', 'note', 'eta')} for d in E.disks_view()], 'lab': L,
                      'disk_warn': (E.disk_warn() if hasattr(E, 'disk_warn') else []), 'goal': (E.day_goal() if hasattr(E, 'day_goal') else None), 'up_goal': (E.up_goal() if hasattr(E, 'up_goal') else None), 'unpub': (E.unpub_n() if hasattr(E, 'unpub_n') else 0), 'cap2': bool(str((E.cfg.get('lab') or {}).get('caption_tpl2') or '').strip()), 'busy': (E.bg_busy() if hasattr(E, 'bg_busy') else []), 'nag_h': int((E.cfg.get('lab') or {}).get('goal_nag_h') or 21), 'brk': (E.break_check() if hasattr(E, 'break_check') else None), 'sprint': (E.sprint_view() if hasattr(E, 'sprint_view') and (E.cfg.get('lab') or {}).get('sprint') else None),
                      'auto_scan': ({k: v for k, v in (getattr(E, '_as', None) or {}).items()} if (E.cfg.get('lab') or {}).get('auto_scan') else None),
                      'note_list': [x.strip() for x in re.split(r'[,，、]+', str((E.cfg.get('lab') or {}).get('note_list') or '可剪,好笑,重看,要上傳')) if x.strip()][:12] if (E.cfg.get('lab') or {}).get('note_presets') else [],
                      'still_left': (E.still_left_c() if ((E.cfg.get('lab') or {}).get('still_scan') or (E.cfg.get('lab') or {}).get('smart_card')) else None),
                      'auto_rule': getattr(E, '_ar_last', None),
                      'theme_hours': [int((E.cfg.get('lab') or {}).get('theme_from', 7)), int((E.cfg.get('lab') or {}).get('theme_to', 19))],
                      'copy': (E.copy_view() if (E.cfg.get('lab') or {}).get('copy_to') and hasattr(E, 'copy_view') else None), 'hz_on': self._hz_on(E)})

    @staticmethod
    def _hz_on(E):
        """V0.6.69 這台有沒有設定 HotZone（沒有＝手機工具也不列 HotZone，跟電腦選單一樣）."""
        try:
            if E.cfg.get('nav_show_hz') is True: return True
            H = getattr(E, 'hz', None); return bool(H is not None and (H.cfg() or {}).get('root'))
        except Exception: return True

    def api_folders(self, req):
        E = self.E(); F = E.folders(); roots = [str(r) for r in E.cfg.get('roots') or []]
        out = [{'path': fd, 'n': n, 'th': th or 0, 'gr': (row[3] if len(row) > 3 else 0) or 0} for row in F for fd, n, th in [row[:3]]]
        return jresp({'ok': True, 'roots': roots, 'folders': out, 'offline': sorted((getattr(E, 'offline', None) or {}).keys())})

    LIST_COLS = ('id', 'name', 'folder', 'ext', 'size', 'dur', 'w', 'h', 'vcodec', 'th_state', 'th_n', 'th_cols', 'th_rows', 'th_step', 'viewed', 'fav', 'grade', 'cut_n', 'tag', 'note', 'card_k', 'still', 'up_t', 'pub_t')

    def api_list(self, req):
        E = self.E(); folder = req.q('folder'); sub = req.q('sub', '1') != '0'; sort = req.q('sort', 'name'); flt = req.q('flt', 'all'); search = req.q('q')
        off = max(0, int(req.q('off', '0') or 0)); lim = max(1, min(500, int(req.q('lim', '120') or 120)))
        if folder and off == 0:
            try: E.recent_push(folder)                                          # V0.2.56 🕘 最近開過的資料夾
            except Exception: pass
        _d, _r = (req.q('dur', '') if (E.cfg.get('lab') or {}).get('dur_chips') else ''), (req.q('res', '') if (E.cfg.get('lab') or {}).get('res_chips') else '')
        if hasattr(E, 'list_page'): total, R = E.list_page(folder, sub, sort, flt, search, _d, _r, off, lim)   # V0.6.63 只撈這一頁
        else: R = E.list_files(folder, sub, sort, flt, search, _d, _r); total = len(R); R = R[off:off + lim]
        rows = [{k: r.get(k) for k in self.LIST_COLS} for r in R]
        if rows:                                                                # 👤 卡片上顯示出現的人（取了名字的）
            ppl = {}
            for fid, nm, n in E.db.q(f"SELECT file_id, name, n FROM people WHERE length(name)>0 AND file_id IN ({','.join(str(int(r['id'])) for r in rows)}) ORDER BY n DESC"):
                ppl.setdefault(fid, []).append(nm)
            for r in rows: r['people'] = ppl.get(r['id'], [])[:3]
            CP = E.cut_pending() if hasattr(E, 'cut_pending') else {}             # V0.2.02 剪輯中幾段（卡片「-剪輯 N」）
            for r in rows: r['cut_pend'] = CP.get(r['id'], 0)
        hid = E.hidden_count(folder, sub) if not str(flt).startswith('ext:') and off == 0 else []
        return jresp({'ok': True, 'total': total, 'off': off, 'rows': rows, 'chips': E.grade_summary(folder, sub) if off == 0 else {}, 'hidden': hid})

    def api_file(self, req):
        E = self.E(); fid = int(req.q('id', '0') or 0); f = E.file(fid)
        if not f: return jresp({'ok': False, 'message': '找不到這部影片'}, 404)
        if f.get('th_state') != 2:
            try: E.thumb_front(fid)                                             # 手機在看的先做預覽圖
            except Exception: pass
        out = {k: f.get(k) for k in self.LIST_COLS + ('path', 'fps', 'acodecs', 'arch', 'last_pos', 'cv_state', 'missing', 'th_err')}
        out['sheets'] = len(E.sheets(f)); out['cuts'] = [Path(x).name for x in E.cut_outputs(fid)]
        out['playable'] = (f.get('ext') or '').lower() in ('.mp4', '.m4v', '.webm', '.mov') and (f.get('vcodec') or '') in ('h264', 'hevc', 'vp9', 'av1', 'vp8', '')
        A = E.cfg.get('arch_names') or {}; out['arch_targets'] = [{'kind': f'grade:{g}', 'name': A.get(g, g)} for g in ('S', 'A', 'E', 'F')] + [{'kind': f'cat:{c}', 'name': c} for c in (E.cfg.get('cats') or [])]
        out['bm'] = E.bm_list(fid) if (E.cfg.get('lab') or {}).get('bookmarks') else []   # V0.2.80 🔖
        E.last_file_set(fid)
        try: out['guess'] = E.grade_guess(fid)                                 # V0.2.62 🤖 分級建議
        except Exception: out['guess'] = None
        try: out['dup_up'] = (E.up_dups([fid]).get(int(fid), '') if (E.cfg.get('lab') or {}).get('copy_to') and not float(f.get('up_t') or 0) else '')   # V0.3.98 ♻
        except Exception: out['dup_up'] = ''
        out['grid_sec'] = int(E.cfg.get('grid_sec') or 2); out['cut_merge'] = bool(E.cfg.get('cut_merge')); out['th_running'] = int(fid) in E.th_active
        return jresp({'ok': True, 'file': out})

    def _img(self, p, cache=True):
        try:
            p = Path(p)
            if not p.is_file(): return Resp(404, b'', 'text/plain')
            return Resp(200, p.read_bytes(), CT.get(p.suffix.lower(), 'application/octet-stream'), {'Cache-Control': 'private, max-age=600' if cache else 'no-store'})
        except Exception: return Resp(404, b'', 'text/plain')

    def api_sheet(self, req):
        E = self.E(); f = E.file(int(req.q('id', '0') or 0))
        if not f: return Resp(404, b'', 'text/plain')
        S = E.sheets(f); i = int(req.q('i', '0') or 0)
        return self._img(S[i]) if 0 <= i < len(S) else Resp(404, b'', 'text/plain')

    @staticmethod
    def card_index(r):
        """跟電腦上的卡片同一張（app.card_k 的算法）：自己換過用那張，不然每部固定一張「隨機」的（避開頭尾 10%）."""
        import random
        n = int(r.get('th_n') or 0)
        if n <= 0: return 0
        k = int(r.get('card_k') if r.get('card_k') is not None else -1)
        if 0 <= k < n: return k
        lo = int(n * 0.1); hi = max(lo, int(n * 0.9) - 1)
        return random.Random(int(r['id']) * 7919).randint(lo, hi)

    def api_card(self, req):
        """卡片縮圖（小張）：電腦上存過的 card_N.jpg 直接給；沒有就用 ffmpeg 從大張切一張存起來（和電腦共用，下次直接讀）."""
        E = self.E(); f = E.file(int(req.q('id', '0') or 0))
        if not f or not f.get('th_dir') or f.get('th_state') != 2: return Resp(404, b'', 'text/plain')
        d = Path(f['th_dir']); k = self.card_index(f); cp = d / f'card_{k}.jpg'
        if cp.is_file(): return self._img(cp)
        S = E.sheets(f); cols = int(f.get('th_cols') or 10); rows = int(f.get('th_rows') or 10); per = cols * rows
        si = min(len(S) - 1, k // per) if S else -1
        if si < 0 or not E.ff: return Resp(404, b'', 'text/plain')
        q = k % per; x, y = q % cols, q // cols
        tmp = d / f'card_{k}.web.jpg'
        cmd = [E.ff, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-i', S[si], '-vf', f'crop=iw/{cols}:ih/{rows}:{x}*iw/{cols}:{y}*ih/{rows},scale=\'min(360,iw)\':-2', '-frames:v', '1', '-q:v', '4', str(tmp)]
        try:
            subprocess.run(cmd, capture_output=True, timeout=20, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
            if tmp.is_file() and tmp.stat().st_size > 0: os.replace(str(tmp), str(cp)); return self._img(cp)
        except Exception: pass
        try: tmp.unlink()
        except Exception: pass
        return Resp(404, b'', 'text/plain')

    def api_video(self, req):
        """手機播放：支援 Range（拖時間軸）。只讀，不會改檔案."""
        E = self.E(); f = E.file(int(req.q('id', '0') or 0))
        p = (f or {}).get('path') if not req.q('out') else None
        if req.q('out'):
            outs = E.cut_outputs(int(req.q('id', '0') or 0)); nm = req.q('out'); p = next((x for x in outs if Path(x).name == nm), None)
        if not p or not os.path.isfile(p): return Resp(404, b'', 'text/plain')
        total = os.path.getsize(p); a, b = 0, total - 1; code = 200
        m = re.match(r'bytes=(\d*)-(\d*)', req.headers.get('range') or '')
        if m:
            if m.group(1): a = int(m.group(1)); b = int(m.group(2)) if m.group(2) else total - 1
            elif m.group(2): a = max(0, total - int(m.group(2)))
            b = min(b, total - 1)
            if a > b: return Resp(416, b'', 'text/plain', {'Content-Range': f'bytes */{total}'})
            code = 206
        return Resp(code, b'', CT.get(Path(p).suffix.lower(), 'application/octet-stream'), {'Cache-Control': 'no-store'}, file=(p, a, b, total))

    def api_vinfo(self, req):
        """V0.1.89 手機播不了時：查這個檔（存不存在、編碼、10-bit、標記、大小），寫進 LOG，告訴手機可能的原因."""
        E = self.E(); fid = int(req.q('id', '0') or 0); f = E.file(fid) or {}; p = f.get('path') or ''
        if req.q('out'):
            p = next((x for x in E.cut_outputs(fid) if Path(x).name == req.q('out')), '') or ''
        err = req.q('err'); r = {'ok': True, 'id': fid, 'name': Path(p).name if p else '', 'exists': bool(p) and os.path.isfile(p)}
        why = []
        drv = os.path.splitdrive(p)[0] if p else ''
        if p and drv and not os.path.exists(drv + os.sep): why.append(f'💤 {drv} 硬碟離線（拔掉、睡著或 USB 斷線）：檔案沒有刪，接回來就能播'); r['offline'] = drv
        elif not r['exists']: why.append('電腦上找不到這個檔（可能被搬走、刪掉，或正在重轉）')
        else:
            r['size'] = os.path.getsize(p)
            try:
                o = subprocess.run([E.ffprobe, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_name,codec_tag_string,profile,pix_fmt,width,height', '-of', 'json', p],
                                   capture_output=True, timeout=20, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), stdin=subprocess.DEVNULL)
                s = (json.loads(o.stdout.decode('utf-8', 'replace') or '{}').get('streams') or [{}])[0]
            except Exception as ex: s = {'err': str(ex)}
            r.update(codec=s.get('codec_name') or '', tag=s.get('codec_tag_string') or '', profile=s.get('profile') or '', pix=s.get('pix_fmt') or '', w=s.get('width'), h=s.get('height'))
            if not s.get('codec_name'): why.append('讀不出影像（檔案可能壞了、還沒轉完，或正被別的程式寫入）')
            elif r['codec'] == 'hevc':
                if '10' in r['pix']: why.append('這是 10-bit 的 H.265：很多手機瀏覽器不能播（電腦上可以）')
                if r['tag'] != 'hvc1': why.append(f'H.265 的標記是 {r["tag"]}（不是 hvc1）：iPhone／部分瀏覽器不能播')
                if not why: why.append('這是 H.265：這支手機的瀏覽器可能不支援 H.265，或同時播太多支把手機的解碼器佔滿了（先關掉其他影片、重新整理再試）')
            elif r['codec'] not in ('h264', 'vp9', 'av1'): why.append(f'編碼 {r["codec"]} 手機瀏覽器多半不能播')
        if not why: why.append('格式手機應該能播：可能是連線中斷、手機暫時解碼失敗，關掉再開一次；還是不行請把這段告訴我')
        r['why'] = why
        E.log.w(f'📱 手機播不了：id {fid} {p}（手機錯誤碼 {err or "?"}）→ ' + (f"{r.get('codec')}/{r.get('tag')}/{r.get('pix')} {r.get('w')}×{r.get('h')} {(r.get('size') or 0) / 1048576:.1f} MB" if r['exists'] else '找不到檔案') + '；' + '；'.join(why))
        return jresp(r)

    def api_flags(self, req):
        """分級、收藏、看過、顏色標籤、備註（可以一次很多部）."""
        E = self.E(); d = req.json(); ids = [int(i) for i in d.get('ids') or []]; kw = {}
        for k in ('grade', 'fav', 'viewed', 'tag', 'note'):
            if k in d: kw[k] = d[k]
        if 'grade' in kw and kw['grade'] not in GRADES: return jresp({'ok': False, 'message': '分級只能是 S A E F 或空白'})
        for k in ('fav', 'viewed'):
            if k in kw: kw[k] = 1 if kw[k] else 0
        if not ids or not kw: return jresp({'ok': False, 'message': '沒有要改的'})
        old = {r['id']: dict(r) for r in E.db.q('SELECT id,grade,fav,viewed,tag,note FROM files WHERE id IN (%s)' % ','.join(map(str, ids)))}
        E.set_flags(ids, **kw); E.log.w(f'📱 手機：{len(ids)} 部 ' + '、'.join(f'{k}={v!r}' for k, v in kw.items()))
        self._pc_rows(ids, **kw)
        return jresp({'ok': True, 'n': len(ids), 'undo': [{'id': i, **{k: (old.get(i) or {}).get(k) for k in kw}} for i in ids]})

    def api_undo_flags(self, req):
        E = self.E(); L = req.json().get('undo') or []; n = 0
        for x in L:
            field = [k for k in x if k != 'id']
            for k in field:
                if k in ('grade', 'fav', 'viewed', 'tag', 'note'): E.set_values([(int(x['id']), x[k] if x[k] is not None else '')], k); n += 1
        if L: self._pc_rows([int(x['id']) for x in L], **{k: v for k, v in L[0].items() if k != 'id'}) if len(L) == 1 else self._pc_reload()
        return jresp({'ok': True, 'n': n})

    def api_cut(self, req):
        E = self.E(); d = req.json(); segs = [(float(a), float(b)) for a, b in d.get('segs') or []]
        r = E.cut_add(int(d.get('id') or 0), segs, merge=bool(d.get('merge')) if 'merge' in d else None)
        if r.get('ok'): E.log.w(f'📱 手機：初剪 {len(segs)} 段'); self._ui(lambda: self.W()._status())
        return jresp(r)

    def api_op(self, req):
        """收藏、移到待刪、歸檔（grade:S／cat:工作用）、加入轉檔、先做預覽圖、刪除已剪輯的原檔、排除資料夾、重做預覽圖."""
        E = self.E(); d = req.json(); kind = str(d.get('kind') or ''); ids = [int(i) for i in d.get('ids') or []]
        if not ids and kind not in ('exclude_folder',): return jresp({'ok': False, 'message': '沒有選影片'})
        E.log.w(f'📱 手機：{kind} {len(ids)} 部')
        if kind in ('fav', 'trash') or kind.startswith('grade:') or kind.startswith('cat:'):
            n = E.archive_many(ids, kind) if kind != 'fav' else sum(1 for i in ids if E.file_op(i, 'fav').get('ok'))
            self._pc_reload(); return jresp({'ok': n > 0, 'n': n, 'message': f'{n} 部排進搬檔隊伍'})
        if kind == 'conv': E.conv_add(ids); return jresp({'ok': True, 'message': f'{len(ids)} 部加入轉檔'})
        if kind == 'conv_cancel': n = E.conv_cancel(ids); return jresp({'ok': True, 'message': '已從轉檔排隊拿掉'})
        if kind == 'front':
            for i in ids: E.thumb_front(i)
            return jresp({'ok': True, 'message': '排到最前面做預覽圖'})
        if kind == 'thumb_cancel':                                              # V0.1.97 停掉正在做的這部（跳過，晚點再做）
            for i in ids: E.thumb_cancel(i, skip=True)
            return jresp({'ok': True, 'message': '已停掉這部的預覽圖（跳過，之後再做）'})
        if kind == 'redo_precise':
            for i in ids: E.thumb_redo(i, precise=True)
            return jresp({'ok': True, 'message': f'{len(ids)} 部重做預覽圖（精準）'})
        if kind == 'delete_original':
            r = E.delete_original_many(ids, permanent=False); self._pc_reload()
            return jresp({'ok': r.get('ok', 0) > 0, 'message': f'刪了 {r.get("ok", 0)} 部原檔（丟到資源回收筒）' + (f'；{len(r.get("fail") or [])} 部沒刪：' + '、'.join(f'{a}（{b}）' for a, b in (r.get('fail') or [])[:5]) if r.get('fail') else '')})
        if kind == 'exclude_folder':
            fd = str(d.get('folder') or '')
            if not fd: return jresp({'ok': False, 'message': '沒有資料夾'})
            E.add_exclude(path=fd); n = E.apply_excludes(); self._pc_reload(); return jresp({'ok': True, 'message': f'排除了，拿掉 {n} 部'})
        return jresp({'ok': False, 'message': f'不認得的動作 {kind}'})

    def api_control(self, req):
        """暫停／繼續（預覽圖、轉檔、全部）、掃描、電腦切到封面、讀失敗的重做."""
        E = self.E(); W = self.W(); a = str(req.json().get('a') or ''); E.log.w(f'📱 手機：{a}')
        def set_th(on):
            E.th_paused = on
            self._ui(lambda: (W.bgp.b_th.setChecked(on)) if hasattr(W, 'bgp') else None)
        def set_cv(on):
            E.cv_paused = on
            self._ui(lambda: (W.conv.b_pause.setChecked(on)) if hasattr(W, 'conv') else None)
        if a == 'pause_all': set_th(True); set_cv(True); getattr(E, 'fc_pause_all', lambda o: None)(True); return jresp({'ok': True, 'message': '⏸ 全部暫停（正在做的做完就停；整理的背景也一起）'})
        if a == 'resume_all': set_th(False); set_cv(False); getattr(E, 'fc_pause_all', lambda o: None)(False); return jresp({'ok': True, 'message': '▶ 全部繼續'})
        if a in ('pause_th', 'resume_th'): set_th(a == 'pause_th'); return jresp({'ok': True})
        if a in ('pause_cv', 'resume_cv'): set_cv(a == 'pause_cv'); return jresp({'ok': True})
        if a == 'scan': ok = E.scan(); return jresp({'ok': ok, 'message': '開始掃描' if ok else '已經在掃描了（或還沒加硬碟）'})
        if a == 'retry_failed': n = E.thumb_retry_failed(); return jresp({'ok': True, 'message': f'{n or 0} 部重新排隊'})
        if a == 'cover': self._ui(lambda: W.show_cover()); return jresp({'ok': True, 'message': '🏠 電腦已切到封面'})
        if a == 'conv_cancel_all': n = E.conv_cancel(); return jresp({'ok': True, 'message': f'取消 {n or 0} 部排隊中的轉檔'})
        return jresp({'ok': False, 'message': '不認得的動作'})

    def api_conv(self, req):
        E = self.E(); R = E.nonmp4(req.q('folder'), req.q('sub', '1') != '0')
        keep = ('id', 'name', 'folder', 'ext', 'size', 'dur', 'w', 'h', 'vcodec', 'cv_state', 'cv_err', 'cv_ratio', 'cv_ssim')
        st = req.q('st'); R = [r for r in R if not st or str(r.get('cv_state') or 0) == st]
        return jresp({'ok': True, 'total': len(R), 'rows': [{k: r.get(k) for k in keep} for r in R[:1500]]})

    def api_bg(self, req):
        """🖥 後台總覽（每一件正在跑的事、剩幾個、速度、還要多久）＋暫停狀態."""
        E = self.E(); ctl = E.bg_view() if hasattr(E, 'bg_view') else None
        return jresp({'ok': True, 'items': E.bg_overview(), 'th_paused': bool(E.th_paused), 'cv_paused': bool(E.cv_paused), 'time': time.strftime('%H:%M:%S'), 'ctl': ctl, 'fc': (E.fc_bg() if hasattr(E, 'fc_bg') else None)})

    def api_learn(self, req):
        """V0.1.65 📈 滾動式參數：GET 看經驗；POST a＝reset（k＝類型，空＝全部）／cfg（規則）."""
        E = self.E()
        if req.method == 'POST':
            d = req.json(); a = d.get('a'); E.log.w(f'📱 手機：滾動式參數 {a}')
            if a == 'reset': E.learn_reset(d.get('k') or None)
            elif a == 'cfg':
                L = dict(E.cfg.get('learn') or {})
                try:                                                            # 先全部檢查過再存（亂填的值會讓轉檔整個卡住）
                    V_ = {}
                    if 'on' in d: V_['on'] = d['on'] is True or str(d['on']).lower() in ('1', 'true', 'on')
                    for k, lo, hi in (('lite_n', 1, 1000), ('quick_n', 1, 2000), ('trust_n', 5, 5000)):
                        if k in d: V_[k] = max(lo, min(hi, int(d[k])))
                    if 'floor' in d: V_['floor'] = max(0.9, min(0.999, float(d['floor'])))
                    if 'spot' in d: V_['spot'] = max(0.0, min(1.0, float(d['spot'])))
                except (TypeError, ValueError): return jresp({'ok': False, 'message': '數值不對'}, 400)
                L.update(V_); E.cfg.set('learn', L)
        V = E.learn_view(); V['recent'] = V['recent'][:80]; V['target'] = float(E.cfg.get('cv_target') or 0.985)
        return jresp(dict(V, ok=True))

    def api_bgctl(self, req):
        """V0.1.65 後台總控制：a＝pause／resume／stop（立刻停）／up／down／all_pause／all_resume／guard（cpu_guard、cpu_max、ramp_sec）."""
        E = self.E(); d = req.json() if req.method == 'POST' else {}; a = d.get('a'); k = d.get('k'); E.log.w(f'📱 手機：後台 {a} {k or ""}')
        if a in ('pause', 'resume', 'stop', 'up', 'down') and k not in {x[0] for x in E.BG_KINDS}: return jresp({'ok': False, 'message': '不認得的項目'}, 400)
        if a == 'guard':
            try:
                cm = max(50, min(100, int(d['cpu_max']))) if d.get('cpu_max') else None
                rs = max(0, min(300, int(d['ramp_sec']))) if d.get('ramp_sec') is not None else None
            except (TypeError, ValueError): return jresp({'ok': False, 'message': '數值不對'}, 400)
            if 'on' in d: E.cfg.set('cpu_guard', d['on'] is True or str(d['on']).lower() in ('1', 'true', 'on'))
            if cm is not None: E.cfg.set('cpu_max', cm)
            if rs is not None: E.cfg.set('bg_ramp_sec', rs)
            if 'mf' in d: E.cfg.set('main_first', d['mf'] is True or str(d['mf']).lower() in ('1', 'true', 'on'))   # V0.6.08 🛟 主程式優先
            if d.get('mf_lag'): E.cfg.set('mf_lag_ms', max(150, min(3000, int(d['mf_lag']))))
        if a == 'pause': E.bg_set_pause(k, True, '手機')
        elif a == 'resume': E.bg_set_pause(k, False, '手機')
        elif a == 'stop': E.bg_stop_now(k)
        elif a in ('up', 'down'): E.bg_move(k, -1 if a == 'up' else 1)
        elif a == 'all_pause': E.bg_all(True)
        elif a == 'all_resume': E.bg_all(False)
        elif a == 'pack_now':                                                   # V0.2.26 💾 現在寫到各硬碟
            r_ = E.pack_export_due(force=True, why='（手機按的）'); d_, left_ = E.pack_left()
            return jresp({'ok': True, 'ctl': E.bg_view(), 'message': ('💾 已寫到：' + '、'.join(x + ':' for x in r_) if r_ else '都是最新的') + (f'（預覽圖還有 {left_:,} 部在搬，搬完再拔）' if left_ else '　✔ 可以關掉程式、拔硬碟')})
        self._ui(lambda: getattr(self.W(), 'bgp', None) and self.W().bgp.refresh_ctl())
        return jresp({'ok': True, 'ctl': E.bg_view()})

    def api_goal(self, req):
        E = self.E()
        if req.method == 'POST':
            d = req.json(); G = dict(E.cfg.get('shrink_goal') or {})
            if d.get('reset'): return jresp({'ok': True, 'goal': E.goal_view(reset=True)})
            if 'days' in d: G['days'] = max(1, min(365, int(d['days'])))
            if 'ratio' in d: G['ratio'] = max(0.05, min(0.95, float(d['ratio'])))
            E.cfg.set('shrink_goal', G); E.log.w(f'📱 手機：瘦身目標 {G}')
        return jresp({'ok': True, 'goal': E.goal_view()})

    def api_explore(self, req):
        """V0.6.19 🗺 檔案總覽：GET prefix（空＝每個影片庫）、sort（size／n／save／name）；q＝搜尋（像 Everything）."""
        E = self.E(); q = req.q('q', '') or ''; pf = req.q('prefix', '') or ''; so = req.q('sort', 'size') or 'size'
        try:
            if q.strip(): return jresp(E.explore_search(q, pf, so, int(req.q('limit', '300') or 300)))
            return jresp(E.explore(pf, so))
        except Exception as ex:
            E.log.err('🗺 檔案總覽'); return jresp({'ok': False, 'message': f'讀不到：{ex}'})

    def api_conv2(self, req):
        """🔁 轉檔工作區：選檔（種類／類型／大小／資料夾／排序）、轉檔中、轉檔完成（刪原檔、搬回）、失敗."""
        E = self.E()
        if req.method == 'POST':
            d = req.json(); a = d.get('a'); E.log.w(f'📱 手機：轉檔 {a}')
            raw = d.get('ids'); ids = [int(x) for x in raw] if isinstance(raw, list) else []
            ALL = d.get('all') is True                                          # V0.1.87「全部」要明講（以前空的就當全部：選取被清掉時會動到全部的檔）
            if a in ('cancel', 'purge', 'redo', 'reverify', 'stage', 'undo') and not ids and not ALL: return jresp({'ok': False, 'message': '沒有選任何一部'}, 400)
            if a == 'add_filtered':
                n = E.conv_add_filtered(d.get('exts') or [], d.get('smin') or 0, d.get('smax') or 0, d.get('folders') or [], d.get('sort') or 'size_desc', d.get('kind') or 'nonmp4', int(d.get('limit') or 0))
                r = {'ok': True, 'n': n, 'message': f'已排入 {n:,} 部'}
            elif a == 'add': n = E.conv_add(ids); r = {'ok': True, 'n': n, 'message': f'已排入 {n} 部'}
            elif a == 'cancel': n = E.conv_cancel(ids or None); r = {'ok': True, 'message': f'取消 {n or 0} 部'}
            elif a == 'reorder': n = E.conv_reorder(d.get('sort') or 'smart'); r = {'ok': True, 'message': f'排隊 {n} 部重新排序'}
            elif a == 'purge': r = E.conv_purge(ids if ids else None)
            elif a == 'restore': r = E.conv_restore(ids)
            elif a == 'redo_force': r = E.conv_redo(ids, True, True)
            elif a == 'redo': r = E.conv_redo(ids if ids else [i for i in E.conv_below() if (E.file(i) or {}).get('cv_del')])   # V0.1.65 用 DELETE 裡的原檔重轉
            elif a == 'reverify': r = E.conv_reverify(ids if ids else E.conv_below())        # V0.1.66 用修正後的方法重新驗證
            elif a == 'undo_low': r = E.conv_undo(E.conv_below())                         # V0.1.65 畫質沒到目標的全部還原
            elif a == 'stage': r = E.conv_stage(ids if ids else None)
            elif a == 'undo': r = E.conv_undo(ids if ids else E.conv_bigger())  # ids 空＝ALL（上面檢查過）             # V0.1.57 轉大的還原
            elif a == 'seen': E.set_flags(ids, viewed=1); r = {'ok': True}
            elif a == 'tag_vs': r = E.conv_tag_vs(dry=bool(d.get('dry')))
            elif a == 'trial':                                                  # V0.1.97 🧪 試轉 10 秒（背景跑，手機輪詢）
                j = self.jobs.get('trial')
                if j and j.get('run'): return jresp({'ok': False, 'message': '上一個試轉還在跑'})
                if not ids: return jresp({'ok': False, 'message': '沒有選任何一部'}, 400)
                try: secs = max(3.0, min(60.0, float(d.get('secs') or 10)))
                except (TypeError, ValueError): secs = 10.0
                j = {'run': True, 'msg': '試轉中…', 'res': None, 't0': time.time(), 'fid': ids[0]}; self.jobs['trial'] = j
                def work():
                    try:
                        R = E.conv_trial(ids[0], None, None, secs)
                        j['res'] = {k: R.get(k) for k in ('name', 'secs', 'at', 'bytes', 'pred', 'est', 'osz', 'ratio', 'ssim', 'enc', 'elapsed', 'speed', 'full_time', 'w', 'h', 'kbps', 'src_kbps', 'kn')}
                        j['msg'] = '完成'
                    except Exception as ex: j['msg'] = f'試轉失敗：{ex}'
                    finally: j['run'] = False
                threading.Thread(target=work, name='VsWebTrial', daemon=True).start()
                return jresp({'ok': True, 'message': '🧪 試轉中…'})
            else: return jresp({'ok': False, 'message': '不認得的動作'})
            self._ui(lambda: getattr(self.W(), 'conv', None) and self.W().conv.refresh_tab())
            return jresp(r)
        a = req.q('a') or 'cand'
        if a == 'cand':
            L = lambda k: [x for x in (req.q(k) or '').split(',') if x]
            kind = req.q('kind') or 'nonmp4'; smin = float(req.q('smin') or 0); smax = float(req.q('smax') or 0); F = [x for x in (req.q('folders') or '').split('|') if x]
            c = E.conv_candidates(L('exts'), smin, smax, F, req.q('sort') or 'smart', (0, 4, 5), 400, kind)
            w_, a_ = E.conv_where(None, smin, smax, F, (0, 4, 5), kind)
            c['exts'] = [[e, n, b or 0] for e, n, b in E.db.q(f'SELECT ext, COUNT(*), SUM(size) FROM files WHERE {w_} GROUP BY ext ORDER BY 3 DESC', a_)]
            c['ratio'] = E.conv_ratio(); c['ok'] = True; return jresp(c)
        if a == 'plan':                                                         # V0.6.11 📏 數量與目標
            L = lambda k: [x for x in (req.q(k) or '').split(',') if x]
            P = E.conv_plan(L('exts'), float(req.q('smin') or 0), float(req.q('smax') or 0), [x for x in (req.q('folders') or '').split('|') if x],
                            req.q('sort') or 'size_desc', req.q('kind') or 'nonmp4', int(float(req.q('n') or 0)), float(req.q('t') or 0))
            return jresp(P)
        if a == 'queue':
            R = E.conv_queue(1000); return jresp({'ok': True, 'rows': R, 'paused': bool(E.cv_paused), 'total': len(R), 'eta': E.conv_eta()})
        if a == 'done':
            D = E.conv_done_list(req.q('q') or '', req.q('sort') or 't_desc', 1500); D['ok'] = True; return jresp(D)
        if a == 'trial':
            j = self.jobs.get('trial'); return jresp({'ok': True, 'job': {k: j.get(k) for k in ('run', 'msg', 'res', 'fid')} if j else None})
        if a == 'fail':
            R = [dict(r) for r in E.db.q('SELECT id,name,folder,size,cv_state,cv_err FROM files WHERE cv_state IN (4,6) AND missing=0 ORDER BY cv_t DESC, id DESC LIMIT 1500')]
            return jresp({'ok': True, 'rows': R})
        return jresp({'ok': False, 'message': '不認得'})

    def api_hz(self, req):
        """🔥 HotZone：狀態、啟動／停止／接手、檢查環境、安裝、協調員設定."""
        E = self.E(); H = getattr(E, 'hz', None)
        if H is None: return jresp({'ok': False, 'message': 'HotZone 模組沒有載入'})
        if req.method == 'POST':
            d = req.json(); a = d.get('a'); E.log.w(f'📱 手機：HotZone {a}')
            if a in ('start', 'stop', 'takeover', 'check', 'diag', 'use', 'keep'):   # V0.1.87 會等很久的（UAC、等引擎結束、PowerShell）：在背景做，手機看狀態
                if a == 'use':
                    pth = str(d.get('path') or '')
                    if not any(os.path.normcase(c['path']) == os.path.normcase(pth) for c in (H.cands or [])): return jresp({'ok': False, 'message': '這個資料夾不在找到的清單裡（先按「🩺 連線診斷」）'})
                F = {'start': lambda: H.start('手機'), 'stop': lambda: H.stop('手機'), 'takeover': H.takeover, 'keep': H.keep_original,
                     'check': lambda: (H.check_env(), {'ok': True, 'message': '檢查好了'})[1], 'diag': H.diagnose,
                     'use': lambda: H.set_root(pth, getattr(H, 'ui_before', None))}[a]
                return jresp(H.run_job(a, F))
            if a == 'open': r = H.open_ui()
            elif a == 'migrate': r = H.migrate_bg('手機')
            elif a == 'install': r = H.install(bool(d.get('window')))
            elif a == 'cfg':
                try:
                    kw = {k: (d[k] is True or str(d[k]).lower() in ('1', 'true', 'on')) for k in ('auto', 'arb') if k in d}
                    for k, lo, hi in (('slice_min', 1, 120), ('busy_pct', 50, 100), ('hz_mbps', 1, 500)):
                        if k in d: kw[k] = max(lo, min(hi, int(d[k])))
                except (TypeError, ValueError): return jresp({'ok': False, 'message': '數值不對'}, 400)
                H.set_cfg(**kw); r = {'ok': True, 'message': '✔ 已儲存'}
            else: return jresp({'ok': False, 'message': '不認得的動作'})
            return jresp(r)
        st = H.status(); st['ok'] = True; return jresp(st)

    def api_ops(self, req):
        E = self.E(); L = E.oplog_query(req.q('q'), req.q('kind'), int(req.q('days', '30') or 30), 500)
        return jresp({'ok': True, 'rows': [{k: r.get(k) for k in ('id', 't', 'kind', 'name', 'src', 'dst', 'size', 'detail', 'ok', 'undone')} for r in L]})

    def api_ops_undo_last(self, req):
        if req.method != 'POST': return jresp({'ok': False, 'message': '要用 POST'}, 405)
        E = self.E(); d = req.json() or {}; r = E.oplog_undo_last(dry=bool(d.get('dry')))
        if not d.get('dry'): self._pc_reload()
        return jresp(r)

    def api_ops_undo(self, req):
        E = self.E(); r = E.oplog_undo(int(req.json().get('id') or 0)); self._pc_reload(); return jresp(r)

    # ================================================================ V0.1.97 手機也能管影片庫（電腦有的手機也要有）
    def _lib_info(self):
        E = self.E(); off = set(getattr(E, 'offline', None) or {}); R = []
        for r in E.cfg.get('roots') or []:
            r = str(r)
            try: n = (E.db.one('SELECT COUNT(*) FROM files WHERE root=? AND missing=0', (r,)) or [0])[0]
            except Exception: n = 0
            R.append({'path': r, 'n': n, 'offline': r in off})
        U = getattr(E, 'usb', None); us = None
        if U is not None:
            try: us = U.status()
            except Exception: us = None
        B = [{'name': a, 't': b, 'size': c} for a, b, c in (E.db_backups() if hasattr(E, 'db_backups') else [])[:30]]
        return {'ok': True, 'roots': R, 'ex_dirs': [str(x) for x in E.cfg.get('ex_dirs') or []], 'ex_names': [str(x) for x in E.cfg.get('ex_names') or []],
                'cats': [str(x) for x in E.cfg.get('cats') or []], 'backups': B, 'usb': us,
                'guard': {'on': E.cfg.get('cpu_guard') is not False, 'mf': E.cfg.get('main_first') is not False, 'mf_lag': int(E.cfg.get('mf_lag_ms') or 400), 'cpu_max': int(E.cfg.get('cpu_max') or 90), 'ramp_sec': int(E.cfg.get('bg_ramp_sec') if E.cfg.get('bg_ramp_sec') is not None else 20)},
                'scan': {'running': bool(E.scan_st.get('running')), 'n': E.scan_st.get('n'), 'cur': E.scan_st.get('cur', '')}}

    def api_lib(self, req):
        """💽 影片庫：硬碟／資料夾加入、移除、重新掃描；排除清單；分類資料夾；資料庫備份還原；USB 硬碟救回；資料夾的 ⚙（先做預覽圖、一鍵歸檔）."""
        E = self.E()
        if req.method != 'POST':
            a = req.q('a') or 'info'
            if a == 'info': return jresp(self._lib_info())
            if a == 'trash': r = E.trash_purge(dry=True, folder=req.q('folder') or ''); r.pop('dirs', None); return jresp(r)
            if a == 'iso': r = E.iso_list(); r['ok'] = True; return jresp(r)                                       # V0.2.24 🗄 讀不到的（隔離中）                 # V0.2.01 清空待刪：先看有幾個
            if a == 'dirs':                                                     # 手機上「＋ 加硬碟」：瀏覽電腦上的資料夾
                p = req.q('path') or ''
                if not p:
                    if os.name == 'nt': D = [f'{c}:\\' for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.exists(f'{c}:\\')]
                    else: D = ['/']
                    return jresp({'ok': True, 'path': '', 'dirs': [{'name': d, 'path': d} for d in D]})
                try:
                    with os.scandir(p) as it:
                        D = sorted((x.name for x in it if not x.name.startswith(('$', '.')) and x.is_dir(follow_symlinks=False)), key=str.lower)[:1000]
                except Exception as ex: return jresp({'ok': False, 'message': f'打不開：{ex}'})
                up = os.path.dirname(p.rstrip('\\/')) if p.rstrip('\\/') != p.rstrip('\\/')[:2] else ''
                if up and up.endswith(':'): up += '\\'
                return jresp({'ok': True, 'path': p, 'up': up if up != p else '', 'dirs': [{'name': n, 'path': os.path.join(p, n)} for n in D]})
            if a == 'fold':
                fd = req.q('folder') or ''; C = E.grade_counts(fd)
                is_root = any(os.path.normcase(os.path.normpath(fd)) == os.path.normcase(os.path.normpath(str(r))) for r in E.cfg.get('roots') or []) if fd else False
                return jresp({'ok': True, 'folder': fd, 'is_root': is_root, 'grades': {g: list(C.get(g, (0, 0))) for g in ('S', 'A', 'E', 'F')},
                              'f_trash': bool(E.cfg.get('arch_f_trash')), 'names': E.cfg.get('arch_names') or {}})
            return jresp({'ok': False, 'message': '不認得'})
        d = req.json() or {}; a = str(d.get('a') or ''); E.log.w(f'📱 手機：影片庫 {a}')
        s = lambda k: str(d.get(k) or '').strip()
        if a == 'root_add':
            p = os.path.normpath(s('path')) if s('path') else ''
            if not p or not os.path.isdir(p): return jresp({'ok': False, 'message': '找不到這個資料夾'})
            R = [str(x) for x in E.cfg.get('roots') or []]
            if any(p.lower() == r.lower() for r in R): return jresp({'ok': False, 'message': '已經在影片庫裡'})
            E.cfg.set('roots', R + [p]); ok = E.scan([p]); self._pc_reload(); self._ui(lambda: self._sync_pc_settings())
            return jresp({'ok': True, 'message': f'已加入 {p}，' + ('開始掃描（背景）' if ok else '目前正在掃描別的，掃完再按「🔄 重新掃描」')})
        if a == 'root_del':
            p = s('path'); R = [str(x) for x in E.cfg.get('roots') or []]
            if p not in R: return jresp({'ok': False, 'message': '不在影片庫裡'})
            E.cfg.set('roots', [r for r in R if r != p]); E.db.x('UPDATE files SET missing=1 WHERE root=?', (p,)); self._pc_reload(); self._ui(lambda: self._sync_pc_settings())
            return jresp({'ok': True, 'message': f'已從影片庫移除 {p}（檔案和預覽圖都沒刪）'})
        if a == 'iso_set':                                                      # V0.2.24 指定新位置
            p = os.path.normpath(s('path')) if s('path') else ''
            if not p or not os.path.isdir(p): return jresp({'ok': False, 'message': '找不到這個資料夾'})
            r = E.unpark(s('key'), p, bool(d.get('force'))) if d.get('kind') == 'drive' else E.relocate_folder(s('folder'), p, bool(d.get('force')))
            self._pc_reload(); return jresp(r)
        if a == 'iso_find':
            r_ = E.vol_check(); self._pc_reload(); return jresp({'ok': True, 'message': '；'.join(r_) if r_ else '沒有找到接回來的硬碟'})
        if a == 'rescan':
            ok = E.scan([s('path')] if s('path') else None); return jresp({'ok': ok, 'message': '開始掃描（背景）' if ok else '已經在掃描了（或還沒加硬碟）'})
        if a == 'unexclude':
            if d.get('kind') == 'dir': ok = E.remove_exclude(path=s('x'))
            else: ok = E.remove_exclude(name=s('x'))
            self._ui(lambda: self._sync_pc_settings()); return jresp({'ok': True, 'message': '已取消排除，' + ('重新掃描中（背景）' if ok else '目前正在掃描，掃完再按一次「🔄 重新掃描」')})
        if a == 'exclude':
            if d.get('kind') == 'dir': n = E.add_exclude(path=s('x'))
            else: n = E.add_exclude(name=s('x'))
            self._pc_reload(); return jresp({'ok': True, 'message': f'排除了，拿掉 {n or 0} 部'})
        if a == 'cat_add':
            ok = E.add_cat(s('name')); return jresp({'ok': bool(ok), 'message': '已新增分類' if ok else '名稱不能用或已經有了'})
        if a == 'cat_del':
            E.remove_cat(s('name')); return jresp({'ok': True, 'message': '已移除分類（資料夾和裡面的檔案不動）'})
        if a == 'front':
            n = E.folder_front(s('folder')); return jresp({'ok': True, 'message': f'{n or 0} 部排到最前面做預覽圖'})
        if a == 'archive':
            g = s('g'); fd = s('folder')
            if g not in ('S', 'A', 'E', 'F'): return jresp({'ok': False, 'message': '不認得的分級'}, 400)
            ids = E.grade_ids(g, fd)
            if not ids: return jresp({'ok': False, 'message': '沒有這個分級的影片'})
            kind = 'trash' if (g == 'F' and E.cfg.get('arch_f_trash')) else f'grade:{g}'
            n = E.archive_many(ids, kind); self._pc_reload(); return jresp({'ok': n > 0, 'message': f'已排入歸檔 {n:,} 部（後台看進度；📒 操作紀錄有每一筆，可以搬回）'})
        if a == 'trash_purge':
            w_ = str(d.get('del') or '')                                         # V0.6.35 ''＝只有待刪、with＝連 DELETE、only＝只有 DELETE
            f_ = str(d.get('f') or '')                                           # V0.6.36 ''＝不含 F、with＝連 F 級一起、only＝只刪 F 級
            r = E.trash_purge(dry=False, incl_del=(w_ == 'with'), only_del=(w_ == 'only'), incl_f=(f_ == 'with'), only_f=(f_ == 'only'), folder=s('folder')); self._pc_reload(); return jresp(r)
        if a == 'restore_db':
            r = E.request_restore(s('name'))
            if r.get('ok'): r['message'] = f'已排定：下次打開程式時用這份備份還原（{r.get("n", 0):,} 部影片；現在的資料庫會改名留著）'
            return jresp(r)
        if a == 'backup_now':
            try: E.db_backup('手機手動'); return jresp({'ok': True, 'message': '已備份'})
            except Exception as ex: return jresp({'ok': False, 'message': f'備份失敗：{ex}'})
        if a in ('usb_on', 'usb_rescue', 'usb_map'):
            U = getattr(E, 'usb', None)
            if U is None: return jresp({'ok': False, 'message': 'USB 硬碟自動救回 模組沒有載入'})
            if a == 'usb_on':
                G = E.cfg.get('usb_guard'); G = dict(G) if isinstance(G, dict) else {}; G['on'] = d.get('on') is True; E.cfg.set('usb_guard', G)
                return jresp({'ok': True, 'message': '✔ 已儲存'})
            if a == 'usb_map':
                threading.Thread(target=U.refresh_map, name='VsWebUsbMap', daemon=True).start(); return jresp({'ok': True, 'message': '重新讀線路中（幾秒）'})
            offl = sorted({os.path.splitdrive(str(r))[0].rstrip(':').upper() for r in (getattr(E, 'offline', None) or {})} - {''})
            if not offl: return jresp({'ok': False, 'message': '現在沒有離線的硬碟'})
            for L in offl: threading.Thread(target=U.rescue, args=(L,), name='VsWebUsbRescue', daemon=True).start()
            return jresp({'ok': True, 'message': f'🔌 重啟 {"、".join(offl)}: 的 USB 中（最多 2～3 分鐘；結果看 LOG）'})
        return jresp({'ok': False, 'message': '不認得的動作'})

    def api_log(self, req):
        E = self.E(); L = list(E.log.tail); q = [w.lower() for w in req.q('q').split()]; warn = req.q('warn') == '1'
        W = ('⚠', '失敗', '錯誤', 'Error', 'Traceback', '找不到', '離線', '逾時', '有問題')
        if q or warn: L = [l for l in L if all(w in l.lower() for w in q) and (not warn or any(k in l for k in W))]
        return jresp({'ok': True, 'lines': L[-400:]})

    SETTINGS = [  # (鍵, 名稱, 種類, 選項)
        ('cv_autoskip', '⏭ 轉檔卡住／太慢自動跳過（放到「失敗」，可以重試）', 'bool', None),                          # V0.6.51
        ('cv_stuck_min', '⏭ 幾分鐘沒前進算卡住', 'choice', [(5, '5 分鐘'), (10, '10 分鐘（建議）'), (20, '20 分鐘'), (30, '30 分鐘'), (60, '60 分鐘')]),
        ('th_on', '背景做預覽圖', 'bool', None), ('th_n', '預覽圖同時做幾部', 'int', (1, 8)), ('th_step', '預覽圖每幾秒一張（新做的才算）', 'choice', [(1, '每 1 秒'), (2, '每 2 秒'), (3, '每 3 秒'), (5, '每 5 秒'), (10, '每 10 秒')]),
        ('th_prio', '預覽圖優先權', 'choice', [('idle', '最低（不影響你用電腦）'), ('below', '低'), ('normal', '一般')]), ('probe_n', '讀影片資訊同時幾部', 'int', (1, 4)),
        ('scan_on_start', '打開程式時自動掃描', 'bool', None), ('hdd_n', 'HDD 同一顆一次幾部預覽圖', 'int', (1, 4)),
        ('cut_merge', '初剪：多段合併成一個檔（_ALL）', 'bool', None), ('cut_mode', '初剪方式', 'choice', [('copy', '免轉檔（最快）'), ('enc', '重新壓縮（剪點準，比較慢）')]),
        ('grid_sec', '預覽格子每幾秒一張', 'int', (2, 600)), ('cv_enc', '轉檔編碼器', 'choice', [('auto', '自動（有顯示卡用顯示卡）'), ('gpu', '顯示卡 NVENC'), ('cpu', 'CPU x265')]),
        ('cv_q', '轉檔畫質', 'choice', [(17, '接近無損（檔案大）'), (19, '接近原畫質（建議）'), (21, '高畫質'), (23, '平衡'), (26, '省空間')]), ('cv_n', '轉檔同時幾部（全部）', 'int', (1, 8)), ('cv_per_disk', '同一顆 HDD／外接硬碟同時轉幾部', 'int', (1, 8)),
        ('cv_cap', '轉檔位元率上限', 'choice', [('auto', '自動：照原檔封頂（不會變大，建議）'), ('off', '不封頂'), (4, '最多 4 Mbps'), (8, '最多 8 Mbps'), (12, '最多 12 Mbps'), (20, '最多 20 Mbps')]),
        ('cv_mode', '轉檔方式', 'choice', [('target', '🎯 自動：每部找肉眼看不出差別的最省設定'), ('fixed', '固定：照「轉檔畫質」')]),
        ('cv_target', '自動模式的目標 SSIM', 'choice', [(0.975, '0.975（更省）'), (0.98, '0.980'), (0.985, '0.985（建議）'), (0.99, '0.990（更保守）')]),
        ('cv_res', '轉檔解析度', 'choice', [(0, '原始（不縮）'), (2160, '4K'), (1440, '1440p'), (1080, '1080p'), (720, '720p'), (480, '480p')]),
        ('cv_after', '轉好之後原檔', 'choice', [('auto_del', '畫質到目標的直接刪；0.975～目標的搬到 DELETE 等你確認'), ('delete_dir', '全部先搬到該硬碟最外層的 DELETE'), ('orig', '搬到 VideoSIFT\\原檔備份'), ('recycle', '丟資源回收筒')]), ('cv_verify', '每部轉好自動驗證畫質', 'bool', None),
        ('pc_name', '🖥 這台電腦的名稱（兩台都裝時分得出來）', 'text', 20), ('pc_color', '🖥 這台電腦的代表色', 'choice', [('#4dc9ff', '藍'), ('#45d483', '綠'), ('#ffc94d', '黃'), ('#ff8a3d', '橘'), ('#ff4d6d', '紅'), ('#b48cff', '紫'), ('#ff6fb5', '粉'), ('#9aa5b3', '灰')]),
        ('arch_f_trash', 'F 級歸檔＝移到待刪', 'bool', None), ('db_backup', '每天自動備份資料庫', 'bool', None), ('daily_goal_n', '🎯 每日目標（部）', 'int', (5, 5000))]

    def api_settings(self, req):
        E = self.E()
        if req.method == 'POST':
            d = req.json(); k = d.get('k'); v = d.get('v'); spec = next((s for s in self.SETTINGS if s[0] == k), None)
            if k == 'hide_exts':                                                # 🗂 檔案總管列出的格式
                core_ = sys.modules.get(type(E).__module__); allx = set(getattr(core_, 'VIDEO_EXT', set()))
                hide = sorted({('.' + str(x).lower().lstrip('.')) for x in (v or []) if ('.' + str(x).lower().lstrip('.')) in allx})
                E.cfg.set('hide_exts', hide); E.log.w('📱 手機：檔案總管不列 ' + ('、'.join(hide) or '（全部列出）'))
                self._ui(lambda: (self._sync_pc_settings(), self._pc_reload())); return jresp({'ok': True, 'v': hide})
            if k and k.startswith('lab:'):
                lk = k[4:]
                if lk not in {x[0] for x in self.lab_list}: return jresp({'ok': False, 'message': '不認得的實驗功能'})
                L = dict(E.cfg.get('lab') or {}); L[lk] = bool(v); E.cfg.set('lab', L); E.log.w(f'📱 手機：實驗功能 {lk} → {bool(v)}')
                self._ui(lambda: self._sync_pc_settings()); return jresp({'ok': True})
            if not spec: return jresp({'ok': False, 'message': '這個設定不能從手機改'})
            _k, _n, typ, opt = spec
            if typ == 'bool': v = bool(v)
            elif typ == 'int':
                try: v = max(opt[0], min(opt[1], int(v)))
                except Exception: return jresp({'ok': False, 'message': '要填數字'})
            elif typ == 'choice' and v not in [o[0] for o in opt]: return jresp({'ok': False, 'message': '不認得的選項'})
            elif typ == 'text': v = str(v or '').strip()[:int(opt or 50)]
            E.cfg.set(k, v); E.log.w(f'📱 手機：設定 {k} → {v!r}'); self._ui(lambda: self._sync_pc_settings())
            if k in ('pc_name', 'pc_color'):
                self._icons = {}; self._ui(lambda: getattr(self.W(), 'apply_pc', lambda: None)())
            return jresp({'ok': True, 'v': v})
        DEF_ = {'cv_autoskip': True, 'cv_stuck_min': 10}                          # V0.6.51 沒設過＝預設值
        g_ = lambda k: E.cfg.get(k) if E.cfg.get(k) is not None else DEF_.get(k)
        S = [{'k': k, 'name': n, 'type': t, 'opt': o, 'v': (E.pc_name() if k == 'pc_name' else E.pc_color() if k == 'pc_color' else g_(k)) if hasattr(E, 'pc_name') else g_(k)} for k, n, t, o in self.SETTINGS]
        try: ND = {k: d for k, _n, d, _v in getattr(self.app_mod(), 'NEW_LABS', [])}        # V0.2.46 手機也看得到新功能的說明
        except Exception: ND = {}
        L = [{'k': 'lab:' + k, 'name': n, 'ver': ver, 'v': bool((E.cfg.get('lab') or {}).get(k)), 'desc': ND.get(k, ''), 'new': k in ND} for k, n, ver in self.lab_list]
        return jresp({'ok': True, 'settings': S, 'lab': L, 'lab_extra': self.lab_extra(), 'lab_packs': [[n, K] for n, K in getattr(self.app_mod(), 'LAB_PACKS', [])], 'roots': [str(r) for r in E.cfg.get('roots') or []], 'ex_dirs': E.cfg.get('ex_dirs') or [], 'ex_names': E.cfg.get('ex_names') or [],
                      'web': {'port': self.port, 'https': https_port(self.port)},
                      'exts': {'all': sorted(getattr(sys.modules.get(type(E).__module__), 'VIDEO_EXT', [])), 'hide': E.hidden_exts(), 'count': E.ext_counts()}})

    def _sync_pc_settings(self):
        W = self.W()
        try: W.apply_new_labs()
        except Exception: pass
        for nm in ('setp', 'lab'):
            pg = getattr(W, nm, None)
            for m in ('_load', 'load', 'refresh_summary'):
                f = getattr(pg, m, None)
                if callable(f):
                    try: f()
                    except Exception: pass

    LAB_EXTRA = (('disk_warn', 'disk_warn_gb', '剩不到幾 GB 就提醒', 'num', (5, 2000), 50),  ('copy_to', 'copy_dir', '上傳資料夾（電腦上的路徑，例如 K:\\上傳）', 'text', 200, ''), ('copy_to', 'copy_mbps', '複製最快幾 MB/s', 'num', (5, 500), 60),
                 ('copy_to', 'copy_on_grade', '分級時自動複製', 'choice', [['', '不自動'], ['S', '分成 S 就自動複製'], ['A', '分成 A 就自動複製']], ''),
                 ('copy_to', 'copy_after_cut', '剪好就自動複製', 'choice', [[0, '不要'], [1, '要']], 0),
                 ('copy_to', 'copy_sub', '上傳資料夾裡怎麼放', 'choice', [['', '直接放進去'], ['date', '分今天日期資料夾'], ['creator', '分作者資料夾']], ''),
                 ('copy_to', 'copy_name', '複本檔名', 'choice', [['', '跟原檔一樣'], ['date', '前面加今天日期（20261107_）'], ['grade', '前面加分級（S_）'], ['both', '日期＋分級（20261107_S_）']], ''),
                 ('goal', 'goal_nag_h', '目標還沒達成，幾點提醒一次', 'choice', [[18, '傍晚 6 點'], [20, '晚上 8 點'], [21, '晚上 9 點'], [22, '晚上 10 點'], [23, '晚上 11 點'], [24, '不要提醒']], 21),
                 ('break_remind', 'break_min', '連續分級幾分鐘提醒休息', 'choice', [[30, '30 分鐘'], [45, '45 分鐘'], [60, '1 小時'], [90, '1.5 小時'], [120, '2 小時']], 45),
                 ('copy_to', 'up_goal', '每天想上傳幾部（0＝不設，有設就顯示今天進度）', 'num', (0, 200), 0),
                 ('copy_to', 'up_goal_by', '每天目標算哪個', 'choice', [['', '複製到上傳資料夾的'], ['pub', '真的發佈的（✅）']], ''),
                 ('copy_to', 'up_auto_clean', '已發佈的複本放幾天自動丟資源回收筒', 'choice', [[0, '不要自動清'], [3, '3 天'], [7, '7 天'], [14, '14 天'], [30, '30 天']], 0),
                 ('copy_to', 'copy_tag', '複製好自動貼哪個顏色標籤', 'choice', [['', '不貼'], ['red', '🔴 紅'], ['orange', '🟠 橙'], ['yellow', '🟡 黃'], ['green', '🟢 綠'], ['blue', '🔵 藍'], ['purple', '🟣 紫']], ''),
                 ('auto_scan', 'auto_scan_min', '每隔幾分鐘找一次', 'choice', [[10, '10 分鐘'], [20, '20 分鐘'], [30, '30 分鐘'], [60, '1 小時'], [120, '2 小時'], [240, '4 小時']], 30),
                 ('proc_guard', 'proc_copy', '📤 複製到上傳資料夾也讓路', 'choice', [[0, '不用'], [1, '要（直播時先不複製）']], 0),
                 ('proc_guard', 'proc_names', '這些程式在跑時讓路（逗號隔開，例如 obs64.exe, TikLive.exe）', 'text', 300, 'obs64.exe'),
                 ('note_presets', 'note_list', '快速備註的選項（逗號隔開）', 'text', 200, '可剪,好笑,重看,要上傳'),
                 ('caption', 'copy_caption', '📤 複製到上傳資料夾時一起放文案 .txt', 'choice', [[0, '不要'], [1, '要']], 0),
                 ('caption', 'caption_tpl', '上傳文案範本（{作者} {檔名} {日期} {分級} {備註} {長度}，\\n＝換行）', 'text', 300, '{作者} {日期}\\n{備註}\\n#直播 #精華'),
                 ('caption', 'caption_tpl2', '第二組文案範本（給別的平台用，空白＝不用；一樣可以用 {#作者}）', 'text', 300, ''),
                 ('auto_theme', 'theme_from', '淺色從幾點開始', 'num', (0, 23), 7), ('auto_theme', 'theme_to', '淺色到幾點結束', 'num', (0, 23), 19))

    def lab_extra(self):
        """V0.2.67 🆕 新功能的細項設定（手機也能改）."""
        L = self.E().cfg.get('lab') or {}
        return [{'lab': lb, 'k': k, 'name': n, 'type': t, 'opt': o, 'v': L.get(k, dv)} for lb, k, n, t, o, dv in self.LAB_EXTRA]

    def api_new(self, req):
        """V0.2.36 🆕 新功能的手機版：a=report／creators（GET）、a=sched（POST：kind,on,from,to）."""
        E = self.E()
        if req.method == 'POST':
            d = req.json(); a = d.get('a')
            if a == 'sched':
                k = str(d.get('kind') or '')
                if k not in getattr(E, 'SCHED_KINDS', ()): return jresp({'ok': False, 'message': '不認得的項目'})
                L = dict(E.cfg.get('lab') or {}); S = dict(L.get('sched') or {})
                S[k] = {'on': bool(d.get('on')), 'from': int(d.get('from') or 0) % 24, 'to': int(d.get('to') or 0) % 24}; L['sched'] = S; E.cfg.set('lab', L)
                E.log.w(f'📱 手機：背景工作時段 {k} → {S[k]}'); self._ui(lambda: self._sync_pc_settings()); return jresp({'ok': True})
            if a == 'view_save':                                                 # V0.2.40 ⭐ 常用篩選
                ok = E.view_save(d.get('name'), d.get('view') or {}); return jresp({'ok': ok, 'views': E.views(), 'message': '' if ok else '要取個名字'})
            if a in ('bm_add', 'bm_del'):                                         # V0.2.41 🔖 時間書籤
                fid = int(d.get('id') or 0)
                if not fid or not E.file(fid): return jresp({'ok': False, 'message': '找不到這部'})
                L = E.bm_add(fid, d.get('t'), d.get('note') or '') if a == 'bm_add' else E.bm_del(fid, d.get('t')); return jresp({'ok': True, 'rows': L})
            if a == 'goal': g = E.day_goal_set(d.get('n')); self._ui(lambda: self._sync_pc_settings()); return jresp({'ok': True, 'goal': E.day_goal(), 'n': g})   # V0.2.44
            if a in ('empty_scan', 'empty_rm'):                                    # V0.2.45 🧹 空資料夾
                if not (E.cfg.get('lab') or {}).get('empty_dirs'): return jresp({'ok': False, 'message': '請先在 實驗工作區 打開「🧹 空資料夾清理」'})
                if a == 'empty_scan': E.empty_scan(); return jresp({'ok': True})
                ok, fail = E.empty_remove([str(x) for x in d.get('dirs') or []]); return jresp({'ok': True, 'n': ok, 'fail': fail, 'message': f'🧹 刪掉 {ok} 個' + (f'，{fail} 個保留' if fail else '')})
            if a == 'rule_auto_del': E.auto_rule_del(int(d.get('i', -1))); return jresp({'ok': True, 'auto': E.auto_rules()})
            if a == 'rule_auto_undo': n, m = E.auto_rule_undo(); return jresp({'ok': True, 'n': n, 'message': m})   # V0.3.27
            if a in ('rule_prev', 'rule_apply', 'rule_undo', 'rule_auto_add'):                       # V0.2.60 ⚡ 規則分級
                if not (E.cfg.get('lab') or {}).get('rules'): return jresp({'ok': False, 'message': '請先在 實驗工作區 打開「⚡ 規則分級」'})
                R = d.get('rule') or {}
                if a == 'rule_prev': P = E.rule_preview(R); P['ok'] = True; return jresp(P)
                if a == 'rule_auto_add': ok, m = E.auto_rule_add(R); return jresp({'ok': ok, 'message': m, 'auto': E.auto_rules()})   # V0.3.21
                n, m = E.rule_apply(R) if a == 'rule_apply' else E.rule_undo(); return jresp({'ok': True, 'n': n, 'message': m})
            if a == 'pos':                                                          # V0.2.71 ⏯ 手機續播：記住看到哪
                if not (E.cfg.get('lab') or {}).get('resume'): return jresp({'ok': False})
                try: fid = int(d.get('id') or 0); t = max(0.0, float(d.get('t') or 0))
                except Exception: return jresp({'ok': False})
                f = E.file(fid)
                if not f: return jresp({'ok': False})
                dur = float(f.get('dur') or 0); t = 0.0 if (dur and t > dur - 15) or t < 5 else round(t, 1)   # 快看完／剛開始＝下次從頭
                E.set_flags([fid], _stamp=False, last_pos=t); return jresp({'ok': True, 't': t})
            if a == 'lab_set':                                                     # V0.2.67 新功能細項設定
                k = str(d.get('k') or ''); X = {x[1]: x for x in self.LAB_EXTRA}
                if k not in X: return jresp({'ok': False, 'message': '不認得的設定'})
                _lb, _k, _n, t, o, dv = X[k]; v = d.get('v')
                try:
                    if t == 'num': v = max(o[0], min(o[1], int(float(v))))
                    elif t == 'choice': v = type(o[0][0])(v); assert v in [c[0] for c in o]
                    else: v = str(v or '').strip()[:o]
                except Exception: return jresp({'ok': False, 'message': '數值不對'})
                L = dict(E.cfg.get('lab') or {}); L[k] = v
                if k == 'copy_dir': L['copy_dir_vol'] = E.path_vol(v)                    # V0.3.03 記住是哪顆硬碟
                E.cfg.set('lab', L)
                for attr in ('_dw_c', '_goal_c'): setattr(E, attr, None)
                E.log.w(f'📱 手機：新功能設定 {k} → {v}'); self._ui(lambda: self._sync_pc_settings()); return jresp({'ok': True, 'v': v})
            if a == 'pack_on':                                                     # V0.2.93 一次打開一組
                P = dict((n, K) for n, K in getattr(self.app_mod(), 'LAB_PACKS', [])); K = P.get(str(d.get('name') or ''))
                if not K: return jresp({'ok': False, 'message': '不認得'})
                L = dict(E.cfg.get('lab') or {}); n = sum(1 for k in K if not L.get(k)); L.update({k: True for k in K}); E.cfg.set('lab', L)
                E.log.w(f'📱 手機：一次打開 {d.get("name")}（{n} 個）'); self._ui(lambda: self._sync_pc_settings()); return jresp({'ok': True, 'n': n, 'message': f'打開了 {n} 個'})
            if a == 'folder_move':
                if not (E.cfg.get('lab') or {}).get('folder_move'): return jresp({'ok': False, 'message': '請先在 實驗工作區 打開「🚚 資料夾搬到別顆硬碟」'})
                r = E.move_start_folder(str(d.get('folder') or ''), str(d.get('to') or '').strip(), 60); E.log.w(f'📱 手機：搬資料夾 {d.get("folder")} → {d.get("to")}'); return jresp({'ok': bool(r.get('ok')), 'message': r.get('message', '')})
            if a == 'share_export': r = E.share_export(); return jresp({'ok': True, 'message': '🔄 存到：' + ('、'.join(f'{x}:' for x in r) or '（沒有有紀錄包的硬碟）')})   # V0.3.29
            if a == 'share_import':
                ok, m = E.share_import(str(d.get('d') or '')[:1].upper())
                if ok: self._ui(lambda: self._sync_pc_settings())
                return jresp({'ok': ok, 'message': m})
            if a == 'snap': ok, m = E.snap_at(int(d.get('id') or 0), float(d.get('t') or 0)); return jresp({'ok': ok, 'message': m})   # V0.3.34
            if a == 'cut_static':                                                    # V0.3.47
                if not (E.cfg.get('lab') or {}).get('scenes'): return jresp({'ok': False, 'message': '請先打開「🎬 換場景標記」'})
                ids_ = [int(x) for x in d.get('ids') or []][:500]
                threading.Thread(target=lambda: E.cut_skip_static(ids_), daemon=True, name='cut_static').start()   # V0.3.48 背景算（多部要一段時間），結果記 LOG
                return jresp({'ok': True, 'message': f'✂ {len(ids_)} 部在背景找靜止段落、排進剪輯（後台看進度，結果在 LOG）'})
            if a == 'shist_push': E.search_push(d.get('q')); return jresp({'ok': True, 'rows': E.search_hist()})   # V0.2.65
            if a == 'shist_clear': E.cfg.set('search_hist', []); return jresp({'ok': True, 'rows': []})
            if a == 'copy_ctl': m = E.copy_ctl(str(d.get('do') or '')); return jresp({'ok': bool(m), 'message': m, 'copy': E.copy_view()})   # V0.2.76
            if a == 'copy_cuts': n, m = E.copy_cuts(d.get('ids') or []); return jresp({'ok': bool(n), 'n': n, 'message': m})   # V0.2.59
            if a == 'up_old_rm': n, m = E.up_old_rm(d.get('rels') or [], int(d.get('days') or 14)); return jresp({'ok': bool(n), 'n': n, 'message': m})   # V0.3.66
            if a == 'sprint': return jresp({'ok': True, 'message': E.sprint_start(d.get('min') or 15)} if d.get('on', 1) else {'ok': True, 'result': E.sprint_stop()})   # V0.3.72
            if a == 'up_undo': n, m = E.up_undo(int(d.get('n') or 1)); return jresp({'ok': bool(n), 'n': n, 'message': m})   # V0.4.07
            if a == 'bm_clip': r = E.bm_clip(int(d.get('id') or 0), float(d.get('t') or 0), float(d.get('before') or 5), float(d.get('after') or 10)); return jresp(r if isinstance(r, dict) else {'ok': False})   # V0.4.17
            if a == 'up_done_days': E.cfg.set('up_done_days', 7 if int(d.get('days') or 1) == 7 else 1); return jresp({'ok': True})   # V0.4.38
            if a == 'up_order': E.cfg.set('up_order', 'mix' if d.get('mix') else ''); return jresp({'ok': True})   # V0.4.26
            if a == 'pub_names': n, m = E.pub_by_names(d.get('text') or ''); return jresp({'ok': bool(n), 'n': n, 'message': m})   # V0.4.27
            if a == 'pub_mark': n, m = E.pub_mark(d.get('ids') or [], bool(d.get('on', 1))); return jresp({'ok': bool(n), 'n': n, 'message': m})   # V0.4.21
            if a == 'up_mark': n, m = E.up_mark(d.get('ids') or [], bool(d.get('on', 1))); return jresp({'ok': bool(n), 'n': n, 'message': m})   # V0.3.58
            if a == 'copy_to': n, m = E.copy_enqueue([int(x) for x in d.get('ids') or [] if str(x).isdigit()]); return jresp({'ok': bool(n), 'n': n, 'message': m})   # V0.2.49
            if a == 'view_del': E.view_del(str(d.get('name') or '')); return jresp({'ok': True, 'views': E.views()})
            return jresp({'ok': False, 'message': '不認得的動作'})
        a = req.q('a')
        if a == 'report': r = E.review_report(); r['ok'] = True; return jresp(r)
        if a == 'creators': return jresp({'ok': True, 'rows': E.creator_stats()[:300]})
        if a == 'views': return jresp({'ok': True, 'views': E.views()})
        if a == 'random': return jresp({'ok': True, 'ids': E.random_ungraded(req.q('folder') or '')})   # V0.3.84 🎲
        if a == 'whatsnew':                                                     # V0.3.97 🆕 since＝上次看到的版本
            vt = lambda v: tuple(int(x) for x in re.findall(r'\d+', str(v))[:3])
            try: C = json.loads((Path(self.app_mod().HERE) / 'CHANGELOG.json').read_text(encoding='utf-8'))
            except Exception: C = []
            cur = str(getattr(self.app_mod(), 'APP_VERSION', '')); sn = str(req.q('since') or '')
            R = [x for x in C if vt(sn) < vt(x.get('version')) <= vt(cur)][:80] if sn else []
            return jresp({'ok': True, 'cur': cur, 'rows': R})
        if a == 'drive_busy': return jresp({'ok': True, 'rows': E.drive_busy()})   # V0.4.49 🔌
        if a == 'bm_all': return jresp({'ok': True, 'rows': E.bm_all()})   # V0.4.16 🔖
        if a == 'day_text': return jresp({'ok': True, 'text': E.day_text()})   # V0.4.34 🧾
        if a == 'heat': return jresp({'ok': True, 'rows': E.grade_heat(84)})   # V0.4.09
        if a == 'week': return jresp(dict(E.week_review(), ok=True))   # V0.3.80
        if a == 'sprint_hist': return jresp({'ok': True, 'rows': (E.cfg.get('sprint_hist') or [])[::-1], 'cur': E.sprint_view()})   # V0.3.72
        if a == 'up_board': return jresp(dict(E.up_board(), ok=True))   # V0.3.69
        if a == 'up_old':                                                       # V0.3.66 🧹 上傳資料夾舊檔
            try: dy = max(0, min(365, int(req.q('days') or 14)))
            except Exception: dy = 14
            return jresp(dict(E.up_old(dy), days=dy))
        if a == 'recent': return jresp({'ok': True, 'rows': E.recent_list(), 'last': E.last_file(), 'up_left': (E.up_left() if hasattr(E, 'up_left') else 0), 'unpub': (E.unpub_n() if hasattr(E, 'unpub_n') else 0)})
        if a == 'caption_today':                                                 # V0.4.06 📋 今天傳好的文案一次拿
            lt = time.localtime(); t0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
            R = E.db.q('SELECT id,name FROM files WHERE up_t>=? ORDER BY up_t', (t0,))
            return jresp({'ok': True, 'n': len(R), 'text': '\n\n'.join(f"【{r['name']}】\n" + E.caption_for(int(r['id'])) for r in R)})
        if a == 'caption': return jresp({'ok': True, 'text': E.caption_for(int(req.q('id', '0') or 0), int(req.q('n', '1') or 1))})   # V0.3.43
        if a == 'share_list': return jresp({'ok': True, 'rows': E.share_list()})
        if a == 'rules_auto': return jresp({'ok': True, 'auto': E.auto_rules()})
        if a == 'flow': return jresp({'ok': True, 'rows': [list(x) for x in getattr(self.app_mod(), 'NEW_FLOW', [])]})   # V0.3.18
        if a == 'scenes':                                                         # V0.3.09 🎬／V0.3.11 😴
            on = (E.cfg.get('lab') or {}).get('scenes'); fid = int(req.q('id', '0') or 0)
            return jresp({'ok': True, 'rows': E.scene_cuts(fid) if on else [], 'static': E.static_runs(fid) if on else [], 'hot': E.highlights(fid) if on else []})
        if a == 'find':                                                          # V0.3.07 ⌘ 手機快速找
            if not (E.cfg.get('lab') or {}).get('cmdk'): return jresp({'ok': False, 'message': '請先在 實驗工作區 打開「⌘ 指令面板」'})
            r = E.quick_find(req.q('q'), 30); r['ok'] = True; return jresp(r)
        if a == 'drives':                                                        # V0.2.99 🚚 搬資料夾：可以搬去哪幾顆
            src = str(req.q('folder') or '')[:1].upper(); out = []
            try: L = sorted(set(E.vol_letters().values()) - {src})
            except Exception: L = []
            for X in L:
                try: out.append({'d': X, 'label': E.vol_label(X + ':\\') or '', 'free': shutil.disk_usage(X + ':\\').free})
                except Exception: out.append({'d': X, 'label': '', 'free': 0})
            return jresp({'ok': True, 'rows': out})
        if a == 'hist': return jresp({'ok': True, 'rows': E.file_history(int(req.q('id', '0') or 0))})
        if a == 'fprog': return jresp({'ok': True, 'rows': E.folder_progress()[:500]})
        if a == 'copyq': return jresp({'ok': True, 'rows': E.copy_list(), 'copy': E.copy_view()})
        if a == 'check': return jresp({'ok': True, 'rows': [{'ok': ok, 't': t} for ok, t in E.new_selfcheck()]})
        if a == 'shist': return jresp({'ok': True, 'rows': E.search_hist()})
        if a == 'space': return jresp({'ok': True, 'rows': E.space_map()})
        if a == 'months': return jresp({'ok': True, 'rows': E.month_stats()})
        if a == 'pcs': r = E.pack_overview(); r['ok'] = True; return jresp(r)
        if a == 'empty': r = E.empty_view(); r['ok'] = True; return jresp(r)
        if a == 'bm': return jresp({'ok': True, 'rows': E.bm_list(int(req.q('id', '0') or 0))})
        if a == 'up_csv':                                                        # V0.3.93 🧾 上傳紀錄
            from urllib.parse import quote as _qt
            try: dy = max(1, min(3650, int(req.q('days') or 30)))
            except Exception: dy = 30
            return Resp(200, E.up_csv(dy).encode('utf-8'), 'text/csv; charset=utf-8', {'Content-Disposition': "attachment; filename*=UTF-8''" + _qt('VideoSift_上傳紀錄_' + time.strftime('%Y%m%d') + '.csv')})
        if a == 'csv':                                                           # V0.2.38 📤 目前清單匯出 CSV
            if not (E.cfg.get('lab') or {}).get('list_csv'): return jresp({'ok': False, 'message': '請先在 實驗工作區 打開「📤 清單匯出 CSV」'})
            R = E.list_files(req.q('folder'), req.q('sub', '1') != '0', req.q('sort', 'name'), req.q('flt', 'all'), req.q('q'), req.q('dur', '') if (E.cfg.get('lab') or {}).get('dur_chips') else '', req.q('res', '') if (E.cfg.get('lab') or {}).get('res_chips') else '')
            fn = 'VideoSift_清單_' + time.strftime('%Y%m%d_%H%M') + '.csv'
            from urllib.parse import quote as _qt
            return Resp(200, E.list_csv(R).encode('utf-8'), 'text/csv; charset=utf-8', {'Content-Disposition': "attachment; filename*=UTF-8''" + _qt(fn)})
        if a == 'sched':
            NM = dict({k: n for k, _i, n in E.BG_KINDS}, copy='📤 複製到上傳資料夾', move='🚚 搬硬碟')
            return jresp({'ok': True, 'on': bool((E.cfg.get('lab') or {}).get('bg_sched')), 'rows': [dict({'kind': k, 'name': NM.get(k, k), 'on': False, 'from': 1, 'to': 9}, **(((E.cfg.get('lab') or {}).get('sched') or {}).get(k) or {}))
                                                                                                for k in getattr(E, 'SCHED_KINDS', ())]})
        return jresp({'ok': False, 'message': '不認得的動作'})

    def api_lab(self, req):
        """🧪 工具：找重複、找畫面相似（背景跑，手機輪詢進度）、跟這部相似、整理成果統計、隨機抽一部、健康檢查."""
        E = self.E(); a = req.q('a') or req.json().get('a') or ''
        if a == 'dupes': return jresp({'ok': True, 'groups': [[self._slim(x) for x in g] for g in E.find_dupes(200)]})
        if a == 'like': return jresp({'ok': True, 'groups': [[self._slim(x) for x in E.similar_to(int(req.q('id', '0') or 0), int(req.q('thr', '12') or 12))]]})
        if a == 'random':
            fid = E.random_unseen(req.q('folder')); return jresp({'ok': bool(fid), 'id': fid, 'message': '' if fid else '沒有預覽圖好了又沒看過的'})
        if a == 'stats':
            S = E.stats(); return jresp({'ok': True, 'stats': {k: S.get(k) for k in ('lib', 'arch', 'ops', 'freed_delete', 'freed_conv', 'cuts', 'graded_days', 'res', 'ext')}})
        if a == 'health':
            H = E.health(); return jresp({'ok': True, 'health': {k: {'name': v['name'], 'rows': [self._slim(x) for x in v['rows'][:100]], 'n': len(v['rows'])} for k, v in H.items()}})
        if a == 'similar':
            j = self.jobs.get('similar')
            if req.method == 'POST':
                d = req.json()
                if d.get('stop'): E.vfp_cancel = True; return jresp({'ok': True})
                if j and j.get('run'): return jresp({'ok': True, 'job': self._jv(j)})
                j = {'run': True, 'msg': '準備中…', 'groups': None, 't0': time.time()}; self.jobs['similar'] = j; thr = int(d.get('thr') or 10)
                def work():
                    try:
                        G = E.find_similar(thr, lambda x, y: j.update(msg=f'算畫面指紋 {x:,}／{y:,}'), cmp_progress=lambda x, y: j.update(msg=f'比對 {x:,}／{y:,}'))
                        j.update(groups=[[self._slim(x) for x in g] for g in G], msg=f'找到 {len(G)} 組' + ('（中途停了）' if getattr(E, 'vfp_cancel', False) else ''))
                    except Exception as ex: j.update(msg=f'出錯了：{ex}')
                    finally: j['run'] = False; E.vfp_cancel = False
                threading.Thread(target=work, name='VsWebSimilar', daemon=True).start()
            return jresp({'ok': True, 'job': self._jv(j) if j else None})
        return jresp({'ok': False, 'message': '不認得的工具'})

    @staticmethod
    def _jv(j): return {'run': j.get('run'), 'msg': j.get('msg'), 'groups': j.get('groups')}

    @staticmethod
    def _slim(x):
        return {k: x.get(k) for k in ('id', 'name', 'folder', 'size', 'dur', 'w', 'h', 'grade', 'dist', 'big', 'me', 'th_err', 'probe_err') if k in x}

    def api_update(self, req):
        """上傳更新包（SC_V….zip）→ 放進 UPDATE → 在電腦上熱更新（程式不用關）."""
        E = self.E(); W = self.W(); M = self.app_mod()
        if req.method != 'POST' or not req.body: return jresp({'ok': False, 'message': '沒有收到檔案'})
        nm = re.sub(r'[^\w.\-]', '_', req.q('name') or 'VS_update.zip')
        if not nm.lower().endswith('.zip'): nm += '.zip'
        d = E.root / 'UPDATE'; d.mkdir(exist_ok=True); p = d / nm; p.write_bytes(req.body)
        try: pkg = M.load_pkg(p)
        except Exception as ex:
            try: p.unlink()
            except Exception: pass
            return jresp({'ok': False, 'message': f'這個更新包不能用：{ex}'})
        E.log.w(f'📱 手機：上傳更新包 {nm}（V{pkg["version"]}）')
        if not pkg.get('hot_ok'): return jresp({'ok': True, 'message': f'已放進 UPDATE（V{pkg["version"]}），這版要重開程式才會套用'})
        def go():
            try:
                W.upd.pkg = pkg; M.hot_update(W, pkg)
            except Exception: E.log.err('手機熱更新')
        self._ui(lambda: self.ui_later(go))
        return jresp({'ok': True, 'message': f'V{pkg["version"]} 熱更新中…（大約 5～10 秒，之後手機會自動重新整理）', 'ver': pkg['version']})

    def api_cloud_upd(self, req):
        """V0.6.01 ☁ 雲端更新：GET 上次看的結果；POST {a: check|go}."""
        E = self.E(); W = self.W(); M = self.app_mod()
        import vs_cloudupd as CU
        if req.method != 'POST':
            r = getattr(E, 'cloud_upd', None) or {}
            return jresp({'ok': True, 'cur': M.APP_VERSION, 'launcher': CU.launcher_ver(), 'auto': E.cfg.get('cloud_auto') is True, 'r': {k: r.get(k) for k in ('ok', 'newer', 'message', 't', 'info')} if r else None})
        if self.is_ro(req): return jresp({'ok': False, 'message': '👀 這支手機是唯讀登入：只能看，不能改'})
        a = (req.json() or {}).get('a')
        if a == 'auto':                                                         # V0.6.29 有新版自動熱更新
            on = bool((req.json() or {}).get('on')); E.cfg.set('cloud_auto', on)
            try: self._ui(lambda: W.upd.cb_cauto.setChecked(on))
            except Exception: pass
            return jresp({'ok': True, 'message': '☁ 有新版會自動熱更新（你 5 分鐘沒碰電腦時）' if on else '☁ 自動熱更新關了（要自己按更新）'})
        if a == 'check':
            r = CU.check(M.APP_VERSION); E.cloud_upd = r
            try: W._cloud = r; self._ui(lambda: W.upd.cloud_show(r))
            except Exception: pass
            return jresp({'ok': r.get('ok'), 'newer': r.get('newer'), 'message': r.get('message'), 'info': r.get('info')})
        if a == 'go':
            r = getattr(W, '_cloud', None) or getattr(E, 'cloud_upd', None) or {}
            if not r.get('newer'): return jresp({'ok': False, 'message': '沒有比較新的版本（先按「檢查」）'})
            E.log.w(f'📱 手機：按了雲端更新 V{r["info"]["version"]}')
            self._ui(lambda: self.ui_later(W._cloud_go))
            return jresp({'ok': True, 'message': f'電腦開始下載 V{r["info"]["version"]}，下載好自動熱更新（程式不用關、電腦上不用按）；大約 30 秒後重新整理就是新版'})
        return jresp({'ok': False, 'message': '不認得的動作'})

    def ui_later(self, fn):
        try: self.app_mod().QTimer.singleShot(400, fn)                         # 先把回應送出去再換
        except Exception: fn()

    def api_changelog(self, req):
        try: C = json.loads((Path(self.app_mod().HERE) / 'CHANGELOG.json').read_text(encoding='utf-8'))[:15]
        except Exception: C = []
        return jresp({'ok': True, 'log': C})

    def api_logout(self, req):
        E = self.E(); t = req.headers.get('x-vs-token') or req.cookie('vs_t'); L = [x for x in (E.cfg.get('web_tokens') or []) if not same(x, t)]
        E.cfg.set('web_tokens', L); return jresp({'ok': True}, headers={'Set-Cookie': 'vs_t=; Path=/; Max-Age=0'})

    # ================================================================ V0.1.51 TikLive 風格的浮動視窗＋👤 人物
    def api_perf(self, req):
        """📊 效能：CPU、記憶體、顯示卡（使用率、編碼、解碼、顯示記憶體、溫度）、最近 3 分鐘的線、每顆硬碟（忙碌、讀寫、剩多少）."""
        E = self.E(); P = getattr(E, 'perf', None); g = dict(getattr(P, 'gpu', None) or {}) if P else {}
        H = {k: [None if x is None else round(float(x), 1) for x in list(v)[-90:]] for k, v in (getattr(P, 'H', {}) or {}).items()} if P else {}
        disks = []
        for d in E.disks_view():
            free = tot = None
            for r_ in d.get('roots') or []:
                try: du = shutil.disk_usage(r_); free, tot = du.free, du.total; break
                except Exception: pass
            disks.append({'label': d.get('label'), 'media': d.get('media'), 'busy': d.get('busy'), 'rd': d.get('rd'), 'wr': d.get('wr'), 'th': d.get('th'), 'cv': d.get('cv'), 'free': free, 'total': tot, 'note': d.get('note'), 'eta': d.get('eta')})
        return jresp({'ok': True, 'time': time.strftime('%H:%M:%S'), 'cpu': round(getattr(P, 'cpu', 0) or 0, 1) if P else None, 'ram': round(getattr(P, 'ram', 0) or 0, 1) if P else None,
                      'ram_used': getattr(P, 'ram_used', 0) if P else 0, 'ram_total': getattr(P, 'ram_total', 0) if P else 0, 'gpu': g, 'hist': H, 'disks': disks,
                      'jobs': {'th': len(E.th_active), 'cv': len(E.cv_active), 'cut': len(E.cut_q) + (1 if E.cut_cur else 0)}})

    def api_grades(self, req):
        """🗂 分類：S／A／E／F／未分級 各幾部、幾 GB、占比；已歸檔的各資料夾."""
        E = self.E(); es, ea = E.ext_sql()
        R = {g or '': (n, b or 0) for g, n, b in E.db.q(f"SELECT grade, COUNT(*), SUM(size) FROM files WHERE missing=0 AND length(arch)=0 {'AND ' + es if es else ''} GROUP BY grade", ea)}
        A = [(a, n, b or 0) for a, n, b in E.db.q("SELECT arch, COUNT(*), SUM(size) FROM files WHERE missing=0 AND length(arch)>0 GROUP BY arch ORDER BY 3 DESC")]
        tot = sum(b for _n, b in R.values()) or 0
        return jresp({'ok': True, 'tot': tot, 'n': sum(n for n, _b in R.values()), 'g': {k: {'n': R.get(k, (0, 0))[0], 'b': R.get(k, (0, 0))[1]} for k in ('S', 'A', 'E', 'F', '')},
                      'arch': [{'name': a, 'n': n, 'b': b} for a, n, b in A]})

    def _F(self):
        f = getattr(self.E(), 'faces', None)
        if f is None: raise RuntimeError('人物功能沒有載入')
        return f

    def _with_sheet(self, faces):
        """臉的位置加上那部影片的預覽圖排法（手機用 CSS 從大張切出臉）."""
        E = self.E(); ids = list({f['file_id'] for f in faces if f}); R = {}
        for i in range(0, len(ids), 500):
            for r in E.db.q(f"SELECT id, th_cols, th_rows, w, h FROM files WHERE id IN ({','.join(map(str, ids[i:i + 500])) or '-1'})"): R[r['id']] = dict(r)
        for f in faces:
            if not f: continue
            r = R.get(f['file_id']) or {}; per = int(r.get('th_cols') or 10) * int(r.get('th_rows') or 10)
            f.update(cols=int(r.get('th_cols') or 10), rows=int(r.get('th_rows') or 10), si=int(f['k']) // per, q=int(f['k']) % per, vw=r.get('w') or 16, vh=r.get('h') or 9)
        return faces

    def api_faces(self, req):
        """👤 狀態＋控制：開始／停止／重新分群／檢查環境／設定."""
        F = self._F()
        if req.method == 'POST':
            d = req.json(); a = d.get('a'); self.E().log.w(f'📱 手機：人物 {a}')
            if a == 'start': return jresp(F.start('手機'))
            if a == 'stop': return jresp(F.stop('手機'))
            if a == 'recluster': return jresp(F.start('手機', cluster_only=True))
            if a == 'check': e = F.check_env(); return jresp({'ok': bool(e.get('ok')), 'env': {k: e.get(k) for k in ('py', 'ort', 'providers', 'insightface', 'models', 'ok', 'has_models', 'gpu')}})
            if a == 'cfg':
                ok = {k: d[k] for k in ('ratio', 'src', 'thr', 'min_faces', 'gpu', 'night', 'night_from', 'night_to', 'auto_min') if k in d}
                if 'ratio' in ok: ok['ratio'] = max(0.01, min(1.0, float(ok['ratio'])))
                F.set_cfg(**ok); return jresp({'ok': True})
            return jresp({'ok': False, 'message': '不認得的動作'})
        st = F.status(); st.pop('env', None); return jresp({'ok': True, 'st': st})

    def api_people(self, req):
        F = self._F(); P = F.persons(show_hidden=req.q('hidden') == '1', q=req.q('q'))
        if req.q('named') == '1': P = [p for p in P if p['name']]
        self._with_sheet([p['face'] for p in P if p.get('face')])
        return jresp({'ok': True, 'people': P[:1500], 'total': len(P)})

    def api_person(self, req):
        F = self._F()
        if req.method == 'POST':
            d = req.json(); a = d.get('a'); pid = int(d.get('id') or 0); self.E().log.w(f'📱 手機：人物 #{pid} {a}')
            if a == 'rename': r = F.rename(pid, d.get('name', ''))
            elif a == 'merge': r = F.merge([int(x) for x in d.get('ids') or []], pid)
            elif a == 'hide': r = F.set_flag(pid, hidden=bool(d.get('v')))
            elif a == 'auto_cat': r = F.set_flag(pid, auto_cat=bool(d.get('v')))
            elif a == 'not_me': r = F.remove_faces([int(x) for x in d.get('faces') or []])
            elif a == 'rm_file': r = F.remove_file(pid, int(d.get('file_id') or 0))
            elif a == 'apply_cat': r = F.apply_cat(pid)
            else: return jresp({'ok': False, 'message': '不認得的動作'})
            self._ui(lambda: (getattr(self.W(), 'people', None) and self.W().people.load(), self.W().browse.refresh_people_filter()))
            return jresp(r)
        p = F.person(int(req.q('id', '0') or 0))
        if not p: return jresp({'ok': False, 'message': '找不到這個人（可能合併掉了）'}, 404)
        self._with_sheet([f.get('face') for f in p['files']] + list(p.get('samples') or []))
        return jresp({'ok': True, 'person': p})


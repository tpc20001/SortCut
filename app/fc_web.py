"""📱 手機網頁：用手機（或別台電腦的瀏覽器）透過 Tailscale 遙控這個程式。

和你的其他程式錯開、不會互相蓋掉（重要規則，換程式也照這樣）：
  - 本機只聽 127.0.0.1:<本機埠>（brand.json 的 web_port，每個程式要不一樣）。
  - Tailscale 用「自己的」HTTPS 埠＝本機埠 + 1000：tailscale serve --bg --https=<本機埠+1000> http://127.0.0.1:<本機埠>
  - 只設定／關掉自己這個埠：從來不碰 443（TikLive 用的根目錄）、從來不跑 tailscale serve reset（會清掉別的程式的設定）。
  - 手機上每個程式是不同的埠＋不同的 manifest id（brand.json 的 phone_id）→ 可以各自安裝成 App、同時開。
伺服器是自己寫的小型 HTTP（只用 socket／threading，啟動器 EXE 裡一定有），每個連線一條背景執行緒；
碰到畫面的動作一律交給畫面執行緒（ui）。新功能的 API：寫一個 api_<名字>(self, req) 方法就好（登入檢查已經做好）。
"""
import os, re, json, time, socket, platform, threading, hashlib, struct, zlib, subprocess, shutil, traceback, urllib.parse
from pathlib import Path
import fc_report as report  # noqa: E402

MAX_BODY = 64 * 1024 * 1024
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
HERE = Path(__file__).resolve().parent


def https_port(local_port):
    """規則：Tailscale HTTPS 埠＝本機埠 + 1000."""
    return int(local_port) + 1000


def pin_hash(pin, salt): return hashlib.sha256((salt + '|' + str(pin)).encode('utf-8')).hexdigest()


def pin_ok_format(pin): return bool(re.fullmatch(r'[^\s]{4,20}', str(pin or '')))


def rand_hex(n=16): return os.urandom(n).hex()


def same(a, b):
    a = str(a).encode(); b = str(b).encode()
    if len(a) != len(b): return False
    r = 0
    for x, y in zip(a, b): r |= x ^ y
    return r == 0


def make_icon_png(size, accent=(229, 30, 99)):
    """沒有圖檔時自己畫一個 PNG 圖示（不用 PIL）：深色圓角方塊＋彩色圓點。Android 安裝 App 需要 192／512 的 PNG."""
    S = int(size); rad = S * 0.22; rows = []
    for y in range(S):
        row = bytearray(b'\x00')
        for x in range(S):
            dx = max(rad - x, 0, x - (S - 1 - rad)); dy = max(rad - y, 0, y - (S - 1 - rad))
            if dx * dx + dy * dy > rad * rad: row += b'\x0b\x0f\x14\xff'; continue
            cx, cy = x - S / 2, y - S / 2; d2 = cx * cx + cy * cy
            if d2 <= (S * 0.2) ** 2: row += bytes((*accent, 255))
            elif d2 <= (S * 0.3) ** 2 and d2 >= (S * 0.26) ** 2: row += b'\xe8\xec\xf2\xff'
            else: t = (x + y) / (2 * S); row += bytes((int(16 + 20 * t), int(22 + 30 * t), int(34 + 50 * t), 255))
        rows.append(bytes(row))
    raw = zlib.compress(b''.join(rows), 9)
    def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', S, S, 8, 6, 0, 0, 0)) + chunk(b'IDAT', raw) + chunk(b'IEND', b'')


# ------------------------------------------------------------------ Tailscale（只動自己的埠）
def tailscale_exe():
    exe = shutil.which('tailscale') or ''
    for c in (os.path.expandvars(r'%ProgramFiles%\Tailscale\tailscale.exe'), r'C:\Program Files\Tailscale\tailscale.exe', r'C:\Program Files (x86)\Tailscale\tailscale.exe'):
        if not exe and c and os.path.isfile(c): exe = c
    return exe


def tailscale_run(args, timeout=10):
    exe = tailscale_exe()
    if not exe: return -1, '找不到 tailscale（這台電腦還沒裝 Tailscale？）'
    if args and args[0] == 'serve' and 'reset' in args: return -1, '不准 tailscale serve reset（會清掉別的程式的設定）'
    try:
        p = subprocess.run([exe] + list(args), capture_output=True, timeout=timeout, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
        return p.returncode, (p.stdout + p.stderr).decode('utf-8', 'replace')
    except subprocess.TimeoutExpired: return -9, '逾時（Tailscale 沒回應；如果要登入，請看電腦右下角的 Tailscale）'
    except Exception as ex: return -1, f'{type(ex).__name__}: {ex}'


def tailscale_info(local_port):
    """{'installed', 'dns'（電腦名稱.xxx.ts.net）, 'ip', 'serving'（自己的 HTTPS 埠有沒有設好）, 'url', 'others'（別的程式用的埠，只顯示）}."""
    out = {'installed': bool(tailscale_exe()), 'dns': '', 'ip': '', 'serving': False, 'url': '', 'others': []}
    if not out['installed']: return out
    rc, s = tailscale_run(['status', '--json'], 6)
    if rc == 0 and '{' in s:
        try:
            j = json.loads(s[s.index('{'):]); me = j.get('Self') or {}
            out['dns'] = str(me.get('DNSName') or '').rstrip('.'); ips = me.get('TailscaleIPs') or []; out['ip'] = next((i for i in ips if '.' in i), ips[0] if ips else '')
        except Exception: pass
    hp = https_port(local_port)
    rc, s = tailscale_run(['serve', 'status', '--json'], 6)
    if rc == 0 and '{' in s:
        try:
            j = json.loads(s[s.index('{'):]); tcp = j.get('TCP') or {}
            out['serving'] = str(hp) in {str(k) for k in tcp.keys()}; out['others'] = sorted(str(k) for k in tcp.keys() if str(k) != str(hp))
        except Exception: pass
    if out['dns']: out['url'] = f'https://{out["dns"]}:{hp}/'
    return out


def tailscale_serve_on(local_port):
    return tailscale_run(['serve', '--bg', f'--https={https_port(local_port)}', f'http://127.0.0.1:{int(local_port)}'], 40)


def tailscale_serve_off(local_port):
    return tailscale_run(['serve', f'--https={https_port(local_port)}', 'off'], 20)


# ------------------------------------------------------------------ HTTP
class Req:
    def __init__(self, method, path, query, headers, body, peer):
        self.method = method; self.path = path; self.query = query; self.headers = headers; self.body = body; self.peer = peer

    def q(self, k, d=''):
        v = self.query.get(k); return v[0] if v else d

    def json(self):
        try: return json.loads(self.body.decode('utf-8') or '{}')
        except Exception: return {}

    def cookie(self, k):
        for part in (self.headers.get('cookie') or '').split(';'):
            a, _, b = part.strip().partition('=')
            if a == k: return urllib.parse.unquote(b)
        return ''

    def client(self):
        if self.peer in ('127.0.0.1', '::1'): return (self.headers.get('x-forwarded-for') or self.peer or '').split(',')[0].strip()
        return self.peer or ''


class Resp:
    def __init__(self, code=200, body=b'', ctype='application/json; charset=utf-8', headers=None):
        self.code = code; self.body = body; self.ctype = ctype; self.headers = headers or {}; self.file = None


class FileResp(Resp):
    """大檔案（影片）一段一段送，支援 Range（手機播放器拉進度條）——不會整個讀進記憶體（V0.1.42）."""
    def __init__(self, path, ctype, rng=None):
        size = os.path.getsize(path); a, b = 0, size - 1; code = 200
        m = re.match(r'bytes=(\d*)-(\d*)$', (rng or '').strip())
        if m and size:
            if m.group(1): a = int(m.group(1)); b = int(m.group(2)) if m.group(2) else size - 1
            elif m.group(2): a = max(0, size - int(m.group(2)))
            b = min(b, size - 1); code = 206
        if a > b and size: a, b = 0, size - 1; code = 416
        h = {'Accept-Ranges': 'bytes', 'Cache-Control': 'private, max-age=600'}
        if code == 206: h['Content-Range'] = f'bytes {a}-{b}/{size}'
        if code == 416: h['Content-Range'] = f'bytes */{size}'
        super().__init__(code, b'', ctype, h); self.file = path; self.a = a; self.n = 0 if code == 416 else b - a + 1


def pets_MODEL():
    try:
        import fc_pets as pets; return pets.MODEL
    except Exception: return 'mobilenetv2-7.onnx'


def jresp(obj, code=200, headers=None):
    return Resp(code, json.dumps(obj, ensure_ascii=False, default=str).encode('utf-8', 'replace'), headers=headers)      # 亂碼檔名不會讓整個回應失敗


REASON = {200: 'OK', 400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found', 413: 'Payload Too Large', 429: 'Too Many Requests', 500: 'Internal Server Error'}


class WebServer:
    """get_eng()／get_win()：目前的引擎和主視窗（熱更新後自動是新的）；ui(fn)：交給畫面執行緒；app_mod()：目前的 app 模組."""

    def __init__(self, get_eng, get_win, ui, app_mod, version, brand):
        self.E = get_eng; self.W = get_win; self.ui = ui; self.app_mod = app_mod; self.version = version; self.brand = dict(brand)
        self.sock = None; self.th = None; self.stop = False; self.port = 0; self.bind = ''; self.err = ''; self.fails = {}; self.n_conn = 0; self.lock = threading.Lock(); self._icons = {}

    def start(self, port, lan=False):
        self.close(); self.port = int(port); self.bind = '0.0.0.0' if lan else '127.0.0.1'; self.err = ''
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if os.name == 'nt' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'): s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else: s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.bind, self.port)); s.listen(32); s.settimeout(1.0)
        except OSError as ex:
            self.err = f'埠 {self.port} 不能用（{ex.strerror or ex}）：可能被別的程式佔用了，請在設定換一個（例如 {self.port + 10}）'
            self._log('⚠ 手機網頁開不起來：' + self.err); return False
        self.sock = s; self.stop = False
        self.th = threading.Thread(target=self._loop, name='Web', daemon=True); self.th.start()
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
            threading.Thread(target=self._conn, args=(c, addr), name='WebConn', daemon=True).start()

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
                if nh > 100 or time.time() > t_dead: return
                if not h or h in (b'\r\n', b'\n'): break
                k, _, v = h.decode('latin-1').partition(':'); H[k.strip().lower()] = v.strip()
            try: n = int(H.get('content-length') or 0)
            except ValueError: n = -1
            if n < 0: self._send(c, Resp(400, b'bad length', 'text/plain')); return
            if n > MAX_BODY: self._send(c, Resp(413, b'too big', 'text/plain')); return
            if n > (1 << 20):                                                   # 還沒登入的不收大的內容
                tk = H.get('x-app-token') or ''
                if not tk:
                    for part in (H.get('cookie') or '').split(';'):
                        a_, _, b_ = part.strip().partition('=')
                        if a_ == 'app_t': tk = urllib.parse.unquote(b_)
                if not (tk and any(same(tk, x) for x in (self.E().cfg.get('web_tokens') or []))): self._send(c, Resp(413, b'too big', 'text/plain')); return
            body = f.read(n) if n else b''
            u = urllib.parse.urlsplit(target); req = Req(method, urllib.parse.unquote(u.path), urllib.parse.parse_qs(u.query), H, body, addr[0] if addr else '')
            try: import vs_mainfirst as MF_; mk_ = MF_.web_begin(req.path)              # V0.6.08 🛟 SortCut 的主程式優先（獨立跑整理時沒有這個檔也沒關係）
            except Exception: MF_ = None
            try: r = self.route(req)
            except Exception as ex:
                self._log(f'手機網頁錯誤：{method} {req.path}\n{traceback.format_exc()}'); r = jresp({'ok': False, 'message': f'{type(ex).__name__}: {ex}'}, 500)
            finally:
                if MF_ is not None:
                    try: MF_.web_end(mk_)
                    except Exception: pass
            try:                                                                    # 大的回應壓縮再送（幾萬部的清單 10 MB → 1～2 MB，手機快很多）（V0.3.29）
                if not getattr(r, 'file', None) and len(r.body) > 32768 and 'gzip' in (H.get('accept-encoding') or '') and 'Content-Encoding' not in r.headers \
                        and any(x in r.ctype for x in ('json', 'html', 'javascript', 'text/')):
                    z = zlib.compressobj(1 if len(r.body) > 1000000 else 5, zlib.DEFLATED, 31); r.body = z.compress(r.body) + z.flush(); r.headers['Content-Encoding'] = 'gzip'; r.headers['Vary'] = 'Accept-Encoding'
            except Exception: pass
            self._send(c, r, method == 'HEAD')
        except Exception: pass
        finally:
            try: c.close()
            except Exception: pass
            with self.lock: self.n_conn -= 1

    def _send(self, c, r, head=False):
        H = {'Content-Type': r.ctype, 'Connection': 'close', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store'}
        H.update(r.headers); H['Content-Length'] = str(r.n if getattr(r, 'file', None) else len(r.body))
        c.sendall((f'HTTP/1.1 {r.code} {REASON.get(r.code, "OK")}\r\n' + ''.join(f'{k}: {v}\r\n' for k, v in H.items()) + '\r\n').encode('latin-1', 'replace'))
        if head: return
        if getattr(r, 'file', None):
            c.settimeout(120); left = r.n
            with open(r.file, 'rb') as fh:
                fh.seek(r.a)
                while left > 0:
                    buf = fh.read(min(262144, left))
                    if not buf: break
                    c.sendall(buf); left -= len(buf)
            return
        c.sendall(r.body)

    # ---- 登入（PIN：錯 5 次鎖 5 分鐘；登入後給 token，存在 cookie）
    def authed(self, req):
        toks = self.E().cfg.get('web_tokens') or []; t = req.headers.get('x-app-token') or req.cookie('app_t')
        return bool(t) and any(same(t, x) for x in toks)

    def login(self, req):
        E = self.E(); d = req.json(); cl = req.client(); n, t0 = self.fails.get(cl, (0, 0))
        if n >= 5 and time.time() - t0 < 300: return jresp({'ok': False, 'message': '錯太多次，請 5 分鐘後再試'}, 429)
        h = E.cfg.get('web_pin_hash'); salt = E.cfg.get('web_pin_salt') or ''
        if not h: return jresp({'ok': False, 'message': '電腦上還沒設定 PIN：到 設定 → 📱 手機網頁 設一個'}, 403)
        if not same(pin_hash(str(d.get('pin', '')), salt), h):
            self.fails[cl] = (n + 1, time.time()); self._log(f'手機網頁：PIN 錯誤（{cl}，第 {n + 1} 次）')
            return jresp({'ok': False, 'message': 'PIN 不對' + (f'（再錯 {4 - n} 次會鎖 5 分鐘）' if n >= 1 else '')}, 401)
        self.fails.pop(cl, None); tok = rand_hex(24); E.cfg.set('web_tokens', list(E.cfg.get('web_tokens') or [])[-19:] + [tok])
        self._log(f'手機網頁：登入成功（{cl}）')
        return jresp({'ok': True, 'token': tok}, headers={'Set-Cookie': f'app_t={tok}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Strict'})

    # ---- 靜態（頁面、PWA）
    def icon(self, size):
        if size not in self._icons:
            fn = {512: 'icon_512.png', 192: 'icon_192.png', 'mask': 'icon_512.png'}.get(size)
            try: self._icons[size] = (HERE / fn).read_bytes()
            except Exception:
                a = self.brand.get('accent', '#e51e63').lstrip('#'); rgb = tuple(int(a[i:i + 2], 16) for i in (0, 2, 4)) if len(a) == 6 else (229, 30, 99)
                self._icons[size] = make_icon_png(size if isinstance(size, int) else 512, rgb)
        return Resp(200, self._icons[size], 'image/png', {'Cache-Control': 'public, max-age=86400'})

    def manifest(self):
        B = self.brand
        m = {'name': B.get('title'), 'short_name': B.get('name'), 'start_url': './', 'scope': './', 'display': 'standalone', 'orientation': 'any',
             'background_color': '#0b0f14', 'theme_color': '#0b0f14', 'id': B.get('phone_id') or (B.get('id', 'app').lower() + '-phone'), 'lang': 'zh-TW',
             'icons': [{'src': 'icon-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'}, {'src': 'icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
                       {'src': 'icon-mask.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'}],
             'shortcuts': [{'name': n, 'short_name': n, 'url': u, 'icons': [{'src': 'icon-192.png', 'sizes': '192x192'}]} for n, u in      # 長按桌面圖示的捷徑（V0.2.01）
                           (('🎞 分類', './?go=vc'), ('🔎 搜尋', './?go=tool:find'), ('🧳 活動', './?go=tool:evt'), ('📦 隔離區', './?go=tool:q'))]}
        return Resp(200, json.dumps(m, ensure_ascii=False).encode('utf-8'), 'application/manifest+json; charset=utf-8')

    def sw(self):
        js = ("const V='%s-%s';self.addEventListener('install',e=>self.skipWaiting());"
              "self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(K=>Promise.all(K.filter(k=>k!==V).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));"
              "self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET'||u.pathname.startsWith('/api/'))return;"
              "e.respondWith(fetch(e.request).then(r=>{if(r.ok&&(u.pathname==='/'||u.pathname.endsWith('.png'))){const c=r.clone();caches.open(V).then(x=>x.put(e.request,c));}return r;})"
              ".catch(()=>caches.match(e.request).then(r=>r||new Response('<h3 style=\"font-family:sans-serif;color:#ccc;background:#0b0f14\">連不到電腦（Tailscale 有開嗎？電腦開著嗎？）</h3>',{headers:{'Content-Type':'text/html; charset=utf-8'}}))));});"
              ) % (self.brand.get('id', 'app'), self.version)
        return Resp(200, js.encode('utf-8'), 'application/javascript; charset=utf-8', {'Service-Worker-Allowed': '/'})

    def page(self):
        import fc_webpage as webpage
        html = webpage.PAGE.replace('__VER__', str(self.version)).replace('__NAME__', str(self.brand.get('name'))).replace('__TITLE__', str(self.brand.get('title'))).replace('__ACCENT__', str(self.brand.get('accent', '#e51e63'))).replace('__PREFIX__', str(self.brand.get('prefix', 'AK')))
        return Resp(200, html.encode('utf-8'), 'text/html; charset=utf-8')

    def route(self, req):
        p = req.path
        if p in ('/', '/index.html'): return self.page()
        if p == '/manifest.webmanifest': return self.manifest()
        if p == '/sw.js': return self.sw()
        if p in ('/icon-192.png', '/icon-512.png', '/favicon.ico'): return self.icon(512 if '512' in p else 192)
        if p in ('/icon-mask.png', '/apple-touch-icon.png'): return self.icon('mask')
        if p == '/api/hello': return jresp({'ok': True, 'ver': self.version, 'name': self.brand.get('name'), 'authed': self.authed(req), 'pin_set': bool(self.E().cfg.get('web_pin_hash'))})
        if p == '/api/login' and req.method == 'POST': return self.login(req)
        if not p.startswith('/api/'): return Resp(404, b'not found', 'text/plain')
        if not self.authed(req): return jresp({'ok': False, 'message': '要先輸入 PIN', 'login': True}, 401)
        name = p[5:].split('/')[0]; fn = getattr(self, 'api_' + name.replace('-', '_'), None)
        if fn is None: return jresp({'ok': False, 'message': f'沒有這個功能：{name}'}, 404)
        t0 = time.time()
        try: return fn(req)
        finally:
            dt = time.time() - t0
            if dt > 3 and name not in ('fc_thumb', 'vc_thumb', 'vc_img', 'play', 'update_up', 'update', 'report'):
                try: self.E().log.w(f'⏱ 手機網頁比較慢：{name}　{dt:.1f} 秒')         # 找「畫面空白／很慢」用（V0.2.59）
                except Exception: pass

    def _ui(self, fn):
        try: self.ui(fn)
        except Exception: pass

    # ================================================================ API（新功能照這樣加：def api_xxx(self, req): ... return jresp({...})）
    def api_state(self, req):
        E = self.E(); I = E.info()
        return jresp({'ok': True, 'ver': self.version, 'time': time.strftime('%H:%M:%S'), 'info': I, 'ctl': E.bg_view(),
                      'tasks': [{k: t.get(k) for k in ('title', 'state', 'pct', 'msg', 't0')} for t in E.tasks_list()[-15:]][::-1]})

    def api_perf(self, req):
        return jresp(dict(self.E().perf.view(), ok=True, time=time.strftime('%H:%M:%S')))

    def api_bgctl(self, req):
        """後台總控制：a＝pause／resume／stop／up／down／all_pause／all_resume／guard（on、cpu_max、ramp_sec）／demo（排示範工作）."""
        E = self.E(); d = req.json() if req.method == 'POST' else {}; a = d.get('a'); k = d.get('k')
        if a in ('pause', 'resume', 'stop', 'up', 'down') and k not in {x[0] for x in E.BG_KINDS}: return jresp({'ok': False, 'message': '不認得的項目'}, 400)
        if a: E.log.w(f'📱 手機：後台 {a} {k or ""}')
        if a == 'guard':
            if 'on' in d: E.cfg.set('cpu_guard', bool(d['on']))
            if d.get('cpu_max'): E.cfg.set('cpu_max', max(50, min(100, int(d['cpu_max']))))
            if d.get('ramp_sec') is not None: E.cfg.set('bg_ramp_sec', max(0, min(300, int(d['ramp_sec']))))
        elif a == 'pause': E.bg_set_pause(k, True, '手機')
        elif a == 'resume': E.bg_set_pause(k, False, '手機')
        elif a == 'stop': E.bg_stop_now(k)
        elif a in ('up', 'down'): E.bg_move(k, -1 if a == 'up' else 1)
        elif a == 'all_pause': E.bg_all(True)
        elif a == 'all_resume': E.bg_all(False)
        elif a == 'demo': E.demo_add(int(d.get('n') or 5), float(d.get('sec') or 8))
        self._ui(lambda: getattr(self.W(), 'bgp', None) and self.W().bgp.refresh())
        return jresp({'ok': True, 'ctl': E.bg_view()})

    SETTABLE = {'ui_theme': str, 'cpu_guard': bool, 'cpu_max': int, 'bg_ramp_sec': int, 'close_to_tray': bool, 'auto_restart': bool,
                'hash_n': int, 'health_n': int, 'health_deep': bool, 'media_only': bool, 'meta_n': int, 'meta_dhash': bool, 'repair_n': int, 'auto_repair': bool, 'auto_quar_broken': bool,
                'vc_next': bool, 'vgrid_n': int, 'skip_pkg': bool, 'vc_skip_live': bool, 'vc_sub': str, 'vc_dup_del': bool, 'pet_auto': bool, 'vc_mix': bool, 'pet_face': bool, 'pet_build': bool, 'rm_empty_dirs': bool, 'quiet_on': bool, 'quiet_from': int, 'quiet_to': int, 'vs_root': str, 'db_backup': bool, 'upd_dl_dir': str}   # 手機可以改的設定（新功能的設定加在這裡）

    # (分類, 代號, 名稱, 型別, 選項)：bool／choice [(值, 文字)]／num [最小, 最大]／text
    SETDEF = [('bg', 'cpu_guard', '⚖ 電腦太忙時背景工作自動讓路', 'bool', None), ('bg', 'cpu_max', 'CPU 平均超過幾 % 開始讓路', 'choice', [(70, '70'), (80, '80'), (85, '85'), (90, '90'), (95, '95'), (100, '100')]),
              ('bg', 'bg_ramp_sec', '開始時慢慢加速：每幾秒多開 1 個', 'choice', [(0, '不用'), (10, '10'), (20, '20'), (30, '30'), (60, '60'), (120, '120')]),
              ('bg', 'quiet_on', '🌙 指定時段不跑背景工作（例如白天用電腦時）', 'bool', None),
              ('bg', 'quiet_from', '🌙 從幾點開始不跑', 'choice', [(h, f'{h} 點') for h in range(24)]),
              ('bg', 'quiet_to', '🌙 到幾點恢復', 'choice', [(h, f'{h} 點') for h in range(24)]),
              ('scan', 'media_only', '只看照片和影片（其他檔案不列入）', 'bool', None), ('scan', 'hash_n', '比對重複：同時幾個（傳統硬碟建議 1～2）', 'choice', [(1, '1'), (2, '2'), (3, '3'), (4, '4'), (6, '6'), (8, '8')]),
              ('scan', 'health_n', '損毀檢查：同時幾個', 'choice', [(1, '1'), (2, '2'), (3, '3'), (4, '4'), (6, '6'), (8, '8'), (12, '12')]),
              ('scan', 'health_deep', '損毀檢查用 FFmpeg 解碼（比較準、比較慢）', 'bool', None), ('scan', 'meta_n', '讀取拍攝資訊：同時幾個', 'choice', [(1, '1'), (2, '2'), (3, '3'), (4, '4'), (6, '6'), (8, '8'), (12, '12')]),
              ('scan', 'meta_dhash', '順便算「相似照片指紋」（每張多約 0.1 秒）', 'bool', None),
              ('scan', 'skip_pkg', '🎮 遊戲／軟體資料夾裡的照片影片（素材）不列入重複、損毀、分類、相似…', 'bool', None),
              ('rep', 'auto_repair', '🌙 自動修復：檢查出有問題就試著修復／救出（不用按）', 'bool', None),
              ('rep', 'auto_quar_broken', '🌙 自動隔離：打不開／0 位元組的原檔，修完自動搬到隔離區', 'bool', None), ('rep', 'repair_n', '修復：同時幾個（很吃硬碟）', 'choice', [(1, '1'), (2, '2'), (3, '3'), (4, '4'), (6, '6')]),
              ('vc', 'vc_next', '🎞 按了分類自動跳下一部', 'bool', None),
              ('vc', 'rm_empty_dirs', '🧹 搬走之後變「完全空」的資料夾順手收掉（復原時會自動建回來）', 'bool', None),
              ('vc', 'vc_dup_del', '🗑 分類過的影片，它在別處一模一樣的副本自動標成「Delete」（只留分類的那一份）', 'bool', None),
    ('vc', 'vc_sub', '🚚 搬檔時，分類資料夾裡再細分', 'choice', [('', '不分'), ('dir', '照原本的資料夾名'), ('y', '年（2023）'), ('ym', '年-月（2023-05）'), ('y_ym', '年＼年-月')]),
              ('vc', 'vc_skip_live', '📱 不列動態照片的那段短影片（跟照片同名、4 秒以內）', 'bool', None),
              ('vc', 'vc_mix', '🧮 💡 建議也用「綜合好幾個線索」（關掉＝只照單一很強的線索）', 'bool', None),
              ('vc', 'pet_auto', '🐾 背景自動看新的影片有沒有貓狗、人、全黑（每 10 分鐘）', 'bool', None),
              ('vc', 'pet_face', '👤 看內容時也找人臉', 'bool', None),
              ('vc', 'pet_build', '🎞 看內容時，還沒做 16 格的先做好再看', 'bool', None),
              ('vc', 'vgrid_n', '背景做 16 格預覽：同時幾個', 'choice', [(1, '1'), (2, '2'), (3, '3'), (4, '4')]), ('vc', 'vs_root', 'SortCut 的資料夾（有 Data\\videosift.sqlite3；空的＝自動找）', 'text', None),
              ('misc', 'close_to_tray', '按 X：縮到右下角（不關程式）', 'bool', None), ('misc', 'auto_restart', '閃退自動重開', 'bool', None),
              ('misc', 'db_backup', '每天備份資料庫', 'bool', None), ('misc', 'upd_dl_dir', '找新版更新包的資料夾（空的＝這台電腦的「下載」）', 'text', None)]

    def api_settings(self, req):
        E = self.E()
        if req.method == 'POST':
            d = req.json(); ch = []
            if 'k' in d and 'v' in d and len(d) == 2: d = {d['k']: d['v']}             # 新的設定頁：一次改一項
            for k, v in d.items():
                tp = self.SETTABLE.get(k)
                if tp is None: continue
                try: E.cfg.set(k, tp(v)); ch.append(k)
                except Exception: pass
            if 'vs_root' in ch: E.vc.vs['t'] = 0                                    # SortCut 位置改了：下次重新找
            if 'skip_pkg' in ch: threading.Thread(target=E.pkg_mark, name='PkgMark', daemon=True).start()
            self._ui(lambda: getattr(self.W(), 'setp', None) and self.W().setp.load())
            self._ui(lambda: getattr(self.W(), 'home', None) and self.W().home.load())
            return jresp({'ok': True, 'changed': ch})
        DV = {'pet_face': False, 'pet_build': True, 'vc_mix': True}                                   # V0.6.00 人臉太吃效能：預設不找（要再到設定打開）                                    # 沒設過時的預設（V0.4.27）
        S = [{'cat': c, 'k': k, 'name': n, 'type': t, 'opt': o, 'v': E.cfg.get(k) if E.cfg.get(k) is not None else DV.get(k)} for c, k, n, t, o in self.SETDEF]
        return jresp({'ok': True, 'cfg': {k: E.cfg.get(k) for k in self.SETTABLE}, 'settings': S, 'lab': dict(E.cfg.get('lab') or {}), 'labs': getattr(self.app_mod(), 'LAB_LIST', [])})

    def api_lab(self, req):
        E = self.E(); d = req.json(); k = str(d.get('k') or '')
        if k not in {x[0] for x in getattr(self.app_mod(), 'LAB_LIST', [])}: return jresp({'ok': False, 'message': '不認得的實驗功能'}, 400)
        L = dict(E.cfg.get('lab') or {}); L[k] = bool(d.get('on')); E.cfg.set('lab', L)
        self._ui(lambda: getattr(self.W(), 'lab', None) and self.W().lab.load()); return jresp({'ok': True, 'lab': L})

    def api_log(self, req):
        E = self.E(); f = req.q('f', 'app_log.txt')
        if f not in ('app_log.txt', 'error_log.txt', 'ui_freeze_log.txt', 'update_log.txt'): f = 'app_log.txt'
        try:
            p = E.log.d / f; sz = p.stat().st_size
            with open(p, 'rb') as fh: fh.seek(max(0, sz - 60000)); txt = fh.read().decode('utf-8', 'replace')
        except Exception: txt = ''
        return jresp({'ok': True, 'f': f, 'text': txt[-60000:]})

    def api_update(self, req):
        """手機上傳更新包（<前綴>_V….zip）→ 放進 UPDATE → 在電腦上熱更新（程式不用關）."""
        E = self.E(); W = self.W(); M = self.app_mod()
        if req.method != 'POST' or not req.body: return jresp({'ok': False, 'message': '沒有收到檔案'})
        nm = re.sub(r'[^\w.\-]', '_', req.q('name') or 'update.zip')
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
            try: W.upd.pkg = pkg; M.hot_update(W, pkg)
            except Exception: E.log.err('手機熱更新')
        self._ui(lambda: M.QTimer.singleShot(400, go))
        return jresp({'ok': True, 'message': f'V{pkg["version"]} 熱更新中…（大約 5～10 秒，之後手機會自動重新整理）', 'ver': pkg['version']})

    # ---- 🆕 線上更新（照 TikLive）：上傳或用「下載」裡的更新包 → 先看改了什麼 → 按「開始更新」；可以退回前一版
    def _upd_check(self, path, name):
        E = self.E(); M = self.app_mod()
        try: pkg = M.load_pkg(path) if str(path).lower().endswith('.zip') else M.load_backup(path)
        except Exception as ex: return {'ok': False, 'message': f'不能用這個更新包：{ex}'}
        tok = rand_hex(10); E.upd_st.clear(); E.upd_st.update(tok=tok, pkg=pkg, state='ready', name=name, t=time.time())
        c = M.vkey(pkg['version']); cur = M.vkey(self.version)
        E.log.w(f'🆕 更新包檢查好了：{name}（V{self.version} → V{pkg["version"]}）')
        return {'ok': True, 'tok': tok, 'from': self.version, 'to': pkg['version'], 'cmp': 1 if c > cur else (0 if c == cur else -1), 'notes': pkg.get('notes') or [], 'hot': bool(pkg.get('hot_ok')), 'name': name}

    def api_update_dl(self, req):
        M = self.app_mod(); E = self.E(); C = self.__dict__.setdefault('_dlc', {'t': 0, 'v': None})
        if time.time() - C['t'] > 12:                                           # 跟 TikLive 一樣約 15 秒看一次（只列資料夾）
            try: C['v'] = M.upd_scan()
            except Exception: C['v'] = None
            C['t'] = time.time()
        f = C['v']; dirs = [str(d) for d in M.upd_dirs()]
        return jresp({'ok': True, 'cur': self.version, 'found': {k: f[k] for k in ('ver', 'name', 'size', 'mtime')} if f else None, 'dir': dirs[-1], 'dirs': dirs})

    def api_update_prep(self, req):
        """用「下載」（或 UPDATE）資料夾裡找到的那個更新包：先檢查（還要按「開始更新」）."""
        M = self.app_mod(); f = M.upd_scan()
        if not f: return jresp({'ok': False, 'message': '下載資料夾裡沒有比現在新的更新包'})
        return jresp(self._upd_check(f['path'], f['name']))

    def api_update_up(self, req):
        """手機上傳更新包：存到 UPDATE\\手機上傳（留最近 5 個）→ 檢查 → 回傳改了什麼（還要按「開始更新」）."""
        E = self.E(); body = req.body or b''
        if len(body) < 200 or body[:2] != b'PK': return jresp({'ok': False, 'message': f'這不是 zip 檔，請選 {self.brand.get("prefix")}_V版本.zip'})
        nm = re.sub(r'[^\w.\-]+', '_', req.q('name') or 'update.zip')[-80:]
        if not nm.lower().endswith('.zip'): nm += '.zip'
        d = E.root / 'UPDATE' / '手機上傳'
        try:
            d.mkdir(parents=True, exist_ok=True); p = d / (time.strftime('%Y%m%d_%H%M%S_') + nm); p.write_bytes(body)
            for old in sorted(d.glob('*.zip'), key=lambda x: x.stat().st_mtime)[:-5]:
                try: old.unlink()
                except OSError: pass
        except Exception as ex: return jresp({'ok': False, 'message': f'電腦存檔失敗：{ex}'})
        E.log.w(f'📱 手機：上傳更新包 {nm}（{len(body):,} bytes）'); return jresp(self._upd_check(p, nm))

    def api_update_apply(self, req):
        E = self.E(); W = self.W(); M = self.app_mod(); st = E.upd_st; d = req.json()
        if not st.get('pkg') or d.get('tok') != st.get('tok'): return jresp({'ok': False, 'message': '更新包過期了，請重新選一次'})
        pkg = st['pkg']
        if not pkg.get('hot_ok'):
            try:
                u = E.root / 'UPDATE'; u.mkdir(exist_ok=True)
                if str(pkg['path']).lower().endswith('.zip') and Path(pkg['path']).parent.resolve() != u.resolve(): shutil.copy2(pkg['path'], u / Path(pkg['path']).name)
            except Exception as ex: return jresp({'ok': False, 'message': str(ex)})
            return jresp({'ok': False, 'message': f'V{pkg["version"]} 不支援熱更新：已放進 UPDATE，下次打開程式時套用'})
        st.update(state='run', to=pkg['version'], t=time.time()); E.log.w(f'📱 手機：開始更新到 V{pkg["version"]}')
        def go():
            try: ok = M.hot_update(W, pkg)
            except Exception as ex: ok = False; st['message'] = str(ex); E.log.err('手機熱更新')
            st.update(state='done' if ok else 'failed', pkg=None)
            if not ok:
                why = st.get('message') or getattr(M, 'LAST_UPD_ERR', '') or ''
                st['message'] = '新版載入不了，已經自動還原成原本的版本。把電腦上的程式關掉再打開，就會改用重開的方式套用。' + (f'\n原因：{why}' if why else '')
        self._ui(lambda: M.QTimer.singleShot(300, go))
        return jresp({'ok': True, 'message': f'更新到 V{pkg["version"]} 中…'})

    def api_update_status(self, req):
        st = self.E().upd_st; return jresp({'ok': True, 'current': self.version, 'state': st.get('state', ''), 'to': st.get('to', ''), 'message': st.get('message', '')})

    def api_update_rollback(self, req):
        """GET：可以退回的版本（每次更新前自動備份的，最近 3 個不同版本）；POST {id}：用那個備份（一樣先檢查、再按「開始更新」）."""
        E = self.E(); M = self.app_mod(); root = E.root / 'app_backup'
        if req.method == 'POST':
            nm = Path(str(req.json().get('id') or '')).name; d = root / nm
            if not nm or not d.is_dir(): return jresp({'ok': False, 'message': '找不到這個備份'})
            return jresp(self._upd_check(d, nm))
        L = []; seen = set()
        try: D = sorted([d for d in root.iterdir() if d.is_dir()], key=lambda d: d.name, reverse=True)
        except OSError: D = []
        for d in D:
            try: pkg = M.load_backup(d)
            except Exception: continue
            if pkg['version'] in seen or pkg['version'] == self.version: continue
            seen.add(pkg['version']); m = re.match(r'(\d{8})_(\d{6})', d.name)
            L.append({'id': d.name, 'version': pkg['version'], 'time': (f'{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]} {m.group(2)[:2]}:{m.group(2)[2:4]}' if m else d.name),
                      'notes': (pkg.get('notes') or [])[:3], 'older': M.vkey(pkg['version']) < M.vkey(self.version)})
            if len(L) >= 3: break
        return jresp({'ok': True, 'items': L, 'current': self.version})

    def api_changelog(self, req):
        try: C = json.loads((HERE / 'fc_CHANGELOG.json').read_text(encoding='utf-8'))[:int(req.q('n', '20') or 20)]
        except Exception: C = []
        return jresp({'ok': True, 'log': C})

    def api_logout(self, req):
        E = self.E(); t = req.headers.get('x-app-token') or req.cookie('app_t')
        E.cfg.set('web_tokens', [x for x in (E.cfg.get('web_tokens') or []) if not same(x, t)])
        return jresp({'ok': True}, headers={'Set-Cookie': 'app_t=; Path=/; Max-Age=0'})

    # ================================================================ FileCompare（跟電腦版同一套：總覽、重複檔、損毀檢查、隔離區）
    def _reload_ui(self, *names):
        def f():
            W = self.W()
            for n in names:
                p = getattr(W, n, None)
                try:
                    if p is not None: (p.reload if hasattr(p, 'reload') else p.load)()
                except Exception: pass
        self._ui(f)

    def api_fc_state(self, req):
        E = self.E(); I = E.info()
        return jresp({'ok': True, 'fc': I.get('fc') or {}, 'busy': I.get('busy') or {}, 'scan_q': I.get('scan_q', 0), 'bulk': I.get('bulk') or {},
                      'roots': E.fc_list('roots'), 'prio': E.fc_list('keep_prio'), 'skip': E.fc_list('skip_dirs'), 'pause': {k: bool(E.bg_pause.get(k)) for k in E.FC_KINDS}})

    def api_fc_run(self, req):
        """a＝scan（開始掃描）／pause、resume（k＝scan／hash／health）／bulk（全部照建議處理，kind）／bulk_stop／add、del（which＝roots／keep_prio，p）／move（p，d）."""
        E = self.E(); d = req.json(); a = d.get('a'); E.log.w(f'📱 手機：FileCompare {a} {d.get("p") or d.get("k") or ""}')
        if a == 'scan': n = E.fc_scan_add(); r = {'ok': True, 'message': f'排了 {n} 個資料夾要掃描' if n else '已經在掃描／排隊中了'}
        elif a in ('pause', 'resume') and d.get('k') in E.FC_KINDS: E.bg_set_pause(d['k'], a == 'pause', '手機'); r = {'ok': True, 'message': '好了'}
        elif a == 'bulk': ok = E.fc_bulk_start(d.get('kind') or '', d.get('folder') or ''); r = {'ok': ok, 'message': '⚡ 開始全部處理（背景做）' if ok else '已經在處理中了'}
        elif a == 'bulk_stop': E.fc_bulk.update(cancel=True); r = {'ok': True, 'message': '停止中…'}
        elif a in ('add', 'del') and d.get('which') in ('roots', 'keep_prio', 'skip_dirs') and d.get('p'):
            ok, m = (E.fc_list_add if a == 'add' else E.fc_list_del)(d['which'], str(d['p'])); r = {'ok': ok, 'message': m}
            if ok and d['which'] == 'skip_dirs': threading.Thread(target=E.skip_mark, daemon=True).start(); r['message'] += '（背景標記中）'
        elif a == 'move' and d.get('p'): E.fc_list_move('keep_prio', str(d['p']), int(d.get('d') or 0)); r = {'ok': True, 'message': '好了'}
        else: return jresp({'ok': False, 'message': '不認得的動作'}, 400)
        self._reload_ui('home'); return jresp(r)

    def api_fc_groups(self, req):
        E = self.E(); off = max(0, int(req.q('offset', '0') or 0)); k = req.q('kind', ''); fo = req.q('folder', '')
        if fo: n, sv = E.fc_groups_n(k, fo); return jresp({'ok': True, 'groups': E.fc_groups(off, 50, k, fo), 'offset': off, 'total': n, 'save': sv, 'folder': fo})
        return jresp({'ok': True, 'groups': E.fc_groups(off, 50, k), 'offset': off, 'total': (E.fc_counts() or {}).get('dup_groups', 0)})

    def api_fc_group(self, req):
        return jresp({'ok': True, 'files': self.E().fc_group(req.q('g'))})

    def api_fc_keep(self, req):
        d = req.json(); r = self.E().fc_keep_group(str(d.get('g') or ''), int(d.get('keep') or 0), '手機')
        self._reload_ui('dupp'); return jresp(r)

    def api_fc_health(self, req):
        E = self.E(); off = max(0, int(req.q('offset', '0') or 0))
        return jresp(dict(E.fc_health_list(req.q('f', 'bad'), req.q('kind', ''), off, 100), ok=True, offset=off))

    def api_fc_decide(self, req):
        d = req.json(); r = self.E().fc_decide(int(d.get('id') or 0), str(d.get('a') or ''))
        self._reload_ui('healthp'); return jresp(r)

    def api_fc_thumb(self, req):
        E = self.E(); fid = int(req.q('id', '0') or 0); tw = max(64, min(1600, int(req.q('w', '480') or 480)))
        out = Path(E.data) / 'thumbs' / f'{fid % 100:02d}' / f'{fid}_{tw}.jpg'
        if out.exists(): return Resp(200, out.read_bytes(), 'image/jpeg', {'Cache-Control': 'private, max-age=86400'})
        if tw < 1000 and req.q('wait', '') != '1':                                  # 小縮圖還沒做：背景做、馬上回（不佔連線）（V0.3.49）
            if ('fc', fid, tw) in self.__dict__.get('_thfail', set()): return Resp(404, b'no preview', 'text/plain')
            self._thumb_q(E, fid, tw, 'fc'); return Resp(503, b'making', 'text/plain', {'Retry-After': '2'})
        try: p = E.fc_thumb(fid, tw)
        except Exception: p = None
        if not p: return Resp(404, b'no preview', 'text/plain')
        return Resp(200, Path(p).read_bytes(), 'image/jpeg', {'Cache-Control': 'private, max-age=86400'})

    def api_fc_moves(self, req):
        off = max(0, int(req.q('offset', '0') or 0))
        import fc_fcore as fcore
        E = self.E(); cv = req.q('cv', '') == '1'; dr = E.quar_drives() if not off else []
        dr = [d for d in dr if (fcore.CONV_QUAR_NAME in d[0]) == cv]
        nc = (E.db.one("SELECT COUNT(*) FROM moves WHERE undone=0 AND (" + ' OR '.join("reason LIKE ?" for _ in E.CONV_R) + ")", [x + '%' for x in E.CONV_R]) or [0])[0]
        return jresp(dict(E.fc_moves(off, 100, req.q('all') != '1', req.q('r', ''), cv), ok=True, offset=off, reasons=E.fc_move_reasons(cv), drives=dr, conv_n=nc))

    def api_quar_cells(self, req):
        """V0.5.77 📦 隔離區預覽：這部的 16 格（沒有就現在做；做不出來說原因）."""
        try:
            E = self.E(); fid = int(req.q('id', '0') or 0); f = E.fc_file(fid)
            if not f: return jresp({'ok': False, 'message': '這個檔的紀錄已經不在（可能已經永久刪除）'})
            nm = os.path.basename(f.get('path') or ''); info = {'name': nm, 'path': f.get('path') or '', 'size': f.get('size') or 0, 'dur': f.get('dur') or 0, 'w': f.get('w') or 0, 'h': f.get('h') or 0,
                                                              'health': f.get('health') or '', 'hmsg': f.get('health_msg') or '', 'kind': f.get('kind') or ''}
            import fc_fcore as fcore_
            if not os.path.exists(fcore_.lp(f.get('path') or '')): return jresp(dict(info, ok=False, message='硬碟上找不到這個檔（被刪掉、或硬碟沒接）'))
            if f.get('kind') == 'photo': return jresp(dict(info, ok=True, photo=True))
            g = E.vc.grid(fid, build=True)
            if not g.get('ok'): return jresp(dict(info, ok=False, message=g.get('message') or '沒辦法做預覽（影片可能壞了）'))
            return jresp(dict(info, ok=True, cols=g['cols'], rows=g['rows'], cells=g['cells'][:16], ar=g.get('ar') or 16 / 9))
        except Exception as ex: return jresp({'ok': False, 'message': f'預覽失敗：{ex}'})

    def api_fc_undo(self, req):
        d = req.json()
        if d.get('reason'): r = self.E().fc_undo_reason(str(d['reason'])); self._reload_ui('quarp'); return jresp(r)
        E = self.E()
        if d.get('all'):                                                             # 全部復原：一般／轉檔後隔離區分開（V0.4.61）
            cvw = ' OR '.join("reason LIKE ?" for _ in E.CONV_R)
            ids = [r[0] for r in E.db.q(f"SELECT id FROM moves WHERE undone=0 AND {'(' + cvw + ')' if d.get('cv') else 'NOT (' + cvw + ')'}", [x + '%' for x in E.CONV_R])]
            r = E.fc_undo(ids) if ids else {'ok': False, 'message': '沒有可以復原的'}
        else: r = E.fc_undo([int(x) for x in (d.get('ids') or [])])
        self._reload_ui('quarp'); return jresp(r)

    def api_fc_search(self, req):
        """POST {f: 條件, offset, order, facets: true/false}：跟電腦版「🔎 搜尋篩選」同一套條件."""
        E = self.E(); d = req.json(); F = d.get('f') or {}; off = max(0, int(d.get('offset') or 0)); order = str(d.get('order') or 'taken')
        r = E.fc_search(F, off, 60, order); r.update(ok=True, offset=off, src_nm=E.SRC_NM, dsrc_nm=E.DSRC_NM)
        if d.get('facets'): r['facets'] = E.fc_facets(F)
        return jresp(r)

    def api_fc_repair(self, req):
        """POST {ids:[…]} 或 {f: 損毀篩選, kind}：排進「🛠 修復／救出」."""
        E = self.E(); d = req.json()
        n = E.fc_repair_add([int(x) for x in d['ids']]) if d.get('ids') else E.fc_repair_add(None, str(d.get('f') or 'bad'), str(d.get('kind') or ''))
        self._reload_ui('healthp'); return jresp({'ok': True, 'n': n, 'message': f'🛠 排了 {n:,} 個要修復／救出（背景做）'})

    def api_fc_quar_filter(self, req):
        d = req.json(); ok = self.E().fc_quar_filter(str(d.get('f') or ''), str(d.get('kind') or ''))
        self._reload_ui('healthp'); return jresp({'ok': ok, 'message': '📦 開始整批搬到隔離區（背景做）' if ok else '不能整批搬（可能已經有整批的工作在跑）'})

    def api_fc_repairs(self, req):
        E = self.E(); fid = int(req.q('id', '0') or 0); f = E.fc_file(fid) or {}
        return jresp({'ok': True, 'rep': f.get('rep', 0), 'msg': f.get('rep_msg', ''), 'items': E.fc_repairs(fid)})

    def api_fc_rthumb(self, req):
        try: p = self.E().fc_rthumb(int(req.q('id', '0') or 0), int(req.q('w', '320') or 320))
        except Exception: p = None
        if not p: return Resp(404, b'no preview', 'text/plain')
        return Resp(200, Path(p).read_bytes(), 'image/jpeg', {'Cache-Control': 'private, max-age=86400'})

    def api_fc_quar_many(self, req):
        d = req.json(); r = self.E().fc_quar_many([int(x) for x in (d.get('ids') or [])], '手動（手機）')
        self._reload_ui('searchp'); return jresp(r)

    def api_fc_csv(self, req):
        """手機下載 CSV：GET ?f=<JSON 條件>&order=."""
        import tempfile
        E = self.E()
        try: F = json.loads(req.q('f') or '{}')
        except Exception: F = {}
        fd, p = tempfile.mkstemp(suffix='.csv'); os.close(fd)
        try:
            E.fc_export_csv(F, p, req.q('order', 'taken')); body = Path(p).read_bytes()
        finally:
            try: os.remove(p)
            except OSError: pass
        return Resp(200, body, 'text/csv; charset=utf-8', {'Content-Disposition': f'attachment; filename="FileCompare_{time.strftime("%Y%m%d_%H%M")}.csv"'})

    # ---- 📈 資料分析
    def api_ana(self, req):
        E = self.E()
        try: cap = E.cap_summary()
        except Exception: cap = None
        return jresp(dict(E.ana_view(), ok=True, cap=cap))

    def api_ana_run(self, req):
        """a＝start／pause／resume／stop."""
        E = self.E(); a = req.json().get('a'); E.log.w(f'📱 手機：資料分析 {a}')
        if a == 'start':
            if not E.fc_list('roots'): return jresp({'ok': False, 'message': '先在總覽加入要整理的資料夾'})
            ok = E.ana_start(); return jresp({'ok': ok, 'message': '📈 開始分析（背景做）' if ok else '已經在分析／排隊中了'})
        if a in ('pause', 'resume'): E.bg_set_pause('ana', a == 'pause', '手機'); return jresp({'ok': True, 'message': '好了'})
        if a == 'stop': E.bg_stop_now('ana'); return jresp({'ok': True, 'message': '停止了'})
        return jresp({'ok': False, 'message': '不認得的動作'}, 400)

    def api_ana_dir(self, req):
        return jresp(self.E().ana_dir(req.q('p', '')))

    def api_ana_pkgs(self, req):
        return jresp({'ok': True, 'rows': self.E().ana_pkgs(req.q('t', ''), 500)})

    # ---- 🎞 影片快速分類
    def api_vc_state(self, req):
        E = self.E(); V = E.vc.vs
        return jresp({'ok': True, 'cats': E.vc.cats(), 'mv': {k: v for k, v in E.vc.mv.items() if k != 'err'}, 'vs': {'db': V.get('db', ''), 'n': V.get('n', 0), 'err': V.get('err', '')},
                      'next': E.cfg.get('vc_next') is not False, 'sp': E.vc.speed(), 'pet': bool(E.pet.st.get('run')), 'petn': [E.pet.st.get('n') or 0, E.pet.st.get('total') or 0] if E.pet.st.get('run') else None})

    def api_vc_sus(self, req):
        """🧐 可能分錯的有幾部（V0.4.31）；POST {ok: fid}＝這部沒錯（V0.4.35）."""
        if req.method == 'POST':
            d = req.json(); ok = self.E().vc.sus_ok(int(d.get('ok') or 0)); return jresp({'ok': ok, 'message': '👌 好，這部不再列' if ok else '找不到'})
        try:
            V = self.E().vc; n = len(V.suspects())
            if req.q('d', '') != '1': return jresp({'ok': True, 'n': n})
            nv = len(V.vlist('chk', kind='video')); np_ = len(V.vlist('chk', kind='photo'))   # V0.5.76 影片／照片各幾部（清單是分開看的）
            return jresp({'ok': True, 'n': n, 'nv': nv, 'np': np_, 'nx': max(0, n - nv - np_)})
        except Exception as ex: return jresp({'ok': False, 'n': 0, 'message': str(ex)})

    def api_vc_marks(self, req):
        """🐾 只重拿小格子上的記號（🐾／🌑），不用重讀整份清單（V0.4.22）：POST {ids}."""
        E = self.E(); L = [int(x) for x in (req.json().get('ids') or [])] if req.method == 'POST' else []
        E.pet._scc = {}
        return jresp({'ok': True, 'pets': self._pets_in(E, L), 'dark': self._dark_in(E, L)})

    def api_vc_list(self, req):
        E = self.E(); L, D, B, S, PT = E.vc.vlist(req.q('f', 'todo'), req.q('folder', ''), req.q('order', 'path'), meta=True, ready_first=req.q('rf', '0') == '1', ln=req.q('ln', ''), kind=req.q('k', 'video'), q=req.q('q', ''), paths=True)
        E.fc_kick()                                                                 # 背景馬上先做這份清單還沒做的 16 格
        try:                                                                        # 🐾 背景自動看開著＋你在看某個資料夾：先看這個資料夾（V0.4.21）
            if L and req.q('folder', '') and E.cfg.get('pet_auto') and not E.pet.st.get('run') and time.time() - getattr(E.pet, 'fail_t', 0) > 86400 and len(L) <= 600:
                seen = {r[0] for r in E.db.q('SELECT fid FROM vc_pet WHERE dog>=0 OR face>=0')}; miss = [f for f in L if f not in seen]
                if len(miss) >= 3: E.pet.start(0, 'photo' if req.q('k', '') == 'photo' else 'video', only=miss)
        except Exception: pass
        kq = 'photo' if req.q('k', 'video') == 'photo' else 'video'                   # 只讀這一種（V0.2.61：以前連 43 萬張照片的路徑都讀）
        P = {}
        for fid, pth in zip(L, PT):                                                 # ⚡ 路徑 vlist 已經讀了、不用 os.path.dirname（43 萬張照片時快很多）（V0.3.89）
            k = max(pth.rfind('/'), pth.rfind('\\')); d = pth[:k] if k > 0 else pth[:k + 1]
            if d.endswith(':') or not d: d = pth[:k + 1]
            P[fid] = d
        DN = []; DI = {}; dix = []                                                   # ⏭ 每部在哪個資料夾（V0.1.67：跳到下一個資料夾）
        for i in L:
            d = P.get(i, '')
            if d not in DI: DI[d] = len(DN); DN.append(d)
            dix.append(DI[d])
        gm = req.q('g', ''); GN = []; GI = []; GP = []
        if gm and L:                                                                # 🧩 相關的排一起（V0.2.14）：同一組排在一起
            try:
                ix = {f: k for k, f in enumerate(L)}; L2, GN, GI, GP = E.vg.group(L, gm, req.q('order', ''))
                D = [D[ix[f]] for f in L2]; B = [B[ix[f]] for f in L2]; S = [S[ix[f]] for f in L2]; dix = [dix[ix[f]] for f in L2]; L = L2
            except Exception: E.log.err('🧩 分組'); GN = []; GI = []; GP = []
        return jresp({'ok': True, 'ids': L, 'dur': D, 'size': B, 'st': S, 'dn': DN, 'di': dix, 'gn': GN, 'gi': GI, 'gp': GP, 'tags': E.vc.tags_of(L), 'pets': self._pets_in(E, L), 'dark': self._dark_in(E, L), 'sus': self._sus_in(E, L, req.q('f', 'todo')), 'live': getattr(E.vc, 'live_n', 0) if req.q('k', 'video') != 'photo' else 0})

    def api_dpl(self, req):
        """🧭 重複檔用資料夾看（V0.2.16）：GET 分析（force=1 重算）、?plan=1&keep=&other= 預覽；POST {a:keep/merge/all/stop, keep, other}."""
        E = self.E()
        if req.method == 'POST':
            d = req.json(); a = d.get('a')
            if a in ('keep', 'merge'): return jresp(E.dpl.start(str(d.get('keep') or ''), str(d.get('other') or ''), a == 'merge'))
            if a == 'all': return jresp(E.dpl.start_all(d.get('only_copy', True) is not False))
            if a == 'stop': E.dpl.st['cancel'] = True; return jresp({'ok': True, 'message': '⏹ 停止中…'})
            if a == 'undo': return jresp(E.dpl.undo(str(d.get('key') or '')))
            return jresp({'ok': False, 'message': '不認得的動作'})
        if req.q('plan'):
            p = E.dpl.plan(req.q('keep'), req.q('other')); return jresp({k: v for k, v in p.items() if not k.startswith('_')})
        if req.q('st'): return jresp({'ok': True, 'st': E.dpl.status()})
        if req.q('hist'): return jresp({'ok': True, 'rows': E.dpl.history()})
        r = E.dpl.analyze(req.q('force') == '1'); return jresp(dict(r, st=E.dpl.status()))

    def api_wiz(self, req):
        """🚀 整理精靈：GET 每一步的狀況；POST {a: bad/dpl_all/dup_all/move/dpl_scan}."""
        E = self.E()
        if req.method == 'POST':
            a = req.json().get('a')
            if a == 'bad': ok = E.fc_quar_filter('bad'); return jresp({'ok': ok, 'message': '📦 損毀的開始搬到隔離區（背景）' if ok else '現在有別的整批搬移在做，等一下'})
            if a == 'dpl_all': return jresp(E.dpl.start_all())
            if a == 'dpl_scan': E.dpl.analyze(True); return jresp({'ok': True, 'message': '🧭 分析好了'})
            if a == 'dup_all': ok = E.fc_bulk_start(); return jresp({'ok': ok, 'message': '🔁 開始全部照建議處理（背景）' if ok else '現在有別的整批搬移在做，等一下'})
            if a == 'move': ok = E.vc.move_start(); return jresp({'ok': ok, 'message': '🚚 開始搬檔（背景）' if ok else '已經在搬了'})
            return jresp({'ok': False, 'message': '不認得的動作'})
        return jresp(E.wizard())

    def api_vc_prog(self, req):
        c = getattr(self, '_vprog_c', None)                                           # 快取 60 秒（V0.2.61）
        if c and time.time() - c[0] < 60: return jresp(c[1])
        E = self.E(); r = E.vg.progress()
        try: r = dict(r, pets=E.pet.todo_count())                                 # 🐾 還沒分、有貓狗的（V0.3.09）
        except Exception: pass
        try: r = dict(r, sug=(E.vc.hint_summary() or {}).get('n', 0))                  # 💡 可以照建議分的（背景算好的）（V0.3.46）
        except Exception: pass
        self._vprog_c = (time.time(), r); return jresp(r)

    def api_vg(self, req):
        """📦 資料夾包（V0.2.14）：GET 清單（show=todo/all/skip/done、q=）、?path= 一包的內容；POST {a:tag/untag/skip/unskip, path, cat, photos, tree, go}."""
        E = self.E()
        if req.method == 'POST':
            d = req.json(); a = d.get('a'); p = str(d.get('path') or '')
            if a == 'tag':
                r = E.vg.pack_tag(p, int(d.get('cat') or 0), d.get('photos', True) is not False, d.get('tree', True) is not False, bool(d.get('only_todo')))
                if r.get('ok') and d.get('go'):
                    r['message'] = r['message'].split('，按 🚚')[0]
                    if not r.get('ids'): pass
                    elif E.vc.move_start(r['ids']): r['message'] += '；🚚 開始搬這一包（背景）'
                    else: r['message'] += '；（已經在搬，等一下再按 🚚 搬）'
                r.pop('ids', None); return jresp(r)
            if a == 'tag_many':
                r = E.vg.pack_tag_many([str(x) for x in d.get('paths') or []], int(d.get('cat') or 0))
                if r.get('ok') and r.get('ids') and d.get('go'): r['message'] += '；🚚 開始搬這幾包（背景）' if E.vc.move_start(r['ids']) else '；（已經在搬，等一下再按 🚚 搬）'
                r.pop('ids', None); return jresp(r)
            if a == 'untag': return jresp(E.vg.pack_untag(p))
            if a in ('skip', 'unskip'): return jresp(E.vg.pack_skip(p, a == 'skip'))
            if a == 'mark': return jresp(E.vg.mark(p, int(d.get('on', 1))))
            if a == 'back': return jresp(E.vg.pack_back(str(d.get('name') or ''), int(d.get('cat') or 0)))
            return jresp({'ok': False, 'message': '不認得的動作'})
        if req.q('info'):                                                             # 整包分類前先告訴你多大（V0.2.50）
            p = req.q('info'); g = E.vg.pack_info(p)
            if not g:
                R = E.vg.pack_ids(p, ('video', 'photo')); g = {'path': p, 'name': os.path.basename(p), 'n': sum(1 for r in R if r[4] == 'video'), 'np': sum(1 for r in R if r[4] != 'video'), 'b': 0}
            return jresp({'ok': True, 'pack': g})
        if req.q('path'):
            p = req.q('path'); g = E.vg.pack_info(p); R = E.vg.pack_ids(p, ('video', 'photo'))
            C = {c['id']: c['name'] for c in E.vc.cats()}
            rows = [{'id': fid, 'name': os.path.basename(fp), 'sub': os.path.relpath(os.path.dirname(fp), p), 'cat': C.get(cat, '') if cat else '', 'moved': mv or 0,
                     'kind': k, 'dur': dur or 0} for fid, fp, cat, mv, k, dur in R[:3000]]
            try: dups = E.vg.pack_dups(p)
            except Exception: dups = None
            return jresp({'ok': True, 'pack': g, 'rows': rows, 'n': len(R), 'dups': dups})
        if req.q('show') == 'moved': return jresp({'ok': True, 'moved': E.vg.recent(), 'packs': [], 'total': 0})
        L = E.vg.packs(req.q('show', 'todo'), req.q('q', ''), req.q('o', ''))
        kc = E.db.one('SELECT dest FROM vc_cat WHERE name=?', ('已篩選',)); kd = (kc[0] if kc else '') or ''
        return jresp({'ok': True, 'packs': L[:int(req.q('n', '300') or 300)], 'total': len(L), 'keep_cat': '已篩選', 'keep_dest': kd})

    def api_vc_folders(self, req):
        return jresp({'ok': True, 'rows': self.E().vc.folders(req.q('k', 'video'))})

    def api_vc_thumb(self, req):
        E = self.E(); fid = int(req.q('id', '0') or 0); tw = int(req.q('w', '160') or 160)
        if req.q('p', '') == '1': tw = -abs(tw)                                     # 🐾 用最像貓狗那一格（V0.3.94）
        try: p = E.vc.thumb_cached(fid, tw)
        except Exception: p = None
        if not p and (fid, tw) in self.__dict__.get('_thfail', set()): return Resp(404, b'no preview', 'text/plain')
        if not p and req.q('wait', '') != '1':                                      # 還沒做：丟給背景做，馬上回（不佔住連線，按分類才不會卡）（V0.3.47）
            self._thumb_q(E, fid, tw); return Resp(503, b'making', 'text/plain', {'Retry-After': '2'})
        if not p:
            try: p = E.vc.thumb(fid, tw)
            except Exception: p = None
        if not p: return Resp(404, b'no preview', 'text/plain')
        return Resp(200, Path(p).read_bytes(), 'image/jpeg', {'Cache-Control': 'private, max-age=86400'})

    def _thumb_q(self, E, fid, tw, kind='vc'):
        key = (fid, tw) if kind == 'vc' else ('fc', fid, tw)
        with self.lock:
            q = self.__dict__.setdefault('_thq', {}); busy = self.__dict__.setdefault('_thbusy', set())
            if key in busy or key in q: return
            q[key] = time.time()
            while len(q) > 400: q.pop(next(iter(q)))
            if self.__dict__.get('_thn', 0) >= 3: return
            self._thn = self.__dict__.get('_thn', 0) + 1
        def work():
            try:
                while True:
                    with self.lock:
                        if not self._thq: self._thn -= 1; return
                        k = list(self._thq)[-1]; self._thq.pop(k); self._thbusy.add(k)          # 最新要的先做（你正在看的那幾格）
                    try: ok_ = E.vc.thumb(k[0], k[1]) if len(k) == 2 else E.fc_thumb(k[1], k[2])
                    except Exception: ok_ = None
                    with self.lock:
                        self._thbusy.discard(k)
                        if not ok_:
                            fs = self.__dict__.setdefault('_thfail', set()); fs.add(k)
                            if len(fs) > 20000: fs.clear()
            except Exception:
                with self.lock: self._thn = max(0, self._thn - 1)
        threading.Thread(target=work, name='ThumbQ', daemon=True).start()

    def api_vc_item(self, req):
        E = self.E(); fid = int(req.q('id', '0') or 0); it = E.vc.item(fid)
        if not it: return jresp({'ok': False, 'message': '找不到這部（可能被搬走了）'})
        try: E.vc.prefetch([int(x) for x in req.q('next', '').split(',') if x.strip().isdigit()])
        except Exception: pass
        g = E.vc.grid(fid, build=req.q('nb', '') != '1'); g = dict({k: v for k, v in g.items() if k != 'sheets'}, ns=len(g.get('sheets') or [])) if g.get('ok') else g
        try: it['pack'] = E.vg.pack_brief(it['path'])                              # 📦 這部在哪一包（V0.2.14）
        except Exception: it['pack'] = None
        try:
            pr = E.db.one('SELECT dog, cat, COALESCE(sc, top), sp, lum, lstd, mot, pc, face FROM vc_pet WHERE fid=?', (fid,)); it['faces'] = pr[8] if pr and pr[8] and pr[8] > 0 else 0; it['pet'] = [pr[0], pr[1]] if pr and pr[0] is not None and pr[0] >= 0 else None
            if it['pet'] and max(it['pet']) >= E.pet.th() and pr[7]: it['pc'] = pr[7]                      # 🐾 哪一格看到貓狗（V0.3.95）
            import fc_pets as pets
            try:
                if it.get('cat'):
                    c_ = getattr(E.vc, '_sus', None); sv = (c_[2] if c_ else E.vc.suspects()).get(fid)      # 用算好的就好（審片時不重算）
                    if sv: it['sus'] = sv[1]; it['sus_c'] = sv[0]                                         # 🧐 可能分錯的原因（V0.4.31）
            except Exception: pass
            if pr and pr[2] is not None and pr[2] >= 0 and (pr[3] is None or pr[3] < 0 or pr[3] >= pets.SCENE_P):   # 🔎 內容猜測（V0.3.73）
                k = E.pet.scene_of(pr[2]); it['scene'] = next((nm for kk, nm, S in pets.SCENES if kk == k), '') if k else ''; it['scene_k'] = k
            if pr and pr[4] is not None and 0 <= pr[4] < pets.DARK: it['scene'] = '🌑 很暗／全黑'; it['scene_k'] = 'dark'
            elif pr and pr[5] is not None and 0 <= pr[5] < pets.FLAT: it['scene'] = '⬜ 畫面幾乎沒東西'; it['scene_k'] = 'flat'
            elif pr and pr[6] is not None and 0 <= pr[6] < pets.STILL: it['scene'] = '🧱 畫面幾乎沒動'; it['scene_k'] = 'still'
        except Exception: it['pet'] = None
        return jresp({'ok': True, 'item': it, 'grid': g})

    def api_vc_rules(self, req):
        """📏 自己訂的分類規則（V0.2.89）：GET 列出；POST {a:add, w, cat}／{a:del, i}."""
        E = self.E()
        if req.method == 'POST':
            d = req.json(); R = list(E.cfg.get('vc_rules') or [])
            if d.get('a') == 'add':
                wd = str(d.get('w') or '').strip(); c = int(d.get('cat') or 0)
                if not wd or not c: return jresp({'ok': False, 'message': '要填字、選分類'})
                R = [r for r in R if str(r[0]).lower() != wd.lower()] + [[wd, c]]
            elif d.get('a') == 'del':
                i = int(d.get('i', -1))
                if 0 <= i < len(R): R.pop(i)
            E.cfg.set('vc_rules', R); E.log.w(f'📏 分類規則：{len(R)} 條')
        C = {c['id']: c['name'] for c in E.vc.cats()}
        return jresp({'ok': True, 'rules': [{'w': w_, 'cat': c, 'name': C.get(int(c), '（分類被刪了）')} for w_, c in (E.cfg.get('vc_rules') or [])]})

    def api_vc_cams(self, req):
        """📷 照相機一次分（V0.3.19）：GET 還沒分類的照相機各幾部；POST {cam, cat, k} 那台相機還沒分的全部分到那類."""
        E = self.E(); kind = 'photo' if (req.q('k', '') == 'photo' or (req.method == 'POST' and req.json().get('k') == 'photo')) else 'video'
        by = req.q('by', '') if req.method == 'GET' else str(req.json().get('by') or '')
        ck = (kind, by, tuple(E.db.one('SELECT COUNT(*), MAX(t) FROM vc_tag') or ()), (E.db.one("SELECT COUNT(*) FROM files WHERE state='' AND kind=?", (kind,)) or [0])[0])
        cc = self.__dict__.setdefault('_camc', {}).get(ck)                         # ⚡ 沒分新的就用上次算好的（30 萬張照片要 2 秒）（V0.3.97）
        if cc and time.time() - cc[0] < 600:
            C, ids = cc[1], cc[2]
            if req.method != 'POST': return jresp({'ok': True, 'rows': cc[3]})
        else: C = None
        if C is None: C, ids = self._cams_calc(E, kind, by)
        if req.method == 'POST':
            d = req.json(); cm = str(d.get('cam') or ''); cat = int(d.get('cat') or 0)
            if cm not in ids or not cat: return jresp({'ok': False, 'message': '沒有要分的'})
            r = E.vc.tag_many(ids[cm], cat, only_new=True); r['ids'] = ids[cm]; return jresp(r)
        rows = sorted(({'cam': k, 'n': v[0], 'b': v[1]} for k, v in C.items()), key=lambda x: -x['n'])[:60]
        if len(self._camc) > 4: self._camc.clear()
        self._camc[ck] = (time.time(), C, ids, rows)
        return jresp({'ok': True, 'rows': rows})

    def _cams_calc(self, E, kind, by):
        L = set(E.vc.vlist('todo', kind=kind)); C = {}; ids = {}
        for fid, mk, md, sz, pth in E.db.q(f"SELECT id, make, model, size, path FROM files WHERE state='' AND kind='{kind}'"):
            if fid not in L: continue
            cm = E.vc.name_pre(pth) if by == 'name' else (E.vc._cam(mk, md) or '（不知道相機）')       # 🔤 檔名開頭（V0.3.22）
            a = C.setdefault(cm, [0, 0]); a[0] += 1; a[1] += int(sz or 0); ids.setdefault(cm, []).append(fid)
        return C, ids

    def api_vc_learn(self, req):
        """🧠 學到的習慣（V0.3.25）：GET 列出；POST {a:ignore|unignore, w}."""
        E = self.E()
        if req.method == 'POST':
            d = req.json(); wd = str(d.get('w') or ''); IG = list(E.cfg.get('vc_learn_ignore') or [])
            if d.get('a') == 'ignore' and wd not in IG: IG.append(wd)
            if d.get('a') == 'unignore': IG = [x for x in IG if x != wd]
            E.cfg.set('vc_learn_ignore', IG)
        acc = []
        try:                                                                        # 📈 最近 500 次有建議時，你照著分的比例（每種線索）
            NM = {'folder': '同資料夾', 'time': '同一段時間', 'word': '學到的習慣', 'rule': '你的規則', 'mix': '🧮 綜合'}
            for k, n, h in E.db.q('SELECT kind, COUNT(*), SUM(hit) FROM (SELECT kind, hit FROM vc_hstat ORDER BY t DESC LIMIT 500) GROUP BY kind ORDER BY COUNT(*) DESC'):
                acc.append({'k': NM.get(k, k), 'n': n, 'p': round(100 * (h or 0) / max(1, n))})
        except Exception: pass
        return jresp({'ok': True, 'rows': E.vc.learned(), 'acc': acc})

    def api_vc_pet_model(self, req):
        """🐾 自己上傳辨識模型（下載不了的時候；V0.3.56）：POST 原始檔案內容."""
        E = self.E(); b = req.body or b''
        if req.method != 'POST' or len(b) < 5_000_000 or b[:1] != b'\x08': return jresp({'ok': False, 'message': '檔案不對（要 mobilenetv2-7.onnx，約 14 MB）'})
        p = E.pet.adir() / pets_MODEL(); tmp = p.with_suffix('.part'); tmp.write_bytes(b); os.replace(tmp, p); E.log.w(f'🐾 收到上傳的辨識模型：{len(b):,} bytes')
        return jresp({'ok': True, 'message': '🐾 模型放好了，可以按「試 20 部」'})

    def api_vc_recent(self, req):
        """📜 電腦記的最近分類（換手機、重新整理後也看得到；V0.3.60）."""
        E = self.E(); n = max(10, min(500, int(req.q('n', '200') or 200)))
        C = {c['id']: c['name'] for c in E.vc.cats()}
        R = [{'id': r[0], 'cat': r[1], 'name': C.get(r[1], '?'), 't': r[2], 'moved': r[3], 'auto': r[4], 'file': os.path.basename(r[5] or '')}
             for r in E.db.q('SELECT t.fid, t.cat, t.t, t.moved, COALESCE(t.auto,0), f.path FROM vc_tag t LEFT JOIN files f ON f.id=t.fid WHERE COALESCE(t.auto,0)=0 ORDER BY t.t DESC LIMIT ?', (n,))]
        return jresp({'ok': True, 'rows': R})

    def api_diag(self, req):
        """🩺 自我檢查（V0.3.63）：FFmpeg、Windows ML、人臉偵測、硬碟空間…，有問題截圖給開發者看."""
        E = self.E(); R = []
        def add(k, ok, msg): R.append({'k': k, 'ok': ok, 'msg': str(msg)[-600:]})
        try: add('版本', True, f"V{E.version}　Python {platform.python_version()}　{platform.platform()}")
        except Exception as ex: add('版本', None, ex)
        try:
            ff, fp = E.ff(); add('FFmpeg', bool(ff), ff or '找不到 FFmpeg（16 格、縮圖都要它）')
            if ff:
                r_ = subprocess.run([ff, '-hide_banner', '-version'], capture_output=True, timeout=20, creationflags=0x08000000 if os.name == 'nt' else 0, stdin=subprocess.DEVNULL); rc, o, e = r_.returncode, r_.stdout.decode('utf-8', 'replace'), r_.stderr.decode('utf-8', 'replace'); add('FFmpeg 版本', rc == 0, (o or e).splitlines()[0] if (o or e) else rc)
        except Exception as ex: add('FFmpeg', False, ex)
        try:
            dbp = Path(E.data) / 'app.sqlite3'; add('資料庫', True, f"{dbp.stat().st_size / 1e6:,.0f} MB" if dbp.exists() else '？')
        except Exception as ex: add('資料庫', None, ex)
        try:
            for r in (E.fc_list('roots') or [])[:8]:
                du = shutil.disk_usage(r); add(f'硬碟空間 {r}', du.free > 5e9, f"剩 {du.free / 1e9:,.1f} GB／共 {du.total / 1e9:,.0f} GB")
        except Exception as ex: add('硬碟空間', None, ex)
        try: add('🐾 辨識模型', bool(E.pet.model()), str(E.pet.model() or f'還沒有（第一次「試 20 部」會自動下載；放這裡：{E.pet.adir()}）'))
        except Exception as ex: add('🐾 辨識模型', None, ex)
        if req.q('deep') == '1':
            if os.name != 'nt': add('Windows ML／人臉', None, '這台不是 Windows，不能測')
            else:
                exe = os.path.join(os.environ.get('SystemRoot', r'C:\\Windows'), 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
                tests = (('PowerShell', '$PSVersionTable.PSVersion.ToString()'),
                         ('Windows ML', "$null=[Windows.AI.MachineLearning.LearningModel,Windows.AI.MachineLearning,ContentType=WindowsRuntime]; 'OK 可以用'"),
                         ('人臉偵測', "Add-Type -AssemblyName System.Runtime.WindowsRuntime; $null=[Windows.Media.FaceAnalysis.FaceDetector,Windows.Media.FaceAnalysis,ContentType=WindowsRuntime]; if([Windows.Media.FaceAnalysis.FaceDetector]::IsSupported){'OK 可以用'}else{'這台不支援'}"))
                for k, cmd in tests:
                    try:
                        r = subprocess.run([exe, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', cmd], capture_output=True, timeout=60, creationflags=0x08000000, stdin=subprocess.DEVNULL)
                        o = r.stdout.decode('utf-8', 'replace').strip(); e = r.stderr.decode('mbcs' if os.name == 'nt' else 'utf-8', 'replace').strip()
                        add(k, r.returncode == 0 and bool(o) and not e, o or e or f'結束碼 {r.returncode}')
                    except Exception as ex: add(k, False, ex)
                try:                                                                 # 🔬 真的跑一次：灰色小圖丟給 pet.ps1／人臉（V0.4.25）
                    import fc_pets as _pm
                    if not E.pet.model():
                        ok_, er_ = E.pet.fetch()
                        add('🐾 下載辨識模型', bool(ok_), '下載好了' if ok_ else er_)
                    if E.pet.model():
                        t0 = time.time(); R_, er = E.pet._run_ps(bytes([128]) * _pm.ONE, '_diag')
                        add('🐾 實際跑一次貓狗辨識', bool(R_), (f'OK（{time.time() - t0:.1f} 秒）：狗 {R_[0][0]:.2f}、貓 {R_[0][1]:.2f}' if R_ else (er or '沒有結果')))
                    else: add('🐾 實際跑一次貓狗辨識', None, '還沒有辨識模型（按一次「試 20 部」會自動下載）')
                    t0 = time.time(); R_, er = E.pet._run_face(bytes([128]) * _pm.FONE, '_diag')
                    add('👤 實際跑一次人臉偵測', bool(R_), (f'OK（{time.time() - t0:.1f} 秒）' if R_ else (er or '沒有結果')))
                except Exception as ex: add('🐾 實際跑一次', False, ex)
                try:
                    st = E.pet.status(); add('🐾 上次找貓狗', not st.get('err'), (st.get('msg') or '') + ('\n' + st['err'] if st.get('err') else ''))
                except Exception: pass
        return jresp({'ok': True, 'rows': R})

    def _sus_in(self, E, L, f):
        """🧐 分好還沒搬的清單裡，可能分錯的（小格子上標一下）（V0.4.40）."""
        if not (f in ('wait', 'chk', 'all') or (str(f).startswith('c') and str(f)[1:].isdigit())): return []
        try: S = E.vc.suspects(); return [x for x in L if x in S] if S else []
        except Exception: return []

    def _dark_in(self, E, L):
        """🌑 全黑／沒東西／沒動的（小格子上標一下）（V0.3.85）."""
        try:
            P = E.pet.scene_ids('dark') | E.pet.scene_ids('flat') | E.pet.scene_ids('still')
            return [f for f in L if f in P] if P else []
        except Exception: return []

    def _pets_in(self, E, L):
        try: P = E.pet.pet_ids(); return [f for f in L if f in P] if P else []
        except Exception: return []

    def api_vc_pet(self, req):
        """🐾 找有貓狗的影片（V0.2.93）：GET 狀態；POST {a:start|stop|tag(cat, kind)|th(v)}."""
        E = self.E()
        if req.method == 'POST':
            d = req.json(); a = d.get('a')
            if a == 'start': ok = E.pet.start(int(d.get('limit') or 0), 'photo' if d.get('k') == 'photo' else 'video', only=[int(x) for x in d.get('ids') or []] or None); return jresp({'ok': ok, 'message': '🐾 開始找貓狗（背景做，你審片時會放慢）' if ok else '已經在找了'})
            if a == 'stop': E.pet.st['cancel'] = True; return jresp({'ok': True, 'message': '⏹ 停止中…'})
            if a == 'auto': E.cfg.set('pet_auto', bool(d.get('on'))); return jresp({'ok': True, 'message': '🐾 之後新做好 16 格的會自動看' if d.get('on') else '🐾 不自動看了', 'st': E.pet.status()})
            if a == 'reset':
                if E.pet.st.get('run'): return jresp({'ok': False, 'message': '正在找，先停下來'})
                E.db.x('DELETE FROM vc_pet'); E.pet.st.clear(); E.pet._scc = {}
                try:                                                                 # 🐾 那格的小縮圖也清掉（重新看之後格子可能不一樣）（V0.4.08；程式自己的快取，不是你的檔案）
                    for f_ in (Path(E.data) / 'vthumb').glob('*/*_p*.jpg'): f_.unlink()
                except Exception: pass
                return jresp({'ok': True, 'message': '🔄 清掉了，按「開始找」重新看'})
            if a == 'nopet':                                                     # 🐾 ⚡ 快速審：這幾部不是貓狗（V0.6.00）
                n = E.pet.nopet(d.get('ids') or [], d.get('on', True) is not False); return jresp({'ok': True, 'n': n, 'message': f'🚫 {n} 部標成「不是貓狗」，之後不會再出現在 🐾 清單'})
            if a == 'nopet_clear':
                E.db.x('UPDATE vc_pet SET nopet=NULL WHERE nopet=1'); E.pet._scc = {}; return jresp({'ok': True, 'message': '🔄 「不是貓狗」的標記都清掉了'})
            if a == 'th':
                E.cfg.set('pet_th', max(0.05, min(0.95, float(d.get('v') or 0.35)))); return jresp({'ok': True, 'message': '🐾 靈敏度改好了', 'st': E.pet.status()})
            if a == 'tag':
                cat = int(d.get('cat') or 0); kd = str(d.get('kind') or ''); ids = E.vc.vlist('pet_' + kd if kd.startswith('s_') else {'dog': 'pet_dog', 'cat': 'pet_cat'}.get(kd, 'pet'), kind='photo' if d.get('k') == 'photo' else 'video')
                if not cat or not ids: return jresp({'ok': False, 'message': '沒有要分的（先按「開始找」）'})
                r = E.vc.tag_many(ids, cat, only_new=True); r['ids'] = ids; E.pet._scc = {}; return jresp(r)
            return jresp({'ok': False, 'message': '不認得的動作'})
        return jresp({'ok': True, 'st': E.pet.status('photo' if req.q('k', '') == 'photo' else 'video')})

    def api_vc_cells(self, req):
        """🖱 小格子滑過去預覽（V0.2.71）：只回已經做好的 16 格位置，不會現在做."""
        try:
            E = self.E(); fid = int(req.q('id', '0') or 0); f = E.fc_file(fid) or {}
            nm = os.path.basename(f.get('path') or '') + ('\n' + os.path.dirname(f.get('path') or '') if f.get('path') else '')
            g = E.vc.grid(fid, build=False)
            if not g.get('ok') or g.get('photo'): return jresp({'ok': False, 'name': nm})
            return jresp({'ok': True, 'cols': g['cols'], 'rows': g['rows'], 'cells': g['cells'], 'name': nm})
        except Exception: return jresp({'ok': False})

    def api_vc_img(self, req):
        E = self.E()
        try:
            g = E.vc.grid(int(req.q('id', '0') or 0), build=False); p = (g.get('sheets') or [])[int(req.q('s', '0') or 0)]
            return Resp(200, Path(p).read_bytes(), 'image/jpeg', {'Cache-Control': 'private, max-age=3600'})
        except Exception: return Resp(404, b'no image', 'text/plain')

    def api_vc_tag(self, req):
        d = req.json(); E = self.E(); fid = int(d.get('id') or 0); r = E.vc.tag(fid, int(d.get('cat') or 0))
        try:                                                                        # 📈 💡 建議準不準（V0.4.43）：有建議時記下你有沒有照著分
            hc, hk = int(d.get('h') or 0), str(d.get('hk') or '')[:8]
            if hc and int(d.get('cat') or 0) and r.get('ok'):
                E.db.x('CREATE TABLE IF NOT EXISTS vc_hstat(t REAL, kind TEXT, hit INTEGER)')
                E.db.x('INSERT INTO vc_hstat(t, kind, hit) VALUES(?,?,?)', (time.time(), hk or 'folder', 1 if hc == int(d.get('cat') or 0) else 0))
        except Exception: pass
        try:                                                                        # 👯 這部有相似的版本（重新壓縮、轉檔過的）還沒分（V0.3.39）
            if r.get('ok') and int(d.get('cat') or 0) and E.vc.del_cat() != int(d.get('cat') or 0): r['sim'] = len(self._sim_sibs(E, fid))
        except Exception: pass
        return jresp(r)

    def _sim_sibs(self, E, fid):
        g = E.db.one('SELECT gid FROM simv_grp WHERE fid=?', (int(fid),))
        if not g: return []
        T = {r[0] for r in E.db.q('SELECT fid FROM vc_tag')}
        return [r[0] for r in E.db.q('SELECT fid FROM simv_grp WHERE gid=?', (g[0],)) if r[0] != int(fid) and r[0] not in T]

    def api_vc_simdel(self, req):
        """👯 相似版本（不是一模一樣、但內容一樣）標成 Delete（V0.3.39）."""
        E = self.E(); fid = int(req.json().get('id') or 0); did = E.vc.del_cat()
        if not did: return jresp({'ok': False, 'message': '沒有叫「Delete」的分類（先新增一個）'})
        S = self._sim_sibs(E, fid)
        if not S: return jresp({'ok': False, 'message': '沒有還沒分的相似版本'})
        r = E.vc.tag_many(S, did, only_new=True); r['ids'] = S; r['message'] = f'🗑 {len(S)} 個相似版本標成 Delete（只留你分的這部）'; return jresp(r)

    def api_vc_tag_many(self, req):
        d = req.json(); E = self.E(); E.log.w(f'📱 手機：整批分類 {len(d.get("ids") or [])} 部')
        if d.get('hint'): return jresp(E.vc.hint_many(d.get('ids') or [], dry=bool(d.get('dry'))))
        if d.get('folder'): return jresp(E.vc.tag_folder(d['folder'], int(d.get('cat') or 0), d.get('kind', '')))
        return jresp(E.vc.tag_many(d.get('ids') or [], int(d.get('cat') or 0), d.get('only_new', True) is not False))

    def api_vc_cat(self, req):
        """a＝add（name, dest）／edit（id, name, dest）／del（id）／move（id, d）."""
        E = self.E(); d = req.json(); a = d.get('a'); E.log.w(f'📱 手機：影片分類 {a} {d.get("name") or d.get("id") or ""}')
        if a == 'add': return jresp(E.vc.cat_add(d.get('name', ''), d.get('dest', '')))
        if a == 'edit': return jresp(E.vc.cat_edit(int(d['id']), d.get('name'), d.get('dest')))
        if a == 'del': return jresp(E.vc.cat_del(int(d['id'])))
        if a == 'move': return jresp(E.vc.cat_move(int(d['id']), int(d.get('d') or 0)))
        if a == 'order': return jresp(E.vc.cat_order(d.get('ids') or []))
        if a == 'merge': return jresp(E.vc.cat_merge(int(d['id']), int(d.get('to') or 0)))
        return jresp({'ok': False, 'message': '不認得的動作'}, 400)

    def api_vc_plan(self, req):
        E = self.E(); return jresp({'ok': True, 'move': E.vc.move_plan(), 'clean': E.vc.clean_plan()})

    def api_vc_run(self, req):
        """a＝move（開始搬檔）／clean（處理有問題的影片）／stop."""
        E = self.E(); a = req.json().get('a'); E.log.w(f'📱 手機：影片分類 {a}')
        if a == 'move':
            cs = {int(x) for x in (req.json().get('cats') or [])}; only = None             # 只搬勾的分類（V0.2.90）
            if cs:
                only = [r[0] for r in E.db.q('SELECT fid, cat FROM vc_tag WHERE moved=0') if r[1] in cs]
                if not only: return jresp({'ok': False, 'message': '勾的分類沒有要搬的'})
            ok = E.vc.move_start(only); return jresp({'ok': ok, 'message': ('🚚 開始搬檔（背景做）' + (f'：只搬勾的 {len(cs)} 類、{len(only):,} 部' if cs else '')) if ok else '已經在搬了'})
        if a == 'clean': ok = E.vc.clean_start(); return jresp({'ok': ok, 'message': '🧹 開始處理（背景做）' if ok else '已經在搬了'})
        if a == 'stop': E.vc.mv['cancel'] = True; return jresp({'ok': True, 'message': '停止中…'})
        return jresp({'ok': False, 'message': '不認得的動作'}, 400)

    # ---- 🧹 雜物清理
    def api_junk(self, req):
        return jresp(self.E().junk_view(req.q('k', ''), 1500))

    def api_junk_run(self, req):
        d = req.json(); E = self.E(); E.log.w(f'📱 手機：雜物清理 {d.get("k")} {len(d.get("ids") or [])} 個')
        return jresp(E.junk_quar(d.get('k', ''), [int(x) for x in (d.get('ids') or [])]))

    # ---- 🖼 相似照片
    def api_sim(self, req):
        E = self.E(); S = {'video': E.simv, 'burst': E.burst}.get(req.q('k', ''), E.sim)
        return jresp(S.groups(int(req.q('o', '0') or 0), int(req.q('n', '20') or 20)))

    def api_sim_run(self, req):
        """a＝start（level）／stop／quar（gid 或 fids）／skip（gid）／all."""
        E = self.E(); d = req.json(); a = d.get('a'); S = {'video': E.simv, 'burst': E.burst}.get(d.get('k'), E.sim); E.log.w(f'📱 手機：{S.NAME} {a} {d.get("gid") or ""}')
        if a == 'start': return jresp(S.start(d.get('level')))
        if a == 'stop': S.st['cancel'] = True; return jresp({'ok': True, 'message': '停止中…'})
        if a == 'quar': return jresp(S.quar(d.get('gid'), d.get('fids')))
        if a == 'skip': return jresp(S.not_similar(d.get('gid')))
        if a == 'all': return jresp(S.quar_all())
        return jresp({'ok': False, 'message': '不認得的動作'}, 400)

    # ---- 📅 依日期整理
    def api_org(self, req):
        """POST a＝plan（src, dest, pattern, kinds, mtime, unknown）／run／stop；GET＝進度."""
        E = self.E()
        if req.method == 'POST':
            d = req.json(); a = d.get('a'); E.log.w(f'📱 手機：依日期整理 {a}')
            if a == 'plan':
                try: return jresp(E.org.plan(d.get('src', ''), d.get('dest', ''), d.get('pattern', 'ym'), d.get('kinds', 'both'), bool(d.get('mtime')), d.get('unknown', 'skip'), bool(d.get('cam'))))
                except Exception as ex: return jresp({'ok': False, 'message': str(ex)})
            if a == 'run': return jresp(E.org.run())
            if a == 'stop': E.org.st['cancel'] = True; return jresp({'ok': True, 'message': '停止中…'})
            if a == 'srcs': return jresp(E.org.sources())
            if a == 'plan_ren':                                                                   # 📝 依日期改檔名（V0.1.39）
                try: return jresp(E.org.plan_rename(d.get('src', ''), d.get('fmt', 'dash'), bool(d.get('keep_old')), d.get('kinds', 'photo')))
                except Exception as ex: return jresp({'ok': False, 'message': str(ex)})                                       # 🏷 依來源整理（V0.1.37）
            if a == 'plan_src':
                try: return jresp(E.org.plan_src(d.get('srcs') or [], d.get('dest', ''), d.get('keep_dir', True) is not False))
                except Exception as ex: return jresp({'ok': False, 'message': str(ex)})
        import fc_org as _org
        S = E.org.st; return jresp({'ok': True, 'st': {k: v for k, v in S.items() if k != 'err'}, 'patterns': {k: v[0] for k, v in _org.PATTERNS.items()}, 'roots': E.fc_list('roots')})

    # ---- 🗓 那年今天＋時間軸
    def api_tl(self, req):
        E = self.E(); y = req.q('y', '')
        if req.q('day', ''): return jresp(E.tl.day(req.q('day')))
        if y and req.q('heat', ''): return jresp({'ok': True, 'y': y, 'days': E.tl.days(y)})
        if not y: return jresp({'ok': True, 'years': E.tl.years()})
        return jresp(E.tl.month(y, req.q('m', '1'), int(req.q('o', '0') or 0), 60, req.q('k', '')))

    # ---- 📜 操作紀錄（V0.1.56）
    # ---- 💾 設定匯出／匯入（V0.1.66）
    def api_cfg_export(self, req):
        import fc_cfgio as cfgio
        b = json.dumps(cfgio.export(self.E()), ensure_ascii=False, indent=1).encode('utf-8')
        return Resp(200, b, 'application/json; charset=utf-8', {'Content-Disposition': "attachment; filename*=UTF-8''" + urllib.parse.quote(f'FileCompare_設定_{time.strftime("%Y%m%d")}.json')})

    def api_cfg_import(self, req):
        import fc_cfgio as cfgio
        try: d = json.loads((req.body or b'{}').decode('utf-8'))
        except Exception: return jresp({'ok': False, 'message': '讀不懂這個檔（要選 FileCompare_設定_….json）'})
        return jresp(cfgio.import_(self.E(), d))

    def api_mtfix(self, req):                                                       # 🕒 修正修改日期（V0.1.88）
        E = self.E()
        if req.method == 'POST':
            d = req.json(); a = d.get('a')
            if a == 'run': return jresp(E.mtf.start(d.get('kinds', 'both'), d.get('days', 1)))
            if a == 'undo': return jresp(E.mtf.undo())
        return jresp(E.mtf.plan(req.q('kinds', 'both'), float(req.q('days', '1') or 1)))

    def api_hist(self, req):                                                        # 📉 整理進度（V0.1.63）
        return jresp(self.E().hist(int(req.q('d', '60') or 60)))

    def api_cams(self, req):                                                        # 📱 用過的相機／手機（V0.2.04）
        E = self.E()
        R = [{'make': r[0] or '', 'model': r[1] or '', 'n': r[2], 'v': r[3], 'b': r[4], 't0': r[5] or 0, 't1': r[6] or 0} for r in E.db.q(
            "SELECT make, model, COUNT(*), SUM(kind='video'), SUM(size), MIN(NULLIF(taken,0)), MAX(taken) FROM files WHERE state='' AND kind IN ('photo','video') "
            "AND (make!='' OR model!='') GROUP BY make, model HAVING COUNT(*)>=3 ORDER BY MIN(NULLIF(taken,0))")]
        return jresp({'ok': True, 'rows': R})

    def api_random(self, req):                                                      # 🎲 隨機回憶（V0.1.72）
        E = self.E(); n = max(1, min(40, int(req.q('n', '12') or 12)))
        mx = (E.db.one('SELECT MAX(id) FROM files') or [0])[0] or 0; out = []; seen = set()
        for _ in range(6):                                                          # 隨機挑 id 附近的（比 ORDER BY RANDOM() 快很多）
            ids = [1 + int.from_bytes(os.urandom(4), 'little') % mx for _ in range(n * 3)] if mx else []  # 不用 random：舊版啟動器沒打包
            for r in E.db.q(f"SELECT id, path, kind, size, taken, dur FROM files WHERE state='' AND kind IN ('photo','video') AND date_src IN ('exif','video','name') AND src IN ('camera','') AND id IN ({','.join('?' * len(ids))})", ids) if ids else []:
                if r['id'] not in seen: seen.add(r['id']); out.append(dict(r))
            if len(out) >= n: break
        out.sort(key=lambda r: r['taken'] or 0); return jresp({'ok': True, 'rows': out[:n]})

    def api_ops(self, req):
        return jresp(self.E().ops(req.q('k', ''), req.q('q', ''), int(req.q('o', '0') or 0)))

    # ---- 🔔 做完通知（V0.1.55）：t 之後做完的工作（手機每 20 秒問一次）
    def api_done_since(self, req):
        try: t = float(req.q('t', '0') or 0)
        except ValueError: t = 0
        L = [{'title': x.get('title'), 'state': x.get('state'), 'msg': x.get('msg'), 't1': x.get('t1')} for x in self.E().tasks_list()
             if x.get('t1') and x['t1'] > t and x.get('state') in ('done', 'fail') and (x['t1'] - (x.get('t0') or x['t1'])) >= 20]   # 只通知做超過 20 秒的
        return jresp({'ok': True, 'now': time.time(), 'rows': L[-10:]})

    # ---- 📂 瀏覽資料夾（V0.1.51）
    def api_browse(self, req):
        return jresp(self.E().brw.ls(req.q('p', ''), int(req.q('o', '0') or 0)))

    # ---- 🧳 活動（V0.1.48）
    def api_events(self, req):
        E = self.E()
        if req.method == 'POST':
            d = req.json()
            if d.get('a') == 'plan': return jresp(E.evt.plan(d.get('key', ''), d.get('label', ''), d.get('dest', '')))
            if d.get('a') == 'run': E.evt.c.clear(); return jresp(E.org.run())
        if req.q('items', ''): return jresp({'ok': True, 'rows': E.evt.items(req.q('items'))})
        return jresp(E.evt.list(float(req.q('gap', '6') or 6), int(req.q('min', '15') or 15), req.q('f', '') == '1'))

    # ---- ⭐ 最愛（V0.1.43）
    def api_fav(self, req):
        E = self.E()
        if req.method == 'POST': d = req.json(); return jresp(E.fav_set(int(d.get('id') or 0), bool(d.get('on'))))
        if req.q('id', ''): return jresp({'ok': True, 'on': E.fav_get(int(req.q('id')))})
        return jresp(E.favs(int(req.q('o', '0') or 0), 60, req.q('k', '')))

    # ---- ▶ 在手機上播影片（V0.1.42）
    MIME = {'.mp4': 'video/mp4', '.m4v': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm', '.mkv': 'video/x-matroska', '.3gp': 'video/3gpp',
            '.avi': 'video/x-msvideo', '.ts': 'video/mp2t', '.mts': 'video/mp2t', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp', '.heic': 'image/heic'}

    def api_play(self, req):
        E = self.E()
        try: f = E.fc_file(int(req.q('id', '0') or 0))
        except Exception: f = None
        if not f: return Resp(404, '找不到這個檔'.encode('utf-8'), 'text/plain; charset=utf-8')
        import fc_fcore as fcore
        p = fcore.lp(f['path'])
        if not os.path.exists(p): return Resp(404, '檔案不見了'.encode('utf-8'), 'text/plain; charset=utf-8')
        r = FileResp(p, self.MIME.get(os.path.splitext(p)[1].lower(), 'application/octet-stream'), req.headers.get('range'))
        if req.q('dl', ''): r.headers['Content-Disposition'] = "attachment; filename*=UTF-8''" + urllib.parse.quote(os.path.basename(p))      # ⬇ 下載原檔（V0.1.52）
        return r

    def api_finfo(self, req):
        """ℹ 看大圖時的檔案資訊（V0.1.52）."""
        E = self.E(); f = E.fc_file(int(req.q('id', '0') or 0))
        if not f: return jresp({'ok': False, 'message': '找不到'})
        k = ('id', 'path', 'size', 'kind', 'taken', 'date_src', 'mtime', 'w', 'h', 'dur', 'make', 'model', 'lat', 'lon', 'src', 'health', 'fav', 'vcodec', 'state')
        return jresp({'ok': True, 'f': {x: f.get(x) for x in k}, 'src_nm': E.SRC_NM.get(f.get('src') or '', '')})

    # ---- 💾 備份檢查（V0.1.38）
    def api_backup(self, req):
        return jresp(self.E().bak.check(req.q('f', '') == '1'))

    # ---- 🧰 工具頁的數字徽章（V0.1.36）
    def api_badges(self, req):
        E = self.E(); now = time.time(); c = getattr(self, '_badge_c', None)
        if c and now - c[0] < 300: return jresp(c[1])                                  # 5 分鐘（V0.2.61：很重）
        out = {'ok': True}
        try: out['sim'] = E.sim.info().get('groups') or 0; out['simv'] = E.simv.info().get('groups') or 0; out['burst'] = E.burst.info().get('groups') or 0
        except Exception: pass
        try: J = E.junk_view(); out['junk'] = sum(v[0] for k, v in (J.get('counts') or {}).items() if k != 'big')
        except Exception: pass
        try: out['slim'] = E.slim.candidates(200, 1).get('save') or 0
        except Exception: pass
        try: out['fav'] = (E.db.one("SELECT COUNT(*) FROM files WHERE state='' AND fav=1") or [0])[0]; x = E.evt.c.get((6, 15)); out['evt'] = x[1]['n'] if x else 0
        except Exception: pass
        try: out['geo'] = E.geo.summary().get('n') or 0
        except Exception: pass
        try: out['ddir'] = len((E.ddir.c[1] or {}).get('pairs') or []) if getattr(E.ddir, 'c', None) else 0                # 算過才顯示（不在這裡算）
        except Exception: pass
        try:                                                                          # 📦 還沒審的包、🧭 資料夾對（算過才顯示，V0.2.54）
            pc = E.vg._cache[1]
            if pc is None: E.vg.warm()
            else: out['pk'] = sum(1 for g in pc.values() if g['todo'])
            dc = getattr(E.dpl, 'c', None)
            if dc: out['dpl'] = len(dc[1].get('pairs') or [])
        except Exception: pass
        self._badge_c = (now, out); return jresp(out)

    # ---- 💡 建議你做（V0.1.35）
    def api_advice(self, req):
        return jresp(self.E().adv.get(req.q('f', '') == '1'))

    # ---- 🗜 影片瘦身（V0.1.34）
    def api_slim(self, req):
        return jresp(self.E().slim.candidates(int(req.q('mb', '200') or 200), which=req.q('w', 'all') if req.q('w', 'all') in ('all', 'tagged', 'moved', 'wait', 'untagged') else 'all'))

    def api_slim_run(self, req):
        E = self.E(); d = req.json(); a = d.get('a'); E.log.w(f'📱 手機：影片瘦身 {a} {len(d.get("ids") or [])}')
        if a == 'start': return jresp(E.slim.start(d.get('ids') or [], d.get('q')))
        if a == 'stop': E.slim.st['cancel'] = True; return jresp({'ok': True, 'message': '停止中…（這部轉完的部分會丟掉，原檔不動）'})
        if a == 'test': return jresp(E.slim.test(int(d.get('id') or 0)))
        if a == 'test_stop': E.slim.tst['cancel'] = True; return jresp({'ok': True, 'message': '停止試轉'})
        if a == 'done': return jresp(E.slim.done_list(d.get('f') or 'all', d.get('q') or ''))
        if a == 'seen': return jresp(E.slim.seen(d.get('ids') or []))
        if a == 'revert': return jresp(E.slim.revert(d.get('ids') or []))
        if a == 'cfg':
            for k, lo, hi in (('target', 0.95, 0.995), ('floor', 0.90, 0.995)):
                if d.get(k) is not None: E.cfg.set('slim_' + k, min(hi, max(lo, float(d[k]))))
            return jresp({'ok': True, 'message': '設定好了', 'cfg': E.slim.cfg()})
        return jresp({'ok': False, 'message': '不認得的動作'}, 400)

    # ---- 📄 匯出報告（V0.1.31）：沒參數＝做一份新的；list＝以前做的；f＝打開某一份
    def api_report(self, req):
        E = self.E(); d = E.data / 'reports'
        if req.q('list', ''):
            L = sorted(d.glob('FileCompare_報告_*.html'), reverse=True) if d.exists() else []
            return jresp({'ok': True, 'rows': [{'name': p.name, 'size': p.stat().st_size, 't': p.stat().st_mtime} for p in L]})
        f = req.q('f', '')
        if f:
            p = d / os.path.basename(f)
            if not p.name.startswith('FileCompare_報告_') or not p.exists(): return Resp(404, '找不到這份報告'.encode('utf-8'), 'text/plain; charset=utf-8')
        else:
            E.log.w('📱 手機：匯出報告'); p = Path(report.build(E)[0])
        return Resp(200, p.read_bytes(), 'text/html; charset=utf-8', {'Cache-Control': 'no-store'})

    # ---- 🗺 照片地圖（V0.1.30）
    def api_geo(self, req):
        E = self.E(); k = req.q('k', '')
        y = req.q('y', '')
        if req.q('gy', '') != '': return jresp(E.geo.cell(int(req.q('z', '9')), int(req.q('gy')), int(req.q('gx')), int(req.q('o', '0') or 0), 60, k, y))
        return jresp({'ok': True, 'sum': E.geo.summary(), 'cl': E.geo.clusters(int(req.q('z', '3') or 3), k, y), 'years': E.geo.years()})

    def api_otd(self, req):
        return jresp(dict(self.E().tl.on_this_day(), ok=True))

    # ---- 📁 重複資料夾
    def api_ddir(self, req):
        E = self.E()
        if req.method == 'POST':
            d = req.json(); E.log.w(f'📱 手機：重複資料夾 保留 {d.get("keep")} 搬 {d.get("other")}')
            return jresp(E.ddir.keep(d.get('keep', ''), d.get('other', '')))
        r = dict(E.ddir.pairs(force=req.q('f', '') == '1')); r['st'] = dict(E.ddir.st); return jresp(r)

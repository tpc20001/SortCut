"""HotZone FM — web server. The desktop window and the phone / remote browser (LAN, Tailscale) use the same page
and the same API, so everything that can be done on the computer can be done remotely.

Security: every API call needs a session cookie. The desktop window gets one through a one-time local key;
remote browsers log in with the web password (no password set = remote access refused). Writes also need the
X-HZ header (a page on another site cannot send it), and wrong passwords lock the address for 5 minutes.
"""
from __future__ import annotations

import gzip
import hashlib
import hmac
import json
import mimetypes
import os
import uuid
import re
import secrets
import shutil
import socket
import threading
import time
import traceback
import urllib.parse
import zipfile
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from hz_common import ROOT, APP_DIR, APP_NAME, APP_VERSION, IS_WIN, DATA_DIR, LOCAL_TOKEN_FILE, norm, json_safe, atomic_write_json, read_json, fmt_size, unique_name
import hz_win as W
import hz_fileops as F

SESS_FILE = DATA_DIR / 'sessions.json'
STATIC = {'/': 'ui.html', '/index.html': 'ui.html', '/ui.css': 'ui.css', '/icon.svg': 'icon.svg',
          '/manifest.webmanifest': 'hz_manifest.json', '/sw.js': 'sw.js'}
PUBLIC_API = {'/api/ping', '/api/login', '/api/me'}


def local_token(rotate=False):
    """The key the desktop window logs in with (only accepted from this computer). A new one at every engine start, so
    an old one left in a browser history is worthless."""
    if not rotate:
        try:
            t = LOCAL_TOKEN_FILE.read_text(encoding='utf-8').strip()
            if re.fullmatch(r'[A-Za-z0-9_-]{20,}', t): return t
        except Exception:
            pass
    t = secrets.token_urlsafe(24)
    LOCAL_TOKEN_FILE.write_text(t, encoding='utf-8')
    return t


def hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), bytes.fromhex(salt), 200_000).hex()


class Sessions:
    def __init__(self, days=30):
        self.lock = threading.Lock(); self.days = days
        d = read_json(SESS_FILE, {}) or {}
        now = time.time()
        # only hashes of the session keys are kept on disk (a copy of sessions.json does not log anyone in)
        self.s = {}
        for k, v in d.items():
            if not isinstance(v, dict) or now - v.get('t', 0) >= days * 86400: continue
            self.s[k if k.startswith('h:') else self._h(k)] = v              # older versions kept the key itself: hash it
        if any(not k.startswith('h:') for k in d): self._save()

    @staticmethod
    def _h(tok): return 'h:' + hashlib.sha256(tok.encode('utf-8', 'replace')).hexdigest()

    def new(self, ip, local):
        tok = secrets.token_urlsafe(32)
        with self.lock:
            self.s[self._h(tok)] = {'t': time.time(), 'ip': ip, 'local': local}
            self._save()
        return tok

    def check(self, tok):
        if not tok: return None
        k = self._h(tok)
        with self.lock:
            v = self.s.get(k)
            if not v: return None
            if time.time() - v['t'] > self.days * 86400: self.s.pop(k, None); return None
            if time.time() - v['t'] > 3600: v['t'] = time.time(); self._save()
            return v

    def drop(self, tok):
        with self.lock: self.s.pop(self._h(tok or ''), None); self._save()

    def drop_remote(self):
        with self.lock:
            self.s = {k: v for k, v in self.s.items() if v.get('local')}; self._save()

    def _save(self):
        try: atomic_write_json(SESS_FILE, self.s, indent=None)
        except Exception: pass


class ChunkedWriter:
    """File-like object writing HTTP/1.1 chunked transfer encoding (zip streaming)."""
    def __init__(self, wfile): self.w = wfile; self.n = 0
    def write(self, b):
        if not b: return 0
        self.w.write(b'%X\r\n' % len(b)); self.w.write(b); self.w.write(b'\r\n'); self.n += len(b)
        return len(b)
    def flush(self): self.w.flush()
    def close(self):
        self.w.write(b'0\r\n\r\n'); self.w.flush()


class HttpError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg); self.code = code


def make_handler(eng):
    class H(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        server_version = 'HotZoneFM'
        timeout = 120

        def log_message(self, fmt, *a): pass

        # ------------------------------------------------------------------ helpers
        FWD = ('X-Forwarded-For', 'Forwarded', 'X-Forwarded-Proto', 'X-Forwarded-Host', 'Tailscale-User-Login', 'X-Real-IP')

        @property
        def is_local(self):
            """A request from a program on THIS computer. `tailscale serve` (and any reverse proxy) also connects from
            127.0.0.1 but adds forwarding headers: those requests come from other devices and are NOT local."""
            if self.client_address[0] not in ('127.0.0.1', '::1', '::ffff:127.0.0.1'): return False
            return not any(self.headers.get(k) for k in self.FWD)

        @property
        def client_ip(self):
            """The real client: the forwarded address when a local proxy (tailscale serve) passed the request on."""
            ip = self.client_address[0]
            if ip in ('127.0.0.1', '::1', '::ffff:127.0.0.1'):
                f = (self.headers.get('X-Forwarded-For') or self.headers.get('X-Real-IP') or '').split(',')[0].strip()
                if f: return f
                if self.headers.get('Tailscale-User-Login'): return 'ts:' + self.headers.get('Tailscale-User-Login')
            return ip

        def check_paths(self, q, method, sess):
            """Every path a request names: device paths (\\\\.\\PhysicalDrive0, CON...) are refused for everyone; the program's
            own folder (Data\\ holds the keys, sessions and the password hash) only from this computer."""
            vals = []
            for v in q.values():
                vals.append(v)
                if v[:1] in '[{':
                    try: vals.append(json.loads(v))
                    except Exception: pass
            if method == 'POST' and 'json' in (self.headers.get('Content-Type') or '') and self.headers.get('Content-Length', '0') != '0':   # (PUT = file uploads: raw data)
                self._jcache = None; self._jcache = self.jbody(); vals.append(self._jcache)
            local = bool(sess and sess.get('local') and self.is_local)
            root = os.path.normcase(os.path.abspath(str(ROOT)))
            stack = vals; n = 0
            while stack and n < 200000:
                v = stack.pop(); n += 1
                if isinstance(v, dict): stack.extend(v.values()); continue
                if isinstance(v, list): stack.extend(v); continue
                if not isinstance(v, str) or len(v) < 2 or len(v) > 4000: continue
                if not (v.startswith(('/', '\\')) or re.match(r'[A-Za-z]:[\\/]', v)): continue
                if v.startswith(('\\\\.\\', '\\\\?\\GLOBALROOT', '//./')) or re.fullmatch(r'(?i)(con|prn|aux|nul|com\d|lpt\d)(\..*)?', os.path.basename(v.rstrip('\\/'))):
                    raise HttpError(400, '不支援裝置路徑')
                if not local:
                    a = os.path.normcase(os.path.abspath(v))
                    if a == root or a.startswith(root.rstrip('\\/') + os.sep):
                        raise HttpError(403, '程式自己的資料夾（設定、金鑰）只能在這台電腦上開啟')

        def host_ok(self):
            """DNS rebinding guard: a web page on some domain re-pointed at 127.0.0.1 sends its own Host name.
            Allowed: IP addresses, localhost, one-word names (the PC name), *.ts.net (Tailscale) and *.local."""
            host = (self.headers.get('Host') or '').strip().lower()
            if not host: return True
            if host.startswith('['): name = host[1:host.find(']')] if ']' in host else host
            else: name = host.rsplit(':', 1)[0] if host.count(':') == 1 else host
            if name in ('localhost',) or '.' not in name: return True
            if re.fullmatch(r'[0-9.]+', name) or ':' in name: return True                # IPv4 / IPv6 literal
            if name.endswith(('.ts.net', '.local', '.localhost')): return True
            extra = [x.lower() for x in (eng.S.get('web.hosts') or []) if isinstance(x, str)]
            return name in extra

        def cookie(self, name):
            c = SimpleCookie()
            try: c.load(self.headers.get('Cookie', ''))
            except Exception: return ''
            return c[name].value if name in c else ''

        def send(self, code, body=b'', ctype='application/json; charset=utf-8', headers=None, cache=0):
            if isinstance(body, str): body = body.encode('utf-8')
            if len(body) > 4096 and ('json' in ctype or 'text' in ctype or 'javascript' in ctype) and 'gzip' in self.headers.get('Accept-Encoding', ''):
                body = gzip.compress(body, 5); headers = dict(headers or {}); headers['Content-Encoding'] = 'gzip'; headers['Vary'] = 'Accept-Encoding'
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', f'private, max-age={cache}' if cache else 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            for k, v in (headers or {}).items(): self.send_header(k, v)
            self.end_headers()
            if self.command != 'HEAD': self.wfile.write(body)

        def json(self, obj, code=200, headers=None):
            dflt = lambda o: list(o) if isinstance(o, (set, frozenset)) else str(o)
            try: txt = json.dumps(obj, ensure_ascii=False, allow_nan=False, default=dflt)   # no deep copy (100k-item ls: -0.46 s)
            except (ValueError, TypeError): txt = json.dumps(json_safe(obj), ensure_ascii=False, default=str)  # NaN / inf -> null
            try: body = txt.encode('utf-8')
            except UnicodeEncodeError:                     # a name with a lone surrogate (unpaired UTF-16 on NTFS): escape
                body = json.dumps(json_safe(obj), ensure_ascii=True, default=str).encode('ascii')   # instead of failing the folder
            self.send(code, body, headers=headers)

        def body(self, limit=64 * 1024 * 1024):
            n = int(self.headers.get('Content-Length') or 0)
            if n > limit: raise HttpError(413, '資料太大')
            self._consumed = True
            return self.rfile.read(n) if n else b''

        def jbody(self):
            if getattr(self, '_jcache', None) is not None: return self._jcache
            b = self.body()
            try: return json.loads(b.decode('utf-8') or '{}')
            except Exception: raise HttpError(400, '資料格式錯誤')

        # ------------------------------------------------------------------ entry points
        def do_GET(self): self.route('GET')
        def do_POST(self): self.route('POST')
        def do_PUT(self): self.route('PUT')
        def do_HEAD(self): self.route('GET')

        def route(self, method):
            self._consumed = False
            try:
                self._route(method)
            finally:
                # a handler that did not read the request body would leave it in the connection, where it would be
                # taken as the start of the next request ('{}GET /api/...') -> read it away (or close if big)
                try: n = int(self.headers.get('Content-Length') or 0)
                except ValueError: n = 0
                if n and not self._consumed:
                    if n <= 1024 * 1024:
                        try: self.rfile.read(n)
                        except Exception: self.close_connection = True
                    else:
                        self.close_connection = True

        def _route(self, method):
            u = urllib.parse.urlsplit(self.path); path = u.path
            q = {k: v[-1] for k, v in urllib.parse.parse_qs(u.query, keep_blank_values=True).items()}
            try:
                if not self.host_ok(): raise HttpError(421, '不認得的主機名稱（Host）。如果你用自己的網域連線，請在電腦上的設定檔 web.hosts 加入它')
                if not self.is_local and not eng.S.get('web.remote'):
                    raise HttpError(403, '這台電腦沒有開放遠端連線（設定 → 遠端連線）')
                if path in STATIC or path.startswith('/static/'):
                    if path == '/' and 'k' in q: return self.local_login(q['k'])
                    return self.static(path)
                if not path.startswith('/api/'): raise HttpError(404, '找不到')
                sess = self.session()
                if path not in PUBLIC_API:
                    if sess is None: raise HttpError(401, '請先登入')
                    if method != 'GET' and self.headers.get('X-HZ') != '1': raise HttpError(403, '缺少驗證標頭')
                fn = eng.api.get((method, path))
                if fn is None: raise HttpError(404, '沒有這個功能')
                self._jcache = None
                if path not in PUBLIC_API: self.check_paths(q, method, sess)
                r = fn(self, q, sess)
                if r is not None: self.json(r)
            except HttpError as e:
                self.json({'ok': False, 'error': str(e), 'code': e.code}, e.code)
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                pass
            except (FileNotFoundError, PermissionError, FileExistsError, ValueError, KeyError, OSError) as e:
                msg = e.strerror if isinstance(e, OSError) and e.strerror else (e.args[0] if e.args else str(e))
                if isinstance(e, PermissionError): msg = '沒有權限：' + str(getattr(e, 'filename', '') or msg)
                try: self.json({'ok': False, 'error': str(msg)}, 400)
                except Exception: pass
            except Exception as e:
                eng.log.exc('web', f'{method} {path}')
                try: self.json({'ok': False, 'error': f'{type(e).__name__}: {e}'}, 500)
                except Exception: pass

        def session(self):
            return eng.sessions.check(self.cookie('hzs'))

        def set_cookie_headers(self, tok):
            secure = '; Secure' if self.headers.get('X-Forwarded-Proto') == 'https' else ''
            return {'Set-Cookie': f'hzs={tok}; Path=/; HttpOnly; SameSite=Strict; Max-Age={86400 * int(eng.S.get("web.session_days") or 30)}{secure}'}

        def local_login(self, key):
            if self.is_local and hmac.compare_digest(key, eng.local_token):
                tok = eng.sessions.new(self.client_address[0], True)
                h = self.set_cookie_headers(tok); h['Location'] = '/'; h['Referrer-Policy'] = 'no-referrer'
                self.send(302, b'', 'text/plain', h)
            else:
                self.send(302, b'', 'text/plain', {'Location': '/', 'Referrer-Policy': 'no-referrer'})

        def static(self, path):
            name = STATIC.get(path) or path[len('/static/'):]
            if not re.fullmatch(r'[A-Za-z0-9_.-]+', name): raise HttpError(404, '找不到')
            f = APP_DIR / name
            if not f.is_file(): raise HttpError(404, '找不到')
            data = f.read_bytes()
            if name == 'ui.html':
                data = data.replace(b'__VER__', APP_VERSION.encode()).replace(b'__STAMP__', repr(round(eng.ui_stamp(), 3)).encode())
            ct = mimetypes.guess_type(name)[0] or 'application/octet-stream'
            if name.endswith('.webmanifest'): ct = 'application/manifest+json'
            if ct.startswith('text/') or 'javascript' in ct or 'json' in ct: ct += '; charset=utf-8'
            self.send(200, data, ct, cache=0, headers={'X-Frame-Options': 'DENY', 'Content-Security-Policy': "frame-ancestors 'none'",
                                                     'Referrer-Policy': 'no-referrer'})

        # ------------------------------------------------------------------ file streaming
        def send_file(self, path, download=False):
            p = norm(path)
            if not os.path.isfile(W.lp(p)): raise HttpError(404, '找不到檔案')
            size = os.path.getsize(W.lp(p))
            ct = mimetypes.guess_type(p)[0] or 'application/octet-stream'
            if p.lower().endswith('.mkv'): ct = 'video/webm'                 # Chromium plays most mkv (h264/vp9) this way
            # a file from disk must never run as a page of this app (it would act with the user's session):
            # web pages / scripts are shown as plain text, and everything gets a sandbox CSP (no scripts at all)
            if p.lower().endswith(('.html', '.htm', '.xhtml', '.shtml', '.xht', '.mht', '.mhtml', '.js', '.mjs', '.xml', '.xsl', '.hta', '.svgz')):
                ct = 'text/plain; charset=utf-8'
            rng = self.headers.get('Range', '')
            start, end = 0, size - 1; code = 200
            m = re.match(r'bytes=(\d*)-(\d*)', rng)
            if m and size:
                a, b = m.groups()
                if a == '' and b: start = max(0, size - int(b))
                else: start = int(a or 0); end = min(size - 1, int(b)) if b else size - 1
                if start > end or start >= size:
                    self.send(416, b'', 'text/plain', {'Content-Range': f'bytes */{size}'}); return
                code = 206
            n = end - start + 1 if size else 0
            self.send_response(code)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', str(n))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Cache-Control', 'private, max-age=60')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if ct != 'application/pdf':                                     # (Chrome's PDF viewer does not run sandboxed)
                self.send_header('Content-Security-Policy', "sandbox; default-src 'none'; img-src 'self' data:; media-src 'self'; style-src 'unsafe-inline'")
            if code == 206: self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            fn = urllib.parse.quote(os.path.basename(p))
            self.send_header('Content-Disposition', f"{'attachment' if download else 'inline'}; filename*=UTF-8''{fn}")
            self.end_headers()
            if self.command == 'HEAD' or not n: return
            with open(W.lp(p), 'rb') as f:
                f.seek(start); left = n
                while left > 0:
                    b = f.read(min(1024 * 1024, left))
                    if not b: break
                    self.wfile.write(b); left -= len(b)

        def send_zip(self, paths, name):
            """Stream a zip of files / folders. Folder links (junctions) are not followed; names that would clash get
            ' (2)'; anything that could not be read completely is listed in HotZone_未包含的檔案.txt inside the zip
            (a zip that silently misses files is worse than no zip)."""
            self.send_response(200)
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Transfer-Encoding', 'chunked')
            self.send_header('Content-Disposition', f"attachment; filename*=UTF-8''{urllib.parse.quote(name)}")
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if self.command == 'HEAD': return
            cw = ChunkedWriter(self.wfile)
            used = set(); problems = []

            def arc_name(n):
                n = n.replace('\\', '/'); k = n.lower() if IS_WIN else n
                if k in used:
                    stem, ext = os.path.splitext(n); i = 2
                    while (f'{stem} ({i}){ext}'.lower() if IS_WIN else f'{stem} ({i}){ext}') in used: i += 1
                    n = f'{stem} ({i}){ext}'; k = n.lower() if IS_WIN else n
                used.add(k); return n

            def add(zf, fp, arc):
                try:
                    st = os.stat(W.lp(fp))
                    zi = zipfile.ZipInfo.from_file(W.lp(fp), arc_name(arc))
                    got = 0
                    with open(W.lp(fp), 'rb') as src, zf.open(zi, 'w', force_zip64=st.st_size > 2 ** 31) as dst:
                        while True:
                            b = src.read(1024 * 1024)
                            if not b: break
                            dst.write(b); got += len(b)
                    if got < st.st_size: problems.append(f'{fp}\t不完整：只讀到 {got:,} / {st.st_size:,} 位元組')
                except OSError as e:
                    problems.append(f'{fp}\t讀取失敗：{e}')
            with zipfile.ZipFile(cw, 'w', zipfile.ZIP_STORED, allowZip64=True) as zf:
                for p in paths:
                    p = norm(p); base = os.path.dirname(p.rstrip('\\/'))
                    if W.is_link_like(p) and os.path.isdir(p):
                        problems.append(f'{p}\t連結資料夾（junction / 捷徑），沒有跟著打包'); continue
                    if os.path.isdir(p):
                        top, base_l = W.lp(p), (W.lp(base) if base else base)       # long paths (> 260) too
                        for root, dirs, files, links in W.walk(top, onerror=lambda e: problems.append(f'{getattr(e, "filename", "")}\t無法讀取：{e}')):
                            for d in links: problems.append(f'{os.path.join(root, d)}\t連結資料夾（junction / 捷徑），沒有跟著打包')
                            for f in files:
                                fp = os.path.join(root, f)
                                add(zf, fp, os.path.relpath(fp, base_l))
                    elif os.path.isfile(p):
                        add(zf, p, os.path.basename(p))
                    else:
                        problems.append(f'{p}\t找不到')
                if problems:
                    zf.writestr(arc_name('HotZone_未包含的檔案.txt'), ('下列項目沒有完整包進這個 zip：\r\n\r\n' + '\r\n'.join(problems) + '\r\n').encode('utf-8-sig'))
            cw.close()

        def receive_upload(self, q):
            """Upload into a folder. Never overwrites without a vault copy: the data goes to a private temp file
            first, then is renamed into place with a no-replace rename (overwrite = vault the old file first)."""
            self._consumed = True; self.close_connection = True       # the body is read here (or the connection dropped)
            d = norm(q.get('dir', '')); name = F.check_name(q.get('name', ''))
            if not os.path.isdir(d): raise HttpError(400, '目的資料夾不存在')
            mode = q.get('mode', 'rename')
            if mode not in ('rename', 'skip', 'overwrite'): raise HttpError(400, '不認得的同名處理方式')
            dst = os.path.join(d, name)
            if self.headers.get('Content-Length') is None: raise HttpError(411, '上傳缺少檔案大小')
            n = int(self.headers.get('Content-Length') or 0)
            if mode == 'skip' and os.path.lexists(W.lp(dst)):
                left = n
                while left > 0:
                    b = self.rfile.read(min(1024 * 1024, left))
                    if not b: break
                    left -= len(b)
                return {'ok': True, 'skipped': True, 'path': dst}
            try:                                                    # our own temp files left by an upload cut short (> 1 day old)
                for e in os.scandir(W.lp(d)):
                    if re.fullmatch(r'\.[0-9a-f]{12}\.hzupload', e.name) and time.time() - e.stat().st_mtime > 86400: os.remove(e.path)
            except OSError:
                pass
            part = os.path.join(d, f'.{uuid.uuid4().hex[:12]}.hzupload'); got = 0
            try:
                with open(W.lp(part), 'xb') as f:
                    while got < n:
                        b = self.rfile.read(min(1024 * 1024, n - got))
                        if not b: break
                        f.write(b); got += len(b)
                    if got == n: f.flush(); os.fsync(f.fileno())     # on the disk BEFORE it gets its name and we answer OK
                if got != n: raise HttpError(400, '上傳中斷')
                for _ in range(1000):
                    try:
                        W.rename_noreplace(part, dst); break
                    except FileExistsError:
                        if mode == 'skip':
                            os.remove(W.lp(part)); return {'ok': True, 'skipped': True, 'path': dst}
                        if mode == 'overwrite' and os.path.isdir(W.lp(dst)) and not W.is_link_like(dst):
                            mode = 'rename'; dst = unique_name(dst); continue      # never replace a whole folder by a file
                        if mode == 'overwrite':
                            eng.vault.stash(dst, f'上傳同名檔案「{name}」時選了覆蓋，舊檔先保管', 'upload_overwrite')
                            mode = 'rename'                    # if something re-appears, keep both
                        else:
                            dst = unique_name(dst)
                else:
                    raise HttpError(500, '找不到可用的檔名')
            except BaseException:
                try:
                    if os.path.lexists(W.lp(part)): os.remove(W.lp(part))
                except OSError:
                    pass
                raise
            eng.index.touch(dst); eng.hot.notify([dst])
            return {'ok': True, 'path': dst, 'size': got}
    return H


class WebServer:
    def __init__(self, eng):
        self.eng = eng; self.httpd = None; self.th = None; self.err = ''; self.port = 0
        self.stop_ev = threading.Event()

    def start(self):
        self.th = threading.Thread(target=self._run, name='HZ-Web', daemon=True); self.th.start()
        return self

    def _run(self):
        tries = 0
        while not self.stop_ev.is_set():
            port = int(self.eng.S.get('web.port') or 8765)
            host = '0.0.0.0' if self.eng.S.get('web.remote') else '127.0.0.1'
            try:
                ThreadingHTTPServer.allow_reuse_address = not IS_WIN
                ThreadingHTTPServer.daemon_threads = True
                self.httpd = ThreadingHTTPServer((host, port), make_handler(self.eng))
                self.port = port; self.err = ''
                self.eng.log.info('web', f'網頁伺服器 {host}:{port}')
                self.httpd.serve_forever(poll_interval=0.3)
                return
            except OSError as e:
                tries += 1
                self.err = f'埠 {port} 無法使用（{e.strerror or e}）'
                if tries in (1, 10): self.eng.log.warn('web', self.err)
                if tries == 3 and self._move_port(host, port): tries = 0; continue   # another program owns it: take a free one
                if self.stop_ev.wait(1.0 if tries < 15 else 5.0): return

    def _move_port(self, host, busy):
        """The port is taken by another program (seen on a real PC: the window waited 60 s for nothing). Pick the next
        free one, store it as web.port (the launcher reads it from settings.json) and tell the user."""
        import socket, json as _j, urllib.request
        other = ''
        try:                                                           # who is it? our own previous engine (hot update) -> wait
            op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with op.open(f'http://127.0.0.1:{busy}/api/ping', timeout=1.5) as r: j = _j.loads(r.read().decode('utf-8'))
            if j.get('app') == 'HotZone FM':
                if j.get('root', '') == os.path.normcase(os.path.abspath(str(ROOT))) or not j.get('root'): return False
                other = j.get('root', '')
        except Exception:
            pass
        for p in list(range(busy + 1, busy + 40)) + [18765, 28765]:
            if p > 65535: continue
            s = socket.socket()
            try:
                if not IS_WIN: s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((host, p))
            except OSError:
                continue
            finally:
                s.close()
            self.eng.S.set('web.port', p)
            msg = (f'連接埠 {busy} 被另一份 HotZone（{other}）使用中' if other else f'連接埠 {busy} 被別的程式佔用') + f'，已自動改用 {p}（手機或其他電腦的網址也要改成 :{p}；可以在「設定」換成別的號碼）'
            self.eng.log.warn('web', msg)
            try: self.eng.notice('port', 'warn', msg)
            except Exception: pass
            return True
        return False

    def stop(self):
        self.stop_ev.set()
        h = self.httpd
        if h is not None:
            try: h.shutdown(); h.server_close()
            except Exception: pass
        if self.th: self.th.join(3)

    def restart(self):
        self.stop(); self.stop_ev = threading.Event(); self.httpd = None; self.start()

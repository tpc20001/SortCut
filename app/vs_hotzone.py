"""🔥 HotZone 整合進 SortCut（V0.1.55）— SortCut 主程式這一邊（只用標準函式庫）。

HotZone 的程式（app\\hz_*.py、ui.*）跟著 SortCut 一起更新；背景引擎用電腦上的 Python 3.11 另外跑（vs_hz_boot.py），
設定、搬檔佇列、熱區、索引、保管區都照舊讀 HotZone 原本的資料夾（Data\\）。

這個檔負責：找 HotZone 資料夾、檢查／安裝 Python 套件、啟動（系統管理員）／停止／接手舊的 HotZoneFM.exe、開視窗，
以及「硬碟協調員」：同一顆 HDD 兩邊都在大量讀寫、忙碌一直很高時，只讓一邊做（避免 HDD 長時間卡在 100%）。
"""
import os, sys, json, time, shutil, threading, subprocess, urllib.request, urllib.parse, http.client
from collections import deque
from pathlib import Path

IS_WIN = os.name == 'nt'
NO_WINDOW = 0x08000000 if IS_WIN else 0
PKGS = ['Pillow', 'numpy', 'opencv-python-headless']                         # HotZone 背景引擎要的（imageio-ffmpeg 不用：用 SortCut 的 ffmpeg）
CHECK = r'''
import sys, json, importlib
r = {'py': sys.version.split()[0], 'exe': sys.executable}
for m, k in (('PIL', 'pil'), ('numpy', 'numpy'), ('cv2', 'cv2')):
    try: mod = importlib.import_module(m); r[k] = getattr(mod, '__version__', 'ok')
    except Exception: r[k] = ''
try:
    import PySide6; from PySide6 import QtWebEngineWidgets; r['pyside6'] = PySide6.__version__
except Exception: r['pyside6'] = ''
print('VSHZ' + json.dumps(r))
'''
DEFAULTS = {'root': '', 'python': '', 'auto': False, 'arb': True, 'slice_min': 10, 'busy_pct': 85, 'hz_mbps': 3}


def clean_env():
    """給電腦上的 Python 用的環境變數：拿掉 SortCut EXE（PyInstaller）帶的 Qt 設定和自己的資料夾，免得那邊載到錯的 PySide6."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('QT_', 'QTWEBENGINE', 'QML', 'PYTHONHOME', 'PYTHONPATH', '_MEI', '_PYI'))}
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.normcase(os.path.dirname(sys.executable))
        env['PATH'] = os.pathsep.join(p for p in env.get('PATH', '').split(os.pathsep) if p and not os.path.normcase(p).startswith(exe_dir))
    return env


def _mapped_drive(path):
    """這個路徑在「連線網路磁碟機」或 subst 的磁碟代號上嗎？是就回傳那個代號."""
    if not IS_WIN: return ''
    try:
        import ctypes
        drv = os.path.splitdrive(os.path.abspath(str(path)))[0]
        if not drv or drv.startswith('\\\\'): return ''
        if ctypes.windll.kernel32.GetDriveTypeW(drv + '\\') == 4: return drv
        buf = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.QueryDosDeviceW(drv, buf, 1024) and buf.value.startswith('\\??\\'): return drv
    except Exception: pass
    return ''


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None


class HotZoneManager:
    def __init__(self, E, adopt=None):
        self.E = E; self.env = getattr(adopt, 'env', None) or {}; self.installing = None; self.cookie = ''; self.cookie_port = 0
        self._ping = (0, None); self.state = {}; self.arb = {}; self.arb_log = deque(maxlen=200); self.paused_by_us = set()
        self.cont = {}; self.decide = {}; self.slice_owner = {}; self.lock = threading.Lock(); self.alive = True; self._t_state = 0
        self.last_err = ''; self.old = adopt; self.th = None; self.migrating = False; self.cands = []; self.ui_before = None; self.job = {}; self.life = threading.RLock(); self.mig_msg = ''; self.mig_last = None
        if adopt is not None:                                                   # 熱更新：接手舊的狀態（協調員暫停了什麼、誰在用哪顆硬碟）
            for k in ('paused_by_us', 'arb', 'arb_log', 'slice_owner', 'cont', 'cookie', 'cookie_port', 'installing', 'ui_before', 'mig_msg', 'mig_last', 'migrating', 'cands', 'job', 'life'):
                try: setattr(self, k, getattr(adopt, k))
                except Exception: pass

    def start_thread(self):
        if self.th is not None: return
        if self.old is not None:
            try: self.old.alive = False
            except Exception: pass
            self.old = None
        self.th = threading.Thread(target=self._loop, name='VsHotZone', daemon=True); self.th.start()

    # ---------------------------------------------------------------- 設定、資料夾
    def cfg(self):
        c = dict(DEFAULTS); c.update(self.E.cfg.get('hz') or {}); return c

    def set_cfg(self, **kw):
        c = dict(self.E.cfg.get('hz') or {}); c.update(kw); self.E.cfg.set('hz', c); self.E.log.w(f'🔥 HotZone 設定：{kw}')

    def root_candidates(self):
        L = []
        app_root = Path(getattr(self.E, 'root', '.'))
        for base in [app_root.parent, app_root, Path.home(), Path.home() / 'Desktop', Path.home() / 'Documents']:
            for nm in ('HotZoneFM', 'HotZone', 'HotZone FM', 'hotzone'):
                L.append(base / nm)
        if IS_WIN:
            for d in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
                for nm in ('HotZoneFM', 'HotZone', 'Tools\\HotZoneFM', 'Program\\HotZoneFM', 'Apps\\HotZoneFM'):
                    L.append(Path(f'{d}:\\') / nm)
            for x in self._running_exe_dirs(): L.insert(0, x)                   # 正在跑的 HotZoneFM.exe 在哪裡：最準
        for base in self._scan_bases():                                         # 名字裡有 hotzone 的資料夾（例如 HotZoneFM_V0.1.66），往下看兩層
            for p1 in self._ls(base):
                if 'hotzone' in p1.name.lower().replace(' ', ''): L.append(p1)
                elif p1.name.lower() in ('tools', 'apps', 'program', 'programs', 'software', '程式', '工具'):
                    L.extend(p2 for p2 in self._ls(p1) if 'hotzone' in p2.name.lower().replace(' ', ''))
        L2 = []
        for p in L:                                                             # 版本資料夾裡面還有一層（解壓縮成 HotZoneFM_V0.1.66\\HotZoneFM）
            L2.append(p)
            if p.name.lower().startswith('hotzone') and not self.looks_like_root(p): L2.extend(q for q in self._ls(p) if 'hotzone' in q.name.lower())
        L = L2
        hm = os.path.normcase(os.path.abspath(str(self.home()))); out = []
        for p in L:                                                             # VideoSift\HotZone 是整合的目的地（可能只複製了一半），不當成「原本的」
            k = os.path.normcase(os.path.abspath(str(p)))
            if k != hm and k not in [os.path.normcase(os.path.abspath(str(x))) for x in out] and self.looks_like_root(p): out.append(p)
        return out

    @staticmethod
    def _ls(p):
        """資料夾第一層：只看名字可能有關的（先比名字、再看是不是資料夾，大資料夾也很快）."""
        K = ('hotzone', 'tools', 'apps', 'program', 'programs', 'software', '程式', '工具')
        out = []
        try:
            for i, x in enumerate(os.scandir(str(p))):
                if i > 20000: break
                n = x.name.lower().replace(' ', '')
                if any(k in n for k in K):
                    try:
                        if x.is_dir(): out.append(Path(x.path))
                    except Exception: pass
        except Exception: pass
        return out

    def _scan_bases(self):
        app_root = Path(getattr(self.E, 'root', '.')); B = [app_root.parent, Path.home(), Path.home() / 'Desktop', Path.home() / 'Documents', Path.home() / 'Downloads']
        if IS_WIN:
            try:
                import ctypes
                m = ctypes.windll.kernel32.GetLogicalDrives()
                for i, d in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
                    if i >= 2 and m >> i & 1 and ctypes.windll.kernel32.GetDriveTypeW(f'{d}:\\') in (2, 3): B.append(Path(f'{d}:\\'))   # 本機硬碟、隨身碟（不碰網路磁碟）
            except Exception: pass
        return B

    def _running_exe_dirs(self):
        out = []
        for x in self.hz_procs():
            if (x.get('Name') or '').lower() == 'hotzonefm.exe' and x.get('ExecutablePath'): out.append(Path(x['ExecutablePath']).parent)
        return out

    @staticmethod
    def looks_like_root(p):
        try: p = Path(p); return (p / 'HotZoneFM.exe').exists() or (p / 'Data' / 'settings.json').exists() and ((p / 'app' / 'hz_engine.py').exists() or (p / 'Data' / 'queue').exists())
        except Exception: return False

    def _is_home(self, p):
        try: return os.path.normcase(os.path.abspath(str(p))) == os.path.normcase(os.path.abspath(str(self.home())))
        except Exception: return False

    def root(self):
        c = self.cfg()
        if c.get('root') and not (self._is_home(c['root']) and not c.get('migrated_from')): return Path(c['root'])
        if c.get('root') and not getattr(self, '_home_warned', False):          # 舊版把「暫用的 VideoSift\HotZone」存成設定了：照樣去找原本的
            self._home_warned = True; self.E.log.w(f'🔥 HotZone：設定裡的資料夾是 VideoSift\\HotZone（之前沒找到原本的時候暫用的），再找一次原本的 HotZone')
        rc = getattr(self, '_root_cache', None)
        if rc and time.time() - rc[0] < 60: return rc[1]                       # 還沒找到時：別每次都掃 D～Z（畫面會卡、HDD 會被叫醒）
        pg = self.ping()
        if pg and pg.get('root') and not self._is_home(pg['root']) and self.looks_like_root(pg['root']):
            self.set_cfg(root=str(pg['root'])); return Path(pg['root'])
        cand = self.root_candidates()
        if len(cand) > 1:                                                       # 找到好幾個：正在跑的優先，再來是最近有改動的（平常在用的）
            run = {os.path.normcase(str(x)) for x in self._running_exe_dirs()}
            cand = sorted(cand, key=lambda p: (os.path.normcase(str(p)) in run, self.root_info(p)['t']), reverse=True)
        if cand: self._root_cache = None; self.set_cfg(root=str(cand[0])); self.E.log.w(f'🔥 HotZone：找到原本的資料夾 {cand[0]}（設定、佇列、索引都讀這裡）'); return cand[0]
        r = Path(getattr(self.E, 'root', '.')) / 'HotZone'; self._root_cache = (time.time() + 540, r)   # 沒找到：先用 VideoSift\HotZone，但不存進設定（之後還能找到原本的）
        return r

    def settings_file(self): return self.root() / 'Data' / 'settings.json'

    def port(self):
        try: return int(json.loads(self.settings_file().read_text(encoding='utf-8')).get('web.port') or 8765)
        except Exception: return 8765

    def token(self):
        try: return (self.root() / 'Data' / 'local_token.txt').read_text(encoding='utf-8').strip()
        except Exception: return ''

    # ---------------------------------------------------------------- 連線
    def ping(self, fresh=False):
        t, v = self._ping
        if not fresh and time.time() - t < 2: return v
        res = None; want = (self.E.cfg.get('hz') or {}).get('root') or ''
        want = os.path.normcase(os.path.abspath(want)) if want else ''
        base = int((self.E.cfg.get('hz') or {}).get('port') or 0) or self._port_guess()
        for port in [base] + [p for p in range(8765, 8771) if p != base]:
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(f'http://127.0.0.1:{port}/api/ping', timeout=0.8) as r:
                    d = json.loads(r.read().decode('utf-8'))
                if d.get('app') == 'HotZone FM':
                    d['port'] = port
                    if res is None: res = d
                    if not want or os.path.normcase(os.path.abspath(str(d.get('root') or ''))) == want: res = d; break   # 有好幾個 HotZone 在跑：用資料夾對得上的那個
            except Exception: continue
        if res is not None and want and os.path.normcase(os.path.abspath(str(res.get('root') or ''))) != want: res['other_root'] = True
        self._ping = (time.time(), res); return res

    def _port_guess(self):
        try:
            c = self.E.cfg.get('hz') or {}
            if c.get('root'): return int(json.loads((Path(c['root']) / 'Data' / 'settings.json').read_text(encoding='utf-8')).get('web.port') or 8765)
        except Exception: pass
        return 8765

    def _login(self, port):
        k = self.token()
        if not k: return False
        try:
            op = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
            try: op.open(f'http://127.0.0.1:{port}/?k={urllib.parse.quote(k)}', timeout=3)
            except urllib.error.HTTPError as e:
                ck = e.headers.get('Set-Cookie') or ''
                if 'hzs=' in ck and 'hzs=;' not in ck: self.cookie = ck.split(';')[0]; self.cookie_port = port; return True
        except Exception as ex: self.last_err = str(ex)
        return False

    def api(self, path, body=None, timeout=5):
        pg = self.ping()
        if not pg: raise RuntimeError('HotZone 背景引擎沒有在跑')
        port = pg['port']
        for attempt in (0, 1):
            if not self.cookie or self.cookie_port != port:
                if not self._login(port): raise RuntimeError('登入 HotZone 失敗（讀不到 Data\\local_token.txt？）')
            data = json.dumps(body).encode('utf-8') if body is not None else None
            rq = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data, method='POST' if body is not None else 'GET',
                                        headers={'Cookie': self.cookie, 'X-HZ': '1', 'Content-Type': 'application/json'})
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(rq, timeout=timeout) as r:
                    return json.loads(r.read().decode('utf-8') or '{}')
            except urllib.error.HTTPError as e:
                if e.code in (401, 403) and attempt == 0: self.cookie = ''; continue
                try: msg = json.loads(e.read().decode('utf-8')).get('error') or str(e)
                except Exception: msg = str(e)
                raise RuntimeError(msg)
        raise RuntimeError('HotZone 沒有回應')

    # ---------------------------------------------------------------- Python 環境
    def python_candidates(self):
        c = self.cfg(); L = []
        if c.get('python'): L.append([c['python']])
        fe = (getattr(getattr(self.E, 'faces', None), 'env', None) or {}).get('cmd')
        if fe: L.append(list(fe))
        if IS_WIN:
            if shutil.which('py'): L.append(['py', '-3.11']); L.append(['py', '-3'])
            la = os.environ.get('LOCALAPPDATA', '')
            for v in ('311', '312', '313', '310'):
                p = os.path.join(la, 'Programs', 'Python', f'Python{v}', 'python.exe')
                if os.path.isfile(p): L.append([p])
            for nm in ('python', 'python3'):
                p = shutil.which(nm)
                if p and 'WindowsApps' not in p: L.append([p])
        else:
            for nm in ('python3.11', 'python3', 'python'):
                p = shutil.which(nm)
                if p: L.append([p])
        out = []
        for x in L:
            if x not in out: out.append(x)
        return out

    def check_env(self):
        best = None; tried = []
        for cmd in self.python_candidates():
            try:
                p = subprocess.run(cmd + ['-c', CHECK], capture_output=True, timeout=90, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL, env=clean_env())
                out = p.stdout.decode('utf-8', 'replace'); i = out.find('VSHZ')
                if i < 0: tried.append({'cmd': cmd, 'err': (p.stderr.decode('utf-8', 'replace') or out)[-300:]}); continue
                r = json.loads(out[i + 4:].strip().splitlines()[0]); r['cmd'] = cmd; r['ok'] = bool(r.get('pil') and r.get('numpy') and r.get('cv2'))
                tried.append(r); score = (r['ok'], bool(r.get('pyside6')), r.get('py', '').startswith('3.11'))
                if best is None or score > best[0]: best = (score, r)
            except Exception as ex: tried.append({'cmd': cmd, 'err': f'{type(ex).__name__}: {ex}'})
        env = dict(best[1]) if best else {'ok': False}
        env['tried'] = tried; env['t'] = time.time(); self.env = env
        self.E.log.w('🔥 HotZone：檢查環境 → ' + (f'{env.get("exe")}（Python {env.get("py")}，Pillow {env.get("pil") or "沒有"}，numpy {env.get("numpy") or "沒有"}，'
                                                 f'OpenCV {env.get("cv2") or "沒有"}，視窗用的 PySide6 {env.get("pyside6") or "沒有"}）' if best else '找不到 Python') + f'；試過 {len(tried)} 個')
        return env

    def install(self, window=False):
        cmds = self.python_candidates()
        if not cmds: return {'ok': False, 'message': '找不到 Python：請先到 python.org 下載 Python 3.11 安裝（勾「Add to PATH」）'}
        py = (self.env or {}).get('cmd') or cmds[0]
        pk = PKGS + (['PySide6'] if window else [])
        logp = Path(self.E.root) / 'LOG' / 'hotzone_install.txt'; logp.parent.mkdir(parents=True, exist_ok=True)
        cmd = py + ['-m', 'pip', 'install', '--user', '--upgrade'] + pk
        try:
            fh = open(logp, 'a', encoding='utf-8'); fh.write(f'\n===== {time.strftime("%Y-%m-%d %H:%M:%S")} {" ".join(cmd)}\n'); fh.flush()
            self.installing = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
        except Exception as ex: return {'ok': False, 'message': f'沒辦法開始安裝：{ex}'}
        self.E.log.w(f'🔥 HotZone：開始安裝套件 {" ".join(cmd)}（LOG\\hotzone_install.txt）')
        return {'ok': True, 'message': '開始安裝（1～5 分鐘' + ('，PySide6 比較大，可能 10 分鐘' if window else '') + '），裝好會自動重新檢查'}

    def pyw(self, env=None):
        env = env or self.env or {}
        exe = env.get('exe') or ''
        if not exe: return None
        if IS_WIN and exe.lower().endswith('python.exe') and os.path.exists(exe[:-10] + 'pythonw.exe'): return exe[:-10] + 'pythonw.exe'
        return exe

    # ---------------------------------------------------------------- 啟動／停止／接手
    def boot_path(self): return str(Path(__file__).resolve().parent / 'vs_hz_boot.py')

    def ff_dir(self):
        ff = getattr(self.E, 'ff', '') or ''
        return str(Path(ff).parent) if ff and os.path.isabs(ff) else ''

    def start(self, by='手動'):
        with self.life: return self._start(by)                             # 同時只做一件（手機和電腦同時按不會開兩個引擎）

    def _start(self, by='手動'):
        pg = self.ping(fresh=True)
        if pg: return {'ok': True, 'message': 'HotZone 背景引擎已經在跑了' + ('' if pg.get('mode') == 'videosift' else '（是原本的 HotZoneFM.exe：按「接手」改由 SortCut 跑）')}
        env = self.env if (self.env or {}).get('ok') else self.check_env()
        if not env.get('ok'):
            return {'ok': False, 'need_env': True, 'message': 'Python 還沒裝好 HotZone 要的套件（Pillow、numpy、OpenCV）：按「📦 安裝需要的套件」'}
        root = str(self.root()); exe = self.pyw(env); args = [self.boot_path(), '--root', root, '--engine'] + (['--ff', self.ff_dir()] if self.ff_dir() else [])
        try:
            if IS_WIN:
                import ctypes
                for pth in (self.boot_path(), root, exe):                      # 系統管理員身分看不到「連線網路磁碟機」／subst 的磁碟代號
                    bad = _mapped_drive(pth)
                    if bad: return {'ok': False, 'message': f'{pth} 在對應的網路磁碟機／subst 磁碟 {bad}，系統管理員身分看不到：請把 SortCut／HotZone／Python 放在本機硬碟'}
                try: os.makedirs(root, exist_ok=True)
                except Exception: pass
                params = subprocess.list2cmdline(args)
                r = ctypes.windll.shell32.ShellExecuteW(None, 'runas', exe, params, root, 0)
                if int(r) <= 32:
                    if int(r) in (5, 1223):
                        self.uac_declined = True
                        return {'ok': False, 'message': f'沒有啟動（你在「使用者帳戶控制」按了否？代碼 {int(r)}）。自動啟動先停住，要用時再按「▶ 啟動」'}
                    why = {2: '找不到 Python（pythonw.exe）', 3: '找不到資料夾', 8: '記憶體不夠', 31: '沒有程式可以開'}.get(int(r), '')
                    return {'ok': False, 'message': f'沒有啟動：Windows 回報代碼 {int(r)}' + (f'（{why}）' if why else '') + f'。Python：{exe}；資料夾：{root}'}
                self.uac_declined = False
            else:
                env2 = dict(os.environ); subprocess.Popen([exe] + args, cwd=root, env=env2, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except Exception as ex: return {'ok': False, 'message': f'啟動失敗：{ex}'}
        self.E.log.w(f'🔥 HotZone：{by}啟動背景引擎（{exe} {" ".join(args)}）')
        return {'ok': True, 'message': 'HotZone 背景引擎啟動中（Windows 會問一次系統管理員權限，按「是」）'}

    @staticmethod
    def _pid_alive(pid):
        if not pid: return False
        if IS_WIN:
            import ctypes
            k = ctypes.windll.kernel32; h = k.OpenProcess(0x00100000 | 0x1000, False, int(pid))      # SYNCHRONIZE | QUERY_LIMITED_INFORMATION
            if not h: return False
            try: return k.WaitForSingleObject(h, 0) == 0x102                         # WAIT_TIMEOUT＝還在
            finally: k.CloseHandle(h)
        try: os.kill(int(pid), 0)
        except Exception: return False
        try: return open(f'/proc/{int(pid)}/stat').read().rsplit(')', 1)[1].split()[0] != 'Z'     # 結束了但還沒被收（zombie）＝已經結束
        except Exception: return True

    def wait_engine_gone(self, pg, secs=150, prog=None):
        """等引擎真的結束：網頁先關，它之後還在存索引、關保管區（檔案還開著）。有 PID 就等到程序結束；舊版沒有 PID 就多等 10 秒."""
        t0 = time.time()
        while time.time() - t0 < secs and self.ping(fresh=True): time.sleep(1)
        if self.ping(fresh=True): return False
        pid = (pg or {}).get('pid')
        if pid:
            while time.time() - t0 < secs and self._pid_alive(pid):
                if prog: prog(f'等 HotZone 背景引擎存好索引、關好檔案…（{time.time() - t0:.0f} 秒）')
                time.sleep(1)
            if self._pid_alive(pid): return False
        else: time.sleep(10)
        return True

    def stop(self, by='手動'):
        try: self.api('/api/system/quit', {}); self.E.log.w(f'🔥 HotZone：{by}停止背景引擎'); return {'ok': True, 'message': '已經叫 HotZone 背景引擎結束（做到一半的搬檔，下次啟動會接著做）'}
        except Exception as ex: return {'ok': False, 'message': f'停止失敗：{ex}'}

    def takeover(self):
        with self.life: return self._takeover()                             # 同時只做一件（手機和電腦同時按不會開兩個引擎）

    def _takeover(self):
        """原本的 HotZoneFM.exe 正在跑：叫它結束 → 用 SortCut 裡的接著跑（同一個 Data\\：佇列、熱區、索引都接續）."""
        pg = self.ping(fresh=True)
        if pg and pg.get('mode') == 'videosift': return {'ok': True, 'message': '已經是 SortCut 在跑了'}
        env = self.env if (self.env or {}).get('ok') else self.check_env()
        if not env.get('ok'): return {'ok': False, 'need_env': True, 'message': '先按「📦 安裝需要的套件」，裝好才能接手'}
        if pg:
            if pg.get('root'): self.set_cfg(root=str(pg['root']))
            r = self.stop('接手：')
            if not r['ok']: return r
            if not self.wait_engine_gone(pg, 90): return {'ok': False, 'message': '原本的 HotZone 一分半內沒有結束（可能在搬大檔或存索引），等一下再按一次「接手」'}
        r = self.start('接手：'); self.E.log.w('🔥 HotZone：接手原本的 HotZoneFM.exe → ' + r['message'])
        if r['ok']: r['message'] = '原本的 HotZone 已經結束，改由 SortCut 接著跑（沒做完的搬檔、熱區會接續）。原本的 HotZoneFM.exe 視窗之後還能用，它會連到這個引擎'
        return r

    def open_ui(self):
        pg = self.ping(fresh=True)
        if not pg: return {'ok': False, 'message': 'HotZone 背景引擎沒有在跑：先按「▶ 啟動」'}
        env = self.env or {}
        if env.get('pyside6') and self.pyw(env):
            try:
                subprocess.Popen([self.pyw(env), self.boot_path(), '--root', str(self.root()), '--shell'], creationflags=NO_WINDOW, stdin=subprocess.DEVNULL, close_fds=True, env=clean_env())
                return {'ok': True, 'message': '打開 HotZone 視窗'}
            except Exception as ex: self.E.log.w(f'🔥 HotZone 視窗開不起來：{ex}，改用瀏覽器')
        url = f'http://127.0.0.1:{pg["port"]}/?k={urllib.parse.quote(self.token())}'
        if IS_WIN:
            for edge in (os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
                         os.path.join(os.environ.get('ProgramFiles', ''), 'Microsoft', 'Edge', 'Application', 'msedge.exe')):
                if os.path.isfile(edge):
                    try: subprocess.Popen([edge, f'--app={url}', '--new-window'], close_fds=True); return {'ok': True, 'message': '用 Edge 的 App 視窗打開 HotZone（從檔案總管拖檔案進來要用 HotZone 視窗：設定裡安裝 PySide6）'}
                    except Exception: pass
            try: os.startfile(url); return {'ok': True, 'message': '用瀏覽器打開 HotZone'}
            except Exception as ex: return {'ok': False, 'message': f'打不開：{ex}'}
        return {'ok': True, 'message': url, 'url': url}

    # ---------------------------------------------------------------- 整合：資料搬進 SortCut
    def home(self): return Path(getattr(self.E, 'root', '.')) / 'HotZone'

    def migrated(self):
        try: return self._is_home(self.root()) and bool(self.cfg().get('migrated_from'))
        except Exception: return False

    MIG_SKIP = {'webview_cache', 'Cache', 'GPUCache', 'Code Cache', 'ShaderCache', 'GrShaderCache', 'DawnCache', 'blob_storage', '__pycache__'}
    MIG_OPTIONAL = ('webview', 'thumbs', 'comfy')            # 視窗暫存、縮圖快取：沒複製到也沒關係（HotZone 會重新產生）

    @staticmethod
    def _lp(p):
        """Windows 長路徑（超過 240 字）加 \\\\?\\ 前綴."""
        s = os.path.abspath(str(p))
        if IS_WIN and len(s) > 240 and not s.startswith('\\\\?\\'): return '\\\\?\\UNC\\' + s[2:] if s.startswith('\\\\') else '\\\\?\\' + s
        return s

    @staticmethod
    def _why(ex):
        w = getattr(ex, 'winerror', None); en = getattr(ex, 'errno', None)
        if w in (32, 33): return '被別的程式開著（占用中）'
        if w == 5 or isinstance(ex, PermissionError): return '沒有權限（可能是系統管理員身分建立的，或還被開著）'
        if w in (3, 206) or en == 36: return '路徑太長或找不到'
        if w == 112 or en == 28: return '磁碟空間不夠'
        if isinstance(ex, FileNotFoundError): return '複製時不見了'
        return f'{type(ex).__name__}: {ex}'

    def hz_procs(self, root=None):
        """電腦上還開著的 HotZone 程式（原本的 HotZoneFM.exe、SortCut 開的 HotZone 視窗）."""
        if not IS_WIN: return []
        ps = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.Name -eq 'HotZoneFM.exe' -or ($_.CommandLine -and $_.CommandLine -like '*vs_hz_boot*')) } | "
              "Select-Object ProcessId,Name,CommandLine,ExecutablePath | ConvertTo-Json -Compress")
        try:
            p = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps], capture_output=True, timeout=40, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
            d = json.loads(p.stdout.decode('utf-8', 'replace').strip() or '[]')
            d = d if isinstance(d, list) else [d]
            return [x for x in d if int(x.get('ProcessId') or 0) != os.getpid()]
        except Exception as ex:
            self.E.log.w(f'🔥 HotZone：查不到還開著的 HotZone 程式（{ex}）'); return []

    def close_procs(self, prog=None):
        """關掉還開著的 HotZone 視窗／HotZoneFM.exe（它們會鎖住 Data\\ 裡的檔案）。回傳關不掉的."""
        left = []
        for x in self.hz_procs():
            pid = int(x.get('ProcessId') or 0); nm = x.get('Name') or ''
            if prog: prog(f'關掉還開著的 HotZone 程式：{nm}（PID {pid}）…')
            try: subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True, timeout=20, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
            except Exception: pass
        time.sleep(1.5)
        for x in self.hz_procs(): left.append(f"{x.get('Name')}（PID {x.get('ProcessId')}）")
        if left: self.E.log.w(f'🔥 HotZone 整合：這些程式關不掉（可能是系統管理員身分在跑）：{left}')
        return left

    def _copy_one(self, a_, z, tries=5):
        """複製一個檔：被占用就等一下再試；目的地唯讀先拿掉唯讀；SQLite 用 backup（連 WAL 一起、資料一致）."""
        last = None
        for k in range(tries):
            try:
                if os.path.exists(self._lp(z)):
                    try: os.chmod(self._lp(z), 0o666)
                    except Exception: pass
                if a_.suffix.lower() in ('.sqlite3', '.sqlite', '.db'):
                    try:
                        import sqlite3
                        for ext in ('-wal', '-shm', '-journal'):
                            try: os.remove(self._lp(str(z) + ext))
                            except FileNotFoundError: pass
                        tmpz = str(z) + '.vs_tmp'
                        try: os.remove(self._lp(tmpz))
                        except FileNotFoundError: pass
                        sc = sqlite3.connect('file:' + urllib.request.pathname2url(os.path.abspath(str(a_))) + '?mode=ro', uri=True, timeout=10); dc = sqlite3.connect(self._lp(tmpz))
                        try: sc.backup(dc)
                        finally: dc.close(); sc.close()
                        os.replace(self._lp(tmpz), self._lp(z))
                        try: st = os.stat(self._lp(a_)); os.utime(self._lp(z), (st.st_atime, st.st_mtime))
                        except Exception: pass
                        return None
                    except Exception as ex:
                        self.E.log.w(f'🔥 HotZone 整合：{a_.name} 用 SQLite 備份方式失敗（{ex}），改成直接複製（連 -wal／-shm 一起）')
                        for ext in ('-wal', '-shm'):
                            if os.path.exists(self._lp(str(a_) + ext)): shutil.copy2(self._lp(str(a_) + ext), self._lp(str(z) + ext))
                shutil.copy2(self._lp(a_), self._lp(z))
                return None
            except FileNotFoundError as ex:
                if not os.path.exists(self._lp(a_)): return 'gone'
                last = ex
            except OSError as ex: last = ex
            time.sleep(min(0.5 * (2 ** k), 4))
        return last

    def _same(self, a_, z):
        try:
            sa, sz = os.stat(self._lp(a_)), os.stat(self._lp(z))
            if a_.suffix.lower() in ('.sqlite3', '.sqlite', '.db'):                  # 用 backup 複製的，大小會不一樣：看修改時間，還有 -wal 有沒有變
                w = Path(str(a_) + '-wal')
                return abs(sa.st_mtime - sz.st_mtime) < 2.5 and (not w.exists() or w.stat().st_mtime <= sz.st_mtime + 2.5)
            return sa.st_size == sz.st_size and abs(sa.st_mtime - sz.st_mtime) < 2.5
        except Exception: return False

    def set_root(self, d, before=None):
        with self.life: return self._set_root(d, before)                             # 同時只做一件（手機和電腦同時按不會開兩個引擎）

    def _set_root(self, d, before=None):
        """換 HotZone 資料夾：引擎在跑、但用的是別的資料夾 → 停掉、用新的資料夾重新啟動（嵌著的畫面也重開）."""
        d = os.path.normpath(os.path.abspath(str(d))); self._root_cache = None
        self.set_cfg(root=d, keep_orig=False) if not self._is_home(d) else self.set_cfg(root=d)
        self.E.log.w(f'🔥 HotZone：改用資料夾 {d}')
        pg = self.ping(fresh=True)
        if not pg: return {'ok': True, 'message': f'改用 {d}；按「▶ 啟動」就會用這裡的資料'}
        if os.path.normcase(os.path.abspath(str(pg.get('root') or ''))) == os.path.normcase(d): return {'ok': True, 'message': f'改用 {d}（背景引擎本來就用這裡）'}
        if before:
            try: before()
            except Exception: pass
        r = self.stop('換資料夾：')
        if not r['ok']: return r
        if not self.wait_engine_gone(pg, 120): return {'ok': False, 'message': '原本在跑的 HotZone 沒有結束，等一下再按一次「▶ 啟動」'}
        r = self.start('換資料夾後'); return {'ok': r['ok'], 'message': f'改用 {d}，背景引擎重新啟動：' + r['message']}

    def keep_original(self):
        """不複製：直接用原本的 HotZone 資料夾（之後不再提醒整合）."""
        r = self.root(); self.set_cfg(root=str(r), keep_orig=True)
        self.E.log.w(f'🔥 HotZone：選擇直接用原本的資料夾 {r}（不整合）')
        return {'ok': True, 'message': f'好，之後直接用原本的 HotZone 資料夾：{r}（設定、佇列、熱區、索引都照舊）'}

    def migrate(self, progress=None, before=None, _pre=False):
        with self.life:
            if self.migrating and not _pre: return {'ok': False, 'message': '已經在整合了，等它做完'}
            self.migrating = True; self.mig_msg = '開始整合…'
        def prog(m):
            self.mig_msg = m
            if progress:
                try: progress(m)
                except Exception: pass
        try:
            with self.life: r = self._migrate(prog, before or self.ui_before)   # 整合中，別的啟動／接手／換資料夾等它做完
        except Exception as ex:
            self.E.log.err('🔥 HotZone 整合'); r = {'ok': False, 'message': f'整合時出錯：{ex}（原本的資料夾沒動，照舊使用；LOG 有詳細）'}
        finally: self.migrating = False
        self.mig_last = dict(r, t=time.time()); self.mig_msg = ''
        return r

    def run_job(self, name, fn):
        """手機按的、會等很久的動作：背景做（同時只做一個），結果放 self.job（status() 看得到）."""
        j = self.job or {}
        if j.get('running'): return {'ok': False, 'message': f'上一個動作（{j.get("name")}）還在做，等一下'}
        self.job = {'name': name, 'running': True, 't0': time.time(), 'result': None}
        def go():
            try: r = fn()
            except Exception as ex: self.E.log.err(f'🔥 HotZone {name}'); r = {'ok': False, 'message': f'出錯：{ex}'}
            self.job = {'name': name, 'running': False, 't0': self.job.get('t0'), 't1': time.time(), 'result': r}
        threading.Thread(target=go, name='VsHzJob', daemon=True).start()
        return {'ok': True, 'job': True, 'message': '處理中…'}

    def migrate_bg(self, by='手機'):
        """手機按整合：在背景做，狀態看 status()['mig_msg'／'mig_last']."""
        with self.life:
            if self.migrating: return {'ok': False, 'message': '已經在整合了'}
            self.migrating = True; self.mig_msg = '開始整合…'                    # 先標起來：連按兩下不會開兩個
        self.E.log.w(f'🔥 HotZone：{by}按了整合')
        threading.Thread(target=lambda: self.migrate(_pre=True), name='VsHzMigrate', daemon=True).start()
        return {'ok': True, 'message': '開始整合（電腦上的 HotZone 畫面會先關掉，好了會自動重開）'}

    def _migrate(self, progress=None, before=None):
        """把目前用的 HotZone 資料夾（Data\\ 設定、搬檔佇列、熱區、索引、保管區紀錄；LOG\\）複製到 VideoSift\\HotZone\\，之後改用那裡。
        原本的資料夾不刪（留一個說明檔），背景引擎先停、複製好再用新的位置啟動。
        V0.1.76：先關掉所有鎖住檔案的 HotZone 程式；一個一個檔複製，被占用的會等一下再試，SQLite 用備份方式；不會因為一個檔失敗整個中斷，
        最後列出哪些沒複製到、為什麼（LOG\\hotzone_migrate_*.txt）；再按一次只補沒複製到的。"""
        src = Path(os.path.abspath(str(self.root()))); dst = Path(os.path.abspath(str(self.home())))
        if self.migrated(): return {'ok': True, 'message': 'HotZone 的資料已經在 SortCut 裡了'}
        if self._is_home(src): return {'ok': False, 'message': f'還沒找到原本的 HotZone 資料夾（現在暫用 {dst}）：先按「📁 HotZone 資料夾…」選原本的（有 HotZoneFM.exe 或 Data\\settings.json 的那個），或按「🩺 連線診斷」看找到了哪些'}
        if not (src / 'Data').exists(): return {'ok': False, 'message': f'{src} 裡沒有 Data 資料夾，沒有東西可以整合（按「📁 HotZone 資料夾…」選原本的 HotZone 資料夾）'}
        try:
            if os.path.normcase(os.path.abspath(str(dst))).startswith(os.path.normcase(os.path.abspath(str(src))) + os.sep):
                return {'ok': False, 'message': f'SortCut 的 HotZone 資料夾 {dst} 在原本的 HotZone 資料夾裡面，不能這樣複製'}
        except Exception: pass
        prog = progress or (lambda m: None)
        self.E.log.w(f'🔥 HotZone 整合開始：{src} → {dst}')
        pg0 = self.ping(fresh=True); was = bool(pg0)
        if was:
            prog('先停 HotZone 背景引擎（做到一半的搬檔，換位置後會接著做）…')
            r = self.stop('整合：')
            if not r['ok']: return r
            if not self.wait_engine_gone(pg0, 150, prog): return {'ok': False, 'message': 'HotZone 背景引擎 2 分半內沒有完全結束（可能在搬大檔或存索引），等一下再按一次'}
        if before:
            prog('關掉 SortCut 裡嵌著的 HotZone 畫面（它會鎖住 Data\\webview 裡的檔案）…')
            try: before()
            except Exception as ex: self.E.log.w(f'🔥 HotZone 整合：關嵌入畫面失敗 {ex}')
        left = self.close_procs(prog)
        time.sleep(1)
        # 先數一下要複製多少
        prog('清點要複製的檔案…')
        todo = []; tot = 0
        for sub in ('Data', 'LOG'):
            s_ = src / sub
            if not s_.exists(): continue
            for dp, dns, fns in os.walk(self._lp(s_)):
                dns[:] = [d for d in dns if d not in self.MIG_SKIP]
                dpp = Path(('\\\\' + dp[8:]) if dp.startswith('\\\\?\\UNC\\') else dp[4:] if dp.startswith('\\\\?\\') else dp); rel = dpp.relative_to(src)
                for fn in fns:
                    if fn.endswith(('-wal', '-shm', '-journal')) and (dpp / fn.rsplit('-', 1)[0]).suffix.lower() in ('.sqlite3', '.sqlite', '.db') and (dpp / fn.rsplit('-', 1)[0]).exists(): continue
                    try: sz = os.stat(self._lp(dpp / fn)).st_size
                    except Exception: sz = 0
                    todo.append((dpp / fn, rel / fn, sz)); tot += sz
        try:
            free = shutil.disk_usage(str(dst.parent if dst.parent.exists() else Path(getattr(self.E, 'root', '.')))).free
            if free < tot * 1.1 + 200 * 1048576:
                if was: self.start('整合失敗後')
                return {'ok': False, 'message': f'{dst} 所在的磁碟空間不夠：要 {tot / 1048576:,.0f} MB，只剩 {free / 1048576:,.0f} MB（原本的資料夾沒動，照舊使用）'}
        except Exception: pass
        mark = dst / '.vs_migrating'
        if (dst / 'Data').exists() and not mark.exists() and any((dst / 'Data').iterdir()):
            old = dst / f'Data.舊_{time.strftime("%Y%m%d_%H%M%S")}'; k = 2
            while old.exists(): old = dst / f'Data.舊_{time.strftime("%Y%m%d_%H%M%S")}_{k}'; k += 1
            try: os.replace(str(dst / 'Data'), str(old)); self.E.log.w(f'🔥 HotZone 整合：{dst}\\Data 本來就有東西（之前全新開始用過？），先改名成 {old.name} 留著')
            except Exception as ex: return {'ok': False, 'message': f'{dst}\\Data 本來就有東西，又沒辦法改名留著（{self._why(ex)}）：請先關掉 HotZone 視窗再試'}
        dst.mkdir(parents=True, exist_ok=True)
        try: mark.write_text(f'{time.time()}\n{src}\n', encoding='utf-8')
        except Exception: pass
        n = skipped = 0; b = 0; fails = []; opt_fails = []; gone = 0; t0 = time.time(); last_p = 0
        for a_, rel, sz in todo:
            z = dst / rel; optional = (len(rel.parts) > 1 and rel.parts[0] == 'Data' and rel.parts[1] in self.MIG_OPTIONAL) or rel.parts[0] == 'LOG'
            try: os.makedirs(self._lp(z.parent), exist_ok=True)
            except Exception as ex: (opt_fails if optional else fails).append((str(rel), self._why(ex))); continue
            if self._same(a_, z): skipped += 1; b += sz; continue
            ex = self._copy_one(a_, z)
            if ex == 'gone': gone += 1; continue
            if ex is not None:
                (opt_fails if optional else fails).append((str(rel), self._why(ex))); continue
            n += 1; b += sz
            if time.time() - last_p > 0.7:
                last_p = time.time(); pct = b * 100 / tot if tot else 100
                prog(f'複製中… {pct:.0f}%（{n + skipped:,} / {len(todo):,} 個檔案，{b / 1048576:,.0f} / {tot / 1048576:,.0f} MB）　{rel}')
        rep = Path(getattr(self.E, 'root', '.')) / 'LOG' / f'hotzone_migrate_{time.strftime("%Y%m%d_%H%M%S")}.txt'
        try:
            rep.parent.mkdir(parents=True, exist_ok=True)
            rep.write_text(f'HotZone 整合 {time.strftime("%Y-%m-%d %H:%M:%S")}\n從 {src}\n到 {dst}\n共 {len(todo)} 個檔案（{tot / 1048576:.1f} MB）：這次複製 {n}、之前就複製好 {skipped}、複製時不見 {gone}\n'
                           f'關不掉的程式：{left or "沒有"}\n\n必要的檔案沒複製到 {len(fails)} 個：\n' + '\n'.join(f'  {r_}　← {w}' for r_, w in fails) +
                           f'\n\n可以不要的（暫存、縮圖、LOG）沒複製到 {len(opt_fails)} 個：\n' + '\n'.join(f'  {r_}　← {w}' for r_, w in opt_fails) + '\n', encoding='utf-8')
        except Exception: rep = None
        self.E.log.w(f'🔥 HotZone 整合：{len(todo)} 個檔，複製 {n}、已有 {skipped}、不見 {gone}、必要的失敗 {len(fails)}、可略過的失敗 {len(opt_fails)}，{time.time() - t0:.0f} 秒' + (f'；明細 {rep}' if rep else ''))
        for r_, w in fails[:30]: self.E.log.w(f'🔥 HotZone 整合沒複製到：{r_}　← {w}')
        if fails:
            if was: self.start('整合失敗後')
            why = {}
            for _r, w in fails: why[w] = why.get(w, 0) + 1
            top = '；'.join(f'{w} {k} 個' for w, k in sorted(why.items(), key=lambda x: -x[1]))
            ex_ = '、'.join(r_ for r_, _w in fails[:4])
            hint = '關掉所有 HotZone 視窗（包括原本的 HotZoneFM.exe）再按一次' if any('占用' in w or '權限' in w for w in why) else '看明細再處理'
            if left: hint = f'還有 {"、".join(left)} 關不掉（可能是系統管理員身分在跑）：先從工作管理員結束它，再按一次'
            return {'ok': False, 'fails': [{'file': r_, 'why': w} for r_, w in fails[:200]], 'report': str(rep or ''),
                    'message': f'還有 {len(fails)} 個檔案沒複製到（{top}），例如 {ex_}。{hint}；已經複製好的 {n + skipped:,} 個下次不用重來。'
                               f'原本的資料夾沒動，照舊使用。也可以按「就用原本的資料夾」不整合。' + (f'明細：{rep}' if rep else '')}
        try: mark.unlink()
        except Exception: pass
        try:
            (src / '已經整合進VideoSift.txt').write_text(f'{time.strftime("%Y-%m-%d %H:%M")} 這個資料夾的 HotZone 資料已經複製到 {dst}，之後 SortCut 用那裡的。\n'
                                                     '這裡的檔案留著當備份（確定沒問題可以刪）。請不要再開這裡的 HotZoneFM.exe，免得兩邊各改各的。\n', encoding='utf-8')
        except Exception: pass
        self.set_cfg(root=str(dst), migrated_from=str(src), migrated_t=time.time(), keep_orig=False); self._ping = (0, None); self.cookie = ''
        self.E.log.w(f'🔥 HotZone 整合：{src} → {dst}（{n + skipped:,} 個檔案，{b / 1048576:.0f} MB），之後用 SortCut 裡的資料')
        msg = f'整合好了：{n + skipped:,} 個檔案（{b / 1048576:,.0f} MB）在 {dst}，之後都用這裡的。原本的資料夾留著當備份'
        if opt_fails: msg += f'（{len(opt_fails)} 個暫存／縮圖／LOG 檔沒複製到，不影響，HotZone 會重新產生）'
        if was:
            r = self.start('整合後'); msg += '；' + r['message']
        return {'ok': True, 'message': msg, 'report': str(rep or '')}

    def root_info(self, p):
        """一個 HotZone 資料夾的概況：有沒有設定、佇列幾筆、索引、最後改動時間（讓你分得出哪個才是平常在用的）."""
        p = Path(p); d = {'path': str(p), 'exe': (p / 'HotZoneFM.exe').exists(), 'settings': (p / 'Data' / 'settings.json').exists(), 'queue': 0, 'mb': 0.0, 't': 0}
        try:
            q = p / 'Data' / 'queue'
            if q.exists(): d['queue'] = sum(1 for x in q.iterdir() if x.is_file())
        except Exception: pass
        try:
            for x in (p / 'Data').iterdir():
                try:
                    st = x.stat(); d['t'] = max(d['t'], st.st_mtime)
                    if x.is_file(): d['mb'] += st.st_size / 1048576
                except Exception: pass
        except Exception: pass
        d['migrated_mark'] = (p / '已經整合進VideoSift.txt').exists()
        return d

    def diagnose(self):
        """🩺 連線診斷：一步一步檢查為什麼連不上原本的 HotZone 資料."""
        R = []; add = lambda ok, t: R.append({'ok': ok, 'text': t})
        c = self.cfg(); r = self.root()
        src = '還沒找到原本的，暫用 SortCut 裡的' if self._is_home(r) and not self.migrated() else '你設定的' if c.get('root') else '自動找到的'
        add(self.looks_like_root(r), f'HotZone 資料夾（{src}）：{r}' + ('' if self.looks_like_root(r) else '　← 這裡沒有 HotZoneFM.exe 或 Data\\settings.json：不是原本的 HotZone 資料夾'))
        ri = self.root_info(r)
        add(ri['settings'], f"設定檔 Data\\settings.json：{'有' if ri['settings'] else '沒有'}；搬檔佇列 {ri['queue']} 筆；Data 根目錄 {ri['mb']:.1f} MB；最後改動 " + (time.strftime('%Y-%m-%d %H:%M', time.localtime(ri['t'])) if ri['t'] else '—'))
        add(bool(self.token()), '登入用的 Data\\local_token.txt：' + ('有' if self.token() else '沒有（HotZone 引擎第一次啟動時才會產生）'))
        try: cand = [x for x in self.root_candidates() if os.path.normcase(str(x)) != os.path.normcase(str(r))]
        except Exception: cand = []
        self.cands = [self.root_info(x) for x in cand[:8]]
        for x in cand[:6]:
            i2 = self.root_info(x)
            add(None, f"另外也找到 HotZone 資料夾：{x}（佇列 {i2['queue']} 筆，最後改動 " + (time.strftime('%Y-%m-%d %H:%M', time.localtime(i2['t'])) if i2['t'] else '—') + '）' + ('　← 這個比較新，可能才是平常在用的：按它旁邊的「用這個」' if i2['t'] > ri['t'] + 60 else ''))
        pg = self.ping(fresh=True)
        if not pg: add(False, 'HotZone 背景引擎：沒有在跑（連接埠 8765～8770 都沒回應）→ 按「▶ 啟動背景引擎」，Windows 問系統管理員權限要按「是」')
        else:
            same = os.path.normcase(os.path.abspath(str(pg.get('root') or ''))) == os.path.normcase(os.path.abspath(str(r)))
            add(True, f"HotZone 背景引擎：在跑（{'SortCut 跑的' if pg.get('mode') == 'videosift' else '原本的 HotZoneFM.exe'}，V{pg.get('ver', '')}，連接埠 {pg.get('port')}）")
            add(same, f"引擎用的資料夾：{pg.get('root') or '（沒回報）'}" + ('' if same else f'　← 跟 SortCut 設定的 {r} 不一樣！按「🔁 接手」或重新啟動讓它用同一個'))
            try: ok = self._login(pg['port']); add(ok, '登入引擎：' + ('成功' if ok else f'失敗（{self.last_err or "local_token.txt 對不上"}）'))
            except Exception as ex: add(False, f'登入引擎：失敗（{ex}）')
        e = self.env or {}
        add(bool(e.get('ok')) if e else None, 'Python 環境：' + (f"Python {e.get('py')}，套件{'齊了' if e.get('ok') else '不齊（按「📦 安裝需要的套件」）'}" if e.get('py') else '還沒檢查（按「🔍 檢查環境」）'))
        if IS_WIN:
            P = self.hz_procs()
            add(None, '電腦上開著的 HotZone 程式：' + ('、'.join(f"{x.get('Name')}（PID {x.get('ProcessId')}）" for x in P) if P else '沒有'))
        mk = self.home() / '.vs_migrating'
        if mk.exists() and not self.migrated(): add(False, f'上次整合沒做完（{self.home()} 裡有一半）：再按一次「📦 整合」只補沒複製到的')
        try:
            reps = sorted((Path(getattr(self.E, 'root', '.')) / 'LOG').glob('hotzone_migrate_*.txt'))
            if reps: add(None, f'上次整合的明細：{reps[-1]}')
        except Exception: pass
        self.E.log.w('🔥 HotZone 連線診斷：' + ' ｜ '.join(('✔' if x['ok'] else '✖' if x['ok'] is False else '•') + x['text'] for x in R))
        return {'ok': True, 'items': R, 'message': '診斷好了'}

    # ---------------------------------------------------------------- 狀態
    def status(self):
        pg = self.ping()
        st = dict(self.state) if pg else {}
        return {'running': bool(pg), 'ours': bool(pg and pg.get('mode') == 'videosift'), 'migrated': self.migrated(), 'home': str(self.home()), 'ver': (pg or {}).get('ver', ''), 'port': (pg or {}).get('port'),
                'root': str(self.root()), 'root_found': self.looks_like_root(self.root()) and (self.migrated() or not self._is_home(self.root())), 'cfg': self.cfg(), 'env': {k: v for k, v in (self.env or {}).items() if k != 'tried'},
                'installing': bool(self.installing and self.installing.poll() is None), 'admin': st.get('admin'), 'queue': st.get('queue'), 'hot': st.get('hot'),
                'hot_paused': st.get('hot_paused'), 'index': st.get('index'), 'notices': st.get('notices') or [], 'disks': st.get('disks') or [],
                'keep_orig': bool(self.cfg().get('keep_orig')), 'migrating': bool(self.migrating), 'cands': list(self.cands or []), 'job': dict(self.job or {}), 'mig_msg': self.mig_msg, 'mig_last': self.mig_last, 'other_root': bool(pg and pg.get('other_root')), 'eng_root': (pg or {}).get('root') or '', 'mig_partial': (self.home() / '.vs_migrating').exists(), 'arb': list(self.arb.values()), 'arb_log': list(self.arb_log)[-30:], 'paused_by_us': sorted(self.paused_by_us), 'err': self.last_err}

    # ---------------------------------------------------------------- 背景：狀態＋硬碟協調員
    def _loop(self):
        t_auto = 0
        while self.alive:
            try:
                if self.installing is not None and self.installing.poll() is not None:
                    self.installing = None; self.check_env()
                pg = self.ping(fresh=True)
                if pg:
                    try: self.state = self.api('/api/state', timeout=4); self.state['queue_lanes'] = (self.api('/api/queue', timeout=4) or {}).get('lanes') or []
                    except Exception as ex: self.last_err = str(ex)
                    if self.cfg().get('arb', True):
                        try: self._arbitrate()
                        except Exception: self.E.log.err('🔥 硬碟協調員')
                else:
                    self.state = {}; self.cookie = ''
                    if self.paused_by_us: self.paused_by_us = set()
                    for L in [k for k, v in list(getattr(self.E, 'lane_hold', {}).items()) if str(v[1]).startswith('🔥')]: self.E.lane_hold.pop(L, None)
                    c = self.cfg()
                    if c.get('auto') and not getattr(self, 'uac_declined', False) and time.time() - t_auto > 600 and (self.env or {}).get('ok', True):
                        t_auto = time.time(); r = self.start('開 SortCut 時自動'); self.E.log.w('🔥 HotZone 自動啟動：' + r['message'])
            except Exception:
                try: self.E.log.err('🔥 HotZone 背景')
                except Exception: pass
            for _ in range(6):
                if not self.alive: return
                time.sleep(0.5)

    def _vs_lane_activity(self):
        """SortCut 每一道（實體硬碟）現在在做什麼：user＝你排的（轉檔、初剪）；bg＝背景（預覽圖、讀資訊、掃描、人臉讀影片）."""
        E = self.E; act = {}
        lp = lambda J: J.get('lane') or E.lane_of(J.get('path') or '')
        for J in list(E.th_active.values()): act.setdefault(lp(J), set()).add('預覽圖')
        for J in list(E.cv_active.values()): act.setdefault(lp(J), set()).add('轉檔')
        for L, n in list(getattr(E, 'pr_lanes', {}).items()):
            if n: act.setdefault(L, set()).add('讀影片資訊')
        s = getattr(E, 'scan_st', {})
        if s.get('running') and s.get('lane'): act.setdefault(s['lane'], set()).add('掃描')
        cut = getattr(E, 'cut_cur', None)
        if cut: act.setdefault(E.lane_of(cut.get('path') or ''), set()).add('初剪')
        return act

    def _arbitrate(self):
        E = self.E; c = self.cfg(); now = time.time(); st = self.state
        disks = {int(d.get('n')): d for d in st.get('disks') or [] if d.get('n') is not None}
        qlanes = {L.get('lane'): L for L in st.get('queue_lanes') or []}
        hot_letters = {str(h.get('letter') or '').upper().rstrip(':\\') for h in st.get('hot') or [] if str(h.get('state') or '') in ('moving', 'evicting', 'planning')}
        vs = self._vs_lane_activity(); seen = set()
        hold = getattr(E, 'lane_hold', None)
        if hold is None: E.lane_hold = hold = {}
        for L, kinds in vs.items():
            try:
                if E.drives.media(L) != 'HDD': continue
                nums = [int(n) for n in E.drives.disk_nums(L)]
            except Exception: continue
            for n in nums:
                d = disks.get(n)
                if not d: continue
                seen.add(n)
                ours = float(d.get('ours') or 0); busy = float(d.get('busy') or 0)
                q = qlanes.get(f'd{n}') or {}; hz_queue = int(q.get('running') or 0) > 0
                letters = [str(x).upper().rstrip(':\\') for x in d.get('letters') or []]
                hz_hot = any(x in hot_letters for x in letters)
                hz_on = ours >= float(c.get('hz_mbps') or 3) * 1048576 or hz_queue
                label = (letters[0] + ':') if letters else f'硬碟 {n}'
                if hz_on and busy >= float(c.get('busy_pct') or 85):
                    self.cont.setdefault(n, now)
                else:
                    if n in self.cont and now - self.cont[n] > 0: self.cont.pop(n, None)
                if n in self.cont and now - self.cont[n] >= 15:                 # 兩邊一起用、忙碌一直很高 15 秒以上 → 只讓一邊做
                    vs_user = bool(kinds & {'轉檔', '初剪'})
                    hz_what = '搬檔佇列' if hz_queue else ('熱區搬移' if hz_hot else '背景（圖片分析／索引）')
                    if hz_queue and not vs_user: owner, why = 'hz', f'HotZone 正在跑你排的{hz_what}，SortCut 的{"、".join(sorted(kinds))}先等'
                    elif vs_user and not hz_queue: owner, why = 'vs', f'SortCut 正在跑你排的{"、".join(sorted(kinds & {"轉檔", "初剪"}))}，HotZone 的{hz_what}先暫停'
                    elif hz_queue and vs_user: owner, why = 'hz', f'兩邊都是你排的工作：先讓 HotZone 的搬檔做完，SortCut 的{"、".join(sorted(kinds))}先等'
                    else:
                        so = self.slice_owner.get(n)
                        if not so or now - so[1] >= max(1, int(c.get('slice_min') or 10)) * 60:
                            nxt = 'hz' if (so and so[0] == 'vs') else 'vs'; self.slice_owner[n] = so = (nxt, now)
                        owner = so[0]; mins = int(c.get('slice_min') or 10)
                        why = (f'兩邊的背景工作輪流（每 {mins} 分鐘換一次）：現在輪到 ' + ('SortCut 的' + '、'.join(sorted(kinds)) + f'，HotZone 的{hz_what}先暫停' if owner == 'vs'
                               else f'HotZone 的{hz_what}，SortCut 的' + '、'.join(sorted(kinds)) + '先等'))
                    prev = self.arb.get(n)
                    if not prev or prev['owner'] != owner:
                        self.arb_log.append({'t': now, 'disk': label, 'owner': owner, 'why': why})
                        E.log.w(f'🔥 硬碟協調：{label}（忙碌 {busy:.0f}%，HotZone {ours / 1048576:.1f} MB/s）→ {why}')
                    self.arb[n] = {'n': n, 'disk': label, 'owner': owner, 'why': why, 'since': prev['since'] if prev and prev['owner'] == owner else now, 't': now,
                                   'busy': busy, 'hz_mbps': round(ours / 1048576, 1), 'lane': L}
        for n, a in list(self.arb.items()):                                     # 套用
            if now - a['t'] > 60: self.arb.pop(n, None); self.arb_log.append({'t': now, 'disk': a['disk'], 'owner': '', 'why': '不再搶硬碟，兩邊照常做'}); E.log.w(f'🔥 硬碟協調：{a["disk"]} 不再搶了，兩邊照常做'); continue
            if a['owner'] == 'hz': hold[a['lane']] = (now + 20, '🔥 ' + a['why'])
            elif str((hold.get(a['lane']) or (0, ''))[1]).startswith('🔥'): hold.pop(a['lane'], None)
        for L in [k for k, v in list(hold.items()) if str(v[1]).startswith('🔥') and not any(a['lane'] == k and a['owner'] == 'hz' for a in self.arb.values())]: hold.pop(L, None)
        want_pause = any(a['owner'] == 'vs' for a in self.arb.values())
        if want_pause:
            if 'hot' not in self.paused_by_us and not st.get('hot_paused'):
                try: self.api('/api/hot/pause', {'on': True}); self.paused_by_us.add('hot'); E.log.w('🔥 硬碟協調：HotZone 熱區搬移暫停（協調員暫停的，不搶了會自動繼續）')
                except Exception as ex: self.last_err = str(ex)
            if 'images' not in self.paused_by_us:
                try:
                    im = self.api('/api/images/status', timeout=4) or {}
                    if not im.get('paused'): self.api('/api/images/pause', {'on': True}); self.paused_by_us.add('images'); E.log.w('🔥 硬碟協調：HotZone 圖片分析暫停')
                except Exception as ex: self.last_err = str(ex)
        elif self.paused_by_us:
            for k, path in (('hot', '/api/hot/pause'), ('images', '/api/images/pause')):
                if k in self.paused_by_us:
                    try: self.api(path, {'on': False})
                    except Exception: pass
            E.log.w('🔥 硬碟協調：不搶了，HotZone 的' + '、'.join({'hot': '熱區搬移', 'images': '圖片分析'}[k] for k in sorted(self.paused_by_us)) + '繼續'); self.paused_by_us = set()

    def shutdown(self):
        """SortCut 結束：HotZone 引擎繼續跑（跟原本一樣），只把協調員暫停的東西放回去."""
        self.alive = False
        if self.paused_by_us and self.ping():
            for k, path in (('hot', '/api/hot/pause'), ('images', '/api/images/pause')):
                if k in self.paused_by_us:
                    try: self.api(path, {'on': False}, timeout=2)
                    except Exception: pass
        self.paused_by_us = set()

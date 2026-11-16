"""HotZone FM — update packages and hot update (same idea as TikLive Monitor).

Package  v0.1.1_Update.zip:
    manifest.json            {"version": "0.1.1", "requires_launcher": 1}
    app/<files>              hz_*.py, ui.html, ui.js, ui.css, CHANGELOG.json ...
    launcher.py (optional)   only used when running from source; the EXE launcher needs a full package

Apply:   syntax check every .py  ->  copy app\\ to app_backup\\<time>_before_V<new>  ->  write the new files
Reload:  the new modules are loaded next to the running ones; the running engine stops at a safe point
         (copies keep their partial file, relocation finishes its current chunk), hands its state over, and the
         new engine continues. If the new code fails to load or start, the backup is put back and the old
         engine continues. The window only reloads its page.
"""
from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import re
import shutil
import sys
import threading
import time
import traceback
import zipfile
from pathlib import Path

from hz_common import APP_DIR, BACKUP_DIR, UPDATE_DIR, DATA_DIR, ROOT, LOG_DIR, APP_VERSION, read_json, atomic_write_json

ALLOWED = re.compile(r'^[A-Za-z0-9_.\-]+\.(py|html|js|css|json|txt|md|svg|png|ico|woff2|webmanifest)$')
LAUNCHER_VERSION_NEEDED = 1


def vtuple(v):
    return tuple(int(x) for x in re.findall(r'\d+', str(v or ''))) or (0,)


def read_package(src) -> dict:
    """Validate an update package (path or bytes). Nothing is written. Raises ValueError with a readable reason."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else src)
    except zipfile.BadZipFile:
        raise ValueError('不是有效的 zip 檔')
    with zf:
        names = zf.namelist()
        manifest = {}
        if 'manifest.json' in names:
            try: manifest = json.loads(zf.read('manifest.json').decode('utf-8-sig'))
            except Exception: raise ValueError('manifest.json 讀不懂')
        files = {}; launcher = None
        for m in names:
            if m.endswith('/'): continue
            if m.startswith('app/'):
                name = m[4:]
                if '/' in name or '\\' in name or '..' in name or not ALLOWED.match(name): raise ValueError(f'不允許的檔案：{m}')
                files[name] = zf.read(m)
            elif m == 'launcher.py':
                launcher = zf.read(m)
    if 'hz_engine.py' not in files and 'ui.js' not in files and not files:
        raise ValueError('更新包裡沒有 app/ 程式檔')
    for name, data in files.items():
        if name.endswith('.py'):
            try: compile(data.decode('utf-8'), name, 'exec')
            except SyntaxError as e: raise ValueError(f'{name} 第 {e.lineno} 行語法錯誤：{e.msg}')
    if launcher is not None:
        compile(launcher.decode('utf-8'), 'launcher.py', 'exec')
    need = int(manifest.get('requires_launcher', 1) or 1)
    rt = sys.modules.get('_hz_rt'); have = int(getattr(rt, 'launcher_version', 1) or 1)
    if need > have: raise ValueError(f'這個更新需要新版啟動器（{need}），請用完整安裝包更新')
    ver = str(manifest.get('version') or '')
    if not ver and 'hz_common.py' in files:
        m = re.search(r"APP_VERSION\s*=\s*'([^']+)'", files['hz_common.py'].decode('utf-8', 'ignore')); ver = m.group(1) if m else '?'
    notes = []
    try:
        log = json.loads(files['CHANGELOG.json'].decode('utf-8-sig')) if 'CHANGELOG.json' in files else []
        entry = next((e for e in log if str(e.get('version')) == ver), None)
        notes = list((entry or {}).get('items', []))
    except Exception:
        pass
    changed = []
    for name, data in files.items():
        cur = APP_DIR / name
        if not cur.exists() or hashlib.sha256(cur.read_bytes()).hexdigest() != hashlib.sha256(data).hexdigest(): changed.append(name)
    direction = 'up' if vtuple(ver) > vtuple(APP_VERSION) else ('same' if vtuple(ver) == vtuple(APP_VERSION) else 'down')
    return {'version': ver, 'files': files, 'launcher': launcher, 'notes': notes, 'changed': sorted(changed), 'direction': direction,
            'shell_changed': 'hz_shell.py' in changed, 'from': APP_VERSION}


def public(pkg):
    return {k: v for k, v in pkg.items() if k not in ('files', 'launcher')} | {'nfiles': len(pkg.get('files', {})), 'has_launcher': pkg.get('launcher') is not None}


MARKER = APP_DIR / '.update_in_progress.json'      # written before the first file is replaced, removed after the last


def backup_app(tag):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    t_ = time.time()                                    # same name format as the launcher's backups (they sort together)
    dst = BACKUP_DIR / (time.strftime('%Y%m%d_%H%M%S', time.localtime(t_)) + f'{int(t_ * 1000) % 1000:03d}_' + re.sub(r'[^A-Za-z0-9_.-]+', '_', tag))
    k = 2
    while dst.exists(): dst = dst.with_name(dst.name.split('#')[0] + f'#{k}'); k += 1
    shutil.copytree(APP_DIR, dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.new'))
    prune_backups()
    return dst


def prune_backups(keep=20):
    try:
        bs = sorted([d for d in BACKUP_DIR.iterdir() if d.is_dir()], key=lambda d: d.name)
        for d in bs[:-keep]: shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass


def _write_durable(path: Path, data: bytes):
    with open(path, 'wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())


def write_files(files: dict, launcher=None, backup: Path = None, version=''):
    """All or nothing: every new file is first written beside its target (.new, on the disk), then they are swapped
    in. A failure on the way puts the backup back; a crash on the way leaves MARKER, and the next start restores."""
    targets = [(APP_DIR / name, data) for name, data in files.items()]
    if launcher is not None and (ROOT / 'launcher.py').exists(): targets.append((ROOT / 'launcher.py', launcher))
    try:
        for dst, data in targets: _write_durable(dst.with_name(dst.name + '.new'), data)
        if backup is not None: _write_durable(MARKER, json.dumps({'backup': str(backup), 'version': version, 't': time.time()}).encode())
        for dst, _d in targets: os.replace(dst.with_name(dst.name + '.new'), dst)
        try: MARKER.unlink()
        except FileNotFoundError: pass
    except Exception:
        if backup is not None: restore_backup(backup)
        raise
    finally:
        for dst, _d in targets:
            try: dst.with_name(dst.name + '.new').unlink()
            except OSError: pass
        shutil.rmtree(APP_DIR / '__pycache__', ignore_errors=True)


def restore_backup(backup: Path):
    """app\\ exactly as in the backup: its files back, files it did not have moved aside (an added ui_*.js or a .pyd would
    otherwise keep loading after a rollback)."""
    backup = Path(backup); keep = {f.name for f in backup.iterdir() if f.is_file()}
    for f in backup.iterdir():
        if f.is_file(): shutil.copy2(f, APP_DIR / f.name)
    extra = [f for f in APP_DIR.iterdir() if f.is_file() and f.name not in keep and f.name != MARKER.name and not f.name.endswith('.new')]
    if extra:
        aside = ROOT / 'app_removed' / time.strftime('%Y%m%d_%H%M%S'); aside.mkdir(parents=True, exist_ok=True)   # not among the backups
        for f in extra:
            try: shutil.move(str(f), aside / f.name)
            except OSError: pass
    try: MARKER.unlink()
    except FileNotFoundError: pass
    shutil.rmtree(APP_DIR / '__pycache__', ignore_errors=True)


def list_backups():
    out = []
    if not BACKUP_DIR.exists(): return out
    for d in sorted(BACKUP_DIR.iterdir(), key=lambda d: d.name, reverse=True):
        if not d.is_dir(): continue
        ver = '?'
        try:
            m = re.search(r"APP_VERSION\s*=\s*'([^']+)'", (d / 'hz_common.py').read_text(encoding='utf-8', errors='ignore')); ver = m.group(1) if m else '?'
        except Exception:
            pass
        out.append({'name': d.name, 'version': ver, 't': d.stat().st_mtime})
    return out


def package_from_backup(name):
    d = BACKUP_DIR / name
    if not d.is_dir() or '..' in name or '/' in name or '\\' in name: raise ValueError('找不到這個備份')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        ver = '?'
        try:
            m = re.search(r"APP_VERSION\s*=\s*'([^']+)'", (d / 'hz_common.py').read_text(encoding='utf-8', errors='ignore')); ver = m.group(1) if m else '?'
        except Exception:
            pass
        zf.writestr('manifest.json', json.dumps({'version': ver, 'requires_launcher': 1}))
        for f in d.iterdir():
            if f.is_file() and ALLOWED.match(f.name): zf.write(f, 'app/' + f.name)
    pkg = read_package(buf.getvalue()); pkg['exact'] = True                 # a rollback: app\\ must become exactly that version
    return pkg


def _ulog(msg):
    try:
        with open(LOG_DIR / 'update_log.txt', 'a', encoding='utf-8') as f: f.write(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}\n')
    except Exception:
        pass


# ============================================================================================ hot reload
OUR_PREFIX = 'hz_'


class Updater:
    def __init__(self, engine):
        self.eng = engine
        self.pending = None           # validated package waiting for "apply"
        self.state = {'state': 'idle'}
        self.lock = threading.Lock()

    def load_upload(self, data: bytes, name='upload.zip'):
        pkg = read_package(data); pkg['src_name'] = name
        self.pending = pkg
        return public(pkg)

    def load_file(self, path):
        pkg = read_package(str(path)); pkg['src_name'] = Path(path).name; pkg['src_path'] = str(path)
        self.pending = pkg
        return public(pkg)

    def apply_pending(self, via='網頁'):
        if getattr(sys.modules.get('_hz_rt'), 'mode', '') == 'videosift':                # 整合進 SortCut 之後：程式跟著 SortCut 的更新包一起更新
            raise ValueError('HotZone 現在是 SortCut 的一部分：請用 SortCut 的更新包（SC_V….zip）更新，這裡不能單獨更新')
        pkg = self.pending
        if not pkg: raise ValueError('沒有待安裝的更新包')
        if not self.lock.acquire(blocking=False): raise ValueError('正在更新中')
        self.state = {'state': 'applying', 'to': pkg['version'], 't': time.time()}
        threading.Thread(target=self._apply_and_reload, args=(pkg, via), name='HZ-Update', daemon=True).start()
        return {'ok': True, 'version': pkg['version']}

    def _apply_and_reload(self, pkg, via):
        log = self.eng.log
        try:
            time.sleep(0.4)                                                   # let the HTTP answer go out first
            backup = backup_app(f'before_V{pkg["version"]}')
            write_files(pkg['files'], pkg.get('launcher'), backup, pkg['version'])
            if pkg.get('exact'):                                            # rollback: files the newer version added go aside
                extra = [f for f in APP_DIR.iterdir() if f.is_file() and f.name not in pkg['files'] and ALLOWED.match(f.name)]
                if extra:
                    aside = ROOT / 'app_removed' / time.strftime('%Y%m%d_%H%M%S'); aside.mkdir(parents=True, exist_ok=True)   # not among the backups
                    for f in extra: shutil.move(str(f), aside / f.name)
            _ulog(f'寫入 V{APP_VERSION} → V{pkg["version"]}（{via}），備份 {backup.name}，變更 {", ".join(pkg["changed"]) or "無"}')
            log.info('update', f'已寫入 V{pkg["version"]}，開始熱更新')
            atomic_write_json(DATA_DIR / 'last_update.json', {'from': APP_VERSION, 'to': pkg['version'], 'notes': pkg['notes'], 't': time.time(),
                                                             'via': via, 'shell_changed': pkg['shell_changed'], 'backup': backup.name})
            if pkg.get('src_path'):
                try:
                    (UPDATE_DIR / 'applied').mkdir(exist_ok=True)
                    shutil.move(pkg['src_path'], UPDATE_DIR / 'applied' / Path(pkg['src_path']).name)
                except Exception:
                    pass
            ok, err = hot_reload(self.eng, backup)
            self.state = {'state': 'done' if ok else 'failed', 'to': pkg['version'], 'message': err, 't': time.time(),
                          'shell_changed': pkg['shell_changed']}
            self.pending = None
        except Exception as e:
            _ulog('更新失敗\n' + traceback.format_exc())
            self.state = {'state': 'failed', 'message': str(e), 't': time.time()}
        finally:
            try: self.lock.release()
            except RuntimeError: pass


def hot_reload(old_engine, backup=None):
    """Swap the running engine for one built from the files now in app\\. -> (ok, message)."""
    rt = sys.modules.get('_hz_rt')
    saved = {n: m for n, m in sys.modules.items() if n.startswith(OUR_PREFIX)}
    for n in saved: sys.modules.pop(n, None)
    importlib.invalidate_caches()
    try:
        new_mod = importlib.import_module('hz_engine')
    except Exception:
        err = traceback.format_exc()
        _ulog('新版載入失敗，還原\n' + err)
        for n in [n for n in sys.modules if n.startswith(OUR_PREFIX)]: sys.modules.pop(n, None)
        sys.modules.update(saved)
        if backup: restore_backup(backup)
        old_engine.log.error('update', '新版無法載入，已還原目前版本：' + err.strip().splitlines()[-1])
        return False, '新版無法載入，已還原目前版本：' + err.strip().splitlines()[-1]
    # stop the old engine at a safe point, hand over, start the new one
    try:
        old_engine.stop(handoff=True)
        state = old_engine.export_state()
    except Exception:
        _ulog('停止舊版時出錯（繼續交接）\n' + traceback.format_exc())
        state = {}
    try:
        new = new_mod.Engine(adopt=state)
        new.start()
        if rt is not None: rt.engine = new; rt.gen = getattr(rt, 'gen', 0) + 1
        new.log.info('update', f'熱更新完成：V{state.get("version", "?")} → V{new_mod.APP_VERSION_ENGINE}，搬檔與熱區工作從中斷點繼續')
        _ulog(f'熱更新完成 → V{new_mod.APP_VERSION_ENGINE}')
        return True, ''
    except Exception:
        err = traceback.format_exc()
        _ulog('新版啟動失敗，還原舊版\n' + err)
        for n in [n for n in sys.modules if n.startswith(OUR_PREFIX)]: sys.modules.pop(n, None)
        sys.modules.update(saved)
        if backup: restore_backup(backup)
        try:
            again = saved['hz_engine'].Engine(adopt=state); again.start()
            if rt is not None: rt.engine = again; rt.gen = getattr(rt, 'gen', 0) + 1
        except Exception:
            _ulog('舊版也無法重新啟動！\n' + traceback.format_exc())
        return False, '新版啟動失敗，已還原：' + err.strip().splitlines()[-1]


def scan_update_folder():
    """Newest valid package in UPDATE\\ (not applied yet) -> path or None."""
    best = None
    for f in UPDATE_DIR.glob('*.zip'):
        try:
            with zipfile.ZipFile(f) as zf:
                m = json.loads(zf.read('manifest.json').decode('utf-8-sig')) if 'manifest.json' in zf.namelist() else {}
            v = str(m.get('version') or '')
            if vtuple(v) > vtuple(APP_VERSION) and (best is None or vtuple(v) > best[0]): best = (vtuple(v), f, v)
        except Exception:
            continue
    return (str(best[1]), best[2]) if best else None

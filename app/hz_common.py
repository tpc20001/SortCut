"""HotZone FM — shared basics: folders, settings, log, small helpers.

Folder layout (fixed, so an update never has to move data):
  <ROOT>\\HotZoneFM.exe      launcher (Python + PySide6, rarely rebuilt)
  <ROOT>\\app\\*.py, ui.*    program code (replaced by update packages, hot-reloaded)
  <ROOT>\\UPDATE\\*.zip      drop update packages here (applied on next launch, or from the 更新 page)
  <ROOT>\\app_backup\\...    automatic copy of app\\ before every update (rollback)
  <ROOT>\\Data\\...          settings, queue, hot folders, search index cache
  <ROOT>\\LOG\\...           human-readable logs
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

APP_NAME = 'HotZone FM'
APP_VERSION = '0.1.66'
IS_WIN = os.name == 'nt'

if os.environ.get('HZFM_ROOT'):
    ROOT = Path(os.environ['HZFM_ROOT']).resolve()
elif getattr(sys, 'frozen', False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'Data'
LOG_DIR = ROOT / 'LOG'
UPDATE_DIR = ROOT / 'UPDATE'
BACKUP_DIR = ROOT / 'app_backup'
QUEUE_DIR = DATA_DIR / 'queue'
INDEX_DIR = DATA_DIR / 'index'
for _d in (DATA_DIR, LOG_DIR, UPDATE_DIR, QUEUE_DIR, INDEX_DIR):
    try: _d.mkdir(parents=True, exist_ok=True)
    except Exception: pass

SETTINGS_FILE = DATA_DIR / 'settings.json'
LOCAL_TOKEN_FILE = DATA_DIR / 'local_token.txt'

# ---------------------------------------------------------------------------------------------- settings
DEFAULTS = {
    'ui.theme': 'dark',
    'ui.zoom': 100,
    'ui.welcomed': False,
    'system.task_v': 0,              # version of the scheduled-task definition last written            # first-run guide shown and closed
    'web.port': 8765,
    'web.remote': True,              # allow LAN / Tailscale (needs a password)
    'web.hosts': [],                 # extra host names allowed in the Host header (own domain); IPs / PC name / *.ts.net always are
    'web.pw_hash': '',               # sha256(salt + pw)
    'web.pw_salt': '',
    'web.session_days': 30,
    'transfer.max_total': 4,         # jobs running at the same time (all disks)
    'transfer.hdd_max': 1,           # jobs per physical HDD at the same time (Copy Handler style)
    'transfer.ssd_max': 2,
    'transfer.net_max': 2,
    'transfer.usage_pct': 80,        # FastCopy style: highest disk usage share for the queue (10-100)
    'transfer.disk_pct': {},         # per physical disk override {"1": 60}
    'transfer.disk_max': {},         # per physical disk override of how many jobs {"1": 2}
    'transfer.mbps_cap': 0,          # 0 = no MB/s cap
    'transfer.buffer_mb': 8,
    'transfer.write_through': True,  # Windows: write straight to disk (accurate usage control, no RAM flood)
    'transfer.verify': False,
    'transfer.preserve_times': True,
    'transfer.conflict': 'ask',      # ask / skip / overwrite / newer / rename
    'transfer.hot_first': True,      # jobs going into a hot folder jump the queue
    'transfer.yield_mbps': 0,        # pause the queue on a disk while other programs use it above this (0 = off)
    'transfer.autostart': True,      # resume unfinished jobs when the engine starts
    'transfer.keep_done': 200,       # finished jobs kept in the list
    'transfer.sched_on': False,      # daytime limits: during [from, to) hours use the lower usage % / MB/s below
    'transfer.sched_from': 9,
    'transfer.sched_to': 23,
    'transfer.sched_pct': 40,
    'transfer.sched_mbps': 0,
    'transfer.after': '',            # when the queue is empty: '' / sleep / hibernate / shutdown (one time)
    'hot.enabled': True,
    'hot.usage_pct': 60,             # relocation share of the disk (user: 60 % is fine, 100 % = full speed)
    'hot.yield_mbps': 8,             # someone else reads/writes this disk faster than this -> pause relocation
    'hot.mode': 'always',            # always / idle / hours
    'hot.hours': [1, 8],             # for mode=hours: start, end (local time)
    'hot.order': 'newest',           # newest / largest / name : which hot files go first
    'hot.cold_to': 'end',            # end = evicted cold data goes to the inner tracks; after = right after the zone
    'hot.chunk_mb': 32,
    'hot.yield_queue': True,         # pause relocation while the transfer queue uses the same disk
    'hot.dry_run': False,
    'hot.zone_gb': {},               # per volume "K:" -> GB of the outer zone (0 / missing = auto)
    'hot.min_gap_mb': 8,             # hot data is never split over free gaps smaller than this (keeps files in one piece)
    'hot.vss_ok': {},                # "K:": True = the user accepted that moving may push out old restore points
    'hot.folders': [],               # [{"path": "K:\\Work", "order": 0, "added": ts}]
    'index.enabled': True,
    'index.drives': [],              # [] = every fixed NTFS / local drive
    'index.exclude': ['$Recycle.Bin', 'System Volume Information', '.HotZoneVault'],
    'index.rescan_min': 30,          # non-NTFS drives: full rescan every N minutes
    'index.create_journal': True,
    'vault.days': 30,                # 保管區: days in keep before moving to review
    'vault.keep_moved_src': True,    # cross-drive move: keep the source in the vault instead of deleting it
    'images.enabled': True,          # 圖片分類 background analysis
    'images.folders': [],
    'images.faces': True,
    'images.usage_pct': 60,
    'images.yield_queue': True,
    'images.threads': 2,             # pictures analysed at the same time (CPU cores; 1 = gentlest)
    'fav': [],                       # quick access
    'explorer.show_hidden': False,
    'explorer.dual': False,
}


SETTING_CHOICES = {
    'ui.theme': ('dark', 'light'), 'transfer.after': ('', 'sleep', 'hibernate', 'shutdown'), 'hot.mode': ('always', 'idle', 'hours'),
    'hot.order': ('newest', 'largest', 'name'), 'hot.cold_to': ('end', 'after'),
    'transfer.conflict': ('ask', 'skip', 'overwrite', 'newer', 'rename'),
}
SETTING_RANGES = {
    'ui.zoom': (50, 200), 'web.port': (1024, 65535), 'web.session_days': (1, 365), 'transfer.max_total': (1, 32),
    'transfer.hdd_max': (1, 8), 'transfer.ssd_max': (1, 16), 'transfer.net_max': (1, 16), 'transfer.usage_pct': (10, 100),
    'transfer.mbps_cap': (0, 100000), 'transfer.buffer_mb': (1, 256), 'transfer.yield_mbps': (0, 100000), 'transfer.keep_done': (10, 100000),
    'transfer.sched_from': (0, 23), 'transfer.sched_to': (0, 24), 'transfer.sched_pct': (5, 100), 'transfer.sched_mbps': (0, 100000),
    'hot.usage_pct': (5, 100), 'hot.yield_mbps': (0, 100000), 'hot.chunk_mb': (1, 1024), 'hot.min_gap_mb': (0, 4096),
    'index.rescan_min': (1, 10080), 'vault.days': (1, 3650), 'images.usage_pct': (5, 100), 'images.threads': (1, 16),
}
IMPORT_SKIP = ('transfer.after', 'hot.vss_ok', 'system.task_v', 'ui.welcomed', 'web.pw_hash', 'web.pw_salt')   # one-off / per-PC


def check_settings(d: dict):
    """-> (clean, rejected): values of the right type for their key (bool / number / text / list / dict), numbers
    clamped to sane ranges, choices checked. A wrong value is dropped instead of breaking the engine later."""
    clean = {}; bad = []
    for k, v in d.items():
        if k not in DEFAULTS: bad.append(k); continue
        dv = DEFAULTS[k]
        if isinstance(dv, bool):
            ok = isinstance(v, bool)
        elif isinstance(dv, (int, float)):
            ok = isinstance(v, (int, float)) and not isinstance(v, bool) and v == v
            if ok and k in SETTING_RANGES:
                lo, hi = SETTING_RANGES[k]; v = max(lo, min(hi, v))
            if ok and isinstance(dv, int) and not isinstance(dv, bool) and float(v).is_integer(): v = int(v)
        elif isinstance(dv, str):
            ok = isinstance(v, str) and len(v) < 10000 and (k not in SETTING_CHOICES or v in SETTING_CHOICES[k])
        elif isinstance(dv, list):
            ok = isinstance(v, list)
            if ok and k == 'hot.folders': ok = all(isinstance(x, dict) and isinstance(x.get('path'), str) for x in v)
            if ok and k == 'hot.hours': ok = len(v) >= 2 and all(isinstance(x, int) and 0 <= x <= 24 for x in v[:2])
            if ok and k in ('index.drives', 'index.exclude', 'images.folders', 'fav', 'web.hosts'): ok = all(isinstance(x, str) for x in v)
        elif isinstance(dv, dict):
            ok = isinstance(v, dict)
        else:
            ok = True
        if ok: clean[k] = v
        else: bad.append(k)
    return clean, bad


class Settings:
    def __init__(self, path: Path = SETTINGS_FILE):
        self.path = path
        self._lock = threading.RLock()
        self._data = {}
        self.load()

    def load(self):
        with self._lock:
            try:
                self._data = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}
            except Exception:
                try: self.path.replace(self.path.with_suffix('.broken.json'))
                except Exception: pass
                self._data = {}

    def get(self, key, default=None):
        with self._lock:
            if key in self._data: return self._data[key]
        v = DEFAULTS.get(key, default)
        return json.loads(json.dumps(v)) if isinstance(v, (dict, list)) else v      # copies: callers may change them

    def set(self, key, value, save=True):
        with self._lock:
            self._data[key] = value
            if save: self.save()

    def update(self, d: dict):
        with self._lock:
            for k, v in d.items():
                if k in DEFAULTS or k.startswith('x.'): self._data[k] = v
            self.save()

    def all(self):
        with self._lock:
            out = dict(DEFAULTS); out.update(self._data)
            return out

    def save(self):
        with self._lock:
            atomic_write_json(self.path, self._data)


def atomic_write_json(path: Path, obj, indent=1, durable=False):
    """Write to a private temp file, then swap it in. durable=True also forces the bytes to the disk first
    (fsync), so after a power cut the file is either the old or the new version, never empty."""
    tmp = Path(f'{path}.{os.getpid()}_{threading.get_ident()}.tmp')
    data = json.dumps(obj, ensure_ascii=False, indent=indent).encode('utf-8')
    with open(tmp, 'wb') as f:
        f.write(data)
        if durable:
            f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def read_json(path: Path, default=None):
    try: return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except Exception: return default


# ---------------------------------------------------------------------------------------------- log
class Log:
    """Small thread-safe log: file in LOG\\ + a ring buffer the UI can show."""
    def __init__(self, name='engine'):
        self.file = LOG_DIR / f'{name}.log'
        self.lock = threading.Lock()
        self.ring = []
        self.seq = 0
        try:
            if self.file.exists() and self.file.stat().st_size > 8 * 1024 * 1024:
                self.file.replace(LOG_DIR / f'{name}.old.log')
        except Exception:
            pass

    def write(self, level, area, msg):
        t = time.time()
        line = f'[{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))}] {level:5} {area}: {msg}'
        with self.lock:
            self.seq += 1
            self.ring.append({'n': self.seq, 't': t, 'lv': level, 'a': area, 'm': str(msg)})
            if len(self.ring) > 1500: del self.ring[:500]
            try:
                with open(self.file, 'a', encoding='utf-8') as f:
                    f.write(line + '\n')
                    big = f.tell() > 8 * 1024 * 1024
                if big: self.file.replace(self.file.with_name(self.file.stem + '.old.log'))   # rotate while running
            except Exception:
                pass

    def info(self, area, msg): self.write('INFO', area, msg)
    def warn(self, area, msg): self.write('WARN', area, msg)
    def error(self, area, msg): self.write('ERROR', area, msg)

    def exc(self, area, msg=''):
        self.write('ERROR', area, (msg + '\n' if msg else '') + traceback.format_exc())

    def since(self, n=0, limit=400):
        with self.lock:
            rows = [r for r in self.ring if r['n'] > n]
        return rows[-limit:]


# ---------------------------------------------------------------------------------------------- helpers
def fmt_size(n):
    try: n = float(n)
    except Exception: return '—'
    for u in ('B', 'KB', 'MB', 'GB', 'TB', 'PB'):
        if abs(n) < 1024 or u == 'PB':
            return f'{n:.0f} {u}' if u == 'B' else f'{n:.1f} {u}' if n < 100 else f'{n:.0f} {u}'
        n /= 1024.0


import ntpath
import re
_WIN_ABS = re.compile(r'^(?:[A-Za-z]:[\\/]|[\\/]{2}[^\\/?.])')


def norm(p: str) -> str:
    """Normalised absolute path (Windows: back-slashes, drive letter upper case)."""
    p = str(p)
    if IS_WIN and _WIN_ABS.match(p): p = ntpath.normpath(p)   # string-only: abspath (GetFullPathNameW) would strip a trailing
    else: p = os.path.abspath(p)                              # '.' / ' ' (a NAS 'Photos.' became the sibling 'Photos')
    if IS_WIN and len(p) >= 2 and p[1] == ':':
        p = p[0].upper() + p[1:]
    return p


def drive_of(p: str) -> str:
    """'K:' for K:\\x\\y ; on Linux the mount point that holds the path."""
    p = norm(p)
    if IS_WIN:
        d = os.path.splitdrive(p)[0]
        return d.upper() if d else ''
    return mount_point(p)


_mount_cache = {'t': 0, 'mounts': ['/']}


def mount_point(p: str) -> str:
    if time.time() - _mount_cache['t'] > 30:
        ms = ['/']
        try:
            for line in open('/proc/mounts', encoding='utf-8'):
                parts = line.split()
                if len(parts) > 1: ms.append(parts[1].replace('\\040', ' '))
        except Exception:
            pass
        _mount_cache.update(t=time.time(), mounts=sorted(set(ms), key=len, reverse=True))
    for m in _mount_cache['mounts']:
        if p == m or p.startswith(m.rstrip('/') + '/'): return m
    return '/'


def is_under(path: str, folder: str) -> bool:
    a = norm(path); b = norm(folder).rstrip('\\/')
    if IS_WIN: a = a.lower(); b = b.lower()
    if a == b: return True
    return a.startswith(b + os.sep) or (len(b) == 2 and b[1] == ':' and a.startswith(b + '\\'))


def same_path(a: str, b: str) -> bool:
    a = norm(a); b = norm(b)
    return a.lower() == b.lower() if IS_WIN else a == b


def _lpx(path: str) -> str:
    if not IS_WIN or path.startswith('\\\\?\\'): return path
    path = os.path.abspath(path)
    if len(path) < 240: return path
    if path.startswith('\\\\'): return '\\\\?\\UNC\\' + path[2:]
    return '\\\\?\\' + path


def unique_name(path: str) -> str:
    """'x.mp4' -> 'x (2).mp4' when taken (long-path safe, broken links count as taken)."""
    if not os.path.lexists(_lpx(path)): return path
    base, ext = os.path.splitext(path)
    if os.path.isdir(_lpx(path)): base, ext = path, ''
    i = 2
    while True:
        cand = f'{base} ({i}){ext}'
        if not os.path.lexists(_lpx(cand)): return cand
        i += 1


def json_safe(o):
    import math
    if isinstance(o, float): return o if math.isfinite(o) else None
    if isinstance(o, dict): return {str(k): json_safe(v) for k, v in list(o.items())}
    if isinstance(o, (list, tuple, set)): return [json_safe(v) for v in list(o)]
    if isinstance(o, Path): return str(o)
    return o


class Stoppable(threading.Thread):
    """Thread with a stop flag and a 'sleep that wakes up on stop'."""
    def __init__(self, name):
        super().__init__(name=name, daemon=True)
        self.stop_ev = threading.Event()

    def stop(self):
        self.stop_ev.set()

    def nap(self, sec) -> bool:
        """Sleep; True = asked to stop."""
        return self.stop_ev.wait(max(0.0, sec))

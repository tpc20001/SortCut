"""HotZone FM — Windows API layer (ctypes). Every function also works (or quietly does nothing) on
other systems so the engine can be tested anywhere.

Drives / physical disks:   which letters live on which physical disk (K: and L: on one HDD share a lane)
HDD or SSD:                IOCTL_STORAGE_QUERY_PROPERTY (seek penalty)
Disk activity:             PDH  \\PhysicalDisk(*)\\% Idle Time, read / write bytes per second
Recycle bin, file times, write-through files, background I/O priority, explorer.exe helpers.
"""
from __future__ import annotations

import ctypes
import os
import stat as _stat
import re
import struct
import subprocess
import threading
import time

from hz_common import IS_WIN

if IS_WIN:
    from ctypes import wintypes
    import msvcrt

    _k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    HANDLE = ctypes.c_void_p
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, HANDLE]
    _k32.CreateFileW.restype = HANDLE
    _k32.CloseHandle.argtypes = [HANDLE]
    _k32.CloseHandle.restype = wintypes.BOOL
    _k32.DeviceIoControl.argtypes = [HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    _k32.DeviceIoControl.restype = wintypes.BOOL
    _k32.ReadFile.argtypes = [HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    _k32.ReadFile.restype = wintypes.BOOL
    _k32.SetFilePointerEx.argtypes = [HANDLE, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
    _k32.SetFilePointerEx.restype = wintypes.BOOL
    _k32.GetLogicalDrives.restype = wintypes.DWORD
    _k32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    _k32.GetDriveTypeW.restype = wintypes.UINT
    _k32.GetVolumeInformationW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                           ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR, wintypes.DWORD]
    _k32.GetVolumeInformationW.restype = wintypes.BOOL
    _k32.GetDiskFreeSpaceExW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_ulonglong), ctypes.POINTER(ctypes.c_ulonglong), ctypes.POINTER(ctypes.c_ulonglong)]
    _k32.GetDiskFreeSpaceExW.restype = wintypes.BOOL
    _k32.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
    _k32.GetFileAttributesW.restype = wintypes.DWORD
    _k32.SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    _k32.SetFileAttributesW.restype = wintypes.BOOL
    _k32.SetFileTime.argtypes = [HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    _k32.SetFileTime.restype = wintypes.BOOL
    _k32.GetCurrentThread.restype = HANDLE
    _k32.SetThreadPriority.argtypes = [HANDLE, ctypes.c_int]
    _k32.SetThreadPriority.restype = wintypes.BOOL

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_READ_ATTRIBUTES = 0x80
FILE_WRITE_ATTRIBUTES = 0x100
FILE_SHARE_ALL = 0x1 | 0x2 | 0x4
OPEN_EXISTING = 3
CREATE_ALWAYS = 2
OPEN_ALWAYS = 4
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_WRITE_THROUGH = 0x80000000
FILE_FLAG_NO_BUFFERING = 0x20000000
FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
FILE_ATTRIBUTE_NORMAL = 0x80
ERROR_MORE_DATA = 234
ERROR_HANDLE_EOF = 38
ERROR_ACCESS_DENIED = 5

IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS = 0x00560000
IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
IOCTL_DISK_GET_DRIVE_GEOMETRY_EX = 0x000700A0
BUS_TYPES = {1: 'SCSI', 2: 'ATAPI', 3: 'ATA', 4: '1394', 6: 'FC', 7: 'USB', 8: 'RAID', 9: 'iSCSI', 10: 'SAS', 11: 'SATA',
             12: 'SD', 13: 'MMC', 14: 'Virtual', 15: 'VHD', 16: 'Spaces', 17: 'NVMe'}


def odd_names(path: str) -> bool:
    """A part that ends in '.' or ' ' (made on a NAS / Linux / WSL): plain Win32 calls strip it and reach another name."""
    return any(x.endswith(('.', ' ')) and x not in ('.', '..') for x in path.replace('/', '\\').split('\\')[1:])


def lp(path: str) -> str:
    """Long path prefix for paths near / over 260 characters."""
    if not IS_WIN or path.startswith('\\\\?\\'): return path
    import ntpath, re
    if re.match(r'^(?:[A-Za-z]:[\\/]|[\\/]{2}[^\\/?.])', path): path = ntpath.normpath(path)   # string-only (see hz_common.norm)
    else: path = os.path.abspath(path)                               # \\?\ turns off normalisation
    if len(path) < 240 and not odd_names(path): return path
    if path.startswith('\\\\'): return '\\\\?\\UNC\\' + path[2:]
    return '\\\\?\\' + path


_renameat2 = None


def rename_noreplace(src: str, dst: str) -> None:
    """Rename that never replaces an existing target (raises FileExistsError instead).
    Windows MoveFileEx without REPLACE_EXISTING already refuses; on Linux renameat2(RENAME_NOREPLACE),
    elsewhere link+unlink for files and a checked rename for folders."""
    global _renameat2
    if IS_WIN:
        try: os.rename(lp(src), lp(dst))
        except FileExistsError: raise
        except OSError as e:
            if getattr(e, 'winerror', None) in (80, 183): raise FileExistsError(e.errno, '目標已經存在', dst)
            raise
        return
    if os.path.lexists(dst): raise FileExistsError(17, '目標已經存在', dst)
    if _renameat2 is None:
        try:
            libc = ctypes.CDLL(None, use_errno=True); f = libc.renameat2
            f.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]; _renameat2 = f
        except Exception:
            _renameat2 = False
    if _renameat2:
        r = _renameat2(-100, os.fsencode(src), -100, os.fsencode(dst), 1)          # AT_FDCWD, RENAME_NOREPLACE
        if r == 0: return
        err = ctypes.get_errno()
        if err == 17: raise FileExistsError(17, '目標已經存在', dst)
        if err not in (22, 38, 95): raise OSError(err, os.strerror(err), src)  # EINVAL/ENOSYS/EOPNOTSUPP -> fallback
    if os.path.isdir(src) and not os.path.islink(src):
        if os.path.lexists(dst): raise FileExistsError(17, '目標已經存在', dst)
        os.rename(src, dst); return
    os.link(src, dst, follow_symlinks=False)                                   # fails with EEXIST, never replaces
    os.unlink(src)


def is_link_like(path: str) -> bool:
    """Symlink or Windows junction (mount point). os.path.islink() says False for junctions and os.walk walks into
    them, so a delete of a folder holding a junction would delete the junction's TARGET. Cloud placeholders
    (OneDrive) are reparse points too but are real folders: only the two link tags count."""
    try: st = os.lstat(lp(path))
    except OSError: return False
    if _stat.S_ISLNK(st.st_mode): return True
    if IS_WIN and getattr(st, 'st_file_attributes', 0) & 0x400:
        return getattr(st, 'st_reparse_tag', 0) in (0xA0000003, 0xA000000C)
    return False


def walk(top: str, onerror=None):
    """os.walk that never descends into symlinks / junctions; yields (root, dirs, files, links) where links are the
    link-like sub-folders (reported separately, not walked)."""
    for root, dirs, files in os.walk(top, onerror=onerror):
        links = [d for d in dirs if is_link_like(os.path.join(root, d))]
        if links: dirs[:] = [d for d in dirs if d not in links]
        yield root, dirs, files, links


def is_admin() -> bool:
    if not IS_WIN:
        try: return os.geteuid() == 0
        except Exception: return False
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception: return False


def open_handle(path, access=0, share=FILE_SHARE_ALL, disp=OPEN_EXISTING, flags=0):
    """CreateFileW -> (handle or None, error)."""
    h = _k32.CreateFileW(path, access, share, None, disp, flags, None)
    if h is None or h == INVALID_HANDLE_VALUE:
        return None, ctypes.get_last_error()
    return h, 0


def close_handle(h):
    try:
        if h: _k32.CloseHandle(h)
    except Exception:
        pass


def ioctl(h, code, inbuf: bytes | None = None, outsize: int = 0):
    """DeviceIoControl -> (ok, data, error). Data is returned also on ERROR_MORE_DATA (partial result)."""
    out = ctypes.create_string_buffer(outsize) if outsize else None
    ret = wintypes.DWORD(0)
    ib = ctypes.create_string_buffer(inbuf, len(inbuf)) if inbuf else None
    ok = _k32.DeviceIoControl(h, code, ib, len(inbuf) if inbuf else 0, out, outsize, ctypes.byref(ret), None)
    err = 0 if ok else ctypes.get_last_error()
    data = out.raw[:ret.value] if out is not None else b''
    return bool(ok), data, err


# ============================================================================================ drives & disks
def _volume_info(root):
    name = ctypes.create_unicode_buffer(261); fs = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD(0); maxc = wintypes.DWORD(0); flags = wintypes.DWORD(0)
    ok = _k32.GetVolumeInformationW(root, name, 261, ctypes.byref(serial), ctypes.byref(maxc), ctypes.byref(flags), fs, 261)
    if not ok: return None
    return {'label': name.value, 'fs': fs.value, 'serial': f'{serial.value:08X}'}


def _free_space(root):
    a = ctypes.c_ulonglong(0); t = ctypes.c_ulonglong(0); f = ctypes.c_ulonglong(0)
    if not _k32.GetDiskFreeSpaceExW(root, ctypes.byref(a), ctypes.byref(t), ctypes.byref(f)): return None
    return {'total': t.value, 'free': f.value, 'avail': a.value}


def volume_disk_extents(letter: str):
    """[(disk_number, partition_start_bytes, length_bytes)] for 'K:'."""
    h, err = open_handle('\\\\.\\' + letter, 0)
    if not h: return []
    try:
        ok, data, err = ioctl(h, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS, None, 8 + 24 * 32)
        if len(data) < 8: return []
        n = struct.unpack_from('<I', data, 0)[0]; out = []
        for i in range(min(n, 32)):
            o = 8 + 24 * i
            if o + 24 > len(data): break
            dn, start, length = struct.unpack_from('<I4xqq', data, o)
            out.append((dn, start, length))
        return out
    finally:
        close_handle(h)


def _storage_query(h, prop_id, outsize):
    q = struct.pack('<ii4s', prop_id, 0, b'\0\0\0\0')          # STORAGE_PROPERTY_QUERY (12 bytes)
    ok, data, err = ioctl(h, IOCTL_STORAGE_QUERY_PROPERTY, q, outsize)
    return data if ok else b''


def physical_disk_info(n: int) -> dict:
    info = {'n': n, 'media': '?', 'model': '', 'bus': '', 'size': 0, 'serial': ''}
    h, err = open_handle(f'\\\\.\\PhysicalDrive{n}', 0)
    if not h: return info
    try:
        d = _storage_query(h, 7, 12)                               # StorageDeviceSeekPenaltyProperty
        if len(d) >= 9: info['media'] = 'HDD' if d[8] else 'SSD'
        d = _storage_query(h, 0, 1024)                             # StorageDeviceProperty
        if len(d) >= 32:
            vo, po, ro, so, bus = struct.unpack_from('<IIIII', d, 12)

            def s(off):
                if not off or off >= len(d): return ''
                return d[off:d.index(b'\0', off) if b'\0' in d[off:] else len(d)].decode('ascii', 'ignore').strip()
            info['model'] = (s(vo) + ' ' + s(po)).strip()
            info['serial'] = s(so)
            info['bus'] = BUS_TYPES.get(bus, str(bus))
            if info['bus'] == 'NVMe' and info['media'] == '?': info['media'] = 'SSD'
        ok, g, err = ioctl(h, IOCTL_DISK_GET_DRIVE_GEOMETRY_EX, None, 256)
        if len(g) >= 32: info['size'] = struct.unpack_from('<q', g, 24)[0]
    finally:
        close_handle(h)
    return info


# model hints for shingled (SMR) drives - the "outer = beginning of the volume" rule is weaker on them
_SMR_HINTS = [r'^WDC? ?WD\d+EFAX', r'^WDC? ?WD\d+EZAZ', r'^WDC? ?WD\d+EDAZ', r'^WDC? ?WD\d+SPZX', r'ST\d+DM00[4-8]', r'ST\d+LM0(15|24|48)',
              r'ST\d+DM003', r'ST\d+VX0', r'HDWD1[2-3]\d', r'^TOSHIBA DT02', r'ST\d+BA\d', r'ST\d+AS0']


def smr_suspect(model: str) -> bool:
    m = (model or '').upper().replace('WDC ', 'WD')
    return any(re.search(p, m) for p in _SMR_HINTS)


class Drives:
    """Cached view of every drive letter and physical disk. refresh() is cheap enough to call every 20 s."""
    def __init__(self):
        self.lock = threading.Lock()
        self.vols = {}     # 'K:' -> {letter,type,label,fs,serial,total,free,disks:[n],media,ok}
        self.disks = {}    # n -> {n,media,model,bus,size,letters}
        self.t = 0
        self._disk_cache = {}

    def get(self, letter):
        with self.lock: return dict(self.vols.get((letter or '').upper(), {}))

    def lane_of(self, path: str):
        """Lane key(s) for a path: physical disk numbers ('d1'), or the drive itself for network / unknown."""
        from hz_common import drive_of
        L = drive_of(path)
        v = self.get(L)
        if v.get('disks'): return ['d%d' % n for n in v['disks']]
        return ['v' + (L or '?')]

    def lane_media(self, lane: str):
        if lane.startswith('d'):
            with self.lock: return (self.disks.get(int(lane[1:])) or {}).get('media', '?')
        v = self.get(lane[1:])
        return 'NET' if v.get('type') == 'remote' else '?'

    def snapshot(self):
        with self.lock:
            return {'vols': [dict(v) for v in self.vols.values()], 'disks': [dict(d) for d in self.disks.values()], 't': self.t}

    def refresh(self):
        vols = {}; disks = {}
        if IS_WIN:
            mask = _k32.GetLogicalDrives()
            for i in range(26):
                if not mask & (1 << i): continue
                L = chr(65 + i) + ':'; root = L + '\\'
                t = _k32.GetDriveTypeW(root)
                kind = {2: 'removable', 3: 'fixed', 4: 'remote', 5: 'cdrom', 6: 'ram'}.get(t, 'other')
                v = {'letter': L, 'type': kind, 'label': '', 'fs': '', 'serial': '', 'total': 0, 'free': 0, 'disks': [], 'ok': False}
                if kind == 'cdrom':
                    vols[L] = v; continue
                res = {}

                def q(root=root, res=res):
                    res['vi'] = _volume_info(root); res['fsp'] = _free_space(root)
                if kind == 'remote':                                          # a dead network share can hang: give it 2 s
                    th = threading.Thread(target=q, daemon=True); th.start(); th.join(2.0)
                else:
                    q()
                if res.get('vi'): v.update(res['vi']); v['ok'] = True
                if res.get('fsp'): v['total'] = res['fsp']['total']; v['free'] = res['fsp']['free']
                if kind in ('fixed', 'removable') and v['ok']:
                    v['extents'] = volume_disk_extents(L)
                    v['disks'] = sorted({e[0] for e in v['extents']})
                    if v['extents']: v['part_offset'] = v['extents'][0][1]
                vols[L] = v
            for v in vols.values():
                for n in v['disks']:
                    if n not in self._disk_cache or time.time() - self._disk_cache[n][0] > 600:
                        self._disk_cache[n] = (time.time(), physical_disk_info(n))
                    d = disks.get(n)
                    if d is None:
                        d = dict(self._disk_cache[n][1] or {}); d['letters'] = []; d.setdefault('media', '?'); disks[n] = d
                    d['letters'] = sorted(set(d['letters']) | {v['letter']})       # (was a KeyError: the right side ran first)
            for v in vols.values():
                ms = {disks[n]['media'] for n in v['disks'] if n in disks}
                v['media'] = 'HDD' if 'HDD' in ms else ('SSD' if 'SSD' in ms else ('NET' if v['type'] == 'remote' else '?'))
                v['smr'] = any(smr_suspect(disks[n].get('model', '')) for n in v['disks'] if n in disks)
        else:
            seen = {}
            try: lines = open('/proc/mounts', encoding='utf-8').read().splitlines()
            except Exception: lines = ['/ / ext4 rw 0 0']
            for line in lines:
                p = line.split()
                if len(p) < 3 or p[2] in ('proc', 'sysfs', 'devpts', 'cgroup', 'cgroup2', 'mqueue', 'securityfs', 'debugfs', 'tracefs',
                                           'pstore', 'bpf', 'autofs', 'hugetlbfs', 'fusectl', 'configfs', 'binfmt_misc', 'nsfs', 'devtmpfs'): continue
                mp = p[1].replace('\\040', ' ')
                if mp.startswith(('/proc', '/sys', '/dev', '/run')) and mp != '/': continue
                try: st = os.statvfs(mp); dev = os.stat(mp).st_dev
                except Exception: continue
                if mp in vols: continue
                n = seen.setdefault(dev, len(seen))
                vols[mp] = {'letter': mp, 'type': 'fixed', 'label': os.path.basename(mp) or '/', 'fs': p[2], 'serial': '%x' % dev,
                            'total': st.f_blocks * st.f_frsize, 'free': st.f_bavail * st.f_frsize, 'disks': [n], 'ok': True, 'media': '?', 'smr': False}
                disks.setdefault(n, {'n': n, 'media': '?', 'model': p[0], 'bus': '', 'size': 0, 'letters': []})['letters'].append(mp)
        with self.lock:
            self.vols = vols; self.disks = disks; self.t = time.time()
        return self.snapshot()


# ============================================================================================ disk activity (PDH)
class DiskCounters:
    """\\PhysicalDisk(*)\\  busy %, read / write bytes per second, sampled every second on its own thread."""
    def __init__(self):
        self.data = {}          # n -> {'busy': %, 'rd': B/s, 'wr': B/s, 't': ts}
        self.ok = False
        self._stop = threading.Event()
        self.th = threading.Thread(target=self._loop, name='HZ-DiskCounters', daemon=True)

    def start(self):
        self.th.start(); return self

    def stop(self):
        self._stop.set()

    def get(self, n):
        d = self.data.get(n)
        return d if d and time.time() - d.get('t', 0) < 5 else None

    def _loop(self):
        if not IS_WIN:
            self._loop_linux(); return
        try:
            pdh = ctypes.WinDLL('pdh.dll')
            q = ctypes.c_void_p(); c_idle = ctypes.c_void_p(); c_rd = ctypes.c_void_p(); c_wr = ctypes.c_void_p()
            if pdh.PdhOpenQueryW(None, None, ctypes.byref(q)) != 0: return
            pdh.PdhAddEnglishCounterW(q, '\\PhysicalDisk(*)\\% Idle Time', None, ctypes.byref(c_idle))
            pdh.PdhAddEnglishCounterW(q, '\\PhysicalDisk(*)\\Disk Read Bytes/sec', None, ctypes.byref(c_rd))
            pdh.PdhAddEnglishCounterW(q, '\\PhysicalDisk(*)\\Disk Write Bytes/sec', None, ctypes.byref(c_wr))
            pdh.PdhCollectQueryData(q)
        except Exception:
            return

        class VAL(ctypes.Structure): _fields_ = [('CStatus', ctypes.c_ulong), ('dbl', ctypes.c_double)]

        class ITEM(ctypes.Structure): _fields_ = [('name', ctypes.c_wchar_p), ('v', VAL)]

        def arr(counter):
            size = ctypes.c_ulong(0); cnt = ctypes.c_ulong(0); FMT = 0x00000200 | 0x00008000
            pdh.PdhGetFormattedCounterArrayW(counter, FMT, ctypes.byref(size), ctypes.byref(cnt), None)
            if not size.value: return {}
            buf = ctypes.create_string_buffer(size.value)
            if pdh.PdhGetFormattedCounterArrayW(counter, FMT, ctypes.byref(size), ctypes.byref(cnt), buf) != 0: return {}
            items = ctypes.cast(buf, ctypes.POINTER(ITEM)); out = {}
            for i in range(cnt.value):
                m = re.match(r'(\d+)', items[i].name or '')
                if m: out[int(m.group(1))] = max(0.0, items[i].v.dbl)
            return out
        while not self._stop.wait(1.0):
            try:
                if pdh.PdhCollectQueryData(q) != 0: continue
                idle = arr(c_idle); rd = arr(c_rd); wr = arr(c_wr); now = time.time()
                for n in set(idle) | set(rd) | set(wr):
                    self.data[n] = {'busy': max(0.0, min(100.0, 100.0 - idle.get(n, 100.0))), 'rd': rd.get(n, 0.0), 'wr': wr.get(n, 0.0), 't': now}
                self.ok = True
            except Exception:
                pass

    def _loop_linux(self):
        """Linux (testing only): /proc/diskstats per block device, mapped to nothing useful - keeps the API alive."""
        while not self._stop.wait(1.0):
            pass


# ============================================================================================ files
def recycle(paths) -> tuple[bool, str]:
    """Send files / folders to the recycle bin (Windows). Elsewhere: refuse (the caller can delete for real)."""
    paths = [os.path.abspath(p) for p in paths if p]
    if not paths: return True, ''
    if not IS_WIN: return False, '這個系統沒有資源回收筒'

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [('hwnd', wintypes.HWND), ('wFunc', wintypes.UINT), ('pFrom', ctypes.c_void_p), ('pTo', ctypes.c_void_p),
                    ('fFlags', ctypes.c_ushort), ('fAnyOperationsAborted', wintypes.BOOL), ('hNameMappings', ctypes.c_void_p),
                    ('lpszProgressTitle', ctypes.c_void_p)]
    s = '\0'.join(paths) + '\0\0'
    buf = ctypes.create_unicode_buffer(len(s) + 1)
    buf[:len(s)] = s
    op = SHFILEOPSTRUCTW()
    op.hwnd = None; op.wFunc = 3                                         # FO_DELETE
    op.pFrom = ctypes.cast(buf, ctypes.c_void_p).value; op.pTo = None
    op.fFlags = 0x40 | 0x10 | 0x4 | 0x400 | 0x4000                       # ALLOWUNDO | NOCONFIRMATION | SILENT | NOERRORUI | WANTNUKEWARNING
    # (WANTNUKEWARNING: an item that cannot go to the bin - network / USB / too big - is asked about, never deleted silently)
    r = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if r != 0: return False, f'資源回收筒失敗（代碼 0x{r:X}）'
    if op.fAnyOperationsAborted: return False, '有部分項目沒有刪除'
    return True, ''


def get_attrs(path):
    if not IS_WIN: return 0
    a = _k32.GetFileAttributesW(lp(path))
    return 0 if a == 0xFFFFFFFF else a


def set_attrs(path, attrs):
    if not IS_WIN: return
    try: _k32.SetFileAttributesW(lp(path), attrs & 0x27 or FILE_ATTRIBUTE_NORMAL)      # readonly hidden system archive
    except Exception: pass


def _filetime(ts):
    v = int((ts + 11644473600) * 10_000_000)
    return ctypes.c_ulonglong(v)


def set_times(path, ctime=None, atime=None, mtime=None):
    """Creation / access / modify time (Windows keeps the creation time, os.utime cannot)."""
    if not IS_WIN:
        try:
            if mtime is not None: os.utime(path, (atime or mtime, mtime))
        except Exception: pass
        return
    h, err = open_handle(lp(path), FILE_WRITE_ATTRIBUTES, FILE_SHARE_ALL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS)
    if not h: return
    try:
        c = _filetime(ctime) if ctime else None; a = _filetime(atime) if atime else None; m = _filetime(mtime) if mtime else None
        _k32.SetFileTime(h, ctypes.byref(c) if c else None, ctypes.byref(a) if a else None, ctypes.byref(m) if m else None)
    finally:
        close_handle(h)


def open_dst(path, offset=0, write_through=True):
    """Open the destination for writing at offset (0 = new file). Windows + write_through: every write is on the disk
    when it returns, so measured time = real disk time (accurate usage %, no RAM flood)."""
    if IS_WIN and not offset:
        try:
            a = get_attrs(path)
            if a and a & 0x7: set_attrs(path, 0x80)                         # CREATE_ALWAYS on a hidden / system / read-only file fails
        except Exception:
            pass
    if IS_WIN and write_through:
        disp = OPEN_ALWAYS if offset else CREATE_ALWAYS
        h, err = open_handle(lp(path), GENERIC_READ | GENERIC_WRITE, 0x1, disp, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_WRITE_THROUGH | FILE_FLAG_SEQUENTIAL_SCAN)
        if not h: raise OSError(None, ctypes.FormatError(err), path, err)
        try:
            fd = msvcrt.open_osfhandle(h, os.O_RDWR)
        except Exception:
            close_handle(h); raise
        f = os.fdopen(fd, 'r+b', buffering=0)
    else:
        f = open(lp(path), 'r+b' if offset else 'wb', buffering=0)
    if offset:
        f.truncate(offset); f.seek(offset)
    return f


def open_src(path):
    return open(lp(path), 'rb', buffering=0)


def read_unbuffered(path, chunk=4 * 1024 * 1024):
    """Yield the file contents bypassing the Windows file cache (for verify after copy). Elsewhere: normal read."""
    if not IS_WIN:
        with open(path, 'rb', buffering=0) as f:
            while True:
                b = f.read(chunk)
                if not b: return
                yield b
    import mmap
    h, err = open_handle(lp(path), GENERIC_READ, FILE_SHARE_ALL, OPEN_EXISTING, FILE_FLAG_NO_BUFFERING | FILE_FLAG_SEQUENTIAL_SCAN)
    if not h: raise OSError(None, ctypes.FormatError(err), path, err)
    mm = mmap.mmap(-1, chunk)                                    # page aligned buffer (required by NO_BUFFERING)
    try:
        addr = ctypes.addressof(ctypes.c_char.from_buffer(mm))
        n = wintypes.DWORD(0)
        while True:
            if not _k32.ReadFile(h, addr, chunk, ctypes.byref(n), None):
                e = ctypes.get_last_error()
                if e == ERROR_HANDLE_EOF: return
                raise OSError(None, ctypes.FormatError(e), path, e)
            if n.value == 0: return
            yield mm[:n.value]
            if n.value < chunk: return
    finally:
        try: del addr
        except Exception: pass
        close_handle(h)
        try: mm.close()
        except BufferError: pass


def thread_background(on: bool):
    """Very low CPU + disk priority for the calling thread (Windows THREAD_MODE_BACKGROUND)."""
    if not IS_WIN or threading.current_thread() is threading.main_thread(): return
    try: _k32.SetThreadPriority(_k32.GetCurrentThread(), 0x00010000 if on else 0x00020000)
    except Exception: pass


def explorer_open(path):
    """Open with the default program WITHOUT administrator rights (explorer.exe starts it for the logged-in user)."""
    if IS_WIN:
        subprocess.Popen(['explorer.exe', os.path.normpath(path)])
    else:
        subprocess.Popen(['xdg-open', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def explorer_select(path):
    if IS_WIN:
        subprocess.Popen('explorer.exe /select,"%s"' % os.path.normpath(path))
    else:
        explorer_open(os.path.dirname(path))


def no_window_flags():
    return 0x08000000 if IS_WIN else 0          # CREATE_NO_WINDOW

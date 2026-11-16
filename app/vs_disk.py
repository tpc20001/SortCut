"""SortCut — 硬碟：哪個磁碟機代號在哪顆實體硬碟上、是 HDD 還是 SSD、現在多忙（改寫自 HotZone FM 的 hz_win）。

用途：預覽圖／讀影片資訊照「實體硬碟」分道排隊。HDD 一次只讀一部（讀頭不用來回跳，整體反而快很多），
SSD 可以同時好幾部；別的程式正在大量用那顆硬碟時，新的工作先等。
所有函式在 Windows 以外也能跑（回傳「不知道」），方便測試。
"""
import os, re, struct, threading, time, ctypes

IS_WIN = os.name == 'nt'

if IS_WIN:
    from ctypes import wintypes
    _k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    HANDLE = ctypes.c_void_p
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, HANDLE]
    _k32.CreateFileW.restype = HANDLE
    _k32.CloseHandle.argtypes = [HANDLE]
    _k32.CloseHandle.restype = wintypes.BOOL
    _k32.DeviceIoControl.argtypes = [HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    _k32.DeviceIoControl.restype = wintypes.BOOL
    _k32.GetLogicalDrives.restype = wintypes.DWORD
    _k32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    _k32.GetDriveTypeW.restype = wintypes.UINT
    _k32.GetVolumeInformationW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                           ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR, wintypes.DWORD]
    _k32.GetVolumeInformationW.restype = wintypes.BOOL
    _k32.GetDiskFreeSpaceExW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_ulonglong), ctypes.POINTER(ctypes.c_ulonglong), ctypes.POINTER(ctypes.c_ulonglong)]
    _k32.GetDiskFreeSpaceExW.restype = wintypes.BOOL

FILE_SHARE_ALL = 0x7
OPEN_EXISTING = 3
IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS = 0x00560000
IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
BUS_TYPES = {1: 'SCSI', 3: 'ATA', 7: 'USB', 8: 'RAID', 10: 'SAS', 11: 'SATA', 12: 'SD', 14: 'Virtual', 15: 'VHD', 16: 'Spaces', 17: 'NVMe'}


def drive_of(p):
    """'D:\\影片\\a.mp4' → 'D:'；網路路徑 → '\\\\server\\share'；其他系統 → 掛載點的裝置編號."""
    p = str(p or '')
    if IS_WIN:
        m = re.match(r'^([A-Za-z]):', p)
        if m: return m.group(1).upper() + ':'
        m = re.match(r'^[\\/]{2}([^\\/]+)[\\/]([^\\/]+)', p)
        return ('\\\\' + m.group(1) + '\\' + m.group(2)).lower() if m else ''
    try:
        while p and not os.path.exists(p): p = os.path.dirname(p)
        return 'dev%x' % os.stat(p or '/').st_dev
    except Exception: return ''


def _open(path):
    h = _k32.CreateFileW(path, 0, FILE_SHARE_ALL, None, OPEN_EXISTING, 0, None)
    return None if (h is None or h == INVALID_HANDLE_VALUE) else h


def _ioctl(h, code, inbuf=None, outsize=0):
    out = ctypes.create_string_buffer(outsize) if outsize else None; ret = wintypes.DWORD(0)
    ib = ctypes.create_string_buffer(inbuf, len(inbuf)) if inbuf else None
    ok = _k32.DeviceIoControl(h, code, ib, len(inbuf) if inbuf else 0, out, outsize, ctypes.byref(ret), None)
    return bool(ok), (out.raw[:ret.value] if out is not None else b'')


def _extents(letter):
    h = _open('\\\\.\\' + letter)
    if not h: return []
    try:
        ok, d = _ioctl(h, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS, None, 8 + 24 * 32)
        if len(d) < 8: return []
        n = struct.unpack_from('<I', d, 0)[0]; out = []
        for i in range(min(n, 32)):
            o = 8 + 24 * i
            if o + 24 > len(d): break
            out.append(struct.unpack_from('<I4xqq', d, o)[0])
        return sorted(set(out))
    finally: _k32.CloseHandle(h)


def _disk_info(n):
    info = {'n': n, 'media': '?', 'model': '', 'bus': ''}
    h = _open(f'\\\\.\\PhysicalDrive{n}')
    if not h: return info
    try:
        ok, d = _ioctl(h, IOCTL_STORAGE_QUERY_PROPERTY, struct.pack('<ii4s', 7, 0, b'\0\0\0\0'), 12)      # seek penalty → HDD
        if len(d) >= 9: info['media'] = 'HDD' if d[8] else 'SSD'
        ok, d = _ioctl(h, IOCTL_STORAGE_QUERY_PROPERTY, struct.pack('<ii4s', 0, 0, b'\0\0\0\0'), 1024)
        if len(d) >= 32:
            vo, po, ro, so, bus = struct.unpack_from('<IIIII', d, 12)
            s = lambda off: d[off:d.index(b'\0', off)].decode('ascii', 'ignore').strip() if off and off < len(d) and b'\0' in d[off:] else ''
            info['model'] = (s(vo) + ' ' + s(po)).strip(); info['bus'] = BUS_TYPES.get(bus, str(bus))
            if info['bus'] == 'NVMe' and info['media'] == '?': info['media'] = 'SSD'
    finally: _k32.CloseHandle(h)
    return info


class Drives:
    """每個磁碟機代號 → 實體硬碟。refresh() 在背景執行緒做（網路磁碟最多等 2 秒）."""
    def __init__(self):
        self.lock = threading.Lock(); self.vols = {}; self.disks = {}; self.t = 0; self._cache = {}; self.force = {}     # force：測試用 {'lane': 'HDD'}

    def refresh(self):
        vols = {}; disks = {}
        if IS_WIN:
            mask = _k32.GetLogicalDrives()
            for i in range(26):
                if not mask & (1 << i): continue
                L = chr(65 + i) + ':'; root = L + '\\'; t = _k32.GetDriveTypeW(root)
                kind = {2: 'removable', 3: 'fixed', 4: 'remote', 5: 'cdrom', 6: 'ram'}.get(t, 'other')
                v = {'letter': L, 'type': kind, 'label': '', 'disks': [], 'total': 0, 'free': 0, 'ok': False}
                if kind in ('cdrom', 'remote'):
                    vols[L] = v; continue
                name = ctypes.create_unicode_buffer(261); fs = ctypes.create_unicode_buffer(261); x = wintypes.DWORD(0)
                if _k32.GetVolumeInformationW(root, name, 261, ctypes.byref(x), ctypes.byref(x), ctypes.byref(x), fs, 261):
                    v['label'] = name.value; v['ok'] = True
                a = ctypes.c_ulonglong(0); tt = ctypes.c_ulonglong(0); f = ctypes.c_ulonglong(0)
                if _k32.GetDiskFreeSpaceExW(root, ctypes.byref(a), ctypes.byref(tt), ctypes.byref(f)): v['total'] = tt.value; v['free'] = a.value
                if v['ok']: v['disks'] = _extents(L)
                vols[L] = v
            for v in vols.values():
                for n in v['disks']:
                    if n not in self._cache or time.time() - self._cache[n][0] > 600: self._cache[n] = (time.time(), _disk_info(n))
                    d = disks.setdefault(n, dict(self._cache[n][1], letters=[])); d['letters'] = sorted(set(d['letters']) | {v['letter']})
        with self.lock: self.vols = vols; self.disks = disks; self.t = time.time()

    def lane_of(self, path):
        """排隊用的「道」：同一顆實體硬碟＝同一道（D: E: 在同一顆 HDD 上也算一道）."""
        L = drive_of(path)
        with self.lock: v = self.vols.get(L)
        if v and v.get('disks'): return 'd' + '+'.join(str(n) for n in v['disks'])
        return 'v' + (L or '?')

    def media(self, lane):
        if lane in self.force: return self.force[lane]
        if lane.startswith('d'):
            with self.lock: ms = {(self.disks.get(int(n)) or {}).get('media', '?') for n in lane[1:].split('+') if n.isdigit()}
            return 'HDD' if 'HDD' in ms else ('SSD' if 'SSD' in ms else '?')
        if lane.startswith('v\\\\'): return 'NET'
        with self.lock: v = self.vols.get(lane[1:])
        return 'NET' if v and v.get('type') == 'remote' else '?'

    def label(self, lane):
        if lane.startswith('d'):
            with self.lock:
                L = sorted({x for n in lane[1:].split('+') if n.isdigit() for x in (self.disks.get(int(n)) or {}).get('letters', [])})
                model = ' / '.join((self.disks.get(int(n)) or {}).get('model', '') for n in lane[1:].split('+') if n.isdigit())
            return ' '.join(L) + (f'（{model}）' if model.strip() else '')
        return lane[1:]

    def disk_nums(self, lane):
        return [int(n) for n in lane[1:].split('+') if n.isdigit()] if lane.startswith('d') else []


class DiskCounters:
    """\\PhysicalDisk(*)\\ 忙碌 %、讀／寫 bytes/s，每秒取樣一次（Windows PDH）."""
    def __init__(self):
        self.data = {}; self.ok = False; self.stop = False
        threading.Thread(target=self._loop, name='VsDiskCounters', daemon=True).start()

    def get(self, n):
        d = self.data.get(n); return d if d and time.time() - d.get('t', 0) < 5 else None

    def _loop(self):
        if not IS_WIN: return
        try:
            pdh = ctypes.WinDLL('pdh.dll')
            q = ctypes.c_void_p(); ci = ctypes.c_void_p(); cr = ctypes.c_void_p(); cw = ctypes.c_void_p()
            if pdh.PdhOpenQueryW(None, None, ctypes.byref(q)) != 0: return
            pdh.PdhAddEnglishCounterW(q, '\\PhysicalDisk(*)\\% Idle Time', None, ctypes.byref(ci))
            pdh.PdhAddEnglishCounterW(q, '\\PhysicalDisk(*)\\Disk Read Bytes/sec', None, ctypes.byref(cr))
            pdh.PdhAddEnglishCounterW(q, '\\PhysicalDisk(*)\\Disk Write Bytes/sec', None, ctypes.byref(cw))
            pdh.PdhCollectQueryData(q)
        except Exception: return

        class VAL(ctypes.Structure): _fields_ = [('CStatus', ctypes.c_ulong), ('dbl', ctypes.c_double)]

        class ITEM(ctypes.Structure): _fields_ = [('name', ctypes.c_wchar_p), ('v', VAL)]

        def arr(c):
            size = ctypes.c_ulong(0); cnt = ctypes.c_ulong(0); FMT = 0x00000200 | 0x00008000
            pdh.PdhGetFormattedCounterArrayW(c, FMT, ctypes.byref(size), ctypes.byref(cnt), None)
            if not size.value: return {}
            buf = ctypes.create_string_buffer(size.value)
            if pdh.PdhGetFormattedCounterArrayW(c, FMT, ctypes.byref(size), ctypes.byref(cnt), buf) != 0: return {}
            it = ctypes.cast(buf, ctypes.POINTER(ITEM)); out = {}
            for i in range(cnt.value):
                m = re.match(r'(\d+)', it[i].name or '')
                if m: out[int(m.group(1))] = max(0.0, it[i].v.dbl)
            return out
        while not self.stop:
            time.sleep(1.0)
            try:
                if pdh.PdhCollectQueryData(q) != 0: continue
                idle = arr(ci); rd = arr(cr); wr = arr(cw); now = time.time()
                for n in set(idle) | set(rd) | set(wr):
                    self.data[n] = {'busy': max(0.0, min(100.0, 100.0 - idle.get(n, 100.0))), 'rd': rd.get(n, 0.0), 'wr': wr.get(n, 0.0), 't': now}
                self.ok = True
            except Exception: pass

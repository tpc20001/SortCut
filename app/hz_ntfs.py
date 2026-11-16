"""HotZone FM — NTFS level access (Windows, administrator).

  * volume data, free-space bitmap, where a file's clusters are (retrieval pointers)
  * FSCTL_MOVE_FILE: the official defragmentation API - NTFS moves the clusters itself, safe while the file is in use
    and safe on power loss (the move is journaled; the old clusters are freed only after the new ones are written)
  * raw $MFT reader (Everything style: whole drive index in seconds) and the USN change journal

Cluster numbers (LCN) count from the beginning of the volume. On a hard disk the beginning of the first partition is
the outer edge of the platters, which is the fastest part (about 1.5-2x the inner edge).
"""
from __future__ import annotations

import ctypes
import struct
import time

from hz_common import IS_WIN
import hz_win as W

FSCTL_GET_NTFS_VOLUME_DATA = 0x00090064
FSCTL_GET_VOLUME_BITMAP = 0x0009006F
FSCTL_GET_RETRIEVAL_POINTERS = 0x00090073
FSCTL_MOVE_FILE = 0x00090074
FSCTL_QUERY_USN_JOURNAL = 0x000900F4
FSCTL_READ_USN_JOURNAL = 0x000900BB
FSCTL_CREATE_USN_JOURNAL = 0x000900E7

ERROR_JOURNAL_NOT_ACTIVE = 1179
ERROR_JOURNAL_DELETE_IN_PROGRESS = 1178
ERROR_JOURNAL_ENTRY_DELETED = 1181

FRN_MASK = 0x0000FFFFFFFFFFFF
EPOCH_DIFF = 11644473600


class NtfsError(Exception):
    def __init__(self, msg, code=0):
        super().__init__(msg); self.code = code


if IS_WIN:
    from ctypes import wintypes

    class MOVE_FILE_DATA(ctypes.Structure):
        _fields_ = [('FileHandle', ctypes.c_void_p), ('StartingVcn', ctypes.c_longlong),
                    ('StartingLcn', ctypes.c_longlong), ('ClusterCount', wintypes.DWORD)]


class FileRef:
    """An open file on the volume (FILE_READ_ATTRIBUTES is all MOVE_FILE needs; the file stays usable by others)."""
    def __init__(self, vol, path):
        self.vol = vol; self.path = path
        self.h, err = W.open_handle(W.lp(path), W.FILE_READ_ATTRIBUTES, W.FILE_SHARE_ALL, W.OPEN_EXISTING, W.FILE_FLAG_BACKUP_SEMANTICS)
        if not self.h: raise NtfsError(f'無法開啟（{err}）', err)

    def close(self):
        W.close_handle(self.h); self.h = None

    def __enter__(self): return self
    def __exit__(self, *a): self.close()

    def extents(self):
        """[(vcn, lcn, count)] ; lcn = -1 for sparse / compressed holes. [] = no clusters (tiny file lives in the MFT)."""
        out = []; vcn = 0
        while True:
            ok, data, err = W.ioctl(self.h, FSCTL_GET_RETRIEVAL_POINTERS, struct.pack('<q', vcn), 16 + 16 * 512)
            if not ok and err not in (W.ERROR_MORE_DATA,):
                if err == W.ERROR_HANDLE_EOF: return out
                raise NtfsError(f'讀不到檔案位置（{err}）', err)
            if len(data) < 16: return out
            n, start = struct.unpack_from('<I4xq', data, 0)
            prev = start
            for i in range(n):
                nxt, lcn = struct.unpack_from('<qq', data, 16 + 16 * i)
                out.append((prev, lcn, nxt - prev)); prev = nxt
            if ok: return out
            vcn = prev

    def move(self, vcn, lcn, count):
        """Move `count` clusters of this file starting at vcn to the free clusters starting at lcn. -> (ok, error)."""
        m = MOVE_FILE_DATA(self.h, vcn, lcn, count)
        ok, data, err = W.ioctl(self.vol.h, FSCTL_MOVE_FILE, bytes(m), 0)
        return ok, err


class NtfsVolume:
    def __init__(self, letter: str):
        if not IS_WIN: raise NtfsError('只有 Windows 才能直接存取 NTFS')
        self.letter = letter.upper().rstrip('\\')
        self.h, err = W.open_handle('\\\\.\\' + self.letter, W.GENERIC_READ, 0x1 | 0x2, W.OPEN_EXISTING, 0)
        if not self.h:
            raise NtfsError('需要系統管理員權限' if err == W.ERROR_ACCESS_DENIED else f'無法開啟磁碟區（{err}）', err)
        try:
            self.vd = self.volume_data()
        except BaseException:                                   # not NTFS: do not keep the volume handle (USB eject)
            W.close_handle(self.h); self.h = None; raise
        self._buf = None

    def close(self):
        W.close_handle(self.h); self.h = None

    def __enter__(self): return self
    def __exit__(self, *a): self.close()

    def volume_data(self):
        ok, d, err = W.ioctl(self.h, FSCTL_GET_NTFS_VOLUME_DATA, None, 512)
        if not ok or len(d) < 96: raise NtfsError(f'不是 NTFS 或讀取失敗（{err}）', err)
        f = struct.unpack_from('<qqqqqIIIIqqqqq', d, 0)
        keys = ('serial', 'sectors', 'total_clusters', 'free_clusters', 'reserved', 'bytes_per_sector', 'cluster', 'frs_size',
                'clusters_per_frs', 'mft_valid', 'mft_start', 'mft2_start', 'mft_zone_start', 'mft_zone_end')
        return dict(zip(keys, f))

    def info(self):
        v = self.vd = self.volume_data()
        return {'cluster': v['cluster'], 'total_clusters': v['total_clusters'], 'free_clusters': v['free_clusters'],
                'mft_zone': (v['mft_zone_start'], v['mft_zone_end']), 'mft_start': v['mft_start'], 'sector': v['bytes_per_sector']}

    def bitmap(self, lcn0: int, count: int):
        """Free-space bitmap -> (first_lcn, bytes). bit i (LSB first) = cluster first_lcn+i in use. first_lcn may be < lcn0."""
        total = self.vd['total_clusters']
        count = max(0, min(count, total - lcn0))
        end = lcn0 + count
        out = bytearray(); first = None; cur = lcn0
        while cur < end:
            want = min((end - cur + 7) // 8 + 8, 32 * 1024 * 1024)
            ok, d, err = W.ioctl(self.h, FSCTL_GET_VOLUME_BITMAP, struct.pack('<q', cur), 16 + want)
            if len(d) < 16:
                raise NtfsError(f'讀不到空間點陣圖（{err}）', err)
            start, size = struct.unpack_from('<qq', d, 0)
            if first is None:
                first = start
            elif start != first + len(out) * 8:                      # NTFS rounded the start: keep the bitmap continuous
                del out[max(0, (start - first) // 8):]
            chunk = d[16:16 + min(len(d) - 16, (size + 7) // 8)]
            out += chunk
            cur = start + len(chunk) * 8
            if not chunk or cur >= total: break
        return (first if first is not None else lcn0), bytes(out)

    def open_file(self, path) -> FileRef:
        return FileRef(self, path)

    zone_keys = 'frn'                                # zone_files() names files by MFT record number

    def zone_files(self, zone_end, stop=None, pace=None):
        return mft_zone_files(self, zone_end, stop, pace=pace)

    # ------------------------------------------------------------------------------------------ raw reads
    def read_at(self, offset: int, size: int) -> bytes:
        import mmap
        if self._buf is None or len(self._buf) < size:
            self._buf = mmap.mmap(-1, max(size, 1 << 20))
        addr = ctypes.addressof(ctypes.c_char.from_buffer(self._buf))
        pos = ctypes.c_longlong(0)
        if not W._k32.SetFilePointerEx(self.h, offset, ctypes.byref(pos), 0):
            e = ctypes.get_last_error(); raise NtfsError(f'讀取位置錯誤（{e}）', e)
        n = wintypes.DWORD(0)
        if not W._k32.ReadFile(self.h, addr, size, ctypes.byref(n), None):
            e = ctypes.get_last_error(); raise NtfsError(f'讀取失敗（{e}）', e)
        return self._buf[:n.value]

    # ------------------------------------------------------------------------------------------ USN journal
    def usn_query(self):
        ok, d, err = W.ioctl(self.h, FSCTL_QUERY_USN_JOURNAL, None, 80)
        if not ok or len(d) < 56: return None, err
        jid, first, nxt, lowest, mx, msize, delta = struct.unpack_from('<QqqqqQQ', d, 0)
        return {'id': jid, 'first': first, 'next': nxt, 'lowest': lowest}, 0

    def usn_create(self, max_size=64 * 1024 * 1024, delta=8 * 1024 * 1024):
        ok, d, err = W.ioctl(self.h, FSCTL_CREATE_USN_JOURNAL, struct.pack('<QQ', max_size, delta), 0)
        return ok, err

    def usn_read(self, start_usn: int, journal_id: int, size=256 * 1024):
        """-> (next_usn, [records]) ; raises NtfsError(code=1181) when the journal no longer reaches start_usn."""
        inp = struct.pack('<qIIQQQ', start_usn, 0xFFFFFFFF, 0, 0, 0, journal_id)
        ok, d, err = W.ioctl(self.h, FSCTL_READ_USN_JOURNAL, inp, size)
        if not ok and err != W.ERROR_HANDLE_EOF:
            raise NtfsError(f'讀取變更日誌失敗（{err}）', err)
        if len(d) < 8: return start_usn, []
        return struct.unpack_from('<q', d, 0)[0], parse_usn_records(d, 8)


def parse_usn_records(d: bytes, off: int):
    out = []
    while off + 8 <= len(d):
        rl, major = struct.unpack_from('<IH', d, off)
        if rl < 60 or off + rl > len(d): break
        if major == 2:
            frn, pfrn, usn, ts, reason, src, sec, attrs, nl, no = struct.unpack_from('<QQqqIIIIHH', d, off + 8)
        elif major == 3:
            frn, _hi, pfrn, _phi, usn, ts, reason, src, sec, attrs, nl, no = struct.unpack_from('<QQQQqqIIIIHH', d, off + 8)
        else:
            off += rl; continue
        name = d[off + no:off + no + nl].decode('utf-16-le', 'replace')
        out.append((frn & FRN_MASK, pfrn & FRN_MASK, reason, attrs, name, ts))
        off += rl
    return out


USN_REASON_DATA = 0x1 | 0x2 | 0x4 | 0x10 | 0x20 | 0x40
USN_REASON_CREATE = 0x100
USN_REASON_DELETE = 0x200
USN_REASON_RENAME_OLD = 0x1000
USN_REASON_RENAME_NEW = 0x2000
USN_REASON_BASIC = 0x8000


# ============================================================================================ $MFT parsing
def apply_fixup(rec: bytearray, stride=512) -> bool:
    usa_off, usa_cnt = struct.unpack_from('<HH', rec, 4)
    if usa_cnt < 2 or usa_off + usa_cnt * 2 > len(rec): return False
    usn = rec[usa_off:usa_off + 2]
    for i in range(1, usa_cnt):
        p = i * stride - 2
        if p + 2 > len(rec): break
        if rec[p:p + 2] != usn: return False
        rec[p:p + 2] = rec[usa_off + 2 * i:usa_off + 2 * i + 2]
    return True


def parse_runlist(b: bytes, off: int):
    """NTFS mapping pairs -> [(lcn, length)] ; lcn None = sparse."""
    runs = []; lcn = 0
    while off < len(b):
        hdr = b[off]
        if hdr == 0: break
        ln = hdr & 0x0F; lo = hdr >> 4; off += 1
        if ln == 0 or off + ln + lo > len(b): break
        length = int.from_bytes(b[off:off + ln], 'little'); off += ln
        if lo:
            delta = int.from_bytes(b[off:off + lo], 'little', signed=True); off += lo
            lcn += delta; runs.append((lcn, length))
        else:
            runs.append((None, length))
    return runs


def parse_record(rec: bytearray):
    """One MFT record (fixups applied) -> dict or None.
    {'flags', 'base', 'names': [(parent, ns, name)], 'size', 'data_first', 'mtime', 'attrs', 'runs' (unnamed $DATA, first segment)}"""
    if rec[0:4] != b'FILE': return None
    attr_off, flags, used = struct.unpack_from('<HHI', rec, 20)
    base = struct.unpack_from('<Q', rec, 32)[0] & FRN_MASK
    r = {'flags': flags, 'base': base, 'names': [], 'size': None, 'mtime': 0, 'attrs': 0, 'runs': None, 'segs': None, 'alist': False}
    off = attr_off; end = min(used, len(rec))
    while off + 16 <= end:
        atype, alen = struct.unpack_from('<II', rec, off)
        if atype == 0xFFFFFFFF or alen < 16 or off + alen > end: break
        nonres = rec[off + 8]; nlen = rec[off + 9]
        if atype == 0x10 and not nonres:                                         # $STANDARD_INFORMATION
            vlen, voff = struct.unpack_from('<IH', rec, off + 16)
            if vlen >= 36:
                p = off + voff
                r['mtime'] = struct.unpack_from('<q', rec, p + 8)[0]
                r['attrs'] = struct.unpack_from('<I', rec, p + 32)[0]
        elif atype == 0x30 and not nonres:                                       # $FILE_NAME
            vlen, voff = struct.unpack_from('<IH', rec, off + 16)
            p = off + voff
            if vlen >= 66:
                parent = struct.unpack_from('<Q', rec, p)[0] & FRN_MASK
                fnl = rec[p + 64]; ns = rec[p + 65]
                name = bytes(rec[p + 66:p + 66 + fnl * 2]).decode('utf-16-le', 'replace')
                r['names'].append((parent, ns, name))
        elif atype == 0x20:                                                      # $ATTRIBUTE_LIST: parts live in extension records
            r['alist'] = True
        elif atype == 0x80 and nlen == 0:                                        # unnamed $DATA
            if not nonres:
                r['size'] = struct.unpack_from('<I', rec, off + 16)[0]
            else:
                svcn = struct.unpack_from('<q', rec, off + 16)[0]
                ro = struct.unpack_from('<H', rec, off + 32)[0]
                if svcn == 0:
                    r['size'] = struct.unpack_from('<q', rec, off + 48)[0]
                    r['runs'] = parse_runlist(bytes(rec[off:off + alen]), ro)
                else:                                                            # a later segment (very fragmented file)
                    r['segs'] = (r['segs'] or []) + [(svcn, parse_runlist(bytes(rec[off:off + alen]), ro))]
        off += alen
    return r


def best_name(names):
    """Win32 (1) or Win32&DOS (3) name first, POSIX (0) next, DOS 8.3 (2) last."""
    if not names: return None
    for want in (1, 3, 0, 2):
        for n in names:
            if n[1] == want: return n
    return names[0]


def filetime_to_unix(ft: int) -> int:
    return int(ft // 10_000_000 - EPOCH_DIFF) if ft > 0 else 0


def iter_mft(vol, progress=None, stop=None, chunk=8 * 1024 * 1024):
    """Read the whole $MFT of `vol` (NtfsVolume or anything with .vd and .read_at).
    Yields (rec_no, parent, name, is_dir, size, mtime_unix, attrs) for every in-use file / folder (including the root, 5).
    Extension records are folded into their base record at the end."""
    vd = vol.vd
    cl = vd['cluster']; frs = vd['frs_size']
    first_read = max(frs, cl)
    rec0 = bytearray(vol.read_at(vd['mft_start'] * cl, first_read)[:frs])
    if not apply_fixup(rec0): raise NtfsError('$MFT 第一筆紀錄損壞')
    p0 = parse_record(rec0)
    if not p0 or not p0['runs']: raise NtfsError('讀不到 $MFT 的位置（可能被嚴重分割，改用一般掃描）')
    total_recs = (p0['size'] or vd['mft_valid']) // frs
    if sum(n for _l, n in p0['runs']) * cl < total_recs * frs:          # rest of the runlist is in an $ATTRIBUTE_LIST extension
        raise NtfsError('$MFT 分割太多（位置清單在延伸紀錄裡），改用一般掃描')
    ext_size = {}; ext_names = {}; pending = {}
    rec_no = 0; done_bytes = 0; total_bytes = total_recs * frs
    carry = b''                                                         # a record split across two runs (tiny clusters)
    for lcn, length in p0['runs']:
        if lcn is None:
            rec_no += length * cl // frs; carry = b''; continue
        byte_off = lcn * cl; remain = length * cl
        while remain > 0 and rec_no < total_recs:
            if stop is not None and stop.is_set(): return
            n = min(remain, chunk)
            got = vol.read_at(byte_off, n)
            if not got: raise NtfsError('讀取 $MFT 中斷')
            byte_off += len(got); remain -= len(got); done_bytes += len(got)
            buf = carry + got if carry else got
            whole = len(buf) - len(buf) % frs
            carry = bytes(buf[whole:]) if whole < len(buf) else b''
            for o in range(0, whole, frs):
                if rec_no >= total_recs: break
                if buf[o:o + 4] == b'FILE':
                    rec = bytearray(buf[o:o + frs])
                    if apply_fixup(rec):
                        flags = struct.unpack_from('<H', rec, 22)[0]
                        if flags & 1:
                            r = parse_record(rec)
                            if r is not None:
                                if r['base']:
                                    if r['size'] is not None: ext_size[r['base']] = r['size']
                                    if r['names']: ext_names.setdefault(r['base'], []).extend(r['names'])
                                elif rec_no >= 24 or rec_no == 5:
                                    nm = best_name(r['names'])
                                    is_dir = bool(r['flags'] & 2)
                                    item = (rec_no, nm[0] if nm else 5, nm[2] if nm else None, is_dir,
                                            0 if is_dir else (r['size'] or 0), filetime_to_unix(r['mtime']), r['attrs'])
                                    if nm is None or (not is_dir and r['size'] is None):
                                        pending[rec_no] = item              # name / size lives in an extension record
                                    else:
                                        yield item
                rec_no += 1
            if progress: progress(min(done_bytes, total_bytes), total_bytes)
    for rn, item in pending.items():
        rn_, parent, name, is_dir, size, mt, at = item
        if name is None:
            nm = best_name(ext_names.get(rn, []))
            if not nm: continue
            parent, name = nm[0], nm[2]
        if not is_dir and rn in ext_size: size = ext_size[rn]
        yield (rn, parent, name, is_dir, size, mt, at)


SKIP_ATTRS = 0x4 | 0x200 | 0x400 | 0x800                                 # system, sparse, reparse point, compressed


def mft_zone_files(vol, zone_end, stop=None, chunk=8 * 1024 * 1024, pace=None):
    """One sequential pass over $MFT -> [(rec_no, size, [(vcn, lcn, n)])] for every file with clusters in
    [0, zone_end). Used to choose WHICH cold files to move so the freed space is contiguous; the moves themselves
    always ask NTFS again (FSCTL_GET_RETRIEVAL_POINTERS), so a stale or partial map can never cause damage.
    Very fragmented files whose $DATA continues in extension records are put together at the end. Compressed,
    sparse, encrypted-system and reparse files are left out (NTFS would refuse or mangle moving them).
    pace(nbytes): called after every chunk read (the caller can slow down / give way; raising stops the pass)."""
    vd = vol.vd
    cl = vd['cluster']; frs = vd['frs_size']
    rec0 = bytearray(vol.read_at(vd['mft_start'] * cl, max(frs, cl))[:frs])
    if not apply_fixup(rec0): raise NtfsError('$MFT 第一筆紀錄損壞')
    p0 = parse_record(rec0)
    if not p0 or not p0['runs']: raise NtfsError('讀不到 $MFT 的位置')
    total_recs = (p0['size'] or vd['mft_valid']) // frs
    out = []; rec_no = 0; carry = b''
    held = {}                                       # base record with an attribute list -> (size, ok, pieces so far)
    ext = {}                                        # base record -> pieces / size found in its extension records

    def zone_pcs(segs):
        pcs = []
        for svcn, runs in segs:
            vcn = svcn
            for lcn, n in runs:
                if lcn is not None and lcn < zone_end and n > 0:
                    pcs.append((vcn, lcn, min(n, zone_end - lcn)))
                vcn += n
        return pcs
    for lcn0, length in p0['runs']:
        if lcn0 is None:
            rec_no += length * cl // frs; carry = b''; continue
        byte_off = lcn0 * cl; remain = length * cl
        while remain > 0 and rec_no < total_recs:
            if stop is not None and stop.is_set(): return out
            got = vol.read_at(byte_off, min(remain, chunk))
            if not got: raise NtfsError('讀取 $MFT 中斷')
            byte_off += len(got); remain -= len(got)
            if pace: pace(len(got))
            buf = carry + got if carry else got
            whole = len(buf) - len(buf) % frs
            carry = bytes(buf[whole:]) if whole < len(buf) else b''
            for o in range(0, whole, frs):
                if rec_no >= total_recs: break
                if buf[o:o + 4] == b'FILE':
                    rec = bytearray(buf[o:o + frs])
                    if apply_fixup(rec) and struct.unpack_from('<H', rec, 22)[0] & 1:
                        r = parse_record(rec)
                        if r and r['base']:                                  # extension record: pieces of its base file
                            segs = ([(0, r['runs'])] if r['runs'] else []) + (r['segs'] or [])
                            pcs = zone_pcs(segs)
                            if pcs or r['size'] is not None:
                                e = ext.setdefault(r['base'], [None, []])
                                if r['size'] is not None: e[0] = r['size']
                                e[1].extend(pcs)
                        elif r and rec_no >= 24 and not (r['flags'] & 2):
                            ok = not (r['attrs'] & SKIP_ATTRS)
                            segs = ([(0, r['runs'])] if r['runs'] else []) + (r['segs'] or [])
                            pcs = zone_pcs(segs) if ok else []
                            if r['alist']: held[rec_no] = (r['size'] or 0, ok, pcs)
                            elif pcs: out.append((rec_no, r['size'] or 0, pcs))
                rec_no += 1
    for rn, (size, ok, pcs) in held.items():
        e = ext.get(rn)
        if not ok: continue
        if e: pcs = pcs + e[1]; size = e[0] if e[0] is not None else size
        if pcs: out.append((rn, size, sorted(pcs)))
    return out


def ntfs_available(letter: str) -> tuple[bool, str]:
    if not IS_WIN: return False, '不是 Windows'
    if not W.is_admin(): return False, '需要系統管理員權限'
    try:
        with NtfsVolume(letter) as v:
            return True, ''
    except NtfsError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)

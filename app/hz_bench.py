"""HotZone FM — 外圈／內圈測速: read-only speed test of one volume at 10 positions from the start (outer tracks)
to the end (inner tracks), straight from the disk (no cache). Shows on the user's own HDD how much faster the
outer zone is — i.e. what 熱處理 gains. Nothing is written.
"""
from __future__ import annotations

import ctypes
import mmap
import threading
import time

from hz_common import IS_WIN, DATA_DIR, read_json, atomic_write_json

BENCH_FILE = DATA_DIR / 'bench.json'


def last_results():
    return read_json(BENCH_FILE, {}) or {}
import hz_win as W

FILE_FLAG_NO_BUFFERING = 0x20000000


class Bench:
    def __init__(self, eng):
        self.eng = eng; self.lock = threading.Lock(); self.th = None; self.stop_ev = threading.Event()
        self.st = {'state': 'idle', 'letter': '', 'points': [], 'msg': ''}

    def start(self, letter, points=10, mb=128):
        if not IS_WIN: raise ValueError('測速只支援 Windows')
        if not W.is_admin(): raise ValueError('需要系統管理員權限（背景引擎要以系統管理員執行）')
        L = letter.rstrip('\\').upper()
        try:                                                                 # our own disk work would spoil the numbers
            busy_hot = any(v.get('state') == 'moving' and v.get('letter', '').upper() == L for v in (self.eng.hot.status() or {}).get('vols', []))
        except Exception:
            busy_hot = False
        if busy_hot: raise ValueError('熱處理正在搬這顆硬碟，請先按「暫停搬移」再測速')
        if self.eng.queue_busy_any(): raise ValueError('傳輸佇列正在工作，請等它做完（或全部暫停）再測速')
        with self.lock:
            if self.st['state'] == 'running': raise ValueError('已經在測了')
            self.st = {'state': 'running', 'letter': letter.rstrip('\\').upper(), 'points': [], 'msg': '準備中…', 't': time.time()}
        self.th = threading.Thread(target=self._run, args=(self.st['letter'], int(points), int(mb)), name='HZ-Bench', daemon=True)
        self.th.start()
        return self.st

    def status(self):
        return dict(self.st)

    def stop(self):
        self.stop_ev.set()
        if self.th and self.th.is_alive(): self.th.join(3)

    def _run(self, letter, points, mb):
        st = self.st
        try:
            h, err = W.open_handle('\\\\.\\' + letter, W.GENERIC_READ, 0x1 | 0x2, W.OPEN_EXISTING, FILE_FLAG_NO_BUFFERING)
            if not h: raise RuntimeError(f'無法開啟磁碟區（{err}）')
            ok, d, err = W.ioctl(h, 0x7405C, None, 8)                         # IOCTL_DISK_GET_LENGTH_INFO: any file system
            if not ok or len(d) < 8:
                W.close_handle(h); raise RuntimeError(f'讀不到磁碟區大小（{err}）')
            import struct
            total = struct.unpack_from('<q', d, 0)[0]
            chunk = 8 * 1024 * 1024
            buf = mmap.mmap(-1, chunk)                                        # page aligned, as NO_BUFFERING requires
            addr = ctypes.addressof(ctypes.c_char.from_buffer(buf))
            span = mb * 1024 * 1024
            if total < (span + chunk) * 2:
                W.close_handle(h); raise RuntimeError('磁碟區太小，不需要測')
            try:
                for i in range(points):
                    if self.stop_ev.is_set(): raise RuntimeError('已停止')
                    pos = int((total - span - chunk) * i / max(1, points - 1)) // (1024 * 1024) * (1024 * 1024)
                    st['msg'] = f'測第 {i + 1} / {points} 個位置（{i * 100 // max(1, points - 1)}%）'
                    newpos = ctypes.c_longlong(0)
                    if not W._k32.SetFilePointerEx(h, pos, ctypes.byref(newpos), 0): raise RuntimeError(f'定位失敗（{ctypes.get_last_error()}）')
                    n = wintypes_dword(); done = 0; t0 = time.perf_counter()
                    while done < span:
                        if not W._k32.ReadFile(h, addr, chunk, ctypes.byref(n), None) or n.value == 0:
                            raise RuntimeError(f'讀取失敗（{ctypes.get_last_error()}）')
                        done += n.value
                    dt = time.perf_counter() - t0
                    st['points'].append({'pct': round(pos / total * 100, 1), 'mbps': round(done / dt / 1024 / 1024, 1)})
            finally:
                W.close_handle(h)
                try: buf.close()
                except Exception: pass
            p = st['points']
            if p:
                outer, inner = p[0]['mbps'], p[-1]['mbps']
                st['msg'] = f'外圈 {outer:.0f} MB/s，內圈 {inner:.0f} MB/s：外圈快 {outer / max(inner, 0.1):.1f} 倍'
                try:                                                         # remembered: the hot page shows the last result
                    saved = read_json(BENCH_FILE, {}) or {}
                    saved[letter] = {'t': time.time(), 'outer': outer, 'inner': inner, 'points': p}
                    atomic_write_json(BENCH_FILE, saved, indent=None)
                except Exception:
                    pass
            st['state'] = 'done'
        except Exception as e:
            st.update(state='error', msg=str(e))


def wintypes_dword():
    from ctypes import wintypes
    return wintypes.DWORD(0)

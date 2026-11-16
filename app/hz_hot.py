"""HotZone FM — hot zone: keep the files of "hot" folders on the fastest part of a hard disk.

A hard disk is fastest at the outer edge of the platters = the lowest cluster numbers (LCN) of the first partition.
The hot zone of a volume is clusters [0, zone_end). For every volume that holds hot folders a relocator thread:

  1. lists the hot files (from the index, else by walking the folders), newest first (or largest / by name)
  2. asks NTFS where each file's clusters are (FSCTL_GET_RETRIEVAL_POINTERS)
  3. if there is not enough free space inside the zone, moves cold files that sit in the zone out to the inner
     tracks (end of the volume) - biggest first
  4. moves the outside parts of every hot file into free space inside the zone (FSCTL_MOVE_FILE)

The move is done by NTFS itself (the same API as Windows defrag): the file stays usable the whole time, nothing is
copied through user space, and a power cut never leaves a half file. Every move is a chunk of hot.chunk_mb; between
chunks the thread rests so that the disk share stays at hot.usage_pct, and it pauses while other programs (or the
transfer queue) use the disk.
"""
from __future__ import annotations

import math
import os
import re
import threading
import time
from bisect import bisect_left, insort
from collections import deque
from heapq import merge

from hz_common import IS_WIN, DATA_DIR, norm, is_under, drive_of, fmt_size, read_json, atomic_write_json
import hz_win as W

GB = 1024 ** 3
HISTORY_FILE = DATA_DIR / 'hot_history.json'


# ============================================================================================ free space
def free_runs(first, bm, lo, hi, min_len=16):
    """Free cluster runs [lcn, len] inside [lo, hi) from a bitmap that starts at cluster `first` (LSB first)."""
    out = []
    a = max(0, (lo - first) // 8); b = min(len(bm), (hi - first + 7) // 8)
    if a >= b: return out
    for m in re.finditer(rb'\x00+', bm[a:b] if (a or b < len(bm)) else bm):
        ms, me = m.start() + a, m.end() + a
        s = first + ms * 8; e = first + me * 8
        if ms > 0:
            v = bm[ms - 1]; k = 0
            while k < 8 and not (v >> (7 - k)) & 1: k += 1
            s -= k
        if me < len(bm):
            v = bm[me]; k = 0
            while k < 8 and not (v >> k) & 1: k += 1
            e += k
        s = max(s, lo); e = min(e, hi)
        if e - s >= min_len: out.append([s, e - s])
    return out


def cut(runs, lo, hi):
    """Remove [lo, hi) from runs."""
    out = []
    for s, n in runs:
        e = s + n
        if e <= lo or s >= hi: out.append([s, n]); continue
        if s < lo: out.append([s, lo - s])
        if e > hi: out.append([hi, e - hi])
    return out


class Allocator:
    """Free runs to fill. from_end=True hands out the highest runs first (cold data -> inner tracks), filling each run
    from its start so a file stays in forward order. min_piece: when a piece has to be split over several runs, runs
    smaller than this are not used (a hot file spread over thousands of 64 KB gaps would be slower than before).
    Fast with 100k+ free runs: runs are kept in two sorted lists (small gaps / big runs) with running totals and
    in-place updates, so a big piece never walks the thousands of tiny gaps it could not use anyway."""
    def __init__(self, runs, from_end=False, min_piece=1):
        self.from_end = from_end; self.min_piece = max(1, int(min_piece))
        self._set(runs)

    def _set(self, runs):
        rs = sorted([list(r) for r in runs if r[1] > 0], key=lambda r: r[0], reverse=self.from_end)
        self.small = [r for r in rs if r[1] < self.min_piece]; self.big = [r for r in rs if r[1] >= self.min_piece]
        self._tot = sum(r[1] for r in rs); self._big = sum(r[1] for r in self.big)

    @property
    def runs(self):
        return list(merge(self.small, self.big, key=self._key))

    def _key(self, r): return -r[0] if self.from_end else r[0]

    def _list(self, n): return self.big if n >= self.min_piece else self.small

    def _add(self, r):
        insort(self._list(r[1]), r, key=self._key); self._tot += r[1]
        if r[1] >= self.min_piece: self._big += r[1]

    def _remove(self, lst, i):
        r = lst.pop(i); self._tot -= r[1]
        if lst is self.big: self._big -= r[1]
        return r

    def give_back(self, lcn, n):
        """Return clusters (a target not used after all)."""
        if n > 0: self._add([lcn, n])

    def total(self):
        return self._tot

    def usable(self, n):
        """Clusters really usable for a piece of n clusters (small gaps only count if the whole piece fits)."""
        big = self._big
        if big >= n: return big
        return n if any(r[1] >= n for r in self.small) else big

    def take(self, n, src=0, align=1, far=False, rest=None, after=None):
        """-> [(lcn, len)] totalling n clusters (or less if full). Prefers one run that fits whole.
        align > 1: every piece keeps (target - source) % align == 0 (Microsoft: keep moves 16 KB aligned so volume
        shadow copies / restore points do not have to copy every moved cluster).
        rest: how much of the piece is still to come (this chunk included). A run smaller than min_piece is only used
        when all of that rest fits in it - otherwise every big file would end with its tail in some tiny gap.
        after: where the previous chunk of the same piece ended - continuing right there keeps the file in one piece."""
        if n <= 0: return []
        rest = max(n, rest or n)
        align = max(1, int(align))

        def fit(r, k, s0):
            if far:                                                          # retry after a refusal: far end of the run
                l = r[0] + r[1] - k
                l -= (l - s0) % align
                return l if l >= r[0] else None
            l = r[0] + (s0 - r[0]) % align                                   # from the start: forward order on disk
            return l if l + k <= r[0] + r[1] else None

        def cut_out(lst, i, l, k):
            r = self._remove(lst, i)
            for x in ([r[0], l - r[0]], [l + k, r[0] + r[1] - l - k]):
                if x[1] > 0: self._add(x)

        def find(lst, start_key=None):
            """First run (in order) in lst that takes n whole -> (i, l) or None."""
            rng = range(len(lst) - 1, -1, -1) if far else range(len(lst))
            for i in rng:
                r = lst[i]
                if r[1] < n: continue
                l = fit(r, n, src)
                if l is not None: return i, l
            return None
        if after is not None and not far:
            for lst in (self.big, self.small):
                i = bisect_left(lst, -after if self.from_end else after, key=self._key)
                if i < len(lst) and lst[i][0] == after:
                    if lst is self.small and lst[i][1] < rest: break         # continuing into a tiny gap: no
                    l = fit(lst[i], n, src)
                    if l == after: cut_out(lst, i, l, n); return [(l, n)]
                    break
        cands = []
        b = find(self.big)
        if b: cands.append((self.big, b))
        if far or rest < self.min_piece:                                     # tiny gaps only for a whole small remainder
            sm = find(self.small) if far else None
            if not far:
                for i, r in enumerate(self.small):
                    if r[1] >= n and r[1] >= rest:
                        l = fit(r, n, src)
                        if l is not None: sm = (i, l); break
            if sm: cands.append((self.small, sm))
        if cands:
            lst, (i, l) = min(cands, key=lambda c: (self._key(c[0][c[1][0]]) * (-1 if far else 1)))
            cut_out(lst, i, l, n); return [(l, n)]
        if far: return []
        out = []; left = n; s0 = src
        for r in self.runs:                                                  # split over several runs, in disk order
            if left <= 0: break
            if r[1] < self.min_piece and r[1] < rest - (n - left): continue  # tiny gap: not for a split piece
            k = min(left, r[1] - (align - 1))
            while k > 0 and fit(r, k, s0) is None: k -= 1
            if k <= 0: continue
            l = fit(r, k, s0)
            lst = self._list(r[1]); i = bisect_left(lst, self._key(r), key=self._key)
            cut_out(lst, i, l, k)
            out.append((l, k)); left -= k; s0 += k
        return out

    def take_exact(self, n, src=0, align=1):
        """One run of exactly n clusters far from the last try, or None (retries: a refused area is often a block)."""
        got = self.take(n, src, align, far=True)
        if len(got) == 1 and got[0][1] == n: return got[0]
        for l, k in got: self.give_back(l, k)
        return None

    def drop(self, lcn, n):
        """Target clusters turned out to be unusable (in use / reserved): forget them."""
        self._set(cut(self.runs, lcn, lcn + n))


def split_extents(ext, zone_end):
    """[(vcn, lcn, n)] -> (clusters inside zone, list of outside pieces (vcn, lcn, n))."""
    inside = 0; outside = []
    for vcn, lcn, n in ext:
        if lcn < 0 or n <= 0: continue
        e = lcn + n
        if e <= zone_end: inside += n
        elif lcn >= zone_end: outside.append((vcn, lcn, n))
        else:
            k = zone_end - lcn; inside += k
            outside.append((vcn + k, zone_end, n - k))
    return inside, outside


def inside_pieces(ext, zone_end, mft_zone=None):
    """Pieces of a file inside [0, zone_end) - minus NTFS's reserved MFT zone (freeing that gains nothing)."""
    out = []
    mz0, mz1 = mft_zone if mft_zone and mft_zone[1] > mft_zone[0] else (0, 0)
    for vcn, lcn, n in ext:
        if lcn < 0 or n <= 0 or lcn >= zone_end: continue
        k = min(n, zone_end - lcn)
        a, b = lcn, lcn + k
        for s_, e_ in ((a, min(b, mz0)), (max(a, mz1), b)) if mz1 > mz0 else ((a, b),):
            if e_ > s_: out.append((vcn + (s_ - lcn), s_, e_ - s_))
    return out


def count_shadow_copies(letter):
    """Number of volume shadow copies (restore points, 'previous versions') of a volume. 0 if none, -1 if it could not
    be found out (PowerShell blocked, WMI broken, timeout): then we ask instead of assuming there are none."""
    if not IS_WIN: return 0
    import subprocess
    ps = ("$v = Get-CimInstance Win32_Volume -Filter \"DriveLetter='%s'\"; "
          "if ($v) { @(Get-CimInstance Win32_ShadowCopy | Where-Object { $_.VolumeName -eq $v.DeviceID }).Count } else { 0 }") % letter.rstrip('\\')
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps], capture_output=True, text=True, errors='replace', timeout=60,
                           creationflags=W.no_window_flags())
        m = re.search(r'(\d+)\s*$', r.stdout or '')
        return int(m.group(1)) if m and r.returncode == 0 else -1
    except Exception:
        return -1


# ============================================================================================ relocator
class Relocator(threading.Thread):
    def __init__(self, mgr, letter):
        super().__init__(name='HZ-Hot-' + letter, daemon=True)
        self.mgr = mgr; self.letter = letter
        self.stop_ev = threading.Event(); self.wake = threading.Event()
        self.priority: list = []                     # paths just added to a hot folder (moved first)
        self.st = {'letter': letter, 'state': 'idle', 'msg': '', 'hot_files': 0, 'hot_bytes': 0, 'in_bytes': 0, 'out_bytes': 0,
                   'moved_bytes': 0, 'evicted_bytes': 0, 'rate': 0.0, 'eta': None, 'cur': '', 'zone_gb': 0, 'cluster': 0,
                   'total_clusters': 0, 'zone_end': 0, 'zone_free': 0, 'mft_zone': None, 'plan_t': 0, 'errors': [],
                   'skipped': 0, 'evict_need': 0, 'dry': None, 'session_t': time.time(), 'done_t': 0}
        self.hot_cells = None
        self.hist = deque(); self.hist_sum = 0
        self.bad = []                                # [(lcn, n, until)] targets NTFS refused (reserved / not really free yet)
        self.skipped_files = {}                      # path -> (until, (size, mtime)) files NTFS would not move
        self.idle_naps = 0
        self.last_move_end = 0.0                     # wall time of our last cluster move (disk counters judge others)
        self.last_listen = 0.0; self.others = 0.0
        self.vss = {'t': 0, 'n': 0}
        self._released = False                       # set when a closed gate made us let go of the handles
        self._plan_state = None                      # a plan interrupted by a closed gate resumes (not from file 0)
        self._light = False                          # this round only handles files that just arrived
        self._zmap = None                            # MFT zone map, reused for 15 min (reading a big $MFT is costly)

    # --------------------------------------------------------------------------- helpers
    def S(self, k): return self.mgr.S.get(k)

    def log(self, msg, lv='info'):
        getattr(self.mgr.log, lv)('hot', f'{self.letter} {msg}')

    def set(self, **kw): self.st.update(kw)

    def stopped(self): return self.stop_ev.is_set()

    def nap(self, sec):
        self.wake.wait(sec); self.wake.clear()
        return self.stopped()

    def lane(self):
        ln = self.mgr.drives.lane_of(self.letter + '\\' if IS_WIN else self.letter)
        return ln[0] if ln else 'v' + self.letter

    def err(self, path, msg):
        self.st['errors'] = (self.st['errors'] + [{'path': path, 'msg': msg, 't': time.time()}])[-50:]
        self.st['skipped'] += 1

    def gate_open(self):
        """None when allowed to work now, else a reason (shown in the UI)."""
        if not self.S('hot.enabled'): return '熱區搬移已關閉'
        if self.mgr.paused: return '已暫停'
        mode = self.S('hot.mode')
        if mode == 'hours':
            h0, h1 = (self.S('hot.hours') or [1, 8])[:2]; h = time.localtime().tm_hour
            ok = (h0 <= h < h1) if h0 <= h1 else (h >= h0 or h < h1)
            if not ok: return f'只在 {h0}:00～{h1}:00 搬移'
        ln = self.lane()
        if self.mgr.queue_busy(ln): return '傳輸佇列正在用這顆硬碟，等它做完'
        if self.vss_blocked(): return self.vss_blocked()
        lim = float(self.S('hot.yield_mbps') or 0)
        if (lim > 0 or mode == 'idle') and self.mgr.counters and ln.startswith('d'):
            c = self.clean_sample(int(ln[1:]))
            if c:
                others = c['rd'] + c['wr']
                if lim > 0 and others > lim * 1024 * 1024: return f'讓路：其他程式正在用這顆硬碟（{others / 1048576:.0f} MB/s）'
                if mode == 'idle' and (others > 1024 * 1024 or c['busy'] > 15): return '等硬碟閒置'
        return None

    def clean_sample(self, disk):
        """A disk-counter sample that does not include our own moves (it started after our last move ended).
        While moving continuously there is none, so every 20 s we hold still for a moment and listen."""
        c = self.mgr.counters.get(disk)
        if not c: return None                                             # no counter data for this disk: listening cannot help
        if c['t'] - 1.05 >= self.last_move_end:
            self.last_listen = time.time(); return c
        if self.last_move_end and time.time() - self.last_listen > 20:
            t_end = time.time() + 2.6
            while time.time() < t_end and not self.stopped():
                self.stop_ev.wait(0.25)
                c = self.mgr.counters.get(disk)
                if c and c['t'] - 1.05 >= self.last_move_end:
                    self.last_listen = time.time(); return c
            self.last_listen = time.time()
        return None

    def vss_blocked(self):
        """Volume shadow copies / restore points on this disk: moving clusters makes Windows copy the old data into
        the shadow storage, which can push out (delete) the oldest restore points. Ask once before doing that."""
        if not IS_WIN or self.mgr.volume_factory: return None
        if (self.S('hot.vss_ok') or {}).get(self.letter): return None
        if self.S('hot.dry_run'): return None                              # a dry run moves nothing
        now = time.time()
        if now - self.vss['t'] > 3600:
            self.vss = {'t': now, 'n': count_shadow_copies(self.letter)}
        if self.vss['n'] < 0:
            return '無法確認這顆硬碟有沒有系統還原點（PowerShell / WMI 無法使用）。若有，搬移可能讓 Windows 刪掉較舊的還原點。請在熱處理頁按「我了解，繼續」'
        if self.vss['n'] > 0:
            return f'這顆硬碟有 {self.vss["n"]} 個系統還原點／陰影複製：搬移可能讓 Windows 刪掉較舊的還原點。請在熱處理頁按「我了解，繼續」'
        return None

    def wait_gate(self, limit=None):
        """Block until allowed. Returns True if asked to stop - or, with a limit, when the gate stayed closed longer
        than `limit` seconds (the caller then closes its file / volume handles and comes back later)."""
        t0 = None
        while not self.stopped():
            why = self.gate_open()
            if why is None:
                if t0: self.set(state='moving', msg='')
                return False
            t0 = t0 or time.time()
            self.set(state='waiting', msg=why, rate=0.0)
            if limit is not None and time.time() - t0 > limit:
                self._released = True; return True
            if self.nap(1.0): return True
        return True

    def pace(self, busy, nbytes):
        pct = max(5, min(100, int(self.S('hot.usage_pct') or 60)))
        rest = busy * (100 - pct) / pct
        now = time.monotonic(); hist = self.hist; hist.append((now, nbytes)); self.hist_sum = getattr(self, 'hist_sum', 0) + nbytes
        while hist and now - hist[0][0] >= 10: self.hist_sum -= hist.popleft()[1]   # running sum: many tiny moves stay cheap
        span = max(1.0, now - hist[0][0]) if hist else 1.0
        self.st['rate'] = self.hist_sum / span
        if self.st['rate'] > 0 and self.st['out_bytes'] > 0:
            left = max(0, self.st['out_bytes'] - self.st.get('moved_round', 0)) + max(0, (self.st.get('evict_need') or 0) - self.st.get('evicted_round', 0))
            self.st['eta'] = left / self.st['rate']
        if rest > 0: self.stop_ev.wait(rest)

    # --------------------------------------------------------------------------- planning
    def zone_clusters(self, info, hot_bytes):
        cl = info['cluster']; tot = info['total_clusters']
        gb = float((self.S('hot.zone_gb') or {}).get(self.letter, 0) or 0)
        if gb <= 0:
            gb = max(50.0, hot_bytes / GB * 1.15 + 10)                     # auto: hot data + 15 % + 10 GB,
            gb = math.ceil(gb / 5) * 5                                      # in 5 GB steps (a new file must not move the zone)
        z = int(gb * GB // cl)
        return min(z, int(tot * 0.6)), gb

    def hot_files(self):
        """[(path, size, mtime)] of every file inside the hot folders on this volume."""
        out = []; seen = set()
        for h in self.mgr.folders():
            p = h['path']
            if drive_of(p) != self.letter: continue
            files = self.mgr.index.subtree_files(p) if self.mgr.index else None
            if files is None:
                files = []
                for root, dirs, fs, _links in W.walk(p):
                    if self.stopped(): return out
                    for f in fs:
                        q = os.path.join(root, f)
                        try: st = os.stat(q); files.append((q, st.st_size, st.st_mtime))
                        except OSError: pass
            for f in files:
                k = f[0].lower() if IS_WIN else f[0]
                if k not in seen: seen.add(k); out.append(f)
        order = self.S('hot.order')
        if order == 'largest': out.sort(key=lambda f: -f[1])
        elif order == 'name': out.sort(key=lambda f: f[0].lower())
        else: out.sort(key=lambda f: -f[2])
        return out

    def is_hot(self, path):
        return any(is_under(path, h['path']) for h in self.mgr.folders())

    def plan(self, vol):
        """Look at every hot file: what is inside / outside the zone. -> (todo, info, zone_end)"""
        info = vol.info()
        self._light = (self.st.get('state') == 'done' and bool(self.priority) and self.st.get('zone_end')
                       and time.time() - (self.st.get('plan_t') or 0) < 6 * 3600 and not self._plan_state)
        if self._light:                                                     # all was in place a moment ago and a few files
            return [], info, self.st['zone_end']                            # arrived: handle just those (no full re-plan)
        self.set(state='planning', msg='檢查熱資料的位置…', cur='')
        files = self.hot_files()
        hot_bytes = sum(f[1] for f in files)
        zone_end, gb = self.zone_clusters(info, hot_bytes)
        cl = info['cluster']
        cells = 400; cell_cl = max(1, info['total_clusters'] // cells + 1); hot_cells = [0] * cells
        prio_snapshot = list(self.priority)
        prio = {(p.lower() if IS_WIN else p) for p in prio_snapshot}
        ps = self._plan_state                                              # resume an interrupted plan (same zone, < 15 min)
        if not ps or ps['zone_end'] != zone_end or ps['cells_cl'] != cell_cl or time.time() - ps['t'] > 900:   # t = last progress
            ps = self._plan_state = {'zone_end': zone_end, 'cells_cl': cell_cl, 't': time.time(), 'seen': set(), 'todo': [],
                                     'in_cl': 0, 'out_cl': 0, 'frag_n': 0, 'frag_f': 0, 'cells': [0] * cells}
        hot_cells = ps['cells']; seen = ps['seen']; t_last = time.time(); since = 0
        for n, (p, size, mt) in enumerate(files):
            if self.stopped(): return None
            key = hash(p.lower() if IS_WIN else p)
            if key in seen: continue
            since += 1
            if since % 2000 == 0 and self.wait_gate(limit=30): return None    # planning reads metadata too: share the disk
            seen.add(key); ps['t'] = time.time()
            if self.is_skipped(p): continue
            try:
                with vol.open_file(p) as fh: ext = fh.extents()
            except Exception as e:
                self.err(p, f'讀不到位置：{e}'); continue
            i, outside = split_extents(ext, zone_end)
            ps['in_cl'] += i
            nfr = sum(1 for x in ext if x[1] >= 0 and x[2] > 0)
            if nfr: ps['frag_n'] += nfr; ps['frag_f'] += 1
            for vcn, lcn, k in ext:
                if lcn >= 0 and k > 0:
                    c = min(cells - 1, lcn // cell_cl); hot_cells[c] += k
            if outside:
                o = sum(x[2] for x in outside); ps['out_cl'] += o
                ps['todo'].append((p, o, (p.lower() if IS_WIN else p) in prio))
            if time.time() - t_last > 0.5:
                self.set(msg=f'檢查熱資料的位置… {len(seen):,}/{len(files):,}'); t_last = time.time()
        self._plan_state = None
        if len(seen) > since:                                              # resumed: drop files no longer hot / gone
            cur = {(f[0].lower() if IS_WIN else f[0]) for f in files}
            ps['todo'] = [t for t in ps['todo'] if (t[0].lower() if IS_WIN else t[0]) in cur]
        todo = ps['todo']; in_cl = ps['in_cl']; out_cl = ps['out_cl']; frag_n = ps['frag_n']; frag_f = ps['frag_f']
        todo.sort(key=lambda t: not t[2])                                   # newly added files first, otherwise keep the order
        done_p = set(prio_snapshot)
        self.priority = [p for p in self.priority if p not in done_p]      # paths added while planning stay queued
        mz = info.get('mft_zone') or (0, 0)
        self.hot_cells = {'cells': hot_cells, 'cell_cl': cell_cl}
        self.set(hot_files=len(files), hot_bytes=hot_bytes, in_bytes=in_cl * cl, out_bytes=out_cl * cl, zone_gb=round(zone_end * cl / GB, 1),
                 cluster=cl, total_clusters=info['total_clusters'], zone_end=zone_end, mft_zone=list(mz), plan_t=time.time(),
                 frag=round(frag_n / frag_f, 2) if frag_f else None)
        self.mgr.history_add(self.letter, {'in': in_cl * cl, 'hot': hot_bytes, 'moved': self.st.get('moved_bytes', 0),
                                           'evicted': self.st.get('evicted_bytes', 0), 'frag': self.st.get('frag')})
        return todo, info, zone_end

    def zone_free(self, vol, info, zone_end):
        first, bm = vol.bitmap(0, zone_end)
        runs = free_runs(first, bm, 0, zone_end)
        mz = info.get('mft_zone') or (0, 0)
        if mz[1] > mz[0]: runs = cut(runs, mz[0], mz[1])
        runs = cut(runs, 0, 64)                                             # never touch the very first clusters
        now = time.time(); self.bad = [b for b in self.bad if b[2] > now]
        for b in self.bad: runs = cut(runs, b[0], b[0] + b[1])
        min_piece = max(16, int(float(self.S('hot.min_gap_mb') or 8) * 1024 * 1024) // max(1, info['cluster']))
        return Allocator(runs, min_piece=min_piece)

    def cold_targets(self, vol, info, zone_end):
        """Free space outside the zone for evicted cold data: from the end of the volume (inner tracks) by default."""
        tot = info['total_clusters']; runs = []
        step = 8 * 1024 * 1024 * 8                                          # 8 MB of bitmap per read
        lo = zone_end
        while lo < tot:
            hi = min(tot, lo + step)
            first, bm = vol.bitmap(lo, hi - lo)
            runs += free_runs(first, bm, lo, hi, min_len=256)
            lo = hi
        mz = info.get('mft_zone') or (0, 0)
        if mz[1] > mz[0]: runs = cut(runs, mz[0], mz[1])
        for b in self.bad: runs = cut(runs, b[0], b[0] + b[1])
        return Allocator(runs, from_end=(self.S('hot.cold_to') != 'after'))

    def cold_from_map(self, vol, zone_end):
        """Every non-hot file with clusters in the zone, from one pass over the MFT (fast, complete: small files
        too, so the freed space can be made contiguous). None when not available."""
        if not hasattr(vol, 'zone_files'): return None
        ix = self.mgr.index if self.mgr.index and hasattr(self.mgr.index, 'frn_paths') else None
        if getattr(vol, 'zone_keys', 'path') == 'frn' and (ix is None or ix.frn_paths(self.letter, []) is None):
            return None                                                     # no MFT index to name the records: do not read
        zm = self._zmap
        if zm and zm['zone_end'] == zone_end and time.time() - zm['t'] < 900:
            return [(p, n, ins) for p, (n, ins) in zm['files'].items() if n and not self.is_hot(p) and not self.is_skipped(p)]
        self.set(state='planning', msg='讀取 MFT：找出熱區裡的檔案…')
        pct = max(5, min(100, int(self.S('hot.usage_pct') or 60)))
        tick = [time.monotonic()]

        def pace(nbytes):                                                   # share the disk like the moves do
            busy = time.monotonic() - tick[0]
            if pct < 100: self.stop_ev.wait(busy * (100 - pct) / pct)
            if self.wait_gate(limit=30): raise InterruptedError('gate')
            tick[0] = time.monotonic()
        try: zf = vol.zone_files(zone_end, self.stop_ev, pace=pace)
        except InterruptedError:
            return []                                                       # _released / stopped: the cycle comes back later
        except Exception as e:
            self.log(f'讀 MFT 失敗，改用逐檔查詢：{e}'); return None
        if self.stopped(): return []
        keys = [k for k, sz, pcs in zf if not isinstance(k, str)]
        names = {}
        for i in range(0, len(keys), 20000):                                # in batches: do not hold the index lock for long
            got = ix.frn_paths(self.letter, keys[i:i + 20000]) if ix else None
            if got is None: return None
            names.update(got)
        mz = self.st.get('mft_zone')
        out = []
        skip_names = ('pagefile.sys', 'hiberfil.sys', 'swapfile.sys', 'dumpstack.log.tmp')
        for k, sz, pcs in zf:
            p = k if isinstance(k, str) else names.get(k)
            if not p or self.is_hot(p) or self.is_skipped(p) or os.path.basename(p).lower() in skip_names: continue
            if '\\$' in p or '\\System Volume Information\\' in p: continue
            ins = inside_pieces(pcs, zone_end, mz)
            n = sum(x[2] for x in ins)
            if n: out.append((p, n, ins))
        self._zmap = {'zone_end': zone_end, 't': time.time(), 'files': {p: (n, ins) for p, n, ins in out}}
        return out

    def zmap_update(self, path, pieces):
        """After moving a file out: what NTFS now says is left of it inside the zone (keeps the cached map true)."""
        zm = self._zmap
        if zm and path in zm['files']: zm['files'][path] = (sum(x[2] for x in pieces), pieces)

    def cold_in_zone(self, vol, zone_end, need_cl):
        """Cold files with clusters inside the zone. [(path, clusters_inside, pieces)]"""
        m = self.cold_from_map(vol, zone_end)
        if m is not None: return m
        self.set(state='planning', msg='找出佔用熱區的冷資料…')
        files = self.mgr.index.all_files(self.letter, min_size=1024 * 1024) if self.mgr.index else None
        if files is None:
            files = []
            root = self.letter + '\\' if IS_WIN else self.letter
            for r, ds, fs, _links in W.walk(root):
                if self.stopped(): return []
                ds[:] = [d for d in ds if d not in ('$Recycle.Bin', 'System Volume Information')]
                for f in fs:
                    q = os.path.join(r, f)
                    try:
                        sz = os.path.getsize(q)
                        if sz >= 1024 * 1024: files.append((q, sz))
                    except OSError: pass
        files.sort(key=lambda f: -f[1])
        out = []; got = 0; t_last = time.time()
        for n, (p, sz) in enumerate(files):
            if self.stopped(): return out
            if not p or self.is_hot(p) or self.is_skipped(p): continue
            if os.path.basename(p).lower() in ('pagefile.sys', 'hiberfil.sys', 'swapfile.sys', 'dumpstack.log.tmp'): continue
            try:
                if getattr(os.stat(p), 'st_file_attributes', 0) & (0x4 | 0x800 | 0x200 | 0x400): continue   # system / compressed / sparse / reparse
            except OSError:
                pass                                                        # opening it through the volume decides
            try:
                with vol.open_file(p) as fh: ext = fh.extents()
            except Exception:
                continue
            pcs = inside_pieces(ext, zone_end, self.st.get('mft_zone'))
            k = sum(x[2] for x in pcs)
            if k: out.append((p, k, pcs)); got += k
            if got >= need_cl * 3 and n > 200: break                          # a choice of files -> contiguous space
            if time.time() - t_last > 0.5:
                self.set(msg=f'找出佔用熱區的冷資料… {n + 1:,}/{len(files):,}'); t_last = time.time()
        out.sort(key=lambda x: -x[1])
        return out

    def pick_block(self, cold, free_runs_, need_cl, min_piece, gap_free=None):
        """Which cold files to move so the freed space is ONE contiguous block (not scattered holes):
        free runs + movable cold pieces are merged into blocks; the smallest block that reaches need_cl wins (else
        the biggest). Returns the cold files of that block in disk order."""
        iv = [(l, l + n, None) for l, n in free_runs_]
        for p, k, pcs in cold:
            for v, l, n in pcs: iv.append((l, l + n, p))
        iv.sort(key=lambda x: (x[0], x[1], x[2] is not None))             # a stale map can repeat a free run's bounds
        blocks = []; cur = None
        for a, b, p in iv:
            if cur and (a <= cur['end'] or (gap_free and gap_free(cur['end'], a))):   # touching, or only free clusters between
                cur['end'] = max(cur['end'], b)
                if p: cur['files'].append((a, p)); cur['cold'] += b - a
            else:
                cur = {'start': a, 'end': b, 'files': [(a, p)] if p else [], 'cold': (b - a) if p else 0}; blocks.append(cur)
        blocks = [b for b in blocks if b['files'] and b['end'] - b['start'] >= min_piece]
        if not blocks: return sorted(cold, key=lambda c: -c[1])           # biggest first: fewest moves
        big = [b for b in blocks if b['end'] - b['start'] >= need_cl]
        best = min(big, key=lambda b: b['cold']) if big else max(blocks, key=lambda b: b['end'] - b['start'])
        # start next to the block's biggest free run, so the space freed grows that run instead of opening a new hole
        frees = [(l, l + n) for l, n in free_runs_ if l >= best['start'] and l + n <= best['end']]
        anchor = max(frees, key=lambda f: f[1] - f[0]) if frees else (best['start'], best['start'])
        dist = lambda a: 0 if anchor[0] <= a <= anchor[1] else min(abs(a - anchor[0]), abs(a - anchor[1]))
        order = []; seen = set()
        for a, p in sorted(best['files'], key=lambda x: dist(x[0])):
            if p not in seen: seen.add(p); order.append(p)
        by = {c[0]: c for c in cold}
        lo, hi = best['start'], best['end']
        first = []
        for p in order:                                                     # only the parts inside the chosen block
            pcs = [x for x in by[p][2] if x[1] < hi and x[1] + x[2] > lo]
            if pcs: first.append((p, sum(x[2] for x in pcs), pcs))
        rest = sorted([c for c in cold if c[0] not in seen], key=lambda c: min((x[1] for x in c[2]), default=0))   # disk order: frees space next to each other
        return first + rest

    # --------------------------------------------------------------------------- moving
    def _map_move(self, src_lcn, dst_lcn, n, kind):
        """Keep the cluster map's hot overlay current while moving (it is rebuilt at every plan)."""
        hc = self.hot_cells
        if not hc or kind != 'hot': return
        cells, per = hc['cells'], hc['cell_cl']
        a = min(len(cells) - 1, src_lcn // per); b = min(len(cells) - 1, dst_lcn // per)
        cells[a] = max(0, cells[a] - n); cells[b] += n

    def target_in_use(self, vol, lcn, n):
        """After a refused move: is the target really taken (-> avoid it for a while) or was the source the problem?"""
        try:
            first, bm = vol.bitmap(lcn, n)
            for c in range(lcn, lcn + n):
                k = c - first
                if 0 <= k // 8 < len(bm) and (bm[k // 8] >> (k % 8)) & 1: return True
            return False
        except Exception:
            return True

    def move_pieces(self, vol, path, pieces, alloc: Allocator, kind, limit=None):
        """Move [(vcn, lcn, n)] of one file into clusters from alloc. Returns clusters moved.
        A move NTFS refuses because of the SOURCE (paging file, compressed / sparse range, file changed) skips the
        file for a while; a refused TARGET is avoided for 60 s and another target is tried."""
        cl = self.st['cluster'] or 4096
        chunk_cl = max(16, int(self.S('hot.chunk_mb') or 32) * 1024 * 1024 // cl)
        align = max(1, 16384 // cl); moved = 0
        try: fh = vol.open_file(path)
        except Exception as e:
            self.skip(path, f'無法開啟：{e}'); return 0
        try:
            for vcn, lcn, n in pieces:
                done = 0; nxt = None
                while done < n:
                    if self.stopped(): return moved
                    if limit is not None and moved >= limit: return moved     # freed enough: do not move a whole 300 GB file
                    if self.wait_gate(limit=30): return moved                 # closed for long: let go of the handles
                    if self.mgr.S.get('hot.dry_run'): return moved
                    k = min(chunk_cl, n - done)
                    if limit is not None: k = min(k, max(16, limit - moved))
                    targets = alloc.take(k, lcn + done, align, rest=(n - done) if limit is None else min(n - done, max(16, limit - moved)), after=nxt)
                    if not targets:
                        return moved                                       # no space left: caller re-plans
                    for i, (tl, tk) in enumerate(targets):
                        src = lcn + done
                        t0 = time.monotonic()
                        ok, e = fh.move(vcn + done, tl, tk)
                        busy = time.monotonic() - t0; self.last_move_end = time.time()
                        tries = 0; free_refusals = 0; suspects = []
                        while not ok and tries < 4:
                            tries += 1
                            if self.target_in_use(vol, tl, tk):              # really taken (someone wrote there): another target
                                self.bad.append((tl, tk, time.time() + 60)); alloc.drop(tl, tk)
                                t2 = alloc.take_exact(tk, src, align)
                                if t2 is None: break
                                tl = t2[0]
                            else:
                                free_refusals += 1
                                if free_refusals == 1:                     # looks free: maybe just freed and NTFS has not
                                    if self.stop_ev.wait(0.01 if self.mgr.volume_factory else 3): break   # checkpointed yet
                                elif free_refusals == 2:                   # still refused: reserved area -> another target
                                    bad = (tl, tk, time.time() + 60); self.bad.append(bad); suspects.append(bad); alloc.drop(tl, tk)
                                    t2 = alloc.take_exact(tk, src, align)
                                    if t2 is None: break
                                    tl = t2[0]
                                else:
                                    break                                  # a different free target refused too: the source
                            t0 = time.monotonic(); ok, e = fh.move(vcn + done, tl, tk); busy = time.monotonic() - t0; self.last_move_end = time.time()
                        if not ok:
                            back = list(targets[i + 1:])
                            if free_refusals >= 3:                         # the source was to blame: the targets were fine
                                for b_ in suspects:
                                    if b_ in self.bad: self.bad.remove(b_)
                                    back.append((b_[0], b_[1]))
                            if not any(b_[0] == tl for b_ in self.bad) and not self.target_in_use(vol, tl, tk):
                                back.append((tl, tk))                      # the target we were holding: still free
                            for l2, k2 in back: alloc.give_back(l2, k2)
                            self.skip(path, f'NTFS 不允許搬移（錯誤 {e}），之後再試')
                            return moved
                        self._map_move(src, tl, tk, kind)
                        done += tk; moved += tk; nxt = tl + tk
                        b = tk * cl
                        self.mgr.meter.add(self.lane(), 2 * b)              # read + write on the same disk
                        if kind == 'hot':
                            self.st['moved_bytes'] += b; self.st['moved_round'] = self.st.get('moved_round', 0) + b
                            self.st['zone_free'] = alloc.total() * cl
                        else:
                            self.st['evicted_bytes'] += b; self.st['evicted_round'] = self.st.get('evicted_round', 0) + b
                        self.pace(busy, b)
        finally:
            fh.close()
        return moved

    def skip(self, path, msg, hours=6):
        """Leave a file alone for a while (it is retried after `hours` or when it changes)."""
        try: st = os.stat(path); sig = (st.st_size, int(st.st_mtime))
        except OSError: sig = None
        self.skipped_files[(path.lower() if IS_WIN else path)] = (time.time() + hours * 3600, sig)
        self.err(path, msg)

    def is_skipped(self, path):
        k = path.lower() if IS_WIN else path
        v = self.skipped_files.get(k)
        if not v: return False
        until, sig = v
        try: st = os.stat(path); now_sig = (st.st_size, int(st.st_mtime))
        except OSError: now_sig = None
        if time.time() > until or now_sig != sig:
            self.skipped_files.pop(k, None); return False
        return True

    # --------------------------------------------------------------------------- main loop
    def run(self):
        W.thread_background(True)
        while not self.stopped():
            try:
                if not [h for h in self.mgr.folders() if drive_of(h['path']) == self.letter]:
                    self.set(state='idle', msg='這個磁碟沒有熱資料夾', rate=0.0)
                    if self.nap(10): break
                    continue
                if self.wait_gate(): break
                self._released = False
                nap = self.cycle()
                if nap and self.nap(nap): break
            except Exception as e:
                self.mgr.log.exc('hot', self.letter)
                self.set(state='error', msg=str(e), rate=0.0)
                if self.nap(60): break

    def cycle(self):
        """One round. Returns how long to rest afterwards (the volume handle is closed by then, so an external disk
        can be removed and chkdsk can lock it while we wait)."""
        self._released = False
        try:
            vol = self.mgr.open_volume(self.letter)
        except Exception as e:
            self.set(state='unsupported', msg=str(e), rate=0.0)
            return 60
        try:
            res = self.plan(vol)
            if res is None: return 0
            todo, info, zone_end = res
            cl = info['cluster']
            dry = bool(self.S('hot.dry_run'))
            alloc = self.zone_free(vol, info, zone_end)
            free_cl = alloc.total(); need_cl = sum(t[1] for t in todo)
            self.set(zone_free=free_cl * cl, evict_need=max(0, need_cl - alloc.usable(need_cl)) * cl, moved_round=0, evicted_round=0)
            if dry:
                est = self.estimate(need_cl * cl, max(0, need_cl - free_cl) * cl); basis = self.move_speed()[1]
                self.set(state='dry', msg='試跑：只規劃、不搬', dry={'move': need_cl * cl, 'evict': max(0, need_cl - free_cl) * cl,
                                                                   'free': free_cl * cl, 'files': len(todo), 'hours': est, 'basis': basis, 't': time.time()})
                self.log(f'試跑：要搬 {fmt_size(need_cl * cl)}（{len(todo)} 個檔案），熱區可用 {fmt_size(free_cl * cl)}，需先騰出 {fmt_size(max(0, need_cl - free_cl) * cl)}，約 {est:.1f} 小時')
                return 300
            if not todo and not self.priority:
                self._zmap = None                                           # nothing to do: free the cached zone map
                if self.st['state'] != 'done': self.log(f'全部熱資料都在外圈（{fmt_size(self.st["hot_bytes"])}）')
                self.set(state='done', msg='全部熱資料都在外圈了', rate=0.0, eta=0, cur='', done_t=time.time())
                # nothing to do: look again in 30 min (new files from this program wake us at once via notify())
                return 1 if self.priority else 1800
            if not self._light: self.log(f'開始：{len(todo)} 個檔案要搬進外圈，共 {fmt_size(need_cl * cl)}；熱區可用 {fmt_size(free_cl * cl)}')
            replan_at = time.time() + 900
            remaining = need_cl; progress = 0

            def work():                                                     # files that just arrived go first, without
                i = 0                                                       # throwing away this plan (it can take minutes)
                while True:
                    while self.priority:
                        p = self.priority.pop(0)
                        if drive_of(p) != self.letter: continue
                        if os.path.isdir(p):                                # a whole folder was copied in: its files
                            for root, _ds, fs, _links in W.walk(p):
                                for f in fs: yield os.path.join(root, f), 0, True
                        else:
                            yield p, 0, True
                    if i >= len(todo): return
                    yield todo[i]; i += 1
            for path, out_cl, _p in work():
                if self.stopped() or time.time() > replan_at: return 0
                if not self.is_hot(path): continue                           # its folder is no longer hot
                if self.wait_gate(limit=30): return 0
                try:
                    with vol.open_file(path) as fh: ext = fh.extents()
                except Exception as e:
                    self.err(path, str(e)); continue
                _i, outside = split_extents(ext, zone_end)
                k = sum(x[2] for x in outside)
                if not k: continue
                if alloc.usable(k) < k:
                    want = min(max(k, remaining), k + 64 * GB // cl) - alloc.usable(k)    # enough for what is left (max 64 GB per round)
                    got = self.evict(vol, info, zone_end, want + max(16, want // 100))
                    if self._released or self.stopped(): return 0
                    alloc = self.zone_free(vol, info, zone_end)
                    self.st['zone_free'] = alloc.total() * cl
                    if alloc.usable(k) < k and got == 0 and self._zmap:        # the cached zone map may be stale: read it again
                        self._zmap = None; got = self.evict(vol, info, zone_end, want + max(16, want // 100))
                        if self._released or self.stopped(): return 0
                        alloc = self.zone_free(vol, info, zone_end); self.st['zone_free'] = alloc.total() * cl
                    if alloc.usable(k) < k and got == 0:
                        self.set(state='full', msg='熱區已滿，冷資料也搬不出去（可加大熱區或清出空間）', rate=0.0)
                        self.log('熱區已滿，無法再騰出空間', 'warn'); return 600
                self.set(state='moving', cur=path, msg='')
                m = self.move_pieces(vol, path, outside, alloc, 'hot')
                progress += m
                remaining -= out_cl
                self.st['in_bytes'] += m * cl
                if self._released: return 0                                  # gate closed for long: handles closed, back later
            self.set(cur='')
            if self._light:                                                 # the new files are in place: still all done
                self.set(state='done', msg='全部熱資料都在外圈了', rate=0.0, eta=0, done_t=time.time())
                return 1 if self.priority else 1800
            if progress == 0 and not self.stopped():                        # nothing could be moved: back off, do not spin
                self.idle_naps = min(self.idle_naps + 1, 6)
                self.set(state='waiting', msg='這一輪沒有可以搬的部分，稍後再試', rate=0.0)
                return 30 * 2 ** self.idle_naps
            self.idle_naps = 0
            return 0
        finally:
            try: vol.close()
            except Exception: pass

    def evict(self, vol, info, zone_end, need_cl):
        """Move cold data out of the zone until need_cl clusters are free. Returns clusters freed."""
        cold = self.cold_in_zone(vol, zone_end, need_cl)
        if not cold: return 0
        self.st['zone_free'] = None
        targets = self.cold_targets(vol, info, zone_end)
        freed = 0
        self.log(f'騰出熱區空間：需要 {fmt_size(need_cl * info["cluster"])}，候選冷檔案 {len(cold)} 個')
        za = self.zone_free(vol, info, zone_end)
        first, bm = vol.bitmap(0, zone_end)
        mz = info.get('mft_zone') or (0, 0)
        gaps = free_runs(first, bm, 0, zone_end, min_len=1)
        if mz[1] > mz[0]: gaps = cut(gaps, mz[0], mz[1])

        def gap_free(a, b):                                                 # small files with tiny free gaps between them
            if b - a > 64 or a < 64 or (mz[0] < b and a < mz[1]): return False   # still form one block
            return all(not (bm[(c - first) >> 3] >> ((c - first) & 7)) & 1 for c in range(a, b) if 0 <= (c - first) >> 3 < len(bm))
        order = self.pick_block(cold, cut(gaps, 0, 64), need_cl, za.min_piece, gap_free)
        for pick in order:
            if freed >= need_cl or self.stopped() or self._released: break
            rest = need_cl - freed; p = pick[0]
            try:
                with vol.open_file(p) as fh: ext = fh.extents()             # NTFS's current answer, not the map
            except Exception:
                continue
            pieces = inside_pieces(ext, zone_end, self.st.get('mft_zone'))
            want = pick[2] if len(pick) > 2 else None
            if want:                                                        # keep to the chosen block where possible
                ranges = [(x[1], x[1] + x[2]) for x in want]
                sel = [x for x in pieces if any(x[1] < b_ and x[1] + x[2] > a_ for a_, b_ in ranges)]
                pieces = sel or pieces
            if not pieces: continue
            self.set(state='evicting', cur=p, msg='把冷資料移到內圈，騰出熱區空間')
            freed += self.move_pieces(vol, p, pieces, targets, 'cold', limit=rest)
            try:
                with vol.open_file(p) as fh: self.zmap_update(p, inside_pieces(fh.extents(), zone_end, self.st.get('mft_zone')))
            except Exception:
                self.zmap_update(p, [])
            if not targets.total(): break
        return freed

    def move_speed(self):
        """(bytes/s, basis): an in-place move reads at the inner speed and writes at the outer speed on the same disk;
        from the last 📈 speed test of this disk when there is one, else a typical hard disk (60 MB/s)."""
        try:
            import hz_bench as BN
            b = BN.last_results().get(self.letter)
            if b and b.get('outer') and b.get('inner'):
                mbps = 0.8 / (1 / b['outer'] + 1 / b['inner'])                  # both halves on one disk, some seeking
                return mbps * 1024 * 1024, f'依這顆硬碟的測速，原地搬移約 {mbps:.0f} MB/s'
        except Exception:
            pass
        return 60 * 1024 * 1024, '一般硬碟原地搬移約 60 MB/s'

    def estimate(self, move_b, evict_b):
        pct = max(5, min(100, int(self.S('hot.usage_pct') or 60))) / 100.0
        speed, _basis = self.move_speed()
        return (move_b + evict_b) / speed / pct / 3600.0


# ============================================================================================ manager
class HotManager:
    def __init__(self, settings, log, drives, index=None, counters=None, meter=None, queue_busy=lambda lane: False):
        self.S = settings; self.log = log; self.drives = drives; self.index = index
        self.counters = counters; self.meter = meter; self.queue_busy_fn = queue_busy
        self.rel: dict[str, Relocator] = {}
        self.paused = False
        self.lock = threading.RLock()
        self.th = None; self.stop_ev = threading.Event()
        self.volume_factory = None                         # tests plug a simulated volume here

    def queue_busy(self, lane):
        if not self.S.get('hot.yield_queue'): return False
        try: return self.queue_busy_fn(lane)
        except Exception: return False

    # --------------------------------------------------------------------------- folders
    def folders(self):
        f = self.S.get('hot.folders') or []
        return sorted([x for x in f if isinstance(x, dict) and x.get('path')], key=lambda x: x.get('order', 0))

    def is_hot(self, path):
        return any(is_under(path, h['path']) for h in self.folders())

    def add_folder(self, path):
        path = norm(path)
        if not os.path.isdir(path): raise ValueError('不是資料夾')
        f = self.folders()
        if any(is_under(path, h['path']) for h in f): raise ValueError('已經在熱資料夾裡面')
        f = [h for h in f if not is_under(h['path'], path)]                  # a parent replaces its children
        f.append({'path': path, 'order': len(f), 'added': time.time()})
        self.S.set('hot.folders', f)
        self.log.info('hot', f'標記熱處理：{path}')
        self.ensure(); self.poke(drive_of(path))
        return f

    def remove_folder(self, path):
        f = [h for h in self.folders() if not (norm(h['path']).lower() == norm(path).lower() if IS_WIN else norm(h['path']) == norm(path))]
        self.S.set('hot.folders', f); self.log.info('hot', f'取消熱處理：{path}')
        return f

    def reorder(self, paths):
        f = {norm(h['path']): h for h in self.folders()}
        out = []
        for i, p in enumerate(paths):
            h = f.pop(norm(p), None)
            if h: h['order'] = i; out.append(h)
        for h in f.values(): h['order'] = len(out); out.append(h)
        self.S.set('hot.folders', out)

    # --------------------------------------------------------------------------- volumes
    def open_volume(self, letter):
        if self.volume_factory: return self.volume_factory(letter)
        import hz_ntfs as N
        if not IS_WIN: raise N.NtfsError('熱區搬移只支援 Windows NTFS')
        v = self.drives.get(letter)
        if (v.get('fs') or '').upper() != 'NTFS': raise N.NtfsError(f'{letter} 不是 NTFS（{v.get("fs") or "?"}），無法搬移磁區')
        if not W.is_admin(): raise N.NtfsError('需要以系統管理員身分執行背景引擎')
        return N.NtfsVolume(letter)

    def ensure(self):
        with self.lock:
            letters = {drive_of(h['path']) for h in self.folders()}
            for L in letters:
                r = self.rel.get(L)
                if r is None or not r.is_alive():
                    r = Relocator(self, L)
                    old = getattr(self, '_adopt_st', {}).get(L)
                    if old:
                        for k in ('moved_bytes', 'evicted_bytes', 'errors', 'skipped', 'session_t'): r.st[k] = old.get(k, r.st[k])
                    self.rel[L] = r; r.start()

    def poke(self, letter=None):
        for L, r in list(self.rel.items()):
            if letter is None or L == letter: r.wake.set()

    def notify(self, paths):
        """Files that just landed in a hot folder: move them first."""
        hits = {}
        for p in paths:
            if self.is_hot(p): hits.setdefault(drive_of(p), []).append(p)
        if not hits: return
        self.ensure()
        for L, ps in hits.items():
            r = self.rel.get(L)
            if r:
                r.priority.extend(ps); r.wake.set()

    def set_paused(self, on):
        self.paused = bool(on); self.poke()

    def start(self):
        self.ensure()
        self.th = threading.Thread(target=self._loop, name='HZ-HotMgr', daemon=True); self.th.start()
        return self

    def _loop(self):
        while not self.stop_ev.wait(15):
            try: self.ensure()
            except Exception: self.log.exc('hot', 'ensure')

    def stop(self, timeout=10):
        self.stop_ev.set()
        for r in self.rel.values(): r.stop_ev.set(); r.wake.set()
        t_end = time.time() + timeout
        for r in self.rel.values(): r.join(max(0.1, t_end - time.time()))

    def export_state(self):
        return {'paused': self.paused, 'st': {L: dict(r.st) for L, r in self.rel.items()}}

    def adopt(self, st):
        st = st or {}
        self.paused = bool(st.get('paused')); self._adopt_st = st.get('st') or {}

    # --------------------------------------------------------------------------- views
    # --------------------------------------------------------------------------- history (progress over days)
    def history_add(self, letter, snap):
        """One point per plan, at most one per 30 min, 120 days, per volume: how much hot data is in the outer zone."""
        with self.lock:
            h = read_json(HISTORY_FILE, {}) or {}
            pts = h.get(letter, [])
            snap = dict(snap, t=int(time.time()))
            if pts and snap['t'] - pts[-1]['t'] < 1800: pts[-1] = snap
            else: pts.append(snap)
            h[letter] = [x for x in pts if snap['t'] - x['t'] < 120 * 86400][-6000:]
            try: atomic_write_json(HISTORY_FILE, h, indent=None)
            except Exception: pass

    def history(self, letter):
        return (read_json(HISTORY_FILE, {}) or {}).get(letter, [])

    def status(self):
        vols = []
        letters = sorted({drive_of(h['path']) for h in self.folders()} | set(self.rel))
        for L in letters:
            r = self.rel.get(L)
            st = dict(r.st) if r else {'letter': L, 'state': 'idle', 'msg': ''}
            v = self.drives.get(L)
            st.update(media=v.get('media', '?'), smr=v.get('smr', False), fs=v.get('fs', ''), total=v.get('total', 0), free=v.get('free', 0),
                      folders=[h for h in self.folders() if drive_of(h['path']) == L])
            setting = (self.S.get('hot.zone_gb') or {}).get(L, 0)
            st['zone_setting'] = setting
            st['pct_in'] = round(100.0 * st.get('in_bytes', 0) / st['hot_bytes'], 1) if st.get('hot_bytes') else None
            vols.append(st)
        return {'paused': self.paused, 'admin': W.is_admin(), 'vols': vols, 'folders': self.folders()}

    def cluster_map(self, letter, cells=1600):
        """Usage of the whole volume in `cells` blocks + where the hot data is (from the last plan)."""
        vol = self.open_volume(letter)
        try:
            info = vol.info(); tot = info['total_clusters']
            per = max(8, (tot // cells + 7) // 8 * 8)
            used = []
            lcn = 0; step = per * max(1, (32 * 1024 * 1024 * 8) // per)
            while lcn < tot:
                n = min(step, tot - lcn)
                first, bm = vol.bitmap(lcn, n)
                off = (lcn - first) // 8
                for c in range(0, n, per):
                    a = off + c // 8; b = min(len(bm), a + per // 8)
                    seg = bm[a:b]
                    used.append(round(int.from_bytes(seg, 'little').bit_count() / max(1, len(seg) * 8), 3) if seg else 0)
                lcn += n
            r = self.rel.get(letter)
            hot = None
            if r and r.hot_cells:
                hc = r.hot_cells; scale = per / hc['cell_cl']
                hot = [0.0] * len(used)
                for i, k in enumerate(hc['cells']):
                    if not k: continue
                    a = int(i * hc['cell_cl'] // per); b = int(((i + 1) * hc['cell_cl'] - 1) // per)
                    span = max(1, b - a + 1)
                    for c in range(a, min(len(hot), b + 1)): hot[c] += k / span / per
                hot = [round(min(1.0, x), 3) for x in hot]
            ze = r.st.get('zone_end', 0) if r else 0
            mz = info.get('mft_zone') or (0, 0)
            return {'cells': used, 'per': per, 'cluster': info['cluster'], 'total': tot, 'zone_end': ze, 'hot': hot, 'mft_zone': list(mz)}
        finally:
            vol.close()

    def file_layout(self, path):
        """Where a file sits: share inside the hot zone, number of fragments, position on the disk (0 % = outer edge)."""
        L = drive_of(path)
        vol = self.open_volume(L)
        try:
            info = vol.info(); tot = info['total_clusters']
            r = self.rel.get(L)
            ze = (r.st.get('zone_end') if r else 0) or 0
            if not ze:
                gb = float((self.S.get('hot.zone_gb') or {}).get(L, 0) or 0)
                ze = int(gb * GB // info['cluster']) if gb > 0 else 0
            with vol.open_file(path) as fh: ext = fh.extents()
            real = [e for e in ext if e[1] >= 0 and e[2] > 0]
            n = sum(e[2] for e in real)
            inside = split_extents(ext, ze)[0] if ze else 0
            return {'clusters': n, 'fragments': len(real), 'zone_gb': round(ze * info['cluster'] / GB, 1) if ze else 0,
                    'inside_pct': round(100.0 * inside / n, 1) if n and ze else None,
                    'start_pct': round(100.0 * real[0][1] / tot, 2) if real else None,
                    'resident': not real}
        finally:
            vol.close()

    def dry_run(self, letter):
        """Plan once without moving (button 試跑)."""
        old = self.S.get('hot.dry_run')
        self.S.set('hot.dry_run', True)
        self.ensure(); self.poke(letter)
        return old


# ============================================================================================ simulated volume (tests / demo)
class SimFile:
    def __init__(self, vol, path):
        self.vol = vol; self.path = path
        if path not in vol.files: raise FileNotFoundError(path)

    def extents(self): return [tuple(x) for x in self.vol.files[self.path]]
    def close(self): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass

    def move(self, vcn, lcn, n):
        return self.vol.move(self.path, vcn, lcn, n)


class SimVolume:
    """In-memory NTFS look-alike: bitmap + files made of extents. move() checks everything FSCTL_MOVE_FILE would."""
    def __init__(self, total_clusters, cluster=4096, mft_zone=(0, 0), speed_bps=0):
        self.total = total_clusters; self.cluster = cluster; self.mft_zone = mft_zone
        self.bm = bytearray((total_clusters + 7) // 8)
        self.files = {}; self.moves = 0; self.speed = speed_bps
        self.reserved = set()
        self.unmovable = set()                      # paths NTFS refuses to move (like pagefile.sys)

    def _set(self, lcn, n, v):
        for c in range(lcn, lcn + n):
            if v: self.bm[c >> 3] |= 1 << (c & 7)
            else: self.bm[c >> 3] &= ~(1 << (c & 7))

    def _free(self, lcn, n):
        return all(not (self.bm[c >> 3] >> (c & 7)) & 1 for c in range(lcn, lcn + n))

    def add_file(self, path, runs):
        vcn = 0; ext = []
        for lcn, n in runs:
            assert self._free(lcn, n), (path, lcn, n)
            self._set(lcn, n, 1); ext.append([vcn, lcn, n]); vcn += n
        self.files[path] = ext

    map_ok = False                                   # tests switch the MFT zone map on / off

    def zone_files(self, zone_end, stop=None, pace=None):
        if pace: pace(4096)
        if not self.map_ok: raise NotImplementedError('no map')
        return [(p, sum(e[2] for e in ext) * self.cluster, [tuple(e) for e in ext if e[1] < zone_end]) for p, ext in self.files.items()
                if any(e[1] < zone_end for e in ext)]

    def info(self):
        return {'cluster': self.cluster, 'total_clusters': self.total, 'mft_zone': self.mft_zone, 'free_clusters': 0}

    def bitmap(self, lcn0, count):
        a = lcn0 // 8 * 8
        return a, bytes(self.bm[a // 8:(lcn0 + count + 7) // 8])

    def open_file(self, path): return SimFile(self, path)
    def close(self): pass

    def move(self, path, vcn, lcn, n):
        if lcn < 0 or lcn + n > self.total: return False, 87
        if self.mft_zone[0] <= lcn < self.mft_zone[1] or self.mft_zone[0] < lcn + n <= self.mft_zone[1]: return False, 5
        if path in self.unmovable: return False, 5
        if any(lcn <= r < lcn + n for r in self.reserved): return False, 5
        if not self._free(lcn, n): return False, 5
        ext = self.files[path]
        # collect the source clusters of vcn..vcn+n
        src = []; left = n; v = vcn
        for e in ext:
            ev, el, en = e
            if ev <= v < ev + en and left > 0:
                k = min(left, ev + en - v)
                if el < 0: return False, 87
                src.append((el + (v - ev), k)); v += k; left -= k
        if left: return False, 87
        for s, k in src: self._set(s, k, 0)
        self._set(lcn, n, 1)
        # rebuild extents: split at vcn / vcn+n and replace the middle
        new = []; v = 0
        for ev, el, en in ext:
            for a, b in ((ev, min(ev + en, vcn)), (max(ev, vcn + n), ev + en)):
                if b > a: new.append([a, el + (a - ev) if el >= 0 else -1, b - a])
        new.append([vcn, lcn, n]); new.sort()
        merged = []
        for e in new:
            if merged and merged[-1][0] + merged[-1][2] == e[0] and merged[-1][1] >= 0 and merged[-1][1] + merged[-1][2] == e[1]:
                merged[-1][2] += e[2]
            else: merged.append(e)
        self.files[path] = merged
        self.moves += 1
        if self.speed: time.sleep(n * self.cluster * 2 / self.speed)
        return True, 0

    def used_by(self):
        owner = {}
        for p, ext in self.files.items():
            for v, l, n in ext:
                for c in range(l, l + n):
                    assert c not in owner, f'overlap at {c}: {p} / {owner[c]}'
                    owner[c] = p
        return owner

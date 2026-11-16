"""HotZone FM — transfer queue (Copy Handler / FastCopy style).

  * Lanes = physical disks. K: and L: on the same HDD are one lane. Each lane runs at most N jobs at the same time
    (HDD 1 by default - one copy at a time is the fastest way on a hard disk), plus a total limit for all lanes.
  * Usage cap per disk (FastCopy style %): after every chunk the worker rests so that the share of time the disk
    spends on the queue stays at the cap. Writes go straight to the disk (write-through) so the measured time is the
    real disk time - Windows cannot first swallow gigabytes into RAM and then flood the disk.
  * Optional MB/s cap, optional "give way" (pause while other programs use the disk).
  * Jobs into a hot folder jump the queue. Same-drive moves are a rename: instant, the file is usable at once.
  * Partial files are kept as  name.hzpart  ->  pause / resume / restart / hot update continue where they stopped.
  * Conflicts: ask / skip / overwrite / newer / rename (ask = only this job waits, the others go on).
"""
from __future__ import annotations

import hashlib
import re
import json
import os
import shutil
import threading
import time
import uuid
from collections import deque

from hz_common import QUEUE_DIR, IS_WIN, norm, is_under, same_path, unique_name, atomic_write_json, read_json, fmt_size
import hz_win as W

PART = '.hzpart'
ACTIVE = ('scanning', 'running')
FINAL = ('done', 'error', 'canceled')
ST_PENDING, ST_DONE, ST_SKIP, ST_ERR, ST_PARTIAL = '0', '1', '2', '3', '4'


class States:
    """One character per item, like the old string, but changing one is O(1) (a 1,000,000-item job rebuilt a
    1 MB string twice per file). Reads like a str: s[k], len(s), iteration, bool. Saved as a plain string."""
    __slots__ = ('b',)
    def __init__(self, s=''): self.b = bytearray(str(s).encode('ascii'))
    def __getitem__(self, k): return self.b[k].decode() if isinstance(k, slice) else chr(self.b[k])
    def __len__(self): return len(self.b)
    def __iter__(self): return iter(self.b.decode())
    def __str__(self): return self.b.decode()
    def __eq__(self, o): return str(self) == str(o)
    def set(self, k, c): self.b[k] = ord(c)
    def count(self, c): return self.b.count(c.encode())


class Interrupted(Exception):
    pass


def _birth(st):
    if not IS_WIN: return None
    return getattr(st, 'st_birthtime', None) or st.st_ctime


# ============================================================================================ pacing
class IoMeter:
    """Bytes per lane over the last seconds (queue + hot relocation), for 'others are using this disk' checks."""
    def __init__(self):
        self.lock = threading.Lock(); self.ev = {}

    def add(self, lane, nbytes):
        now = time.monotonic()
        with self.lock:
            q = self.ev.setdefault(lane, deque())
            q.append((now, nbytes))
            while q and now - q[0][0] > 4: q.popleft()

    def rate(self, lane, window=3.0):
        now = time.monotonic()
        with self.lock:
            q = self.ev.get(lane)
            if not q: return 0.0
            return sum(n for t, n in q if now - t <= window) / window


class Gates:
    """Shared pacing per lane: duty cycle (usage %) + optional MB/s cap. Thread safe."""
    def __init__(self):
        self.lock = threading.Lock(); self.next_t = {}

    def debt(self, lane, busy, nbytes, pct, mbps):
        pct = max(5, min(100, int(pct or 100)))
        d = busy * (100 - pct) / pct if pct < 100 else 0.0
        if mbps and mbps > 0:
            d = max(d, nbytes / (mbps * 1024 * 1024) - busy)
        with self.lock:
            now = time.monotonic()
            t = max(self.next_t.get(lane, 0.0), now) + max(0.0, d)
            self.next_t[lane] = t
            return t

    def wait_until(self, t, stop_check):
        while True:
            left = t - time.monotonic()
            if left <= 0.005: return                 # tiny debts add up in next_t and are slept off together
            stop_check()                             #  (a sleep per small file overshot: 80 % ran at 61 %)
            time.sleep(min(0.25, left))


# ============================================================================================ manager
def _absolute(p):
    p = str(p or '').strip()
    if IS_WIN: return bool(re.match(r'^(?:[A-Za-z]:[\\/]|[\\/]{2}[^\\/?.]+[\\/][^\\/]+)', p))
    return p.startswith('/')


def check_expect(paths, expect):
    """The page sends what it showed for each item: [size, mtime] (size -1 = folder). Anything that is no longer
    that file (renamed / replaced / edited by another program since the list was drawn) is refused, so an old row
    can never delete / rename a different file that took its name. Raises ValueError naming them."""
    if not expect: return
    key = (lambda x: x.lower()) if IS_WIN else (lambda x: x)
    exp = {key(norm(k)): v for k, v in expect.items() if isinstance(v, (list, tuple)) and len(v) >= 2}
    bad = []
    for p in paths:
        e = exp.get(key(norm(p)))
        if e is None: continue
        try: st = os.lstat(W.lp(p))
        except OSError: bad.append((p, '已經不在了')); continue
        isdir = os.path.isdir(W.lp(p)) and not W.is_link_like(p)
        if (e[0] is not None and float(e[0]) < 0) != isdir: bad.append((p, '已經換成別的項目')); continue
        if not isdir and (st.st_size != int(e[0]) or (e[1] and abs(st.st_mtime - float(e[1])) > 2)):
            bad.append((p, '內容在你看到之後被改過或換掉了'))
    if bad:
        names = '、'.join(f'{os.path.basename(p.rstrip(chr(92) + "/"))}（{why}）' for p, why in bad[:5]) + (f' 等 {len(bad)} 個' if len(bad) > 5 else '')
        raise ValueError(f'為了安全沒有執行：{names}。清單可能是舊的，請重新整理後再操作一次。')


def _copy_name(p):
    """Copy into the folder it is already in: 'a.jpg' -> 'a - 複製.jpg', 'a - 複製 (2).jpg', … (like Windows)."""
    d, b = os.path.split(p.rstrip('\\/'))
    stem, ext = (b, '') if os.path.isdir(W.lp(p)) else os.path.splitext(b)
    for i in range(1, 10000):
        c = os.path.join(d, f'{stem} - 複製{"" if i == 1 else f" ({i})"}{ext}')
        if not os.path.lexists(W.lp(c)): return c
    raise IOError('找不到可用的名稱')


class TransferManager:
    def __init__(self, settings, log, drives, counters=None, meter=None):
        self.S = settings; self.log = log; self.drives = drives; self.counters = counters
        self.meter = meter or IoMeter(); self.gates = Gates()
        self.jobs: dict[str, dict] = {}
        self.items: dict[str, list] = {}
        self.lock = threading.RLock()
        self.workers: dict[str, threading.Thread] = {}
        self.flags: dict[str, str] = {}          # id -> 'pause' / 'cancel' / 'stop'
        self.wake = threading.Event()
        self.stop_ev = threading.Event()
        self.paused_all = False
        self.th = None
        self.hot_check = lambda p: False         # set by the engine
        self.on_done_paths = lambda paths, job: None
        self.on_touch = lambda path: None
        self.on_job_done = lambda job: None
        self.vault = None                        # set by the engine (保管區)
        self.seq = time.time()
        self.lane_state = {}                     # lane -> 'yield' when giving way
        self._dirty = set()                      # job ids whose item list changed (renamed targets) since the last save

    # --------------------------------------------------------------------------- persistence
    def _jf(self, jid): return QUEUE_DIR / f'{jid}.json'
    def _if(self, jid): return QUEUE_DIR / f'{jid}.items.json'

    def save_job(self, job):
        job = dict(job)                                                 # snapshot: the worker adds keys meanwhile
        if isinstance(job.get('states'), States): job['states'] = str(job['states'])
        try: atomic_write_json(self._jf(job['id']), job, indent=None, durable=True)   # power cut: old or new, never empty
        except Exception: self.log.exc('queue', 'save job')

    def _items(self, jid):
        """The item list, read from its file when it was let go (finished jobs keep ~100 MB per 200k items otherwise)."""
        it = self.items.get(jid)
        if it is None:
            it = read_json(self._if(jid), None)
            it = it if isinstance(it, list) else []
            if jid in self.jobs: self.items[jid] = it
        return it

    def _release_items(self, j):
        if j['state'] in FINAL and len(self.items.get(j['id']) or ()) > 5000:
            if self._take_dirty(j['id']): self.save_items(j['id'])
            self.items.pop(j['id'], None)

    def _take_dirty(self, jid):
        if jid in self._dirty: self._dirty.discard(jid); return True
        return False

    def save_items(self, jid):
        try: atomic_write_json(self._if(jid), self.items.get(jid, []), indent=None, durable=True)
        except Exception: self.log.exc('queue', 'save items')

    def load(self):
        n = 0
        for f in sorted(QUEUE_DIR.glob('*.json')):
            if f.name.endswith('.items.json'): continue
            j = read_json(f)
            if not isinstance(j, dict) or 'id' not in j:
                self.log.warn('queue', f'工作檔損壞，略過（檔案都還在原處）：{f.name}'); continue
            if j.get('state') in ACTIVE:
                j['state'] = 'queued'; j['resume'] = True
            if j.get('kind') == 'recycle':                              # old versions: the recycle bin can silently delete -> vault
                j['kind'] = 'vault'; j['pos'] = 0; j.setdefault('opts', {})['reason'] = '你按了刪除（舊版的資源回收筒工作，改放保管區）'
            if j.get('state') == 'queued' and not j.get('resume') and not self.S.get('transfer.autostart'):
                j['state'] = 'paused'
            it = read_json(self._if(j['id']), None) if j.get('state') not in FINAL else None    # finished: read when looked at
            if it is not None: self.items[j['id']] = it
            uses_items = j.get('kind') not in ('vault', 'recycle') and not (j.get('kind') == 'move' and j.get('same')) and j.get('state') not in FINAL
            if (uses_items and j.get('scanned') and j.get('state') not in ('done', 'canceled', 'error')
                    and (not isinstance(it, list) or len(it) != len(j.get('states') or ''))):
                # the list of what to do is gone (crash / power cut): continuing would report 'done' having done nothing
                j['state'] = 'error'; j['resume'] = False
                j['msg'] = '工作清單檔損壞或遺失（可能是當機或斷電），為了安全沒有繼續；檔案都還在原處，請重新加入這個工作'
                self.log.warn('queue', f'{j["id"]}：{j["msg"]}')
            self.jobs[j['id']] = j; n += 1
            self.seq = max(self.seq, float(j.get('seq', 0)))
        if n: self.log.info('queue', f'載入 {n} 個工作')

    # --------------------------------------------------------------------------- hot update
    def export_state(self):
        return {'paused_all': self.paused_all}

    def adopt(self, st):
        self.paused_all = bool((st or {}).get('paused_all'))

    def start(self):
        self.load()
        self.th = threading.Thread(target=self._loop, name='HZ-Queue', daemon=True); self.th.start()
        return self

    def stop(self, timeout=15):
        """Stop at a safe point: every worker finishes its current chunk, keeps the partial file and is re-queued."""
        self.stop_ev.set(); self.wake.set()
        with self.lock:
            for jid in list(self.workers): self.flags[jid] = 'stop'
        t_end = time.time() + timeout
        for jid, th in list(self.workers.items()):
            th.join(max(0.1, t_end - time.time()))
        # a worker in the middle of one long step (e.g. measuring a 200,000-file folder before vaulting it) must
        # finish it: the next engine would otherwise start the same job twice. Data safety beats a fast reload.
        t_hard = time.time() + 300
        for jid, th in list(self.workers.items()):
            if th.is_alive():
                self.log.warn('queue', f'工作 {jid} 還在完成目前這一步，等它安全停下…')
                th.join(max(0.1, t_hard - time.time()))
        with self.lock:
            for j in self.jobs.values():
                if j['state'] in ACTIVE: j['state'] = 'queued'; j['resume'] = True
                self.save_job(j)
        if self.th: self.th.join(3)

    # --------------------------------------------------------------------------- adding
    def lanes_for(self, kind, src, dst):
        if kind in ('recycle', 'vault'): return []
        lanes = set()
        for s in src: lanes.update(self.drives.lane_of(s))
        if dst: lanes.update(self.drives.lane_of(dst))
        return sorted(lanes)

    def same_volume(self, a, b):
        try:
            if IS_WIN:
                da, db = os.path.splitdrive(norm(a))[0].upper(), os.path.splitdrive(norm(b))[0].upper()
                return bool(da) and da == db
            while b and not os.path.exists(b) and os.path.dirname(b) != b: b = os.path.dirname(b)   # folders not made yet
            return os.stat(a).st_dev == os.stat(b).st_dev
        except OSError:
            return False

    def add(self, kind, src, dst=None, opts=None, prio=0):
        src = [norm(s) for s in (src or []) if s]
        if not src and kind in ('copy', 'move') and (opts or {}).get('pairs'): src = [norm(opts['pairs'][0][0])]
        if not src: raise ValueError('沒有選擇任何項目')
        if kind == 'recycle': kind = 'vault'                          # the recycle bin can delete big files without asking
        if kind not in ('copy', 'move', 'delete', 'vault'): raise ValueError('不支援的動作')
        if kind == 'delete' and int((opts or {}).get('confirmed', 0)) != 3:
            raise ValueError('永久刪除需要確認三次')
        expect = (opts or {}).get('expect') or {}
        check_expect(src, expect)                                      # the page's row must still be this very file
        if kind == 'delete':                                           # what exactly was confirmed: size + time of each file
            opts = dict(opts or {}); fp = {}
            ekey = {(norm(k).lower() if IS_WIN else norm(k)): v for k, v in expect.items()}
            for s_ in src:
                e = ekey.get(s_.lower() if IS_WIN else s_)
                if e and float(e[0]) >= 0: fp[s_] = [int(e[0]), float(e[1] or 0)]; continue   # what the user SAW
                try:
                    st_ = os.lstat(W.lp(s_))
                    if not os.path.isdir(W.lp(s_)): fp[s_] = [st_.st_size, st_.st_mtime]
                except OSError: pass
            opts['confirmed_fp'] = fp
        lane_src = None
        if kind in ('copy', 'move') and (opts or {}).get('pairs'):          # explicit file -> file (sync, organise by date)
            if any(x and len(x) == 2 and not (_absolute(x[0]) and _absolute(x[1])) for x in opts['pairs']):
                raise ValueError('檔案清單裡有不完整的路徑，為了安全沒有執行')
            prs = [[norm(x[0]), norm(x[1])] for x in opts['pairs'] if x and len(x) == 2 and not same_path(x[0], x[1])]
            if not prs: raise ValueError('沒有要處理的檔案')
            opts = dict(opts); opts['pairs'] = prs
            src = [x[0] for x in prs]
            lane_src = sorted({os.path.dirname(x[0]) for x in prs})[:50]
            if not dst: dst = os.path.dirname(prs[0][1])
        elif kind in ('copy', 'move'):
            if not dst: raise ValueError('沒有目的地')
            if not _absolute(dst):                                         # '備份' would land in the program's folder
                raise ValueError(f'請輸入完整路徑，例如 K:\\備份（「{dst}」不是完整路徑）' if IS_WIN else f'請輸入完整路徑（「{dst}」不是完整路徑）')
            dst = norm(dst)
            for s in src:
                if os.path.isdir(s) and (is_under(dst, s) or is_under(os.path.realpath(dst), os.path.realpath(s))):   # also via a link
                    raise ValueError(f'不能把資料夾放進它自己裡面：{s}')
                if kind == 'move' and same_path(os.path.dirname(s), dst): raise ValueError('來源和目的地是同一個資料夾')
        if kind == 'recycle' and IS_WIN:
            from hz_common import drive_of
            for s_ in src:
                v = self.drives.get(drive_of(s_))
                if v.get('type') == 'remote' or (v.get('type') == 'removable' and (v.get('fs') or '').upper() != 'NTFS'):
                    raise ValueError(f'{drive_of(s_)} 沒有資源回收筒（網路磁碟或隨身碟），刪除會直接消失：請改用「永久刪除」')
        o = {'conflict': self.S.get('transfer.conflict'), 'verify': bool(self.S.get('transfer.verify')),
             'preserve': bool(self.S.get('transfer.preserve_times'))}
        o.update(opts or {}); o.pop('expect', None)
        if lane_src is not None and kind == 'move':
            same = all(self.same_volume(a, b) for a, b in opts['pairs'][:2000])
        else:
            same = kind == 'move' and all(self.same_volume(s, dst) for s in (lane_src or src))
        hot = bool(dst and self.hot_check(dst))
        with self.lock:
            self.seq += 1
            job = {'id': time.strftime('%m%d%H%M%S') + '_' + uuid.uuid4().hex[:6], 'kind': kind, 'src': src, 'dst': dst, 'opts': o,
                   'state': 'queued', 'prio': int(prio) + (100 if hot and self.S.get('transfer.hot_first') else 0), 'hot': hot,
                   'seq': self.seq, 'created': time.time(), 'started': 0, 'finished': 0, 'same': same,
                   'lanes': [] if same else self.lanes_for(kind, lane_src or src, dst),
                   'total_files': 0, 'total_bytes': 0, 'done_files': 0, 'done_bytes': 0, 'skipped': 0, 'err_count': 0,
                   'errors': [], 'cur': None, 'speed': 0.0, 'eta': None, 'msg': '', 'pos': 0, 'states': '', 'scanned': False}
        if kind == 'delete':                                           # list exactly what was confirmed, right now:
            self.flags.pop(job['id'], None)                            # files that appear later are never deleted
            self._scan(job)
            job['state'] = 'queued'; job['msg'] = ''
        with self.lock:
            self.jobs[job['id']] = job
            self.save_job(job)
        self.log.info('queue', f'新增{self._kind_text(kind)}：{len(src)} 項 → {dst or ""}' + ('（熱處理優先）' if hot else ''))
        self.wake.set()
        return job['id']

    @staticmethod
    def _kind_text(k):
        return {'copy': '複製', 'move': '移動', 'delete': '永久刪除', 'recycle': '刪除到資源回收筒', 'vault': '刪除（放進保管區）'}.get(k, k)

    # --------------------------------------------------------------------------- control
    def action(self, jid, act, data=None):
        with self.lock:
            j = self.jobs.get(jid)
            if j is None: raise KeyError('找不到這個工作')
            st = j['state']
            if act == 'pause':
                if st in ACTIVE: self.flags[jid] = 'pause'
                elif st in ('queued', 'waiting'): j['state'] = 'paused'
            elif act == 'resume':
                if st in ('paused', 'error') or (st == 'waiting' and not j.get('question')): j['state'] = 'queued'
            elif act == 'cancel':
                if st in ACTIVE: self.flags[jid] = 'cancel'
                elif st not in FINAL: j['state'] = 'canceled'; j['finished'] = time.time(); j['question'] = None; self._cleanup_partials(j)
            elif act == 'remove':
                if st in ACTIVE: raise ValueError('執行中的工作請先停止')
                self._cleanup_partials(j) if st not in ('done',) else None
                del self.jobs[jid]; self.items.pop(jid, None)
                for f in (self._jf(jid), self._if(jid)):
                    try: f.unlink()
                    except OSError: pass
                return True
            elif act in ('top', 'up', 'down', 'bottom'):
                self._reorder(j, act)
            elif act == 'prio':
                j['prio'] = int((data or {}).get('prio', 0))
            elif act == 'retry':
                states = list(j.get('states') or '')
                n = 0
                for i, s in enumerate(states):
                    if s == ST_ERR: states[i] = ST_PENDING; n += 1
                j['states'] = ''.join(states); j['err_count'] = 0; j['errors'] = []
                if n or st in ('error', 'canceled'):
                    j['pos'] = min([i for i, s in enumerate(states) if s in (ST_PENDING, ST_PARTIAL)] or [len(states)])
                    j['state'] = 'queued'; j['finished'] = 0
                    if not j.get('scanned'): j['pos'] = 0
            elif act == 'answer':
                q = j.get('question')
                if not q: return False
                a = (data or {}).get('action', 'skip')
                if q.get('kind') == 'space' and a != 'cancel':
                    j['opts']['space_ok'] = True; j['question'] = None; j['state'] = 'queued'
                elif a == 'cancel':
                    j['question'] = None; j['state'] = 'canceled'; j['finished'] = time.time(); self._cleanup_partials(j)
                else:
                    if (data or {}).get('all'): j['opts']['conflict'] = a
                    else: j['once'] = {'dst': q['dst'], 'action': a}
                    j['question'] = None; j['state'] = 'queued'
            else:
                raise ValueError('不支援的操作')
            self.save_job(j)
        self.wake.set()
        return True

    def _reorder(self, j, act):
        q = sorted((x for x in self.jobs.values() if x['state'] not in FINAL), key=lambda x: (-x['prio'], x['seq']))
        same = [x for x in q if x['prio'] == j['prio']]
        if act == 'top':
            j['prio'] = max([x['prio'] for x in q] + [0]); same = [x for x in q if x['prio'] == j['prio'] and x is not j]
            j['seq'] = (min([x['seq'] for x in same]) if same else self.seq) - 1
        elif act == 'bottom':
            j['seq'] = (max([x['seq'] for x in same]) if same else self.seq) + 1
        else:
            k = same.index(j) if j in same else -1
            o = k - 1 if act == 'up' else k + 1
            if k >= 0 and 0 <= o < len(same):
                j['seq'], same[o]['seq'] = same[o]['seq'], j['seq']
                self.save_job(same[o])

    def pause_all(self, on: bool):
        with self.lock:
            self.paused_all = on
            for jid, j in self.jobs.items():
                if on and j['state'] in ACTIVE: self.flags[jid] = 'pause'
                elif on and j['state'] == 'queued': j['state'] = 'paused'; self.save_job(j)
                elif not on and j['state'] == 'paused': j['state'] = 'queued'; self.save_job(j)
        self.wake.set()

    def clear_finished(self):
        with self.lock:
            for jid in [k for k, j in self.jobs.items() if j['state'] in FINAL]:
                self.action(jid, 'remove')

    def _cleanup_partials(self, j):
        for k, (it, s) in enumerate(zip(self._items(j['id']), j.get('states') or '')):
            if s in (ST_PARTIAL, ST_ERR, ST_PENDING) and it[4] == 'f' and it[1]:
                try: os.remove(W.lp(self._part(j, k, it[1])))
                except OSError: pass

    # --------------------------------------------------------------------------- views
    def lane_limit(self, lane):
        over = self.S.get('transfer.disk_max') or {}
        if lane.startswith('d') and str(lane[1:]) in over: return max(1, int(over[str(lane[1:])]))
        m = self.drives.lane_media(lane)
        if m == 'SSD': return max(1, int(self.S.get('transfer.ssd_max')))
        if m == 'NET': return max(1, int(self.S.get('transfer.net_max')))
        return max(1, int(self.S.get('transfer.hdd_max')))

    def in_sched(self):
        """Inside the 'daytime limits' hours?"""
        if not self.S.get('transfer.sched_on'): return False
        f, t = int(self.S.get('transfer.sched_from') or 0) % 24, int(self.S.get('transfer.sched_to') or 0) % 24
        hnow = time.localtime().tm_hour
        return (f <= hnow < t) if f < t else (hnow >= f or hnow < t) if f > t else False

    def lane_pct(self, lane):
        over = self.S.get('transfer.disk_pct') or {}
        if lane.startswith('d') and str(lane[1:]) in over: base = int(over[str(lane[1:])])
        else: base = int(self.S.get('transfer.usage_pct') or 100)
        if self.in_sched(): base = min(base, int(self.S.get('transfer.sched_pct') or base))
        return base

    def cap_mbps(self):
        cap = float(self.S.get('transfer.mbps_cap') or 0)
        if self.in_sched():
            sc = float(self.S.get('transfer.sched_mbps') or 0)
            if sc > 0: cap = min(cap, sc) if cap > 0 else sc
        return cap

    def summary(self, j):
        """What the page polls every 1.5 s: keep it small even for a 1,000,000-file job."""
        j = dict(j)                              # one atomic copy: the worker adds keys while the page polls
        d = {k: v for k, v in j.items() if k not in ('states', 'errors', 'opts', 'src', 'pairs', 'tops', 'vault_ids', 'scan_bad', 'over_ok')}
        d['vault_n'] = len(j.get('vault_ids') or []); d['scan_bad_n'] = len(j.get('scan_bad') or [])
        d['errors'] = (j.get('errors') or [])[-5:]
        src = j.get('src') or []
        d['src'] = src[:20]; d['src_n'] = len(src)
        d['opts'] = {k: v for k, v in (j.get('opts') or {}).items() if k not in ('pairs', 'confirmed_fp')}
        return d

    def list(self):
        with self.lock:
            jobs = sorted(self.jobs.values(), key=lambda x: (x['state'] in FINAL, -x['prio'] if x['state'] not in FINAL else 0,
                                                              x['seq'] if x['state'] not in FINAL else -x.get('finished', 0)))
            out = [self.summary(j) for j in jobs]
            lanes = {}
            for j in self.jobs.values():
                for ln in j.get('lanes') or []:
                    L = lanes.setdefault(ln, {'lane': ln, 'running': 0, 'queued': 0})
                    if j['state'] in ACTIVE: L['running'] += 1
                    elif j['state'] == 'queued': L['queued'] += 1
            for ln, L in lanes.items():
                L.update(limit=self.lane_limit(ln), pct=self.lane_pct(ln), media=self.drives.lane_media(ln),
                         rate=self.meter.rate(ln), state=self.lane_state.get(ln, ''))
        return {'jobs': out, 'lanes': list(lanes.values()), 'paused_all': self.paused_all,
                'running': sum(1 for j in out if j['state'] in ACTIVE), 'queued': sum(1 for j in out if j['state'] == 'queued'),
                'waiting': sum(1 for j in out if j['state'] == 'waiting'),
                'speed': sum(j.get('speed') or 0 for j in out if j['state'] in ACTIVE),
                'sched': {'on': self.in_sched(), 'pct': self.S.get('transfer.sched_pct'), 'mbps': self.S.get('transfer.sched_mbps'),
                          'to': self.S.get('transfer.sched_to')} if self.S.get('transfer.sched_on') else None}

    def detail(self, jid, offset=0, limit=500, only=''):
        limit = max(1, min(5000, int(limit or 500))); offset = max(0, int(offset or 0))
        with self.lock:
            j = self.jobs.get(jid)
            if j is None: return None
            items = self._items(jid); states = j.get('states') or ''
            rows = []; n = 0                                            # only the page asked for is built (was all 200k under the lock)
            for k, it in enumerate(items):
                s = states[k] if k < len(states) else ST_PENDING
                if only and s not in only: continue
                if offset <= n < offset + limit: rows.append({'i': k, 'src': it[0], 'dst': it[1], 'size': it[2], 'kind': it[4], 's': s})
                n += 1
            d = {k: v for k, v in dict(j).items() if k not in ('states', 'vault_ids', 'over_ok')}
            d['items_total'] = n; d['items'] = rows
            return d

    # --------------------------------------------------------------------------- scheduler
    def _loop(self):
        while not self.stop_ev.is_set():
            try: self._schedule()
            except Exception: self.log.exc('queue', 'schedule')
            self.wake.wait(0.5); self.wake.clear()

    def _schedule(self):
        with self.lock:
            for jid, th in list(self.workers.items()):
                if not th.is_alive(): del self.workers[jid]; self.flags.pop(jid, None)
            if self.paused_all or self.stop_ev.is_set(): return
            running = [j for j in self.jobs.values() if j['state'] in ACTIVE]
            used = {}
            for j in running:
                for ln in j.get('lanes') or []: used[ln] = used.get(ln, 0) + 1
            total = len([j for j in running if j.get('lanes')])
            maxt = max(1, int(self.S.get('transfer.max_total') or 4))
            for j in sorted((x for x in self.jobs.values() if x['state'] == 'queued'), key=lambda x: (-x['prio'], x['seq'])):
                if j['id'] in self.workers: continue
                lanes = j.get('lanes') or []
                if lanes:
                    if total >= maxt: continue
                    if any(used.get(ln, 0) >= self.lane_limit(ln) for ln in lanes): continue
                    for ln in lanes: used[ln] = used.get(ln, 0) + 1
                    total += 1
                j['state'] = 'running'
                if not j['started']: j['started'] = time.time()
                th = threading.Thread(target=self._work, args=(j,), name='HZ-Job-' + j['id'], daemon=True)
                self.workers[j['id']] = th; self.flags.pop(j['id'], None)
                th.start()

    # --------------------------------------------------------------------------- worker
    def _check(self, j):
        f = self.flags.get(j['id'])
        if f: raise Interrupted(f)
        if self.stop_ev.is_set(): raise Interrupted('stop')

    def _err(self, j, path, e):
        j['err_count'] += 1
        msg = e.strerror if isinstance(e, OSError) and e.strerror else str(e)
        if len(j['errors']) < 300: j['errors'].append({'path': path, 'msg': msg, 't': time.time()})
        self.log.warn('queue', f'{path}：{msg}')

    def _work(self, j):
        jid = j['id']; reason = None
        try:
            r = None
            if j['kind'] == 'recycle': self._do_recycle(j)
            elif j['kind'] == 'vault': self._do_vault(j)
            elif j['kind'] == 'move' and j.get('same'): r = self._do_rename_move(j)
            else:
                if not j.get('scanned'): self._scan(j)
                r = self._do_items(j)
            if r == 'wait': return                                  # a question is open (or was answered already)
            with self.lock:
                if j['state'] not in ACTIVE: return                 # paused / canceled by the user meanwhile: not 'done'
                left = sum(1 for c in (j.get('states') or '') if c in (ST_PENDING, ST_PARTIAL))
                if left:                                            # never report 'done' with items not handled
                    raise RuntimeError(f'還有 {left} 個項目沒有處理（內部錯誤），請按「重試」')
                failed = j['err_count'] and j['done_files'] == 0 and j['total_files']
                j['state'] = 'error' if failed else 'done'
                j['finished'] = time.time(); j['cur'] = None; j['speed'] = 0; j['eta'] = None
                j['msg'] = (f'失敗：{j["err_count"]} 個錯誤' if failed else f'完成，{j["err_count"]} 個錯誤' if j['err_count'] else '完成') + (f'，略過 {j["skipped"]}' if j['skipped'] else '')
            self.log.info('queue', f'{self._kind_text(j["kind"])}完成：{j["done_files"]} 個檔案 {fmt_size(j["done_bytes"])}' + (f'，{j["err_count"]} 個錯誤' if j['err_count'] else ''))
            try: self.on_job_done(j)
            except Exception: self.log.exc('queue', 'on_job_done')
            self._trim_done()
        except Interrupted as e:
            reason = str(e)
            with self.lock:
                j['speed'] = 0; j['eta'] = None
                if reason == 'pause': j['state'] = 'paused'; j['msg'] = '已暫停'
                elif reason == 'cancel':
                    j['state'] = 'canceled'; j['finished'] = time.time(); j['msg'] = '已取消'; self._cleanup_partials(j)
                else: j['state'] = 'queued'; j['resume'] = True
        except Exception as e:
            self.log.exc('queue', f'工作 {jid} 失敗')
            with self.lock:
                j['state'] = 'error'; j['msg'] = str(e); j['finished'] = time.time(); j['speed'] = 0
        finally:
            with self.lock:
                self.flags.pop(jid, None)
                if jid in self.jobs:
                    if self._take_dirty(j['id']): self.save_items(jid)
                    self.save_job(j)
                    self._release_items(j)
            self.wake.set()

    def _trim_done(self):
        keep = int(self.S.get('transfer.keep_done') or 200)
        with self.lock:
            done = sorted((x for x in self.jobs.values() if x['state'] in FINAL), key=lambda x: x.get('finished', 0))
            for x in done[:max(0, len(done) - keep)]:
                try: self.action(x['id'], 'remove')
                except Exception: pass

    # ---- scanning
    def _scan(self, j):
        j['state'] = 'scanning'; j['msg'] = '正在列出檔案…'
        items = []; tb = 0; t_last = time.time()
        pairs = (j.get('opts') or {}).get('pairs') if j['kind'] in ('copy', 'move') else None
        for sp, dp in (pairs or []):                                  # folder sync: explicit source -> target file pairs
            self._check(j)
            try: st = os.stat(W.lp(sp))
            except OSError as e: self._err(j, sp, e); continue
            if not os.path.isfile(W.lp(sp)): continue
            items.append([norm(sp), norm(dp), st.st_size, st.st_mtime, 'f']); tb += st.st_size
        if pairs:                                                       # now in the items file; keep the job file small
            j['opts']['pairs_n'] = len(pairs); j['opts'].pop('pairs', None)
        for s in ([] if pairs else j['src']):
            self._check(j)
            if not os.path.lexists(W.lp(s)):
                self._err(j, s, FileNotFoundError('找不到來源')); continue
            if j['kind'] == 'delete':
                base_dst = None
            else:
                base_dst = os.path.join(j['dst'], os.path.basename(s.rstrip('\\/')) or s.replace(':', '').strip('\\/'))
                if j['kind'] == 'copy' and same_path(base_dst, s): base_dst = _copy_name(s)
                j.setdefault('tops', []).append([s, base_dst, os.path.lexists(W.lp(base_dst))])     # for undo
            if W.is_link_like(s):                                       # symlink / junction: never walk into its target
                if j['kind'] == 'delete': items.append([s, None, 0, 0, 'l'])
                else: self._err(j, s, OSError('這是連結（junction／捷徑資料夾），為了安全沒有處理它指向的內容')); j.setdefault('scan_bad', []).append(s)
                continue
            if os.path.isdir(s) and not os.path.islink(s):
                items.append([s, base_dst, 0, 0, 'd'])
                walk_top = ('\\\\?\\' + os.path.abspath(s) if not s.startswith('\\\\') else '\\\\?\\UNC\\' + s[2:]) if IS_WIN else s
                def _onerr(e, s=s):
                    self._err(j, getattr(e, 'filename', '') or s, e); j.setdefault('scan_bad', []).append(s)
                for root, dirs, files, links in W.walk(walk_top, onerror=_onerr):
                    self._check(j)
                    if IS_WIN and root.startswith('\\\\?\\'): root = root[4:] if not root.startswith('\\\\?\\UNC\\') else '\\' + root[7:]
                    rel = os.path.relpath(root, s)
                    droot = base_dst if rel == '.' else (os.path.join(base_dst, rel) if base_dst else None)
                    for d in dirs:
                        items.append([os.path.join(root, d), os.path.join(droot, d) if droot else None, 0, 0, 'd'])
                    for d in links:
                        if j['kind'] == 'delete': items.append([os.path.join(root, d), None, 0, 0, 'l'])
                        else: self._err(j, os.path.join(root, d), OSError('連結資料夾（junction）已略過，沒有複製它指向的內容')); j.setdefault('scan_bad', []).append(s)
                    for f in files:
                        p = os.path.join(root, f)
                        try: st = os.stat(W.lp(p))
                        except OSError as e: self._err(j, p, e); j.setdefault('scan_bad', []).append(s); continue
                        items.append([p, os.path.join(droot, f) if droot else None, st.st_size, st.st_mtime, 'f']); tb += st.st_size
                    if time.time() - t_last > 0.5:
                        j['msg'] = f'正在列出檔案… {len(items):,} 項 {fmt_size(tb)}'; t_last = time.time()
            else:
                try: st = os.stat(W.lp(s))
                except OSError as e: self._err(j, s, e); continue
                items.append([s, base_dst, st.st_size, st.st_mtime, 'f']); tb += st.st_size
        if j['kind'] == 'delete':
            items = ([it for it in items if it[4] == 'f'] + [it for it in items if it[4] == 'l'] +       # files, then links (only the link itself),
                     [it for it in items if it[4] == 'd'][::-1])                                       # then folders deepest first
        with self.lock:
            self.items[j['id']] = items
            j['states'] = ST_PENDING * len(items); j['pos'] = 0
            j['total_files'] = sum(1 for it in items if it[4] == 'f'); j['total_bytes'] = tb
            j['scanned'] = True; j['state'] = 'running'; j['msg'] = ''
            self.save_items(j['id']); self.save_job(j)

    def _set_state(self, j, k, s):
        if not isinstance(j['states'], States): j['states'] = States(j['states'])
        j['states'].set(k, s)

    def _part(self, j, k, dst):
        """The temporary copy: named after the job and the item, never after the target (a user's own
        'photo.jpg.hzpart' was emptied; two jobs bringing the same name into one folder wrote into one part file)."""
        return os.path.join(os.path.dirname(dst), f'.hz{j["id"]}_{k}{PART}')

    def _do_items(self, j):
        items = self._items(j['id'])
        last_save = time.time(); hist = deque(maxlen=12); dirs_done = []
        keep_src = j['kind'] == 'move'                                    # moved originals always go to the vault (rule: nothing vanishes)
        o = j['opts']; touched = []
        if j['kind'] in ('copy', 'move') and not o.get('space_ok'):
            r = self._space_question(j, items)
            if r: return r
        for k in range(j.get('pos', 0), len(items)):
            self._check(j)
            s = j['states'][k] if k < len(j['states']) else ST_PENDING
            if s in (ST_DONE, ST_SKIP, ST_ERR): j['pos'] = k + 1; continue
            src, dst, size, mt, kind = items[k]
            j['pos'] = k; bytes_before = j['done_bytes']
            try:
                if j['kind'] == 'delete':
                    if kind == 'f':
                        st = os.lstat(W.lp(src)); cf = (j['opts'].get('confirmed_fp') or {}).get(src)
                        if st.st_size != size or abs(st.st_mtime - mt) > 2 or (cf and (st.st_size != cf[0] or abs(st.st_mtime - cf[1]) > 2)):
                            raise IOError('這個檔案在你確認刪除之後被修改過，為了安全沒有刪除（請重新確認）')
                    self._delete_one(src, kind); self._set_state(j, k, ST_DONE)
                    if kind == 'f': j['done_files'] += 1; j['done_bytes'] += size
                elif kind == 'd':
                    os.makedirs(W.lp(dst), exist_ok=True); self._set_state(j, k, ST_DONE); dirs_done.append(k)
                else:
                    r = self._copy_item(j, k, src, dst, size, mt, hist)
                    if r == 'wait': return 'wait'
                    if r == 'skip':
                        self._set_state(j, k, ST_SKIP); j['skipped'] += 1; j['done_bytes'] = bytes_before + size
                    else:
                        self._set_state(j, k, ST_DONE); j['done_files'] += 1
                        if j['kind'] == 'move' and not keep_src:
                            self._remove_src_file(src, j, r)
                        touched.append(r)
            except Interrupted:
                raise
            except Exception as e:
                self._set_state(j, k, ST_ERR); self._err(j, src, e)
                if kind == 'f':
                    j['done_bytes'] = bytes_before + size                  # (the bytes of a half copy were counted already)
                    if dst:
                        try: os.remove(W.lp(self._part(j, k, dst)))       # disk full: do not leave gigabytes behind
                        except OSError: pass
            j['pos'] = k + 1
            if time.time() - last_save > 3:
                with self.lock:
                    if self._take_dirty(j['id']): self.save_items(j['id'])   # renamed targets (keep both): before the states
                    self.save_job(j)
                last_save = time.time()
        j['cur'] = None
        if j['kind'] in ('copy', 'move') and o.get('preserve'):
            for k in reversed(dirs_done):
                src, dst = items[k][0], items[k][1]
                try:
                    st = os.stat(W.lp(src)); W.set_times(dst, _birth(st), st.st_atime, st.st_mtime)
                    W.set_attrs(dst, W.get_attrs(src))
                except OSError:
                    pass
        if j['kind'] == 'move' and keep_src:
            self._stash_moved_sources(j, items)
        if j['kind'] == 'move':
            for it in reversed(items):
                if it[4] == 'd':
                    try: os.rmdir(W.lp(it[0]))
                    except OSError: pass
            for s in j['src']: self.on_touch(s)
        if j['kind'] == 'delete':
            for s in j['src']: self.on_touch(s)
        if j.get('dst'):
            for s in j['src']:
                self.on_touch(os.path.join(j['dst'], os.path.basename(s.rstrip('\\/'))))
        if touched: self.on_done_paths(touched, j)

    def _delete_one(self, path, kind):
        p = W.lp(path)
        if kind == 'l':                                                 # remove the link, never what it points to
            if not W.is_link_like(path): raise IOError('這個連結在確認之後被換成了真的資料夾，為了安全沒有刪除')
            if IS_WIN:
                try: os.rmdir(p)
                except OSError: os.unlink(p)
            else: os.unlink(p)
            return
        if kind == 'd':
            os.rmdir(p)
        else:
            try: os.remove(p)
            except PermissionError:
                W.set_attrs(path, 0x80); os.remove(p)

    def _remove_src_file(self, src, j=None, dst=None):
        if True:
            self._stash(src, f'已跨磁碟移動到 {dst or (j or {}).get("dst", "")}，原檔先保管', 'move_src', j); return
        try: os.remove(W.lp(src))
        except PermissionError:
            W.set_attrs(src, 0x80); os.remove(W.lp(src))

    def _stash_moved_sources(self, j, items):
        """Cross-drive move finished: each source folder / file goes into the vault as ONE item (not file by file).
        A source with skipped or failed items stays where it is; only its copied files are put in the vault."""
        states = j.get('states') or ''
        tops = {t: [] for t in j['src']}                                # one pass (was items x sources: 80 min at 200k)
        for k, it in enumerate(items):
            p = it[0]
            for _ in range(256):
                if p in tops: tops[p].append((k, it)); break
                up = os.path.dirname(p)
                if up == p: break
                p = up
        for top in j['src']:
            mine = tops.get(top) or []
            files = [(k, it) for k, it in mine if it[4] == 'f']
            if not mine or not os.path.lexists(W.lp(top)): continue
            if all(states[k] == ST_DONE for k, it in mine) and top not in (j.get('scan_bad') or []) and self._unchanged_since_scan(top, mine):
                try: self._stash(top, f'已跨磁碟移動到 {j["dst"]}，原本的{"資料夾" if os.path.isdir(top) else "檔案"}先保管', 'move_src', j)
                except Exception as e: self._err(j, top, e)
            else:
                for k, it in files:
                    if states[k] == ST_DONE and os.path.lexists(W.lp(it[0])):
                        try:
                            st = os.stat(W.lp(it[0]))
                            if st.st_size != it[2] or abs(st.st_mtime - it[3]) > 2:     # changed after it was copied:
                                self._err(j, it[0], IOError('複製完成後原檔又被修改，留在原處沒有移走（目的地是修改前的版本）')); continue
                            self._stash(it[0], f'已跨磁碟移動到 {it[1]}，原檔先保管', 'move_src', j)
                        except Exception as e: self._err(j, it[0], e)

    def _unchanged_since_scan(self, top, mine):
        """Walk the source again: every file still there must be one we copied, with the same size and time.
        (A photo added to the folder while the job waited was never copied -> the folder must not be vaulted whole.)"""
        if not os.path.isdir(W.lp(top)): return True
        known = {it[0]: (it[2], it[3]) for k, it in mine if it[4] == 'f'}
        key = (lambda p: p.lower()) if IS_WIN else (lambda p: p)
        known = {key(p): v for p, v in known.items()}
        walk_top = ('\\\\?\\' + os.path.abspath(top) if not top.startswith('\\\\') else '\\\\?\\UNC\\' + top[2:]) if IS_WIN else top
        bad = []
        for root, dirs, files, links in W.walk(walk_top, onerror=lambda e: bad.append(e)):
            if links: return False                                       # a link inside: keep it simple, stash file by file
            if IS_WIN and root.startswith('\\\\?\\'): root = root[4:] if not root.startswith('\\\\?\\UNC\\') else '\\' + root[7:]
            for f in files:
                p = os.path.join(root, f); v = known.get(key(p))
                if v is None: return False
                try: st = os.stat(W.lp(p))
                except OSError: return False
                if st.st_size != v[0] or abs(st.st_mtime - v[1]) > 2: return False
        return not bad

    def _stash(self, path, reason, action, j=None):
        if self.vault is None: raise IOError('保管區沒有啟動，為了安全不覆蓋／不刪除')
        return self.vault.stash(path, reason, action, {'job': (j or {}).get('id')})

    def _do_vault(self, j):
        j['total_files'] = len(j['src'])
        why = (j.get('opts') or {}).get('reason') or '你按了刪除'
        for k in range(j.get('pos', 0), len(j['src'])):
            self._check(j)
            s = j['src'][k]
            try:
                rec = self._stash(s, why, 'delete', j); j['done_files'] += 1
                if rec: j.setdefault('vault_ids', []).append(rec['id'])        # Ctrl+Z puts them back
            except Exception as e:
                self._err(j, s, e)
            j['pos'] = k + 1
            self.on_touch(s)

    # ---- conflicts
    def _resolve(self, j, src, dst, size, mt):
        """-> final dst path, 'skip', or 'wait'."""
        if not os.path.lexists(W.lp(dst)): return dst
        once = j.get('once')
        if once and same_path(once.get('dst', ''), dst):
            act = once['action']; j['once'] = None
        else:
            act = j['opts'].get('conflict') or 'ask'
        if act == 'ask':
            try: dst_st = os.stat(W.lp(dst))
            except OSError: return dst
            with self.lock:
                j['question'] = {'kind': 'conflict', 'src': src, 'dst': dst, 'src_size': size, 'dst_size': dst_st.st_size,
                                 'src_mtime': mt, 'dst_mtime': dst_st.st_mtime}
                j['state'] = 'waiting'; j['msg'] = '目的地已有同名檔案，等你決定'; j['speed'] = 0
                self.save_job(j)
            self.log.info('queue', f'同名檔案，等待決定：{dst}')
            return 'wait'
        if act == 'skip': return 'skip'
        if act == 'rename': return unique_name(dst)
        if act == 'newer':
            try: return dst if mt > os.stat(W.lp(dst)).st_mtime + 1 else 'skip'
            except OSError: return dst
        if act == 'larger':
            try: return dst if size > os.stat(W.lp(dst)).st_size else 'skip'
            except OSError: return dst
        return dst                                                   # overwrite

    # ---- one file
    def _space_question(self, j, items):
        """Not enough free space for the whole job: ask before writing anything (overwritten files go to the
        vault on the same drive, so they free nothing)."""
        states = j.get('states') or ''
        need = sum(it[2] for k, it in enumerate(items) if it[4] == 'f' and (k >= len(states) or states[k] in (ST_PENDING, ST_PARTIAL)))
        if need <= 0 or not j.get('dst'): return None
        d = j['dst']
        while d and not os.path.isdir(W.lp(d)) and os.path.dirname(d) != d: d = os.path.dirname(d)
        try: free = shutil.disk_usage(W.lp(d)).free
        except OSError: return None
        if need + 64 * 1024 * 1024 <= free: return None
        with self.lock:
            if self.flags.get(j['id']): return None
            j['question'] = {'kind': 'space', 'need': need, 'free': free, 'dst': j['dst']}
            j['state'] = 'waiting'; j['msg'] = f'目的地空間不夠：需要 {fmt_size(need)}，只剩 {fmt_size(free)}'; j['speed'] = 0
            self.save_job(j)
        self.log.warn('queue', f'{j["id"]}：{j["msg"]}')
        return 'wait'

    def _copy_item(self, j, k, src, dst, size, mt, hist):
        part = self._part(j, k, dst)
        old_part = dst + PART                                           # versions before 0.1.60 (resume only, never deleted blindly)
        if j['states'][k] == ST_PARTIAL and not os.path.exists(W.lp(part)) and os.path.isfile(W.lp(old_part)):
            try: W.rename_noreplace(old_part, part)
            except OSError: pass
        offset = 0
        if (j.get('resume') and j['states'][k] in (ST_PARTIAL, ST_PENDING) and not os.path.exists(W.lp(part))
                and os.path.isfile(W.lp(dst))):
            # a job cut short (crash / power cut) right after the final rename, before its progress was saved: the
            # file there is OUR finished copy - not a clash to ask about, rename or vault. Only if every byte matches.
            try:
                if os.path.getsize(W.lp(dst)) == size and os.stat(W.lp(src)).st_size == size and self._same_content(j, src, dst):
                    return dst
            except OSError:
                pass
        if j['states'][k] == ST_PARTIAL and os.path.exists(W.lp(part)):
            offset = os.path.getsize(W.lp(part))
            try: st = os.stat(W.lp(src)); changed = st.st_size != size or abs(st.st_mtime - mt) > 2
            except OSError: changed = True
            if changed or offset > size or not self._tail_matches(src, part, offset): offset = 0
        else:
            existed = os.path.lexists(W.lp(dst))
            target = self._resolve(j, src, dst, size, mt)
            if target in ('skip', 'wait'): return target
            if target != dst:
                self.items[j['id']][k][1] = dst = target; part = self._part(j, k, dst)
                self._dirty.add(j['id'])                                # saved every few seconds, not per clash
            elif existed: j.setdefault('over_ok', []).append(k)         # the user / setting chose to overwrite this one
        try: st0 = os.stat(W.lp(src))
        except OSError as e: raise FileNotFoundError(f'找不到來源：{src}') from e
        self._set_state(j, k, ST_PARTIAL)
        j['cur'] = {'path': src, 'dst': dst, 'size': size, 'done': offset}
        os.makedirs(W.lp(os.path.dirname(dst)), exist_ok=True)
        digest = self._copy_data(j, src, part, size, offset, hist)
        try: st1 = os.stat(W.lp(src))
        except OSError: st1 = None
        if st1 is None or st1.st_size != st0.st_size or st1.st_mtime_ns != st0.st_mtime_ns or os.path.getsize(W.lp(part)) != st1.st_size:
            try: os.remove(W.lp(part))
            except OSError: pass
            raise IOError('來源在複製途中被修改（例如還在下載或編輯），為了安全沒有完成這個檔案，原檔留在原處；請稍後重試')
        self.items[j['id']][k][2] = st1.st_size; self.items[j['id']][k][3] = st1.st_mtime   # what was really copied
        if j['opts'].get('verify'):
            j['msg'] = '校驗中…'
            h = hashlib.md5()
            for b in W.read_unbuffered(part):
                self._check(j); h.update(b)
            if h.hexdigest() != digest:
                try: os.remove(W.lp(part))
                except OSError: pass
                raise IOError('校驗不一致（複製後內容不同），已刪除這個檔案的複本')
            j['msg'] = ''
        decided = k in (j.get('over_ok') or ())
        for _ in range(5):
            if os.path.isdir(W.lp(dst)) and not W.is_link_like(dst):
                raise IsADirectoryError(f'目的地是同名的資料夾，不能用檔案取代整個資料夾：{dst}')
            if os.path.lexists(W.lp(dst)) and not decided:              # appeared while copying (another job / program):
                t = self._resolve(j, src, dst, size, mt)                #  the user's choice applies, not a silent overwrite
                if t == 'wait': return 'wait'                           #  (the finished part file waits for the answer)
                if t == 'skip':
                    try: os.remove(W.lp(part))
                    except OSError: pass
                    return 'skip'
                if t != dst:
                    self.items[j['id']][k][1] = dst = t; self._dirty.add(j['id'])
                    new_part = self._part(j, k, dst)
                    os.replace(W.lp(part), W.lp(new_part)); part = new_part
                    continue
                decided = True
            if os.path.lexists(W.lp(dst)):                              # overwrite: the old file goes to the vault first
                self._stash(dst, f'{"移動" if j["kind"] == "move" else "複製"}時被覆蓋：新的檔案來自 {src}', 'overwrite', j)
            try: W.rename_noreplace(part, dst); break
            except FileExistsError: decided = False; continue          # appeared in between -> ask / apply the choice again
        else:
            raise IOError(f'目的地一直被別的程式重新建立，為了安全沒有覆蓋：{dst}')
        if j['opts'].get('preserve'):
            try:
                st = os.stat(W.lp(src))
                W.set_times(dst, _birth(st), st.st_atime, st.st_mtime)
                W.set_attrs(dst, W.get_attrs(src))
            except OSError:
                pass
        return dst

    def _same_content(self, j, a, b):
        with open(W.lp(a), 'rb') as fa, open(W.lp(b), 'rb') as fb:
            while True:
                self._check(j)
                x = fa.read(4 * 1024 * 1024); y = fb.read(4 * 1024 * 1024)
                if x != y: return False
                if not x: return True

    def _tail_matches(self, src, part, offset):
        n = min(offset, 64 * 1024)
        if n == 0: return True
        try:
            with open(W.lp(src), 'rb') as a, open(W.lp(part), 'rb') as b:
                a.seek(offset - n); b.seek(offset - n)
                return a.read(n) == b.read(n)
        except OSError:
            return False

    def _lane_wait(self, j, lanes):
        """Give way: other programs are using one of these disks (rate above transfer.yield_mbps)."""
        lim = float(self.S.get('transfer.yield_mbps') or 0)
        if lim <= 0 or self.counters is None: return
        t_first = None
        while True:
            busy_lane = None
            for ln in lanes:
                if not ln.startswith('d'): continue
                c = self.counters.get(int(ln[1:]))
                if not c: continue
                others = c['rd'] + c['wr'] - self.meter.rate(ln)
                if others > lim * 1024 * 1024: busy_lane = ln; break
            if busy_lane is None:
                for ln in lanes: self.lane_state.pop(ln, None)
                if t_first: j['msg'] = ''
                return
            self.lane_state[busy_lane] = 'yield'
            t_first = t_first or time.time()
            j['msg'] = '讓路中：其他程式正在使用這顆硬碟'; j['speed'] = 0
            if time.time() - t_first > 120: return                    # never wait forever
            self._check(j); time.sleep(0.5)

    def _copy_data(self, j, src, part, size, offset, hist):
        bufsize = max(1, int(self.S.get('transfer.buffer_mb') or 8)) * 1024 * 1024
        wt = bool(self.S.get('transfer.write_through'))
        src_l = self.drives.lane_of(src); dst_l = self.drives.lane_of(part)
        lanes = sorted(set(src_l) | set(dst_l))
        h = hashlib.md5() if j['opts'].get('verify') else None
        if h and offset:
            with W.open_src(src) as f:
                left = offset
                while left > 0:
                    b = f.read(min(bufsize, left))
                    if not b: break
                    h.update(b); left -= len(b)
        fsync_every = 64 * 1024 * 1024; since = 0
        with W.open_src(src) as fs, W.open_dst(part, offset, write_through=wt) as fd:
            if offset: fs.seek(offset)
            done = offset
            while True:
                self._check(j)
                self._lane_wait(j, lanes)
                t0 = time.perf_counter()
                b = fs.read(bufsize)
                t1 = time.perf_counter()
                if not b: break
                mv = memoryview(b); w = 0
                while w < len(b):
                    n = fd.write(mv[w:])
                    if not n: raise IOError('寫入失敗（磁碟已滿？）')
                    w += n
                since += len(b)
                if not wt and since >= fsync_every:
                    os.fsync(fd.fileno()); since = 0
                t2 = time.perf_counter()
                if h: h.update(b)
                done += len(b); j['done_bytes'] += len(b)
                j['cur']['done'] = done
                for ln in lanes: self.meter.add(ln, len(b))
                now = time.monotonic(); hist.append((now, j['done_bytes']))
                if len(hist) > 1 and now - hist[0][0] > 0.3:
                    j['speed'] = (hist[-1][1] - hist[0][1]) / (now - hist[0][0])
                    left = max(0, j['total_bytes'] - j['done_bytes'])
                    j['eta'] = left / j['speed'] if j['speed'] > 1 else None
                # pacing: read time belongs to the source disk, write time to the destination disk
                rt, wtm = t1 - t0, t2 - t1; until = 0
                mbps = self.cap_mbps()
                for ln in lanes:
                    busy = (rt if ln in src_l else 0) + (wtm if ln in dst_l else 0)
                    until = max(until, self.gates.debt(ln, busy, len(b), self.lane_pct(ln), mbps))
                self.gates.wait_until(until, lambda: self._check(j))
            if not wt:
                try: os.fsync(fd.fileno())
                except OSError: pass
        return h.hexdigest() if h else None

    # ---- same drive move = rename (instant)
    def _do_rename_move(self, j):
        if (j.get('opts') or {}).get('pairs'): return self._do_rename_pairs(j)
        dst = j['dst']; os.makedirs(W.lp(dst), exist_ok=True)
        j['total_files'] = len(j['src']); moved = []
        start = j.get('pos', 0)
        for k in range(start, len(j['src'])):
            self._check(j)
            s = j['src'][k]
            target = os.path.join(dst, os.path.basename(s.rstrip('\\/')))
            j['cur'] = {'path': s, 'dst': target, 'size': 0, 'done': 0}
            try:
                r = self._rename_into(j, s, target, moved)
                if r == 'wait': j['pos'] = k; return 'wait'
            except OSError as e:
                if getattr(e, 'errno', 0) == 18:                        # EXDEV (Linux: other mount) -> copy path
                    j['same'] = False; j['lanes'] = self.lanes_for('move', j['src'][k:], dst); j['src'] = j['src'][k:]
                    j['pos'] = 0; self._scan(j); return self._do_items(j)
                self._err(j, s, e); j['pos'] = k + 1; continue
            j['done_files'] += 1; j['pos'] = k + 1
            if k % 50 == 0:
                with self.lock: self.save_job(j)
        for s in j['src']: self.on_touch(s)
        for p in moved: self.on_touch(p)
        if moved: self.on_done_paths(moved, j)

    def _do_rename_pairs(self, j):
        """Same-drive move of explicit file pairs (organise by date): instant renames, never replacing anything."""
        prs = j['opts']['pairs']; j['total_files'] = len(prs); moved = []
        for k in range(j.get('pos', 0), len(prs)):
            self._check(j)
            s, d = prs[k]
            j['cur'] = {'path': s, 'dst': d, 'size': 0, 'done': 0}
            try:
                if not os.path.lexists(W.lp(s)):
                    if os.path.lexists(W.lp(d)): j['pos'] = k + 1; j['skipped'] += 1; continue   # moved by a run cut short
                    raise FileNotFoundError('找不到來源')
                os.makedirs(W.lp(os.path.dirname(d)), exist_ok=True)
                for _ in range(1000):
                    try: W.rename_noreplace(s, d); break
                    except FileExistsError: d = unique_name(d)
                moved.append(d); j.setdefault('pairs', []).append([s, d]); j['done_files'] += 1
            except OSError as e:
                if getattr(e, 'errno', 0) == 18 or getattr(e, 'winerror', 0) == 17:   # another drive after all -> copy path
                    j['same'] = False; j['opts']['pairs'] = prs[k:]; j['pos'] = 0; j['scanned'] = False
                    j['lanes'] = self.lanes_for('move', sorted({os.path.dirname(x[0]) for x in prs[k:]})[:50], j['dst'])
                    self._scan(j); return self._do_items(j)
                self._err(j, s, e)
            j['pos'] = k + 1
            if k % 200 == 0:
                with self.lock: self.save_job(j)
        for p in moved[:20000]: self.on_touch(p)
        for s_, _d in prs[:20000]: self.on_touch(s_)                      # the old names leave the search results
        for s_ in {os.path.dirname(x[0]) for x in prs}: self.on_touch(s_)
        if moved: self.on_done_paths(moved, j)

    def _rename_into(self, j, s, target, moved):
        if not os.path.lexists(W.lp(s)):
            # the source is gone: a run cut short (crash / power loss) already moved it, but its progress was not saved
            # yet. NEVER treat the target as a clash then - that would put the file we just moved into the vault.
            if os.path.lexists(W.lp(target)): return 'ok'
            raise FileNotFoundError(f'找不到來源：{s}')
        if not os.path.lexists(W.lp(target)):
            try:
                W.rename_noreplace(s, target); moved.append(target); j.setdefault('pairs', []).append([s, target]); return 'ok'
            except FileExistsError:
                pass                                                    # appeared meanwhile -> normal conflict handling
        if os.path.isdir(s) and os.path.isdir(target):                   # merge folders
            for name in os.listdir(W.lp(s)):
                r = self._rename_into(j, os.path.join(s, name), os.path.join(target, name), moved)
                if r == 'wait': return r
            try: os.rmdir(W.lp(s))
            except OSError: pass
            return 'ok'
        try: st = os.stat(W.lp(s)); size, mt = st.st_size, st.st_mtime
        except OSError: size, mt = 0, 0
        t = self._resolve(j, s, target, size, mt)
        if t == 'wait': return 'wait'
        if t == 'skip': j['skipped'] += 1; return 'skip'
        if same_path(t, target):
            if os.path.isdir(target) and not os.path.isdir(s): raise IsADirectoryError(f'目的地是資料夾：{target}')
            self._stash(target, f'移動時被取代：新的檔案來自 {s}', 'overwrite', j)
            W.rename_noreplace(s, target)
        else:
            W.rename_noreplace(s, t)
        moved.append(t); j.setdefault('pairs', []).append([s, t]); return 'ok'

    # ---- recycle bin
    def _do_recycle(self, j):
        """Never used for new jobs (add() turns 'recycle' into 'vault'): the recycle bin can delete silently."""
        j['kind'] = 'vault'; return self._do_vault(j)

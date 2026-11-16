"""HotZone FM — whole-drive index (Everything style) + folder sizes (TreeSize style).

Build:   NTFS + administrator -> read the $MFT directly (a few seconds to a minute for a whole drive)
         anything else        -> os.scandir walk (also used on Linux for testing)
Live:    NTFS -> USN change journal every second ; others -> full rescan every N minutes
         + every file operation done by HotZone FM itself is applied at once (touch()).
Cache:   Data\\index\\<drive>.pkl, reloaded at start and caught up from the USN journal.

Search syntax (like Everything):
  abc def        both words in the name             abc|def      either word
  !abc           name must not contain abc          "a b"        exact phrase
  *.mp4  a?c     wildcards match the whole name     regex:^\\d+$  regular expression on the name
  K:\\Work\\ ab    a term with \\ matches the full path     path:work  same
  ext:mp4;mkv    size:>1gb  size:100mb..2gb  size:empty
  dm:today dm:thisweek dm:last7days dm:2026-10 dm:>2026-01-01 dm:2026-01..2026-03
  file: folder:  parent:K:\\Work (direct children)   infolder:K:\\Work   hot: (inside hot folders)
  video: audio: pic: doc: zip: exe:   case:ABC   empty: (empty folders)
"""
from __future__ import annotations

import os
import pickle
import re
import unicodedata
import threading
import time
from array import array
from bisect import bisect_right
from datetime import datetime, timedelta

from hz_common import IS_WIN, INDEX_DIR, norm, is_under, Stoppable
import hz_win as W

F_USED, F_DIR, F_HIDDEN, F_SYSTEM = 1, 2, 4, 8
SEP = '\\' if IS_WIN else '/'

TYPE_EXT = {
    'video': 'mp4 mkv avi mov wmv flv ts m2ts mts webm mpg mpeg m4v 3gp rmvb vob',
    'audio': 'mp3 wav flac aac m4a ogg wma opus ape aiff alac',
    'pic': 'jpg jpeg png gif bmp webp tif tiff heic heif raw cr2 cr3 nef arw dng psd svg ico',
    'doc': 'doc docx xls xlsx ppt pptx pdf txt md rtf odt ods odp csv json xml html htm epub',
    'zip': 'zip rar 7z tar gz tgz bz2 xz zst iso cab',
    'exe': 'exe msi bat cmd ps1 com scr',
}
TYPE_ALIAS = {'影片': 'video', '音樂': 'audio', '圖片': 'pic', '文件': 'doc', '壓縮檔': 'zip', '程式': 'exe',
              'picture': 'pic', 'image': 'pic', 'music': 'audio', 'document': 'doc', 'compressed': 'zip', 'executable': 'exe'}
SIZE_UNITS = {'': 1, 'b': 1, 'k': 1024, 'kb': 1024, 'm': 1024 ** 2, 'mb': 1024 ** 2, 'g': 1024 ** 3, 'gb': 1024 ** 3, 't': 1024 ** 4, 'tb': 1024 ** 4}
SIZE_WORDS = {'empty': (0, 0), 'tiny': (0, 10 * 1024), 'small': (10 * 1024, 100 * 1024), 'medium': (100 * 1024, 1024 ** 2),
              'large': (1024 ** 2, 16 * 1024 ** 2), 'huge': (16 * 1024 ** 2, 128 * 1024 ** 2), 'gigantic': (128 * 1024 ** 2, 1 << 62)}


class QueryError(Exception):
    pass


# ============================================================================================ one root
class VolumeIndex:
    def __init__(self, key: str, root_path: str):
        self.key = key                       # 'K:' or a folder
        self.root_path = root_path           # 'K:\\'
        self.lock = threading.RLock()
        self.names: list = []
        self.parent = array('q')
        self.size = array('q')
        self.mtime = array('q')
        self.flags = bytearray()
        self.root_id = 0
        self.method = ''                     # mft / scan
        self.journal = None                  # {'id','next'}
        self.serial = ''
        self.state = 'empty'                 # empty / building / ready / error
        self.progress = 0.0
        self.msg = ''
        self.built_t = 0.0
        self.changed_t = 0.0
        self.saved_t = 0.0
        self.count_files = 0
        self.count_dirs = 0
        self.free_ids: list = []
        self.next_id = 0
        self.vserial = ''
        self._reset_derived()

    def _reset_derived(self):
        self.lnames = []; self.blob_cs = None; self.starts = array('q'); self.blob_ids = array('q'); self.blob_t = 0.0
        self.delta = set()
        self.children = None
        self.dir_path_cache = {}
        self.tot_size = None; self.tot_files = None; self.tot_t = 0.0; self.tot_dirty = True

    # --------------------------------------------------------------------------- state for hot update / cache
    def export(self):
        return {k: getattr(self, k) for k in ('key', 'root_path', 'names', 'parent', 'size', 'mtime', 'flags', 'root_id', 'method',
                                               'journal', 'serial', 'state', 'built_t', 'changed_t', 'count_files', 'count_dirs', 'free_ids', 'next_id', 'vserial') if hasattr(self, k)} | {'scan_took': getattr(self, 'scan_took', 0)}

    @classmethod
    def from_state(cls, d):
        v = cls(d['key'], d['root_path'])
        for k, val in d.items():
            if k in ('key', 'root_path'): continue
            setattr(v, k, val)
        if v.state == 'building': v.state = 'empty'
        v._reset_derived()
        return v

    def cache_file(self):
        safe = re.sub(r'[^A-Za-z0-9_.-]+', '_', self.key.strip('\\/:') or 'root')
        return INDEX_DIR / f'{safe}.pkl'

    def save(self):
        with self.lock:
            d = self.export(); d['v'] = 1
            data = pickle.dumps(d, protocol=pickle.HIGHEST_PROTOCOL)
        tmp = self.cache_file().with_suffix('.tmp')
        tmp.write_bytes(data); os.replace(tmp, self.cache_file())
        self.saved_t = time.time()

    @classmethod
    def load(cls, key, root_path):
        f = cls(key, root_path).cache_file()
        if not f.exists(): return None
        try:
            d = pickle.loads(f.read_bytes())
            if d.get('v') != 1 or d.get('key') != key: return None
            d['state'] = 'ready'
            return cls.from_state(d)
        except Exception:
            return None

    # --------------------------------------------------------------------------- building blocks
    def _ensure(self, i):
        n = len(self.names)
        if i < n: return
        grow = i - n + 1 + 4096
        self.names.extend([None] * grow)
        self.parent.extend([-1] * grow)
        self.size.extend([0] * grow)
        self.mtime.extend([0] * grow)
        self.flags.extend(b'\0' * grow)

    def set_entry(self, i, parent, name, is_dir, size, mtime, attrs=0):
        self._ensure(i)
        was = self.flags[i]
        ch = self.children
        if ch is not None:                                                  # keep the child lists current (no full rebuild)
            old = self.parent[i] if was & F_USED else None
            if old is not None and old != parent:
                lst = ch.get(old)
                if lst: lst.discard(i)
            if (old != parent or not was & F_USED) and i != self.root_id:
                ch.setdefault(parent, set()).add(i)
        if was & F_USED and (was & F_DIR) and (self.parent[i] != parent or self.names[i] != name): self.dir_path_cache = {}
        else: self.dir_path_cache.pop(i, None)                             # a reused id must not keep an old cached path
        self.names[i] = name
        self.parent[i] = parent
        self.size[i] = 0 if is_dir else max(0, int(size or 0))
        self.mtime[i] = int(mtime or 0)
        self.flags[i] = F_USED | (F_DIR if is_dir else 0) | (F_HIDDEN if attrs & 2 else 0) | (F_SYSTEM if attrs & 4 else 0)
        if not was & F_USED:
            if is_dir: self.count_dirs += 1
            else: self.count_files += 1

    def remove_entry(self, i, recursive=True):
        if i >= len(self.flags) or not self.flags[i] & F_USED or i == self.root_id: return
        todo = [i]
        kids = self.get_children() if recursive and self.flags[i] & F_DIR else self.children   # child lists kept current
        while todo:
            j = todo.pop()
            if not self.flags[j] & F_USED: continue
            if self.flags[j] & F_DIR: self.count_dirs -= 1
            else: self.count_files -= 1
            if kids is not None:
                lst = kids.get(self.parent[j])
                if lst: lst.discard(j)
            self.dir_path_cache.pop(j, None)
            self.flags[j] = 0; self.names[j] = None; self.delta.add(j)
            if self.method == 'scan': self.free_ids.append(j)
            if recursive and kids is not None: todo.extend(kids.pop(j, ()))
        self.tot_dirty = True

    def used(self, i):
        return 0 <= i < len(self.flags) and self.flags[i] & F_USED

    # --------------------------------------------------------------------------- paths
    def dir_path(self, i):
        """Full path of folder i (cached). None when the chain is broken (orphan / system metadata)."""
        if i == self.root_id: return self.root_path.rstrip('\\/') or self.root_path
        c = self.dir_path_cache.get(i)
        if c is not None: return c
        chain = []; j = i; guard = 0
        while j != self.root_id:
            if not self.used(j) or guard > 4096: return None
            hit = self.dir_path_cache.get(j)
            if hit is not None:
                base = hit; break
            chain.append(j); j = self.parent[j]; guard += 1
        else:
            base = self.root_path.rstrip('\\/')
        for k in reversed(chain):
            base = base + SEP + self.names[k] if base else SEP + self.names[k]
            if self.flags[k] & F_DIR: self.dir_path_cache[k] = base
        return base

    def path(self, i):
        if i == self.root_id: return self.root_path
        if not self.used(i): return None
        if self.flags[i] & F_DIR: return self.dir_path(i)
        d = self.dir_path(self.parent[i])
        return None if d is None else (d + SEP + self.names[i] if d != SEP else SEP + self.names[i])

    def get_children(self):
        if self.children is None:
            ch = {}; par = self.parent; fl = self.flags
            for i in range(len(fl)):
                if fl[i] & F_USED and i != self.root_id:
                    ch.setdefault(par[i], set()).add(i)
            self.children = ch
        return self.children

    def lookup(self, path):
        """id of a path inside this root, or None."""
        p = norm(path); rp = norm(self.root_path).rstrip('\\/')
        if IS_WIN: p_cmp, rp_cmp = p.lower(), rp.lower()
        else: p_cmp, rp_cmp = p, rp
        if p_cmp.rstrip('\\/') == rp_cmp: return self.root_id
        if not p_cmp.startswith(rp_cmp + SEP) and not (rp_cmp == '' and p_cmp.startswith(SEP)): return None
        parts = [x for x in p[len(rp):].split(SEP) if x]
        kids = self.get_children(); cur = self.root_id
        for part in parts:
            pc = part.lower() if IS_WIN else part
            nxt = None
            for c in tuple(kids.get(cur, ())):
                n = self.names[c]
                if n is not None and (n.lower() if IS_WIN else n) == pc: nxt = c; break
            if nxt is None: return None
            cur = nxt
        return cur

    # --------------------------------------------------------------------------- search structures
    def build_blob(self):
        names = self.names; fl = self.flags
        ids = array('q'); starts = array('q'); parts = []; pos = 0
        for i in range(len(fl)):
            if fl[i] & F_USED and i != self.root_id:
                n = names[i]
                if n is None: continue
                if '\n' in n: n = n.replace('\n', ' ')
                ids.append(i); starts.append(pos); parts.append(n); pos += len(n) + 1
        self.blob_cs = '\n'.join(parts) + '\n'                           # case-sensitive search (rare): find in one string
        self.lnames = [x.lower() for x in parts]                           # the usual search: one list pass (~50 ms / million)
        self.starts = starts; self.blob_ids = ids; self.blob_t = time.time(); self.delta = set()

    def need_blob(self):
        if not self.blob_ids and (self.count_files or self.count_dirs): return True
        return len(self.delta) > 50000 or (self.delta and time.time() - self.blob_t > 60)

    def blob_find(self, s, cs=False):
        if not cs:
            ids = self.blob_ids
            return [ids[k] for k, n in enumerate(self.lnames) if s in n]
        blob = self.blob_cs
        starts = self.starts; ids = self.blob_ids; out = []; find = blob.find; count = blob.count
        n = len(starts); p = find(s); k = 0; last = 0
        while p != -1:                                  # entry number = newlines before the hit (counted in C, hits
            k += count('\n', last, p); last = p         # come in order: one pass over the blob, no bisect per hit)
            out.append(ids[k])
            p = find(s, starts[k + 1] if k + 1 < n else len(blob))
        return out

    def blob_match(self, groups):
        """Ids whose (lower-case) name passes every group. groups = [[(op, value, neg), ...], ...]; a group is true when
        any of its tests is; op: 'in' (part of the name), 'start', 'end', 'ext' (ends with, files only).
        Compiled to one list comprehension (no Python call per name: ~50 ms per million names)."""
        env = {}; conds = []
        for gi, g in enumerate(groups):
            alts = []
            for ti, (op, v, neg) in enumerate(g):
                k = f'v{gi}_{ti}'; env[k] = tuple(v) if isinstance(v, list) else v
                e = {'in': f'{k} in n', 'start': f'n.startswith({k})', 'end': f'n.endswith({k})',
                     'ext': f'(n.endswith({k}) and not F[I[k]] & D)'}[op]
                alts.append(f'not ({e})' if neg else e)
            conds.append('(' + ' or '.join(alts) + ')')
        args = ', '.join(env)                                              # parameters = fast locals inside the loop
        fn = eval(f"lambda L, I, F, D{', ' if args else ''}{args}: [I[k] for k, n in enumerate(L) if {' and '.join(conds)}]",
                  {'__builtins__': {'enumerate': enumerate}})
        return fn(self.lnames, self.blob_ids, self.flags, F_DIR, *env.values())

    # --------------------------------------------------------------------------- folder sizes
    def totals(self, max_age=60.0, wait=False):
        """(tot_size, tot_files): whole-subtree size / file count of every folder.
        Fresh enough -> cached. Stale -> the old arrays are returned at once and a recount runs in the background
        (a busy C: drive changes all the time; recounting 2 million entries costs a few seconds of CPU)."""
        ts = self.tot_size
        stale = ts is None or (self.tot_dirty and time.time() - self.tot_t > max_age)
        if not stale and len(ts) == len(self.flags): return ts, self.tot_files
        if ts is not None and not wait:
            if not getattr(self, '_tot_running', False):
                self._tot_running = True
                threading.Thread(target=self._totals_bg, name='HZ-Totals', daemon=True).start()
            return ts, self.tot_files
        return self._compute_totals()

    def _totals_bg(self):
        try: self._compute_totals()
        finally: self._tot_running = False

    def _compute_totals(self):
        """Lock-free: the arrays only grow and every index is bounds-checked; a change during the count only
        makes the result a moment old, it is recounted on the next request."""
        self.tot_dirty = False; t0 = time.time()
        n = len(self.flags); fl = self.flags; par = self.parent; sz = self.size
        depth = array('i', [-1]) * n                     # -1 unknown, -2 orphan (chain does not reach the root)
        if self.root_id < n: depth[self.root_id] = 0
        for i in range(n):
            if not fl[i] & F_USED or depth[i] != -1: continue
            chain = []; j = i
            while True:
                if j < 0 or j >= n or not fl[j] & F_USED: d = -2; break
                if depth[j] != -1: d = depth[j]; break
                if len(chain) > 4096: d = -2; break
                chain.append(j); j = par[j]
            for k in reversed(chain):
                if d == -2: depth[k] = -2
                else: d += 1; depth[k] = d
        buckets = {}
        for i in range(n):
            d = depth[i]
            if d > 0: buckets.setdefault(d, []).append(i)
        ts = array('q', sz[:n]); tf = array('q', [0]) * n
        for i in range(n):
            if fl[i] & F_USED and not fl[i] & F_DIR: tf[i] = 1
            if not fl[i] & F_USED: ts[i] = 0
        for i in getattr(self, 'linkdup', None) or ():
            if i < n: ts[i] = 0
        for d in sorted(buckets, reverse=True):
            for i in buckets[d]:
                p = par[i]
                if 0 <= p < n: ts[p] += ts[i]; tf[p] += tf[i]
        self.tot_size, self.tot_files, self.tot_t = ts, tf, t0
        return ts, tf

    def dirty(self, i=None, structure=False):
        self.changed_t = time.time(); self.tot_dirty = True
        if i is not None:
            self.delta.add(i)
            ld = getattr(self, 'linkdup', None)
            if ld: ld.discard(i)                         # a slot that changed is no longer a known second link
        if structure:
            self.children = None; self.dir_path_cache = {}
            if getattr(self, 'linkdup', None): self.linkdup = set()      # unsure now: count every name (never hide bytes)


# ============================================================================================ builders
def build_scan(vi: VolumeIndex, exclude=(), stop=None, progress=None):
    """Fill vi by walking the folders (works everywhere). Returns a NEW VolumeIndex (swap when done)."""
    new = VolumeIndex(vi.key, vi.root_path)
    new.method = 'scan'; new.serial = vi.serial
    root = vi.root_path
    try: st = os.stat(root); rmt = int(st.st_mtime)
    except OSError: rmt = 0
    new.set_entry(0, -1, '', True, 0, rmt); new.root_id = 0; new.count_dirs = 0
    excl = {e.lower() for e in exclude}
    nxt = 1; stack = [(root, 0)]; seen = 0; t0 = time.time()
    bad = set(); links = set(); linkdup = set()                                           # folders that could not be read (fully)
    while stack:
        if stop is not None and stop.is_set(): return None
        d, did = stack.pop()
        try:
            it = os.scandir(W.lp(d) if IS_WIN else d)
        except OSError:
            bad.add(did); continue
        with it:
            while True:
                try: e = next(it)                                        # listing itself can fail half way (access denied)
                except StopIteration: break
                except OSError: bad.add(did); break
                try:
                    name = e.name
                    if name.lower() in excl: continue
                    st = e.stat(follow_symlinks=False)
                    attrs = getattr(st, 'st_file_attributes', 0)
                    is_link = e.is_symlink() or bool(attrs & 0x400)
                    is_dir = e.is_dir(follow_symlinks=False) and not is_link
                    if IS_WIN and not attrs and name.startswith('.'): attrs = 0
                    if not IS_WIN and name.startswith('.'): attrs |= 2
                    if not is_dir and getattr(st, 'st_nlink', 1) > 1 and st.st_ino:   # hard links: folder totals count
                        k = (st.st_dev, st.st_ino)                                 #  the bytes once (search still sees
                        if k in links: linkdup.add(nxt)                            #  each name with its real size)
                        else: links.add(k)
                    new.set_entry(nxt, did, name, is_dir, 0 if is_dir else st.st_size, st.st_mtime, attrs)
                    if is_dir: stack.append((os.path.join(d, name), nxt))
                    nxt += 1; seen += 1
                except OSError:
                    continue
        if progress and seen and time.time() - t0 > 0.5:
            progress(seen); t0 = time.time()
    del new.names[nxt:]; del new.parent[nxt:]; del new.size[nxt:]; del new.mtime[nxt:]; del new.flags[nxt:]
    new.next_id = nxt; new.bad = bad; new.linkdup = linkdup
    new.state = 'ready'; new.built_t = time.time(); new.changed_t = new.built_t
    return new


def build_mft(vi: VolumeIndex, stop=None, progress=None):
    import hz_ntfs as N
    new = VolumeIndex(vi.key, vi.root_path)
    new.method = 'mft'; new.root_id = 5
    with N.NtfsVolume(vi.key) as vol:
        new.serial = '%016X' % (vol.vd['serial'] & 0xFFFFFFFFFFFFFFFF)
        j, err = vol.usn_query()
        if j is None and err == N.ERROR_JOURNAL_NOT_ACTIVE:
            vol.usn_create(); j, err = vol.usn_query()
        new._ensure(vol.vd['mft_valid'] // max(1, vol.vd['frs_size']))
        for rn, parent, name, is_dir, size, mt, attrs in N.iter_mft(vol, progress=progress, stop=stop):
            if rn == 5:
                new.set_entry(5, -1, '', True, 0, mt, attrs); continue
            if parent == 11: continue                                  # $Extend metadata
            new.set_entry(rn, parent, name, is_dir, size, mt, attrs)
        if stop is not None and stop.is_set(): return None
        if not new.used(5): new.set_entry(5, -1, '', True, 0, 0)
        new.count_dirs = max(0, new.count_dirs - 1)                      # the root itself
        new.journal = {'id': j['id'], 'next': j['next']} if j else None
    while new.names and new.names[-1] is None and len(new.names) > 6:   # trim the tail we pre-grew
        new.names.pop(); new.parent.pop(); new.size.pop(); new.mtime.pop(); new.flags.pop()
    new.state = 'ready'; new.built_t = time.time(); new.changed_t = new.built_t
    return new


def apply_usn(vi: VolumeIndex, records):
    """Apply USN records to an MFT-built index. Returns the ids whose size / time should be re-read."""
    import hz_ntfs as N
    need = set(); structure = False
    with vi.lock:
        for frn, pfrn, reason, attrs, name, ts in records:
            if reason & N.USN_REASON_DELETE:
                if vi.used(frn): vi.remove_entry(frn, recursive=False); structure = True
                need.discard(frn); continue
            if reason & N.USN_REASON_RENAME_OLD and not reason & N.USN_REASON_RENAME_NEW:
                continue
            if pfrn == 11: continue
            if frn == vi.root_id:
                if ts: vi.mtime[frn] = N.filetime_to_unix(ts)
                continue
            is_dir = bool(attrs & 0x10)
            if not vi.used(frn) or vi.names[frn] != name or vi.parent[frn] != pfrn:
                old_size = vi.size[frn] if vi.used(frn) else 0
                vi.set_entry(frn, pfrn, name, is_dir, old_size, ts and N.filetime_to_unix(ts), attrs)
                vi.delta.add(frn); structure = True
            if not is_dir and reason & (N.USN_REASON_DATA | N.USN_REASON_CREATE | N.USN_REASON_BASIC | N.USN_REASON_RENAME_NEW):
                need.add(frn)
            elif is_dir and ts:
                vi.mtime[frn] = N.filetime_to_unix(ts)
        if records: vi.dirty(structure=structure)
    return need


def restat(vi: VolumeIndex, ids, limit=3000):
    done = 0
    for i in list(ids)[:limit]:
        p = vi.path(i)
        if not p: continue
        try: st = os.stat(W.lp(p) if IS_WIN else p)
        except OSError: continue
        with vi.lock:
            if vi.used(i):
                if not vi.flags[i] & F_DIR: vi.size[i] = st.st_size
                vi.mtime[i] = int(st.st_mtime)
        done += 1
    if done: vi.dirty()


# ============================================================================================ query
def parse_size(v):
    v = v.strip().lower()
    if v in SIZE_WORDS: return SIZE_WORDS[v]
    num = r'(\d+(?:\.\d+)?|\.\d+)'
    m = re.fullmatch(r'(>=|<=|>|<|=)?\s*' + num + r'?\s*([kmgt]?b?)?(?:\.\.' + num + r'?\s*([kmgt]?b?)?)?', v)
    if not m or (m.group(2) is None and m.group(4) is None) or (m.group(2) is None and '..' not in v):
        raise QueryError(f'看不懂大小：{v}（例：size:>1gb、size:100mb..2gb、size:..5mb）')
    op, a, ua, b, ub = m.groups()
    x = int(float(a) * SIZE_UNITS.get(ua or '', 1)) if a is not None else 0
    if '..' in v:                                                        # a..b, a.. (from a), ..b (up to b)
        y = int(float(b) * SIZE_UNITS.get(ub or ua or '', 1)) if b is not None else 1 << 62
        if y < x: raise QueryError(f'大小範圍反了：{v}')
        return (x, y)
    if op in ('>', '>='): return (x + (1 if op == '>' else 0), 1 << 62)
    if op in ('<', '<='): return (0, x - (1 if op == '<' else 0))
    if op == '=': return (x, x)
    return (x, 1 << 62)


def _day(d): return datetime(d.year, d.month, d.day)


def parse_date(v, now=None):
    """-> (t0, t1) unix seconds, inclusive start, exclusive end."""
    now = now or datetime.now(); v = v.strip().lower()
    today = _day(now)
    words = {'today': (today, today + timedelta(days=1)), '今天': (today, today + timedelta(days=1)),
             'yesterday': (today - timedelta(days=1), today), '昨天': (today - timedelta(days=1), today)}
    wk = today - timedelta(days=today.weekday())
    words.update({'thisweek': (wk, wk + timedelta(days=7)), '本週': (wk, wk + timedelta(days=7)), 'lastweek': (wk - timedelta(days=7), wk)})
    mo = datetime(today.year, today.month, 1)
    nmo = datetime(mo.year + (mo.month == 12), mo.month % 12 + 1, 1)
    pmo = datetime(mo.year - (mo.month == 1), (mo.month - 2) % 12 + 1, 1)
    words.update({'thismonth': (mo, nmo), '本月': (mo, nmo), 'lastmonth': (pmo, mo)})
    yr = datetime(today.year, 1, 1)
    words.update({'thisyear': (yr, datetime(today.year + 1, 1, 1)), '今年': (yr, datetime(today.year + 1, 1, 1)),
                  'lastyear': (datetime(today.year - 1, 1, 1), yr)})
    if v in words:
        a, b = words[v]; return a.timestamp(), b.timestamp()
    m = re.fullmatch(r'last(\d+)(hours?|days?|weeks?|months?|years?)', v) or re.fullmatch(r'past(\d+)(hours?|days?|weeks?|months?|years?)', v)
    if m:
        n = int(m.group(1)); u = m.group(2).rstrip('s')
        sec = {'hour': 3600, 'day': 86400, 'week': 7 * 86400, 'month': 30 * 86400, 'year': 365 * 86400}[u]
        return now.timestamp() - n * sec, now.timestamp() + 1

    def one(s, end=False):
        s = s.strip()
        for fmt, step in (('%Y-%m-%d', 'd'), ('%Y/%m/%d', 'd'), ('%Y-%m', 'm'), ('%Y/%m', 'm'), ('%Y', 'y')):
            try: d = datetime.strptime(s, fmt)
            except ValueError: continue
            if not end: return d
            if step == 'd': return d + timedelta(days=1)
            if step == 'm': return datetime(d.year + (d.month == 12), d.month % 12 + 1, 1)
            return datetime(d.year + 1, 1, 1)
        raise QueryError(f'看不懂日期：{s}')
    if '..' in v:
        a, b = v.split('..', 1)
        t0 = one(a).timestamp() if a.strip() else 0                     # 2026-01..  /  ..2026-03
        t1 = one(b, True).timestamp() if b.strip() else 1 << 40
        if t1 <= t0: raise QueryError(f'日期範圍反了：{v}')
        return t0, t1
    m = re.fullmatch(r'(>=|<=|>|<)(.+)', v)
    if m:
        op, s = m.groups()
        if op == '>': return one(s, True).timestamp(), 1 << 40
        if op == '>=': return one(s).timestamp(), 1 << 40
        if op == '<': return 0, one(s).timestamp()
        return 0, one(s, True).timestamp()
    return one(v).timestamp(), one(v, True).timestamp()


class Wild:
    """* and ? on a whole name without backtracking blow-ups (as a regex, '*a*a*a*a*b' on one long name took
    45 s while holding the index lock). Greedy two-pointer match: at most len(pattern) x len(name) steps."""
    __slots__ = ('p', 'cs')
    def __init__(self, pat, cs=False): self.cs = cs; self.p = pat if cs else pat.lower()
    def fullmatch(self, name):
        p = self.p; s = name if self.cs else name.lower()
        i = j = 0; star = -1; mark = 0; n, m = len(s), len(p)
        while i < n:
            if j < m and (p[j] == '?' or p[j] == s[i]): i += 1; j += 1
            elif j < m and p[j] == '*': star = j; mark = i; j += 1
            elif star >= 0: j = star + 1; mark += 1; i = mark
            else: return False
        while j < m and p[j] == '*': j += 1
        return j == m


RX_ERR = {'unterminated character set': '[ 沒有對應的 ]', 'missing ), unterminated subpattern': '( 沒有對應的 )',
          'unbalanced parenthesis': ') 沒有對應的 (', 'nothing to repeat': '* + ? 前面沒有東西可以重複',
          'multiple repeat': '重複符號連在一起', 'bad escape (end of pattern)': '最後的 \\ 後面少了字'}
_NESTED = re.compile(r'\((?:[^()\\]|\\.)*(?:[+*}]|\|)(?:[^()\\]|\\.)*\)\s*(?:[+*]|\{\d*,)')


def safe_regex(val, flags):
    """Python's regex cannot be stopped once it runs (and it holds the interpreter): refuse the patterns that can take
    exponential time - a repeated group that itself repeats or alternates, e.g. (a+)+  (a|aa)*  (\\w+\\s?)+ - and
    back-references."""
    if _NESTED.search(val) or re.search(r'\\[1-9]|\(\?P=', val):
        raise QueryError('這個正規表達式可能讓搜尋卡住很久（重複裡面又有重複／選擇），請改寫，例如把 (a+)+ 改成 a+')
    if len(val) > 500: raise QueryError('正規表達式太長')
    bare = re.sub(r'\\.|\[(?:\\.|[^\]])*\]', 'x', val)                  # escapes and [classes] do not repeat
    if len(re.findall(r'[*+]|\{\d*,\}', bare)) > 4:                     # .*.*.*.*.* is n^5 on a long name
        raise QueryError('這個正規表達式的重複（* +）太多，可能讓搜尋卡住很久，請精簡')
    try: return re.compile(val, flags)
    except re.error as e: raise QueryError(f'正規表達式寫錯了（第 {e.pos + 1 if e.pos is not None else "?"} 個字附近）：{RX_ERR.get(e.msg.split(" at ")[0], e.msg)}')


def wild_to_rx(s):
    out = ''
    for ch in s:
        out += '.*' if ch == '*' else '.' if ch == '?' else re.escape(ch)
    return out


def tokenize(q):
    """Words separated by spaces; "quoted" keeps spaces; returns list of raw tokens."""
    toks = []; cur = ''; quoted = False; i = 0
    while i < len(q):
        ch = q[i]
        if ch == '"': quoted = not quoted; cur += ch
        elif ch.isspace() and not quoted:
            if cur: toks.append(cur); cur = ''
        else: cur += ch
        i += 1
    if cur: toks.append(cur)
    return toks


class Term:
    __slots__ = ('kind', 'neg', 'v', 'rx', 'cs', 'lit')

    def __init__(self, kind, v=None, neg=False, cs=False):
        self.kind = kind; self.v = v; self.neg = neg; self.cs = cs; self.rx = None; self.lit = None


def parse_atom(tok, hot_folders=()):
    neg = False
    while tok.startswith('!'): neg = not neg; tok = tok[1:]
    if not tok: return None
    fw = re.match(r'^([Ａ-Ｚａ-ｚa-zA-Z\u4e00-\u9fff]+)[：:]', tok)
    if fw and (re.search(r'[Ａ-Ｚａ-ｚ]', fw.group(1)) or '：' in fw.group(0)):    # ｅｘｔ：jpg (full-width typing)
        tok = unicodedata.normalize('NFKC', fw.group(1)) + ':' + tok[fw.end():]
    m = re.match(r'^([a-zA-Z\u4e00-\u9fff]+):(.*)$', tok, re.S)
    if m and not (len(m.group(1)) == 1 and IS_WIN):                   # 'K:\x' is a path, not a modifier
        mod, val = m.group(1).lower(), m.group(2).strip('"')
        mod = TYPE_ALIAS.get(mod, mod)
        if mod in TYPE_EXT:
            t = Term('ext', set(TYPE_EXT[mod].split()), neg)
            if val: return [t, parse_atom(('!' if neg else '') + val, hot_folders)]
            return t
        if mod in ('ext', '副檔名'):
            return Term('ext', {e.strip('. ').lower() for e in re.split(r'[;,|]', val) if e.strip('. ')}, neg)
        if mod in ('size', '大小'): return Term('size', parse_size(val), neg)
        if mod in ('dm', 'datemodified', '日期', '修改'): return Term('dm', parse_date(val), neg)
        if mod in ('file', 'files', '檔案'):
            t = Term('isfile', None, neg); return [t, parse_atom(val, hot_folders)] if val else t
        if mod in ('folder', 'folders', 'dir', '資料夾'):
            t = Term('isdir', None, neg); return [t, parse_atom(val, hot_folders)] if val else t
        if mod == 'regex':
            t = Term('regex', val, neg); t.rx = safe_regex(val, re.I); return t
        if mod == 'case':
            t = parse_atom(val, hot_folders)
            if isinstance(t, Term):
                t.cs = True; t.neg = t.neg ^ neg
                if t.kind == 'regex': t.rx = safe_regex(t.v, 0)                  # (case: was ignored for regex:)
                if t.kind == 'wild': t.rx = Wild(t.v, True)
            return t
        if mod in ('path', '路徑'): return Term('path', val, neg)
        if mod == 'parent': return Term('parent', norm(val) if val else '', neg)
        if mod in ('infolder', 'in', '在'): return Term('infolder', norm(val) if val else '', neg)
        if mod in ('hot', '熱'): return Term('hot', list(hot_folders), neg)
        if mod in ('dupe', '同名', '重複'):                                   # Everything's dupe: same name somewhere else
            t = Term('dupe', None, False); return [t, parse_atom(val, hot_folders)] if val else t
        if mod in ('sizedupe', '同大小'):
            t = Term('sizedupe', None, False); return [t, parse_atom(val, hot_folders)] if val else t
        if mod in ('empty', '空'): return Term('empty', None, neg)
        # unknown modifier: treat the whole thing as text
    text = tok
    if text.startswith('"') and text.endswith('"') and len(text) >= 2: text = text[1:-1]
    else: text = text.replace('"', '')
    if not text: return None
    if '\\' in text or '/' in text:
        return Term('path', text, neg)
    if '*' in text or '?' in text:
        t = Term('wild', text, neg); t.rx = Wild(text)
        lits = [x for x in re.split(r'[*?]+', text) if x]
        t.lit = max(lits, key=len).lower() if lits else None
        return t
    return Term('sub', text, neg)


def parse_query(q, hot_folders=()):
    """-> list of AND groups; each group = list of OR'ed Terms."""
    groups = []
    for tok in tokenize(q.strip()):
        alts = []
        parts = [tok] if re.match(r'^!*(?:case:)?regex:', tok, re.I) else re.split(r'\|(?=(?:[^"]*"[^"]*")*[^"]*$)', tok)   # (a|b) is regex
        for part in parts:
            if not part: continue
            a = parse_atom(part, hot_folders)
            if a is None: continue
            if isinstance(a, list):
                for x in a:
                    if x is not None: groups.append([x])
                continue
            alts.append(a)
        if alts: groups.append(alts)
    return groups


class Searcher:
    """Evaluate a parsed query on one VolumeIndex."""
    def __init__(self, vi: VolumeIndex, groups, scope_ids=None):
        self.vi = vi; self.groups = groups; self.scope = scope_ids
        self._sets = {}; self.exact = ()               # groups the anchor already proved for every candidate

    def _path_l(self, i):
        p = self.vi.path(i)
        return p if p is None else p.lower()

    def term_ok(self, t: Term, i):
        vi = self.vi; fl = vi.flags[i]
        k = t.kind; r = False
        if k == 'sub':
            n = vi.names[i] or ''
            r = (t.v in n) if t.cs else (t.v.lower() in n.lower())
        elif k == 'wild':
            r = t.rx.fullmatch(vi.names[i] or '')
        elif k == 'regex':
            r = bool(t.rx.search(vi.names[i] or ''))
        elif k == 'ext':
            n = vi.names[i] or ''
            r = not fl & F_DIR and '.' in n and n.rsplit('.', 1)[1].lower() in t.v
        elif k == 'size':
            r = not fl & F_DIR and t.v[0] <= vi.size[i] <= t.v[1]
        elif k == 'dm':
            r = t.v[0] <= vi.mtime[i] < t.v[1]
        elif k == 'isfile':
            r = not fl & F_DIR
        elif k == 'isdir':
            r = bool(fl & F_DIR)
        elif k == 'path':
            p = vi.path(i) or ''
            v = t.v if t.cs else t.v.lower()
            r = v.replace('/', SEP) in (p if t.cs else p.lower())
        elif k == 'parent':
            pid = self._sets.setdefault(('parent', t.v), vi.lookup(t.v))
            r = pid is not None and vi.parent[i] == pid
        elif k in ('infolder', 'hot'):
            s = self._sub_set(t)
            r = i in s
        elif k == 'empty':
            r = bool(fl & F_DIR) and not vi.get_children().get(i)
        return r != t.neg

    def _sub_set(self, t):
        key = (t.kind, str(t.v))
        s = self._sets.get(key)
        if s is None:
            s = set(); vi = self.vi; kids = vi.get_children()
            roots = [t.v] if t.kind == 'infolder' else list(t.v or [])
            for r in roots:
                rid = vi.lookup(r) if r else None
                if rid is None: continue
                stack = [rid]
                while stack:
                    j = stack.pop(); s.add(j); stack.extend(kids.get(j, ()))
                if t.kind == 'infolder': s.discard(rid)
            self._sets[key] = s
        return s

    @staticmethod
    def fast_test(t):
        """(op, value, neg) when the term can be tested on the lower-case name alone, else None."""
        if t.cs: return None
        if t.kind == 'sub' and t.v: return ('in', t.v.lower(), t.neg)
        if t.kind == 'ext' and t.v: return ('ext', ['.' + e.lower() for e in t.v], t.neg)
        if t.kind == 'wild' and '?' not in t.v:
            parts = t.v.lower().split('*')
            if len(parts) == 2 and parts[0] and not parts[1]: return ('start', parts[0], t.neg)       # abc*
            if len(parts) == 2 and parts[1] and not parts[0]: return ('end', parts[1], t.neg)         # *.psd
            if len(parts) == 3 and parts[1] and not parts[0] and not parts[2]: return ('in', parts[1], t.neg)   # *abc*
        return None

    def blob_groups(self):
        """Groups whose every term can be tested on the name alone (the usual search): all of them are tested in ONE
        pass over the name list, instead of testing candidates one by one in Python."""
        out = []
        for g in self.groups:
            tests = [self.fast_test(t) for t in g]
            if g and all(tests): out.append((g, tests))
        return out

    def anchor(self):
        """Pick the cheapest positive term group to produce candidates. -> list(ids) or None (= everything)."""
        vi = self.vi; best = None
        bg = self.blob_groups()
        if bg and any(not t.neg for g, _ in bg for t in g):                 # at least one positive test to narrow down
            out = set(vi.blob_match([tests for _g, tests in bg]))
            self.exact = tuple(g for g, _ in bg)
            out.difference_update(vi.delta)                                 # renamed since the blob: checked one by one
            out.update(i for i in vi.delta if vi.used(i))
            return out
        for g in self.groups:
            if any(t.neg for t in g): continue
            score = None
            kinds = {t.kind for t in g}
            if kinds <= {'sub', 'wild', 'ext'}:
                score = 0
                for t in g:
                    if t.kind == 'sub': score += max(1, 8 - len(t.v))
                    elif t.kind == 'wild': score += 3 if t.lit else 100
                    else: score += 2
                if any(t.kind == 'wild' and not t.lit for t in g): score = None
            elif kinds == {'parent'}: score = -1
            elif kinds <= {'infolder', 'hot'}: score = 20
            if score is not None and (best is None or score < best[0]): best = (score, g)
        if best is None: return None
        g = best[1]; out = set()
        for t in g:
            if t.kind == 'sub':
                out.update(vi.blob_find(t.v if t.cs else t.v.lower(), cs=t.cs))
            elif t.kind == 'wild':
                out.update(vi.blob_find(t.lit))
            elif t.kind == 'ext':
                out.update(vi.blob_match([([], ['.' + e.lower() for e in t.v])]))
            elif t.kind == 'parent':
                pid = vi.lookup(t.v)
                if pid is not None: out.update(vi.get_children().get(pid, ()))
            elif t.kind in ('infolder', 'hot'):
                out.update(self._sub_set(t))
        if all(t.kind in ('sub', 'wild', 'ext') for t in g):               # names changed after the blob was built: check them directly
            out.difference_update(vi.delta)
            out.update(i for i in vi.delta if vi.used(i))
        return out

    def run(self):
        vi = self.vi
        cand = self.anchor()
        if cand is None:
            fl = vi.flags
            cand = (i for i in range(len(fl)) if fl[i] & F_USED and i != vi.root_id)
        groups = self.groups; scope = self.scope; out = []
        ex = self.exact; rest = [g for g in groups if not any(g is e for e in ex)]; delta = vi.delta; fl = vi.flags; root = vi.root_id
        for i in cand:
            if not fl[i] & F_USED or i == root: continue
            if scope is not None and i not in scope: continue
            ok = True
            for g in (rest if ex and i not in delta else groups):
                if not any(self.term_ok(t, i) for t in g): ok = False; break
            if ok: out.append(i)
        return out


# ============================================================================================ manager
class IndexManager:
    def __init__(self, settings, log, drives, hot_folders_fn=lambda: []):
        self.S = settings; self.log = log; self.drives = drives; self.hot_folders = hot_folders_fn
        self.vols: dict[str, VolumeIndex] = {}
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.th = None
        self.stop_ev = threading.Event()
        self.building = None

    # --------------------------------------------------------------------------- hot update
    def export_state(self):
        with self.lock:
            return {'vols': {k: v.export() for k, v in self.vols.items()}}

    def adopt(self, st):
        for k, d in (st or {}).get('vols', {}).items():
            try: self.vols[k] = VolumeIndex.from_state(d)
            except Exception: self.log.exc('index', 'adopt ' + k)

    # --------------------------------------------------------------------------- roots
    def wanted_roots(self):
        """[(key, root_path, method_hint)]"""
        want = self.S.get('index.drives') or []
        snap = self.drives.snapshot()
        out = []
        if want:
            for w in want:
                w = str(w)
                if IS_WIN and re.fullmatch(r'[A-Za-z]:\\?', w): out.append((w[:2].upper(), w[:2].upper() + '\\'))
                else: out.append((norm(w), norm(w)))
        elif IS_WIN:
            for v in snap['vols']:
                if v.get('type') in ('fixed', 'removable') and v.get('ok') and v.get('fs', '').upper() in ('NTFS', 'REFS', 'EXFAT', 'FAT32', 'FAT'):
                    out.append((v['letter'], v['letter'] + '\\'))
        return out

    def start(self):
        self.th = threading.Thread(target=self._loop, name='HZ-Index', daemon=True)
        self.th.start()
        self.th2 = threading.Thread(target=self._usn_loop, name='HZ-IndexLive', daemon=True)
        self.th2.start()
        return self

    def stop(self, save=True):
        self.stop_ev.set(); self.wake.set()
        for t in (getattr(self, 'th', None), getattr(self, 'th2', None)):
            if t is not None: t.join(timeout=5)
        if save:
            for v in list(self.vols.values()):
                if v.state == 'ready' and v.changed_t > v.saved_t:
                    try: v.save()
                    except Exception: self.log.exc('index', 'save ' + v.key)

    def rebuild(self, key=None):
        with self.lock:
            for k, v in self.vols.items():
                if key is None or k == key: v.state = 'empty'; v.built_t = 0
        self.wake.set()

    def _method_for(self, key):
        if not IS_WIN or not re.fullmatch(r'[A-Z]:', key): return 'scan'
        v = self.drives.get(key)
        if (v.get('fs') or '').upper() != 'NTFS' or not W.is_admin(): return 'scan'
        return 'mft'

    def _loop(self):
        if not self.S.get('index.enabled'): self.log.info('index', '索引已關閉'); return
        while not self.stop_ev.is_set():
            try:
                roots = self.wanted_roots()
                with self.lock:
                    for key, rp in roots:
                        if key not in self.vols:
                            vi = VolumeIndex.load(key, rp)
                            cur_serial = self.drives.get(key).get('serial', '') if IS_WIN else ''
                            if vi is not None and vi.method == 'mft' and self._method_for(key) != 'mft': vi = None
                            if vi is not None and cur_serial and vi.vserial and vi.vserial != cur_serial: vi = None   # another disk got this letter
                            self.vols[key] = vi or VolumeIndex(key, rp)
                            if vi is not None: self.log.info('index', f'{key} 從快取載入 {vi.count_files:,} 個檔案、{vi.count_dirs:,} 個資料夾')
                    for k in list(self.vols):
                        if k not in {r[0] for r in roots}: del self.vols[k]
                for key, rp in roots:
                    if self.stop_ev.is_set(): break
                    vi = self.vols.get(key)
                    if vi is None: continue
                    meth = self._method_for(key)
                    # drives without a journal are walked again now and then; a walk that takes long (a big USB disk) is
                    # repeated less often (at most ~2 % of the time), so it does not keep the disk busy
                    every = max(60 * max(1, int(self.S.get('index.rescan_min') or 30)), 50 * getattr(vi, 'scan_took', 0))
                    stale = vi.state != 'ready' or (meth == 'scan' and time.time() - vi.built_t > every)
                    if stale: self._build(key, vi, meth)
                    if vi.need_blob():
                        with vi.lock: vi.build_blob()
                    if vi.state == 'ready' and vi.tot_size is None:
                        vi.totals(wait=True)
                    if vi.state == 'ready' and vi.changed_t > vi.saved_t and time.time() - vi.saved_t > 600:
                        try: vi.save()
                        except Exception: self.log.exc('index', 'save')
            except Exception:
                self.log.exc('index', 'loop')
            self.wake.wait(5.0); self.wake.clear()

    def _build(self, key, vi, meth):
        t0 = time.time(); self.building = key
        prev_state = vi.state
        vi.state = 'building'; vi.progress = 0.0; vi.msg = '讀取 MFT…' if meth == 'mft' else '掃描資料夾…'

        def prog_mft(done, total): vi.progress = done / max(1, total)

        def prog_scan(n): vi.msg = f'掃描資料夾… {n:,} 個'
        try:
            new = None
            if meth == 'mft':
                try: new = build_mft(vi, stop=self.stop_ev, progress=prog_mft)
                except Exception as e:
                    self.log.warn('index', f'{key} 讀 MFT 失敗，改用一般掃描：{e}'); meth = 'scan'
            if meth == 'scan':
                new = build_scan(vi, exclude=self.S.get('index.exclude') or [], stop=self.stop_ev, progress=prog_scan)
            if new is None:
                vi.state = prev_state if prev_state == 'ready' else 'empty'; return
            new.build_blob()
            new.vserial = self.drives.get(key).get('serial', '') if IS_WIN else ''
            new.scan_took = time.time() - t0
            with self.lock:
                self.vols[key] = new
                pend = getattr(self, '_pending', None) or []; self._pending = []
            for p_ in dict.fromkeys(pend): self.touch(p_)                  # what HotZone FM changed while this was built
            new.totals(wait=True)
            try: new.save()
            except Exception: self.log.exc('index', 'save')
            self.log.info('index', f'{key} 索引完成（{"MFT" if meth == "mft" else "掃描"}）：{new.count_files:,} 個檔案、{new.count_dirs:,} 個資料夾，{time.time() - t0:.1f} 秒')
        except Exception as e:
            vi.state = 'error'; vi.msg = str(e); self.log.exc('index', f'{key} 建立索引失敗')
        finally:
            self.building = None

    def _usn_loop(self):
        import hz_ntfs as N
        opened = {}
        while not self.stop_ev.wait(1.0):
            for key, vi in list(self.vols.items()):
                if vi.method != 'mft' or vi.state != 'ready' or not vi.journal: continue
                try:
                    vol = opened.get(key)
                    if vol is None: vol = opened[key] = N.NtfsVolume(key)
                    j, err = vol.usn_query()
                    if j is None or j['id'] != vi.journal['id']:
                        self.log.warn('index', f'{key} 變更日誌重設，重新建立索引'); vi.state = 'empty'; self.wake.set(); continue
                    if vi.journal['next'] < j['first']:
                        self.log.warn('index', f'{key} 變更日誌已覆蓋，重新建立索引'); vi.state = 'empty'; self.wake.set(); continue
                    need = set(); rounds = 0
                    while vi.journal['next'] < j['next'] and rounds < 50:
                        nxt, recs = vol.usn_read(vi.journal['next'], vi.journal['id'])
                        if nxt <= vi.journal['next'] and not recs: break
                        need |= apply_usn(vi, recs)
                        vi.journal['next'] = nxt; rounds += 1
                    if need: restat(vi, need)
                except N.NtfsError as e:
                    if e.code == N.ERROR_JOURNAL_ENTRY_DELETED:
                        vi.state = 'empty'; self.wake.set()
                    try: opened.pop(key).close()
                    except Exception: pass
                except Exception:
                    self.log.exc('index', 'usn ' + key)
                    try: opened.pop(key).close()
                    except Exception: pass
        for v in opened.values():
            try: v.close()
            except Exception: pass

    # --------------------------------------------------------------------------- lookups
    def vol_for(self, path):
        p = norm(path); best = None
        for k, vi in list(self.vols.items()):
            if vi.state != 'ready': continue
            rp = norm(vi.root_path)
            if is_under(p, rp) and (best is None or len(rp) > len(norm(best.root_path))): best = vi
        return best

    def touch(self, path, recursive_new=True):
        """HotZone FM changed `path` itself: update the index now (also for drives without a journal)."""
        vi = self.vol_for(path)
        if vi is None:
            b = self.vols.get(self.building) if self.building else None
            if b is not None and is_under(norm(path), norm(b.root_path)):           # being rebuilt: replay it after the swap
                pend = getattr(self, '_pending', None)
                if pend is None: pend = self._pending = []
                if len(pend) < 200000: pend.append(path)
            return
        if vi.method == 'mft': return                           # MFT drives: the USN journal reports it within a second
        try:
            with vi.lock:
                p = norm(path)
                i = vi.lookup(p)
                exists = os.path.lexists(W.lp(p))                          # long paths: never 'gone' just for being long
                if not exists:
                    if i is not None: vi.remove_entry(i)
                    vi.dirty(); return
                par = vi.lookup(os.path.dirname(p))
                if par is None:                                              # parent folder new too (organise by date):
                    up = os.path.dirname(p)                                  #  add it, with everything inside it
                    if up != p and is_under(up, norm(vi.root_path)) and up != norm(vi.root_path) and recursive_new:
                        self.touch(up)
                    return
                st = os.stat(W.lp(p)); is_dir = os.path.isdir(W.lp(p))
                if i is None:
                    i = vi.free_ids.pop() if vi.free_ids else vi.next_id
                    if i >= vi.next_id: vi.next_id = i + 1
                    vi.set_entry(i, par, os.path.basename(p), is_dir, st.st_size, st.st_mtime, getattr(st, 'st_file_attributes', 0))
                    vi.dirty(i)                                             # set_entry kept the child lists current
                    if is_dir and recursive_new:
                        sub = build_scan(VolumeIndex(vi.key, p), exclude=self.S.get('index.exclude') or [])
                        if sub is not None:
                            remap = {0: i}
                            for j in range(1, len(sub.names)):
                                if not sub.flags[j] & F_USED: continue
                                k = vi.free_ids.pop() if vi.free_ids else vi.next_id
                                if k >= vi.next_id: vi.next_id = k + 1
                                vi._ensure(k); remap[j] = k
                                vi.set_entry(k, remap[sub.parent[j]], sub.names[j], bool(sub.flags[j] & F_DIR), sub.size[j], sub.mtime[j],
                                             (2 if sub.flags[j] & F_HIDDEN else 0) | (4 if sub.flags[j] & F_SYSTEM else 0))
                                vi.delta.add(k)
                            vi.dirty()
                else:
                    nm = os.path.basename(p)
                    if vi.names[i] != nm:                                   # same name but other letter case (Windows)
                        vi.set_entry(i, vi.parent[i], nm, bool(vi.flags[i] & F_DIR), st.st_size, st.st_mtime, getattr(st, 'st_file_attributes', 0))
                    if not is_dir: vi.size[i] = st.st_size
                    vi.mtime[i] = int(st.st_mtime); vi.dirty(i)
        except Exception:
            self.log.exc('index', 'touch ' + str(path))

    def status(self):
        out = []
        for k, v in list(self.vols.items()):
            out.append({'key': k, 'root': v.root_path, 'state': v.state, 'method': v.method, 'files': v.count_files, 'dirs': v.count_dirs,
                        'progress': round(v.progress, 3), 'msg': v.msg, 'built': v.built_t, 'live': bool(v.method == 'mft' and v.journal),
                        'changed': v.changed_t})
        return out

    # --------------------------------------------------------------------------- search
    def search(self, q, scope='', limit=500, offset=0, sort='name', desc=False, dirs_first=False, with_sizes=True):
        t0 = time.time()
        groups = parse_query(q, [h['path'] if isinstance(h, dict) else h for h in self.hot_folders()])
        post = {g[0].kind for g in groups if len(g) == 1 and g[0].kind in ('dupe', 'sizedupe')}
        groups = [g for g in groups if not (len(g) == 1 and g[0].kind in ('dupe', 'sizedupe'))]
        if post: groups.append([Term('isfile')])                           # duplicates are about files
        if scope: groups.append([Term('infolder', norm(scope))])
        if not groups: return {'total': 0, 'items': [], 'ms': 0, 'ready': self._ready_text()}
        rows = []
        for key, vi in list(self.vols.items()):
            if vi.state != 'ready' and not vi.blob_ids: continue
            if scope and not is_under(norm(scope), norm(vi.root_path)) and not is_under(norm(vi.root_path), norm(scope)): continue
            with vi.lock:
                if vi.need_blob() and len(vi.delta) > 50000: vi.build_blob()
                ids = Searcher(vi, groups).run()
                vid = vi.lookup(os.path.join(vi.root_path, '.HotZoneVault'))
                if vid is not None:                                              # the safety vault is not part of search results
                    vs = Searcher(vi, [])._sub_set(Term('infolder', os.path.join(vi.root_path, '.HotZoneVault'))); vs.add(vid)
                    ids = [i for i in ids if i not in vs]
                rows.extend((vi, i) for i in ids)
        if post:                                                            # keep only names / sizes that occur twice or more
            if 'dupe' in post:
                cnt = {}
                for vi, i in rows: k = (vi.names[i] or '').lower(); cnt[k] = cnt.get(k, 0) + 1
                rows = [r for r in rows if cnt[(r[0].names[r[1]] or '').lower()] > 1]
            if 'sizedupe' in post:
                cnt = {}
                for vi, i in rows: cnt[vi.size[i]] = cnt.get(vi.size[i], 0) + 1
                rows = [r for r in rows if r[0].size[r[1]] > 0 and cnt[r[0].size[r[1]]] > 1]
            if sort == 'name' or not sort: sort = 'dupe_size' if 'sizedupe' in post and 'dupe' not in post else 'name'
        total = len(rows)
        keyf = self._sort_key(sort)
        try:
            want = offset + limit
            if not dirs_first and len(rows) > 4 * want:                   # 1M matches: only the page is ordered
                import heapq                                                #  (a full sort took 1-3 s per keystroke)
                rows = (heapq.nlargest if desc else heapq.nsmallest)(want, rows, key=keyf)
            else:
                rows.sort(key=keyf, reverse=desc)
            if dirs_first:
                rows = [r for r in rows if r[0].flags[r[1]] & F_DIR] + [r for r in rows if not r[0].flags[r[1]] & F_DIR]
        except Exception:
            self.log.exc('index', 'sort')
        items = [self._item(vi, i, with_sizes) for vi, i in rows[offset:offset + limit]]
        items = [x for x in items if x]
        return {'total': total, 'items': items, 'ms': int((time.time() - t0) * 1000), 'ready': self._ready_text()}

    def _ready_text(self):
        bad = [f'{v.key} {"建立中" if v.state == "building" else v.state}' for v in self.vols.values() if v.state != 'ready']
        return '、'.join(bad)

    def _sort_key(self, sort):
        if sort == 'size':
            def k(r):
                vi, i = r
                if vi.flags[i] & F_DIR and vi.tot_size is not None and i < len(vi.tot_size): return vi.tot_size[i]
                return vi.size[i]
            return k
        if sort == 'mtime': return lambda r: r[0].mtime[r[1]]
        if sort == 'dupe_size': return lambda r: (-r[0].size[r[1]], (r[0].names[r[1]] or '').lower())
        if sort == 'path': return lambda r: ((r[0].dir_path(r[0].parent[r[1]]) or '').lower(), (r[0].names[r[1]] or '').lower())
        if sort == 'ext': return lambda r: (os.path.splitext(r[0].names[r[1]] or '')[1].lower(), (r[0].names[r[1]] or '').lower())
        return lambda r: (r[0].names[r[1]] or '').lower()

    def _item(self, vi, i, with_sizes=True):
        p = vi.path(i)
        if p is None: return None
        is_dir = bool(vi.flags[i] & F_DIR)
        size = vi.size[i]
        if is_dir and with_sizes and vi.tot_size is not None and i < len(vi.tot_size): size = vi.tot_size[i]
        elif is_dir: size = -1
        return {'path': p, 'name': vi.names[i], 'dir': is_dir, 'size': size, 'mtime': vi.mtime[i], 'hidden': bool(vi.flags[i] & F_HIDDEN)}

    # --------------------------------------------------------------------------- folder sizes (TreeSize)
    def folder_size(self, path):
        vi = self.vol_for(path)
        if vi is None: return None
        i = vi.lookup(path)
        if i is None: return None
        ts, tf = vi.totals()
        if i >= len(ts): ts, tf = vi.totals(wait=True)
        return {'size': ts[i], 'files': tf[i]}

    def sizes_for(self, paths):
        """{path: size} for many folders at once (Explorer list)."""
        out = {}
        by = {}
        for p in paths:
            vi = self.vol_for(p)
            if vi is not None: by.setdefault(id(vi), (vi, []))[1].append(p)
        for vi, ps in by.values():
            ts, tf = vi.totals()
            for p in ps:
                i = vi.lookup(p)
                if i is not None and i < len(ts): out[p] = [ts[i], tf[i]]
        return out

    def tree(self, path, depth=1, max_children=200):
        vi = self.vol_for(path)
        if vi is None: return None
        rid = vi.lookup(path)
        if rid is None: return None
        ts, tf = vi.totals()
        if len(ts) < len(vi.flags): ts, tf = vi.totals(wait=True)
        kids = vi.get_children()

        def node(i, d):
            is_dir = bool(vi.flags[i] & F_DIR)
            n = {'name': vi.names[i] if i != vi.root_id else vi.root_path, 'path': vi.path(i), 'size': ts[i] if is_dir else vi.size[i],
                 'files': tf[i] if is_dir else 1, 'dir': is_dir, 'mtime': vi.mtime[i]}
            if i in bad: n['unreadable'] = True                         # access denied: its size is not known (shown, not 0 B)
            if is_dir and d > 0:
                ch = sorted(kids.get(i, ()), key=lambda c: -(ts[c] if vi.flags[c] & F_DIR else vi.size[c]))
                n['nchildren'] = len(ch)
                shown = ch[:max_children]
                n['children'] = [node(c, d - 1) for c in shown]
                rest = ch[max_children:]
                if rest:
                    n['others'] = {'count': len(rest), 'size': sum(ts[c] if vi.flags[c] & F_DIR else vi.size[c] for c in rest)}
            return n
        bad = getattr(vi, 'bad', None) or set()
        with vi.lock:
            out = node(rid, depth)
        if bad: out['bad_n'] = len(bad)
        return out

    def largest(self, path, n=100, dirs=False):
        vi = self.vol_for(path)
        if vi is None: return []
        rid = vi.lookup(path)
        if rid is None: return []
        import heapq
        kids = vi.get_children(); stack = [rid]; heap = []
        ts, tf = vi.totals(wait=len(vi.tot_size or []) < len(vi.flags)) if dirs else (None, None)
        while stack:
            j = stack.pop()
            for c in tuple(kids.get(j, ())):
                if vi.flags[c] & F_DIR:
                    stack.append(c)
                    if dirs:
                        item = (ts[c], c)
                        if len(heap) < n: heapq.heappush(heap, item)
                        elif item > heap[0]: heapq.heapreplace(heap, item)
                elif not dirs:
                    item = (vi.size[c], c)
                    if len(heap) < n: heapq.heappush(heap, item)
                    elif item > heap[0]: heapq.heapreplace(heap, item)
        return [x for x in (self._item(vi, i) for s, i in sorted(heap, reverse=True)) if x]

    def ext_stats(self, path, top=30):
        vi = self.vol_for(path)
        if vi is None: return []
        rid = vi.lookup(path)
        if rid is None: return []
        kids = vi.get_children(); stack = [rid]; agg = {}
        while stack:
            j = stack.pop()
            for c in tuple(kids.get(j, ())):
                if vi.flags[c] & F_DIR: stack.append(c)
                else:
                    n = vi.names[c] or ''
                    e = n.rsplit('.', 1)[1].lower() if '.' in n[1:] else '(無)'
                    a = agg.setdefault(e, [0, 0]); a[0] += vi.size[c]; a[1] += 1
        rows = sorted(([k, v[0], v[1]] for k, v in agg.items()), key=lambda r: -r[1])
        if len(rows) > top:
            rest = rows[top:]; rows = rows[:top] + [['其他', sum(r[1] for r in rest), sum(r[2] for r in rest)]]
        return rows

    def age_stats(self, path):
        """TreeSize-style 'age of files': size / count by last-modified age, and by year."""
        vi = self.vol_for(path)
        if vi is None: return None
        rid = vi.lookup(path)
        if rid is None: return None
        now = time.time(); D = 86400
        edges = [(7 * D, '7 天內'), (30 * D, '1 個月內'), (91 * D, '3 個月內'), (365 * D, '1 年內'), (730 * D, '1～2 年'), (1826 * D, '2～5 年'), (float('inf'), '5 年以上')]
        buckets = [[lab, 0, 0] for _, lab in edges] + [['日期不明', 0, 0]]
        years = {}
        kids = vi.get_children(); stack = [rid]
        while stack:
            j = stack.pop()
            for c in tuple(kids.get(j, ())):
                if vi.flags[c] & F_DIR: stack.append(c); continue
                mt = vi.mtime[c]; sz = vi.size[c]
                if mt <= 0 or mt > now + 2 * D: b = buckets[-1]
                else:
                    age = now - mt; b = buckets[next(i for i, (e, _) in enumerate(edges) if age < e)]
                    y = time.localtime(mt).tm_year; a = years.setdefault(y, [0, 0]); a[0] += sz; a[1] += 1
                b[1] += sz; b[2] += 1
        return {'buckets': buckets, 'years': sorted(([y, v[0], v[1]] for y, v in years.items()), reverse=True)}

    def subtree_files(self, path):
        """[(path, size, mtime)] of every file under path (hot zone planning). None if not indexed."""
        vi = self.vol_for(path)
        if vi is None: return None
        with vi.lock:
            rid = vi.lookup(path)
            if rid is None: return None
            kids = vi.get_children(); stack = [rid]; out = []
            while stack:
                j = stack.pop()
                for c in tuple(kids.get(j, ())):
                    if vi.flags[c] & F_DIR: stack.append(c)
                    else:
                        p = vi.path(c)
                        if p: out.append((p, vi.size[c], vi.mtime[c]))
            return out

    def frn_paths(self, key, frns):
        """{record number: path} for an MFT-built index (None if the index of that volume is not MFT based)."""
        vi = self.vols.get(key)
        if vi is None or vi.state != 'ready' or getattr(vi, 'method', '') != 'mft': return None
        out = {}
        with vi.lock:
            n = len(vi.flags)
            for i in frns:
                if 0 <= i < n and vi.flags[i] & F_USED and not vi.flags[i] & F_DIR:
                    p = vi.path(i)
                    if p: out[i] = p
        return out

    def all_files(self, key, min_size=0):
        """Every file on a volume (cold-data eviction planning)."""
        vi = self.vols.get(key)
        if vi is None or vi.state != 'ready': return None
        out = []
        with vi.lock:
            fl = vi.flags; sz = vi.size
            for i in range(len(fl)):
                if fl[i] & F_USED and not fl[i] & F_DIR and sz[i] >= min_size:
                    out.append(i)
            return [(vi.path(i), sz[i]) for i in out]

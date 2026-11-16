"""🎞 影片快速分類（不准 import Qt）：一部影片平均切 16 格一次看完 → 按分類按鈕（先記下來，不搬）→ 一個段落後再一次搬檔。

16 格從哪裡來：
  ① SortCut（VS）已經做好的預覽圖：VS 的 Data\\videosift.sqlite3 → files.th_dir 資料夾裡的 s0001.jpg…（每張 th_cols×th_rows 格，每 th_step 秒一格）。
     只讀、不改 VS 的任何東西；從大張裡切出平均分佈的 16 格。
  ② VS 沒有這部：自己用 FFmpeg 跳到 16 個時間點各抓一格，拼成一張 4×4（快取在 Data\\vgrid，下一部會先在背景做好）。
搬檔：只在同一顆硬碟裡搬（瞬間完成），記在 moves 表，「📦 隔離區」頁可以復原。
"""
import os, re, json, time, math, sqlite3, threading
from collections import deque
from pathlib import Path

import fc_fcore as fcore

N_CELLS = 16
COLORS = ['#3b8eea', '#2bb673', '#f0ad4e', '#e5484d', '#c678dd', '#1fb5c9', '#f06ea9', '#e5c07b', '#8f7cf0', '#d19a66', '#98a2b3', '#45d483']
MOVE_DIR = 'FileCompare_分類'
STAY = ('不搬', '原地', '=', 'stay')                                         # 分類的位置填這個＝只記下「看過、分到這類」，檔案留在原處（V0.2.32）
PROB_DIR = 'FileCompare_問題影片'                                       # 跟分類分開：delete（打不開）、check video（部分損毀）、repeat（重複的）
PROB_SUB = {'delete': 'delete', 'check': 'check video', 'repeat': 'repeat'}


def pick_idx(n, k=N_CELLS):
    """n 格裡平均挑 k 格（每一段的中間）."""
    if n <= 0: return []
    if n <= k: return list(range(n))
    return sorted({min(n - 1, int((i + 0.5) * n / k)) for i in range(k)})


class VSort:
    def __init__(self, E, old=None):
        self.E = E; self.lock = threading.RLock()
        self.mv = old.mv if old is not None else {}                     # 搬檔進度（跨熱更新）
        self.vs = {'t': 0, 'db': '', 'path': {}, 'ns': {}, 'err': '', 'n': 0}
        self.pq = deque(); self.pbusy = set(); self.pev = threading.Event()
        self.ready = set(); self.failed = set(); self.want = []; self.st_t = 0          # 16 格做好了／做不出來；want＝你現在這份清單（背景先做這些）
        for i in range(2): threading.Thread(target=self._pre_loop, name=f'VGridPre{i}', daemon=True).start()
        threading.Thread(target=self._fail_fix, name='VGridFailFix', daemon=True).start()

    def _fail_fix(self):
        """V0.2.78：以前 4 秒以下的短片做 16 格都失敗（FFmpeg 參數錯：Result too large）→ 把那些失敗紀錄清掉，背景會重做."""
        try:
            if self.E.cfg.get('vg_fail_fix78'): return
            time.sleep(20); n = 0
            for p in self.gdir().glob('*/*.fail'):
                try:
                    if 'Result too large' in p.read_text(encoding='utf-8', errors='replace'):
                        p.unlink(); n += 1
                        try: self.failed.discard(int(p.stem))
                        except ValueError: pass
                except OSError: pass
            self.E.cfg.set('vg_fail_fix78', True)
            if n: self.E.log.w(f'🎞 修好短片 16 格的問題：{n:,} 部重新做預覽（背景）')
        except Exception: self.E.log.err('🎞 清短片失敗紀錄')

    # ================================================================ SortCut 的資料庫
    def vs_candidates(self):
        root = Path(self.E.root); C = []
        if getattr(self.E, '_vs_root', None): C.append(Path(self.E._vs_root))     # 嵌在 SortCut 裡：自己這套優先
        cfg = str(self.E.cfg.get('vs_root') or '').strip()
        if cfg: C.append(Path(cfg))
        for base in (root.parent, root.parent.parent):
            try: C += [d for d in base.iterdir() if d.is_dir() and d != root]
            except OSError: pass
        if os.name == 'nt':
            for dl in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
                for nm in ('VideoSift', 'VS', 'Tools\\VideoSift', 'Program\\VideoSift'): C.append(Path(f'{dl}:\\{nm}'))
        return C

    def vs_find(self):
        for d in self.vs_candidates():
            for p in (d / 'Data' / 'videosift.sqlite3', d / 'videosift.sqlite3'):
                try:
                    if p.is_file(): return str(p)
                except OSError: pass
        return ''

    def vs_load(self, force=False):
        """VS 有預覽圖的影片：路徑 → 資料（5 分鐘重讀一次）."""
        V = self.vs
        if not force and time.time() - V['t'] < 300: return V
        with self.lock:
            if not force and time.time() - V['t'] < 300: return V
            db = self.vs_find(); P = {}; NS = {}; err = ''
            if db:
                try:
                    con = sqlite3.connect(f'file:{Path(db).as_posix()}?mode=ro', uri=True, timeout=10)
                    try:
                        for r in con.execute("SELECT path, name, size, dur, th_n, th_cols, th_rows, th_step, th_dir FROM files WHERE th_state=2 AND th_n>0 AND th_dir!=''"):
                            d = {'path': r[0], 'dur': r[3] or 0, 'n': int(r[4] or 0), 'cols': int(r[5] or 10), 'rows': int(r[6] or 10), 'step': float(r[7] or 2), 'dir': r[8]}
                            P[str(r[0]).lower()] = d; NS[(str(r[1] or os.path.basename(r[0])).lower(), int(r[2] or 0))] = d
                    finally: con.close()
                except Exception as ex: err = f'讀不到 SortCut 的資料庫：{ex}'
            if db and (db != V.get('db') or not V['n']): self.E.log.w(f'🎞 SortCut 預覽圖：{db or "找不到"}（{len(P):,} 部有 10 秒一張的預覽）' + (f'　{err}' if err else ''))
            self.vs = {'t': time.time(), 'db': db, 'path': P, 'ns': NS, 'err': err, 'n': len(P)}
            return self.vs

    def vs_match(self, f):
        V = self.vs_load(); d = V['path'].get(str(f['path']).lower()) or V['ns'].get((os.path.basename(f['path']).lower(), int(f['size'] or 0)))
        if not d: return None
        S = sorted(Path(d['dir']).glob('s*.jpg')) if os.path.isdir(d['dir']) else []
        return dict(d, sheets=[str(s) for s in S]) if S else None

    # ================================================================ 16 格
    def gdir(self): return self.E.data / 'vgrid'

    def grid(self, fid, build=True):
        """{'ok', 'src': 'vs'／'fc', 'sheets': [路徑], 'cols', 'rows'（大張幾格）, 'cells': [{'s','c','r','t'}], 'ar': 寬/高}."""
        f = self.E.fc_file(fid)
        if not f: return {'ok': False, 'message': '找不到這部影片'}
        if f.get('kind') == 'photo':                                                # 📷 照片模式（V0.1.32）：直接看一張大圖
            w, h = int(f.get('w') or 0), int(f.get('h') or 0)
            return {'ok': True, 'photo': True, 'cells': [], 'ar': round(w / h, 4) if w and h else 1.5}
        d = self.vs_match(f)
        if d and d['n'] < 12: d = None                                              # 短片：VS 10 秒一張只有幾格 → 自己抓滿 16 格
        if d:
            cap = len(d['sheets']) * d['cols'] * d['rows']; n = max(1, min(d['n'], cap)); per = d['cols'] * d['rows']; C = []
            for i in pick_idx(n):
                C.append({'s': i // per, 'c': i % per % d['cols'], 'r': i % per // d['cols'], 't': round(i * d['step'], 1)})
            w, h = fcore.img_dims(d['sheets'][0])
            return {'ok': True, 'src': 'vs', 'sheets': d['sheets'], 'cols': d['cols'], 'rows': d['rows'], 'cells': C, 'ar': (w / d['cols']) / (h / d['rows']) if w and h else 16 / 9,
                    'step': d['step'], 'vs_n': d['n']}
        out = self.gdir() / f'{int(fid) % 100:02d}' / f'{int(fid)}.jpg'; meta = out.with_suffix('.json')
        if not out.exists() and (int(fid) in self.failed or out.with_suffix('.fail').exists()):
            self.failed.add(int(fid)); return {'ok': False, 'fail': True, 'message': '⚠ 沒辦法做預覽（影片可能壞了，或缺 FFmpeg）：按 ▶ 跳過，或到電腦上打開看看'}
        if not out.exists():
            if not build: return {'ok': False, 'pending': True, 'message': '預覽做做中…'}
            self._build(f, out, meta)
        if not out.exists(): return {'ok': False, 'message': '沒辦法做預覽（影片可能壞了，或缺 FFmpeg）'}
        try: M = json.loads(meta.read_text(encoding='utf-8'))
        except Exception: M = {'t': [], 'cols': 4, 'rows': 4}
        cols, rows = M.get('cols', 4), M.get('rows', 4); T = M.get('t') or []
        w, h = fcore.img_dims(str(out))
        return {'ok': True, 'src': 'fc', 'sheets': [str(out)], 'cols': cols, 'rows': rows, 'ar': (w / cols) / (h / rows) if w and h else 16 / 9,
                'cells': [{'s': 0, 'c': i % cols, 'r': i // cols, 't': (T[i] if i < len(T) else 0)} for i in range(min(len(T) or cols * rows, cols * rows))]}

    def _build(self, f, out, meta):
        """VS 沒有的：FFmpeg 跳到 16 個時間點各抓一格（一個指令、只解跳到的那附近）拼成 4×4."""
        ff, fp = self.E.ff()
        if not ff: return
        key = int(f['id'])
        with self.lock:
            if key in self.pbusy: busy = True
            else: busy = False; self.pbusy.add(key)
        if busy:
            for _ in range(600):
                time.sleep(0.1)
                if key not in self.pbusy: return
            return
        try:
            dur = float(f.get('dur') or 0)
            if dur <= 0 and fp:
                try: _rc, dur, _e = fcore.probe_dur(fp, f['path'])
                except Exception: dur = 0
            dur = float(dur or 0); n = N_CELLS if dur >= 4 else (4 if dur > 0 else 1)
            T = [round(dur * (i + 0.5) / n, 2) for i in range(n)] if dur > 0 else [0.0]
            cols = 4 if n >= 4 else 1; rows = max(1, math.ceil(n / cols))
            hh = 180 if (f.get('w') or 16) >= (f.get('h') or 9) else 320
            cmd = [ff, '-hide_banner', '-v', 'error', '-y']
            for t in T: cmd += ['-ss', f'{t:.2f}', '-i', f['path']]
            fc = ''.join(f'[{i}:v:0]scale=-2:{hh},setsar=1,trim=end_frame=1[v{i}];' for i in range(n))
            if n > 1:
                for r in range(rows): fc += ''.join(f'[v{r * cols + c}]' for c in range(cols)) + f'hstack=inputs={cols}[r{r}];'
                fc += ''.join(f'[r{r}]' for r in range(rows)) + (f'vstack=inputs={rows}[o]' if rows > 1 else 'null[o]')   # 只有 1 列（短片 4 格）不能 vstack（V0.2.78）
            else: fc += '[v0]null[o]'
            out.parent.mkdir(parents=True, exist_ok=True); tmp = str(out) + '.tmp.jpg'
            cmd += ['-filter_complex', fc, '-map', '[o]', '-frames:v', '1', '-q:v', '4', tmp]
            rc, _o, e = fcore.run(cmd, 120)
            if (rc != 0 or not os.path.isfile(tmp)) and n > 1:                    # 有一格跳不過去（壞掉的影片）：改成每格分開抓，抓不到的用黑的
                self.E.log.w(f'🎞 16 格一次抓不成功，改成一格一格：{f["path"]}：{(e or "")[-200:]}')
                tmp = self._build_slow(ff, f['path'], T, hh, cols, rows, out) or tmp
            if os.path.isfile(tmp) and os.path.getsize(tmp) > 0:
                os.replace(tmp, str(out)); meta.write_text(json.dumps({'t': T, 'cols': cols, 'rows': rows}), encoding='utf-8'); self.ready.add(key)
            else:
                out.with_suffix('.fail').write_text(time.strftime('%Y-%m-%d %H:%M:%S') + ' ' + str(e or '')[-300:], encoding='utf-8'); self.failed.add(key)
        except Exception: self.E.log.err(f'🎞 做 16 格：{f.get("path")}')
        finally:
            with self.lock: self.pbusy.discard(key)

    def _build_slow(self, ff, path, T, hh, cols, rows, out):
        d = out.parent / (out.stem + '_parts'); d.mkdir(parents=True, exist_ok=True); P = []
        try:
            for i, t in enumerate(T):
                p = d / f'{i:02d}.jpg'
                fcore.run([ff, '-hide_banner', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', path, '-frames:v', '1', '-vf', f'scale=-2:{hh},setsar=1', '-q:v', '4', str(p)], 40)
                P.append(p if p.exists() else None)
            ok = [p for p in P if p]
            if not ok: return None
            w, h = fcore.img_dims(str(ok[0])); w = w or int(hh * 16 / 9); w -= w % 2
            cmd = [ff, '-hide_banner', '-v', 'error', '-y']; fc = ''
            for i, p in enumerate(P):
                if p: cmd += ['-i', str(p)]
                else: cmd += ['-f', 'lavfi', '-i', f'color=c=black:s={w}x{hh}:d=1']              # 抓不到的那格：黑的
                fc += f'[{i}:v]scale={w}:{hh},setsar=1,trim=end_frame=1[v{i}];'
            for r in range(rows): fc += ''.join(f'[v{r * cols + c}]' for c in range(cols)) + f'hstack=inputs={cols}[r{r}];'
            fc += ''.join(f'[r{r}]' for r in range(rows)) + (f'vstack=inputs={rows}[o]' if rows > 1 else 'null[o]')
            tmp = str(out) + '.tmp.jpg'
            fcore.run(cmd + ['-filter_complex', fc, '-map', '[o]', '-frames:v', '1', '-q:v', '4', tmp], 60)
            return tmp if os.path.isfile(tmp) else None
        finally:
            for p in d.glob('*'):
                try: p.unlink()
                except OSError: pass
            try: d.rmdir()
            except OSError: pass

    def prefetch(self, ids):
        """接下來幾部先在背景做好（VS 有的不用做）."""
        for i in list(ids)[:6]:
            i = int(i)
            if i not in self.pq: self.pq.append(i)
        while len(self.pq) > 12: self.pq.popleft()
        self.pev.set()

    def _pre_loop(self):
        while self.E.alive():
            self.pev.wait(2.0); self.pev.clear()
            while self.pq and not self.E.stop_all:
                try: fid = self.pq.popleft()
                except IndexError: break
                try: self.grid(fid, build=True)
                except Exception: self.E.log.err('🎞 先做下一部的 16 格')

    # ================================================================ 分類（先記下來，不搬）
    def cats(self):
        R = [dict(r) for r in self.E.db.q('SELECT id,name,dest,color,ord FROM vc_cat ORDER BY ord, id')]
        C = {r[0]: (r[1], r[2], r[3], r[4]) for r in self.E.db.q('SELECT t.cat, COUNT(*), COALESCE(SUM(t.moved=0),0), COALESCE(SUM(f.size),0), COALESCE(SUM(t.moved=0 AND COALESCE(t.auto,0)=1),0) FROM vc_tag t LEFT JOIN files f ON f.id=t.fid GROUP BY t.cat')}
        for r in R: r['n'], r['wait'], r['b'], r['auto'] = C.get(r['id'], (0, 0, 0, 0))     # auto＝自動標的副本（V0.3.57）
        D = {r[0]: r[1] for r in self.E.db.q("SELECT cat, MAX(dst) FROM vc_tag WHERE moved=1 AND dst!='' GROUP BY cat")}
        for r in R: r['dir'] = self.dest_of(r, D[r['id']]) if D.get(r['id']) else ''         # 分類資料夾（搬過才有；V0.1.90：📂 看）
        return R

    def cat_add(self, name, dest=''):
        name = re.sub(r'[\\/:*?"<>|]', '_', str(name or '').strip())[:40]
        if not name: return {'ok': False, 'message': '分類要有名字'}
        if self.E.db.one('SELECT id FROM vc_cat WHERE name=?', (name,)): return {'ok': False, 'message': f'已經有「{name}」了'}
        o = (self.E.db.one('SELECT COALESCE(MAX(ord),0)+1 FROM vc_cat') or [1])[0]; n = (self.E.db.one('SELECT COUNT(*) FROM vc_cat') or [0])[0]
        self.E.db.x('INSERT INTO vc_cat(name,dest,color,ord,t) VALUES(?,?,?,?,?)', (name, str(dest or '').strip(), COLORS[n % len(COLORS)], o, time.time()))
        self.E.log.w(f'🎞 新增分類：{name}　{dest or "（搬到同一顆硬碟的 " + MOVE_DIR + "）"}'); return {'ok': True, 'message': f'加好了：{name}'}

    def cat_edit(self, cid, name=None, dest=None):
        r = self.E.db.one('SELECT * FROM vc_cat WHERE id=?', (int(cid),))
        if not r: return {'ok': False, 'message': '找不到這個分類'}
        if name is not None:
            name = re.sub(r'[\\/:*?"<>|]', '_', str(name).strip())[:40]
            if not name: return {'ok': False, 'message': '分類要有名字'}
            self.E.db.x('UPDATE vc_cat SET name=? WHERE id=?', (name, int(cid)))
        if dest is not None: self.E.db.x('UPDATE vc_cat SET dest=? WHERE id=?', (str(dest).strip(), int(cid)))
        self.E.log.w(f'🎞 改分類 #{cid}：名字={name} 位置={dest}'); return {'ok': True, 'message': '改好了'}

    def cat_del(self, cid):
        n = (self.E.db.one('SELECT COUNT(*) FROM vc_tag WHERE cat=? AND moved=0', (int(cid),)) or [0])[0]
        self.E.db.x('DELETE FROM vc_tag WHERE cat=? AND moved=0', (int(cid),)); self.E.db.x('DELETE FROM vc_cat WHERE id=?', (int(cid),))
        self.E.log.w(f'🎞 刪掉分類 #{cid}（{n} 部還沒搬的取消分類）'); return {'ok': True, 'message': f'刪掉了（{n} 部還沒搬的變回沒分類）'}

    def cat_merge(self, src, dst):
        """🔀 兩類併成一類（V0.4.50）：還沒搬的改到 dst；規則也改；src 沒有搬過的就刪掉（搬過的檔案已經在 src 的資料夾，留著那一類）."""
        src, dst = int(src), int(dst)
        if src == dst or not self.E.db.one('SELECT id FROM vc_cat WHERE id=?', (src,)) or not self.E.db.one('SELECT id FROM vc_cat WHERE id=?', (dst,)): return {'ok': False, 'message': '分類不對'}
        n = (self.E.db.one('SELECT COUNT(*) FROM vc_tag WHERE cat=? AND moved=0', (src,)) or [0])[0]
        self.E.db.x('UPDATE vc_tag SET cat=? WHERE cat=? AND moved=0', (dst, src))
        R = self.E.cfg.get('vc_rules') or []
        if any(int(c) == src for _w, c in R): self.E.cfg.set('vc_rules', [[w, dst if int(c) == src else int(c)] for w, c in R])
        mv = (self.E.db.one('SELECT COUNT(*) FROM vc_tag WHERE cat=?', (src,)) or [0])[0]
        if not mv: self.E.db.x('DELETE FROM vc_cat WHERE id=?', (src,))
        self._ws = None; self._sus = None
        self.E.log.w(f'🎞 分類 #{src} 併到 #{dst}：{n} 部'); return {'ok': True, 'message': f'✔ 併好了：{n} 部改過去' + ('' if not mv else f'（原本那類已經搬過 {mv} 部，那類先留著）')}

    def cat_move(self, cid, d):
        R = [r['id'] for r in self.E.db.q('SELECT id FROM vc_cat ORDER BY ord, id')]
        if int(cid) not in R: return {'ok': False}
        i = R.index(int(cid)); j = max(0, min(len(R) - 1, i + int(d))); R[i], R[j] = R[j], R[i]
        self.E.db.xm('UPDATE vc_cat SET ord=? WHERE id=?', [(k, x) for k, x in enumerate(R)]); return {'ok': True}

    def cat_order(self, ids):
        """長按拖曳後的新順序（ids 照新的順序）."""
        have = [r['id'] for r in self.E.db.q('SELECT id FROM vc_cat ORDER BY ord, id')]; ids = [int(x) for x in ids if int(x) in have]
        ids += [x for x in have if x not in ids]
        self.E.db.xm('UPDATE vc_cat SET ord=? WHERE id=?', [(k, x) for k, x in enumerate(ids)]); self.E.log.w(f'🎞 分類順序：{ids}'); return {'ok': True, 'message': '✔ 順序改好了'}

    def dest_of(self, cat, src):
        """要搬去哪：分類有設位置就用；沒設＝影片那顆硬碟的 \\FileCompare_分類\\分類名稱；位置填「不搬」＝留在原處."""
        if str(cat.get('dest') or '').strip() in STAY: return os.path.dirname(src)
        if cat.get('dest'): return os.path.normpath(cat['dest'])
        drv = os.path.splitdrive(src)[0]
        return os.path.join(drv + '\\', MOVE_DIR, cat['name']) if drv else os.path.join(os.path.dirname(os.path.dirname(src)), MOVE_DIR, cat['name'])

    # ---- 影片清單
    LIST_F = {'todo': 't.fid IS NULL', 'all': '1', 'wait': 't.moved=0', 'done': 't.moved=1'}
    ORD = {'path': 'f.path', 'size': 'f.size DESC, f.path', 'size_asc': 'f.size, f.path', 'dur': 'f.dur DESC, f.path', 'dur_asc': 'f.dur, f.path',
           'taken': 'COALESCE(f.taken, f.mtime), f.path', 'taken_desc': 'COALESCE(f.taken, f.mtime) DESC, f.path', 'mtime_desc': 'f.mtime DESC, f.path',
           'rand': '(f.id * 2654435761) % 4294967291', 'tagged_last': "COALESCE(t.t, 0) DESC, f.path",
           'pet': 'COALESCE((SELECT MAX(p.dog, p.cat) FROM vc_pet p WHERE p.fid=f.id), -1) DESC, f.path',
           'res': 'COALESCE(f.w, 0) * COALESCE(f.h, 0) DESC, f.path', 'res_asc': 'COALESCE(f.w, 0) * COALESCE(f.h, 0), f.path'}         # 畫質（解析度）（V0.4.10）      # 打散（每次一樣的亂序）；最近分的先（V0.1.79）

    def dup_losers(self, kind='video'):
        """（V0.2.59：快取 2 分鐘——四萬多部、七萬多組重複時，每次讀清單都重算太慢）."""
        C = self.__dict__.setdefault('_dlc', {}); c = C.get(kind)
        if c and time.time() - c[0] < 120: return c[1]
        if c and time.time() - c[0] < 3600:                                         # 舊了：先回舊的、背景重算（V0.3.86）
            R_ = self.__dict__.setdefault('_dlr', set())
            if kind not in R_:
                R_.add(kind)
                def job():
                    try: C[kind] = (time.time(), self._dup_losers(kind))
                    except Exception: pass
                    finally: R_.discard(kind)
                threading.Thread(target=job, name='DupLosers', daemon=True).start()
            return c[1]
        r = self._dup_losers(kind); C[kind] = (time.time(), r); return r

    def _dup_losers(self, kind='video'):
        """一模一樣的影片：每組留一部（建議的那部），其他的 id。留哪部：①優先保留的資料夾 ②檔名裡有拍攝日期 ③不像副本 ④修改日期最早 ⑤路徑短."""
        k_ = 'photo' if kind == 'photo' else 'video'
        R = [dict(r) for r in self.E.db.q(f"SELECT id,path,size,hash,mtime,name_date,fav FROM files WHERE state='' AND kind='{k_}' AND hash IS NOT NULL AND hash NOT LIKE '!%' AND "
                                          f"(size,hash) IN (SELECT size,hash FROM files WHERE state='' AND kind='{k_}' AND hash IS NOT NULL AND hash NOT LIKE '!%' GROUP BY size,hash HAVING COUNT(*)>1)")]
        G = {}; P = self.E.fc_list('keep_prio')
        for r in R: G.setdefault((r['size'], r['hash']), []).append(r)
        out = {}
        for g in G.values():
            k = min(g, key=lambda f: self.E.fc_rank(f, P))
            for f in g:
                if f['id'] != k['id']: out[f['id']] = k['path']
        return out

    def state_of(self, fid, path, size):
        """0＝16 格做好了（VS 有夠多格、或自己做好了）、1＝還沒做、2＝做不出來."""
        fid = int(fid)
        if fid in self.ready: return 0
        if fid in self.failed: return 2
        V = self.vs_load(); d = V['path'].get(str(path).lower()) or V['ns'].get((os.path.basename(path).lower(), int(size or 0)))
        if d and d['n'] >= 12: self.ready.add(fid); return 0
        J, F = self._gset()                                                         # 一次讀整個資料夾清單，不再一部一部問硬碟（V0.2.79：清單 3 萬部時快很多）
        if fid in J: self.ready.add(fid); return 0
        if fid in F: self.failed.add(fid); return 2
        return 1

    def _gset(self):
        c = getattr(self, '_gs', None)
        if c and time.time() - c[0] < 30: return c[1], c[2]
        J = set(); F = set()
        try:
            for d in self.gdir().iterdir():
                if not d.is_dir(): continue
                for n in os.listdir(d):
                    b, ext = os.path.splitext(n)
                    if not b.isdigit(): continue
                    if ext == '.jpg': J.add(int(b))
                    elif ext == '.fail': F.add(int(b))
        except OSError: pass
        self._gs = (time.time(), J, F); return J, F

    # 長度／大小（V0.1.29）：只看短片、只看大檔…
    LEN_F = {'s30': 'f.dur>0 AND f.dur<30', 's180': 'f.dur>=30 AND f.dur<180', 's600': 'f.dur>=180 AND f.dur<600', 'l600': 'f.dur>=600', 'l1800': 'f.dur>=1800', 'nodur': 'COALESCE(f.dur,0)<=0',
             'b100': 'f.size<100000000', 'b1g': 'f.size>=100000000 AND f.size<1000000000', 'g1': 'f.size>=1000000000', 'g4': 'f.size>=4000000000',
             'por': 'COALESCE(f.h,0) > COALESCE(f.w,0)', 'lan': 'COALESCE(f.w,0) >= COALESCE(f.h,0) AND COALESCE(f.w,0) > 0'}          # 直的／橫的（V0.4.24）
    LEN_N = [('', '全部長度大小'), ('s30', '短於 30 秒'), ('s180', '30 秒～3 分'), ('s600', '3～10 分'), ('l600', '10 分以上'), ('l1800', '30 分以上'), ('nodur', '不知道長度'),
             ('b100', '小於 100 MB'), ('b1g', '100 MB～1 GB'), ('g1', '1 GB 以上'), ('g4', '4 GB 以上'), ('por', '📱 直的（手機直拍、短影音）'), ('lan', '🖥 橫的')]

    def vlist(self, flt='todo', folder='', order='path', meta=False, ready_first=False, ln='', kind='video', q='', paths=False):
        kind = 'photo' if kind == 'photo' else 'video'
        pkf = flt if flt in ('todo_np', 'todo_pk') else ''                         # 📦 只看不在／在資料夾包裡的（V0.2.35）
        if pkf: flt = 'todo'
        petf = flt if str(flt).startswith('pet') else ''                             # 🐾 有貓狗的（V0.2.93）
        if petf: flt = 'todo'
        chkf = flt == 'chk'                                                            # 🧐 可能分錯的（V0.4.31）
        if chkf: flt = 'wait'
        sugf = flt == 'todo_sug'                                                     # 💡 還沒分、有建議的（V0.3.42）
        if sugf: flt = 'todo'
        W = ["f.state=''", f"f.kind='{kind}'"] + ([] if chkf else ['f.size>0', "f.health NOT IN ('broken','partial','zero')"]); A = []   # 🧐 可能分錯的：壞的也要列出來看（V0.5.76，不然算到 31 部、清單卻是 0）      # 壞掉的、半壞的不列（用「🧹 處理有問題的影片」搬走）
        if ln in self.LEN_F: W.append(self.LEN_F[ln])
        if str(flt).startswith('c'):
            try: W.append('t.cat=?'); A.append(int(str(flt)[1:]))
            except ValueError: pass
        else: W.append(self.LIST_F.get(flt, self.LIST_F['todo']))
        if folder:
            fo = fcore.like_esc(os.path.normpath(str(folder)).rstrip('\\/')); W.append("(f.path LIKE ? ESCAPE '^' OR f.path LIKE ? ESCAPE '^')"); A += [fo + '\\%', fo + '/%']
        qs = str(q or '').strip()
        if re.match(r'^(相機|camera|cam)\s*[:：]', qs, re.I):                              # 🔍「相機:DJI」＝相機型號（V0.3.19）
            cm = re.sub(r'^(相機|camera|cam)\s*[:：]\s*', '', qs, flags=re.I)
            if cm in ('', '（不知道相機）'): W.append("TRIM(COALESCE(f.make,'')||COALESCE(f.model,''))=''")
            else: W.append("(COALESCE(f.make,'')||' '||COALESCE(f.model,'')) LIKE ? ESCAPE '^'"); A.append('%' + fcore.like_esc(cm) + '%')
            qs = ''
        elif re.match(r'^(檔名|name)\s*[:：]', qs, re.I):                                   # 🔍「檔名:DJI_」＝檔名開頭（V0.3.22）
            pre = re.sub(r'^(檔名|name)\s*[:：]', '', qs, flags=re.I); qs = ''
            if pre and not pre.startswith('（'): W.append("(f.path LIKE ? ESCAPE '^' OR f.path LIKE ? ESCAPE '^')"); A += ['%\\' + fcore.like_esc(pre) + '%', '%/' + fcore.like_esc(pre) + '%']
        m = re.search(r'(?:^|\s)(?:日期|date)\s*[:：]\s*(\d{4})(?:[-/.](\d{1,2}))?(?:[-/.](\d{1,2}))?(?=\s|$)', qs, re.I)
        if m:                                                                       # 🔍「日期:2019-10」＝那年／那個月／那天拍的（V0.3.51）
            y, mo, dd = int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0)
            if 1 <= (mo or 1) <= 12 and 1 <= (dd or 1) <= 31:
                ta = time.mktime((y, mo or 1, dd or 1, 0, 0, 0, 0, 0, -1))
                tb = ta + 86400 if dd else (time.mktime((y + (mo == 12), (mo % 12) + 1, 1, 0, 0, 0, 0, 0, -1)) if mo else time.mktime((y + 1, 1, 1, 0, 0, 0, 0, 0, -1)))
                W.append('COALESCE(f.taken, f.mtime) >= ? AND COALESCE(f.taken, f.mtime) < ?'); A += [ta, tb]
            qs = (qs[:m.start()] + ' ' + qs[m.end():]).strip()
        cq = None; m2 = re.search(r'(?:^|\s)(?:內容|content)\s*[:：]\s*(\S+)', qs, re.I)
        if m2:                                                                      # 🔍「內容:有狗」「內容:很暗」「內容:有人」＝電腦看到的（V0.4.28）
            want = m2.group(1); qs = (qs[:m2.start()] + ' ' + qs[m2.end():]).strip()
            if want in ('有人', '人臉', '人'): cq = {r[0] for r in self.E.db.q('SELECT fid FROM vc_pet WHERE face>0')}
            elif want in ('沒人', '沒有人'): cq = {r[0] for r in self.E.db.q('SELECT fid FROM vc_pet WHERE face=0')}
            else: cq = {f for f, T in self._pet_map().items() if any(want in t[1:] for t in T)}
        for w in qs.split()[:6]:                                          # 🔍 檔名／資料夾找字（V0.2.75）：空白分開＝都要有
            W.append("f.path LIKE ? ESCAPE '^'"); A.append('%' + fcore.like_esc(w) + '%')
        R = self.E.db.q(f"SELECT f.id, f.dur, f.size, f.path FROM files f LEFT JOIN vc_tag t ON t.fid=f.id WHERE {' AND '.join(W)} ORDER BY {self.ORD.get(order, 'f.path')}", A)
        if cq is not None: R = [r for r in R if r[0] in cq]
        if chkf:
            try: SS = self.suspects()
            except Exception: SS = {}
            R = [r for r in R if r[0] in SS]
        if sugf:
            try:
                d = self.hint_many([r[0] for r in R], dry=True); SG = {x for rr in d.get('rows', []) for x in rr['ids']}
            except Exception: SG = set()
            R = [r for r in R if r[0] in SG]
        if petf:
            try: PS = self.E.pet.pet_ids({'pet_dog': 'dog', 'pet_cat': 'cat', 'pet_face': 'face', 'pet_noface': 'noface'}.get(petf, petf[4:] if petf.startswith('pet_s_') else 'any'))   # 🔎 pet_s_food → s_food（V0.3.73）
            except Exception: PS = set()
            R = [r for r in R if r[0] in PS]
        if pkf:
            PP = {r[0]: r[1] for r in self.E.db.q(f"SELECT id, path FROM files WHERE state='' AND kind='{kind}'")}
            inp = lambda fid: bool(self.E.vg.pack_of(os.path.dirname(PP.get(fid, ''))))
            R = [r for r in R if inp(r[0]) == (pkf == 'todo_pk')]
        if kind == 'photo':                                                         # 📷 照片：不用做 16 格，全部都「好了」
            if not chkf: L = self.dup_losers('photo'); R = [r for r in R if r[0] not in L]
            if meta: return ([r[0] for r in R], [0] * len(R), [int(r[2] or 0) for r in R], [0] * len(R)) + (([r[3] for r in R],) if paths else ())
            return [r[0] for r in R]
        if not chkf: L = self.dup_losers(); R = [r for r in R if r[0] not in L]       # 重複的只列建議保留的那部（🧐 可能分錯的全部列，V0.5.76）
        if self.E.cfg.get('vc_skip_live') is not False and flt in ('todo', 'all'):    # 📱 動態照片的那段短影片（跟照片同名、≤ 4 秒）不列（V0.1.58）
            LV = self.live_ids(); self.live_n = sum(1 for r in R if r[0] in LV); R = [r for r in R if r[0] not in LV]
        if meta or ready_first:
            S = {r[0]: self.state_of(r[0], r[3], r[2]) for r in R}                       # 路徑上面已經讀了，不用再查一次（V0.3.89）
            self.want = [r[0] for r in R if S[r[0]] == 1]                                # 背景先做你現在這份清單裡還沒做的
            if ready_first: R = sorted(R, key=lambda r: S[r[0]])                          # ⚡ 做好的先（同一類裡順序不變）
        if meta: return ([r[0] for r in R], [int(r[1] or 0) for r in R], [int(r[2] or 0) for r in R], [S[r[0]] for r in R]) + (([r[3] for r in R],) if paths else ())
        return [r[0] for r in R]                                    # 重複的只列建議保留的那部

    def item(self, fid):
        self.last_view = time.time()                                               # 背景做 16 格的讓路用
        f = self.E.fc_file(fid)
        if not f: return None
        t = self.E.db.one('SELECT cat, moved, dst FROM vc_tag WHERE fid=?', (int(fid),))
        return {'id': f['id'], 'path': f['path'], 'name': os.path.basename(f['path']), 'size': f['size'], 'dur': f.get('dur') or 0, 'taken': f.get('taken') or f.get('mtime'),
                'w': f.get('w') or 0, 'h': f.get('h') or 0, 'health': f.get('health') or '', 'model': ((f.get('make') or '') + ' ' + (f.get('model') or '')).strip(),
                'fav': f.get('fav') or 0, 'cat': t['cat'] if t else 0, 'moved': t['moved'] if t else 0, 'hint': None if t else self.hint(f['path'], f.get('taken') if f.get('date_src') in ('exif', 'video', 'name') else None, f.get('dur') if f.get('kind') == 'video' else None, self._cam(f.get('make'), f.get('model')), loc=self._loc(f.get('lat'), f.get('lon')), pt=self._pet_map().get(int(fid)))}

    def tag(self, fid, cat):
        fid = int(fid); cat = int(cat or 0)
        r = self.E.db.one('SELECT moved FROM vc_tag WHERE fid=?', (fid,))
        if r and r['moved']: return {'ok': False, 'message': '這部已經搬過了（要改的話先到「📦 隔離區」復原）'}
        if not cat: self.E.db.x('DELETE FROM vc_tag WHERE fid=?', (fid,)); self.dup_release([fid]); return {'ok': True}
        if not self.E.db.one('SELECT id FROM vc_cat WHERE id=?', (cat,)): return {'ok': False, 'message': '沒有這個分類'}
        self.E.db.x('INSERT INTO vc_tag(fid,cat,t,moved,auto) VALUES(?,?,?,0,0) ON CONFLICT(fid) DO UPDATE SET cat=excluded.cat, t=excluded.t, auto=0', (fid, cat, time.time()))
        return {'ok': True, 'dup': self.dup_to_delete([fid])}

    WORD_SKIP = {'dcim', 'camera', 'video', 'videos', 'movie', 'movies', 'clip', 'private', 'm4root', 'avchd', 'stream', '100media', 'pictures', 'photos', 'photo',
                 'download', 'downloads', 'desktop', 'users', 'new', 'folder', 'backup', 'copy', 'temp', 'tmp', 'data', 'files', 'file', 'all', 'pic', 'pics', 'vid', 'vids', 'mov',
                 '影片', '照片', '相片', '新增資料夾', '備份', '資料夾', '整理', '未整理', '待整理', '其他', '手機', '下載', '桌面', 'filecompare', '分類', '已篩選'}

    def _words(self, path):
        """資料夾名裡的關鍵字（最後 3 層）：英文字、中文詞，去掉數字跟常見的通用名."""
        parts = [p for p in re.split(r'[\\/]', os.path.dirname(path)) if p][-3:]; W = set()
        for p in parts:
            for w in re.findall(r'[A-Za-z]{3,}|[\u3400-\u9fff\u3040-\u30ff]{2,}', p):
                w = w.lower()
                if w not in self.WORD_SKIP: W.add(w)
        return W

    def word_stats(self):
        """💡 從你分過的影片學：資料夾名有哪個字的，大多分到哪一類（V0.2.76；快取 5 分鐘）."""
        c = getattr(self, '_ws', None)
        if c and time.time() - getattr(self, '_ws_chk', 0) < 3: return c[1]                  # 3 秒內不用再問資料庫
        self._ws_chk = time.time(); k = tuple(self.E.db.one('SELECT COUNT(*), MAX(t) FROM vc_tag') or (0, 0))
        if c and time.time() - c[0] < 300 and (len(c) < 3 or c[2] == k or time.time() - c[0] < 20): return c[1]   # 你分了新的就重算（最快 20 秒一次）（V0.3.25）
        S = {}
        PM = self._pet_map()
        for fid, path, cat, mk, md, la, lo in self.E.db.q("SELECT t.fid, f.path, t.cat, f.make, f.model, f.lat, f.lon FROM vc_tag t JOIN files f ON f.id=t.fid WHERE t.auto=0"):
            W = self._words(path); cm = self._cam(mk, md); gl = self._loc(la, lo)
            if fid in PM: W |= PM[fid]                                               # 🐾 有貓狗、🔎 電腦猜的內容（V0.3.74）
            if gl: W.add(gl)                                                         # 同一個地方（V0.3.68）
            if cm: W.add('📷' + cm)                                                  # 同一台相機（V0.3.18）：例如空拍機、行車記錄器
            np_ = self.name_pre(path)
            if not np_.startswith('（'): W.add('🔤' + np_)                            # 檔名開頭一樣（V0.3.23）：例如 LINE_、DJI_
            for w in W:
                d = S.setdefault(w, {}); d[cat] = d.get(cat, 0) + 1
            d = S.setdefault('\x00all', {}); d[cat] = d.get(cat, 0) + 1              # 全部分過的各類幾部（綜合判斷用；不是線索）
        AC = {}
        try:                                                                        # 📈 建議準確率（每種線索；綜合判斷太常不準就自動不用）（V0.4.46）
            for k_, n_, h_ in self.E.db.q('SELECT kind, COUNT(*), SUM(hit) FROM (SELECT kind, hit FROM vc_hstat ORDER BY t DESC LIMIT 500) GROUP BY kind'):
                AC[k_] = (n_, (h_ or 0) / max(1, n_))
        except Exception: pass
        self._acc = AC
        self._ws = (time.time(), S, k); return S

    def hint_summary(self):
        """💡 還沒分的有幾部可以照建議分（背景算，10 分鐘一次；給總覽建議用）（V0.3.27）."""
        c = getattr(self, '_hs', None)
        if (not c or time.time() - c[0] > 600) and not getattr(self, '_hs_run', False):
            def job():
                try:
                    self._hs_run = True
                    if (self.E.db.one('SELECT COUNT(*) FROM vc_tag WHERE auto=0') or [0])[0] < 20 and not self.rules(): self._hs = (time.time(), None); return
                    L = self.vlist('todo'); d = self.hint_many(L, dry=True) if 0 < len(L) <= 60000 else None
                    if d: d = {'n': d['n'], 'rows': [{k: r[k] for k in ('cat', 'why', 'n')} for r in d['rows'][:5]]}
                    self._hs = (time.time(), d)
                except Exception: self._hs = (time.time(), None)
                finally: self._hs_run = False
            threading.Thread(target=job, name='HintSum', daemon=True).start()
        return c[1] if c else None

    def learned(self):
        """🧠 學到的習慣（V0.3.25）：[{w, cat, n, tot, ign}]，夠多例子、八成以上同一類的."""
        S = self.word_stats(); IG = set(self.E.cfg.get('vc_learn_ignore') or []); C = {c['id']: c['name'] for c in self.cats()}; out = []
        for w, D in S.items():
            if w.startswith('\x00'): continue
            cat, n = max(D.items(), key=lambda x: x[1]); tot = sum(D.values())
            if n >= self._need(w) and n / tot >= 0.8 and cat in C: out.append({'w': w, 'cat': C[cat], 'n': n, 'tot': tot, 'ign': w in IG})
        return sorted(out, key=lambda x: -x['n'])[:80]

    def suspects(self):
        """🧐 可能分錯的（分好還沒搬）：同資料夾八成以上是別類，或電腦看到的內容九成以上你都分到別類 → {fid: (建議類, 原因)}（V0.4.31）."""
        k = tuple(self.E.db.one('SELECT COUNT(*), MAX(t) FROM vc_tag') or ()); c = getattr(self, '_sus', None)
        if c and c[0] == k and time.time() - c[1] < 300: return c[2]
        R = self.E.db.q("SELECT t.fid, t.cat, f.path FROM vc_tag t JOIN files f ON f.id=t.fid WHERE t.moved=0 AND t.auto=0 AND f.state=''")
        try: OK = {r[0]: r[1] for r in self.E.db.q('SELECT fid, cat FROM vc_susok')}      # 你按過「沒錯」的（同一類就不再列）
        except Exception: OK = {}
        FD = {}
        for fid, cat, p in R:
            D = FD.setdefault(os.path.dirname(p), {}); D[cat] = D.get(cat, 0) + 1
        C = {c_['id']: c_['name'] for c_ in self.cats()}; WS = self.word_stats(); PM = self._pet_map(); IG = set(self.E.cfg.get('vc_learn_ignore') or []); out = {}
        RU = [r for r in self.rules() if self._rule_dur(r[0]) is None and not re.match(r'^\s*(相機|camera|cam)\s*[:：]', r[0], re.I)]   # 路徑字、內容: 規則
        for fid, cat, p in R:
            if OK.get(fid) == cat: continue
            D = FD[os.path.dirname(p)]; tot = sum(D.values()); mc, mn = max(D.items(), key=lambda x: x[1])
            if mc != cat and tot >= 5 and mn / tot >= 0.8 and mc in C: out[fid] = (mc, f'同一個資料夾 {mn}／{tot} 部是「{C[mc]}」'); continue
            if RU:                                                                    # 📏 跟你自己的規則不一樣（V0.4.36）
                try:
                    h = self.hint(p, None, None, '', {}, RU, '', PM.get(fid))
                    if h and len(h) > 3 and h[3] == 'rule' and h[0] != cat and h[0] in C: out[fid] = (h[0], f'你的規則「{h[4]}」是「{C[h[0]]}」'); continue
                except Exception: pass
            for w in PM.get(fid, ()):
                Dw = WS.get(w)
                if not Dw or w in IG: continue
                wc, wn = max(Dw.items(), key=lambda x: x[1]); wt = sum(Dw.values())
                if wc != cat and wn >= 10 and wn / wt >= 0.9 and wc in C: out[fid] = (wc, f'電腦看到「{w[1:]}」的你 {wn}／{wt} 部分到「{C[wc]}」'); break
        self._sus = (k, time.time(), out); return out

    def hstat(self, hint, cat):
        """📈 有 💡 建議時記下有沒有照著分（V0.4.45；網頁、電腦版都用）."""
        try:
            if not hint or not cat: return
            self.E.db.x('CREATE TABLE IF NOT EXISTS vc_hstat(t REAL, kind TEXT, hit INTEGER)')
            self.E.db.x('INSERT INTO vc_hstat(t, kind, hit) VALUES(?,?,?)', (time.time(), (hint[3] if len(hint) > 3 else 'folder'), 1 if int(hint[0]) == int(cat) else 0))
        except Exception: pass

    def sus_ok(self, fid):
        """🧐 這部沒分錯：以後不再列（V0.4.35）."""
        self.E.db.x('CREATE TABLE IF NOT EXISTS vc_susok(fid INTEGER PRIMARY KEY, cat INTEGER)')
        r = self.E.db.one('SELECT cat FROM vc_tag WHERE fid=?', (int(fid),))
        if r: self.E.db.x('INSERT OR REPLACE INTO vc_susok(fid, cat) VALUES(?,?)', (int(fid), r[0]))
        c = getattr(self, '_sus', None)
        if c: c[2].pop(int(fid), None)
        return bool(r)

    @staticmethod
    def _need(w):
        """學到的習慣要幾部例子才算：相機、檔名開頭 12；地方 8；貓狗、內容 10；資料夾的字 5."""
        c = w[:1]
        return 12 if c in ('📷', '🔤') else 8 if c == '📍' else 10 if c in ('🐾', '🔎') else 5

    def _pet_map(self):
        """fid → {'🐾有狗', '🔎食物', …}（電腦看過的；快取 60 秒）（V0.3.74）."""
        c = getattr(self, '_pm', None)
        if c and time.time() - c[0] < 60: return c[1]
        M = {}
        try:
            import fc_pets as pets
            th = self.E.pet.th(); SC = {}
            for k, nm, S in pets.SCENES:
                for i in S: SC[i] = '🔎' + nm.split(' ', 1)[-1].split('／')[0]
            for fid, dog, cat, top, sp, lum, lsd, mot, fc, np_ in self.E.db.q('SELECT fid, dog, cat, COALESCE(sc, top), sp, lum, lstd, mot, face, COALESCE(nopet,0) FROM vc_pet'):
                T = set()
                if np_: dog = cat = -1                                              # 你按過「不是貓狗」（V0.6.00）
                if lum is not None and 0 <= lum < pets.DARK: T.add('🔎很暗')
                elif lsd is not None and 0 <= lsd < pets.FLAT: T.add('🔎畫面沒東西')
                elif mot is not None and 0 <= mot < pets.STILL: T.add('🔎畫面沒動')
                dog = dog if dog is not None else -1; cat = cat if cat is not None else -1
                if dog >= th: T.add('🐾有狗')
                if cat >= th: T.add('🐾有貓')
                if (dog >= th or cat >= th) and fc is not None and fc >= 0: T.add('🐾貓狗＋人' if fc > 0 else '🐾只有貓狗')   # （V0.4.15）
                if fc is not None and fc >= 3: T.add('🔎3人以上')                         # 👥 聚會、合照（V0.4.53）
                if top is not None and top in SC and not (sp is not None and 0 <= sp < pets.SCENE_P) and not (dog >= th or cat >= th): T.add(SC[top])
                if T: M[fid] = frozenset(T)
        except Exception: pass
        self._pm = (time.time(), M); return M

    @staticmethod
    def name_pre(path):
        """🔤 檔名開頭（V0.3.22）：DJI_0001.MP4 → DJI_、LINE_MOVIE_123 → LINE_MOVIE_、Screenrecorder-2021 → Screenrecorder-；數字開頭 → （數字開頭）."""
        b = os.path.basename(str(path)); m = re.match(r'[A-Za-z][A-Za-z_\-. ]*?(?=\d|$)', b)
        pre = m.group(0) if m else ''
        if not pre or (len(pre.strip('_-. ')) < 2 and not pre.isupper()): return '（數字開頭）' if b[:1].isdigit() else '（其他）'
        return pre[:24]

    @staticmethod
    def _loc(la, lo):
        try:
            if la is None or lo is None or (not la and not lo): return ''
            return f'📍{round(float(la) * 20) / 20:.2f},{round(float(lo) * 20) / 20:.2f}'
        except (TypeError, ValueError): return ''

    @staticmethod
    def _cam(mk, md):
        return ' '.join(str(x or '').strip() for x in (mk, md) if str(x or '').strip()).strip()[:60]

    def rules(self):
        """📏 你自己訂的規則（V0.2.89）：路徑裡有這個字 → 分到這類：[[字, 分類 id], …]."""
        R = self.E.cfg.get('vc_rules') or []; C = {c['id'] for c in self.cats()}
        return [[str(w), int(c)] for w, c in R if str(w).strip() and int(c) in C]

    @staticmethod
    def _rule_dur(w):
        """規則「<3秒」「<3s」＝長度小於 3 秒（V0.3.12）→ 秒數；不是這種規則回 None."""
        m = re.fullmatch(r'\s*[<＜]\s*(\d+(?:\.\d+)?)\s*(秒|s|sec)?\s*', str(w), re.I)
        return float(m.group(1)) if m else None

    @staticmethod
    def _rule_date(w):
        """規則「日期:2019-10」「日期:2019-10-20～2019-10-25」→ (開始, 結束) 秒；不是這種規則回 None（V0.4.57）."""
        m = re.fullmatch(r'\s*(?:日期|date)\s*[:：]\s*(\d{4})(?:[-/.](\d{1,2}))?(?:[-/.](\d{1,2}))?(?:\s*[~～至到-]+\s*(\d{4})(?:[-/.](\d{1,2}))?(?:[-/.](\d{1,2}))?)?\s*', str(w), re.I)
        if not m: return None
        def rng(y, mo, d):
            y, mo, d = int(y), int(mo or 0), int(d or 0); a = time.mktime((y, mo or 1, d or 1, 0, 0, 0, 0, 0, -1))
            b = a + 86400 if d else (time.mktime((y + (mo == 12), (mo % 12) + 1, 1, 0, 0, 0, 0, 0, -1)) if mo else time.mktime((y + 1, 1, 1, 0, 0, 0, 0, 0, -1)))
            return a, b
        try:
            a, b = rng(m.group(1), m.group(2), m.group(3))
            if m.group(4): b = rng(m.group(4), m.group(5), m.group(6))[1]
            return (a, b)
        except (ValueError, OverflowError): return None

    def hint(self, path, taken=None, dur=None, cam='', fold=None, rules=None, loc='', pt=None, tk=None):
        """💡 建議分類（V0.1.45）：同一個資料夾裡已經分好的，大多分到哪一類（至少 2 部、超過 60%）→ (分類 id, 幾部, 共幾部)."""
        try:
            lp = str(path).lower()
            for w, c in (self.rules() if rules is None else rules):
                sec = self._rule_dur(w); dr = self._rule_date(w) if sec is None else None
                if sec is not None:
                    if dur is not None and 0 < float(dur or 0) < sec: return (c, 0, 0, 'rule', w)
                elif dr is not None:                                                        # 「日期:2019-10」＝那段時間拍的（V0.4.57）
                    t_ = tk if tk is not None else taken
                    if t_ and dr[0] <= float(t_) < dr[1]: return (c, 0, 0, 'rule', w)
                elif re.match(r'^\s*(相機|camera|cam)\s*[:：]', w, re.I):                    # 「相機:DJI」＝相機型號有 DJI（V0.3.18）
                    want = re.sub(r'^\s*(相機|camera|cam)\s*[:：]\s*', '', w, flags=re.I).lower()
                    if want and cam and want in cam.lower(): return (c, 0, 0, 'rule', w)
                elif re.match(r'^\s*(內容|content)\s*[:：]', w, re.I):                       # 「內容:有狗」「內容:很暗」＝電腦看的結果（V0.3.82）
                    want = re.sub(r'^\s*(內容|content)\s*[:：]\s*', '', w, flags=re.I).strip()
                    if want and pt and any(want in t[1:] for t in pt): return (c, 0, 0, 'rule', w)
                elif w.lower() in lp: return (c, 0, 0, 'rule', w)
        except Exception: pass
        if fold is not None: C = dict(fold.get(os.path.dirname(path).rstrip('\\/'), {}))   # 整批時先一次算好（V0.3.28）
        else:
            d = fcore.like_esc(os.path.dirname(path).rstrip('\\/')); C = {}
            for (cat,) in self.E.db.q("SELECT t.cat FROM vc_tag t JOIN files f ON f.id=t.fid WHERE t.auto=0 AND f.path LIKE ? ESCAPE '^' AND f.path NOT LIKE ? ESCAPE '^'",
                                      (d + os.sep + '%', d + os.sep + '%' + os.sep + '%')):
                C[cat] = C.get(cat, 0) + 1
        if C:
            cat, n = max(C.items(), key=lambda x: x[1]); tot = sum(C.values())
            if n >= 2 and n / tot >= 0.6: return (cat, n, tot)
        if taken:                                                                   # 同一個時段（前後 3 小時）拍的分到哪（V0.1.86）
            T = {}
            for (cat,) in self.E.db.q("SELECT t.cat FROM vc_tag t JOIN files f ON f.id=t.fid WHERE t.auto=0 AND f.taken BETWEEN ? AND ? AND f.date_src IN ('exif','video','name')", (taken - 10800, taken + 10800)):
                T[cat] = T.get(cat, 0) + 1
            if T:
                cat, n = max(T.items(), key=lambda x: x[1]); tot = sum(T.values())
                if n >= 2 and n / tot >= 0.7: return (cat, n, tot, 'time')
        try:                                                                        # 資料夾名有同一個字的大多分到哪（V0.2.76）
            S = self.word_stats(); best = None; W = self._words(path); IG = set(self.E.cfg.get('vc_learn_ignore') or [])
            if cam: W.add('📷' + cam)
            if loc: W.add(loc)
            if pt: W |= set(pt)
            np_ = self.name_pre(path)
            if not np_.startswith('（'): W.add('🔤' + np_)
            for w in W:
                D = S.get(w)
                if not D or w in IG: continue
                cat, n = max(D.items(), key=lambda x: x[1]); tot = sum(D.values())
                if n >= self._need(w) and n / tot >= 0.8 and (not best or n > best[1]): best = (cat, n, tot, 'word', w)   # 相機、檔名開頭比較籠統，要多一點例子
            if best: return best
            AL = S.get('\x00all')                                                   # 🧮 綜合判斷（V0.4.41）：單一線索不夠強時，幾個線索一起看（像垃圾信過濾那樣）
            am = getattr(self, '_acc', {}).get('mix')
            if AL and len(AL) >= 2 and sum(AL.values()) >= 30 and self.E.cfg.get('vc_mix') is not False and not (am and am[0] >= 30 and am[1] < 0.7):
                K = len(AL); ta = sum(AL.values()); sc = {c: math.log(n / ta) for c, n in AL.items()}; used = 0; UW = []
                for w in W:
                    D = S.get(w)
                    if not D or w in IG: continue
                    tot = sum(D.values())
                    if tot < 3: continue
                    used += 1; UW.append(w)
                    for c in sc: sc[c] += math.log(((D.get(c, 0) + 0.5) / (tot + 0.5 * K)) / (AL[c] / ta))
                if used >= 2:
                    mx = max(sc.values()); Z = sum(math.exp(v - mx) for v in sc.values()); c = max(sc, key=sc.get); p = 1 / Z
                    if p >= 0.92:
                        nm_ = lambda w: (('相機' + w[1:]) if w[:1] == '📷' else ('檔名' + w[1:]) if w[:1] == '🔤' else '同一個地方' if w[:1] == '📍' else w[1:] if w[:1] in ('🐾', '🔎') else f'「{w}」')
                        return (c, used, round(p * 100), 'mix', '、'.join(nm_(w) for w in UW[:4]))
        except Exception: pass
        return None

    def hint_many(self, ids, dry=False):
        """整批：每部影片照建議分（同資料夾／資料夾名的字；沒建議的不動、已經分好的不動）；dry＝只算會怎麼分（V0.2.77）."""
        T = {r[0] for r in self.E.db.q('SELECT fid FROM vc_tag')}; P = {}; R = []; now = time.time(); why = {}; wid = {}; KD = {}; S = set(int(x) for x in ids or [])
        PP = {r[0]: r[1] for r in self.E.db.q("SELECT id, path FROM files WHERE state=''") if r[0] in S}
        DU = {r[0]: r[1] for r in self.E.db.q("SELECT id, dur FROM files WHERE state='' AND kind='video'") if r[0] in S}
        CM = {}; LC = {}
        for r in self.E.db.q("SELECT id, make, model, lat, lon FROM files WHERE state=''"):
            if r[0] in S: CM[r[0]] = self._cam(r[1], r[2]); LC[r[0]] = self._loc(r[3], r[4])
        RU = self.rules(); hasdur = any(self._rule_dur(w) is not None or self._rule_date(w) is not None for w, _c in RU); FD = {}
        TK = {r[0]: r[1] for r in self.E.db.q("SELECT id, taken FROM files WHERE state='' AND date_src IN ('exif','video','name')") if r[0] in S} if hasdur else {}
        for pth, cat in self.E.db.q('SELECT f.path, t.cat FROM vc_tag t JOIN files f ON f.id=t.fid WHERE t.auto=0'):
            dd = FD.setdefault(os.path.dirname(pth).rstrip('\\/'), {}); dd[cat] = dd.get(cat, 0) + 1
        PM = self._pet_map()
        for fid in S:
            if fid in T or fid not in PP: continue
            d = os.path.dirname(PP[fid])
            k_ = (d, CM.get(fid, ''), LC.get(fid, ''), PM.get(fid), self.name_pre(PP[fid]))   # 檔名開頭也算進去（V0.4.56：以前同資料夾不同開頭會共用第一部的建議）
            if hasdur: h = self.hint(PP[fid], None, DU.get(fid), CM.get(fid, ''), FD, RU, LC.get(fid, ''), PM.get(fid), TK.get(fid))     # 有「<3秒」「日期:」規則：每部自己算
            else:
                if k_ not in P: P[k_] = self.hint(PP[fid], None, None, CM.get(fid, ''), FD, RU, LC.get(fid, ''), PM.get(fid))
                h = P[k_]
            if h:
                R.append((fid, h[0], now)); k = (h[0], (f"你的規則「{h[4]}」" if h[3] == 'rule' else '🧮 綜合好幾個線索' if h[3] == 'mix' else (f"同一台相機「{h[4][1:]}」" if str(h[4]).startswith('📷') else (f"檔名開頭「{h[4][1:]}」" if str(h[4]).startswith('🔤') else (f"同一個地方（{h[4][1:]}）" if str(h[4]).startswith('📍') else (f"電腦看到「{h[4][1:]}」" if str(h[4])[:1] in ('🐾', '🔎') else f"資料夾名有「{h[4]}」"))))) if len(h) > 4 else ('同一段時間' if len(h) > 3 else '同資料夾'))
                why[k] = why.get(k, 0) + 1; wid.setdefault(k, []).append(fid); KD[k] = h[3] if len(h) > 3 else 'folder'
        if dry:
            C = {c['id']: c['name'] for c in self.cats()}
            AC = {}
            try:                                                                    # 📈 這種線索你以前照著分的比例（V0.4.44）
                for k_, n_, h_ in self.E.db.q('SELECT kind, COUNT(*), SUM(hit) FROM (SELECT kind, hit FROM vc_hstat ORDER BY t DESC LIMIT 500) GROUP BY kind'):
                    if n_ >= 10: AC[k_] = round(100 * (h_ or 0) / n_)
            except Exception: pass
            return {'ok': True, 'n': len(R), 'rows': sorted([{'cat': C.get(c, '?'), 'cid': c, 'why': w, 'n': n, 'ids': wid[(c, w)], 'kind': KD.get((c, w)), 'acc': AC.get(KD.get((c, w)))} for (c, w), n in why.items()], key=lambda x: -x['n'])}
        self.E.db.xm('INSERT INTO vc_tag(fid,cat,t,moved,auto) VALUES(?,?,?,0,0) ON CONFLICT(fid) DO NOTHING', R)
        try: self.dup_to_delete([r[0] for r in R])
        except Exception: pass
        self.E.log.w(f'💡 照建議分類：{len(R):,} 部'); return {'ok': True, 'n': len(R), 'ids': [r[0] for r in R], 'message': f'✔ {len(R):,} 部照建議分好了' if R else '沒有可以照建議分的（要先分好幾部，才知道你習慣怎麼分）'}

    def live_ids(self):
        """📱 動態照片（iPhone Live Photo、部分 Android）：同一個資料夾有同名的照片＋≤ 4 秒的影片 → 影片那段的 id（快取 2 分鐘）."""
        c = getattr(self, '_live', None)
        if c and time.time() - c[0] < 900: return c[1]
        if c and not getattr(self, '_live_run', False):                             # 舊了：先回舊的、背景重算（不讓清單等）（V0.3.86）
            self._live_run = True
            def job():
                try: self._live_calc()
                except Exception: pass
                finally: self._live_run = False
            threading.Thread(target=job, name='LiveIds', daemon=True).start(); return c[1]
        if c: return c[1]
        return self._live_calc()

    def _live_calc(self):
        V = {}
        for fid, p in self.E.db.q("SELECT id, path FROM files WHERE state='' AND kind='video' AND dur>0 AND dur<=4.5"):
            i = p.rfind('.'); V.setdefault((p[:i] if i > max(p.rfind('/'), p.rfind('\\')) else p).lower(), []).append(fid)
        out = set()
        if V:
            for (p,) in self.E.db.q("SELECT path FROM files WHERE state='' AND kind='photo'"):
                i = p.rfind('.'); k = (p[:i] if i > max(p.rfind('/'), p.rfind('\\')) else p).lower()
                if k in V: out.update(V[k])
        self._live = (time.time(), out); return out

    def tag_folder(self, path, cat, kind=''):
        """📂 整個資料夾（含子資料夾）分到同一類（V0.1.77）：還沒分的才分."""
        pre = os.path.normpath(str(path)).rstrip('\\/') + os.sep
        kw = f"kind='{kind}'" if kind in ('photo', 'video') else "kind IN ('photo','video')"
        ids = [r[0] for r in self.E.db.q(f"SELECT id FROM files WHERE state='' AND {kw} AND size>0 AND path LIKE ? ESCAPE '^'", (fcore.like_esc(pre) + '%',))]
        return self.tag_many(ids, cat, True)

    def speed(self):
        """分類速度（V0.1.44）：今天分了幾部、這 7 天、平均幾秒一部（連續分類時的間隔中位數）."""
        lt = time.localtime(); t0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
        T = sorted(r[0] for r in self.E.db.q('SELECT t FROM vc_tag WHERE t>=?', (t0 - 6 * 86400,)) if r[0])
        today = sum(1 for t in T if t >= t0); G = sorted(b - a for a, b in zip(T[-300:], T[-299:]) if 0 < b - a < 90)
        C = {c['id']: c['name'] for c in self.cats()}                               # 今天各類幾部（V0.4.39）
        bc = [[C.get(c, '?'), n] for c, n in self.E.db.q('SELECT cat, COUNT(*) FROM vc_tag WHERE t>=? GROUP BY cat ORDER BY COUNT(*) DESC', (t0,))]
        return {'today': today, 'week': len(T), 'per': round(G[len(G) // 2], 1) if len(G) >= 5 else 0, 'bycat': bc[:8]}

    def tag_many(self, ids, cat, only_new=True):
        """整批分類（V0.1.29）：現在這份清單全部標成同一類；已經搬過的不動，only_new＝已經分好的也不改."""
        cat = int(cat or 0)
        if cat and not self.E.db.one('SELECT id FROM vc_cat WHERE id=?', (cat,)): return {'ok': False, 'message': '沒有這個分類'}
        T = {r[0]: r[1] for r in self.E.db.q('SELECT fid, moved FROM vc_tag')}; now = time.time(); n = 0; R = []
        for fid in {int(x) for x in ids or []}:
            if T.get(fid) == 1 or (only_new and fid in T): continue
            R.append((fid, cat, now)); n += 1
        if cat: self.E.db.xm('INSERT INTO vc_tag(fid,cat,t,moved,auto) VALUES(?,?,?,0,0) ON CONFLICT(fid) DO UPDATE SET cat=excluded.cat, t=excluded.t, auto=0', R)
        else: self.E.db.xm('DELETE FROM vc_tag WHERE fid=? AND moved=0', [(r[0],) for r in R])
        dd = self.dup_to_delete([r[0] for r in R]) if cat else 0
        if not cat: self.dup_release([r[0] for r in R])
        self.E.log.w(f'🎞 整批分類：{n:,} 部 → {cat or "取消分類"}')
        return {'ok': True, 'n': n, 'dup': dd, 'message': (f'✔ {n:,} 部分好了' if cat else f'✔ {n:,} 部取消分類') + (f'；🗑 另外 {dd:,} 個重複的副本標成「Delete」' if dd else '')}

    # ---------------------------------------------------------------- 🗑 分類過的檔，它的重複副本 → Delete（V0.2.66）
    DEL_NAMES = ('delete', 'del', '刪除', '删除', '要刪的', '垃圾')

    def del_cat(self):
        for cid, nm in self.E.db.q('SELECT id, name FROM vc_cat'):
            if str(nm).strip().lower() in self.DEL_NAMES: return cid
        return 0

    def _dup_keys(self, fids):
        K = {}
        L = [int(x) for x in fids or []]
        for i in range(0, len(L), 500):
            part = L[i:i + 500]
            for fid, size, h in self.E.db.q(f"SELECT id, size, hash FROM files WHERE id IN ({','.join('?' * len(part))}) AND hash IS NOT NULL AND hash NOT LIKE '!%' AND size>0", part):
                K[(size, h)] = fid
        return K

    def _dup_copies(self, K):
        out = []; keys = list(K)
        for i in range(0, len(keys), 300):
            part = keys[i:i + 300]
            ks = set(part)                                                         # 用指紋的索引找（快），大小再比一次
            out += [r for r in self.E.db.q(f"SELECT id, size, hash FROM files INDEXED BY ix_files_hash WHERE hash IN ({','.join('?' * len(part))}) AND state='' AND keep=0", [k[1] for k in part]) if (r[1], r[2]) in ks]
        return out

    def dup_to_delete(self, fids):
        """你分類過的檔：它在別的地方一模一樣的副本，自動標成「Delete」（只留你分的那一份；你自己分過類的副本不動；按 🚚 搬才會搬）."""
        if self.E.cfg.get('vc_dup_del') is False: return 0
        did = self.del_cat()
        if not did or not fids: return 0
        src = {int(x) for x in fids}; K = self._dup_keys(src)
        if not K: return 0
        T = {r[0]: (r[1], r[2], r[3]) for r in self.E.db.q('SELECT fid, cat, moved, COALESCE(auto,0) FROM vc_tag')}
        now = time.time(); W = []
        for fid, size, h in self._dup_copies(K):
            if fid in src or fid == K.get((size, h)): continue
            t = T.get(fid)
            if t and (t[1] or not t[2]): continue                                    # 已經搬過、或是你自己分的 → 不動
            if t and t[0] == did: continue
            W.append((fid, did, now))
        if W:
            self.E.db.xm('INSERT INTO vc_tag(fid,cat,t,moved,auto) VALUES(?,?,?,0,1) ON CONFLICT(fid) DO UPDATE SET cat=excluded.cat, t=excluded.t, auto=1 WHERE vc_tag.moved=0 AND vc_tag.auto=1', W)
            self.E.log.w(f'🗑 分類過的檔有重複：另外 {len(W):,} 個副本標成「Delete」（只留分類的那一份）')
        return len(W)

    def dup_release(self, fids):
        """取消分類時：之前因為它而自動標成 Delete 的副本，放回還沒分類."""
        K = self._dup_keys(fids)
        if not K: return 0
        ids = [(r[0],) for r in self._dup_copies(K)]
        self.E.db.xm('DELETE FROM vc_tag WHERE fid=? AND moved=0 AND COALESCE(auto,0)=1', ids); return len(ids)

    def dup_to_delete_all(self):
        """已經分類過的全部檢查一次（背景，啟動後跑一次）."""
        try:
            F = [r[0] for r in self.E.db.q('SELECT fid FROM vc_tag WHERE COALESCE(auto,0)=0')]
            n = self.dup_to_delete(F)
            if n: self.E.oplog('重複副本 → Delete', f'已分類的 {len(F):,} 部檢查完：{n:,} 個副本標成 Delete')
            return n
        except Exception: self.E.log.err('🗑 重複副本 → Delete（全部）'); return 0

    # ================================================================ 一次搬檔
    def move_plan(self):
        C = {c['id']: c for c in self.cats()}; out = []
        for c in C.values():
            if c['wait']: out.append({'id': c['id'], 'name': c['name'], 'n': c['wait'], 'dest': c['dest'] or f'（每顆硬碟的 \\{MOVE_DIR}\\{c["name"]}）', 'ex': self.move_examples(c['id'])})
        return out

    def target_dir(self, c, r, sub):
        """這部要搬到哪個資料夾（搬檔、搬前預覽共用；V0.3.62 抽出來）."""
        E = self.E; src = r['path']; dd = self.dest_of(c, src)
        if str(c.get('dest') or '').strip() in STAY: return dd                       # 不搬：留在原處、只記下分好了
        if r.get('sub'): return os.path.join(dd, r['sub'])                          # 📦 整包分類：保留「包名＼原本的子資料夾」（V0.2.14）
        if sub == 'dir':                                                            # 照原本的資料夾名（V0.2.25）：已篩選＼2020-日本旅遊＼…
            sd = os.path.dirname(src); pd = os.path.basename(sd)
            try: pk = E.vg.pack_of(sd)
            except Exception: pk = ''
            if pk: pd = os.path.relpath(sd, os.path.dirname(pk))                       # 在資料夾包裡：包名＼原本的子資料夾
            if pd and pd != '.': dd = os.path.join(dd, pd)
        elif sub:                                                                   # 分類資料夾裡再照年份分（V0.1.84）
            t_ = r['taken'] if r.get('date_src') in ('exif', 'video', 'name') and r.get('taken') else r.get('mtime')
            try: lt = time.localtime(t_); dd = os.path.join(dd, f'{lt.tm_year}' if sub == 'y' else os.path.join(f'{lt.tm_year}', f'{lt.tm_year}-{lt.tm_mon:02d}') if sub == 'y_ym' else f'{lt.tm_year}-{lt.tm_mon:02d}')
            except Exception: pass
        return dd

    def move_examples(self, cid, n=2):
        """🚚 搬前預覽：這一類的前幾部會搬到哪（V0.3.62）."""
        C = {c['id']: c for c in self.cats()}; c = C.get(int(cid)); sub = self.E.cfg.get('vc_sub') or ''
        if not c: return []
        out = []
        for r in self.E.db.q("SELECT t.fid, t.cat, t.sub, f.path, f.size, f.taken, f.mtime, f.date_src FROM vc_tag t JOIN files f ON f.id=t.fid WHERE t.moved=0 AND t.cat=? AND f.state='' ORDER BY RANDOM() LIMIT ?", (int(cid), n)):
            r = dict(r)
            try: out.append({'src': r['path'], 'dst': os.path.join(self.target_dir(c, r, sub), os.path.basename(r['path']))})
            except Exception: pass
        return out

    def move_start(self, only=None):
        """only＝只搬這些 id（例如整包已篩選只搬那一包；V0.2.26）；None＝全部分好還沒搬的."""
        if self.mv.get('run'): return False
        only = {int(x) for x in only} if only else None
        tot = len(only) if only else (self.E.db.one('SELECT COUNT(*) FROM vc_tag WHERE moved=0') or [0])[0]
        self.mv.clear(); self.mv.update(run=True, n=0, ok=0, bad=0, b=0, cancel=False, err=[], total=tot)
        threading.Thread(target=self._move_job, args=(only,), name='VSortMove', daemon=True).start(); return True

    def _move_job(self, only=None):
        E = self.E; M = self.mv; t = E.task('op', '🎞 影片分類：搬檔'); C = {c['id']: c for c in self.cats()}
        E.log.w(f'🎞 開始搬檔：{M["total"]} 部')
        try:
            R = [dict(r) for r in E.db.q("SELECT t.fid, t.cat, t.sub, f.path, f.size, f.taken, f.mtime, f.date_src FROM vc_tag t JOIN files f ON f.id=t.fid WHERE t.moved=0 AND f.state='' ORDER BY f.path")]
            if only: R = [r for r in R if r['fid'] in only]
            sub = E.cfg.get('vc_sub') or ''
            for r in R:
                if M.get('cancel') or E.stop_all: break
                M['n'] += 1; c = C.get(r['cat'])
                if not c: continue
                src = r['path']; dd = self.target_dir(c, r, sub)
                try:
                    if os.path.splitdrive(src)[0].lower() != os.path.splitdrive(dd)[0].lower():
                        raise RuntimeError(f'目的地在別顆硬碟（{dd}）：這版只在同一顆硬碟裡搬（瞬間完成、不會複製）')
                    if fcore.under(src, dd): E.db.x('UPDATE vc_tag SET moved=1, dst=? WHERE fid=?', (src, r['fid'])); M['ok'] += 1; continue
                    dst = fcore.move(src, os.path.join(dd, os.path.basename(src)))
                except Exception as ex:
                    M['bad'] += 1; M['err'].append(f'{os.path.basename(src)}：{ex}'); E.oplog('影片分類搬檔', f'失敗：{src}：{ex}', False); continue
                try:
                    E.db.x('UPDATE files SET path=? WHERE id=?', (dst, r['fid']))
                    E.db.x('INSERT INTO moves(t,fid,src,dst,reason) VALUES(?,?,?,?,?)', (time.time(), r['fid'], src, dst, f'分類：{c["name"]}'))
                    E.db.x('UPDATE vc_tag SET moved=1, dst=? WHERE fid=?', (dst, r['fid']))
                except Exception as ex:
                    try: fcore.move(dst, src, rename=False)
                    except Exception: E.log.err(f'🎞 搬檔：資料庫寫不進去，檔案也搬不回去：{dst}')
                    M['bad'] += 1; M['err'].append(f'{os.path.basename(src)}：資料庫寫不進去 {ex}'); continue
                M['ok'] += 1; M['b'] += r['size'] or 0; t['msg'] = f'{M["ok"]:,}／{M["total"]:,}'
                if E.cfg.get('rm_empty_dirs') is not False:                         # 搬空的資料夾順手收掉（只收「完全空的」，V0.1.87）
                    try:
                        stop = next((x for x in E.fc_list('roots') if fcore.under(src, x)), None)          # 不會收掉「要整理的資料夾」本身
                        if stop: fcore.rmdirs_up(os.path.dirname(src), stop)
                    except Exception: pass
                # 預覽快取跟著新路徑（VS 的不用動：用檔名＋大小也找得到）
            msg = f'搬了 {M["ok"]:,} 部（{fcore_fmt_b(M["b"])}）' + (f'，{M["bad"]} 部沒辦法：{M["err"][0]}' if M['bad'] else '')
            E.done(t, 'stop' if M.get('cancel') else 'done', msg); E.oplog('影片分類搬檔', msg); E.log.w('🎞 ' + msg); M['msg'] = msg
        except Exception as ex: E.log.err('🎞 搬檔'); E.done(t, 'fail', str(ex)); M['msg'] = str(ex)
        finally: M['run'] = False; E.fc_kick()


def fcore_fmt_b(b):
    b = float(b or 0)
    return f'{b / 1e9:.2f} GB' if b >= 1e9 else f'{b / 1e6:.0f} MB'


# ================================================================ 🧹 有問題的影片：壞的 → delete、半壞 → check video、重複 → repeat（跟分類分開放）
def prob_dst(src, sub, root=''):
    drv, rest = os.path.splitdrive(src)
    if drv: return os.path.join(drv + '\\', PROB_DIR, sub, rest.lstrip('\\/'))
    base = root or os.path.dirname(src)                                          # （不是 Windows：放在要整理的資料夾底下，測試用）
    return os.path.join(base, PROB_DIR, sub, os.path.relpath(src, base))


def _clean_rows(self):
    E = self.E; out = {'delete': [], 'check': [], 'repeat': []}
    for r in E.db.q("SELECT id,path,root,size,health,health_msg FROM files WHERE state='' AND kind='video' AND health IN ('broken','zero','partial') AND keep=0"):
        out['check' if r['health'] == 'partial' else 'delete'].append(dict(r, why=r['health_msg'] or ''))
    L = self.dup_losers(); bad = {x['id'] for v in out.values() for x in v}
    for i in range(0, len(L), 500):
        ids = [x for x in list(L)[i:i + 500] if x not in bad]
        if ids:
            for r in E.db.q(f"SELECT id,path,root,size FROM files WHERE id IN ({','.join('?' * len(ids))})", ids):
                out['repeat'].append(dict(r, why='重複，保留 ' + L[r['id']]))
    return out


def clean_plan(self):
    R = _clean_rows(self); E = self.E
    un = (E.db.one("SELECT COUNT(*) FROM files WHERE state='' AND kind='video' AND health=''") or [0])[0]
    uh = (E.db.one(f"SELECT COUNT(*) FROM files WHERE state='' AND kind='video' AND size>0 AND (hash IS NULL AND size IN ({E.DUP_SIZES}))") or [0])[0]
    out = {k: {'n': len(v), 'b': sum(x['size'] or 0 for x in v), 'sub': PROB_SUB[k]} for k, v in R.items()}
    out.update(unchecked=un, unhashed=uh, dir=PROB_DIR); return out


def clean_start(self):
    if self.mv.get('run'): return False
    self.mv.clear(); self.mv.update(run=True, what='clean', n=0, ok=0, bad=0, b=0, cancel=False, err=[], total=0)
    threading.Thread(target=self._clean_job, name='VSortClean', daemon=True).start(); return True


def _clean_job(self):
    E = self.E; M = self.mv; t = E.task('op', '🧹 有問題的影片：搬到 delete／check video／repeat')
    try:
        R = _clean_rows(self); M['total'] = sum(len(v) for v in R.values()); cnt = {}
        for k, rows in R.items():
            for r in rows:
                if M.get('cancel') or E.stop_all: break
                M['n'] += 1; src = r['path']
                try: dst = fcore.move(src, prob_dst(src, PROB_SUB[k], r.get('root') or ''))
                except Exception as ex: M['bad'] += 1; M['err'].append(f'{os.path.basename(src)}：{ex}'); continue
                try:
                    E.db.x("UPDATE files SET state='quar', path=?, qpath=? WHERE id=?", (dst, src, r['id']))
                    E.db.x('INSERT INTO moves(t,fid,src,dst,reason) VALUES(?,?,?,?,?)', (time.time(), r['id'], src, dst, f'影片 {PROB_SUB[k]}：{r["why"]}'[:400]))
                    E.db.x('DELETE FROM vc_tag WHERE fid=? AND moved=0', (r['id'],))
                except Exception as ex:
                    try: fcore.move(dst, src, rename=False)
                    except Exception: E.log.err(f'🧹 資料庫寫不進去，檔案也搬不回去：{dst}')
                    M['bad'] += 1; M['err'].append(f'{os.path.basename(src)}：資料庫 {ex}'); continue
                M['ok'] += 1; M['b'] += r['size'] or 0; cnt[k] = cnt.get(k, 0) + 1; t['msg'] = f'{M["ok"]:,}／{M["total"]:,}'
        msg = '、'.join(f'{PROB_SUB[k]} {n:,} 部' for k, n in cnt.items()) or '沒有要搬的'
        msg = f'搬了 {msg}（{fcore_fmt_b(M["b"])}）' + (f'，{M["bad"]} 部沒辦法：{M["err"][0]}' if M['bad'] else '')
        E.done(t, 'stop' if M.get('cancel') else 'done', msg); E.oplog('有問題的影片', msg); E.log.w('🧹 ' + msg); M['msg'] = msg
    except Exception as ex: E.log.err('🧹 有問題的影片'); E.done(t, 'fail', str(ex)); M['msg'] = str(ex)
    finally: M['run'] = False; E.fc_kick()


VSort.clean_plan = clean_plan; VSort.clean_start = clean_start; VSort._clean_job = _clean_job


def tags_of(self, ids):
    """清單上每一部分到哪一類（只回有分的）：{id: cat}."""
    S = set(ids); return {r[0]: r[1] for r in self.E.db.q('SELECT fid, cat FROM vc_tag') if r[0] in S}


def folders(self, kind='video'):
    """有影片（或照片）的資料夾（給「只看這個資料夾」選）：[(資料夾, 幾部)]，照路徑排."""
    C = {}; kind = 'photo' if kind == 'photo' else 'video'
    for r in self.E.db.q(f"SELECT path FROM files WHERE state='' AND kind='{kind}' AND size>0"):
        d = os.path.dirname(r[0]); C[d] = C.get(d, 0) + 1
    return sorted(C.items())


def _pet_cell(self, fid):
    try:
        r = self.E.db.one('SELECT pc FROM vc_pet WHERE fid=?', (int(fid),))
        return r[0] if r and r[0] else None
    except Exception: return None


def thumb_cached(self, fid, w=160):
    """已經做好的小縮圖路徑（不會現做）；沒有回 None（V0.3.47：讓網頁不用卡在等縮圖）；w 是負的＝🐾 用最像貓狗那一格（V0.3.94）."""
    if int(w or 160) < 0:
        if not _pet_cell(self, fid): return thumb_cached(self, fid, -int(w))
        tw = 320 if -int(w) > 160 else 160; out = self.E.data / 'vthumb' / f'{int(fid) % 100:02d}' / f'{int(fid)}_p{tw}.jpg'
        return str(out) if out.exists() else None
    tw = 320 if int(w or 160) > 160 else 160
    out = self.E.data / 'vthumb' / f'{int(fid) % 100:02d}' / (f'{int(fid)}.jpg' if tw == 160 else f'{int(fid)}_{tw}.jpg')
    if out.exists(): return str(out)
    for pw in ((320,) if tw == 160 else (480,)):                                      # 照片用一般縮圖
        p = self.E.data / 'thumbs' / f'{int(fid) % 100:02d}' / f'{int(fid)}_{pw}.jpg'
        if p.exists(): return str(p)
    return None


def thumb(self, fid, w=160):
    """左邊清單的小縮圖：VS 有的從它的大張切中間那格；沒有就用 16 格的中間那格；再沒有就用 FFmpeg 抓一張。快取在 Data\\vthumb；w＝寬（縮圖牆用 320，V0.3.08）."""
    if int(w or 160) < 0:                                                           # 🐾 最像貓狗那一格（V0.3.94）
        pc = _pet_cell(self, fid)
        if not pc: return thumb(self, fid, -int(w))
        tw = 320 if -int(w) > 160 else 160; out = self.E.data / 'vthumb' / f'{int(fid) % 100:02d}' / f'{int(fid)}_p{tw}.jpg'
        if out.exists(): return str(out)
        try:
            si, ci, ri = (int(x) for x in pc.split(',')); g = self.grid(fid, build=False); ff = self.E.ff()[0]
            if not g.get('ok') or not ff or si >= len(g.get('sheets') or []): return thumb(self, fid, -int(w))
            src = g['sheets'][si]; cols, rows = g['cols'], g['rows']; W_, H_ = fcore.img_dims(src)
            if not W_ or not H_: return thumb(self, fid, -int(w))
            cw, ch = W_ // cols, H_ // rows; out.parent.mkdir(parents=True, exist_ok=True); tmp = str(out) + '.tmp.jpg'
            fcore.run([ff, '-hide_banner', '-v', 'error', '-y', '-i', src, '-vf', f'crop={cw}:{ch}:{ci * cw}:{ri * ch},scale=min({tw}\\,iw):-2', '-q:v', '5', tmp], 30)
            if os.path.isfile(tmp): os.replace(tmp, str(out)); return str(out)
        except Exception: pass
        return thumb(self, fid, -int(w))
    tw = 320 if int(w or 160) > 160 else 160
    out = self.E.data / 'vthumb' / f'{int(fid) % 100:02d}' / (f'{int(fid)}.jpg' if tw == 160 else f'{int(fid)}_{tw}.jpg')
    if out.exists(): return str(out)
    f = self.E.fc_file(fid); ff = self.E.ff()[0]
    if f and f.get('kind') == 'photo': return self.E.fc_thumb(fid, 320 if tw == 160 else 480)          # 📷 照片：用一般縮圖
    if not f or not ff: return None
    src = None; cols = rows = 1; cell = 0
    d = self.vs_match(f)
    if d: per = d['cols'] * d['rows']; i = max(0, min(d['n'], len(d['sheets']) * per) // 2); src = d['sheets'][i // per]; cols, rows, cell = d['cols'], d['rows'], i % per
    else:
        g = self.gdir() / f'{int(fid) % 100:02d}' / f'{int(fid)}.jpg'
        if g.exists(): src = str(g); cols = rows = 4; cell = 5
    out.parent.mkdir(parents=True, exist_ok=True); tmp = str(out) + '.tmp.jpg'
    if src:
        w, h = fcore.img_dims(src)
        if w and h:
            cw, ch = w // cols, h // rows
            fcore.run([ff, '-hide_banner', '-v', 'error', '-y', '-i', src, '-vf', f'crop={cw}:{ch}:{cell % cols * cw}:{cell // cols * ch},scale=min({tw}\\,iw):-2', '-q:v', '5', tmp], 30)
    if not os.path.isfile(tmp):
        p = self.E.fc_thumb(fid, tw)
        if p: return p
        return None
    os.replace(tmp, str(out)); return str(out)


VSort.tags_of = tags_of; VSort.folders = folders; VSort.thumb = thumb; VSort.thumb_cached = thumb_cached


# ================================================================ 🎞 分類預覽（背景）：還沒有 16 格的影片先做好（你現在這份清單的先做）
def pre_fetch(self):
    E = self.E; out = []
    for fid in list(self.want):
        if fid in self.ready or fid in self.failed: continue
        out.append(fid)
        if len(out) >= 40: break
    if not out:
        R = E.db.q("SELECT id, path, size FROM files WHERE state='' AND kind='video' AND size>0 AND health NOT IN ('broken','partial','zero') ORDER BY path")
        for r in R:
            if self.state_of(r[0], r[1], r[2]) == 1:
                out.append(r[0])
                if len(out) >= 40: break
    if not out: return []
    return [dict(r) for r in E.db.q(f"SELECT id, path FROM files WHERE id IN ({','.join('?' * len(out))})", out)]


def pre_work(self, it, J):
    if J.get('cancel'): raise InterruptedError
    while time.time() - getattr(self, 'last_view', 0) < 45 and time.time() - getattr(self, '_bg_last', 0) < 8 and not J.get('cancel') and not self.E.stop_all:
        time.sleep(1)                                                               # 你在審片時放慢：8 秒才做一部（V0.3.37；以前完全停，一直審就一直不做）
    if J.get('cancel'): raise InterruptedError
    self._bg_last = time.time(); self.grid(it['id'], build=True)


def pre_progress(self):
    """（做好的, 全部影片）：每 30 秒算一次."""
    if time.time() - self.st_t > 30 or not hasattr(self, '_pp'):
        self.st_t = time.time(); E = self.E; n = d = 0
        try:
            for r in E.db.q("SELECT id, path, size FROM files WHERE state='' AND kind='video' AND size>0"):
                n += 1; d += 1 if self.state_of(r[0], r[1], r[2]) != 1 else 0
        except Exception: pass
        self._pp = (d, n)
    return self._pp


VSort.pre_fetch = pre_fetch; VSort.pre_work = pre_work; VSort.pre_progress = pre_progress

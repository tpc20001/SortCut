"""🖼 相似照片（V0.1.24，不准 import Qt）：不是一模一樣、但看起來幾乎一樣的照片（改過大小、重新壓縮、連拍、加了浮水印）.

用「讀取拍攝資訊」時已經算好的 dHash（64 位元指紋）：差幾個位元＝多像。
為了不用 43 萬 × 43 萬兩兩比：把指紋切成 4 段（每段 16 位元），差 ≤3 個位元的兩張，一定有一段一模一樣（鴿籠原理）→ 只比同一段一樣的。
一模一樣的照片（重複檔）每組只拿建議保留的那張來比（重複的交給「🔁 重複檔」）。
"""
import time, threading

LEVELS = {1: '很嚴格（幾乎一樣）', 2: '嚴格', 3: '一般（建議）'}
MAX_BUCKET = 3000           # 同一段一樣的超過這麼多張（幾乎都是全黑／全白／純色）：不比，免得拖很久


def _flat(h):
    c = bin(h).count('1'); return c <= 3 or c >= 61          # 純色、幾乎全黑全白：每張都「像」，不算


class Sim:
    GRP, SKIP, KV, KIND, REASON, CFG, NAME, UNIT, SEG = 'sim_grp', 'sim_skip', 'sim', 'photo', '相似照片', 'sim_level', '🖼 相似照片', '張', 4

    def __init__(self, E, old=None):
        self.E = E; self.st = old.st if old is not None else {}
        self.lock = threading.Lock()

    # 子類別（相似影片）改這幾個就好
    def thr(self, lv): return lv

    def close(self, i, j, H, X, thr): return bin(H[i] ^ H[j]).count('1') <= thr

    def _sigs(self, lose, S):
        """要比的：(ids, 指紋 int, 額外資料)."""
        ids = []; H = []
        for r in self.E.db.q("SELECT id, dhash FROM files WHERE state='' AND kind='photo' AND dhash!='' AND size>0"):
            if r[0] in lose: continue
            try: h = int(r[1], 16)
            except (TypeError, ValueError): continue
            if _flat(h): continue
            ids.append(r[0]); H.append(h)
        return ids, H, None

    def _files(self, gid):
        return [dict(r) for r in self.E.db.q(f"SELECT f.id, f.path, f.size, f.w, f.h, f.taken, f.mtime, f.dhash, f.name_date, f.make, f.model, f.dur, f.fav FROM {self.GRP} g JOIN files f ON f.id=g.fid WHERE g.gid=? AND f.state=''", (int(gid),))]

    # ---------------------------------------------------------------- 找相似（背景）
    def start(self, level=None):
        if self.st.get('run'): return {'ok': False, 'message': '已經在找了'}
        lv = int(level or self.E.cfg.get(self.CFG) or 3); lv = max(1, min(3, lv)); self.E.cfg.set(self.CFG, lv)
        self.st.clear(); self.st.update(run=True, phase='讀取指紋…', n=0, total=0, cancel=False)
        threading.Thread(target=self._job, args=(lv,), name='SimFind', daemon=True).start()
        return {'ok': True, 'message': f'{self.NAME}：開始找（{LEVELS[lv]}，背景做）'}

    def _job(self, lv):
        E = self.E; S = self.st; t = E.task('op', '找' + self.NAME); t0 = time.time(); K = self.KIND
        try:
            # 一模一樣的（重複檔）：每組只留建議保留的那張
            P = E.fc_list('keep_prio'); lose = set(); G = {}
            for r in E.db.q(f"SELECT id,path,size,hash,mtime,name_date,fav FROM files WHERE state='' AND kind='{K}' AND hash IS NOT NULL AND hash NOT LIKE '!%' AND "
                            f"(size,hash) IN (SELECT size,hash FROM files WHERE state='' AND kind='{K}' AND hash IS NOT NULL AND hash NOT LIKE '!%' GROUP BY size,hash HAVING COUNT(*)>1)"):
                G.setdefault((r['size'], r['hash']), []).append(dict(r))
            for g in G.values():
                k = min(g, key=lambda f: E.fc_rank(f, P)); lose.update(f['id'] for f in g if f['id'] != k['id'])
            skip = {(min(a, b), max(a, b)) for a, b in E.db.q(f'SELECT a, b FROM {self.SKIP}')}
            ids, H, X = self._sigs(lose, S); thr = self.thr(lv); nseg = self.SEG
            n = len(ids); S.update(total=n, n=0, phase='比對中…')
            parent = list(range(n))

            def find(x):
                while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
                return x
            pairs = 0
            for sh in range(0, 16 * nseg, 16):                               # 照片 4 段、影片 12 段，每段 16 位元
                if S.get('cancel') or E.stop_all: raise InterruptedError
                B = {}
                for i, h in enumerate(H): B.setdefault((h >> sh) & 0xFFFF, []).append(i)
                for L in B.values():
                    if len(L) < 2 or len(L) > MAX_BUCKET: continue
                    for x in range(len(L)):
                        i = L[x]; hi = H[i]
                        for y in range(x + 1, len(L)):
                            j = L[y]
                            if self.close(i, j, H, X, thr):
                                if (min(ids[i], ids[j]), max(ids[i], ids[j])) in skip: continue
                                a, b = find(i), find(j)
                                if a != b: parent[a] = b; pairs += 1
                S['n'] = int(n * (sh + 16) / (16 * nseg))
            grp = {}
            for i in range(n):
                grp.setdefault(find(i), []).append(i)
            groups = [g for g in grp.values() if len(g) > 1]
            S['phase'] = '整理分組…'
            rows = []; gid = 0
            for g in sorted(groups, key=lambda g: -len(g)):
                gid += 1
                for i in g: rows.append((gid, ids[i]))
            E.db.x(f'DELETE FROM {self.GRP}')
            for i in range(0, len(rows), 5000): E.db.xm(f'INSERT INTO {self.GRP}(gid, fid) VALUES(?,?)', rows[i:i + 5000])
            info = {'t': time.time(), 'sec': round(time.time() - t0, 1), 'level': lv, 'photos': n, 'groups': gid, 'files': len(rows), 'lose_skip': len(lose)}
            info.update(S.get('extra') or {})
            E.db.x('INSERT OR REPLACE INTO kv(k,v,t) VALUES(?,?,?)', (self.KV, __import__('json').dumps(info), time.time()))
            msg = f'{gid:,} 組、{len(rows):,} {self.UNIT}相似（比了 {n:,} {self.UNIT}，{info["sec"]:g} 秒）'
            E.done(t, 'done', msg); E.log.w(self.NAME + '：' + msg); E.oplog(self.REASON, msg); S['msg'] = msg
        except InterruptedError: E.done(t, 'stop', '停止'); S['msg'] = '停止了'
        except Exception as ex: E.log.err(self.NAME); E.done(t, 'fail', str(ex)); S['msg'] = str(ex)
        finally: S['run'] = False

    # ---------------------------------------------------------------- 看
    def info(self):
        r = self.E.db.one('SELECT v FROM kv WHERE k=?', (self.KV,))
        try: return __import__('json').loads(r[0]) if r else {}
        except Exception: return {}

    def keeper(self, F):
        """建議保留：解析度最高 → 檔案最大（壓縮最少）→ 跟重複檔一樣的規則（優先保留的資料夾、檔名有日期、最早）."""
        P = self.E.fc_list('keep_prio')
        return max(F, key=lambda f: (1 if f.get('fav') else 0, (f.get('w') or 0) * (f.get('h') or 0), f.get('size') or 0, tuple(-x if isinstance(x, (int, float)) else 0 for x in self.E.fc_rank(f, P))))

    def groups(self, offset=0, limit=20):
        E = self.E
        n = (E.db.one(f'SELECT COUNT(DISTINCT gid) FROM {self.GRP}') or [0])[0]
        G = [r[0] for r in E.db.q(f"SELECT DISTINCT g.gid FROM {self.GRP} g JOIN files f ON f.id=g.fid AND f.state='' GROUP BY g.gid HAVING COUNT(*)>1 ORDER BY g.gid LIMIT ? OFFSET ?", (int(limit), int(offset)))]
        out = []
        for gid in G:
            F = self._files(gid)
            if len(F) < 2: continue
            k = self.keeper(F); hk = int(k['dhash'] or '0', 16)
            for f in F:
                f['keep'] = f['id'] == k['id']; f['dist'] = bin(hk ^ int(f['dhash'] or '0', 16)).count('1')
            F.sort(key=lambda f: (not f['keep'], f['dist']))
            out.append({'gid': gid, 'files': F, 'save': sum(f['size'] or 0 for f in F if not f['keep'])})
        return {'ok': True, 'n': n, 'groups': out, 'info': self.info(), 'st': {k: v for k, v in self.st.items() if k != 'extra'}, 'level': int(E.cfg.get(self.CFG) or 3), 'levels': LEVELS}

    def not_similar(self, gid):
        """這組不是相似（例如同一個地方拍的兩張不同照片）：記下來，以後不再放一組."""
        F = [r[0] for r in self.E.db.q(f'SELECT fid FROM {self.GRP} WHERE gid=?', (int(gid),))]
        self.E.db.xm(f'INSERT OR IGNORE INTO {self.SKIP}(a, b) VALUES(?,?)', [(min(a, b), max(a, b)) for i, a in enumerate(F) for b in F[i + 1:]])
        self.E.db.x(f'DELETE FROM {self.GRP} WHERE gid=?', (int(gid),)); return {'ok': True, 'message': '好，這組以後不會再出現'}

    def quar(self, gid=None, fids=None):
        """把一組裡不是 ⭐ 的搬到隔離區（fids＝只搬這幾張）."""
        E = self.E; done = 0; bad = []
        if fids: L = [int(x) for x in fids]
        else:
            F = self._files(gid)
            if len(F) < 2: return {'ok': False, 'message': '這組已經處理過了'}
            k = self.keeper(F); L = [f['id'] for f in F if f['id'] != k['id']]
        for fid in L:
            ok, m = E.fc_quar(fid, self.REASON)
            if ok: done += 1
            else: bad.append(m)
        return {'ok': done > 0, 'message': f'搬了 {done} {self.UNIT}到隔離區' + (f'，{len(bad)} {self.UNIT}沒辦法：{bad[0]}' if bad else '')}

    def quar_all(self):
        """全部組都照建議處理（背景）."""
        if self.st.get('run'): return {'ok': False, 'message': '正在忙'}
        G = [r[0] for r in self.E.db.q(f'SELECT DISTINCT gid FROM {self.GRP}')]
        self.st.clear(); self.st.update(run=True, phase='照建議搬到隔離區…', n=0, total=len(G))

        def job():
            t = self.E.task('op', f'{self.NAME}：照建議搬到隔離區'); ok = 0
            try:
                for g in G:
                    if self.E.stop_all: break
                    r = self.quar(g); self.st['n'] += 1
                    if r.get('ok'): ok += 1
                msg = f'{ok:,} 組照建議處理好了（留 ⭐、其他搬到隔離區）'; self.E.done(t, 'done', msg); self.st['msg'] = msg
            except Exception as ex: self.E.log.err(f'{self.NAME} 全部照建議'); self.E.done(t, 'fail', str(ex))
            finally: self.st['run'] = False
        threading.Thread(target=job, name='SimQuarAll', daemon=True).start()
        return {'ok': True, 'message': f'開始處理 {len(G):,} 組（背景）'}

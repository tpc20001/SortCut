"""📁 重複資料夾（V0.1.27，不准 import Qt）：哪兩個資料夾有很多一模一樣的檔（例如備份、複製了好幾次的手機資料夾）.

「保留 A」：B 裡面「在 A 也有一模一樣的」才搬到隔離區；B 裡 A 沒有的完全不動。
"""
import os, time, threading
from collections import defaultdict

MAX_GROUP = 8          # 一組重複超過 8 份（例如幾百個一樣的貼圖）：兩兩配對太多，不算資料夾對


class DupDir:
    def __init__(self, E, old=None):
        self.E = E; self.st = old.st if old is not None else {}; self.c = None

    def pairs(self, limit=200, force=False):
        if self.c and not force and time.time() - self.c[0] < 300: return self.c[1]
        E = self.E; G = defaultdict(list); N = defaultdict(int)
        for p, k in E.db.q("SELECT path, kind FROM files WHERE state='' AND kind IN ('photo','video')"): N[os.path.dirname(p)] += 1
        for r in E.db.q("SELECT id, path, size, hash FROM files WHERE state='' AND kind IN ('photo','video') AND hash IS NOT NULL AND hash NOT LIKE '!%' AND "
                        "(size,hash) IN (SELECT size,hash FROM files WHERE state='' AND hash IS NOT NULL AND hash NOT LIKE '!%' GROUP BY size,hash HAVING COUNT(*)>1)"):
            G[(r['size'], r['hash'])].append(os.path.dirname(r['path']))
        P = defaultdict(lambda: [0, 0])
        for (size, _h), D in G.items():
            D = sorted(set(D))
            if len(D) < 2 or len(D) > MAX_GROUP: continue
            for i in range(len(D)):
                for j in range(i + 1, len(D)):
                    x = P[(D[i], D[j])]; x[0] += 1; x[1] += size
        out = []
        for (a, b), (n, by) in sorted(P.items(), key=lambda kv: -kv[1][1])[:limit]:
            out.append({'a': a, 'b': b, 'n': n, 'b_bytes': by, 'na': N.get(a, 0), 'nb': N.get(b, 0), 'pa': round(100 * n / max(1, N.get(a, 1))), 'pb': round(100 * n / max(1, N.get(b, 1)))})
        res = {'ok': True, 'pairs': out, 't': time.time(), 'groups': len(G)}
        self.c = (time.time(), res); return res

    def keep(self, keep_dir, other_dir):
        """保留 keep_dir：other_dir 裡「keep_dir 也有一模一樣的」搬到隔離區（背景）."""
        if self.st.get('run'): return {'ok': False, 'message': '已經在搬了'}
        E = self.E; kd = os.path.normcase(keep_dir); od = os.path.normcase(other_dir)
        G = defaultdict(list)
        for r in E.db.q("SELECT id, path, size, hash FROM files WHERE state='' AND hash IS NOT NULL AND hash NOT LIKE '!%' AND (path LIKE ? OR path LIKE ? OR path LIKE ? OR path LIKE ?)",
                        (keep_dir.rstrip('\\/') + '\\%', keep_dir.rstrip('\\/') + '/%', other_dir.rstrip('\\/') + '\\%', other_dir.rstrip('\\/') + '/%')):
            d = os.path.normcase(os.path.dirname(r['path']))
            if d in (kd, od): G[(r['size'], r['hash'])].append((d, r['id'], r['size']))
        L = []
        for g in G.values():
            if any(d == kd for d, _i, _s in g): L += [(i, s) for d, i, s in g if d == od]
        if not L: return {'ok': False, 'message': '沒有要搬的（可能已經處理過了）'}
        self.st.clear(); self.st.update(run=True, n=0, ok=0, bad=0, b=0, total=len(L))

        def job():
            t = E.task('op', f'📁 重複資料夾：保留 {os.path.basename(keep_dir) or keep_dir}')
            try:
                for fid, s in L:
                    if E.stop_all: break
                    self.st['n'] += 1; ok, m = E.fc_quar(fid, '重複資料夾', f'保留 {keep_dir}')
                    if ok: self.st['ok'] += 1; self.st['b'] += s or 0
                    else: self.st['bad'] += 1
                msg = f'搬了 {self.st["ok"]:,} 個（{self.st["b"] / 1e9:.2f} GB）到隔離區，保留 {keep_dir}' + (f'，{self.st["bad"]} 個沒辦法' if self.st['bad'] else '')
                E.done(t, 'done', msg); E.oplog('重複資料夾', msg); self.st['msg'] = msg; self.c = None
            except Exception as ex: E.log.err('📁 重複資料夾'); E.done(t, 'fail', str(ex)); self.st['msg'] = str(ex)
            finally: self.st['run'] = False
        threading.Thread(target=job, name='DupDirKeep', daemon=True).start()
        return {'ok': True, 'message': f'📁 開始搬 {len(L):,} 個（背景做）'}

"""📸 連拍精選（V0.1.50，不准 import Qt）：同一台相機、幾秒內連續拍的一串照片，挑最清楚的留下.

分組：有 EXIF 拍攝時間的照片照時間排，同一台相機（廠牌＋型號）、跟上一張隔 ≤ N 秒就算同一串（至少 3 張）。
清楚程度：FFmpeg 的 blurdetect（縮到 640 寬、灰階）→ 數字越小越清楚；算過存起來（pblur）。
⭐ 建議保留：最愛 → 最清楚 → 解析度 → 檔案大；其他搬到隔離區（可以復原）。介面、動作跟「相似照片」一樣。
"""
import os, re, subprocess, time

import fc_fcore as fcore
import fc_simi as simi

GAP = {1: 1.0, 2: 2.0, 3: 3.0}                 # 等級 → 隔幾秒內算連拍
LEVELS = {1: '很嚴格（1 秒內）', 2: '嚴格（2 秒內）', 3: '一般（3 秒內，建議）'}


def blur_of(ff, path):
    try:
        r = subprocess.run([ff, '-hide_banner', '-i', fcore.lp(path), '-frames:v', '1', '-vf', 'scale=640:-2,format=gray,blurdetect', '-f', 'null', '-'],
                           capture_output=True, timeout=60, creationflags=fcore.NO_WINDOW | (0x00004000 if os.name == 'nt' else 0), stdin=subprocess.DEVNULL)
        m = re.search(rb'blur mean:\s*([\d.]+)', r.stderr)
        return float(m.group(1)) if m else -1.0
    except Exception: return -1.0


class Burst(simi.Sim):
    GRP, SKIP, KV, KIND, REASON, CFG, NAME, UNIT, SEG = 'burst_grp', 'burst_skip', 'burst', 'photo', '連拍精選', 'burst_level', '📸 連拍精選', '張', 4

    def _job(self, lv):
        E = self.E; S = self.st; t = E.task('op', '📸 找連拍'); t0 = time.time(); gap = GAP.get(lv, 3.0)
        try:
            ff = E.ff()[0]
            skip = {(min(a, b), max(a, b)) for a, b in E.db.q('SELECT a, b FROM burst_skip')}
            R = E.db.q("SELECT id, path, size, taken, make, model FROM files WHERE state='' AND kind='photo' AND size>0 AND date_src='exif' AND taken>0 "
                       "AND health NOT IN ('broken','zero') ORDER BY make, model, taken")
            G = []; cur = []; last = None
            for r in R:
                cam = (r['make'] or '', r['model'] or '')
                if last and cam == last[0] and r['taken'] - last[1] <= gap and (min(cur[-1][0], r['id']), max(cur[-1][0], r['id'])) not in skip: cur.append((r['id'], r['path'], r['size']))
                else:
                    if len(cur) >= 3: G.append(cur)
                    cur = [(r['id'], r['path'], r['size'])]
                last = (cam, r['taken'])
            if len(cur) >= 3: G.append(cur)
            have = {r[0]: (r[1], r[2]) for r in E.db.q('SELECT fid, size, blur FROM pblur')}
            need = [x for g in G for x in g if have.get(x[0], (None,))[0] != x[2]]
            S.update(total=len(need), n=0, phase=f'算清楚程度（{len(G):,} 串連拍、{len(need):,} 張）…')
            for fid, p, size in need:
                if S.get('cancel') or E.stop_all: raise InterruptedError
                b = blur_of(ff, p) if ff else -1.0
                E.db.x('INSERT OR REPLACE INTO pblur(fid, size, blur) VALUES(?,?,?)', (fid, size, b)); S['n'] += 1
            S['phase'] = '整理分組…'; rows = []
            for gid, g in enumerate(sorted(G, key=lambda g: -len(g)), 1): rows += [(gid, x[0]) for x in g]
            E.db.x('DELETE FROM burst_grp')
            for i in range(0, len(rows), 5000): E.db.xm('INSERT INTO burst_grp(gid, fid) VALUES(?,?)', rows[i:i + 5000])
            info = {'t': time.time(), 'sec': round(time.time() - t0, 1), 'level': lv, 'photos': len(R), 'groups': len(G), 'files': len(rows)}
            E.db.x('INSERT OR REPLACE INTO kv(k,v,t) VALUES(?,?,?)', ('burst', __import__('json').dumps(info), time.time()))
            msg = f'{len(G):,} 串連拍、{len(rows):,} 張（{info["sec"]:g} 秒）'
            E.done(t, 'done', msg); E.log.w('📸 ' + msg); E.oplog('連拍精選', msg); S['msg'] = msg
        except InterruptedError: E.done(t, 'stop', '停止'); S['msg'] = '停止了'
        except Exception as ex: E.log.err('📸 連拍精選'); E.done(t, 'fail', str(ex)); S['msg'] = str(ex)
        finally: S['run'] = False

    def _files(self, gid):
        return [dict(r) for r in self.E.db.q("SELECT f.id, f.path, f.size, f.w, f.h, f.taken, f.mtime, '' AS dhash, f.name_date, f.make, f.model, f.dur, f.fav, COALESCE(b.blur,-1) AS blur "
                                              "FROM burst_grp g JOIN files f ON f.id=g.fid LEFT JOIN pblur b ON b.fid=f.id WHERE g.gid=? AND f.state='' ORDER BY f.taken", (int(gid),))]

    def keeper(self, F):
        """最愛 → 最清楚（blur 越小越好；算不出來的排最後）→ 解析度 → 檔案大."""
        return min(F, key=lambda f: (0 if f.get('fav') else 1, f['blur'] if (f.get('blur') or -1) >= 0 else 1e9, -((f.get('w') or 0) * (f.get('h') or 0)), -(f.get('size') or 0)))

    def groups(self, offset=0, limit=20):
        r = super().groups(offset, limit)
        for g in r['groups']:
            k = next((f for f in g['files'] if f['keep']), None); kb = (k or {}).get('blur') or 0
            for f in g['files']: f['dist'] = round(f['blur'], 1) if (f.get('blur') or -1) >= 0 else '?'      # 「差」改成顯示清楚程度
            g['files'].sort(key=lambda f: (not f['keep'], f.get('taken') or 0))
        r['levels'] = LEVELS; r['burst'] = True; return r

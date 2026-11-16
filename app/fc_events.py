"""🧳 活動（V0.1.48，不准 import Qt）：照拍攝時間自動分成一段一段的「活動」（出遊、聚會、生日…）.

做法：把有可靠拍攝日期的照片影片照時間排好，前後兩個隔超過 N 小時就算新的活動；太少的（少於 M 個）不列。
有 GPS 的算出大概在哪（給地圖連結）。可以把一個活動「整理成一個資料夾」（先預覽、同一顆硬碟搬、可以復原）。
"""
import os, re, time

GOOD = "date_src IN ('exif','video','name')"


class Events:
    def __init__(self, E):
        self.E = E; self.c = {}

    def list(self, gap_h=6, min_n=15, force=False):
        key = (int(gap_h), int(min_n))
        x = self.c.get(key)
        if x and not force and time.time() - x[0] < 300: return x[1]
        E = self.E; gap = max(1, float(gap_h)) * 3600; out = []; cur = None
        R = E.db.q(f"SELECT id, path, kind, size, taken, lat, lon FROM files WHERE state='' AND kind IN ('photo','video') AND taken>0 AND {GOOD} ORDER BY taken")

        def close(ev):
            if ev and ev['n'] >= int(min_n): out.append(ev)
        for r in R:
            t = r['taken']
            if cur is None or t - cur['t1'] > gap:
                close(cur); cur = {'t0': t, 't1': t, 'n': 0, 'photo': 0, 'video': 0, 'b': 0, 'ids': [], 'la': 0.0, 'lo': 0.0, 'g': 0, 'dirs': {}}
            cur['t1'] = t; cur['n'] += 1; cur[r['kind']] += 1; cur['b'] += r['size'] or 0; cur['ids'].append(r['id'])
            if r['lat'] is not None and r['lon'] is not None and (r['lat'] or r['lon']): cur['la'] += r['lat']; cur['lo'] += r['lon']; cur['g'] += 1
            d = os.path.dirname(r['path']); cur['dirs'][d] = cur['dirs'].get(d, 0) + 1
        close(cur)
        for i, ev in enumerate(out):
            ids = ev.pop('ids'); k = len(ids); ev['cover'] = [ids[int(j * (k - 1) / 5)] for j in range(6)] if k >= 6 else ids
            ev['key'] = f"{int(ev['t0'])}-{int(ev['t1'])}"
            ev['gps'] = [round(ev['la'] / ev['g'], 4), round(ev['lo'] / ev['g'], 4)] if ev['g'] else None
            ev['days'] = int((ev['t1'] - ev['t0']) // 86400) + 1
            ev['dir'] = max(ev['dirs'].items(), key=lambda x: x[1])[0]; ev['ndirs'] = len(ev['dirs'])
            for k_ in ('la', 'lo', 'g', 'dirs'): ev.pop(k_)
        out.reverse()                                                                          # 最新的在最上面
        res = {'ok': True, 'rows': out, 'n': len(out), 'gap_h': gap_h, 'min_n': min_n}
        self.c[key] = (time.time(), res); return res

    def items(self, key, limit=2000):
        """這個活動的照片影片（照時間）：給輪播用（V0.1.95）."""
        try: t0, t1 = (float(x) for x in str(key).split('-'))
        except ValueError: return []
        return [[r[0], r[1]] for r in self.E.db.q(f"SELECT id, kind FROM files WHERE state='' AND kind IN ('photo','video') AND {GOOD} AND taken>=? AND taken<=? ORDER BY taken LIMIT ?", (t0, t1, int(limit)))]

    def name_of(self, t0, t1, label=''):
        a, b = time.localtime(t0), time.localtime(t1)
        s = time.strftime('%Y-%m-%d', a)
        if (a.tm_year, a.tm_yday) != (b.tm_year, b.tm_yday): s += ' ~ ' + (time.strftime('%m-%d', b) if a.tm_year == b.tm_year else time.strftime('%Y-%m-%d', b))
        label = re.sub(r'[\\/:*?"<>|]', '_', (label or '').strip())[:60]
        return s + (' ' + label if label else '')

    def plan(self, key, label='', dest=''):
        """預覽：把這個活動的照片影片搬到 <硬碟>\\照片影片_依活動\\2023-05-01 ~ 05-03 名稱\\（交給 Org 的 run／復原）."""
        E = self.E
        try: t0, t1 = (float(x) for x in str(key).split('-'))
        except ValueError: return {'ok': False, 'message': '不認得的活動'}
        name = self.name_of(t0, t1, label); org = E.org; pk = org._pkgs()
        moves = []; skip = {'不同硬碟': 0, '已經在對的位置': 0, '在遊戲／軟體資料夾裡': 0}; nb = 0
        for r in E.db.q(f"SELECT id, path, size FROM files WHERE state='' AND kind IN ('photo','video') AND {GOOD} AND taken>=? AND taken<=? ORDER BY taken", (t0, t1)):
            p = r['path']
            if org._in_pkg(p, pk): skip['在遊戲／軟體資料夾裡'] += 1; continue
            drv = os.path.splitdrive(p)[0]
            base = os.path.normpath(dest) if dest else (os.path.join(drv + '\\', '照片影片_依活動') if drv else os.path.join(os.path.dirname(os.path.dirname(p)), '照片影片_依活動'))
            if os.path.splitdrive(base)[0].lower() != drv.lower(): skip['不同硬碟'] += 1; continue
            d = os.path.join(base, name)
            if os.path.normcase(os.path.dirname(p)) == os.path.normcase(d): skip['已經在對的位置'] += 1; continue
            moves.append((r['id'], p, os.path.join(d, os.path.basename(p)), r['size'] or 0)); nb += r['size'] or 0
        org.plan_ = {'moves': moves, 't': time.time(), 'reason': '依活動整理'}
        return {'ok': True, 'n': len(moves), 'b': nb, 'skip': skip, 'name': name, 'sample': [{'src': a, 'dst': b} for _i, a, b, _s in moves[:30]],
                'dest_eg': os.path.dirname(moves[0][2]) if moves else ''}

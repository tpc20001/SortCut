"""🗺 照片地圖（V0.1.30，不准 import Qt）：有 GPS 的照片影片，照位置分群.
地圖底圖由手機瀏覽器直接跟 OpenStreetMap 拿（電腦端不連網也沒關係，只是沒有底圖）."""
import math, time


def cell_deg(z):
    """縮放 z 時，一群大約 64 像素寬 → 幾度."""
    return 64 * 360.0 / (256 * 2 ** max(0, min(19, int(z))))


class Geo:
    def __init__(self, E):
        self.E = E; self.c = {}

    def _cache(self, key, fn, sec=300):
        x = self.c.get(key)
        if x and time.time() - x[0] < sec: return x[1]
        v = fn(); self.c[key] = (time.time(), v); return v

    W = "state='' AND kind IN ('photo','video') AND lat IS NOT NULL AND lon IS NOT NULL AND NOT (lat=0 AND lon=0) AND lat BETWEEN -85 AND 85"

    def summary(self):
        def f():
            r = self.E.db.one(f"SELECT COUNT(*), COALESCE(SUM(kind='photo'),0), COALESCE(SUM(kind='video'),0), MIN(lat), MAX(lat), MIN(lon), MAX(lon) FROM files WHERE {self.W}") or (0,) * 7
            a = (self.E.db.one("SELECT COUNT(*) FROM files WHERE state='' AND kind IN ('photo','video')") or [0])[0]
            return {'n': r[0], 'photo': r[1], 'video': r[2], 'all': a, 'box': [r[3], r[4], r[5], r[6]] if r[0] else None}
        return self._cache('sum', f)

    def years(self):
        return [r[0] for r in self.E.db.q(f"SELECT DISTINCT strftime('%Y', taken, 'unixepoch', 'localtime') y FROM files WHERE {self.W} AND taken>0 ORDER BY y DESC") if r[0]]

    def _yw(self, year):
        try: y = int(year)
        except (TypeError, ValueError): return ''
        return f" AND taken>={time.mktime((y, 1, 1, 0, 0, 0, 0, 0, -1))} AND taken<{time.mktime((y + 1, 1, 1, 0, 0, 0, 0, 0, -1))}"

    def clusters(self, z, kind='', year=''):
        """整個世界照格子分群：[{lat, lon（平均）, n, id（最新一張）, k, t0, t1}]."""
        z = max(0, min(19, int(z))); d = cell_deg(z); kw = (f" AND kind='{kind}'" if kind in ('photo', 'video') else '') + self._yw(year)

        def f():
            R = self.E.db.q(f"SELECT CAST(FLOOR(lat/?) AS INTEGER) gy, CAST(FLOOR(lon/?) AS INTEGER) gx, COUNT(*), AVG(lat), AVG(lon), MAX(id), MIN(NULLIF(taken,0)), MAX(taken), "
                            f"SUM(kind='video') FROM files WHERE {self.W}{kw} GROUP BY gy, gx ORDER BY COUNT(*) DESC LIMIT 4000", (d, d))
            return [{'gy': r[0], 'gx': r[1], 'n': r[2], 'lat': round(r[3], 5), 'lon': round(r[4], 5), 'id': r[5], 't0': r[6] or 0, 't1': r[7] or 0, 'v': r[8]} for r in R]
        try: return self._cache(('cl', z, kind, year), f)
        except Exception:                                   # 很舊的 SQLite 沒有 FLOOR：用 Python 自己分
            G = {}
            for lat, lon, fid, t, k in self.E.db.q(f"SELECT lat, lon, id, taken, kind FROM files WHERE {self.W}{kw}"):
                key = (math.floor(lat / d), math.floor(lon / d)); g = G.get(key)
                if not g: g = G[key] = {'gy': key[0], 'gx': key[1], 'n': 0, 'la': 0.0, 'lo': 0.0, 'id': fid, 't0': 0, 't1': 0, 'v': 0}
                g['n'] += 1; g['la'] += lat; g['lo'] += lon; g['id'] = max(g['id'], fid); g['v'] += k == 'video'
                if t: g['t0'] = min(g['t0'] or t, t); g['t1'] = max(g['t1'], t)
            out = sorted(G.values(), key=lambda g: -g['n'])[:4000]
            for g in out: g['lat'] = round(g.pop('la') / g['n'], 5); g['lon'] = round(g.pop('lo') / g['n'], 5)
            return out

    def cell(self, z, gy, gx, offset=0, limit=60, kind='', year=''):
        """一群裡面的照片影片（照拍攝時間）."""
        d = cell_deg(z); la0, lo0 = int(gy) * d, int(gx) * d; kw = (f" AND kind='{kind}'" if kind in ('photo', 'video') else '') + self._yw(year)
        w = f"{self.W}{kw} AND lat>=? AND lat<? AND lon>=? AND lon<?"; a = (la0, la0 + d, lo0, lo0 + d)
        n = (self.E.db.one(f'SELECT COUNT(*) FROM files WHERE {w}', a) or [0])[0]
        R = [dict(r) for r in self.E.db.q(f'SELECT id, path, kind, size, taken, dur, lat, lon FROM files WHERE {w} ORDER BY taken, path LIMIT ? OFFSET ?', a + (int(limit), int(offset)))]
        return {'ok': True, 'n': n, 'rows': R}

    def places(self, z=9, limit=200):
        """「去過的地方」清單（大約 30 公里一格），照數量排：給電腦版、手機清單用."""
        return self.clusters(z)[:limit]

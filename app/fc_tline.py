"""🗓 那年今天＋時間軸（V0.1.26，不准 import Qt）：只用可靠的拍攝日期（EXIF／影片內建／檔名），修改日期不算."""
import time, calendar

GOOD = "date_src IN ('exif','video','name')"


class Timeline:
    def __init__(self, E):
        self.E = E; self.c = {}

    def _cache(self, key, fn, sec=600):
        x = self.c.get(key)
        if x and time.time() - x[0] < sec: return x[1]
        v = fn(); self.c[key] = (time.time(), v); return v

    def years(self):
        """每年、每月幾張照片／幾支影片."""
        def f():
            Y = {}
            for y, m, k, n, b in self.E.db.q(f"SELECT strftime('%Y', taken, 'unixepoch', 'localtime') y, strftime('%m', taken, 'unixepoch', 'localtime') m, kind, COUNT(*), SUM(size) "
                                             f"FROM files WHERE state='' AND kind IN ('photo','video') AND taken>0 AND {GOOD} GROUP BY y, m, kind"):
                if not y or not m or int(y) < 1980: continue
                M = Y.setdefault(y, {}).setdefault(m, {'photo': 0, 'video': 0, 'b': 0}); M[k] = n; M['b'] += b or 0
            return Y
        return self._cache('years', f)

    def month(self, y, m, offset=0, limit=60, kind=''):
        y, m = int(y), int(m); t0 = time.mktime((y, m, 1, 0, 0, 0, 0, 0, -1)); t1 = time.mktime((y + (m == 12), m % 12 + 1, 1, 0, 0, 0, 0, 0, -1))
        kw = "kind IN ('photo','video')" if kind not in ('photo', 'video') else f"kind='{kind}'"
        n = (self.E.db.one(f"SELECT COUNT(*) FROM files WHERE state='' AND {kw} AND {GOOD} AND taken>=? AND taken<?", (t0, t1)) or [0])[0]
        R = [dict(r) for r in self.E.db.q(f"SELECT id, path, kind, size, taken, dur, w, h, make, model FROM files WHERE state='' AND {kw} AND {GOOD} AND taken>=? AND taken<? ORDER BY taken LIMIT ? OFFSET ?",
                                          (t0, t1, int(limit), int(offset)))]
        return {'ok': True, 'y': y, 'm': m, 'n': n, 'rows': R, 'days': calendar.monthrange(y, m)[1]}

    def days(self, y):
        """🔥 熱力圖（V0.1.47）：這一年每天拍了幾個 → {'2023-05-01': n}."""
        y = int(y)
        def f():
            return {d: n for d, n in self.E.db.q(f"SELECT strftime('%Y-%m-%d', taken, 'unixepoch', 'localtime') d, COUNT(*) FROM files WHERE state='' AND kind IN ('photo','video') "
                                                 f"AND taken>0 AND {GOOD} AND strftime('%Y', taken, 'unixepoch', 'localtime')=? GROUP BY d", (str(y),)) if d}
        return self._cache(('days', y), f)

    def day(self, ymd, offset=0, limit=120):
        y, m, d = (int(x) for x in str(ymd).split('-')); t0 = time.mktime((y, m, d, 0, 0, 0, 0, 0, -1)); t1 = t0 + 86400
        R = [dict(r) for r in self.E.db.q(f"SELECT id, path, kind, size, taken, dur FROM files WHERE state='' AND kind IN ('photo','video') AND {GOOD} AND taken>=? AND taken<? ORDER BY taken LIMIT ? OFFSET ?",
                                          (t0, t1, int(limit), int(offset)))]
        return {'ok': True, 'd': ymd, 'rows': R}

    def on_this_day(self, limit=60):
        """那年今天：今天的月-日，往年拍的（每年最多 12 個）."""
        md = time.strftime('%m-%d'); ty = time.strftime('%Y')

        def f():
            R = [dict(r) for r in self.E.db.q(f"SELECT id, path, kind, size, taken, dur FROM files WHERE state='' AND kind IN ('photo','video') AND taken>0 AND {GOOD} "
                                              f"AND strftime('%m-%d', taken, 'unixepoch', 'localtime')=? AND strftime('%Y', taken, 'unixepoch', 'localtime')<? ORDER BY taken DESC", (md, ty))]
            Y = {}
            for r in R:
                y = time.strftime('%Y', time.localtime(r['taken'])); L = Y.setdefault(y, [])
                if len(L) < 12: L.append(r)
            return {'md': md, 'years': [{'y': y, 'ago': int(ty) - int(y), 'n': sum(1 for r in R if time.strftime('%Y', time.localtime(r['taken'])) == y), 'rows': L} for y, L in sorted(Y.items(), reverse=True)], 'n': len(R)}
        return self._cache('otd' + md, f, 1800)

"""📂 瀏覽資料夾（V0.1.51，不准 import Qt）：在手機上一層一層看「要整理的資料夾」裡有什麼（照資料庫，不用再掃硬碟）."""
import os, time
import fc_fcore as fcore


class Browse:
    def __init__(self, E):
        self.E = E; self.c = {}

    def ls(self, path='', offset=0, limit=240):
        E = self.E; roots = E.fc_list('roots')
        if not path:
            out = []
            for r in roots:
                p = r.rstrip('\\/') + os.sep
                n, b = E.db.one("SELECT COUNT(*), COALESCE(SUM(size),0) FROM files WHERE state IN ('','pkg','skip') AND path LIKE ? ESCAPE '^'", (fcore.like_esc(p) + '%',)) or (0, 0)
                out.append({'name': r, 'path': r, 'n': n, 'b': b, 'm': 0})
            return {'ok': True, 'path': '', 'crumbs': [], 'dirs': out, 'files': [], 'nf': 0, 'other': 0}
        path = os.path.normpath(path); pre = path.rstrip('\\/') + os.sep; pl = pre.lower()
        key = (pl, int(offset)); x = self.c.get(key)
        if x and time.time() - x[0] < 60: return x[1]
        D = {}; F = []; other = 0
        for r in E.db.q("SELECT id, path, size, kind, taken, mtime, dur, fav FROM files WHERE state IN ('','pkg','skip') AND path LIKE ? ESCAPE '^'", (fcore.like_esc(pre) + '%',)):
            p = r['path']
            if not p.lower().startswith(pl): continue
            rest = p[len(pre):]
            if os.sep in rest:
                c = rest.split(os.sep, 1)[0]; d = D.setdefault(c, [0, 0, 0]); d[0] += 1; d[1] += r['size'] or 0; d[2] += r['kind'] in ('photo', 'video')
            elif r['kind'] in ('photo', 'video'): F.append(dict(r))
            else: other += 1
        F.sort(key=lambda f: os.path.basename(f['path']).lower())
        root = next((r for r in roots if pl.startswith(r.rstrip('\\/').lower() + os.sep) or pl == r.rstrip('\\/').lower() + os.sep), '')
        crumbs = []
        if root:
            crumbs.append({'name': root, 'path': root}); cur = root.rstrip('\\/')
            for part in path[len(root.rstrip('\\/')):].strip('\\/').split(os.sep):
                if part: cur = cur + os.sep + part; crumbs.append({'name': part, 'path': cur})
        out = {'ok': True, 'path': path, 'crumbs': crumbs, 'dirs': [{'name': k, 'path': pre + k, 'n': v[0], 'b': v[1], 'm': v[2]} for k, v in sorted(D.items(), key=lambda x: x[0].lower())],
               'files': F[int(offset):int(offset) + int(limit)], 'nf': len(F), 'other': other}
        self.c[key] = (time.time(), out)
        if len(self.c) > 50: self.c.clear()
        return out

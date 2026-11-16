"""💾 備份檢查（V0.1.38，不准 import Qt）：你的照片影片，哪些「只有一份」（硬碟壞了就沒了）、哪些別顆硬碟也有.

不用另外算：比對重複時已經知道 ——
  大小跟誰都不一樣的 → 一定只有一份；
  大小一樣的有算指紋 → 同一個指紋在「別顆硬碟」也有＝有備份；只在同一顆硬碟＝副本跟本尊會一起壞。
遊戲／軟體裡的素材不算（state='pkg'）。
"""
import os, time
from collections import defaultdict


def drive_of(p, roots):
    d = os.path.splitdrive(p)[0]
    if d: return d.upper()
    for r in roots:                                         # 沒有磁碟代號（測試／網路路徑）：用「要整理的資料夾」當一顆
        if p.startswith(r.rstrip('/\\') + os.sep): return r
    return '?'


class Backup:
    def __init__(self, E):
        self.E = E; self.c = None

    def check(self, force=False):
        if self.c and not force and time.time() - self.c[0] < 300: return self.c[1]
        E = self.E; roots = E.fc_list('roots')
        dup_sizes = {r[0] for r in E.db.q("SELECT size FROM files WHERE state IN ('','quar') AND size>0 GROUP BY size HAVING COUNT(*)>1")}
        H = defaultdict(set); C = defaultdict(int)                               # (size, hash) → 在哪幾顆硬碟、幾份（隔離區裡的也算：還在硬碟上）
        rows = E.db.q("SELECT id, path, size, hash, kind, state FROM files WHERE state IN ('','quar') AND size>0 AND kind IN ('photo','video')")
        for r in rows:
            if r['hash'] and not r['hash'].startswith('!'): key = (r['size'], r['hash']); H[key].add(drive_of(r['path'], roots)); C[key] += 1
        D = defaultdict(lambda: {'ok': [0, 0], 'same': [0, 0], 'one': [0, 0], 'wait': [0, 0]}); F = defaultdict(lambda: [0, 0])
        for r in rows:
            if r['state'] != '': continue
            dv = drive_of(r['path'], roots); sz = r['size']
            if sz not in dup_sizes: k = 'one'
            elif not r['hash'] or r['hash'].startswith('!'): k = 'wait'                      # 還沒比對完
            else:
                key = (sz, r['hash']); k = 'ok' if len(H[key]) > 1 else ('same' if C[key] > 1 else 'one')
            x = D[dv][k]; x[0] += 1; x[1] += sz
            if k in ('one', 'same'): f = F[(dv, os.path.dirname(r['path']))]; f[0] += 1; f[1] += sz
        tot = {k: [sum(D[d][k][0] for d in D), sum(D[d][k][1] for d in D)] for k in ('ok', 'same', 'one', 'wait')}
        top = sorted(([d, p, n, b] for (d, p), (n, b) in F.items()), key=lambda x: -x[3])[:60]
        out = {'ok': True, 'drives': [dict(drive=d, **v) for d, v in sorted(D.items())], 'tot': tot, 'top': top, 'ndrives': len(D), 't': time.time()}
        self.c = (time.time(), out); return out

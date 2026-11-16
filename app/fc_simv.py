"""🎬 相似影片（V0.1.33，不准 import Qt）：不是一模一樣、但內容一樣的影片（重新壓縮、轉檔、改解析度、LINE／FB 傳過一次的）.

做法：用分類預覽已經做好的 16 格（SortCut 的或自己做的），取第 4、8、12 格 → 各算一個 dHash（64 位元），三個接起來＝192 位元指紋。
長度要差不多（差 2 秒或 2% 以內），而且三格加起來差的位元夠少，才算相似。指紋算過就存起來（vsig），下次不用再算。
還沒有 16 格預覽的影片先跳過（分類頁的背景會慢慢做）。
"""
import os, subprocess, time

import fc_fcore as fcore
import fc_simi as simi

THR = {1: 5, 2: 8, 3: 11}          # 192 位元裡最多差幾個（12 段×16 位元：≤11 一定有一段一模一樣，鴿籠原理）
PICK = (3, 7, 11)                  # 16 格裡取哪幾格（大約 25%、50%、75%）


def frame_sig(ff, g):
    """從 16 格的大張切出 3 格 → 192 位元指紋（48 個 16 進位字）；失敗回 ''."""
    C = g.get('cells') or []
    if len(C) < 12 or not ff: return ''
    cols, rows = int(g.get('cols') or 4), int(g.get('rows') or 4); args = []; fl = []
    for k, i in enumerate(PICK):
        c = C[min(i, len(C) - 1)]; args += ['-i', fcore.lp(g['sheets'][c['s']])]
        fl.append(f"[{k}:v]crop=iw/{cols}:ih/{rows}:iw/{cols}*{c['c']}:ih/{rows}*{c['r']},scale=9:8:flags=area,format=gray[f{k}]")
    fc = ';'.join(fl) + f";{''.join(f'[f{k}]' for k in range(len(PICK)))}vstack=inputs={len(PICK)}[o]"
    try:
        r = subprocess.run([ff, '-hide_banner', '-v', 'error'] + args + ['-filter_complex', fc, '-map', '[o]', '-frames:v', '1', '-f', 'rawvideo', '-'],
                           capture_output=True, timeout=60, creationflags=fcore.NO_WINDOW | (0x00004000 if os.name == 'nt' else 0), stdin=subprocess.DEVNULL)
        px = r.stdout
        if len(px) < 72 * len(PICK): return ''
        out = ''
        for k in range(len(PICK)):
            b = px[72 * k:72 * (k + 1)]; bits = 0
            for y in range(8):
                for x in range(8): bits = (bits << 1) | (1 if b[y * 9 + x] > b[y * 9 + x + 1] else 0)
            out += f'{bits:016x}'
        return out
    except Exception: return ''


class SimV(simi.Sim):
    GRP, SKIP, KV, KIND, REASON, CFG, NAME, UNIT, SEG = 'simv_grp', 'simv_skip', 'simv', 'video', '相似影片', 'simv_level', '🎬 相似影片', '部', 12

    def thr(self, lv): return THR.get(lv, 11)

    def close(self, i, j, H, X, thr):
        a, b = X[i], X[j]
        if abs(a - b) > max(2.0, 0.02 * max(a, b)): return False                   # 長度差太多：不是同一部
        return bin(H[i] ^ H[j]).count('1') <= thr

    def _sigs(self, lose, S):
        E = self.E; ff = E.ff()[0]; vc = E.vc
        have = {r[0]: (r[1], r[2]) for r in E.db.q('SELECT fid, size, sig FROM vsig')}
        R = E.db.q("SELECT id, path, size, dur FROM files WHERE state='' AND kind='video' AND size>0 AND dur>0 AND health NOT IN ('broken','partial','zero')")
        S.update(phase='算指紋（用分類預覽的 16 格）…', total=len(R), n=0); ids = []; H = []; X = []; nog = 0; new = 0; t1 = time.time()
        for r in R:
            if S.get('cancel') or E.stop_all: raise InterruptedError
            S['n'] += 1; fid = r[0]
            if fid in lose: continue
            h = have.get(fid)
            if not h or h[0] != r[2]:
                if not ff: continue
                if vc.state_of(fid, r[1], r[2]) != 0: nog += 1; continue                # 還沒有 16 格：先跳過
                g = vc.grid(fid, build=False); sig = frame_sig(ff, g) if g.get('ok') else ''
                E.db.x('INSERT OR REPLACE INTO vsig(fid, size, sig) VALUES(?,?,?)', (fid, r[2], sig)); h = (r[2], sig); new += 1
                if time.time() - t1 > 1: t1 = time.time(); S['phase'] = f'算指紋…（新算 {new:,} 部）'
            if not h[1]: continue
            v = int(h[1], 16)
            if all(simi._flat((v >> s) & 0xFFFFFFFFFFFFFFFF) for s in (0, 64, 128)): continue      # 三格都全黑／純色
            ids.append(fid); H.append(v); X.append(float(r[3] or 0))
        S['extra'] = {'no_grid': nog, 'new_sig': new}
        S.update(phase='比對中…', n=0)
        return ids, H, X

    def _files(self, gid):
        F = [dict(r) for r in self.E.db.q(f"SELECT f.id, f.path, f.size, f.w, f.h, f.taken, f.mtime, s.sig AS dhash, f.name_date, f.make, f.model, f.dur, f.fav FROM {self.GRP} g "
                                          f"JOIN files f ON f.id=g.fid LEFT JOIN vsig s ON s.fid=f.id WHERE g.gid=? AND f.state=''", (int(gid),))]
        return F

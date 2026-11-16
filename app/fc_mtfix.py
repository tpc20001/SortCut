"""🕒 修正修改日期（V0.1.88，不准 import Qt）：照片影片的「修改日期」常常是複製、傳輸的時間；改成真正的拍攝日期，
Windows 檔案總管、別的相簿軟體照日期排就對了。只改檔案的日期屬性（不動內容、不搬），每一筆都記下來，可以整批改回去."""
import os, time, threading

import fc_fcore as fcore

GOOD = "date_src IN ('exif','video','name')"


class MtFix:
    def __init__(self, E, old=None):
        self.E = E; self.st = old.st if old is not None else {}

    def plan(self, kinds='both', min_days=1):
        K = {'photo': "kind='photo'", 'video': "kind='video'"}.get(kinds, "kind IN ('photo','video')")
        R = self.E.db.q(f"SELECT id, path, mtime, taken FROM files WHERE state='' AND {K} AND {GOOD} AND taken>315532800 AND ABS(mtime-taken)>? ORDER BY path", (float(min_days) * 86400,))
        undo = (self.E.db.one('SELECT COUNT(*) FROM mt_fix WHERE undone=0') or [0])[0]
        return {'ok': True, 'n': len(R), 'sample': [{'path': r['path'], 'old': r['mtime'], 'new': r['taken']} for r in R[:40]], 'undo': undo, 'st': dict(self.st)}

    def start(self, kinds='both', min_days=1):
        if self.st.get('run'): return {'ok': False, 'message': '已經在改了'}
        K = {'photo': "kind='photo'", 'video': "kind='video'"}.get(kinds, "kind IN ('photo','video')")
        R = [dict(r) for r in self.E.db.q(f"SELECT id, path, mtime, taken FROM files WHERE state='' AND {K} AND {GOOD} AND taken>315532800 AND ABS(mtime-taken)>?", (float(min_days) * 86400,))]
        self.st.clear(); self.st.update(run=True, n=0, ok=0, bad=0, total=len(R))
        threading.Thread(target=self._job, args=(R, False), name='MtFix', daemon=True).start()
        return {'ok': True, 'message': f'🕒 開始修正 {len(R):,} 個的修改日期（背景做）'}

    def undo(self):
        if self.st.get('run'): return {'ok': False, 'message': '正在忙'}
        R = [dict(r) for r in self.E.db.q('SELECT m.id AS mid, m.fid AS id, f.path, m.old AS mtime, m.new AS taken FROM mt_fix m JOIN files f ON f.id=m.fid WHERE m.undone=0')]
        self.st.clear(); self.st.update(run=True, n=0, ok=0, bad=0, total=len(R))
        threading.Thread(target=self._job, args=(R, True), name='MtFixUndo', daemon=True).start()
        return {'ok': True, 'message': f'↩ 把 {len(R):,} 個改回原本的修改日期（背景做）'}

    def _job(self, R, back):
        E = self.E; S = self.st; t = E.task('op', '🕒 ' + ('改回修改日期' if back else '修正修改日期'))
        try:
            for r in R:
                if E.stop_all or S.get('cancel'): break
                S['n'] += 1; p = fcore.lp(r['path']); new = r['mtime'] if back else r['taken']
                try:
                    st = os.stat(p); os.utime(p, (st.st_atime, new))
                    E.db.x('UPDATE files SET mtime=? WHERE id=?', (new, r['id']))
                    if back: E.db.x('UPDATE mt_fix SET undone=1 WHERE id=?', (r['mid'],))
                    else: E.db.x('INSERT INTO mt_fix(t, fid, old, new, undone) VALUES(?,?,?,?,0)', (time.time(), r['id'], r['mtime'], r['taken']))
                    S['ok'] += 1
                except OSError: S['bad'] += 1
                if S['n'] % 200 == 0: t['msg'] = f"{S['n']:,}／{S['total']:,}"
            msg = f"{'改回' if back else '修正'}了 {S['ok']:,} 個" + (f"，{S['bad']} 個改不了（唯讀或不見了）" if S['bad'] else '')
            E.done(t, 'done', msg); E.oplog('修正修改日期', msg); S['msg'] = msg
        except Exception as ex: E.log.err('🕒 修正修改日期'); E.done(t, 'fail', str(ex)); S['msg'] = str(ex)
        finally: S['run'] = False

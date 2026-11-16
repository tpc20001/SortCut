"""📅 依日期整理（V0.1.25，不准 import Qt）：把照片／影片照拍攝日期搬進「年／月」資料夾.

先「預覽」（不動任何檔）：會搬幾個、每年每月幾個、前 60 個會從哪裡搬到哪裡、哪些跳過（不同硬碟、已經在對的位置、沒有可靠日期…）
再按「開始整理」才搬；只在同一顆硬碟搬（瞬間完成），每一筆都記在 moves（「📦 隔離區」頁可以復原）。
"""
import os, re, time, threading

import fc_fcore as fcore

PATTERNS = {'ym': ('年\\年-月', lambda y, m: os.path.join(f'{y}', f'{y}-{m:02d}')), 'y_m': ('年\\月', lambda y, m: os.path.join(f'{y}', f'{m:02d}')),
            'y': ('年', lambda y, m: f'{y}'), 'ym1': ('年-月（一層）', lambda y, m: f'{y}-{m:02d}')}
GOOD_SRC = ('exif', 'video', 'name')                 # 可靠的拍攝日期（修改日期 mtime 不可靠：複製、傳輸都會變）
UNKNOWN = '日期不明'


class Org:
    def __init__(self, E, old=None):
        self.E = E; self.st = old.st if old is not None else {}; self.plan_ = old.plan_ if old is not None else None

    def plan(self, src='', dest='', pattern='ym', kinds='both', trust_mtime=False, unknown='skip', only_cam=False):
        """預覽（不動檔案）。src＝只整理這個資料夾底下的（空的＝全部要整理的資料夾）；dest＝整理到哪（空的＝每顆硬碟的 \\照片影片_依日期）."""
        E = self.E; src = os.path.normpath(src.strip()) if src and src.strip() else ''; dest = os.path.normpath(dest.strip()) if dest and dest.strip() else ''
        if pattern not in PATTERNS: pattern = 'ym'
        K = {'photo': ("'photo'",), 'video': ("'video'",)}.get(kinds, ("'photo'", "'video'"))
        W = [f"kind IN ({','.join(K)})", "state=''", 'size>0', "health NOT IN ('broken','zero')"]; A = []
        if src: W.append("(path LIKE ? ESCAPE '^' OR path LIKE ? ESCAPE '^')"); A += [fcore.like_esc(src.rstrip('\\/')) + '\\%', fcore.like_esc(src.rstrip('\\/')) + '/%']
        if only_cam: W.append("src='camera'")                                       # 只整理自己拍的（V0.1.83）：截圖、下載、LINE…不動
        pk = self._pkgs()
        moves = []; skip = {'沒有可靠日期': 0, '不同硬碟': 0, '已經在對的位置': 0, '在遊戲／軟體資料夾裡': 0}; Y = {}; nb = 0
        for r in E.db.q(f"SELECT id, path, size, taken, mtime, date_src FROM files WHERE {' AND '.join(W)} ORDER BY path", A):
            p = r['path']
            if self._in_pkg(p, pk): skip['在遊戲／軟體資料夾裡'] += 1; continue
            ok = r['date_src'] in GOOD_SRC or (trust_mtime and r['mtime'])
            t = r['taken'] if r['date_src'] in GOOD_SRC else (r['mtime'] if trust_mtime else None)
            if not ok or not t:
                if unknown != 'move': skip['沒有可靠日期'] += 1; continue
                sub = UNKNOWN; key = UNKNOWN
            else:
                try: lt = time.localtime(t); y, m = lt.tm_year, lt.tm_mon
                except (OverflowError, OSError, ValueError): skip['沒有可靠日期'] += 1; continue
                if y < 1980 or y > time.localtime().tm_year + 1: skip['沒有可靠日期'] += 1; continue
                sub = PATTERNS[pattern][1](y, m); key = f'{y}-{m:02d}'
            base = dest or self._default_dest(p)
            if os.path.splitdrive(base)[0].lower() != os.path.splitdrive(p)[0].lower(): skip['不同硬碟'] += 1; continue
            d = os.path.join(base, sub)
            if os.path.normcase(os.path.dirname(p)) == os.path.normcase(d): skip['已經在對的位置'] += 1; continue
            moves.append((r['id'], p, os.path.join(d, os.path.basename(p)), r['size'] or 0)); nb += r['size'] or 0
            x = Y.setdefault(key, [0, 0]); x[0] += 1; x[1] += r['size'] or 0
        self.plan_ = {'moves': moves, 't': time.time(), 'args': dict(src=src, dest=dest, pattern=pattern, kinds=kinds, trust_mtime=trust_mtime, unknown=unknown, only_cam=only_cam)}
        return {'ok': True, 'n': len(moves), 'b': nb, 'skip': skip, 'months': sorted(Y.items()), 'sample': [{'src': a, 'dst': b} for _i, a, b, _s in moves[:60]],
                'dest_eg': dest or (self._default_dest(moves[0][1]) if moves else ''), 'pattern': PATTERNS[pattern][0]}

    def _default_dest(self, p):
        drv = os.path.splitdrive(p)[0]
        return os.path.join(drv + '\\', '照片影片_依日期') if drv else os.path.join(os.path.dirname(os.path.dirname(p)), '照片影片_依日期')

    def _pkgs(self):
        S = self.E.ana_result(); gen = S.get('gen')
        if not gen: return set()
        return {r[0].lower().rstrip('\\/') for r in self.E.db.q("SELECT path FROM ana_dir WHERE gen=? AND pkg IN ('game','app','dev','system')", (gen,))}

    @staticmethod
    def _in_pkg(p, P):
        if not P: return False
        s = p.lower(); i = s.rfind(os.sep)
        while i > 0:
            if s[:i] in P: return True
            i = s.rfind(os.sep, 0, i)
        return False

    def run(self):
        P = self.plan_
        if not P or not P['moves']: return {'ok': False, 'message': '先按「預覽」'}
        if time.time() - P['t'] > 1800: return {'ok': False, 'message': '預覽太久以前了，請重新預覽一次'}
        if self.st.get('run'): return {'ok': False, 'message': '已經在整理了'}
        self.st.clear(); self.st.update(run=True, n=0, ok=0, bad=0, b=0, total=len(P['moves']), err=[])
        why = P.get('reason') or '依日期整理'
        threading.Thread(target=self._job, args=(P['moves'], why), name='OrgByDate', daemon=True).start(); self.plan_ = None
        return {'ok': True, 'message': f'{ {"依日期整理": "📅", "改檔名": "📝"}.get(why, "🏷") } 開始{why} {len(P["moves"]):,} 個（背景做）'}

    # ---------------------------------------------------------------- 🏷 依來源整理（V0.1.37）：截圖、抖音、LINE…各放一個資料夾
    def sources(self):
        R = self.E.db.q("SELECT src, kind, COUNT(*), COALESCE(SUM(size),0) FROM files WHERE state='' AND kind IN ('photo','video') AND size>0 GROUP BY src, kind")
        out = {}
        for s, k, n, b in R:
            s = s or ''; x = out.setdefault(s, {'src': s, 'name': fcore.SRC_NM.get(s, '還沒讀拍攝資訊' if not s else s), 'photo': 0, 'video': 0, 'b': 0})
            x[k] = n; x['b'] += b
        return {'ok': True, 'rows': sorted(out.values(), key=lambda x: -(x['photo'] + x['video'])), 'st': {k: v for k, v in self.st.items()}}

    def plan_src(self, srcs, dest='', keep_dir=True):
        r"""預覽：選的來源 → <硬碟>\照片影片_依來源\<來源名>\<原本的資料夾名>\檔名."""
        E = self.E; srcs = [s for s in (srcs or []) if s in fcore.SRC_NM]
        if not srcs: return {'ok': False, 'message': '先勾要整理的來源'}
        dest = os.path.normpath(dest.strip()) if dest and dest.strip() else ''; pk = self._pkgs()
        moves = []; skip = {'不同硬碟': 0, '已經在對的位置': 0, '在遊戲／軟體資料夾裡': 0}; C = {}; nb = 0
        for r in E.db.q(f"SELECT id, path, size, src FROM files WHERE state='' AND kind IN ('photo','video') AND size>0 AND src IN ({','.join('?' * len(srcs))}) ORDER BY path", srcs):
            p = r['path']
            if self._in_pkg(p, pk): skip['在遊戲／軟體資料夾裡'] += 1; continue
            nm = re.sub(r'^\W+\s*', '', fcore.SRC_NM[r['src']]).replace('／', '、')
            base = dest or self._src_dest(p)
            if os.path.splitdrive(base)[0].lower() != os.path.splitdrive(p)[0].lower(): skip['不同硬碟'] += 1; continue
            d = os.path.join(base, nm, os.path.basename(os.path.dirname(p)) or '根目錄') if keep_dir else os.path.join(base, nm)
            if os.path.normcase(os.path.normpath(p)).startswith(os.path.normcase(os.path.join(base, nm)) + os.sep): skip['已經在對的位置'] += 1; continue
            moves.append((r['id'], p, os.path.join(d, os.path.basename(p)), r['size'] or 0)); nb += r['size'] or 0
            x = C.setdefault(nm, [0, 0]); x[0] += 1; x[1] += r['size'] or 0
        self.plan_ = {'moves': moves, 't': time.time(), 'reason': '依來源整理'}
        return {'ok': True, 'n': len(moves), 'b': nb, 'skip': skip, 'months': sorted(C.items(), key=lambda x: -x[1][0]), 'sample': [{'src': a, 'dst': b} for _i, a, b, _s in moves[:60]],
                'dest_eg': dest or (self._src_dest(moves[0][1]) if moves else '')}

    # ---------------------------------------------------------------- 📝 依拍攝日期改檔名（V0.1.39）：留在原資料夾、只改名字
    RN = {'dash': ('2023-05-01 14.30.05', '%Y-%m-%d %H.%M.%S'), 'us': ('2023-05-01_143005', '%Y-%m-%d_%H%M%S'), 'cam': ('20230501_143005', '%Y%m%d_%H%M%S')}

    def plan_rename(self, src='', fmt='dash', keep_old=False, kinds='both'):
        E = self.E; src = os.path.normpath(src.strip()) if src and src.strip() else ''
        f = self.RN.get(fmt, self.RN['dash'])[1]
        K = {'photo': ("'photo'",), 'video': ("'video'",)}.get(kinds, ("'photo'", "'video'"))
        W = [f"kind IN ({','.join(K)})", "state=''", 'size>0', "date_src IN ('exif','video','name')", 'taken>0']; A = []
        if src: W.append("(path LIKE ? ESCAPE '^' OR path LIKE ? ESCAPE '^')"); A += [fcore.like_esc(src.rstrip('\\/')) + '\\%', fcore.like_esc(src.rstrip('\\/')) + '/%']
        pk = self._pkgs(); moves = []; skip = {'已經是這種名字': 0, '在遊戲／軟體資料夾裡': 0, '日期怪怪的': 0}; used = set(); nb = 0
        for r in E.db.q(f"SELECT id, path, size, taken, date_src FROM files WHERE {' AND '.join(W)} ORDER BY path", A):
            p = r['path']
            if self._in_pkg(p, pk): skip['在遊戲／軟體資料夾裡'] += 1; continue
            try: lt = time.localtime(r['taken'])
            except (OverflowError, OSError, ValueError): skip['日期怪怪的'] += 1; continue
            if lt.tm_year < 1980 or lt.tm_year > time.localtime().tm_year + 1: skip['日期怪怪的'] += 1; continue
            d, nm = os.path.split(p); stem, ext = os.path.splitext(nm); new = time.strftime(f, lt)
            day_only = r['date_src'] == 'name' and not (lt.tm_hour or lt.tm_min or lt.tm_sec)          # 檔名只有日期、沒有時間：只用日期＋保留原檔名
            if day_only: new = time.strftime(f.split(' ')[0].split('_')[0] if fmt != 'cam' else '%Y%m%d', lt)
            if stem.startswith(new) and not day_only: skip['已經是這種名字'] += 1; continue
            if day_only and stem.startswith(new + ' '): skip['已經是這種名字'] += 1; continue
            if keep_old or day_only: new += ' ' + stem
            cand = new + ext.lower(); i = 1
            while os.path.normcase(os.path.join(d, cand)) in used: i += 1; cand = f'{new}_{i}{ext.lower()}'      # 同一秒拍好幾張（連拍）：加 _2 _3
            used.add(os.path.normcase(os.path.join(d, cand)))
            moves.append((r['id'], p, os.path.join(d, cand), r['size'] or 0)); nb += r['size'] or 0
        self.plan_ = {'moves': moves, 't': time.time(), 'reason': '改檔名'}
        return {'ok': True, 'n': len(moves), 'b': nb, 'skip': skip, 'months': [], 'sample': [{'src': a, 'dst': b} for _i, a, b, _s in moves[:60]], 'dest_eg': '（留在原本的資料夾）',
                'fmts': {k: v[0] for k, v in self.RN.items()}}

    def _src_dest(self, p):
        drv = os.path.splitdrive(p)[0]
        return os.path.join(drv + '\\', '照片影片_依來源') if drv else os.path.join(os.path.dirname(os.path.dirname(p)), '照片影片_依來源')

    def _job(self, M, why='依日期整理'):
        E = self.E; S = self.st; t = E.task('op', ('📅 ' if why == '依日期整理' else '🏷 ') + why)
        try:
            for fid, src, dst, size in M:
                if E.stop_all or S.get('cancel'): break
                S['n'] += 1
                r = E.db.one("SELECT path FROM files WHERE id=? AND state=''", (fid,))
                if not r or r[0] != src: S['bad'] += 1; S['err'].append(f'{os.path.basename(src)}：預覽之後被動過了，跳過'); continue
                try: real = fcore.move(src, dst)
                except Exception as ex: S['bad'] += 1; S['err'].append(f'{os.path.basename(src)}：{ex}'); continue
                try:
                    E.db.x('UPDATE files SET path=? WHERE id=?', (real, fid))
                    E.db.x('INSERT INTO moves(t,fid,src,dst,reason) VALUES(?,?,?,?,?)', (time.time(), fid, src, real, why))
                except Exception as ex:
                    try: fcore.move(real, src, rename=False)
                    except Exception: E.log.err(f'📅 資料庫寫不進去，檔案也搬不回去：{real}')
                    S['bad'] += 1; S['err'].append(f'{os.path.basename(src)}：資料庫 {ex}'); continue
                S['ok'] += 1; S['b'] += size; t['msg'] = f'{S["ok"]:,}／{S["total"]:,}'
                try: fcore.rmdirs_up(os.path.dirname(src), os.path.splitdrive(src)[0] + '\\' if os.path.splitdrive(src)[0] else os.path.dirname(os.path.dirname(src)))
                except Exception: pass
            msg = f'整理好 {S["ok"]:,} 個（{S["b"] / 1e9:.2f} GB）' + (f'，{S["bad"]} 個沒辦法：{S["err"][0]}' if S['bad'] else '')
            E.done(t, 'stop' if S.get('cancel') else 'done', msg); E.oplog(why, msg); E.log.w(why + '：' + msg); S['msg'] = msg
        except Exception as ex: E.log.err(why); E.done(t, 'fail', str(ex)); S['msg'] = str(ex)
        finally: S['run'] = False; E.fc_kick()

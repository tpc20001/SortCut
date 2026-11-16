"""🧭 重複檔：用資料夾的角度看（V0.2.16，不准 import Qt）.

七萬多組重複檔，大多是「整包資料夾被複製了好幾次」（備份、手機倒出來、硬碟直接複製）。這裡：
1. 把一組一組的重複，往上合成「哪兩個資料夾（整棵）是彼此的複本」：子資料夾名字一樣就一路往上合
2. 每一對建議留哪邊：你取名字整理過的、已經分類過的 > 原始資料夾 > 備份／整台倒出來／救援出來的
3. 動作：保留一邊（另一邊「這邊也有的」搬隔離區，獨有的不動）、或🔀 合併（另一邊獨有的搬過來、保留子資料夾，重複的搬隔離區）
4. 每個最上層資料夾：多少在別的地方也有、大多在哪
安全：搬之前每個檔再確認一次「保留那邊真的還有一模一樣的」，絕不會把最後一份搬走。只在同一顆硬碟搬，全部記在 moves 可以復原。
"""
import os, re, time, threading
from collections import defaultdict
import fc_fcore as fcore
import fc_vgroup as vgroup

MAX_COPIES = 12
LOW = ('recup_dir', 'found.000', '救援', '恢復', '恢复', 'recovered', 'recovery', 'lost.dir', '$recycle')


def _parts(p):
    return [x for x in re.split(r'[\\/]', p) if x]


class DupPlan:
    def __init__(self, E, old=None):
        self.E = E; self.st = old.st if old is not None and getattr(old, 'st', None) is not None else {}; self.c = None

    # ------------------------------------------------------------ 評分：留哪邊
    def roots(self):
        return [vgroup.rootnorm(r) for r in self.E.fc_list('roots')]

    def top_of(self, p):
        """最上層資料夾（要整理的資料夾底下第一層）."""
        for r in sorted(self.roots(), key=len, reverse=True):
            if fcore.under(p, r):
                rest = _parts(p[len(r):]); return os.path.join(r, rest[0]) if len(rest) > 1 else r
        pp = _parts(p); return os.sep.join(pp[:2]) if len(pp) > 2 else os.path.dirname(p)

    def score(self, d):
        """越高越該留：(分數, 原因)."""
        lo = d.lower(); s = 0; why = []
        if 'filecompare_分類' in lo or os.sep + vgroup.KEEP_CAT in d or '/' + vgroup.KEEP_CAT in d: s += 6; why.append('已經分類過')
        try:
            pk = self.E.vg.pack_of(d)
            if pk: s += 3; why.append(f'在你整理過的「{os.path.basename(pk)}」')
        except Exception: pass
        P = [x.lower() for x in self.E.fc_list('keep_prio')]
        for i, k in enumerate(P):
            if lo == k or lo.startswith(k.rstrip('\\/') + os.sep) or lo.startswith(k.rstrip('\\/') + '/'): s += max(1, 4 - i); why.append('在「優先保留」清單'); break
        parts = [x for x in _parts(d)]
        if any(any(w in x.lower() for w in LOW) for x in parts): s -= 5; why.append('是救援出來的')
        elif any(vgroup.is_dump(x) for x in parts[1:]): s -= 2; why.append('在備份／整台倒出來的資料夾')
        s -= len(parts) * 0.05
        return s, why

    # ------------------------------------------------------------ 分析
    def analyze(self, force=False):
        if self.c and not force and time.time() - self.c[0] < 600: return self.c[1]
        E = self.E; t0 = time.time()
        G = defaultdict(list)
        for fid, p, size, h in E.db.q("SELECT id, path, size, hash FROM files WHERE state='' AND hash IS NOT NULL AND hash NOT LIKE '!%' AND size>0 AND "
                                      "(size,hash) IN (SELECT size,hash FROM files WHERE state='' AND hash IS NOT NULL AND hash NOT LIKE '!%' AND size>0 GROUP BY size,hash HAVING COUNT(*)>1)"):
            G[(size, h)].append((fid, p))
        N = defaultdict(int); B = defaultdict(int)                                   # 每個資料夾（含子資料夾）有幾個檔、多大
        for p, size in E.db.q("SELECT path, size FROM files WHERE state=''"):
            d = os.path.dirname(p); N[d] += 1; B[d] += size or 0
        NT = defaultdict(int); BT = defaultdict(int)
        for d in list(N):
            n, b = N[d], B[d]; x = d
            while True:
                NT[x] += n; BT[x] += b; par = os.path.dirname(x)
                if par == x or not par: break
                x = par
        R = {r.lower() for r in self.roots()}
        lift = {}

        def up(a, b):
            k = (a, b)
            if k in lift: return lift[k]
            x, y = a, b
            while True:                                                             # 上一層的名字也一樣，才往上合（停在「被複製的那個資料夾」）
                px, py = os.path.dirname(x), os.path.dirname(y)
                if px == x or py == y or px.lower() in R or py.lower() in R: break
                if os.path.basename(px).lower() != os.path.basename(py).lower(): break
                if px.lower() == py.lower() or fcore.under(px, py) or fcore.under(py, px): break
                x, y = px, py
            lift[k] = (x, y); return x, y
        P = defaultdict(lambda: [0, 0]); TOP = defaultdict(lambda: [0, 0, defaultdict(int)]); extra = 0; extra_b = 0; ng = 0
        for (size, _h), L in G.items():
            ng += 1; extra += len(L) - 1; extra_b += size * (len(L) - 1)
            tops = defaultdict(int)
            for _fid, p in L: tops[self.top_of(p)] += 1
            for tp, c in tops.items():
                others = [o for o in tops if o != tp]
                if others:
                    T = TOP[tp]; T[0] += c; T[1] += size * c
                    for o in others: T[2][o] += c
            D = sorted({os.path.dirname(p) for _f, p in L})
            if len(D) < 2 or len(D) > MAX_COPIES: continue
            seen = set()
            for i in range(len(D)):
                for j in range(i + 1, len(D)):
                    a, b = up(D[i], D[j]); key = (a, b) if a.lower() < b.lower() else (b, a)
                    if key in seen: continue
                    seen.add(key); x = P[key]; x[0] += 1; x[1] += size
        pairs = []
        for (a, b), (n, by) in sorted(P.items(), key=lambda kv: -kv[1][1])[:400]:
            na, nb = NT.get(a, 0), NT.get(b, 0); sa, wa = self.score(a); sb, wb = self.score(b)
            ca = min(100, round(100 * n / max(1, na))); cb = min(100, round(100 * n / max(1, nb)))
            if abs(sa - sb) >= 0.5: keep = 'a' if sa > sb else 'b'
            elif ca != cb: keep = 'a' if ca < cb else 'b'                            # 比較完整的那邊留（另一邊幾乎都是它的複本）
            else: keep = 'a' if len(a) <= len(b) else 'b'
            other_cov = cb if keep == 'a' else ca
            rel = 'copy' if other_cov >= 95 else 'overlap'
            kd, od = (a, b) if keep == 'a' else (b, a); kw = wa if keep == 'a' else wb; ow = wb if keep == 'a' else wa
            kw2 = [x for x in kw if x not in ow]; ow2 = [x for x in ow if x not in kw]
            why = '、'.join(kw2[:2]) if kw2 else ('另一邊幾乎都是它的複本' if other_cov >= 95 else '這邊比較完整' if (ca if keep == 'a' else cb) < other_cov else '路徑比較短')
            if ow2: why += f'；另一邊{ow2[0]}'
            L_ = lambda d: os.path.join(os.path.basename(os.path.dirname(d)), os.path.basename(d))
            pairs.append({'a': a, 'b': b, 'n': n, 'bytes': by, 'na': na, 'nb': nb, 'ba': BT.get(a, 0), 'bb': BT.get(b, 0), 'pa': ca, 'pb': cb, 'keep': keep, 'rel': rel, 'why': why,
                          'same_drive': os.path.splitdrive(a)[0].lower() == os.path.splitdrive(b)[0].lower(),
                          'tip': (f'「{L_(od)}」整包是複本 → 保留「{L_(kd)}」，複本搬到隔離區' if rel == 'copy'
                                  else f'兩邊各有獨有的 → 建議 🔀 合併到「{L_(kd)}」（獨有的搬過去、重複的搬隔離區）')})
        tops = []
        for tp, (c, by, OT) in sorted(TOP.items(), key=lambda kv: -kv[1][1])[:60]:
            main = sorted(OT.items(), key=lambda kv: -kv[1])[:3]
            tops.append({'path': tp, 'n': NT.get(tp, 0), 'b': BT.get(tp, 0), 'dn': c, 'db': by, 'pct': min(100, round(100 * c / max(1, NT.get(tp, 0)))),
                         'with': [{'path': o, 'n': k} for o, k in main], 'score': self.score(tp)[0]})
        save = sum(p['bytes'] for p in pairs)
        res = {'ok': True, 'groups': ng, 'extra': extra, 'extra_b': extra_b, 'pairs': pairs, 'tops': tops, 'save_b': save, 'sec': round(time.time() - t0, 1), 't': time.time()}
        self.c = (time.time(), res); return res

    # ------------------------------------------------------------ 動作
    def _files(self, d):
        pre = d.rstrip('\\/')
        e = fcore.like_esc(pre)
        return [dict(r) for r in self.E.db.q("SELECT id, path, size, hash FROM files WHERE state='' AND (path LIKE ? ESCAPE '^' OR path LIKE ? ESCAPE '^')", (e + '\\%', e + '/%'))]

    def plan(self, keep_dir, other_dir, merge=False):
        """預覽：other 裡多少「keep 也有」（搬隔離區）、多少獨有（合併時搬過去）."""
        K = self._files(keep_dir); O = self._files(other_dir)
        KH = {(f['size'], f['hash']) for f in K if f['hash'] and not str(f['hash']).startswith('!')}
        dup = [f for f in O if f['hash'] and (f['size'], f['hash']) in KH]; uniq = [f for f in O if not (f['hash'] and (f['size'], f['hash']) in KH)]
        nh = sum(1 for f in O if not f['hash'])
        return {'ok': True, 'dup': len(dup), 'dup_b': sum(f['size'] or 0 for f in dup), 'uniq': len(uniq), 'uniq_b': sum(f['size'] or 0 for f in uniq), 'nohash': nh,
                'same_drive': os.path.splitdrive(keep_dir)[0].lower() == os.path.splitdrive(other_dir)[0].lower(), '_dup': dup, '_uniq': uniq}

    def start(self, keep_dir, other_dir, merge=False):
        if self.st.get('run'): return {'ok': False, 'message': '已經在做了，等它做完'}
        if fcore.under(keep_dir, other_dir) or fcore.under(other_dir, keep_dir): return {'ok': False, 'message': '這兩個資料夾一個在另一個裡面，不能這樣做'}
        pl = self.plan(keep_dir, other_dir, merge)
        if merge and not pl['same_drive']: return {'ok': False, 'message': '兩邊在不同硬碟：合併要複製，這版只在同一顆硬碟裡搬。可以改用「保留」（只搬重複的）'}
        if not pl['dup'] and not (merge and pl['uniq']): return {'ok': False, 'message': '沒有要搬的（可能已經處理過了）'}
        self.st.clear(); self.st.update(run=True, n=0, q=0, m=0, bad=0, b=0, total=pl['dup'] + (pl['uniq'] if merge else 0), keep=keep_dir, other=other_dir, merge=merge)
        threading.Thread(target=self._job, args=(keep_dir, other_dir, merge, pl), name='DupPlan', daemon=True).start()
        return {'ok': True, 'message': f"開始：{pl['dup']:,} 個重複的搬隔離區" + (f"、{pl['uniq']:,} 個獨有的合併過去" if merge and pl['uniq'] else '') + '（背景做）'}

    def _job(self, kd, od, merge, pl):
        E = self.E; S = self.st; t = E.task('op', f"🧭 {'合併' if merge else '保留'}：{os.path.basename(kd) or kd} ← {os.path.basename(od) or od}")
        why = f'保留 {kd}'
        try:
            for f in pl['_dup']:
                if E.stop_all or S.get('cancel'): break
                S['n'] += 1
                ok_ = E.db.one("SELECT id FROM files WHERE state='' AND size=? AND hash=? AND id!=? AND (path LIKE ? ESCAPE '^' OR path LIKE ? ESCAPE '^') LIMIT 1",
                               (f['size'], f['hash'], f['id'], fcore.like_esc(kd.rstrip('\\/')) + '\\%', fcore.like_esc(kd.rstrip('\\/')) + '/%'))
                if not ok_: S['bad'] += 1; continue                                   # 保留那邊已經沒有一樣的了：不動（不會把最後一份搬走）
                ok, _m = E.fc_quar(f['id'], '整包重複' if not merge else '合併資料夾', why)
                if ok: S['q'] += 1; S['b'] += f['size'] or 0
                else: S['bad'] += 1
                t['msg'] = f"{S['n']:,}／{S['total']:,}"
            if merge:
                for f in pl['_uniq']:
                    if E.stop_all or S.get('cancel'): break
                    S['n'] += 1; src = f['path']
                    if not E.db.one("SELECT id FROM files WHERE id=? AND state='' AND path=?", (f['id'], src)): continue
                    try: rel = os.path.relpath(src, od)
                    except ValueError: rel = '..'
                    if rel.startswith('..') or os.path.isabs(rel): S['bad'] += 1; continue      # 防呆：不在另一邊裡面的不動
                    dst0 = os.path.join(kd, rel)
                    try: dst = fcore.move(src, dst0)
                    except Exception as ex: S['bad'] += 1; E.oplog('合併資料夾', f'失敗：{src}：{ex}', False); continue
                    try:
                        E.db.x('UPDATE files SET path=? WHERE id=?', (dst, f['id']))
                        E.db.x('INSERT INTO moves(t,fid,src,dst,reason) VALUES(?,?,?,?,?)', (time.time(), f['id'], src, dst, f'合併資料夾：{kd}'))
                        S['m'] += 1
                    except Exception:
                        try: fcore.move(dst, src, rename=False)
                        except Exception: pass
                        S['bad'] += 1
                    t['msg'] = f"{S['n']:,}／{S['total']:,}"
                if E.cfg.get('rm_empty_dirs') is not False:
                    try:
                        stop = next((x for x in E.fc_list('roots') if fcore.under(od, x)), None)
                        for dp, _dn, _fn in sorted(os.walk(od), key=lambda x: -len(x[0])):
                            if stop: fcore.rmdirs_up(dp, stop)
                    except Exception: pass
            msg = (f"保留「{os.path.basename(kd) or kd}」：" + f"{S['q']:,} 個重複的搬到隔離區（{S['b'] / 1e9:.2f} GB）" + (f"、{S['m']:,} 個獨有的合併過來" if merge else '')
                   + (f"，{S['bad']:,} 個沒動（保留那邊找不到一樣的、或搬不動）" if S['bad'] else ''))
            E.done(t, 'stop' if S.get('cancel') else 'done', msg); E.oplog('重複資料夾（最佳解）', msg); E.log.w('🧭 ' + msg); S['msg'] = msg; self.c = None
        except Exception as ex: E.log.err('🧭 重複資料夾最佳解'); E.done(t, 'fail', str(ex)); S['msg'] = str(ex)
        finally: S['run'] = False; E.fc_kick()

    def start_all(self, only_copy=True):
        """⚡ 全部照最佳解：每一對照建議「保留」（only_copy＝只做「整包是複本」的；部分重複的留給你決定）。一對一對做."""
        if self.st.get('run'): return {'ok': False, 'message': '已經在做了'}
        res = self.analyze(); L = [p for p in res['pairs'] if (p['rel'] == 'copy' or not only_copy)]
        if not L: return {'ok': False, 'message': '沒有可以直接處理的（整包是複本的已經處理完了）'}
        self.st.clear(); self.st.update(run=True, n=0, q=0, m=0, bad=0, b=0, total=0, all=len(L), done_pairs=0)

        def job():
            E = self.E; S = self.st; t = E.task('op', f'🧭 全部照最佳解（{len(L)} 對）')
            try:
                for p in L:
                    if E.stop_all or S.get('cancel'): break
                    kd, od = (p['a'], p['b']) if p['keep'] == 'a' else (p['b'], p['a'])
                    if fcore.under(kd, od) or fcore.under(od, kd): continue
                    pl = self.plan(kd, od); S['total'] += pl['dup']
                    for f in pl['_dup']:
                        if E.stop_all or S.get('cancel'): break
                        S['n'] += 1
                        if not E.db.one("SELECT id FROM files WHERE state='' AND size=? AND hash=? AND id!=? AND (path LIKE ? ESCAPE '^' OR path LIKE ? ESCAPE '^') LIMIT 1",
                                        (f['size'], f['hash'], f['id'], fcore.like_esc(kd.rstrip('\\/')) + '\\%', fcore.like_esc(kd.rstrip('\\/')) + '/%')): S['bad'] += 1; continue
                        ok, _m = E.fc_quar(f['id'], '整包重複', f'保留 {kd}')
                        if ok: S['q'] += 1; S['b'] += f['size'] or 0
                        else: S['bad'] += 1
                    S['done_pairs'] += 1; t['msg'] = f"{S['done_pairs']}／{len(L)} 對、搬了 {S['q']:,} 個（{S['b'] / 1e9:.2f} GB）"
                msg = f"全部照最佳解：{S['done_pairs']} 對、{S['q']:,} 個重複的搬到隔離區（{S['b'] / 1e9:.2f} GB）" + (f"，{S['bad']:,} 個沒動" if S['bad'] else '')
                E.done(t, 'stop' if S.get('cancel') else 'done', msg); E.oplog('重複資料夾（最佳解）', msg); S['msg'] = msg; self.c = None
            except Exception as ex: E.log.err('🧭 全部照最佳解'); E.done(t, 'fail', str(ex)); S['msg'] = str(ex)
            finally: S['run'] = False; E.fc_kick()
        threading.Thread(target=job, name='DupPlanAll', daemon=True).start()
        return {'ok': True, 'message': f'開始處理 {len(L)} 對「整包是複本」的資料夾（背景做）'}

    def history(self, limit=40):
        """最近做過的（可以一次復原一筆）：[{key, kind, keep, n, t}]."""
        H = {}
        for reason, n, t in self.E.db.q("SELECT reason, COUNT(*), MAX(t) FROM moves WHERE undone=0 AND (reason LIKE '整包重複：%' OR reason LIKE '合併資料夾：%') GROUP BY reason"):
            kind = 'merge' if reason.startswith('合併資料夾') else 'keep'; kd = reason.split('：', 1)[1]
            if kd.startswith('保留 '): kd = kd[3:]
            h = H.setdefault((kind, kd), {'key': f'{kind}|{kd}', 'kind': kind, 'keep': kd, 'n': 0, 't': 0}); h['n'] += n; h['t'] = max(h['t'], t or 0)
        return sorted(H.values(), key=lambda h: -h['t'])[:limit]

    def undo(self, key):
        kind, _, kd = str(key).partition('|')
        R = ['整包重複：保留 ' + kd] if kind == 'keep' else ['合併資料夾：保留 ' + kd, '合併資料夾：' + kd]
        ids = [r[0] for x in R for r in self.E.db.q('SELECT id FROM moves WHERE undone=0 AND reason=?', (x,))]
        if not ids: return {'ok': False, 'message': '沒有要復原的'}
        r = self.E.fc_undo(ids); self.c = None
        self.E.oplog('重複資料夾：復原', f"{'合併' if kind == 'merge' else '保留'} {kd}：{r.get('message', '')}")
        return {'ok': r.get('ok'), 'message': '↶ ' + r.get('message', '')}

    def status(self):
        return {k: v for k, v in self.st.items() if not k.startswith('_')}

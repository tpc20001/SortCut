"""💾 設定匯出／匯入（V0.1.66，不准 import Qt）：重灌、換電腦時把「你的設定」帶走——
要整理的資料夾、優先保留、不要整理的資料夾、所有設定、影片分類（分類名稱、顏色、搬去哪）、每部影片分到哪類（用路徑對應）、⭐ 最愛。
匯入是「合併」：已經有的不重複加；分類標記只套到找得到同路徑的檔。不會動任何檔案."""
import json, time

KEEP = ('roots', 'keep_prio', 'skip_dirs')


def export(E):
    C = {k: v for k, v in dict(E.cfg.d).items() if not k.startswith('web_') and k not in ('perf_pos', 'side_w', 'upd_dl_dir')}
    cats = [dict(r) for r in E.db.q('SELECT id, name, dest, color, ord FROM vc_cat ORDER BY ord, id')]
    tags = [[r[0], r[1], r[2]] for r in E.db.q("SELECT f.path, t.cat, t.moved FROM vc_tag t JOIN files f ON f.id=t.fid")]
    favs = [r[0] for r in E.db.q('SELECT path FROM files WHERE fav=1')]
    return {'app': 'FileCompare', 'kind': 'settings', 'v': 1, 't': time.time(), 'ver': E.version, 'cfg': C, 'cats': cats, 'tags': tags, 'favs': favs}


def import_(E, d):
    if not isinstance(d, dict) or d.get('kind') != 'settings': return {'ok': False, 'message': '這不是 FileCompare 的設定檔'}
    n = {'lists': 0, 'cfg': 0, 'cats': 0, 'tags': 0, 'favs': 0}
    for k in KEEP:
        for p in d.get('cfg', {}).get(k) or []:
            ok, _m = E.fc_list_add(k, p); n['lists'] += ok
    for k, v in (d.get('cfg') or {}).items():
        if k in KEEP or k.startswith('web_') or k in ('upd_dl_dir',): continue
        try: E.cfg.set(k, v); n['cfg'] += 1
        except Exception: pass
    M = {}
    have = {r[1]: r[0] for r in E.db.q('SELECT id, name FROM vc_cat')}
    for c in d.get('cats') or []:
        if c['name'] in have: M[c['id']] = have[c['name']]; continue
        r = E.vc.cat_add(c['name'], c.get('dest') or '')
        nid = (E.db.one('SELECT id FROM vc_cat WHERE name=?', (c['name'],)) or [None])[0]
        if nid:
            M[c['id']] = nid; n['cats'] += 1
            if c.get('color'): E.db.x('UPDATE vc_cat SET color=? WHERE id=?', (c['color'], nid))
    P = {r[1].lower(): r[0] for r in E.db.q("SELECT id, path FROM files WHERE state=''")}
    R = []
    for path, cat, moved in d.get('tags') or []:
        fid = P.get(str(path).lower()); nc = M.get(cat)
        if fid and nc: R.append((fid, nc, time.time(), int(moved or 0)))
    E.db.xm('INSERT INTO vc_tag(fid,cat,t,moved) VALUES(?,?,?,?) ON CONFLICT(fid) DO NOTHING', R); n['tags'] = len(R)
    F = [(P[p.lower()],) for p in d.get('favs') or [] if p.lower() in P]
    E.db.xm('UPDATE files SET fav=1 WHERE id=?', F); n['favs'] = len(F)
    E.log.w(f'💾 匯入設定：{n}')
    return {'ok': True, 'n': n, 'message': f"匯入好了：資料夾清單 {n['lists']}、設定 {n['cfg']}、分類 {n['cats']}、分類標記 {n['tags']}、最愛 {n['favs']}"}

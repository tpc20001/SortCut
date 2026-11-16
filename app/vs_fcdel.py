"""🗑 整理（FileCompare）的「Delete」分類：已經搬進 Delete 資料夾的檔 → 永久刪除，騰出硬碟空間（V0.5.67）.

只刪「分類＝Delete（或 刪除／垃圾…）而且已經搬好（moved=1）」的檔；刪之前再確認一次檔案還在、大小跟紀錄一樣。
不經過資源回收筒（外接硬碟的回收筒不會空出空間）。每一個都寫進整理的操作紀錄；SortCut 有這部的話標成「不見了」（預覽圖記憶不刪）。
沒有 Qt，電腦版和手機都叫這裡。
"""
import os
import threading
import time

DEL_NAMES = ('delete', 'del', '刪除', '删除', '要刪的', '垃圾')
ST = {'run': False, 'n': 0, 'total': 0, 'ok': 0, 'bad': 0, 'b': 0, 'err': [], 't0': 0.0, 'done_t': 0.0, 'msg': ''}


def _cats(E):
    return [(int(i), str(n)) for i, n in E.db.q('SELECT id, name FROM vc_cat') if str(n or '').strip().lower() in DEL_NAMES]


def _rows(E, ids):
    if not ids: return []
    ph = ','.join(str(i) for i in ids)
    return [dict(r) for r in E.db.q(f"SELECT f.id, f.path, f.size FROM vc_tag t JOIN files f ON f.id=t.fid WHERE t.cat IN ({ph}) AND t.moved=1 AND f.state=''")]


def info(E):
    """還有幾部可以刪、多大、在哪幾顆硬碟、還有幾部沒搬（沒搬的不刪）."""
    C = _cats(E); ids = [i for i, _n in C]
    R = _rows(E, ids); drv = {}
    for r in R:
        d = os.path.splitdrive(str(r['path']))[0].upper() or '?'; drv[d] = drv.get(d, 0) + int(r['size'] or 0)
    wait = 0
    if ids:
        ph = ','.join(str(i) for i in ids)
        wait = int((E.db.one(f'SELECT COUNT(*) FROM vc_tag WHERE cat IN ({ph}) AND moved=0') or [0])[0] or 0)
    return {'ok': True, 'cats': [n for _i, n in C], 'n': len(R), 'bytes': sum(int(r['size'] or 0) for r in R), 'drives': drv, 'wait': wait,
            'st': {k: ST[k] for k in ('run', 'n', 'total', 'ok', 'bad', 'b', 'msg', 'done_t')}, 'err': ST['err'][-5:]}


def purge(E, lp=None, on_gone=None, log=None):
    """背景刪；回傳開始了沒。lp＝長路徑轉換；on_gone(path)＝通知 SortCut；log(msg)＝寫 LOG."""
    if ST['run']: return {'ok': False, 'message': '已經在刪了'}
    R = _rows(E, [i for i, _n in _cats(E)])
    if not R: return {'ok': False, 'message': '沒有已經搬進 Delete 的檔'}
    ST.update(run=True, n=0, total=len(R), ok=0, bad=0, b=0, err=[], t0=time.time(), done_t=0.0, msg='開始')
    lp = lp or (lambda p: p)

    def job():
        try:
            for r in R:
                ST['n'] += 1; p = str(r['path'])
                try:
                    st = os.stat(lp(p))
                    if int(r['size'] or 0) and st.st_size != int(r['size']): raise RuntimeError(f'大小跟紀錄不一樣（{st.st_size} ≠ {r["size"]}），不刪')
                    os.remove(lp(p))
                except FileNotFoundError:
                    pass                                                        # 已經不在了：一樣把紀錄清掉
                except Exception as ex:
                    ST['bad'] += 1; ST['err'].append(f'{os.path.basename(p)}：{ex}'); continue
                try:
                    E.db.x('DELETE FROM vc_tag WHERE fid=?', (int(r['id']),)); E.db.x('DELETE FROM files WHERE id=?', (int(r['id']),))
                    E.db.x('UPDATE moves SET undone=2 WHERE fid=? AND undone=0', (int(r['id']),))   # V0.5.77 之前搬到 Delete 的那筆也不算在隔離區了（檔案已經不在）
                    E.db.x('INSERT INTO moves(t,fid,src,dst,reason,undone) VALUES(?,?,?,?,?,2)', (time.time(), int(r['id']), p, '', '🗑 永久刪除（Delete 分類）'))
                except Exception: pass
                ST['ok'] += 1; ST['b'] += int(r['size'] or 0); ST['msg'] = f'{ST["ok"]:,}／{ST["total"]:,}'
                if on_gone:
                    try: on_gone(p)
                    except Exception: pass
            try:
                E.oplog('🗑 永久刪除 Delete 分類', f'刪了 {ST["ok"]:,} 個（{ST["b"] / 1e9:.1f} GB），失敗 {ST["bad"]}', ST['bad'] == 0)
                E.fc_cache['t'] = 0
            except Exception: pass
            if log: log(f'🗑 整理：永久刪除 Delete 分類 {ST["ok"]:,} 個、{ST["b"] / 1e9:.1f} GB，失敗 {ST["bad"]}')
        finally:
            ST['run'] = False; ST['done_t'] = time.time(); ST['msg'] = f'刪好了 {ST["ok"]:,} 個' + (f'，{ST["bad"]} 個沒刪' if ST['bad'] else '')

    threading.Thread(target=job, name='fc-delpurge', daemon=True).start()
    return {'ok': True, 'message': f'開始永久刪除 {len(R):,} 個'}

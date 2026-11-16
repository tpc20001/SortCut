"""💽 整理（FileCompare）的紀錄也寫到每顆硬碟自己身上（V0.5.69）：X:\\VideoSIFT\\.vsdata\\FileCompare\\.

跟 SortCut 的 .vsdata 放一起：硬碟搬到別台電腦，整理那邊打開就看得到「在 R: 找到整理紀錄 → 接上」，不用再自己複製 Data。
寫的是整個整理資料庫的一致快照（SQLite backup，不會寫到一半）＋設定；有改過才寫，平常最多 1 小時一次，按「💾 現在寫到各硬碟」就馬上寫。
沒有 Qt。
"""
import json
import os
import platform
import shutil
import time
from pathlib import Path

SUB = 'FileCompare'
ST = {'t': {}, 'run': False}


def pack_dir(X):
    return Path(f'{str(X)[:1].upper()}:\\') / 'VideoSIFT' / '.vsdata' / SUB


def drives(FE):
    out = []
    for r in list(FE.fc_list('roots') if hasattr(FE, 'fc_list') else FE.cfg.get('roots') or []):
        r = str(r)
        if len(r) > 1 and r[1] == ':' and r[0].upper() not in out: out.append(r[0].upper())
    return out


def export(FE, force=False, log=None, ver=''):
    """有改過（或 force）的話，把整理資料庫快照＋設定寫到每顆整理資料夾所在的硬碟。回傳寫了哪幾顆."""
    if ST['run']: return []
    dirty = float((getattr(FE, 'fc_dirty', None) or [0])[0] or 0)
    out = []; ST['run'] = True
    try:
        for X in drives(FE):
            if not os.path.isdir(f'{X}:\\'): continue
            last = ST['t'].get(X, 0)
            if last and dirty and dirty <= last and not force: continue
            if not force and last and time.time() - last < 3600: continue
            if force and last and dirty and dirty <= last: continue                # 按了「現在寫」但沒改過：不用再寫
            pd = pack_dir(X)
            try:
                pd.mkdir(parents=True, exist_ok=True); tmp = pd / 'app.tmp.sqlite3'
                try: tmp.unlink()
                except OSError: pass
                FE.db.backup_to(tmp); os.replace(str(tmp), str(pd / 'app.sqlite3'))
                sj = Path(FE.data) / 'settings.json'
                if sj.exists(): shutil.copy2(str(sj), str(pd / 'settings.tmp.json')); os.replace(str(pd / 'settings.tmp.json'), str(pd / 'settings.json'))
                n = int((FE.db.one('SELECT COUNT(*) FROM files') or [0])[0] or 0)
                J = {'v': 1, 't': time.time(), 'pc': platform.node(), 'app': ver, 'roots': list(FE.fc_list('roots')), 'files': n,
                     'tagged': int((FE.db.one('SELECT COUNT(*) FROM vc_tag') or [0])[0] or 0)}
                (pd / 'pack.tmp.json').write_text(json.dumps(J, ensure_ascii=False, indent=1), encoding='utf-8'); os.replace(str(pd / 'pack.tmp.json'), str(pd / 'pack.json'))
                ST['t'][X] = time.time(); out.append(X)
                if log: log(f'💽 整理的紀錄寫到 {X}:\\VideoSIFT\\.vsdata\\{SUB}（{n:,} 個檔）')
            except Exception as ex:
                if log: log(f'💽 整理的紀錄寫到 {X}: 失敗：{ex}')
    finally: ST['run'] = False
    return out


def find(FE=None):
    """接著的硬碟裡有整理紀錄的：[(代號, pack.json)]（新的在前）。這台整理已經有資料夾的話不找."""
    if FE is not None and list(FE.fc_list('roots') or []): return []
    out = []
    for c in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
        try:
            pd = pack_dir(c)
            if (pd / 'pack.json').exists() and (pd / 'app.sqlite3').exists():
                out.append((c, json.loads((pd / 'pack.json').read_text(encoding='utf-8'))))
        except Exception: pass
    return sorted(out, key=lambda x: -float(x[1].get('t') or 0))


def use(X, fc_root):
    """把 X: 上的整理紀錄放到「下次開程式換上」（跟 📥 匯入舊資料同一條路）."""
    pd = pack_dir(X); dst = Path(fc_root) / 'Data_import_pending'
    if dst.exists(): shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True)
    shutil.copy2(str(pd / 'app.sqlite3'), str(dst / 'app.sqlite3'))
    if (pd / 'settings.json').exists(): shutil.copy2(str(pd / 'settings.json'), str(dst / 'settings.json'))
    return {'ok': True, 'message': f'{X}: 的整理紀錄準備好了，重開 SortCut 就接上'}

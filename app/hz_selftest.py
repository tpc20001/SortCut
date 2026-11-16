"""HotZone FM — 自我檢查: one button that verifies, on the user's own Windows machine, everything the program relies on
(administrator rights, the NTFS calls used by 熱處理, the modules used by 圖片分類, the data folder, the web server)
and produces a report that can be copied and sent back. The only thing written to a user drive is one temporary
8 MB test file inside that drive's hidden .HotZoneVault\\selftest folder, which is removed again at the end.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import platform
import sqlite3
import sys
import time

from hz_common import APP_VERSION, DATA_DIR, IS_WIN, drive_of, norm
import hz_win as W


def _check(out, name, fn):
    t0 = time.perf_counter()
    try:
        r = fn()
        ok, detail = (r if isinstance(r, tuple) else (True, r))
    except Exception as e:
        ok, detail = False, f'{type(e).__name__}: {e}'
    out.append({'name': name, 'ok': ok, 'detail': str(detail), 'ms': round((time.perf_counter() - t0) * 1000)})
    return ok


def _modules():
    parts = []; ok = True
    for mod, label, need in (('PIL', 'Pillow（縮圖、圖片分類）', True), ('numpy', 'numpy', False), ('cv2', 'OpenCV（人臉偵測）', False),
                             ('PySide6', 'PySide6（視窗外殼）', False)):
        try:
            if mod == 'PySide6':
                spec = importlib.util.find_spec('PySide6')
                parts.append(f'{label} {"有" if spec else "沒有"}'); continue
            m = importlib.import_module(mod)
            v = getattr(m, '__version__', '?')
            extra = ''
            if mod == 'cv2':
                p = os.path.join(getattr(getattr(m, 'data', None), 'haarcascades', '') or '', 'haarcascade_frontalface_default.xml')
                extra = '，臉部模型 ' + ('有' if os.path.isfile(p) else '找不到')
            parts.append(f'{label} {v}{extra}')
        except Exception as e:
            parts.append(f'{label} 沒有（{type(e).__name__}）')
            if need: ok = False
    return ok, '；'.join(parts)


def _sqlite():
    db = sqlite3.connect(':memory:')
    n = db.execute("SELECT COUNT(*) FROM json_each('[1,2,3]')").fetchone()[0]
    return n == 3, f'SQLite {sqlite3.sqlite_version}，JSON 函式{"可用" if n == 3 else "不可用"}'


def _data_dir():
    p = DATA_DIR / f'.selftest_{os.getpid()}.tmp'
    with open(p, 'wb') as f:
        f.write(b'x' * 4096); f.flush(); os.fsync(f.fileno())
    os.remove(p)
    return True, f'{DATA_DIR} 可以寫入'


def _find_free(vol, need, zone_end=None):
    """First run of `need` free clusters, outside the MFT zone, as early on the disk as possible."""
    vd = vol.vd; total = vd['total_clusters']
    mz0, mz1 = vd['mft_zone_start'], vd['mft_zone_end']
    k = (need + 7) // 8 + 1
    pos = 0; step = 64 * 1024 * 1024                                           # clusters per bitmap read
    while pos < total:
        first, bm = vol.bitmap(pos, min(step, total - pos))
        i = 0
        while True:
            j = bm.find(b'\x00' * k, i)
            if j < 0: break
            lcn = first + j * 8
            if mz0 <= lcn < mz1 or mz0 <= lcn + need <= mz1:
                i = max(j + 1, (mz1 - first) // 8 + 1); continue
            return lcn
        if not bm: break
        nxt = first + len(bm) * 8 - k * 8                                     # overlap: a run may cross the chunk edge
        pos = nxt if nxt > pos else first + len(bm) * 8
    return None


def _move_test(letter, vault_root):
    """Create an 8 MB file, move it with FSCTL_MOVE_FILE to free clusters near the start of the disk, check the
    data is byte-for-byte the same, remove it."""
    import hz_ntfs as N
    d = os.path.join(vault_root, 'selftest'); os.makedirs(W.lp(d), exist_ok=True)
    p = os.path.join(d, f'move_test_{os.getpid()}.bin')
    data = os.urandom(8 * 1024 * 1024); h0 = hashlib.sha256(data).hexdigest()
    try:
        with open(W.lp(p), 'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        with N.NtfsVolume(letter) as vol:
            cl = vol.vd['cluster']
            with vol.open_file(p) as fr:
                ext0 = fr.extents()
                if not ext0: return False, '測試檔沒有拿到磁碟位置'
                need = sum(c for v, l, c in ext0)
                target = _find_free(vol, need)
                if target is None: return None, '找不到夠大的連續空間做搬移測試（磁碟太滿或太零碎），略過'
                t0 = time.perf_counter()
                ok, err = fr.move(0, target, need)
                dt = time.perf_counter() - t0
                if not ok: return False, f'FSCTL_MOVE_FILE 失敗（錯誤碼 {err}）：熱處理沒辦法搬資料'
                ext1 = fr.extents()
        hh = hashlib.sha256()                                               # read past the cache: the clusters themselves
        for b in W.read_unbuffered(p): hh.update(b)
        h1 = hh.hexdigest()
        if h1 != h0: return False, '搬移後內容不一樣！請不要使用熱處理，並把這份報告傳給開發者'
        where = ext1[0][1] if ext1 else -1
        pct = where / max(1, vol.vd['total_clusters']) * 100
        return True, (f'8 MB 測試檔從第 {ext0[0][1]:,} 叢集搬到第 {where:,} 叢集（磁碟前 {pct:.2f}%），內容完全相同，'
                      f'{len(ext1)} 段，{8 / max(dt, 1e-6):.0f} MB/s，叢集大小 {cl} B')
    finally:
        try: os.remove(W.lp(p))
        except OSError: pass
        try: os.rmdir(W.lp(d))
        except OSError: pass


def _ntfs(letter):
    import hz_ntfs as N
    with N.NtfsVolume(letter) as vol:
        vd = vol.vd; total = vd['total_clusters']; cl = vd['cluster']
        t0 = time.perf_counter(); first, bm = vol.bitmap(0, min(total, 8 * 1024 * 1024)); tb = time.perf_counter() - t0
        used = sum(bin(b).count('1') for b in bm[:1 << 20])
        j, err = vol.usn_query()
        return True, (f'NTFS，{total * cl / 1e12:.2f} TB，叢集 {cl} B，可用 {vd["free_clusters"] * cl / 1e9:.0f} GB；'
                      f'空間點陣圖讀取正常（{tb * 1000:.0f} ms，前段使用率 {used / max(1, min(len(bm), 1 << 20) * 8) * 100:.0f}%）；'
                      f'MFT {vd["mft_valid"] / 1e6:.0f} MB；變更日誌（USN）{"有" if j else "沒有（第一次建立索引時會自動開）"}')


def _mft(letter):
    import hz_ntfs as N
    with N.NtfsVolume(letter) as vol:
        t0 = time.perf_counter(); n = 0
        for _ in N.iter_mft(vol):
            n += 1
            if n >= 20000: break
        dt = time.perf_counter() - t0
    return True, f'直接讀 MFT 正常：{n:,} 筆 {dt:.2f} 秒（建立索引會用這個方式，速度像 Everything）'


def _disk(letter):
    ex = W.volume_disk_extents(letter)
    if not ex: return None, '查不到對應的實體硬碟（可能是 RAID、動態磁碟或虛擬磁碟），佇列會把它當成獨立的一顆'
    parts = []
    for n in sorted({e[0] for e in ex}):
        try:
            info = W.physical_disk_info(n)
            media = info.get('media', '?')
            parts.append(f'實體硬碟 {n}：{info.get("model") or "?"}（{info.get("bus") or "?"}），{media if media != "?" else "類型不明"}'
                         + ('，疑似 SMR 疊瓦式：大量寫入時會變慢，外圈加速效果也比較弱' if W.smr_suspect(info.get('model', '')) else '')
                         + ('；SSD 沒有內外圈的差別，熱處理對它沒有幫助' if media == 'SSD' else ''))
        except Exception as e:
            parts.append(f'實體硬碟 {n}：{e}')
    return True, '；'.join(parts)


def run(eng, letters=None, move_test=True):
    out = []
    _check(out, '程式版本', lambda: (True, f'HotZone FM {APP_VERSION}，Python {sys.version.split()[0]}，{platform.platform()}'
                                       f'{"，exe" if getattr(sys, "frozen", False) else "，原始碼執行"}'))
    _check(out, '系統管理員權限', lambda: (True, '有（熱處理、讀 MFT 都可以用）') if W.is_admin() else
           (False, '沒有：熱處理和快速索引需要它。請用 HotZoneFM.exe 啟動（會自動要求權限），或在設定裡建立開機排程'))
    _check(out, '必要模組', _modules)
    _check(out, '資料庫', _sqlite)
    _check(out, '資料資料夾', _data_dir)
    def _vault():
        st = eng.vault.stats(); k = st.get('keep', {}); r = st.get('review', {})
        import hz_fileops as F
        left = len(F.pending_plans())
        txt = f'保管中 {k.get("n", 0):,} 項（{k.get("size", 0) / 1e9:.1f} GB），待你決定 {r.get("n", 0):,} 項'
        if left: return False, txt + f'；有 {left} 個中斷的批次改名還沒改回原名（檔案可能被別的程式開著），請看紀錄頁'
        return True, txt
    _check(out, '保管區與批次改名', _vault)
    _check(out, '網頁伺服器', lambda: (True, f'連接埠 {eng.S.get("web.port")}，遠端連線{"已開放" if eng.S.get("web.remote") else "沒有開放"}'))
    if letters is None:
        letters = []
        for f in (eng.hot.folders() if hasattr(eng.hot, 'folders') else []):
            p = f.get('path') if isinstance(f, dict) else f
            if p and drive_of(norm(p)) not in letters: letters.append(drive_of(norm(p)))
    if not IS_WIN:
        out.append({'name': 'NTFS 檢查', 'ok': None, 'detail': '這台不是 Windows，略過', 'ms': 0})
        return {'t': time.time(), 'checks': out}
    if not letters:
        out.append({'name': 'NTFS 檢查', 'ok': None, 'detail': '還沒有熱處理資料夾，所以沒有檢查硬碟。標記一個熱處理資料夾後再按一次自我檢查。', 'ms': 0})
    for lt in letters:
        lt = lt.rstrip('\\').upper()
        _check(out, f'{lt} 實體硬碟', lambda lt=lt: _disk(lt))
        if not _check(out, f'{lt} NTFS 存取', lambda lt=lt: _ntfs(lt)): continue
        _check(out, f'{lt} 讀取 MFT', lambda lt=lt: _mft(lt))
        def _vss(lt=lt):
            import hz_hot as HH
            n = HH.count_shadow_copies(lt)
            return (True, '沒有系統還原點（陰影複製），搬移不受影響') if not n else (None, f'有 {n} 個系統還原點：搬移可能讓 Windows 刪掉較舊的還原點（第一次搬移前會先問你）')
        _check(out, f'{lt} 系統還原點', _vss)
        if move_test:
            import hz_vault as VA
            vr = VA.vault_root(lt + '\\')
            try: eng.vault._prepare_root(vr)
            except Exception: pass
            _check(out, f'{lt} 搬移測試', lambda lt=lt, vr=vr: _move_test(lt, vr))
    return {'t': time.time(), 'checks': out}


def report_text(r):
    lines = [f'HotZone FM 自我檢查　{time.strftime("%Y-%m-%d %H:%M", time.localtime(r["t"]))}']
    for c in r['checks']:
        mark = {True: '✓', False: '✗', None: '－'}[c['ok']]
        lines.append(f'{mark} {c["name"]}：{c["detail"]}（{c["ms"]} ms）')
    return '\n'.join(lines)

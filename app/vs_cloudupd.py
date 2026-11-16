"""☁ 雲端自動更新（V0.6.01）：讀 GitHub Releases 上的 update.json，有新版就提示；按「更新」才下載.
沒有 Qt。

- 程式更新（ZIP）：下載 SC_V….zip 放進 UPDATE → 用原本的熱更新套用（程式不用關）。
- 外殼更新（換 EXE）：update.json 的 launcher 比現在的大才需要。下載 SC_Shell_L….zip，寫一個小 BAT：
  等 SortCut 關掉 → 換 VideoSift.exe 和 _internal → 重新打開 SortCut。
- 下載完都比 SHA-256，不一樣就不用（防止下載壞掉）。
"""
import hashlib
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

URLS = ['https://github.com/tpc20001/SortCut/releases/latest/download/update.json',          # SortCut 是公開的 repo：更新檔就放它自己的 Releases
        'https://github.com/tpc20001/SortCut-Release/releases/latest/download/update.json']   # （以後如果改成 Private，更新檔改放這個公開 repo）
UA = 'SortCut-Updater'


def vkey(v):
    import re
    return tuple(int(x) for x in re.findall(r'\d+', str(v or ''))) or (0,)


def launcher_ver():
    """現在這個 EXE 是第幾版啟動器（新的啟動器會設環境變數；舊的＝1）."""
    try: return int(os.environ.get('SC_LAUNCHER') or 1)
    except ValueError: return 1


def _open(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/octet-stream, application/json'})
    return urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context())


def check(cur_ver, urls=None):
    """回 {'ok', 'newer', 'info', 'url', 'message'}；info 是 update.json 的內容."""
    err = ''
    for u in (urls or URLS):
        try:
            with _open(u) as r: info = json.loads(r.read().decode('utf-8-sig'))
            if not info.get('version'): err = f'{u}：update.json 裡沒有版本'; continue
            info['need_shell'] = bool(info.get('shell')) and int(info.get('launcher') or 1) > launcher_ver()
            info['shell_only'] = info['need_shell'] and vkey(info['version']) <= vkey(cur_ver)   # V0.6.02 程式已經是最新、只差 EXE 也要提示
            newer = vkey(info['version']) > vkey(cur_ver) or info['need_shell']
            return {'ok': True, 'newer': newer, 'info': info, 'url': u, 't': time.time(),
                    'message': f"雲端最新 V{info['version']}" + ('（程式已是最新，EXE 有新版）' if info['shell_only'] else '（有新版）' if newer else '（已經是最新）')}
        except Exception as ex: err = f'{type(ex).__name__}: {ex}'
    return {'ok': False, 'newer': False, 'info': None, 't': time.time(), 'message': '連不到 GitHub 更新：' + err}


def download(url, dest, sha256='', cb=None, cancel=None):
    """下載到 dest（先寫 .part），比對 SHA-256；cb(已下載, 全部)."""
    dest = Path(dest); dest.parent.mkdir(parents=True, exist_ok=True); tmp = dest.with_suffix(dest.suffix + '.part'); h = hashlib.sha256()
    with _open(url, timeout=60) as r, open(tmp, 'wb') as f:
        tot = int(r.headers.get('Content-Length') or 0); got = 0
        while True:
            if cancel and cancel(): raise InterruptedError('取消了')
            b = r.read(1 << 20)
            if not b: break
            f.write(b); h.update(b); got += len(b)
            if cb: cb(got, tot)
    if sha256 and h.hexdigest().lower() != str(sha256).lower():
        try: tmp.unlink()
        except Exception: pass
        raise IOError('下載的檔案不完整（SHA-256 對不上），請再試一次')
    os.replace(tmp, dest); return dest


def shell_bat(root, shell_zip, pid, exe='VideoSift.exe'):
    """寫一個 BAT：等 SortCut（pid）關掉 → 解開新外殼 → 換掉 VideoSift.exe、_internal → 重新打開。失敗就換回舊的."""
    root = Path(root); bat = root / 'UPDATE' / 'shell_update.bat'; tmp = root / 'UPDATE' / 'shell_new'; logf = root / 'LOG' / 'update_log.txt'
    q = lambda p: str(p).replace('%', '%%')
    s = f"""@echo off
chcp 65001 >nul
title SortCut 更新外殼
echo 等 SortCut 關掉...
set /a N=0
:wait
set /a N+=1
if %N% GTR 120 goto go
tasklist /FI "PID eq {int(pid)}" /NH 2>nul | find /I "{exe}" >nul && (timeout /t 1 /nobreak >nul & goto wait)
:go
timeout /t 2 /nobreak >nul
echo [%date% %time%] 外殼更新開始 >> "{q(logf)}"
if exist "{q(tmp)}" rmdir /s /q "{q(tmp)}"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '{q(shell_zip)}' -DestinationPath '{q(tmp)}' -Force"
if not exist "{q(tmp)}\\{exe}" goto fail
if exist "{q(root)}\\_internal_old" rmdir /s /q "{q(root)}\\_internal_old"
if exist "{q(root)}\\{exe}.old" del /f /q "{q(root)}\\{exe}.old"
move "{q(root)}\\_internal" "{q(root)}\\_internal_old" >nul
move "{q(root)}\\{exe}" "{q(root)}\\{exe}.old" >nul
robocopy "{q(tmp)}" "{q(root)}" /E /R:3 /W:2 /NFL /NDL /NJH /NJS /NP >nul
if not exist "{q(root)}\\{exe}" goto restore
echo [%date% %time%] 外殼更新完成 >> "{q(logf)}"
rmdir /s /q "{q(tmp)}"
start "" /D "{q(root)}" "{q(root)}\\{exe}"
rmdir /s /q "{q(root)}\\_internal_old" 2>nul
del /f /q "{q(root)}\\{exe}.old" 2>nul
exit /b 0
:restore
echo [%date% %time%] 外殼更新失敗，換回舊的 >> "{q(logf)}"
if exist "{q(root)}\\_internal" rmdir /s /q "{q(root)}\\_internal"
move "{q(root)}\\_internal_old" "{q(root)}\\_internal" >nul
move "{q(root)}\\{exe}.old" "{q(root)}\\{exe}" >nul
:fail
echo [%date% %time%] 外殼更新沒有成功（解壓縮失敗），用原本的 >> "{q(logf)}"
start "" /D "{q(root)}" "{q(root)}\\{exe}"
exit /b 1
"""
    bat.parent.mkdir(parents=True, exist_ok=True); bat.write_text(s, encoding='utf-8'); return bat


def run_bat(bat):
    """開一個不擋住 SortCut 的 BAT（SortCut 關掉它還繼續跑）."""
    if os.name == 'nt':
        subprocess.Popen(['cmd', '/c', str(bat)], creationflags=0x00000008 | 0x00000200 | 0x08000000, close_fds=True)   # DETACHED | NEW_GROUP | NO_WINDOW
    else:
        subprocess.Popen(['sh', '-c', f'echo {bat}'])

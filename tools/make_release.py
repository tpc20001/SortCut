"""雲端打包用（GitHub Actions 會叫）：做出 Release 要放的檔案.

python tools/make_release.py --version            → 印出程式版本（例如 0.6.01）
python tools/make_release.py --dist <PyInstaller 的 dist\\VideoSift> --out out --repo tpc20001/SortCut-Release

產生：
  SC_V<版本>.zip           程式更新包（app\\*.py…＋manifest.json），程式裡「☁ 更新」下載的就是這個
  SC_Shell_L<啟動器>.zip    外殼（VideoSift.exe＋_internal），啟動器版本變了才會用到
  SortCut_Full_V<版本>.zip  第一次安裝用（外殼＋程式；FFmpeg 不在裡面，用原本的）
  update.json              給程式讀：版本、下載網址、SHA-256、更新說明
  notes.md                 Release 頁面上的說明
"""
import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / 'app'
SHELL_REQ = 1          # V0.6.12 程式最少要第幾版 EXE（外殼）才能跑。只有程式真的用到新 EXE 的功能才加一；其他時候不會叫使用者換外殼
OK_EXT = ('.py', '.json', '.md', '.txt', '.css', '.js', '.html', '.png', '.ico', '.svg')   # 跟程式裡 load_pkg 認得的一樣


def app_version():
    return re.search(r"APP_VERSION\s*=\s*'([^']+)'", (APP / 'app.py').read_text(encoding='utf-8')).group(1)


def launcher_version():
    return int(re.search(r'LAUNCHER_VERSION\s*=\s*(\d+)', (ROOT / 'build' / 'launcher.py').read_text(encoding='utf-8')).group(1))


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def app_files():
    return sorted(f for f in APP.iterdir() if f.is_file() and f.suffix.lower() in OK_EXT and '__pycache__' not in f.parts)


def zip_dir(zf, src, prefix=''):
    for p in sorted(Path(src).rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts: zf.write(p, (prefix + p.relative_to(src).as_posix()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', action='store_true'); ap.add_argument('--launcher', action='store_true')
    ap.add_argument('--dist', default=''); ap.add_argument('--out', default='out'); ap.add_argument('--repo', default='tpc20001/SortCut')
    a = ap.parse_args()
    ver = app_version(); L = launcher_version()
    if a.version: print(ver); return
    if a.launcher: print(L); return
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tag = f'v{ver}'; base = f'https://github.com/{a.repo}/releases/download/{tag}/'

    zp = out / f'SC_V{ver}.zip'                                                  # 程式更新包（跟以前手動給的格式一樣）
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('manifest.json', json.dumps({'version': ver, 'requires_launcher': 1}))
        for f in app_files(): zf.write(f, 'app/' + f.name)
    files = {'zip': zp}
    if a.dist:
        d = Path(a.dist)
        if not (d / 'VideoSift.exe').exists(): sys.exit(f'找不到 {d / "VideoSift.exe"}')
        sp = out / f'SC_Shell_L{L}.zip'
        with zipfile.ZipFile(sp, 'w', zipfile.ZIP_DEFLATED) as zf: zip_dir(zf, d)
        fp = out / f'SortCut_Full_V{ver}.zip'
        with zipfile.ZipFile(fp, 'w', zipfile.ZIP_DEFLATED) as zf:
            zip_dir(zf, d, 'SortCut/')
            for f in app_files(): zf.write(f, 'SortCut/app/' + f.name)
            ico = ROOT / 'VideoSift.ico'
            if ico.exists(): zf.write(ico, 'SortCut/VideoSift.ico')
            for n in ('UPDATE', 'LOG', 'Data'): zf.writestr(f'SortCut/{n}/', '')
        files.update(shell=sp, full=fp)

    try: C = json.loads((APP / 'CHANGELOG.json').read_text(encoding='utf-8'))
    except Exception: C = []
    cur = next((e for e in C if str(e.get('version')) == ver), None) or {}
    info = {'version': ver, 'launcher': L, 'shell_req': SHELL_REQ, 'date': cur.get('date', ''), 'tag': tag, 'notes': list(cur.get('items') or []),
            'zip': base + files['zip'].name, 'zip_sha256': sha(files['zip']), 'zip_size': files['zip'].stat().st_size}
    if 'shell' in files:
        info.update(shell=base + files['shell'].name, shell_sha256=sha(files['shell']), shell_size=files['shell'].stat().st_size,
                    full=base + files['full'].name, full_sha256=sha(files['full']))
    (out / 'update.json').write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding='utf-8')
    md = [f'## SortCut V{ver}', '']
    md += [f'- {x}' for x in info['notes']] or ['- （這版沒有寫更新說明）']
    md += ['', '### 檔案', f'- `SC_V{ver}.zip`：程式更新包（程式裡按「☁ 更新」會自己下載這個）',
           f'- `SC_Shell_L{L}.zip`：外殼（EXE），啟動器第 {L} 版', f'- `SortCut_Full_V{ver}.zip`：第一次安裝用（不含 FFmpeg）', '- `update.json`：給程式讀的版本資訊']
    (out / 'notes.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(json.dumps({k: (str(v) if isinstance(v, Path) else v) for k, v in info.items() if k != 'notes'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()

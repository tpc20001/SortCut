"""V0.6.31 熱更新只換 app/*.py，不換 EXE：程式不能 import EXE 裡沒有的模組（例如 html）。
這裡列出 app/*.py 用到的外部模組，不在「EXE 裡有的」清單就失敗（雲端打包前跑）。
要用新的標準函式庫模組：先加進 build/_deps.py（只對之後新的 EXE 有用），而且舊 EXE 也要能動 → 最好別用。"""
import ast, glob, os, sys

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 舊 EXE 裡確定有的（build/_deps.py ＋ 這些模組間接帶進來的、以前就在用的）
KNOWN = set('''__future__ argparse array binascii calendar faulthandler fnmatch hmac mimetypes mmap msvcrt ntpath pickle platform
secrets socket stat types encodings codecs locale select selectors signal copy enum inspect operator abc contextlib numbers'''.split())
OPTIONAL = {'PIL', 'cv2', 'numpy', 'onnxruntime', 'insightface', 'imageio_ffmpeg'}      # 有 try／沒有也能動的


def main():
    deps = set()
    for n in ast.walk(ast.parse(open(os.path.join(KIT, 'build', '_deps.py'), encoding='utf-8').read())):
        if isinstance(n, ast.Import): deps |= {a.name.split('.')[0] for a in n.names}
        if isinstance(n, ast.ImportFrom) and n.module: deps.add(n.module.split('.')[0])
    local = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(KIT, 'app', '*.py'))}
    ok = deps | local | KNOWN | OPTIONAL; bad = []
    for p in sorted(glob.glob(os.path.join(KIT, 'app', '*.py'))):
        for n in ast.walk(ast.parse(open(p, encoding='utf-8').read())):
            ms = [a.name for a in n.names] if isinstance(n, ast.Import) else ([n.module] if isinstance(n, ast.ImportFrom) and n.module and n.level == 0 else [])
            bad += [f'{os.path.basename(p)}:{n.lineno} import {m}' for m in ms if m.split('.')[0] not in ok]
    if bad:
        print('✖ 舊 EXE 裡沒有這些模組（熱更新會失敗）：'); print('\n'.join(bad)); sys.exit(1)
    print('IMPORTS OK')


if __name__ == '__main__': main()

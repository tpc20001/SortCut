"""📈 資料分析（不准 import Qt）：把要整理的資料夾整個走一遍，統計每一類佔多少。

重點：遊戲、軟體、程式專案「整包資料夾」算一個，不拆開用檔案來看
（遊戲裡的 .png 素材不算照片、軟體裡的 .exe 不算安裝檔）。
判斷的依據（why）會存起來，畫面上看得到「為什麼說它是遊戲」。
"""
import os, re, time


class _Heap:
    """小頂堆（不用 heapq：舊版啟動器 EXE 裡沒有打包 heapq）."""
    @staticmethod
    def heappush(h, x):
        h.append(x); i = len(h) - 1
        while i > 0:
            p = (i - 1) // 2
            if h[i] < h[p]: h[i], h[p] = h[p], h[i]; i = p
            else: break

    @staticmethod
    def _down(h, i):
        n = len(h)
        while True:
            l = 2 * i + 1; r = l + 1; m = i
            if l < n and h[l] < h[m]: m = l
            if r < n and h[r] < h[m]: m = r
            if m == i: return
            h[i], h[m] = h[m], h[i]; i = m

    @staticmethod
    def heappop(h):
        last = h.pop()
        if not h: return last
        top = h[0]; h[0] = last; _Heap._down(h, 0); return top

    @staticmethod
    def heapify(h):
        for i in range(len(h) // 2 - 1, -1, -1): _Heap._down(h, i)


heapq = _Heap

import fc_fcore as fcore

# (代號, 名稱, 顏色)：順序＝圖上的順序
CATS = [('photo', '照片', '#3b8eea'), ('video', '影片', '#e5484d'), ('audio', '音樂／錄音', '#c678dd'), ('doc', '文件', '#e5c07b'),
        ('archive', '壓縮檔／光碟映像', '#d19a66'), ('installer', '安裝檔', '#98a2b3'), ('game', '遊戲', '#2bb673'), ('app', '軟體', '#1fb5c9'),
        ('dev', '程式開發', '#f06ea9'), ('backup', '備份', '#8f7cf0'), ('system', '系統', '#6b7280'), ('other', '其他', '#4b5563')]
CAT_NM = {k: n for k, n, _c in CATS}
CAT_COL = {k: c for k, _n, c in CATS}
PKG_TYPES = ('game', 'app', 'dev', 'backup', 'system')
PKG_ICON = {'game': '🎮', 'app': '🧩', 'dev': '💻', 'backup': '💾', 'system': '⚙'}

EXT = {}
for _c, _L in (('photo', fcore.PHOTO | {'.svg', '.ico', '.jfif', '.avif', '.jxl'}),
               ('video', fcore.VIDEO | {'.ts', '.vob', '.rmvb', '.rm', '.f4v', '.asf', '.m2v', '.divx', '.ogv'}),
               ('audio', {'.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.wma', '.ape', '.opus', '.amr', '.aiff', '.aif', '.mid', '.midi', '.m4b', '.dsf', '.dff'}),
               ('doc', {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md', '.rtf', '.odt', '.ods', '.odp', '.csv', '.epub', '.mobi', '.azw3',
                        '.pages', '.key', '.numbers', '.psd', '.ai', '.xcf', '.indd', '.cdr', '.dwg', '.hwp', '.one', '.vsdx', '.xmind'}),
               ('archive', {'.zip', '.rar', '.7z', '.tar', '.gz', '.tgz', '.bz2', '.xz', '.iso', '.img', '.dmg', '.cab', '.zst', '.lz4', '.001', '.vhd', '.vhdx', '.wim', '.esd'}),
               ('installer', {'.exe', '.msi', '.apk', '.xapk', '.ipa', '.appx', '.msix', '.msixbundle', '.msu', '.pkg', '.deb', '.rpm'})):
    for _e in _L: EXT[_e] = _c
GAME_EXT = {'.pak', '.vpk', '.pck', '.rpa', '.xp3', '.bsa', '.ba2', '.wad', '.upk', '.forge', '.wpk', '.npk', '.cpk', '.gcf', '.rgssad', '.rgss2a', '.rgss3a',
            '.assets', '.ucas', '.utoc', '.big', '.dzip', '.arz', '.arc4'}
BINLIKE = {'bin', 'bin32', 'bin64', 'binaries', 'win32', 'win64', 'x64', 'x86', 'amd64', 'windowsnoeditor', 'wingdk', 'program', 'retail', 'shipping', 'release'}
UNINST = {'unins000.exe', 'unins001.exe', 'uninstall.exe', 'uninst.exe', 'uninstaller.exe', 'uninstall.dat', 'unins000.dat'}
GAME_HOME = {'epic games': 'Epic 遊戲庫', 'gog games': 'GOG 遊戲庫', 'xboxgames': 'Xbox 遊戲庫', 'riot games': 'Riot 遊戲', 'ea games': 'EA 遊戲庫',
             'origin games': 'Origin 遊戲庫', 'ubisoft game launcher': 'Ubisoft 遊戲', 'battle.net': 'Battle.net 遊戲', 'wegame': 'WeGame 遊戲庫'}
APP_HOME = {'program files': 'Program Files 裡的軟體', 'program files (x86)': 'Program Files 裡的軟體', 'windowsapps': 'Microsoft Store 軟體', 'programdata': 'ProgramData 程式資料'}
SYS_NAMES = {'$windows.~bt': 'Windows 更新暫存', '$windows.~ws': 'Windows 更新暫存', 'windows.old': '舊的 Windows（升級留下的）', 'recovery': '系統還原',
             'msocache': 'Office 安裝快取', '$sysreset': '系統重設暫存', 'perflogs': '系統效能紀錄', '$winreagent': 'Windows 更新暫存'}
# 🧹 雜物：系統／暫存留下的檔（可以放心搬走）
TEMP_NAMES = {'thumbs.db', 'ehthumbs.db', 'ehthumbs_vista.db', '.ds_store', 'desktop.ini', '.localized', 'icon\r'}
TEMP_EXT = {'.tmp', '.temp', '.crdownload', '.part', '.partial', '.download', '.!ut', '.bak~'}
JUNK_KINDS = [('edir', '📂', '空資料夾'), ('efile', '📄', '0 位元組的檔案'), ('temp', '🗑', '暫存／系統雜檔'), ('big', '🐘', '最大的 300 個檔')]


def is_temp(ln):
    return ln in TEMP_NAMES or ln.startswith('~$') or (ln.startswith('._') and len(ln) > 2) or os.path.splitext(ln)[1] in TEMP_EXT


MIN_KEEP = 50 * 1024 * 1024          # 比這個小的資料夾不單獨存（樹狀圖上合成「其他小資料夾」）


def cat_of(ext): return EXT.get(ext, 'other')


def _add(D, k, n, b):
    x = D.get(k)
    if x is None: D[k] = [n, b]
    else: x[0] += n; x[1] += b


def _merge(D, S):
    for k, (n, b) in S.items(): _add(D, k, n, b)


class _F:
    """一個資料夾（走的時候）."""
    __slots__ = ('path', 'name', 'depth', 'up', 'inpkg', 'pkg', 'why', 'kidpkg', 'kidwhy', 'todo', 'files', 'dirs', 'own', 'raw', 'eff', 'n', 'b', 'mt',
                 'gx', 'exe', 'pkids', 'kept')

    def __init__(self, path, depth, up):
        self.path = path; self.name = os.path.basename(path.rstrip('\\/')).lower() or path.lower(); self.depth = depth; self.up = up
        self.inpkg = bool(up is not None and (up.inpkg or up.pkg)); self.pkg = ''; self.why = ''; self.kidpkg = ''; self.kidwhy = ''
        self.todo = []; self.files = []; self.dirs = set(); self.own = {}; self.raw = {}; self.eff = {}; self.n = 0; self.b = 0; self.mt = 0.0
        self.gx = 0; self.exe = 0; self.pkids = []; self.kept = False


def classify(F):
    """看這一層的檔名／資料夾名，判斷是不是一整包（遊戲／軟體／程式專案／備份／系統）。回傳 (類型, 為什麼) 或 ('', '')."""
    up = F.up; nm = F.name; fs = F.files; ds = F.dirs; S = set(fs)
    upn = up.name if up is not None else ''
    if up is not None and up.kidpkg: return up.kidpkg, up.kidwhy
    if upn == 'steamapps' and nm != 'common': return 'game', f'Steam 遊戲資料（{F.path.rstrip(chr(92) + "/").split(os.sep)[-1]}）'
    exes = [f for f in fs if f.endswith('.exe')]; dlls = sum(1 for f in fs if f.endswith('.dll'))
    # 程式開發
    if nm == 'node_modules': return 'dev', 'Node.js 套件（node_modules）'
    if '.git' in ds: return 'dev', '程式專案（有 .git）'
    if 'pyvenv.cfg' in S: return 'dev', 'Python 虛擬環境（pyvenv.cfg）'
    if any(f.endswith('.sln') for f in fs): return 'dev', 'Visual Studio 專案（.sln）'
    # 遊戲（很確定的記號）
    if 'unityplayer.dll' in S or 'gameassembly.dll' in S: return 'game', 'Unity 遊戲（UnityPlayer.dll）'
    for e in exes:
        if e[:-4] + '_data' in ds: return 'game', f'Unity 遊戲（{e} ＋ {e[:-4]}_Data）'
    if S & {'steam_api.dll', 'steam_api64.dll', 'steam_appid.txt'}: return 'game', 'Steam 遊戲（steam_api）'
    if any(f.startswith('goggame-') for f in fs): return 'game', 'GOG 遊戲（goggame-…）'
    if S & {'eossdk-win64-shipping.dll', 'eossdk-win32-shipping.dll'}: return 'game', 'Epic 遊戲（EOSSDK）'
    if any(e.endswith('-shipping.exe') for e in exes): return 'game', 'Unreal 引擎遊戲（…-Shipping.exe）'
    if 'engine' in ds and exes and ('content' in ds or any(d.endswith('game') for d in ds) or len(ds) <= 4): return 'game', 'Unreal 引擎遊戲（Engine 資料夾＋執行檔）'
    if 'renpy' in ds and 'game' in ds: return 'game', "Ren'Py 遊戲"
    if 'www' in ds and ('nw.dll' in S or 'game.exe' in S): return 'game', 'RPG Maker MV／MZ 遊戲'
    if any(f.startswith('rgss') and f.endswith('.dll') for f in fs) or any(os.path.splitext(f)[1] in ('.rgssad', '.rgss2a', '.rgss3a') for f in fs): return 'game', 'RPG Maker 遊戲（RGSS）'
    if 'data.win' in S and exes: return 'game', 'GameMaker 遊戲（data.win）'
    if exes:
        gx = sorted({os.path.splitext(f)[1] for f in fs} & GAME_EXT)
        if gx: return 'game', f'遊戲（執行檔＋{"、".join(gx[:3])} 遊戲資料檔）'
    # 系統、備份
    if nm == 'windows' and 'system32' in ds: return 'system', 'Windows 系統資料夾'
    if nm in SYS_NAMES: return 'system', SYS_NAMES[nm]
    if nm == 'windowsimagebackup': return 'backup', 'Windows 系統映像備份'
    if ('manifest.db' in S or 'manifest.mbdb' in S) and ('info.plist' in S or 'status.plist' in S): return 'backup', 'iPhone／iPad 備份（iTunes）'
    # 軟體
    u = S & UNINST
    if u: return 'app', f'軟體（有解除安裝程式 {sorted(u)[0]}）'
    if exes and 'resources' in ds and 'locales' in ds: return 'app', '軟體（Electron：resources＋locales）'
    if exes and dlls >= 3: return 'app', f'軟體（{len(exes)} 個 .exe、{dlls} 個 .dll）'
    return '', ''


def _container(F):
    """這一層本身不是一包，但底下每個資料夾都是一包（例如 Steam 的 common、Program Files）."""
    nm = F.name; upn = F.up.name if F.up is not None else ''
    if nm == 'common' and upn == 'steamapps': return 'game', 'Steam 遊戲（steamapps\\common）'
    if nm in GAME_HOME: return 'game', GAME_HOME[nm]
    if nm in APP_HOME: return 'app', APP_HOME[nm]
    if nm in ('local', 'roaming', 'locallow') and upn == 'appdata': return 'app', f'程式資料（AppData\\{F.path.rstrip(chr(92) + "/").split(os.sep)[-1]}）'
    if nm == 'backup' and upn == 'mobilesync': return 'backup', 'iPhone／iPad 備份（iTunes）'
    return '', ''


def _open(F, skip_dirs, J=None):
    """讀這一層：檔案（名稱、大小、時間）、子資料夾."""
    try: it = os.scandir(fcore.lp(F.path))
    except OSError: return
    with it:
        for e in it:
            try:
                if e.is_dir(follow_symlinks=False):
                    ln = e.name.lower()
                    if ln in skip_dirs: continue
                    st = e.stat(follow_symlinks=False)
                    if getattr(st, 'st_file_attributes', 0) & 0x400: continue      # junction／symlink：不跟進去（不然會算兩次）
                    F.dirs.add(ln); F.todo.append(os.path.join(F.path, e.name))
                elif e.is_file(follow_symlinks=False):
                    st = e.stat(follow_symlinks=False); ln = e.name.lower(); ext = os.path.splitext(ln)[1]; sz = st.st_size
                    F.files.append(ln); F.n += 1; F.b += sz
                    if st.st_mtime > F.mt: F.mt = st.st_mtime
                    c = cat_of(ext); _add(F.raw, c, 1, sz)
                    if not F.inpkg: _add(F.own, c, 1, sz)
                    if ext in GAME_EXT: F.gx += sz
                    if ext == '.exe': F.exe += 1
                    if J is not None and not F.inpkg:                              # 🧹 雜物（遊戲／軟體裡面的不算）
                        p = os.path.join(F.path, e.name)
                        if is_temp(ln): J['temp'].append((p, sz, st.st_mtime))
                        elif sz == 0: J['efile'].append((p, 0, st.st_mtime))
                        if sz > J['bigmin']:
                            heapq.heappush(J['big'], (sz, p, st.st_mtime))
                            if len(J['big']) > 300: heapq.heappop(J['big']); J['bigmin'] = J['big'][0][0]
            except OSError: continue


def analyze(root, stop=None, tick=None, junk=None):
    """走完整個 root。回傳 {'rows': {路徑: 資料夾資料}, 'eff': 每一類, 'raw': 檔案本身的類別, 'n', 'b', 'dirs', 'sec'}.
    rows 只存「不在某一包裡面」而且夠大（或前兩層、或本身就是一包）的資料夾：樹狀圖、清單用。"""
    t0 = time.time(); root = os.path.normpath(str(root)); skip = set(fcore.SKIP_DIRS) - {'.vsdata', '_vs_tmp'}
    rows = {}; ndir = 0; nfile = [0]; last = [time.time()]
    if not os.path.isdir(fcore.lp(root)): raise FileNotFoundError(f'找不到資料夾 {root}（硬碟沒接上？）')

    def start(path, depth, up):
        F = _F(path, depth, up)
        if not F.inpkg:
            F.kidpkg, F.kidwhy = _container(F)
        _open(F, skip, junk)
        if not F.inpkg and depth > 0:
            F.pkg, F.why = classify(F)
            if F.pkg: F.own = {}                                                  # 一整包：裡面的檔案不分開算
        nfile[0] += F.n
        if tick is not None and time.time() - last[0] > 1.0: last[0] = time.time(); tick(nfile[0], path)
        F.files = F.files if not F.inpkg else []                                   # 包裡面的檔名用不到了，省記憶體
        return F

    def drop_under(path):
        pre = path.rstrip('\\/') + os.sep
        for k in [k for k in rows if k.startswith(pre)]: rows.pop(k, None)

    def promote(F, typ, why):
        F.pkg, F.why = typ, why; drop_under(F.path)

    def finish(F):
        if not F.inpkg and not F.pkg and F.depth > 0 and not F.kidpkg and F.name not in APP_HOME and F.name not in GAME_HOME:
            K = [k for k in F.pkids if k[0] in BINLIKE and k[1] in ('game', 'app')]
            if K:                                                                  # …\遊戲\Binaries\Win64 判斷出來 → 整個「遊戲」資料夾算一包
                k = next((x for x in K if x[1] == 'game'), K[0]); promote(F, k[1], k[2] + f'（在 {k[0]} 裡）')
            elif 'engine' in F.dirs and any(k[1] == 'game' for k in F.pkids): promote(F, 'game', 'Unreal 引擎遊戲（Engine＋遊戲資料夾）')
            elif F.exe and F.gx >= 100e6 and F.gx >= F.b * 0.3: promote(F, 'game', f'遊戲（執行檔＋{F.gx / 1e9:.1f} GB 遊戲資料檔）')
        if junk is not None and F.pkg and not F.inpkg: junk_drop(junk, F.path)        # 一整包（遊戲／軟體）：裡面的不算雜物
        if junk is not None and not F.inpkg and F.depth > 0 and F.n == 0 and not F.pkg: junk['edir'].append((F.path, 0, F.mt))
        if F.pkg: F.eff = {F.pkg: [F.n, F.b]}
        else:
            _merge(F.eff, F.own)
        U = F.up
        if U is not None:
            U.n += F.n; U.b += F.b; U.mt = max(U.mt, F.mt); U.gx += F.gx; _merge(U.raw, F.raw)
            if not U.inpkg and not U.pkg: _merge(U.eff, F.eff)
            if F.pkg and not F.inpkg: U.pkids.append((F.name, F.pkg, F.why))
        if not F.inpkg and (F.depth <= 2 or F.b >= MIN_KEEP or F.pkg or F.kept):      # 底下有存的（例如一包遊戲）→ 這層也要存，樹狀圖才點得進去
            if U is not None: U.kept = True
            rows[F.path] = {'path': F.path, 'parent': U.path if U is not None else '', 'depth': F.depth, 'b': F.b, 'n': F.n, 'eff': F.eff,
                            'pkg': F.pkg, 'why': F.why, 'raw': F.raw if F.pkg else {}, 'mt': F.mt, 'kids': bool(F.dirs) and not F.pkg}

    top = start(root, 0, None); stack = [top]
    while stack:
        if stop is not None and stop(): raise InterruptedError
        F = stack[-1]
        if F.todo:
            stack.append(start(F.todo.pop(), F.depth + 1, F)); ndir += 1; continue
        stack.pop(); finish(F)
    R = rows.get(root) or {}
    return {'rows': rows, 'eff': R.get('eff') or {}, 'raw': top.raw, 'n': R.get('n', 0), 'b': R.get('b', 0), 'dirs': ndir + 1,
            'sec': round(time.time() - t0, 1), 'files_seen': nfile[0]}


def squarify(items, x, y, w, h):
    """樹狀圖排版（squarified）：items＝[(值, 任何東西)]，大的先。回傳 [(x, y, w, h, 東西)]."""
    items = [(float(v), o) for v, o in items if v > 0]
    tot = sum(v for v, _o in items); out = []
    if tot <= 0 or w <= 0 or h <= 0: return out
    sc = w * h / tot; items = [(v * sc, o) for v, o in items]

    def worst(row, side):
        s = sum(v for v, _o in row); mx = max(v for v, _o in row); mn = min(v for v, _o in row)
        return max(side * side * mx / (s * s), (s * s) / (side * side * mn))

    i = 0
    while i < len(items):
        side = min(w, h); row = [items[i]]; i += 1
        while i < len(items) and worst(row + [items[i]], side) <= worst(row, side): row.append(items[i]); i += 1
        s = sum(v for v, _o in row)
        if w >= h:
            cw = s / h if h else 0; cy = y
            for v, o in row: ch = v / cw if cw else 0; out.append((x, cy, cw, ch, o)); cy += ch
            x += cw; w -= cw
        else:
            rh = s / w if w else 0; cx = x
            for v, o in row: cw2 = v / rh if rh else 0; out.append((cx, y, cw2, rh, o)); cx += cw2
            y += rh; h -= rh
    return out


def dominant(eff):
    """這個資料夾主要是哪一類（看大小）."""
    if not eff: return 'other'
    return max(eff.items(), key=lambda kv: kv[1][1])[0]


def junk_drop(J, path):
    pre = path.rstrip('\\/') + os.sep
    for k in ('edir', 'efile', 'temp'): J[k] = [x for x in J[k] if not x[0].startswith(pre)]
    b = [x for x in J['big'] if not x[1].startswith(pre)]
    if len(b) != len(J['big']): heapq.heapify(b); J['big'] = b; J['bigmin'] = b[0][0] if len(b) >= 300 else 0


def new_junk():
    return {'edir': [], 'efile': [], 'temp': [], 'big': [], 'bigmin': 0}


def junk_rows(J):
    """空資料夾只留最上層那個（裡面整串都是空的）；最大的照大小排."""
    E = {p for p, _b, _m in J['edir']}
    J['edir'] = [x for x in J['edir'] if os.path.dirname(x[0].rstrip('\\/')) not in E]
    J['big'] = sorted(J['big'], reverse=True)
    return [(k, p, b, m) for k in ('edir', 'efile', 'temp') for p, b, m in J[k]] + [('big', p, b, m) for b, p, m in J['big']]

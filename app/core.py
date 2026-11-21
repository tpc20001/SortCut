"""SortCut core — everything that is not UI (no Qt here).

影片庫（掃描、ffprobe）、每 2 秒一張的預覽圖（拼成 10x10 的大圖存）、初剪（免轉檔）、轉檔（H.265，顯示卡 NVENC 或 CPU）、
歸檔（初剪／收藏／待刪／原檔備份）、LOG、效能（CPU／RAM／GPU）。
規則：所有讀硬碟、跑 FFmpeg 的事都在背景執行緒；畫面只拿結果。
"""
import urllib.request
import os, sys, re, json, time, platform, math, random, shutil, sqlite3, threading, subprocess, traceback, queue, bisect, zipfile, fnmatch, base64, binascii, urllib.parse
from pathlib import Path
from collections import OrderedDict, deque

import vs_disk

APP_NAME = 'SortCut'
VIDEO_EXT = {'.mp4', '.m4v', '.mov', '.mkv', '.avi', '.flv', '.f4v', '.ts', '.m2ts', '.mts', '.tp', '.trp', '.rm', '.rmvb', '.wmv', '.asf',
             '.mpg', '.mpeg', '.mpe', '.m1v', '.m2v', '.vob', '.webm', '.3gp', '.3g2', '.ogv', '.divx', '.xvid', '.dat', '.mxf', '.dv', '.qt', '.amv'}
MP4_EXT = {'.mp4', '.m4v'}
ARCH = {'cut': '_初剪', 'fav': '_收藏', 'trash': '_待刪', 'orig': '_原檔備份'}           # V0.1.08 以前：直接放在硬碟最上層（G:\\_初剪）
ARCH_BASE = 'VideoSIFT'
PACK_DIR = '.vsdata'                                                                     # V0.2.26 每顆硬碟自己的 SortCut 資料：X:\\VideoSIFT\\.vsdata\\                                                                  # V0.1.09 起：全部集中在每顆硬碟的 G:\\VideoSIFT\\ 底下
VS_RE = re.compile(r'_V(\d*)S$', re.I)                                                   # V0.1.94 轉好的檔名結尾：_VS、_V2S、_V3S…（SortCut 轉過幾次）


def is_vcd_dat(name):
    """.dat 是不是 VCD 影片（AVSEQ01.DAT、MUSIC01.DAT…）：其他 .dat 多半是遊戲、程式的資料檔."""
    return bool(re.match(r'^(AVSEQ|MUSIC|ITEM)\d+\.DAT$', str(name), re.I))


def vs_gen(name):
    """檔名是第幾代轉檔：沒標＝0、_VS＝1、_V2S＝2…."""
    m = VS_RE.search(Path(str(name)).stem)
    return (int(m.group(1)) if m.group(1) else 1) if m else 0


def vs_stem(stem):
    """轉好的檔名：abc → abc_VS；abc_VS → abc_V2S；abc_V2S → abc_V3S."""
    m = VS_RE.search(stem)
    if not m: return stem + '_VS'
    return stem[:m.start()] + f'_V{(int(m.group(1)) if m.group(1) else 1) + 1}S'


VS_SQL = "(name GLOB '*_VS.*' OR name GLOB '*_vs.*' OR name GLOB '*_V[0-9]S.*' OR name GLOB '*_V[0-9][0-9]S.*' OR name GLOB '*_v[0-9]s.*')"
DEL_DIR = 'DELETE'                                                                       # V0.1.53 轉好之後原檔先搬到每顆硬碟最外層的 X:\\DELETE\\（抽檢沒問題再按刪除）
ARCH2 = {'cut': '初剪', 'fav': '收藏', 'trash': '待刪', 'orig': '原檔備份'}
SKIP_DIRS = {'$recycle.bin', 'system volume information', 'recycler', 'found.000', '$windows.~bt', '$windows.~ws', 'windows', 'program files',
             'program files (x86)', 'programdata', 'appdata', '$sysreset', 'msocache', 'videosift_data', ARCH_BASE.lower()} | {v.lower() for v in ARCH.values()}
SKIP_DIRS |= {'_filecompare_待確認', '_filecompare_轉檔後隔離區', '_filecompare_修復結果', 'filecompare_問題影片'}   # V0.5.36 整理（FileCompare）的隔離區／修復結果／問題影片：不收進影片庫（不重做預覽圖、不重複）
IS_WIN = os.name == 'nt'
NO_WINDOW = 0x08000000 if IS_WIN else 0
PRIO = {'idle': 0x00000040, 'below': 0x00004000, 'normal': 0x00000020} if IS_WIN else {'idle': 0, 'below': 0, 'normal': 0}

DEFAULTS = {
    'roots': [],                    # 影片庫：要整理的硬碟／資料夾
    'ex_dirs': [],                  # 排除的資料夾（完整路徑，含底下所有子資料夾）
    'ex_names': [],                 # 排除的資料夾名稱（不管在哪一層，可用 * ?，例如 temp、*備份*）
    'scan_on_start': True,
    'th_on': True, 'th_n': 2, 'th_h': 180, 'th_step': 2, 'th_prio': 'idle', 'th_dir': '',
    'probe_n': 2,
    'cut_mode': 'copy', 'cut_merge': False, 'cut_dir': '',
    'fav_dir': '', 'fav_mode': 'copy', 'trash_dir': '',
    'cv_enc': 'auto', 'cv_q': 19, 'cv_n': 3, 'cv_preset': 'p5', 'cv_out': 'beside', 'cv_out_dir': '', 'cv_after': 'delete_dir', 'cv_verify': True, 'cv_res': 0, 'cv_cap': 'auto', 'cv_mode': 'target', 'cv_target': 0.985, 'cv_prio': 'below',
    'grid_cols': 10, 'grid_sec': 2, 'vol': 80, 'mute': False, 'list_sort': 'name', 'sub_folders': True,
    'arch_names': {'S': 'S_無條件保存', 'A': 'A_保存', 'E': 'E_觀察', 'F': 'F_刪除'}, 'arch_f_trash': True, 'arch_tree': True,   # 分級歸檔的資料夾名；F 歸到待刪；保留原本的子資料夾
    'cats': [],                     # 自訂分類資料夾（工作用、家庭日…）：歸進去就不再出現在清單
    'cover_on_start': True, 'cover_on_restore': False, 'cover_stats': True, 'cover_idle_min': 0, 'last_page': 0,     # 開機封面
    'db_backup': True, 'db_backup_keep': 7,      # 資料庫每天自動備份
    'oplog_days': 30, 'lab': {}, 'player_keys': [], 'drag_max': 600,     # 播放器快捷鍵（空＝預設）；畫面上拖曳整個寬＝最多幾秒
    'hdd_n': 1, 'net_n': 1, 'hdd_busy': 80, 'hdd_yield': True,      # HDD：同一顆一次幾部預覽圖；別的程式用到幾 % 就先等（0＝不管）；轉檔／掃描同一顆時讓路
    'perf_float': False, 'close_to_tray': True, 'freeze_log_s': 2.0,
}


def now_s(): return time.strftime('%Y-%m-%d %H:%M:%S')


def parse_search(text):
    """🧪 進階搜尋：>1h <10m >30s（長度）、>2gb <500mb（大小）、4k 1440p 1080p 720p sd（解析度）、hevc h264（編碼）、ext:avi 或 .avi；
    其他的字＝檔名要有（空格隔開＝都要有）。回傳 (SQL 條件, 參數)."""
    W = []; A = []
    RES = {'4k': ('min(w,h) >= 2000', ()), '2160p': ('min(w,h) >= 2000', ()), '1440p': ('min(w,h) >= 1400 AND min(w,h) < 2000', ()), '2k': ('min(w,h) >= 1400 AND min(w,h) < 2000', ()),
           '1080p': ('min(w,h) >= 1000 AND min(w,h) < 1400', ()), '720p': ('min(w,h) >= 700 AND min(w,h) < 1000', ()), 'sd': ('min(w,h) > 0 AND min(w,h) < 700', ()), '480p': ('min(w,h) > 0 AND min(w,h) < 700', ())}
    CODEC = {'hevc': 'hevc', 'h265': 'hevc', 'x265': 'hevc', 'h264': 'h264', 'avc': 'h264', 'x264': 'h264', 'mpeg4': 'mpeg4', 'av1': 'av1', 'vp9': 'vp9', 'wmv': 'wmv3', 'mpeg2': 'mpeg2video'}
    for t in str(text).split():
        tl = t.lower()
        m = re.fullmatch(r'([<>]=?)(\d+(?:\.\d+)?)(h|m|s|小時|分|秒)', tl)
        if m:
            mul = {'h': 3600, '小時': 3600, 'm': 60, '分': 60, 's': 1, '秒': 1}[m.group(3)]; W.append(('dur > 0 AND ' if m.group(1).startswith('<') else '') + f'dur {m.group(1)} ?'); A.append(float(m.group(2)) * mul); continue
        m = re.fullmatch(r'([<>]=?)(\d+(?:\.\d+)?)(tb|gb|g|mb|kb)', tl)
        if m:
            mul = {'tb': 1e12, 'gb': 1e9, 'g': 1e9, 'mb': 1e6, 'kb': 1e3}[m.group(3)]; W.append(f'size {m.group(1)} ?'); A.append(float(m.group(2)) * mul); continue
        if tl in RES: W.append(RES[tl][0]); continue
        if tl in CODEC: W.append('vcodec=?'); A.append(CODEC[tl]); continue
        m = re.fullmatch(r'(?:ext:)?\.?([a-z0-9]{2,5})', tl) if (tl.startswith('ext:') or tl.startswith('.')) else None
        if m: W.append('ext=?'); A.append('.' + m.group(1)); continue
        m = re.fullmatch(r'(?:g|分級|grade):([saef]+|none|無|沒分)', tl)                   # V0.3.81 g:S g:SA g:none
        if m:
            v = m.group(1)
            if v in ('none', '無', '沒分'): W.append("grade=''")
            else: G_ = sorted(set(v.upper())); W.append('grade IN (' + ','.join('?' * len(G_)) + ')'); A += G_
            continue
        if tl in ('up:yes', '已上傳', 'uped'): W.append('up_t>0'); continue           # V0.3.81 📤
        if tl in ('up:no', '沒上傳', '未上傳'): W.append('up_t<=0'); continue
        if tl in ('★', 'fav', '收藏'): W.append('fav=1'); continue
        if tl in ('看過', 'seen:yes'): W.append('viewed>0'); continue
        if tl in ('沒看過', 'seen:no'): W.append('(viewed IS NULL OR viewed<=0)'); continue
        if tl.startswith('note:') and len(t) > 5: W.append('note LIKE ?'); A.append(f'%{t[5:]}%'); continue
        if t.startswith('-') and len(t) > 1: W.append('name NOT LIKE ?'); A.append(f'%{t[1:]}%'); continue   # -字＝檔名不要有
        W.append('name LIKE ?'); A.append(f'%{t}%')
    return W, A


def path_key(p):
    """比對路徑用：統一斜線、大小寫，去掉結尾的斜線."""
    return os.path.normcase(os.path.normpath(str(p))).rstrip('\\/').lower()


def fmt_t(s):
    s = int(max(0, s or 0)); return f'{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}' if s >= 3600 else f'{s // 60}:{s % 60:02d}'


def fmt_gb(b):
    """V0.2.04 標籤列用：取到小數第一位（52.3GB；1000GB 以上 1.2TB；不到 0.1GB 用 MB）."""
    b = float(b or 0)
    return '0GB' if b <= 0 else (f'{b / 1e12:.1f}TB' if b >= 1e12 else (f'{b / 1e9:.1f}GB' if b >= 1e8 else f'{max(1, round(b / 1e6))}MB'))


def fmt_b(b):
    b = float(b or 0)
    return f'{b / 1e12:.2f} TB' if b >= 1e12 else f'{b / 1e9:.2f} GB' if b >= 1e9 else f'{b / 1e6:.0f} MB' if b >= 1e6 else f'{b / 1e3:.0f} KB'


# ---------------------------------------------------------------- LOG
DUR_BINS = {'s': 'dur>0 AND dur<60', 'm': 'dur>=60 AND dur<600', 'l': 'dur>=600 AND dur<3600', 'x': 'dur>=3600', 'z': '(dur IS NULL OR dur<=0)'}
RES_BINS = {'sd': 'MIN(w,h)>0 AND MIN(w,h)<720', 'hd': 'MIN(w,h)>=720 AND MIN(w,h)<1080', 'fhd': 'MIN(w,h)>=1080 AND MIN(w,h)<2160', '4k': 'MIN(w,h)>=2160'}
RES_NAMES = [('', '全部畫質'), ('sd', '< 720p'), ('hd', '720p'), ('fhd', '1080p'), ('4k', '4K')]
DUR_NAMES = [('', '全部時長'), ('s', '< 1 分'), ('m', '1–10 分'), ('l', '10–60 分'), ('x', '> 1 小時'), ('z', '沒時長')]

def month_range(ym):
    """'2026-10' → (當月 1 號 0 點, 下個月 1 號 0 點)（本地時間）；看不懂就給 (0, 0)."""
    try:
        y, m = (int(x) for x in str(ym).split('-')[:2]); y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
        return time.mktime((y, m, 1, 0, 0, 0, 0, 0, -1)), time.mktime((y2, m2, 1, 0, 0, 0, 0, 0, -1))
    except Exception: return 0.0, 0.0


class Log:
    """app_log.txt＝什麼都記（操作、設定變更、每個工作的開始／結束／花多久／錯誤）；error_log.txt＝錯誤＋程式位置；
    ui_freeze_log.txt＝畫面卡住（含卡在哪一行）；crash_dump.txt＝程式整個掛掉時的傾印；update_log.txt＝更新／熱更新。
    每個檔超過 20 MB 換一個新的，舊的留最近 10 個."""
    KEEP = 10

    def __init__(self, d):
        self.d = Path(d); self.d.mkdir(parents=True, exist_ok=True); self.lock = threading.Lock(); self.tail = deque(maxlen=600)

    def _rotate(self, p):
        try:
            if p.exists() and p.stat().st_size > 20e6:
                os.replace(str(p), str(p.with_name(f'{p.stem}_{time.strftime("%Y%m%d_%H%M%S")}{p.suffix}')))
                olds = sorted(self.d.glob(f'{p.stem}_2*{p.suffix}'))
                for o in olds[:-self.KEEP]:
                    try: o.unlink()
                    except Exception: pass
        except Exception: pass

    def w(self, msg, f='app_log.txt'):
        th = threading.current_thread().name
        line = f'[{now_s()}] [{th}] {msg}' if f == 'app_log.txt' and th != 'MainThread' else f'[{now_s()}] {msg}'
        if f == 'app_log.txt': self.tail.append(line)
        with self.lock:
            try:
                p = self.d / f; self._rotate(p)
                with open(p, 'a', encoding='utf-8') as fh: fh.write(line + '\n')
            except Exception: pass

    def raw(self, line, f):
        """不加時間前綴（給 .jsonl：一行一筆 JSON，方便別的程式讀）."""
        with self.lock:
            try:
                p = self.d / f; self._rotate(p)
                with open(p, 'a', encoding='utf-8') as fh: fh.write(line + '\n')
            except Exception: pass

    def err(self, msg):
        tb = traceback.format_exc()
        if tb.strip() == 'NoneType: None': tb = ''.join(traceback.format_stack()[:-1])
        self.w(f'{msg}\n{tb}', 'error_log.txt'); self.w('✖ ' + msg + '　（詳細在 error_log.txt）')

    def export(self, out_zip, days=7, extra=()):
        """extra＝[(資料夾, zip 裡的子資料夾)]：V0.5.20 整理（FileCompare）的 LOG 一起放進同一包（有問題一次給我看）."""
        cut = time.time() - days * 86400; n = 0
        with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as z:
            for d_, pre in [(self.d, '')] + [(Path(a), b.rstrip('/') + '/') for a, b in extra]:
                try: L_ = sorted(Path(d_).glob('*')) if Path(d_).is_dir() else []
                except OSError: L_ = []
                for p in L_:
                    if p.is_file() and p.stat().st_mtime >= cut and p.suffix.lower() in ('.txt', '.jsonl', '.json', '.log'): z.write(p, pre + p.name); n += 1
        self.w(f'匯出 LOG：{n} 個檔（最近 {days} 天）→ {out_zip}')
        return n


# ---------------------------------------------------------------- 設定
class Settings:
    def __init__(self, path):
        self.path = Path(path); self.lock = threading.Lock(); self.d = dict(DEFAULTS)
        try:
            j = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(j, dict): self.d.update(j)
        except Exception: pass

    def get(self, k): return self.d.get(k, DEFAULTS.get(k))

    QUIET = {'perf_pos'}                                                    # 拖來拖去的位置不記

    def set(self, k, v):
        old = self.d.get(k, DEFAULTS.get(k))
        if old == v: return
        lg = getattr(self, 'log', None)
        if lg and k not in self.QUIET:
            sv = lambda x: (json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else repr(x))[:300]
            lg.w(f'設定：{k}　{sv(old)} → {sv(v)}')
        with self.lock:
            self.d[k] = v; self.path.parent.mkdir(parents=True, exist_ok=True); tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.d, ensure_ascii=False, indent=1), encoding='utf-8'); os.replace(str(tmp), str(self.path))


# ---------------------------------------------------------------- 資料庫
SCHEMA = """
CREATE TABLE IF NOT EXISTS files(
  id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE NOT NULL, root TEXT, folder TEXT, name TEXT, ext TEXT, size INTEGER, mtime REAL,
  seen REAL, missing INTEGER DEFAULT 0, probed INTEGER DEFAULT 0, probe_err TEXT DEFAULT '', has_v INTEGER DEFAULT 1,
  dur REAL DEFAULT 0, w INTEGER DEFAULT 0, h INTEGER DEFAULT 0, vcodec TEXT DEFAULT '', acodecs TEXT DEFAULT '', fps REAL DEFAULT 0,
  pix TEXT DEFAULT '', field TEXT DEFAULT '', vbr INTEGER DEFAULT 0,
  th_state INTEGER DEFAULT 0, th_n INTEGER DEFAULT 0, th_cols INTEGER DEFAULT 10, th_rows INTEGER DEFAULT 10, th_step INTEGER DEFAULT 2,
  th_dir TEXT DEFAULT '', th_err TEXT DEFAULT '', th_t REAL DEFAULT 0,
  viewed REAL DEFAULT 0, fav INTEGER DEFAULT 0, grade TEXT DEFAULT '', note TEXT DEFAULT '', cut_n INTEGER DEFAULT 0,
  cv_state INTEGER DEFAULT 0, cv_q REAL DEFAULT 0, cv_out TEXT DEFAULT '', cv_err TEXT DEFAULT '', cv_ratio REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_files_folder ON files(folder);
CREATE INDEX IF NOT EXISTS ix_files_th ON files(th_state, missing);
CREATE INDEX IF NOT EXISTS ix_files_cv ON files(cv_state);
CREATE INDEX IF NOT EXISTS ix_files_probed ON files(probed, missing);
CREATE TABLE IF NOT EXISTS cuts(id INTEGER PRIMARY KEY AUTOINCREMENT, file_id INTEGER, a REAL, b REAL, out TEXT, mode TEXT, state INTEGER DEFAULT 0, err TEXT DEFAULT '', t REAL);
CREATE TABLE IF NOT EXISTS oplog(id INTEGER PRIMARY KEY AUTOINCREMENT, t REAL, kind TEXT, fid INTEGER, name TEXT, src TEXT, dst TEXT, size INTEGER DEFAULT 0,
  detail TEXT DEFAULT '', ok INTEGER DEFAULT 1, batch TEXT DEFAULT '', undone REAL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_oplog_t ON oplog(t);
CREATE TABLE IF NOT EXISTS ops(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, src TEXT, dst TEXT, t REAL, ok INTEGER, err TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS people(file_id INTEGER, pid INTEGER, name TEXT DEFAULT '', n INTEGER DEFAULT 0, ts TEXT DEFAULT '', PRIMARY KEY(file_id, pid));
CREATE INDEX IF NOT EXISTS ix_people_pid ON people(pid);
"""
MIGRATE = [('tag', "TEXT DEFAULT ''"), ('bmk', "TEXT DEFAULT ''"), ('still', 'REAL DEFAULT -1'), ('up_t', 'REAL DEFAULT 0'), ('pub_t', 'REAL DEFAULT 0'), ('card_k', 'INTEGER DEFAULT -1'), ('arch', "TEXT DEFAULT ''"), ('last_pos', 'REAL DEFAULT 0'), ('cv_ssim', 'REAL DEFAULT 0'), ('vfp', "TEXT DEFAULT ''"), ('vfp_t', 'REAL DEFAULT 0'), ('grade_t', 'REAL DEFAULT 0'), ('cv_src', "TEXT DEFAULT ''"), ('cv_del', "TEXT DEFAULT ''"), ('cv_osz', 'INTEGER DEFAULT 0'), ('cv_nsz', 'INTEGER DEFAULT 0'), ('cv_t', 'REAL DEFAULT 0'), ('cv_redo', 'INTEGER DEFAULT 0'), ('cv_cq', 'INTEGER DEFAULT 0'), ('cv_how', "TEXT DEFAULT ''"), ('cv_gpu', 'INTEGER DEFAULT 0')]      # V0.1.10 arch＝歸到哪個資料夾（S_無條件保存、工作用…）      # V0.1.09 顏色標籤、卡片縮圖用第幾張（-1＝隨機）
# th_state: 0 未做 1 做中 2 好了 3 失敗 4 沒有畫面　cv_state: 0 無 1 排隊 2 轉檔中 3 完成 4 失敗 5 取消


class Store:
    def __init__(self, path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True); self.lock = threading.RLock()
        self.con = sqlite3.connect(str(self.path), check_same_thread=False, timeout=30)
        self.con.execute('PRAGMA journal_mode=WAL'); self.con.execute('PRAGMA synchronous=NORMAL'); self.con.execute('PRAGMA busy_timeout=30000')
        with self.lock:
            self.con.executescript(SCHEMA); self.con.commit()
            have = {r[1] for r in self.con.execute('PRAGMA table_info(files)').fetchall()}
            for col, decl in MIGRATE:                                           # 舊的資料庫自動補新欄位（不動原本的資料）
                if col not in have: self.con.execute(f'ALTER TABLE files ADD COLUMN {col} {decl}'); self.con.commit()
            if 'up_t' not in have:                                              # V0.3.61 V0.3.54～0.3.55 記在操作紀錄的「已上傳」搬到影片上（只做一次）
                try: self.con.execute("UPDATE files SET up_t=COALESCE((SELECT MAX(t) FROM oplog WHERE kind='upcopy' AND fid=files.id),0)"); self.con.commit()
                except Exception: pass
            try: self.con.execute('CREATE INDEX IF NOT EXISTS ix_files_sz ON files(size)'); self.con.commit()   # V0.3.74 找重複上傳用
            except Exception: pass
            try: self.con.execute('CREATE INDEX IF NOT EXISTS ix_files_gt ON files(grade_t)'); self.con.commit()   # V0.2.48 報表、每日目標查得快
            except Exception: pass
        self.con.row_factory = sqlite3.Row

    # ---- V0.5.92 畫面（主執行緒）絕對不等資料庫：背景在跑很久的查詢時，主執行緒改用自己的連線（WAL 可以同時讀）
    def _ui(self):
        return threading.current_thread() is threading.main_thread()

    def _mcon(self):
        c = getattr(self, '_ui_con', None)
        if c is None:
            c = sqlite3.connect(str(self.path), check_same_thread=False, timeout=2)
            c.execute('PRAGMA busy_timeout=2000'); c.row_factory = sqlite3.Row; self._ui_con = c
        return c

    def _bgw(self, sql, a, many=False):
        """主執行緒的寫入擠不進去：交給背景排隊寫（畫面不等）."""
        def w():
            try:
                with self.lock:
                    (self.con.executemany if many else self.con.execute)(sql, a); self.con.commit()
            except Exception:
                try: self.con.rollback()
                except Exception: pass
        threading.Thread(target=w, name='DbLateWrite', daemon=True).start()

    def q(self, sql, a=()):
        if self._ui() and not self.lock.acquire(timeout=0.15):
            self.ui_wait = getattr(self, 'ui_wait', 0) + 1; return self._mcon().execute(sql, a).fetchall()
        elif self._ui():
            try: return self.con.execute(sql, a).fetchall()
            finally: self.lock.release()
        with self.lock: return self.con.execute(sql, a).fetchall()

    def one(self, sql, a=()):
        if self._ui() and not self.lock.acquire(timeout=0.15):
            self.ui_wait = getattr(self, 'ui_wait', 0) + 1; return self._mcon().execute(sql, a).fetchone()
        elif self._ui():
            try: return self.con.execute(sql, a).fetchone()
            finally: self.lock.release()
        with self.lock: return self.con.execute(sql, a).fetchone()

    def _uiw(self, sql, a, many):
        """主執行緒寫：鎖拿得到就照舊；拿不到用自己的連線寫（最多等 2 秒），再不行就交給背景."""
        if self.lock.acquire(timeout=0.15):
            try:
                c = (self.con.executemany if many else self.con.execute)(sql, a); self.con.commit(); return c.rowcount
            except Exception:
                try: self.con.rollback()
                except Exception: pass
                raise
            finally: self.lock.release()
        self.ui_wait = getattr(self, 'ui_wait', 0) + 1; m = self._mcon()
        try:
            c = (m.executemany if many else m.execute)(sql, a); m.commit(); return c.rowcount
        except sqlite3.OperationalError:
            try: m.rollback()
            except Exception: pass
            self._bgw(sql, a, many); return 0

    def x(self, sql, a=()):
        if self._ui(): return self._uiw(sql, a, False)
        with self.lock:
            try:
                c = self.con.execute(sql, a); self.con.commit(); return c.rowcount
            except Exception:
                try: self.con.rollback()
                except Exception: pass
                raise

    def xm(self, sql, seq):
        if self._ui(): self._uiw(sql, list(seq), True); return
        with self.lock:
            try:
                self.con.executemany(sql, seq); self.con.commit()
            except Exception:
                try: self.con.rollback()
                except Exception: pass
                raise

    def close(self):
        with self.lock:
            try: self.con.close()
            except Exception: pass


# ---------------------------------------------------------------- 外部程式
def _mf_active():
    """V0.6.08 🛟 主程式優先中？（看 sys 上的狀態，不用 import，熱更新也一樣）."""
    try: return float(getattr(sys, '_vs_mf', {}).get('until') or 0) > time.time()
    except Exception: return False


def _mf_view():
    try:
        import vs_mainfirst; return vs_mainfirst.view()
    except Exception: return None


def run(cmd, timeout=60, prio='normal'):
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=NO_WINDOW | PRIO.get(prio, 0), stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout.decode('utf-8', 'replace'), p.stderr.decode('utf-8', 'replace')
    except subprocess.TimeoutExpired: return -9, '', '逾時'
    except Exception as ex: return -1, '', f'{type(ex).__name__}: {ex}'


def find_exe(root, name):
    exe = name + ('.exe' if IS_WIN else '')
    for c in (Path(root) / exe, Path(root) / 'ffmpeg' / exe, Path(root) / 'ffmpeg' / 'bin' / exe):
        if c.is_file(): return str(c)
    return shutil.which(name) or ''


def _fps(s):
    try:
        a, b = str(s).split('/'); return round(float(a) / float(b), 3) if float(b) else 0.0
    except Exception:
        try: return float(s)
        except Exception: return 0.0


def probe(ffprobe, path):
    rc, out, err = run([ffprobe, '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', str(path)], timeout=60, prio='idle')
    if rc != 0 or not out.strip(): return {'ok': False, 'err': (err or f'ffprobe {rc}').strip()[-300:]}
    try: j = json.loads(out)
    except Exception as ex: return {'ok': False, 'err': f'json {ex}'}
    S = j.get('streams') or []; F = j.get('format') or {}
    v = next((s for s in S if s.get('codec_type') == 'video' and not (s.get('disposition') or {}).get('attached_pic')), None)
    A = [str(s.get('codec_name') or '') for s in S if s.get('codec_type') == 'audio']
    try: dur = float(F.get('duration') or 0)
    except Exception: dur = 0.0
    if not dur and v is not None:
        try: dur = float(v.get('duration') or 0)
        except Exception: dur = 0.0
    r = {'ok': True, 'dur': dur, 'has_v': 1 if v is not None else 0, 'acodecs': ','.join(A), 'w': 0, 'h': 0, 'vcodec': '', 'fps': 0.0, 'pix': '', 'field': '', 'vbr': 0}
    if v is not None:
        w = int(v.get('width') or 0); h = int(v.get('height') or 0)
        try:
            sar = str(v.get('sample_aspect_ratio') or '1:1'); a, b = sar.split(':'); a, b = float(a), float(b)
            if a > 0 and b > 0 and abs(a / b - 1) > 0.01: w = int(round(w * a / b / 2) * 2)
        except Exception: pass
        rot = 0
        try:
            rot = int(float((v.get('tags') or {}).get('rotate') or 0))
            for sd in v.get('side_data_list') or []:
                if 'rotation' in sd: rot = int(float(sd['rotation']))
        except Exception: pass
        if abs(rot) % 180 == 90: w, h = h, w
        try: vbr = int(v.get('bit_rate') or F.get('bit_rate') or 0)
        except Exception: vbr = 0
        r.update(w=w, h=h, vcodec=str(v.get('codec_name') or ''), fps=_fps(v.get('avg_frame_rate') or v.get('r_frame_rate')), pix=str(v.get('pix_fmt') or ''),
                 field=str(v.get('field_order') or ''), vbr=vbr)
    return r


def proc_io(pid):
    """程序到現在讀了／寫了多少 bytes（Windows）；讀不到回傳 None."""
    if not IS_WIN or not pid: return None
    try:
        import ctypes
        class IOC(ctypes.Structure):
            _fields_ = [(k, ctypes.c_ulonglong) for k in ('ro', 'wo', 'oo', 'rb', 'wb', 'ob')]
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not h: return None
        try:
            c = IOC()
            if ctypes.windll.kernel32.GetProcessIoCounters(h, ctypes.byref(c)): return (int(c.rb), int(c.wb))
        finally: ctypes.windll.kernel32.CloseHandle(h)
    except Exception: pass
    return None


class Proc:
    """FFmpeg with -progress pipe:1：讀進度、可以停；超過 stall 秒沒有任何輸出就當卡住."""
    def __init__(self, cmd, prio='normal'):
        self.cmd = cmd; self.prio = prio; self.p = None; self.out_us = 0; self.speed = ''; self.err = deque(maxlen=60); self.t_last = time.time(); self.killed = False

    def start(self):
        self.p = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW | PRIO.get(self.prio, 0))
        threading.Thread(target=self._rd_err, daemon=True).start()
        threading.Thread(target=self._rd_out, daemon=True).start()
        return self

    def _rd_out(self):
        try:
            for ln in iter(self.p.stdout.readline, b''):
                s = ln.decode('utf-8', 'replace').strip(); self.t_last = time.time()
                if s.startswith('out_time_us=') or s.startswith('out_time_ms='):
                    try: self.out_us = max(self.out_us, int(s.split('=', 1)[1]))
                    except Exception: pass
                elif s.startswith('speed='): self.speed = s.split('=', 1)[1]
        except Exception: pass

    def _rd_err(self):
        try:
            for ln in iter(self.p.stderr.readline, b''):
                s = ln.decode('utf-8', 'replace').rstrip()
                if s: self.err.append(s); self.t_last = time.time()
        except Exception: pass

    def kill(self):
        self.killed = True
        try:
            if self.p and self.p.poll() is None: self.p.kill()
        except Exception: pass

    def wait(self, stop=None, stall=300, on_tick=None):
        while True:
            try:
                rc = self.p.wait(timeout=0.5); time.sleep(0.2); return rc
            except subprocess.TimeoutExpired: pass
            if on_tick:
                try: on_tick(self)
                except Exception: pass
            if stop is not None and stop(): self.kill(); return -2
            if time.time() - self.t_last > stall: self.err.append(f'{stall} 秒沒有任何進度，停掉'); self.kill(); return -3

    def errtext(self, n=8): return '\n'.join(list(self.err)[-n:])


def free_bytes(path):
    """這個路徑所在的硬碟還剩多少（找得到的最近一層）；讀不到回傳 None."""
    p = Path(path)
    for _ in range(40):
        try:
            if p.exists(): return shutil.disk_usage(str(p)).free
        except Exception: return None
        if p.parent == p: break
        p = p.parent
    return None


def need_space(path, need, margin=1e9):
    """空間夠不夠：不夠就丟 RuntimeError（說清楚差多少）。讀不到剩多少就當作夠（不擋）."""
    fb = free_bytes(path)
    if fb is not None and fb < need + margin:
        raise RuntimeError(f'空間不夠：{Path(path).anchor or path} 只剩 {fmt_b(fb)}，這次大約要 {fmt_b(need)}（另外留 {fmt_b(margin)} 給系統），先清出空間再試')


def cmd_text(cmd):
    """LOG 用：FFmpeg 指令（可以直接貼到命令列重跑）."""
    return ' '.join(('"' + str(c) + '"') if (' ' in str(c) or not str(c)) else str(c) for c in cmd)


def unique_path(p):
    p = Path(p)
    if not p.exists(): return p
    for i in range(2, 9999):
        q = p.with_name(f'{p.stem} ({i}){p.suffix}')
        if not q.exists(): return q
    return p.with_name(f'{p.stem}_{int(time.time())}{p.suffix}')


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|\r\n\t]+', '_', str(s)).strip(' .') or 'video'


# ---------------------------------------------------------------- 初剪檔名：亂碼的檔名先試著解碼，解不出來只取前 10 碼
_HEX = re.compile(r'^[0-9a-fA-F]+$'); _B64 = re.compile(r'^[A-Za-z0-9+/_\-]+={0,2}$'); _B32 = re.compile(r'^[A-Z2-7]+=*$')


def _is_cjk(c):
    o = ord(c); return 0x3040 <= o <= 0x30ff or 0x3400 <= o <= 0x9fff or 0xac00 <= o <= 0xd7af or 0xf900 <= o <= 0xfaff or 0xff00 <= o <= 0xffef


def _garbled_token(stem):
    """檔名裡最長、像亂碼的那一段（16 碼以上的數字／英文／編碼字元），沒有就回傳 ''.
    正常的名字不算：IMG_20231010_123456（每段都短）、video2023final1080p（英文是字、數字一段一段）、MyHolidayVideo（有母音）."""
    if not stem or not stem.isascii() or ' ' in stem.strip(): return ''
    toks = [t for t in re.split(r'[_\-.\s]+', stem) if t]
    whole = stem if re.fullmatch(r'[A-Za-z0-9+/=%]{16,}', stem) else ''
    cand = [t for t in toks if len(t) >= 16 and re.fullmatch(r'[A-Za-z0-9+/=%]+', t)]
    for t in ([whole] if whole else []) + sorted(cand, key=len, reverse=True):
        c = t.rstrip('=')
        if c.isdigit() or '%' in t or '+' in c or '/' in c: return t
        if _HEX.match(c) and any(ch.isdigit() for ch in c) and any(ch.isalpha() for ch in c): return t
        letters = ''.join(ch for ch in c if ch.isalpha()); vow = sum(1 for ch in letters.lower() if ch in 'aeiou') / max(1, len(letters))
        alt = sum(1 for x, y in zip(c, c[1:]) if x.isdigit() != y.isdigit())
        if letters and vow < 0.22: return t                                     # 幾乎沒有母音＝不是字
        if alt >= 6: return t                                                   # 英文數字亂跳
    return ''


def looks_garbled(stem): return bool(_garbled_token(stem))


def _readable(s):
    if not s or len(s.strip()) < 2 or '\ufffd' in s: return False
    if any(ord(c) < 32 or 0x7f <= ord(c) < 0xa0 for c in s): return False
    n = len(s); cjk = sum(1 for c in s if _is_cjk(c))
    if cjk and cjk >= n * 0.3: return True
    ok = sum(1 for c in s if c.isalnum() or c in ' _-.,()[]&\'!+#@~') ; letters = sum(1 for c in s if c.isalpha())
    return ok / n >= 0.9 and letters >= 2 and not looks_garbled(s)


def _decodes(t):
    """[(方式, 解出來的字)]：URL 編碼、16 進位、Base64、Base32（都要是 UTF-8 才算）."""
    out = []
    def add(kind, fn):
        try:
            v = fn()
            if isinstance(v, bytes): v = v.decode('utf-8')
            if v and v != t: out.append((kind, v))
        except Exception: pass
    if '%' in t: add('URL', lambda: urllib.parse.unquote(t, errors='strict'))
    if len(t) % 2 == 0 and _HEX.match(t): add('16進位', lambda: bytes.fromhex(t))
    if _B64.match(t) and len(t.rstrip('=')) >= 4:
        u = t.rstrip('='); pad = u + '=' * (-len(u) % 4)
        add('Base64', lambda: base64.b64decode(pad, validate=True)) if re.fullmatch(r'[A-Za-z0-9+/]+=*', pad) else None
        add('Base64', lambda: base64.urlsafe_b64decode(pad)) if re.fullmatch(r'[A-Za-z0-9_\-]+=*', pad) else None
    if _B32.match(t) and len(t.rstrip('=')) >= 8:
        u = t.rstrip('='); add('Base32', lambda: base64.b32decode(u + '=' * (-len(u) % 8)))
    return out


def decode_name(t, depth=0):
    """解得出來（解完是看得懂的字）就回傳 (字, 方式)，不然 (None, '')。最多連解 3 層（例如 Base64 裡面又是 URL 編碼）."""
    for kind, v in _decodes(t):
        v2 = v.strip()
        if _readable(v2): return v2, kind
        if depth < 2 and looks_garbled(v2):
            w, k2 = decode_name(_garbled_token(v2) if _garbled_token(v2) != v2 else v2, depth + 1)
            if w: return w, kind + '→' + k2
    return None, ''


def cut_base_name(stem):
    """初剪檔名的主體：正常的檔名照用；亂碼檔名能解碼就用解出來的，解不出來只取前 10 碼."""
    stem = str(stem).strip()
    if not looks_garbled(stem): return safe_name(stem)[:100], ''
    tok = _garbled_token(stem)
    for t in ([stem, tok] if tok != stem else [stem]):
        w, kind = decode_name(t)
        if w:
            w = os.path.splitext(w)[0] if os.path.splitext(w)[1].lower() in VIDEO_EXT else w
            return safe_name(w)[:80], kind
    return safe_name(stem[:10]), '前10碼'


def show_properties(path):
    """Windows 的「內容」視窗（跟在檔案總管按右鍵 → 內容一樣）."""
    if not IS_WIN: return False
    try:
        import ctypes
        from ctypes import wintypes

        class SEI(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('fMask', ctypes.c_ulong), ('hwnd', wintypes.HWND), ('lpVerb', wintypes.LPCWSTR), ('lpFile', wintypes.LPCWSTR),
                        ('lpParameters', wintypes.LPCWSTR), ('lpDirectory', wintypes.LPCWSTR), ('nShow', ctypes.c_int), ('hInstApp', wintypes.HINSTANCE),
                        ('lpIDList', ctypes.c_void_p), ('lpClass', wintypes.LPCWSTR), ('hkeyClass', wintypes.HKEY), ('dwHotKey', wintypes.DWORD),
                        ('hIcon', wintypes.HANDLE), ('hProcess', wintypes.HANDLE)]
        e = SEI(); e.cbSize = ctypes.sizeof(e); e.fMask = 0x0000000C; e.lpVerb = 'properties'; e.lpFile = str(Path(path)); e.nShow = 1
        return bool(ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(e)))
    except Exception: return False


def explorer_select(path):
    """Windows 檔案總管打開所在資料夾，並選取（定位）這個檔."""
    if IS_WIN: subprocess.Popen(f'explorer.exe /select,"{os.path.normpath(str(path))}"', creationflags=NO_WINDOW)
    else: subprocess.Popen(['xdg-open', str(Path(path).parent)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_default(path):
    if IS_WIN: os.startfile(str(path))
    else: subprocess.Popen(['xdg-open', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_with(path):
    if IS_WIN: subprocess.Popen(['rundll32.exe', 'shell32.dll,OpenAs_RunDLL', os.path.normpath(str(path))], creationflags=NO_WINDOW)


def is_drive_root(d):
    try:
        p = Path(d); return str(p) == p.anchor or str(p).rstrip('\\/') + os.sep == p.anchor or p.parent == p
    except Exception: return False


def keep_awake(on):
    """V0.4.03 ☕ 背景還有事在做時不讓 Windows 自動睡著（螢幕可以關；做完就恢復平常的睡眠設定）。要在同一個執行緒呼叫."""
    if not IS_WIN: return False
    try:
        import ctypes
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | (0x00000001 if on else 0)))
    except Exception: return False


def send_to_recycle(path):
    """Windows：丟到資源回收筒（可以救回來）."""
    if not IS_WIN: return False
    try:
        import ctypes
        from ctypes import wintypes

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [('hwnd', wintypes.HWND), ('wFunc', wintypes.UINT), ('pFrom', wintypes.LPCWSTR), ('pTo', wintypes.LPCWSTR),
                        ('fFlags', ctypes.c_uint16), ('fAnyOperationsAborted', wintypes.BOOL), ('hNameMappings', ctypes.c_void_p), ('lpszProgressTitle', wintypes.LPCWSTR)]
        op = SHFILEOPSTRUCTW(None, 3, str(Path(path).resolve()) + '\0\0', None, 0x0040 | 0x0010 | 0x0004 | 0x0400, False, None, None)
        return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0 and not Path(path).exists()
    except Exception: return False


# ---------------------------------------------------------------- 效能（不用 psutil）
class Perf:
    def __init__(self, log):
        self.log = log; self.cpu = 0.0; self.ram = 0.0; self.ram_used = 0; self.ram_total = 0; self.gpu = None; self.H = {k: deque(maxlen=180) for k in ('cpu', 'ram', 'gpu', 'enc', 'dec', 'vram')}
        self._ct = None; self.cpu_old = None; self.cpu_src = 'GetSystemTimes'; self._pdh = None; self.stop = False; self.smi = shutil.which('nvidia-smi') or (r'C:\Windows\System32\nvidia-smi.exe' if IS_WIN and Path(r'C:\Windows\System32\nvidia-smi.exe').exists() else '')
        threading.Thread(target=self._loop, name='VsPerf', daemon=True).start()

    def _pdh_cpu(self):
        """V0.6.09 跟工作管理員一樣的算法：\\Processor Information(_Total)\\% Processor Utility（Win8 以後的工作管理員用這個）。
        舊算法 GetSystemTimes 在有些電腦（例如裝了 VMware／Hyper-V、或開了核心隔離）會多算很多，CPU 明明很閒卻顯示 90～100%."""
        if not IS_WIN: return None
        import ctypes
        from ctypes import wintypes as W
        if self._pdh is None:
            self._pdh = False
            try:
                P = ctypes.WinDLL('pdh')
                P.PdhOpenQueryW.argtypes = [W.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
                P.PdhAddEnglishCounterW.argtypes = [ctypes.c_void_p, W.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
                P.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
                class FMT(ctypes.Structure): _fields_ = [('CStatus', W.DWORD), ('pad', W.DWORD), ('doubleValue', ctypes.c_double)]
                P.PdhGetFormattedCounterValue.argtypes = [ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD), ctypes.POINTER(FMT)]
                q = ctypes.c_void_p()
                if P.PdhOpenQueryW(None, 0, ctypes.byref(q)) == 0:
                    for path, src in (('\\Processor Information(_Total)\\% Processor Utility', '工作管理員算法'), ('\\Processor(_Total)\\% Processor Time', 'PDH Processor Time')):
                        h = ctypes.c_void_p()
                        if P.PdhAddEnglishCounterW(q, path, 0, ctypes.byref(h)) == 0:
                            P.PdhCollectQueryData(q); self._pdh = (P, q, h, FMT); self.cpu_src = src; break
            except Exception: self._pdh = False
        if not self._pdh: return None
        P, q, h, FMT = self._pdh; v = FMT()
        if P.PdhCollectQueryData(q) != 0: return None
        if P.PdhGetFormattedCounterValue(h, 0x00000200 | 0x00001000, None, ctypes.byref(v)) != 0 or v.CStatus not in (0, 1): return None   # PDH_FMT_DOUBLE | PDH_FMT_NOCAP100
        return max(0.0, min(100.0, float(v.doubleValue)))

    def _cpu_times(self):
        if IS_WIN:
            import ctypes
            from ctypes import wintypes
            i, k, u = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
            ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
            f = lambda x: (x.dwHighDateTime << 32) | x.dwLowDateTime
            return f(i), f(k) + f(u)
        with open('/proc/stat') as fh: v = [int(x) for x in fh.readline().split()[1:]]
        return v[3] + v[4], sum(v)

    def _ram(self):
        if IS_WIN:
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                            ('a', ctypes.c_ulonglong), ('b', ctypes.c_ulonglong), ('c', ctypes.c_ulonglong), ('d', ctypes.c_ulonglong), ('e', ctypes.c_ulonglong)]
            m = MS(); m.dwLength = ctypes.sizeof(MS); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys - m.ullAvailPhys, m.ullTotalPhys
        d = {}
        with open('/proc/meminfo') as fh:
            for ln in fh:
                k, v = ln.split(':', 1); d[k] = int(v.split()[0]) * 1024
        return d['MemTotal'] - d.get('MemAvailable', 0), d['MemTotal']

    def _loop(self):
        k = 0
        while not self.stop:
            try:
                idle, tot = self._cpu_times()
                if self._ct:
                    di, dt = idle - self._ct[0], tot - self._ct[1]
                    self.cpu_old = max(0.0, min(100.0, 100.0 * (1 - di / dt))) if dt > 0 else 0.0
                self._ct = (idle, tot)
                try: pc = self._pdh_cpu()
                except Exception: pc = None
                if pc is not None: self.cpu = pc                                # V0.6.09 跟工作管理員一樣
                elif self.cpu_old is not None: self.cpu = self.cpu_old; self.cpu_src = 'GetSystemTimes'
                self.ram_used, self.ram_total = self._ram(); self.ram = 100.0 * self.ram_used / self.ram_total if self.ram_total else 0
            except Exception: pass
            if self.smi and k % 2 == 0:
                rc, out, _e = run([self.smi, '--query-gpu=name,utilization.gpu,utilization.encoder,utilization.decoder,memory.used,memory.total,temperature.gpu,driver_version',
                                   '--format=csv,noheader,nounits'], timeout=8)
                if rc == 0 and out.strip():
                    try:
                        p = [x.strip() for x in out.strip().splitlines()[0].split(',')]
                        self.gpu = {'name': p[0], 'util': float(p[1]), 'enc': float(p[2]), 'dec': float(p[3]), 'mem': float(p[4]), 'mem_t': float(p[5]), 'temp': float(p[6]), 'drv': p[7]}
                    except Exception: self.gpu = None
                else: self.gpu = None
            g = self.gpu or {}
            self.H['cpu'].append(self.cpu); self.H['ram'].append(self.ram); self.H['gpu'].append(g.get('util')); self.H['enc'].append(g.get('enc')); self.H['dec'].append(g.get('dec'))
            self.H['vram'].append(100.0 * g['mem'] / g['mem_t'] if g.get('mem_t') else None)
            k += 1; time.sleep(1.0)


# ---------------------------------------------------------------- 引擎
def _keep(adopt, k, make):
    """熱更新接手：舊的有就共用同一個（空的也共用，不能用 or）."""
    v = getattr(adopt, k, None) if adopt is not None else None
    return v if v is not None else make()


EXT_MOVED = {'fn': None}                                                     # V0.5.38 SortCut 搬了檔（待刪、歸檔）→ 通知整理（FileCompare）


class Engine:
    """adopt＝熱更新：接手舊版引擎（同一份排隊、進行中的工作、工作清單）。舊引擎 retire() 之後不再接新工作，手上那部做完就停.
    start=False：先建好、還不開始跑（熱更新時新視窗也建好了才 start，失敗的話新引擎根本沒動過）."""
    PREV_GC_TICK, PREV_GC_WAIT = 15, 120                                       # 熱更新後多久檢查／至少等多久才放掉舊引擎

    def __init__(self, root, adopt=None, start=True, version=''):
        self.root = Path(root); self.data = self.root / 'Data'; self.data.mkdir(parents=True, exist_ok=True); self.version = version
        self.log = Log(self.root / 'LOG'); self.cfg = Settings(self.data / 'settings.json'); self.cfg.log = self.log
        if not self.cfg.get('cv_v2'):                                         # V0.1.53：轉好之後原檔預設搬到 X:\DELETE\（原本預設「留著不動」的換掉；自己選過搬去備份／回收筒的不動）
            if (self.cfg.get('cv_after') or 'keep') == 'keep': self.cfg.set('cv_after', 'delete_dir')
            self.cfg.set('cv_v2', True)
        if not self.cfg.get('drag_v2'):                                       # V0.1.51：拖曳改成「快＝遠、慢＝細」，舊的預設 3 分鐘換成 10 分鐘（自己改過的不動）
            if int(self.cfg.get('drag_max') or 180) == 180: self.cfg.set('drag_max', 600)
            self.cfg.set('drag_v2', True)
        if (self.cfg.get('cv_after') or '') == 'keep': self.cfg.set('cv_after', 'delete_dir')   # V0.1.57 不再有「原檔留在原位」
        if not self.cfg.get('cv_cap_t'): self.cfg.set('cv_cap_t', time.time())     # V0.1.57：從這時候開始轉檔有位元率上限（之前轉的不算進「同類平均」）
        self.db_health = _keep(adopt, 'db_health', lambda: {'ok': None, 'msg': '', 't': 0})
        if adopt is None: self._pending_restore()                               # 上次在設定頁按了「從備份還原」：開資料庫之前先換好
        if adopt is None: self._pack_boot()                                     # V0.2.26 新電腦：設定從硬碟上的 SortCut 資料拿回來
        try: self.db = Store(self.data / 'videosift.sqlite3')
        except Exception as ex:                                                 # 資料庫壞到打不開：不要整個程式開不起來
            if adopt is not None: raise
            self.log.err('打開資料庫'); self.db = self._recover_db(ex)
        if adopt is None:                                                       # V0.2.27 開程式一瞬間：每顆硬碟在不在、是不是另一台電腦用過（沒接的不顯示）
            try: self._pack_startup()
            except Exception: self.log.err('💽 開程式檢查硬碟')
        self.ff = find_exe(self.root, 'ffmpeg'); self.ffprobe = find_exe(self.root, 'ffprobe')
        try:
            if self.cfg.get('faces_on'):                                         # V0.5.00 👤 人物拿掉了（預設不載入；設定 faces_on=true 才回來）
                import vs_face                                                  # V0.1.51 👤 人物（背景程式用另外的 Python 跑）
                self.faces = vs_face.FaceManager(self, adopt=getattr(adopt, 'faces', None))
            else:
                self.faces = None; F_ = getattr(adopt, 'faces', None)
                if F_ is not None:
                    try:
                        if F_.running(): F_.stop('👤 人物功能拿掉了')
                    except Exception: pass
        except Exception: self.faces = None; self.log.err('👤 人物模組載入')
        self._mv_lock = _keep(adopt, '_mv_lock', threading.Lock); self._mv_st = _keep(adopt, '_mv_st', lambda: {'run': False, 'phase': '', 'cur': '', 'speed_now': 0.0, 'total_b': 0, 'total_n': 0})
        self.lane_hold = _keep(adopt, 'lane_hold', dict)                        # V0.1.55 硬碟協調員：{道: (到什麼時候, 為什麼)} 這段時間不開新工作
        try:
            import vs_hotzone                                                   # V0.1.55 🔥 HotZone（背景引擎用另外的 Python 跑）
            self.hz = vs_hotzone.HotZoneManager(self, adopt=getattr(adopt, 'hz', None))
        except Exception: self.hz = None; self.log.err('🔥 HotZone 模組載入')
        try:
            import vs_usb                                                       # V0.1.91 🔌 USB 硬碟斷線自動救回
            self.usb = vs_usb.UsbGuard(self, adopt=getattr(adopt, 'usb', None))
        except Exception: self.usb = None; self.log.err('🔌 USB 硬碟自動救回 模組載入')
        gp = self.root / 'ffmpeg_gpu' / ('ffmpeg.exe' if IS_WIN else 'ffmpeg'); self.ff_gpu = str(gp) if gp.is_file() else ''
        self.stop_all = False; self.retired = False; self.started = False; self.prev = adopt; self.perf = Perf(self.log)
        self.pr_active = 0; self.info_c = {'t': 0, 'v': {}}; self._cut_cur = None; self._op_cur = None; self.pr_lanes = {}; self.lane_note = {}; self._root_lane = {}
        self._cpause = bool(getattr(adopt, '_cpause', False)) if adopt is not None else False   # V0.2.88 新功能的狀態熱更新後接著用
        for k_ in ('_as', '_ed', '_gg_c', '_gg_f', '_ps_c'):
            if adopt is not None and getattr(adopt, k_, None) is not None: setattr(self, k_, getattr(adopt, k_))
        self.offline = _keep(adopt, 'offline', dict); self._off_chk = {}                # 硬碟離線（拔掉、睡著）：{影片庫: 從什麼時候}；離線的不開新工作、失敗的也不算壞掉
        self.cut_hist = _keep(adopt, 'cut_hist', lambda: deque(maxlen=300)); self.th_precise = _keep(adopt, 'th_precise', set)
        self.th_done_log = _keep(adopt, 'th_done_log', lambda: deque(maxlen=2000))
        self.brt_st = _keep(adopt, 'brt_st', lambda: None); self._ssim_sem = _keep(adopt, '_ssim_sem', lambda: threading.Semaphore(2))   # V0.1.62 碼率測試：熱更新後還看得到；畫質抽查最多同時 2 個
        self.pr_done_log = _keep(adopt, 'pr_done_log', lambda: deque(maxlen=4000)); self.cv_done_log = _keep(adopt, 'cv_done_log', lambda: deque(maxlen=500))   # V0.1.53 後台總覽的處理速度      # (完成時間, 影片秒數)：估「還要多久」
        self.drives = getattr(adopt, 'drives', None) or vs_disk.Drives(); self.dcount = getattr(adopt, 'dcount', None) or vs_disk.DiskCounters()
        # V0.1.65 後台總控制：每一項的暫停（存在設定裡，重開還在）、電腦太忙時自動讓路、慢慢加速
        self.bg_pause = {k: True for k, v in dict(self.cfg.get('bg_pause') or {}).items() if v}
        self.bg_auto = _keep(adopt, 'bg_auto', lambda: {}); self.bg_slow = _keep(adopt, 'bg_slow', lambda: {}); self.bg_ramp = _keep(adopt, 'bg_ramp', lambda: {}); self.bg_last = dict(self.cfg.get('bg_last') or {})
        self.bg_gov = _keep(adopt, 'bg_gov', lambda: {'hi_t': 0.0, 'lo_t': 0.0, 'note': '', 'log': deque(maxlen=200)})
        self.rv_st = _keep(adopt, 'rv_st', lambda: {'run': False, 'q': deque(), 'n': 0, 'done': 0, 'cur': '', 'stop': False, 'up': 0, 'res': deque(maxlen=500)})
        self._seekc = _keep(adopt, '_seekc', lambda: {}); self._seekl = _keep(adopt, '_seekl', lambda: threading.Lock())
        self._cvop_lock = _keep(adopt, '_cvop_lock', lambda: threading.RLock())   # V0.1.88 還原／搬原檔／刪原檔：電腦和手機同時按不會撞在一起
        self._learn_lock = _keep(adopt, '_learn_lock', lambda: threading.Lock()); self._learn = _keep(adopt, '_learn', self._learn_load)
        if adopt is None:
            self.lock = threading.RLock(); self.tasks = OrderedDict(); self._tid = 0
            self.scan_st = {'running': False, 'n': 0, 'dirs': 0, 'cur': '', 't0': 0, 't1': 0, 'new': 0}
            self.th_active = {}; self.th_focus = ''; self.th_front = deque()
            self.cv_active = {}; self.gpu_st = {'checked': False, 'ok': False, 'ff': '', 'preset': 'p5', 'aq': True, 'diag': '', 't': 0}
            self.cut_q = deque(); self.op_q = deque(); self.procs = set()
        else:                                                                   # 同一個物件，舊的做完手上的會自己從裡面拿掉
            g = lambda k, d: getattr(adopt, k, d)
            self.lock = g('lock', threading.RLock()); self.tasks = g('tasks', OrderedDict()); self._tid = g('_tid', 0) + 1000
            self.scan_st = g('scan_st', {'running': False, 'n': 0, 'dirs': 0, 'cur': '', 't0': 0, 't1': 0, 'new': 0})
            self.th_active = g('th_active', {})
            if g('th_paused', False): self.bg_pause['thumb'] = True
            self.th_focus = g('th_focus', ''); self.th_front = g('th_front', deque())
            self.cv_active = g('cv_active', {})
            if g('cv_paused', False): self.bg_pause['conv'] = True
            self.gpu_st = g('gpu_st', None) or {'checked': False, 'ok': False, 'ff': '', 'preset': 'p5', 'aq': True, 'diag': '', 't': 0}
            self.cut_q = g('cut_q', deque()); self.op_q = g('op_q', deque()); self.procs = g('procs', set())
        if start: self.start()

    cut_cur = property(lambda self: self._cut_cur or (getattr(self.prev, 'cut_cur', None) if self.prev is not None else None),
                       lambda self, v: setattr(self, '_cut_cur', v))
    op_cur = property(lambda self: self._op_cur or (getattr(self.prev, 'op_cur', None) if self.prev is not None else None),
                      lambda self, v: setattr(self, '_op_cur', v))

    # ================================================================ V0.1.65 後台總控制
    BG_KINDS = [('conv', '🔁', '轉檔'), ('thumb', '🖼', '預覽圖'), ('probe', '🔍', '讀影片資訊'), ('faces', '👤', '人臉辨識'), ('cut', '✂', '初剪'), ('op', '📦', '搬檔'), ('hotzone', '🔥', 'HotZone 熱區／圖片分析'), ('pack', '💽', '資料存到各硬碟'), ('move', '🚚', '搬硬碟')]

    th_paused = property(lambda self: bool(self.bg_pause.get('thumb')), lambda self, v: self.bg_set_pause('thumb', v))
    cv_paused = property(lambda self: bool(self.bg_pause.get('conv')), lambda self, v: self.bg_set_pause('conv', v))

    def bg_prio(self):
        """先後順序（前面的優先；電腦太忙時從最後面的開始讓路）."""
        L = [k for k in (self.cfg.get('bg_prio') or []) if k in dict((x[0], 1) for x in self.BG_KINDS)]
        return L + [k for k, _i, _n in self.BG_KINDS if k not in L]

    def bg_hold(self, kind):
        """這一項現在不要開新的工作：你按了暫停，或電腦太忙自動讓路，或不在你設定的時段（🧪 V0.2.31）."""
        if bool(self.bg_pause.get(kind)) or kind in self.bg_auto or bool(self.bg_sched_hold(kind)): return True
        if _mf_active(): return True                                            # V0.6.08 🛟 主程式優先：畫面／手機卡了，背景先不開新的
        try:
            import vs_yield; return bool(vs_yield.hold(kind))                   # V0.5.71 🤝 TikLive 說「要開始了」又已經 Lv 1：轉檔先不開新的
        except Exception: return False

    SCHED_KINDS = ('conv', 'thumb', 'probe', 'move', 'copy')                     # V0.3.90 📤 複製到上傳也可以排時段

    def proc_seen(self):
        """V0.2.69 現在有在跑的程式名稱（小寫，例如 obs64.exe）：30 秒查一次、在背景查（不會卡住呼叫的人）."""
        c = getattr(self, '_ps_c', None)
        if (not c or time.time() - c[0] > 30) and not getattr(self, '_ps_run', False) and IS_WIN:
            self._ps_run = True
            def work():
                try:
                    p = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, timeout=15, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
                    out = p.stdout.decode('mbcs' if IS_WIN else 'utf-8', 'ignore')
                    self._ps_c = (time.time(), {ln.split('","')[0].strip('"').lower() for ln in out.splitlines() if ln.startswith('"')})
                except Exception: self._ps_c = (time.time(), (c or (0, set()))[1])
                finally: self._ps_run = False
            threading.Thread(target=work, daemon=True, name='tasklist').start()
        return (c or (0, set()))[1]

    def proc_hold(self, kind):
        """V0.2.69 🎥 直播／錄影時讓路：設定的程式（例如 OBS）在跑，就先不開新的這一項（預設只有轉檔）."""
        try:
            L = self.cfg.get('lab') or {}
            if not L.get('proc_guard') or (kind not in (L.get('proc_kinds') or ['conv']) and not (kind == 'copy' and L.get('proc_copy'))): return ''
            want = [x.strip().lower() for x in re.split(r'[,，、\s]+', str(L.get('proc_names') or 'obs64.exe')) if x.strip()]
            run = self.proc_seen(); hit = [x for x in want if x in run or (x + '.exe') in run]
            return f'🎥 {hit[0]} 在跑：先讓路' if hit else ''
        except Exception: return ''

    def bg_sched_hold(self, kind):
        """V0.2.31 🕑 背景工作時段：這一項只在設定的時段做；時段外回傳原因（不做新的，手上的做完）. V0.2.69 也包含 🎥 程式在跑時讓路."""
        ph = self.proc_hold(kind)
        if ph: return ph
        try:
            L = self.cfg.get('lab') or {}
            if not L.get('bg_sched'): return ''
            S = (L.get('sched') or {}).get(kind) or {}
            if not S.get('on'): return ''
            a, b = int(S.get('from', 0)) % 24, int(S.get('to', 0)) % 24; h = time.localtime().tm_hour
            inside = True if a == b else ((a <= h < b) if a < b else (h >= a or h < b))
            return '' if inside else f'🕑 時段外：只在 {a:02d}:00～{b:02d}:00 做'
        except Exception: return ''

    def bg_cap(self, kind, n):
        """慢慢加速：剛開始／剛繼續的時候同時只做 1 個，每過一段時間（預設 20 秒）多 1 個，直到設定的上限."""
        try:                                                                    # V0.5.71 🤝 讓路等級：Lv 10＝照設定，Lv 1＝同時只做 1 個
            import vs_yield; n = vs_yield.cap(kind, n)
        except Exception: pass
        if _mf_active(): return 1                                               # V0.6.08 🛟 主程式優先
        if self.bg_slow.get(kind): n = max(1, min(n, int(self.bg_slow[kind])))     # 電腦太忙、又沒有更優先的可以讓：先降速（同時少做幾個）
        t0 = self.bg_ramp.get(kind)
        if not t0: return n
        sec = max(0, int(self.cfg.get('bg_ramp_sec') if self.cfg.get('bg_ramp_sec') is not None else 20))
        if sec <= 0: return n
        k = 1 + int((time.time() - t0) / sec)
        if k >= n: self.bg_ramp.pop(kind, None); return n
        return max(1, k)

    def bg_running(self, kind):
        try:
            if kind == 'thumb': return len(self.th_active)
            if kind == 'probe': return int(self.pr_active)
            if kind == 'conv': return len(self.cv_active)
            if kind == 'cut': return 1 if self.cut_cur else 0
            if kind == 'op': return 1 if self.op_cur else 0
            if kind == 'pack': return 1 if getattr(self, '_pk_busy', False) else 0
            if kind == 'move': return 1 if (getattr(self, '_mv_st', None) or {}).get('run') else 0
            if kind == 'faces': return 1 if (getattr(self, 'faces', None) is not None and self.faces.running()) else 0
            if kind == 'hotzone':
                H = getattr(self, 'hz', None); return 1 if (H is not None and H.status().get('running')) else 0
        except Exception: return 0
        return 0

    def bg_set_pause(self, kind, on, why='你按的'):
        if not hasattr(self, 'bg_pause'): return
        on = bool(on); was = bool(self.bg_pause.get(kind))
        if on: self.bg_pause[kind] = True
        else: self.bg_pause.pop(kind, None); self.bg_auto.pop(kind, None); self.bg_ramp[kind] = time.time()      # 繼續：慢慢加速
        try: self.cfg.set('bg_pause', dict(self.bg_pause)); self.cfg.set('bg_last', dict(self.bg_last))
        except Exception: pass
        if kind == 'move' and not on and (self.cfg.get('disk_move') or {}).get('state') == 'run':      # V0.2.28 搬硬碟：按繼續（電腦或手機）就接著搬
            try: self._mv_kick()
            except Exception: pass
        if was != on:
            nm = dict((k, n) for k, _i, n in self.BG_KINDS).get(kind, kind)
            self.log.w(f'⏯ 後台：{nm} {"暫停" if on else "繼續（慢慢加速）"}（{why}）' + (f'，停在：{self.bg_last.get(kind)}' if on and self.bg_last.get(kind) else ''))
            try:
                if kind == 'faces' and getattr(self, 'faces', None) is not None:
                    if on and self.faces.running(): self.faces.stop('後台暫停')
                if kind == 'hotzone' and getattr(self, 'hz', None) is not None:
                    for path in ('/api/hot/pause', '/api/images/pause'): self.hz.api(path, {'on': on})
            except Exception: self.log.err('後台暫停')
        return True

    def bg_stop_now(self, kind):
        """立刻停：暫停，正在做的也停掉、放回排隊（下次從頭做那一部）."""
        self.bg_set_pause(kind, True, '立刻停')
        n = 0
        try:
            if kind == 'thumb':
                for J in list(self.th_active.values()):
                    J['cancel'] = True; J['skip'] = False; n += 1
                    if J.get('proc'): J['proc'].kill()
            elif kind == 'conv':
                for J in list(self.cv_active.values()):
                    J['cancel'] = True; J['requeue'] = True; n += 1
                    if J.get('proc'): J['proc'].kill()
            elif kind == 'faces' and getattr(self, 'faces', None) is not None and self.faces.running(): self.faces.stop('後台立刻停'); n = 1
        except Exception: self.log.err('後台立刻停')
        self.log.w(f'⏹ 後台：{kind} 立刻停，{n} 個正在做的放回排隊'); return n

    def bg_all(self, on):
        for k, _i, _n in self.BG_KINDS:
            if k != 'hotzone': self.bg_set_pause(k, on, '全部' + ('暫停' if on else '繼續'))
        if not on:                                                               # 全部繼續：照先後順序，一項一項慢慢加進來（每項晚 10 秒開始）
            now = time.time()
            for i, k in enumerate(self.bg_prio()): self.bg_ramp[k] = now + i * 10
        self.fc_pause_all(on)

    def fc_pause_all(self, on):
        """V0.5.11「全部暫停／全部繼續」連整理（FileCompare）的背景一起（同一台電腦、同一批硬碟，按一次就全部停）."""
        F = sys.modules.get('fc_app'); E = getattr(F, 'ENG', None) if F else None
        if type(E).__name__ != 'Engine': return
        try: E.bg_all(bool(on)); self.log.w('🗂 整理的背景也' + ('全部暫停' if on else '全部繼續'))
        except Exception: self.log.err('🗂 整理：全部暫停／繼續')

    def bg_move(self, kind, d):
        L = self.bg_prio()
        if kind not in L: return L
        i = L.index(kind); j = max(0, min(len(L) - 1, i + int(d)))
        L[i], L[j] = L[j], L[i]; self.cfg.set('bg_prio', L); self.log.w('⏯ 後台：先後順序改成 ' + ' > '.join(L)); return L

    def bg_mark(self, kind, name):
        """記住每一項最近在做哪一部（暫停時顯示「停在哪裡」）."""
        self.bg_last[kind] = str(name or '')[:200]

    def _gov_loop(self):
        """電腦太忙（CPU 一直很高）就從最不重要的開始自動讓路；閒下來再照順序一項一項慢慢放回來."""
        while self.alive():
            try:
                time.sleep(2.0)
                if not (self.cfg.get('cpu_guard') is not False): 
                    if self.bg_auto:
                        for k in list(self.bg_auto): self.bg_auto.pop(k, None); self.bg_ramp[k] = time.time()
                    self.bg_slow.clear()
                    continue
                cpu = float(self.perf.cpu or 0); hi = float(self.cfg.get('cpu_max') or 90); lo = max(10.0, hi - 25); now = time.time(); G = self.bg_gov
                if cpu >= hi:
                    G['lo_t'] = 0.0; G['hi_t'] = G['hi_t'] or now
                    if now - G['hi_t'] >= 12:
                        PR = self.bg_prio()
                        for k in reversed(PR):
                            if k in ('hotzone', 'move') or self.bg_hold(k) or not self.bg_running(k): continue      # 🚚 搬硬碟：電腦忙只放慢（在裡面），不會被停掉
                            if not any(self.bg_running(x) and not self.bg_hold(x) for x in PR[:PR.index(k)] if x != 'hotzone'):   # 前面沒有更優先的在跑：不停，改成降速
                                rn = self.bg_running(k)
                                if rn > 1 and k in ('thumb', 'probe', 'conv'):
                                    self.bg_slow[k] = rn - 1; G['hi_t'] = now
                                    msg = f'⚖ CPU {cpu:.0f}% 持續 12 秒：{dict((a, c) for a, _b, c in self.BG_KINDS).get(k, k)} 降速成同時最多 {rn - 1} 個'
                                    G['log'].append((now, msg)); self.log.w('⏯ 後台：' + msg); break
                                continue
                            self.bg_auto[k] = f'電腦很忙（CPU {cpu:.0f}%），先讓給前面的'; G['hi_t'] = now
                            msg = f'⚖ CPU {cpu:.0f}% 持續 12 秒：{dict((a, c) for a, _b, c in self.BG_KINDS).get(k, k)} 先不開新的（讓給更優先的）'
                            G['log'].append((now, msg)); self.log.w('⏯ 後台：' + msg); break
                        else: G['hi_t'] = now
                elif cpu <= lo:
                    G['hi_t'] = 0.0; G['lo_t'] = G['lo_t'] or now
                    if self.bg_slow and now - G['lo_t'] >= 30 and not self.bg_auto:      # 先把降速的放回來
                        k = next(iter(self.bg_slow)); self.bg_slow.pop(k, None); self.bg_ramp[k] = now; G['lo_t'] = now
                        msg = f'⚖ CPU 降到 {cpu:.0f}%：{dict((a, c) for a, _b, c in self.BG_KINDS).get(k, k)} 不降速了（慢慢加回去）'; G['log'].append((now, msg)); self.log.w('⏯ 後台：' + msg)
                    if self.bg_auto and now - G['lo_t'] >= 30:
                        for k in self.bg_prio():
                            if k in self.bg_auto:
                                self.bg_auto.pop(k, None); self.bg_ramp[k] = now; G['lo_t'] = now
                                msg = f'⚖ CPU 降到 {cpu:.0f}%：{dict((a, c) for a, _b, c in self.BG_KINDS).get(k, k)} 繼續（慢慢加速）'
                                G['log'].append((now, msg)); self.log.w('⏯ 後台：' + msg); break
                else: G['hi_t'] = 0.0; G['lo_t'] = 0.0
            except Exception:
                self.log.err('後台總控制'); time.sleep(5)

    def bg_progress(self):
        """每一項的總進度 %（完成的 ÷ 全部）."""
        q1 = lambda sql: int((self.db.one(sql) or [0])[0] or 0); out = {}
        try:
            d = q1("SELECT COUNT(*) FROM files WHERE th_state=2 AND missing=0"); left = q1("SELECT COUNT(*) FROM files WHERE th_state IN (0,1) AND has_v=1 AND missing=0 AND length(arch)=0")
            out['thumb'] = (d, d + left)
            d = q1("SELECT COUNT(*) FROM files WHERE probed IN (1,3) AND missing=0"); left = q1("SELECT COUNT(*) FROM files WHERE probed IN (0,2) AND missing=0")
            out['probe'] = (d, d + left)
            d = q1("SELECT COUNT(*) FROM files WHERE cv_state IN (3,6)"); left = q1("SELECT COUNT(*) FROM files WHERE cv_state IN (1,2) AND missing=0")
            out['conv'] = (d, d + left)
            d, left = self.pack_left(); out['pack'] = (d, d + left)
            MV = self.move_view()
            if MV.get('on') and MV.get('total_b'): out['move'] = (int(MV['done_b'] or 0) // 1000000, int(MV['total_b']) // 1000000)
        except Exception: pass
        try:
            F = getattr(self, 'faces', None)
            if F is not None: fs = F.status(); out['faces'] = (int(fs.get('done') or 0), int(fs.get('total') or 0))
        except Exception: pass
        return out

    def fc_bg(self):
        """V0.5.10 🗂 整理（FileCompare）的背景工作一行摘要（給 SortCut 的後台頁／手機）：在跑什麼、暫停什麼、在讓誰；不查資料庫."""
        F = sys.modules.get('fc_app'); E = getattr(F, 'ENG', None) if F else None
        if type(E).__name__ != 'Engine': return None
        try:
            nm = {k: (i, n) for k, i, n in E.BG_KINDS}
            run = [f'{nm[k][0]} {nm[k][1]}' for k in nm if E.bg_running(k)]
            S = (getattr(getattr(E, 'slim', None), 'st', None) or {})
            if S.get('run'): run.append(f"🗜 影片瘦身 {S.get('n', 0)}／{S.get('total', 0)}" + ('（⏳ 等 SortCut 轉檔轉完）' if str(S.get('cur') or '').startswith('⏳') else ''))
            pau = [nm[k][1] for k, v in list(E.bg_pause.items()) if v and k in nm]
            auto = [nm[k][1] for k in list(E.bg_auto) if k in nm]
            hold = E.ext_hold('hash') if hasattr(E, 'ext_hold') else ''
            if hold:                                                            # V0.5.46 整理手上真的有還沒做完的（掃描／比對／檢查／16 格…）才算「在等」
                try:                                                            # 只看整理已經算好的快取（畫面執行緒呼叫，不查資料庫、不掃檔案）
                    C = (getattr(E, 'fc_cache', None) or {}).get('v') or None; St = getattr(E, 'fc_stat', None) or {}
                    if C is not None:
                        md = int(C.get('media', 0) or 0)
                        pend = (int(C.get('hash_total', 0) or 0) > int(C.get('hash_done', 0) or 0) or md > int(C.get('health_done', 0) or 0)
                                or md > int(C.get('meta_done', 0) or 0) or int(C.get('rep_q', 0) or 0) > 0)
                        if not pend: hold = ''
                except Exception: pass
            return {'run': run, 'pause': pau, 'auto': auto, 'hold': hold}
        except Exception: return None

    def bg_view(self):
        """給後台頁／手機：每一項的狀態、先後順序、進度、停在哪."""
        P = self.bg_progress(); L = []
        nm = dict((k, (i, n)) for k, i, n in self.BG_KINDS)
        for idx, k in enumerate([k_ for k_ in self.bg_prio() if not (k_ == 'faces' and getattr(self, 'faces', None) is None)]):   # V0.5.10 👤 人物拿掉了：後台不列
            d, tot = P.get(k, (0, 0)); run = self.bg_running(k)
            st = 'pause' if self.bg_pause.get(k) else ('hold' if k in self.bg_auto else ('run' if run else 'idle'))
            sh = self.bg_sched_hold(k)
            if sh and st not in ('pause',): st = 'hold'
            L.append({'k': k, 'icon': nm[k][0], 'name': nm[k][1], 'state': st, 'running': run, 'prio': idx + 1, 'held': self.bg_auto.get(k, '') or sh,
                      'last': self.bg_last.get(k, ''), 'done': d, 'total': tot, 'pct': round(d * 100 / tot, 1) if tot else None,
                      'ramp': (self.bg_cap(k, 99) if self.bg_ramp.get(k) else None), 'slow': self.bg_slow.get(k)})
        G = self.bg_gov
        return {'kinds': L, 'cpu': round(float(self.perf.cpu or 0), 1), 'guard': (self.cfg.get('cpu_guard') is not False), 'cpu_max': int(self.cfg.get('cpu_max') or 90),
                'ramp_sec': int(self.cfg.get('bg_ramp_sec') if self.cfg.get('bg_ramp_sec') is not None else 20), 'mf': _mf_view(),
                'log': [f'{time.strftime("%H:%M:%S", time.localtime(t))} {m}' for t, m in list(G['log'])[-30:]][::-1]}

    def alive(self): return not self.stop_all and not self.retired

    def start(self):
        if self.started: return
        self.started = True; old = self.prev
        try:                                                                    # V0.5.71 🤝 讓路給 TikLive（右上角 Lv 1～10）；熱更新：舊的先停、暫停中的 FFmpeg 放開
            import vs_yield; vs_yield.start(self, self.version)
        except Exception: self.log.err('🤝 讓路給 TikLive')
        try:                                                                    # V0.6.08 🛟 主程式優先（畫面、手機永遠先；卡了背景馬上退）
            import vs_mainfirst; vs_mainfirst.attach(self)
        except Exception: self.log.err('🛟 主程式優先')
        try:                                                                    # V0.5.85 🚚 R 碟清空搬移：上次沒搬完的接著搬
            import vs_rsplit; vs_rsplit.boot(self)
        except Exception: self.log.err('🚚 R 碟清空搬移')
        try:
            if self.hz is not None: self.hz.start_thread()                     # 熱更新：舊的協調員停、新的接手
        except Exception: self.log.err('🔥 HotZone 協調員')
        if old is not None:
            try: old.cfg = self.cfg                                             # 舊的做完手上那部之前，也讀新的設定
            except Exception: pass
            try: old.retire()
            except Exception:
                try: old.retired = True                                         # 太舊的版本沒有 retire()
                except Exception: pass
            try: old.perf.stop = True
            except Exception: pass
        else:
            try: self.db.x('UPDATE files SET th_state=0 WHERE th_state=1'); self.db.x('UPDATE files SET cv_state=1 WHERE cv_state=2')   # 上次關掉時做到一半的：重來
            except Exception: self.log.err('db reset')
        if old is None: self.log_startup(); self.oplog_purge()
        try:                                                                    # V0.1.95 先確認硬碟代號沒換（換了就把資料改過去），再開始掃描、做預覽圖
            rm_ = self.drive_remap()
            if rm_.get('n'): self.remap_msg = rm_['message']
            nd_ = self.dedupe_letters() if (rm_.get('n') or not self.cfg.get('dedupe_v95')) else 0      # 只在換代號後（和這次更新一次）整理，免得把備份碟上同路徑的檔當重複
            self.cfg.set('dedupe_v95', True)
            if nd_ and not rm_.get('n'): self.remap_msg = f'清掉 {nd_:,} 筆換了磁碟代號後重複收進來的資料（檔案沒動）'
            self.remember_vols()
        except Exception: self.log.err('硬碟代號檢查')
        if not self.cfg.get('th_fix_v95'): threading.Thread(target=self._thumb_fix_scan, name='VsThumbFix', daemon=True).start()
        if not self.cfg.get('cv_gpu_v99'): threading.Thread(target=self._cv_gpu_backfill, name='VsGpuBackfill', daemon=True).start()
        if not self.cfg.get('th_fix_v203') and not os.environ.get('VIDEOSIFT_NO_PKSCAN'): threading.Thread(target=self._thumb_pk_scan, name='VsThumbPK', daemon=True).start()
        if not self.cfg.get('auto_next_v207'):                                   # V0.2.07 使用者要求：按 S／A／E／F 直接跳下一部（實驗區那個開關打開；不要可以再關）
            self.cfg.set('lab', dict(self.cfg.get('lab') or {}, auto_next=True)); self.cfg.set('auto_next_v207', True)
        if not self.cfg.get('cv_after_v95'):                                     # V0.1.95 使用者要求：畫質到目標的原檔直接刪，0.975～0.985 留 DELETE 手動確認
            if (self.cfg.get('cv_after') or 'delete_dir') == 'delete_dir': self.cfg.set('cv_after', 'auto_del')
            self.cfg.set('cv_after_v95', True)
        if not self.cfg.get('th_h_v94'):                                        # V0.1.94 預覽圖預設改清楚一點（只影響之後新做的；已經做好的不重做）
            try:
                h0 = int(self.cfg.get('th_h') or 120); self.cfg.set('th_h', {90: 120, 120: 180, 160: 180, 200: 240}.get(h0, h0 if h0 in (120, 180, 240) else 180)); self.cfg.set('th_h_v94', True)
            except Exception: pass
        if old is None:
            try:                                                                # V0.1.93 之前收進來的遊戲／程式 .dat（不是影片，全部預覽圖失敗）：從清單拿掉（只動資料庫，不動檔案）
                bad = [(int(r[0]),) for r in self.db.q("SELECT id,name FROM files WHERE lower(ext)='.dat' AND probed=3") if not is_vcd_dat(r[1])]
                if bad: self.db.xm('DELETE FROM files WHERE id=?', bad); self.log.w(f'清單整理：{len(bad)} 個不是影片的 .dat 檔（遊戲、程式的資料檔）從影片清單拿掉（檔案沒動）')
            except Exception: self.log.err('清單整理 .dat')
        if old is None:                                                         # V0.1.75 上次沒做完的初剪、重新驗證：接著做
            try:
                CP = list(self.cfg.get('cut_pending') or []); ok_ = 0
                for j in CP:
                    try: self.cut_add(j['fid'], [tuple(x) for x in j['segs']], j.get('merge'), j.get('mode')); ok_ += 1
                    except Exception as ex: self.log.w(f'接續上次：有一個初剪接不上（{type(ex).__name__}: {ex}），跳過')
                if CP: self.log.w(f'接續上次：初剪 {ok_}/{len(CP)} 個重新排隊'); self._cut_persist()          # 接不上的不再留著
            except Exception: self.log.err('接續上次的初剪')
            try:
                RP = [int(x) for x in (self.cfg.get('rv_pending') or [])]
                if RP: self.conv_reverify(RP); self.log.w(f'接續上次：重新驗證畫質 {len(RP)} 部')
            except Exception: self.log.err('接續上次的重新驗證')
        else:
            self.log.w(f'熱更新：新引擎 V{self.version} 接手　舊的還在做：預覽圖 {len(self.th_active)} 部、轉檔 {len(self.cv_active)} 部、初剪 {"1" if self.cut_cur else "0"}（做完就交給新的）　'
                       f'排隊：初剪 {len(self.cut_q)}、搬檔 {len(self.op_q)}')
        threading.Thread(target=self._disk_loop, name='VsDisks', daemon=True).start()
        threading.Thread(target=self._migrate_loop, name='VsMigrate', daemon=True).start()
        threading.Thread(target=self._pack_loop, name='VsPack', daemon=True).start()
        try:                                                                     # V0.2.28 上次搬硬碟搬到一半：接著搬（熱更新時等舊的手上那個檔做完）
            if (self.cfg.get('disk_move') or {}).get('state') in ('run', 'pause'): threading.Timer(15, self._mv_kick).start()
        except Exception: self.log.err('🚚 接著搬硬碟')
        threading.Thread(target=self._backup_loop, name='VsDbBackup', daemon=True).start()
        if old is not None: threading.Thread(target=self._prev_gc, name='VsPrevGC', daemon=True).start()
        if old is not None: threading.Thread(target=lambda: (time.sleep(2), self._pack_startup()) if self.alive() else None, name='VsPackStart', daemon=True).start()   # V0.2.27 熱更新上來也檢查一次
        if old is None:
            for k_ in ('thumb', 'probe', 'conv'): self.bg_ramp[k_] = time.time()         # 程式剛開：慢慢加速
        for nm, fn in (('VsProbeBoss', self._probe_boss), ('VsThumbBoss', self._thumb_boss), ('VsConvBoss', self._conv_boss), ('VsCutBoss', self._cut_boss), ('VsOpBoss', self._op_boss), ('VsGovernor', self._gov_loop)):
            threading.Thread(target=fn, name=nm, daemon=True).start()
        if not self.gpu_st.get('checked'): threading.Thread(target=self.gpu_check, name='VsGpuCheck', daemon=True).start()
        if old is None and self.cfg.get('scan_on_start') and self.cfg.get('roots'): self.scan()

    def _prev_gc(self):
        """熱更新後：舊引擎手上的工作都做完了，就把它的資料庫連線關掉、放掉（不然每熱更新一次就多留一份在記憶體）."""
        t0 = time.time()
        while self.alive():
            time.sleep(self.PREV_GC_TICK)
            e = self.prev
            if e is None: return
            try:
                busy = (getattr(e, 'cut_cur', None) is not None or getattr(e, 'op_cur', None) is not None
                        or bool(self.th_active) or bool(self.cv_active) or time.time() - t0 < self.PREV_GC_WAIT)
                if busy: continue
                p2 = getattr(e, 'prev', None)
                for o in (p2, e):                                               # 舊版留下的程式（畫面回呼等）如果還碰資料庫，改用新的連線，不會出錯
                    if o is None or o is self: continue
                    try:
                        od = o.db; o.stop_all = True; o.db = self.db
                        if od is not self.db: od.close()
                    except Exception: pass
                e.prev = None
                self.prev = None
                self.log.w(f'熱更新：舊引擎 V{getattr(e, "version", "") or "?"} 的工作都做完了，已釋放（{time.time() - t0:.0f} 秒後）'); return
            except Exception: self.log.err('釋放舊引擎')

    def discard(self):
        """熱更新失敗：這個沒開始跑的新引擎丟掉（舊的照常）."""
        self.stop_all = True
        try: self.perf.stop = True
        except Exception: pass
        try:
            od = self.db
            if self.prev is not None and getattr(self.prev, 'db', None) is not None: self.db = self.prev.db     # 建到一半的新畫面如果還有排好的回呼，碰到的是舊的（還開著的）連線
            if od is not self.db: od.close()
        except Exception: pass

    def retire(self):
        """熱更新：不再接新工作（正在做的照做完）."""
        self.retired = True
        try: self.perf.stop = True
        except Exception: pass
        self.log.w(f'舊引擎 V{self.version or "?"} 退休：手上的做完就停')

    def log_startup(self):
        L = self.log.w
        L('=' * 100)
        L(f'啟動 {APP_NAME} V{self.version}　{platform.platform()}　Python {platform.python_version()}　{"EXE" if getattr(sys, "frozen", False) else "原始碼"}　程式資料夾 {self.root}')
        L(f'ffmpeg={self.ff or "（找不到）"}　ffprobe={self.ffprobe or "（找不到）"}　ffmpeg_gpu={self.ff_gpu or "—"}')
        try:
            n = self.db.one('SELECT COUNT(*), SUM(missing=0), SUM(th_state=2 AND missing=0), SUM(cv_state=1) FROM files')
            L(f'資料庫：{n[0] or 0:,} 筆（在庫 {n[1] or 0:,}、預覽圖好了 {n[2] or 0:,}、轉檔排隊 {n[3] or 0:,}）')
        except Exception: self.log.err('啟動：讀資料庫')
        for r in self.cfg.get('roots') or []:
            try: du = shutil.disk_usage(r); L(f'影片庫：{r}　剩 {fmt_b(du.free)} / {fmt_b(du.total)}')
            except Exception: L(f'影片庫：{r}　（找不到，硬碟沒接？）')
        L('排除：' + ('、'.join(map(str, (self.cfg.get('ex_dirs') or []) + (self.cfg.get('ex_names') or []))) or '（沒有）') + '　初剪資料夾：' + (self.cfg.get('cut_dir') or '每顆硬碟的 VideoSIFT\\初剪'))
        keys = ('th_on', 'th_n', 'th_step', 'th_h', 'th_prio', 'probe_n', 'cut_mode', 'cut_merge', 'cv_enc', 'cv_q', 'cv_n', 'cv_after', 'grid_sec')
        L('設定：' + '　'.join(f'{k}={self.cfg.get(k)}' for k in keys))

    # ---------- 共用
    def task(self, kind, title):
        with self.lock:
            self._tid += 1; t = {'id': self._tid, 'kind': kind, 'title': title, 'state': 'run', 'pct': None, 'msg': '', 't0': time.time(), 't1': 0}
            self.tasks[self._tid] = t
            while len(self.tasks) > 300:
                k = next(iter(self.tasks))
                if self.tasks[k]['state'] == 'run' and len(self.tasks) < 600: break
                self.tasks.pop(k)
            return t

    def tasks_list(self):
        with self.lock: return list(self.tasks.values())

    def done(self, t, state='done', msg=''):
        t['state'] = state; t['t1'] = time.time()
        if msg: t['msg'] = msg

    def shutdown(self):
        self.stop_all = True
        try:
            import vs_yield; y_ = vs_yield.get()
            if y_ is not None and y_.E is self: y_.close()
        except Exception: pass
        try: self.perf.stop = True
        except Exception: pass
        for e in list(getattr(self, '_seekc', {}).values()):                    # 比畫質用的暫存 MKV
            try: e.get('p') and Path(e['p']).unlink()
            except Exception: pass
        try:
            if self.faces is not None and self.faces.running(): self.faces.stop('關閉 SortCut')
        except Exception: pass
        try:
            if getattr(self, 'hz', None) is not None: self.hz.shutdown()       # HotZone 引擎照常跑（跟原本一樣）
        except Exception: pass
        busy = len(self.th_active) + len(self.cv_active) + (1 if self.cut_cur else 0)
        for p in list(self.procs): p.kill()
        try:                                                                     # V0.2.26 關掉前：有改過的都寫到各硬碟（之後拔走接到別台電腦就是最新的）
            if self.cfg.get('drive_pack') is not False and not os.environ.get('VIDEOSIFT_SELFTEST'): self.pack_export_due(force=True, why='（關閉程式）')
        except Exception: self.log.err('💽 關閉前寫到各硬碟')
        e = self.prev
        while e is not None:                                                    # 熱更新前的舊引擎（還在做手上那部的）也一起停
            try: e.stop_all = True; e.db.close()
            except Exception: pass
            e = getattr(e, 'prev', None)
        self.log.w(f'關閉 {APP_NAME} V{self.version}（停掉做到一半的 {busy} 個工作，下次打開接著做）'); self.log.w('=' * 100); self.db.close()

    def root_of(self, path):
        P = str(path).lower(); best = ''
        for r in self.cfg.get('roots') or []:
            rl = str(r).lower().rstrip('\\/')
            if (P == rl or P.startswith(rl + os.sep) or P.startswith(rl + '/')) and len(rl) > len(best): best = str(r)
        return best

    def arch_dir(self, kind, src, setting=''):
        """歸檔的位置：設定裡指定的資料夾，沒指定就是「同一顆硬碟的 VideoSIFT\\初剪／收藏／待刪／原檔備份」，底下保留原本的子資料夾結構."""
        src = Path(src); r = self.root_of(src); rp = Path(r) if r else Path(src.anchor or src.parent)
        try: rel = src.parent.relative_to(rp)
        except Exception: rel = Path()
        base = Path(setting) if setting else Path(src.anchor or rp) / ARCH_BASE / ARCH2[kind]
        sub = Path(safe_name(rp.name)) if rp.name else Path()
        return base / sub / rel

    def thumbs_root(self):
        d = self.cfg.get('th_dir'); return Path(d) if d else self.data / 'thumbs'

    # ---------- 舊的歸檔資料夾（G:\_初剪…）搬進 G:\VideoSIFT\（V0.1.09）
    def _migrate_loop(self):
        """等手上的初剪／搬檔做完（轉檔「原檔搬到備份」正在做的也等），再把每顆硬碟最上層的舊資料夾搬進 VideoSIFT\。同一顆硬碟只是改位置，一下就好."""
        if os.environ.get('VIDEOSIFT_SELFTEST'): return                         # 自我測試不動真的硬碟上的資料夾
        for _ in range(3600):
            if not self.alive(): return
            idle = not self.cut_q and not self.cut_cur and not self.op_q and not self.op_cur and not ((self.cfg.get('cv_after') == 'orig') and self.cv_active)
            if idle: break
            time.sleep(1)
        try: self.migrate_arch()
        except Exception: self.log.err('搬移舊的歸檔資料夾')

    def migrate_arch(self):
        anchors = sorted({Path(str(r)).anchor for r in self.cfg.get('roots') or [] if Path(str(r)).anchor})
        moved = []
        for a in anchors:
            for kind, old in ARCH.items():
                src = Path(a) / old
                if not src.is_dir(): continue
                dst = Path(a) / ARCH_BASE / ARCH2[kind]; t0 = time.time()
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if not dst.exists(): os.replace(str(src), str(dst)); how = '整個資料夾改位置'
                    else: how = self._merge_dir(src, dst)
                    moved.append((str(src), str(dst)))
                    self.db.x("INSERT INTO ops(kind,src,dst,t,ok,err) VALUES('migrate',?,?,?,1,?)", (str(src), str(dst), time.time(), how))
                    self.log.w(f'歸檔資料夾搬家：{src} → {dst}（{how}，{time.time() - t0:.1f} 秒）'); self.oplog('migrate', src=str(src), dst=str(dst), detail=f'歸檔資料夾搬進 VideoSIFT（{how}）')
                except Exception as ex:
                    self.log.err(f'歸檔資料夾搬家失敗：{src} → {dst}')
                    self.db.x("INSERT INTO ops(kind,src,dst,t,ok,err) VALUES('migrate',?,?,?,0,?)", (str(src), str(dst), time.time(), str(ex)[-300:]))
        for src, dst in moved:                                                  # 資料庫裡記的路徑跟著改（刪除原檔前要確認初剪檔還在）
            for tbl, col in (('cuts', 'out'), ('ops', 'dst'), ('files', 'path')):
                for sep in ('\\', '/'):
                    self.db.x(f"UPDATE {tbl} SET {col}=? || substr({col}, ?) WHERE substr({col}, 1, ?)=?", (dst + sep, len(src) + 2, len(src) + 1, src + sep))
            self.db.x("UPDATE files SET folder=? WHERE folder=?", (dst, src))
            for sep in ('\\', '/'): self.db.x("UPDATE files SET folder=? || substr(folder, ?) WHERE substr(folder, 1, ?)=?", (dst + sep, len(src) + 2, len(src) + 1, src + sep))
            for j in list(self.cut_hist):
                j['outs'] = [dst + o[len(src):] if path_key(o).startswith(path_key(src) + os.sep) else o for o in j.get('outs') or []]
            for k in ('cut_dir', 'fav_dir', 'trash_dir'):
                v = str(self.cfg.get(k) or '')
                if v and path_key(v) == path_key(src): self.cfg.set(k, '')            # 原本就指定成舊的位置 → 改回預設（＝新的位置）
        if moved: self.migrated = moved
        return moved

    def _merge_dir(self, src, dst):
        """目的地已經有同名資料夾：一個一個檔搬進去（同名的加 (2)），搬完把空資料夾拿掉."""
        n = 0; ren = 0
        for d, dirs, files in os.walk(src, topdown=False):
            rel = Path(d).relative_to(src)
            for f in files:
                s0 = Path(d) / f; t = dst / rel / f; t.parent.mkdir(parents=True, exist_ok=True)
                if t.exists(): t = unique_path(t); ren += 1
                os.replace(str(s0), str(t)); n += 1
                if t.name != f: self.db.x("UPDATE cuts SET out=? WHERE out=?", (str(t), str(s0)))
            try: os.rmdir(d)
            except OSError: pass
        return f'合併 {n} 個檔' + (f'（{ren} 個同名，加了 (2)）' if ren else '')

    # ---------- 資料庫備份（分級、標籤、備註、剪輯紀錄都在這裡）
    def backup_dir(self): return self.data / 'db_backup'

    def db_backup(self, why='每天自動'):
        """用 SQLite 的線上備份（程式照常用、不用停）。保留最近 N 份."""
        d = self.backup_dir(); d.mkdir(parents=True, exist_ok=True); out = d / f'videosift_{time.strftime("%Y%m%d_%H%M%S")}.sqlite3'; t0 = time.time()
        if not self.db_check():                                                 # 壞掉的不要備份（不然好的備份會被一份份擠掉）
            self.log.w(f'資料庫備份（{why}）：跳過，資料庫檢查有問題，保留原本的備份'); return ''
        try:
            dst = sqlite3.connect(str(out))
            with self.db.lock: self.db.con.backup(dst)
            try: dst.execute('PRAGMA journal_mode=DELETE')                     # 備份檔不要是 WAL（不然打開會留下 -wal／-shm）
            except Exception: pass
            dst.close()
            try: shutil.copy2(str(self.cfg.path), str(out.with_name(out.stem.replace('videosift_', 'settings_') + '.json')))     # 設定也一起（快捷鍵、分類、排除…）
            except Exception: self.log.err('備份設定檔')
            keep = max(2, int(self.cfg.get('db_backup_keep') or 7))
            for o in sorted(d.glob('settings_*.json'))[:-keep]:
                try: o.unlink()
                except Exception: pass
            tgt = self._restore_target()
            for o in sorted(d.glob('videosift_*.sqlite3'))[:-keep]:
                if o.name == tgt: continue                                      # 排定要還原的那份不能刪
                try: o.unlink()
                except Exception: pass
            for o in list(d.glob('videosift_*.sqlite3-wal')) + list(d.glob('videosift_*.sqlite3-shm')):
                if not o.with_name(o.name.rsplit('-', 1)[0]).exists():
                    try: o.unlink()
                    except Exception: pass
            self.log.w(f'資料庫備份（{why}）：{out.name}　{fmt_b(out.stat().st_size)}　{time.time() - t0:.1f} 秒'); return str(out)
        except Exception:
            self.log.err('資料庫備份'); return ''

    def last_backup(self):
        try: L = sorted(self.backup_dir().glob('videosift_*.sqlite3')); return (L[-1].name, L[-1].stat().st_mtime) if L else ('', 0)
        except Exception: return ('', 0)

    def db_check(self):
        """PRAGMA quick_check：True＝正常。結果放在 db_health（畫面會提醒）."""
        try:
            r = self.db.one('PRAGMA quick_check'); ok = (r[0] if r else '') == 'ok'; msg = '' if ok else str(r[0] if r else '?')
        except Exception as ex: ok = False; msg = f'{type(ex).__name__}: {ex}'
        was = self.db_health.get('ok'); self.db_health.update(ok=ok, msg=msg, t=time.time())
        if was is None or was != ok: self.log.w('資料庫檢查：' + ('✔ 正常' if ok else f'⚠ 有問題：{msg[:300]}（可以到 設定 → 資料庫備份 →「↩ 從備份還原」）'))
        return ok

    def db_backups(self):
        """[(檔名, 修改時間, 大小)]，新的在前."""
        try: return [(p.name, p.stat().st_mtime, p.stat().st_size) for p in sorted(self.backup_dir().glob('videosift_*.sqlite3'), reverse=True)]
        except Exception: return []

    @staticmethod
    def check_db_file(p):
        """唯讀檢查一個資料庫檔（不會留下 -wal／-shm，路徑有 # ? % 也可以）。回傳 (好不好, 幾部影片, 訊息)."""
        try:
            uri = 'file:' + urllib.request.pathname2url(str(Path(p).resolve())) + '?mode=ro&immutable=1'
            c = sqlite3.connect(uri, uri=True)
            try:
                r = c.execute('PRAGMA quick_check').fetchone(); ok = (r[0] if r else '') == 'ok'
                n = c.execute('SELECT COUNT(*) FROM files').fetchone()[0] if ok else 0
                return ok, n, '' if ok else str(r[0] if r else '?')
            finally: c.close()
        except Exception as ex: return False, 0, f'{type(ex).__name__}: {ex}'

    def request_restore(self, name):
        """下次開程式時用這份備份還原（現在的資料庫先改名留著，不刪）。先檢查備份本身是好的."""
        src = self.backup_dir() / Path(name).name
        if not src.is_file(): return {'ok': False, 'message': '找不到這份備份'}
        ok, n, msg = self.check_db_file(src)
        if not ok: return {'ok': False, 'message': f'這份備份有問題，不能用：{msg}'}
        (self.data / 'restore_db.json').write_text(json.dumps({'from': str(src), 't': time.time()}, ensure_ascii=False), encoding='utf-8')
        self.log.w(f'資料庫還原：已排定下次開程式時用 {src.name}（{n:,} 部影片）還原'); return {'ok': True, 'n': n}

    def _restore_target(self):
        """排定要還原的那份備份（備份清理時不能刪它）."""
        try: return Path(json.loads((self.data / 'restore_db.json').read_text(encoding='utf-8'))['from']).name
        except Exception: return ''

    def _swap_db(self, src, keep):
        """把 src 換成目前的資料庫：先複製到暫存檔，再把現在的（含 -wal／-shm）搬到 keep，最後換上。任何一步失敗都搬回原樣並丟例外."""
        db = self.data / 'videosift.sqlite3'; tmp = db.with_name(db.name + '.restoring'); moved = []
        shutil.copy2(str(src), str(tmp))
        try:
            keep.mkdir(parents=True, exist_ok=True)
            for x in (db, db.with_name(db.name + '-wal'), db.with_name(db.name + '-shm')):
                if x.exists(): os.replace(str(x), str(keep / x.name)); moved.append(x)
            for x in (db, db.with_name(db.name + '-wal'), db.with_name(db.name + '-shm')):
                if x.exists(): raise RuntimeError(f'{x.name} 搬不走（被別的程式開著？）')
            os.replace(str(tmp), str(db))
        except Exception:
            for x in moved:
                try:
                    if not x.exists(): os.replace(str(keep / x.name), str(x))
                except Exception: pass
            try: tmp.unlink()
            except Exception: pass
            raise

    def _pending_restore(self):
        f = self.data / 'restore_db.json'
        if not f.exists(): return
        try:
            src = Path(json.loads(f.read_text(encoding='utf-8'))['from'])
            if not src.is_file(): raise RuntimeError(f'找不到要還原的備份 {src.name}')
            ok, n, msg = self.check_db_file(src)
            if not ok: raise RuntimeError(f'備份 {src.name} 有問題：{msg}')
            keep = self.data / f'db_before_restore_{time.strftime("%Y%m%d_%H%M%S")}'; self._swap_db(src, keep); f.unlink()
            self.log.w(f'資料庫還原完成：用 {src.name}（{n:,} 部）；原本的資料庫留在 Data\\{keep.name}（確定沒問題再自己刪）')
        except Exception as ex:
            self.log.err('資料庫還原（沒有換，照原本的資料庫繼續）')
            self.db_health.update(recover_msg=f'排定的資料庫還原沒有做（{ex}），照原本的資料庫繼續用，資料沒有動。')
            try: os.replace(str(f), str(f.with_suffix('.failed')))
            except Exception: pass

    @staticmethod
    def _corrupt_err(ex):
        m = str(ex).lower()
        return isinstance(ex, sqlite3.DatabaseError) and any(k in m for k in ('malformed', 'not a database', 'disk image', 'file is encrypted'))

    def _recover_db(self, ex):
        """資料庫壞到打不開：原本的改名留著，換成最近一份檢查過是好的備份；都沒有就開一個新的。
        只有「真的壞掉」才這樣做；被鎖住、磁碟滿、權限問題等就把錯誤丟出去（不要拿好的資料庫去換備份）."""
        if not self._corrupt_err(ex): raise ex
        keep = self.data / f'db_broken_{time.strftime("%Y%m%d_%H%M%S")}'; used = ''
        for p in sorted(self.backup_dir().glob('videosift_*.sqlite3'), reverse=True):
            if self.check_db_file(p)[0]:
                self._swap_db(p, keep); used = p.name; break                    # 搬不走會丟例外：寧可開不起來也不要蓋掉
        if not used:
            db = self.data / 'videosift.sqlite3'; keep.mkdir(parents=True, exist_ok=True)
            for x in (db, db.with_name(db.name + '-wal'), db.with_name(db.name + '-shm')):
                if x.exists(): os.replace(str(x), str(keep / x.name))
        st = Store(self.data / 'videosift.sqlite3')
        msg = f'資料庫打不開（{type(ex).__name__}: {str(ex)[:200]}），' + (f'已經自動換成最近一份好的備份 {used}' if used else '也沒有可用的備份，開了一個新的（重新掃描就會回來）') + f'；壞掉的那份留在 Data\\{keep.name}'
        self.db_health.update(recovered=used or 'new', recover_msg=msg); self.log.w('⚠ ' + msg); return st

    def _backup_loop(self):
        self.db_check()
        for _ in range(90):
            if not self.alive(): return
            time.sleep(1)
        while self.alive():
            try:
                if self.cfg.get('db_backup') is not False:
                    name, t = self.last_backup()
                    if not name or time.strftime('%Y%m%d', time.localtime(t)) != time.strftime('%Y%m%d'): self.db_backup()
            except Exception: self.log.err('自動備份')
            for _ in range(1800):
                if not self.alive(): return
                time.sleep(1)

    # ---------- 🧪 清理用不到的預覽圖
    def thumbs_orphans(self):
        """不在影片庫的影片（刪掉、搬走、移除）留下的預覽圖資料夾。回傳 {'dirs': [...], 'bytes': n, 'used': n}."""
        root = self.thumbs_root(); keep = {path_key(r[0]) for r in self.db.q("SELECT th_dir FROM files WHERE th_dir!=''")}        # V0.2.24 讀不到的（隔離中）預覽圖也留著
        active = {path_key(str(J.get('path', ''))) for J in list(self.th_active.values())}
        dirs = []; tot = 0; used = 0
        if root.is_dir():
            for sub in root.iterdir():
                if not sub.is_dir(): continue
                for d in sub.iterdir():
                    if not d.is_dir() or d.name.endswith('.tmp'): continue
                    try: sz = sum(f.stat().st_size for f in d.iterdir() if f.is_file())
                    except Exception: sz = 0
                    if path_key(d) in keep or not d.name.isdigit() or int(d.name) in self.th_active: used += sz; continue
                    dirs.append(str(d)); tot += sz
        return {'dirs': dirs, 'bytes': tot, 'used': used, 'active': len(active)}

    def thumbs_clean(self, dirs):
        n = 0; b = 0; root = path_key(self.thumbs_root())
        for d in dirs:
            p = Path(d)
            if not path_key(p).startswith(root + os.sep) or not p.name.isdigit(): continue          # 只刪預覽圖資料夾裡的
            try: b += sum(f.stat().st_size for f in p.iterdir() if f.is_file())
            except Exception: pass
            shutil.rmtree(p, ignore_errors=True); n += 1
            self.db.x("UPDATE files SET th_state=0, th_dir='' WHERE id=? AND missing=1", (int(p.name),))
        self.log.w(f'清理用不到的預覽圖：{n} 個資料夾、{fmt_b(b)}'); self.oplog('clean', detail=f'清理用不到的預覽圖 {n} 個資料夾、{fmt_b(b)}', size=b)
        return n, b

    def _th_low_space(self):
        """預覽圖資料夾所在的硬碟剩不到 2 GB：先不做新的預覽圖（每分鐘看一次）."""
        now = time.time()
        if now - getattr(self, '_tls_t', 0) < 60: return getattr(self, '_tls', False)
        self._tls_t = now; fb = free_bytes(self.thumbs_root()); low = fb is not None and fb < 2e9
        if low != getattr(self, '_tls', False): self.log.w(f'預覽圖資料夾的硬碟只剩 {fmt_b(fb)}，先暫停做預覽圖（清出空間就會自己繼續）' if low else '預覽圖資料夾的硬碟空間夠了，繼續做預覽圖')
        self._tls = low; self.th_low = (f'預覽圖資料夾的硬碟只剩 {fmt_b(fb)}，暫停中' if low else ''); return low

    # ---------- 🔤 亂碼檔名解碼改名（🧪）
    def rename_candidates(self, limit=2000):
        out = []
        for r in self.db.q("SELECT id,path,folder,name,ext FROM files WHERE missing=0 AND arch='' ORDER BY folder,name"):
            stem = Path(r['name']).stem
            if not looks_garbled(stem): continue
            tok = _garbled_token(stem); w = None
            for t in ([stem, tok] if tok != stem else [stem]):
                w, how = decode_name(t)
                if w: break
            if not w: continue
            w = os.path.splitext(w)[0] if os.path.splitext(w)[1].lower() in VIDEO_EXT else w
            new = safe_name(w)[:120] + (r['ext'] or Path(r['name']).suffix)
            if new != r['name']: out.append({'id': r['id'], 'path': r['path'], 'name': r['name'], 'new': new, 'how': how})
            if len(out) >= limit: break
        return out

    def rename_file(self, fid, new):
        r = self.file(fid)
        if not r: return {'ok': False, 'message': '找不到'}
        why = self.changed_since_scan(r)
        if why: return {'ok': False, 'message': f'{r["name"]}：{why}，沒有改'}
        src = Path(r['path']); dst = unique_path(src.with_name(safe_name(new)))
        try: os.rename(str(src), str(dst))
        except Exception as ex: return {'ok': False, 'message': f'{r["name"]}：改不了（{ex}）'}
        self.db.x('UPDATE files SET path=?, name=? WHERE id=?', (str(dst), dst.name, int(fid)))
        if EXT_MOVED.get('fn'):                                                   # V0.5.53 改名：整理的紀錄跟著改（不用重算指紋）
            try: EXT_MOVED['fn'](str(src), str(dst))
            except Exception: pass
        self.oplog('rename', src=str(src), dst=str(dst), fid=int(fid), size=r['size'] or 0, detail=f'改名・搬：{src.name} → {dst.name}')
        return {'ok': True, 'message': dst.name}

    # ---------- 🧪 背景加速（兩種：電腦閒置時／夜間時段；可以都開）
    def boosted(self):
        """現在要不要加速？回傳原因（'' ＝不加速）. 畫面會把最後一次有人操作的時間寫在 self.last_user."""
        L = self.cfg.get('lab') or {}; why = ''
        if L.get('boost_idle'):
            idle = time.time() - float(getattr(self, 'last_user', 0) or time.time())
            if idle >= int(L.get('boost_idle_min') or 10) * 60: why = f'電腦閒置 {int(idle // 60)} 分鐘'
        if not why and L.get('boost_night'):
            h = time.localtime().tm_hour; a = int(L.get('night_from', 23)); b = int(L.get('night_to', 8))
            if (h >= a or h < b) if a > b else (a <= h < b): why = f'夜間時段 {a}:00～{b}:00'
        if bool(why) != bool(getattr(self, '_boost_was', '')):
            self.log.w(('🚀 背景加速開始：' + why) if why else '🚀 背景加速結束（回到平常速度）')
        self._boost_was = why; return why

    # ---------- 硬碟分道（HDD 一次一部、照順序讀、別人在用就讓路）
    def _disk_loop(self):
        k = 0
        while self.alive():
            try:
                t0 = time.time(); self.drives.refresh(); self._root_lane = {}
                if k == 0:
                    self.log.w('硬碟：' + ('；'.join(f'{self.drives.label(l)} = {self.drives.media(l)}' for l in sorted({self.lane_of(r) for r in self.cfg.get('roots') or []})) or '（還沒有影片庫）')
                               + f'（偵測 {time.time() - t0:.1f} 秒）')
            except Exception: self.log.err('偵測硬碟')
            try:                                                                 # V0.2.24 讀不到的先隔離、接回來套回去
                if k == 0: self._park_mig_v224()
                if k == 0 or self.offline or self.cfg.get('parked') or getattr(self, '_remap_want', False): self.vol_check()
            except Exception: self.log.err('硬碟隔離檢查')
            try:
                if getattr(self, '_remap_want', False) and not self.cv_active and not self.cut_cur:      # 代號換了：找到原本那顆就改過去
                    M = self.drive_remap_detect()
                    if M:
                        r_ = self.drive_remap(M); self.dedupe_letters(); self.remap_msg = r_.get('message', ''); self._off_chk = {}
                    self._remap_want = False
            except Exception: self.log.err('硬碟代號改過去')
            k += 1
            for _ in range(60):
                if not self.alive(): return
                time.sleep(1)

    def lane_of(self, path):
        try: return self.drives.lane_of(path)
        except Exception: return 'v?'

    def root_lane(self, root):
        L = self._root_lane.get(root)
        if L is None: L = self._root_lane[root] = self.lane_of(root)
        return L

    def lane_cap(self, lane):
        m = self.drives.media(lane)
        if m in ('HDD', '?', 'USB'): return max(1, int(self.cfg.get('hdd_n') or 1))      # V0.1.91 認不出來的（多半是 USB 外接 HDD）也當 HDD
        if m == 'NET': return max(1, int(self.cfg.get('net_n') or 1))
        return 99

    def lane_load(self, lane, with_conv=True):
        lp = lambda J: J.get('lane') or self.lane_of(J.get('path') or '')
        n = sum(1 for J in list(self.th_active.values()) if lp(J) == lane) + self.pr_lanes.get(lane, 0)
        if with_conv and self.cfg.get('hdd_yield') and self.drives.media(lane) == 'HDD':
            n += sum(1 for J in list(self.cv_active.values()) if lp(J) == lane)
        return n

    def lane_busy_other(self, lane):
        """別的程式正在大量用這顆 HDD（我們自己在這顆上沒有工作時才看得準）. 回傳忙碌 % 或 0."""
        lim = int(self.cfg.get('hdd_busy') or 0)
        if not lim or self.drives.media(lane) != 'HDD' or self.lane_load(lane) > 0: return 0
        b = max([(self.dcount.get(n) or {}).get('busy', 0) for n in self.drives.disk_nums(lane)] or [0])
        return b if b >= lim else 0

    def lane_open(self, lane, extra=0):
        """這一道現在可以再開一個工作嗎？順便記下為什麼不行（給後台看）."""
        h = (getattr(self, 'lane_hold', None) or {}).get(lane)
        if h and h[0] > time.time(): self.lane_note[lane] = str(h[1]); return False          # 🔥 硬碟協調員：這段時間讓給 HotZone
        if self.cfg.get('hdd_yield') and self.scan_st.get('running') and self.scan_st.get('lane') == lane and self.drives.media(lane) == 'HDD':
            self.lane_note[lane] = '正在掃描這顆 HDD，預覽圖先等'; return False
        b = self.lane_busy_other(lane)
        if b:
            if not self.lane_note.get(lane, '').startswith('別的程式'): self.log.w(f'硬碟 {self.drives.label(lane)}：別的程式正在用（忙碌 {b:.0f}%），新的預覽圖先等')
            self.lane_note[lane] = f'別的程式正在用這顆硬碟（忙碌 {b:.0f}%），先等'; return False
        if self.lane_load(lane) + extra >= self.lane_cap(lane):
            self.lane_note[lane] = f'這顆是 {self.drives.media(lane)}，同時 {self.lane_cap(lane)} 部（滿了）'; return False
        self.lane_note.pop(lane, None); return True

    def full_roots(self):
        """這些影片庫所在的硬碟現在不能再開工作 → 查詢時先排除（其他硬碟才不會被卡住）。離線的硬碟也排除."""
        return [r for r in {str(x) for x in self.cfg.get('roots') or []} if self.root_offline(r) or not self.lane_open(self.root_lane(r))]

    def root_offline(self, root, fresh=False):
        """影片庫找不到了（外接硬碟拔掉、網路磁碟斷線、睡著）。每 10 秒最多實際檢查一次；狀態變了記 LOG."""
        root = str(root); now = time.time()
        if not fresh and now - self._off_chk.get(root, 0) < 10: return root in self.offline
        self._off_chk[root] = now
        try: gone = not os.path.exists(root)
        except Exception: gone = True
        want = (self.cfg.get('root_vol') or {}).get(root)
        if not gone and want and IS_WIN:                                        # V0.1.95 代號對、但不是同一顆硬碟（重開機後代號換了）→ 當成離線，不掃、不做（免得把別顆的檔當成新的收進來）
            sn = self.vol_serial(root)
            if sn and sn != want:
                gone = True
                if root not in self.offline: self.log.w(f'⚠ {root} 現在的硬碟序號 {sn} 不是原本那顆（{want}）：磁碟代號換了，先當成離線，等找到原本那顆再改過去')
                self._remap_want = True
        if gone and root not in self.offline:
            try:
                if not hasattr(self, 'lane_off_t'): self.lane_off_t = {}
                self.lane_off_t[self.root_lane(root)] = now
            except Exception: pass
            self.offline[root] = now; self.log.w(f'⚠ 硬碟離線：找不到 {root}（拔掉了或睡著了？）。這顆的預覽圖、讀影片資訊、轉檔先暫停，做到一半失敗的不會被當成壞檔，接回來會自動繼續')
            try:
                if getattr(self, 'usb', None) is not None: self.usb.on_offline(root)
            except Exception: pass
        elif not gone and root in self.offline:
            t0 = self.offline.pop(root, now); self.log.w(f'✅ 硬碟回來了：{root}（離線 {fmt_t(now - t0)}），繼續做')
        return gone

    # ---------- V0.2.24 讀不到的先隔離：拔掉的硬碟／別顆硬碟占了同一個代號 → 原本那顆的紀錄改成「|序號|\…」（沒有代號），預覽圖、分級全部留著；接回來（任何代號）自動套回去
    PARK_DELAY = 600                                                             # 拔掉超過 10 分鐘才隔離（USB 一下斷一下回來的不動）
    _HIST = staticmethod(lambda r: bool(r['grade'] or r['fav'] or r['cut_n'] or r['note'] or r['tag'] or int(r['cv_state'] or 0) or r['arch'] or int(r['viewed'] or 0) or int(r['th_state'] or 0) == 2))

    @staticmethod
    def _pfx_swap(v, old, new):
        """v 開頭是 old（不分大小寫、要剛好在資料夾分界）就換成 new."""
        v = str(v or '')
        if v and old and v[:len(old)].lower() == old.lower() and (len(v) == len(old) or v[len(old)] in '\\/' or old[-1] in '\\/|'): return new + v[len(old):]
        return v

    def vol_letters_c(self, ttl=20):
        """V0.3.17 同 vol_letters，但 20 秒內用上次的結果（新功能常常要問，不要一直去碰每顆硬碟、吵醒睡著的硬碟）."""
        c = getattr(self, '_vl_c', None)
        if c and time.time() - c[0] < ttl: return dict(c[1])
        v = self.vol_letters(); self._vl_c = (time.time(), v); return dict(v)

    def vol_letters(self):
        """現在接著的硬碟：{序號: 代號}."""
        out = {}
        if not IS_WIN: return out
        for c in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
            try:
                if os.path.exists(c + ':\\'):
                    sn = self.vol_serial(c + ':\\')
                    if sn: out.setdefault(sn, c)
            except Exception: pass
        return out

    @staticmethod
    def vol_label(root):
        """磁碟的名稱（卷標，例如「My Passport」）."""
        if not IS_WIN: return ''
        try:
            import ctypes
            d = os.path.splitdrive(str(root))[0]
            buf = ctypes.create_unicode_buffer(261)
            ok = ctypes.windll.kernel32.GetVolumeInformationW(ctypes.c_wchar_p(d + '\\'), buf, 261, None, None, None, None, 0)
            return buf.value if ok else ''
        except Exception: return ''

    def _busy_letter(self, X):
        """這個代號上現在有預覽圖／轉檔／初剪／讀資訊在做嗎（有就先不搬紀錄）."""
        X = str(X)[:1].upper()
        try:
            for E_ in (self, getattr(self, 'prev', None)):
                if E_ is None: continue
                for J in list(getattr(E_, 'th_active', {}).values()) + list(getattr(E_, 'cv_active', {}).values()):
                    if str(J.get('path') or '')[:1].upper() == X: return True
            cc = self.cut_cur
            if cc and str(cc.get('path') if isinstance(cc, dict) else cc)[:1].upper() == X: return True
            if self.pr_lanes.get(self.lane_of(X + ':\\'), 0) > 0: return True
        except Exception: return True
        return False

    def _exists_fn(self):
        cache = {}
        _split = os.path.split if IS_WIN else __import__('ntpath').split
        def ex(p, size=None):
            d, n = _split(str(p))
            if d not in cache:
                try: cache[d] = {x.name.lower(): x for x in os.scandir(d)}
                except Exception: cache[d] = {}
            e = cache[d].get(n.lower())
            if e is None: return False
            if size is None: return True
            try: return e.stat().st_size == int(size)
            except Exception: return False
        return ex

    def _move_rows(self, rows, old, new, root_new, ex):
        """把這些紀錄的路徑開頭 old 換成 new（path、folder、root、轉檔紀錄）。目的地已經有一筆同路徑的：留有紀錄的那筆."""
        F = ('folder', 'cv_src', 'cv_del', 'cv_out', 'th_dir')                 # V0.2.27 th_dir 也跟著換（預覽圖現在在硬碟上）
        n = 0; dele = 0
        for r in rows:
            newp = self._pfx_swap(r['path'], old, new)
            if newp == r['path']: continue
            try:
                dup = self.db.one('SELECT * FROM files WHERE path=? AND id!=?', (newp, r['id']))
                if dup is not None:
                    if self._HIST(dict(dup)) and not self._HIST(r): self.db.x('DELETE FROM files WHERE id=?', (r['id'],)); dele += 1; continue
                    self.db.x('DELETE FROM files WHERE id=?', (int(dup['id']),)); dele += 1
                vals = [newp] + [self._pfx_swap(r[k], old, new) for k in F] + [root_new if root_new is not None else self._pfx_swap(r['root'], old, new)]
                miss = 1 if newp.startswith('|') else (0 if ex(newp) else 1)
                self.db.x('UPDATE files SET path=?,folder=?,cv_src=?,cv_del=?,cv_out=?,th_dir=?,root=?,missing=? WHERE id=?', (*vals, miss, r['id'])); n += 1
            except Exception: self.log.err(f'隔離／套回：{r.get("path")}')
        return n, dele

    def park_root(self, root, key, label='', serial='', only_gone=True):
        """把這個影片庫（原本那顆硬碟）的紀錄隔離起來：路徑前面的代號拿掉（變成 |序號|），預覽圖、分級、轉檔紀錄全部留著."""
        R = str(root); X = R[:2]; pre = f'|{key}|'
        rows = [dict(r) for r in self.db.q("SELECT * FROM files WHERE root=? AND substr(path,1,1)!='|'", (R,))]
        ex = self._exists_fn()
        if only_gone: rows = [r for r in rows if not ex(r['path'], r['size'] if r['size'] else None)]
        n, _d = self._move_rows(rows, X, pre, pre + R[2:], ex)
        P = dict(self.cfg.get('parked') or {}); old = P.get(key) or {}
        P[key] = {'root': old.get('root') or R, 'serial': serial or old.get('serial', ''), 'label': label or old.get('label', ''), 't': old.get('t') or time.time()}
        self.cfg.set('parked', P)
        if n: self.log.w(f'🗄 隔離：{R} 原本那顆硬碟（{label or "沒有名稱"}，序號 {serial or "?"}）的 {n:,} 部紀錄先隔離（不再掛在 {X} 下面；預覽圖、分級都留著），接回來會自動套回去')
        try: self.info_c['t'] = 0
        except Exception: pass
        return n

    def unpark(self, key, base, force=False):
        """隔離的那顆硬碟找到了（或你手動指定位置）：紀錄套回 base（原本的影片庫在現在的哪裡）."""
        P = dict(self.cfg.get('parked') or {}); I = P.get(key)
        if not I: return {'ok': False, 'message': '找不到這筆隔離的紀錄'}
        pre = f'|{key}|'; R0 = str(I.get('root') or ''); old = (pre + R0[2:]).rstrip('\\/'); newb = os.path.normpath(str(base)).rstrip('\\/')
        if old == pre: old = pre                                                  # 原本是整顆（E:\）
        rows = [dict(r) for r in self.db.q('SELECT * FROM files WHERE substr(path,1,?)=?', (len(pre), pre))]
        ex = self._exists_fn()
        if not force and rows:
            S = [r for r in rows if r['size']][:30] or rows[:30]
            hit = sum(1 for r in S if ex(self._pfx_swap(r['path'], old, newb)))
            if not hit: return {'ok': False, 'need_force': True, 'message': f'在 {newb} 抽查 {len(S)} 部，一部都找不到，可能選錯位置了'}
        newroot = (newb + '\\') if len(newb) == 2 and newb[1] == ':' else newb
        n, dele = self._move_rows(rows, old, newb, newroot, ex)
        left = (self.db.one('SELECT COUNT(*) FROM files WHERE substr(path,1,?)=?', (len(pre), pre)) or [0])[0]
        if not left: P.pop(key, None); self.cfg.set('parked', P)
        R = [str(x) for x in self.cfg.get('roots') or []]
        if not any(path_key(x) == path_key(newroot) for x in R): R.append(newroot); self.cfg.set('roots', R)
        vol = dict(self.cfg.get('root_vol') or {}); sn = self.vol_serial(newroot)
        if sn: vol[newroot] = sn; self.cfg.set('root_vol', vol)
        self.offline.pop(newroot, None); self._off_chk = {}; self._root_lane = {}
        try: self.info_c['t'] = 0
        except Exception: pass
        msg = f'隔離的「{I.get("label") or R0}」套回 {newroot}：{n:,} 部（預覽圖、分級都沿用）' + (f'；重複的 {dele:,} 筆合併' if dele else '') + (f'；還有 {left:,} 部沒對上，留在隔離' if left else '')
        self.log.w('🗄 ' + msg)
        try: self.scan([newroot])
        except Exception: pass
        return {'ok': True, 'n': n, 'message': msg}

    def relocate_folder(self, old, new, force=False):
        """資料夾搬走了：把這個資料夾（含子資料夾）的紀錄改到新位置，預覽圖、分級都沿用."""
        old = os.path.normpath(str(old)).rstrip('\\/'); new = os.path.normpath(str(new)).rstrip('\\/')
        if old.startswith('|'): old = str(old)
        rows = [dict(r) for r in self.db.q('SELECT * FROM files WHERE folder=? OR substr(folder,1,?)=?', (old, len(old) + 1, old + '\\'))]
        if not rows: return {'ok': False, 'message': '這個資料夾沒有紀錄'}
        ex = self._exists_fn()
        if not force:
            S = rows[:30]; hit = sum(1 for r in S if ex(self._pfx_swap(r['path'], old, new)))
            if not hit: return {'ok': False, 'need_force': True, 'message': f'在 {new} 抽查 {len(S)} 部，一部都找不到，可能選錯位置了'}
        rt = self.root_of(new + '\\x')
        if not rt:
            rt = new; R = [str(x) for x in self.cfg.get('roots') or []]; R.append(new); self.cfg.set('roots', R)
        n, dele = self._move_rows(rows, old, new, rt, ex)
        try: self.info_c['t'] = 0
        except Exception: pass
        msg = f'資料夾 {old} → {new}：{n:,} 部改好（預覽圖、分級都沿用）' + (f'；重複的 {dele:,} 筆合併' if dele else '')
        self.log.w('🗄 ' + msg)
        try: self.scan([rt])
        except Exception: pass
        return {'ok': True, 'n': n, 'message': msg}

    def vol_check(self, force=False):
        """每分鐘：別顆硬碟占了影片庫的代號 → 原本那顆的紀錄隔離；拔掉 10 分鐘以上 → 隔離；隔離的那顆接回來（任何代號）→ 套回去."""
        lk = getattr(self, '_vol_lock', None)
        if lk is None: lk = self._vol_lock = threading.Lock()
        if not lk.acquire(blocking=False): return []
        out = []
        try:
            if not IS_WIN: return out
            L = self.vol_letters(); at = {v: k for k, v in L.items()}
            roots = [str(x) for x in self.cfg.get('roots') or []]; vol = dict(self.cfg.get('root_vol') or {}); P = dict(self.cfg.get('parked') or {})
            known = set(P) | {v for k, v in vol.items()}
            VL = dict(self.cfg.get('vol_label') or {}); ch = False
            for R in roots:
                w_ = vol.get(R)
                if w_ and len(R) > 1 and at.get(R[:1].upper()) == w_ and w_ not in VL:
                    lb = self.vol_label(R)
                    if lb: VL[w_] = lb; ch = True
            if ch: self.cfg.set('vol_label', VL)
            for R in roots:
                if len(R) < 2 or R[1] != ':': continue
                X = R[:1].upper(); want = vol.get(R)
                if not want: continue
                if X in at:
                    sn = at[X]
                    if sn == want or self._busy_letter(X): continue
                    self.park_root(R, want, (self.cfg.get('vol_label') or {}).get(want, ''), want, only_gone=True)
                    left = (self.db.one('SELECT COUNT(*) FROM files WHERE root=? AND missing=0', (R,)) or [0])[0]
                    cur = [str(x) for x in self.cfg.get('roots') or []]; v2 = dict(self.cfg.get('root_vol') or {})
                    if left >= 20 and sn not in known:                                 # 這顆新的已經掃進來了（你按過重新掃描）：這個代號改認它
                        v2[R] = sn; self.cfg.set('root_vol', v2); out.append(f'{R} 改認現在這顆（序號 {sn}），原本那顆的紀錄已隔離')
                    else:
                        self.cfg.set('roots', [x for x in cur if x != R]); v2.pop(R, None); self.cfg.set('root_vol', v2); self.offline.pop(R, None)
                        out.append(f'{X}: 現在接的是另一顆硬碟（序號 {sn}），原本那顆的紀錄已隔離；新的這顆要整理的話，請按「加入硬碟／資料夾」')
                else:
                    t_off = self.offline.get(R)
                    if t_off and (force or time.time() - t_off > self.PARK_DELAY) and not self._busy_letter(X):
                        self.park_root(R, want, (self.cfg.get('vol_label') or {}).get(want, ''), want, only_gone=False)
                        cur = [str(x) for x in self.cfg.get('roots') or []]; v2 = dict(self.cfg.get('root_vol') or {})
                        self.cfg.set('roots', [x for x in cur if x != R]); v2.pop(R, None); self.cfg.set('root_vol', v2); self.offline.pop(R, None)
                        out.append(f'{R} 拔掉超過 {self.PARK_DELAY // 60} 分鐘：紀錄先隔離（預覽圖、分級都留著），接回來會自動套回去')
            for key, I in list((self.cfg.get('parked') or {}).items()):
                sn = I.get('serial') or ''
                if sn and sn in L and not self._busy_letter(L[sn]):
                    J_ = self._pack_newer(L[sn], sn)
                    if J_:                                                       # V0.2.27 這段時間在另一台電腦用過：用硬碟上比較新的
                        r = self._pack_refresh(L[sn], sn, J_, key)
                        if r.get('message'): out.append(r['message'])
                        continue
                    r = self.unpark(key, L[sn] + ':' + str(I.get('root') or '')[2:] or L[sn] + ':\\', force=True)
                    if r.get('message'): out.append(r['message'])
            if out: self.remap_msg = '；'.join(out)
        except Exception: self.log.err('硬碟隔離／套回')
        finally: lk.release()
        return out

    def iso_list(self):
        """🗄 讀不到的（隔離中）：拔掉的硬碟＋找不到的資料夾，給資料夾樹顯示."""
        D = []
        for k, I in (self.cfg.get('parked') or {}).items():
            pre = f'|{k}|'; c = self.db.one('SELECT COUNT(*), SUM(th_state=2), SUM(size), SUM(length(grade)>0) FROM files WHERE substr(path,1,?)=?', (len(pre), pre))
            D.append({'kind': 'drive', 'key': k, 'label': I.get('label') or '', 'serial': I.get('serial') or '', 'root': I.get('root') or '', 'sub': str(I.get('root') or '')[2:].strip('\\/'),
                      't': I.get('t') or 0, 'n': int(c[0] or 0), 'th': int(c[1] or 0), 'bytes': int(c[2] or 0), 'gr': int(c[3] or 0)})
        off = set(self.offline or {}); G = []
        try:
            rows = self.db.q("SELECT folder, root, COUNT(*), SUM(th_state=2), SUM(size), SUM(length(grade)>0) FROM files WHERE missing=1 AND substr(path,1,1)!='|' AND (th_state=2 OR length(grade)>0 OR fav=1 OR cut_n>0 OR length(note)>0) GROUP BY folder ORDER BY folder LIMIT 3000")
            for r in rows:
                fd = str(r[0] or ''); rt = str(r[1] or '')
                if not fd or rt in off or (len(fd) > 1 and fd[1] == ':' and not os.path.exists(fd[:2] + '\\')): continue
                if os.path.isdir(fd): continue
                if G and (fd.lower() + '\\').startswith(G[-1]['folder'].lower() + '\\'):
                    g = G[-1]; g['n'] += int(r[2] or 0); g['th'] += int(r[3] or 0); g['bytes'] += int(r[4] or 0); g['gr'] += int(r[5] or 0); continue
                G.append({'kind': 'folder', 'folder': fd, 'n': int(r[2] or 0), 'th': int(r[3] or 0), 'bytes': int(r[4] or 0), 'gr': int(r[5] or 0)})
        except Exception: self.log.err('隔離清單：找不到的資料夾')
        G.sort(key=lambda g: -g['n'])
        return {'drives': D, 'folders': G[:150]}

    def _park_mig_v224(self):
        """V0.2.24 一次性：V0.2.23 已經把代號改認新硬碟的（舊那顆的紀錄還掛在同一個代號下）→ 從 LOG 找出原本的序號，把舊的紀錄隔離."""
        if self.cfg.get('park_v224'): return
        try:
            import re
            p = Path(self.log.d) / 'app_log.txt'; txt = ''
            if p.exists():
                with open(p, 'rb') as f:
                    f.seek(max(0, p.stat().st_size - 8 * 1024 * 1024)); txt = f.read().decode('utf-8', 'ignore')
            for m in re.finditer(r'💽 (.+?) 現在接的硬碟序號 ([0-9A-F]{8})（原本記的是 ([0-9A-F]{8})', txt):
                R, new, old = m.group(1), m.group(2), m.group(3)
                if R in [str(x) for x in self.cfg.get('roots') or []] and old not in (self.cfg.get('parked') or {}):
                    self.park_root(R, old, '', old, only_gone=True)
        except Exception: self.log.err('隔離：V0.2.23 舊硬碟紀錄')
        self.cfg.set('park_v224', True)

    # ---------- V0.2.26 💽 資料存在各硬碟自己身上（X:\VideoSIFT\.vsdata\）：預覽圖、分級、初剪紀錄…跟著硬碟走，接到哪台電腦都直接用
    PACK_EXCL = {'roots', 'root_vol', 'parked', 'vol_label', 'park_v224', 'th_dir', 'hz', 'perf_pos', 'cut_pending', 'e_fix', 'rv_pending', 'db_uid',
                 'pack_boot_done', 'ts_host', 'pack_skip', 'last_page', 'pc_uid', 'pc_name', 'pc_color', 'pack_t',
                 'copy_q', 'copy_src', 'rule_last', 'free_hist', 'privacy_on', 'auto_rule_log', 'last_file', 'share_t', 'sprint', 'week_seen', 'ver_seen', 'web_tokens_ro', 'web_pin_ro_hash', 'web_pin_ro_salt', 'web_tok_meta', 'up_ac_day'}   # V0.3.01 這台電腦自己的（影片編號、這台的硬碟代號）          # 換電腦時不帶過去的設定（跟這台電腦綁在一起的）
    PACK_FIELDS = ('path', 'folder', 'root', 'cv_src', 'cv_del', 'cv_out', 'th_dir')

    # ---------- V0.2.27 🖥 這台電腦是誰（兩台都裝 SortCut 時分得出來）＋ 硬碟在兩台之間換來換去時，不會用舊的蓋掉新的
    PC_COLORS = [('#4dc9ff', '藍'), ('#45d483', '綠'), ('#ffc94d', '黃'), ('#ff8a3d', '橘'), ('#ff4d6d', '紅'), ('#b48cff', '紫'), ('#ff6fb5', '粉'), ('#9aa5b3', '灰')]

    def pc_uid(self):
        u = self.cfg.get('pc_uid')
        if not u: u = binascii.hexlify(os.urandom(6)).decode(); self.cfg.set('pc_uid', u)
        return u

    def pc_name(self):
        return str(self.cfg.get('pc_name') or platform.node() or '這台電腦').strip()[:20]

    def pc_color(self):
        c = str(self.cfg.get('pc_color') or '')
        if c.startswith('#') and len(c) == 7: return c
        h = sum(ord(ch) for ch in (platform.node() or 'pc'))
        return self.PC_COLORS[h % len(self.PC_COLORS)][0]

    def _pack_json(self, X):
        try: return json.loads((self.pack_dir(X) / 'pack.json').read_text(encoding='utf-8'))
        except Exception: return None

    def _pack_t(self, sn):
        try: return float((self.cfg.get('pack_t') or {}).get(sn) or 0)
        except Exception: return 0.0

    def _pack_t_set(self, sn, t):
        try:
            D = dict(self.cfg.get('pack_t') or {}); D[sn] = float(t or 0); self.cfg.set('pack_t', D)
        except Exception: self.log.err('💽 記錄硬碟資料的時間')

    def _pack_mine(self, J):
        if not J: return True
        if J.get('pc_uid'): return J['pc_uid'] == self.pc_uid()
        return str(J.get('pc') or '') == platform.node()

    def _pack_newer(self, X, sn, J=None):
        """這顆硬碟上的資料是「另一台電腦」寫的、而且比這台手上的新 → 回傳 pack.json（要先讀進來，不能拿舊的蓋掉）."""
        J = J if J is not None else self._pack_json(X)
        if not J or self._pack_mine(J) or not (self.pack_dir(X) / 'files.sqlite3').exists(): return None
        t = float(J.get('t') or 0); mine = self._pack_t(sn)
        if not mine:                                                             # 第一次（還沒記過）：跟這台資料庫裡那顆硬碟最後改的時間比
            r = self.db.one("SELECT MAX(COALESCE(MAX(grade_t),0), COALESCE(MAX(th_t),0), COALESCE(MAX(viewed),0), COALESCE(MAX(cv_t),0)) FROM files WHERE upper(substr(path,1,2))=?", (X + ':',))
            mine = float((r or [0])[0] or 0)
            if t <= mine + 60: self._pack_t_set(sn, t); return None
        return J if t > mine + 1 else None

    def _park_bulk(self, R, key, label='', serial=''):
        """V0.2.27 一次把這個影片庫的紀錄全部隔離（很快：一個 SQL；開程式時硬碟沒接就馬上不顯示）."""
        R = str(R); X = R[:2].upper(); pre = f'|{key}|'
        sw = lambda c: f"CASE WHEN upper(substr({c},1,2))=? THEN ?||substr({c},3) ELSE {c} END"
        cols = ('path', 'folder', 'root', 'cv_src', 'cv_del', 'cv_out', 'th_dir')
        n = self.db.x('UPDATE OR IGNORE files SET ' + ', '.join(f'{c}={sw(c)}' for c in cols) + ", missing=1 WHERE root=? AND substr(path,1,1)!='|'",
                      tuple(x for _c in cols for x in (X, pre)) + (R,))
        P = dict(self.cfg.get('parked') or {}); old = P.get(key) or {}
        P[key] = {'root': old.get('root') or R, 'serial': serial or old.get('serial', ''), 'label': label or old.get('label', ''), 't': old.get('t') or time.time()}
        self.cfg.set('parked', P)
        try: self.info_c['t'] = 0
        except Exception: pass
        return n or 0

    def _pack_refresh(self, X, sn, J, key=None):
        """另一台電腦用過這顆硬碟（比較新）：這台的舊紀錄拿掉，換成硬碟上的（分級、預覽圖、初剪紀錄都照另一台的）."""
        X = str(X)[:1].upper(); pre = f'|{key}|' if key else None
        try:
            if pre:
                ids = [int(r[0]) for r in self.db.q('SELECT id FROM files WHERE substr(path,1,?)=?', (len(pre), pre))]
            else:
                ids = [int(r[0]) for r in self.db.q("SELECT id FROM files WHERE upper(substr(path,1,2))=?", (X + ':',))]
            for i in range(0, len(ids), 500):
                ph = ','.join(map(str, ids[i:i + 500]))
                for tb in ('people', 'cuts'): self.db.x(f'DELETE FROM {tb} WHERE file_id IN ({ph})')
                self.db.x(f'DELETE FROM files WHERE id IN ({ph})')
            if key:
                P = dict(self.cfg.get('parked') or {}); P.pop(key, None); self.cfg.set('parked', P)
            r = self.pack_import(X, sn, J)
            self.log.w(f'💽 {X}: 上次在「{J.get("pc_name") or J.get("pc") or "另一台電腦"}」用過（比這台新）：這台的舊紀錄 {len(ids):,} 筆換成硬碟上的 {r.get("n", 0):,} 筆')
            roots = [str(x) for x in self.cfg.get('roots') or [] if str(x)[:2].upper() == X + ':']
            if roots and not self.scan(roots): self._pk_rescan = sorted(set(getattr(self, '_pk_rescan', []) or []) | set(roots))
            return r
        except Exception: self.log.err(f'💽 {X}: 換成另一台電腦的紀錄'); return {'ok': False}

    def _pack_startup(self):
        """V0.2.27 每次打開程式：一瞬間看每顆硬碟在不在（讀硬碟序號＋X:\\VideoSIFT\\.vsdata\\pack.json 這個小檔）.
        不在的 → 紀錄馬上隔離（不顯示，留著，接回來自動套回）；在、但另一台電腦用過比較新 → 這台的舊紀錄先藏起來，背景換成硬碟上的."""
        if not IS_WIN or os.environ.get('VIDEOSIFT_SELFTEST'): return
        t0 = time.time(); L = self.vol_letters(); at = {v: k for k, v in L.items()}
        roots = [str(x) for x in self.cfg.get('roots') or []]; vol = dict(self.cfg.get('root_vol') or {}); VL = self.cfg.get('vol_label') or {}
        gone, newer = [], []; self._pk_refresh_q = []
        for R in roots:
            if len(R) < 2 or R[1] != ':': continue
            want = vol.get(R); X = R[:1].upper()
            if not want: continue
            if at.get(X) == want:
                if any(q[0] == X for q in self._pk_refresh_q): continue
                J = self._pack_newer(X, want)
                if J:
                    key = f'{want}~old'
                    for R2 in [r for r in roots if r[:1].upper() == X]: self._park_bulk(R2, key, VL.get(want, ''), want)
                    self._pk_refresh_q.append((X, want, J, key)); newer.append(f'{X}:')
                continue
            if want in L: continue                                               # 換了代號：之後的檢查會搬過去
            n = self._park_bulk(R, want, VL.get(want, ''), want); gone.append(f'{R}（{n:,} 筆）')
            self.cfg.set('roots', [x for x in (self.cfg.get('roots') or []) if str(x) != R]); v2 = dict(self.cfg.get('root_vol') or {}); v2.pop(R, None); self.cfg.set('root_vol', v2)
        msg = []
        if gone: msg.append('沒接的硬碟先不顯示：' + '、'.join(gone) + '（紀錄留著，接回來自動套回）')
        if newer: msg.append('另一台電腦用過、比較新：' + '、'.join(newer) + '（讀硬碟上的紀錄中）')
        self.log.w(f'💽 開程式檢查硬碟（{time.time() - t0:.2f} 秒）：' + ('；'.join(msg) if msg else '每顆都在、都是最新的'))
        if msg: self.remap_msg = '；'.join(msg)

    def disk_warn(self):
        """V0.2.32 ⚠ 空間不足：影片庫的硬碟剩不到設定的 GB（🧪 disk_warn）→ [{'d','label','free','total'}]；1 分鐘查一次，第一次不足時記 LOG."""
        L = self.cfg.get('lab') or {}
        if not L.get('disk_warn'): return []
        C = getattr(self, '_dw_c', None)
        if C and time.time() - C[0] < 60: return C[1]
        thr = float(L.get('disk_warn_gb') or 50) * 1e9; out = []; seen = set()
        for r in self.cfg.get('roots') or []:
            r = str(r); X = r[:2].upper() if len(r) > 1 and r[1] == ':' else r
            if X in seen: continue
            seen.add(X)
            try:
                du = shutil.disk_usage(X + '\\' if len(X) == 2 else X)
                _per, dfull = self.free_trend((self.cfg.get('free_hist') or {}).get(X[:1])) if len(X) == 2 else (None, None)   # V0.2.92 照速度 3 天內會滿也提醒
                if du.free < thr or (dfull is not None and dfull <= 3):
                    out.append({'d': X, 'label': self.vol_label(X + '\\') if len(X) == 2 else '', 'free': du.free, 'total': du.total, 'days_full': dfull})
            except Exception: pass
        old = {x['d'] for x in (C[1] if C else [])}
        for x in out:
            if x['d'] not in old: self.log.w(f'⚠ 空間不足：{x["d"]}（{x["label"] or "沒有名稱"}）只剩 {fmt_b(x["free"])}' + (f'，照最近的速度大約 {x["days_full"]:g} 天會滿' if x.get('days_full') is not None else '') + f'（設定：少於 {thr / 1e9:.0f} GB 就提醒）')
        self._dw_c = (time.time(), out); return out

    @staticmethod
    def creator_key(name):
        """V0.2.33 👥 從檔名猜作者／主播：「D01-林熹熹_20260531…」→ 林熹熹；「小宅宅_2026…」→ 小宅宅；「hhd800.com@PRED-123」→ PRED."""
        st = os.path.splitext(str(name or ''))[0]
        if '@' in st: st = st.split('@', 1)[1]
        m = re.match(r'^([A-Za-z]{2,6})-?\d{2,5}', st)
        if m: return m.group(1).upper()
        st = re.sub(r'^[A-Za-z]\d{1,3}[-_ ]+', '', st)                            # D01- 這種前綴
        st = re.sub(r'[^\w\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]+', '_', st)   # 表情符號、符號 → _
        for t in [x for x in st.split('_') if x]:
            if re.fullmatch(r'\d{6,}|\d{1,5}|(19|20)\d{2}[-.]?\d{2}[-.]?\d{2}.*|copy|VID|IMG|Screenrecorder|InShot|vid|img', t, re.I): continue
            return t[:20]
        return '（其他）'

    def creator_stats(self):
        """V0.2.33 👥 每個作者幾部、多大、分級了多少（沒歸檔、沒刪的）."""
        D = {}
        for r in self.db.q("SELECT name, size, grade, still, up_t, pub_t FROM files WHERE missing=0 AND arch=''"):
            k = self.creator_key(r['name']); d = D.setdefault(k, {'k': k, 'n': 0, 'bytes': 0, 'graded': 0, 'S': 0, 'A': 0, 'E': 0, 'F': 0, '_sv': 0.0, '_sn': 0, 'up': 0, 'last_up': 0, 'pub': 0, 'last_pub': 0})
            if float(r['up_t'] or 0) > 0: d['up'] += 1; d['last_up'] = max(d['last_up'], float(r['up_t']))   # V0.3.75 📤 上傳過幾部、最後一次
            if float(r['pub_t'] or 0) > 0: d['pub'] += 1; d['last_pub'] = max(d['last_pub'], float(r['pub_t']))   # V0.4.40 ✅ 發佈過幾部
            d['n'] += 1; d['bytes'] += int(r['size'] or 0); g = r['grade'] or ''
            if g: d['graded'] += 1; d[g] = d.get(g, 0) + 1
            if (r['still'] if r['still'] is not None else -1) >= 0: d['_sv'] += float(r['still']); d['_sn'] += 1   # V0.3.19 😴 平均靜止
        for d in D.values(): d['still'] = round(d['_sv'] / d['_sn'], 3) if d['_sn'] else None; d['still_n'] = d.pop('_sn'); d.pop('_sv')
        return sorted(D.values(), key=lambda x: -x['bytes'])

    def review_report(self, days=14):
        """V0.2.35 📈 分級報表：每天分級幾部（S/A/E/F）、剪了幾段、轉檔省了多少、清掉待刪多少."""
        t0 = time.time() - days * 86400; D = {}
        day = lambda c: f"date({c},'unixepoch','localtime')"
        def slot(d): return D.setdefault(d, {'d': d, 'S': 0, 'A': 0, 'E': 0, 'F': 0, 'cuts': 0, 'cv_n': 0, 'cv_save': 0, 'purge_b': 0, 'purge_n': 0, 'up': 0, 'pub': 0})
        for r in self.db.q(f"SELECT {day('grade_t')} d, grade, COUNT(*) FROM files WHERE grade_t>=? AND grade!='' GROUP BY d, grade", (t0,)):
            slot(r[0])[r[1]] = int(r[2])
        for r in self.db.q(f"SELECT {day('t')} d, COUNT(*) FROM cuts WHERE t>=? AND state=1 GROUP BY d", (t0,)): slot(r[0])['cuts'] = int(r[1])
        for r in self.db.q(f"SELECT {day('cv_t')} d, COUNT(*), TOTAL(MAX(cv_osz-cv_nsz,0)) FROM files WHERE cv_state=3 AND cv_t>=? GROUP BY d", (t0,)):
            x = slot(r[0]); x['cv_n'] = int(r[1]); x['cv_save'] = int(r[2] or 0)
        for r in self.db.q(f"SELECT {day('t')} d, COUNT(*), TOTAL(size) FROM oplog WHERE kind='purge' AND t>=? GROUP BY d", (t0,)):
            x = slot(r[0]); x['purge_n'] = int(r[1]); x['purge_b'] = int(r[2] or 0)
        try:                                                                    # V0.3.77 📤 每天上傳幾部
            for r in self.db.q(f"SELECT {day('up_t')} d, COUNT(*) FROM files WHERE up_t>=? GROUP BY d", (t0,)): slot(r[0])['up'] = int(r[1])
            for r in self.db.q(f"SELECT {day('pub_t')} d, COUNT(*) FROM files WHERE pub_t>=? GROUP BY d", (t0,)): slot(r[0])['pub'] = int(r[1])   # V0.4.25 ✅
        except Exception: pass
        L = []
        for i in range(days - 1, -1, -1):
            d = time.strftime('%Y-%m-%d', time.localtime(time.time() - i * 86400)); L.append(slot(d))
        for x in L: x['graded'] = x['S'] + x['A'] + x['E'] + x['F']
        tot = lambda k, n: sum(x[k] for x in L[-n:])
        return {'days': L, 'today': L[-1], 'week': {k: tot(k, 7) for k in ('graded', 'S', 'A', 'E', 'F', 'cuts', 'cv_n', 'cv_save', 'purge_b', 'purge_n')},
                'left': int((self.db.one("SELECT COUNT(*) FROM files WHERE missing=0 AND arch='' AND grade='' AND th_state=2") or [0])[0] or 0), **self._report_pace(L)}

    def _report_pace(self, L):
        """V0.2.50 速度：最近 7 天平均每天分級幾部、照這速度剩下的幾天分完、幾點最常審（14 天，每小時）."""
        try:
            wk = L[-7:]; act = [x['graded'] for x in wk]; pace = sum(act) / 7.0
            nogo = int((self.db.one("SELECT COUNT(*) FROM files WHERE missing=0 AND arch='' AND grade=''") or [0])[0] or 0)
            H = [0] * 24; t0 = time.time() - 14 * 86400
            for r in self.db.q("SELECT CAST(strftime('%H', grade_t, 'unixepoch', 'localtime') AS INTEGER) h, COUNT(*) n FROM files WHERE grade_t>=? AND grade!='' GROUP BY h", (t0,)):
                if r['h'] is not None and 0 <= int(r['h']) < 24: H[int(r['h'])] = int(r['n'])
            best = max(range(24), key=lambda i: H[i]) if any(H) else -1
            T_ = [r[0] for r in self.db.q("SELECT grade_t FROM files WHERE grade_t>=? AND grade!='' ORDER BY grade_t", (time.time() - 7 * 86400,))]   # V0.3.32 ⏱ 每部大概花幾秒（連續分的間隔，10 分鐘以上不算）
            G_ = sorted(b_ - a_ for a_, b_ in zip(T_, T_[1:]) if 0.5 < b_ - a_ < 600)
            per_ = round(G_[len(G_) // 2], 1) if len(G_) >= 5 else None
            AR_ = sum(len(h.get('ids') or []) for h in (self.cfg.get('auto_rule_log') or []) if float(h.get('t') or 0) >= time.time() - 7 * 86400)   # V0.3.42
            St_ = self.cfg.get('guess_stat') or {}
            U7_ = self.db.one('SELECT COUNT(*) FROM files WHERE up_t>=?', (time.time() - 7 * 86400,))[0]   # V0.3.60 📤 上傳
            UL_ = self.db.one("SELECT COUNT(*) FROM files WHERE grade IN ('S','A') AND up_t<=0 AND missing=0")[0] if (self.cfg.get('lab') or {}).get('copy_to') else 0
            return {'up_7d': int(U7_ or 0), 'up_left': int(UL_ or 0), 'auto_7d': AR_, 'guess_acc': (round(St_['ok'] * 100 / St_['n']) if St_.get('n') else None), 'guess_n': int(St_.get('n') or 0), 'per_file': per_, 'pace': round(pace, 1), 'ungraded': nogo, 'eta_days': (round(nogo / pace, 1) if pace > 0 else None), 'hours': H, 'best_h': best, 'active_days': sum(1 for x in act if x)}
        except Exception:
            self.log.err('報表速度'); return {'pace': 0, 'ungraded': 0, 'eta_days': None, 'hours': [0] * 24, 'best_h': -1, 'active_days': 0}

    def quick_find(self, q, n=25):
        """V0.2.30 ⌘ 指令面板：檔名／資料夾快速找（每個字都要有，不分大小寫）."""
        W_ = [w for w in re.split(r'\s+', str(q or '').strip().lower()) if w][:6]
        if not W_: return {'files': [], 'folders': []}
        cond = ' AND '.join(['instr(lower(name), ?)>0'] * len(W_))
        F = [dict(r) for r in self.db.q(f"SELECT id, name, folder, size, dur, grade FROM files WHERE missing=0 AND {cond} ORDER BY size DESC LIMIT ?", (*W_, int(n)))]
        condf = ' AND '.join(['instr(lower(folder), ?)>0'] * len(W_))
        D = [dict(r) for r in self.db.q(f"SELECT folder, COUNT(*) n FROM files WHERE missing=0 AND arch='' AND {condf} GROUP BY folder ORDER BY n DESC LIMIT 12", tuple(W_))]
        return {'files': F, 'folders': D}

    def pack_dir(self, X):
        return Path(f'{str(X)[:1].upper()}:\\') / ARCH_BASE / PACK_DIR

    def db_uid(self):
        u = self.cfg.get('db_uid')
        if not u: u = binascii.hexlify(os.urandom(3)).decode(); self.cfg.set('db_uid', u)
        return u

    @staticmethod
    def _hide(p):
        if not IS_WIN: return
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(ctypes.c_wchar_p(str(p)), 0x2)
        except Exception: pass

    def _pack_ready(self, X):
        """這顆硬碟可以放資料嗎：有接、有序號、影片庫在上面、剩 3 GB 以上、寫得進去（1 分鐘檢查一次）."""
        X = str(X)[:1].upper(); C = getattr(self, '_pk_ok', None)
        if C is None: C = self._pk_ok = {}
        v = C.get(X)
        if v and time.time() - v[0] < 60: return v[1]
        ok = False
        try:
            if self.cfg.get('drive_pack') is not False and os.path.exists(X + ':\\') and self.vol_serial(X + ':\\') \
                    and any(str(r)[:1].upper() == X and len(str(r)) > 1 and str(r)[1] == ':' for r in self.cfg.get('roots') or []):
                fb = free_bytes(X + ':\\')
                if fb is not None and fb > 3e9:
                    pd = self.pack_dir(X); new = not pd.exists(); (pd / 'thumbs').mkdir(parents=True, exist_ok=True)
                    if new: self._hide(pd)
                    ok = True
        except Exception: ok = False
        C[X] = (time.time(), ok); return ok

    def th_out_dir(self, fid, path):
        """預覽圖要放哪：影片所在的那顆硬碟（X:\\VideoSIFT\\.vsdata\\thumbs\\）；那顆不能放才放這台電腦的 Data\\thumbs."""
        fid = int(fid); p = str(path or '')
        try:
            if IS_WIN and len(p) > 1 and p[1] == ':' and self._pack_ready(p[0]):
                return self.pack_dir(p[0]) / 'thumbs' / f'{fid % 100:02d}' / f'{fid}-{self.db_uid()}'
        except Exception: pass
        return self.thumbs_root() / f'{fid % 100:02d}' / str(fid)

    def th_owned(self, td, fid=None):
        """這個預覽圖資料夾是 SortCut 自己做的（可以刪）."""
        try:
            s = str(td or '')
            if not s: return False
            nm = Path(s).name
            if fid is not None and (nm == str(int(fid)) or nm.startswith(f'{int(fid)}-')): return True
            k = path_key(s)
            return k.startswith(path_key(self.thumbs_root()) + os.sep) or (os.sep + PACK_DIR + os.sep + 'thumbs' + os.sep) in k
        except Exception: return False

    def _pk_sql(self):
        return "th_state=2 AND length(th_dir)>0 AND instr(lower(th_dir), ?)=0 AND missing=0 AND substr(path,2,1)=':'"

    def pack_left(self):
        """還有幾部的預覽圖在這台電腦（影片所在的硬碟可以放的）、已經放到硬碟上的幾部."""
        try:
            tag = (os.sep + PACK_DIR + os.sep).lower()
            done = int((self.db.one("SELECT COUNT(*) FROM files WHERE instr(lower(th_dir), ?)>0", (tag,)) or [0])[0] or 0)
            L = [X for X in {str(r)[:1].upper() for r in self.cfg.get('roots') or [] if len(str(r)) > 1 and str(r)[1] == ':'} if self._pack_ready(X)]
            left = 0
            if L:
                left = int((self.db.one(f"SELECT COUNT(*) FROM files WHERE {self._pk_sql()} AND upper(substr(path,1,1)) IN ({','.join('?' * len(L))})", (tag, *L)) or [0])[0] or 0)
            return done, left
        except Exception: return 0, 0

    def _pack_move_step(self, limit=60):
        """把這台電腦上的預覽圖搬到影片所在的硬碟（先複製、資料庫改好、5 分鐘後才刪本機的那份，畫面正在看的不會壞）."""
        tag = (os.sep + PACK_DIR + os.sep).lower()
        L = [X for X in {str(r)[:1].upper() for r in self.cfg.get('roots') or [] if len(str(r)) > 1 and str(r)[1] == ':'} if self._pack_ready(X)]
        if not L: return 0
        rows = self.db.q(f"SELECT id, path, th_dir FROM files WHERE {self._pk_sql()} AND upper(substr(path,1,1)) IN ({','.join('?' * len(L))}) ORDER BY path LIMIT ?", (tag, *L, int(limit)))
        n = 0; DQ = getattr(self, '_pk_del', None)
        if DQ is None: DQ = self._pk_del = deque()
        for r in rows:
            if not self.alive() or self.bg_hold('pack'): break
            fid = int(r['id'])
            if fid in self.th_active: continue
            src = Path(r['th_dir'])
            if not src.is_dir():                                                  # 本機的預覽圖不見了：之後重做
                self.db.x("UPDATE files SET th_state=0, th_dir='' WHERE id=? AND th_dir=?", (fid, r['th_dir'])); continue
            dst = self.th_out_dir(fid, r['path'])
            if path_key(dst).startswith(path_key(self.thumbs_root())): continue
            tmp = dst.with_name(dst.name + '.tmp')
            try:
                shutil.rmtree(tmp, ignore_errors=True); dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, tmp)
                if sum(1 for _ in tmp.glob('s*.jpg')) < sum(1 for _ in src.glob('s*.jpg')): raise IOError('複製不完整')
                shutil.rmtree(dst, ignore_errors=True); os.replace(str(tmp), str(dst))
                if self.db.x('UPDATE files SET th_dir=? WHERE id=? AND th_dir=?', (str(dst), fid, r['th_dir'])): DQ.append((time.time(), str(src))); n += 1
                else: shutil.rmtree(dst, ignore_errors=True)
                self.bg_mark('pack', Path(r['path']).name)
            except Exception as ex:
                shutil.rmtree(tmp, ignore_errors=True)
                self.log.w(f'💽 預覽圖搬到硬碟：{r["path"]} 沒搬成（{type(ex).__name__}: {ex}），之後再試'); self._pk_ok = {}; break
            time.sleep(0.02)
        while DQ and time.time() - DQ[0][0] > 300:                             # 本機那份：5 分鐘後才刪（畫面上可能還開著）
            _t, p = DQ.popleft()
            if self.th_owned(p): shutil.rmtree(p, ignore_errors=True)
        return n

    def _pack_sweep_local(self):
        """搬完後：這台電腦 Data\\thumbs 裡、已經放到硬碟上的那些（熱更新時還沒刪到的）清掉."""
        try:
            tag = (os.sep + PACK_DIR + os.sep).lower(); root = self.thumbs_root(); n = 0
            have = {int(r[0]) for r in self.db.q("SELECT id FROM files WHERE instr(lower(th_dir), ?)>0", (tag,))}
            wait = {path_key(p) for _t, p in list(getattr(self, '_pk_del', None) or [])}
            if not root.is_dir(): return 0
            for sub in root.iterdir():
                if not sub.is_dir(): continue
                for d in sub.iterdir():
                    if d.is_dir() and d.name.isdigit() and int(d.name) in have and path_key(d) not in wait and int(d.name) not in self.th_active:
                        shutil.rmtree(d, ignore_errors=True); n += 1
            if n: self.log.w(f'💽 這台電腦上已經搬到硬碟的預覽圖清掉 {n:,} 份')
            return n
        except Exception: self.log.err('💽 清本機預覽圖'); return 0

    def _pack_sig(self, X):
        r = self.db.one("SELECT COUNT(*), TOTAL(th_t), TOTAL(grade_t), TOTAL(viewed), TOTAL(cut_n), TOTAL(cv_t), TOTAL(fav), TOTAL(missing), TOTAL(th_state), TOTAL(probed), "
                        "TOTAL(length(grade)+length(note)+length(tag)+length(path)+length(arch)+length(th_dir)) FROM files WHERE upper(substr(path,1,2))=?", (X + ':',))
        return tuple(round(float(x or 0), 3) for x in r)

    def pack_export(self, X, why=''):
        """把這顆硬碟的資料寫到它自己身上：files.sqlite3（路徑不含代號）＋ pack.json ＋ global\\（設定、經驗值）."""
        X = str(X)[:1].upper(); pd = self.pack_dir(X); sn = self.vol_serial(X + ':\\')
        if not sn: return {'ok': False}
        J0 = self._pack_newer(X, sn)
        if J0:                                                                   # V0.2.27 硬碟上的是另一台電腦寫的、比較新：不能蓋掉，先讀進來
            self.log.w(f'💽 {X}: 上的資料是「{J0.get("pc_name") or J0.get("pc")}」寫的、比這台新：不寫入，改成先讀進來')
            Q = getattr(self, '_pk_refresh_q', None)
            if Q is None: Q = self._pk_refresh_q = []
            if not any(q[0] == X for q in Q): Q.append((X, sn, J0, None))
            return {'ok': False, 'newer': True}
        pd.mkdir(parents=True, exist_ok=True)
        cols = [r[1] for r in self.db.q('PRAGMA table_info(files)')]
        rows = self.db.q("SELECT * FROM files WHERE upper(substr(path,1,2))=?", (X + ':',))
        if not rows: return {'ok': False}
        sw = lambda v: ('@:' + v[2:]) if isinstance(v, str) and len(v) > 1 and v[:2].upper() == X + ':' else v
        fi = {c: i for i, c in enumerate(cols)}
        ids = [int(r['id']) for r in rows]
        tmp = pd / 'files.tmp.sqlite3'; final = pd / 'files.sqlite3'
        try: tmp.unlink()
        except Exception: pass
        con = sqlite3.connect(str(tmp))
        try:
            con.execute('CREATE TABLE files(' + ', '.join(f'"{c}"' for c in cols) + ')')
            con.executemany(f'INSERT INTO files VALUES({",".join("?" * len(cols))})',
                            [tuple(sw(v) if cols[i] in self.PACK_FIELDS else v for i, v in enumerate(tuple(r))) for r in rows])
            for tb in ('people', 'cuts'):
                tc = [r[1] for r in self.db.q(f'PRAGMA table_info({tb})')]
                con.execute(f'CREATE TABLE {tb}(' + ', '.join(f'"{c}"' for c in tc) + ')')
                R = []
                for i in range(0, len(ids), 500):
                    R += [tuple(sw(v) if tc[j] == 'out' else v for j, v in enumerate(tuple(x))) for x in self.db.q(f'SELECT * FROM {tb} WHERE file_id IN ({",".join(map(str, ids[i:i + 500]))})')]
                if R: con.executemany(f'INSERT INTO {tb} VALUES({",".join("?" * len(tc))})', R)
            con.commit()
        finally: con.close()
        os.replace(str(tmp), str(final))
        roots = ['@:' + str(r)[2:] for r in self.cfg.get('roots') or [] if str(r)[:2].upper() == X + ':']
        old = {}
        try: old = json.loads((pd / 'pack.json').read_text(encoding='utf-8'))
        except Exception: pass
        tag = (os.sep + PACK_DIR + os.sep).lower()
        nth = sum(1 for r in rows if tag in str(r['th_dir'] or '').lower())
        J = {'v': 1, 'uid': old.get('uid') or binascii.hexlify(os.urandom(8)).decode(), 'serial': sn, 'label': self.vol_label(X + ':\\') or (self.cfg.get('vol_label') or {}).get(sn, ''),
             't': time.time(), 'pc': platform.node(), 'pc_uid': self.pc_uid(), 'pc_name': self.pc_name(), 'app': self.version, 'roots': roots, 'n': len(rows), 'th': nth,
             'graded': sum(1 for r in rows if r['grade'])}
        (pd / 'pack.tmp.json').write_text(json.dumps(J, ensure_ascii=False, indent=1), encoding='utf-8'); os.replace(str(pd / 'pack.tmp.json'), str(pd / 'pack.json'))
        self._pack_t_set(sn, J['t'])
        try:                                                                     # 共用的設定、轉檔經驗：每顆硬碟都放一份（換電腦時拿最新的那份）
            gd = pd / 'global'; gd.mkdir(exist_ok=True)
            for nm in ('settings.json', 'tq_learn.json', 'brtest_history.json'):
                f = self.data / nm
                if f.exists(): shutil.copy2(str(f), str(gd / (nm + '.tmp'))); os.replace(str(gd / (nm + '.tmp')), str(gd / nm))
        except Exception: self.log.err('💽 共用設定寫到硬碟')
        S = getattr(self, '_pk_exp', None)
        if S is None: S = self._pk_exp = {}
        S[X] = (time.time(), self._pack_sig(X))
        self.log.w(f'💽 資料寫到 {X}:（{J["label"] or sn}）：{len(rows):,} 部的紀錄（預覽圖在硬碟上的 {nth:,} 部）' + (f'　{why}' if why else ''))
        return {'ok': True, 'n': len(rows), 'th': nth}

    def pack_export_due(self, force=False, why=''):
        """有改過的硬碟：每 10 分鐘寫一次（force＝現在全部寫）."""
        S = getattr(self, '_pk_exp', None)
        if S is None: S = self._pk_exp = {}
        out = []
        for X in sorted({str(r)[:1].upper() for r in self.cfg.get('roots') or [] if len(str(r)) > 1 and str(r)[1] == ':'}):
            try:
                if not self._pack_ready(X): continue
                last = S.get(X)
                if not force and last and time.time() - last[0] < 600: continue
                if last and last[1] == self._pack_sig(X): S[X] = (time.time(), last[1]); continue
                r = self.pack_export(X, why)
                if r.get('ok'): out.append(X)
            except Exception: self.log.err(f'💽 資料寫到 {X}:')
        if '關閉' not in str(why):                                                 # V0.5.69 💽 整理（FileCompare）的紀錄也寫到各硬碟（關程式時不寫，免得關很久）
            try:
                F_ = sys.modules.get('fc_app'); FE_ = getattr(F_, 'ENG', None) if F_ else None
                if type(FE_).__name__ == 'Engine':
                    import vs_fcpack
                    out += ['整理 ' + x for x in vs_fcpack.export(FE_, force=force, log=self.log.w, ver=self.version)]
            except Exception: self.log.err('💽 整理的紀錄寫到各硬碟')
        try:                                                                    # V0.3.30 🔄 新功能設定也跟著存（打開「自動同步」時，1 小時最多一次）
            if (self.cfg.get('lab') or {}).get('share_auto') and (force or time.time() - getattr(self, '_sx_t', 0) > 3600): self._sx_t = time.time(); self.share_export()
        except Exception: pass
        return out

    def pack_find(self):
        """接著的硬碟裡，有 SortCut 資料、但這台電腦還沒用過的：[(代號, 序號, pack.json)]."""
        out = []
        if not IS_WIN: return out
        vol = dict(self.cfg.get('root_vol') or {}); known = set(vol.values()) | set(self.cfg.get('parked') or {}) | set(self.cfg.get('pack_skip') or [])
        for sn, X in self.vol_letters().items():
            try:
                pj = self.pack_dir(X) / 'pack.json'
                if not pj.exists() or not (self.pack_dir(X) / 'files.sqlite3').exists(): continue
                J = json.loads(pj.read_text(encoding='utf-8'))
                if sn in known or str(J.get('serial') or '') in known: continue
                if (self.db.one("SELECT COUNT(*) FROM files WHERE upper(substr(path,1,2))=?", (X + ':',)) or [0])[0]: continue
                out.append((X, sn, J))
            except Exception: self.log.err(f'💽 讀 {X}: 的 SortCut 資料')
        return out

    def pack_import(self, X, sn, J=None):
        """另一台電腦帶過來的硬碟：把它身上的紀錄、預覽圖直接接上（不用重做），加進影片庫、重新掃描."""
        X = str(X)[:1].upper(); pd = self.pack_dir(X); J = J or {}
        src = sqlite3.connect(f'file:{(pd / "files.sqlite3").as_posix()}?mode=ro', uri=True); src.row_factory = sqlite3.Row
        try:
            mine = [r[1] for r in self.db.q('PRAGMA table_info(files)')]; ms = set(mine)
            sw = lambda v: (X + ':' + v[2:]) if isinstance(v, str) and v.startswith('@:') else v
            rows = [dict(r) for r in src.execute('SELECT * FROM files')]
            idmap = {}; n = 0; th_lost = 0
            with self.db.lock:
                cur = self.db.con.cursor()
                for r in rows:
                    oid = r.pop('id', None); d = {k: (sw(v) if k in self.PACK_FIELDS else v) for k, v in r.items() if k in ms and k != 'id'}
                    if int(d.get('th_state') or 0) in (1,): d['th_state'] = 0
                    if int(d.get('th_state') or 0) == 2 and not (d.get('th_dir') and os.path.isdir(d['th_dir'])): d['th_state'] = 0; d['th_dir'] = ''; th_lost += 1
                    if int(d.get('cv_state') or 0) == 2: d['cv_state'] = 1
                    if int(d.get('probed') or 0) == 2: d['probed'] = 0
                    ks = list(d)
                    cur.execute(f'INSERT OR IGNORE INTO files({",".join(ks)}) VALUES({",".join("?" * len(ks))})', [d[k] for k in ks])
                    if cur.rowcount:
                        n += 1
                        if oid is not None: idmap[int(oid)] = cur.lastrowid
                for tb in ('people', 'cuts'):
                    try:
                        mc = {r[1] for r in self.db.con.execute(f'PRAGMA table_info({tb})').fetchall()}
                        for x in src.execute(f'SELECT * FROM {tb}'):
                            x = dict(x); fid = idmap.get(int(x.get('file_id') or -1))
                            if fid is None: continue
                            x['file_id'] = fid; x.pop('id', None) if tb == 'cuts' else None
                            if tb == 'cuts': x['out'] = sw(x.get('out'))
                            ks = [k for k in x if k in mc]
                            cur.execute(f'INSERT OR IGNORE INTO {tb}({",".join(ks)}) VALUES({",".join("?" * len(ks))})', [x[k] for k in ks])
                    except Exception: self.log.err(f'💽 接上 {X}:：{tb}')
                self.db.con.commit()
        finally: src.close()
        R = [str(x) for x in self.cfg.get('roots') or []]; vol = dict(self.cfg.get('root_vol') or {}); add = []
        for r in (J.get('roots') or ['@:\\']):
            nr = X + ':' + str(r)[2:]
            if not any(path_key(nr) == path_key(x) for x in R): R.append(nr); add.append(nr)
            vol[nr] = sn
        self.cfg.set('roots', R); self.cfg.set('root_vol', vol); self._pk_ok = {}
        if J.get('label'):
            VL = dict(self.cfg.get('vol_label') or {}); VL[sn] = J['label']; self.cfg.set('vol_label', VL)
        try: self.info_c['t'] = 0
        except Exception: pass
        msg = (f'💽 接上 {X}:（{J.get("label") or sn}，上次在 {J.get("pc") or "?"} 用）：{n:,} 部的紀錄、分級、預覽圖直接沿用' +
               (f'（{th_lost:,} 部的預覽圖不在硬碟上，會重做）' if th_lost else '') + f'；影片庫加入 {"、".join(add) or "（原本就有）"}，重新掃描')
        self.log.w(msg); self.remap_msg = msg
        self._pack_t_set(sn, J.get('t') or time.time())
        S = getattr(self, '_pk_exp', None)
        if S is None: S = self._pk_exp = {}
        S[X] = (time.time(), self._pack_sig(X))
        return {'ok': True, 'n': n, 'roots': add, 'message': msg}

    def _pack_boot(self):
        """V0.2.26 新電腦第一次打開（還沒有影片庫、還沒有資料庫）：從接著的硬碟裡最新的那份 SortCut 資料，把設定、轉檔經驗拿回來."""
        try:
            if not IS_WIN or self.cfg.get('roots') or self.cfg.get('pack_boot_done') or (self.data / 'videosift.sqlite3').exists(): return
            best = None
            for sn, X in self.vol_letters().items():
                g = self.pack_dir(X) / 'global' / 'settings.json'
                try:
                    if g.exists() and (best is None or g.stat().st_mtime > best.stat().st_mtime): best = g
                except Exception: pass
            if best is None: self.cfg.set('pack_boot_done', True); return
            S = json.loads(best.read_text(encoding='utf-8'))
            with self.cfg.lock:
                for k, v in S.items():
                    if k not in self.PACK_EXCL: self.cfg.d[k] = v
            for nm in ('tq_learn.json', 'brtest_history.json'):
                f = best.parent / nm
                if f.exists() and not (self.data / nm).exists(): shutil.copy2(str(f), str(self.data / nm))
            self.cfg.set('pack_boot_done', True)
            self.log.w(f'💽 新電腦：設定、轉檔經驗從 {best.parent.parent} 拿回來了（手機網頁、PIN、轉檔設定照舊）')
        except Exception: self.log.err('💽 新電腦：拿回設定')

    def _ts_auto(self):
        """V0.2.26 換到新電腦：手機網頁有開的話，自動在 Tailscale 開好 SortCut 自己的 HTTPS 埠（不碰別的程式用的埠，不 reset）."""
        try:
            if not self.cfg.get('web_on') or os.environ.get('VIDEOSIFT_SELFTEST'): return
            host = platform.node()
            if self.cfg.get('ts_host') == host: return
            import vs_web
            port = int(self.cfg.get('web_port') or 8461); T = vs_web.tailscale_info(port)
            if not T.get('installed'): self.log.w('📱 新電腦：還沒裝 Tailscale（裝好、登入同一個帳號後，到設定 → 📱 手機網頁 按「📱 手機 App」）'); return
            if not T.get('serving'):
                rc, out = vs_web.tailscale_serve_on(port)
                self.log.w(f'📱 新電腦：Tailscale 開好 SortCut 的 HTTPS :{vs_web.https_port(port)} → {rc}：{(out or "")[-300:]}')
                T = vs_web.tailscale_info(port)
            if T.get('serving'):
                self.cfg.set('ts_host', host); self.log.w(f'📱 手機 App 網址：{T.get("url")}（新電腦的網址不一樣，手機要用這個重新打開、安裝一次）')
        except Exception: self.log.err('📱 新電腦：Tailscale')

    def _pack_loop(self):
        """💽 背景：接上別台電腦帶來的硬碟、把預覽圖搬到各硬碟、有改過就寫到硬碟上."""
        if os.environ.get('VIDEOSIFT_SELFTEST'): return
        for _ in range(3):
            if not self.alive(): return
            time.sleep(1)
        k = 0; t = None; moved = 0
        while self.alive():
            busy = False
            try:
                Q = getattr(self, '_pk_refresh_q', None) or []
                while Q:                                                         # V0.2.27 另一台電腦用過的硬碟：先換成硬碟上的紀錄
                    X_, sn_, J_, key_ = Q.pop(0); self._pack_refresh(X_, sn_, J_, key_)
                RS = getattr(self, '_pk_rescan', None)
                if RS and self.scan(RS): self._pk_rescan = []
                if k % 12 == 0:
                    for X, sn, J in self.pack_find():
                        try:
                            r = self.pack_import(X, sn, J)
                            if r.get('roots'): self.scan(r['roots']) or self.log.w('💽 接上的硬碟：目前正在掃描別的，掃完再按「🔄 重新掃描」')
                        except Exception: self.log.err(f'💽 接上 {X}:')
                if k == 6: self._ts_auto()
                if self.cfg.get('drive_pack') is not False and not self.bg_hold('pack'):
                    n = self._pack_move_step()
                    if n:
                        busy = True; moved += n
                        if t is None: t = self.task('pack', '💽 預覽圖搬到各硬碟')
                        d, left = self.pack_left(); t['pct'] = round(d * 100 / max(1, d + left)); t['msg'] = f'已搬 {moved:,} 部，還有 {left:,} 部'
                    elif t is not None:
                        self.done(t, 'done', f'搬好 {moved:,} 部'); t = None; moved = 0
                        self.pack_export_due(force=True, why='（預覽圖搬完）'); self.bg_mark('pack', '全部搬好、已寫到各硬碟（' + time.strftime('%H:%M') + '）')
                        self._pk_sweep_t = time.time() + 330
                    if getattr(self, '_pk_sweep_t', 0) and time.time() > self._pk_sweep_t: self._pk_sweep_t = 0; self._pack_sweep_local()
                    if k % 6 == 0 and not busy: self.pack_export_due()
            except Exception: self.log.err('💽 資料存到各硬碟'); time.sleep(10)
            self._pk_busy = busy; k += 1
            time.sleep(0.5 if busy else 5)

    # ---------- V0.2.28 🚚 整顆硬碟搬到另一顆（例如 K → F）：紀錄、分級、預覽圖都跟著過去；優先權低、限速、不吃 RAM／CPU，但一定會一直前進
    MV_SKIP = {'$recycle.bin', 'system volume information', 'recycler', 'found.000'}
    MV_SPEEDS = [(30, '慢：每秒 30 MB（幾乎感覺不到）'), (60, '中：每秒 60 MB（建議）'), (120, '快：每秒 120 MB'), (0, '不限速（硬碟多快就多快）')]

    def _mv(self):
        M = getattr(self, '_mv_st', None)
        if M is None: M = self._mv_st = {'run': False, 'phase': '', 'cur': '', 'speed_now': 0.0, 'total_b': 0, 'total_n': 0}
        return M

    def _mv_map(self, p, J):
        """來源路徑 → 目的路徑：VideoSIFT\\ 和 DELETE\\ 併到目的硬碟同名的資料夾（初剪、歸檔、待刪放在一起）；.vsdata 只搬預覽圖；其他放到 目的:\\<名稱>\\."""
        if J.get('folder'):                                                      # V0.2.34 只搬一個資料夾：資料夾底下 → 新位置底下
            Fo = str(J['folder']).rstrip('\\/'); To = str(J['to']).rstrip('\\/')
            if p.lower() == Fo.lower(): return To
            return (To + p[len(Fo):]) if p[:len(Fo) + 1].lower() == Fo.lower() + '\\' else None
        S = J['src'].rstrip('\\') + '\\'; D = J['dst'].rstrip('\\')
        if not p[:len(S)].lower() == S.lower(): return None
        rel = p[len(S):]; parts = rel.split('\\'); top = parts[0].lower()
        if top == ARCH_BASE.lower():
            if len(parts) > 1 and parts[1].lower() == PACK_DIR:
                return (D + '\\' + rel) if len(parts) > 3 and parts[2].lower() == 'thumbs' else None
            return D + '\\' + rel
        if top == DEL_DIR.lower(): return D + '\\' + rel
        return D + '\\' + J['name'] + '\\' + rel

    def move_plan(self, src, dst, J=None):
        """先算一下：有幾個檔、多大、目的硬碟空間夠不夠（只讀）."""
        S = str(src)[:1].upper() + ':\\'; n = 0; b = 0; skip = 0
        JJ = J if (J and J.get('folder')) else {'src': S, 'dst': str(dst)[:1].upper() + ':', 'name': 'x'}
        for dp, dn, fn in os.walk(J['folder'] if (J and J.get('folder')) else S):
            if path_key(dp) == path_key(S): dn[:] = [d for d in dn if d.lower() not in self.MV_SKIP]
            for f in fn:
                p = os.path.join(dp, f)
                try: sz = os.path.getsize(p)
                except Exception: skip += 1; continue
                if self._mv_map(p, JJ) is None: continue
                n += 1; b += sz
        free = free_bytes(str(dst)[:1].upper() + ':\\')
        return {'ok': True, 'n': n, 'bytes': b, 'free': free, 'skip': skip, 'fits': free is None or free > b + 5e9}

    def move_start(self, src, dst, name, speed=60):
        S = str(src)[:1].upper(); D = str(dst)[:1].upper(); name = re.sub(r'[\\/:*?"<>|]', '_', str(name or '').strip()) or f'{S}槽'
        if S == D: return {'ok': False, 'message': '來源和目的不能是同一顆'}
        if not os.path.exists(S + ':\\') or not os.path.exists(D + ':\\'): return {'ok': False, 'message': '有一顆硬碟沒接著'}
        J = self.cfg.get('disk_move') or {}
        if J.get('state') in ('run', 'pause'): return {'ok': False, 'message': f'已經在搬 {J.get("src")} → {J.get("dst")}（先停掉才能開新的）'}
        J = {'src': S + ':', 'dst': D + ':', 'name': name, 'speed': int(speed or 0), 'state': 'run', 't0': time.time(), 'done_b': 0, 'done_n': 0, 'fail': [], 'serial': self.vol_serial(S + ':\\')}
        if not self.root_of(D + ':\\' + name + '\\x'):                         # 目的地要在影片庫裡（紀錄才有地方掛）
            R = [str(x) for x in self.cfg.get('roots') or []]; nr = D + ':\\' + name; R.append(nr); self.cfg.set('roots', R)
            sn = self.vol_serial(D + ':\\')
            if sn: vol = dict(self.cfg.get('root_vol') or {}); vol[nr] = sn; self.cfg.set('root_vol', vol)
        self.cfg.set('disk_move', J); self.bg_set_pause('move', False, '開始搬硬碟')
        self.log.w(f'🚚 搬硬碟開始：{S}:\\ → {D}:\\{name}\\（VideoSIFT、DELETE 併到 {D}:\\ 同名資料夾；限速 {speed or "不限"} MB/秒）')
        self._mv_kick(); return {'ok': True, 'message': f'開始搬 {S}: → {D}:\\{name}（背景、低優先權）'}

    def move_ctl(self, a):
        J = dict(self.cfg.get('disk_move') or {})
        if not J: return {'ok': False, 'message': '沒有在搬'}
        if a == 'pause': self.bg_set_pause('move', True, '搬硬碟 暫停'); return {'ok': True}
        elif a == 'resume':
            if J.get('state') == 'pause': J['state'] = 'run'
            self.cfg.set('disk_move', J); self.bg_set_pause('move', False, '搬硬碟 繼續'); return {'ok': True}
        elif a == 'stop': J['state'] = 'stop'; self.log.w('🚚 搬硬碟：你按了停（做完手上這個檔就停，已經搬過去的照樣算數）')
        elif a == 'speed': pass
        elif a == 'clear' and J.get('state') in ('done', 'stop'): self.cfg.set('disk_move', {}); return {'ok': True}
        self.cfg.set('disk_move', J); return {'ok': True}

    def move_speed(self, v):
        J = dict(self.cfg.get('disk_move') or {})
        if J: J['speed'] = int(v or 0); self.cfg.set('disk_move', J)

    def move_view(self):
        J = dict(self.cfg.get('disk_move') or {}); M = self._mv()
        if not J: return {'on': False}
        el = max(1.0, time.time() - float(J.get('t0') or time.time())); tb = int(M.get('total_b') or 0); db = int(J.get('done_b') or 0)
        sp = float(M.get('speed_now') or 0); left = max(0, tb - db)
        return {'on': True, **{k: J.get(k) for k in ('src', 'dst', 'name', 'speed', 'state', 'done_n', 'done_b')}, 'fail': list(J.get('fail') or [])[-50:],
                'total_b': tb, 'total_n': int(M.get('total_n') or 0), 'phase': M.get('phase', ''), 'cur': M.get('cur', ''), 'speed_now': sp, 'run': bool(M.get('run')),
                'eta': (left / sp) if sp > 1e5 and left else 0, 'avg': db / el}

    def _mv_kick(self):
        if os.environ.get('VIDEOSIFT_SELFTEST') and not os.environ.get('VIDEOSIFT_MOVETEST'): return
        M = self._mv()
        if M.get('run'): return
        threading.Thread(target=self._mv_loop, name='VsDiskMove', daemon=True).start()

    def _mv_wait(self, J):
        """暫停中就等；回傳 False＝要停了。電腦很忙也不會停（只會在 _mv_copy 裡放慢），不會一直等不到."""
        while not self.stop_all:
            j = self.cfg.get('disk_move') or {}
            if j.get('state') == 'stop': return False
            if not self.bg_pause.get('move') and not self.bg_sched_hold('move'): return True
            self._mv()['speed_now'] = 0.0; time.sleep(1)
        return False

    def _mv_loop(self):
        L = getattr(self, '_mv_lock', None)
        if L is None: L = self._mv_lock = threading.Lock()
        if not L.acquire(timeout=600): return
        M = self._mv(); M['run'] = True
        try:
            J = dict(self.cfg.get('disk_move') or {})
            if not J or J.get('state') not in ('run', 'pause'): return
            S = J['src']; lane = self.root_lane(S + '\\')
            try:                                                                 # 這顆不再做預覽圖／讀資訊／轉檔（免得搬到一半被讀），手上的先做完
                import ctypes
                ctypes.windll.kernel32.SetThreadPriority(ctypes.windll.kernel32.GetCurrentThread(), -1)       # 低一點的 CPU 優先權（不是最低：才不會一直排不到）
            except Exception: pass
            hold = lambda: self.lane_hold.__setitem__(lane, (time.time() + 120, '🚚 搬硬碟中：這顆先不做預覽圖、轉檔'))
            hold(); t_w = time.time()
            while self._busy_letter(S) and time.time() - t_w < 1800 and not self.stop_all: M['phase'] = '等這顆硬碟手上的預覽圖／轉檔做完'; hold(); time.sleep(2)
            M['phase'] = '計算要搬多少'; P = self.move_plan(S, J['dst'], J); M['total_b'] = P['bytes'] + int(J.get('done_b') or 0); M['total_n'] = P['n'] + int(J.get('done_n') or 0)
            if not P['fits']:
                J['state'] = 'stop'; J.setdefault('fail', []).append(f'目的硬碟空間不夠：要 {fmt_b(P["bytes"])}，只剩 {fmt_b(P["free"])}'); self.cfg.set('disk_move', J)
                self.log.w(f'🚚 搬硬碟停下：{J["dst"]} 空間不夠（要 {fmt_b(P["bytes"])}，只剩 {fmt_b(P["free"])}）'); return
            self.log.w(f'🚚 搬硬碟：{S} 要搬 {P["n"]:,} 個檔、{fmt_b(P["bytes"])}')
            # ① 預覽圖資料夾（整個資料夾一起搬，資料庫的 th_dir 跟著改）
            td = Path(S + '\\') / ARCH_BASE / PACK_DIR / 'thumbs'
            if td.is_dir() and not J.get('folder'):
                M['phase'] = '搬預覽圖'
                for sub in sorted(td.iterdir()):
                    if not sub.is_dir(): continue
                    for d in sorted(sub.iterdir()):
                        if self.stop_all or not self._mv_wait(J): return
                        hold()
                        if not d.is_dir() or d.name.endswith('.tmp'): continue
                        self._mv_thumbdir(str(d), self._mv_map(str(d), J), J)
            # ② 其他所有檔（影片、圖片、文件…什麼都搬）
            M['phase'] = '搬檔案'; later = []
            pk_ = path_key(Path(S + '\\') / ARCH_BASE / PACK_DIR)
            for dp, dn, fn in os.walk(J['folder'] if J.get('folder') else S + '\\'):
                if path_key(dp) == path_key(S + '\\'): dn[:] = [x for x in dn if x.lower() not in self.MV_SKIP]
                if path_key(dp) == pk_ or path_key(dp).startswith(pk_ + os.sep): dn[:] = []; continue
                dn.sort(); fn.sort()
                for f in fn:
                    if self.stop_all or not self._mv_wait(J): return
                    hold(); s = os.path.join(dp, f); d = self._mv_map(s, J)
                    if d is None or s.lower().endswith('.vsmove'): continue
                    r = self._mv_file(s, d, J)
                    if r == 'later': later.append(s)
            for s in later:                                                      # 剛剛還在寫入的（10 分鐘內改過）：最後再試一次
                if self.stop_all or not self._mv_wait(J): return
                hold(); d = self._mv_map(s, J)
                if d and self._mv_file(s, d, J, force=True) == 'later': self._mv_fail(J, s, '一直有程式在寫這個檔（TikLive 錄影中？），先跳過')
            self._mv_finish(J)
        except Exception: self.log.err('🚚 搬硬碟')
        finally:
            M['run'] = False; M['speed_now'] = 0.0
            try: self.lane_hold.pop(self.root_lane(str((self.cfg.get('disk_move') or {}).get('src') or '') + '\\'), None)
            except Exception: pass
            L.release()

    def _mv_fail(self, J, p, why):
        j = dict(self.cfg.get('disk_move') or J); F = list(j.get('fail') or [])[-199:] + [f'{p}：{why}']; j['fail'] = F; self.cfg.set('disk_move', j)
        self.log.w(f'🚚 搬硬碟：{p} 沒搬（{why}）')

    def _mv_done(self, J, nbytes):
        j = dict(self.cfg.get('disk_move') or J); j['done_b'] = int(j.get('done_b') or 0) + int(nbytes); j['done_n'] = int(j.get('done_n') or 0) + 1
        self.cfg.d['disk_move'] = j                                              # 很頻繁：不每次都寫檔
        now = time.time()
        if now - getattr(self, '_mv_save_t', 0) > 30: self._mv_save_t = now; self.cfg.set('disk_move', dict(j, _t=now))

    def _mv_unique(self, d):
        if not os.path.exists(d): return d
        b, e = os.path.splitext(d); i = 2
        while os.path.exists(f'{b} ({i}){e}'): i += 1
        return f'{b} ({i}){e}'

    def _mv_copy(self, s, d, J):
        """一塊一塊複製（4 MB）：照設定限速；電腦很忙（CPU 超過上限）就再放慢一半，但不會停；每 64 MB 寫進硬碟一次（不會佔一堆記憶體）."""
        M = self._mv(); tmp = d + '.vsmove'; buf = 4 << 20; done = 0; t0 = time.time(); base = 0; last_sync = 0; win = [(t0, 0)]
        os.makedirs(os.path.dirname(d), exist_ok=True)
        try:
            with open(s, 'rb', buffering=0) as fi, open(tmp, 'wb', buffering=0) as fo:
                while True:
                    if self.stop_all: raise InterruptedError
                    if (self.cfg.get('disk_move') or {}).get('state') == 'stop' or self.bg_pause.get('move'):
                        if not self._mv_wait(J): raise InterruptedError
                        t0 = time.time(); base = done; win = [(t0, done)]
                    b = fi.read(buf)
                    if not b: break
                    fo.write(b); done += len(b)
                    if done - last_sync >= (64 << 20): os.fsync(fo.fileno()); last_sync = done
                    lim = float((self.cfg.get('disk_move') or {}).get('speed') or 0) * 1e6
                    if lim and float(self.perf.cpu or 0) >= float(self.cfg.get('cpu_max') or 90): lim *= 0.5
                    now = time.time(); win.append((now, done)); win = win[-30:]
                    M['speed_now'] = (win[-1][1] - win[0][1]) / max(0.2, win[-1][0] - win[0][0])
                    if lim:                                                  # 限速：看最近這段（約 120 MB）的平均，太快就睡一下
                        ahead = (win[-1][1] - win[0][1]) / lim - (now - win[0][0])
                        if ahead > 0: time.sleep(min(ahead, 2.0))
                os.fsync(fo.fileno())
            shutil.copystat(s, tmp); os.replace(tmp, d); return done
        except BaseException:
            try: os.remove(tmp)
            except Exception: pass
            raise

    @staticmethod
    def _mv_same(s, d):
        """搬過去的跟原本的一樣嗎：大小一樣＋抽 5 個地方（開頭、中間、結尾…）各 1 MB 逐位元比對."""
        try:
            n = os.path.getsize(s)
            if n != os.path.getsize(d): return False
            if n == 0: return True
            with open(s, 'rb') as a, open(d, 'rb') as b:
                for pos in sorted({0, n // 4, n // 2, 3 * n // 4, max(0, n - (1 << 20))}):
                    a.seek(pos); b.seek(pos)
                    if a.read(1 << 20) != b.read(1 << 20): return False
            return True
        except Exception: return False

    def _mv_file(self, s, d, J, force=False):
        M = self._mv(); M['cur'] = s
        try: st = os.stat(s)
        except Exception: return 'gone'
        if not force and time.time() - st.st_mtime < 600: return 'later'          # 10 分鐘內還在改：可能正在錄、正在寫，最後再搬
        fid = None
        try:
            r = self.db.one('SELECT id FROM files WHERE path=?', (s,)) or self.db.one('SELECT id FROM files WHERE lower(path)=lower(?)', (s,))
            fid = int(r[0]) if r else None
        except Exception: pass
        if fid is not None and (fid in self.th_active or fid in self.cv_active): return 'later'
        try:
            if os.path.exists(d) and self._mv_same(s, d): pass                    # 上次搬到一半（已經複製好、還沒刪原檔）
            else:
                d = self._mv_unique(d); n = self._mv_copy(s, d, J)
                if not self._mv_same(s, d):
                    try: os.remove(d)
                    except Exception: pass
                    self._mv_fail(J, s, '複製過去的檔案比對不一樣（硬碟有問題？），原檔沒動'); return 'fail'
        except InterruptedError: return 'stop'
        except Exception as ex: self._mv_fail(J, s, f'{type(ex).__name__}: {ex}'); return 'fail'
        if fid is not None:                                                      # 紀錄跟著過去（分級、預覽圖、初剪紀錄都沿用）
            try:
                dup = self.db.one('SELECT * FROM files WHERE path=? AND id!=?', (d, fid))
                if dup is not None:
                    if self._HIST(dict(dup)): self._mv_fail(J, s, f'目的地已經有一筆有紀錄的 {d}，兩筆都留著'); fid = None
                    else: self.db.x('DELETE FROM files WHERE id=?', (int(dup['id']),))
                if fid is not None:
                    rt = self.root_of(d) or ''
                    self.db.x('UPDATE files SET path=?, folder=?, name=?, root=?, missing=0 WHERE id=?', (d, os.path.dirname(d), os.path.basename(d), rt or os.path.dirname(d), fid))
                    if J.get('folder'): self._mv_thumb_follow(fid, d)
            except Exception: self.log.err(f'🚚 搬硬碟：改紀錄 {s}')
        try:
            try: os.chmod(s, 0o666)
            except Exception: pass
            os.remove(s)
        except Exception as ex: self._mv_fail(J, s, f'已經複製好，但原檔刪不掉（{ex}）：之後再刪'); return 'fail'
        self._mv_done(J, st.st_size); self.bg_mark('move', os.path.basename(s)); return 'ok'

    def _mv_thumb_follow(self, fid, d):
        """V0.2.34 搬資料夾：預覽圖也搬到新位置那顆硬碟（不然那顆拔走就沒預覽圖）."""
        try:
            r = self.db.one('SELECT th_dir FROM files WHERE id=?', (fid,)); td = str((r or [''])[0] or '')
            if not td or not os.path.isdir(td) or td[:2].upper() == d[:2].upper(): return
            nd = str(self.th_out_dir(fid, d))
            if nd[:2].upper() != d[:2].upper(): return
            tmp = nd + '.tmp'; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(os.path.dirname(nd), exist_ok=True); shutil.copytree(td, tmp)
            shutil.rmtree(nd, ignore_errors=True); os.replace(tmp, nd)
            if self.db.x('UPDATE files SET th_dir=? WHERE id=? AND th_dir=?', (nd, fid, td)) and self.th_owned(td, fid): shutil.rmtree(td, ignore_errors=True)
        except Exception: self.log.err(f'🚚 搬資料夾：預覽圖跟著搬 {fid}')

    def move_start_folder(self, folder, to, speed=60):
        """V0.2.34 只搬一個資料夾到別顆硬碟（紀錄、分級、預覽圖都跟著過去）."""
        Fo = os.path.normpath(str(folder)).rstrip('\\/'); To = os.path.normpath(str(to)).rstrip('\\/')
        if not os.path.isdir(Fo): return {'ok': False, 'message': '找不到這個資料夾'}
        if len(To) < 3 or To[1] != ':' or To[:2].upper() == Fo[:2].upper(): return {'ok': False, 'message': '新位置要在另一顆硬碟上'}
        if (To.lower() + '\\').startswith(Fo.lower() + '\\'): return {'ok': False, 'message': '不能搬到自己裡面'}
        J = self.cfg.get('disk_move') or {}
        if J.get('state') in ('run', 'pause'): return {'ok': False, 'message': '已經有一個在搬（先等它搬完或停掉）'}
        if not self.root_of(To + '\\x'):
            R = [str(x) for x in self.cfg.get('roots') or []]; R.append(To); self.cfg.set('roots', R)
            sn = self.vol_serial(To[:2] + '\\')
            if sn: vol = dict(self.cfg.get('root_vol') or {}); vol[To] = sn; self.cfg.set('root_vol', vol)
        J = {'src': Fo[:2].upper(), 'dst': To[:2].upper(), 'name': os.path.basename(To), 'folder': Fo, 'to': To, 'speed': int(speed or 0), 'state': 'run', 't0': time.time(),
             'done_b': 0, 'done_n': 0, 'fail': []}
        self.cfg.set('disk_move', J); self.bg_set_pause('move', False, '開始搬資料夾')
        self.log.w(f'🚚 搬資料夾開始：{Fo} → {To}（限速 {speed or "不限"} MB/秒）'); self._mv_kick()
        return {'ok': True, 'message': f'開始搬 {Fo} → {To}（背景、低優先權；進度在「🚚 搬硬碟」）'}

    def _mv_thumbdir(self, s, d, J):
        if not d: return
        try:
            if os.path.exists(d): d = self._mv_unique(d)
            tmp = d + '.tmp'; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copytree(s, tmp)
            if sum(1 for _ in Path(tmp).glob('*')) < sum(1 for _ in Path(s).glob('*')): raise IOError('複製不完整')
            os.replace(tmp, d)
            self.db.x('UPDATE files SET th_dir=? WHERE th_dir=?', (d, s))
            sz = sum(f.stat().st_size for f in Path(d).glob('*') if f.is_file())
            shutil.rmtree(s, ignore_errors=True); self._mv_done(J, sz)
            time.sleep(0.01)
        except Exception as ex: self._mv_fail(J, s, f'預覽圖資料夾：{type(ex).__name__}: {ex}')

    def _mv_finish_folder(self, J):
        Fo = J['folder']; To = J['to']
        try:
            for r in self.db.q("SELECT id, cv_src, cv_del, cv_out FROM files WHERE instr(lower(cv_src), ?)=1 OR instr(lower(cv_del), ?)=1 OR instr(lower(cv_out), ?)=1", (Fo.lower(),) * 3):
                v = [(self._mv_map(x, J) or x) if x else x for x in (r['cv_src'], r['cv_del'], r['cv_out'])]
                self.db.x('UPDATE files SET cv_src=?, cv_del=?, cv_out=? WHERE id=?', (*v, r['id']))
            for r in self.db.q("SELECT id, out FROM cuts WHERE instr(lower(out), ?)=1", (Fo.lower(),)):
                o = self._mv_map(r['out'], J)
                if o: self.db.x('UPDATE cuts SET out=? WHERE id=?', (o, r['id']))
        except Exception: self.log.err('🚚 搬資料夾：改轉檔／初剪紀錄')
        left = 0
        for dp, dn, fn in os.walk(Fo, topdown=False):
            left += len(fn)
            try:
                if not os.listdir(dp): os.rmdir(dp)
            except Exception: pass
        J['state'] = 'done'; J['t1'] = time.time(); self.cfg.set('disk_move', J)
        try: self.info_c['t'] = 0
        except Exception: pass
        try: self.pack_export_due(force=True, why='（搬資料夾完成）')
        except Exception: pass
        msg = f'🚚 搬資料夾完成：{Fo} → {To}，{int(J.get("done_n") or 0):,} 個檔、{fmt_b(J.get("done_b"))}' + (f'；{left:,} 個沒搬（看「沒搬成的」）' if left else '')
        self.log.w(msg); self.remap_msg = msg; self.bg_mark('move', msg)

    def _mv_finish(self, J):
        """全部搬完：轉檔／初剪紀錄裡的路徑改過去、空資料夾清掉、影片庫換成目的硬碟、兩顆的資料重新寫到硬碟上."""
        J = dict(self.cfg.get('disk_move') or J); S = J['src']; D = J['dst']
        if J.get('folder'): return self._mv_finish_folder(J)
        try:                                                                     # 紀錄裡其他欄位的舊路徑
            for r in self.db.q("SELECT id, cv_src, cv_del, cv_out FROM files WHERE upper(substr(cv_src,1,2))=? OR upper(substr(cv_del,1,2))=? OR upper(substr(cv_out,1,2))=?", (S, S, S)):
                v = [self._mv_map(x, J) if x and x[:2].upper() == S else x for x in (r['cv_src'], r['cv_del'], r['cv_out'])]
                self.db.x('UPDATE files SET cv_src=?, cv_del=?, cv_out=? WHERE id=?', (v[0] or r['cv_src'], v[1] or r['cv_del'], v[2] or r['cv_out'], r['id']))
            for r in self.db.q("SELECT id, out FROM cuts WHERE upper(substr(out,1,2))=?", (S,)):
                o = self._mv_map(r['out'], J)
                if o: self.db.x('UPDATE cuts SET out=? WHERE id=?', (o, r['id']))
        except Exception: self.log.err('🚚 搬硬碟：改轉檔／初剪紀錄')
        left = 0
        for dp, dn, fn in os.walk(S + '\\', topdown=False):                       # 空資料夾清掉（系統資料夾不碰）
            if any(x.lower() in self.MV_SKIP for x in Path(dp).parts[1:2]): continue
            if path_key(dp) == path_key(S + '\\'): continue
            try:
                if not os.listdir(dp): os.rmdir(dp)
            except Exception: pass
        try:
            for dp, dn, fn in os.walk(S + '\\'):
                if path_key(dp) == path_key(S + '\\'): dn[:] = [x for x in dn if x.lower() not in self.MV_SKIP]
                left += len([f for f in fn if self._mv_map(os.path.join(dp, f), J) is not None])
        except Exception: pass
        rows_left = int((self.db.one("SELECT COUNT(*) FROM files WHERE upper(substr(path,1,2))=? AND missing=0", (S,)) or [0])[0] or 0)
        if not left:
            self.cfg.set('roots', [r for r in (self.cfg.get('roots') or []) if str(r)[:2].upper() != S])
            vol = dict(self.cfg.get('root_vol') or {})
            for k in [k for k in vol if str(k)[:2].upper() == S]: vol.pop(k, None)
            self.cfg.set('root_vol', vol)
            try:                                                                 # 來源那顆已經空了：它身上的 SortCut 資料也拿掉（以後當新硬碟用，不會被當成舊的接回來）
                pd = self.pack_dir(S); shutil.rmtree(pd, ignore_errors=True)
                b = Path(S + '\\') / ARCH_BASE
                if b.is_dir() and not any(b.iterdir()): b.rmdir()
            except Exception: pass
        J['state'] = 'done'; J['t1'] = time.time(); self.cfg.set('disk_move', J)
        try: self.info_c['t'] = 0
        except Exception: pass
        self._pk_ok = {}
        try: self.pack_export_due(force=True, why='（搬硬碟完成）')
        except Exception: self.log.err('🚚 搬硬碟：寫到各硬碟')
        try: self.scan([r for r in self.cfg.get('roots') or [] if str(r)[:2].upper() == D]) or None
        except Exception: pass
        msg = f'🚚 搬硬碟完成：{S} → {D}\\{J["name"]}，{int(J.get("done_n") or 0):,} 個檔、{fmt_b(J.get("done_b"))}' + (f'；{left:,} 個沒搬（看「沒搬成的」）' if left else f'；{S} 已經空了') + (f'；還有 {rows_left:,} 筆紀錄在 {S}' if rows_left else '')
        self.log.w(msg); self.remap_msg = msg; self.bg_mark('move', msg)

    def gone_reason(self, path, root=''):
        """工作失敗後判斷：'offline'＝整顆硬碟不見（不算壞檔，之後重來）、'missing'＝只有這個檔不見、''＝檔案還在（真的失敗）."""
        try:
            if os.path.exists(path): return ''
        except Exception: pass
        r = str(root or self.root_of(path) or Path(path).anchor)
        if r and self.root_offline(r, fresh=True): return 'offline'
        try: anc = Path(path).anchor
        except Exception: anc = ''
        if anc and not os.path.exists(anc): return 'offline'
        return 'missing'

    def lane_eta(self, lane, roots):
        """這顆硬碟上的預覽圖還要多久（照這顆最近 30 分鐘的速度；資料不夠回傳 None）."""
        try:
            if not roots: return None
            now = time.time(); D = [x for x in list(self.th_done_log) if len(x) > 2 and x[2] == lane and now - x[0] <= 1800]
            ph = ','.join('?' * len(roots))
            left = (self.db.one(f"SELECT SUM(dur) FROM files WHERE th_state IN (0,1) AND has_v=1 AND probed=1 AND missing=0 AND arch='' AND root IN ({ph})", roots) or [0])[0] or 0
            if not left: return 0
            if len(D) < 2: return None
            rate = sum(x[1] for x in D) / max(now - D[0][0], 120.0)
            return left / rate if rate > 0 else None
        except Exception: return None

    def disks_view(self):
        """後台用：每一道（實體硬碟）的狀態."""
        lanes = {}
        for r in self.cfg.get('roots') or []: lanes.setdefault(self.root_lane(str(r)), []).append(str(r))
        for J in list(self.th_active.values()) + list(self.cv_active.values()):
            lanes.setdefault(J.get('lane') or self.lane_of(J.get('path') or ''), [])
        out = []
        for L, roots in lanes.items():
            self.lane_open(L)                                                   # 更新「為什麼在等」
            c = [self.dcount.get(n) for n in self.drives.disk_nums(L)]; c = [x for x in c if x]
            out.append({'lane': L, 'label': self.drives.label(L), 'media': self.drives.media(L), 'roots': roots, 'cap': self.lane_cap(L),
                        'busy': max([x['busy'] for x in c] or [None]) if c else None, 'rd': sum(x['rd'] for x in c) if c else None, 'wr': sum(x['wr'] for x in c) if c else None,
                        'th': sum(1 for J in list(self.th_active.values()) if (J.get('lane') or self.lane_of(J.get('path') or '')) == L),
                        'cv': sum(1 for J in list(self.cv_active.values()) if (J.get('lane') or self.lane_of(J.get('path') or '')) == L),
                        'pr': self.pr_lanes.get(L, 0), 'note': self.lane_note.get(L, ''), 'eta': self.lane_eta(L, roots)})
        return out

    # ---------- 排除的資料夾
    def ex_rules(self):
        """(完整路徑的集合, 名稱規則的 regex 或 None)."""
        P = {path_key(p) for p in self.cfg.get('ex_dirs') or [] if str(p).strip()}
        if str(self.cfg.get('cut_dir') or '').strip(): P.add(path_key(self.cfg.get('cut_dir')))       # 初剪資料夾：永遠排除（_初剪 本來就不掃）
        N = [str(n).strip().lower() for n in self.cfg.get('ex_names') or [] if str(n).strip()]
        R = re.compile('|'.join(fnmatch.translate(n) for n in N)) if N else None
        return P, R

    def is_excluded(self, path, root='', rules=None):
        """這個資料夾（或它上面任何一層）是不是被排除了。名稱規則只看影片庫根目錄底下的那幾層."""
        P, R = rules or self.ex_rules(); k = path_key(path)
        if P and (k in P or any(k.startswith(p + os.sep) for p in P)): return True
        if R is not None:
            rk = path_key(root) if root else ''
            rel = k[len(rk):] if rk and (k == rk or k.startswith(rk + os.sep)) else k
            for part in rel.split(os.sep):
                if part and R.match(part): return True
        return False

    def apply_excludes(self):
        """把已經在影片庫裡、但現在被排除的影片拿掉（missing=1，檔案和預覽圖都不動）。回傳拿掉幾部."""
        rules = self.ex_rules(); n = 0
        if not rules[0] and rules[1] is None: return 0
        bad = [r['folder'] for r in self.db.q('SELECT DISTINCT root, folder FROM files WHERE missing=0') if self.is_excluded(r['folder'], r['root'] or self.root_of(r['folder']), rules)]
        for f in bad: n += self.db.x('UPDATE files SET missing=1 WHERE folder=? AND missing=0', (f,)) or 0
        with self.lock:
            self.th_front = deque(x for x in self.th_front if (self.db.one('SELECT missing FROM files WHERE id=?', (x,)) or [1])[0] == 0)
        self.info_c['t'] = 0
        if n: self.log.w(f'排除：{len(bad):,} 個資料夾、{n:,} 部影片從影片庫拿掉（檔案沒動）')
        return n

    def add_exclude(self, path=None, name=None):
        if path:
            L = [str(x) for x in self.cfg.get('ex_dirs') or []]
            if path_key(path) not in {path_key(x) for x in L}: self.cfg.set('ex_dirs', L + [os.path.normpath(str(path))]); self.oplog('exclude', dst=str(path), detail='排除資料夾')
        if name:
            L = [str(x) for x in self.cfg.get('ex_names') or []]
            if name.strip().lower() not in {x.strip().lower() for x in L}: self.cfg.set('ex_names', L + [name.strip()])
        return self.apply_excludes()

    def remove_exclude(self, path=None, name=None):
        """取消排除：重新掃描就會把那些影片找回來（預覽圖之前做好的還在，不用重做）."""
        if path is not None: self.cfg.set('ex_dirs', [x for x in self.cfg.get('ex_dirs') or [] if path_key(x) != path_key(path)])
        if name is not None: self.cfg.set('ex_names', [x for x in self.cfg.get('ex_names') or [] if str(x).strip().lower() != name.strip().lower()])
        return self.scan()

    # ---------- 影片庫掃描
    def scan(self, roots=None):
        if self.scan_st['running']: return False
        roots = [str(r) for r in (roots or self.cfg.get('roots') or []) if r]
        if not roots: return False
        self.scan_st.update(running=True, n=0, dirs=0, cur='', t0=time.time(), new=0)
        threading.Thread(target=self._scan, args=(roots,), name='VsScan', daemon=True).start(); return True

    def _scan(self, roots):
        try:                                                                     # V0.2.24 先確認每個代號接的還是原本那顆（別顆的不會被當成同一個影片庫收進來）
            R0 = {path_key(x) for x in self.cfg.get('roots') or []}; allr = R0 <= {path_key(x) for x in roots}
            self.vol_check(); R_ = [str(x) for x in self.cfg.get('roots') or []]
            roots = R_ if allr else [r for r in roots if path_key(r) in {path_key(x) for x in R_}]
        except Exception: self.log.err('掃描前檢查硬碟')
        t = self.task('scan', '掃描影片庫'); t_seen = time.time(); th = str(self.thumbs_root()).lower()
        exP, exR = rules = self.ex_rules(); n_ex = 0
        sql = ('INSERT INTO files(path,root,folder,name,ext,size,mtime,seen,missing) VALUES(?,?,?,?,?,?,?,?,0) ON CONFLICT(path) DO UPDATE SET '
               'probed=CASE WHEN files.size!=excluded.size OR abs(files.mtime-excluded.mtime)>2 THEN 0 ELSE files.probed END, '
               'th_state=CASE WHEN files.size!=excluded.size OR abs(files.mtime-excluded.mtime)>2 THEN 0 ELSE files.th_state END, '
               'size=excluded.size, mtime=excluded.mtime, seen=excluded.seen, missing=0, root=excluded.root')
        try:
            before = self.db.one('SELECT COUNT(*) FROM files')[0]
            MVS = str((self.cfg.get('disk_move') or {}).get('src') or '') if (self.cfg.get('disk_move') or {}).get('state') in ('run', 'pause') else ''
            for root in roots:
                if not Path(root).exists(): self.log.w(f'掃描：找不到 {root}（硬碟沒接？），這一個先跳過，原本的資料保留'); continue
                if MVS and str(root)[:2].upper() == MVS.upper(): self.log.w(f'掃描：{root} 正在搬到別顆硬碟，這次不掃'); continue
                if self.is_excluded(root, root, rules): self.log.w(f'掃描：{root} 在排除清單裡，跳過'); continue
                stack = [root]; batch = []; self.scan_st['lane'] = self.root_lane(root)
                while stack and not self.stop_all:
                    d = stack.pop(); self.scan_st['dirs'] += 1; self.scan_st['cur'] = d
                    try: it = list(os.scandir(d))
                    except Exception: continue
                    for e in it:
                        try:
                            if e.is_dir(follow_symlinks=False):
                                nm = e.name.lower()
                                if nm in SKIP_DIRS or nm.startswith('.') or e.path.lower() == th: continue
                                if nm == DEL_DIR.lower() and is_drive_root(d): continue          # X:\DELETE\（轉好之後原檔暫放的地方）不掃
                                if (exR is not None and exR.match(nm)) or (exP and path_key(e.path) in exP): n_ex += 1; continue      # 你設定要排除的
                                stack.append(e.path)
                            elif e.is_file(follow_symlinks=False):
                                ext = os.path.splitext(e.name)[1].lower()
                                if ext in VIDEO_EXT and '.vspart' not in e.name.lower() and (ext != '.dat' or is_vcd_dat(e.name)):      # 轉到一半的暫存檔不算；.dat 只收 VCD 影片（AVSEQ01.DAT），遊戲／程式的 .dat 不算
                                    st = e.stat(); batch.append((e.path, root, d, e.name, ext, st.st_size, st.st_mtime, t_seen)); self.scan_st['n'] += 1
                        except Exception: pass
                    if len(batch) >= 400: self.db.xm(sql, batch); batch = []
                    t['msg'] = f'{self.scan_st["n"]:,} 個影片 · {self.scan_st["dirs"]:,} 個資料夾 · {d}'
                if batch: self.db.xm(sql, batch)
                if not self.stop_all and Path(root).exists(): self.db.x("UPDATE files SET missing=1 WHERE root=? AND seen<? AND arch=''", (root, t_seen - 1))
                elif not self.stop_all: self.log.w(f'掃描：掃到一半找不到 {root}（硬碟離線？），這次不把沒掃到的影片當成不見')      # 歸檔的在 VideoSIFT 裡（不掃），不算不見
            after = self.db.one('SELECT COUNT(*) FROM files')[0]; self.scan_st['new'] = after - before; self.scan_st['ex'] = n_ex
            self.done(t, 'done', f'{self.scan_st["n"]:,} 個影片（新的 {after - before:,}）· {self.scan_st["dirs"]:,} 個資料夾' + (f' · 排除 {n_ex:,} 個資料夾' if n_ex else ''))
            self.log.w(f'掃描完成：{self.scan_st["n"]:,} 個影片，新的 {after - before:,}，{self.scan_st["dirs"]:,} 個資料夾' + (f'，排除 {n_ex:,} 個資料夾' if n_ex else '') + f'，{time.time() - t["t0"]:.0f} 秒')
        except Exception as ex:
            self.log.err('掃描'); self.done(t, 'fail', str(ex))
        finally:
            self.scan_st.update(running=False, t1=time.time(), cur='', lane='')

    # ---------- ffprobe（背景，最低優先權）
    def _probe_boss(self):
        while self.alive():
            try:
                n = max(1, min(4, int(self.cfg.get('probe_n') or 2)))
                if self.boosted(): n = min(4, n * 2)
                n = self.bg_cap('probe', n)
                if self.pr_active < n and self.ffprobe and not self.bg_hold('probe'):
                    full = self.full_roots(); ph = ','.join('?' * len(full))
                    r0 = self.db.one(f'SELECT root FROM files WHERE probed=0 AND missing=0 AND length(arch)=0 {"AND root NOT IN (" + ph + ")" if full else ""} '
                                     'ORDER BY (substr(folder,1,?)=?) DESC, folder, name LIMIT 1', (*full, len(self.th_focus), self.th_focus))
                    rows = self.db.q('SELECT id,path FROM files WHERE probed=0 AND missing=0 AND length(arch)=0 AND root=? ORDER BY (substr(folder,1,?)=?) DESC, folder, name LIMIT 20',
                                     (r0['root'], len(self.th_focus), self.th_focus)) if r0 is not None else []
                    if rows:
                        lane = self.root_lane(str(r0['root']))
                        self.db.xm('UPDATE files SET probed=2 WHERE id=?', [(r['id'],) for r in rows])          # 2＝讀取中
                        self.pr_active += 1; self.pr_lanes[lane] = self.pr_lanes.get(lane, 0) + 1
                        self.bg_mark('probe', Path(rows[0]['path']).name)
                        threading.Thread(target=self._probe_batch, args=([(r['id'], r['path']) for r in rows], lane), name='VsProbe', daemon=True).start()
                        continue
                time.sleep(1.0)
            except Exception:
                self.log.err('probe boss'); time.sleep(5)

    def _probe_batch(self, rows, lane=''):
        PC = self.__dict__.setdefault('pr_cur', {}); k_ = threading.get_ident()
        try:
            for fid, path in rows:
                if self.stop_all: break
                PC[k_] = path
                r = probe(self.ffprobe, path)
                if r.get('ok'):
                    self.db.x('UPDATE files SET probed=1,probe_err=\'\',has_v=?,dur=?,w=?,h=?,vcodec=?,acodecs=?,fps=?,pix=?,field=?,vbr=?,th_state=CASE WHEN ?=0 THEN 4 ELSE th_state END WHERE id=?',
                              (r['has_v'], r['dur'], r['w'], r['h'], r['vcodec'], r['acodecs'], r['fps'], r['pix'], r['field'], r['vbr'], r['has_v'], fid))
                    self.pr_done_log.append(time.time())
                else:
                    why = self.gone_reason(path)
                    if why == 'offline': self.log.w(f'讀影片資訊：{path} 所在的硬碟離線，這批先停（不算壞檔）'); break      # finally 會把這批改回「還沒讀」
                    if why == 'missing': self.db.x('UPDATE files SET missing=1,probed=0 WHERE id=?', (fid,)); self.log.w(f'讀影片資訊：{path} 不見了（被搬走或刪掉），從清單拿掉'); continue
                    self.db.x('UPDATE files SET probed=3,probe_err=?,th_state=3,th_err=? WHERE id=?', (r.get('err', ''), '讀不到這個檔（可能壞掉或不是影片）', fid))
                    self.log.w(f'讀影片資訊失敗：{path}：{str(r.get("err", ""))[-300:]}')
        except Exception: self.log.err('probe')
        finally:
            PC.pop(k_, None)
            try: self.db.x('UPDATE files SET probed=0 WHERE probed=2 AND id IN (%s)' % ','.join(str(int(f)) for f, _p in rows))
            except Exception: pass
            self.pr_active -= 1
            if lane: self.pr_lanes[lane] = max(0, self.pr_lanes.get(lane, 1) - 1)

    # ---------- 預覽圖：每 2 秒一張，拼成 10x10 一大張
    def folder_front(self, folder):
        """這個資料夾（含子資料夾）還沒做預覽圖的，全部排到最前面（照資料夾、檔名順序）."""
        f = str(folder).rstrip('\\/')
        ids = [r[0] for r in self.db.q("SELECT id FROM files WHERE missing=0 AND arch='' AND has_v=1 AND th_state IN (0,3) AND (folder=? OR substr(folder,1,?)=? OR substr(folder,1,?)=?) ORDER BY folder, name LIMIT 5000",
                                       (f, len(f) + 1, f + '\\', len(f) + 1, f + '/'))]
        with self.lock:
            for i in reversed(ids):
                if i in self.th_front: self.th_front.remove(i)
                self.th_front.appendleft(int(i))
        self.log.w(f'資料夾先做預覽圖：{folder}（{len(ids)} 部排到最前面）'); return len(ids)

    def thumb_front(self, fid):
        """你正在看的那部：排到最前面（不中斷正在做的）."""
        with self.lock:
            if fid in self.th_front: self.th_front.remove(fid)
            self.th_front.appendleft(int(fid))

    def _thumb_next(self):
        """下一部：先看「⚡ 先做這部」，再照你正在看的資料夾 → 資料夾 → 檔名的順序（同一顆 HDD 上就是照位置順序讀）。
        所在硬碟滿了（HDD 一次一部）或正被別的程式占用的，先跳過，做別顆硬碟上的."""
        with self.lock:
            keep = deque(); got = None
            while self.th_front:
                fid = self.th_front.popleft()
                if fid in self.th_active: continue
                r = self.db.one('SELECT id,path,dur,th_state,probed,has_v,missing FROM files WHERE id=?', (fid,))
                if not (r and r['th_state'] in (0, 3) and r['probed'] == 1 and r['has_v'] and not r['missing']): continue
                if got is None and self.lane_open(self.lane_of(r['path'])): got = r
                else: keep.append(fid)
            self.th_front.extend(keep)
            if got is not None: return got
        excl = ','.join(str(int(x)) for x in self.th_active) or '-1'; full = self.full_roots(); ph = ','.join('?' * len(full))
        for r in self.db.q(f'SELECT id,path,dur,th_state,probed,has_v,root FROM files WHERE th_state=0 AND probed=1 AND has_v=1 AND missing=0 AND length(arch)=0 AND id NOT IN ({excl}) '
                           f'{"AND root NOT IN (" + ph + ")" if full else ""} ORDER BY (substr(folder,1,?)=?) DESC, folder, name LIMIT 30', (*full, len(self.th_focus), self.th_focus)):
            if self.lane_open(self.lane_of(r['path'])): return r
        return None

    def _thumb_boss(self):
        while self.alive():
            try:
                n = max(1, min(8, int(self.cfg.get('th_n') or 2))); bz = self.boosted()
                if bz: n = min(8, n * 2)                                         # 🧪 背景加速：同時做的部數加倍（HDD 還是一次一部）
                n = self.bg_cap('thumb', n)
                if self.cfg.get('th_on') and not self.bg_hold('thumb') and self.ff and len(self.th_active) < n and not self._th_low_space():
                    r = self._thumb_next()
                    if r is not None:
                        fid = int(r['id']); self.db.x('UPDATE files SET th_state=1 WHERE id=?', (fid,))
                        self.th_active[fid] = {'id': fid, 'name': Path(r['path']).name, 'path': r['path'], 'lane': self.lane_of(r['path']), 'pct': 0, 't0': time.time(), 'proc': None,
                                               'precise': fid in self.th_precise}; self.th_precise.discard(fid); self.bg_mark('thumb', Path(r['path']).name)
                        threading.Thread(target=self._thumb_job, args=(fid, r['path'], float(r['dur'] or 0)), name='VsThumb', daemon=True).start()
                        continue
                time.sleep(1.0)
            except Exception:
                self.log.err('thumb boss'); time.sleep(5)

    # ---------- V0.1.95 硬碟代號換了（重開機後 E: 和 G: 對調）：自動找到、把資料改過去
    @staticmethod
    def vol_serial(root):
        """磁碟的序號（Windows）：代號換了序號不會變，用來認硬碟."""
        if not IS_WIN: return ''
        try:
            import ctypes
            d = os.path.splitdrive(str(root))[0]
            if not d: return ''
            sn = ctypes.c_uint32(0); ok = ctypes.windll.kernel32.GetVolumeInformationW(ctypes.c_wchar_p(d + '\\'), None, 0, ctypes.byref(sn), None, None, None, 0)
            return f'{sn.value:08X}' if ok else ''
        except Exception: return ''

    def drive_remap_detect(self):
        """每個影片庫：舊的資料用原本的代號找不到、換成別的代號找得到（同名同大小）→ 回傳 {舊代號: 新代號}."""
        letters = [c for c in 'CDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.exists(c + ':\\')] if IS_WIN else []
        M = {}; vol = dict(self.cfg.get('root_vol') or {})
        for root in [str(x) for x in self.cfg.get('roots') or []]:
            X = os.path.splitdrive(root)[0][:1].upper()
            if not X or X in M: continue
            want = vol.get(root)
            if want and self.vol_serial(root) == want: continue                  # 序號對得上：沒換
            if want:
                for Y in letters:
                    if Y != X and self.vol_serial(Y + ':') == want: M[X] = Y; break
                if X in M: continue
            S = [r for r in self.db.q('SELECT path, size FROM files WHERE root=? AND size>0 ORDER BY id LIMIT 40', (root,))]
            if len(S) < 5: continue
            ok = lambda p, sz: os.path.isfile(p) and os.path.getsize(p) == sz
            hx = sum(1 for r in S if ok(r['path'], r['size']))
            if hx > len(S) * 0.3: continue
            for Y in letters:
                if Y == X: continue
                hy = sum(1 for r in S if ok(Y + r['path'][1:], r['size']))
                if hy >= max(5, len(S) * 0.7): M[X] = Y; break
        return M

    def drive_remap(self, M=None):
        """把資料庫裡的路徑、影片庫設定，從舊代號改成新代號（分級、預覽圖、轉檔紀錄都留著）.
        換代號後掃描誤收進來的「另一顆硬碟的檔」（沒有任何紀錄的）一起清掉，免得重複."""
        M = M if M is not None else self.drive_remap_detect()
        if not M: return {'ok': True, 'n': 0}
        self.log.w(f'💽 硬碟代號換了：' + '、'.join(f'{a}: → {b}:' for a, b in M.items()) + '，把資料改過去（分級、預覽圖、轉檔紀錄都保留）')
        cache = {}
        _split = os.path.split if IS_WIN else __import__('ntpath').split        # Windows 的 os.path 就是 ntpath（測試在 Linux 上也要拆得開 X:\\ 路徑）
        def ex(p):
            d, n = _split(p)
            if d not in cache:
                try: cache[d] = {x.lower() for x in os.listdir(d)}
                except Exception: cache[d] = set()
            return n.lower() in cache[d]
        roots = [str(x) for x in self.cfg.get('roots') or []]
        newroots = [(M[r[:1].upper()] + r[1:]) if len(r) > 1 and r[1] == ':' and r[:1].upper() in M else r for r in roots]
        hist = lambda r: bool(r['grade'] or r['fav'] or r['cut_n'] or r['note'] or r['tag'] or int(r['cv_state'] or 0) or r['arch'] or int(r['viewed'] or 0))
        rows = [dict(r) for r in self.db.q(f"SELECT * FROM files WHERE upper(substr(path,1,1)) IN ({','.join('?' * len(M))})", list(M))]
        remap = {}; intr = []
        for r in rows:
            X = r['path'][:1].upper(); newp = M[X] + r['path'][1:]
            if ex(newp) or not ex(r['path']): remap[r['id']] = newp
            else: intr.append(r)
        newset = {v.lower(): k for k, v in remap.items()}
        dele = []; merged = 0
        for r in intr:
            hid = newset.get(r['path'].lower())
            if hid is not None or not hist(r):
                if hid is not None and int(r['th_state'] or 0) == 2:
                    h = self.db.one('SELECT th_state FROM files WHERE id=?', (hid,))
                    if h and int(h[0] or 0) != 2:
                        self.db.x('UPDATE files SET th_state=2,th_n=?,th_cols=?,th_rows=?,th_step=?,th_dir=?,th_t=? WHERE id=?', (r['th_n'], r['th_cols'], r['th_rows'], r['th_step'], r['th_dir'], r['th_t'], hid)); merged += 1
                dele.append((int(r['id']),))
        if dele: self.db.xm('DELETE FROM files WHERE id=?', dele)
        sw = lambda v: (M[v[:1].upper()] + v[1:]) if v and len(v) > 1 and v[1] == ':' and v[:1].upper() in M else v
        U = []
        for r in rows:
            if r['id'] not in remap: continue
            U.append(('#' + remap[r['id']], sw(r['folder'] or ''), sw(r['root'] or ''), sw(r['cv_src'] or ''), sw(r['cv_del'] or ''), sw(r['cv_out'] or ''), 0 if ex(remap[r['id']]) else int(r['missing'] or 0), r['id']))
        self.db.xm('UPDATE files SET path=?, folder=?, root=?, cv_src=?, cv_del=?, cv_out=?, missing=? WHERE id=?', U)
        self.db.x("UPDATE files SET path=substr(path,2) WHERE substr(path,1,1)='#'")
        self.cfg.set('roots', newroots); self._root_lane = {}
        vol = dict(self.cfg.get('root_vol') or {})
        for r in roots: vol.pop(r, None)
        for r in newroots:
            sn = self.vol_serial(r)
            if sn: vol[r] = sn
        self.cfg.set('root_vol', vol)
        try: self.info_c['t'] = 0
        except Exception: pass
        msg = f'硬碟代號換了（' + '、'.join(f'{a}: → {b}:' for a, b in M.items()) + f'）：{len(U):,} 部的路徑改好（分級、預覽圖、轉檔紀錄都在）；換代號後誤收進來的重複 {len(dele):,} 部清掉' + (f'（{merged} 部的預覽圖併過去）' if merged else '')
        self.log.w('💽 ' + msg); return {'ok': True, 'n': len(U), 'deleted': len(dele), 'map': M, 'message': msg}

    def dedupe_letters(self):
        """同一個檔（除了磁碟代號以外路徑一樣、大小一樣）出現兩筆 → 留有紀錄的／舊的那筆，刪掉後來誤收、沒有任何紀錄的那筆（只動資料庫）."""
        try:
            G = {}; ids = []
            for r in self.db.q("SELECT id, path, size, grade, fav, cut_n, note, tag, cv_state, arch, viewed FROM files ORDER BY id"):
                p = str(r['path'] or '')
                if len(p) < 3 or p[1] != ':': continue
                k = (p[1:].lower(), int(r['size'] or 0))
                if k in G and G[k] != p[:1].upper():
                    if not (r['grade'] or r['fav'] or r['cut_n'] or r['note'] or r['tag'] or int(r['cv_state'] or 0) or r['arch'] or int(r['viewed'] or 0)): ids.append(int(r['id']))
                else: G.setdefault(k, p[:1].upper())
            if ids:
                self.db.xm('DELETE FROM files WHERE id=?', [(i,) for i in ids])
                self.log.w(f'💽 清單整理：{len(ids):,} 筆是換了磁碟代號後重複收進來的（同一個檔、不同代號），刪掉重複的那筆（檔案沒動；有分級、預覽圖、轉檔紀錄的那筆留著）')
            return len(ids)
        except Exception: self.log.err('清重複（磁碟代號）'); return 0

    def remember_vols(self):
        vol = dict(self.cfg.get('root_vol') or {}); ch = False
        for r in [str(x) for x in self.cfg.get('roots') or []]:
            if r not in vol and os.path.exists(r):
                sn = self.vol_serial(r)
                if sn: vol[r] = sn; ch = True
        if ch: self.cfg.set('root_vol', vol)

    @staticmethod
    def thumb_broken(d, th_n):
        """V0.1.95 預覽圖時間軸對不起來：FFmpeg 把整張大圖重複輸出（同一張存好幾次），後面每一格的時間都往後偏 —
        大圖張數比應該的多，或連續兩張一模一樣 → 回傳原因."""
        try:
            S = sorted(Path(d).glob('s*.jpg'))
            if not S: return ''
            want = max(1, math.ceil(int(th_n or 0) / 100))
            if len(S) > want: return f'大圖 {len(S)} 張（應該 {want} 張）'
            sz = [x.stat().st_size for x in S]
            for i in range(1, len(S)):
                if sz[i] == sz[i - 1] and S[i].read_bytes() == S[i - 1].read_bytes(): return f'第 {i} 和 {i + 1} 張一模一樣'
        except Exception: pass
        return ''

    def thumb_short(self, d, dur, step, cols=10, rows=10, keyonly=False):
        # V0.2.03 格子比影片長度少（PK 換畫面大小時 FFmpeg 丟格）→ 回傳原因。最後一張大圖縮成 10×10 個點，每點＝一格的平均亮度，黑的＝空格
        try:
            S = sorted(Path(d).glob('s*.jpg')); dur = float(dur or 0); step = max(1, int(step or 2))
            if not S or dur <= step * 10: return ''
            p = subprocess.run([self.ff, '-hide_banner', '-loglevel', 'error', '-i', str(S[-1]), '-vf', f'scale={cols}:{rows}:flags=area', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                               capture_output=True, timeout=30, creationflags=NO_WINDOW | PRIO.get('idle', 0), stdin=subprocess.DEVNULL)
            v = list(p.stdout or b'')
            if p.returncode != 0 or len(v) != cols * rows: return ''
            last = max((i for i, x in enumerate(v) if x >= 20), default=-1) + 1
            got = (len(S) - 1) * cols * rows + last; want = int(dur // step)
            lack = want - got - (3 if keyonly else 0)                            # 只解關鍵格：最後幾秒沒有關鍵格是正常的
            if lack >= 5: return f'少了 {want - got} 格（{fmt_t((want - got) * step)}），後面的時間會偏掉'
        except Exception: pass
        return ''

    def _thumb_pk_scan(self):
        """V0.2.03 更新後跑一次（背景、最低優先）：舊方法做的預覽圖，格子數比影片長度少的（PK 換畫面大小造成）→ 重新排隊做."""
        try:
            R = self.db.q("SELECT id, path, th_dir, dur, th_step, th_cols, th_rows FROM files WHERE th_state=2 AND missing=0 AND th_dir!='' AND dur>0 ORDER BY id")
            bad = []; t0 = time.time()
            for k, r in enumerate(R):
                if not self.alive(): return
                why = self.thumb_short(r['th_dir'], r['dur'], r['th_step'], int(r['th_cols'] or 10), int(r['th_rows'] or 10))
                if why:
                    bad.append((int(r['id']), r['path'], why)); self.db.x('UPDATE files SET th_state=0 WHERE id=? AND th_state=2', (int(r['id']),))
                if k % 50 == 49: time.sleep(0.2)                                 # 慢慢來，不搶硬碟
                if k % 2000 == 1999: self.log.w(f'🖼 預覽圖 PK 時間軸檢查：{k + 1:,}／{len(R):,}，目前 {len(bad)} 部要重做')
            self.cfg.set('th_fix_v203', True)
            self.log.w(f'🖼 預覽圖 PK 時間軸檢查完成（{len(R):,} 部，{time.time() - t0:.0f} 秒）：{len(bad)} 部格子少了（直播 PK 換畫面大小造成，後面時間偏掉），已重新排隊做' +
                       ('；例如：' + '；'.join(f'{Path(p).name}（{w}）' for _i, p, w in bad[:5]) if bad else ''))
            self.pk_scan_last = {'n': len(R), 'bad': len(bad), 't': time.time()}
        except Exception: self.log.err('預覽圖 PK 時間軸檢查')

    def _thumb_fix_scan(self):
        """更新後跑一次：找出時間軸對不起來的預覽圖，重新排隊做（只重做壞的；好的不動）."""
        try:
            bad = []
            for r in self.db.q("SELECT id, path, th_dir, th_n FROM files WHERE th_state=2 AND missing=0 AND th_dir!=''"):
                if not self.alive(): return
                why = self.thumb_broken(r['th_dir'], r['th_n'])
                if why: bad.append((int(r['id']), r['path'], why))
            if bad:
                self.db.xm('UPDATE files SET th_state=0 WHERE id=?', [(i,) for i, _p, _w in bad])
                self.log.w(f'🖼 預覽圖時間軸檢查：{len(bad)} 部對不起來（FFmpeg 重複輸出了整張大圖，後面的時間都偏掉），重新排隊做；例如：' + '；'.join(f'{Path(p).name}（{w}）' for _i, p, w in bad[:5]))
            else: self.log.w('🖼 預覽圖時間軸檢查：都對得上')
            self.cfg.set('th_fix_v95', True)
        except Exception: self.log.err('預覽圖時間軸檢查')

    def _thumb_job(self, fid, path, dur):
        J = self.th_active.get(fid) or {}; t = self.task('thumb', f'預覽圖：{Path(path).name}')
        step = max(1, int(self.cfg.get('th_step') or 2)); h = int(self.cfg.get('th_h') or 180); cols = rows = 10; vw_ = vh_ = 0
        try:                                                                    # V0.1.94 直的影片（手機直播）：高度加倍，寬度才不會只剩一點點（以前 960×1920 縮成 60×120，放大看很糊）
            vw_, vh_ = self.db.one('SELECT w, h FROM files WHERE id=?', (int(fid),)) or (0, 0)
            if vw_ and vh_ and vh_ > vw_ * 1.2: h = int(h * min(2.0, vh_ / vw_))
        except Exception: pass
        h = h - h % 2
        # V0.2.03 直播 PK 時畫面大小會變：FFmpeg 會重建濾鏡，fps 濾鏡丟掉幾格 → PK 之後每一格的時間都往前偏（隨機、看哪部有 PK）。
        # 改成固定格子大小＋不重建濾鏡（-reinit_filter 0），scale 自己處理中途換大小 → 格數、時間都對
        cw_ = int(round(h * vw_ / vh_ / 2) * 2) if vw_ and vh_ else 0; sc_ = f'scale={cw_}:{h}' if cw_ >= 16 else f'scale=-2:{h}'
        nore = ['-reinit_filter', '0'] if cw_ >= 16 else []
        out = self.th_out_dir(fid, path); tmp = out.with_name(out.name + '.tmp')          # V0.2.26 放在影片所在的那顆硬碟
        old_td = (self.db.one('SELECT th_dir FROM files WHERE id=?', (int(fid),)) or [''])[0] or ''
        try:
            shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True, exist_ok=True)
            ok = False; err = ''
            precise = J.get('precise') or (self.cfg.get('lab') or {}).get('thumb_precise')
            hw_ok = bool(self.gpu_st.get('ok')) and self.cfg.get('th_hw') is not False and time.time() - float(getattr(self, '_hwdec_bad', 0) or 0) > 1800
            steps_ = ([] if precise else [(True, False)]) + ([(False, True)] if hw_ok else []) + [(False, False)]
            for fast, hw in steps_:                                              # 先只解關鍵格（很快）；不行再整個解（V0.1.72：整個解先用顯示卡，CPU 省很多）；🧪 精準模式＝一開始就整個解
                vf = f'fps=1/{step},{sc_}:flags=bicubic,tile={cols}x{rows}'          # V0.1.94 縮圖用 bicubic（比 fast_bilinear 清楚）
                cmd = [(self.gpu_st.get('ff') or self.ff) if hw else self.ff, '-hide_banner', '-nostdin', '-loglevel', 'error', '-y', '-threads', '2'] + (['-hwaccel', 'cuda'] if hw else []) + (['-skip_frame', 'nokey'] if fast else []) + nore + \
                      ['-i', str(path), '-map', '0:v:0', '-an', '-sn', '-dn', '-vf', vf, '-q:v', '3', '-fps_mode', 'passthrough', '-progress', 'pipe:1', '-nostats', str(tmp / 's%04d.jpg')]
                if getattr(self, '_ff_old_vsync', False): cmd[cmd.index('-fps_mode'):cmd.index('-fps_mode') + 2] = ['-vsync', '0']
                pr = self.cfg.get('th_prio') or 'idle'
                if self.boosted() and pr == 'idle': pr = 'below'
                P = Proc(cmd, pr).start(); self.procs.add(P); J['proc'] = P
                def tick(p):
                    if dur > 0: J['pct'] = t['pct'] = min(99, round(p.out_us / 1e6 / dur * 100))
                rc = P.wait(stop=lambda: self.stop_all or not self.cfg.get('th_on') or J.get('cancel'), stall=240, on_tick=tick); self.procs.discard(P)
                if rc == -2: raise InterruptedError('停止')
                sheets = sorted(tmp.glob('s*.jpg'))
                if rc == 0 and sheets: ok = True; break
                err = P.errtext() or f'ffmpeg {rc}'
                if 'fps_mode' in err and not getattr(self, '_ff_old_vsync', False):  # 舊版 FFmpeg 沒有 -fps_mode：改用 -vsync 0 再做一次
                    self._ff_old_vsync = True
                    for f in sheets: f.unlink()
                    steps_.insert(steps_.index((fast, hw)) + 1, (fast, hw)); continue
                for f in sheets: f.unlink()
                if hw and ('cuda' in err.lower() or 'hwaccel' in err.lower() or 'device' in err.lower()):
                    self._hwdec_bad = time.time(); self.log.w(f'預覽圖：顯示卡解碼不行，改用 CPU（30 分鐘後再試）：{err[-200:]}')
            if not ok: raise RuntimeError(err[-400:] + '\n指令：' + cmd_text(cmd))
            n = math.ceil(dur / step) if dur > 0 else len(sheets) * cols * rows
            bw = self.thumb_broken(tmp, n) or self.thumb_short(tmp, dur, step, cols, rows, fast)
            if bw: self.log.w(f'⚠ 預覽圖：{path} 時間軸可能對不起來（{bw}），請回報')
            n = max(1, min(n, len(sheets) * cols * rows))
            out.parent.mkdir(parents=True, exist_ok=True); shutil.rmtree(out, ignore_errors=True); os.replace(str(tmp), str(out))
            self.db.x('UPDATE files SET th_state=2,th_n=?,th_cols=?,th_rows=?,th_step=?,th_dir=?,th_err=\'\',th_t=? WHERE id=?', (n, cols, rows, step, str(out), time.time(), fid))
            if old_td and path_key(old_td) != path_key(out) and self.th_owned(old_td, fid): shutil.rmtree(old_td, ignore_errors=True)      # 重做：舊的那份（在別的地方）拿掉
            try: self.e_fix_done(fid, True)
            except Exception: self.log.err('E 處理')
            el = time.time() - J.get('t0', time.time()); self.done(t, 'done', f'{n} 張 · {len(sheets)} 大張 · {el:.0f} 秒'); self.th_done_log.append((time.time(), float(dur or 0), J.get('lane') or ''))
            self.log.w(f'預覽圖好了：{path}　{fmt_t(dur)}・每 {step} 秒一張共 {n} 張（{len(sheets)} 大張）・{"只解關鍵格" if fast else ("整段解碼（精準模式）" if precise else "整段解碼（關鍵格不夠）")}・{el:.1f} 秒')
        except InterruptedError:
            shutil.rmtree(tmp, ignore_errors=True)
            if J.get('skip'): self.db.x("UPDATE files SET th_state=3,th_err='你按了停（略過這部；要做的話在檔案總管按「先做這部的預覽圖」）' WHERE id=?", (fid,)); self.done(t, 'stop', '你按了停，略過')
            else: self.db.x('UPDATE files SET th_state=0 WHERE id=?', (fid,)); self.done(t, 'stop', '停止（之後再做）')
        except Exception as ex:
            shutil.rmtree(tmp, ignore_errors=True); why = self.gone_reason(path)
            if why == 'offline': self.db.x('UPDATE files SET th_state=0 WHERE id=?', (fid,)); self.done(t, 'stop', '硬碟離線，接回來再做'); self.log.w(f'預覽圖：{path} 所在的硬碟離線，先停（不算壞檔，接回來會重做）')
            elif why == 'missing': self.db.x('UPDATE files SET th_state=0,missing=1 WHERE id=?', (fid,)); self.done(t, 'stop', '檔案不見了'); self.log.w(f'預覽圖：{path} 不見了（被搬走或刪掉），從清單拿掉')
            else:
                why_, _s, cmd_ = str(ex).partition('\n指令：')                     # V0.1.93 記「為什麼」而不是指令（以前看到的都是指令）
                why_ = ' '.join(x.strip() for x in why_.strip().splitlines()[-3:] if x.strip())[-300:] or '不知道原因'
                self.db.x('UPDATE files SET th_state=3,th_err=? WHERE id=?', (why_, fid))
                try: self.e_fix_done(fid, False)
                except Exception: pass
                self.done(t, 'fail', why_[-200:]); self.log.w(f'預覽圖失敗：{path}：{why_}' + (f'\n　指令：{cmd_[:400]}' if cmd_ else ''))
        finally:
            self.th_active.pop(fid, None)

    def thumb_cancel(self, fid, skip=False):
        J = self.th_active.get(int(fid))
        if J:
            J['cancel'] = True; J['skip'] = bool(skip)
            if J.get('proc'): J['proc'].kill()

    def thumb_retry_failed(self):
        return self.db.x('UPDATE files SET th_state=0 WHERE th_state=3')

    def thumb_redo(self, fid, precise=False):
        if precise: self.th_precise.add(int(fid))
        self.db.x('UPDATE files SET th_state=0 WHERE id=?', (int(fid),)); self.thumb_front(int(fid)); self.log.w(f'重做預覽圖{"（精準）" if precise else ""}：id {fid}')

    # ---------- 初剪（免轉檔：從前一個關鍵格開始，幾秒就好）
    def _cut_persist(self):
        """還沒剪完的初剪存起來：程式閃退重開後接著剪（V0.1.75）."""
        try:
            L = [{'fid': j['fid'], 'segs': [list(x) for x in j['segs']], 'merge': j['merge'], 'mode': j['mode']} for j in ([self.cut_cur] if self.cut_cur else []) + list(self.cut_q)]
            self.cfg.set('cut_pending', L)
        except Exception: self.log.err('初剪排隊存檔')

    def cut_pending(self):
        # V0.2.02 還在排隊／正在剪的：{影片 id: 幾段}（卡片上的「-剪輯 N」）
        d = {}
        for j in list(self.cut_q) + ([self.cut_cur] if self.cut_cur else []):
            try: d[int(j['fid'])] = d.get(int(j['fid']), 0) + len(j.get('segs') or [])
            except Exception: pass
        return d

    def cut_add(self, fid, segs, merge=None, mode=None):
        r = self.db.one('SELECT * FROM files WHERE id=?', (int(fid),))
        if not r: return {'ok': False, 'message': '找不到這部影片'}
        segs = [(float(a), float(b)) for a, b in segs if float(b) - float(a) >= 0.5]
        if not segs: return {'ok': False, 'message': '沒有選任何片段'}
        job = {'fid': int(fid), 'path': r['path'], 'segs': sorted(segs), 'merge': self.cfg.get('cut_merge') if merge is None else bool(merge),
               'mode': mode or self.cfg.get('cut_mode') or 'copy', 'task': self.task('cut', f'初剪：{r["name"]}（{len(segs)} 段）')}
        job.update(name=r['name'], t=time.time(), state='wait', nout=1 if job['merge'] else len(job['segs']), outs=[], err='')
        job['task']['state'] = 'wait'; self.cut_hist.append(job); self.cut_q.append(job); self._cut_persist()
        self.log.w(f'初剪排隊：{r["path"]}　{len(segs)} 段 ' + '、'.join(f'{fmt_t(a)}～{fmt_t(b)}' for a, b in job['segs']) + f'　{"合併" if job["merge"] else "分段"}・{"免轉檔" if job["mode"] == "copy" else "重新壓縮"}')
        return {'ok': True, 'message': f'已排入初剪：{len(segs)} 段'}

    def _cut_boss(self):
        while self.alive():
            try:
                if self.cut_q and not self.bg_hold('cut'):
                    job = self.cut_q.popleft(); self.bg_mark('cut', job.get('name')); self.cut_cur = job; job['task']['state'] = 'run'; job['state'] = 'run'; job['t_start'] = time.time()
                    try: self._cut_job(job)
                    except Exception as ex: self.log.err('初剪'); self.done(job['task'], 'fail', str(ex)[-200:]); job['state'] = 'fail'; job['err'] = str(ex)[-300:]
                    job['t_end'] = time.time(); self.cut_cur = None; self._cut_persist()
                else: time.sleep(0.5)
            except Exception: time.sleep(2)

    def _cut_out_ext(self, src, mode):
        ext = Path(src).suffix.lower()
        return '.mp4' if mode != 'copy' or ext in ('.mp4', '.m4v', '.mov') else '.mkv'

    def _cut_one(self, src, a, b, out, mode):
        """回傳 (ok, out_path, err)."""
        enc = self.enc_args(None, for_cut=True) if mode != 'copy' else None
        tries = []
        if mode == 'copy':
            tries.append(('copy', out))
            if out.suffix != '.mkv': tries.append(('copy', out.with_suffix('.mkv')))
        tries.append(('enc', out.with_suffix('.mp4')))
        err = ''
        for ti, (kind, o) in enumerate(tries):
            o = unique_path(o); tmp = o.with_name(o.stem + '.part' + o.suffix)
            if kind == 'copy':
                cmd = [self.ff, '-hide_banner', '-nostdin', '-loglevel', 'error', '-y', '-ss', f'{a:.3f}', '-i', str(src), '-t', f'{b - a:.3f}',
                       '-map', '0:v:0?', '-map', '0:a?', '-c', 'copy', '-avoid_negative_ts', 'make_zero'] + (['-movflags', '+faststart'] if o.suffix == '.mp4' else []) + \
                      ['-progress', 'pipe:1', '-nostats', str(tmp)]
            else:
                e = enc or self.enc_args(None, for_cut=True)
                cmd = [self.ff, '-hide_banner', '-nostdin', '-loglevel', 'error', '-y'] + e['pre'] + ['-ss', f'{a:.3f}', '-i', str(src), '-t', f'{b - a:.3f}',
                       '-map', '0:v:0?', '-map', '0:a?'] + e['v'] + ['-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-progress', 'pipe:1', '-nostats', str(tmp)]
            o.parent.mkdir(parents=True, exist_ok=True)
            P = Proc(cmd, 'normal').start(); self.procs.add(P); rc = P.wait(stop=lambda: self.stop_all, stall=300); self.procs.discard(P)
            if rc == 0 and tmp.exists() and tmp.stat().st_size > 1000:
                os.replace(str(tmp), str(o)); self.log.w(f'　初剪一段好了（{"免轉檔" if kind == "copy" else "重新壓縮"}）：{fmt_t(a)}～{fmt_t(b)} → {o}（{fmt_b(o.stat().st_size)}）'); return True, o, ''
            err = P.errtext() or f'ffmpeg {rc}'; self.log.w(f'　初剪一段失敗（{kind}，{"改用下一個方法" if ti < len(tries) - 1 else "沒有別的方法了"}）：{src}　{fmt_t(a)}～{fmt_t(b)}：{err[-300:]}\n　指令：{cmd_text(cmd)}')
            try: tmp.unlink()
            except Exception: pass
        return False, None, err

    def cut_next_no(self, od, base):
        """同一個資料夾裡已經有 base_01、base_02… 的話，接著編號."""
        n = 0; rx = re.compile(re.escape(base) + r'_(\d{2,})(?: \(\d+\))?$')
        try:
            for p in Path(od).iterdir():
                m = rx.match(p.stem)
                if m: n = max(n, int(m.group(1)))
        except Exception: pass
        return n + 1

    def cut_names(self, path, nseg, merge, mode=None):
        """給確認視窗看的：會用的檔名（例：abc_01.mp4、abc_02.mp4 或 abc_ALL.mp4）和怎麼來的."""
        src = Path(path); od = self.arch_dir('cut', src, self.cfg.get('cut_dir')); ext = self._cut_out_ext(src, mode or self.cfg.get('cut_mode') or 'copy')
        base, how = cut_base_name(src.stem)
        if merge: return [f'{base}_ALL{ext}'], how
        n0 = self.cut_next_no(od, base); return [f'{base}_{n0 + i:02d}{ext}' for i in range(nseg)], how

    def _cut_job(self, job):
        t = job['task']; src = Path(job['path']); od = self.arch_dir('cut', src, self.cfg.get('cut_dir')); mode = job['mode']
        ext = self._cut_out_ext(src, mode); outs = []; err = ''
        segs = job['segs']; tot = sum(b - a for a, b in segs) or 1; done_s = 0
        base, how = cut_base_name(src.stem); no0 = self.cut_next_no(od, base); seg_out = []
        try:
            r0 = self.file(job['fid']) or {}; d0 = float(r0.get('dur') or 0)
            need_space(od, float(r0.get('size') or 0) * (min(1.0, tot / d0) if d0 else 1.0) * (2.1 if job['merge'] else 1.1))   # 合併時暫時要兩倍
        except RuntimeError as ex:
            job['outs'] = []; job['err'] = str(ex); job['state'] = 'fail'; self.done(t, 'fail', str(ex)); self.log.w(f'初剪沒做：{src}：{ex}'); return
        if how: self.log.w(f'初剪檔名：{src.stem} → {base}（{how}）')
        for i, (a, b) in enumerate(segs):
            nm = f'{base}_{no0 + i:02d}{ext}'
            ok, o, e = self._cut_one(src, a, b, (od / nm) if not job['merge'] else (od / f'.vs_tmp_{int(time.time())}_{i}{ext}'), mode)
            if ok: outs.append(o)
            else: err = e
            seg_out.append(o if ok else None)
            done_s += b - a; t['pct'] = round(done_s / tot * 100); t['msg'] = f'{i + 1}/{len(segs)} 段'
        if job['merge'] and len(outs) > 1:
            lst = od / f'.vs_concat_{int(time.time())}.txt'
            lst.write_text(''.join("file '" + str(Path(o).resolve()).replace("'", "'\\''") + "'\n" for o in outs), encoding='utf-8')
            final = unique_path(od / f'{base}_ALL{outs[0].suffix}')
            rc, _o, e = run([self.ff, '-hide_banner', '-nostdin', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy'] +
                            (['-movflags', '+faststart'] if final.suffix == '.mp4' else []) + [str(final)], timeout=3600)
            try: lst.unlink()
            except Exception: pass
            if rc == 0 and final.exists():
                for o in outs:
                    try: o.unlink()
                    except Exception: pass
                outs = [final]
            else:
                err = e or f'合併失敗 {rc}'
                kept = []
                for k, o in enumerate(outs):                                     # 合併不成：至少每段留著（_01、_02…）
                    try: q = unique_path(od / f'{base}_{no0 + k:02d}{o.suffix}'); os.replace(str(o), str(q)); kept.append(q)
                    except Exception: kept.append(o)
                outs = kept; it = iter(kept); seg_out = [next(it, None) if x is not None else None for x in seg_out]
        elif job['merge'] and len(outs) == 1:
            o = outs[0]; final = unique_path(od / f'{base}_ALL{o.suffix}')
            os.replace(str(o), str(final)); outs = [final]
        merged = job['merge'] and len(outs) == 1
        for k, (a, b) in enumerate(segs):
            o = outs[0] if merged else (seg_out[k] if k < len(seg_out) else None)
            self.db.x('INSERT INTO cuts(file_id,a,b,out,mode,state,err,t) VALUES(?,?,?,?,?,?,?,?)', (job['fid'], a, b, str(o) if o else '', mode, 1 if o else 2, '' if o else err[-300:], time.time()))
        self.db.x('UPDATE files SET cut_n=cut_n+? WHERE id=?', (len(segs) if outs else 0, job['fid']))
        if outs:
            self.done(t, 'done' if not err else 'fail', f'{len(outs)} 個檔 → {od}' + (f'（有一段沒成功：{err[-120:]}）' if err else ''))
            self.log.w(f'初剪：{src} → {", ".join(o.name for o in outs)}')
            try:                                                                # V0.3.49 📤 剪好自動複製到上傳資料夾
                L_ = self.cfg.get('lab') or {}
                if L_.get('copy_to') and L_.get('copy_after_cut'):
                    M_ = self._cut_src = getattr(self, '_cut_src', None) or {}
                    for o_ in outs: M_[str(o_)] = int(job['fid'])
                    self.copy_enqueue([str(o_) for o_ in outs])
            except Exception: self.log.err('剪好自動複製')
            for o in outs: self.oplog('cut', src=str(src), dst=str(o), fid=job['fid'], size=Path(o).stat().st_size if Path(o).exists() else 0, detail=f'初剪（{"免轉檔" if mode == "copy" else "重新壓縮"}，{len(segs)} 段，{"合併" if job["merge"] else "分段"}）')
        else:
            self.done(t, 'fail', err[-200:]); self.log.w(f'初剪失敗：{src}：{err[-300:]}')
        job['outs'] = [str(o) for o in outs]; job['err'] = err[-300:]; job['state'] = ('done' if not err else 'part') if outs else 'fail'

    # ---------- 收藏／待刪（搬或複製到歸檔資料夾）
    def file_op(self, fid, kind, batch=''):
        r = self.db.one('SELECT * FROM files WHERE id=?', (int(fid),))
        if not r: return {'ok': False, 'message': '找不到這部影片'}
        label = ''
        if kind == 'fav':
            dst = self.arch_dir('fav', r['path'], self.cfg.get('fav_dir')); mode = self.cfg.get('fav_mode') or 'copy'
        elif kind == 'trash':
            dst = self.arch_dir('trash', r['path'], self.cfg.get('trash_dir')); mode = 'move'
        elif kind.startswith('grade:') or kind.startswith('cat:'):
            label = self.arch_label(kind)
            if not label: return {'ok': False, 'message': '不認得的歸檔資料夾'}
            if kind == 'grade:F' and self.cfg.get('arch_f_trash'):
                dst = self.arch_dir('trash', r['path'], self.cfg.get('trash_dir')); kind = 'trash'; label = ''
            else: dst = self.arch_target(label, r['path'])
            mode = 'move'
        else: return {'ok': False, 'message': '不認得'}
        nm = {'fav': '收藏', 'trash': '待刪'}.get(kind, f'歸檔到 {label}')
        t = self.task('op', f'{nm}：{r["name"]}'); t['state'] = 'wait'
        self.op_q.append({'fid': int(fid), 'kind': kind, 'label': label, 'src': r['path'], 'dst': str(dst), 'mode': mode, 'task': t, 'batch': batch})
        return {'ok': True, 'message': f'{nm}：{"複製" if mode == "copy" else "搬"}到 {dst}'}

    def _op_boss(self):
        while self.alive():
            try:
                if self.op_q and not self.bg_hold('op'):
                    j = self.op_q.popleft(); self.bg_mark('op', j.get('title') or j.get('name')); self.op_cur = j; j['task']['state'] = 'run'
                    try: self._op_job(j)
                    except Exception as ex: self.log.err('搬檔'); self.done(j['task'], 'fail', str(ex)[-200:])
                    self.op_cur = None
                else: time.sleep(0.5)
            except Exception: time.sleep(2)

    def copy_file(self, src, dst, t=None, move=False):
        src = Path(src); dst = unique_path(Path(dst)); dst.parent.mkdir(parents=True, exist_ok=True)
        if move:
            try:
                os.replace(str(src), str(dst)); return dst                      # 同一顆硬碟：一下就好
            except OSError: pass
        tmp = dst.with_name(dst.name + '.vspart'); size = src.stat().st_size; got = 0; need_space(dst.parent, size, 2e8)
        with open(src, 'rb') as fi, open(tmp, 'wb') as fo:
            while True:
                if self.stop_all: raise InterruptedError('停止')
                b = fi.read(8 << 20)
                if not b: break
                fo.write(b); got += len(b)
                if t is not None and size: t['pct'] = round(got / size * 100)
        if tmp.stat().st_size != size: raise IOError('大小不對，沒有完成')
        try: shutil.copystat(str(src), str(tmp))
        except Exception: pass
        os.replace(str(tmp), str(dst))
        if move: src.unlink()
        return dst

    def changed_since_scan(self, r):
        """檔案在掃描之後被換掉或改過嗎？（大小或修改時間不一樣）→ 回傳原因，沒變回傳 ''."""
        try: st = os.stat(r['path'])
        except OSError: return '檔案已經不在了'
        if r['size'] is not None and st.st_size != int(r['size'] or 0):
            a, b = fmt_b(r['size']), fmt_b(st.st_size)
            return f'大小變了（{a} → {b}）' if a != b else f'大小變了（{int(r["size"]):,} → {st.st_size:,} bytes）'
        if r['mtime'] and abs(st.st_mtime - float(r['mtime'])) > 2: return '修改時間變了'
        return ''

    def _op_job(self, j):
        t = j['task']; src = Path(j['src'])
        if not src.exists(): self.done(t, 'fail', '原檔不見了'); return
        r = self.file(j['fid'])
        why = self.changed_since_scan(r) if r and j['mode'] == 'move' else ''
        if why:
            self.done(t, 'fail', f'為了安全沒有搬：{why}，請重新掃描'); self.log.w(f'{"收藏" if j["kind"] == "fav" else "待刪"}取消（檔案在掃描後被改過：{why}）：{src}'); return
        size = src.stat().st_size
        dst = self.copy_file(src, Path(j['dst']) / src.name, t, move=(j['mode'] == 'move'))
        if j['mode'] == 'move' and EXT_MOVED.get('fn'):                         # V0.5.38 整理（FileCompare）的紀錄跟著搬（不用重算指紋）
            try: EXT_MOVED['fn'](str(src), str(dst))
            except Exception: pass
        if j['kind'] == 'fav': self.db.x('UPDATE files SET fav=1 WHERE id=?', (j['fid'],))
        if j.get('label'):                                                      # 歸檔：這一筆跟著走（在 VideoSIFT 裡，清單不再列；可以從操作紀錄搬回來）
            self.db.x('UPDATE files SET path=?, folder=?, name=?, arch=? WHERE id=?', (str(dst), str(dst.parent), dst.name, j['label'], j['fid']))
        elif j['mode'] == 'move':
            self.db.x('UPDATE files SET missing=1 WHERE id=?', (j['fid'],))
        self.db.x('INSERT INTO ops(kind,src,dst,t,ok) VALUES(?,?,?,?,1)', (j['kind'], str(src), str(dst), time.time()))
        nm = {'fav': '收藏', 'trash': '待刪'}.get(j['kind'], f'歸檔（{j.get("label")}）')
        self.oplog('arch' if j.get('label') else j['kind'], src=str(src), dst=str(dst), fid=j['fid'], size=size, batch=j.get('batch', ''),
                   detail=f'{nm}・{"搬" if j["mode"] == "move" else "複製"}' + (f'・改名為 {dst.name}' if dst.name != src.name else ''))
        self.done(t, 'done', f'→ {dst}'); self.log.w(f'{nm}（{"搬" if j["mode"] == "move" else "複製"}）：{src} → {dst}')

    # ---------- 分級／分類歸檔（都在每顆硬碟的 VideoSIFT\ 底下）
    def arch_label(self, kind):
        if kind.startswith('grade:'):
            g = kind[6:]; return str((self.cfg.get('arch_names') or {}).get(g) or DEFAULTS['arch_names'].get(g) or '')
        if kind.startswith('cat:'):
            c = kind[4:]; return safe_name(c) if c in (self.cfg.get('cats') or []) else ''
        return ''

    def arch_target(self, label, src):
        src = Path(src); r = self.root_of(src); rp = Path(r) if r else Path(src.anchor or src.parent)
        base = Path(src.anchor or rp) / ARCH_BASE / safe_name(label)
        if not self.cfg.get('arch_tree'): return base
        try: rel = src.parent.relative_to(rp)
        except Exception: rel = Path()
        return base / (safe_name(rp.name) if rp.name else '') / rel

    def add_cat(self, name):
        name = safe_name(str(name).strip())[:60]
        if not name or name in ('初剪', '收藏', '待刪', '原檔備份'): return False
        C = list(self.cfg.get('cats') or [])
        if name in C: return False
        self.cfg.set('cats', C + [name]); self.oplog('cat', dst=name, detail='新增分類資料夾'); return True

    def remove_cat(self, name):
        C = [c for c in self.cfg.get('cats') or [] if c != name]; self.cfg.set('cats', C); self.oplog('cat', src=name, detail='移除分類（資料夾和裡面的檔案不動）')

    def grade_counts(self, folder=''):
        """一鍵歸檔選單用：目前範圍裡每個分級幾部、多大."""
        w = ["missing=0", "arch=''", "grade!=''"]; a = []
        if folder:
            f = str(folder).rstrip('\\/'); w.append('(folder=? OR substr(folder,1,?)=? OR substr(folder,1,?)=?)'); a += [f, len(f) + 1, f + '\\', len(f) + 1, f + '/']
        return {r[0]: (r[1], r[2] or 0) for r in self.db.q(f'SELECT grade, COUNT(*), SUM(size) FROM files WHERE {" AND ".join(w)} GROUP BY grade', a)}

    # ---------- V0.1.51 檔案總管篩掉檔案類型（遠端／手機只能播 MP4：其他格式預設不列出來；轉檔頁照樣看得到）
    def hidden_exts(self):
        v = self.cfg.get('hide_exts')
        if v is None: return sorted(VIDEO_EXT - MP4_EXT)                         # 預設：只列 MP4／M4V
        return sorted({('.' + str(x).lower().lstrip('.')) for x in v if str(x).strip()})

    def ext_sql(self):
        H = self.hidden_exts()
        return (f"ext NOT IN ({','.join('?' * len(H))})", list(H)) if H else ('', [])

    def hidden_count(self, folder='', sub=True):
        """被篩掉沒列出來的有幾部（依類型）：[(ext, n)]."""
        H = self.hidden_exts()
        if not H: return []
        w = ["missing=0", "arch=''", f"ext IN ({','.join('?' * len(H))})"]; a = list(H)
        if folder:
            f = str(folder).rstrip('\\/')
            if sub: w.append('(folder=? OR substr(folder,1,?)=? OR substr(folder,1,?)=?)'); a += [f, len(f) + 1, f + '\\', len(f) + 1, f + '/']
            else: w.append('folder=?'); a.append(str(folder))
        return [tuple(r) for r in self.db.q(f'SELECT ext, COUNT(*) FROM files WHERE {" AND ".join(w)} GROUP BY ext ORDER BY 2 DESC', a)]

    def ext_counts(self):
        """影片庫裡每種格式幾部（設定頁勾選用）."""
        return {r[0]: r[1] for r in self.db.q("SELECT ext, COUNT(*) FROM files WHERE missing=0 GROUP BY ext")}

    def grade_summary(self, folder='', sub=True):
        """分級標籤列用：目前資料夾裡（還沒歸檔的）全部幾部、未分級幾部、S／A／E／F 各幾部."""
        w = ["missing=0", "arch=''"]; a = []
        if folder:
            f = str(folder).rstrip('\\/')
            if sub: w.append('(folder=? OR substr(folder,1,?)=? OR substr(folder,1,?)=?)'); a += [f, len(f) + 1, f + '\\', len(f) + 1, f + '/']
            else: w.append('folder=?'); a.append(str(folder))
        es, ea = self.ext_sql()
        if es: w.append(es); a += ea
        out = {'all': 0, 'ready': 0, 'nograde': 0, 'S': 0, 'A': 0, 'E': 0, 'F': 0}; B = dict.fromkeys(out, 0)
        for g, th, n, sz in self.db.q(f'SELECT grade, th_state=2, COUNT(*), SUM(size) FROM files WHERE {" AND ".join(w)} GROUP BY grade, th_state=2', a):
            k = g if g in ('S', 'A', 'E', 'F') else 'nograde'; sz = int(sz or 0); out['all'] += n; out[k] += n; B['all'] += sz; B[k] += sz
            if k == 'nograde' and th: out['ready'] += n; B['ready'] += sz         # V0.1.94 可以審＝預覽圖好了、還沒分級
        out['bytes'] = B                                                        # V0.2.04 每個標籤下面一行顯示總大小
        return out

    def grade_ids(self, grade, folder=''):
        w = ["missing=0", "arch=''", "grade=?"]; a = [grade]
        if folder:
            f = str(folder).rstrip('\\/'); w.append('(folder=? OR substr(folder,1,?)=? OR substr(folder,1,?)=?)'); a += [f, len(f) + 1, f + '\\', len(f) + 1, f + '/']
        es, ea = self.ext_sql()
        if es: w.append(es); a += ea
        return [r[0] for r in self.db.q(f'SELECT id FROM files WHERE {" AND ".join(w)} ORDER BY folder, name', a)]

    def archive_many(self, ids, kind):
        """kind＝'grade:S'／'cat:工作用'／'trash'. 排進搬檔隊伍（一部一部搬，後台看進度）."""
        batch = time.strftime('%Y%m%d_%H%M%S') + f'_{kind}'; res = [self.file_op(i, kind, batch) for i in ids]
        n = sum(1 for x in res if x.get('ok')); self.log.w(f'批量歸檔排隊：{kind}，{n}/{len(ids)} 部（批次 {batch}）'); return n

    # ---------- 🧪 實驗工作區
    def find_dupes(self, limit=500):
        """可能重複的影片：大小一樣、或長度一樣（差 1 秒內）而且大小差不到 2%。回傳 [[file…], …]（每組照大小排）."""
        R = [dict(r) for r in self.db.q("SELECT id,path,folder,name,size,dur,w,h,grade FROM files WHERE missing=0 AND arch='' AND size>0")]
        groups = {}
        for r in R: groups.setdefault(('s', r['size']), []).append(r)
        bydur = {}
        for r in R:
            if r['dur'] and r['dur'] > 5: bydur.setdefault(int(round(r['dur'])), []).append(r)
        seen = set(); out = []
        for g in [v for v in groups.values() if len(v) > 1]:
            key = tuple(sorted(x['id'] for x in g))
            if key not in seen: seen.add(key); out.append(g)
        for d, g in bydur.items():
            g = g + bydur.get(d + 1, [])
            g = sorted(g, key=lambda x: x['size'])
            for i, a in enumerate(g):
                grp = [a] + [b for b in g[i + 1:] if b['id'] != a['id'] and abs(b['size'] - a['size']) <= a['size'] * 0.02]
                if len(grp) > 1:
                    key = tuple(sorted(x['id'] for x in grp))
                    if key not in seen and not any(set(key) <= set(k) for k in seen): seen.add(key); out.append(grp)
        out.sort(key=lambda g: -sum(x['size'] for x in g)); self.log.w(f'實驗：找重複影片，{len(out)} 組')
        return out[:limit]

    # ---------- 🧪 找畫面相似的影片（V0.1.36）：只看已經做好的預覽圖，不讀影片、不碰 HDD
    VFP_N = 16

    def vfp_make(self, r):
        """畫面指紋：整張預覽圖縮成每格 9×8 灰階（一次 ffmpeg 就拿到整張的每一格），挑 16 個平均分布的位置算 dHash（每格 64 位元）。
        回傳 '十六進位,…'；預覽圖讀不到回傳 ''."""
        d = Path(r['th_dir'] or ''); cols = int(r['th_cols'] or 10); rows = int(r['th_rows'] or 10); n = int(r['th_n'] or 0)
        try: sheets = sorted(d.glob('s*.jpg')) if r['th_dir'] else []
        except Exception: sheets = []
        if n < 2 or not sheets or not self.ff: return ''
        per = cols * rows; want = sorted({min(n - 1, int((i + 0.5) * n / self.VFP_N)) for i in range(self.VFP_N)}); tiles = {}; W = cols * 9
        for si in sorted({k // per for k in want}):
            if si >= len(sheets): continue
            cmd = [self.ff, '-hide_banner', '-loglevel', 'error', '-nostdin', '-i', str(sheets[si]), '-vf', f'scale={W}:{rows * 8}:flags=area,format=gray', '-frames:v', '1', '-f', 'rawvideo', '-']
            try: p = subprocess.run(cmd, capture_output=True, timeout=30, creationflags=NO_WINDOW | PRIO.get('below', 0), stdin=subprocess.DEVNULL)
            except Exception: continue
            b = p.stdout
            if p.returncode or len(b) < W * rows * 8: continue
            for k in want:
                if k // per != si: continue
                q = k % per; x0 = (q % cols) * 9; y0 = (q // cols) * 8; h = 0
                for y in range(8):
                    o = (y0 + y) * W + x0
                    for x in range(8): h = (h << 1) | (1 if b[o + x] < b[o + x + 1] else 0)
                tiles[k] = h
        if len(tiles) < len(want): return ''
        return ','.join(f'{tiles[k]:016x}' for k in want)

    def scene_cuts(self, fid):
        """V0.3.09 🎬 場景切換：用預覽圖（每格縮成 8×8 灰階）比前後兩格差多少，差很多＝換場景 → [第幾張預覽圖（原始編號）]；有快取."""
        C = self._sc_c = getattr(self, '_sc_c', None) or {}
        r = self.file(fid)
        if not r or int(r.get('th_state') or 0) != 2 or not self.ff: return []
        key = (int(fid), float(r.get('th_t') or 0))
        if key in C and key in (getattr(self, '_st_c', None) or {}): return C[key]
        d = Path(r.get('th_dir') or ''); cols = int(r.get('th_cols') or 10); rows = int(r.get('th_rows') or 10); n = int(r.get('th_n') or 0); per = cols * rows
        try: sheets = sorted(d.glob('s*.jpg'))
        except Exception: sheets = []
        vec = []
        for si, sh in enumerate(sheets):
            W = cols * 8
            cmd = [self.ff, '-hide_banner', '-loglevel', 'error', '-nostdin', '-i', str(sh), '-vf', f'scale={W}:{rows * 8}:flags=area,format=gray', '-frames:v', '1', '-f', 'rawvideo', '-']
            try: p = subprocess.run(cmd, capture_output=True, timeout=30, creationflags=NO_WINDOW | PRIO.get('below', 0), stdin=subprocess.DEVNULL)
            except Exception: break
            b = p.stdout
            if p.returncode or len(b) < W * rows * 8: break
            for q in range(per):
                k = si * per + q
                if k >= n: break
                x0 = (q % cols) * 8; y0 = (q // cols) * 8
                vec.append([b[(y0 + y) * W + x0 + x] for y in range(8) for x in range(8)])
        if len(vec) < 3: C[key] = []; self._st_c = getattr(self, '_st_c', {}); self._st_c[key] = []; return []
        D = [sum(abs(a - b_) for a, b_ in zip(vec[i - 1], vec[i])) / 64.0 for i in range(1, len(vec))]
        med = sorted(D)[len(D) // 2] if D else 0
        thr = max(22.0, med * 3.0); out = []
        for i, dv in enumerate(D, start=1):
            if dv >= thr and (not out or i - out[-1] >= 2): out.append(i)
        C[key] = out
        st = []; run = None                                                      # V0.3.11 😴 靜止／全黑：連續好幾格幾乎沒變（或很暗）
        for i in range(len(vec)):
            dark = sum(vec[i]) / 64.0 < 14; same = i > 0 and D[i - 1] < 2.5
            if dark or same:
                if run is None: run = [max(0, i - 1) if same and not dark else i, i]
                else: run[1] = i
            else:
                if run and run[1] - run[0] + 1 >= 5: st.append((run[0], run[1]))
                run = None
        if run and run[1] - run[0] + 1 >= 5: st.append((run[0], run[1]))
        self._st_c = getattr(self, '_st_c', None) or {}; self._st_c[key] = st
        try:                                                                    # V0.3.16 🔥 畫面動得最多的地方（前 10%，至少要比中位數大很多）
            Sm = [0.0] + [(D[max(0, i - 2)] + D[i - 1] + D[min(len(D) - 1, i)]) / 3.0 for i in range(1, len(vec))]
            stset = {b_ for a_, z_ in st for b_ in range(a_, z_ + 1)}
            srt = sorted(Sm); p90 = srt[int(len(srt) * 0.9)] if srt else 0
            th_ = max(12.0, p90, med * 2.0)
            self._hl_c = getattr(self, '_hl_c', None) or {}; self._hl_c[key] = [i for i, v_ in enumerate(Sm) if v_ >= th_ and i not in stset and i not in out]
            lo_, hi_ = int(len(Sm) * 0.1), max(int(len(Sm) * 0.1), int(len(Sm) * 0.9) - 1)            # V0.3.22 🖼 最精彩的一格（避開頭尾 10%、靜止、換場景那格）
            cand = [i for i in range(lo_, hi_ + 1) if i not in stset and i not in out]
            self._bt_c = getattr(self, '_bt_c', None) or {}; self._bt_c[key] = max(cand, key=lambda i: Sm[i]) if cand else -1
            if len(self._bt_c) > 300: self._bt_c.pop(next(iter(self._bt_c)))
            if len(self._hl_c) > 300: self._hl_c.pop(next(iter(self._hl_c)))
        except Exception: pass
        if len(C) > 300: C.pop(next(iter(C)))
        if len(self._st_c) > 300: self._st_c.pop(next(iter(self._st_c)))
        return out

    def highlights(self, fid):
        """V0.3.16 🔥 動得最多的預覽圖編號（換場景那一格不算）."""
        r = self.file(fid)
        if not r: return []
        key = (int(fid), float(r.get('th_t') or 0))
        if key not in (getattr(self, '_hl_c', None) or {}): self._sc_c = getattr(self, '_sc_c', None) or {}; self._sc_c.pop(key, None); self.scene_cuts(fid)
        return list((getattr(self, '_hl_c', None) or {}).get(key) or [])

    def cut_skip_static(self, ids, min_keep=0.15):
        """V0.3.47 ✂ 批次：每部「剪掉 😴 靜止／黑畫面」，有內容的合成一個檔（原檔不動）→ (排了幾部, 說明)."""
        n = 0; skip = 0
        for fid in ids:
            try:
                f = self.file(int(fid))
                if not f or int(f.get('th_state') or 0) != 2: skip += 1; continue
                self.scene_cuts(int(fid)); S_ = self.static_runs(int(fid)); st = max(1, int(f.get('th_step') or 2)); N = int(f.get('th_n') or 0); dur = float(f.get('dur') or N * st)
                if not S_: skip += 1; continue
                segs = []; cur = 0.0
                for a, z in S_:
                    a_t, z_t = a * st, (z + 1) * st
                    if a_t - cur >= 2: segs.append((cur, a_t))
                    cur = max(cur, z_t)
                if dur - cur >= 2: segs.append((cur, dur))
                if not segs or sum(b - a for a, b in segs) < dur * min_keep: skip += 1; continue      # 幾乎全部都是靜止的＝不剪（直接標 F 比較快）
                r = self.cut_add(int(fid), segs, merge=True)
                if r.get('ok'): n += 1
                else: skip += 1
            except Exception: self.log.err('批次剪掉靜止'); skip += 1
        self.log.w(f'✂ 批次剪掉靜止：排了 {n} 部，跳過 {skip} 部'); return n, f'✂ 排了 {n} 部去剪（有內容的合成一個檔，原檔不動）' + (f'，跳過 {skip} 部（沒有靜止段落／幾乎全靜止／預覽圖沒好）' if skip else '')

    def still_tick(self):
        """V0.3.12 😴 背景慢慢算每部「靜止佔幾 %」（一次一部；已經算過、預覽圖沒好的跳過）→ 回傳算了哪一部."""
        if not getattr(self, '_still_reset', False):                             # 每次開程式：上次「硬碟沒接上」的再試一次
            self._still_reset = True
            try: self.db.x('UPDATE files SET still=-1 WHERE still=-2')
            except Exception: pass
        r = self.db.one("SELECT id, th_n, th_dir FROM files WHERE missing=0 AND th_state=2 AND th_n>2 AND still=-1 AND substr(path,1,1)!='|' LIMIT 1")
        if not r and (self.cfg.get('lab') or {}).get('smart_card'):              # V0.3.23 之前算過靜止、後來才打開 🖼 的：補換卡片縮圖
            r2 = self.db.one("SELECT id, th_n, th_dir, th_t FROM files WHERE missing=0 AND th_state=2 AND th_n>2 AND still>=0 AND card_k<0 AND substr(path,1,1)!='|' LIMIT 1")
            if not r2: return None
            fid = int(r2[0]); n = int(r2[1] or 0); bt = -1
            try:
                if r2[2] and Path(r2[2]).is_dir(): self.scene_cuts(fid); bt = (getattr(self, '_bt_c', None) or {}).get((fid, float(r2[3] or 0)), -1)
            except Exception: bt = -1
            if bt is None or bt < 0: lo = int(n * 0.1); bt = random.Random(fid * 7919).randint(lo, max(lo, int(n * 0.9) - 1))   # 算不出來＝用原本那張（不會一直重算）
            self.db.x('UPDATE files SET card_k=? WHERE id=?', (int(bt), fid)); return fid
        if not r: return None
        fid = int(r[0]); n = int(r[1] or 0)
        try: ok_ = bool(r[2]) and Path(r[2]).is_dir()
        except Exception: ok_ = False
        if not ok_: self.db.x('UPDATE files SET still=-2 WHERE id=?', (fid,)); return fid      # 預覽圖那顆硬碟沒接上：先跳過，下次開程式再試
        try: self.scene_cuts(fid); S_ = self.static_runs(fid); v = round(sum(z - a + 1 for a, z in S_) / max(1, n), 3)
        except Exception: v = 0.0
        self.db.x('UPDATE files SET still=? WHERE id=?', (v, fid))
        if (self.cfg.get('lab') or {}).get('smart_card'):                         # V0.3.22 🖼 卡片縮圖自動挑最精彩那格（自己換過的不動）
            try:
                r2 = self.file(fid); bt = (getattr(self, '_bt_c', None) or {}).get((fid, float(r2.get('th_t') or 0)), -1)
                if bt is not None and bt >= 0 and int(r2.get('card_k') if r2.get('card_k') is not None else -1) < 0: self.db.x('UPDATE files SET card_k=? WHERE id=?', (int(bt), fid))
            except Exception: pass
        return fid

    def still_left_c(self):
        """V0.3.25 同 still_left，30 秒快取（手機每幾秒問一次）."""
        c = getattr(self, '_sl_c', None)
        if c and time.time() - c[0] < 30: return c[1]
        v = self.still_left(); self._sl_c = (time.time(), v); return v

    def still_left(self):
        try: return int(self.db.one("SELECT COUNT(*) FROM files WHERE missing=0 AND th_state=2 AND th_n>2 AND substr(path,1,1)!='|' AND (still=-1" + (" OR (still>=0 AND card_k<0)" if (self.cfg.get('lab') or {}).get('smart_card') else '') + ")")[0] or 0)
        except Exception: return 0

    def static_runs(self, fid):
        """V0.3.11 😴 靜止／全黑的段落：[(從第幾張, 到第幾張)]（連續 5 張以上；直播主離開、黑畫面）."""
        r = self.file(fid)
        if not r: return []
        key = (int(fid), float(r.get('th_t') or 0))
        if key not in (getattr(self, '_st_c', None) or {}): self.scene_cuts(fid)
        return list((getattr(self, '_st_c', None) or {}).get(key) or [])

    def vfp_fill(self, progress=None, dur_range=None):
        """還沒有指紋（或預覽圖重做過）的影片補算。dur_range=(最短, 最長)＝只算這個長度範圍的。回傳 (算了幾部, 失敗幾部).
        失敗的（vfp_t 記成 -1、-2…）之後再試，最多 3 次；找不到 ffmpeg 就整個不做（不記失敗）."""
        if not self.ff: return 0, 0
        extra, a = ('AND dur BETWEEN ? AND ?', tuple(dur_range)) if dur_range else ('', ())
        R = [dict(x) for x in self.db.q(f"SELECT id,name,th_dir,th_n,th_cols,th_rows,th_t,vfp_t FROM files WHERE missing=0 AND length(arch)=0 AND th_state=2 AND th_n>=2 "
                                        f"AND (vfp_t IS NULL OR (vfp_t!=th_t AND vfp_t>-3)) {extra}", a)]
        done = bad = 0; t0 = time.time(); self.vfp_cancel = False
        for i, r in enumerate(R):
            if self.stop_all or getattr(self, 'vfp_cancel', False): break
            fp = ''
            try: fp = self.vfp_make(r)
            except Exception: self.log.err(f'畫面指紋 {r["name"]}')
            vt = r['th_t'] or 0
            if not fp: o = r.get('vfp_t') or 0; vt = (o - 1) if o <= 0 else -1          # 失敗：-1、-2、-3 次
            self.db.x('UPDATE files SET vfp=?, vfp_t=? WHERE id=?', (fp, vt, r['id']))
            done += 1; bad += 0 if fp else 1
            if progress and (i % 20 == 0 or i == len(R) - 1): progress(i + 1, len(R))
        if R: self.log.w(f'實驗：畫面指紋補算 {done:,} 部（讀不到 {bad:,} 部），花 {time.time() - t0:.0f} 秒')
        return done, bad

    VFP_FLAT = (0, 0xFFFFFFFFFFFFFFFF)

    @classmethod
    def vfp_parse(cls, txt):
        """'十六進位,…' → 固定 16 格的 tuple（全黑／全平的格子＝None，不拿來比）。不足 16 格的平均拉成 16 格."""
        v = [int(x, 16) for x in str(txt or '').split(',') if x]
        if not v: return ()
        n = cls.VFP_N; v = [v[int(i * len(v) / n)] for i in range(n)] if len(v) != n else v
        return tuple(None if x in cls.VFP_FLAT else x for x in v)

    @classmethod
    def vfp_dist(cls, a, b):
        """兩部影片指紋的平均差異（0＝一樣，64＝完全不同）。能比的格子太少回傳 99。a、b 可以是 vfp_parse 的結果或舊的 list."""
        if not a or not b: return 99
        if len(a) != cls.VFP_N or len(b) != cls.VFP_N:
            a = cls.vfp_parse(','.join(f'{x:x}' for x in a if x is not None) if not isinstance(a, str) else a); b = cls.vfp_parse(','.join(f'{x:x}' for x in b if x is not None) if not isinstance(b, str) else b)
            if not a or not b: return 99
        tot = cnt = 0
        for x, y in zip(a, b):
            if x is None or y is None: continue
            tot += (x ^ y).bit_count(); cnt += 1
        if cnt < max(4, cls.VFP_N // 2): return 99
        return tot / cnt

    def similar_to(self, fid, thr=12, progress=None):
        """🧪 跟這一部畫面相似的（只比長度差 5% 以內的，第一次只補算那些的指紋，很快）。
        回傳 [這部＋相似的…]（照大小排，多 'dist'＝跟你選的那部差多少、'big'＝最大的那部、'me'＝你選的那部）；找不到相似的回傳 [這部]，沒有指紋回傳 []."""
        f = self.file(fid)
        if not f or not f.get('dur'): return []
        lo, hi = (f['dur'] - 1) / 1.05, f['dur'] * 1.05 + 1; t0 = time.time(); self.vfp_fill(progress, (lo, hi))
        me = self.db.one('SELECT vfp FROM files WHERE id=?', (int(fid),)); mfp = self.vfp_parse(me[0] if me else '')
        if not mfp: return []
        out = []
        for r in map(dict, self.db.q("SELECT id,path,folder,name,size,dur,w,h,grade,vfp FROM files WHERE missing=0 AND length(arch)=0 AND length(vfp)>0 AND dur BETWEEN ? AND ? AND id!=?", (lo, hi, int(fid)))):
            d = self.vfp_dist(mfp, self.vfp_parse(r['vfp']))
            if d <= thr: r['dist'] = round(d, 1); r.pop('vfp', None); out.append(r)
        head = {k: f.get(k) for k in ('id', 'path', 'folder', 'name', 'size', 'dur', 'w', 'h', 'grade')}; head['dist'] = 0.0; head['me'] = True
        g = sorted([head] + out, key=lambda r: (-(r['size'] or 0), -((r['w'] or 0) * (r['h'] or 0))))
        if len(g) > 1: g[0]['big'] = True
        self.log.w(f'實驗：跟「{f["name"]}」畫面相似的：{len(out)} 部（門檻 {thr}，{time.time() - t0:.1f} 秒）'); return g

    def find_similar(self, thr=10, progress=None, limit=500, cmp_progress=None):
        """畫面相似的影片（同一部轉檔過、不同解析度、重複下載…）：長度差 5% 以內、跟那組「最大的那部」平均差異 ≤ thr 的放同一組
        （不串連：A 像 B、B 像 C 不會把不像的 A、C 放一起）。回傳 [[file（多 'dist'、第一部 'big'）…], …]，每組第一部是最大的.
        比對時可以用 vfp_cancel=True 中途停."""
        t0 = time.time(); n_new, n_bad = self.vfp_fill(progress)
        if getattr(self, 'vfp_cancel', False): return []
        R = [dict(x) for x in self.db.q("SELECT id,path,folder,name,size,dur,w,h,grade,vfp FROM files WHERE missing=0 AND length(arch)=0 AND length(vfp)>0 AND dur>0")]
        for r in R: r['fp'] = self.vfp_parse(r.pop('vfp'))
        R = [r for r in R if r['fp']]
        by_dur = sorted(range(len(R)), key=lambda i: R[i]['dur']); durs = [R[i]['dur'] for i in by_dur]
        order = sorted(range(len(R)), key=lambda i: (-(R[i]['size'] or 0), -((R[i]['w'] or 0) * (R[i]['h'] or 0))))     # 大的先當「組長」
        used = set(); out = []; pairs = 0; dist = self.vfp_dist
        for k, i in enumerate(order):
            if self.stop_all or getattr(self, 'vfp_cancel', False): break
            if cmp_progress and k % 500 == 0: cmp_progress(k, len(order))
            if i in used: continue
            a = R[i]; lo = bisect.bisect_left(durs, (a['dur'] - 1) / 1.05); hi = bisect.bisect_right(durs, a['dur'] * 1.05 + 1)
            grp = []
            for p_ in range(lo, hi):
                j = by_dur[p_]
                if j == i or j in used: continue
                pairs += 1; d = dist(a['fp'], R[j]['fp'])
                if d <= thr: grp.append((j, d))
            if not grp: continue
            used.add(i); a = dict(a); a['dist'] = 0.0; a['big'] = True; g = [a]
            for j, d in sorted(grp, key=lambda x: x[1]):
                used.add(j); b = dict(R[j]); b['dist'] = round(d, 1); g.append(b)
            for x in g: x.pop('fp', None)
            out.append(g)
        out.sort(key=lambda g: -sum(x['size'] or 0 for x in g))
        self.log.w(f'實驗：找畫面相似的影片（門檻 {thr}）：{len(R):,} 部有指紋、比了 {pairs:,} 對 → {len(out)} 組；新算指紋 {n_new:,}（讀不到 {n_bad:,}），共 {time.time() - t0:.1f} 秒'
                   + ('（中途停了）' if getattr(self, 'vfp_cancel', False) else ''))
        return out[:limit]

    def health(self):
        """🧪 影片庫健康檢查：可能有問題的影片（每類最多 500 部）."""
        Q = {'th_fail': ("th_state=3 AND probed!=3", '預覽圖做不出來'), 'probe_bad': ('probed=3', '讀不到（可能壞掉或不是影片）'), 'no_video': ('has_v=0 AND probed=1', '沒有畫面（只有聲音）'),
             'short': ('dur > 0 AND dur < 5', '超短（不到 5 秒）'), 'tiny': ('size < 100000', '超小（不到 100 KB）'), 'nodur': ('probed=1 AND has_v=1 AND (dur IS NULL OR dur=0)', '讀不到長度')}
        out = {}
        for k, (cond, nm) in Q.items():
            out[k] = {'name': nm, 'rows': [dict(r) for r in self.db.q(f"SELECT id,path,folder,name,size,dur,th_err,probe_err FROM files WHERE missing=0 AND arch='' AND {cond} ORDER BY folder,name LIMIT 500")]}
        self.log.w('實驗：健康檢查 ' + '、'.join(f'{v["name"]} {len(v["rows"])}' for v in out.values()))
        return out

    def stats(self, days=30):
        """🧪 整理成果統計."""
        q = self.db.q; one = lambda sql, a=(): (self.db.one(sql, a) or [0])
        out = {'lib': [tuple(r) for r in q("SELECT grade, COUNT(*), SUM(size) FROM files WHERE missing=0 AND arch='' GROUP BY grade")],
               'arch': [tuple(r) for r in q("SELECT arch, COUNT(*), SUM(size) FROM files WHERE missing=0 AND arch!='' GROUP BY arch ORDER BY 3 DESC")],
               'ext': [tuple(r) for r in q("SELECT ext, COUNT(*), SUM(size) FROM files WHERE missing=0 GROUP BY ext ORDER BY 3 DESC LIMIT 10")],
               'res': [tuple(r) for r in q("""SELECT CASE WHEN min(w,h)>=2000 THEN '4K' WHEN min(w,h)>=1400 THEN '1440p' WHEN min(w,h)>=1000 THEN '1080p' WHEN min(w,h)>=700 THEN '720p'
                                               WHEN min(w,h)>0 THEN 'SD' ELSE '不明' END AS r, COUNT(*), SUM(size) FROM files WHERE missing=0 GROUP BY r ORDER BY 3 DESC""")]}
        since = time.time() - days * 86400
        out['ops'] = [tuple(r) for r in q('SELECT kind, COUNT(*), SUM(size) FROM oplog WHERE t>=? AND ok=1 AND undone=0 GROUP BY kind', (since,))]
        out['days'] = [tuple(r) for r in q("SELECT date(t,'unixepoch','localtime') d, kind, COUNT(*), SUM(size) FROM oplog WHERE t>=? AND ok=1 AND undone=0 GROUP BY d, kind ORDER BY d", (since,))]
        out['freed_delete'] = one("SELECT SUM(size) FROM oplog WHERE kind='delete' AND undone=0")[0] or 0
        out['freed_conv'] = one("SELECT SUM(size*(1-cv_ratio)) FROM files WHERE cv_state=3 AND cv_ratio>0")[0] or 0
        out['cuts'] = one('SELECT COUNT(*), COUNT(DISTINCT file_id) FROM cuts WHERE state=1')
        out['graded_days'] = [tuple(r) for r in q("SELECT date(grade_t,'unixepoch','localtime') d, COUNT(*) FROM files WHERE length(grade)>0 AND grade_t>=? GROUP BY d ORDER BY d", (since,))]   # V0.1.43
        return out

    def random_unseen(self, folder=''):
        w = ["missing=0", "arch=''", "viewed=0", "th_state=2"]; a = []
        if folder:
            f = str(folder).rstrip('\\/'); w.append('(folder=? OR substr(folder,1,?)=? OR substr(folder,1,?)=?)'); a += [f, len(f) + 1, f + '\\', len(f) + 1, f + '/']
        es, ea = self.ext_sql()
        if es: w.append(es); a += ea
        r = self.db.one(f'SELECT id FROM files WHERE {" AND ".join(w)} ORDER BY RANDOM() LIMIT 1', a); return r[0] if r else None

    # ---------- 操作紀錄（保留 30 天，可以搜尋、匯出、把搬過的搬回來）
    def oplog(self, kind, src='', dst='', fid=None, name='', size=0, detail='', ok=1, batch=''):
        nm = name or (Path(src).name if src else (Path(dst).name if dst else ''))
        try:
            self.db.x('INSERT INTO oplog(t,kind,fid,name,src,dst,size,detail,ok,batch) VALUES(?,?,?,?,?,?,?,?,?,?)',
                      (time.time(), kind, fid, nm, str(src or ''), str(dst or ''), int(size or 0), str(detail or '')[:500], int(ok), batch))
            rec = {'t': now_s(), 'kind': kind, 'name': nm, 'src': str(src or ''), 'dst': str(dst or ''), 'size': int(size or 0), 'detail': detail, 'ok': int(ok), 'batch': batch}
            self.log.raw(json.dumps(rec, ensure_ascii=False), 'ops_log.jsonl')                       # LOG\\ops_log.jsonl：一行一筆，別的程式也好讀
            self.log.w(f'操作紀錄：{kind}　{nm}　{src or ""} → {dst or ""}　{detail}')
        except Exception: self.log.err('寫操作紀錄')

    def oplog_purge(self):
        days = max(7, int(self.cfg.get('oplog_days') or 30))
        try:
            n = self.db.x('DELETE FROM oplog WHERE t < ?', (time.time() - days * 86400,))
            if n: self.log.w(f'操作紀錄：清掉 {days} 天以前的 {n} 筆')
            jl = self.log.d / 'ops_log.jsonl'; cut = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() - days * 86400))
            if jl.exists():                                                     # LOG\ops_log.jsonl 也只留這幾天
                keep = []; drop = 0
                for line in jl.read_text(encoding='utf-8', errors='replace').splitlines():
                    try: old = json.loads(line).get('t', '') < cut
                    except Exception: old = False
                    if old: drop += 1
                    else: keep.append(line)
                if drop:
                    tmp = jl.with_suffix('.tmp'); tmp.write_text('\n'.join(keep) + ('\n' if keep else ''), encoding='utf-8'); os.replace(str(tmp), str(jl))
                    self.log.w(f'ops_log.jsonl：清掉 {days} 天以前的 {drop} 行')
        except Exception: self.log.err('清操作紀錄')

    def oplog_query(self, text='', kind='', days=30, limit=3000):
        w = ['t >= ?']; a = [time.time() - days * 86400]
        if kind: w.append('kind=?'); a.append(kind)
        if text:
            for word in str(text).split():
                w.append('(name LIKE ? OR src LIKE ? OR dst LIKE ? OR detail LIKE ?)'); a += [f'%{word}%'] * 4
        return [dict(r) for r in self.db.q(f'SELECT * FROM oplog WHERE {" AND ".join(w)} ORDER BY t DESC, id DESC LIMIT {int(limit)}', a)]

    def oplog_last_move(self):
        """最近一次「搬」的動作（移到待刪／歸檔／收藏搬）：同一種、連續做的（前後間隔 3 分鐘內）算同一次."""
        R = [dict(r) for r in self.db.q("SELECT * FROM oplog WHERE kind IN ('trash','arch','fav') AND undone=0 AND detail LIKE '%搬%' ORDER BY t DESC LIMIT 5000")]
        if not R: return []
        k0 = R[0]['kind']; out = [R[0]]
        for r in R[1:]:
            if r['kind'] != k0 or out[-1]['t'] - r['t'] > 180: break
            out.append(r)
        return out

    # ---------- V0.2.01 清空待刪：VideoSIFT\待刪 裡的檔案永久刪除，連預覽圖、人臉資料一起清；初剪的 100% 不碰
    def trash_dirs(self):
        D = []; seen = set()
        for r in self.cfg.get('roots') or []:
            a = Path(str(r)).anchor
            if not a: continue
            for d in (Path(a) / ARCH_BASE / ARCH2['trash'], Path(a) / ARCH['trash']):
                k = path_key(d)
                if k not in seen: seen.add(k); D.append(d)
        td = str(self.cfg.get('trash_dir') or '').strip()
        if td and path_key(td) not in seen: D.append(Path(td))
        return [d for d in D if d.is_dir()]

    def _is_cut_file(self, p, cut_keys):
        return path_key(p) in cut_keys or self.in_cut_dir(p) or ARCH2['cut'] in Path(str(p)).parts or ARCH['cut'] in Path(str(p)).parts

    def trash_scan(self):
        """待刪資料夾裡有什麼：[{path, size, fid, src}]＋不刪的（初剪、正在用的）."""
        cut_keys = {path_key(c['out']) for c in self.db.q("SELECT out FROM cuts WHERE length(out)>0")}
        by_dst = {}
        for r in self.db.q("SELECT fid, src, dst FROM oplog WHERE kind='trash' AND ok=1 AND undone=0 ORDER BY t"):
            if r['dst']: by_dst[path_key(r['dst'])] = (r['fid'], r['src'])
        busy = set(int(x) for x in self.cv_active) | {int(j['fid']) for j in list(self.cut_q)} | ({int(self.cut_cur['fid'])} if self.cut_cur else set())
        L = []; skip = []
        for d in self.trash_dirs():
            for dp, dn, fn in os.walk(d):
                for n in fn:
                    p = os.path.join(dp, n)
                    try: sz = os.path.getsize(p)
                    except OSError: continue
                    fid, src = by_dst.get(path_key(p), (None, ''))
                    if fid is None:                                                 # 操作紀錄只留 30 天：用檔名＋大小找回原本那筆
                        rr = self.db.one("SELECT id, path FROM files WHERE missing=1 AND name=? AND size=? ORDER BY id DESC LIMIT 1", (n, sz))
                        if rr: fid, src = rr[0], rr[1]
                    if self._is_cut_file(p, cut_keys) or (src and self._is_cut_file(src, cut_keys)): skip.append({'path': p, 'size': sz, 'why': '初剪的檔，一律保留'}); continue
                    if fid is not None and int(fid) in busy: skip.append({'path': p, 'size': sz, 'why': '正在轉檔／初剪'}); continue
                    L.append({'path': p, 'size': sz, 'fid': int(fid) if fid is not None else None, 'src': src or ''})
        return L, skip

    def trash_purge(self, dry=True):
        """dry＝只算有幾個、多大；不然在背景永久刪除（硬碟空間馬上回來，不經過資源回收筒）."""
        L, skip = self.trash_scan(); by = {}
        for x in L:
            k = Path(x['path']).anchor.upper(); n_, b_ = by.get(k, (0, 0)); by[k] = (n_ + 1, b_ + x['size'])
        res = {'ok': True, 'n': len(L), 'bytes': sum(x['size'] for x in L), 'by': by, 'skip': len(skip), 'skip_cut': sum(1 for x in skip if x['why'].startswith('初剪')),
               'dirs': [str(d) for d in self.trash_dirs()]}
        if dry or not L: return dict(res, message=f'待刪裡有 {len(L):,} 個檔、{fmt_b(res["bytes"])}' + (f'（{len(skip)} 個不刪：初剪或正在用）' if skip else ''))
        if getattr(self, '_trash_busy', False): return {'ok': False, 'message': '上一次清空待刪還在進行'}
        self._trash_busy = True; t = self.task('op', f'清空待刪：{len(L):,} 個檔')
        def work():
            ok = 0; fb = 0; bad = []; fids = []
            try:
                for i, x in enumerate(L):
                    t['pct'] = round(i * 100 / max(1, len(L)))
                    try: os.remove(x['path'])
                    except FileNotFoundError: pass
                    except Exception as ex: bad.append(f'{Path(x["path"]).name}（{ex}）'); continue
                    ok += 1; fb += x['size']
                    self.oplog('purge', src=x['path'], fid=x['fid'], size=x['size'], detail='清空待刪：永久刪除' + (f'（原本在 {x["src"]}）' if x['src'] else ''))
                    try: self.db.x("UPDATE oplog SET undone=-1 WHERE kind='trash' AND undone=0 AND dst=?", (x['path'],))     # 已經刪掉了：「↩ 復原上一次移到待刪」不要再找它
                    except Exception: pass
                    if x['fid'] is not None: fids.append(x['fid'])
                n_db = self._forget_files(fids)
                for d in self.trash_dirs():                                          # 空掉的子資料夾也拿掉（待刪本身留著）
                    for dp, dn, fn in os.walk(d, topdown=False):
                        if path_key(dp) != path_key(d) and not os.listdir(dp):
                            try: os.rmdir(dp)
                            except Exception: pass
                msg = f'清空待刪：永久刪除 {ok:,} 個檔，空出 {fmt_b(fb)}；預覽圖、人臉資料一起清掉 {n_db:,} 部' + (f'；{len(bad)} 個刪不掉：' + '、'.join(bad[:5]) if bad else '') + (f'；初剪的 {res["skip_cut"]} 個保留' if res['skip_cut'] else '')
                self.log.w(msg); self.done(t, 'done' if not bad else 'fail', msg); self.info_c['t'] = 0
                self.trash_last = {'t': time.time(), 'message': msg, 'ok': ok, 'bytes': fb, 'bad': len(bad)}
            except Exception as ex: self.log.err('清空待刪'); self.done(t, 'fail', str(ex)[-200:])
            finally: self._trash_busy = False
        threading.Thread(target=work, name='VsTrashPurge', daemon=True).start()
        return dict(res, message=f'開始永久刪除 {len(L):,} 個檔（{fmt_b(res["bytes"])}），在背景做')

    def _forget_files(self, fids):
        """這幾部（檔案已經刪掉）：刪預覽圖資料夾、人臉資料、清單裡那一筆。有初剪紀錄的那筆留著（只清預覽圖）."""
        fids = sorted({int(i) for i in fids if i is not None})
        if not fids: return 0
        n = 0
        for i in fids:
            r = self.db.one('SELECT id, th_dir FROM files WHERE id=?', (i,))
            if not r: continue
            td = Path(r['th_dir'] or '')
            if r['th_dir'] and self.th_owned(td, i):
                try: shutil.rmtree(td, ignore_errors=True)
                except Exception: pass
            with self.lock:
                if i in self.th_front: self.th_front.remove(i)
            has_cut = (self.db.one('SELECT COUNT(*) FROM cuts WHERE file_id=?', (i,)) or [0])[0]
            if has_cut: self.db.x("UPDATE files SET missing=1,th_state=0,th_n=0,th_dir='',vfp='' WHERE id=?", (i,))
            else: self.db.x('DELETE FROM files WHERE id=?', (i,))
            try: self.db.x('DELETE FROM people WHERE file_id=?', (i,))
            except Exception: pass
            n += 1
        F = getattr(self, 'faces', None)
        if F is not None and hasattr(F, 'forget_files'):
            try: F.forget_files(fids)
            except Exception: self.log.err('清人臉資料')
        return n

    def oplog_undo_last(self, dry=False):
        """↩ 復原上一次搬移（整批）."""
        L = self.oplog_last_move()
        if not L: return {'ok': False, 'n': 0, 'message': '沒有可以復原的搬移'}
        nm = {'trash': '移到待刪', 'arch': '歸檔', 'fav': '搬去收藏'}.get(L[0]['kind'], L[0]['kind'])
        when = time.strftime('%m-%d %H:%M', time.localtime(L[0]['t']))
        if dry: return {'ok': True, 'n': len(L), 'kind': nm, 'when': when, 'bytes': sum(int(x['size'] or 0) for x in L), 'names': [x['name'] for x in L[:8]]}
        res = [self.oplog_undo(x['id']) for x in L]; ok = sum(1 for r in res if r.get('ok')); bad = [r['message'] for r in res if not r.get('ok')]
        self.log.w(f'↩ 復原上一次搬移（{nm}，{when}）：搬回 {ok} 個' + (f'，{len(bad)} 個沒搬：{bad[:5]}' if bad else ''))
        return {'ok': True, 'n': ok, 'bad': bad, 'message': f'↩ 復原「{nm}」（{when}）：搬回 {ok} 個' + (f'，{len(bad)} 個沒搬（{bad[0]}）' if bad else '')}

    def oplog_undo(self, oid):
        """把一筆「搬過去」的搬回原來的位置（歸檔、待刪、搬去收藏）。原位置已經有同名的就不動."""
        r = self.db.one('SELECT * FROM oplog WHERE id=?', (int(oid),))
        if not r: return {'ok': False, 'message': '找不到這筆紀錄'}
        if r['undone']: return {'ok': False, 'message': '這筆已經搬回去過了'}
        if r['kind'] not in ('arch', 'trash', 'fav', 'rename') or '搬' not in (r['detail'] or ''): return {'ok': False, 'message': '這種紀錄沒辦法自動復原（只有搬過去的可以搬回來）'}
        src, dst = Path(r['src']), Path(r['dst'])
        if not dst.exists(): return {'ok': False, 'message': f'搬過去的檔案已經不在了：{dst}'}
        if src.exists(): return {'ok': False, 'message': f'原位置已經有同名的檔案，為了安全不覆蓋：{src}'}
        try:
            src.parent.mkdir(parents=True, exist_ok=True); self.copy_file(dst, src, None, move=True)
        except Exception as ex: return {'ok': False, 'message': f'搬不回去：{ex}'}
        if EXT_MOVED.get('fn'):                                                   # V0.5.39 搬回來：整理的紀錄也跟著回來
            try: EXT_MOVED['fn'](str(dst), str(src))
            except Exception: pass
        if r['fid']:
            self.db.x("UPDATE files SET path=?, folder=?, name=?, arch='', missing=0 WHERE id=?", (str(src), str(src.parent), src.name, r['fid']))
        self.db.x('UPDATE oplog SET undone=? WHERE id=?', (time.time(), r['id']))
        self.oplog('undo', src=str(dst), dst=str(src), fid=r['fid'], size=r['size'], detail=f'復原第 {r["id"]} 筆（{r["detail"]}）')
        self.info_c['t'] = 0; return {'ok': True, 'message': f'已搬回：{src}'}

    # ---------- 剪好之後：刪除原檔（連預覽圖一起刪；初剪檔永遠不動）
    def cut_outputs(self, fid):
        return sorted({c['out'] for c in self.db.q('SELECT out FROM cuts WHERE file_id=? AND state=1', (int(fid),)) if c['out'] and Path(c['out']).exists()})

    def in_cut_dir(self, path):
        k = path_key(path); cd = str(self.cfg.get('cut_dir') or '').strip()
        if cd and (k == path_key(cd) or k.startswith(path_key(cd) + os.sep)): return True
        parts = [x.lower() for x in Path(k).parts]
        if ARCH['cut'].lower() in parts: return True
        return any(a == ARCH_BASE.lower() and b == ARCH2['cut'].lower() for a, b in zip(parts, parts[1:]))

    def delete_original(self, fid, permanent=False):
        """丟到資源回收筒（permanent=True 才直接刪）。要有剪好、還在的初剪檔才給刪。回傳 {'ok','message','need_perm'}."""
        r = self.file(fid)
        if not r: return {'ok': False, 'message': '找不到這部影片'}
        if self.in_cut_dir(r['path']): return {'ok': False, 'message': '這是初剪資料夾裡的檔，永久保存，不刪'}
        if int(fid) in self.cv_active: return {'ok': False, 'message': '這部正在轉檔，轉完（或取消）再刪'}
        if any(j['fid'] == int(fid) for j in list(self.cut_q)) or (self.cut_cur and self.cut_cur['fid'] == int(fid)): return {'ok': False, 'message': '這部還在初剪，剪好再刪'}
        outs = self.cut_outputs(fid)
        if not outs: return {'ok': False, 'message': '找不到這部剪好的初剪檔（被搬走或刪掉了？），為了安全不刪原檔'}
        why = self.changed_since_scan(r) if Path(r['path']).exists() else ''
        if why:
            self.log.w(f'刪除原檔取消（檔案在掃描後被改過：{why}）：{r["path"]}')
            return {'ok': False, 'message': f'為了安全沒有刪：{r["name"]} {why}（可能被別的程式換掉了），請重新掃描後再試'}
        self.thumb_cancel(fid)
        with self.lock:
            if int(fid) in self.th_front: self.th_front.remove(int(fid))
        src = Path(r['path']); how = ''
        if src.exists():
            if not permanent and send_to_recycle(src): how = '丟到資源回收筒'
            elif not permanent: return {'ok': False, 'need_perm': True, 'message': '這顆硬碟沒辦法丟資源回收筒（或檔案正在用）'}
            else:
                try: src.unlink(); how = '直接刪除'
                except Exception as ex: return {'ok': False, 'message': f'刪不掉（檔案正在播放或被別的程式開著？先關掉播放視窗再試）：{ex}'}
        else: how = '原檔本來就不在了'
        td = Path(r['th_dir'] or '')
        if r['th_dir'] and self.th_owned(td, fid): shutil.rmtree(td, ignore_errors=True)        # 那部的 2 秒預覽圖
        self.db.x("UPDATE files SET missing=1,th_state=0,th_n=0,th_dir='' WHERE id=?", (int(fid),))
        self.db.x("INSERT INTO ops(kind,src,dst,t,ok) VALUES('delete',?,?,?,1)", (str(src), how, time.time())); self.info_c['t'] = 0
        self.oplog('delete', src=str(src), fid=int(fid), size=r['size'] or 0, detail=f'刪除原檔（{how}）；初剪檔保留：' + '、'.join(Path(o).name for o in outs))
        self.log.w(f'刪除原檔（{how}）：{src}　初剪檔保留：{", ".join(Path(o).name for o in outs)}')
        return {'ok': True, 'message': f'已刪除原檔（{how}）和它的預覽圖：{src.name}　初剪檔保留 {len(outs)} 個'}

    # ---------- 顯示卡（NVENC）檢查
    def gpu_check(self, force=False):
        st = self.gpu_st
        if st['checked'] and not force: return st
        lines = []
        drv = ''
        if self.perf.smi:
            rc, out, e = run([self.perf.smi, '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'], timeout=10)
            drv = out.strip(); lines.append(f'顯示卡：{drv or e.strip() or "讀不到"}')
        else: lines.append('找不到 nvidia-smi（沒有 NVIDIA 顯示卡或驅動）')
        res = None
        for ff in [x for x in (self.ff, self.ff_gpu) if x]:
            rc0, o0, e0 = run([ff, '-hide_banner', '-version'], timeout=10); ver = (o0.splitlines() or ['?'])[0][:60]
            for preset, aq in (('p5', True), ('p5', False), ('slow', False)):
                cmd = [ff, '-hide_banner', '-nostdin', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=30', '-t', '1', '-c:v', 'hevc_nvenc', '-preset', preset] + \
                      (['-tune', 'hq', '-rc', 'vbr', '-cq', '20', '-b:v', '0', '-spatial_aq', '1', '-temporal_aq', '1', '-rc-lookahead', '32'] if aq else ['-rc', 'vbr', '-cq', '20', '-b:v', '0']) + \
                      ['-f', 'null', '-']
                rc, o, e = run(cmd, timeout=40)
                lines.append(f'{ver}｜hevc_nvenc preset={preset} {"完整" if aq else "基本"}：{"✔ 可以" if rc == 0 else "✖ " + (e.strip().splitlines() or ["?"])[-1][:200]}')
                if rc == 0: res = (ff, preset, aq); break
            if res: break
        st.update(checked=True, ok=bool(res), ff=res[0] if res else '', preset=res[1] if res else 'p5', aq=res[2] if res else False, t=time.time(), drv=drv)
        if not res:
            lines.append('結論：顯示卡壓縮不能用 → 轉檔改用 CPU（libx265，比較慢）。常見原因：驅動太舊（新版 FFmpeg 要新驅動）。'
                         '可以更新 NVIDIA 驅動，或把可用的舊版 FFmpeg（例如 7.1）放在「程式資料夾\\ffmpeg_gpu\\」')
        else: lines.append(f'結論：✔ 用顯示卡轉（{Path(res[0]).name}，preset {res[1]}）')
        st['diag'] = '\n'.join(lines)
        try: (self.root / 'LOG' / 'gpu_diag.txt').write_text(f'[{now_s()}]\n' + st['diag'] + '\n', encoding='utf-8')
        except Exception: pass
        self.log.w('顯示卡檢查：' + ('✔ 可以用' if res else '✖ 不能用') + f'（{drv}）')
        return st

    CAP_K = {'h264': 0.6, 'hevc': 0.9, 'h265': 0.9, 'mpeg2video': 0.35, 'mpeg1video': 0.35, 'mpeg4': 0.45, 'msmpeg4v3': 0.45, 'msmpeg4v2': 0.45, 'wmv3': 0.45, 'wmv2': 0.45, 'vc1': 0.5, 'vp8': 0.6, 'vp9': 0.9, 'av1': 1.0}
    RES_OPTS = [(0, '原始解析度'), (2160, '4K（2160p）'), (1440, '1440p'), (1080, '1080p'), (720, '720p'), (480, '480p')]

    def src_vbr(self, info):
        """原檔「影像」的位元率（bps）。ffprobe 讀不到（.ts 常常這樣）就用 檔案大小 ÷ 長度，扣掉聲音估."""
        info = info or {}
        try: v = int(float(info.get('vbr') or 0))
        except Exception: v = 0
        try:
            sz = float(info.get('size') or 0); d = float(info.get('dur') or 0); tot = sz * 8 / d if sz and d > 1 else 0
        except Exception: tot = 0
        if tot and (not v or v >= tot * 0.97):                                  # 讀到的是整個檔（含聲音）的
            na = len([a for a in str(info.get('acodecs') or '').split(',') if a]); v = int(max(tot * 0.5, tot - 160000 * na))
        return int(v)

    def conv_params(self, info, P=None):
        """這一部要用的轉檔參數（V0.1.57）：畫質 q、解析度上限 res、位元率上限 cap（bps，0＝不限）.
        cv_cap：'auto'＝照原檔位元率的一定比例（H.264 的 60%）封頂 → 轉完不會比原檔大；'off'＝不封頂；數字＝固定幾 Mbps."""
        P = dict(P or {}); info = info or {}
        q = int(P.get('q') or self.cfg.get('cv_q') or 19)
        res = int(P['res'] if P.get('res') is not None else (self.cfg.get('cv_res') or 0))
        capm = P['cap'] if P.get('cap') is not None else self.cfg.get('cv_cap')
        if capm in (None, ''): capm = 'auto'
        h = int(info.get('h') or 0); scale = (res / h) if (res and h and h > res) else 1.0
        vb = self.src_vbr(info); cap = 0
        if capm == 'auto':
            k = self.CAP_K.get(str(info.get('vcodec') or '').lower(), 0.5)
            if vb: cap = int(max(300000, vb * k * (scale ** 1.6)))
        elif str(capm) not in ('off', '0'):
            try: cap = int(float(capm) * 1e6)
            except Exception: cap = 0
        return {'q': q, 'res': res if scale < 1 else 0, 'cap': cap, 'capm': capm, 'scale': scale, 'src_vbr': vb}

    def enc_args(self, info, for_cut=False, P=None, cpu=False):
        """{'ff','pre','v','name'}：照設定和顯示卡檢查結果選 hevc_nvenc 或 libx265；P＝conv_params（有 cap 就封頂位元率）."""
        want = self.cfg.get('cv_enc') or 'auto'; g = self.gpu_st
        q = int((P or {}).get('q') or self.cfg.get('cv_q') or 19); cap = int((P or {}).get('cap') or 0)
        v10 = bool(info) and '10' in str((info or {}).get('pix') or '')
        use_gpu = not cpu and (want == 'gpu' or (want == 'auto' and g.get('ok')))
        if use_gpu and g.get('ok'):
            v = ['-c:v', 'hevc_nvenc', '-preset', g.get('preset') or 'p5']
            v += (['-tune', 'hq', '-rc', 'vbr', '-cq', str(q), '-b:v', '0', '-spatial_aq', '1', '-temporal_aq', '1', '-rc-lookahead', '32'] if g.get('aq') else ['-rc', 'vbr', '-cq', str(q), '-b:v', '0'])
            if cap: v += ['-maxrate', str(cap), '-bufsize', str(cap * 2)]
            v += ['-pix_fmt', 'p010le', '-profile:v', 'main10'] if v10 else ['-pix_fmt', 'yuv420p', '-profile:v', 'main']
            return {'ff': g.get('ff') or self.ff, 'pre': ['-hwaccel', 'cuda'], 'v': v + ['-tag:v', 'hvc1'], 'name': '顯示卡 NVENC' + (f'（上限 {cap / 1e6:.1f} Mbps）' if cap else '')}
        xp = 'log-level=error' + (f':vbv-maxrate={cap // 1000}:vbv-bufsize={cap * 2 // 1000}' if cap else '')
        v = ['-c:v', 'libx265', '-preset', 'medium', '-crf', str(q), '-pix_fmt', 'yuv420p10le' if v10 else 'yuv420p', '-x265-params', xp, '-tag:v', 'hvc1']
        return {'ff': self.ff, 'pre': [], 'v': v, 'name': 'CPU x265' + ('（顯示卡失敗改用）' if cpu else ('（顯示卡不能用）' if want == 'gpu' else '')) + (f'（上限 {cap / 1e6:.1f} Mbps）' if cap else '')}

    @staticmethod
    def _vfa(pl, vf):
        V = pl['vf'] if 'vf' in pl else vf
        return ['-vf', ','.join(V)] if V else []

    def conv_vf(self, info, P):
        vf = []
        if str(info.get('field') or '') in ('tt', 'bb', 'tb', 'bt'): vf.append('bwdif=0')
        w, h = int(info.get('w') or 0), int(info.get('h') or 0)
        if P.get('res') and P.get('scale', 1) < 1: vf.append(f"scale=-2:{int(P['res'])}:flags=lanczos")
        elif (w % 2) or (h % 2): vf.append('scale=trunc(iw/2)*2:trunc(ih/2)*2')
        return vf

    NVDEC_V = ('h264', 'hevc', 'mpeg2video', 'mpeg1video', 'vp8', 'vp9', 'av1', 'vc1', 'mpeg4')
    NVDEC_PIX = ('yuv420p', 'yuvj420p', 'nv12', 'yuv420p10le', 'p010le', '')

    def gpu_vf(self, vf):
        # V0.1.98 全程顯示卡：把 CPU 濾鏡換成顯示卡版（去交錯 bwdif_cuda、縮小 scale_cuda）；換不了回 None
        out = []
        for f in vf or []:
            if f.startswith('bwdif='): out.append('bwdif_cuda=' + f.split('=', 1)[1])
            elif f.startswith('scale='):
                a = f.split('=', 1)[1].split(':'); w_, h_ = a[0], a[1]
                out.append(f'scale_cuda={w_}:{h_}' + (':interp_algo=lanczos' if 'flags=lanczos' in f else ''))
            else: return None
        return out

    def fullgpu_plan(self, info, e, vf):
        # V0.1.98 解碼 → 濾鏡 → 壓縮 全部留在顯示卡（畫面不搬回 CPU，CPU 幾乎不用）；同一組 NVENC 參數，畫質一樣。
        # 只用在顯示卡解得開的格式；失敗會自動退回原本的做法
        if self.cfg.get('cv_fullgpu') is False or not e['name'].startswith('顯示卡'): return None
        vc = str((info or {}).get('vcodec') or '').lower(); px = str((info or {}).get('pix') or '').lower()
        if vc not in self.NVDEC_V or px not in self.NVDEC_PIX: return None
        gv = self.gpu_vf(vf)
        if gv is None: return None
        v = list(e['v'])
        while '-pix_fmt' in v: i = v.index('-pix_fmt'); del v[i:i + 2]                     # 顯示卡上的畫面本來就是 nv12／p010，不用轉
        # V0.1.99 -reinit_filter 0：直播合併檔（_all）中間會換顏色範圍之類的參數，ffmpeg 會重建濾鏡，顯示卡上的畫面重建不了 → 半途失敗、整部從頭用舊方法重轉
        return dict(e, pre=['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda', '-extra_hw_frames', '8', '-reinit_filter', '0'], v=v, vf=gv, gpu_full=True,
                    name=e['name'].replace('顯示卡 NVENC', '顯示卡全程 NVENC'))

    def enc_plans(self, info, P):
        plans = []
        e = self.enc_args(info, P=P)
        try: fg = self.fullgpu_plan(info, e, self.conv_vf(info or {}, P or {}))
        except Exception: fg = None
        if fg: plans.append(fg)
        plans.append(e)
        if e['name'].startswith('顯示卡'):
            e2 = dict(e); e2['v'] = [x for x in e['v']]
            for k in ('-tune', '-spatial_aq', '-temporal_aq', '-rc-lookahead'):
                while k in e2['v']: i = e2['v'].index(k); del e2['v'][i:i + 2]
            e2['pre'] = []; e2['name'] = e['name'].replace('顯示卡 NVENC', '顯示卡 NVENC（基本）'); plans.append(e2)
            if (self.cfg.get('cv_enc') or 'auto') == 'auto': plans.append(self.enc_args({'pix': ''}, P=P, cpu=True))
        return plans

    # ---------- 轉檔（非 MP4 → MP4／H.265）
    def conv_add(self, ids):
        ids = [int(i) for i in ids]
        if not ids: return 0
        self._cv_index(); ph = ','.join(str(i) for i in ids)
        skip = [int(r[0]) for r in self.db.q(f"SELECT id FROM files WHERE id IN ({ph}) AND ((upper(substr(folder,2,8))=':\\DELETE' AND (length(folder)=9 OR substr(folder,10,1)='\\')) OR "
                                               "EXISTS (SELECT 1 FROM files f2 WHERE f2.cv_state=3 AND f2.cv_osz=files.size AND f2.id!=files.id AND lower(substr(f2.cv_src, -length(files.name)))=lower(files.name)))")]
        if skip:
            ids = [i for i in ids if i not in set(skip)]; self.log.w(f'轉檔排隊：{len(skip)} 部跳過（已經轉過的同一個原檔，或在 DELETE 裡）')
            if not ids: return 0
        ids = self._fc_slim_skip(ids)                                               # 整理（FileCompare）的影片瘦身已經在轉／轉好的不重複排
        if not ids: return 0
        mx = (self.db.one('SELECT MAX(cv_q) FROM files')[0] or 0)
        self.db.xm('UPDATE files SET cv_state=1,cv_err=\'\',cv_q=? WHERE id=? AND cv_state NOT IN (1,2)', [(mx + k + 1, i) for k, i in enumerate(ids)])
        self.log.w(f'轉檔排隊：加入 {len(ids)} 部（id {ids[:20]}{"…" if len(ids) > 20 else ""}）'); return len(ids)

    SEEK_BAD = ('mpegts', 'mpeg', 'rm', 'h264', 'hevc', 'mpegvideo', 'm4v', 'rawvideo')

    def _fmt_name(self, p):
        try:
            rc, o, _e = run([self.ffprobe, '-v', 'error', '-show_entries', 'format=format_name', '-of', 'default=nw=1:nk=1', str(p)], timeout=30)
            return (o or '').strip().lower()
        except Exception: return ''

    def seek_src(self, src):
        """V0.1.65 比畫質要「準確跳到某一秒」：.ts／.mpg／.vob／.rm 這類檔跳時間不準（會從半個畫面開始解，比出來的分數亂掉）
        → 先把影像原封不動搬成 MKV（不重壓、很快，放在該硬碟的 DELETE\\_vs_tmp），用完就刪。回傳 (要用的檔, 鑰匙)."""
        src = Path(src); fmt = self._fmt_name(src)
        if not any(x in fmt.split(',') for x in self.SEEK_BAD): return src, None
        key = str(src)
        try: mt = src.stat().st_mtime
        except Exception: return src, None
        while True:                                                              # 同一部別的工作正在整理：等它好了一起用
            with self._seekl:
                e = self._seekc.get(key)
                if e and e.get('busy'): wait = e['ev']
                elif e and e['mt'] == mt and Path(e['p']).exists(): e['n'] += 1; e['t'] = time.time(); return Path(e['p']), key
                else:
                    if e and e.get('p') and int(e.get('n') or 0) <= 0 and e['mt'] != mt:          # 原檔改過了：舊的暫存 MKV 沒人在用就刪掉
                        try: Path(e['p']).unlink()
                        except Exception: pass
                    wait = None; self._seekc[key] = {'busy': True, 'ev': threading.Event(), 'n': 0, 't': time.time(), 'mt': mt, 'p': ''}; break
            wait.wait(7200)
        ev = self._seekc[key]['ev']
        d = None
        for cand in (self.data / 'tq', Path(src.anchor or '/') / DEL_DIR / '_vs_tmp'):     # V0.1.91 先放程式所在的硬碟（不要在同一顆外接硬碟上又讀又寫）
            try:
                cand.mkdir(parents=True, exist_ok=True)
                for old in cand.glob('seek_*.vspart.mkv'):                         # 上次沒刪掉的（程式關掉）：超過 2 小時就清掉
                    try:
                        if time.time() - old.stat().st_mtime > 7200 and str(old) not in {e['p'] for e in self._seekc.values()}: old.unlink()
                    except Exception: pass
                need_space(cand, src.stat().st_size * 1.05, 1e9); d = cand; break
            except Exception: continue
        if d is None:
            with self._seekl: self._seekc.pop(key, None)
            ev.set(); self.log.w(f'比畫質：{src.name} 跳時間不準，但沒有空間先整理，照原本的方式比（分數可能不準）'); return src, None
        out = d / f'seek_{abs(hash(key)) % 10 ** 10}_{int(time.time())}_{random.randrange(16 ** 6):06x}.vspart.mkv'; t0 = time.time()
        rc, _o, e_ = run([self.ff, '-hide_banner', '-nostdin', '-v', 'error', '-y', '-fflags', '+genpts', '-i', str(src), '-map', '0:v:0', '-c', 'copy', '-an', '-sn', '-dn', str(out)], timeout=7200, prio='below')
        if rc != 0 or not out.exists():
            self.log.w(f'比畫質：{src.name}（{fmt}）跳時間不準，整理成 MKV 失敗：{(e_ or "")[-200:]}，照原本的方式比')
            try: out.unlink()
            except Exception: pass
            with self._seekl: self._seekc.pop(key, None)
            ev.set(); return src, None
        with self._seekl: self._seekc[key] = {'p': str(out), 'n': 1, 't': time.time(), 'mt': mt}
        ev.set()
        self.log.w(f'比畫質：{src.name}（{fmt}）跳時間不準 → 影像原封不動搬成 MKV（{fmt_b(out.stat().st_size)}，{time.time() - t0:.1f} 秒），用完就刪'); return out, key

    def seek_done(self, key):
        if not key or not hasattr(self, '_seekc'): return
        now = time.time()
        with self._seekl:
            e = self._seekc.get(key)
            if e: e['n'] = max(0, e['n'] - 1); e['t'] = now
            for k, e in list(self._seekc.items()):                               # 沒在用、10 分鐘沒再用到的就刪（同一部的抽查還可以接著用）
                if e['n'] <= 0 and not e.get('busy') and now - e['t'] > 600:
                    try: Path(e['p']).unlink()
                    except Exception: pass
                    self._seekc.pop(k, None)

    def _vstart(self, p):
        """影像實際從幾秒開始（相對整個檔的開頭）：.ts 常常聲音比影像早一點，要扣掉才對得齊."""
        try:
            rc, o, _e = run([self.ffprobe, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=start_time:format=start_time', '-of', 'json', str(p)], timeout=30)
            j = json.loads(o or '{}'); sv = float(((j.get('streams') or [{}])[0] or {}).get('start_time') or 0); fv = float((j.get('format') or {}).get('start_time') or 0)
            return max(-5.0, min(5.0, sv - fv))
        except Exception: return 0.0

    def _gray(self, path, t, d, W=48, H=27):
        """從 t 秒開始 d 秒的每一格，縮成很小的灰階（對齊用）."""
        try:
            p = subprocess.run([self.ff, '-hide_banner', '-nostdin', '-v', 'error', '-ss', f'{max(0.0, t):.3f}', '-t', f'{d:.3f}', '-i', str(path), '-an', '-vf', f'scale={W}:{H},format=gray', '-f', 'rawvideo', '-'],
                               capture_output=True, timeout=600, creationflags=NO_WINDOW | PRIO.get('below', 0), stdin=subprocess.DEVNULL)
            b = p.stdout or b''; N = W * H; return [b[i * N:(i + 1) * N] for i in range(len(b) // N)]
        except Exception: return []

    def _align(self, src, out, c, src_off, fps):
        """V0.1.62 找轉好的第 c 秒對到原檔的哪裡：原檔前後多抓 0.5 秒，逐格比小灰階圖，最像的那個位移（秒）。找不到回傳 None."""
        pad = 0.5; A = self._gray(src, c + src_off - pad, 2.0 + pad * 2); B = self._gray(out, c, 1.5)
        if len(A) < 5 or len(B) < 5 or len(A) <= len(B): return None
        B = B[:max(5, len(B))]; best = None
        idx = list(range(0, len(B), 2))
        for k in range(0, len(A) - len(B) + 1):
            cost = 0
            for i in idx:
                x, y = A[k + i], B[i]; cost += sum(abs(a - b) for a, b in zip(x[::3], y[::3]))
                if best is not None and cost >= best[1]: break
            if best is None or cost < best[1]: best = (k, cost)
        start = max(0.0, c + src_off - pad); return (start + best[0] / max(1.0, fps)) - (c + src_off)

    @staticmethod
    def ssim_size(w, h):
        """V0.1.63 比畫質用的大小：短邊最多 1080（原本一律縮成 640×360，4K 的壓縮痕跡縮那麼小就看不到了，分數太寬鬆）."""
        w, h = int(w or 0), int(h or 0)
        if not w or not h: return 1280, 720
        if w <= h: tw = min(w, 1080); th = int(round(h * tw / w / 2)) * 2
        else: th = min(h, 1080); tw = int(round(w * th / h / 2)) * 2
        return max(2, tw - tw % 2), max(2, th - th % 2)

    def dec_threads(self):
        """CPU 解碼最多用幾條執行緒（V0.1.81）：留 1/4 給電腦其他事（CineForm、ProRes 這種只能用 CPU 解的 4K，之前會把 CPU 吃到 100%）."""
        try: v = int(self.cfg.get('dec_threads') or 0)
        except Exception: v = 0
        return v if v > 0 else max(2, (os.cpu_count() or 4) * 3 // 4)

    def ssim_run(self, ins, lavfi):
        """比畫質（V0.1.71）：兩個來源用顯示卡解碼（NVDEC，CPU 省很多），顯示卡不行就自動改回 CPU 解碼.
        ins＝[(輸入前的參數, 檔案), (…)]. 回傳 SSIM 或 None."""
        hw = bool(self.gpu_st.get('ok')) and self.cfg.get('ssim_hw') is not False and time.time() - float(getattr(self, '_hwdec_bad', 0) or 0) > 1800
        for use in ((True, False) if hw else (False,)):
            cmd = [(self.gpu_st.get('ff') or self.ff) if use else self.ff, '-hide_banner', '-nostdin']
            for pre, f in ins: cmd += (['-hwaccel', 'cuda'] if use else ['-threads', str(self.dec_threads())]) + list(pre) + ['-i', str(f)]
            cmd += ['-lavfi', lavfi, '-f', 'null', '-']
            rc, _o, e = run(cmd, timeout=900, prio='below'); m = re.findall(r'All:([0-9.]+)', e or '')
            if m: return float(m[-1])
            if use:
                self._hwdec_bad = time.time(); self.log.w(f'比畫質：顯示卡解碼不行，改用 CPU 解碼（30 分鐘後再試顯示卡）：{(e or "")[-200:]}')
        return None

    def _ssim_lavfi(self, W, H, deint=False):
        return f'[0:v]setpts=PTS-STARTPTS,{"bwdif=0," if deint else ""}scale={W}:{H}:flags=bicubic,setsar=1,format=yuv420p[a];[1:v]setpts=PTS-STARTPTS,scale={W}:{H}:flags=bicubic,setsar=1,format=yuv420p[b];[a][b]ssim'

    def ssim_check(self, src, out, dur, src_off=0.0, n=5, seg=2.0):
        """原檔和轉好的比畫面像不像（SSIM：1＝一模一樣，0.98 以上肉眼看不出來）。平均抽 n 個地方各 2 秒，取中間值.
        V0.1.61：先在中間那一點試「不位移／照影像起點位移」，挑最像的那個對齊方式（手機影片影像常常比聲音晚一點開始，
        之前一律照起點位移反而對歪了，所有碼率都卡在 0.86 左右）。src_off：轉好的第 0 秒＝原檔的第幾秒（試轉用）。失敗回傳 0."""
        skey = None
        try:
            src, skey = self.seek_src(src)
            dur = float(dur or 0); ds = self._vstart(src); do = self._vstart(out)
            try: p0 = probe(self.ffprobe, Path(src)); W, H = self.ssim_size(p0.get('w'), p0.get('h')); di = str(p0.get('field') or '') in ('tt', 'bb', 'tb', 'bt')
            except Exception: W, H = 1280, 720; di = False
            LF = self._ssim_lavfi(W, H, di)

            def one(c, sh):
                xs = max(0.0, c + src_off + sh); xo = max(0.0, c)
                with self._ssim_sem: return _one(xs, xo)

            def _one(xs, xo):
                return self.ssim_run([(['-ss', f'{xs:.6f}', '-t', f'{seg:.2f}'], src), (['-ss', f'{xo:.6f}', '-t', f'{seg:.2f}'], out)], LF)
            pts = [dur * (k + 1) / (n + 1) for k in range(n)] if dur > seg * 3 else [0.0]
            pts = [max(0.0, min(c, max(0.0, dur - seg))) for c in pts]
            try: fps = float(probe(self.ffprobe, Path(out)).get('fps') or 30)
            except Exception: fps = 30.0
            pts = [(math.floor(c * fps) + 0.5) / fps for c in pts]               # 落在一格的正中間（落在兩格之間會差一格）
            mid = pts[len(pts) // 2]; cands = []
            try: al = self._align(src, out, mid, src_off, fps)
            except Exception: al = None
            for sh in (0.0, round(ds - do, 6), round(do - ds, 6)) + ((round(al, 6),) if al is not None else ()):
                if all(abs(sh - x) > 0.01 for x, _v in cands): cands.append((sh, one(mid, sh)))
            good = [(sh, v) for sh, v in cands if v is not None]
            if not good: self.log.w(f'畫質抽查沒成功：{Path(src).name}'); return 0.0
            sh, vmid = max(good, key=lambda x: x[1]); V = []
            fd = 1.0 / max(1.0, fps)
            for y in (sh - fd, sh + fd):                                         # 中間那一點也前後差一格試
                x = one(mid, y)
                if x is not None and x > vmid: vmid = x
            fd = 1.0 / max(1.0, fps)
            for c in pts:                                                        # 每個點跳到的位置可能差幾格：每個點自己再逐格對齊一次，取最像的
                if c == mid: V.append(vmid); continue
                a_ = None
                try: a_ = self._align(src, out, c, src_off, fps)
                except Exception: pass
                C_ = [sh, sh - fd, sh + fd] + ([a_] if a_ is not None and all(abs(a_ - x) > fd / 2 for x in (sh, sh - fd, sh + fd)) else [])
                L_ = [x for x in (one(c, y) for y in C_) if x is not None]
                if L_: V.append(max(L_))
            V.sort(); v = V[len(V) // 2] if len(V) % 2 else (V[len(V) // 2 - 1] + V[len(V) // 2]) / 2
            al_s = '沒找到' if al is None else f'{al:+.3f}s'
            self.log.w(f'畫質抽查：{Path(src).name} → SSIM 中間值 {v:.4f}（{W}×{H} 比，{len(V)} 處：{", ".join(f"{x:.3f}" for x in V)}；對齊位移 {sh:+.3f}s（逐格比對找到 {al_s}），試過 ' +
                       '、'.join(f'{a:+.3f}s＝{b:.3f}' for a, b in good) + '）'); return v
        except Exception: self.log.err('畫質抽查'); return 0.0
        finally: self.seek_done(skey)

    # ---------- 🎯 滾動式參數（V0.1.65）：同類型的檔累積經驗 → 樣本越取越少 → 夠多又穩就直接套用＋抽查
    LEARN_MODES = {'full': '完整測試（5 段×2 秒）', 'lite': '少量確認（3 段×2 秒，從經驗值附近找）', 'quick': '快速確認（3 段×1 秒，經驗值 ±2）', 'trust': '直接套用經驗值（不先測，轉完抽查）'}

    def tq_class(self, info):
        """同類型：編碼＋解析度（短邊）＋影格率＋每像素位元率＋交錯."""
        w, h = int(info.get('w') or 0), int(info.get('h') or 0); sh = min(w, h) if w and h else 0
        rb = next((f'{x}p' for x in (360, 480, 720, 1080, 1440, 2160) if sh <= x * 1.05), '4K+') if sh else '?p'
        fps = float(info.get('fps') or 0); fb = '≤30fps' if fps <= 31 else ('≤60fps' if fps <= 61 else '>60fps')
        vb = self.src_vbr(info); bpp = vb / (w * h * (fps or 30)) if w and h and vb else 0
        bb = '?' if not bpp else ('bpp<0.05' if bpp < 0.05 else ('bpp<0.1' if bpp < 0.1 else ('bpp<0.2' if bpp < 0.2 else 'bpp≥0.2')))
        il = '交錯' if str(info.get('field') or '') in ('tt', 'bb', 'tb', 'bt') else ''
        return '|'.join(x for x in (str(info.get('vcodec') or '?').lower(), rb, fb, bb, il) if x)

    def _learn_path(self): return self.data / 'tq_learn.json'

    def tq_try(self, src, target=None):
        """碼率測試頁「🎯 自動找」：完整測試一次，結果也記成📈經驗（V0.1.68）."""
        p_ = probe(self.ffprobe, Path(src)); info = dict(p_); info['size'] = Path(src).stat().st_size
        r = self.tq_search(src, info, target)
        if r and r.get('ok'):
            try: self.learn_add(self.tq_class(info), {'mode': 'full', 'q': int(r['q']), 'ssim': r.get('ssim'), 'spread': r.get('spread', 0), 'name': Path(src).name, 'npts': r.get('npts'), 'seg': r.get('seg'),
                                                      'sec': round(r.get('sec') or 0, 1), 'ratio': round(r['pred'] / info['size'], 4) if info['size'] and r.get('pred') else None, 'note': '碼率測試頁（預估大小）'})
            except Exception: self.log.err('碼率測試記經驗')
        return r

    def _learn_load(self):
        try: return json.loads(self._learn_path().read_text(encoding='utf-8'))
        except Exception: return {}

    def learn_db(self): return self._learn

    def _learn_save(self):
        try:
            p = self._learn_path(); tmp = p.with_name(p.name + '.tmp'); tmp.write_text(json.dumps(self._learn, ensure_ascii=False), encoding='utf-8'); os.replace(str(tmp), str(p))
        except Exception: self.log.err('滾動式參數存檔')

    def learn_cfg(self):
        C = dict(self.cfg.get('learn') or {})
        return {'trust_n': int(C.get('trust_n') or 100), 'floor': float(C.get('floor') or 0.975), 'spot': float(C.get('spot') or 0.2), 'lite_n': int(C.get('lite_n') or 5), 'quick_n': int(C.get('quick_n') or 15),
                'on': C.get('on') is not False}

    def tq_plan(self, info, cls=None):
        """照這一類的經驗決定這部怎麼測：full／lite／quick／trust."""
        L = self.learn_db(); cls = cls or self.tq_class(info); C = self.learn_cfg()
        with self._learn_lock:
            c = dict(L.get(cls) or {}); HA = [x for x in list(c.get('hist') or []) if x.get('q') and not x.get('remux')]
        H = [x for x in HA if not x.get('fail') and x.get('ok') is not False]     # V0.1.86 CQ 統計：不算抽查沒過的那次、也不算「最好也沒到目標」的
        n = len(H); Q = sorted(x['q'] for x in H[-60:])
        base = {'cls': cls, 'n': n, 'mode': 'full', 'npts': 5, 'seg': 2.0, 'reason': '第一次遇到這一類' if not n else f'這一類 {n} 次經驗，還不夠'}
        if not C['on'] or not n: return base
        med = Q[len(Q) // 2]
        sp = [x.get('spread', 1) for x in H if (x.get('npts') or 0) >= 5][-10:]      # 樣本差只看 5 段的（短片 1 段、3 段的差本來就小，會讓它太早變省）
        avg_sp = sum(sp) / len(sp) if sp else 1.0
        spots = [x for x in HA[-30:] if x.get('spot')]; bad = [x for x in spots if x['spot'] < C['floor']]
        sd = (sum((q - sum(Q) / len(Q)) ** 2 for q in Q) / len(Q)) ** 0.5
        tgt = float(self.cfg.get('cv_target') or 0.985)
        D = sorted(x['ssim'] - x['spot'] for x in HA[-30:] if x.get('ssim') and x.get('spot'))
        bias = D[(len(D) - 1) // 2] if len(D) >= 3 else 0.0                     # 樣本比整部「樂觀」多少（整部抽查一直比樣本低 → 找設定時目標調高一點補回來；至少 3 次、取偏小的中間值、最多補 0.006）
        bias = min(0.006, bias)
        base['target'] = min(0.995, tgt + max(0.0, bias)) if bias > 0.0005 else None
        if base['target']: base['reason'] += f'（樣本比整部高 {bias:.3f}，找設定的目標調成 {base["target"]:.3f}）'
        spot_med = sorted(x['spot'] for x in spots)[(len(spots) - 1) // 2] if spots else 0     # 偏小的中間值
        hold = int(c.get('demote_left') or 0) > 0                               # 抽查沒過 → 之後 10 部先回到比較保守的方式
        if n >= C['trust_n'] and sd <= 1.5 and len(spots) >= 3 and not bad and not hold and spot_med >= tgt:
            qq = Q[max(0, int(len(Q) * 0.3) - 1)]                               # 偏保守：取經驗值的 30% 分位（數字小一點＝畫質好一點）
            SS = sorted(x['ssim'] for x in H[-60:] if x.get('ssim')); SP = sorted(x['spot'] for x in H[-60:] if x.get('spot'))
            est = (SP[len(SP) // 2] if SP else (SS[len(SS) // 2] if SS else 0.0))
            return dict(base, mode='trust', q=qq, med=med, sd=sd, ssim_est=est, spot_rate=max(0.05, float(c.get('spot_rate') or C['spot'])),
                        reason=f'{n} 次經驗、CQ 很集中（中間值 {med}、標準差 {sd:.1f}）、抽查 {len(spots)} 次都過 → 直接用 CQ {qq}')
        if n >= C['quick_n'] and avg_sp <= 0.008 and not hold:
            return dict(base, mode='quick', npts=3, seg=1.0, start=med, lo=max(18, med - 2), hi=min(40, med + 2), med=med, reason=f'{n} 次經驗、樣本之間差很少（平均差 {avg_sp:.3f}）→ 3 段×1 秒、CQ {med}±2' + (base['reason'][base['reason'].find('（樣本比整部'):] if base.get('target') else ''))
        if n >= C['lite_n'] and avg_sp <= 0.012 and not hold:
            return dict(base, mode='lite', npts=3, seg=2.0, start=med, lo=max(18, med - 3), hi=min(40, med + 3), med=med, reason=f'{n} 次經驗（平均差 {avg_sp:.3f}）→ 3 段×2 秒、CQ {med}±3' + (base['reason'][base['reason'].find('（樣本比整部'):] if base.get('target') else ''))
        return dict(base, start=med, reason=base['reason'] + (f'（樣本之間差 {avg_sp:.3f}，還不穩）' if n >= C['lite_n'] else '') + ('（剛抽查沒過，先保守）' if hold else ''))

    def learn_add(self, cls, rec):
        """記一次經驗（滾動式：每一類最多留 300 筆）."""
        L = self.learn_db()
        with self._learn_lock:
            c = L.setdefault(cls, {'hist': [], 'spot_rate': self.learn_cfg()['spot']}); rec = dict(rec, t=time.time())
            c['hist'] = (c.get('hist') or []) + [rec]; c['hist'] = c['hist'][-300:]; c['last_t'] = rec['t']; c.pop('demote_until', None)
            if int(c.get('demote_left') or 0) > 0 and not rec.get('fail') and not rec.get('after_fail'): c['demote_left'] = int(c['demote_left']) - 1
            if rec.get('spot') and not rec.get('no_rate'):
                C = self.learn_cfg(); sr = float(c.get('spot_rate') or C['spot'])
                if rec['spot'] < C['floor']: c['spot_rate'] = min(1.0, sr * 2 + 0.1); c['fail'] = int(c.get('fail') or 0) + 1; c['demote_left'] = 10
                elif rec['spot'] < float(self.cfg.get('cv_target') or 0.985): c['spot_rate'] = min(1.0, sr * 1.3)
                else: c['spot_rate'] = max(0.05, sr * 0.9)
            self._learn_save()
        self.log.w(f'📈 滾動式參數：{cls}　{rec.get("mode")}　CQ {rec.get("q")}　樣本 {rec.get("ssim") if rec.get("ssim") is None else round(rec["ssim"], 4)}' +
                   (f'　抽查 {rec["spot"]:.4f}' if rec.get('spot') is not None else '') + (f'　{rec.get("note")}' if rec.get('note') else '') + f'　{rec.get("name", "")}')

    def learn_view(self):
        """給「滾動式參數 LOG」頁：每一類的經驗、現在用哪種方式、CQ 分布、抽查結果；最近的決定."""
        L = self.learn_db(); out = []; recent = []
        with self._learn_lock: items = [(k, dict(v, hist=list(v.get('hist') or []))) for k, v in list(L.items())]
        for cls, c in items:
            H = [x for x in (c.get('hist') or []) if x.get('q')]
            if not H: continue
            info_like = {}
            Q = sorted(x['q'] for x in H[-60:]); spots = [x['spot'] for x in H if x.get('spot') is not None]
            plan = self._plan_from_hist(cls)
            dist = {}
            for q in Q: dist[q] = dist.get(q, 0) + 1
            saved = [x.get('ratio') for x in H if x.get('ratio')]
            out.append({'cls': cls, 'n': len(H), 'mode': plan['mode'], 'mode_name': self.LEARN_MODES.get(plan['mode'], plan['mode']), 'reason': plan.get('reason', ''),
                        'q_med': Q[len(Q) // 2], 'q_min': Q[0], 'q_max': Q[-1], 'dist': dist, 'spots': len(spots), 'spot_bad': sum(1 for x in spots if x < self.learn_cfg()['floor']),
                        'spot_avg': (sum(spots) / len(spots)) if spots else None, 'spot_rate': float(c.get('spot_rate') or 0), 'fail': int(c.get('fail') or 0),
                        'ratio_avg': (sum(saved) / len(saved)) if saved else None, 'last_t': c.get('last_t', 0),
                        'ssim_avg': (lambda V: sum(V) / len(V) if V else None)([x['ssim'] for x in H if x.get('ssim')])})
            for x in H[-40:]: recent.append(dict(x, cls=cls))
        out.sort(key=lambda r: -r['n']); recent.sort(key=lambda r: -r.get('t', 0))
        return {'classes': out, 'recent': recent[:200], 'cfg': self.learn_cfg(), 'total': sum(r['n'] for r in out)}

    def _plan_from_hist(self, cls):
        try: return self.tq_plan({'vcodec': cls.split('|')[0]}, cls)              # 用這一類的經驗算一次「下一部會怎麼做」
        except Exception: return {'mode': 'full'}

    def learn_export(self):
        """📤 全部經驗匯出成 CSV（Excel 可以開；之後當大數據參考）."""
        import csv
        out = self.data / f'滾動式參數_{time.strftime("%Y%m%d_%H%M%S")}.csv'; n = 0
        with open(out, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.writer(fh); w.writerow(['時間', '類型', '編碼', '解析度', '影格率', '每像素位元率', '方式', 'CQ', '樣本SSIM', '抽查SSIM', '樣本差', '段數', '每段秒數', '找了幾秒', '變成原檔的比例', '只換外殼', '備註', '檔名'])
            with self._learn_lock: items = [(k, list(v.get('hist') or [])) for k, v in list(self.learn_db().items())]
            for cls, hist in items:
                c = {'hist': hist}; parts = (cls.split('|') + ['', '', '', ''])[:4]
                for x in c.get('hist') or []:
                    w.writerow([time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(x.get('t') or 0)), cls, *parts, x.get('mode', ''), x.get('q', ''), x.get('ssim') or '', '' if x.get('spot') is None else x['spot'],
                                x.get('spread', ''), x.get('npts', ''), x.get('seg', ''), x.get('sec', ''), x.get('ratio') or '', 'Y' if x.get('remux') else '', x.get('note', ''), x.get('name', '')]); n += 1
        self.log.w(f'📈 滾動式參數：匯出 {n} 筆 → {out}'); return {'ok': True, 'path': str(out), 'n': n}

    def learn_reset(self, cls=None):
        L = self.learn_db()
        with self._learn_lock:
            if cls: L.pop(cls, None)
            else: L.clear()
            self._learn_save()
        self.log.w(f'📈 滾動式參數：清掉 {cls or "全部"} 的經驗')

    # ---------- 🎯 畫質目標（V0.1.63）：每一部先拿 5 段樣本試，找「SSIM 還在目標以上」最省的設定，再整部轉
    def tq_search(self, src, info=None, target=None, J=None, cb=None, plan=None):
        """從片長 10%／30%／50%／70%／90% 各取一小段，用跟整部一樣的方式（顯示卡）轉成不同畫質（CQ），
        每段和原檔同一段比 SSIM（短邊 1080 比），取中間值；二分法找出「中間值 ≥ 目標」裡數字最大（最省）的 CQ.
        回傳 {'q', 'ssim', 'pred'（預估整部大小）, 'bps', 'tried': {q: ssim}, 'ok'（有沒有達到目標）, 'sec'（花了幾秒）}."""
        t_0 = time.time(); src = Path(src); target = float(target or self.cfg.get('cv_target') or 0.985)
        if not info or not info.get('dur'):
            p = probe(self.ffprobe, src); info = dict(info or {}); info.update(p) if p.get('ok') else None
        info = dict(info); info.setdefault('size', src.stat().st_size); dur = float(info.get('dur') or 0)
        if dur <= 0: return None
        P0 = self.conv_params(info); vf = self.conv_vf(info, P0); W, H = self.ssim_size(info.get('w'), info.get('h'))
        if P0.get('capm') == 'auto' and P0.get('src_vbr'):                      # 自動模式由畫質決定：上限只用來「不要比原檔大」（原檔影像位元率 95%）
            P0['cap'] = int(P0['src_vbr'] * 0.95 * (P0.get('scale', 1.0) ** 1.6))
        plan = plan or {}
        seg = float(plan.get('seg') or 2.0) if dur >= 20 else max(0.5, dur / 8)
        FR = {5: (0.1, 0.3, 0.5, 0.7, 0.9), 3: (0.2, 0.5, 0.8), 1: (0.5,)}.get(int(plan.get('npts') or 5), (0.1, 0.3, 0.5, 0.7, 0.9))
        pts = [dur * f for f in FR] if dur >= 12 else [max(0.0, dur / 2 - seg / 2)]
        fr = float(info.get('fps') or 0) or 30.0
        pts = [(math.floor(x * fr) + 0.5) / fr for x in pts]                     # 落在一格的正中間：原檔和樣本才會從同一格開始（落在兩格之間會差一格）
        d = self.data / 'tq'; d.mkdir(parents=True, exist_ok=True); cache = {}
        tag = f'{os.getpid()}_{threading.get_ident()}'
        src0 = src; src, skey = self.seek_src(src)                               # .ts 這類：先整理成可以準確跳的 MKV（樣本才不會從半個畫面開始）
        try: return self._tq_search2(src0, src, info, target, J, cb, plan, P0, vf, W, H, seg, pts, d, cache, tag, dur, t_0)
        finally: self.seek_done(skey)

    def _tq_search2(self, src0, src, info, target, J, cb, plan, P0, vf, W, H, seg, pts, d, cache, tag, dur, t_0):

        def score(q):
            if q in cache: return cache[q][0]
            P = dict(P0, q=int(q)); plans = self.enc_plans(info, P); V = []; B = 0; n = 0
            for k, x in enumerate(pts):
                if J is not None and J.get('cancel'): raise InterruptedError('取消')
                out = d / f'tq_{tag}_{k}.mp4'; ok = False
                for pl in plans:
                    cmd = [pl['ff'], '-hide_banner', '-nostdin', '-loglevel', 'error', '-y'] + pl['pre'] + ['-threads', str(self.dec_threads()), '-ss', f'{x:.6f}', '-t', f'{seg:.3f}', '-i', str(src), '-map', '0:v:0', '-an', '-sn', '-dn'] + \
                          self._vfa(pl, vf) + pl['v'] + ['-fps_mode', 'passthrough', str(out)]
                    rc, _o, _e = run(cmd, timeout=900, prio='below')
                    if rc != 0 and 'fps_mode' in (_e or ''): cmd[cmd.index('-fps_mode'):cmd.index('-fps_mode') + 2] = ['-vsync', '0']; rc, _o, _e = run(cmd, timeout=900, prio='below')   # 舊版 FFmpeg
                    if rc == 0 and out.exists() and out.stat().st_size > 0: ok = True; break
                if not ok: continue
                B += out.stat().st_size; n += 1
                with self._ssim_sem: v_ = self.ssim_run([(['-ss', f'{x:.6f}', '-t', f'{seg:.3f}'], src), ([], out)], self._ssim_lavfi(W, H, 'bwdif=0' in (vf or [])))   # 交錯的：原檔也去交錯再比
                if v_ is not None: V.append(v_)
                try: out.unlink()
                except Exception: pass
            if not V: cache[q] = (None, 0, []); return None
            V.sort(); med = V[len(V) // 2] if len(V) % 2 else (V[len(V) // 2 - 1] + V[len(V) // 2]) / 2
            bps = B * 8 / (seg * n) if n else 0; cache[q] = (med, bps, V)
            msg = f'🎯 試 CQ {q}：SSIM {med:.4f}（{", ".join(f"{v:.3f}" for v in V)}），影像約 {bps / 1e6:.2f} Mbps'
            self.log.w(f'{msg}　{src0.name}')
            if J is not None: J['enc'] = f'🎯 找最省的設定：CQ {q} → {med:.3f}'
            if cb: cb(q, med, bps)
            return med
        H_ = (self.cfg.get('tq_hist') or {}).get(str(info.get('vcodec') or '').lower()) or []
        start = int(plan['start']) if plan.get('start') else (int(sorted(H_)[len(H_) // 2]) if H_ else 28)
        lo, hi, best = int(plan.get('lo') or 18), int(plan.get('hi') or 40), None
        q = max(lo, min(hi, start)); it = 0
        while lo <= hi and it < 7:
            v = score(q); it += 1
            if v is not None and v >= target: best = q; lo = q + 1
            else: hi = q - 1
            q = (lo + hi) // 2
        if best is None:
            ok = False; best = min([k for k, x in cache.items() if x[0] is not None] or [18])
        else: ok = True
        med, bps, V = cache.get(best, (None, 0, []))
        if med is None: return None
        ab = 0.0
        try:
            tot = float(info.get('size') or 0) * 8 / dur; vb = self.src_vbr(info); ab = max(0.0, tot - vb)
        except Exception: pass
        pred = int((bps + ab) * dur / 8)
        if ok:
            with self._learn_lock:
                HH = dict(self.cfg.get('tq_hist') or {}); kk = str(info.get('vcodec') or '').lower(); HH[kk] = (list(HH.get(kk) or []) + [best])[-30:]; self.cfg.set('tq_hist', HH)
        r = {'npts': len(pts), 'seg': seg, 'V': list(V or []), 'spread': (max(V) - min(V)) if V else 0.0, 'cap': P0.get('cap', 0), 'q': best, 'ssim': med, 'bps': bps, 'pred': pred, 'ok': ok, 'target': target, 'tried': {k: x[0] for k, x in sorted(cache.items())}, 'sec': time.time() - t_0, 'cmp': f'{W}×{H}'}
        self.log.w(f'🎯 畫質目標 {target:.3f}：{src0.name} → 用 CQ {best}（樣本 SSIM {med:.4f}{"" if ok else "，最好也沒到目標"}），預估整部 {fmt_b(pred)}（原檔 {fmt_b(info["size"])} 的 {pred * 100 / max(1, info["size"]):.0f}%），'
                   f'試了 {len(cache)} 種：' + '、'.join(f'CQ{k}={("%.4f" % v) if v is not None else "失敗"}' for k, v in r['tried'].items()) + f'，花 {r["sec"]:.0f} 秒（{W}×{H} 比）')
        return r

    def _fc_slim_skip(self, ids):
        """嵌著的整理（FileCompare）🗜 影片瘦身：正在轉的那部、或旁邊已經有「_h265.mp4」的 → 這邊不排（同一部不要轉兩次）."""
        F = sys.modules.get('fc_app'); E = getattr(F, 'ENG', None) if F else None; SL = getattr(E, 'slim', None)
        if SL is None: return ids
        try:
            cur = str((SL.st or {}).get('src') or '').lower() if (SL.st or {}).get('run') else ''
            try: done_ = {str(r[0]).lower() for r in E.db.q('SELECT src FROM slim_done WHERE undone=0')}      # V0.5.50 看整理的瘦身紀錄（不去硬碟一個一個找 _h265.mp4）
            except Exception: done_ = set()
            ph = ','.join(str(int(i)) for i in ids); out = []; sk = 0
            for i, p in self.db.q(f'SELECT id,path FROM files WHERE id IN ({ph})'):
                pl = str(p).lower()
                if (cur and pl == cur) or pl in done_: sk += 1
                else: out.append(int(i))
            if sk: self.log.w(f'轉檔排隊：{sk} 部跳過（整理的「🗜 影片瘦身」正在轉或已經轉好）')
            keep = set(out); return [i for i in ids if i in keep]
        except Exception: return ids

    def conv_ratio(self):
        """轉好的平均大小比例（照檔案大小加權）；還沒轉過回傳 (0.5, 0)."""
        r = self.db.one('SELECT SUM(size*cv_ratio), SUM(size), COUNT(*) FROM files WHERE cv_state=3 AND cv_ratio>0 AND size>0 AND cv_t>=?', (float(self.cfg.get('cv_cap_t') or 0),))
        if not r or not r[2]: return (0.5, 0)                                    # V0.1.60 只算 0.1.57（有封頂）之後轉的；之前沒封頂轉大的不算，預估省才不會變負的
        return (float(r[0]) / float(r[1]) if r[1] else 0.5, int(r[2]))

    def conv_cancel(self, ids=None):
        if ids is None:
            n = self.db.x('UPDATE files SET cv_state=CASE WHEN cv_redo=1 THEN 3 ELSE 5 END, cv_redo=0 WHERE cv_state=1')
            for J in list(self.cv_active.values()): J['cancel'] = True; J['proc'] and J['proc'].kill()
            return n
        for i in ids:
            J = self.cv_active.get(int(i))
            if J:
                J['cancel'] = True
                if J.get('proc'): J['proc'].kill()
        return self.db.xm('UPDATE files SET cv_state=CASE WHEN cv_redo=1 THEN 3 ELSE 5 END, cv_redo=0 WHERE id=? AND cv_state=1', [(int(i),) for i in ids]) or 0

    def _conv_boss(self):
        while self.alive():
            try:
                n = self.bg_cap('conv', max(1, min(8, int(self.cfg.get('cv_n') or 3))))
                AJ = list(self.cv_active.values()); fin_n = sum(1 for J_ in AJ if J_.get('phase') in ('finish', 'post'))
                busy_n = len(AJ) - fin_n                                        # V0.1.93 收尾中的（顯示卡已經空了）不佔「同時幾部」；收尾的也滿 N 部就先等它們做完
                if not self.bg_hold('conv') and self.ff and busy_n < n and fin_n < n:
                    if not self.gpu_st.get('checked') and (self.cfg.get('cv_enc') or 'auto') != 'cpu': time.sleep(1); continue
                    excl = ','.join(str(int(x)) for x in self.cv_active) or '-1'
                    hl = getattr(self, 'lane_hold', None) or {}
                    off = [r_ for r_ in {str(x) for x in self.cfg.get('roots') or []} if self.root_offline(r_) or (hl.get(self.root_lane(r_)) or (0,))[0] > time.time()]; ph = ','.join('?' * len(off))
                    R_ = self.db.q(f'SELECT * FROM files WHERE cv_state=1 AND missing=0 AND id NOT IN ({excl}) {"AND root NOT IN (" + ph + ")" if off else ""} ORDER BY cv_q LIMIT 60', off)
                    r = None; per = max(1, int(self.cfg.get('cv_per_disk') or 1))
                    act = {}
                    for J_ in list(self.cv_active.values()):
                        if J_.get('phase') == 'finish' and J_.get('tmp_local'): continue      # 在本機收尾：不佔那顆外接硬碟
                        act[J_.get('lane')] = act.get(J_.get('lane'), 0) + 1
                    for c_ in R_:                                               # V0.1.91 同一顆 HDD／USB 硬碟同時只轉 1 部（3 部一起讀寫會把 USB 硬碟壓到斷線）
                        ln = self.lane_of(c_['cv_del'] if dict(c_).get('cv_redo') and dict(c_).get('cv_del') else c_['path'])
                        if self.drives.media(ln) in ('SSD', 'NVME') or act.get(ln, 0) < self._disk_cap(ln, per, n): r = c_; break
                    if r is not None:
                        fid = int(r['id']); self.db.x('UPDATE files SET cv_state=2 WHERE id=?', (fid,)); self.bg_mark('conv', r['name'])
                        self.cv_active[fid] = {'id': fid, 'name': r['name'], 'path': r['path'], 'lane': ln, 'pct': 0, 't0': time.time(), 'proc': None, 'speed': ''}
                        threading.Thread(target=self._conv_job, args=(dict(r),), name='VsConv', daemon=True).start(); continue
                time.sleep(1.0)
            except Exception:
                self.log.err('conv boss'); time.sleep(5)

    def conv_out_path(self, r):
        src = Path(r['path'])
        if (self.cfg.get('cv_out') or 'beside') == 'dir' and self.cfg.get('cv_out_dir'):
            rr = self.root_of(src); rp = Path(rr) if rr else Path(src.anchor)
            try: rel = src.parent.relative_to(rp)
            except Exception: rel = Path()
            d = Path(self.cfg.get('cv_out_dir')) / (safe_name(rp.name) if rp.name else '') / rel
        else:
            d = src.parent
            if src.suffix.lower() == '.mp4' and self.cfg.get('vs_tag') is False: return src     # 不加 _VS 時：H.264 MP4 → H.265 放回原本的檔名（原檔先搬到 DELETE）
        return unique_path(d / ((vs_stem(src.stem) if self.cfg.get('vs_tag') is not False else src.stem) + '.mp4'))     # V0.1.94 轉好的檔名加 _VS（再轉一次 _V2S…）

    def conv_tag_vs(self, dry=False):
        """V0.1.94 之前轉好的 MP4 檔名都補上 _VS（磁碟上改名＋資料庫一起改；每一筆都記操作紀錄，可以在「操作紀錄」一筆筆改回）."""
        rows = [dict(x) for x in self.db.q("SELECT id,path,name,size FROM files WHERE cv_state=3 AND missing=0")]
        todo = [r for r in rows if not vs_gen(r['name']) and int(r['id']) not in self.cv_active]
        if dry: return {'ok': True, 'n': len(todo)}
        n = 0; bad = []
        for r in todo:
            src = Path(r['path'])
            try:
                if not src.exists(): bad.append(f'{src.name}：找不到（硬碟離線？）'); continue
                dst = unique_path(src.with_name(vs_stem(src.stem) + src.suffix)); os.rename(str(src), str(dst))
                self.db.x('UPDATE files SET path=?, name=? WHERE id=?', (str(dst), dst.name, int(r['id'])))
                if EXT_MOVED.get('fn'):
                    try: EXT_MOVED['fn'](str(src), str(dst))
                    except Exception: pass
                self.oplog('rename', src=str(src), dst=str(dst), fid=int(r['id']), size=r['size'] or 0, detail=f'改名・搬：轉好的加上 _VS：{src.name} → {dst.name}'); n += 1
            except Exception as ex: bad.append(f'{src.name}：{ex}')
        self.log.w(f'🏷 轉好的加上 _VS：{n} 部改好' + (f'，{len(bad)} 部沒改：{bad[:10]}' if bad else ''))
        return {'ok': True, 'n': n, 'bad': bad, 'message': f'{n:,} 部轉好的檔名加上 _VS' + (f'；{len(bad)} 部沒改（多半是硬碟離線）' if bad else '')}

    def _disk_cap(self, lane, per, n):
        """V0.1.96 同一顆 HDD／外接硬碟同時轉幾部：你設的數字是基本；那顆硬碟其實很閒（最近 1 分鐘平均忙碌 < 35%）、
        而且 6 小時內沒斷過線 → 自動多開一部（最多 3 部、也不超過「同時」）；一忙起來就不再多開."""
        try:
            if self.cfg.get('cv_disk_auto') is False: return per
            E_ = getattr(self, '_busy_ema', None)
            if E_ is None: E_ = self._busy_ema = {}
            b = max([(self.dcount.get(x) or {}).get('busy', 0) for x in self.drives.disk_nums(lane)] or [100])
            e = E_.get(lane); now = time.time()
            if e is None or now - e[1] > 120: e = (float(b), now)
            else: a = min(1.0, (now - e[1]) / 60.0); e = (e[0] * (1 - a) + float(b) * a, now)
            E_[lane] = e
            if now - float((getattr(self, 'lane_off_t', {}) or {}).get(lane, 0)) < 6 * 3600: return per
            return min(max(1, int(n)), max(per, 3)) if e[0] < 35 else per
        except Exception: return per

    def _cv_tmp(self, out, fid, size):
        """V0.1.91 轉檔中的暫存檔：程式所在的硬碟（多半是 SSD）空間夠就先寫在那裡，轉好再整個搬過去 ——
        外接 USB 硬碟只剩「讀原檔」和最後一次連續寫入；faststart 回頭重寫、抽查畫質都在本機做（大量讀寫是 USB 硬碟斷線的主因）."""
        try:
            if self.cfg.get('cv_local_tmp') is not False:
                d = self.data / 'cv_tmp'; d.mkdir(parents=True, exist_ok=True)
                for old in d.glob('*.vspart.mp4'):                              # 上次閃退留下的
                    try:
                        if time.time() - old.stat().st_mtime > 86400: old.unlink()
                    except Exception: pass
                if os.path.splitdrive(str(d.resolve()))[0].upper() != os.path.splitdrive(str(out))[0].upper() and shutil.disk_usage(str(d)).free > size * 1.5 + 5e9:
                    return d / f'{int(fid)}_{os.getpid()}.vspart.mp4'
        except Exception: pass
        return out.with_name(out.stem + '.vspart.mp4')

    def _place(self, tmp, dst, J=None):
        """暫存檔放到最後的位置：同一顆直接改名；不同顆先複製成 .vsmove 再改名（複製到一半斷線不會留下壞的 MP4）."""
        tmp, dst = Path(tmp), Path(dst)
        if J is not None: J['enc'] = f'把轉好的檔搬到 {dst.anchor or dst.parent}（{fmt_b(tmp.stat().st_size) if tmp.exists() else ""}）…'; J['pct'] = 100.0; J['left'] = None
        try: os.replace(str(tmp), str(dst)); return
        except OSError:
            if os.path.splitdrive(str(tmp))[0].upper() == os.path.splitdrive(str(dst))[0].upper(): raise
        mv = dst.with_name(dst.stem + '.vsmove.mp4')
        try:
            shutil.copyfile(str(tmp), str(mv))
            if mv.stat().st_size != tmp.stat().st_size: raise OSError('複製過去的大小不對')
            os.replace(str(mv), str(dst))
        except Exception:
            try: mv.unlink()
            except Exception: pass
            raise
        try: tmp.unlink()
        except Exception: pass

    def _conv_job(self, r):
        redo = bool(dict(r).get('cv_redo')); force = int(dict(r).get('cv_redo') or 0) == 2; mp4 = Path(r['path'])
        if redo:                                                                 # V0.1.65 用 DELETE 裡的原檔、新方式重轉；原檔留在 DELETE，等你自己刪
            r = dict(r); r['path'] = r.get('cv_del') or ''; r['probed'] = 0
        fid = int(r['id']); J = self.cv_active.get(fid) or {}; src = Path(r['path']); t = self.task('conv', f'{"重轉" if redo else "轉檔"}：{src.name}')
        info = dict(r); dur = float(r['dur'] or 0)
        try:
            if not src.exists(): raise RuntimeError('原檔不見了' + ('（DELETE 裡的原檔已經刪掉，沒辦法重轉）' if redo else ''))
            if redo:
                r['size'] = src.stat().st_size; info['size'] = r['size']
            if not r['probed'] == 1:
                p = probe(self.ffprobe, src)
                if p.get('ok'): info.update(p); dur = float(p.get('dur') or 0)
            out = mp4 if redo else self.conv_out_path(r); need_space(out.parent, float(r['size'] or 0) * 1.1); out.parent.mkdir(parents=True, exist_ok=True); tmp = self._cv_tmp(out, fid, float(r['size'] or 0)); J['tmp_local'] = os.path.splitdrive(str(tmp))[0].upper() != os.path.splitdrive(str(out))[0].upper(); J['phase'] = 'test'
            A = [a for a in str(info.get('acodecs') or '').split(',') if a]
            acopy = bool(A) and all(a in ('aac', 'mp3', 'ac3', 'eac3') for a in A)
            info.setdefault('size', r['size']); info.setdefault('dur', dur)
            PP = self.conv_params(info); vf = self.conv_vf(info, PP); plans = self.enc_plans(info, PP)
            ok = False; err = ''; tq = None; pre_big = False
            plan = None
            if (redo or (self.cfg.get('cv_mode') or 'target') == 'target') and (not dur or info.get('has_v') == 0):
                self.log.w(f'🎯 {src.name}：' + ('讀不到片長' if not dur else '沒有影像') + '，不找設定，用固定畫質轉')
            elif redo or (self.cfg.get('cv_mode') or 'target') == 'target':        # 🎯 V0.1.63 每一部先找「肉眼看不出差別」最省的設定（重轉一定用這個）
                plan = self.tq_plan(info); self.log.w(f'🎯 {src.name}：{self.LEARN_MODES.get(plan["mode"])}　{plan.get("reason", "")}　（類型 {plan["cls"]}）')
                if plan['mode'] == 'trust':
                    tq = {'q': int(plan['q']), 'ssim': None, 'est': float(plan.get('ssim_est') or 0), 'ok': True, 'trust': True, 'pred': 0, 'sec': 0.0, 'cap': PP.get('cap', 0), 'npts': 0, 'seg': 0, 'V': [], 'spread': 0.0, 'tried': {}}
                    vb_ = self.src_vbr(info)
                    if PP.get('capm') == 'auto' and vb_: tq['cap'] = int(vb_ * 0.95 * (PP.get('scale', 1.0) ** 1.6))
                    J['enc'] = f'🎯 直接用經驗值 CQ {tq["q"]}'
                else:
                    J['enc'] = f'🎯 找最省的設定中（{plan["mode"]}）…'; t['msg'] = J['enc']
                    tq = self.tq_search(src, info, plan.get('target'), J=J, plan=plan)
                    if tq and not tq.get('ok') and plan['mode'] in ('lite', 'quick'):  # 經驗值附近找不到：這部可能不一樣，改完整測試
                        self.log.w(f'🎯 {src.name}：{plan["mode"]} 在經驗值附近沒找到 → 改完整測試')
                        plan = dict(plan, mode='full', npts=5, seg=2.0, lo=18, hi=40, start=plan.get('start'))
                        J['enc'] = '🎯 找最省的設定中（full）…'; tq = self.tq_search(src, info, plan.get('target'), J=J, plan=plan)
                if not tq: plan = None                                           # 找不到設定（樣本都失敗）：照固定畫質，不記成這種方式
                if tq:
                    PP['q'] = tq['q']; PP['cap'] = tq.get('cap', PP['cap']); plans = self.enc_plans(info, PP)
                    pre_big = not force and self.cfg.get('cv_skip_big') is True and bool(tq.get('pred')) and float(tq.get('seg') or 0) >= 2.0 and tq['pred'] >= float(r['size'] or 0) * 0.95   # V0.1.95 預設一定整部轉完再看大小（樣本預估不準：常常預估會變大、其實會變小）       # 樣本就看得出轉了不會變小 → 不用整部轉（1 秒的樣本頭部比例太大、不準，不用它判斷）

            def ffrun(cmd, name):
                J['enc'] = name; J['phase'] = 'enc'; P = Proc(cmd, self.cfg.get('cv_prio') or 'below').start(); self.procs.add(P); J['proc'] = P; t0 = time.time()
                fs = '+faststart' in ' '.join(cmd); outp = Path(cmd[-1]); FIN = {'t': 0.0, 'r0': None, 'sz': 0}
                spgb = float(self.cfg.get('cv_fin_spgb') or 20.0)                # 收尾（把索引移到檔頭）每 GB 要幾秒：照實際量到的慢慢修正
                W = 0.9 if fs else 1.0                                          # V0.1.93 進度條照實際：轉檔 0～90%、收尾 90～100%（以前轉完就停在 99.8% 不動）

                def tick(p):
                    el = time.time() - t0; ep = min(1.0, p.out_us / 1e6 / dur) if dur > 0 else 0.0
                    if fs and (FIN['t'] or (ep >= 0.97 and time.time() - p.t_last > 4)):          # 轉完了、FFmpeg 不再回報進度＝在收尾
                        if not FIN['t']:
                            FIN['t'] = time.time(); FIN['r0'] = proc_io(p.p.pid); J['phase'] = 'finish'      # 顯示卡已經空出來：下一部可以先開始
                            try: FIN['sz'] = outp.stat().st_size
                            except Exception: FIN['sz'] = 0
                        io = proc_io(p.p.pid); done_b = (io[0] - FIN['r0'][0]) if (io and FIN['r0']) else None
                        fe = time.time() - FIN['t']; est = max(3.0, FIN['sz'] / 1e9 * spgb)
                        fp = min(0.99, done_b / FIN['sz']) if (done_b is not None and FIN['sz'] > 0) else min(0.95, fe / est)
                        if done_b is not None and done_b > 0: p.t_last = time.time()      # 還在讀寫：不是卡住
                        J['pct'] = t['pct'] = round(W * 100 + (100 - W * 100) * fp, 1)
                        J['enc'] = f'{name} · 收尾：把索引移到檔頭（手機、網頁才能邊下載邊播）{fp * 100:.0f}%'
                        J['left'] = (fe / fp - fe) if fp > 0.03 else max(0.0, est - fe); J['speed'] = ''
                    else:
                        J['pct'] = t['pct'] = round(min(W * 100, ep * W * 100), 1); J['speed'] = p.speed
                        fin_left = 0.0 if not fs else ((float(tq.get('pred') or 0) if tq else float(r['size'] or 0) * 0.4) / 1e9 * spgb)
                        J['left'] = ((el / ep - el) + fin_left) if ep > 0.01 else None
                    t['msg'] = f"{J.get('enc') or name} · {J.get('speed') or ''}" + (f" · 還要 {fmt_t(J['left'])}" if J.get('left') else '')
                rc = P.wait(stop=lambda: self.stop_all or J.get('cancel'), stall=600, on_tick=tick); self.procs.discard(P); J['phase'] = 'post'
                if FIN['t'] and rc == 0 and FIN['sz'] > 50e6:                    # 記下這次收尾每 GB 花幾秒（下次預估更準）
                    v_ = (time.time() - FIN['t']) / (FIN['sz'] / 1e9)
                    self.cfg.set('cv_fin_spgb', round(spgb * 0.6 + v_ * 0.4, 2))
                    self.log.w(f'轉檔收尾（把索引移到檔頭）：{fmt_b(FIN["sz"])} 花 {time.time() - FIN["t"]:.0f} 秒（每 GB {v_:.0f} 秒）')
                if rc == -2: raise InterruptedError('取消')
                return rc, (P.errtext() or f'ffmpeg {rc}')
            aargs = ['-c:a', 'copy'] if acopy else ['-c:a', 'aac', '-b:a', '192k']
            self.log.w(f'轉檔開始：{src}（{fmt_b(r["size"])}・{fmt_t(dur)}・{info.get("vcodec")} {info.get("w")}×{info.get("h")}・原檔影像約 {PP["src_vbr"] / 1e6:.1f} Mbps）→ {out}　方法：' + ' → '.join(x['name'] for x in plans) +
                       f'　畫質 {PP["q"]}' + (f'　縮成 {PP["res"]}p' if PP['res'] else '') + (f'　位元率上限 {PP["cap"] / 1e6:.1f} Mbps' if PP['cap'] else '　位元率不封頂') + ('　去交錯' if 'bwdif=0' in vf else '') + ('　聲音直接複製' if acopy else '　聲音轉 AAC'))
            if pre_big:
                ok = True; self.log.w(f'轉檔：{src} 🎯 樣本預估轉完 {fmt_b(tq["pred"])}，不會比原檔 {fmt_b(r["size"])} 小 → 不整部重壓')
            for pl in ([] if pre_big else plans):
                cmd = [pl['ff'], '-hide_banner', '-nostdin', '-loglevel', 'error', '-y'] + pl['pre'] + ['-i', str(src), '-map', '0:v:0', '-map', '0:a?', '-map_metadata', '0', '-sn', '-dn'] + \
                      self._vfa(pl, vf) + pl['v'] + aargs + ['-movflags', '+faststart', '-max_muxing_queue_size', '4096', '-progress', 'pipe:1', '-nostats', str(tmp)]
                J['fullgpu'] = bool(pl.get('gpu_full')); rc, e_ = ffrun(cmd, pl['name'])
                if rc == 0 and tmp.exists():
                    ok = True; break
                err = e_; self.log.w(f'轉檔用 {pl["name"]} 失敗：{src}：{err[-300:]}\n　指令：{cmd_text(cmd)}')
                try: tmp.unlink()
                except Exception: pass
            if not ok: raise RuntimeError(err[-400:])

            def check_len():
                q_ = probe(self.ffprobe, tmp); od = float(q_.get('dur') or 0) if q_.get('ok') else 0
                if not q_.get('ok') or not q_.get('has_v') or (dur > 0 and abs(od - dur) > max(2.0, dur * 0.01)):
                    try: tmp.unlink()
                    except Exception: pass
                    raise RuntimeError(f'轉好的長度不對（原本 {fmt_t(dur)}，轉好 {fmt_t(od)}）' if q_.get('ok') else '轉好的檔讀不出來：' + str(q_.get('err', ''))[-200:])
                return q_
            q = None if pre_big else check_len()
            spot = None
            if tq and not pre_big and plan is not None:                          # 🎯 抽查：直接套用的一定機率抽查；其他方式偶爾抽查（驗證樣本準不準）
                C_ = self.learn_cfg(); rate_ = float(plan.get('spot_rate') or C_['spot']) if plan['mode'] == 'trust' else C_['spot'] * (0.5 if plan['mode'] in ('lite', 'quick') else 0.25)
                if redo and plan['mode'] == 'trust': rate_ = 1.0                     # 重轉要確定有到目標：直接套用的一定抽查
                tries = 0
                while random.random() < rate_ or (tries and spot is not None and spot < C_['floor']):
                    J['enc'] = f'🎯 抽查畫質中（CQ {PP["q"]}）'; J['phase'] = 'check'; spot = self.ssim_check(src, tmp, dur, n=3) or None     # 量不出來（0）≠ 畫質差
                    if not spot or spot >= C_['floor'] or tries >= 2: break
                    tries += 1; old_q = PP['q']; PP['q'] = max(18, int(PP['q']) - 3); plans = self.enc_plans(info, PP)      # 低於底線：更保守重轉
                    self.log.w(f'🎯 抽查沒過：{src.name} CQ {old_q} → SSIM {spot:.4f} < 底線 {C_["floor"]}，改用 CQ {PP["q"]} 重轉（第 {tries} 次）')
                    try: tmp.unlink()
                    except Exception: pass
                    self.learn_add(plan['cls'], {'mode': plan['mode'], 'q': old_q, 'ssim': tq.get('ssim'), 'spot': spot, 'name': src.name, 'note': '抽查沒過 → 重轉', 'spread': tq.get('spread', 0), 'fail': True, 'npts': tq.get('npts')})
                    ok = False
                    for pl in plans:
                        cmd = [pl['ff'], '-hide_banner', '-nostdin', '-loglevel', 'error', '-y'] + pl['pre'] + ['-i', str(src), '-map', '0:v:0', '-map', '0:a?', '-map_metadata', '0', '-sn', '-dn'] + \
                              self._vfa(pl, vf) + pl['v'] + aargs + ['-movflags', '+faststart', '-max_muxing_queue_size', '4096', '-progress', 'pipe:1', '-nostats', str(tmp)]
                        J['fullgpu'] = bool(pl.get('gpu_full')); rc, e_ = ffrun(cmd, pl['name'] + f'（重轉 CQ {PP["q"]}）')
                        if rc == 0 and tmp.exists(): ok = True; break
                    if not ok:
                        try: tmp.unlink()
                        except Exception: pass
                        raise RuntimeError('抽查沒過、重轉也失敗')
                    q = check_len(); tq['q'] = PP['q']; tq['ssim'] = None; tq['redone'] = True; rate_ = 1.0
                if spot is not None: tq['spot'] = spot
                if spot is not None and spot < C_['floor']:                       # V0.1.86 重轉 2 次還是低於底線：不要用這個結果，原檔不動
                    try: tmp.unlink()
                    except Exception: pass
                    why = f'畫質到不了底線（CQ {PP["q"]} 還是 SSIM {spot:.3f} < {C_["floor"]}）'
                    try: self.learn_add(plan['cls'], {'mode': plan['mode'], 'q': int(PP['q']), 'ssim': None, 'spot': spot, 'name': src.name, 'note': why, 'fail': True, 'no_rate': True})
                    except Exception: self.log.err('滾動式參數記錄')
                    if redo:
                        self.db.x("UPDATE files SET cv_state=3,cv_redo=0,cv_err=? WHERE id=?", (f'重轉沒成功：{why}，留著舊的 MP4', fid))
                        self.done(t, 'fail', f'重轉沒成功：{why}'); self.log.w(f'🔁 重轉沒成功：{src} → {why}，舊的 MP4 留著'); return
                    self.db.x("UPDATE files SET cv_state=6,cv_err=?,cv_t=? WHERE id=?", (f'{why}，保留原檔', time.time(), fid))
                    self.done(t, 'done', f'{why}，保留原檔'); self.log.w(f'🎯 {src}：{why} → 不用轉好的，原檔不動'); return
            if redo:                                                             # 重轉：達到目標才換掉舊的 MP4；原檔一直留在 DELETE
                tgt_ = float(self.cfg.get('cv_target') or 0.985); sc_ = (tq or {}).get('spot') or (tq or {}).get('ssim') or 0
                okq = bool(tq) and not pre_big and (tq.get('ok') or (tq.get('spot') or 0) >= tgt_) and sc_ >= tgt_ - 1e-9
                osz = src.stat().st_size
                if not okq:
                    try: tmp.unlink()
                    except Exception: pass
                    why = '樣本就看得出轉了不會比原檔小' if pre_big else (f'最好只到 SSIM {sc_:.3f}，沒到 {tgt_:.3f}' if tq else '找不到設定')
                    self.db.x("UPDATE files SET cv_state=3,cv_redo=0,cv_err=? WHERE id=?", (f'重轉沒成功：{why}，留著舊的 MP4', fid))
                    self.done(t, 'fail', f'重轉沒成功：{why}'); self.log.w(f'🔁 重轉沒成功：{src} → {why}，舊的 MP4 留著，原檔還在 DELETE'); return
                nsz = tmp.stat().st_size; old = mp4.stat().st_size if mp4.exists() else 0
                if nsz >= osz * 0.98:                                            # 重壓了還是沒比原檔小：留著舊的
                    try: tmp.unlink()
                    except Exception: pass
                    why = f'重壓到目標畫質後 {fmt_b(nsz)}，沒有比原檔 {fmt_b(osz)} 小'
                    self.db.x("UPDATE files SET cv_state=3,cv_redo=0,cv_err=? WHERE id=?", (f'重轉沒成功：{why}，留著舊的 MP4', fid))
                    self.done(t, 'fail', f'重轉沒成功：{why}'); self.log.w(f'🔁 重轉沒成功：{src} → {why}，舊的 MP4 留著'); return
                self._place(tmp, mp4, J); st_ = mp4.stat()
                sets = {'size': int(st_.st_size), 'mtime': float(st_.st_mtime), 'cv_state': 3, 'cv_redo': 0, 'cv_err': '', 'cv_ssim': float(sc_), 'cv_nsz': int(nsz), 'cv_osz': int(osz),
                        'cv_ratio': nsz / osz if osz else 0, 'cv_t': time.time()}
                sets.update(cv_cq=int(tq['q']), cv_how='redo-' + str((plan or {}).get('mode') or 'full'), cv_gpu=1 if J.get('fullgpu') else 0)
                self.db.x('UPDATE files SET ' + ','.join(f'{k}=?' for k in sets) + ' WHERE id=?', (*sets.values(), fid))
                if plan is not None:
                    self.learn_add(plan['cls'], {'mode': plan['mode'], 'q': int(tq['q']), 'ssim': tq.get('ssim'), 'spot': tq.get('spot'), 'spread': tq.get('spread', 0), 'name': src.name,
                                                 'npts': tq.get('npts'), 'seg': tq.get('seg'), 'sec': round(tq.get('sec') or 0, 1), 'ratio': round(nsz / osz, 4) if osz else None, 'note': '重轉',
                                                 'ok': tq.get('ok', True), 'after_fail': bool(tq.get('redone'))})
                if (self.cfg.get('cv_after') or '') == 'auto_del' and sc_ >= tgt_ - 1e-9 and (tq.get('ssim') is not None or tq.get('spot')):
                    try:
                        os.remove(str(src)); self.db.x("UPDATE files SET cv_del='' WHERE id=?", (fid,)); self.log.w(f'🔁 重轉到目標 → DELETE 裡的原檔直接刪掉：{src}（{fmt_b(osz)}）')
                    except Exception as ex_: self.log.w(f'🔁 重轉到目標，但 DELETE 裡的原檔刪不掉：{src}：{ex_}')
                self.done(t, 'done', f'重轉 CQ {tq["q"]} · {fmt_b(old)} → {fmt_b(nsz)}（原檔 {fmt_b(osz)} 的 {nsz * 100 / max(1, osz):.0f}%）SSIM {sc_:.3f}')
                self.oplog('conv', src=str(src), dst=str(mp4), fid=fid, size=nsz, detail=f'🔁 用新方式重轉（CQ {tq["q"]}，SSIM {sc_:.3f}）：舊的 MP4 {fmt_b(old)} → 新的 {fmt_b(nsz)}；原檔還在 DELETE')
                self.log.w(f'🔁 重轉成功：{src} → {mp4}（CQ {tq["q"]}，SSIM {sc_:.4f}，舊 {fmt_b(old)} → 新 {fmt_b(nsz)}，原檔 {fmt_b(osz)} 還在 DELETE，等你自己刪）'); return
            inplace = os.path.normcase(str(out)) == os.path.normcase(str(src))           # H.264 MP4 → H.265：轉好的用原本的檔名
            osz = src.stat().st_size; nsz = (tq['pred'] if pre_big else tmp.stat().st_size); ratio = nsz / osz if osz else 0
            after = self.cfg.get('cv_after') or 'delete_dir'; note = ''; ssim = 0.0; remux = False
            if after == 'keep': after = 'delete_dir'                             # V0.1.57 同一個資料夾不能同時有 MP4 和原檔：原檔一律先搬到 DELETE
            if nsz >= osz * 0.92:                                                 # V0.1.57 不管什麼格式：轉了沒變小 → 不用這個結果
                vc = str(info.get('vcodec') or '').lower(); was = f'{fmt_b(osz)} → {"預估 " if pre_big else ""}{fmt_b(nsz)}，{ratio * 100:.0f}%'
                try: tmp.unlink()
                except Exception: pass
                if not inplace and vc in ('h264', 'hevc') and not PP['res'] and 'bwdif=0' not in vf:   # 原本就是 H.264／H.265：只換成 MP4 外殼（不重壓，畫質完全一樣）
                    self.log.w(f'轉檔：{src} 重壓沒有變小（{was}）→ 改成只換 MP4 外殼（影像直接複製）')
                    cmd = [self.ff, '-hide_banner', '-nostdin', '-loglevel', 'error', '-y', '-i', str(src), '-map', '0:v:0', '-map', '0:a?', '-map_metadata', '0', '-sn', '-dn', '-c:v', 'copy'] + \
                          (['-tag:v', 'hvc1'] if vc == 'hevc' else []) + aargs + ['-movflags', '+faststart', '-max_muxing_queue_size', '4096', '-progress', 'pipe:1', '-nostats', str(tmp)]
                    rc, e_ = ffrun(cmd, '只換 MP4 外殼（不重壓）')
                    if rc == 0 and tmp.exists():
                        try:
                            q = check_len(); nsz = tmp.stat().st_size; ratio = nsz / osz if osz else 0; remux = True
                            note += f'；重壓沒有變小（{was}）→ 只換成 MP4 外殼，畫質完全不變'
                        except RuntimeError as ex2: self.log.w(f'轉檔：只換外殼也不行：{src}：{ex2}')
                    else:
                        self.log.w(f'轉檔：只換外殼失敗：{src}：{e_[-300:]}')
                        try: tmp.unlink()
                        except Exception: pass
                if not remux:
                    self.db.x("UPDATE files SET cv_state=6,cv_err=?,cv_osz=?,cv_nsz=?,cv_t=? WHERE id=?", (f'轉好沒有變小（{was}），保留原檔', osz, nsz, time.time(), fid))
                    self.done(t, 'done', f'沒有變小（{ratio * 100:.0f}%），保留原檔'); self.log.w(f'轉檔：{src} 轉好 {was} 沒有變小，放棄、原檔不動')
                    return
            if tq and tq.get('trust'): note += f'；🎯 直接用經驗值 CQ {tq["q"]}（{plan.get("reason", "")}）'
            elif tq and tq.get('ssim') is not None: note += f'；🎯 自動選 CQ {tq["q"]}（{plan["mode"] if plan else ""} 樣本 SSIM {tq["ssim"]:.3f}{"" if tq["ok"] else "，沒到目標"}，找了 {tq["sec"]:.0f} 秒）'
            elif tq: note += f'；🎯 CQ {tq["q"]}（抽查沒過重轉）'
            try: self.db.x('UPDATE files SET cv_cq=?, cv_how=?, cv_gpu=? WHERE id=?', (0 if remux else int(PP['q']), 'remux' if remux else ((plan or {}).get('mode') or 'fixed'), 1 if J.get('fullgpu') else 0, fid))   # V0.1.70 記下用了哪個 CQ、哪種方式
            except Exception: pass
            if tq and plan is not None:
                try:
                    self.learn_add(plan['cls'], {'mode': plan['mode'], 'q': int(tq['q']), 'ssim': tq.get('ssim'), 'spot': tq.get('spot'), 'spread': tq.get('spread', 0), 'name': src.name,
                                                 'npts': tq.get('npts'), 'seg': tq.get('seg'), 'sec': round(tq.get('sec') or 0, 1), 'ratio': round(nsz / osz, 4) if osz and not remux else None,
                                                 'note': '只換外殼' if remux else ('抽查沒過後重轉' if tq.get('redone') else ''), 'remux': bool(remux), 'ok': tq.get('ok', True), 'after_fail': bool(tq.get('redone'))})
                except Exception: self.log.err('滾動式參數記錄')
            if remux: ssim = 1.0
            elif tq and tq.get('trust') and not tq.get('spot'):                  # 直接套用、這部沒抽到：不整部重比，分數用這一類的經驗值（標「經驗估」）
                ssim = float(tq.get('est') or 0); note += f'；畫質＝這一類的經驗估 {ssim:.3f}（沒抽到查）'
            elif tq and (tq.get('spot') or tq.get('ssim')):                       # V0.1.64 🎯 自動模式：轉之前已經用樣本比過畫質，轉完不用再整部比一次（抽查到的用抽查的）
                ssim = float(tq.get('spot') or tq['ssim']); note += '；畫質＝' + ('轉完抽查的' if tq.get('spot') else f'轉檔前 {tq.get("npts") or 5} 段樣本比的（不再整部重比）')
                if ssim < 0.90:
                    note += '（⚠ 偏低，原檔在 DELETE，先抽檢再決定）'
                    if after == 'recycle': after = 'delete_dir'
            elif self.cfg.get('cv_verify') is not False or (self.cfg.get('lab') or {}).get('conv_ssim'):   # V0.1.53 每部都自動抽查畫質（V0.1.57：抽 5 個地方取中間值）
                J['enc'] = (J.get('enc') or '') + '・自動驗證畫質中'; ssim = self.ssim_check(src, tmp, dur)
                J['enc'] = J['enc'].replace('・自動驗證畫質中', '')
                if ssim: note += f'；畫質抽查 SSIM {ssim:.3f}'
                if ssim and ssim < 0.90:
                    if inplace:
                        try: tmp.unlink()
                        except Exception: pass
                        raise RuntimeError(f'畫質抽查偏低（SSIM {ssim:.3f}），為了安全放棄這次、原檔不動')
                    note += '（⚠ 偏低，原檔在 DELETE，先抽檢再決定）'; self.log.w(f'⚠ 畫質抽查偏低（SSIM {ssim:.3f}）：{src}，原檔照樣搬到 DELETE（同一個資料夾不留兩份），等你抽檢')
                    if after == 'recycle': after = 'delete_dir'                      # 偏低：不要直接丟回收筒
            measured = not (tq and tq.get('trust') and not tq.get('spot'))      # 有真的量過畫質（不是「經驗估」）
            if after == 'auto_del':                                              # V0.1.95 畫質到目標（量過的）→ 原檔直接刪；0.975～目標 → 搬到 DELETE 等你確認
                tg_ = float(self.cfg.get('cv_target') or 0.985)
                if ssim and ssim >= tg_ - 1e-9 and measured and not inplace: after = 'perm'
                else:
                    after = 'delete_dir'
                    if ssim and ssim < tg_: note += f'；畫質 {ssim:.3f} 沒到 {tg_:.3f} → 原檔留在 DELETE 等你確認'
                    elif not measured: note += '；畫質是經驗估、沒有實際量 → 原檔留在 DELETE 等你確認'
            if inplace:
                if after in ('keep', 'perm'): after = 'delete_dir'                # 同一個檔名只能放一個：原檔一定要先移開
                dst = self.del_path(src) if after != 'orig' else (self.arch_dir('orig', src) / src.name)
                if after == 'recycle':
                    if not send_to_recycle(src): dst = self.copy_file(src, self.del_path(src), None, move=True); after = 'delete_dir'
                else: dst = self.copy_file(src, dst, None, move=True)
                self._place(tmp, out, J); note += '；原檔丟到資源回收筒' if after == 'recycle' else f'；原檔先搬到 {Path(dst).parent}（抽檢沒問題再到「轉檔完成」按刪除）'
                self._conv_takeover(fid, src, out, q, osz, nsz, keep_orig=False)
                self.db.x('UPDATE files SET cv_state=3,cv_out=?,cv_err=\'\',cv_ratio=?,cv_ssim=?,cv_src=?,cv_del=?,cv_osz=?,cv_nsz=?,cv_t=? WHERE id=?',
                          (str(out), ratio, ssim, str(src), '' if after == 'recycle' else str(dst), osz, nsz, time.time(), fid))
                if after != 'recycle' and EXT_MOVED.get('fn'):                    # V0.5.41 同名轉檔：原檔搬開，整理的紀錄跟著搬
                    try: EXT_MOVED['fn'](str(src), str(dst))
                    except Exception: pass
                self.cv_done_log.append((time.time(), dur, osz, nsz)); self._trial_learn(fid, PP, nsz)
                self.done(t, 'done', f'{J.get("enc", "")} · {fmt_b(osz)} → {fmt_b(nsz)}（{ratio * 100:.0f}%）{note}')
                self.oplog('conv', src=str(src), dst=str(out), fid=fid, size=nsz, detail=f'H.264→H.265 {J.get("enc", "")}，{fmt_b(osz)} → {fmt_b(nsz)}{note}')
                self.log.w(f'轉檔完成（同檔名）：{src}（{J.get("enc")}，{fmt_b(osz)} → {fmt_b(nsz)}，{time.time() - J.get("t0", time.time()):.0f} 秒）{note}')
                return
            self._place(tmp, out, J)
            dele = ''
            if after == 'orig':
                bd = self.arch_dir('orig', src); dst = self.copy_file(src, bd / src.name, None, move=True); note += f'；原檔搬到 {dst.parent}'; dele = str(dst)
            elif after == 'perm':
                try:
                    try: os.chmod(str(src), 0o666)
                    except Exception: pass
                    os.remove(str(src)); note += f'；畫質 {ssim:.3f} 到目標 → 原檔直接刪掉（{fmt_b(osz)}）'
                except Exception as ex_:
                    dst = self.copy_file(src, self.del_path(src), None, move=True); dele = str(dst); note += f'；原檔刪不掉（{ex_}）→ 先搬到 {dst.parent}'
            elif after == 'delete_dir':
                dst = self.del_path(src); dst = self.copy_file(src, dst, None, move=True); note += f'；原檔先搬到 {dst.parent}（抽檢沒問題再到「轉檔完成」按刪除）'; dele = str(dst)
            elif after == 'recycle':
                if send_to_recycle(src): note += '；原檔丟到資源回收筒'
                else:                                                            # 丟不了回收筒：也不要和 MP4 留在同一個資料夾
                    dst = self.copy_file(src, self.del_path(src), None, move=True); dele = str(dst); note += f'；原檔沒丟成資源回收筒 → 先搬到 {dst.parent}'
            self._conv_takeover(fid, src, out, q, osz, nsz, keep_orig=src.exists())
            self.db.x('UPDATE files SET cv_state=3,cv_out=?,cv_err=\'\',cv_ratio=?,cv_ssim=?,cv_src=?,cv_del=?,cv_osz=?,cv_nsz=?,cv_t=? WHERE id=?', (str(out), ratio, ssim, str(src), dele, osz, nsz, time.time(), fid))
            if dele and EXT_MOVED.get('fn'):                                     # V0.5.40 原檔搬到 DELETE：整理的紀錄跟著搬
                try: EXT_MOVED['fn'](str(src), dele)
                except Exception: pass
            self.cv_done_log.append((time.time(), dur, osz, nsz)); self._trial_learn(fid, PP, nsz)
            self.done(t, 'done', f'{J.get("enc", "")} · {fmt_b(osz)} → {fmt_b(nsz)}（{ratio * 100:.0f}%）{note}')
            self.oplog('conv', src=str(src), dst=str(out), fid=fid, size=nsz, detail=f'轉檔 {J.get("enc", "")}，{fmt_b(osz)} → {fmt_b(nsz)}{note}')
            self.log.w(f'轉檔完成：{src} → {out}（{J.get("enc")}，{fmt_b(osz)} → {fmt_b(nsz)}，{time.time() - J.get("t0", time.time()):.0f} 秒）{note}')
        except InterruptedError:
            rq_ = J.get('requeue') or self.stop_all                              # 關程式／熱更新：放回排隊（不算取消）
            try: self.db.x('UPDATE files SET cv_state=? WHERE id=?', (1 if rq_ else (3 if redo else 5), fid))
            except Exception: pass
            for x in (locals().get('tmp'),):
                try:
                    if x is not None and Path(x).exists(): Path(x).unlink()
                except Exception: pass
            self.done(t, 'stop', '放回排隊' if rq_ else '取消')
        except Exception as ex:
            try:
                if 'tmp' in locals() and Path(tmp).exists(): Path(tmp).unlink()        # 做到一半的暫存檔（可能很大）
            except Exception: pass
            if self.gone_reason(str(src)) == 'offline':
                self.db.x('UPDATE files SET cv_state=1 WHERE id=?', (fid,)); self.done(t, 'stop', '硬碟離線，接回來再轉'); self.log.w(f'轉檔：{src} 所在的硬碟離線，放回排隊（接回來會重轉）')
            elif redo:
                self.db.x('UPDATE files SET cv_state=3,cv_redo=0,cv_err=? WHERE id=?', ('重轉失敗：' + str(ex)[-300:], fid)); self.done(t, 'fail', str(ex)[-200:])
                self.log.w(f'🔁 重轉失敗：{src}：{str(ex)[-300:]}（舊的 MP4 留著）')
            else:
                self.db.x('UPDATE files SET cv_state=4,cv_err=? WHERE id=?', (str(ex)[-400:], fid)); self.done(t, 'fail', str(ex)[-200:])
                self.log.w(f'轉檔失敗：{src}：{str(ex)[-300:]}')
        finally:
            self.cv_active.pop(fid, None)

    def del_path(self, src):
        """X:\\DELETE\\原本的資料夾\\檔名（保留資料夾結構，不會撞名）."""
        src = Path(src); anc = Path(src.anchor or '/')
        try: rel = src.relative_to(anc)
        except Exception: rel = Path(src.name)
        return unique_path(anc / DEL_DIR / rel)

    def _conv_takeover(self, fid, src, out, q, osz, nsz, keep_orig=False):
        """轉好的 MP4 接手原本這筆資料：同一個編號 → 預覽圖、分級、標籤、人臉都沿用，不用重做.
        原檔還留在原位（「留著不動」）時，原檔另外變成一筆新的（之後掃描會補預覽圖）."""
        try:
            st = out.stat(); outs = str(out)
            dup = self.db.one('SELECT id FROM files WHERE path=? AND id!=?', (outs, fid))
            if dup is not None:                                                  # 之前掃描先把 MP4 當新檔加進來了：拿掉那筆（這筆才有預覽圖和分級）
                self.db.x('DELETE FROM files WHERE id=?', (int(dup[0]),)); self.log.w(f'轉檔：{outs} 之前被當成新檔（id {dup[0]}），合併回原本這筆 id {fid}')
            sets = {'path': outs, 'folder': str(out.parent), 'name': out.name, 'ext': out.suffix.lower(), 'size': int(st.st_size), 'mtime': float(st.st_mtime), 'missing': 0}
            if q and q.get('ok'):
                for k in ('vcodec', 'acodecs', 'vbr', 'pix', 'fps', 'w', 'h'):
                    if q.get(k) not in (None, ''): sets[k] = q.get(k)
            self.db.x('UPDATE files SET ' + ','.join(f'{k}=?' for k in sets) + ' WHERE id=?', (*sets.values(), fid))
            if keep_orig:
                rr = self.root_of(src) or ''
                self.db.x("INSERT OR IGNORE INTO files(path,root,folder,name,ext,size,mtime,seen) VALUES(?,?,?,?,?,?,?,?)",
                          (str(src), str(rr), str(Path(src).parent), Path(src).name, Path(src).suffix.lower(), int(osz or 0), float(Path(src).stat().st_mtime), time.time()))
            self.log.w(f'轉檔：id {fid} 改成 {outs}（{fmt_b(osz)} → {fmt_b(nsz)}），預覽圖、分級、人物照舊沿用')
        except Exception: self.log.err('轉檔：轉好的接手原本的資料')

    CONV_SORT = {'size_desc': 'size DESC', 'size_asc': 'size ASC', 'name': 'name COLLATE NOCASE', 'folder': 'folder COLLATE NOCASE, name COLLATE NOCASE',
                 'dur_desc': 'dur DESC', 'mtime_desc': 'mtime DESC', 'ext': 'ext, size DESC',
                 'smart': 'CASE WHEN dur>0 THEN size*1.0/dur ELSE 0 END DESC, size DESC'}      # 最省空間優先：位元率高的先轉（同樣時間省最多）

    HEVC = ("'hevc'", "'h265'", "'av1'", "'vp9'")

    def _cv_index(self):
        if getattr(self, '_cvix', False): return
        try: self.db.x('CREATE INDEX IF NOT EXISTS ix_files_cvosz ON files(cv_osz) WHERE cv_state=3'); self._cvix = True
        except Exception:
            try: self.db.x('CREATE INDEX IF NOT EXISTS ix_files_cvosz2 ON files(cv_osz)'); self._cvix = True
            except Exception: self.log.err('轉檔索引')

    def conv_where(self, exts=None, smin=0, smax=0, folders=None, states=(0, 4, 5), kind='nonmp4'):
        """轉檔範圍：種類（非 MP4／H.264 MP4）、類型、大小（MB）、資料夾（含子資料夾）；空的＝不限."""
        F = [str(f).rstrip('\\/') for f in (folders or []) if str(f).strip()]
        w = ["missing=0"] + ([] if F else ["arch=''"]) + [                     # V0.2.22 有指定資料夾時，已歸檔的（例如 VideoSIFT\S_無條件保存）也可以轉
             "NOT (upper(substr(folder,2,8))=':\\DELETE' AND (length(folder)=9 OR substr(folder,10,1)='\\'))",           # V0.1.93 X:\DELETE\ 裡的（轉好後暫放的原檔）不再轉
             "NOT EXISTS (SELECT 1 FROM files f2 WHERE f2.cv_state=3 AND f2.cv_osz=files.size AND f2.id!=files.id AND lower(substr(f2.cv_src, -length(files.name)))=lower(files.name))"]   # 已經轉過的同一個原檔（同名同大小）又被匯進來：不再轉
        a = []; self._cv_index()
        h264 = f"(ext IN ('.mp4','.m4v') AND probed=1 AND has_v=1 AND lower(vcodec) NOT IN ({','.join(self.HEVC)}))"
        if kind == 'vs': w.append(f"{VS_SQL} AND probed=1 AND has_v=1")          # 已經轉過（檔名有 _VS）的，要再轉一次
        else:
            w.append({'h264': h264, 'all': f"(ext NOT IN ('.mp4','.m4v') OR {h264})"}.get(kind, "ext NOT IN ('.mp4','.m4v')"))
            w.append(f"NOT {VS_SQL}")                                           # V0.1.94 檔名有 _VS 的不混在一般的裡面（另外問）
        if states is not None: w.append(f"cv_state IN ({','.join(str(int(x)) for x in states)})")
        E = [('.' + str(x).lower().lstrip('.')) for x in (exts or []) if str(x).strip()]
        if E: w.append(f"ext IN ({','.join('?' * len(E))})"); a += E
        if smin: w.append('size>=?'); a.append(int(float(smin) * 1048576))
        if smax: w.append('size<=?'); a.append(int(float(smax) * 1048576))
        if F:
            ors = []
            for f in F: ors.append('(folder=? OR substr(folder,1,?)=? OR substr(folder,1,?)=?)'); a += [f, len(f) + 1, f + '\\', len(f) + 1, f + '/']
            w.append('(' + ' OR '.join(ors) + ')')
        return ' AND '.join(w), a

    def conv_candidates(self, exts=None, smin=0, smax=0, folders=None, sort='size_desc', states=(0, 4, 5), limit=5000, kind='nonmp4'):
        w, a = self.conv_where(exts, smin, smax, folders, states, kind)
        rows = [dict(r) for r in self.db.q(f'SELECT id,name,folder,path,ext,size,dur,vcodec,w,h,fps,vbr,field,acodecs,cv_state,cv_err,th_state FROM files WHERE {w} ORDER BY {self.CONV_SORT.get(sort, "size DESC")} LIMIT ?', (*a, int(limit)))]
        tot = self.db.one(f'SELECT COUNT(*), SUM(size), SUM(dur) FROM files WHERE {w}', a)
        RM = self.learn_ratio_map(); gr = self.conv_ratio(); g_ = gr[0] if gr[1] else 0.5; est = 0; hit = 0
        for r in rows:                                                           # V0.1.66 預估省：有同類經驗就用同類的平均（比較準），沒有就用全部的平均
            try: c_ = self.tq_class(r)
            except Exception: c_ = ''
            x = RM.get(c_)
            if x: hit += 1
            r['est_ratio'] = min(1.0, x[0] if x else g_); r['est_n'] = x[1] if x else 0; est += int((r['size'] or 0) * (1 - r['est_ratio']))
        allb = int(tot[1] or 0); lb = sum(int(r['size'] or 0) for r in rows)
        est_all = est + int(max(0, allb - lb) * (1 - g_))
        try: vs_n = int(self.db.one(f"SELECT COUNT(*) FROM files WHERE missing=0 AND arch='' AND cv_state IN (0,4,5) AND {VS_SQL}")[0] or 0) if kind != 'vs' else 0
        except Exception: vs_n = 0
        why = ''
        if not int(tot[0] or 0) and folders:
            try: why = self.conv_why(folders, kind)
            except Exception: why = ''
        return {'rows': rows, 'n': int(tot[0] or 0), 'bytes': allb, 'dur': float(tot[2] or 0), 'est_save': est_all, 'est_hit': hit, 'vs_n': vs_n, 'why': why}

    def conv_why(self, folders, kind='nonmp4'):
        """V0.2.22 選的資料夾裡範圍內 0 部時，說明裡面的檔案為什麼沒列出來."""
        F = [str(f).rstrip('\\/') for f in (folders or []) if str(f).strip()]
        if not F: return ''
        ors = []; a = []
        for f in F: ors.append('(folder=? OR substr(folder,1,?)=? OR substr(folder,1,?)=?)'); a += [f, len(f) + 1, f + '\\', len(f) + 1, f + '/']
        fw = 'missing=0 AND (' + ' OR '.join(ors) + ')'
        q1 = lambda c: int((self.db.one(f'SELECT COUNT(*) FROM files WHERE {fw} AND ({c})', a) or [0])[0] or 0)
        n = q1('1')
        if not n: return '這個資料夾在影片庫裡沒有任何檔案（可能還沒掃描到：到 💽 影片庫 把它所在的硬碟／資料夾加進來）'
        hv = ','.join(self.HEVC); P = []
        k = q1(f"probed=1 AND has_v=1 AND lower(vcodec) IN ({hv})")
        if k: P.append(f'已經是 H.265／新格式 {k:,} 部（不用再轉）')
        k = q1('cv_state=3')
        if k: P.append(f'已經轉好 {k:,} 部')
        k = q1('cv_state IN (1,2)')
        if k: P.append(f'排隊／轉檔中 {k:,} 部')
        k = q1('probed IN (0,2)')
        if k: P.append(f'還沒讀取影片資訊 {k:,} 部（掃描讀完後才會列出）')
        k = q1('probed=3 OR (probed=1 AND has_v=0)')
        if k: P.append(f'讀不到畫面／壞檔 {k:,} 部')
        k = q1(VS_SQL)
        if k and kind != 'vs': P.append(f'檔名有 _VS {k:,} 部（種類選「🏷 已轉過的」）')
        if kind == 'h264':
            k = q1("ext NOT IN ('.mp4','.m4v')")
            if k: P.append(f'不是 MP4 的 {k:,} 部（種類選「非 MP4」或「兩種都要」）')
        elif kind == 'nonmp4':
            k = q1(f"ext IN ('.mp4','.m4v') AND probed=1 AND has_v=1 AND lower(vcodec) NOT IN ({hv})")
            if k: P.append(f'H.264 MP4 {k:,} 部（種類選「H.264 MP4 → H.265」或「兩種都要」）')
        return f'這個資料夾有 {n:,} 部，但都不在範圍內：' + '；'.join(P) if P else f'這個資料夾有 {n:,} 部，但都不符合目前的條件（類型／大小）'


    def learn_ratio_map(self):
        """每一類轉完平均變成原檔的幾 %（只算真的重壓的，最近 60 次）：{類型: (比例, 次數)}."""
        out = {}
        try:
            for cls, c in list(self.learn_db().items()):
                R = [x['ratio'] for x in (c.get('hist') or [])[-60:] if x.get('ratio')]
                if len(R) >= 2: out[cls] = (sum(R) / len(R), len(R))
        except Exception: pass
        return out

    def conv_add_filtered(self, exts=None, smin=0, smax=0, folders=None, sort='size_desc', kind='nonmp4', limit=0):
        """照範圍＋排序一次加進排隊（排在現有排隊的後面）；limit＞0＝只加前幾部（V0.6.11 數量控制）."""
        w, a = self.conv_where(exts, smin, smax, folders, (0, 4, 5), kind)
        lim = int(limit or 0)
        ids = [int(r[0]) for r in self.db.q(f'SELECT id FROM files WHERE {w} ORDER BY {self.CONV_SORT.get(sort, "size DESC")}' + (' LIMIT ?' if lim > 0 else ''), (*a, lim) if lim > 0 else a)]
        n = self.conv_add(ids); self.log.w(f'轉檔：照範圍加入 {n} 部（類型 {exts or "全部"}、大小 {smin or 0}～{smax or "不限"} MB、資料夾 {folders or "全部"}、排序 {sort}' + (f'、只取前 {lim} 部' if lim > 0 else '') + '）'); return n

    # ================================================================ 🗂 檔案總覽（V0.6.19：像 Everything 搜尋 ＋ TreeSize 資料夾大小）
    @staticmethod
    def _like_esc(t): return str(t).replace('^', '^^').replace('%', '^%').replace('_', '^_')

    def explore(self, prefix='', sort='size'):
        """一層一層看：prefix＝''（看每個影片庫根目錄）或某個資料夾；回這一層底下每個子資料夾的大小、檔數、能轉幾部、預估省多少.
        sort：size（大小）／n（檔數）／save（可省）／name（名稱）."""
        prefix = str(prefix or '').rstrip('\\/')
        ck = (prefix.lower(), sort); C = getattr(self, '_exp_cache', None)
        if C is None: C = self._exp_cache = {}
        hit = C.get(ck)
        if hit and time.time() - hit[0] < 30: return hit[1]
        ratio = (self.conv_ratio() or (0.5, 0))[0] or 0.5
        cw, ca = self.conv_where(None, 0, 0, None, (0, 4, 5), 'all')
        if not prefix:
            rows = self.db.q("SELECT root, COUNT(*), SUM(size) FROM files WHERE missing=0 GROUP BY root")
            crow = {r[0]: (r[1], r[2]) for r in self.db.q(f"SELECT root, COUNT(*), SUM(size) FROM files WHERE {cw} GROUP BY root", ca)}
            items = []
            for r in rows:
                if not r[0]: continue
                cn, cb = crow.get(r[0], (0, 0))
                items.append({'name': str(r[0]), 'path': str(r[0]), 'n': int(r[1] or 0), 'size': int(r[2] or 0), 'conv_n': int(cn or 0), 'conv_b': int(cb or 0), 'save': int((cb or 0) * (1 - min(1.0, ratio))), 'dir': True})
            here = {'n': 0, 'size': 0}
        else:
            eq = prefix + '\\' if prefix.endswith(':') else prefix               # 磁碟根目錄（H:）的資料夾欄位是 H:\\
            lk = self._like_esc(eq.rstrip('\\')) + '\\%'
            wh = "(folder=? OR folder LIKE ? ESCAPE '^')"
            agg = {}; here = {'n': 0, 'size': 0, 'conv_n': 0, 'conv_b': 0}
            def key(folder):
                rel = str(folder or '')[len(eq):].lstrip('\\/')
                return rel.split('\\')[0].split('/')[0] if rel else ''
            for f, n, b in self.db.q(f"SELECT folder, COUNT(*), SUM(size) FROM files WHERE missing=0 AND {wh} GROUP BY folder", (eq, lk)):
                k = key(f); d = agg.setdefault(k, {'n': 0, 'size': 0, 'conv_n': 0, 'conv_b': 0}); d['n'] += int(n or 0); d['size'] += int(b or 0)
            for f, n, b in self.db.q(f"SELECT folder, COUNT(*), SUM(size) FROM files WHERE {cw} AND {wh} GROUP BY folder", (*ca, eq, lk)):
                k = key(f); d = agg.setdefault(k, {'n': 0, 'size': 0, 'conv_n': 0, 'conv_b': 0}); d['conv_n'] += int(n or 0); d['conv_b'] += int(b or 0)
            items = []
            for k, d in agg.items():
                if k == '': here = d; continue
                items.append({'name': k, 'path': eq.rstrip('\\') + '\\' + k, **d, 'save': int(d['conv_b'] * (1 - min(1.0, ratio))), 'dir': True})
            here = {**here, 'save': int(here.get('conv_b', 0) * (1 - min(1.0, ratio)))}
        keyf = {'n': lambda x: -x['n'], 'save': lambda x: -x['save'], 'name': lambda x: x['name'].lower()}.get(sort, lambda x: -x['size'])
        items.sort(key=keyf)
        tot = {'n': sum(x['n'] for x in items) + int(here.get('n') or 0), 'size': sum(x['size'] for x in items) + int(here.get('size') or 0),
               'conv_n': sum(x.get('conv_n', 0) for x in items) + int(here.get('conv_n') or 0), 'save': sum(x.get('save', 0) for x in items) + int(here.get('save') or 0)}
        parent = ''
        if prefix:
            r_ = self.root_of(prefix) if hasattr(self, 'root_of') else None
            if not (r_ and os.path.normcase(prefix.rstrip('\\/')) == os.path.normcase(str(r_).rstrip('\\/'))) and '\\' in prefix:
                parent = prefix.rsplit('\\', 1)[0]
        try:                                                                     # V0.6.20 這裡最大的 20 個檔、各種格式佔多少
            if prefix: fw, fa = "missing=0 AND (folder=? OR folder LIKE ? ESCAPE '^')", (eq, lk)
            else: fw, fa = 'missing=0', ()
            big = [{'id': int(r[0]), 'name': r[1], 'folder': r[2], 'size': int(r[3] or 0), 'vcodec': r[4] or '', 'cv': int(r[5] or 0)}
                   for r in self.db.q(f"SELECT id, name, folder, size, vcodec, cv_state FROM files WHERE {fw} ORDER BY size DESC LIMIT 20", fa)]
            exts = [{'ext': (r[0] or '').lower() or '（沒有）', 'n': int(r[1] or 0), 'size': int(r[2] or 0)}
                    for r in self.db.q(f"SELECT lower(ext), COUNT(*), SUM(size) FROM files WHERE {fw} GROUP BY lower(ext) ORDER BY SUM(size) DESC LIMIT 12", fa)]
            codecs = [{'codec': (r[0] or '').lower() or '（還沒讀）', 'n': int(r[1] or 0), 'size': int(r[2] or 0)}
                      for r in self.db.q(f"SELECT lower(vcodec), COUNT(*), SUM(size) FROM files WHERE {fw} GROUP BY lower(vcodec) ORDER BY SUM(size) DESC LIMIT 8", fa)]
        except Exception: big, exts, codecs = [], [], []
        out = {'ok': True, 'prefix': prefix, 'parent': parent, 'items': items, 'here': here, 'tot': tot, 'ratio': ratio, 'sort': sort, 't': time.time(), 'big': big, 'exts': exts, 'codecs': codecs}
        C[ck] = (time.time(), out)
        if len(C) > 200: C.clear()
        return out

    def explore_search(self, q, prefix='', sort='size', limit=500):
        """像 Everything：空白分開的每個字都要出現在完整路徑裡（不分大小寫）；可以限定在某個資料夾底下."""
        toks = [t for t in str(q or '').lower().split() if t][:8]
        if not toks: return {'ok': True, 'rows': [], 'more': False}
        w = ['missing=0']; a = []
        for t in toks: w.append("lower(path) LIKE ? ESCAPE '^'"); a.append('%' + self._like_esc(t) + '%')
        prefix = str(prefix or '').rstrip('\\/')
        if prefix:
            eq = prefix + '\\' if prefix.endswith(':') else prefix
            w.append("(folder=? OR folder LIKE ? ESCAPE '^')"); a += [eq, self._like_esc(eq.rstrip('\\')) + '\\%']
        order = {'name': 'name COLLATE NOCASE', 'mtime': 'mtime DESC', 'path': 'path COLLATE NOCASE'}.get(sort, 'size DESC')
        lim = max(10, min(5000, int(limit or 500)))
        R = self.db.q(f"SELECT id, path, name, folder, ext, size, mtime, vcodec, cv_state FROM files WHERE {' AND '.join(w)} ORDER BY {order} LIMIT ?", (*a, lim + 1))
        rows = [{'id': int(r[0]), 'path': r[1], 'name': r[2], 'folder': r[3], 'ext': r[4], 'size': int(r[5] or 0), 'mtime': float(r[6] or 0), 'vcodec': r[7] or '', 'cv': int(r[8] or 0)} for r in R[:lim]]
        return {'ok': True, 'rows': rows, 'more': len(R) > lim, 'n': len(rows), 'sum': sum(x['size'] for x in rows)}

    def conv_plan(self, exts=None, smin=0, smax=0, folders=None, sort='size_desc', kind='nonmp4', n=0, target_gb=0):
        """V0.6.11 📏 數量／目標：範圍內最大最小檔、前 n 部的大小區間和預估省；給目標（GB）就算出要轉幾部.
        預估省：有📈同類經驗用同類的比例，沒有用全部平均（跟清單上的「預估省」一樣）."""
        w, a = self.conv_where(exts, smin, smax, folders, (0, 4, 5), kind)
        rows = self.db.q(f'SELECT id,size,ext,vcodec,w,h,fps,vbr,dur,field,acodecs FROM files WHERE {w} ORDER BY {self.CONV_SORT.get(sort, "size DESC")}', a)
        RM = self.learn_ratio_map(); gr = self.conv_ratio(); g_ = gr[0] if gr[1] else 0.5
        sz = []; sv = []
        for r in rows:
            try: c_ = self.tq_class(dict(r)) if RM else ''
            except Exception: c_ = ''
            x = RM.get(c_); er = min(1.0, x[0] if x else g_); b = int(r['size'] or 0)
            sz.append(b); sv.append(int(b * (1 - er)))
        N = len(sz); tot_b = sum(sz); tot_s = sum(sv)
        out = {'ok': True, 'n_all': N, 'bytes_all': tot_b, 'save_all': tot_s, 'min_all': min(sz) if sz else 0, 'max_all': max(sz) if sz else 0, 'ratio': g_}
        tgt = int(float(target_gb or 0) * 1e9); auto = False
        if tgt > 0:                                                              # 照目標算要幾部（照目前的排序一部一部加，加到夠為止）
            acc = 0; k = 0
            for k, v in enumerate(sv, 1):
                acc += v
                if acc >= tgt: break
            n = k if N else 0; auto = True; out['reach'] = acc >= tgt
        n = max(0, min(N, int(n or 0))) or N
        S = sz[:n]
        out.update(n=n, auto=auto, sel_bytes=sum(S), sel_save=sum(sv[:n]), sel_min=min(S) if S else 0, sel_max=max(S) if S else 0, target_gb=float(target_gb or 0))
        return out

    def conv_reorder(self, sort='size_desc'):
        """排隊中的重新排順序（正在轉的不動）."""
        ids = [int(r[0]) for r in self.db.q(f'SELECT id FROM files WHERE cv_state=1 ORDER BY {self.CONV_SORT.get(sort, "size DESC")}')]
        self.db.xm('UPDATE files SET cv_q=? WHERE id=?', [(k + 1, i) for k, i in enumerate(ids)]); self.log.w(f'轉檔：排隊 {len(ids)} 部重新排序（{sort}）'); return len(ids)

    def conv_eta(self):
        """V0.1.75 排隊轉檔全部還要多久（保守估、多抓）：照最近 3 小時實際轉完的「每小時處理幾小時的影片」（含找設定、抽查的時間），
        打 7 折再加 10%；還沒有紀錄就用現在合計倍速打 6 折、每部再加 1 分鐘."""
        now = time.time(); left_s = 0.0; n = 0
        if self.cv_paused and not self.cv_active:                               # V0.6.13 暫停中：不要算出「還要 2 萬天」這種數字
            n_ = int((self.db.one('SELECT COUNT(*) FROM files WHERE cv_state IN (1,2) AND missing=0') or [0])[0] or 0)
            return {'n': n_, 'eta': 0, 'left_s': 0, 'basis': '⏸ 轉檔暫停中（你按的）：排隊的都在等，按「▶ 轉檔繼續」才會開始轉', 'paused': True}
        for r in self.db.q('SELECT id,dur FROM files WHERE cv_state IN (1,2) AND missing=0'):
            J = self.cv_active.get(int(r['id'])); d = float(r['dur'] or 0)
            left_s += d * (1 - (float(J.get('pct') or 0) / 100 if J else 0)); n += 1
        R = self.db.q('SELECT dur, cv_t, cv_gpu FROM files WHERE cv_state IN (3,6) AND cv_t>? ORDER BY cv_t', (now - 3 * 3600,))
        AJ = list(self.cv_active.values()); G = any(int(x['cv_gpu'] or 0) for x in R) or any(J.get('fullgpu') for J in AJ)
        if G: R = [x for x in R if int(x['cv_gpu'] or 0)]; AJ = [J for J in AJ if J.get('fullgpu')]      # V0.1.99 有「顯示卡全程」的紀錄就只看它（舊的 CPU 轉格式那種慢很多，不算）
        cnt = len(R); t0 = float(R[0]['cv_t'] or 0) if R else 0.0
        sd = sum(float(x['dur'] or 0) for x in R[1:])                           # 第一部是在時間窗之前就開始轉的：不算它的長度（不然剛轉完一部 2 小時的會估成超快）
        cnt -= 1
        rate = 0.0; basis = ''
        if cnt >= 1 and t0 and sd > 0:
            win = max(300.0, now - t0); rate = sd / win * 0.7; basis = f'照最近 3 小時{"用顯示卡全程" if G else ""}轉完 {cnt} 部的實際速度（含找設定、抽查，平均 {sd / win:.2f} 倍速）打 7 折、再多抓 10%'
        elif cnt == 0 and R and float(R[0]['dur'] or 0) > 0:                   # 只轉完一部：不知道它什麼時候開始的 → 當它最快是 1 倍速，再打 7 折（保守）
            d0 = float(R[0]['dur']); win = max(600.0, now - t0 + d0); rate = d0 / win * 0.7; basis = '只轉完 1 部，先保守估（當它 1 倍速、打 7 折、每部多抓 1 分鐘），多轉幾部會更準'
        spd = 0.0
        for J in AJ:
            try:
                if time.time() - float(J.get('t0') or time.time()) > 120: spd += float(str(J.get('speed') or '0').rstrip('x') or 0)
            except Exception: pass
        if spd * 0.6 > rate:                                                     # V0.1.96 現在同時在轉的合計速度比較快（例如剛調多幾部）：用現在的（打 6 折，還是保守）
            rate = spd * 0.6; basis = f'照現在 {len(AJ)} 部{"顯示卡全程" if G else ""}合計 {spd:.1f} 倍速打 6 折、每部多抓 1 分鐘'
            if G and len(AJ) < len(self.cv_active): rate *= max(1.0, min(float(self.cfg.get('cv_n') or 1), len(self.cv_active)) / max(1, len(AJ)))   # 舊方法的轉完後也會換成新方法
        if rate <= 0 or not n: return {'n': n, 'left_s': left_s, 'eta': None, 'basis': '還沒有速度紀錄，轉一陣子之後就會估'}
        eta = left_s / rate * 1.1 + (n * 60 if not basis.startswith('照最近') else 0)
        return {'n': n, 'left_s': left_s, 'eta': eta, 'basis': basis, 'done_at': now + eta}

    def conv_queue(self, limit=3000):
        rows = [dict(r) for r in self.db.q("SELECT id,name,folder,ext,size,dur,vcodec,w,h,cv_state,cv_err,cv_redo,cv_osz FROM files WHERE cv_state IN (1,2) AND missing=0 ORDER BY cv_state DESC, cv_q LIMIT ?", (int(limit),))]
        for r in rows:
            J = self.cv_active.get(int(r['id']))
            if J: r.update(pct=J.get('pct') or 0, speed=J.get('speed') or '', enc=J.get('enc') or '', left=J.get('left'))
        return rows

    def conv_stats(self, folder):
        """V0.2.11 📊 轉檔統計（只算指定資料夾，含子資料夾；別的硬碟、別的資料夾不算）：
        每一筆轉檔（轉檔前、轉檔後）、第一筆／最後一筆的時間、轉過的合計 before／after、整個資料夾 before（第一筆轉之前）／after（現在）、累積曲線."""
        f = str(folder or '').rstrip('\\/')
        if not f: return {'ok': False, 'message': '先選一個資料夾'}
        w = '(folder=? OR substr(folder,1,?)=? OR substr(folder,1,?)=?)'; a = [f, len(f) + 1, f + '\\', len(f) + 1, f + '/']
        R = [dict(r) for r in self.db.q(f"SELECT id,name,folder,size,cv_osz,cv_nsz,cv_t,cv_ssim,cv_how,missing FROM files WHERE cv_state=3 AND cv_osz>0 AND {w} ORDER BY cv_t", a)]
        R = [r for r in R if not r['missing']] + [r for r in R if r['missing']]
        conv = [r for r in R if not r['missing']]
        other = self.db.one(f"SELECT COUNT(*), SUM(size) FROM files WHERE missing=0 AND cv_state!=3 AND {w}", a) or (0, 0)
        cb = sum(int(r['cv_osz'] or 0) for r in conv); ca = sum(int(r['size'] or r['cv_nsz'] or 0) for r in conv); ob = int(other[1] or 0)
        T = sorted(conv, key=lambda r: float(r['cv_t'] or 0)); cum = []; x = y = 0
        for r in T: x += int(r['cv_osz'] or 0); y += int(r['size'] or r['cv_nsz'] or 0); cum.append((float(r['cv_t'] or 0), x, y))
        return {'ok': True, 'folder': f, 'rows': [{k: r.get(k) for k in ('id', 'name', 'folder', 'size', 'cv_osz', 'cv_nsz', 'cv_t', 'cv_ssim', 'cv_how')} for r in sorted(conv, key=lambda r: -float(r['cv_t'] or 0))],
                'n': len(conv), 'first_t': float(T[0]['cv_t'] or 0) if T else 0, 'last_t': float(T[-1]['cv_t'] or 0) if T else 0,
                'conv_before': cb, 'conv_after': ca, 'other_n': int(other[0] or 0), 'other_bytes': ob,
                'folder_before': cb + ob, 'folder_after': ca + ob, 'cum': cum[-2000:]}

    def conv_done_list(self, q='', sort='t_desc', limit=3000):
        """轉檔完成：轉檔前後大小、省多少、原檔現在在哪（DELETE 裡／已刪／還在原位）."""
        o = {'t_desc': 'cv_t DESC', 'save_desc': '(cv_osz-cv_nsz) DESC', 'size_desc': 'cv_osz DESC', 'name': 'name COLLATE NOCASE'}.get(sort, 'cv_t DESC')
        w = 'cv_state=3'; a = []
        if q: w += ' AND (name LIKE ? OR cv_src LIKE ?)'; a += [f'%{q}%', f'%{q}%']
        rows = [dict(r) for r in self.db.q(f'SELECT id,name,path,folder,size,dur,cv_src,cv_del,cv_osz,cv_nsz,cv_ratio,cv_ssim,cv_t,missing,viewed,cv_err,cv_cq,cv_how FROM files WHERE {w} ORDER BY {o} LIMIT ?', (*a, int(limit)))]
        up = {}
        def drive_up(p):                                                        # V0.1.90 硬碟離線時檔案「找不到」≠ 被刪了
            k = os.path.splitdrive(str(p or ''))[0] or Path(str(p or '/')).anchor
            if k not in up: up[k] = os.path.exists(k + os.sep) if k else True
            return up[k]
        for r in rows:
            r['offline'] = not drive_up(r['path']) or (bool(r['cv_del']) and not drive_up(r['cv_del']))
            r['osz'] = int(r['cv_osz'] or 0) or (int(r['size'] / r['cv_ratio']) if r.get('cv_ratio') else 0); r['nsz'] = int(r['cv_nsz'] or r['size'] or 0)
            r['del_exists'] = bool(r['cv_del']) and os.path.exists(r['cv_del']); r['src_exists'] = bool(r['cv_src']) and os.path.normcase(r['cv_src']) != os.path.normcase(r['path']) and os.path.exists(r['cv_src'])
            r['out_exists'] = os.path.exists(r['path']); r['big'] = bool(r['osz']) and r['nsz'] >= r['osz'] * 0.98
            r['orig'] = r['cv_del'] if r['del_exists'] else (r['cv_src'] if r['src_exists'] else '')       # 比較用：原檔現在在哪
        sm = self.db.one("SELECT COUNT(*), SUM(cv_osz), SUM(cv_nsz) FROM files WHERE cv_state=3 AND cv_osz>0")
        def win_(t0):                                                           # V0.6.14 今天／這次開程式後 省了多少
            x = self.db.one("SELECT COUNT(*), SUM(cv_osz), SUM(cv_nsz) FROM files WHERE cv_state=3 AND cv_osz>0 AND cv_t>=?", (float(t0),))
            return {'n': int(x[0] or 0), 'osz': int(x[1] or 0), 'nsz': int(x[2] or 0), 'save': max(0, int(x[1] or 0) - int(x[2] or 0)), 't0': float(t0)}
        lt = time.localtime(); today0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
        if not getattr(sys, '_vs_boot_t', None): sys._vs_boot_t = time.time()  # 程式這次打開的時間（熱更新不重算）
        pend = [r for r in rows if r['del_exists'] and not r['big']]; big = [r for r in rows if r['big'] and r['orig']]
        return {'rows': rows, 'n': int(sm[0] or 0), 'osz': int(sm[1] or 0), 'nsz': int(sm[2] or 0), 'today': win_(today0), 'session': win_(sys._vs_boot_t), 'pending': len(pend), 'pending_bytes': sum(r['osz'] for r in pend),
                'big': len(big), 'big_bytes': sum(r['nsz'] - r['osz'] for r in big),
                'offline_n': sum(1 for r in rows if r['offline']), 'offline_drives': sorted(k for k, v in up.items() if not v),
                'pending_by': {k: [sum(1 for r in pend if os.path.splitdrive(str(r['cv_del']))[0].upper() == k), sum(r['osz'] for r in pend if os.path.splitdrive(str(r['cv_del']))[0].upper() == k)]
                               for k in sorted({os.path.splitdrive(str(r['cv_del']))[0].upper() for r in pend})}}

    def conv_purge(self, ids=None):
        with self._cvop_lock: return self._conv_purge(ids)

    def _conv_purge(self, ids=None):
        """刪除已轉檔完成的原檔（DELETE 資料夾裡的）：抽檢沒問題才按。真的刪掉，不能復原."""
        w = 'cv_state=3 AND length(cv_del)>0 AND NOT (cv_osz>0 AND cv_nsz>=cv_osz*0.98)' + (f" AND id IN ({','.join(str(int(i)) for i in ids) or '-1'})" if ids is not None else '')   # V0.1.57 轉大的不刪原檔（要還原）
        n = 0; b = 0; bad = []
        for r in self.db.q(f'SELECT id,cv_del,cv_src,path FROM files WHERE {w}'):
            pth = r['cv_del']
            try:
                if os.path.exists(pth):
                    sz = os.path.getsize(pth); os.remove(pth); n += 1; b += sz
                    self.oplog('delete', src=pth, fid=r['id'], size=sz, detail=f'刪除已轉檔完成的原檔（轉好的：{r["path"]}）')
                self.db.x("UPDATE files SET cv_del='' WHERE id=?", (int(r['id']),))
            except Exception as ex: bad.append(f'{Path(pth).name}：{ex}')
        self.log.w(f'轉檔完成：刪除原檔 {n} 個，空出 {fmt_b(b)}' + (f'；失敗 {len(bad)} 個：{bad[:5]}' if bad else ''))
        return {'ok': not bad, 'n': n, 'bytes': b, 'bad': bad, 'message': f'刪掉 {n} 個原檔，空出 {fmt_b(b)}' + (f'（{len(bad)} 個沒刪成，LOG 有原因）' if bad else '')}

    def conv_restore(self, ids):
        with self._cvop_lock: return self._conv_restore(ids)

    def _conv_restore(self, ids):
        """把 DELETE 裡的原檔搬回原本的位置（轉好的 MP4 留著）."""
        n = 0
        for r in self.db.q(f"SELECT id,cv_del,cv_src FROM files WHERE cv_state=3 AND length(cv_del)>0 AND id IN ({','.join(str(int(i)) for i in ids) or '-1'})"):
            try:
                if os.path.exists(r['cv_del']):
                    dst = self.copy_file(r['cv_del'], r['cv_src'], None, move=True); n += 1
                    self.oplog('undo', src=r['cv_del'], dst=str(dst), fid=r['id'], detail='原檔從 DELETE 搬回原位')
                self.db.x("UPDATE files SET cv_del='' WHERE id=?", (int(r['id']),))
            except Exception: self.log.err('轉檔：原檔搬回')
        self.log.w(f'轉檔完成：{n} 個原檔從 DELETE 搬回原位'); return {'ok': True, 'n': n, 'message': f'{n} 個原檔搬回原本的位置（下次掃描會出現在清單）'}

    def conv_stage(self, ids=None):
        with self._cvop_lock: return self._conv_stage(ids)

    def _conv_stage(self, ids=None):
        """V0.1.57 原檔還留在原位的（舊版畫質偏低時留下的）→ 搬到該硬碟最外層的 DELETE（保留 MP4），同一個資料夾不留兩份."""
        w = "cv_state=3 AND length(cv_src)>0 AND length(cv_del)=0" + (f" AND id IN ({','.join(str(int(i)) for i in ids) or '-1'})" if ids is not None else '')
        n = 0; b = 0; bad = []
        for r in [dict(x) for x in self.db.q(f'SELECT id,path,cv_src FROM files WHERE {w}')]:
            src = str(r['cv_src']); fid = int(r['id'])
            if os.path.normcase(src) == os.path.normcase(str(r['path'])) or not os.path.exists(src): continue
            try:
                sz = os.path.getsize(src); dst = self.copy_file(src, self.del_path(src), None, move=True)
                dup = self.db.one('SELECT id FROM files WHERE path=? AND id!=?', (src, fid))
                if dup is not None: self.db.x('DELETE FROM files WHERE id=?', (int(dup[0]),))
                self.db.x('UPDATE files SET cv_del=? WHERE id=?', (str(dst), fid)); n += 1; b += sz
                self.oplog('move', src=src, dst=str(dst), fid=fid, size=sz, detail=f'轉檔完成：原檔搬到 DELETE（保留轉好的 {r["path"]}）')
            except Exception as ex: bad.append(f'{Path(src).name}：{ex}')
        msg = f'{n} 個原檔搬到 DELETE（{fmt_b(b)}），資料夾裡只留 MP4' + (f'；{len(bad)} 個沒搬成：{bad[0]}' if bad else '')
        self.log.w('轉檔完成：' + msg + (f'　{bad[:10]}' if bad else '')); return {'ok': not bad, 'n': n, 'bytes': b, 'message': msg}

    def _cv_gpu_backfill(self):
        # V0.1.99 0.1.98 還沒有 cv_gpu 欄位：從 LOG 找出已經用「顯示卡全程」轉好的，補上記號（預估時間只看這些）
        try:
            p = self.root / 'LOG' / 'app_log.txt'; sz = p.stat().st_size
            with open(p, 'rb') as fh:
                fh.seek(max(0, sz - 20_000_000)); t = fh.read().decode('utf-8', 'replace')
            ok_ = {}
            for ln in t.splitlines():
                m = re.search(r'轉檔開始：(.+?)（[\d.,]+ [KMGT]?B・', ln)
                if m: ok_[m.group(1)] = '方法：顯示卡全程' in ln; continue
                m = re.search(r'轉檔用 顯示卡全程 NVENC.*? 失敗：(.+?)：', ln)
                if m:
                    for k in list(ok_):
                        if m.group(1).startswith(k): ok_[k] = False
            S_ = [k for k, v in ok_.items() if v]
            n = 0
            for i in range(0, len(S_), 400):
                ch = S_[i:i + 400]; n += self.db.x(f"UPDATE files SET cv_gpu=1 WHERE cv_state IN (3,6) AND cv_src IN ({','.join('?' * len(ch))})", ch) or 0
            self.cfg.set('cv_gpu_v99', True)
            if n: self.log.w(f'轉檔預估：從 LOG 找到 {n} 部已經用「顯示卡全程」轉好的，之後預估只看這些')
        except FileNotFoundError: self.cfg.set('cv_gpu_v99', True)
        except Exception: self.log.err('補顯示卡全程記號')

    def log_grep(self, keys, n=300):
        """app_log.txt 最後面幾 MB 裡，有這些字的行（給畫面直接看 LOG）."""
        try:
            p = self.root / 'LOG' / 'app_log.txt'; sz = p.stat().st_size
            with open(p, 'rb') as fh:
                fh.seek(max(0, sz - 3_000_000)); t = fh.read().decode('utf-8', 'replace')
            return [ln for ln in t.splitlines() if any(k in ln for k in keys)][-n:]
        except Exception: return []

    def brt_history(self):
        try: return json.loads((self.data / 'brtest_history.json').read_text(encoding='utf-8'))
        except Exception: return []

    def brt_save(self, st):
        """碼率測試結果存起來（熱更新、重開都看得到；留最近 30 次）."""
        try:
            keep = {k: v for k, v in st.items() if k not in ('jobs',) and isinstance(v, (str, int, float, bool, type(None)))}
            keep['jobs'] = [{k: v for k, v in j.items() if k not in ('plans', 'proc') and isinstance(v, (str, int, float, bool, type(None)))} for j in st.get('jobs') or []]
            H = [h for h in self.brt_history() if h.get('t0') != keep.get('t0')] + [keep]
            (self.data / 'brtest_history.json').write_text(json.dumps(H[-30:], ensure_ascii=False), encoding='utf-8')
        except Exception: self.log.err('碼率測試存紀錄')

    def media_detail(self, path):
        """V0.1.61 影片的詳細格式（給碼率測試看）：[(分類, [(項目, 內容), …]), …]."""
        rc, o, e = run([self.ffprobe, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)], timeout=60)
        j = json.loads(o or '{}'); F = j.get('format') or {}; SS = j.get('streams') or []
        if not F: raise RuntimeError('讀不到：' + (e or '')[-200:])
        fl = lambda x, d=0.0: float(x) if x not in (None, '', 'N/A') else d
        def rate(x):
            try: a, b = str(x).split('/'); return float(a) / float(b) if float(b) else 0.0
            except Exception: return fl(x)
        T = {k.lower(): v for k, v in (F.get('tags') or {}).items()}; dur = fl(F.get('duration')); sz = int(fl(F.get('size')))
        dev = ' '.join(x for x in (T.get('com.android.manufacturer') or T.get('com.apple.quicktime.make') or T.get('make') or '', T.get('com.android.model') or T.get('com.apple.quicktime.model') or T.get('model') or '') if x)
        G = [('容器', f"{F.get('format_long_name') or F.get('format_name')}（{F.get('format_name')}）"), ('大小', f'{fmt_b(sz)}（{sz:,} bytes）'), ('長度', f'{fmt_t(dur)}（{dur:.3f} 秒）'),
             ('整體位元率', f"{fl(F.get('bit_rate')) / 1e6:.2f} Mbps"), ('串流', f"{len(SS)} 個：" + '、'.join(str(x.get('codec_type')) for x in SS))]
        if T.get('creation_time'): G.append(('拍攝／建立時間', T['creation_time']))
        if dev: G.append(('裝置', dev))
        if T.get('encoder'): G.append(('編碼程式', T['encoder']))
        if T.get('major_brand'): G.append(('品牌', f"{T.get('major_brand')}（相容 {T.get('compatible_brands', '')}）"))
        out = [('📄 檔案', G)]
        for i, v in enumerate([x for x in SS if x.get('codec_type') == 'video' and not (x.get('disposition') or {}).get('attached_pic')]):
            w, h = int(v.get('width') or 0), int(v.get('height') or 0); rot = 0
            for sd in v.get('side_data_list') or []:
                if 'rotation' in sd: rot = int(fl(sd['rotation']))
            rot = rot or int(fl((v.get('tags') or {}).get('rotate')))
            dw, dh = (h, w) if abs(rot) % 180 == 90 else (w, h)
            af, rf = rate(v.get('avg_frame_rate')), rate(v.get('r_frame_rate')); vb = fl(v.get('bit_rate')) or self.src_vbr({'vbr': 0, 'size': sz, 'dur': dur, 'acodecs': ','.join(x.get('codec_name') or '' for x in SS if x.get('codec_type') == 'audio')})
            pix = str(v.get('pix_fmt') or ''); bits = v.get('bits_per_raw_sample') or ('10' if '10' in pix else ('12' if '12' in pix else '8'))
            trc = str(v.get('color_transfer') or ''); hdr = 'HDR10／PQ' if trc == 'smpte2084' else ('HLG' if trc == 'arib-std-b67' else 'SDR')
            if any('dovi' in str(sd.get('side_data_type', '')).lower() or 'dolby' in str(sd.get('side_data_type', '')).lower() for sd in v.get('side_data_list') or []): hdr += '＋杜比視界'
            rng = {'pc': '全範圍 0-255（full）', 'tv': '一般範圍 16-235（limited）'}.get(str(v.get('color_range') or ''), str(v.get('color_range') or '沒標'))
            V = [('編碼', f"{v.get('codec_long_name') or v.get('codec_name')}（{v.get('codec_name')}，{v.get('codec_tag_string') or ''}）"),
                 ('規格', f"profile {v.get('profile') or '?'}，level " + (lambda L, c: '?' if L in (None, -99, '') else (f'{int(L) / 30:g}' if c == 'hevc' else (f'{int(L) / 10:g}' if c == 'h264' else str(L))))(v.get('level'), v.get('codec_name'))),
                 ('解析度', f'{dw}×{dh}' + (f'（實際存 {w}×{h}，旋轉 {rot}°）' if rot else '') + (f"，像素比 {v.get('sample_aspect_ratio')}" + ('' if rot else f"、畫面比 {v.get('display_aspect_ratio')}") if v.get('display_aspect_ratio') else '')),
                 ('影格率', f'平均 {af:.3f} fps' + (f'，標稱 {rf:.3f} fps → 可變影格率（VFR，手機常見）' if rf and af and abs(rf - af) > 0.05 else '，固定影格率') + (f"，共 {int(v['nb_frames']):,} 格" if str(v.get('nb_frames') or '').isdigit() else '')),
                 ('位元率', f'{vb / 1e6:.2f} Mbps' + (f'（每像素 {vb / (w * h * af):.3f} bit）' if w and h and af else '') + ('' if v.get('bit_rate') else '（檔案沒寫，用大小估的）')),
                 ('色彩', f'{pix}，{bits}-bit，{rng}'), ('色彩空間', f"{v.get('color_space') or '沒標'}／原色 {v.get('color_primaries') or '沒標'}／轉換 {trc or '沒標'}（{hdr}）"),
                 ('掃描', {'progressive': '逐行', 'tt': '交錯（上場先）', 'bb': '交錯（下場先）', 'tb': '交錯', 'bt': '交錯'}.get(str(v.get('field_order') or ''), str(v.get('field_order') or '沒標'))),
                 ('B 幀／參考幀', f"has_b_frames {v.get('has_b_frames', '?')}，refs {v.get('refs', '?')}")]
            if fl(v.get('start_time')): V.append(('影像起點', f"{fl(v.get('start_time')):.3f} 秒（和聲音沒有同時開始）"))
            out.append((f'🎬 影像 {i + 1}', V))
        for i, a in enumerate([x for x in SS if x.get('codec_type') == 'audio']):
            out.append((f'🔊 聲音 {i + 1}', [('編碼', f"{a.get('codec_long_name') or a.get('codec_name')}（{a.get('codec_name')}" + (f"，{a.get('profile')}" if a.get('profile') else '') + '）'),
                                            ('聲道', f"{a.get('channels', '?')} 聲道（{a.get('channel_layout') or '?'}）"), ('取樣', f"{int(fl(a.get('sample_rate'))):,} Hz" + (f"，{a.get('sample_fmt')}" if a.get('sample_fmt') else '')),
                                            ('位元率', f"{fl(a.get('bit_rate')) / 1000:.0f} kbps" if a.get('bit_rate') else '沒寫'), ('語言', (a.get('tags') or {}).get('language') or '沒標')]))
        oth = [x for x in SS if x.get('codec_type') not in ('video', 'audio')]
        if oth: out.append(('📎 其他', [(str(x.get('codec_type')), f"{x.get('codec_name') or ''} {(x.get('tags') or {}).get('handler_name', '')}") for x in oth]))
        return out

    # ---------- 🧪 碼率測試（V0.1.60，測試用，之後可能刪掉）
    BRT_KINDS = {'br': 'H.265 顯示卡・指定碼率', 'cq': 'H.265 顯示卡・固定畫質 CQ', 'hq': 'H.265 顯示卡最高品質 p7＋兩階段・CQ',
                 'av1nv': 'AV1 顯示卡（RTX 40 系列才有）・CQ'}                       # 使用者要求：只用顯示卡

    def ff_encoders(self):
        if getattr(self, '_ffenc', None) is None:
            rc, o, _e = run([self.gpu_st.get('ff') or self.ff, '-hide_banner', '-encoders'], timeout=20)
            self._ffenc = set(re.findall(r'^\s*V\S*\s+(\S+)', o or '', re.M))
        return self._ffenc

    def brt_guess(self, kind, val, vc):
        """還沒有實際轉過的時候，猜影像位元率是原檔的幾倍（H.264 原檔；其他原檔再乘一個係數）."""
        val = float(val); src_k = {'h264': 1.0, 'hevc': 1.6, 'mpeg2video': 0.6, 'mpeg4': 0.75, 'wmv3': 0.75, 'vc1': 0.8}.get(str(vc or '').lower(), 0.85)
        if kind == 'br': return val / 100
        if kind == 'cq': r = 0.55 * 0.88 ** (val - 23)
        elif kind in ('x265', 'hq'): r = 0.50 * 0.88 ** (val - 23)
        elif kind == 'av1nv': r = 0.45 * 0.90 ** (val - 30)
        else: r = 0.40 * 0.92 ** (val - 30)
        return min(1.5, r * src_k)

    def brt_key(self, kind, val, vc):
        return f'{kind}|{float(val):g}' + ('' if kind == 'br' else f'|{str(vc or "").lower()}')

    def brt_calib(self, kind, val, vc):
        """之前轉出來「實際 ÷ 預估」：同一種設定優先，不夠就用同一種方式的，越轉越準."""
        H = self.cfg.get('brt_k') or {}
        L = list(H.get(self.brt_key(kind, val, vc)) or [])
        if len(L) < 2:
            pre = kind + '|'; L2 = [x for k_, v_ in H.items() if k_.startswith(pre) for x in v_]
            if len(L2) > len(L): L = L2
        if not L: return 1.0, 0
        L = sorted(L[-15:]); return float(L[len(L) // 2]), len(L)

    def brt_estimate(self, info, kind, val):
        """預估輸出大小（bytes）：影像（原檔影像位元率 × 倍數）＋聲音，再乘上校正值."""
        dur = float(info.get('dur') or 0); vb = self.src_vbr(info); sz = float(info.get('size') or 0)
        if dur <= 0 or not vb: return 0, 1.0, 0
        tot = sz * 8 / dur if sz else vb; A = [a for a in str(info.get('acodecs') or '').split(',') if a]
        acopy = bool(A) and all(a in ('aac', 'mp3', 'ac3', 'eac3') for a in A); ab = max(0.0, tot - vb) if acopy else (192000.0 * min(1, len(A)))
        k, n = self.brt_calib(kind, val, info.get('vcodec'))
        raw = (vb * self.brt_guess(kind, val, info.get('vcodec')) + ab) * dur / 8 + 200000
        return int(raw), k, n

    def _brt_learn(self, kind, val, vc, raw, actual):
        if not raw or not actual: return
        H = dict(self.cfg.get('brt_k') or {}); key = self.brt_key(kind, val, vc)
        H[key] = (list(H.get(key) or []) + [round(actual / raw, 4)])[-15:]; self.cfg.set('brt_k', H)

    def br_test(self, src, out_dir, variants=None, st=None, ssim=True):
        """一個檔「同時」轉成好幾種設定的 MP4（顯示卡的同時轉，CPU 的一次一個），列出預估大小、實際大小、是原檔的幾 %、畫質分數；
        每轉完一個就用實際大小校正之後的預估。variants：[('br', 80), ('cq', 28), ('x265', 24), ('av1', 32), ('av1nv', 32)]."""
        st = st if st is not None else {}; src = Path(src)
        variants = list(variants or [('br', x) for x in (100, 80, 60, 40, 20)])
        p = probe(self.ffprobe, src)
        if not p.get('ok'): raise RuntimeError('讀不到這個檔：' + str(p.get('err', ''))[-200:])
        info = dict(p); info['size'] = src.stat().st_size; dur = float(p.get('dur') or 0); vb = self.src_vbr(info); vc = info.get('vcodec')
        if not vb or dur <= 0: raise RuntimeError('讀不到原檔的位元率或長度')
        if not self.gpu_st.get('ok'): raise RuntimeError('顯示卡現在不能壓縮（碼率測試只用顯示卡）：到「轉檔」→ 轉檔中 →「🔄 重新檢查顯示卡」看原因')
        out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        g = self.gpu_st; gpu = bool(g.get('ok')); v10 = '10' in str(info.get('pix') or ''); enc = self.ff_encoders(); gff = g.get('ff') or self.ff
        A = [a for a in str(info.get('acodecs') or '').split(',') if a]; acopy = bool(A) and all(a in ('aac', 'mp3', 'ac3', 'eac3') for a in A)
        aargs = ['-c:a', 'copy'] if acopy else ['-c:a', 'aac', '-b:a', '192k']
        vf = self.conv_vf(info, {'res': 0, 'scale': 1.0}); vfa = ['-vf', ','.join(vf)] if vf else []
        pix = (['-pix_fmt', 'p010le', '-profile:v', 'main10'] if v10 else ['-pix_fmt', 'yuv420p', '-profile:v', 'main'])
        aq = ['-tune', 'hq', '-spatial_aq', '1', '-temporal_aq', '1', '-rc-lookahead', '32'] if g.get('aq') else []
        J = []; stem = safe_name(src.stem)[:70]
        for kind, val in variants:
            val = float(val); plans = []
            if kind == 'br':
                br = max(100000, int(vb * val / 100)); tag = f'H265_{val:g}%_{br // 1000}k'
                base = ['-c:v', 'hevc_nvenc', '-preset', g.get('preset') or 'p5', '-rc', 'vbr', '-b:v', str(br), '-maxrate', str(int(br * 1.5)), '-bufsize', str(br * 2)]
                if gpu:
                    if aq: plans.append(('顯示卡 NVENC', 'gpu', gff, ['-hwaccel', 'cuda'], base + aq + pix + ['-tag:v', 'hvc1']))
                    plans.append(('顯示卡 NVENC（基本）', 'gpu', gff, [], base + pix + ['-tag:v', 'hvc1']))
            elif kind == 'cq':
                tag = f'H265_CQ{val:g}'; base = ['-c:v', 'hevc_nvenc', '-preset', g.get('preset') or 'p5', '-rc', 'vbr', '-cq', f'{val:g}', '-b:v', '0']
                if gpu:
                    if aq: plans.append(('顯示卡 NVENC', 'gpu', gff, ['-hwaccel', 'cuda'], base + aq + pix + ['-tag:v', 'hvc1']))
                    plans.append(('顯示卡 NVENC（基本）', 'gpu', gff, [], base + pix + ['-tag:v', 'hvc1']))
            elif kind == 'hq':
                tag = f'H265_p7_CQ{val:g}'; base = ['-c:v', 'hevc_nvenc', '-preset', 'p7', '-tune', 'hq', '-rc', 'vbr', '-cq', f'{val:g}', '-b:v', '0', '-multipass', 'fullres', '-spatial_aq', '1', '-temporal_aq', '1', '-rc-lookahead', '48', '-bf', '4', '-b_ref_mode', 'middle']
                plans.append(('顯示卡 NVENC p7 兩階段', 'gpu', gff, ['-hwaccel', 'cuda'], base + ['-pix_fmt', 'p010le', '-profile:v', 'main10', '-tag:v', 'hvc1']))
                plans.append(('顯示卡 NVENC p7（基本）', 'gpu', gff, [], ['-c:v', 'hevc_nvenc', '-preset', 'p7', '-rc', 'vbr', '-cq', f'{val:g}', '-b:v', '0', '-pix_fmt', 'p010le', '-profile:v', 'main10', '-tag:v', 'hvc1']))
            elif kind == 'av1nv':
                tag = f'AV1_nvenc_CQ{val:g}'
                if 'av1_nvenc' in enc: plans.append(('顯示卡 AV1 NVENC', 'gpu', gff, [], ['-c:v', 'av1_nvenc', '-preset', g.get('preset') or 'p5', '-rc', 'vbr', '-cq', f'{val:g}', '-b:v', '0', '-pix_fmt', 'p010le' if v10 else 'yuv420p']))
            else: continue
            out = unique_path(out_dir / f'{stem}_{tag}.mp4'); raw, k, n = self.brt_estimate(info, kind, val)
            J.append({'kind': kind, 'val': val, 'label': self.BRT_KINDS.get(kind, kind), 'name': tag, 'out': str(out), 'plans': plans, 'state': 'wait' if plans else 'fail',
                      'err': '' if plans else '這台的 FFmpeg 沒有這種編碼器', 'pctdone': 0.0, 'size': 0, 'ssim': 0.0, 'speed': '', 'enc': '', 'sec': 0.0,
                      'raw': raw, 'est': int(raw * k), 'k': k, 'kn': n})
        st.update(src=str(src), out_dir=str(out_dir), src_vbr=vb, src_size=info['size'], dur=dur, vcodec=vc, w=info.get('w'), h=info.get('h'),
                  jobs=J, done=False, cancel=False, t0=time.time(), gpu=gpu, src_tot=info['size'] * 8 / dur if dur else 0); self.brt_st = st
        self.log.w(f'🧪 碼率測試開始：{src}（{vc} {info.get("w")}×{info.get("h")}，{fmt_t(dur)}，影像約 {vb / 1e6:.2f} Mbps，{fmt_b(info["size"])}）→ {out_dir}：' +
                   '、'.join(f'{j["name"]}（預估 {fmt_b(j["est"])}）' for j in J))
        sem = {'gpu': threading.Semaphore(5), 'cpu': threading.Semaphore(1)}           # 顯示卡最多同時 5 個（一般顯示卡的上限），CPU 一次一個

        def one(j):
            tmp = Path(j['out']).with_name(Path(j['out']).stem + '.vspart.mp4')
            for nm, lane, ff, pre, v in j['plans']:
                if st.get('cancel'): j['state'] = 'stop'; return
                with sem[lane]:
                    if st.get('cancel'): j['state'] = 'stop'; return
                    j['state'] = 'run'; j['enc'] = nm; t0 = time.time(); j['t0'] = t0
                    cmd = [ff, '-hide_banner', '-nostdin', '-loglevel', 'error', '-y'] + pre + ['-i', str(src), '-map', '0:v:0', '-map', '0:a?', '-map_metadata', '0', '-sn', '-dn'] + vfa + v + aargs + \
                          ['-movflags', '+faststart', '-max_muxing_queue_size', '4096', '-progress', 'pipe:1', '-nostats', str(tmp)]
                    P = Proc(cmd, 'normal' if lane == 'gpu' else 'below').start(); self.procs.add(P); j['proc'] = P

                    def tick(pp):
                        if dur > 0: j['pctdone'] = min(99.9, round(pp.out_us / 1e6 / dur * 100, 1))
                        j['speed'] = pp.speed; el_ = time.time() - j['t0']
                        j['left'] = (el_ / (j['pctdone'] / 100) - el_) if j.get('pctdone', 0) > 0.5 else None
                    rc = P.wait(stop=lambda: self.stop_all or st.get('cancel'), stall=900, on_tick=tick); self.procs.discard(P); j['proc'] = None
                if rc == -2:
                    j['state'] = 'stop'
                    try: tmp.unlink()
                    except Exception: pass
                    return
                if rc == 0 and tmp.exists():
                    os.replace(str(tmp), j['out']); j['size'] = os.path.getsize(j['out']); j['sec'] = time.time() - t0; j['pctdone'] = 100.0; j['left'] = 0
                    self._brt_learn(j['kind'], j['val'], vc, j['raw'], j['size'])
                    try:
                        q_ = probe(self.ffprobe, Path(j['out'])); od_ = float(q_.get('dur') or dur) or dur
                        j['tot_br'] = j['size'] * 8 / od_; j['v_br'] = float(q_.get('vbr') or 0); j['v_br'] = j['v_br'] if j['v_br'] < j['tot_br'] * 0.99 else max(0.0, j['tot_br'] - (st['src_tot'] - vb))
                    except Exception: pass
                    self.log.w(f'🧪 碼率測試 {j["name"]}（{nm}）：預估 {fmt_b(j["est"])}，實際 {fmt_b(j["size"])}（誤差 {(j["size"] / j["est"] - 1) * 100 if j["est"] else 0:+.0f}%，原檔的 {j["size"] * 100 / info["size"]:.0f}%），{j["sec"]:.0f} 秒 → {j["out"]}')
                    if ssim and not st.get('cancel'):
                        j['state'] = 'ssim'; j['ssim'] = self.ssim_check(src, j['out'], dur)
                    j['state'] = 'done'; return
                j['err'] = P.errtext()[-300:]; self.log.w(f'🧪 碼率測試 {j["name"]} 用 {nm} 失敗：{j["err"]}\n　指令：{cmd_text(cmd)}')
                try: tmp.unlink()
                except Exception: pass
            j['state'] = 'fail'
        T = [threading.Thread(target=one, args=(j,), name='VsBrTest', daemon=True) for j in J if j['plans']]
        for t_ in T: t_.start()
        for t_ in T: t_.join()
        st['done'] = True; st['t1'] = time.time(); self.brt_save(st)
        self.log.w('🧪 碼率測試完成：' + '；'.join(f'{j["name"]} {j["state"]} {fmt_b(j["size"])} SSIM {j["ssim"]:.3f}' for j in J))
        return st

    def conv_bigger(self):
        """轉完反而變大（或差不多大）的：id 清單."""
        return [int(r[0]) for r in self.db.q('SELECT id FROM files WHERE cv_state=3 AND cv_osz>0 AND cv_nsz>=cv_osz*0.98')]

    def conv_below(self, target=None):
        """V0.1.65 畫質分數沒到目標（含沒驗證的；只換外殼的不算）、原檔還在的：id 清單."""
        t_ = float(target or self.cfg.get('cv_target') or 0.985); out = []
        for r in self.db.q("SELECT id,cv_ssim,cv_del,cv_src,path FROM files WHERE cv_state=3"):
            ss = float(r['cv_ssim'] or 0)
            if ss >= t_ or ss >= 0.9999: continue
            here = r['cv_src'] and os.path.normcase(r['cv_src']) != os.path.normcase(r['path']) and os.path.exists(r['cv_src'])
            if (r['cv_del'] and os.path.exists(r['cv_del'])) or here: out.append(int(r['id']))
        return out

    def conv_reverify(self, ids):
        """🔍 V0.1.66 用修正後的方法重新驗證轉好的畫質（之前 .ts 這類跳時間不準，算出來的 ⚠ 很多不是真的變差）。
        原檔要還在（DELETE 或原位）。一部一部在背景做，結果寫回「自動驗證」那一欄。"""
        R = self.rv_st; have = set(R['q'])
        for i in ids:
            if int(i) not in have: R['q'].append(int(i)); R['n'] += 1
        R['stop'] = False; self.cfg.set('rv_pending', list(R['q']))
        if not R['run']:
            R['run'] = True; threading.Thread(target=self._reverify_loop, name='VsReverify', daemon=True).start()
        self.log.w(f'🔍 重新驗證畫質：加入 {len(ids)} 部（排隊共 {len(R["q"])} 部）'); return {'ok': True, 'n': len(ids), 'message': f'排入 {len(ids)} 部重新驗證畫質（後台一部一部做，結果會更新在「自動驗證」那一欄）'}

    def _reverify_loop(self):
        R = self.rv_st
        try:
            while self.alive() and R['q'] and not R['stop']:
                if self.bg_hold('conv'): time.sleep(2); continue                 # 轉檔暫停／讓路的時候也一起等
                fid = R['q'].popleft(); self.cfg.set('rv_pending', list(R['q'])); r = self.db.one('SELECT id,name,path,dur,cv_del,cv_src,cv_ssim FROM files WHERE id=? AND cv_state=3', (fid,))
                if r is None: R['done'] += 1; continue
                orig = r['cv_del'] if r['cv_del'] and os.path.exists(r['cv_del']) else (r['cv_src'] if r['cv_src'] and os.path.normcase(r['cv_src']) != os.path.normcase(r['path']) and os.path.exists(r['cv_src']) else '')
                if not orig or not os.path.exists(r['path']): R['done'] += 1; R['res'].append((fid, None, '原檔或轉好的不見了')); continue
                R['cur'] = r['name']; t0 = time.time()
                v = self.ssim_check(orig, r['path'], float(r['dur'] or 0), n=5)
                if v:
                    self.db.x('UPDATE files SET cv_ssim=? WHERE id=?', (v, fid))
                    self.log.w(f'🔍 重新驗證：{r["name"]}　{float(r["cv_ssim"] or 0):.3f} → {v:.4f}（{time.time() - t0:.0f} 秒）')
                R['res'].append((fid, v, f'{float(r["cv_ssim"] or 0):.3f} → {v:.4f}' if v else '沒算成')); R['done'] += 1; R['up'] = time.time()
        except Exception: self.log.err('重新驗證畫質')
        finally:
            R['run'] = False; R['cur'] = ''
            if not R['q']: self.log.w(f'🔍 重新驗證畫質：做完 {R["done"]} 部')

    def conv_redo(self, ids, force=False, front=False):
        """🔁 用 DELETE 裡的原檔、🎯 新方式重轉：達到目標（0.985）才換掉舊的 MP4；原檔一直留在 DELETE，等你自己刪.
        V0.1.95 force＝一定整部重壓（不因為「樣本看起來不會變小」就只換外殼）；front＝插隊排第一."""
        ids = [int(i) for i in ids]; ok = []
        for r in self.db.q(f"SELECT id,cv_del FROM files WHERE cv_state=3 AND id IN ({','.join(str(i) for i in ids) or '-1'})"):
            if r['cv_del'] and os.path.exists(r['cv_del']): ok.append(int(r['id']))
        if front:
            mn = (self.db.one('SELECT MIN(cv_q) FROM files WHERE cv_state=1')[0] or 0)
            Q = [(mn - len(ok) + k, i) for k, i in enumerate(ok)]
        else:
            mx = (self.db.one('SELECT MAX(cv_q) FROM files')[0] or 0); Q = [(mx + k + 1, i) for k, i in enumerate(ok)]
        self.db.xm(f"UPDATE files SET cv_state=1,cv_redo={2 if force else 1},cv_err='',cv_q=? WHERE id=?", Q)
        self.log.w(f'🔁 重轉排隊：{len(ok)} 部（原檔在 DELETE）；{len(ids) - len(ok)} 部原檔不在 DELETE，不能重轉')
        return {'ok': True, 'n': len(ok), 'message': f'{len(ok)} 部排入重轉（用 DELETE 裡的原檔，達到 {float(self.cfg.get("cv_target") or 0.985):.3f} 才換掉舊的 MP4）' + (f'；{len(ids) - len(ok)} 部原檔不在 DELETE，跳過' if len(ids) > len(ok) else '')}

    def conv_undo(self, ids):
        with self._cvop_lock: return self._conv_undo(ids)

    def _conv_undo(self, ids):
        """V0.1.57 轉壞／轉大了 → 還原：刪掉轉好的 MP4，原檔搬回原位，這筆資料改回原檔（同一個編號：預覽圖、分級、人物照舊），之後可以用新設定重轉.
        原檔已經永久刪掉的不會動。"""
        n = 0; freed = 0; bad = []
        for r in [dict(x) for x in self.db.q(f"SELECT id,path,cv_src,cv_del,cv_osz,cv_nsz FROM files WHERE cv_state=3 AND id IN ({','.join(str(int(i)) for i in ids) or '-1'})")]:
            fid = int(r['id']); out = str(r['path'] or ''); src = str(r['cv_src'] or ''); dl = str(r['cv_del'] or '')
            try:
                if not src: raise RuntimeError('不知道原檔原本在哪')
                inplace = os.path.normcase(src) == os.path.normcase(out)
                here = (not inplace) and os.path.exists(src)
                if not here and not (dl and os.path.exists(dl)): raise RuntimeError('原檔已經刪掉了，沒辦法還原')
                if inplace:
                    side = out + '.vsundo'
                    if os.path.exists(out): os.replace(out, side)
                    try: self.copy_file(dl, src, None, move=True)
                    except Exception:
                        if os.path.exists(side) and not os.path.exists(out): os.replace(side, out)
                        raise
                    if os.path.exists(side): freed += os.path.getsize(side); os.remove(side)
                else:
                    if not here:
                        got = self.copy_file(dl, src, None, move=True)
                        if os.path.normcase(str(got)) != os.path.normcase(src): src = str(got)
                    if out and os.path.exists(out): freed += os.path.getsize(out); os.remove(out)
                dup = self.db.one('SELECT id FROM files WHERE path=? AND id!=?', (src, fid))
                if dup is not None: self.db.x('DELETE FROM files WHERE id=?', (int(dup[0]),))
                sp = Path(src); st = sp.stat()
                sets = {'path': src, 'folder': str(sp.parent), 'name': sp.name, 'ext': sp.suffix.lower(), 'size': int(st.st_size), 'mtime': float(st.st_mtime), 'missing': 0,
                        'cv_state': 0, 'cv_err': '上次轉完沒有變小，已還原原檔（可以用新設定重轉）', 'cv_out': '', 'cv_del': '', 'cv_src': '', 'cv_ratio': 0, 'cv_ssim': 0}
                q = probe(self.ffprobe, sp)
                if q.get('ok'):
                    for k in ('vcodec', 'acodecs', 'vbr', 'pix', 'fps', 'w', 'h'):
                        if q.get(k) not in (None, ''): sets[k] = q.get(k)
                self.db.x('UPDATE files SET ' + ','.join(f'{k}=?' for k in sets) + ' WHERE id=?', (*sets.values(), fid)); n += 1
                self.oplog('undo', src=out, dst=src, fid=fid, size=int(r['cv_nsz'] or 0), detail=f'轉檔還原：刪掉轉好的（{fmt_b(r["cv_nsz"] or 0)}），原檔（{fmt_b(r["cv_osz"] or 0)}）搬回原位')
                self.log.w(f'轉檔還原：id {fid} {out} 刪掉，原檔 {src} 搬回原位')
            except Exception as ex:
                bad.append(f'{Path(out).name}：{ex}'); self.log.w(f'轉檔還原失敗：id {fid} {out}：{ex}')
        msg = f'還原 {n} 部（刪掉轉好的 MP4、原檔搬回原本的資料夾，空出 {fmt_b(freed)}）' + (f'；{len(bad)} 部沒還原：{bad[0]}' if bad else '')
        self.log.w('轉檔還原：' + msg + (f'　{bad[:10]}' if bad else '')); return {'ok': not bad, 'n': n, 'bytes': freed, 'bad': bad, 'message': msg}

    # ---------- 🧪 參考畫質：試轉 10 秒（V0.1.57）
    def _pkey(self, PP):
        return f"{self.cfg.get('cv_enc') or 'auto'}|{PP.get('q')}|{PP.get('res') or 0}|{PP.get('capm')}"

    def trial_calib(self, PP):
        """之前「試轉推估」對上「實際轉完」的比例（中間值）：同一組參數優先，不夠就用全部."""
        H = [x for x in (self.cfg.get('cv_trial_k') or []) if isinstance(x, list) and len(x) == 2 and x[1] > 0]
        key = self._pkey(PP); S = [x[1] for x in H if x[0] == key]
        L = S if len(S) >= 2 else [x[1] for x in H]
        if not L: return 1.0, 0
        L = sorted(L); return float(L[len(L) // 2]), len(L)

    def conv_class_hist(self, ext):
        """已經轉完的同類（原檔副檔名一樣）實際變成幾 %（照大小加權）；V0.1.57 之後轉的優先."""
        t57 = float(self.cfg.get('cv_cap_t') or 0); A = []; B = []
        for r in self.db.q("SELECT cv_src,cv_osz,cv_nsz,cv_t FROM files WHERE cv_state=3 AND cv_osz>0 AND cv_nsz>0"):
            if Path(str(r['cv_src'] or '')).suffix.lower() != str(ext or '').lower(): continue
            (A if (r['cv_t'] or 0) >= t57 else B).append((int(r['cv_osz']), int(r['cv_nsz'])))
        L = A if len(A) >= 3 else A + B
        if not L: return None
        o = sum(x[0] for x in L); nn = sum(x[1] for x in L)
        return {'n': len(L), 'ratio': nn / o if o else 0, 'new': len(A)}

    def conv_trial(self, fid, P=None, at=None, secs=10.0):
        """照這組參數，從片子中間（或 at 秒）試轉 secs 秒：實際轉出來的大小 → 推估整部；和原檔同一段比 SSIM；
        再用「之前試轉 vs 實際轉完」的比例、和已經轉完的同類檔案校正."""
        r = self.file(int(fid))
        if not r: raise RuntimeError('找不到這部')
        src = Path(r['path']); info = dict(r)
        if not src.exists(): raise RuntimeError('檔案不見了')
        if not r.get('probed') == 1 or not info.get('dur'):
            p = probe(self.ffprobe, src)
            if p.get('ok'): info.update(p)
        dur = float(info.get('dur') or 0)
        if dur <= 0: raise RuntimeError('讀不到影片長度')
        secs = max(3.0, min(float(secs or 10), dur)); at = dur * 0.4 if at is None else float(at); at = max(0.0, min(at, dur - secs))
        PP = self.conv_params(info, P); vf = self.conv_vf(info, PP); plans = self.enc_plans(info, PP)
        d = self.data / 'trial'; d.mkdir(parents=True, exist_ok=True)
        old = sorted(d.glob('trial_*.mp4'), key=lambda x: x.stat().st_mtime)
        for x in old[:-6]:
            try: x.unlink()
            except Exception: pass
        out = d / f'trial_{int(fid)}_{int(time.time())}.mp4'
        A = [a for a in str(info.get('acodecs') or '').split(',') if a]; acopy = bool(A) and all(a in ('aac', 'mp3', 'ac3', 'eac3') for a in A)
        aargs = ['-c:a', 'copy'] if acopy else ['-c:a', 'aac', '-b:a', '192k']; err = ''; used = ''; el = 0.0
        for pl in plans:
            cmd = [pl['ff'], '-hide_banner', '-nostdin', '-loglevel', 'error', '-y'] + pl['pre'] + ['-ss', f'{at:.3f}', '-t', f'{secs:.3f}', '-i', str(src), '-map', '0:v:0', '-map', '0:a?', '-sn', '-dn'] + \
                  self._vfa(pl, vf) + pl['v'] + aargs + ['-movflags', '+faststart', str(out)]
            t0 = time.time(); rc, _o, e = run(cmd, timeout=900, prio='normal'); el = time.time() - t0
            if rc == 0 and out.exists() and out.stat().st_size > 0: used = pl['name']; break
            err = e or f'ffmpeg {rc}'; self.log.w(f'試轉用 {pl["name"]} 失敗：{src}：{err[-300:]}')
        if not used: raise RuntimeError('試轉失敗：' + err[-300:])
        q = probe(self.ffprobe, out); od = float(q.get('dur') or 0) if q.get('ok') else 0
        if od <= 0 or od > secs: od = secs                                   # 聲音前後多一點不算
        b = out.stat().st_size; pred = int(b / od * dur); osz = int(info.get('size') or src.stat().st_size)
        ssim = self.ssim_check(src, out, od, src_off=at, n=3, seg=2.0)
        k, kn = self.trial_calib(PP); est = int(pred * k)
        ch = self.conv_class_hist(src.suffix.lower())
        T = [x for x in (self.cfg.get('cv_trials') or []) if isinstance(x, dict) and x.get('fid') != int(fid)][-199:]
        T.append({'fid': int(fid), 'pred': pred, 'key': self._pkey(PP), 't': time.time()}); self.cfg.set('cv_trials', T)
        res = {'ok': True, 'out': str(out), 'src': str(src), 'at': at, 'secs': od, 'bytes': b, 'pred': pred, 'est': est, 'k': k, 'kn': kn, 'osz': osz, 'dur': dur,
               'ratio': est / osz if osz else 0, 'ssim': ssim, 'enc': used, 'elapsed': el, 'speed': od / el if el > 0 else 0, 'full_time': dur * el / od if od else 0,
               'params': PP, 'class': ch, 'w': int(q.get('w') or 0), 'h': int(q.get('h') or 0), 'kbps': int(b * 8 / od / 1000), 'src_kbps': int(PP['src_vbr'] / 1000),
               'name': src.name}
        self.log.w(f'🧪 試轉 {od:.1f} 秒：{src.name}（從 {fmt_t(at)}，{used}，畫質 {PP["q"]}' + (f'，{PP["res"]}p' if PP['res'] else '') + (f'，上限 {PP["cap"] / 1e6:.1f} Mbps' if PP['cap'] else '，不封頂') +
                   f'）→ {fmt_b(b)}，推估整部 {fmt_b(pred)}' + (f'×校正 {k:.2f}（{kn} 筆）＝{fmt_b(est)}' if kn else '') + f'，原檔 {fmt_b(osz)}（{res["ratio"] * 100:.0f}%），SSIM {ssim:.3f}，花 {el:.1f} 秒')
        return res

    def _trial_learn(self, fid, PP, nsz):
        """這部之前試轉過（同一組參數）→ 記下「實際／推估」，之後的推估更準."""
        try:
            T = list(self.cfg.get('cv_trials') or []); key = self._pkey(PP)
            x = next((x for x in reversed(T) if isinstance(x, dict) and x.get('fid') == int(fid) and x.get('key') == key and x.get('pred')), None)
            if not x: return
            K = [y for y in (self.cfg.get('cv_trial_k') or []) if isinstance(y, list)][-49:]; K.append([key, round(nsz / x['pred'], 4)]); self.cfg.set('cv_trial_k', K)
            self.cfg.set('cv_trials', [y for y in T if y is not x]); self.log.w(f'🧪 試轉校正：id {fid} 推估 {fmt_b(x["pred"])}，實際 {fmt_b(nsz)}（{nsz / x["pred"]:.2f}）')
        except Exception: self.log.err('試轉校正')

    def goal_view(self, reset=False):
        """🎯 瘦身目標：開始時全部檔案的總大小 → 一個月內減半（轉檔、刪原檔、剪輯、F 級刪除都算）."""
        q1 = lambda sql, a_=(): (self.db.one(sql, a_) or [0])[0] or 0
        lib = int(q1('SELECT SUM(size) FROM files WHERE missing=0'))
        pend = 0
        for r in self.db.q("SELECT cv_del, cv_osz FROM files WHERE cv_state=3 AND length(cv_del)>0"):
            pend += int(r['cv_osz'] or 0)                                        # 還在 DELETE 裡等你刪的原檔，也還佔空間
        cur = lib + pend; G = dict(self.cfg.get('shrink_goal') or {})
        if reset or not G.get('b0'):
            G = {'t0': time.time(), 'b0': cur, 'ratio': float(G.get('ratio') or 0.5), 'days': int(G.get('days') or 30)}; self.cfg.set('shrink_goal', G)
            self.log.w(f'🎯 瘦身目標開始：現在 {fmt_b(cur)} → 目標 {fmt_b(cur * G["ratio"])}，{G["days"]} 天')
        H = list(self.cfg.get('shrink_hist') or []); day = time.strftime('%Y-%m-%d')
        if not H or H[-1][0] != day: H.append([day, cur]); self.cfg.set('shrink_hist', H[-90:])
        elif abs(H[-1][1] - cur) > 1e8: H[-1][1] = cur; self.cfg.set('shrink_hist', H[-90:])
        b0 = float(G['b0']); target = b0 * float(G.get('ratio') or 0.5); t0 = float(G['t0']); days = int(G.get('days') or 30)
        el_days = max(0.0, (time.time() - t0) / 86400); left_days = max(0.0, days - el_days)
        saved = max(0.0, b0 - cur); need = max(0.0, cur - target); pct = min(100.0, saved * 100 / max(1.0, b0 - target))
        pace = saved / el_days if el_days >= 0.5 else 0.0                       # 開始到現在平均每天省多少
        rec = [h for h in H if h[0] >= time.strftime('%Y-%m-%d', time.localtime(time.time() - 7 * 86400))]
        if len(rec) >= 2: pace = max(pace, (rec[0][1] - rec[-1][1]) / max(1, len(rec) - 1))
        conv_saved = int(q1('SELECT SUM(cv_osz-cv_nsz) FROM files WHERE cv_state=3 AND cv_t>=? AND cv_osz>cv_nsz', (t0,)))
        ratio, nr = self.conv_ratio()
        w_n, a_n = self.conv_where(None, 0, 0, None, (0, 1, 2, 4, 5), 'nonmp4'); w_h, a_h = self.conv_where(None, 0, 0, None, (0, 1, 2, 4, 5), 'h264')
        nb = int(q1(f'SELECT SUM(size) FROM files WHERE {w_n}', a_n)); hb = int(q1(f'SELECT SUM(size) FROM files WHERE {w_h}', a_h))
        pot = (nb + hb) * max(0.0, 1 - (ratio if nr else 0.5))
        cvr = [x for x in list(self.cv_done_log) if time.time() - x[0] <= 86400]
        conv_day = sum(max(0, x[2] - x[3]) for x in cvr) if cvr else 0          # 最近 24 小時轉檔省下的
        tips = []
        if need > 0:
            if pace > 0: tips.append(f'照最近的速度每天省 {fmt_b(pace)}，大約還要 {need / pace:.0f} 天' + ('（來得及 ✔）' if need / pace <= left_days else f'（比目標多 {need / pace - left_days:.0f} 天）'))
            if pot < need: tips.append(f'光靠轉檔最多再省約 {fmt_b(pot)}，還差 {fmt_b(need - pot)}：要靠分級刪除（F）、初剪後刪原檔、排除不要的資料夾')
            else: tips.append(f'還沒轉的非 MP4＋H.264 共 {fmt_b(nb + hb)}，全部轉完約可再省 {fmt_b(pot)}')
            if pend: tips.append(f'DELETE 裡還有 {fmt_b(pend)} 的原檔等你抽檢後刪除（刪了才真的空出來）')
        return {'b0': b0, 'cur': cur, 'lib': lib, 'pend': pend, 'target': target, 'saved': saved, 'need': need, 'pct': pct, 'days': days, 'el_days': el_days, 'left_days': left_days,
                'need_day': (need / left_days) if left_days > 0 else need, 'pace': pace, 'conv_saved': conv_saved, 'conv_day': conv_day, 'nonmp4_b': nb, 'h264_b': hb, 'potential': pot,
                'ratio': ratio, 'eta_days': (need / pace) if pace > 0 and need > 0 else None, 'tips': tips, 't0': t0, 'hist': H[-30:]}

    def bg_overview(self):
        """後台總覽：每一件正在跑的事（在做哪個檔、進度、剩下幾個、處理速度、還要多久）."""
        now = time.time(); I = self.info(); out = []
        def rate(log, win=600):
            L = [x for x in list(log) if now - (x[0] if isinstance(x, tuple) else x) <= win]
            if len(L) < 2: return 0.0
            t0 = L[0][0] if isinstance(L[0], tuple) else L[0]; return len(L) / max(60.0, now - t0)
        s = self.scan_st
        out.append({'k': 'scan', 'icon': '🔄', 'name': '掃描影片庫', 'state': 'run' if s.get('running') else 'idle',
                    'items': [{'name': str(s.get('cur') or ''), 'pct': None, 'sub': f"{s.get('n', 0):,} 個影片 · {s.get('dirs', 0):,} 個資料夾"}] if s.get('running') else [],
                    'left': None, 'speed': '', 'eta': None, 'note': '' if s.get('running') else (f"上次掃到 {s.get('n', 0):,} 個影片" if s.get('t1') else '')})
        pr = rate(self.pr_done_log)
        out.append({'k': 'probe', 'icon': '🔍', 'name': '讀影片資訊（長度、解析度）', 'state': 'run' if self.pr_active else ('wait' if I['probe_left'] else 'idle'), 'items': [],
                    'left': I['probe_left'], 'speed': f'每分鐘 {pr * 60:.0f} 部' if pr else '', 'eta': (I['probe_left'] / pr) if pr and I['probe_left'] else None,
                    'note': f"{I['probe_bad']:,} 部讀不出來" if I['probe_bad'] else ''})
        TH = []
        for k, J in list(self.th_active.items()):
            el = now - J.get('t0', now); TH.append({'id': k, 'name': J.get('name'), 'pct': J.get('pct') or 0, 'sub': f"已經 {int(el)} 秒" + (' · 精準模式' if J.get('precise') else ''), 'lane': J.get('lane')})
        thr = rate([(x[0],) for x in self.th_done_log], 1800)
        out.append({'k': 'thumb', 'icon': '🖼', 'name': f"預覽圖（每 {int(self.cfg.get('th_step') or 2)} 秒一張）", 'state': 'pause' if self.th_paused else ('run' if TH else ('wait' if I['th_left'] else 'idle')),
                    'items': TH, 'left': I['th_left'], 'speed': (f"每秒處理 {I.get('th_rate', 0):.0f} 秒影片" if I.get('th_rate') else '') + (f' · 每小時約 {thr * 3600:.0f} 部' if thr else ''),
                    'eta': I.get('th_eta') if I['th_left'] else None, 'note': (f"失敗 {I['th_fail']:,} 部" if I['th_fail'] else '') + (f' · ⚠ {self.th_low}' if getattr(self, 'th_low', '') else '')})
        F = getattr(self, 'faces', None)
        if F is not None:
            try:
                fs = F.status(); left = max(0, int(fs.get('total') or 0) - int(fs.get('done') or 0))
                out.append({'k': 'faces', 'icon': '👤', 'name': '人臉辨識（人物分類）', 'state': 'run' if fs.get('running') else ('err' if fs.get('state') == 'error' else 'idle'),
                            'items': [{'name': str(fs.get('cur') or fs.get('msg') or ''), 'pct': None, 'sub': str(fs.get('provider') or '')}] if fs.get('running') else [],
                            'left': left if fs.get('running') or fs.get('done') else None, 'speed': str(fs.get('speed') or '') if fs.get('running') else '',
                            'eta': fs.get('eta'), 'note': f"找到 {fs.get('faces', 0):,} 張臉、{fs.get('people', 0):,} 個人" + (' · ' + str(fs.get('err'))[:80] if fs.get('err') else '')})
            except Exception: pass
        CV = []; spd = 0.0
        for k, J in list(self.cv_active.items()):
            CV.append({'id': k, 'name': J.get('name'), 'pct': J.get('pct') or 0, 'sub': f"{J.get('enc', '')} {J.get('speed') or ''}" + (f" · 還要 {fmt_t(J['left'])}" if J.get('left') else '')})
            try: spd += float(str(J.get('speed') or '0').rstrip('x') or 0)
            except Exception: pass
        qd = self.db.one('SELECT COUNT(*), SUM(dur), SUM(size) FROM files WHERE cv_state=1 AND missing=0')
        cvr = rate(self.cv_done_log, 3600)
        out.append({'k': 'conv', 'icon': '🔁', 'name': '轉檔（→ H.265 MP4）', 'state': 'pause' if self.cv_paused else ('run' if CV else ('wait' if qd[0] else 'idle')), 'items': CV,
                    'left': int(qd[0] or 0), 'speed': (f'現在合計 {spd:.1f} 倍速' if spd else '') + (f' · 每小時約 {cvr * 3600:.0f} 部' if cvr else ''),
                    'eta': (self.conv_eta().get('eta') if qd[0] else None), 'note': f"排隊共 {fmt_b(qd[2] or 0)}（還要多久是保守估、多抓）" if qd[0] else ''})
        R = self.rv_st
        if R['run'] or R['q']:
            out.append({'k': 'reverify', 'icon': '🔍', 'name': '重新驗證畫質', 'state': 'run' if R['run'] else 'wait', 'items': [{'name': R['cur'], 'pct': None, 'sub': ''}] if R['cur'] else [],
                        'left': len(R['q']), 'speed': '', 'eta': None, 'note': f"做完 {R['done']} 部"})
        cut = self.cut_cur
        out.append({'k': 'cut', 'icon': '✂', 'name': '初剪', 'state': 'run' if cut else ('wait' if self.cut_q else 'idle'),
                    'items': [{'name': (cut.get('name') or Path(cut.get('path', '')).name), 'pct': (cut.get('task') or {}).get('pct'), 'sub': f"{len(cut.get('segs') or [])} 段"}] if cut else [],
                    'left': len(self.cut_q), 'speed': '', 'eta': None, 'note': ''})
        op = self.op_cur
        out.append({'k': 'op', 'icon': '📦', 'name': '搬檔（歸檔、收藏、待刪）', 'state': 'run' if op else ('wait' if self.op_q else 'idle'),
                    'items': [{'name': str((op or {}).get('title') or (op or {}).get('name') or ''), 'pct': None, 'sub': ''}] if op else [], 'left': len(self.op_q), 'speed': '', 'eta': None, 'note': ''})
        H = getattr(self, 'hz', None)
        if H is not None:                                                        # 🔥 HotZone（另外的程式，在這裡一起看）
            try:
                hs = H.status()
                if hs['running']:
                    q = hs.get('queue') or {}; hot = [v for v in hs.get('hot') or [] if v.get('state') in ('moving', 'evicting', 'planning')]
                    items = [{'name': f"{v.get('letter')} 熱區：{v.get('msg') or v.get('state')}", 'pct': v.get('pct_in'), 'sub': (fmt_b(v.get('rate') or 0) + '/s') if v.get('rate') else ''} for v in hot]
                    if q.get('running'): items.insert(0, {'name': f"搬檔佇列 {q.get('running')} 個在跑", 'pct': None, 'sub': (fmt_b(q.get('speed') or 0) + '/s') if q.get('speed') else ''})
                    note = '　'.join(f"⚖ {a['disk']}：{a['why']}" for a in hs.get('arb') or [])
                    out.append({'k': 'hotzone', 'icon': '🔥', 'name': 'HotZone（搬檔佇列、熱區、索引）' + ('' if hs['ours'] else '（原本的 HotZoneFM.exe）'),
                                'state': 'run' if (q.get('running') or hot) else ('wait' if q.get('queued') else 'idle'), 'items': items,
                                'left': int(q.get('queued') or 0) or None, 'speed': '', 'eta': None, 'note': note or ('熱區暫停中' if hs.get('hot_paused') else '')})
                else:
                    out.append({'k': 'hotzone', 'icon': '🔥', 'name': 'HotZone（搬檔佇列、熱區、索引）', 'state': 'idle', 'items': [], 'left': None, 'speed': '', 'eta': None,
                                'note': '背景引擎沒有在跑（🔥 HotZone 頁可以啟動）'})
            except Exception: pass
        for t in self.tasks_list()[-60:]:                                        # 其他（找相似、資料庫備份、清理…）
            if t['state'] == 'run' and t['kind'] not in ('scan', 'thumb', 'conv', 'cut', 'op'):
                out.append({'k': 'task' + str(t['id']), 'icon': '⚙', 'name': t['title'], 'state': 'run', 'items': [{'name': t.get('msg', ''), 'pct': t.get('pct'), 'sub': ''}], 'left': None, 'speed': '', 'eta': None, 'note': ''})
        return out

    # ---------- 查詢（給畫面；都在背景執行緒呼叫）
    def jobs_view(self):
        """上方「✂ 剪輯／轉檔」浮窗用：最近的初剪工作（排隊／剪輯中／完成／失敗、輸出檔、原檔刪了沒）、正在轉檔的、排隊數."""
        J = list(self.cut_hist)[-80:][::-1]; ids = list({j['fid'] for j in J})
        st = {r['id']: dict(r) for r in self.db.q('SELECT id,missing,cut_n FROM files WHERE id IN (%s)' % (','.join(str(int(i)) for i in ids) or '-1'))}
        cuts = [{'key': j['task']['id'], 'fid': j['fid'], 'name': j.get('name') or Path(j['path']).name, 'path': j['path'], 'nseg': len(j['segs']), 'merge': j['merge'],
                 'mode': j['mode'], 'state': j.get('state', 'wait'), 'pct': j['task'].get('pct'), 'outs': list(j.get('outs') or []), 'err': j.get('err', ''), 't': j.get('t', 0),
                 'gone': bool((st.get(j['fid']) or {}).get('missing')) or not os.path.exists(j['path']),
                 'secs': sum(b - a for a, b in j['segs'])} for j in J]
        conv = [{'id': k, 'name': v.get('name'), 'pct': v.get('pct') or 0, 'enc': v.get('enc', ''), 'speed': v.get('speed', ''), 'left': v.get('left')} for k, v in list(self.cv_active.items())]
        cv_wait = (self.db.one('SELECT COUNT(*) FROM files WHERE cv_state=1') or [0])[0]
        n_cut = len(self.cut_q) + (1 if self.cut_cur else 0)
        return {'cuts': cuts, 'conv': conv, 'cv_wait': cv_wait, 'cut_active': n_cut, 'op_active': len(self.op_q) + (1 if self.op_cur else 0),
                'active': n_cut + len(conv) + cv_wait + len(self.op_q) + (1 if self.op_cur else 0)}

    def info(self):
        c = self.info_c
        if time.time() - c['t'] < 2: return c['v']
        q = lambda s, a=(): (self.db.one(s, a) or [0])[0] or 0
        lt = time.localtime(); day0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
        v = {'graded_today': q('SELECT COUNT(*) FROM files WHERE length(grade)>0 AND grade_t>=?', (day0,)), 'files': q('SELECT COUNT(*) FROM files WHERE missing=0'), 'bytes': q('SELECT SUM(size) FROM files WHERE missing=0'),
             'probe_left': q("SELECT COUNT(*) FROM files WHERE probed IN (0,2) AND missing=0 AND arch=''"), 'probe_bad': q('SELECT COUNT(*) FROM files WHERE probed=3 AND missing=0'),
             'th_done': q('SELECT COUNT(*) FROM files WHERE th_state=2 AND missing=0'), 'th_left': q("SELECT COUNT(*) FROM files WHERE th_state IN (0,1) AND has_v=1 AND probed!=3 AND missing=0 AND arch=''"),
             'th_left_s': q("SELECT SUM(dur) FROM files WHERE th_state IN (0,1) AND has_v=1 AND probed=1 AND missing=0 AND arch=''"),
             'th_fail': q('SELECT COUNT(*) FROM files WHERE th_state=3 AND missing=0'), 'cv_wait': q('SELECT COUNT(*) FROM files WHERE cv_state=1'),
             'cv_done': q('SELECT COUNT(*) FROM files WHERE cv_state=3'), 'cv_fail': q('SELECT COUNT(*) FROM files WHERE cv_state=4'),
             'nonmp4': q("SELECT COUNT(*) FROM files WHERE missing=0 AND ext NOT IN ('.mp4','.m4v')")}
        try:                                                                    # V0.1.53 側邊欄大數字：待整理、還沒分級（跟檔案總管一樣篩掉不列的格式）
            es, ea = self.ext_sql(); w_ = "missing=0 AND arch=''" + (' AND ' + es if es else '')
            v['lib'] = q(f'SELECT COUNT(*) FROM files WHERE {w_}', tuple(ea)); v['nograde'] = q(f'SELECT COUNT(*) FROM files WHERE {w_} AND length(grade)=0', tuple(ea))
        except Exception: v['lib'] = v['files']; v['nograde'] = 0
        v.update(self.th_eta(v.get('th_left_s') or 0))
        c.update(t=time.time(), v=v); return v

    def th_eta(self, left_s):
        """依最近 30 分鐘真的做好的速度（每秒處理幾秒影片），估計預覽圖還要多久。資料太少（<3 部或 <2 分鐘）就不估."""
        now = time.time(); D = [(x[0], x[1]) for x in list(self.th_done_log) if now - x[0] <= 1800]
        if len(D) < 3: return {'th_rate': 0, 'th_eta': None}
        span = max(now - D[0][0], 120.0); rate = sum(d for _t, d in D) / span
        return {'th_rate': rate, 'th_eta': (left_s / rate) if rate > 0 else None}

    def folders(self):
        """[(folder, 影片數, 預覽好了幾部, 分級好了幾部)]."""
        es, ea = self.ext_sql()
        return [(r[0], r[1], r[2], r[3] or 0) for r in self.db.q(f"SELECT folder,COUNT(*),SUM(th_state=2),SUM(length(grade)>0) FROM files WHERE missing=0 AND arch='' {'AND ' + es if es else ''} GROUP BY folder ORDER BY folder", ea)]

    def folder_progress(self):
        """V0.2.84 📂 各資料夾分級進度：部數、大小、預覽好了、分級了、還沒分、F 待刪大小；還沒分最多的排前面."""
        es, ea = self.ext_sql(); out = []
        for r in self.db.q(f"SELECT folder, COUNT(*) n, COALESCE(SUM(size),0) b, SUM(th_state=2) th, SUM(length(grade)>0) g, SUM(CASE WHEN grade='F' THEN size ELSE 0 END) fb, SUM(CASE WHEN grade='' AND th_state=2 THEN 1 ELSE 0 END) rd, SUM(grade IN ('S','A')) sa, SUM(CASE WHEN grade IN ('S','A') AND up_t>0 THEN 1 ELSE 0 END) su "
                           f"FROM files WHERE missing=0 AND arch='' {'AND ' + es if es else ''} GROUP BY folder", ea):
            n = int(r['n'] or 0); g = int(r['g'] or 0)
            out.append({'folder': r['folder'], 'n': n, 'bytes': int(r['b'] or 0), 'th': int(r['th'] or 0), 'graded': g, 'left': n - g, 'ready': int(r['rd'] or 0), 'f_bytes': int(r['fb'] or 0),
                        'pct': round(g * 100 / n) if n else 0, 'sa': int(r['sa'] or 0), 'sa_up': int(r['su'] or 0)})   # V0.4.01 S／A 傳了幾部
        return sorted(out, key=lambda x: (-x['ready'], -x['left'], x['folder']))

    ED_SKIP = {'.vsdata', 'videosift', '$recycle.bin', 'system volume information', '.trash', 'found.000'}

    def empty_scan(self):
        """V0.2.45 🧹 找影片庫裡的空資料夾（裡面一個檔都沒有，子資料夾也是空的）：背景跑，結果放 self._ed."""
        ed = getattr(self, '_ed', None)
        if ed and ed.get('run'): return False
        self._ed = {'run': True, 'rows': [], 't': time.time(), 'n': 0}

        def work():
            out = []; seen = 0
            try:
                for root in [str(r) for r in self.cfg.get('roots') or []]:
                    if not os.path.isdir(root): continue
                    empty = {}; mine = []; rk = os.path.normcase(os.path.normpath(root))
                    for dp, dns, fns in os.walk(root, topdown=False, onerror=lambda e: None):
                        seen += 1
                        if seen % 500 == 0: self._ed['n'] = seen
                        if any(p_.lower() in self.ED_SKIP for p_ in Path(dp).parts): empty[dp] = False; continue
                        e = not fns and all(empty.get(os.path.join(dp, d_), False) for d_ in dns); empty[dp] = e
                        if e and os.path.normcase(os.path.normpath(dp)) != rk: mine.append(dp)
                    ms = set(mine); out += [d_ for d_ in mine if os.path.dirname(d_) not in ms]     # 只留最上層的空資料夾（底下的一起刪）
                self._ed['rows'] = sorted(set(out), key=str.lower)[:5000]
            except Exception: self.log.err('找空資料夾')
            self._ed['run'] = False; self._ed['n'] = seen; self._ed['t'] = time.time()
        threading.Thread(target=work, daemon=True, name='empty_scan').start(); return True

    def empty_view(self):
        ed = getattr(self, '_ed', None) or {}
        return {'run': bool(ed.get('run')), 'rows': list(ed.get('rows') or []), 'n': ed.get('n', 0), 't': ed.get('t', 0), 'done': bool(ed) and not ed.get('run')}

    def empty_remove(self, dirs):
        """只刪真的空的（os.rmdir 遇到有東西就會失敗，不會誤刪檔案）."""
        ok = 0; fail = 0; R = set(str(x) for x in (self.cfg.get('roots') or []))
        for d in dirs or []:
            d = str(d)
            if d in R or not os.path.isdir(d): continue
            try:
                for dp, dns, fns in os.walk(d, topdown=False):
                    if fns: raise OSError('不是空的')
                    os.rmdir(dp)
                ok += 1
            except Exception: fail += 1
        ed = getattr(self, '_ed', None)
        if ed: ed['rows'] = [x for x in ed.get('rows') or [] if os.path.isdir(x)]
        self.log.w(f'🧹 刪掉空資料夾 {ok} 個' + (f'（{fail} 個不是空的或刪不掉，保留）' if fail else '')); return ok, fail

    def day_goal(self):
        """V0.2.44 🎯 每日分級目標：{'n': 今天分級幾部, 'goal': 目標, 'done': 達成了沒}；20 秒快取."""
        L = self.cfg.get('lab') or {}
        if not (L.get('goal') or L.get('daily_goal')): return None
        G_ = int(self.cfg.get('daily_goal_n') or L.get('goal_n') or 100)               # V0.2.68 跟原本「🎯 每日整理目標」共用同一個目標數
        c = getattr(self, '_goal_c', None)
        if c and time.time() - c[0] < 20 and c[1]['goal'] == G_: return c[1]
        lt = time.localtime(); t0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
        try: n = int(self.db.one("SELECT COUNT(*) FROM files WHERE grade!='' AND grade_t>=?", (t0,))[0] or 0)
        except Exception: n = 0
        g = max(1, G_); r = {'n': n, 'goal': g, 'done': n >= g, 'streak': self._goal_streak(g, t0, n >= g)}; self._goal_c = (time.time(), r)
        if r['done'] and getattr(self, '_goal_day', '') != time.strftime('%Y%m%d'): self._goal_day = time.strftime('%Y%m%d'); self.log.w(f'🎯 今天的分級目標 {g} 部達成（{n} 部）')
        return r

    def drive_busy(self):
        """V0.4.49 🔌 拔硬碟前看一下：每顆接著的硬碟現在有沒有在讀寫（預覽圖、轉檔、初剪、複製、搬硬碟）→ {代號: [在做什麼]}."""
        D = {}
        def add(p, what):
            try:
                p = str(p or '')
                if len(p) >= 2 and p[1] == ':': D.setdefault(p[0].upper(), set()).add(what)
            except Exception: pass
        try:
            for x in list((getattr(self, 'th_active', None) or {}).values()): add(x.get('path'), '🖼 做預覽圖')
            for x in list((getattr(self, 'cv_active', None) or {}).values()): add(x.get('path'), '🔁 轉檔')
            S_ = getattr(self, 'scan_st', None) or {}
            if S_.get('running'): add(S_.get('cur'), '📂 掃描資料夾')                     # V0.5.08 掃描、讀影片資訊也算（整理才知道要讓路、拔硬碟前也看得到）
            for p_ in list((getattr(self, 'pr_cur', None) or {}).values()): add(p_, '🏷 讀影片資訊')
            c = getattr(self, 'cut_cur', None)
            if c: add((self.file(c.get('fid')) or {}).get('path'), '✂ 初剪')
            C = getattr(self, '_cs', None) or {}
            if C.get('run'): add(self.copy_dest(), '📤 複製（寫入）')
            if (getattr(self, '_mv_st', None) or {}).get('run'):
                M = self.cfg.get('disk_move') or {}; add(M.get('src') or M.get('from'), '🚚 搬硬碟'); add(M.get('dst') or M.get('to'), '🚚 搬硬碟')
        except Exception: pass
        try: L = sorted(set(self.vol_letters_c().values()))
        except Exception: L = []
        return [{'d': x, 'busy': sorted(D.get(x, set()))} for x in sorted(set(L) | set(D))]

    def bg_busy(self):
        """V0.4.03 背景有沒有在做事（☕ 不睡用）：回傳在做的項目名稱 list."""
        B = []
        try:
            if getattr(self, 'cv_active', None): B.append('轉檔')
            if getattr(self, 'th_active', None): B.append('預覽圖')
            if getattr(self, 'cut_q', None) or getattr(self, 'cut_cur', None): B.append('初剪')
            if (getattr(self, '_cs', None) or {}).get('run'): B.append('複製到上傳')
            if (getattr(self, '_mv_st', None) or {}).get('run'): B.append('搬硬碟')
            if (getattr(self, 'scan_st', None) or {}).get('running'): B.append('掃描')
            f_ = self.fc_bg()                                                    # V0.5.61 整理（FileCompare）在做事也算（☕ 不睡、手機「正在做」都看得到）
            if f_ and f_.get('run'): B.append('整理（' + '、'.join(x.split(' ', 1)[-1] for x in f_['run'][:2]) + '）')
        except Exception: pass
        return B

    def break_check(self):
        """V0.3.88 👀 休息提醒：連續分級（中間沒停超過 5 分鐘）超過 N 分鐘 → {'mins': 連續幾分鐘, 'n': 這段分了幾部}；同一段只提醒一次；30 秒快取."""
        L = self.cfg.get('lab') or {}
        if not L.get('break_remind'): return None
        c = getattr(self, '_brk_c', None)
        if c and time.time() - c[0] < 30: return c[1]
        r = None
        try:
            N = max(10, int(L.get('break_min') or 45)); now = time.time()
            T = [float(x[0]) for x in self.db.q("SELECT grade_t FROM files WHERE grade_t>=? AND grade!='' ORDER BY grade_t DESC LIMIT 3000", (now - 4 * 3600,))]
            if T and now - T[0] < 300:
                st = T[0]; n = 1
                for a_, b_ in zip(T, T[1:]):
                    if a_ - b_ > 300: break
                    st = b_; n += 1
                mins = int((T[0] - st) // 60)
                if mins >= N and getattr(self, '_brk_said', 0) != round(st): self._brk_said = round(st); r = {'mins': mins, 'n': n, 'id': round(st)}
                elif getattr(self, '_brk_said', 0) == round(st): r = getattr(self, '_brk_last', None)
            if r: self._brk_last = r
        except Exception: self.log.err('休息提醒')
        self._brk_c = (time.time(), r); return r

    def random_ungraded(self, folder='', n=1):
        """V0.3.84 🎲 隨便抽還沒分級（預覽圖好了）的：看膩了換換口味。folder＝只在這個資料夾（含子資料夾）."""
        w = ["missing=0", "arch=''", "grade=''", 'th_state=2']; a = []
        if folder: f = str(folder).rstrip('\\/'); w.append('(folder=? OR substr(folder,1,?) IN (?,?))'); a += [f, len(f) + 1, f + '\\', f + '/']
        try:
            tot = int(self.db.one(f'SELECT COUNT(*) FROM files WHERE {" AND ".join(w)}', a)[0] or 0)
            if not tot: return []
            return [int(self.db.one(f'SELECT id FROM files WHERE {" AND ".join(w)} LIMIT 1 OFFSET ?', a + [random.randrange(tot)])[0]) for _ in range(max(1, int(n)))]
        except Exception: self.log.err('隨機抽'); return []

    def grade_heat(self, days=84):
        """V0.4.09 🗓 最近 12 週每天分級幾部（熱圖用）：[{'d': 'YYYY-MM-DD', 'n', 'up'}]，最舊在前."""
        t0 = time.time() - days * 86400; D = {}; U = {}; P = {}
        try:
            for r in self.db.q("SELECT date(grade_t,'unixepoch','localtime') d, COUNT(*) n FROM files WHERE grade_t>=? AND grade!='' GROUP BY d", (t0,)): D[r['d']] = int(r['n'])
            for r in self.db.q("SELECT date(up_t,'unixepoch','localtime') d, COUNT(*) n FROM files WHERE up_t>=? GROUP BY d", (t0,)): U[r['d']] = int(r['n'])
            for r in self.db.q("SELECT date(pub_t,'unixepoch','localtime') d, COUNT(*) n FROM files WHERE pub_t>=? GROUP BY d", (t0,)): P[r['d']] = int(r['n'])   # V0.4.43 ✅
        except Exception: pass
        return [{'d': d, 'n': D.get(d, 0), 'up': U.get(d, 0), 'pub': P.get(d, 0)} for d in (time.strftime('%Y-%m-%d', time.localtime(time.time() - i * 86400)) for i in range(days - 1, -1, -1))]

    def day_text(self):
        """V0.4.34 🧾 今天的工作日報（純文字，可以貼到 LINE／群組）."""
        R = self.review_report(7); T = R['today']; L = self.cfg.get('lab') or {}
        out = [f"📅 {time.strftime('%Y/%m/%d')} SortCut 日報", f"🎬 分級 {T['graded']} 部（S {T['S']}・A {T['A']}・E {T['E']}・F {T['F']}）"]
        if T.get('cuts'): out.append(f"✂ 剪了 {T['cuts']} 段")
        if L.get('copy_to'): out.append(f"📤 複製到上傳 {T.get('up', 0)} 部・✅ 發佈 {T.get('pub', 0)} 部・S／A 還沒傳 {self.up_left()} 部")
        if T.get('cv_n') or T.get('purge_b'): out.append(f"💾 轉檔 {T['cv_n']} 部・省下／清掉 {fmt_b(int(T.get('cv_save') or 0) + int(T.get('purge_b') or 0))}")
        G = self.day_goal() if hasattr(self, 'day_goal') else None
        if G: out.append(f"🎯 目標 {G['n']}／{G['goal']}" + (' 🎉 達成' if G['done'] else '') + (f"・🔥 連續 {G['streak']} 天" if G.get('streak', 0) >= 2 else ''))
        out.append(f"⏳ 還沒分級 {int(R.get('ungraded', R.get('left', 0)) or 0):,} 部" + (f"（照速度約 {R['eta_days']:g} 天分完）" if R.get('eta_days') else ''))
        return '\n'.join(out)

    def week_review(self):
        """V0.3.80 📆 這週回顧：最近 7 天 vs 前 7 天（分級、上傳、剪輯、省下／清掉的空間、衝刺最佳、有審的天數）."""
        R = self.review_report(14); D = R['days']; a, b = D[-7:], D[:7]
        s_ = lambda L, k: sum(int(x.get(k) or 0) for x in L)
        H = [h for h in (self.cfg.get('sprint_hist') or []) if float(h.get('t') or 0) >= time.time() - 7 * 86400]
        out = {'wk': time.strftime('%G-W%V'), 'graded': s_(a, 'graded'), 'graded_prev': s_(b, 'graded'), 'S': s_(a, 'S'), 'A': s_(a, 'A'), 'up': s_(a, 'up'), 'up_prev': s_(b, 'up'), 'pub': s_(a, 'pub'),
               'cuts': s_(a, 'cuts'), 'saved': s_(a, 'cv_save') + s_(a, 'purge_b'), 'active': sum(1 for x in a if x.get('graded')), 'best_day': max(a, key=lambda x: x.get('graded') or 0)['d'] if any(x.get('graded') for x in a) else '',
               'sprint_n': len(H), 'sprint_best': max((float(h.get('rate') or 0) for h in H), default=0), 'left': R.get('ungraded', R.get('left', 0))}
        g, p = out['graded'], out['graded_prev']; out['trend'] = (round((g - p) * 100 / p) if p else (100 if g else 0))
        return out

    def sprint_start(self, mins=15):
        """V0.3.72 ⏱ 分級衝刺：接下來 N 分鐘專心分級，算分了幾部、平均幾秒一部."""
        mins = max(1, min(180, int(mins or 15))); self.cfg.set('sprint', {'t0': time.time(), 'min': mins}); self._spr_c = None
        return f'⏱ 衝刺 {mins} 分鐘開始！'

    def sprint_stop(self):
        S = self.cfg.get('sprint') or {}
        if not S.get('t0'): return None
        V = self.sprint_view(final=True); self.cfg.set('sprint', {}); return V

    def sprint_view(self, final=False):
        """{'on', 'left', 'n', 'min', 'per', 'best', 'done'}；時間到自動收尾、記錄最佳（3 秒快取）."""
        S = self.cfg.get('sprint') or {}
        if not S.get('t0'): return None
        c = getattr(self, '_spr_c', None)
        if c and not final and time.time() - c[0] < 3: return c[1]
        t0 = float(S['t0']); m = int(S.get('min') or 15); end = t0 + m * 60; now = time.time()
        try: n = int(self.db.one("SELECT COUNT(*) FROM files WHERE grade!='' AND grade_t>=? AND grade_t<=?", (t0, min(now, end)))[0] or 0)
        except Exception: n = 0
        H = self.cfg.get('sprint_hist') or []; best = max((h.get('rate', 0) for h in H), default=0)
        el = max(1, min(now, end) - t0); rate = round(n / (el / 60), 1)
        r = {'on': now < end, 'left': max(0, int(end - now)), 'n': n, 'min': m, 'per': (round(el / n, 1) if n else None), 'rate': rate, 'best': best}
        if (now >= end or final) and not S.get('saved'):
            nb = bool(n and rate > best); H = (H + [{'t': t0, 'min': m, 'n': n, 'rate': rate}])[-30:]; self.cfg.set('sprint_hist', H); S = dict(S, saved=True, nb=nb); self.cfg.set('sprint', S)
            self.log.w(f'⏱ 衝刺 {m} 分鐘結束：分了 {n} 部（每分鐘 {rate}）' + ('🏆 新紀錄' if nb else ''))
        r['done'] = now >= end; r['new_best'] = bool(S.get('nb'))
        if now > end + 900 and not final: self.cfg.set('sprint', {}); return None   # 結束 15 分鐘後收起來（紀錄已經存好）
        self._spr_c = (time.time(), r); return r

    def up_left(self):
        """V0.3.65 📤 S／A 還沒上傳幾部（封面捷徑用，30 秒快取；沒開複製到上傳就 0）."""
        if not (self.cfg.get('lab') or {}).get('copy_to'): return 0
        c = getattr(self, '_upl_c', None)
        if c and time.time() - c[0] < 30: return c[1]
        try: n = int(self.db.one("SELECT COUNT(*) FROM files WHERE grade IN ('S','A') AND up_t<=0 AND missing=0")[0] or 0)
        except Exception: n = 0
        self._upl_c = (time.time(), n); return n

    def unpub_n(self):
        """V0.4.36 ⬜ 複製了還沒發佈幾部（30 秒快取）."""
        if not (self.cfg.get('lab') or {}).get('copy_to'): return 0
        c = getattr(self, '_unp_c', None)
        if c and time.time() - c[0] < 30: return c[1]
        try: n = int(self.db.one('SELECT COUNT(*) FROM files WHERE up_t>0 AND pub_t<=0 AND missing=0')[0] or 0)
        except Exception: n = 0
        self._unp_c = (time.time(), n); return n

    def up_goal(self):
        """V0.3.63 📤 每天上傳目標：{'n': 今天複製到上傳幾部, 'goal', 'done'}；沒設（0）就 None；20 秒快取."""
        L = self.cfg.get('lab') or {}
        try: g = int(L.get('up_goal') or 0)
        except Exception: g = 0
        if not L.get('copy_to') or g <= 0: return None
        c = getattr(self, '_upg_c', None)
        if c and time.time() - c[0] < 20 and c[1]['goal'] == g: return c[1]
        lt = time.localtime(); t0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
        by = 'pub' if str(L.get('up_goal_by') or '') == 'pub' else 'up'                # V0.4.44 目標可以算「發佈」而不是「複製」
        try: n = int(self.db.one(f'SELECT COUNT(*) FROM files WHERE {by}_t>=?', (t0,))[0] or 0)
        except Exception: n = 0
        r = {'n': n, 'goal': g, 'done': n >= g, 'by': by}; self._upg_c = (time.time(), r); return r

    def _goal_streak(self, g, t0, today_done):
        """V0.3.04 🔥 連續幾天達成（今天達成也算；今天還沒達成就從昨天往回數）."""
        try:
            D = {r[0]: int(r[1]) for r in self.db.q("SELECT date(grade_t,'unixepoch','localtime') d, COUNT(*) FROM files WHERE grade!='' AND grade_t>=? AND grade_t<? GROUP BY d", (t0 - 60 * 86400, t0))}
            k = 0; day = t0 - 86400
            while k < 60:
                ds = time.strftime('%Y-%m-%d', time.localtime(day + 3600))
                if D.get(ds, 0) >= g: k += 1; day -= 86400
                else: break
            return k + (1 if today_done else 0)
        except Exception: return 0

    def day_goal_set(self, n):
        g = max(1, min(100000, int(n or 100))); self.cfg.set('daily_goal_n', g); self._goal_c = None; return g

    def pack_overview(self):
        """V0.2.51 🖥 硬碟在哪台電腦：每顆接著的硬碟，紀錄最後是哪台電腦、什麼時候寫的、幾部、分級多少."""
        out = []; me = self.pc_uid(); roots = [str(r) for r in self.cfg.get('roots') or []]
        try: L = self.vol_letters()
        except Exception: L = {}
        for sn, X in sorted(L.items(), key=lambda x: x[1]):
            J = self._pack_json(X) or {}
            out.append({'d': X, 'serial': sn, 'label': J.get('label') or (self.cfg.get('vol_label') or {}).get(sn, ''), 'has': bool(J), 'pc_name': J.get('pc_name') or J.get('pc') or '',
                        'mine': bool(J) and J.get('pc_uid') == me, 't': float(J.get('t') or 0), 'app': J.get('app') or '', 'n': int(J.get('n') or 0), 'graded': int(J.get('graded') or 0),
                        'th': int(J.get('th') or 0), 'in_lib': any(r[:1].upper() == X for r in roots)})
        return {'me': self.pc_name(), 'color': self.pc_color(), 'rows': out}

    def copy_dest(self):
        """V0.3.03 上傳資料夾的實際位置：記得是哪顆硬碟，代號變了跟著換；那顆沒接上＝''（不會複製到別顆）."""
        L = self.cfg.get('lab') or {}; d = str(L.get('copy_dir') or '').strip(); sn = str(L.get('copy_dir_vol') or '')
        if not d or not sn or len(d) < 2 or d[1] != ':': return d
        try: V = self.vol_letters_c()
        except Exception: return d
        if not V: return d
        return self.path_fix(d, sn) if sn in V else ''

    def up_old(self, days=14):
        """V0.3.66 🧹 上傳資料夾裡放超過 N 天的檔（以複製進去的時間算）：{'dir', 'rows': [{rel, size, age}], 'bytes'}."""
        d = self.copy_dest(); R = []; tot = 0
        if not d or not os.path.isdir(d): return {'dir': d, 'rows': [], 'bytes': 0, 'ok': False, 'message': '上傳資料夾沒設定或沒接上'}
        lim = time.time() - max(0, float(days)) * 86400; cur = str((getattr(self, '_cs', None) or {}).get('cur') or '')
        for root, dirs, files in os.walk(d):
            for n in files:
                p = os.path.join(root, n)
                try: st = os.stat(p)
                except Exception: continue
                t = max(st.st_mtime, st.st_ctime)
                if t > lim or n == cur or n.endswith('.vspart'): continue
                R.append({'rel': os.path.relpath(p, d), 'size': st.st_size, 'age': int((time.time() - t) // 86400)}); tot += st.st_size
                if len(R) >= 3000: break
            if len(R) >= 3000: break
        try:                                                                    # V0.4.22 哪些已經發佈了（從複製紀錄對回影片）
            P_ = {}
            for r in self.db.q("SELECT o.dst, f.pub_t FROM oplog o JOIN files f ON f.id=o.fid WHERE o.kind='upcopy' AND o.undone=0"):
                try: P_[os.path.normcase(os.path.relpath(str(r[0]), d))] = float(r[1] or 0) > 0
                except Exception: pass
            for x in R: x['pub'] = P_.get(os.path.normcase(x['rel']))
        except Exception: pass
        R.sort(key=lambda x: -x['age']); return {'ok': True, 'dir': d, 'rows': R, 'bytes': tot}

    def up_auto_clean(self):
        """V0.4.50 🧺 自動清理：上傳資料夾裡「已發佈」而且放超過 N 天的複本丟到資源回收筒（沒發佈的、對不到紀錄的都不動）；一天最多做一次."""
        L = self.cfg.get('lab') or {}
        try: N = int(L.get('up_auto_clean') or 0)
        except Exception: N = 0
        if not L.get('copy_to') or N <= 0 or self.cfg.get('up_ac_day') == time.strftime('%Y%m%d'): return 0, ''
        self.cfg.set('up_ac_day', time.strftime('%Y%m%d'))
        R = [x['rel'] for x in self.up_old(N).get('rows') or [] if x.get('pub') is True]
        if not R: return 0, ''
        n, m = self.up_old_rm(R, N); self.log.w(f'🧺 自動清理上傳資料夾：{m}'); return n, m

    def up_old_rm(self, rels, days=14):
        """V0.3.66 把上傳資料夾裡的舊檔丟到資源回收筒（只收上傳資料夾裡面、而且真的超過 N 天的；救得回來）."""
        d = self.copy_dest()
        if not d or not os.path.isdir(d): return 0, '上傳資料夾沒設定或沒接上'
        ok_ = {x['rel'] for x in self.up_old(days)['rows']}; base = os.path.realpath(d); n = 0; b = 0; bad = 0
        for r in rels or []:
            r = str(r)
            if r not in ok_: continue
            p = os.path.realpath(os.path.join(d, r))
            if not p.startswith(base + os.sep): continue
            try: sz = os.path.getsize(p)
            except Exception: sz = 0
            if send_to_recycle(p): n += 1; b += sz
            else: bad += 1
        if n: self.log.w(f'🧹 上傳資料夾清掉 {n} 個舊檔（{fmt_b(b)}），在資源回收筒')
        return n, f'🧹 丟到資源回收筒 {n} 個（{round(b / 1e9, 2)} GB）' + (f'・{bad} 個丟不掉' if bad else '')

    def copy_kick(self):
        """V0.3.03 排隊還有、沒在複製、上傳資料夾那顆接回來了 → 接著做（每分鐘看一次）."""
        C = getattr(self, '_cs', None) or {}
        if C.get('run') or not getattr(self, '_cq', None) or getattr(self, '_cpause', False) or not self.copy_dest() or self.bg_sched_hold('copy'): return False
        self._cs = {'run': True, 'done': C.get('done', 0), 'fail': C.get('fail', 0), 'skip': C.get('skip', 0), 'cur': '', 'pct': 0, 'speed': 0.0}
        threading.Thread(target=self._copy_work, daemon=True, name='copy_to').start(); return True

    def copy_view(self):
        """V0.2.49 📤 複製到上傳資料夾：{'dir', 'q': 排隊幾部, 'cur', 'pct', 'done', 'fail', 'skip', 'speed', 'run'}."""
        C = getattr(self, '_cs', None) or {}
        return {'dir': self.copy_dest() or (str((self.cfg.get('lab') or {}).get('copy_dir') or '') + '（硬碟沒接上）'), 'q': len(getattr(self, '_cq', None) or []), 'cur': C.get('cur', ''), 'pct': C.get('pct', 0),
                'done': C.get('done', 0), 'fail': C.get('fail', 0), 'skip': C.get('skip', 0), 'speed': C.get('speed', 0.0), 'run': bool(C.get('run')), 'last_err': C.get('err', ''),
                'paused': bool(getattr(self, '_cpause', False))}

    def copy_ctl(self, a):
        """V0.2.76 📤 複製佇列：pause／resume／clear／list."""
        if a == 'pause': self._cpause = True; return '⏸ 複製暫停'
        if a == 'resume': self._cpause = False; return '▶ 複製繼續'
        if a == 'clear':
            n = len(getattr(self, '_cq', None) or []); self._cq[:] = [] if getattr(self, '_cq', None) is not None else []; self._cq_save(); return f'🗑 清掉排隊的 {n} 個（正在複製的這個會做完）'
        return ''

    def copy_list(self):
        out = []
        for it_ in list(getattr(self, '_cq', None) or [])[:300]:
            if isinstance(it_, str): out.append({'name': os.path.basename(it_), 'cut': True})
            else:
                f = self.file(it_) or {}; out.append({'name': f.get('name') or f'#{it_}', 'cut': False, 'size': f.get('size') or 0})
        return out

    def up_board(self, n=60):
        """V0.3.69 📋 上傳看板：還沒傳（S 先、A 後）→ 排隊中 → 今天傳好的."""
        lt = time.localtime(); t0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
        qd = {x for x in (getattr(self, '_cq', None) or []) if not isinstance(x, str)}
        todo = [dict(r) for r in self.db.q("SELECT id,name,grade,size,dur FROM files WHERE grade IN ('S','A') AND up_t<=0 AND missing=0 ORDER BY grade, grade_t DESC LIMIT ?", ((int(n) * (6 if str(self.cfg.get('up_order') or '') == 'mix' else 1)) + len(qd),))]
        todo = [r for r in todo if r['id'] not in qd]
        if str(self.cfg.get('up_order') or '') == 'mix':                      # V0.4.26 🔀 作者輪流排：同一個主播不會連著好幾部（S 還是比 A 前面）
            out_ = []
            for g_ in ('S', 'A'):
                Q_ = {}
                for r in todo:
                    if r['grade'] == g_: Q_.setdefault(self.creator_key(r['name']), []).append(r)
                while Q_:
                    for k_ in list(Q_):
                        out_.append(Q_[k_].pop(0))
                        if not Q_[k_]: Q_.pop(k_)
            todo = out_
        todo = todo[:int(n)]
        D_ = self.up_dups([r['id'] for r in todo])
        for r in todo: r['dup'] = D_.get(r['id'], '')
        ddn_ = 7 if int(self.cfg.get('up_done_days') or 1) == 7 else 1            # V0.4.38 「傳好的」看今天或最近 7 天
        done = [dict(r) for r in self.db.q('SELECT id,name,grade,size,up_t,pub_t FROM files WHERE up_t>=? ORDER BY up_t DESC LIMIT ?', ((t0 - 6 * 86400) if ddn_ == 7 else t0, int(n) * (3 if ddn_ == 7 else 1)))]
        unpub = int(self.db.one('SELECT COUNT(*) FROM files WHERE up_t>0 AND pub_t<=0')[0] or 0)   # V0.4.21 複製了但還沒發佈
        V = self.copy_view() if hasattr(self, 'copy_view') else {}
        try:                                                                    # V0.4.05 ⌛ 照目前速度還要幾天傳完
            n7 = int(self.db.one('SELECT COUNT(*) FROM files WHERE up_t>=?', (time.time() - 7 * 86400,))[0] or 0); G_ = self.up_goal(); per = (G_['goal'] if G_ else n7 / 7.0); tl = self.up_left()
            eta = {'per': round(per, 1), 'days': (round(tl / per, 1) if per > 0 else None), 'by': ('goal' if G_ else 'pace')}
        except Exception: eta = None
        try: dd_ = self.copy_dest(); free_ = shutil.disk_usage(dd_).free if dd_ and os.path.isdir(dd_) else None   # V0.4.15 上傳那顆還剩多少
        except Exception: free_ = None
        return {'done_days': ddn_, 'order': str(self.cfg.get('up_order') or ''), 'unpub': unpub, 'free': free_, 'dest': self.copy_dest(), 'eta': eta, 'todo': todo, 'todo_n': self.up_left(), 'queue': self.copy_list()[:int(n)], 'cur': (V.get('cur') or '') if V.get('run') else '', 'pct': V.get('pct') or 0, 'done': done, 'goal': self.up_goal(), 'wait': ('⏸ 暫停中' if V.get('paused') else str(V.get('last_err') or '')) if (V.get('q') and not V.get('run')) else ''}

    def up_csv(self, days=30):
        """V0.3.93 🧾 上傳紀錄 CSV：最近 N 天複製到上傳的（時間、檔名、分級、作者、長度、大小、備註、資料夾）；Excel 打得開（有 BOM）."""
        import csv, io
        b = io.StringIO(); w_ = csv.writer(b); w_.writerow(['上傳時間', '檔名', '分級', '作者', '長度(秒)', '大小(MB)', '備註', '資料夾'])
        for r in self.db.q('SELECT name,grade,dur,size,note,folder,up_t FROM files WHERE up_t>=? ORDER BY up_t DESC', (time.time() - max(1, int(days)) * 86400,)):
            w_.writerow([time.strftime('%Y-%m-%d %H:%M', time.localtime(r['up_t'])), r['name'], r['grade'] or '', self.creator_key(r['name']), round(float(r['dur'] or 0)), round((r['size'] or 0) / 1e6, 1), r['note'] or '', r['folder']])
        return '\ufeff' + b.getvalue()

    def up_undo(self, n=1):
        """V0.4.07 ⏪ 復原最近 n 個「複製到上傳」：上傳資料夾裡那份丟到資源回收筒、取消已上傳標記（只動上傳資料夾裡的複本，原檔不動）."""
        d = self.copy_dest(); base = os.path.realpath(d) if d else ''; k = 0; fail = 0
        for r in self.db.q("SELECT id,fid,dst,name FROM oplog WHERE kind='upcopy' AND undone=0 ORDER BY id DESC LIMIT ?", (max(1, int(n)),)):
            p_ = os.path.realpath(str(r['dst'] or ''))
            if not base or not p_.startswith(base + os.sep): fail += 1; continue
            ok_ = (not os.path.exists(p_)) or send_to_recycle(p_)
            if not ok_: fail += 1; continue
            try:
                tx = os.path.splitext(p_)[0] + '.txt'
                if os.path.exists(tx): send_to_recycle(tx)
            except Exception: pass
            self.db.x('UPDATE oplog SET undone=? WHERE id=?', (time.time(), r['id']))
            if r['fid']: self.db.x('UPDATE files SET up_t=0 WHERE id=?', (int(r['fid']),))
            k += 1
        self._upl_c = self._upg_c = None
        return k, (f'⏪ 復原了 {k} 個（上傳資料夾那份在資源回收筒）' if k else '沒有可以復原的') + (f'・{fail} 個沒辦法復原' if fail else '')

    def pub_mark(self, ids, on=True):
        """V0.4.21 ✅ 標成「已發佈」（真的貼到 TikTok 了；跟「已複製到上傳」分開記）."""
        ids = [int(i) for i in ids or [] if str(i).isdigit()]
        for i in ids: self.db.x('UPDATE files SET pub_t=? WHERE id=?', (time.time() if on else 0, i))
        self._unp_c = None; self._upg_c = None
        return len(ids), (f'✅ {len(ids)} 部標成已發佈' if on else f'↩ {len(ids)} 部取消已發佈')

    def pub_by_names(self, text):
        """V0.4.27 📥 貼一串檔名（一行一個，可以有日期／分級前綴、副檔名可有可無）→ 對到的影片標成已發佈."""
        ids = []; miss = []
        for ln in str(text or '').splitlines():
            t = ln.strip().strip('"').strip()
            if not t: continue
            t = os.path.basename(t.replace('/', '\\').split('\\')[-1]); st = os.path.splitext(t)[0]
            st2 = re.sub(r'^(\d{8}_)?([SAEF]_)?', '', st)                       # 去掉複本檔名加的 20261107_S_
            r = self.db.one("SELECT id FROM files WHERE name=? OR name LIKE ? ORDER BY up_t DESC LIMIT 1", (t, st2 + '.%'))
            (ids.append(int(r[0])) if r else miss.append(t))
        n, _m = self.pub_mark(ids, True) if ids else (0, '')
        return n, f'✅ 標成已發佈 {n} 部' + (f'・{len(miss)} 個對不到（{", ".join(miss[:3])}…）' if miss else '')

    def up_mark(self, ids, on=True):
        """V0.3.58 手動標記／取消「📤 已上傳」（例如自己用別的方式傳過、或上傳資料夾裡刪掉了要重傳）."""
        ids = [int(i) for i in ids or [] if str(i).isdigit()]
        if not ids: return 0, '沒有選影片'
        for i in ids: self.db.x('UPDATE files SET up_t=? WHERE id=?', (time.time() if on else 0, i))
        self._upl_c = self._upg_c = None; self._unp_c = None
        return len(ids), (f'📤 {len(ids)} 部標成已上傳' if on else f'↩ {len(ids)} 部取消已上傳標記')

    def copy_enqueue(self, ids):
        """把這幾部排進「複製到上傳資料夾」（不是搬：原檔留著）。回傳 (排進去幾部, 訊息)."""
        L = self.cfg.get('lab') or {}; dst = str(L.get('copy_dir') or '').strip()
        if not L.get('copy_to'): return 0, '請先在 實驗工作區 打開「📤 複製到上傳資料夾」'
        if not dst: return 0, '還沒設定上傳資料夾（實驗工作區 →「📤 複製到上傳資料夾」底下）'
        Q = self._cq = getattr(self, '_cq', None) or []; have = {x for x in Q}; n = 0
        for i in ids or []:
            if not (isinstance(i, str) and not i.isdigit()):
                try: i = int(i)
                except Exception: continue
            if i not in have: Q.append(i); have.add(i); n += 1
        self._cq_save()
        C = getattr(self, '_cs', None)
        if not C or not C.get('run'):
            self._cs = {'run': True, 'done': 0, 'fail': 0, 'skip': 0, 'cur': '', 'pct': 0, 'speed': 0.0}
            threading.Thread(target=self._copy_work, daemon=True, name='copy_to').start()
        dup = self.up_dups([i for i in ids or [] if not isinstance(i, str)])   # V0.3.74 ♻ 跟已經上傳過的很像（同一支影片的另一份）
        h_ = self.bg_sched_hold('copy')
        return n, f'📤 排了 {n} 部 → {dst}' + (f'（{h_}，時段到了自動開始）' if h_ else '') + (f'　⚠ 其中 {len(dup)} 部跟已經上傳過的是同一支（{", ".join(list(dup.values())[:2])}…）' if dup else '')

    def up_dups(self, ids):
        """V0.3.74 ♻ 這幾部裡哪些「另一份」已經上傳過：一樣的畫面指紋，或一樣大小＋長度。回傳 {id: 已上傳那份的檔名}."""
        out = {}
        for i in ids or []:
            try:
                f = self.db.one('SELECT id,vfp,size,dur FROM files WHERE id=?', (int(i),))
                if not f: continue
                r = None
                if f['vfp']: r = self.db.one("SELECT name FROM files WHERE vfp=? AND id!=? AND up_t>0 LIMIT 1", (f['vfp'], f['id']))
                if not r and f['size'] and f['dur']: r = self.db.one('SELECT name FROM files WHERE size=? AND ABS(dur-?)<0.2 AND id!=? AND up_t>0 LIMIT 1', (f['size'], f['dur'], f['id']))
                if r: out[int(i)] = r[0]
            except Exception: continue
        return out

    def _cq_save(self):
        """V0.2.75 複製佇列存起來：程式關掉／更新後還會接著複製."""
        try: self.cfg.set('copy_q', list(getattr(self, '_cq', None) or [])[:5000]); self.cfg.set('copy_src', {k: v for k, v in (getattr(self, '_cut_src', None) or {}).items() if k in set(self._cq or [])})
        except Exception: pass

    def copy_resume(self):
        Q = [x for x in (self.cfg.get('copy_q') or []) if isinstance(x, (int, str))]
        if not Q or not (self.cfg.get('lab') or {}).get('copy_to'): return 0
        self._cut_src = dict(self.cfg.get('copy_src') or {}); self._cq = []
        n, _m = self.copy_enqueue(Q); self.log.w(f'📤 接著複製上次沒做完的 {n} 個'); return n

    def cut_outs(self, ids):
        """V0.2.59 這幾部「剪好的片段」檔案（還在的）."""
        out = []
        for i in ids or []:
            try: R = self.db.q('SELECT out FROM cuts WHERE file_id=? AND state=1 ORDER BY id', (int(i),))
            except Exception: continue
            out += [r[0] for r in R if r[0] and os.path.isfile(r[0])]
        return out

    def copy_cuts(self, ids):
        P = []; M = self._cut_src = getattr(self, '_cut_src', None) or {}
        for i in ids or []:
            for x in self.cut_outs([i]): P.append(x); M[x] = int(i)
        if not P: return 0, '這幾部沒有剪好的片段（或片段檔不在了）'
        n, m = self.copy_enqueue(P); return n, m.replace('部', '個片段') if n else m

    def _copy_work(self):
        C = self._cs; Q = self._cq
        try:
            while Q and not self.stop_all and not getattr(self, 'retired', False):   # V0.2.88 熱更新後舊引擎做完手上這個就停，新引擎接著做
                h_ = self.bg_sched_hold('copy')                                        # V0.3.90 🕑 時段外／直播中：排隊留著，時段到了 copy_kick 接著做
                if h_: C['err'] = h_; break
                C.pop('err', None) if str(C.get('err') or '').startswith(('🕑', '🎥')) else None
                it_ = Q.pop(0); self._cq_save(); L = self.cfg.get('lab') or {}; dst = self.copy_dest()
                src = it_ if isinstance(it_, str) else (self.file(it_) or {}).get('path')        # V0.2.59 也可以直接放路徑（剪好的片段）
                if not dst and str(L.get('copy_dir') or ''): C['err'] = '上傳資料夾那顆硬碟沒接上'; Q.insert(0, it_); self._cq_save(); break   # 等硬碟接回來再做（排隊留著）
                if not src or not dst: C['fail'] += 1; continue
                sub_ = str(L.get('copy_sub') or '')                                     # V0.3.53 放進子資料夾：今天日期／作者
                if sub_ == 'date': dst = os.path.join(dst, time.strftime('%Y-%m-%d'))
                elif sub_ == 'creator':
                    ck_ = self.creator_key(os.path.basename(src)); dst = os.path.join(dst, safe_name(ck_) if ck_ and ck_ != '（其他）' else '其他')
                nm_ = os.path.basename(src); cn_ = str(L.get('copy_name') or '')                  # V0.3.85 複本檔名前面加日期／分級（方便照順序發）
                if cn_:
                    fg_ = it_ if not isinstance(it_, str) else (getattr(self, '_cut_src', None) or {}).get(it_); g_ = str((self.file(int(fg_)) or {}).get('grade') or '') if fg_ else ''
                    pre_ = {'date': time.strftime('%Y%m%d_'), 'grade': (g_ + '_') if g_ else '', 'both': time.strftime('%Y%m%d_') + ((g_ + '_') if g_ else '')}.get(cn_, '')
                    if pre_ and not nm_.startswith(pre_): nm_ = pre_ + nm_
                out = os.path.join(dst, nm_); C['cur'] = os.path.basename(src); C['pct'] = 0
                try:
                    if not os.path.isfile(src): raise FileNotFoundError('原檔不在（硬碟沒接上？）')
                    if os.path.isfile(out) and os.path.getsize(out) == os.path.getsize(src): C['skip'] += 1; continue
                    try:                                                          # V0.3.52 目的地空間不夠（留 2 GB）就先停，排隊留著
                        if shutil.disk_usage(os.path.dirname(out) if os.path.isdir(os.path.dirname(out)) else dst).free < os.path.getsize(src) + 2e9:
                            C['err'] = f'上傳資料夾那顆空間不夠（{os.path.basename(src)} 要 {fmt_b(os.path.getsize(src))}）'; Q.insert(0, it_); self._cq_save(); self._cpause = True
                            self.log.w('📤 ' + C['err'] + '：先暫停'); break
                    except Exception: pass
                    os.makedirs(dst, exist_ok=True); tmp = out + '.vscopy'; tot = max(1, os.path.getsize(src)); done = 0; win = [(time.time(), 0)]
                    with open(src, 'rb', buffering=0) as fi, open(tmp, 'wb', buffering=0) as fo:
                        while not self.stop_all:
                            if self.bg_pause.get('move') or getattr(self, '_cpause', False): time.sleep(1); win = [(time.time(), done)]; continue
                            b = fi.read(4 << 20)
                            if not b: break
                            fo.write(b); done += len(b); C['pct'] = int(done * 100 / tot)
                            lim = float(L.get('copy_mbps') or 60) * 1e6
                            if float(self.perf.cpu or 0) >= float(self.cfg.get('cpu_max') or 90): lim *= 0.5      # 電腦忙（TikLive）就放慢一半
                            now = time.time(); win.append((now, done)); win = win[-30:]; C['speed'] = (win[-1][1] - win[0][1]) / max(0.2, win[-1][0] - win[0][0])
                            ahead = (win[-1][1] - win[0][1]) / lim - (now - win[0][0])
                            if ahead > 0: time.sleep(min(ahead, 2.0))
                        os.fsync(fo.fileno())
                    if self.stop_all: os.remove(tmp); break
                    if os.path.getsize(tmp) != os.path.getsize(src): os.remove(tmp); raise IOError('複製後大小不一樣')
                    shutil.copystat(src, tmp); os.replace(tmp, out); C['done'] += 1; self.log.w(f'📤 複製到上傳資料夾：{os.path.basename(src)}')
                    try:                                                          # V0.3.56 記在影片上（跟著硬碟紀錄包走，換電腦也知道傳過了）
                        f_up = it_ if not isinstance(it_, str) else (getattr(self, '_cut_src', None) or {}).get(it_)
                        if f_up: self.db.x('UPDATE files SET up_t=? WHERE id=?', (time.time(), int(f_up))); self._upl_c = self._upg_c = None; self._unp_c = None
                    except Exception: pass
                    try: self.oplog('upcopy', src=src, dst=out, fid=(it_ if not isinstance(it_, str) else (getattr(self, '_cut_src', None) or {}).get(it_)), name=os.path.basename(src), size=os.path.getsize(out), detail='📤 複製到上傳資料夾')   # V0.3.54
                    except Exception: pass
                    try:                                                                # V0.3.44 📋 一起放上傳文案 .txt（同名）
                        fid0 = it_ if not isinstance(it_, str) else (getattr(self, '_cut_src', None) or {}).get(it_)
                        if L.get('caption') and L.get('copy_caption') and fid0:
                            Path(out).with_suffix('.txt').write_text(self.caption_for(int(fid0)), encoding='utf-8')
                    except Exception: pass
                    tg = str(L.get('copy_tag') or '')                                    # V0.2.74 複製好自動貼顏色標籤
                    fid_ = it_ if not isinstance(it_, str) else (getattr(self, '_cut_src', None) or {}).get(it_)
                    if tg and fid_:
                        try: self.set_flags([int(fid_)], _stamp=False, tag=tg)
                        except Exception: pass
                except Exception as e:
                    C['fail'] += 1; C['err'] = f'{os.path.basename(src)}：{e}'; self.log.w(f'📤 複製失敗 {C["err"]}')
                    try: os.remove(out + '.vscopy')
                    except Exception: pass
        finally:
            C['run'] = False; C['cur'] = ''; C['pct'] = 0

    def month_stats(self):
        """V0.2.47 📅 依月份：每個月（檔案修改時間）幾部、多大、分級了多少."""
        out = []
        for r in self.db.q("SELECT strftime('%Y-%m', mtime, 'unixepoch', 'localtime') ym, grade g, COUNT(*) n, COALESCE(SUM(size),0) b FROM files WHERE missing=0 AND mtime>0 GROUP BY ym, g ORDER BY ym DESC"):
            if not r['ym']: continue
            if not out or out[-1]['ym'] != r['ym']: out.append({'ym': r['ym'], 'n': 0, 'bytes': 0, 'graded': 0, 'S': 0, 'A': 0, 'E': 0, 'F': 0})
            o = out[-1]; o['n'] += r['n']; o['bytes'] += r['b']
            if r['g'] in ('S', 'A', 'E', 'F'): o[r['g']] += r['n']; o['graded'] += r['n']
        return out

    def free_track(self):
        """V0.2.91 📉 每顆硬碟每天記一次剩多少（最多 60 天），看空間掉多快、大約幾天會滿（TikLive 一直錄的話很有用）."""
        if not (self.cfg.get('lab') or {}).get('space_map') or not IS_WIN: return
        day = time.strftime('%Y-%m-%d'); H = dict(self.cfg.get('free_hist') or {}); ch = False
        try: letters = sorted(set(self.vol_letters().values()))
        except Exception: letters = []
        for X in letters:
            try: f = shutil.disk_usage(X + ':\\').free
            except Exception: continue
            L = [x for x in (H.get(X) or []) if isinstance(x, list) and len(x) == 2]
            if L and L[-1][0] == day: L[-1][1] = f
            else: L.append([day, f])
            H[X] = L[-60:]; ch = True
        if ch: self.cfg.set('free_hist', H)

    @staticmethod
    def free_trend(L):
        """[[日期, 剩下 bytes]] → (每天少多少 bytes（負的＝在變多）, 照這速度幾天滿 或 None)；看最近 14 天."""
        L = [x for x in (L or []) if isinstance(x, list) and len(x) == 2][-14:]
        if len(L) < 3: return None, None
        import datetime as _dt
        d0 = _dt.date.fromisoformat(L[0][0]); d1 = _dt.date.fromisoformat(L[-1][0]); n = max(1, (d1 - d0).days)
        per = (float(L[0][1]) - float(L[-1][1])) / n
        return per, (round(float(L[-1][1]) / per, 1) if per > 1e8 else None)

    def space_map(self):
        """V0.2.43 💽 硬碟空間地圖：每顆硬碟 總量／剩下／影片庫裡 S A E F 未分級 各佔多少、待刪（F）能空出多少."""
        out = {}
        for r in self.db.q("SELECT upper(substr(path,1,1)) d, grade g, COUNT(*) n, COALESCE(SUM(size),0) b FROM files WHERE missing=0 AND substr(path,2,1)=':' GROUP BY d, g"):
            d = r['d']
            if not ('A' <= d <= 'Z'): continue
            o = out.setdefault(d, {'d': d, 'n': 0, 'lib': 0, 'S': 0, 'A': 0, 'E': 0, 'F': 0, '': 0, 'nS': 0, 'nA': 0, 'nE': 0, 'nF': 0})
            g = r['g'] if r['g'] in ('S', 'A', 'E', 'F') else ''; o[g] += r['b']; o['lib'] += r['b']; o['n'] += r['n']
            if g: o['n' + g] += r['n']
        try: DV = list(self.disks_view() or [])
        except Exception: DV = []
        for d, o in out.items():
            try: u = shutil.disk_usage(d + ':\\'); o['total'], o['free'] = u.total, u.free
            except Exception: o['total'], o['free'] = 0, 0
            try: o['label'] = next((x.get('label') or '' for x in DV if str(x.get('label') or '').upper().startswith(d)), '')
            except Exception: o['label'] = ''
            o['other'] = max(0, o['total'] - o['free'] - o['lib']) if o['total'] else 0
            try: per, dfull = self.free_trend((self.cfg.get('free_hist') or {}).get(d)); o['per_day'] = per; o['days_full'] = dfull   # V0.2.91 📉
            except Exception: o['per_day'] = o['days_full'] = None
        return sorted(out.values(), key=lambda x: x['d'])

    HIST_K = {'arch': '📦 歸檔', 'trash': '🗑 移到待刪', 'fav': '⭐ 收藏', 'delete': '❌ 刪除原檔', 'cut': '✂ 初剪', 'conv': '🔁 轉檔', 'undo': '↩ 復原', 'migrate': '📁 搬家',
              'exclude': '🚫 排除', 'cat': '🏷 分類', 'snap': '📷 截圖', 'clean': '🧹 清理', 'purge': '🔥 清空待刪', 'upcopy': '📤 複製到上傳'}

    def file_history(self, fid):
        """V0.2.98 📜 這部影片的紀錄：搬移／歸檔／剪輯／轉檔／分級／看過／書籤（新的在上面）→ [{'t','what','detail'}]."""
        f = self.file(fid)
        if not f: return []
        H = []
        try:
            for r in self.db.q('SELECT t,kind,name,src,dst,size,detail,ok,undone FROM oplog WHERE fid=? ORDER BY t DESC LIMIT 200', (int(fid),)):
                k = str(r['kind'] or ''); nm = self.HIST_K.get(k.split(':')[0], k)
                d = ' → '.join(x for x in (os.path.dirname(str(r['src'] or '')), os.path.dirname(str(r['dst'] or ''))) if x) or str(r['detail'] or '')
                H.append({'t': float(r['t'] or 0), 'what': nm + ('（失敗）' if not r['ok'] else '') + ('（已復原）' if r['undone'] else ''), 'detail': d})
        except Exception: pass
        try:
            for r in self.db.q('SELECT t,a,b,out,state FROM cuts WHERE file_id=? ORDER BY t DESC LIMIT 100', (int(fid),)):
                H.append({'t': float(r['t'] or 0), 'what': '✂ 剪了一段' + ('' if r['state'] == 1 else '（失敗）' if r['state'] == 2 else '（處理中）'), 'detail': f"{fmt_t(r['a'] or 0)}～{fmt_t(r['b'] or 0)}　{os.path.basename(str(r['out'] or ''))}"})
        except Exception: pass
        if f.get('grade_t'): H.append({'t': float(f['grade_t']), 'what': f"🏷 分級 {f.get('grade') or '取消'}", 'detail': '最後一次改分級'})
        if f.get('viewed'): H.append({'t': float(f['viewed']), 'what': '👁 看過', 'detail': '最後一次看'})
        if f.get('cv_t'): H.append({'t': float(f['cv_t']), 'what': '🔁 轉檔完成', 'detail': ''})
        if f.get('th_t'): H.append({'t': float(f['th_t']), 'what': '🖼 預覽圖做好', 'detail': f"{f.get('th_n') or 0} 張"})
        if f.get('seen'): H.append({'t': float(f['seen']), 'what': '🔎 掃描到', 'detail': ''})
        for t, n in self.bm_list(fid): H.append({'t': 0, 'what': f'🔖 書籤 {fmt_t(t)}', 'detail': n})
        return sorted([h for h in H if h['t'] > 0], key=lambda x: -x['t']) + [h for h in H if not h['t']]

    def snap_at(self, fid, t):
        """V0.3.34 📷 手機截圖：這部在 t 秒那一格存成原尺寸 JPG 到 X:\\VideoSIFT\\截圖（跟電腦播放器 Ctrl+E 一樣的位置）."""
        f = self.file(fid)
        if not f or not self.ff: return False, '找不到這部或沒有 ffmpeg'
        src = Path(f['path'])
        if not src.is_file(): return False, '原檔不在（硬碟沒接上？）'
        try:
            d = Path(src.anchor or src.parent) / ARCH_BASE / '截圖'; d.mkdir(parents=True, exist_ok=True)
            out = unique_path(d / f'{safe_name(src.stem)[:60]}_{fmt_t(float(t)).replace(":", "")}.jpg')
            p = subprocess.run([self.ff, '-hide_banner', '-loglevel', 'error', '-nostdin', '-ss', f'{max(0.0, float(t)):.3f}', '-i', str(src), '-frames:v', '1', '-q:v', '2', '-y', str(out)],
                               capture_output=True, timeout=60, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
            if p.returncode or not out.is_file(): return False, '截不到這一格'
            self.oplog('snap', src=str(src), dst=str(out), detail=f'📱 截圖 {fmt_t(float(t))}'); return True, f'📷 存到 {out}'
        except Exception as e: return False, f'截圖失敗：{e}'

    def caption_for(self, fid, n=1):
        """V0.3.43 📋 上傳文案：照範本（{作者} {檔名} {日期} {分級} {備註} {長度} {#作者}）組一段文字。V0.4.20 n=2＝第二組範本（例如給 IG／YouTube）."""
        f = self.file(fid)
        if not f: return ''
        L_ = self.cfg.get('lab') or {}
        tpl = str((L_.get('caption_tpl2') if int(n or 1) == 2 and str(L_.get('caption_tpl2') or '').strip() else L_.get('caption_tpl')) or '{作者} {日期}\n{備註}\n#直播 #精華')
        V = {'作者': self.creator_key(f['name']) if self.creator_key(f['name']) != '（其他）' else '', '檔名': Path(f['name']).stem, '日期': time.strftime('%Y/%m/%d', time.localtime(float(f.get('mtime') or 0))) if f.get('mtime') else '',
             '分級': f.get('grade') or '', '備註': f.get('note') or '', '長度': fmt_t(float(f.get('dur') or 0))}
        V['#作者'] = ('#' + re.sub(r'\s+', '', V['作者'])) if V['作者'] else ''
        out = tpl
        for k, v in V.items(): out = out.replace('{' + k + '}', str(v))
        return '\n'.join(ln.rstrip() for ln in out.replace('\\n', '\n').splitlines() if ln.strip())

    def bm_list(self, fid):
        """V0.2.41 🔖 時間書籤：[[秒, 說明], …]（存在 files.bmk，跟著硬碟包走）."""
        try:
            r = self.db.one('SELECT bmk FROM files WHERE id=?', (int(fid),)); L = json.loads(r[0]) if r and r[0] else []
            return sorted([[float(x[0]), str(x[1] if len(x) > 1 else '')] for x in L if isinstance(x, (list, tuple)) and x], key=lambda x: x[0])
        except Exception: return []

    def bm_all(self, limit=800):
        """V0.4.16 🔖 所有影片的時間書籤一次列出：[{'id', 'name', 'grade', 't', 'note'}]（最近分級／加入的在前）."""
        out = []
        try:
            for r in self.db.q("SELECT id,name,grade,bmk FROM files WHERE bmk!='' AND bmk!='[]' AND missing=0 ORDER BY grade_t DESC, id DESC LIMIT 2000"):
                try: L = json.loads(r['bmk'] or '[]')
                except Exception: continue
                for x in sorted([x for x in L if isinstance(x, (list, tuple)) and x], key=lambda x: float(x[0])):
                    out.append({'id': int(r['id']), 'name': r['name'], 'grade': r['grade'] or '', 't': float(x[0]), 'note': str(x[1] if len(x) > 1 else '')})
                    if len(out) >= limit: return out
        except Exception: self.log.err('全部書籤')
        return out

    def bm_clip(self, fid, t, before=5, after=10):
        """V0.4.17 ✂ 從書籤剪一段：書籤前 N 秒到後 M 秒（照一般初剪排隊，剪好的檔照樣留著）."""
        f = self.file(int(fid)) or {}; dur = float(f.get('dur') or 0); a = max(0.0, float(t) - float(before)); b = float(t) + float(after)
        if dur > 0: b = min(dur, b)
        return self.cut_add(int(fid), [(a, b)], merge=False)

    def bm_add(self, fid, t, note=''):
        t = round(max(0.0, float(t or 0)), 1); L = [x for x in self.bm_list(fid) if abs(x[0] - t) >= 0.5] + [[t, str(note or '')[:80]]]
        L = sorted(L, key=lambda x: x[0])[-200:]; self.db.x('UPDATE files SET bmk=? WHERE id=?', (json.dumps(L, ensure_ascii=False), int(fid))); return L

    def bm_del(self, fid, t):
        L = [x for x in self.bm_list(fid) if abs(x[0] - float(t or 0)) >= 0.05]; self.db.x('UPDATE files SET bmk=? WHERE id=?', (json.dumps(L, ensure_ascii=False) if L else '', int(fid))); return L

    def _rule_where(self, R):
        """V0.2.60 ⚡ 規則分級：只看「還沒分級、沒歸檔、在」的；條件都要符合（沒填的不管）."""
        w = ["missing=0", "grade=''", "arch=''", "probed=1", "cut_n=0", "fav=0", "bmk=''"]; a = []        # V0.3.26 剪過、收藏、有書籤的＝你有在注意的，規則不動
        try:
            if float(R.get('dur_lt') or 0) > 0: w.append('dur>0 AND dur<?'); a.append(float(R['dur_lt']))
            if float(R.get('dur_gt') or 0) > 0: w.append('dur>?'); a.append(float(R['dur_gt']))
            if int(R.get('h_lt') or 0) > 0: w.append('h>0 AND h<?'); a.append(int(R['h_lt']))
            if float(R.get('size_lt') or 0) > 0: w.append('size<?'); a.append(float(R['size_lt']) * 1e6)
        except Exception: pass
        try:
            if float(R.get('still_gt') or 0) > 0: w.append('still>=?'); a.append(float(R['still_gt']) / 100.0)   # V0.3.12 😴 靜止超過幾 %
        except Exception: pass
        if str(R.get('name') or '').strip(): w.append('name LIKE ?'); a.append('%' + str(R['name']).strip() + '%')
        f = str(R.get('folder') or '').strip()
        if f: w.append('(folder=? OR folder LIKE ?)'); a += [f, f.rstrip('\\/') + os.sep + '%']
        return w, a

    def rule_preview(self, R):
        w, a = self._rule_where(R)
        if len(w) <= 7: return {'n': 0, 'bytes': 0, 'sample': [], 'message': '至少要設一個條件'}
        r = self.db.one(f"SELECT COUNT(*), COALESCE(SUM(size),0) FROM files WHERE {' AND '.join(w)}", a)
        S = [dict(x) for x in self.db.q(f"SELECT id,name,dur,h,size FROM files WHERE {' AND '.join(w)} ORDER BY dur LIMIT 12", a)]
        return {'n': int(r[0] or 0), 'bytes': int(r[1] or 0), 'sample': S, 'message': ''}

    def rule_apply(self, R):
        g = str(R.get('grade') or '')
        if g not in ('S', 'A', 'E', 'F'): return 0, '要選分級'
        w, a = self._rule_where(R)
        if len(w) <= 7: return 0, '至少要設一個條件'
        ids = [r[0] for r in self.db.q(f"SELECT id FROM files WHERE {' AND '.join(w)}", a)]
        if not ids: return 0, '沒有符合的'
        self.set_flags(ids, _stamp=False, grade=g); self.cfg.set('rule_last', {'ids': ids[:200000], 'grade': g, 't': time.time()})
        self.log.w(f'⚡ 規則分級：{len(ids)} 部 → {g}（條件 {R}）'); return len(ids), f'⚡ {len(ids):,} 部 → {g}'

    def rule_undo(self):
        L = self.cfg.get('rule_last') or {}; ids = [int(i) for i in L.get('ids') or []]
        if not ids: return 0, '沒有可以復原的'
        keep = []                                                               # 只改回「還是規則給的那個分級」的（之後你自己改過的不動）
        for k in range(0, len(ids), 900):
            ch = ids[k:k + 900]; keep += [r[0] for r in self.db.q(f"SELECT id FROM files WHERE grade=? AND grade_t=0 AND id IN ({','.join('?' * len(ch))})", [L.get('grade')] + ch)]
        ids = keep
        self.set_flags(ids, _stamp=False, grade=''); self.cfg.set('rule_last', {}); self.log.w(f'⚡ 規則分級復原：{len(ids)} 部改回未分級'); return len(ids), f'↩ {len(ids):,} 部改回未分級'

    def new_selfcheck(self):
        """V0.2.73 🩺 新功能自我檢查：資料庫欄位／索引、設定格式、上傳資料夾、背景工作狀態 → [(ok, 文字)]."""
        R = []; L = self.cfg.get('lab') or {}
        def add(ok, t): R.append((bool(ok), t))
        try:
            cols = {r[1] for r in self.db.q('PRAGMA table_info(files)')}
            add('bmk' in cols, '資料庫有 🔖 書籤欄位（bmk）'); add('grade_t' in cols, '資料庫有分級時間欄位（grade_t）')
            add(bool(self.db.one("SELECT name FROM sqlite_master WHERE name='ix_files_gt'")), '分級時間有索引（報表、目標查得快）')
        except Exception as e: add(False, f'資料庫讀不到：{e}')
        for k, nm in (('saved_views', '⭐ 常用篩選'), ('recent_dirs', '🕘 最近資料夾'), ('search_hist', '🔎 搜尋紀錄')):
            v = self.cfg.get(k); add(v is None or isinstance(v, list), f'{nm} 設定格式正常（{len(v) if isinstance(v, list) else 0} 筆）')
        add(isinstance(L, dict), f'實驗開關格式正常（打開了 {sum(1 for v in L.values() if v is True)} 個）')
        if L.get('copy_to'):
            d = str(L.get('copy_dir') or '')
            add(bool(d), '📤 上傳資料夾有設定' + (f'：{d}' if d else '（還沒設定）'))
            if d: add(os.path.isdir(d) or os.path.isdir(os.path.dirname(d.rstrip('\\/')) or d), f'📤 上傳資料夾（或它的上一層）存在：{d}')
            C = self.copy_view(); add(not (C['q'] and not C['run']), f"📤 複製佇列：還有 {C['q']} 部、{'複製中' if C['run'] else '沒在跑'}")
            try:                                                                # V0.3.79 上傳相關的新欄位、目前那顆接著沒、還有沒有空間
                cols_ = {r[1] for r in self.db.q('PRAGMA table_info(files)')}; add('up_t' in cols_, '資料庫有 📤 已上傳欄位（up_t）'); add('pub_t' in cols_, '資料庫有 ✅ 已發佈欄位（pub_t）')
                dd = self.copy_dest(); add(bool(dd), '📤 上傳資料夾那顆硬碟接著' + (f'：{dd}' if dd else '（沒接上：排隊的會等它接回來）'))
                if dd and os.path.isdir(dd): fr = shutil.disk_usage(dd).free; add(fr > 2e9, f'📤 上傳資料夾還有 {fmt_b(fr)} 空間（剩 2 GB 會自動暫停）')
                ug = int(L.get('up_goal') or 0); add(0 <= ug <= 200, f'📤 每天上傳目標：{ug or "沒設"}')
            except Exception as e: add(False, f'📤 上傳檢查失敗：{e}')
        try:                                                                    # V0.3.96 ⚠ 讀不了的檔：哪顆硬碟比較多（硬碟可能要換了）
            B_ = {}
            for r in self.db.q("SELECT substr(path,1,2) d, COUNT(*) n FROM files WHERE missing=0 AND (th_state=3 OR probe_err!='') GROUP BY d"): B_[r['d']] = int(r['n'])
            tb_ = sum(B_.values()); add(tb_ < 50, f'⚠ 讀不了／可能壞掉的檔 {tb_:,} 部' + ('：' + '、'.join(f'{k} {v}' for k, v in sorted(B_.items(), key=lambda x: -x[1])[:5]) if B_ else '') + ('（篩選「⚠ 讀不了」看是哪些）' if tb_ else ''))
        except Exception: pass
        if L.get('sprint'):                                                     # V0.3.79 ⏱ 衝刺
            S_ = self.cfg.get('sprint') or {}; add(not S_ or isinstance(S_.get('t0'), (int, float)), '⏱ 分級衝刺：' + ('衝刺中' if S_.get('t0') and not S_.get('saved') else '沒在衝刺') + f"・歷史 {len(self.cfg.get('sprint_hist') or [])} 次")
        if L.get('proc_guard'):
            n = str(L.get('proc_names') or ''); add(bool(n.strip()), f'🎥 讓路程式名稱：{n or "（空的）"}')
            add(not any(x in n.lower() for x in ('tiklive',)), '🎥 讓路名單裡沒有 24 小時開著的 TikLive（有的話轉檔永遠不會做）')
        if L.get('auto_scan'):
            st = getattr(self, '_as', None) or {}; add(True, f"👀 自動找新影片：每 {int(L.get('auto_scan_min') or 30)} 分鐘，上次 {time.strftime('%H:%M', time.localtime(st['last_t'])) if st.get('last_t') else '還沒跑過'}")
        if L.get('bg_sched'):
            S = L.get('sched') or {}; bad = [k for k, v in S.items() if isinstance(v, dict) and v.get('on') and int(v.get('from', 0)) == int(v.get('to', 0))]
            add(not bad, '🕑 背景工作時段：' + ('、'.join(f'{k} 開始＝結束（等於整天都做）' for k in bad) if bad else '設定正常'))
        try:
            M = self.cfg.get('disk_move') or {}; add(M.get('state') not in ('run',) or self._mv().get('run'), f"🚚 搬硬碟狀態：{M.get('state') or '沒有'}")
        except Exception: pass
        try:
            V = self.vol_letters(); P = [X for X in V.values() if self._pack_json(X)]
            add(True, f'💾 接著的硬碟 {len(V)} 顆，有紀錄包的 {len(P)} 顆：' + ('、'.join(sorted(P)) or '—'))
        except Exception: pass
        return R

    SHARE_KEYS = ('auto_rules', 'saved_views', 'search_hist', 'daily_goal_n')
    LAB_LOCAL = ('copy_dir', 'copy_dir_vol', 'proc_names', 'proc_kinds')                # 跟這台電腦有關的不帶

    def share_export(self):
        """V0.3.29 🔄 新功能設定存到每顆接著的硬碟（X:\\VideoSIFT\\.vsdata\\global\\new_features.json），另一台接上就能讀."""
        L = {k: v for k, v in (self.cfg.get('lab') or {}).items() if k not in self.LAB_LOCAL}
        J = {'v': 1, 't': time.time(), 'pc_name': self.pc_name(), 'pc_uid': self.pc_uid(), 'app': self.version, 'lab': L, **{k: self.cfg.get(k) for k in self.SHARE_KEYS}}
        out = []
        try: letters = sorted(set(self.vol_letters().values()))
        except Exception: letters = []
        for X in letters:
            try:
                d = self.pack_dir(X)
                if not d.is_dir(): continue
                g = d / 'global'; g.mkdir(exist_ok=True); tmp = g / 'new_features.tmp'
                tmp.write_text(json.dumps(J, ensure_ascii=False, indent=1), encoding='utf-8'); os.replace(str(tmp), str(g / 'new_features.json')); out.append(X)
            except Exception: pass
        self.log.w(f'🔄 新功能設定存到：{"、".join(out) or "（沒有有紀錄包的硬碟）"}'); return out

    def share_list(self):
        """接著的硬碟上別台電腦存的新功能設定 → [{'d','pc_name','t','app','n_on','mine'}]."""
        out = []
        try: letters = sorted(set(self.vol_letters().values()))
        except Exception: letters = []
        for X in letters:
            try:
                f = self.pack_dir(X) / 'global' / 'new_features.json'
                if not f.is_file(): continue
                J = json.loads(f.read_text(encoding='utf-8'))
                out.append({'d': X, 'pc_name': J.get('pc_name') or '', 't': float(J.get('t') or 0), 'app': J.get('app') or '', 'n_on': sum(1 for v in (J.get('lab') or {}).values() if v is True), 'mine': J.get('pc_uid') == self.pc_uid()})
            except Exception: pass
        return sorted(out, key=lambda x: -x['t'])

    def share_newer(self):
        """V0.3.30 硬碟上有「另一台」存的、而且比這台上次套用／存的還新的新功能設定 → 那一份（沒有＝None）."""
        mine_t = max(float(self.cfg.get('share_t') or 0), float(getattr(self, '_sx_t', 0) or 0))
        L = [x for x in self.share_list() if not x['mine'] and x['t'] > mine_t + 60]
        return L[0] if L else None

    def share_import(self, X):
        try: J = json.loads((self.pack_dir(X) / 'global' / 'new_features.json').read_text(encoding='utf-8'))
        except Exception: return False, '讀不到'
        L = dict(self.cfg.get('lab') or {}); keep = {k: L.get(k) for k in self.LAB_LOCAL if k in L}
        L.update({k: v for k, v in (J.get('lab') or {}).items() if k not in self.LAB_LOCAL}); L.update(keep); self.cfg.set('lab', L)
        for k in self.SHARE_KEYS:
            if J.get(k) is not None: self.cfg.set(k, J[k])
        self.cfg.set('share_t', float(J.get('t') or time.time())); self.log.w(f'🔄 套用 {J.get("pc_name")} 的新功能設定（{X}:）'); return True, f'🔄 套用了「{J.get("pc_name") or "另一台"}」的新功能設定'

    def auto_rules(self):
        """V0.3.21 ⚡ 自動規則：存起來的規則，每分鐘對「還沒分級」的自動套用一次（新進來的影片也會被分）."""
        R = self.cfg.get('auto_rules')
        return [x for x in R if isinstance(x, dict) and x.get('grade') in ('S', 'A', 'E', 'F')] if isinstance(R, list) else []

    def auto_rule_add(self, R):
        R = dict(R or {}); R.pop('folder', None) if not R.get('folder') else None
        w, _a = self._rule_where(R)
        if len(w) <= 7 or R.get('grade') not in ('S', 'A', 'E', 'F'): return False, '至少要設一個條件，也要選分級'
        L = self.auto_rules(); R['t'] = time.time(); L.append(R); self.cfg.set('auto_rules', L[-10:]); self.log.w(f'⚡ 新增自動規則：{R}'); return True, f'⚡ 存成自動規則（共 {len(L[-10:])} 條）'

    def auto_rule_del(self, i):
        L = self.auto_rules()
        if 0 <= int(i) < len(L): x = L.pop(int(i)); self.cfg.set('auto_rules', L); self.log.w(f'⚡ 刪除自動規則：{x}'); return True
        return False

    def auto_rule_undo(self, hours=24):
        """V0.3.27 ↩ 復原最近 N 小時自動規則分的（之後你自己改過的不動）."""
        H = list(self.cfg.get('auto_rule_log') or []); t0 = time.time() - hours * 3600; keep = []; n = 0
        for h in H:
            if float(h.get('t') or 0) < t0: keep.append(h); continue
            ids = [int(i) for i in h.get('ids') or []]
            for k in range(0, len(ids), 900):
                ch = ids[k:k + 900]; back = [r[0] for r in self.db.q(f"SELECT id FROM files WHERE grade=? AND grade_t=0 AND id IN ({','.join('?' * len(ch))})", [h.get('grade')] + ch)]
                if back: self.set_flags(back, _stamp=False, grade=''); n += len(back)
        self.cfg.set('auto_rule_log', keep); self.log.w(f'⚡ 復原自動規則：{n} 部改回未分級'); return n, f'↩ {n:,} 部改回未分級'

    def auto_rules_tick(self):
        """每分鐘：每條自動規則對還沒分級的套用（不算進今天的分級數；記 LOG）."""
        if not (self.cfg.get('lab') or {}).get('rules'): return 0
        tot = 0
        for R in self.auto_rules():
            try:
                w, a = self._rule_where(R)
                if len(w) <= 7: continue
                ids = [r[0] for r in self.db.q(f"SELECT id FROM files WHERE {' AND '.join(w)} LIMIT 5000", a)]
                if ids:
                    self.set_flags(ids, _stamp=False, grade=R['grade']); tot += len(ids); self.log.w(f'⚡ 自動規則：{len(ids)} 部 → {R["grade"]}（{R}）')
                    H = list(self.cfg.get('auto_rule_log') or []); H.append({'t': time.time(), 'grade': R['grade'], 'ids': ids}); self.cfg.set('auto_rule_log', H[-30:])   # V0.3.27 可以復原
            except Exception: self.log.err('自動規則')
        if tot: self._ar_last = {'t': time.time(), 'n': tot}                        # V0.3.31 手機提醒用
        return tot

    def auto_scan_tick(self):
        """V0.2.58 👀 自動找新影片：每隔 N 分鐘（預設 30）重新掃描影片庫一次，TikLive 新錄的影片自動出現；搬硬碟中、正在掃描就先不做."""
        L = self.cfg.get('lab') or {}; st = self._as = getattr(self, '_as', None) or {'t': time.time(), 'run': False, 'last_new': 0, 'last_t': 0}
        if st['run'] and not self.scan_st.get('running'):
            st['run'] = False; st['last_t'] = time.time(); n = int(self.scan_st.get('new') or 0); st['last_new'] = n
            if n: self.log.w(f'👀 自動找新影片：多了 {n} 部')
        if not L.get('auto_scan') or self.scan_st.get('running'): return st
        try:
            if self._mv().get('run'): return st
        except Exception: pass
        if time.time() - st['t'] < max(5, int(L.get('auto_scan_min') or 30)) * 60: return st
        st['t'] = time.time()
        if self.scan(): st['run'] = True
        return st

    def grade_guess(self, fid):
        """V0.2.62 🤖 分級建議：同一個作者／主播（從檔名猜）你以前分過的，大多是哪一級 → {'g','n','of','why'}；資料不夠就 None."""
        if not (self.cfg.get('lab') or {}).get('guess'): return None
        f = self.file(fid)
        if not f or f.get('grade'): return None
        c = getattr(self, '_gg_c', None)
        if (not c or time.time() - c[0] > 300) and not getattr(self, '_gg_run', False):   # 5 分鐘重算一次（背景算，不卡畫面；V0.2.63）
            def work():
                try:
                    D = {}; FD = {}
                    for r in self.db.q("SELECT name, folder, grade FROM files WHERE missing=0 AND grade IN ('S','A','E','F')"):
                        k = self.creator_key(r['name']); D.setdefault(k, {}); D[k][r['grade']] = D[k].get(r['grade'], 0) + 1
                        FD.setdefault(r['folder'], {}); FD[r['folder']][r['grade']] = FD[r['folder']].get(r['grade'], 0) + 1   # V0.2.85 同資料夾也算
                    self._gg_c = (time.time(), D); self._gg_f = FD
                except Exception: self.log.err('分級建議')
                finally: self._gg_run = False
            self._gg_run = True; threading.Thread(target=work, daemon=True, name='guess').start()   # 第一次算好之前先不猜
        if not c: return None
        k = self.creator_key(f['name'])
        if k and k != '（其他）':
            G = c[1].get(k) or {}; tot = sum(G.values())
            if tot >= 5:
                g, n = max(G.items(), key=lambda x: x[1])
                if n / tot >= 0.6: return {'g': g, 'n': n, 'of': tot, 'who': k, 'why': f'「{k}」你分過 {tot} 部，{n} 部是 {g}'}
        G = (getattr(self, '_gg_f', None) or {}).get(f.get('folder')) or {}; tot = sum(G.values())          # 作者看不出來 → 看同一個資料夾（要更明顯才猜）
        if tot >= 8:
            g, n = max(G.items(), key=lambda x: x[1])
            if n / tot >= 0.7: return {'g': g, 'n': n, 'of': tot, 'who': os.path.basename(str(f.get('folder') or '')), 'why': f'這個資料夾你分過 {tot} 部，{n} 部是 {g}'}
        sv = float(f.get('still') if f.get('still') is not None else -1)                       # V0.3.50 都看不出來 → 看 😴 靜止比例
        if sv >= 0.8: return {'g': 'F', 'n': 0, 'of': 0, 'who': '', 'why': f'{round(sv * 100)}% 都是靜止／黑畫面'}
        return None

    def recent_push(self, folder):
        """V0.2.56 🕘 最近開過的資料夾（電腦、手機共用，最多 15 個）."""
        f = str(folder or '').strip()
        if not f or not (self.cfg.get('lab') or {}).get('recent_dirs'): return
        R = [x for x in (self.cfg.get('recent_dirs') or []) if isinstance(x, str) and x != f]
        R.insert(0, f); self.cfg.set('recent_dirs', R[:15])
        M = {k: v for k, v in (self.cfg.get('recent_vol') or {}).items() if k in R[:15]}; sn = self.path_vol(f)
        if sn: M[f] = sn
        self.cfg.set('recent_vol', M)

    def search_push(self, q):
        """V0.2.65 🔎 搜尋紀錄（電腦、手機共用，最多 20 個）."""
        q = str(q or '').strip()[:80]
        if len(q) < 2 or not (self.cfg.get('lab') or {}).get('search_hist'): return
        H = [x for x in (self.cfg.get('search_hist') or []) if isinstance(x, str) and x != q]; H.insert(0, q); self.cfg.set('search_hist', H[:20])

    def search_hist(self):
        return [x for x in (self.cfg.get('search_hist') or []) if isinstance(x, str)]

    def last_file_set(self, fid):
        """V0.3.38 ⏯ 最後看的那一部（電腦、手機共用；🕘 最近資料夾 打開才記）."""
        if (self.cfg.get('lab') or {}).get('recent_dirs'):
            try: self.cfg.set('last_file', {'id': int(fid), 't': time.time()})
            except Exception: pass

    def last_file(self):
        L = self.cfg.get('last_file') or {}
        f = self.file(int(L.get('id') or 0)) if L.get('id') else None
        return {'id': f['id'], 'name': f['name'], 'folder': f['folder'], 't': L.get('t')} if f else None

    def recent_list(self):
        M = self.cfg.get('recent_vol') or {}
        return [self.path_fix(x, M.get(x)) for x in (self.cfg.get('recent_dirs') or []) if isinstance(x, str)]

    def path_vol(self, p):
        """V0.3.02 這個路徑在哪一顆硬碟（序號）；換電腦、換代號後用來找回來."""
        p = str(p or '')
        if len(p) < 2 or p[1] != ':': return ''
        try: return next((sn for sn, X in self.vol_letters_c().items() if X.upper() == p[0].upper()), '')
        except Exception: return ''

    def path_fix(self, p, sn):
        """硬碟代號變了（例如 K: 接到另一台變 F:）→ 換成現在的代號；找不到就原樣."""
        p = str(p or '')
        if not sn or len(p) < 2 or p[1] != ':': return p
        try:
            X = self.vol_letters_c().get(sn)
            return (X + p[1:]) if X and X.upper() != p[0].upper() else p
        except Exception: return p

    VIEW_KEYS = ('folder', 'flt', 'q', 'sort', 'sub', 'dur', 'res')

    def views(self):
        """V0.2.40 ⭐ 常用篩選（電腦、手機共用）. V0.3.02 硬碟換代號也找得到."""
        V = self.cfg.get('saved_views')
        out = [dict(v) for v in V if isinstance(v, dict) and v.get('name')] if isinstance(V, list) else []
        for v in out:
            if v.get('vol'): v['folder'] = self.path_fix(v.get('folder'), v['vol'])
        return out

    def view_save(self, name, view):
        name = str(name or '').strip()[:40]
        if not name: return False
        v = {k: view.get(k) for k in self.VIEW_KEYS}; v['sub'] = bool(v.get('sub', True)); v['name'] = name; v['t'] = time.time(); v['vol'] = self.path_vol(view.get('folder'))
        for k in ('folder', 'flt', 'q', 'sort', 'dur', 'res'): v[k] = str(v.get(k) or ('all' if k == 'flt' else 'name' if k == 'sort' else ''))
        V = [x for x in (self.cfg.get('saved_views') or []) if isinstance(x, dict) and x.get('name') and x.get('name') != name] + [v]; self.cfg.set('saved_views', V[-60:]); self.log.w(f'⭐ 存了常用篩選「{name}」'); return True

    def view_del(self, name):
        V = [x for x in (self.cfg.get('saved_views') or []) if isinstance(x, dict)]; W = [x for x in V if x.get('name') != name]; self.cfg.set('saved_views', W); return len(W) != len(V)

    @staticmethod
    def list_csv(rows):
        """V0.2.38 📤 把清單變成 CSV 文字（Excel 直接開：utf-8 BOM）."""
        import csv, io
        b = io.StringIO(); w = csv.writer(b)
        w.writerow(['檔名', '資料夾', '分級', '大小(MB)', '時長(秒)', '時長', '寬', '高', '編碼', '收藏', '剪了幾段', '看過', '標籤', '說明', '完整路徑'])
        for r in rows:
            d = r.get('dur') or 0
            w.writerow([r.get('name') or '', r.get('folder') or '', r.get('grade') or '', round((r.get('size') or 0) / 1e6, 1), round(d, 1),
                        '%d:%02d:%02d' % (d // 3600, d % 3600 // 60, d % 60) if d else '', r.get('w') or '', r.get('h') or '', r.get('vcodec') or '',
                        '★' if r.get('fav') else '', r.get('cut_n') or 0, '✔' if r.get('viewed') else '', r.get('tag') or '', (r.get('note') or '').replace('\n', ' '), r.get('path') or ''])
        return '\ufeff' + b.getvalue()

    def list_files(self, folder, sub=True, sort='name', flt='all', search='', dur='', res=''):
        w = ['missing=0']; a = []
        dw_ = DUR_BINS.get(str(dur or ''))                                       # V0.2.37 ⏱ 時長篩選
        if dw_: w.append(dw_)
        rw_ = RES_BINS.get(str(res or ''))                                       # V0.2.78 📺 畫質篩選（看短邊，直的影片也對）
        if rw_: w.append(rw_)
        if flt == 'archived': w.append("arch!=''")
        elif str(flt).startswith('arch:'): w.append('arch=?'); a.append(str(flt)[5:])
        else: w.append("arch=''")
        if folder:
            if sub:
                f = str(folder).rstrip('\\/'); w.append('(folder=? OR substr(folder,1,?)=? OR substr(folder,1,?)=?)'); a += [f, len(f) + 1, f + '\\', len(f) + 1, f + '/']
            else: w.append('folder=?'); a.append(str(folder))
        if flt == 'unseen': w.append('viewed=0')
        elif flt == 'fav': w.append('fav=1')
        elif flt == 'cut': w.append('cut_n>0')
        elif flt == 'nothumb': w.append('th_state!=2')
        elif flt == 'ready': w.append("th_state=2 AND grade=''")                # V0.1.94 ✅ 可以審：預覽圖好了、還沒分級
        elif flt == 'thumbok': w.append('th_state=2')
        elif flt in ('S', 'A', 'E', 'F'): w.append('grade=?'); a.append(flt)
        elif flt == 'nograde': w.append("grade=''")
        elif flt == 'tagany': w.append("tag!=''")
        elif str(flt).startswith('tag:'): w.append('tag=?'); a.append(str(flt)[4:])
        elif str(flt).startswith('month:'):                                     # V0.2.47 📅 依月份（檔案修改時間）
            t0_, t1_ = month_range(str(flt)[6:]); w.append('mtime>=? AND mtime<?'); a += [t0_, t1_]
        elif flt == 'noted': w.append("note!=''")
        elif flt == 'bmk': w.append("bmk!=''")                                  # V0.2.81 🔖 有書籤
        elif flt == 'still': w.append('still>=0.6')                             # V0.3.12 😴 大多是靜止的
        elif flt == 'uped': w.append("up_t>0")                                   # V0.3.55／0.3.56 📤 已經複製到上傳
        elif flt == 'notup': w.append("grade IN ('S','A') AND up_t<=0")             # S／A 但還沒上傳
        elif flt == 'notpub': w.append('up_t>0 AND pub_t<=0')                       # V0.4.21 ✅ 複製了、還沒發佈
        elif flt == 'pub': w.append('pub_t>0')
        elif flt == 'bad': w.append("(th_state=3 OR probe_err!='' OR th_err!='')")    # V0.3.95 ⚠ 讀不了／可能壞掉（預覽圖做不出來、讀不到影片資訊）
        elif flt == 'novideo': w.append('has_v=0')                                   # 🔇 只有聲音、沒有畫面
        elif str(flt).startswith('person:'):                                    # V0.1.51 依人物（👤 人物頁取好名字、自動比對出來的）
            w.append('id IN (SELECT file_id FROM people WHERE pid=?)'); a.append(int(str(flt)[7:] or 0))
        if not str(flt).startswith('ext:'):
            es, ea = self.ext_sql()
            if es: w.append(es); a += ea
        else: w.append('ext=?'); a.append(str(flt)[4:])
        if search:
            if (self.cfg.get('lab') or {}).get('smart_search'): ww, aa = parse_search(search); w += ww; a += aa
            elif (self.cfg.get('lab') or {}).get('note_presets'): w.append('(name LIKE ? OR note LIKE ?)'); a += [f'%{search}%', f'%{search}%']   # V0.2.83 也找備註
            else: w.append('name LIKE ?'); a.append(f'%{search}%')
        order = {'up_t': 'up_t DESC, folder, name', 'still': 'still DESC, folder, name', 'name': 'folder,name', 'size': 'size DESC', 'size_asc': 'size ASC', 'dur': 'dur DESC', 'dur_asc': 'dur ASC', 'mtime': 'mtime DESC', 'viewed': 'viewed DESC, folder, name', 'added': 'id DESC', 'grade': "CASE grade WHEN 'S' THEN 0 WHEN 'A' THEN 1 WHEN 'E' THEN 2 WHEN 'F' THEN 3 ELSE 4 END, folder, name"}.get(sort, 'folder,name')
        return [dict(r) for r in self.db.q(f'SELECT id,path,folder,name,ext,size,dur,w,h,vcodec,th_state,th_n,th_dir,th_cols,th_rows,th_step,viewed,fav,grade,cut_n,probed,has_v,tag,note,card_k,mtime,still,up_t,pub_t FROM files WHERE {" AND ".join(w)} ORDER BY {order} LIMIT 20000', a)]

    def file(self, fid):
        r = self.db.one('SELECT * FROM files WHERE id=?', (int(fid),)); return dict(r) if r else None

    def sheets(self, r):
        d = Path(r.get('th_dir') or '')
        try: return sorted(str(p) for p in d.glob('s*.jpg'))
        except Exception: return []

    def set_flags(self, ids, _stamp=True, **kw):
        """一次改很多部（分級、收藏記號…）."""
        ok = {k: v for k, v in kw.items() if k in ('fav', 'grade', 'note', 'viewed', 'tag', 'card_k', 'last_pos')}; ids = [int(i) for i in ids]
        if 'grade' in ok: ok['grade_t'] = time.time() if _stamp else 0                           # 什麼時候分級的（🧪 每日整理目標用）
        try:                                                                    # V0.3.36 🤖 分級建議準不準：你自己分的時候對照一下
            if _stamp and ok.get('grade') and (self.cfg.get('lab') or {}).get('guess') and 0 < len(ids) <= 20:
                n_ = k_ = 0
                for i_ in ids:
                    G_ = self.grade_guess(i_)
                    if G_: n_ += 1; k_ += 1 if G_['g'] == ok['grade'] else 0
                if n_: St = dict(self.cfg.get('guess_stat') or {}); St['n'] = int(St.get('n', 0)) + n_; St['ok'] = int(St.get('ok', 0)) + k_; self.cfg.set('guess_stat', St)
        except Exception: pass
        try:                                                                    # V0.3.33 📤 分成某一級時自動排進「複製到上傳資料夾」（只算你自己分的，規則分的不算）
            L_ = self.cfg.get('lab') or {}; cg = str(L_.get('copy_on_grade') or '')
            if cg and _stamp and L_.get('copy_to') and ok.get('grade') == cg and ids: threading.Timer(0.5, lambda ids=list(ids): self.copy_enqueue(ids)).start()
        except Exception: pass
        if ok and ids:
            self.db.xm('UPDATE files SET ' + ','.join(f'{k}=?' for k in ok) + ' WHERE id=?', [list(ok.values()) + [i] for i in ids])
            self.log.w(f'批量設定 {len(ids)} 部：' + '、'.join(f'{k}={v!r}' for k, v in ok.items()) + f'（id {ids[:15]}{"…" if len(ids) > 15 else ""}）')
            if ok.get('grade') == 'E': self.e_fix_add(ids)
        return len(ids)

    # ---------- V0.2.08 使用者的約定：發現預覽圖和影片時間對不上 → 標 E。自動用精準方式重做預覽圖，做好就把 E 拿掉（留在原資料夾等剪輯）
    def e_fix_ids(self):
        return [int(i) for i in (self.cfg.get('e_fix') or [])]

    def e_fix_add(self, ids):
        L = self.e_fix_ids(); new = [int(i) for i in ids if int(i) not in L]
        if not new: return
        self.cfg.set('e_fix', (L + new)[-5000:])
        for i in new:
            try: self.thumb_redo(i, precise=True)
            except Exception: self.log.err('E 重做預覽圖')
        self.log.w(f'🛠 標 E＝預覽圖時間對不上：{len(new)} 部排到最前面用精準方式重做，做好會自動把 E 拿掉（id {new[:15]}）')

    def e_fix_done(self, fid, ok=True):
        L = self.e_fix_ids()
        if int(fid) not in L: return
        self.cfg.set('e_fix', [i for i in L if i != int(fid)])
        if ok:
            n = self.db.x("UPDATE files SET grade='', grade_t=0 WHERE id=? AND grade='E'", (int(fid),))
            self.log.w(f'🛠 E 處理好了：id {fid} 預覽圖已用精準方式重做' + ('，E 標籤拿掉了（留在原資料夾）' if n else ''))
        else: self.log.w(f'🛠 E：id {fid} 預覽圖重做失敗，E 先留著')

    def states(self, ids):
        """清單／卡片自己更新用：預覽圖做好了沒、縮圖在哪."""
        ids = [int(i) for i in ids][:3000]
        if not ids: return {}
        return {r['id']: dict(r) for r in self.db.q('SELECT id,th_state,th_n,th_dir,th_cols,th_rows,cut_n,viewed,missing,grade FROM files WHERE id IN (%s)' % ','.join(map(str, ids)))}

    def set_values(self, pairs, field):
        """復原用：每部改回各自原本的值 [(id, 值)]."""
        if field not in ('fav', 'grade', 'tag', 'viewed', 'note'): return 0
        self.db.xm(f'UPDATE files SET {field}=?{", grade_t=0" if field == "grade" else ""} WHERE id=?', [(v, int(i)) for i, v in pairs]); self.log.w(f'復原：{len(pairs)} 部的 {field} 改回原本的值'); return len(pairs)

    def delete_original_many(self, ids, permanent=False):
        """批量刪除已剪輯的原檔。回傳 {'ok': n, 'fail': [(名稱, 原因)], 'need_perm': [id]}."""
        t = self.task('op', f'刪除原檔 {len(ids)} 部'); res = {'ok': 0, 'fail': [], 'need_perm': []}
        self.log.w(f'批量刪除原檔開始：{len(ids)} 部（{"直接刪除" if permanent else "資源回收筒"}）')
        for k, fid in enumerate(ids):
            if self.stop_all: break
            r = self.delete_original(fid, permanent)
            if r.get('ok'): res['ok'] += 1
            elif r.get('need_perm'): res['need_perm'].append(fid)
            else: res['fail'].append(((self.file(fid) or {}).get('name', str(fid)), r.get('message', '')))
            t['pct'] = round((k + 1) / max(1, len(ids)) * 100); t['msg'] = f'{k + 1}/{len(ids)}'
        self.done(t, 'done' if not res['fail'] else 'fail', f'刪了 {res["ok"]} 部' + (f'，{len(res["fail"])} 部沒刪' if res['fail'] else '') + (f'，{len(res["need_perm"])} 部不能丟回收筒' if res['need_perm'] else ''))
        self.log.w(f'批量刪除原檔結束：成功 {res["ok"]}、沒刪 {len(res["fail"])}、不能丟回收筒 {len(res["need_perm"])}')
        return res

    def set_flag(self, fid, **kw):
        ok = {k: v for k, v in kw.items() if k in ('fav', 'grade', 'note', 'viewed', 'tag', 'card_k', 'last_pos')}
        if ok: self.db.x('UPDATE files SET ' + ','.join(f'{k}=?' for k in ok) + ' WHERE id=?', list(ok.values()) + [int(fid)])
        if ok.get('grade') == 'E': self.e_fix_add([fid])

    def nonmp4(self, folder='', sub=True):
        w = ["missing=0", "ext NOT IN ('.mp4','.m4v')"]; a = []
        if folder:
            f = str(folder).rstrip('\\/'); w.append('(folder=? OR substr(folder,1,?)=? OR substr(folder,1,?)=?)' if sub else 'folder=?'); a += ([f, len(f) + 1, f + '\\', len(f) + 1, f + '/'] if sub else [f])
        return [dict(r) for r in self.db.q(f'SELECT id,path,folder,name,ext,size,dur,w,h,vcodec,acodecs,probed,cv_state,cv_err,cv_out,cv_ratio,cv_ssim FROM files WHERE {" AND ".join(w)} ORDER BY folder,name LIMIT 50000', a)]

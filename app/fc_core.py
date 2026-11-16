"""核心引擎（不准 import Qt）：設定、LOG、資料庫、效能、背景工作（後台總控制）、熱更新交接。

規則（給接手的 AI）：
- 畫面（app.py）只做畫面；讀硬碟、跑外部程式、算東西都在這裡的背景執行緒，畫面用 bg() 拿結果。
- 熱更新：新的 Engine(adopt=舊引擎) 接手同一份排隊／進行中的工作；舊引擎 retire() 後不再接新工作，手上的做完就停。
  新加「要跨熱更新保留」的東西 → 用 _keep(adopt, '名字', 建立函式)。
- 新的背景工作類型：加到 BG_KINDS、寫一個 _xxx_boss 執行緒（每次開新工作前先看 self.bg_hold('xxx')），
  bg_running／bg_progress 補上那一項，後台頁和手機就自動有暫停／繼續／立刻停／先後順序／自動讓路。
"""
import os, sys, re, json, time, platform, shutil, sqlite3, threading, subprocess, traceback, zipfile, binascii
from pathlib import Path
from collections import OrderedDict, deque

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fc_fcore as fcore  # noqa: E402
import fc_ana as ana  # noqa: E402
import fc_vsort as vsort  # noqa: E402
import fc_vgroup as vgroup  # noqa: E402
import fc_dupplan as dupplan  # noqa: E402
import fc_pets as pets  # noqa: E402
import fc_simi as simi  # noqa: E402
import fc_simv as simv  # noqa: E402
import fc_burst as burst  # noqa: E402
import fc_vslim as vslim  # noqa: E402
import fc_advice as advice  # noqa: E402
import fc_backup as backup  # noqa: E402
import fc_events as events  # noqa: E402
import fc_browse as browse  # noqa: E402
import fc_mtfix as mtfix  # noqa: E402
import fc_org as org  # noqa: E402
import fc_tline as tline  # noqa: E402
import fc_dupdir as dupdir  # noqa: E402
import fc_geo as geo  # noqa: E402
import fc_report as report  # noqa: E402


def load_brand():
    """app/brand.json：程式名稱、更新包前綴、手機網頁埠…（換成新程式只要改這個檔，或用 tools/rename.py）."""
    B = {'id': 'AppKit', 'name': 'AppKit', 'title': 'AppKit 新程式', 'prefix': 'AK', 'web_port': 8561, 'accent': '#e51e63', 'phone_id': 'appkit-phone'}
    try: B.update(json.loads((HERE / 'fc_brand.json').read_text(encoding='utf-8-sig')))
    except Exception: pass
    return B


BRAND = load_brand()
APP_NAME = BRAND['name']
IS_WIN = os.name == 'nt'
NO_WINDOW = 0x08000000 if IS_WIN else 0
PRIO = {'idle': 0x00000040, 'below': 0x00004000, 'normal': 0x00000020} if IS_WIN else {'idle': 0, 'below': 0, 'normal': 0}

DEFAULTS = {
    'ui_theme': 'dark', 'ui_zoom': 100,          # 深色／淺色、介面大小（下方狀態列）
    'side_w': 210, 'nav_shut': [],               # 側邊欄寬度、收起來的分組
    'last_page': 0, 'cover_on_start': True, 'cover_on_restore': False, 'cover_idle_min': 0,
    'close_to_tray': True,                       # 按 X：縮到右下角（托盤「結束」才真的關）
    'perf_float': False, 'perf_pos': None,       # 📊 效能浮窗
    'freeze_log_s': 2.0,                         # 畫面卡超過幾秒記到 ui_freeze_log.txt
    'auto_restart': True,                        # 閃退自動重開（看門狗）
    'web_on': False, 'web_port': BRAND.get('web_port', 8561), 'web_lan': False, 'web_tokens': [], 'web_pin_hash': '', 'web_pin_salt': '',
    'cpu_guard': True, 'cpu_max': 90, 'bg_ramp_sec': 20, 'bg_pause': {}, 'bg_last': {}, 'bg_prio': [],
    'db_backup': True, 'db_backup_keep': 7,
    'lab': {},                                   # 🧪 實驗工作區的開關 {名稱: True/False}
    'demo_n': 2,                                 # 示範背景工作：同時幾個
    'roots': [], 'keep_prio': [],                # 要掃描的資料夾、重複時優先保留的資料夾（上面的優先）
    'media_only': True,                          # 只看照片和影片
    'hash_n': 2, 'health_n': 6,                  # 比對重複／損毀檢查：同時幾個
    'health_deep': True,                         # 損毀檢查用 FFmpeg 解碼（比較準、比較慢）
    'meta_n': 6, 'meta_dhash': True,             # 讀取拍攝資訊：同時幾個、順便算相似照片的指紋
    'repair_n': 2,                               # 修復／救出：同時幾個（很吃硬碟）
    'auto_repair': True,                         # 🌙 檢查出有問題的檔案自動修復／救出（不用按 R）
    'auto_quar_broken': True,                    # 🌙 打不開／0 位元組的原檔，修完自動搬到隔離區（部分損毀的不搬）
    'vs_root': '',                               # 🎞 SortCut 的資料夾（有 Data\videosift.sqlite3）；空的＝自動找
    'vc_next': True,                             # 🎞 按了分類自動跳下一部
    'upd_dl_dir': '',
    'vgrid_n': 1,
    'sim_level': 3, 'simv_level': 3, 'burst_level': 3,
    'skip_pkg': True,
    'vc_skip_live': True,
    'vc_dup_del': True,                          # 🗑 分類過的檔，它的重複副本自動標成「Delete」（只留一份；V0.2.66）
    'rm_empty_dirs': True,                       # 搬走之後變「完全空」的資料夾順手收掉（不會收要整理的資料夾本身）
    'vc_sub': 'dir',                             # 🎞 分類搬檔時，分類資料夾裡再細分：dir＝照原本的資料夾名（V0.2.25 預設）、''＝不分、y＝年、ym＝年-月、y_ym＝年\年-月                        # 📱 影片分類不列動態照片的那段短影片（跟照片同名、≤ 4 秒）
    'quiet_on': False, 'quiet_from': 9, 'quiet_to': 23,     # 🌙 這段時間不跑背景工作（掃描、比對、檢查…）                            # 🎮 遊戲／軟體／程式專案資料夾裡的照片影片（素材）：重複、損毀、分類、相似…都不列                              # 🖼 相似照片：差幾個位元以內算相似（1 很嚴格～3 一般）                                # 🎞 分類預覽（背景做 16 格）同時幾個                            # 🆕 找新版更新包的資料夾（空的＝這台電腦的「下載」）
}


def now_s(): return time.strftime('%Y-%m-%d %H:%M:%S')


def path_key(p): return os.path.normcase(os.path.normpath(str(p))).rstrip('\\/').lower()


def fmt_t(s):
    s = int(max(0, s or 0)); return f'{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}' if s >= 3600 else f'{s // 60}:{s % 60:02d}'


def fmt_b(b):
    b = float(b or 0)
    return f'{b / 1e12:.2f} TB' if b >= 1e12 else f'{b / 1e9:.2f} GB' if b >= 1e9 else f'{b / 1e6:.0f} MB' if b >= 1e6 else f'{b / 1e3:.0f} KB'


def vkey(v):
    """版本比大小：'0.1.99' < '0.2.01'."""
    return tuple(int(x) for x in re.findall(r'\d+', str(v or ''))) or (0,)


def next_version(v):
    """版本規則：0.1.01 → 0.1.02 … 0.1.99 → 0.2.01（最後一段兩位數、不用 00）."""
    a = list(vkey(v)) + [0, 0, 0]; ma, mi, pa = a[0], a[1], a[2]
    pa += 1
    if pa > 99: mi += 1; pa = 1
    return f'{ma}.{mi}.{pa:02d}'


def run(cmd, timeout=60, prio='normal'):
    """跑外部程式（不開黑視窗）：回傳 (returncode, stdout, stderr)."""
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=NO_WINDOW | PRIO.get(prio, 0), stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout.decode('utf-8', 'replace'), p.stderr.decode('utf-8', 'replace')
    except subprocess.TimeoutExpired: return -9, '', '逾時'
    except Exception as ex: return -1, '', f'{type(ex).__name__}: {ex}'


# ---------------------------------------------------------------- LOG
class Log:
    """app_log.txt＝什麼都記（操作、設定變更、工作開始／結束、錯誤一行摘要）；error_log.txt＝錯誤＋完整位置；
    ui_freeze_log.txt＝畫面卡住（含卡在哪一行）；crash_dump.txt＝整個掛掉時每條執行緒在做什麼；update_log.txt＝更新／熱更新；qt_log.txt＝Qt 警告。
    每個檔超過 20 MB 換新的，舊的留最近 10 個。出問題時請使用者把整個 LOG 資料夾傳給 AI."""
    KEEP = 10

    def __init__(self, d):
        self.d = Path(d); self.d.mkdir(parents=True, exist_ok=True); self.lock = threading.Lock(); self.tail = deque(maxlen=600)

    def _rotate(self, p):
        try:
            if p.exists() and p.stat().st_size > 20e6:
                os.replace(str(p), str(p.with_name(f'{p.stem}_{time.strftime("%Y%m%d_%H%M%S")}{p.suffix}')))
                for o in sorted(self.d.glob(f'{p.stem}_2*{p.suffix}'))[:-self.KEEP]:
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

    def err(self, msg):
        tb = traceback.format_exc()
        if tb.strip() == 'NoneType: None': tb = ''.join(traceback.format_stack()[:-1])
        self.w(f'{msg}\n{tb}', 'error_log.txt'); self.w('✖ ' + msg + '　（詳細在 error_log.txt）')

    def export(self, out_zip, days=7):
        cut = time.time() - days * 86400; n = 0
        with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in sorted(self.d.glob('*')):
                if p.is_file() and p.stat().st_mtime >= cut and p.suffix.lower() in ('.txt', '.jsonl', '.json', '.log'): z.write(p, p.name); n += 1
        self.w(f'匯出 LOG：{n} 個檔（最近 {days} 天）→ {out_zip}'); return n


# ---------------------------------------------------------------- 設定
class Settings:
    """Data/settings.json。get 沒有的就用 DEFAULTS；set 馬上存檔（先寫 .tmp 再換掉，不會寫到一半壞掉），每次改都記 LOG."""
    QUIET = {'perf_pos', 'side_w'}

    def __init__(self, path):
        self.path = Path(path); self.lock = threading.Lock(); self.d = dict(DEFAULTS); self.log = None
        try:
            j = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(j, dict): self.d.update(j)
        except Exception: pass

    def get(self, k, default=None):
        v = self.d.get(k, DEFAULTS.get(k))
        return default if v is None and default is not None else v

    def set(self, k, v):
        old = self.d.get(k, DEFAULTS.get(k))
        if old == v: return
        if self.log and k not in self.QUIET:
            sv = lambda x: (json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else repr(x))[:300]
            self.log.w(f'設定：{k}　{sv(old)} → {sv(v)}')
        with self.lock:
            self.d[k] = v; self.path.parent.mkdir(parents=True, exist_ok=True); tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.d, ensure_ascii=False, indent=1), encoding='utf-8'); os.replace(str(tmp), str(self.path))


# ---------------------------------------------------------------- 資料庫
SCHEMA = """
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT, t REAL);
CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, state INTEGER DEFAULT 0, note TEXT DEFAULT '', t REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS oplog(id INTEGER PRIMARY KEY AUTOINCREMENT, t REAL, kind TEXT, detail TEXT DEFAULT '', ok INTEGER DEFAULT 1);
CREATE INDEX IF NOT EXISTS ix_oplog_t ON oplog(t);
CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE, root TEXT DEFAULT '', size INTEGER DEFAULT 0, mtime REAL DEFAULT 0,
  ext TEXT DEFAULT '', kind TEXT DEFAULT '', qhash TEXT, hash TEXT, health TEXT DEFAULT '', health_msg TEXT DEFAULT '', dur REAL DEFAULT 0,
  keep INTEGER DEFAULT 0, state TEXT DEFAULT '', qpath TEXT DEFAULT '', seen REAL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_files_size ON files(size);
CREATE INDEX IF NOT EXISTS ix_files_hash ON files(hash);
CREATE INDEX IF NOT EXISTS ix_files_root ON files(root);
CREATE INDEX IF NOT EXISTS ix_files_health ON files(state, health);
CREATE TABLE IF NOT EXISTS moves(id INTEGER PRIMARY KEY AUTOINCREMENT, t REAL, fid INTEGER, src TEXT, dst TEXT, reason TEXT DEFAULT '', undone INTEGER DEFAULT 0);
"""
MIGRATE = [('items', 'tag', "TEXT DEFAULT ''"),
           # V0.1.02：拍攝資訊（篩選、之後按年月整理、找相似照片用）
           ('files', 'meta', 'INTEGER DEFAULT 0'), ('files', 'taken', 'REAL'), ('files', 'date_src', "TEXT DEFAULT ''"), ('files', 'name_date', 'REAL DEFAULT 0'),
           ('files', 'make', "TEXT DEFAULT ''"), ('files', 'model', "TEXT DEFAULT ''"), ('files', 'software', "TEXT DEFAULT ''"), ('files', 'w', 'INTEGER DEFAULT 0'),
           ('files', 'h', 'INTEGER DEFAULT 0'), ('files', 'mp', 'REAL DEFAULT 0'), ('files', 'gps', 'INTEGER DEFAULT 0'), ('files', 'lat', 'REAL'), ('files', 'lon', 'REAL'),
           ('files', 'src', "TEXT DEFAULT ''"), ('files', 'vcodec', "TEXT DEFAULT ''"), ('files', 'motion', 'INTEGER DEFAULT 0'), ('files', 'dhash', "TEXT DEFAULT ''"),
           # V0.1.03：修復／救出（rep：0＝沒做、1＝排隊、2＝救出東西、3＝沒救出）
           ('files', 'rep', 'INTEGER DEFAULT 0'), ('files', 'rep_msg', "TEXT DEFAULT ''"),
           # V0.1.04：畫面綠色比例（缺資料的 JPEG 會被填成綠色）：-1＝還沒算、-2＝算不了
           ('files', 'green', 'REAL DEFAULT -1'),
           # V0.1.43：⭐ 最愛（重複、相似的時候優先留這份）
           ('files', 'fav', 'INTEGER DEFAULT 0')]
INDEXES = ['CREATE INDEX IF NOT EXISTS ix_files_meta ON files(state, meta)', 'CREATE INDEX IF NOT EXISTS ix_files_taken ON files(taken)',
           'CREATE INDEX IF NOT EXISTS ix_files_src ON files(src)', 'CREATE INDEX IF NOT EXISTS ix_files_rep ON files(rep)',
           'CREATE TABLE IF NOT EXISTS repairs(id INTEGER PRIMARY KEY AUTOINCREMENT, fid INTEGER, t REAL, type TEXT, out TEXT, size INTEGER DEFAULT 0, note TEXT DEFAULT \'\')',
           'CREATE INDEX IF NOT EXISTS ix_repairs_fid ON repairs(fid)',
           # 「還沒做的」專用索引：背景工作找下一批時不用掃整個資料表（50 萬筆也是瞬間）
           "CREATE INDEX IF NOT EXISTS ix_todo_meta ON files(path) WHERE state='' AND meta=0",
           "CREATE INDEX IF NOT EXISTS ix_todo_health ON files(path) WHERE state='' AND health=''",
           "CREATE INDEX IF NOT EXISTS ix_todo_green ON files(path) WHERE state='' AND kind='photo' AND green=-1 AND health IN ('ok','partial')",
           "CREATE INDEX IF NOT EXISTS ix_todo_qhash ON files(path) WHERE state='' AND size>0 AND qhash IS NULL",
           "CREATE INDEX IF NOT EXISTS ix_todo_rep ON files(path) WHERE state='' AND rep=1",
           'CREATE INDEX IF NOT EXISTS ix_geo ON files(lat, lon) WHERE lat IS NOT NULL',
           # V0.1.10：📈 資料分析（每個資料夾的大小、每一類佔多少、是不是一整包遊戲／軟體）；gen＝第幾次分析（新的寫好才換掉舊的）
           "CREATE TABLE IF NOT EXISTS ana_dir(gen INTEGER, root TEXT, path TEXT, parent TEXT, depth INTEGER, b INTEGER, n INTEGER, eff TEXT, pkg TEXT DEFAULT '', why TEXT DEFAULT '', raw TEXT DEFAULT '', mt REAL DEFAULT 0, kids INTEGER DEFAULT 0)",
           'CREATE INDEX IF NOT EXISTS ix_ana_parent ON ana_dir(gen, parent)', 'CREATE INDEX IF NOT EXISTS ix_ana_pkg ON ana_dir(gen, pkg, b)', 'CREATE INDEX IF NOT EXISTS ix_ana_path ON ana_dir(gen, path)',
           # V0.1.11：🎞 影片快速分類（分類、每部影片分到哪一類；moved＝已經搬了）
           "CREATE TABLE IF NOT EXISTS vc_cat(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, dest TEXT DEFAULT '', color TEXT DEFAULT '', ord INTEGER DEFAULT 0, t REAL DEFAULT 0)",
           "CREATE TABLE IF NOT EXISTS vc_tag(fid INTEGER PRIMARY KEY, cat INTEGER, t REAL DEFAULT 0, moved INTEGER DEFAULT 0, dst TEXT DEFAULT '')",
           'CREATE INDEX IF NOT EXISTS ix_vc_tag_cat ON vc_tag(cat, moved)',
           # V0.1.23：🧹 雜物（資料分析時順便找：空資料夾、0 位元組、暫存雜檔、最大的檔）
           "CREATE TABLE IF NOT EXISTS ana_junk(gen INTEGER, kind TEXT, path TEXT, b INTEGER, mt REAL, done INTEGER DEFAULT 0)",
           'CREATE INDEX IF NOT EXISTS ix_ana_junk ON ana_junk(gen, kind, done, b)',
           # V0.1.24：🖼 相似照片（分組）、「不是相似」記下來
           'CREATE TABLE IF NOT EXISTS sim_grp(gid INTEGER, fid INTEGER)', 'CREATE INDEX IF NOT EXISTS ix_sim_gid ON sim_grp(gid)',
           'CREATE TABLE IF NOT EXISTS sim_skip(a INTEGER, b INTEGER, PRIMARY KEY(a, b))',
           # V0.1.33：🎬 相似影片（指紋、分組、不是相似）
           'CREATE TABLE IF NOT EXISTS vsig(fid INTEGER PRIMARY KEY, size INTEGER, sig TEXT)',
           'CREATE TABLE IF NOT EXISTS simv_grp(gid INTEGER, fid INTEGER)', 'CREATE INDEX IF NOT EXISTS ix_simv_gid ON simv_grp(gid)',
           'CREATE TABLE IF NOT EXISTS simv_skip(a INTEGER, b INTEGER, PRIMARY KEY(a, b))',
           # V0.1.50：📸 連拍精選（清楚程度、分組、不是連拍）
           'CREATE TABLE IF NOT EXISTS pblur(fid INTEGER PRIMARY KEY, size INTEGER, blur REAL)',
           'CREATE TABLE IF NOT EXISTS burst_grp(gid INTEGER, fid INTEGER)', 'CREATE INDEX IF NOT EXISTS ix_burst_gid ON burst_grp(gid)',
           'CREATE TABLE IF NOT EXISTS burst_skip(a INTEGER, b INTEGER, PRIMARY KEY(a, b))',
           # V0.1.63：📉 整理進度（每小時記一次總數）
           'CREATE TABLE IF NOT EXISTS mt_fix(id INTEGER PRIMARY KEY AUTOINCREMENT, t REAL, fid INTEGER, old REAL, new REAL, undone INTEGER DEFAULT 0)',
           'CREATE TABLE IF NOT EXISTS stat_hist(t REAL PRIMARY KEY, files INTEGER, bytes INTEGER, dup_b INTEGER, quar_b INTEGER, bad INTEGER, tagged INTEGER)']          # 新欄位放這裡：舊資料庫打開時自動補（不動原本的資料）


def db_migrate(store):
    """建表、補新欄位、補索引（只加不刪）。熱更新時新版也會對同一個資料庫跑一次，所以舊版的 Store 也能用."""
    with store.lock:
        rf = store.con.row_factory; store.con.row_factory = None
        try:
            store.con.executescript(SCHEMA); store.con.commit()
            for tb, col, decl in MIGRATE:
                have = {r[1] for r in store.con.execute(f'PRAGMA table_info({tb})').fetchall()}
                if col not in have: store.con.execute(f'ALTER TABLE {tb} ADD COLUMN {col} {decl}'); store.con.commit()
            for sql in INDEXES: store.con.execute(sql)
            store.con.commit()
        finally: store.con.row_factory = rf


class Store:
    """SQLite（WAL）。所有讀寫用同一把鎖；q／one 讀、x／xm 寫（失敗自動 rollback）."""
    def __init__(self, path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True); self.lock = threading.RLock()
        self.con = sqlite3.connect(str(self.path), check_same_thread=False, timeout=30)
        self.con.execute('PRAGMA journal_mode=WAL'); self.con.execute('PRAGMA synchronous=NORMAL'); self.con.execute('PRAGMA busy_timeout=30000')
        db_migrate(self)
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
            try: self.con.executemany(sql, seq); self.con.commit()
            except Exception:
                try: self.con.rollback()
                except Exception: pass
                raise

    def backup_to(self, dst):
        with self.lock:
            b = sqlite3.connect(str(dst))
            try: self.con.backup(b)
            finally: b.close()

    def close(self):
        with self.lock:
            try: self.con.close()
            except Exception: pass


# ---------------------------------------------------------------- 效能（不用 psutil：Windows API／Linux /proc；顯示卡用 nvidia-smi）
class Perf:
    def __init__(self, log):
        self.log = log; self.cpu = 0.0; self.ram = 0.0; self.ram_used = 0; self.ram_total = 0; self.gpu = None
        self.H = {k: deque(maxlen=180) for k in ('cpu', 'ram', 'gpu', 'enc', 'dec', 'vram')}; self._ct = None; self.stop = False
        self.smi = shutil.which('nvidia-smi') or (r'C:\Windows\System32\nvidia-smi.exe' if IS_WIN and Path(r'C:\Windows\System32\nvidia-smi.exe').exists() else '')
        threading.Thread(target=self._loop, name='Perf', daemon=True).start()

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
                    self.cpu = max(0.0, min(100.0, 100.0 * (1 - di / dt))) if dt > 0 else 0.0
                self._ct = (idle, tot)
                self.ram_used, self.ram_total = self._ram(); self.ram = 100.0 * self.ram_used / self.ram_total if self.ram_total else 0
            except Exception: pass
            if self.smi and k % 2 == 0:
                rc, out, _e = run([self.smi, '--query-gpu=name,utilization.gpu,utilization.encoder,utilization.decoder,memory.used,memory.total,temperature.gpu,driver_version',
                                   '--format=csv,noheader,nounits'], timeout=8)
                try:
                    p = [x.strip() for x in out.strip().splitlines()[0].split(',')] if rc == 0 and out.strip() else None
                    self.gpu = {'name': p[0], 'util': float(p[1]), 'enc': float(p[2]), 'dec': float(p[3]), 'mem': float(p[4]), 'mem_t': float(p[5]), 'temp': float(p[6]), 'drv': p[7]} if p else None
                except Exception: self.gpu = None
            g = self.gpu or {}
            self.H['cpu'].append(self.cpu); self.H['ram'].append(self.ram); self.H['gpu'].append(g.get('util')); self.H['enc'].append(g.get('enc')); self.H['dec'].append(g.get('dec'))
            self.H['vram'].append(100.0 * g['mem'] / g['mem_t'] if g.get('mem_t') else None)
            k += 1; time.sleep(1.0)

    def view(self):
        g = dict(self.gpu or {})
        return {'cpu': round(self.cpu, 1), 'ram': round(self.ram, 1), 'ram_used': self.ram_used, 'ram_total': self.ram_total, 'gpu': g,
                'hist': {k: [None if x is None else round(float(x), 1) for x in list(v)[-90:]] for k, v in self.H.items()}}


# ---------------------------------------------------------------- 引擎
def _keep(adopt, k, make):
    """熱更新接手：舊的有就共用同一個（空的也共用，所以不能用 or）."""
    v = getattr(adopt, k, None) if adopt is not None else None
    return v if v is not None else make()


EXT_HOLD = {'fn': None}                                                       # 嵌在 SortCut 裡：VS 設的讓路規則


class Engine:
    """root＝程式資料夾（EXE 旁邊）：Data\\（設定、資料庫）、LOG\\、UPDATE\\、app\\。
    adopt＝熱更新時的舊引擎；start=False：先建好、還不開始跑（熱更新時新視窗也建好才 start，失敗就 discard，舊的照常）."""
    PREV_GC_TICK, PREV_GC_WAIT = 15, 120
    # 後台總控制的項目：(代號, 圖示, 名稱)。新功能的背景工作加在這裡（順序＝預設先後）
    BG_KINDS = [('scan', '📂', '掃描資料夾'), ('meta', '🏷', '讀取拍攝資訊'), ('hash', '🔁', '比對重複（算指紋）'), ('health', '🩺', '損毀檢查'), ('repair', '🛠', '修復／救出'), ('ana', '📈', '資料分析'), ('vgrid', '🎞', '分類預覽（16 格）')]
    FC_KINDS = ('scan', 'meta', 'hash', 'health', 'repair', 'ana', 'vgrid')

    def __init__(self, root, adopt=None, start=True, version=''):
        self.root = Path(root); self.data = self.root / 'Data'; self.data.mkdir(parents=True, exist_ok=True); self.version = version
        self.log = _keep(adopt, 'log', lambda: Log(self.root / 'LOG')); self.cfg = Settings(self.data / 'settings.json'); self.cfg.log = self.log
        self.db = Store(self.data / 'app.sqlite3') if adopt is None else adopt.db
        if adopt is not None and type(self.db) is not Store and type(self.db).__name__ == 'Store':
            try: self.db.__class__ = Store                                      # V0.5.92 熱更新接手的舊連線也用新的「畫面不等資料庫」
            except Exception: pass
        if adopt is not None: db_migrate(self.db)
        self.stop_all = False; self.retired = False; self.started = False; self.prev = adopt
        self.perf = Perf(self.log)
        self.lock = _keep(adopt, 'lock', threading.RLock); self.tasks = _keep(adopt, 'tasks', OrderedDict); self._tid = (getattr(adopt, '_tid', 0) + 1000) if adopt else 0
        self.procs = _keep(adopt, 'procs', set)
        # 後台總控制：暫停（存在設定裡，重開還在）、電腦太忙時自動讓路、慢慢加速、最近在做哪一個
        self.bg_pause = {k: True for k, v in dict(self.cfg.get('bg_pause') or {}).items() if v}
        self.bg_auto = _keep(adopt, 'bg_auto', dict); self.bg_slow = _keep(adopt, 'bg_slow', dict); self.bg_ramp = _keep(adopt, 'bg_ramp', dict)
        self.bg_last = dict(self.cfg.get('bg_last') or {})
        self.bg_gov = _keep(adopt, 'bg_gov', lambda: {'hi_t': 0.0, 'lo_t': 0.0, 'log': deque(maxlen=200)})
        # 示範背景工作（新程式把它換成真的工作）：排隊、進行中
        self.demo_q = _keep(adopt, 'demo_q', deque); self.demo_active = _keep(adopt, 'demo_active', dict); self.demo_done = _keep(adopt, 'demo_done', lambda: [0])
        # FileCompare：掃描排隊、進行中的工作（大家共用，熱更新時新舊引擎不會重複做同一個檔）
        self.fc_scan_q = _keep(adopt, 'fc_scan_q', deque); self.fc_active = _keep(adopt, 'fc_active', dict); self.fc_claim = _keep(adopt, 'fc_claim', set)
        self.fc_stat = _keep(adopt, 'fc_stat', lambda: {'done': 0, 'total': 0}); self.fc_run = _keep(adopt, 'fc_run', dict)
        self.fc_dirty = _keep(adopt, 'fc_dirty', lambda: [time.time()]); self.fc_bulk = _keep(adopt, 'fc_bulk', dict)
        self.ana_st = _keep(adopt, 'ana_st', lambda: {'req': False, 'auto': False, 'done': 0, 'total': 0, 'cur': ''})       # 📈 資料分析
        self.fc_cache = {'t': 0, 'v': {}}; self.fc_cache_lock = threading.Lock(); self._ff = None
        self.info_c = {'t': 0, 'v': {}}
        self.vc = vsort.VSort(self, getattr(adopt, 'vc', None))                 # 🎞 影片快速分類
        self.upd_st = _keep(adopt, 'upd_st', dict)
        self.junk_st = _keep(adopt, 'junk_st', dict)
        self.sim = simi.Sim(self, getattr(adopt, 'sim', None))                    # 🖼 相似照片
        self.mtf = mtfix.MtFix(self, getattr(adopt, 'mtf', None))              # 🕒 修正修改日期
        self.brw = browse.Browse(self)                                           # 📂 瀏覽資料夾
        self.evt = events.Events(self)                                           # 🧳 活動
        self.bak = backup.Backup(self)                                           # 💾 備份檢查
        self.adv = advice.Advice(self)                                           # 💡 建議你做
        self.slim = vslim.Slim(self, getattr(adopt, 'slim', None))              # 🗜 影片瘦身
        self.simv = simv.SimV(self, getattr(adopt, 'simv', None))
        self.burst = burst.Burst(self, getattr(adopt, 'burst', None))           # 📸 連拍精選                 # 🎬 相似影片
        self.org = org.Org(self, getattr(adopt, 'org', None))                     # 📅 依日期整理
        self.tl = tline.Timeline(self)                                           # 🗓 那年今天＋時間軸
        self.geo = geo.Geo(self)                                                 # 🗺 照片地圖
        self.dpl = dupplan.DupPlan(self, getattr(adopt, 'dpl', None))           # 🧭 重複檔：資料夾的角度（V0.2.16）
        self.pet = pets.Pets(self, getattr(adopt, 'pet', None))                  # 🐾 找有貓狗的影片（V0.2.93）
        self.vg = vgroup.VGroup(self)
        _t = threading.Timer(40, self.vc.dup_to_delete_all); _t.daemon = True; _t.start()   # 已分類的檔：重複副本 → Delete（背景，啟動 40 秒後）                                            # 📦 資料夾包＋🧩 相關的排一起（V0.2.14）
        self.ddir = dupdir.DupDir(self, getattr(adopt, 'ddir', None))             # 📁 重複資料夾                             # 🧹 雜物搬到隔離區的進度                               # 🆕 線上更新的狀態（手機等新版好了沒；熱更新後新版接著用同一個）
        if start: self.start()

    # ================================================================ 生命週期
    def alive(self): return not self.stop_all and not self.retired

    def start(self):
        if self.started: return
        self.started = True; old = self.prev
        if old is not None:
            try: old.cfg = self.cfg
            except Exception: pass
            try: old.retire()
            except Exception:
                try: old.retired = True
                except Exception: pass
        else:
            self.log_startup()
        for k_ in [k for k, _i, _n in self.BG_KINDS]:
            if old is None: self.bg_ramp[k_] = time.time()                     # 剛開程式：慢慢加速
        for nm, fn in (('DemoBoss', self._demo_boss), ('Governor', self._gov_loop), ('DbBackup', self._backup_loop), ('ScanBoss', self._scan_boss),
                       ('HashBoss', lambda: self._pool_boss('hash', self._hash_fetch, self._hash_work, 'hash_n', 2, '比對重複（算指紋）')),
                       ('HealthBoss', lambda: self._pool_boss('health', self._health_fetch, self._health_work, 'health_n', 3, '損毀檢查')),
                       ('MetaBoss', lambda: self._pool_boss('meta', self._meta_fetch, self._meta_work, 'meta_n', 3, '讀取拍攝資訊')),
                       ('RepairBoss', lambda: self._pool_boss('repair', self._repair_fetch, self._repair_work, 'repair_n', 1, '修復／救出')),
                       ('AnaBoss', self._ana_boss),
                       ('VGridBoss', lambda: self._pool_boss('vgrid', self.vc.pre_fetch, self.vc.pre_work, 'vgrid_n', 1, '🎞 分類預覽（16 格）'))):
            threading.Thread(target=fn, name=nm, daemon=True).start()
        if old is not None: threading.Thread(target=self._prev_gc, name='PrevGC', daemon=True).start()

    def retire(self):
        """熱更新：不再接新工作（正在做的照做完）."""
        self.retired = True
        try: self.perf.stop = True
        except Exception: pass
        self.log.w(f'舊引擎 V{self.version or "?"} 退休：手上的做完就停')

    def discard(self):
        """熱更新失敗：這個沒開始跑的新引擎丟掉（舊的照常）."""
        self.stop_all = True
        try: self.perf.stop = True
        except Exception: pass

    def _prev_gc(self):
        """熱更新後：舊引擎手上的都做完了就放掉（不然每熱更新一次多留一份在記憶體）."""
        t0 = time.time()
        while self.alive():
            time.sleep(self.PREV_GC_TICK)
            e = self.prev
            if e is None: return
            if self.demo_active or self.fc_active or time.time() - t0 < self.PREV_GC_WAIT: continue
            try: e.prev = None
            except Exception: pass
            self.prev = None; self.log.w(f'熱更新：舊引擎 V{getattr(e, "version", "?")} 已釋放'); return

    def shutdown(self):
        self.stop_all = True
        try: self.perf.stop = True
        except Exception: pass
        busy = len(self.demo_active) + len(self.fc_active)
        for J in list(self.fc_active.values()): J['cancel'] = True
        for p in list(self.procs):
            try: p.kill()
            except Exception: pass
        e = self.prev
        while e is not None:
            try: e.stop_all = True
            except Exception: pass
            e = getattr(e, 'prev', None)
        self.log.w(f'關閉 {APP_NAME} V{self.version}（停掉做到一半的 {busy} 個工作，下次打開接著做）'); self.log.w('=' * 100); self.db.close()

    def log_startup(self):
        L = self.log.w; L('=' * 100)
        L(f'啟動 {APP_NAME} V{self.version}　{platform.platform()}　Python {platform.python_version()}　{"EXE" if getattr(sys, "frozen", False) else "原始碼"}　程式資料夾 {self.root}')
        try: L('設定：' + '　'.join(f'{k}={self.cfg.get(k)}' for k in ('ui_theme', 'ui_zoom', 'web_on', 'web_port', 'cpu_guard', 'cpu_max')))
        except Exception: pass

    # ================================================================ 工作清單（後台頁下方的「最近的工作」）
    def task(self, kind, title):
        with self.lock:
            self._tid += 1; t = {'id': self._tid, 'kind': kind, 'title': title, 'state': 'run', 'pct': None, 'msg': '', 't0': time.time(), 't1': 0}
            self.tasks[self._tid] = t
            while len(self.tasks) > 300: self.tasks.popitem(last=False)
            return t

    def done(self, t, state='done', msg=''):
        t['state'] = state; t['t1'] = time.time()
        if msg: t['msg'] = msg

    def tasks_list(self):
        with self.lock: return list(self.tasks.values())

    def oplog(self, kind, detail='', ok=True):
        try: self.db.x('INSERT INTO oplog(t,kind,detail,ok) VALUES(?,?,?,?)', (time.time(), kind, detail, 1 if ok else 0))
        except Exception: self.log.err('操作紀錄')

    # ================================================================ 後台總控制（每一項：暫停／繼續／立刻停／先後順序／自動讓路／慢慢加速）
    def bg_prio(self):
        K = [k for k, _i, _n in self.BG_KINDS]; L = [k for k in (self.cfg.get('bg_prio') or []) if k in K]
        return L + [k for k in K if k not in L]

    def bg_hold(self, kind):
        """這一項現在不要開新的工作：你按了暫停，或電腦太忙自動讓路；嵌在 SortCut 裡時，VS 正在用同一顆硬碟也先讓路."""
        return bool(self.bg_pause.get(kind)) or kind in self.bg_auto or self.quiet_now() or bool(self.ext_hold(kind))

    def ext_hold(self, kind):
        """SortCut 設的「先讓路」（EXT_HOLD['fn'](kind) → 原因；空的＝不用讓）."""
        f = EXT_HOLD.get('fn')
        if f is None: return ''
        try: return str(f(kind) or '')
        except Exception: return ''

    def quiet_now(self):
        """🌙 指定時段不跑背景（V0.1.54）：例如白天 9～23 點用電腦時不跑，晚上才跑；quiet_from > quiet_to 表示跨過半夜."""
        if not self.cfg.get('quiet_on'): return False
        try: a, b = int(self.cfg.get('quiet_from') or 0) % 24, int(self.cfg.get('quiet_to') or 0) % 24
        except (TypeError, ValueError): return False
        h = time.localtime().tm_hour
        return (a <= h < b) if a < b else ((h >= a or h < b) if a > b else False)

    def bg_cap(self, kind, n):
        """慢慢加速：剛開始／剛繼續時同時只做 1 個，每過 bg_ramp_sec 秒多 1 個，直到上限 n."""
        f_ = EXT_HOLD.get('cap')                                                # V0.5.71 SortCut 的 🤝 讓路等級（Lv 1＝同時只做 1 個）
        if f_ is not None:
            try: n = int(f_(kind, n))
            except Exception: pass
        if self.bg_slow.get(kind): n = max(1, min(n, int(self.bg_slow[kind])))
        t0 = self.bg_ramp.get(kind)
        if not t0: return n
        sec = max(0, int(self.cfg.get('bg_ramp_sec') if self.cfg.get('bg_ramp_sec') is not None else 20))
        if sec <= 0: return n
        k = 1 + int((time.time() - t0) / sec)
        if k >= n: self.bg_ramp.pop(kind, None); return n
        return max(1, k)

    def bg_running(self, kind):
        if kind == 'demo': return len(self.demo_active)
        return sum(1 for J in list(self.fc_active.values()) if J.get('kind') == kind)

    def bg_progress(self):
        """每一項的總進度（完成的, 全部）."""
        d = self.demo_done[0]; C = self.fc_counts(); S = self.fc_stat
        return {'demo': (d, d + len(self.demo_q) + len(self.demo_active)), 'scan': (S.get('done', 0), S.get('total', 0)),
                'hash': (C.get('hash_done', 0), C.get('hash_total', 0)), 'health': (C.get('health_done', 0), C.get('media', 0)), 'meta': (C.get('meta_done', 0), C.get('media', 0)),
                'repair': (C.get('rep_done', 0), C.get('rep_done', 0) + C.get('rep_q', 0)), 'ana': (self.ana_st.get('done', 0), self.ana_st.get('total', 0)), 'vgrid': self.vc.pre_progress()}

    def bg_mark(self, kind, name): self.bg_last[kind] = str(name or '')[:200]

    def bg_set_pause(self, kind, on, why='你按的'):
        on = bool(on); was = bool(self.bg_pause.get(kind))
        if on: self.bg_pause[kind] = True
        else: self.bg_pause.pop(kind, None); self.bg_auto.pop(kind, None); self.bg_ramp[kind] = time.time()
        try: self.cfg.set('bg_pause', dict(self.bg_pause)); self.cfg.set('bg_last', dict(self.bg_last))
        except Exception: pass
        if was != on:
            nm = dict((k, n) for k, _i, n in self.BG_KINDS).get(kind, kind)
            self.log.w(f'⏯ 後台：{nm} {"暫停" if on else "繼續（慢慢加速）"}（{why}）')
        return True

    def bg_stop_now(self, kind):
        """立刻停：暫停，正在做的也停掉、放回排隊."""
        self.bg_set_pause(kind, True, '立刻停'); n = 0
        if kind == 'demo':
            for J in list(self.demo_active.values()): J['cancel'] = True; n += 1
        for J in list(self.fc_active.values()):
            if J.get('kind') == kind: J['cancel'] = True; n += 1
        self.log.w(f'⏹ 後台：{kind} 立刻停，{n} 個放回排隊'); return n

    def bg_all(self, on):
        for k, _i, _n in self.BG_KINDS: self.bg_set_pause(k, on, '全部' + ('暫停' if on else '繼續'))
        if not on:
            now = time.time()
            for i, k in enumerate(self.bg_prio()): self.bg_ramp[k] = now + i * 10

    def bg_move(self, kind, d):
        L = self.bg_prio()
        if kind not in L: return L
        i = L.index(kind); j = max(0, min(len(L) - 1, i + int(d))); L[i], L[j] = L[j], L[i]
        self.cfg.set('bg_prio', L); return L

    def bg_view(self):
        """給後台頁／手機：每一項的狀態、先後順序、進度、停在哪."""
        P = self.bg_progress(); L = []; nm = dict((k, (i, n)) for k, i, n in self.BG_KINDS)
        for idx, k in enumerate(self.bg_prio()):
            d, tot = P.get(k, (0, 0)); run_ = self.bg_running(k)
            qn = self.quiet_now()
            xh_ = self.ext_hold(k) if (not run_ and tot and d < tot) else ''
            st = 'pause' if self.bg_pause.get(k) else ('hold' if (k in self.bg_auto or qn or xh_) else ('run' if run_ else 'idle'))
            L.append({'k': k, 'icon': nm[k][0], 'name': nm[k][1], 'state': st, 'running': run_, 'prio': idx + 1,
                      'held': self.bg_auto.get(k, '') or (('🤝 ' + xh_) if xh_ else '') or (f"🌙 {int(self.cfg.get('quiet_from') or 0)}～{int(self.cfg.get('quiet_to') or 0)} 點不跑" if qn else ''),
                      'last': self.bg_last.get(k, ''), 'done': d, 'total': tot, 'pct': round(d * 100 / tot, 1) if tot else None,
                      'ramp': (self.bg_cap(k, 99) if self.bg_ramp.get(k) else None), 'slow': self.bg_slow.get(k)})
        G = self.bg_gov
        return {'kinds': L, 'cpu': round(float(self.perf.cpu or 0), 1), 'guard': (self.cfg.get('cpu_guard') is not False), 'cpu_max': int(self.cfg.get('cpu_max') or 90),
                'ramp_sec': int(self.cfg.get('bg_ramp_sec') if self.cfg.get('bg_ramp_sec') is not None else 20),
                'log': [f'{time.strftime("%H:%M:%S", time.localtime(t))} {m}' for t, m in list(G['log'])[-30:]][::-1]}

    def _gov_loop(self):
        """電腦太忙（CPU 一直很高）：從最不重要的開始自動讓路；閒下來照順序一項一項放回來."""
        nmf = lambda k: dict((a, c) for a, _b, c in self.BG_KINDS).get(k, k)
        while self.alive():
            try:
                time.sleep(2.0)
                if self.cfg.get('cpu_guard') is False:
                    for k in list(self.bg_auto): self.bg_auto.pop(k, None); self.bg_ramp[k] = time.time()
                    self.bg_slow.clear(); continue
                # 看最近 20 秒的平均（不是瞬間值）：每開一個 FFmpeg 都會讓 CPU 瞬間衝高，用瞬間值會一直誤判成「很忙」
                hist = [x for x in list(self.perf.H['cpu'])[-20:] if x is not None]
                cpu = sum(hist) / len(hist) if hist else float(self.perf.cpu or 0)
                hi = float(self.cfg.get('cpu_max') or 90); lo = max(10.0, hi - 25); now = time.time(); G = self.bg_gov
                if cpu >= hi:
                    G['lo_t'] = 0.0; G['hi_t'] = G['hi_t'] or now
                    if now - G['hi_t'] >= 12:
                        PR = self.bg_prio()
                        for k in reversed(PR):
                            if self.bg_hold(k) or not self.bg_running(k): continue
                            if not any(self.bg_running(x) and not self.bg_hold(x) for x in PR[:PR.index(k)]):
                                rn = self.bg_running(k)
                                if rn > 1:
                                    self.bg_slow[k] = rn - 1; G['hi_t'] = now; msg = f'⚖ 平均 CPU {cpu:.0f}%（最近 20 秒）：{nmf(k)} 降速成同時最多 {rn - 1} 個'
                                    G['log'].append((now, msg)); self.log.w('⏯ 後台：' + msg); break
                                continue
                            self.bg_auto[k] = f'電腦很忙（CPU {cpu:.0f}%），先讓給前面的'; G['hi_t'] = now
                            msg = f'⚖ 平均 CPU {cpu:.0f}%（最近 20 秒）：{nmf(k)} 先不開新的'; G['log'].append((now, msg)); self.log.w('⏯ 後台：' + msg); break
                        else: G['hi_t'] = now
                elif cpu <= lo:
                    G['hi_t'] = 0.0; G['lo_t'] = G['lo_t'] or now
                    if self.bg_slow and now - G['lo_t'] >= 30 and not self.bg_auto:
                        k = next(iter(self.bg_slow)); self.bg_slow.pop(k, None); self.bg_ramp[k] = now; G['lo_t'] = now
                        msg = f'⚖ CPU 降到 {cpu:.0f}%：{nmf(k)} 不降速了'; G['log'].append((now, msg)); self.log.w('⏯ 後台：' + msg)
                    if self.bg_auto and now - G['lo_t'] >= 30:
                        for k in self.bg_prio():
                            if k in self.bg_auto:
                                self.bg_auto.pop(k, None); self.bg_ramp[k] = now; G['lo_t'] = now
                                msg = f'⚖ CPU 降到 {cpu:.0f}%：{nmf(k)} 繼續'; G['log'].append((now, msg)); self.log.w('⏯ 後台：' + msg); break
                else: G['hi_t'] = 0.0; G['lo_t'] = 0.0
            except Exception: self.log.err('後台總控制'); time.sleep(5)

    # ================================================================ 示範背景工作（新程式照這個樣子寫自己的工作，然後刪掉這段）
    def demo_add(self, n=5, sec=8):
        """排 n 個假的工作（每個 sec 秒），用來看後台頁、手機、熱更新、自動讓路是不是都正常."""
        with self.lock:
            for i in range(int(n)): self.demo_q.append({'name': f'示範工作 #{self.demo_done[0] + len(self.demo_q) + len(self.demo_active) + 1}', 'sec': float(sec)})
        self.log.w(f'示範：排了 {n} 個工作（每個 {sec} 秒）'); return len(self.demo_q)

    def _demo_boss(self):
        while self.alive():
            try:
                n = self.bg_cap('demo', max(1, min(8, int(self.cfg.get('demo_n') or 2))))
                if self.demo_q and len(self.demo_active) < n and not self.bg_hold('demo'):
                    with self.lock: J = self.demo_q.popleft() if self.demo_q else None
                    if J:
                        J['id'] = id(J); self.demo_active[J['id']] = J; self.bg_mark('demo', J['name'])
                        threading.Thread(target=self._demo_job, args=(J,), name='DemoJob', daemon=True).start(); continue
                time.sleep(0.5)
            except Exception: self.log.err('示範工作排程'); time.sleep(5)

    def _demo_job(self, J):
        t = self.task('demo', J['name']); t0 = time.time()
        try:
            while time.time() - t0 < J['sec']:
                if J.get('cancel') or self.stop_all: raise InterruptedError
                t['pct'] = J['pct'] = round((time.time() - t0) / J['sec'] * 100); time.sleep(0.2)
            self.demo_done[0] += 1; self.done(t, 'done', f'{time.time() - t0:.1f} 秒')
        except InterruptedError:
            with self.lock: self.demo_q.appendleft({k: v for k, v in J.items() if k in ('name', 'sec')})
            self.done(t, 'stop', '停止（放回排隊）')
        except Exception as ex: self.log.err('示範工作'); self.done(t, 'fail', str(ex))
        finally: self.demo_active.pop(J['id'], None)

    # ================================================================ 資料庫每日備份
    def _backup_loop(self):
        for _ in range(60):
            if not self.alive(): return
            time.sleep(1)
        while self.alive():
            try:
                if self.cfg.get('db_backup') is not False:
                    d = self.data / 'db_backup'; d.mkdir(exist_ok=True); tag = time.strftime('%Y%m%d')
                    if not list(d.glob(f'app_{tag}_*.sqlite3')):
                        self.db.backup_to(d / f'app_{tag}_{time.strftime("%H%M%S")}.sqlite3')
                        if (self.data / 'settings.json').exists(): shutil.copy2(str(self.data / 'settings.json'), str(d / f'settings_{tag}.json'))
                        keep = max(1, int(self.cfg.get('db_backup_keep') or 7))
                        for o in sorted(d.glob('app_*.sqlite3'))[:-keep]: o.unlink()
                        self.log.w(f'資料庫備份好了（{d}）')
            except Exception: self.log.err('資料庫備份')
            for _ in range(1800):
                if not self.alive(): return
                time.sleep(1)

    # ================================================================ 畫面／手機共用的狀態
    def info(self):
        if time.time() - self.info_c['t'] < 1.0: return self.info_c['v']
        v = {'demo_wait': len(self.demo_q), 'demo_run': len(self.demo_active), 'demo_done': self.demo_done[0],
             'items': int((self.db.one('SELECT COUNT(*) FROM items') or [0])[0] or 0), 'cpu': round(self.perf.cpu, 1), 'ram': round(self.perf.ram, 1),
             'fc': self.fc_counts(), 'busy': {k: self.bg_running(k) for k in self.FC_KINDS}, 'scan_q': len(self.fc_scan_q), 'bulk': dict(self.fc_bulk)}
        self.info_c = {'t': time.time(), 'v': v}; return v

    # ================================================================ FileCompare：掃描 → 比對重複 → 損毀檢查 → 隔離／復原（從來不刪檔）
    def ff(self):
        if not self._ff or not self._ff[0]: self._ff = fcore.find_ff(self.root)
        return self._ff

    def fc_kick(self):
        """資料變了：背景工作馬上重新找事做、統計數字重算."""
        self.fc_dirty[0] = time.time(); self.fc_cache['t'] = 0; self.info_c['t'] = 0

    # ---- 資料夾清單（roots＝要掃描的；keep_prio＝重複時優先保留，上面的優先）
    def fc_list(self, which): return [str(x) for x in (self.cfg.get(which) or [])]

    def fc_list_add(self, which, p):
        p = os.path.normpath(str(p)); L = self.fc_list(which)
        if any(path_key(x) == path_key(p) for x in L): return False, '已經在清單裡了'
        if which == 'roots':
            for r in L:
                if fcore.under(p, r): return False, f'已經包含在「{r}」裡面了'
                if fcore.under(r, p): return False, f'「{r}」在它裡面，請先移除那個（不能一個包一個）'
        L.append(p); self.cfg.set(which, L); self.log.w(f'清單 {which}：加入 {p}'); return True, '加好了'

    def fc_list_del(self, which, p):
        L = [x for x in self.fc_list(which) if path_key(x) != path_key(p)]; self.cfg.set(which, L); return True, '移除了（已經掃描的資料還在）'

    def fc_list_move(self, which, p, d):
        L = self.fc_list(which); i = next((k for k, x in enumerate(L) if path_key(x) == path_key(p)), -1)
        if i < 0: return L
        j = max(0, min(len(L) - 1, i + int(d))); L[i], L[j] = L[j], L[i]; self.cfg.set(which, L); return L

    # ---- 掃描
    def fc_scan_add(self, roots=None):
        R = [str(r) for r in (roots or self.fc_list('roots'))]; n = 0
        with self.lock:
            busy = {J['name'] for J in list(self.fc_active.values()) if J.get('kind') == 'scan'}
            if not self.fc_scan_q and not busy: self.fc_stat.update(done=0, total=0)
            for r in R:
                if r not in self.fc_scan_q and r not in busy: self.fc_scan_q.append(r); n += 1
            self.fc_stat['total'] = self.fc_stat.get('total', 0) + n
        self.log.w(f'掃描：排了 {n} 個資料夾'); return n

    UPSERT = ("INSERT INTO files(path,root,size,mtime,ext,kind,seen) VALUES(?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET root=excluded.root, seen=excluded.seen, "
              "qhash=CASE WHEN files.size=excluded.size AND files.mtime=excluded.mtime THEN files.qhash ELSE NULL END, "
              "hash=CASE WHEN files.size=excluded.size AND files.mtime=excluded.mtime THEN files.hash ELSE NULL END, "
              "health=CASE WHEN files.size=excluded.size AND files.mtime=excluded.mtime THEN files.health ELSE '' END, "
              "meta=CASE WHEN files.size=excluded.size AND files.mtime=excluded.mtime THEN files.meta ELSE 0 END, "
              "size=excluded.size, mtime=excluded.mtime, ext=excluded.ext, kind=excluded.kind")

    def _scan_boss(self):
        while self.alive():
            try:
                if self.fc_scan_q and not self.bg_hold('scan') and not self.bg_running('scan'):
                    with self.lock: r = self.fc_scan_q.popleft() if self.fc_scan_q else None
                    if r: self._scan_job(r); continue
                time.sleep(0.5)
            except Exception: self.log.err('掃描排程'); time.sleep(5)

    def _scan_job(self, r):
        key = ('scan', r); J = {'kind': 'scan', 'name': r, 'cancel': False}; self.fc_active[key] = J; self.bg_mark('scan', r)
        t = self.task('scan', f'掃描 {r}'); t0 = time.time(); scan_t = time.time(); B = []; n = 0; mo = self.cfg.get('media_only') is not False
        try:
            if not os.path.isdir(fcore.lp(r)): raise FileNotFoundError(f'找不到資料夾 {r}（硬碟沒接上？）')
            for p, size, mt, ext in fcore.walk(r):
                if J['cancel'] or self.stop_all: raise InterruptedError
                k = fcore.kind_of(ext)
                if mo and not k: continue
                B.append((p, r, size, mt, ext, k, scan_t)); n += 1
                if len(B) >= 2000: self.db.xm(self.UPSERT, B); B = []; t['msg'] = f'{n:,} 個檔…'; self.bg_mark('scan', f'{r}（{n:,} 個）')
            if B: self.db.xm(self.UPSERT, B)
            gone = self.db.x("DELETE FROM files WHERE root=? AND seen<? AND state IN ('','pkg','skip')", (r, scan_t))
            try: self.skip_mark()
            except Exception: self.log.err('🚫 標記不整理的資料夾')
            try: self.pkg_mark()
            except Exception: self.log.err('🎮 標記遊戲／軟體裡的檔')
            self.fc_stat['done'] = self.fc_stat.get('done', 0) + 1
            self.done(t, 'done', f'{n:,} 個檔，{fmt_t(time.time() - t0)}' + (f'，{gone:,} 個已經不在了（從清單拿掉）' if gone > 0 else ''))
            self.log.w(f'掃描完成：{r}　{n:,} 個檔　{time.time() - t0:.0f} 秒')
        except InterruptedError:
            with self.lock: self.fc_scan_q.appendleft(r)
            if B: self.db.xm(self.UPSERT, B)
            self.done(t, 'stop', f'停止（{n:,} 個，放回排隊）')
        except Exception as ex: self.log.err(f'掃描 {r}'); self.done(t, 'fail', str(ex)); self.fc_stat['done'] = self.fc_stat.get('done', 0) + 1
        finally: self.fc_active.pop(key, None); self.fc_kick()

    # ---- 共用：從資料庫拿工作 → 同時做幾個（比對重複、損毀檢查）
    def _pool_boss(self, kind, fetch, work, ncfg, ndef, title):
        Q = deque(); T = None; nxt = 0.0; seen = 0.0
        while self.alive():
            try:
                if self.bg_hold(kind): time.sleep(0.5); continue
                busy = self.bg_running(kind)
                if not Q and (time.time() >= nxt or self.fc_dirty[0] > seen):
                    seen = self.fc_dirty[0]; items = [x for x in fetch() if (kind, x['id']) not in self.fc_claim]
                    if items: Q.extend(items); nxt = 0.0
                    else: nxt = time.time() + (1 if busy else 30)                 # 還有在做的：做完可能會多出下一階段的工作
                R = self.fc_run.setdefault(kind, [0, 0])
                if Q and T is None: T = self.task(kind, title); R[0] = R[1] = 0
                if T is not None:
                    T['msg'] = f'{R[0]:,} 個' + (f'（{R[1]} 個讀不到）' if R[1] else '')
                    if not Q and not busy and nxt: self.done(T, 'done', T['msg']); T = None; self.fc_kick(); nxt = time.time() + 30; seen = self.fc_dirty[0]
                n = self.bg_cap(kind, max(1, min(16, int(self.cfg.get(ncfg) or ndef))))
                if Q and busy < n:
                    it = Q.popleft()
                    key = (kind, it['id'])
                    if key in self.fc_claim: continue
                    self.fc_claim.add(key); J = {'kind': kind, 'name': it['path'], 'cancel': False}; self.fc_active[key] = J
                    self.bg_mark(kind, it['path'])
                    threading.Thread(target=self._pool_job, args=(kind, work, it, J, key), name=kind.title() + 'Job', daemon=True).start(); continue
                time.sleep(0.03 if Q else 0.5)
            except Exception: self.log.err(f'背景工作排程（{kind}）'); time.sleep(5)
        if T is not None: self.done(T, 'stop', T.get('msg', '') + '（交給新版接著做）')

    def _pool_job(self, kind, work, it, J, key):
        R = self.fc_run.setdefault(kind, [0, 0])
        try:
            if not os.path.exists(fcore.lp(it['path'])): self.db.x("DELETE FROM files WHERE id=? AND state=''", (it['id'],)); R[1] += 1; return
            work(it, J); R[0] += 1
        except InterruptedError: pass
        except Exception: R[1] += 1; self.log.err(f'{kind}：{it.get("path")}')
        finally: self.fc_claim.discard(key); self.fc_active.pop(key, None)

    DUP_SIZES = "SELECT size FROM files WHERE state='' AND size>0 GROUP BY size HAVING COUNT(*)>1"
    DUP_Q = "SELECT size,qhash FROM files WHERE state='' AND qhash IS NOT NULL GROUP BY size,qhash HAVING COUNT(*)>1"

    def _hash_fetch(self):
        R = self.db.q(f"SELECT id,path,size FROM files INDEXED BY ix_todo_qhash WHERE state='' AND size>0 AND qhash IS NULL AND size IN ({self.DUP_SIZES}) ORDER BY path LIMIT 2000")
        if R: return [{'id': r['id'], 'path': r['path'], 'size': r['size'], 'st': 'q'} for r in R]
        R = self.db.q(f"SELECT id,path,size FROM files WHERE state='' AND hash IS NULL AND qhash IS NOT NULL AND (size,qhash) IN ({self.DUP_Q}) ORDER BY path LIMIT 100")
        return [{'id': r['id'], 'path': r['path'], 'size': r['size'], 'st': 'f'} for r in R]

    def _hash_work(self, it, J):
        try:
            if it['st'] == 'q':
                h = fcore.qhash(it['path'], it['size'])                          # 小檔（≤128 KB）頭尾就是整個檔，直接算完整指紋
                self.db.x('UPDATE files SET qhash=?, hash=CASE WHEN size<=? THEN ? ELSE hash END WHERE id=?', (h, fcore.HEAD * 2, h, it['id']))
            else:
                h = fcore.fhash(it['path'], lambda: J['cancel'] or self.stop_all); self.db.x('UPDATE files SET hash=? WHERE id=?', (h, it['id']))
        except OSError as ex:
            bad = '!' + str(it['id']); self.db.x('UPDATE files SET qhash=?, hash=? WHERE id=?', (bad, bad, it['id']))      # 讀不到：不跟別人配對
            self.fc_run.setdefault('hash', [0, 0])[1] += 1; self.log.w(f'比對重複：讀不到 {it["path"]}（{ex.strerror or ex}）')

    def _health_fetch(self):
        R = self.db.q("SELECT id,path,size,kind FROM files INDEXED BY ix_todo_health WHERE state='' AND health='' AND kind IN ('photo','video') ORDER BY path LIMIT 600")
        if not R and self.cfg.get('health_deep') is not False and self.ff()[0]:           # V0.1.04：之前檢查過的照片補算「綠色比例」
            R = self.db.q("SELECT id,path,size,kind FROM files INDEXED BY ix_todo_green WHERE state='' AND kind='photo' AND green=-1 AND health IN ('ok','partial') ORDER BY path LIMIT 600")
        return [dict(r) for r in R]

    def _health_work(self, it, J):
        ff, fp = self.ff(); deep = self.cfg.get('health_deep') is not False; dur = 0.0; g = -2.0
        try:
            if it['kind'] == 'video': st, msg, dur = fcore.check_video(it['path'], it['size'], ff, fp, deep)
            else: st, msg, g = fcore.check_photo_ex(it['path'], it['size'], ff, deep)
        except Exception as ex: st, msg = 'broken', f'檢查時出錯：{type(ex).__name__}: {ex}'
        if J['cancel'] and st == 'ok': raise InterruptedError
        self.db.x('UPDATE files SET health=?, health_msg=?, dur=CASE WHEN ?>0 THEN ? ELSE dur END, green=? WHERE id=?',
                  (st, (msg or '')[:500], float(dur or 0), float(dur or 0), g if g >= 0 else -2.0, it['id']))

    # ---- 統計（快取 10 秒；查詢在背景執行緒）
    def fc_counts(self, force=False):
        C = self.fc_cache
        if not force and time.time() - C['t'] < 10 and C['v']: return C['v']
        if not self.fc_cache_lock.acquire(blocking=not C['v']): return C['v']
        try:
            if not force and time.time() - C['t'] < 10 and C['v']: return C['v']
            o = lambda sql, a=(): tuple(self.db.one(sql, a) or ())
            a = o("SELECT COUNT(*), COALESCE(SUM(size),0), COALESCE(SUM(kind='photo'),0), COALESCE(SUM(kind='video'),0), COALESCE(SUM(health!=''),0), COALESCE(SUM(meta=1),0) FROM files WHERE state=''")
            h = o(f"SELECT COUNT(*), COALESCE(SUM(qhash IS NOT NULL),0) FROM files WHERE state='' AND size>0 AND size IN ({self.DUP_SIZES})")
            g = o("SELECT COUNT(*), COALESCE(SUM(size*(c-1)),0), COALESCE(SUM(c-1),0) FROM (SELECT size, COUNT(*) c FROM files WHERE state='' AND hash IS NOT NULL AND hash NOT LIKE '!%' GROUP BY size, hash HAVING c>1)")
            H = {r[0]: r[1] for r in self.db.q("SELECT health, COUNT(*) FROM files WHERE state='' AND keep=0 AND health IN ('broken','partial','zero') GROUP BY health")}
            kept = o("SELECT COUNT(*) FROM files WHERE state='' AND keep=1")[0]
            hb = o("SELECT COALESCE(SUM(size),0) FROM files WHERE state='' AND keep=0 AND health IN ('broken','partial','zero')")
            qz = o("SELECT COUNT(*), COALESCE(SUM(size),0) FROM files WHERE state='quar' AND path NOT LIKE ?", ('%' + fcore.CONV_QUAR_NAME + '%',))   # 不算轉檔後隔離區（V0.4.61）
            pk = o("SELECT COUNT(*), COALESCE(SUM(size),0) FROM files WHERE state='pkg'")
            sk = o("SELECT COUNT(*), COALESCE(SUM(size),0) FROM files WHERE state='skip'")
            rp = o("SELECT COALESCE(SUM(rep=1),0), COALESCE(SUM(rep IN (2,3)),0), COALESCE(SUM(rep=2),0) FROM files WHERE rep>0")
            ro = o('SELECT COUNT(*) FROM repairs')[0]
            v = {'files': a[0], 'bytes': a[1], 'photos': a[2], 'videos': a[3], 'media': a[2] + a[3], 'health_done': a[4], 'meta_done': a[5], 'hash_total': h[0], 'hash_done': h[1],
                 'pkg_n': pk[0], 'pkg_bytes': pk[1], 'skip_n': sk[0], 'skip_bytes': sk[1], 'dup_groups': g[0], 'dup_bytes': g[1], 'dup_files': g[2], 'broken': H.get('broken', 0), 'partial': H.get('partial', 0), 'zero': H.get('zero', 0),
                 'bad': sum(H.values()), 'kept': kept, 'rep_q': rp[0], 'rep_done': rp[1], 'rep_ok': rp[2], 'rep_outs': ro, 'quar_n': qz[0], 'quar_bytes': qz[1], 'ff': bool(self.ff()[0]), 't': time.strftime('%H:%M:%S')}
            v['bad_bytes'] = hb[0]
            self.fc_cache.update(t=time.time(), v=v)
            try: self._hist_snap(v)
            except Exception: pass
            return v
        except Exception:
            self.log.err('統計'); return C['v'] or {}
        finally: self.fc_cache_lock.release()

    # ---- 重複檔
    @staticmethod
    def _g(g):
        s, _, h = str(g).partition(':'); return int(s), h

    def fc_groups(self, offset=0, limit=100, kind='', folder=''):
        kf, a = (' AND kind=?', (kind,)) if kind in ('photo', 'video') else ('', ())
        hv = ''
        if folder:                                                                  # 📁 只看「有一份在這個資料夾裡」的重複（V0.1.65）
            fo = os.path.normpath(str(folder)).rstrip('\\/') + os.sep; hv = " AND SUM(path LIKE ? ESCAPE '^')>0"; a = a + (fcore.like_esc(fo) + '%',)
        R = self.db.q(f"SELECT size, hash, COUNT(*) c, MIN(path) p, MAX(kind) k FROM files WHERE state='' AND hash IS NOT NULL AND hash NOT LIKE '!%'{kf} "
                      f"GROUP BY size, hash HAVING c>1{hv} ORDER BY size*(c-1) DESC, p LIMIT ? OFFSET ?", a + (int(limit), int(offset)))
        return [{'g': f'{r["size"]}:{r["hash"]}', 'size': r['size'], 'n': r['c'], 'save': r['size'] * (r['c'] - 1), 'name': os.path.basename(r['p']),
                 'path': r['p'], 'kind': r['k']} for r in R]

    COPYISH = re.compile(r'\(\d+\)|（\d+）|副本|複本|拷貝|copy|_\d{1,2}$', re.I)

    def fc_rank(self, f, P):
        """建議保留哪一份：①在「優先保留」清單越上面的越好 ②檔名裡有拍攝日期（VID_20190512…；一模一樣的檔案裡面的日期也一樣，只能看檔名）
        ③檔名不像副本（(1)、副本、copy）④修改日期最早（最接近當初拍的時候，不是後來複製／傳輸的時間）⑤路徑短."""
        i = next((k for k, x in enumerate(P) if fcore.under(f['path'], x)), len(P))
        nd = f.get('name_date')
        if nd is None: nd = fcore.name_date(os.path.basename(f['path'])) or 0
        return (0 if f.get('fav') else 1, i, self.org_rank(f['path']), 0 if nd else 1, 1 if self.COPYISH.search(os.path.splitext(os.path.basename(f['path']))[0]) else 0, f.get('mtime') or 0, len(f['path']))

    def org_rank(self, path):
        """整理得多好（V0.2.24，越小越該留）：0 已經分類過／已篩選、1 在你整理過的資料夾包、2 一般、3 備份／整台倒出來的、4 救援出來的."""
        d = os.path.dirname(path); c = self.__dict__.setdefault('_orgc', {})
        if d in c: return c[d]
        lo = d.lower(); parts = [x for x in re.split(r'[\\/]', d) if x]
        if 'filecompare_分類' in lo: r = 0
        elif any(any(w in x.lower() for w in dupplan.LOW) for x in parts): r = 4
        else:
            try: pk = self.vg.pack_of(d)
            except Exception: pk = ''
            r = 1 if pk else (3 if any(vgroup.is_dump(x) for x in parts[1:]) else 2)
        if len(c) > 200000: c.clear()
        c[d] = r; return r

    def fc_group(self, g):
        size, h = self._g(g); P = self.fc_list('keep_prio')
        F = [dict(r) for r in self.db.q("SELECT id,path,size,mtime,kind,health,health_msg,dur,name_date,fav FROM files WHERE state='' AND size=? AND hash=? ORDER BY path", (size, h))]
        if F:
            best = min(F, key=lambda f: self.fc_rank(f, P))['id']
            for f in F:
                f['suggest'] = f['id'] == best; i = self.fc_rank(f, P)[1]
                f['prio'] = (i + 1) if i < len(P) else 0
        return F

    def fc_keep_group(self, g, keep_id, why='你選的'):
        F = self.fc_group(g); keep_id = int(keep_id)
        if len(F) < 2: return {'ok': False, 'message': '這組已經沒有重複了'}
        if keep_id not in {f['id'] for f in F}: return {'ok': False, 'message': '要保留的那份不在這組裡'}
        k = next(f for f in F if f['id'] == keep_id)
        if not os.path.exists(fcore.lp(k['path'])): return {'ok': False, 'message': f'要保留的那份不見了：{k["path"]}（先重新掃描）'}
        n = b = 0; err = []
        for f in F:
            if f['id'] == keep_id: continue
            ok, m = self.fc_quar(f['id'], '重複', f'保留 {k["path"]}（{why}）')
            if ok: n += 1; b += f['size']
            else: err.append(m)
        return {'ok': n > 0, 'moved': n, 'bytes': b, 'message': f'搬到隔離區 {n} 份（{fmt_b(b)}）' + (f'，{len(err)} 份失敗：{err[0]}' if err else '')}

    def fc_groups_n(self, kind='', folder=''):
        kf, a = (' AND kind=?', (kind,)) if kind in ('photo', 'video') else ('', ())
        hv = ''
        if folder: fo = os.path.normpath(str(folder)).rstrip('\\/') + os.sep; hv = " AND SUM(path LIKE ? ESCAPE '^')>0"; a = a + (fcore.like_esc(fo) + '%',)
        r = self.db.one(f"SELECT COUNT(*), COALESCE(SUM(s),0) FROM (SELECT size*(COUNT(*)-1) s FROM files WHERE state='' AND hash IS NOT NULL AND hash NOT LIKE '!%'{kf} GROUP BY size, hash HAVING COUNT(*)>1{hv})", a)
        return (r[0], r[1]) if r else (0, 0)

    def wizard(self):
        """🚀 整理精靈（V0.2.39）：建議的順序、每一步現在還剩多少（只讀，不做事）."""
        C = self.fc_counts(); S = []
        bad = C.get('bad') or 0
        S.append({'k': 'bad', 'ic': '🩺', 't': '損毀的先隔離', 'n': bad, 'b': C.get('bad_bytes') or 0, 'done': bad == 0, 'go': 'home', 'act': 'bad',
                  'd': f'{bad:,} 個打不開／部分損毀／0 位元組' if bad else '沒有損毀的了 ✔'})
        dc = getattr(self.dpl, 'c', None); res = dc[1] if dc else None
        if res:
            cp = [p for p in res['pairs'] if p['rel'] == 'copy']; ov = [p for p in res['pairs'] if p['rel'] != 'copy']
            S.append({'k': 'dpl', 'ic': '🧭', 't': '整包被複製的資料夾', 'n': len(cp) + len(ov), 'b': sum(p['bytes'] for p in res['pairs']), 'done': not res['pairs'], 'go': 'tool:dpl', 'act': 'dpl_all' if cp else '',
                      'd': f'整包複本 {len(cp)} 對、部分重複 {len(ov)} 對' if res['pairs'] else '沒有整包重複的資料夾了 ✔'})
        else:
            S.append({'k': 'dpl', 'ic': '🧭', 't': '整包被複製的資料夾', 'n': -1, 'b': 0, 'done': not C.get('dup_groups'), 'go': 'tool:dpl', 'act': '', 'd': '還沒分析：按「🔍 先分析」（幾秒到一分鐘）'})
        dg = C.get('dup_groups') or 0
        S.append({'k': 'dup', 'ic': '🔁', 't': '剩下零散的重複檔', 'n': dg, 'b': C.get('dup_bytes') or 0, 'done': dg == 0, 'go': 'tool:dup', 'act': 'dup_all' if dg else '',
                  'd': f'{dg:,} 組、可以省 {fmt_b(C.get("dup_bytes") or 0)}' if dg else '沒有重複的了 ✔'})
        try: P = self.vg.progress()
        except Exception: P = {}
        pk = P.get('packs', 0)
        S.append({'k': 'pk', 'ic': '📦', 't': '你整理過的資料夾整包處理', 'n': pk, 'b': 0, 'done': pk == 0 and self.vg._cache[1] is not None, 'go': 'tool:pk', 'act': '',
                  'd': f"{pk:,} 包（{P.get('pack_v', 0):,} 部影片）還沒審" if pk else ('都處理完了 ✔' if self.vg._cache[1] is not None else '計算中…')})
        todo = P.get('todo', 0)
        try:                                                                        # 🐾 電腦先看內容（V0.4.04）：貓狗 → Family、全黑 → Delete
            st = self.pet.status(); pn = self.pet.todo_count(); SC = {x['k']: x['n'] for x in st.get('scenes') or []}; jn = SC.get('dark', 0) + SC.get('flat', 0) + SC.get('still', 0)
            if st.get('run'): d_ = st.get('msg') or '看內容中…'
            elif not st.get('checked'): d_ = '電腦自己看每部影片裡有沒有貓狗、人、全黑誤錄的（Windows 內建，背景做）'
            else: d_ = (f'🐾 有貓狗還沒分 {pn:,} 部' if pn else '有貓狗的都分好了 ✔') + (f'、🌑 全黑／沒東西／沒動 {jn:,} 部' if jn else '')
            S.append({'k': 'pet', 'ic': '🐾', 't': '電腦先看內容（貓狗 → Family、誤錄 → Delete）', 'n': pn + jn, 'b': 0, 'done': bool(st.get('checked')) and not st.get('run') and pn + jn == 0,
                      'go': 'vc', 'act': ('' if st.get('run') else 'pet_start' if not st.get('checked') else 'pet_view' if pn else 'junk_view' if jn else ''), 'd': d_})
        except Exception: pass
        try:                                                                        # 💡 照你的習慣先一次分（V0.3.53）
            hs = self.vc.hint_summary() or {}; sn = hs.get('n', 0)
            S.append({'k': 'sug', 'ic': '💡', 't': '照你的習慣先一次分', 'n': sn, 'b': 0, 'done': todo > 0 and sn == 0 and hs != {}, 'go': 'vc', 'act': 'vc_sug' if sn else '',
                      'd': f"{sn:,} 部電腦有建議（同資料夾、同相機、檔名開頭、你的規則…）：只看那些，一路按 A 確認" if sn else '先自己分一些，電腦學會你的習慣後這裡會有建議'})
        except Exception: pass
        S.append({'k': 'vc', 'ic': '🧩', 't': '其他影片一組一組審', 'n': todo, 'b': 0, 'done': todo == 0, 'go': 'vc', 'act': 'vc_group',
                  'd': f"還沒審 {todo:,} 部" + (f"，照現在速度約 {P['eta'] / 3600:.1f} 小時" if P.get('eta') else '') if todo else '全部審完了 🎉'})
        wait = sum(c['wait'] for c in self.vc.cats())
        S.append({'k': 'mv', 'ic': '🚚', 't': '分好的搬進分類資料夾', 'n': wait, 'b': 0, 'done': wait == 0, 'go': 'vc', 'act': 'move' if wait else '',
                  'd': f'{wait:,} 部分好還沒搬' if wait else '沒有要搬的 ✔'})
        cur = next((i for i, s in enumerate(S) if not s['done']), len(S))
        return {'ok': True, 'steps': S, 'cur': cur, 'busy': bool(self.fc_bulk.get('run') or self.dpl.st.get('run') or self.vc.mv.get('run'))}

    def cap_summary(self):
        """🩺 容量健康（V0.2.15）：全部有多大、其中重複多出來的、損毀的、已經在隔離區的各佔多少."""
        c = self.fc_counts(); tot = (c.get('bytes') or 0) + (c.get('quar_bytes') or 0)
        dup = c.get('dup_bytes') or 0; bad = c.get('bad_bytes') or 0; q = c.get('quar_bytes') or 0
        return {'total': tot, 'dup': dup, 'dup_files': c.get('dup_files') or 0, 'bad': bad, 'bad_n': c.get('bad') or 0, 'quar': q, 'quar_n': c.get('quar_n') or 0,
                'ok': max(0, tot - dup - bad - q), 'run': bool(self.fc_bulk.get('run')), 'run_what': self.fc_bulk.get('what', ''), 'run_n': self.fc_bulk.get('n', 0)}

    def fc_bulk_start(self, kind='', folder=''):
        """「全部照建議處理」：每一組保留建議的那份，其他搬到隔離區（背景做，可以停）。folder＝只處理有一份在這個資料夾的."""
        if self.fc_bulk.get('run'): return False
        self.fc_bulk.clear(); self.fc_bulk.update(run=True, n=0, b=0, g=0, cancel=False, kind=kind, folder=folder)
        threading.Thread(target=self._bulk_job, args=(kind, folder), name='BulkDup', daemon=True).start(); return True

    def _bulk_job(self, kind, folder=''):
        B = self.fc_bulk; t = self.task('hash', '全部照建議處理重複檔' + ({'photo': '（照片）', 'video': '（影片）'}.get(kind, ''))); skip = set()
        self.log.w(f'重複檔：開始全部照建議處理（{kind or "全部"}）')
        try:
            while not B.get('cancel') and not self.stop_all:
                G = [x for x in self.fc_groups(0, 300 + len(skip), kind, folder) if x['g'] not in skip]
                if not G: break
                for x in G:
                    if B.get('cancel') or self.stop_all: break
                    F = self.fc_group(x['g']); best = next((f['id'] for f in F if f.get('suggest')), None)
                    if folder:                                                       # 清這個資料夾：別的地方有的就留別的地方那份（V0.1.65）
                        out = [f for f in F if not fcore.under(f['path'], folder)]
                        if out: P_ = self.fc_list('keep_prio'); best = min(out, key=lambda f: self.fc_rank(f, P_))['id']
                    r = self.fc_keep_group(x['g'], best, '全部照建議') if best else {'ok': False}
                    if r.get('moved'): B['n'] += r['moved']; B['b'] += r['bytes']
                    else: skip.add(x['g'])
                    B['g'] += 1; t['msg'] = f'{B["g"]:,} 組、搬了 {B["n"]:,} 份（{fmt_b(B["b"])}）'
            self.done(t, 'stop' if B.get('cancel') else 'done', t.get('msg') or '沒有要處理的'); self.oplog('全部照建議處理', t.get('msg', ''))
            self.log.w(f'重複檔：全部照建議處理結束　{t.get("msg")}')
        except Exception as ex: self.log.err('全部照建議處理'); self.done(t, 'fail', str(ex))
        finally: B['run'] = False; self.fc_kick()

    # ---- 損毀檢查的結果
    HF = {'bad': "health IN ('broken','partial','zero') AND keep=0", 'broken': "health='broken' AND keep=0", 'partial': "health='partial' AND keep=0",
          'zero': "health='zero' AND keep=0", 'kept': 'keep=1', 'ok': "health='ok'", 'todo': "health=''", 'repaired': 'rep=2', 'repq': 'rep=1',
          'green': "green>=0.25 AND keep=0"}

    def fc_quar_filter(self, flt, kind=''):
        """損毀檢查：這個篩選的檔案全部搬到隔離區（背景做；跟「全部照建議處理」共用同一個進度／停止）."""
        if self.fc_bulk.get('run'): return False
        if flt not in self.HF or flt in ('ok', 'todo', 'kept'): return False
        self.fc_bulk.clear(); self.fc_bulk.update(run=True, n=0, b=0, g=0, cancel=False, kind=kind, what='quar_filter')
        threading.Thread(target=self._quar_filter_job, args=(flt, kind), name='BulkQuar', daemon=True).start(); return True

    def _quar_filter_job(self, flt, kind):
        B = self.fc_bulk; w = self.HF[flt]; a = []
        if kind in ('photo', 'video'): w += ' AND kind=?'; a.append(kind)
        t = self.task('health', f'損毀：整個篩選搬到隔離區（{flt}）'); bad = 0
        try:
            while not B.get('cancel') and not self.stop_all:
                R = self.db.q(f"SELECT id, size, health_msg FROM files WHERE state='' AND {w} LIMIT 500", a)
                R = [r for r in R if r['id'] not in B.setdefault('skip', set())]
                if not R: break
                for r in R:
                    if B.get('cancel') or self.stop_all: break
                    ok, _m = self.fc_quar(r['id'], '損毀', r['health_msg'] or '')
                    if ok: B['n'] += 1; B['b'] += r['size'] or 0
                    else: bad += 1; B['skip'].add(r['id'])
                    t['msg'] = f'搬了 {B["n"]:,} 個（{fmt_b(B["b"])}）' + (f'，{bad} 個搬不動' if bad else '')
            self.done(t, 'stop' if B.get('cancel') else 'done', t.get('msg') or '沒有要搬的'); self.oplog('損毀：整個篩選搬到隔離區', t.get('msg', ''))
        except Exception as ex: self.log.err('損毀：整個篩選搬到隔離區'); self.done(t, 'fail', str(ex))
        finally: B['run'] = False; B.pop('skip', None); self.fc_kick()

    def fc_health_list(self, flt='bad', kind='', offset=0, limit=200):
        w = self.HF.get(flt, self.HF['bad']); a = []
        if kind in ('photo', 'video'): w += ' AND kind=?'; a.append(kind)
        n = (self.db.one(f"SELECT COUNT(*) FROM files WHERE state='' AND {w}", a) or [0])[0]
        R = self.db.q(f"SELECT id,path,size,mtime,kind,health,health_msg,dur,keep,rep,rep_msg FROM files WHERE state='' AND {w} ORDER BY path LIMIT ? OFFSET ?", a + [int(limit), int(offset)])
        return {'n': n, 'rows': [dict(r) for r in R]}

    def fc_decide(self, fid, a):
        """a：keep（留著，不再列出來）／unkeep（取消留著）／quar（搬到隔離區）."""
        fid = int(fid)
        if a == 'keep': self.db.x('UPDATE files SET keep=1 WHERE id=?', (fid,)); self.fc_kick(); return {'ok': True, 'message': '✔ 留著'}
        if a == 'unkeep': self.db.x('UPDATE files SET keep=0 WHERE id=?', (fid,)); self.fc_kick(); return {'ok': True, 'message': '取消留著'}
        if a == 'quar':
            r = self.db.one('SELECT health, health_msg FROM files WHERE id=?', (fid,)); ok, m = self.fc_quar(fid, '損毀', (r['health_msg'] if r else '') or '')
            return {'ok': ok, 'message': '📦 搬到隔離區了' if ok else m}
        return {'ok': False, 'message': '不認得的動作'}

    # ---- 隔離（搬到同一顆硬碟的 _FileCompare_待確認，可以復原）
    CONV_R = ('轉檔原檔', '影片瘦身（原檔）', '轉檔還原')                                          # 🗜 轉檔後隔離區的原因（舊版叫「影片瘦身（原檔）」）

    def fc_quar(self, fid, reason, note='', name=None):
        r = self.db.one("SELECT id,path FROM files WHERE id=? AND state=''", (int(fid),))
        if not r: return False, '找不到這個檔（可能已經處理過了）'
        src = r['path']
        try: dst = fcore.move(src, fcore.quar_dst(src, reason, name))
        except Exception as ex: self.oplog('隔離', f'失敗：{src}：{ex}', False); return False, f'搬不動：{ex}'
        try:
            self.db.x("UPDATE files SET state='quar', path=?, qpath=? WHERE id=?", (dst, src, r['id']))
            self.db.x('INSERT INTO moves(t,fid,src,dst,reason) VALUES(?,?,?,?,?)', (time.time(), r['id'], src, dst, reason + ('：' + note if note else '')))
        except Exception as ex:
            try: fcore.move(dst, src, rename=False)
            except Exception: self.log.err(f'隔離：資料庫寫不進去，檔案也搬不回去：{dst}')
            return False, f'資料庫寫不進去：{ex}'
        self.oplog('隔離', f'{reason}：{src} → {dst}'); self.fc_kick(); return True, dst

    def fc_gone_fix(self):
        """V0.5.77 永久刪除（Delete 分類）的檔已經不在了：那筆和它之前「分類：Delete」搬過去的紀錄標成 undone=2（不算在隔離區、不能復原）."""
        if getattr(self, '_gone_fixed', 0): return
        try:
            self.db.x("UPDATE moves SET undone=2 WHERE undone=0 AND fid IN (SELECT fid FROM moves WHERE reason LIKE '🗑 永久刪除%' AND fid IS NOT NULL)")
            self.db.x("UPDATE moves SET undone=2 WHERE undone=0 AND reason LIKE '🗑 永久刪除%'")
            self._gone_fixed = 1
        except Exception: self.log.err('隔離區：整理永久刪除的紀錄')

    def fc_moves(self, offset=0, limit=200, only_open=False, reason='', conv=False):
        self.fc_gone_fix()
        W = ["(" + ' OR '.join("reason LIKE ?" for _ in self.CONV_R) + ")" if conv else "NOT (" + ' OR '.join("reason LIKE ?" for _ in self.CONV_R) + ")"]; A = [x + '%' for x in self.CONV_R]   # 一般／轉檔後隔離區分開（V0.4.61）
        if only_open: W.append('undone=0')
        if reason: W.append("(reason=? OR reason LIKE ?)"); A += [reason, reason + '：%']
        w = (' WHERE ' + ' AND '.join(W)) if W else ''
        n = (self.db.one(f'SELECT COUNT(*) FROM moves{w}', A) or [0])[0]
        R = self.db.q(f'SELECT id,t,fid,src,dst,reason,undone FROM moves{w} ORDER BY id DESC LIMIT ? OFFSET ?', A + [int(limit), int(offset)])
        return {'n': n, 'rows': [dict(r) for r in R]}

    def fc_move_reasons(self, conv=False):
        """還在隔離區／搬過的，照原因分（V0.1.46）：[(原因, 幾筆, 最近一次)]."""
        C = {}; self.fc_gone_fix()
        for reason, n, t in self.db.q('SELECT reason, COUNT(*), MAX(t) FROM moves WHERE undone=0 GROUP BY reason'):
            k = (reason or '其他').split('：')[0]
            if (k in self.CONV_R) != bool(conv): continue
            x = C.setdefault(k, [0, 0]); x[0] += n; x[1] = max(x[1], t or 0)
        return sorted(([k, v[0], v[1]] for k, v in C.items()), key=lambda x: -x[2])

    def fc_undo_reason(self, reason):
        ids = [r[0] for r in self.db.q("SELECT id FROM moves WHERE undone=0 AND (reason=? OR reason LIKE ?)", (reason, reason + '：%'))]
        return self.fc_undo(ids) if ids else {'ok': False, 'message': '這一類沒有可以復原的'}

    def fc_undo(self, ids=None):
        """復原：從隔離區搬回原本的位置（原本的位置已經有檔案就不動）。ids=None＝全部."""
        if ids is None: R = self.db.q('SELECT id,fid,src,dst FROM moves WHERE undone=0 ORDER BY id DESC')
        else:
            ids = [int(x) for x in ids][:5000]
            R = [r for i in range(0, len(ids), 500) for r in self.db.q(f'SELECT id,fid,src,dst FROM moves WHERE undone=0 AND id IN ({",".join("?" * len(ids[i:i + 500]))})', ids[i:i + 500])]
        ok = 0; bad = []
        for m in R:
            if os.path.exists(fcore.lp(m['src'])): bad.append(f'原本的位置已經有檔案：{m["src"]}'); continue
            if not os.path.exists(fcore.lp(m['dst'])): bad.append(f'隔離區裡找不到（被刪掉了？）：{m["dst"]}'); continue
            try: fcore.move(m['dst'], m['src'], rename=False)
            except Exception as ex: bad.append(f'{m["dst"]}：{ex}'); continue
            try:
                self.db.x("UPDATE files SET state='', path=?, qpath='' WHERE id=?", (m['src'], m['fid'])); self.db.x('UPDATE moves SET undone=1 WHERE id=?', (m['id'],))
                self.db.x("UPDATE vc_tag SET moved=0, dst='' WHERE fid=?", (m['fid'],))           # 🎞 分類搬過去的復原：變回「分好、還沒搬」
            except Exception: self.log.err(f'復原：資料庫 {m["src"]}')
            ok += 1; fcore.rmdirs_up(os.path.dirname(m['dst']), fcore.quar_root(m['dst']))
        self.oplog('復原', f'{ok} 個' + (f'，{len(bad)} 個沒辦法' if bad else '')); self.log.w(f'復原：{ok} 個' + (f'，{len(bad)} 個沒辦法：{bad[0]}' if bad else ''))
        self.fc_kick(); return {'ok': ok > 0 or not bad, 'done': ok, 'bad': len(bad), 'message': f'復原了 {ok} 個' + (f'，{len(bad)} 個沒辦法：{bad[0]}' if bad else '')}

    # ---- 縮圖（快取在 Data\thumbs）
    def fc_file(self, fid):
        r = self.db.one('SELECT * FROM files WHERE id=?', (int(fid),)); return dict(r) if r else None

    def fc_thumb(self, fid, w=320):
        f = self.fc_file(fid)
        if not f or not f['size']: return None
        w = max(64, min(1600, int(w))); out = self.data / 'thumbs' / f'{int(fid) % 100:02d}' / f'{int(fid)}_{w}.jpg'
        if out.exists(): return str(out)
        t = (f['dur'] or 0) / 2 if f['kind'] == 'video' else 0.0
        if f['kind'] == 'video' and not t: t = 1.0
        return str(out) if fcore.make_thumb(self.ff()[0], f['path'], out, w, f['kind'], t) else None

    # ---- 讀取拍攝資訊（EXIF、影片標籤、檔名日期、來源、相似照片指紋）
    META_COLS = ('taken', 'date_src', 'name_date', 'make', 'model', 'software', 'w', 'h', 'mp', 'gps', 'lat', 'lon', 'src', 'vcodec', 'motion', 'dhash')

    def _meta_fetch(self):
        return [dict(r) for r in self.db.q("SELECT id,path,size,kind FROM files INDEXED BY ix_todo_meta WHERE state='' AND meta=0 AND kind IN ('photo','video') ORDER BY path LIMIT 800")]

    def _meta_work(self, it, J):
        ff, fp = self.ff()
        try: M = fcore.read_meta(it['path'], it['size'], it['kind'], ff, fp, self.cfg.get('meta_dhash') is not False)
        except Exception as ex:
            self.log.w(f'讀取拍攝資訊：{it["path"]}：{type(ex).__name__}: {ex}'); M = {'src': 'download', 'date_src': 'mtime'}
        if J['cancel'] and not M.get('taken'): raise InterruptedError
        vals = [M.get(k) for k in self.META_COLS]
        self.db.x(f"UPDATE files SET meta=1, {', '.join(k + '=?' for k in self.META_COLS)}, dur=CASE WHEN dur>0 THEN dur ELSE ? END WHERE id=?", vals + [float(M.get('mdur') or 0), it['id']])

    # ---- 🔎 搜尋篩選
    SRC_NM = fcore.SRC_NM
    DSRC_NM = {'exif': '照片 EXIF', 'video': '影片內建', 'name': '檔名', 'mtime': '只有修改日期（不可靠）', '': '還沒讀'}
    ORDERS = {'taken': 'COALESCE(taken, mtime), path', 'taken_desc': 'COALESCE(taken, mtime) DESC, path', 'path': 'path', 'size_desc': 'size DESC',
              'dur_desc': 'dur DESC', 'mp': 'mp, path'}

    @staticmethod
    def _ym(s, end=False):
        m = re.match(r'\s*(\d{4})(?:[-/.](\d{1,2}))?(?:[-/.](\d{1,2}))?', str(s or ''))
        if not m: return None
        y, mo, d = int(m.group(1)), int(m.group(2) or (12 if end else 1)), int(m.group(3) or 0)
        try:
            if end:
                if d: return time.mktime((y, mo, d, 23, 59, 59, 0, 0, -1))
                y2, m2 = (y + 1, 1) if mo == 12 else (y, mo + 1)
                return time.mktime((y2, m2, 1, 0, 0, 0, 0, 0, -1)) - 1
            return time.mktime((y, mo, d or 1, 0, 0, 0, 0, 0, -1))
        except (ValueError, OverflowError): return None

    def _where(self, F):
        F = dict(F or {}); W = ["state=''"]; A = []
        def add(sql, *a): W.append(sql); A.extend(a)
        if F.get('kind') in ('photo', 'video'): add('kind=?', F['kind'])
        S = [s for s in (F.get('src') or []) if s in self.SRC_NM]
        if S: add(f"src IN ({','.join('?' * len(S))})", *S)
        t1, t2 = self._ym(F.get('d1')), self._ym(F.get('d2'), True)
        if t1: add('COALESCE(taken, mtime)>=?', t1)
        if t2: add('COALESCE(taken, mtime)<=?', t2)
        ds = F.get('dsrc')
        if ds == 'reliable': add("date_src IN ('exif','video','name')")
        elif ds == 'mtime': add("date_src='mtime'")
        elif ds == 'conflict': add("date_src IN ('exif','video') AND name_date>0 AND ABS(taken-name_date)>86400*2")
        elif ds == 'todo': add('meta=0')
        if F.get('model'):
            for wd in str(F['model']).split(): add("(make || ' ' || model) LIKE ?", f'%{wd}%')
        if F.get('gps') in ('0', '1', 0, 1): add('gps=?', int(F['gps']))
        if F.get('motion') in ('1', 1): add('motion=1')
        if F.get('fav') in ('1', 1): add('fav=1')
        for wd in str(F.get('q') or '').split(): add('path LIKE ?', f'%{wd}%')
        if F.get('folder'): add("(path LIKE ? ESCAPE '^' OR path LIKE ? ESCAPE '^')", fcore.like_esc(os.path.normpath(str(F['folder'])).rstrip('\\')) + '\\%', fcore.like_esc(os.path.normpath(str(F['folder'])).rstrip('\\')) + '/%')
        H = [h for h in (F.get('health') or []) if h in ('ok', 'partial', 'broken', 'zero', 'todo')]
        if H: add(f"health IN ({','.join('?' * len(H))})", *['' if h == 'todo' else h for h in H])
        if F.get('dup') in ('1', 1): add("hash IS NOT NULL AND hash NOT LIKE '!%' AND (SELECT COUNT(*) FROM files f2 WHERE f2.state='' AND f2.hash=files.hash AND f2.size=files.size)>1")
        for k, col, mul in (('mp_min', 'mp', 1), ('size_min', 'size', 1e6), ('dur_min', 'dur', 1)):
            try:
                if F.get(k) not in (None, ''): add(f'{col}>=?', float(F[k]) * mul)
            except ValueError: pass
        for k, col, mul in (('mp_max', 'mp', 1), ('size_max', 'size', 1e6), ('dur_max', 'dur', 1)):
            try:
                if F.get(k) not in (None, ''): add(f'{col}<=?', float(F[k]) * mul)
            except ValueError: pass
        if F.get('mp_max') not in (None, ''): add('mp>0')
        return ' AND '.join(W), A

    def fc_search(self, F, offset=0, limit=200, order='taken'):
        w, a = self._where(F); ob = self.ORDERS.get(order, self.ORDERS['taken'])
        n = (self.db.one(f'SELECT COUNT(*), COALESCE(SUM(size),0) FROM files WHERE {w}', a) or [0, 0])
        R = self.db.q(f'SELECT id,path,size,mtime,kind,health,health_msg,dur,taken,date_src,make,model,software,w,h,mp,gps,src,motion,meta FROM files WHERE {w} ORDER BY {ob} LIMIT ? OFFSET ?',
                      a + [int(limit), int(offset)])
        return {'n': n[0], 'bytes': n[1], 'rows': [dict(r) for r in R]}

    def fc_facets(self, F=None):
        """目前條件下：每年幾個、來源、相機型號、日期從哪裡來、GPS、動態照片."""
        w, a = self._where(F or {}); q = lambda sql: [tuple(r) for r in self.db.q(sql, a)]
        return {'years': q(f"SELECT strftime('%Y', COALESCE(taken, mtime), 'unixepoch', 'localtime') y, COUNT(*) FROM files WHERE {w} GROUP BY y ORDER BY y"),
                'src': q(f'SELECT src, COUNT(*) FROM files WHERE {w} GROUP BY src ORDER BY COUNT(*) DESC'),
                'models': q(f"SELECT TRIM(make || ' ' || model) m, COUNT(*) FROM files WHERE {w} AND (make!='' OR model!='') GROUP BY m ORDER BY COUNT(*) DESC LIMIT 40"),
                'dsrc': q(f'SELECT date_src, COUNT(*) FROM files WHERE {w} GROUP BY date_src ORDER BY COUNT(*) DESC'),
                'gps': tuple(self.db.one(f'SELECT COALESCE(SUM(gps),0), COALESCE(SUM(motion),0), COUNT(*) FROM files WHERE {w}', a) or (0, 0, 0))}

    def fc_export_csv(self, F, out, order='taken'):
        import csv
        w, a = self._where(F); ob = self.ORDERS.get(order, self.ORDERS['taken']); n = 0
        cols = ['path', 'size', 'kind', 'taken', 'date_src', 'src', 'make', 'model', 'software', 'w', 'h', 'mp', 'dur', 'gps', 'lat', 'lon', 'motion', 'health', 'health_msg', 'hash']
        with open(out, 'w', newline='', encoding='utf-8-sig') as fh:
            wr = csv.writer(fh); wr.writerow(['路徑', '大小', '類型', '拍攝時間', '日期來源', '來源', '廠牌', '型號', '軟體', '寬', '高', '百萬畫素', '長度秒', 'GPS', '緯度', '經度', '動態照片', '狀態', '說明', '指紋'])
            for r in self.db.q(f'SELECT {",".join(cols)} FROM files WHERE {w} ORDER BY {ob}', a):
                d = dict(r); d['taken'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(d['taken'])) if d.get('taken') else ''
                d['src'] = self.SRC_NM.get(d['src'], d['src']); d['date_src'] = self.DSRC_NM.get(d['date_src'], d['date_src']); wr.writerow([d[c] for c in cols]); n += 1
        self.log.w(f'匯出 CSV：{n:,} 筆 → {out}'); return n

    # ---- 🛠 修復／救出（原檔不動；結果在 <磁碟>:\_FileCompare_修復結果）
    def fc_repair_add(self, ids=None, flt=None, kind=''):
        """排隊：ids＝指定的檔；flt＝損毀檢查的篩選（bad／broken／partial…）整批排."""
        if ids is not None:
            ids = [int(x) for x in ids][:20000]; n = 0
            for i in range(0, len(ids), 500):
                n += max(0, self.db.x(f"UPDATE files SET rep=1, rep_msg='' WHERE state='' AND size>0 AND id IN ({','.join('?' * len(ids[i:i + 500]))})", ids[i:i + 500]))
        else:
            w = self.HF.get(flt or 'bad', self.HF['bad']); a = []
            if kind in ('photo', 'video'): w += ' AND kind=?'; a.append(kind)
            n = self.db.x(f"UPDATE files SET rep=1, rep_msg='' WHERE state='' AND size>0 AND rep IN (0,3) AND {w}", a)
        self.log.w(f'修復／救出：排了 {n} 個'); self.fc_kick(); return n

    def _repair_fetch(self):
        """①你排的 ②🌙 自動修復：檢查出有問題、還沒修過的 ③🌙 自動隔離：之前修過、打不開的原檔."""
        R = self.db.q("SELECT id,path,size,kind,health,health_msg,keep FROM files INDEXED BY ix_todo_rep WHERE state='' AND rep=1 ORDER BY path LIMIT 50")
        if not R and self.cfg.get('auto_repair') is not False:
            R = self.db.q("SELECT id,path,size,kind,health,health_msg,keep FROM files WHERE state='' AND rep=0 AND keep=0 AND health IN ('broken','partial','zero') ORDER BY path LIMIT 50")
        if not R and self.cfg.get('auto_quar_broken') is not False:
            R = [dict(r, quar_only=1) for r in self.db.q("SELECT id,path,size,kind,health,health_msg,keep FROM files WHERE state='' AND rep IN (2,3) AND keep=0 AND health IN ('broken','zero') LIMIT 200")]
        return [dict(r) for r in R]

    def _auto_quar(self, it, msg=''):
        """🌙 自動隔離：打不開／0 位元組的原檔（能救的已經救到 _FileCompare_修復結果）搬到隔離區."""
        if self.cfg.get('auto_quar_broken') is False or it.get('keep') or it.get('health') not in ('broken', 'zero'): return
        ok, m = self.fc_quar(it['id'], '損毀', ((it.get('health_msg') or '') + ('；修復：' + msg if msg else ''))[:300])
        if not ok: self.log.w(f'自動隔離沒成功：{it["path"]}：{m}')

    def _known(self, size, h):
        """救出來的照片：你的硬碟上已經有一模一樣的了嗎？（同樣大小的才讀來比）."""
        for r in self.db.q("SELECT path, hash FROM files WHERE size=? AND state=''", (int(size),))[:20]:
            if r['hash'] == h: return r['path']
            try:
                if not r['hash'] and fcore.fhash(r['path']) == h: return r['path']
            except OSError: pass
        return None

    def _repair_work(self, it, J):
        if it.get('quar_only'): self._auto_quar(it); return
        ff, fp = self.ff()
        old = self.db.q('SELECT out FROM repairs WHERE fid=?', (it['id'],))
        if old: self.db.x('DELETE FROM repairs WHERE fid=?', (it['id'],))                  # 重做：舊的紀錄換掉（檔案留著，會被同名蓋掉）
        try: outs, msg = fcore.repair(it['path'], it['size'], it['kind'], ff, fp, lambda: J['cancel'] or self.stop_all, self._known)
        except InterruptedError: self.db.x("UPDATE files SET rep=1 WHERE id=?", (it['id'],)); raise
        except Exception as ex: outs, msg = [], f'出錯：{type(ex).__name__}: {ex}'; self.log.err(f'修復 {it["path"]}')
        now = time.time()
        if outs: self.db.xm('INSERT INTO repairs(fid,t,type,out,size,note) VALUES(?,?,?,?,?,?)', [(it['id'], now, o['type'], o['path'], o['size'], o['note']) for o in outs])
        self.db.x('UPDATE files SET rep=?, rep_msg=? WHERE id=?', (2 if outs else 3, msg[:400], it['id']))
        self.oplog('修復', f'{it["path"]}：{msg}')
        if 'health' not in it:
            r = self.db.one('SELECT health, health_msg, keep FROM files WHERE id=?', (it['id'],)); it.update(dict(r) if r else {})
        self._auto_quar(it, msg)
        # 重複檔：一模一樣的其他份不用再修一次，沿用這次的結果（打不開的一起搬到隔離區）
        h = (self.db.one('SELECT hash FROM files WHERE id=?', (it['id'],)) or [None])[0]
        if h and not str(h).startswith('!'):
            for s in self.db.q("SELECT id,path,size,health,health_msg,keep FROM files WHERE state='' AND hash=? AND size=? AND id!=? AND rep IN (0,1)", (h, it['size'], it['id'])):
                self.db.x('UPDATE files SET rep=?, rep_msg=? WHERE id=?', (2 if outs else 3, f'跟 {os.path.basename(it["path"])} 一模一樣：{msg}'[:400], s['id']))
                if outs: self.db.xm('INSERT INTO repairs(fid,t,type,out,size,note) VALUES(?,?,?,?,?,?)', [(s['id'], now, o['type'], o['path'], o['size'], o['note']) for o in outs])
                self._auto_quar(dict(s), '跟 ' + os.path.basename(it['path']) + ' 一模一樣，已經修過')

    def fc_repairs(self, fid):
        return [dict(r) for r in self.db.q('SELECT id,type,out,size,note FROM repairs WHERE fid=? ORDER BY id', (int(fid),))]

    def fc_rthumb(self, rid, w=320):
        r = self.db.one('SELECT out, type FROM repairs WHERE id=?', (int(rid),))
        if not r or not os.path.exists(fcore.lp(r['out'])): return None
        w = max(64, min(1600, int(w))); out = self.data / 'thumbs' / 'rep' / f'{int(rid)}_{w}.jpg'
        if out.exists(): return str(out)
        kind = 'video' if r['out'].lower().endswith('.mp4') else 'photo'
        return str(out) if fcore.make_thumb(self.ff()[0], r['out'], out, w, kind, 2.0 if kind == 'video' else 0) else None

    def fc_quar_many(self, ids, reason='手動'):
        ok = 0; err = []
        for i in list(ids)[:5000]:
            r, m = self.fc_quar(int(i), reason)
            if r: ok += 1
            else: err.append(m)
        return {'ok': ok > 0, 'moved': ok, 'message': f'搬到隔離區 {ok} 個' + (f'，{len(err)} 個失敗：{err[0]}' if err else '')}

    # ================================================================ 📈 資料分析（遊戲／軟體／程式專案整包算；照片影片的年份、來源）
    def ana_start(self):
        if self.bg_running('ana') or self.ana_st.get('req'): return False
        self.ana_st['req'] = True; self.log.w('📈 資料分析：排隊'); return True

    def ana_result(self):
        r = self.db.one("SELECT v FROM kv WHERE k='ana'")
        try: return json.loads(r[0]) if r and r[0] else {}
        except Exception: return {}

    def _ana_boss(self):
        while self.alive():
            try:
                A = self.ana_st
                if not A.get('req') and not A.get('auto') and self.fc_list('roots') and not self.fc_scan_q and not self.bg_running('scan'):
                    A['auto'] = True                                                      # 還沒分析過：自動做一次
                    if not self.ana_result(): A['req'] = True; self.log.w('📈 資料分析：還沒分析過，自動開始')
                if A.get('req') and not self.bg_hold('ana') and not self.bg_running('ana') and not self.fc_scan_q and not self.bg_running('scan'):
                    self._ana_job(); continue
                time.sleep(1.0)
            except Exception: self.log.err('資料分析排程'); time.sleep(5)

    def _ana_job(self):
        A = self.ana_st; key = ('ana', 'run'); J = {'kind': 'ana', 'name': '資料分析', 'cancel': False}; self.fc_active[key] = J
        t = self.task('ana', '📈 資料分析'); t0 = time.time(); prev = self.ana_result()
        A.update(done=0, total=int(prev.get('n') or 0), cur='')
        gen = int(time.time() * 1000); R = []; tot = {}; seen = [0]; P = []
        try:
            for root in self.fc_list('roots'):
                base = seen[0]
                def tick(n, path, base=base):
                    A['done'] = base + n; A['total'] = max(A['total'], A['done']); A['cur'] = path; self.bg_mark('ana', path); t['msg'] = f'{A["done"]:,} 個檔…'
                JK = ana.new_junk()
                try: r = ana.analyze(root, lambda: J['cancel'] or self.stop_all, tick, JK)
                except InterruptedError: raise
                except Exception as ex:
                    self.log.w(f'📈 資料分析：{root}：{ex}'); R.append({'root': root, 'err': str(ex), 'n': 0, 'b': 0, 'eff': {}}); continue
                seen[0] = base + r['files_seen']
                sx = lambda t: t.encode('utf-8', 'replace').decode('utf-8') if isinstance(t, str) else t     # 亂碼檔名（救援軟體留下的）：存成 �，不要整個存不進去
                rows = [(gen, sx(root), sx(x['path']), sx(x['parent']), x['depth'], x['b'], x['n'], json.dumps(x['eff']), x['pkg'], x['why'], json.dumps(x['raw']) if x['raw'] else '', x['mt'], 1 if x['kids'] else 0)
                        for x in r['rows'].values()]
                for i in range(0, len(rows), 2000): self.db.xm('INSERT INTO ana_dir(gen,root,path,parent,depth,b,n,eff,pkg,why,raw,mt,kids) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', rows[i:i + 2000])
                P += [sx(x['path']) for x in r['rows'].values() if x['pkg']]
                jr = [(gen, k, sx(p), b, m) for k, p, b, m in ana.junk_rows(JK)]
                for i in range(0, len(jr), 2000): self.db.xm('INSERT INTO ana_junk(gen,kind,path,b,mt) VALUES(?,?,?,?,?)', jr[i:i + 2000])
                for k, (n, b) in r['eff'].items():
                    x = tot.setdefault(k, [0, 0]); x[0] += n; x[1] += b
                R.append({'root': root, 'n': r['n'], 'b': r['b'], 'eff': r['eff'], 'raw': r['raw'], 'dirs': r['dirs'], 'sec': r['sec']})
            A['cur'] = '照片影片的年份、來源…'; t['msg'] = A['cur']
            pk = {}
            for typ, n, b in self.db.q("SELECT pkg, COUNT(*), SUM(b) FROM ana_dir WHERE gen=? AND pkg!='' GROUP BY pkg", (gen,)): pk[typ] = [n, b]
            S = {'gen': gen, 't0': t0, 't1': time.time(), 'sec': round(time.time() - t0, 1), 'roots': R, 'eff': tot, 'n': sum(x['n'] for x in R), 'b': sum(x['b'] for x in R),
                 'pkgs': pk, 'disks': self._ana_disks(), 'media': self._ana_media(P, J)}
            self.db.x('INSERT OR REPLACE INTO kv(k,v,t) VALUES(?,?,?)', ('ana', json.dumps(S, ensure_ascii=False), time.time()))
            self.db.x('DELETE FROM ana_dir WHERE gen!=?', (gen,)); self.db.x('DELETE FROM ana_junk WHERE gen!=?', (gen,)); A['req'] = False
            A['done'] = A['total'] = S['n']
            try: self.pkg_mark()
            except Exception: self.log.err('🎮 標記遊戲／軟體裡的檔')
            msg = f'{S["n"]:,} 個檔、{fmt_b(S["b"])}、找到 {sum(v[0] for v in pk.values()):,} 包遊戲／軟體…，{fmt_t(S["sec"])}'
            self.done(t, 'done', msg); self.log.w(f'📈 資料分析完成：{msg}'); self.oplog('資料分析', msg)
        except InterruptedError:
            self.db.x('DELETE FROM ana_dir WHERE gen=?', (gen,)); self.db.x('DELETE FROM ana_junk WHERE gen=?', (gen,)); self.done(t, 'stop', '停止（下次重新分析）')
        except Exception as ex:
            self.log.err('資料分析'); A['req'] = False; self.done(t, 'fail', str(ex))
            try: self.db.x('DELETE FROM ana_dir WHERE gen=?', (gen,))
            except Exception: pass
        finally: self.fc_active.pop(key, None); A['cur'] = ''

    def _ana_disks(self):
        """每一顆硬碟：全部、用了、還剩多少."""
        D = []; seen = set()
        for r in self.fc_list('roots'):
            drv = os.path.splitdrive(r)[0]
            if drv: m = drv + '\\'
            else:
                m = os.path.abspath(r)
                while not os.path.ismount(m) and os.path.dirname(m) != m: m = os.path.dirname(m)
            if m.lower() in seen: continue
            seen.add(m.lower())
            try: u = shutil.disk_usage(fcore.lp(m) if drv else m); D.append({'drive': m, 'total': u.total, 'used': u.used, 'free': u.free})
            except OSError: D.append({'drive': m, 'err': '讀不到（沒接上？）'})
        return D

    def _ana_media(self, pkgs, J):
        """照片影片（資料庫裡的）：每年幾個、來源；在遊戲／軟體資料夾裡的分開算（那些是素材，不是你的照片）."""
        P = {p.lower().rstrip('\\/') for p in pkgs}; sep = os.sep; Y = {}; SRC = {}; IN = {}; last = 0; nd = 0
        while True:
            if J['cancel'] or self.stop_all: raise InterruptedError
            rows = self.db.q("SELECT id, path, kind, size, src, COALESCE(taken, mtime) t FROM files WHERE state='' AND kind IN ('photo','video') AND id>? ORDER BY id LIMIT 20000", (last,))
            if not rows: break
            for r in rows:
                last = r['id']; s = r['path'].lower(); i = s.rfind(sep); hit = False
                while i > 0:
                    if s[:i] in P: hit = True; break
                    i = s.rfind(sep, 0, i)
                k = r['kind']; sz = r['size'] or 0
                if hit: x = IN.setdefault(k, [0, 0]); x[0] += 1; x[1] += sz; continue
                try: y = str(time.localtime(r['t']).tm_year) if r['t'] else '?'
                except (OverflowError, OSError, ValueError): y = '?'
                x = Y.setdefault(y, {}).setdefault(k, [0, 0]); x[0] += 1; x[1] += sz
                if k == 'photo' or k == 'video':
                    x = SRC.setdefault(r['src'] or '', [0, 0]); x[0] += 1; x[1] += sz
                nd += 1
        return {'years': Y, 'src': SRC, 'in_pkg': IN, 'n': nd}

    def ana_view(self):
        S = self.ana_result(); A = self.ana_st
        return {'res': S, 'run': bool(self.bg_running('ana')), 'req': bool(A.get('req')), 'done': A.get('done', 0), 'total': A.get('total', 0), 'cur': A.get('cur', ''),
                'pause': bool(self.bg_pause.get('ana')), 'cats': ana.CATS, 'src_nm': fcore.SRC_NM, 'roots': self.fc_list('roots')}

    def ana_dir(self, path=''):
        """樹狀圖：這個資料夾＋底下的資料夾；放不下的（小資料夾、這層的檔案）合成一塊「其他」。path＝''：最上層（每個要整理的資料夾）."""
        S = self.ana_result(); gen = S.get('gen')
        if not gen: return {'ok': False, 'message': '還沒分析過'}
        cols = 'path,parent,depth,b,n,eff,pkg,why,raw,mt,kids,root'
        dec = lambda r: dict(dict(r), eff=json.loads(r['eff'] or '{}'), raw=json.loads(r['raw'] or '{}') if r['raw'] else {})
        if not path:
            K = [dec(r) for r in self.db.q(f"SELECT {cols} FROM ana_dir WHERE gen=? AND parent='' ORDER BY b DESC", (gen,))]
            if len(K) == 1:                                                        # 只有一個要整理的資料夾：直接打開它（不然整張圖只有一大塊）
                r = self.ana_dir(K[0]['path'])
                if r.get('ok'): r['node']['parent'] = None
                return r
            node = {'path': '', 'b': sum(k['b'] for k in K), 'n': sum(k['n'] for k in K), 'eff': S.get('eff') or {}, 'pkg': '', 'why': '', 'parent': None}
            return {'ok': True, 'node': node, 'kids': K, 'rest': None}
        r = self.db.one(f'SELECT {cols} FROM ana_dir WHERE gen=? AND path=?', (gen, path))
        if not r: return {'ok': False, 'message': '找不到這個資料夾（重新分析看看）'}
        node = dec(r); K = [dec(x) for x in self.db.q(f'SELECT {cols} FROM ana_dir WHERE gen=? AND parent=? ORDER BY b DESC', (gen, path))]
        nk = len(K); K = K[:120]                                                   # 救援硬碟最上層常有幾千個資料夾（recup_dir.1…）：只畫最大的 120 個，其他的合成一塊
        rest = {k: list(v) for k, v in node['eff'].items()}
        for k in K:
            for c, (n, b) in k['eff'].items():
                if c in rest: rest[c][0] -= n; rest[c][1] -= b
        rest = {c: v for c, v in rest.items() if v[1] > 0}; rb = node['b'] - sum(k['b'] for k in K)
        return {'ok': True, 'node': node, 'kids': K, 'nk': nk, 'rest': {'b': rb, 'n': node['n'] - sum(k['n'] for k in K), 'eff': rest, 'more': nk - len(K)} if rb > 0 else None}

    def ana_pkgs(self, typ='', limit=1000):
        S = self.ana_result(); gen = S.get('gen')
        if not gen: return []
        w, a = ("pkg=?", [typ]) if typ in ana.PKG_TYPES else ("pkg!=''", [])
        return [dict(dict(r), raw=json.loads(r['raw'] or '{}') if r['raw'] else {}) for r in
                self.db.q(f'SELECT path,b,n,pkg,why,raw,mt,root FROM ana_dir WHERE gen=? AND {w} ORDER BY b DESC LIMIT ?', [gen] + a + [int(limit)])]

    # ================================================================ 🧹 雜物清理（V0.1.23）：資料分析時順便找到的；搬到隔離區（可以復原）
    def junk_view(self, kind='', limit=1500):
        S = self.ana_result(); gen = S.get('gen')
        if not gen: return {'ok': False, 'message': '還沒分析過：到總覽 → 📈 資料分析 →「🔄 重新分析」'}
        C = {r[0]: [r[1], r[2] or 0] for r in self.db.q('SELECT kind, COUNT(*), SUM(b) FROM ana_junk WHERE gen=? AND done=0 GROUP BY kind', (gen,))}
        rows = []
        if kind:
            o = 'b DESC' if kind == 'big' else 'path'
            rows = [dict(r) for r in self.db.q(f'SELECT rowid AS id, kind, path, b, mt FROM ana_junk WHERE gen=? AND kind=? AND done=0 ORDER BY {o} LIMIT ?', (gen, kind, int(limit)))]
        return {'ok': True, 'counts': C, 'rows': rows, 'kinds': ana.JUNK_KINDS, 't': S.get('t1'), 'run': self.junk_st.get('run', False), 'st': {k: v for k, v in self.junk_st.items() if k != 'err'}}

    def junk_quar(self, kind='', ids=None):
        """把雜物搬到隔離區（背景做）。ids＝只搬這幾個；沒給＝這一類全部（「最大的檔」不能整類搬，一定要選）."""
        if self.junk_st.get('run'): return {'ok': False, 'message': '已經在搬了'}
        if not ids and kind not in ('edir', 'efile', 'temp'): return {'ok': False, 'message': '最大的檔要一個一個選'}
        gen = self.ana_result().get('gen')
        if ids: R = [dict(r) for r in self.db.q(f"SELECT rowid AS id, kind, path, b FROM ana_junk WHERE done=0 AND rowid IN ({','.join('?' * len(ids[:5000]))})", [int(x) for x in ids[:5000]])]
        else: R = [dict(r) for r in self.db.q('SELECT rowid AS id, kind, path, b FROM ana_junk WHERE gen=? AND kind=? AND done=0', (gen, kind))]
        self.junk_st.clear(); self.junk_st.update(run=True, n=0, ok=0, bad=0, b=0, total=len(R), err=[])
        threading.Thread(target=self._junk_job, args=(R,), name='JunkMove', daemon=True).start()
        return {'ok': True, 'message': f'🧹 搬 {len(R):,} 個到隔離區（背景做）'}

    def _junk_job(self, R):
        M = self.junk_st; t = self.task('op', '🧹 雜物 → 隔離區'); NM = {k: n for k, _i, n in ana.JUNK_KINDS}
        try:
            for r in R:
                if self.stop_all: break
                M['n'] += 1; src = r['path']; why = '雜物：' + NM.get(r['kind'], r['kind'])
                try:
                    if r['kind'] == 'edir':
                        if not os.path.isdir(fcore.lp(src)): raise FileNotFoundError('已經不在了')
                        if any(True for _ in os.scandir(fcore.lp(src)) if not _.is_dir()): raise RuntimeError('裡面現在有檔案了，不搬')
                    dst = fcore.move(src, fcore.quar_dst(src, why))
                except Exception as ex:
                    M['bad'] += 1; M['err'].append(f'{os.path.basename(src)}：{ex}')
                    if isinstance(ex, FileNotFoundError): self.db.x('UPDATE ana_junk SET done=2 WHERE rowid=?', (r['id'],))
                    continue
                f = self.db.one("SELECT id FROM files WHERE path=? AND state=''", (src,))
                if f: self.db.x("UPDATE files SET state='quar', path=?, qpath=? WHERE id=?", (dst, src, f[0]))
                self.db.x('INSERT INTO moves(t,fid,src,dst,reason) VALUES(?,?,?,?,?)', (time.time(), f[0] if f else None, src, dst, why))
                self.db.x('UPDATE ana_junk SET done=1 WHERE rowid=?', (r['id'],)); M['ok'] += 1; M['b'] += r['b'] or 0; t['msg'] = f'{M["ok"]:,}／{M["total"]:,}'
            msg = f'搬了 {M["ok"]:,} 個（{fmt_b(M["b"])}）到隔離區' + (f'，{M["bad"]} 個沒辦法：{M["err"][0]}' if M['bad'] else '')
            self.done(t, 'done', msg); self.oplog('雜物清理', msg); self.log.w('🧹 ' + msg); M['msg'] = msg
        except Exception as ex: self.log.err('🧹 雜物'); self.done(t, 'fail', str(ex)); M['msg'] = str(ex)
        finally: M['run'] = False; self.fc_kick()

    # ================================================================ 🎮 遊戲／軟體資料夾裡的照片影片（V0.1.28）：state='pkg' → 所有工具都不列（關掉就恢復）
    def pkg_mark(self):
        """資料分析找到的一整包（遊戲、軟體、程式專案、系統）裡面的照片影片：標成 pkg（不是刪、也不是搬，只是不列）."""
        if self.cfg.get('skip_pkg') is False: return self.pkg_unmark()
        S = self.ana_result(); gen = S.get('gen')
        if not gen: return 0
        P = {r[0].lower().rstrip('\\/') for r in self.db.q("SELECT path FROM ana_dir WHERE gen=? AND pkg IN ('game','app','dev','system')", (gen,))}
        if not P: return 0
        sep = os.sep; hit = []
        for fid, p in self.db.q("SELECT id, path FROM files WHERE state=''"):
            s = p.lower(); i = s.rfind(sep)
            while i > 0:
                if s[:i] in P: hit.append((fid,)); break
                i = s.rfind(sep, 0, i)
        for i in range(0, len(hit), 5000): self.db.xm("UPDATE files SET state='pkg' WHERE id=? AND state=''", hit[i:i + 5000])
        if hit: self.log.w(f'🎮 遊戲／軟體資料夾裡的照片影片：{len(hit):,} 個不列入（素材）'); self.fc_cache['t'] = 0
        return len(hit)

    def pkg_unmark(self):
        n = self.db.x("UPDATE files SET state='' WHERE state='pkg'")
        if n: self.log.w(f'🎮 遊戲／軟體資料夾裡的照片影片：{n:,} 個恢復列入'); self.fc_cache['t'] = 0; self.fc_kick()
        return n

    # ================================================================ ⭐ 最愛（V0.1.43）：重複、相似的時候優先留這份；「⭐ 最愛」工具看全部
    def fav_set(self, fid, on):
        self.db.x('UPDATE files SET fav=? WHERE id=?', (1 if on else 0, int(fid))); return {'ok': True, 'on': bool(on), 'message': '⭐ 加到最愛' if on else '取消最愛'}

    def fav_get(self, fid):
        r = self.db.one('SELECT fav FROM files WHERE id=?', (int(fid),)); return bool(r and r[0])

    def favs(self, offset=0, limit=60, kind=''):
        w = "state='' AND fav=1" + (f" AND kind='{kind}'" if kind in ('photo', 'video') else '')
        n = (self.db.one(f'SELECT COUNT(*) FROM files WHERE {w}') or [0])[0]
        R = [dict(r) for r in self.db.q(f'SELECT id, path, kind, size, taken, mtime, dur FROM files WHERE {w} ORDER BY COALESCE(taken, mtime) DESC LIMIT ? OFFSET ?', (int(limit), int(offset)))]
        return {'ok': True, 'n': n, 'rows': R}

    # ================================================================ 📜 操作紀錄（V0.1.56）：程式做過什麼（搬檔、整理、復原、分析…）
    def ops(self, kind='', q='', offset=0, limit=200):
        W = []; A = []
        if kind: W.append('kind=?'); A.append(kind)
        if q: W.append('detail LIKE ?'); A.append(f'%{q}%')
        w = (' WHERE ' + ' AND '.join(W)) if W else ''
        n = (self.db.one(f'SELECT COUNT(*) FROM oplog{w}', A) or [0])[0]
        R = [dict(r) for r in self.db.q(f'SELECT id, t, kind, detail, ok FROM oplog{w} ORDER BY id DESC LIMIT ? OFFSET ?', A + [int(limit), int(offset)])]
        K = [(r[0], r[1]) for r in self.db.q('SELECT kind, COUNT(*) FROM oplog GROUP BY kind ORDER BY MAX(id) DESC')]
        return {'ok': True, 'n': n, 'rows': R, 'kinds': K}

    # ================================================================ 🚫 不要整理的資料夾（V0.1.62）：裡面的檔 state='skip'，所有工具都不列；移出清單就恢復
    def skip_mark(self):
        L = [os.path.normpath(p).rstrip('\\/') + os.sep for p in self.fc_list('skip_dirs')]
        n0 = self.db.x("UPDATE files SET state='' WHERE state='skip'")
        n = 0
        for p in L:
            n += max(0, self.db.x("UPDATE files SET state='skip' WHERE state='' AND path LIKE ? ESCAPE '^'", (fcore.like_esc(p) + '%',)))
        if n or n0: self.fc_cache['t'] = 0; self.fc_kick()
        if n != n0: self.log.w(f'🚫 不整理的資料夾：{n:,} 個檔不列入')
        return n

    # ================================================================ 📉 整理進度（V0.1.63）：每小時記一次，總覽畫成小折線
    def _hist_snap(self, v):
        now = time.time()
        if now - getattr(self, '_hist_t', 0) < 3600: return
        last = self.db.one('SELECT MAX(t) FROM stat_hist'); last = (last[0] if last else 0) or 0
        self._hist_t = now
        if now - last < 3600 or not v.get('files'): return
        tg = (self.db.one('SELECT COUNT(*) FROM vc_tag') or [0])[0]
        self.db.x('INSERT OR REPLACE INTO stat_hist(t, files, bytes, dup_b, quar_b, bad, tagged) VALUES(?,?,?,?,?,?,?)',
                  (now, v.get('files', 0), v.get('bytes', 0), v.get('dup_bytes', 0), v.get('quar_bytes', 0), v.get('bad', 0), tg))

    def hist(self, days=60):
        R = self.db.q('SELECT t, files, bytes, dup_b, quar_b, bad, tagged FROM stat_hist WHERE t>=? ORDER BY t', (time.time() - days * 86400,))
        D = {}
        for r in R: D[time.strftime('%Y-%m-%d', time.localtime(r['t']))] = dict(r)          # 每天留最後一筆
        return {'ok': True, 'rows': list(D.values())}

    def quar_drives(self):
        """📦 每顆硬碟的隔離區有多大（V0.1.85）：[(隔離區資料夾, 幾個, 大小)]."""
        D = {}
        for p, b in self.db.q("SELECT path, size FROM files WHERE state='quar'"):
            try: q = fcore.quar_root(p, fcore.CONV_QUAR_NAME if fcore.CONV_QUAR_NAME.lower() in p.lower() else None)
            except Exception: q = os.path.splitdrive(p)[0] or '?'
            x = D.setdefault(q, [0, 0]); x[0] += 1; x[1] += b or 0
        return sorted(([k, v[0], v[1]] for k, v in D.items()), key=lambda x: -x[2])

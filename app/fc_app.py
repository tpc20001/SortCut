"""主程式（PySide6）＝畫面殼。新程式的功能頁加在 PAGES／NavList.GROUPS，畫面只做畫面，重的事交給 core.Engine（背景執行緒）。

已經做好、不用再調的（給接手的 AI：不要重寫這些，只在需要時小改）：
  - 左邊分組選單（點分組標題收合）、左下電腦狀態（點了開📊效能浮窗）、上方 📊效能／🖥後台／🌙縮到背景／🏠封面、下方深色／淺色＋介面大小
  - 🖥 後台狀態：每一項背景工作 暫停／繼續／立刻停／先後順序／CPU 太忙自動讓路／慢慢加速；最近的工作
  - ⚙ 設定：一般、📱 手機網頁（PIN、Tailscale HTTPS 自己的埠）、資料夾；⟳ 版本與更新（熱更新，程式不用關）
  - 📜 LOG、🧪 實驗工作區（LAB_LIST）、📖 使用說明、托盤、只能開一個、閃退自動重開（看門狗）、畫面卡住記錄、Windows 關機不擋
"""
import os, sys, re, json, time, math, shutil, zipfile, threading, traceback, subprocess, faulthandler, importlib, importlib.util
from pathlib import Path
from collections import deque

from PySide6.QtCore import Qt, QTimer, QObject, Signal, Slot, QRect, QRectF, QPoint, QSize, QUrl, QEvent, qInstallMessageHandler
from PySide6.QtGui import QPainter, QColor, QPixmap, QIcon, QFont, QPen, QKeySequence, QShortcut, QDesktopServices, QPainterPath, QFontMetrics, QLinearGradient, QRadialGradient
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QListWidget, QListWidgetItem,
                               QSplitter, QStackedWidget, QScrollArea, QComboBox, QSpinBox, QCheckBox, QLineEdit, QFileDialog, QMessageBox, QTableWidget,
                               QTableWidgetItem, QHeaderView, QAbstractItemView, QProgressBar, QDialog, QMenu, QSystemTrayIcon, QFormLayout, QGroupBox,
                               QPlainTextEdit, QTextBrowser, QDialogButtonBox, QFrame, QSizePolicy, QStyledItemDelegate, QStyle, QRadioButton, QButtonGroup,
                               QListView, QTreeWidget, QTreeWidgetItem)

APP_VERSION = '0.4.62'
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fc_core as core  # noqa: E402
import fc_web as web  # noqa: E402
import fc_fcore as fcore  # noqa: E402
import fc_vsort as vsort  # noqa: E402
import fc_vgroup as vgroup  # noqa: E402
import fc_report as report  # noqa: E402
import fc_vslim as vslim  # noqa: E402
import fc_simi as simi  # noqa: E402
import fc_org as org  # noqa: E402
from collections import OrderedDict as OrderedDict_  # noqa: E402
from fc_core import fmt_t, fmt_b, BRAND  # noqa: E402

APP_TITLE = BRAND['title']
ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else HERE.parent
SELFTEST = bool(os.environ.get('APP_SELFTEST'))
SINGLE = f'{BRAND["id"]}_single_v1'
PKG_GLOB = f'{BRAND["prefix"]}_V*.zip'

# 🧪 實驗工作區：(代號, 名稱, 說明)。新推薦的功能先放這裡（預設關），使用者試過說好再變正式功能
LAB_LIST = []

# ============================================================ 🔗 嵌進 SortCut（VS 的「🗂 整理」）：EMBED['on'] 時不碰整個程式的樣式、托盤、看門狗、更新、封面
EMBED = {'on': False, 'msg': None, 'vs_root': None}


def _set_qss(qss):
    """樣式：嵌入時只套在 FileCompare 自己的畫面上（不影響 SortCut）."""
    if EMBED['on']:
        w = getattr(QApplication.instance(), '_fc_main', None)
        if type(w).__name__ == 'Main': w.setStyleSheet(qss)
    else: _set_qss(qss)

# ============================================================ 顏色、字型（深色／淺色同一套 token）
THEMES = {
    'dark': {'bg': '#0e1116', 'side': '#090c10', 'nav': '#0a0e13', 'panel': '#11161c', 'card': '#151a21', 'input': '#151a21', 'button': '#171d26', 'button_hover': '#222b37',
             'border': '#252c35', 'border_strong': '#2a3340', 'text': '#e8ecf2', 'text_strong': '#ffffff', 'subtext': '#8994a4', 'muted': '#7f8a99', 'nav_text': '#b9c2cf',
             'hover': '#161e28', 'header_bg': '#191f27', 'header_text': '#aeb7c4', 'grid': '#222933', 'alt_row': '#151a21', 'selection': '#263342', 'selection_text': '#ffffff',
             'scroll': '#3a4654', 'track': '#2a3038', 'accent': BRAND.get('accent', '#e51e63'), 'viewer_line': '#43d9ff', 'sub_accent': '#f0ad4e'},
    'light': {'bg': '#f3f5f8', 'side': '#e8ecf1', 'nav': '#e8ecf1', 'panel': '#ffffff', 'card': '#ffffff', 'input': '#ffffff', 'button': '#ffffff', 'button_hover': '#e7ecf2',
              'border': '#d5dce4', 'border_strong': '#c2cbd6', 'text': '#1b2430', 'text_strong': '#0b121a', 'subtext': '#5d6978', 'muted': '#6b7685', 'nav_text': '#334050',
              'hover': '#dde4ec', 'header_bg': '#eef1f5', 'header_text': '#3d4856', 'grid': '#e4e9ef', 'alt_row': '#f7f9fb', 'selection': '#d3e6fb', 'selection_text': '#0b121a',
              'scroll': '#b6c0cb', 'track': '#dfe5ec', 'accent': BRAND.get('accent', '#e51e63'), 'viewer_line': '#0a84c6', 'sub_accent': '#c77700'},
}
THEME = dict(THEMES['dark'])
THEME_MODE = {'mode': 'dark', 'zoom': 100}


def set_theme_mode(mode):
    mode = 'light' if str(mode) == 'light' else 'dark'
    THEME.clear(); THEME.update(THEMES[mode]); THEME_MODE['mode'] = mode
    return mode


def TC(key): return QColor(THEME.get(key, '#ff00ff'))


def theme_qss(mode=None, zoom=None):
    if mode is not None: set_theme_mode(mode)
    if zoom is not None: THEME_MODE['zoom'] = max(70, min(160, int(zoom)))
    t = THEME; fs = round(13 * THEME_MODE['zoom'] / 100); ac = t['accent']
    return f"""
QMainWindow,QWidget,QDialog{{background:{t['bg']};color:{t['text']};font-family:"Yu Gothic UI","Microsoft JhengHei","PingFang TC";font-size:{fs}px}}
QFrame#side{{background:{t['side']};border-right:1px solid {t['border']}}}
QLabel#title{{font-weight:800;font-size:{round(fs * 1.3)}px;color:{t['text_strong']}}} QLabel#sub,QLabel#muted{{color:{t['subtext']}}}
QLabel#ptitle{{font-weight:850;font-size:{round(fs * 1.35)}px;color:{t['text_strong']};background:transparent}}
QPushButton{{background:{t['button']};border:1px solid {t['border_strong']};border-radius:10px;padding:6px 12px;min-height:22px;color:{t['text']}}}
QPushButton:hover{{background:{t['button_hover']}}} QPushButton:disabled{{color:{t['muted']}}}
QPushButton:checked{{background:{t['selection']};border-color:{t['viewer_line']};color:{t['text_strong']}}}
QPushButton#start{{background:{ac};border:0;font-weight:900;min-height:32px;border-radius:12px;padding:6px 16px;color:#ffffff}}
QGroupBox{{border-radius:12px}} QTableWidget,QListWidget{{border-radius:10px}}
QPushButton#net_btn{{text-align:left;padding:5px 8px;border-radius:9px;background:{t['card']};border:1px solid {t['border']}}} QPushButton#net_btn:hover{{background:{t['button_hover']}}}
QPushButton#pill{{border-radius:11px;padding:2px 10px;font-size:{round(fs * 0.9)}px}}
QListWidget#workspace_nav{{background:{t['nav']};border:0;border-radius:9px;padding:2px 1px;outline:0}} QListWidget#workspace_nav::item{{border:0;background:transparent}}
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox{{background:{t['input']};border:1px solid {t['border_strong']};border-radius:7px;padding:4px 7px;color:{t['text_strong']}}}
QPlainTextEdit,QTextBrowser,QTextEdit{{background:{t['panel']};border:1px solid {t['border']};border-radius:8px;color:{t['text']}}}
QComboBox QAbstractItemView{{background:{t['panel']};color:{t['text']};selection-background-color:{t['selection']};selection-color:{t['selection_text']}}}
QMenu{{background:{t['panel']};color:{t['text']};border:1px solid {t['border']}}} QMenu::item{{padding:5px 18px}} QMenu::item:selected{{background:{t['selection']};color:{t['selection_text']}}}
QListWidget,QTreeWidget,QTableWidget,QTableView,QListView{{background:{t['panel']};border:1px solid {t['border']};border-radius:8px;alternate-background-color:{t['alt_row']};outline:0}}
QListWidget::item:selected,QTreeWidget::item:selected,QTableWidget::item:selected{{background:{t['selection']};color:{t['selection_text']}}}
QTableWidget,QTableView{{gridline-color:{t['grid']}}}
QHeaderView::section{{background:{t['header_bg']};color:{t['header_text']};padding:5px;border:0;font-weight:700}} QTableCornerButton::section{{background:{t['header_bg']};border:0}}
QFrame#card{{background:{t['card']};border:1px solid {t['border']};border-radius:11px}} QFrame#topbar{{background:{t['bg']};border-bottom:1px solid {t['border']}}}
QGroupBox{{background:{t['panel']};border:1px solid {t['border']};border-radius:11px;margin-top:16px;padding:10px 8px 8px 8px}}
QGroupBox::title{{subcontrol-origin:margin;left:12px;padding:0 4px;color:{ac};font-weight:800}}
QGroupBox QWidget{{background:transparent}} QGroupBox QLineEdit,QGroupBox QSpinBox,QGroupBox QComboBox{{background:{t['input']}}} QGroupBox QPushButton{{background:{t['button']}}}
QCheckBox,QRadioButton{{color:{t['text']};background:transparent}} QToolTip{{background:{t['panel']};color:{t['text']};border:1px solid {t['border']}}}
QStatusBar{{color:{t['subtext']};background:{t['bg']};border-top:1px solid {t['border']}}} QStatusBar QLabel{{background:transparent}}
QProgressBar{{border:0;border-radius:4px;text-align:center;background:{t['track']};color:{t['text_strong']};max-height:14px}} QProgressBar::chunk{{background:{t['viewer_line']};border-radius:4px}}
QTabWidget::pane{{border:1px solid {t['border']};border-radius:9px;top:-1px}} QTabBar::tab{{background:{t['panel']};border:1px solid {t['border']};padding:6px 14px;border-radius:8px;margin:2px;color:{t['subtext']}}}
QTabBar::tab:selected{{background:{t['selection']};color:{t['text_strong']};border-color:{t['viewer_line']}}}
QScrollArea{{border:0;background:transparent}}
QScrollBar:vertical{{background:transparent;width:8px}} QScrollBar::handle:vertical{{background:{t['scroll']};border-radius:4px;min-height:28px}}
QScrollBar:horizontal{{background:transparent;height:8px}} QScrollBar::handle:horizontal{{background:{t['scroll']};border-radius:4px;min-width:28px}}
QScrollBar::add-line,QScrollBar::sub-line{{width:0;height:0}} QScrollBar::add-page,QScrollBar::sub-page{{background:transparent}}
QSplitter::handle{{background:{t['border']}}}
"""


STYLE = theme_qss('dark', 100)


# ============================================================ 執行緒工具：bg(背景做, 回到畫面執行緒的 cb)、ui(交給畫面執行緒)
class Bus(QObject):
    call = Signal(object)

    def __init__(self):
        super().__init__(); self.call.connect(self._run, Qt.QueuedConnection)

    @Slot(object)
    def _run(self, fn):
        try: fn()
        except Exception:
            try: ENG.log.err('畫面更新')
            except Exception: pass


BUS = None
ENG = None


def ui(fn):
    """在畫面執行緒執行（從背景執行緒呼叫）."""
    BUS.call.emit(fn)


def bg(fn, cb=None, err=None):
    """在背景做 fn()，做完在畫面執行緒呼叫 cb(結果)。畫面上任何會讀硬碟／查資料庫／跑程式的動作都用這個（畫面才不會卡）."""
    def work():
        try: r = fn()
        except Exception as ex:
            r = ex
            try: ENG.log.err(f'背景工作 {getattr(fn, "__qualname__", fn)}')
            except Exception: pass
        if cb is not None: ui(lambda r=r: (cb(r) if not isinstance(r, Exception) else (err(r) if err else None)))
    threading.Thread(target=work, daemon=True).start()


def lab_cfg(): return dict(ENG.cfg.get('lab') or {})


def esc_html(t): return str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _ti(text, tip='', align=None, color=None):
    it = QTableWidgetItem(str(text)); it.setToolTip(str(tip or text))
    if align is not None: it.setTextAlignment(align)
    if color: it.setForeground(QColor(color))
    return it


def scroll_wrap(w):
    """每一頁包一層捲動：視窗太窄時出現捲軸，不會把視窗撐寬."""
    sa = QScrollArea(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.NoFrame); sa.setWidget(w); return sa


def note(text):
    l = QLabel(text); l.setObjectName('muted'); l.setWordWrap(True); return l


# ============================================================ 共用：縮圖、開檔、在資料夾中顯示
HEALTH_NM = {'ok': ('✔ 正常', '#45d483'), 'partial': ('◐ 部分損毀', '#f0ad4e'), 'broken': ('✖ 打不開', '#ff4d6d'), 'zero': ('∅ 0 位元組', '#ff4d6d'), '': ('… 還沒檢查', '#7f8a99')}


def open_file(p):
    try: QDesktopServices.openUrl(QUrl.fromLocalFile(str(p))); ENG.log.w(f'開啟：{p}')
    except Exception: ENG.log.err('開啟檔案')


def show_in_folder(p):
    try:
        if core.IS_WIN: subprocess.Popen(['explorer', '/select,', os.path.normpath(str(p))], creationflags=core.NO_WINDOW)
        else: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(p).parent)))
    except Exception: ENG.log.err('在資料夾中顯示')


def fmt_day(t):
    try: return time.strftime('%Y-%m-%d %H:%M', time.localtime(float(t)))
    except Exception: return ''


class Thumb(QLabel):
    """縮圖（背景用 FFmpeg 做，快取在 Data\\thumbs）。換成別的檔時，晚到的舊縮圖不會蓋上來."""
    def __init__(self, w=260, h=200):
        super().__init__(); self.W, self.H = w, h; self.fid = None; self.setFixedSize(w, h); self.setAlignment(Qt.AlignCenter); self.setWordWrap(True)
        self.setStyleSheet(f"QLabel{{background:{THEME['card']};border:1px solid {THEME['border']};border-radius:8px;color:{THEME['subtext']}}}")

    def load(self, fid, text='', rep=False):
        """rep=True：fid 是「修復／救出」結果的編號."""
        self.fid = (rep, fid); self.setPixmap(QPixmap()); self.setText(text or '載入預覽中…')
        if fid is None or text: return
        w = max(self.W, self.H) * 2 if max(self.W, self.H) <= 400 else 1280; key = self.fid
        bg(lambda: (ENG.fc_rthumb if rep else ENG.fc_thumb)(fid, w), lambda p, key=key: self._got(key, p))

    def _got(self, fid, p):
        try:
            if fid != self.fid: return
            pm = QPixmap(p) if p else QPixmap()
            if pm.isNull(): self.setText('沒辦法產生預覽\n（檔案可能壞掉，或缺 FFmpeg）'); return
            self.setPixmap(pm.scaled(self.W - 4, self.H - 4, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except RuntimeError: pass                                                    # 縮圖做好時，這張卡片已經被換掉了（換了一組），不用顯示


def pick_folder(parent, title):
    return QFileDialog.getExistingDirectory(parent, title, str(Path.home()))


# ============================================================ 🏠 總覽：資料夾、優先保留、進度
class KpiCard(QPushButton):
    """總覽的數字卡片（V0.1.41）：小標題、大數字、說明；點了到那一頁."""
    def __init__(self, icon, title, color, page, win):
        super().__init__(); self.setCursor(Qt.PointingHandCursor); self.setMinimumHeight(92); self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(f"QPushButton{{background:{THEME['card']};border:1px solid {THEME['border']};border-top:3px solid {color};border-radius:12px;text-align:left;padding:0}}"
                           f"QPushButton:hover{{border-color:{color}}}")
        v = QVBoxLayout(self); v.setContentsMargins(12, 8, 12, 8); v.setSpacing(1)
        self.t = QLabel(f'{icon} {title}'); self.t.setStyleSheet('color:#8994a4;font-size:12px;background:transparent;border:0')
        self.v = QLabel('—'); self.v.setStyleSheet('font-size:22px;font-weight:800;background:transparent;border:0'); self.v.setTextFormat(Qt.RichText)
        self.s = QLabel(''); self.s.setStyleSheet('color:#8994a4;font-size:11.5px;background:transparent;border:0'); self.s.setWordWrap(True)
        for w_ in (self.t, self.v, self.s): w_.setAttribute(Qt.WA_TransparentForMouseEvents); v.addWidget(w_)
        self.clicked.connect(lambda: win.nav.setCurrentRow(page))

    def set(self, val, sub=''): self.v.setText(val); self.s.setText(sub)


class HomePage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win
        v = QVBoxLayout(self); v.setContentsMargins(12, 12, 12, 12)
        t = QLabel(f'🏠 {APP_TITLE}'); t.setObjectName('title'); v.addWidget(t)
        v.addWidget(note('步驟：① 加入要整理的資料夾 → 按「▶ 開始掃描」（掃完會自動比對重複、檢查損毀）→ ② 設定重複時優先保留哪裡 → 到「🔁 重複檔」「🩺 損毀檢查」一個一個決定。\n'
                         '🔒 不會刪任何檔案：要處理的檔案只會搬到同一顆硬碟的「_FileCompare_待確認」資料夾（瞬間完成、不佔空間），在「📦 隔離區」隨時可以復原。你確認沒問題，再自己刪掉那個資料夾。'))
        kg = QGridLayout(); kg.setSpacing(8); v.addLayout(kg); self.kpi = {}
        for i, (k, ic, nm, col, pg) in enumerate((('all', '📁', '全部照片影片', '#4dc9ff', 11), ('dup', '🔁', '重複可以省', '#45d483', 2), ('bad', '🩺', '有問題', '#ff4d6d', 3),
                                                  ('vc', '🎞', '影片分類', '#b48cff', 12), ('meta', '🏷', '拍攝資訊', '#f0ad4e', 10), ('q', '📦', '隔離區', '#e5437f', 4))):
            self.kpi[k] = KpiCard(ic, nm, col, pg, win); kg.addWidget(self.kpi[k], i // 3, i % 3)
        self.info = QLabel('統計讀取中…'); self.info.setTextFormat(Qt.RichText); self.info.setWordWrap(True); self.info.setObjectName('card')
        self.info.setStyleSheet(f"QLabel{{background:{THEME['card']};border:1px solid {THEME['border']};border-radius:11px;padding:10px 12px}}"); v.addWidget(self.info)
        self.ffw = QLabel('⚠ 找不到 FFmpeg：沒辦法做縮圖和深度損毀檢查（重新跑 BUILD_AND_INSTALL.bat 會裝好）'); self.ffw.setStyleSheet('color:#f0ad4e'); self.ffw.hide(); v.addWidget(self.ffw)
        self.adv = QLabel(''); self.adv.setTextFormat(Qt.RichText); self.adv.setWordWrap(True); self.adv.hide(); self._adv_t = 0
        self.adv.setStyleSheet(f"QLabel{{background:{THEME['card']};border:1px solid {THEME['border']};border-radius:11px;padding:10px 12px}}"); v.addWidget(self.adv)
        self.adv.linkActivated.connect(self._adv_go)
        self.roots = self._list_box(v, 'roots', '① 要整理的資料夾（可以加很多個，不能一個包一個）', True)
        self.prio = self._list_box(v, 'keep_prio', '② 重複的時候優先保留哪裡（越上面越優先；例如手機原始的 DCIM 放最上面，「待整理」「備份」放下面）', False)
        self.skipd = self._list_box(v, 'skip_dirs', '🚫 ③ 不要整理的資料夾（裡面的檔案：重複、損毀、分類、相似…都不列、也不會被搬；移出清單就恢復）', False)
        g = QGroupBox('④ 背景工作（也可以在「🖥 後台狀態」暫停／調順序）'); gv = QVBoxLayout(g); v.addWidget(g)
        r = QHBoxLayout(); gv.addLayout(r); self.pb = {}
        for k, nm in (('scan', '掃描'), ('meta', '讀取拍攝資訊'), ('hash', '比對重複'), ('health', '損毀檢查'), ('repair', '修復')):
            b = QPushButton(); b.clicked.connect(lambda _c=False, k=k: (ENG.bg_set_pause(k, not ENG.bg_pause.get(k)), self.refresh())); r.addWidget(b); self.pb[k] = (b, nm)
        r.addStretch(1)
        f = QFormLayout(); gv.addLayout(f)
        self.hn = QSpinBox(); self.hn.setRange(1, 8); self.hn.setSuffix(' 個（傳統硬碟建議 1～2）'); self.qn = QSpinBox(); self.qn.setRange(1, 12); self.qn.setSuffix(' 個')
        self.deep = QCheckBox('損毀檢查用 FFmpeg 解碼（比較準、比較慢；關掉只檢查檔案結構）'); self.mo = QCheckBox('只看照片和影片（其他檔案不列入）')
        self.mn = QSpinBox(); self.mn.setRange(1, 12); self.mn.setSuffix(' 個'); self.dh = QCheckBox('讀取拍攝資訊時順便算「相似照片指紋」（之後找看起來一樣的照片用，每張多約 0.1 秒）')
        f.addRow('比對重複同時', self.hn); f.addRow('損毀檢查同時', self.qn); f.addRow('讀取拍攝資訊同時', self.mn); f.addRow(self.deep); f.addRow(self.dh); f.addRow(self.mo)
        self.pk = QCheckBox('🎮 遊戲／軟體／程式專案資料夾裡的照片影片（素材）不列入重複、損毀、分類、相似…（要先做過「資料分析」）'); f.addRow(self.pk)
        self.pk.toggled.connect(lambda on: (ENG.cfg.set('skip_pkg', bool(on)), threading.Thread(target=ENG.pkg_mark, daemon=True).start()))
        qh = QHBoxLayout(); self.qon = QCheckBox('🌙 這段時間不跑背景工作：'); self.qf = QSpinBox(); self.qt = QSpinBox()
        for sp in (self.qf, self.qt): sp.setRange(0, 23); sp.setSuffix(' 點')
        for w_ in (self.qon, self.qf, QLabel('到'), self.qt): qh.addWidget(w_)
        qh.addStretch(1); f.addRow(qh)
        self.qon.toggled.connect(lambda on: ENG.cfg.set('quiet_on', bool(on))); self.qf.valueChanged.connect(lambda x: ENG.cfg.set('quiet_from', int(x))); self.qt.valueChanged.connect(lambda x: ENG.cfg.set('quiet_to', int(x)))
        self.mn.valueChanged.connect(lambda x: ENG.cfg.set('meta_n', int(x))); self.dh.toggled.connect(lambda on: ENG.cfg.set('meta_dhash', bool(on)))
        self.ar = QCheckBox('🌙 自動修復：檢查出打不開／部分損毀的檔案，自動試著修復／救出（不用按 R）')
        self.aq = QCheckBox('🌙 自動隔離：打不開／0 位元組的原檔，修完（能救的先救到 _FileCompare_修復結果）自動搬到隔離區；部分損毀的不搬')
        self.rn = QSpinBox(); self.rn.setRange(1, 6); self.rn.setSuffix(' 個'); f.addRow('修復同時', self.rn); f.addRow(self.ar); f.addRow(self.aq)
        self.ar.toggled.connect(lambda on: ENG.cfg.set('auto_repair', bool(on))); self.aq.toggled.connect(lambda on: ENG.cfg.set('auto_quar_broken', bool(on)))
        self.rn.valueChanged.connect(lambda x: ENG.cfg.set('repair_n', int(x)))
        self.load()
        self.hn.valueChanged.connect(lambda x: ENG.cfg.set('hash_n', int(x))); self.qn.valueChanged.connect(lambda x: ENG.cfg.set('health_n', int(x)))
        self.deep.toggled.connect(lambda on: ENG.cfg.set('health_deep', bool(on))); self.mo.toggled.connect(lambda on: ENG.cfg.set('media_only', bool(on)))
        v.addStretch(1)
        self.tm = QTimer(self); self.tm.timeout.connect(self.refresh); self.tm.start(1500)

    def _list_box(self, v, which, title, scan):
        g = QGroupBox(title); gv = QVBoxLayout(g); v.addWidget(g)
        lw = QListWidget(); lw.setMinimumHeight(96); lw.setMaximumHeight(170); gv.addWidget(lw); r = QHBoxLayout(); gv.addLayout(r)
        ba = QPushButton('＋ 加入資料夾'); bd = QPushButton('－ 移除'); r.addWidget(ba); r.addWidget(bd)
        if scan:
            bs = QPushButton('▶ 開始掃描（全部）'); bs.setObjectName('start'); b1 = QPushButton('只掃選取的'); r.addWidget(bs); r.addWidget(b1)
            bs.clicked.connect(lambda: self._scan(None)); b1.clicked.connect(lambda: self._scan([it.text() for it in lw.selectedItems()]))
        else:
            bu = QPushButton('↑'); bdn = QPushButton('↓'); r.addWidget(bu); r.addWidget(bdn)
            bu.clicked.connect(lambda: self._move(lw, which, -1)); bdn.clicked.connect(lambda: self._move(lw, which, 1))
        r.addStretch(1)
        ba.clicked.connect(lambda: self._add(which)); bd.clicked.connect(lambda: self._del(lw, which)); lw.setSelectionMode(QAbstractItemView.ExtendedSelection)
        return lw

    def load(self):
        for lw, which in ((self.roots, 'roots'), (self.prio, 'keep_prio'), (self.skipd, 'skip_dirs')):
            sel = {it.text() for it in lw.selectedItems()}; lw.clear()
            for i, p in enumerate(ENG.fc_list(which)):
                it = QListWidgetItem(p); it.setToolTip(f'第 {i + 1} 優先' if which == 'keep_prio' else p); lw.addItem(it); it.setSelected(p in sel)
        for w_, val in ((self.hn, int(ENG.cfg.get('hash_n') or 2)), (self.qn, int(ENG.cfg.get('health_n') or 3)), (self.deep, ENG.cfg.get('health_deep') is not False), (self.mo, ENG.cfg.get('media_only') is not False),
                        (self.mn, int(ENG.cfg.get('meta_n') or 3)), (self.dh, ENG.cfg.get('meta_dhash') is not False), (self.pk, ENG.cfg.get('skip_pkg') is not False), (self.qon, bool(ENG.cfg.get('quiet_on'))), (self.qf, int(ENG.cfg.get('quiet_from') or 9)), (self.qt, int(ENG.cfg.get('quiet_to') or 23)),
                        (self.ar, ENG.cfg.get('auto_repair') is not False), (self.aq, ENG.cfg.get('auto_quar_broken') is not False), (self.rn, int(ENG.cfg.get('repair_n') or 2))):
            w_.blockSignals(True); (w_.setChecked(val) if isinstance(w_, QCheckBox) else w_.setValue(val)); w_.blockSignals(False)

    def _add(self, which):
        d = pick_folder(self, '選資料夾')
        if not d: return
        ok, m = ENG.fc_list_add(which, d); self.load(); self.win.msg(('✔ ' if ok else '⚠ ') + m)
        if ok and which == 'skip_dirs': threading.Thread(target=ENG.skip_mark, daemon=True).start()
        if ok and which == 'roots' and QMessageBox.question(self, '開始掃描', f'現在就掃描「{d}」？') == QMessageBox.Yes: self._scan([os.path.normpath(d)])

    def _del(self, lw, which):
        for it in lw.selectedItems(): ENG.fc_list_del(which, it.text())
        self.load()
        if which == 'skip_dirs': threading.Thread(target=ENG.skip_mark, daemon=True).start()

    def _move(self, lw, which, d):
        it = lw.currentItem()
        if it is None: return
        p = it.text(); ENG.fc_list_move(which, p, d); self.load()
        for i in range(lw.count()):
            if lw.item(i).text() == p: lw.setCurrentRow(i)

    def _scan(self, roots):
        if roots is not None and not roots: self.win.msg('先在清單選一個資料夾'); return
        if not ENG.fc_list('roots'): self.win.msg('先加入要整理的資料夾'); return
        n = ENG.fc_scan_add(roots); self.win.msg(f'排了 {n} 個資料夾要掃描（進度在上面和「🖥 後台狀態」）' if n else '這些資料夾已經在掃描／排隊中了'); self.refresh()

    ADV_PAGE = {'tool:dup': 2, 'tool:hl': 3, 'tool:q': 4, 'tool:sim': 14, 'tool:simv': 14, 'tool:burst': 14, 'tool:junk': 13, 'tool:slim': 19, 'tool:bak': 20, 'tool:osrc': 15, 'vc': 12, 'home': 11, 'set': 0}

    def _adv_go(self, k):
        if k == 'act:pet_start': ENG.pet.start(); self.win.msg('🐾 開始看內容（背景做，看完總覽會告訴你）', 5000); return
        if str(k).startswith('vc:'):                                                 # 「vc:篩選|名字」＝分類頁直接切到那個篩選（V0.3.77）
            self.win.nav.setCurrentRow(self.ADV_PAGE['vc'])
            try:
                f = self.win.vcp.flt; i = f.findData(str(k)[3:].split('|')[0])
                if i >= 0: f.setCurrentIndex(i)
            except Exception: pass
            return
        if k in self.ADV_PAGE: self.win.nav.setCurrentRow(self.ADV_PAGE[k])

    def _adv_got(self, j):
        R = j.get('rows') or []
        if not R: self.adv.setText("<span style='color:#45d483'>💡 目前沒有要特別處理的 ✔</span>"); self.adv.show(); return
        self.adv.setText('<b>💡 建議你接下來做</b>（照能省多少排，點連結過去）<br>' + '<br>'.join(
            f"{a['ic']} <b>{esc_html(a['title'])}</b>　<span style='color:#8994a4'>{esc_html(a['sub'])}</span>" + (f"　<a href='{a['go']}' style='color:#4dc9ff'>{esc_html(a['btn'] or '去看看')} ›</a>" if a['go'] in self.ADV_PAGE or str(a['go']).startswith(('vc:', 'act:')) else '') for a in R))
        self.adv.show()

    def refresh(self):
        if not self.isVisible(): return
        bg(ENG.info, self._got)
        if time.time() - self._adv_t > 60: self._adv_t = time.time(); bg(ENG.adv.get, self._adv_got); bg(ENG.vg.progress, lambda p: setattr(self, '_vprog', p))

    def _got(self, I):
        C = I.get('fc') or {}; B = I.get('busy') or {}
        if not C: return
        self.ffw.setVisible(not C.get('ff'))
        try:
            K = self.kpi; pc = lambda a_, b_: f'{round(100 * a_ / b_)}%' if b_ else '—'
            K['all'].set(f"{C['files']:,} 個", f"照片 {C['photos']:,}・影片 {C['videos']:,}・{fmt_b(C['bytes'])}")
            K['dup'].set(f"<span style='color:#45d483'>{fmt_b(C['dup_bytes'])}</span>", f"{C['dup_groups']:,} 組・比對 {pc(C['hash_done'], C['hash_total'])}")
            K['bad'].set(f"{C['broken'] + C['partial'] + C['zero']:,} 個", f"打不開 {C['broken']:,}・部分 {C['partial']:,}・0 位元組 {C['zero']:,}・檢查 {pc(C['health_done'], C['media'])}")
            cats = ENG.vc.cats(); tg = sum(c['n'] for c in cats); wt = sum(c['wait'] for c in cats)
            P_ = getattr(self, '_vprog', None) or {}
            eta = (f"・約 {P_['eta'] / 3600:.1f} 小時" if P_.get('eta', 0) >= 3600 else f"・約 {max(1, P_.get('eta', 0) // 60)} 分") if P_.get('eta') else ''
            K['vc'].set(f"✔ {tg:,} 部", f"分好 {pc(tg, C['videos'])}・還沒審 {P_.get('todo', 0):,}{eta}" + (f"・今天 {P_['today']:,}" if P_.get('today') else '') + (f"・待搬 {wt:,}" if wt else '')
                        + (f"<br>📦 {P_['packs']:,} 包整理過的資料夾還沒審" if P_.get('packs') else ''))
            K['meta'].set(pc(C.get('meta_done', 0), C['media']), f"{C.get('meta_done', 0):,}／{C['media']:,}")
            K['q'].set(f"{C['quar_n']:,} 個", f"{fmt_b(C['quar_bytes'])}・可以隨時復原")
        except Exception: pass
        sc = f"掃描中（還有 {I.get('scan_q', 0)} 個資料夾排隊）" if B.get('scan') else ''
        self.info.setText(
            f"📁 已掃描 <b>{C['files']:,}</b> 個檔（照片 {C['photos']:,}・影片 {C['videos']:,}，共 {fmt_b(C['bytes'])}）{('　<span style=color:#4dc9ff>' + sc + '</span>') if sc else ''}<br>"
            f"🏷 拍攝資訊（日期、來源、相機、相似照片指紋）：<b>{C.get('meta_done', 0):,}</b>／{C['media']:,}{'，進行中' if B.get('meta') else ''}　<span style=color:#8994a4>→ 到「🔎 搜尋篩選」用</span><br>"
            f"🔁 重複：<b>{C['dup_groups']:,}</b> 組、多出來 <b>{C['dup_files']:,}</b> 份，可以省 <b style=color:#45d483>{fmt_b(C['dup_bytes'])}</b>"
            f"　<span style=color:#8994a4>（比對進度 {C['hash_done']:,}／{C['hash_total']:,}{'，進行中' if B.get('hash') else ''}）</span><br>"
            f"🩺 損毀：打不開 <b style=color:#ff4d6d>{C['broken']:,}</b>・部分損毀 <b style=color:#f0ad4e>{C['partial']:,}</b>・0 位元組 <b>{C['zero']:,}</b>・已決定留著 {C['kept']:,}"
            f"　<span style=color:#8994a4>（檢查進度 {C['health_done']:,}／{C['media']:,}{'，進行中' if B.get('health') else ''}）</span><br>"
            + (f"🛠 修復／救出：排隊 {C.get('rep_q', 0):,}・試過 {C.get('rep_done', 0):,} 個・有救出東西 <b style=color:#45d483>{C.get('rep_ok', 0):,}</b> 個（共 {C.get('rep_outs', 0):,} 個結果）<br>"
               if C.get('rep_q') or C.get('rep_done') else '') +
            f"📦 隔離區：{C['quar_n']:,} 個（{fmt_b(C['quar_bytes'])}）"
            + (f"　🎮 遊戲／軟體裡的素材 {C.get('pkg_n', 0):,} 個不列入（{fmt_b(C.get('pkg_bytes', 0))}）" if C.get('pkg_n') else '')
            + f"　<span style=color:#8994a4>{C.get('t', '')} 更新</span>")
        for k, (b, nm) in self.pb.items():
            p = bool(ENG.bg_pause.get(k)); b.setText(f'▶ 繼續{nm}' if p else f'⏸ 暫停{nm}'); b.setStyleSheet('color:#ff4d6d' if p else '')


# ============================================================ 🔁 重複檔：一組一組看、選要保留哪一份
class DupPage(QWidget):
    PAGE = 100

    def __init__(self, win):
        super().__init__(); self.win = win; self.off = 0; self.G = []; self.cur = None; self.radios = {}
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r)
        self.kind = QComboBox(); self.kind.addItems(['全部', '只看照片', '只看影片']); self.sum = QLabel(''); self.sum.setObjectName('muted')
        bp = QPushButton('◀ 上一頁'); bn = QPushButton('下一頁 ▶'); br = QPushButton('🔄 重新整理'); self.ball = QPushButton('⚡ 全部照建議處理…'); self.bstop = QPushButton('⏹ 停止全部處理')
        self.fo = QLineEdit(); self.fo.setPlaceholderText('📁 只看這個資料夾裡的重複（空的＝全部；處理時留別的地方那份）'); self.fo.setMinimumWidth(260)
        self.fo.editingFinished.connect(lambda: (setattr(self, 'off', 0), self.reload()))
        for w_ in (self.kind, self.fo, bp, bn, br, self.ball, self.bstop): r.addWidget(w_)
        r.addWidget(self.sum, 1); self.bstop.hide()
        v.addWidget(note('同一組＝內容一模一樣（每個位元組都一樣，跟檔名無關）。⭐＝建議保留（照「總覽 ②優先保留」的順序，其次檔名不像副本、路徑短、比較早的）。'
                         '按「✔ 這組保留勾選的」：其他份搬到隔離區（可以復原）。'))
        sp = QSplitter(Qt.Horizontal); v.addWidget(sp, 1)
        self.tb = QTableWidget(0, 4); self.tb.setHorizontalHeaderLabels(['可以省', '份數', '類型', '檔名']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tb.horizontalHeader().setStretchLastSection(True); [self.tb.setColumnWidth(i, w) for i, w in enumerate((90, 50, 50))]; sp.addWidget(self.tb)
        rw = QWidget(); rv = QVBoxLayout(rw); rv.setContentsMargins(6, 0, 0, 0); sp.addWidget(rw)
        self.gt = QLabel('← 選一組'); self.gt.setObjectName('title'); self.gt.setWordWrap(True); rv.addWidget(self.gt)
        self.cw = QWidget(); self.grid = QGridLayout(self.cw); self.grid.setSpacing(10); sa = QScrollArea(); sa.setWidgetResizable(True); sa.setWidget(self.cw); rv.addWidget(sa, 1)
        rb = QHBoxLayout(); rv.addLayout(rb); self.bap = QPushButton('✔ 這組保留勾選的那份，其他搬到隔離區'); self.bap.setObjectName('start'); bnx = QPushButton('⏭ 先跳過，下一組')
        rb.addWidget(self.bap); rb.addWidget(bnx); rb.addStretch(1)
        sp.setSizes([380, 900])
        self.kind.currentIndexChanged.connect(lambda _i: (setattr(self, 'off', 0), self.reload())); br.clicked.connect(self.reload)
        bp.clicked.connect(lambda: (setattr(self, 'off', max(0, self.off - self.PAGE)), self.reload())); bn.clicked.connect(lambda: (setattr(self, 'off', self.off + self.PAGE), self.reload()))
        self.tb.itemSelectionChanged.connect(self._sel); self.bap.clicked.connect(self.apply); bnx.clicked.connect(self.next_group)
        self.ball.clicked.connect(self.bulk); self.bstop.clicked.connect(lambda: ENG.fc_bulk.update(cancel=True))
        self.tm = QTimer(self); self.tm.timeout.connect(self._tick); self.tm.start(2000); self._shown = False

    def kind_k(self): return {1: 'photo', 2: 'video'}.get(self.kind.currentIndex(), '')

    def showEvent(self, e):
        super().showEvent(e)
        if not self._shown: self._shown = True; self.reload()

    def _tick(self):
        if not self.isVisible(): return
        bg(ENG.info, self._sum)

    def _sum(self, I):
        C = I.get('fc') or {}; Bk = I.get('bulk') or {}
        run = bool(Bk.get('run')); self.bstop.setVisible(run); self.ball.setEnabled(not run)
        t = f"共 {C.get('dup_groups', 0):,} 組、可以省 {fmt_b(C.get('dup_bytes', 0))}　第 {self.off // self.PAGE + 1} 頁"
        if run: t += f"　⚡ 全部處理中：{Bk.get('g', 0):,} 組、搬了 {Bk.get('n', 0):,} 份（{fmt_b(Bk.get('b', 0))}）"
        if C.get('hash_total') and C.get('hash_done', 0) < C['hash_total']: t += f"　（還在比對：{C['hash_done']:,}／{C['hash_total']:,}）"
        self.sum.setText(t)

    def reload(self):
        k = self.kind_k(); off = self.off; fo = self.fo.text().strip(); bg(lambda: ENG.fc_groups(off, self.PAGE, k, fo), self._fill)

    def _fill(self, G):
        if not G and self.off > 0: self.off = max(0, self.off - self.PAGE); self.reload(); return
        self.G = G; self.tb.setRowCount(len(G))
        for i, g in enumerate(G):
            for j, val in enumerate((fmt_b(g['save']), str(g['n']), '🎞' if g['kind'] == 'video' else '🖼', g['name'])): self.tb.setItem(i, j, _ti(val, g['path'] if j == 3 else val))
        if G: self.tb.selectRow(0)
        else: self._clear('沒有重複的檔案' + ('（還在比對中，等一下再按 🔄）' if ENG.bg_running('hash') else '')); self._tick()

    def _clear(self, txt=''):
        self.cur = None; self.radios = {}; self.gt.setText(txt)
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget(): it.widget().deleteLater()

    def _sel(self):
        rows = self.tb.selectionModel().selectedRows()
        if not rows: return
        i = rows[0].row()
        if 0 <= i < len(self.G): g = self.G[i]; bg(lambda: ENG.fc_group(g['g']), lambda F, g=g: self._show(g, F))

    def _show(self, g, F):
        self._clear(f"{'🎞 影片' if g['kind'] == 'video' else '🖼 照片'}　{g['n']} 份一模一樣・每份 {fmt_b(g['size'])}・保留一份可以省 {fmt_b(g['save'])}")
        self.cur = g
        if len(F) < 2: self.gt.setText('這組已經沒有重複了（可能剛處理過）→ 按 🔄'); return
        cols = 3 if len(F) > 2 else 2
        for k, f in enumerate(F):
            card = QFrame(); card.setObjectName('card'); card.setStyleSheet('QLabel,QRadioButton{background:transparent}'); card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
            cv = QVBoxLayout(card); th = Thumb(250, 190); cv.addWidget(th, 0, Qt.AlignHCenter); th.load(f['id'])
            rb = QRadioButton(('⭐ 建議保留　' if f['suggest'] else '') + '保留這份'); rb.setChecked(bool(f['suggest'])); self.radios[f['id']] = rb; cv.addWidget(rb)
            pl = QLabel(esc_html(f['path'])); pl.setWordWrap(True); pl.setTextInteractionFlags(Qt.TextSelectableByMouse); cv.addWidget(pl)
            cv.addWidget(note(f"{fmt_day(f['mtime'])}" + (f"　優先順序 #{f['prio']}" if f.get('prio') else '　（不在優先保留清單）')))
            rr = QHBoxLayout(); bo = QPushButton('▶ 開啟'); bf = QPushButton('📂 位置'); rr.addWidget(bo); rr.addWidget(bf); rr.addStretch(1); cv.addLayout(rr)
            bo.clicked.connect(lambda _c=False, p=f['path']: open_file(p)); bf.clicked.connect(lambda _c=False, p=f['path']: show_in_folder(p))
            self.grid.addWidget(card, k // cols, k % cols, Qt.AlignTop)
        for rr_ in range(self.grid.rowCount() + 1): self.grid.setRowStretch(rr_, 0)
        self.grid.setRowStretch((len(F) - 1) // cols + 1, 1)
        grp = QButtonGroup(self.cw); [grp.addButton(b) for b in self.radios.values()]; self._grp = grp

    def apply(self):
        if not self.cur: return
        keep = next((fid for fid, b in self.radios.items() if b.isChecked()), None)
        if keep is None: self.win.msg('先勾選要保留哪一份'); return
        g = self.cur['g']; self.bap.setEnabled(False)
        bg(lambda: ENG.fc_keep_group(g, keep), self._applied)

    def _applied(self, r):
        self.bap.setEnabled(True); self.win.msg(('✔ ' if r.get('ok') else '⚠ ') + r.get('message', ''))
        if r.get('ok'): self._drop_current()

    def _drop_current(self):
        rows = self.tb.selectionModel().selectedRows(); i = rows[0].row() if rows else 0
        if 0 <= i < len(self.G): self.G.pop(i); self.tb.removeRow(i)
        if self.G: self.tb.selectRow(min(i, len(self.G) - 1))
        else: self.reload()

    def next_group(self):
        rows = self.tb.selectionModel().selectedRows(); i = rows[0].row() if rows else -1
        if i + 1 < len(self.G): self.tb.selectRow(i + 1)
        else: self.off += self.PAGE; self.reload()

    def bulk(self):
        k = self.kind_k(); C = ENG.fc_cache.get('v') or {}; P = ENG.fc_list('keep_prio')
        txt = (f"每一組都保留「⭐ 建議保留」那份，其他搬到隔離區（可以復原）。\n\n目前大約 {C.get('dup_groups', 0):,} 組、{C.get('dup_files', 0):,} 份、{fmt_b(C.get('dup_bytes', 0))}"
               f"{'（只處理' + self.kind.currentText()[2:] + '）' if k else ''}。\n\n優先保留順序：\n" + ('\n'.join(f'  {i + 1}. {p}' for i, p in enumerate(P)) or '  （還沒設定！會用：檔名不像副本 → 路徑短 → 比較早的）')
               + '\n\n建議先手動看幾組，確定「⭐ 建議」選得對再用這個。確定要全部處理？')
        if QMessageBox.question(self, '全部照建議處理', txt) != QMessageBox.Yes: return
        if self.fo.text().strip(): txt_ok = QMessageBox.question(self, '只處理這個資料夾', f'只處理「{self.fo.text().strip()}」裡的重複：別的地方也有的，搬走這個資料夾裡的那份。確定？') == QMessageBox.Yes
        else: txt_ok = True
        if txt_ok and ENG.fc_bulk_start(k, self.fo.text().strip()): self.win.msg('⚡ 開始全部處理（背景做，可以按「⏹ 停止全部處理」）'); self._tick()
        else: self.win.msg('已經在處理中了')


# ============================================================ 🩺 損毀檢查：一個一個看，決定留著或搬走
class HealthPage(QWidget):
    PAGE = 300
    FL = [('bad', '全部有問題的'), ('broken', '✖ 打不開'), ('partial', '◐ 部分損毀（可能還看得到）'), ('zero', '∅ 0 位元組'), ('kept', '✔ 已決定留著的'), ('todo', '… 還沒檢查的'),
          ('green', '🟩 畫面大半是綠色（救援沒救完整）'), ('repaired', '🛠 有救出東西的'), ('repq', '🛠 排隊修復中')]
    REP_NM = {1: '🛠 排隊中', 2: '🛠 有救出', 3: '🛠 沒救出'}

    def __init__(self, win):
        super().__init__(); self.win = win; self.off = 0; self.R = []; self.n = 0; self._shown = False
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10); r = QHBoxLayout(); v.addLayout(r)
        self.flt = QComboBox(); [self.flt.addItem(n, k) for k, n in self.FL]; self.kind = QComboBox(); self.kind.addItems(['照片＋影片', '只看照片', '只看影片'])
        bp = QPushButton('◀ 上一頁'); bn = QPushButton('下一頁 ▶'); br = QPushButton('🔄 重新整理'); self.sum = QLabel(''); self.sum.setObjectName('muted')
        for w_ in (self.flt, self.kind, bp, bn, br): r.addWidget(w_)
        r.addWidget(self.sum, 1)
        v.addWidget(note('快速鍵：K＝留著　D＝搬到隔離區　R＝試著修復／救出　→／空白＝下一個　←＝上一個　Enter＝用預設程式打開。\n'
                         '🛠 修復／救出：部分損毀的照片重新存成完整檔；影片重新包裝成能播的檔、每隔幾秒擷取畫面；「打不開」的檔案常常裡面藏著好幾張完整的照片（救援軟體混在一起存的），會挖出來。'
                         '原檔完全不動，結果放在同一顆硬碟的「_FileCompare_修復結果」；硬碟上已經有的照片不會重複存。'))
        sp = QSplitter(Qt.Horizontal); v.addWidget(sp, 1)
        self.tb = QTableWidget(0, 4); self.tb.setHorizontalHeaderLabels(['狀態', '檔名', '大小', '說明']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tb.horizontalHeader().setStretchLastSection(True); [self.tb.setColumnWidth(i, w) for i, w in enumerate((100, 200, 70))]; sp.addWidget(self.tb)
        rw = QWidget(); rv = QVBoxLayout(rw); rv.setContentsMargins(6, 0, 0, 0); sp.addWidget(rw)
        self.big = Thumb(720, 480); rv.addWidget(self.big, 0, Qt.AlignHCenter)
        self.meta = QLabel(''); self.meta.setWordWrap(True); self.meta.setTextFormat(Qt.RichText); self.meta.setTextInteractionFlags(Qt.TextSelectableByMouse); rv.addWidget(self.meta)
        rb = QHBoxLayout(); rv.addLayout(rb)
        self.bk = QPushButton('✔ 留著（K）'); self.bq = QPushButton('📦 搬到隔離區（D）'); self.bq.setObjectName('start'); bpv = QPushButton('⏮ 上一個'); bnx = QPushButton('⏭ 下一個')
        bo = QPushButton('▶ 打開（Enter）'); bf = QPushButton('📂 位置')
        for w_ in (self.bk, self.bq, bpv, bnx, bo, bf): rb.addWidget(w_)
        rb.addStretch(1)
        rr = QHBoxLayout(); rv.addLayout(rr); self.brp = QPushButton('🛠 試著修復／救出（R）'); self.brall = QPushButton('🛠 這個篩選全部試試看…'); self.brf = QPushButton('📂 打開救出的資料夾')
        self.bqall = QPushButton('📦 這個篩選全部搬到隔離區…'); self.bqstop = QPushButton('⏹ 停止搬移'); self.bqstop.hide()
        for w_ in (self.brp, self.brall, self.brf, self.bqall, self.bqstop): rr.addWidget(w_)
        self.bqall.clicked.connect(self.quar_all); self.bqstop.clicked.connect(lambda: ENG.fc_bulk.update(cancel=True))
        rr.addStretch(1)
        self.rl = QLabel(''); self.rl.setWordWrap(True); self.rl.setTextFormat(Qt.RichText); rv.addWidget(self.rl)
        self.rg = QGridLayout(); self.rg.setSpacing(6); rv.addLayout(self.rg); self.rth = []; self.rcap = []
        for k in range(8):
            t_ = Thumb(150, 112); t_.hide(); t_.setCursor(Qt.PointingHandCursor); c_ = QLabel(''); c_.setWordWrap(True); c_.setFixedWidth(150); c_.setObjectName('muted'); c_.hide()
            self.rg.addWidget(t_, (k // 4) * 2, k % 4); self.rg.addWidget(c_, (k // 4) * 2 + 1, k % 4, Qt.AlignTop); self.rth.append(t_); self.rcap.append(c_)
        rv.addStretch(1); sp.setSizes([480, 820]); self.reps = []
        self.brp.clicked.connect(self.repair_one); self.brall.clicked.connect(self.repair_all); self.brf.clicked.connect(self.open_rep)
        self.rt = QTimer(self); self.rt.timeout.connect(self._rep_tick); self.rt.start(3000)
        self.flt.currentIndexChanged.connect(lambda _i: (setattr(self, 'off', 0), self.reload())); self.kind.currentIndexChanged.connect(lambda _i: (setattr(self, 'off', 0), self.reload()))
        br.clicked.connect(self.reload); bp.clicked.connect(lambda: (setattr(self, 'off', max(0, self.off - self.PAGE)), self.reload()))
        bn.clicked.connect(lambda: (setattr(self, 'off', self.off + self.PAGE), self.reload()) if self.off + self.PAGE < self.n else None)
        self.tb.itemSelectionChanged.connect(self._sel); self.bk.clicked.connect(lambda: self.decide('unkeep' if self.flt.currentData() == 'kept' else 'keep'))
        self.bq.clicked.connect(lambda: self.decide('quar')); bnx.clicked.connect(lambda: self.step(1)); bpv.clicked.connect(lambda: self.step(-1))
        bo.clicked.connect(lambda: self.cur() and open_file(self.cur()['path'])); bf.clicked.connect(lambda: self.cur() and show_in_folder(self.cur()['path']))
        for ks, fn in (('K', lambda: self.bk.click()), ('D', lambda: self.decide('quar')), ('Right', lambda: self.step(1)), ('Space', lambda: self.step(1)), ('Left', lambda: self.step(-1)),
                       ('Return', lambda: self.cur() and open_file(self.cur()['path'])), ('R', self.repair_one)):
            sc = QShortcut(QKeySequence(ks), self); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(fn)

    def showEvent(self, e):
        super().showEvent(e)
        if not self._shown: self._shown = True; self.reload()
        self.setFocus()

    def kind_k(self): return {1: 'photo', 2: 'video'}.get(self.kind.currentIndex(), '')

    def reload(self):
        fl = self.flt.currentData(); k = self.kind_k(); off = self.off; self.bk.setText('↩ 取消留著（K）' if fl == 'kept' else '✔ 留著（K）')
        bg(lambda: ENG.fc_health_list(fl, k, off, self.PAGE), self._fill)

    def _fill(self, r):
        self.R = r['rows']; self.n = r['n']; self.tb.setRowCount(len(self.R))
        for i, f in enumerate(self.R): self._row(i, f)
        self.sum.setText(f"共 {self.n:,} 個　第 {self.off // self.PAGE + 1}／{max(1, (self.n + self.PAGE - 1) // self.PAGE)} 頁")
        if self.R: self.tb.selectRow(0)
        else: self.big.load(None, '這裡沒有檔案' + ('（還在檢查中）' if ENG.bg_running('health') else '')); self.meta.setText('')

    def _row(self, i, f):
        nm, col = HEALTH_NM.get(f['health'], (f['health'], None))
        rp = self.REP_NM.get(f.get('rep') or 0, '')
        for j, val in enumerate((('✔ 留著・' if f.get('keep') else '') + nm + ('・' + rp if rp else ''), os.path.basename(f['path']), fmt_b(f['size']),
                                 (f"{rp}：{f['rep_msg']}　" if f.get('rep_msg') else '') + (f['health_msg'] or ''))):
            self.tb.setItem(i, j, _ti(val, f['path'] if j == 1 else val, None, col if j == 0 else None))

    def cur(self):
        rows = self.tb.selectionModel().selectedRows(); i = rows[0].row() if rows else -1
        return self.R[i] if 0 <= i < len(self.R) else None

    def _sel(self):
        f = self.cur()
        if not f: return
        nm, col = HEALTH_NM.get(f['health'], (f['health'], '#ccc'))
        self.big.load(f['id'], '0 位元組：沒有內容可以預覽' if not f['size'] else '')
        self.meta.setText(f"<b style='color:{col}'>{nm}</b>　{esc_html(f['health_msg'] or '')}<br><b>{esc_html(os.path.basename(f['path']))}</b>　{fmt_b(f['size'])}　{fmt_day(f['mtime'])}"
                          + (f"　長度 {fmt_t(f['dur'])}" if f.get('dur') else '') + f"<br><span style='color:#8994a4'>{esc_html(os.path.dirname(f['path']))}</span>")
        self._show_rep(f)

    # ---- 🛠 修復／救出
    def _show_rep(self, f):
        rp = f.get('rep') or 0; self.brf.setEnabled(rp == 2)
        self.rl.setText({0: '', 1: '🛠 排隊修復中…（背景做，好了這裡會自動更新）', 3: f"🛠 試過了：{esc_html(f.get('rep_msg') or '')}"}.get(rp, ''))
        for t_ in self.rth + self.rcap: t_.hide()
        if rp != 2: self.reps = []; return
        fid = f['id']; bg(lambda: ENG.fc_repairs(fid), lambda R, fid=fid: self._got_rep(fid, R))

    def _got_rep(self, fid, R):
        f = self.cur()
        if not f or f['id'] != fid: return
        self.reps = R; nm = {'fixed': '修好的完整檔', 'frame': '擷取的畫面', 'carved': '挖出的照片', 'found': '找到的影片'}
        cnt = '、'.join(f"{nm[k]} {sum(1 for r in R if r['type'] == k)}" for k in nm if any(r['type'] == k for r in R))
        self.rl.setText(f"🛠 <b style='color:#45d483'>{esc_html(f.get('rep_msg') or '')}</b>　（{cnt}；點縮圖打開）")
        for k, t_ in enumerate(self.rth):
            if k < len(R):
                t_.show(); t_.load(R[k]['id'], rep=True); t_.setToolTip(R[k]['note'] + '\n' + R[k]['out'])
                t_.mousePressEvent = (lambda _e, p=R[k]['out']: open_file(p))
                self.rcap[k].setText(R[k]['note'].split('：')[0][:40]); self.rcap[k].setToolTip(R[k]['note']); self.rcap[k].show()
            else: t_.hide(); self.rcap[k].hide()

    def repair_one(self):
        f = self.cur()
        if not f: return
        if not f['size']: self.win.msg('0 位元組：裡面什麼都沒有，救不回來'); return
        bg(lambda: ENG.fc_repair_add([f['id']]), lambda n, f=f: (f.update(rep=1, rep_msg=''), self._row(self.R.index(f), f) if f in self.R else None, self._show_rep(f),
                                                               self.win.msg('🛠 排進修復了（在背景做）')))

    def repair_all(self):
        fl = self.flt.currentData(); k = self.kind_k()
        if fl in ('kept', 'ok', 'repaired', 'repq', 'todo') and QMessageBox.question(self, '全部試試看', f'目前的篩選是「{self.flt.currentText()}」，確定也要全部試？') != QMessageBox.Yes: return
        if QMessageBox.question(self, '全部試著修復／救出', f'把「{self.flt.currentText()}」的 {self.n:,} 個檔案排進修復？\n\n原檔完全不動，結果放在同一顆硬碟的「_FileCompare_修復結果」。'
                                '\n檔案多、影片大的話要很久（背景做，可以在「🖥 後台狀態」暫停）。') != QMessageBox.Yes: return
        bg(lambda: ENG.fc_repair_add(None, fl, k), lambda n: (self.win.msg(f'🛠 排了 {n:,} 個要修復／救出'), self.reload()))

    def quar_all(self):
        fl = self.flt.currentData(); k = self.kind_k()
        if fl in ('ok', 'todo', 'kept'): self.win.msg('這個篩選不能整批搬（先換成有問題的篩選）'); return
        if QMessageBox.question(self, '整個篩選搬到隔離區', f'把「{self.flt.currentText()}」的 {self.n:,} 個檔案全部搬到隔離區？\n\n'
                                '建議先往下翻幾個確認都是你不要的。搬過去之後在「📦 隔離區」都可以復原。') != QMessageBox.Yes: return
        if ENG.fc_quar_filter(fl, k): self.win.msg('📦 開始搬（背景做，可以按「⏹ 停止搬移」）')
        else: self.win.msg('已經有整批的工作在跑了')

    def open_rep(self):
        f = self.cur()
        if not f: return
        d = fcore.repair_dir(f['path'])
        if os.path.isdir(fcore.lp(d)): QDesktopServices.openUrl(QUrl.fromLocalFile(d))
        else: self.win.msg('還沒有救出的資料夾')

    def _rep_tick(self):
        """排隊修復中的那個做完了：更新畫面；整批搬移的進度."""
        if not self.isVisible(): return
        B = dict(ENG.fc_bulk); run = bool(B.get('run')); self.bqstop.setVisible(run); self.bqall.setEnabled(not run)
        if run and B.get('what') == 'quar_filter': self.win.msg(f"📦 整批搬到隔離區中：{B.get('n', 0):,} 個（{fmt_b(B.get('b', 0))}）", 4000)
        if getattr(self, '_was_run', False) and not run: self.reload()
        self._was_run = run
        f = self.cur()
        if not f or f.get('rep') != 1: return
        fid = f['id']; bg(lambda: ENG.fc_file(fid), lambda r, f=f: (r and r.get('rep') != 1) and (f.update(rep=r['rep'], rep_msg=r['rep_msg']), self._row(self.R.index(f), f) if f in self.R else None,
                                                                    self._show_rep(f) if self.cur() is f else None))

    def step(self, d):
        rows = self.tb.selectionModel().selectedRows(); i = (rows[0].row() if rows else -1) + d
        if 0 <= i < len(self.R): self.tb.selectRow(i)

    def decide(self, a):
        f = self.cur()
        if not f: return
        bg(lambda: ENG.fc_decide(f['id'], a), lambda r, f=f: self._decided(f, r))

    def _decided(self, f, r):
        self.win.msg(('' if r.get('ok') else '⚠ ') + r.get('message', '') + f'　{os.path.basename(f["path"])}')
        if not r.get('ok'): return
        i = next((k for k, x in enumerate(self.R) if x['id'] == f['id']), -1)
        if i < 0: return
        self.R.pop(i); self.tb.removeRow(i); self.n = max(0, self.n - 1)
        if self.R: self.tb.selectRow(min(i, len(self.R) - 1))
        else: self.reload()


# ============================================================ 🔎 搜尋篩選：用掃描時記下來的資訊找檔案（不用再讀硬碟）
DSRC_SHORT = {'exif': 'EXIF', 'video': '影片內建', 'name': '檔名', 'mtime': '⚠ 修改日期', '': '…'}


class SearchPage(QWidget):
    PAGE = 300
    HL = [('ok', '✔ 正常'), ('partial', '◐ 部分損毀'), ('broken', '✖ 打不開'), ('zero', '∅ 0 位元組'), ('todo', '… 還沒檢查')]
    DS = [('', '全部'), ('reliable', '日期可靠（EXIF／影片／檔名）'), ('mtime', '⚠ 只有修改日期（不可靠）'), ('conflict', '檔名日期和拍攝日期對不上'), ('todo', '還沒讀拍攝資訊')]
    OR = [('taken', '拍攝時間（舊→新）'), ('taken_desc', '拍攝時間（新→舊）'), ('path', '路徑'), ('size_desc', '檔案大小（大→小）'), ('dur_desc', '影片長度（長→短）'), ('mp', '解析度（小→大）')]

    def __init__(self, win):
        super().__init__(); self.win = win; self.off = 0; self.R = []; self.n = 0; self.F = {}; self._shown = False
        h = QHBoxLayout(self); h.setContentsMargins(10, 10, 10, 10)
        fw = QWidget(); fw.setMaximumWidth(330); fl = QFormLayout(fw); fl.setContentsMargins(0, 0, 6, 0); sa = QScrollArea(); sa.setWidgetResizable(True); sa.setWidget(fw); sa.setFixedWidth(345); h.addWidget(sa)
        self.q = QLineEdit(); self.q.setPlaceholderText('檔名或路徑裡的字（空白隔開＝都要有）'); fl.addRow('關鍵字', self.q)
        self.folder = QLineEdit(); self.folder.setPlaceholderText('只找這個資料夾底下'); bfd = QPushButton('…'); bfd.setFixedWidth(30); rf = QHBoxLayout(); rf.addWidget(self.folder); rf.addWidget(bfd); fl.addRow('資料夾', rf)
        self.kind = QComboBox(); self.kind.addItems(['照片＋影片', '只看照片', '只看影片']); fl.addRow('類型', self.kind)
        gs = QGroupBox('來源（不勾＝全部）'); gsv = QVBoxLayout(gs); self.srcs = {}
        for k, nm in fcore.SRC_NM.items(): cb = QCheckBox(nm); gsv.addWidget(cb); self.srcs[k] = cb
        fl.addRow(gs)
        self.d1 = QLineEdit(); self.d1.setPlaceholderText('2018 或 2018-05'); self.d2 = QLineEdit(); self.d2.setPlaceholderText('2019-12'); rd = QHBoxLayout(); rd.addWidget(self.d1); rd.addWidget(QLabel('到')); rd.addWidget(self.d2)
        fl.addRow('拍攝日期', rd); self.ds = QComboBox(); [self.ds.addItem(n, k) for k, n in self.DS]; fl.addRow('日期來源', self.ds)
        self.model = QComboBox(); self.model.setEditable(True); self.model.lineEdit().setPlaceholderText('例如 Xiaomi、RX100、iPhone'); fl.addRow('相機／手機', self.model)
        self.gps = QComboBox(); self.gps.addItems(['全部', '有定位（GPS）', '沒有定位']); fl.addRow('定位', self.gps)
        self.motion = QCheckBox('只看動態照片（照片裡有一小段影片）'); self.dup = QCheckBox('只看有重複的'); self.fav = QCheckBox('只看 ⭐ 最愛'); fl.addRow(self.motion); fl.addRow(self.dup); fl.addRow(self.fav)
        gh = QGroupBox('狀態（不勾＝全部）'); ghv = QVBoxLayout(gh); self.hls = {}
        for k, nm in self.HL: cb = QCheckBox(nm); ghv.addWidget(cb); self.hls[k] = cb
        fl.addRow(gh)
        def rng(ph1, ph2):
            a = QLineEdit(); a.setPlaceholderText(ph1); b = QLineEdit(); b.setPlaceholderText(ph2); r = QHBoxLayout(); r.addWidget(a); r.addWidget(QLabel('～')); r.addWidget(b); return a, b, r
        self.mp1, self.mp2, r1 = rng('最少', '最多'); fl.addRow('百萬畫素', r1)
        self.sz1, self.sz2, r2 = rng('MB', 'MB'); fl.addRow('檔案大小', r2)
        self.du1, self.du2, r3 = rng('秒', '秒'); fl.addRow('影片長度', r3)
        self.order = QComboBox(); [self.order.addItem(n, k) for k, n in self.OR]; fl.addRow('排序', self.order)
        rb = QHBoxLayout(); bs = QPushButton('🔎 搜尋'); bs.setObjectName('start'); bc = QPushButton('清除條件'); rb.addWidget(bs); rb.addWidget(bc); fl.addRow(rb)
        fl.addRow(note('小技巧：\n• 來源勾「手機縮圖快取」：手機自動產生的小縮圖，通常可以整批搬走。\n• 百萬畫素最多 0.3：很小的圖（多半是縮圖或網路下載的）。\n'
                       '• 日期來源選「只有修改日期」：這些檔案沒有拍攝時間，之後按年月整理時要特別看。'))
        rw = QWidget(); rv = QVBoxLayout(rw); rv.setContentsMargins(4, 0, 0, 0); h.addWidget(rw, 1)
        self.sum = QLabel('按「🔎 搜尋」'); self.sum.setWordWrap(True); self.sum.setTextFormat(Qt.RichText); rv.addWidget(self.sum)
        self.fac = QLabel(''); self.fac.setWordWrap(True); self.fac.setTextFormat(Qt.RichText); self.fac.setObjectName('muted'); rv.addWidget(self.fac)
        rt = QHBoxLayout(); rv.addLayout(rt); bp = QPushButton('◀ 上一頁'); bn = QPushButton('下一頁 ▶'); bo = QPushButton('▶ 開啟'); bf = QPushButton('📂 位置')
        bq = QPushButton('📦 選取的搬到隔離區…'); be = QPushButton('💾 匯出 CSV（全部符合的）'); self.pg = QLabel(''); self.pg.setObjectName('muted')
        for w_ in (bp, bn, self.pg, bo, bf, bq, be): rt.addWidget(w_)
        rt.addStretch(1)
        sp = QSplitter(Qt.Horizontal); rv.addWidget(sp, 1)
        self.tb = QTableWidget(0, 10); self.tb.setHorizontalHeaderLabels(['拍攝時間', '日期從', '來源', '相機／手機', '解析度', '長度', '大小', '狀態', '檔名', '資料夾'])
        self.tb.verticalHeader().setVisible(False); self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tb.setSelectionMode(QAbstractItemView.ExtendedSelection); self.tb.horizontalHeader().setStretchLastSection(True)
        for i, w in enumerate((125, 70, 110, 130, 85, 55, 70, 80, 200)): self.tb.setColumnWidth(i, w)
        sp.addWidget(self.tb); pw = QWidget(); pv = QVBoxLayout(pw); pv.setContentsMargins(6, 0, 0, 0); self.pre = Thumb(320, 260); pv.addWidget(self.pre)
        self.pm = QLabel(''); self.pm.setWordWrap(True); self.pm.setTextFormat(Qt.RichText); self.pm.setTextInteractionFlags(Qt.TextSelectableByMouse); pv.addWidget(self.pm); pv.addStretch(1)
        sp.addWidget(pw); sp.setSizes([900, 330])
        bs.clicked.connect(lambda: self.search(True)); bc.clicked.connect(self.clear); self.q.returnPressed.connect(lambda: self.search(True))
        bfd.clicked.connect(lambda: (lambda d: d and self.folder.setText(os.path.normpath(d)))(pick_folder(self, '只找這個資料夾底下')))
        bp.clicked.connect(lambda: (setattr(self, 'off', max(0, self.off - self.PAGE)), self.search(False)))
        bn.clicked.connect(lambda: (setattr(self, 'off', self.off + self.PAGE), self.search(False)) if self.off + self.PAGE < self.n else None)
        self.tb.itemSelectionChanged.connect(self._sel); self.tb.itemDoubleClicked.connect(lambda _it: self.cur() and open_file(self.cur()['path']))
        bo.clicked.connect(lambda: self.cur() and open_file(self.cur()['path'])); bf.clicked.connect(lambda: self.cur() and show_in_folder(self.cur()['path']))
        bq.clicked.connect(self.quar); be.clicked.connect(self.export)

    def showEvent(self, e):
        super().showEvent(e)
        if not self._shown: self._shown = True; self.search(True)

    def reload(self):
        if self._shown: self.search(False)

    def filters(self):
        F = {'q': self.q.text().strip(), 'folder': self.folder.text().strip(), 'kind': {1: 'photo', 2: 'video'}.get(self.kind.currentIndex(), ''),
             'src': [k for k, cb in self.srcs.items() if cb.isChecked()], 'd1': self.d1.text().strip(), 'd2': self.d2.text().strip(), 'dsrc': self.ds.currentData(),
             'model': self.model.currentText().strip().split('（')[0].strip(), 'gps': {1: '1', 2: '0'}.get(self.gps.currentIndex(), ''), 'motion': '1' if self.motion.isChecked() else '', 'fav': '1' if self.fav.isChecked() else '',
             'dup': '1' if self.dup.isChecked() else '', 'health': [k for k, cb in self.hls.items() if cb.isChecked()]}
        for k, w_ in (('mp_min', self.mp1), ('mp_max', self.mp2), ('size_min', self.sz1), ('size_max', self.sz2), ('dur_min', self.du1), ('dur_max', self.du2)): F[k] = w_.text().strip()
        return F

    def clear(self):
        for w_ in (self.q, self.folder, self.d1, self.d2, self.mp1, self.mp2, self.sz1, self.sz2, self.du1, self.du2): w_.clear()
        for cb in list(self.srcs.values()) + list(self.hls.values()) + [self.motion, self.dup, self.fav]: cb.setChecked(False)
        for c_ in (self.kind, self.ds, self.gps, self.order): c_.setCurrentIndex(0)
        self.model.setEditText(''); self.search(True)

    def search(self, fresh=True):
        if fresh: self.off = 0; self.F = self.filters()
        F = dict(self.F); off = self.off; order = self.order.currentData(); self.sum.setText('搜尋中…')
        bg(lambda: (ENG.fc_search(F, off, self.PAGE, order), ENG.fc_facets(F) if fresh else None), self._got)

    def _got(self, r):
        res, fac = r; self.R = res['rows']; self.n = res['n']; self.tb.setRowCount(len(self.R))
        for i, f in enumerate(self.R):
            hn, hc = HEALTH_NM.get(f['health'], (f['health'], None))
            vals = (fmt_day(f['taken']) if f.get('taken') else '', DSRC_SHORT.get(f.get('date_src') or '', f.get('date_src')), fcore.SRC_NM.get(f.get('src') or '', '…').split(' ', 1)[-1][:10],
                    (f"{f.get('make') or ''} {f.get('model') or ''}").strip(), f"{f['w']}×{f['h']}" if f.get('w') else '', fmt_t(f['dur']) if f.get('dur') else '', fmt_b(f['size']), hn,
                    os.path.basename(f['path']), os.path.dirname(f['path']))
            for j, val in enumerate(vals): self.tb.setItem(i, j, _ti(val, f['path'] if j >= 8 else val, None, hc if j == 7 else ('#f0ad4e' if j == 1 and f.get('date_src') == 'mtime' else None)))
        pages = max(1, (self.n + self.PAGE - 1) // self.PAGE); self.pg.setText(f'第 {self.off // self.PAGE + 1}／{pages} 頁')
        self.sum.setText(f"找到 <b>{self.n:,}</b> 個，共 <b>{fmt_b(res['bytes'])}</b>")
        if fac:
            yrs = '　'.join(f"{y or '?'}：{n:,}" for y, n in fac['years']); srcs = '　'.join(f"{fcore.SRC_NM.get(s or '', '… 還沒讀')}：{n:,}" for s, n in fac['src'])
            ds = '　'.join(f"{ENG.DSRC_NM.get(s or '', s)}：{n:,}" for s, n in fac['dsrc']); g = fac['gps']
            self.fac.setText(f'📅 {yrs}<br>📥 {srcs}<br>🕒 日期從：{ds}<br>📍 有定位 {g[0]:,}・動態照片 {g[1]:,}')
            cur = self.model.currentText(); self.model.blockSignals(True); self.model.clear(); self.model.addItem('')
            for m, n in fac['models']: self.model.addItem(f'{m}（{n:,}）')
            self.model.setEditText(cur); self.model.blockSignals(False)
        if self.R: self.tb.selectRow(0)
        else: self.pre.load(None, '沒有符合的檔案'); self.pm.setText('')

    def cur(self):
        rows = self.tb.selectionModel().selectedRows(); i = rows[0].row() if rows else -1
        return self.R[i] if 0 <= i < len(self.R) else None

    def _sel(self):
        f = self.cur()
        if not f: return
        self.pre.load(f['id'], '' if f['size'] else '0 位元組')
        hn, hc = HEALTH_NM.get(f['health'], (f['health'], '#ccc'))
        self.pm.setText(f"<b>{esc_html(os.path.basename(f['path']))}</b><br>{fmt_b(f['size'])}" + (f"　{f['w']}×{f['h']}（{f['mp']} MP）" if f.get('w') else '')
                        + (f"　{fmt_t(f['dur'])}" if f.get('dur') else '') + f"<br>📅 {fmt_day(f['taken']) if f.get('taken') else '—'}（{ENG.DSRC_NM.get(f.get('date_src') or '', '')}）"
                        + f"<br>{esc_html(fcore.SRC_NM.get(f.get('src') or '', '… 還沒讀'))}" + (f"<br>📷 {esc_html((f.get('make') or '') + ' ' + (f.get('model') or ''))}" if f.get('make') or f.get('model') else '')
                        + (f"<br>🎨 {esc_html(f['software'])}" if f.get('software') else '') + ('<br>📍 有定位' if f.get('gps') else '') + ('<br>🎞 動態照片' if f.get('motion') else '')
                        + f"<br><span style='color:{hc}'>{hn}</span> {esc_html(f.get('health_msg') or '')}<br><span style='color:#8994a4'>{esc_html(os.path.dirname(f['path']))}</span>")

    def quar(self):
        ids = [self.R[x.row()]['id'] for x in self.tb.selectionModel().selectedRows() if 0 <= x.row() < len(self.R)]
        if not ids: self.win.msg('先選檔案（Ctrl／Shift 可以選很多個；Ctrl+A 全選這一頁）'); return
        if QMessageBox.question(self, '搬到隔離區', f'把選取的 {len(ids)} 個檔案搬到隔離區？（可以在「📦 隔離區」復原）') != QMessageBox.Yes: return
        bg(lambda: ENG.fc_quar_many(ids, '手動'), lambda r: (self.win.msg(r.get('message', '')), self.search(False)))

    def export(self):
        out, _ = QFileDialog.getSaveFileName(self, '匯出 CSV', str(Path.home() / 'Desktop' / f'FileCompare_{time.strftime("%Y%m%d_%H%M")}.csv'), 'CSV (*.csv)')
        if not out: return
        F = dict(self.F); order = self.order.currentData(); self.win.msg('匯出中…', 30000)
        bg(lambda: ENG.fc_export_csv(F, out, order), lambda n: self.win.msg(f'匯出好了：{n:,} 筆 → {out}（可以用 Excel 打開）'))


# ============================================================ 📦 隔離區：搬過去的檔案、復原
class QuarPage(QWidget):
    PAGE = 300

    def __init__(self, win):
        super().__init__(); self.win = win; self.off = 0; self.R = []; self.n = 0; self._shown = False
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10); r = QHBoxLayout(); v.addLayout(r)
        self.only = QComboBox(); self.only.addItems(['還在隔離區的', '全部紀錄（含已復原）']); bp = QPushButton('◀ 上一頁'); bn = QPushButton('下一頁 ▶'); br = QPushButton('🔄 重新整理')
        bu = QPushButton('↩ 復原選取的'); ba = QPushButton('↩ 全部復原…'); bo = QPushButton('📂 打開隔離資料夾'); self.sum = QLabel(''); self.sum.setObjectName('muted')
        self.rs = QComboBox(); self.rs.addItem('全部原因', ''); self.rs.setToolTip('只看某一種原因（例如「依來源整理」）'); bur = QPushButton('↩ 復原這種原因全部…')
        for w_ in (self.only, self.rs, bp, bn, br, bu, bur, ba, bo): r.addWidget(w_)
        r.addWidget(self.sum, 1)
        self.rs.currentIndexChanged.connect(lambda _i: (setattr(self, 'off', 0), self.reload())); bur.clicked.connect(self.undo_reason)
        v.addWidget(note('隔離區＝每顆硬碟根目錄的「_FileCompare_待確認」資料夾，裡面照「重複／損毀」分開，並保留原本的資料夾結構。'
                         '確認都不要了，再自己刪掉那個資料夾（Shift+Delete 才會真的空出空間；刪掉之後就不能復原了）。'))
        self.tb = QTableWidget(0, 5); self.tb.setHorizontalHeaderLabels(['時間', '原因', '原本的位置', '現在在', '狀態']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tb.horizontalHeader().setStretchLastSection(True); [self.tb.setColumnWidth(i, w) for i, w in enumerate((130, 160, 420, 420))]; v.addWidget(self.tb, 1)
        self.only.currentIndexChanged.connect(lambda _i: (setattr(self, 'off', 0), self.reload())); br.clicked.connect(self.reload)
        bp.clicked.connect(lambda: (setattr(self, 'off', max(0, self.off - self.PAGE)), self.reload()))
        bn.clicked.connect(lambda: (setattr(self, 'off', self.off + self.PAGE), self.reload()) if self.off + self.PAGE < self.n else None)
        bu.clicked.connect(self.undo_sel); ba.clicked.connect(self.undo_all); bo.clicked.connect(self.open_q)
        self.tb.itemDoubleClicked.connect(lambda it: (0 <= it.row() < len(self.R)) and show_in_folder(self.R[it.row()]['dst']))

    def showEvent(self, e):
        super().showEvent(e); self.reload()

    def reload(self):
        only = self.only.currentIndex() == 0; off = self.off; rs = self.rs.currentData() or ''; bg(lambda: ENG.fc_moves(off, self.PAGE, only, rs), self._fill)
        bg(ENG.fc_move_reasons, self._reasons)

    def _reasons(self, L):
        cur = self.rs.currentData() or ''; self.rs.blockSignals(True); self.rs.clear(); self.rs.addItem('全部原因', '')
        for k, n, _t in L: self.rs.addItem(f'{k}（{n:,}）', k)
        i = self.rs.findData(cur); self.rs.setCurrentIndex(max(0, i)); self.rs.blockSignals(False)

    def undo_reason(self):
        k = self.rs.currentData() or ''
        if not k: self.win.msg('先在旁邊選一種原因'); return
        if QMessageBox.question(self, '復原', f'把「{k}」搬過的全部搬回原本的位置？') != QMessageBox.Yes: return
        bg(lambda: ENG.fc_undo_reason(k), lambda r: (self.win.msg(r.get('message', '')), self.reload()))

    def _fill(self, r):
        self.R = r['rows']; self.n = r['n']; self.tb.setRowCount(len(self.R))
        for i, m in enumerate(self.R):
            for j, val in enumerate((fmt_day(m['t']), m['reason'], m['src'], m['dst'], '↩ 已復原' if m['undone'] else '📦 在隔離區')):
                self.tb.setItem(i, j, _ti(val, val, None, '#7f8a99' if m['undone'] else None))
        self.sum.setText(f"共 {self.n:,} 筆　第 {self.off // self.PAGE + 1}／{max(1, (self.n + self.PAGE - 1) // self.PAGE)} 頁　（雙擊一列：在資料夾中顯示）")

    def undo_sel(self):
        ids = [self.R[x.row()]['id'] for x in self.tb.selectionModel().selectedRows() if 0 <= x.row() < len(self.R) and not self.R[x.row()]['undone']]
        if not ids: self.win.msg('先選要復原的（可以按住 Ctrl／Shift 選很多個）'); return
        bg(lambda: ENG.fc_undo(ids), self._undone)

    def undo_all(self):
        if QMessageBox.question(self, '全部復原', '把隔離區裡所有的檔案都搬回原本的位置？') != QMessageBox.Yes: return
        self.win.msg('復原中…（檔案多的話要一點時間）', 30000); bg(lambda: ENG.fc_undo(None), self._undone)

    def _undone(self, r):
        (self.win.msg if r.get('ok') else lambda m: QMessageBox.warning(self, '復原', m))(r.get('message', '')); self.reload()

    def open_q(self):
        ds = sorted({fcore.quar_root(m['dst']) for m in self.R} | {fcore.quar_root(p) for p in ENG.fc_list('roots')})
        ds = [d for d in ds if os.path.isdir(d)]
        if not ds: self.win.msg('還沒有隔離資料夾（還沒搬過任何檔案）'); return
        for d in ds[:4]: QDesktopServices.openUrl(QUrl.fromLocalFile(d))


# ============================================================ 🖥 後台狀態（總控制＋最近的工作）
class BgPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.ct_sig = None; self.ct_w = {}
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        g = QGroupBox('⏯ 總控制：每一項都可以暫停／繼續／立刻停、調先後順序（電腦太忙時從最下面的先讓路）'); gv = QVBoxLayout(g); v.addWidget(g)
        self.ct = QTableWidget(0, 9); self.ct.setHorizontalHeaderLabels(['順序', '項目', '狀態', '總進度', '停在／最近在做', '', '', '', ''])
        self.ct.verticalHeader().setVisible(False); self.ct.setEditTriggers(QAbstractItemView.NoEditTriggers); self.ct.setSelectionMode(QAbstractItemView.NoSelection)
        for i, w in enumerate((50, 170, 120, 200, 260, 80, 90, 36, 36)): self.ct.setColumnWidth(i, w)
        self.ct.setMinimumHeight(140); gv.addWidget(self.ct)
        r = QHBoxLayout(); gv.addLayout(r)
        ba = QPushButton('⏸ 全部暫停'); bb = QPushButton('▶ 全部繼續（照順序慢慢加）'); self.guard = QCheckBox('電腦太忙自動讓路'); self.cmax = QSpinBox(); self.cmax.setRange(50, 100); self.cmax.setPrefix('CPU 超過 '); self.cmax.setSuffix('%')
        self.ramp = QSpinBox(); self.ramp.setRange(0, 300); self.ramp.setPrefix('慢慢加速：每 '); self.ramp.setSuffix(' 秒多開 1 個')
        for w_ in (ba, bb, self.guard, self.cmax, self.ramp): r.addWidget(w_)
        r.addStretch(1)
        self.glog = QLabel(''); self.glog.setObjectName('muted'); self.glog.setWordWrap(True); gv.addWidget(self.glog)
        ba.clicked.connect(lambda: (ENG.bg_all(True), self.refresh())); bb.clicked.connect(lambda: (ENG.bg_all(False), self.refresh()))
        self.guard.toggled.connect(lambda on: ENG.cfg.set('cpu_guard', bool(on))); self.cmax.valueChanged.connect(lambda x: ENG.cfg.set('cpu_max', int(x)))
        self.ramp.valueChanged.connect(lambda x: ENG.cfg.set('bg_ramp_sec', int(x)))
        g2 = QGroupBox('最近的工作'); g2v = QVBoxLayout(g2); v.addWidget(g2, 1)
        self.tb = QTableWidget(0, 5); self.tb.setHorizontalHeaderLabels(['時間', '工作', '狀態', '進度', '結果']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.horizontalHeader().setStretchLastSection(True)
        for i, w in enumerate((80, 320, 80, 70)): self.tb.setColumnWidth(i, w)
        self.tb.setMinimumHeight(220); g2v.addWidget(self.tb)
        self.load_guard(); self.tm = QTimer(self); self.tm.timeout.connect(self.refresh); self.tm.start(1000)

    def load_guard(self):
        for w_, val in ((self.guard, ENG.cfg.get('cpu_guard') is not False), (self.cmax, int(ENG.cfg.get('cpu_max') or 90)), (self.ramp, int(ENG.cfg.get('bg_ramp_sec') if ENG.cfg.get('bg_ramp_sec') is not None else 20))):
            w_.blockSignals(True); (w_.setChecked(val) if isinstance(w_, QCheckBox) else w_.setValue(val)); w_.blockSignals(False)

    def refresh(self):
        if not self.isVisible(): return
        bg(lambda: (ENG.bg_view(), ENG.tasks_list()[-80:]), self._got)

    def _got(self, r):
        V, T = r; L = V['kinds']; sig = tuple(k['k'] for k in L)
        if sig != self.ct_sig:
            self.ct_sig = sig; self.ct.setRowCount(len(L)); self.ct_w = {}
            for i, k in enumerate(L):
                pb = QProgressBar(); pb.setRange(0, 1000); pb.setTextVisible(True); self.ct.setCellWidget(i, 3, pb)
                bp = QPushButton(); bs = QPushButton('⏹ 立刻停'); bu = QPushButton('↑'); bd = QPushButton('↓')
                for c_, w_ in ((5, bp), (6, bs), (7, bu), (8, bd)): self.ct.setCellWidget(i, c_, w_)
                kk = k['k']
                bp.clicked.connect(lambda _c=False, kk=kk: (ENG.bg_set_pause(kk, not ENG.bg_pause.get(kk)), self.refresh()))
                bs.clicked.connect(lambda _c=False, kk=kk: (QMessageBox.question(self, '立刻停', '正在做的也停掉，放回排隊？') == QMessageBox.Yes) and (ENG.bg_stop_now(kk), self.refresh()))
                bu.clicked.connect(lambda _c=False, kk=kk: (ENG.bg_move(kk, -1), self.refresh())); bd.clicked.connect(lambda _c=False, kk=kk: (ENG.bg_move(kk, 1), self.refresh()))
                self.ct_w[i] = (pb, bp, bs)
        STN = {'run': ('▶ 進行中', '#45d483'), 'idle': ('— 沒事', '#7f8a99'), 'pause': ('⏸ 暫停中', '#ff4d6d'), 'hold': ('⚖ 讓路中', '#f0ad4e')}
        for i, k in enumerate(L):
            nm, col = STN.get(k['state'], (k['state'], None))
            if k.get('ramp'): nm += f'（慢慢加速 {k["ramp"]}）'
            if k.get('slow'): nm += f'（降速：最多 {k["slow"]} 個）'
            last = (('⏸ 停在：' if k['state'] == 'pause' else '') + k['last']) if k['last'] else ''
            if k.get('held'): last = k['held'] + ('　' + last if last else '')
            for c_, val in enumerate((str(k['prio']), f"{k['icon']} {k['name']}", nm, None, last)):
                if val is None: continue
                it = self.ct.item(i, c_)
                if it is None or it.text() != val: self.ct.setItem(i, c_, _ti(val, val, None, col if c_ == 2 else None))
            w3 = self.ct_w.get(i)
            if w3 is not None:
                bar_, bpz, bsz = w3; bar_.setVisible(k['pct'] is not None)
                if k['pct'] is not None: bar_.setValue(int(k['pct'] * 10)); bar_.setFormat(f"{k['pct']:.1f}%（{k['done']:,}／{k['total']:,}）")
                bpz.setText('▶ 繼續' if k['state'] == 'pause' else '⏸ 暫停'); bsz.setEnabled(bool(k['running']))
        self.glog.setText(f"CPU 現在 {V['cpu']:.0f}%　" + ('　'.join(V['log'][:3]) if V.get('log') else '（自動讓路的紀錄會顯示在這裡）'))
        T = list(reversed(T)); self.tb.setRowCount(len(T)); SC = {'run': '#4dc9ff', 'done': '#45d483', 'fail': '#ff4d6d', 'stop': '#f0ad4e'}
        for i, t in enumerate(T):
            vals = (time.strftime('%H:%M:%S', time.localtime(t['t0'])), t['title'], t['state'], f"{t['pct']}%" if t.get('pct') is not None and t['state'] == 'run' else '', t.get('msg') or '')
            for j, val in enumerate(vals):
                it = self.tb.item(i, j)
                if it is None or it.text() != str(val): self.tb.setItem(i, j, _ti(val, val, None, SC.get(t['state']) if j == 2 else None))


# ============================================================ 📈 資料分析：每一類佔多少、哪些是遊戲／軟體（整包算）、樹狀圖點進去看
from PySide6.QtWidgets import QToolTip  # noqa: E402
import fc_ana as ana  # noqa: E402

CAT_NM, CAT_COL = ana.CAT_NM, ana.CAT_COL


def _pct(a, b): return (100.0 * a / b) if b else 0.0


class Donut(QWidget):
    """圓環圖：每一類佔多少（大小或檔案數）."""
    def __init__(self):
        super().__init__(); self.D = []; self.center = ('', ''); self.setMinimumSize(250, 250); self.setMouseTracking(True)

    def set_data(self, D, center):
        self.D = [d for d in D if d[2] > 0]; self.center = center; self.update()

    def _geo(self):
        s = min(self.width(), self.height()) - 16; return QRectF((self.width() - s) / 2, (self.height() - s) / 2, s, s), s

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); R, s = self._geo(); th = s * 0.2; r2 = R.adjusted(th / 2, th / 2, -th / 2, -th / 2)
        tot = sum(d[2] for d in self.D)
        if not tot:
            p.setPen(QPen(TC('track'), th)); p.drawEllipse(r2)
        a = 90 * 16.0
        for _k, _nm, v, col in self.D:
            sp = -360 * 16.0 * v / tot
            p.setPen(QPen(QColor(col), th, Qt.SolidLine, Qt.FlatCap)); p.drawArc(r2, int(a), int(sp) + (8 if abs(sp) > 40 else 0)); a += sp
        f = QFont(); f.setPixelSize(max(12, int(s * 0.09))); f.setBold(True); p.setFont(f); p.setPen(TC('text_strong'))
        p.drawText(QRectF(R.x(), R.center().y() - s * 0.13, s, s * 0.13), Qt.AlignHCenter | Qt.AlignBottom, self.center[0])
        f.setPixelSize(max(10, int(s * 0.05))); f.setBold(False); p.setFont(f); p.setPen(TC('subtext'))
        p.drawText(QRectF(R.x(), R.center().y() + 2, s, s * 0.1), Qt.AlignHCenter | Qt.AlignTop, self.center[1])

    def mouseMoveEvent(self, e):
        R, s = self._geo(); c = R.center(); dx = e.position().x() - c.x(); dy = c.y() - e.position().y(); d = math.hypot(dx, dy)
        tot = sum(x[2] for x in self.D)
        if not tot or d < s * 0.3 or d > s / 2: QToolTip.hideText(); return
        ang = (90 - math.degrees(math.atan2(dy, dx))) % 360; acc = 0
        for _k, nm, v, _c in self.D:
            acc += 360 * v / tot
            if ang <= acc: QToolTip.showText(e.globalPosition().toPoint(), f'{nm}：{_pct(v, tot):.1f}%', self); return


class HBars(QWidget):
    """一列一條的橫條（每條裡面分好幾段）：rows＝[(左邊文字, 右邊文字, [(顏色, 值, 提示)], 這條的長度比例 0~1)]."""
    ROW = 30

    def __init__(self, label_w=230):
        super().__init__(); self.rows = []; self.lw = label_w; self.setMouseTracking(True)

    def set_rows(self, rows):
        self.rows = rows; self.setMinimumHeight(max(20, len(rows) * self.ROW + 4)); self.updateGeometry(); self.update()

    def _bar(self, i, row):
        w = max(10, self.width() - self.lw - 150); return QRectF(self.lw, i * self.ROW + 7, w * max(0.002, min(1.0, row[3])), self.ROW - 14)

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); fm = QFontMetrics(self.font())
        for i, row in enumerate(self.rows):
            y = i * self.ROW; p.setPen(TC('text'))
            p.drawText(QRectF(0, y, self.lw - 8, self.ROW), Qt.AlignVCenter | Qt.AlignRight, fm.elidedText(row[0], Qt.ElideMiddle, self.lw - 10))
            full = QRectF(self.lw, y + 7, max(10, self.width() - self.lw - 150), self.ROW - 14)
            p.setPen(Qt.NoPen); p.setBrush(TC('track')); p.drawRoundedRect(full, 4, 4)
            R = self._bar(i, row); tot = sum(s[1] for s in row[2]); x = R.x()
            path = QPainterPath(); path.addRoundedRect(R, 4, 4); p.save(); p.setClipPath(path)
            for col, v, _t in row[2]:
                w = R.width() * v / tot if tot else 0; p.setBrush(QColor(col)); p.drawRect(QRectF(x, R.y(), w + 0.5, R.height())); x += w
            p.restore(); p.setPen(TC('subtext'))
            p.drawText(QRectF(full.right() + 8, y, 142, self.ROW), Qt.AlignVCenter | Qt.AlignLeft, row[1])

    def mouseMoveEvent(self, e):
        i = int(e.position().y() // self.ROW)
        if not (0 <= i < len(self.rows)): QToolTip.hideText(); return
        row = self.rows[i]; R = self._bar(i, row); tot = sum(s[1] for s in row[2]); x = R.x(); px = e.position().x()
        for _col, v, tip in row[2]:
            w = R.width() * v / tot if tot else 0
            if x <= px <= x + w: QToolTip.showText(e.globalPosition().toPoint(), f'{row[0]}\n{tip}', self); return
            x += w
        QToolTip.hideText()


class Treemap(QWidget):
    """樹狀圖：一塊＝一個資料夾，面積＝大小，顏色＝主要是哪一類（下面的細條＝裡面的比例）。點一下進去，右鍵打開資料夾."""
    def __init__(self, on_drill):
        super().__init__(); self.on_drill = on_drill; self.items = []; self.R = []; self.hover = -1; self.setMinimumHeight(440); self.setMouseTracking(True)

    def set_data(self, kids, rest):
        self.items = [(k['b'], k) for k in kids if k['b'] > 0]
        if rest and rest.get('b', 0) > 0: self.items.append((rest['b'], dict(rest, path='', rest=True, pkg='', why='')))
        self.items.sort(key=lambda x: -x[0]); self.hover = -1; self._lay(); self.update()

    def _lay(self):
        self.R = ana.squarify(self.items, 0, 0, self.width(), self.height())

    def resizeEvent(self, e): self._lay(); super().resizeEvent(e)

    @staticmethod
    def label(o):
        if o.get('rest'): return f'其他 {o["more"]:,} 個資料夾＋這層的檔案' if o.get('more') else '這層的檔案＋小資料夾'
        nm = os.path.basename(str(o['path']).rstrip('\\/')) or str(o['path'])
        return (ana.PKG_ICON.get(o.get('pkg'), '') + ' ' + nm).strip()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); fm = QFontMetrics(self.font())
        if not self.R:
            p.setPen(TC('subtext')); p.drawText(self.rect(), Qt.AlignCenter, '（沒有資料）'); return
        for i, (x, y, w, h, o) in enumerate(self.R):
            r = QRectF(x + 1, y + 1, max(0, w - 2), max(0, h - 2)); eff = o.get('eff') or {}
            base = QColor(CAT_COL.get(o.get('pkg') or ana.dominant(eff), '#4b5563'))
            if o.get('rest'): base = base.darker(150)
            if i == self.hover: base = base.lighter(125)
            p.setPen(Qt.NoPen); p.setBrush(base); p.drawRoundedRect(r, 3, 3)
            if h > 26 and w > 20 and not o.get('pkg'):                             # 下面細條：裡面各類的比例
                tot = sum(v[1] for v in eff.values()); bx = r.x() + 3
                for c, (_n, b) in sorted(eff.items(), key=lambda kv: -kv[1][1]):
                    bw = (r.width() - 6) * b / tot if tot else 0; p.setBrush(QColor(CAT_COL.get(c, '#4b5563')).lighter(115)); p.drawRect(QRectF(bx, r.bottom() - 7, bw, 4)); bx += bw
            if w > 46 and h > 20:
                p.setPen(QColor('#ffffff')); t1 = fm.elidedText(self.label(o), Qt.ElideRight, int(w - 8))
                p.drawText(QRectF(r.x() + 5, r.y() + 3, w - 10, 18), Qt.AlignLeft | Qt.AlignVCenter, t1)
                if h > 38: p.setPen(QColor(255, 255, 255, 190)); p.drawText(QRectF(r.x() + 5, r.y() + 20, w - 10, 16), Qt.AlignLeft | Qt.AlignVCenter, fmt_b(o['b']))

    def _at(self, pos):
        for i, (x, y, w, h, _o) in enumerate(self.R):
            if x <= pos.x() < x + w and y <= pos.y() < y + h: return i
        return -1

    def mouseMoveEvent(self, e):
        i = self._at(e.position())
        if i != self.hover: self.hover = i; self.update()
        if i < 0: QToolTip.hideText(); return
        o = self.R[i][4]; eff = o.get('eff') or {}; tot = sum(v[1] for v in eff.values()) or 1
        L = [f'<b>{esc_html(self.label(o))}</b>　{fmt_b(o["b"])}・{o.get("n", 0):,} 個檔']
        if o.get('pkg'):
            L.append(f'{ana.PKG_ICON.get(o["pkg"], "")} 整包算「{CAT_NM.get(o["pkg"])}」：{esc_html(o.get("why", ""))}')
            raw = o.get('raw') or {}
            if raw: L.append('裡面的檔案：' + '、'.join(f'{CAT_NM.get(c, c)} {v[0]:,} 個' for c, v in sorted(raw.items(), key=lambda kv: -kv[1][1])[:5]))
        else: L += [f'<span style="color:{CAT_COL.get(c)}">■</span> {CAT_NM.get(c, c)} {_pct(v[1], tot):.0f}%（{fmt_b(v[1])}）' for c, v in sorted(eff.items(), key=lambda kv: -kv[1][1])[:7]]
        if o.get('mt'): L.append(f'最近修改：{fmt_day(o["mt"])[:10]}')
        if not o.get('rest'): L.append('<span style="color:#8994a4">' + ('左鍵：點進去看・' if o.get('kids') else '') + '右鍵：打開資料夾</span>')
        QToolTip.showText(e.globalPosition().toPoint(), '<br>'.join(L), self)

    def leaveEvent(self, e): self.hover = -1; self.update(); super().leaveEvent(e)

    def mousePressEvent(self, e):
        i = self._at(e.position())
        if i < 0: return
        o = self.R[i][4]
        if o.get('rest'): return
        if e.button() == Qt.RightButton:
            m = QMenu(self); m.addAction('📂 打開這個資料夾', lambda: open_file(o['path'])); m.addAction('📋 複製路徑', lambda: QApplication.clipboard().setText(o['path']))
            if o.get('kids'): m.addAction('🔍 點進去看', lambda: self.on_drill(o['path']))
            m.exec(e.globalPosition().toPoint()); return
        if o.get('kids'): self.on_drill(o['path'])


class YearBars(QWidget):
    """每年拍了幾張照片／幾支影片（直條，照片＋影片疊起來）."""
    def __init__(self):
        super().__init__(); self.Y = []; self.setMinimumHeight(220); self.setMouseTracking(True); self.cols = []

    def set_data(self, Y):
        self.Y = Y; self.update()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); self.cols = []
        if not self.Y: p.setPen(TC('subtext')); p.drawText(self.rect(), Qt.AlignCenter, '（還沒有照片影片的資料）'); return
        mx = max(a + b for _y, a, b in self.Y) or 1; n = len(self.Y); W = self.width(); H = self.height() - 40; bw = min(46, max(8, (W - 10) / n - 6))
        for i, (y, a, b) in enumerate(self.Y):
            x = 5 + i * (W - 10) / n + ((W - 10) / n - bw) / 2; ha = H * a / mx; hb = H * b / mx; top = 18 + H - ha - hb
            p.setPen(Qt.NoPen); p.setBrush(QColor(CAT_COL['video'])); p.drawRect(QRectF(x, top, bw, hb))
            p.setBrush(QColor(CAT_COL['photo'])); p.drawRect(QRectF(x, top + hb, bw, ha)); self.cols.append((x, bw, y, a, b))
            p.setPen(TC('subtext')); f = QFont(self.font()); f.setPixelSize(10); p.setFont(f)
            if bw >= 20 or i % max(1, int(30 / max(bw, 1))) == 0: p.drawText(QRectF(x - 14, 18 + H + 4, bw + 28, 16), Qt.AlignCenter, y)
            if bw >= 26: p.drawText(QRectF(x - 14, top - 16, bw + 28, 14), Qt.AlignCenter, f'{a + b:,}')

    def mouseMoveEvent(self, e):
        for x, bw, y, a, b in self.cols:
            if x <= e.position().x() <= x + bw: QToolTip.showText(e.globalPosition().toPoint(), f'{y} 年：照片 {a:,} 張、影片 {b:,} 支', self); return
        QToolTip.hideText()


class AnaPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.gen = -1; self.cur = ''; self.V = {}; self.mode = 'b'; self.pkg_rows = []
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('📈 資料分析'); t.setObjectName('title'); r.addWidget(t)
        self.st = QLabel(''); self.st.setObjectName('muted'); self.st.setWordWrap(True); r.addWidget(self.st, 1)
        self.b_run = QPushButton('🔄 重新分析'); self.b_run.setObjectName('start'); self.b_pause = QPushButton(); self.b_stop = QPushButton('⏹ 停止')
        b_rep = QPushButton('📄 匯出報告'); b_rep.setToolTip('把整理狀況做成一頁 HTML（硬碟、種類、重複、損毀、分類、地點…），可以列印成 PDF')
        b_rep.clicked.connect(lambda: (self.win.msg('📄 做報告中…'), bg(lambda: report.build(ENG), lambda r: (self.win.msg(f'📄 報告好了：{r[0]}'), open_file(r[0])))))
        for b_ in (self.b_run, self.b_pause, self.b_stop, b_rep): r.addWidget(b_)
        v.addWidget(note('把「要整理的資料夾」裡的所有檔案（不只照片影片）走一遍，看每一類佔多少。遊戲、軟體、程式專案是「整包資料夾」算一個：'
                         '遊戲裡的圖片是素材、不算照片；軟體裡的 .exe 不算安裝檔。只看、不動任何檔案。'))
        # ① 總覽：圓環＋每一類
        g1 = QGroupBox('① 每一類佔多少'); h1 = QHBoxLayout(g1); v.addWidget(g1)
        self.donut = Donut(); self.donut.setFixedSize(290, 290); h1.addWidget(self.donut)
        rv = QVBoxLayout(); h1.addLayout(rv, 1); rm = QHBoxLayout(); rv.addLayout(rm)
        self.cm = QComboBox(); self.cm.addItems(['看大小', '看檔案數']); rm.addWidget(self.cm); rm.addStretch(1)
        self.legend = QTableWidget(0, 5); self.legend.setHorizontalHeaderLabels(['', '類別', '大小', '檔案數', '說明']); self.legend.verticalHeader().setVisible(False)
        self.legend.setEditTriggers(QAbstractItemView.NoEditTriggers); self.legend.setSelectionMode(QAbstractItemView.NoSelection); self.legend.horizontalHeader().setStretchLastSection(True)
        for i, w in enumerate((60, 140, 150, 120)): self.legend.setColumnWidth(i, w)
        self.legend.setMinimumHeight(250); rv.addWidget(self.legend)
        self.cm.currentIndexChanged.connect(lambda i: (setattr(self, 'mode', 'b' if i == 0 else 'n'), self._summary()))
        # 🩺 容量健康（V0.2.15）
        gc = QGroupBox('🩺 容量健康：重複、損毀各佔多少'); vc_ = QVBoxLayout(gc); v.addWidget(gc)
        self.capbar = HBars(150); vc_.addWidget(self.capbar)
        rc = QHBoxLayout(); vc_.addLayout(rc); self.caplab = QLabel(''); self.caplab.setTextFormat(Qt.RichText); self.caplab.setWordWrap(True); rc.addWidget(self.caplab, 1)
        self.b_capdup = QPushButton('🔁 去處理重複'); self.b_capbad = QPushButton('📦 損毀的全部先隔離'); self.b_capbad.setToolTip('打不開、部分損毀、0 位元組的，全部搬到同一顆硬碟的隔離區（不是刪除，可以復原）')
        rc.addWidget(self.b_capdup); rc.addWidget(self.b_capbad)
        self.b_capdup.clicked.connect(lambda: self.win.nav.setCurrentRow(2)); self.b_capbad.clicked.connect(self.quar_bad)
        # ② 硬碟、每個資料夾
        g2 = QGroupBox('② 硬碟空間、每個要整理的資料夾'); v2 = QVBoxLayout(g2); v.addWidget(g2)
        self.disks = HBars(230); v2.addWidget(self.disks); self.rootbars = HBars(230); v2.addWidget(self.rootbars)
        # ③ 樹狀圖
        g3 = QGroupBox('③ 資料夾地圖（面積＝大小、顏色＝主要是哪一類；點一下進去、右鍵打開）'); v3 = QVBoxLayout(g3); v.addWidget(g3)
        r3 = QHBoxLayout(); v3.addLayout(r3); self.b_up = QPushButton('⬆ 上一層'); self.b_top = QPushButton('⏫ 最上層'); self.b_open = QPushButton('📂 打開這個資料夾')
        self.crumb = QLabel(''); self.crumb.setWordWrap(True); self.crumb.setTextInteractionFlags(Qt.TextSelectableByMouse)
        for w_ in (self.b_top, self.b_up, self.b_open): r3.addWidget(w_)
        r3.addWidget(self.crumb, 1)
        self.tree = Treemap(self.drill); v3.addWidget(self.tree)
        self.legend2 = QLabel(''); self.legend2.setTextFormat(Qt.RichText); self.legend2.setWordWrap(True); v3.addWidget(self.legend2)
        # ④ 遊戲／軟體清單
        g4 = QGroupBox('④ 找到的遊戲、軟體、程式專案（整包算；雙擊打開資料夾）'); v4 = QVBoxLayout(g4); v.addWidget(g4)
        r4 = QHBoxLayout(); v4.addLayout(r4); self.pk = QComboBox(); self.pk.addItem('全部', ''); [self.pk.addItem(f'{ana.PKG_ICON[k]} {CAT_NM[k]}', k) for k in ana.PKG_TYPES]
        r4.addWidget(self.pk); self.pk_sum = QLabel(''); self.pk_sum.setObjectName('muted'); r4.addWidget(self.pk_sum, 1)
        self.ptb = QTableWidget(0, 6); self.ptb.setHorizontalHeaderLabels(['類型', '名稱', '大小', '最近修改', '為什麼這樣判斷', '位置']); self.ptb.verticalHeader().setVisible(False)
        self.ptb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.ptb.setSelectionBehavior(QAbstractItemView.SelectRows); self.ptb.horizontalHeader().setStretchLastSection(True)
        for i, w in enumerate((90, 220, 100, 100, 300)): self.ptb.setColumnWidth(i, w)
        self.ptb.setMinimumHeight(300); v4.addWidget(self.ptb)
        self.pk.currentIndexChanged.connect(self._pkgs); self.ptb.cellDoubleClicked.connect(lambda r_, _c: self._open_row(r_))
        # ⑤ 照片影片
        g5 = QGroupBox('⑤ 照片、影片：每年幾個、從哪裡來（用掃描時讀到的拍攝日期）'); v5 = QVBoxLayout(g5); v.addWidget(g5)
        self.years = YearBars(); v5.addWidget(self.years); self.srcbars = HBars(230); v5.addWidget(self.srcbars)
        self.mnote = QLabel(''); self.mnote.setWordWrap(True); self.mnote.setTextFormat(Qt.RichText); v5.addWidget(self.mnote)
        v.addStretch(1)
        self.b_run.clicked.connect(self.run); self.b_stop.clicked.connect(lambda: (ENG.bg_stop_now('ana'), self.refresh()))
        self.b_pause.clicked.connect(lambda: (ENG.bg_set_pause('ana', not ENG.bg_pause.get('ana')), self.refresh()))
        self.b_up.clicked.connect(self.up); self.b_top.clicked.connect(lambda: self.drill('')); self.b_open.clicked.connect(lambda: getattr(self, 'open_p', '') and open_file(self.open_p))
        self.tm = QTimer(self); self.tm.timeout.connect(self.refresh); self.tm.start(1500)

    def showEvent(self, e):
        super().showEvent(e); self.refresh()

    def reload(self): self.gen = -1; self.refresh()

    def run(self):
        if not ENG.fc_list('roots'): self.win.msg('先到「🏠 總覽」加入要整理的資料夾'); return
        ok = ENG.ana_start(); self.win.msg('📈 開始分析（背景做，可以先去做別的）' if ok else '已經在分析／排隊中了'); self.refresh()

    def refresh(self):
        if not self.isVisible(): return
        bg(ENG.ana_view, self._got)
        if time.time() - getattr(self, '_capt', 0) > 8: self._capt = time.time(); bg(ENG.cap_summary, self._cap)

    def _cap(self, c):
        if not c: return
        first = getattr(self, '_capc', None) is None; self._capc = c
        if first: self._summary()
        T = c['total'] or 1; P = lambda x: x * 100 / T
        seg = [('#45d483', c['ok'], '正常'), ('#f0ad4e', c['dup'], '重複多出來的份'), ('#ff4d6d', c['bad'], '損毀'), ('#8f7cf0', c['quar'], '已在隔離區')]
        self.capbar.set_rows([(f"全部 {fmt_b(c['total'])}", '', [(col, val, f'{nm} {fmt_b(val)}（{P(val):.1f}%）') for col, val, nm in seg if val > 0], 1.0)])
        self.caplab.setText('　'.join(f"<span style='color:{col}'>■</span> {nm} <b>{P(val):.1f}%</b> {fmt_b(val)}" for col, val, nm in seg)
                            + (f"<br><span style='color:#4dc9ff'>背景搬移中：{c['run_n']:,} 個…</span>" if c.get('run') else f"<br><span style='color:#8994a4'>損毀 {c['bad_n']:,} 個、重複多出來 {c['dup_files']:,} 份。損毀的先搬到隔離區（不是刪除），之後可以復原。</span>"))
        self.b_capbad.setEnabled(bool(c['bad']) and not c.get('run')); self.b_capdup.setEnabled(bool(c['dup']))

    def quar_bad(self):
        if QMessageBox.question(self, '📦 損毀的全部先隔離', '損毀的（打不開、部分損毀、0 位元組）全部先搬到隔離區？\n\n只是搬到同一顆硬碟的隔離區，不是刪除；在「📦 隔離區」可以依原因整批復原。') != QMessageBox.Yes: return
        self.win.msg('📦 開始搬損毀的到隔離區（背景做）' if ENG.fc_quar_filter('bad') else '現在有別的整批搬移在做，等一下再按'); self._capt = 0

    def _got(self, V):
        self.V = V; S = V.get('res') or {}
        pz = V.get('pause'); self.b_pause.setText('▶ 繼續' if pz else '⏸ 暫停'); self.b_pause.setStyleSheet('color:#ff4d6d' if pz else ''); self.b_stop.setEnabled(V.get('run'))
        if V.get('run'):
            tot = V.get('total') or 0; d = V.get('done') or 0
            s = f"<span style='color:#4dc9ff'>▶ 分析中：{d:,} 個檔" + (f'（上次共 {tot:,} 個，約 {_pct(d, tot):.0f}%）' if tot and d <= tot else '') + f"</span>　{esc_html(V.get('cur', ''))[-90:]}"
        elif V.get('req'): s = '⏸ 暫停中（按「▶ 繼續」）' if pz else '排隊中（等掃描做完就開始）'
        elif S: s = f"上次分析：{fmt_day(S.get('t1'))}，花 {fmt_t(S.get('sec', 0))}　共 <b>{S.get('n', 0):,}</b> 個檔、<b>{fmt_b(S.get('b', 0))}</b>"
        else: s = '還沒分析過：按「🔄 重新分析」' if ENG.fc_list('roots') else '先到「🏠 總覽」加入要整理的資料夾'
        self.st.setText(s); self.st.setTextFormat(Qt.RichText)
        if S.get('gen') != self.gen:
            self.gen = S.get('gen'); self._summary(); self._roots(); self._media(); self._pkgs()
            bg(lambda: ENG.ana_dir(self.cur) if self.cur else None, lambda r: self.drill('' if not (r and r.get('ok')) else self.cur))

    def _summary(self):
        S = (self.V.get('res') or {}); E = S.get('eff') or {}; i = 1 if self.mode == 'b' else 0
        tot = sum(v[i] for v in E.values()); D = [(k, n, (E.get(k) or [0, 0])[i], c) for k, n, c in ana.CATS]
        self.donut.set_data(D, (fmt_b(tot) if self.mode == 'b' else f'{tot:,} 個', '全部' if tot else '還沒分析'))
        DESC = {'photo': '不含遊戲／軟體裡的圖片', 'video': '不含遊戲／軟體裡的影片', 'installer': '散落的 .exe／.msi／.apk（不在軟體資料夾裡）',
                'game': '整個遊戲資料夾', 'app': '整個軟體資料夾（含 AppData 程式資料）', 'dev': '.git 專案、node_modules、Python 環境', 'backup': 'iPhone 備份、系統映像',
                'system': 'Windows、更新暫存', 'other': '認不得的檔案類型'}
        P = S.get('pkgs') or {}; rows = [d for d in D if (E.get(d[0]) or [0, 0])[1] > 0 or (E.get(d[0]) or [0, 0])[0] > 0]
        rows.sort(key=lambda d: -(E.get(d[0]) or [0, 0])[1]); self.legend.setRowCount(len(rows))
        for r_, (k, nm, _v, col) in enumerate(rows):
            n, b = E.get(k) or [0, 0]; Ttot = sum(v[1] for v in E.values()); Ntot = sum(v[0] for v in E.values())
            extra = (f'{P[k][0]:,} 包・' if k in P else '') + DESC.get(k, '')
            for c_, val in enumerate((f'{_pct(b if self.mode == "b" else n, Ttot if self.mode == "b" else Ntot):.1f}%', nm, fmt_b(b), f'{n:,}', extra)):
                self.legend.setItem(r_, c_, _ti(val, val, None, col if c_ < 2 else None))
            self.legend.item(r_, 0).setBackground(QColor(col).darker(260))
        try:                                                                         # 🩺 其中損毀／重複多出來的份（V0.2.40）
            if self.mode == 'b':
                c = getattr(self, '_capc', None)
                if not c: raise ValueError
                Ttot = sum(v[1] for v in E.values()) or 1; base = self.legend.rowCount(); self.legend.setRowCount(base + 2)
                for k_, (col, nm, b, m) in enumerate((('#ff4d6d', '其中：損毀', c['bad'], f"{c['bad_n']:,} 個"), ('#f0ad4e', '其中：重複多出來的份', c['dup'], f"{c['dup_files']:,} 份"))):
                    for c_, val in enumerate((f'{_pct(b, Ttot):.1f}%', nm, fmt_b(b), m, '已經算在上面的類別裡' if k_ == 0 else '刪掉多的份可以省這麼多（建議用「🧭 重複資料夾最佳解」）')):
                        self.legend.setItem(base + k_, c_, _ti(val, val, None, col if c_ < 2 else None))
        except Exception: pass

    def _roots(self):
        S = self.V.get('res') or {}; rows = []
        for d in S.get('disks') or []:
            if d.get('err'): rows.append((f"💽 {d['drive']}", d['err'], [], 0)); continue
            rows.append((f"💽 {d['drive']}", f"還剩 {fmt_b(d['free'])}", [(THEME['viewer_line'], d['used'], f"用了 {fmt_b(d['used'])}（{_pct(d['used'], d['total']):.0f}%）"),
                                                                       (THEME['track'], d['free'], f"還剩 {fmt_b(d['free'])}／共 {fmt_b(d['total'])}")], 1.0))
        self.disks.set_rows(rows); R = S.get('roots') or []; mx = max([r['b'] for r in R] + [1]); rows = []
        for r in R:
            E = r.get('eff') or {}
            segs = [(c, (E.get(k) or [0, 0])[1], f'{nm}：{fmt_b((E.get(k) or [0, 0])[1])}（{_pct((E.get(k) or [0, 0])[1], r["b"]):.0f}%）') for k, nm, c in ana.CATS if (E.get(k) or [0, 0])[1] > 0]
            rows.append((f"📁 {r['root']}", r.get('err') or fmt_b(r['b']), segs, r['b'] / mx if mx else 0))
        self.rootbars.set_rows(rows)

    def _media(self):
        M = ((self.V.get('res') or {}).get('media') or {}); Y = M.get('years') or {}
        L = [(y, (Y[y].get('photo') or [0, 0])[0], (Y[y].get('video') or [0, 0])[0]) for y in sorted(Y) if y != '?']
        if '?' in Y: L.append(('不明', (Y['?'].get('photo') or [0, 0])[0], (Y['?'].get('video') or [0, 0])[0]))
        self.years.set_data(L); SRC = M.get('src') or {}; NM = self.V.get('src_nm') or {}; mx = max([v[0] for v in SRC.values()] + [1])
        self.srcbars.set_rows([(NM.get(k, k or '還沒讀到'), f'{v[0]:,} 個・{fmt_b(v[1])}', [(CAT_COL['photo'], v[0], f'{v[0]:,} 個')], v[0] / mx)
                               for k, v in sorted(SRC.items(), key=lambda kv: -kv[1][0])])
        IN = M.get('in_pkg') or {}; n = sum(v[0] for v in IN.values())
        self.mnote.setText(f"🎮 另外有 <b>{n:,}</b> 個圖片／影片在遊戲、軟體資料夾裡（{fmt_b(sum(v[1] for v in IN.values()))}），是素材，上面沒算進去。"
                           '<span style="color:#8994a4">　年份用 EXIF／影片內建／檔名的日期，都沒有的用修改日期。</span>' if n else
                           '<span style="color:#8994a4">年份用 EXIF／影片內建／檔名的日期，都沒有的用修改日期。</span>')

    def _pkgs(self):
        typ = self.pk.currentData() or ''
        bg(lambda: ENG.ana_pkgs(typ), self._got_pkgs)

    def _got_pkgs(self, L):
        self.pkg_rows = L; self.ptb.setRowCount(len(L)); tb = sum(x['b'] for x in L)
        self.pk_sum.setText(f'{len(L):,} 包，共 {fmt_b(tb)}' + ('（最多列 1000 包）' if len(L) >= 1000 else ''))
        for i, x in enumerate(L):
            nm = os.path.basename(x['path'].rstrip('\\/')) or x['path']; col = CAT_COL.get(x['pkg'])
            for c_, val in enumerate((f"{ana.PKG_ICON.get(x['pkg'], '')} {CAT_NM.get(x['pkg'], x['pkg'])}", nm, fmt_b(x['b']), fmt_day(x['mt'])[:10], x['why'], x['path'])):
                self.ptb.setItem(i, c_, _ti(val, val, None, col if c_ == 0 else None))

    def _open_row(self, r_):
        try: open_file(self.pkg_rows[r_]['path'])
        except Exception: pass

    def drill(self, path):
        bg(lambda: ENG.ana_dir(path), lambda r, path=path: self._got_dir(path, r))

    def _got_dir(self, path, r):
        if not r or not r.get('ok'):
            self.tree.set_data([], None); self.crumb.setText(esc_html((r or {}).get('message', '還沒分析過'))); self.cur = ''; return
        N = r['node']; self.cur = path if N.get('parent') is not None else ''; self.open_p = N.get('path') or ''; self.tree.set_data(r['kids'], r.get('rest'))
        self.b_up.setEnabled(N.get('parent') is not None and bool(path)); self.b_open.setEnabled(bool(N.get('path')))
        self.crumb.setText(f"<b>{esc_html(N.get('path') or '全部要整理的資料夾')}</b>　{fmt_b(N['b'])}・{N.get('n', 0):,} 個檔"); self.crumb.setTextFormat(Qt.RichText)
        E = N.get('eff') or {}
        self.legend2.setText('　'.join(f'<span style="color:{c}">■</span> {nm}' for k, nm, c in ana.CATS if k in E) or '')

    def up(self):
        if not self.cur: return
        bg(lambda: ENG.ana_dir(self.cur), lambda r: self.drill(((r or {}).get('node') or {}).get('parent') or ''))


# ============================================================ 🎞 影片快速分類：16 格一次看完 → 按分類（先記下來）→ 一個段落後一次搬
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QInputDialog  # noqa: E402


def best_grid(n, W, H, ar):
    """n 格（可以少 1 格）放進 W×H，每格寬高比 ar：挑格子最大的排法（橫的影片在手機上會變 2×8，直的變 4×4…）."""
    best = (0, n, 1, 1, 0, 0)
    for k in (n, n - 1):
        if k <= 0: continue
        for c in range(1, k + 1):
            r = math.ceil(k / c)
            if c * r != k and k != n: continue                                  # 少 1 格的只在剛好排滿時用（例如 3×5）
            cw = min(W / c, H / r * ar); ch = cw / ar; sc = cw * ch * (1 if c * r == k else 0.8)       # 最後一列沒排滿的：除非大很多，不然用排滿的
            if sc > best[0] * 1.0001: best = (sc, k, c, r, cw, ch)
    return best[1:]


class FrameGrid(QWidget):
    """16 格：自動挑最大的排法；左下角是時間；雙擊用預設播放器打開影片."""
    def __init__(self, on_open):
        super().__init__(); self.imgs = []; self.T = []; self.ar = 16 / 9; self.msg = ''; self.on_open = on_open; self.L = []; self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding); self.setMinimumHeight(200)

    def set_data(self, imgs, T, ar, msg=''):
        self.imgs = [QPixmap.fromImage(i) if isinstance(i, QImage) else i for i in imgs]; self.T = T; self.ar = ar or 16 / 9; self.msg = msg; self.update()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.SmoothPixmapTransform); p.fillRect(self.rect(), QColor('#000000')); self.L = []
        if not self.imgs:
            p.setPen(QColor('#8994a4')); p.drawText(self.rect(), Qt.AlignCenter, self.msg or '…'); return
        k, c, r, cw, ch = best_grid(len(self.imgs), self.width() - 4, self.height() - 4, self.ar)
        ox = (self.width() - c * cw) / 2; oy = (self.height() - r * ch) / 2; f = QFont(self.font()); f.setPixelSize(max(10, int(ch / 12))); p.setFont(f)
        for i, pm in enumerate(self.imgs[:k]):
            x = ox + (i % c) * cw; y = oy + (i // c) * ch; R = QRectF(x + 1, y + 1, cw - 2, ch - 2); self.L.append((R, i))
            p.drawPixmap(R, pm, QRectF(pm.rect()))
            if i < len(self.T):
                t = self.T[i]; s = fmt_t(t); fm = QFontMetrics(f); tw = fm.horizontalAdvance(s) + 8
                p.fillRect(QRectF(R.x(), R.bottom() - fm.height() - 2, tw, fm.height() + 2), QColor(0, 0, 0, 150)); p.setPen(QColor('#ffffff'))
                p.drawText(QRectF(R.x() + 4, R.bottom() - fm.height() - 1, tw, fm.height()), Qt.AlignLeft | Qt.AlignVCenter, s)

    def mouseDoubleClickEvent(self, e): self.on_open()


class GrpDlg(QDialog):
    """👀 整組一覽（V0.2.18，電腦版）：這組的縮圖一次看；勾幾部先分到別類，再把剩下的整組分到同一類；分完自動開下一組."""
    def __init__(self, page, s_, e_, g):
        super().__init__(page); self.p = page; self.s_ = s_; self.ids = page.ids[s_:e_ + 1]; self.g = g; self.res = None
        self.setWindowTitle(f'👀 {page.gn[g]}　第 {g + 1}／{len(page.gn)} 組'); self.resize(1100, 760)
        v = QVBoxLayout(self); T = ENG.vc.tags_of(self.ids); self.T = T
        self.head = QLabel(''); self.head.setTextFormat(Qt.RichText); v.addWidget(self.head)
        self.ls = QListWidget(); self.ls.setViewMode(QListView.IconMode); self.ls.setIconSize(QSize(240, 150)); self.ls.setResizeMode(QListView.Adjust)
        self.ls.setUniformItemSizes(True); self.ls.setSpacing(6); self.ls.setMovement(QListView.Static); v.addWidget(self.ls, 1)
        C = {c['id']: c for c in page.cats}
        for k, fid in enumerate(self.ids):
            c = C.get(T.get(fid)); it = QListWidgetItem(f"{k + 1}" + (f"　■ {c['name']}" if c else ''))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Unchecked); it.setData(Qt.UserRole, fid); it.setSizeHint(QSize(252, 182))
            if c: it.setForeground(QColor(c['color']))
            self.ls.addItem(it)
            bg(lambda fid=fid: ENG.vc.thumb(fid), lambda p, it=it: p and it.setIcon(QIcon(QPixmap(str(p)))))
        self.ls.itemDoubleClicked.connect(lambda it: self._done(('go', self.s_ + self.ls.row(it))))
        self.ls.itemChanged.connect(lambda _it: self._head())
        cw = QWidget(); cg = QGridLayout(cw); cg.setContentsMargins(0, 0, 0, 0); v.addWidget(cw)
        for i, c in enumerate(page.cats):
            b = QPushButton((f'{(i + 1) % 10} ' if i < 10 else '') + c['name']); b.setStyleSheet(f"border-left:6px solid {c['color']};padding:8px 12px;font-weight:800"); b.clicked.connect(lambda _=False, c=c: self.tag(c)); cg.addWidget(b, i // 8, i % 8)
        r = QHBoxLayout(); v.addLayout(r)
        self.chain = QCheckBox('分完自動開下一組'); self.chain.setChecked(ENG.cfg.get('vc_gchain') is not False); r.addWidget(self.chain)
        r.addStretch(1)
        p = page.gp[g] if page.gp else ''
        if p:
            bk = QPushButton('✅ 整包已篩選'); bk.setObjectName('start'); r.addWidget(bk); bk.clicked.connect(lambda: self._done(('keep', p)))
        self._sc = []                                                                 # ⌨ 1～9、0＝分類（跟分類頁一樣）；]＝下一組（V0.2.52）
        for i, c in enumerate(page.cats[:10]):
            sc = QShortcut(QKeySequence(str((i + 1) % 10)), self); sc.activated.connect(lambda c=c: self.tag(c)); self._sc.append(sc)
        sc = QShortcut(QKeySequence(']'), self); sc.activated.connect(lambda: self._done(('next', None))); self._sc.append(sc)
        bp = QPushButton('▶ 播選的'); bp.setToolTip('用預設播放器打開目前選的那部'); r.addWidget(bp)
        bp.clicked.connect(lambda: self.ls.currentItem() and bg(lambda: (ENG.fc_file(self.ls.currentItem().data(Qt.UserRole)) or {}).get('path'), lambda p_: p_ and open_file(p_)))
        U = getattr(page, '_gundo', None)
        if U:
            bu = QPushButton(f'↶ 復原剛剛（{len(U[0])} 部）'); bu.setToolTip('把剛剛整組分類的變回原本的樣子（Backspace）'); r.addWidget(bu); bu.clicked.connect(self.undo)
            sc = QShortcut(QKeySequence('Backspace'), self); sc.activated.connect(self.undo); self._sc.append(sc)
        bn = QPushButton('⏭ 下一組'); bx = QPushButton('關閉'); r.addWidget(bn); r.addWidget(bx)
        bn.clicked.connect(lambda: self._done(('next', None))); bx.clicked.connect(self.reject)
        self._head()

    def checked(self):
        return [self.ls.item(i).data(Qt.UserRole) for i in range(self.ls.count()) if self.ls.item(i).checkState() == Qt.Checked]

    def _head(self):
        ck = self.checked(); todo = [f for f in self.ids if f not in self.T]
        tgt = f'勾選的 {len(ck)} 部' if ck else (f'剩下還沒分的 {len(todo)} 部' if len(todo) < len(self.ids) else f'這組全部 {len(self.ids)} 部')
        self.head.setText(f"<b>{esc_html(self.p.gn[self.g])}</b>　{len(self.ids)} 部・待分 {len(todo)}　—　按下面的分類＝<b>{tgt}</b>分到那一類（只是標記）。"
                          "<br><span style='color:#8994a4'>勾選框：先挑出幾部分到別類；雙擊縮圖跳到那一部看 16 格；鍵盤 1～9、0＝分類，]＝下一組</span>")

    def tag(self, c):
        ck = self.checked(); todo = [f for f in self.ids if f not in self.T]
        L = ck or todo or self.ids
        self.p._gundo = (list(L), {f: self.T.get(f, 0) for f in L}, self.p.idx)
        r = ENG.vc.tag_many(L, c['id'], only_new=not ck and bool(todo))
        for f in L: self.T[f] = c['id']
        try: self.p.tagged.update(L)
        except Exception: pass
        self.p.win.msg(f"✔ {len(L)} 部 → {c['name']}", 2500)
        if ck and any(f not in self.T for f in self.ids):
            for i in range(self.ls.count()):
                it = self.ls.item(i)
                if it.checkState() == Qt.Checked: it.setCheckState(Qt.Unchecked); it.setText(f"{i + 1}　■ {c['name']}"); it.setForeground(QColor(c['color']))
            self._head(); return
        self._done(('chain' if self.chain.isChecked() else 'stay', None))

    def undo(self):
        U = getattr(self.p, '_gundo', None)
        if not U: return
        self.p._gundo = None; ids, prev, at = U
        none = [f for f in ids if not prev.get(f)]
        if none: ENG.vc.tag_many(none, 0, only_new=False)
        for f in ids:
            if prev.get(f): ENG.vc.tag(f, prev[f])
        try: self.p.tagged.difference_update(none)
        except Exception: pass
        self.p.win.msg(f'↶ 復原了 {len(ids)} 部', 3000); self._done(('undo', at))

    def _done(self, res):
        try: ENG.cfg.set('vc_gchain', self.chain.isChecked())
        except Exception: pass
        self.res = res; self.accept()


class VcCatDlg(QDialog):
    """⚙ 管理分類：改名字、設定搬去哪、調順序、刪掉；SortCut 在哪."""
    def __init__(self, page):
        super().__init__(page); self.page = page; self.setWindowTitle('⚙ 管理分類'); self.resize(860, 480); v = QVBoxLayout(self)
        v.addWidget(note('「搬去哪」空著＝搬到影片那顆硬碟的 \\FileCompare_分類\\分類名稱（同一顆硬碟裡搬，瞬間完成）。要搬到別的地方就按「📁 選位置」（要在同一顆硬碟）。「📌 不搬」＝只記下看過、檔案留在原處（例如「已篩選」只想標記）。'))
        self.tb = QTableWidget(0, 4); self.tb.setHorizontalHeaderLabels(['按鍵', '分類', '搬去哪', '分好的']); self.tb.verticalHeader().setVisible(False)
        self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.setSelectionMode(QAbstractItemView.SingleSelection); self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for i, w in enumerate((50, 160, 460)): self.tb.setColumnWidth(i, w)
        self.tb.horizontalHeader().setStretchLastSection(True); v.addWidget(self.tb, 1)
        r = QHBoxLayout(); v.addLayout(r)
        for t_, fn in (('＋ 新增', self.add), ('✏ 改名字', self.ren), ('📁 選位置', self.dest), ('↺ 位置用預設', lambda: self._edit(dest='')), ('📌 不搬', lambda: self._edit(dest='不搬')), ('↑', lambda: self.mv(-1)), ('↓', lambda: self.mv(1)), ('🔀 併到…', self.merge), ('🗑 刪掉', self.dele)):
            b = QPushButton(t_); b.clicked.connect(fn); r.addWidget(b)
        r.addStretch(1)
        g = QGroupBox('SortCut（從它的「10 秒一張」預覽切 16 格，不用重新讀影片）'); gl = QHBoxLayout(g); v.addWidget(g)
        self.vs_l = QLabel(''); self.vs_l.setWordWrap(True); gl.addWidget(self.vs_l, 1); b1 = QPushButton('📁 指定 SortCut 資料夾'); b2 = QPushButton('↺ 自動找'); gl.addWidget(b1); gl.addWidget(b2)
        b1.clicked.connect(self.vs_pick); b2.clicked.connect(lambda: (ENG.cfg.set('vs_root', ''), self.vs_reload()))
        bc = QPushButton('關閉'); bc.clicked.connect(self.accept); v.addWidget(bc, 0, Qt.AlignRight)
        self.load(); self.vs_reload()

    def load(self):
        self.C = ENG.vc.cats(); self.tb.setRowCount(len(self.C))
        for i, c in enumerate(self.C):
            for j, val in enumerate((str((i + 1) % 10) if i < 10 else '', c['name'], ('📌 不搬（留在原處，只標記）' if (c['dest'] or '').strip() in vsort.STAY else c['dest']) or f'（預設：每顆硬碟的 \\{vsort.MOVE_DIR}\\{c["name"]}）', f"{c['n']:,}（還沒搬 {c['wait']:,}）")):
                self.tb.setItem(i, j, _ti(val, val, None, c['color'] if j == 1 else None))

    def cur(self):
        i = self.tb.currentRow(); return self.C[i] if 0 <= i < len(self.C) else None

    def add(self):
        nm, ok = QInputDialog.getText(self, '新增分類', '分類名稱（例如 工作、家庭、寵物）：')
        if ok and nm.strip():
            r = ENG.vc.cat_add(nm); self.page.win.msg(r['message']); self.load(); self.page.reload_cats()

    def _edit(self, **kw):
        c = self.cur()
        if not c: self.page.win.msg('先選一個分類'); return
        r = ENG.vc.cat_edit(c['id'], **kw); self.page.win.msg(r['message']); self.load(); self.page.reload_cats()

    def ren(self):
        c = self.cur()
        if not c: return
        nm, ok = QInputDialog.getText(self, '改名字', '新的名字：', text=c['name'])
        if ok: self._edit(name=nm)

    def dest(self):
        c = self.cur()
        if not c: return
        d = QFileDialog.getExistingDirectory(self, f'「{c["name"]}」要搬去哪', c['dest'] or str(Path.home()))
        if d: self._edit(dest=os.path.normpath(d))

    def mv(self, d):
        c = self.cur()
        if not c: return
        i = self.tb.currentRow(); ENG.vc.cat_move(c['id'], d); self.load(); self.tb.selectRow(max(0, min(len(self.C) - 1, i + d))); self.page.reload_cats()

    def merge(self):
        """🔀 兩類併成一類（V0.4.51，跟網頁一樣）."""
        c = self.cur()
        if not c: self.page.win.msg('先選一個分類'); return
        O = [x for x in self.C if x['id'] != c['id']]
        if not O: return
        nm, ok = QInputDialog.getItem(self, '🔀 併到哪一類', f'「{c["name"]}」還沒搬的 {c["wait"]:,} 部改到：', [x['name'] for x in O], 0, False)
        if not ok: return
        t = next((x for x in O if x['name'] == nm), None)
        if not t: return
        r = ENG.vc.cat_merge(c['id'], t['id']); self.page.win.msg(r['message']); self.load(); self.page.reload_cats()

    def dele(self):
        c = self.cur()
        if not c: return
        if QMessageBox.question(self, '刪掉分類', f'刪掉「{c["name"]}」？\n\n還沒搬的 {c["wait"]:,} 部會變回「沒分類」（已經搬過的檔案不動）。') != QMessageBox.Yes: return
        r = ENG.vc.cat_del(c['id']); self.page.win.msg(r['message']); self.load(); self.page.reload_cats()

    def vs_pick(self):
        d = QFileDialog.getExistingDirectory(self, '選 SortCut 的資料夾（裡面有 Data\\videosift.sqlite3）', str(ENG.cfg.get('vs_root') or Path.home()))
        if d: ENG.cfg.set('vs_root', os.path.normpath(d)); self.vs_reload()

    def vs_reload(self):
        self.vs_l.setText('找…'); bg(lambda: ENG.vc.vs_load(force=True), lambda V: (self.vs_l.setText(self.page.vs_text(V)), self.page.reload()))


class VcPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.ids = []; self.idx = 0; self.cache = OrderedDict_(); self.cats = []; self.undo = []; self.it = None; self.btns = []; self._tok = 0; self.tagged = set()
        v = QVBoxLayout(self); v.setContentsMargins(8, 6, 8, 6); v.setSpacing(5)
        r1 = QHBoxLayout(); v.addLayout(r1)
        self.flt = QComboBox(); self.ordc = QComboBox()
        for k, nm in (('path', '照資料夾'), ('taken', '照拍攝日期'), ('size', '大的先'), ('dur', '長的先'), ('rand', '🔀 打散'), ('tagged_last', '最近分好的先'), ('pet', '🐾 最像貓狗的先'), ('res', '畫質 高→低'), ('res_asc', '畫質 低→高')): self.ordc.addItem(nm, k)
        self.kc = QComboBox(); self.kc.addItem('🎞 影片', 'video'); self.kc.addItem('📷 照片', 'photo'); self.kc.setToolTip('切換：影片快速分類／照片快速分類（分類共用）')
        self.lnc = QComboBox()
        for k, nm in vsort.VSort.LEN_N: self.lnc.addItem(('⏱ ' if not k else '') + nm, k)
        b_many = QPushButton('📚 整批分類…'); b_many.setToolTip('現在這份清單（篩選＋資料夾＋長度大小）全部分到同一類'); b_many.clicked.connect(self.many)
        self.folder = QLineEdit(); self.folder.setPlaceholderText('資料夾路徑，或搜尋：日本 2019、日期:2020、相機:DJI、內容:有狗（空的＝全部）'); bf = QPushButton('…'); bf.setFixedWidth(30)
        b_ref = QPushButton('🔄'); b_ref.setToolTip('重新讀清單')
        self.gc = QComboBox(); self.gc.setToolTip('🧩 相關的排一起（V0.2.14）：資料夾包／同類型／同一段時間，一組一組審')
        for k, nm in vgroup.VGroup.MODES: self.gc.addItem(('🧩 ' if not k else '') + nm, k)
        self.gc.setCurrentIndex(max(0, self.gc.findData(ENG.cfg.get('vc_group') or ''))); self.gn = []; self.gi = []; self.gp = []
        for w_ in (self.kc, self.flt, self.ordc, self.lnc, self.gc): r1.addWidget(w_)
        r1.addWidget(self.folder, 1); r1.addWidget(bf); r1.addWidget(b_ref); r1.addWidget(b_many)
        self.pos = QLabel(''); self.pos.setObjectName('title'); r1.addWidget(self.pos)
        self.b_prev = QPushButton('◀ 上一部'); self.b_next = QPushButton('下一部 ▶'); self.b_undo = QPushButton('↶ 復原'); self.b_play = QPushButton('▶ 播放'); self.b_dir = QPushButton('📂')
        self.b_prev.setToolTip('← 鍵'); self.b_next.setToolTip('→ 或空白鍵（略過，不分類）'); self.b_undo.setToolTip('Backspace：回到上一部、取消剛剛的分類'); self.b_play.setToolTip('Enter：用預設播放器打開'); self.b_dir.setToolTip('在資料夾中顯示')
        self.b_fav = QPushButton('☆ 最愛'); self.b_fav.setToolTip('F：加到最愛（重複、相似時優先保留）'); self.b_fav.clicked.connect(self.toggle_fav)
        self.b_gnext = QPushButton('⏭ 下一組'); self.b_gnext.setToolTip('跳到下一組（] 鍵）'); self.b_gnext.clicked.connect(self.next_group)
        self.b_gview = QPushButton('👀 整組一覽'); self.b_gview.setToolTip('這組的縮圖一次看、整組分類（G 鍵）'); self.b_gview.clicked.connect(self.group_view)
        self.b_gkeep = QPushButton('✅ 整包已篩選'); self.b_gkeep.setToolTip('這部所在的資料夾包（你以前整理過、有取名字的資料夾）整包放到「已篩選」：保留資料夾結構、馬上搬'); self.b_gkeep.clicked.connect(self.keep_pack)
        for b_ in (self.b_prev, self.b_next, self.b_undo, self.b_play, self.b_dir, self.b_fav, self.b_gview, self.b_gnext, self.b_gkeep): r1.addWidget(b_)
        self.info = QLabel(''); self.info.setTextFormat(Qt.RichText); self.info.setTextInteractionFlags(Qt.TextSelectableByMouse); v.addWidget(self.info)
        self.catw = QWidget(); self.catg = QGridLayout(self.catw); self.catg.setContentsMargins(0, 0, 0, 0); self.catg.setSpacing(5); v.addWidget(self.catw)
        r3 = QHBoxLayout(); v.addLayout(r3)
        self.pend = QLabel(''); self.pend.setTextFormat(Qt.RichText); r3.addWidget(self.pend, 1)
        self.auto = QCheckBox('按了分類自動跳下一部'); self.auto.setChecked(ENG.cfg.get('vc_next') is not False); r3.addWidget(self.auto)
        self.b_clean = QPushButton('🧹 處理有問題的影片…'); self.b_clean.setToolTip('打不開 → delete、部分損毀 → check video、重複的（每組留一部）→ repeat；跟分類分開放')
        self.b_pet = QPushButton('🐾 找貓狗'); self.b_pet.setToolTip('電腦自己看 16 格裡有沒有貓、狗（Windows ML）；找到後上面篩選選「🐾 有貓或狗的」'); self.b_pet.clicked.connect(self.pet); r3.addWidget(self.b_pet)
        r3.addWidget(self.b_clean); self.b_move = QPushButton('🚚 開始搬檔'); self.b_move.setObjectName('start'); r3.addWidget(self.b_move)
        self.grid = FrameGrid(self.play); v.addWidget(self.grid, 1)
        self.flt.currentIndexChanged.connect(lambda _i: self._flt_changed()); self.ordc.currentIndexChanged.connect(lambda _i: self.reload()); self.lnc.currentIndexChanged.connect(lambda _i: self.reload()); self.gc.currentIndexChanged.connect(lambda _i: self.reload()); self.kc.currentIndexChanged.connect(lambda _i: (self.folder.setText(''), self.reload())); b_ref.clicked.connect(self.reload)
        self.folder.returnPressed.connect(self.reload); bf.clicked.connect(self._pick)
        self.b_prev.clicked.connect(lambda: self.go(self.idx - 1)); self.b_next.clicked.connect(lambda: self.go(self.idx + 1)); self.b_undo.clicked.connect(self.do_undo)
        self.b_play.clicked.connect(self.play); self.b_dir.clicked.connect(lambda: self.it and show_in_folder(self.it['path'])); self.b_move.clicked.connect(self.move); self.b_clean.clicked.connect(self.clean)
        self.auto.toggled.connect(lambda on: ENG.cfg.set('vc_next', bool(on)))
        for key, fn in (('Left', lambda: self.go(self.idx - 1)), ('Right', lambda: self.go(self.idx + 1)), ('Space', lambda: self.go(self.idx + 1)),
                        ('Backspace', self.do_undo), ('Ctrl+Z', self.do_undo), ('Shift+F', self._fsug_do), ('Shift+P', lambda: (self.flt.setCurrentIndex(max(0, self.flt.findData('pet'))))), ('Return', self.play), ('F', self.toggle_fav), (']', self.next_group), ('G', self.group_view), ('N', lambda: self.go(self._next_todo(self.idx)))):
            sc = QShortcut(QKeySequence(key), self); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(fn)
        for n in range(10):
            sc = QShortcut(QKeySequence(str(n)), self); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(lambda n=n: self.assign_idx((n - 1) % 10))
            sc = QShortcut(QKeySequence(f'Ctrl+{n}'), self); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(lambda n=n: self.assign_idx(10 + (n - 1) % 10))   # 第 11～20 類（V0.3.38）
        for key, fn in (('R', lambda: self._last_cat is not None and self.assign_idx(self._last_cat)), ('P', self._prev_todo), ('A', self._accept_hint)):
            sc = QShortcut(QKeySequence(key), self); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(fn)
        self._last_cat = None
        self.setFocusPolicy(Qt.StrongFocus)
        for b_ in self.findChildren(QPushButton) + [self.auto]: b_.setFocusPolicy(Qt.NoFocus)          # 按鈕不搶鍵盤（空白鍵＝下一部，不會誤按到分類）
        self.tm = QTimer(self); self.tm.timeout.connect(self._tick); self.tm.start(1500); self._first = True

    # ---- 清單、分類按鈕
    def showEvent(self, e):
        super().showEvent(e)
        if self._first: self._first = False; self.reload_cats(); self.reload()
        self.setFocus()

    def vs_text(self, V):
        if V.get('db'): return f"🔗 SortCut：{esc_html(V['db'])}　（{V.get('n', 0):,} 部有預覽圖可以直接用）" + (f"<br><span style='color:#ff4d6d'>{esc_html(V['err'])}</span>" if V.get('err') else '')
        return '沒找到 SortCut（找它的 Data\\videosift.sqlite3）：每部影片改用 FFmpeg 自己抓 16 格（第一次約 1 秒，下一部會先在背景做好）'

    def reload_cats(self):
        bg(ENG.vc.cats, self._got_cats)

    def _got_cats(self, C):
        self.cats = C; cur = self.flt.currentData(); self.flt.blockSignals(True); self.flt.clear()
        for k, nm in (('todo', '還沒分類的'), ('todo_np', '還沒分類・不在資料夾包裡'), ('todo_pk', '還沒分類・在資料夾包裡'), ('todo_sug', '💡 還沒分類・電腦有建議的'), ('pet', '🐾 還沒分類・有貓或狗的'), ('pet_dog', '🐶 還沒分類・有狗的'), ('pet_cat', '🐱 還沒分類・有貓的'), ('pet_face', '👤 還沒分類・有人臉的'), ('pet_noface', '🏞 還沒分類・沒有人臉的'), ('pet_s_petppl', '🐾👤 還沒分類・有貓狗、也有人'), ('pet_s_petonly', '🐾 還沒分類・只有貓狗（沒拍到人）'), ('pet_s_many', '👥 還沒分類・3 個人以上'), ('pet_s_junk', '🌑 還沒分類・全黑／沒東西／沒動'), ('pet_s_dark', '🌑 還沒分類・很暗／全黑'), ('pet_s_flat', '⬜ 還沒分類・畫面幾乎沒東西'), ('pet_s_still', '🧱 還沒分類・畫面幾乎沒動')) + tuple(('pet_s_' + k, '🔎 還沒分類・' + nm) for k, nm, _ in getattr(sys.modules.get('pets'), 'SCENES', [])) + (('all', '全部影片'), ('wait', '分好、還沒搬的'), ('chk', '🧐 可能分錯的（分好還沒搬）'), ('done', '已經搬過的')): self.flt.addItem(nm, k)
        for c in C: self.flt.addItem(f'只看「{c["name"]}」', f'c{c["id"]}')
        i = self.flt.findData(cur); self.flt.setCurrentIndex(i if i >= 0 else 0); self.flt.blockSignals(False)
        while self.catg.count():
            w_ = self.catg.takeAt(0).widget()
            if w_: w_.deleteLater()
        self.btns = []
        for i, c in enumerate(C):
            b = QPushButton(); b.setMinimumHeight(46); b.setCheckable(True); b.setFocusPolicy(Qt.NoFocus); b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            b.setStyleSheet(f"QPushButton{{border-left:6px solid {c['color']};font-weight:800;font-size:15px;text-align:left;padding-left:10px}}"
                            f"QPushButton:checked{{background:{c['color']};color:#ffffff;border-color:{c['color']}}}")
            b.clicked.connect(lambda _c=False, i=i: self.assign_idx(i)); self.catg.addWidget(b, i // 7, i % 7); self.btns.append(b)
        n = len(C); ba = QPushButton('＋ 新增分類'); ba.setMinimumHeight(46); bm = QPushButton('⚙ 管理'); bm.setMinimumHeight(46); ba.setFocusPolicy(Qt.NoFocus); bm.setFocusPolicy(Qt.NoFocus)
        ba.clicked.connect(self.add_cat); bm.clicked.connect(lambda: VcCatDlg(self).exec())
        self.catg.addWidget(ba, n // 7, n % 7); self.catg.addWidget(bm, (n + 1) // 7, (n + 1) % 7)
        for c_ in range(7): self.catg.setColumnStretch(c_, 1)
        self._btn_text(); self._pend()

    def _btn_text(self):
        cur = (self.it or {}).get('cat'); hn = (self.it or {}).get('hint')
        for i, (b, c) in enumerate(zip(self.btns, self.cats)):
            key = str((i + 1) % 10) if i < 10 else (f'Ctrl+{(i - 9) % 10}' if i < 20 else ' ')
            gb = (c.get('b') or 0) / 1e9; gbs = '<1 GB' if 0 < gb < 0.5 else f'{round(gb):,} GB'
            b.setText(f"{key}  {c['name']}" + ('  💡' if hn and hn[0] == c['id'] and cur != c['id'] else '') + f"\n     {c['n']:,} 部・{gbs}" + (f"（還沒搬 {c['wait']:,}）" if c['wait'] else '')); b.setChecked(cur == c['id'])
            if hn and hn[0] == c['id'] and cur != c['id'] and self.it and getattr(self, '_hfl', None) != self.it['id']:
                self._hfl = self.it['id']; self._flash(b, c['color'])

    def _flash(self, b, col):
        """💡 建議的分類整格亮一下、2 秒慢慢變暗（V0.2.63）."""
        ss0 = getattr(b, '_ss0', None)
        if ss0 is None: ss0 = b._ss0 = b.styleSheet()
        q = QColor(col); step = [0]
        tm = getattr(b, '_fltm', None)
        if tm: tm.stop()
        tm = b._fltm = QTimer(b)

        def tick():
            k = step[0]; step[0] += 1; a = max(0, 255 - k * 13)                      # 20 步 × 100 毫秒 ≈ 2 秒
            if a <= 0: tm.stop(); b.setStyleSheet(ss0); return
            b.setStyleSheet(ss0 + f"QPushButton{{background:rgba({q.red()},{q.green()},{q.blue()},{a});color:#fff}}")
        tm.timeout.connect(tick); tm.start(100); tick()

    def toggle_fav(self):
        if not self.it: return
        on = not self.it.get('fav'); ENG.fav_set(self.it['id'], on); self.it['fav'] = 1 if on else 0
        self.b_fav.setText('⭐ 最愛' if on else '☆ 最愛'); self.win.msg('⭐ 加到最愛' if on else '取消最愛')

    def add_cat(self):
        nm, ok = QInputDialog.getText(self, '新增分類', '分類名稱（例如 工作、家庭、寵物）：')
        if ok and nm.strip(): r = ENG.vc.cat_add(nm); self.win.msg(r['message']); self.reload_cats()

    def _pick(self):
        d = pick_folder(self, '只看這個資料夾底下的影片')
        if d: self.folder.setText(os.path.normpath(d)); self.reload()

    def reload(self):
        f, o, fo = self.flt.currentData() or 'todo', self.ordc.currentData() or 'path', self.folder.text().strip(); keep = self.it['id'] if self.it else None
        ln = self.lnc.currentData() or ''; k = self.kc.currentData() or 'video'; gm = self.gc.currentData() or ''
        try: ENG.cfg.set('vc_group', gm)
        except Exception: pass
        q_ = ''
        if fo and not os.path.isabs(fo) and not re.match(r'^[A-Za-z]:', fo) and '\\' not in fo and '/' not in fo: q_, fo = fo, ''   # 🔍 不是資料夾路徑＝當搜尋字（日期:、相機:、內容:有狗…）（V0.4.29，跟網頁一樣）
        def work():
            L = ENG.vc.vlist(f, fo, o, ln=ln, kind=k, q=q_)
            G = ENG.vg.group(L, gm, o) if gm else (L, [], [], [])
            try: T = set(ENG.vc.tags_of(G[0]))
            except Exception: T = set()
            return tuple(G) + (T,)
        bg(work, lambda R, keep=keep: self._got_list(R, keep))

    def _grange(self, i):
        g = self.gi[i]; s_ = i; e_ = i
        while s_ > 0 and self.gi[s_ - 1] == g: s_ -= 1
        while e_ < len(self.ids) - 1 and self.gi[e_ + 1] == g: e_ += 1
        return s_, e_, g

    def next_group(self):
        if not self.gn or not self.ids: self.win.msg('先在上面選「🧩 相關的排一起」'); return
        _s, e_, _g = self._grange(self.idx)
        if e_ >= len(self.ids) - 1: self.win.msg('已經是最後一組了'); return
        k = e_ + 1; sk = 0                                                          # 整組都分好的跳過（V0.2.86）
        while k < len(self.ids):
            s2, e2, _g2 = self._grange(k); todo = [j for j in range(s2, e2 + 1) if self.ids[j] not in self.tagged]
            if todo: k = todo[0]; break
            sk += 1; k = e2 + 1
        if k >= len(self.ids): k = e_ + 1; sk = 0
        if sk: self.win.msg(f'⏭ 跳過 {sk} 組已經分完的', 2500)
        self.go(k)

    def group_view(self):
        if not self.gn or not self.ids: self.win.msg('先在上面選「🧩 相關的排一起」（資料夾包／同類型／同一段時間…）'); return
        s_, e0, g = self._grange(self.idx); big = e0 - s_ + 1 > 400                   # 一次最多 400 部（V0.2.48）：只顯示、只處理這一批
        st = min(self.idx, max(s_, e0 - 399)) if big else s_; e_ = st + 399 if big else e0
        d = GrpDlg(self, st, e_, g)
        if big: d.setWindowTitle(d.windowTitle() + f'　（這組 {e0 - s_ + 1:,} 部，這一批第 {st - s_ + 1:,}～{e_ - s_ + 1:,} 部）')
        d.exec(); res = d.res
        if not res: return
        self.reload_cats(); self.cache.clear()
        a, x = res
        if a == 'go': self.go(x)
        elif a == 'undo': self.go(x); QTimer.singleShot(350, self.group_view)
        elif a == 'keep':
            self.keep_pack_path(x)
        elif a in ('next', 'chain'):
            if big and a == 'chain':                                                  # 大組：接著看同一組還沒分的下一批
                T = ENG.vc.tags_of(self.ids[s_:e0 + 1]); nx = next((k for k in range(s_, e0 + 1) if self.ids[k] not in T), None)
                if nx is not None: self.go(nx); QTimer.singleShot(350, self.group_view); return
            if e0 >= len(self.ids) - 1: self.win.msg('🎉 最後一組了'); self.go(self.idx); return
            self.go(e0 + 1)
            if a == 'chain' or a == 'next': QTimer.singleShot(350, self.group_view)
        else: self.go(self.idx)

    def keep_pack_path(self, p):
        nm = os.path.basename(p); g = ENG.vg.pack_info(p) or {}
        sz = f"{g.get('n', 0):,} 部影片" + (f"＋{g['np']:,} 張照片" if g.get('np') else '') if g else '（影片＋照片）'
        if QMessageBox.question(self, '✅ 整包已篩選', f'「{nm}」整包 {sz} 放到「已篩選」並馬上搬？\n\n會保留資料夾：同一顆硬碟的 \\FileCompare_分類\\已篩選\\{nm}\\…') != QMessageBox.Yes: return
        r = ENG.vg.pack_tag(p); msg = r['message'].split('，按 🚚')[0]
        if r.get('ok') and r.get('ids') and ENG.vc.move_start(r['ids']): msg += '；🚚 開始搬這一包（背景）'
        self.win.msg(msg, 8000); self.reload_cats(); self.reload()

    def _cur_pack(self):
        if self.gn and self.ids and self.gp:
            p = self.gp[self.gi[self.idx]]
            if p: return p
        try: return (ENG.vg.pack_brief(self.it['path']) or {}).get('path') if self.it else ''
        except Exception: return ''

    def keep_pack(self):
        p = self._cur_pack()
        if not p: self.win.msg('這部不在「資料夾包」裡（資料夾沒有取名字，或是手機整台倒出來的）'); return
        self.keep_pack_path(p)

    def _flt_changed(self):
        """選「有貓狗的」時自動改成最像的排前面（跟網頁一樣）（V0.4.01）."""
        k = str(self.flt.currentData() or '')
        if k in ('pet', 'pet_dog', 'pet_cat') or k.startswith('pet_s_pet'):
            i = self.ordc.findData('pet')
            if i >= 0 and self.ordc.currentIndex() != i:
                self.ordc.blockSignals(True); self.ordc.setCurrentIndex(i); self.ordc.blockSignals(False)
        self.reload()

    def pet(self):
        """🐾 找有貓狗的影片（V0.2.95）."""
        st = ENG.pet.status()
        if st.get('run'):
            if QMessageBox.question(self, '🐾 找貓狗', f"{st.get('msg', '')}\n\n要停下來嗎？") == QMessageBox.Yes: ENG.pet.st['cancel'] = True
            return
        info = f"看過 {st.get('checked', 0):,} 部：🐶 有狗 {st.get('dog', 0):,}、🐱 有貓 {st.get('cat', 0):,}、👤 有人臉 {st.get('face', 0):,}" + (f"\n上次：{st['msg']}" if st.get('msg') else '') + (f"\n⚠ {st['err']}" if st.get('err') else '')
        SC = st.get('scenes') or []
        if SC: info += '\n\n🔎 還沒分類的，電腦猜的內容（點下面按鈕只看那些）：\n' + '\n'.join(f"　{x['name']}：{x['n']:,} 部" for x in SC)
        b = QMessageBox(self); b.setWindowTitle('🐾 電腦看內容'); b.setText(info + '\n\n電腦自己看每部的 16 格裡有沒有貓、狗、人臉（Windows 內建的 Windows ML；第一次會下載 14 MB 的辨識模型），還沒做 16 格的會順便先做；也會找出全黑、沒東西、沒動的影片。背景做。\n找到後用上面的篩選（🐾／🔎 還沒分類・…）只看那些，再用「📚 整批分類」分。')
        t = b.addButton('試 20 部', QMessageBox.ActionRole); a = b.addButton('🐾 全部開始找', QMessageBox.AcceptRole)
        vb = {b.addButton(x['name'].split('（')[0][:14], QMessageBox.ActionRole): x for x in SC[:6]}
        lb = {b.addButton(f"💡 {x['name'].split(' ', 1)[-1].split('（')[0][:8]} → {x['ln']}", QMessageBox.ActionRole): x for x in SC if x.get('lc')}   # 你以前這種大多分到哪（V0.4.05）
        b.addButton('關閉', QMessageBox.RejectRole); b.exec()
        cb = b.clickedButton()
        if cb in lb:
            x = lb[cb]
            if QMessageBox.question(self, '🐾 一次分', f"還沒分類、電腦看是「{x['name']}」的 {x['n']:,} 部，全部分到「{x['ln']}」？\n\n（你以前這種的大多分到這類。電腦會看錯，不放心就先用篩選看過。）只是標記，按 🚚 搬才會搬。") != QMessageBox.Yes: return
            r = ENG.vc.tag_many(ENG.vc.vlist('pet_s_' + x['k']), int(x['lc']), only_new=True); ENG.pet._scc = {}
            self.win.msg(r.get('message') or '好了', 4000); self.reload(); return
        if cb in vb:
            i = self.flt.findData('pet_s_' + vb[cb]['k'])
            if i >= 0: self.flt.setCurrentIndex(i)
            return
        if cb in (t, a): ENG.pet.start(20 if cb is t else 0); self.win.msg('🐾 開始找（背景）', 4000)

    def many(self):
        if not self.ids: self.win.msg('這份清單是空的'); return
        if not self.cats: self.win.msg('先新增分類'); return
        T = ENG.vc.tags_of(self.ids); nt = sum(1 for i in self.ids if i not in T)
        names = [c['name'] for c in self.cats] + ['✖ 取消分類']
        nm, ok = QInputDialog.getItem(self, '📚 整批分類', f'現在這份清單 {len(self.ids):,} 部（還沒分的 {nt:,} 部）\n全部分到哪一類？（已經分好的不改、搬過的不動）', names, 0, False)
        if not ok: return
        cid = 0 if nm == names[-1] else self.cats[names.index(nm)]['id']
        r = ENG.vc.tag_many(self.ids, cid, only_new=bool(cid)); self.win.msg(r['message']); self.reload_cats(); self.reload()

    def _got_list(self, R, keep):
        L, self.gn, self.gi, self.gp = R[:4]; self.tagged = set(R[4]) if len(R) > 4 else set()
        self.ids = L; self.undo = []; self.idx = L.index(keep) if keep in L else 0; self.cache.clear()
        if not L: self.it = None; self.grid.set_data([], [], 0, '這裡沒有影片' + ('（全部都分好了 🎉）' if (self.flt.currentData() or 'todo') == 'todo' and self.cats else '')); self.info.setText(''); self.pos.setText('0／0'); self._btn_text(); return
        self.go(self.idx)

    # ---- 顯示一部
    def _load(self, fid):
        """背景：影片資料＋16 格（從 VS 的大張切出來，或自己做的 4×4）."""
        it = ENG.vc.item(fid); g = ENG.vc.grid(fid) if it else {'ok': False}
        if it:
            try: it['pack'] = ENG.vg.pack_brief(it['path'])
            except Exception: it['pack'] = None
        if not g.get('ok'): return it, g, [], []
        if g.get('photo'):                                                          # 📷 照片：一張大圖
            p = ENG.fc_thumb(fid, 1600); im = QImage(p) if p else QImage()
            if im.isNull(): return it, {'ok': False}, [], []
            g = dict(g, ar=im.width() / max(1, im.height())); return it, g, [im], []
        S = {}; out = []; pc = None
        try:                                                                         # 🐾 電腦看到貓狗的那一格框起來（V0.3.96）
            r_ = ENG.db.one('SELECT pc, dog, cat, face, lum, lstd, mot, COALESCE(sc, top), sp FROM vc_pet WHERE fid=?', (int(fid),))
            if r_ and r_[0] and max(r_[1] or 0, r_[2] or 0) >= ENG.pet.th(): pc = r_[0]
            if r_ and it is not None:                                                # 🐾 電腦看到的（跟網頁一樣寫在資訊列）（V0.4.17）
                import fc_pets as _pm; P_ = []
                if max(r_[1] or 0, r_[2] or 0) >= 0.15: P_.append(f"🐶 {round((r_[1] or 0) * 100)}%" if (r_[1] or 0) >= (r_[2] or 0) else f"🐱 {round((r_[2] or 0) * 100)}%")
                if (r_[3] or 0) > 0: P_.append(f'👤 {r_[3]}')
                if r_[4] is not None and 0 <= r_[4] < _pm.DARK: P_.append('🌑 很暗')
                elif r_[5] is not None and 0 <= r_[5] < _pm.FLAT: P_.append('⬜ 沒東西')
                elif r_[6] is not None and 0 <= r_[6] < _pm.STILL: P_.append('🧱 沒動')
                elif r_[7] is not None and r_[7] >= 0 and (r_[8] is None or r_[8] < 0 or r_[8] >= _pm.SCENE_P):
                    k_ = ENG.pet.scene_of(r_[7]); nm_ = next((n for kk, n, _S in _pm.SCENES if kk == k_), '')
                    if nm_: P_.append(nm_.split('／')[0])
                it['petinfo'] = '・'.join(P_)
            if it is not None and it.get('cat'):                                     # 🧐 可能分錯的原因（V0.4.38）
                c_ = getattr(ENG.vc, '_sus', None); sv = (c_[2] if c_ else ENG.vc.suspects()).get(int(fid))
                if sv: it['petinfo'] = ((it.get('petinfo') or '') + '・🧐 ' + sv[1]).strip('・')
        except Exception: pc = None
        for c in g['cells']:
            im = S.get(c['s'])
            if im is None: im = S[c['s']] = QImage(g['sheets'][c['s']])
            if im.isNull(): continue
            cw = im.width() // g['cols']; ch = im.height() // g['rows']; cut = im.copy(c['c'] * cw, c['r'] * ch, cw, ch)
            if pc and pc == f"{c['s']},{c['c']},{c['r']}":
                try:
                    pp = QPainter(cut); pp.setPen(QPen(QColor('#f5a623'), max(3, cw // 50))); pp.drawRect(1, 1, cw - 3, ch - 3); pp.end()
                except Exception: pass
            out.append(cut)
        return it, g, out, [c['t'] for c in g['cells']]

    def go(self, i):
        if not self.ids: return
        i = max(0, min(len(self.ids) - 1, int(i))); self.idx = i; fid = self.ids[i]; self._tok += 1; tok = self._tok
        gt = ''
        if self.gn:
            s_, e_, g = self._grange(i); gt = f'　{self.gn[g]}（第 {g + 1}／{len(self.gn)} 組・{i - s_ + 1}／{e_ - s_ + 1}）'
        self.pos.setText(f'{i + 1:,}／{len(self.ids):,}' + gt)
        if fid in self.cache: self._show(self.cache[fid], tok)
        else:
            self.grid.set_data([], [], 0, '載入中…')
            bg(lambda: self._load(fid), lambda R, fid=fid, tok=tok: (self._put(fid, R), self._show(R, tok)))
        nxt = self.ids[i + 1:i + 4]; ENG.vc.prefetch(nxt)
        for n_ in nxt[:2]:
            if n_ not in self.cache: bg(lambda n_=n_: self._load(n_), lambda R, n_=n_: self._put(n_, R))

    def _put(self, fid, R):
        self.cache[fid] = R
        while len(self.cache) > 10: self.cache.popitem(last=False)

    def _show(self, R, tok):
        if tok != self._tok: return
        it, g, imgs, T = R
        if not it: self.it = None; self.grid.set_data([], [], 0, '找不到這部（可能被搬走了，按 🔄）'); return
        if it['id'] != self.ids[self.idx]: return
        self.it = it; c = next((c for c in self.cats if c['id'] == it['cat']), None); self.b_fav.setText('⭐ 最愛' if it.get('fav') else '☆ 最愛')
        tag = (f"<b style='color:{c['color']}'>■ {esc_html(c['name'])}</b>" + ('（已搬）' if it['moved'] else '') if c else "<span style='color:#8994a4'>還沒分類</span>")
        src = {'vs': f"SortCut 預覽（每 {g.get('step', 0):g} 秒一張，共 {g.get('vs_n', 0)} 張，挑 {len(imgs)} 張）", 'fc': '自己抓的 16 格'}.get(g.get('src'), '')
        res = f"{it['w']}×{it['h']}" if it['w'] else ''
        self.info.setText(f"{tag}　<b>{esc_html(it['name'])}</b>　{fmt_t(it['dur']) + '・' if it['dur'] else ''}{fmt_b(it['size'])}・{fmt_day(it['taken'])[:10]}" + (f'・{res}' if res else '')
                          + (f"・{esc_html(it['model'])}" if it['model'] else '') + (f"・<span style='color:#f5a623'>{esc_html(it['petinfo'])}</span>" if it.get('petinfo') else '') + f"　<span style='color:#8994a4'>{esc_html(os.path.dirname(it['path']))}　{src}</span>"
                          + (f"<br><span style='color:#45d483'>📦 在你整理過的「<b>{esc_html(it['pack']['name'])}</b>」（還有 {it['pack']['todo']:,} 部沒審）→ 「✅ 整包已篩選」或資料夾包頁整包看</span>" if it.get('pack') and it['pack'].get('todo', 0) >= 2 else ''))
        try: self.b_gkeep.setEnabled(bool(it.get('pack')) or bool(self.gp and self.gp[self.gi[self.idx]]))
        except Exception: pass
        self.grid.set_data(imgs, T, g.get('ar') or 16 / 9, g.get('message', '') if not imgs else ''); self._btn_text()

    # ---- 分類、復原、播放
    def assign_idx(self, i):
        if not (0 <= i < len(self.cats)) or not self.ids: return
        self._last_cat = i
        if not self.it or self.it.get('id') != self.ids[self.idx]:                   # 下一部還在讀：照現在這一格分，不會分到上一部（V0.3.32）
            c = self.cats[i]; fid = self.ids[self.idx]; j0 = self.idx
            self.undo.append((fid, 0, j0)); self.tagged.add(fid)
            bg(lambda: ENG.vc.tag(fid, c['id']), lambda r: (self.reload_cats(), self._pend()))
            if self.auto.isChecked() and j0 < len(self.ids) - 1: self.go(self._next_todo(j0))
            return
        c = self.cats[i]; it = self.it
        if it.get('moved'): self.win.msg('這部已經搬過了（要改的話先到「📦 隔離區」復原）'); return
        prev = it.get('cat') or 0; self.undo.append((it['id'], prev, self.idx)); self.undo = self.undo[-500:]
        it['cat'] = c['id']; c['n'] += 0 if prev == c['id'] else 1; c['wait'] += 0 if prev == c['id'] else 1; c['b'] = (c.get('b') or 0) + (0 if prev == c['id'] else it['size'] or 0)
        p = next((x for x in self.cats if x['id'] == prev), None)
        if p and prev != c['id']: p['n'] -= 1; p['wait'] -= 1; p['b'] = (p.get('b') or 0) - (it['size'] or 0)
        hn_ = it.get('hint') if not prev else None
        bg(lambda: (ENG.vc.hstat(hn_, c['id']), ENG.vc.tag(it['id'], c['id']))[1], lambda r: self.win.msg(r.get('message', '')) if not r.get('ok') else (r.get('dup') and self.win.msg(f"🗑 另外 {r['dup']} 個一模一樣的副本標成「Delete」（只留這一份）", 4000)))
        self.cache.pop(it['id'], None); self._btn_text(); self._pend()
        self.tagged.add(it['id'])
        try:                                                                         # 📁 同資料夾連續 3 部同一類 → Shift＋F 剩下的全部（V0.4.07，跟網頁一樣）
            d = os.path.dirname(it['path']); st = getattr(self, '_stk', None)
            self._stk = (d, c['id'], st[2] + 1) if st and st[0] == d and st[1] == c['id'] else (d, c['id'], 1)
            if self._stk[2] == 3:
                e_ = fcore.like_esc(d.rstrip('\\/')); S_ = set(self.ids); T_ = ENG.vc.tags_of(self.ids)
                rest = [r[0] for r in ENG.db.q("SELECT id FROM files WHERE state='' AND path LIKE ? ESCAPE '^' AND path NOT LIKE ? ESCAPE '^'", (e_ + os.sep + '%', e_ + os.sep + '%' + os.sep + '%'))
                        if r[0] in S_ and r[0] not in T_ and r[0] not in self.tagged and r[0] != it['id']]
                if len(rest) >= 3: self._fsug = (rest, c); self.win.msg(f"📁 這個資料夾你連續 3 部都分「{c['name']}」，還有 {len(rest):,} 部沒分：按 Shift＋F 全部分「{c['name']}」", 6000)
        except Exception: pass
        if self.auto.isChecked() and self.idx < len(self.ids) - 1:
            j = self._next_todo(self.idx)                                           # V0.2.68：跳過已經分好的，到下一部還沒分的
            if j - self.idx > 1: self.win.msg(f'⏭ 跳過 {j - self.idx - 1:,} 部已經分好的', 2500)
            self.go(j)
        else: self._show_tag()

    def _fsug_do(self):
        f = getattr(self, '_fsug', None)
        if not f: self.win.msg('同一個資料夾連續分 3 部同一類之後才能用'); return
        rest, c = f; self._fsug = None; ids = [x for x in rest if x not in self.tagged]
        if not ids: self.win.msg('都分好了'); return
        r = ENG.vc.tag_many(ids, c['id'], only_new=True); self.tagged.update(ids)
        for x in ids: self.undo.append((x, 0, self.ids.index(x) if x in self.ids else self.idx))
        self.undo = self.undo[-2000:]; self.cache.clear(); self.reload_cats(); self._pend()
        self.win.msg(f"📁 這個資料夾剩下的 {len(ids):,} 部 → 「{c['name']}」（{r.get('message', '')}；Backspace 一部一部復原）", 5000)

    def _accept_hint(self):
        hn = (self.it or {}).get('hint') if self.it and self.ids and self.it.get('id') == self.ids[self.idx] else None
        if not hn: self.win.msg('這部沒有建議'); return
        i = next((k for k, c in enumerate(self.cats) if c['id'] == hn[0]), None)
        if i is not None: self.assign_idx(i)

    def _prev_todo(self):
        for j in range(self.idx - 1, -1, -1):
            if self.ids[j] not in self.tagged: return self.go(j)
        self.win.msg('前面都分好了')

    def _next_todo(self, i):
        """i 之後第一部還沒分類的；後面都分好了就回 i+1."""
        for j in range(i + 1, len(self.ids)):
            if self.ids[j] not in self.tagged: return j
        return min(i + 1, len(self.ids) - 1)

    def _show_tag(self):
        if self.it: self.cache.pop(self.it['id'], None); self.go(self.idx)

    def do_undo(self):
        if not self.undo: self.win.msg('沒有可以復原的'); return
        fid, prev, i = self.undo.pop()
        if prev: self.tagged.add(fid)
        else: self.tagged.discard(fid)
        bg(lambda: ENG.vc.tag(fid, prev), lambda _r: (self.cache.pop(fid, None), self.reload_cats(), self.go(i if fid not in self.ids else self.ids.index(fid))))

    def play(self):
        if self.it: open_file(self.it['path'])

    # ---- 搬檔
    def _pend(self):
        W = [c for c in self.cats if c['wait']]; M = ENG.vc.mv
        if M.get('run'): s = f"<span style='color:#4dc9ff'>{'🧹 處理有問題的影片' if M.get('what') == 'clean' else '🚚 搬檔'}中：{M.get('n', 0):,}／{M.get('total', 0):,}</span>"
        elif W: s = '分好、還沒搬：' + '　'.join(f"<b style='color:{c['color']}'>{esc_html(c['name'])} {c['wait']:,}</b>" for c in W)
        else: s = "<span style='color:#8994a4'>按上面的分類（或鍵盤 1～9、0）：先記下來，不搬檔；一個段落後按「🚚 開始搬檔」。← → 換一部、Backspace 復原、Enter 播放。</span>"
        if M.get('msg') and not M.get('run'): s += f"　<span style='color:#45d483'>上次：{esc_html(M['msg'])}</span>"
        self.pend.setText(s); self.b_clean.setEnabled(not M.get('run')); self.b_move.setEnabled(bool(W) and not M.get('run')); self.b_move.setText(f"🚚 開始搬檔（{sum(c['wait'] for c in W):,} 部）" if W else '🚚 開始搬檔')

    def _tick(self):
        if not self.isVisible(): return
        M = ENG.vc.mv
        if M.get('run') or getattr(self, '_was_run', False):
            self._was_run = bool(M.get('run')); self._pend()
            if not M.get('run'): self.reload_cats(); self.reload()

    def clean(self):
        self.b_clean.setEnabled(False); bg(ENG.vc.clean_plan, self._clean_ask)

    def _clean_ask(self, P):
        self.b_clean.setEnabled(True); n = sum(P[k]['n'] for k in ('delete', 'check', 'repeat'))
        L = [f"• 打不開／0 位元組：{P['delete']['n']:,} 部（{fmt_b(P['delete']['b'])}）→ delete",
             f"• 部分損毀：{P['check']['n']:,} 部（{fmt_b(P['check']['b'])}）→ check video",
             f"• 重複的（每組留一部：檔名有拍攝日期、修改日期最早的優先）：{P['repeat']['n']:,} 部（{fmt_b(P['repeat']['b'])}）→ repeat"]
        if P.get('unchecked'): L.append(f"\n⚠ 還有 {P['unchecked']:,} 部影片還沒做完損毀檢查")
        if P.get('unhashed'): L.append(f"⚠ 還有 {P['unhashed']:,} 部影片還沒比對完重複")
        if not n: QMessageBox.information(self, '有問題的影片', '目前沒有要搬的。\n\n' + '\n'.join(L)); return
        if QMessageBox.question(self, '處理有問題的影片', '\n'.join(L) + f"\n\n搬到每顆硬碟的 \\{P['dir']}\\delete、check video、repeat（保留原本的資料夾結構，跟分類分開）。"
                                '\n不會刪任何檔案；搬錯了在「📦 隔離區」復原。\n\n開始？') != QMessageBox.Yes: return
        ENG.vc.clean_start(); self._was_run = True; self._pend()

    def move(self):
        P = ENG.vc.move_plan()
        if not P: return
        d = QDialog(self); d.setWindowTitle('🚚 開始搬檔'); v = QVBoxLayout(d)              # 可以只勾幾類搬（V0.2.90）
        v.addWidget(QLabel('勾要搬的分類（預設全部）。只在同一顆硬碟裡搬（瞬間完成）；搬錯了可以在「📦 隔離區」復原。\n⚠ SortCut 會看到這些影片換了位置（它重新掃描就好）。'))
        try:                                                                         # 🧐 可能分錯的（V0.4.34，跟網頁一樣）
            ns = len(ENG.vc.suspects())
            if ns:
                ls = QLabel(f'🧐 有 {ns:,} 部可能分錯了（跟同資料夾、或你平常的分法不一樣）：可以先取消，篩選選「🧐 可能分錯的」看一下'); ls.setWordWrap(True); ls.setStyleSheet('color:#f5a623'); v.addWidget(ls)
        except Exception: pass
        cks = []
        for p in P:
            ck = QCheckBox(f"{p['name']}：{p['n']:,} 部 → {p['dest']}"); ck.setChecked(True); v.addWidget(ck); cks.append((ck, p))
            for x in (p.get('ex') or [])[:2]:                                        # 例子：原本在哪 → 會搬到哪（V0.3.62）
                lb = QLabel(f"　　例：{x['src']}\n　　　→ {x['dst']}"); lb.setStyleSheet('color:#8994a4;font-size:11px'); lb.setWordWrap(True); v.addWidget(lb)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); v.addWidget(bb)
        if d.exec() != QDialog.Accepted: return
        cs = {p['id'] for ck, p in cks if ck.isChecked()}
        if not cs: return
        only = None if len(cs) == len(cks) else [r[0] for r in ENG.db.q('SELECT fid, cat FROM vc_tag WHERE moved=0') if r[1] in cs]
        ENG.vc.move_start(only); self._was_run = True; self._pend(); self.setFocus()


# ============================================================ 🧹 雜物清理（V0.1.23）：資料分析時順便找到的空資料夾、0 位元組、暫存雜檔、最大的檔
class JunkPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.rows = []; self.kind = 'temp'
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('🧹 雜物清理'); t.setObjectName('title'); r.addWidget(t)
        self.st = QLabel(''); self.st.setObjectName('muted'); self.st.setWordWrap(True); r.addWidget(self.st, 1)
        v.addWidget(note('資料分析時順便找到的（遊戲／軟體資料夾裡的不算）。搬到同一顆硬碟的「_FileCompare_待確認\\雜物：…」，在「📦 隔離區」可以復原。要找最新的：到「📈 資料分析」按「🔄 重新分析」。'))
        self.kb = QHBoxLayout(); v.addLayout(self.kb); self.kbtn = {}
        for k, ic, nm in ana.JUNK_KINDS:
            b = QPushButton(f'{ic} {nm}'); b.setCheckable(True); b.clicked.connect(lambda _c=False, k=k: self.pick(k)); self.kb.addWidget(b); self.kbtn[k] = b
        self.kb.addStretch(1)
        self.desc = QLabel(''); self.desc.setObjectName('muted'); self.desc.setWordWrap(True); v.addWidget(self.desc)
        self.tb = QTableWidget(0, 3); self.tb.setHorizontalHeaderLabels(['位置', '大小', '修改日期']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tb.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch); self.tb.setColumnWidth(1, 110); self.tb.setColumnWidth(2, 110); v.addWidget(self.tb, 1)
        self.tb.cellDoubleClicked.connect(lambda r_, _c: 0 <= r_ < len(self.rows) and show_in_folder(self.rows[r_]['path']))
        rb = QHBoxLayout(); v.addLayout(rb)
        self.b_all = QPushButton('📦 這一類全部搬到隔離區'); self.b_sel = QPushButton('📦 搬選取的'); self.b_dir = QPushButton('📂 在資料夾中顯示')
        for b in (self.b_all, self.b_sel, self.b_dir): rb.addWidget(b)
        rb.addStretch(1)
        self.b_all.clicked.connect(lambda: self.go(True)); self.b_sel.clicked.connect(lambda: self.go(False))
        self.b_dir.clicked.connect(lambda: [show_in_folder(self.rows[i]['path']) for i in sorted({x.row() for x in self.tb.selectedIndexes()})[:1]])
        self.tm = QTimer(self); self.tm.timeout.connect(self._tick); self.tm.start(1500)

    DESC = {'edir': '裡面整串都沒有檔案的資料夾（只列最上層那個）。', 'efile': '大小是 0 的檔案，通常是複製失敗或救援留下的空殼。',
            'temp': 'Thumbs.db、.DS_Store、desktop.ini、~$ 開頭的 Office 暫存、._ 開頭的 Mac 檔、沒下載完的 .crdownload／.part…',
            'big': '整個硬碟最大的 300 個檔（不含遊戲／軟體資料夾）：看看有沒有不需要的。這一類要自己選（可以按住 Ctrl 多選）。'}

    def showEvent(self, e): super().showEvent(e); self.pick(self.kind)

    def pick(self, k):
        self.kind = k
        for kk, b in self.kbtn.items(): b.setChecked(kk == k)
        self.desc.setText(self.DESC.get(k, '')); self.b_all.setVisible(k != 'big')
        bg(lambda: ENG.junk_view(k, 3000), self._got)

    def _got(self, V):
        if not V.get('ok'): self.st.setText(V.get('message', '')); self.tb.setRowCount(0); self.rows = []; return
        C = V.get('counts') or {}
        for k, ic, nm in ana.JUNK_KINDS:
            n, b = C.get(k) or [0, 0]; self.kbtn[k].setText(f'{ic} {nm}（{n:,}・{fmt_b(b)}）')
        self.rows = V.get('rows') or []; self.tb.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            for j, val in enumerate((r['path'], fmt_b(r['b']) if r['b'] else '0', fmt_day(r['mt'])[:10])): self.tb.setItem(i, j, _ti(val, val))
        self._st(V.get('st') or {}, V.get('t'))

    def _st(self, M, t=None):
        if M.get('run'): self.st.setText(f"<span style='color:#4dc9ff'>🧹 搬到隔離區中：{M.get('n', 0):,}／{M.get('total', 0):,}</span>")
        else: self.st.setText(('✔ ' + esc_html(M['msg'])) if M.get('msg') else (f'資料來自 {fmt_day(t)} 的資料分析' if t else ''))
        self.st.setTextFormat(Qt.RichText)

    def _tick(self):
        if not self.isVisible(): return
        M = ENG.junk_st
        if M.get('run') or getattr(self, '_was', False):
            self._was = bool(M.get('run')); self._st(M)
            if not M.get('run'): self.pick(self.kind)

    def go(self, every):
        ids = [] if every else [self.rows[i]['id'] for i in sorted({x.row() for x in self.tb.selectedIndexes()}) if i < len(self.rows)]
        if not every and not ids: self.win.msg('先選要搬的（可以按住 Ctrl／Shift 多選）'); return
        what = '這一類全部' if every else f'選取的 {len(ids)} 個'
        if QMessageBox.question(self, '搬到隔離區', f'把{what}搬到隔離區？\n\n不會刪檔，在「📦 隔離區」可以復原。') != QMessageBox.Yes: return
        r = ENG.junk_quar(self.kind, ids); self.win.msg(r.get('message', '')); self._was = True


# ============================================================ 🖼 相似照片（V0.1.24）
class SimPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.off = 0; self.G = []; self.rows = []
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('🖼 相似照片／🎬 相似影片'); t.setObjectName('title'); r.addWidget(t)
        self.st = QLabel(''); self.st.setObjectName('muted'); self.st.setWordWrap(True); r.addWidget(self.st, 1)
        v.addWidget(note('不是一模一樣、但幾乎一樣的照片（改過大小、重新壓縮、連拍）。⭐＝建議保留（解析度最高 → 檔案最大 → 跟重複檔一樣的規則），其他搬到隔離區、可以復原。一模一樣的請用「🔁 重複檔」。'))
        r2 = QHBoxLayout(); v.addLayout(r2); self.lv = QComboBox()
        self.kc = QComboBox(); self.kc.addItem('🖼 照片', 'photo'); self.kc.addItem('🎬 影片（用分類預覽的 16 格比內容＋長度）', 'video'); self.kc.addItem('📸 連拍（挑最清楚的）', 'burst'); r2.addWidget(self.kc)
        self.kc.currentIndexChanged.connect(lambda _i: (setattr(self, 'off', 0), self.load()))
        for k, n in simi.LEVELS.items(): self.lv.addItem(n, k)
        self.lv.setCurrentIndex(max(0, self.lv.findData(int(ENG.cfg.get('sim_level') or 3))))
        b_go = QPushButton('🔍 開始找'); b_go.setObjectName('start'); self.b_all = QPushButton('⭐ 全部照建議處理')
        self.b_prev = QPushButton('‹ 上一頁'); self.b_next = QPushButton('下一頁 ›'); self.pg = QLabel('')
        for w_ in (QLabel('多像才算：'), self.lv, b_go, self.b_all): r2.addWidget(w_)
        r2.addStretch(1)
        for w_ in (self.b_prev, self.pg, self.b_next): r2.addWidget(w_)
        self.tb = QTableWidget(0, 7); self.tb.setHorizontalHeaderLabels(['組', '', '差', '解析度', '大小', '日期', '位置']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        for i, w in enumerate((50, 50, 40, 100, 90, 100)): self.tb.setColumnWidth(i, w)
        v.addWidget(self.tb, 1); self.tb.cellDoubleClicked.connect(lambda r_, _c: 0 <= r_ < len(self.rows) and open_file(self.rows[r_]['path']))
        r3 = QHBoxLayout(); v.addLayout(r3)
        b1 = QPushButton('📦 選取的那一組：留 ⭐、其他搬到隔離區'); b2 = QPushButton('📦 只搬選取的這張'); b3 = QPushButton('不是相似（以後不放一起）'); b4 = QPushButton('📂 在資料夾中顯示')
        for b in (b1, b2, b3, b4): r3.addWidget(b)
        r3.addStretch(1)
        b_go.clicked.connect(lambda: (self.win.msg(self.S.start(self.lv.currentData())['message']), self._tick()))
        self.b_all.clicked.connect(self.all_); b1.clicked.connect(lambda: self.act('grp')); b2.clicked.connect(lambda: self.act('one')); b3.clicked.connect(lambda: self.act('skip'))
        b4.clicked.connect(lambda: (r_ := self.cur()) and show_in_folder(r_['path']))
        self.b_prev.clicked.connect(lambda: self.page(-1)); self.b_next.clicked.connect(lambda: self.page(1))
        self.tm = QTimer(self); self.tm.timeout.connect(self._tick); self.tm.start(1500)

    @property
    def S(self): return {'video': ENG.simv, 'burst': ENG.burst}.get(self.kc.currentData(), ENG.sim)

    def showEvent(self, e): super().showEvent(e); self.load()

    def page(self, d): self.off = max(0, self.off + 30 * d); self.load()

    def load(self): bg(lambda: self.S.groups(self.off, 30), self._got)

    def _got(self, V):
        self.V = V; self.rows = []
        for g in V.get('groups') or []:
            for f in g['files']: self.rows.append(dict(f, gid=g['gid']))
        self.tb.setRowCount(len(self.rows)); last = None
        for i, f in enumerate(self.rows):
            vals = (str(f['gid']) if f['gid'] != last else '', '⭐ 留' if f['keep'] else '', '' if f['keep'] else str(f['dist']), f"{f['w']}×{f['h']}" if f.get('w') else '', fmt_b(f['size']),
                    fmt_day(f.get('taken') or f.get('mtime'))[:10], f['path'])
            for j, val in enumerate(vals): self.tb.setItem(i, j, _ti(val, val, None, '#45d483' if f['keep'] and j == 1 else None))
            last = f['gid']
        n = V.get('n') or 0; self.pg.setText(f'{self.off + 1 if n else 0}～{min(self.off + 30, n)}／{n:,} 組')
        self.b_prev.setEnabled(self.off > 0); self.b_next.setEnabled(self.off + 30 < n); self.b_all.setEnabled(n > 0); self._st()

    def _st(self):
        S = self.S.st; I = self.S.info()
        if S.get('run'): self.st.setText(f"<span style='color:#4dc9ff'>{self.S.NAME} {esc_html(S.get('phase', ''))} {round(100 * S.get('n', 0) / max(1, S.get('total', 1)))}%</span>")
        elif I.get('t'): self.st.setText(f"上次找：{fmt_day(I['t'])}・{I.get('groups', 0):,} 組、{I.get('files', 0):,} {self.S.UNIT}（比了 {I.get('photos', 0):,} {self.S.UNIT}）" + (f"・還有 {I['no_grid']:,} 部沒有 16 格預覽、沒比" if I.get('no_grid') else '') + (f"　✔ {esc_html(S['msg'])}" if S.get('msg') else ''))
        else: self.st.setText('還沒找過：按「🔍 開始找」')
        self.st.setTextFormat(Qt.RichText)

    def _tick(self):
        if not self.isVisible(): return
        run = self.S.st.get('run')
        if run or getattr(self, '_was', False):
            self._was = bool(run); self._st()
            if not run: self.load()

    def cur(self):
        i = self.tb.currentRow(); return self.rows[i] if 0 <= i < len(self.rows) else None

    def act(self, k):
        f = self.cur()
        if not f: self.win.msg('先選一張（或那一組的任何一列）'); return
        if k == 'one' and f['keep']: self.win.msg('⭐ 是建議保留的那張'); return
        r = self.S.quar(f['gid']) if k == 'grp' else (self.S.quar(fids=[f['id']]) if k == 'one' else self.S.not_similar(f['gid']))
        self.win.msg(r.get('message', '')); self.load()

    def all_(self):
        n = (self.V or {}).get('n') or 0
        if QMessageBox.question(self, '全部照建議處理', f'全部 {n:,} 組都照建議處理？\n\n每組留 ⭐，其他搬到隔離區（可以復原）。建議先看幾組確定沒問題。') != QMessageBox.Yes: return
        self.win.msg(self.S.quar_all()['message']); self._was = True


# ============================================================ 📅 依日期整理（V0.1.25）
class RenDlg(QDialog):
    """📝 依拍攝日期改檔名（V0.1.39）：留在原資料夾、只改名字；同一個背景工作、可以復原."""
    def __init__(self, page):
        super().__init__(page); self.page = page; self.setWindowTitle('📝 依拍攝日期改檔名'); self.resize(760, 560); v = QVBoxLayout(self)
        v.addWidget(note('把檔名改成拍攝日期時間（只用可靠的日期），檔案留在原本的資料夾。同一秒的連拍會加 _2、_3；檔名只有日期的，會變成「日期 原檔名」。'))
        f = QFormLayout(); v.addLayout(f)
        self.src = QLineEdit(); self.src.setPlaceholderText('空的＝全部要整理的資料夾'); f.addRow('要改哪裡', self.src)
        self.fmt = QComboBox()
        for k, (eg, _f) in ENG.org.RN.items(): self.fmt.addItem(eg, k)
        f.addRow('名字長這樣', self.fmt)
        self.kind = QComboBox(); self.kind.addItem('只有照片', 'photo'); self.kind.addItem('照片＋影片', 'both'); self.kind.addItem('只有影片', 'video'); f.addRow('改什麼', self.kind)
        self.keep = QCheckBox('後面保留原本的檔名'); f.addRow(self.keep)
        v.addWidget(note('影片改名後，SortCut 的預覽要用大小重新對應（分類頁可能要重做 16 格），所以預設只改照片。'))
        self.out = QLabel(''); self.out.setWordWrap(True); self.out.setTextFormat(Qt.RichText); v.addWidget(self.out, 1)
        r = QHBoxLayout(); v.addLayout(r); bp = QPushButton('👀 預覽'); self.br = QPushButton('📝 開始改名'); self.br.setObjectName('start'); self.br.setEnabled(False)
        for b in (bp, self.br): r.addWidget(b)
        r.addStretch(1); bp.clicked.connect(self.plan); self.br.clicked.connect(self.run)

    def plan(self):
        r = ENG.org.plan_rename(self.src.text(), self.fmt.currentData(), self.keep.isChecked(), self.kind.currentData())
        if not r.get('ok'): self.out.setText(esc_html(r.get('message', ''))); self.br.setEnabled(False); return
        self.out.setText(f"<b>會改 {r['n']:,} 個</b>　跳過：" + '、'.join(f'{k} {v:,}' for k, v in r['skip'].items() if v) + '<br>'
                         + '<br>'.join(f"<span style='color:#8994a4'>{esc_html(os.path.basename(x['src']))}</span> → <b>{esc_html(os.path.basename(x['dst']))}</b>" for x in r['sample'][:14]))
        self.br.setEnabled(r['n'] > 0)

    def run(self):
        if QMessageBox.question(self, '改檔名', '開始改檔名？\n\n每一筆都記下來，可以在「📦 隔離區」復原。') != QMessageBox.Yes: return
        self.page.win.msg(ENG.org.run()['message']); self.accept()


class OsrcDlg(QDialog):
    """🏷 依來源整理（V0.1.37）：勾來源 → 預覽 → 開始（跟依日期整理共用背景工作、可以在隔離區復原）."""
    def __init__(self, page):
        super().__init__(page); self.page = page; self.setWindowTitle('🏷 依來源整理'); self.resize(760, 560); v = QVBoxLayout(self)
        v.addWidget(note('照「從哪裡來的」分開放：截圖、抖音、LINE／微信、修圖過的、救援軟體救回的…各放一個資料夾。放到每顆硬碟的 \\照片影片_依來源\\來源\\原本的資料夾名；同一顆硬碟搬、可以復原。'))
        self.lw = QListWidget(); v.addWidget(self.lw, 1)
        for r in ENG.org.sources()['rows']:
            it = QListWidgetItem(f"{r['name']}　照片 {r['photo']:,}・影片 {r['video']:,}・{fmt_b(r['b'])}"); it.setData(Qt.UserRole, r['src'])
            if r['src'] and r['src'] != 'camera': it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Checked if r['src'] == 'screenshot' else Qt.Unchecked)
            else: it.setFlags(it.flags() & ~Qt.ItemIsEnabled)
            self.lw.addItem(it)
        self.kd = QCheckBox('保留原本的資料夾名（關掉＝同一個來源全部放一起）'); self.kd.setChecked(True); v.addWidget(self.kd)
        self.out = QLabel(''); self.out.setWordWrap(True); self.out.setTextFormat(Qt.RichText); v.addWidget(self.out)
        r = QHBoxLayout(); v.addLayout(r); bp = QPushButton('👀 預覽'); self.br = QPushButton('🏷 開始整理'); self.br.setObjectName('start'); self.br.setEnabled(False)
        for b in (bp, self.br): r.addWidget(b)
        r.addStretch(1); bp.clicked.connect(self.plan); self.br.clicked.connect(self.run)

    def plan(self):
        S = [self.lw.item(i).data(Qt.UserRole) for i in range(self.lw.count()) if self.lw.item(i).flags() & Qt.ItemIsUserCheckable and self.lw.item(i).checkState() == Qt.Checked]
        r = ENG.org.plan_src(S, '', self.kd.isChecked())
        if not r.get('ok'): self.out.setText(esc_html(r.get('message', ''))); self.br.setEnabled(False); return
        self.out.setText(f"<b>會搬 {r['n']:,} 個（{fmt_b(r['b'])}）</b> → {esc_html(r['dest_eg'])}<br>" + '・'.join(f'{esc_html(k)} {v[0]:,} 個' for k, v in r['months'])
                         + '<br>' + '<br>'.join(f"<span style='color:#8994a4'>{esc_html(x['src'])}</span> → {esc_html(x['dst'])}" for x in r['sample'][:8]))
        self.br.setEnabled(r['n'] > 0)

    def run(self):
        if QMessageBox.question(self, '依來源整理', '開始依來源整理？\n\n只在同一顆硬碟裡搬（瞬間完成），可以在「📦 隔離區」復原。') != QMessageBox.Yes: return
        self.page.win.msg(ENG.org.run()['message']); self.accept()


class OrgPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('📅 依日期整理'); t.setObjectName('title'); r.addWidget(t)
        self.st = QLabel(''); self.st.setObjectName('muted'); r.addWidget(self.st, 1)
        b_src = QPushButton('🏷 改成依來源整理…'); b_src.setToolTip('截圖、抖音、LINE、修圖、救援的…各放一個資料夾'); r.addWidget(b_src); b_src.clicked.connect(lambda: OsrcDlg(self).exec())
        b_ren = QPushButton('📝 依日期改檔名…'); r.addWidget(b_ren); b_ren.clicked.connect(lambda: RenDlg(self).exec())
        b_mt = QPushButton('🕒 修正修改日期…'); r.addWidget(b_mt); b_mt.clicked.connect(self.mtfix)
        v.addWidget(note('把照片／影片照拍攝日期搬進「年／月」資料夾。先按「👀 預覽」（不動任何檔），確定再按「📅 開始整理」。只在同一顆硬碟搬（瞬間完成），搬錯了在「📦 隔離區」→ 搬移紀錄可以復原。'))
        f = QFormLayout(); v.addLayout(f)
        self.src = QLineEdit(); self.src.setPlaceholderText('空的＝全部要整理的資料夾'); b1 = QPushButton('…'); b1.setFixedWidth(30); h1 = QHBoxLayout(); h1.addWidget(self.src, 1); h1.addWidget(b1)
        self.dest = QLineEdit(); self.dest.setPlaceholderText('空的＝每顆硬碟的 \\照片影片_依日期'); b2 = QPushButton('…'); b2.setFixedWidth(30); h2 = QHBoxLayout(); h2.addWidget(self.dest, 1); h2.addWidget(b2)
        self.pat = QComboBox()
        for k, (n, _f) in org.PATTERNS.items(): self.pat.addItem(n, k)
        self.kind = QComboBox()
        for k, n in (('both', '照片＋影片'), ('photo', '只有照片'), ('video', '只有影片')): self.kind.addItem(n, k)
        self.mt = QCheckBox('沒有拍攝日期的，用「修改日期」（常常是複製、傳輸的時間，不一定準）'); self.unk = QCheckBox('日期不明的放進「日期不明」資料夾（不勾＝留在原地）')
        f.addRow('要整理哪裡', h1); f.addRow('整理到哪', h2); f.addRow('資料夾怎麼分', self.pat); f.addRow('整理什麼', self.kind); f.addRow('', self.mt); f.addRow('', self.unk)
        self.cam = QCheckBox('📷 只整理自己拍的（截圖、下載、LINE、抖音…都不動）'); f.addRow('', self.cam)
        b1.clicked.connect(lambda: (d := pick_folder(self, '要整理哪個資料夾')) and self.src.setText(os.path.normpath(d)))
        b2.clicked.connect(lambda: (d := pick_folder(self, '整理到哪個資料夾（要同一顆硬碟）')) and self.dest.setText(os.path.normpath(d)))
        rb = QHBoxLayout(); v.addLayout(rb); bp = QPushButton('👀 預覽（不會動任何檔）'); self.b_run = QPushButton('📅 開始整理'); self.b_run.setObjectName('start'); self.b_run.setEnabled(False)
        rb.addWidget(bp); rb.addWidget(self.b_run); rb.addStretch(1)
        self.info = QLabel(''); self.info.setWordWrap(True); self.info.setTextFormat(Qt.RichText); v.addWidget(self.info)
        self.tb = QTableWidget(0, 2); self.tb.setHorizontalHeaderLabels(['原本', '搬到']); self.tb.verticalHeader().setVisible(False); self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch); self.tb.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch); v.addWidget(self.tb, 1)
        bp.clicked.connect(self.plan); self.b_run.clicked.connect(self.run)
        self.tm = QTimer(self); self.tm.timeout.connect(self._tick); self.tm.start(1500)

    def mtfix(self):
        p = ENG.mtf.plan()
        if p['undo'] and QMessageBox.question(self, '修正修改日期', f"已經修正過 {p['undo']:,} 個。\n\n要「全部改回去」嗎？（選「否」繼續看要不要修正）") == QMessageBox.Yes:
            self.win.msg(ENG.mtf.undo()['message']); return
        if not p['n']: self.win.msg('沒有要修正的（修改日期都跟拍攝日期差不多）'); return
        eg = '\n'.join(f"{os.path.basename(x['path'])}：{fmt_day(x['old'])[:10]} → {fmt_day(x['new'])[:10]}" for x in p['sample'][:6])
        if QMessageBox.question(self, '修正修改日期', f"{p['n']:,} 個照片影片的修改日期跟拍攝日期差超過 1 天，例如：\n{eg}\n\n改成拍攝日期？（只改日期屬性、不動內容，可以全部改回去）") != QMessageBox.Yes: return
        self.win.msg(ENG.mtf.start()['message'])

    def plan(self):
        a = (self.src.text().strip(), self.dest.text().strip(), self.pat.currentData(), self.kind.currentData(), self.mt.isChecked(), 'move' if self.unk.isChecked() else 'skip', self.cam.isChecked())
        self.info.setText('預覽中…'); self.b_run.setEnabled(False); bg(lambda: ENG.org.plan(*a), self._got)

    def _got(self, r):
        if not r.get('ok'): self.info.setText(esc_html(r.get('message', '失敗'))); return
        sk = '、'.join(f'{k} {v:,}' for k, v in r['skip'].items() if v) or '沒有'
        mon = '　'.join(f'{k}：{v[0]:,}' for k, v in r['months'][:40]) + ('…' if len(r['months']) > 40 else '')
        self.info.setText(f"<b>會搬 {r['n']:,} 個（{fmt_b(r['b'])}）</b>　整理到：{esc_html(r.get('dest_eg') or '')}\\{esc_html(r['pattern'])}<br>跳過：{esc_html(sk)}<br><span style='color:#8994a4'>{esc_html(mon)}</span>")
        self.tb.setRowCount(len(r['sample']))
        for i, x in enumerate(r['sample']): self.tb.setItem(i, 0, _ti(x['src'])); self.tb.setItem(i, 1, _ti(x['dst']))
        self.b_run.setEnabled(r['n'] > 0); self.b_run.setText(f"📅 開始整理（{r['n']:,} 個）")

    def run(self):
        if QMessageBox.question(self, '依日期整理', '開始整理？\n\n只在同一顆硬碟裡搬（瞬間完成），可以在「📦 隔離區」復原。') != QMessageBox.Yes: return
        r = ENG.org.run(); self.win.msg(r['message']); self.b_run.setEnabled(False); self._was = True

    def _tick(self):
        if not self.isVisible(): return
        S = ENG.org.st
        if S.get('run'): self.st.setText(f"📅 整理中：{S.get('n', 0):,}／{S.get('total', 0):,}")
        elif S.get('msg'): self.st.setText('✔ ' + S['msg'])


# ============================================================ 🗓 時間軸＋那年今天（V0.1.26）
class TlPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.rows = []; self.ym = None; self.off = 0
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('🗓 時間軸'); t.setObjectName('title'); r.addWidget(t)
        self.otd = QLabel(''); self.otd.setObjectName('muted'); r.addWidget(self.otd, 1)
        v.addWidget(note('只用可靠的拍攝日期（EXIF／影片內建／檔名）。左邊選年月，右邊是那個月的照片影片；雙擊打開。上面「那年今天」：今天的日期往年拍的。'))
        h = QHBoxLayout(); v.addLayout(h, 1)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(['年／月', '個數']); self.tree.setColumnWidth(0, 120); self.tree.setFixedWidth(230); h.addWidget(self.tree)
        right = QVBoxLayout(); h.addLayout(right, 1)
        self.title = QLabel(''); self.title.setObjectName('title'); right.addWidget(self.title)
        self.grid = QListWidget(); self.grid.setViewMode(QListView.IconMode); self.grid.setIconSize(QSize(150, 150)); self.grid.setResizeMode(QListView.Adjust)
        self.grid.setUniformItemSizes(True); self.grid.setSpacing(4); self.grid.setMovement(QListView.Static); right.addWidget(self.grid, 1)
        self.more = QPushButton('再載入 120 個'); right.addWidget(self.more); self.more.hide()
        self.tree.itemClicked.connect(self._pick); self.grid.itemDoubleClicked.connect(lambda it: open_file(it.data(Qt.UserRole)))
        self.more.clicked.connect(lambda: self._load(True)); self._first = True

    def showEvent(self, e):
        super().showEvent(e)
        if self._first: self._first = False; bg(ENG.tl.years, self._got_years); bg(ENG.tl.on_this_day, self._got_otd)

    def _got_otd(self, o):
        self.otd.setText(('🗓 那年今天：' + '、'.join(f"{y['ago']} 年前（{y['y']}）{y['n']} 個" for y in o['years'][:6]) + '　→ 左邊點那一年的這個月看') if o.get('n') else '🗓 那年今天：往年的今天沒有拍東西')

    def _got_years(self, Y):
        self.tree.clear()
        for y in sorted(Y, reverse=True):
            M = Y[y]; it = QTreeWidgetItem([y, f"{sum(m['photo'] + m['video'] for m in M.values()):,}"]); self.tree.addTopLevelItem(it)
            for m in sorted(M):
                c = QTreeWidgetItem([f'{y}-{m}', f"{M[m]['photo'] + M[m]['video']:,}"]); c.setData(0, Qt.UserRole, (y, m)); it.addChild(c)
        if self.tree.topLevelItemCount(): self.tree.topLevelItem(0).setExpanded(True)

    def _pick(self, it, _c=0):
        d = it.data(0, Qt.UserRole)
        if not d: it.setExpanded(not it.isExpanded()); return
        self.ym = d; self.off = 0; self.grid.clear(); self._load(False)

    def _load(self, more):
        if more: self.off += 120
        y, m = self.ym; bg(lambda: ENG.tl.month(y, m, self.off, 120), self._got)

    def _got(self, r):
        self.title.setText(f"{r['y']} 年 {r['m']} 月・{r['n']:,} 個"); self.more.setVisible(self.off + 120 < r['n'])
        for f in r['rows']:
            it = QListWidgetItem(('🎞 ' if f['kind'] == 'video' else '') + fmt_day(f['taken'])[5:10]); it.setData(Qt.UserRole, f['path']); it.setToolTip(f['path']); it.setSizeHint(QSize(160, 180)); self.grid.addItem(it)
            bg(lambda fid=f['id']: ENG.fc_thumb(fid, 320), lambda p, it=it: p and it.setIcon(QIcon(QPixmap(p))))


# ============================================================ 🗺 照片地圖（V0.1.30）：電腦版是「去過的地方」清單＋照片；大地圖在手機（或瀏覽器打開手機版）
class GeoPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.P = []; self.sel = None; self.off = 0
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('🗺 照片地圖'); t.setObjectName('title'); r.addWidget(t)
        self.st = QLabel(''); self.st.setObjectName('muted'); r.addWidget(self.st, 1)
        self.zc = QComboBox()
        for z, nm in ((6, '大範圍（約 300 公里一區）'), (9, '城市（約 40 公里）'), (12, '鄉鎮（約 5 公里）'), (15, '附近（約 600 公尺）')): self.zc.addItem(nm, z)
        self.zc.setCurrentIndex(1); r.addWidget(self.zc); b_r = QPushButton('🔄'); r.addWidget(b_r);
        v.addWidget(note('有 GPS 的照片影片照位置分區，照「拍了幾個」排。點一區看那裡拍的（雙擊打開）；「🌐 Google 地圖」看那裡是哪裡。可以拖曳縮放的大地圖在手機「工具 → 🗺 照片地圖」。'))
        h = QHBoxLayout(); v.addLayout(h, 1)
        self.tb = QTableWidget(0, 3); self.tb.setHorizontalHeaderLabels(['個數', '時間', '位置']); self.tb.verticalHeader().setVisible(False); self.tb.setFixedWidth(420)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tb.setColumnWidth(0, 60); self.tb.setColumnWidth(1, 170); self.tb.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch); h.addWidget(self.tb)
        right = QVBoxLayout(); h.addLayout(right, 1)
        rr = QHBoxLayout(); right.addLayout(rr); self.title = QLabel(''); self.title.setObjectName('title'); rr.addWidget(self.title, 1)
        b_g = QPushButton('🌐 Google 地圖'); rr.addWidget(b_g)
        self.grid = QListWidget(); self.grid.setViewMode(QListView.IconMode); self.grid.setIconSize(QSize(150, 150)); self.grid.setResizeMode(QListView.Adjust)
        self.grid.setUniformItemSizes(True); self.grid.setSpacing(4); self.grid.setMovement(QListView.Static); right.addWidget(self.grid, 1)
        self.more = QPushButton('再載入 120 個'); right.addWidget(self.more); self.more.hide()
        self.tb.itemSelectionChanged.connect(self._pick); self.grid.itemDoubleClicked.connect(lambda it: open_file(it.data(Qt.UserRole)))
        self.more.clicked.connect(lambda: self._load(True)); b_r.clicked.connect(self.load); self.zc.currentIndexChanged.connect(lambda _i: self.load())
        b_g.clicked.connect(lambda: self.sel and QDesktopServices.openUrl(QUrl(f"https://www.google.com/maps?q={self.sel['lat']},{self.sel['lon']}")))
        self._first = True

    def showEvent(self, e):
        super().showEvent(e)
        if self._first: self._first = False; self.load()

    def load(self):
        z = self.zc.currentData() or 9; ENG.geo.c.clear()
        bg(lambda: (ENG.geo.summary(), ENG.geo.places(z, 300)), self._got)

    def _got(self, r):
        S, P = r; self.P = P; self.tb.setRowCount(0)
        self.st.setText(f"　📍 {S['n']:,} 個有位置（照片 {S['photo']:,}・影片 {S['video']:,}，全部的 {round(100 * S['n'] / S['all']) if S['all'] else 0}%）" if S['n'] else '　還沒有找到有 GPS 的照片影片（要先讀取拍攝資訊；手機拍照要開定位）')
        for p in P:
            i = self.tb.rowCount(); self.tb.insertRow(i)
            d = fmt_day(p['t0'])[:10] + ('' if fmt_day(p['t1'])[:10] == fmt_day(p['t0'])[:10] else ' ～ ' + fmt_day(p['t1'])[:10]) if p['t0'] else ''
            for c, x in enumerate((f"{p['n']:,}", d, f"{p['lat']:.3f}, {p['lon']:.3f}")): self.tb.setItem(i, c, QTableWidgetItem(x))

    def _pick(self):
        rs = self.tb.selectionModel().selectedRows()
        if not rs: return
        self.sel = self.P[rs[0].row()]; self.off = 0; self.grid.clear(); self._load(False)

    def _load(self, more):
        if more: self.off += 120
        z = self.zc.currentData() or 9; p = self.sel; bg(lambda: ENG.geo.cell(z, p['gy'], p['gx'], self.off, 120), self._show)

    def _show(self, r):
        self.title.setText(f"📍 這附近 {r['n']:,} 個"); self.more.setVisible(self.off + 120 < r['n'])
        for f in r['rows']:
            it = QListWidgetItem(('🎞 ' if f['kind'] == 'video' else '') + fmt_day(f['taken'])[:10]); it.setData(Qt.UserRole, f['path']); it.setToolTip(f['path']); it.setSizeHint(QSize(160, 180)); self.grid.addItem(it)
            bg(lambda fid=f['id']: ENG.fc_thumb(fid, 320), lambda p, it=it: p and it.setIcon(QIcon(QPixmap(p))))


# ============================================================ 🗜 影片瘦身（V0.1.34；V0.4.62 改成 VS 的 🎯 畫質目標：選片／轉好的，跟手機頁一樣）
class SlimPage(QWidget):
    WHICH = (('tagged', '已分類的（不含 Delete）'), ('moved', '已經搬進分類資料夾的'), ('wait', '分好、還沒搬的'), ('untagged', '還沒分類的'), ('all', '全部'))

    def __init__(self, win):
        super().__init__(); self.win = win; self.R = []; self.D = []
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('🗜 影片瘦身'); t.setObjectName('title'); r.addWidget(t)
        self.st = QLabel(''); self.st.setObjectName('muted'); self.st.setWordWrap(True); r.addWidget(self.st, 1)
        v.addWidget(note('🎯 跟 VS 一樣的「畫質目標」：每一部先從片長 10%～90% 取 5 段各 2 秒，試不同畫質（CQ 18～40），跟原檔同一段比 SSIM，'
                         '找「中間值 ≥ 目標（預設 0.985）」裡最省的設定再整部轉；轉完抽 3 段，低於底線（預設 0.975）就調高畫質重轉（最多 2 次），還是不到 → 不用轉好的、原檔不動。'
                         '新檔叫「原檔名_h265.mp4」，原檔搬到「🗜 轉檔後隔離區」（可以復原，不會刪）。'))
        self.tst = QLabel(''); self.tst.setWordWrap(True); self.tst.setTextFormat(Qt.RichText); v.addWidget(self.tst)
        r0 = QHBoxLayout(); v.addLayout(r0); self.b_pick = QPushButton('🎞 選片'); self.b_done = QPushButton('✅ 轉好的')
        for b_ in (self.b_pick, self.b_done): b_.setCheckable(True); r0.addWidget(b_)
        r0.addStretch(1); self.q = QComboBox(); self.b_tgt = QPushButton(''); self.b_flr = QPushButton('')
        for k, (n, _a, _b) in vslim.QUAL.items(): self.q.addItem(n, k)
        self.q.setCurrentIndex(max(0, self.q.findData(ENG.cfg.get('slim_q') or 'auto')))
        for w_ in (QLabel('方式'), self.q, self.b_tgt, self.b_flr): r0.addWidget(w_)
        self.stk = QStackedWidget(); v.addWidget(self.stk, 1)
        # --- 🎞 選片
        P = QWidget(); pv = QVBoxLayout(P); pv.setContentsMargins(0, 0, 0, 0)
        r2 = QHBoxLayout(); pv.addLayout(r2); self.mb = QComboBox(); self.w = QComboBox()
        for m in (100, 200, 500, 1000, 2000): self.mb.addItem(f'只列大於 {m // 1000} GB' if m >= 1000 else f'只列大於 {m} MB', m)
        self.mb.setCurrentIndex(1)
        for k, n in self.WHICH: self.w.addItem(n, k)
        b_go = QPushButton('🗜 瘦身選取的'); b_go.setObjectName('start'); b_t = QPushButton('🧪 試轉選取的那部'); self.b_stop = QPushButton('⏹ 停止'); b_r = QPushButton('🔄')
        for w_ in (self.mb, self.w, b_go, b_t, self.b_stop, b_r): r2.addWidget(w_)
        r2.addStretch(1); self.sum = QLabel(''); r2.addWidget(self.sum)
        self.tb = QTableWidget(0, 6); self.tb.setHorizontalHeaderLabels(['大小', '預估省', '長度', '解析度／編碼', 'Mbps', '位置']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        for i, w in enumerate((90, 90, 70, 150, 60)): self.tb.setColumnWidth(i, w)
        pv.addWidget(self.tb, 1); self.tb.cellDoubleClicked.connect(lambda r_, _c: 0 <= r_ < len(self.R) and open_file(self.R[r_]['path']))
        self.stk.addWidget(P)
        # --- ✅ 轉好的
        Dw = QWidget(); dv = QVBoxLayout(Dw); dv.setContentsMargins(0, 0, 0, 0)
        r3 = QHBoxLayout(); dv.addLayout(r3); self.df = QComboBox()
        for k, n in (('all', '全部'), ('warn', '⚠ 沒到目標'), ('unseen', '沒抽檢'), ('undone', '已還原')): self.df.addItem(n, k)
        b_pl = QPushButton('▶ 播放選取的（抽檢）'); b_rv = QPushButton('↩ 還原選取的'); self.dsum = QLabel(''); self.dsum.setTextFormat(Qt.RichText)
        for w_ in (self.df, b_pl, b_rv): r3.addWidget(w_)
        r3.addStretch(1); r3.addWidget(self.dsum)
        self.dt = QTableWidget(0, 7); self.dt.setHorizontalHeaderLabels(['SSIM', '原檔 → 新檔', '變成', 'CQ', '編碼器', '時間', '新檔']); self.dt.verticalHeader().setVisible(False)
        self.dt.setEditTriggers(QAbstractItemView.NoEditTriggers); self.dt.setSelectionBehavior(QAbstractItemView.SelectRows); self.dt.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        for i, w in enumerate((80, 170, 60, 50, 90, 130)): self.dt.setColumnWidth(i, w)
        dv.addWidget(self.dt, 1); self.dt.cellDoubleClicked.connect(lambda r_, _c: self.play([r_]))
        self.stk.addWidget(Dw)
        self.b_pick.clicked.connect(lambda: self.tab(0)); self.b_done.clicked.connect(lambda: self.tab(1))
        b_go.clicked.connect(self.go); b_t.clicked.connect(self.test); self.b_stop.clicked.connect(lambda: ENG.slim.st.update(cancel=True)); b_r.clicked.connect(self.load)
        b_pl.clicked.connect(lambda: self.play(sorted({x.row() for x in self.dt.selectedIndexes()}))); b_rv.clicked.connect(self.revert)
        self.b_tgt.clicked.connect(lambda: self.setc('target')); self.b_flr.clicked.connect(lambda: self.setc('floor'))
        self.mb.currentIndexChanged.connect(lambda _i: self.load()); self.w.currentIndexChanged.connect(lambda _i: self.load()); self.df.currentIndexChanged.connect(lambda _i: self.load())
        self.tm = QTimer(self); self.tm.timeout.connect(self._tick); self.tm.start(1500); self.tab(0, False)

    def tab(self, i, load=True):
        self.stk.setCurrentIndex(i); self.b_pick.setChecked(i == 0); self.b_done.setChecked(i == 1)
        if load: self.load()

    def showEvent(self, e): super().showEvent(e); self.load()

    def load(self):
        C = ENG.slim.cfg(); self.b_tgt.setText(f"目標 SSIM {C['target']}"); self.b_flr.setText(f"底線 {C['floor']}")
        if self.stk.currentIndex() == 1: bg(lambda: ENG.slim.done_list(self.df.currentData() or 'all'), self._gotd)
        else: bg(lambda: ENG.slim.candidates(self.mb.currentData() or 200, which=self.w.currentData() or 'tagged'), self._got)

    def _got(self, j):
        self.R = j.get('rows') or []; self.tb.setRowCount(len(self.R))
        for i, x in enumerate(self.R):
            vals = (fmt_b(x['size']), fmt_b(x['save']), fmt_t(x['dur']), f"{x['w']}×{x['h']} {x.get('vcodec') or ''}", f"{x['br'] / 1e6:.1f}", x['path'])
            for c, val in enumerate(vals): self.tb.setItem(i, c, _ti(val, val, None, '#45d483' if c == 1 else None))
        self.sum.setText(f"可以瘦身 {j.get('n', 0):,} 部（{fmt_b(j.get('bytes'))}），預估省 <b style='color:#45d483'>{fmt_b(j.get('save'))}</b>"); self.sum.setTextFormat(Qt.RichText); self._st()

    def _gotd(self, j):
        C = j.get('cfg') or ENG.slim.cfg(); self.D = j.get('rows') or []; self.dt.setRowCount(len(self.D))
        for i, x in enumerate(self.D):
            sc = x.get('score') or 0; col = '#45d483' if sc >= C['target'] - 1e-9 else ('#ff9f43' if sc >= C['floor'] else '#ff5c7a')
            vals = ((f"{sc:.3f}" + ('（抽查）' if x.get('spot') else '')) if sc else '—', f"{fmt_b(x['osz'])} → {fmt_b(x['nsz'])}", f"{x['nsz'] * 100 // max(1, x['osz'])}%", str(x.get('q') or ''),
                    x.get('enc') or '', fmt_day(x['t'])[:16], ('✔ ' if x.get('viewed') else '') + ('↩ ' if x.get('undone') else '') + (x.get('dst') or ''))
            for c, val in enumerate(vals): self.dt.setItem(i, c, _ti(val, x.get('note') or val, None, col if c == 0 and sc else None))
        self.dsum.setText(f"轉好 {j.get('n', 0):,} 部：{fmt_b(j.get('osz'))} → {fmt_b(j.get('nsz'))}，省 <b style='color:#45d483'>{fmt_b(max(0, (j.get('osz') or 0) - (j.get('nsz') or 0)))}</b>"
                          + (f"・<span style='color:#ff9f43'>⚠ {j['warn']} 部沒到目標</span>" if j.get('warn') else '') + f"・轉檔後隔離區還有 {j.get('qn', 0)} 個原檔")

    def _st(self):
        S = ENG.slim.st; T = ENG.slim.tst
        if S.get('run'):
            tr = '　'.join(f'CQ{k}＝{v:.3f}' for k, v in sorted((S.get('tried') or {}).items(), key=lambda x: int(x[0])))
            self.st.setText(f"🗜 {S.get('n')}／{S.get('total')}：{S.get('cur', '')}・{S.get('phase', '')} {S.get('pct', 0) if '轉' in (S.get('phase') or '') else ''}%・已省 {fmt_b(S.get('saved'))}" + (f'\n🎯 {tr}' if tr else ''))
        else: self.st.setText(('✔ ' + S['msg']) if S.get('msg') else '')
        self.b_stop.setEnabled(bool(S.get('run')))
        if T.get('run'): self.tst.setText(f"🧪 試轉 {T.get('name', '')}：{T.get('phase', '')}")
        elif T.get('res'):
            x = T['res']; self.tst.setText(f"🧪 試轉 {T.get('name', '')}：用 <b>CQ {x['q']}</b>，樣本 SSIM <b>{x['ssim']:.4f}</b>{' ✔' if x['ok'] else '（⚠ 沒到目標）'}，整部預估 <b>{fmt_b(x['pred'])}</b>"
                                  f"（原檔 {fmt_b(x['osz'])}，變成 {x['pred'] * 100 // max(1, x['osz'] or 1)}%）・找了 {x['sec']:.0f} 秒・" + '　'.join(f'CQ{k}＝{v:.3f}' for k, v in sorted(x['tried'].items(), key=lambda z: int(z[0])) if v is not None))
        elif T.get('err'): self.tst.setText(f"🧪 試轉 {T.get('name', '')}：{T['err']}")
        else: self.tst.setText('')

    def _tick(self):
        if not self.isVisible(): return
        run = ENG.slim.st.get('run'); self._st()
        if getattr(self, '_was', False) and not run: self.load()
        self._was = bool(run)

    def sel(self): return [self.R[i]['id'] for i in sorted({x.row() for x in self.tb.selectedIndexes()}) if i < len(self.R)]

    def test(self):
        ids = self.sel()
        if not ids: self.win.msg('先選一部要試轉的影片'); return
        self.win.msg(ENG.slim.test(ids[0])['message'])

    def setc(self, k):
        C = ENG.slim.cfg(); lab = '目標 SSIM（找「樣本中間值 ≥ 這個」最省的設定；VS 預設 0.985）' if k == 'target' else '底線 SSIM（轉完抽查低於這個就重轉；VS 預設 0.975）'
        v, ok = QInputDialog.getDouble(self, '影片瘦身', lab, C[k], 0.90, 0.995, 3)
        if ok: ENG.cfg.set('slim_' + k, float(v)); self.load()

    def play(self, rows):
        R = [self.D[i] for i in rows if 0 <= i < len(self.D)]
        for x in R[:3]:
            if x.get('dst') and os.path.exists(fcore.lp(x['dst'])): open_file(x['dst'])
        ENG.slim.seen([x['id'] for x in R]); self.load()

    def revert(self):
        R = [self.D[i] for i in sorted({x.row() for x in self.dt.selectedIndexes()}) if i < len(self.D)]
        if not R: self.win.msg('先選要還原的'); return
        if QMessageBox.question(self, '影片瘦身', f'還原 {len(R)} 部？\n\n• 原檔從「轉檔後隔離區」搬回原位\n• 轉好的 _h265 搬進轉檔後隔離區（不刪，可以再復原）\n• 分類跟回原檔') != QMessageBox.Yes: return
        bg(lambda: ENG.slim.revert([x['id'] for x in R]), lambda r: (self.win.msg(r.get('message', '')), self.load()))

    def go(self):
        ids = self.sel()
        if not ids: self.win.msg('先選要瘦身的影片（可以按住 Ctrl／Shift 多選）'); return
        sv = sum(x['save'] for x in self.R if x['id'] in ids); C = ENG.slim.cfg(); q = self.q.currentData()
        how = f"🎯 每部先用 5 段樣本找「SSIM ≥ {C['target']}」最省的設定，轉完抽查、低於 {C['floor']} 重轉" if q == 'auto' else '固定畫質'
        if QMessageBox.question(self, '影片瘦身', f'瘦身 {len(ids)} 部（預估省 {fmt_b(sv)}）？\n\n• {how}\n• 新檔：原檔名_h265.mp4（同一個資料夾）\n• 成功才把原檔搬到「轉檔後隔離區」（可以復原）\n• 很花電腦時間，可以隨時停') != QMessageBox.Yes: return
        self.win.msg(ENG.slim.start(ids, q)['message']); self._was = True


# ============================================================ 💾 備份檢查（V0.1.38）
class BakPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('💾 備份檢查'); t.setObjectName('title'); r.addWidget(t); r.addStretch(1)
        b_r = QPushButton('🔄 重新檢查'); r.addWidget(b_r); b_r.clicked.connect(lambda: self.load(True))
        v.addWidget(note('用比對重複的結果算（不用另外跑）：同一個檔（內容一模一樣）在別顆硬碟也有＝有備份。要檢查備份，記得把備份硬碟也加進「要整理的資料夾」。'))
        self.sum = QLabel('檢查中…'); self.sum.setTextFormat(Qt.RichText); self.sum.setWordWrap(True); v.addWidget(self.sum)
        self.tb = QTableWidget(0, 4); self.tb.setHorizontalHeaderLabels(['硬碟', '個數', '大小', '最需要備份的資料夾（只有一份＋只在同一顆）']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        for i, w in enumerate((90, 80, 90)): self.tb.setColumnWidth(i, w)
        v.addWidget(self.tb, 1); self.tb.cellDoubleClicked.connect(lambda r_, _c: open_file(self.tb.item(r_, 3).text()))
        self._first = True

    def showEvent(self, e):
        super().showEvent(e)
        if self._first: self._first = False; self.load()

    def load(self, force=False): self.sum.setText('檢查中…'); bg(lambda: ENG.bak.check(force), self._got)

    def _got(self, j):
        T = j['tot']; nm = (('one', '#ff4d6d', '✖ 只有一份（硬碟壞了就沒了）'), ('same', '#f0ad4e', '⚠ 只在同一顆硬碟有副本'), ('ok', '#45d483', '✔ 別顆硬碟也有'), ('wait', '#8994a4', '… 還沒比對完'))
        self.sum.setText('<br>'.join(f"<span style='color:{c}'>{n}</span>：<b>{T[k][0]:,}</b> 個、<b>{fmt_b(T[k][1])}</b>" for k, c, n in nm)
                         + ('' if j['ndrives'] > 1 else "<br><b style='color:#f0ad4e'>目前只整理了 1 顆硬碟。</b>")
                         + '<br>' + '　'.join(f"💽 {esc_html(d['drive'])}：只有一份 {fmt_b(d['one'][1])}" for d in j['drives']))
        self.tb.setRowCount(len(j['top']))
        for i, (d, p, n, b) in enumerate(j['top']):
            for c, val in enumerate((d, f'{n:,}', fmt_b(b), p)): self.tb.setItem(i, c, _ti(val, val))


# ============================================================ 🧳 活動（V0.1.48）
class EvtPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.R = []
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('🧳 活動'); t.setObjectName('title'); r.addWidget(t)
        self.gap = QComboBox(); self.mn = QComboBox()
        for h in (3, 6, 12, 24): self.gap.addItem(f'隔 {h} 小時算新的一次', h)
        for n in (5, 15, 30, 60): self.mn.addItem(f'至少 {n} 個', n)
        self.gap.setCurrentIndex(1); self.mn.setCurrentIndex(1); self.st = QLabel(''); self.st.setObjectName('muted')
        b_go = QPushButton('📁 選取的整理成一個資料夾…'); b_go.setObjectName('start')
        for w_ in (self.gap, self.mn, self.st): r.addWidget(w_)
        r.addStretch(1); r.addWidget(b_go)
        v.addWidget(note('照拍攝時間自動分段（只用可靠的拍攝日期）：出遊、聚會、生日…一次一列。雙擊打開那個活動最多的資料夾；選一列按右上可以整理成一個資料夾（先預覽、同一顆硬碟搬、可以復原）。'))
        self.tb = QTableWidget(0, 6); self.tb.setHorizontalHeaderLabels(['開始', '結束', '天', '照片／影片', '大小', '主要資料夾']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tb.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        for i, w in enumerate((140, 140, 40, 110, 90)): self.tb.setColumnWidth(i, w)
        v.addWidget(self.tb, 1); self.tb.cellDoubleClicked.connect(lambda r_, _c: 0 <= r_ < len(self.R) and open_file(self.R[r_]['dir']))
        self.gap.currentIndexChanged.connect(lambda _i: self.load()); self.mn.currentIndexChanged.connect(lambda _i: self.load()); b_go.clicked.connect(self.go)
        self._first = True

    def showEvent(self, e):
        super().showEvent(e)
        if self._first: self._first = False; self.load()

    def load(self):
        g, m = self.gap.currentData(), self.mn.currentData(); self.st.setText('讀取中…'); bg(lambda: ENG.evt.list(g, m), self._got)

    def _got(self, j):
        self.R = j['rows']; self.tb.setRowCount(len(self.R)); self.st.setText(f"{j['n']:,} 次活動")
        for i, e in enumerate(self.R):
            for c, val in enumerate((fmt_day(e['t0']), fmt_day(e['t1']), str(e['days']), f"{e['photo']:,}／{e['video']:,}", fmt_b(e['b']), e['dir'] + (f"（＋{e['ndirs'] - 1}）" if e['ndirs'] > 1 else ''))):
                self.tb.setItem(i, c, _ti(val, val))

    def go(self):
        i = self.tb.currentRow()
        if not 0 <= i < len(self.R): self.win.msg('先選一個活動'); return
        e = self.R[i]; label, ok = QInputDialog.getText(self, '整理成一個資料夾', '資料夾名稱要加什麼？（例如：墾丁、阿嬤生日；可以空白）')
        if not ok: return
        r = ENG.evt.plan(e['key'], label)
        if not r.get('ok') or not r['n']: self.win.msg(r.get('message') or '沒有要搬的'); return
        if QMessageBox.question(self, '整理成一個資料夾', f"會搬 {r['n']:,} 個（{fmt_b(r['b'])}）到\n{r['dest_eg']}\n\n同一顆硬碟搬、可以在隔離區復原。開始？") != QMessageBox.Yes: return
        ENG.evt.c.clear(); self.win.msg(ENG.org.run()['message'])


# ============================================================ 🧾 操作紀錄＋⭐ 最愛（V0.1.81，電腦版）
class OpsPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.off = 0
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('🧾 操作紀錄'); t.setObjectName('title'); r.addWidget(t)
        self.kind = QComboBox(); self.q = QLineEdit(); self.q.setPlaceholderText('找檔名、資料夾…'); self.st = QLabel(''); self.st.setObjectName('muted'); b_more = QPushButton('再看 300 筆')
        for w_ in (self.kind, self.q, b_more, self.st): r.addWidget(w_)
        r.addStretch(1)
        v.addWidget(note('程式做過的每一件事（搬到隔離區、整理、復原、分析、瘦身…）都記在這裡。'))
        self.tb = QTableWidget(0, 3); self.tb.setHorizontalHeaderLabels(['時間', '做什麼', '內容']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch); self.tb.setColumnWidth(0, 140); self.tb.setColumnWidth(1, 130)
        v.addWidget(self.tb, 1)
        self.kind.currentIndexChanged.connect(lambda _i: self.load()); self.q.editingFinished.connect(self.load); b_more.clicked.connect(lambda: self.load(True)); self._first = True

    def showEvent(self, e):
        super().showEvent(e)
        if self._first: self._first = False; self.load()

    def load(self, more=False):
        self.off = self.off + 300 if more else 0; k = self.kind.currentData() or ''; q = self.q.text().strip(); off = self.off
        bg(lambda: ENG.ops(k, q, off, 300), lambda j, more=more: self._got(j, more))

    def _got(self, j, more):
        if not more:
            cur = self.kind.currentData() or ''; self.kind.blockSignals(True); self.kind.clear(); self.kind.addItem(f"全部（{j['n']:,}）", '')
            for k, n in j['kinds']: self.kind.addItem(f'{k}（{n:,}）', k)
            self.kind.setCurrentIndex(max(0, self.kind.findData(cur))); self.kind.blockSignals(False); self.tb.setRowCount(0)
        for r in j['rows']:
            i = self.tb.rowCount(); self.tb.insertRow(i)
            for c, val in enumerate((fmt_day(r['t']), r['kind'], r['detail'])): self.tb.setItem(i, c, _ti(val, val, None, None if r['ok'] else '#ff4d6d'))
        self.st.setText(f"{self.tb.rowCount():,}／{j['n']:,} 筆")


class WizPage(QWidget):
    """🚀 整理精靈（V0.2.39）：建議的順序、每一步還剩多少、一鍵去做."""
    GO = {'home': 11, 'tool:dpl': 25, 'tool:dup': 2, 'tool:pk': 24, 'vc': 12}
    ACT = {'bad': ('📦 全部先隔離', '損毀的（打不開、部分損毀、0 位元組）全部先搬到隔離區？（不是刪除，可以復原）'),
           'dpl_all': ('⚡ 整包複本照建議', '「整包是複本」的資料夾對，全部保留 ⭐ 那邊、另一邊的複本搬到隔離區？（獨有的不動）'),
           'dup_all': ('⚡ 全部照建議', '剩下的重複檔，每組留建議的那份（分類過、整理過的優先），其他搬到隔離區？'),
           'vc_group': ('🧩 開始一組一組審', ''), 'move': ('🚚 搬', '分好的影片全部搬進分類資料夾？'), 'dpl_scan': ('🔍 先分析', ''),
           'pet_start': ('🐾 開始看', ''), 'pet_view': ('🐾 只看有貓狗的', ''), 'junk_view': ('🌑 只看誤錄的', ''), 'vc_sug': ('💡 只看有建議的', '')}

    def __init__(self, win):
        super().__init__(); self.win = win; self.rows = []
        v = QVBoxLayout(self); v.setContentsMargins(12, 12, 12, 12)
        t = QLabel('🚀 整理精靈'); t.setObjectName('title'); v.addWidget(t)
        v.addWidget(note('照這個順序做最快：先清掉壞的、整包重複的，再整包處理你整理過的資料夾，最後才一組一組審。每一步都只搬到同一顆硬碟的隔離區或分類資料夾、可以復原。'))
        self.busy = QLabel(''); self.busy.setStyleSheet('color:#4dc9ff'); v.addWidget(self.busy)
        self.g = QGridLayout(); self.g.setSpacing(8); v.addLayout(self.g); v.addStretch(1)
        for i in range(10):                                                          # （V0.4.04：以前只有 6 列，後面加的步驟看不到）
            num = QLabel(str(i + 1)); num.setFixedSize(34, 34); num.setAlignment(Qt.AlignCenter)
            lab = QLabel(''); lab.setTextFormat(Qt.RichText); lab.setWordWrap(True)
            b1 = QPushButton(''); b2 = QPushButton('去看 ›'); b0 = QPushButton('🔍 先分析')
            b1.clicked.connect(lambda _=False, i=i: self.act(i)); b2.clicked.connect(lambda _=False, i=i: self.goto(i)); b0.clicked.connect(lambda _=False: self.do('dpl_scan'))
            for c, w_ in enumerate((num, lab, b0, b1, b2)): self.g.addWidget(w_, i, c)
            self.rows.append((num, lab, b0, b1, b2))
        self.g.setColumnStretch(1, 1)
        self.tm = QTimer(self); self.tm.timeout.connect(self.load); self.tm.start(3000); self.S = []

    def showEvent(self, e): super().showEvent(e); self.load()

    def load(self):
        if self.isVisible(): bg(ENG.wizard, self._got)

    def _got(self, W):
        self.S = W['steps']; self.busy.setText('背景正在搬…（做完會自動更新）' if W.get('busy') else '')
        for i, (num, lab, b0, b1, b2) in enumerate(self.rows):
            if i >= len(self.S): [w_.hide() for w_ in (num, lab, b0, b1, b2)]; continue
            s_ = self.S[i]; cur = i == W['cur']
            num.setText('✔' if s_['done'] else str(i + 1))
            num.setStyleSheet(f"border-radius:17px;font-weight:900;color:#fff;background:{'#45d483' if s_['done'] else ('#2f9bff' if cur else '#2a3340')}")
            lab.setText(f"<b style='font-size:14px'>{s_['ic']} {esc_html(s_['t'])}</b>" + (f"　<span style='color:#8994a4'>{fmt_b(s_['b'])}</span>" if s_['b'] else '') + f"<br><span style='color:#8994a4'>{esc_html(s_['d'])}</span>")
            b0.setVisible(s_['k'] == 'dpl' and s_['n'] < 0)
            a = s_['act'] if not s_['done'] else ''
            b1.setVisible(bool(a and a in self.ACT)); b1.setText(self.ACT.get(a, ('',))[0]); b1.setEnabled(not W.get('busy') or a == 'vc_group')
            if a in ('dpl_all', 'dup_all', 'vc_group', 'move'): b1.setObjectName('start')

    def goto(self, i):
        if i < len(self.S): self.win.nav.setCurrentRow(self.GO.get(self.S[i]['go'], 0))

    def act(self, i):
        if i < len(self.S): self.do(self.S[i]['act'])

    def do(self, a):
        if a == 'vc_group':
            p = self.win.vcp
            try:
                p.folder.setText(''); p.gc.setCurrentIndex(max(0, p.gc.findData('pack'))); i_ = p.flt.findData('todo_np')
                if i_ >= 0: p.flt.setCurrentIndex(i_)
                p.reload()
            except Exception: pass
            self.win.nav.setCurrentRow(12); return
        if a in ('pet_view', 'junk_view', 'vc_sug'):                                  # 🐾／🌑／💡：分類頁切到那個篩選（V0.4.04）
            p = self.win.vcp; i_ = p.flt.findData({'pet_view': 'pet', 'junk_view': 'pet_s_junk', 'vc_sug': 'todo_sug'}[a])
            if i_ >= 0: p.flt.setCurrentIndex(i_)
            self.win.nav.setCurrentRow(12); return
        if a == 'pet_start': ENG.pet.start(); self.win.msg('🐾 開始看內容（背景）', 4000); self.load(); return
        nm, q = self.ACT.get(a, ('', ''))
        if q and QMessageBox.question(self, '🚀 整理精靈', q) != QMessageBox.Yes: return
        if a == 'bad': ok = ENG.fc_quar_filter('bad'); self.win.msg('📦 損毀的開始搬到隔離區（背景）' if ok else '現在有別的整批搬移在做，等一下')
        elif a == 'dpl_all': self.win.msg(ENG.dpl.start_all()['message'])
        elif a == 'dpl_scan': self.win.msg('🧭 分析中…'); bg(lambda: ENG.dpl.analyze(True), lambda _r: (self.win.msg('🧭 分析好了'), self.load())); return
        elif a == 'dup_all': ok = ENG.fc_bulk_start(); self.win.msg('🔁 開始全部照建議處理（背景）' if ok else '現在有別的整批搬移在做，等一下')
        elif a == 'move': ok = ENG.vc.move_start(); self.win.msg('🚚 開始搬檔（背景）' if ok else '已經在搬了')
        self.load()


class DupPlanPage(QWidget):
    """🧭 重複檔用資料夾看（V0.2.16）：哪些資料夾整包被複製、留哪邊、合併."""
    def __init__(self, win):
        super().__init__(); self.win = win; self.R = None; self.rows = []
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('🧭 重複資料夾最佳解'); t.setObjectName('title'); r.addWidget(t)
        self.st = QLabel(''); self.st.setTextFormat(Qt.RichText); self.st.setWordWrap(True); r.addWidget(self.st, 1)
        b_re = QPushButton('🔄 重新分析'); self.b_all = QPushButton('⚡ ① 整包複本全部照建議'); self.b_all.setObjectName('start'); b_stop = QPushButton('⏹ 停止'); b_hist = QPushButton('↶ 最近做過的…')
        for w_ in (b_re, self.b_all, b_stop, b_hist): r.addWidget(w_)
        b_hist.clicked.connect(self.hist)
        self.sum = QLabel('分析中…'); self.sum.setTextFormat(Qt.RichText); self.sum.setWordWrap(True); v.addWidget(self.sum)
        g1 = QGroupBox('最上層資料夾：多少在別的地方也有'); v1 = QVBoxLayout(g1); v.addWidget(g1)
        self.tops = HBars(260); v1.addWidget(self.tops)
        rt = QHBoxLayout(); v1.addLayout(rt); self.tpc = QComboBox(); rt.addWidget(self.tpc, 1); b_tk = QPushButton('執行（先預覽）'); rt.addWidget(b_tk); b_tk.clicked.connect(self.top_keep)
        g2 = QGroupBox('資料夾對（⭐＝建議保留；大的先）'); v2 = QVBoxLayout(g2); v.addWidget(g2, 1)
        rf = QHBoxLayout(); v2.addLayout(rf); self.flt = QComboBox(); [self.flt.addItem(n, k) for k, n in (('all', '全部'), ('copy', '📋 整包複本'), ('overlap', '🔀 部分重複'))]; rf.addWidget(self.flt); rf.addStretch(1)
        self.tb = QTableWidget(0, 6); self.tb.setHorizontalHeaderLabels(['類型', '⭐ 建議保留', '另一邊', '一樣的', '另一邊幾 % 這邊也有', '原因']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.horizontalHeader().setStretchLastSection(True)
        for i, w in enumerate((90, 300, 300, 150, 130)): self.tb.setColumnWidth(i, w)
        self.tb.setMinimumHeight(260); v2.addWidget(self.tb, 1)
        self.pvs = []
        for lab in ('⭐ 建議保留這邊：', '另一邊：'):
            rr = QHBoxLayout(); v2.addLayout(rr); l_ = QLabel(lab); l_.setFixedWidth(110); l_.setObjectName('muted'); rr.addWidget(l_)
            pv = QListWidget(); pv.setViewMode(QListView.IconMode); pv.setFlow(QListView.LeftToRight); pv.setWrapping(False); pv.setIconSize(QSize(128, 80)); pv.setFixedHeight(112)
            pv.setMovement(QListView.Static); pv.itemDoubleClicked.connect(lambda it: open_file(it.data(Qt.UserRole))); rr.addWidget(pv, 1); self.pvs.append(pv)
        self.tb.currentCellChanged.connect(lambda r_, _c, _r2, _c2: self._preview())
        r2 = QHBoxLayout(); v2.addLayout(r2)
        b_k1 = QPushButton('保留 ⭐ 那邊'); b_k2 = QPushButton('保留另一邊'); b_m1 = QPushButton('🔀 合併到 ⭐'); b_m2 = QPushButton('🔀 合併到另一邊'); b_o1 = QPushButton('📂 打開 ⭐'); b_o2 = QPushButton('📂 打開另一邊')
        for w_ in (b_o1, b_o2): r2.addWidget(w_)
        r2.addStretch(1)
        for w_ in (b_k1, b_k2, b_m1, b_m2): r2.addWidget(w_)
        v2.addWidget(note('「保留」：另一邊裡「這邊也有一模一樣的」搬到隔離區，獨有的不動。「合併」：重複的搬隔離區、獨有的搬過來（保留子資料夾），搬空的資料夾收掉。都只在同一顆硬碟搬、可以在隔離區依原因復原；搬之前會再確認保留那邊真的有，不會把最後一份搬走。'))
        b_re.clicked.connect(lambda: self.load(True)); self.b_all.clicked.connect(self.do_all); b_stop.clicked.connect(lambda: ENG.dpl.st.__setitem__('cancel', True))
        self.flt.currentIndexChanged.connect(lambda _i: self._fill())
        b_k1.clicked.connect(lambda: self.act(True, False)); b_k2.clicked.connect(lambda: self.act(False, False)); b_m1.clicked.connect(lambda: self.act(True, True)); b_m2.clicked.connect(lambda: self.act(False, True))
        b_o1.clicked.connect(lambda: self._open(True)); b_o2.clicked.connect(lambda: self._open(False))
        self.tm = QTimer(self); self.tm.timeout.connect(self._tick); self.tm.start(2000); self._first = True; self._was = False

    def showEvent(self, e):
        super().showEvent(e)
        if self._first: self._first = False; self.load()

    def load(self, force=False):
        self.sum.setText('🧭 分析中…（七萬多組要幾秒到一分鐘）'); bg(lambda: ENG.dpl.analyze(force), self._got)

    def _got(self, R):
        self.R = R; P = R['pairs']; cp = [p for p in P if p['rel'] == 'copy']; ov = [p for p in P if p['rel'] != 'copy']
        self.sum.setText(f"{R['groups']:,} 組重複、多出來 <b>{R['extra']:,}</b> 份（<b>{fmt_b(R['extra_b'])}</b>），找到 <b>{len(P)}</b> 對整包／大半被複製的資料夾。<br>"
                         f"最佳解：① <b>整包是複本</b> {len(cp)} 對（{fmt_b(sum(p['bytes'] for p in cp))}）→ 按「⚡ ① 整包複本全部照建議」　"
                         f"② <b>部分重複</b> {len(ov)} 對（{fmt_b(sum(p['bytes'] for p in ov))}）→ 一對一對選「🔀 合併」或「保留」　③ 剩下零散的 →「🔁 重複檔」⚡ 全部照建議　④ 合併好的再用「📦 資料夾包」整包分類")
        self.b_all.setEnabled(bool(cp))
        mx = max([t['b'] for t in R['tops']] + [1])
        self.tops.set_rows([(os.path.join(os.path.basename(os.path.dirname(t['path'])), os.path.basename(t['path'])), f"{t['pct']}% 別處也有・{fmt_b(t['b'])}",
                             [('#f0ad4e' if t['pct'] >= 80 else '#3b8eea', t['b'] * t['pct'] / 100, '大多在：' + '、'.join(os.path.basename(w['path']) + f" {w['n']:,}" for w in t['with'])), ('#2a3340', t['b'] * (100 - t['pct']) / 100, '只有這裡有')],
                             t['b'] / mx) for t in R['tops'][:20]])
        self.tpc.clear(); self.tpc.addItem('（最上層整個處理：選一項）', None)
        for t in R['tops'][:20]:
            for w in t['with'][:2]:
                self.tpc.addItem(f"留「{os.path.basename(w['path'])}」的，「{os.path.basename(t['path'])}」裡它也有的搬走（{w['n']:,} 個）", (w['path'], t['path']))
        self._fill()

    def top_keep(self):
        x = self.tpc.currentData()
        if not x: self.win.msg('先在左邊選一項'); return
        kd, od = x; pl = ENG.dpl.plan(kd, od)
        if QMessageBox.question(self, '最上層整個處理', f"保留「{kd}」那邊的？\n\n・「{od}」裡 {pl['dup']:,} 個「{os.path.basename(kd)}」也有一模一樣的 → 隔離區（{fmt_b(pl['dup_b'])}）\n・{pl['uniq']:,} 個只有這裡有的不動\n\n可以在「📦 隔離區」依原因整批復原。") != QMessageBox.Yes: return
        self.win.msg(ENG.dpl.start(kd, od)['message'])

    def _fill(self):
        if not self.R: return
        k = self.flt.currentData() or 'all'; self.rows = [p for p in self.R['pairs'] if k == 'all' or (p['rel'] == 'copy') == (k == 'copy')]
        self.tb.setRowCount(len(self.rows))
        for i, p in enumerate(self.rows):
            kd, od = (p['a'], p['b']) if p['keep'] == 'a' else (p['b'], p['a']); oc = p['pb'] if p['keep'] == 'a' else p['pa']
            vals = ('📋 整包複本' if p['rel'] == 'copy' else '🔀 部分重複', kd, od, f"{p['n']:,} 個・{fmt_b(p['bytes'])}", f'{oc}%', p['why'] + ('' if p['same_drive'] else '（不同硬碟：只能保留）'))
            for c, val in enumerate(vals): self.tb.setItem(i, c, _ti(val, p['tip']))

    def _preview(self):
        p = self._cur()
        for pv in self.pvs: pv.clear()
        if not p: return
        kd, od = (p['a'], p['b']) if p['keep'] == 'a' else (p['b'], p['a']); self._pt = getattr(self, '_pt', 0) + 1; tok = self._pt
        for pv, d in zip(self.pvs, (kd, od)):
            bg(lambda d=d: ENG.vg.pack_ids(d, ('video', 'photo'))[:40], lambda R, pv=pv, tok=tok: self._pv_fill(pv, R, tok))

    def _pv_fill(self, pv, R, tok):
        if tok != self._pt: return
        for fid, fp, _c, _m, kind, dur in R:
            it = QListWidgetItem('🎞' if kind == 'video' else '📷'); it.setData(Qt.UserRole, fp); it.setToolTip(fp); pv.addItem(it)
            bg((lambda fid=fid: ENG.vc.thumb(fid)) if kind == 'video' else (lambda fid=fid: ENG.fc_thumb(fid, 320)), lambda pth, it=it, tok=tok: pth and tok == self._pt and it.setIcon(QIcon(QPixmap(str(pth)))))

    def _cur(self):
        i = self.tb.currentRow()
        return self.rows[i] if 0 <= i < len(self.rows) else None

    def _open(self, star):
        p = self._cur()
        if p: d = (p['a'] if p['keep'] == 'a' else p['b']) if star else (p['b'] if p['keep'] == 'a' else p['a']); QDesktopServices.openUrl(QUrl.fromLocalFile(d))

    def act(self, star, merge):
        p = self._cur()
        if not p: self.win.msg('先點一對'); return
        kd, od = (p['a'], p['b']) if p['keep'] == 'a' else (p['b'], p['a'])
        if not star: kd, od = od, kd
        pl = ENG.dpl.plan(kd, od, merge)
        txt = (f"🔀 合併到「{kd}」？\n\n・「{od}」裡 {pl['dup']:,} 個一樣的 → 隔離區（{fmt_b(pl['dup_b'])}）\n・{pl['uniq']:,} 個獨有的 → 搬過去（保留子資料夾）\n・搬空的資料夾會收掉" if merge else
               f"保留「{kd}」？\n\n・「{od}」裡 {pl['dup']:,} 個這邊也有的 → 隔離區（{fmt_b(pl['dup_b'])}）\n・{pl['uniq']:,} 個獨有的不動")
        if QMessageBox.question(self, '🧭 重複資料夾', txt + '\n\n可以在「📦 隔離區」依原因整批復原。') != QMessageBox.Yes: return
        self.win.msg(ENG.dpl.start(kd, od, merge)['message'])

    def hist(self):
        H = ENG.dpl.history()
        if not H: self.win.msg('最近沒有做過'); return
        names = [f"{'🔀 合併到' if h['kind'] == 'merge' else '保留'} {h['keep']}（{h['n']:,} 個・{fmt_day(h['t'])[:16]}）" for h in H]
        nm, ok = QInputDialog.getItem(self, '↶ 復原哪一筆？', '搬到隔離區的搬回原處；合併過去的搬回原本的資料夾', names, 0, False)
        if not ok: return
        self.win.msg(ENG.dpl.undo(H[names.index(nm)]['key'])['message'], 8000); self.load(True)

    def do_all(self):
        if not self.R: return
        cp = [p for p in self.R['pairs'] if p['rel'] == 'copy']
        if QMessageBox.question(self, '⚡ 整包複本全部照建議', f"「整包是複本」的 {len(cp)} 對，全部保留 ⭐ 那邊、另一邊的複本搬到隔離區（{fmt_b(sum(p['bytes'] for p in cp))}）？\n\n獨有的不動；每個檔都會再確認保留那邊有一模一樣的。") != QMessageBox.Yes: return
        self.win.msg(ENG.dpl.start_all()['message'])

    def _tick(self):
        if not self.isVisible(): return
        S = ENG.dpl.status()
        if S.get('run'):
            self._was = True; self.st.setText(f"<span style='color:#4dc9ff'>🧭 處理中 {S.get('n', 0):,}／{S.get('total', 0):,}・已搬 {S.get('q', 0):,} 個 {fmt_b(S.get('b', 0))}</span>")
        else:
            self.st.setText(('✔ ' + esc_html(S.get('msg', ''))) if S.get('msg') else '')
            if self._was: self._was = False; self.load(True)


class PackPage(QWidget):
    """📦 資料夾包（V0.2.14）：你以前整理過、有取名字的資料夾整包看、整包放到「已篩選」."""
    def __init__(self, win):
        super().__init__(); self.win = win; self.rows = []
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('📦 資料夾包'); t.setObjectName('title'); r.addWidget(t)
        self.show_ = QComboBox()
        for k, nm in (('todo', '還沒審的'), ('done', '審完的'), ('skip', '跳過的'), ('all', '全部'), ('moved', '↶ 最近整包搬過')): self.show_.addItem(nm, k)
        self.q = QLineEdit(); self.q.setPlaceholderText('找資料夾名…'); self.st = QLabel(''); self.st.setObjectName('muted'); b_ref = QPushButton('🔄')
        self.ord_ = QComboBox()
        for k, nm in (('', '建議順序'), ('n', '待審最多'), ('new', '日期新→舊'), ('old', '日期舊→新'), ('big', '最大'), ('name', '名字')): self.ord_.addItem(nm, k)
        self.ord_.currentIndexChanged.connect(lambda _i: self.load())
        for w_ in (self.show_, self.ord_, self.q, b_ref, self.st): r.addWidget(w_)
        r.addStretch(1)
        v.addWidget(note('你以前自己整理、有取名字的資料夾（例如「2020-日本旅遊」）整包列出來。先「📂 打開」或「▶ 一部一部審」看一下，再決定「✅ 整包已篩選」：整包（影片＋照片）搬到同一顆硬碟的 \\FileCompare_分類\\已篩選\\資料夾名\\，保留原本的子資料夾。手機整台倒出來的（DCIM、備份、XIAOMI…）不算一包。'))
        rd = QHBoxLayout(); v.addLayout(rd); self.dest_l = QLabel(''); self.dest_l.setObjectName('muted'); rd.addWidget(self.dest_l, 1)
        b_dest = QPushButton('📁 已篩選放哪…'); rd.addWidget(b_dest); b_dest.clicked.connect(self.set_dest)
        self.tb = QTableWidget(0, 6); self.tb.setHorizontalHeaderLabels(['資料夾包', '影片（待審）', '照片', '大小', '日期', '位置']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.tb.setColumnWidth(0, 220); self.tb.setColumnWidth(1, 100); self.tb.setColumnWidth(2, 60); self.tb.setColumnWidth(3, 90); self.tb.setColumnWidth(4, 170)
        self.tb.setSelectionMode(QAbstractItemView.ExtendedSelection)
        hs = QHBoxLayout(); v.addLayout(hs, 1); hs.addWidget(self.tb, 3)
        self.pv = QListWidget(); self.pv.setViewMode(QListView.IconMode); self.pv.setIconSize(QSize(160, 100)); self.pv.setResizeMode(QListView.Adjust); self.pv.setUniformItemSizes(True)
        self.pv.setSpacing(3); self.pv.setMovement(QListView.Static); self.pv.setMinimumWidth(360); hs.addWidget(self.pv, 2)
        self.pv.itemDoubleClicked.connect(lambda it: open_file(it.data(Qt.UserRole)))
        self.tb.currentCellChanged.connect(lambda r_, _c, _r2, _c2: self.preview())
        r2 = QHBoxLayout(); v.addLayout(r2)
        b_open = QPushButton('📂 打開資料夾'); b_one = QPushButton('▶ 一部一部審'); b_skip = QPushButton('⏭ 跳過／放回'); b_cat = QPushButton('🏷 整包分到…'); b_keep = QPushButton('✅ 整包已篩選'); b_keep.setObjectName('start')
        b_add = QPushButton('＋ 指定一包…'); b_add.setToolTip('自動判斷沒抓到：自己選一個資料夾當成一包（例如沒取名字的旅行資料夾）')
        b_no = QPushButton('🚫 不是一包'); b_no.setToolTip('自動判斷錯了：這個資料夾不要當成一包')
        b_nx = QPushButton('⏭ 下一包'); b_nx.clicked.connect(self.next_pack)
        b_back = QPushButton('↶ 搬回原處'); b_back.setToolTip('「最近整包搬過」裡選一包：整包搬回原本的位置、變回還沒審'); b_back.clicked.connect(self.back)
        for w_ in (b_open, b_nx, b_one, b_skip, b_add, b_no, b_back): r2.addWidget(w_)
        r2.addStretch(1); r2.addWidget(b_cat); r2.addWidget(b_keep)
        b_add.clicked.connect(lambda: (lambda d: d and (self.win.msg(ENG.vg.mark(os.path.normpath(d), 1)['message']), self.load()))(pick_folder(self, '選一個資料夾當成一包')))
        b_no.clicked.connect(lambda: self.cur() and (self.win.msg(ENG.vg.mark(self.cur()['path'], 0)['message']), self.load()))
        b_ref.clicked.connect(self.load); self.q.returnPressed.connect(self.load); self.show_.currentIndexChanged.connect(lambda _i: self.load())
        b_open.clicked.connect(lambda: self.cur() and QDesktopServices.openUrl(QUrl.fromLocalFile(self.cur()['path'])))
        self.tb.itemDoubleClicked.connect(lambda _it: self.cur() and QDesktopServices.openUrl(QUrl.fromLocalFile(self.cur()['path'])))
        b_one.clicked.connect(self.one); b_skip.clicked.connect(self.skip); b_cat.clicked.connect(lambda: self.keep(True)); b_keep.clicked.connect(lambda: self.keep(False)); self._first = True

    def showEvent(self, e):
        super().showEvent(e)
        if self._first: self._first = False; self.load()

    def _dest_text(self):
        try:
            r = ENG.db.one('SELECT dest FROM vc_cat WHERE name=?', ('已篩選',)); d = (r[0] if r else '') or ''
            self.dest_l.setText('📁 「已篩選」放在：' + ('📌 不搬（留在原處，只標記）' if d.strip() in vsort.STAY else (d + '\\資料夾名\\…' if d else '每顆硬碟的 \\FileCompare_分類\\已篩選\\資料夾名\\…')))
        except Exception: pass

    def set_dest(self):
        r = ENG.db.one('SELECT id FROM vc_cat WHERE name=?', ('已篩選',))
        if not r: return
        opts = ['預設：每顆硬碟的 \\FileCompare_分類\\已篩選', '📌 不搬（只標記、留在原處）', '選一個資料夾…']
        nm, ok = QInputDialog.getItem(self, '📁 已篩選放哪', '整包已篩選、一部一部按「已篩選」的，要搬到哪？', opts, 0, False)
        if not ok: return
        if nm == opts[0]: d = ''
        elif nm == opts[1]: d = '不搬'
        else:
            d = pick_folder(self, '已篩選放哪（同一顆硬碟）')
            if not d: return
            d = os.path.normpath(d)
        self.win.msg(ENG.vc.cat_edit(r[0], dest=d)['message']); self._dest_text()

    def load(self):
        self._dest_text()
        k = self.show_.currentData() or 'todo'; q = self.q.text().strip(); o = self.ord_.currentData() or ''; self.st.setText('讀取中…')
        if k == 'moved': bg(ENG.vg.recent, self._got_moved); return
        bg(lambda: ENG.vg.packs(k, q, o), self._got)

    def _got_moved(self, L):
        self.rows = [dict(g, path='', moved=True, n=g['n'], todo=0, np=0, b=0, t0=g['t'], t1=0) for g in L]; self.tb.setRowCount(len(self.rows))
        for i, g in enumerate(self.rows):
            for c, val in enumerate(('↶ ' + g['name'], f"{g['n']:,} 個", '', '', fmt_day(g['t'])[:16], f"→ {g['cname']}（選這一列按「↶ 搬回原處」）")): self.tb.setItem(i, c, _ti(val, val))
        self.st.setText(f'{len(L):,} 包最近整包搬過')

    def back(self):
        g = self.cur()
        if not g or not g.get('moved'): self.win.msg('先在上面選「↶ 最近整包搬過」，再點一包'); return
        if QMessageBox.question(self, '↶ 搬回原處', f"「{g['name']}」整包搬回原本的位置，變回「還沒審」？") != QMessageBox.Yes: return
        self.win.msg(ENG.vg.pack_back(g['name'], g['cat'])['message'], 8000); self.load()

    def next_pack(self):
        r_ = self.tb.currentRow()
        if r_ + 1 >= self.tb.rowCount(): self.win.msg('已經是最後一包了'); return
        self.tb.setCurrentCell(r_ + 1, 0)

    def _got(self, L):
        keep_row = getattr(self, '_keep_row', None); self._keep_row = None
        self.rows = L[:2000]; self.tb.setRowCount(len(self.rows))
        for i, g in enumerate(self.rows):
            d = fmt_day(g['t0'])[:10] if g['t0'] else ''; d2 = fmt_day(g['t1'])[:10] if g['t1'] else ''
            vals = ('📦 ' + g['name'] + ('　⏭' if g.get('skip') else '') + (f"　🐾{g['pet']}" if g.get('pet') else ''), f"{g['n']:,}（{g['todo']:,}）", f"{g['np']:,}", fmt_b(g['b']), d + ('～' + d2 if d2 and d2 != d else ''), os.path.dirname(g['path']))
            for c, val in enumerate(vals): self.tb.setItem(i, c, _ti(val, g['path']))
        self.st.setText(f'{len(L):,} 包')
        if keep_row is not None and self.rows: self.tb.setCurrentCell(min(keep_row, len(self.rows) - 1), 0); self.preview()   # 分完自動跳到下一包

    def preview(self):
        g = self.cur(); self.pv.clear()
        if not g or not g.get('path'): return
        p = g['path']; self._pvtok = getattr(self, '_pvtok', 0) + 1; tok = self._pvtok
        bg(lambda: ENG.vg.pack_ids(p, ('video', 'photo'))[:120], lambda R, tok=tok: self._pv_got(R, tok))

    def _pv_got(self, R, tok):
        if tok != self._pvtok: return
        for fid, fp, cat, mv, kind, dur in R:
            it = QListWidgetItem(('🎞 ' + fmt_t(dur or 0) if kind == 'video' else '📷') + ('　✔' if cat else '')); it.setData(Qt.UserRole, fp); it.setToolTip(fp); it.setSizeHint(QSize(168, 124)); self.pv.addItem(it)
            bg((lambda fid=fid: ENG.vc.thumb(fid)) if kind == 'video' else (lambda fid=fid: ENG.fc_thumb(fid, 320)), lambda pth, it=it, tok=tok: pth and tok == self._pvtok and it.setIcon(QIcon(QPixmap(str(pth)))))

    def sel(self):
        R = sorted({i.row() for i in self.tb.selectedIndexes()})
        return [self.rows[r] for r in R if 0 <= r < len(self.rows) and self.rows[r].get('path')]

    def cur(self):
        i = self.tb.currentRow()
        return self.rows[i] if 0 <= i < len(self.rows) else None

    def keep_many(self, G, ask):
        cat = 0; cn = '已篩選'
        if ask:
            C = ENG.vc.cats()
            nm, ok = QInputDialog.getItem(self, '🏷 整包分到…', f'選的 {len(G)} 包整包分到哪一類？（每包保留自己的資料夾、只搬這幾包）', [c['name'] for c in C], 0, False)
            if not ok: return
            c = next(c for c in C if c['name'] == nm); cat = c['id']; cn = c['name']
        if QMessageBox.question(self, '整包分類', f"選的 {len(G)} 包（{'、'.join(g['name'] for g in G[:5])}{'…' if len(G) > 5 else ''}）整包放到「{cn}」並馬上搬？\n\n每包保留自己的資料夾；可以在「↶ 最近整包搬過」一包一包搬回。") != QMessageBox.Yes: return
        r = ENG.vg.pack_tag_many([g['path'] for g in G], cat); msg = r['message']
        if r.get('ids') and ENG.vc.move_start(r['ids']): msg += '；🚚 開始搬這幾包（背景）'
        self.win.msg(msg, 8000); QTimer.singleShot(1500, self.load)

    def one(self):
        g = self.cur()
        if not g: self.win.msg('先點一包'); return
        p = self.win.vcp
        try:
            p.folder.setText(g['path']); p.gc.setCurrentIndex(0); p.kc.setCurrentIndex(0); p.reload()
        except Exception: pass
        self.win.nav.setCurrentRow(12); self.win.msg(f"▶ 只看「{g['name']}」：一部一部審（清掉上面的資料夾欄就回到全部）")

    def skip(self):
        g = self.cur()
        if not g: return
        self.win.msg(ENG.vg.pack_skip(g['path'], not g.get('skip'))['message']); self.load()

    def keep(self, ask):
        G = self.sel()
        if len(G) > 1: return self.keep_many(G, ask)
        g = self.cur()
        if not g: self.win.msg('先點一包'); return
        cat = 0; cn = '已篩選'
        if ask:
            C = ENG.vc.cats()
            if not C: self.win.msg('先在「影片快速分類」新增分類'); return
            nm, ok = QInputDialog.getItem(self, '🏷 整包分到…', f"「{g['name']}」整包分到哪一類？（保留資料夾、馬上搬）", [c['name'] for c in C], 0, False)
            if not ok: return
            c = next(c for c in C if c['name'] == nm); cat = c['id']; cn = c['name']
        sz = f"{g['n']:,} 部影片" + (f"＋{g['np']:,} 張照片" if g.get('np') else '') + (f"（{fmt_b(g['b'])}）" if g.get('b') else '') + ('\n\n⚠ 這包很大，確定都是同一類嗎？' if g['n'] > 500 else '')
        if QMessageBox.question(self, '整包分類', f"「{g['name']}」整包 {sz}\n放到「{cn}」並馬上搬？\n\n會保留資料夾：…\\FileCompare_分類\\{cn}\\{g['name']}\\…\n搬錯了可以在「📦 隔離區」依原因整批復原。") != QMessageBox.Yes: return
        self._keep_row = self.tb.currentRow()
        r = ENG.vg.pack_tag(g['path'], cat); msg = r['message'].split('，按 🚚')[0]
        if r.get('ok') and r.get('ids') and ENG.vc.move_start(r['ids']): msg += '；🚚 開始搬這一包（背景）'
        self.win.msg(msg, 8000); QTimer.singleShot(1500, self.load)


class FavPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.off = 0
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('⭐ 最愛'); t.setObjectName('title'); r.addWidget(t); self.st = QLabel(''); self.st.setObjectName('muted'); r.addWidget(self.st, 1)
        b_un = QPushButton('取消選取的最愛'); r.addWidget(b_un)
        v.addWidget(note('在手機看大圖時按「☆ 最愛」、或分類頁按 F 加進來。重複、相似時會優先保留最愛那份。雙擊打開。'))
        self.grid = QListWidget(); self.grid.setViewMode(QListView.IconMode); self.grid.setIconSize(QSize(150, 150)); self.grid.setResizeMode(QListView.Adjust)
        self.grid.setUniformItemSizes(True); self.grid.setSpacing(4); self.grid.setMovement(QListView.Static); self.grid.setSelectionMode(QAbstractItemView.ExtendedSelection); v.addWidget(self.grid, 1)
        self.more = QPushButton('再載入 120 個'); v.addWidget(self.more); self.more.hide()
        self.grid.itemDoubleClicked.connect(lambda it: open_file(it.data(Qt.UserRole)[1])); self.more.clicked.connect(lambda: self.load(True)); b_un.clicked.connect(self.unfav)

    def showEvent(self, e): super().showEvent(e); self.load()

    def load(self, more=False):
        if not more: self.off = 0; self.grid.clear()
        else: self.off += 120
        off = self.off; bg(lambda: ENG.favs(off, 120), self._got)

    def _got(self, j):
        self.st.setText(f"　{j['n']:,} 個"); self.more.setVisible(self.off + 120 < j['n'])
        for f in j['rows']:
            it = QListWidgetItem(('🎞 ' if f['kind'] == 'video' else '') + fmt_day(f.get('taken') or f.get('mtime'))[:10]); it.setData(Qt.UserRole, (f['id'], f['path'])); it.setToolTip(f['path']); it.setSizeHint(QSize(160, 180)); self.grid.addItem(it)
            bg(lambda fid=f['id']: ENG.fc_thumb(fid, 320), lambda p, it=it: p and it.setIcon(QIcon(QPixmap(p))))

    def unfav(self):
        for it in self.grid.selectedItems(): ENG.fav_set(it.data(Qt.UserRole)[0], False)
        self.load()


# ============================================================ 📁 重複資料夾（V0.1.27）
class DdirPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.P = []
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('📁 重複資料夾'); t.setObjectName('title'); r.addWidget(t)
        self.st = QLabel(''); self.st.setObjectName('muted'); r.addWidget(self.st, 1); b_r = QPushButton('🔄 重新算'); r.addWidget(b_r)
        v.addWidget(note('兩個資料夾有很多一模一樣的照片影片（備份、手機資料夾複製了好幾次）。選一列，按「保留 A」或「保留 B」：另一個裡面「保留的那邊也有一模一樣的」才搬到隔離區，獨有的完全不動。'))
        self.tb = QTableWidget(0, 6); self.tb.setHorizontalHeaderLabels(['一樣的', '大小', 'A', 'A 有幾 %', 'B', 'B 有幾 %']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.setSelectionMode(QAbstractItemView.SingleSelection)
        for c in (2, 4): self.tb.horizontalHeader().setSectionResizeMode(c, QHeaderView.Stretch)
        for c, w in ((0, 80), (1, 90), (3, 70), (5, 70)): self.tb.setColumnWidth(c, w)
        v.addWidget(self.tb, 1)
        rb = QHBoxLayout(); v.addLayout(rb); ba = QPushButton('保留 A（搬走 B 裡一樣的）'); bb = QPushButton('保留 B（搬走 A 裡一樣的）'); oa = QPushButton('📂 打開 A'); ob = QPushButton('📂 打開 B')
        for b in (ba, bb, oa, ob): rb.addWidget(b)
        rb.addStretch(1)
        ba.clicked.connect(lambda: self.keep('a')); bb.clicked.connect(lambda: self.keep('b'))
        oa.clicked.connect(lambda: (p := self.cur()) and open_file(p['a'])); ob.clicked.connect(lambda: (p := self.cur()) and open_file(p['b']))
        b_r.clicked.connect(lambda: self.load(True)); self.tm = QTimer(self); self.tm.timeout.connect(self._tick); self.tm.start(1500)

    def showEvent(self, e): super().showEvent(e); self.load()

    def load(self, force=False): self.st.setText('計算中…'); bg(lambda: ENG.ddir.pairs(force=force), self._got)

    def _got(self, r):
        self.P = r.get('pairs') or []; self.tb.setRowCount(len(self.P))
        for i, p in enumerate(self.P):
            for j, val in enumerate((f"{p['n']:,}", fmt_b(p['b_bytes']), p['a'], f"{p['pa']}%", p['b'], f"{p['pb']}%")): self.tb.setItem(i, j, _ti(val, val))
        self.st.setText(f'{len(self.P):,} 對資料夾' if self.P else '沒有找到（要等「比對重複」做完）')

    def cur(self):
        i = self.tb.currentRow(); return self.P[i] if 0 <= i < len(self.P) else None

    def keep(self, w):
        p = self.cur()
        if not p: self.win.msg('先選一列'); return
        k, o = (p['a'], p['b']) if w == 'a' else (p['b'], p['a'])
        if QMessageBox.question(self, '重複資料夾', f'保留：{k}\n\n搬走：{o} 裡面「保留的那邊也有一模一樣的」約 {p["n"]:,} 個（{fmt_b(p["b_bytes"])}）\n\n搬到隔離區、可以復原。') != QMessageBox.Yes: return
        self.win.msg(ENG.ddir.keep(k, o)['message']); self._was = True

    def _tick(self):
        if not self.isVisible(): return
        S = ENG.ddir.st
        if S.get('run'): self.st.setText(f"📁 搬到隔離區中：{S.get('n', 0):,}／{S.get('total', 0):,}")
        elif getattr(self, '_was', False): self._was = False; self.win.msg('📁 ' + S.get('msg', '')); self.load(True)


# ============================================================ ⚙ 設定
class SetPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        g = QGroupBox('一般'); f = QFormLayout(g); v.addWidget(g)
        self.tray = QCheckBox('按右上角 X：縮到右下角（背景繼續做；托盤右鍵「結束」才真的關）'); self.cover = QCheckBox('打開程式先顯示封面（不露出內容）')
        self.restore = QCheckBox('從右下角叫回來時先顯示封面'); self.idle = QSpinBox(); self.idle.setRange(0, 240); self.idle.setSuffix(' 分鐘沒動作回封面（0＝不要）')
        self.autor = QCheckBox('閃退自動重開（看門狗；10 分鐘內閃退 3 次就先不重開）'); self.frz = QSpinBox(); self.frz.setRange(1, 30); self.frz.setSuffix(' 秒（畫面卡超過就記到 ui_freeze_log.txt）')
        for w_ in (self.tray, self.cover, self.restore, self.idle, self.autor, self.frz): f.addRow(w_)
        self._web_box(v)
        g3 = QGroupBox('資料夾'); r3 = QHBoxLayout(g3); v.addWidget(g3)
        for t_, d_ in (('📂 程式資料夾', ROOT), ('📂 Data（設定、資料庫）', ROOT / 'Data'), ('📂 LOG', ROOT / 'LOG'), ('📂 UPDATE（更新包）', ROOT / 'UPDATE')):
            b_ = QPushButton(t_); b_.clicked.connect(lambda _c=False, d_=d_: (Path(d_).mkdir(exist_ok=True), QDesktopServices.openUrl(QUrl.fromLocalFile(str(d_))))); r3.addWidget(b_)
        r3.addStretch(1)
        v.addStretch(1); self.load()
        self.tray.toggled.connect(lambda on: ENG.cfg.set('close_to_tray', bool(on))); self.cover.toggled.connect(lambda on: ENG.cfg.set('cover_on_start', bool(on)))
        self.restore.toggled.connect(lambda on: ENG.cfg.set('cover_on_restore', bool(on))); self.idle.valueChanged.connect(lambda x: ENG.cfg.set('cover_idle_min', int(x)))
        self.autor.toggled.connect(lambda on: ENG.cfg.set('auto_restart', bool(on))); self.frz.valueChanged.connect(lambda x: ENG.cfg.set('freeze_log_s', float(x)))

    def load(self):
        for w_, val in ((self.tray, bool(ENG.cfg.get('close_to_tray'))), (self.cover, ENG.cfg.get('cover_on_start') is not False), (self.restore, bool(ENG.cfg.get('cover_on_restore'))),
                        (self.idle, int(ENG.cfg.get('cover_idle_min') or 0)), (self.autor, ENG.cfg.get('auto_restart') is not False), (self.frz, int(float(ENG.cfg.get('freeze_log_s') or 2)))):
            w_.blockSignals(True); (w_.setChecked(val) if isinstance(w_, QCheckBox) else w_.setValue(val)); w_.blockSignals(False)

    # ---------- 📱 手機網頁
    def _web_box(self, v):
        g = QGroupBox('📱 手機網頁（用手機遙控，透過 Tailscale）'); f = QFormLayout(g); v.addWidget(g)
        self.web_on = QCheckBox('開啟手機網頁'); self.web_port = QSpinBox(); self.web_port.setRange(1025, 64000); self.web_port.setValue(int(ENG.cfg.get('web_port') or BRAND['web_port']))
        self.web_hp = QLabel(''); self.web_hp.setObjectName('muted'); rp = QHBoxLayout(); rp.addWidget(self.web_port); rp.addWidget(self.web_hp, 1)
        self.web_pin = QLineEdit(); self.web_pin.setMaxLength(20); self.web_pin.setPlaceholderText('自己設 PIN：4～20 個字，數字、英文都可以，不能有空白')
        self.web_pin_l = QLabel(''); rpin = QHBoxLayout(); rpin.addWidget(self.web_pin, 1); rpin.addWidget(self.web_pin_l)
        self.web_lan = QCheckBox('也允許用 Tailscale IP／區網直接連 http（不能安裝成 App；不建議）')
        rb = QHBoxLayout(); b_app = QPushButton('📱 手機 App（Tailscale HTTPS）'); b_app.setObjectName('start'); b_copy = QPushButton('🔗 複製網址'); b_off = QPushButton('關掉 Tailscale 上的這個埠'); b_out = QPushButton('登出所有手機')
        for b_ in (b_app, b_copy, b_off, b_out): rb.addWidget(b_)
        rb.addStretch(1); self.web_st = QLabel(''); self.web_st.setWordWrap(True); self.web_st.setTextFormat(Qt.RichText); self.web_st.setTextInteractionFlags(Qt.TextSelectableByMouse)
        f.addRow(self.web_on); f.addRow('本機埠', rp); f.addRow('PIN', rpin); f.addRow(self.web_lan); f.addRow(rb); f.addRow(self.web_st)
        f.addRow(note('跟你的其他程式錯開、不會互相蓋掉：每個程式在 Tailscale 上用自己的 HTTPS 埠＝本機埠 + 1000（TikLive 用 443、SortCut 9461…）。'
                      '只設定／關掉自己的埠，不碰別人的、不會 reset。每個程式的本機埠也要不一樣（brand.json 的 web_port）。'))
        self.web_on.setChecked(bool(ENG.cfg.get('web_on'))); self.web_lan.setChecked(bool(ENG.cfg.get('web_lan'))); self._pin_label()
        self.web_on.toggled.connect(lambda on: (ENG.cfg.set('web_on', bool(on)), web_apply(), self._web_status()))
        self.web_lan.toggled.connect(lambda on: (ENG.cfg.set('web_lan', bool(on)), web_apply(), self._web_status()))
        self.web_port.editingFinished.connect(self._port_changed); self.web_pin.editingFinished.connect(self._pin_save)
        b_app.clicked.connect(self._web_app); b_copy.clicked.connect(self._web_copy); b_off.clicked.connect(self._web_off)
        b_out.clicked.connect(lambda: (ENG.cfg.set('web_tokens', []), self.win.msg('所有手機都登出了，下次要重新輸入 PIN')))
        self._ts = {}; self._web_status(True)

    def _pin_label(self): self.web_pin_l.setText('🔒 已設定' if ENG.cfg.get('web_pin_hash') else '<span style="color:#ffb02e">還沒設 PIN</span>')

    def _pin_save(self):
        pin = self.web_pin.text().strip()
        if not pin: return
        if not web.pin_ok_format(pin): self.web_pin_l.setText('<span style="color:#ff5d6c">4～20 個字、不能有空白</span>'); return
        salt = web.rand_hex(8); ENG.cfg.set('web_pin_salt', salt); ENG.cfg.set('web_pin_hash', web.pin_hash(pin, salt)); self.web_pin.clear(); self.web_pin_l.setText('✔ 已儲存')

    def _port_changed(self):
        old = int(ENG.cfg.get('web_port') or BRAND['web_port']); new = int(self.web_port.value())
        if new == old: return
        ENG.cfg.set('web_port', new); was = self._ts.get('serving'); web_apply()
        if was: bg(lambda: (web.tailscale_serve_off(old), web.tailscale_serve_on(new)), lambda _r: self._web_status(True))
        self._web_status()

    def _web_status(self, ts=False):
        port = int(ENG.cfg.get('web_port') or BRAND['web_port']); self.web_hp.setText(f'→ Tailscale HTTPS 用 :{web.https_port(port)}')
        s = web_server(create=False); T = self._ts
        st = ('✔ 手機網頁開著：127.0.0.1:' + str(port) if s is not None and s.running else ('⚠ ' + s.err if s is not None and s.err else '手機網頁關著'))
        if T.get('installed') is False: st += '<br>Tailscale：這台電腦還沒裝（tailscale.com 下載，登入同一個帳號）'
        elif T.get('url'): st += f'<br>📱 手機 App 網址：<b>{esc_html(T["url"])}</b>' + ('　✔ Tailscale 已設定' if T.get('serving') else '　（還沒設定 → 按「📱 手機 App」）')
        if T.get('others'): st += f'<br><small>Tailscale 上其他程式用的 HTTPS 埠：{"、".join(T["others"])}（不會動它們）</small>'
        self.web_st.setText(st)
        if ts: bg(lambda: web.tailscale_info(port), lambda r: (setattr(self, '_ts', r), self._web_status()))

    def _web_app(self):
        if not web.tailscale_exe(): QMessageBox.information(self, '手機 App', '這台電腦還沒偵測到 Tailscale：\n\n1. 到 tailscale.com 下載 Windows 版安裝\n2. 右下角 Tailscale 圖示 → Log in\n3. 手機裝 Tailscale、登入同一個帳號'); return
        if not ENG.cfg.get('web_pin_hash'): QMessageBox.information(self, '手機 App', '先在上面設一個 PIN'); return
        if not ENG.cfg.get('web_on'): self.web_on.setChecked(True)
        port = int(ENG.cfg.get('web_port') or BRAND['web_port']); self.win.msg('設定 Tailscale HTTPS 中…（第一次可能要 10～30 秒）', 30000)
        bg(lambda: (web.tailscale_serve_on(port), web.tailscale_info(port)), self._web_app_done)

    def _web_app_done(self, r):
        (rc, out), T = r; self._ts = T; self._web_status(); ENG.log.w(f'手機網頁：tailscale serve → {rc}：{(out or "")[-400:]}')
        m = re.search(r'https://login\.tailscale\.com/\S+', out or '')
        if m: QDesktopServices.openUrl(QUrl(m.group(0))); QMessageBox.information(self, '手機 App', 'Tailscale 要你先在網頁上同意開啟 HTTPS（已經幫你打開），按完再按一次「📱 手機 App」'); return
        if not T.get('serving'): QMessageBox.warning(self, '手機 App', f'Tailscale 設定沒成功：\n{(out or "")[-600:]}\n\n常見原因：Tailscale 還沒登入、管理後台沒開 HTTPS（DNS → Enable HTTPS）。'); return
        QApplication.clipboard().setText(T['url'])
        QMessageBox.information(self, '手機 App', f'好了！網址已複製：\n\n{T["url"]}\n\n用手機（Tailscale 開著）打開 → 輸入 PIN → Chrome 右上「⋮」→「安裝應用程式」。')

    def _web_copy(self):
        u = self._ts.get('url')
        if not u: self._web_status(True); self.win.msg('還沒拿到 Tailscale 網址（先按「📱 手機 App」）'); return
        QApplication.clipboard().setText(u); self.win.msg(f'已複製：{u}')

    def _web_off(self):
        port = int(ENG.cfg.get('web_port') or BRAND['web_port'])
        if QMessageBox.question(self, 'Tailscale', f'把 Tailscale 上的 :{web.https_port(port)} 關掉？（只關這個程式自己的）') != QMessageBox.Yes: return
        bg(lambda: web.tailscale_serve_off(port), lambda r: (self._web_status(True), self.win.msg('已關掉 Tailscale 上這個程式的埠')))


# ============================================================ 📜 LOG
class LogPage(QWidget):
    FILES = ('app_log.txt', 'error_log.txt', 'ui_freeze_log.txt', 'update_log.txt', 'crash_dump.txt', 'qt_log.txt')

    def __init__(self, win):
        super().__init__(); self.win = win
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10); r = QHBoxLayout(); v.addLayout(r)
        self.f = QComboBox(); self.f.addItems(self.FILES); b1 = QPushButton('🔄 重新讀'); b2 = QPushButton('📦 匯出最近 7 天（給 AI 看）'); b3 = QPushButton('📂 開 LOG 資料夾')
        for w_ in (self.f, b1, b2, b3): r.addWidget(w_)
        r.addStretch(1); self.tx = QPlainTextEdit(); self.tx.setReadOnly(True); self.tx.setLineWrapMode(QPlainTextEdit.NoWrap); v.addWidget(self.tx, 1)
        self.f.currentIndexChanged.connect(lambda _i: self.load()); b1.clicked.connect(self.load)
        b3.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ENG.log.d))))
        b2.clicked.connect(self._export)

    def showEvent(self, e):
        super().showEvent(e); self.load()

    def load(self):
        p = ENG.log.d / self.f.currentText()
        def rd():
            try:
                sz = p.stat().st_size
                with open(p, 'rb') as fh: fh.seek(max(0, sz - 400000)); return fh.read().decode('utf-8', 'replace')
            except Exception: return '（還沒有這個檔）'
        bg(rd, lambda t: (self.tx.setPlainText(t), self.tx.verticalScrollBar().setValue(self.tx.verticalScrollBar().maximum())))

    def _export(self):
        out, _ = QFileDialog.getSaveFileName(self, '匯出 LOG', str(Path.home() / 'Desktop' / f'{BRAND["id"]}_LOG_{time.strftime("%Y%m%d_%H%M")}.zip'), 'ZIP (*.zip)')
        if out: bg(lambda: ENG.log.export(out, 7), lambda n: self.win.msg(f'匯出好了：{n} 個檔 → {out}'))


# ============================================================ 🧪 實驗工作區
class LabPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.cbs = {}
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        t = QLabel('🧪 實驗工作區'); t.setObjectName('title'); v.addWidget(t)
        v.addWidget(note('新推薦的功能先放這裡（預設關）。試過覺得好，再說「變成正式功能」。程式裡用 lab_cfg().get("代號") 判斷有沒有打開。'))
        g = QGroupBox('開關'); self.fl = QVBoxLayout(g); v.addWidget(g)
        for k, nm, desc in LAB_LIST:
            cb = QCheckBox(nm); cb.setToolTip(desc); self.fl.addWidget(cb); self.fl.addWidget(note(desc)); self.cbs[k] = cb
            cb.toggled.connect(lambda on, k=k: self._set(k, on))
        if not LAB_LIST: self.fl.addWidget(note('目前沒有實驗功能'))
        v.addStretch(1); self.load()

    def _set(self, k, on):
        L = lab_cfg(); L[k] = bool(on); ENG.cfg.set('lab', L); self.win.msg(f'🧪 {k}：{"開" if on else "關"}')

    def load(self):
        L = lab_cfg()
        for k, cb in self.cbs.items(): cb.blockSignals(True); cb.setChecked(bool(L.get(k))); cb.blockSignals(False)


# ============================================================ 📖 使用說明
class HelpPage(QWidget):
    def __init__(self, win):
        super().__init__(); v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10); tx = QTextBrowser(); v.addWidget(tx, 1)
        tx.setHtml(f"""<h2>📖 {esc_html(APP_TITLE)}</h2>
<h3>🧭 四萬多部影片、七萬多組重複：建議順序</h3>
<p>最簡單：左邊第一個「🚀 整理精靈」——每一步還剩多少、做完打 ✔、一鍵去做。</p>
<ol><li><b>📈 資料分析 → 🩺 容量健康</b>：看重複、損毀各佔多少；按「📦 損毀的全部先隔離」（不是刪除，可以復原）。</li>
<li><b>🧭 重複資料夾最佳解</b>：整包被複製的資料夾一次處理（⚡ 整包複本全部照建議）；兩邊各有獨有的 🔀 合併；最上層像「硬碟直接複製過來」可以整個處理。剩下零散的到「🔁 重複檔」⚡ 全部照建議。</li>
<li><b>📦 資料夾包</b>：你以前整理過、有取名字的資料夾（例如「2020-日本旅遊」）整包看一眼 → ✅ 整包已篩選（保留資料夾、馬上搬），或 ▶ 一部一部審。</li>
<li><b>🎞 影片快速分類 → 🧩 相關的排一起</b>：選「同類型」或「同一段時間」，按「👀 整組一覽」（G）整組縮圖一次看，勾幾部先分到別類，剩下的整組分到同一類，自動開下一組；⏭ 下一組（]）。</li>
<li>篩選選「還沒分類・不在資料夾包裡」，剩下零散的一部一部看 16 格；看過留著就按「已篩選」。最後按「🚚 開始搬檔」（分類資料夾裡照原本的資料夾名放）。</li>
<li>只想標記、不想搬：「⚙ 管理分類」把「已篩選」設成「📌 不搬」。整包搬錯了：資料夾包「↶ 最近整包搬過」→「搬回原處」。</li></ol>
<h3>整理照片影片的步驟</h3>
<ol><li><b>🏠 總覽</b>：① 加入要整理的資料夾（例如 R:\\）→ ▶ 開始掃描。掃完會自動「比對重複」和「損毀檢查」（背景做，可以暫停）。</li>
<li>② 設定「重複時優先保留哪裡」：手機原始資料夾放最上面，「待整理」「備份」「一刻相冊下載」放下面。</li>
<li><b>🔁 重複檔</b>：內容一模一樣的檔案（跟檔名無關）一組一組列出來，⭐ 是建議保留的那份。確認幾組都對了，再用「⚡ 全部照建議處理」。</li>
<li><b>🩺 損毀檢查</b>：打不開／部分損毀／0 位元組。一張一張看：K 留著、D 搬到隔離區、→ 下一個、Enter 用預設程式打開（影片要看完整就按這個）。</li>
<li><b>🎞 影片快速分類</b>：一部影片平均切 16 格一次看完（有 SortCut 的「10 秒一張」預覽就直接用），按上面的分類按鈕（或鍵盤 1～9、0）先記下來、不搬檔；← → 換一部、Backspace 復原、Enter 播放。一個段落後按「🚚 開始搬檔」，搬錯了在「📦 隔離區」復原。</li>
<li><b>📈 資料分析</b>：所有檔案（不只照片影片）各佔多少、硬碟還剩多少、資料夾地圖（點進去看）、找到哪些遊戲／軟體。遊戲、軟體、程式專案是整包資料夾算一個，裡面的圖片不算照片。</li>
<li><b>📦 隔離區</b>：所有搬走的檔案都在每顆硬碟的「_FileCompare_待確認」裡，可以一個一個或全部復原。確定不要了，再自己刪那個資料夾。</li></ol>
<p>🔒 這個程式<b>不會刪任何檔案</b>，只會在同一顆硬碟裡搬（瞬間完成、不佔空間）。</p>
<p>「比對重複」只抓內容完全一樣的檔案。一刻相冊下載回來如果被重新壓縮過（檔案不一樣、看起來一樣），這一版還抓不到。</p>
<h3>其他</h3>
<ul><li>右上「📊 效能」：CPU／RAM／顯示卡浮窗（拖到你要的地方）；左下電腦狀態點一下也可以。</li>
<li>「🖥 後台」：每一項背景工作暫停／繼續／立刻停、先後順序；電腦太忙時自動讓路。</li>
<li>「🌙 縮到背景」：縮到右下角，背景繼續做。「🏠 封面」（Ctrl+L）：畫面上不留內容。</li>
<li>下方：深色／淺色、介面大小。</li>
<li>📱 手機：設定 → 手機網頁 → 打勾、設 PIN → 「📱 手機 App」，用手機打開網址、安裝成 App。</li>
<li>更新：把 {esc_html(BRAND['prefix'])}_V….zip 丟進 UPDATE 資料夾（上方會跳提示），或「⟳ 版本與更新」選它 → ⚡ 熱更新，程式不用關。</li>
<li>出問題：「📜 LOG」→「📦 匯出最近 7 天」，把 zip 傳給 AI。</li></ul>""")


# ============================================================ ⟳ 版本與更新（熱更新）
def vkey(v): return core.vkey(v)


def load_pkg(path):
    """讀更新包、檢查（只讀，不寫任何檔）：有 app/app.py、路徑安全、副檔名認得、每個 .py 都能編譯。回傳 {'path','files','version','notes','hot_ok'}."""
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        man = json.loads(zf.read('manifest.json').decode('utf-8-sig')) if 'manifest.json' in names else {}
        files = {m[4:]: zf.read(m) for m in names if m.startswith('app/') and not m.endswith('/')}
    if 'app.py' not in files: raise RuntimeError('這不是更新包（裡面沒有 app/app.py）')
    if man.get('app') and str(man['app']) != str(BRAND['id']): raise RuntimeError(f'這是別的程式（{man["app"]}）的更新包，不是 {BRAND["id"]} 的')
    for n in files:
        if '..' in Path(n).parts or Path(n).is_absolute() or '/' in n or '\\' in n: raise RuntimeError(f'更新包裡有不安全的路徑：{n}')
        if Path(n).suffix.lower() not in ('.py', '.json', '.md', '.txt', '.css', '.js', '.html', '.png', '.ico', '.svg'): raise RuntimeError(f'更新包裡有不認得的檔案：{n}')
    for n, data in files.items():
        if n.endswith('.py'):
            try: compile(data.decode('utf-8'), n, 'exec')
            except SyntaxError as ex: raise RuntimeError(f'{n} 第 {ex.lineno} 行有語法錯誤：{ex.msg}')
    if int(man.get('requires_launcher', 1)) > 1: raise RuntimeError('這個更新需要新的啟動器（EXE），請用完整安裝包（BUILD_AND_INSTALL.bat）更新')
    ver = str(man.get('version') or '')
    if not ver:
        m = re.search(r"APP_VERSION\s*=\s*'([^']+)'", files['app.py'].decode('utf-8', 'ignore')); ver = m.group(1) if m else '?'
    notes = []
    try:
        C = json.loads(files['fc_CHANGELOG.json'].decode('utf-8-sig')) if 'fc_CHANGELOG.json' in files else []
        notes = list((next((e for e in C if str(e.get('version')) == ver), None) or {}).get('items') or [])
    except Exception: pass
    return {'path': str(path), 'files': files, 'version': ver, 'notes': notes, 'hot_ok': b'def hot_start(' in files['app.py']}


def load_backup(d):
    """退回前一版：app_backup\\<時間>_before_hot_V… 裡是「更新之前」那一版的檔案 → 當成更新包."""
    d = Path(d); files = {}
    for f in d.iterdir():
        if f.is_file() and f.suffix.lower() in ('.py', '.json', '.md', '.txt', '.css', '.js', '.html', '.png', '.ico', '.svg'): files[f.name] = f.read_bytes()
    if 'app.py' not in files: raise RuntimeError('這個備份裡沒有 app.py')
    for n, data in files.items():
        if n.endswith('.py'): compile(data.decode('utf-8'), n, 'exec')
    m = re.search(r"APP_VERSION\s*=\s*'([^']+)'", files['app.py'].decode('utf-8', 'ignore')); ver = m.group(1) if m else '?'
    notes = []
    try: notes = list((next((e for e in json.loads(files['fc_CHANGELOG.json'].decode('utf-8-sig')) if str(e.get('version')) == ver), None) or {}).get('items') or [])
    except Exception: pass
    return {'path': str(d), 'files': files, 'version': ver, 'notes': notes, 'hot_ok': b'def hot_start(' in files['app.py']}


DL_RE = re.compile(r'^' + re.escape(BRAND['prefix']) + r'_V(\d+(?:\.\d+){1,3})(?:_Update)?(?:\s*\(\d+\))?\.zip$', re.I)


def upd_dirs():
    """去哪裡找新的更新包：UPDATE 資料夾、這台電腦的「下載」（跟 TikLive／SortCut 一樣）."""
    L = [ROOT / 'UPDATE']; dl = str(ENG.cfg.get('upd_dl_dir') or '') if ENG else ''
    L.append(Path(dl) if dl else Path(os.path.expanduser('~')) / 'Downloads'); return L


def upd_scan():
    """找比現在新的更新包（只列資料夾、不打開檔案）：回傳 {'ver','name','path','size','mtime'} 或 None."""
    best = None; cur = vkey(APP_VERSION)
    for d in upd_dirs():
        try:
            with os.scandir(d) as it:
                for e in it:
                    m = DL_RE.match(e.name)
                    if not m or not e.is_file(): continue
                    v = vkey(m.group(1))
                    if v <= cur: continue
                    st = e.stat()
                    if best is None or v > best[0] or (v == best[0] and st.st_mtime > best[1]['mtime']): best = (v, {'ver': m.group(1), 'name': e.name, 'path': e.path, 'size': st.st_size, 'mtime': st.st_mtime})
        except OSError: pass
    return best[1] if best else None


def upd_log(msg):
    try:
        (ROOT / 'LOG').mkdir(exist_ok=True)
        with open(ROOT / 'LOG' / 'update_log.txt', 'a', encoding='utf-8') as fh: fh.write(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}\n')
    except Exception: pass
    try: ENG.log.w('更新：' + msg.splitlines()[0][:300])
    except Exception: pass


def hot_update(win, pkg):
    """熱更新：寫入新程式 → 用全新的模組建新引擎、新視窗 → 交接 → 收掉舊視窗。背景工作不停、程式不關。
    任何一步失敗：檔案還原、模組還原，舊視窗照常用（更新包留在 UPDATE，下次開程式時再試）。回傳 True／False."""
    global LAST_UPD_ERR
    code = HERE; ver = pkg['version']; t0 = time.time(); name = ''; LAST_UPD_ERR = ''
    upd_log(f'熱更新開始：V{APP_VERSION} → V{ver}（{Path(pkg["path"]).name}）')
    backup = ROOT / 'app_backup' / f'{time.strftime("%Y%m%d_%H%M%S")}_before_hot_V{ver}'
    try:
        shutil.copytree(code, backup, ignore=shutil.ignore_patterns('__pycache__'))
        for n, data in pkg['files'].items():
            dst = code / n; tmp = dst.with_name(dst.name + '.new'); tmp.write_bytes(data); os.replace(str(tmp), str(dst))
        shutil.rmtree(code / '__pycache__', ignore_errors=True)
    except Exception as ex:
        _restore_files(backup); upd_log(f'熱更新失敗（寫檔）：{ex}\n{traceback.format_exc()}')
        _upd_fail(win, '更新失敗', f'寫入新程式失敗，已還原，程式照常使用：\n{ex}', ex); return False
    mods = sorted({p.stem for p in code.glob('*.py')} - {'app'}); saved = {m: sys.modules.get(m) for m in mods}; new_eng = None
    try:
        for m in mods: sys.modules.pop(m, None)
        importlib.invalidate_caches()
        name = f'app_hot_{int(time.time() * 1000)}'
        spec = importlib.util.spec_from_file_location(name, str(code / 'app.py')); mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod
        spec.loader.exec_module(mod)
        if not hasattr(mod, 'hot_start'): raise RuntimeError('這個版本不支援熱更新')
        state = win.export_state(); state.update(hot_from=APP_VERSION, hot_to=ver, hot_notes=pkg.get('notes') or [])
        new_win, new_eng = mod.hot_start(ENG, state)
    except Exception as ex:
        err = traceback.format_exc()
        if new_eng is not None:
            try: new_eng.discard()
            except Exception: pass
        for m, v in saved.items():
            if v is not None: sys.modules[m] = v
            else: sys.modules.pop(m, None)
        sys.modules.pop(name, None); _restore_files(backup)
        try:
            d = ROOT / 'UPDATE'; d.mkdir(exist_ok=True)
            if Path(pkg['path']).parent.resolve() != d.resolve(): shutil.copy2(pkg['path'], d / Path(pkg['path']).name)
        except Exception: pass
        upd_log(f'熱更新失敗（新版載入）：{ex}\n{err}')
        _upd_fail(win, '無法熱更新', f'新版沒辦法在執行中載入，已經還原成 V{APP_VERSION}，背景工作沒有受影響。\n\n更新包放在 UPDATE 資料夾：把程式關掉再打開就會套用（失敗會自動退回）。\n\n{ex}', ex, err)
        return False
    try: win.handoff()
    except Exception: upd_log('舊視窗交接時有錯誤（不影響新版）：\n' + traceback.format_exc())
    try: new_eng.start()
    except Exception: upd_log('新引擎啟動時有錯誤：\n' + traceback.format_exc())
    try: new_win.show_after_hot(state)
    except Exception: upd_log('新視窗顯示時有錯誤：\n' + traceback.format_exc()); new_win.show()
    app = QApplication.instance(); app._fc_main = new_win; app._fc_eng = new_eng
    try:
        p = Path(pkg['path']); d = ROOT / 'UPDATE'
        if p.parent.resolve() == d.resolve(): (d / 'applied').mkdir(exist_ok=True); os.replace(str(p), str(d / 'applied' / p.name))
    except Exception: pass
    upd_log(f'熱更新完成：V{APP_VERSION} → V{ver}，{time.time() - t0:.1f} 秒（備份 {backup.name}）')
    try: win.close(); win.deleteLater()
    except Exception: pass
    return True


LAST_UPD_ERR = ''


def _upd_fail(win, title, text, ex, err=''):
    """更新失敗：記下原因（手機的更新頁會顯示）、電腦跳不擋住的提示（手機按更新時不會卡在電腦的對話框）."""
    global LAST_UPD_ERR
    last = [x for x in (err or '').strip().splitlines() if x.strip()]
    LAST_UPD_ERR = f'{ex}' + (f'（{last[-1].strip()[:200]}）' if last and str(ex) not in last[-1] else '')
    try:
        mb = QMessageBox(win); mb.setIcon(QMessageBox.Warning); mb.setWindowTitle(title); mb.setText(text); mb.setModal(False); mb.show(); win._upd_mb = mb
    except Exception: pass


def _restore_files(backup):
    try:
        if backup and Path(backup).exists():
            keep = {f.name for f in Path(backup).iterdir() if f.is_file()}
            for f in Path(backup).iterdir():
                if f.is_file(): shutil.copy2(f, HERE / f.name)
            for f in HERE.iterdir():
                if f.is_file() and f.name not in keep and f.suffix in ('.py', '.json'):
                    try: f.unlink(); upd_log(f'還原：移除更新包新加的 {f.name}')
                    except Exception: pass
            shutil.rmtree(HERE / '__pycache__', ignore_errors=True)
    except Exception: upd_log('還原檔案失敗：\n' + traceback.format_exc())


class UpdPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.pkg = None
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        t = QLabel(f'⟳ 版本與更新　目前 V{APP_VERSION}'); t.setObjectName('title'); v.addWidget(t)
        v.addWidget(note(f'⚡ 熱更新：選更新包（{BRAND["prefix"]}_V….zip）、丟進 UPDATE 資料夾，或直接下載到這台電腦的「下載」資料夾（上面會跳提示、右下角也會提醒）→ 確認 → 程式不用關，畫面直接換成新版；背景工作不中斷。新版載入不了會自動還原。手機：設定 →「🆕 線上更新」也可以。'))
        g = QGroupBox('📦 更新包規則（給 AI／給你自己看）'); gl = QVBoxLayout(g); v.addWidget(g)
        gl.addWidget(note(f'檔名：{BRAND["prefix"]}_V0.1.01.zip（版本最後一段兩位數：0.1.01 → 0.1.02 … 0.1.99 → 0.2.01，不用 00）\n'
                          '內容：manifest.json（{"app": "' + BRAND['id'] + '", "version": "0.1.02", "requires_launcher": 1}）＋ app\\ 底下所有程式檔（app.py、core.py、web.py、webpage.py、brand.json、CHANGELOG.json…）\n'
                          '每一版：app.py 的 APP_VERSION 改成新版本、CHANGELOG.json 最上面加一筆（版本、日期、改了什麼）；用 tools\\pack.py 打包會自動檢查這些。\n'
                          '只有 app\\ 的檔會被換；Data\\（設定、資料庫）、LOG\\ 永遠不動。換 EXE（build\\launcher.py）才需要重新跑 BUILD_AND_INSTALL.bat。'))
        r = QHBoxLayout(); v.addLayout(r); b1 = QPushButton('📦 選更新包…'); self.b_go = QPushButton('⚡ 熱更新'); self.b_go.setEnabled(False); self.b_go.setObjectName('start')
        b3 = QPushButton('🔁 改用重開程式套用'); b2 = QPushButton('📂 開 UPDATE 資料夾')
        for w in (b1, self.b_go, b3, b2): r.addWidget(w)
        r.addStretch(1)
        self.info = QLabel('（還沒選更新包）'); self.info.setWordWrap(True); self.info.setTextFormat(Qt.RichText); v.addWidget(self.info)
        g2 = QGroupBox('↩ 退回前一版（每次更新前都會自動備份；退回時背景工作一樣不會中斷）'); g2l = QVBoxLayout(g2); v.addWidget(g2)
        self.rb = QTableWidget(0, 3); self.rb.setHorizontalHeaderLabels(['版本', '備份時間', '改了什麼']); self.rb.verticalHeader().setVisible(False)
        self.rb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.rb.setSelectionBehavior(QAbstractItemView.SelectRows); self.rb.horizontalHeader().setStretchLastSection(True)
        self.rb.setColumnWidth(0, 90); self.rb.setColumnWidth(1, 150); self.rb.setMaximumHeight(130); g2l.addWidget(self.rb)
        rr = QHBoxLayout(); g2l.addLayout(rr); brb = QPushButton('↩ 用選取的備份（先看內容，再按 ⚡ 熱更新）'); rr.addWidget(brb); rr.addStretch(1); brb.clicked.connect(self._rb_use)
        self.tx = QTextBrowser(); self.tx.setMinimumHeight(240); v.addWidget(self.tx, 1); self._cl(); self._rb_load()
        b1.clicked.connect(self.pick); self.b_go.clicked.connect(self.go); b3.clicked.connect(self.restart_way)
        b2.clicked.connect(lambda: (Path(ROOT / 'UPDATE').mkdir(exist_ok=True), QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT / 'UPDATE')))))

    def _cl(self):
        try: C = json.loads((HERE / 'fc_CHANGELOG.json').read_text(encoding='utf-8'))
        except Exception: C = []
        self.tx.setHtml(''.join(f"<h3>V{x.get('version')}　<small>{x.get('date', '')}</small></h3><ul>" + ''.join(f'<li>{esc_html(i)}</li>' for i in x.get('items') or []) + '</ul>' for x in C) or '（沒有更新紀錄）')

    def _rb_load(self):
        def look():
            L = []; seen = set()
            try: D = sorted([d for d in (ROOT / 'app_backup').iterdir() if d.is_dir()], key=lambda d: d.name, reverse=True)
            except OSError: D = []
            for d in D:
                try: pk = load_backup(d)
                except Exception: continue
                if pk['version'] in seen or pk['version'] == APP_VERSION: continue
                seen.add(pk['version']); L.append((str(d), pk['version'], d.name[:15], '；'.join(pk['notes'][:2])))
                if len(L) >= 3: break
            return L
        bg(look, self._rb_got)

    def _rb_got(self, L):
        self.rb_rows = L; self.rb.setRowCount(len(L))
        for i, (_d, ver, t, n) in enumerate(L):
            for j, val in enumerate((f'V{ver}', f'{t[:4]}-{t[4:6]}-{t[6:8]} {t[9:11]}:{t[11:13]}' if len(t) >= 13 else t, n)): self.rb.setItem(i, j, _ti(val))

    def _rb_use(self):
        i = self.rb.currentRow()
        if not (0 <= i < len(getattr(self, 'rb_rows', []))): self.win.msg('先選一個備份'); return
        try: pkg = load_backup(self.rb_rows[i][0])
        except Exception as ex: QMessageBox.warning(self, '退回', f'這個備份不能用：{ex}'); return
        self.pkg = pkg; d = vkey(pkg['version']); c = vkey(APP_VERSION); way = '⚠ 降版（退回舊版）' if d < c else '升級'
        self.info.setText(f'<b>備份 {esc_html(Path(pkg["path"]).name)}</b>　V{APP_VERSION} → <b>V{esc_html(pkg["version"])}</b>（{way}）<br>' + '<br>'.join('• ' + esc_html(x) for x in pkg['notes'][:8]))
        self.b_go.setEnabled(pkg['hot_ok'])

    def pick(self):
        p, _ = QFileDialog.getOpenFileName(self, '選更新包', str(Path.home() / 'Downloads'), f'更新包 ({PKG_GLOB} *.zip)')
        if p: self.load(p)

    def load(self, p):
        self.pkg = None; self.b_go.setEnabled(False)
        try: pkg = load_pkg(p)
        except Exception as ex:
            self.info.setText(f'<b>{esc_html(Path(p).name)}</b><br><span style="color:#ff6577">不能用這個更新包：{esc_html(ex)}</span>'); upd_log(f'更新包不能用：{p}：{ex}'); return False
        self.pkg = pkg; d = vkey(pkg['version']); c = vkey(APP_VERSION)
        way = '升級' if d > c else ('相同版本（重新套用）' if d == c else '⚠ 降版（退回舊版）')
        h = f'<b>{esc_html(Path(p).name)}</b>　V{APP_VERSION} → <b>V{esc_html(pkg["version"])}</b>（{way}）'
        if pkg['notes']: h += '<br>' + '<br>'.join('• ' + esc_html(x) for x in pkg['notes'])
        h += ('<br><span style="color:#45d483">可以熱更新：程式不用關。</span>' if pkg['hot_ok'] else '<br><span style="color:#f0ad4e">這個版本不支援熱更新，要用「🔁 改用重開程式套用」。</span>')
        self.info.setText(h); self.b_go.setEnabled(pkg['hot_ok']); upd_log(f'選了更新包：{p}（V{pkg["version"]}，{way}）'); return True

    def go(self, confirm=True):
        if not self.pkg: return
        busy = sum(ENG.bg_running(k) for k, _i, _n in ENG.BG_KINDS)
        if confirm and QMessageBox.question(self, '熱更新', f'從 V{APP_VERSION} 更新到 V{self.pkg["version"]}？\n\n程式不用關；' + (f'正在做的 {busy} 個工作不會中斷（做完由新版接手）。' if busy else '')) != QMessageBox.Yes: return
        hot_update(self.win, self.pkg)

    def restart_way(self):
        if not self.pkg: self.win.msg('先選更新包'); return
        try:
            d = ROOT / 'UPDATE'; d.mkdir(exist_ok=True)
            if Path(self.pkg['path']).parent.resolve() != d.resolve(): shutil.copy2(self.pkg['path'], d / Path(self.pkg['path']).name)
        except Exception as ex: QMessageBox.warning(self, '更新', str(ex)); return
        if QMessageBox.question(self, '更新', '更新包放好了。現在重新開程式套用？') == QMessageBox.Yes: self.win.restart()


# ============================================================ 📊 效能浮窗、左邊選單、左下電腦狀態、封面
class PerfFloat(QWidget):
    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint); self.setAttribute(Qt.WA_TranslucentBackground); self.resize(250, 150); self.drag = None
        self.tm = QTimer(self); self.tm.timeout.connect(self._tick); self.tm.start(1000)

    def _tick(self):
        h = 8 + 20 * (6 if ENG.perf.gpu else 2) + (22 if ENG.perf.gpu else 2)
        if self.height() != h: self.setFixedHeight(h)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.setBrush(QColor(12, 15, 20, 225)); p.setPen(QColor('#2f3a4a')); p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 10, 10)
        P = ENG.perf; g = P.gpu or {}
        rows = [('CPU', P.cpu, '#4dc9ff', P.H['cpu']), ('RAM', P.ram, '#b48cff', P.H['ram'])]
        if g: rows += [('GPU', g.get('util'), '#45d483', P.H['gpu']), ('壓縮', g.get('enc'), '#f0ad4e', P.H['enc']), ('解碼', g.get('dec'), '#ff6577', P.H['dec']),
                       ('VRAM', 100 * g['mem'] / g['mem_t'] if g.get('mem_t') else None, '#9aa5b3', P.H['vram'])]
        f = QFont(); f.setPixelSize(11); p.setFont(f); y = 8
        for nm, val, col, H in rows:
            p.setPen(QColor('#cfd6e0')); p.drawText(QRect(10, y, 40, 16), Qt.AlignLeft | Qt.AlignVCenter, nm)
            bx = QRect(52, y + 3, 120, 10); p.setPen(Qt.NoPen); p.setBrush(QColor('#1d2430')); p.drawRoundedRect(bx, 4, 4)
            if val is not None: p.setBrush(QColor(col)); p.drawRoundedRect(QRect(bx.x(), bx.y(), int(bx.width() * max(0, min(100, val)) / 100), bx.height()), 4, 4)
            pts = list(H)[-60:]
            if pts:
                p.setPen(QPen(QColor(col), 1)); x0 = 180; w = 60
                for i in range(1, len(pts)):
                    if pts[i] is None or pts[i - 1] is None: continue
                    p.drawLine(int(x0 + (i - 1) * w / 60), int(y + 14 - pts[i - 1] / 100 * 13), int(x0 + i * w / 60), int(y + 14 - pts[i] / 100 * 13))
            p.setPen(QColor('#ffffff')); p.drawText(QRect(52, y, 120, 16), Qt.AlignCenter, '—' if val is None else f'{val:.0f}%'); y += 20
        if g: p.setPen(QColor('#8a96a8')); p.drawText(QRect(10, y, 230, 16), Qt.AlignLeft, f"{g.get('name', '')[:22]} {g.get('temp', 0):.0f}°C")
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self.drag is not None: self.move(e.globalPosition().toPoint() - self.drag)

    def mouseReleaseEvent(self, e):
        self.drag = None
        try: ENG.cfg.set('perf_pos', [self.x(), self.y()])
        except Exception: pass


class NavDelegate(QStyledItemDelegate):
    """側邊選單：分組標題（彩色小字＋細線，點了收合）和選項（圖示欄＋選到時左邊彩色條）."""
    def sizeHint(self, option, index):
        h = QFontMetrics(option.font).height(); return QSize(option.rect.width(), (h + 9) if index.data(Qt.UserRole + 2) == 'header' else (h + 12))

    def paint(self, painter, option, index):
        painter.save(); painter.setRenderHint(QPainter.Antialiasing)
        kind = index.data(Qt.UserRole + 2); text = str(index.data(Qt.DisplayRole) or ''); color = QColor(str(index.data(Qt.UserRole + 1) or '#4dc9ff')); r = option.rect
        if kind == 'header':
            f = QFont(option.font); f.setBold(True); px = option.font.pixelSize()
            if px > 0: f.setPixelSize(max(9, round(px * 0.82)))
            else: f.setPointSizeF(max(7.0, f.pointSizeF() * 0.82))
            painter.setFont(f); fm = QFontMetrics(f); y = r.bottom() - 6
            painter.setPen(color); painter.drawText(QRectF(r.left() + 10, r.top(), r.width() - 14, r.height() - 4), Qt.AlignLeft | Qt.AlignBottom, text)
            x0 = r.left() + 14 + fm.horizontalAdvance(text)
            if x0 < r.right() - 8:
                c = QColor(color); c.setAlpha(70); painter.setPen(QPen(c, 1)); painter.drawLine(int(x0), int(y - fm.height() / 2 + 3), int(r.right() - 8), int(y - fm.height() / 2 + 3))
        else:
            selected = bool(option.state & QStyle.State_Selected); hover = bool(option.state & QStyle.State_MouseOver)
            box = QRectF(r.left() + 4, r.top() + 2, r.width() - 8, r.height() - 4)
            if selected:
                bgc = QColor(color); bgc.setAlpha(38); painter.setPen(Qt.NoPen); painter.setBrush(bgc); painter.drawRoundedRect(box, 7, 7)
                painter.setBrush(color); painter.drawRoundedRect(QRectF(box.left(), box.top() + 5, 3.5, box.height() - 10), 2, 2)
            elif hover: painter.setPen(Qt.NoPen); painter.setBrush(TC('hover')); painter.drawRoundedRect(box, 7, 7)
            f = QFont(option.font); f.setBold(selected); painter.setFont(f)
            icon = str(index.data(Qt.UserRole + 3) or ''); badge = str(index.data(Qt.UserRole + 4) or '')
            painter.setPen(color if selected else TC('muted')); painter.drawText(QRectF(box.left() + 10, box.top(), 22, box.height()), Qt.AlignCenter, icon)
            painter.setPen(TC('text_strong') if selected else (TC('text') if hover else TC('nav_text')))
            painter.drawText(QRectF(box.left() + 38, box.top(), box.width() - 42, box.height()), Qt.AlignLeft | Qt.AlignVCenter, text)
            if badge:
                fb = QFont(option.font); fb.setBold(True); painter.setFont(fb); fmb = QFontMetrics(fb)
                bw = fmb.horizontalAdvance(badge) + 12; br = QRectF(box.right() - bw - 6, box.center().y() - 8, bw, 16)
                c = QColor(color); c.setAlpha(60); painter.setPen(Qt.NoPen); painter.setBrush(c); painter.drawRoundedRect(br, 8, 8)
                painter.setPen(TC('text_strong')); painter.drawText(br, Qt.AlignCenter, badge)
        painter.restore()


class NavList(QListWidget):
    """左邊選單。GROUPS：(分組名稱, 顏色, [(頁碼, 名稱, 圖示)])。頁碼＝Main.PAGES 的位置。對外 setCurrentRow(頁)、currentRow() 都用頁碼."""
    GROUPS = [('總覽', '#4dc9ff', [(0, '總覽', '🏠'), (11, '資料分析', '📈'), (1, '後台狀態', '🖥')]),
              ('整理照片影片', '#f0ad4e', [(26, '整理精靈', '🚀'), (12, '影片快速分類', '🎞'), (24, '資料夾包', '📦'), (25, '重複資料夾最佳解', '🧭'), (2, '重複檔', '🔁'), (17, '重複資料夾', '📁'), (3, '損毀檢查', '🩺'), (10, '搜尋篩選', '🔎'), (4, '隔離區', '📦'), (13, '雜物清理', '🧹'), (14, '相似／連拍', '🖼'), (15, '依日期整理', '📅'), (16, '時間軸', '🗓'), (18, '照片地圖', '🗺'), (19, '影片瘦身', '🗜'), (20, '備份檢查', '💾'), (21, '活動', '🧳'), (23, '最愛', '⭐')]),
              ('電腦與檔案', '#45d483', [(5, '🧪 實驗工作區', '🧪'), (6, 'LOG', '📜'), (22, '操作紀錄', '🧾')]),
              ('設定', '#9aa5b3', [(7, '設定', '⚙'), (8, '版本與更新', '⟳'), (9, '使用說明', '📖')])]
    NAMES = {pg: (ic, nm) for _g, _c, L in GROUPS for pg, nm, ic in L}

    def __init__(self, on_page):
        super().__init__(); self.on_page = on_page; self._page = -1; self._items = {}; self._groups = []
        self.setObjectName('workspace_nav'); self.setItemDelegate(NavDelegate(self)); self.setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel); self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for gname, col, L in self.GROUPS:
            h = QListWidgetItem(gname); h.setFlags(Qt.ItemIsEnabled); h.setData(Qt.UserRole, -1); h.setData(Qt.UserRole + 1, col); h.setData(Qt.UserRole + 2, 'header'); self.addItem(h)
            its = []
            for pg, nm, ic in L:
                it = QListWidgetItem(nm); it.setData(Qt.UserRole, pg); it.setData(Qt.UserRole + 1, col); it.setData(Qt.UserRole + 2, 'item'); it.setData(Qt.UserRole + 3, ic)
                it.setToolTip(nm); self.addItem(it); self._items[pg] = it; its.append(it)
            self._groups.append((h, gname, its))
        self.currentRowChanged.connect(self._row_changed); self.itemClicked.connect(self._clicked)
        QTimer.singleShot(0, self.apply_collapse)

    def page_name(self, pg): return self.NAMES.get(int(pg), ('', ''))[1]

    def page_icon(self, pg): return self.NAMES.get(int(pg), ('', ''))[0]

    def _row_changed(self, row):
        try: it = self.item(row); pg = int(it.data(Qt.UserRole)) if it is not None else -1
        except Exception: return
        if pg >= 0 and pg != self._page: self._page = pg; self.on_page(pg)

    def setCurrentRow(self, pg, *a):
        pg = int(pg); it = self._items.get(pg)
        if it is None: return
        try: super().setCurrentItem(it)
        except Exception: pass
        if pg != self._page: self._page = pg; self.on_page(pg)
        self.apply_collapse()

    def currentRow(self): return self._page

    def set_badge(self, pg, txt):
        if EMBED['on'] and EMBED.get('badge'):                                  # 嵌在 SortCut 裡：數字也掛到 SortCut 左邊選單那一項
            try: EMBED['badge'](int(pg), str(txt or ''))
            except Exception: pass
        it = self._items.get(int(pg))
        if it is not None and str(it.data(Qt.UserRole + 4) or '') != str(txt or ''): it.setData(Qt.UserRole + 4, str(txt or ''))

    def _shut(self):
        v = ENG.cfg.get('nav_shut'); return set(v) if isinstance(v, list) else set()

    def apply_collapse(self):
        try:
            shut = self._shut(); cur = self._items.get(self._page)
            for h, nm, its in self._groups:
                off = nm in shut and cur not in its
                for it in its: it.setHidden(off)
                h.setText(nm + ('　▸ ' + str(len(its)) if off else ''))
        except Exception: pass

    def _clicked(self, item):
        try:
            if item is None or int(item.data(Qt.UserRole)) >= 0: return
            nm = item.text().split('　')[0]; shut = self._shut(); shut.symmetric_difference_update({nm}); ENG.cfg.set('nav_shut', sorted(shut)); self.apply_collapse()
            cur = self._items.get(self._page)
            if cur is not None: QListWidget.setCurrentItem(self, cur)
        except Exception: pass


class SysPanel(QWidget):
    """左下角電腦狀態：每項一列（名稱、彩色進度條、數值、溫度），點一下開／關📊效能浮窗."""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent); self.rows = []; self.setCursor(Qt.PointingHandCursor); self.setMinimumHeight(40)

    def set_rows(self, rows):
        if rows != self.rows: self.rows = rows; self.setFixedHeight(10 + 19 * max(1, len(rows))); self.update()

    def mousePressEvent(self, e): self.clicked.emit()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True); W = self.width()
        p.setPen(QPen(TC('border'), 1)); p.setBrush(TC('card')); p.drawRoundedRect(QRectF(0.5, 0.5, W - 1, self.height() - 1), 9, 9)
        f = QFont(self.font()); f.setPointSizeF(8.2); fb = QFont(f); fb.setBold(True)
        lw, vw, tw = 40, 46, 30; bx = 8 + lw; bw = max(20, W - 8 - lw - vw - tw - 10)
        if not self.rows: p.setPen(TC('subtext')); p.drawText(self.rect(), Qt.AlignCenter, '電腦狀態讀取中…'); p.end(); return
        for i, (lab, pct, val, temp, col) in enumerate(self.rows):
            y = 5 + i * 19; cy = y + 9.5
            p.setFont(fb); p.setPen(TC('subtext')); p.drawText(QRectF(8, y, lw, 19), Qt.AlignLeft | Qt.AlignVCenter, lab)
            if pct is not None:
                p.setPen(Qt.NoPen); p.setBrush(TC('track')); p.drawRoundedRect(QRectF(bx, cy - 3, bw, 6), 3, 3)
                p.setBrush(QColor(col)); p.drawRoundedRect(QRectF(bx, cy - 3, max(3.0, bw * min(100.0, max(0.0, pct)) / 100.0), 6), 3, 3)
            p.setPen(TC('text_strong')); p.drawText(QRectF(bx + bw + 4, y, vw, 19), Qt.AlignRight | Qt.AlignVCenter, val)
            if temp:
                p.setPen(QColor('#ff5c5c' if temp >= 85 else '#f0ad4e' if temp >= 70 else '#45d483')); p.setFont(f)
                p.drawText(QRectF(W - 8 - tw, y, tw, 19), Qt.AlignRight | Qt.AlignVCenter, f'{temp:.0f}°')
        p.end()


class CoverPage(QWidget):
    """開機封面：不露出任何內容；你按了才進去（Ctrl+L 或上方🏠封面隨時回來）。COVER_BTNS＝(頁碼, 圖示, 名稱, 說明)."""
    COVER_BTNS = [(0, '🏠', '總覽', '資料夾、進度'), (2, '🔁', '重複檔', '選要保留哪一份'), (3, '🩺', '損毀檢查', '一個一個看'), (10, '🔎', '搜尋篩選', '日期、來源、相機'), (4, '📦', '隔離區', '可以復原'),
                  (1, '🖥', '後台', '背景工作'), (7, '⚙', '設定', '手機網頁、一般'), (8, '⟳', '版本與更新', '熱更新')]

    def __init__(self, win):
        super().__init__(); self.win = win; self.t0 = time.time()
        v = QVBoxLayout(self); v.setContentsMargins(40, 0, 40, 24); v.addStretch(5)
        self.resume = QPushButton(''); self.resume.setMinimumHeight(48)
        self.resume.setStyleSheet('QPushButton{background:rgba(77,201,255,0.18);border:1px solid #4dc9ff;border-radius:24px;font-size:16px;font-weight:700;padding:8px 28px;color:#ffffff}QPushButton:hover{background:rgba(77,201,255,0.32)}')
        rr = QHBoxLayout(); rr.addStretch(1); rr.addWidget(self.resume); rr.addStretch(1); v.addLayout(rr); v.addSpacing(22)
        grid = QGridLayout(); grid.setHorizontalSpacing(14); grid.setVerticalSpacing(14)
        for k, (page, ic, nm, sub) in enumerate(self.COVER_BTNS):
            b = QPushButton(f'{ic}\n{nm}' + (f'\n{sub}' if sub else '')); b.setMinimumSize(190, 96)
            b.setStyleSheet('QPushButton{background:rgba(20,28,40,0.72);border:1px solid rgba(120,160,210,0.35);border-radius:16px;font-size:13px;color:#dfe9f5;padding:10px}QPushButton:hover{background:rgba(40,60,90,0.85);border-color:#4dc9ff;color:#ffffff}')
            b.clicked.connect(lambda _c=False, page=page: self.win.enter(page)); grid.addWidget(b, k // 4, k % 4)
        gw = QWidget(); gw.setLayout(grid); gw.setStyleSheet('background:transparent'); gr = QHBoxLayout(); gr.addStretch(1); gr.addWidget(gw); gr.addStretch(1); v.addLayout(gr)
        v.addStretch(3)
        self.hint = QLabel('Ctrl+L 或上方「🏠 封面」隨時回到這裡'); self.hint.setAlignment(Qt.AlignCenter); self.hint.setStyleSheet('QLabel{color:#4f6178;font-size:11px;background:transparent}'); v.addWidget(self.hint)
        self.resume.clicked.connect(lambda: self.win.enter(int(ENG.cfg.get('last_page') or 0)))
        self.tm = QTimer(self); self.tm.timeout.connect(lambda: self.update() if self.isVisible() else None); self.tm.start(1000)

    def showEvent(self, e):
        super().showEvent(e); self.refresh()

    def refresh(self):
        lp = int(ENG.cfg.get('last_page') or 0); self.resume.setText(f'↩  進入（上次停在：{NavList.NAMES.get(lp, ("", "首頁"))[1]}）'); self.resume.setFocus()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); W, H = self.width(), self.height()
        g = QLinearGradient(0, 0, W, H); g.setColorAt(0, QColor('#070b12')); g.setColorAt(0.55, QColor('#0f1a2b')); g.setColorAt(1, QColor('#1a1430')); p.fillRect(self.rect(), g)
        ph = (time.time() - self.t0) * 0.15
        for cx, cy, r, col in ((0.25 + 0.04 * math.sin(ph), 0.28, 0.55, QColor(77, 201, 255, 46)), (0.78, 0.7 + 0.04 * math.cos(ph * 1.3), 0.5, QColor(180, 140, 255, 40))):
            rg = QRadialGradient(W * cx, H * cy, max(W, H) * r); rg.setColorAt(0, col); rg.setColorAt(1, QColor(0, 0, 0, 0)); p.fillRect(self.rect(), rg)
        cy = H * 0.2; lw = 74; R = QRectF(W / 2 - lw / 2, cy - lw / 2, lw, lw); lg = QLinearGradient(R.topLeft(), R.bottomRight())
        lg.setColorAt(0, QColor(THEME['accent'])); lg.setColorAt(1, QColor('#8b6cff')); p.setBrush(lg); p.setPen(Qt.NoPen); p.drawRoundedRect(R, 20, 20)
        p.setBrush(QColor('#0b0e13')); p.drawEllipse(R.center(), 14, 14)
        f = QFont(); f.setPixelSize(48); f.setBold(True); p.setFont(f); p.setPen(QColor('#f2f6fb')); p.drawText(QRectF(0, cy + lw / 2 + 10, W, 62), Qt.AlignCenter, BRAND['name'])
        f2 = QFont(); f2.setPixelSize(15); p.setFont(f2); p.setPen(QColor('#8ea4bf')); p.drawText(QRectF(0, cy + lw / 2 + 72, W, 24), Qt.AlignCenter, f'{APP_TITLE}　·　V{APP_VERSION}')
        f3 = QFont(); f3.setPixelSize(13); p.setFont(f3); p.setPen(QColor('#9fb3c8')); wd = '一二三四五六日'[time.localtime().tm_wday]
        p.drawText(QRectF(0, 18, W - 28, 20), Qt.AlignRight | Qt.AlignVCenter, time.strftime('%Y-%m-%d') + f'（{wd}）　' + time.strftime('%H:%M'))
        p.end()


def app_icon():
    """app\\icon.ico（有的話）；沒有就自己畫一個."""
    for p_ in (HERE / 'icon.ico', ROOT / 'icon.ico', HERE / 'icon_512.png'):
        if p_.exists(): return QIcon(str(p_))
    pm = QPixmap(64, 64); pm.fill(Qt.transparent); p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(THEME['accent'])); p.setPen(Qt.NoPen); p.drawRoundedRect(4, 4, 56, 56, 14, 14); p.setBrush(QColor('#0b0e13')); p.drawEllipse(QPoint(32, 32), 11, 11); p.end()
    return QIcon(pm)


# ============================================================ 主視窗
class ErrPage(QWidget):
    """有一頁建不起來時的替代頁（其他頁照常用、更新不會因為一頁失敗而整個還原）."""
    def __init__(self, title, err):
        super().__init__(); v = QVBoxLayout(self); v.setContentsMargins(16, 16, 16, 16)
        t = QLabel(f'⚠ 「{title}」這一頁打不開'); t.setObjectName('title'); v.addWidget(t)
        v.addWidget(note('其他功能都可以照常用。請到「📜 LOG」→「📦 匯出最近 7 天」，把 zip 傳給 AI 修正。'))
        tx = QPlainTextEdit(err); tx.setReadOnly(True); v.addWidget(tx, 1)


class Main(QMainWindow):
    def __init__(self, adopt=None, embedded=False):
        self.embedded = bool(embedded)
        try:
            if not self.embedded: _set_qss(theme_qss(ENG.cfg.get('ui_theme') or 'dark', ENG.cfg.get('ui_zoom') or 100))
        except Exception: pass
        super().__init__(); self.setWindowTitle(f'{APP_TITLE}  V{APP_VERSION}'); self.resize(1400, 880); self.quitting = False; self._handoff = False; self._upd_seen = set()
        self.icon = app_icon(); self.setWindowIcon(self.icon)
        try: QApplication.instance().setWindowIcon(self.icon)
        except Exception: pass
        cw = QWidget(); self.setCentralWidget(cw); v = QVBoxLayout(cw); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        self.outer = QStackedWidget(); v.addWidget(self.outer, 1); self.mainw = QWidget(); mv = QVBoxLayout(self.mainw); mv.setContentsMargins(0, 0, 0, 0); mv.setSpacing(0)
        self._cover_ready = False
        split = QSplitter(Qt.Horizontal); split.setChildrenCollapsible(False); mv.addWidget(split, 1)
        side = QFrame(); side.setObjectName('side'); side.setMinimumWidth(180); side.setMaximumWidth(320); sl = QVBoxLayout(side); sl.setContentsMargins(10, 6, 10, 10); sl.setSpacing(5)
        self.nav = NavList(self._page); sl.addWidget(self.nav, 1)
        self.sys_panel = SysPanel(); self.sys_panel.setToolTip('電腦狀態：點一下打開／關掉「📊 效能」浮窗'); sl.addWidget(self.sys_panel)
        split.addWidget(side)
        content = QWidget(); cv_ = QVBoxLayout(content); cv_.setContentsMargins(0, 0, 0, 0); cv_.setSpacing(0)
        topf = QFrame(); topf.setObjectName('topbar'); top = QHBoxLayout(topf); top.setContentsMargins(12, 7, 10, 7); top.setSpacing(6); cv_.addWidget(topf)
        self.ptitle = QLabel(''); self.ptitle.setObjectName('ptitle'); top.addWidget(self.ptitle)
        self.stat = QLabel(''); self.stat.setObjectName('muted'); self.stat.setMinimumWidth(10); self.stat.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred); top.addWidget(self.stat, 1)
        self.b_perf = QPushButton('📊 效能'); self.b_perf.setCheckable(True); self.b_perf.setToolTip('電腦效能浮窗（左下角電腦狀態點一下也可以）')
        self.b_bg = QPushButton('🖥 後台'); self.b_hide = QPushButton('🌙 縮到背景'); self.b_hide.setToolTip('縮到右下角，背景繼續做')
        self.b_cover = QPushButton('🏠 封面'); self.b_cover.setToolTip('回到封面（Ctrl+L）：畫面上不留任何內容，背景照常做')
        for b_ in (self.b_perf, self.b_bg, self.b_hide, self.b_cover): b_.setObjectName('pill'); top.addWidget(b_)
        self.stack = QStackedWidget(); cv_.addWidget(self.stack, 1); split.addWidget(content); split.setStretchFactor(1, 1)
        try: split.setSizes([int(ENG.cfg.get('side_w') or 210), 1190])
        except Exception: pass
        self._sw_t = QTimer(self); self._sw_t.setSingleShot(True); self._sw_t.timeout.connect(lambda: ENG.cfg.set('side_w', int(split.sizes()[0])))
        split.splitterMoved.connect(lambda *_a: self._sw_t.start(600))
        # ---- 頁面（順序＝頁碼，NavList.GROUPS 用這個號碼）
        self.home = HomePage(self); self.bgp = BgPage(self); self.lab = LabPage(self); self.logp = LogPage(self); self.setp = SetPage(self); self.upd = UpdPage(self); self.helpp = HelpPage(self)
        _mk = self._mk_page
        self.dupp = _mk(DupPage); self.healthp = _mk(HealthPage); self.quarp = _mk(QuarPage); self.searchp = _mk(SearchPage); self.anap = _mk(AnaPage); self.vcp = _mk(VcPage); self.junkp = _mk(JunkPage); self.simp = _mk(SimPage); self.orgp = _mk(OrgPage); self.tlp = _mk(TlPage); self.ddp = _mk(DdirPage); self.geop = _mk(GeoPage); self.slimp = _mk(SlimPage); self.bakp = _mk(BakPage); self.evtp = _mk(EvtPage); self.opsp = _mk(OpsPage); self.favp = _mk(FavPage); self.pkp = _mk(PackPage); self.dplp = _mk(DupPlanPage); self.wizp = _mk(WizPage)
        self.PAGES = [self.home, self.bgp, self.dupp, self.healthp, self.quarp, self.lab, self.logp, self.setp, self.upd, self.helpp, self.searchp, self.anap, self.vcp, self.junkp, self.simp, self.orgp, self.tlp, self.ddp, self.geop, self.slimp, self.bakp, self.evtp, self.opsp, self.favp, self.pkp, self.dplp, self.wizp]
        for w in self.PAGES: self.stack.addWidget(w if w in (self.logp, self.dupp, self.healthp, self.quarp, self.searchp, self.vcp, self.junkp, self.simp, self.orgp, self.tlp, self.ddp, self.geop, self.slimp, self.bakp, self.evtp, self.opsp, self.favp, self.pkp, self.dplp, self.wizp) else scroll_wrap(w))
        self.stack.setMinimumWidth(420)
        self.sys_panel.clicked.connect(lambda: self.b_perf.toggle()); self.b_bg.clicked.connect(lambda: self.nav.setCurrentRow(1))
        self.b_hide.clicked.connect(self.to_tray); self.b_perf.toggled.connect(self.perf); self.b_cover.clicked.connect(self.show_cover)
        self.nav.setCurrentRow(0)
        # ---- 下面狀態列：後台暫停中的項目、深色／淺色、介面大小
        sb = self.statusBar(); self.b_theme = QPushButton('◐ 深色／淺色'); self.b_theme.setObjectName('pill')
        self.b_zm = QPushButton('－'); self.b_zp = QPushButton('＋'); self.zoom_l = QLabel(f"{THEME_MODE['zoom']}%"); self.zoom_l.setObjectName('muted')
        for b_ in (self.b_zm, self.b_zp): b_.setObjectName('pill'); b_.setFixedWidth(34)
        zl = QLabel('介面大小'); zl.setObjectName('muted')
        self.b_bgst = QPushButton(''); self.b_bgst.setObjectName('pill'); self.b_bgst.setToolTip('後台：暫停中／讓路中的項目（點一下到「後台狀態」）'); self.b_bgst.hide()
        self.b_bgst.clicked.connect(lambda: self.nav.setCurrentRow(1))
        for w_ in (self.b_bgst, self.b_theme, zl, self.b_zm, self.zoom_l, self.b_zp): sb.addPermanentWidget(w_)
        self.b_theme.clicked.connect(lambda: self.set_theme('light' if THEME_MODE['mode'] == 'dark' else 'dark'))
        self.b_zm.clicked.connect(lambda: self.set_zoom(THEME_MODE['zoom'] - 10)); self.b_zp.clicked.connect(lambda: self.set_zoom(THEME_MODE['zoom'] + 10))
        self.pf = None
        if not self.embedded: QTimer.singleShot(3000, arm_watchdog)
        if ENG.cfg.get('perf_float'): self.b_perf.setChecked(True)
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable() and not SELFTEST and not self.embedded:
            self.tray = QSystemTrayIcon(self.icon, self); m = QMenu(self)
            m.addAction('顯示視窗', self.from_tray); m.addAction('⏸ 背景工作全部暫停', lambda: ENG.bg_all(True)); m.addAction('▶ 背景工作全部繼續', lambda: ENG.bg_all(False))
            m.addSeparator(); m.addAction('結束', self.really_quit); self.tray_menu = m
            self.tray.setContextMenu(m); self.tray.activated.connect(lambda r: self.from_tray() if r in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
            self.tray.setToolTip(BRAND['name']); self.tray.show()
        self.lag_last = time.time(); self.lag = QTimer(self); self.lag.timeout.connect(self._lag); self.lag.start(500)
        self.st_t = QTimer(self); self.st_t.timeout.connect(self._status); self.st_t.start(1000)
        self.hb = QTimer(self); self.hb.timeout.connect(lambda: setattr(QApplication.instance(), '_fc_hb', time.time())); self.hb.start(250)
        # ---- 更新提示列：UPDATE 資料夾裡出現新的更新包
        self.ubar = QFrame(); self.ubar.setStyleSheet('QFrame{background:#1f3550;border-bottom:1px solid #4dc9ff}'); ub = QHBoxLayout(self.ubar); ub.setContentsMargins(10, 4, 10, 4)
        self.ubar_l = QLabel(''); ub.addWidget(self.ubar_l, 1); self.ubar_go = QPushButton('⚡ 立即熱更新'); self.ubar_no = QPushButton('稍後'); ub.addWidget(self.ubar_go); ub.addWidget(self.ubar_no)
        v.insertWidget(0, self.ubar); self.ubar.hide(); self._ubar_path = ''
        self.ubar_go.clicked.connect(self._ubar_apply); self.ubar_no.clicked.connect(lambda: (self._upd_seen.add(self._ubar_path), self.ubar.hide()))
        self.ut = QTimer(self); self.ut.timeout.connect(self._watch_update)
        if not self.embedded: self.ut.start(5000)
        self.cover = CoverPage(self); self.outer.addWidget(self.cover); self.outer.addWidget(self.mainw)
        if not self.embedded:
            sc = QShortcut(QKeySequence('Ctrl+L'), self); sc.setContext(Qt.ApplicationShortcut); sc.activated.connect(self.show_cover)
            sc2 = QShortcut(QKeySequence('F1'), self); sc2.activated.connect(lambda: self.enter(9))
        self.last_act = time.time()                                             # V0.5.91 不再攔截整個程式的每個事件（容易卡住）；改問 Windows 最後一次有人動是什麼時候
        self.idle_t = QTimer(self); self.idle_t.timeout.connect(self._idle_check); self.idle_t.start(15000)
        self.outer.setCurrentIndex(0 if ENG.cfg.get('cover_on_start') is not False else 1); self._cover_ready = True
        if self.embedded: self._embed_setup()
        if adopt: self._adopt(adopt)

    def _embed_setup(self):
        """嵌在 SortCut 裡：不要自己的選單（用 VS 左邊的「🗂 整理」）、封面、狀態列、托盤按鈕；樣式照 VS 的深色／淺色."""
        self.setWindowFlags(Qt.Widget)
        try: self.nav.parentWidget().hide()
        except Exception: pass
        for b_ in (self.b_perf, self.b_hide, self.b_cover, self.ptitle): b_.hide()
        self.statusBar().hide(); self.ubar.hide(); self.idle_t.stop(); self.outer.setCurrentIndex(1)
        try: self.setStyleSheet(theme_qss(THEME_MODE['mode'], THEME_MODE['zoom']))
        except Exception: pass
        try: self._embed_setp()
        except Exception: pass
        try:
            if not getattr(self.helpp, '_emb', False):
                self.helpp._emb = True; n_ = QLabel('🔗 <b>現在跑在 SortCut 裡面</b>：下面說的「📊 效能」「🏠 封面」「🌙 縮到背景」、深色／淺色、介面大小、手機網頁、線上更新，都改用 SortCut 的（上方狀態列、設定：SortCut、版本與更新）。左邊選單 ①～⑥ 是建議的順序。')
                n_.setWordWrap(True); n_.setTextFormat(Qt.RichText); self.helpp.layout().insertWidget(0, n_)
        except Exception: pass

    def _embed_setp(self):
        """設定頁：托盤、封面、看門狗、手機網頁、更新都交給 SortCut，這裡只留資料夾＋說明哪些設定在哪."""
        if getattr(self.setp, '_emb', False): return
        self.setp._emb = True
        for g_ in self.setp.findChildren(QGroupBox):
            t_ = str(g_.title())
            if t_.startswith('一般') or t_.startswith('📱'): g_.hide()
            for b_ in g_.findChildren(QPushButton):
                if 'UPDATE' in str(b_.text()) or '程式資料夾' in str(b_.text()): b_.hide()
        n_ = QLabel('🔧 <b>整理（FileCompare）的設定在各頁裡</b>：要整理的資料夾 →「整理總覽」；分類和要搬去哪 →「影片快速分類」的 ⚙；瘦身畫質 →「影片瘦身」；背景要不要跑、時段 →「整理的後台」。<br>'
                    '托盤、封面、手機網頁、更新都跟著 SortCut（設定：SortCut／版本與更新）。'); n_.setWordWrap(True); n_.setTextFormat(Qt.RichText)
        b_ = QPushButton('📥 匯入舊 FileCompare 資料（舊電腦的 Data 資料夾）'); b_.clicked.connect(lambda: EMBED.get('import') and EMBED['import']())
        L_ = self.setp.layout(); L_.insertWidget(0, n_); L_.insertWidget(1, b_)

    # ---------- 熱更新：狀態交出去／接過來（新功能有要保留的畫面狀態就加在這兩個函式）
    def export_state(self):
        return {'page': self.nav.currentRow(), 'cover': self.outer.currentIndex() == 0, 'geo': bytes(self.saveGeometry()), 'max': self.isMaximized(),
                'visible': self.isVisible(), 'perf': self.b_perf.isChecked(), 'seen': list(self._upd_seen)}

    def _adopt(self, st):
        try:
            self._upd_seen = set(st.get('seen') or [])
            if st.get('geo'):
                from PySide6.QtCore import QByteArray
                self.restoreGeometry(QByteArray(st['geo']))
            self.nav.setCurrentRow(int(st.get('page') or 0)); self.outer.setCurrentIndex(0 if st.get('cover') else 1)
        except Exception: ENG.log.err('熱更新：接手畫面狀態')

    def show_after_hot(self, st):
        if st.get('visible', True): (self.showMaximized() if st.get('max') else self.show()); self.raise_(); self.activateWindow()
        notes = st.get('hot_notes') or []
        self.msg(f'⚡ 已熱更新：V{st.get("hot_from")} → V{APP_VERSION}（程式沒有關、背景工作沒有中斷）', 15000)
        if st.get('visible', True):
            QTimer.singleShot(400, lambda: QMessageBox.information(self, '已熱更新', f'V{st.get("hot_from")} → V{APP_VERSION}\n\n' + '\n'.join('• ' + str(x) for x in notes[:12]) + ('\n…' if len(notes) > 12 else '') + '\n\n程式沒有關，背景工作照常進行。'))

    def handoff(self):
        """舊視窗要被新版取代：停計時器、收托盤、關浮窗；不碰引擎."""
        self._handoff = True; self.quitting = True
        for t in self.findChildren(QTimer):
            try: t.stop()
            except Exception: pass
        for d in self.findChildren(QDialog):
            try: d.close()
            except Exception: pass
        try:
            if self.pf is not None: self.pf.close()
        except Exception: pass
        try:
            if self.tray: self.tray.hide()
        except Exception: pass
        try: QApplication.instance().removeEventFilter(self)
        except Exception: pass
        self.hide()

    def _mk_page(self, cls):
        try: return cls(self)
        except Exception:
            err = traceback.format_exc()
            try: ENG.log.w(f'⚠ 電腦版頁面 {cls.__name__} 建不起來（改用替代頁）：' + err.splitlines()[-1][:300]); upd_log(f'頁面 {cls.__name__} 建不起來：\n{err}')
            except Exception: pass
            return ErrPage(cls.__name__, err)

    def _watch_update(self):
        seen = set(self._upd_seen); cache = self.__dict__.setdefault('_pkg_cache', {})
        def look():
            new_seen = []; Z = []
            for d in upd_dirs():                                                # UPDATE 資料夾＋「下載」（下載的只看 FC_V….zip）
                try: Z += [p for p in d.glob('*.zip') if d.name.lower() == 'update' or DL_RE.match(p.name)]
                except Exception: pass
            Z.sort(key=lambda p: vkey(p.stem))
            for z in reversed(Z):
                if str(z) in seen: continue
                try: ck = (str(z), z.stat().st_mtime, z.stat().st_size)
                except Exception: continue
                if ck not in cache:
                    try: pk = load_pkg(z); cache[ck] = (pk['version'], pk['hot_ok'])
                    except Exception as ex: return ('bad', str(z), str(ex), False, new_seen)
                ver_, hot_ = cache[ck]
                if vkey(ver_) > vkey(APP_VERSION): return ('ok', str(z), ver_, hot_, new_seen)
                new_seen.append(str(z))
            return ('none', '', '', False, new_seen)
        bg(look, self._upd_found)

    def _upd_found(self, r):
        if not r: return
        self._upd_seen.update(r[-1])
        if r[0] == 'none' or self._handoff or r[1] in self._upd_seen or self.ubar.isVisible(): return
        self._ubar_path = r[1]
        if r[0] == 'bad': self._upd_seen.add(r[1]); self.msg(f'UPDATE 資料夾裡的 {Path(r[1]).name} 不能用：{r[2]}', 15000); return
        self.ubar_l.setText(f'🆕 發現更新包 <b>{esc_html(Path(r[1]).name)}</b>：V{APP_VERSION} → V{esc_html(r[2])}' + ('（可以熱更新，程式不用關）' if r[3] else '（要重開程式套用）'))
        self.ubar_go.setText('⚡ 立即熱更新' if r[3] else '🔁 重開程式套用'); self.ubar.show(); upd_log(f'發現更新包：{r[1]}（V{r[2]}）')
        try:                                                                   # 跟 TikLive 一樣：右下角也提醒一次
            if self.tray: self.tray.showMessage(f'{BRAND["name"]} · 有新版', f'{Path(r[1]).name}（V{APP_VERSION} → V{r[2]}）：按上面的「⚡ 立即熱更新」', QSystemTrayIcon.Information, 10000)
        except Exception: pass

    def _ubar_apply(self):
        self.ubar.hide(); self._upd_seen.add(self._ubar_path)
        if not self.upd.load(self._ubar_path): self.nav.setCurrentRow(8); return
        if self.upd.pkg.get('hot_ok'): self.upd.go()
        else: self.upd.restart_way()

    # ---------- 封面、切頁
    def show_cover(self):
        if getattr(self, 'embedded', False): return
        self.outer.setCurrentIndex(0); self.cover.refresh(); ENG.log.w('畫面：回到封面')

    def enter(self, page):
        self.outer.setCurrentIndex(1); was_ = self.nav.currentRow(); self.nav.setCurrentRow(int(page))
        if was_ == int(page): self._page(int(page))

    def eventFilter(self, obj, e): return False                             # V0.5.91 舊版熱更新上來的還掛著也不做事

    def _idle_check(self):
        try:
            A = sys.modules.get('app') or sys.modules.get('__main__'); f_ = getattr(A, 'user_last_input', None)
            if f_ is None:
                import ctypes

                class _LII(ctypes.Structure): _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]
                li = _LII(); li.cbSize = ctypes.sizeof(_LII)
                if os.name == 'nt' and ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
                    self.last_act = max(self.last_act, time.time() - ((ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000.0)
            else: self.last_act = max(self.last_act, f_())
        except Exception: pass
        m = int(ENG.cfg.get('cover_idle_min') or 0)
        if m and self.outer.currentIndex() == 1 and time.time() - self.last_act > m * 60: self.show_cover(); ENG.log.w(f'閒置 {m} 分鐘，自動回到封面')

    def _page(self, i):
        i = int(i)
        if not hasattr(self, 'stack') or not (0 <= i < self.stack.count()): return
        self.stack.setCurrentIndex(i)
        if getattr(self, 'embedded', False) and EMBED.get('nav'):                # 整理裡面按按鈕跳到別頁：SortCut 左邊選單跟著亮那一頁
            try: EMBED['nav'](i)
            except Exception: pass
        if self._cover_ready and self.outer.currentIndex() == 0: self.outer.setCurrentIndex(1)
        if self._cover_ready and i not in (6, 8): ENG.cfg.set('last_page', i)
        try: self.ptitle.setText(f'{self.nav.page_icon(i)} {self.nav.page_name(i)}'.strip())
        except Exception: pass
        ENG.log.w(f'畫面：切到「{self.nav.page_name(i)}」')

    # ---------- 外觀
    def set_theme(self, mode):
        mode = set_theme_mode(mode); ENG.cfg.set('ui_theme', mode); _set_qss(theme_qss(mode)); self.update()
        for w_ in self.findChildren(QWidget):
            try: w_.update()
            except Exception: pass
        self.msg('主題：' + ('☀ 淺色' if mode == 'light' else '🌙 深色'), 3000)

    def set_zoom(self, z):
        z = max(70, min(160, int(z))); ENG.cfg.set('ui_zoom', z); _set_qss(theme_qss(None, z)); self.zoom_l.setText(f'{z}%'); self.msg(f'介面大小 {z}%', 2500)

    def msg(self, s, ms=6000):
        if getattr(self, 'embedded', False) and EMBED.get('msg'):
            try: EMBED['msg'](str(s), ms)
            except Exception: pass
        else: self.statusBar().showMessage(str(s), ms)
        ENG.log.w('畫面：' + str(s))

    def perf(self, on):
        ENG.cfg.set('perf_float', bool(on))
        if on:
            if self.pf is None:
                self.pf = PerfFloat(); pos = ENG.cfg.get('perf_pos')
                if pos: self.pf.move(int(pos[0]), int(pos[1]))
                else: self.pf.move(self.x() + self.width() - 280, self.y() + 70)
            self.pf.show()
        elif self.pf is not None: self.pf.hide()

    def _status(self):
        if getattr(self, 'embedded', False) and not self.isVisible():            # 嵌在 SortCut 裡、現在沒在看整理：5 秒更新一次就好（少查資料庫）
            if time.time() - getattr(self, '_st_t0', 0) < 5: return
        self._st_t0 = time.time()
        bg(ENG.info, self._st)
        try:
            nm = dict((k, n) for k, _i, n in ENG.BG_KINDS); P = [nm.get(k, k) for k, v_ in list(ENG.bg_pause.items()) if v_]; H = [nm.get(k, k) for k in list(ENG.bg_auto)]
            t_ = ('⏸ ' + '、'.join(P) if P else '') + ('　' if P and H else '') + ('⚖ 讓路：' + '、'.join(H) if H else '')
            self.b_bgst.setText(t_); self.b_bgst.setVisible(bool(t_))
        except Exception: pass

    def _st(self, I):
        C = I.get('fc') or {}; B = I.get('busy') or {}; nb = sum(B.values())
        txt = (f"　{C.get('files', 0):,} 個檔・重複 {C.get('dup_groups', 0):,} 組（可省 {fmt_b(C.get('dup_bytes', 0))}）・有問題 {C.get('bad', 0):,} 個・隔離區 {C.get('quar_n', 0):,} 個"
               + ('　▶ ' + '、'.join(n for k, n in (('scan', '掃描'), ('meta', '讀資訊'), ('hash', '比對'), ('health', '檢查'), ('repair', '修復')) if B.get(k)) + '中' if nb else ''))
        self.stat.setText(txt); self.nav.set_badge(1, str(nb) if nb else '')
        self.nav.set_badge(2, f"{C.get('dup_groups', 0):,}" if C.get('dup_groups') else ''); self.nav.set_badge(3, f"{C.get('bad', 0):,}" if C.get('bad') else '')
        self.nav.set_badge(4, f"{C.get('quar_n', 0):,}" if C.get('quar_n') else '')
        try:                                                                         # 📦 還沒審的資料夾包、🎞 還沒審的影片（V0.2.54，用快取，不查資料庫）
            pc = ENG.vg._cache[1]
            if pc is not None: n_ = sum(1 for g in pc.values() if g['todo']); self.nav.set_badge(24, f'{n_:,}' if n_ else '')
        except Exception: pass
        P = ENG.perf; g = P.gpu or {}
        rows = [('CPU', P.cpu, f'{P.cpu:.0f}%', None, '#4dc9ff'), ('RAM', P.ram, f'{P.ram:.0f}%', None, '#b48cff')]
        if g:
            rows.append(('GPU', g.get('util'), f'{g.get("util", 0):.0f}%', g.get('temp'), '#45d483'))
            if g.get('mem_t'): rows.append(('VRAM', 100 * g['mem'] / g['mem_t'], f'{100 * g["mem"] / g["mem_t"]:.0f}%', None, '#9aa5b3'))
        self.sys_panel.set_rows(rows)
        if self.tray: self.tray.setToolTip(BRAND['name'] + txt.replace('　', '\n'))

    def _lag(self):
        now = time.time(); gap = now - self.lag_last - 0.5; self.lag_last = now
        try: lim = float(ENG.cfg.get('freeze_log_s') or 2)
        except Exception: lim = 2.0
        if gap >= lim: ENG.log.w(f'畫面卡了 {gap:.1f} 秒　頁面={self.nav.currentRow()}　CPU {ENG.perf.cpu:.0f}%', 'ui_freeze_log.txt')

    # ---------- 托盤、關閉、重開
    def to_tray(self):
        if getattr(self, 'embedded', False): return
        if self.tray: self.hide(); self.tray.showMessage(BRAND['name'], '在背景繼續做；點右下角圖示打開', QSystemTrayIcon.Information, 3000)
        else: self.showMinimized()

    def from_tray(self):
        if ENG.cfg.get('cover_on_restore'): self.show_cover()
        self.show(); self.setWindowState(self.windowState() & ~Qt.WindowMinimized); self.raise_(); self.activateWindow()

    def closeEvent(self, e):
        if self._handoff: e.accept(); return
        if not self.quitting and self.tray and ENG.cfg.get('close_to_tray'): e.ignore(); self.to_tray(); return
        self.quitting = True
        if self.pf is not None: self.pf.close()
        if self.tray: self.tray.hide()
        try:
            s_ = web_server(create=False)
            if s_ is not None: s_.close()
        except Exception: pass
        mark_clean_exit(); ENG.shutdown(); e.accept(); QApplication.instance().quit()

    def really_quit(self):
        busy = sum(ENG.bg_running(k) for k, _i, _n in ENG.BG_KINDS)
        if busy and QMessageBox.question(self, '結束', f'還有 {busy} 個工作在做（下次打開會接著做）。確定結束？') != QMessageBox.Yes: return
        self.quitting = True; self.close()

    def restart(self):
        self.quitting = True; mark_clean_exit()
        exe = sys.executable; rest = [a for a in sys.argv[1:] if a != '--restart' and not a.startswith('--oldpid=')] + ['--restart', f'--oldpid={os.getpid()}']
        args = rest if getattr(sys, 'frozen', False) else [str(HERE / 'app.py')] + rest
        try: subprocess.Popen([exe] + args, cwd=str(ROOT), creationflags=0x00000008 if core.IS_WIN else 0)
        except Exception as ex: QMessageBox.warning(self, '重新開啟', f'沒辦法自己重開，請手動打開程式：{ex}')
        self.close()


# ============================================================ 防當機／查問題
def _install_guards(app):
    """程式整個掛掉的傾印、背景執行緒的錯誤、Qt 的警告、畫面卡住時卡在哪一行。熱更新時新版也會叫一次（不重複裝）."""
    sys.excepthook = lambda t, v, tb: _eng_log('未處理的錯誤（程式沒有關）：\n' + ''.join(traceback.format_exception(t, v, tb)), 'error_log.txt')
    threading.excepthook = lambda a: _eng_log(f'背景執行緒 {getattr(a.thread, "name", "?")} 出錯（程式沒有關）：\n' + ''.join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)), 'error_log.txt')
    seen = {}
    def qt_msg(mode, ctx, msg):
        try:
            k = str(msg)[:200]; now = time.time()
            if now - seen.get(k, 0) < 60: return
            seen[k] = now
            if len(seen) > 500: seen.clear()
            _eng_log(f'Qt：{msg}', 'qt_log.txt')
        except Exception: pass
    try: qInstallMessageHandler(qt_msg)
    except Exception: pass
    if getattr(app, '_fc_guards', False): return
    app._fc_guards = True
    try:
        (ROOT / 'LOG').mkdir(exist_ok=True); fh = open(ROOT / 'LOG' / 'crash_dump.txt', 'a', encoding='utf-8')
        fh.write(f'\n===== {time.strftime("%Y-%m-%d %H:%M:%S")} 啟動 V{APP_VERSION}（如果程式整個掛掉，這下面會有每條執行緒在做什麼）=====\n'); fh.flush()
        faulthandler.enable(file=fh, all_threads=True); app._fc_fault_fh = fh
    except Exception: pass
    app._fc_hb = time.time()
    def watchdog():
        dumped = 0
        while True:
            time.sleep(0.5)
            try:
                gap = time.time() - float(getattr(app, '_fc_hb', time.time())); e = getattr(app, '_fc_eng', None)
                lim = max(3.0, float(e.cfg.get('freeze_log_s') or 2) + 1.0) if e else 4.0
                if gap >= lim and not dumped:
                    fr = sys._current_frames().get(threading.main_thread().ident)
                    _eng_log(f'⚠ 畫面已經卡住 {gap:.1f} 秒，主執行緒現在卡在：\n' + (''.join(traceback.format_stack(fr)[-14:]) if fr else '（讀不到）'), 'ui_freeze_log.txt'); dumped = 1
                elif gap < 1 and dumped: dumped = 0
            except Exception: pass
    threading.Thread(target=watchdog, name='UiWatchdog', daemon=True).start()


def _eng_log(msg, f='app_log.txt'):
    try: (getattr(QApplication.instance(), '_fc_eng', None) or ENG).log.w(msg, f)
    except Exception:
        try:
            with open(ROOT / 'LOG' / f, 'a', encoding='utf-8') as fh: fh.write(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}\n')
        except Exception: pass


def _connect_peer(app):
    """只能開一個：第二次打開時叫出原本那個的視窗."""
    srv = getattr(app, '_fc_srv', None)
    if srv is None: return
    try: srv.newConnection.disconnect()
    except Exception: pass
    def _peer():
        c = srv.nextPendingConnection()
        if c: c.disconnectFromServer(); c.deleteLater()
        w = getattr(app, '_fc_main', None)
        if w is not None and not w.quitting: w.from_tray()
    srv.newConnection.connect(_peer)


# ============================================================ 📱 手機網頁伺服器（放在 QApplication 上，熱更新時換成新版的）
def web_server(create=True):
    app = QApplication.instance(); s = getattr(app, '_fc_web', None)
    if type(s).__name__ != 'WebServer': s = None
    if s is None and create:
        s = web.WebServer(lambda: QApplication.instance()._fc_eng, lambda: QApplication.instance()._fc_main, ui, lambda: sys.modules[__name__], APP_VERSION, BRAND); app._fc_web = s
    return s


def web_apply():
    """照設定開／關手機網頁（埠、區網選項改了就重開）."""
    try:
        on = bool(ENG.cfg.get('web_on')); port = int(ENG.cfg.get('web_port') or BRAND['web_port']); lan = bool(ENG.cfg.get('web_lan'))
        s = web_server(create=on)
        if s is None: return
        if not on: s.close(); return
        if s.running and s.port == port and s.bind == ('0.0.0.0' if lan else '127.0.0.1'): return
        s.start(port, lan)
    except Exception: ENG.log.err('手機網頁 開／關')


def web_restart_new():
    """熱更新：舊版的伺服器關掉，換成新版的（同一個埠）。埠還沒放開就 1 秒後再試."""
    app = QApplication.instance(); old = getattr(app, '_fc_web', None)
    if type(old).__name__ == 'WebServer':
        try: old.close()
        except Exception: pass
        app._fc_web = None
    def again(n=0):
        web_apply(); s = web_server(create=False)
        if s is not None and ENG.cfg.get('web_on') and not s.running and n < 5: QTimer.singleShot(1000, lambda: again(n + 1))
    again()


def hot_start(old_eng, state):
    """熱更新進來的入口（舊版呼叫）：新引擎（還沒開始跑）＋新視窗。失敗就丟例外，舊版會還原."""
    global BUS, ENG
    app = QApplication.instance(); BUS = Bus()
    ENG = core.Engine(ROOT, adopt=old_eng, start=False, version=APP_VERSION)
    old_main = getattr(app, '_fc_main', None); old_e = getattr(app, '_fc_eng', None); before = set(map(id, QApplication.topLevelWidgets())); w = None
    try:
        w = Main(adopt=state); app._fc_main = w; app._fc_eng = ENG; _install_guards(app); _connect_peer(app)
        try: app.commitDataRequest.disconnect()
        except Exception: pass
        app.commitDataRequest.connect(_on_commit)
        if state.get('perf'): w.b_perf.setChecked(True)
        try: web_restart_new()
        except Exception: ENG.log.err('熱更新：手機網頁換新版')
    except Exception:
        for tw in QApplication.topLevelWidgets():
            if id(tw) in before: continue
            try:
                if isinstance(tw, Main): tw.handoff()
                tw.close(); tw.deleteLater()
            except Exception: pass
        app._fc_main = old_main; app._fc_eng = old_e
        try:
            if old_main is not None: app.commitDataRequest.connect(_on_commit)
        except Exception: pass
        ENG.discard(); raise
    return w, ENG


# ============================================================ 閃退自動重開（Windows：另外一個 PowerShell 看著，主程式不見又沒有正常結束的記號就重開）
WATCHDOG_PS1 = r'''param([int]$procid, [string]$flag, [string]$exe, [string]$argline, [string]$cwd, [string]$log, [long]$ft = 0)
try {
  $p = Get-Process -Id $procid -ErrorAction SilentlyContinue
  if ($p -and ($ft -eq 0 -or [math]::Abs($p.StartTime.ToFileTimeUtc() - $ft) -lt 20000000)) { $p.WaitForExit() }
} catch {}
Start-Sleep -Seconds 4
if (Test-Path -LiteralPath $flag) { Remove-Item -LiteralPath $flag -ErrorAction SilentlyContinue; exit }
$t = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Add-Content -LiteralPath $log -Value "[$t] watchdog: PID $procid did not exit normally -> restarting" -Encoding UTF8
if ($argline) { Start-Process -FilePath $exe -ArgumentList $argline -WorkingDirectory $cwd } else { Start-Process -FilePath $exe -WorkingDirectory $cwd }
'''


def run_state_path(): return ENG.data / 'run_state.json'


def _on_commit(_m=None):
    """Windows 關機／登出：標記正常結束（不要重開）；關機被取消的話 1 分鐘後把記號拿掉."""
    try: setattr(getattr(QApplication.instance(), '_fc_main', None), 'quitting', True)
    except Exception: pass
    mark_clean_exit()
    try: QTimer.singleShot(60000, _commit_cancelled)
    except Exception: pass


def _commit_cancelled():
    try: (ENG.data / f'clean_exit_{os.getpid()}.flag').unlink()
    except Exception: pass
    try:
        st = json.loads(run_state_path().read_text(encoding='utf-8')) if run_state_path().exists() else {}
        st.update(clean=False); run_state_path().write_text(json.dumps(st), encoding='utf-8')
        w = getattr(QApplication.instance(), '_fc_main', None)
        if w is not None: w.quitting = False
    except Exception: pass


def _proc_ft():
    try:
        import ctypes
        from ctypes import wintypes
        a, b, c, d = (wintypes.FILETIME() for _ in range(4))
        if ctypes.windll.kernel32.GetProcessTimes(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(a), ctypes.byref(b), ctypes.byref(c), ctypes.byref(d)):
            return (a.dwHighDateTime << 32) | a.dwLowDateTime
    except Exception: pass
    return 0


def mark_clean_exit():
    try:
        (ENG.data / f'clean_exit_{os.getpid()}.flag').write_text(time.strftime('%Y-%m-%d %H:%M:%S'), encoding='utf-8')
        st = json.loads(run_state_path().read_text(encoding='utf-8')) if run_state_path().exists() else {}
        st.update(clean=True, t_end=time.time()); run_state_path().write_text(json.dumps(st), encoding='utf-8')
    except Exception: pass


def arm_watchdog(win=None):
    """①上次是不是閃退 → 記 LOG、提醒（10 分鐘內第 2 次：背景工作先全部暫停）②開看門狗（10 分鐘內閃退 3 次就先不開，避免一直重開）."""
    app = QApplication.instance()
    if getattr(app, '_fc_wd_armed', False) or SELFTEST: return
    app._fc_wd_armed = True; app.aboutToQuit.connect(mark_clean_exit)
    try: st = json.loads(run_state_path().read_text(encoding='utf-8')) if run_state_path().exists() else {}
    except Exception: st = {}
    crashes = [t for t in (st.get('crashes') or []) if time.time() - t < 600]
    if st and st.get('clean') is False:
        crashes.append(time.time()); ENG.log.w(f'⚠ 上次（PID {st.get("pid")}）沒有正常結束（閃退／當機）' + ('，看門狗自動重開了' if '--after-crash' in sys.argv else ''))
        if len(crashes) >= 2:
            try: ENG.bg_all(True); ENG.log.w('⚠ 10 分鐘內閃退 2 次以上：背景工作先全部暫停（到「🖥 後台」按繼續）')
            except Exception: pass
        QTimer.singleShot(5000, lambda: (getattr(QApplication.instance(), '_fc_main', None) or type('N', (), {'msg': lambda *a: None})()).msg('⚠ 上次程式意外關閉（閃退），LOG 有紀錄', 20000))
    try: run_state_path().write_text(json.dumps({'pid': os.getpid(), 't': time.time(), 'clean': False, 'crashes': crashes, 'ver': APP_VERSION}), encoding='utf-8')
    except Exception: pass
    if not core.IS_WIN or ENG.cfg.get('auto_restart') is False: return
    if len(crashes) >= 3: ENG.log.w(f'⚠ 10 分鐘內閃退 {len(crashes)} 次：這次先不開看門狗'); return
    try:
        ps1 = ENG.data / 'watchdog.ps1'; ps1.write_text(WATCHDOG_PS1, encoding='utf-8-sig')
        exe = sys.executable; rest = [a for a in sys.argv[1:] if a not in ('--restart', '--after-crash') and not a.startswith('--oldpid=')] + ['--restart', '--after-crash']
        args = rest if getattr(sys, 'frozen', False) else [str(HERE / 'app.py')] + rest
        flag = ENG.data / f'clean_exit_{os.getpid()}.flag'
        try: flag.unlink()
        except Exception: pass
        psx = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
        if not os.path.isfile(psx): psx = 'powershell'
        if not getattr(sys, 'frozen', False) and exe.lower().endswith('python.exe') and os.path.isfile(exe[:-10] + 'pythonw.exe'): exe = exe[:-10] + 'pythonw.exe'
        cmd = [psx, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', str(ps1), '-procid', str(os.getpid()), '-flag', str(flag),
               '-exe', exe, '-argline', subprocess.list2cmdline(args), '-cwd', str(ROOT), '-log', str(ROOT / 'LOG' / 'app_log.txt'), '-ft', str(_proc_ft())]
        for fl in (0x08000000 | 0x00000200 | 0x01000000, 0x08000000 | 0x00000200):
            try: app._fc_wd = subprocess.Popen(cmd, creationflags=fl, close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); ENG.log.w('看門狗開好了：閃退會自動重開'); break
            except OSError: continue
        for old in ENG.data.glob('clean_exit_*.flag'):
            if old.name != flag.name:
                try:
                    if time.time() - old.stat().st_mtime > 3600: old.unlink()
                except Exception: pass
    except Exception: ENG.log.err('看門狗')


def _pid_gone(pid):
    try:
        if core.IS_WIN:
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x00100000, False, int(pid))
            if not h: return True
            try: return ctypes.windll.kernel32.WaitForSingleObject(h, 0) == 0
            finally: ctypes.windll.kernel32.CloseHandle(h)
        os.kill(int(pid), 0); return False
    except Exception: return True


def main():
    global BUS, ENG
    t_boot = time.time()
    app = QApplication.instance() or QApplication(sys.argv); app.setApplicationName(BRAND['id']); app.setStyleSheet(STYLE); app.setQuitOnLastWindowClosed(False)
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    if not SELFTEST:
        t_end = time.time() + (25 if '--restart' in sys.argv else 0)
        opid = next((int(a.split('=', 1)[1]) for a in sys.argv if a.startswith('--oldpid=') and a.split('=', 1)[1].isdigit()), 0)
        if opid: t_end = time.time() + 120
        while True:                                                             # 只能開一個（重開時等舊的關掉）
            s = QLocalSocket(); s.connectToServer(SINGLE)
            if not s.waitForConnected(300): break
            s.abort()
            if opid and time.time() <= t_end and _pid_gone(opid): time.sleep(0.5); continue
            if time.time() > t_end: QMessageBox.information(None, BRAND['name'], f'{BRAND["name"]} 已經開著了（看右下角的圖示）。'); return 0
            time.sleep(0.5)
        srv = QLocalServer(); QLocalServer.removeServer(SINGLE); srv.listen(SINGLE); app._fc_srv = srv
    BUS = Bus(); ENG = core.Engine(ROOT, version=APP_VERSION); app._fc_eng = ENG
    _install_guards(app)
    try: arm_watchdog()
    except Exception: ENG.log.err('看門狗')
    w = Main(); w.show(); app._fc_main = w
    web_apply()
    ENG.log.w(f'啟動完成：畫面出來花 {time.time() - t_boot:.1f} 秒')
    app.commitDataRequest.connect(_on_commit)
    if not SELFTEST: _connect_peer(app)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())


# ============================================================ 🔗 SortCut 叫的入口
class _PerfProxy:
    """嵌在 SortCut 裡：CPU／記憶體／顯示卡用 SortCut 已經在量的（不要兩邊各自每 2 秒開一次 nvidia-smi）."""
    def __init__(self, get): self.__dict__['_get'] = get; self.__dict__['stop'] = False
    def __getattr__(self, k): return getattr(self.__dict__['_get'](), k)

    def view(self):
        """手機「效能」：SortCut 的量測物件沒有 view()，這裡照整理的格式組一份."""
        P = self.__dict__['_get'](); f = getattr(type(P), 'view', None)
        if callable(f): return P.view()
        g = dict(P.gpu or {})
        return {'cpu': round(float(P.cpu or 0), 1), 'ram': round(float(P.ram or 0), 1), 'ram_used': P.ram_used, 'ram_total': P.ram_total, 'gpu': g,
                'hist': {k: [None if x is None else round(float(x), 1) for x in list(v)[-90:]] for k, v in P.H.items()}}
    def __setattr__(self, k, v):
        if k == 'stop': self.__dict__['stop'] = v                                # 整理要停自己的量測：不能停到 SortCut 的


def embed_boot(root, vs_root=None, theme='dark', zoom=100, msg=None, ff=None, imp=None, nav=None, perf=None, badge=None):
    """SortCut 開 FileCompare 引擎：root＝FileCompare 的資料（Data\\、LOG\\）。已經有在跑的就接手（VS 熱更新）."""
    global BUS, ENG, ROOT
    app = QApplication.instance(); ROOT = Path(root); ROOT.mkdir(parents=True, exist_ok=True)
    EMBED['on'] = True; EMBED['msg'] = msg; EMBED['vs_root'] = vs_root; EMBED['import'] = imp; EMBED['nav'] = nav; EMBED['badge'] = badge
    set_theme_mode(theme); THEME_MODE['zoom'] = max(70, min(160, int(zoom or 100)))
    BUS = Bus(); old = getattr(app, '_fc_eng', None)
    if type(old).__name__ != 'Engine': old = None
    ENG = core.Engine(ROOT, adopt=old, start=False, version=APP_VERSION)
    if ff and ff[0]: ENG._ff = tuple(ff)
    if vs_root: ENG._vs_root = str(vs_root)
    if perf:
        try: ENG.perf.stop = True
        except Exception: pass
        ENG.perf = _PerfProxy(perf)
    return ENG


def embed_main(state=None):
    """建嵌入用的主畫面（還沒放進 SortCut 的版面）。舊的（VS 熱更新前的）交接掉、新引擎開始跑."""
    app = QApplication.instance(); old_w = getattr(app, '_fc_main', None); old_e = getattr(app, '_fc_eng', None)
    if type(old_w).__name__ != 'Main': old_w = None
    if type(old_e).__name__ != 'Engine': old_e = None
    if state is None and old_w is not None:
        try: state = old_w.export_state()
        except Exception: state = None
    w = Main(adopt=state, embedded=True)
    if old_w is not None:
        try: old_w.handoff()
        except Exception: pass
    app._fc_main = w; app._fc_eng = ENG
    if not ENG.started: ENG.start()
    if old_e is not None and old_e is not ENG:
        try: old_e.retire()
        except Exception: pass
    if old_w is not None:
        try: old_w.setParent(None); old_w.deleteLater()
        except Exception: pass
    try: w._embed_setup()
    except Exception: pass
    return w


def embed_theme(mode, zoom=None):
    set_theme_mode(mode)
    if zoom is not None: THEME_MODE['zoom'] = max(70, min(160, int(zoom)))
    _set_qss(theme_qss(mode, THEME_MODE['zoom']))


def embed_shutdown():
    """SortCut 要結束：FileCompare 的背景工作收掉（下次打開接著做）."""
    app = QApplication.instance(); e = getattr(app, '_fc_eng', None)
    if type(e).__name__ == 'Engine':
        try: e.shutdown()
        except Exception: pass


_EMBED_WEB = {}


def embed_web():
    """手機：SortCut 的網頁伺服器借用 FileCompare 的 API（不另外開埠、不用另外的 PIN）."""
    s = _EMBED_WEB.get('s')
    if s is None:
        s = web.WebServer(lambda: QApplication.instance()._fc_eng, lambda: QApplication.instance()._fc_main, ui, lambda: sys.modules[__name__], APP_VERSION, dict(BRAND, name='🗂 整理', title='整理（FileCompare）'))
        _EMBED_WEB['s'] = s
    return s

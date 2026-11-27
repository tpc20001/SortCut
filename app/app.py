"""SortCut 影片初剪整理 — 主程式（PySide6）。

畫面只做畫面：讀硬碟、查資料庫、跑 FFmpeg 都在 core.Engine 的背景執行緒；畫面每隔一下拿結果來顯示。
"""
import os, sys, re, json, time, math, random, shutil, zipfile, threading, traceback, subprocess, faulthandler, importlib, importlib.util
from pathlib import Path
from collections import OrderedDict, deque

from PySide6.QtCore import Qt, QTimer, QObject, Signal, Slot, QRect, QRectF, QPoint, QPointF, QSize, QUrl, QEvent, QMimeData, qInstallMessageHandler
from PySide6.QtGui import (QPainter, QColor, QPixmap, QImage, QIcon, QFont, QPen, QAction, QKeySequence, QShortcut, QDesktopServices, QPainterPath, QCursor, QFontMetrics, QLinearGradient, QRadialGradient, QWindow)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QListWidget, QListWidgetItem,
                               QTreeWidget, QTreeWidgetItem, QSplitter, QStackedWidget, QScrollArea, QComboBox, QSpinBox, QCheckBox, QLineEdit, QFileDialog,
                               QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QProgressBar, QDialog, QSlider, QDoubleSpinBox, QMenu,
                               QSystemTrayIcon, QFormLayout, QGroupBox, QPlainTextEdit, QTextBrowser, QFrame, QSizePolicy, QListView, QStyledItemDelegate, QStyle, QInputDialog, QKeySequenceEdit, QTabWidget, QLayout, QStyleOptionSlider, QToolTip, QAbstractScrollArea)

APP_VERSION = '0.6.42'
APP_TITLE = 'SortCut 影片初剪整理'
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import core  # noqa: E402
import vs_web  # noqa: E402  V0.1.49 手機網頁
import vs_face  # noqa: E402  V0.1.51 人物
from core import fmt_t, fmt_b  # noqa: E402
class _html:                                                                    # V0.6.31 不能 import html：舊的 EXE 裡沒有這個模組（熱更新只換程式，不換 EXE）
    @staticmethod
    def escape(s, quote=True):
        s = str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return s.replace('"', '&quot;').replace("'", '&#x27;') if quote else s

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else HERE.parent
SELFTEST = bool(os.environ.get('VIDEOSIFT_SELFTEST'))
GC = {'S': '#ffc94d', 'A': '#45d483', 'E': '#4dc9ff', 'F': '#ff4d6d'}
GN = {'S': '無條件保存', 'A': '保存', 'E': '觀察', 'F': '刪除'}

# ============================================================ V0.1.53 介面照 TikLive：顏色、字型、側邊欄（同一套 token，深色／淺色）
THEMES = {
    'dark': {
        'bg': '#0e1116', 'side': '#090c10', 'nav': '#0a0e13', 'panel': '#11161c', 'card': '#151a21', 'input': '#151a21',
        'button': '#171d26', 'button_hover': '#222b37', 'border': '#252c35', 'border_strong': '#2a3340', 'text': '#e8ecf2',
        'text_strong': '#ffffff', 'subtext': '#8994a4', 'muted': '#7f8a99', 'nav_text': '#b9c2cf', 'hover': '#161e28',
        'header_bg': '#191f27', 'header_text': '#aeb7c4', 'grid': '#222933', 'alt_row': '#151a21', 'selection': '#263342',
        'selection_text': '#ffffff', 'chart_bg': '#0d1218', 'scroll': '#3a4654', 'track': '#2a3038', 'accent': '#e51e63',
        'tile_bg': '#151b23', 'tile_border': '#2a3543', 'viewer_line': '#43d9ff', 'sub_accent': '#f0ad4e',
    },
    'light': {
        'bg': '#f3f5f8', 'side': '#e8ecf1', 'nav': '#e8ecf1', 'panel': '#ffffff', 'card': '#ffffff', 'input': '#ffffff',
        'button': '#ffffff', 'button_hover': '#e7ecf2', 'border': '#d5dce4', 'border_strong': '#c2cbd6', 'text': '#1b2430',
        'text_strong': '#0b121a', 'subtext': '#5d6978', 'muted': '#6b7685', 'nav_text': '#334050', 'hover': '#dde4ec',
        'header_bg': '#eef1f5', 'header_text': '#3d4856', 'grid': '#e4e9ef', 'alt_row': '#f7f9fb', 'selection': '#d3e6fb',
        'selection_text': '#0b121a', 'chart_bg': '#ffffff', 'scroll': '#b6c0cb', 'track': '#dfe5ec', 'accent': '#e51e63',
        'tile_bg': '#ffffff', 'tile_border': '#d5dce4', 'viewer_line': '#0a84c6', 'sub_accent': '#c77700',
    },
}
THEME = dict(THEMES['dark'])
THEME_MODE = {'mode': 'dark', 'zoom': 100}


def set_theme_mode(mode):
    mode = 'light' if str(mode) == 'light' else 'dark'
    THEME.clear(); THEME.update(THEMES[mode]); THEME_MODE['mode'] = mode
    return mode


def TC(key):
    return QColor(THEME.get(key, '#ff00ff'))


def theme_qss(mode=None, zoom=None):
    """整個程式的樣式（照 TikLive apply_theme_stylesheet，再加上 SortCut 自己用到的元件）."""
    if mode is not None: set_theme_mode(mode)
    if zoom is not None: THEME_MODE['zoom'] = max(70, min(160, int(zoom)))
    t = THEME; fs = round(13 * THEME_MODE['zoom'] / 100)
    return f"""
QMainWindow,QWidget,QDialog{{background:{t['bg']};color:{t['text']};font-family:"Yu Gothic UI","Microsoft JhengHei","PingFang TC";font-size:{fs}px}}
QFrame#side{{background:{t['side']};border-right:1px solid {t['border']}}}
QLabel#title{{font-weight:800;font-size:{round(fs * 1.3)}px;color:{t['text_strong']}}} QLabel#sub,QLabel#muted{{color:{t['subtext']}}}
QLabel#ptitle{{font-weight:850;font-size:{round(fs * 1.35)}px;color:{t['text_strong']};background:transparent}}
QPushButton{{background:{t['button']};border:1px solid {t['border_strong']};border-radius:9px;padding:5px 10px;color:{t['text']}}} QPushButton:pressed{{background:{t['selection']}}}
QPushButton:hover{{background:{t['button_hover']}}} QPushButton:disabled{{color:{t['muted']}}}
QPushButton:checked{{background:{t['selection']};border-color:{t['viewer_line']};color:{t['text_strong']}}}
QPushButton#side_start{{background:#e51e63;border:0;font-weight:900;min-height:26px;padding:2px 4px;color:#ffffff}} QPushButton#side_start:hover{{background:#f0306f}}
QPushButton#side_stop{{background:{t['button']};border:1px solid {t['border_strong']};font-weight:850;min-height:26px;padding:2px 4px}}
QPushButton#side_stop:checked{{background:{t['button']};color:{t['sub_accent']};border-color:{t['sub_accent']}}}
QPushButton#start{{background:#e51e63;border:0;font-weight:900;min-height:32px;color:#ffffff}}
QPushButton#net_btn{{text-align:left;padding:5px 8px;border-radius:9px;background:{t['card']};border:1px solid {t['border']}}} QPushButton#net_btn:hover{{background:{t['button_hover']}}}
QPushButton#pill{{border-radius:12px;padding:3px 11px;font-size:{round(fs * 0.9)}px}}
QListWidget#workspace_nav{{background:{t['nav']};border:0;border-radius:9px;padding:2px 1px;outline:0}}
QListWidget#workspace_nav::item{{border:0;background:transparent}}
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QFontComboBox,QKeySequenceEdit,QTimeEdit{{background:{t['input']};border:1px solid {t['border_strong']};border-radius:7px;padding:4px 7px;color:{t['text_strong']}}}
QPlainTextEdit,QTextBrowser,QTextEdit{{background:{t['panel']};border:1px solid {t['border']};border-radius:8px;color:{t['text']}}}
QLineEdit:focus,QSpinBox:focus,QComboBox:focus,QPlainTextEdit:focus{{border-color:{t['viewer_line']}}}   /* V0.4.57 輸入框選到時邊框變亮 */
QComboBox QAbstractItemView{{background:{t['panel']};color:{t['text']};selection-background-color:{t['selection']};selection-color:{t['selection_text']}}}
QMenu{{background:{t['panel']};color:{t['text']};border:1px solid {t['border']};border-radius:10px;padding:4px}} QMenu::item{{padding:6px 20px;border-radius:7px}} QMenu::item:selected{{background:{t['selection']};color:{t['selection_text']}}} QMenu::separator{{height:1px;background:{t['border']};margin:4px 8px}}
QListWidget,QTreeWidget,QTableWidget,QTableView,QListView{{background:{t['panel']};border:1px solid {t['border']};border-radius:8px;alternate-background-color:{t['alt_row']};outline:0}}
QListWidget::item:selected,QTreeWidget::item:selected,QTableWidget::item:selected,QListView::item:selected{{background:{t['selection']};color:{t['selection_text']}}}
QListWidget::item:hover,QTreeWidget::item:hover{{background:{t['hover']}}}
QTableWidget,QTableView{{gridline-color:{t['grid']}}}
QHeaderView::section{{background:{t['header_bg']};color:{t['header_text']};padding:5px;padding-right:15px;border:0;font-weight:700}}
QTableCornerButton::section{{background:{t['header_bg']};border:0}}
QFrame#card{{background:{t['card']};border:1px solid {t['border']};border-radius:11px}} QFrame#panel{{background:{t['panel']};border:1px solid {t['border']};border-radius:9px}}
QFrame#hero{{background:{t['card']};border:1px solid {t['border_strong']};border-radius:13px}}
QFrame#topbar{{background:{t['bg']};border-bottom:1px solid {t['border']}}}
QGroupBox{{background:{t['panel']};border:1px solid {t['border']};border-radius:11px;margin-top:16px;padding:10px 8px 8px 8px}}
QGroupBox::title{{subcontrol-origin:margin;left:12px;padding:0 4px;color:{t['accent']};font-weight:800}}
QGroupBox QWidget{{background:transparent}} QGroupBox QLineEdit,QGroupBox QSpinBox,QGroupBox QComboBox{{background:{t['input']}}} QGroupBox QPushButton{{background:{t['button']}}}
QGroupBox QPushButton:hover{{background:{t['button_hover']}}}
QCheckBox,QRadioButton{{color:{t['text']};background:transparent}} QToolTip{{background:{t['panel']};color:{t['text']};border:1px solid {t['border']};border-radius:6px;padding:4px 6px}}
QStatusBar{{color:{t['subtext']};background:{t['bg']};border-top:1px solid {t['border']}}} QStatusBar QLabel{{background:transparent}}
QToolButton{{background:{t['button']};border:1px solid {t['border_strong']};border-radius:8px;padding:2px 8px;color:{t['text']}}} QToolButton:hover{{background:{t['button_hover']}}}
QProgressBar{{border:0;border-radius:4px;text-align:center;background:{t['track']};color:{t['text_strong']};max-height:14px}} QProgressBar::chunk{{background:{t['viewer_line']};border-radius:4px}}
QSlider::groove:horizontal{{height:4px;background:{t['track']};border-radius:2px}} QSlider::handle:horizontal{{background:#e51e63;width:12px;height:12px;margin:-4px 0;border-radius:6px}}
QSlider::sub-page:horizontal{{background:#e51e63;border-radius:2px}}
QTabWidget::pane{{border:1px solid {t['border']};border-radius:9px;top:-1px}} QTabBar::tab{{background:{t['tab_bg'] if 'tab_bg' in t else t['panel']};border:1px solid {t['border']};padding:6px 14px;border-radius:8px;margin:2px;color:{t['subtext']}}}
QTabBar::tab:selected{{background:{t['selection']};color:{t['text_strong']};border-color:{t['viewer_line']}}}
QScrollArea{{border:0;background:transparent}}
QScrollBar:vertical{{background:transparent;width:8px}} QScrollBar::handle:vertical{{background:{t['scroll']};border-radius:4px;min-height:28px}}
QScrollBar:horizontal{{background:transparent;height:8px}} QScrollBar::handle:horizontal{{background:{t['scroll']};border-radius:4px;min-width:28px}}
QScrollBar::add-line,QScrollBar::sub-line{{width:0;height:0}} QScrollBar::add-page,QScrollBar::sub-page{{background:transparent}}
QSplitter::handle{{background:{t['border']}}}
"""


STYLE = theme_qss('dark', 100)


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


def ui(fn):
    """在畫面執行緒執行（從背景執行緒呼叫）."""
    BUS.call.emit(fn)


def bg(fn, cb=None, err=None):
    def work():
        try: r = fn()
        except Exception as ex:
            r = ex
            try: ENG.log.err(f'背景工作 {getattr(fn, "__qualname__", fn)}')
            except Exception: pass
        if cb is not None:
            ui(lambda r=r: (cb(r) if not isinstance(r, Exception) else (err(r) if err else None)))
    threading.Thread(target=work, daemon=True).start()


ENG = None


# ============================================================ 圖片讀取（一條背景執行緒，後要的先讀）
class ImgLoader:
    def __init__(self):
        self.q = deque(); self.ev = threading.Event(); self.lock = threading.Lock()
        threading.Thread(target=self._loop, name='VsImgLoad', daemon=True).start()

    def want(self, key, path, cb):
        with self.lock:
            self.q.append((key, path, cb))
            while len(self.q) > 80:
                k, _p, c = self.q.popleft(); ui(lambda k=k, c=c: c(k, QImage()))      # 丟掉的告訴格子，之後會再要
        self.ev.set()

    def _loop(self):
        while True:
            self.ev.wait(); self.ev.clear()
            if getattr(self, 'stop', False): return                             # 熱更新：舊版的讀圖執行緒收掉，不要一直留在記憶體
            while True:
                with self.lock:
                    if not self.q: break
                    key, path, cb = self.q.pop()
                try: img = QImage(str(path))
                except Exception: img = QImage()
                ui(lambda key=key, img=img, cb=cb: cb(key, img))


LOADER = None

TAGS = OrderedDict([('red', ('🔴', '紅', '#ff4d6d')), ('orange', ('🟠', '橙', '#ff9a3c')), ('yellow', ('🟡', '黃', '#ffd84d')),
                    ('green', ('🟢', '綠', '#45d483')), ('blue', ('🔵', '藍', '#4d9dff')), ('purple', ('🟣', '紫', '#b48cff'))])


# ============================================================ 卡片縮圖：從預覽圖裡挑一張（隨機、每部固定；可以換），切出來存成 card_N.jpg，下次直接讀
class CardLoader:
    def __init__(self):
        self.q = deque(); self.ev = threading.Event(); self.lock = threading.Lock(); self.wanted = set()
        threading.Thread(target=self._loop, name='VsCardLoad', daemon=True).start()

    def want(self, key, job, cb):
        with self.lock:
            if key in self.wanted: return
            self.wanted.add(key); self.q.append((key, job, cb))
            while len(self.q) > 300:
                k, _j, _c = self.q.popleft(); self.wanted.discard(k)              # 捲過去沒看到的先丟掉，回來再要
        self.ev.set()

    def _loop(self):
        while True:
            self.ev.wait(); self.ev.clear()
            if getattr(self, 'stop', False): return                             # 熱更新：舊版的讀圖執行緒收掉，不要一直留在記憶體
            while True:
                with self.lock:
                    if not self.q: break
                    key, job, cb = self.q.pop()                                 # 後要的先做（＝畫面上正在看的）
                img = QImage()
                try: img = self._make(job)
                except Exception:
                    try: ENG.log.err(f'卡片縮圖 {job.get("dir")}')
                    except Exception: pass
                with self.lock: self.wanted.discard(key)
                ui(lambda key=key, img=img, cb=cb: cb(key, img))

    @staticmethod
    def _make(job):
        d = Path(job['dir']); k = int(job['k']); cp = d / f'card_{k}.jpg'
        if cp.exists():
            img = QImage(str(cp))
            if not img.isNull(): return img
        per = job['cols'] * job['rows']; sheets = sorted(d.glob('s*.jpg'))
        if not sheets: return QImage()
        si = min(len(sheets) - 1, k // per); q = k % per
        big = QImage(str(sheets[si]))
        if big.isNull(): return QImage()
        w, h = big.width() // job['cols'], big.height() // job['rows']
        img = big.copy((q % job['cols']) * w, (q // job['cols']) * h, w, h)
        if img.width() > 360: img = img.scaledToWidth(360, Qt.SmoothTransformation)
        if not job.get('nosave'):
            try: img.save(str(cp), 'JPG', 85)
            except Exception: pass
        return img


def invert_segs(segs, dur, min_len=0.5):
    """反過來剪：選的片段＝不要的，回傳其他要保留的片段（太短的 <0.5 秒丟掉）."""
    out = []; t = 0.0
    for a, b in sorted(segs):
        if a - t >= min_len: out.append((t, a))
        t = max(t, b)
    if dur and dur - t >= min_len: out.append((t, float(dur)))
    return out


def chunked(owner, key, n, fn, step=600, widget=None, done=None):
    """在畫面上分批做 fn(0..n-1)：每批 step 個，中間讓畫面喘口氣（不卡）。同一個 key 又開新的，舊的那批自動停."""
    gen = getattr(owner, '_chunk_' + key, 0) + 1; setattr(owner, '_chunk_' + key, gen)
    def run(i):
        if getattr(owner, '_chunk_' + key, None) != gen: return
        j = min(n, i + step)
        if widget is not None: widget.setUpdatesEnabled(False)
        try:
            for k in range(i, j): fn(k)
        except Exception:
            try: ENG.log.err(f'分批填表 {key}')
            except Exception: pass
            return
        finally:
            if widget is not None: widget.setUpdatesEnabled(True)
        if j < n: QTimer.singleShot(0, lambda: run(j))
        elif done is not None: done()
    run(0)


def lab_cfg():
    """實驗區的開關（引擎還沒好時當作全部關）."""
    try: return (ENG.cfg.get('lab') or {}) if ENG is not None else {}
    except Exception: return {}


def card_k(r):
    """這部卡片用第幾張預覽圖：自己換過就用那張；不然每部固定一張「隨機」的（避開頭尾 10%，常常是黑畫面或片頭）."""
    n = int(r.get('th_n') or 0)
    if n <= 0: return 0
    k = int(r.get('card_k') if r.get('card_k') is not None else -1)
    if 0 <= k < n: return k
    lo = int(n * 0.1); hi = max(lo, int(n * 0.9) - 1)
    return random.Random(int(r['id']) * 7919).randint(lo, hi)


class CardDelegate(QStyledItemDelegate):
    """一張卡片：縮圖（隨機一格）＋右上分級圓章＋邊框顏色＝分級；左上 ✔ 看過、⭐ 收藏；縮圖上 ✂ 已剪輯、右下長度；下面檔名、大小・解析度；左下顏色標籤."""
    def __init__(self, page):
        super().__init__(page.lst); self.pg = page

    def sizeHint(self, opt, idx):
        cw = self.pg.card_w; return QSize(cw, int((cw - 14) * 9 / 16) + 52)

    def paint(self, p, opt, idx):
        r = self.pg.row_of.get(idx.data(Qt.UserRole))
        if not r: return
        R = opt.rect.adjusted(3, 3, -3, -3); sel = bool(opt.state & QStyle.State_Selected); cur = r['id'] == (self.pg.cur or {}).get('id')
        p.save(); p.setRenderHint(QPainter.Antialiasing)
        gc = GC.get(r.get('grade') or '', '#2f3a4a')
        p.setPen(QPen(QColor('#ffffff') if cur else (QColor('#4dc9ff') if sel else QColor(gc)), 3 if (sel or cur) else 2))
        p.setBrush(QColor('#1f3550' if sel else '#151b24')); p.drawRoundedRect(R, 8, 8)
        IR = QRect(R.x() + 5, R.y() + 5, R.width() - 10, int((R.width() - 10) * 9 / 16))
        pm = None; scrub = self.pg.scrub if self.pg.scrub and self.pg.scrub[0] == r['id'] else None
        if scrub: pm = self.pg.cards.get((r['id'], scrub[1]))
        if pm is None or pm.isNull(): pm = self.pg.card_pix(r)
        if pm is not None and not pm.isNull():
            sw, sh = pm.width(), pm.height(); tar = IR.width() / max(1, IR.height())
            if sw / max(1, sh) > tar: cw_ = int(sh * tar); src = QRect((sw - cw_) // 2, 0, cw_, sh)
            else: ch_ = int(sw / tar); src = QRect(0, (sh - ch_) // 2, sw, ch_)
            path = QPainterPath(); path.addRoundedRect(QRectF(IR), 6, 6); p.setClipPath(path); p.drawPixmap(IR, pm, src); p.setClipping(False)
        else:
            p.setPen(Qt.NoPen); p.setBrush(QColor('#0c0f14')); p.drawRoundedRect(IR, 6, 6)
            st = int(r.get('th_state') or 0); p.setPen(QColor('#6c7a8c'))
            f = QFont(); f.setPixelSize(11); p.setFont(f)
            p.drawText(IR, Qt.AlignCenter, {0: '⏳ 預覽圖排隊', 1: '⚙ 做預覽圖中', 2: '…', 3: '✖ 預覽圖失敗', 4: '🔇 沒有畫面'}.get(st, ''))
        if scrub and int(r.get('th_n') or 0) > 1:                               # 🧪 滑過預覽：縮圖下緣一條位置條＋那一格的時間
            fr = scrub[1] / max(1, int(r['th_n']) - 1); p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 150)); p.drawRect(QRect(IR.x(), IR.bottom() - 3, IR.width(), 3))
            p.setBrush(QColor('#4dc9ff')); p.drawRect(QRect(IR.x(), IR.bottom() - 3, int(IR.width() * fr), 3))
        f = QFont(); f.setPixelSize(10); f.setBold(True); p.setFont(f)
        if scrub:
            t = fmt_t(scrub[1] * int(r.get('th_step') or 2)); tw = QFontMetrics(f).horizontalAdvance(t) + 8; TR = QRect(IR.x() + 2, IR.y() + 22, tw, 14)
            p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 170)); p.drawRoundedRect(TR, 4, 4); p.setPen(QColor('#4dc9ff')); p.drawText(TR, Qt.AlignCenter, t)
        if r.get('dur'):                                                        # 右下長度
            t = fmt_t(r['dur']); tw = QFontMetrics(f).horizontalAdvance(t) + 8; TR = QRect(IR.right() - tw - 2, IR.bottom() - 16, tw, 14)
            p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 170)); p.drawRoundedRect(TR, 4, 4); p.setPen(QColor('#ffffff')); p.drawText(TR, Qt.AlignCenter, t)
        x = R.x() + 4
        if r.get('viewed'):                                                     # 左上 ✔ 看過
            C = QRect(x, R.y() + 3, 17, 17); p.setPen(QPen(QColor('#0b0e13'), 1)); p.setBrush(QColor('#4dc9ff')); p.drawEllipse(C); p.setPen(QColor('#0b0e13')); p.drawText(C, Qt.AlignCenter, '✔'); x += 19
        if r.get('fav'):
            C = QRect(x, R.y() + 3, 17, 17); p.setPen(Qt.NoPen); p.setBrush(QColor('#ffc94d')); p.drawEllipse(C); p.setPen(QColor('#0b0e13')); p.drawText(C, Qt.AlignCenter, '★'); x += 19
        if float(r.get('up_t') or 0) > 0 and lab_cfg().get('copy_to'):        # V0.3.57 📤 已複製到上傳（綠色箭頭）
            pb_ = float(r.get('pub_t') or 0) > 0                                 # V0.4.24 已發佈＝藍綠色 ✓，只複製＝綠色 ↑
            C = QRect(x, R.y() + 3, 17, 17); p.setPen(Qt.NoPen); p.setBrush(QColor('#3fd0c9' if pb_ else '#4dd68a')); p.drawEllipse(C); p.setPen(QColor('#0b0e13')); p.drawText(C, Qt.AlignCenter, '✓' if pb_ else '↑')
        if r.get('grade'):                                                      # 右上分級圓章
            C = QRect(R.right() - 21, R.y() + 3, 18, 18); p.setPen(QPen(QColor('#0b0e13'), 1)); p.setBrush(QColor(gc)); p.drawEllipse(C)
            p.setPen(QColor('#0b0e13')); p.drawText(C, Qt.AlignCenter, r['grade'])
        if r.get('note'):
            C = QRect(R.right() - (42 if r.get('grade') else 21), R.y() + 3, 18, 18); p.setPen(Qt.NoPen); p.setBrush(QColor('#b48cff')); p.drawEllipse(C)
            p.setPen(QColor('#0b0e13')); p.drawText(C, Qt.AlignCenter, '✎')
        pend = (getattr(self.pg, 'cut_pend', None) or {}).get(r['id'], 0); done_n = int(r.get('cut_n') or 0)
        if pend or done_n:                                                      # V0.2.02 剪了幾段（分級圓章旁邊）：剪輯中＝橘色「-剪輯 N」、剪好＝藍色「√剪輯 N」
            t = f'{"-" if pend else "√"}剪輯{done_n + pend}'; fb = QFont(); fb.setPixelSize(10); fb.setBold(True); p.setFont(fb)
            tw = QFontMetrics(fb).horizontalAdvance(t) + 10; xr = R.right() - 3 - (21 if r.get('grade') else 0) - (21 if r.get('note') else 0)
            TR = QRect(xr - tw, R.y() + 4, tw, 16); p.setPen(Qt.NoPen); p.setBrush(QColor('#f0a030' if pend else '#2f8fe0')); p.drawRoundedRect(TR, 4, 4)
            p.setPen(QColor('#0b0e13' if pend else '#ffffff')); p.drawText(TR, Qt.AlignCenter, t); p.setFont(f)
        ty = IR.bottom() + 4; tx = R.x() + 6; tw_all = R.width() - 12
        if r.get('tag') in TAGS:                                                # 顏色標籤：檔名前一個色點
            p.setPen(Qt.NoPen); p.setBrush(QColor(TAGS[r['tag']][2])); p.drawEllipse(QRect(tx, ty + 4, 9, 9)); tx += 12; tw_all -= 12
        f1 = QFont(); f1.setPixelSize(11); p.setFont(f1); p.setPen(QColor('#ffffff') if not r.get('viewed') else QColor('#dfe5ee'))
        p.drawText(QRect(tx, ty, tw_all, 16), Qt.AlignLeft | Qt.AlignVCenter, QFontMetrics(f1).elidedText(r['name'], Qt.ElideMiddle, tw_all))
        f2 = QFont(); f2.setPixelSize(10); p.setFont(f2); p.setPen(QColor('#8a96a8'))
        info = f"{fmt_b(r.get('size'))}" + (f" · {r['w']}×{r['h']}" if r.get('w') else '') + f" · {str(r.get('ext') or '')[1:]}"
        p.drawText(QRect(R.x() + 6, ty + 16, R.width() - 12, 15), Qt.AlignLeft | Qt.AlignVCenter, QFontMetrics(f2).elidedText(info, Qt.ElideRight, R.width() - 12))
        p.restore()


# ============================================================ 預覽圖格子（每 2 秒一格）
class ThumbGrid(QWidget):
    """預覽格子。預覽圖都是用原本的間隔（通常 2 秒）做好的；「顯示間隔」只是每 k 張拿 1 張出來排，不用重做.
    選取（V0.1.08）：點一格＝選它；點已選的格＝取消；按住拖曳＝圈選一段（從按下的格到放開的格，照時間順序）；
    從已選的格按住拖曳＝把拖過的取消。選取記在「原本那一張」的編號上，換間隔時不會亂掉；連在一起的格子就是一段."""
    play = Signal(float)
    segsChanged = Signal()
    colsChanged = Signal(int)
    hint = Signal(str)
    secWheel = Signal(int)
    LABEL_H = 16
    FCACHE_MAX = 1500

    def __init__(self):
        super().__init__(); self.setMouseTracking(True); self.setFocusPolicy(Qt.StrongFocus)
        self.fid = None; self.n = 0; self.step = 2; self.dur = 0; self.cs = 10; self.rs = 10; self.sheets = []; self.ar = 16 / 9
        self.fw = 0; self.fh = 0; self.cols = 10; self.vw = 800; self.cache = OrderedDict(); self.fcache = OrderedDict(); self.loading = set(); self.gen = 0
        self.sec = 2; self.k = 1; self.nd = 0; self.area = None
        self.sel = set(); self.anchor = None; self.hover = -1; self.press = None; self.lp_fired = False; self.drag = None; self._undo = None
        self.lp = QTimer(self); self.lp.setSingleShot(True); self.lp.timeout.connect(self._long_press)
        self.dt = QTimer(self); self.dt.timeout.connect(self._drag_tick)
        self.zt = QTimer(self); self.zt.setSingleShot(True); self.zt.timeout.connect(self._zoom_show); self.zoom = None; self.kcur = None

    bm_ts = ()                                                                  # V0.2.96 🔖 書籤時間（秒）
    sc_bs = frozenset()                                                         # V0.3.09 🎬 換場景的預覽圖編號
    st_bs = frozenset()                                                         # V0.3.11 😴 靜止的預覽圖編號
    hl_bs = frozenset()                                                         # V0.3.16 🔥 動得多的預覽圖編號

    def set_video(self, r, sheets):
        self.gen += 1; self.cache.clear(); self.fcache.clear(); self.loading.clear(); self.sel = set(); self.anchor = None; self.hover = -1; self.drag = None
        try: self.bm_ts = tuple(t for t, _n in ENG.bm_list(r['id'])) if (r and lab_cfg().get('bookmarks')) else ()
        except Exception: self.bm_ts = ()
        self.sc_bs = frozenset()
        if r and lab_cfg().get('scenes') and int(r.get('th_state') or 0) == 2:
            fid_ = r['id']; self.st_bs = frozenset()
            self.hl_bs = frozenset()
            bg(lambda: (ENG.scene_cuts(fid_), ENG.static_runs(fid_), ENG.highlights(fid_)), lambda L: (setattr(self, 'sc_bs', frozenset(L[0])), setattr(self, 'st_bs', frozenset(b_ for a_, z_ in L[1] for b_ in range(a_, z_ + 1))), setattr(self, 'hl_bs', frozenset(L[2])), self.update()) if self.fid == fid_ else None)
        self.fid = r['id'] if r else None; self.n = int(r.get('th_n') or 0) if r else 0; self.step = max(1, int(r.get('th_step') or 2)) if r else 2
        self.dur = float(r.get('dur') or 0) if r else 0; self.cs = int(r.get('th_cols') or 10) if r else 10; self.rs = int(r.get('th_rows') or 10) if r else 10
        self.sheets = list(sheets or []); self.fw = self.fh = 0
        w, h = (int(r.get('w') or 0), int(r.get('h') or 0)) if r else (0, 0); self.ar = (w / h) if w and h else 16 / 9
        self._calc_k(); self.relayout(); self.segsChanged.emit(); self.update()

    # ---- 顯示間隔
    def _calc_k(self):
        self.k = max(1, int(float(self.sec) / self.step + 0.5)); self.nd = math.ceil(self.n / self.k) if self.n else 0

    def set_sec(self, sec):
        """每幾秒顯示一張（會對齊到原本間隔的倍數）。回傳實際的秒數."""
        self.sec = max(1, int(sec)); k0 = self.k; self._calc_k()
        if self.k != k0:
            self.gen += 1; self.loading.clear(); self.fcache.clear(); self.hover = -1; self.relayout()
        return self.k * self.step

    def real_sec(self): return self.k * self.step

    # ---- 編號換算：i＝畫面上第幾格，b＝原本第幾張
    def b_of(self, i): return min(max(0, self.n - 1), i * self.k)

    def b_end(self, i): return min(max(0, self.n - 1), i * self.k + self.k - 1)

    def d_of(self, b): return b // self.k

    def tile_bs(self, i): return range(self.b_of(i), self.b_end(i) + 1)

    def set_cols(self, c):
        self.cols = max(2, min(30, int(c))); self.relayout(); self.colsChanged.emit(self.cols)

    def tile_size(self):
        tw = max(40, self.vw // max(1, self.cols)); ih = max(20, int(tw / max(0.2, self.ar))); return tw, ih + self.LABEL_H

    def relayout(self, vw=None):
        if vw: self.vw = max(200, int(vw))
        tw, th = self.tile_size(); rows = math.ceil(self.nd / self.cols) if self.nd else 0
        self.setFixedSize(self.vw, max(10, min(16000000, rows * th))); self.update()
        fit = getattr(self.area, 'fit', None)
        if callable(fit): fit()

    def rect_of(self, i):
        tw, th = self.tile_size(); return QRect((i % self.cols) * tw, (i // self.cols) * th, tw, th)

    def index_at(self, pos):
        tw, th = self.tile_size(); c = pos.x() // tw; r = pos.y() // th
        if c < 0 or c >= self.cols or r < 0: return -1
        i = r * self.cols + c; return i if 0 <= i < self.nd else -1

    def index_near(self, pos):
        """拖曳用：滑鼠跑出格子外面時，算最近的那一格."""
        if not self.nd: return -1
        tw, th = self.tile_size(); rows = math.ceil(self.nd / self.cols)
        c = max(0, min(self.cols - 1, pos.x() // tw)); r = max(0, min(rows - 1, pos.y() // th)); return min(self.nd - 1, r * self.cols + c)

    def t_of(self, i): return self.b_of(i) * self.step

    def anchor_t(self): return (self.anchor or 0) * self.step

    # ---- 選取 → 片段
    @property
    def segs(self):
        """連在一起的選取＝一段：[(第一張, 最後一張)]（原本的編號）."""
        out = []
        for b in sorted(self.sel):
            if out and b == out[-1][1] + 1: out[-1] = (out[-1][0], b)
            else: out.append((b, b))
        return out

    def seg_times(self):
        return [(a * self.step, min(self.dur or 1e12, b * self.step + self.step)) for a, b in self.segs]

    def in_seg(self, i): return any(b in self.sel for b in self.tile_bs(i))

    def _hit(self, i):
        lo, hi = self.b_of(i), self.b_end(i); return [k for k, (a, b) in enumerate(self.segs) if a <= hi and b >= lo]

    def _range_bs(self, i, j):
        lo, hi = sorted((i, j)); return set(range(self.b_of(lo), self.b_end(hi) + 1))

    def _sel_hint(self):
        S = self.seg_times()
        if not S: self.hint.emit('點一格＝選；再點＝取消；按住拖曳＝圈選一段；從已選的格拖＝取消拖過的；長按或點兩下＝播放'); return
        self.hint.emit(f'已選 {len(S)} 段，共 {fmt_t(sum(b - a for a, b in S))}：' + '、'.join(f'{fmt_t(a)}～{fmt_t(b)}' for a, b in S[:6]) + ('…' if len(S) > 6 else ''))

    def _want(self, si):
        if si in self.loading or si >= len(self.sheets): return
        self.loading.add(si); g = self.gen
        LOADER.want((g, si), self.sheets[si], self._loaded)

    def _loaded(self, key, img):
        g, si = key
        if g != self.gen: return
        self.loading.discard(si)
        if img.isNull(): return
        pm = QPixmap.fromImage(img)
        fw, fh = pm.width() // self.cs, pm.height() // self.rs
        if fw and fh and (fw, fh) != (self.fw, self.fh):
            self.fw, self.fh = fw, fh; ar = fw / fh
            if abs(ar - self.ar) > 0.02: self.ar = ar; self.relayout()
        if self.k == 1:                                                         # 原本的間隔：整張大圖留著用
            self.cache[si] = pm
            while len(self.cache) > 12: self.cache.popitem(last=False)
        elif fw and fh:                                                         # 拉大間隔：只把要顯示的那幾張切出來留著，大圖丟掉（省記憶體）
            per = self.cs * self.rs; b0 = si * per; first = -(-b0 // self.k) * self.k
            for b in range(first, min(self.n, b0 + per), self.k):
                q = b - b0; self.fcache[b] = pm.copy((q % self.cs) * fw, (q // self.cs) * fh, fw, fh)
            while len(self.fcache) > self.FCACHE_MAX: self.fcache.popitem(last=False)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); r = e.rect(); tw, th = self.tile_size(); per = self.cs * self.rs
        p.fillRect(r, QColor('#0b0e13'))
        if not self.nd: p.end(); return
        r0 = max(0, r.top() // th); r1 = r.bottom() // th
        f = QFont(); f.setPixelSize(11); p.setFont(f)
        ad = self.d_of(self.anchor) if self.anchor is not None else None
        for i in range(r0 * self.cols, min(self.nd, (r1 + 1) * self.cols)):
            R = self.rect_of(i); img = QRect(R.x() + 1, R.y() + 1, R.width() - 2, R.height() - self.LABEL_H - 2)
            b = self.b_of(i); si = b // per
            if self.k == 1:
                pm = self.cache.get(si)
                if pm is not None and self.fw:
                    self.cache.move_to_end(si); q = b % per
                    p.drawPixmap(img, pm, QRect((q % self.cs) * self.fw, (q // self.cs) * self.fh, self.fw, self.fh))
                else: p.fillRect(img, QColor('#1a2029')); self._want(si)
            else:
                fp = self.fcache.get(b)
                if fp is not None: self.fcache.move_to_end(b); p.drawPixmap(img, fp)
                else: p.fillRect(img, QColor('#1a2029')); self._want(si)
            if self.in_seg(i):
                full = all(x in self.sel for x in self.tile_bs(i))
                p.fillRect(img, QColor(77, 201, 255, 70 if full else 35)); p.setPen(QPen(QColor('#4dc9ff'), 2 if full else 1)); p.drawRect(img.adjusted(1, 1, -1, -1))
            if ad == i: p.setPen(QPen(QColor('#ffc94d'), 2, Qt.DashLine)); p.drawRect(img.adjusted(2, 2, -2, -2))
            if self.hover == i: p.setPen(QPen(QColor(255, 255, 255, 120), 1)); p.drawRect(img.adjusted(0, 0, -1, -1))
            if self.kcur == i and self.hasFocus(): p.setPen(QPen(QColor('#ffffff'), 2, Qt.DotLine)); p.drawRect(img.adjusted(3, 3, -3, -3))
            p.setPen(QColor('#4dc9ff') if self.in_seg(i) else QColor('#9fb0c4'))
            p.drawText(QRect(R.x() + 3, R.bottom() - self.LABEL_H + 1, R.width() - 4, self.LABEL_H - 1), Qt.AlignLeft | Qt.AlignVCenter, fmt_t(self.t_of(i)))
            if self.st_bs and all(b_ in self.st_bs for b_ in self.tile_bs(i)):  # V0.3.11 😴 靜止／全黑：蓋一層灰
                p.fillRect(img, QColor(10, 12, 16, 150)); p.setPen(QColor('#9aa0a6')); p.drawText(img, Qt.AlignCenter, '😴')
            if self.hl_bs and any(b_ in self.hl_bs for b_ in self.tile_bs(i)):   # V0.3.16 🔥 動得多：下面紅線
                p.fillRect(QRect(img.left(), img.bottom() - 3, img.width(), 4), QColor('#ff4d6d'))
            if self.sc_bs and any(b_ in self.sc_bs for b_ in self.tile_bs(i)):   # V0.3.09 🎬 換場景：左邊橘線
                p.fillRect(QRect(img.left(), img.top(), 4, img.height()), QColor('#ff8a3c'))
            if self.bm_ts:                                                      # V0.2.96 🔖 這格裡有書籤：右上角黃色標記
                t0_ = self.t_of(i); t1_ = (self.b_end(i) + 1) * self.step
                if any(t0_ <= t_ < t1_ for t_ in self.bm_ts):
                    p.setPen(Qt.NoPen); p.setBrush(QColor('#ffc94d')); p.drawRect(QRect(img.right() - 12, img.top() + 2, 10, 14)); p.setBrush(Qt.NoBrush)
        p.end()

    # ---- 滑鼠
    def mousePressEvent(self, e):
        pos = e.position().toPoint()
        self._zoom_hide()
        if e.button() == Qt.LeftButton:
            i = self.index_at(pos)
            self.press = (pos, i); self.lp_fired = False; self.drag = None
            if i >= 0: self.lp.start(450)
        elif e.button() == Qt.RightButton:
            self._menu(self.index_at(pos), e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint(); i = self.index_at(pos)
        if i != self.hover:
            self.hover = i; self.update(); self._zoom_hide()
            zoom_on = lab_cfg().get('grid_zoom')
            if i >= 0 and self.drag is None and not zoom_on: self.setToolTip(f'{fmt_t(self.t_of(i))}　點＝選／取消　按住拖曳＝圈選　長按或點兩下＝從這裡播放　右鍵＝更多')
            if i >= 0 and self.drag is None and zoom_on and not self.press: self.setToolTip(''); self.zt.start(int(lab_cfg().get('grid_zoom_ms') or 2500))     # V0.2.17 停 2.5 秒才放大
        if self.press and self.press[1] >= 0 and not self.lp_fired:
            if self.drag is None and (pos - self.press[0]).manhattanLength() > 8:
                i0 = self.press[1]; self.lp.stop()
                self.drag = {'i0': i0, 'mode': 'del' if self.in_seg(i0) else 'add', 'sel0': set(self.sel), 'last': -1}
                self._undo = set(self.sel); self.dt.start(40)
            if self.drag is not None: self._drag_to(pos)

    def _drag_to(self, pos):
        j = self.index_near(pos)
        if j < 0 or j == self.drag['last']: return
        self.drag['last'] = j; R = self._range_bs(self.drag['i0'], j)
        self.sel = (self.drag['sel0'] | R) if self.drag['mode'] == 'add' else (self.drag['sel0'] - R)
        lo, hi = sorted((self.drag['i0'], j))
        self.hint.emit(f'{"圈選" if self.drag["mode"] == "add" else "取消"} {fmt_t(self.t_of(lo))} ～ {fmt_t(min(self.dur or 1e12, (self.b_end(hi) + 1) * self.step))}（放開完成）')
        self.update()

    def _drag_tick(self):
        """拖到上下邊緣：自動捲動，繼續圈選."""
        if self.drag is None or self.area is None: self.dt.stop(); return
        vp = self.area.viewport(); lp = vp.mapFromGlobal(QCursor.pos()); h = vp.height(); sb = self.area.verticalScrollBar(); d = 0
        if lp.y() < 30: d = -max(8, (30 - lp.y()) * 2)
        elif lp.y() > h - 30: d = max(8, (lp.y() - h + 30) * 2)
        if d:
            sb.setValue(sb.value() + int(d)); self._drag_to(self.mapFromGlobal(QCursor.pos()))

    def leaveEvent(self, e):
        self.hover = -1; self.update(); self._zoom_hide()

    def _tile_pix(self, i):
        b = self.b_of(i)
        if self.k == 1:
            pm = self.cache.get(b // (self.cs * self.rs))
            if pm is None or not self.fw: return None
            q = b % (self.cs * self.rs); return pm.copy((q % self.cs) * self.fw, (q // self.cs) * self.fh, self.fw, self.fh)
        return self.fcache.get(b)

    def _zoom_show(self):
        """🧪 格子放大預覽：滑鼠停在一格上一下，旁邊跳出放大的那一格（預覽圖本來就是這個大小，放大會比較糊）."""
        i = self.hover
        if i < 0 or self.drag is not None or self.press: return
        if time.monotonic() - getattr(self, '_scroll_t', 0) < 1.5: self.zt.start(2500); return      # V0.2.17 滾動中（或剛滾完）不放大
        pm = self._tile_pix(i)
        if pm is None or pm.isNull(): return
        if self.zoom is None:
            self.zoom = QLabel(None, Qt.ToolTip | Qt.FramelessWindowHint); self.zoom.setStyleSheet('QLabel{border:2px solid #4dc9ff;background:#0b0e13;color:#ffffff}')
        w = int(lab_cfg().get('grid_zoom_w') or 480); big = pm.scaledToWidth(w, Qt.SmoothTransformation)
        self.zoom.setPixmap(big); self.zoom.resize(big.width() + 4, big.height() + 4)
        gp = QCursor.pos(); scr = QApplication.screenAt(gp); x, y = gp.x() + 18, gp.y() + 18
        if scr is not None:
            g = scr.availableGeometry()
            if x + big.width() > g.right(): x = gp.x() - big.width() - 22
            if y + big.height() > g.bottom(): y = gp.y() - big.height() - 22
        self.zoom.move(x, y); self.zoom.show(); self.zoom.setToolTip(fmt_t(self.t_of(i)))

    def _zoom_hide(self):
        self.zt.stop()
        if self.zoom is not None: self.zoom.hide()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self.press: return
        self.lp.stop(); self.dt.stop(); pos, i = self.press; self.press = None
        if self.drag is not None:
            self.drag = None; self.segsChanged.emit(); self._sel_hint(); self.update(); return
        if self.lp_fired or i < 0: return
        self.click(i, bool(e.modifiers() & Qt.ShiftModifier))

    def mouseDoubleClickEvent(self, e):
        self.lp.stop(); i = self.index_at(e.position().toPoint())
        if i >= 0:
            if self._undo is not None: self.sel = set(self._undo); self._undo = None; self.segsChanged.emit()   # 點兩下＝播放，不算選取
            self.play.emit(float(self.t_of(i))); self.update()

    def _long_press(self):
        if self.press and self.press[1] >= 0 and self.drag is None: self.lp_fired = True; self.play.emit(float(self.t_of(self.press[1])))

    def click(self, i, shift=False):
        """點一格：沒選就選、已選就取消；Shift＋點＝從上一次點的格子到這格全部選起來."""
        self._undo = set(self.sel); bs = set(self.tile_bs(i))
        if shift and self.anchor is not None: self.sel |= self._range_bs(self.d_of(self.anchor), i)
        elif self.in_seg(i): self.sel -= bs
        else: self.sel |= bs
        self.anchor = self.b_of(i); self.segsChanged.emit(); self._sel_hint(); self.update()

    def keyPressEvent(self, e):
        """🧪 鍵盤操作格子：方向鍵移動、空白鍵選／取消、Shift＋方向鍵連續選、Enter 從這格播放、Home／End."""
        if not lab_cfg().get('grid_keys') or not self.nd: return super().keyPressEvent(e)
        k = e.key(); shift = bool(e.modifiers() & Qt.ShiftModifier); cur = self.kcur if self.kcur is not None else (self.hover if self.hover >= 0 else 0)
        moves = {Qt.Key_Left: -1, Qt.Key_Right: 1, Qt.Key_Up: -self.cols, Qt.Key_Down: self.cols}
        if k in moves or k in (Qt.Key_Home, Qt.Key_End):
            new = 0 if k == Qt.Key_Home else (self.nd - 1 if k == Qt.Key_End else max(0, min(self.nd - 1, cur + moves[k])))
            if shift:
                if self.kcur is None or self.anchor is None: self.anchor = self.b_of(cur)
                self._undo = set(self.sel); self.sel |= self._range_bs(self.d_of(self.anchor), new); self.segsChanged.emit(); self._sel_hint()
            self.kcur = new; R = self.rect_of(new)
            if self.area is not None: self.area.ensureVisible(R.center().x(), R.center().y(), 10, R.height())
            self.update(); return
        if k == Qt.Key_Space: self.kcur = cur; self.click(cur); return
        if k in (Qt.Key_Return, Qt.Key_Enter): self.play.emit(float(self.t_of(cur))); return
        super().keyPressEvent(e)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.set_cols(self.cols + (-1 if e.angleDelta().y() > 0 else 1)); self.hint.emit(f'一列 {self.cols} 張'); e.accept(); return
        if e.modifiers() & Qt.AltModifier:                                      # Alt＋滾輪＝顯示間隔
            d = e.angleDelta().y() or e.angleDelta().x()
            if d: self.secWheel.emit(1 if d < 0 else -1)
            e.accept(); return
        e.ignore()

    def _select_scene(self, i):
        b = self.b_of(i); C = sorted(self.sc_bs); a = max([0] + [x for x in C if x <= b]); z = min([self.n] + [x for x in C if x > b]) - 1
        self.sel |= set(range(a, max(a, z) + 1)); self._changed(); self.hint.emit(f'🎬 選了 {fmt_t(a * self.step)}～{fmt_t((z + 1) * self.step)}')

    def _menu(self, i, gp):
        m = QMenu(self)
        if i >= 0:
            m.addAction(f'▶ 從 {fmt_t(self.t_of(i))} 播放', lambda: self.play.emit(float(self.t_of(i))))
            hit = self._hit(i)
            if hit:
                a, b = self.segs[hit[0]]
                m.addAction(f'刪掉這一段（{fmt_t(a * self.step)}～{fmt_t(min(self.dur or 1e12, (b + 1) * self.step))}）', lambda a=a, b=b: self._drop_range(a, b))
            if self.fid: m.addAction(f'📷 存這一格截圖（原尺寸，{fmt_t(self.t_of(i))}）', lambda: bg(lambda: ENG.snap_at(self.fid, float(self.t_of(i))), lambda r_: self.hint.emit(r_[1])))   # V0.3.35
            m.addAction('從這格選到最後', lambda: self._select_to_end(i))
            m.addAction('從開頭選到這格', lambda: self._select_from_start(i))
            if self.sc_bs:                                                      # V0.3.10 🎬 選整個場景（這格所在的那一段，到下一個換場景為止）
                m.addAction('🎬 選這整個場景', lambda: self._select_scene(i))
        if self.hl_bs and self.n: m.addAction(f'🔥 選畫面動得最多的地方（{len(self.hl_bs)} 格，前後各多 1 格）', lambda: (self.sel.update(b2 for b_ in self.hl_bs for b2 in range(max(0, b_ - 1), min(self.n, b_ + 2))), self._changed()))   # V0.3.16
        if self.st_bs and self.n: m.addAction(f'✂ 選全部、跳過 😴 靜止的（{len(self.st_bs) * self.step // 60} 分鐘）', lambda: (setattr(self, 'sel', set(b_ for b_ in range(self.n) if b_ not in self.st_bs)), self._changed()))   # V0.3.11
        if self.n: m.addAction('全選', self.select_all); m.addAction('反選', self.invert)
        if self.sel: m.addAction('清除全部選取', self.clear_sel)
        m.exec(gp); m.deleteLater()

    def _changed(self):
        self.segsChanged.emit(); self._sel_hint(); self.update()

    def _drop_range(self, a, b): self._undo = set(self.sel); self.sel -= set(range(a, b + 1)); self._changed()

    def _select_to_end(self, i): self._undo = set(self.sel); self.sel |= set(range(self.b_of(i), self.n)); self._changed()

    def _select_from_start(self, i): self._undo = set(self.sel); self.sel |= set(range(0, self.b_end(i) + 1)); self._changed()

    def select_all(self): self._undo = set(self.sel); self.sel = set(range(self.n)); self._changed()

    def invert(self): self._undo = set(self.sel); self.sel = set(range(self.n)) - self.sel; self._changed()

    def clear_sel(self):
        self.sel = set(); self.anchor = None; self._changed()

    def add_seg_t(self, ta, tb):
        last = max(0, self.n - 1); a = min(int(ta // self.step), last); b = min(max(a, int(max(ta, tb - 0.01) // self.step)), last)
        self.sel |= set(range(a, b + 1)); self._changed()


class GridArea(QScrollArea):
    """V0.2.09 裡面放一個容器：目前這部的格子＋（📜 連續分級）分隔列＋下一部的格子（只看不能點）."""
    def __init__(self, grid):
        super().__init__(); self.grid = grid; self.nxt = None; self.nxt2 = None; self.sep_on = False; self._fitting = False
        self.box = QWidget(); grid.setParent(self.box); grid.move(0, 0); grid.area = self
        self.sep = QLabel('', self.box); self.sep.setAlignment(Qt.AlignCenter); self.sep.setWordWrap(True)
        self.sep.setStyleSheet('QLabel{color:#4dc9ff;font-weight:700;font-size:13px;background:#0b0e13;border-top:1px dashed #2f3a4a}'); self.sep.hide()
        self.sep2 = QLabel('', self.box); self.sep2.setAlignment(Qt.AlignCenter); self.sep2.setWordWrap(True)
        self.sep2.setStyleSheet('QLabel{color:#8a96a8;font-weight:700;font-size:13px;background:#0b0e13;border-top:1px dashed #2f3a4a}'); self.sep2.hide()
        self.setWidget(self.box); self.setWidgetResizable(False); self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.verticalScrollBar().setSingleStep(60)
        self.verticalScrollBar().valueChanged.connect(self._scrolled)

    def _scrolled(self, _v):
        """V0.2.17 一滾動就把放大圖關掉，滾完 1.5 秒內也不放大."""
        now = time.monotonic()
        for g in (self.grid, self.nxt):
            if g is None: continue
            g._scroll_t = now
            try: g._zoom_hide()
            except Exception: pass

    def set_follower(self, g):
        self.nxt = g; g.setParent(self.box); g.area = self; g.hide()

    def set_follower2(self, g):
        self.nxt2 = g; g.setParent(self.box); g.area = self; g.hide()

    def sep_h(self):
        return self.grid.tile_size()[1] if self.sep_on else 0                    # 空一行（一格的高度）

    def fit(self):
        if self._fitting: return
        self._fitting = True
        try:
            w = max(self.grid.width(), 200); y = self.grid.height()
            if self.sep_on: self.sep.setGeometry(0, y, w, self.sep_h()); self.sep.show(); self.sep.raise_(); y += self.sep_h()
            else: self.sep.hide()
            if self.nxt is not None and self.nxt.isVisible():
                self.nxt.move(0, y); y += self.nxt.height()
                if self.nxt2 is not None and self.nxt2.isVisible():                # V0.2.20 一次接兩部
                    self.sep2.setGeometry(0, y, w, self.sep_h()); self.sep2.show(); self.sep2.raise_(); y += self.sep_h(); self.nxt2.move(0, y); y += self.nxt2.height()
                else: self.sep2.hide()
                y = max(y, self.grid.height() + self.sep_h() + self.viewport().height())   # V0.2.16 下一部很短時也要能把上一部整個滾出去（不然卡住、接不到下一部）
            else: self.sep2.hide()
            self.box.setFixedSize(w, max(10, y))
        finally: self._fitting = False

    def resizeEvent(self, e):
        super().resizeEvent(e); self.grid.relayout(self.viewport().width())
        if self.nxt is not None: self.nxt.relayout(self.viewport().width())
        if self.nxt2 is not None: self.nxt2.relayout(self.viewport().width())
        self.fit()


# ============================================================ 播放器
# 播放器的動作：(名稱, 需不需要秒數)
PLAYER_ACTIONS = OrderedDict([
    ('seek', ('跳秒數（負數＝往回）', True)), ('play', ('播放／暫停', False)), ('vol_up', ('音量 +5%', False)), ('vol_down', ('音量 −5%', False)), ('mute', ('靜音', False)),
    ('speed_up', ('加速 +0.1 倍', False)), ('speed_down', ('減速 −0.1 倍', False)), ('speed_reset', ('速度回到 1 倍', False)),
    ('frame_next', ('下一格（暫停）', False)), ('frame_prev', ('上一格（暫停）', False)), ('home', ('跳到開頭', False)), ('end', ('跳到最後 5 秒', False)),
    ('mark_a', ('這裡當起點', False)), ('mark_b', ('這裡當終點（加入一段）', False)), ('snap', ('截圖（存到 VideoSIFT\\截圖）', False)),
    ('full', ('全螢幕／還原', False)), ('close', ('關閉（全螢幕時先還原）', False)),
    ('ab_loop', ('A-B 重複播放（第 1 下起點、第 2 下終點開始重複、第 3 下取消）', False)), ('pct', ('跳到全片的幾 %（數字＝百分比）', True)),
    ('seek_pct', ('前後跳全片的幾 %（負數＝往回）', True)), ('speed_fine', ('速度微調（1＝每下 +0.01 倍，按住越加越快；負數＝減慢）', True))])          # V0.1.46
DEFAULT_KEYS = [  # V0.1.57 照你要的：方向鍵 1 秒、Ctrl 5 秒、Shift 1%、Ctrl＋Shift 5%；Ctrl＋上下＝速度 ±0.01 倍（按住越加越快）
    ('Space', 'play', 0), ('Left', 'seek', -1), ('Right', 'seek', 1), ('Ctrl+Left', 'seek', -5), ('Ctrl+Right', 'seek', 5),
    ('Shift+Left', 'seek_pct', -1), ('Shift+Right', 'seek_pct', 1), ('Ctrl+Shift+Left', 'seek_pct', -5), ('Ctrl+Shift+Right', 'seek_pct', 5),
    ('PgUp', 'seek', -60), ('PgDown', 'seek', 60), ('Up', 'vol_up', 0), ('Down', 'vol_down', 0), ('Ctrl+Up', 'speed_fine', 1), ('Ctrl+Down', 'speed_fine', -1), ('M', 'mute', 0),
    ('C', 'speed_up', 0), ('X', 'speed_down', 0), ('Z', 'speed_reset', 0), ('F', 'frame_next', 0), ('D', 'frame_prev', 0),
    ('Home', 'home', 0), ('End', 'end', 0), ('I', 'mark_a', 0), ('O', 'mark_b', 0), ('Ctrl+E', 'snap', 0),
    ('Return', 'full', 0), ('F11', 'full', 0), ('Esc', 'close', 0), ('R', 'ab_loop', 0)] + [(f'Ctrl+{i}', 'pct', i * 10) for i in range(1, 10)]
KEYS_V57 = {'left': ('seek', -1), 'right': ('seek', 1), 'ctrl+left': ('seek', -5), 'ctrl+right': ('seek', 5), 'shift+left': ('seek_pct', -1), 'shift+right': ('seek_pct', 1),
            'ctrl+shift+left': ('seek_pct', -5), 'ctrl+shift+right': ('seek_pct', 5), 'ctrl+up': ('speed_fine', 1), 'ctrl+down': ('speed_fine', -1)}
NEW_KEYS = {'ab_loop': '0.1.46', 'pct': '0.1.46'}                               # 自己改過快捷鍵的人：新動作也補上預設鍵（鍵沒被用掉才補）


def player_keys():
    K = ENG.cfg.get('player_keys')
    if not isinstance(K, list) or not K: return [list(x) for x in DEFAULT_KEYS]
    if not ENG.cfg.get('keys_v57'):                                             # V0.1.57 你指定的新方向鍵：自己改過快捷鍵的人也換成新的
        try:
            K2 = [list(x) for x in K if isinstance(x, (list, tuple)) and len(x) == 3 and str(x[0]).lower().replace(' ', '') not in KEYS_V57]
            nm = {k.lower(): k for k, _a, _n in DEFAULT_KEYS}
            for k, (a, n) in KEYS_V57.items(): K2.append([nm.get(k, k), a, n])
            ENG.cfg.set('player_keys', K2); K = K2; ENG.log.w('播放器快捷鍵：方向鍵換成 1 秒／Ctrl 5 秒／Shift 1%／Ctrl+Shift 5%、Ctrl+上下＝速度微調')
        except Exception: ENG.log.err('播放器快捷鍵更新')
        ENG.cfg.set('keys_v57', True)
    K = [list(x) for x in K if isinstance(x, (list, tuple)) and len(x) == 3 and x[1] in PLAYER_ACTIONS]
    have = {x[1] for x in K}; used = {str(x[0]).lower() for x in K}; seen = set(ENG.cfg.get('player_keys_seen') or [])
    for k, a, n in DEFAULT_KEYS:
        if a in NEW_KEYS and a not in have and a not in seen and k.lower() not in used: K.append([k, a, n]); used.add(k.lower())
    return K


def key_help(K):
    def one(k, a, n):
        nm = PLAYER_ACTIONS[a][0]
        if a == 'seek': nm = ('⏪ ' if n < 0 else '⏩ ') + (fmt_t(abs(n)) if abs(n) >= 60 else f'{abs(n)} 秒')
        elif a == 'pct': nm = f'跳到 {n:g}%'
        elif a == 'seek_pct': nm = ('⏪ ' if n < 0 else '⏩ ') + f'{abs(n):g}%'
        elif a == 'speed_fine': nm = f'速度 {"+" if n >= 0 else "−"}{abs(n) * 0.01:.2f} 倍'
        return f'{k}＝{nm}'
    return '　'.join(one(*x) for x in K)


def html_esc(t):
    return str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


NEW_FLOW = [   # V0.3.18 🚀 用新功能的建議流程（電腦說明頁、手機工具頁共用）
    ('① 新影片自己進來', '打開 👀 自動找新影片：TikLive 錄好的檔案每 30 分鐘自動出現、自動排預覽圖。💽 空間地圖＋⚠ 空間提醒會告訴你哪顆快滿（照速度算幾天會滿）。'),
    ('② 先把明顯不要的清掉', '打開 😴 背景算靜止比例，等它算一陣子 → ⚡ 規則分級：「靜止超過 80 % → F」、「短於 20 秒 → F」，先預覽符合幾部再套用（可以復原）；滿意就「💾 存成自動規則」，之後新進來的也自動分（剪過、收藏、有書籤的不會動）。'),
    ('③ 從最有東西的資料夾開始', '📂 各資料夾分級進度：「可以審」最多的排最前面，點兩下直接去；或排序選「😴 靜止多→少」先看最可能不要的。'),
    ('④ 一部一部快速分', '⏱ 時長／📺 畫質篩選縮小範圍；🤖 分級建議（按 G 照建議分）；🎬 換場景標記、🔥 動得最多、😴 靜止灰掉，一眼看出哪裡有內容；👆 手機左右滑換部。'),
    ('⑤ 剪精華', '🔖 看到好段落按 B 加書籤 →「✂ 書籤附近選成片段」；或「🔥 選動得最多的地方」、「🎬 選這整個場景」、「✂ 選全部、跳過靜止的」→ 輸出初剪。'),
    ('⑥ 送去上傳', '📤 複製到上傳資料夾（剪好的片段也可以），複製好自動貼 🔵 標籤；📋 上傳看板一次看還沒傳／排隊中／今天傳好的（🔀 作者輪流排、⌛ 還要幾天）；按 U 標成已上傳；🧺 傳完的複本放久了可以一鍵清掉。'),
    ('⑦ 發佈之後', '真的貼到 TikTok 了 → 看板上 ⬜ 點成 ✅（或按 P、或「📥 貼檔名標已發佈」一次一串）；格子上 ↑＝只複製、✓＝已發佈；清理上傳資料夾時還沒發佈的不會預設勾。'),
    ('⑧ 追進度', '🎯 每日目標＋🔥 連續天數、📈 分級報表（每天幾部、照速度還要幾天分完）。兩台電腦輪流用的話看 🖥 硬碟在哪台電腦。'),
]


def note_presets():
    """V0.2.82 ✎ 快速備註的選項（逗號隔開）."""
    return [x.strip() for x in re.split(r'[,，、]+', str(lab_cfg().get('note_list') or '可剪,好笑,重看,要上傳')) if x.strip()][:12]


def keys_sections():
    """V0.2.39 ⌨ 快捷鍵一覽的內容（電腦版）."""
    def one(k, a, n):
        nm = PLAYER_ACTIONS.get(a, (a,))[0]
        if a == 'seek': nm = ('⏪ ' if n < 0 else '⏩ ') + (fmt_t(abs(n)) if abs(n) >= 60 else f'{abs(n)} 秒')
        elif a == 'pct': nm = f'跳到 {n:g}%'
        elif a == 'seek_pct': nm = ('⏪ ' if n < 0 else '⏩ ') + f'{abs(n):g}%'
        elif a == 'speed_fine': nm = f'速度 {"+" if n >= 0 else "−"}{abs(n) * 0.01:.2f} 倍'
        return (str(k), nm)
    try: P = [one(*x) for x in player_keys()]
    except Exception: P = []
    L = lab_cfg()
    if L.get('player_grade'): P += [('1／2／3／4', '播放中分級 S／A／E／F（🧪）'), ('0', '取消分級（🧪）')]
    return [('全域', [('Ctrl+Shift+R', '🗄 封存的功能（R 碟清空搬移）'), ('Ctrl+Shift+H', '🙈 隱私模糊 開／關（🧪）'), ('Ctrl+K', '⌘ 指令面板（🧪）'), ('Ctrl+/', '⌨ 這個快捷鍵一覽（🧪）'), ('Ctrl+L', '回到封面'), ('F1', '說明')]),
            ('檔案總管', [('Ctrl+F', '跳到搜尋框'), ('S／A／E／F', '選到的分級'), ('G', '🤖 照分級建議分級（🧪）'), ('U', '📤 標成／取消「已上傳」（🧪）'), ('Ctrl+Shift+U', '📋 打開上傳看板（🧪）'), ('P', '✅ 標成／取消「已發佈」（🧪）'), ('Ctrl+R', '🎲 隨便抽一部還沒分級的（🧪）'), ('0', '取消分級'), ('N／Shift+N', '下一部／上一部還沒分級的'), ('Enter', '播放'),
                       ('Delete', '移到待刪'), ('Shift+Del', '直接刪除'), ('Ctrl+Z', '復原上一步'), ('PgUp／PgDn', '專注模式：上一部／下一部'), ('滑鼠側鍵', '上一部／下一部（🧪 手勢換部）'), ('Esc', '離開專注模式')]),
            ('播放器（設定裡可以改）', P + ([('B', '🔖 在這裡加時間書籤（🧪）'), ('Shift+B', '✂ 加書籤＋剪這裡前 5 秒～後 10 秒（🧪）')] if L.get('bookmarks') else []) + ([('U／P', '📤 標已上傳／✅ 標已發佈（🧪）')] if L.get('copy_to') else []) + ([('[／]', '🎬 上一個／下一個換場景（🧪）')] if L.get('scenes') else [])),
            ('左右比對播放器', [('Space', '播放／暫停'), ('←／→', '±1 秒'), ('Ctrl+←／→', '±5 秒'), ('Shift+←／→', '±1%'), ('Ctrl+Shift+←／→', '±5%'),
                          ('Ctrl+↑／↓', '速度'), ('D／G', '上一格／下一格'), ('F／F11', '全螢幕'), ('Esc', '關閉')])]


class SeekSlider(QSlider):
    """V0.1.57 時間軸：點哪裡就跳到哪裡（原本點空白處只動一點點），按住拖著不放畫面就跟著走."""
    marks = ()                                                                  # V0.2.79 🔖 書籤位置（0～1）

    def paintEvent(self, e):
        QSlider.paintEvent(self, e) if hasattr(QSlider, 'paintEvent') else None
        if not self.marks: return
        try:
            from PySide6.QtGui import QPolygonF
            from PySide6.QtCore import QPointF
            p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); W_, H_ = self.width(), self.height(); p.setPen(Qt.NoPen); p.setBrush(QColor('#ffc94d'))
            for f in self.marks:
                x = 6 + max(0.0, min(1.0, float(f))) * (W_ - 12); p.drawPolygon(QPolygonF([QPointF(x - 4, 0), QPointF(x + 4, 0), QPointF(x, 6)]))
            p.end()
        except Exception: pass

    def mousePressEvent(self, e):
        try:
            if e.button() == Qt.LeftButton and self.maximum() > self.minimum():
                opt = QStyleOptionSlider(); self.initStyleOption(opt)
                gr = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
                hd = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
                pt = e.position().toPoint()
                if not hd.contains(pt):
                    span = max(1, gr.width() - hd.width()); x = int(pt.x() - gr.x() - hd.width() / 2)
                    v = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), max(0, min(span, x)), span)
                    self.setValue(v); self.sliderMoved.emit(v)
        except Exception: pass
        super().mousePressEvent(e)


def drag_mx(dur_ms):
    """V0.2.08 在畫面上左右拖曳一次最多移動多少（毫秒）：預設影片長度的 10%（cfg drag_pct，0＝改用 drag_max 秒數）."""
    try: pct = float(ENG.cfg.get('drag_pct') if ENG.cfg.get('drag_pct') is not None else 10)
    except Exception: pct = 10.0
    if pct > 0 and dur_ms and dur_ms > 0: return max(3000.0, float(dur_ms) * min(100.0, pct) / 100.0)
    return max(10, min(600, int(ENG.cfg.get('drag_max') or 600))) * 1000


class Player(QDialog):
    graded = Signal(int, str)
    """內建播放器。快捷鍵全部可以在「設定 → 🎬 播放器快捷鍵」改；在畫面上按住左右拖曳＝移動時間（拖著不放畫面就跟著走，一次最多 drag_max）；點兩下＝全螢幕."""
    marks = Signal(float, float)

    def __init__(self, parent, path, t0=0.0, title='', fps=30.0, fid=None, segs=None):
        super().__init__(parent); self.setWindowTitle('▶ ' + (title or Path(path).name)); self.resize(1100, 700); self.path = str(path); self.t0 = float(t0); self.mark_a = None
        self.fps = float(fps or 30) or 30.0; self.drag = None
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
        from PySide6.QtMultimediaWidgets import QVideoWidget
        self.QMP = QMediaPlayer
        v = QVBoxLayout(self); v.setContentsMargins(6, 6, 6, 6)
        self.vw = QVideoWidget(); v.addWidget(self.vw, 1); self.vw.setMouseTracking(False); self.vw.installEventFilter(self); self.vw.setCursor(Qt.SizeHorCursor)
        QTimer.singleShot(400, self._hook_vw_kids)                                # 有些顯示卡驅動把影像畫在子視窗上，滑鼠事件也要從那裡接
        self.vw.setToolTip('按住左右拖曳＝移動時間（拖著不放畫面就跟著走）　點兩下＝全螢幕　滾輪＝音量')
        self.pl = QMediaPlayer(self); self.ao = QAudioOutput(self); self.ao.setVolume(max(0, min(100, int(ENG.cfg.get('vol') if ENG.cfg.get('vol') is not None else 80))) / 100); self.ao.setMuted(bool(ENG.cfg.get('mute'))); self.pl.setAudioOutput(self.ao); self.pl.setVideoOutput(self.vw)
        self.osd = QLabel(''); self.osd.setAlignment(Qt.AlignCenter); self.osd.setStyleSheet('QLabel{color:#4dc9ff;font-size:15px;font-weight:700}'); v.addWidget(self.osd)
        self.osd_t = QTimer(self); self.osd_t.setSingleShot(True); self.osd_t.timeout.connect(lambda: self.osd.setText(''))
        row = QHBoxLayout(); v.addLayout(row)
        self.bp = QPushButton('⏯'); self.sl = SeekSlider(Qt.Horizontal); self.tl = QLabel('0:00 / 0:00')
        self.ma = QPushButton('✂ 這裡當起點'); self.mb = QPushButton('✂ 這裡當終點'); self.ext = QPushButton('外部播放器'); self.spd = QLabel('1.00x'); self.spd.setFixedWidth(48)
        row.addWidget(self.bp)
        self.bm = QPushButton(); self.bm.setFixedWidth(40); self.bm.setToolTip('靜音／取消靜音'); self.vs = QSlider(Qt.Horizontal); self.vs.setRange(0, 100); self.vs.setFixedWidth(120)
        self.vs.setToolTip('音量（↑ ↓ 或在畫面上滾輪也可以調）'); self.vl = QLabel(''); self.vl.setFixedWidth(38); self.vs.setValue(round(self.ao.volume() * 100))
        row.addWidget(self.sl, 1); row.addWidget(self.tl); row.addWidget(self.spd); row.addWidget(self.bm); row.addWidget(self.vs); row.addWidget(self.vl); row.addWidget(self.ma); row.addWidget(self.mb); row.addWidget(self.ext)
        for w in (self.bp, self.sl, self.ma, self.mb, self.ext, self.bm, self.vs): w.setFocusPolicy(Qt.NoFocus)     # 方向鍵、空白鍵都給快捷鍵
        self.vs.valueChanged.connect(self._vol_set); self.bm.clicked.connect(self.mute); self._vol_ui()
        self.K = player_keys()
        self.msg = QLabel(key_help(self.K) + '　（設定 → 🎬 播放器快捷鍵 可以改）'); self.msg.setObjectName('muted'); self.msg.setWordWrap(True); v.addWidget(self.msg)
        self.bp.clicked.connect(self.toggle); self.sf = {'t': 0.0, 'd': 0, 'n': 0}
        self.seek_want = None; self.seek_t = QTimer(self); self.seek_t.setSingleShot(True); self.seek_t.timeout.connect(self._seek_flush); self.scrub_play = None
        self.sl.sliderPressed.connect(self._scrub_begin); self.sl.sliderReleased.connect(lambda: self._scrub_end(self.sl.value()))
        self.sl.sliderMoved.connect(lambda x: (self.live_seek(int(x)), self.tl.setText(f'{fmt_t(x / 1000)} / {fmt_t(self.pl.duration() / 1000)}'))); self.ext.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.path)))
        self.ma.clicked.connect(self._ma); self.mb.clicked.connect(self._mb)
        self.pl.durationChanged.connect(lambda d: (self.sl.setRange(0, int(d)), self._bm_ui() if hasattr(self, 'b_bmk') else None)); self.pl.positionChanged.connect(self._pos)
        self.pl.mediaStatusChanged.connect(self._st); self.pl.errorOccurred.connect(self._err)
        self.scs = []
        for k, a, n in self.K:
            try:
                sc = QShortcut(QKeySequence(k), self); sc.setAutoRepeat(a not in ('play', 'full', 'close', 'snap', 'mark_a', 'mark_b', 'mute'))
                sc.activated.connect(lambda a=a, n=n: self.do(a, n)); self.scs.append(sc)
            except Exception: ENG.log.err(f'播放器快捷鍵 {k}')
        self.fid = fid; L = lab_cfg(); self.resume_at = 0.0; self.segs = sorted(segs or []); self.seg_i = 0
        if self.segs:
            self.t0 = float(self.segs[0][0]); self.setWindowTitle('▶ 片段預覽：' + (title or Path(path).name))
            self.msg.setText(f'🧪 片段預覽：只播你選的 {len(self.segs)} 段（共 {fmt_t(sum(b - a for a, b in self.segs))}），一段播完自動跳下一段，最後停住')
        if fid and L.get('resume') and self.t0 <= 0:
            try: self.resume_at = float((ENG.file(fid) or {}).get('last_pos') or 0)
            except Exception: self.resume_at = 0.0
        if fid and L.get('player_grade'):                                     # 🧪 播放中直接分級：1 2 3 4 ＝ S A E F、0 ＝ 取消
            used = {str(k).lower() for k, _a, _n in self.K}
            for key, g in (('1', 'S'), ('2', 'A'), ('3', 'E'), ('4', 'F'), ('0', '')):
                if key in used: continue
                sc = QShortcut(QKeySequence(key), self); sc.activated.connect(lambda g=g: self.grade(g)); self.scs.append(sc)
            self.msg.setText(self.msg.text() + '　🧪 1／2／3／4＝S／A／E／F、0＝取消分級')
        if fid and L.get('scenes'):                                           # V0.3.37 🎬 [ ]＝上一個／下一個換場景
            try:
                used_ = {str(k).lower() for k, _a, _n in self.K}; self._scn = []
                f_ = ENG.file(fid) or {}; st_ = max(1, int(f_.get('th_step') or 2))
                bg(lambda: ENG.scene_cuts(fid), lambda L_: setattr(self, '_scn', [b_ * st_ for b_ in L_]))
                for key_, d_ in (('[', -1), (']', 1)):
                    if key_ not in used_: sc = QShortcut(QKeySequence(key_), self); sc.activated.connect(lambda d_=d_: self.scene_jump(d_)); self.scs.append(sc)
                self.msg.setText(self.msg.text() + '　🧪 [ ]＝上／下一個換場景')
            except Exception: ENG.log.err('換場景跳轉')
        if fid and L.get('bookmarks'):                                        # V0.2.41 🔖 時間書籤：B＝加在這裡、🔖 按鈕＝列表跳過去
            try:
                self.b_bmk = QPushButton('🔖'); self.b_bmk.setToolTip('🔖 時間書籤：B＝在這裡加一個；按這裡看全部、跳過去'); self.b_bmk.setFocusPolicy(Qt.NoFocus)
                row.insertWidget(row.count() - 1, self.b_bmk); self.b_bmk.clicked.connect(self.bm_menu)
                if 'b' not in {str(k).lower() for k, _a, _n in self.K}:
                    sc = QShortcut(QKeySequence('B'), self); sc.setAutoRepeat(False); sc.activated.connect(self.bm_here); self.scs.append(sc)
                if 'shift+b' not in {str(k).lower() for k, _a, _n in self.K}:                                   # V0.4.18 Shift+B＝加書籤＋剪前 5 秒～後 10 秒
                    sc = QShortcut(QKeySequence('Shift+B'), self); sc.setAutoRepeat(False); sc.activated.connect(self.bm_clip_here); self.scs.append(sc)
                self._bm_ui(); self.msg.setText(self.msg.text() + '　🧪 B＝加時間書籤、Shift+B＝順便剪一段')
            except Exception: ENG.log.err('時間書籤按鈕')
        try:                                                                    # V0.4.47 播放器裡也能按 U／P 標已上傳／已發佈
            if fid and lab_cfg().get('copy_to'):
                ks_ = {str(k).lower() for k, _a, _n in self.K}
                for key_, fn_ in (('U', self._mark_up), ('P', self._mark_pub)):
                    if key_.lower() not in ks_: sc = QShortcut(QKeySequence(key_), self); sc.setAutoRepeat(False); sc.activated.connect(fn_); self.scs.append(sc)
        except Exception: ENG.log.err('播放器 U／P')
        try: self._fit_portrait(fid)
        except Exception: pass
        self.ab = None; self.seeked = False; self.pl.setSource(QUrl.fromLocalFile(self.path)); self.pl.play()
        ENG.log.w(f'播放：{self.path}（從 {fmt_t(self.t0)}）')

    def _fit_portrait(self, fid):
        """V0.2.05 直的影片（手機直播）：視窗改成長條型，高度用到螢幕可用高度的 92%、寬度剛好裝下畫面（最少 900，控制列才放得下）."""
        r = (ENG.file(fid) if fid else None) or ENG.db.one('SELECT w, h FROM files WHERE path=? LIMIT 1', (self.path,))
        w, h = (int(r['w'] or 0), int(r['h'] or 0)) if r else (0, 0)
        if not (w and h and h > w * 1.2): return
        par = self.parent(); scr = (par.screen() if par is not None and hasattr(par, 'screen') else None) or QApplication.primaryScreen()
        g = scr.availableGeometry(); H = int(g.height() * 0.92); extra = 230                       # 控制列＋快捷鍵說明（說明在窄視窗會折成好幾行）
        vh = max(300, H - extra); W = max(900, min(g.width() - 40, int(vh * w / h) + 40))
        self.resize(W, H); self.move(g.x() + (g.width() - W) // 2, g.y() + max(0, (g.height() - H) // 2))

    # ---- 動作
    def do(self, a, n=0):
        try:
            if a == 'seek': self.seek_rel(float(n))
            elif a == 'play': self.toggle()
            elif a == 'vol_up': self.vol(0.05)
            elif a == 'vol_down': self.vol(-0.05)
            elif a == 'mute': self.mute()
            elif a in ('speed_up', 'speed_down', 'speed_reset'):
                r = 1.0 if a == 'speed_reset' else max(0.1, min(4.0, round(self.pl.playbackRate() + (0.1 if a == 'speed_up' else -0.1), 2)))
                self.pl.setPlaybackRate(r); self.spd.setText(f'{r:.2f}x'); self.show_osd(f'速度 {r:.2f} 倍')
            elif a == 'speed_fine': self.speed_fine(float(n or 1))
            elif a == 'seek_pct':
                d = self.pl.duration()
                if d > 0:
                    to = max(0, min(d - 500, self.pl.position() + int(d * float(n) / 100))); self.pl.setPosition(int(to))
                    self.show_osd(('⏩ +' if n >= 0 else '⏪ −') + f'{abs(float(n)):g}%　→ {fmt_t(to / 1000)}')
            elif a in ('frame_next', 'frame_prev'):
                self.pl.pause(); st = max(1, int(round(1000 / self.fps)))
                self.pl.setPosition(max(0, self.pl.position() + (st if a == 'frame_next' else -st))); self.show_osd(('下一格 ' if a == 'frame_next' else '上一格 ') + fmt_t(self.pl.position() / 1000))
            elif a == 'home': self.pl.setPosition(0); self.show_osd('⏮ 開頭')
            elif a == 'end': self.pl.setPosition(max(0, self.pl.duration() - 5000)); self.show_osd('⏭ 最後 5 秒')
            elif a == 'mark_a': self._ma()
            elif a == 'mark_b': self._mb()
            elif a == 'snap': self.snap()
            elif a == 'ab_loop': self._ab_step()
            elif a == 'pct':
                d = self.pl.duration()
                if d > 0: self.pl.setPosition(int(d * max(0.0, min(99.0, float(n))) / 100)); self.show_osd(f'→ {float(n):g}%（{fmt_t(d * float(n) / 100000)}）')
            elif a == 'full': self.full()
            elif a == 'close':
                if self.isFullScreen(): self.showNormal()
                else: self.close()
        except Exception: ENG.log.err(f'播放器動作 {a}')

    def show_osd(self, t, ms=1500):
        self.osd.setText(t); self.osd_t.start(ms)

    def full(self):
        if self.isFullScreen(): self.showNormal()
        else: self.showFullScreen()

    def snap(self):
        try:
            img = self.vw.videoSink().videoFrame().toImage()
            if img.isNull(): self.show_osd('現在這格抓不到畫面（先播放一下再試）'); return
            src = Path(self.path); d = Path(src.anchor or src.parent) / core.ARCH_BASE / '截圖'; d.mkdir(parents=True, exist_ok=True)
            out = core.unique_path(d / f'{core.safe_name(src.stem)[:60]}_{fmt_t(self.pl.position() / 1000).replace(":", "")}.jpg')
            img.save(str(out), 'JPG', 92); self.show_osd(f'📷 已截圖 → {out.name}', 2500); ENG.oplog('snap', src=str(src), dst=str(out), detail=f'截圖 {fmt_t(self.pl.position() / 1000)}')
        except Exception as ex: ENG.log.err('截圖'); self.show_osd(f'截圖失敗：{ex}')

    # ---- 畫面上拖曳：移動時間
    def eventFilter(self, obj, e):
        try:
            t = e.type()
            if t == QEvent.MouseButtonDblClick: self.full(); return True
            if t == QEvent.MouseButtonPress and e.button() == Qt.LeftButton:
                x_ = e.position().x(); self.drag = {'x0': x_, 'p0': self.pl.position(), 'moved': False, 'x': x_, 't': time.monotonic(), 'acc': 0.0}; return True
            if t == QEvent.MouseMove and self.drag is not None:
                dx = e.position().x() - self.drag['x0']
                if abs(dx) > 6 and not self.drag['moved']: self.drag['moved'] = True; self._scrub_begin()
                self._drag_step(e.position().x())
                if self.drag['moved']:
                    tgt = self._drag_target(dx); d = (tgt - self.drag['p0']) / 1000; self.live_seek(int(tgt))      # V0.1.57 拖著不放：畫面跟著走
                    self.show_osd(f'{"⏩ +" if d >= 0 else "⏪ −"}{fmt_t(abs(d))}　→ {fmt_t(tgt / 1000)}', 3000)
                return True
            if t == QEvent.MouseButtonRelease and self.drag is not None:
                dx = e.position().x() - self.drag['x0']; self._drag_step(e.position().x())
                if self.drag['moved'] or abs(dx) > 6: tgt = self._drag_target(dx); self._scrub_end(int(tgt)); self.show_osd(f'→ {fmt_t(tgt / 1000)}'); ENG.log.w(f'播放器拖曳：→ {fmt_t(tgt / 1000)}')
                self.drag = None; return True
        except Exception: ENG.log.err('播放器拖曳')
        return super().eventFilter(obj, e)

    # ---- 拖著不放畫面就跟著走（時間軸、畫面上拖曳共用）
    def live_seek(self, ms):
        self.seek_want = int(ms)
        if not self.seek_t.isActive(): self._seek_flush()

    def _seek_flush(self):
        if self.seek_want is None: return
        self.pl.setPosition(int(self.seek_want)); self.seek_want = None; self.seek_t.start(60)        # 最多每 60 毫秒跳一次，不會塞車

    def _scrub_begin(self):
        if self.scrub_play is None: self.scrub_play = self.pl.playbackState() == self.QMP.PlaybackState.PlayingState
        if self.scrub_play: self.pl.pause()                                    # 拖的時候先停住，畫面一格一格跟著走
        try:
            if not self.pl.isSeekable(): self.show_osd('⚠ 這個檔內建播放器沒辦法跳時間（.ts 之類），按「外部播放器」或轉成 MP4 再看', 4000)
        except Exception: pass

    def _scrub_end(self, ms):
        self.seek_want = None; self.seek_t.stop(); self.pl.setPosition(int(ms))
        if self.scrub_play: self.pl.play()
        self.scrub_play = None

    def speed_fine(self, n):
        """Ctrl＋上／下：每下 ±0.01 倍；按住不放越加越快（0.01 → 0.02 → 0.05 → 0.1）."""
        now = time.monotonic(); d = 1 if n >= 0 else -1; S = self.sf
        S['n'] = S['n'] + 1 if (now - S['t'] < 0.35 and S['d'] == d) else 0; S['t'] = now; S['d'] = d
        st = 0.01 if S['n'] < 6 else 0.02 if S['n'] < 15 else 0.05 if S['n'] < 30 else 0.1
        r = max(0.1, min(4.0, round(self.pl.playbackRate() + d * st * max(1.0, abs(n)), 2)))
        self.pl.setPlaybackRate(r); self.spd.setText(f'{r:.2f}x'); self.show_osd(f'速度 ×{r:.2f}' + ('（按住加速中）' if S['n'] >= 6 else ''))

    def _hook_vw_kids(self):
        try:
            for c in self.vw.findChildren(QWidget):
                c.installEventFilter(self); c.setCursor(Qt.SizeHorCursor)
        except Exception: ENG.log.err('播放器：接子視窗滑鼠')

    def _drag_step(self, x):
        """照 TikLive：拖得快、拖得長＝跳得遠，慢慢拖＝幾秒幾秒細調；一次最多 drag_max 秒（預設 10 分鐘）."""
        g = self.drag; now = time.monotonic(); ddx = x - g['x']; dt = max(0.008, now - g['t']); g['x'] = x; g['t'] = now
        mx = drag_mx(self.pl.duration())
        w = max(200, self.vw.width()); sp = abs(ddx) / (dt * 1000)                         # 每毫秒幾像素
        kk = min(1.0, max(0.12, (sp - 0.05) / 1.3))
        g['acc'] = max(-mx, min(mx, g['acc'] + ddx / w * mx * 1.6 * kk))

    def _drag_target(self, dx):
        mx = drag_mx(self.pl.duration())                                       # V0.2.08 一次最多＝影片長度的 10%（設定可改）
        d = max(-mx, min(mx, self.drag.get('acc', 0.0)))
        return max(0, min(self.pl.duration() or 0, self.drag['p0'] + d)) if self.pl.duration() else max(0, self.drag['p0'] + d)

    def _st(self, s):
        try:                                                                    # V0.2.90 ▶ 連播：播完自動換下一部
            if getattr(self, 'pl_next', 0) and s == self.QMP.MediaStatus.EndOfMedia and not getattr(self, '_ended', False):
                self._ended = True; self.show_osd(f'⏭ 下一部（還有 {self.pl_next} 部）', 1200); QTimer.singleShot(900, self.close)
        except Exception: pass
        if not self.seeked and s in (self.QMP.MediaStatus.LoadedMedia, self.QMP.MediaStatus.BufferedMedia, self.QMP.MediaStatus.BufferingMedia):
            self.seeked = True
            if self.t0 > 0: self.pl.setPosition(int(self.t0 * 1000))
            elif self.resume_at > 5: self.pl.setPosition(int(self.resume_at * 1000)); self.show_osd(f'⏯ 從上次 {fmt_t(self.resume_at)} 繼續（Home＝回到開頭）', 4000)

    def grade(self, g):
        try:
            fid = self.fid; ENG.set_flags([fid], grade=g); self.graded.emit(int(fid), g)
            self.show_osd(f'分級 → {g}（{GN[g]}）' if g else '取消分級', 2000); ENG.log.w(f'播放中分級：{self.path} → {g or "未分級"}')
        except Exception: ENG.log.err('播放中分級')

    def _err(self, *a):
        self.msg.setText('✖ 這個格式內建播放器放不了：' + str(self.pl.errorString())[:200] + '　→ 按「外部播放器」用電腦預設的播放器開')

    def _ab_step(self):
        """A-B 重複：第 1 下起點、第 2 下終點（開始重複）、第 3 下取消."""
        ab = self.ab; p = self.pl.position()
        if ab is None: self.ab = [p, None]; self.show_osd(f'🔁 A＝{fmt_t(p / 1000)}（再按一次設 B）', 2500)
        elif ab[1] is None:
            if p <= ab[0] + 300: self.show_osd('B 要在 A 後面', 2000); return
            ab[1] = p; self.pl.setPosition(int(ab[0])); self.show_osd(f'🔁 重複 {fmt_t(ab[0] / 1000)} → {fmt_t(p / 1000)}（再按一次取消）', 3000); ENG.log.w(f'播放器 A-B 重複：{fmt_t(ab[0] / 1000)} → {fmt_t(p / 1000)}')
        else: self.ab = None; self.show_osd('🔁 取消重複', 1500)

    def scene_jump(self, d):
        L = sorted(getattr(self, '_scn', []) or [])
        if not L: self.show_osd('🎬 這部沒有找到換場景（或還在算）', 1500); return
        cur = self.pl.position() / 1000
        t = next((x for x in L if x > cur + 1), None) if d > 0 else next((x for x in reversed(L) if x < cur - 2), None)
        if t is None: self.show_osd('🎬 沒有了', 1000); return
        self.pl.setPosition(int(t * 1000)); self.show_osd(f'🎬 {fmt_t(t)}', 1200)

    def _mark_up(self):
        try:
            f = ENG.file(self.fid) or {}; on_ = not float(f.get('up_t') or 0) > 0; m_ = ENG.up_mark([self.fid], on_)[1]; self.osd.setText(m_); self.osd_t.start(1500)
        except Exception: ENG.log.err('播放器標已上傳')

    def _mark_pub(self):
        try:
            f = ENG.file(self.fid) or {}; on_ = not float(f.get('pub_t') or 0) > 0; m_ = ENG.pub_mark([self.fid], on_)[1]; self.osd.setText(m_); self.osd_t.start(1500)
        except Exception: ENG.log.err('播放器標已發佈')

    def bm_clip_here(self):
        """V0.4.18 Shift+B：這裡加書籤，順便把前 5 秒～後 10 秒排進初剪."""
        try:
            t = self.pl.position() / 1000; ENG.bm_add(self.fid, t, '✂'); self._bm_ui(); r = ENG.bm_clip(self.fid, t, 5, 10) or {}
            self.osd.setText(f"✂ {fmt_t(max(0, t - 5))}～{fmt_t(t + 10)} " + ('排進初剪了' if r.get('ok') else (r.get('message') or ''))); self.osd_t.start(2000)
        except Exception: ENG.log.err('書籤剪一段')

    def bm_here(self, note=''):
        try:
            t = self.pl.position() / 1000; ENG.bm_add(self.fid, t, note); self._bm_ui()
            self.osd.setText(f'🔖 {fmt_t(t)}'); self.osd_t.start(1500)
        except Exception: ENG.log.err('加時間書籤')

    def _bm_ui(self):
        try:
            L = ENG.bm_list(self.fid); n = len(L); self.b_bmk.setText(f'🔖 {n}' if n else '🔖')
            d = max(1, self.pl.duration()) / 1000; self.sl.marks = tuple(t / d for t, _n in L) if self.pl.duration() > 0 else (); self.sl.update()   # V0.2.79 時間軸上標出書籤
            try:
                g_ = self.parent().grid if hasattr(self.parent(), 'grid') else None
                if g_ is not None and getattr(g_, 'fid', None) == self.fid: g_.bm_ts = tuple(t for t, _n in L); g_.update()   # V0.2.96 預覽格子也跟著標
            except Exception: pass
        except Exception: pass

    def bm_menu(self):
        try:
            m = QMenu(self); L = ENG.bm_list(self.fid); cur = self.pl.position() / 1000
            m.addAction(f'＋ 加在這裡（{fmt_t(cur)}）', self.bm_here)
            def _named():
                n, ok = QInputDialog.getText(self, '🔖 時間書籤', f'{fmt_t(cur)} 的說明：')
                if ok: ENG.bm_add(self.fid, cur, n); self._bm_ui()
            m.addAction('＋ 加在這裡並寫說明…', _named)
            if L: m.addAction('✂ 每個書籤 前 5 秒～後 15 秒 選成片段', lambda: ([self.marks.emit(max(0.0, t - 5), t + 15) for t, _n in L], self.show_osd(f'✂ 選了 {len(L)} 段（回到格子按「輸出初剪」）', 3000)))   # V0.2.97
            if L: m.addSeparator()
            for t, n in L: m.addAction(f'▶ {fmt_t(t)}　{n}', lambda t=t: self.pl.setPosition(int(t * 1000)))
            if L:
                sm = m.addMenu('🗑 刪除'); [sm.addAction(f'{fmt_t(t)} {n}', lambda t=t: (ENG.bm_del(self.fid, t), self._bm_ui())) for t, n in L]
            m.exec(self.b_bmk.mapToGlobal(self.b_bmk.rect().topLeft())); m.deleteLater()
        except Exception: ENG.log.err('時間書籤選單')

    def _pos(self, ms):
        ab = self.ab
        if ab is not None and ab[1] is not None and ms >= ab[1] and not self.sl.isSliderDown(): self.pl.setPosition(int(ab[0])); return
        if not self.sl.isSliderDown(): self.sl.setValue(int(ms))
        self.tl.setText(f'{fmt_t(ms / 1000)} / {fmt_t(self.pl.duration() / 1000)}')
        if self.segs and self.seeked: self._seg_follow(ms / 1000)

    def _seg_follow(self, t):
        """🧪 片段預覽：跑出這一段就跳下一段；最後一段播完就停."""
        i = next((k for k, (a, b) in enumerate(self.segs) if a - 0.3 <= t < b), None)
        if i is not None: self.seg_i = i; return
        nxt = next((k for k, (a, b) in enumerate(self.segs) if a > t), None)
        if nxt is not None and t >= self.segs[self.seg_i][1] - 0.05:
            self.seg_i = nxt; self.pl.setPosition(int(self.segs[nxt][0] * 1000)); self.show_osd(f'片段 {nxt + 1}/{len(self.segs)}　{fmt_t(self.segs[nxt][0])}～{fmt_t(self.segs[nxt][1])}', 2500)
        elif nxt is None and t >= self.segs[-1][1] - 0.05 and self.pl.playbackState() == self.QMP.PlaybackState.PlayingState:
            self.pl.pause(); self.show_osd('✔ 片段預覽播完了（回到格子按「輸出初剪」）', 5000)

    def toggle(self):
        if self.pl.playbackState() == self.QMP.PlaybackState.PlayingState: self.pl.pause()
        else: self.pl.play()

    def seek_rel(self, s):
        self.pl.setPosition(max(0, self.pl.position() + int(s * 1000))); a = abs(s)
        self.show_osd(('⏩ +' if s >= 0 else '⏪ −') + (fmt_t(a) if a >= 60 else f'{a:g} 秒') + f'　→ {fmt_t(max(0, self.pl.position() / 1000))}')

    def vol(self, d): self.vs.setValue(max(0, min(100, self.vs.value() + round(d * 100))))

    def _vol_set(self, v):
        self.ao.setVolume(v / 100)
        if self.ao.isMuted() and v > 0: self.ao.setMuted(False)
        self._vol_ui(); ENG.cfg.set('vol', int(v)); ENG.cfg.set('mute', bool(self.ao.isMuted()))

    def mute(self):
        self.ao.setMuted(not self.ao.isMuted()); self._vol_ui(); ENG.cfg.set('mute', bool(self.ao.isMuted()))

    def _vol_ui(self):
        v = self.vs.value(); m = self.ao.isMuted() or v == 0
        self.bm.setText('🔇' if m else '🔈' if v < 34 else '🔉' if v < 67 else '🔊'); self.vl.setText('靜音' if self.ao.isMuted() else f'{v}%')

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if d: self.vol(0.05 if d > 0 else -0.05)
        e.accept()

    def _ma(self):
        self.mark_a = self.pl.position() / 1000; self.msg.setText(f'起點 {fmt_t(self.mark_a)}：播到想要的地方再按「這裡當終點」')

    def _mb(self):
        b = self.pl.position() / 1000
        if self.mark_a is None or b <= self.mark_a + 0.5: self.msg.setText('先按「這裡當起點」，終點要在起點後面'); return
        self.marks.emit(self.mark_a, b); self.msg.setText(f'✔ 已加入一段 {fmt_t(self.mark_a)} ～ {fmt_t(b)}（回到格子按「輸出初剪」）'); self.mark_a = None

    def closeEvent(self, e):
        try:
            if self.fid and lab_cfg().get('resume'):                            # 🧪 續播：記住看到哪裡（開頭 10 秒內、最後 10 秒內就不記）
                pos = (self.pl.position() or 0) / 1000; dur = (self.pl.duration() or 0) / 1000
                keep = pos if (pos > 10 and (not dur or pos < dur - 10)) else 0
                fid = self.fid; bg(lambda: ENG.set_flags([fid], last_pos=keep))
        except Exception: ENG.log.err('記住播放位置')
        try: self.pl.stop(); self.pl.setSource(QUrl())
        except Exception: pass
        super().closeEvent(e)


# ============================================================ 🆚 並排比較（V0.1.57）：原檔 vs 轉好的，同一條時間軸、放大鏡
class FrameView(QWidget):
    """自己畫影片畫面（才能做放大鏡）。滑鼠移過去＝放大鏡，另一邊同一個位置一起放大；滾輪＝放大倍數."""
    hover = Signal(object)
    zoomed = Signal(float)

    def __init__(self, tag, color):
        super().__init__(); self.tag = tag; self.color = color; self.info = ''; self.img = None; self.rel = None; self.zoom = 3.0; self.R = 120; self.tr = None; self.note = ''; self.vf = None; self.pm = None; self.pm_k = None
        self.setMouseTracking(True); self.setMinimumSize(200, 120); self.setCursor(Qt.CrossCursor); self.setAttribute(Qt.WA_OpaquePaintEvent)
        from PySide6.QtMultimedia import QVideoSink
        self.sink = QVideoSink(self); self.sink.videoFrameChanged.connect(self._frame)

    def _frame(self, f):
        self.vf = f if (f is not None and f.isValid()) else None; self.update()     # V0.1.85：先記著，畫的時候才轉（4K 每格轉圖很慢，來不及畫的就跳過，不卡畫面）

    def _take(self):
        f = self.vf
        if f is not None:
            self.vf = None
            try: self.img = f.toImage(); self.pm = None
            except Exception: pass
        return self.img

    def set_rel(self, rel):
        self.rel = rel; self.update()

    def paintEvent(self, _e):
        p = QPainter(self); p.fillRect(self.rect(), QColor('#000'))
        img = self._take()
        if img is not None and not img.isNull():
            W, H = self.width(), self.height(); iw, ih = img.width(), img.height(); sc = min(W / iw, H / ih)
            tw, th = int(iw * sc), int(ih * sc); tr = QRect((W - tw) // 2, (H - th) // 2, tw, th); self.tr = tr
            dpr = self.devicePixelRatioF() if hasattr(self, 'devicePixelRatioF') else 1.0
            k_ = (id(img), tw, th)
            if self.pm is None or self.pm_k != k_:                              # 縮好的畫面留著：只動放大鏡時不用每次重縮 4K
                try:
                    pm = QPixmap.fromImage(img.scaled(max(1, int(tw * dpr)), max(1, int(th * dpr)), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    pm.setDevicePixelRatio(dpr); self.pm = pm; self.pm_k = k_
                except Exception: self.pm = None
            if self.pm is not None: p.drawPixmap(tr, self.pm)
            else: p.setRenderHint(QPainter.SmoothPixmapTransform, True); p.drawImage(tr, img)
            if self.rel is not None:
                rx, ry = self.rel; cx = tr.x() + rx * tr.width(); cy = tr.y() + ry * tr.height(); R = self.R
                k = iw / max(1, tr.width()); half = R / self.zoom * k
                src = QRectF(rx * iw - half, ry * ih - half, half * 2, half * 2); dst = QRectF(cx - R, cy - R, R * 2, R * 2)
                path = QPainterPath(); path.addEllipse(dst); p.save(); p.setClipPath(path); p.fillRect(dst, QColor('#000'))
                p.setRenderHint(QPainter.SmoothPixmapTransform, False); p.drawImage(dst, img, src); p.restore()      # 放大鏡不要平滑：看得到真正的像素
                p.setRenderHint(QPainter.Antialiasing, True); p.setPen(QPen(QColor(self.color), 2)); p.drawEllipse(dst)
                p.setPen(QColor('#fff')); p.drawText(QRectF(cx - R, cy + R + 2, R * 2, 18), Qt.AlignCenter, f'×{self.zoom:g}')
        else:
            self.tr = None; p.setPen(QColor('#8a93a3')); p.drawText(self.rect(), Qt.AlignCenter, self.note or '載入中…')
        p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 170)); fm = QFontMetrics(self.font()); txt = f'{self.tag}　{self.info}'
        bw = min(self.width() - 8, fm.horizontalAdvance(txt) + 16); p.drawRoundedRect(QRect(4, 4, bw, 24), 6, 6)
        p.setPen(QColor(self.color)); p.drawText(QRect(12, 4, bw - 12, 24), Qt.AlignVCenter | Qt.AlignLeft, fm.elidedText(txt, Qt.ElideRight, bw - 16)); p.end()

    def mouseMoveEvent(self, e):
        tr = self.tr
        if tr is not None and tr.width() > 0:
            x = (e.position().x() - tr.x()) / tr.width(); y = (e.position().y() - tr.y()) / tr.height()
            self.hover.emit((max(0.0, min(1.0, x)), max(0.0, min(1.0, y))) if -0.02 <= x <= 1.02 and -0.02 <= y <= 1.02 else None)
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self.hover.emit(None); super().leaveEvent(e)

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if d: self.zoomed.emit(max(1.5, min(12.0, round(self.zoom * (1.25 if d > 0 else 0.8), 2))))
        e.accept()


class PlayCompareDlg(QDialog):
    """兩個檔同時播：左右或上下並排、同一條時間軸（拖著不放兩邊畫面一起跟著走）、滑鼠移過去兩邊同一個位置一起放大.
    a_off／b_off：時間軸的 0 秒＝A／B 的第幾秒（試轉 10 秒用：原檔從中間開始）."""
    def __init__(self, parent, a_path, b_path, a_tag='原檔', b_tag='轉好的', t0=0.0, a_off=0.0, b_off=0.0, title=''):
        super().__init__(parent); self.setWindowTitle('🆚 ' + (title or f'{Path(a_path).name}　vs　{Path(b_path).name}')); self.resize(1400, 800)
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
        self.QMP = QMediaPlayer; self.paths = (str(a_path), str(b_path)); self.off = (float(a_off) * 1000, float(b_off) * 1000); self.t0 = float(t0); self.started = False
        self.rate = 1.0; self.sync_hold = 0.0; self.bad = set(); self.fstep = 33; self.key_to = None; self.key_t = 0.0
        v = QVBoxLayout(self); v.setContentsMargins(6, 6, 6, 6); v.setSpacing(4)
        self.sp = QSplitter(Qt.Horizontal if (ENG.cfg.get('cmp_layout') or 'lr') == 'lr' else Qt.Vertical); v.addWidget(self.sp, 1)
        self.va = FrameView(a_tag, '#ffb454'); self.vb = FrameView(b_tag, '#4dc9ff'); self.sp.addWidget(self.va); self.sp.addWidget(self.vb)
        self.pa = QMediaPlayer(self); self.pb = QMediaPlayer(self); self.ao = QAudioOutput(self); self.ao.setVolume(max(0, min(100, int(ENG.cfg.get('vol') if ENG.cfg.get('vol') is not None else 80))) / 100)
        self.pa.setVideoSink(self.va.sink); self.pb.setVideoSink(self.vb.sink); self.pb.setAudioOutput(self.ao); self.aud = 'b'
        for vw in (self.va, self.vb):
            vw.hover.connect(self._hover); vw.zoomed.connect(self._zoom); vw.installEventFilter(self)
        self.osd = QLabel(''); self.osd.setAlignment(Qt.AlignCenter); self.osd.setStyleSheet('QLabel{color:#4dc9ff;font-size:15px;font-weight:700}'); v.addWidget(self.osd)
        self.osd_t = QTimer(self); self.osd_t.setSingleShot(True); self.osd_t.timeout.connect(lambda: self.osd.setText(''))
        row = QHBoxLayout(); v.addLayout(row)
        self.bp = QPushButton('⏯'); self.sl = SeekSlider(Qt.Horizontal); self.tl = QLabel('0:00 / 0:00'); self.blay = QPushButton(); self.bau = QPushButton(); self.spd = QLabel('1.00x'); self.spd.setFixedWidth(48)
        self.bsw = QPushButton('A／B 互換位置')
        for w in (self.bp, self.sl, self.tl, self.spd, self.blay, self.bsw, self.bau): row.addWidget(w, 1 if w is self.sl else 0)
        for w in (self.bp, self.sl, self.blay, self.bau, self.bsw): w.setFocusPolicy(Qt.NoFocus)
        self.msg = QLabel('滑鼠移到畫面上＝放大鏡（兩邊同一個位置一起放大，滾輪調倍數）　畫面上按住左右拖＝移動時間（拖著不放兩邊一起跟著走）　空白鍵＝播放／暫停　←→ 1 秒、Ctrl 5 秒、Shift 1%、Ctrl+Shift 5%　Ctrl+↑↓ 速度微調　F／雙擊＝全螢幕')
        self.msg.setObjectName('muted'); self.msg.setWordWrap(True); v.addWidget(self.msg)
        self._lay_txt(); self._au_txt()
        self.bp.clicked.connect(self.toggle); self.blay.clicked.connect(self._lay); self.bau.clicked.connect(self._au); self.bsw.clicked.connect(self._swap)
        self.seek_want = None; self.seek_t = QTimer(self); self.seek_t.setSingleShot(True); self.seek_t.timeout.connect(self._flush); self.scrub_play = None; self.drag = None; self.sf = {'t': 0.0, 'd': 0, 'n': 0}
        self.sl.sliderPressed.connect(self._scrub_begin); self.sl.sliderReleased.connect(lambda: self._scrub_end(self.sl.value())); self.sl.sliderMoved.connect(lambda x: (self.live(int(x)), self._tl(int(x))))
        self.pb.positionChanged.connect(self._pos); self.pa.positionChanged.connect(lambda _m: 'b' in self.bad and self._pos(_m)); self.pa.durationChanged.connect(lambda _d: self._range()); self.pb.durationChanged.connect(lambda _d: self._range())
        self.pa.mediaStatusChanged.connect(lambda s: self._st()); self.pb.mediaStatusChanged.connect(lambda s: self._st())
        self.pa.errorOccurred.connect(lambda *a: self._err(self.va, self.pa)); self.pb.errorOccurred.connect(lambda *a: self._err(self.vb, self.pb))
        self.sync = QTimer(self); self.sync.timeout.connect(self._sync); self.sync.start(400)
        K = [('Space', lambda: self.toggle()), ('Left', lambda: self.rel_s(-1)), ('Right', lambda: self.rel_s(1)), ('Ctrl+Left', lambda: self.rel_s(-5)), ('Ctrl+Right', lambda: self.rel_s(5)),
             ('Shift+Left', lambda: self.rel_p(-1)), ('Shift+Right', lambda: self.rel_p(1)), ('Ctrl+Shift+Left', lambda: self.rel_p(-5)), ('Ctrl+Shift+Right', lambda: self.rel_p(5)),
             ('Ctrl+Up', lambda: self.speed(1)), ('Ctrl+Down', lambda: self.speed(-1)), ('F', self.full), ('F11', self.full), ('Esc', self._esc), ('D', lambda: self.frame(-1)), ('G', lambda: self.frame(1))]
        self.scs = []
        for k, fn in K:
            sc = QShortcut(QKeySequence(k), self); sc.setAutoRepeat(k not in ('Space', 'F', 'F11', 'Esc')); sc.activated.connect(fn); self.scs.append(sc)
        for vw, pth in ((self.va, a_path), (self.vb, b_path)):
            if not os.path.exists(pth): vw.note = '檔案不見了：' + str(pth)
        self.pa.setSource(QUrl.fromLocalFile(str(a_path))); self.pb.setSource(QUrl.fromLocalFile(str(b_path))); self.pa.play(); self.pb.play()
        def info(p):
            try:
                q = core.probe(ENG.ffprobe, Path(p)); sz = os.path.getsize(p)
                if p == b_path and float(q.get('fps') or 0) > 1: self.fstep = 1000.0 / float(q['fps'])     # 一格多長（D／G 逐格）
                return f"{fmt_b(sz)} · {q.get('vcodec') or '?'} {q.get('w')}×{q.get('h')} · {(q.get('vbr') or 0) / 1e6:.1f} Mbps" if q.get('ok') else fmt_b(sz)
            except Exception: return ''
        bg(lambda: (info(a_path), info(b_path)), self._info)
        ENG.log.w(f'並排比較：{a_path}（從 {a_off:.1f}s）vs {b_path}（從 {b_off:.1f}s）')

    def _info(self, ab):
        try: self.va.info, self.vb.info = ab[0], ab[1]; self.va.update(); self.vb.update()
        except RuntimeError: pass

    # ---- 版面
    def _lay_txt(self): self.blay.setText('⇅ 改上下' if self.sp.orientation() == Qt.Horizontal else '⇄ 改左右')

    def _lay(self):
        o = Qt.Vertical if self.sp.orientation() == Qt.Horizontal else Qt.Horizontal; self.sp.setOrientation(o); self._lay_txt()
        ENG.cfg.set('cmp_layout', 'lr' if o == Qt.Horizontal else 'tb'); n = self.sp.count(); self.sp.setSizes([1000] * n)

    def _swap(self):
        w0 = self.sp.widget(0); self.sp.insertWidget(1, w0); self.sp.setSizes([1000, 1000])

    def _au_txt(self): self.bau.setText('🔊 聽：' + ('轉好的' if self.aud == 'b' else '原檔'))

    def _au(self):
        self.aud = 'a' if self.aud == 'b' else 'b'
        if self.aud == 'a': self.pb.setAudioOutput(None); self.pa.setAudioOutput(self.ao)
        else: self.pa.setAudioOutput(None); self.pb.setAudioOutput(self.ao)
        self.pa.setPlaybackRate(self.rate); self.pb.setPlaybackRate(self.rate); self.sync_hold = time.monotonic() + 1.0      # 換成以另一邊為準
        self._au_txt()

    def _hover(self, rel):
        self.va.set_rel(rel); self.vb.set_rel(rel)

    def _zoom(self, z):
        self.va.zoom = self.vb.zoom = z; self.va.update(); self.vb.update(); self.show_osd(f'放大鏡 ×{z:g}')

    def show_osd(self, t, ms=1500): self.osd.setText(t); self.osd_t.start(ms)

    # ---- 時間（時間軸 0＝A 的 a_off、B 的 b_off）
    def dur(self):
        a = self.pa.duration() - self.off[0] if 'a' not in self.bad else 0; b = self.pb.duration() - self.off[1] if 'b' not in self.bad else 0
        L = [x for x in (a, b) if x > 0]; return int(min(L)) if L else 0

    def _range(self): self.sl.setRange(0, max(0, self.dur()))

    def pos(self):
        if 'b' in self.bad: return max(0, self.pa.position() - int(self.off[0]))
        return max(0, self.pb.position() - int(self.off[1]))

    def set_pos(self, ms):
        ms = int(max(0, min(self.dur() or ms, ms))); self.pa.setPosition(int(ms + self.off[0])); self.pb.setPosition(int(ms + self.off[1]))

    def _tl(self, ms): self.tl.setText(f'{fmt_t(ms / 1000)} / {fmt_t(self.dur() / 1000)}')

    def _pos(self, _ms):
        p = self.pos()
        if not self.sl.isSliderDown() and self.drag is None: self.sl.setValue(p)
        self._tl(p)

    def _st(self):
        ok = (self.QMP.MediaStatus.LoadedMedia, self.QMP.MediaStatus.BufferedMedia, self.QMP.MediaStatus.BufferingMedia)
        if self.pa.mediaStatus() == self.QMP.MediaStatus.InvalidMedia: self.bad.add('a')
        if self.pb.mediaStatus() == self.QMP.MediaStatus.InvalidMedia: self.bad.add('b')
        sa = self.pa.mediaStatus() in ok or 'a' in self.bad; sb = self.pb.mediaStatus() in ok or 'b' in self.bad
        if not self.started and sa and sb and len(self.bad) < 2:                 # 一邊放不了：另一邊照樣能看、能拖
            self.started = True; self._range(); self.set_pos(int(self.t0 * 1000))
            for vw, pl in ((self.va, self.pa), (self.vb, self.pb)):
                try:
                    if not pl.isSeekable(): vw.note = '這個檔內建播放器沒辦法跳時間'; self.show_osd(f'⚠ {vw.tag} 內建播放器沒辦法跳時間（.ts 之類），兩邊可能對不齊', 5000)
                except Exception: pass

    def _err(self, vw, pl):
        vw.note = '✖ 內建播放器放不了：' + str(pl.errorString())[:120]; vw.update()
        self.bad.add('a' if pl is self.pa else 'b'); self._st(); self._range()

    def _ref(self):
        """以哪一邊為準：有聲音的那邊（聲音不能跳）；那邊壞了就用另一邊."""
        a, b = (self.pa, self.off[0]), (self.pb, self.off[1])
        if 'b' in self.bad: return a, b
        if 'a' in self.bad: return b, a
        return (b, a) if self.aud == 'b' else (a, b)

    def _sync(self):
        """V0.1.85 兩邊對齊：以有聲音的那邊為準。差一點點（0.06～1 秒）就讓另一邊快／慢 3% 慢慢追上（不跳、不卡）；
        差超過 1 秒才直接跳，跳完等 1.5 秒再看。播到尾巴兩邊一起停在最後，不會又從頭開始."""
        if self.drag is not None or self.sl.isSliderDown() or not self.started: return
        try:
            PS = self.QMP.PlaybackState; (R, ro), (F, fo) = self._ref(); d = self.dur(); p = R.position() - ro
            if d > 0 and (p >= d - 60 or R.mediaStatus() == self.QMP.MediaStatus.EndOfMedia or (len(self.bad) == 0 and F.mediaStatus() == self.QMP.MediaStatus.EndOfMedia)):
                if self.playing() or F.playbackState() == PS.PlayingState:
                    self.pa.pause(); self.pb.pause(); self.set_pos(max(0, d - 40)); self.pa.setPlaybackRate(self.rate); self.pb.setPlaybackRate(self.rate); self.show_osd('⏹ 播完了')
                return
            if self.bad: return
            if R.playbackState() != F.playbackState():
                (F.play if R.playbackState() == PS.PlayingState else F.pause)()
            if R.playbackState() != PS.PlayingState or time.monotonic() < self.sync_hold: F.setPlaybackRate(self.rate); return
            gap = (F.position() - fo) - p                                       # >0：另一邊跑太前面
            if abs(gap) > 1000: F.setPosition(int(p + fo)); F.setPlaybackRate(self.rate); self.sync_hold = time.monotonic() + 1.5
            elif abs(gap) > 60: F.setPlaybackRate(round(self.rate * (0.97 if gap > 0 else 1.03), 3))
            else: F.setPlaybackRate(self.rate)
        except Exception: pass

    def playing(self): return (self.pa if 'b' in self.bad else self.pb).playbackState() == self.QMP.PlaybackState.PlayingState

    def toggle(self):
        if self.playing(): self.pa.pause(); self.pb.pause()
        else:
            d = self.dur(); p_ = self.pos()
            self.set_pos(0 if d > 0 and p_ >= d - 100 else p_); self.sync_hold = time.monotonic() + 1.0; self.pa.play(); self.pb.play()

    def live(self, ms):
        self.seek_want = int(ms)
        if not self.seek_t.isActive(): self._flush()

    def _flush(self):
        if self.seek_want is None: return
        self.set_pos(self.seek_want); self.seek_want = None; self.seek_t.start(80)

    def _scrub_begin(self):
        if self.scrub_play is None: self.scrub_play = self.playing()
        if self.scrub_play: self.pa.pause(); self.pb.pause()

    def _scrub_end(self, ms):
        self.seek_want = None; self.seek_t.stop(); self.set_pos(ms)
        if self.scrub_play: self.pa.play(); self.pb.play()
        self.scrub_play = None

    def _kbase(self):
        """按住方向鍵：從上一次要跳到的地方往下加（播放器還沒跳到，不要讀現在位置），跳的動作經過 live() 節流."""
        return self.key_to if (self.key_to is not None and time.monotonic() - self.key_t < 0.6) else self.pos()

    def _kgo(self, to):
        d = self.dur(); to = int(max(0, min(d, to) if d else max(0, to))); self.key_to = to; self.key_t = time.monotonic()
        self.live(to); self.sl.setValue(to); self._tl(to); self.sync_hold = time.monotonic() + 1.0; return to

    def rel_s(self, s):
        to = self._kgo(self._kbase() + int(s * 1000)); self.show_osd(('⏩ +' if s >= 0 else '⏪ −') + f'{abs(s):g} 秒　→ {fmt_t(max(0, to) / 1000)}')

    def rel_p(self, pc):
        d = self.dur()
        if d > 0: to = self._kgo(self._kbase() + int(d * pc / 100)); self.show_osd(('⏩ +' if pc >= 0 else '⏪ −') + f'{abs(pc):g}%　→ {fmt_t(max(0, to) / 1000)}')

    def frame(self, k):
        self.pa.pause(); self.pb.pause(); self._kgo(self._kbase() + int(round(k * self.fstep)))

    def speed(self, n):
        now = time.monotonic(); d = 1 if n >= 0 else -1; S = self.sf
        S['n'] = S['n'] + 1 if (now - S['t'] < 0.35 and S['d'] == d) else 0; S['t'] = now; S['d'] = d
        st = 0.01 if S['n'] < 6 else 0.02 if S['n'] < 15 else 0.05 if S['n'] < 30 else 0.1
        r = max(0.1, min(4.0, round(self.rate + d * st, 2))); self.rate = r; self.sync_hold = time.monotonic() + 1.0; self.pa.setPlaybackRate(r); self.pb.setPlaybackRate(r); self.spd.setText(f'{r:.2f}x'); self.show_osd(f'速度 ×{r:.2f}')

    def full(self):
        if self.isFullScreen(): self.showNormal()
        else: self.showFullScreen()

    def _esc(self):
        if self.isFullScreen(): self.showNormal()
        else: self.close()

    def eventFilter(self, obj, e):
        try:
            t = e.type()
            if t == QEvent.MouseButtonDblClick: self.full(); return True
            if t == QEvent.MouseButtonPress and e.button() == Qt.LeftButton:
                x_ = e.position().x(); self.drag = {'x0': x_, 'x': x_, 't': time.monotonic(), 'p0': self.pos(), 'acc': 0.0, 'moved': False, 'w': max(200, obj.width())}; return True
            if t == QEvent.MouseMove and self.drag is not None:
                g = self.drag; x = e.position().x(); dx = x - g['x0']
                if abs(dx) > 6 and not g['moved']: g['moved'] = True; self._scrub_begin()
                now = time.monotonic(); ddx = x - g['x']; dt = max(0.008, now - g['t']); g['x'] = x; g['t'] = now
                mx = drag_mx(self.dur()); sp = abs(ddx) / (dt * 1000); kk = min(1.0, max(0.12, (sp - 0.05) / 1.3))
                g['acc'] = max(-mx, min(mx, g['acc'] + ddx / g['w'] * mx * 1.6 * kk))
                if g['moved']:
                    tgt = int(max(0, min(self.dur() or 0, g['p0'] + g['acc']))); self.live(tgt); self.sl.setValue(tgt); self._tl(tgt)
                    d = (tgt - g['p0']) / 1000; self.show_osd(f'{"⏩ +" if d >= 0 else "⏪ −"}{fmt_t(abs(d))}　→ {fmt_t(tgt / 1000)}', 3000)
                return False                                                     # 讓放大鏡也跟著動
            if t == QEvent.MouseButtonRelease and self.drag is not None:
                g = self.drag; self.drag = None
                if g['moved']: self._scrub_end(int(max(0, min(self.dur() or 0, g['p0'] + g['acc']))))
                return True
        except Exception: ENG.log.err('並排比較拖曳')
        return super().eventFilter(obj, e)

    def _teardown(self):
        if getattr(self, '_torn', False): return
        self._torn = True
        try:
            self.sync.stop(); self.seek_t.stop()
            for pl in (self.pa, self.pb): pl.stop(); pl.setSource(QUrl()); pl.setVideoSink(None); pl.setAudioOutput(None)
        except Exception: pass

    def done(self, r):
        self._teardown(); super().done(r)

    def closeEvent(self, e):
        self._teardown(); super().closeEvent(e)


# ============================================================ 排除資料夾（檔案總管右鍵、設定頁共用）
def exclude_folder(win, d):
    d = os.path.normpath(str(d))
    if any(core.path_key(d) == core.path_key(r) for r in ENG.cfg.get('roots') or []):
        QMessageBox.information(win, '排除資料夾', f'{d}\n是影片庫本身。不想要整顆的話，到「⚙ 設定」→ 影片庫 → 移除選取的。'); return
    if any(core.path_key(d) == core.path_key(x) for x in ENG.cfg.get('ex_dirs') or []): win.msg('這個資料夾已經排除了'); return
    if QMessageBox.question(win, '排除資料夾', f'排除這個資料夾（含底下所有子資料夾）？\n\n{d}\n\n'
                            '裡面的影片會從清單拿掉，也不會再做預覽圖、不會出現在轉檔。\n檔案不會動；之後在「⚙ 設定」取消排除，重新掃描就會回來（做好的預覽圖還在）。') != QMessageBox.Yes: return
    bg(lambda: ENG.add_exclude(path=d), lambda n: _ex_done(win, f'已排除 {d}（拿掉 {n:,} 部影片）'))


def exclude_name(win, name):
    name = str(name or '').strip().strip('\\/')
    if not name: win.msg('先輸入資料夾名稱'); return
    if any(name.lower() == str(x).strip().lower() for x in ENG.cfg.get('ex_names') or []): win.msg('這個名稱已經排除了'); return
    bg(lambda: ENG.add_exclude(name=name), lambda n: _ex_done(win, f'已排除名稱「{name}」的資料夾（拿掉 {n:,} 部影片）'))


def _ex_done(win, s):
    win.msg(s); win.browse.load_tree(); win.browse.load_list(); win.setp._load_ex()


# ============================================================ 檔案總管
class BrowsePage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.cur = None; self.folder = ''; self.rows = []; self.tree_nodes = {}; self.poll_t = 0
        lay = QHBoxLayout(self); lay.setContentsMargins(6, 6, 6, 6); sp = QSplitter(Qt.Horizontal); lay.addWidget(sp)
        # 左：資料夾＋清單
        left = QWidget(); lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0)
        r = QHBoxLayout(); lv.addLayout(r)
        self.b_add = QPushButton('➕ 加入硬碟／資料夾'); self.b_scan = QPushButton('🔄 重新掃描'); r.addWidget(self.b_add); r.addWidget(self.b_scan)
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True); self.tree.setColumnCount(1); lv.addWidget(self.tree, 2)
        # 分級標籤列（參考 TikLive 分級頁）：全部／未分級／S／A／E／F 各幾部，點一下就篩選；下面一條分級進度
        chips = QHBoxLayout(); chips.setSpacing(4); lv.addLayout(chips); self.chips = {}
        for k, nm, col in (('all', '全部', '#4dc9ff'), ('ready', '✅ 可以審', '#45d483'), ('nograde', '未分級', '#9aa5b3'), ('S', 'S', GC['S']), ('A', 'A', GC['A']), ('E', 'E', GC['E']), ('F', 'F', GC['F'])):
            c = QPushButton(nm); c.setCheckable(True); c.setCursor(Qt.PointingHandCursor)
            c.setStyleSheet(f'QPushButton{{border:1px solid {col};border-radius:11px;padding:2px 9px;color:{col};font-weight:700}}QPushButton:checked{{background:{col};color:#0b0e13}}')
            c.clicked.connect(lambda _c=False, k=k: self._chip(k)); chips.addWidget(c); self.chips[k] = c
        chips.addStretch(1)
        self.gprog = QProgressBar(); self.gprog.setFixedHeight(12); self.gprog.setTextVisible(True); self.gprog.setFormat('已分級 %v / %m')
        self.gprog.setStyleSheet('QProgressBar{font-size:9px;height:12px;border-radius:5px}QProgressBar::chunk{background:#45d483;border-radius:4px}'); lv.addWidget(self.gprog)
        f = QHBoxLayout(); lv.addLayout(f)
        self.flt = QComboBox()
        for t, k in (('全部', 'all'), ('✅ 可以審（預覽圖好了、還沒分級）', 'ready'), ('預覽圖好了', 'thumbok'), ('沒看過', 'unseen'), ('⭐ 收藏', 'fav'), ('有初剪', 'cut'), ('預覽圖還沒好', 'nothumb'), ('S', 'S'), ('A', 'A'), ('E', 'E'), ('F', 'F'), ('未分級', 'nograde'),
                     ('🏷 有顏色標籤', 'tagany'), *[(f'{v[0]} {v[1]}標', 'tag:' + k2) for k2, v in TAGS.items()], ('✎ 有備註', 'noted'), ('🔖 有書籤', 'bmk'), ('😴 大多是靜止的', 'still'), ('📤 已經複製到上傳', 'uped'), ('📤 S／A 還沒上傳', 'notup'), ('✅ 複製了、還沒發佈', 'notpub'), ('✅ 已發佈', 'pub'), ('⚠ 讀不了／可能壞掉', 'bad'), ('🔇 只有聲音', 'novideo'), ('📦 已歸檔（看歸進 VideoSIFT 的）', 'archived')): self.flt.addItem(t, k)
        self.sort = QComboBox()
        for t, k in (('名稱', 'name'), ('最大', 'size'), ('最小', 'size_asc'), ('最長', 'dur'), ('最短', 'dur_asc'), ('最新', 'mtime'), ('分級', 'grade'), ('最近看過', 'viewed'), ('最近加入', 'added'), ('😴 靜止多→少', 'still'), ('📤 最近上傳', 'up_t')): self.sort.addItem(t, k)
        self.sub = QCheckBox('含子資料夾'); self.sub.setChecked(bool(ENG.cfg.get('sub_folders')))
        f.addWidget(self.flt); f.addWidget(self.sort); f.addWidget(self.sub)
        f2 = QHBoxLayout(); lv.addLayout(f2); self.vmode = QComboBox(); self.vmode.addItem('▦ 卡片', 'card'); self.vmode.addItem('☰ 清單', 'list')
        self.csize = QComboBox()
        for t, k in (('小卡', 120), ('中卡', 150), ('大卡', 190), ('特大', 240)): self.csize.addItem(t, k)
        f2.addWidget(QLabel('顯示')); f2.addWidget(self.vmode); f2.addWidget(self.csize); f2.addStretch(1)
        self.b_arch = QPushButton('📦 一鍵歸檔'); self.b_arch.setToolTip('把目前資料夾（含子資料夾）裡已經分好級的，一次歸到 VideoSIFT 的 S／A／E／F 資料夾'); self.am = QMenu(self)
        self.b_arch.setMenu(self.am); self.am.aboutToShow.connect(self._fill_arch_menu); f2.addWidget(self.b_arch)
        self.b_purge = QPushButton('🔥 清空待刪'); self.b_purge.setStyleSheet('QPushButton{color:#fff;background:#c62845;border:1px solid #c62845;font-weight:700}')
        self.b_purge.setToolTip('V0.2.01 各硬碟 VideoSIFT\\待刪 裡的檔案永久刪除（空間馬上回來），預覽圖、人臉資料一起清掉。\n初剪的檔 100% 保留。'); self.b_purge.clicked.connect(self.purge_trash); f2.addWidget(self.b_purge); self.b_purge.setVisible(False)
        self.vmode.setCurrentIndex(max(0, self.vmode.findData(ENG.cfg.get('list_view') or 'card'))); self.csize.setCurrentIndex(max(0, self.csize.findData(int(ENG.cfg.get('card_w') or 150))))
        self.q = QLineEdit(); self.q.setPlaceholderText('搜尋檔名'); self.q.setClearButtonEnabled(True)
        qrow_ = QHBoxLayout(); qrow_.addWidget(self.q, 1); self.b_cre = QPushButton('👥 作者'); self.b_cre.setToolTip('🧪 依作者／主播分組（從檔名猜）'); qrow_.addWidget(self.b_cre); self.b_mon = QPushButton('📅 月份'); self.b_mon.setToolTip('🧪 依月份（檔案時間）：每個月幾部、分級了多少，點兩下只看那個月'); qrow_.addWidget(self.b_mon); self.b_csv = QPushButton('📤 CSV'); self.b_csv.setToolTip('🧪 把目前清單（含篩選、搜尋）存成 Excel 能開的 CSV'); qrow_.addWidget(self.b_csv); self.b_view = QPushButton('⭐'); self.b_view.setToolTip('🧪 常用篩選：存下／叫出 資料夾＋分級＋搜尋＋排序＋時長'); qrow_.addWidget(self.b_view); self.b_rec = QPushButton('🕘'); self.b_rec.setToolTip('🧪 最近開過的資料夾'); qrow_.addWidget(self.b_rec); lv.addLayout(qrow_)
        self.b_rnd = QPushButton('🎲'); self.b_rnd.setToolTip('🎲 隨便抽一部這個資料夾還沒分級的（Ctrl+R）'); self.b_rnd.setVisible(bool(lab_cfg().get('random_pick'))); self.b_rnd.clicked.connect(self.random_pick); qrow_.insertWidget(1, self.b_rnd)   # V0.3.84
        self.b_syn = QPushButton('🔎＋'); self.b_syn.setToolTip('點一下加一個搜尋條件（不用記語法）'); self.b_syn.setVisible(bool(lab_cfg().get('smart_search'))); self.b_syn.clicked.connect(self.syn_menu); qrow_.insertWidget(1, self.b_syn)   # V0.3.83
        self.b_cre.setVisible(bool(lab_cfg().get('creators'))); self.b_cre.clicked.connect(self.creators_dlg)
        self.b_csv.setVisible(bool(lab_cfg().get('list_csv'))); self.b_csv.clicked.connect(self.export_csv)
        self.b_view.setVisible(bool(lab_cfg().get('views'))); self.b_view.clicked.connect(self.views_menu)
        self.b_mon.setVisible(bool(lab_cfg().get('months'))); self.b_mon.clicked.connect(self.months_dlg)
        self.b_rec.setVisible(bool(lab_cfg().get('recent_dirs'))); self.b_rec.clicked.connect(self.recent_menu)
        try:                                                                    # V0.2.65 🔎 搜尋紀錄：打字時下拉出以前搜過的
            from PySide6.QtWidgets import QCompleter
            from PySide6.QtCore import QStringListModel
            self.q_hm = QStringListModel(ENG.search_hist() if lab_cfg().get('search_hist') else []); self.q_cp = QCompleter(self.q_hm, self); self.q_cp.setCaseSensitivity(Qt.CaseInsensitive)
            self.q_cp.setFilterMode(Qt.MatchContains); self.q.setCompleter(self.q_cp); self.q.returnPressed.connect(self._q_push); self.q.editingFinished.connect(self._q_push)
        except Exception: ENG.log.err('搜尋紀錄')
        for b_, t_ in ((self.b_cre, '👥'), (self.b_mon, '📅'), (self.b_csv, '📤'), (self.b_view, '⭐'), (self.b_rec, '🕘')):    # V0.2.57 搜尋框旁的小按鈕只放圖示（說明在滑鼠停上去）
            b_.setText(t_); b_.setFixedWidth(36); b_.setToolTip(b_.toolTip().replace('🧪 ', ''))
        self.durw = QWidget(); dl_ = QHBoxLayout(self.durw); dl_.setContentsMargins(0, 0, 0, 0); dl_.setSpacing(4); self.dur_b = {}; self.dur_k = ''   # V0.2.37 ⏱ 時長篩選
        for k_, n_ in core.DUR_NAMES:
            b_ = QPushButton(n_); b_.setCheckable(True); b_.setChecked(k_ == ''); b_.setStyleSheet('QPushButton{padding:2px 8px;border-radius:10px} QPushButton:checked{background:#2d6cdf;color:#fff}')
            b_.clicked.connect(lambda _c=False, k=k_: self.set_dur(k)); dl_.addWidget(b_); self.dur_b[k_] = b_
        self.fltrow = QHBoxLayout(); self.fltrow.setSpacing(10); lv.addLayout(self.fltrow)   # V0.2.94 ⏱ 時長、📺 畫質 放同一排（省一排高度）
        self.fltrow.addWidget(self.durw); self.durw.setVisible(bool(lab_cfg().get('dur_chips')))
        self.resw = QWidget(); rl_ = QHBoxLayout(self.resw); rl_.setContentsMargins(0, 0, 0, 0); rl_.setSpacing(4); self.res_b = {}; self.res_k = ''   # V0.2.78 📺 畫質篩選
        for k_, n_ in core.RES_NAMES:
            b_ = QPushButton(n_); b_.setCheckable(True); b_.setChecked(k_ == ''); b_.setStyleSheet('QPushButton{padding:2px 8px;border-radius:10px} QPushButton:checked{background:#8a5cf6;color:#fff}')
            b_.clicked.connect(lambda _c=False, k=k_: self.set_res(k)); rl_.addWidget(b_); self.res_b[k_] = b_
        self.fltrow.addWidget(self.resw); self.fltrow.addStretch(1); self.resw.setVisible(bool(lab_cfg().get('res_chips')))
        self.lst = QListWidget(); self.lst.setUniformItemSizes(True); self.lst.setSelectionMode(QAbstractItemView.ExtendedSelection); lv.addWidget(self.lst, 3)
        self.lst.setToolTip('Ctrl／Shift＋點＝多選，Ctrl+A＝全選；右鍵＝選單\nEnter＝播放　N＝下一部沒分級的　S A E F 0＝分級　Del＝移到待刪　Shift+Del＝刪除已剪輯的原檔　Ctrl+Z＝復原分級／收藏記號')
        self.bbar = QFrame(); self.bbar.setObjectName('hero'); bl = QVBoxLayout(self.bbar); bl.setContentsMargins(6, 4, 6, 4); bl.setSpacing(4)
        self.bb_l = QLabel(''); bl.addWidget(self.bb_l); br1 = QHBoxLayout(); br2 = QHBoxLayout(); bl.addLayout(br1); bl.addLayout(br2)
        for k in ('S', 'A', 'E', 'F', ''):
            x = QPushButton(k or '—'); x.setFixedWidth(34); c = GC.get(k, '#9aa5b3'); x.setStyleSheet(f'QPushButton{{border:2px solid {c};font-weight:800;color:{c};padding:2px}}')
            x.setToolTip(f'選的全部改成 {k}（{GN[k]}）' if k else '選的全部改成未分級'); x.clicked.connect(lambda _c=False, k=k: self.grade_many(k)); br1.addWidget(x)
        self.bb_fav = QPushButton('⭐ 收藏'); self.bb_front = QPushButton('⚡ 先做預覽圖'); br1.addWidget(self.bb_fav); br1.addWidget(self.bb_front); br1.addStretch(1)
        self.bb_cat = QPushButton('📦 歸類到…'); self.bb_cm = QMenu(self); self.bb_cat.setMenu(self.bb_cm); self.bb_cm.aboutToShow.connect(lambda: self._fill_cat_menu(self.bb_cm))
        self.bb_trash = QPushButton('🗑 待刪'); self.bb_del = QPushButton('🗑 刪除原檔'); self.bb_conv = QPushButton('🔁 轉檔'); self.bb_ex = QPushButton('🚫 排除資料夾')
        self.bb_del.setStyleSheet('QPushButton{color:#ff6577;font-weight:700}')
        for x in (self.bb_cat, self.bb_trash, self.bb_del, self.bb_conv, self.bb_ex): br2.addWidget(x)
        br2.addStretch(1); lv.addWidget(self.bbar); self.bbar.hide()
        self.bb_fav.clicked.connect(self.fav_many); self.bb_front.clicked.connect(self.front_many); self.bb_trash.clicked.connect(self.trash_many)
        self.bb_del.clicked.connect(self.del_many); self.bb_conv.clicked.connect(self.conv_many); self.bb_ex.clicked.connect(self.ex_many)
        self.cnt = QLabel(''); self.cnt.setObjectName('muted'); self.cnt.setWordWrap(True); lv.addWidget(self.cnt)
        self.undo = []; self.item_of = {}; self.row_of = {}; self.card_w = int(ENG.cfg.get('card_w') or 150); self.cards = OrderedDict(); self.cload = CardLoader()
        self.card_del = CardDelegate(self); self.plain_del = QStyledItemDelegate(self.lst); self._vp_t = QTimer(self); self._vp_t.setSingleShot(True); self._vp_t.timeout.connect(lambda: self.lst.viewport().update())
        self.scrub = None; self.lst.viewport().setMouseTracking(True); self.lst.viewport().installEventFilter(self)
        self.apply_view()
        self.vmode.currentIndexChanged.connect(lambda _i: (ENG.cfg.set('list_view', self.vmode.currentData()), self.apply_view()))
        self.csize.currentIndexChanged.connect(lambda _i: (ENG.cfg.set('card_w', int(self.csize.currentData())), self.apply_view()))
        sp.addWidget(left)
        # 右：影片資訊＋格子
        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(0, 0, 0, 0); self.left_w = left
        # 🧪 專注分級：上一部／下一部＋大分級鍵（只有專注模式時出現）
        self.fbar = QFrame(); self.fbar.setObjectName('hero'); fb = QHBoxLayout(self.fbar); fb.setContentsMargins(8, 4, 8, 4)
        fp = QPushButton('⬅ 上一部（PgUp）'); fn = QPushButton('下一部（PgDn）➡'); fp.clicked.connect(lambda: self.step_item(-1)); fn.clicked.connect(lambda: self.step_item(1)); fb.addWidget(fp); fb.addWidget(fn); fb.addSpacing(16)
        for k in ('S', 'A', 'E', 'F'):
            x = QPushButton(f'{k}  {GN[k]}'); c = GC[k]; x.setMinimumHeight(38)
            x.setStyleSheet(f'QPushButton{{border:2px solid {c};color:{c};font-weight:800;font-size:15px;padding:4px 14px}}QPushButton:hover{{background:{c};color:#111}}')
            x.clicked.connect(lambda _c=False, k=k: self.grade_many(k)); fb.addWidget(x)
        fb.addStretch(1); self.fpos = QLabel(''); self.fpos.setObjectName('muted'); fb.addWidget(self.fpos); fx = QPushButton('離開專注（Esc）'); fx.clicked.connect(lambda: self.set_focus_mode(False)); fb.addWidget(fx)
        rv.addWidget(self.fbar); self.fbar.hide(); self.focus_on = False
        self.h1 = QLabel('← 左邊選一部影片'); self.h1.setObjectName('title'); self.h1.setWordWrap(True); rv.addWidget(self.h1)
        self.h2 = QLabel(''); self.h2.setObjectName('muted'); self.h2.setWordWrap(True); self.h2.setTextInteractionFlags(Qt.TextSelectableByMouse); rv.addWidget(self.h2)
        bw_ = QWidget(); b = FlowLayout(bw_, 5); rv.addWidget(bw_); self.gb = {}          # V0.1.53 按鈕太多時自動換行（視窗可以拉窄）
        self.b_prev = QPushButton('◀ 上一則'); self.b_prev.setToolTip('清單裡的上一部'); self.b_prev.clicked.connect(lambda: self.step_item(-1)); b.addWidget(self.b_prev)   # V0.2.06
        for k in ('S', 'A', 'E', 'F', ''):
            x = QPushButton(k or '—'); x.setCheckable(True); x.setFixedWidth(46); c = GC.get(k, '#9aa5b3')
            x.setStyleSheet(f'QPushButton{{border:2px solid {c};font-weight:800;color:{c}}}QPushButton:checked{{background:{c};color:#111}}')
            x.setToolTip(f'{k}：{GN[k]}' if k else '未分級'); b.addWidget(x); self.gb[k] = x
        self.b_fold = QPushButton('📁 資料夾'); self.b_fold.setToolTip('用資料夾分類：選一個資料夾（或新增），這部自動標 S，搬到它所在硬碟的 VideoSIFT\\<資料夾>（多選時一次全部）')
        self.b_fold.setStyleSheet(f'QPushButton{{border:2px solid {GC["S"]};color:{GC["S"]};font-weight:800}}'); self.b_fold.clicked.connect(self._fold_menu); b.addWidget(self.b_fold)   # V0.2.29
        self.b_next = QPushButton('下一則 ▶'); self.b_next.setToolTip('清單裡的下一部'); self.b_next.clicked.connect(lambda: self.step_item(1)); b.addWidget(self.b_next)
        self.l_guess = QLabel(''); self.l_guess.setObjectName('muted'); self.l_guess.hide(); b.addWidget(self.l_guess)   # V0.2.62 🤖 分級建議
        self.b_fav = QPushButton('⭐ 收藏'); self.b_cut = QPushButton('✂ 輸出初剪（0 段）'); self.b_clear = QPushButton('清除選取'); self.b_segp = QPushButton('▶ 預覽選的片段')
        self.b_segp.setToolTip('🧪 只連續播你選的那幾段，剪之前先確認'); self.b_segp.setVisible(bool(lab_cfg().get('seg_preview')))
        self.b_focus = QPushButton('⛶ 專注'); self.b_focus.setToolTip('🧪 專注分級：收起左邊，預覽格子佔滿畫面；PgUp／PgDn 換部、S A E F 分級、Esc 離開'); self.b_focus.setVisible(bool(lab_cfg().get('focus_mode')))
        self.b_play = QPushButton('▶ 播放'); self.b_dir = QPushButton('📂 資料夾'); self.b_trash = QPushButton('🗑 移到待刪'); self.b_untrash = QPushButton('↩ 復原搬移'); self.b_untrash.setToolTip('上一次「移到待刪／歸檔／搬去收藏」整批搬回原來的位置'); self.b_untrash.clicked.connect(lambda: undo_last_move(self.win)); self.b_front = QPushButton('⚡ 先做這部的預覽圖')
        self.b_cat = QPushButton('📦 歸類'); self.b_cm = QMenu(self); self.b_cat.setMenu(self.b_cm); self.b_cm.aboutToShow.connect(lambda: self._fill_cat_menu(self.b_cm))
        self.b_cat.setToolTip('歸到 VideoSIFT 的分級資料夾或你自己的分類（工作用、家庭日…）；歸進去就不再出現在清單')
        self.b_del = QPushButton('🗑 刪除原檔'); self.b_del.setStyleSheet('QPushButton{color:#ff6577;font-weight:700}')
        self.b_del.setToolTip('已經剪好了：把原檔丟到資源回收筒，連它的 2 秒預覽圖一起刪。剪好的初剪檔永久保留'); self.b_del.hide()
        for x in (self.b_focus, self.b_fav, self.b_cut, self.b_segp, self.b_del, self.b_cat, self.b_clear, self.b_play, self.b_dir, self.b_trash, self.b_untrash, self.b_front): b.addWidget(x)
        b.addWidget(QLabel('間隔')); self.gsec = QSpinBox(); self.gsec.setRange(2, 600); self.gsec.setSingleStep(2); self.gsec.setSuffix(' 秒一張')
        self.gsec.setToolTip('格子上每幾秒顯示一張（2、4、6…600）。直接用已經做好的 2 秒一張預覽圖挑著顯示，不用重做。Alt＋滾輪也可以調'); self.gsec.setKeyboardTracking(False)
        self.gsec.setValue(int(ENG.cfg.get('grid_sec') or 2)); b.addWidget(self.gsec)
        b.addWidget(QLabel('一列')); self.cols = QSpinBox(); self.cols.setRange(2, 30); self.cols.setValue(int(ENG.cfg.get('grid_cols') or 10)); self.cols.setSuffix(' 張'); b.addWidget(self.cols)
        self.hint = QLabel('點一格＝選；再點＝取消；按住拖曳＝圈選一段；從已選的格拖＝取消拖過的；Shift＋點＝選到這格；長按或點兩下＝播放；右鍵＝全選／反選；Ctrl＋滾輪＝一列幾張；Alt＋滾輪＝間隔')
        self.hint.setObjectName('muted'); shrinkable(self.hint, True); rv.addWidget(self.hint)
        self.b_rv = QCheckBox('📜 連續分級'); self.b_rv.setChecked(ENG.cfg.get('rv_cont') is not False); b.addWidget(self.b_rv)
        self.b_rv.setToolTip('V0.2.09 右邊滾到底會接著顯示下一部（中間空一行）。上一部完全滾出畫面、又沒分級的，自動標 F；有按分級的照你按的。\n有選片段就滾過去：選的全部合併輸出成 1 個初剪檔、標 F。部數不限。')
        self.b_rv.toggled.connect(lambda on: (ENG.cfg.set('rv_cont', bool(on)), self._rv_clear()))
        self.legend = QLabel('🎬 橘線＝換場景　🔥 紅線＝動得多　😴 變暗＝靜止／黑畫面　🔖 黃色小塊＝書籤'); self.legend.setObjectName('muted')   # V0.3.20 格子標記說明
        self.legend.setVisible(bool(lab_cfg().get('scenes') or lab_cfg().get('bookmarks'))); rv.addWidget(self.legend)
        self.grid = ThumbGrid(); self.area = GridArea(self.grid); rv.addWidget(self.area, 1); self.grid.set_cols(self.cols.value()); self.grid.set_sec(self.gsec.value())
        self.nxt = ThumbGrid(); self.nxt.setAttribute(Qt.WA_TransparentForMouseEvents, True); self.area.set_follower(self.nxt); self.nxt.set_cols(self.cols.value()); self.nxt.set_sec(self.gsec.value())
        self.nxt2 = ThumbGrid(); self.nxt2.setAttribute(Qt.WA_TransparentForMouseEvents, True); self.area.set_follower2(self.nxt2); self.nxt2.set_cols(self.cols.value()); self.nxt2.set_sec(self.gsec.value())
        self.rv = {'n': 1, 'row': None, 'want': None, 'row2': None, 'want2': None, 't': time.time(), 'auto': []}; self._rv_adv = False
        self.b_rvundo = QPushButton('↩ 復原自動 F'); self.b_rvundo.setToolTip('把連續分級自動標的 F 全部改回沒分級（最近 50 部）'); self.b_rvundo.clicked.connect(self._rv_undo_auto); b.addWidget(self.b_rvundo); self.b_rvundo.hide()
        self.area.verticalScrollBar().valueChanged.connect(self._rv_scroll)
        self.gsec.valueChanged.connect(self._gsec); self.grid.secWheel.connect(lambda d: self.gsec.stepBy(d))
        self.grid.colsChanged.connect(self._cols_from_grid)
        self.wait = QLabel(''); self.wait.setAlignment(Qt.AlignCenter); self.wait.setObjectName('muted'); self.wait.setWordWrap(True); rv.addWidget(self.wait); self.wait.hide()
        sp.addWidget(right); sp.setSizes([560, 920] if (ENG.cfg.get('list_view') or 'card') == 'card' else [380, 1100])
        # 連接
        self.b_add.clicked.connect(self.add_root); self.b_scan.clicked.connect(lambda: (ENG.scan(), self.win.msg('開始掃描影片庫（背景）')))
        self.tree.itemExpanded.connect(self._expand); self.tree.currentItemChanged.connect(lambda it, _p: self.pick_folder(it))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu); self.tree.customContextMenuRequested.connect(self._tree_menu)
        for w in (self.flt, self.sort): w.currentIndexChanged.connect(lambda _i: self.load_list())
        self.sub.toggled.connect(lambda on: (ENG.cfg.set('sub_folders', bool(on)), self.load_list()))
        self.q.textChanged.connect(lambda _t: self._qt.start(350)); self._qt = QTimer(self); self._qt.setSingleShot(True); self._qt.timeout.connect(self.load_list)
        self.lst.currentItemChanged.connect(lambda it, _p: self.pick_file(it)); self.lst.itemSelectionChanged.connect(self._sel_changed)
        self.lst.setContextMenuPolicy(Qt.CustomContextMenu); self.lst.customContextMenuRequested.connect(self._list_menu)
        for key, fn in ((Qt.Key_Delete, self.trash_many), (QKeySequence('Shift+Del'), self.del_many), (Qt.Key_Return, self._play_cur), (Qt.Key_Enter, self._play_cur)):
            sc = QShortcut(QKeySequence(key), self.lst); sc.setContext(Qt.WidgetShortcut); sc.activated.connect(fn)
        sc = QShortcut(QKeySequence('Ctrl+Z'), self); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(self.undo_last)
        self.focus_scs = []                                                     # 只有專注模式時才開（平常 PgUp／PgDn 留給清單捲動）
        for key, fn in (('PgUp', lambda: self.step_item(-1)), ('PgDown', lambda: self.step_item(1)), ('Esc', lambda: self.set_focus_mode(False))):
            sc = QShortcut(QKeySequence(key), self); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(fn); sc.setEnabled(False); self.focus_scs.append(sc)
        sc = QShortcut(QKeySequence('Ctrl+F'), self); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(lambda: (self.q.setFocus(), self.q.selectAll()))
        for k_, st_ in (('N', 1), ('Shift+N', -1)):                               # V0.1.48：跳到下一部／上一部還沒分級的
            sc = QShortcut(QKeySequence(k_), self.lst); sc.setContext(Qt.WidgetShortcut); sc.activated.connect(lambda st_=st_: self.next_ungraded(st_))
        for k, x in self.gb.items(): x.clicked.connect(lambda _c=False, k=k: self.set_grade(k))
        self.b_fav.clicked.connect(self.fav); self.b_cut.clicked.connect(self.cut); self.b_segp.clicked.connect(self.seg_preview); self.b_focus.clicked.connect(lambda: self.set_focus_mode(not self.focus_on)); self.b_clear.clicked.connect(self.grid.clear_sel)
        self.b_play.clicked.connect(lambda: self.play(self.grid.anchor_t() if self.grid.anchor is not None else 0))
        self.b_dir.clicked.connect(self.open_dir); self.b_trash.clicked.connect(self.trash); self.b_front.clicked.connect(self.front); self.b_del.clicked.connect(self.del_orig)
        self.cols.valueChanged.connect(lambda n: (ENG.cfg.set('grid_cols', int(n)), self.grid.set_cols(n), self.nxt.set_cols(n), self.nxt2.set_cols(n)))
        self.grid.play.connect(self.play); self.grid.segsChanged.connect(self._segs); self.grid.hint.connect(self.hint.setText)
        for k in ('S', 'A', 'E', 'F', '0'):
            sc = QShortcut(QKeySequence(k), self); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(lambda k=k: self.grade_many('' if k == '0' else k))
        sc = QShortcut(QKeySequence('G'), self); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(self.apply_guess)   # V0.2.86 🤖 G＝照建議分級
        sc = QShortcut(QKeySequence('Ctrl+R'), self); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(self.random_pick)   # V0.3.84 🎲
        sc = QShortcut(QKeySequence('P'), self); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(self.toggle_pub)   # V0.4.23 ✅ P＝標成／取消已發佈
        sc = QShortcut(QKeySequence('U'), self); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(self.toggle_up)   # V0.3.62 📤 U＝標成／取消已上傳
        self._en(False); self.tm = QTimer(self); self.tm.timeout.connect(self.tick); self.tm.start(2000)
        QTimer.singleShot(300, self.load_tree)

    def _gsec(self, v):
        """換顯示間隔：對齊到這部預覽圖原本間隔的倍數，畫面停在同一個時間點附近."""
        g = self.grid; sb = self.area.verticalScrollBar(); tw, th = g.tile_size()
        t_top = g.t_of((sb.value() // th) * g.cols) if g.nd else 0
        real = g.set_sec(int(v))
        try: self.nxt.set_sec(int(v)); self.nxt2.set_sec(int(v))
        except Exception: pass
        if real != int(v):
            self.gsec.blockSignals(True); self.gsec.setValue(real); self.gsec.blockSignals(False)
        ENG.cfg.set('grid_sec', int(real))
        if g.nd: _tw, th = g.tile_size(); sb.setValue(int((g.d_of(int(t_top // g.step)) // g.cols) * th))
        self.hint.setText(f'每 {real} 秒一張（共 {g.nd:,} 格；用原本每 {g.step} 秒的預覽圖，不用重做）' if g.n else f'每 {real} 秒一張')

    def _sync_gsec(self):
        """換影片時：這部的預覽圖如果不是 2 秒一張做的，間隔就照它的倍數調."""
        g = self.grid; self.gsec.blockSignals(True); self.gsec.setSingleStep(g.step); self.gsec.setMinimum(g.step); self.gsec.setValue(g.real_sec()); self.gsec.blockSignals(False)

    def _cols_from_grid(self, n):
        if self.cols.value() != n: self.cols.blockSignals(True); self.cols.setValue(n); self.cols.blockSignals(False); ENG.cfg.set('grid_cols', int(n))

    def _en(self, on):
        for x in list(self.gb.values()) + [self.b_fav, self.b_cut, self.b_del, self.b_cat, self.b_clear, self.b_play, self.b_dir, self.b_trash, self.b_front]: x.setEnabled(on)

    # ---- 資料夾樹（只把有影片的資料夾放進來；展開時才建下一層）
    def load_tree(self):
        bg(ENG.folders, self._tree)

    def _build_T(self, F, roots):
        node = lambda: {'n': 0, 'th': 0, 'gr': 0, 'kids': {}}
        T = {}
        for r in roots: T[r] = node()
        tot = [0, 0]
        for row in F:
            fd, n, th = row[:3]; gr = (row[3] if len(row) > 3 else 0) or 0; tot[0] += n; tot[1] += gr
            r = ENG.root_of(fd)
            if not r: continue
            rel = os.path.relpath(fd, r) if fd.lower() != r.lower().rstrip('\\/') else '.'
            parts = [] if rel in ('.', '') else rel.replace('/', '\\').split('\\')
            nd = T.setdefault(r, node()); nd['n'] += n; nd['th'] += th or 0; nd['gr'] += gr; path = r
            for p in parts:
                path = os.path.join(path, p); nd = nd['kids'].setdefault(p, node()); nd['n'] += n; nd['th'] += th or 0; nd['gr'] += gr; nd['path'] = path
        for r, nd in T.items(): nd['path'] = r
        return T, tot

    def _tree_scroll(self, sb):
        try: self.tree.verticalScrollBar().setValue(sb)
        except Exception: pass

    def tree_relabel(self):
        """分級改了：只更新資料夾樹的字（不重建、展開的不會收起來）。連續改很多次只做一次."""
        if not lab_cfg().get('tree_grade') or getattr(self, '_relabel_wait', False): return
        self._relabel_wait = True
        QTimer.singleShot(600, lambda: (setattr(self, '_relabel_wait', False), bg(ENG.folders, self._relabel)))

    def _relabel(self, F):
        roots = [str(r) for r in ENG.cfg.get('roots') or []]; T, tot = self._build_T(F, roots)
        def find(path):
            pl = path.lower()
            for r, nd in T.items():
                rl = r.lower().rstrip('\\/')
                if pl == rl or pl == r.lower(): return nd, True, r
                if pl.startswith(rl + '\\') or pl.startswith(rl + '/'):
                    for p in os.path.relpath(path, r).replace('/', '\\').split('\\'):
                        nd = nd['kids'].get(p)
                        if nd is None: return None
                    return nd, False, os.path.basename(path)
            return None
        def walk(it):
            pth = it.data(0, Qt.UserRole)
            if pth is None: return
            pth = str(pth)
            if pth == '': it.setText(0, f'🎬 全部影片' + (f'　{self._gr_txt(tot[1], tot[0])}' if lab_cfg().get('tree_grade') and tot[0] else ''))
            else:
                f_ = find(pth)
                if f_: nd, is_root, nm = f_; it.setText(0, self._label(nm, nd, is_root)); self.tree_nodes[id(it)] = nd
            for i in range(it.childCount()): walk(it.child(i))
        try:
            for i in range(self.tree.topLevelItemCount()): walk(self.tree.topLevelItem(i))
        except Exception: ENG.log.err('資料夾樹更新分級進度')

    def _tree(self, F):
        roots = [str(r) for r in ENG.cfg.get('roots') or []]; cur = self.folder
        T, tot = self._build_T(F, roots)
        exp = set(); sb = 0                                                     # 重建前記下哪些資料夾是展開的、捲到哪裡（掃描完重建時不會全部收起來）
        try:
            def rec(it):
                if it.isExpanded() and it.data(0, Qt.UserRole) is not None: exp.add(str(it.data(0, Qt.UserRole)).lower())
                for i in range(it.childCount()): rec(it.child(i))
            for i in range(self.tree.topLevelItemCount()): rec(self.tree.topLevelItem(i))
            sb = self.tree.verticalScrollBar().value()
        except Exception: exp = set()
        self.tree.blockSignals(True); self.tree.clear(); self.tree_nodes = {}
        top = QTreeWidgetItem([f'🎬 全部影片' + (f'　{self._gr_txt(tot[1], tot[0])}' if lab_cfg().get('tree_grade') and tot[0] else '')])
        top.setData(0, Qt.UserRole, ''); self.tree.addTopLevelItem(top)
        for r, nd in T.items():
            it = self._mk_item(r, nd, True); self.tree.addTopLevelItem(it)
        try: bg(ENG.iso_list, self._iso_tree)                                    # V0.2.24 🗄 讀不到的（隔離中）
        except Exception: ENG.log.err('資料夾樹：隔離清單')
        sel = None
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if str(it.data(0, Qt.UserRole) or '') == cur: sel = it
            elif cur and cur.lower().startswith(str(it.data(0, Qt.UserRole) or '\0').lower()) and sel is None: sel = it
        try:
            exact = [None]
            def rex(it):
                pth = it.data(0, Qt.UserRole)
                if pth is None: return
                if cur and str(pth).lower() == cur.lower(): exact[0] = it
                if str(pth).lower() in exp or (cur and str(pth) and cur.lower().startswith(str(pth).lower().rstrip('\\/') + '\\')):
                    self._expand(it); it.setExpanded(True)
                for i in range(it.childCount()): rex(it.child(i))
            if exp or cur:
                for i in range(self.tree.topLevelItemCount()): rex(self.tree.topLevelItem(i))
            if exact[0] is not None: sel = exact[0]
        except Exception: ENG.log.err('資料夾樹：恢復展開')
        if sel is not None: self.tree.setCurrentItem(sel)
        if sb:                                                                  # 樹的捲軸範圍要等版面算好才對：下一輪再設
            QTimer.singleShot(0, lambda sb=sb: self._tree_scroll(sb))
        self.tree.blockSignals(False)
        if not roots: self.h1.setText('先按左上「➕ 加入硬碟／資料夾」選你放影片的硬碟'); self.h2.setText('會掃描所有子資料夾裡的影片（不會改動任何檔案），然後在背景慢慢做每 2 秒一張的預覽圖。')
        if self.tree.currentItem() is None: self.tree.setCurrentItem(top)
        elif not getattr(self, '_tree_once', False): self.pick_folder(self.tree.currentItem())    # 第一次：選中的項目是在擋訊號時設的，清單要自己載
        self._tree_once = True

    def _iso_tree(self, I):
        """V0.2.24 資料夾樹最下面：🗄 讀不到的（拔掉的硬碟、搬走的資料夾）— 紀錄和預覽圖都留著，右鍵可以指定新位置."""
        try:
            for i in reversed(range(self.tree.topLevelItemCount())):
                if self.tree.topLevelItem(i).data(0, Qt.UserRole + 2) is not None: self.tree.takeTopLevelItem(i)
            D, G = I.get('drives') or [], I.get('folders') or []
            if not D and not G: return
            n = sum(x['n'] for x in D + G); th = sum(x['th'] for x in D + G)
            top = QTreeWidgetItem([f'🗄 讀不到的（先隔離，紀錄和預覽圖都留著）　{n:,} 部（預覽好 {th:,}）'])
            top.setData(0, Qt.UserRole + 2, {'kind': 'top'}); top.setForeground(0, QColor('#9aa4b2'))
            top.setToolTip(0, '拔掉的硬碟、搬走或刪掉的資料夾。\n接回來會自動套回去；找不到的可以右鍵「📍 指定新位置」')
            for d in D:
                nm = d['label'] or '外接硬碟'
                it = QTreeWidgetItem([f'💤 {nm}' + (f'　\\{d["sub"]}' if d['sub'] else '') + f'　{d["n"]:,} 部（預覽好 {d["th"]:,}・{core.fmt_gb(d["bytes"])}）'])
                it.setToolTip(0, f'硬碟序號 {d["serial"] or "?"}（原本在 {d["root"]}）\n接回來（任何代號）會自動套回去；也可以右鍵「📍 指定新位置」')
                it.setData(0, Qt.UserRole + 2, d); top.addChild(it)
            for g in G:
                it = QTreeWidgetItem([f'📁 {g["folder"]}　{g["n"]:,} 部（預覽好 {g["th"]:,}）— 找不到'])
                it.setToolTip(0, '這個資料夾不見了（搬走、改名或刪掉）。搬到別的地方的話：右鍵「📍 指定新位置」'); it.setData(0, Qt.UserRole + 2, g); top.addChild(it)
            self.tree.addTopLevelItem(top)
        except Exception: ENG.log.err('資料夾樹：隔離清單')

    def _iso_set(self, info, force=False, d=None):
        if d is None:
            d = QFileDialog.getExistingDirectory(self, '它現在在哪裡？選那個資料夾（整顆硬碟就選磁碟機本身）')
            if not d: return
            d = os.path.normpath(d)
        fn = (lambda: ENG.unpark(info['key'], d, force)) if info.get('kind') == 'drive' else (lambda: ENG.relocate_folder(info['folder'], d, force))
        def got(r):
            if r.get('need_force'):
                if QMessageBox.question(self, '指定新位置', r.get('message', '') + '\n\n還是要改過去嗎？') == QMessageBox.Yes: self._iso_set(info, True, d)
                return
            self.win.msg(r.get('message', '')); self.load_tree()
        bg(fn, got)

    @staticmethod
    def _gr_txt(gr, n):
        """🧪 分級進度：▰▰▰▱▱ 60%（全部分好 ✅）."""
        if gr >= n: return '✅ 全部分級好'
        pc = gr * 100 // max(1, n); k = pc // 20
        return '▰' * k + '▱' * (5 - k) + f' {pc}%'

    def _label(self, name, nd, is_root=False):
        label = (('💽 ' if is_root else '📁 ') + name + f'　{nd["n"]:,}' + (f'（預覽好 {nd["th"]:,}）' if nd['th'] < nd['n'] else ' ✔'))
        if lab_cfg().get('tree_grade') and nd['n']: label += '　' + self._gr_txt(nd.get('gr', 0), nd['n'])
        return label

    def _mk_item(self, name, nd, is_root=False):
        label = self._label(name, nd, is_root)
        it = QTreeWidgetItem([label]); it.setData(0, Qt.UserRole, nd.get('path', name)); self.tree_nodes[id(it)] = nd
        if nd['kids']: it.addChild(QTreeWidgetItem(['…']))
        return it

    def _expand(self, it):
        nd = self.tree_nodes.get(id(it))
        if not nd or it.data(0, Qt.UserRole + 1): return
        it.setData(0, Qt.UserRole + 1, True); it.takeChildren()
        for k in sorted(nd['kids'], key=lambda s: s.lower()): it.addChild(self._mk_item(k, nd['kids'][k]))

    def _tree_menu(self, pos):
        it = self.tree.itemAt(pos)
        if it is None: return
        info = it.data(0, Qt.UserRole + 2)
        if info is not None:                                                    # V0.2.24 🗄 讀不到的
            m = QMenu(self)
            if info.get('kind') in ('drive', 'folder'): m.addAction('📍 指定新位置（它現在在哪裡）…', lambda: self._iso_set(info))
            m.addAction('🔎 現在重新找一次（硬碟接回來了）', lambda: bg(lambda: ENG.vol_check(), lambda r_: (self.win.msg('；'.join(r_) if r_ else '沒有找到接回來的硬碟'), self.load_tree())))
            m.exec(self.tree.viewport().mapToGlobal(pos)); m.deleteLater(); return
        d = str(it.data(0, Qt.UserRole) or '')
        if not d: return
        m = QMenu(self); is_root = any(core.path_key(d) == core.path_key(r) for r in ENG.cfg.get('roots') or [])
        m.addAction('📂 打開這個資料夾', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(d)))
        if hasattr(self.win, 'explore'): m.addAction('🗺 看大小／能省多少（檔案總覽）', lambda: (self.win.explore.go(d.rstrip('\\/')), self.win.nav.setCurrentRow(74)))   # V0.6.22
        if hasattr(self.win, 'conv'): m.addAction('🔁 轉檔這個資料夾…', lambda: self.win.explore.menu_for({'path': d.rstrip('\\/'), 'name': Path(d).name or d}, None))
        m.addAction('⚡ 這個資料夾的預覽圖先做', lambda: bg(lambda: ENG.folder_front(d), lambda n_: self.win.msg(f'{Path(d).name or d}：{n_} 部排到最前面做預覽圖')))
        if lab_cfg().get('folder_move') and len(d) > 3: m.addAction('🚚 搬到別顆硬碟…（紀錄跟著過去）', lambda: self._folder_move(d))   # V0.2.34
        am = m.addMenu('📦 歸檔這個資料夾（含子資料夾）')
        C_ = ENG.grade_counts(d)
        for g_ in ('S', 'A', 'E', 'F'):
            n_, sz_ = C_.get(g_, (0, 0)); a_ = am.addAction(f'{g_}（{GN[g_]}）{n_:,} 部・{fmt_b(sz_)}', lambda g_=g_: self.archive_grade(g_, d)); a_.setEnabled(n_ > 0)
        m.addSeparator()
        if not is_root:
            m.addAction('🚫 排除這個資料夾（含子資料夾）', lambda: exclude_folder(self.win, d))
            m.addAction(f'🚫 排除所有叫「{Path(d).name}」的資料夾', lambda: exclude_name(self.win, Path(d).name))
        m.exec(self.tree.viewport().mapToGlobal(pos)); m.deleteLater()

    def pick_folder(self, it):
        if it is None or it.data(0, Qt.UserRole + 2) is not None: return
        self.folder = str(it.data(0, Qt.UserRole) or ''); ENG.th_focus = self.folder; self.load_list()
        try: ENG.recent_push(self.folder)                                       # V0.2.56 🕘
        except Exception: pass

    def add_root(self):
        d = QFileDialog.getExistingDirectory(self, '選要整理的硬碟或資料夾')
        if not d: return
        d = os.path.normpath(d); R = [str(x) for x in ENG.cfg.get('roots') or []]
        if any(d.lower() == r.lower() for r in R): self.win.msg('已經在影片庫裡'); return
        R.append(d); ENG.cfg.set('roots', R); ok = ENG.scan([d])
        self.win.msg(f'已加入 {d}，' + ('開始掃描（背景）' if ok else '目前正在掃描別的，掃完請按「🔄 重新掃描」')); QTimer.singleShot(1500, self.load_tree)

    # ---- 清單
    def cur_view(self):
        return {'folder': self.folder, 'flt': self.flt.currentData() or 'all', 'q': self.q.text().strip(), 'sort': self.sort.currentData() or 'name', 'sub': self.sub.isChecked(), 'dur': getattr(self, 'dur_k', ''), 'res': getattr(self, 'res_k', '')}

    def views_menu(self):
        try:
            m = QMenu(self); V = ENG.views()
            for v in V:
                fi_ = self.flt.findData(v.get('flt')); d_ = '・'.join(x for x in (Path(v.get('folder') or '').name or '全部', (self.flt.itemText(fi_) if fi_ >= 0 else str(v.get('flt'))) if v.get('flt') != 'all' else '', ('「' + v['q'] + '」') if v.get('q') else '', ('⏱' + dict(core.DUR_NAMES).get(v.get('dur'), '')) if v.get('dur') else '') if x)
                m.addAction(f'⭐ {v["name"]}　（{d_}）', lambda v=v: self.use_view(v))
            if not V: a_ = m.addAction('（還沒存過）'); a_.setEnabled(False)
            m.addSeparator(); m.addAction('＋ 把目前的篩選存起來…', self._view_add)
            if V:
                sm = m.addMenu('🗑 刪除'); [sm.addAction(v['name'], lambda n=v['name']: (ENG.view_del(n), self.win.msg(f'已刪除「{n}」'))) for v in V]
            m.exec(self.b_view.mapToGlobal(self.b_view.rect().bottomLeft())); m.deleteLater()
        except Exception: ENG.log.err('常用篩選選單')

    def _view_add(self):
        v = self.cur_view(); dn = Path(v['folder']).name if v['folder'] else '全部'
        n, ok = QInputDialog.getText(self, '⭐ 存成常用篩選', '名字：', text=dn + (f' {v["q"]}' if v['q'] else '') + (f' {v["flt"]}' if v['flt'] != 'all' else ''))
        if ok and str(n).strip() and ENG.view_save(n, v): self.win.msg(f'⭐ 已存「{str(n).strip()}」（手機也看得到）')

    def bm_all_dlg(self):
        """V0.4.16 🔖 所有書籤：點兩下＝打開那部、從那個時間開始播."""
        try:
            d = QDialog(self); d.setWindowTitle('🔖 所有時間書籤'); d.resize(720, 560); v = QVBoxLayout(d); q = QLineEdit(); q.setPlaceholderText('找檔名或書籤說明'); v.addWidget(q)
            lw = QListWidget(); v.addWidget(lw, 1); n = QLabel('讀取中…'); n.setObjectName('muted'); v.addWidget(n); D = []
            def show(*_a):
                k_ = q.text().strip().lower(); lw.clear()
                for x in D:
                    if k_ and k_ not in (x['name'] + x['note']).lower(): continue
                    it = QListWidgetItem(f"{x['grade'] or '・'}　{fmt_t(x['t'])}　{x['note'] or '（沒寫說明）'}　—　{x['name']}"); it.setData(Qt.UserRole, (x['id'], x['t'])); lw.addItem(it)
                n.setText(f'{lw.count():,} 個書籤（點兩下＝打開那部、從那裡開始播；右鍵＝✂ 剪書籤前後一段；播放時按 B 加書籤）')
            def got(R): D[:] = R; show()
            def go(it):
                fid, t = it.data(Qt.UserRole); d.accept(); self.goto_file(fid); QTimer.singleShot(400, lambda: self.play(t))
            def clip_(it):                                                      # V0.4.17 右鍵＝剪這個書籤前 5 秒～後 10 秒
                if it is None: return
                fid, t = it.data(Qt.UserRole); m = QMenu(d)
                for a_, b_ in ((5, 10), (3, 7), (10, 20), (15, 45)):
                    m.addAction(f'✂ 剪 前 {a_} 秒～後 {b_} 秒（{a_ + b_} 秒）', lambda a_=a_, b_=b_: self.win.msg((ENG.bm_clip(fid, t, a_, b_) or {}).get('message') or '✂ 排進初剪了'))
                m.exec(QCursor.pos())
            lw.setContextMenuPolicy(Qt.CustomContextMenu); lw.customContextMenuRequested.connect(lambda p_: clip_(lw.itemAt(p_)))
            q.textChanged.connect(show); lw.itemDoubleClicked.connect(go); bg(ENG.bm_all, got); d.exec(); d.deleteLater()
        except Exception: ENG.log.err('全部書籤')

    def random_pick(self):
        """V0.3.84 🎲 隨便抽一部還沒分級的打開."""
        if not lab_cfg().get('random_pick'): return
        def got(L):
            if not L: self.win.msg('🎲 這裡沒有還沒分級的了 🎉'); return
            self.goto_file(L[0]); self.win.msg('🎲 隨便抽了一部')
        f_ = self.folder; bg(lambda: ENG.random_ungraded(f_), got)

    def syn_menu(self):
        """V0.3.83 🔎＋ 搜尋條件選單（電腦版，跟手機一樣）."""
        m = QMenu(self)
        TK = [('g:S', '只要 S'), ('g:SA', 'S 和 A'), ('g:none', '還沒分級'), ('沒上傳', '還沒上傳'), ('已上傳', '已經上傳'), ('★', '收藏'), ('沒看過', '沒看過'), ('>10m', '長度超過 10 分'), ('<1m', '短於 1 分'),
              ('>2gb', '大於 2 GB'), ('4k', '4K'), ('1080p', '1080p'), ('hevc', 'HEVC 編碼'), ('note:', '備註有…（後面打字）'), ('-', '檔名不要有…（後面打字）')]
        def add(t):
            v_ = self.q.text().strip(); self.q.setText((v_ + ' ' if v_ else '') + t); self.q.setFocus()
            if not (t.endswith(':') or t == '-'): self.load_list()
        for t, n in TK: m.addAction(f'{t}　{n}', lambda t=t: add(t))
        m.addSeparator(); m.addAction('✕ 清掉搜尋', lambda: (self.q.clear(), self.load_list()))
        m.exec(QCursor.pos())

    def use_view(self, v):
        """叫出常用篩選：資料夾、分級、搜尋、排序、子資料夾、時長一次套上."""
        try:
            for w_ in (self.flt, self.sort, self.sub, self.q): w_.blockSignals(True)
            i = self.flt.findData(v.get('flt') or 'all'); self.flt.setCurrentIndex(i if i >= 0 else 0)
            i = self.sort.findData(v.get('sort') or 'name'); self.sort.setCurrentIndex(i if i >= 0 else 0)
            self.sub.setChecked(bool(v.get('sub', True))); self.q.setText(v.get('q') or '')
        finally:
            for w_ in (self.flt, self.sort, self.sub, self.q): w_.blockSignals(False)
        self.dur_k = v.get('dur') or ''; self.res_k = v.get('res') or ''
        for k_, b_ in getattr(self, 'dur_b', {}).items(): b_.setChecked(k_ == self.dur_k)
        for k_, b_ in getattr(self, 'res_b', {}).items(): b_.setChecked(k_ == self.res_k)
        self._sel_folder(v.get('folder') or '')
        self.load_list(); self.win.msg(f'⭐ {v.get("name", "")}')

    def _q_push(self):
        try:
            if not lab_cfg().get('search_hist'): return
            ENG.search_push(self.q.text()); self.q_hm.setStringList(ENG.search_hist())
        except Exception: pass

    def recent_menu(self):
        try:
            m = QMenu(self); R = ENG.recent_list()
            for f in R: m.addAction(f'📁 {Path(f).name or f}　（{f}）', lambda f=f: (self._sel_folder(f), self.load_list()))
            if not R: a_ = m.addAction('（還沒有）'); a_.setEnabled(False)
            m.exec(self.b_rec.mapToGlobal(self.b_rec.rect().bottomLeft())); m.deleteLater()
        except Exception: ENG.log.err('最近資料夾')

    def _sel_folder(self, folder):
        """切到這個資料夾（左邊樹也跟著選到，不觸發重新讀取）."""
        self.folder = folder or ''; ENG.th_focus = self.folder
        try:
            def walk(it):
                if str(it.data(0, Qt.UserRole) or '') == self.folder: return it
                for j in range(it.childCount()):
                    r = walk(it.child(j))
                    if r is not None: return r
            for j in range(self.tree.topLevelItemCount()):
                r = walk(self.tree.topLevelItem(j))
                if r is not None: self.tree.blockSignals(True); self.tree.setCurrentItem(r); self.tree.blockSignals(False); break
        except Exception: pass

    def export_csv(self):
        rows = list(getattr(self, 'rows', None) or [])
        if not rows: self.win.msg('清單是空的'); return
        p, _ = QFileDialog.getSaveFileName(self, '清單匯出 CSV', str(Path.home() / f'VideoSift_清單_{time.strftime("%Y%m%d_%H%M")}.csv'), 'CSV (*.csv)')
        if not p: return
        try: Path(p).write_text(ENG.list_csv(rows), encoding='utf-8'); self.win.msg(f'📤 已匯出 {len(rows):,} 部 → {p}')
        except Exception as e: ENG.log.err('清單匯出 CSV'); self.win.msg(f'匯出失敗：{e}')

    def set_res(self, k):
        self.res_k = k
        for k_, b_ in getattr(self, 'res_b', {}).items(): b_.setChecked(k_ == k)
        self.load_list()

    def set_dur(self, k):
        self.dur_k = k
        for k_, b_ in getattr(self, 'dur_b', {}).items(): b_.setChecked(k_ == k)
        self.load_list()

    def load_list(self):
        fd, sub, srt, fl, q = self.folder, self.sub.isChecked(), self.sort.currentData(), self.flt.currentData(), self.q.text().strip()
        du = getattr(self, 'dur_k', '') if lab_cfg().get('dur_chips') else ''; rs = getattr(self, 'res_k', '') if lab_cfg().get('res_chips') else ''
        self._lg = getattr(self, '_lg', 0) + 1; g = self._lg
        bg(lambda: (ENG.list_files(fd, sub, srt, fl, q, du, rs), ENG.hidden_count(fd, sub) if not str(fl).startswith('ext:') else []), lambda r: self._list(r[0], r[1]) if g == self._lg else None)
        self.load_chips()

    def load_chips(self):
        fd, sub = self.folder, self.sub.isChecked()
        bg(lambda: ENG.grade_summary(fd, sub), self._chips_got)

    def _chips_got(self, C):
        names = {'all': '全部', 'ready': '✅ 可以審', 'nograde': '未分級', 'S': 'S 無條件保存', 'A': 'A 保存', 'E': 'E 觀察', 'F': 'F 刪除'}; cur = self.flt.currentData()
        try: self.b_purge.setVisible(cur == 'F')                                 # V0.2.01 選到 F 才出現「清空待刪」
        except Exception: pass
        for k, c in self.chips.items():
            bb_ = (C.get('bytes') or {}).get(k)
            c.setText(f'{names[k]} {C.get(k, 0):,}' + (f'\n{core.fmt_gb(bb_)}' if bb_ is not None else '')); c.setChecked(k == cur)      # V0.2.04 下一行＝總大小
        tot = C.get('all', 0); done = tot - C.get('nograde', 0)
        self.gprog.setMaximum(max(1, tot)); self.gprog.setValue(done); self.gprog.setToolTip(f'這個資料夾裡已經分級 {done:,} 部，還有 {C.get("nograde", 0):,} 部沒分級')

    def _chip(self, k):
        i = self.flt.findData(k)
        if i >= 0: self.flt.setCurrentIndex(i)
        for kk, c in self.chips.items(): c.setChecked(kk == k)

    def _row_text(self, r):
        st = {0: '⏳', 1: '⚙', 2: '✔', 3: '✖', 4: '🔇'}.get(int(r['th_state'] or 0), '')
        tags = ('⭐' if r['fav'] else '') + (f'[{r["grade"]}]' if r['grade'] else '') + ((lambda pn: f'[{"-" if pn else "√"}剪輯{int(r["cut_n"] or 0) + pn}]' if (pn or r['cut_n']) else '')((getattr(self, 'cut_pend', None) or {}).get(r['id'], 0))) + ('' if r['viewed'] else '•')
        return f'{st} {tags} {r["name"]}\n      {fmt_t(r["dur"]) if r["dur"] else "—"} · {r["w"]}×{r["h"]} · {fmt_b(r["size"])} · {r["ext"][1:]}'

    def _list(self, rows, hidden=None):
        """清單：先放前 1500 張，其餘每次 2500 張在背景一批一批補（上萬部也不會卡畫面）."""
        keep = self.cur['id'] if self.cur else None; self.rows = rows; self._fill_gen = getattr(self, '_fill_gen', 0) + 1
        tot = sum(r['size'] or 0 for r in rows); dur = sum(r['dur'] or 0 for r in rows); ok = sum(1 for r in rows if r['th_state'] == 2)
        self._cnt_base = (f'{len(rows):,} 部 · {fmt_b(tot)} · {fmt_t(dur)} · 預覽圖好了 {ok:,}' + ('（只列前 20000 部）' if len(rows) >= 20000 else '') +
                          '　⏳ 排隊 ⚙ 做中 ✔ 好了 ✖ 失敗 🔇 沒畫面　• 沒看過'
                          + (('\n🚫 沒列出來的格式：' + '、'.join(f'{e[1:]} {n:,}' for e, n in hidden[:8]) + (' …' if len(hidden) > 8 else '') + '（設定 → 🗂 檔案總管列出的格式 可以改；轉檔頁照樣看得到）') if hidden else ''))
        self.lst.blockSignals(True); self.lst.clear(); self.lst.blockSignals(False); self.item_of = {}; self.row_of = {r['id']: r for r in rows}
        self._fill = {'rows': rows, 'i': 0, 'keep': keep, 'want': getattr(self, '_want_id', None), 'gen': self._fill_gen, 't0': time.time()}
        self._fill_step()

    def _fill_step(self):
        F = getattr(self, '_fill', None)
        if not F or F['gen'] != self._fill_gen: return
        rows = F['rows']; i = F['i']; j = min(len(rows), i + (1500 if i == 0 else 2500)); sel = None
        self.lst.blockSignals(True); self.lst.setUpdatesEnabled(False)
        try:
            for r in rows[i:j]:
                it = QListWidgetItem(self._row_text(r)); it.setData(Qt.UserRole, r['id']); it.setToolTip(r['path'] + (f"\n✎ {r['note']}" if r.get('note') else '')); self.item_of[r['id']] = it
                if r['grade'] in GC: it.setForeground(QColor(GC[r['grade']]))
                self.lst.addItem(it)
                if r['id'] == F['keep'] or (F['keep'] is None and r['id'] == F['want']): sel = it
        finally:
            self.lst.setUpdatesEnabled(True); self.lst.blockSignals(False)
        if sel is not None: self.lst.setCurrentItem(sel); self._want_id = None
        F['i'] = j
        if j < len(rows):
            self.cnt.setText(f'{self._cnt_base}　（載入中 {j:,}／{len(rows):,}）'); QTimer.singleShot(0, self._fill_step)
        else:
            self._fill = None
            self.cnt.setText(self._cnt_base)
            if len(rows) > 1500: ENG.log.w(f'清單載入 {len(rows):,} 部，花 {time.time() - F["t0"]:.1f} 秒（分批，畫面不卡）')
            self._sel_changed()

    def pick_file(self, it):
        if it is None: return
        fid = int(it.data(Qt.UserRole)); bg(lambda: (ENG.file(fid), None), lambda x: self.show_file(x[0]))

    def show_file(self, r, keep_sel=True):
        if not r: return
        same = self.cur and self.cur['id'] == r['id']
        if not same and not self._rv_adv: self.rv['n'] = 1; self._rv_clear()       # V0.2.09 手動換部（點清單、上一則／下一則、分級後跳）＝新的一輪 10 部
        if not same: self.rv['t'] = time.time()
        self.cur = r; self._en(True)
        self.h1.setText(('⭐ ' if r['fav'] else '') + r['name'])
        if not same: ENG.last_file_set(r['id'])                                   # V0.3.38 ⏯
        try:
            G_ = ENG.grade_guess(r['id']) if lab_cfg().get('guess') and not r.get('grade') else None
            self.l_guess.setVisible(bool(G_))
            if G_: self.l_guess.setText(f"🤖 猜 <b style='color:{GC[G_['g']]}'>{G_['g']}</b>（G）"); self.l_guess.setToolTip(G_['why'] + '（只是建議；按 G＝照建議分級，或按 S／A／E／F 自己決定）')
        except Exception: pass
        self.h2.setText(f"{r['folder']}\n{fmt_t(r['dur'])} · {r['w']}×{r['h']} · {r['vcodec']} {round(r['fps'] or 0, 2)}fps · 聲音 {r['acodecs'] or '無'} · {fmt_b(r['size'])}"
                        + (f" · 已初剪 {r['cut_n']} 段" if r['cut_n'] else '') + (f" · 😴 靜止 {round(float(r['still']) * 100)}%" if (r.get('still') or -1) >= 0 and lab_cfg().get('still_scan') else '') + (f" · 📤 {time.strftime('%m/%d', time.localtime(float(r['up_t'])))} 傳過" if float(r.get('up_t') or 0) > 0 and lab_cfg().get('copy_to') else '') + (f" · ✅ {time.strftime('%m/%d', time.localtime(float(r['pub_t'])))} 發佈" if float(r.get('pub_t') or 0) > 0 and lab_cfg().get('copy_to') else '') + (f"\n✎ {r['note']}" if r.get('note') else '')
                        + (('\n👤 ' + '、'.join(f'{nm}（{n}）' for _p, nm, n in ppl)) if (ppl := (ENG.faces.people_of(r['id']) if getattr(ENG, 'faces', None) else [])) else ''))
        for k, x in self.gb.items(): x.setChecked((r['grade'] or '') == k)
        self.b_fav.setText('⭐ 已收藏' if r['fav'] else '⭐ 收藏'); self.b_del.setVisible(bool(r['cut_n']))
        if not r['viewed']:
            fid = r['id']; bg(lambda: ENG.set_flag(fid, viewed=time.time()))
        st = int(r['th_state'] or 0)
        if st == 2:
            self.wait.hide(); self.b_front.hide()
            if not (same and keep_sel and self.grid.fid == r['id'] and self.grid.n):
                bg(lambda: ENG.sheets(r), lambda S: (self.grid.set_video(r, S), self._sync_gsec(), self.area.verticalScrollBar().setValue(0), QTimer.singleShot(400, self._rv_check)) if self.cur and self.cur['id'] == r['id'] else None)
        else:
            self.grid.set_video(None, []); self.wait.show(); self.b_front.setVisible(st in (0, 3))
            J = ENG.th_active.get(r['id'])
            self.wait.setText({0: '預覽圖排隊中（背景照順序做）。按「⚡ 先做這部的預覽圖」可以插到最前面；也可以直接按 ▶ 播放',
                               1: f'正在做預覽圖… {J["pct"] if J else 0}%', 3: '✖ 預覽圖做不出來：' + str(r['th_err'] or '')[:300] + '\n可以按「⚡ 先做這部的預覽圖」再試一次，或直接 ▶ 播放',
                               4: '🔇 這個檔沒有畫面（只有聲音）'}.get(st, ''))

    # ---- V0.2.09 📜 連續分級：滾到底接下一部；上一部完全滾出畫面又沒分級 → 自動 F；一輪 10 部
    RV_N = 0                                                                    # V0.2.15 不限部數（以前一輪 10 部）
    RV_MIN_SEC = 0.0                                                            # 防誤觸：一部在畫面上不到 1 秒就滾過去（滾太快）＝不算看過，不標 F（V0.2.21 使用者取消：0＝不管看多久都算）

    def _rv_undo_auto(self):
        L = list(self.rv.get('auto') or [])
        if not L: return
        ids = [i for i in L if (self.row_of.get(i) or {}).get('grade') == 'F']
        for i in ids: self._upd_row(i, grade='')
        if self.cur and self.cur['id'] in ids:
            self.cur['grade'] = ''
            for kk, x in self.gb.items(): x.setChecked(kk == '')
        bg(lambda: ENG.set_flags(ids, grade=''), lambda _r: self.load_chips()); self.rv['auto'] = []; self.b_rvundo.hide()
        self.win.msg(f'↩ 自動標的 F 改回沒分級：{len(ids)} 部'); ENG.log.w(f'📜 連續分級：復原自動 F {len(ids)} 部')

    def _rv_clear(self):
        self.rv['row'] = None; self.rv['want'] = None; self.rv['row2'] = None; self.rv['want2'] = None
        try: self.nxt.set_video(None, []); self.nxt.hide(); self.nxt2.set_video(None, []); self.nxt2.hide()
        except Exception: pass
        self.area.sep_on = False; self.area.fit()

    def _rv_next_row(self, after=None):
        """清單裡目前這部（或第 after 列）之後，第一部「沒分級、預覽圖好了」的 → (第幾列, 那一筆)."""
        n = self.lst.count(); r0 = self.lst.currentRow() if after is None else int(after); R = getattr(self, 'row_of', {})
        for r in range(r0 + 1, n):
            it = self.lst.item(r)
            if it is None: continue
            x = R.get(it.data(Qt.UserRole)) or {}
            if not (x.get('grade') or '') and int(x.get('th_state') or 0) == 2: return r, x
        return -1, None

    def _rv_scroll(self, v):
        if not self.b_rv.isChecked() or not self.cur or not self.grid.n or self._rv_adv: return
        A = self.area; gh = self.grid.height(); vh = A.viewport().height(); _tw, th = self.grid.tile_size()
        if v + vh >= gh - vh and self.rv['row'] is None and self.rv['want'] is None:                  # V0.2.20 快滾到這部最下面（剩一個畫面）就先接下一部
            if self.RV_N and self.rv['n'] >= self.RV_N:                         # V0.2.15 使用者取消 10 部上限（RV_N＝0）
                A.sep_on = True; A.sep.setText(f'⏸ 這一輪 {self.RV_N} 部看完了：按「下一則 ▶」或分級，開始下一輪'); A.fit(); return
            ri, x = self._rv_next_row()
            if x is None: A.sep_on = True; A.sep.setText('— 清單最後一部了 —'); A.fit(); return
            self.rv['want'] = x['id']; fid = x['id']
            def got(S, x=x, fid=fid, ri=ri):
                if self.rv.get('want') != fid or not self.cur: return
                self.rv['row'] = (ri, x); self.rv['want'] = None
                A.sep_on = True; A.sep.setText(f'▼ 下一部（連續第 {self.rv["n"] + 1} 部）：{x.get("name", "")}')
                self.nxt.set_video(x, S); self.nxt.relayout(A.viewport().width()); self.nxt.show(); A.fit(); self._rv_load2()
            bg(lambda x=x: ENG.sheets(x), got); return
        if self.rv['row'] is not None and v >= gh + A.sep_h():                   # 這部已經完全滾出畫面 → 換下一部
            self._rv_advance(min(v - gh - A.sep_h(), max(0, self.nxt.height() - th * 2)))   # 不要一換過來就已經滾出去（連環換部）

    def _rv_load2(self):
        """V0.2.20 一次接兩部：下一部接好之後，再把下下一部也接上來（滾起來比較順）."""
        if self.rv.get('row') is None or self.rv.get('row2') is not None or self.rv.get('want2') is not None: return
        ri2, x2 = self._rv_next_row(after=self.rv['row'][0])
        if x2 is None: return
        self.rv['want2'] = x2['id']; fid2 = x2['id']; A = self.area
        def got2(S, x2=x2, fid2=fid2, ri2=ri2):
            if self.rv.get('want2') != fid2 or self.rv.get('row') is None: return
            self.rv['row2'] = (ri2, x2); self.rv['want2'] = None
            A.sep2.setText(f'▼ 再下一部（連續第 {self.rv["n"] + 2} 部）：{x2.get("name", "")}')
            self.nxt2.set_video(x2, S); self.nxt2.relayout(A.viewport().width()); self.nxt2.show(); A.fit()
        bg(lambda x2=x2: ENG.sheets(x2), got2)

    def _rv_check(self):
        """V0.2.19 影片很短、格子一個畫面就放得下（沒有捲軸、不會有捲動事件）→ 直接檢查一次，把下一部接上來."""
        try:
            if self.isVisible() and self.cur and self.grid.n and self.rv['row'] is None and self.rv['want'] is None: self._rv_scroll(self.area.verticalScrollBar().value())
        except Exception: pass

    def _rv_advance(self, off):
        prev = self.cur; ri, x = self.rv['row']; S = list(self.nxt.sheets)
        stay = time.time() - float(self.rv.get('t') or 0)
        segs = self.grid.seg_times() if (prev and self.grid.fid == prev.get('id')) else []
        if prev and segs:                                                        # V0.2.15 有選片段就滾到下一部 → 全部片段合併輸出成 1 個檔，標 F（有自己按分級的照你按的）
            pid = prev['id']; pname = prev.get('name', ''); g0 = prev.get('grade') or ''
            def cut_it(pid=pid, segs=list(segs)):
                r_ = ENG.cut_add(pid, segs, merge=True)
                if r_.get('ok') and not g0: ENG.set_flag(pid, grade='F')
                return r_
            def cut_done(r_, pid=pid, pname=pname, n=len(segs)):
                if r_.get('ok'): self.win.msg(f'📜 {pname}：選的 {n} 段合併輸出成 1 個初剪檔（排隊中）' + ('，標 F' if not g0 else f'，分級照你按的 {g0}'), 8000); self.load_chips()
                else: self.win.msg(f'📜 {pname}：自動輸出初剪失敗：{r_.get("message", "")}', 10000)
            if not g0: prev['grade'] = 'F'; self._upd_row(pid, grade='F'); self.undo.append(('grade', [(pid, '')])); self.undo = self.undo[-30:]
            self.grid.clear_sel(); bg(cut_it, cut_done)
            ENG.log.w(f'📜 連續分級：{pname} 有選 {len(segs)} 段就滾到下一部 → 合併輸出 1 個初剪檔' + ('、標 F' if not g0 else ''))
        elif prev and not (prev.get('grade') or '') and stay < self.RV_MIN_SEC:    # 滾太快：可能是誤觸，不標 F
            self.win.msg(f'📜 {prev.get("name", "")} 只看了 {stay:.1f} 秒就滾過去（太快，可能是誤觸）→ 沒標 F，留著沒分級')
        elif prev and not (prev.get('grade') or ''):                             # 沒分級就滾過去了 → F
            pid = prev['id']; self.undo.append(('grade', [(pid, '')])); self.undo = self.undo[-30:]; prev['grade'] = 'F'; self._upd_row(pid, grade='F')
            self.rv['auto'] = (self.rv.get('auto') or [])[-49:] + [pid]; self.b_rvundo.setText(f'↩ 復原自動 F（{len(self.rv["auto"])}）'); self.b_rvundo.show()
            bg(lambda: ENG.set_flag(pid, grade='F'), lambda _r: self.load_chips()); self.win.msg(f'📜 {prev.get("name", "")} 滾過去沒分級 → 自動 F（Ctrl+Z 或「↩ 復原自動 F」可以改回）')
            ENG.log.w(f'📜 連續分級：{prev.get("name", "")} 沒分級就滾過去（看了 {stay:.0f} 秒）→ 自動標 F')
        self._rv_adv = True
        try:
            self.rv['row'] = None; self.rv['n'] += 1; r2 = self.rv.get('row2'); S2 = list(self.nxt2.sheets)
            self.rv['row2'] = None; self.rv['want2'] = None; self.nxt2.set_video(None, []); self.nxt2.hide()
            self.nxt.set_video(None, []); self.nxt.hide(); self.area.sep_on = False
            self.grid.set_video(x, S); self._sync_gsec()
            if r2 is not None:                                                   # V0.2.20 下下一部已經接好：直接變成下一部，不用等
                self.nxt.set_video(r2[1], S2); self.nxt.relayout(self.area.viewport().width()); self.nxt.show(); self.rv['row'] = r2
                self.area.sep_on = True; self.area.sep.setText(f'▼ 下一部（連續第 {self.rv["n"] + 1} 部）：{r2[1].get("name", "")}')
            self.area.fit(); self.area.verticalScrollBar().setValue(max(0, int(off)))
            self.lst.blockSignals(True)
            try: self.lst.clearSelection(); self.lst.setCurrentRow(ri); self.lst.scrollToItem(self.lst.item(ri))
            finally: self.lst.blockSignals(False)
            self._sel_changed(); self._focus_pos(); self.cur = x; self.rv['t'] = time.time(); QTimer.singleShot(400, self._rv_check)
        finally: self._rv_adv = False
        fid = x['id']
        def done(t):
            if self.cur and self.cur['id'] == fid and t and t[0]:
                self._rv_adv = True
                try: self.show_file(t[0])
                finally: self._rv_adv = False
        bg(lambda: (ENG.file(fid), None), done)
        if self.rv.get('row') is not None: QTimer.singleShot(200, self._rv_load2)

    def tick(self):
        self._tk = getattr(self, '_tk', 0) + 1
        self._rv_check()
        if self._tk % 3 == 0 and self.isVisible(): self._refresh_states()
        t1 = ENG.scan_st['t1']
        if t1 != getattr(self, '_scan_t1', 0):                                  # 掃描做完：資料夾樹、清單重讀
            self._scan_t1 = t1
            if t1: self.load_tree(); self.load_list()
        if not self.isVisible() or not self.cur: return
        if int(self.cur.get('th_state') or 0) != 2:
            fid = self.cur['id']; bg(lambda: ENG.file(fid), lambda r: self.show_file(r) if r and self.cur and self.cur['id'] == r['id'] else None)
        elif ENG.cut_q or ENG.cut_cur or getattr(self, '_cut_watch', 0) > time.time():  # 初剪做完：清單顯示「已剪輯」、出現刪除原檔
            if ENG.cut_q or ENG.cut_cur: self._cut_watch = time.time() + 6
            fid = self.cur['id']; bg(lambda: ENG.file(fid), self._cut_refresh)

    def _cut_refresh(self, r):
        if not r or not self.cur or self.cur['id'] != r['id'] or r['cut_n'] == self.cur.get('cut_n'): return
        self.show_file(r); self._upd_row(r['id'], cut_n=r['cut_n'])

    def _segs(self):
        n = len(self.grid.seg_times()); tot = sum(b - a for a, b in self.grid.seg_times())
        self.b_cut.setText(f'✂ 輸出初剪（{n} 段' + (f' · {fmt_t(tot)}' if n else '') + '）')

    # ---- 動作
    def toggle_pub(self):
        """V0.4.23 ✅ 按 P＝選到的標成「已發佈」（都已發佈就取消）."""
        if not lab_cfg().get('copy_to'): return
        R = self.sel_rows() or ([self.cur] if self.cur else [])
        if not R: return
        on_ = not all(float(r.get('pub_t') or 0) > 0 for r in R); n_, m_ = ENG.pub_mark([r['id'] for r in R], on_)
        for r in R: self._upd_row(r['id'], pub_t=time.time() if on_ else 0)
        self.win.msg(m_)

    def toggle_up(self):
        """V0.3.62 📤 按 U＝選到的標成「已上傳」（都已上傳就取消）."""
        if not lab_cfg().get('copy_to'): return
        R = self.sel_rows() or ([self.cur] if self.cur else [])
        if not R: return
        on_ = not all(float(r.get('up_t') or 0) > 0 for r in R); n_, m_ = ENG.up_mark([r['id'] for r in R], on_)
        for r in R: self._upd_row(r['id'], up_t=time.time() if on_ else 0)
        if self.cur and any(r['id'] == self.cur['id'] for r in R): self.cur['up_t'] = time.time() if on_ else 0
        self.win.msg(m_)

    def apply_guess(self):
        """V0.2.86 🤖 按 G＝照「分級建議」分級（沒有建議就不動）."""
        if not lab_cfg().get('guess') or not self.cur: return
        G_ = ENG.grade_guess(self.cur['id'])
        if not G_: self.win.msg('🤖 這部沒有建議（資料不夠）'); return
        self.set_grade(G_['g']); self.win.msg(f"🤖 照建議分成 {G_['g']}（{G_['why']}）")

    def set_grade(self, k):
        if not self.cur: return
        fid = self.cur['id']; self.undo.append(('grade', [(fid, self.cur.get('grade') or '')])); self.undo = self.undo[-30:]; self.cur['grade'] = k
        for kk, x in self.gb.items(): x.setChecked(kk == k)
        bg(lambda: ENG.set_flag(fid, grade=k), lambda _r: (self._upd_row(fid, grade=k), self.load_chips())); self.win.msg(f'{self.cur["name"]} → {k + "（" + GN[k] + "）" if k else "未分級"}')
        if k and (ENG.cfg.get('lab') or {}).get('auto_next'): QTimer.singleShot(120, lambda: self.next_ungraded(1))      # V0.2.08 直接跳下一部「還沒分級」的


    def refresh_people_filter(self):
        """👤 篩選選單後面加「取了名字的人」."""
        if getattr(ENG, 'faces', None) is None: return
        def done(P):
            cur = self.flt.currentData(); self.flt.blockSignals(True)
            for i in range(self.flt.count() - 1, -1, -1):
                if str(self.flt.itemData(i) or '').startswith('person:'): self.flt.removeItem(i)
            for p in P: self.flt.addItem(f'👤 {p["name"]}（{p["n_files"]}）', f'person:{p["id"]}')
            i = self.flt.findData(cur); self.flt.setCurrentIndex(max(0, i)); self.flt.blockSignals(False)
        bg(lambda: [p for p in ENG.faces.persons() if p['name']], done)

    def show_person(self, pid, name):
        """檔案總管只看這個人的影片（全部資料夾）."""
        k = f'person:{pid}'; i = self.flt.findData(k)
        if i < 0: self.flt.addItem(f'👤 {name}', k); i = self.flt.findData(k)
        self.folder = ''; self.tree.setCurrentItem(self.tree.topLevelItem(0)) if self.tree.topLevelItemCount() else None; self.flt.setCurrentIndex(i)

    def next_ungraded(self, step=1):
        """N＝下一部還沒分級的、Shift+N＝上一部（到底會從另一頭繼續找）."""
        n = self.lst.count(); R = getattr(self, 'row_of', {})
        if not n: return
        r0 = self.lst.currentRow()
        for i in range(1, n + 1):
            r = (r0 + step * i) % n; it = self.lst.item(r)
            if it is None: continue
            x = R.get(it.data(Qt.UserRole)) or {}
            if not (x.get('grade') or ''):
                self.lst.clearSelection(); self.lst.setCurrentRow(r); self.lst.scrollToItem(it); self._focus_pos()
                if (step > 0 and r < r0) or (step < 0 and r > r0): self.win.msg('從清單另一頭繼續找到的')
                return
        self.win.msg('這個清單都分級好了 ✅')

    def _upd_row(self, fid, **kw):
        it = self.item_of.get(fid); r = getattr(self, 'row_of', {}).get(fid)
        if it is None or r is None: return
        try: r.update(kw); it.setText(self._row_text(r)); it.setForeground(QColor(GC.get(r['grade'], '#dfe5ee')))
        except RuntimeError: pass                                               # 清單剛好重讀，那一列已經不在

    # ---- 多選＋批量
    def sel_rows(self):
        """選取的那幾部（照清單順序）；沒有多選就是目前這一部."""
        ids = [it.data(Qt.UserRole) for it in self.lst.selectedItems()]
        R = [self.row_of[i] for i in ids if i in getattr(self, 'row_of', {})]
        if not R and self.cur: R = [self.row_of.get(self.cur['id'], self.cur)]
        order = {r['id']: k for k, r in enumerate(self.rows)}; return sorted(R, key=lambda r: order.get(r['id'], 0))

    def _sel_changed(self):
        R = [it for it in self.lst.selectedItems()]; n = len(R)
        if n >= 2:
            rows = [self.row_of[i.data(Qt.UserRole)] for i in R if i.data(Qt.UserRole) in self.row_of]
            cut = sum(1 for r in rows if r['cut_n']); nm = sum(1 for r in rows if r['ext'] not in ('.mp4', '.m4v'))
            self.bb_l.setText(f'已選 <b>{n:,}</b> 部 · {fmt_b(sum(r["size"] or 0 for r in rows))} · {fmt_t(sum(r["dur"] or 0 for r in rows))}' + (f' · 已剪輯 {cut}' if cut else ''))
            self.bb_del.setEnabled(cut > 0); self.bb_del.setText(f'🗑 刪除原檔（{cut}）'); self.bb_conv.setEnabled(nm > 0); self.bb_conv.setText(f'🔁 轉檔（{nm}）'); self.bbar.show()
        else: self.bbar.hide()

    def _play_cur(self):
        if self.cur: self.play(0)

    def grade_many(self, k):
        R = self.sel_rows()
        if not R: return
        if len(R) == 1 and self.cur and R[0]['id'] == self.cur['id']: self.set_grade(k); return
        ids = [r['id'] for r in R]; self.undo.append(('grade', [(r['id'], r['grade'] or '') for r in R])); self.undo = self.undo[-30:]
        for r in R: self._upd_row(r['id'], grade=k)
        if self.cur and self.cur['id'] in ids:
            self.cur['grade'] = k
            for kk, x in self.gb.items(): x.setChecked(kk == k)
        bg(lambda: ENG.set_flags(ids, grade=k), lambda _r: (self.load_chips(), self.tree_relabel())); self.win.msg(f'{len(ids)} 部 → {k + "（" + GN[k] + "）" if k else "未分級"}（Ctrl+Z 可以復原）')

    def undo_last(self):
        if not self.undo: self.win.msg('沒有可以復原的'); return
        field, pairs = self.undo.pop()
        for i, v in pairs: self._upd_row(i, **{field: v})
        if self.cur:
            m = dict(pairs)
            if self.cur['id'] in m:
                self.cur[field] = m[self.cur['id']]
                if field == 'grade':
                    for kk, x in self.gb.items(): x.setChecked(kk == (self.cur['grade'] or ''))
        bg(lambda: ENG.set_values(pairs, field), lambda _r: (self.load_chips(), self.tree_relabel() if field == 'grade' else None)); self.lst.viewport().update(); self.win.msg(f'已復原 {len(pairs)} 部的' + {'grade': '分級', 'tag': '顏色標籤', 'viewed': '看過記號', 'note': '備註'}.get(field, field))

    def fav_many(self):
        R = self.sel_rows()
        if not R: return
        mode = '複製' if (ENG.cfg.get('fav_mode') or 'copy') == 'copy' else '搬'
        if QMessageBox.question(self, '收藏', f'把選的 {len(R)} 部{mode}到各自硬碟的收藏資料夾？\n（{fmt_b(sum(r["size"] or 0 for r in R))}，後台看進度）') != QMessageBox.Yes: return
        ids = [r['id'] for r in R]
        bg(lambda: [ENG.file_op(i, 'fav') for i in ids], lambda res: self.win.msg(f'已排入收藏 {sum(1 for x in res if x.get("ok"))} 部（後台看進度）'))

    def front_many(self):
        R = self.sel_rows()
        for r in reversed(R): ENG.thumb_front(r['id'])
        self.win.msg(f'{len(R)} 部的預覽圖排到最前面（照清單順序）')

    def trash_many(self):
        R = self.sel_rows()
        if not R: return
        if len(R) == 1 and self.cur and R[0]['id'] == self.cur['id']: self.trash(); return
        if QMessageBox.question(self, '移到待刪', f'把選的 {len(R)} 部搬到各自硬碟的 VideoSIFT\\待刪？（{fmt_b(sum(r["size"] or 0 for r in R))}）\n\n不會真的刪掉。') != QMessageBox.Yes: return
        ids = [r['id'] for r in R]
        bg(lambda: [ENG.file_op(i, 'trash') for i in ids], lambda res: (self.win.msg(f'已排入待刪 {len(res)} 部（後台看進度）'), QTimer.singleShot(2500, self.load_list)))

    def del_many(self):
        R = [r for r in self.sel_rows() if r['cut_n']]
        if not R: self.win.msg('選的影片裡沒有剪過的（要先剪才能刪原檔）'); return
        if len(R) == 1 and self.cur and R[0]['id'] == self.cur['id']: self.del_orig(); return
        if QMessageBox.question(self, '刪除原檔', f'刪除 {len(R)} 部已剪輯影片的原檔（{fmt_b(sum(r["size"] or 0 for r in R))}）？\n\n'
                                '丟到資源回收筒，它們的 2 秒預覽圖一起刪；剪好的初剪檔永久保留。\n每部都會先確認初剪檔還在、原檔沒被換掉。') != QMessageBox.Yes: return
        ids = [r['id'] for r in R]; bg(lambda: ENG.delete_original_many(ids), lambda res: self._del_many_done(res, False))

    def _del_many_done(self, res, permanent):
        msg = f'刪除原檔：成功 {res["ok"]} 部' + (f'，{len(res["fail"])} 部沒刪' if res['fail'] else '')
        self.win.msg(msg); self.load_list(); self.load_tree()
        if res['fail']: QMessageBox.warning(self, '刪除原檔', msg + '：\n\n' + '\n'.join(f'• {n}：{m}' for n, m in res['fail'][:15]) + ('\n…' if len(res['fail']) > 15 else ''))
        if res['need_perm'] and not permanent:
            if QMessageBox.question(self, '刪除原檔', f'有 {len(res["need_perm"])} 部所在的硬碟沒辦法丟資源回收筒。\n要直接刪除嗎？（直接刪除就救不回來了）') == QMessageBox.Yes:
                ids = res['need_perm']; bg(lambda: ENG.delete_original_many(ids, True), lambda r2: self._del_many_done(r2, True))

    def conv_many(self):
        R = [r for r in self.sel_rows() if r['ext'] not in ('.mp4', '.m4v')]
        if not R: self.win.msg('選的都已經是 MP4'); return
        if QMessageBox.question(self, '轉檔', f'把選的 {len(R)} 部（不是 MP4 的）加入轉檔排隊？\n設定照「🔁 轉檔」頁。') != QMessageBox.Yes: return
        ids = [r['id'] for r in R]; bg(lambda: ENG.conv_add(ids), lambda n: self.win.msg(f'已加入轉檔 {n} 部（🔁 轉檔頁看進度）'))

    def ex_many(self):
        F = sorted({r['folder'] for r in self.sel_rows()})
        roots = {core.path_key(x) for x in ENG.cfg.get('roots') or []}; F = [f for f in F if core.path_key(f) not in roots]
        if not F: self.win.msg('選的影片都在影片庫最上層（要排除整顆請到設定移除）'); return
        if QMessageBox.question(self, '排除資料夾', f'排除這 {len(F)} 個資料夾（含子資料夾）？\n\n' + '\n'.join(F[:12]) + ('\n…' if len(F) > 12 else '') +
                                '\n\n裡面的影片會從清單拿掉，檔案不會動。') != QMessageBox.Yes: return
        bg(lambda: sum(ENG.add_exclude(path=f) for f in F), lambda n: _ex_done(self.win, f'已排除 {len(F)} 個資料夾（拿掉 {n:,} 部影片）'))

    # ---- 📦 歸檔／歸類
    def _fill_arch_menu(self):
        m = self.am; m.clear(); C = ENG.grade_counts(self.folder); names = ENG.cfg.get('arch_names') or {}
        where = self.folder or '整個影片庫'; m.addAction(f'範圍：{where}（含子資料夾）').setEnabled(False)
        any_ = False
        for g in ('S', 'A', 'E', 'F'):
            n, sz = C.get(g, (0, 0))
            to = 'VideoSIFT\\待刪' if (g == 'F' and ENG.cfg.get('arch_f_trash')) else f'VideoSIFT\\{names.get(g) or g}'
            a = m.addAction(f'{g}（{GN[g]}）{n:,} 部・{fmt_b(sz)}　→ {to}', lambda g=g: self.archive_grade(g)); a.setEnabled(n > 0); any_ = any_ or n > 0
        if not any_: m.addAction('（這個範圍裡還沒有分好級的影片）').setEnabled(False)
        m.addSeparator(); m.addAction('📒 看操作紀錄（30 天，可以搬回來）', lambda: self.win.nav.setCurrentRow(6))

    def purge_trash(self):
        def ask(r):                                                              # V0.6.35 也看 X:\DELETE（轉檔前的原檔），可以選清哪個
            fn, fb_ = int(r.get('f_n') or 0), int(r.get('f_b') or 0); where = self.folder or '整個影片庫'
            fl = (f'\n🅵 F 級（{where}，還在原位）：{fn:,} 部・{fmt_b(fb_)}（剪好的片段 100% 保留）' if fn else '')
            tn, tb, dn, db_ = int(r.get('trash_n') or 0), int(r.get('trash_b') or 0), int(r.get('del_n') or 0), int(r.get('del_b') or 0)
            if not tn and not dn and not fn: QMessageBox.information(self, '🔥 清空待刪', '待刪和 DELETE 都是空的' + (f'（{r["skip"]} 個是初剪或正在用，保留）' if r.get('skip') else '') + fl); return
            mb = QMessageBox(self); mb.setWindowTitle('🔥 清空待刪'); mb.setIcon(QMessageBox.Warning)
            mb.setText(f'要永久刪除哪些？（不經過資源回收筒，刪了救不回來）\n\n'
                       f'🗑 VideoSIFT\\待刪：{tn:,} 個・{fmt_b(tb)}（預覽圖、人臉、清單那一筆一起清；初剪的 100% 保留）\n'
                       f'🔁 X:\\DELETE（轉檔前的原檔）：{dn:,} 個・{fmt_b(db_)}（轉好的 MP4 留著）' + (f'；轉完變大的 {r.get("del_skip", 0)} 個原檔保留' if r.get('del_skip') else '') + fl)
            bt = mb.addButton(f'只清待刪（{fmt_b(tb)}）', QMessageBox.AcceptRole) if tn else None
            bd = mb.addButton(f'只清 DELETE（{fmt_b(db_)}）', QMessageBox.AcceptRole) if dn else None
            bb = mb.addButton(f'待刪＋DELETE（{fmt_b(tb + db_)}）', QMessageBox.AcceptRole) if tn and dn else None
            bf = mb.addButton(f'🅵 F 級直接刪（{fmt_b(fb_)}）', QMessageBox.AcceptRole) if fn else None                      # V0.6.36 不用先移到待刪
            ba = mb.addButton(f'全部一起（{fmt_b(tb + db_ + fb_)}）', QMessageBox.AcceptRole) if fn and (tn or dn) else None
            mb.addButton('取消', QMessageBox.RejectRole); mb.exec(); c = mb.clickedButton()
            if c is None or c not in [x for x in (bt, bd, bb, bf, ba) if x is not None]: return
            if c is bf: w, f_, n, b_ = '', 'only', fn, fb_
            elif c is ba: w, f_, n, b_ = 'with', 'with', tn + dn + fn, tb + db_ + fb_
            else:
                f_ = ''; w = 'only' if c is bd else 'with' if c is bb else ''; n = dn if w == 'only' else tn + dn if w == 'with' else tn; b_ = db_ if w == 'only' else tb + db_ if w == 'with' else tb
            if n > 20 and QMessageBox.question(self, '🔥 清空待刪', f'再確認一次：永久刪除 {n:,} 個檔、{fmt_b(b_)}？') != QMessageBox.Yes: return
            fd = self.folder or ''
            bg(lambda: ENG.trash_purge(dry=False, incl_del=(w == 'with'), only_del=(w == 'only'), incl_f=(f_ == 'with'), only_f=(f_ == 'only'), folder=fd),
               lambda x: (self.win.msg('🔥 ' + x.get('message', ''), 12000), QTimer.singleShot(3000, self.load_list)))
        fd0 = self.folder or ''
        bg(lambda: ENG.trash_purge(dry=True, folder=fd0), ask)

    def archive_grade(self, g, folder=None):
        fd = self.folder if folder is None else folder
        ids = ENG.grade_ids(g, fd); C = ENG.grade_counts(fd); n, sz = C.get(g, (0, 0))
        if not ids: return
        to = 'VideoSIFT\\待刪' if (g == 'F' and ENG.cfg.get('arch_f_trash')) else 'VideoSIFT\\' + ((ENG.cfg.get('arch_names') or {}).get(g) or g)
        if QMessageBox.question(self, '一鍵歸檔', f'把 {fd or "整個影片庫"} 裡分級 {g}（{GN[g]}）的 {n:,} 部（{fmt_b(sz)}）\n搬到各自硬碟的 {to}？\n\n'
                                '同一顆硬碟只是改位置，很快；歸進去就不再出現在清單。\n每一筆都記在「📒 操作紀錄」（30 天），搬錯可以搬回來。') != QMessageBox.Yes: return
        kind = 'trash' if (g == 'F' and ENG.cfg.get('arch_f_trash')) else f'grade:{g}'
        bg(lambda: ENG.archive_many(ids, kind), lambda k: (self.win.msg(f'已排入歸檔 {k:,} 部（後台看進度；📒 操作紀錄有每一筆）'), QTimer.singleShot(2000, self.load_list), QTimer.singleShot(2500, self.load_tree)))

    def _fill_cat_menu(self, m):
        m.clear(); names = ENG.cfg.get('arch_names') or {}
        for g in ('S', 'A', 'E', 'F'):
            to = '待刪' if (g == 'F' and ENG.cfg.get('arch_f_trash')) else (names.get(g) or g)
            m.addAction(f'{g}　→ VideoSIFT\\{to}', lambda g=g: self.archive_sel('trash' if (g == 'F' and ENG.cfg.get('arch_f_trash')) else f'grade:{g}', to))
        m.addSeparator()
        for c in ENG.cfg.get('cats') or []: m.addAction(f'📁 {c}', lambda c=c: self.archive_sel(f'cat:{c}', c))
        m.addAction('＋ 新增分類資料夾…', self.new_cat)

    def _folder_move(self, d):
        """V0.2.34 🚚 這個資料夾搬到別顆硬碟."""
        L = sorted(set(ENG.vol_letters().values()) - {d[:1].upper()})
        if not L: QMessageBox.information(self, '搬資料夾', '沒有偵測到別顆硬碟'); return
        items = []
        for X in L:
            try: items.append(f'{X}:（{ENG.vol_label(X + ":" + chr(92)) or "沒有名稱"}）剩 {fmt_b(shutil.disk_usage(X + ":" + chr(92)).free)}')
            except Exception: items.append(f'{X}:')
        it, ok = QInputDialog.getItem(self, '🚚 搬到別顆硬碟', f'把\n{d}\n搬到哪一顆？', items, 0, False)
        if not ok: return
        X = it[:1]; to, ok = QInputDialog.getText(self, '🚚 搬到別顆硬碟', '新位置（可以改）：', text=X + ':' + d[2:])
        if not ok or not to.strip(): return
        if QMessageBox.question(self, '🚚 搬到別顆硬碟', f'{d}\n→ {to.strip()}\n\n整個資料夾（含子資料夾）搬過去，分級、備註、預覽圖都跟著過去。\n'
                                '每個檔都先複製、比對一樣才刪原檔；背景慢慢搬，進度在「🚚 搬硬碟」。') != QMessageBox.Yes: return
        r = ENG.move_start_folder(d, to.strip(), 60); self.win.msg(r.get('message', ''))
        if r.get('ok'): self.win.enter(15)

    def creators_dlg(self):
        """V0.2.33 👥 作者／主播統計：點兩下＝檔案總管只看他（用搜尋框）."""
        d = QDialog(self); d.setWindowTitle('👥 依作者／主播'); d.resize(760, 560); v = QVBoxLayout(d)
        q = QLineEdit(); q.setPlaceholderText('找作者'); v.addWidget(q); t = QTableWidget(0, 14); v.addWidget(t, 1)
        t.setHorizontalHeaderLabels(['作者（從檔名猜）', '部數', '大小', '已分級', 'S', 'A', 'E', 'F', '還沒分', '😴 平均靜止', '📤 上傳過', '最後上傳', '✅ 發佈過', '最後發佈']); t.verticalHeader().setVisible(False); t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectRows); t.setSortingEnabled(True); t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        n = QLabel('讀取中…'); n.setObjectName('muted'); v.addWidget(n); D = []
        def num(x, txt=None):
            it = QTableWidgetItem(); it.setData(Qt.DisplayRole, x if txt is None else txt); it.setData(Qt.UserRole, x); return it
        def show(*_a):
            k_ = q.text().strip().lower(); R_ = [x for x in D if k_ in x['k'].lower()]; t.setSortingEnabled(False); t.setRowCount(len(R_))
            for i, x in enumerate(R_):
                t.setItem(i, 0, QTableWidgetItem(x['k'])); t.setItem(i, 1, num(x['n'])); it = num(x['bytes'], fmt_b(x['bytes'])); t.setItem(i, 2, it)
                t.setItem(i, 3, num(round(x['graded'] * 100 / max(1, x['n'])), f"{round(x['graded'] * 100 / max(1, x['n']))}%"))
                for j, g in enumerate('SAEF'): t.setItem(i, 4 + j, num(x.get(g, 0)))
                t.setItem(i, 8, num(x['n'] - x['graded']))
                t.setItem(i, 9, num(x['still'] if x.get('still') is not None else -1, f"{round(x['still'] * 100)}%（{x['still_n']} 部）" if x.get('still') is not None else ''))   # V0.3.19
                t.setItem(i, 10, num(x.get('up', 0))); lu = float(x.get('last_up') or 0); t.setItem(i, 11, num(lu, f"{int((time.time() - lu) // 86400)} 天前" if lu else ''))   # V0.3.75
                t.setItem(i, 12, num(x.get('pub', 0))); lp_ = float(x.get('last_pub') or 0); t.setItem(i, 13, num(lp_, f"{int((time.time() - lp_) // 86400)} 天前" if lp_ else ''))   # V0.4.40
            t.setSortingEnabled(True); n.setText(f'{len(R_):,} 位（點兩下＝檔案總管只看他）')
        def got(r):
            D[:] = r; show()
        def go(it):
            k_ = t.item(it.row(), 0).text()
            if k_ and k_ != '（其他）': self.q.setText(k_); d.accept(); self.win.msg(f'👥 只看「{k_}」（清掉搜尋框就回到全部）')
        q.textChanged.connect(show); t.itemDoubleClicked.connect(go); bg(ENG.creator_stats, got); d.exec(); d.deleteLater()

    def show_month(self, ym):
        k = f'month:{ym}'; i = self.flt.findData(k)
        if i < 0: self.flt.addItem(f'📅 {ym}', k); i = self.flt.findData(k)
        self.folder = ''; self.tree.setCurrentItem(self.tree.topLevelItem(0)) if self.tree.topLevelItemCount() else None; self.flt.setCurrentIndex(i)

    def months_dlg(self):
        """V0.2.47 📅 依月份：點兩下＝檔案總管只看那個月."""
        d = QDialog(self); d.setWindowTitle('📅 依月份（檔案時間）'); d.resize(720, 560); v = QVBoxLayout(d); t = QTableWidget(0, 9); v.addWidget(t, 1)
        t.setHorizontalHeaderLabels(['月份', '部數', '大小', '已分級', 'S', 'A', 'E', 'F', '還沒分']); t.verticalHeader().setVisible(False); t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectRows); t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        n = QLabel('讀取中…'); n.setObjectName('muted'); v.addWidget(n)
        def cell(x, txt=None):
            it = QTableWidgetItem(str(x) if txt is None else txt); it.setData(Qt.UserRole, x); return it
        def got(R):
            t.setRowCount(len(R))
            for i, x in enumerate(R):
                pc = round(x['graded'] * 100 / max(1, x['n']))
                for j, c in enumerate((cell(x['ym']), cell(f"{x['n']:,}"), cell(fmt_b(x['bytes'])), cell(f'{pc}%'), cell(x['S']), cell(x['A']), cell(x['E']), cell(x['F']), cell(x['n'] - x['graded']))): t.setItem(i, j, c)
            n.setText(f'{len(R):,} 個月（點兩下＝檔案總管只看那個月；時間是檔案的修改時間，通常就是錄影那天）')
        def go(it):
            ym = t.item(it.row(), 0).text(); d.accept(); self.show_month(ym); self.win.msg(f'📅 只看 {ym}（篩選選「全部」就回去）')
        t.itemDoubleClicked.connect(go); bg(ENG.month_stats, got); d.exec(); d.deleteLater()

    def _fold_menu(self):
        """V0.2.29 📁 用資料夾分類：彈出選單（你的分類資料夾＋新增）."""
        if not self.cur and not self.sel_rows(): self.win.msg('先選一部影片'); return
        m = QMenu(self); m.addAction('用資料夾分類（自動標 S，搬到 VideoSIFT\\資料夾）').setEnabled(False); m.addSeparator()
        for c in ENG.cfg.get('cats') or []: m.addAction(f'📁 {c}', lambda c=c: self.fold_to(c))
        if not (ENG.cfg.get('cats') or []): m.addAction('（還沒有資料夾）').setEnabled(False)
        m.addSeparator(); m.addAction('＋ 新增資料夾…', self._fold_new)
        m.exec(self.b_fold.mapToGlobal(QPoint(0, self.b_fold.height()))); m.deleteLater()

    def _fold_new(self):
        name, ok = QInputDialog.getText(self, '新增資料夾', '資料夾名稱（例如：工作用、林娜貝兒）：\n會放在每顆硬碟的 VideoSIFT\\ 底下')
        if not ok or not str(name).strip(): return
        nm = core.safe_name(str(name).strip())[:60]
        if not ENG.add_cat(nm) and nm not in (ENG.cfg.get('cats') or []): self.win.msg('這個名稱不能用'); return
        try: self.win.setp._load_cats()
        except Exception: pass
        self.fold_to(nm)

    def fold_to(self, cat):
        """這部（或多選的）→ 標 S → 搬到 VideoSIFT\\<cat>；接著跳下一部還沒分級的."""
        R = self.sel_rows() if len(self.sel_rows()) > 1 else ([self.cur] if self.cur else [])
        if not R: return
        ids = [int(r['id']) for r in R]
        if len(ids) == 1 and self.cur and self.cur['id'] == ids[0]:
            self.undo.append(('grade', [(ids[0], self.cur.get('grade') or '')])); self.undo = self.undo[-30:]; self.cur['grade'] = 'S'
            for kk, x in self.gb.items(): x.setChecked(kk == 'S')
        def go():
            for i in ids: ENG.set_flag(i, grade='S')
            return ENG.archive_many(ids, f'cat:{cat}')
        bg(go, lambda n: (self.win.msg(f'📁 {len(ids)} 部 → S，搬到 VideoSIFT\\{cat}（{n} 部排進搬檔）'), [self._upd_row(i, grade='S') for i in ids], self.load_chips(),
                         QTimer.singleShot(1500, self.load_list), QTimer.singleShot(2000, self.load_tree)))
        if (ENG.cfg.get('lab') or {}).get('auto_next'): QTimer.singleShot(150, lambda: self.next_ungraded(1))

    def new_cat(self):
        name, ok = QInputDialog.getText(self, '新增分類資料夾', '資料夾名稱（例如：工作用、家庭日）：\n會放在每顆硬碟的 VideoSIFT\\ 底下；歸進去的影片不再出現在清單、不用分級')
        if not ok or not str(name).strip(): return
        if ENG.add_cat(name): self.win.msg(f'已新增分類：{core.safe_name(str(name).strip())}'); self.win.setp._load_cats()
        else: self.win.msg('這個名稱不能用或已經有了')

    def archive_sel(self, kind, label):
        R = self.sel_rows()
        if not R: return
        if QMessageBox.question(self, '歸類', f'把選的 {len(R)} 部（{fmt_b(sum(r["size"] or 0 for r in R))}）歸到各自硬碟的 VideoSIFT\\{label}？\n\n'
                                '歸進去就不再出現在清單（篩選「📦 已歸檔」還看得到）；「📒 操作紀錄」可以搬回來。') != QMessageBox.Yes: return
        ids = [r['id'] for r in R]
        bg(lambda: ENG.archive_many(ids, kind), lambda k: (self.win.msg(f'已排入歸類 {k} 部 → {label}'), QTimer.singleShot(1500, self.load_list), QTimer.singleShot(2000, self.load_tree)))

    # ---- 卡片／清單
    def apply_view(self):
        card = (self.vmode.currentData() or 'card') == 'card'; self.card_w = int(self.csize.currentData() or 150); self.csize.setVisible(card)
        if card:
            self.lst.setViewMode(QListView.IconMode); self.lst.setFlow(QListView.LeftToRight); self.lst.setWrapping(True); self.lst.setResizeMode(QListView.Adjust)
            self.lst.setMovement(QListView.Static); self.lst.setSpacing(0); self.lst.setItemDelegate(self.card_del)
            self.lst.setGridSize(self.card_del.sizeHint(None, None)); self.lst.setUniformItemSizes(True)
        else:
            self.lst.setViewMode(QListView.ListMode); self.lst.setGridSize(QSize()); self.lst.setWrapping(False); self.lst.setItemDelegate(self.plain_del)
        self.lst.viewport().update()

    def eventFilter(self, obj, e):
        """🧪 卡片滑過預覽：滑鼠在卡片上左右移動 → 換成影片不同位置的畫面（只切 24 個位置，不存檔）."""
        try:
            t = e.type()
            if t == QEvent.MouseMove and (ENG.cfg.get('lab') or {}).get('card_scrub') and (self.vmode.currentData() or 'card') == 'card':
                pos = e.position().toPoint(); idx = self.lst.indexAt(pos); fid = idx.data(Qt.UserRole) if idx.isValid() else None
                r = self.row_of.get(fid) if fid is not None else None
                if r and int(r.get('th_state') or 0) == 2 and int(r.get('th_n') or 0) > 1 and r.get('th_dir'):
                    R = self.lst.visualRect(idx); n = int(r['th_n']); fr = max(0.0, min(1.0, (pos.x() - R.x() - 5) / max(1, R.width() - 10)))
                    k = min(n - 1, int(round(fr * 23)) * (n - 1) // 23)
                    if self.scrub != (fid, k):
                        old = self.scrub; self.scrub = (fid, k)
                        if (fid, k) not in self.cards:
                            self.cload.want((fid, k), {'dir': r['th_dir'], 'k': k, 'cols': int(r.get('th_cols') or 10), 'rows': int(r.get('th_rows') or 10), 'nosave': True}, self._card_loaded)
                        self.lst.viewport().update(R)
                        if old and old[0] != fid and old[0] in self.item_of: self.lst.viewport().update(self.lst.visualItemRect(self.item_of[old[0]]))
                elif self.scrub: self._scrub_off()
            elif t == QEvent.Leave and self.scrub: self._scrub_off()
        except Exception: ENG.log.err('卡片滑過預覽')
        return False

    def _scrub_off(self):
        self.scrub = None; self.lst.viewport().update()

    def card_pix(self, r):
        """卡片的縮圖（記憶體裡最多 900 張；沒有就叫背景去切，切好畫面自己更新）."""
        if int(r.get('th_state') or 0) != 2 or not r.get('th_dir'): return None
        key = (r['id'], card_k(r)); pm = self.cards.get(key)
        if pm is not None: self.cards.move_to_end(key); return pm
        self.cload.want(key, {'dir': r['th_dir'], 'k': key[1], 'cols': int(r.get('th_cols') or 10), 'rows': int(r.get('th_rows') or 10)}, self._card_loaded)
        return None

    def _card_loaded(self, key, img):
        if img.isNull(): self.cards[key] = QPixmap(); return
        self.cards[key] = QPixmap.fromImage(img)
        while len(self.cards) > 900: self.cards.popitem(last=False)
        if not self._vp_t.isActive(): self._vp_t.start(60)

    def reroll_card(self, R):
        """🎲 換一張縮圖."""
        pairs = []
        for r in R:
            n = int(r.get('th_n') or 0)
            if n < 2: continue
            old = card_k(r); k = old
            while k == old: k = random.randint(int(n * 0.05), max(int(n * 0.05), n - 1))
            r['card_k'] = k; pairs.append((r['id'], k))
        if pairs:
            bg(lambda: [ENG.set_flags([i], card_k=k) for i, k in pairs]); self.lst.viewport().update(); self.win.msg(f'換了 {len(pairs)} 張卡片縮圖')

    def _refresh_states(self):
        """預覽圖做好了，卡片自己換成縮圖（不用整個清單重讀）."""
        ids = [r['id'] for r in self.rows if int(r.get('th_state') or 0) != 2][:2000]
        try: ids += [i for i in ENG.e_fix_ids() if i in self.row_of and i not in ids]           # V0.2.08 標 E 重做中的：做好會拿掉 E，卡片跟著換
        except Exception: pass
        if ids: bg(lambda: ENG.states(ids), self._states_got)
        try:                                                                    # V0.2.02 剪輯排隊變了：卡片的「-剪輯／√剪輯」跟著換
            P = ENG.cut_pending(); old = getattr(self, 'cut_pend', None) or {}
            if P != old:
                self.cut_pend = P; gone = [i for i in old if P.get(i, 0) < old[i] and i in self.row_of]
                if gone: bg(lambda: ENG.states(gone), self._cut_got)
                self.lst.viewport().update()
        except Exception: pass

    def _cut_got(self, M):
        for fid, x in M.items():
            r = self.row_of.get(fid)
            if r is not None: r['cut_n'] = x.get('cut_n') or 0
        self.lst.viewport().update()

    def _states_got(self, M):
        ch = False
        for fid, x in M.items():
            r = self.row_of.get(fid)
            if r and 'grade' in x and (r.get('grade') or '') != (x['grade'] or ''):
                r['grade'] = x['grade'] or ''; ch = True
                it = self.item_of.get(fid)
                if it is not None: it.setText(self._row_text(r))
                if self.cur and self.cur.get('id') == fid:
                    self.cur['grade'] = r['grade']
                    for kk, b_ in self.gb.items(): b_.setChecked(kk == r['grade'])
            if r and (r.get('th_state') != x['th_state'] or r.get('th_dir') != x['th_dir']):
                r.update(th_state=x['th_state'], th_n=x['th_n'], th_dir=x['th_dir'], th_cols=x['th_cols'], th_rows=x['th_rows']); ch = True
                it = self.item_of.get(fid)
                if it is not None: it.setText(self._row_text(r))
        if ch: self.lst.viewport().update()

    # ---- 標記
    def redo_precise(self, R):
        if QMessageBox.question(self, '重做預覽圖', f'把 {len(R)} 部的預覽圖用「精準模式」重做？\n\n每一張都是那一秒的真實畫面（不會連續好幾張一樣），比較慢；做好之前格子先不能看。') != QMessageBox.Yes: return
        for r in R: ENG.thumb_redo(r['id'], precise=True); self._upd_row(r['id'], th_state=0)
        self.lst.viewport().update(); self.win.msg(f'{len(R)} 部排到最前面重做預覽圖（精準）')
        if self.cur and any(r['id'] == self.cur['id'] for r in R): self.grid.set_video(None, []); self.cur['th_state'] = 0; self.show_file(self.cur)

    def mark_viewed(self, on):
        R = self.sel_rows(); v = time.time() if on else 0
        if not R: return
        self.undo.append(('viewed', [(r['id'], r.get('viewed') or 0) for r in R])); self.undo = self.undo[-30:]
        for r in R: self._upd_row(r['id'], viewed=v)
        ids = [r['id'] for r in R]; bg(lambda: ENG.set_flags(ids, viewed=v)); self.lst.viewport().update(); self.win.msg(f'{len(R)} 部標成{"看過" if on else "沒看過"}')

    def set_tag(self, tag):
        R = self.sel_rows()
        if not R: return
        self.undo.append(('tag', [(r['id'], r.get('tag') or '') for r in R])); self.undo = self.undo[-30:]
        for r in R: self._upd_row(r['id'], tag=tag)
        ids = [r['id'] for r in R]; bg(lambda: ENG.set_flags(ids, tag=tag)); self.lst.viewport().update()
        self.win.msg(f'{len(R)} 部' + (f'標上{TAGS[tag][0]} {TAGS[tag][1]}色' if tag else '拿掉顏色標籤') + '（Ctrl+Z 可以復原）')

    def edit_note(self):
        R = self.sel_rows()
        if not R: return
        old = R[0].get('note') or ''
        txt, ok = QInputDialog.getText(self, '備註', f'備註（{len(R)} 部{"，會一起改成這段" if len(R) > 1 else ""}；清空＝拿掉）：', QLineEdit.Normal, old)
        if not ok: return
        txt = str(txt).strip()[:500]; self.undo.append(('note', [(r['id'], r.get('note') or '') for r in R])); self.undo = self.undo[-30:]
        for r in R: self._upd_row(r['id'], note=txt)
        ids = [r['id'] for r in R]; bg(lambda: ENG.set_flags(ids, note=txt)); self.lst.viewport().update()
        if self.cur and self.cur['id'] in ids: self.cur['note'] = txt; self.show_file(self.cur)

    def quick_note(self, t):
        """V0.2.82 ✎ 快速備註：把這幾個字加到備註後面（已經有就不重複）."""
        R = self.sel_rows()
        if not R: return
        self.undo.append(('note', [(r['id'], r.get('note') or '') for r in R])); self.undo = self.undo[-30:]
        for r in R:
            old = r.get('note') or ''; new = old if t in old else (old + ('、' if old else '') + t)[:500]
            self._upd_row(r['id'], note=new); i_ = r['id']; bg(lambda i_=i_, new=new: ENG.set_flags([i_], note=new))
            if self.cur and self.cur['id'] == r['id']: self.cur['note'] = new
        self.lst.viewport().update(); self.cur and self.show_file(self.cur); self.win.msg(f'✎ {len(R)} 部加上「{t}」')

    def copy_files(self, R):
        md = QMimeData(); md.setUrls([QUrl.fromLocalFile(r['path']) for r in R]); md.setText('\n'.join(r['path'] for r in R))
        QApplication.clipboard().setMimeData(md); self.win.msg(f'已複製 {len(R)} 個檔案（可以到檔案總管貼上）')

    def _shell(self, what, R):
        try:
            for r in R[:20]:
                if not os.path.exists(r['path']): self.win.msg(f'找不到檔案：{r["path"]}'); continue
                if what == 'select': core.explorer_select(r['path'])
                elif what == 'open': core.open_default(r['path'])
                elif what == 'with': core.open_with(r['path'])
                elif what == 'props':
                    if not core.show_properties(r['path']): self.win.msg('這個系統沒有「內容」視窗')
            ENG.log.w(f'畫面：{ {"select": "檔案總管定位", "open": "預設程式開啟", "with": "開啟方式", "props": "內容"}[what]} {len(R)} 部：' + '、'.join(r['name'] for r in R[:5]))
        except Exception as ex: ENG.log.err(f'開啟（{what}）'); self.win.msg(f'打不開：{ex}')

    def _list_menu(self, pos):
        it = self.lst.itemAt(pos)
        if it is None: return
        if not it.isSelected(): self.lst.setCurrentItem(it)
        R = self.sel_rows(); n = len(R)
        if not n: return
        m = QMenu(self); one = R[0]
        if n == 1: m.addAction('▶ 播放（內建）', lambda: self.play(0))
        m.addAction('📂 在 Windows 檔案總管顯示（選取這個檔）', lambda: self._shell('select', R))
        m.addAction('🎬 用預設程式開啟', lambda: self._shell('open', R))
        if n == 1: m.addAction('…用其他程式開啟', lambda: self._shell('with', R))
        m.addAction('📄 內容（Windows 的檔案內容視窗）', lambda: self._shell('props', R))
        if n == 1 and lab_cfg().get('bookmarks'):                              # V0.2.80 🔖 從書籤播
            BM_ = ENG.bm_list(one['id'])
            if BM_:
                sm_ = m.addMenu(f'🔖 從書籤播（{len(BM_)}）')
                for t_, n_ in BM_: sm_.addAction(f'▶ {fmt_t(t_)}　{n_}', lambda t_=t_: self.play(t_))
                if self.cur and self.cur['id'] == one['id'] and self.grid.n: m.addAction(f'✂ 書籤附近選成片段（{len(BM_)} 段：前 5 秒～後 15 秒）', lambda: [self.grid.add_seg_t(max(0.0, t_ - 5), t_ + 15) for t_, _n in BM_])   # V0.2.97
        if n == 1 and lab_cfg().get('file_hist'): m.addAction('📜 這部的紀錄', lambda: self.hist_dlg(one))   # V0.2.98
        if lab_cfg().get('scenes'): m.addAction(f'✂ 批次：{n} 部都剪掉 😴 靜止段落（有內容的合成一個檔）', lambda: (bg(lambda: ENG.cut_skip_static([r['id'] for r in R]), lambda r_: self.win.msg(r_[1] + '（後台看進度）', 12000))) if QMessageBox.question(self, '✂ 批次剪掉靜止', f'{n} 部：每部把靜止／黑畫面的段落剪掉，剩下有內容的合成一個新檔（原檔不動、放在初剪資料夾）？') == QMessageBox.Yes else None)   # V0.3.47
        if lab_cfg().get('caption'): m.addAction('📋 複製上傳文案', lambda: (QApplication.clipboard().setText('\n\n'.join(ENG.caption_for(r['id']) for r in R)), self.win.msg('📋 已複製上傳文案（可以直接貼到 TikTok）')))
        if lab_cfg().get('caption') and str(lab_cfg().get('caption_tpl2') or '').strip(): m.addAction('📋 複製上傳文案（第二組範本）', lambda: (QApplication.clipboard().setText('\n\n'.join(ENG.caption_for(r['id'], 2) for r in R)), self.win.msg('📋 已複製（第二組範本）')))   # V0.4.20   # V0.3.43
        if lab_cfg().get('playlist'): m.addAction(f'▶ 連播選的 {n} 部' if n > 1 else '▶ 從這部開始連播清單', lambda: self.play_list(R if n > 1 else self.rows[next((i for i, x in enumerate(self.rows) if x['id'] == one['id']), 0):]))   # V0.2.90
        if lab_cfg().get('copy_to'): m.addAction(f'📤 複製到上傳資料夾（{n} 部，原檔留著）', lambda: self.win.msg(ENG.copy_enqueue([r['id'] for r in R])[1]))   # V0.2.49
        if lab_cfg().get('copy_to'):                                           # V0.3.58 手動標記／取消「已上傳」
            on_ = not all(float(r.get('up_t') or 0) > 0 for r in R)
            def _um(on_=on_, R=R):
                n_, m_ = ENG.up_mark([r['id'] for r in R], on_)
                for r in R: self._upd_row(r['id'], up_t=time.time() if on_ else 0)
                self.win.msg(m_)
            m.addAction('📤 標成「已上傳」' if on_ else '↩ 取消「已上傳」標記', _um)
            onp_ = not all(float(r.get('pub_t') or 0) > 0 for r in R)        # V0.4.39 ✅ 已發佈也能右鍵標
            m.addAction('✅ 標成「已發佈」（P）' if onp_ else '↩ 取消「已發佈」（P）', self.toggle_pub)
        if lab_cfg().get('copy_to') and any(r.get('cut_n') for r in R): m.addAction('📤 剪好的片段複製到上傳資料夾', lambda: self.win.msg(ENG.copy_cuts([r['id'] for r in R])[1]))   # V0.2.59
        m.addSeparator()
        mk = m.addMenu(f'🏷 標記（{n} 部）')
        mk.addAction('✔ 標成看過', lambda: self.mark_viewed(True)); mk.addAction('• 標成沒看過', lambda: self.mark_viewed(False)); mk.addSeparator()
        for k2, (ic, nm, _c) in TAGS.items(): mk.addAction(f'{ic} {nm}色標籤', lambda k2=k2: self.set_tag(k2))
        mk.addAction('拿掉顏色標籤', lambda: self.set_tag('')); mk.addSeparator(); mk.addAction('✎ 備註…', self.edit_note)
        if lab_cfg().get('note_presets'):                                       # V0.2.82 ✎ 快速備註
            for t_ in note_presets(): mk.addAction(f'✎ ＋「{t_}」', lambda t_=t_: self.quick_note(t_))
        if (self.vmode.currentData() or 'card') == 'card': m.addAction('🎲 換一張卡片縮圖', lambda: self.reroll_card(R))
        m.addAction(f'🔁 重做預覽圖（精準，{n} 部）', lambda: self.redo_precise(R))
        if n == 1: m.addAction('🧬 找跟這部畫面相似的（🧪）', lambda: self.win.lab.find_like(R[0]))
        g = m.addMenu(f'分級（{n} 部）')
        for k in ('S', 'A', 'E', 'F', ''): g.addAction(f'{k}　{GN[k]}' if k else '— 未分級', lambda k=k: self.grade_many(k))
        self._fill_cat_menu(m.addMenu(f'📦 歸類到（{n} 部）'))
        m.addAction(f'⭐ 收藏（{n}）', self.fav_many); m.addAction(f'⚡ 先做預覽圖（{n}）', self.front_many)
        m.addSeparator()
        m.addAction(f'🗑 移到待刪（{n}）　Del', self.trash_many)
        c = sum(1 for r in R if r['cut_n'])
        a = m.addAction(f'🗑 刪除已剪輯的原檔（{c}）　Shift+Del', self.del_many); a.setEnabled(c > 0)
        nm = sum(1 for r in R if r['ext'] not in ('.mp4', '.m4v'))
        a = m.addAction(f'🔁 加入轉檔（{nm}）', self.conv_many); a.setEnabled(nm > 0)
        m.addAction('🚫 排除所在資料夾', self.ex_many)
        m.addSeparator()
        m.addAction('📋 複製路徑', lambda: (QApplication.clipboard().setText('\n'.join(r['path'] for r in R)), self.win.msg(f'已複製 {n} 個路徑')))
        m.addAction('📋 複製檔名', lambda: (QApplication.clipboard().setText('\n'.join(r['name'] for r in R)), self.win.msg(f'已複製 {n} 個檔名')))
        m.addAction('📋 複製檔案（到檔案總管貼上）', lambda: self.copy_files(R))
        m.exec(self.lst.viewport().mapToGlobal(pos)); m.deleteLater()

    def fav(self):
        if not self.cur: return
        mode = '複製' if (ENG.cfg.get('fav_mode') or 'copy') == 'copy' else '搬'
        dst = ENG.arch_dir('fav', self.cur['path'], ENG.cfg.get('fav_dir'))
        if QMessageBox.question(self, '收藏', f'把「{self.cur["name"]}」{mode}到：\n{dst}\n\n（設定裡可以改成搬或複製、改位置）') != QMessageBox.Yes: return
        fid = self.cur['id']; bg(lambda: ENG.file_op(fid, 'fav'), lambda r: self.win.msg(r['message']))

    def trash(self):
        if not self.cur: return
        dst = ENG.arch_dir('trash', self.cur['path'], ENG.cfg.get('trash_dir'))
        if QMessageBox.question(self, '移到待刪', f'把「{self.cur["name"]}」搬到：\n{dst}\n\n不會真的刪掉，之後確定不要再自己刪那個資料夾。') != QMessageBox.Yes: return
        fid = self.cur['id']; bg(lambda: ENG.file_op(fid, 'trash'), lambda r: (self.win.msg(r['message']), QTimer.singleShot(1500, self.load_list)))

    def cut(self):
        """先在背景算好檔名（要讀輸出資料夾；HDD 休眠時喚醒要幾秒，不能卡畫面），算好再跳確認視窗."""
        if not self.cur: return
        segs = self.grid.seg_times()
        if not segs: self.win.msg('先在格子上點選或拖曳圈選要留的片段'); return
        if getattr(self, '_cut_busy', False): return
        r = dict(self.cur); path = r['path']; n = len(segs); self._cut_busy = True; self.b_cut.setEnabled(False); self.win.msg('準備輸出初剪…（讀輸出資料夾）')
        def done(res):
            self._cut_busy = False; self.b_cut.setEnabled(bool(self.cur))
            if not self.cur or self.cur['id'] != r['id']: return
            self._cut_dialog(segs, res)
        def fail(_ex):
            self._cut_busy = False; self.b_cut.setEnabled(bool(self.cur)); self.win.msg('讀輸出資料夾失敗（硬碟沒接？）：看 LOG')
        bg(lambda: (ENG.cut_names(path, n, False), ENG.cut_names(path, n, True)), done, fail)

    def _cut_dialog(self, segs, names):
        (n_sep, how), (n_all, _h) = names
        od = ENG.arch_dir('cut', self.cur['path'], ENG.cfg.get('cut_dir'))
        mode = '⚡ 快速免轉檔（幾秒就好，畫質不變；起點會落在前一個關鍵格）' if (ENG.cfg.get('cut_mode') or 'copy') == 'copy' else '重新壓縮（精準，比較慢）'
        hows = {'': '', '前10碼': '（原檔名是亂碼、解不出來，只取前 10 碼）'}.get(how, f'（原檔名是 {how} 編碼，已經解開）')
        sep_txt = n_sep[0] + (f'、{n_sep[1]}' if len(n_sep) > 1 else '') + ('…' if len(n_sep) > 2 else '')
        mb = QMessageBox(self); mb.setWindowTitle('輸出初剪'); mb.setIcon(QMessageBox.Question)
        mb.setText(f'{len(segs)} 段，共 {fmt_t(sum(b - a for a, b in segs))}\n方式：{mode}\n存到：{od}\n\n'
                   f'分段：{sep_txt}\n不分段（合併成一個檔）：{n_all[0]}\n{hows}\n\n原檔不會動。剪好之後可以按「🗑 刪除原檔」。')
        inv = invert_segs(segs, float(self.cur.get('dur') or self.grid.dur or 0)) if lab_cfg().get('inverse_cut') else None
        if inv is not None:
            mb.setInformativeText(f'🧪 反過來剪（勾下面）：選的 {len(segs)} 段當成「不要的」刪掉，保留其他 {len(inv)} 段，共 {fmt_t(sum(b - a for a, b in inv))}。')
            cb = QCheckBox('反過來：刪掉選的片段，保留其他部分'); mb.setCheckBox(cb)
        b1 = mb.addButton(f'每段一個檔（_01…）', QMessageBox.AcceptRole); b2 = mb.addButton('不分段，合併成一個（_ALL）', QMessageBox.AcceptRole); mb.addButton('取消', QMessageBox.RejectRole)
        mb.setDefaultButton(b2 if ENG.cfg.get('cut_merge') else b1); mb.exec(); c = mb.clickedButton(); inv_on = inv is not None and mb.checkBox() is not None and mb.checkBox().isChecked(); mb.deleteLater()
        if c not in (b1, b2): return
        if inv_on:
            if not inv: self.win.msg('反過來剪之後什麼都不剩（選的就是整部）'); return
            ENG.log.w(f'反過來剪：選的 {len(segs)} 段刪掉，保留 {len(inv)} 段'); segs = inv
        merge = c is b2; ENG.cfg.set('cut_merge', merge); self.win.jobs_new(1 if merge else len(segs))
        fid = self.cur['id']; self.grid.clear_sel(); self._cut_watch = time.time() + 10
        bg(lambda: ENG.cut_add(fid, segs, merge=merge), lambda r: self.win.msg(r['message'] + '（後台看進度）'))

    def start_review(self):
        """🗂 分級：只看未分級、專注模式（預覽格子佔滿、S A E F 分級、PgUp／PgDn 換部）."""
        self._review = True; self._chip('nograde')
        if not self.focus_on: self.set_focus_mode(True)
        self.win.msg('🗂 分級：只看還沒分級的；按 S／A／E／F 分級、PgDn 下一部、Esc 離開', 8000)

    def set_focus_mode(self, on):
        """🧪 專注分級：收起左邊清單和選單，只留預覽格子＋上一部／下一部＋大分級鍵."""
        self.focus_on = bool(on); self.left_w.setVisible(not on); self.win.side_frame.setVisible(not on); self.fbar.setVisible(on)
        for sc in getattr(self, 'focus_scs', []): sc.setEnabled(self.focus_on)
        if not on and getattr(self, '_review', False): self._review = False; self.win.nav.setCurrentRow(0)
        self.b_focus.setText('⛶ 離開專注' if on else '⛶ 專注'); self._focus_pos(); ENG.log.w('畫面：' + ('進入' if on else '離開') + '專注分級')
        if on: self.grid.setFocus()

    def _focus_pos(self):
        r = self.lst.currentRow(); self.fpos.setText(f'第 {r + 1:,} / {self.lst.count():,} 部' if r >= 0 else '')

    def step_item(self, d):
        r = self.lst.currentRow() + d
        if 0 <= r < self.lst.count(): self.lst.setCurrentRow(r); self.lst.scrollToItem(self.lst.item(r)); self._focus_pos()
        else: self.win.msg('已經是第一部了' if d < 0 else '已經是最後一部了')

    def seg_preview(self):
        if not self.cur: return
        segs = self.grid.seg_times()
        if not segs: self.win.msg('先在格子上選片段'); return
        p = Player(self, self.cur['path'], segs[0][0], self.cur['name'], fps=self.cur.get('fps') or 30, fid=self.cur['id'], segs=segs)
        p.setAttribute(Qt.WA_DeleteOnClose); p.show(); ENG.log.w(f'片段預覽：{self.cur["path"]}　{len(segs)} 段')

    def _graded_in_player(self, fid, g):
        self._upd_row(fid, grade=g); self.lst.viewport().update(); self.load_chips(); self.tree_relabel()
        if self.cur and self.cur['id'] == fid:
            self.cur['grade'] = g
            for kk, x in self.gb.items(): x.setChecked(kk == g)

    def goto_file(self, fid):
        """從浮窗「到這部」：清單選到那一部（不在目前清單就切到全部影片）."""
        if fid in self.item_of: self.lst.setCurrentItem(self.item_of[fid]); self.lst.scrollToItem(self.item_of[fid]); return
        self._want_id = fid; self.folder = ''; ENG.th_focus = ''; self.q.clear(); self.flt.setCurrentIndex(0); self.load_tree(); self.load_list()

    def del_orig(self):
        if not self.cur: return
        r = self.cur; fid = r['id']
        bg(lambda: ENG.cut_outputs(fid), lambda outs: self._del_ask(r, outs))

    def _del_ask(self, r, outs):
        if not self.cur or self.cur['id'] != r['id']: return
        if not outs: QMessageBox.warning(self, '刪除原檔', '找不到這部剪好的初剪檔（被搬走或刪掉了？）\n為了安全，不刪原檔。'); return
        if QMessageBox.question(self, '刪除原檔', f'刪除原檔：\n{r["path"]}\n\n會丟到資源回收筒，它的 2 秒預覽圖也一起刪。\n\n剪好的初剪檔永久保留（{len(outs)} 個）：\n' +
                                '\n'.join(outs[:6]) + ('\n…' if len(outs) > 6 else '')) != QMessageBox.Yes: return
        self._del_go(r, False)

    def _del_go(self, r, permanent):
        def done(res):
            if res.get('need_perm'):
                if QMessageBox.question(self, '刪除原檔', res['message'] + '。\n\n要直接刪除嗎？（直接刪除就救不回來了）') == QMessageBox.Yes: self._del_go(r, True)
                return
            self.win.msg(res['message'])
            if not res.get('ok'): QMessageBox.warning(self, '刪除原檔', res['message']); return
            if self.cur and self.cur['id'] == r['id']:
                self.cur = None; self.grid.set_video(None, []); self._en(False); self.b_del.hide(); self.wait.hide()
                self.h1.setText('🗑 已刪除：' + r['name']); self.h2.setText('初剪檔都還在初剪資料夾裡。')
            self.load_list(); self.load_tree()
        bg(lambda: ENG.delete_original(r['id'], permanent), done)

    def open_dir(self):
        if self.cur:
            if core.IS_WIN: subprocess.Popen(['explorer', '/select,', self.cur['path']], creationflags=core.NO_WINDOW)
            else: QDesktopServices.openUrl(QUrl.fromLocalFile(self.cur['folder']))

    def front(self):
        if self.cur: ENG.thumb_front(self.cur['id']); self.win.msg('這部的預覽圖排到最前面了（正在做的做完就輪到）'); self.b_front.hide()

    def hist_dlg(self, r):
        def show(H):
            try:
                d = QDialog(self); d.setWindowTitle(f"📜 {r['name']}"); d.resize(640, 480); v = QVBoxLayout(d); tb = QTextBrowser(); v.addWidget(tb, 1)
                tb.setHtml('<table cellpadding="4">' + ''.join(f"<tr><td style='white-space:nowrap;color:#8994a4'>{time.strftime('%Y/%m/%d %H:%M', time.localtime(h['t'])) if h['t'] else ''}</td><td><b>{html_esc(h['what'])}</b></td><td>{html_esc(h['detail'])}</td></tr>" for h in H) + '</table>' if H else '還沒有紀錄')
                b = QPushButton('關閉'); b.clicked.connect(d.accept); v.addWidget(b); d.exec(); d.deleteLater()
            except Exception: ENG.log.err('這部的紀錄')
        bg(lambda: ENG.file_history(r['id']), show)

    def play_list(self, rows):
        """V0.2.90 ▶ 連播：這幾部一部接一部播（播完自動下一部；按 ⏭ 跳下一部；Esc 關掉＝停止連播）."""
        R = [r for r in rows if r.get('path')][:500]
        if not R: return
        self._plq = R; self.win.msg(f'▶ 連播 {len(R)} 部（播完自動下一部；Esc＝停止）'); self._pl_next()

    def _pl_next(self):
        Q = getattr(self, '_plq', None) or []
        if not Q: return
        r = Q.pop(0)
        try:
            p = Player(self, r['path'], 0.0, f"▶ 連播：{r['name']}", fps=r.get('fps') or 30, fid=r['id']); p.pl_next = len(Q); p.graded.connect(self._graded_in_player)
            if Q:
                b_ = QPushButton('⏭ 下一部'); b_.setFocusPolicy(Qt.NoFocus); b_.clicked.connect(lambda: (setattr(p, '_ended', True), p.close()))
                try: p.layout().addWidget(b_)
                except Exception: pass
            p.finished.connect(lambda _r, p=p: QTimer.singleShot(300, self._pl_next) if getattr(p, '_ended', False) else setattr(self, '_plq', []))
            p.setAttribute(Qt.WA_DeleteOnClose); p.show()
        except Exception: ENG.log.err('連播')

    def play(self, t=0.0):
        if not self.cur: return
        p = Player(self, self.cur['path'], t, self.cur['name'], fps=self.cur.get('fps') or 30, fid=self.cur['id']); p.marks.connect(lambda a, b: self.grid.add_seg_t(a, b) if self.grid.n else None)
        p.graded.connect(self._graded_in_player)
        p.setAttribute(Qt.WA_DeleteOnClose); p.show()


# ============================================================ 轉檔
class FlowLayout(QLayout):
    """會自動換行的排法（按鈕、勾選框太多時往下排，不會把視窗撐寬）."""
    def __init__(self, parent=None, spacing=6):
        super().__init__(parent); self._items = []; self._sp = spacing
        try: self.setContentsMargins(0, 0, 0, 0)
        except Exception: pass

    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, i): return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i): return self._items.pop(i) if 0 <= i < len(self._items) else None
    def expandingDirections(self): return Qt.Orientation(0)
    def hasHeightForWidth(self): return True
    def heightForWidth(self, w): return self._do(QRect(0, 0, w, 0), True)
    def setGeometry(self, r): super().setGeometry(r); self._do(r, False)
    def sizeHint(self): return self.minimumSize()

    def minimumSize(self):
        sz = QSize(0, 0)
        for it in self._items: sz = sz.expandedTo(it.minimumSize())
        return sz + QSize(4, 4)

    def _do(self, r, test):
        x, y, lh = r.x(), r.y(), 0
        for it in self._items:
            hw = it.sizeHint(); nx = x + hw.width() + self._sp
            if nx - self._sp > r.right() and lh > 0: x = r.x(); y = y + lh + self._sp; nx = x + hw.width() + self._sp; lh = 0
            if not test: it.setGeometry(QRect(QPoint(x, y), hw))
            x = nx; lh = max(lh, hw.height())
        return y + lh - r.y()


def flow_row(widgets, spacing=6):
    """一排按鈕放進會換行的容器."""
    w = QWidget(); fl = FlowLayout(w, spacing)
    for x in widgets: fl.addWidget(x)
    return w


def shrinkable(lb, wrap=False):
    """長文字的標籤不要把視窗撐寬：寬度可以縮（文字太長就換行或被裁掉）."""
    try:
        lb.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred); lb.setMinimumWidth(40)
        if wrap: lb.setWordWrap(True)
    except Exception: pass
    return lb


def scroll_wrap(w):
    """分頁內容放進可以捲動的框：視窗可以拉窄，太窄就出現捲軸（不會被撐寬）."""
    sa = QScrollArea(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.NoFrame); sa.setWidget(w); return sa


CONV_SORTS = [('smart', '💡 最省空間優先（位元率高的先轉）'), ('size_desc', '檔案大 → 小'), ('size_asc', '檔案小 → 大'), ('name', '檔名'), ('folder', '資料夾'),
              ('dur_desc', '長度 長 → 短'), ('mtime_desc', '最新的先'), ('ext', '類型')]
CONV_KINDS = [('nonmp4', '非 MP4 → H.265 MP4'), ('h264', 'H.264 MP4 → H.265'), ('all', '兩種都要'), ('vs', '🏷 已轉過的（檔名有 _VS）再轉一次 → _V2S')]


def _ti(text, tip='', align=None, color=None, data=None):
    it = QTableWidgetItem(str(text)); it.setToolTip(str(tip or text))
    if align is not None: it.setTextAlignment(align)
    if color: it.setForeground(QColor(color))
    if data is not None: it.setData(Qt.UserRole, data)
    return it


def _table(headers, widths, stretch_last=True):
    t = QTableWidget(0, len(headers)); t.setHorizontalHeaderLabels(headers); t.verticalHeader().setVisible(False); t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers); t.setSelectionMode(QAbstractItemView.ExtendedSelection); t.setAlternatingRowColors(True)
    hh = t.horizontalHeader(); hh.setSectionResizeMode(QHeaderView.Interactive); hh.setStretchLastSection(stretch_last)
    for k, w in enumerate(widths): t.setColumnWidth(k, w)
    return t


class GoalCard(QFrame):
    """🎯 瘦身目標：開始時的總大小 → 一個月內減半；進度、每天要省多少、照目前速度幾天達標."""
    def __init__(self, win):
        super().__init__(); self.win = win; self.setObjectName('hero'); v = QVBoxLayout(self); v.setContentsMargins(12, 10, 12, 10); v.setSpacing(5)
        r = QHBoxLayout(); v.addLayout(r)
        self.t = QLabel('🎯 瘦身目標'); self.t.setStyleSheet('font-weight:900;font-size:15px;background:transparent'); r.addWidget(self.t, 1)
        self.b_set = QPushButton('目標設定…'); self.b_reset = QPushButton('↺ 從現在重新算'); r.addWidget(self.b_set); r.addWidget(self.b_reset)
        self.pb = QProgressBar(); self.pb.setRange(0, 1000); self.pb.setTextVisible(False); self.pb.setFixedHeight(12)
        self.pb.setStyleSheet('QProgressBar{background:%s;border-radius:6px}QProgressBar::chunk{background:#45d483;border-radius:6px}' % THEME['track']); v.addWidget(self.pb)
        self.nums = QLabel(''); self.nums.setTextFormat(Qt.RichText); self.nums.setWordWrap(True); self.nums.setStyleSheet('background:transparent'); v.addWidget(self.nums)
        self.tips = QLabel(''); self.tips.setObjectName('muted'); self.tips.setWordWrap(True); self.tips.setStyleSheet('background:transparent'); v.addWidget(self.tips)
        self.b_reset.clicked.connect(self._reset); self.b_set.clicked.connect(self._set)
        self.tm = QTimer(self); self.tm.timeout.connect(self.refresh); self.tm.start(30000); QTimer.singleShot(300, self.refresh)

    def refresh(self):
        if not self.isVisible() and getattr(self, '_got', False): return
        bg(ENG.goal_view, self._got_v)

    def _got_v(self, G):
        self._got = True; self.G = G
        self.t.setText(f"🎯 瘦身目標：{fmt_b(G['b0'])} → {fmt_b(G['target'])}（{G['days']} 天內，{time.strftime('%m/%d', time.localtime(G['t0']))} 開始）")
        self.pb.setValue(int(G['pct'] * 10))
        ok = G['eta_days'] is not None and G['eta_days'] <= G['left_days']; okc = '#45d483' if ok else '#ff4d6d'
        self.nums.setText(f"已經省 <b style='color:#45d483'>{fmt_b(G['saved'])}</b>（{G['pct']:.1f}%）　現在 <b>{fmt_b(G['cur'])}</b>" + (f"（含 DELETE 裡 {fmt_b(G['pend'])}）" if G['pend'] else '') +
                          f"　還要省 <b style='color:#f0ad4e'>{fmt_b(G['need'])}</b>　剩 <b>{G['left_days']:.1f}</b> 天　每天要省 <b>{fmt_b(G['need_day'])}</b>" +
                          (f"　最近每天省 <b>{fmt_b(G['pace'])}</b>" if G['pace'] else '') + (f"　預估 <b style='color:{okc}'>{G['eta_days']:.0f} 天</b>達標" if G['eta_days'] else '') +
                          (f"　轉檔已省 {fmt_b(G['conv_saved'])}" if G['conv_saved'] else ''))
        self.tips.setText('　'.join('💡 ' + x for x in G['tips']) if G['tips'] else ('🎉 達標了！' if G['need'] <= 0 else ''))

    def _reset(self):
        if QMessageBox.question(self, '瘦身目標', '從現在的總大小重新開始算（目標＝一半、30 天）？') == QMessageBox.Yes: bg(lambda: ENG.goal_view(reset=True), self._got_v)

    def _set(self):
        G = dict(ENG.cfg.get('shrink_goal') or {})
        d, ok = QInputDialog.getInt(self, '瘦身目標', '幾天內完成？', int(G.get('days') or 30), 1, 365)
        if not ok: return
        r, ok = QInputDialog.getInt(self, '瘦身目標', '縮到原本的幾 %？（50＝減半）', int(round(float(G.get('ratio') or 0.5) * 100)), 5, 95)
        if not ok: return
        G.update(days=int(d), ratio=int(r) / 100.0); ENG.cfg.set('shrink_goal', G); ENG.log.w(f'🎯 瘦身目標改成 {d} 天縮到 {r}%'); self.refresh()


HOW_N = {'full': '🎯 完整測試', 'lite': '🎯 少量確認', 'quick': '🎯 快速確認', 'trust': '🎯 直接套用', 'fixed': '固定', 'remux': '只換外殼'}


def how_txt(r):
    h = str(r.get('cv_how') or '')
    if not h: return ''
    redo = h.startswith('redo-'); h = h[5:] if redo else h
    return ('🔁 重轉・' if redo else '') + HOW_N.get(h, h) + (f"・CQ {r['cv_cq']}" if r.get('cv_cq') else '')


CAP_OPTS = [('自動：照原檔位元率封頂（轉完不會比原檔大，建議）', 'auto'), ('不封頂（只看畫質，可能變大）', 'off'), ('最多 2 Mbps', 2), ('最多 4 Mbps', 4), ('最多 6 Mbps', 6), ('最多 8 Mbps', 8), ('最多 12 Mbps', 12), ('最多 20 Mbps', 20), ('最多 40 Mbps', 40)]


def trial_html(T):
    P = T.get('params') or {}; ch = T.get('class'); ss = T.get('ssim') or 0
    sc = '#45d483' if ss >= 0.95 else ('#f0ad4e' if ss >= 0.90 else '#ff6577'); rt = T.get('ratio') or 0; rc = '#45d483' if rt < 0.85 else ('#f0ad4e' if rt < 1 else '#ff6577')
    s = (f"<b>{T['name']}</b>：試轉 {T['secs']:.0f} 秒（從 {fmt_t(T['at'])}，{T['enc']}，{T['w']}×{T['h']}）→ <b>{fmt_b(T['bytes'])}</b>、{T['kbps']:,} kbps（原檔影像約 {T['src_kbps']:,} kbps）<br>"
         f"推估整部轉完：<b style='color:{rc}'>{fmt_b(T['est'])}</b>（原檔 {fmt_b(T['osz'])} 的 <b style='color:{rc}'>{rt * 100:.0f}%</b>，"
         + (f"省 {fmt_b(T['osz'] - T['est'])}" if T['est'] < T['osz'] else f"<span style='color:#ff6577'>會變大 {fmt_b(T['est'] - T['osz'])}</span>") + '）')
    s += (f"　已照之前 {T['kn']} 次「試轉 vs 實際」校正 ×{T['k']:.2f}" if T.get('kn') else '　（還沒有試轉過又實際轉完的紀錄，先不校正；之後會越來越準）')
    if ch: s += f"<br>已經轉完的同類（{Path(T['src']).suffix}）{ch['n']} 部，實際平均變成 <b>{ch['ratio'] * 100:.0f}%</b>" + ('' if ch.get('new', 0) >= 3 else '（含舊版沒封頂轉的，僅供參考）') + f" → 照這個比例約 {fmt_b(T['osz'] * ch['ratio'])}"
    s += f"<br>畫質分數 SSIM <b style='color:{sc}'>{ss:.3f}</b>（0.98 以上肉眼看不出來、0.95 以上很好、0.90 以下明顯變差）　轉這 {T['secs']:.0f} 秒花 {T['elapsed']:.1f} 秒（{T['speed']:.1f} 倍速）→ 整部大約 {fmt_t(T['full_time'])}"
    s += f"<br>參數：畫質 {P.get('q')}" + (f"、縮成 {P.get('res')}p" if P.get('res') else '、原始解析度') + (f"、位元率上限 {P.get('cap', 0) / 1e6:.1f} Mbps" if P.get('cap') else '、不封頂')
    return s


class ConvStatsChart(QWidget):
    """V0.2.11 統計圖：左邊兩組長條（轉過的檔案／整個資料夾 的 before、after），右邊累積曲線（轉檔前 vs 轉檔後，照時間）."""
    def __init__(self):
        super().__init__(); self.S = None; self.setMinimumHeight(240)

    def set_data(self, S): self.S = S; self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); W, H = self.width(), self.height(); p.fillRect(0, 0, W, H, QColor('#11161c'))
        S = self.S; f = QFont(); f.setPixelSize(11); p.setFont(f)
        if not S or not S.get('n'):
            p.setPen(QColor('#8a96a8')); p.drawText(QRect(0, 0, W, H), Qt.AlignCenter, '這個資料夾還沒有轉好的檔案' if S else ''); p.end(); return
        cb, ca, fb, fa = S['conv_before'], S['conv_after'], S['folder_before'], S['folder_after']
        bw = min(380, W // 3); top = 24; bot = H - 34; hh = bot - top; mx = max(1, fb, cb)
        groups = [('轉過的檔案', cb, ca), ('整個資料夾', fb, fa)]; gw = bw // 2
        for gi, (nm, b, a) in enumerate(groups):
            x0 = 16 + gi * gw
            for k, (val, col, lab) in enumerate(((b, '#ff8a4d', 'before'), (a, '#45d483', 'after'))):
                h = int(hh * val / mx); R = QRect(x0 + 8 + k * (gw // 2 - 4), bot - h, gw // 2 - 14, h)
                p.setPen(Qt.NoPen); p.setBrush(QColor(col)); p.drawRoundedRect(R, 3, 3)
                p.setPen(QColor('#dfe5ee')); p.drawText(QRect(R.x() - 10, R.y() - 16, R.width() + 20, 14), Qt.AlignCenter, core.fmt_gb(val))
                p.setPen(QColor('#8a96a8')); p.drawText(QRect(R.x() - 6, bot + 2, R.width() + 12, 14), Qt.AlignCenter, lab)
            p.setPen(QColor('#dfe5ee')); p.drawText(QRect(x0, bot + 16, gw, 14), Qt.AlignCenter, nm + (f'（-{(1 - a / b) * 100:.1f}%）' if b else ''))
        C = S.get('cum') or []; X0 = 16 + bw + 24; X1 = W - 12; cw = X1 - X0
        p.setPen(QColor('#dfe5ee')); p.drawText(QRect(X0, 4, cw, 16), Qt.AlignLeft, '累積：轉檔前（橘） vs 轉檔後（綠），照轉檔時間')
        if len(C) >= 1 and cw > 80:
            t0, t1 = C[0][0], C[-1][0]; span = max(1.0, t1 - t0); my = max(1, C[-1][1])
            p.setPen(QPen(QColor('#2a3340'), 1)); p.drawLine(X0, bot, X1, bot); p.drawLine(X0, top, X0, bot)
            for k, col in ((1, '#ff8a4d'), (2, '#45d483')):
                path = QPainterPath(); path.moveTo(X0, bot)
                for c in C: path.lineTo(X0 + cw * (c[0] - t0) / span if len(C) > 1 else X0 + cw, bot - hh * c[k] / my)
                p.setPen(QPen(QColor(col), 2)); p.setBrush(Qt.NoBrush); p.drawPath(path)
            p.setPen(QColor('#8a96a8')); fmt = lambda t: time.strftime('%m-%d %H:%M', time.localtime(t))
            p.drawText(QRect(X0, bot + 2, 120, 14), Qt.AlignLeft, fmt(t0)); p.drawText(QRect(X1 - 120, bot + 2, 120, 14), Qt.AlignRight, fmt(t1))
            p.drawText(QRect(X0 + 4, top, 160, 14), Qt.AlignLeft, core.fmt_gb(my))
        p.end()


class ConvPage(QWidget):
    """🔁 轉檔工作區（V0.1.53）：選檔加入（非 MP4／H.264 → H.265、類型、大小、資料夾、排序）｜轉檔中｜轉檔完成（大小差異、自動驗證、抽檢、刪原檔）｜失敗／沒變小."""
    def __init__(self, win):
        super().__init__(); self.win = win; self.rows = []; self.vis = []; self.done_rows = []; self.ratio = (0.5, 0)
        v = QVBoxLayout(self); v.setContentsMargins(10, 8, 10, 8); v.setSpacing(6)
        self.goal = GoalCard(win); v.addWidget(self.goal); self.goal.hide(); self.goal.tm.stop(); self.goal.refresh = lambda *a: None        # V0.1.92 使用者不要瘦身目標：不顯示、不佔版面、也不在背景算
        self.tabs = QTabWidget(); v.addWidget(self.tabs, 1)
        self.tabs.addTab(scroll_wrap(self._tab_pick()), '➕ 選檔加入'); self.tabs.addTab(scroll_wrap(self._tab_run()), '⚙ 轉檔中'); self.tabs.addTab(scroll_wrap(self._tab_done()), '✔ 轉檔完成'); self.tabs.addTab(scroll_wrap(self._tab_fail()), '✖ 失敗／沒變小')
        self.tabs.insertTab(3, scroll_wrap(self._tab_stats()), '📊 統計')                 # V0.2.11 完成的右邊
        self.tabs.currentChanged.connect(lambda _i: self.refresh_tab())
        self.tm = QTimer(self); self.tm.timeout.connect(self.tick); self.tm.start(1500)
        self.fill_roots()

    # ---------- ➕ 選檔加入
    def _tab_pick(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(6, 8, 6, 6)
        self.kind_b = {}; W1 = [QLabel('要轉的')]
        for k, nm in CONV_KINDS:
            b = QPushButton(nm); b.setCheckable(True); b.setObjectName('pill'); b.clicked.connect(lambda _c=False, k=k: self._kind(k)); W1.append(b); self.kind_b[k] = b
        self.sort = QComboBox()
        for k, nm in CONV_SORTS: self.sort.addItem(nm, k)
        v.addWidget(flow_row(W1 + [QLabel('　排序'), self.sort]))
        g = QGroupBox('範圍（都不選＝全部）'); gl = QGridLayout(g); v.addWidget(g)
        self.ext_w = QWidget(); self.ext_l = FlowLayout(self.ext_w); self.ext_cb = {}
        gl.addWidget(QLabel('類型'), 0, 0); gl.addWidget(self.ext_w, 0, 1, 1, 5)
        self.smin = QSpinBox(); self.smax = QSpinBox()
        for sp in (self.smin, self.smax): sp.setRange(0, 999999); sp.setSuffix(' MB'); sp.setSpecialValueText('不限')
        gl.addWidget(QLabel('大小'), 1, 0); gl.addWidget(self.smin, 1, 1); gl.addWidget(QLabel('～'), 1, 2); gl.addWidget(self.smax, 1, 3)
        self.sz_hint = QLabel(''); self.sz_hint.setObjectName('muted'); gl.addWidget(self.sz_hint, 1, 4)          # V0.6.11 範圍內最大／最小檔
        self.fd_list = QListWidget(); self.fd_list.setMaximumHeight(64); self.b_fd = QPushButton('＋ 加資料夾…'); self.b_fd_tree = QPushButton('＋ 檔案總管目前的資料夾'); self.b_fd_rm = QPushButton('拿掉選的')
        gl.addWidget(QLabel('資料夾（含子資料夾）'), 2, 0); gl.addWidget(self.fd_list, 2, 1, 1, 3)
        fb = QVBoxLayout(); fb.addWidget(self.b_fd); fb.addWidget(self.b_fd_tree); fb.addWidget(self.b_fd_rm); gl.addLayout(fb, 2, 4)
        gq = QGroupBox('📏 數量與目標（照上面的排序，從第一部開始取）'); ql = QGridLayout(gq); v.addWidget(gq)   # V0.6.11
        self.q_n = QSpinBox(); self.q_n.setRange(0, 999999); self.q_n.setSuffix(' 部'); self.q_n.setSpecialValueText('全部'); self.q_n.setSingleStep(50)
        self.q_sl = QSlider(Qt.Horizontal); self.q_sl.setRange(0, 1)
        self.q_all = QPushButton('全部')
        ql.addWidget(QLabel('數量'), 0, 0); ql.addWidget(self.q_n, 0, 1); ql.addWidget(self.q_sl, 0, 2); ql.addWidget(self.q_all, 0, 3)
        self.q_t = QDoubleSpinBox(); self.q_t.setRange(0, 999999); self.q_t.setDecimals(0); self.q_t.setSingleStep(50); self.q_t.setSuffix(' GB'); self.q_t.setSpecialValueText('不設')
        self.q_t.setToolTip('想省多少空間：設了之後「數量」會自動算（範圍、類型、排序變了也會跟著重算）；自己改數量就變回手動')
        self.q_tt = QLabel(''); self.q_tt.setObjectName('muted')
        ql.addWidget(QLabel('目標省'), 1, 0); ql.addWidget(self.q_t, 1, 1); ql.addWidget(self.q_tt, 1, 2, 1, 2)
        self.q_info = QLabel(''); self.q_info.setWordWrap(True); self.q_info.setTextFormat(Qt.RichText); ql.addWidget(self.q_info, 2, 0, 1, 4)
        self.cnt = shrinkable(QLabel(''), True); self.cnt.setObjectName('muted'); v.addWidget(self.cnt)
        self.b_ref = QPushButton('🔄 重新整理'); self.b_add_sel = QPushButton('加入選取的'); self.b_add_all = QPushButton('▶ 範圍內全部加入轉檔'); self.b_add_all.setObjectName('start')
        v.addWidget(flow_row([self.b_ref, self.b_add_sel, self.b_add_all]))
        self.tb = _table(['檔名', '資料夾', '類型', '編碼', '解析度', '長度', '大小', '預估省', '狀態'], (300, 260, 55, 70, 90, 70, 80, 80))
        self.tb.setContextMenuPolicy(Qt.CustomContextMenu); self.tb.customContextMenuRequested.connect(self._menu); self.tb.doubleClicked.connect(lambda ix: self._play_row(self.vis[ix.row()]) if 0 <= ix.row() < len(self.vis) else None)
        v.addWidget(self.tb, 1)
        k0 = ENG.cfg.get('cv_kind') or 'nonmp4'; self.kind = k0 if k0 in dict(CONV_KINDS) else 'nonmp4'
        for k, b in self.kind_b.items(): b.setChecked(k == self.kind)
        i = self.sort.findData(ENG.cfg.get('cv_sort') or 'smart'); self.sort.setCurrentIndex(max(0, i))
        sm = ENG.cfg.get('cv_range') or {}
        self.smin.setValue(int(sm.get('smin') or 0)); self.smax.setValue(int(sm.get('smax') or 0))
        for f in sm.get('folders') or []: self.fd_list.addItem(str(f))
        self._ext_sel = set(sm.get('exts') or [])
        self.sort.currentIndexChanged.connect(lambda _i: (ENG.cfg.set('cv_sort', self.sort.currentData()), self.load()))
        for sp in (self.smin, self.smax): sp.editingFinished.connect(lambda: (self._save_range(), self.load()))
        self.b_fd.clicked.connect(self.pick_dir); self.b_fd_tree.clicked.connect(self._fd_from_tree); self.b_fd_rm.clicked.connect(self._fd_rm)
        self.b_ref.clicked.connect(self.load); self.b_add_all.clicked.connect(self.go_all); self.b_add_sel.clicked.connect(self.go)
        self.q_n.setValue(int(ENG.cfg.get('cv_n') or 0)); self.q_t.setValue(float(ENG.cfg.get('cv_target_gb') or 0)); self.plan = None; self._qbusy = False
        self.q_dt = QTimer(self); self.q_dt.setSingleShot(True); self.q_dt.timeout.connect(self._plan_load)
        self.q_n.valueChanged.connect(lambda v_: self._q_set_n(v_)); self.q_sl.valueChanged.connect(lambda v_: self._q_set_n(v_, True))
        self.q_all.clicked.connect(lambda: (self.q_t.setValue(0), self.q_n.setValue(0)))
        self.q_t.valueChanged.connect(self._q_set_t)
        if not ENG.cfg.get('v0611_sort'):                                          # V0.6.11 使用者要「從最大的開始轉」：預設改成大 → 小，排隊中的也照大小重排一次
            ENG.cfg.set('v0611_sort', 1); ENG.cfg.set('cv_sort', 'size_desc'); i_ = self.sort.findData('size_desc'); self.sort.blockSignals(True); self.sort.setCurrentIndex(max(0, i_)); self.sort.blockSignals(False)
            bg(lambda: ENG.conv_reorder('size_desc'), lambda n_: None)
        return w

    # ---------- 📏 數量與目標（V0.6.11）
    def _q_set_n(self, v_, from_slider=False):
        if self._qbusy: return
        self._qbusy = True
        try:
            if from_slider: self.q_n.setValue(int(v_))
            else: self.q_sl.setValue(int(v_) or self.q_sl.maximum())
            if self.q_t.value(): self.q_t.setValue(0)                            # 自己改數量 → 目標變手動
        finally: self._qbusy = False
        ENG.cfg.set('cv_n', int(self.q_n.value())); ENG.cfg.set('cv_target_gb', float(self.q_t.value())); self.q_dt.start(250)

    def _q_set_t(self, v_):
        if self._qbusy: return
        ENG.cfg.set('cv_target_gb', float(v_)); self.q_tt.setText(f'＝{v_ / 1000:.2f} TB' if v_ >= 1000 else ''); self.q_dt.start(250)

    def _plan_args(self):
        R = self._range(); return (R['exts'], R['smin'], R['smax'], R['folders'], self.sort.currentData() or 'size_desc', self.kind, int(self.q_n.value()), float(self.q_t.value()))

    def _plan_load(self):
        A_ = self._plan_args(); bg(lambda: ENG.conv_plan(*A_), self._plan_show)

    def _plan_show(self, P):
        self.plan = P; N = int(P.get('n_all') or 0)
        self.sz_hint.setText(f"範圍內：最小 {fmt_b(P['min_all'])}、最大 {fmt_b(P['max_all'])}" if N else '範圍內沒有檔')
        self._qbusy = True
        try:
            self.q_sl.setRange(0, max(1, N))
            if P.get('auto'): self.q_n.setValue(int(P['n']))                    # 照目標自動帶入數量（浮動）
            self.q_sl.setValue(int(self.q_n.value()) or max(1, N))
        finally: self._qbusy = False
        if P.get('auto'): ENG.cfg.set('cv_n', int(P['n']))
        n = int(P.get('n') or 0); t_ = float(P.get('target_gb') or 0)
        h = (f"前 <b>{n:,}</b> 部（共 {N:,} 部）：大小 <b>{fmt_b(P['sel_max'])} ～ {fmt_b(P['sel_min'])}</b>・合計 {fmt_b(P['sel_bytes'])} → 預估省 <b style='color:#45d483'>{fmt_b(P['sel_save'])}</b>"
             if N else '範圍內沒有可以轉的檔')
        if t_ and N:
            h += (f"<br>🎯 目標省 {fmt_b(t_ * 1e9)}：大約要轉 <b>{n:,}</b> 部（已自動帶入數量，範圍改了會跟著重算）" if P.get('reach') else
                  f"<br><span style='color:#f0ad4e'>🎯 目標省 {fmt_b(t_ * 1e9)}：範圍內全部轉完也只能省大約 {fmt_b(P['save_all'])}（放寬大小、類型、資料夾試試）</span>")
        if N: h += f"<br><span style='color:#8994a4'>全部 {N:,} 部轉完預估省 {fmt_b(P['save_all'])}</span>"
        self.q_info.setText(h)
        self.b_add_all.setText(f'▶ 加入前 {n:,} 部轉檔' if N and n < N else '▶ 範圍內全部加入轉檔')

    def _kind(self, k):
        self.kind = k; ENG.cfg.set('cv_kind', k)
        for kk, b in self.kind_b.items(): b.setChecked(kk == k)
        self._ext_sel = set(); self._save_range(); self.load()

    def use_folder(self, path, kind='all', add=False):
        """V0.6.19 從 🗺 檔案總覽 跳過來：範圍＝這個資料夾（含子資料夾）、種類＝選的那種、回到「➕ 選檔加入」.
        V0.6.28 path 可以是好幾個；add＝True 加到原本的範圍（kind=None 不改種類）."""
        L = [str(x) for x in (path if isinstance(path, (list, tuple)) else [path]) if x]
        if not add: self.fd_list.clear()
        have = {self.fd_list.item(i).text().lower() for i in range(self.fd_list.count())}
        for x in L:
            if x.lower() not in have: self.fd_list.addItem(x); have.add(x.lower())
        self._ext_sel = set()
        if kind is None: kind = self.kind
        self.kind = kind; ENG.cfg.set('cv_kind', kind)
        for kk, b in self.kind_b.items(): b.setChecked(kk == kind)
        try: self.tabs.setCurrentIndex(0)
        except Exception: pass
        self._save_range(); self.load()

    def _range(self):
        return dict(exts=sorted(self._ext_sel), smin=self.smin.value(), smax=self.smax.value(), folders=[self.fd_list.item(i).text() for i in range(self.fd_list.count())])

    def _save_range(self): ENG.cfg.set('cv_range', self._range())

    def fill_roots(self): pass                                                  # 舊版的範圍下拉選單（留著給別的地方呼叫）

    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, '選要轉檔的資料夾（含子資料夾）')
        if not d: return
        d = os.path.normpath(d)
        if not ENG.root_of(d):
            if QMessageBox.question(self, '加入影片庫', f'{d}\n不在影片庫裡，要先加入並掃描嗎？') != QMessageBox.Yes: return
            ENG.cfg.set('roots', list(ENG.cfg.get('roots') or []) + [d]); ENG.scan([d])
        self.fd_list.addItem(d); self._save_range(); self.load()

    def _fd_from_tree(self):
        d = getattr(self.win.browse, 'folder', '') or ''
        if not d: self.win.msg('檔案總管現在是「全部」，先在左邊點一個資料夾'); return
        self.fd_list.addItem(d); self._save_range(); self.load()

    def _fd_rm(self):
        for it in self.fd_list.selectedItems(): self.fd_list.takeItem(self.fd_list.row(it))
        if not self.fd_list.selectedItems() and self.fd_list.count() and not self.fd_list.currentItem(): pass
        self._save_range(); self.load()

    def load(self):
        R = self._range(); k = self.kind; srt = self.sort.currentData() or 'smart'; self.cnt.setText('讀取中…')
        def work():
            c = ENG.conv_candidates(R['exts'], R['smin'], R['smax'], R['folders'], srt, (0, 4, 5), 5000, k)
            allx = ENG.conv_candidates(None, R['smin'], R['smax'], R['folders'], srt, (0, 4, 5), 0, k)        # 類型勾選框的數字（不受類型影響）
            ex = {}
            w_, a_ = ENG.conv_where(None, R['smin'], R['smax'], R['folders'], (0, 4, 5), k)
            for e, n, b in ENG.db.q(f'SELECT ext, COUNT(*), SUM(size) FROM files WHERE {w_} GROUP BY ext ORDER BY 3 DESC', a_): ex[e] = (n, b or 0)
            c['exts'] = ex; c['ratio'] = ENG.conv_ratio()
            try: c['plan'] = ENG.conv_plan(*A_)
            except Exception: c['plan'] = None
            return c
        A_ = self._plan_args(); bg(work, self._loaded)

    def _loaded(self, c):
        self.rows = c['rows']; self.vis = self.rows; self.ratio = c.get('ratio') or (0.5, 0); ratio = self.ratio[0] if self.ratio[1] else 0.5
        while self.ext_l.count():
            it = self.ext_l.takeAt(0); w_ = it.widget()
            if w_ is not None: w_.setParent(None); w_.deleteLater()
        self.ext_cb = {}
        for e, (n, b) in (c.get('exts') or {}).items():
            cb = QCheckBox(f'{e[1:]}（{n:,}・{fmt_b(b)}）'); cb.setChecked(e in self._ext_sel); cb.toggled.connect(lambda on, e=e: self._ext_tog(e, on)); self.ext_l.addWidget(cb); self.ext_cb[e] = cb
        R = self.rows; self.tb.setRowCount(len(R))
        def row(i):
            r = R[i]; er = r.get('est_ratio', ratio); est = int((r['size'] or 0) * (1 - er))
            vals = (r['name'], r['folder'], r['ext'][1:], r['vcodec'] or '?', f"{r['w']}×{r['h']}" if r['w'] else '?', fmt_t(r['dur']) if r['dur'] else '?', fmt_b(r['size']), '約 ' + fmt_b(est), self._st(r))
            for j, val in enumerate(vals):
                tp = r.get('path') if j <= 1 else ((f"照同類 {r['est_n']} 次經驗：轉完約原檔的 {er * 100:.0f}%" if r.get('est_n') else f'還沒有同類經驗，先用全部平均 {er * 100:.0f}% 估') if j == 7 else val)
                self.tb.setItem(i, j, _ti(val, tp, Qt.AlignRight | Qt.AlignVCenter if j in (6, 7) else None, ('#45d483' if r.get('est_n') else '#8fd8a8') if j == 7 else None))
        chunked(self, 'conv', len(R), row, 600, self.tb)
        sv = c.get('est_save', c['bytes'] * (1 - ratio))
        self.cnt.setText(f"範圍內 {c['n']:,} 部 · {fmt_b(c['bytes'])} · {fmt_t(c['dur'])} → 轉完預估省 <b>{fmt_b(sv)}</b>" +
                         (f"（{c.get('est_hit', 0):,} 部照📈同類經驗估，其他照已轉好的 {self.ratio[1]} 部平均 {ratio * 100:.0f}%）" if self.ratio[1] else '（還沒轉過，先用 50% 估）') + (f'　清單只列前 {len(R):,} 部' if c['n'] > len(R) else '') +
                         (f"<br><span style='color:#f0ad4e'>🏷 另外有 {c['vs_n']:,} 部檔名有 _VS（已經轉過），沒有列在這裡；真的要再轉，種類選「🏷 已轉過的」</span>" if c.get('vs_n') else '') + (f"<br><span style='color:#ff9f43'>ℹ {c['why']}</span>" if c.get('why') else ''))
        self.cnt.setTextFormat(Qt.RichText)
        if c.get('plan'): self._plan_show(c['plan'])

    def _ext_tog(self, e, on):
        (self._ext_sel.add if on else self._ext_sel.discard)(e); self._save_range(); self.load()

    def _st(self, r):
        s = int(r.get('cv_state') or 0)
        return {0: '', 1: '⏳ 排隊', 2: '⚙ 轉檔中', 3: '✔ 完成', 4: '✖ 失敗：' + str(r.get('cv_err') or '')[:60], 5: '取消', 6: '沒變小（保留原檔）'}.get(s, '')

    def _sel_rows(self, t, L):
        return [L[i] for i in sorted({ix.row() for ix in t.selectedIndexes()}) if 0 <= i < len(L)]

    def checked(self): return [r['id'] for r in self._sel_rows(self.tb, self.vis)]

    def check(self, fn):
        self.tb.clearSelection()
        for i, r in enumerate(self.vis):
            if fn(r): self.tb.selectRow(i)


    def go(self):
        ids = self.checked()
        if not ids: self.win.msg('先在清單選幾部（Ctrl／Shift 多選），或按「範圍內全部加入」'); return
        bg(lambda: ENG.conv_add(ids), lambda n: (self.win.msg(f'已排入 {n} 部（到「⚙ 轉檔中」看進度）'), self.load()))

    def go_all(self):
        R = self._range(); k = self.kind; srt = self.sort.currentData() or 'smart'
        P_ = self.plan or {}; lim = int(P_.get('n') or 0) if P_.get('n_all') and int(P_.get('n') or 0) < int(P_.get('n_all') or 0) else 0
        n = lim or int(P_.get('n_all') or len(self.rows)); after = {'delete_dir': '原檔先搬到該硬碟最外層的 DELETE 資料夾（抽檢沒問題再刪）', 'keep': '原檔留著不動', 'orig': '原檔搬到 VideoSIFT\\原檔備份', 'recycle': '原檔丟資源回收筒'}.get(ENG.cfg.get('cv_after') or 'delete_dir', '')
        if QMessageBox.question(self, '加入轉檔', (f'把範圍內前 {n:,} 部（最大的先）' if lim else f'把範圍內的影片（{n:,} 部）') + f'照「{self.sort.currentText()}」的順序加入轉檔？\n\n轉成 H.265 MP4，放在原本的資料夾；預覽圖、分級、人物都沿用。\n轉好後：{after}\n每部轉好會自動檢查長度和畫質。') != QMessageBox.Yes: return
        bg(lambda: ENG.conv_add_filtered(R['exts'], R['smin'], R['smax'], R['folders'], srt, k, lim), lambda n_: (self.win.msg(f'已排入 {n_:,} 部（到「⚙ 轉檔中」看進度）'), self.load(), self.tabs.setCurrentIndex(1)))

    def _menu(self, pos):
        R = self._sel_rows(self.tb, self.vis)
        if not R and self.tb.rowAt(pos.y()) >= 0 and self.tb.rowAt(pos.y()) < len(self.vis): R = [self.vis[self.tb.rowAt(pos.y())]]
        if not R: return
        m = QMenu(self); one = R[0]
        m.addAction('▶ 播放', lambda: self._play_row(one)); m.addAction('📂 在 Windows 檔案總管顯示', lambda: core.explorer_select(one.get('path') or ''))
        m.addAction(f'➕ 加入轉檔（{len(R)}）', lambda: bg(lambda: ENG.conv_add([r['id'] for r in R]), lambda n: (self.win.msg(f'已排入 {n} 部'), self.load())))
        m.exec(self.tb.viewport().mapToGlobal(pos)); m.deleteLater()

    def _play_row(self, r):
        if not r: return
        path = r.get('path') or (ENG.file(r['id']) or {}).get('path')
        p_ = Player(self.win, path, 0, r.get('name') or Path(path).name, fid=r['id']); p_.setAttribute(Qt.WA_DeleteOnClose); p_.show()


    # ---------- ⚙ 轉檔中
    def _tab_run(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(6, 8, 6, 6)
        g = QGroupBox('轉檔設定（改了馬上存，下一部開始用）'); gl = QGridLayout(g)               # V0.1.93 收進「⚙ 轉檔設定」浮窗，主畫面只留一行摘要
        self.enc = QComboBox()
        for a, b in (('自動（顯示卡能用就用顯示卡）', 'auto'), ('🎮 顯示卡 NVENC', 'gpu'), ('🧠 CPU x265（慢，品質穩）', 'cpu')): self.enc.addItem(a, b)
        self.qual = QComboBox()
        for a, b in (('接近無損（檔案大）', 17), ('接近原畫質（建議）', 19), ('高畫質', 21), ('平衡', 23), ('省空間', 26)): self.qual.addItem(a, b)
        self.n = QSpinBox(); self.n.setRange(1, 8); self.n.setSuffix(' 部同時（全部）')
        self.npd = QSpinBox(); self.npd.setRange(1, 8); self.npd.setPrefix('同一顆 HDD／外接 '); self.npd.setSuffix(' 部')
        self.npd.setToolTip('V0.1.91 起：同一顆傳統硬碟或 USB 外接硬碟同時轉幾部。好幾部一起讀寫會把 USB 外接硬碟壓到斷線（重插沒用、要重開機）；SSD 不受這個限制；那顆硬碟很閒（忙碌 < 35%）、6 小時內沒斷線時會自動多開一部，最多 3 部')
        self.after = QComboBox()
        for a, b in (('畫質到目標（量過的）原檔直接刪；0.975～目標的搬到該硬碟 DELETE 等你確認', 'auto_del'), ('原檔先搬到該硬碟最外層的 DELETE 資料夾（全部都要自己確認）', 'delete_dir'), ('原檔搬到 VideoSIFT\\原檔備份', 'orig'), ('原檔丟到資源回收筒', 'recycle')): self.after.addItem(a, b)
        self.verify = QCheckBox('固定方式：每部轉好自動驗證畫質（抽 5 個地方和原檔比；偏低會標 ⚠ 要你抽檢）')
        self.verify.setToolTip('🎯 自動方式不用這個：轉之前已經用 5 段樣本比過畫質，轉完直接用那個分數，不再整部重比')
        self.res = QComboBox()
        for k, nm in ENG.RES_OPTS: self.res.addItem(nm if k else '原始解析度（不縮）', k)
        self.cap = QComboBox()
        for a, b in CAP_OPTS: self.cap.addItem(a, b)
        self.mode = QComboBox()
        for a, b in (('🎯 自動：每一部先試 5 段，找肉眼看不出差別的最省設定（建議）', 'target'), ('固定：照上面的「畫質」', 'fixed')): self.mode.addItem(a, b)
        self.tgt = QSpinBox(); self.tgt.setRange(950, 999); self.tgt.setPrefix('目標 SSIM ≥ 0.'); self.tgt.setValue(int(round(float(ENG.cfg.get('cv_target') or 0.985) * 1000)))
        self.tgt.setToolTip(SSIM_TIP)
        gl.addWidget(QLabel('壓縮'), 0, 0); gl.addWidget(self.enc, 0, 1); gl.addWidget(QLabel('畫質'), 0, 2); gl.addWidget(self.qual, 0, 3); gl.addWidget(QLabel('同時'), 0, 4); gl.addWidget(flow_row([self.n, self.npd]), 0, 5)
        gl.addWidget(QLabel('解析度'), 1, 0); gl.addWidget(self.res, 1, 1); gl.addWidget(QLabel('位元率上限'), 1, 2); gl.addWidget(self.cap, 1, 3, 1, 3)
        gl.addWidget(QLabel('轉好後'), 2, 0); gl.addWidget(self.after, 2, 1, 1, 3); gl.addWidget(self.verify, 2, 4, 1, 2)
        gl.addWidget(QLabel('轉檔方式'), 4, 0); gl.addWidget(self.mode, 4, 1, 1, 3); gl.addWidget(self.tgt, 4, 4, 1, 2)
        self.lsum = QPushButton('📈 滾動式參數：讀取中…'); self.lsum.setObjectName('pill'); self.lsum.setToolTip('點一下看每一類的經驗、用哪種方式、抽查結果'); self.lsum.clicked.connect(lambda: self.win.nav.setCurrentRow(14))
        self.gpu = QLabel('顯示卡檢查中…'); self.gpu.setWordWrap(True); self.b_gpu = QPushButton('🔄 重新檢查顯示卡'); self.b_gd = QPushButton('詳細')
        gl.addWidget(self.gpu, 3, 0, 1, 4); gl.addWidget(self.b_gpu, 3, 4); gl.addWidget(self.b_gd, 3, 5)
        tb_ = self._trial_box()
        def mk_dlg(title, body):
            d = QDialog(self); d.setWindowTitle(title); d.resize(1000, 10); dl = QVBoxLayout(d); dl.addWidget(body)
            bx = QPushButton('關閉'); bx.clicked.connect(d.close); dl.addWidget(flow_row([bx])); return d
        self.set_dlg = mk_dlg('⚙ 轉檔設定', g); self.trial_dlg = mk_dlg('🧪 參考畫質：試轉 10 秒', tb_)
        self.b_set = QPushButton('⚙ 轉檔設定'); self.b_trial = QPushButton('🧪 試轉 10 秒')
        self.b_set.setToolTip('壓縮方式、畫質、同時幾部、解析度、位元率上限、轉好後原檔去哪、自動／固定方式、顯示卡狀態'); self.b_trial.setToolTip('先試轉 10 秒看效果、推估整部轉完多大')
        for b_ in (self.b_set, self.b_trial, self.lsum): b_.setObjectName('pill')
        self.b_set.clicked.connect(lambda: (self.set_dlg.show(), self.set_dlg.raise_(), self.set_dlg.activateWindow()))
        self.b_trial.clicked.connect(lambda: (self.trial_dlg.show(), self.trial_dlg.raise_(), self.trial_dlg.activateWindow()))
        self.set_sum = shrinkable(QLabel('')); self.set_sum.setObjectName('muted')
        v.addWidget(flow_row([self.b_set, self.b_trial, self.lsum, self.set_sum]))
        self.sum_t = QTimer(self); self.sum_t.timeout.connect(self._set_sum); self.sum_t.start(3000); QTimer.singleShot(500, self._set_sum)
        self.b_pause = QPushButton('⏸ 暫停轉檔'); self.b_pause.setCheckable(True); self.rsort = QComboBox()
        for k, nm in CONV_SORTS: self.rsort.addItem(nm, k)
        self.rsort.setCurrentIndex(max(0, self.rsort.findData('size_desc')))          # V0.6.13 重新排序預設：大 → 小
        self.b_resort = QPushButton('排隊重新排序'); self.b_rm = QPushButton('從排隊拿掉選取的'); self.b_cancel = QPushButton('✖ 全部取消'); self.b_cancel.setStyleSheet('QPushButton{color:#ff6577}')
        self.qsum = QLabel(''); self.qsum.setObjectName('muted')
        self.qeta = QLabel(''); self.qeta.setTextFormat(Qt.RichText); self.qeta.setWordWrap(True)
        v.addWidget(flow_row([self.b_pause, self.rsort, self.b_resort, self.b_rm, self.b_cancel])); qr_ = QHBoxLayout(); qr_.setContentsMargins(0, 0, 0, 0); qr_.addWidget(self.qsum, 0); qr_.addWidget(self.qeta, 1); v.addLayout(qr_)     # V0.1.99 同一行，預估吃剩下的寬度（以前放在 FlowLayout 裡被擠成一條直的）
        lt = QLabel('正在轉的'); lt.setStyleSheet('font-weight:800;background:transparent'); v.addWidget(lt)
        self.at = _table(['檔名', '方式', '速度', '還要', '進度', ''], (330, 130, 70, 70, 260, 50)); self.at.setSelectionMode(QAbstractItemView.NoSelection)
        self.at.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch); self.at.horizontalHeader().setStretchLastSection(False); self.at.setMaximumHeight(150); v.addWidget(self.at)
        self.act_ids = []; self.bars = {}
        self.qt = _table(['#', '檔名', '資料夾', '類型', '編碼', '長度', '大小', '狀態'], (40, 300, 260, 55, 70, 70, 80)); v.addWidget(self.qt, 1); self.qrows = []
        self.qt.doubleClicked.connect(lambda ix: self._play_row(self.qrows[ix.row()]) if 0 <= ix.row() < len(self.qrows) else None)
        self._load_cfg()
        self.enc.currentIndexChanged.connect(lambda _i: ENG.cfg.set('cv_enc', self.enc.currentData())); self.qual.currentIndexChanged.connect(lambda _i: ENG.cfg.set('cv_q', int(self.qual.currentData())))
        self.mode.currentIndexChanged.connect(lambda _i: (ENG.cfg.set('cv_mode', self.mode.currentData()), self.qual.setEnabled(self.mode.currentData() != 'target')))
        self.tgt.valueChanged.connect(lambda x: ENG.cfg.set('cv_target', round(x / 1000, 3))); self.qual.setEnabled((ENG.cfg.get('cv_mode') or 'target') != 'target')
        self.res.currentIndexChanged.connect(lambda _i: ENG.cfg.set('cv_res', int(self.res.currentData() or 0))); self.cap.currentIndexChanged.connect(lambda _i: ENG.cfg.set('cv_cap', self.cap.currentData()))
        self.n.valueChanged.connect(lambda x: ENG.cfg.set('cv_n', int(x))); self.npd.valueChanged.connect(lambda x: ENG.cfg.set('cv_per_disk', int(x))); self.after.currentIndexChanged.connect(self._after); self.verify.toggled.connect(lambda on: ENG.cfg.set('cv_verify', bool(on)))
        self.b_gpu.clicked.connect(lambda: (self.gpu.setText('檢查中…'), bg(lambda: ENG.gpu_check(True), lambda _r: self.tick())))
        self.b_gd.clicked.connect(lambda: QMessageBox.information(self, '顯示卡檢查', ENG.gpu_st.get('diag') or '還沒檢查'))
        self.b_pause.toggled.connect(self._pause); self.b_resort.clicked.connect(lambda: bg(lambda: ENG.conv_reorder(self.rsort.currentData()), lambda n: (self.win.msg(f'排隊 {n} 部重新排序'), self.load_queue())))
        self.b_rm.clicked.connect(lambda: self._rm_q()); self.b_cancel.clicked.connect(self.cancel)
        return w

    def _tag_vs(self):
        def got(r):
            n = r.get('n', 0)
            if not n: self.win.msg('🏷 轉好的檔名都已經有 _VS 了'); return
            if QMessageBox.question(self, '加上 _VS', f'把 {n:,} 部轉好的 MP4 檔名後面加上 _VS？\n例如 abc.mp4 → abc_VS.mp4\n\n（只改檔名、不動內容；每一筆都記在「操作紀錄」，可以改回。硬碟離線的會跳過）') != QMessageBox.Yes: return
            self.win.msg('🏷 改名中…', 8000)
            bg(ENG.conv_tag_vs, lambda r2: (self.win.msg('🏷 ' + r2['message'], 12000), self.load_done()))
        bg(lambda: ENG.conv_tag_vs(dry=True), got)

    def _set_sum(self):
        """主畫面一行摘要（詳細設定在「⚙ 轉檔設定」浮窗）."""
        try:
            if not self.isVisible(): return
            c = ENG.cfg; tgt = (c.get('cv_mode') or 'target') == 'target'
            enc = {'auto': '自動', 'gpu': '顯示卡', 'cpu': 'CPU'}.get(c.get('cv_enc') or 'auto', '自動')
            gp = '🎮 顯示卡 OK' if ENG.gpu_st.get('ok') else ('顯示卡檢查中' if not ENG.gpu_st.get('checked') else '⚠ 顯示卡不能用')
            t = '　·　'.join([f'{enc}（{gp}）', f"🎯 自動 SSIM ≥ {float(c.get('cv_target') or 0.985):.3f}" if tgt else '固定畫質',
                             f"{int(c.get('cv_n') or 3)} 部同時、同一顆 HDD／外接 {max(1, int(c.get('cv_per_disk') or 1))} 部",
                             {'auto_del': '到目標的原檔直接刪、其他→DELETE', 'delete_dir': '原檔→該硬碟 DELETE', 'orig': '原檔→原檔備份', 'recycle': '原檔→資源回收筒'}.get(c.get('cv_after') or 'delete_dir', '')])
            if self.set_sum.text() != t: self.set_sum.setText(t)
        except Exception: pass

    # ---------- 🧪 參考畫質：試轉 10 秒
    def _trial_box(self):
        g = QGroupBox('🧪 參考畫質：先用最短時間試轉 10 秒看效果、推估整部轉完多大（照已經轉完的檔校正）'); gl = QGridLayout(g)
        self.t_file = QComboBox(); self.t_file.setMinimumWidth(260); self.t_file.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon); self.b_tfill = QPushButton('🔄')
        self.b_tfill.setToolTip('重新列出：排隊中的、選檔清單裡的'); self.t_q = QComboBox(); self.t_res = QComboBox(); self.t_cap = QComboBox(); self.t_at = QSpinBox(); self.t_at.setRange(0, 95); self.t_at.setSuffix(' %'); self.t_at.setValue(40)
        for a, b in (('接近無損', 17), ('接近原畫質', 19), ('高畫質', 21), ('平衡', 23), ('省空間', 26), ('很省（28）', 28), ('最省（30）', 30)): self.t_q.addItem(a, b)
        for k, nm in ENG.RES_OPTS: self.t_res.addItem(nm, k)
        for a, b in CAP_OPTS: self.t_cap.addItem(a, b)
        self.b_trial = QPushButton('▶ 試轉 10 秒'); self.b_trial.setObjectName('start'); self.b_tcmp = QPushButton('🆚 原檔 vs 試轉 並排看'); self.b_tapply = QPushButton('✔ 這組套用到轉檔設定')
        self.b_tcmp.setEnabled(False); self.b_tapply.setEnabled(False)
        gl.addWidget(QLabel('拿哪部試'), 0, 0); gl.addWidget(self.t_file, 0, 1, 1, 4); gl.addWidget(self.b_tfill, 0, 5)
        gl.addWidget(QLabel('畫質'), 1, 0); gl.addWidget(self.t_q, 1, 1); gl.addWidget(QLabel('解析度'), 1, 2); gl.addWidget(self.t_res, 1, 3); gl.addWidget(QLabel('從片子'), 1, 4); gl.addWidget(self.t_at, 1, 5)
        gl.addWidget(QLabel('位元率上限'), 2, 0); gl.addWidget(self.t_cap, 2, 1, 1, 3)
        gl.addWidget(flow_row([self.b_trial, self.b_tcmp, self.b_tapply]), 3, 0, 1, 6)
        self.t_out = QLabel('選一部、調參數，按「▶ 試轉 10 秒」：會告訴你這組參數轉完整部大概多大、省多少、畫質分數、要轉多久；再按「🆚」原檔和試轉的同一段並排看（有放大鏡）。')
        self.t_out.setWordWrap(True); self.t_out.setTextFormat(Qt.RichText); self.t_out.setObjectName('muted'); gl.addWidget(self.t_out, 4, 0, 1, 6)
        self.trial = None; self.b_tfill.clicked.connect(self._tfill); self.b_trial.clicked.connect(self._trial); self.b_tcmp.clicked.connect(self._tcmp); self.b_tapply.clicked.connect(self._tapply)
        self._tsync(); QTimer.singleShot(1500, self._tfill)
        return g

    def _tsync(self):
        for w, k, dv in ((self.t_q, 'cv_q', 19), (self.t_res, 'cv_res', 0), (self.t_cap, 'cv_cap', 'auto')):
            i = w.findData(ENG.cfg.get(k) if ENG.cfg.get(k) is not None else dv); w.setCurrentIndex(max(0, i))

    def _tfill(self):
        def work():
            R = [dict(r) for r in ENG.db.q("SELECT id,name,size,dur,vcodec,w,h FROM files WHERE cv_state IN (1,2) AND missing=0 ORDER BY cv_state DESC, cv_q LIMIT 30")]
            have = {r['id'] for r in R}
            R += [r for r in (self.rows or [])[:40] if r['id'] not in have]; return R
        def got(R):
            cur = self.t_file.currentData(); self.t_file.clear()
            for r in R: self.t_file.addItem(f"{r['name']}（{fmt_b(r['size'])}・{r.get('vcodec') or '?'} {r.get('w') or '?'}×{r.get('h') or '?'}）", r['id'])
            i = self.t_file.findData(cur); self.t_file.setCurrentIndex(max(0, i))
            if not R: self.t_file.addItem('（排隊和選檔清單都是空的：先到「➕ 選檔加入」列出來）', None)
        bg(work, got)

    def _tparams(self): return {'q': int(self.t_q.currentData()), 'res': int(self.t_res.currentData() or 0), 'cap': self.t_cap.currentData()}

    def _trial(self):
        fid = self.t_file.currentData()
        if not fid: self.win.msg('先選一部要試的'); return
        Pm = self._tparams(); self.b_trial.setEnabled(False); self.b_trial.setText('⏳ 試轉中…'); self.t_out.setText('試轉中：轉 10 秒＋和原檔比畫質，通常幾秒到半分鐘…')
        r = ENG.file(int(fid)) or {}; at = (float(r.get('dur') or 0) * self.t_at.value() / 100) if r.get('dur') else None
        def done(res):
            try: self.b_trial.setEnabled(True); self.b_trial.setText('▶ 試轉 10 秒')
            except RuntimeError: return
            if isinstance(res, Exception) or not isinstance(res, dict): self.t_out.setText(f"<span style='color:#ff6577'>✖ 試轉失敗：{res}</span>"); return
            self.trial = res; self.b_tcmp.setEnabled(True); self.b_tapply.setEnabled(True); self.t_out.setText(trial_html(res))
        def work():
            try: return ENG.conv_trial(int(fid), Pm, at)
            except Exception as ex: ENG.log.w(f'試轉失敗：{ex}'); return ex
        bg(work, done, err=done)

    def _tcmp(self):
        T = self.trial
        if not T: return
        d = PlayCompareDlg(self.win, T['src'], T['out'], '原檔', '試轉', 0.0, a_off=T['at'], b_off=0.0, title=f"試轉比較：{T['name']}（從 {fmt_t(T['at'])} 起 {T['secs']:.0f} 秒）")
        d.setAttribute(Qt.WA_DeleteOnClose); d.show()

    def _tapply(self):
        Pm = self._tparams()
        for w, k, val in ((self.qual, 'cv_q', Pm['q']), (self.res, 'cv_res', Pm['res']), (self.cap, 'cv_cap', Pm['cap'])):
            i = w.findData(val)
            if i < 0 and w is self.qual: w.addItem(f'畫質 {val}', val); i = w.findData(val)
            w.setCurrentIndex(max(0, i)); ENG.cfg.set(k, val)
        self.win.msg('✔ 這組參數套用到轉檔設定（下一部開始用）'); ENG.log.w(f'轉檔設定：套用試轉參數 {Pm}')

    def _load_cfg(self):
        for w, k in ((self.enc, 'cv_enc'), (self.qual, 'cv_q'), (self.after, 'cv_after'), (self.res, 'cv_res'), (self.cap, 'cv_cap'), (self.mode, 'cv_mode')):
            i = w.findData(ENG.cfg.get(k) if ENG.cfg.get(k) is not None else {'cv_res': 0, 'cv_cap': 'auto', 'cv_mode': 'target'}.get(k)); w.setCurrentIndex(max(0, i))
        self.n.setValue(int(ENG.cfg.get('cv_n') or 3)); self.npd.setValue(max(1, int(ENG.cfg.get('cv_per_disk') or 1))); self.verify.setChecked(ENG.cfg.get('cv_verify') is not False)

    def _after(self, _i):
        k = self.after.currentData()
        if k == 'recycle' and QMessageBox.question(self, '轉好後', '轉好、檢查過沒問題之後，原檔丟到資源回收筒？（外接硬碟可能沒有回收筒＝直接刪）') != QMessageBox.Yes:
            self.after.setCurrentIndex(0); return
        ENG.cfg.set('cv_after', k)

    def _pause(self, on):
        ENG.cv_paused = bool(on); self.b_pause.setText('▶ 繼續轉檔' if on else '⏸ 暫停轉檔'); self.win.msg('轉檔暫停（正在轉的轉完就停）' if on else '轉檔繼續')

    def _rm_q(self):
        ids = [r['id'] for r in self._sel_rows(self.qt, self.qrows)]
        if ids: bg(lambda: ENG.conv_cancel(ids), lambda _n: self.load_queue())

    def cancel(self):
        if QMessageBox.question(self, '取消', '取消全部排隊中的轉檔（正在轉的也停掉）？') != QMessageBox.Yes: return
        bg(lambda: ENG.conv_cancel(None), lambda _n: self.load_queue())

    def load_queue(self): bg(ENG.conv_queue, self._queue); bg(ENG.conv_eta, self._eta)

    def _eta(self, E_):
        try:
            if E_.get('eta'):
                self.qeta.setText(f"⏱ 全部大約還要 <b>{eta_txt(E_['eta'])}</b>（{time.strftime('%m-%d %H:%M', time.localtime(E_['done_at']))} 左右轉完，保守估）"); self.qeta.setToolTip(f"排隊 {E_['n']:,} 部、{fmt_t(E_['left_s'])} 的影片\n{E_['basis']}")
            else: self.qeta.setText(f"⏱ {E_.get('basis', '')}" if E_.get('n') else '')
        except RuntimeError: pass

    def _queue(self, R):
        self.qrows = R; self.qt.setRowCount(len(R))
        for i, r in enumerate(R):
            st = (f"⚙ {r.get('pct', 0)}% · {r.get('enc', '')} {r.get('speed', '')}" + (f" · 還要 {fmt_t(r['left'])}" if r.get('left') else '')) if r['cv_state'] == 2 else '⏳ 排隊'
            if r.get('cv_redo'): st = '🔁 重轉（原檔在 DELETE）　' + st
            for j, val in enumerate((i + 1, r['name'], r['folder'], r['ext'][1:], r['vcodec'] or '?', fmt_t(r['dur']) if r['dur'] else '?', fmt_b(r['size']), st)):
                it = self.qt.item(i, j)
                if it is None or it.text() != str(val): self.qt.setItem(i, j, _ti(val))
        tb = sum(r['size'] or 0 for r in R); td = sum(r['dur'] or 0 for r in R)
        self.qsum.setText(f'排隊 {len(R):,} 部 · {fmt_b(tb)} · {fmt_t(td)} 的影片')

    # ---------- ✔ 轉檔完成
    def _tab_done(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(6, 8, 6, 6)
        self.dsum = shrinkable(QLabel(''), True); self.dsum.setTextFormat(Qt.RichText); v.addWidget(self.dsum)
        self.dflt = QComboBox()
        for a, b in (('全部', 'all'), ('原檔還在 DELETE（等你刪）', 'pend'), ('原檔還在原位（選去留）', 'here'), ('⚠ 轉完變大', 'big'), ('⚠ 畫質沒到目標／沒驗證', 'warn'), ('還沒抽檢的', 'unseen')): self.dflt.addItem(a, b)
        self.dq = QLineEdit(); self.dq.setPlaceholderText('🔍 找檔名'); self.dq.setClearButtonEnabled(True)
        self.b_dplay = QPushButton('▶ 播放（雙擊也可以）'); self.b_rand = QPushButton('🎲 隨機抽 5 部抽檢'); self.b_ddir = QPushButton('📂 開資料夾'); self.b_rest = QPushButton('↩ 原檔搬回')
        self.b_cmp = QPushButton('🆚 原檔／轉好的 並排比較'); self.b_cmp.setObjectName('start'); self.b_keepmp4 = QPushButton('✔ 留 MP4（原檔搬到 DELETE）'); self.b_keeporig = QPushButton('↩ 留原檔（刪掉 MP4）')
        self.b_force = QPushButton('🎯 選取的重轉到 0.985（插隊）'); self.b_force.setToolTip('例如自動驗證 1.000（之前只換了外殼、沒重壓）的：用 DELETE 裡的原檔，一定整部重壓到目標畫質，排到隊伍最前面')
        self.b_force.clicked.connect(lambda: self._redo([r['id'] for r in self._sel_rows(self.dt, self.done_rows)], True))
        self.b_redo = QPushButton('🔁 選取的用新方式重轉'); self.b_redoall = QPushButton('🔁 沒到目標的全部重轉（原檔留 DELETE）'); self.b_redoall.setObjectName('start')
        for b_ in (self.b_redo, self.b_redoall): b_.setToolTip('用 DELETE 裡的原檔、🎯 自動方式重轉：畫質分數達到目標（預設 0.985）才換掉舊的 MP4，沒達到就留著舊的；原檔一直留在 DELETE，等你自己刪')
        self.b_rv = QPushButton('🔍 沒到目標的重新驗證畫質'); self.b_rv.setToolTip('先用修正後的方法重新算一次畫質分數（之前 .ts 這類算錯的很多其實沒問題），算完還沒到目標的再重轉；不會動到任何檔案')
        self.b_lowall = QPushButton('↩ 畫質沒到目標的全部還原'); self.b_lowall.setStyleSheet('QPushButton{color:#f0ad4e;font-weight:800}')
        self.b_lowall.setToolTip('畫質分數低於目標（預設 0.985，轉檔設定可以改）或沒驗證過的：刪掉轉好的 MP4、原檔從 DELETE 搬回原本的資料夾，之後可以用新設定重轉')
        self.b_bigall = QPushButton('↩ 變大的全部還原'); self.b_bigall.setStyleSheet('QPushButton{color:#ff6577;font-weight:800}'); self.b_stall = QPushButton('原位的全部留 MP4')
        self.b_pdel = QPushButton('🗑 刪除選取的原檔'); self.b_pall = QPushButton('🗑 刪除已轉檔完成的原檔'); self.b_pall.setStyleSheet('QPushButton{background:#c62845;color:#fff;border:0;border-radius:8px;padding:6px 12px;font-weight:800}')
        self.b_pdel.setStyleSheet('QPushButton{color:#ff6577;font-weight:700}')
        v.addWidget(flow_row([self.dflt, self.dq, self.b_cmp, self.b_dplay, self.b_rand, self.b_ddir]))
        v.addWidget(flow_row([self.b_rv, self.b_redoall, self.b_force, self.b_redo, self.b_lowall, self.b_bigall]))
        self.rvl = QLabel(''); self.rvl.setObjectName('muted'); v.addWidget(self.rvl)
        self.b_tag = QPushButton('🏷 轉好的全部加上 _VS'); self.b_tag.setToolTip('之前轉好的 MP4 檔名後面補上 _VS（例如 abc.mp4 → abc_VS.mp4），以後重新匯入一眼就知道轉過了；每一筆都記在操作紀錄，可以改回')
        self.b_tag.clicked.connect(self._tag_vs)
        v.addWidget(flow_row([self.b_keepmp4, self.b_keeporig, self.b_rest, self.b_stall, self.b_tag, self.b_pdel, self.b_pall]))
        self.dt = _table(['檔名', '轉檔前', '轉檔後', '省下', '比例', '自動驗證', '抽檢', '原檔', '完成時間', '位置', '方式／CQ'], (280, 85, 85, 85, 55, 95, 55, 120, 120, 260, 150))
        self.dt.doubleClicked.connect(lambda ix: self._dplay(ix.row())); v.addWidget(self.dt, 1)
        self.dt.setContextMenuPolicy(Qt.CustomContextMenu); self.dt.customContextMenuRequested.connect(self._dmenu)
        tip = QLabel('雙擊打開轉好的 MP4 抽檢（看過會打 ✔）；「🆚 並排比較」原檔和轉好的同時播、放大鏡看細節。原檔在該硬碟最外層的 DELETE 資料夾，抽檢沒問題再按「🗑 刪除已轉檔完成的原檔」。'
                     '原檔還在原位的（同一個資料夾有兩份）：選「✔ 留 MP4」或「↩ 留原檔」。轉完反而變大的：按「↩ 變大的全部還原」（刪掉轉大的、原檔搬回原位，之後可以用新設定重轉）。'); tip.setObjectName('muted'); tip.setWordWrap(True); v.addWidget(tip)
        self.dflt.currentIndexChanged.connect(lambda _i: self._dfill()); self.dq.textChanged.connect(lambda _t: self._dq_t.start(300))
        self._dq_t = QTimer(self); self._dq_t.setSingleShot(True); self._dq_t.timeout.connect(self.load_done)
        self.b_dplay.clicked.connect(lambda: self._dplay(self.dt.currentRow())); self.b_rand.clicked.connect(self._rand)
        self.b_ddir.clicked.connect(lambda: (lambda r: core.explorer_select(r['path']) if r else None)(self._dcur()))
        self.b_rest.clicked.connect(self._restore); self.b_pdel.clicked.connect(lambda: self._purge(True)); self.b_pall.clicked.connect(lambda: self._purge(False))
        self.b_cmp.clicked.connect(lambda: self._cmp(self._dcur())); self.b_keepmp4.clicked.connect(lambda: self._stage(self._sel_rows(self.dt, self.done_rows)))
        self.b_keeporig.clicked.connect(lambda: self._undo(self._sel_rows(self.dt, self.done_rows))); self.b_bigall.clicked.connect(self._undo_big); self.b_lowall.clicked.connect(self._undo_low); self.b_rv.clicked.connect(self._reverify); self.b_redo.clicked.connect(lambda: self._redo([r['id'] for r in self._sel_rows(self.dt, self.done_rows)])); self.b_redoall.clicked.connect(self._redo_low); self.b_stall.clicked.connect(self._stage_all)
        return w

    def _cmp(self, r):
        if not r: self.win.msg('先在清單點一部'); return
        if not r.get('orig'): self.win.msg('這部的原檔已經刪掉了，只能看轉好的（雙擊）'); return
        if not r['out_exists']: self.win.msg(('💤 硬碟離線，檔案沒有刪，接回來才能播：' if r.get('offline') else '轉好的檔不見了：') + r['path']); return
        d = PlayCompareDlg(self.win, r['orig'], r['path'], '原檔', '轉好的 H.265', max(0.0, (r['dur'] or 0) * 0.3), title='比較：' + r['name']); d.setAttribute(Qt.WA_DeleteOnClose); d.show()
        ENG.set_flags([r['id']], viewed=1); r['viewed'] = time.time(); self._dfill()

    def _dmenu(self, pos):
        R = self._sel_rows(self.dt, self.done_rows); i = self.dt.rowAt(pos.y())
        if not R and 0 <= i < len(self.done_rows): R = [self.done_rows[i]]
        if not R: return
        m = QMenu(self); one = R[0]; i0 = self.done_rows.index(one) if one in self.done_rows else -1
        m.addAction('🆚 原檔／轉好的 並排比較', lambda: self._cmp(one)); m.addAction('▶ 播放轉好的', lambda: self._dplay(i0) if 0 <= i0 < len(self.done_rows) and self.done_rows[i0]['id'] == one['id'] else self._dplay_row(one))
        if one.get('orig'): m.addAction('▶ 播放原檔', lambda: (lambda p_: (p_.setAttribute(Qt.WA_DeleteOnClose), p_.show()))(Player(self.win, one['orig'], max(0.0, (one['dur'] or 0) * 0.3), '原檔：' + Path(one['orig']).name)))
        m.addAction('📂 在 Windows 檔案總管顯示轉好的', lambda: core.explorer_select(one['path']))
        if one.get('orig'): m.addAction('📂 在 Windows 檔案總管顯示原檔', lambda: core.explorer_select(one['orig']))
        m.addSeparator()
        if any(r['src_exists'] and not r['del_exists'] for r in R): m.addAction('✔ 留 MP4（原檔搬到 DELETE）', lambda: self._stage(R))
        if any(r.get('orig') for r in R): m.addAction('↩ 留原檔（刪掉轉好的 MP4、原檔回原位）', lambda: self._undo(R))
        if any(r['del_exists'] for r in R): m.addAction('↩ 原檔搬回（兩個都留）', lambda: self._restore(R))
        m.exec(self.dt.viewport().mapToGlobal(pos)); m.deleteLater()

    def _stage(self, R):
        ids = [r['id'] for r in R if r['src_exists'] and not r['del_exists']]
        if not ids: self.win.msg('選幾部「原檔還在原位」的'); return
        bg(lambda: ENG.conv_stage(ids), lambda r: (self.win.msg(r['message'], 8000), self.load_done()), err=lambda ex: self.win.msg(f'✖ 沒搬成：{ex}'))

    def _stage_all(self):
        R = [r for r in getattr(self, 'done_all', []) if r['src_exists'] and not r['del_exists']]
        if not R: self.win.msg('沒有原檔還在原位的'); return
        if QMessageBox.question(self, '原位的全部留 MP4', f'{len(R)} 部的原檔還和 MP4 放在同一個資料夾。\n全部搬到該硬碟最外層的 DELETE（留 MP4）？\n\n搬過去還沒刪，抽檢後再到這裡按刪除。') != QMessageBox.Yes: return
        bg(lambda: ENG.conv_stage(None), lambda r: (self.win.msg(r['message'], 8000), self.load_done()), err=lambda ex: self.win.msg(f'✖ 沒搬成：{ex}'))

    def _undo(self, R):
        R = [r for r in R if r.get('orig')]
        if not R: self.win.msg('選幾部原檔還在的（在 DELETE 或原位）'); return
        b = sum(r['nsz'] for r in R)
        if QMessageBox.question(self, '留原檔', f'{len(R)} 部：刪掉轉好的 MP4（{fmt_b(b)}），原檔放回原本的位置？\n\n預覽圖、分級都照舊；之後可以用新設定重轉。') != QMessageBox.Yes: return
        ids = [r['id'] for r in R]; bg(lambda: ENG.conv_undo(ids), lambda r: (self.win.msg(r['message'], 10000), self.load_done(), self.goal.refresh()), err=lambda ex: self.win.msg(f'✖ 還原失敗：{ex}'))

    def _reverify(self):
        tg = float(ENG.cfg.get('cv_target') or 0.985)
        def got(ids):
            if not ids: self.win.msg(f'沒有畫質分數低於 {tg:.3f}、原檔還在的'); return
            bg(lambda: ENG.conv_reverify(ids), lambda r: self.win.msg(r['message'], 8000))
        bg(lambda: ENG.conv_below(tg), got)

    def _redo(self, ids, force=False):
        if not ids: self.win.msg('先選幾部（原檔要還在 DELETE）'); return
        tg = float(ENG.cfg.get('cv_target') or 0.985)
        if QMessageBox.question(self, '用新方式重轉', f'{len(ids)} 部用 DELETE 裡的原檔、🎯 自動方式重轉' + ('（一定整部重壓、插隊排第一）' if force else '') + f'？\n\n畫質分數達到 {tg:.3f} 才換掉舊的 MP4（沒達到就留著舊的）；原檔一直留在 DELETE，等你自己刪。') != QMessageBox.Yes: return
        bg(lambda: ENG.conv_redo(ids, force, force), lambda r: (self.win.msg(r['message'], 10000), self.load_done()), err=lambda ex: self.win.msg(f'✖ {ex}'))

    def _redo_low(self):
        tg = float(ENG.cfg.get('cv_target') or 0.985)
        def got(ids):
            ids = [i for i in ids if (ENG.file(i) or {}).get('cv_del') and os.path.exists((ENG.file(i) or {}).get('cv_del') or '')]
            if not ids: self.win.msg(f'沒有畫質分數低於 {tg:.3f}、原檔還在 DELETE 的'); return
            self._redo(ids)
        bg(lambda: ENG.conv_below(tg), got)

    def _undo_low(self):
        tg = float(ENG.cfg.get('cv_target') or 0.985)
        def got(ids):
            if not ids: self.win.msg(f'沒有畫質分數低於 {tg:.3f}、而且原檔還在的'); return
            qs = ','.join(str(int(i)) for i in ids)
            nv = int((ENG.db.one(f'SELECT COUNT(*) FROM files WHERE id IN ({qs}) AND (cv_ssim IS NULL OR cv_ssim=0)') or [0])[0]); b = int((ENG.db.one(f'SELECT SUM(size) FROM files WHERE id IN ({qs})') or [0])[0] or 0)
            if QMessageBox.question(self, '畫質沒到目標的全部還原', f'{len(ids)} 部畫質分數低於 {tg:.3f}' + (f'（其中 {nv} 部沒驗證過）' if nv else '') +
                                    f'。\n\n刪掉這些轉好的 MP4（{fmt_b(b)}），原檔從 DELETE 搬回原本的資料夾？\n預覽圖、分級都照舊；之後會出現在「選檔加入」，可以用 🎯 自動方式重轉。') != QMessageBox.Yes: return
            bg(lambda: ENG.conv_undo(ids), lambda r: (self.win.msg(r['message'], 10000), self.load_done(), self.goal.refresh()), err=lambda ex: self.win.msg(f'✖ 還原失敗：{ex}'))
        bg(lambda: ENG.conv_below(tg), got)

    def _undo_big(self):
        R = [r for r in getattr(self, 'done_all', []) if r['big'] and r.get('orig')]
        if not R: self.win.msg('沒有轉完變大、而且原檔還在的'); return
        extra = sum(r['nsz'] - r['osz'] for r in R)
        if QMessageBox.question(self, '變大的全部還原', f'{len(R)} 部轉完反而變大（多佔 {fmt_b(extra)}）。\n刪掉這些轉大的 MP4、原檔搬回原位？\n\n預覽圖、分級都照舊。新版轉檔會照原檔位元率封頂，重轉不會再變大。') != QMessageBox.Yes: return
        ids = [r['id'] for r in R]; bg(lambda: ENG.conv_undo(ids), lambda r: (self.win.msg(r['message'], 10000), self.load_done(), self.goal.refresh()), err=lambda ex: self.win.msg(f'✖ 還原失敗：{ex}'))

    def load_done(self): bg(lambda: ENG.conv_done_list(self.dq.text().strip()), self._done)

    def _done(self, D):
        self.D = D; self.done_all = D['rows']
        self.dsum.setText(f"完成 <b>{D['n']:,}</b> 部：轉檔前 {fmt_b(D['osz'])} → 轉檔後 {fmt_b(D['nsz'])}，省下 <b style='color:#45d483'>{fmt_b(max(0, D['osz'] - D['nsz']))}</b>" +
                          (f"（{D['nsz'] * 100 / D['osz']:.0f}%）" if D['osz'] else '') + (f"　｜　DELETE 裡還有 <b style='color:#f0ad4e'>{D['pending']:,}</b> 個原檔、{fmt_b(D['pending_bytes'])} 等你抽檢後刪除" + ('（' + '、'.join(f'{k}\\DELETE {v[0]:,} 個・{fmt_b(v[1])}' for k, v in (D.get('pending_by') or {}).items()) + '）' if D.get('pending_by') else '') if D['pending'] else '　｜　DELETE 裡沒有等著刪的原檔') +
                          (lambda T_, S_: f"<br>📅 今天轉好 <b>{T_['n']:,}</b> 部，省下 <b style='color:#45d483'>{fmt_b(T_['save'])}</b>"
                           + f"　｜　🔁 這次（{time.strftime('%m-%d %H:%M', time.localtime(S_['t0']))} 打開後）轉好 <b>{S_['n']:,}</b> 部，省下 <b style='color:#45d483'>{fmt_b(S_['save'])}</b>")(D.get('today') or {'n': 0, 'save': 0}, D.get('session') or {'n': 0, 'save': 0, 't0': time.time()}) +
                          (f"<br><span style='color:#f0ad4e'>💤 {'、'.join(D.get('offline_drives') or [])} 硬碟離線：{D.get('offline_n', 0):,} 部暫時讀不到（檔案沒有刪），接回來就恢復</span>" if D.get('offline_n') else ''))
        self.b_pall.setText(f"🗑 刪除已轉檔完成的原檔（{D['pending']:,} 個・{fmt_b(D['pending_bytes'])}）" if D['pending'] else '🗑 刪除已轉檔完成的原檔'); self.b_pall.setEnabled(bool(D['pending']))
        self.b_bigall.setText(f"↩ 變大的全部還原（{D.get('big', 0)} 部・多佔 {fmt_b(D.get('big_bytes', 0))}）" if D.get('big') else '↩ 變大的全部還原'); self.b_bigall.setEnabled(bool(D.get('big')))
        ns = sum(1 for r in D['rows'] if r['src_exists'] and not r['del_exists']); self.b_stall.setText(f'原位的全部留 MP4（{ns}）' if ns else '原位的全部留 MP4'); self.b_stall.setEnabled(bool(ns))
        if D.get('big'): self.dsum.setText(self.dsum.text() + f"<br><b style='color:#ff6577'>⚠ {D['big']} 部轉完反而變大（多佔 {fmt_b(D['big_bytes'])}）</b>：按「↩ 變大的全部還原」，這些的原檔不會被「刪除已轉檔完成的原檔」刪掉")
        self._dfill()

    def _dfill(self):
        f = self.dflt.currentData(); L = getattr(self, 'done_all', [])
        if f == 'pend': L = [r for r in L if r['del_exists']]
        elif f == 'warn': L = [r for r in L if not r['cv_ssim'] or r['cv_ssim'] < float(ENG.cfg.get('cv_target') or 0.985)]
        elif f == 'here': L = [r for r in L if r['src_exists'] and not r['del_exists']]
        elif f == 'big': L = [r for r in L if r['big']]
        elif f == 'unseen': L = [r for r in L if not (r['viewed'] and r['viewed'] >= (r['cv_t'] or 0))]
        self.done_rows = L; self.dt.setRowCount(len(L))
        for i, r in enumerate(L):
            ss = r['cv_ssim'] or 0; tg_ = float(ENG.cfg.get('cv_target') or 0.985); ver = (f'✔ {ss:.3f}' if ss >= tg_ else (f'⚠ {ss:.3f}' if ss else '— 沒驗證')); vc = '#45d483' if ss >= tg_ else '#f0ad4e'
            if str(r.get('cv_err') or '').startswith('重轉'): ver += '（' + str(r['cv_err'])[:40] + '）'
            if str(r.get('cv_how') or '').endswith('trust') and ss: ver = ver.replace(f'{ss:.3f}', f'≈{ss:.3f}（經驗估）')
            seen = bool(r['viewed'] and r['viewed'] >= (r['cv_t'] or 0))
            orig = '💤 硬碟離線（沒刪）' if r.get('offline') else (('在 DELETE（要還原）' if r['big'] else '在 DELETE（可刪）') if r['del_exists'] else ('已刪除' if not r['src_exists'] else '⚠ 還在原位（選去留）'))
            sv = (f"⚠ 變大 +{fmt_b(r['nsz'] - r['osz'])}" if r['big'] and r['nsz'] > r['osz'] else ('⚠ 差不多' if r['big'] else fmt_b(max(0, r['osz'] - r['nsz']))))
            vals = [(r['name'], r['path']), (fmt_b(r['osz']), ''), (fmt_b(r['nsz']), ''), (sv, ''), (f"{r['nsz'] * 100 / r['osz']:.0f}%" if r['osz'] else '', ''),
                    (ver, '自動驗證：從中間抽 5 秒和原檔比 SSIM（1＝一模一樣，0.95 以上肉眼看不出差別）'), ('✔' if seen else '', ''), (orig, r['cv_del'] or r['cv_src']),
                    (time.strftime('%m-%d %H:%M', time.localtime(r['cv_t'])) if r['cv_t'] else '', ''), (r['folder'], r['folder']), (how_txt(r), '')]
            for j, (val, tp) in enumerate(vals):
                self.dt.setItem(i, j, _ti(val, tp or val, Qt.AlignRight | Qt.AlignVCenter if j in (1, 2, 3, 4) else None,
                                         vc if j == 5 else (('#ff6577' if r['big'] else '#45d483') if j in (3, 4) and (r['big'] or j == 3) else ('#ff6577' if j == 7 and (r['big'] or not r['del_exists'] and r['src_exists']) else ('#f0ad4e' if j == 7 and r['del_exists'] else None)))))

    def _dcur(self):
        i = self.dt.currentRow(); return self.done_rows[i] if 0 <= i < len(self.done_rows) else None

    def _dplay_row(self, r):
        i = next((k for k, x in enumerate(self.done_rows) if x['id'] == r['id']), -1)
        if i >= 0: self._dplay(i)

    def _dplay(self, i):
        if not (0 <= i < len(self.done_rows)): return
        r = self.done_rows[i]
        if not r['out_exists']: self.win.msg(('💤 硬碟離線，檔案沒有刪，接回來才能播：' if r.get('offline') else '轉好的檔不見了：') + r['path']); return
        p_ = Player(self.win, r['path'], max(0.0, (r['dur'] or 0) * 0.3), '抽檢：' + r['name'], fid=r['id']); p_.setAttribute(Qt.WA_DeleteOnClose); p_.show()
        ENG.set_flags([r['id']], viewed=1); r['viewed'] = time.time(); self._dfill(); ENG.log.w(f'轉檔完成：抽檢 {r["path"]}')

    def _rand(self):
        L = [r for r in getattr(self, 'done_all', []) if r['del_exists'] and r['out_exists']] or [r for r in getattr(self, 'done_all', []) if r['out_exists']]
        if not L: self.win.msg('沒有可以抽檢的'); return
        pick = random.sample(L, min(5, len(L))); self.dflt.setCurrentIndex(0); self._dfill(); self.dt.clearSelection()
        ids = {r['id'] for r in pick}
        for i, r in enumerate(self.done_rows):
            if r['id'] in ids: self.dt.selectRow(i)
        first = next((i for i, r in enumerate(self.done_rows) if r['id'] == pick[0]['id']), -1); self._dplay(first)
        self.win.msg(f'🎲 抽了 {len(pick)} 部（已經選起來）：第一部開始播，其他的雙擊看')

    def _restore(self, R=None):
        ids = [r['id'] for r in (R if isinstance(R, list) else self._sel_rows(self.dt, self.done_rows)) if r['del_exists']]
        if not ids: self.win.msg('選幾部「原檔在 DELETE」的'); return
        if QMessageBox.question(self, '原檔搬回', f'把 {len(ids)} 個原檔從 DELETE 搬回原本的位置？（轉好的 MP4 留著）') != QMessageBox.Yes: return
        bg(lambda: ENG.conv_restore(ids), lambda r: (self.win.msg(r['message']), self.load_done()))

    def _purge(self, sel):
        R = [r for r in (self._sel_rows(self.dt, self.done_rows) if sel else getattr(self, 'done_all', [])) if r['del_exists']]
        if not R: self.win.msg('沒有在 DELETE 裡的原檔'); return
        b = sum(r['osz'] for r in R); warn = sum(1 for r in R if not r['cv_ssim'] or r['cv_ssim'] < 0.95); seen = sum(1 for r in R if r['viewed'] and r['viewed'] >= (r['cv_t'] or 0))
        msg = f'永久刪除 {len(R):,} 個已轉檔完成的原檔（{fmt_b(b)}）？\n\n你抽檢過 {seen} 部' + (f'；有 {warn} 部自動驗證偏低或沒驗證（建議先看）' if warn else '；全部自動驗證都通過 ✔') + '\n\n刪了就救不回來（轉好的 MP4 不會動）。'
        if QMessageBox.question(self, '刪除已轉檔完成的原檔', msg) != QMessageBox.Yes: return
        if len(R) > 20 and QMessageBox.question(self, '再確認一次', f'真的要刪 {len(R):,} 個原檔、{fmt_b(b)}？') != QMessageBox.Yes: return
        ids = [r['id'] for r in R]; bg(lambda: ENG.conv_purge(ids), lambda r: (self.win.msg('🗑 ' + r['message'], 10000), self.load_done(), self.goal.refresh()))

    # ---------- ✖ 失敗／沒變小
    # ---------- V0.2.11 📊 統計：指定資料夾的每一筆轉檔、before／after、圖表
    def _tab_stats(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(6, 8, 6, 6)
        self.st_fd = QComboBox(); self.st_fd.setEditable(True); self.st_fd.setMinimumWidth(320); self.st_fd.setToolTip('只算這個資料夾（含子資料夾）裡的；別的硬碟、別的資料夾不算')
        last = str(ENG.cfg.get('conv_stats_dir') or '')
        for r in ([last] if last else []) + [str(x) for x in ENG.cfg.get('roots') or [] if str(x) != last]: self.st_fd.addItem(r)
        b1 = QPushButton('📂 選資料夾'); b2 = QPushButton('🔄 重新統計')
        v.addWidget(flow_row([QLabel('資料夾'), self.st_fd, b1, b2]))
        self.st_sum = QLabel('選一個資料夾，按「🔄 重新統計」'); self.st_sum.setWordWrap(True); self.st_sum.setTextFormat(Qt.RichText); v.addWidget(self.st_sum)
        self.st_chart = ConvStatsChart(); v.addWidget(self.st_chart)
        self.st_t = _table(['檔名', '轉檔時間', '轉檔前', '轉檔後', '縮小', '變成', 'SSIM', '資料夾'], (260, 130, 80, 80, 80, 60, 60)); v.addWidget(self.st_t, 1); self.st_rows = []
        def pick():
            d = QFileDialog.getExistingDirectory(self, '選要統計的資料夾（含子資料夾）', self.st_fd.currentText())
            if d: self.st_fd.setEditText(os.path.normpath(d)); self.load_stats()
        b1.clicked.connect(pick); b2.clicked.connect(self.load_stats); self.st_fd.activated.connect(lambda _i: self.load_stats())
        return w

    def load_stats(self):
        fd = self.st_fd.currentText().strip()
        if not fd: return
        ENG.cfg.set('conv_stats_dir', fd); self.st_sum.setText('統計中…'); bg(lambda: ENG.conv_stats(fd), self._stats)

    def _stats(self, S):
        if not S or not S.get('ok'): self.st_sum.setText((S or {}).get('message') or '統計不出來'); return
        ts = lambda t: time.strftime('%Y-%m-%d %H:%M', time.localtime(t)) if t else '—'
        pc = lambda a, b: f'{(1 - b / a) * 100:.1f}%' if a else '—'
        cb, ca, fb, fa = S['conv_before'], S['conv_after'], S['folder_before'], S['folder_after']
        self.st_sum.setText(f"<b>{S['folder']}</b>（含子資料夾）<br>"
                            f"轉過的 <b>{S['n']:,}</b> 部：第一筆 {ts(S['first_t'])} → 最後一筆 {ts(S['last_t'])}　轉檔前 <b>{fmt_b(cb)}</b> → 轉檔後 <b>{fmt_b(ca)}</b>，"
                            f"縮小 <b style='color:#45d483'>{fmt_b(max(0, cb - ca))}</b>（少了 {pc(cb, ca)}）<br>"
                            f"整個資料夾（含沒轉的 {S['other_n']:,} 部・{fmt_b(S['other_bytes'])}）：第一筆轉之前 <b>{fmt_b(fb)}</b> → 現在 <b>{fmt_b(fa)}</b>，少了 {pc(fb, fa)}")
        self.st_chart.set_data(S)
        self.st_rows = S['rows']; t = self.st_t; t.setRowCount(0); t.setRowCount(len(self.st_rows))
        for i, r in enumerate(self.st_rows):
            o, n = int(r['cv_osz'] or 0), int(r['size'] or r['cv_nsz'] or 0)
            for j, val in enumerate([r['name'], ts(r['cv_t']), fmt_b(o), fmt_b(n), fmt_b(max(0, o - n)), f'{n * 100 / o:.0f}%' if o else '—', f"{float(r['cv_ssim'] or 0):.3f}" if r.get('cv_ssim') else '—', r['folder']]):
                t.setItem(i, j, QTableWidgetItem(str(val)))

    def _tab_fail(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(6, 8, 6, 6)
        r = QHBoxLayout(); v.addLayout(r); self.b_retry = QPushButton('↻ 選取的重試'); self.b_retry_all = QPushButton('↻ 失敗的全部重試'); self.fsum = QLabel(''); self.fsum.setObjectName('muted')
        shrinkable(self.fsum); r.addWidget(self.b_retry); r.addWidget(self.b_retry_all); r.addWidget(self.fsum, 1)
        self.ft = _table(['檔名', '資料夾', '大小', '結果', '原因'], (280, 260, 80, 120)); v.addWidget(self.ft, 1); self.frows = []
        self.ft.doubleClicked.connect(lambda ix: self._play_row(self.frows[ix.row()]) if 0 <= ix.row() < len(self.frows) else None)
        self.b_retry.clicked.connect(lambda: bg(lambda: ENG.conv_add([r['id'] for r in self._sel_rows(self.ft, self.frows)]), lambda n: (self.win.msg(f'{n} 部重新排隊'), self.load_fail())))
        self.b_retry_all.clicked.connect(lambda: bg(lambda: ENG.conv_add([r['id'] for r in self.frows if r['cv_state'] == 4]), lambda n: (self.win.msg(f'{n} 部重新排隊'), self.load_fail())))
        return w

    def load_fail(self): bg(lambda: [dict(r) for r in ENG.db.q('SELECT id,name,folder,path,size,cv_state,cv_err FROM files WHERE cv_state IN (4,6) AND missing=0 ORDER BY cv_t DESC, id DESC LIMIT 3000')], self._fail)

    def _fail(self, R):
        self.frows = R; self.ft.setRowCount(len(R))
        for i, r in enumerate(R):
            for j, val in enumerate((r['name'], r['folder'], fmt_b(r['size']), '✖ 失敗' if r['cv_state'] == 4 else '沒變小（保留原檔）', r['cv_err'] or '')):
                self.ft.setItem(i, j, _ti(val, r['path'] if j <= 1 else val, None, '#ff6577' if j == 3 and r['cv_state'] == 4 else None))
        self.fsum.setText(f"失敗 {sum(1 for r in R if r['cv_state'] == 4):,} 部 · 沒變小 {sum(1 for r in R if r['cv_state'] == 6):,} 部（已經很省空間了，原檔不動）")

    # ---------- 共用
    def refresh_tab(self):
        i = self.tabs.currentIndex()
        if i == 0: self.load()
        elif i == 1: self.load_queue()
        elif i == 2: self.load_done()
        elif i == 3: self.load_stats()
        elif i == 4: self.load_fail()

    def tick(self):
        g = ENG.gpu_st
        self.gpu.setText(('顯示卡檢查中…' if not g.get('checked') else ('🎮 ✔ 顯示卡可以壓縮（' + str(g.get('drv') or '') + '）' if g.get('ok') else '🧠 顯示卡不能用 → 會用 CPU 轉（按「詳細」看原因）')))
        if not self.isVisible(): return
        try:
            if self.b_pause.isChecked() != bool(ENG.cv_paused):                 # 後台總控制／手機改了：按鈕跟著變
                self.b_pause.blockSignals(True); self.b_pause.setChecked(bool(ENG.cv_paused)); self.b_pause.setText('▶ 繼續轉檔' if ENG.cv_paused else '⏸ 暫停轉檔'); self.b_pause.blockSignals(False)
        except Exception: pass
        act = dict(ENG.cv_active); ids = list(act)
        if ids != self.act_ids:                                                  # 正在轉的換了：整張表重排（進度條都對齊同一欄）
            self.act_ids = ids; self.at.setRowCount(len(ids)); self.bars = {}
            for r_, fid in enumerate(ids):
                pb = QProgressBar(); pb.setRange(0, 1000); pb.setFixedHeight(14); self.at.setCellWidget(r_, 4, pb)
                x = QPushButton('停'); x.clicked.connect(lambda _c=False, fid=fid: bg(lambda: ENG.conv_cancel([fid]))); self.at.setCellWidget(r_, 5, x); self.bars[fid] = (r_, pb)
            self.at.setMaximumHeight(34 + 30 * max(1, len(ids)))
        for fid, J in act.items():
            r_, pb = self.bars.get(fid, (None, None))
            if r_ is None: continue
            p_ = J.get('pct') or 0; pb.setValue(int(p_ * 10)); pb.setFormat(f'{p_}%'); pb.setTextVisible(True)
            for c_, val in enumerate((J.get('name') or '', J.get('enc') or '', J.get('speed') or '', fmt_t(J['left']) if J.get('left') else '')):
                it = self.at.item(r_, c_)
                if it is None or it.text() != str(val): self.at.setItem(r_, c_, _ti(val))
        if self.tabs.currentIndex() == 1:
            self._ln = getattr(self, '_ln', 0) + 1
            if self._ln % 5 == 1:
                def got_l(V):
                    try:
                        C = V['classes']; MN = {'full': '完整測試', 'lite': '少量確認', 'quick': '快速確認', 'trust': '直接套用'}; cnt = {}
                        for c in C: cnt[c['mode']] = cnt.get(c['mode'], 0) + 1
                        self.lsum.setText(f"📈 滾動式參數：經驗 {V['total']:,} 次、{len(C)} 類　" + '　'.join(f'{MN.get(k, k)} {n} 類' for k, n in cnt.items()) + '　（點這裡看）' if C else '📈 滾動式參數：還沒有經驗（🎯 自動方式轉檔就會開始累積；點這裡看）')
                    except RuntimeError: pass
                bg(ENG.learn_view, got_l)
        R = ENG.rv_st
        self.rvl.setText((f"🔍 重新驗證畫質：做完 {R['done']}／{R['n']}" + (f"，正在算 {R['cur']}" if R['cur'] else '') + ('' if R['run'] or R['q'] else '（做完了）')) if R['n'] else '')
        if self.tabs.currentIndex() == 2 and R.get('up') and R['up'] != getattr(self, '_rv_up', 0) and (not R['run'] or time.time() - getattr(self, '_rv_ld', 0) > 15):
            self._rv_up = R['up']; self._rv_ld = time.time(); self.load_done()          # 重新驗證中：最多 15 秒更新一次清單
        if self.tabs.currentIndex() == 1:
            self._qn = getattr(self, '_qn', 0) + 1
            if self._qn % 2 == 0: self.load_queue()


SSIM_TIP = ('SSIM＝畫質分數（結構相似度）：把轉出來的畫面和原檔同一格比，亮度、對比、紋理結構像不像。\n'
            '1.000＝一模一樣　0.99 以上＝幾乎分不出來　0.98 以上＝肉眼很難看出差別　0.95～0.98＝仔細看會發現一點糊　0.95 以下＝看得出變差\n'
            '這裡是抽 5 個地方各 2 秒、用短邊 1080 的大小比，取中間值；只是參考，最後用「並排比較」自己看')


# ============================================================ 🧪 碼率測試（V0.1.60，測試用）
class BrTestPage(QWidget):
    """選一個檔 → 同時用顯示卡轉成 100%／80%／60%／40%／20% 碼率的 H.265 MP4，比大小和畫質。介面不講究，之後可能刪掉."""
    def __init__(self, win):
        super().__init__(); self.win = win; self.st = None
        v = QVBoxLayout(self); v.setContentsMargins(10, 8, 10, 8)
        t = QLabel('🧪 碼率測試：選一個影片，一次轉成好幾種格式／碼率的 MP4（顯示卡的同時轉），列出預估大小、實際大小、畫質分數，⭐ 標出「肉眼看不出來裡面最小的」。'
                   '每轉一次，預估就用實際大小校正，越轉越準。原檔不會動。'); t.setWordWrap(True); v.addWidget(t)
        g = QGridLayout(); v.addLayout(g)
        self.src = QLineEdit(); self.src.setPlaceholderText('要測試的影片'); b1 = QPushButton('選檔案…')
        self.out = QLineEdit(); self.out.setPlaceholderText('輸出到哪個資料夾（空的＝和原檔同一個資料夾）'); b2 = QPushButton('選資料夾…')
        F = ENG.cfg.get('brt_fmt') or {}
        self.f = {}
        for r_, (k, dv, tip) in enumerate((('br', '100,80,60,40,20', '原檔影像位元率的幾 %'), ('cq', '24,28,32', '固定畫質：數字越大越省（建議從 28 開始看）'),
                                            ('hq', '28,32', '最慢最細的顯示卡設定（p7、兩階段、10-bit）：同畫質通常再省一些，速度大約慢一半'),
                                            ('av1nv', '', 'AV1：比 H.265 再省 20～30%，但要 RTX 40 系列（3060 不能用）；舊播放器可能放不了'))):
            cb = QCheckBox(ENG.BRT_KINDS[k]); e = QLineEdit(str(F.get(k, dv))); cb.setChecked(bool(F.get(k + '_on', k in ('br', 'cq', 'hq')))); cb.setToolTip(tip); e.setToolTip(tip + '　多個用逗號隔開')
            g.addWidget(cb, 3 + r_, 0, 1, 1); g.addWidget(e, 3 + r_, 1); g.addWidget(QLabel(tip), 3 + r_, 2); self.f[k] = (cb, e)
        self.ss = QCheckBox('轉完自動算畫質分數 SSIM（和原檔比，抽 5 個地方）'); self.ss.setChecked(True)
        self.thr = QSpinBox(); self.thr.setRange(900, 999); self.thr.setValue(int(F.get('thr', 985))); self.thr.setPrefix('肉眼看不出來＝SSIM ≥ 0.'); self.thr.setToolTip('⭐ 推薦＝畫質分數在這個以上、檔案最小的那個')
        g.addWidget(QLabel('影片'), 0, 0); g.addWidget(self.src, 0, 1); g.addWidget(b1, 0, 2)
        g.addWidget(QLabel('輸出'), 1, 0); g.addWidget(self.out, 1, 1); g.addWidget(b2, 1, 2)
        g.addWidget(self.ss, 2, 0, 1, 2); g.addWidget(self.thr, 2, 2)
        self.b_est = QPushButton('🔮 先看預估大小（不轉）'); self.b_tq = QPushButton('🎯 自動找這部最省的設定（SSIM ≥ 門檻）')
        self.b_tq.setToolTip('跟「轉檔」的自動模式一樣：從 10%／30%／50%／70%／90% 各取 2 秒，用顯示卡試不同 CQ，找畫質分數還在門檻以上、最省的那個')
        self.out.setText(ENG.cfg.get('brt_out') or '')
        self.b_go = QPushButton('▶ 開始（全部同時轉）'); self.b_go.setObjectName('start'); self.b_stop = QPushButton('⏹ 停止'); self.b_dir = QPushButton('📂 開輸出資料夾')
        self.b_cmp = QPushButton('🆚 選的那一列和原檔並排比較'); self.b_play = QPushButton('▶ 播放選的那一列')
        v.addWidget(flow_row([self.b_est, self.b_tq, self.b_go, self.b_stop, self.b_dir, self.b_cmp, self.b_play]))
        self.info = QLabel(''); self.info.setWordWrap(True); v.addWidget(self.info)
        self.det = QLabel('選了影片之後，這裡會列出原檔的詳細格式'); self.det.setWordWrap(True); self.det.setTextFormat(Qt.RichText); self.det.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.det.setStyleSheet('QLabel{background:rgba(127,127,127,0.08);border-radius:8px;padding:8px}'); v.addWidget(self.det)
        self.src.editingFinished.connect(self._detail)
        hist = QHBoxLayout(); v.addLayout(hist); self.hc = QComboBox(); self.hc.setMinimumWidth(420); self.b_hload = QPushButton('看這次的結果'); self.b_det2 = QPushButton('📋 選的那一列的詳細格式')
        hist.addWidget(QLabel('之前的紀錄')); hist.addWidget(self.hc, 1); hist.addWidget(self.b_hload); hist.addWidget(self.b_det2)
        self.tb = _table(['設定', '方式', '預估大小', '實際大小', '誤差', '原檔的', '整體位元率', '影像位元率', 'SSIM', '進度', '效率', '還要', '花多久', '狀態', '檔案'],
                         (190, 150, 90, 90, 60, 65, 90, 90, 70, 60, 60, 70, 65, 110, 300)); v.addWidget(self.tb, 1)
        try:
            hi = self.tb.horizontalHeaderItem(8)
            if hi is not None: hi.setToolTip(SSIM_TIP)
        except Exception: pass
        note = QLabel('SSIM＝畫質分數：把轉出來的每一格和原檔同一格比「結構像不像」，1＝一模一樣；0.99 以上幾乎分不出來、0.98 以上肉眼很難看出差別、0.95 以下仔細看會看到糊或色塊。'
                      'V0.1.63 起用短邊 1080 的大小比（之前縮成 640×360，4K 的壓縮痕跡被縮不見，分數偏寬鬆），所以分數會比之前低一點、但比較誠實。只是參考，最後還是用「並排比較」自己看。')
        note.setObjectName('muted'); note.setWordWrap(True); v.addWidget(note)
        lg = QHBoxLayout(); v.addLayout(lg); lt = QLabel('📜 LOG（碼率測試、畫質抽查）'); lt.setStyleSheet('font-weight:800'); self.b_full_log = QPushButton('打開完整 LOG')
        lg.addWidget(lt); lg.addStretch(1); lg.addWidget(self.b_full_log)
        self.logv = QPlainTextEdit(); self.logv.setReadOnly(True); self.logv.setMaximumHeight(200); self.logv.setLineWrapMode(QPlainTextEdit.NoWrap); v.addWidget(self.logv)
        self.b_full_log.clicked.connect(lambda: self.win.nav.setCurrentRow(4)); self.b_hload.clicked.connect(self._hload); self.b_det2.clicked.connect(self._det2)
        self.tb.doubleClicked.connect(lambda _ix: self._play())
        b1.clicked.connect(self._pick); b2.clicked.connect(self._pick_out); self.b_go.clicked.connect(self._go); self.b_stop.clicked.connect(self._stop)
        self.b_dir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self._outdir())) if self._outdir() else None)
        self.b_cmp.clicked.connect(self._cmp); self.b_play.clicked.connect(self._play); self.b_est.clicked.connect(self._est); self.b_tq.clicked.connect(self._tq)
        self.tm = QTimer(self); self.tm.timeout.connect(self._tick); self.tm.start(700); self._lg_n = 0
        self.st = ENG.brt_st                                                     # V0.1.62 熱更新後接著看（還在轉的也是）
        if not self.st:
            H = ENG.brt_history(); self.st = H[-1] if H else None
        if self.st and self.st.get('src'): self.src.setText(self.st['src']); QTimer.singleShot(800, self._detail)
        self._hfill()

    def _tq(self):
        src = self.src.text().strip()
        if not src or not os.path.isfile(src): self.win.msg('先選一個影片檔'); return
        if not ENG.gpu_st.get('ok'): self.win.msg('顯示卡現在不能壓縮（只用顯示卡）'); return
        thr = self.thr.value() / 1000; self.b_tq.setEnabled(False); self.b_tq.setText('🎯 找最省的設定中…（看下面 LOG）')
        def done(r):
            try: self.b_tq.setEnabled(True); self.b_tq.setText('🎯 自動找這部最省的設定（SSIM ≥ 門檻）')
            except RuntimeError: return
            if isinstance(r, Exception) or not r: self.win.msg(f'沒找成：{r}'); return
            tried = '、'.join(f'CQ{k}＝{v:.4f}' if v is not None else f'CQ{k}＝失敗' for k, v in r['tried'].items())
            QMessageBox.information(self, '🎯 自動找到的設定', f"{Path(src).name}\n\n目標 SSIM ≥ {thr:.3f}（{r['cmp']} 比）\n→ 用 CQ {r['q']}：樣本 SSIM {r['ssim']:.4f}" + ('' if r['ok'] else '（最好也沒到目標）') +
                                    f"\n影像約 {r['bps'] / 1e6:.2f} Mbps，預估整部 {fmt_b(r['pred'])}\n\n試過：{tried}\n花了 {r['sec']:.0f} 秒\n\n要驗證：在上面「H.265 顯示卡・固定畫質 CQ」填 {r['q']}，按開始，用並排比較看。")
        def work():
            try: return ENG.tq_try(src, thr)
            except Exception as ex: return ex
        bg(work, done, err=done)

    def _hfill(self):
        self.hc.clear()
        for h in reversed(ENG.brt_history()):
            self.hc.addItem(f"{time.strftime('%m-%d %H:%M', time.localtime(h.get('t0') or 0))}　{Path(h.get('src') or '').name}　{len(h.get('jobs') or [])} 種", h.get('t0'))

    def _hload(self):
        t0 = self.hc.currentData(); h = next((x for x in ENG.brt_history() if x.get('t0') == t0), None)
        if not h: return
        if self.st and not self.st.get('done'): self.win.msg('現在還在轉，轉完再看舊的'); return
        self.st = h; self.src.setText(h.get('src') or ''); self._det_for = None; self._detail(); self.tb.setRowCount(0); self._tick()

    def _det2(self):
        j = self._row()
        if not j or not j.get('out') or not os.path.exists(j['out']): self.win.msg('先選一列已經轉好的'); return
        def got(D):
            txt = '\n\n'.join(t_ + '\n' + '\n'.join(f'  {k}：{v_}' for k, v_ in it) for t_, it in D)
            m = QMessageBox(self); m.setWindowTitle('詳細格式：' + Path(j['out']).name); m.setText(txt); m.setTextInteractionFlags(Qt.TextSelectableByMouse); m.exec()
        bg(lambda: ENG.media_detail(j['out']), got, err=lambda ex: self.win.msg(f'讀不到格式：{ex}'))

    def _pick(self):
        f, _ = QFileDialog.getOpenFileName(self, '選要測試的影片', str(Path(self.src.text()).parent) if self.src.text() else '', '影片 (*.mp4 *.mkv *.ts *.avi *.mov *.wmv *.flv *.m4v *.mts *.webm *.mpg *.vob);;全部 (*.*)')
        if f: self.src.setText(os.path.normpath(f)); self._detail()

    def _detail(self):
        src = self.src.text().strip()
        if not src or not os.path.isfile(src): return
        if getattr(self, '_det_for', None) == src: return
        self._det_for = src; self.det.setText('讀取原檔格式中…')

        def got(D):
            if self._det_for != src: return
            cols = []
            for title, items in D:
                rows = ''.join(f"<tr><td style='color:#8a93a3;padding-right:10px;white-space:nowrap'>{k}</td><td>{str(v_).replace('<', '&lt;')}</td></tr>" for k, v_ in items)
                cols.append(f"<td style='vertical-align:top;padding-right:22px'><b>{title}</b><table>{rows}</table></td>")
            self.det.setText(f"<b>原檔詳細格式：{Path(src).name}</b><table><tr>{''.join(cols)}</tr></table>"); ENG.log.w(f'🧪 碼率測試：原檔格式 {src}：{D}')
        def bad(ex):
            if self._det_for == src: self._det_for = None; self.det.setText(f'讀不到格式：{ex}')
        bg(lambda: ENG.media_detail(src), got, err=bad)

    def _pick_out(self):
        d = QFileDialog.getExistingDirectory(self, '輸出到哪個資料夾', self.out.text() or '')
        if d: self.out.setText(os.path.normpath(d)); ENG.cfg.set('brt_out', self.out.text())

    def _outdir(self):
        return self.out.text().strip() or (str(Path(self.src.text().strip()).parent) if self.src.text().strip() else '')

    def _variants(self):
        V = []; F = {'thr': self.thr.value()}
        for k, (cb, e) in self.f.items():
            F[k] = e.text().strip(); F[k + '_on'] = cb.isChecked()
            if not cb.isChecked(): continue
            for x in e.text().replace('%', '').replace('，', ',').split(','):
                try: val = float(x)
                except ValueError: continue
                if (k == 'br' and 1 <= val <= 300) or (k != 'br' and 0 <= val <= 63): V.append((k, val))
        ENG.cfg.set('brt_fmt', F); return V[:16]

    def _est(self):
        src = self.src.text().strip()
        if not src or not os.path.isfile(src): self.win.msg('先選一個影片檔'); return
        V = self._variants()
        def work():
            p = core.probe(ENG.ffprobe, Path(src)); info = dict(p); info['size'] = os.path.getsize(src)
            return [(k, v, ENG.brt_estimate(info, k, v)) for k, v in V], info
        def got(r):
            L, info = r; self.st = {'jobs': [{'kind': k, 'val': v, 'name': f'{ENG.BRT_KINDS[k]} {v:g}' + ('%' if k == 'br' else ''), 'label': ENG.BRT_KINDS[k], 'raw': raw, 'est': int(raw * kk), 'k': kk, 'kn': n,
                                               'out': '', 'state': 'est', 'size': 0, 'ssim': 0, 'pctdone': 0, 'speed': '', 'sec': 0, 'enc': ''} for k, v, (raw, kk, n) in L],
                                     'src': src, 'src_size': info['size'], 'src_vbr': ENG.src_vbr(info), 'dur': float(info.get('dur') or 0), 'vcodec': info.get('vcodec'), 'w': info.get('w'), 'h': info.get('h'),
                                     'done': True, 'est_only': True, 'out_dir': self._outdir()}
            self.tb.setRowCount(0); self._tick()
        bg(work, got, err=lambda ex: self.win.msg(f'讀不到這個檔：{ex}'))

    def _go(self):
        src = self.src.text().strip()
        if not src or not os.path.isfile(src): self.win.msg('先選一個影片檔'); return
        if self.st and not self.st.get('done'): self.win.msg('上一次還在轉'); return
        P = self._variants()
        if not P: self.win.msg('至少勾一種格式、填一個數字'); return
        ENG.cfg.set('brt_out', self.out.text().strip()); self._detail()
        self.st = {'jobs': [], 'done': False}; st = self.st; ENG.brt_st = st; od = self._outdir(); ss = self.ss.isChecked()
        self.info.setText('準備中…'); self.b_go.setEnabled(False); self.tb.setRowCount(0)

        def work():
            try: ENG.br_test(src, od, P, st, ss)
            except Exception as ex: st['err'] = str(ex); st['done'] = True; ENG.log.w(f'🧪 碼率測試失敗：{ex}')
            if st.get('cancel'): ENG.brt_save(st)
        threading.Thread(target=work, name='VsBrTestBoss', daemon=True).start()

    def _stop(self):
        if self.st and not self.st.get('done'):
            self.st['cancel'] = True
            for j in self.st.get('jobs') or []:
                P = j.get('proc')
                if P:
                    try: P.kill()
                    except Exception: pass
            self.win.msg('停止中…')

    def _row(self):
        i = self.tb.currentRow(); J = (self.st or {}).get('jobs') or []
        return J[i] if 0 <= i < len(J) else None

    def _cmp(self):
        j = self._row()
        if not j or not j.get('out') or not os.path.exists(j['out']): self.win.msg('先選一列已經轉好的'); return
        d = PlayCompareDlg(self.win, self.st['src'], j['out'], '原檔', j['name'], max(0.0, float(self.st.get('dur') or 0) * 0.3),
                           title=f"碼率測試：原檔 vs {j['name']}"); d.setAttribute(Qt.WA_DeleteOnClose); d.show()

    def _play(self):
        j = self._row()
        if not j or not j.get('out') or not os.path.exists(j['out']): self.win.msg('先選一列已經轉好的'); return
        p_ = Player(self.win, j['out'], max(0.0, float(self.st.get('dur') or 0) * 0.3), Path(j['out']).name); p_.setAttribute(Qt.WA_DeleteOnClose); p_.show()

    def _tick(self):
        st = self.st
        if not self.isVisible(): return
        self._lg_n += 1
        if self._lg_n % 3 == 1:
            def got_log(L):
                t_ = '\n'.join(L)
                if t_ != self.logv.toPlainText():
                    sb = self.logv.verticalScrollBar(); at_end = sb.value() >= sb.maximum() - 4; self.logv.setPlainText(t_)
                    if at_end: sb.setValue(sb.maximum())
            bg(lambda: ENG.log_grep(['碼率測試', '畫質抽查', '試轉', '🎯'], 400), got_log)
        if not st: return
        if st.get('done') and not getattr(self, '_saved_list', False): self._saved_list = True; self._hfill()
        elif not st.get('done'): self._saved_list = False
        if st.get('err'): self.info.setText(f"<span style='color:#ff6577'>✖ {st['err']}</span>"); self.b_go.setEnabled(True); return
        J = st.get('jobs') or []; thr = self.thr.value() / 1000; srcsz = st.get('src_size') or 0
        ok = [j for j in J if j.get('state') == 'done' and (j.get('ssim') or 0) >= thr and j.get('size')]; best = min(ok, key=lambda j: j['size']) if ok else None
        if st.get('src_vbr'):
            el = (st.get('t1') or time.time()) - (st.get('t0') or time.time())
            s_ = (f"原檔：{Path(st['src']).name}　{st.get('vcodec')} {st.get('w')}×{st.get('h')}　{fmt_t(st.get('dur') or 0)}　整體 {srcsz * 8 / max(1, st.get('dur') or 1) / 1e6:.2f} Mbps（影像約 {st['src_vbr'] / 1e6:.2f} Mbps）　{fmt_b(srcsz)}")
            if st.get('est_only'): s_ += '　｜　🔮 只是預估（還沒轉）：預估會用之前轉出來的實際大小校正，轉越多次越準'
            else:
                L_ = [j_.get('left') for j_ in J if j_.get('state') in ('run', 'wait') and j_.get('left')]
                s_ += f"　｜　顯示卡同時轉（最多 5 個）　｜　{'✔ 全部完成' if st.get('done') else '轉檔中'}，花了 {fmt_t(el)}" + (f"，全部大約還要 {fmt_t(max(L_))}" if L_ and not st.get('done') else '') + f"　→ {st.get('out_dir')}"
            if best: s_ += f"<br><b style='color:#45d483'>⭐ 推薦：{best['name']}</b>（{fmt_b(best['size'])}，原檔的 {best['size'] * 100 / srcsz:.0f}%，SSIM {best['ssim']:.4f}）＝畫質分數 ≥ {thr:.3f} 裡面最小的"
            elif st.get('done') and not st.get('est_only'): s_ += f"<br>沒有一個畫質分數到 {thr:.3f}（可以把門檻調低，或試畫質數字小一點的）"
            self.info.setText(s_); self.info.setTextFormat(Qt.RichText)
        NM = {'wait': '等待', 'run': '⚙ 轉檔中', 'ssim': '算畫質中', 'done': '✔ 完成', 'fail': '✖ 失敗', 'stop': '停止', 'est': '🔮 預估'}
        if self.tb.rowCount() != len(J): self.tb.setRowCount(len(J))
        for i, j in enumerate(J):
            ss = j.get('ssim') or 0; est = j.get('est') or 0; sz = j.get('size') or 0
            vals = (('⭐ ' if j is best else '') + j['name'], j.get('enc') or j.get('label') or '', (fmt_b(est) + (f'（校正×{j["k"]:.2f}・{j["kn"]} 筆）' if j.get('kn') else '（第一次：用估的）')) if est else '?',
                    fmt_b(sz) if sz else '', f'{(sz / est - 1) * 100:+.0f}%' if sz and est else '', f"{(sz or est) * 100 / srcsz:.0f}%" if (sz or est) and srcsz else '',
                    f"{j['tot_br'] / 1e6:.2f} Mbps" if j.get('tot_br') else (f"約 {est * 8 / st['dur'] / 1e6:.2f} Mbps" if est and st.get('dur') else ''), f"{j['v_br'] / 1e6:.2f} Mbps" if j.get('v_br') else '',
                    f'{ss:.4f}' if ss else '', f"{j.get('pctdone') or 0:.0f}%", ('x' + str(j.get('speed') or '').rstrip('x')) if j.get('speed') else '',
                    fmt_t(j['left']) if j.get('left') else '', f"{j['sec']:.0f} 秒" if j.get('sec') else '',
                    NM.get(j.get('state'), j.get('state')) + ('：' + j['err'][-80:] if j.get('state') == 'fail' and j.get('err') else ''), j.get('out') or '')
            for c, val in enumerate(vals):
                it = self.tb.item(i, c)
                if it is None or it.text() != str(val):
                    col = None
                    if c == 8 and ss: col = '#45d483' if ss >= thr else ('#f0ad4e' if ss >= 0.95 else '#ff6577')
                    if c == 0 and j is best: col = '#45d483'
                    self.tb.setItem(i, c, _ti(val, SSIM_TIP if c == 8 else val, Qt.AlignRight | Qt.AlignVCenter if c in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12) else None, col))
        if st.get('done'): self.b_go.setEnabled(True)


# ============================================================ 📈 滾動式參數 LOG（V0.1.65）
# ============================================================ V0.2.28 🚚 搬硬碟（整顆搬到另一顆，紀錄跟著過去）
LAB_PACKS = [('⚡ 分級加速包', ['sprint', 'random_pick', 'break_remind', 'dur_chips', 'res_chips', 'guess', 'note_presets', 'bookmarks', 'scenes', 'keys_help', 'swipe_nav', 'playlist', 'views', 'recent_dirs', 'search_hist']),
             ('💽 硬碟管理包', ['unplug_check', 'keep_awake', 'done_notify', 'still_scan', 'smart_card', 'space_map', 'disk_warn', 'empty_dirs', 'pc_overview', 'auto_scan', 'folder_prog', 'report']),
             ('📤 上傳包', ['caption', 'copy_to', 'note_presets', 'playlist', 'list_csv']),
             ('📱 手機與安全包', ['conn_bar', 'web_devices', 'web_ro', 'phone_notify', 'bottom_nav', 'whats_new'])]   # V0.4.33   # V0.2.93 一次打開一組


class ToolboxPage(QWidget):
    """V0.2.52 🧰 新功能工具箱：每個新功能一張卡，一按就用；還沒打開的按一下＝打開再用."""
    def __init__(self, win):
        super().__init__(); self.win = win; self.cards = {}
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        t = QLabel('🧰 新功能工具箱'); t.setObjectName('title'); v.addWidget(t)
        n = QLabel('🆕 新功能都在這裡，一張卡一個。亮的＝已經打開，按一下就用；暗的＝還沒打開，按一下會先打開（之後在 🧪 實驗工作區 可以關掉）。按右鍵＝📌 釘到封面捷徑。'); n.setObjectName('muted'); n.setWordWrap(True); v.addWidget(n)
        pr = QHBoxLayout(); pr.addWidget(QLabel('一次打開一組：'))
        for nm_, K_ in LAB_PACKS:
            b_ = QPushButton(nm_); b_.setToolTip('打開：' + '、'.join(dict((k, n) for k, n, _d, _v in NEW_LABS).get(k, k) for k in K_)); b_.clicked.connect(lambda _c=False, nm_=nm_, K_=K_: self.pack_on(nm_, K_)); pr.addWidget(b_)
        pr.addStretch(1); bt_ = QPushButton('🆕 新功能導覽'); bt_.clicked.connect(win.tour_dlg); pr.addWidget(bt_); v.addLayout(pr)
        sr = QHBoxLayout(); self.fq = QLineEdit(); self.fq.setPlaceholderText('🔍 找功能（例如 上傳、衝刺、硬碟）'); self.fq.setClearButtonEnabled(True); sr.addWidget(self.fq, 1)   # V0.3.86 找功能、只看打開的
        self.fon = QCheckBox('只看打開的'); sr.addWidget(self.fon); v.addLayout(sr); self.fq.textChanged.connect(lambda _t: self.build()); self.fon.toggled.connect(lambda _o: self.build())
        self.grid = QGridLayout(); self.grid.setSpacing(8); v.addLayout(self.grid); v.addStretch(1); self.build()

    def acts(self):
        W = self.win
        def br(fn): return lambda: (W.enter(0), QTimer.singleShot(50, fn))
        def say(t): return lambda: W.msg(t)
        return {'unplug_check': W.unplug_dlg, 'web_devices': W.devices_dlg, 'web_ro': W.ro_pin_dlg, 'whats_new': lambda: W.whats_new(True), 'break_remind': W.break_dlg, 'random_pick': br(lambda: W.browse.random_pick()), 'weekly': W.week_dlg, 'sprint': W.sprint_dlg, 'report': W.report_dlg, 'space_map': W.space_dlg, 'empty_dirs': W.empty_dlg, 'pc_overview': W.pcs_dlg, 'goal': W.goal_dlg, 'keys_help': W.keys_dlg, 'cmdk': W.cmd_palette,
                'months': br(lambda: W.browse.months_dlg()), 'creators': br(lambda: W.browse.creators_dlg()), 'views': br(lambda: W.browse.views_menu()), 'list_csv': br(lambda: W.browse.export_csv()),
                'dur_chips': br(lambda: W.msg('⏱ 檔案總管搜尋框下面那一排就是')), 'res_chips': br(lambda: W.msg('📺 檔案總管時長那排下面就是')), 'copy_to': W.up_board_dlg,
                'bookmarks': br(lambda: W.browse.bm_all_dlg()), 'swipe_nav': say('👆 手機看檔案左右滑；電腦用滑鼠側鍵換部'),
                'folder_move': br(lambda: W.msg('🚚 檔案總管左邊資料夾按右鍵 →「🚚 搬到別顆硬碟…」')), 'bg_sched': lambda: W.enter(7), 'disk_warn': lambda: W.enter(7), 'privacy': lambda: W.b_pv.toggle(), 'recent_dirs': br(lambda: W.browse.recent_menu()), 'auto_scan': lambda: W.enter(7), 'rules': W.rule_dlg, 'caption': lambda: W.enter(7), 'share_auto': lambda: W.enter(7), 'smart_card': lambda: W.msg(f'🖼 背景慢慢換：還有 {ENG.still_left():,} 部'), 'still_scan': lambda: W.msg(f'😴 還有 {ENG.still_left():,} 部還沒算（背景慢慢算）'), 'scenes': say('🎬 看一部影片的預覽圖，換場景的格子左邊會有橘線'), 'bottom_nav': say('👍 這是手機用的：打開後手機分頁會移到螢幕最下面'), 'file_hist': say('📜 檔案總管選一部按右鍵「📜 這部的紀錄」'), 'playlist': br(lambda: W.browse.play_list(list(W.browse.rows or []))), 'folder_prog': W.progress_dlg, 'note_presets': lambda: W.enter(7), 'phone_notify': say('🔔 這是手機用的：手機網頁開著時狀態有變化就跳提醒'), 'proc_guard': lambda: W.enter(7), 'auto_theme': lambda: W.enter(7), 'search_hist': br(lambda: (W.browse.q.setFocus(), W.msg('🔎 在搜尋框打字，以前搜過的會跳出來'))), 'guess': br(lambda: W.msg('🤖 看一部還沒分級的影片，分級按鈕旁邊會出現「🤖 猜 …」'))}

    def build(self):
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        self.cards = {}; L = lab_cfg(); A_ = self.acts(); vt_ = lambda x: tuple(int(p_) for p_ in re.findall(r'\d+', str(x))[:3])
        S_ = sorted(NEW_LABS, key=lambda x: vt_(x[3]), reverse=True); used = set(); row = 0                     # V0.3.40 分組顯示（分級／硬碟／上傳／其他）
        fq_ = (self.fq.text().strip().lower() if hasattr(self, 'fq') else ''); fon_ = bool(hasattr(self, 'fon') and self.fon.isChecked())
        S_ = [x for x in S_ if (not fq_ or fq_ in (x[1] + x[2]).lower()) and (not fon_ or L.get(x[0]))]
        groups = [(n_, K_) for n_, K_ in LAB_PACKS] + [('🧩 其他', [x[0] for x in S_])]
        for gn, K in groups:
            items = [x for x in S_ if x[0] in K and x[0] not in used]
            if not items: continue
            h = QLabel(f'{gn}（{sum(1 for x in items if L.get(x[0]))}／{len(items)} 開著）'); h.setObjectName('title'); h.setStyleSheet('font-size:14px;margin-top:6px'); self.grid.addWidget(h, row, 0, 1, 3); row += 1
            for i, (k, nm, desc, ver) in enumerate(items):
                used.add(k)
                b = QPushButton(); b.setMinimumHeight(86); b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred); on = bool(L.get(k))
                short = desc if len(desc) <= 54 else desc[:52] + '…'
                b._vs = (nm, short, on); self._card_text(k, b); b.setToolTip(f'V{ver}　{desc}')
                b.setStyleSheet('QPushButton{text-align:left;padding:8px 10px;border-radius:10px;' + ('' if on else 'color:#8a9099;') + '}')
                b.clicked.connect(lambda _c=False, k=k: self.use(k)); self.grid.addWidget(b, row + i // 3, i % 3); self.cards[k] = b
                b.setContextMenuPolicy(Qt.CustomContextMenu); b.customContextMenuRequested.connect(lambda _p, k=k, nm=nm: self.pin(k, nm))   # V0.4.13 右鍵＝釘到封面
            row += (len(items) + 2) // 3

    def pin(self, k, nm):
        """V0.4.13 📌 工具箱卡片按右鍵：釘到封面那排捷徑（再按一次取消，最多 8 個）."""
        P = list(ENG.cfg.get('pin_tools') or [])
        if k in P: P.remove(k); self.win.msg(f'📌 {nm} 取消釘選')
        else: P = (P + [k])[-8:]; self.win.msg(f'📌 {nm} 釘到封面捷徑了（工具箱再按右鍵取消）')
        ENG.cfg.set('pin_tools', P)
        try: self.win.cover._quick()
        except Exception: pass
        self.build()

    def status(self, k):
        """V0.2.87 卡片上的即時狀態（打開的才顯示）."""
        try:
            if k == 'copy_to':
                C = ENG.copy_view(); c_ = getattr(ENG, '_upl_c', None)
                return (f"複製中 {C['pct']}%・還有 {C['q']}" if C['run'] or C['q'] else f"好了 {C['done']}") + ('・暫停' if C['paused'] else '') + (f"・S／A 還沒傳 {c_[1]:,}" if c_ and c_[1] else '') + ((lambda u_: f"・⬜ 沒發佈 {u_[1]:,}" if u_ and u_[1] else '')(getattr(ENG, '_unp_c', None)))   # V0.3.71／0.4.37
            if k == 'goal':
                G = getattr(ENG, '_goal_c', None); return f"今天 {G[1]['n']}／{G[1]['goal']}" if G else ''
            if k == 'auto_scan':
                st = getattr(ENG, '_as', None) or {}; return '掃描中' if st.get('run') else (f"上次 {time.strftime('%H:%M', time.localtime(st['last_t']))}・多了 {st.get('last_new', 0)}" if st.get('last_t') else '等第一次')
            if k == 'keep_awake': B_ = ENG.bg_busy(); return ('不睡中：' + '、'.join(B_)) if B_ else '沒事做，照平常睡'   # V0.4.03
            if k == 'break_remind': return f"連續 {int(lab_cfg().get('break_min') or 45)} 分鐘提醒"   # V0.3.89
            if k == 'random_pick': return 'Ctrl+R'
            if k == 'sprint': V = ENG.sprint_view(); return (f"衝刺中・{V['n']} 部" if V['on'] else f"剛結束・{V['n']} 部") if V else ''   # V0.3.72
            if k == 'views': return f'{len(ENG.views())} 個'
            if k == 'recent_dirs': return f'{len(ENG.recent_list())} 個'
            if k == 'search_hist': return f'{len(ENG.search_hist())} 個'
            if k == 'privacy': return '模糊中' if ENG.cfg.get('privacy_on') else '沒模糊'
            if k == 'proc_guard': h = ENG.proc_hold('conv'); return h.replace('🎥 ', '') if h else '沒在讓路'
            if k == 'empty_dirs': V = ENG.empty_view(); return '找中…' if V['run'] else (f"找到 {len(V['rows'])} 個" if V['done'] else '')
            if k == 'rules': L = ENG.cfg.get('rule_last') or {}; return f"上次 {len(L.get('ids') or [])} 部→{L.get('grade')}" if L.get('ids') else ''
            if k == 'guess': St = ENG.cfg.get('guess_stat') or {}; return f"猜中 {round(St['ok'] * 100 / St['n'])}%（{St['n']} 次）" if St.get('n') else ''   # V0.3.36
            if k in ('still_scan', 'smart_card'): n_ = ENG.still_left_c(); return f'還有 {n_:,} 部' if n_ else '都算好了'   # V0.3.25
        except Exception: return ''
        return ''

    def _card_text(self, k, b):
        nm, short, on = b._vs; st_ = self.status(k) if on else ''
        b.setText(f'{nm}' + ('　📌' if k in (ENG.cfg.get('pin_tools') or []) else '') + (f'　【{st_}】' if st_ else '') + f'\n{short}' + ('' if on else '\n（還沒打開・按一下打開）'))

    def refresh(self):
        for k, b in list(self.cards.items()):
            try: self._card_text(k, b)
            except Exception: pass

    def showEvent(self, e):
        super().showEvent(e); self.build()
        if not hasattr(self, '_st_t'): self._st_t = QTimer(self); self._st_t.timeout.connect(lambda: self.refresh() if self.isVisible() else None)
        self._st_t.start(3000)

    def hideEvent(self, e):
        super().hideEvent(e)
        if hasattr(self, '_st_t'): self._st_t.stop()

    def pack_on(self, nm, K):
        K = [k for k in K if k in dict((k_, 1) for k_, *_r in NEW_LABS) and not lab_cfg().get(k)]
        if not K: self.win.msg(f'{nm}：都已經打開了'); return
        if QMessageBox.question(self, nm, f'一次打開這 {len(K)} 個？\n\n' + '\n'.join('・' + dict((k_, n_) for k_, n_, _d, _v in NEW_LABS)[k] for k in K) + '\n\n（之後在 🧪 實驗工作區 可以一個一個關）') != QMessageBox.Yes: return
        ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, **{k: True for k in K})); self.win.apply_new_labs()
        try: self.win.lab.refresh_summary()
        except Exception: pass
        self.build(); self.win.msg(f'{nm}：打開了 {len(K)} 個')

    def use(self, k):
        try:
            if not lab_cfg().get(k):
                ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, **{k: True})); self.win.apply_new_labs()
                try: self.win.lab.refresh_summary()
                except Exception: pass
                self.build(); self.win.msg(f'🧪 已打開「{dict((a, b) for a, b, _c, _d in NEW_LABS).get(k, k)}」')
            fn = self.acts().get(k)
            if fn: fn()
        except Exception: ENG.log.err(f'工具箱 {k}')


class RsDiskW(QWidget):
    """V0.5.96 💽 一顆硬碟：工作管理員樣式（上：使用率％ 面積圖；下：讀（虛線）／寫（實線）MB/s）."""
    def __init__(self):
        super().__init__(); self.D = {}; self.c = '#2f9bff'; self.setMinimumHeight(190); self.setMinimumWidth(180)

    def set(self, D, c): self.D = D or {}; self.c = c; self.setToolTip(f"{D.get('X')}: {D.get('role')}"); self.update()

    def paintEvent(self, e):
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); W, H = self.width(), self.height(); C = QColor(self.c); D = self.D
        try:
            p.setPen(QPen(QColor(self.c), 1)); bg = QColor(0, 0, 0, 60); p.setBrush(bg); p.drawRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), 10, 10)
            p.fillRect(QRectF(1, 1, W - 2, 3), C)
            f = p.font(); f.setBold(True); f.setPointSizeF(10.5); p.setFont(f); p.setPen(QColor('#e6edf6'))
            p.drawText(QRectF(10, 8, W - 20, 20), Qt.AlignLeft | Qt.AlignVCenter, f"💽 {D.get('X', '?')}:  {D.get('role', '')}")
            bz = D.get('busy'); f.setPointSizeF(15); p.setFont(f); p.setPen(QColor('#ff6b6b') if (bz or 0) >= 95 else C)
            p.drawText(QRectF(10, 6, W - 20, 24), Qt.AlignRight | Qt.AlignVCenter, '—' if bz is None else f'{bz}%')
            h = D.get('h') or []; N = 100; f.setBold(False); f.setPointSizeF(8); p.setFont(f)

            def box(y, hh, label, right):
                r = QRectF(10, y, W - 20, hh); p.setPen(QColor(150, 160, 175)); p.drawText(QRectF(10, y - 14, W - 20, 12), Qt.AlignLeft, label); p.drawText(QRectF(10, y - 14, W - 20, 12), Qt.AlignRight, right)
                gc = QColor(self.c); gc.setAlpha(45); p.setPen(QPen(gc, 1)); p.setBrush(QColor(0, 0, 0, 50)); p.drawRect(r)
                for k in range(1, 4): p.drawLine(QPointF(r.left(), r.top() + r.height() * k / 4), QPointF(r.right(), r.top() + r.height() * k / 4))
                for k in range(1, 10): p.drawLine(QPointF(r.left() + r.width() * k / 10, r.top()), QPointF(r.left() + r.width() * k / 10, r.bottom()))
                return r

            def pts(r, vals, mx):
                n = len(vals); return [QPointF(r.right() - (n - 1 - i) * r.width() / (N - 1), r.bottom() - min(1.0, float(v or 0) / mx) * (r.height() - 2) - 1) for i, v in enumerate(vals)]
            r1 = box(48, (H - 110) * 0.6, '使用率', '100%')
            if len(h) > 1:
                P1 = pts(r1, [x[0] or 0 for x in h], 100.0); poly = QPolygonF([QPointF(P1[0].x(), r1.bottom())] + P1 + [QPointF(P1[-1].x(), r1.bottom())])
                fc = QColor(self.c); fc.setAlpha(55); p.setPen(Qt.NoPen); p.setBrush(fc); p.drawPolygon(poly); p.setPen(QPen(C, 1.6)); p.setBrush(Qt.NoBrush); p.drawPolyline(QPolygonF(P1))
            mx = max([10 * 1048576.0] + [float(x[1] or 0) for x in h] + [float(x[2] or 0) for x in h]) * 1.15
            r2 = box(r1.bottom() + 20, (H - 110) * 0.4, '傳輸速率', f'{mx / 1048576:.0f} MB/s')
            if len(h) > 1:
                pr = QPen(C, 1.3); pr.setStyle(Qt.DashLine); p.setPen(pr); p.drawPolyline(QPolygonF(pts(r2, [x[1] for x in h], mx)))
                p.setPen(QPen(C, 1.8)); p.drawPolyline(QPolygonF(pts(r2, [x[2] for x in h], mx)))
            f.setPointSizeF(9); p.setFont(f); p.setPen(QColor('#cfd8e3'))
            mb = lambda b: f'{float(b or 0) / 1048576:.1f} MB/s'
            p.drawText(QRectF(10, H - 22, W - 20, 16), Qt.AlignLeft, f"┅ 讀 {mb(D.get('rd'))}"); p.drawText(QRectF(10, H - 22, W - 20, 16), Qt.AlignRight, f"━ 寫 {mb(D.get('wr'))}")
        except Exception: pass
        finally: p.end()


def _hesc(x):
    return _html.escape(str(x))                                                 # V0.6.31 舊 EXE 沒有 html 模組


class RSplitPage(QWidget):
    """V0.5.85 🚚 R 碟清空搬移：R 上的檔案分到兩顆硬碟；每個檔整檔比對過才刪 R 上的那個（引擎在 vs_rsplit.py，網頁「工具」最上面也有一樣的）."""
    def __init__(self, win):
        super().__init__(); self.win = win; self.arm = 0; self._busy = False
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        t = QLabel('🗄 R 碟清空搬移（已封存）'); t.setObjectName('title'); t.setStyleSheet('color:#ff5252;font-size:20px;font-weight:700'); v.addWidget(t)
        ar = QLabel('🗄 這個功能已經封存：不在左邊選單裡，避免誤按。要再用：電腦按 <b>Ctrl+Shift+R</b>；手機：⚙ 設定 → 📱 手機網頁 最下面「🗄 封存的功能」。搬移紀錄和設定都還在。')
        ar.setWordWrap(True); ar.setStyleSheet('background:#2a2410;border:1px solid #f0ad4e;border-radius:8px;padding:8px;color:#f0c27a'); v.addWidget(ar)
        w = QLabel('把來源硬碟上<b>所有的檔案</b>分到兩顆硬碟（位置不變，只換磁碟代號：R:\\A\\b.mp4 → S:\\A\\b.mp4）。<br>'
                   '• 開始後 SortCut 和整理的背景工作都先停（不讀 R），搬完自動恢復。<br>'
                   '• 每個檔：<b>複製 → 寫進硬碟 → 確認</b>（⚡ 快速：大小一樣、抽查 5 段一樣；🔎 完整：整檔讀回比指紋），確認過才刪 R 上的那個檔；不一樣的留在 R、下面列清單。<br>'
                   '• 預覽圖、分級、指紋、分類紀錄都跟著換到新位置，不用重算。關掉程式、更新也會從剩下的接著搬。<br>'
                   '• 兩顆同時跑：複製到一顆的同時，比對另一顆剛寫好的。')
        w.setWordWrap(True); w.setTextFormat(Qt.RichText); w.setStyleSheet('background:rgba(198,40,40,.14);border:1px solid #c62828;border-radius:8px;padding:8px'); v.addWidget(w)
        pg = QGroupBox('⚡ 傳輸速度'); pv = QVBoxLayout(pg); v.insertWidget(1, pg)                 # V0.5.87 速度拉桿、🧠 智能
        ph = QHBoxLayout(); pv.addLayout(ph)
        self.sl = QSlider(Qt.Horizontal); self.sl.setRange(1, 20); self.sl.setPageStep(2); self.sl.setMinimumWidth(260)
        self.slv = QLabel('100%'); self.slv.setStyleSheet('font-size:20px;font-weight:800;color:#4dc9ff;min-width:90px')
        self.b_smart = QPushButton('🧠 智能'); self.b_smart.setCheckable(True)
        self.b_smart.setStyleSheet('QPushButton{padding:6px 14px;border-radius:14px;font-weight:700}QPushButton:checked{background:#5b3fe0;color:#fff}')
        self.ser = QComboBox(); self.ser.addItem('寫入：🧠 自動', 'auto'); self.ser.addItem('寫入：一次寫一顆', 'one'); self.ser.addItem('寫入：兩顆同時寫', 'two')
        self.ver = QComboBox(); self.ver.addItem('確認：⚡ 快速（單向，抽查）', 'quick'); self.ver.addItem('確認：🔎 完整（整檔讀回）', 'full')
        self.ver.setToolTip('⚡ 快速：只寫一次，寫完確認大小、抽查 5 段跟原檔一樣就刪 R 的（最快）\n🔎 完整：寫完再把整個檔讀回來比指紋（最保險，慢一倍）')
        self.ver.activated.connect(lambda _i: self._pace({'verify': self.ver.currentData()}))
        ph.addWidget(QLabel('慢')); ph.addWidget(self.sl, 1); ph.addWidget(QLabel('快')); ph.addWidget(self.slv); ph.addWidget(self.b_smart); ph.addWidget(self.ser); ph.addWidget(self.ver)
        self.pinf = QLabel(''); self.pinf.setWordWrap(True); self.pinf.setTextFormat(Qt.RichText); pv.addWidget(self.pinf)
        self.sl.valueChanged.connect(lambda x: self.slv.setText(f'{x * 5}%'))
        self.sl.sliderReleased.connect(lambda: self._pace({'pct': self.sl.value() * 5, 'smart': False}))
        self.b_smart.clicked.connect(lambda on: self._pace({'smart': bool(on)}))
        self.ser.activated.connect(lambda _i: self._pace({'serial': self.ser.currentData()}))
        self.g = QGroupBox('選硬碟'); f = QFormLayout(self.g); v.addWidget(self.g)
        self.src = QComboBox(); self.t1 = QComboBox(); self.t2 = QComboBox(); b_rf = QPushButton('🔄 重新讀硬碟')
        rs = QHBoxLayout(); rs.addWidget(self.src, 1); rs.addWidget(b_rf)
        self.mode = QComboBox(); self.mode.addItem('📂 已分類一顆、還沒分類一顆（建議）', 'cls'); self.mode.addItem('⚖ 兩顆平均分', 'auto')
        self.l1 = QLabel('① 已分類（倉庫）'); self.l2 = QLabel('② 還沒分類（工作）')
        f.addRow('來源（要清空的）', rs); f.addRow('怎麼分', self.mode); f.addRow(self.l1, self.t1); f.addRow(self.l2, self.t2)
        self.mode.currentIndexChanged.connect(lambda _i: (self.l1.setText('① 已分類（倉庫）' if self.mode.currentData() == 'cls' else '目的 ①'),
                                                          self.l2.setText('② 還沒分類（工作）' if self.mode.currentData() == 'cls' else '目的 ②')))
        r = QHBoxLayout(); v.addLayout(r)
        self.b_plan = QPushButton('🔍 先算一下怎麼分（只讀，不會動檔案）'); self.b_go = QPushButton('🚚 開始轉移')
        self.b_go.setStyleSheet('QPushButton{background:#c62828;color:#fff;font-weight:700;font-size:15px;padding:8px 18px;border-radius:6px}QPushButton:disabled{background:#5a2a2a;color:#aaa}')
        self.b_pause = QPushButton('⏸ 暫停'); self.b_reset = QPushButton('↺ 清掉這次的紀錄')
        for w_ in (self.b_plan, self.b_go, self.b_pause, self.b_reset): r.addWidget(w_)
        r.addStretch(1)
        self.pinfo = QLabel(''); self.pinfo.setWordWrap(True); self.pinfo.setTextFormat(Qt.RichText); v.addWidget(self.pinfo)
        self.dk = QWidget(); dkl = QHBoxLayout(self.dk); dkl.setContentsMargins(0, 0, 0, 0); dkl.setSpacing(8); self.dkw = []   # V0.5.96 💽 三顆硬碟曲線
        for _i in range(3): w_ = RsDiskW(); dkl.addWidget(w_, 1); self.dkw.append(w_)
        v.addWidget(self.dk); self.dk.hide()
        self.bar = QProgressBar(); self.bar.setRange(0, 1000); v.addWidget(self.bar)
        self.st = QLabel(''); self.st.setWordWrap(True); self.st.setTextFormat(Qt.RichText); v.addWidget(self.st)
        self.gf = QGroupBox('📄 正在處理'); gf = QGridLayout(self.gf); v.addWidget(self.gf); self.fr = {}
        for r_, (k_, ic_) in enumerate((('c0', '📥 複製'), ('c1', '📥 複製'), ('v', '🔎 確認'))):
            l1 = QLabel(ic_); l1.setStyleSheet('font-weight:700'); nm = QLabel('—'); nm.setTextFormat(Qt.RichText); nm.setWordWrap(True)
            pb = QProgressBar(); pb.setRange(0, 1000); pb.setTextVisible(True); pb.setMaximumHeight(16)
            gf.addWidget(l1, r_ * 2, 0); gf.addWidget(nm, r_ * 2, 1); gf.addWidget(pb, r_ * 2 + 1, 0, 1, 2); self.fr[k_] = (nm, pb)
        gf.setColumnStretch(1, 1)
        g3 = QGroupBox('✅ 最近搬好的'); g3v = QVBoxLayout(g3); v.addWidget(g3, 2)
        self.rec = QTableWidget(0, 6); self.rec.setHorizontalHeaderLabels(['', '檔名', '大小', '到', '複製／比對', '時間'])
        self.rec.verticalHeader().setVisible(False); self.rec.setEditTriggers(QAbstractItemView.NoEditTriggers); self.rec.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rec.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch); self.rec.setMinimumHeight(200); g3v.addWidget(self.rec)
        g2 = QGroupBox('沒搬成的（原檔還在來源硬碟上）'); g2v = QVBoxLayout(g2); v.addWidget(g2, 1)
        self.fail = QPlainTextEdit(); self.fail.setReadOnly(True); self.fail.setMinimumHeight(120); g2v.addWidget(self.fail)
        b_rf.clicked.connect(self.load_drives); self.b_plan.clicked.connect(self._plan); self.b_go.clicked.connect(self._go)
        self.b_pause.clicked.connect(lambda: self._ctl('resume' if self._state == 'pause' else 'pause'))
        self.b_reset.clicked.connect(lambda: QMessageBox.question(self, '清掉紀錄', '清掉這次的搬移紀錄？（已經搬好的檔不會動）') == QMessageBox.Yes and self._ctl('reset'))
        for cb in (self.src, self.t1): cb.currentIndexChanged.connect(self._fix)
        self._state = ''; self._D = []
        self._mq_build(v)
        self.load_drives(); self.tm = QTimer(self); self.tm.timeout.connect(self.refresh); self.tm.start(2000)

    def _mq_build(self, v):
        """V0.6.35 📋 多步搬移（手機同一個）：① A 選的資料夾 → C ② A 剩下 → B ③ B 原本的 → A ④ 對調代號."""
        g = QGroupBox('📋 多步搬移（照順序一步一步搬，空間不夠先停；搬的時候這幾顆冷凍：只能看不能改）'); g.setStyleSheet('QGroupBox{border:2px solid #2f9bff}')
        gv = QVBoxLayout(g); v.insertWidget(1, g); self._mq_sig = ''
        r = QHBoxLayout(); gv.addLayout(r); self.mqX = QComboBox(); self.mqY = QComboBox(); self.mqZ = QComboBox()
        for nm, cb, d in (('A（先清空）', self.mqX, 'D'), ('B（A 剩下的搬來、原本的搬去 A）', self.mqY, 'H'), ('C（A 選的資料夾先搬來）', self.mqZ, 'G')):
            r.addWidget(QLabel(nm)); r.addWidget(cb); cb.setProperty('def', d)
        b = QPushButton('🔍 讀 A 的資料夾大小'); r.addWidget(b); r.addStretch(1); b.clicked.connect(lambda: self._mq('mq_scan'))
        gv.addWidget(QLabel('① A 選的資料夾 → C　② A 剩下的 → B　③ B 原本的 → A　④ 到磁碟管理對調 A／B 代號（SortCut 用序號認得，紀錄都在）'))
        self.mq_tree = QTreeWidget(); self.mq_tree.setHeaderLabels(['A 上的資料夾（勾＝① 先搬到 C）', '大小', '檔案數']); self.mq_tree.setMinimumHeight(180); gv.addWidget(self.mq_tree)
        self.mq_tree.setColumnWidth(0, 420)
        self.mq_info = QLabel(''); self.mq_info.setWordWrap(True); self.mq_info.setTextFormat(Qt.RichText); gv.addWidget(self.mq_info)
        r2 = QHBoxLayout(); gv.addLayout(r2); self.mq_b = {}
        for k, t in (('mq_create', '✅ 檢查空間、記下 B 原本的檔'), ('mq_go', '🚚 開始／▶ 繼續'), ('mq_pause', '⏸ 暫停'), ('mq_swapped', '✔ 代號換好了'), ('mq_cancel', '✖ 取消計畫')):
            bb = QPushButton(t); r2.addWidget(bb); self.mq_b[k] = bb; bb.clicked.connect(lambda _c=False, k=k: self._mq(k))
        r2.addStretch(1)

    def _mq_only(self):
        out = []
        for i in range(self.mq_tree.topLevelItemCount()):
            it = self.mq_tree.topLevelItem(i)
            if it.checkState(0) == Qt.Checked: out.append(it.data(0, Qt.UserRole)); continue
            for k in range(it.childCount()):
                c = it.child(k)
                if c.checkState(0) == Qt.Checked: out.append(c.data(0, Qt.UserRole))
        return [x for x in out if x]

    def _mq(self, a):
        X, Y, Z = (cb.currentData() for cb in (self.mqX, self.mqY, self.mqZ))
        if a == 'mq_scan': return bg(lambda: self.o().mq_scan(X), lambda r: self.win.msg('📋 ' + r.get('message', '')))
        if a == 'mq_create':
            only = self._mq_only()
            if not only: QMessageBox.information(self, '📋 多步搬移', f'先勾 {X}: 上要先搬到 {Z}: 的資料夾'); return
            return bg(lambda: self.o().mq_create(X, Y, Z, only), lambda r: self.win.msg('📋 ' + r.get('message', '')))
        if a == 'mq_go':
            if QMessageBox.question(self, '📋 多步搬移', '確定開始搬？\n\n• 先停好轉檔／H265（手上的停下、放回排隊），確認沒有在動才開始\n• 搬的時候這幾顆冷凍：SortCut、整理、H265 只能看不能改\n• 一步做完自動接下一步') != QMessageBox.Yes: return
            return bg(lambda: self.o().mq_go(), lambda r: self.win.msg('📋 ' + r.get('message', '')))
        if a == 'mq_cancel' and QMessageBox.question(self, '📋 多步搬移', '取消這個計畫？（已經搬好的不會變回去）') != QMessageBox.Yes: return
        bg(lambda: self.o().mq_ctl(a[3:]), lambda r: self.win.msg('📋 ' + r.get('message', '')))

    def _mq_show(self, j):
        D = j.get('drives') or []; Q = j.get('mq') or {}; M = j.get('mqs') or {}; FZ = j.get('freeze') or {}; st = Q.get('state') or ''
        ks = ','.join(d['X'] for d in D)
        if ks != getattr(self, '_mq_ks', ''):
            self._mq_ks = ks
            for cb in (self.mqX, self.mqY, self.mqZ):
                cur = cb.currentData() or Q.get({'D': 'X', 'H': 'Y', 'G': 'Z'}.get(cb.property('def'), ''), '') or cb.property('def'); cb.blockSignals(True); cb.clear()
                for d in D: cb.addItem(f"{d['X']}:{(' ' + d['label']) if d.get('label') else ''}　{core.fmt_b(d['used'])}／{core.fmt_b(d['total'])}", d['X'])
                i = cb.findData(cur); cb.setCurrentIndex(max(0, i)); cb.blockSignals(False)
        sig = f"{M.get('X')}{M.get('t')}{len(M.get('tops') or [])}"
        if sig != self._mq_sig and (M.get('tops') or []):
            self._mq_sig = sig; self.mq_tree.clear()
            for t in M['tops']:
                if t['rel'] == '（根目錄的檔）': continue
                it = QTreeWidgetItem([f"📁 {t['rel']}", core.fmt_b(t['b']), f"{t['n']:,}"]); it.setData(0, Qt.UserRole, t['rel']); it.setCheckState(0, Qt.Unchecked)
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                for k in t.get('kids') or []:
                    c = QTreeWidgetItem([k['rel'], core.fmt_b(k['b']), f"{k['n']:,}"]); c.setData(0, Qt.UserRole, k['rel']); c.setCheckState(0, Qt.Unchecked); it.addChild(c)
                self.mq_tree.addTopLevelItem(it)
        h = []
        if FZ.get('on'): h.append(f"<b style='color:#4dc9ff'>🧊 {' '.join(x + ':' for x in FZ.get('letters') or [])} 冷凍中</b>（SortCut、整理、H265 只能看不能改；搬完或暫停就解凍）")
        if j.get('waiting') or j.get('pmsg'): h.append('⏳ ' + _html.escape(j.get('pmsg') or '等轉檔／H265 停好…'))
        if M.get('msg'): h.append(_html.escape(M['msg']))
        if Q.get('X'):
            s_ = Q.get('s') or [0, 0, 0]
            for i, x in enumerate(Q.get('steps') or []):
                dn = next((d for d in Q.get('done') or [] if d['i'] == i), None); cur = i == int(Q.get('i') or 0) and st == 'run'
                h.append(f"{'✔' if dn else '▶' if cur else '○'} <b>{_html.escape(x['title'])}</b>" + (f'　{core.fmt_b(s_[i])}' if i < 3 else '') + (f"　搬好 {dn['n']:,} 個" + (f"・沒搬成 {dn['fail']}" if dn.get('fail') else '') if dn else ''))
            if Q.get('collide_n'): h.append(f"⚠ {Q['collide_n']} 個同路徑同名（搬到 {Q['Y']}: 時自動加 (2)）")
            for p_ in Q.get('problems') or []: h.append(f"<span style='color:#ff6b6b'>✖ {_html.escape(p_)}</span>")
            if Q.get('notice'): h.append(f"<b style='color:#3fb37f'>{_html.escape(Q['notice'])}</b>")
            if Q.get('msg'): h.append(_html.escape(Q['msg']))
        self.mq_info.setText('<br>'.join(h))
        en = {'mq_create': st in ('', 'bad', 'done'), 'mq_go': st in ('ready', 'stopped'), 'mq_pause': st == 'run', 'mq_swapped': st == 'swap', 'mq_cancel': bool(Q) and st != 'run'}
        for k, b_ in self.mq_b.items(): b_.setEnabled(en.get(k, False))

    def o(self):
        import vs_rsplit as RS
        return RS.get(ENG)

    def load_drives(self):
        def get():
            o = self.o(); return o.drives(), (o.meta('plan') or {})
        bg(get, self._drives)

    def _drives(self, r):
        L, P = r; self._D = L or []; V = {}                                     # V0.5.91 資料庫在背景讀（畫面不等）
        want = [P.get('src') or 'R'] + list(P.get('tgts') or [])
        for cb in (self.src, self.t1, self.t2): V[cb] = cb.currentData()
        big = [d['X'] for d in sorted(self._D, key=lambda d: -d['free']) if d['X'] != want[0]]
        j_ = self.mode.findData(P.get('mode') or 'cls')
        if j_ >= 0: self.mode.setCurrentIndex(j_)
        for i, cb in enumerate((self.src, self.t1, self.t2)):
            cb.blockSignals(True); cb.clear()
            for d in self._D: cb.addItem(f"{d['X']}:（{d['label'] or '沒有名稱'}）用了 {fmt_b(d['used'])}／{fmt_b(d['total'])}・剩 {fmt_b(d['free'])}", d['X'])
            w_ = V[cb] or (want[i] if i < len(want) else '') or (big[i - 1] if 0 < i <= len(big) else '')
            j = cb.findData(w_)
            if j >= 0: cb.setCurrentIndex(j)
            cb.blockSignals(False)
        self._fix()

    def _fix(self, *_a):
        S = self.src.currentData()
        if self.t1.currentData() == S:
            for j in range(self.t1.count()):
                if self.t1.itemData(j) != S: self.t1.setCurrentIndex(j); break
        if self.t2.currentData() in (S, self.t1.currentData()):
            for j in range(self.t2.count()):
                if self.t2.itemData(j) not in (S, self.t1.currentData()): self.t2.setCurrentIndex(j); break

    def _plan(self):
        S, A, B = self.src.currentData(), self.t1.currentData(), self.t2.currentData()
        if not (S and A and B) or len({S, A, B}) != 3: return QMessageBox.information(self, '選硬碟', '來源和兩顆目的要是三顆不同的硬碟')
        self.b_plan.setEnabled(False); self.b_plan.setText('🔍 計算中…（檔案多要等一下）'); ENG.log.w(f'🚚 電腦按了「先算一下」：{S}: → {A}: ＋ {B}:')
        M = self.mode.currentData() or 'auto'
        bg(lambda: self.o().plan(S, [A, B], M), self._planned, lambda ex: self._planned({'ok': False, 'message': str(ex)}))

    def _planned(self, r):
        self.b_plan.setEnabled(True); self.b_plan.setText('🔍 先算一下怎麼分（只讀，不會動檔案）')
        if not r.get('ok'): QMessageBox.warning(self, '算不出來', r.get('message', '沒成功'))
        self.refresh()

    def _go(self):
        if self._state == 'pause':                                               # V0.5.99 代號對不上：先問要不要照序號改過去
            VB = [c for c in (getattr(self, '_vols', None) or []) if not c.get('ok')]
            if VB:
                M = {c['X']: c['found'] for c in VB if c.get('found')}
                txt = '\n'.join(f"{c['role']}：原本 {c['X']}:（{c.get('label') or ''}）→ " + (f"現在是 {c['found']}:" if c.get('found') else '找不到（還沒接上？）') for c in VB)
                if len(M) == len(VB) and QMessageBox.question(self, '💽 硬碟代號換了', f'重開機後代號跑掉了（用硬碟序號認出來的）：\n\n{txt}\n\n要把搬移清單和 SortCut／整理的紀錄改成新代號嗎？（檔案不動）') == QMessageBox.Yes:
                    ENG.log.w(f'🚚 電腦按了改代號：{M}')
                    return bg(lambda: self.o().remap(M), lambda r: (QMessageBox.information(self, '💽 硬碟代號', r.get('message', '')), self.refresh()))
                if len(M) != len(VB): return QMessageBox.warning(self, '💽 硬碟代號', f'有硬碟還找不到：\n\n{txt}\n\n請先接好再按繼續（網頁版可以手動選代號）')
                return
            return self._ctl('resume')
        P = getattr(self, '_P', None) or {}
        if QMessageBox.question(self, '🚚 開始轉移', f"確定開始？\n\n{P.get('src')}: 上 {P.get('n', 0):,} 個檔、{fmt_b(P.get('total'))} 會分到 {'： ＋ '.join(P.get('tgts') or [])}:。\n"
                                f"每個檔整檔比對過才刪 {P.get('src')}: 上的那個。開始後背景工作會先停，搬完自動恢復。") != QMessageBox.Yes: return
        self._ctl('start')

    def _ctl(self, a):
        ENG.log.w(f'🚚 電腦按了 R 碟搬移：{a}')
        def done(r):
            if not r.get('ok'): QMessageBox.information(self, 'R 碟搬移', r.get('message', '沒成功'))
            self.refresh()
        bg(lambda: self.o().ctl(a), done)

    def _pace(self, d):
        ENG.log.w(f'🚚 電腦改 R 碟搬移速度：{d}')
        bg(lambda: self.o().set_pace(d), lambda r: self.refresh())

    def refresh(self):
        if self._busy or not self.isVisible(): return
        self._busy = True
        bg(lambda: self.o().view(), self._show, lambda ex: setattr(self, '_busy', False))

    def _show(self, j):
        self._busy = False
        try: self._mq_show(j)
        except Exception: ENG.log.err('📋 多步搬移畫面')
        try:
            st = j.get('state') or ''; self._state = st; P = j.get('plan') or {}; self._P = P; self._vols = j.get('vols') or []; T = list(P.get('tgts') or []); busy = st in ('run', 'pause')
            self.g.setEnabled(not busy and st != 'done'); self.b_plan.setEnabled(not busy and st != 'done')
            if j.get('planning'): self.b_plan.setEnabled(False); self.b_plan.setText('🔍 ' + (j.get('pmsg') or '計算中…')); self.g.setEnabled(False)
            elif not self.b_plan.isEnabled() and not busy and st != 'done': self.b_plan.setText('🔍 先算一下怎麼分（只讀，不會動檔案）')
            self.b_go.setEnabled(st in ('planned', 'pause') and not j.get('draining')); self.b_go.setText('▶ 繼續轉移' if st == 'pause' else '🚚 開始轉移')
            self.b_pause.setText('⏸ 暫停（手上的做完再停）')
            self.b_pause.setEnabled(st == 'run'); self.b_reset.setEnabled(st in ('planned', 'done', 'pause'))
            h = ''
            if P.get('ok'):
                h = f"<b>📋 分法：{P['src']}: 共 {P['n']:,} 個檔、{fmt_b(P['total'])}</b><br>" + '<br>'.join(
                    f"<b>{t}:</b> 放 {P['pern'].get(t, 0):,} 個、{fmt_b(P['per'].get(t, 0))}・搬完後剩 <b>{fmt_b(P['free'][t] - P['per'].get(t, 0))}</b>" for t in T)
                if P.get('mode') == 'cls':
                    h += (f"<br>📂 已分類 {P.get('cls_n', 0):,} 個 {fmt_b(P.get('cls_b'))} → <b>{T[0]}:</b>　🆕 還沒分類 {P.get('unc_n', 0):,} 個 {fmt_b(P.get('unc_b'))} → <b>{T[1]}:</b>"
                          + (f"<br><span style='color:#f0ad4e'>⚠ {T[1]}: 放不下全部還沒分類的：{P['spill_n']:,} 個 {fmt_b(P['spill_b'])} 補到 {T[0]}:</span>" if P.get('spill_n') else ''))
                U = P.get('units') or []
                h += '<br><small>' + '　'.join(f"{u['tgt']}: {_hesc(u['rel'])}（{fmt_b(u['b'])}）" for u in U[:40]) + (f'　…共 {len(U)} 個' if len(U) > 40 else '') + '</small>'
            self.pinfo.setText(h)
            pc = float(j.get('pct') or 0); self.bar.setValue(int(pc * 10)); self.bar.setVisible(busy or st == 'done')
            s = ''
            if busy or st == 'done':
                C = j.get('cur') or {}
                s = (f"<b>{'▶ 搬移中' if st == 'run' else '⏸ 暫停中' if st == 'pause' else '✔ 搬完了'}　{pc}%</b>　已搬好（比對過、原檔已刪）<b>{j['done_n']:,}</b> 個 {fmt_b(j['done_b'])}・還剩 <b>{j['pend_n']:,}</b> 個 {fmt_b(j['pend_b'])}"
                     + (f"・<span style='color:#ff6b6b'>沒搬成 {j['fail_n']}</span>" if j.get('fail_n') else '')
                     + (f"<br>最近 10 分鐘 <b>{fmt_b(j.get('rate'))}/s</b>・平均 {fmt_b(j.get('avg'))}/s・硬碟讀寫 {fmt_b(j.get('io'))}/s・已經跑了 {int(j.get('act', 0) // 3600)} 小時 {int(j.get('act', 0) % 3600 // 60)} 分"
                        + (f"<br>⏱ 預計完成 <b style='color:#4dd68a'>{time.strftime('%m/%d %H:%M', time.localtime(j['fin_at']))}</b>（還要 {int(j['eta'] // 3600)} 小時 {int(j['eta'] % 3600 // 60)} 分）" if j.get('eta') else '') if busy else '')
                     + ''.join(f"<br><b>{t}:</b> 好了 {v['done_n']:,} 個 {fmt_b(v['done_b'])}・還剩 {v['pend_n']:,} 個 {fmt_b(v['pend_b'])}" for t, v in (j.get('per') or {}).items())
                     + (f"<br>📥 複製到 {C.get('copy_t')}:：{_hesc(C['copy'])}" if C.get('copy') else '') + (f"<br>🔎 比對 {C.get('verify_t')}:：{_hesc(C['verify'])}" if C.get('verify') else ''))
                if st == 'done':
                    s += f"<br><br><b>{P.get('src')}: 上還剩 {j.get('left_n', 0)} 個檔</b>" + ('・已經清空 ✔' if not j.get('left_n') else '：' + '<br>'.join(_hesc(x) for x in j.get('left_ex') or []))
            if st == 'pause':
                s = ("<div style='color:#f0c27a;font-size:15px'>⏳ 收尾中：手上正在搬的做完、確認完就停，請等一下…（還不要關機）</div>" if j.get('draining') else
                     f"<div style='color:#4dd68a;font-size:15px'>✔ 已停好，可以關機了。重開機後<b>不會自己開始</b>，按「▶ 繼續轉移」才會從 {float(j.get('pct') or 0):.1f}% 接著搬。</div>") + \
                    ''.join(f"<div>{'✔' if c.get('ok') else '⚠'} {c.get('role')}：原本 {c.get('X')}:（{_hesc(c.get('label') or '')}）" + ('' if c.get('ok') else (f" → 現在是 {c['found']}:" if c.get('found') else ' → 找不到')) + '</div>' for c in (j.get('vols') or [])) + s
            self.st.setText(s)
            A = j.get('pace') or {}; run = st == 'run'
            if not self.sl.isSliderDown():
                self.sl.blockSignals(True); self.sl.setValue(max(1, int(A.get('man') or 100) // 5)); self.sl.blockSignals(False); self.slv.setText(f"{A.get('man') or 100}%")
            self.b_smart.setChecked(bool(A.get('smart'))); self.b_smart.setText('🧠 智能（開）' if A.get('smart') else '🧠 智能')
            self.sl.setStyleSheet('' if not A.get('smart') else 'QSlider{opacity:0.5}')
            jv_ = self.ver.findData(A.get('verify') or 'quick')
            if jv_ >= 0 and not self.ver.view().isVisible(): self.ver.setCurrentIndex(jv_)
            j_ = self.ser.findData(A.get('ser') or 'auto')
            if j_ >= 0 and not self.ser.view().isVisible(): self.ser.setCurrentIndex(j_)
            B = A.get('busy') or {}
            self.pinf.setText((f"現在用 <b>{A.get('pct')}%</b>・{_hesc(A.get('why') or '')}・{'一次寫一顆（U、V 輪流）' if A.get('serial') else '兩顆同時寫（R 同時讀兩個檔）'}" if run else
                               ('🧠 智能：自己看 TikLive、CPU、溫度、硬碟忙不忙來調' if A.get('smart') else '✋ 手動：照拉桿的百分比（TikLive 要用時一樣會自動讓）'))
                              + (f"・🌡 {A['temp']:.0f}°C" if A.get('temp') else '') + ('・💽 ' + ' '.join(f'{x}: {b}%' for x, b in B.items()) if B else '')
                              + ''.join(f"<br><small>{_hesc(x)}</small>" for x in (A.get('log') or [])[:3]))
            self.gf.setVisible(busy)
            DV = j.get('drv') or []; self.dk.setVisible(busy and bool(DV)); T_ = list(P.get('tgts') or [])
            for i_, w_ in enumerate(self.dkw):
                if i_ < len(DV):
                    X_ = DV[i_]['X']; w_.set(DV[i_], '#f0a33a' if X_ == P.get('src') else '#2f9bff' if T_ and X_ == T_[0] else '#26b39a'); w_.show()
                else: w_.hide()
            FC_ = list(j.get('f_copies') or ([j['f_copy']] if j.get('f_copy') else []))
            for k_, F_ in (('c0', FC_[0] if FC_ else None), ('c1', FC_[1] if len(FC_) > 1 else None), ('v', j.get('f_ver'))):
                nm, pb = self.fr[k_]
                if F_:
                    nm.setText(f"<b>{_hesc(F_['name'])}</b>　→ {F_['tgt']}:　{fmt_b(F_['size'])}　" + ('⏳ 等另一邊用完硬碟' if F_.get('wait') else f"{fmt_b(F_['bps'])}/s・{F_['sec']:.0f} 秒"))
                    nm.setToolTip(F_.get('dst') or ''); pb.setValue(int(F_['pct'] * 10)); pb.setFormat(f"{F_['pct']:.1f}%　{fmt_b(F_['done'])}／{fmt_b(F_['size'])}")
                else: nm.setText('<span style="color:#888">沒有</span>'); pb.setValue(0); pb.setFormat('')
            R_ = j.get('recent') or []; self.rec.setRowCount(len(R_))
            for i_, r_ in enumerate(R_):
                vals = ['✔' if r_.get('ok') else '✖', r_.get('n', ''), fmt_b(r_.get('b')), (r_.get('t') or '?') + ':',
                        f"{r_.get('dc', 0):.0f} 秒／{r_.get('dv', 0):.0f} 秒" if r_.get('ok') else (r_.get('err') or ''), time.strftime('%H:%M:%S', time.localtime(r_.get('ts', 0)))]
                for c_, x_ in enumerate(vals):
                    it_ = QTableWidgetItem(str(x_))
                    if c_ == 0: it_.setForeground(QColor('#4dd68a' if r_.get('ok') else '#ff6b6b'))
                    if c_ == 1: it_.setToolTip(r_.get('d') or '')
                    self.rec.setItem(i_, c_, it_)
            F = j.get('fails') or []
            self.fail.setPlainText('\n'.join(f"{x['src']}　← {x.get('err') or ''}" for x in F) if F else '（沒有）')
        except Exception: ENG.log.err('🚚 R 碟搬移畫面')


class MovePage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.plan = None
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10)
        t = QLabel('🚚 搬硬碟：把一顆硬碟的所有檔案搬到另一顆（空出來給你用）'); t.setObjectName('title')
        th_ = QHBoxLayout(); th_.addWidget(t, 1); self.b_smap = QPushButton('💽 空間地圖'); self.b_smap.setToolTip('🧪 每顆硬碟裡 S／A／E／F／未分級 各佔多少'); self.b_smap.clicked.connect(win.space_dlg)
        self.b_smap.setVisible(bool(lab_cfg().get('space_map'))); th_.addWidget(self.b_smap)
        self.b_empty = QPushButton('🧹 空資料夾'); self.b_empty.setToolTip('🧪 找出搬完、整理完留下的空資料夾，勾選後刪掉'); self.b_empty.clicked.connect(win.empty_dlg)
        self.b_empty.setVisible(bool(lab_cfg().get('empty_dirs'))); th_.addWidget(self.b_empty)
        self.b_pcs = QPushButton('🖥 硬碟在哪台'); self.b_pcs.setToolTip('🧪 每顆硬碟的紀錄最後是哪台電腦寫的'); self.b_pcs.clicked.connect(win.pcs_dlg)
        self.b_pcs.setVisible(bool(lab_cfg().get('pc_overview'))); th_.addWidget(self.b_pcs); v.addLayout(th_)
        g = QGroupBox('要怎麼搬'); f = QFormLayout(g); v.addWidget(g)
        self.src = QComboBox(); self.dst = QComboBox(); self.name = QLineEdit(); self.name.setPlaceholderText('放到目的硬碟的哪個資料夾')
        self.spd = QComboBox()
        for k_, n_ in ENG.MV_SPEEDS: self.spd.addItem(n_, k_)
        self.spd.setCurrentIndex(max(0, self.spd.findData(60)))
        b_rf = QPushButton('🔄 重新讀硬碟'); rs = QHBoxLayout(); rs.addWidget(self.src, 1); rs.addWidget(b_rf)
        f.addRow('從（要清空的）', rs); f.addRow('搬到', self.dst); f.addRow('放在目的硬碟的資料夾', self.name); f.addRow('速度', self.spd)
        f.addRow(self._note('• 所有檔案都搬（影片、照片、文件…），資料夾結構照舊，放到「目的:\\資料夾名稱\\」底下。\n'
                            '• VideoSIFT（初剪、歸檔、待刪）和 DELETE 會併到目的硬碟本來的 VideoSIFT、DELETE 裡（同名的檔不會蓋掉，自動改名）。\n'
                            '• 分級、備註、初剪紀錄、預覽圖都跟著過去，不用重做。每個檔：複製 → 比對一樣 → 改紀錄 → 才刪原檔；比對不一樣就不刪。\n'
                            '• 優先權低、照速度限速、一次只用 4 MB 記憶體；電腦很忙（CPU 超過「後台」設定的上限）時放慢一半，但不會停，一定會一直前進。\n'
                            '• 10 分鐘內還在被改的檔（例如 TikLive 正在錄）最後再搬；搬的時候這顆先不做預覽圖、轉檔。程式關掉、熱更新後會接著搬。'))
        r = QHBoxLayout(); v.addLayout(r)
        self.b_plan = QPushButton('🔍 先算一下（幾個檔、多大、空間夠不夠）'); self.b_go = QPushButton('▶ 開始搬'); self.b_go.setObjectName('start')
        self.b_pause = QPushButton('⏸ 暫停'); self.b_stop = QPushButton('⏹ 停止'); self.b_clear = QPushButton('清掉這次的紀錄')
        for w_ in (self.b_plan, self.b_go, self.b_pause, self.b_stop, self.b_clear): r.addWidget(w_)
        r.addStretch(1)
        self.pinfo = QLabel(''); self.pinfo.setWordWrap(True); self.pinfo.setTextFormat(Qt.RichText); v.addWidget(self.pinfo)
        self.bar = QProgressBar(); self.bar.setRange(0, 1000); v.addWidget(self.bar)
        self.st = QLabel(''); self.st.setWordWrap(True); self.st.setTextFormat(Qt.RichText); v.addWidget(self.st)
        g2 = QGroupBox('沒搬成的（原檔都還在）'); g2v = QVBoxLayout(g2); v.addWidget(g2, 1)
        self.fail = QPlainTextEdit(); self.fail.setReadOnly(True); self.fail.setMinimumHeight(140); g2v.addWidget(self.fail)
        b_rf.clicked.connect(self.load_drives); self.src.currentIndexChanged.connect(self._src_changed)
        self.b_plan.clicked.connect(self._plan); self.b_go.clicked.connect(self._go)
        self.b_pause.clicked.connect(lambda: (ENG.move_ctl('resume' if ENG.bg_pause.get('move') else 'pause'), self.refresh()))
        self.b_stop.clicked.connect(lambda: QMessageBox.question(self, '停止', '做完手上這個檔就停？（已經搬過去的照樣算數，之後可以再開始，會從剩下的接著搬）') == QMessageBox.Yes and (ENG.move_ctl('stop'), self.refresh()))
        self.b_clear.clicked.connect(lambda: (ENG.move_ctl('clear'), self.refresh()))
        self.spd.currentIndexChanged.connect(lambda _i: ENG.move_speed(self.spd.currentData()))
        self.load_drives(); self.tm = QTimer(self); self.tm.timeout.connect(self.refresh); self.tm.start(1000)

    @staticmethod
    def _note(s):
        l = QLabel(s); l.setObjectName('muted'); l.setWordWrap(True); return l

    def load_drives(self):
        def get():
            out = []
            for sn, X in sorted(ENG.vol_letters().items(), key=lambda x: x[1]):
                try: du = shutil.disk_usage(X + ':\\'); out.append((X, ENG.vol_label(X + ':\\') or '', du.total - du.free, du.free, du.total))
                except Exception: pass
            return out
        bg(get, self._drives)

    def _drives(self, L):
        cs, cd = self.src.currentData(), self.dst.currentData()
        for cb in (self.src, self.dst):
            cb.blockSignals(True); cb.clear()
            for X, lb, used, free, tot in L: cb.addItem(f'{X}:（{lb or "沒有名稱"}）用了 {fmt_b(used)}・剩 {fmt_b(free)}', X)
            cb.blockSignals(False)
        J = ENG.cfg.get('disk_move') or {}
        for cb, want in ((self.src, (J.get('src') or '')[:1] or cs), (self.dst, (J.get('dst') or '')[:1] or cd)):
            i = cb.findData(want)
            if i >= 0: cb.setCurrentIndex(i)
        self._src_changed()

    def _src_changed(self, *_a):
        X = self.src.currentData()
        if not X: return
        J = ENG.cfg.get('disk_move') or {}
        if J.get('name') and (J.get('src') or '')[:1] == X: self.name.setText(J['name']); return
        try: lb = ENG.vol_label(X + ':\\')
        except Exception: lb = ''
        self.name.setText(f'{X}槽_{lb}' if lb else f'{X}槽'); self.plan = None; self.pinfo.setText('')

    def _plan(self):
        S, D = self.src.currentData(), self.dst.currentData()
        if not S or not D or S == D: self.win.msg('來源和目的要選兩顆不同的硬碟'); return
        self.pinfo.setText(f'計算 {S}: 有多少檔中…（只讀，不會動任何檔）'); self.b_plan.setEnabled(False)
        bg(lambda: ENG.move_plan(S, D), self._plan_done, lambda _e: self.b_plan.setEnabled(True))

    def _plan_done(self, P):
        self.b_plan.setEnabled(True); self.plan = P; sp = int(self.spd.currentData() or 0)
        eta = (P['bytes'] / (sp * 1e6)) if sp else 0
        self.pinfo.setText(f"要搬 <b>{P['n']:,}</b> 個檔、<b>{fmt_b(P['bytes'])}</b>；目的硬碟剩 {fmt_b(P['free']) if P['free'] is not None else '?'}　" +
                           ("<span style='color:#45d483'>✔ 空間夠</span>" if P['fits'] else "<span style='color:#ff4d6d'>✖ 空間不夠</span>") +
                           (f"　照這個速度大約 {eta_txt(eta)}" if eta else '') + (f"　（{P['skip']} 個讀不到）" if P['skip'] else ''))

    def _go(self):
        S, D, nm = self.src.currentData(), self.dst.currentData(), self.name.text().strip()
        if not S or not D or S == D: self.win.msg('來源和目的要選兩顆不同的硬碟'); return
        if self.plan is not None and not self.plan.get('fits'): QMessageBox.warning(self, '搬硬碟', '目的硬碟空間不夠'); return
        if QMessageBox.question(self, '搬硬碟', f'把 {S}: 的所有檔案搬到 {D}:\\{nm or S + "槽"}\\？\n\n（VideoSIFT、DELETE 併到 {D}: 的同名資料夾）\n'
                                '每個檔都會先複製、比對一樣才刪 ' + f'{S}: 的原檔；分級、預覽圖都跟著過去。\n背景慢慢搬，可以隨時暫停。') != QMessageBox.Yes: return
        r = ENG.move_start(S, D, nm, self.spd.currentData()); self.win.msg(r.get('message', '')); self.refresh()

    def refresh(self):
        if not self.isVisible(): return
        bg(ENG.move_view, self._show)

    def _show(self, V):
        on = bool(V.get('on')); st = V.get('state') if on else ''
        busy = st in ('run', 'pause')
        for w_ in (self.src, self.dst, self.name, self.b_go, self.b_plan): w_.setEnabled(not busy)
        self.b_pause.setEnabled(busy); self.b_stop.setEnabled(busy); self.b_clear.setEnabled(st in ('done', 'stop'))
        paused = bool(ENG.bg_pause.get('move')); self.b_pause.setText('▶ 繼續' if paused else '⏸ 暫停')
        if on and int(V.get('speed') or 0) != int(self.spd.currentData() or 0):
            self.spd.blockSignals(True); self.spd.setCurrentIndex(max(0, self.spd.findData(int(V.get('speed') or 0)))); self.spd.blockSignals(False)
        if not on: self.bar.setValue(0); self.st.setText('還沒開始。選好「從」「搬到」，先按「🔍 先算一下」，再按「▶ 開始搬」。'); self.fail.setPlainText(''); return
        tb = int(V.get('total_b') or 0); db = int(V.get('done_b') or 0); self.bar.setValue(int(db * 1000 / tb) if tb else (1000 if st == 'done' else 0))
        self.bar.setFormat(f'{db * 100 / tb:.1f}%' if tb else '')
        nm = {'run': '▶ 搬檔中', 'pause': '⏸ 暫停中', 'stop': '⏹ 停了', 'done': '✔ 搬完了'}.get(st, st)
        self.st.setText(f"<b>{nm}</b>　{V['src']} → {V['dst']}\\{esc_html(V.get('name') or '')}　已搬 <b>{int(V.get('done_n') or 0):,}</b>" + (f"／{int(V.get('total_n') or 0):,}" if V.get('total_n') else '') +
                        f" 個檔・{fmt_b(db)}" + (f"／{fmt_b(tb)}" if tb else '') +
                        (f"　現在 {V['speed_now'] / 1e6:.0f} MB/秒" if V.get('run') and V.get('speed_now') else '') + (f"　還要大約 {eta_txt(V['eta'])}" if V.get('eta') else '') +
                        (f"<br><span style='color:#8a96a8'>{esc_html(V.get('phase') or '')}：{esc_html(V.get('cur') or '')}</span>" if V.get('run') else ''))
        F = V.get('fail') or []; txt = '\n'.join(F) if F else '（沒有）'
        if self.fail.toPlainText() != txt: self.fail.setPlainText(txt)


class LearnPage(QWidget):
    """每一類檔案（編碼＋解析度＋影格率＋位元率）轉了幾次、選到的 CQ、現在用哪種方式（完整測試／少量確認／快速確認／直接套用＋抽查）、抽查結果、最近的決定."""
    def __init__(self, win):
        super().__init__(); self.win = win; self.V = None
        v = QVBoxLayout(self); v.setContentsMargins(10, 8, 10, 8)
        t = QLabel('📈 滾動式參數：🎯 自動轉檔累積的經驗。同一類的檔轉越多，樣本取越少（5 段×2 秒 → 3 段×2 秒 → 3 段×1 秒）；經驗夠多、CQ 很集中、抽查都過，就直接套用不先測（轉完照機率抽查）。'
                   '抽查低於底線就用更保守的 CQ 重轉，這一類先退回完整測試、抽查變多。'); t.setWordWrap(True); v.addWidget(t)
        g = QGroupBox('規則（改了馬上用）'); gl = QGridLayout(g); v.addWidget(g)
        C = ENG.learn_cfg()
        self.on = QCheckBox('用經驗（關掉＝每一部都完整測試）'); self.on.setChecked(C['on'])
        self.lite = QSpinBox(); self.lite.setRange(1, 1000); self.lite.setValue(C['lite_n']); self.lite.setSuffix(' 次經驗以上')
        self.quick = QSpinBox(); self.quick.setRange(1, 1000); self.quick.setValue(C['quick_n']); self.quick.setSuffix(' 次經驗以上')
        self.trust = QSpinBox(); self.trust.setRange(5, 5000); self.trust.setValue(C['trust_n']); self.trust.setSuffix(' 次經驗以上')
        self.floor = QSpinBox(); self.floor.setRange(900, 995); self.floor.setValue(int(round(C['floor'] * 1000))); self.floor.setPrefix('底線 SSIM 0.')
        self.spot = QSpinBox(); self.spot.setRange(1, 100); self.spot.setValue(int(round(C['spot'] * 100))); self.spot.setSuffix(' %'); self.spot.setPrefix('抽查機率 ')
        gl.addWidget(self.on, 0, 0, 1, 2); gl.addWidget(QLabel('少量確認（3 段×2 秒）'), 1, 0); gl.addWidget(self.lite, 1, 1); gl.addWidget(QLabel('快速確認（3 段×1 秒）'), 1, 2); gl.addWidget(self.quick, 1, 3)
        gl.addWidget(QLabel('直接套用（不先測）'), 2, 0); gl.addWidget(self.trust, 2, 1); gl.addWidget(self.floor, 2, 2); gl.addWidget(self.spot, 2, 3)
        tip = QLabel(f'目標 SSIM 在「轉檔 → 轉檔中 → 轉檔方式」設定（現在 {float(ENG.cfg.get("cv_target") or 0.985):.3f}）；底線以下一定重轉。直接套用時抽查機率會自己調：抽查都過就慢慢降（最低 5%），沒過就加倍。')
        tip.setObjectName('muted'); tip.setWordWrap(True); gl.addWidget(tip, 3, 0, 1, 4)
        for w in (self.on,): w.toggled.connect(self._save)
        for w in (self.lite, self.quick, self.trust, self.floor, self.spot): w.valueChanged.connect(self._save)
        self.sum = QLabel(''); self.sum.setWordWrap(True); self.sum.setTextFormat(Qt.RichText); v.addWidget(self.sum)
        self.ct = _table(['類型', '經驗', '下一部會怎麼做', 'CQ 中間值（範圍）', '樣本 SSIM 平均', '抽查（沒過）', '抽查機率', '平均變成原檔的', '最近'], (260, 60, 230, 130, 110, 100, 80, 110, 110))
        self.ct.itemSelectionChanged.connect(self._sel); v.addWidget(self.ct, 2)
        self.dist = QLabel('點一類看 CQ 分布'); self.dist.setWordWrap(True); self.dist.setTextFormat(Qt.RichText); v.addWidget(self.dist)
        self.b_ref = QPushButton('🔄 重新整理'); self.b_rm = QPushButton('清掉選取那一類的經驗'); self.b_all = QPushButton('全部經驗清掉'); self.b_all.setStyleSheet('QPushButton{color:#ff6577}')
        self.b_exp = QPushButton('📤 匯出全部經驗（CSV，Excel 可以開）'); self.b_exp.clicked.connect(lambda: bg(ENG.learn_export, lambda r: (self.win.msg(f"匯出 {r['n']} 筆 → {r['path']}", 8000), core.explorer_select(r['path']))))
        v.addWidget(flow_row([self.b_ref, self.b_exp, self.b_rm, self.b_all]))
        lt = QLabel('最近的決定'); lt.setStyleSheet('font-weight:800'); v.addWidget(lt)
        self.rt = _table(['時間', '檔名', '類型', '方式', 'CQ', '樣本 SSIM', '抽查', '變成原檔的', '找了幾秒', '備註'], (110, 260, 220, 80, 50, 90, 80, 90, 70, 200)); v.addWidget(self.rt, 2)
        lt2 = QLabel('📜 LOG（🎯 找設定、📈 經驗、抽查）'); lt2.setStyleSheet('font-weight:800'); v.addWidget(lt2)
        self.logv = QPlainTextEdit(); self.logv.setReadOnly(True); self.logv.setMaximumHeight(170); self.logv.setLineWrapMode(QPlainTextEdit.NoWrap); v.addWidget(self.logv)
        self.b_ref.clicked.connect(self.refresh); self.b_rm.clicked.connect(self._rm); self.b_all.clicked.connect(self._rm_all)
        self.tm = QTimer(self); self.tm.timeout.connect(lambda: self.refresh() if self.isVisible() else None); self.tm.start(5000)

    def _save(self, *_a):
        L = {'on': self.on.isChecked(), 'lite_n': self.lite.value(), 'quick_n': self.quick.value(), 'trust_n': self.trust.value(), 'floor': round(self.floor.value() / 1000, 3), 'spot': round(self.spot.value() / 100, 2)}
        ENG.cfg.set('learn', L)

    def refresh(self):
        bg(ENG.learn_view, self._got); bg(lambda: ENG.log_grep(['📈', '🎯', '抽查'], 300), self._log)

    def _log(self, L):
        t_ = '\n'.join(L)
        if t_ != self.logv.toPlainText():
            sb = self.logv.verticalScrollBar(); end = sb.value() >= sb.maximum() - 4; self.logv.setPlainText(t_)
            if end: sb.setValue(sb.maximum())

    def _got(self, V):
        self.V = V; C = V['classes']; MN = {'full': '完整測試', 'lite': '少量確認', 'quick': '快速確認', 'trust': '直接套用＋抽查'}
        tr = sum(1 for c in C if c['mode'] == 'trust')
        self.sum.setText(f"共 <b>{V['total']:,}</b> 次經驗、<b>{len(C)}</b> 類；{tr} 類已經可以直接套用。" + ('' if V['cfg']['on'] else '　<b style="color:#f0ad4e">（經驗關掉了：每一部都完整測試）</b>'))
        cur = self.ct.currentRow(); self.ct.setRowCount(len(C))
        for i, c in enumerate(C):
            vals = (c['cls'], f"{c['n']:,}", MN.get(c['mode'], c['mode']), f"{c['q_med']}（{c['q_min']}～{c['q_max']}）", f"{c['ssim_avg']:.4f}" if c.get('ssim_avg') else '—',
                    f"{c['spots']}（{c['spot_bad']}）", f"{c['spot_rate'] * 100:.0f}%", f"{c['ratio_avg'] * 100:.0f}%" if c.get('ratio_avg') else '—',
                    time.strftime('%m-%d %H:%M', time.localtime(c['last_t'])) if c.get('last_t') else '')
            for j, val in enumerate(vals):
                col = {'trust': '#45d483', 'quick': '#4dc9ff', 'lite': '#b48cff', 'full': None}.get(c['mode']) if j == 2 else ('#ff6577' if j == 5 and c['spot_bad'] else None)
                self.ct.setItem(i, j, _ti(val, c.get('reason') if j == 2 else val, None, col))
        if 0 <= cur < len(C): self.ct.selectRow(cur)
        R = V['recent']; self.rt.setRowCount(len(R))
        for i, x in enumerate(R):
            vals = (time.strftime('%m-%d %H:%M:%S', time.localtime(x.get('t') or 0)), x.get('name', ''), x.get('cls', ''), MN.get(x.get('mode'), x.get('mode', '')), str(x.get('q', '')),
                    f"{x['ssim']:.4f}" if x.get('ssim') else '—', f"{x['spot']:.4f}" if x.get('spot') is not None else '', f"{x['ratio'] * 100:.0f}%" if x.get('ratio') else '',
                    f"{x.get('sec', 0):.0f}" if x.get('sec') else '', x.get('note', ''))
            for j, val in enumerate(vals):
                col = ('#ff6577' if x.get('spot') is not None and x['spot'] < V['cfg']['floor'] else '#45d483') if j == 6 and x.get('spot') is not None else None
                it = self.rt.item(i, j)
                if it is None or it.text() != val: self.rt.setItem(i, j, _ti(val, val, None, col))
        self._sel()

    def _sel(self):
        i = self.ct.currentRow(); C = (self.V or {}).get('classes') or []
        if not (0 <= i < len(C)): return
        c = C[i]; D = c['dist']; mx = max(D.values()) if D else 1
        bars = '　'.join(f"CQ{q}：{'█' * max(1, round(n * 12 / mx))} {n}" for q, n in sorted(D.items(), key=lambda kv: int(kv[0])))
        self.dist.setText(f"<b>{c['cls']}</b>　{c['reason']}<br>最近 60 次選到的 CQ：{bars}")

    def _rm(self):
        i = self.ct.currentRow(); C = (self.V or {}).get('classes') or []
        if not (0 <= i < len(C)): self.win.msg('先點一類'); return
        c = C[i]['cls']
        if QMessageBox.question(self, '清掉經驗', f'清掉「{c}」的 {C[i]["n"]} 次經驗？之後這一類從完整測試重新開始。') != QMessageBox.Yes: return
        bg(lambda: ENG.learn_reset(c), lambda _r: self.refresh())

    def _rm_all(self):
        if QMessageBox.question(self, '全部清掉', '清掉全部的經驗？之後每一類都從完整測試重新開始。') != QMessageBox.Yes: return
        bg(lambda: ENG.learn_reset(None), lambda _r: self.refresh())


# ============================================================ 後台
BG_ST = {'run': ('▶ 進行中', '#45d483'), 'wait': ('⏳ 排隊中', '#f0ad4e'), 'pause': ('⏸ 暫停中', '#ff4d6d'), 'idle': ('— 沒事', '#7f8a99'), 'err': ('✖ 出錯', '#ff4d6d')}


class OverviewPanel(QWidget):
    """後台總覽：每一件事一張卡片（在做哪個檔、進度條、剩幾個、處理速度、還要多久）."""
    def __init__(self, win, compact=False):
        super().__init__(); self.win = win; self.compact = compact; self.v = QVBoxLayout(self); self.v.setContentsMargins(0, 0, 0, 0); self.v.setSpacing(6); self.sig = None; self.cards = {}

    def refresh(self): bg(ENG.bg_overview, self.show_data)

    def show_data(self, L):
        if not self.compact: L = L
        else: L = [o for o in L if o['state'] != 'idle']
        sig = tuple((o['k'], len(o['items'])) for o in L)
        if sig != self.sig:
            while self.v.count():
                it = self.v.takeAt(0); w_ = it.widget()
                if w_ is not None: w_.setParent(None); w_.deleteLater()
            self.cards = {}
            for o in L:
                c = QFrame(); c.setObjectName('card'); cl = QVBoxLayout(c); cl.setContentsMargins(10, 7, 10, 7); cl.setSpacing(3)
                h = QHBoxLayout(); t = QLabel(); t.setStyleSheet('font-weight:800;background:transparent'); st = QLabel(); st.setStyleSheet('background:transparent;font-weight:700')
                info = shrinkable(QLabel()); info.setObjectName('muted'); info.setStyleSheet('background:transparent'); info.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                h.addWidget(t); h.addWidget(st); h.addStretch(1); h.addWidget(info, 2); cl.addLayout(h)
                rows = []
                for _x in o['items']:
                    rr = QHBoxLayout(); lb = shrinkable(QLabel()); lb.setStyleSheet('background:transparent'); pb = QProgressBar(); pb.setRange(0, 1000); pb.setFixedHeight(10); pb.setTextVisible(False)
                    sub = QLabel(); sub.setObjectName('muted'); sub.setStyleSheet('background:transparent')
                    rr.addWidget(lb, 3); rr.addWidget(pb, 2); rr.addWidget(sub, 1); cl.addLayout(rr); rows.append((lb, pb, sub))
                note = QLabel(); note.setObjectName('muted'); note.setStyleSheet('background:transparent'); note.setWordWrap(True); cl.addWidget(note)
                self.v.addWidget(c); self.cards[o['k']] = (t, st, info, rows, note)
            self.v.addStretch(1); self.sig = sig
        for o in L:
            t2, st2, info2, rows2, note2 = self.cards[o['k']]; nm, col = BG_ST.get(o['state'], (o['state'], '#7f8a99'))
            t2.setText(f"{o['icon']} {o['name']}"); st2.setText(nm); st2.setStyleSheet(f'background:transparent;font-weight:700;color:{col}')
            bits = []
            if o.get('left') is not None: bits.append(f"剩 {o['left']:,} 個")
            if o.get('speed'): bits.append(str(o['speed']))
            if o.get('eta'): bits.append('還要 ' + eta_txt(o['eta']))
            info2.setText('　·　'.join(bits))
            for (lb, pb, sub), x in zip(rows2, o['items']):
                lb.setText('　' + str(x.get('name') or '')[:90]); lb.setToolTip(str(x.get('name') or '')); p = x.get('pct')
                pb.setVisible(p is not None); pb.setValue(int((p or 0) * 10)); sub.setText((f'{p:.0f}%　' if p is not None else '') + str(x.get('sub') or ''))
            note2.setText(str(o.get('note') or '')); note2.setVisible(bool(o.get('note')))


class BgPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win
        v = QVBoxLayout(self); v.setContentsMargins(8, 8, 8, 8)
        t = QLabel('🖥 後台總覽：每一件正在跑的事（在做哪個檔、剩幾個、處理速度、還要多久）'); t.setObjectName('title'); t.setWordWrap(True); v.addWidget(t)
        self.sum = QLabel(''); self.sum.setWordWrap(True); self.sum.setTextFormat(Qt.RichText); v.addWidget(self.sum)
        self.fcl = QPushButton(''); self.fcl.setObjectName('pill'); self.fcl.setStyleSheet('text-align:left'); self.fcl.hide()        # V0.5.10 🗂 整理的背景也在這裡看一行
        self.fcl.setToolTip('整理（FileCompare）的背景工作；點一下到「整理的後台」'); self.fcl.clicked.connect(lambda: self.win.enter(42)); v.addWidget(self.fcl)
        r = QHBoxLayout(); v.addLayout(r)
        self.b_scan = QPushButton('🔄 掃描影片庫'); self.b_th = QPushButton('⏸ 暫停預覽圖'); self.b_th.setCheckable(True); self.b_retry = QPushButton('↻ 失敗的預覽圖重做')
        self.b_pack = QPushButton('💾 現在寫到各硬碟（要拔硬碟前按）'); self.b_pack.setToolTip('把每顆硬碟的紀錄、分級、預覽圖位置寫到它自己身上（X:\\VideoSIFT\\.vsdata）；之後拔走接到別台電腦，打開 SortCut 就直接接上')
        self.b_pack.clicked.connect(lambda: (self.b_pack.setEnabled(False), bg(lambda: ENG.pack_export_due(force=True, why='（你按的）'), lambda r_: (self.b_pack.setEnabled(True), self.win.msg('💾 已寫到：' + ('、'.join(x + ':' for x in r_) if r_ else '都是最新的，不用再寫') + self._pack_note())))))
        for w in (self.b_scan, self.b_th, self.b_retry, self.b_pack): r.addWidget(w)
        r.addStretch(1)
        g = QGroupBox('⏯ 總控制：每一項可以暫停／繼續／立刻停、調先後順序（電腦太忙時從最下面的先讓路）'); gv = QVBoxLayout(g); v.addWidget(g)
        self.ct = _table(['順序', '項目', '狀態', '總進度', '停在／最近在做', '', '', '', ''], (50, 150, 110, 200, 330, 80, 80, 36, 36)); self.ct.setSelectionMode(QAbstractItemView.NoSelection)
        self.ct.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch); self.ct.horizontalHeader().setStretchLastSection(False); gv.addWidget(self.ct); self.ct_sig = None; self.ct_w = {}
        self.b_allp = QPushButton('⏸ 全部暫停'); self.b_allr = QPushButton('▶ 全部繼續（照順序慢慢加）'); self.cg = QCheckBox('電腦太忙自動讓路'); self.cmax = QSpinBox(); self.cmax.setRange(50, 100); self.cmax.setPrefix('CPU 超過 '); self.cmax.setSuffix('%')
        self.rsec = QSpinBox(); self.rsec.setRange(0, 300); self.rsec.setPrefix('慢慢加速：每 '); self.rsec.setSuffix(' 秒多開 1 個'); self.rsec.setSpecialValueText('慢慢加速：關')
        self.cg.setChecked((ENG.cfg.get('cpu_guard') is not False)); self.cmax.setValue(int(ENG.cfg.get('cpu_max') or 90)); self.rsec.setValue(int(ENG.cfg.get('bg_ramp_sec') if ENG.cfg.get('bg_ramp_sec') is not None else 20))
        self.ar = QCheckBox('🛟 閃退自動重開並接續'); self.ar.setChecked(ENG.cfg.get('auto_restart') is not False); self.ar.setToolTip('主程式閃退（不是你關的）4 秒後自動重開，背景工作和排隊接著做；改了下次開程式生效')
        self.ar.toggled.connect(lambda on: ENG.cfg.set('auto_restart', bool(on)))
        self.mfc = QCheckBox('🛟 主程式優先（畫面、手機永遠先；一卡背景馬上退到最低）'); self.mfc.setChecked(ENG.cfg.get('main_first') is not False)
        self.mfc.setToolTip('V0.6.08：畫面慢了 0.4 秒或手機請求卡 2.5 秒 → 背景工作全部不開新的、同時只做 1 個、FFmpeg 壓到 5%；順了 20 秒才慢慢放回來。\n也會把畫面和手機的執行緒排在前面、背景的排在後面（CPU 100% 時畫面照樣能動）')
        self.mfc.toggled.connect(lambda on: ENG.cfg.set('main_first', bool(on)))
        gv.addWidget(flow_row([self.b_allp, self.b_allr, self.mfc, self.cg, self.cmax, self.rsec, self.ar]))
        self.mfl = QLabel(''); self.mfl.setWordWrap(True); self.mfl.setStyleSheet('color:#f0c27a'); gv.addWidget(self.mfl)
        self.glog = QLabel(''); self.glog.setObjectName('muted'); self.glog.setWordWrap(True); gv.addWidget(self.glog)
        self.b_allp.clicked.connect(lambda: (ENG.bg_all(True), self.refresh_ctl())); self.b_allr.clicked.connect(lambda: (ENG.bg_all(False), self.refresh_ctl()))
        self.cg.toggled.connect(lambda on: ENG.cfg.set('cpu_guard', bool(on))); self.cmax.valueChanged.connect(lambda x: ENG.cfg.set('cpu_max', int(x))); self.rsec.valueChanged.connect(lambda x: ENG.cfg.set('bg_ramp_sec', int(x)))
        self.dk = QTableWidget(0, 8); self.dk.setHorizontalHeaderLabels(['硬碟', '種類', '忙碌', '讀／寫', '我們在做', '同時', '預覽圖預計還要', '狀態']); self.dk.verticalHeader().setVisible(False)
        self.dk.setEditTriggers(QAbstractItemView.NoEditTriggers); self.dk.horizontalHeader().setStretchLastSection(True); self.dk.setMaximumHeight(150)
        for i, w in enumerate((260, 60, 60, 130, 150, 50, 120)): self.dk.setColumnWidth(i, w)
        self.dk.setToolTip('每顆實體硬碟分開排隊：HDD 一次只讀一部（讀頭不用來回跳，整體比較快），SSD 可以同時好幾部；別的程式正在大量用硬碟時先等'); v.addWidget(self.dk)
        gu = QGroupBox('🔌 USB 外接硬碟保護（V0.1.91）：避免大量讀寫把外接硬碟壓到斷線；斷線了自動把那個 USB 連接埠重新啟動（不用重開機）'); gul = QVBoxLayout(gu); v.addWidget(gu)
        self.u_per = QSpinBox(); self.u_per.setRange(1, 4); self.u_per.setPrefix('同一顆 HDD／USB 硬碟同時轉 '); self.u_per.setSuffix(' 部'); self.u_per.setValue(max(1, int(ENG.cfg.get('cv_per_disk') or 1)))
        self.u_tmp = QCheckBox('轉檔暫存先寫在本機（程式所在的硬碟），轉好再搬過去'); self.u_tmp.setChecked(ENG.cfg.get('cv_local_tmp') is not False)
        self.u_on = QCheckBox('斷線 45 秒沒回來：自動重啟那個 USB'); self.u_on.setChecked(((ENG.cfg.get('usb_guard') or {}) if isinstance(ENG.cfg.get('usb_guard'), dict) else {}).get('on', True) is not False)
        self.u_set = QPushButton('🔌 設定自動救回＋關掉 USB 省電（問一次系統管理員）'); self.u_map = QPushButton('🔁 重新讀 USB 線路'); self.u_now = QPushButton('🚑 立刻救回離線的硬碟')
        gul.addWidget(flow_row([self.u_per, self.u_tmp, self.u_on])); gul.addWidget(flow_row([self.u_set, self.u_map, self.u_now]))
        self.u_st = QLabel(''); self.u_st.setObjectName('muted'); self.u_st.setWordWrap(True); self.u_st.setTextFormat(Qt.RichText); gul.addWidget(self.u_st)
        self.u_per.valueChanged.connect(lambda x: ENG.cfg.set('cv_per_disk', int(x))); self.u_tmp.toggled.connect(lambda on: ENG.cfg.set('cv_local_tmp', bool(on)))
        self.u_on.toggled.connect(lambda on: ENG.cfg.set('usb_guard', dict((ENG.cfg.get('usb_guard') if isinstance(ENG.cfg.get('usb_guard'), dict) else {}), on=bool(on))))
        U = lambda: getattr(ENG, 'usb', None)
        self.u_set.clicked.connect(lambda: U() and bg(U().setup, lambda r: self.win.msg('🔌 ' + r['message'], 12000)))
        self.u_map.clicked.connect(lambda: U() and bg(U().refresh_map, lambda m: (self.win.msg(f'🔌 讀到 {len(m or {})} 個磁碟代號的線路'), self._usb())))
        self.u_now.clicked.connect(self._usb_now); self._usb_t = 0
        self.act = QWidget(); self.al = QVBoxLayout(self.act); self.al.setContentsMargins(0, 0, 0, 0); self.bars = {}          # 舊版的進度條（改用下面的總覽）
        sa = QScrollArea(); sa.setWidgetResizable(True); self.ov = OverviewPanel(win); sa.setWidget(self.ov); sa.setMinimumHeight(260)
        sp = QSplitter(Qt.Vertical); sp.addWidget(sa); v.addWidget(sp, 1); self.bg_split = sp
        self.tb = QTableWidget(0, 5); self.tb.setHorizontalHeaderLabels(['時間', '種類', '工作', '狀態', '說明']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.horizontalHeader().setStretchLastSection(True)
        for i, w in enumerate((130, 70, 360, 70)): self.tb.setColumnWidth(i, w)
        sp.addWidget(self.tb); sp.setSizes([520, 260])
        self.b_scan.clicked.connect(lambda: self.win.msg('開始掃描' if ENG.scan() else '已經在掃描（或還沒加入影片庫）'))
        self.b_th.toggled.connect(self._pause); self.b_retry.clicked.connect(lambda: bg(ENG.thumb_retry_failed, lambda n: self.win.msg(f'{n} 部重新排隊')))
        self.speed = deque(maxlen=60); self.tm = QTimer(self); self.tm.timeout.connect(self.tick); self.tm.start(1500)

    def refresh_ctl(self):
        bg(ENG.bg_view, self._ctl)
        try:
            f = ENG.fc_bg() if hasattr(ENG, 'fc_bg') else None
            if not isinstance(f, dict): self.fcl.hide(); return
            t_ = [x for x in (('▶ ' + '、'.join(f['run'])) if f['run'] else '', ('⏸ 暫停：' + '、'.join(f['pause'])) if f['pause'] else '',
                              ('⚖ 電腦忙讓路：' + '、'.join(f['auto'])) if f['auto'] else '', ('🤝 ' + f['hold']) if f['hold'] else '') if x]
            self.fcl.setText('🗂 整理（FileCompare）：' + ('　'.join(t_) if t_ else '現在沒有背景工作 ✔') + '　›'); self.fcl.show()
        except Exception: self.fcl.hide()

    def _usb(self):
        u = getattr(ENG, 'usb', None)
        if u is None: self.u_st.setText('USB 保護模組沒有載入（LOG 有原因）'); return
        def got(st):
            if not st.get('win'): self.u_st.setText('只有 Windows 能用'); return
            mp = st.get('map') or {}
            usb = [k for k, x in sorted(mp.items()) if str(x.get('bus') or '').upper() == 'USB']
            off = st.get('pending') or {}
            txt = ('✔ 自動救回已設定' if st.get('installed') else "<span style='color:#f0ad4e'>還沒設定自動救回：按「🔌 設定…」（問一次系統管理員）</span>") + \
                  f"　·　記得線路的磁碟：{'、'.join(sorted(mp)) or '還沒讀'}（USB：{'、'.join(usb) or '無'}）" + \
                  (f"　·　<b style='color:#ff6b6b'>離線中：{'、'.join(f'{k}:（{int(v)} 秒）' for k, v in off.items())}</b>" if off else '')
            last = st.get('last') or []
            if last: txt += '<br>' + '<br>'.join(esc_html(time.strftime('%m-%d %H:%M:%S', time.localtime(x['t'])) + '　' + x['m']) for x in last[-4:])
            self.u_st.setText(txt)
        bg(u.status, got)

    def _usb_now(self):
        u = getattr(ENG, 'usb', None)
        if u is None: return
        offl = sorted({os.path.splitdrive(str(r))[0].rstrip(':').upper() for r in (ENG.offline or {}) if os.path.splitdrive(str(r))[0]} | set((u.pending or {}).keys()))
        if not offl: self.win.msg('🔌 現在沒有離線的硬碟'); return
        if QMessageBox.question(self, 'USB 硬碟', f'重新啟動這些硬碟接的 USB：{"、".join(offl)}？\n（同一個 USB 控制器上的其他裝置可能會斷線幾秒）') != QMessageBox.Yes: return
        for L in offl: bg(lambda L=L: u.rescue(L), lambda r: (self.win.msg('🔌 ' + r['message'], 12000), self._usb()))

    def _ctl(self, V):
        try: L = V['kinds']
        except Exception: return
        sig = tuple(k['k'] for k in L)
        if sig != self.ct_sig:
            self.ct_sig = sig; self.ct.setRowCount(len(L)); self.ct_w = {}
            for i, k in enumerate(L):
                pb = QProgressBar(); pb.setRange(0, 1000); pb.setFixedHeight(16); pb.setTextVisible(True); self.ct.setCellWidget(i, 3, pb)
                bp = QPushButton(); bs = QPushButton('⏹ 立刻停'); bu = QPushButton('↑'); bd = QPushButton('↓')
                bs.setToolTip('正在做的也停掉、放回排隊（下次從頭做那一部）'); bu.setToolTip('往前（比較優先）'); bd.setToolTip('往後（電腦忙時先讓路）')
                for c_, w_ in ((5, bp), (6, bs), (7, bu), (8, bd)): self.ct.setCellWidget(i, c_, w_)
                kk = k['k']
                bp.clicked.connect(lambda _c=False, kk=kk: (ENG.bg_set_pause(kk, not ENG.bg_pause.get(kk)), self.refresh_ctl()))
                bs.clicked.connect(lambda _c=False, kk=kk: (QMessageBox.question(self, '立刻停', '正在做的也停掉，放回排隊（下次從頭做那一部）？') == QMessageBox.Yes) and (ENG.bg_stop_now(kk), self.refresh_ctl()))
                bu.clicked.connect(lambda _c=False, kk=kk: (ENG.bg_move(kk, -1), self.refresh_ctl())); bd.clicked.connect(lambda _c=False, kk=kk: (ENG.bg_move(kk, 1), self.refresh_ctl()))
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
                bpz.setText('▶ 繼續' if k['state'] == 'pause' else '⏸ 暫停'); bsz.setEnabled(bool(k['running']) and k['k'] != 'hotzone')
        M_ = V.get('mf') or {}
        try: self.mfl.setText((f"🛟 主程式優先中（{M_.get('why', '')}）：背景先退開，順了 {M_.get('left', 0)} 秒後慢慢放回來" if M_.get('active') else
                               (f"🛟 畫面很順（慢了 {M_.get('lag_ms', 0)} 毫秒；卡了 {M_.get('n', 0)} 次）" if M_.get('on') else '')))
        except Exception: pass
        self.glog.setText(f"CPU 現在 {V['cpu']:.0f}%　" + ('　'.join(V['log'][:3]) if V.get('log') else '（自動讓路的紀錄會顯示在這裡）'))
        try:
            self.b_th.blockSignals(True); self.b_th.setChecked(bool(ENG.th_paused)); self.b_th.setText('▶ 繼續預覽圖' if ENG.th_paused else '⏸ 暫停預覽圖'); self.b_th.blockSignals(False)
        except Exception: pass

    @staticmethod
    def _pack_note():
        try:
            d, left = ENG.pack_left()
            return f'　（預覽圖還有 {left:,} 部在這台電腦、正在搬到各硬碟；搬完再拔）' if left else '　✔ 預覽圖都在各硬碟上了，可以關掉程式、拔硬碟'
        except Exception: return ''

    def _pause(self, on):
        ENG.th_paused = bool(on); self.b_th.setText('▶ 繼續預覽圖' if on else '⏸ 暫停預覽圖')
        if on:
            for fid in list(ENG.th_active): ENG.thumb_cancel(fid)
        self.win.msg('預覽圖暫停（正在做的那幾部先停，之後重做）' if on else '預覽圖繼續')

    def tick(self):
        if not self.isVisible(): return
        bg(ENG.info, self._info); bg(ENG.disks_view, self._disks); self.ov.refresh(); self.refresh_ctl()
        if time.time() - self._usb_t > 5: self._usb_t = time.time(); self._usb()

    def _disks(self, D):
        self.dk.setRowCount(len(D)); mc = {'HDD': '#f0ad4e', 'SSD': '#45d483', 'NET': '#4dc9ff'}
        for i, d in enumerate(D):
            mb = lambda x: '—' if x is None else f'{x / 1e6:.0f}'
            vals = (d['label'] or d['lane'], d['media'] if d['media'] != '?' else '不明', '—' if d['busy'] is None else f"{d['busy']:.0f}%", f"{mb(d['rd'])}／{mb(d['wr'])} MB/s",
                    f"預覽圖 {d['th']}・讀資訊 {d['pr']}・轉檔 {d['cv']}", '不限' if d['cap'] >= 99 else str(d['cap']),
                    ('✔ 做完了' if d.get('eta') == 0 else (eta_txt(d['eta']) if d.get('eta') else '估算中…')), d['note'] or ('工作中' if d['th'] or d['pr'] or d['cv'] else '閒置'))
            for j, val in enumerate(vals):
                it = self.dk.item(i, j)
                if it is None: it = QTableWidgetItem(); self.dk.setItem(i, j, it)
                if it.text() != str(val): it.setText(str(val)); it.setToolTip(str(val) + ('\n' + '\n'.join(d['roots']) if j == 0 and d['roots'] else ''))
            it1 = self.dk.item(i, 1)
            if it1 is not None: it1.setForeground(QColor(mc.get(d['media'], '#9aa5b3')))

    def _info(self, I):
        s = ENG.scan_st; kinds = {'scan': '掃描', 'thumb': '預覽圖', 'cut': '初剪', 'conv': '轉檔', 'op': '搬檔'}
        TL = ENG.tasks_list(); done = [t for t in TL if t['kind'] == 'thumb' and t['state'] == 'done' and time.time() - t['t1'] < 3600]
        self.sum.setText(
            f"<b>影片庫</b>：{I['files']:,} 部 · {fmt_b(I['bytes'])}　" + (f"<span style='color:#4dc9ff'>掃描中 {s['n']:,} 個…</span>" if s['running'] else '') +
            f"<br><b>讀取影片資訊</b>：還有 {I['probe_left']:,} 部" + (f"（{I['probe_bad']:,} 部讀不出來）" if I['probe_bad'] else '') +
            f"<br><b>預覽圖</b>：好了 {I['th_done']:,} 部 · 還有 {I['th_left']:,} 部（約 {fmt_t(I['th_left_s'] or 0)} 的影片）" + (f" · 失敗 {I['th_fail']:,}" if I['th_fail'] else '') +
            (f" · <span style='color:#45d483'>預計還要 {eta_txt(I.get('th_eta'))}</span>（最近每秒處理 {I.get('th_rate', 0):.0f} 秒影片）" if I.get('th_eta') and I['th_left'] else '') +
            (f" · 最近 1 小時做好 {len(done)} 部" if done else '') + ('　<b style="color:#f0ad4e">暫停中</b>' if ENG.th_paused else '') +
            (f'　<b style="color:#ff9a3c">🚀 加速中（{ENG.boosted()}）</b>' if ENG.boosted() else '') + (f'　<b style="color:#ff4d6d">⚠ {ENG.th_low}</b>' if getattr(ENG, 'th_low', '') else '') +
            f"<br><b>轉檔</b>：排隊 {I['cv_wait']:,} · 完成 {I['cv_done']:,}" + (f" · 失敗 {I['cv_fail']:,}" if I['cv_fail'] else '') + (' · <b style="color:#f0ad4e">暫停中</b>' if ENG.cv_paused else '') +
            f"<br><b>初剪</b>：排隊 {len(ENG.cut_q)}" + (' · 剪輯中' if ENG.cut_cur else '') + f"　<b>收藏／待刪</b>：排隊 {len(ENG.op_q)}" + (' · 搬檔中' if ENG.op_cur else ''))
        act = {('th', k): v for k, v in dict(ENG.th_active).items()}; act.update({('cv', k): v for k, v in dict(ENG.cv_active).items()})
        for key in list(self.bars):
            if key not in act: w = self.bars.pop(key); w[0].setParent(None); w[0].deleteLater()
        for key, J in act.items():
            if key not in self.bars:
                box = QWidget(); hl = QHBoxLayout(box); hl.setContentsMargins(0, 0, 0, 0); lb = QLabel(); lb.setMinimumWidth(460); pb = QProgressBar(); pb.setRange(0, 1000); x = QPushButton('停')
                hl.addWidget(lb); hl.addWidget(pb, 1); hl.addWidget(x); self.al.addWidget(box); self.bars[key] = (box, lb, pb)
                x.clicked.connect(lambda _c=False, key=key: ENG.thumb_cancel(key[1], skip=True) if key[0] == 'th' else bg(lambda: ENG.conv_cancel([key[1]])))
            _b, lb, pb = self.bars[key]; p = J.get('pct') or 0; pb.setValue(int(p * 10)); pb.setFormat(f'{p}%')
            lb.setText(('🖼 預覽圖：' if key[0] == 'th' else '🔁 轉檔：') + J['name'] + (f" · {J.get('enc', '')} {J.get('speed') or ''}" if key[0] == 'cv' else f" · {time.time() - J['t0']:.0f} 秒"))
        T = TL[-200:][::-1]
        self.tb.setUpdatesEnabled(False); self.tb.setRowCount(len(T))
        stn = {'run': '▶ 進行中', 'wait': '⏳ 排隊', 'done': '✔ 完成', 'fail': '✖ 失敗', 'stop': '■ 停止'}
        for i, t in enumerate(T):
            for j, val in enumerate((time.strftime('%m-%d %H:%M:%S', time.localtime(t['t0'])), kinds.get(t['kind'], t['kind']), t['title'],
                                     stn.get(t['state'], t['state']) + (f" {t['pct']}%" if t['state'] == 'run' and t['pct'] is not None else ''), t['msg'])):
                it = self.tb.item(i, j)
                if it is None: it = QTableWidgetItem(); self.tb.setItem(i, j, it)
                if it.text() != str(val): it.setText(str(val)); it.setToolTip(str(val))
        self.tb.setUpdatesEnabled(True)


# ============================================================ 設定
class SetPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); sa = QScrollArea(); sa.setWidgetResizable(True); outer.addWidget(sa)
        body = QWidget(); sa.setWidget(body); v = QVBoxLayout(body); v.setContentsMargins(10, 10, 10, 10)
        t = QLabel('⚙ 設定（改了馬上存）'); t.setObjectName('title'); v.addWidget(t)
        g = QGroupBox('🖥 這台電腦（兩台都裝 SortCut 時分得出來）'); f = QFormLayout(g); v.addWidget(g)       # V0.2.27
        self.pc_nm = QLineEdit(); self.pc_nm.setMaxLength(20); self.pc_nm.setPlaceholderText('例如：主機、24h、3060')
        self.pc_col = QComboBox()
        for c_, n_ in ENG.PC_COLORS:
            pm_ = QPixmap(14, 14); pm_.fill(QColor(c_)); self.pc_col.addItem(QIcon(pm_), n_, c_)
        f.addRow('名稱', self.pc_nm); f.addRow('代表色', self.pc_col)
        f.addRow(self._note('會顯示在視窗標題、封面、工作列和托盤的圖示（右下角圓點＋第一個字）、手機 App 的名稱和圖示。'
                            '手機 App 的名稱和圖示是安裝時定下來的：改了之後，手機上的 App 要刪掉、重新打開網址再安裝一次。'))
        self.pc_nm.editingFinished.connect(lambda: (ENG.cfg.set('pc_name', self.pc_nm.text().strip()[:20]), self.win.apply_pc()))
        self.pc_col.currentIndexChanged.connect(lambda _i: (ENG.cfg.set('pc_color', self.pc_col.currentData()), self.win.apply_pc()))
        g = QGroupBox('影片庫：要整理的硬碟／資料夾（含所有子資料夾）'); gl = QVBoxLayout(g); v.addWidget(g)
        self.roots = QListWidget(); self.roots.setMaximumHeight(130); gl.addWidget(self.roots)
        r = QHBoxLayout(); gl.addLayout(r); b1 = QPushButton('➕ 加入'); b2 = QPushButton('移除選取的'); b3 = QPushButton('🔄 全部重新掃描'); self.sos = QCheckBox('打開程式時自動掃描一次')
        for w in (b1, b2, b3, self.sos): r.addWidget(w)
        r.addStretch(1)
        gl.addWidget(self._note('一定不會掃：每顆硬碟的 VideoSIFT 資料夾（初剪、收藏、待刪、原檔備份…都放這裡）、資源回收筒、系統資料夾、「.」開頭的資料夾。掃描只讀檔名和大小，不會改動任何檔案。'))
        g = QGroupBox('🚫 排除的資料夾（不掃描、不列出、不做預覽圖、不轉檔）'); gl = QVBoxLayout(g); v.addWidget(g)
        self.ex = QListWidget(); self.ex.setMaximumHeight(150); self.ex.setSelectionMode(QAbstractItemView.ExtendedSelection); gl.addWidget(self.ex)
        r = QHBoxLayout(); gl.addLayout(r); e1 = QPushButton('➕ 排除資料夾…'); self.ex_nm = QLineEdit(); self.ex_nm.setPlaceholderText('或輸入資料夾名稱（每一層都算，可用 *，例如 temp、*備份*、Sample）')
        e2 = QPushButton('➕ 排除這個名稱'); e3 = QPushButton('取消排除選取的')
        for w in (e1, self.ex_nm, e2, e3): r.addWidget(w, 1 if w is self.ex_nm else 0)
        gl.addWidget(self._note('排除後，裡面的影片馬上從清單拿掉；檔案不會動、做好的預覽圖也保留。取消排除會重新掃描，影片就回來。'
                                '也可以在檔案總管左邊的資料夾上按右鍵 →「🚫 排除這個資料夾」。'))
        e1.clicked.connect(self._ex_add_dir); e2.clicked.connect(lambda: (exclude_name(self.win, self.ex_nm.text()), self.ex_nm.clear()))
        self.ex_nm.returnPressed.connect(lambda: (exclude_name(self.win, self.ex_nm.text()), self.ex_nm.clear())); e3.clicked.connect(self._ex_del)
        g = QGroupBox('🖱 滑鼠滾輪（檔案總管、清單、每一頁都一樣）'); f = QFormLayout(g); v.addWidget(g)      # V0.6.34
        self.wh_m = QComboBox()
        for x_ in WheelBoost.STEPS: self.wh_m.addItem(f'×{x_:g}' + ('（原本的速度）' if x_ == 1 else '（慢一點）' if x_ < 1 else ''), x_)
        self.wh_m.setCurrentIndex(max(0, WheelBoost.STEPS.index(WheelBoost.mult()) if WheelBoost.mult() in WheelBoost.STEPS else 2))
        self.wh_s = QCheckBox('絲滑（緩進緩出，連續滾不會一頓一頓）'); self.wh_s.setChecked(WheelBoost.smooth())
        self.wh_m.currentIndexChanged.connect(lambda _i: (ENG.cfg.set('wheel_mult', float(self.wh_m.currentData())), self.win.msg(f'🖱 滾輪 ×{self.wh_m.currentData():g}')))
        self.wh_s.toggled.connect(lambda on: ENG.cfg.set('wheel_smooth', bool(on)))
        f.addRow('捲動速度', self.wh_m); f.addRow(self.wh_s)
        f.addRow(self._note('Ctrl＋滾輪（一列幾張）、Alt＋滾輪、時間軸、音量這些自己的滾輪功能照舊。手機網頁的電腦版（瀏覽器）在右下角另外調。'))
        g = QGroupBox('預覽圖（背景慢慢做，最低優先權，不搶你在用的程式）'); f = QFormLayout(g); v.addWidget(g)
        self.th_on = QCheckBox('開著（關掉＝不做新的預覽圖）'); self.th_n = QSpinBox(); self.th_n.setRange(1, 8); self.th_n.setSuffix(' 部同時')
        self.th_step = QComboBox()
        for s in (1, 2, 3, 5, 10): self.th_step.addItem(f'每 {s} 秒一張', s)
        self.th_h = QComboBox()
        for h in (120, 180, 240): self.th_h.addItem(f'{h} 像素高（{"小、省空間" if h < 180 else "建議" if h == 180 else "最清楚、比較占空間"}；直的影片自動加高）', h)
        self.th_prio = QComboBox()
        for a, b in (('最低（建議，電腦閒才做）', 'idle'), ('低', 'below'), ('一般（最快）', 'normal')): self.th_prio.addItem(a, b)
        self.th_dir = QLineEdit(); b4 = QPushButton('選…'); rr = QHBoxLayout(); rr.addWidget(self.th_dir, 1); rr.addWidget(b4)
        f.addRow(self.th_on); f.addRow('同時做幾部', self.th_n); f.addRow('間隔', self.th_step); f.addRow('大小', self.th_h); f.addRow('優先權', self.th_prio); f.addRow('存放位置（空白＝程式資料夾\\Data\\thumbs）', rr)
        f.addRow(self._note('間隔和大小只影響之後新做的。預覽圖拼成每 100 張一大張存，一小時的影片約 4～8 MB。放在 SSD 上捲動最順。'))
        g = QGroupBox('💽 硬碟（HDD 優化：每顆實體硬碟分開排隊）'); f = QFormLayout(g); v.addWidget(g)
        self.hdd_n = QSpinBox(); self.hdd_n.setRange(1, 4); self.hdd_n.setSuffix(' 部'); self.hdd_busy = QComboBox()
        for a, b in (('不管（照做）', 0), ('忙碌 60% 以上就先等', 60), ('忙碌 80% 以上就先等（建議）', 80), ('忙碌 95% 以上才等', 95)): self.hdd_busy.addItem(a, b)
        self.hdd_yield = QCheckBox('同一顆 HDD 正在掃描或轉檔時，預覽圖先讓路')
        f.addRow('同一顆 HDD 同時做幾部', self.hdd_n); f.addRow('別的程式在用硬碟時', self.hdd_busy); f.addRow(self.hdd_yield)
        f.addRow(self._note('HDD 一次讀一部最快（讀頭不用在幾個檔案之間來回跳）；不同顆硬碟會同時做。SSD 不限，照上面「同時做幾部」。後台可以看每顆硬碟現在多忙。'))
        g = QGroupBox('初剪'); f = QFormLayout(g); v.addWidget(g)
        self.cut_mode = QComboBox(); self.cut_mode.addItem('免轉檔（幾秒就好，畫質不變；起點會落在前一個關鍵格，可能早 1～5 秒）', 'copy'); self.cut_mode.addItem('重新壓縮（起點終點精準，比較慢）', 'enc')
        self.cut_merge = QComboBox(); self.cut_merge.addItem('每一段一個檔', False); self.cut_merge.addItem('同一部的幾段合併成一個檔', True)
        self.cut_dir = QLineEdit(); self.cut_dir.setPlaceholderText('空白＝同一顆硬碟的 VideoSIFT\\初剪（保留原本的子資料夾）；這個資料夾自動排除、永久保存'); b5 = QPushButton('選…'); r5 = QHBoxLayout(); r5.addWidget(self.cut_dir, 1); r5.addWidget(b5)
        f.addRow('方式', self.cut_mode); f.addRow('多段', self.cut_merge); f.addRow('存到', r5)
        g = QGroupBox('收藏／待刪'); f = QFormLayout(g); v.addWidget(g)
        self.fav_mode = QComboBox(); self.fav_mode.addItem('複製一份到收藏（原檔留著）', 'copy'); self.fav_mode.addItem('整個搬到收藏', 'move')
        self.fav_dir = QLineEdit(); self.fav_dir.setPlaceholderText('空白＝同一顆硬碟的 VideoSIFT\\收藏'); b6 = QPushButton('選…'); r6 = QHBoxLayout(); r6.addWidget(self.fav_dir, 1); r6.addWidget(b6)
        self.trash_dir = QLineEdit(); self.trash_dir.setPlaceholderText('空白＝同一顆硬碟的 VideoSIFT\\待刪'); b7 = QPushButton('選…'); r7 = QHBoxLayout(); r7.addWidget(self.trash_dir, 1); r7.addWidget(b7)
        f.addRow('收藏方式', self.fav_mode); f.addRow('收藏位置', r6); f.addRow('待刪位置', r7)
        f.addRow(self._note('「移到待刪」只是搬過去，不會真的刪；確定不要了再自己刪那個資料夾。'))
        g = QGroupBox('📦 歸檔（都放在每顆硬碟的 VideoSIFT\\ 底下）'); f = QFormLayout(g); v.addWidget(g); self.an = {}
        for gr in ('S', 'A', 'E', 'F'):
            e = QLineEdit(); e.setPlaceholderText(core.DEFAULTS['arch_names'][gr]); self.an[gr] = e; f.addRow(f'{gr}（{GN[gr]}）歸到 VideoSIFT\\', e)
            e.editingFinished.connect(lambda gr=gr, e=e: ENG.cfg.set('arch_names', dict(ENG.cfg.get('arch_names') or {}, **{gr: core.safe_name(e.text().strip() or core.DEFAULTS['arch_names'][gr])})))
        self.af = QCheckBox('F 歸到「待刪」資料夾（不另外開 F 資料夾）'); self.atree = QCheckBox('保留原本的子資料夾（不同資料夾的同名檔不會撞名）'); f.addRow(self.af); f.addRow(self.atree)
        self.cats = QListWidget(); self.cats.setMaximumHeight(110); cr = QHBoxLayout(); c1 = QPushButton('＋ 新增分類'); c2 = QPushButton('移除選取的分類')
        cr.addWidget(c1); cr.addWidget(c2); cr.addStretch(1); f.addRow('自訂分類資料夾', self.cats); f.addRow(cr)
        f.addRow(self._note('自訂分類（工作用、家庭日…）：歸進去的影片不再出現在待整理清單、不用分級。移除分類只是不再顯示在選單，資料夾和檔案不動。所有歸檔都記在「📒 操作紀錄」（保留 30 天），搬錯可以搬回來。'))
        self.af.toggled.connect(lambda on: ENG.cfg.set('arch_f_trash', bool(on))); self.atree.toggled.connect(lambda on: ENG.cfg.set('arch_tree', bool(on)))
        c1.clicked.connect(lambda: self.win.browse.new_cat()); c2.clicked.connect(self._del_cat)
        g = QGroupBox('💾 資料庫備份（分級、標籤、備註、剪輯紀錄都在資料庫裡）'); f = QFormLayout(g); v.addWidget(g)
        self.dbb = QCheckBox('每天自動備份一份（程式照常用，不用停）'); self.dbk = QComboBox()
        for nm_, k_ in (('保留 3 份', 3), ('保留 7 份（建議）', 7), ('保留 14 份', 14), ('保留 30 份', 30)): self.dbk.addItem(nm_, k_)
        br_ = QHBoxLayout(); bb1 = QPushButton('💾 立即備份'); bb2 = QPushButton('📂 開備份資料夾'); self.dbl = QLabel(''); self.dbl.setObjectName('muted')
        bb3 = QPushButton('↩ 從備份還原…'); bb3.setToolTip('選一份備份，下次開程式時換回那份（現在的資料庫會改名留著，不會刪）')
        br_.addWidget(bb1); br_.addWidget(bb2); br_.addWidget(bb3); br_.addWidget(self.dbl, 1); bb3.clicked.connect(self.restore_db)
        f.addRow(self.dbb); f.addRow('保留', self.dbk); f.addRow(br_)
        f.addRow(self._note('設定檔（快捷鍵、分類、排除…）也一起備份成 settings_日期.json，還原時複製回 Data\\settings.json。要還原資料庫：按「↩ 從備份還原…」選一份，重開程式就換好（原本的資料庫改名留在 Data 裡）。啟動和每次備份前都會檢查資料庫有沒有壞掉；壞掉的不會拿去備份，好的備份不會被擠掉。'))
        self.dbb.toggled.connect(lambda on: ENG.cfg.set('db_backup', bool(on))); self.dbk.currentIndexChanged.connect(lambda _i: ENG.cfg.set('db_backup_keep', int(self.dbk.currentData())))
        bb1.clicked.connect(lambda: (self.dbl.setText('備份中…'), bg(lambda: ENG.db_backup('手動'), lambda r_: (self.win.msg(('已備份：' + Path(r_).name) if r_ else '備份失敗（看 LOG）'), self._load_db()))))
        bb2.clicked.connect(lambda: (ENG.backup_dir().mkdir(parents=True, exist_ok=True), QDesktopServices.openUrl(QUrl.fromLocalFile(str(ENG.backup_dir())))))
        self._ext_box(v); self._web_box(v)
        g = QGroupBox('介面'); f = QFormLayout(g); v.addWidget(g)
        self.tray = QCheckBox('按右上角 ✕ 時縮到右下角，背景繼續做（要真的結束：右下角圖示 → 結束）')
        self.fz = QComboBox()
        for s in (1.0, 2.0, 3.0, 5.0): self.fz.addItem(f'畫面卡超過 {s:g} 秒就記到 LOG', s)
        f.addRow(self.tray); f.addRow('卡頓紀錄', self.fz)
        self.cv_start = QCheckBox('打開程式先停在封面（不顯示任何影片內容）'); self.cv_restore = QCheckBox('從右下角叫回視窗時，也先顯示封面'); self.cv_stats = QCheckBox('封面顯示總數（幾部影片、多大、背景在做什麼）')
        self.cv_idle = QComboBox()
        for _nm, _mn in (('不會', 0), ('閒置 5 分鐘', 5), ('閒置 10 分鐘', 10), ('閒置 30 分鐘', 30)): self.cv_idle.addItem(_nm, _mn)
        f.addRow(self.cv_start); f.addRow(self.cv_restore); f.addRow(self.cv_stats); f.addRow('自動回到封面', self.cv_idle)
        self.cv_start.toggled.connect(lambda on: ENG.cfg.set('cover_on_start', bool(on))); self.cv_restore.toggled.connect(lambda on: ENG.cfg.set('cover_on_restore', bool(on)))
        self.cv_stats.toggled.connect(lambda on: ENG.cfg.set('cover_stats', bool(on))); self.cv_idle.currentIndexChanged.connect(lambda _i: ENG.cfg.set('cover_idle_min', int(self.cv_idle.currentData())))
        g = QGroupBox('🎬 播放器快捷鍵（雙擊格子打開的播放視窗）'); gl = QVBoxLayout(g); v.addWidget(g)
        self.kt = QTableWidget(0, 3); self.kt.setHorizontalHeaderLabels(['按鍵（點一下再按你要的鍵）', '做什麼', '秒數（跳秒數用；負數＝往回）'])
        self.kt.verticalHeader().setVisible(False); self.kt.horizontalHeader().setStretchLastSection(True); self.kt.setMinimumHeight(260)
        for i, w in enumerate((230, 240)): self.kt.setColumnWidth(i, w)
        gl.addWidget(self.kt)
        kr = QHBoxLayout(); gl.addLayout(kr); k1 = QPushButton('＋ 新增一個'); k2 = QPushButton('刪掉選的'); k3 = QPushButton('↺ 回到預設'); self.dmax = QSpinBox(); self.dmax.setRange(10, 600); self.dmax.setSuffix(' 秒')
        for w in (k1, k2, k3): kr.addWidget(w)
        self.dpct = QSpinBox(); self.dpct.setRange(0, 50); self.dpct.setSuffix(' % 影片長度'); self.dpct.setToolTip('V0.2.08 拖曳一次最多移動影片長度的幾 %（0＝改用右邊的秒數）'); self.dpct.setValue(int(ENG.cfg.get('drag_pct') if ENG.cfg.get('drag_pct') is not None else 10))
        self.dpct.valueChanged.connect(lambda x: ENG.cfg.set('drag_pct', int(x)))
        kr.addStretch(1); kr.addWidget(QLabel('在畫面上左右拖曳（快＝遠、慢＝細調）：一次最多')); kr.addWidget(self.dpct); kr.addWidget(QLabel('（0％ 時用）')); kr.addWidget(self.dmax)
        gl.addWidget(self._note('預設：← →＝1 秒、Ctrl＋← →＝5 秒、Shift＋← →＝1%、Ctrl＋Shift＋← →＝5%、PgUp／PgDn＝1 分鐘、↑ ↓＝音量、Ctrl＋↑ ↓＝速度 ±0.01 倍（按住越加越快）、M＝靜音、C／X／Z＝加速／減速／正常、'
                                'F／D＝下一格／上一格、Home／End、I／O＝起點／終點、Ctrl+E＝截圖、Enter／F11＝全螢幕、Esc＝關閉（參考 PotPlayer／KMPlayer／GOM）。改了下次打開播放視窗生效。'))
        k1.clicked.connect(lambda: (self._key_row('', 'seek', 30), self._save_keys())); k2.clicked.connect(self._del_keys)
        k3.clicked.connect(lambda: (ENG.cfg.set('player_keys', []), self._load_keys(), self.win.msg('播放器快捷鍵回到預設')))
        self.dmax.valueChanged.connect(lambda x: ENG.cfg.set('drag_max', int(x)))
        v.addStretch(1)
        self._load()
        b1.clicked.connect(self.add_root); b2.clicked.connect(self.del_root); b3.clicked.connect(lambda: self.win.msg('開始掃描' if ENG.scan() else '已經在掃描'))
        self.sos.toggled.connect(lambda on: ENG.cfg.set('scan_on_start', bool(on))); self.th_on.toggled.connect(lambda on: ENG.cfg.set('th_on', bool(on)))
        self.th_n.valueChanged.connect(lambda x: ENG.cfg.set('th_n', int(x)))
        for w, k in ((self.th_step, 'th_step'), (self.th_h, 'th_h'), (self.th_prio, 'th_prio'), (self.cut_mode, 'cut_mode'), (self.cut_merge, 'cut_merge'), (self.fav_mode, 'fav_mode'), (self.fz, 'freeze_log_s')):
            w.currentIndexChanged.connect(lambda _i, w=w, k=k: ENG.cfg.set(k, w.currentData()))
        for w, k, b in ((self.th_dir, 'th_dir', b4), (self.cut_dir, 'cut_dir', b5), (self.fav_dir, 'fav_dir', b6), (self.trash_dir, 'trash_dir', b7)):
            w.editingFinished.connect(lambda w=w, k=k: (ENG.cfg.set(k, w.text().strip()), self._cut_dir_changed() if k == 'cut_dir' else None))
            b.clicked.connect(lambda _c=False, w=w, k=k: (self._pick(w, k), self._cut_dir_changed() if k == 'cut_dir' else None))
        self.tray.toggled.connect(lambda on: ENG.cfg.set('close_to_tray', bool(on)))
        self.hdd_n.valueChanged.connect(lambda x: ENG.cfg.set('hdd_n', int(x))); self.hdd_busy.currentIndexChanged.connect(lambda _i: ENG.cfg.set('hdd_busy', self.hdd_busy.currentData()))
        self.hdd_yield.toggled.connect(lambda on: ENG.cfg.set('hdd_yield', bool(on)))
        try: self._organize(sa, body, v)                                         # V0.5.02 分類排好＋上面一排跳到哪一段
        except Exception: ENG.log.err('設定頁整理')

    SECTIONS = (('🖥 一般', ('🖥 這台電腦', '介面', '📱 手機網頁')),
                ('📂 影片庫', ('影片庫', '🚫 排除的資料夾', '🗂 檔案總管列出的格式')),
                ('⚙ 背景工作', ('預覽圖', '💽 硬碟')),
                ('✂ 剪輯・收藏・歸檔', ('初剪', '收藏／待刪', '📦 歸檔', '🎬 播放器快捷鍵')),
                ('💾 備份', ('💾 資料庫備份',)))

    def _organize(self, sa, body, v):
        """設定頁：同一類的放在一起、每類一個小標題；最上面一排按鈕跳到那一類，另外兩套程式（整理、HotZone）的設定也從這裡去."""
        G = [w for w in body.findChildren(QGroupBox) if w.parent() is body]
        if not G: return
        for g_ in G: v.removeWidget(g_)
        for i_ in reversed(range(v.count())):
            if v.itemAt(i_) is not None and v.itemAt(i_).spacerItem() is not None: v.takeAt(i_)
        rest = list(G); jumps = []; hdrs = []
        bar = QWidget(); bl = QVBoxLayout(bar); bl.setContentsMargins(0, 0, 0, 6)
        go = [QPushButton('🔧 設定：整理（FileCompare）'), QPushButton('🔥 設定：HotZone')]
        go[0].clicked.connect(lambda: self.win.nav.setCurrentRow(62)); go[1].clicked.connect(lambda: self.win.nav.setCurrentRow(33))
        for nm, keys in self.SECTIONS:
            L = [g_ for g_ in rest if any(str(g_.title()).startswith(k) for k in keys)]
            if not L: continue
            for g_ in L: rest.remove(g_)
            h = QLabel(nm); h.setObjectName('title'); h.setStyleSheet('margin-top:14px;font-size:16px'); v.addWidget(h); hdrs.append(h)
            for g_ in L: v.addWidget(g_)
            b = QPushButton(nm); b.clicked.connect(lambda _c=False, h=h: sa.verticalScrollBar().setValue(max(0, h.y() - 6))); jumps.append(b)
        if rest:
            h = QLabel('其他'); h.setObjectName('title'); v.addWidget(h)
            for g_ in rest: v.addWidget(g_)
        v.addStretch(1)
        bl.addWidget(flow_row(jumps)); bl.addWidget(flow_row(go))
        v.insertWidget(1, bar)

    # ---------- 🗂 檔案總管列出的格式（V0.1.51）
    def _ext_box(self, v):
        g = QGroupBox('🗂 檔案總管列出的格式（勾＝列出來；手機／遠端只能播 MP4，其他格式預設不列）'); gv = QVBoxLayout(g); v.addWidget(g)
        grid = QGridLayout(); gv.addLayout(grid); self.ext_cb = {}
        for i, e in enumerate(sorted(core.VIDEO_EXT)):
            cb = QCheckBox(e[1:]); self.ext_cb[e] = cb; grid.addWidget(cb, i // 8, i % 8); cb.toggled.connect(lambda _o: self._ext_save())
        rb = QHBoxLayout(); gv.addLayout(rb); b1 = QPushButton('只列 MP4（預設）'); b2 = QPushButton('全部列出'); self.ext_l = QLabel(''); self.ext_l.setObjectName('muted')
        rb.addWidget(b1); rb.addWidget(b2); rb.addWidget(self.ext_l, 1)
        gv.addWidget(self._note('沒列出來的影片照樣會做預覽圖、會在「🔁 轉檔」頁出現（轉成 MP4 之後就會列出來）；檔案總管下面會寫被篩掉幾部。手機網頁用一樣的設定。'))
        b1.clicked.connect(lambda: self._ext_set(set(core.VIDEO_EXT) - set(core.MP4_EXT))); b2.clicked.connect(lambda: self._ext_set(set()))
        self._ext_load()

    def _ext_load(self):
        H = set(ENG.hidden_exts())
        for e, cb in self.ext_cb.items(): cb.blockSignals(True); cb.setChecked(e not in H); cb.blockSignals(False)
        def done(C):
            for e, cb in self.ext_cb.items(): cb.setText(e[1:] + (f'（{C[e]:,}）' if C.get(e) else ''))
            hid = sum(n for e, n in C.items() if e in set(ENG.hidden_exts())); self.ext_l.setText(f'目前有 {hid:,} 部沒列出來' if hid else '全部都有列出來')
        bg(ENG.ext_counts, done)

    def _ext_set(self, hide):
        ENG.cfg.set('hide_exts', sorted(hide)); ENG.log.w('檔案總管列出的格式：不列 ' + ('、'.join(sorted(hide)) or '（全部列出）')); self._ext_load(); self._ext_after()

    def _ext_save(self):
        hide = sorted(e for e, cb in self.ext_cb.items() if not cb.isChecked()); ENG.cfg.set('hide_exts', hide); ENG.log.w('檔案總管列出的格式：不列 ' + ('、'.join(hide) or '（全部列出）'))
        self._ext_load(); self._ext_after()

    def _ext_after(self):
        try: self.win.browse.load_tree(); self.win.browse.load_list()
        except Exception: pass

    # ---------- 📱 手機網頁（V0.1.49）
    def _web_box(self, v):
        g = QGroupBox('📱 手機網頁（用手機遙控 SortCut，透過 Tailscale）'); f = QFormLayout(g); v.addWidget(g)
        self.web_on = QCheckBox('開啟手機網頁'); self.web_port = QSpinBox(); self.web_port.setRange(1025, 64000); self.web_port.setValue(int(ENG.cfg.get('web_port') or 8461))
        self.web_hp = QLabel(''); self.web_hp.setObjectName('muted'); rp = QHBoxLayout(); rp.addWidget(self.web_port); rp.addWidget(self.web_hp, 1)
        self.web_pin = QLineEdit(); self.web_pin.setMaxLength(20); self.web_pin.setPlaceholderText('自己設 PIN：4～20 個字，數字、英文都可以，不能有空白')
        self.web_pin_l = QLabel(''); b_rand = QPushButton('🎲 隨機產生'); rpin = QHBoxLayout(); rpin.addWidget(self.web_pin, 1); rpin.addWidget(b_rand); rpin.addWidget(self.web_pin_l)
        self.web_lan = QCheckBox('也允許用 Tailscale IP／區網直接連 http（不用 HTTPS 也能用，但不能安裝成 App；不建議）')
        rb = QHBoxLayout(); b_app = QPushButton('📱 手機 App（Tailscale HTTPS）'); b_app.setObjectName('start')
        b_copy = QPushButton('🔗 複製網址'); b_off = QPushButton('關掉 Tailscale 上的這個埠'); b_out = QPushButton('登出所有手機')
        for b_ in (b_app, b_copy, b_off, b_out): rb.addWidget(b_)
        rb.addStretch(1); self.web_st = QLabel(''); self.web_st.setWordWrap(True); self.web_st.setTextFormat(Qt.RichText); self.web_st.setTextInteractionFlags(Qt.TextSelectableByMouse)
        f.addRow(self.web_on); f.addRow('本機埠', rp); f.addRow('PIN', rpin); f.addRow(self.web_lan); f.addRow(rb); f.addRow(self.web_st)
        f.addRow(self._note('跟你的其他程式錯開、不會互相蓋掉：每個程式在 Tailscale 上用自己的 HTTPS 埠＝本機埠 + 1000（TikLive 用預設的 https://電腦名稱/、FusionStitch 用 :9361、SortCut 預設 :9461）。'
                            'SortCut 只設定／關掉自己的埠，不碰 TikLive 的 443，也不會清掉其他程式的設定。每個程式的本機埠也要不一樣。'))
        self.web_on.setChecked(bool(ENG.cfg.get('web_on'))); self.web_lan.setChecked(bool(ENG.cfg.get('web_lan'))); self._web_pin_label()
        self.web_on.toggled.connect(lambda on: (ENG.cfg.set('web_on', bool(on)), web_apply(), self._web_status()))
        self.web_lan.toggled.connect(lambda on: (ENG.cfg.set('web_lan', bool(on)), web_apply(), self._web_status()))
        self.web_port.editingFinished.connect(self._web_port_changed)
        self.web_pin.editingFinished.connect(self._web_pin_save); self.web_pin.returnPressed.connect(self._web_pin_save)
        b_rand.clicked.connect(lambda: (self.web_pin.setText(''.join(random.choice('23456789') for _ in range(6))), self._web_pin_save()))
        b_app.clicked.connect(self._web_app); b_copy.clicked.connect(self._web_copy); b_off.clicked.connect(self._web_ts_off)
        b_out.clicked.connect(lambda: (ENG.cfg.set('web_tokens', []), ENG.cfg.set('web_tokens_ro', []), ENG.log.w('手機網頁：登出所有手機'), self.win.msg('所有手機都登出了，下次要重新輸入 PIN')))
        self._web_ts = {}; self._web_status()

    def _web_pin_label(self):
        self.web_pin_l.setText('🔒 已設定' if ENG.cfg.get('web_pin_hash') else '<span style="color:#ffb02e">還沒設 PIN</span>')

    def _web_pin_save(self):
        pin = self.web_pin.text().strip()
        if not pin: return
        if not vs_web.pin_ok_format(pin): self.web_pin_l.setText('<span style="color:#ff5d6c">4～20 個字、不能有空白</span>'); return
        salt = vs_web.rand_hex(8); ENG.cfg.set('web_pin_salt', salt); ENG.cfg.set('web_pin_hash', vs_web.pin_hash(pin, salt))
        self.web_pin_l.setText('✔ 已儲存'); ENG.log.w('手機網頁：PIN 改了（已經登入的手機不會被登出）')
        self.win.msg(f'手機網頁 PIN 已儲存：{pin}（記好；欄位清掉後就看不到了）', 10000); QTimer.singleShot(4000, lambda: (self.web_pin.clear(), self._web_pin_label()))

    def _web_port_changed(self):
        old = int(ENG.cfg.get('web_port') or 8461); new = int(self.web_port.value())
        if new == old: return
        ENG.cfg.set('web_port', new); ENG.log.w(f'手機網頁：本機埠 {old} → {new}（Tailscale HTTPS {vs_web.https_port(old)} → {vs_web.https_port(new)}）')
        was = bool((self._web_ts or {}).get('serving'))
        web_apply(); self._web_status()
        if was: bg(lambda: (vs_web.tailscale_serve_off(old), vs_web.tailscale_serve_on(new)), lambda _r: (self._web_status(True), self.win.msg(f'Tailscale 改用 :{vs_web.https_port(new)}；手機 App 要重新安裝（網址變了）', 10000)))

    def _web_status(self, ts=False):
        srv = web_server(create=False); port = int(ENG.cfg.get('web_port') or 8461); hp = vs_web.https_port(port)
        self.web_hp.setText(f'→ Tailscale HTTPS 用 :{hp}')
        T = self._web_ts or {}
        if srv is not None and srv.running: st = f'<span style="color:#45d483">● 開著</span>　本機 {srv.bind}:{srv.port}　有人連過 {srv.reqs} 次'
        elif srv is not None and srv.err: st = f'<span style="color:#ff5d6c">● 開不起來：{esc_html(srv.err)}</span>'
        else: st = '<span style="color:#8a96a8">● 關著</span>'
        if T.get('installed') is False: st += '<br>Tailscale：這台電腦還沒裝（tailscale.com 下載，登入同一個帳號）'
        elif T.get('url'): st += f'<br>📱 手機 App 網址：<b>{esc_html(T["url"])}</b>' + ('　✔ Tailscale 已設定' if T.get('serving') else '　（還沒設定 → 按「📱 手機 App」）')
        if T.get('others'): st += f'<br><small style="color:#8a96a8">Tailscale 上其他程式用的 HTTPS 埠：{"、".join(T["others"])}（SortCut 不會動它們）</small>'
        if srv is not None and srv.running and srv.bind == '0.0.0.0' and T.get('ip'): st += f'<br>直接連（http）：http://{T["ip"]}:{srv.port}/'
        self.web_st.setText(st)
        if ts or not T: bg(lambda: vs_web.tailscale_info(port), lambda r: (setattr(self, '_web_ts', r), self._web_status()) if r != self._web_ts else None)

    def _web_app(self):
        if not ENG.cfg.get('web_pin_hash'): QMessageBox.information(self, '手機 App', '先設一個 PIN（4～20 個字），手機第一次登入要用。'); self.web_pin.setFocus(); return
        if not ENG.cfg.get('web_on'): self.web_on.setChecked(True)
        if not vs_web.tailscale_exe():
            QMessageBox.information(self, '手機 App', '這台電腦還沒偵測到 Tailscale：\n\n1. 到 tailscale.com 下載 Windows 版安裝\n2. 右下角 Tailscale 圖示 → Log in\n3. 手機裝 Tailscale App，用同一個帳號登入並打開\n\n完成後再按一次這顆按鈕。'); return
        port = int(ENG.cfg.get('web_port') or 8461); self.win.msg('設定 Tailscale HTTPS 中…（第一次可能要 10～30 秒）', 30000)
        bg(lambda: (vs_web.tailscale_serve_on(port), vs_web.tailscale_info(port)), self._web_app_done)

    def _web_app_done(self, r):
        (rc, out), T = r; self._web_ts = T; self._web_status(); ENG.log.w(f'手機網頁：tailscale serve（:{vs_web.https_port(int(ENG.cfg.get("web_port") or 8461))}）→ {rc}：{(out or "")[-400:]}')
        m = re.search(r'https://login\.tailscale\.com/\S+', out or '')
        if m: QDesktopServices.openUrl(QUrl(m.group(0))); QMessageBox.information(self, '手機 App', 'Tailscale 要你先在網頁上同意開啟 HTTPS（已經幫你打開），按完再按一次「📱 手機 App」。'); return
        if rc != 0 or not T.get('url'):
            QMessageBox.warning(self, '手機 App', f'Tailscale 設定沒成功：\n{(out or "")[-600:]}\n\n常見原因：Tailscale 還沒登入、管理後台沒開 HTTPS（DNS → Enable HTTPS）。'); return
        QApplication.clipboard().setText(T['url'])
        QMessageBox.information(self, '手機 App', f'好了！網址已複製：\n\n{T["url"]}\n\n用手機（Tailscale 開著）打開這個網址 → 輸入 PIN → Chrome 右上「⋮」→「安裝應用程式」／iPhone Safari「分享」→「加入主畫面」。\n\n'
                                f'這個埠只給 SortCut 用，不會影響 TikLive、FusionStitch。')

    def _web_copy(self):
        u = (self._web_ts or {}).get('url')
        if not u: self._web_status(True); self.win.msg('還沒拿到 Tailscale 網址（先按「📱 手機 App」）'); return
        QApplication.clipboard().setText(u); self.win.msg(f'已複製：{u}')

    def _web_ts_off(self):
        port = int(ENG.cfg.get('web_port') or 8461)
        if QMessageBox.question(self, 'Tailscale', f'把 Tailscale 上的 :{vs_web.https_port(port)} 關掉？（只關 SortCut 自己的，其他程式不受影響）') != QMessageBox.Yes: return
        bg(lambda: vs_web.tailscale_serve_off(port), lambda r: (ENG.log.w(f'手機網頁：tailscale serve off → {r}'), self._web_status(True), self.win.msg('已關掉 Tailscale 上 SortCut 的埠')))

    def restore_db(self):
        B = ENG.db_backups()
        if not B: QMessageBox.information(self, '從備份還原', '還沒有任何備份（可以先按「💾 立即備份」）。'); return
        items = [f'{time.strftime("%Y-%m-%d %H:%M", time.localtime(t))}　{fmt_b(sz)}　{nm}' for nm, t, sz in B]
        it, ok = QInputDialog.getItem(self, '從備份還原', '要換回哪一份？（新的在上面）\n之後分級、標籤、剪輯紀錄都會回到那時候的樣子。', items, 0, False)
        if not ok or not it: return
        nm = B[items.index(it)][0]; r = ENG.request_restore(nm)
        if not r.get('ok'): QMessageBox.warning(self, '從備份還原', r.get('message', '不行')); return
        if QMessageBox.question(self, '從備份還原', f'已排好：下次開程式時換成「{nm}」（{r["n"]:,} 部影片）。\n現在的資料庫會改名留在 Data 資料夾，不會刪。\n\n現在就重開程式？') == QMessageBox.Yes: self.win.restart()
        else: self.win.msg('下次打開程式時會用備份還原')

    def _note(self, s):
        l = QLabel(s); l.setObjectName('muted'); l.setWordWrap(True); return l

    def _load(self):
        try:
            self.pc_nm.blockSignals(True); self.pc_nm.setText(ENG.pc_name()); self.pc_nm.blockSignals(False)
            self.pc_col.blockSignals(True); self.pc_col.setCurrentIndex(max(0, self.pc_col.findData(ENG.pc_color()))); self.pc_col.blockSignals(False)
        except Exception: pass
        self.roots.clear(); [self.roots.addItem(str(r)) for r in ENG.cfg.get('roots') or []]
        self.sos.setChecked(bool(ENG.cfg.get('scan_on_start'))); self.th_on.setChecked(bool(ENG.cfg.get('th_on'))); self.th_n.setValue(int(ENG.cfg.get('th_n') or 2))
        for w, k in ((self.th_step, 'th_step'), (self.th_h, 'th_h'), (self.th_prio, 'th_prio'), (self.cut_mode, 'cut_mode'), (self.cut_merge, 'cut_merge'), (self.fav_mode, 'fav_mode'), (self.fz, 'freeze_log_s')):
            i = w.findData(ENG.cfg.get(k)); w.setCurrentIndex(max(0, i))
        for w, k in ((self.th_dir, 'th_dir'), (self.cut_dir, 'cut_dir'), (self.fav_dir, 'fav_dir'), (self.trash_dir, 'trash_dir')): w.setText(ENG.cfg.get(k) or '')
        self.tray.setChecked(bool(ENG.cfg.get('close_to_tray'))); self._load_ex(); self._load_cats(); self._load_keys(); self._load_db()
        if hasattr(self, 'cv_start'):
            for w2, k2 in ((self.cv_start, 'cover_on_start'), (self.cv_restore, 'cover_on_restore'), (self.cv_stats, 'cover_stats')): w2.blockSignals(True); w2.setChecked(ENG.cfg.get(k2) is not False if k2 != 'cover_on_restore' else bool(ENG.cfg.get(k2))); w2.blockSignals(False)
            self.cv_idle.blockSignals(True); self.cv_idle.setCurrentIndex(max(0, self.cv_idle.findData(int(ENG.cfg.get('cover_idle_min') or 0)))); self.cv_idle.blockSignals(False)
        for gr, e in getattr(self, 'an', {}).items(): e.setText((ENG.cfg.get('arch_names') or {}).get(gr) or '')
        if hasattr(self, 'af'): self.af.blockSignals(True); self.af.setChecked(bool(ENG.cfg.get('arch_f_trash'))); self.af.blockSignals(False); self.atree.blockSignals(True); self.atree.setChecked(bool(ENG.cfg.get('arch_tree'))); self.atree.blockSignals(False)
        self.hdd_n.setValue(int(ENG.cfg.get('hdd_n') or 1)); self.hdd_busy.setCurrentIndex(max(0, self.hdd_busy.findData(int(ENG.cfg.get('hdd_busy') or 0)))); self.hdd_yield.setChecked(bool(ENG.cfg.get('hdd_yield')))

    # ---- 播放器快捷鍵
    def _key_row(self, key, act, n):
        i = self.kt.rowCount(); self.kt.insertRow(i)
        ke = QKeySequenceEdit(QKeySequence(key)); cb = QComboBox(); sp = QSpinBox(); sp.setRange(-7200, 7200); sp.setSuffix(' 秒'); sp.setValue(int(n or 0))
        for k2, (nm, _need) in PLAYER_ACTIONS.items(): cb.addItem(nm, k2)
        cb.setCurrentIndex(max(0, cb.findData(act))); sp.setEnabled(PLAYER_ACTIONS.get(act, ('', False))[1])
        self.kt.setCellWidget(i, 0, ke); self.kt.setCellWidget(i, 1, cb); self.kt.setCellWidget(i, 2, sp)
        ke.editingFinished.connect(self._save_keys); sp.valueChanged.connect(lambda _x: self._save_keys())
        cb.currentIndexChanged.connect(lambda _i, cb=cb, sp=sp: (sp.setEnabled(PLAYER_ACTIONS.get(cb.currentData(), ('', False))[1]), self._save_keys()))

    def _load_keys(self):
        if not hasattr(self, 'kt'): return
        self._loading_keys = True; self.kt.setRowCount(0)
        for k, a, n in player_keys(): self._key_row(k, a, n)
        self._loading_keys = False; self.dmax.blockSignals(True); self.dmax.setValue(int(ENG.cfg.get('drag_max') or 600)); self.dmax.blockSignals(False)

    def _save_keys(self):
        if getattr(self, '_loading_keys', False): return
        K = []; seen = {}
        for i in range(self.kt.rowCount()):
            ke, cb, sp = self.kt.cellWidget(i, 0), self.kt.cellWidget(i, 1), self.kt.cellWidget(i, 2)
            if ke is None or cb is None or sp is None: continue
            k = ke.keySequence().toString()
            if not k: continue
            if k in seen: self.win.msg(f'「{k}」重複了（第 {seen[k] + 1} 列和第 {i + 1} 列），後面那個不會生效'); continue
            seen[k] = i; K.append([k, cb.currentData(), int(sp.value()) if cb.currentData() == 'seek' else 0])
        ENG.cfg.set('player_keys', K); ENG.cfg.set('player_keys_seen', sorted(NEW_KEYS))      # 存過之後，你刪掉的新快捷鍵不會再自己跑回來

    def _del_keys(self):
        rows = sorted({ix.row() for ix in self.kt.selectedIndexes()}, reverse=True)
        if not rows and self.kt.currentRow() >= 0: rows = [self.kt.currentRow()]
        for r in rows: self.kt.removeRow(r)
        self._save_keys()

    def _load_db(self):
        if not hasattr(self, 'dbb'): return
        self.dbb.blockSignals(True); self.dbb.setChecked(ENG.cfg.get('db_backup') is not False); self.dbb.blockSignals(False)
        self.dbk.blockSignals(True); self.dbk.setCurrentIndex(max(0, self.dbk.findData(int(ENG.cfg.get('db_backup_keep') or 7)))); self.dbk.blockSignals(False)
        nm_, t_ = ENG.last_backup(); self.dbl.setText(f'最近一次：{time.strftime("%m-%d %H:%M", time.localtime(t_))}（{nm_}）' if nm_ else '還沒有備份（啟動 1.5 分鐘後會自動做第一份）')

    def _load_cats(self):
        if not hasattr(self, 'cats'): return
        self.cats.clear()
        for c in ENG.cfg.get('cats') or []: self.cats.addItem(f'📁 {c}')
        if not self.cats.count(): it = QListWidgetItem('（還沒有，按「＋ 新增分類」）'); it.setFlags(Qt.NoItemFlags); self.cats.addItem(it)

    def _del_cat(self):
        it = self.cats.currentItem()
        if not it or not it.text().startswith('📁 '): return
        c = it.text()[2:].strip()
        if QMessageBox.question(self, '移除分類', f'移除分類「{c}」？\n\n只是不再顯示在選單，VideoSIFT\\{c} 資料夾和裡面的檔案都不動。') != QMessageBox.Yes: return
        ENG.remove_cat(c); self._load_cats()

    def _load_ex(self):
        self.ex.clear(); cd = ENG.cfg.get('cut_dir') or ''
        cdt = cd or '每顆硬碟的 VideoSIFT\\初剪'
        it = QListWidgetItem(f'🔒 初剪資料夾：{cdt}（自動排除、永久保存，不能取消）'); it.setFlags(Qt.ItemIsEnabled); it.setForeground(QColor('#9fb3c8')); self.ex.addItem(it)
        for d in ENG.cfg.get('ex_dirs') or []:
            it = QListWidgetItem(f'📁 {d}'); it.setData(Qt.UserRole, ('dir', str(d))); it.setToolTip('這個資料夾和底下所有子資料夾'); self.ex.addItem(it)
        for n in ENG.cfg.get('ex_names') or []:
            it = QListWidgetItem(f'🏷 名稱：{n}'); it.setData(Qt.UserRole, ('name', str(n))); it.setToolTip('不管在哪一層，資料夾名稱符合就排除'); self.ex.addItem(it)

    def _cut_dir_changed(self):
        self._load_ex(); bg(ENG.apply_excludes, lambda n: (self.win.browse.load_tree(), self.win.browse.load_list()) if n else None)

    def _ex_add_dir(self):
        R = ENG.cfg.get('roots') or []
        d = QFileDialog.getExistingDirectory(self, '選要排除的資料夾', str(R[0]) if R else '')
        if d: exclude_folder(self.win, d)

    def _ex_del(self):
        S = [it.data(Qt.UserRole) for it in self.ex.selectedItems() if it.data(Qt.UserRole)]
        if not S: self.win.msg('先在清單選要取消排除的'); return
        if QMessageBox.question(self, '取消排除', '取消排除這幾個？\n\n' + '\n'.join(('📁 ' if k == 'dir' else '🏷 ') + x for k, x in S) +
                                '\n\n會重新掃描影片庫，那些影片就會回來。') != QMessageBox.Yes: return
        def work():
            for k, x in S:
                if k == 'dir': ENG.cfg.set('ex_dirs', [y for y in ENG.cfg.get('ex_dirs') or [] if core.path_key(y) != core.path_key(x)])
                else: ENG.cfg.set('ex_names', [y for y in ENG.cfg.get('ex_names') or [] if str(y).strip().lower() != x.strip().lower()])
            return ENG.scan()
        bg(work, lambda ok: (self._load_ex(), self.win.msg('已取消排除，' + ('重新掃描中（背景）' if ok else '目前正在掃描，掃完請再按一次「🔄 全部重新掃描」'))))

    def _pick(self, w, k):
        d = QFileDialog.getExistingDirectory(self, '選資料夾')
        if d: w.setText(os.path.normpath(d)); ENG.cfg.set(k, os.path.normpath(d))

    def add_root(self):
        self.win.browse.add_root(); QTimer.singleShot(200, self._load)

    def del_root(self):
        it = self.roots.currentItem()
        if not it: return
        if QMessageBox.question(self, '移除', f'從影片庫移除 {it.text()}？\n\n只是不再列出，檔案和已做好的預覽圖都不會刪。') != QMessageBox.Yes: return
        root = it.text(); ENG.cfg.set('roots', [r for r in ENG.cfg.get('roots') or [] if str(r) != root])
        bg(lambda: ENG.db.x('UPDATE files SET missing=1 WHERE root=?', (root,)), lambda _r: self.win.browse.load_tree()); self._load()


# ============================================================ LOG、版本與更新
class LogPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win
        v = QVBoxLayout(self); v.setContentsMargins(8, 8, 8, 8)
        t = QLabel('📜 LOG'); t.setObjectName('title'); v.addWidget(t)
        r = QHBoxLayout(); v.addLayout(r)
        b1 = QPushButton('📂 開 LOG 資料夾'); b2 = QPushButton('📤 匯出最近 7 天的 LOG（zip，含整理）'); b3 = QPushButton('看錯誤紀錄'); b4 = QPushButton('看卡頓紀錄'); b5 = QPushButton('看顯示卡檢查'); b6 = QPushButton('看更新紀錄'); b7 = QPushButton('看當機傾印'); b8 = QPushButton('看 Qt 警告')
        for w in (b1, b2, b3, b4, b5, b6, b7, b8): r.addWidget(w)
        b9 = QPushButton('📜 整理的 LOG ›'); b9.setToolTip('整理（FileCompare）的 LOG 另外記；匯出時會一起放進 zip'); b9.clicked.connect(lambda: self.win.enter(63)); r.addWidget(b9)   # V0.5.65
        r.addStretch(1)
        r2 = QHBoxLayout(); v.addLayout(r2)
        self.fq = QLineEdit(); self.fq.setPlaceholderText('🔎 篩選最近的 LOG（空格隔開＝都要有，例如：預覽圖 失敗）'); self.fq.setClearButtonEnabled(True)
        self.fw = QCheckBox('只看警告／失敗'); self.fp = QCheckBox('⏸ 暫停更新'); self.fc = QLabel(''); self.fc.setObjectName('muted')
        for w in (self.fq, self.fw, self.fp, self.fc): r2.addWidget(w, 1 if w is self.fq else 0)
        self.fq.textChanged.connect(lambda _t: self._refresh(True)); self.fw.toggled.connect(lambda _o: self._refresh(True)); self.fp.toggled.connect(lambda on: None if on else self._refresh(True))
        self.tx = QPlainTextEdit(); self.tx.setReadOnly(True); self.tx.setMaximumBlockCount(3000); v.addWidget(self.tx, 1)
        b1.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ENG.log.d))))
        b2.clicked.connect(self.export); b3.clicked.connect(lambda: self.show_file('error_log.txt')); b4.clicked.connect(lambda: self.show_file('ui_freeze_log.txt'))
        b5.clicked.connect(lambda: self.show_file('gpu_diag.txt')); b6.clicked.connect(lambda: self.show_file('update_log.txt'))
        b7.clicked.connect(lambda: self.show_file('crash_dump.txt')); b8.clicked.connect(lambda: self.show_file('qt_log.txt'))
        self.n = 0; self.tm = QTimer(self); self.tm.timeout.connect(self.tick); self.tm.start(1500)

    WARN = ('⚠', '失敗', '錯誤', 'Error', 'error', 'Traceback', '找不到', '離線', '逾時', '有問題', '跳過')

    def tick(self):
        if not self.isVisible() or getattr(self, 'viewing', False): return
        self._refresh()

    def _refresh(self, force=False):
        """最近 600 行；可以篩選關鍵字、只看警告、暫停更新（看到一半不會被捲走）."""
        if self.fp.isChecked() and not force: return
        L = list(ENG.log.tail); q = [w.lower() for w in self.fq.text().split()]; warn = self.fw.isChecked()
        sig = (len(L), L[-1] if L else '', tuple(q), warn)
        if sig == getattr(self, '_sig', None) and not force: return
        self._sig = sig
        if q or warn:
            L = [l for l in L if all(w in l.lower() for w in q) and (not warn or any(k in l for k in self.WARN))]
            self.fc.setText(f'{len(L):,} 行符合')
        else: self.fc.setText('')
        self.tx.setPlainText('\n'.join(L)); self.tx.verticalScrollBar().setValue(self.tx.verticalScrollBar().maximum())

    def show_file(self, nm):
        p = ENG.log.d / nm
        try: s = p.read_text(encoding='utf-8', errors='replace')[-200000:]
        except Exception: s = '（還沒有這個紀錄）'
        d = QDialog(self); d.setWindowTitle(nm); d.resize(1000, 650); l = QVBoxLayout(d); t = QPlainTextEdit(s); t.setReadOnly(True); l.addWidget(t); d.exec()

    def export(self):
        p, _ = QFileDialog.getSaveFileName(self, '匯出 LOG', str(Path.home() / f'VideoSift_LOG_{time.strftime("%m%d_%H%M")}.zip'), 'zip (*.zip)')
        if not p: return
        bg(lambda: ENG.log.export(p, extra=[(fc_root() / 'LOG', 'FileCompare')]), lambda n: self.win.msg(f'已匯出 {n} 個檔（含整理的 LOG）→ {p}'))


def undo_last_move(win):
    """↩ 復原上一次搬移（移到待刪／歸檔／收藏）：先問、再整批搬回."""
    def got(d):
        if not d.get('n'): win.msg('↩ 沒有可以復原的搬移'); return
        if QMessageBox.question(win, '復原上一次搬移', f"把上一次「{d['kind']}」（{d['when']}，{d['n']} 個、{fmt_b(d['bytes'])}）整批搬回原來的位置？\n\n" + '\n'.join(d['names']) + ('\n…' if d['n'] > 8 else '')) != QMessageBox.Yes: return
        def done(r):
            win.msg(r['message'], 12000)
            try: win.browse.load_list(); win.browse.load_tree()
            except Exception: pass
            if r.get('bad'): QMessageBox.warning(win, '復原上一次搬移', '\n'.join(r['bad'][:15]))
        bg(ENG.oplog_undo_last, done)
    bg(lambda: ENG.oplog_undo_last(dry=True), got)


class OpsPage(QWidget):
    """📒 操作紀錄：最近 30 天每一筆搬移／歸檔／刪除／剪輯／轉檔，原本叫什麼、從哪裡到哪裡、多大；可以搜尋、匯出、把搬過的搬回來."""
    KINDS = OrderedDict([('', '全部'), ('arch', '📦 歸檔'), ('trash', '🗑 待刪'), ('fav', '⭐ 收藏'), ('delete', '❌ 刪除原檔'), ('cut', '✂ 初剪'), ('conv', '🔁 轉檔'),
                         ('undo', '↩ 復原'), ('migrate', '📁 資料夾搬家'), ('exclude', '🚫 排除'), ('cat', '🏷 分類'), ('rename', '🔤 改名'), ('snap', '📷 截圖'), ('clean', '🧹 清理')])

    def __init__(self, win):
        super().__init__(); self.win = win; self.rows = []
        v = QVBoxLayout(self); v.setContentsMargins(8, 8, 8, 8)
        t = QLabel('📒 操作紀錄（保留最近 30 天：誰搬到哪、原本叫什麼、多大、什麼時候）'); t.setObjectName('title')
        b_fc = QPushButton('🧾 整理（FileCompare）的操作紀錄 ›'); b_fc.setToolTip('整理的分類搬檔、隔離區、依日期整理…記在那邊（也可以搬回）'); b_fc.clicked.connect(lambda: self.win.enter(61))   # V0.5.64
        h_ = QHBoxLayout(); h_.addWidget(t, 1); h_.addWidget(b_fc); v.addLayout(h_)
        r = QHBoxLayout(); v.addLayout(r)
        self.q = QLineEdit(); self.q.setPlaceholderText('搜尋檔名、路徑、說明（空格隔開＝都要有）'); self.q.setClearButtonEnabled(True)
        self.kind = QComboBox()
        for k, n in self.KINDS.items(): self.kind.addItem(n, k)
        self.days = QComboBox()
        for n, d in (('今天', 1), ('7 天', 7), ('30 天', 30)): self.days.addItem(n, d)
        self.days.setCurrentIndex(2)
        for w in (self.q, self.kind, self.days): r.addWidget(w, 1 if w is self.q else 0)
        self.tb = QTableWidget(0, 7); self.tb.setHorizontalHeaderLabels(['時間', '動作', '檔名（原本）', '從', '到', '大小', '說明'])
        self.tb.verticalHeader().setVisible(False); self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tb.setSelectionMode(QAbstractItemView.ExtendedSelection); self.tb.horizontalHeader().setStretchLastSection(True)
        for i, w in enumerate((130, 90, 220, 280, 280, 80)): self.tb.setColumnWidth(i, w)
        v.addWidget(self.tb, 1)
        r2 = QHBoxLayout(); v.addLayout(r2)
        b0 = QPushButton('↩ 復原上一次搬移'); b0.setObjectName('start'); b0.setToolTip('上一次「移到待刪／歸檔／搬去收藏」整批搬回原來的位置'); b0.clicked.connect(lambda: undo_last_move(self.win))
        b1 = QPushButton('📂 在檔案總管顯示（現在的位置）'); b2 = QPushButton('↩ 搬回原來的位置（選的）'); r2.addWidget(b0); b3 = QPushButton('📤 匯出 CSV'); b4 = QPushButton('🔄 重新整理')
        for w in (b1, b2, b3, b4): r2.addWidget(w)
        r2.addStretch(1); self.cnt = QLabel(''); self.cnt.setObjectName('muted'); r2.addWidget(self.cnt)
        self.q.textChanged.connect(lambda _t: self._qt.start(300)); self._qt = QTimer(self); self._qt.setSingleShot(True); self._qt.timeout.connect(self.load)
        self.kind.currentIndexChanged.connect(lambda _i: self.load()); self.days.currentIndexChanged.connect(lambda _i: self.load())
        b1.clicked.connect(self.show_where); b2.clicked.connect(self.undo); b3.clicked.connect(self.export); b4.clicked.connect(self.load)
        self.tb.itemDoubleClicked.connect(lambda _it: self.show_where())

    def showEvent(self, e):
        super().showEvent(e); self.load()

    def load(self):
        q, k, d = self.q.text().strip(), self.kind.currentData() or '', int(self.days.currentData() or 30)
        bg(lambda: ENG.oplog_query(q, k, d), self._fill)

    def _fill(self, R):
        self.rows = R; self.tb.setRowCount(len(R))
        def row(i):
            x = R[i]
            vals = (time.strftime('%m-%d %H:%M:%S', time.localtime(x['t'])), self.KINDS.get(x['kind'], x['kind']) + ('（已搬回）' if x['undone'] else ''), x['name'] or '',
                    x['src'] or '', x['dst'] or '', fmt_b(x['size']) if x['size'] else '', x['detail'] or '')
            for j, val in enumerate(vals):
                it = self.tb.item(i, j)
                if it is None: it = QTableWidgetItem(); self.tb.setItem(i, j, it)
                it.setText(str(val)); it.setToolTip(str(val))
        chunked(self, 'ops', len(R), row, 500, self.tb); self.cnt.setText(f'{len(R):,} 筆' + ('（最多列 3000 筆，用搜尋縮小範圍）' if len(R) >= 3000 else ''))

    def _sel(self):
        return [self.rows[r.row()] for r in self.tb.selectionModel().selectedRows() if r.row() < len(self.rows)]

    def show_where(self):
        S = self._sel()
        if not S: return
        x = S[0]; p = x['dst'] if (x['dst'] and os.path.exists(x['dst'])) else x['src']
        if p and os.path.exists(p): core.explorer_select(p)
        else: self.win.msg('兩邊都找不到這個檔了（可能被刪掉或搬走）')

    def undo(self):
        S = [x for x in self._sel() if x['kind'] in ('arch', 'trash', 'fav', 'rename') and not x['undone']]
        if not S: self.win.msg('選「歸檔／待刪／收藏（搬）」而且還沒搬回去的紀錄'); return
        if QMessageBox.question(self, '搬回去', f'把選的 {len(S)} 個檔搬回原來的位置？\n\n原位置已經有同名的檔案就不動（不會覆蓋）。') != QMessageBox.Yes: return
        ids = [x['id'] for x in S]
        def done(res):
            ok = sum(1 for r in res if r.get('ok')); bad = [r['message'] for r in res if not r.get('ok')]
            self.win.msg(f'搬回 {ok} 個' + (f'，{len(bad)} 個沒搬' if bad else '')); self.load(); self.win.browse.load_list(); self.win.browse.load_tree()
            if bad: QMessageBox.warning(self, '搬回去', '\n'.join(bad[:15]))
        bg(lambda: [ENG.oplog_undo(i) for i in ids], done)

    def export(self):
        p, _ = QFileDialog.getSaveFileName(self, '匯出操作紀錄', str(Path.home() / f'VideoSift_操作紀錄_{time.strftime("%Y%m%d_%H%M")}.csv'), 'CSV (*.csv)')
        if not p: return
        import csv
        try:
            with open(p, 'w', encoding='utf-8-sig', newline='') as fh:
                w = csv.writer(fh); w.writerow(['時間', '動作', '檔名', '從', '到', '大小(bytes)', '說明', '批次', '已搬回'])
                for x in self.rows: w.writerow([time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(x['t'])), x['kind'], x['name'], x['src'], x['dst'], x['size'], x['detail'], x['batch'], 'Y' if x['undone'] else ''])
            self.win.msg(f'已匯出 {len(self.rows):,} 筆 → {p}'); ENG.log.w(f'匯出操作紀錄 {len(self.rows)} 筆 → {p}')
        except Exception as ex: QMessageBox.warning(self, '匯出', str(ex))


LAB_LIST = [  # (設定鍵, 名稱, 哪一版加的) ── 一覽表、一鍵全部關閉用
    ('boost_idle', '🚀 A. 電腦閒置時加速', '0.1.15'), ('boost_night', '🚀 B. 夜間時段加速', '0.1.15'), ('card_scrub', '👀 卡片滑過預覽', '0.1.16'), ('grid_zoom', '👀 格子放大預覽', '0.1.16'),
    ('inverse_cut', '✂ 反過來剪', '0.1.17'), ('grid_keys', '⌨ 鍵盤操作預覽格子', '0.1.17'), ('smart_search', '🔎 進階搜尋語法', '0.1.18'),
    ('resume', '⏯ 續播', '0.1.20'), ('player_grade', '🎬 播放中直接分級', '0.1.20'), ('auto_next', '⏭ 分級後自動跳下一部', '0.1.13'), ('watch_downloads', '📥 也看下載資料夾的更新包', '0.1.23'), ('seg_preview', '▶ 預覽選的片段', '0.1.24'), ('cover_b', '🏠 封面樣式 B', '0.1.25'), ('focus_mode', '⛶ 專注分級模式', '0.1.27'), ('thumb_precise', '🎯 預覽圖精準模式', '0.1.28'), ('conv_ssim', '🔬 轉檔後抽查畫質', '0.1.33'), ('tree_grade', '📊 資料夾樹顯示分級進度', '0.1.38'), ('daily_goal', '🎯 每日整理目標', '0.1.42')]
# V0.2.30 🆕 第二波新功能（每一版加一個；全部預設關，實驗工作區最上面「🆕 新功能」打開）：(設定鍵, 名稱, 說明, 哪一版)
NEW_LABS = [
    ('bg_sched', '🕑 背景工作時段', '轉檔、預覽圖、讀影片資訊、搬硬碟可以各自設定「只在幾點到幾點做」（例如轉檔只在半夜 1～9 點）；時段外不開新的，手上的做完，後台會顯示「🕑 時段外」', '0.2.31'),
    ('disk_warn', '⚠ 硬碟空間不足提醒', '影片庫的任何一顆硬碟剩不到設定的空間（預設 50 GB），或照最近的速度 3 天內會滿（要開 💽 空間地圖 才算得出速度）時，下方狀態列和手機的後台會跳紅色提醒，LOG 也記一行（轉檔、初剪、搬硬碟寫滿之前先知道）', '0.2.32'),
    ('creators', '👥 依作者／主播分組', '檔案總管搜尋框旁邊多一個「👥 作者」：從檔名自動猜作者（D01-林熹熹、小宅宅、PRED…），列出每個人幾部、多大、分級了多少、S／A／E／F 各幾部；點兩下就只看那個人', '0.2.33'),
    ('folder_move', '🚚 資料夾搬到別顆硬碟', '檔案總管資料夾按右鍵多一個「🚚 搬到別顆硬碟…」：整個資料夾搬過去（例如 D:\\VideoSIFT\\S_無條件保存\\TO M → F:），分級、備註、預覽圖都跟著過去；跟搬硬碟一樣低優先權、限速、比對過才刪原檔，進度在「🚚 搬硬碟」', '0.2.34'),
    ('report', '📈 分級報表', '下方狀態列多一個「📈」：今天／這 7 天分級了幾部（S／A／E／F）、剪了幾段、轉檔省了多少、清掉待刪多少，還有最近 14 天的長條圖、還剩幾部可以審', '0.2.35'),
    ('dur_chips', '⏱ 依影片長度篩選', '檔案總管搜尋框下面多一排：全部時長／< 1 分／1–10 分／10–60 分／> 1 小時／沒時長，一按就只列那個長度的影片（可以跟分級、搜尋一起用）。手機檔案總管也有同一排。', '0.2.37'),
    ('list_csv', '📤 清單匯出 CSV', '檔案總管搜尋框旁多一個「📤 CSV」：把目前列出來的影片（含分級、時長、搜尋篩選）存成 Excel 直接能開的表格：檔名、資料夾、分級、大小、時長、解析度、編碼、收藏、剪了幾段、標籤、說明、完整路徑。手機在 工具 →「🆕 新功能」也能下載。', '0.2.38'),
    ('keys_help', '⌨ 快捷鍵一覽', '按 Ctrl+/（或 Ctrl+K 打「快捷鍵」）跳出所有快捷鍵：全域、檔案總管、播放器（讀你自己改過的鍵）、比對播放器，可以打字找。手機網頁版（電腦瀏覽器開）也加上鍵盤操作：? 看一覽、/ 搜尋、看影片時 1-4 分級、←→ 上一部下一部、空白鍵播放。', '0.2.39'),
    ('views', '⭐ 常用篩選', '檔案總管搜尋框旁多一個「⭐」：把「資料夾＋分級＋搜尋＋排序＋子資料夾＋時長」存成一個名字（例如「F 槽 未分級 長片」），之後一按就回到那個畫面。電腦和手機共用同一份；手機在檔案總管分級列最前面有「⭐」。', '0.2.40'),
    ('bookmarks', '🔖 時間書籤', '播放器多一個「🔖」：按 B 在現在的時間點加一個書籤（也可以寫說明，例如「這段要剪」），之後按 🔖 一鍵跳回去。書籤存在影片那顆硬碟的紀錄裡，換電腦也在。手機看影片時也有 🔖：加書籤、點一下跳過去。', '0.2.41'),
    ('swipe_nav', '👆 手勢換部', '手機看檔案（預覽圖那頁）時往左滑＝下一部、往右滑＝上一部，不用回清單。電腦檔案總管：滑鼠側邊的「上一頁／下一頁」鍵＝上一部／下一部。', '0.2.42'),
    ('space_map', '💽 硬碟空間地圖', '「🚚 搬硬碟」頁右上（或 Ctrl+K 打「空間」）：每顆硬碟一條彩色長條，看 S／A／E／F／未分級／影片庫以外的檔案 各佔多少、還剩多少，F 待刪清掉能空出幾 GB。打開後每天記一次剩多少，用了 3 天以上會顯示「📉 每天少多少、大約幾天會滿」。手機在 工具 →「🆕 新功能」。', '0.2.43'),
    ('goal', '🎯 每日分級目標', '設一個「一天要分級幾部」（預設 100，跟 其他設定 的每日目標是同一個數字）：下方狀態列顯示「🎯 今天 37／100」，達成變 🎉。手機檔案總管上面也有一條進度，點一下可以改目標。原本的「每日整理目標」開著的話，電腦狀態列只顯示原本那個（不重複）。', '0.2.44'),
    ('empty_dirs', '🧹 空資料夾清理', '「🚚 搬硬碟」頁右上（或 Ctrl+K 打「空資料夾」）：找出影片庫裡一個檔都沒有的資料夾（搬完、分類完常留下一堆），勾選後刪掉。只刪真的空的，有任何檔案就保留；VideoSIFT 分類資料夾和紀錄資料夾不會列出來。手機在 工具 →「🆕 新功能」。', '0.2.45'),
    ('months', '📅 依月份', '檔案總管搜尋框旁多一個「📅 月份」：每個月（檔案時間，通常就是錄影那天）有幾部、多大、分級了多少（S／A／E／F／還沒分），點兩下就只看那個月。手機在 工具 →「🆕 新功能」，點一下就切過去。', '0.2.47'),
    ('copy_to', '📤 複製到上傳資料夾', '先設定一個上傳資料夾（例如 K:\\上傳）：檔案總管選好影片按右鍵「📤 複製到上傳資料夾」，就在背景一部一部複製過去（原檔留著、不改分級）。會限速、電腦很忙（TikLive）時自動放慢一半，下方狀態列看進度。手機選好影片的選單裡也有。也可以設定「分成 S（或 A）就自動複製」：你一分級就自動排進去（規則自動分的不算）。', '0.2.49'),
    ('pc_overview', '🖥 硬碟在哪台電腦', '兩台電腦輪流用的時候：「🚚 搬硬碟」頁右上（或 Ctrl+K）列出每顆接著的硬碟，紀錄最後是「這台」還是「另一台：名稱」寫的、什麼時候、幾部、分級多少；另一台寫的用橘色標出來。也可以一鍵把紀錄寫到各硬碟。手機在 工具 →「🆕 新功能」。', '0.2.51'),
    ('privacy', '🙈 隱私模糊', '有人經過時一鍵把檔案總管的預覽圖、清單全部模糊：下方狀態列「🙈」或 Ctrl+Shift+H 切換（下次打開會記得）。手機檔案總管分級列也有「🙈」，看檔案、播放時也一起模糊，按住預覽圖可以暫時看清楚。', '0.2.55'),
    ('recent_dirs', '🕘 最近開過的資料夾', '檔案總管搜尋框旁多一個「🕘」：最近開過的 15 個資料夾，一按就跳回去（不用在左邊樹裡一層一層找）。電腦和手機共用同一份；手機在分級列最前面。', '0.2.56'),
    ('auto_scan', '👀 自動找新影片', 'TikLive 一直在錄新影片的話：每隔一段時間（預設 30 分鐘，可以改）自動重新掃描影片庫一次，新錄好的影片自己出現、自動排預覽圖，不用再按「🔄 重新掃描」。正在搬硬碟、正在掃描時會先跳過。找到新的會記在 LOG。', '0.2.58'),
    ('rules', '⚡ 規則分級', '還沒分級的影片，用條件一次標好：例如「短於 20 秒 → F」「低於 480p → E」「檔名有 test → F」，可以只做目前資料夾。套用前先看符合幾部、列出例子；規則標的不算進今天的分級數，可以一鍵復原。剪過初剪的、⭐ 收藏的、🔖 有書籤的不會被規則動到。也可以「💾 存成自動規則」：之後每分鐘自動對還沒分級的套用（TikLive 新錄的也會自動被分），還能「↩ 復原最近 24 小時自動規則分的」。在 🧰 工具箱 或 Ctrl+K；手機在 工具 →「🆕 新功能」。', '0.2.60'),
    ('guess', '🤖 分級建議', '還沒分級的影片，看同一個作者／主播（從檔名猜）你以前分過的大多是哪一級，在分級按鈕旁邊小字提示「🤖 猜 F」（至少分過 5 部、6 成以上同一級才會猜；看不出作者時改看同一個資料夾，至少 8 部、7 成以上；都看不出來但 😴 靜止超過 8 成的猜 F）。只是建議，不會自動分級。手機看檔案時分級按鈕上面也會顯示。', '0.2.62'),
    ('search_hist', '🔎 搜尋紀錄', '檔案總管搜尋框記住你搜過的字（最多 20 個，電腦和手機共用）：打一兩個字就下拉出以前搜過的，點一下就搜。按 Enter 或離開搜尋框才記。', '0.2.65'),
    ('auto_theme', '🌗 跟著時間換深色／淺色', '白天自動淺色、晚上自動深色（預設 7 點到 19 點淺色，可以改）。手機在 設定 → 外觀 → 主題 選「🌗 跟著時間」，用一樣的時間。', '0.2.66'),
    ('proc_guard', '🎥 直播／錄影時讓路', '設定幾個程式名稱（例如 obs64.exe）。⚠ 24 小時都開著的程式（例如一直開著的 TikLive）不要填，不然那些工作永遠不會做；填「直播／錄影時才開」的程式：它們在跑的時候，選的背景工作（預設只有轉檔，也可以勾預覽圖、讀影片資訊、搬硬碟）先不開新的，手上的做完；程式關掉就自動繼續。後台狀態會寫「🎥 … 在跑：先讓路」。可以按「🔍 看現在有哪些程式在跑」找正確的名稱。', '0.2.69'),
    ('phone_notify', '🔔 手機狀態提醒', '手機網頁開著時，狀態有變化就跳提醒：👀 自動找到新影片、📤 複製到上傳資料夾完成、🎉 今天目標達成、⚠ 硬碟空間不足、✂ 剪輯都好了、⚡ 自動規則分了幾部；晚上 9 點今天目標還沒達成也提醒一次。手機允許通知的話，切到別的 App 時也會跳系統通知（在 工具 頁打開時會問）。', '0.2.72'),
    ('res_chips', '📺 依畫質篩選', '檔案總管時長那排下面多一排：全部畫質／< 720p／720p／1080p／4K（看影片的短邊，直的手機影片也算得對），一按就只列那個畫質，可以跟分級、搜尋、時長一起用。手機檔案總管也有同一排。', '0.2.78'),
    ('note_presets', '✎ 快速備註', '常用的備註一鍵加上（預設：可剪、好笑、重看、要上傳，可以自己改）：電腦清單右鍵 → 🏷 標記 → ✎ ＋「可剪」；手機看檔案按「✎ 備註」會先跳出這些選項。加在原本備註後面，不會重複，可以 Ctrl+Z 復原。打開這個功能後，檔案總管搜尋框也會找備註：打「可剪」就列出所有標了可剪的。', '0.2.82'),
    ('folder_prog', '📂 各資料夾分級進度', '一張表看每個資料夾：幾部、多大、可以審（預覽圖好了還沒分級）幾部、還沒分幾部、分級進度 %、預覽圖做了多少、F 待刪多大；可以審最多的排最前面，點兩下直接到那個資料夾只看可以審的。在 🧰 工具箱 或 Ctrl+K；手機在 工具 →「🆕 新功能」。', '0.2.84'),
    ('playlist', '▶ 連播', '一部接一部播：電腦清單選好幾部按右鍵「▶ 連播選的 N 部」（只選一部＝從這部開始把清單播下去），播完自動換下一部，播放器下面有「⏭ 下一部」，Esc 關掉＝停止連播；播放中照樣可以分級、加書籤。手機檔案總管分級列前面「▶」＝從頭連播目前清單。', '0.2.90'),
    ('file_hist', '📜 這部的紀錄', '一部影片從掃描到現在發生過什麼：🔎 掃描到、🖼 預覽圖做好、👁 看過、🏷 分級、✂ 剪了哪幾段、🔁 轉檔、📦 歸檔／🗑 待刪／搬到哪裡、↩ 復原、🔖 書籤，新的在上面。電腦清單右鍵「📜 這部的紀錄」；手機看檔案按右上「⋯」裡面。', '0.2.98'),
    ('bottom_nav', '👍 手機分頁放下面（單手好按）', '手機專用：上面那排「檔案總管／整理／工具／設定」移到螢幕最下面，大拇指就按得到；看檔案、播放的時候自動藏起來。電腦和網頁版不受影響。', '0.3.08'),
    ('scenes', '🎬 換場景標記', '看預覽圖時，自動找出畫面「換場景」的地方（前後兩格差很多），在那一格左邊畫一條橘線：剪片時一眼看出哪裡換鏡頭、換段落。用已經做好的預覽圖算，不用重讀影片，一部大約一兩秒。也會找出「😴 靜止／全黑」的段落（連續 5 格以上幾乎沒變，例如直播主離開、黑畫面）蓋一層灰，右鍵「✂ 選全部、跳過靜止的」一鍵把有內容的都選起來。還會標出「🔥 畫面動得最多」的地方（格子下面紅線），右鍵「🔥 選畫面動得最多的地方」快速挑精華。清單多選後右鍵「✂ 批次：都剪掉 😴 靜止段落」：每部把靜止的剪掉、有內容的合成一個新檔（原檔不動）。手機看檔案時一樣有。', '0.3.09'),
    ('still_scan', '😴 背景算靜止比例', '背景慢慢把每部影片「靜止／黑畫面佔幾 %」算好（用預覽圖，一次一部，電腦很忙或讀影片資訊暫停時先停）。算好之後：篩選多「😴 大多是靜止的」（6 成以上），⚡ 規則分級可以用「靜止超過 N % → F」。', '0.3.12'),
    ('smart_card', '🖼 卡片縮圖挑最精彩那格', '檔案總管卡片的縮圖，不再隨機挑一格，改成挑「畫面最精彩」的那一格（動得最多、避開頭尾 10%、靜止和黑畫面）。在背景慢慢算（會順便算好 😴 靜止比例）；你自己按「🎲 換一張卡片縮圖」換過的不會動。', '0.3.22'),
    ('share_auto', '🔄 新功能設定自動存到硬碟', '每次把紀錄寫到各硬碟時（1 小時最多一次），順便把新功能設定（開關、自動規則、常用篩選…）也存上去；打開程式時如果硬碟上有另一台電腦比較新的設定，下方會提醒你去套用（不會自己蓋掉）。', '0.3.30'),
    ('caption', '📋 上傳文案', '選好影片按右鍵「📋 複製上傳文案」，照你的範本組好一段文字放進剪貼簿，直接貼到 TikTok：範本可以用 {作者}（從檔名猜）{檔名} {日期} {分級} {備註} {長度}，預設「{作者} {日期}／{備註}／#直播 #精華」。手機看檔案的「⋯」裡也有，會直接複製。', '0.3.43'),
    ('cmdk', '⌘ 指令面板（Ctrl+K）', '按 Ctrl+K 跳出搜尋框：打幾個字就能找到頁面、動作（掃描、暫停、封面…）、資料夾、影片，Enter 直接去', '0.2.30'),
    ('sprint', '⏱ 分級衝刺', '選 10／15／25／45 分鐘，倒數計時專心分級：下方狀態列（手機首頁）顯示還剩幾分鐘、分了幾部、每分鐘幾部；時間到跳結果，破紀錄有 🏆。歷史紀錄看得到自己有沒有變快。', '0.3.72'),
    ('weekly', '📆 每週回顧', '每週第一次打開時，狀態列（手機工具頁）跳一張這 7 天的回顧：分了幾部（跟前 7 天比）、上傳幾部、剪幾段、省下多少空間、衝刺最佳、哪天最拚、還剩多少沒分。工具箱點卡片隨時看。', '0.3.80'),
    ('random_pick', '🎲 隨便抽一部', '看膩了換換口味：從這個資料夾（含子資料夾）還沒分級的影片裡隨便抽一部打開。電腦按 Ctrl+R 或搜尋框旁的 🎲、指令面板也有；手機檔案總管上面的 🎲。', '0.3.84'),
    ('break_remind', '👀 休息提醒', '連續分級（中間沒停超過 5 分鐘）超過 45 分鐘（可以改 30 分～2 小時）就提醒你站起來動一動、讓眼睛休息；同一段只提醒一次。電腦狀態列、手機都會跳。', '0.3.88'),
    ('whats_new', '🆕 更新後看這次多了什麼', '更新（包括一次跳好幾版）之後第一次打開，跳一張「從 V舊 到 V新 多了什麼」：把中間每一版的改變一次列出來，不會漏看。手機工具頁也會出現一次。', '0.3.97'),
    ('conn_bar', '📶 手機連線狀態列', '手機網頁連不到電腦時（Tailscale 斷了、電腦睡著），最上面一直顯示紅色「連不到電腦，自動重試中（上次連上幾點）」，連回來自動變綠消失；不用猜畫面為什麼不動。', '0.4.02'),
    ('keep_awake', '☕ 背景在做事時不睡', '轉檔、預覽圖、初剪、複製到上傳、搬硬碟還在跑時，不讓 Windows 自動睡著（螢幕照樣會關）；全部做完就恢復平常的睡眠設定。晚上排隊複製、轉檔不會做到一半停掉。', '0.4.03'),
    ('done_notify', '🔔 背景全部做完通知', '轉檔、預覽圖、初剪、複製到上傳、搬硬碟全部做完（而且之前至少做了 5 分鐘）時，電腦右下角跳通知「全部做完了」；開了 🔔 手機狀態提醒的話手機也會收到。', '0.4.04'),
    ('unplug_check', '🔌 拔硬碟前看一下', '要拔硬碟前打開：每顆接著的硬碟現在有沒有在讀寫（做預覽圖、轉檔、初剪、複製、搬硬碟），沒在用的顯示「✅ 可以拔」；有在用的會寫在做什麼，可以先按暫停。', '0.4.49'),
    ('web_ro', '👀 手機唯讀 PIN', '另外設一組「唯讀 PIN」給別人（例如家人、助理）：用這組登入的手機只能看清單、看影片、看報表，不能分級、搬檔、刪除、改設定。工具箱點卡片設定或清除；「登出所有手機」也會登出唯讀的。', '0.4.30'),
    ('web_devices', '📱 登入過的手機', '列出每支登入過的手機（iPhone／Android／電腦瀏覽器、從哪個網址、第一次和最後一次用的時間、是不是唯讀），可以只登出其中一支（手機掉了、換手機時）。工具箱點卡片看。', '0.4.31'),
]
LAB_LIST += [(k, n, v) for k, n, _d, v in NEW_LABS]
LAB_TOOLS = [('🔤 亂碼檔名解碼改名', '0.1.26'), ('🎲 隨機抽一部沒看過的', '0.1.10'), ('🔍 找重複的影片', '0.1.10'), ('🧬 找畫面相似的影片', '0.1.36'), ('🆚 並排比較兩部', '0.1.40'), ('🩺 影片庫健康檢查', '0.1.18'), ('🧹 清理用不到的預覽圖', '0.1.19'), ('📊 整理成果統計', '0.1.25')]


class HelpPage(QWidget):
    """📖 使用說明：建議流程、所有快捷鍵（播放器的照你目前的設定）、小技巧、資料放哪裡."""
    def __init__(self, win):
        super().__init__(); self.win = win
        v = QVBoxLayout(self); v.setContentsMargins(8, 8, 8, 8)
        t = QLabel('📖 使用說明（F1 隨時打開）'); t.setObjectName('title')
        b_ = QPushButton('🧭 合併導覽（FileCompare 怎麼用）'); b_.clicked.connect(lambda: self.win.merge_tour(True))     # V0.5.26
        b2_ = QPushButton('📖 整理的說明'); b2_.clicked.connect(lambda: self.win.enter(64))
        h_ = QHBoxLayout(); h_.addWidget(t); h_.addStretch(1); h_.addWidget(b_); h_.addWidget(b2_); v.addLayout(h_)
        self.tx = QTextBrowser(); self.tx.setOpenExternalLinks(False); v.addWidget(self.tx, 1)

    def showEvent(self, e):
        super().showEvent(e); self.render()

    def render(self):
        K = player_keys()
        def keyrow(k, a, n):
            nm = PLAYER_ACTIONS[a][0]
            if a == 'seek': nm = ('往回 ' if n < 0 else '往前 ') + (fmt_t(abs(n)) if abs(n) >= 60 else f'{abs(n)} 秒')
            elif a == 'pct': nm = f'跳到全片的 {n:g}%'
            return f'<tr><td><code>{k}</code></td><td>{nm}</td></tr>'
        T = lambda rows: '<table cellspacing="0" cellpadding="3">' + ''.join(f'<tr><td><code>{a}</code></td><td>{b}</td></tr>' for a, b in rows) + '</table>'
        h = f"""<style>h2{{color:#4dc9ff}} h3{{color:#9fb3c8}} code{{background:#1d2430;color:#ffc94d}} td{{padding-right:18px}} li{{margin:3px 0}}</style>
<h2>建議的整理流程</h2><ol>
<li><b>加硬碟</b>：檔案總管左上「➕ 加入硬碟／資料夾」。掃描只讀檔名和大小，不會動檔案。不想整理的資料夾：在資料夾上按右鍵「🚫 排除」。</li>
<li><b>等預覽圖</b>：背景每 2 秒一張慢慢做（HDD 一次一部、別的程式在用就讓路）。上方和後台會顯示「預計還要多久」，做完右下角會通知。想晚上全速做：🧪 實驗工作區「🚀 背景加速」。</li>
<li><b>看＋選片段</b>：右邊格子點一格＝選、再點＝取消、按住拖曳＝圈選一段；長按或點兩下＝從那裡播放。上面「間隔」可以改成每 4～600 秒一張看長片。</li>
<li><b>剪</b>：「✂ 輸出初剪」→ 選每段一個檔（_01、_02…）或合併成一個（_ALL）。快速免轉檔，幾秒就好；上方「✂ 剪輯／轉檔」的數字會跳，剪完變綠。</li>
<li><b>分級</b>：按 S／A／E／F（0＝取消），可以多選一次改；清單上方的分級標籤看還剩幾部沒分。</li>
<li><b>歸檔</b>：清單上方「📦 一鍵歸檔」把分好級的一次搬到 VideoSIFT\\S_無條件保存…；特別的檔案右鍵「📦 歸類到」自己的分類（工作用、家庭日…）。</li>
<li><b>刪原檔</b>：剪好的影片右邊會出現「🗑 刪除原檔」（丟資源回收筒，連預覽圖一起刪，初剪檔永久保留）。所有動作都記在「📒 操作紀錄」30 天，搬錯可以搬回來。</li></ol>
<h2>快捷鍵</h2>
<h3>到處都能用</h3>{T([('Ctrl+L', '回到封面（不留任何影片內容）'), ('F1', '使用說明')])}
<h3>檔案總管清單／卡片</h3>{T([('Ctrl／Shift＋點、Ctrl+A', '多選、全選'), ('S A E F 0', '分級（多選時一次改全部）'), ('Enter', '播放'), ('N／Shift+N', '下一部／上一部還沒分級的'), ('Del', '移到待刪'), ('Shift+Del', '刪除已剪輯的原檔'), ('Ctrl+Z', '復原分級／標籤／備註／看過'), ('Ctrl+F', '搜尋'), ('右鍵', '檔案總管定位、預設程式開啟、內容、標記、歸類…')])}
<h3>預覽格子</h3>{T([('點一格', '選／取消'), ('按住拖曳', '圈選一段（從已選的格拖＝取消）'), ('Shift＋點', '從上一次點的選到這格'), ('長按、點兩下', '從那裡播放'), ('Ctrl＋滾輪', '一列幾張'), ('Alt＋滾輪', '間隔（每幾秒一張）'), ('右鍵', '全選、反選、從這格選到最後…')])}
<h3>播放視窗（照你目前的設定；設定 → 🎬 播放器快捷鍵 可以改）</h3><table cellspacing="0" cellpadding="3">{''.join(keyrow(*x) for x in K)}</table>
<p>畫面上按住左右拖曳＝移動時間：拖得快、拖得長＝跳得遠（一次最多影片長度的 {int(ENG.cfg.get('drag_pct') if ENG.cfg.get('drag_pct') is not None else 10)}%），慢慢拖＝幾秒幾秒細調；點兩下＝全螢幕；滾輪＝音量。</p>
<h2>小技巧</h2><ul>
<li>更新：把 SC_V….zip 丟進 UPDATE 資料夾，上面會跳「立即熱更新」，程式不用關；只要裝最新那包就好，不用一個一個裝。</li>
<li>卡片縮圖不喜歡：右鍵「🎲 換一張卡片縮圖」。卡片邊框顏色＝分級，左上 ✔＝看過、★＝收藏。</li>
<li>找東西：篩選有「沒看過、收藏、有初剪、顏色標籤、有備註、已歸檔」；🧪 開「進階搜尋」可以打 &gt;1h 4k hevc 這種條件。</li>
<li>電腦怪怪的、畫面卡：LOG 頁有錯誤紀錄、卡頓紀錄（會記卡在哪一行）、當機傾印，可以「📤 匯出最近 7 天」給我看。</li>
<li>重複的影片：🧪 實驗工作區「🔍 找重複」看大小／長度，「🧬 找畫面相似」看畫面（轉過檔、縮小的也找得到）；選一部按「🆚 並排比較」決定留哪部，或「🏷 每組只留最大的」一次標 F。</li>
<li>🔥 HotZone（整進 SortCut 了）：左邊「HotZone 檔案／圖片與影片／傳輸與熱區／系統」就是 HotZone 原本的各頁，點了直接在 SortCut 裡面顯示（HotZone 的畫面嵌在右邊，要電腦上的 Python 裝 PySide6）。「HotZone 總管」管背景引擎、整合資料。第一次：①「🔍 檢查環境」②沒裝好按「📦 安裝需要的套件」（用電腦上的 Python 3.11）③原本的 HotZoneFM.exe 還在跑就按「🔁 接手」，沒在跑就按「▶ 啟動背景引擎」（Windows 會問一次系統管理員權限）④「🪟 打開 HotZone」。設定、搬檔佇列、熱區、索引、保管區都還是讀原本 HotZone 的資料夾。硬碟協調員：同一顆 HDD 兩邊都在大量讀寫、忙碌一直很高時只讓一邊做（你排的優先，背景工作輪流），每一次讓誰都記在 HotZone 頁和 LOG。</li>
<li>🔁 轉檔工作區：①「➕ 選檔加入」選要轉的（非 MP4 → H.265 MP4、H.264 MP4 → H.265、或兩種）、類型、大小範圍、資料夾（含子資料夾），排序可以選「💡 最省空間優先」（位元率高的先轉）；②「⚙ 轉檔中」看進度、重新排序、暫停；③「✔ 轉檔完成」看轉檔前後大小差多少，雙擊打開轉好的 MP4 抽檢（或按「🎲 隨機抽 5 部」），沒問題再按「🗑 刪除已轉檔完成的原檔」。轉好的放在原本的資料夾，原檔先搬到那顆硬碟最外層的 DELETE 資料夾；預覽圖、分級、人物都沿用不重做。每部都會自動檢查長度和畫質（SSIM），轉了沒變小的會自動放棄、留原檔。<br>
🎯 <b>自動方式（預設）</b>：每一部先從 10%／30%／50%／70%／90% 各取一小段，用顯示卡試不同 CQ，找「畫質分數（SSIM）還在 0.985 以上」最省的那個再整部轉，轉完不再整部重比。
轉完沒到目標的：先按「🔍 沒到目標的重新驗證畫質」（之前 .ts 這類分數算錯的很多其實沒問題），還是沒到的再按「🔁 沒到目標的全部重轉」（用 DELETE 裡的原檔重轉，到目標才換掉舊的，原檔留在 DELETE 等你刪），或「↩ 全部還原」。</li>
<li>📈 滾動式參數：🎯 自動方式會把每一部的結果記成經驗，照「編碼＋解析度＋影格率＋位元率」分類。同一類越多，樣本越少（5 段×2 秒 → 3 段×2 秒 → 3 段×1 秒）；100 次以上又很穩就直接套用、轉完照機率抽查；抽查低於底線 0.975 就更保守重轉、那一類先退回完整測試。左邊「📈 滾動式參數」看每一類現在用哪種方式、CQ 分布、抽查結果。</li>
<li>⏯ 後台總控制（後台狀態頁最上面）：每一項背景工作可以暫停、繼續、立刻停、調先後順序，暫停時顯示停在哪一部、總進度幾 %，重開程式還記得。開始／繼續會慢慢加速；CPU 一直很高時，從順序最後的先讓路（沒有更優先的就降速）。右下狀態列會顯示目前暫停／讓路／降速的項目。</li>
<li>🧪 碼率測試（左邊影片工具）：選一部，一次轉出好幾種碼率／畫質比大小和畫質，列出原檔詳細格式；「🎯 自動找這部最省的設定」可以先試試自動方式會選什麼。</li>

<li>左邊側邊欄：分組選單（點分組標題可以收起來）、電腦狀態（點一下開效能浮窗）、預覽圖進度、剪輯／轉檔；下面狀態列可以切深色／淺色、調介面大小。</li>
<li>🧭 工作流程（左邊選單照這個順序）：① 檔案管理（16 格快速分類到資料夾）→ ② 檔案剪輯（每 10 秒一張預覽圖、S A E F 分級、初剪）→ ③ 畫質降容量（轉檔／影片瘦身，SSIM 畫質目標；同一部不會兩邊都轉）→ ④ 隔離區・壞掉的檔 → ⑤ 重複檔案（以「整理」的重複檔＋最佳解為主）→ ⑥ 照片分類與找圖。三套設定分開：設定：SortCut／設定：整理／設定：HotZone。</li>
<li>🗂 整理（原本的 FileCompare）：整套跑在 SortCut 裡面，資料在 VideoSift\\FileCompare\\Data；舊電腦用過的話按「📥 匯入舊 FileCompare 資料」選舊的 Data 資料夾，重開就接上（R 碟代號要一樣）。SortCut 在大量讀某顆硬碟時，整理在那顆的比對指紋、損毀檢查、讀拍攝資訊（整檔讀的）會先讓路（掃資料夾、16 格預覽很輕，照做）（上面小膠囊會寫「🤝 讓 SortCut 先用 R 碟」）。兩邊搬檔、改名、轉檔會互相通知，紀錄跟著搬（預覽圖、分級、指紋都沿用，不重做）；整理瘦身好的 _h265.mp4 直接接手 SortCut 原本那筆；SortCut 轉檔中，影片瘦身先等。手機：下面「🗂 整理」。</li>
<li>🗂 檔案總管沒列出來的格式：手機／遠端只能播 MP4，所以 ts、flv、avi… 預設不列（清單上方會寫幾部沒列出來）。設定 →「🗂 檔案總管列出的格式」可以自己勾。沒列出來的照樣做預覽圖，轉成 MP4 之後就會出現。</li>
<li>外接硬碟拔掉、睡著：那顆的工作自動暫停，不會被當成壞檔；接回來自動繼續（下方會提醒）。</li>
<li>📱 用手機遙控：設定 → 📱 手機網頁 → 打勾、自己設 PIN → 按「📱 手機 App（Tailscale HTTPS）」，網址會複製好（https://電腦名稱:9461/），手機打開後可以安裝成 App。用自己的埠，不會跟 TikLive、FusionStitch 打架。</li>
<li>資料庫出問題（例如突然斷電）：設定 → 資料庫備份 →「↩ 從備份還原…」；打不開時程式也會自己換成最近一份好的備份。</li></ul>
<h2>資料放哪裡</h2><ul>
<li>剪好的、收藏、待刪、原檔備份、歸檔、截圖：每顆硬碟的 <code>VideoSIFT\\</code> 底下（自動排除、不會被掃描）。</li>
<li>每顆硬碟自己的紀錄（分級、標籤、備註、書籤、預覽圖）：<code>X:\\VideoSIFT\\.vsdata\\</code>，硬碟接到哪台電腦，紀錄就跟到哪台（V0.2.27 起）。</li>
<li>這台電腦的總資料庫：程式資料夾的 <code>Data\\videosift.sqlite3</code>，每天自動備份到 <code>Data\\db_backup</code>。LOG：<code>LOG\\</code>。</li></ul>"""
        try: h += '<h2>🚀 用新功能的建議流程</h2><ol>' + ''.join(f'<li><b>{html_esc(a_)}</b>：{html_esc(b_)}</li>' for a_, b_ in NEW_FLOW) + '</ol><p style="color:#8994a4">（左邊「🧰 新功能工具箱」上面有「一次打開一組」）</p>'   # V0.3.18
        except Exception: pass
        try:                                                                    # V0.2.61 🆕 新功能說明（照實驗工作區的開關）
            L_ = lab_cfg(); vt_ = lambda x: tuple(int(p_) for p_ in re.findall(r'\d+', str(x))[:3])
            h += '<h2>🆕 新功能（V0.2.30 起，在 🧪 實驗工作區 或 🧰 新功能工具箱 打開）</h2><table cellspacing="0" cellpadding="4">' + ''.join(
                f'<tr><td valign="top" style="white-space:nowrap">{"✅" if L_.get(k_) else "⬜"} <b>{html_esc(n_)}</b><br><small style="color:#8994a4">V{v_}</small></td><td>{html_esc(d_)}</td></tr>'
                for k_, n_, d_, v_ in sorted(NEW_LABS, key=lambda x: vt_(x[3]), reverse=True)) + '</table><p style="color:#8994a4">✅＝已經打開　⬜＝還沒打開</p>'
        except Exception: ENG.log.err('說明：新功能')
        self.tx.setHtml(h)


def face_crop_image(face, frow, size=96):
    """從預覽圖大張切出一張臉（多留 35% 邊），回傳 QImage。背景執行緒可以呼叫（只用 QImage）."""
    try:
        d = Path(frow.get('th_dir') or ''); S = sorted(d.glob('s*.jpg')); cols = int(frow.get('th_cols') or 10); rows = int(frow.get('th_rows') or 10); per = cols * rows; k = int(face['k'])
        if not S or k // per >= len(S): return QImage()
        big = QImage(str(S[k // per]))
        if big.isNull(): return QImage()
        tw, th = big.width() // cols, big.height() // rows; q = k % per; ox, oy = (q % cols) * tw, (q // cols) * th
        x, y, w, h = face['x'] * tw, face['y'] * th, face['w'] * tw, face['h'] * th; m = 0.35 * max(w, h); side = max(w, h) + 2 * m
        cx, cy = x + w / 2, y + h / 2; X = int(max(0, cx - side / 2)); Y = int(max(0, cy - side / 2)); Wd = int(min(tw - X, side)); Ht = int(min(th - Y, side))
        if Wd < 4 or Ht < 4: return QImage()
        return big.copy(ox + X, oy + Y, Wd, Ht).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    except Exception: return QImage()


class PeoplePage(QWidget):
    """👤 人物（V0.1.51）：用已經做好的每 2 秒預覽圖找臉、長得像的分成同一群；取名字之後新影片自動套用；點一個人列出他出現的影片和時間點."""
    def __init__(self, win):
        super().__init__(); self.win = win; self.cur = None; self.P = []; self._icons = {}; self._gen = 0
        v = QVBoxLayout(self); v.setContentsMargins(8, 8, 8, 8)
        r = QHBoxLayout(); v.addLayout(r); t = QLabel('👤 人物（人臉分類）'); t.setObjectName('title'); r.addWidget(t)
        self.st = QLabel(''); self.st.setTextFormat(Qt.RichText); self.st.setWordWrap(True); r.addWidget(self.st, 1)
        self.b_go = QPushButton('▶ 開始'); self.b_go.setObjectName('start'); self.b_stop = QPushButton('⏹ 停止'); self.b_rc = QPushButton('🔁 重新分群'); self.b_set = QPushButton('⚙ 設定'); self.b_set.setCheckable(True)
        for b_ in (self.b_go, self.b_stop, self.b_rc, self.b_set): r.addWidget(b_)
        self.b_rc.setToolTip('不重新找臉，只把找到的臉重新分群（取了名字的人和你改過的不會被打亂）')
        # ---- 設定
        self.sg = QGroupBox('⚙ 人臉分類設定（只在這台電腦跑，不連網、不查身分）'); f = QFormLayout(self.sg); v.addWidget(self.sg); self.sg.setVisible(False)
        self.c_ratio = QSpinBox(); self.c_ratio.setRange(1, 100); self.c_ratio.setSuffix(' %'); self.c_src = QComboBox(); self.c_src.addItem('每 2 秒的預覽圖（快，不碰硬碟）', 'thumbs'); self.c_src.addItem('從影片抽原畫面（準，會讀硬碟，比較慢）', 'video')
        self.c_thr = QComboBox()
        for nm_, k_ in (('嚴格（不像的不會混進來，但同一人可能分成好幾群）', 'strict'), ('一般（建議）', 'normal'), ('寬鬆（比較會合在一起，可能混到別人）', 'loose')): self.c_thr.addItem(nm_, k_)
        self.c_min = QSpinBox(); self.c_min.setRange(2, 50); self.c_min.setSuffix(' 張臉以上才算一個人'); self.c_gpu = QCheckBox('用顯示卡（RTX 3060：CUDA，沒有的話 DirectML）')
        self.c_px = QSpinBox(); self.c_px.setRange(0, 400); self.c_px.setSpecialValueText('自動（預覽圖 16、原畫面 40）'); self.c_px.setSuffix(' 像素')
        self.c_night = QCheckBox('晚上自動跑：'); self.c_nf = QLineEdit(); self.c_nt = QLineEdit(); self.c_nf.setFixedWidth(60); self.c_nt.setFixedWidth(60)
        rn = QHBoxLayout(); rn.addWidget(self.c_night); rn.addWidget(self.c_nf); rn.addWidget(QLabel('～')); rn.addWidget(self.c_nt); rn.addWidget(QLabel('（時段外會自動停，下次接著做）')); rn.addStretch(1)
        self.c_auto = QSpinBox(); self.c_auto.setRange(1, 50); self.c_auto.setSuffix(' 次以上才自動歸類')
        self.c_py = QLineEdit(); self.c_py.setPlaceholderText('空白＝自動找（py -3.11、python）'); bpy = QPushButton('選…'); rp = QHBoxLayout(); rp.addWidget(self.c_py, 1); rp.addWidget(bpy)
        self.env_l = QLabel('（還沒檢查）'); self.env_l.setWordWrap(True); self.env_l.setTextFormat(Qt.RichText); self.env_l.setTextInteractionFlags(Qt.TextSelectableByMouse)
        re_ = QHBoxLayout(); b_chk = QPushButton('🔍 檢查環境'); b_i1 = QPushButton('📦 安裝需要的套件（NVIDIA 顯示卡）'); b_i2 = QPushButton('DirectML 版'); b_i3 = QPushButton('只用 CPU'); b_log = QPushButton('📜 人臉 LOG')
        for b_ in (b_chk, b_i1, b_i2, b_i3, b_log): re_.addWidget(b_)
        re_.addStretch(1)
        f.addRow('每部影片抽', self.c_ratio); f.addRow('來源', self.c_src); f.addRow('長得像的程度', self.c_thr); f.addRow('一群至少', self.c_min); f.addRow('', self.c_gpu); f.addRow('臉至少', self.c_px)
        f.addRow('', rn); f.addRow('自動歸類：出現', self.c_auto); f.addRow('Python', rp); f.addRow(re_); f.addRow(self.env_l)
        f.addRow(self._note('第一次：按「檢查環境」→ 沒裝好就按「安裝需要的套件」（用你電腦上的 Python 3.11，pip --user 安裝，不會動到 SortCut）。模型用 %USERPROFILE%\\.insightface\\models\\buffalo_l（你已經有了）。'
                            '兩萬部影片抽 10% 大約要幾個小時（顯示卡），可以晚上掛著跑；中斷（關機、按停止、超過時段）之後再開，會接著做還沒做的。'))
        # ---- 人物清單＋右邊細節
        rq = QHBoxLayout(); v.addLayout(rq); self.q = QLineEdit(); self.q.setPlaceholderText('🔎 找名字'); self.q.setClearButtonEnabled(True); self.c_hid = QCheckBox('顯示隱藏的'); self.c_named = QCheckBox('只看取了名字的')
        self.cnt = QLabel(''); self.cnt.setObjectName('muted'); rq.addWidget(self.q, 1); rq.addWidget(self.c_named); rq.addWidget(self.c_hid); rq.addWidget(self.cnt)
        sp = QSplitter(Qt.Horizontal); v.addWidget(sp, 1)
        self.lst = QListWidget(); self.lst.setViewMode(QListView.IconMode); self.lst.setIconSize(QSize(96, 96)); self.lst.setGridSize(QSize(118, 140)); self.lst.setResizeMode(QListView.Adjust)
        self.lst.setMovement(QListView.Static); self.lst.setSelectionMode(QAbstractItemView.ExtendedSelection); self.lst.setWordWrap(True); sp.addWidget(self.lst)
        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(6, 0, 0, 0); sp.addWidget(right); sp.setSizes([520, 680])
        rn2 = QHBoxLayout(); rv.addLayout(rn2); self.nm = QLineEdit(); self.nm.setPlaceholderText('幫這個人取名字（按 Enter 存）'); self.b_nm = QPushButton('💾 存名字'); rn2.addWidget(self.nm, 1); rn2.addWidget(self.b_nm)
        rb = QHBoxLayout(); rv.addLayout(rb); self.b_merge = QPushButton('🔗 把左邊選的合併到這個人'); self.b_hide = QPushButton('🙈 隱藏'); self.c_ac = QCheckBox('新影片自動歸到分類資料夾「名字」'); self.b_cat = QPushButton('📦 現在就歸類他的影片…')
        for b_ in (self.b_merge, self.b_hide, self.c_ac, self.b_cat): rb.addWidget(b_)
        rb.addStretch(1)
        self.info = QLabel('← 點一個人'); self.info.setObjectName('muted'); rv.addWidget(self.info)
        self.faces = QListWidget(); self.faces.setViewMode(QListView.IconMode); self.faces.setIconSize(QSize(64, 64)); self.faces.setGridSize(QSize(72, 72)); self.faces.setResizeMode(QListView.Adjust)
        self.faces.setMovement(QListView.Static); self.faces.setSelectionMode(QAbstractItemView.ExtendedSelection); self.faces.setMaximumHeight(165); rv.addWidget(self.faces)
        rf = QHBoxLayout(); rv.addLayout(rf); self.b_notme = QPushButton('🚫 不是他（拿掉選的臉）'); rf.addWidget(self.b_notme); rf.addWidget(QLabel('選錯的臉拿掉，之後不會再自動算進任何人')); rf.addStretch(1)
        self.tb = QTreeWidget(); self.tb.setHeaderLabels(['影片', '出現', '時間點（雙擊播放第一次出現）', '分級', '資料夾']); self.tb.setRootIsDecorated(False); self.tb.setAlternatingRowColors(True)
        for i, w_ in enumerate((280, 50, 260, 40)): self.tb.setColumnWidth(i, w_)
        rv.addWidget(self.tb, 1)
        rt = QHBoxLayout(); rv.addLayout(rt); b_play = QPushButton('▶ 從他第一次出現播放'); b_goto = QPushButton('到這部（檔案總管）'); b_rmf = QPushButton('這部不是他'); b_flt = QPushButton('📁 在檔案總管只看他的影片')
        for b_ in (b_play, b_goto, b_rmf, b_flt): rt.addWidget(b_)
        rt.addStretch(1)
        # ---- 連結
        self.b_set.toggled.connect(self.sg.setVisible); self.b_go.clicked.connect(lambda: self._run(lambda: ENG.faces.start('手動')))
        self.b_stop.clicked.connect(lambda: self._run(lambda: ENG.faces.stop('手動'))); self.b_rc.clicked.connect(lambda: self._run(lambda: ENG.faces.start('手動', cluster_only=True)))
        b_chk.clicked.connect(self.check_env); b_i1.clicked.connect(lambda: self.install('cuda')); b_i2.clicked.connect(lambda: self.install('directml')); b_i3.clicked.connect(lambda: self.install('cpu'))
        b_log.clicked.connect(lambda: self.win.logp.show_file('face_log.txt')); bpy.clicked.connect(self._pick_py)
        for w_, k_ in ((self.c_ratio, 'ratio'), (self.c_min, 'min_faces'), (self.c_px, 'minpx'), (self.c_auto, 'auto_min')): w_.valueChanged.connect(lambda n_, k_=k_: self._set(k_, n_ / 100 if k_ == 'ratio' else int(n_)))
        self.c_src.currentIndexChanged.connect(lambda _i: self._set('src', self.c_src.currentData())); self.c_thr.currentIndexChanged.connect(lambda _i: self._set('thr', vs_face.THR[self.c_thr.currentData()]))
        self.c_gpu.toggled.connect(lambda on: self._set('gpu', bool(on))); self.c_night.toggled.connect(lambda on: self._set('night', bool(on)))
        self.c_nf.editingFinished.connect(lambda: self._set('night_from', self._hhmm(self.c_nf.text(), '01:00'))); self.c_nt.editingFinished.connect(lambda: self._set('night_to', self._hhmm(self.c_nt.text(), '07:00')))
        self.c_py.editingFinished.connect(lambda: self._set('python', self.c_py.text().strip()))
        self.q.textChanged.connect(lambda _t: self._qt.start(300)); self._qt = QTimer(self); self._qt.setSingleShot(True); self._qt.timeout.connect(self.load)
        self.c_hid.toggled.connect(lambda _o: self.load()); self.c_named.toggled.connect(lambda _o: self.load())
        self.lst.currentItemChanged.connect(lambda it, _p: self.pick(it)); self.nm.returnPressed.connect(self.save_name); self.b_nm.clicked.connect(self.save_name)
        self.b_merge.clicked.connect(self.merge); self.b_hide.clicked.connect(self.toggle_hide); self.c_ac.toggled.connect(self.toggle_auto); self.b_cat.clicked.connect(self.apply_cat)
        self.b_notme.clicked.connect(self.not_me); self.tb.itemDoubleClicked.connect(lambda _it, _c: self.play()); b_play.clicked.connect(self.play); b_goto.clicked.connect(self.goto)
        b_rmf.clicked.connect(self.rm_file); b_flt.clicked.connect(self.filter_browse)
        self.tm = QTimer(self); self.tm.timeout.connect(self.tick); self.tm.start(2000); self._load_cfg()

    def _note(self, s):
        l_ = QLabel(s); l_.setWordWrap(True); l_.setObjectName('muted'); return l_

    @staticmethod
    def _hhmm(s, d):
        m = re.fullmatch(r'\s*(\d{1,2})[:：](\d{2})\s*', str(s or ''))
        return f'{int(m.group(1)) % 24:02d}:{int(m.group(2)) % 60:02d}' if m else d

    def _load_cfg(self):
        if ENG.faces is None: return
        c = ENG.faces.cfg(); ws = (self.c_ratio, self.c_src, self.c_thr, self.c_min, self.c_gpu, self.c_px, self.c_night, self.c_nf, self.c_nt, self.c_auto, self.c_py)
        for w_ in ws: w_.blockSignals(True)
        self.c_ratio.setValue(int(round(float(c['ratio']) * 100))); self.c_src.setCurrentIndex(max(0, self.c_src.findData(c['src'])))
        self.c_thr.setCurrentIndex(max(0, self.c_thr.findData(min(vs_face.THR, key=lambda k: abs(vs_face.THR[k] - float(c['thr'])))))); self.c_min.setValue(int(c['min_faces'])); self.c_gpu.setChecked(bool(c['gpu']))
        self.c_px.setValue(int(c.get('minpx') or 0)); self.c_night.setChecked(bool(c['night'])); self.c_nf.setText(c['night_from']); self.c_nt.setText(c['night_to']); self.c_auto.setValue(int(c['auto_min'])); self.c_py.setText(c.get('python') or '')
        for w_ in ws: w_.blockSignals(False)

    def _set(self, k, v):
        if ENG.faces is not None: ENG.faces.set_cfg(**{k: v})

    def _run(self, fn):
        if ENG.faces is None: return
        bg(fn, lambda r: (self.win.msg(r.get('message', '')), (self.b_set.setChecked(True), self.check_env()) if r.get('need_env') else None, self.tick()))

    def _pick_py(self):
        p, _ = QFileDialog.getOpenFileName(self, '選 python.exe', '', 'python (python*.exe);;全部 (*)')
        if p: self.c_py.setText(p); self._set('python', p); self.check_env()

    def check_env(self):
        self.env_l.setText('檢查中…（每個找得到的 Python 都試一次，大約 5～20 秒）'); bg(ENG.faces.check_env, self._env_got)

    def _env_got(self, e):
        if not e or not e.get('cmd'):
            self.env_l.setText('<span style="color:#ff5d6c">找不到 Python。</span>到 python.org 下載 Python 3.11 安裝（勾「Add python.exe to PATH」），再按一次檢查。'); return
        pr = e.get('providers') or []; gpu = 'CUDAExecutionProvider' in pr and 'CUDA' or ('DmlExecutionProvider' in pr and 'DirectML') or ''
        miss = [n for n, k in (('onnxruntime', 'ort'), ('numpy', 'numpy'), ('opencv', 'cv2')) if not e.get(k)]
        models = e.get('models') or {}
        self.env_l.setText(f'Python {esc_html(e.get("py", "?"))}（{esc_html(" ".join(e["cmd"]))}）<br>'
                           + ('<span style="color:#45d483">✔ 套件都裝好了</span>' if not miss else f'<span style="color:#ffb02e">還沒裝：{"、".join(miss)} → 按「安裝需要的套件」</span>')
                           + (f'　顯示卡：<b>{gpu}</b>' if gpu else ('　<span style="color:#ffb02e">顯示卡加速還不能用（會用 CPU，比較慢）</span>' if not miss else ''))
                           + (f'　insightface {esc_html(e["insightface"])}' if e.get('insightface') else '')
                           + '<br>模型：' + ('、'.join(f'{esc_html(k)}（{len(v)} 個檔）' for k, v in models.items()) if models else '<span style="color:#ff5d6c">%USERPROFILE%\\.insightface\\models 底下找不到</span>'))

    def install(self, flavor):
        if QMessageBox.question(self, '安裝套件', '用你電腦上的 Python 安裝 onnxruntime、numpy、opencv（pip --user，不會動到 SortCut 和系統）？\n要連網下載，大約 1～5 分鐘。') != QMessageBox.Yes: return
        bg(lambda: ENG.faces.install(flavor), lambda r: (self.win.msg(r.get('message', ''), 12000), self.env_l.setText('📦 ' + r.get('message', '')) if r.get('ok') else QMessageBox.warning(self, '安裝套件', r.get('message', ''))))

    def showEvent(self, e):
        super().showEvent(e); self.tick(); self.load()

    def tick(self):
        if not self.isVisible() or ENG.faces is None: return
        bg(ENG.faces.status, self._st_got)

    def _st_got(self, s):
        run = s.get('running'); pct = s['done'] * 100 // max(1, s['total'])
        txt = (f'<span style="color:#45d483">● 跑中（{esc_html(s.get("by") or "")}）</span>　' if run else ('<span style="color:#ff5d6c">● 出錯了</span>　' if s.get('state') == 'error' else '<span style="color:#8a96a8">● 沒在跑</span>　'))
        txt += f'影片 {s["done"]:,}／{s["total"]:,}（{pct}%）　臉 {s["faces"]:,} 張　人 {s["people"]:,}（取了名字 {s["named"]}）'
        if run and s.get('eta'): txt += f'　還要約 {eta_txt(s["eta"])}'
        if s.get('provider'): txt += f'　{esc_html(s["provider"])}'
        if s.get('msg'): txt += f'<br><small style="color:#8a96a8">{esc_html(s["msg"])[:160]}</small>'
        if s.get('err'): txt += f'<br><small style="color:#ff5d6c">{esc_html(s["err"])[:200]}</small>'
        if s.get('installing'): txt += '<br><small style="color:#ffb02e">📦 安裝套件中…</small>'
        self.st.setText(txt); self.b_go.setEnabled(not run); self.b_stop.setEnabled(bool(run)); self.b_rc.setEnabled(not run)
        if (getattr(self, '_was_run', False) and not run) or (run and time.time() - getattr(self, '_lt', 0) > 30): self._lt = time.time(); self.load()
        self._was_run = run

    # ---- 人物清單
    def load(self):
        if ENG.faces is None: return
        q = self.q.text().strip(); hid = self.c_hid.isChecked(); named = self.c_named.isChecked()
        self._gen += 1; g = self._gen
        def work():
            P = ENG.faces.persons(show_hidden=hid, q=q)
            if named: P = [p for p in P if p['name']]
            return P
        bg(work, lambda P: self._fill(P) if g == self._gen else None)

    def _fill(self, P):
        cur = self.cur['id'] if self.cur else None; self.P = P; self.lst.blockSignals(True); self.lst.clear(); sel = None
        for p in P:
            it = QListWidgetItem((p['name'] or f'未命名 #{p["id"]}') + f'\n{p["n_files"]} 部' + ('　🙈' if p['hidden'] else '') + ('　📦' if p['auto_cat'] else ''))
            it.setData(Qt.UserRole, p['id']); it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            if p['id'] in self._icons: it.setIcon(self._icons[p['id']])
            if not p['name']: it.setForeground(QColor('#8a96a8'))
            self.lst.addItem(it)
            if p['id'] == cur: sel = it
        self.lst.blockSignals(False); self.cnt.setText(f'{len(P)} 個人' + (f'（取了名字 {sum(1 for p in P if p["name"])}）' if P else '　還沒有結果：按「▶ 開始」'))
        if sel is not None: self.lst.setCurrentItem(sel)
        need = [p for p in P if p['id'] not in self._icons and p.get('face')]
        if need: self._load_icons(need[:400])

    def _load_icons(self, P):
        ids = list({p['face']['file_id'] for p in P}); rows = {}
        def work():
            for i in range(0, len(ids), 500):
                for r in ENG.db.q(f'SELECT id, th_dir, th_cols, th_rows FROM files WHERE id IN ({",".join(map(str, ids[i:i + 500]))})'): rows[r['id']] = dict(r)
            return [(p['id'], face_crop_image(p['face'], rows.get(p['face']['file_id']) or {})) for p in P]
        def done(L):
            m = {}
            for pid, img in L:
                if not img.isNull(): self._icons[pid] = QIcon(QPixmap.fromImage(img))
            for i in range(self.lst.count()):
                it = self.lst.item(i); pid = it.data(Qt.UserRole)
                if pid in self._icons: it.setIcon(self._icons[pid])
        bg(work, done)

    def pick(self, it):
        if it is None or ENG.faces is None: return
        pid = it.data(Qt.UserRole); bg(lambda: ENG.faces.person(pid), self._show)

    def _show(self, p):
        self.cur = p
        if not p: self.info.setText('（這個人已經不在了，可能被合併）'); self.tb.clear(); self.faces.clear(); return
        self.nm.setText(p['name'] or ''); self.b_hide.setText('🙉 取消隱藏' if p['hidden'] else '🙈 隱藏（不是人／不重要）')
        self.c_ac.blockSignals(True); self.c_ac.setChecked(bool(p['auto_cat'])); self.c_ac.blockSignals(False)
        nm_ = p['name'] or ('未命名 #' + str(p['id']))
        self.info.setText(f'{nm_}：出現在 {len(p["files"])} 部影片、{p["n_faces"]} 張臉' + ('' if p['name'] else '　→ 取名字之後，新影片長得像會自動套用'))
        self.tb.clear()
        for f in p['files']:
            it = QTreeWidgetItem([f['name'] or '', str(f['faces']), '　'.join(fmt_t(t) for t in f['times'][:30]) + ('…' if len(f['times']) > 30 else ''), f.get('grade') or '', f.get('folder') or ''])
            it.setData(0, Qt.UserRole, f['file_id']); it.setData(1, Qt.UserRole, f['times'][0] if f['times'] else 0); self.tb.addTopLevelItem(it)
        self.faces.clear(); S = p.get('samples') or []
        ids = list({s['file_id'] for s in S}); rows = {}
        def work():
            if ids:
                for r in ENG.db.q(f'SELECT id, th_dir, th_cols, th_rows FROM files WHERE id IN ({",".join(map(str, ids))})'): rows[r['id']] = dict(r)
            return [(s, face_crop_image(s, rows.get(s['file_id']) or {}, 64)) for s in S]
        def done(L):
            if self.cur is not p: return
            for s, img in L:
                it = QListWidgetItem(); it.setData(Qt.UserRole, s['id']); it.setToolTip(fmt_t(s['t']))
                if not img.isNull(): it.setIcon(QIcon(QPixmap.fromImage(img)))
                self.faces.addItem(it)
        bg(work, done)

    def _after(self, r=None, reload_person=True):
        if r and r.get('message'): self.win.msg(r['message'])
        self.load()
        if reload_person and self.cur: pid = (r or {}).get('id') or self.cur['id']; bg(lambda: ENG.faces.person(pid), self._show)
        try: self.win.browse.refresh_people_filter()
        except Exception: pass

    def save_name(self):
        if not self.cur: return
        pid = self.cur['id']; nm = self.nm.text().strip(); self._icons.pop(pid, None); bg(lambda: ENG.faces.rename(pid, nm), self._after)

    def merge(self):
        if not self.cur: return
        ids = [it.data(Qt.UserRole) for it in self.lst.selectedItems() if it.data(Qt.UserRole) != self.cur['id']]
        if not ids: self.win.msg('先在左邊多選（Ctrl＋點）要合併進來的人，再點右邊這個人… 或：選好幾個，最後點的那個當主角'); return
        if QMessageBox.question(self, '合併', '把 ' + str(len(ids)) + ' 群合併到「' + (self.cur['name'] or ('#' + str(self.cur['id']))) + '」？') != QMessageBox.Yes: return
        tgt = self.cur['id']; bg(lambda: ENG.faces.merge(ids, tgt), self._after)

    def toggle_hide(self):
        if not self.cur: return
        pid = self.cur['id']; h = not self.cur['hidden']; bg(lambda: ENG.faces.set_flag(pid, hidden=h), lambda r: self._after(r))

    def toggle_auto(self, on):
        if not self.cur: return
        if on and not self.cur['name']: self.win.msg('先取名字（分類資料夾用名字當名稱）'); self.c_ac.blockSignals(True); self.c_ac.setChecked(False); self.c_ac.blockSignals(False); return
        if on and QMessageBox.question(self, '自動歸類', f'之後找到「{self.cur["name"]}」出現 {ENG.faces.cfg()["auto_min"]} 次以上的影片，會自動搬到每顆硬碟的 VideoSIFT\\{self.cur["name"]}（現在已經找到的也會）。\n\n每一筆都記在操作紀錄，可以搬回。確定？') != QMessageBox.Yes:
            self.c_ac.blockSignals(True); self.c_ac.setChecked(False); self.c_ac.blockSignals(False); return
        pid = self.cur['id']; bg(lambda: ENG.faces.set_flag(pid, auto_cat=on), self._after)

    def apply_cat(self):
        if not self.cur: return
        if not self.cur['name']: self.win.msg('先取名字'); return
        if QMessageBox.question(self, '歸類', f'把「{self.cur["name"]}」出現 {ENG.faces.cfg()["auto_min"]} 次以上、還沒歸檔的影片，搬到分類資料夾「{self.cur["name"]}」？（操作紀錄可以搬回）') != QMessageBox.Yes: return
        pid = self.cur['id']; bg(lambda: ENG.faces.apply_cat(pid), lambda r: (self.win.msg(r.get('message', ''), 10000), self.win.browse.load_list()))

    def not_me(self):
        ids = [it.data(Qt.UserRole) for it in self.faces.selectedItems()]
        if not ids: self.win.msg('先在上面選錯的臉（可以多選）'); return
        bg(lambda: ENG.faces.remove_faces(ids), self._after)

    def _cur_file(self):
        it = self.tb.currentItem(); return (it.data(0, Qt.UserRole), it.data(1, Qt.UserRole)) if it else (None, 0)

    def play(self):
        fid, t = self._cur_file()
        if not fid: return
        r = ENG.file(fid)
        if not r: return
        p_ = Player(self.win, r['path'], max(0.0, float(t or 0) - 2), r['name'], fid=fid); p_.setAttribute(Qt.WA_DeleteOnClose); p_.show()

    def goto(self):
        fid, _t = self._cur_file()
        if fid: self.win.nav.setCurrentRow(0); self.win.browse.goto_file(fid)

    def rm_file(self):
        fid, _t = self._cur_file()
        if not fid or not self.cur: return
        pid = self.cur['id']; bg(lambda: ENG.faces.remove_file(pid, fid), self._after)

    def filter_browse(self):
        if not self.cur: return
        self.win.nav.setCurrentRow(0); self.win.browse.show_person(self.cur['id'], self.cur['name'] or f'#{self.cur["id"]}')


# ============================================================ 🗂 整理（FileCompare 整套搬進來，取代原本的「審核」）V0.5.00
FC_PAGES = {40: 0, 41: 11, 42: 1, 43: 26, 44: 12, 45: 24, 46: 25, 47: 2, 48: 17, 49: 3, 50: 10, 51: 4, 52: 13, 53: 14, 54: 15, 55: 16, 56: 18, 57: 19, 58: 20,
            59: 21, 60: 23, 61: 22, 62: 7, 63: 6, 64: 9, 65: 5}                    # SortCut 選單頁碼 → FileCompare 的頁碼


def fc_root():
    """FileCompare 的資料（設定、資料庫、縮圖）放在 SortCut 資料夾裡的 FileCompare\\."""
    return ROOT / 'FileCompare'


# ============================================================ V0.5.70 🎛 三段切換＋📊 一頁總覽（電腦版；資料跟網頁同一份 vs_dash）
DZC = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767']; DZG = '#5b6573'
MODE_COL = {'vs': '#4dc9ff', 'fc': '#9085e9', 'h265': '#ff9f43'}
MODE_DASH = {'vs': 70, 'fc': 71, 'h265': 72}


_EV_PRESS = QEvent.Type.MouseButtonPress if hasattr(QEvent, 'Type') else QEvent.MouseButtonPress
_ULI = {'pos': None, 't': 0.0}


def user_last_input():
    """V0.5.91 最後一次有人動滑鼠／鍵盤的時間（問 Windows，不用攔截每個畫面事件）."""
    try:
        if os.name == 'nt':
            import ctypes

            class _LII(ctypes.Structure): _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]
            li = _LII(); li.cbSize = ctypes.sizeof(_LII)
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
                ms = (ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF
                return time.time() - ms / 1000.0
        p = QCursor.pos(); p = (p.x(), p.y())
        if _ULI['pos'] is None: _ULI['pos'] = p                                 # 第一次只記位置（不算有人動）
        elif p != _ULI['pos']: _ULI['pos'] = p; _ULI['t'] = time.time()
        return _ULI['t']
    except Exception: return 0.0


def _dzp(a, b): return round(a * 1000 / b) / 10 if b else 0


class ModeSwitch(QFrame):
    """左上角三段切換：🎬 SortCut／🗂 FileCompare／🗜 H265（選中的那段塗上那邊的顏色）."""
    def __init__(self, on_mode):
        super().__init__(); self.setObjectName('msw'); self.on_mode = on_mode; self.m = 'vs'; self.bs = {}
        h = QHBoxLayout(self); h.setContentsMargins(3, 3, 3, 3); h.setSpacing(2); self.h = h; self.lab = {}
        for k, ic, n, tip in (('vs', '🎬', 'VideoSift', '10 秒剪輯、分級'), ('fc', '🗂', 'FileCompare', '16 格分類整理'), ('h265', '🗜', 'H265', 'SSIM 轉檔瘦身')):
            b = QPushButton(f'{ic}\n{n}'); b.setCheckable(True); b.setToolTip(f'{n}：{tip}'); b.setCursor(Qt.PointingHandCursor); b.setMinimumHeight(40)
            b.clicked.connect(lambda _=False, k=k: self.on_mode(k)); h.addWidget(b, 1); self.bs[k] = b; self.lab[k] = (ic, n)
        self.set(self.m)

    def set(self, m):
        self.m = m
        for i, (k, b) in enumerate(self.bs.items()):
            ic, n = self.lab.get(k, ('', k))
            b.setText(f'{ic} {n}' if k == m else ic)                              # V0.5.78 只顯示目前那一段的名字（其他只留圖示，滑過去看名字）
            try: self.h.setStretch(i, 4 if k == m else 1)
            except Exception: pass
            b.setChecked(k == m); c = MODE_COL[k]
            b.setStyleSheet(f'QPushButton{{border:0;border-radius:9px;padding:3px 2px;font-size:10.5px;font-weight:700;background:{c if k == m else "transparent"};'
                            f'color:{"#0b1018" if k == m else "palette(text)"}}}QPushButton:hover{{background:{c if k == m else "rgba(127,140,160,0.18)"}}}')
        self.setStyleSheet('QFrame#msw{background:rgba(127,140,160,0.14);border:1px solid rgba(127,140,160,0.30);border-radius:12px}')


class LvBadge(QWidget):
    """V0.5.71 右上角小小的 Lv 1～10：10 格小長條＋數字（紅＝讓路給 TikLive 中，綠＝全速）。點一下看為什麼、改設定."""
    clicked = Signal()

    def __init__(self):
        super().__init__(); self.v = {'level': 10, 'col': '#2ecc71', 'why': '', 'on': True}; self.setFixedSize(92, 26); self.setCursor(Qt.PointingHandCursor)

    def set(self, v):
        if not isinstance(v, dict): return
        old = (self.v.get('level'), self.v.get('on'), self.v.get('tk'), bool(self.v.get('alert'))); self.v = v
        tip = [f"🤝 讓路等級 Lv {v.get('level')}／10（1＝最讓路，10＝最快）", str(v.get('why') or '')]
        if v.get('tk'): tip.append('TikLive：' + ('已連上（' + str(v.get('tk_ver') or '') + '）' if v.get('tk_link') else '有在跑（還沒更新到 1.0.84，用量測的）'))
        else: tip.append('這台沒有看到 TikLive')
        if not v.get('on'): tip = ['🧠 智能調速：關掉了（點一下打開）']
        if v.get('alert'): tip.insert(0, '⚡ TikLive 斷電警報：' + str((v['alert'] or {}).get('msg') or ''))
        tip.append('點一下看詳細、改設定'); self.setToolTip('\n'.join(tip))
        if old != (v.get('level'), v.get('on'), v.get('tk'), bool(v.get('alert'))): self.update()

    def mousePressEvent(self, e): self.clicked.emit()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); lv = int(self.v.get('level') or 10); on = self.v.get('on', True)
        c = QColor(str(self.v.get('col') or '#2ecc71')) if on else QColor('#7f8a99'); W, H = self.width(), self.height()
        bgp = QPainterPath(); bgp.addRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), 13, 13); p.fillPath(bgp, QColor(127, 140, 160, 36))
        p.setPen(QPen(QColor(c.red(), c.green(), c.blue(), 150), 1)); p.drawPath(bgp)
        x0 = 9; bw = 3; gap = 1.6
        for i in range(10):
            h = 5 + i * 1.2; r = QRectF(x0 + i * (bw + gap), H - 6 - h, bw, h); pp = QPainterPath(); pp.addRoundedRect(r, 1.2, 1.2)
            p.fillPath(pp, c if (i < lv and on) else QColor(127, 140, 160, 70))
        f = p.font(); f.setBold(True); f.setPixelSize(12); p.setFont(f); p.setPen(c if on else QColor('#7f8a99'))
        p.drawText(QRectF(x0 + 10 * (bw + gap) + 3, 0, W - (x0 + 10 * (bw + gap) + 3) - 6, H), Qt.AlignVCenter | Qt.AlignLeft, (('⚡' if self.v.get('alert') else '') + f'Lv{lv}') if on else 'OFF'); p.end()


class YieldDlg(QDialog):
    """V0.5.71 🤝 讓路給 TikLive：現在幾級、為什麼、TikLive／這邊各用了多少；開關、最高等級、NVENC 上限."""
    def __init__(self, win):
        super().__init__(win); self.setWindowTitle('🤝 讓路／🧠 智能調速'); self.resize(560, 560); v = QVBoxLayout(self)
        self.top = QLabel(); self.top.setWordWrap(True); self.top.setTextFormat(Qt.RichText); v.addWidget(self.top)
        self.tb = QTextBrowser(); v.addWidget(self.tb, 1)
        f = QFormLayout(); v.addLayout(f)
        self.c_on = QCheckBox('🧠 智能調速：看 CPU／顯示卡／溫度自己調（建議一直開著）'); self.c_on.setChecked(ENG.cfg.get('yield_on') is not False); f.addRow(self.c_on)
        self.c_tk = QCheckBox('🤝 讓路給 TikLive（這台有跑 TikLive 才勾；另一台取消勾選，上面的調速、%、控溫照樣有）'); self.c_tk.setChecked(ENG.cfg.get('yield_tk') is not False); f.addRow(self.c_tk)
        self.s_max = QSpinBox(); self.s_max.setRange(1, 10); self.s_max.setValue(int(ENG.cfg.get('yield_max') or 10)); self.s_max.setSuffix(' 級'); f.addRow('最高到 Lv', self.s_max)
        self.s_nv = QSpinBox(); self.s_nv.setRange(2, 16); self.s_nv.setValue(int(ENG.cfg.get('nvenc_limit') or 8)); self.s_nv.setSuffix(' 條'); f.addRow('顯示卡 NVENC 最多幾條（整台）', self.s_nv)
        V0 = __import__('vs_yield').view()                                          # V0.5.79 🌡 控溫
        self.c_th = QCheckBox('🌡 控溫（主機板會過熱斷電）：整台 CPU 壓在下面的預算內，這邊只用剩下的；後台同時只做 1 個（會比較慢）'); self.c_th.setChecked(bool(V0.get('th_on'))); f.addRow(self.c_th)
        self.s_thc = QSpinBox(); self.s_thc.setRange(15, 95); self.s_thc.setValue(int(V0.get('th_cpu') or 45)); self.s_thc.setSuffix(' %'); f.addRow('　整台電腦 CPU 預算（TikLive＋這邊）', self.s_thc)
        self.s_thv = QSpinBox(); self.s_thv.setRange(2, 60); self.s_thv.setValue(int(V0.get('th_vs') or 15)); self.s_thv.setSuffix(' %'); f.addRow('　這邊最多用（整台的）', self.s_thv)
        self.s_thg = QSpinBox(); self.s_thg.setRange(50, 95); self.s_thg.setValue(int(V0.get('th_gpu') or 75)); self.s_thg.setSuffix(' °C'); f.addRow('　顯示卡超過幾度轉檔先停', self.s_thg)
        self.s_sp = QSpinBox(); self.s_sp.setRange(0, 60); self.s_sp.setValue(int(ENG.cfg.get('heat_spare') or 10)); self.s_sp.setSuffix(' %'); f.addRow('　轉檔要電腦有空：留給這邊的 CPU 連續 1 分鐘 ≥', self.s_sp)   # V0.5.81
        self.s_rmn = QSpinBox(); self.s_rmn.setRange(0, 60); self.s_rmn.setValue(int(ENG.cfg.get('heat_rest_min') or 2)); self.s_rmn.setSuffix(' 分'); f.addRow('　轉完一部最少休息', self.s_rmn)
        self.s_rmx = QSpinBox(); self.s_rmx.setRange(2, 120); self.s_rmx.setValue(int(ENG.cfg.get('heat_rest_max') or 30)); self.s_rmx.setSuffix(' 分'); f.addRow('　最多休息（學到的時間超過也只休息這麼久）', self.s_rmx)
        self.cb_bd = QComboBox(); self.cb_bd.addItem('自動（名稱有 VRM／MOS／PCH 的）', 'auto'); self.cb_bd.addItem('不看主機板感測器', 'off')
        for k_ in sorted(((V0.get('heat') or {}).get('sens') or {}).keys()): self.cb_bd.addItem(k_, k_)
        i_ = self.cb_bd.findData(str(ENG.cfg.get('heat_board') or 'auto')); self.cb_bd.setCurrentIndex(max(0, i_)); f.addRow('　主機板感測器（供電 IC）', self.cb_bd)
        self.s_bmx = QSpinBox(); self.s_bmx.setRange(50, 120); self.s_bmx.setValue(int(ENG.cfg.get('heat_board_max') or 85)); self.s_bmx.setSuffix(' °C'); f.addRow('　主機板感測器上限', self.s_bmx)
        self.s_cmx = QSpinBox(); self.s_cmx.setRange(50, 100); self.s_cmx.setValue(int(ENG.cfg.get('heat_cpu') or 80)); self.s_cmx.setSuffix(' °C'); f.addRow('　CPU 溫度上限', self.s_cmx)
        self.c_hs = QCheckBox('🤝 跟別的程式握手（FusionStitch）：誰需要 CPU 就讓誰先跑'); self.c_hs.setChecked(ENG.cfg.get('hs_on') is not False); f.addRow(self.c_hs)   # V0.6.10
        self.s_hp = QSpinBox(); self.s_hp.setRange(0, 10); self.s_hp.setValue(int(ENG.cfg.get('hs_prio') if ENG.cfg.get('hs_prio') is not None else 5))
        self.s_hp.setToolTip('兩邊都在做重工作時：數字大的先跑；一樣（都是 5）＝平分。使用者在等的那邊永遠先'); f.addRow('　這邊的優先（5＝一樣，大的先）', self.s_hp)
        hb = QHBoxLayout(); self.b_hb = QPushButton('⏩ 這邊先跑 1 小時'); self.b_hc = QPushButton('取消'); hb.addWidget(self.b_hb); hb.addWidget(self.b_hc); hb.addStretch(1); f.addRow('　', hb)
        self.b_hb.clicked.connect(lambda: (ENG.cfg.set('hs_boost_until', time.time() + 3600), ENG.log.w('🤝 握手：使用者按了「這邊先跑 1 小時」'), self.load()))
        self.b_hc.clicked.connect(lambda: (ENG.cfg.set('hs_boost_until', 0), self.load()))
        try: P_ = __import__('vs_yield')._hs_pol(); P_['members']                                                         # V0.6.17 三個程式共用的設定（policy3.json）
        except Exception: P_ = {'members': {}}
        mb = QHBoxLayout(); self.c_mfs = QCheckBox('FusionStitch'); self.c_mcr = QCheckBox('ComfyRemote'); self.c_mtk = QCheckBox('TikLive')
        self.c_mfs.setChecked(P_['members'].get('FusionStitch', True) is not False); self.c_mcr.setChecked(P_['members'].get('ComfyRemote', True) is not False)
        self.c_mtk.setChecked(ENG.cfg.get('yield_tk') is not False)
        self.c_comfy = QCheckBox('🎨 自動看 ComfyUI'); self.c_comfy.setToolTip('問本機 ComfyUI（8188／8000）的佇列：在跑就讓它先，5 分鐘沒進度就不讓'); self.c_comfy.setChecked(ENG.cfg.get('hs_comfy') is not False)
        self.c_comfy.toggled.connect(lambda on: ENG.cfg.set('hs_comfy', bool(on)))
        for w_ in (self.c_mtk, self.c_mfs, self.c_mcr, self.c_comfy): mb.addWidget(w_)
        mb.addStretch(1); f.addRow('　☑ 這台有誰', mb)
        self.s_res = QSpinBox(); self.s_res.setRange(0, 50); self.s_res.setSuffix(' %'); self.s_res.setValue(int(P_.get('reserve3', 10))); self.s_res.setToolTip('永遠留給你隨時操作電腦（三個程式合起來最多用 100 − 這個 %）')
        self.s_fc = QSpinBox(); self.s_fc.setRange(10, 95); self.s_fc.setSuffix(' %'); self.s_fc.setValue(int(P_.get('first_cap', 80)))
        self.s_yc = QSpinBox(); self.s_yc.setRange(1, 30); self.s_yc.setSuffix(' %'); self.s_yc.setValue(int(P_.get('yield_cap', 5)))
        self.s_sh = QSpinBox(); self.s_sh.setRange(10, 90); self.s_sh.setSuffix(' %'); self.s_sh.setValue(int(P_.get('share_sc', 50)))
        self.s_sh.setToolTip('兩個都在轉檔時：SortCut 佔幾 %（剩下給 FusionStitch），再乘上 100 − 留給你的 %')
        rr = QHBoxLayout()
        for lb_, w_ in (('留給你', self.s_res), ('ComfyRemote 優先時拿', self.s_fc), ('其他降到', self.s_yc), ('平常 SortCut 佔', self.s_sh)): rr.addWidget(QLabel(lb_)); rr.addWidget(w_)
        rr.addStretch(1); f.addRow('　⚖ 分配', rr)
        self.cb_bd.currentIndexChanged.connect(self._save)
        for w_ in (self.c_mfs, self.c_mcr, self.c_mtk): w_.toggled.connect(self._save_pol)          # V0.6.15 只有動到這幾個才改共用設定（不會蓋掉另外兩個程式剛改的）
        for w_ in (self.s_res, self.s_fc, self.s_yc, self.s_sh): w_.valueChanged.connect(self._save_pol)
        for w_ in (self.c_on, self.c_tk, self.c_hs, self.s_hp, self.s_max, self.s_nv, self.c_th, self.s_thc, self.s_thv, self.s_thg, self.s_sp, self.s_rmn, self.s_rmx, self.s_bmx, self.s_cmx):
            (w_.toggled if isinstance(w_, QCheckBox) else w_.valueChanged).connect(self._save)
        b = QPushButton('關閉'); b.clicked.connect(self.accept); v.addWidget(b)
        self.t = QTimer(self); self.t.timeout.connect(self.load); self.t.start(2000); self.load()

    def _save_pol(self, *_a):
        """V0.6.15 三個程式共用的設定（存在 AppHandshake\\policy.json，三邊一起變）."""
        try:
            import vs_yield as VY_
            if self.c_mtk.isChecked() != (ENG.cfg.get('yield_tk') is not False): ENG.cfg.set('yield_tk', bool(self.c_mtk.isChecked())); self.c_tk.setChecked(self.c_mtk.isChecked())
            pk = VY_.hs_set_pol(members={'FusionStitch': self.c_mfs.isChecked(), 'ComfyRemote': self.c_mcr.isChecked(), 'TikLive': self.c_mtk.isChecked()}, reserve3=int(self.s_res.value()),
                                first_cap=int(self.s_fc.value()), yield_cap=int(self.s_yc.value()), share_sc=int(self.s_sh.value()))
            ENG.log.w(f'🤝 握手共用設定：{pk}')
        except Exception: ENG.log.err('🤝 握手共用設定')

    def _save(self, *_):
        ENG.cfg.set('yield_on', bool(self.c_on.isChecked())); ENG.cfg.set('yield_tk', bool(self.c_tk.isChecked())); ENG.cfg.set('yield_max', int(self.s_max.value())); ENG.cfg.set('nvenc_limit', int(self.s_nv.value()))
        for k_, w_ in (('heat_spare', self.s_sp), ('heat_rest_min', self.s_rmn), ('heat_rest_max', self.s_rmx), ('heat_board_max', self.s_bmx), ('heat_cpu', self.s_cmx)): ENG.cfg.set(k_, int(w_.value()))
        ENG.cfg.set('heat_board', str(self.cb_bd.currentData() or 'auto'))
        ENG.cfg.set('hs_on', bool(self.c_hs.isChecked())); ENG.cfg.set('hs_prio', int(self.s_hp.value()))
        ENG.cfg.set('thermal_on', bool(self.c_th.isChecked())); ENG.cfg.set('thermal_cpu', int(self.s_thc.value())); ENG.cfg.set('thermal_vs_max', int(self.s_thv.value())); ENG.cfg.set('thermal_gpu', int(self.s_thg.value()))
        ENG.log.w(f'🤝 讓路設定：智能調速{"開" if self.c_on.isChecked() else "關"}、TikLive {"讓" if self.c_tk.isChecked() else "不讓"}、最高 Lv {self.s_max.value()}、NVENC {self.s_nv.value()} 條')

    def load(self):
        try:
            import vs_yield; V = vs_yield.view()
        except Exception as ex: self.top.setText(f'讀不到：{ex}'); return
        c = V.get('col') or '#2ecc71'
        self.top.setText(f"<span style='font-size:26px;font-weight:800;color:{c}'>Lv {V.get('level')}</span>　<b>／10</b>　"
                         f"<span style='color:#8994a4'>目標 Lv {V.get('target', '—')}・FFmpeg 每秒跑 {round(float(V.get('duty') or 1) * 100)}%</span><br>{V.get('why') or ''}"
                         + (lambda c_: f"<br><span style='color:#8994a4'>CPU 用{c_.get('src') or '—'}量" + (f"（舊算法是 {float(c_['old']):.0f}%，只給你對照）" if c_.get('old') is not None and c_.get('src') != 'GetSystemTimes' else '') + '</span>')(V.get('cpu_src') or {}))
        U = V.get('use') or {}; N = {'cpu': 'CPU', 'gpu': '顯示卡', 'enc': '顯示卡編碼（NVENC）', 'dec': '顯示卡解碼', 'vram': '顯示卡記憶體'}
        fm = lambda x: '—' if x is None else f'{x:.0f}%'
        TKC = bool(V.get('tk'))                                                   # V0.6.18 這台真的有看到 TikLive 才寫 TikLive（不然會誤會）
        rows = ''.join(f"<tr><td>{N[k]}</td><td align=right>{fm((U.get(k) or {}).get('all'))}</td>" + (f"<td align=right>{fm((U.get(k) or {}).get('tk'))}</td>" if TKC else '') +
                       f"<td align=right>{fm((U.get(k) or {}).get('vs'))}</td><td align=right>{(V.get('L') or {}).get(k, '—')}</td></tr>" for k in N)
        tk = ('✅ TikLive 已連上（' + str(V.get('tk_ver') or '') + f"）：錄影 {V.get('tk_rec') or 0} 間、轉檔 {V.get('tk_conv') or 0}、字幕 {'跑' if V.get('tk_stt') else '沒跑'}") if V.get('tk_link') else (
            '🟡 TikLive 有在跑，但還沒更新到 TK_V1.0.84：用量測的（量得到它整串程式用多少，只是不知道它「等一下要開始做什麼」）' if V.get('tk') else '⚪ 這台沒有看到 TikLive')
        H_ = V.get('hs') or {}; P_ = H_.get('peers') or []; W_ = ['閒著', '背景小工作', '在做重工作', '使用者在等']
        M_ = {'lead': '⚡ 這邊優先', 'yield': '🤝 讓別人先跑', 'split': '⚖ 照比例分', 'alone': '⚪ 各跑各的'}
        tk += ('<br>' + '<br>'.join(f"🔗 <b>{esc_html(p.get('name') or p.get('app'))}</b> V{esc_html(p.get('ver') or '')}：{W_[int(p.get('want') or 0)]}" + (f"（{esc_html(p.get('what'))}）" if p.get('what') else '') + f"・優先 {p.get('prio', 5)}" for p in P_)
               if P_ else '<br>⚪ 沒有看到 FusionStitch／ComfyRemote（更新到有握手的版本、而且開著，就會出現）')
        if H_.get('alloc'): tk += '<br>現在分配：' + '・'.join(f"<b>{esc_html(a)}</b> {c}%" for a, c in H_['alloc'].items()) + (f"（這邊重工作最多 {H_['cpu_cap']}%）" if H_.get('cpu_cap') is not None else '') + f"・規則第 {H_.get('rules') or '?'} 版"
        if H_.get('mode'): tk += f"<br><b>{M_.get(H_['mode'], H_['mode'])}</b>" + (f"：{esc_html(H_.get('why'))}" if H_.get('why') else '') + (f"・這邊先跑還剩 {-(-int(H_['boost']) // 60)} 分" if H_.get('boost') else '')
        h = (f"<p>{tk}</p><table cellspacing=0 cellpadding=3 width=100%><tr><th align=left>項目</th><th align=right>整台</th>{'<th align=right>TikLive</th>' if TKC else ''}<th align=right>這邊</th><th align=right>這項允許 Lv</th></tr>{rows}"
             f"<tr><td>RAM</td><td align=right>{fm(V.get('ram'))}</td>{'<td></td>' if TKC else ''}<td></td><td align=right>{(V.get('L') or {}).get('ram', '—')}</td></tr>"
             f"<tr><td>NVENC 條數</td><td align=right>{V.get('nvenc') if V.get('nvenc') is not None else '—'}／{V.get('nvenc_limit')}</td>{'<td></td>' if TKC else ''}<td></td><td align=right>{(V.get('L') or {}).get('nvenc', '—')}</td></tr></table>"
             f"<p style='color:#8994a4'>Lv 是「每一項允許的等級」裡最小的那個。降：馬上；升：每 8 秒最多 +1、剛降過 20 秒內不升。"
             + (f"Lv 10 也不會吃滿：整台加起來 CPU ≤85%、顯示卡 ≤80%、NVENC ≤75%，而且 TikLive 最近 10 分鐘的高峰先空一半給它（現在保留：{', '.join(f'{N.get(k, k)} {x}%' for k, x in (V.get('R') or {}).items() if x) or '沒有'}）。" if TKC else
                "這台沒有 TikLive：沒人在用電腦（3 分鐘沒碰鍵盤滑鼠）就全力跑到 99%；有人在用就留 10% 給你。") +
             f"Lv 2 以下轉檔／瘦身先不開新的（跑到一半的照跑完）；同時做幾個也跟著等級。</p>")
        T = V.get('th') or {}; A_ = V.get('alert')
        if A_: h = (f"<p style='color:#e5484d'><b>⚡ TikLive 斷電警報（24 小時內斷電 {A_.get('n24', '?')} 次）</b>：{A_.get('msg', '')}<br>"
                    f"這邊照做：{'轉檔／瘦身不開新的、' if True else ''}Lv 1、CPU 上限 2%、同時只做 1 個，到 {time.strftime('%m-%d %H:%M', time.localtime(float(A_.get('until') or 0)))}。要提早解除：到 TikLive 按「解除警報」。</p>") + h
        h += (f"<p>🌡 <b>控溫{'開著' if V.get('th_on') else '關著'}</b>" + (f"：這邊現在最多用整台 CPU 的 <b>{T.get('cap', '—')}%</b>（預算 {T.get('budget', '—')}% − 其他程式 {T.get('others', '—')}%）"
              f"・顯示卡 {V.get('gpu_temp') if V.get('gpu_temp') is not None else '—'}°C" if V.get('th_on') else '') + (f"<br><span style='color:#e5484d'>{T.get('err')}</span>" if T.get('err') else '') + '</p>')
        HV = V.get('heat') or {}
        if HV and V.get('th_on'):
            st_ = HV.get('stats') or {}; ss = HV.get('sess')
            h += (f"<p><b>🌡 轉檔看溫度</b>：{HV.get('why') or '—'}"
                  + (f"<br>正在轉：{ss['mins']} 分鐘，{ss['sensor']} {ss['t0'] or 0:.0f}°C → 最高 {ss['peak'] or 0:.0f}°C" if ss else '')
                  + (f"<br>學到的（最近 {st_['n']} 部平均）：轉一部升 {st_.get('rise')}°C、轉 {st_.get('mins')} 分鐘、轉完 {st_.get('cool')} 分鐘降回來" if st_.get('n') else '<br>還沒學到（轉完第一部就有）')
                  + ('<br>溫度：' + '、'.join(f'{k.split("｜")[-1]} {v:.0f}°C' for k, v in list((HV.get('sens') or {}).items())[:12]) if HV.get('sens') else f"<br><span style='color:#8994a4'>{HV.get('sens_err') or ''}</span>")
                  + ('<br>' + '<br>'.join(HV.get('log') or []) if HV.get('log') else '') + '</p>')
        if V.get('log'): h += '<p><b>最近變化</b><br>' + '<br>'.join(V['log']) + '</p>'
        if V.get('err'): h += f"<p style='color:#e5484d'>{V['err']}</p>"
        self.tb.setHtml(h)


class DzClick(QFrame):
    """點一下會跳頁的 KPI 卡."""
    go = None

    def mousePressEvent(self, e):
        try:
            if self.go is not None and e.button() == Qt.LeftButton: self.go()
        except Exception: ENG.log.err('📊 總覽卡片')


class DonutW(QWidget):
    def __init__(self):
        super().__init__(); self.segs = []; self.big = ''; self.lab = ''; self.setMinimumSize(150, 150); self.setMouseTracking(True)

    def set(self, segs, big, lab, fmt=None): self.segs = [s for s in segs if (s[1] or 0) > 0]; self.big = big; self.lab = lab; self.fmt = fmt; self.update()

    def _geo(self):
        d = min(self.width(), self.height()) - 8; return QRectF((self.width() - d) / 2, (self.height() - d) / 2, d, d), d

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); r, d = self._geo(); w = max(10.0, d * 0.13); rr = r.adjusted(w / 2, w / 2, -w / 2, -w / 2)
        p.setPen(QPen(QColor(127, 140, 160, 40), w)); p.drawEllipse(rr)
        tot = sum(float(s[1] or 0) for s in self.segs) or 1; a = 90.0
        for n, v, c, *_x in self.segs:
            span = float(v) / tot * 360.0; g = min(1.6, span / 3) if len(self.segs) > 1 else 0
            pen = QPen(QColor(c), w); pen.setCapStyle(Qt.FlatCap); p.setPen(pen); p.drawArc(rr, int((a - g / 2) * 16), int(-(span - g) * 16)); a -= span
        p.setPen(self.palette().color(self.foregroundRole())); f = p.font(); f.setPointSizeF(max(10, d * 0.11)); f.setBold(True); p.setFont(f)
        p.drawText(QRectF(r.x(), r.y() + d * 0.36, d, d * 0.18), Qt.AlignCenter, self.big)
        f.setPointSizeF(max(7, d * 0.05)); f.setBold(False); p.setFont(f); p.drawText(QRectF(r.x(), r.y() + d * 0.55, d, d * 0.1), Qt.AlignCenter, self.lab); p.end()

    def mouseMoveEvent(self, e):
        import math
        r, d = self._geo(); cx, cy = r.center().x(), r.center().y(); x, y = e.position().x() - cx, cy - e.position().y()
        if math.hypot(x, y) > d / 2 or math.hypot(x, y) < d / 2 * 0.7: QToolTip.hideText(); return
        ang = (90 - math.degrees(math.atan2(y, x))) % 360; tot = sum(float(s[1] or 0) for s in self.segs) or 1; a = 0
        for n, v, c, *x_ in self.segs:
            a += float(v) / tot * 360
            if ang <= a: QToolTip.showText(e.globalPosition().toPoint(), f'{n}：{(getattr(self, "fmt", None) or (lambda z: f"{z:,.0f}"))(v)}（{_dzp(float(v), tot)}%）' + (f'　{x_[0]}' if x_ and x_[0] else ''), self); return


class Day7W(QWidget):
    def __init__(self):
        super().__init__(); self.d = []; self.c = DZC[2]; self.fmt = None; self.setMinimumHeight(120)

    def set(self, d, c, fmt=None): self.d = d or []; self.c = c; self.fmt = fmt; self.update()

    def paintEvent(self, e):
        if not self.d: return
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); W, H = self.width(), self.height(); n = len(self.d); bw = W / n
        mx = max([float(x[1] or 0) for x in self.d] + [1]); fg = self.palette().color(self.foregroundRole())
        f = p.font(); f.setPointSizeF(8); p.setFont(f)
        for i, (lab, v) in enumerate(self.d):
            v = float(v or 0); h = max(2.0, v / mx * (H - 34)); x = i * bw + bw * 0.2; w = min(bw * 0.6, 34); x = i * bw + (bw - w) / 2
            path = QPainterPath(); path.addRoundedRect(QRectF(x, H - 16 - h, w, h + 3), 4, 4); p.fillPath(path, QColor(self.c))
            p.setPen(fg)
            if v: p.drawText(QRectF(i * bw, H - 32 - h, bw, 14), Qt.AlignCenter, self.fmt(v) if self.fmt else f'{v:,.0f}')
            p.drawText(QRectF(i * bw, H - 14, bw, 14), Qt.AlignCenter, '今天' if i == n - 1 else str(lab))
        p.end()


class BarRow(QWidget):
    def __init__(self, name, val, pct, col, tip=''):
        super().__init__(); v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(2); h = QHBoxLayout(); h.setSpacing(6)
        a = QLabel(str(name)); a.setMinimumWidth(10); b = QLabel(str(val)); b.setStyleSheet('font-weight:700'); h.addWidget(a, 1); h.addWidget(b); v.addLayout(h)
        self.pct = max(0.0, min(100.0, float(pct or 0))); self.col = col; self.setToolTip(tip); self.setMinimumHeight(30)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); y = self.height() - 8; W = self.width()
        bgp = QPainterPath(); bgp.addRoundedRect(QRectF(0, y, W, 7), 3.5, 3.5); p.fillPath(bgp, QColor(127, 140, 160, 46))
        if self.pct > 0: fp = QPainterPath(); fp.addRoundedRect(QRectF(0, y, W * self.pct / 100, 7), 3.5, 3.5); p.fillPath(fp, QColor(self.col))
        p.end()


class TreeMap(QWidget):
    """🗺 方塊圖（像 TreeSize／WinDirStat）：面積＝大小；點一下進去、右鍵＝選單."""
    COLS = ['#3987e5', '#45b5d4', '#3fb37f', '#b9a43c', '#e09a3e', '#e5735f', '#9d7be0', '#e06fa5', '#5d8fc9', '#58a39a']

    def __init__(self, page):
        super().__init__(); self.page = page; self.items = []; self.rects = []; self.hot = -1
        self.setMinimumHeight(220); self.setMouseTracking(True)

    def set_items(self, items):
        self.items = [x for x in items if x.get('size', 0) > 0][:60]; self.hot = -1; self._lay(); self.update()

    def resizeEvent(self, e): self._lay(); super().resizeEvent(e)

    def _lay(self):
        W, H = max(1, self.width()), max(1, self.height()); tot = float(sum(x['size'] for x in self.items)) or 1.0
        vals = [x['size'] / tot * W * H for x in self.items]; out = []
        def worst(row, w):
            s = sum(row); return max(max(w * w * r / (s * s), (s * s) / (w * w * r)) for r in row) if row and s > 0 and w > 0 else 1e9
        x, y, w, h = 0.0, 0.0, float(W), float(H); i = 0
        while i < len(vals):
            side = min(w, h); row = [vals[i]]; j = i + 1
            while j < len(vals) and worst(row + [vals[j]], side) <= worst(row, side): row.append(vals[j]); j += 1
            s = sum(row)
            if w >= h:
                cw = s / h if h else 0; yy = y
                for r in row: rh = r / cw if cw else 0; out.append(QRectF(x, yy, cw, rh)); yy += rh
                x += cw; w -= cw
            else:
                rh = s / w if w else 0; xx = x
                for r in row: cw = r / rh if rh else 0; out.append(QRectF(xx, y, cw, rh)); xx += cw
                y += rh; h -= rh
            i = j
        self.rects = out

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        if not self.items:
            p.setPen(QColor('#8994a4')); p.drawText(self.rect(), Qt.AlignCenter, '這裡沒有子資料夾'); return
        tot = float(sum(x['size'] for x in self.items)) or 1.0
        for k, (r, it) in enumerate(zip(self.rects, self.items)):
            rr = r.adjusted(1, 1, -1, -1)
            if rr.width() < 1 or rr.height() < 1: continue
            c = QColor(self.COLS[k % len(self.COLS)])
            if k == self.hot: c = c.lighter(125)
            path = QPainterPath(); path.addRoundedRect(rr, 4, 4); p.fillPath(path, c)
            sv = float(it.get('conv_b') or 0) / max(1, it['size'])                       # 下面那條綠的＝能轉 H.265 的部分
            if sv > 0.01 and rr.height() > 14:
                p.fillRect(QRectF(rr.left() + 3, rr.bottom() - 5, (rr.width() - 6) * min(1.0, sv), 3), QColor('#7CFC9A'))
            if rr.width() > 46 and rr.height() > 22:
                p.setPen(QColor('#ffffff')); f = p.font(); f.setBold(True); f.setPointSizeF(9.5); p.setFont(f)
                t = QRectF(rr.left() + 6, rr.top() + 4, rr.width() - 10, rr.height() - 8)
                fm = QFontMetrics(f); nm = fm.elidedText(it['name'], Qt.ElideRight, int(t.width()))
                p.drawText(t, Qt.AlignLeft | Qt.AlignTop, nm)
                if rr.height() > 40:
                    f.setBold(False); f.setPointSizeF(8.5); p.setFont(f)
                    p.drawText(t.adjusted(0, 16, 0, 0), Qt.AlignLeft | Qt.AlignTop, f"{core.fmt_b(it['size'])}・{it['size'] / tot * 100:.0f}%")

    def _at(self, pos):
        for k, r in enumerate(self.rects):
            if r.contains(QPointF(pos)): return k
        return -1

    def mouseMoveEvent(self, e):
        k = self._at(e.position().toPoint() if hasattr(e, 'position') else e.pos())
        if k != self.hot:
            self.hot = k; self.update()
            if 0 <= k < len(self.items):
                it = self.items[k]; QToolTip.showText(e.globalPosition().toPoint() if hasattr(e, 'globalPosition') else e.globalPos(),
                    f"📁 {it['path']}\n{core.fmt_b(it['size'])}・{it['n']:,} 個檔" + (f"\n能轉 {it.get('conv_n', 0):,} 部，預估省 {core.fmt_b(it.get('save', 0))}" if it.get('conv_n') else ''), self)

    def leaveEvent(self, e): self.hot = -1; self.update()

    def mouseReleaseEvent(self, e):
        k = self._at(e.position().toPoint() if hasattr(e, 'position') else e.pos())
        if not (0 <= k < len(self.items)): return
        if e.button() == Qt.RightButton: self.page.menu_for(self.items[k], self.mapToGlobal(e.position().toPoint() if hasattr(e, 'position') else e.pos()))
        elif e.button() == Qt.LeftButton: self.page.go(self.items[k]['path'])


class ExplorePage(QWidget):
    """V0.6.19 🗺 檔案總覽：像 Everything 搜尋檔名、像 TreeSize 一層一層看哪個資料夾最大、能轉幾部、預估省多少；右鍵資料夾 → 轉檔."""
    SORTS = [('size', '大小'), ('n', '檔案數'), ('save', '可省最多'), ('name', '名稱')]

    def __init__(self, win):
        super().__init__(); self.win = win; self.prefix = str(ENG.cfg.get('ex_prefix') or ''); self.sort = str(ENG.cfg.get('ex_sort') or 'size'); self._j = None; self._seq = 0
        v = QVBoxLayout(self); v.setContentsMargins(14, 10, 14, 10); v.setSpacing(8)
        top = QHBoxLayout(); self.q = QLineEdit(); self.q.setPlaceholderText('🔍 找檔案（像 Everything：空白分開；也可以 size:>1g  ext:mkv  codec:h264  dur:>30m  cv:no；在某個資料夾裡就只找那裡）'); self.q.setClearButtonEnabled(True)
        self._qt = QTimer(self); self._qt.setSingleShot(True); self._qt.timeout.connect(self.refresh); self.q.textChanged.connect(lambda _t: self._qt.start(300))
        top.addWidget(self.q, 1); self.cb = QComboBox()
        for k, n in self.SORTS: self.cb.addItem(n, k)
        self.cb.setCurrentIndex(max(0, [k for k, _ in self.SORTS].index(self.sort) if self.sort in [k for k, _ in self.SORTS] else 0))
        self.cb.currentIndexChanged.connect(self._sort); top.addWidget(QLabel('排序')); top.addWidget(self.cb)
        b = QPushButton('⟳'); b.setToolTip('重新讀'); b.clicked.connect(lambda: (ENG.__dict__.pop('_exp_cache', None), self.refresh())); top.addWidget(b); v.addLayout(top)
        ch = QHBoxLayout(); ch.setSpacing(4); self.chips = {}                       # V0.6.23 常用篩選一按就加進搜尋
        for t, n in (('size:>1g', '大於 1GB'), ('size:>10g', '大於 10GB'), ('codec:h264', 'H.264'), ('codec:hevc', 'H.265'), ('ext:mkv,avi,wmv,mov,ts', '非 MP4'), ('dur:>60m', '超過 1 小時'), ('cv:no', '還沒轉')):
            c = QPushButton(n); c.setObjectName('pill'); c.setCheckable(True); c.setToolTip(t); c.clicked.connect(lambda _c=False, t=t: self._chip(t)); ch.addWidget(c); self.chips[t] = c
        ch.addStretch(1); v.addLayout(ch)
        self.q.textChanged.connect(lambda t: [c.setChecked(k in t.split()) for k, c in self.chips.items()])
        nav = QHBoxLayout(); self.b_up = QPushButton('⬆ 上一層'); self.b_up.clicked.connect(self.up); nav.addWidget(self.b_up)
        self.crumb = QLabel(); self.crumb.setTextFormat(Qt.RichText); self.crumb.linkActivated.connect(lambda h: (setattr(self, "_no_auto", not h), self.go(h))); self.crumb.setWordWrap(True); nav.addWidget(self.crumb, 1); v.addLayout(nav)
        kp = QHBoxLayout(); self.k = {}
        for key, nm, col in (('size', '這裡總共', '#3987e5'), ('n', '檔案', '#8994a4'), ('conv_n', '能轉的', '#e09a3e'), ('save', '轉完預估省', '#3fb37f')):
            f = QFrame(); f.setObjectName('exk'); f.setStyleSheet(f'QFrame#exk{{background:rgba(127,140,160,0.08);border:1px solid rgba(127,140,160,0.28);border-top:3px solid {col};border-radius:12px}}')
            fv = QVBoxLayout(f); fv.setContentsMargins(12, 6, 12, 6); fv.setSpacing(0); a = QLabel(nm); a.setStyleSheet('font-size:11.5px;color:#8994a4'); fv.addWidget(a)
            bb = QLabel('—'); bb.setStyleSheet('font-size:22px;font-weight:800' + (';color:#3fb37f' if key == 'save' else '')); fv.addWidget(bb); self.k[key] = bb; kp.addWidget(f, 1)
        self.b_conv = QPushButton('🔁 轉檔這個資料夾'); self.b_conv.setMinimumHeight(44); self.b_conv.clicked.connect(lambda: self.menu_for({'path': self.prefix, 'name': self.prefix.rsplit('\\', 1)[-1] or self.prefix}, None))
        kp.addWidget(self.b_conv); v.addLayout(kp)
        sp = QSplitter(Qt.Vertical); self.tm = TreeMap(self); sp.addWidget(self.tm)
        self.tw = QTreeWidget(); self.tw.setRootIsDecorated(False); self.tw.setAlternatingRowColors(True); self.tw.setUniformRowHeights(True)
        self.tw.setContextMenuPolicy(Qt.CustomContextMenu); self.tw.customContextMenuRequested.connect(self._ctx); self.tw.itemDoubleClicked.connect(self._dbl)
        self.tw.setSelectionMode(QAbstractItemView.ExtendedSelection)               # V0.6.28 Ctrl／Shift 選好幾個資料夾
        self.tabs = QTabWidget(); self.tabs.addTab(self.tw, '📁 資料夾')
        self.tw_big = QTreeWidget(); self.tw_big.setRootIsDecorated(False); self.tw_big.setAlternatingRowColors(True); self.tw_big.setHeaderLabels(['檔名', '大小', '資料夾', '編碼'])
        self.tw_big.itemDoubleClicked.connect(self._dbl); self.tw_big.setContextMenuPolicy(Qt.CustomContextMenu); self.tw_big.customContextMenuRequested.connect(lambda pos: self._ctx(pos, self.tw_big))
        self.tabs.addTab(self.tw_big, '🐘 最大的 20 個檔')
        self.tw_hot = QTreeWidget(); self.tw_hot.setRootIsDecorated(False); self.tw_hot.setAlternatingRowColors(True); self.tw_hot.setHeaderLabels(['資料夾', '轉完預估省', '能轉', '大小', '位置'])
        self.tw_hot.itemDoubleClicked.connect(lambda it, _c: self.menu_for((it.data(0, Qt.UserRole) or ('', {}))[1], None))
        self.tw_hot.setContextMenuPolicy(Qt.CustomContextMenu); self.tw_hot.customContextMenuRequested.connect(lambda pos: self._ctx(pos, self.tw_hot))
        self.tabs.addTab(self.tw_hot, '💡 最值得轉的')
        self.mix = QLabel(); self.mix.setTextFormat(Qt.RichText); self.mix.setWordWrap(True); self.mix.setAlignment(Qt.AlignTop | Qt.AlignLeft); self.mix.setMargin(10)
        self.tabs.addTab(scroll_wrap(self.mix), '🎞 編碼／格式')
        sp.addWidget(self.tabs); sp.setStretchFactor(0, 2); sp.setStretchFactor(1, 3); v.addWidget(sp, 1)
        for ks, fn in (('Backspace', self.up), ('Alt+Up', self.up), ('F5', lambda: (ENG.__dict__.pop('_exp_cache', None), self.refresh())), ('Ctrl+F', lambda: (self.q.setFocus(), self.q.selectAll()))):   # V0.6.26 鍵盤
            sc = QShortcut(QKeySequence(ks), self); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(lambda fn=fn, bk=(ks == 'Backspace'): (None if (bk and self.q.hasFocus()) else fn()))
        self.tw.installEventFilter(self)
        self.hint = QLabel('點方塊或按兩下進去・右鍵（或手機長按）資料夾 → 🔁 轉檔／到檔案總管・方塊底下綠線＝能轉 H.265 的部分'); self.hint.setStyleSheet('color:#8994a4;font-size:11.5px'); v.addWidget(self.hint)

    def eventFilter(self, o, e):
        if o is self.tw and e.type() == QEvent.KeyPress and e.key() in (Qt.Key_Return, Qt.Key_Enter):
            it = self.tw.currentItem()
            if it is not None: self._dbl(it, 0); return True
        return super().eventFilter(o, e)

    def _chip(self, t):
        L = self.q.text().split(); L = [x for x in L if x != t] if t in L else L + [t]; self.q.setText(' '.join(L))

    def _sort(self, _i):
        self.sort = self.cb.currentData() or 'size'; ENG.cfg.set('ex_sort', self.sort); self.refresh()

    def go(self, path):
        self.prefix = str(path or ''); ENG.cfg.set('ex_prefix', self.prefix)
        if self.q.text(): self.q.blockSignals(True); self.q.clear(); self.q.blockSignals(False)
        self.refresh()

    def up(self):
        j = self._j or {}; p_ = j.get('parent', '') if self.prefix else ''; self._no_auto = not p_; self.go(p_)

    def _crumbs(self):
        if not self.prefix: return '<b>💽 全部影片庫</b>'
        parts = [x for x in self.prefix.split('\\') if x]; acc = ''; st = 'text-decoration:none;color:#aeb7c4'; h = f'<a href="" style="{st}">💽 全部</a>'
        for i, x in enumerate(parts):
            acc = acc + '\\' + x if i else x; last = i == len(parts) - 1
            h += f' <span style="color:#5d6978">›</span> <a href="{_html.escape(acc)}" style="{st}{";color:#4dc9ff;font-weight:700" if last else ""}">{_html.escape(x)}</a>'
        return f'<span style="font-size:14px">{h}</span>'

    def refresh(self):
        self._seq += 1; seq = self._seq; q = self.q.text().strip(); pf = self.prefix; so = self.sort
        self.crumb.setText(self._crumbs()); self.b_up.setEnabled(bool(pf))
        def get():
            if q: return ENG.explore_search(q, pf, 'name' if so == 'name' else 'size', 500)
            return ENG.explore(pf, so)
        bg(get, lambda j, seq=seq, q=q: seq == self._seq and self._show(j, q), lambda e: self.win.msg(f'🗺 讀不到：{e}'))

    def _show(self, j, q):
        if not j or not j.get('ok'): return
        self.tw.clear()
        if q:
            self._j = None; self.tm.setVisible(False); self.b_conv.setVisible(False); self.tabs.setCurrentIndex(0)
            self.tw.setHeaderLabels(['檔名', '大小', '資料夾', '格式']); R = j.get('rows') or []
            self.k['size'].setText(core.fmt_b(j.get('sum', 0))); self.k['n'].setText(f"{j.get('n', 0):,}{'+' if j.get('more') else ''}"); self.k['conv_n'].setText('—'); self.k['save'].setText('—')
            for r in R:
                it = QTreeWidgetItem([r['name'], core.fmt_b(r['size']), r['folder'], (r.get('vcodec') or '').upper() + ('・✔ 轉好' if r.get('cv') == 3 else '')])
                it.setData(0, Qt.UserRole, ('f', r)); it.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter); self.tw.addTopLevelItem(it)
            self.hint.setText(f"找到 {j.get('n', 0):,} 個{'（只列前 500 個，多打幾個字縮小）' if j.get('more') else ''}・按兩下到檔案總管看這部・右鍵＝在 Windows 檔案總管顯示")
            for c, w in ((0, 380), (1, 90), (2, 360)): self.tw.setColumnWidth(c, w)
            return
        self._j = j; I = j.get('items') or []; T = j.get('tot') or {}; H = j.get('here') or {}; tot = max(1, int(T.get('size') or 0))
        if not self.prefix and len(I) == 1 and not getattr(self, '_no_auto', False): self.go(I[0]['path']); return     # V0.6.42 只有一個影片庫：直接進去
        self.tm.setVisible(True); self.b_conv.setVisible(bool(self.prefix) and bool(T.get('conv_n')))
        self.b_conv.setText(f"🔁 轉檔這個資料夾\n預估省 {core.fmt_b(T.get('save', 0))}")
        self.k['size'].setText(core.fmt_b(T.get('size', 0))); self.k['n'].setText(f"{int(T.get('n') or 0):,}"); self.k['conv_n'].setText(f"{int(T.get('conv_n') or 0):,}"); self.k['save'].setText(core.fmt_b(T.get('save', 0)))
        self.tm.set_items(sorted(I, key=lambda x: -x['size']))
        self.tw.setHeaderLabels(['資料夾', '大小', '佔比', '檔案數', '能轉', '預估省'])
        for x in I:
            it = QTreeWidgetItem([f"📁 {x['name']}", core.fmt_b(x['size']), f"{x['size'] / tot * 100:.1f}%", f"{x['n']:,}", f"{x.get('conv_n', 0):,}" if x.get('conv_n') else '', core.fmt_b(x['save']) if x.get('save') else ''])
            it.setData(0, Qt.UserRole, ('d', x))
            for c in range(1, 6): it.setTextAlignment(c, Qt.AlignRight | Qt.AlignVCenter)
            if x.get('save'): it.setForeground(5, QColor('#3fb37f'))
            self.tw.addTopLevelItem(it)
        if H.get('n'):
            it = QTreeWidgetItem([f"📄 直接放在這一層的檔案", core.fmt_b(H.get('size', 0)), f"{H.get('size', 0) / tot * 100:.1f}%", f"{H['n']:,}", f"{H.get('conv_n', 0):,}" if H.get('conv_n') else '', core.fmt_b(H.get('save', 0)) if H.get('save') else ''])
            it.setData(0, Qt.UserRole, ('h', {'path': self.prefix, 'name': '這一層'})); it.setForeground(0, QColor('#8994a4'))
            for c in range(1, 6): it.setTextAlignment(c, Qt.AlignRight | Qt.AlignVCenter)
            self.tw.addTopLevelItem(it)
        for c, w in ((0, 340), (1, 90), (2, 70), (3, 80), (4, 70), (5, 90)): self.tw.setColumnWidth(c, w)
        self.tw_big.clear()                                                      # V0.6.20 最大的 20 個檔、編碼／格式
        for r in j.get('big') or []:
            it = QTreeWidgetItem([r['name'], core.fmt_b(r['size']), r['folder'], (r.get('vcodec') or '').upper() + ('・✔ 轉好' if r.get('cv') == 3 else '')])
            it.setData(0, Qt.UserRole, ('f', r)); it.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter); self.tw_big.addTopLevelItem(it)
        for c, w in ((0, 380), (1, 90), (2, 380)): self.tw_big.setColumnWidth(c, w)
        self.tw_hot.clear()                                                      # V0.6.24 💡 最值得轉的資料夾（按兩下＝轉檔選單）
        for x in j.get('hot') or []:
            it = QTreeWidgetItem([f"📁 {x['name']}", core.fmt_b(x['save']), f"{x['conv_n']:,}", core.fmt_b(x['conv_b']), x['path']])
            it.setData(0, Qt.UserRole, ('d', x)); it.setForeground(1, QColor('#3fb37f'))
            for c in (1, 2, 3): it.setTextAlignment(c, Qt.AlignRight | Qt.AlignVCenter)
            self.tw_hot.addTopLevelItem(it)
        for c, w in ((0, 260), (1, 100), (2, 70), (3, 90)): self.tw_hot.setColumnWidth(c, w)
        def bars(L, lab):
            h = '<table width="100%" cellspacing="0" cellpadding="3">'
            for i, x in enumerate(L):
                pct = x['size'] / tot * 100; col = TreeMap.COLS[i % len(TreeMap.COLS)]
                h += (f'<tr><td width="120"><b>{_html.escape(lab(x))}</b></td><td width="55%"><table cellspacing="0" cellpadding="0" width="{max(1, int(pct))}%"><tr><td bgcolor="{col}" height="12"></td></tr></table></td>'
                      f'<td align="right">{core.fmt_b(x["size"])}</td><td align="right" style="color:#8994a4">{pct:.1f}%・{x["n"]:,} 個</td></tr>')
            return h + '</table>'
        C = j.get('codecs') or []; X = j.get('exts') or []
        self.mix.setText((f'<b>🎞 影片編碼</b> <span style="color:#8994a4">（H264 越多，轉 H.265 越能省）</span>{bars(C, lambda x: x["codec"].upper())}<br><b>📄 副檔名</b>{bars(X, lambda x: x["ext"])}' + (f'<br><b>📅 檔案年份（修改日期）</b>{bars(j.get("ages") or [], lambda x: x["year"])}' if j.get('ages') else '')) if C or X else '<span style="color:#8994a4">這裡沒有影片</span>')
        self.hint.setText('點方塊或按兩下進去・右鍵資料夾 → 🔁 轉檔（H.264→H.265 等，先算好能省多少）／到檔案總管・方塊底下綠線＝能轉的部分')

    def _dbl(self, it, _c):
        k, x = it.data(0, Qt.UserRole) or ('', {})
        if k == 'd': self.go(x['path'])
        elif k == 'h': self._to_browse(self.prefix)
        elif k == 'f': self.win.nav.setCurrentRow(0); self.win.browse.goto_file(int(x['id']))

    def _ctx(self, pos, tw=None):
        tw = tw or self.tw; it = tw.itemAt(pos)
        if it is None: return
        k, x = it.data(0, Qt.UserRole) or ('', {})
        g = tw.viewport().mapToGlobal(pos)
        sel = [(i.data(0, Qt.UserRole) or ('', {})) for i in tw.selectedItems()]
        ds = [v_['path'] for k_, v_ in sel if k_ in ('d', 'h') and v_.get('path')]
        if len(ds) > 1 and k in ('d', 'h'):                                      # V0.6.28 選好幾個資料夾一起轉
            self.menu_for({'paths': ds, 'name': f'{len(ds)} 個資料夾'}, g); return
        if k == 'f':
            m = QMenu(self); m.addAction('📂 在 Windows 檔案總管顯示', lambda: core.explorer_select(x.get('path') or ''))
            m.addAction('▦ 到 SortCut 檔案總管看這部', lambda: (self.win.nav.setCurrentRow(0), self.win.browse.goto_file(int(x['id']))))
            m.addAction('📋 複製路徑', lambda: QApplication.clipboard().setText(x.get('path') or '')); m.exec(g); return
        self.menu_for(x, g)

    def _to_browse(self, path):
        try: self.win.nav.setCurrentRow(0); self.win.browse.use_view({'name': f'🗺 {path}', 'folder': path, 'flt': 'all', 'sort': 'name', 'sub': True})
        except Exception: ENG.log.err('🗺 到檔案總管')

    def menu_for(self, x, gpos):
        """右鍵資料夾：先在背景算好三種轉檔各能省多少，再跳選單."""
        paths = [p_ for p_ in (x.get('paths') or [x.get('path') or '']) if p_]
        if not paths: return
        path = paths[0] if len(paths) == 1 else paths
        self.win.msg('🗺 計算能省多少…', 2000)
        K = [('h264', 'H.264 → H.265'), ('nonmp4', '非 MP4 → MP4（H.265）'), ('all', '兩種都要')]
        def get():
            out = []
            for k, _n in K:
                try: P = ENG.conv_plan(None, 0, 0, list(paths), 'size_desc', k, 0, 0)
                except Exception: P = {}
                out.append(P or {})
            return out
        def show(P):
            m = QMenu(self); m.setToolTipsVisible(True); t = m.addAction(f"🔁 轉檔「{x.get('name') or path}」"); t.setEnabled(False)
            for (k, n), p in zip(K, P):
                na = int(p.get('n_all') or 0); a = m.addAction(f"   {n}：{na:,} 部・預估省 {core.fmt_b(p.get('save_all') or 0)}", lambda k=k: self.to_conv(path, k)); a.setEnabled(na > 0)
            m.addAction('   ➕ 加到目前的轉檔範圍（不清掉原本的、種類不變）', lambda: self.to_conv(path, None, True))
            m.addSeparator()
            if len(paths) == 1:
                m.addAction('▦ 到 SortCut 檔案總管看這個資料夾', lambda: self._to_browse(paths[0]))
                m.addAction('📂 在 Windows 檔案總管打開', lambda: core.explorer_select(paths[0]))
            m.addAction('📋 複製路徑', lambda: QApplication.clipboard().setText('\n'.join(paths)))
            m.exec(gpos or QCursor.pos())
        bg(get, show)

    def to_conv(self, path, kind, add=False):
        try:
            self.win.nav.setCurrentRow(1); self.win.conv.use_folder(path, kind, add)
            nm = path if isinstance(path, str) else f'{len(path)} 個資料夾'
            self.win.msg(f'🔁 轉檔：已{"加入" if add else "帶入"}「{nm}」，種類＝{dict(CONV_KINDS).get(self.win.conv.kind, self.win.conv.kind)}；確認數量後按加入')
        except Exception: ENG.log.err('🗺 → 轉檔')


class DashPage(QWidget):
    """📊 一頁總覽（電腦版）：SortCut／FileCompare／H265 三種，資料從 vs_dash 一次算好（20 秒快取），這頁看得到時 15 秒更新一次."""
    def __init__(self, win):
        super().__init__(); self.win = win; self.kind = 'vs'; self.L = QGridLayout(self); self.L.setContentsMargins(14, 10, 14, 10); self.L.setSpacing(10)
        self.t = QTimer(self); self.t.timeout.connect(lambda: self.isVisible() and self.load()); self.t.start(15000)

    def show_kind(self, k): self.kind = k; self.load()

    def load(self):
        k = self.kind
        def get():
            import vs_dash as D
            F = sys.modules.get('fc_app'); FE = getattr(F, 'ENG', None) if F else None
            if type(FE).__name__ != 'Engine': FE = None
            if k == 'fc': return D.fc(FE) if FE is not None else {'ok': False, 'message': '🗂 整理還在準備，等幾秒'}
            return D.h265(ENG, FE) if k == 'h265' else D.vs(ENG)
        bg(get, lambda j, k=k: k == self.kind and self.render(j), lambda e: ENG.log.err('📊 總覽'))

    def _clear(self):
        while self.L.count():
            it = self.L.takeAt(0); w = it.widget()
            if w is not None: w.setParent(None); w.deleteLater()

    def _card(self, title='', sub=''):
        f = QFrame(); f.setObjectName('dzcard'); f.setStyleSheet('QFrame#dzcard{background:rgba(127,140,160,0.08);border:1px solid rgba(127,140,160,0.28);border-radius:14px}')
        v = QVBoxLayout(f); v.setContentsMargins(12, 10, 12, 10); v.setSpacing(6)
        if title:
            h = QHBoxLayout(); a = QLabel(title); a.setStyleSheet('font-weight:800;font-size:13px'); h.addWidget(a); h.addStretch(1)
            if sub: b = QLabel(sub); b.setStyleSheet('font-size:11px;color:#8994a4'); h.addWidget(b)
            v.addLayout(h)
        return f, v

    def _kpi(self, l, val, sub, col, delta=None, pct=None, go=None, tip=''):
        f = DzClick(); f.setObjectName('dzk'); f.setStyleSheet(f'QFrame#dzk{{background:rgba(127,140,160,0.08);border:1px solid rgba(127,140,160,0.28);border-top:3px solid {col};border-radius:14px}}')
        v = QVBoxLayout(f); v.setContentsMargins(12, 8, 12, 8); v.setSpacing(1); h = QHBoxLayout(); a = QLabel(l); a.setStyleSheet('font-size:11.5px;color:#8994a4'); h.addWidget(a); h.addStretch(1)
        if delta is not None:
            d = QLabel(f'+{int(delta):,} 今天'); d.setStyleSheet('font-size:11px;font-weight:800;padding:1px 7px;border-radius:8px;' + ('background:rgba(12,163,12,0.16);color:#3ccb3c' if delta else 'color:#8994a4;background:rgba(127,140,160,0.15)'))
            h.addWidget(d)
        v.addLayout(h); b = QLabel(str(val)); b.setStyleSheet('font-size:24px;font-weight:800'); v.addWidget(b)
        c = QLabel(str(sub)); c.setStyleSheet('font-size:11.5px;color:#8994a4'); v.addWidget(c)
        if pct is not None: v.addWidget(BarRow('', '', pct, col))
        if go is not None:
            f.setCursor(Qt.PointingHandCursor); f.go = (go if callable(go) else (lambda g=int(go): self.win.enter(g)))
        if tip: f.setToolTip(tip)
        return f

    def _head(self, title, btns):
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); t = QLabel(title); t.setStyleSheet('font-size:18px;font-weight:800'); h.addWidget(t)
        tm = QLabel(time.strftime('%H:%M:%S') + ' 更新'); tm.setStyleSheet('color:#8994a4;font-size:11px'); h.addWidget(tm); h.addStretch(1)
        for txt, fn, acc in btns:
            b = QPushButton(txt); b.setCursor(Qt.PointingHandCursor); b.clicked.connect(fn)
            if acc: b.setStyleSheet(f'QPushButton{{background:{acc};color:#fff;border:0;border-radius:14px;padding:6px 14px;font-weight:700}}')
            h.addWidget(b)
        return w

    def _legend(self, segs, fmt=None):
        w = QWidget(); g = QGridLayout(w); g.setContentsMargins(0, 0, 0, 0); g.setVerticalSpacing(3); tot = sum(float(s[1] or 0) for s in segs) or 1
        for i, s in enumerate(segs):
            n, v, c = s[0], float(s[1] or 0), s[2]
            sw = QLabel(); sw.setFixedSize(10, 10); sw.setStyleSheet(f'background:{c};border-radius:3px'); g.addWidget(sw, i, 0)
            g.addWidget(QLabel(str(n)), i, 1); b = QLabel(fmt(v) if fmt else f'{v:,.0f}'); b.setStyleSheet('font-weight:700'); g.addWidget(b, i, 2, Qt.AlignRight)
            e = QLabel(f'{_dzp(v, tot)}%'); e.setStyleSheet('color:#8994a4;font-size:11px'); g.addWidget(e, i, 3, Qt.AlignRight)
        g.setColumnStretch(1, 1); return w

    def _donut_card(self, title, sub, segs, big, lab, fmt=None):
        f, v = self._card(title, sub); h = QHBoxLayout(); dn = DonutW(); dn.set(segs, big, lab, fmt); h.addWidget(dn, 3); h.addWidget(self._legend(segs, fmt), 2); v.addLayout(h, 1); return f

    def _d7_card(self, title, sub, d, c, fmt=None):
        f, v = self._card(title, sub); w = Day7W(); w.set(d, c, fmt); v.addWidget(w, 1); return f

    def _bars_card(self, title, rows, sub=''):
        f, v = self._card(title, sub)
        for r in rows: v.addWidget(BarRow(r[0], r[1], r[2], r[3], r[4] if len(r) > 4 else ''))
        if not rows: v.addWidget(QLabel('—'))
        v.addStretch(1); return f

    def _disk(self, D):
        out = []
        for d in D or []:
            u = d['total'] - d['free']; fr = d['free'] / d['total'] if d['total'] else 1
            out.append((f"💽 {d['d']} 剩 {fmt_b(d['free'])}", f"{_dzp(u, d['total'])}%", _dzp(u, d['total']), '#d03b3b' if fr < 0.08 else '#fab219' if fr < 0.15 else '#5b8def', f'用了 {fmt_b(u)} / 共 {fmt_b(d["total"])}'))
        return out

    def render(self, j):
        self._clear(); L = self.L
        if not isinstance(j, dict) or not j.get('ok'): L.addWidget(QLabel(str((j or {}).get('message') or '讀不到')), 0, 0); return
        k = j.get('kind'); W = self.win
        if k == 'vs':
            G = j.get('G') or {}; n = j['n']
            L.addWidget(self._head('🎬 VideoSift 總覽', [('▦ 進 10 秒剪輯 ›', lambda: W.enter(0), '#3987e5')]), 0, 0, 1, 4)
            L.addWidget(self._kpi('🎬 影片', f"{n:,} 部", f"{fmt_b(j['b'])}・預覽圖 {_dzp(j['th'], n)}%", DZC[0], pct=_dzp(j['th'], n), go=0), 1, 0)
            L.addWidget(self._kpi('✅ 已分級', f"{_dzp(j['graded'], n)}%", f"{j['graded']:,}／{n:,} 部", DZC[2], delta=j['today'], pct=_dzp(j['graded'], n)), 1, 1)
            L.addWidget(self._kpi('✂ 初剪', f"{j['cutf']:,} 部", f"{j['cuts']:,} 段・收藏 {j['fav']:,}", DZC[1], delta=j['cut_today']), 1, 2)
            L.addWidget(self._kpi('🗑 F（待刪）', fmt_b(j['F_b']), f"{j['F_n']:,} 部，可以清掉的空間", DZC[7]), 1, 3)
            seg = [('S', G.get('S', 0), DZC[0]), ('A', G.get('A', 0), DZC[2]), ('E', G.get('E', 0), DZC[3]), ('F（待刪）', G.get('F', 0), DZC[7]), ('還沒分級', max(0, n - j['graded']), DZG)]
            L.addWidget(self._donut_card('🥧 分級分布', '滑過去看數字', seg, f"{_dzp(j['graded'], n)}%", '已分級'), 2, 0, 1, 2)
            L.addWidget(self._d7_card('📅 最近 7 天每天分級', f"今天 +{j['today']:,}", j['d7'], DZC[2]), 2, 2, 1, 2)
            L.addWidget(self._bars_card('📂 各資料夾進度', [(r['name'], f"{r['done']:,}／{r['n']:,}（{_dzp(r['done'], r['n'])}%）", _dzp(r['done'], r['n']), DZC[0], fmt_b(r['b'])) for r in j.get('roots') or []], '已分級／全部'), 3, 0, 1, 2)
            L.addWidget(self._bars_card('💽 硬碟空間', self._disk(j.get('disk'))), 3, 2, 1, 2)
        elif k == 'h265':
            C = j.get('codec') or {}; sl = j.get('slim') or {}; sv = j['saved'] + float(sl.get('save') or 0)
            L.addWidget(self._head('🗜 H265 總覽', [('🔁 進轉檔工作區 ›', lambda: W.enter(1), '#d95926'), ('🗜 整理的影片瘦身', lambda: W.enter(57), None)]), 0, 0, 1, 4)
            L.addWidget(self._kpi('💾 已經省下', fmt_b(sv), f"轉檔 {j['done']:,} 部" + (f"・瘦身 {sl.get('n', 0):,} 部" if sl.get('n') else ''), DZC[2], delta=j['today'] + int(sl.get('today') or 0), tip=f"轉檔前 {fmt_b(j['osz'])} → 轉檔後 {fmt_b(j['nsz'])}"), 1, 0)
            L.addWidget(self._kpi('🎯 還可以轉', f"{j['cand']:,} 部", f"{fmt_b(j['cand_b'])}・預估再省 {fmt_b(j['est_save'])}", DZC[1], go=1), 1, 1)
            L.addWidget(self._kpi('⏳ 轉檔中／排隊', f"{j['running']:,}／{j['queue']:,}", fmt_b(j['queue_b']) + (f"・失敗 {j['bad']:,}" if j['bad'] else ''), DZC[3], go=1), 1, 2)
            L.addWidget(self._kpi('📐 平均畫質 SSIM', f"{float(j['ssim']):.3f}" if j.get('ssim') else '—', f"平均縮到 {round(j['ratio'] * 100)}%（越接近 1 越像原檔）", DZC[6]), 1, 3)
            seg = [('H.265（已經小了）', (C.get('hevc') or [0, 0])[1], DZC[0], f"{(C.get('hevc') or [0])[0]:,} 部"), ('H.264', (C.get('h264') or [0, 0])[1], DZC[1], f"{(C.get('h264') or [0])[0]:,} 部"),
                   ('其他編碼', (C.get('other') or [0, 0])[1], DZC[3], f"{(C.get('other') or [0])[0]:,} 部"), ('還沒讀到', (C.get('unk') or [0, 0])[1], DZG, f"{(C.get('unk') or [0])[0]:,} 部")]
            tb = sum(float(s[1] or 0) for s in seg)
            L.addWidget(self._donut_card('🥧 影片編碼（照大小）', f'共 {fmt_b(tb)}', seg, f"{_dzp((C.get('hevc') or [0, 0])[1], tb)}%", '已是 H.265', fmt_b), 2, 0, 1, 2)
            L.addWidget(self._d7_card('📅 最近 7 天每天省多少', f"今天 {fmt_b(j['today_save'])}", j['d7'], DZC[2], fmt_b), 2, 2, 1, 2)
            tot = sv + j['est_save']
            L.addWidget(self._bars_card('📊 空間', [('已經省下（轉檔＋瘦身）', fmt_b(sv), _dzp(sv, tot), DZC[2]), ('預估還能省（還沒轉的）', fmt_b(j['est_save']), _dzp(j['est_save'], tot), DZC[1]),
                                                ('排隊中的', fmt_b(j['queue_b']), _dzp(j['queue_b'], j['cand_b'] + j['queue_b']), DZC[3])], '已省／還能省'), 3, 0, 1, 2)
            L.addWidget(self._bars_card('💽 硬碟空間', self._disk(j.get('disk'))), 3, 2, 1, 2)
        else:
            V = sorted([c for c in j.get('cats') or [] if c['n'] > 0], key=lambda c: -c['n']); tag = j['tagged']; vid = j['videos']; D = j.get('del') or {}
            L.addWidget(self._head('🗂 FileCompare 總覽', [('🎞 進 16 格分類 ›', lambda: W.enter(44), '#9085e9'), ('📋 詳細總覽', lambda: W.enter(40), None)]), 0, 0, 1, 6)
            r0 = 1
            P = (j.get('packs') or [None])[0]
            if P:
                b = QPushButton(f"💽 在 {P['X']}: 找到整理的紀錄（{P.get('pc') or ''}・{int(P.get('files') or 0):,} 個檔・分類 {int(P.get('tagged') or 0):,} 部）→ 📥 接上這份紀錄")
                b.clicked.connect(lambda _=False, X=P['X']: (setattr(W.fcp, '_pk', X), W.fcp.use_pack())); L.addWidget(b, r0, 0, 1, 6); r0 += 1
            L.addWidget(self._kpi('📁 全部檔案', f"{j['files']:,}", f"{fmt_b(j['bytes'])}・照片 {j['photos']:,}・影片 {vid:,}", DZC[0]), r0, 0)
            _UB = ENG.cfg.get('dash_fc_unit') == 'b' and j.get('vid_b') is not None
            L.addWidget(self._kpi('🎞 影片分類' + ('（大小）' if _UB else ''), f"{_dzp(j.get('tag_b'), j.get('vid_b')) if _UB else _dzp(tag, vid)}%",
                                  f"{fmt_b(j.get('tag_b'))}／{fmt_b(j.get('vid_b'))}" if _UB else f'{tag:,}／{vid:,} 部', '#9085e9', delta=j['today'],
                                  pct=_dzp(j.get('tag_b'), j.get('vid_b')) if _UB else _dzp(tag, vid), go=44,
                                  tip=f"部數 {_dzp(tag, vid)}%（{tag:,}／{vid:,} 部）・大小 {_dzp(j.get('tag_b'), j.get('vid_b'))}%（{fmt_b(j.get('tag_b'))}／{fmt_b(j.get('vid_b'))}）"), r0, 1)
            L.addWidget(self._kpi('🔁 重複可以省', fmt_b(j['dup_bytes']), f"{j['dup_groups']:,} 組・多 {j['dup_files']:,} 份", DZC[2], go=47), r0, 2)
            L.addWidget(self._kpi('🩺 有問題', f"{(j['broken'] or 0) + (j['partial'] or 0) + (j['zero'] or 0):,}", f"打不開 {j['broken']:,}・部分損毀 {j['partial']:,}", '#e66767', go=49), r0, 3)
            L.addWidget(self._kpi('📦 隔離區', f"{j['quar_n']:,} 個", f"{fmt_b(j['quar_bytes'])}・可以隨時復原", DZC[3], go=51), r0, 4)
            L.addWidget(self._kpi('🗑 Delete（已搬好）', fmt_b(D.get('b')), f"{int(D.get('n') or 0):,} 個" + (f"・還有 {D['wait']:,} 部沒搬" if D.get('wait') else '') + ('　點一下永久刪除…' if D.get('n') else ''),
                                  '#d03b3b', go=(self.win.fcp.del_purge if D.get('n') else None)), r0, 5)
            UB = ENG.cfg.get('dash_fc_unit') == 'b' and j.get('vid_b') is not None                  # V0.5.88 部數／大小切換
            kf = (lambda c: float(c['b'] or 0)) if UB else (lambda c: c['n'])
            V = sorted(V, key=lambda c: -kf(c)); ub = max(0.0, float(j.get('vid_b') or 0) - float(j.get('tag_b') or 0))
            seg = [(c['name'], kf(c), c['color'] or DZC[i % 8], f"{c['n']:,} 部" if UB else fmt_b(c['b'])) for i, c in enumerate(V[:7])]
            if len(V) > 7: seg.append((f'其他 {len(V) - 7} 類', sum(kf(c) for c in V[7:]), '#8a8f98'))
            seg.append(('還沒分類', ub if UB else max(0, vid - tag), DZG))
            pc_ = _dzp(j.get('tag_b'), j.get('vid_b')) if UB else _dzp(tag, vid)
            dc = self._donut_card('🥧 影片分類分布', f"{len(V)} 類・{'照大小算' if UB else '照部數算'}", seg, f'{pc_}%', '分好了（大小）' if UB else '分好了（部數）', fmt_b if UB else None)
            try:
                hl = dc.layout().itemAt(0).layout(); bx = QWidget(); bl = QHBoxLayout(bx); bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(0)
                for k_, n_ in (('n', '部數'), ('b', '大小')):
                    b_ = QPushButton(n_); b_.setCheckable(True); b_.setChecked((k_ == 'b') == UB); b_.setCursor(Qt.PointingHandCursor)
                    b_.setStyleSheet('QPushButton{padding:1px 10px;font-size:11px;border:1px solid rgba(127,140,160,.45);border-radius:0;background:transparent}QPushButton:checked{background:#9085e9;color:#fff;border-color:#9085e9}')
                    b_.clicked.connect(lambda _=False, k_=k_: (ENG.cfg.set('dash_fc_unit', k_), self.render(j))); bl.addWidget(b_)
                hl.insertWidget(1, bx)
            except Exception: ENG.log.err('📊 部數／大小切換')
            L.addWidget(dc, r0 + 1, 0, 1, 3)
            L.addWidget(self._d7_card('📅 最近 7 天每天分類', f"今天 +{j['today']:,}", j['d7'], '#9085e9'), r0 + 1, 3, 1, 3)
            L.addWidget(self._bars_card('⚙ 整理進度', [('🏷 拍攝資訊', f"{j['meta_done']:,}／{j['media']:,}", _dzp(j['meta_done'], j['media']), DZC[0]),
                                                  ('🔁 比對指紋', f"{j['hash_done']:,}／{j['hash_total']:,}", _dzp(j['hash_done'], j['hash_total']), DZC[2]),
                                                  ('🩺 損毀檢查', f"{j['health_done']:,}／{j['media']:,}", _dzp(j['health_done'], j['media']), '#e66767')]), r0 + 2, 0, 1, 3)
            L.addWidget(self._bars_card('💽 硬碟空間', self._disk(j.get('disk')), '、'.join(j.get('roots') or [])), r0 + 2, 3, 1, 3)
        for r_ in range(L.rowCount()): L.setRowStretch(r_, 0)
        L.setRowStretch(L.rowCount() - 1, 1); L.setRowStretch(L.rowCount() - 2, 1)


def fc_apply_pending(root):
    """「匯入舊 FileCompare 資料」複製好的，在 FileCompare 引擎開起來之前換上（原本的改名留著，不刪）."""
    try:
        pend = Path(root) / 'Data_import_pending'
        if not (pend / 'app.sqlite3').is_file(): return ''
        cur = Path(root) / 'Data'
        if cur.exists(): os.replace(str(cur), str(Path(root) / f'Data_before_import_{time.strftime("%Y%m%d_%H%M%S")}'))
        os.replace(str(pend), str(cur)); ENG.log.w(f'🗂 舊 FileCompare 資料換上了：{cur}'); return '✅ 舊 FileCompare 的整理紀錄換上了'
    except Exception as ex: ENG.log.err('換上舊 FileCompare 資料'); return f'⚠ 舊資料換不上去：{ex}'


class FCEmbedPage(QWidget):
    """🗂 整理（FileCompare）：FileCompare 整套程式跑在 SortCut 裡面（同一個程式、同一個視窗），左邊「🗂 整理」那組選單切它的各頁。
    資料放在 VideoSift\\FileCompare\\Data；開程式 3 秒後背景開始跑（掃描、比對重複…照 FileCompare 原本的設定）."""
    def __init__(self, win):
        super().__init__(); self.win = win; self.fw = None; self.err = ''; self.want = None
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        self.bar = QFrame(); self.bar.setObjectName('hero'); bl = QHBoxLayout(self.bar); bl.setContentsMargins(14, 8, 14, 8)
        self.bar_l = shrinkable(QLabel(''), True); bl.addWidget(self.bar_l, 1)
        self.b_imp = QPushButton('📥 匯入舊 FileCompare 資料'); self.b_imp.clicked.connect(lambda: self.use_pack() if getattr(self, '_pk', None) else self.import_old()); bl.addWidget(self.b_imp)
        self.b_rs = QPushButton('🔄 現在重開換上'); self.b_rs.clicked.connect(lambda: self.win.restart()); bl.addWidget(self.b_rs); self.b_rs.hide()   # V0.5.55
        self.b_x = QPushButton('✕'); self.b_x.setFixedWidth(34); self.b_x.clicked.connect(lambda: (ENG.cfg.set('fc_bar_off', True), self.bar.hide())); bl.addWidget(self.b_x)
        v.addWidget(self.bar); self.bar.hide()
        self.b_st = QPushButton(''); self.b_st.setObjectName('pill'); self.b_st.hide()        # ⏸／⚖／🤝：整理的後台現在誰在等（點一下看後台）
        self.b_st.setToolTip('整理的背景工作：暫停中、電腦忙自動讓路、或讓 SortCut 先用同一顆硬碟（點一下到「整理的後台」）')
        self.b_st.clicked.connect(lambda: self.fw is not None and self.fw.enter(1))
        self.b_del = QPushButton(''); self.b_del.setObjectName('pill'); self.b_del.hide(); self.b_del.setStyleSheet('color:#ff8a8a;border-color:#ff6b6b')   # V0.5.67 🗑 永久刪除 Delete
        self.b_del.setToolTip('把「Delete」分類裡已經搬好的檔永久刪掉（不經過資源回收筒），騰出硬碟空間'); self.b_del.clicked.connect(self.del_purge)
        sl = QHBoxLayout(); sl.setContentsMargins(10, 4, 10, 0); sl.addWidget(self.b_st); sl.addStretch(1); sl.addWidget(self.b_del); v.addLayout(sl)
        self.hint = QFrame(); hl_ = QHBoxLayout(self.hint); hl_.setContentsMargins(12, 2, 8, 2)                  # V0.5.17 這一頁跟 SortCut／HotZone 哪裡重疊、該用哪個
        self.hint_l = shrinkable(QLabel(''), True); self.hint_l.setObjectName('muted'); hl_.addWidget(self.hint_l, 1)
        self.hint_x = QPushButton('✕'); self.hint_x.setFixedWidth(30); self.hint_x.setToolTip('這一頁不要再提示'); self.hint_x.clicked.connect(self._hint_off); hl_.addWidget(self.hint_x)
        v.addWidget(self.hint); self.hint.hide(); self._hint_pg = None
        self.st_t = QTimer(self); self.st_t.timeout.connect(self._st); self.st_t.start(5000)
        self.msgl = QLabel('🗂 整理（FileCompare）準備中…'); self.msgl.setAlignment(Qt.AlignCenter); self.msgl.setObjectName('muted'); v.addWidget(self.msgl, 1)
        self.host = QVBoxLayout(); v.addLayout(self.host, 1)
        QTimer.singleShot(3000, self.ensure)

    def ensure(self):
        if self.fw is not None or self.err: return self.fw
        if getattr(self.win, '_handoff', False) or getattr(QApplication.instance(), '_vs_main', None) is not self.win:   # 熱更新失敗的半成品視窗不要接手
            if not getattr(self.win, '_handoff', False): QTimer.singleShot(2000, self.ensure)
            return None
        try:
            import fc_app as F
            pm = fc_apply_pending(fc_root())
            ff = (getattr(ENG, 'ff', '') or '', getattr(ENG, 'ffprobe', '') or '')
            F.embed_boot(fc_root(), vs_root=ROOT, theme=THEME_MODE['mode'], zoom=THEME_MODE['zoom'], msg=lambda s_, ms=6000: self.win.msg(s_, ms), ff=ff, imp=self.import_old, nav=self._fc_nav, perf=lambda: ENG.perf, badge=self._fc_badge)
            self.fw = F.embed_main(); self.host.addWidget(self.fw, 1); self.msgl.hide(); self.fw.show()
            try:
                import fc_core as FCC
                FCC.EXT_HOLD['fn'] = self._hold                                  # VS 在用同一顆硬碟時，整理的大量讀寫先讓路
                FCC.EXT_HOLD['cap'] = lambda k, n: __import__('vs_yield').cap(k, n)   # V0.5.71 🤝 讓路給 TikLive：整理的背景也跟著等級
                FCC.EXT_HOLD['conv'] = self._conv_busy                           # 同一部影片不要「轉檔」和「影片瘦身」兩邊都轉
                FCC.EXT_HOLD['slimmed'] = self._fc_slimmed                       # V0.5.54 瘦身好的新檔接手 VS 原本那筆（預覽圖、分級沿用）
                import fc_fcore as FCF; FCF.MOVED['fn'] = self._fc_moved          # V0.5.34 整理搬了檔案：VS 的紀錄跟著改
                core.EXT_MOVED['fn'] = self._vs_moved                              # V0.5.38 反過來：VS 搬了檔，整理的紀錄跟著改
                FCC.EXT_HOLD['enc'] = lambda: (('SortCut 正在轉檔（' + str(len(ENG.cv_active)) + ' 部），等它轉完再瘦身下一部') if getattr(ENG, 'cv_active', None) else '') or __import__('vs_yield').hold('slim')   # V0.5.28 不搶顯示卡；V0.5.71 也讓 TikLive
            except Exception: ENG.log.err('🗂 整理：讓路規則')
            if pm: self.win.msg(pm, 12000)
            ENG.log.w(f'🗂 整理（FileCompare V{F.APP_VERSION}）開好了：資料在 {fc_root()}')
            self._bar()
            if self.want is not None: self.fw.enter(self.want)
        except Exception:
            self.err = traceback.format_exc(); ENG.log.w('⚠ 🗂 整理（FileCompare）開不起來：\n' + self.err)
            self.msgl.setText('⚠ 🗂 整理（FileCompare）開不起來，原因記在 LOG。SortCut 其他功能照常可以用。\n\n' + self.err.strip().splitlines()[-1][:300])
        return self.fw

    FC_IO = ('meta', 'hash', 'health', 'repair', 'ana')                       # V0.5.63 只讓「整檔讀」的；掃資料夾、16 格預覽（分類時要用）照做

    def _hold(self, kind):
        """整理（FileCompare）的背景工作要不要先讓 SortCut：VS 正在大量讀寫（轉檔、預覽圖、初剪、複製、搬硬碟）的那顆硬碟＝整理要掃的那顆 → 先不開新的（5 秒看一次）."""
        if kind not in self.FC_IO or ENG.cfg.get('fc_yield') is False: return ''
        try:                                                                    # V0.5.71 🤝 Lv 1（TikLive 很忙）：整理整檔讀的先不開新的
            import vs_yield; y_ = vs_yield.get()
            if y_ is not None and y_.on and y_.level <= 1 and y_.tk_pids: return f'🤝 讓路給 TikLive（Lv 1）：{y_.gov.why}'
        except Exception: pass
        c = getattr(self, '_hold_c', None)
        if c and time.time() - c[0] < 5: return c[1]
        r = ''
        try:
            import fc_app as F
            dr = {str(x)[0].upper() for x in (F.ENG.cfg.get('roots') or []) if len(str(x)) >= 2 and str(x)[1] == ':'}
            for x in ENG.drive_busy():
                if x['busy'] and x['d'] in dr: r = f"讓 SortCut 先用 {x['d']} 碟（{'、'.join(x['busy'])}）"; break
        except Exception: r = ''
        self._hold_c = (time.time(), r); return r

    def _fc_nav(self, fi):
        """整理裡面按按鈕換頁（例如總覽的「去重複檔」）：左邊選單、標題跟著換，不重新切頁."""
        try:
            v = next((k for k, x in FC_PAGES.items() if x == int(fi)), None); nav = self.win.nav
            if v is None or nav.currentRow() == v: return
            nav._page = v; nav.setCurrentRow(v)
            self._hint(fi)
            self.win.ptitle.setText(f'🗂 整理 · {nav.page_icon(v)} {nav.page_name(v)}'); ENG.cfg.set('last_page', int(v))
        except Exception: pass

    def _fc_badge(self, fi, txt):
        """整理的數字（重複幾組、有問題幾個、隔離區幾個、背景幾個在跑）也掛到 SortCut 左邊選單."""
        try:
            v = next((k for k, x in FC_PAGES.items() if x == int(fi)), None)
            if v is not None: self.win.nav.set_badge(v, txt)
        except Exception: pass

    def _fc_moved(self, src, dst):
        """整理（分類、隔離、依日期整理、重複檔）搬了一個檔：SortCut 有這部的話紀錄跟著改路徑（分級、預覽圖、初剪紀錄都沿用），
        不會被當成「不見了＋一部新影片」重做預覽圖。搬到影片庫外面的就不動（下次掃描照常標成不見）."""
        try:
            if os.path.splitext(str(src))[1].lower() not in core.VIDEO_EXT: return              # 照片等：SortCut 沒收（大量搬照片時不用每張查一次）
            r = ENG.db.one('SELECT id FROM files WHERE path=?', (src,))                         # 只查完全一樣的路徑（有索引；不做 lower() 全表掃描）
            if not r: return
            rt = ENG.root_of(dst) or ''
            if not rt: return
            dup = ENG.db.one('SELECT id FROM files WHERE path=? AND id!=?', (dst, int(r[0])))
            if dup is not None:
                ENG.db.x('DELETE FROM files WHERE id=? AND th_state!=2 AND grade=\'\' AND cut_n=0', (int(dup[0]),))
                if ENG.db.one('SELECT id FROM files WHERE id=?', (int(dup[0]),)): return            # 那邊已經有一筆有紀錄的：兩筆都留著，不硬改
            ENG.db.x('UPDATE files SET path=?, folder=?, name=?, root=?, missing=0 WHERE id=?', (dst, os.path.dirname(dst), os.path.basename(dst), rt, int(r[0])))
            LM = self.__dict__.setdefault('_last_mv', {}); LM[str(src)] = str(dst)              # 瘦身時：原檔先搬去轉檔後隔離區，新檔接手要找得到這筆
            if len(LM) > 200: LM.pop(next(iter(LM)))
            ENG.log.w(f'🗂 整理搬了檔案，SortCut 紀錄跟著改：{src} → {dst}')
        except Exception: ENG.log.err('🗂 整理搬檔：改 SortCut 紀錄')

    def _vs_moved(self, src, dst):
        """SortCut 移到待刪／歸檔：整理（FileCompare）有這個檔的話紀錄跟著改路徑（指紋、拍攝資訊、分類都沿用，不用重算）；搬出整理的資料夾就不動."""
        try:
            import fc_app as F, fc_fcore as FF
            E = F.ENG
            if type(E).__name__ != 'Engine': return
            r = E.db.one('SELECT id FROM files WHERE path=?', (src,))                         # 只查完全一樣的路徑（整理的資料表可能幾十萬筆，不做全表掃描）
            if not r: return
            rt = next((x for x in E.fc_list('roots') if FF.under(dst, x)), None)
            if not rt or E.db.one('SELECT id FROM files WHERE path=?', (dst,)): return
            E.db.x('UPDATE files SET path=?, root=? WHERE id=?', (dst, rt, int(r[0]))); ENG.log.w(f'🗂 SortCut 搬了檔案，整理的紀錄跟著改：{src} → {dst}')
        except Exception: ENG.log.err('SortCut 搬檔：改整理的紀錄')

    def _fc_slimmed(self, src, out, osz, nsz):
        """整理的影片瘦身做好一部：SortCut 原本那筆（原檔已經搬去轉檔後隔離區）改成新的 _h265.mp4，
        預覽圖、分級、初剪紀錄都沿用（內容一樣），不會把新檔當成新影片重做預覽圖."""
        try:
            if os.path.splitext(str(src))[1].lower() not in core.VIDEO_EXT or not ENG.root_of(out): return
            qp = (self.__dict__.get('_last_mv') or {}).pop(str(src), None)
            r = (ENG.db.one('SELECT id FROM files WHERE path=?', (qp,)) if qp else None) or ENG.db.one('SELECT id FROM files WHERE path=?', (str(src),))
            if not r: return
            ENG._conv_takeover(int(r[0]), Path(qp or src), Path(out), {'ok': True, 'vcodec': 'hevc'}, osz, nsz, keep_orig=False)
        except Exception: ENG.log.err('🗂 影片瘦身：新檔接手 SortCut 那筆')

    def _conv_busy(self, src):
        """整理的 🗜 影片瘦身要轉 src 之前問：SortCut 的 🔁 轉檔已經排了／正在轉／轉好了這部 → 回原因（跳過）."""
        try:
            r = ENG.db.one('SELECT cv_state FROM files WHERE path=?', (str(src),)) or ENG.db.one('SELECT cv_state FROM files WHERE lower(path)=lower(?)', (str(src),))
            c = int(r[0] or 0) if r else 0
            return {1: 'SortCut 的「🔁 轉檔」已經排了這部', 2: 'SortCut 的「🔁 轉檔」正在轉這部', 3: 'SortCut 已經轉過這部'}.get(c, '')
        except Exception: return ''

    def _del_info(self):
        try:
            import fc_app as F, vs_fcdel as FD
            if type(F.ENG).__name__ != 'Engine': return None
            return FD.info(F.ENG)
        except Exception: return None

    def _del_btn(self, j):
        if not isinstance(j, dict): self.b_del.hide(); return
        st = j.get('st') or {}
        if st.get('run'): self.b_del.setText('🗑 刪除中 ' + str(st.get('msg') or '')); self.b_del.show(); return
        if j.get('n'): self.b_del.setText(f"🗑 永久刪除 Delete（{j['n']:,} 個・{fmt_b(j['bytes'])}）"); self.b_del.show()
        else: self.b_del.hide()

    def del_purge(self):
        """V0.5.67 🗑 Delete 分類裡已經搬好的檔 → 永久刪除（兩次確認）."""
        j = self._del_info()
        if not j: return
        if (j.get('st') or {}).get('run'): self.win.msg('🗑 已經在刪了：' + str(j['st'].get('msg'))); return
        if not j['n']:
            QMessageBox.information(self, '🗑 永久刪除 Delete', 'Delete 裡沒有已經搬好的檔' + (f"（還有 {j['wait']} 部沒搬，先按 🚚 搬）" if j['wait'] else '')); return
        dv = '、'.join(f'{d} {fmt_b(b)}' for d, b in j['drives'].items())
        if QMessageBox.warning(self, '🗑 永久刪除 Delete', f"永久刪除「{'／'.join(j['cats'])}」分類裡已經搬好的檔：\n\n{j['n']:,} 個，共 {fmt_b(j['bytes'])}（{dv}）\n"
                               + (f"還沒搬的 {j['wait']} 部不會刪（要刪先按 🚚 搬）\n" if j['wait'] else '') + '\n不經過資源回收筒，刪了救不回來。確定？',
                               QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        t, ok = QInputDialog.getText(self, '最後確認', '輸入「刪除」兩個字：')
        if not ok or str(t).strip() != '刪除': self.win.msg('沒有刪'); return
        import fc_app as F, vs_fcdel as FD
        def gone_(p_):
            try: ENG.db.x('UPDATE files SET missing=1 WHERE path=?', (p_,))
            except Exception: pass
        r = FD.purge(F.ENG, lp=getattr(sys.modules.get('fc_fcore'), 'lp', None), on_gone=gone_, log=ENG.log.w)
        self.win.msg('🗑 ' + str(r.get('message')), 8000); self._del_t = 0

    def _st(self):
        """上面那顆小膠囊：⏸ 暫停中、⚖ 電腦忙讓路、🤝 讓 SortCut 先用硬碟（畫面看得到才算，5 秒一次；用快取，不查硬碟）."""
        if self.fw is None or not self.isVisible(): return
        try:
            if time.time() - getattr(self, '_del_t', 0) > (3 if ((getattr(self, '_del_last', None) or {}).get('st') or {}).get('run') else 30):
                self._del_t = time.time(); self._del_last = self._del_info(); self._del_btn(self._del_last)
        except Exception: pass
        try:
            import fc_app as F
            E = F.ENG; nm = dict((k, n) for k, _i, n in E.BG_KINDS)
            P = [nm.get(k, k) for k, v_ in list(E.bg_pause.items()) if v_]; H = [nm.get(k, k) for k in list(E.bg_auto)]
            X = ((ENG.fc_bg() or {}).get('hold') or '') if hasattr(ENG, 'fc_bg') else self._hold('hash'); SL_ = (getattr(getattr(E, 'slim', None), 'st', None) or {})
            W_ = '🎛 影片瘦身等 SortCut 轉檔轉完' if SL_.get('run') and str(SL_.get('cur') or '').startswith('⏳') else ''
            t_ = '　'.join(x for x in (('⏸ 暫停：' + '、'.join(P)) if P else '', ('⚖ 電腦忙讓路：' + '、'.join(H)) if H else '', ('🤝 ' + X) if X else '', W_) if x)
            self.b_st.setText(t_); self.b_st.setVisible(bool(t_))
        except Exception: self.b_st.hide()

    def _bar(self):
        try:
            import fc_app as F
            roots = list(F.ENG.cfg.get('roots') or []) if F.ENG is not None else []
        except Exception: roots = []
        if (fc_root() / 'Data_import_pending').is_dir():                         # V0.5.55 舊資料複製好了、還沒重開：一直提醒（按了就重開）
            self.bar_l.setText('📥 <b>舊 FileCompare 資料已經複製好了</b>，重開 SortCut 才會換上（現在的整理紀錄會改名留著，不刪）。')
            self.bar_l.setTextFormat(Qt.RichText); self.b_imp.hide(); self.b_x.hide(); self.b_rs.show(); self.bar.show(); return
        self.b_rs.hide(); self.b_imp.show(); self.b_x.show()
        if not roots:                                                            # V0.5.69 💽 接著的硬碟上有整理紀錄（別台電腦寫的）：直接接上
            try:
                import vs_fcpack
                P_ = vs_fcpack.find()
                if P_:
                    X_, J_ = P_[0]
                    self.bar_l.setText(f"💽 <b>在 {X_}: 找到整理（FileCompare）的紀錄</b>：{esc_html(J_.get('pc') or '')} 寫的、{time.strftime('%m-%d %H:%M', time.localtime(float(J_.get('t') or 0)))}、"
                                       f"{int(J_.get('files') or 0):,} 個檔、分類 {int(J_.get('tagged') or 0):,} 部。按右邊「📥 接上」，重開就跟原本那台一樣。")
                    self.bar_l.setTextFormat(Qt.RichText); self._pk = X_; self.b_imp.setText(f'📥 接上 {X_}: 的紀錄'); self.bar.show(); return
            except Exception: ENG.log.err('💽 找硬碟上的整理紀錄')
        self._pk = None; self.b_imp.setText('📥 匯入舊 FileCompare 資料')
        if ENG.cfg.get('fc_bar_off') or roots: self.bar.hide(); return
        self.bar_l.setText('🗂 這裡是原本的 <b>FileCompare</b>。還沒有要整理的資料夾：到 ①「🏠 整理總覽」的「要整理的資料夾」按加入（例如 R:\\），再按 ▶ 開始掃描，影片就會出現在「影片快速分類」。舊電腦用過的話：把舊 FileCompare 的 <b>Data</b> 複製過來，按右邊「📥 匯入」（R 碟代號要一樣）。')
        self.bar_l.setTextFormat(Qt.RichText); self.bar.show()

    HINTS = vs_web.VS_FC_HINTS                                                   # 手機共用同一份

    def _hint(self, fi):
        t = self.HINTS.get(int(fi)) if int(fi) not in (ENG.cfg.get('fc_hint_off') or []) else None
        self._hint_pg = int(fi); self.hint_l.setText(t or ''); self.hint.setVisible(bool(t))

    def _hint_off(self):
        L = list(ENG.cfg.get('fc_hint_off') or [])
        if self._hint_pg is not None and self._hint_pg not in L: L.append(self._hint_pg); ENG.cfg.set('fc_hint_off', L)
        self.hint.hide()

    def show_fc(self, pg):
        self.want = int(pg); fw = self.ensure()
        try: self._hint(pg)
        except Exception: pass
        if fw is not None:
            try: fw.enter(int(pg))
            except Exception: ENG.log.err('🗂 整理：切頁')

    def set_theme(self, mode, zoom=None):
        if self.fw is None: return
        try:
            import fc_app as F
            F.embed_theme(mode, zoom)
        except Exception: pass

    def use_pack(self):
        """V0.5.69 接上硬碟身上的整理紀錄（X:\\VideoSIFT\\.vsdata\\FileCompare）."""
        X_ = getattr(self, '_pk', None)
        if not X_: return
        try:
            import vs_fcpack
            r = vs_fcpack.use(X_, fc_root()); self._bar()
            if QMessageBox.question(self, '💽 接上整理紀錄', r['message'] + '\n\n現在重開？') == QMessageBox.Yes: self.win.restart()
        except Exception as ex: ENG.log.err('💽 接上整理紀錄'); QMessageBox.warning(self, '💽 接上整理紀錄', f'接不上：{ex}')

    def import_old(self):
        """📥 選舊 FileCompare 的資料夾（或它的 Data）：複製到 VideoSift\\FileCompare\\Data_import_pending，SortCut 重開時換上（原本的改名留著）."""
        d = QFileDialog.getExistingDirectory(self, '選舊的 FileCompare 資料夾（或它裡面的 Data 資料夾）')
        if not d: return
        src = Path(d)
        if not (src / 'app.sqlite3').is_file() and (src / 'Data' / 'app.sqlite3').is_file(): src = src / 'Data'
        if not (src / 'app.sqlite3').is_file(): QMessageBox.warning(self, '📥 匯入', f'這個資料夾裡找不到 FileCompare 的資料庫（app.sqlite3）：\n{d}'); return
        try: sz = sum(f.stat().st_size for f in src.rglob('*') if f.is_file())
        except Exception: sz = 0
        try: R_ = [str(x) for x in (json.loads((src / 'settings.json').read_text(encoding='utf-8')).get('roots') or [])]   # V0.5.14 舊的整理資料夾在這台找不找得到
        except Exception: R_ = []
        rl = '\n'.join(('✅ ' if os.path.isdir(r) else '⚠ 這台找不到：') + r for r in R_[:12]) + ('\n…' if len(R_) > 12 else '')
        miss = sum(1 for r in R_ if not os.path.isdir(r))
        if QMessageBox.question(self, '📥 匯入舊 FileCompare 資料', f'從：{src}\n大小：{fmt_b(sz)}\n\n要整理的資料夾：\n{rl or "（沒有設定）"}\n'
                                + (f'\n⚠ 有 {miss} 個這台找不到：硬碟還沒接上或代號不一樣（例如要改回 R:），接好再匯入比較好；匯入後也可以到「整理總覽」改。\n' if miss else '')
                                + '\n複製好之後要重開 SortCut 才會換上；現在 SortCut 裡的整理紀錄會改名留著（不刪）。\n開始複製？') != QMessageBox.Yes: return
        dst = fc_root() / 'Data_import_pending'
        P = {'n': 0, 'b': 0, 'tot': sz}                                          # V0.5.23 複製進度（幾個檔、幾 %）
        def cp(a_, b_, *k_, **kw_):
            r_ = shutil.copy2(a_, b_); P['n'] += 1
            try: P['b'] += os.path.getsize(b_)
            except OSError: pass
            return r_
        def job():
            if dst.exists(): shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(str(src), str(dst), ignore=shutil.ignore_patterns('db_backup', 'run_state.json', 'watchdog.ps1'), copy_function=cp)
            return True
        tm = QTimer(self)
        tm.timeout.connect(lambda: self.win.msg(f"📥 複製舊 FileCompare 資料：{P['n']:,} 個檔・{fmt_b(P['b'])}" + (f"（{min(99, int(P['b'] * 100 / P['tot']))}%）" if P['tot'] else ''), 3000))
        tm.start(1000)
        def done(_r):
            tm.stop(); tm.deleteLater()
            self.win.msg(f"📥 舊資料複製好了（{P['n']:,} 個檔、{fmt_b(P['b'])}）：重開 SortCut 就會換上", 15000)
            try: self._bar()
            except Exception: pass
            if QMessageBox.question(self, '📥 匯入', '複製好了。現在重開 SortCut 換上舊資料？（背景工作下次會接著做）') == QMessageBox.Yes: self.win.restart()
        self.win.msg('📥 複製舊 FileCompare 資料中…（大的話要幾分鐘）', 60000); bg(job, done, lambda e: (tm.stop(), QMessageBox.warning(self, '📥 匯入', f'複製失敗：{e}')))


class HZEmbedPage(QWidget):
    """HotZone 的畫面嵌在 SortCut 裡（V0.1.56）：用電腦上的 Python＋PySide6 開一個沒有邊框的 HotZone 視窗，把它放進這一頁；
    左邊選單點 HotZone 的哪一頁，就叫它切過去（HotZone 自己的左側選單藏起來）。整個是一個程式的感覺。"""
    def __init__(self, win):
        super().__init__(); self.win = win; self.srv = None; self.sock = None; self.proc = None; self.container = None; self.fw = None; self.want = ''; self.buf = b''; self._t_start = 0
        self.name = f'VideoSift_HZEmbed_{os.getpid()}_{int(time.time())}'
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        self.msgw = QFrame(); self.msgw.setObjectName('hero'); mv = QVBoxLayout(self.msgw); mv.setContentsMargins(20, 18, 20, 18)
        self.msg = shrinkable(QLabel('HotZone 準備中…'), True); self.msg.setStyleSheet('font-size:15px;background:transparent'); mv.addWidget(self.msg)
        self.b1 = QPushButton('▶ 啟動 HotZone 背景引擎'); self.b1.setObjectName('start'); self.b2 = QPushButton('📦 安裝 PySide6（HotZone 畫面要用）'); self.b3 = QPushButton('🔥 到 HotZone 總管'); self.b4 = QPushButton('🔄 重新開 HotZone 畫面')
        mv.addWidget(flow_row([self.b1, self.b2, self.b4, self.b3])); mv.addStretch(1)
        self.host = QWidget(); self.hl = QVBoxLayout(self.host); self.hl.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.msgw); v.addWidget(self.host, 1); self.host.hide()
        self.b1.clicked.connect(lambda: bg(lambda: ENG.hz.start('HotZone 頁'), lambda r: (self.win.msg('🔥 ' + r['message'], 8000), QTimer.singleShot(4000, self.ensure))))
        self.b2.clicked.connect(lambda: bg(lambda: ENG.hz.install(True), lambda r: self.win.msg('🔥 ' + r['message'], 10000)))
        self.b3.clicked.connect(lambda: self.win.nav.setCurrentRow(11)); self.b4.clicked.connect(lambda: (self._kill(), self.ensure()))
        self.tm = QTimer(self); self.tm.timeout.connect(self._watch); self.tm.start(1500)

    def _show_msg(self, text, start=False, pyside=False, again=False):
        self.msg.setText(text); self.b1.setVisible(start); self.b2.setVisible(pyside); self.b4.setVisible(again); self.msgw.show()
        if self.container is None: self.host.hide()

    def show_hz(self, pid):
        self.want = pid; self.ensure(); self.send('go ' + pid)

    def ensure(self):
        H = getattr(ENG, 'hz', None)
        if H is None: self._show_msg('HotZone 模組沒有載入（LOG 有原因）'); return
        if self.container is not None and self.sock is not None: return
        if self.proc is not None and self.proc.poll() is None and time.time() - self._t_start < 40: return          # 正在開
        if getattr(H, 'migrating', False): self._show_msg('🔥 HotZone 資料整合中，好了會自動打開…'); return
        def chk():
            pg = H.ping(fresh=True); env = H.env if (H.env or {}).get('exe') else H.check_env(); return pg, env
        bg(chk, self._ensure2)

    def _ensure2(self, r):
        pg, env = r; H = ENG.hz
        if getattr(H, 'migrating', False): self._show_msg('🔥 HotZone 資料整合中，好了會自動打開…'); return
        if not pg: self._show_msg('🔥 HotZone 背景引擎沒有在跑。按「▶ 啟動」（Windows 會問一次系統管理員權限）；第一次用請先到「HotZone 總管」檢查環境。', start=True); return
        if not (env or {}).get('pyside6'):
            self._show_msg('🔥 HotZone 的畫面要用電腦上 Python 的 PySide6（含網頁元件）才能嵌進 SortCut。按「📦 安裝 PySide6」（大約 10 分鐘），裝好會自動打開。', pyside=True); return
        if self.container is not None and self.sock is not None: return
        if self.proc is not None and self.proc.poll() is None and time.time() - self._t_start < 40: return
        from PySide6.QtNetwork import QLocalServer
        if self.srv is None:
            QLocalServer.removeServer(self.name); self.srv = QLocalServer(self); self.srv.listen(self.name); self.srv.newConnection.connect(self._conn)
        try:
            import vs_hotzone as VH
            self.proc = subprocess.Popen([H.pyw(env), H.boot_path(), '--root', str(H.root()), '--embed', self.name], creationflags=core.NO_WINDOW, stdin=subprocess.DEVNULL,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, env=VH.clean_env())
            self._t_start = time.time(); ENG.log.w(f'🔥 打開嵌進 SortCut 的 HotZone 畫面（{self.name}）')
            self._show_msg('🔥 正在打開 HotZone…（第一次大約 5～10 秒）')
        except Exception as ex: self._show_msg(f'HotZone 畫面開不起來：{ex}', again=True)

    def _conn(self):
        s_ = self.srv.nextPendingConnection()
        if s_ is None: return
        self.sock = s_; self.buf = b''; s_.readyRead.connect(self._read); s_.disconnected.connect(self._gone)

    def _read(self):
        if self.sock is None: return
        self.buf += bytes(self.sock.readAll())
        while b'\n' in self.buf:
            line, self.buf = self.buf.split(b'\n', 1); cmd = line.decode('utf-8', 'replace').strip()
            if cmd.startswith('hwnd '):
                try: self._embed(int(cmd[5:]))
                except Exception: ENG.log.err('嵌入 HotZone 畫面')

    def _embed(self, hwnd):
        if self.container is not None: self.container.setParent(None); self.container.deleteLater(); self.container = None
        self.fw = QWindow.fromWinId(hwnd); self.container = QWidget.createWindowContainer(self.fw, self.host)
        self.container.setFocusPolicy(Qt.StrongFocus); self.container.setMinimumSize(200, 200); self.hl.addWidget(self.container)
        self.msgw.hide(); self.host.show(); ENG.log.w('🔥 HotZone 畫面嵌進 SortCut 了')
        if self.want: self.send('go ' + self.want)

    def send(self, line):
        try:
            if self.sock is not None: self.sock.write((line + '\n').encode('utf-8')); self.sock.flush(); self.sock.waitForBytesWritten(300)
        except Exception: pass

    def _detach(self):
        """先把 HotZone 的視窗從 SortCut 拿出來，免得 SortCut 關掉時把別的程式的視窗一起毀掉."""
        try:
            if self.fw is not None: self.fw.hide(); self.fw.setParent(None)
        except Exception: pass
        if self.container is not None:
            try: self.container.setParent(None); self.container.deleteLater()
            except Exception: pass
        self.container = None; self.fw = None

    def _gone(self):
        try:
            snd = self.sender()
            if snd is not None and self.sock is not None and snd is not self.sock: return     # 舊的那個斷了（HotZone 自己重開畫面），新的照用
        except Exception: pass
        if self.sock is None and self.container is None: return
        self.sock = None; self._detach(); self.host.hide()
        if not self.win.quitting: self._show_msg('HotZone 畫面關掉了（背景引擎還在跑的話，搬檔、熱區照常）。', again=True); ENG.log.w('🔥 嵌進來的 HotZone 畫面關掉了')

    def _watch(self):
        if self.proc is not None and self.proc.poll() is not None and self.sock is None and self.container is None and self.isVisible():
            self.proc = None; self._show_msg('HotZone 畫面沒有打開（LOG\\videosift_boot_log.txt 在 HotZone 資料夾）。', again=True); self._t_try = time.time() + 60
        elif self.isVisible() and self.container is None and self.proc is None and time.time() - getattr(self, '_t_try', 0) > 8:
            self._t_try = time.time(); self.ensure()                              # 引擎剛啟動、PySide6 剛裝好：自動再試

    def _kill(self):
        self._detach(); self.send('quit')
        try:
            if self.sock is not None: self.sock.disconnectFromServer()
        except Exception: pass
        self.sock = None; self.host.hide()
        try:
            if self.proc is not None and self.proc.poll() is None: QTimer.singleShot(1500, lambda p=self.proc: p.poll() is None and p.kill())
        except Exception: pass
        self.proc = None

    def shutdown(self):
        self._kill()
        try:
            if self.srv is not None: self.srv.close()
        except Exception: pass


class HotZonePage(QWidget):
    """🔥 HotZone（V0.1.55 整進 SortCut）：背景引擎狀態、啟動／停止／接手原本的 HotZoneFM.exe、打開 HotZone 視窗、硬碟協調員."""
    def __init__(self, win):
        super().__init__(); self.win = win; v = QVBoxLayout(self); v.setContentsMargins(10, 8, 10, 8); v.setSpacing(8)
        hero = QFrame(); hero.setObjectName('hero'); hv = QVBoxLayout(hero); hv.setContentsMargins(12, 10, 12, 10); v.addWidget(hero)
        self.h1 = QLabel('🔥 HotZone 總管'); self.h1.setStyleSheet('font-weight:900;font-size:16px;background:transparent'); hv.addWidget(self.h1)
        self.h2 = shrinkable(QLabel(''), True); self.h2.setObjectName('muted'); self.h2.setTextFormat(Qt.RichText); hv.addWidget(self.h2)
        self.b_start = QPushButton('▶ 啟動背景引擎'); self.b_start.setObjectName('start'); self.b_stop = QPushButton('⏹ 停止'); self.b_take = QPushButton('🔁 接手原本的 HotZone')
        self.b_open = QPushButton('🗂 打開 HotZone 檔案總管'); self.b_open.setStyleSheet('QPushButton{font-weight:800}'); self.b_root = QPushButton('📁 HotZone 資料夾…')
        self.b_win = QPushButton('🪟 另開視窗'); self.b_win.setToolTip('不嵌在 SortCut 裡，另外開一個 HotZone 視窗（或 Edge 視窗）')
        hv.addWidget(flow_row([self.b_open, self.b_start, self.b_take, self.b_stop, self.b_root, self.b_win]))
        mg = QFrame(); mg.setObjectName('card'); ml = QVBoxLayout(mg); ml.setContentsMargins(10, 8, 10, 8); hv.addWidget(mg); self.mig_box = mg
        self.mig_l = shrinkable(QLabel(''), True); self.mig_l.setStyleSheet('background:transparent'); self.mig_l.setTextFormat(Qt.RichText); ml.addWidget(self.mig_l)
        self.b_mig = QPushButton('📦 把偵測到的 HotZone 資料整合進 SortCut'); self.b_mig.setObjectName('start')
        self.b_keep = QPushButton('📌 就用原本的資料夾（不整合）'); self.b_keep.setToolTip('不複製，SortCut 直接讀寫原本的 HotZone 資料夾（設定、佇列、熱區、索引都照舊）')
        self.b_diag = QPushButton('🩺 連線診斷'); self.b_diag.setToolTip('一步一步檢查為什麼連不上原本的 HotZone 資料')
        self.b_rep = QPushButton('📄 整合明細'); self.b_rep.hide()
        ml.addWidget(flow_row([self.b_mig, self.b_keep, self.b_diag, self.b_rep]))
        self.cand_w = QWidget(); self.cand_l = QVBoxLayout(self.cand_w); self.cand_l.setContentsMargins(0, 0, 0, 0); ml.addWidget(self.cand_w); self._cands_k = None
        self.diag = shrinkable(QLabel(''), True); self.diag.setTextFormat(Qt.RichText); self.diag.setStyleSheet('background:transparent'); self.diag.hide(); ml.addWidget(self.diag)
        g = QGroupBox('Python 環境（HotZone 的背景引擎用電腦上的 Python 3.11 跑，跟人臉辨識同一個）'); gl = QVBoxLayout(g); v.addWidget(g)
        self.envl = shrinkable(QLabel('還沒檢查'), True); gl.addWidget(self.envl)
        self.b_chk = QPushButton('🔍 檢查環境'); self.b_ins = QPushButton('📦 安裝需要的套件（Pillow、numpy、OpenCV）'); self.b_ins_w = QPushButton('📦 再裝視窗用的 PySide6（可以從檔案總管拖檔案進來）')
        self.c_auto = QCheckBox('開 SortCut 時，如果 HotZone 沒在跑就自動啟動（會問一次系統管理員權限；HotZone 設定裡開「開機自動啟動」就不用問）')
        gl.addWidget(flow_row([self.b_chk, self.b_ins, self.b_ins_w])); gl.addWidget(self.c_auto)
        g2 = QGroupBox('現在在做什麼'); g2l = QVBoxLayout(g2); v.addWidget(g2)
        self.sum = shrinkable(QLabel(''), True); self.sum.setTextFormat(Qt.RichText); g2l.addWidget(self.sum)
        self.hot = _table(['磁碟', '熱區狀態', '說明', '外圈進度', '速度', '還要'], (60, 90, 360, 80, 90, 90)); self.hot.setMaximumHeight(180); g2l.addWidget(self.hot)
        self.notes = shrinkable(QLabel(''), True); self.notes.setObjectName('muted'); g2l.addWidget(self.notes)
        g3 = QGroupBox('⚖ 硬碟協調員（SortCut 和 HotZone 不同時把同一顆 HDD 頂在 100%）'); g3l = QVBoxLayout(g3); v.addWidget(g3)
        rule = QLabel('同一顆 HDD 兩邊都在大量讀寫、忙碌一直很高（15 秒以上）時只讓一邊做：你排的工作優先（HotZone 搬檔佇列、SortCut 轉檔／初剪）；'
                      '兩邊都是背景工作（預覽圖、讀影片資訊、熱區搬移、圖片分析）就輪流。被讓的那邊只是先不開新的，做到一半的照做完；不搶了 1 分鐘後兩邊照常。')
        shrinkable(rule, True); rule.setObjectName('muted'); g3l.addWidget(rule)
        self.c_arb = QCheckBox('開啟硬碟協調員'); self.sp_slice = QSpinBox(); self.sp_slice.setRange(1, 120); self.sp_slice.setSuffix(' 分鐘換一次')
        self.sp_busy = QSpinBox(); self.sp_busy.setRange(50, 100); self.sp_busy.setSuffix(' % 以上算忙'); self.sp_mbps = QSpinBox(); self.sp_mbps.setRange(1, 500); self.sp_mbps.setSuffix(' MB/s 以上算 HotZone 在用')
        g3l.addWidget(flow_row([self.c_arb, QLabel('背景工作輪流'), self.sp_slice, QLabel('忙碌'), self.sp_busy, QLabel('HotZone'), self.sp_mbps]))
        self.arb = _table(['硬碟', '現在讓給', '原因', '從什麼時候'], (70, 100, 520, 110)); self.arb.setMaximumHeight(150); g3l.addWidget(self.arb)
        self.arblog = QPlainTextEdit(); self.arblog.setReadOnly(True); self.arblog.setMaximumHeight(130); g3l.addWidget(self.arblog)
        v.addStretch(1)
        c = self.H().cfg() if self.H() else {}
        self.c_auto.setChecked(bool(c.get('auto'))); self.c_arb.setChecked(c.get('arb', True) is not False); self.sp_slice.setValue(int(c.get('slice_min') or 10))
        self.sp_busy.setValue(int(c.get('busy_pct') or 85)); self.sp_mbps.setValue(int(c.get('hz_mbps') or 3))
        self.c_auto.toggled.connect(lambda on: self.H() and self.H().set_cfg(auto=bool(on))); self.c_arb.toggled.connect(lambda on: self.H() and self.H().set_cfg(arb=bool(on)))
        self.sp_slice.valueChanged.connect(lambda x: self.H() and self.H().set_cfg(slice_min=int(x))); self.sp_busy.valueChanged.connect(lambda x: self.H() and self.H().set_cfg(busy_pct=int(x)))
        self.sp_mbps.valueChanged.connect(lambda x: self.H() and self.H().set_cfg(hz_mbps=int(x)))
        self.b_start.clicked.connect(self._start); self.b_stop.clicked.connect(self._stop); self.b_take.clicked.connect(self._take)
        self.b_open.clicked.connect(lambda: self.win.nav.setCurrentRow(21)); self.b_win.clicked.connect(lambda: self._do(lambda H: H.open_ui())); self.b_root.clicked.connect(self._pick_root)
        self.b_mig.clicked.connect(self._migrate); self.b_keep.clicked.connect(self._keep); self.b_diag.clicked.connect(self._diag)
        self.b_rep.clicked.connect(lambda: getattr(self, '_rep', '') and QDesktopServices.openUrl(QUrl.fromLocalFile(self._rep)))
        self.b_chk.clicked.connect(lambda: (self.envl.setText('檢查中…（5～20 秒）'), self._do(lambda H: (H.check_env(), {'ok': True, 'message': '檢查好了'})[1])))
        self.b_ins.clicked.connect(lambda: self._do(lambda H: H.install(False))); self.b_ins_w.clicked.connect(lambda: self._do(lambda H: H.install(True)))
        self.tm = QTimer(self); self.tm.timeout.connect(self.refresh); self.tm.start(2000)

    def H(self): return getattr(ENG, 'hz', None)

    def _do(self, fn):
        H = self.H()
        if H is None: self.win.msg('HotZone 模組沒有載入（LOG 有原因）'); return
        bg(lambda: fn(H), lambda r: (self.win.msg('🔥 ' + str((r or {}).get('message') or ''), 10000), self.refresh()))

    def _start(self):
        H = self.H()
        if H is None: return
        if not H.looks_like_root(H.root()) and QMessageBox.question(self, 'HotZone', f'還沒找到原本的 HotZone 資料夾（現在：{H.root()}）。\n\n'
                '直接啟動＝全新開始（原本的設定、搬檔佇列、熱區、索引都不會有）。\n要連原本的資料，請按「否」，再按「📁 HotZone 資料夾…」選原本的資料夾（或按「🩺 連線診斷」）。\n\n還是要全新開始？') != QMessageBox.Yes: return
        self._do(lambda H: H.start('手動'))

    def _stop(self):
        if QMessageBox.question(self, 'HotZone', '停止 HotZone 背景引擎？（搬檔佇列、熱區搬移會停；做到一半的下次啟動會接著做）') == QMessageBox.Yes: self._do(lambda H: H.stop('手動'))

    def _take(self):
        if QMessageBox.question(self, '接手原本的 HotZone', '讓原本的 HotZoneFM.exe 背景引擎結束，改由 SortCut 裡的 HotZone 接著跑？\n\n設定、搬檔佇列、熱區、索引、保管區都照舊（同一個資料夾）；'
                                '沒做完的搬檔會接著做。Windows 會問一次系統管理員權限。') == QMessageBox.Yes:
            self._do(lambda H: H.takeover())

    def _migrate(self):
        H = self.H()
        if H is None: return
        src = str(H.root()); dst = str(H.home())
        if QMessageBox.question(self, '整合進 SortCut', f'把 HotZone 的資料（設定、搬檔佇列、熱區、索引、保管區紀錄、LOG）\n從　{src}\n複製到　{dst}\n之後都用 SortCut 裡的？\n\n'
                                '• HotZone 背景引擎、HotZone 畫面（包括原本的 HotZoneFM.exe）會先關掉，複製好再啟動（Windows 會問一次系統管理員權限），做到一半的搬檔會接著做\n'
                                '• 被占用的檔案會等一下再試；真的複製不到的會列出來，已經複製好的下次不用重來\n'
                                '• 原本的資料夾不刪，留著當備份；之後請不要再開那裡的 HotZoneFM.exe' +
                                (f'\n\n⚠ {dst} 裡已經有一份 HotZone 資料，會先改名成 Data.舊_日期時間 留著（不會刪）' if (Path(dst) / 'Data').exists() and not (Path(dst) / '.vs_migrating').exists() else '')) != QMessageBox.Yes: return
        self.b_mig.setEnabled(False); self.b_keep.setEnabled(False); self.mig_l.setText('📦 整合中…'); self._mig_busy = True
        def prog(m): BUS.call.emit(lambda: self.mig_l.setText('📦 ' + esc_html(m))) if hasattr(BUS, 'call') else None
        before = self.win._hz_before
        def done(r):
            self._mig_busy = False; self.b_mig.setEnabled(True); self.b_keep.setEnabled(True); self.win.msg('🔥 ' + r['message'], 15000)
            self._rep = r.get('report') or ''; self.b_rep.setVisible(bool(self._rep))
            if r.get('ok'): QMessageBox.information(self, 'HotZone 整合', r['message'])
            else:
                F = r.get('fails') or []
                det = ('\n\n沒複製到的（前 15 個）：\n' + '\n'.join(f"• {x['file']}　← {x['why']}" for x in F[:15])) if F else ''
                QMessageBox.warning(self, 'HotZone 整合', r['message'] + det)
            self.refresh()
        bg(lambda: self.H().migrate(prog, before), done, err=lambda ex: (setattr(self, '_mig_busy', False), self.b_mig.setEnabled(True), self.b_keep.setEnabled(True), self.mig_l.setText(f'📦 整合時出錯：{esc_html(str(ex))}')))

    def _keep(self):
        H = self.H()
        if H is None: return
        if QMessageBox.question(self, 'HotZone', f'不整合，SortCut 直接用原本的 HotZone 資料夾？\n{H.root()}\n\n（之後想整合，按「📦 整合」還是可以）') != QMessageBox.Yes: return
        self._do(lambda H: H.keep_original())

    def _diag(self):
        H = self.H()
        if H is None: return
        self.diag.show(); self.diag.setText('🩺 檢查中…（5～30 秒）')
        def got(r):
            ic = lambda ok: "<span style='color:#45d483'>✔</span>" if ok else ("<span style='color:#ff6b6b'>✖</span>" if ok is False else '•')
            self.diag.setText('<b>🩺 連線診斷</b><br>' + '<br>'.join(ic(x['ok']) + ' ' + esc_html(x['text']) for x in r.get('items') or []))
        bg(H.diagnose, got, err=lambda ex: self.diag.setText(f'🩺 診斷出錯：{esc_html(str(ex))}'))

    def _use_root(self, d):
        H = self.H()
        if H is None or not d: return
        if QMessageBox.question(self, 'HotZone', f'改用這個 HotZone 資料夾？\n{d}\n\n（在跑的 HotZone 用的是別的資料夾的話，會自動重新啟動）') != QMessageBox.Yes: return
        self.win.msg('🔥 換 HotZone 資料夾中…', 8000)
        bg(lambda: H.set_root(d, self.win._hz_before), lambda r: (self.win.msg('🔥 ' + r['message'], 12000), self.refresh()))

    def _pick_root(self):
        d = QFileDialog.getExistingDirectory(self, '選 HotZone 的資料夾（有 HotZoneFM.exe 或 Data\\settings.json 的那個）')
        if not d: return
        H = self.H()
        if H is None: return
        if not H.looks_like_root(d) and QMessageBox.question(self, 'HotZone', f'{d}\n看起來不是 HotZone 的資料夾（沒有 HotZoneFM.exe 或 Data\\settings.json）。\n還是要用這個資料夾（全新開始）？') != QMessageBox.Yes: return
        before = self.win._hz_before
        self.win.msg('🔥 換 HotZone 資料夾中…', 8000)
        bg(lambda: H.set_root(d, before), lambda r: (self.win.msg('🔥 ' + r['message'], 12000), self.refresh()))

    def refresh(self):
        if not self.isVisible() or self.H() is None: return
        bg(self.H().status, self._got)

    def _got(self, st):
        e = st.get('env') or {}
        self.envl.setText(('✔ ' if e.get('ok') else '✖ ') + (f"Python {e.get('py')}（{e.get('exe')}）· Pillow {e.get('pil') or '沒有'} · numpy {e.get('numpy') or '沒有'} · OpenCV {e.get('cv2') or '沒有'} · 視窗用的 PySide6 {e.get('pyside6') or '沒有（用 Edge 視窗開）'}"
                                                         if e.get('py') else '還沒檢查（按「🔍 檢查環境」）') + ('　📦 安裝中…' if st.get('installing') else ''))
        if st['running']:
            who = 'SortCut 在跑' if st['ours'] else '原本的 HotZoneFM.exe 在跑（按「🔁 接手」改由 SortCut 跑）'
            self.h1.setText(f"🔥 HotZone V{st['ver']}　<span style='color:#45d483'>● 執行中</span>"); self.h1.setTextFormat(Qt.RichText)
            adm = '系統管理員 ✔' if st.get('admin') else "<span style='color:#f0ad4e'>不是系統管理員（熱區、MFT 索引不能用）</span>"
            self.h2.setText(f"{who} · 連接埠 {st['port']} · {adm}"
                            f"<br>資料夾：{esc_html(st['root'])}（設定、搬檔佇列、熱區、索引、保管區都讀這裡）" +
                            (f"<br><span style='color:#ff6b6b'>⚠ 在跑的 HotZone 用的是另一個資料夾：{esc_html(st.get('eng_root') or '')}（不是上面這個）→ 按「📁 HotZone 資料夾…」重選一次會自動換過去，或按「🩺 連線診斷」</span>" if st.get('other_root') else ''))
        else:
            self.h1.setText("🔥 HotZone　<span style='color:#7f8a99'>● 沒有在跑</span>"); self.h1.setTextFormat(Qt.RichText)
            self.h2.setText(f"資料夾：{esc_html(st['root'])}" + ('' if st.get('root_found') else '（還沒找到原本的 HotZone：按「📁 HotZone 資料夾…」選，或直接啟動＝全新開始）') +
                            ('<br>先按「🔍 檢查環境」，沒裝好就按「📦 安裝需要的套件」，再按「▶ 啟動背景引擎」' if not e.get('ok') else '<br>按「▶ 啟動背景引擎」（Windows 會問一次系統管理員權限）'))
        self.b_take.setVisible(bool(st['running'] and not st['ours'])); self.b_stop.setEnabled(bool(st['running'])); self.b_open.setEnabled(bool(st['running']))
        if getattr(self, '_mig_busy', False): pass
        elif st.get('migrating'):
            self.mig_l.setText('📦 ' + esc_html(st.get('mig_msg') or '整合中…') + '（從手機開始的）'); self.b_mig.setEnabled(False); self.b_keep.setEnabled(False)
        elif st.get('migrated'):
            mf = (st.get('cfg') or {}).get('migrated_from')
            self.b_mig.setEnabled(True); self.b_keep.setEnabled(True)
            self.mig_l.setText('✔ HotZone 的資料已經整合在 SortCut 裡：' + esc_html(st['home']) + (f'（原本的 {esc_html(mf)} 留著當備份）' if mf else '')); self.b_mig.hide(); self.b_keep.hide()
        elif st.get('keep_orig'):
            self.mig_l.setText(f"✔ 直接用原本的 HotZone 資料夾：<b>{esc_html(st['root'])}</b>（不整合；想整合還是可以按下面的按鈕）")
            self.b_mig.show(); self.b_mig.setEnabled(bool(st.get('root_found'))); self.b_keep.hide()
        else:
            part = "<br><span style='color:#f0ad4e'>上次整合沒做完：再按一次只補沒複製到的。</span>" if st.get('mig_partial') else ''
            self.mig_l.setText((f"目前用的是偵測到的 HotZone 資料夾：<b>{esc_html(st['root'])}</b><br>按下面的按鈕，把它整合進 SortCut（複製到 {esc_html(st['home'])}，之後都用那裡的；原本的留著當備份），"
                                "或者不整合、直接用原本的資料夾。連不上就按「🩺 連線診斷」。" if st.get('root_found') else
                                f"還沒找到原本的 HotZone 資料夾（現在：{esc_html(st['root'])}）。按「📁 HotZone 資料夾…」選有 HotZoneFM.exe 或 Data\\settings.json 的那個，或按「🩺 連線診斷」看找到了哪些。") + part)
            self.b_mig.show(); self.b_mig.setEnabled(bool(st.get('root_found'))); self.b_keep.setVisible(bool(st.get('root_found')))
        if not st.get('root_found') and not st.get('migrated') and not getattr(self, '_auto_diag', False) and self.H() is not None:
            self._auto_diag = True; bg(self.H().diagnose)                          # 還沒找到原本的：自動找一次，把找到的列出來
        ck = json.dumps([c.get('path') for c in st.get('cands') or []])
        if ck != self._cands_k:                                                   # 診斷找到的其他 HotZone 資料夾：一鍵改用
            self._cands_k = ck
            while self.cand_l.count():
                it = self.cand_l.takeAt(0); w = it.widget()
                if w is not None: w.deleteLater()
            if st.get('cands'):
                hd = QLabel('<b>電腦上找到的其他 HotZone 資料夾</b>（最後改動越新的，越可能是平常在用的）'); hd.setTextFormat(Qt.RichText); hd.setStyleSheet('background:transparent'); self.cand_l.addWidget(hd)
            for c in st.get('cands') or []:
                lb = shrinkable(QLabel(f"{c.get('path')}　·　佇列 {c.get('queue', 0)} 筆　·　最後改動 " + (time.strftime('%Y-%m-%d %H:%M', time.localtime(c['t'])) if c.get('t') else '—') + ('　·　有 HotZoneFM.exe' if c.get('exe') else '')), True)
                lb.setStyleSheet('background:transparent'); bt = QPushButton('用這個'); bt.clicked.connect(lambda _=False, p=c.get('path'): self._use_root(p))
                self.cand_l.addWidget(flow_row([bt, lb]))
        q = st.get('queue') or {}; ix = st.get('index') or {}
        self.sum.setText((f"搬檔佇列：在跑 <b>{q.get('running', 0)}</b> · 排隊 {q.get('queued', 0)} · 等待 {q.get('waiting', 0)}" + (f" · {fmt_b(q.get('speed') or 0)}/s" if q.get('speed') else '') +
                          (' · <b style="color:#f0ad4e">全部暫停中</b>' if q.get('paused_all') else '') + ('　｜　熱區：<b style="color:#f0ad4e">暫停中</b>' if st.get('hot_paused') else '') +
                          (f"　｜　索引：{esc_html(str(ix.get('msg') or ix.get('state') or ''))[:80]}" if isinstance(ix, dict) and (ix.get('msg') or ix.get('state')) else ''))
                         if st['running'] else '—')
        H = st.get('hot') or []; self.hot.setRowCount(len(H))
        for i, h in enumerate(H):
            for j, val in enumerate((h.get('letter') or '', h.get('state') or '', h.get('msg') or '', f"{h.get('pct_in') or 0:.0f}%" if h.get('pct_in') is not None else '',
                                     (fmt_b(h.get('rate') or 0) + '/s') if h.get('rate') else '', eta_txt(h.get('eta')) if h.get('eta') else '')):
                self.hot.setItem(i, j, _ti(val))
        self.notes.setText('　'.join('⚠ ' + str(n.get('text') or '') for n in (st.get('notices') or [])[-5:]))
        A = st.get('arb') or []; self.arb.setRowCount(len(A))
        for i, a in enumerate(A):
            for j, val in enumerate((a['disk'], 'SortCut' if a['owner'] == 'vs' else 'HotZone', a['why'], time.strftime('%H:%M:%S', time.localtime(a['since'])))): self.arb.setItem(i, j, _ti(val))
        txt = '\n'.join(time.strftime('%m-%d %H:%M:%S', time.localtime(x['t'])) + f"　{x['disk']}　→ {x['why']}" for x in reversed(st.get('arb_log') or [])) or '（還沒有搶過硬碟）'
        if self.arblog.toPlainText() != txt: self.arblog.setPlainText(txt)


class ReportChart(QWidget):
    """V0.2.35 最近 14 天每天分級幾部（S／A／E／F 疊起來）."""
    def __init__(self, days):
        super().__init__(); self.days = days; self.setMinimumHeight(220)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); W_, H_ = self.width(), self.height(); L = self.days or []
        mx = max([x['graded'] for x in L] + [1]); bw = (W_ - 40) / max(1, len(L)); base = H_ - 28; f = QFont(); f.setPixelSize(10); p.setFont(f)
        for i, x in enumerate(L):
            X = 30 + i * bw; y = base
            for g in ('F', 'E', 'A', 'S'):
                h = (x[g] / mx) * (base - 20)
                if h > 0: p.fillRect(QRectF(X + 2, y - h, bw - 4, h), QColor(GC[g])); y -= h
            p.setPen(TC('subtext')); p.drawText(QRectF(X, base + 4, bw, 14), Qt.AlignCenter, x['d'][5:])
            if x['graded']: p.setPen(TC('text_strong')); p.drawText(QRectF(X, y - 16, bw, 14), Qt.AlignCenter, str(x['graded']))
            if x.get('up') and lab_cfg().get('copy_to'): p.setPen(QColor('#4dd68a')); p.drawText(QRectF(X, base + 16, bw, 12), Qt.AlignCenter, f"↑{x['up']}")   # V0.3.77 📤 那天上傳幾部
        p.end()


class HeatMap(QWidget):
    """V0.4.09 🗓 最近 12 週每天分級幾部（像 GitHub 的格子：一欄一週，越綠越多）."""
    def __init__(self, rows):
        super().__init__(); self.R = list(rows or []); self.setMinimumHeight(118); self.setMouseTracking(True)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); mx = max([x['n'] for x in self.R] + [1]); c = 12; g = 3; x0 = 34
        f = QFont(); f.setPixelSize(9); p.setFont(f); p.setPen(TC('subtext'))
        for i, t in ((0, '一'), (2, '三'), (4, '五'), (6, '日')): p.drawText(QRectF(4, 4 + i * (c + g), 26, c), Qt.AlignRight | Qt.AlignVCenter, t)
        if not self.R: p.end(); return
        try: wd0 = time.strptime(self.R[0]['d'], '%Y-%m-%d').tm_wday
        except Exception: wd0 = 0
        for i, x in enumerate(self.R):
            k = i + wd0; col, row = k // 7, k % 7; r_ = QRectF(x0 + col * (c + g), 4 + row * (c + g), c, c)
            v = x['n'] / mx; q = QColor('#2a3140') if not x['n'] else QColor.fromHsvF(0.38, 0.35 + 0.6 * v, 0.35 + 0.6 * v)
            p.setPen(Qt.NoPen); p.setBrush(q); p.drawRoundedRect(r_, 2, 2)
            if x.get('up') and lab_cfg().get('copy_to'): p.setBrush(QColor('#4dd68a')); p.drawEllipse(QRectF(r_.right() - 4, r_.top() + 1, 3, 3))
            if x.get('pub') and lab_cfg().get('copy_to'): p.setBrush(QColor('#3fd0c9')); p.drawEllipse(QRectF(r_.left() + 1, r_.bottom() - 4, 3, 3))   # V0.4.43 左下＝那天有發佈
        p.setPen(TC('subtext')); p.drawText(QRectF(x0, 4 + 7 * (c + g), 400, 12), Qt.AlignLeft, '最近 12 週每天分級幾部（越綠越多；右上綠點＝有複製上傳、左下藍綠點＝有發佈）'); p.end()

    def mouseMoveEvent(self, e):
        try:
            c, g, x0 = 12, 3, 34; wd0 = time.strptime(self.R[0]['d'], '%Y-%m-%d').tm_wday
            col = int((e.position().x() - x0) // (c + g)); row = int((e.position().y() - 4) // (c + g)); i = col * 7 + row - wd0
            if 0 <= row < 7 and 0 <= i < len(self.R): x = self.R[i]; self.setToolTip(f"{x['d']}：分級 {x['n']} 部" + (f"、上傳 {x['up']} 部" if x.get('up') else '') + (f"、發佈 {x['pub']} 部" if x.get('pub') else ''))
        except Exception: pass


class HourChart(QWidget):
    """V0.2.50 0～23 點每個鐘頭分級幾部."""
    def __init__(self, H):
        super().__init__(); self.H = list(H or [0] * 24); self.setMinimumHeight(70)

    def paintEvent(self, e):
        p = QPainter(self); W_, H_ = self.width(), self.height(); mx = max(self.H + [1]); bw = W_ / 24.0; base = H_ - 14; f = QFont(); f.setPixelSize(9); p.setFont(f)
        for i, n in enumerate(self.H):
            h = n / mx * (base - 4)
            if h > 0: p.fillRect(QRectF(i * bw + 1, base - h, bw - 2, h), QColor('#4dc9ff'))
            if i % 3 == 0: p.setPen(TC('subtext')); p.drawText(QRectF(i * bw, base + 1, bw * 2, 12), Qt.AlignLeft, str(i))
        p.end()


class SpaceBar(QWidget):
    """V0.2.43 一顆硬碟一條：S A E F 未分級 其他檔案 剩下."""
    def __init__(self, o):
        super().__init__(); self.o = o; self.setMinimumHeight(30)

    def paintEvent(self, e):
        p = QPainter(self); o = self.o; W_, H_ = self.width(), self.height(); tot = o.get('total') or (o['lib'] or 1)
        p.fillRect(QRectF(0, 4, W_, H_ - 8), TC('border')); x = 0.0
        for k, c in (('S', GC['S']), ('A', GC['A']), ('E', GC['E']), ('F', GC['F']), ('', '#9aa0a6'), ('other', '#5c6168')):
            w_ = W_ * (o.get(k) or 0) / tot
            if w_ > 0: p.fillRect(QRectF(x, 4, w_, H_ - 8), QColor(c)); x += w_
        p.end()


class CmdPalette(QDialog):
    """V0.2.30 ⌘ 指令面板（Ctrl+K）：頁面、動作、資料夾、影片，打字就找到，Enter 去."""
    def __init__(self, win):
        super().__init__(win, Qt.Dialog | Qt.FramelessWindowHint); self.win = win; self.setModal(True); self.resize(640, 460); self.items = []; self.seq = 0
        self.setStyleSheet(f'QDialog{{background:{THEME["panel"]};border:1px solid {THEME["viewer_line"]};border-radius:12px}}')
        v = QVBoxLayout(self); v.setContentsMargins(12, 12, 12, 12)
        self.q = QLineEdit(); self.q.setPlaceholderText('打字找：頁面、動作、資料夾、影片（↑↓ 選、Enter 去、Esc 關）'); self.q.setStyleSheet('font-size:16px;padding:8px'); v.addWidget(self.q)
        self.lst = QListWidget(); v.addWidget(self.lst, 1); self.hint = QLabel(''); self.hint.setObjectName('muted'); v.addWidget(self.hint)
        self.q.textChanged.connect(self._changed); self.q.returnPressed.connect(self._go); self.lst.itemActivated.connect(lambda _it: self._go())
        self.q.installEventFilter(self); self._fill('')

    def eventFilter(self, o, e):
        try:
            if e.type() == QEvent.KeyPress and e.key() in (Qt.Key_Down, Qt.Key_Up):
                r = self.lst.currentRow() + (1 if e.key() == Qt.Key_Down else -1); r = max(0, min(self.lst.count() - 1, r)); self.lst.setCurrentRow(r); return True
        except Exception: pass
        return False

    def _actions(self):
        W_ = self.win; A = []
        for pg, (ic, nm) in NavList.NAMES.items(): A.append((f'{ic} 到「{nm}」', 'page', pg))
        A += [('🔄 重新掃描影片庫', 'act', lambda: W_.msg('開始掃描' if ENG.scan() else '已經在掃描')), ('🏠 回到封面', 'act', W_.show_cover),
              ('⏸ 背景工作全部暫停', 'act', lambda: (ENG.bg_all(True), W_.msg('背景工作全部暫停'))), ('▶ 背景工作全部繼續', 'act', lambda: (ENG.bg_all(False), W_.msg('背景工作全部繼續（照順序慢慢加）'))),
              ('💾 現在寫到各硬碟', 'act', lambda: bg(lambda: ENG.pack_export_due(force=True, why='（指令面板）'), lambda r_: W_.msg('💾 已寫到：' + ('、'.join(r_) or '都是最新的')))),
              ('🌙 縮到背景', 'act', W_.to_tray), ('◐ 深色／淺色', 'act', lambda: W_.set_theme('light' if THEME_MODE['mode'] == 'dark' else 'dark')),
              ('📥 匯入舊 FileCompare 資料', 'act', lambda: W_.fcp.import_old()), ('🧭 合併導覽（FileCompare 怎麼用）', 'act', lambda: W_.merge_tour(True)),   # V0.5.46
              ('📊 效能浮窗 開／關', 'act', lambda: W_.b_perf.toggle()), ('⌨ 快捷鍵一覽（Ctrl+/）', 'act', W_.keys_dlg), ('💽 硬碟空間地圖', 'act', W_.space_dlg), ('🧹 找空資料夾', 'act', W_.empty_dlg), ('🖥 硬碟在哪台電腦', 'act', W_.pcs_dlg), ('⚡ 規則分級', 'act', W_.rule_dlg), ('🆕 新功能導覽', 'act', W_.tour_dlg), ('📂 各資料夾分級進度', 'act', W_.progress_dlg)]
        try:                                                                    # V0.4.14 📌 釘選的工具排最前面
            NM_ = {k: n for k, n, _d, _v in NEW_LABS}
            for k in reversed(ENG.cfg.get('pin_tools') or []):
                if k in NM_: A.insert(0, (f'📌 {NM_[k]}', 'act', lambda k=k: W_.toolp.use(k)))
        except Exception: pass
        L_ = lab_cfg()                                                          # V0.4.51 新工具也能從指令面板叫
        for k_, t_, f_ in (('copy_to', '📋 上傳看板（Ctrl+Shift+U）', lambda: W_.up_board_dlg()), ('copy_to', '🧺 清理上傳資料夾的舊檔', lambda: W_.up_old_dlg()), ('bookmarks', '🔖 所有時間書籤', lambda: (W_.enter(0), W_.browse.bm_all_dlg())),
                           ('unplug_check', '🔌 拔硬碟前看一下', lambda: W_.unplug_dlg()), ('web_devices', '📱 登入過的手機', lambda: W_.devices_dlg()), ('sprint', '⏱ 分級衝刺', lambda: W_.sprint_dlg()),
                           ('weekly', '📆 每週回顧', lambda: W_.week_dlg()), ('report', '🧾 複製今天的日報', lambda: (QApplication.clipboard().setText(ENG.day_text()), W_.msg('🧾 日報複製好了')))):
            if L_.get(k_): A.append((t_, 'act', f_))
        if lab_cfg().get('random_pick'): A.append(('🎲 隨便抽一部還沒分級的', 'act', lambda: (W_.enter(0), W_.browse.random_pick())))   # V0.3.84
        if lab_cfg().get('views'):                                              # V0.2.40 ⭐ 常用篩選也能從指令面板叫
            try: A += [(f'⭐ {v["name"]}', 'act', lambda v=v: (W_.enter(0), W_.browse.use_view(v))) for v in ENG.views()]
            except Exception: pass
        try:
            LF_ = ENG.last_file() if lab_cfg().get('recent_dirs') else None
            if LF_: A.insert(0, (f"⏯ 繼續看：{LF_['name']}", 'act', lambda LF_=LF_: (W_.enter(0), W_.browse.goto_file(LF_['id']))))   # V0.3.39
        except Exception: pass
        if lab_cfg().get('recent_dirs'):                                        # V0.2.57 🕘 最近資料夾也能從指令面板叫
            try: A += [(f'🕘 {Path(f).name or f}　{f}', 'act', lambda f=f: (W_.enter(0), W_.browse._sel_folder(f), W_.browse.load_list())) for f in ENG.recent_list()[:10]]
            except Exception: pass
        return A

    def _fill(self, q):
        q_ = q.strip().lower(); W_ = [w for w in q_.split() if w]
        def hit(t): return all(w in t.lower() for w in W_)
        self.items = [x for x in self._actions() if hit(x[0])][:12]
        self._render()
        if len(q_) >= 1:
            self.seq += 1; sq = self.seq
            bg(lambda: ENG.quick_find(q_), lambda r: self._found(sq, r))

    def _found(self, sq, r):
        if sq != self.seq: return
        for d in r.get('folders') or []: self.items.append((f'📁 {d["folder"]}　（{d["n"]:,} 部）', 'folder', d['folder']))
        for f in r.get('files') or []: self.items.append((f'🎬 {f["name"]}　{fmt_b(f["size"])}' + (f'　{f["grade"]}' if f.get('grade') else '') + f'　— {f["folder"]}', 'file', f['id']))
        self._render()

    def _render(self):
        cur = self.lst.currentRow(); self.lst.clear()
        for t, _k, _v in self.items: self.lst.addItem(t)
        if self.lst.count(): self.lst.setCurrentRow(max(0, min(cur, self.lst.count() - 1)))
        self.hint.setText(f'{len(self.items)} 個結果' if self.q.text().strip() else '常用：打「掃描」「暫停」「封面」、資料夾名、檔名的一部分')

    def _changed(self, t):
        self._fill(t)

    def _go(self):
        r = self.lst.currentRow()
        if not (0 <= r < len(self.items)): return
        t, k, v = self.items[r]; self.accept(); W_ = self.win
        try:
            ENG.log.w(f'⌘ 指令面板：{t[:80]}')
            if k == 'page': W_.enter(int(v))
            elif k == 'act': v()
            elif k == 'file': W_.enter(0); W_.browse.goto_file(int(v))
            elif k == 'folder':
                W_.enter(0); B = W_.browse; B.folder = str(v); ENG.th_focus = B.folder; B.load_list(); W_.msg(f'📁 {v}')
        except Exception: ENG.log.err('指令面板')


class LabPage(QWidget):
    """🧪 實驗工作區：新的好用功能先放這裡給你試；用得順再正式加進去."""
    def __init__(self, win):
        super().__init__(); self.win = win; self.dupes = []
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); sa = QScrollArea(); sa.setWidgetResizable(True); outer.addWidget(sa)
        body = QWidget(); sa.setWidget(body); v = QVBoxLayout(body); v.setContentsMargins(8, 8, 8, 8)
        t = QLabel('🧪 實驗工作區'); t.setObjectName('title'); v.addWidget(t)
        n = QLabel('新功能先放在這裡給你試用。覺得好用就跟我說，我再正式加進主畫面；不好用也跟我說，我改或拿掉。'); n.setObjectName('muted'); n.setWordWrap(True); v.addWidget(n)
        g = QGroupBox('📋 一覽（現在哪些開著）'); gl = QVBoxLayout(g); v.addWidget(g)
        self.summ = QLabel(''); self.summ.setTextFormat(Qt.RichText); self.summ.setWordWrap(True); gl.addWidget(self.summ)
        sr = QHBoxLayout(); gl.addLayout(sr); off = QPushButton('全部關閉（回到原本的樣子）'); sr.addWidget(off); sr.addStretch(1)
        off.clicked.connect(self.all_off)
        g = QGroupBox(f'🆕 新功能（V0.2.30 起・每一版加一個・共 {len(NEW_LABS)} 個・預設都關著，想試就打勾）'); gl0 = QVBoxLayout(g); v.addWidget(g); self.new_cb = {}; self.new_box = {}
        rs_ = QHBoxLayout(); b_sx = QPushButton('🔄 新功能設定存到硬碟'); b_sx.setToolTip('開關、自動規則、常用篩選、搜尋紀錄存到每顆接著的硬碟，另一台電腦接上後按「📥 從硬碟套用」就一樣（上傳資料夾、讓路程式這些跟電腦有關的不帶）')
        b_si = QPushButton('📥 從硬碟套用另一台的設定'); rs_.addWidget(b_sx); rs_.addWidget(b_si); rs_.addStretch(1); gl0.addLayout(rs_)   # V0.3.29 兩台電腦同步
        b_sx.clicked.connect(lambda: bg(ENG.share_export, lambda r_: self.win.msg('🔄 存到：' + ('、'.join(f'{x}:' for x in r_) or '（沒有有紀錄包的硬碟）'))))
        b_si.clicked.connect(self._share_import)
        b_chk_ = QPushButton('🩺 新功能自我檢查'); b_chk_.setToolTip('檢查新功能用到的資料庫欄位、設定、上傳資料夾…有沒有問題'); b_chk_.clicked.connect(self._new_check); gl0.addWidget(b_chk_)   # V0.2.73
        fr_ = QHBoxLayout(); gl0.addLayout(fr_); self.new_q = QLineEdit(); self.new_q.setPlaceholderText('🔎 找新功能（名字或說明）'); self.new_q.setClearButtonEnabled(True)   # V0.2.46
        self.new_off = QCheckBox('只看還沒打開的'); b_on_ = QPushButton('全部打開'); b_on_.setToolTip('把下面列出來的新功能一次打勾（之後可以一個一個關）')
        fr_.addWidget(self.new_q, 1); fr_.addWidget(self.new_off); fr_.addWidget(b_on_)
        seen_ = str(ENG.cfg.get('lab_seen') or '0.2.29'); vt_ = lambda x: tuple(int(p_) for p_ in re.findall(r'\d+', str(x))[:3])
        for k_, nm_, desc_, ver_ in sorted(NEW_LABS, key=lambda x: vt_(x[3]), reverse=True):                     # 最新的在最上面
            box_ = QWidget(); gl = QVBoxLayout(box_); gl.setContentsMargins(0, 2, 0, 2); gl0.addWidget(box_); self.new_box[k_] = (box_, (nm_ + ' ' + desc_).lower())
            cb_ = QCheckBox(f'{nm_}　V{ver_}' + ('　🔴 NEW' if vt_(ver_) > vt_(seen_) else '')); cb_.setChecked(bool((ENG.cfg.get('lab') or {}).get(k_))); gl.addWidget(cb_)
            d_ = QLabel(desc_); d_.setObjectName('muted'); d_.setWordWrap(True); d_.setContentsMargins(24, 0, 0, 4); gl.addWidget(d_); self.new_cb[k_] = cb_
            extra_ = getattr(self, f'_new_{k_}', None)
            if extra_ is not None:
                try: w_ = extra_(); w_.setContentsMargins(24, 0, 0, 6); gl.addWidget(w_)
                except Exception: ENG.log.err(f'實驗工作區：{k_}')
            cb_.toggled.connect(lambda on, k_=k_: (ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, **{k_: bool(on)})), self.refresh_summary(), self.win.apply_new_labs(), self.win.msg(f'🧪 {k_}：{"開" if on else "關"}')))
        self.new_q.textChanged.connect(lambda _t: self._new_filter()); self.new_off.toggled.connect(lambda _o: self._new_filter())
        b_on_.clicked.connect(self._new_all_on)
        try: ENG.cfg.set('lab_seen', APP_VERSION)
        except Exception: pass
        g = QGroupBox('🚀 背景加速（試用中・兩種方式，可以只開一種或都開）'); gl = QGridLayout(g); v.addWidget(g); L = ENG.cfg.get('lab') or {}
        self.bi = QCheckBox('A. 電腦閒置時加速：超過'); self.bim = QComboBox()
        for nm_, m_ in (('5 分鐘', 5), ('10 分鐘', 10), ('20 分鐘', 20), ('30 分鐘', 30)): self.bim.addItem(nm_, m_)
        self.bn = QCheckBox('B. 夜間時段加速：從'); self.bnf = QSpinBox(); self.bnf.setRange(0, 23); self.bnf.setSuffix(' 點'); self.bnt = QSpinBox(); self.bnt.setRange(0, 23); self.bnt.setSuffix(' 點')
        self.bi.setChecked(bool(L.get('boost_idle'))); self.bim.setCurrentIndex(max(0, self.bim.findData(int(L.get('boost_idle_min') or 10))))
        self.bn.setChecked(bool(L.get('boost_night'))); self.bnf.setValue(int(L.get('night_from', 23))); self.bnt.setValue(int(L.get('night_to', 8)))
        gl.addWidget(self.bi, 0, 0); gl.addWidget(self.bim, 0, 1); gl.addWidget(QLabel('沒動滑鼠鍵盤，就加速'), 0, 2, 1, 3)
        gl.addWidget(self.bn, 1, 0); gl.addWidget(self.bnf, 1, 1); gl.addWidget(QLabel('到'), 1, 2); gl.addWidget(self.bnt, 1, 3); gl.addWidget(QLabel('加速（不管有沒有在用電腦）'), 1, 4)
        nb = QLabel('加速＝預覽圖同時做的部數加倍、優先權從「最低」改成「低」，讀影片資訊也加倍；同一顆 HDD 還是一次一部（不會來回跳）。'
                    'A 適合「人走開就全力做」，B 適合「固定晚上睡覺時做」。現在有沒有在加速，後台和封面會顯示 🚀。'); nb.setObjectName('muted'); nb.setWordWrap(True); gl.addWidget(nb, 2, 0, 1, 5)
        def save_boost():
            ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, boost_idle=self.bi.isChecked(), boost_idle_min=int(self.bim.currentData() or 10), boost_night=self.bn.isChecked(),
                                    night_from=int(self.bnf.value()), night_to=int(self.bnt.value())))
        for w_ in (self.bi, self.bn): w_.toggled.connect(lambda _o: save_boost())
        self.bim.currentIndexChanged.connect(lambda _i: save_boost()); self.bnf.valueChanged.connect(lambda _x: save_boost()); self.bnt.valueChanged.connect(lambda _x: save_boost())
        g = QGroupBox('👀 預覽小幫手（試用中・兩個功能可以分開開關）'); gl = QGridLayout(g); v.addWidget(g)
        self.cs_ = QCheckBox('卡片滑過預覽：滑鼠在卡片上左右移動，縮圖跟著換成影片前段／中段／後段的畫面（左上顯示時間、下緣一條位置條）')
        self.gz = QCheckBox('格子放大預覽：滑鼠停在預覽格上一下，旁邊跳出放大的那一格；大小'); self.gzw = QComboBox()
        for nm_, w_ in (('360', 360), ('480', 480), ('640', 640)): self.gzw.addItem(nm_ + ' 像素寬', w_)
        L2 = ENG.cfg.get('lab') or {}; self.cs_.setChecked(bool(L2.get('card_scrub'))); self.gz.setChecked(bool(L2.get('grid_zoom'))); self.gzw.setCurrentIndex(max(0, self.gzw.findData(int(L2.get('grid_zoom_w') or 480))))
        gl.addWidget(self.cs_, 0, 0, 1, 2); gl.addWidget(self.gz, 1, 0); gl.addWidget(self.gzw, 1, 1)
        nb2 = QLabel('格子放大用的是已經做好的預覽圖（每格約 120 像素高），放大會有點糊，但不用重做、不佔硬碟。開了放大預覽，格子原本的文字提示會改成不顯示。'); nb2.setObjectName('muted'); nb2.setWordWrap(True); gl.addWidget(nb2, 2, 0, 1, 2)
        def save_pv():
            ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, card_scrub=self.cs_.isChecked(), grid_zoom=self.gz.isChecked(), grid_zoom_w=int(self.gzw.currentData() or 480)))
        self.cs_.toggled.connect(lambda _o: save_pv()); self.gz.toggled.connect(lambda _o: save_pv()); self.gzw.currentIndexChanged.connect(lambda _i: save_pv())
        g = QGroupBox('✂ 剪輯小幫手（試用中・兩個功能可以分開開關）'); gl = QVBoxLayout(g); v.addWidget(g); L3 = ENG.cfg.get('lab') or {}
        self.ic = QCheckBox('反過來剪：輸出初剪的視窗多一個勾選「刪掉選的片段，保留其他部分」（剪掉廣告、片頭、不要的段落：只選不要的就好）')
        self.gk = QCheckBox('鍵盤操作預覽格子：先點一下格子，之後 方向鍵＝移動、空白鍵＝選／取消、Shift＋方向鍵＝連續選、Enter＝從這格播放、Home／End＝頭尾')
        self.ic.setChecked(bool(L3.get('inverse_cut'))); self.gk.setChecked(bool(L3.get('grid_keys'))); gl.addWidget(self.ic); gl.addWidget(self.gk)
        self.ic.toggled.connect(lambda on: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, inverse_cut=bool(on))))
        self.gk.toggled.connect(lambda on: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, grid_keys=bool(on))))
        g = QGroupBox('🔎 進階搜尋語法（試用中）'); gl = QVBoxLayout(g); v.addWidget(g)
        self.ss = QCheckBox('檔案總管的搜尋框可以打條件：>1h <10m（長度）、>2gb <500mb（大小）、4k 1440p 1080p 720p sd（解析度）、hevc h264（編碼）、ext:avi、g:S g:SA g:none（分級）、已上傳／沒上傳、★、沒看過、note:字（備註）、-字（不要有）'); self.ss.setChecked(bool((ENG.cfg.get('lab') or {}).get('smart_search')))
        gl.addWidget(self.ss); n3 = QLabel('可以跟檔名混著打，空格隔開＝都要符合，例如「旅行 >30m 1080p」＝檔名有旅行、超過 30 分鐘、1080p。沒開的時候照原本只找檔名。'); n3.setObjectName('muted'); n3.setWordWrap(True); gl.addWidget(n3)
        self.ss.toggled.connect(lambda on: (ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, smart_search=bool(on))), self.win.browse.b_syn.setVisible(bool(on)), self.win.browse.q.setPlaceholderText('搜尋：檔名 或 >1h <10m >2gb 4k hevc g:S 沒上傳 -字' if on else '搜尋檔名')))
        g = QGroupBox('🩺 影片庫健康檢查（試用中）'); gl = QVBoxLayout(g); v.addWidget(g, 1)
        hr = QHBoxLayout(); gl.addLayout(hr); hb = QPushButton('🩺 開始檢查'); self.hk = QComboBox(); self.hl = QLabel('找出預覽圖失敗、讀不到、沒畫面、超短、超小、讀不到長度的影片'); self.hl.setObjectName('muted')
        hr.addWidget(hb); hr.addWidget(self.hk); hr.addWidget(self.hl, 1)
        self.ht = QTableWidget(0, 4); self.ht.setHorizontalHeaderLabels(['檔名', '大小', '長度', '原因／資料夾']); self.ht.verticalHeader().setVisible(False)
        self.ht.setEditTriggers(QAbstractItemView.NoEditTriggers); self.ht.setSelectionBehavior(QAbstractItemView.SelectRows); self.ht.horizontalHeader().setStretchLastSection(True); self.ht.setMinimumHeight(160)
        for i_, w_ in enumerate((300, 90, 80)): self.ht.setColumnWidth(i_, w_)
        gl.addWidget(self.ht, 1); self.health = {}
        hb.clicked.connect(lambda: (self.hl.setText('檢查中…'), bg(ENG.health, self._health))); self.hk.currentIndexChanged.connect(lambda _i: self._health_fill())
        self.ht.itemDoubleClicked.connect(lambda _it: self._health_go())
        g = QGroupBox('🧹 清理用不到的預覽圖（試用中）'); gl = QHBoxLayout(g); v.addWidget(g)
        cb1 = QPushButton('🔍 算算看'); self.cb2 = QPushButton('🧹 清理'); self.cb2.setEnabled(False); self.cl = QLabel('已經刪掉、搬走、移出影片庫的影片，它們的預覽圖還佔著空間；先算能省多少，你按了才清'); self.cl.setObjectName('muted'); self.cl.setWordWrap(True)
        gl.addWidget(cb1); gl.addWidget(self.cb2); gl.addWidget(self.cl, 1); self.orph = None
        cb1.clicked.connect(lambda: (self.cl.setText('計算中…'), bg(ENG.thumbs_orphans, self._orph)))
        self.cb2.clicked.connect(self._orph_clean)
        g = QGroupBox('🎬 播放器小幫手（試用中・兩個功能可以分開開關）'); gl = QVBoxLayout(g); v.addWidget(g); L4 = ENG.cfg.get('lab') or {}
        self.rs = QCheckBox('續播：關掉播放視窗時記住看到哪裡，下次打開同一部從那裡繼續（開頭、最後 10 秒內不記；Home 回到開頭）')
        self.pg_ = QCheckBox('播放中直接分級：1／2／3／4＝S／A／E／F、0＝取消分級（不用關掉播放視窗；清單、卡片、分級標籤馬上更新）')
        self.rs.setChecked(bool(L4.get('resume'))); self.pg_.setChecked(bool(L4.get('player_grade'))); gl.addWidget(self.rs); gl.addWidget(self.pg_)
        self.rs.toggled.connect(lambda on: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, resume=bool(on))))
        self.pg_.toggled.connect(lambda on: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, player_grade=bool(on))))
        g = QGroupBox('🔬 轉檔後抽查畫質（試用中）'); gl = QVBoxLayout(g); v.addWidget(g)
        self.cq = QCheckBox('每部轉好後，從中間抽 5 秒和原檔比畫面（SSIM：1.00＝一模一樣、0.98 以上肉眼看不出差別），結果顯示在轉檔頁的狀態；低於 0.90 的就算你設定了「原檔搬走／丟回收筒」也先留著原檔')
        self.cq.setChecked(bool((ENG.cfg.get('lab') or {}).get('conv_ssim'))); gl.addWidget(self.cq)
        self.cq.toggled.connect(lambda on: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, conv_ssim=bool(on))))
        g = QGroupBox('📊 資料夾樹顯示分級進度（試用中）'); gl = QVBoxLayout(g); v.addWidget(g)
        self.tg = QCheckBox('左邊資料夾樹每個資料夾後面多一條 ▰▰▰▱▱ 60%：這個資料夾（含子資料夾）分級好了多少；全部分好顯示 ✅，一眼看出哪裡還沒整理')
        self.tg.setChecked(bool((ENG.cfg.get('lab') or {}).get('tree_grade'))); gl.addWidget(self.tg)
        self.tg.toggled.connect(lambda on: (ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, tree_grade=bool(on))), self.win.browse.load_tree()))
        g = QGroupBox('🎯 每日整理目標（試用中）'); gl = QVBoxLayout(g); v.addWidget(g)
        r_g = QHBoxLayout(); gl.addLayout(r_g); self.dg = QCheckBox('上方顯示「🎯 今天分級 37／100 ▰▰▱▱▱」，達標時說一聲'); self.dgn = QSpinBox(); self.dgn.setRange(5, 5000); self.dgn.setSingleStep(10)
        self.dgn.setValue(int(ENG.cfg.get('daily_goal_n') or 100)); self.dgn.setSuffix(' 部／天'); r_g.addWidget(self.dg); r_g.addWidget(QLabel('目標：')); r_g.addWidget(self.dgn); r_g.addStretch(1)
        self.dg.setChecked(bool((ENG.cfg.get('lab') or {}).get('daily_goal')))
        self.dg.toggled.connect(lambda on: (ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, daily_goal=bool(on))), self.win._status()))
        self.dgn.valueChanged.connect(lambda n_: (ENG.cfg.set('daily_goal_n', int(n_)), self.win._status()))
        g = QGroupBox('🎯 預覽圖精準模式（試用中）'); gl = QVBoxLayout(g); v.addWidget(g)
        self.tp = QCheckBox('之後新做的預覽圖都用精準模式：每一張都是那一秒的真實畫面（有些影片關鍵格很少，快速模式會連續好幾張一樣），但比較慢、比較吃 CPU')
        self.tp.setChecked(bool((ENG.cfg.get('lab') or {}).get('thumb_precise'))); gl.addWidget(self.tp)
        n5 = QLabel('只想重做某幾部：在檔案總管選那幾部 → 右鍵「🔁 重做預覽圖（精準）」。'); n5.setObjectName('muted'); n5.setWordWrap(True); gl.addWidget(n5)
        self.tp.toggled.connect(lambda on: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, thumb_precise=bool(on))))
        g = QGroupBox('⛶ 專注分級模式（試用中）'); gl = QVBoxLayout(g); v.addWidget(g)
        self.fm = QCheckBox('檔案總管右邊多一顆「⛶ 專注」：收起左邊清單和選單，預覽格子佔滿畫面；上面有 上一部／下一部 和大大的 S／A／E／F；PgUp／PgDn 換部、Esc 離開（可以搭配「分級後自動跳下一部」）')
        self.fm.setChecked(bool((ENG.cfg.get('lab') or {}).get('focus_mode'))); gl.addWidget(self.fm)
        self.fm.toggled.connect(lambda on: (ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, focus_mode=bool(on))), self.win.browse.b_focus.setVisible(bool(on)), self.win.browse.set_focus_mode(False) if not on and self.win.browse.focus_on else None))
        g = QGroupBox('🔤 亂碼檔名解碼改名（試用中）'); gl = QVBoxLayout(g); v.addWidget(g)
        rr_ = QHBoxLayout(); gl.addLayout(rr_); rb1 = QPushButton('🔍 找出能解碼的'); self.rb2 = QPushButton('🔤 改名勾選的'); self.rb2.setEnabled(False)
        self.rl = QLabel('原檔名是 16 進位、Base64、URL 編碼的亂碼，而且解得出正常文字的，先列給你看，勾了才改；每一筆記在操作紀錄，可以改回來'); self.rl.setObjectName('muted'); self.rl.setWordWrap(True)
        rr_.addWidget(rb1); rr_.addWidget(self.rb2); rr_.addWidget(self.rl, 1)
        self.rt = QTableWidget(0, 3); self.rt.setHorizontalHeaderLabels(['', '原本的檔名', '改成']); self.rt.verticalHeader().setVisible(False); self.rt.setMinimumHeight(150)
        self.rt.setEditTriggers(QAbstractItemView.NoEditTriggers); self.rt.horizontalHeader().setStretchLastSection(True); self.rt.setColumnWidth(0, 28); self.rt.setColumnWidth(1, 360); gl.addWidget(self.rt)
        rb1.clicked.connect(lambda: (self.rl.setText('找中…'), bg(ENG.rename_candidates, self._ren))); self.rb2.clicked.connect(self._ren_go); self.rens = []
        g = QGroupBox('🏠 封面樣式 B（試用中）'); gl = QVBoxLayout(g); v.addWidget(g)
        self.cvb = QCheckBox('封面改用樣式 B：極簡大時鐘（深紫漸層、左上小標誌）；關掉＝原本的樣式 A（膠卷、光暈）')
        self.cvb.setChecked(bool((ENG.cfg.get('lab') or {}).get('cover_b'))); gl.addWidget(self.cvb)
        self.cvb.toggled.connect(lambda on: (ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, cover_b=bool(on))), self.win.cover.update()))
        g = QGroupBox('📊 整理成果統計（試用中）'); gl = QVBoxLayout(g); v.addWidget(g)
        sr2 = QHBoxLayout(); gl.addLayout(sr2); stb = QPushButton('📊 算一下'); sr2.addWidget(stb); sr2.addWidget(QLabel('省了多少空間、剪了幾段、歸檔多少、最近 30 天每天做了多少、影片庫的分布')); sr2.addStretch(1)
        self.stx = QTextBrowser(); self.stx.setMinimumHeight(260); gl.addWidget(self.stx)
        stb.clicked.connect(lambda: (self.stx.setHtml('計算中…'), bg(ENG.stats, self._stats)))
        g = QGroupBox('▶ 預覽選的片段（試用中）'); gl = QVBoxLayout(g); v.addWidget(g)
        self.sp_ = QCheckBox('檔案總管「✂ 輸出初剪」旁邊多一顆「▶ 預覽選的片段」：只連續播你選的那幾段，一段播完自動跳下一段，最後停住；剪之前先確認')
        self.sp_.setChecked(bool((ENG.cfg.get('lab') or {}).get('seg_preview'))); gl.addWidget(self.sp_)
        self.sp_.toggled.connect(lambda on: (ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, seg_preview=bool(on))), self.win.browse.b_segp.setVisible(bool(on))))
        g = QGroupBox('📥 也看「下載」資料夾的更新包（試用中）'); gl = QVBoxLayout(g); v.addWidget(g)
        self.wd = QCheckBox('「下載」資料夾裡出現新的 SC_V….zip，上方也跳「發現更新包 → 立即熱更新」（不用再手動搬進 UPDATE）')
        self.wd.setChecked(bool((ENG.cfg.get('lab') or {}).get('watch_downloads'))); gl.addWidget(self.wd)
        self.wd.toggled.connect(lambda on: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, watch_downloads=bool(on))))
        g = QGroupBox('⏭ 分級後自動跳下一部（試用中）'); gl = QHBoxLayout(g); v.addWidget(g)
        self.an = QCheckBox('在檔案總管按 S／A／E／F（或點分級按鈕）之後，自動換到清單的下一部'); self.an.setChecked(bool((ENG.cfg.get('lab') or {}).get('auto_next')))
        self.an.toggled.connect(lambda on: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, auto_next=bool(on)))); gl.addWidget(self.an); gl.addStretch(1)
        g = QGroupBox('🎲 隨機抽一部沒看過的（試用中）'); gl = QHBoxLayout(g); v.addWidget(g)
        b = QPushButton('🎲 抽一部（目前資料夾）'); gl.addWidget(b); gl.addWidget(QLabel('不知道從哪部開始看的時候用；只抽預覽圖已經好的。')); gl.addStretch(1)
        b.clicked.connect(self.pick_random)
        g = QGroupBox('🔍 找重複的影片（試用中）'); gl = QVBoxLayout(g); v.addWidget(g, 1)
        r = QHBoxLayout(); gl.addLayout(r); b2 = QPushButton('🔍 開始找'); self.dl = QLabel('大小完全一樣，或長度一樣（差 1 秒內）而且大小差不到 2% 的，列成一組。'); self.dl.setObjectName('muted')
        r.addWidget(b2); r.addWidget(self.dl, 1)
        r_s = QHBoxLayout(); gl.addLayout(r_s); self.b_sim = QPushButton('🧬 找畫面相似的（看預覽圖）'); self.sim_thr = QComboBox()
        for nm_, v_ in (('嚴格（幾乎一樣）', 6), ('一般', 10), ('寬鬆（可能有誤判）', 14)): self.sim_thr.addItem(nm_, v_)
        self.sim_thr.setCurrentIndex(1); self.b_sim.setToolTip('V0.1.36 試用：比的是已經做好的預覽圖，同一部轉過檔、縮小、換格式、重複下載的都找得到。\n不讀影片、不碰 HDD；第一次要先幫每部算「畫面指紋」，之後很快。')
        r_s.addWidget(self.b_sim); r_s.addWidget(QLabel('相似程度：')); r_s.addWidget(self.sim_thr); r_s.addStretch(1)
        self.b_sim.clicked.connect(self.find_sim)
        self.tb = QTableWidget(0, 5); self.tb.setHorizontalHeaderLabels(['組', '檔名', '大小', '長度', '資料夾']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.horizontalHeader().setStretchLastSection(True)
        for i, w in enumerate((130, 300, 90, 80)): self.tb.setColumnWidth(i, w)
        gl.addWidget(self.tb, 1); r2 = QHBoxLayout(); gl.addLayout(r2); b3 = QPushButton('到這部（檔案總管頁）'); b4 = QPushButton('📂 在 Windows 檔案總管顯示'); b5 = QPushButton('▶ 播放')
        self.b_keep = QPushButton('🏷 每組只留最大的：其他標 F'); self.b_keep.setToolTip('V0.1.37 試用：每組第一部（最大的）不動，其他的分級改成 F（不搬、不刪）。\n之後可以用分級標籤列篩 F、再一鍵歸檔或刪除。按「↩ 復原標記」可以改回原本的分級。')
        self.b_kundo = QPushButton('↩ 復原標記'); self.b_kundo.setEnabled(False); self.keep_undo = []
        b6 = QPushButton('🆚 並排比較'); b6.setToolTip('V0.1.40 試用：選一部，和同一組最大的那部（選的就是最大的話，和第二部）並排比較：\n同樣位置的 8 張畫面、解析度、編碼、位元率、大小，按一下就決定留哪部。只看預覽圖，不讀影片。')
        for b_ in (b3, b4, b5, b6, self.b_keep, self.b_kundo): r2.addWidget(b_)
        r2.addStretch(1); b5.clicked.connect(self.play_cur); b6.clicked.connect(self.compare_cur); self.b_keep.clicked.connect(self.keep_biggest); self.b_kundo.clicked.connect(self.keep_undo_do)
        b2.clicked.connect(self.find); b3.clicked.connect(self.goto); b4.clicked.connect(self.reveal); self.tb.itemDoubleClicked.connect(lambda _it: self.goto())
        for w_ in (self.bi, self.bn, self.cs_, self.gz, self.ic, self.gk, self.ss, self.rs, self.pg_, self.an, self.wd, self.sp_, self.cvb, self.fm, self.tp, self.cq, self.tg, self.dg): w_.toggled.connect(lambda _o: QTimer.singleShot(0, self.refresh_summary))
        self.tb.setMinimumHeight(180)

    def _ren(self, R):
        self.rens = R; self.rt.setRowCount(len(R))
        for i_, x in enumerate(R):
            c = QTableWidgetItem(); c.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled); c.setCheckState(Qt.Checked); self.rt.setItem(i_, 0, c)
            a_ = QTableWidgetItem(x['name']); a_.setToolTip(x['path']); self.rt.setItem(i_, 1, a_); self.rt.setItem(i_, 2, QTableWidgetItem(f"{x['new']}　（{x['how']}）"))
        self.rb2.setEnabled(bool(R)); self.rl.setText(f'找到 {len(R)} 個可以解碼的檔名（預設全勾，不要的取消勾）' if R else '沒有找到可以解碼的亂碼檔名 👍')

    def _ren_go(self):
        S = [x for i_, x in enumerate(self.rens) if self.rt.item(i_, 0) is not None and self.rt.item(i_, 0).checkState() == Qt.Checked]
        if not S: return
        if QMessageBox.question(self, '改名', f'把 {len(S)} 個檔改成解碼後的名字？\n\n每一筆都記在「📒 操作紀錄」，可以「↩ 搬回原來的位置」改回原名。') != QMessageBox.Yes: return
        def work(): return [ENG.rename_file(x['id'], x['new']) for x in S]
        def done(res):
            ok = sum(1 for r_ in res if r_.get('ok')); bad = [r_['message'] for r_ in res if not r_.get('ok')]
            self.rl.setText(f'改好了 {ok} 個' + (f'，{len(bad)} 個沒改' if bad else '')); self.rb2.setEnabled(False); self.win.browse.load_list()
            if bad: QMessageBox.warning(self, '改名', '\n'.join(bad[:15]))
        bg(work, done)

    def _stats(self, S):
        def bars(rows, label=lambda x: x, total=None):
            rows = [r for r in rows if r[2]]; mx = max([r[2] for r in rows] or [1]); tot = total or sum(r[2] or 0 for r in rows) or 1
            return '<table cellspacing="0" cellpadding="2">' + ''.join(
                f'<tr><td>{label(r[0])}</td><td style="color:#4dc9ff">{"█" * max(1, int(28 * r[2] / mx))}</td><td>{r[1]:,} 部</td><td>{fmt_b(r[2])}</td><td style="color:#6c7a8c">{r[2] / tot * 100:.0f}%</td></tr>' for r in rows) + '</table>'
        K = {'arch': '📦 歸檔', 'trash': '🗑 待刪', 'fav': '⭐ 收藏', 'delete': '❌ 刪除原檔', 'cut': '✂ 初剪', 'conv': '🔁 轉檔', 'undo': '↩ 復原', 'migrate': '📁 搬家', 'exclude': '🚫 排除', 'cat': '🏷 分類', 'snap': '📷 截圖', 'clean': '🧹 清理', 'purge': '🔥 清空待刪', 'upcopy': '📤 複製到上傳'}
        G = {'S': 'S 無條件保存', 'A': 'A 保存', 'E': 'E 觀察', 'F': 'F 刪除', '': '未分級', None: '未分級'}
        days = {}
        for d, k, n, _sz in S['days']: days.setdefault(d, {})[k] = n
        dl = ''.join(f'<tr><td>{d[5:]}</td><td style="color:#45d483">{"▇" * min(40, sum(x.values()))}</td><td>' + '、'.join(f'{K.get(k, k)} {n}' for k, n in x.items()) + '</td></tr>' for d, x in sorted(days.items()))
        gd = dict(S.get('graded_days') or []); gtxt = ''
        if gd:
            mx = max(gd.values()); best = max(gd.items(), key=lambda x: x[1]); streak = 0; t_ = time.time()
            while time.strftime('%Y-%m-%d', time.localtime(t_)) in gd: streak += 1; t_ -= 86400
            gtxt = (f"<h3>🏷 最近 30 天每天分級幾部</h3>平均每天 <b>{sum(gd.values()) / max(1, len(gd)):.0f}</b> 部（有整理的 {len(gd)} 天）　最多 <b>{best[1]:,}</b> 部（{best[0][5:]}）"
                    + (f"　🔥 連續 <b>{streak}</b> 天" if streak > 1 else '') + "<table cellspacing='0' cellpadding='2'>"
                    + ''.join(f"<tr><td>{d[5:]}</td><td style='color:#ffd84d'>{'▇' * max(1, int(30 * n / mx))}</td><td>{n:,} 部</td></tr>" for d, n in sorted(gd.items())) + '</table>'
                    + "<small style='color:#6c7a8c'>（V0.1.42 之後分級的才有日期；同一部改過分級算最後那天）</small>")
        h = (f"<h3>💾 省下的空間</h3>刪除原檔：<b style='color:#45d483'>{fmt_b(S['freed_delete'])}</b>　轉檔：<b style='color:#45d483'>{fmt_b(S['freed_conv'])}</b>　合計 <b>{fmt_b(S['freed_delete'] + S['freed_conv'])}</b>"
             f"<br>剪了 {S['cuts'][0]:,} 個初剪檔（{S['cuts'][1]:,} 部影片）"
             "<h3>📒 最近 30 天做了什麼</h3>" + ('　'.join(f"{K.get(k, k)} {n:,}" + (f"（{fmt_b(sz)}）" if sz else '') for k, n, sz in S['ops']) or '（還沒有紀錄）') +
             (f"<table cellspacing='0' cellpadding='2'>{dl}</table>" if dl else '') + gtxt +
             "<h3>🗂 待整理（還沒歸檔）依分級</h3>" + bars(S['lib'], lambda g: G.get(g, g)) +
             ("<h3>📦 已歸檔</h3>" + bars(S['arch']) if S['arch'] else '') +
             "<h3>🎞 格式</h3>" + bars(S['ext'], lambda e: (e or '?')[1:]) + "<h3>📐 解析度</h3>" + bars(S['res']))
        self.stx.setHtml(h)

    def _orph(self, O):
        self.orph = O; self.cb2.setEnabled(bool(O['dirs']))
        self.cl.setText(f'預覽圖共用 {fmt_b(O["used"] + O["bytes"])}；其中 {len(O["dirs"]):,} 部已經不在影片庫，可以省 {fmt_b(O["bytes"])}' if O['dirs'] else f'預覽圖共用 {fmt_b(O["used"])}，沒有用不到的 👍')

    def _orph_clean(self):
        O = self.orph
        if not O or not O['dirs']: return
        if QMessageBox.question(self, '清理預覽圖', f'刪掉 {len(O["dirs"]):,} 部已經不在影片庫的影片的預覽圖（{fmt_b(O["bytes"])}）？\n\n影片本身不會動；如果之後又把它們加回影片庫，會重新做預覽圖。') != QMessageBox.Yes: return
        dirs = O['dirs']; self.cb2.setEnabled(False); bg(lambda: ENG.thumbs_clean(dirs), lambda r_: (self.cl.setText(f'已清理 {r_[0]:,} 個、省了 {fmt_b(r_[1])}'), self.win.msg(f'清理預覽圖：省了 {fmt_b(r_[1])}')))

    def _health(self, H):
        self.health = H; self.hk.blockSignals(True); self.hk.clear()
        for k, x in H.items(): self.hk.addItem(f'{x["name"]}（{len(x["rows"])}）', k)
        self.hk.blockSignals(False); tot = sum(len(x['rows']) for x in H.values())
        self.hl.setText('都沒問題 👍' if not tot else f'共 {tot} 部可能有問題，雙擊跳到那部（再決定要轉檔、待刪或排除）'); self._health_fill()

    def _health_fill(self):
        k = self.hk.currentData(); R = (self.health.get(k) or {}).get('rows') or []; self._hrows = R; self.ht.setRowCount(len(R))
        for i_, x in enumerate(R):
            why = (x.get('th_err') or x.get('probe_err') or '')[:120] or x['folder']
            for j_, val in enumerate((x['name'], fmt_b(x['size']), fmt_t(x['dur']) if x.get('dur') else '—', why)):
                it = QTableWidgetItem(str(val)); it.setToolTip(x['path'] + ('\n' + why if why != x['folder'] else '')); self.ht.setItem(i_, j_, it)

    def _health_go(self):
        r_ = self.ht.currentRow(); R = getattr(self, '_hrows', [])
        if 0 <= r_ < len(R): self.win.nav.setCurrentRow(0); self.win.browse.goto_file(R[r_]['id'])

    def showEvent(self, e):
        super().showEvent(e); self.refresh_summary()

    def _new_bg_sched(self):
        """🕑 背景工作時段：每一項 開關＋從幾點到幾點."""
        w = QWidget(); g = QGridLayout(w); g.setContentsMargins(0, 0, 0, 0); NM = dict({k: n for k, _i, n in ENG.BG_KINDS}, copy='📤 複製到上傳資料夾', move='🚚 搬硬碟')
        S0 = dict((ENG.cfg.get('lab') or {}).get('sched') or {})
        def save():
            S = {k: {'on': cb.isChecked(), 'from': int(a.value()), 'to': int(b.value())} for k, (cb, a, b) in self.sch.items()}
            ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, sched=S))
        self.sch = {}
        for i, k in enumerate(ENG.SCHED_KINDS):
            d = S0.get(k) or {}; cb = QCheckBox(NM.get(k, k)); cb.setChecked(bool(d.get('on')))
            a = QSpinBox(); a.setRange(0, 23); a.setSuffix(' 點'); a.setValue(int(d.get('from', 1))); b = QSpinBox(); b.setRange(0, 23); b.setSuffix(' 點'); b.setValue(int(d.get('to', 9)))
            g.addWidget(cb, i, 0); g.addWidget(QLabel('只在'), i, 1); g.addWidget(a, i, 2); g.addWidget(QLabel('到'), i, 3); g.addWidget(b, i, 4); g.addWidget(QLabel('之間做（跨半夜也可以，例如 23 到 7）'), i, 5)
            self.sch[k] = (cb, a, b); cb.toggled.connect(lambda _o: save()); a.valueChanged.connect(lambda _x: save()); b.valueChanged.connect(lambda _x: save())
        return w

    def _share_import(self):
        L = [x for x in ENG.share_list() if not x['mine']]
        if not L: QMessageBox.information(self, '📥', '接著的硬碟上沒有另一台電腦存的新功能設定\n（另一台先按「🔄 新功能設定存到硬碟」）'); return
        items = [f"{x['d']}:　{x['pc_name']}　{time.strftime('%m/%d %H:%M', time.localtime(x['t']))}　打開 {x['n_on']} 個" for x in L]
        it, ok = QInputDialog.getItem(self, '📥 套用另一台的設定', '選一份（這台的上傳資料夾、讓路程式不會被蓋掉）：', items, 0, False)
        if not ok: return
        X = L[items.index(it)]['d']; ok_, m = ENG.share_import(X); self.win.msg(m)
        if ok_: self.win.apply_new_labs(); self.refresh_summary()

    def _new_check(self):
        def show(R):
            QMessageBox.information(self, '🩺 新功能自我檢查', '\n'.join(('✔ ' if ok else '⚠ ') + t for ok, t in R) or '沒有東西可以檢查')
        bg(ENG.new_selfcheck, show)

    def _new_filter(self):
        f = self.new_q.text().strip().lower(); off = self.new_off.isChecked()
        for k_, (box_, txt_) in self.new_box.items(): box_.setVisible((not f or f in txt_) and not (off and self.new_cb[k_].isChecked()))

    def _new_all_on(self):
        K = [k_ for k_, (box_, _t) in self.new_box.items() if not box_.isHidden() and not self.new_cb[k_].isChecked()]
        if not K: self.win.msg('列出來的都已經打開了'); return
        if QMessageBox.question(self, '🆕 新功能', f'一次打開 {len(K)} 個新功能？') != QMessageBox.Yes: return
        L = dict(ENG.cfg.get('lab') or {}); L.update({k_: True for k_ in K}); ENG.cfg.set('lab', L)
        for k_ in K: self.new_cb[k_].blockSignals(True); self.new_cb[k_].setChecked(True); self.new_cb[k_].blockSignals(False)
        self.refresh_summary(); self.win.apply_new_labs(); self._new_filter(); self.win.msg(f'🧪 打開了 {len(K)} 個新功能')

    def _new_copy_to(self):
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); L = ENG.cfg.get('lab') or {}
        e = QLineEdit(str(L.get('copy_dir') or '')); e.setPlaceholderText('例如 K:\\上傳'); b = QPushButton('選資料夾…'); sp = QSpinBox(); sp.setRange(5, 500); sp.setSuffix(' MB/s'); sp.setValue(int(L.get('copy_mbps') or 60))
        h.addWidget(QLabel('上傳資料夾')); h.addWidget(e, 1); h.addWidget(b); h.addWidget(QLabel('最快')); h.addWidget(sp)
        save = lambda: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, copy_dir=e.text().strip(), copy_dir_vol=ENG.path_vol(e.text().strip()), copy_mbps=int(sp.value())))
        def pick():
            d = QFileDialog.getExistingDirectory(self, '上傳資料夾', e.text() or str(Path.home()))
            if d: e.setText(os.path.normpath(d)); save()
        sb_ = QComboBox(); [sb_.addItem(t_, k_) for t_, k_ in (('直接放進去', ''), ('分今天日期資料夾', 'date'), ('分作者資料夾', 'creator'))]; sb_.setCurrentIndex(max(0, sb_.findData(str(L.get('copy_sub') or ''))))   # V0.3.53
        sb_.currentIndexChanged.connect(lambda _i: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, copy_sub=sb_.currentData()))); h.addWidget(sb_)
        cn_ = QComboBox(); [cn_.addItem(t_, k_) for t_, k_ in (('檔名跟原檔一樣', ''), ('檔名前加日期', 'date'), ('檔名前加分級', 'grade'), ('日期＋分級', 'both'))]; cn_.setCurrentIndex(max(0, cn_.findData(str(L.get('copy_name') or ''))))   # V0.3.85
        cn_.setToolTip('複製到上傳資料夾的複本檔名：例如 20261107_S_原檔名.mp4（方便照順序發；原檔名字不變）'); cn_.currentIndexChanged.connect(lambda _i: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, copy_name=cn_.currentData()))); h.addWidget(cn_)
        ug = QSpinBox(); ug.setRange(0, 200); ug.setPrefix('每天目標 '); ug.setSuffix(' 部'); ug.setSpecialValueText('不設上傳目標'); ug.setValue(int(L.get('up_goal') or 0)); ug.setToolTip('📤 每天想上傳幾部：有設就在下方狀態列顯示今天進度（手機也看得到）'); h.addWidget(ug)   # V0.3.63
        ug.valueChanged.connect(lambda n: (ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, up_goal=int(n))), setattr(self.win if hasattr(self, 'win') else self, '_upg_t', 0)))
        ugb = QComboBox(); [ugb.addItem(t_, k_) for t_, k_ in (('目標算複製的', ''), ('目標算發佈的 ✅', 'pub'))]; ugb.setCurrentIndex(max(0, ugb.findData(str(L.get('up_goal_by') or '')))); h.addWidget(ugb)   # V0.4.44
        ugb.currentIndexChanged.connect(lambda _i: (ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, up_goal_by=ugb.currentData())), setattr(ENG, '_upg_c', None)))
        ac = QCheckBox('剪好就複製'); ac.setToolTip('輸出初剪好了，剪好的檔自動排進複製'); ac.setChecked(bool(L.get('copy_after_cut'))); h.addWidget(ac)   # V0.3.49
        ac.toggled.connect(lambda on: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, copy_after_cut=bool(on))))
        ag = QComboBox(); [ag.addItem(t_, g_) for t_, g_ in (('不自動', ''), ('分成 S 就自動複製', 'S'), ('分成 A 就自動複製', 'A'))]; ag.setCurrentIndex(max(0, ag.findData(str(L.get('copy_on_grade') or ''))))   # V0.3.33
        ag.currentIndexChanged.connect(lambda _i: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, copy_on_grade=ag.currentData()))); h.addWidget(ag)
        tg = QComboBox(); tg.addItem('不貼標籤', '')
        for k_, (ic_, nm_, _c) in TAGS.items(): tg.addItem(f'{ic_} {nm_}', k_)
        i_ = tg.findData(str(L.get('copy_tag') or '')); tg.setCurrentIndex(max(0, i_)); h.addWidget(QLabel('複製好貼')); h.addWidget(tg)   # V0.2.74
        tg.currentIndexChanged.connect(lambda _i: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, copy_tag=tg.currentData())))
        e.editingFinished.connect(save); sp.valueChanged.connect(lambda _x: save()); b.clicked.connect(pick); return w

    def _new_auto_scan(self):
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); c = QComboBox(); cur = int((ENG.cfg.get('lab') or {}).get('auto_scan_min') or 30)
        for m_ in (10, 20, 30, 60, 120, 240): c.addItem(f'每 {m_} 分鐘' if m_ < 60 else f'每 {m_ // 60} 小時', m_)
        i_ = c.findData(cur); c.setCurrentIndex(i_ if i_ >= 0 else 2); h.addWidget(c); h.addStretch(1)
        c.currentIndexChanged.connect(lambda _i: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, auto_scan_min=int(c.currentData())))); return w

    def _new_auto_theme(self):
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); L = ENG.cfg.get('lab') or {}
        a = QSpinBox(); a.setRange(0, 23); a.setSuffix(' 點'); a.setValue(int(L.get('theme_from', 7))); b = QSpinBox(); b.setRange(0, 23); b.setSuffix(' 點'); b.setValue(int(L.get('theme_to', 19)))
        h.addWidget(QLabel('淺色：從')); h.addWidget(a); h.addWidget(QLabel('到')); h.addWidget(b); h.addWidget(QLabel('（其他時間深色）')); h.addStretch(1)
        sv = lambda _x=0: (ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, theme_from=int(a.value()), theme_to=int(b.value()))), setattr(self.win, '_at_t', 0))
        a.valueChanged.connect(sv); b.valueChanged.connect(sv); return w

    def _new_proc_guard(self):
        w = QWidget(); g = QGridLayout(w); g.setContentsMargins(0, 0, 0, 0); L = ENG.cfg.get('lab') or {}
        e = QLineEdit(str(L.get('proc_names') or 'obs64.exe')); e.setPlaceholderText('程式名稱，逗號隔開，例如 obs64.exe, TikLive.exe')
        g.addWidget(QLabel('這些程式在跑時：'), 0, 0); g.addWidget(e, 0, 1, 1, 4)
        K_ = list(L.get('proc_kinds') or ['conv']); cbs = {}
        for i, (k_, n_) in enumerate((('conv', '🔁 轉檔'), ('thumb', '🖼 預覽圖'), ('probe', '🔎 讀影片資訊'), ('move', '🚚 搬硬碟'), ('copy', '📤 複製到上傳'))):   # V0.3.91 複製也可以讓路
            cb = QCheckBox(n_ + ' 先讓路'); cb.setChecked(k_ in K_ or (k_ == 'copy' and bool(L.get('proc_copy')))); g.addWidget(cb, 1, i + 1); cbs[k_] = cb
        sv = lambda *_a: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, proc_names=e.text().strip(), proc_kinds=[k_ for k_, c_ in cbs.items() if c_.isChecked()]))
        e.editingFinished.connect(sv); [c_.toggled.connect(sv) for c_ in cbs.values()]
        b = QPushButton('🔍 看現在有哪些程式在跑'); g.addWidget(b, 2, 1)
        def show_():
            P = sorted(ENG.proc_seen()); QMessageBox.information(self, '現在在跑的程式', ('、'.join(P[:200]) or '（還沒讀到，過幾秒再按一次）'))
        b.clicked.connect(show_); return w

    def _new_note_presets(self):
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); e = QLineEdit(str(lab_cfg().get('note_list') or '可剪,好笑,重看,要上傳')); e.setPlaceholderText('逗號隔開，最多 12 個')
        h.addWidget(QLabel('選項：')); h.addWidget(e, 1); e.editingFinished.connect(lambda: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, note_list=e.text().strip()))); return w

    def _new_caption(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0); e = QPlainTextEdit(str(lab_cfg().get('caption_tpl') or '{作者} {日期}\n{備註}\n#直播 #精華')); e.setMaximumHeight(70)
        v.addWidget(QLabel('範本（可以用 {作者} {檔名} {日期} {分級} {備註} {長度} {#作者}）：')); v.addWidget(e)
        e2 = QPlainTextEdit(str(lab_cfg().get('caption_tpl2') or '')); e2.setMaximumHeight(60); e2.setPlaceholderText('第二組範本（給別的平台用，可以空白）'); v.addWidget(QLabel('第二組範本（V0.4.20，例如 IG／YouTube 用）：')); v.addWidget(e2)
        b = QPushButton('儲存範本'); v.addWidget(b)
        cc = QCheckBox('📤 複製到上傳資料夾時，旁邊一起放同名的文案 .txt'); cc.setChecked(bool(lab_cfg().get('copy_caption'))); v.addWidget(cc)   # V0.3.44
        cc.toggled.connect(lambda on: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, copy_caption=bool(on))))
        b.clicked.connect(lambda: (ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, caption_tpl=e.toPlainText(), caption_tpl2=e2.toPlainText())), self.win.msg('📋 範本存好了'))); return w

    def _new_goal(self):
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); sp = QSpinBox(); sp.setRange(1, 100000); sp.setSingleStep(10); sp.setValue(int((ENG.cfg.get('lab') or {}).get('goal_n') or 100))
        sp.setValue(int(ENG.cfg.get('daily_goal_n') or 100))
        h.addWidget(QLabel('每天')); h.addWidget(sp); h.addWidget(QLabel('部（跟「其他設定」的每日目標同一個數字）')); h.addStretch(1); sp.valueChanged.connect(lambda x: ENG.day_goal_set(x)); return w

    def _new_disk_warn(self):
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); sp = QSpinBox(); sp.setRange(5, 2000); sp.setSuffix(' GB'); sp.setValue(int((ENG.cfg.get('lab') or {}).get('disk_warn_gb') or 50))
        h.addWidget(QLabel('剩不到')); h.addWidget(sp); h.addWidget(QLabel('就提醒')); h.addStretch(1)
        sp.valueChanged.connect(lambda x: (ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, disk_warn_gb=int(x))), setattr(ENG, '_dw_c', None))); return w

    def refresh_summary(self):
        L = ENG.cfg.get('lab') or {}
        on = [f'<span style="color:#45d483">● {nm}</span> <small style="color:#6c7a8c">V{ver}</small>' for k, nm, ver in LAB_LIST if L.get(k)]
        off = [f'<span style="color:#6c7a8c">○ {nm} <small>V{ver}</small></span>' for k, nm, ver in LAB_LIST if not L.get(k)]
        self.summ.setText(('<b>開著：</b>' + '　'.join(on) if on else '<b>開著：</b>（都沒開）') + '<br><b>關著：</b>' + '　'.join(off) +
                          '<br><b>工具（按了才做）：</b>' + '　'.join(f'{nm} <small style="color:#6c7a8c">V{ver}</small>' for nm, ver in LAB_TOOLS))

    def all_off(self):
        if QMessageBox.question(self, '實驗工作區', '把所有試用中的功能都關掉？（工具類的按了才會做，不受影響）') != QMessageBox.Yes: return
        L = dict(ENG.cfg.get('lab') or {})
        for k, _nm, _v in LAB_LIST: L[k] = False
        ENG.cfg.set('lab', L)
        for w_ in (self.bi, self.bn, self.cs_, self.gz, self.ic, self.gk, self.ss, self.rs, self.pg_, self.an, self.wd, self.sp_, self.cvb, self.fm, self.tp, self.cq, self.tg, self.dg):
            w_.blockSignals(True); w_.setChecked(False); w_.blockSignals(False)
        self.win.browse.b_segp.setVisible(False); self.win.browse.b_focus.setVisible(False); self.win.apply_new_labs(); self.win.browse.set_focus_mode(False) if self.win.browse.focus_on else None; self.refresh_summary(); self.win.browse.load_tree(); self.win.msg('實驗功能全部關閉了'); ENG.log.w('實驗工作區：全部關閉')

    def pick_random(self):
        fd = self.win.browse.folder
        bg(lambda: ENG.random_unseen(fd), lambda fid: (self.win.nav.setCurrentRow(0), self.win.browse.goto_file(fid), self.win.msg('🎲 抽到這部')) if fid else self.win.msg('這個資料夾沒有預覽圖好了又沒看過的'))

    def find(self):
        self.dl.setText('找中…'); bg(ENG.find_dupes, self._fill)

    def find_sim(self):
        if getattr(self, '_sim_run', False):                                    # 跑的時候按＝停止
            ENG.vfp_cancel = True; self.b_sim.setEnabled(False); self.dl.setText('🧬 停止中…（做完手上這部就停，已經算好的指紋會留著）'); return
        thr = int(self.sim_thr.currentData() or 10); self._sim_run = True; self.b_sim.setText('⏹ 停止'); self.dl.setText('🧬 準備中…')
        t = ENG.task('lab', f'🧬 找畫面相似的影片（{self.sim_thr.currentText()}）')
        def prog(a, b):
            t['pct'] = a * 100.0 / max(1, b); t['msg'] = f'算畫面指紋 {a:,}／{b:,}'
            ui(lambda a=a, b=b: self.dl.setText(f'🧬 第一次要先算每部的畫面指紋：{a:,}／{b:,}（只讀預覽圖，不碰影片）'))
        def cprog(a, b):
            t['pct'] = a * 100.0 / max(1, b); t['msg'] = f'比對 {a:,}／{b:,}'
            ui(lambda a=a, b=b: self.dl.setText(f'🧬 比對中：{a:,}／{b:,} 部'))
        def work():
            try:
                G = ENG.find_similar(thr, prog, cmp_progress=cprog); stopped = bool(getattr(ENG, 'vfp_cancel', False))
                ENG.done(t, 'stop' if stopped else 'done', ('中途停了，' if stopped else '') + f'{len(G)} 組'); return (G, stopped)
            except Exception as ex: ENG.done(t, 'fail', str(ex)); raise
        def reset():
            self._sim_run = False; ENG.vfp_cancel = False; self.b_sim.setEnabled(True); self.b_sim.setText('🧬 找畫面相似的（看預覽圖）')
        def fin(res):
            reset(); G, stopped = res
            self._fill(G, sim=True)
            if stopped: self.dl.setText(self.dl.text() + '　（中途停了，結果不完整；再按一次會接著算）')
        bg(work, fin, lambda ex: (reset(), self.dl.setText(f'找畫面相似的時候出錯了：{ex}（詳情看 LOG）')))

    def find_like(self, r):
        """🧪 檔案總管右鍵「找跟這部畫面相似的」：結果放在這頁的表格."""
        self.win.nav.setCurrentRow(7)
        if getattr(self, '_sim_run', False) or getattr(self, '_like_run', False): self.win.msg('🧬 上一個還在找，等它做完再按'); return
        self._like_run = True; self.dl.setText(f'🧬 找跟「{r["name"]}」相似的…')
        def prog(a, b): ui(lambda a=a, b=b: self.dl.setText(f'🧬 先算長度接近的影片的畫面指紋：{a:,}／{b:,}'))
        def fin(G):
            self._like_run = False
            if not G: self.dl.setText(f'「{r["name"]}」還沒有預覽圖（或讀不到），先等預覽圖做好'); self._fill([]); return
            if len(G) == 1: self.rows = []; self.tb.setRowCount(0); self.dl.setText(f'🧬 沒有找到跟「{r["name"]}」畫面相似的 👍'); return
            self._fill([G], sim=True)
        bg(lambda: ENG.similar_to(r['id'], int(self.sim_thr.currentData() or 10) + 2, prog), fin,
           lambda ex: (setattr(self, '_like_run', False), self.dl.setText(f'找相似的時候出錯了：{ex}（詳情看 LOG）')))

    def _fill(self, G, sim=False):
        self.rows = [(gi + 1, x) for gi, g in enumerate(G) for x in g]; self.tb.setRowCount(len(self.rows))
        for i, (gi, x) in enumerate(self.rows):
            gtxt = f'{gi}' + ((('　最大' if x.get('big') else f'　差 {x.get("dist", 0):g}') + ('　◀你選的' if x.get('me') else '')) if sim else '') + (f'　{x["w"]}×{x["h"]}' if sim and x.get('w') else '')
            for j, val in enumerate((gtxt, x['name'], fmt_b(x['size']), fmt_t(x['dur']) if x['dur'] else '—', x['folder'])):
                it = QTableWidgetItem(str(val)); it.setToolTip(x['path']); self.tb.setItem(i, j, it)
        self.dl.setText((f'🧬 {len(G)} 組畫面相似' if sim else f'{len(G)} 組可能重複') + f'，共 {len(self.rows)} 部' + ('（沒有找到）' if not G else '　雙擊跳到那部，再決定要留哪一個' + ('（每組第一部是最大的；「差」越小越像，0～6 幾乎一樣）' if sim else '')))

    def _cur(self):
        r = self.tb.currentRow(); return self.rows[r][1] if 0 <= r < len(getattr(self, 'rows', [])) else None

    def play_cur(self):
        x = self._cur()
        if not x: return
        p_ = Player(self.win, x['path'], 0, x['name'], fid=x['id']); p_.setAttribute(Qt.WA_DeleteOnClose); p_.show()

    def compare_cur(self):
        r = self.tb.currentRow(); R = getattr(self, 'rows', [])
        if not (0 <= r < len(R)): self.win.msg('先在表格選一部'); return
        gi, x = R[r]; same = [y for g, y in R if g == gi and y['id'] != x['id']]
        if not same: self.win.msg('這組只有一部'); return
        big = [y for y in same if y.get('big')] or sorted(same, key=lambda y: (-(y.get('size') or 0), -((y.get('w') or 0) * (y.get('h') or 0))))
        same = big[:1] + [y for y in same if y is not big[0]]                   # 跟這組最大的比（選的就是最大的，跟第二部比）
        d = CompareDlg(self.win, x, same[0], self); d.setAttribute(Qt.WA_DeleteOnClose); d.show(); ENG.log.w(f'實驗：並排比較 {x["name"]} ↔ {same[0]["name"]}')

    def mark_f(self, ids, why=''):
        """標 F（記原本的分級，可以按「↩ 復原標記」）."""
        R = getattr(self, 'rows', []); old = {}
        for gi, x in R:
            if x['id'] in ids: old[x['id']] = x.get('grade') or ''; x['grade'] = 'F'
        for i in ids: old.setdefault(i, (ENG.file(i) or {}).get('grade') or '')
        ENG.set_flags(list(ids), grade='F'); self.keep_undo.append(old); self.b_kundo.setEnabled(True)
        ENG.log.w(f'實驗：{why}標 F {len(ids)} 部（原本：' + '、'.join(f'{k}:{v or "無"}' for k, v in old.items()) + '）')
        self.win.browse.load_list(); self.win.browse.tree_relabel()

    def keep_biggest(self):
        """每組第一部（最大的）留著，其他標 F。記下原本的分級，可以復原."""
        R = getattr(self, 'rows', []); first = {}
        for gi, x in R:                                                         # 最大的；一樣大就留解析度高的
            k_ = ((x.get('size') or 0), (x.get('w') or 0) * (x.get('h') or 0))
            if gi not in first or k_ > first[gi][1]: first[gi] = (x['id'], k_)
        first = {gi: v[0] for gi, v in first.items()}; keepers = set(first.values())     # 同一部可能在好幾組：只要它是某一組的最大，就不標
        ids = list(dict.fromkeys(x['id'] for gi, x in R if x['id'] not in keepers and (x.get('grade') or '') != 'F'))
        if not ids: self.win.msg('沒有要標的（每組其他的已經是 F，或還沒找）'); return
        if QMessageBox.question(self, '每組只留最大的', f'{len(first)} 組裡，除了每組最大的那部，其他 {len(ids)} 部的分級改成 F？\n\n只改分級，不搬、不刪；可以按「↩ 復原標記」改回來。') != QMessageBox.Yes: return
        old = {x['id']: (x.get('grade') or '') for gi, x in R if x['id'] in set(ids)}
        ENG.set_flags(ids, grade='F'); self.keep_undo.append(old); self.b_kundo.setEnabled(True)
        for gi, x in R:
            if x['id'] in old: x['grade'] = 'F'
        ENG.log.w(f'實驗：重複／相似的每組只留最大的 → {len(ids)} 部標 F（原本：' + '、'.join(f'{k}:{v or "無"}' for k, v in list(old.items())[:30]) + ('…' if len(old) > 30 else '') + '）')
        self.win.msg(f'🏷 {len(ids)} 部標成 F（每組最大的沒動）'); self.win.browse.load_list(); self.win.browse.tree_relabel()

    def keep_undo_do(self):
        if not self.keep_undo: return
        old = self.keep_undo.pop(); by = {}
        for fid, g in old.items(): by.setdefault(g, []).append(fid)
        for g, ids in by.items(): ENG.set_flags(ids, grade=g, _stamp=False)    # 復原不算「今天分級」
        for gi, x in getattr(self, 'rows', []):
            if x['id'] in old: x['grade'] = old[x['id']]
        self.b_kundo.setEnabled(bool(self.keep_undo)); ENG.log.w(f'實驗：復原「只留最大的」標記 {len(old)} 部'); self.win.browse.tree_relabel(); self.win.msg(f'↩ {len(old)} 部改回原本的分級')

    def goto(self):
        x = self._cur()
        if x: self.win.nav.setCurrentRow(0); self.win.browse.goto_file(x['id'])

    def reveal(self):
        x = self._cur()
        if x: core.explorer_select(x['path'])


class CompareDlg(QDialog):
    """🧪 並排比較兩部（V0.1.40）：同樣位置（10%…90%）的 8 張預覽圖上下對照＋規格；按「留這部」另一部標 F."""
    N = 8

    def __init__(self, win, a, b, lab=None):
        super().__init__(win); self.win = win; self.lab = lab; self.setWindowTitle('🆚 並排比較'); self.resize(1280, 640)
        self.F = [ENG.file(a['id']) or dict(a), ENG.file(b['id']) or dict(b)]
        v = QVBoxLayout(self); g = QGridLayout(); v.addLayout(g, 1); self.cells = [[], []]
        for side, f in enumerate(self.F):
            dur = f.get('dur') or 0; br = (f.get('size') or 0) * 8 / dur / 1e6 if dur else 0
            info = QLabel(f'<b>{"上" if side == 0 else "下"}：{esc_html(f.get("name") or "")}</b><br>'
                          f'{f.get("w") or "?"}×{f.get("h") or "?"}　{esc_html(str(f.get("vcodec") or "?"))}　{(f.get("fps") or 0):.3g} fps　'
                          f'{fmt_b(f.get("size") or 0)}　{fmt_t(dur) if dur else "—"}　{br:.1f} Mbps　分級：{f.get("grade") or "未分級"}<br>'
                          f'<small style="color:#6c7a8c">{esc_html(f.get("folder") or "")}</small>')
            info.setTextFormat(Qt.RichText); info.setWordWrap(True); g.addWidget(info, side * 2, 0, 1, self.N)
            for i in range(self.N):
                c = QLabel('…'); c.setAlignment(Qt.AlignCenter); c.setMinimumSize(140, 80); c.setStyleSheet('background:#0b0f14;border-radius:4px'); g.addWidget(c, side * 2 + 1, i); self.cells[side].append(c)
        r = QHBoxLayout(); v.addLayout(r)
        for side, f in enumerate(self.F):
            k = QPushButton(f'✅ 留{"上" if side == 0 else "下"}面這部（另一部標 F）'); p = QPushButton(f'▶ 播放{"上" if side == 0 else "下"}面'); s_ = QPushButton('📂 顯示')
            k.clicked.connect(lambda _c=False, sd=side: self.keep(sd)); p.clicked.connect(lambda _c=False, sd=side: self.play(sd)); s_.clicked.connect(lambda _c=False, sd=side: core.explorer_select(self.F[sd]['path']))
            for w_ in (k, p, s_): r.addWidget(w_)
            if side == 0: r.addStretch(1)
        bg(self._load, self._show)

    def _load(self):
        out = []
        for f in self.F:
            n = int(f.get('th_n') or 0); imgs = []
            for i in range(self.N):
                img = QImage()
                if f.get('th_dir') and n > 0:
                    k = min(n - 1, int((i + 1) * n / (self.N + 1)))
                    try: img = CardLoader._make({'dir': f['th_dir'], 'k': k, 'cols': int(f.get('th_cols') or 10), 'rows': int(f.get('th_rows') or 10), 'nosave': True})
                    except Exception: img = QImage()
                imgs.append(img)
            out.append(imgs)
        return out

    def _show(self, out):
        try:
            for side, imgs in enumerate(out):
                for c, img in zip(self.cells[side], imgs):
                    if img.isNull(): c.setText('（沒有預覽圖）'); continue
                    c.setPixmap(QPixmap.fromImage(img).scaled(max(140, c.width()), max(80, c.height()), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except RuntimeError: pass                                                # 視窗已經關了

    def play(self, side):
        f = self.F[side]; p_ = Player(self.win, f['path'], 0, f['name'], fid=f['id']); p_.setAttribute(Qt.WA_DeleteOnClose); p_.show()

    def keep(self, side):
        other = self.F[1 - side]
        if self.lab is not None: self.lab.mark_f([other['id']], f'並排比較留「{self.F[side]["name"]}」，')
        else: ENG.set_flags([other['id']], grade='F'); ENG.log.w(f'並排比較：留 {self.F[side]["name"]}，{other["name"]} 標 F')
        self.win.msg(f'✅ 留「{self.F[side]["name"]}」，「{other["name"]}」標成 F'); self.close()


def esc_html(t):
    """放進 RichText 的檔名要跳脫（不用 html 模組：啟動器 EXE 裡不一定有）."""
    return str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def eta_txt(sec):
    """還要多久：1 天 3 小時／2 小時 15 分／12 分鐘."""
    if not sec: return '—'
    sec = int(sec)
    if sec >= 86400: return f'{sec // 86400} 天 {sec % 86400 // 3600} 小時'
    if sec >= 3600: return f'{sec // 3600} 小時 {sec % 3600 // 60} 分'
    return f'{max(1, sec // 60)} 分鐘'


def vkey(v):
    return tuple(int(x) for x in re.findall(r'\d+', str(v or ''))) or (0,)


def load_pkg(path):
    """讀更新包、檢查（只讀，不寫任何檔）。回傳 {'path','files','version','notes','core_changed'}，有問題就丟 RuntimeError."""
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        man = json.loads(zf.read('manifest.json').decode('utf-8-sig')) if 'manifest.json' in names else {}
        files = {m[4:]: zf.read(m) for m in names if m.startswith('app/') and not m.endswith('/')}
    if 'app.py' not in files: raise RuntimeError('這不是 SortCut 的更新包（裡面沒有 app/app.py）')
    if 'vs_web.py' not in files:                                                 # V0.5.22 FileCompare 的更新包也有 app/app.py：不能裝進來蓋掉 SortCut
        raise RuntimeError('這不是 SortCut 的更新包' + ('（是 FileCompare 的：整理已經在 SortCut 裡面了，請用 SC_V… 的包）' if 'web.py' in files or 'fcore.py' in files else '（裡面沒有 app/vs_web.py）'))
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
        C = json.loads(files['CHANGELOG.json'].decode('utf-8-sig')) if 'CHANGELOG.json' in files else []
        notes = []                                                              # V0.2.28 跳版本更新：中間每一版改了什麼都列出來
        for e in C:
            if vkey(APP_VERSION) < vkey(e.get('version')) <= vkey(ver):
                items = list(e.get('items') or []); notes += ([f'【V{e.get("version")}】' + items[0]] + items[1:]) if items else []
        if not notes: notes = list((next((e for e in C if str(e.get('version')) == ver), None) or {}).get('items') or [])
    except Exception: pass
    hot_ok = b'def hot_start(' in files['app.py']
    return {'path': str(path), 'files': files, 'version': ver, 'notes': notes, 'hot_ok': hot_ok}


def upd_log(msg):
    try:
        (ROOT / 'LOG').mkdir(exist_ok=True)
        with open(ROOT / 'LOG' / 'update_log.txt', 'a', encoding='utf-8') as fh: fh.write(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}\n')
    except Exception: pass
    try: ENG.log.w('更新：' + msg.splitlines()[0][:300])
    except Exception: pass


def hot_update(win, pkg):
    """熱更新：寫入新程式 → 用全新的模組建新引擎、新視窗 → 交接 → 收掉舊視窗。背景工作不停、程式不關。
    任何一步失敗：檔案還原、模組還原，舊視窗照常用（更新包放進 UPDATE，下次開程式時再試）。回傳 True／False."""
    code = HERE; ver = pkg['version']; t0 = time.time()
    upd_log(f'熱更新開始：V{APP_VERSION} → V{ver}（{Path(pkg["path"]).name}）')
    backup = ROOT / 'app_backup' / f'{time.strftime("%Y%m%d_%H%M%S")}_before_hot_V{ver}'
    try:
        shutil.copytree(code, backup, ignore=shutil.ignore_patterns('__pycache__'))
        for n, data in pkg['files'].items():
            dst = code / n; tmp = dst.with_name(dst.name + '.new'); tmp.write_bytes(data); os.replace(str(tmp), str(dst))
        shutil.rmtree(code / '__pycache__', ignore_errors=True)
    except Exception as ex:
        _restore_files(backup); upd_log(f'熱更新失敗（寫檔）：{ex}\n{traceback.format_exc()}')
        try: win.msg(f'⚠ 更新失敗：寫入新程式失敗，已還原，程式照常使用（{ex}）', 20000)   # V0.6.16 不跳視窗
        except Exception: pass
        return False
    mods = sorted({p.stem for p in code.glob('*.py')} - {'app'}); saved = {m: sys.modules.get(m) for m in mods}
    new_eng = None
    try:
        for m in mods: sys.modules.pop(m, None)
        importlib.invalidate_caches()
        name = f'vs_app_hot_{int(time.time() * 1000)}'
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
        try: sys.modules.pop(name, None)
        except Exception: pass
        _restore_files(backup)
        try:
            d = ROOT / 'UPDATE'; d.mkdir(exist_ok=True)
            if Path(pkg['path']).parent.resolve() != d.resolve(): shutil.copy2(pkg['path'], d / Path(pkg['path']).name)
        except Exception: pass
        upd_log(f'熱更新失敗（新版載入）：{ex}\n{err}')
        QMessageBox.warning(win, '無法熱更新', f'新版沒辦法在執行中載入，已經還原成 V{APP_VERSION}，背景工作沒有受影響。\n\n'
                            f'更新包放在 UPDATE 資料夾，下次打開程式時會自動套用（失敗會自動退回）。\n\n{ex}'); return False
    try: win.handoff()                                                          # 舊視窗：計時器停、托盤收起來；引擎不動
    except Exception: upd_log('舊視窗交接時有錯誤（不影響新版）：\n' + traceback.format_exc())
    try: new_eng.start()                                                        # 新引擎開始接新工作，舊引擎退休（手上的做完）
    except Exception: upd_log('新引擎啟動時有錯誤：\n' + traceback.format_exc())
    try: new_win.show_after_hot(state)
    except Exception: upd_log('新視窗顯示時有錯誤：\n' + traceback.format_exc()); new_win.show()
    app = QApplication.instance(); app._vs_main = new_win; app._vs_eng = new_eng
    try:
        p = Path(pkg['path']); d = ROOT / 'UPDATE'
        if p.parent.resolve() == d.resolve(): (d / 'applied').mkdir(exist_ok=True); os.replace(str(p), str(d / 'applied' / p.name))
    except Exception: pass
    upd_log(f'熱更新完成：V{APP_VERSION} → V{ver}，{time.time() - t0:.1f} 秒（備份 {backup.name}）')
    try: win.close(); win.deleteLater()
    except Exception: pass
    return True


def _restore_files(backup):
    try:
        if backup and Path(backup).exists():
            keep = {f.name for f in Path(backup).iterdir() if f.is_file()}
            for f in Path(backup).iterdir():
                if f.is_file(): shutil.copy2(f, HERE / f.name)
            for f in HERE.iterdir():                                            # 更新包新加的檔案也拿掉，回到原樣
                if f.is_file() and f.name not in keep and f.suffix in ('.py', '.json'):
                    try: f.unlink(); upd_log(f'還原：移除更新包新加的 {f.name}')
                    except Exception: pass
            shutil.rmtree(HERE / '__pycache__', ignore_errors=True)
    except Exception: upd_log('還原檔案失敗：\n' + traceback.format_exc())


class UpdPage(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win; self.pkg = None
        v = QVBoxLayout(self); v.setContentsMargins(8, 8, 8, 8)
        t = QLabel(f'🆕 版本與更新　目前 V{APP_VERSION}'); t.setObjectName('title'); v.addWidget(t)
        n = QLabel('⚡ 熱更新：選更新包（SC_V…zip）或丟進 UPDATE 資料夾 → 確認 → 程式不用關，畫面直接換成新版；正在做的預覽圖、轉檔、初剪不中斷。'
                   '新版載入不了會自動還原，程式照常用。'); n.setWordWrap(True); v.addWidget(n)
        r = QHBoxLayout(); v.addLayout(r); b1 = QPushButton('📦 選更新包…'); self.b_go = QPushButton('⚡ 熱更新'); self.b_go.setEnabled(False)
        self.b_go.setObjectName('start')
        b3 = QPushButton('🔁 改用重開程式套用'); b2 = QPushButton('📂 開 UPDATE 資料夾')
        b4 = QPushButton('☁ 檢查雲端更新'); b4.setToolTip('從 GitHub 看有沒有新版（開程式 1 分鐘後、之後每 6 小時也會自動看）')
        self.cb_cloud = QCheckBox('自動檢查'); self.cb_cloud.setChecked(ENG.cfg.get('cloud_upd') is not False)
        self.cb_cloud.toggled.connect(lambda on: ENG.cfg.set('cloud_upd', bool(on)))
        self.cb_cauto = QCheckBox('有新版自動熱更新'); self.cb_cauto.setChecked(ENG.cfg.get('cloud_auto') is True)       # V0.6.29
        self.cb_cauto.setToolTip('每 30 分鐘看一次；有新版、而且你 5 分鐘沒碰電腦，就自己下載＋熱更新（不用按、不換外殼）')
        self.cb_cauto.toggled.connect(lambda on: ENG.cfg.set('cloud_auto', bool(on)))
        for w in (b4, self.cb_cloud, self.cb_cauto, b1, self.b_go, b3, b2): r.addWidget(w)
        b4.clicked.connect(lambda: self.win._cloud_check(True))
        r.addStretch(1)
        self.cinfo = QLabel(f'☁ 雲端更新：啟動器（EXE）第 {os.environ.get("SC_LAUNCHER") or 1} 版'); self.cinfo.setWordWrap(True); self.cinfo.setTextFormat(Qt.RichText); v.addWidget(self.cinfo)
        self.info = QLabel('（還沒選更新包）'); self.info.setWordWrap(True); self.info.setTextFormat(Qt.RichText); v.addWidget(self.info)
        self.tx = QTextBrowser(); v.addWidget(self.tx, 1); self._cl()
        b1.clicked.connect(self.pick); self.b_go.clicked.connect(self.go); b3.clicked.connect(self.restart_way)
        b2.clicked.connect(lambda: (Path(ROOT / 'UPDATE').mkdir(exist_ok=True), QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT / 'UPDATE')))))

    def cloud_show(self, r):
        I = r.get('info') or {}
        h = f'☁ 雲端更新：{_hesc(r.get("message", ""))}　<span style="color:#888">（{time.strftime("%H:%M", time.localtime(r.get("t") or time.time()))} 看的・EXE 第 {os.environ.get("SC_LAUNCHER") or 1} 版）</span>'
        if r.get('newer'): h += f'　<a href="#">⬇ 更新到 V{I.get("version")}</a>' + ('（要換 EXE）' if I.get('need_shell') else '')
        self.cinfo.setText(h)
        try: self.cinfo.linkActivated.disconnect()
        except Exception: pass
        self.cinfo.linkActivated.connect(lambda _u: self.win._cloud_go())

    def _cl(self):
        try: C = json.loads((HERE / 'CHANGELOG.json').read_text(encoding='utf-8'))
        except Exception: C = []
        h = ''
        for x in C:
            h += f"<h3>V{x.get('version')}　<small>{x.get('date', '')}</small></h3><ul>" + ''.join(f'<li>{i}</li>' for i in x.get('items') or []) + '</ul>'
        self.tx.setHtml(h or '（沒有更新紀錄）')

    def pick(self):
        p, _ = QFileDialog.getOpenFileName(self, '選更新包', str(Path.home() / 'Downloads'), '更新包 (SC_V*.zip VS_V*.zip *_Update.zip *.zip)')
        if p: self.load(p)

    def load(self, p):
        self.pkg = None; self.b_go.setEnabled(False)
        try: pkg = load_pkg(p)
        except Exception as ex:
            self.info.setText(f'<b>{Path(p).name}</b><br><span style="color:#ff6577">不能用這個更新包：{ex}</span>'); upd_log(f'更新包不能用：{p}：{ex}'); return False
        self.pkg = pkg; d = vkey(pkg['version']); c = vkey(APP_VERSION)
        way = '升級' if d > c else ('相同版本（重新套用）' if d == c else '⚠ 降版（退回舊版）')
        h = f'<b>{Path(p).name}</b>　V{APP_VERSION} → <b>V{pkg["version"]}</b>（{way}）'
        if pkg['notes']: h += '<br>' + '<br>'.join('• ' + str(x) for x in pkg['notes'])
        h += ('<br><span style="color:#45d483">可以熱更新：程式不用關。</span>' if pkg['hot_ok'] else
              '<br><span style="color:#f0ad4e">這個版本不支援熱更新，要用「🔁 改用重開程式套用」。</span>')
        self.info.setText(h); self.b_go.setEnabled(pkg['hot_ok']); upd_log(f'選了更新包：{p}（V{pkg["version"]}，{way}，{len(pkg["files"])} 個檔）')
        return True

    def go(self, confirm=True):
        if not self.pkg: return
        busy = len(ENG.th_active) + len(ENG.cv_active) + (1 if ENG.cut_cur else 0)
        if confirm and QMessageBox.question(self, '熱更新', f'從 V{APP_VERSION} 更新到 V{self.pkg["version"]}？\n\n程式不用關；'
                                            + (f'正在做的 {busy} 個工作不會中斷（做完由新版接手）。' if busy else '') + '\n播放視窗會關掉。') != QMessageBox.Yes: return
        hot_update(self.win, self.pkg)

    def restart_way(self):
        if not self.pkg: self.win.msg('先選更新包'); return
        try:
            d = ROOT / 'UPDATE'; d.mkdir(exist_ok=True)
            if Path(self.pkg['path']).parent.resolve() != d.resolve(): shutil.copy2(self.pkg['path'], d / Path(self.pkg['path']).name)
        except Exception as ex: QMessageBox.warning(self, '更新', str(ex)); return
        if QMessageBox.question(self, '更新', '更新包放好了。現在重新開程式套用？\n\n正在做的預覽圖、轉檔會停下，重開後自動接著做。') == QMessageBox.Yes: self.win.restart()


# ============================================================ 上方「✂ 剪輯／轉檔」按鈕（小數字）＋浮窗（參考 TikLive）
class BadgeButton(QPushButton):
    """右上紅色＝新出的初剪檔數（按下輸出初剪就加上這次要出幾個，打開浮窗歸零）；右下藍色＝進行中／排隊的工作數."""
    def __init__(self, text):
        super().__init__(text); self.red = 0; self.blue = 0; self.flash = 0; self.setMinimumWidth(130)

    def set_counts(self, red=None, blue=None):
        ch = False
        if red is not None and red != self.red: self.red = red; ch = True
        if blue is not None and blue != self.blue: self.blue = blue; ch = True
        if ch: self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); f = QFont(); f.setPixelSize(10); f.setBold(True); p.setFont(f)
        for n, col, top in ((self.red, '#ff4d6d', True), (self.blue, '#4dc9ff', False)):
            if not n: continue
            t = str(n) if n < 1000 else '999+'; w = max(16, 7 * len(t) + 6); h = 15
            r = QRect(self.width() - w - 1, 1 if top else self.height() - h - 1, w, h)
            p.setPen(Qt.NoPen); p.setBrush(QColor(col)); p.drawRoundedRect(r, 7, 7); p.setPen(QColor('#0b0e13')); p.drawText(r, Qt.AlignCenter, t)
        p.end()


class JobsPopup(QFrame):
    """點上方「✂ 剪輯／轉檔」打開：初剪工作（排隊／剪輯中／✔ 完成＋輸出檔）、完成的可以直接刪原檔；正在轉檔的；規則（免轉檔、分段／合併、檔名、存到）."""
    def __init__(self, win):
        super().__init__(win, Qt.Popup | Qt.FramelessWindowHint); self.win = win; self.data = None
        self.setStyleSheet(f"JobsPopup{{background:{THEME['panel']};border:1px solid {THEME['border_strong']};border-radius:12px}}"); self.resize(760, 560)
        v = QVBoxLayout(self); v.setContentsMargins(10, 8, 10, 8)
        self.h = QLabel(''); self.h.setTextFormat(Qt.RichText); v.addWidget(self.h)
        self.tb = QTableWidget(0, 5); self.tb.setHorizontalHeaderLabels(['時間', '影片', '段', '狀態', '輸出']); self.tb.verticalHeader().setVisible(False)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tb.setSelectionBehavior(QAbstractItemView.SelectRows); self.tb.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tb.horizontalHeader().setStretchLastSection(True)
        for i, w in enumerate((70, 230, 60, 150)): self.tb.setColumnWidth(i, w)
        v.addWidget(self.tb, 1)
        r = QHBoxLayout(); v.addLayout(r)
        self.b_dir = QPushButton('📂 開輸出資料夾'); self.b_play = QPushButton('▶ 播放初剪檔'); self.b_del = QPushButton('🗑 刪除原檔（選的、已完成的）')
        self.b_del.setStyleSheet('QPushButton{color:#ff6577;font-weight:700}'); self.b_go = QPushButton('到這部')
        for w in (self.b_dir, self.b_play, self.b_go, self.b_del): r.addWidget(w)
        r.addStretch(1)
        self.cv = QLabel(''); self.cv.setWordWrap(True); self.cv.setTextFormat(Qt.RichText); v.addWidget(self.cv)
        g = QGroupBox('規則（改了馬上存）'); gl = QGridLayout(g); v.addWidget(g)
        self.mode = QComboBox(); self.mode.addItem('⚡ 快速免轉檔（幾秒就好，畫質不變）', 'copy'); self.mode.addItem('重新壓縮（起點終點精準，比較慢）', 'enc')
        self.merge = QComboBox(); self.merge.addItem('分段：每段一個檔（_01、_02…）', False); self.merge.addItem('不分段：合併成一個檔（_ALL）', True)
        self.dirl = QLabel(''); self.dirl.setObjectName('muted'); self.dirl.setWordWrap(True); bd = QPushButton('選…'); bc = QPushButton('🔁 轉檔設定')
        gl.addWidget(QLabel('剪輯方式'), 0, 0); gl.addWidget(self.mode, 0, 1); gl.addWidget(QLabel('多段'), 0, 2); gl.addWidget(self.merge, 0, 3)
        gl.addWidget(QLabel('存到'), 1, 0); gl.addWidget(self.dirl, 1, 1, 1, 2); gl.addWidget(bd, 1, 3)
        nm = QLabel('檔名：正常檔名照用；一大串數字英文的亂碼先試著解碼（16 進位、Base64、URL…），解不出來只取前 10 碼；後面加 _01、_02…或 _ALL。'
                    '初剪資料夾自動排除、永久保存。'); nm.setObjectName('muted'); nm.setWordWrap(True); gl.addWidget(nm, 2, 0, 1, 3); gl.addWidget(bc, 2, 3)
        self._load_rules()
        self.mode.currentIndexChanged.connect(lambda _i: ENG.cfg.set('cut_mode', self.mode.currentData())); self.merge.currentIndexChanged.connect(lambda _i: ENG.cfg.set('cut_merge', self.merge.currentData()))
        bd.clicked.connect(self._pick_dir); bc.clicked.connect(lambda: (self.hide(), self.win.nav.setCurrentRow(1)))
        self.b_dir.clicked.connect(self._open_dir); self.b_play.clicked.connect(self._play); self.b_del.clicked.connect(self._del); self.b_go.clicked.connect(self._goto)
        self.tb.itemDoubleClicked.connect(lambda _it: self._open_dir())
        self.tm = QTimer(self); self.tm.timeout.connect(self.refresh)

    def _load_rules(self):
        for w, k in ((self.mode, 'cut_mode'), (self.merge, 'cut_merge')):
            w.blockSignals(True); w.setCurrentIndex(max(0, w.findData(ENG.cfg.get(k)))); w.blockSignals(False)
        self.dirl.setText(ENG.cfg.get('cut_dir') or '每顆硬碟的 VideoSIFT\\初剪（保留原本的子資料夾）')

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, '初剪檔存到哪裡')
        if d:
            ENG.cfg.set('cut_dir', os.path.normpath(d)); self._load_rules(); bg(ENG.apply_excludes)
            try: self.win.setp._load(); self.win.setp._load_ex()
            except Exception: pass

    def open_at(self, btn):
        self._load_rules(); gp = btn.mapToGlobal(QPoint(btn.width() - self.width(), btn.height() + 4))
        self.move(max(0, gp.x()), gp.y()); self.show(); self.raise_(); self.refresh(); self.tm.start(1000)

    def hideEvent(self, e):
        self.tm.stop(); super().hideEvent(e)

    def refresh(self):
        bg(ENG.jobs_view, self._fill)

    def _fill(self, D):
        if not self.isVisible(): return
        self.data = D; C = D['cuts']; done = sum(1 for c in C if c['state'] in ('done', 'part')); fail = sum(1 for c in C if c['state'] == 'fail')
        self.h.setText(f"<b>✂ 初剪</b>　進行中／排隊 <b style='color:#4dc9ff'>{D['cut_active']}</b>　完成 <b style='color:#45d483'>{done}</b>" + (f"　失敗 <b style='color:#ff4d6d'>{fail}</b>" if fail else '') +
                       ("　<span style='color:#45d483'>✔ 全部做完了，可以放心刪原檔</span>" if C and not D['cut_active'] else ''))
        sel = {self.tb.item(r.row(), 0).data(Qt.UserRole) for r in self.tb.selectionModel().selectedRows()} if self.tb.rowCount() else set()
        self.tb.setUpdatesEnabled(False); self.tb.setRowCount(len(C)); col = {'wait': '#9aa5b3', 'run': '#4dc9ff', 'done': '#45d483', 'part': '#f0ad4e', 'fail': '#ff4d6d'}
        for i, c in enumerate(C):
            stt = {'wait': '⏳ 排隊', 'run': f"⚙ 剪輯中 {c['pct'] or 0}%", 'done': '✔ 完成', 'part': '⚠ 部分完成', 'fail': '✖ 失敗'}.get(c['state'], c['state'])
            if c['state'] in ('done', 'part'): stt += '・原檔已刪' if c['gone'] else '・原檔還在'
            vals = (time.strftime('%H:%M:%S', time.localtime(c['t'])), c['name'], f"{c['nseg']}{'→1' if c['merge'] else ''}", stt,
                    '、'.join(Path(o).name for o in c['outs']) or (c['err'][:120] if c['state'] == 'fail' else ''))
            for j, val in enumerate(vals):
                it = self.tb.item(i, j)
                if it is None: it = QTableWidgetItem(); self.tb.setItem(i, j, it)
                if it.text() != str(val): it.setText(str(val)); it.setToolTip('\n'.join(c['outs']) if j == 4 and c['outs'] else (c['path'] if j == 1 else str(val)))
                if j == 0: it.setData(Qt.UserRole, c['key'])
            self.tb.item(i, 3).setForeground(QColor(col.get(c['state'], '#dfe5ee')))
            if c['key'] in sel: self.tb.selectRow(i)
        self.tb.setUpdatesEnabled(True)
        cv = D['conv']
        self.cv.setText(f"<b>🔁 轉檔</b>　轉中 <b style='color:#4dc9ff'>{len(cv)}</b>　排隊 {D['cv_wait']}" + (f"　收藏／待刪搬檔 {D['op_active']}" if D['op_active'] else '') +
                        ''.join(f"<br>⚙ {x['name']}　{x['pct']}%　{x['enc']} {x['speed'] or ''}" + (f"　還要 {fmt_t(x['left'])}" if x.get('left') else '') for x in cv[:6]))

    def _sel(self):
        if not self.data: return []
        keys = {self.tb.item(r.row(), 0).data(Qt.UserRole) for r in self.tb.selectionModel().selectedRows()}
        return [c for c in self.data['cuts'] if c['key'] in keys]

    def _open_dir(self):
        S = self._sel()
        if not S or not S[0]['outs']: self.win.msg('先選一個已完成的初剪'); return
        o = S[0]['outs'][0]
        if core.IS_WIN: subprocess.Popen(['explorer', '/select,', o], creationflags=core.NO_WINDOW)
        else: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(o).parent)))

    def _play(self):
        S = self._sel()
        if not S or not S[0]['outs']: self.win.msg('先選一個已完成的初剪'); return
        p = Player(self.win, S[0]['outs'][0], 0, Path(S[0]['outs'][0]).name); p.setAttribute(Qt.WA_DeleteOnClose); p.show()

    def _goto(self):
        S = self._sel()
        if S and not S[0]['gone']: self.hide(); self.win.nav.setCurrentRow(0); self.win.browse.goto_file(S[0]['fid'])

    def _del(self):
        S = [c for c in self._sel() if c['state'] in ('done', 'part') and not c['gone']]
        if not S: self.win.msg('選已完成、原檔還在的初剪（可以多選）'); return
        fids = list(dict.fromkeys(c['fid'] for c in S))
        if QMessageBox.question(self, '刪除原檔', f'刪除 {len(fids)} 部的原檔？\n\n' + '\n'.join(c['name'] for c in S[:10]) + ('\n…' if len(S) > 10 else '') +
                                '\n\n丟到資源回收筒，2 秒預覽圖一起刪；初剪檔永久保留。每部都會先確認初剪檔還在、原檔沒被換掉。') != QMessageBox.Yes: return
        bg(lambda: ENG.delete_original_many(fids), lambda res: (self.win.browse._del_many_done(res, False), self.refresh()))


# ============================================================ 效能浮窗
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
        for name, val, col, H in rows:
            p.setPen(QColor('#cfd6e0')); p.drawText(QRect(10, y, 40, 16), Qt.AlignLeft | Qt.AlignVCenter, name)
            bx = QRect(52, y + 3, 120, 10); p.setPen(Qt.NoPen); p.setBrush(QColor('#1d2430')); p.drawRoundedRect(bx, 4, 4)
            if val is not None: p.setBrush(QColor(col)); p.drawRoundedRect(QRect(bx.x(), bx.y(), int(bx.width() * max(0, min(100, val)) / 100), bx.height()), 4, 4)
            pts = [x for x in list(H)[-60:]]
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


# ============================================================ V0.1.53 左邊側邊欄（照 TikLive：大數字、開始／暫停、分組選單、電腦狀態）
class NavDelegate(QStyledItemDelegate):
    """側邊選單：分組標題（彩色小字＋細線，點了收合）和選項（圖示欄＋選到時左邊彩色條）看得出差別."""
    def sizeHint(self, option, index):
        kind = index.data(Qt.UserRole + 2); h = QFontMetrics(option.font).height()
        return QSize(option.rect.width(), (h + 9) if kind == 'header' else (h + 12))

    def paint(self, painter, option, index):
        painter.save(); painter.setRenderHint(QPainter.Antialiasing)
        kind = index.data(Qt.UserRole + 2); text = str(index.data(Qt.DisplayRole) or '')
        color = QColor(str(index.data(Qt.UserRole + 1) or '#4dc9ff')); r = option.rect
        if kind == 'header':
            f = QFont(option.font); f.setBold(True); px = option.font.pixelSize()
            if px > 0: f.setPixelSize(max(9, round(px * 0.82)))
            else: f.setPointSizeF(max(7.0, f.pointSizeF() * 0.82))
            painter.setFont(f); fm = QFontMetrics(f)
            y = r.bottom() - 6
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
            elif hover:
                painter.setPen(Qt.NoPen); painter.setBrush(TC('hover')); painter.drawRoundedRect(box, 7, 7)
            f = QFont(option.font); f.setBold(selected); painter.setFont(f)
            icon = str(index.data(Qt.UserRole + 3) or ''); badge = str(index.data(Qt.UserRole + 4) or '')
            painter.setPen(color if selected else TC('muted'))
            painter.drawText(QRectF(box.left() + 10, box.top(), 22, box.height()), Qt.AlignCenter, icon)
            painter.setPen(TC('text_strong') if selected else (TC('text') if hover else TC('nav_text')))
            painter.drawText(QRectF(box.left() + 38, box.top(), box.width() - 42, box.height()), Qt.AlignLeft | Qt.AlignVCenter, text)
            if badge:                                                            # 右邊的小數字（例如轉檔排隊幾部）
                fb = QFont(option.font); fb.setBold(True); px = option.font.pixelSize()
                if px > 0: fb.setPixelSize(max(9, round(px * 0.8)))
                else: fb.setPointSizeF(max(7.0, fb.pointSizeF() * 0.8))
                painter.setFont(fb); fmb = QFontMetrics(fb)
                bw = fmb.horizontalAdvance(badge) + 12; br = QRectF(box.right() - bw - 6, box.center().y() - 8, bw, 16)
                c = QColor(color); c.setAlpha(60); painter.setPen(Qt.NoPen); painter.setBrush(c); painter.drawRoundedRect(br, 8, 8)
                painter.setPen(TC('text_strong')); painter.drawText(br, Qt.AlignCenter, badge)
        painter.restore()


HZ_PAGES = {20: 'home', 21: 'explorer', 22: 'search', 23: 'space', 24: 'dupes', 25: 'vault', 26: 'images', 27: 'comfy', 28: 'video', 29: 'queue', 30: 'compare',
            31: 'hot', 32: 'disks', 33: 'settings', 34: 'log', 35: 'help'}      # SortCut 選單頁碼 → HotZone 頁面（HotZone 的畫面嵌在 SortCut 裡）


class NavList(QListWidget):
    """左邊選單。分組標題也是一列，所以「第幾列」≠「第幾頁」：對外 setCurrentRow(頁)、currentRow() 都用頁碼."""
    GROUPS = [('① 檔案管理（16 格快速檢索）', '#2f9bff', [(71, 'FileCompare 總覽', '📊'), (44, '影片快速分類（16 格）', '🎞'), (40, '整理總覽', '🏠'), (43, '整理精靈', '🚀'), (45, '資料夾包', '📦'), (50, '搜尋篩選', '🔎')]),
              ('② 檔案剪輯（10 秒一張截圖）', '#4dc9ff', [(70, 'VideoSift 總覽', '📊'), (0, '檔案總管＋初剪', '▦'), (6, '操作紀錄', '📒')]),
              ('③ 畫質降容量（SSIM）', '#f0ad4e', [(72, 'H265 總覽', '📊'), (74, '檔案總覽（哪裡最大・搜尋）', '🗺'), (1, '轉檔（H.265）', '🔁'), (57, '影片瘦身（畫質目標）', '🗜'), (14, '滾動式參數', '📈'), (13, '碼率測試', '🧪')]),
              ('④ 隔離區・壞掉的檔（待修）', '#ff6b6b', [(49, '損毀檢查', '🩺'), (66, 'SortCut 讀不了的影片', '⚠'), (51, '隔離區', '🧺'), (52, '雜物清理', '🧹'), (25, 'HotZone 保管區', '🛟')]),
              ('⑤ 重複檔案', '#b48cff', [(47, '重複檔', '🔁'), (48, '重複資料夾', '📁'), (46, '重複資料夾最佳解', '🧭'), (24, 'HotZone 重複檔', '👯')]),
              ('⑥ 照片分類與找圖', '#ff7eb6', [(53, '相似／連拍', '🖼'), (54, '依日期整理', '📅'), (55, '時間軸', '🗓'), (56, '照片地圖', '🗺'), (59, '活動', '🧳'), (60, '最愛', '⭐'),
                                       (26, 'HotZone 圖片分類', '🎨'), (27, '生圖比較', '🖼')]),
              ('HotZone 檔案與硬碟', '#43d9ff', [(11, 'HotZone 總管', '🔥'), (20, 'HotZone 總覽', '📋'), (21, 'HotZone 檔案總管', '🗂'), (22, '搜尋', '🔍'), (23, '空間分析', '📊'),
                                          (28, '影片工具', '🎬'), (29, '傳輸佇列', '⇅'), (30, '資料夾同步', '⇄'), (31, '熱處理', '♨'), (32, '磁碟', '💽')]),
              ('電腦與背景', '#45d483', [(2, '後台狀態', '🖥'), (42, '整理的後台', '⚙'), (41, '資料分析', '📈'), (58, '備份檢查', '💾'), (73, '多步搬硬碟（D⇄H）', '🚚'), (15, '搬硬碟', '🚚'), (16, '新功能工具箱', '🧰'),
                                    (7, '🧪 實驗工作區', '🧪'), (61, '整理的操作紀錄', '🧾')]),
              ('設定與說明', '#9aa5b3', [(3, '設定：SortCut', '⚙'), (62, '設定：整理（FileCompare）', '🔧'), (33, '設定：HotZone', '🔥'), (5, '版本與更新', '⟳'),
                                     (8, '使用說明', '📖'), (64, '說明：整理', '📖'), (35, '說明：HotZone', '❓'), (4, 'LOG', '📜'), (63, 'LOG：整理', '📜'), (34, 'LOG：HotZone', '📜')])]
    NAMES = {pg: (ic, nm) for _g, _c, L in GROUPS for pg, nm, ic in L}
    ARCHIVED = {}                                                                # V0.6.37 放回選單（電腦與背景 → 🚚 多步搬硬碟）；Ctrl+Shift+R 照樣能開

    def __init__(self, on_page):
        super().__init__(); self.on_page = on_page; self._page = -1; self._rows = {}; self._items = {}; self._groups = []
        self.setObjectName('workspace_nav'); self.setItemDelegate(NavDelegate(self)); self.setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel); self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for gname, col, L in self.GROUPS:
            h = QListWidgetItem(gname); h.setFlags(Qt.ItemIsEnabled); h.setData(Qt.UserRole, -1); h.setData(Qt.UserRole + 1, col); h.setData(Qt.UserRole + 2, 'header'); self.addItem(h)
            its = []
            for pg, nm, ic in L:
                it = QListWidgetItem(nm); it.setData(Qt.UserRole, pg); it.setData(Qt.UserRole + 1, col); it.setData(Qt.UserRole + 2, 'item'); it.setData(Qt.UserRole + 3, ic)
                it.setToolTip(nm); self.addItem(it); self._items[pg] = it; its.append(it)
                if pg == 73:                                                     # V0.5.85 🚚 紅色、粗體：很重要
                    try: f_ = it.font(); f_.setBold(True); it.setFont(f_); it.setForeground(QColor('#ff5252'))
                    except Exception: pass
            self._groups.append((h, gname, its))
        self._rows = {pg: self.row(it) for pg, it in self._items.items()} if hasattr(self, 'row') else {}
        self.currentRowChanged.connect(self._row_changed); self.itemClicked.connect(self._clicked)
        QTimer.singleShot(0, self.apply_collapse)

    def page_name(self, pg):
        ic, nm = self.NAMES.get(int(pg), ('', ''))
        return nm

    def page_icon(self, pg): return self.NAMES.get(int(pg), ('', ''))[0]

    def _row_changed(self, row):
        try:
            it = self.item(row); pg = int(it.data(Qt.UserRole)) if it is not None else -1
        except Exception: return
        if pg >= 0 and pg != self._page:
            self._page = pg; self._seen(self._group_of(pg)); self.on_page(pg)

    def setCurrentRow(self, pg, *a):
        pg = int(pg); it = self._items.get(pg)
        if it is None: return
        try: super().setCurrentItem(it)
        except Exception: pass
        if pg != self._page: self._page = pg; self.on_page(pg)                 # 沒有真的 Qt 時（自我測試）也會切頁
        self.apply_collapse()

    def currentRow(self): return self._page

    def set_badge(self, pg, txt):
        it = self._items.get(int(pg))
        if it is not None and str(it.data(Qt.UserRole + 4) or '') != str(txt or ''): it.setData(Qt.UserRole + 4, str(txt or ''))

    def _shut(self):
        v = ENG.cfg.get('nav_shut5')                                             # V0.5.16 分組改成工作流程後重新記；第一次：HotZone、設定與說明先收起來（點標題打開）
        shut = set(v) if isinstance(v, list) else {'HotZone 檔案與硬碟', '設定與說明'}
        if ENG.cfg.get('nav_auto_shut') is not False:                            # V0.6.39 介面簡化：14 天沒點過的分組自動收起來（點標題就打開，不會刪）
            seen = ENG.cfg.get('nav_seen') or {}; now = time.time()
            if isinstance(seen, dict) and seen:
                t0 = min(float(x) for x in seen.values())                     # 開始記錄還不滿 14 天：先不收
                if now - t0 > 14 * 86400:
                    shut |= {g for _h, g, _i in self._groups if now - float(seen.get(g, 0)) > 14 * 86400 and g not in (ENG.cfg.get('nav_keep') or [])}
        return shut

    def _seen(self, g):
        try:
            seen = dict(ENG.cfg.get('nav_seen') or {}); now = time.time()
            if now - float(seen.get(g, 0)) > 3600: seen[g] = now; ENG.cfg.set('nav_seen', seen)
        except Exception: pass

    def _group_of(self, pg):
        for _h, g, its in self._groups:
            if self._items.get(pg) in its: return g
        return ''

    @staticmethod
    def group_mode(name):
        """V0.5.70 🎛 這個分組屬於哪一邊：vs／fc／h265；'' ＝ 三邊都顯示（電腦與背景、設定與說明）."""
        n = str(name)
        if n.startswith('②'): return 'vs'
        if n.startswith('③'): return 'h265'
        if n[:1] in '①④⑤⑥' or n.startswith('HotZone'): return 'fc'
        return ''

    def page_mode(self, pg):
        it = self._items.get(int(pg))
        for h, name, its in self._groups:
            if it in its: return self.group_mode(name)
        return ''

    def apply_collapse(self):
        """收起來的分組只留標題（目前這頁所在的組一定打開）；V0.5.70 只顯示目前這一邊（🎛 左上角切換）的分組."""
        try:
            shut = self._shut(); cur = self._items.get(self._page); m = getattr(self, 'mode', '')
            for h, name, its in self._groups:
                gm = self.group_mode(name); away = bool(m and gm and gm != m and cur not in its)
                h.setHidden(away)
                off = away or (name in shut and cur not in its)
                for it in its: it.setHidden(off)
                h.setText(name + ('　▸ ' + str(len(its)) if off and not away else ''))
        except Exception: pass

    def _clicked(self, item):
        try:
            if item is None or int(item.data(Qt.UserRole)) >= 0: return
            name = item.text().split('　')[0]; v = ENG.cfg.get('nav_shut5')
            man = set(v) if isinstance(v, list) else {'HotZone 檔案與硬碟', '設定與說明'}
            if name in self._shut(): man.discard(name); self._seen(name)        # 打開：當作剛用過（不會又被自動收）
            else: man.add(name)
            ENG.cfg.set('nav_shut5', sorted(man)); self.apply_collapse()
            cur = self._items.get(self._page)
            if cur is not None: QListWidget.setCurrentItem(self, cur)                # 點標題不要把選到的那頁取消掉
        except Exception: pass


class SiftBadge(QWidget):
    """左上角：狀態小圓點＋大大的綠色數字（還沒分級幾部）＋ / N 部待整理（照 TikLive 的「● 3 / 12 直播間」）."""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent); self.big = 0; self.tot = 0; self.color = '#7f8a99'; self.setFixedHeight(40); self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_counts(self, big, tot, color, tip=''):
        if (big, tot, color) != (self.big, self.tot, self.color): self.big, self.tot, self.color = big, tot, color; self.update()
        if tip: self.setToolTip(tip)

    def sizeHint(self): return QSize(200, 40)

    def mousePressEvent(self, e): self.clicked.emit()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); h = self.height()
        t = f'{self.big:,}'; sub = f'/ {self.tot:,} 部待分級'; W = self.width()
        bp = max(18, int(h * 0.9)); sp = max(10, int(h * 0.32))
        while True:                                                              # 側邊欄窄的時候字自動縮小，數字不會被切掉
            big = QFont(self.font()); big.setBold(True); big.setPixelSize(bp); fmb = QFontMetrics(big)
            sm = QFont(self.font()); sm.setBold(True); sm.setPixelSize(sp); fms = QFontMetrics(sm)
            need = 3 + fms.ascent() * 0.72 + 5 + fmb.horizontalAdvance(t) + 6 + fms.horizontalAdvance(sub)
            if need <= W or bp <= 16:
                if need > W: sub = f'/ {self.tot:,}'
                break
            bp -= 2; sp = max(9, sp - (1 if bp % 4 == 0 else 0))
        base = h / 2 + fmb.ascent() * 0.36; dot = fms.ascent() * 0.72; x = 3
        p.setPen(Qt.NoPen); p.setBrush(QColor(self.color)); p.drawEllipse(QRectF(x, base - fms.ascent() * 0.5 - dot / 2 - 1, dot, dot))
        x += dot + 5; p.setFont(big); p.setPen(QColor('#45d483')); bw = fmb.horizontalAdvance(t); p.drawText(QRectF(x, 0, bw + 4, base + 2), Qt.AlignLeft | Qt.AlignBottom, t)
        x += bw + 6; p.setFont(sm); p.setPen(TC('text')); p.drawText(QRectF(x, 0, max(10, self.width() - x), base), Qt.AlignLeft | Qt.AlignBottom, sub)
        p.end()


class SysPanel(QWidget):
    """左下角電腦狀態：每項一列（名稱、彩色進度條、數值、溫度），點一下打開效能浮窗（照 TikLive）."""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent); self.rows = []; self.setCursor(Qt.PointingHandCursor); self.setMinimumHeight(40)

    def set_rows(self, rows):
        if rows != self.rows: self.rows = rows; self.setFixedHeight(10 + 19 * max(1, len(rows))); self.update()

    def mousePressEvent(self, e): self.clicked.emit()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True); W = self.width()
        p.setPen(QPen(TC('border'), 1)); p.setBrush(TC('card')); p.drawRoundedRect(QRectF(0.5, 0.5, W - 1, self.height() - 1), 9, 9)
        f = QFont(self.font()); f.setPointSizeF(8.2); p.setFont(f); fb = QFont(f); fb.setBold(True)
        lw, vw, tw = 40, 46, 30; bx = 8 + lw; bw = max(20, W - 8 - lw - vw - tw - 10)
        if not self.rows:
            p.setPen(TC('subtext')); p.drawText(self.rect(), Qt.AlignCenter, '電腦狀態讀取中…'); p.end(); return
        for i, (lab, pct, val, temp, col, busy) in enumerate(self.rows):
            y = 5 + i * 19; cy = y + 9.5
            p.setFont(fb); p.setPen(TC('subtext')); p.drawText(QRectF(8, y, lw, 19), Qt.AlignLeft | Qt.AlignVCenter, lab)
            if pct is not None:
                p.setPen(Qt.NoPen); p.setBrush(TC('track')); p.drawRoundedRect(QRectF(bx, cy - 3, bw, 6), 3, 3)
                p.setBrush(QColor(col)); p.drawRoundedRect(QRectF(bx, cy - 3, max(3.0, bw * min(100.0, max(0.0, pct)) / 100.0), 6), 3, 3)
                if busy is not None:
                    p.setBrush(QColor('#f0ad4e' if busy >= 60 else '#4dc9ff')); p.drawRoundedRect(QRectF(bx, cy + 4, max(1.5, bw * min(100.0, busy) / 100.0), 2), 1, 1)
            p.setFont(fb); p.setPen(TC('text_strong')); p.drawText(QRectF(bx + bw + 4, y, vw, 19), Qt.AlignRight | Qt.AlignVCenter, val)
            if temp:
                p.setPen(QColor('#ff5c5c' if temp >= 85 else '#f0ad4e' if temp >= 70 else '#45d483')); p.setFont(f)
                p.drawText(QRectF(W - 8 - tw, y, tw, 19), Qt.AlignRight | Qt.AlignVCenter, f'{temp:.0f}°')
        p.end()


# ============================================================ 開機封面（不露出任何私人內容；你按了才進去）
class CoverPage(QWidget):
    COVER_BTNS = [(44, '①', '檔案管理', '16 格快速分類到資料夾', '#2f9bff'), (0, '②', '檔案剪輯', '每 10 秒一張・分級・初剪', '#4dc9ff'),
                  (1, '③', '畫質降容量', '轉 H.265・SSIM 畫質目標', '#f0ad4e'), (49, '④', '隔離區・壞檔', '損毀檢查・修復・隔離', '#ff6b6b'),
                  (47, '⑤', '重複檔案', '指紋比對・最佳解', '#b48cff'), (53, '⑥', '照片分類', '相似・日期・地圖・活動', '#ff7eb6'),
                  (2, '🖥', '後台', '背景工作・硬碟狀態', '#45d483'), (3, '⚙', '設定', 'SortCut／整理／HotZone', '#9aa5b3')]   # V0.5.09 照工作流程

    def __init__(self, win):
        super().__init__(); self.win = win; self.t0 = time.time()
        v = QVBoxLayout(self); v.setContentsMargins(40, 0, 40, 24); v.addStretch(5)
        self.resume = QPushButton(''); self.resume.setCursor(Qt.PointingHandCursor); self.resume.setMinimumHeight(48)
        self.resume.setStyleSheet('QPushButton{background:rgba(77,201,255,0.18);border:1px solid #4dc9ff;border-radius:24px;font-size:16px;font-weight:700;padding:8px 28px;color:#ffffff}'
                                  'QPushButton:hover{background:rgba(77,201,255,0.32)}')
        rr = QHBoxLayout(); rr.addStretch(1); rr.addWidget(self.resume); rr.addStretch(1); v.addLayout(rr); v.addSpacing(8)
        self.qw = QWidget(); self.qw.setStyleSheet('background:transparent'); self.ql = QHBoxLayout(self.qw); self.ql.setContentsMargins(0, 0, 0, 0)   # V0.3.06 ⭐🕘 快捷
        qr_ = QHBoxLayout(); qr_.addStretch(1); qr_.addWidget(self.qw); qr_.addStretch(1); v.addLayout(qr_); v.addSpacing(14)
        grid = QGridLayout(); grid.setHorizontalSpacing(14); grid.setVerticalSpacing(14); self.btns = []
        for k, (page, ic, name, sub, col) in enumerate(self.COVER_BTNS):
            b = QPushButton(f'{ic}  {name}' + (f'\n{sub}' if sub else '')); b.setCursor(Qt.PointingHandCursor); b.setMinimumSize(200, 92)
            b.setStyleSheet(f'QPushButton{{background:rgba(20,28,40,0.72);border:1px solid rgba(120,160,210,0.30);border-top:3px solid {col};border-radius:16px;font-size:13px;color:#dfe9f5;padding:10px}}'
                            f'QPushButton:hover{{background:rgba(40,60,90,0.85);border-color:{col};color:#ffffff}}')
            b.clicked.connect(lambda _c=False, page=page: self.win.enter(page)); grid.addWidget(b, k // 4, k % 4); self.btns.append(b)
        gw = QWidget(); gw.setLayout(grid); gw.setStyleSheet('background:transparent'); gr = QHBoxLayout(); gr.addStretch(1); gr.addWidget(gw); gr.addStretch(1); v.addLayout(gr)
        v.addStretch(3)
        self.info = QLabel(''); self.info.setAlignment(Qt.AlignCenter); self.info.setStyleSheet('QLabel{color:#7f93ab;font-size:12px;background:transparent}'); v.addWidget(self.info)
        self.hint = QLabel('Ctrl+L 或上方「🏠 封面」隨時回到這裡　·　不會顯示任何影片內容'); self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet('QLabel{color:#4f6178;font-size:11px;background:transparent}'); v.addWidget(self.hint)
        self.resume.clicked.connect(lambda: self.win.enter(int(ENG.cfg.get('last_page') or 0)))
        self.tm = QTimer(self); self.tm.timeout.connect(self._tick); self.tm.start(1000)

    def showEvent(self, e):
        super().showEvent(e); self.refresh()

    def refresh(self):
        lp = int(ENG.cfg.get('last_page') or 0); nm_ = NavList.NAMES.get(lp)
        self.resume.setText(f'↩  進入（上次停在：{(nm_[0] + " " + nm_[1]) if nm_ else "檔案總管"}）'); self.resume.setFocus(); self._tick()
        try: self._quick()
        except Exception: pass

    def _tick(self):
        if not self.isVisible(): return
        self.update()
        if ENG.cfg.get('cover_stats') is False: self.info.setText(''); return
        bg(ENG.info, self._info)

    def _quick(self):
        """V0.3.06 封面上一排 ⭐ 常用篩選、🕘 最近資料夾（只有名字），一按就進去."""
        while self.ql.count():
            it = self.ql.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        L = lab_cfg(); B = []
        if L.get('views'): B += [(f'⭐ {v["name"]}', lambda v=v: (self.win.enter(0), self.win.browse.use_view(v))) for v in ENG.views()[-5:][::-1]]
        LF = ENG.last_file() if L.get('recent_dirs') else None
        if LF: B.append((f"⏯ 繼續：{LF['name'][:24]}", lambda LF=LF: (self.win.enter(0), self.win.browse.goto_file(LF['id']))))   # V0.3.38
        try:                                                                    # V0.4.13 📌 工具箱釘選的
            NM_ = {k: n for k, n, _d, _v in NEW_LABS}; A_ = self.win.toolp.acts()
            B += [(f'📌 {NM_[k]}', lambda k=k: self.win.toolp.use(k)) for k in (ENG.cfg.get('pin_tools') or []) if k in NM_ and k in A_]
        except Exception: pass
        UL_ = ENG.up_left() if L.get('copy_to') else 0                        # V0.3.65 📤 S／A 還沒傳幾部，一按就列出來
        UP_ = ENG.unpub_n() if L.get('copy_to') else 0                        # V0.4.36 ⬜ 複製了還沒發佈
        if UP_: B.append((f'⬜ 還沒發佈 {UP_:,} 部', lambda: (self.win.enter(0), self.win.browse.use_view({'name': '⬜ 複製了還沒發佈', 'folder': '', 'flt': 'notpub', 'sort': 'up_t', 'sub': True}))))
        if UL_: B.append((f'📤 還沒上傳 {UL_:,} 部', lambda: (self.win.enter(0), self.win.browse.use_view({'name': '📤 S／A 還沒上傳', 'folder': '', 'flt': 'notup', 'sort': 'grade', 'sub': True}))))
        if L.get('recent_dirs'): B += [(f'🕘 {Path(f).name or f}', lambda f=f: (self.win.enter(0), self.win.browse._sel_folder(f), self.win.browse.load_list())) for f in ENG.recent_list()[:4]]
        for t_, fn in B:
            b = QPushButton(t_); b.setCursor(Qt.PointingHandCursor); b.clicked.connect(fn)
            b.setStyleSheet('QPushButton{background:rgba(20,28,40,0.72);border:1px solid rgba(120,160,210,0.35);border-radius:14px;font-size:12px;color:#dfe9f5;padding:4px 12px}QPushButton:hover{border-color:#4dc9ff}')
            self.ql.addWidget(b)
        self.qw.setVisible(bool(B))

    def _info(self, I):
        if not self.isVisible() or ENG.cfg.get('cover_stats') is False: return
        th = len(ENG.th_active); cv = len(ENG.cv_active); tot = I['th_done'] + I['th_left']
        busy = []
        if th: busy.append(f'預覽圖做中 {th}')
        if cv or I['cv_wait']: busy.append(f'轉檔 {cv} 部（排隊 {I["cv_wait"]}）')
        if ENG.cut_q or ENG.cut_cur: busy.append('初剪中')
        if ENG.scan_st.get('running'): busy.append('掃描中')
        if ENG.boosted(): busy.append('🚀 加速中')
        try:                                                                    # V0.5.60 整理（FileCompare）在做的也寫（只有項目名稱）
            f_ = ENG.fc_bg() if hasattr(ENG, 'fc_bg') else None
            if isinstance(f_, dict) and f_['run']: busy.append('🗂 整理：' + '、'.join(x.split(' ', 1)[-1] for x in f_['run'][:3]))
        except Exception: pass
        if I.get('th_eta') and I['th_left']: busy.append(f'預覽圖預計還要 {eta_txt(I["th_eta"])}')
        ex = []                                                                 # V0.2.95 封面也看得到：今天目標、空間提醒、上傳複製（只有數字，不露影片內容）
        try:
            G = getattr(ENG, '_goal_c', None)
            if lab_cfg().get('goal') and G: ex.append(f"{'🎉' if G[1]['done'] else '🎯'} 今天 {G[1]['n']:,}／{G[1]['goal']:,}")
            DW = ENG.disk_warn() if lab_cfg().get('disk_warn') else []
            if DW: ex.append('⚠ ' + '、'.join(f'{x["d"]} 剩 {fmt_b(x["free"])}' for x in DW))
            C = ENG.copy_view() if lab_cfg().get('copy_to') else None
            if C and (C['run'] or C['q']): ex.append(f"📤 複製中・還有 {C['q']}")
        except Exception: pass
        self.info.setText(f'影片庫 {I["files"]:,} 部 · {fmt_b(I["bytes"])} · 預覽圖完成 {(I["th_done"] / tot * 100) if tot else 100:.0f}%　　'
                          + ('背景：' + '、'.join(busy) if busy else '背景閒置') + (('　　' + '　'.join(ex)) if ex else ''))

    def paintEvent(self, e):
        if lab_cfg().get('cover_b'): return self._paint_b()
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); W, H = self.width(), self.height()
        g = QLinearGradient(0, 0, W, H); g.setColorAt(0, QColor('#070b12')); g.setColorAt(0.55, QColor('#0f1a2b')); g.setColorAt(1, QColor('#1a1430')); p.fillRect(self.rect(), g)
        ph = (time.time() - self.t0) * 0.15                                     # 很慢的光暈飄動
        for cx, cy, r, col in ((0.25 + 0.04 * math.sin(ph), 0.28, 0.55, QColor(77, 201, 255, 46)), (0.78, 0.7 + 0.04 * math.cos(ph * 1.3), 0.5, QColor(180, 140, 255, 40))):
            rg = QRadialGradient(W * cx, H * cy, max(W, H) * r); rg.setColorAt(0, col); rg.setColorAt(1, QColor(0, 0, 0, 0)); p.fillRect(self.rect(), rg)
        p.save(); p.translate(W * 0.5, H * 0.86); p.rotate(-7)                  # 斜斜的膠卷帶
        fw = W * 1.6; fh = 64; p.setPen(Qt.NoPen); p.setBrush(QColor(255, 255, 255, 10)); p.drawRect(QRectF(-fw / 2, -fh / 2, fw, fh))
        p.setBrush(QColor(255, 255, 255, 22)); step = 34; off = (ph * 40) % step
        x = -fw / 2 + off
        while x < fw / 2:
            p.drawRoundedRect(QRectF(x, -fh / 2 + 6, 16, 9), 2, 2); p.drawRoundedRect(QRectF(x, fh / 2 - 15, 16, 9), 2, 2); x += step
        p.setBrush(QColor(255, 255, 255, 12)); x = -fw / 2 + off * 0.5
        while x < fw / 2: p.drawRoundedRect(QRectF(x, -fh / 2 + 19, 88, 26), 4, 4); x += 104
        p.restore()
        cy = H * 0.2; lw = 74                                                   # 標誌：圓角方塊＋播放三角形
        R = QRectF(W / 2 - lw / 2, cy - lw / 2, lw, lw); lg = QLinearGradient(R.topLeft(), R.bottomRight()); lg.setColorAt(0, QColor('#4dc9ff')); lg.setColorAt(1, QColor('#8b6cff'))
        p.setBrush(lg); p.setPen(Qt.NoPen); p.drawRoundedRect(R, 20, 20)
        tri = QPainterPath(); tri.moveTo(W / 2 - 11, cy - 17); tri.lineTo(W / 2 + 19, cy); tri.lineTo(W / 2 - 11, cy + 17); tri.closeSubpath(); p.setBrush(QColor('#0b0e13')); p.drawPath(tri)
        f = QFont(); f.setPixelSize(52); f.setBold(True); f.setLetterSpacing(QFont.AbsoluteSpacing, 3); p.setFont(f); p.setPen(QColor('#f2f6fb'))
        p.drawText(QRectF(0, cy + lw / 2 + 10, W, 66), Qt.AlignCenter, 'SortCut')
        f2 = QFont(); f2.setPixelSize(15); f2.setLetterSpacing(QFont.AbsoluteSpacing, 6); p.setFont(f2); p.setPen(QColor('#8ea4bf'))
        p.drawText(QRectF(0, cy + lw / 2 + 76, W, 24), Qt.AlignCenter, f'影片初剪整理　·　V{APP_VERSION}')
        try:                                                                    # V0.2.27 這是哪一台電腦
            f4 = QFont(); f4.setPixelSize(17); f4.setBold(True); p.setFont(f4); p.setPen(QColor(ENG.pc_color()))
            p.drawText(QRectF(0, cy + lw / 2 + 106, W, 26), Qt.AlignCenter, f'●  {ENG.pc_name()}')
        except Exception: pass
        f3 = QFont(); f3.setPixelSize(13); p.setFont(f3); p.setPen(QColor('#9fb3c8'))
        wd = '一二三四五六日'[time.localtime().tm_wday]
        p.drawText(QRectF(0, 18, W - 28, 20), Qt.AlignRight | Qt.AlignVCenter, time.strftime('%Y-%m-%d') + f'（{wd}）　' + time.strftime('%H:%M'))
        p.end()


def _cover_paint_b(self):
    """🧪 封面樣式 B：極簡大時鐘（深紫漸層、左上小標誌）."""
    p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); W, H = self.width(), self.height()
    g = QLinearGradient(0, 0, 0, H); g.setColorAt(0, QColor('#120a24')); g.setColorAt(1, QColor('#04050a')); p.fillRect(self.rect(), g)
    rg = QRadialGradient(W * 0.5, H * 0.32, max(W, H) * 0.45); rg.setColorAt(0, QColor(139, 108, 255, 55)); rg.setColorAt(1, QColor(0, 0, 0, 0)); p.fillRect(self.rect(), rg)
    R = QRectF(24, 20, 34, 34); lg = QLinearGradient(R.topLeft(), R.bottomRight()); lg.setColorAt(0, QColor('#4dc9ff')); lg.setColorAt(1, QColor('#8b6cff'))
    p.setPen(Qt.NoPen); p.setBrush(lg); p.drawRoundedRect(R, 9, 9)
    tri = QPainterPath(); tri.moveTo(36, 29); tri.lineTo(49, 37); tri.lineTo(36, 45); tri.closeSubpath(); p.setBrush(QColor('#0b0e13')); p.drawPath(tri)
    f = QFont(); f.setPixelSize(17); f.setBold(True); p.setFont(f); p.setPen(QColor('#e8ecf5')); p.drawText(QRectF(68, 20, 300, 34), Qt.AlignLeft | Qt.AlignVCenter, f'SortCut  V{APP_VERSION}')
    f = QFont(); f.setPixelSize(int(min(W, H) * 0.2)); f.setWeight(QFont.Light); p.setFont(f); p.setPen(QColor('#f4f1ff'))
    p.drawText(QRectF(0, H * 0.12, W, H * 0.26), Qt.AlignCenter, time.strftime('%H:%M'))
    f2 = QFont(); f2.setPixelSize(18); f2.setLetterSpacing(QFont.AbsoluteSpacing, 4); p.setFont(f2); p.setPen(QColor('#a99bd6'))
    wd = '一二三四五六日'[time.localtime().tm_wday]; p.drawText(QRectF(0, H * 0.38, W, 30), Qt.AlignCenter, (lambda t_: f'{t_.tm_year} 年 {t_.tm_mon:02d} 月 {t_.tm_mday:02d} 日')(time.localtime()) + f'　星期{wd}')
    p.end()


CoverPage._paint_b = _cover_paint_b


# ============================================================ 主視窗
def app_icon():
    """V0.1.58 新圖示（資料夾＋放大鏡）：先用更新包裡的 app\\VideoSift.ico（熱更新就換好），也順便換掉程式資料夾的 VideoSift.ico（捷徑用那個的話下次就是新的）."""
    try:
        new = HERE / 'VideoSift.ico'
        if new.exists():
            try:
                old = ROOT / 'VideoSift.ico'
                if not old.exists() or old.read_bytes() != new.read_bytes(): shutil.copyfile(str(new), str(old)); ENG.log.w(f'圖示：{old} 換成新的')
            except Exception: pass
            ic = QIcon(str(new))
            for p_ in ('vs_icon_512.png', 'vs_icon_192.png'):
                if (HERE / p_).exists(): ic.addFile(str(HERE / p_))
            return ic
        old = ROOT / 'VideoSift.ico'
        if old.exists(): return QIcon(str(old))
    except Exception:
        try: ENG.log.err('讀圖示')
        except Exception: pass
    return QIcon()


def pc_badge(icon):
    """V0.2.27 圖示右下角加這台電腦的顏色＋名稱第一個字（兩台都裝時，工作列、托盤看得出是哪一台）."""
    try:
        pm = icon.pixmap(256, 256)
        if pm.isNull(): return icon
        p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(140, 140, 112, 112); p.setPen(QPen(QColor('#0b0e13'), 10)); p.setBrush(QColor(ENG.pc_color())); p.drawEllipse(r)
        f = QFont(); f.setPixelSize(62); f.setBold(True); p.setFont(f); p.setPen(QColor('#0b0e13')); p.drawText(r, Qt.AlignCenter, (ENG.pc_name() or '?')[:1].upper())
        p.end(); return QIcon(pm)
    except Exception:
        try: ENG.log.err('圖示加上電腦名稱')
        except Exception: pass
        return icon


class WheelBoost(QObject):
    """V0.6.34 滾輪速度＋絲滑（參考 TikLive V1.1.29／1.1.31）：所有可以捲的清單、方格、頁面都套用.
    cfg wheel_mult＝倍數（×0.5～×8），wheel_smooth＝緩進緩出動畫。Ctrl／Alt／Shift＋滾輪、觸控板照舊（各自的放大縮小功能不受影響）."""
    STEPS = [0.5, 0.75, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 8]

    def __init__(self):
        super().__init__(); self.an = {}; self.tm = QTimer(self); self.tm.setInterval(12); self.tm.timeout.connect(self._tick)

    @staticmethod
    def mult():
        try: return max(0.5, min(8.0, float(ENG.cfg.get('wheel_mult') or 1)))
        except Exception: return 1.0

    @staticmethod
    def smooth(): return ENG.cfg.get('wheel_smooth') is not False

    def eventFilter(self, obj, e):
        try:
            if e.type() != QEvent.Wheel: return False
            m, sm = self.mult(), self.smooth()
            if m == 1 and not sm: return False
            if e.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.ShiftModifier): return False
            if not e.pixelDelta().isNull(): return False                     # 觸控板：系統本來就是順的
            area = obj.parent() if obj is not None else None
            if not isinstance(area, QAbstractScrollArea) or area.viewport() is not obj: return False
            dy = e.angleDelta().y()
            if not dy: return False
            sb = area.verticalScrollBar()
            if sb is None or sb.maximum() <= sb.minimum() or not sb.isEnabled(): return False
            lines = max(1, QApplication.wheelScrollLines())
            if isinstance(area, QAbstractItemView) and area.verticalScrollMode() == QAbstractItemView.ScrollPerItem:
                d = -round(dy / 120 * lines * m) or (-1 if dy > 0 else 1); sb.setValue(sb.value() + d); return True
            d = -dy / 120.0 * max(sb.singleStep(), 20) * lines * m
            A = self.an.get(sb); cur = A['to'] if A else sb.value()
            if (d < 0 and cur <= sb.minimum()) or (d > 0 and cur >= sb.maximum()): return False   # 到底了：讓外面那層捲
            to = max(sb.minimum(), min(sb.maximum(), cur + d))
            if not sm: sb.setValue(int(round(to))); return True
            import time as _t
            now = _t.monotonic()
            if A: A.update(fr=float(sb.value()), to=to, t0=now, dur=0.22, io=False)      # 連續滾：中途接著加、只緩出
            else: self.an[sb] = {'fr': float(sb.value()), 'to': to, 't0': now, 'dur': 0.30, 'io': True}
            if not self.tm.isActive(): self.tm.start()
            return True
        except Exception: return False

    def _tick(self):
        import time as _t
        now = _t.monotonic()
        for sb, A in list(self.an.items()):
            try:
                t = min(1.0, (now - A['t0']) / A['dur'])
                k = (2 * t * t if t < .5 else 1 - (-2 * t + 2) ** 2 / 2) if A['io'] else 1 - (1 - t) ** 3
                sb.setValue(int(round(A['fr'] + (A['to'] - A['fr']) * k)))
                if t >= 1: self.an.pop(sb, None)
            except Exception: self.an.pop(sb, None)                             # 那個清單關掉了
        if not self.an: self.tm.stop()


def timed_box(parent, title, text, secs=10):
    """V0.6.34 不擋畫面的通知（參考 TikLive V1.1.34）：「確定（N 秒後自動關閉）」倒數，也可以直接按."""
    try:
        mb = QMessageBox(parent); mb.setWindowTitle(title); mb.setText(text); mb.setIcon(QMessageBox.Information); mb.setModal(False)
        mb.setAttribute(Qt.WA_DeleteOnClose, True); b = mb.addButton('確定', QMessageBox.AcceptRole); left = [int(secs)]
        def tick():
            left[0] -= 1
            try:
                if left[0] <= 0: mb.close(); return
                b.setText(f'確定（{left[0]} 秒後自動關閉）')
            except Exception: return
            QTimer.singleShot(1000, tick)
        b.setText(f'確定（{left[0]} 秒後自動關閉）'); mb.show(); QTimer.singleShot(1000, tick); return mb
    except Exception: return None


def wheel_install():
    """裝到整個程式（熱更新時把舊的換掉）."""
    app = QApplication.instance()
    if app is None: return
    old = getattr(app, '_vs_wheel', None)
    if old is not None:
        try: app.removeEventFilter(old)
        except Exception: pass
    W = WheelBoost(); app.installEventFilter(W); app._vs_wheel = W


class Main(QMainWindow):
    def __init__(self, adopt=None):
        try: QApplication.instance().setStyleSheet(theme_qss(ENG.cfg.get('ui_theme') or 'dark', ENG.cfg.get('ui_zoom') or 100))   # V0.1.53 TikLive 樣式（熱更新也馬上換）
        except Exception: pass
        try: wheel_install()                                                     # V0.6.34 滾輪速度＋絲滑
        except Exception: pass
        super().__init__(); self.setWindowTitle(f'{APP_TITLE}  V{APP_VERSION}'); self.resize(1500, 920); self.quitting = False; self._handoff = False; self._upd_seen = set()
        self.icon0 = app_icon()
        if self.icon0.isNull(): self.icon0 = self._mk_icon()
        self.icon = pc_badge(self.icon0); self.setWindowIcon(self.icon); self.setWindowTitle(f'{APP_TITLE}  V{APP_VERSION}  ·  {ENG.pc_name()}')
        try: QApplication.instance().setWindowIcon(self.icon)                   # 播放器、比較視窗等也用同一個
        except Exception: pass
        cw = QWidget(); self.setCentralWidget(cw); v = QVBoxLayout(cw); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        self.outer = QStackedWidget(); v.addWidget(self.outer, 1); self.mainw = QWidget(); mv = QVBoxLayout(self.mainw); mv.setContentsMargins(0, 0, 0, 0); mv.setSpacing(0)
        self._cover_ready = False
        # ---- V0.1.53 版面照 TikLive：左邊側邊欄（大數字、開始／暫停、分組選單、電腦狀態、排隊按鈕）＋右邊內容
        split = QSplitter(Qt.Horizontal); split.setChildrenCollapsible(False); mv.addWidget(split, 1); self.main_split = split
        side = QFrame(); side.setObjectName('side'); side.setMinimumWidth(180); side.setMaximumWidth(300); self.side_frame = side
        sl = QVBoxLayout(side); sl.setContentsMargins(10, 6, 10, 10); sl.setSpacing(5)
        # V0.1.59 左上角的大數字和「開始整理／暫停背景」拿掉（使用者不要），選單直接從最上面開始；元件留著但不放進版面（其他地方還會更新它們）
        self.badge = SiftBadge(side); self.badge.hide(); self.badge.clicked.connect(lambda: (self.nav.setCurrentRow(0), self.browse._chip('nograde')))
        self.b_go = QPushButton('▶ 開始整理', side); self.b_go.setObjectName('side_start'); self.b_go.hide()
        self.b_pause = QPushButton('■ 暫停背景', side); self.b_pause.setObjectName('side_stop'); self.b_pause.hide()
        self.b_go.clicked.connect(lambda: self._bg_all(False)); self.b_pause.clicked.connect(lambda: self._bg_all(True))
        self.msw = ModeSwitch(self.set_mode); sl.addWidget(self.msw)                        # V0.5.70 🎛 SortCut／FileCompare／H265 三段切換
        self.nav = NavList(self._page); sl.addWidget(self.nav, 1)
        try:
            m_ = str(ENG.cfg.get('nav_mode') or 'vs'); m_ = m_ if m_ in MODE_COL else 'vs'; self.nav.mode = m_; self.msw.set(m_)
        except Exception: self.nav.mode = 'vs'
        self.sys_panel = SysPanel(); self.sys_panel.setToolTip('電腦狀態：點一下打開／關掉「📊 效能」浮窗'); sl.addWidget(self.sys_panel)
        self.b_thq = QPushButton('🖼 預覽圖：讀取中…'); self.b_thq.setObjectName('net_btn'); self.b_thq.setToolTip('預覽圖做到哪、還要多久\n點一下看後台狀態'); sl.addWidget(self.b_thq)
        self.b_jobs = BadgeButton('✂ 剪輯／轉檔'); self.b_jobs.setObjectName('net_btn'); self.b_jobs.setToolTip('初剪、轉檔的進度和規則\n紅色數字＝新出的初剪檔（打開歸零）　藍色數字＝進行中／排隊'); self.jobs_pop = None; self._cut_was = 0
        sl.addWidget(self.b_jobs)
        self.b_thq.clicked.connect(lambda: self.nav.setCurrentRow(2))
        split.addWidget(side)
        content = QWidget(); cv_ = QVBoxLayout(content); cv_.setContentsMargins(0, 0, 0, 0); cv_.setSpacing(0)
        topf = QFrame(); topf.setObjectName('topbar'); top = QHBoxLayout(topf); top.setContentsMargins(12, 7, 10, 7); top.setSpacing(6); cv_.addWidget(topf)
        self.ptitle = QLabel('▦ 檔案總管'); self.ptitle.setObjectName('ptitle'); top.addWidget(self.ptitle)
        self.stat = QLabel(''); self.stat.setObjectName('muted'); self.stat.setMinimumWidth(10); top.addWidget(self.stat, 1)
        self.goal_l = QLabel(''); self.goal_l.setVisible(False); self.goal_l.setToolTip('🧪 每日整理目標：今天分級了幾部（實驗工作區可以改目標或關掉）'); top.addWidget(self.goal_l)
        self.b_perf = QPushButton('📊 效能'); self.b_perf.setCheckable(True); self.b_perf.setToolTip('電腦效能浮窗（左下角電腦狀態點一下也可以）')
        self.b_bg = QPushButton('🖥 後台'); self.b_hide = QPushButton('🌙 縮到背景'); self.b_hide.setToolTip('縮到右下角，預覽圖和轉檔在背景繼續做')
        self.b_cover = QPushButton('🏠 封面'); self.b_cover.setToolTip('回到封面（Ctrl+L）：畫面上不留任何影片內容，背景照常做')
        for b_ in (self.b_perf, self.b_bg, self.b_hide, self.b_cover): b_.setObjectName('pill'); top.addWidget(b_)
        self.lv = LvBadge(); self.lv.clicked.connect(self.open_yield); top.addWidget(self.lv)            # V0.5.71 🤝 右上角 Lv 1～10（讓路給 TikLive）
        self._lv_t = QTimer(self); self._lv_t.timeout.connect(self._lv_tick); self._lv_t.start(2000)
        self.b_cover.clicked.connect(self.show_cover)
        self.b_jobs.clicked.connect(self.open_jobs)
        self.stack = QStackedWidget(); cv_.addWidget(self.stack, 1)
        split.addWidget(content); split.setStretchFactor(1, 1)
        try:
            sz = ENG.cfg.get('side_w'); split.setSizes([int(sz) if sz else 210, 1290])
        except Exception: pass
        self._sw_t = QTimer(self); self._sw_t.setSingleShot(True); self._sw_t.timeout.connect(lambda: ENG.cfg.set('side_w', int(split.sizes()[0])))
        split.splitterMoved.connect(lambda *_a: self._sw_t.start(600)) if hasattr(split, 'splitterMoved') else None
        self.sys_panel.clicked.connect(lambda: self.b_perf.toggle())
        self.browse = BrowsePage(self); self.conv = ConvPage(self); self.bgp = BgPage(self); self.setp = SetPage(self); self.logp = LogPage(self); self.upd = UpdPage(self)
        self.opsp = OpsPage(self); self.lab = LabPage(self); self.helpp = HelpPage(self); self.people = PeoplePage(self)
        self.hzp = HotZonePage(self); self.hzembed = HZEmbedPage(self)
        try:
            if getattr(ENG, 'hz', None) is not None: ENG.hz.ui_before = self._hz_before   # 手機按整合時也能先關掉嵌著的 HotZone 畫面
        except Exception: pass
        for w in (self.browse, self.conv, self.bgp, self.setp, self.logp, self.upd, self.opsp, self.lab, self.helpp, self.people, QWidget(), self.hzp):     # 第 10 頁是「分級」（用檔案總管），佔個位
            self.stack.addWidget(w if w is self.browse else scroll_wrap(w))          # V0.1.53 每一頁都不會把視窗撐寬（太窄就出現捲軸）
        self.stack.addWidget(self.hzembed)                                       # 第 12 個：HotZone 的各頁（嵌進來的 HotZone 畫面）
        self.brtest = BrTestPage(self); self.stack.addWidget(scroll_wrap(self.brtest))   # 第 13 個：🧪 碼率測試（V0.1.60）
        self.learnp = LearnPage(self); self.stack.addWidget(scroll_wrap(self.learnp))     # 第 14 個：📈 滾動式參數（V0.1.65）
        self.movep = MovePage(self); self.stack.addWidget(scroll_wrap(self.movep))       # 第 15 個：🚚 搬硬碟（V0.2.28）
        self.toolp = ToolboxPage(self); self.stack.addWidget(scroll_wrap(self.toolp))    # 第 16 個：🧰 新功能工具箱（V0.2.52）
        self.fcp = FCEmbedPage(self); self.stack.addWidget(self.fcp)                     # 第 17 個：🗂 整理（FileCompare 整套，V0.5.00）
        self.dash = DashPage(self); self.stack.addWidget(self.dash)                       # 第 18 個：📊 一頁總覽（SortCut／FileCompare／H265，V0.5.70）
        self.rsp = RSplitPage(self); self.stack.addWidget(scroll_wrap(self.rsp))           # 第 19 個：🚚 R 碟清空搬移（V0.5.85）
        self.explore = ExplorePage(self); self.stack.addWidget(self.explore)                 # 第 20 個：🗺 檔案總覽（V0.6.19）
        self.stack.setMinimumWidth(420); self.stat.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.nav.setCurrentRow(0)
        self.b_bg.clicked.connect(lambda: self.nav.setCurrentRow(2)); self.b_hide.clicked.connect(self.to_tray); self.b_perf.toggled.connect(self.perf)
        # ---- 下面狀態列（照 TikLive）：深色／淺色、介面大小
        sb = self.statusBar(); self.b_theme = QPushButton('◐ 深色／淺色'); self.b_theme.setObjectName('pill'); self.b_theme.setToolTip('切換深色／淺色主題')
        self.b_zm = QPushButton('－'); self.b_zp = QPushButton('＋'); self.zoom_l = QLabel(''); self.zoom_l.setObjectName('muted')
        for b_ in (self.b_zm, self.b_zp): b_.setObjectName('pill'); b_.setFixedWidth(34)
        zl = QLabel('介面大小'); zl.setObjectName('muted')
        self.b_bgst = QPushButton(''); self.b_bgst.setObjectName('pill'); self.b_bgst.setToolTip('後台：暫停中／讓路中的項目（點一下到「後台狀態」總控制）'); self.b_bgst.hide()
        self.b_bgst.clicked.connect(lambda: self.nav.setCurrentRow(2))
        self.b_rep = QPushButton('📈'); self.b_rep.setObjectName('pill'); self.b_rep.setToolTip('🧪 分級報表'); self.b_rep.clicked.connect(self.report_dlg)
        self.b_rep.setVisible(bool(lab_cfg().get('report'))); sb.addPermanentWidget(self.b_rep)
        self.b_goal = QPushButton('🎯'); self.b_goal.setObjectName('pill'); self.b_goal.setToolTip('🧪 今天的分級目標（點一下改目標）'); self.b_goal.clicked.connect(self.goal_dlg)   # V0.2.44
        self.b_goal.setVisible(bool(lab_cfg().get('goal'))); sb.addPermanentWidget(self.b_goal)
        self.b_spr = QPushButton('⏱ 衝刺'); self.b_spr.setObjectName('pill'); self.b_spr.setToolTip('⏱ 分級衝刺：倒數幾分鐘專心分級（🧪）'); self.b_spr.clicked.connect(lambda: self.sprint_dlg()); self.b_spr.hide(); sb.addPermanentWidget(self.b_spr)   # V0.3.72
        self.b_upg = QPushButton(''); self.b_upg.setObjectName('pill'); self.b_upg.setToolTip('📤 今天複製到上傳幾部／每天目標（實驗區「📤 複製到上傳資料夾」的設定裡改）'); self.b_upg.hide(); sb.addPermanentWidget(self.b_upg); self.b_upg.clicked.connect(lambda: self.up_board_dlg())   # V0.3.63
        self.b_pv = QPushButton('🙈'); self.b_pv.setObjectName('pill'); self.b_pv.setCheckable(True); self.b_pv.setToolTip('🧪 隱私模糊：檔案總管的預覽圖全部模糊（Ctrl+Shift+H 切換）'); self.b_pv.toggled.connect(self.set_privacy)   # V0.2.55
        self.b_pv.setVisible(bool(lab_cfg().get('privacy'))); sb.addPermanentWidget(self.b_pv)
        self.b_copy = QPushButton(''); self.b_copy.setObjectName('pill'); self.b_copy.setToolTip('📤 複製到上傳資料夾（點一下打開那個資料夾）'); self.b_copy.hide(); sb.addPermanentWidget(self.b_copy)
        self.b_copy.clicked.connect(lambda: self.up_board_dlg())                    # V0.4.41 點複製進度＝打開上傳看板（佇列在「⋯ 更多」裡）
        for w_ in (self.b_bgst, self.b_theme, zl, self.b_zm, self.zoom_l, self.b_zp): sb.addPermanentWidget(w_)
        sb.setContextMenuPolicy(Qt.CustomContextMenu); sb.customContextMenuRequested.connect(lambda _p: self.pill_menu())   # V0.4.10 狀態列按右鍵＝選要顯示哪些
        self.bgst_t = QTimer(self); self.bgst_t.timeout.connect(self._bgst); self.bgst_t.start(3000)
        QTimer.singleShot(9000, self._week_auto)                                 # V0.3.80 📆
        QTimer.singleShot(5000, self.whats_new)                                  # V0.3.97 🆕
        QTimer.singleShot(7000, self.merge_tour)                                 # V0.5.25 🧭 合併後第一次打開：怎麼用
        self.as_t = QTimer(self); self.as_t.timeout.connect(self._auto_scan); self.as_t.start(60000)   # V0.2.58 👀
        self.still_t = QTimer(self); self.still_t.timeout.connect(self._still_tick); self.still_t.start(3000)   # V0.3.12 😴 背景算靜止比例
        QTimer.singleShot(8000, lambda: ENG.copy_resume() if hasattr(ENG, 'copy_resume') else None)   # V0.2.75 📤 上次沒複製完的接著做
        QTimer.singleShot(5000, self._tour_maybe)                               # V0.3.00 🆕 新功能導覽（只跳一次）
        QTimer.singleShot(12000, lambda: bg(ENG.share_newer, lambda x: self.msg(f"🔄 硬碟 {x['d']}: 上有「{x['pc_name']}」比較新的新功能設定 → 🧪 實驗工作區「📥 從硬碟套用」", 15000) if x and lab_cfg().get('share_auto') else None))   # V0.3.30
        if ENG.cfg.get('privacy_on') and lab_cfg().get('privacy'): QTimer.singleShot(800, lambda: self.set_privacy(True))   # V0.2.55 上次開著就繼續模糊
        self.b_theme.clicked.connect(lambda: self.set_theme('light' if THEME_MODE['mode'] == 'dark' else 'dark'))
        self.b_zm.clicked.connect(lambda: self.set_zoom(THEME_MODE['zoom'] - 10)); self.b_zp.clicked.connect(lambda: self.set_zoom(THEME_MODE['zoom'] + 10))
        self.zoom_l.setText(f"{THEME_MODE['zoom']}%")
        self.pf = None
        if getattr(ENG, 'remap_msg', ''): QTimer.singleShot(2500, lambda: self.msg('💽 ' + ENG.remap_msg, 30000))
        QTimer.singleShot(3000, arm_watchdog)                                   # V0.1.75 閃退自動重開（熱更新上來的、舊版沒開的也會開；已經開了就跳過）
        if ENG.cfg.get('perf_float'): self.b_perf.setChecked(True)
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable() and not SELFTEST:
            self.tray = QSystemTrayIcon(self.icon, self); self.tray_menu = m = QMenu(self)
            m.addAction('顯示視窗', self.from_tray); m.addAction('⏸ 暫停／繼續預覽圖', lambda: self.bgp.b_th.toggle()); m.addSeparator(); m.addAction('結束', self.really_quit)
            self.tray.setContextMenu(m); self.tray.activated.connect(lambda r: self.from_tray() if r in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
            self.tray.setToolTip('SortCut'); self.tray.show()
        self.lag_last = time.time(); self.lag = QTimer(self); self.lag.timeout.connect(self._lag); self.lag.start(500)
        self.st_t = QTimer(self); self.st_t.timeout.connect(self._status); self.st_t.start(1000)
        self.face_t = QTimer(self); self.face_t.timeout.connect(lambda: bg(ENG.faces.tick) if getattr(ENG, 'faces', None) is not None and not self._handoff else None); self.face_t.start(30000)   # 👤 夜間時段、同步人物
        self.hb = QTimer(self); self.hb.timeout.connect(lambda: setattr(QApplication.instance(), '_vs_hb', time.time())); self.hb.start(250)   # 給看門狗：畫面還活著
        try:                                                                    # V0.6.08 🛟 主程式優先：畫面心跳（慢了就叫背景退開）
            import vs_mainfirst; self.mfhb = QTimer(self); self.mfhb.timeout.connect(vs_mainfirst.beat); self.mfhb.start(100); vs_mainfirst.beat()
        except Exception: pass
        # 更新提示列：UPDATE 資料夾裡出現新的更新包
        self.ubar = QFrame(); self.ubar.setStyleSheet('QFrame{background:#1f3550;border-bottom:1px solid #4dc9ff}'); ub = QHBoxLayout(self.ubar); ub.setContentsMargins(10, 4, 10, 4)
        self.ubar_l = QLabel(''); ub.addWidget(self.ubar_l, 1); self.ubar_go = QPushButton('⚡ 立即熱更新'); self.ubar_no = QPushButton('稍後'); ub.addWidget(self.ubar_go); ub.addWidget(self.ubar_no)
        v.insertWidget(0, self.ubar); self.ubar.hide(); self._ubar_path = ''
        self.ubar_go.clicked.connect(self._ubar_apply); self.ubar_no.clicked.connect(self._ubar_later)
        self.ut = QTimer(self); self.ut.timeout.connect(self._watch_update); self.ut.start(5000)
        self._cloud = None; self._cloud_busy = False                              # V0.6.01 ☁ GitHub 雲端更新：開程式 1 分鐘後看一次，之後每 6 小時
        QTimer.singleShot(60000, lambda: self._cloud_check(False))
        self.cut_ = QTimer(self); self.cut_.timeout.connect(lambda: self._cloud_check(False)); self.cut_.start(6 * 3600 * 1000)
        self.cauto_ = QTimer(self); self.cauto_.timeout.connect(lambda: ENG.cfg.get('cloud_auto') is True and self._cloud_check(False)); self.cauto_.start(30 * 60 * 1000)   # V0.6.29 自動熱更新：30 分鐘看一次
        self.cover = CoverPage(self); self.outer.addWidget(self.cover); self.outer.addWidget(self.mainw)
        sc = QShortcut(QKeySequence('Ctrl+L'), self); sc.setContext(Qt.ApplicationShortcut); sc.activated.connect(self.show_cover)
        sck = QShortcut(QKeySequence('Ctrl+K'), self); sck.setContext(Qt.ApplicationShortcut); sck.activated.connect(self.cmd_palette)        # V0.2.30
        scar = QShortcut(QKeySequence('Ctrl+Shift+R'), self); scar.setContext(Qt.ApplicationShortcut); scar.activated.connect(self.open_archive)   # V0.6.06 🗄 封存的功能
        scu = QShortcut(QKeySequence('Ctrl+Shift+U'), self); scu.setContext(Qt.ApplicationShortcut); scu.activated.connect(lambda: self.up_board_dlg() if lab_cfg().get('copy_to') else self.msg('📋 上傳看板要先打開「📤 複製到上傳資料夾」'))   # V0.4.41
        scpv = QShortcut(QKeySequence('Ctrl+Shift+H'), self); scpv.setContext(Qt.ApplicationShortcut); scpv.activated.connect(lambda: self.b_pv.toggle() if lab_cfg().get('privacy') else self.msg('🙈 隱私模糊在 🧪 實驗工作區 →「🆕 新功能」打開'))
        sckh = QShortcut(QKeySequence('Ctrl+/'), self); sckh.setContext(Qt.ApplicationShortcut); sckh.activated.connect(self.keys_dlg)          # V0.2.39
        sc = QShortcut(QKeySequence('F1'), self); sc.activated.connect(lambda: self.enter(8))
        self.last_act = time.time(); ENG.last_user = self.last_act
        # V0.5.91 不再在整個程式裝事件攔截（每一個畫面事件都要跑一段 Python、還要等背景工作放開 GIL → 很容易卡住沒回應）
        # 有沒有人在用電腦改問 Windows（GetLastInputInfo）；滑鼠側鍵換部（🧪）有開才裝
        if lab_cfg().get('swipe_nav'): QApplication.instance().installEventFilter(self)
        self.idle_t = QTimer(self); self.idle_t.timeout.connect(self._idle_check); self.idle_t.start(3000)
        self.outer.setCurrentIndex(0 if ENG.cfg.get('cover_on_start') is not False else 1); self._cover_ready = True
        if adopt: self._adopt(adopt)

    # ---------- 熱更新：狀態交出去／接過來
    def export_state(self):
        b = self.browse
        return {'page': self.nav.currentRow(), 'cover': self.outer.currentIndex() == 0, 'folder': b.folder, 'cur_id': (b.cur or {}).get('id'), 'geo': bytes(self.saveGeometry()), 'max': self.isMaximized(),
                'visible': self.isVisible(), 'perf': self.b_perf.isChecked(), 'seen': list(self._upd_seen)}

    def _adopt(self, st):
        try:
            self._upd_seen = set(st.get('seen') or []); self.browse.folder = st.get('folder') or ''; ENG.th_focus = self.browse.folder; self.browse._want_id = st.get('cur_id')
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
            QTimer.singleShot(400, lambda: timed_box(self, '已熱更新', f'V{st.get("hot_from")} → V{APP_VERSION}\n\n' + '\n'.join('• ' + str(x) for x in notes[:12]) +
                                                       ('\n…' if len(notes) > 12 else '') + '\n\n程式沒有關，背景工作照常進行。'))

    def handoff(self):
        """舊視窗要被新版取代：停計時器、收托盤、關浮窗；不碰引擎."""
        self._handoff = True; self.quitting = True
        try: self.hzembed.shutdown()                                             # 嵌進來的 HotZone 畫面：新視窗會自己再開一個
        except Exception: pass
        for L_ in (LOADER, getattr(getattr(self, 'browse', None), 'cload', None)):
            try: L_.stop = True; L_.ev.set()
            except Exception: pass
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
        self.hide()

    def _watch_update(self):
        d = ROOT / 'UPDATE'; dl = lab_cfg().get('watch_downloads'); seen = set(self._upd_seen); new_seen = []
        cache = self.__dict__.setdefault('_pkg_cache', {})                     # (路徑, 修改時間) → 版本：同一個包不要每 5 秒重新編譯一次
        def look():
            Z = []; places = [(d, '*.zip')]
            if dl: places += [(Path.home() / 'Downloads', 'VS_V*.zip'), (Path.home() / 'Downloads', 'SC_V*.zip')]   # 🧪 也看「下載」資料夾；V0.5.71 改名 SortCut 之後是 SC_V…
            for dd, pat in places:
                try: Z += list(dd.glob(pat))
                except Exception: pass
            Z = sorted(Z, key=lambda p: vkey(p.stem))
            for z in reversed(Z):
                if str(z) in seen: continue
                try: ck = (str(z), z.stat().st_mtime, z.stat().st_size)
                except Exception: continue
                if ck not in cache:
                    try: pk = load_pkg(z); cache[ck] = (pk['version'], pk['hot_ok'])
                    except Exception as ex: return ('bad', str(z), str(ex), new_seen)
                ver_, hot_ = cache[ck]
                if vkey(ver_) > vkey(APP_VERSION): return ('ok', str(z), ver_, hot_, new_seen)      # 只提示比現在新的（退回舊版請用「選更新包」）
                new_seen.append(str(z))
            return ('none', '', '', False, new_seen)
        bg(look, self._upd_found)

    def _upd_found(self, r):
        if not r: return
        if len(r) > 4: self._upd_seen.update(r[-1])                             # 在畫面執行緒加（背景執行緒不碰這個集合）
        if r[0] == 'none' or self._handoff or r[1] in self._upd_seen or self.ubar.isVisible(): return
        self._ubar_path = r[1]
        if r[0] == 'bad':
            self._upd_seen.add(r[1]); self.msg(f'UPDATE 資料夾裡的 {Path(r[1]).name} 不能用：{r[2]}', 15000); return
        self.ubar_l.setText(f'🆕 發現更新包 <b>{Path(r[1]).name}</b>：V{APP_VERSION} → V{r[2]}' + ('（可以熱更新，程式不用關）' if r[3] else '（要重開程式套用）'))
        self.ubar_go.setText('⚡ 立即熱更新' if r[3] else '🔁 重開程式套用'); self.ubar.show(); upd_log(f'發現更新包：{r[1]}（V{r[2]}）')

    # ---------------------------------------------------------------- V0.6.01 ☁ 雲端更新（GitHub Releases）
    def _cloud_check(self, manual=False):
        if self._handoff or self._cloud_busy: return
        if not manual and ENG.cfg.get('cloud_upd') is False: return
        import vs_cloudupd as CU
        def done(r):
            self._cloud = r; ENG.cloud_upd = r
            try: self.upd.cloud_show(r)
            except Exception: pass
            if not r.get('ok'):
                if manual: QMessageBox.information(self, '☁ 檢查更新', r.get('message', '連不到')); upd_log('雲端檢查：' + r.get('message', ''))
                return
            I = r['info']; v = I['version']
            if not r['newer']:
                if manual: QMessageBox.information(self, '☁ 檢查更新', f'已經是最新版（V{APP_VERSION}）')
                return
            if not manual and ENG.cfg.get('cloud_auto') is True and not I.get('shell_only'):    # V0.6.29 有新版自動熱更新（使用者 5 分鐘沒碰電腦才換，不打斷你）
                try:
                    import app_handshake as HS_; idle_ = HS_.idle_seconds()
                except Exception: idle_ = None
                if idle_ is None or idle_ >= 300:
                    upd_log(f'雲端有新版 V{v}：自動熱更新（cloud_auto）'); ENG.log.w(f'☁ 自動熱更新 V{v}'); self._cloud_go(); return
                upd_log(f'雲端有新版 V{v}：你正在用電腦，等沒在用再自動更新'); QTimer.singleShot(5 * 60 * 1000, lambda: self._cloud_check(False))
            if not manual and ENG.cfg.get('cloud_skip') == (f'L{I.get("launcher")}' if I.get('shell_only') else v): return
            if self.ubar.isVisible() and self._ubar_path != 'cloud': return
            notes = list(I.get('notes') or [])[:3]
            self._ubar_path = 'cloud'; self.ubar_go.setText('⬇ 更新'); self.ubar_no.setText('略過這版')
            self.ubar_l.setText((f'☁ 有新的 EXE（外殼）：第 {os.environ.get("SC_LAUNCHER") or 1} 版 → <b>第 {I.get("launcher")} 版</b>（程式已經是 V{APP_VERSION}；會自動關掉、換好、重新打開）' if I.get('shell_only') else
                                 f'☁ 雲端有新版：V{APP_VERSION} → <b>V{v}</b>' + ('（這次要換 EXE，會自動重開一次）' if I.get('need_shell') else '（下載後熱更新，程式不用關）'))
                                + (('　<span style="color:#9fb4c8">' + '；'.join(_hesc(x) for x in notes) + '</span>') if notes else ''))
            self.ubar.show(); upd_log(f'雲端有新版 V{v}（{r.get("url")}）')
        bg(lambda: CU.check(APP_VERSION), done)

    def _cloud_go(self):
        r = self._cloud or {}; I = r.get('info') or {}
        if not I.get('version') or self._cloud_busy: return
        import vs_cloudupd as CU
        v = I['version']; self._cloud_busy = True; self.msg(f'☁ 下載 V{v} 中…', 8000); upd_log(f'雲端更新：開始下載 V{v}')
        st = {'g': 0, 't': 0}

        def job():
            z = CU.download(I['zip'], ROOT / 'UPDATE' / Path(I['zip']).name.split('?')[0], I.get('zip_sha256', ''), cb=lambda g, t: st.update(g=g, t=t))
            return str(z), ''                                                   # V0.6.16 使用者不要換外殼：永遠只下載程式包、熱更新

        def prog():
            if self._cloud_busy and st['t']: self.msg(f"☁ 下載 V{v}：{st['g'] * 100 // max(1, st['t'])}%（{fmt_b(st['g'])}／{fmt_b(st['t'])}）", 3000); QTimer.singleShot(1000, prog)
        QTimer.singleShot(1000, prog)

        def fail(ex):
            self._cloud_busy = False; upd_log(f'雲端更新下載失敗：{ex}'); self.msg(f'☁ 下載失敗：{ex}（程式維持原版本，可以再按一次）', 15000)   # V0.6.16 不跳視窗（手機按的也看得到狀態）

        def ok(res):
            self._cloud_busy = False; zp, shp = res; self._upd_seen.add(str(zp)); upd_log(f'雲端更新：下載好了 {zp}' + (f'、外殼 {shp}' if shp else ''))
            if shp:                                                             # 要換 EXE：程式包先放 UPDATE（啟動器開機會套用），BAT 等程式關掉換外殼再打開
                bat = CU.shell_bat(ROOT, shp, os.getpid())
                if QMessageBox.question(self, '☁ 更新', f'V{v} 下載好了。這次要換 EXE（外殼），SortCut 會關掉、換好後自己重新打開（大約 10～30 秒）。\n\n現在更新？') != QMessageBox.Yes:
                    self.msg('☁ 已下載，下次按「更新」或重開程式時套用', 8000); return
                busy = len(ENG.cv_active) + len(ENG.th_active) + (1 if ENG.cut_cur else 0)
                if busy and QMessageBox.question(self, '☁ 更新', f'還有 {busy} 個工作在做（重開後會接著做）。確定現在更新？') != QMessageBox.Yes: return
                CU.run_bat(bat); upd_log('雲端更新：交給外殼更新程式，SortCut 關閉'); self.quitting = True; mark_clean_exit(); self.close(); return
            if not zp: return
            if not self.upd.load(zp): self.msg('☁ 更新包不能用（LOG\\update_log.txt 有原因）', 15000); return
            if self.upd.pkg.get('hot_ok'): self.upd.go(confirm=False)          # V0.6.16 不用再到電腦按確認：直接熱更新（手機按就好）
            else: upd_log('雲端更新：這個版本不能熱更新，先放在 UPDATE，下次開程式時套用'); self.msg('☁ 這版不能熱更新：下次開程式時自動套用', 15000)
        bg(job, ok, fail)

    def _ubar_later(self):
        if self._ubar_path == 'cloud':
            I_ = (self._cloud or {}).get('info') or {}
            try: ENG.cfg.set('cloud_skip', f'L{I_.get("launcher")}' if I_.get('shell_only') else I_.get('version'))   # 這版不再自動提示（手動「檢查更新」還是會）
            except Exception: pass
            self.ubar_go.setText('⚡ 立即熱更新'); self.ubar_no.setText('稍後')
        else: self._upd_seen.add(self._ubar_path)
        self.ubar.hide()

    def _ubar_apply(self):
        if self._ubar_path == 'cloud':
            self.ubar.hide(); self.ubar_go.setText('⚡ 立即熱更新'); self.ubar_no.setText('稍後'); return self._cloud_go()
        self.ubar.hide(); self._upd_seen.add(self._ubar_path)
        if not self.upd.load(self._ubar_path): self.nav.setCurrentRow(5); return
        if self.upd.pkg.get('hot_ok'): self.upd.go(confirm=False)              # V0.6.16 已經按了「更新」就不再問一次
        else: self.upd.restart_way()

    def _mk_icon(self):
        pm = QPixmap(64, 64); pm.fill(Qt.transparent); p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor('#4dc9ff')); p.setPen(Qt.NoPen); p.drawRoundedRect(4, 10, 56, 44, 10, 10); p.setBrush(QColor('#11151b'))
        path = QPainterPath(); path.moveTo(26, 22); path.lineTo(44, 32); path.lineTo(26, 42); path.closeSubpath(); p.drawPath(path); p.end(); return QIcon(pm)

    def report_dlg(self):
        """V0.2.35 📈 分級報表."""
        def show(R):
            d = QDialog(self); d.setWindowTitle('📈 分級報表'); d.resize(820, 520); v = QVBoxLayout(d); T, Wk = R['today'], R['week']
            row = lambda nm, x: (f"<td><b>{nm}</b></td><td>分級 <b>{x['graded']:,}</b>（<span style='color:{GC['S']}'>S {x['S']}</span>・<span style='color:{GC['A']}'>A {x['A']}</span>・"
                                 f"<span style='color:{GC['E']}'>E {x['E']}</span>・<span style='color:{GC['F']}'>F {x['F']}</span>）</td><td>剪 <b>{x['cuts']:,}</b> 段</td>"
                                 f"<td>轉檔 {x['cv_n']:,} 部・省 <b>{fmt_b(x['cv_save'])}</b></td><td>清掉待刪 {x['purge_n']:,} 個・<b>{fmt_b(x['purge_b'])}</b></td>")
            h = QLabel(f"<table cellpadding='6'><tr>{row('今天', T)}</tr><tr>{row('這 7 天', Wk)}</tr></table>還有 <b>{R['left']:,}</b> 部預覽圖好了、還沒分級")
            h.setTextFormat(Qt.RichText); v.addWidget(h); v.addWidget(ReportChart(R['days']), 1)
            try:                                                                # V0.2.50 速度、還要幾天、幾點最常審
                eta_ = R.get('eta_days'); pc_ = QLabel(f"⏱ 最近 7 天平均每天分級 <b>{R.get('pace', 0):g}</b> 部（有審的 {R.get('active_days', 0)} 天）　還沒分級 <b>{R.get('ungraded', 0):,}</b> 部" +
                                                     (f"　照這速度大約 <b>{eta_:g} 天</b>分完" if eta_ is not None else '　（最近 7 天沒分級，算不出還要幾天）') +
                                                     (f"　🕘 你最常在 <b>{R['best_h']} 點</b>審" if R.get('best_h', -1) >= 0 else '') +
                                                     (f"　⏱ 每部大概 <b>{R['per_file']:g} 秒</b>" if R.get('per_file') else '') +
                                                     ((lambda St: f"　🤖 分級建議猜中 <b>{round(St['ok'] * 100 / St['n'])}%</b>（{St['n']} 次）" if St.get('n') else '')(ENG.cfg.get('guess_stat') or {})) +
                                                     (f"　⚡ 自動規則這 7 天分了 <b>{R['auto_7d']:,}</b> 部" if R.get('auto_7d') else '') +
                                                     (f"　📤 這 7 天上傳 <b>{R.get('up_7d', 0):,}</b> 部・S／A 還沒傳 <b>{R.get('up_left', 0):,}</b> 部" if lab_cfg().get('copy_to') else ''))
                pc_.setTextFormat(Qt.RichText); v.addWidget(pc_); v.addWidget(HourChart(R.get('hours') or [0] * 24))
                v.addWidget(HeatMap(ENG.grade_heat(84)))                             # V0.4.09 🗓
                bdt_ = QPushButton('🧾 複製今天的日報（貼到 LINE／群組）'); v.addWidget(bdt_); bdt_.clicked.connect(lambda: (QApplication.clipboard().setText(ENG.day_text()), self.msg('🧾 日報複製好了，直接貼上')))   # V0.4.34
            except Exception: ENG.log.err('報表速度')
            n = QLabel('長條＝每天分級幾部（S 黃、A 綠、E 藍、F 紅）；日期下面綠色 ↑＝那天上傳幾部；下面小長條＝最近 14 天每個鐘頭分級幾部。分級的時間以「最後一次改分級」算。'); n.setObjectName('muted'); v.addWidget(n); d.exec(); d.deleteLater()
        bg(ENG.review_report, show)

    def empty_dlg(self):
        """V0.2.45 🧹 空資料夾."""
        if not lab_cfg().get('empty_dirs'): self.msg('🧹 空資料夾在 🧪 實驗工作區 →「🆕 新功能」打開'); return
        try:
            d = QDialog(self); d.setWindowTitle('🧹 空資料夾'); d.resize(760, 560); v = QVBoxLayout(d)
            info = QLabel('找影片庫裡「一個檔都沒有」的資料夾（VideoSIFT 分類資料夾、紀錄資料夾不會列出來）。刪除只會刪真的空的，有任何檔案就保留。'); info.setWordWrap(True); info.setObjectName('muted'); v.addWidget(info)
            st = QLabel(''); v.addWidget(st); lst = QListWidget(); v.addWidget(lst, 1)
            row = QHBoxLayout(); b_go = QPushButton('🔎 重新找'); b_all = QPushButton('全選'); b_del = QPushButton('🗑 刪掉勾選的'); [row.addWidget(x) for x in (b_go, b_all)]; row.addStretch(1); row.addWidget(b_del); v.addLayout(row)
            shown = {'t': -1}
            def tick():
                V = ENG.empty_view()
                if V['run']: st.setText(f'找中…已看過 {V["n"]:,} 個資料夾'); return
                if V['t'] == shown['t']: return
                shown['t'] = V['t']; lst.clear()
                for p_ in V['rows']:
                    it = QListWidgetItem(p_); it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Unchecked); lst.addItem(it)
                st.setText(f'找到 {len(V["rows"]):,} 個空資料夾（看過 {V["n"]:,} 個）' if V['done'] else '按「🔎 重新找」開始')
            def go(): ENG.empty_scan(); shown['t'] = -1; tick()
            def all_(): [lst.item(i).setCheckState(Qt.Checked) for i in range(lst.count())]
            def rm():
                L = [lst.item(i).text() for i in range(lst.count()) if lst.item(i).checkState() == Qt.Checked]
                if not L: return
                if QMessageBox.question(d, '🧹 空資料夾', f'刪掉勾選的 {len(L):,} 個空資料夾？（有檔案的會自動保留）') != QMessageBox.Yes: return
                b_del.setEnabled(False); st.setText('🧹 刪除中…')
                def done(r_):
                    ok, fail = r_; b_del.setEnabled(True); shown['t'] = -1; ENG._ed['t'] = time.time(); tick(); self.msg(f'🧹 刪掉 {ok} 個空資料夾' + (f'，{fail} 個保留' if fail else ''))
                bg(lambda: ENG.empty_remove(L), done)
            b_go.clicked.connect(go); b_all.clicked.connect(all_); b_del.clicked.connect(rm)
            tm = QTimer(d); tm.timeout.connect(tick); tm.start(800)
            if not ENG.empty_view()['done']: go()
            else: tick()
            d.exec(); tm.stop(); d.deleteLater()
        except Exception: ENG.log.err('空資料夾')

    def set_privacy(self, on):
        """V0.2.55 🙈 隱私模糊：清單、預覽圖格子全部模糊（不重做圖，直接加模糊效果，一瞬間切換）."""
        on = bool(on) and bool(lab_cfg().get('privacy'))
        try:
            from PySide6.QtWidgets import QGraphicsBlurEffect
            B = self.browse
            for w_ in (B.lst, B.grid, B.nxt, B.nxt2):
                if w_ is None: continue
                if on: e_ = QGraphicsBlurEffect(w_); e_.setBlurRadius(22); w_.setGraphicsEffect(e_)
                else: w_.setGraphicsEffect(None)
            self.b_pv.blockSignals(True); self.b_pv.setChecked(on); self.b_pv.setText('🙈 模糊中' if on else '🙈'); self.b_pv.blockSignals(False)
            ENG.cfg.set('privacy_on', on)
        except Exception: ENG.log.err('隱私模糊')

    def rule_dlg(self):
        """V0.2.60 ⚡ 規則分級：還沒分級的，符合條件的一次標好（可以預覽、可以復原）."""
        if not lab_cfg().get('rules'): self.msg('⚡ 規則分級在 🧪 實驗工作區 →「🆕 新功能」打開'); return
        try:
            d = QDialog(self); d.setWindowTitle('⚡ 規則分級'); d.resize(640, 560); v = QVBoxLayout(d)
            n_ = QLabel('只動「還沒分級」的影片；條件都要符合（0／空白＝不管）。規則標的不算進 🎯 今天的分級數，可以一鍵復原。'); n_.setWordWrap(True); n_.setObjectName('muted'); v.addWidget(n_)
            f = QFormLayout(); v.addLayout(f)
            dlt = QSpinBox(); dlt.setRange(0, 36000); dlt.setSuffix(' 秒'); dlt.setSpecialValueText('不管'); f.addRow('時長短於', dlt)
            dgt = QSpinBox(); dgt.setRange(0, 1440); dgt.setSuffix(' 分鐘'); dgt.setSpecialValueText('不管'); f.addRow('時長長於', dgt)
            hlt = QComboBox(); [hlt.addItem(t_, h_) for t_, h_ in (('不管', 0), ('低於 360p', 360), ('低於 480p', 480), ('低於 720p', 720), ('低於 1080p', 1080))]; f.addRow('畫質', hlt)
            slt = QSpinBox(); slt.setRange(0, 100000); slt.setSuffix(' MB'); slt.setSpecialValueText('不管'); f.addRow('檔案小於', slt)
            stl = QSpinBox(); stl.setRange(0, 100); stl.setSuffix(' %'); stl.setSpecialValueText('不管'); f.addRow('😴 靜止超過', stl)   # V0.3.12（要開 😴 背景算靜止比例）
            nm = QLineEdit(); nm.setPlaceholderText('檔名包含（例如 test）'); f.addRow('檔名', nm)
            cur_ = self.browse.folder; fo = QCheckBox(f'只在目前的資料夾（{cur_ or "全部"}）'); fo.setEnabled(bool(cur_)); f.addRow('', fo)
            gr = QComboBox(); [gr.addItem(t_, g_) for t_, g_ in (('F 刪除（之後在「待刪」確認）', 'F'), ('E 觀察', 'E'), ('A 保存', 'A'), ('S 無條件保存', 'S'))]; f.addRow('標成', gr)
            pv = QLabel('…'); pv.setWordWrap(True); pv.setTextFormat(Qt.RichText); v.addWidget(pv, 1)
            row = QHBoxLayout(); bu = QPushButton('↩ 復原上一次規則'); bauto = QPushButton('💾 存成自動規則'); bauto.setToolTip('之後每分鐘自動對「還沒分級」的套用（新進來的影片也會）'); ba = QPushButton('⚡ 套用'); row.addWidget(bu); row.addStretch(1); row.addWidget(bauto); row.addWidget(ba); v.addLayout(row)
            gA = QGroupBox('⚡ 自動規則（每分鐘自動套用到還沒分級的）'); gAl = QVBoxLayout(gA); v.addWidget(gA); lstA = QListWidget(); lstA.setMaximumHeight(110); gAl.addWidget(lstA)
            rA_ = QHBoxLayout(); bdel = QPushButton('🗑 刪掉選的自動規則'); bund = QPushButton('↩ 復原最近 24 小時自動規則分的'); rA_.addWidget(bdel); rA_.addStretch(1); rA_.addWidget(bund); gAl.addLayout(rA_)
            bund.clicked.connect(lambda: bg(ENG.auto_rule_undo, lambda r_: (self.msg(r_[1]), prev(), self.browse.load_list())) if QMessageBox.question(d, '⚡', '把最近 24 小時自動規則分的改回未分級？（之後你自己改過的不動）') == QMessageBox.Yes else None)   # V0.3.27
            def paintA():
                lstA.clear()
                for x in ENG.auto_rules():
                    c_ = [f'短於 {x["dur_lt"]:g} 秒' if x.get('dur_lt') else '', f'長於 {x["dur_gt"] / 60:g} 分' if x.get('dur_gt') else '', f'低於 {x["h_lt"]}p' if x.get('h_lt') else '', f'小於 {x["size_lt"]:g} MB' if x.get('size_lt') else '', f'靜止超過 {x["still_gt"]:g}%' if x.get('still_gt') else '', f'檔名有「{x["name"]}」' if x.get('name') else '', f'只在 {x["folder"]}' if x.get('folder') else '']
                    lstA.addItem('、'.join(y for y in c_ if y) + f' → {x["grade"]}')
            paintA()
            bauto.clicked.connect(lambda: (self.msg(ENG.auto_rule_add(rule())[1]), paintA()))
            bdel.clicked.connect(lambda: (ENG.auto_rule_del(lstA.currentRow()), paintA()) if lstA.currentRow() >= 0 else None)
            def rule(): return {'dur_lt': dlt.value(), 'dur_gt': dgt.value() * 60, 'h_lt': hlt.currentData(), 'size_lt': slt.value(), 'still_gt': stl.value(), 'name': nm.text().strip(), 'folder': cur_ if fo.isChecked() else '', 'grade': gr.currentData()}
            seq = {'n': 0}
            def prev(*_a):
                seq['n'] += 1; k_ = seq['n']; R_ = rule()
                def got(P):
                    if k_ != seq['n']: return
                    if P['message']: pv.setText(P['message']); ba.setEnabled(False); return
                    ba.setEnabled(P['n'] > 0)
                    pv.setText(f"符合 <b>{P['n']:,}</b> 部（{fmt_b(P['bytes'])}）" + ('<br>' + '<br>'.join(f"・{html_esc(x['name'])}　{fmt_t(x['dur'] or 0)}　{x['h'] or '?'}p　{fmt_b(x['size'] or 0)}" for x in P['sample']) + ('<br>…' if P['n'] > len(P['sample']) else '') if P['sample'] else ''))
                bg(lambda: ENG.rule_preview(R_), got)
            for w_ in (dlt, dgt, slt, stl): w_.valueChanged.connect(prev)
            for w_ in (hlt, gr): w_.currentIndexChanged.connect(prev)
            nm.textChanged.connect(prev); fo.toggled.connect(prev)
            def apply_():
                R_ = rule(); P = ENG.rule_preview(R_)
                if not P['n'] or QMessageBox.question(d, '⚡ 規則分級', f"把 {P['n']:,} 部還沒分級的標成 {R_['grade']}？（可以復原）") != QMessageBox.Yes: return
                ba.setEnabled(False); pv.setText('⚡ 套用中…'); bg(lambda: ENG.rule_apply(R_), lambda r_: (self.msg(r_[1]), prev(), self.browse.load_list()))   # V0.2.64 背景做
            def undo_():
                bu.setEnabled(False); bg(ENG.rule_undo, lambda r_: (self.msg(r_[1]), bu.setEnabled(True), prev(), self.browse.load_list()))
            ba.clicked.connect(apply_); bu.clicked.connect(undo_); prev(); d.exec(); d.deleteLater()
        except Exception: ENG.log.err('規則分級')

    def pcs_dlg(self):
        """V0.2.51 🖥 硬碟在哪台電腦."""
        if not lab_cfg().get('pc_overview'): self.msg('🖥 硬碟在哪台 在 🧪 實驗工作區 →「🆕 新功能」打開'); return
        def show(R):
            try:
                d = QDialog(self); d.setWindowTitle('🖥 硬碟在哪台電腦'); d.resize(820, 420); v = QVBoxLayout(d)
                h = QLabel(f"這台：<b style='color:{R['color']}'>● {html_esc(R['me'])}</b>　（紀錄寫在每顆硬碟自己身上，接到哪台就在哪台用）"); h.setTextFormat(Qt.RichText); v.addWidget(h)
                t = QTableWidget(len(R['rows']), 7); v.addWidget(t, 1); t.setHorizontalHeaderLabels(['硬碟', '名稱', '紀錄最後是', '什麼時候', '影片', '分級', '版本'])
                t.verticalHeader().setVisible(False); t.setEditTriggers(QAbstractItemView.NoEditTriggers); t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
                for i, o in enumerate(R['rows']):
                    who = ('這台' if o['mine'] else f"另一台：{o['pc_name']}") if o['has'] else ('（影片庫裡，還沒寫過）' if o['in_lib'] else '（沒有紀錄）')
                    when = time.strftime('%m/%d %H:%M', time.localtime(o['t'])) if o['t'] else ''
                    for j, x in enumerate((f"{o['d']}:", o['label'], who, when, f"{o['n']:,}" if o['has'] else '', f"{o['graded']:,}" if o['has'] else '', o['app'])):
                        it = QTableWidgetItem(str(x))
                        if j == 2 and o['has'] and not o['mine']: it.setForeground(QColor('#ffb74d'))
                        t.setItem(i, j, it)
                if not R['rows']: v.addWidget(QLabel('讀不到硬碟清單（只有 Windows 才看得到）'))
                b = QPushButton('💾 現在把紀錄寫到各硬碟'); b.clicked.connect(lambda: bg(lambda: ENG.pack_export_due(force=True, why='（硬碟在哪台）'), lambda r_: (self.msg('💾 已寫到：' + ('、'.join(r_) or '都是最新的')), d.accept())))
                v.addWidget(b); d.exec(); d.deleteLater()
            except Exception: ENG.log.err('硬碟在哪台')
        bg(ENG.pack_overview, show)

    def _still_tick(self):
        try:
            if not (lab_cfg().get('still_scan') or lab_cfg().get('smart_card')) or getattr(self, '_still_busy', False): return   # V0.3.24 只開 🖼 也會跑
            if ENG.bg_hold('probe') or float(ENG.perf.cpu or 0) >= float(ENG.cfg.get('cpu_max') or 90): return   # 讀影片資訊暫停／電腦很忙就先不算
            self._still_busy = True; bg(ENG.still_tick, lambda _r: setattr(self, '_still_busy', False), lambda _e: setattr(self, '_still_busy', False))
        except Exception: self._still_busy = False

    def _auto_scan(self):
        try:
            if time.time() - getattr(self, '_ft_t', 0) > 3600: self._ft_t = time.time(); bg(ENG.free_track, lambda _r: None)   # V0.2.91 📉 一小時記一次剩多少
            if lab_cfg().get('copy_to') and int(lab_cfg().get('up_auto_clean') or 0) > 0: bg(ENG.up_auto_clean, lambda r_: self.msg(r_[1]) if r_ and r_[0] else None)   # V0.4.50 🧺
            if lab_cfg().get('copy_to') and ENG.copy_kick(): self.msg('📤 接著複製到上傳資料夾（硬碟接回來／時段到了）')   # V0.3.03
            if lab_cfg().get('rules') and ENG.auto_rules(): bg(ENG.auto_rules_tick, lambda n_: self.msg(f'⚡ 自動規則分了 {n_} 部') if n_ else None)   # V0.3.21
        except Exception: pass
        try:
            st = ENG.auto_scan_tick(); t_ = st.get('last_t', 0)
            if t_ and t_ != getattr(self, '_as_seen', 0):
                self._as_seen = t_
                if st.get('last_new'): self.msg(f"👀 自動找新影片：多了 {st['last_new']} 部", 8000); self.browse.load_tree()
        except Exception: pass

    def copy_dlg(self):
        """V0.2.76 📤 複製佇列：看排了哪些、暫停／繼續、清空、打開上傳資料夾."""
        try:
            d = QDialog(self); d.setWindowTitle('📤 複製到上傳資料夾'); d.resize(560, 480); v = QVBoxLayout(d); st = QLabel(''); st.setWordWrap(True); v.addWidget(st); lst = QListWidget(); v.addWidget(lst, 1)
            row = QHBoxLayout(); bp = QPushButton(''); bc = QPushButton('🗑 清空排隊'); bo = QPushButton('📂 打開上傳資料夾'); [row.addWidget(x) for x in (bp, bc)]; row.addStretch(1); row.addWidget(bo); v.addLayout(row)
            def paint():
                V = ENG.copy_view(); bp.setText('▶ 繼續' if V['paused'] else '⏸ 暫停')
                st.setText(f"{'⏸ 暫停中　' if V['paused'] else ''}正在複製：{V['cur'] or '—'} {V['pct']}%・{fmt_b(V['speed'])}/s\n好了 {V['done']}・失敗 {V['fail']}・已經有 {V['skip']}・還有 {V['q']} 個\n→ {V['dir']}" + (f"\n最後一次錯誤：{V['last_err']}" if V['last_err'] else ''))
                L = ENG.copy_list(); lst.clear(); [lst.addItem(('✂ ' if x['cut'] else '🎬 ') + x['name']) for x in L]
            bp.clicked.connect(lambda: (self.msg(ENG.copy_ctl('resume' if ENG.copy_view()['paused'] else 'pause')), paint()))
            bc.clicked.connect(lambda: (self.msg(ENG.copy_ctl('clear')), paint()) if QMessageBox.question(d, '📤', '清掉還沒開始的排隊？') == QMessageBox.Yes else None)
            bo.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str((ENG.cfg.get('lab') or {}).get('copy_dir') or ''))))
            bb_ = QPushButton('📋 上傳看板'); row.insertWidget(2, bb_); bb_.clicked.connect(lambda: self.up_board_dlg(d))   # V0.3.69
            bk = QPushButton('🧹 清理舊檔…'); bk.setToolTip('上傳資料夾裡放很久（傳完了）的檔丟到資源回收筒'); row.insertWidget(2, bk); bk.clicked.connect(lambda: self.up_old_dlg(d))   # V0.3.66
            tm = QTimer(d); tm.timeout.connect(paint); tm.start(1500); paint(); d.exec(); tm.stop(); d.deleteLater()
        except Exception: ENG.log.err('複製佇列')

    def _vt(self, v):
        try: return tuple(int(x) for x in re.findall(r'\d+', str(v))[:3])
        except Exception: return (0,)

    def unplug_dlg(self):
        """V0.4.49 🔌 拔硬碟前看一下（每 2 秒更新）."""
        try:
            d = QDialog(self); d.setWindowTitle('🔌 拔硬碟前看一下'); d.resize(520, 380); v = QVBoxLayout(d); lw = QListWidget(); v.addWidget(lw, 1)
            row = QHBoxLayout(); bp = QPushButton('⏸ 背景工作全部暫停'); row.addWidget(bp); row.addStretch(1); v.addLayout(row)
            n = QLabel('✅ 可以拔＝現在沒有在讀寫那顆。拔之前最好還是用 Windows 的「安全地移除硬體」。'); n.setObjectName('muted'); n.setWordWrap(True); v.addWidget(n)
            def fill():
                lw.clear()
                for x in ENG.drive_busy(): lw.addItem(f"💽 {x['d']}:　" + ('⚠ 正在用：' + '、'.join(x['busy']) if x['busy'] else '✅ 可以拔'))
            bp.clicked.connect(lambda: (ENG.bg_all(True), self.msg('⏸ 背景工作全部暫停（手上那個做完就停）'), fill()))
            tm = QTimer(d); tm.timeout.connect(fill); tm.start(2000); fill(); d.exec(); tm.stop(); d.deleteLater()
        except Exception: ENG.log.err('拔硬碟前看一下')

    def devices_dlg(self):
        """V0.4.31 📱 登入過的手機：可以只登出其中一支."""
        try:
            srv = web_server(create=False)
            if srv is None: self.msg('📱 手機網頁沒開'); return
            d = QDialog(self); d.setWindowTitle('📱 登入過的手機'); d.resize(720, 420); v = QVBoxLayout(d); t = QTableWidget(0, 6); v.addWidget(t, 1)
            t.setHorizontalHeaderLabels(['裝置', '權限', '從哪裡', '第一次登入', '最後一次用', '']); t.verticalHeader().setVisible(False); t.setEditTriggers(QAbstractItemView.NoEditTriggers); t.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
            def fill():
                L = srv.tok_list(); t.setRowCount(len(L)); ft = lambda x: time.strftime('%m/%d %H:%M', time.localtime(float(x))) if x else '—'
                for i, x in enumerate(L):
                    for j, c in enumerate((x['dev'], '👀 唯讀' if x['ro'] else '一般', x['ip'], ft(x['t']), ft(x['last']))): t.setItem(i, j, QTableWidgetItem(str(c)))
                    b = QPushButton('登出這支'); b.clicked.connect(lambda _c=False, k=x['k']: (srv.tok_revoke(k), self.msg('📱 登出了一支手機'), fill())); t.setCellWidget(i, 5, b)
            fill(); n = QLabel('只登出其中一支：那支手機下次要重新輸入 PIN。'); n.setObjectName('muted'); v.addWidget(n); d.exec(); d.deleteLater()
        except Exception: ENG.log.err('登入過的手機')

    def ro_pin_dlg(self):
        """V0.4.30 👀 設定／清除手機唯讀 PIN."""
        try:
            has = bool(ENG.cfg.get('web_pin_ro_hash'))
            t, ok = QInputDialog.getText(self, '👀 手機唯讀 PIN', ('已經設定了。輸入新的就換掉；輸入 0 清除（唯讀的手機全部登出）：' if has else '設一組給別人用的唯讀 PIN（4～20 個字，不能跟一般 PIN 一樣）：'))
            if not ok or not t.strip(): return
            t = t.strip()
            if t == '0': ENG.cfg.set('web_pin_ro_hash', ''); ENG.cfg.set('web_tokens_ro', []); self.msg('👀 唯讀 PIN 清掉了，唯讀的手機都登出'); return
            if not vs_web.pin_ok_format(t): self.msg('4～20 個字、不能有空白'); return
            if ENG.cfg.get('web_pin_hash') and vs_web.same(vs_web.pin_hash(t, ENG.cfg.get('web_pin_salt') or ''), ENG.cfg.get('web_pin_hash')): self.msg('不能跟一般 PIN 一樣'); return
            salt = vs_web.rand_hex(8); ENG.cfg.set('web_pin_ro_salt', salt); ENG.cfg.set('web_pin_ro_hash', vs_web.pin_hash(t, salt)); ENG.log.w('手機網頁：唯讀 PIN 設定好了')
            self.msg(f'👀 唯讀 PIN 存好了：{t}（給別人用這組登入就只能看）', 12000)
        except Exception: ENG.log.err('唯讀 PIN')

    def merge_tour(self, force=False):
        """V0.5.25 FileCompare 合併進來之後第一次打開：一張圖說工作流程、舊資料怎麼接（只出現一次；使用說明裡也有）."""
        try:
            if (ENG.cfg.get('tour5') and not force) or self._handoff: return
            if not force and isinstance(QApplication.activeModalWidget(), QWidget):
                QTimer.singleShot(4000, self.merge_tour); return                   # 別的視窗（例如「這次更新多了什麼」）還開著：等它關了再出現
            ENG.cfg.set('tour5', APP_VERSION)
            d = QDialog(self); d.setWindowTitle('🧭 FileCompare 合併進來了'); d.resize(620, 520); v = QVBoxLayout(d)
            G = [(c, n) for n, c, _L in NavList.GROUPS[:6]]
            t = QLabel('<h3>FileCompare 整套搬進 SortCut 了（取代原本的「審核」，👤 人物拿掉）</h3>'
                       '<p>左邊選單照工作流程排，從上往下做：</p>' + ''.join(f'<p style="margin:2px 0"><span style="color:{c};font-weight:700">■</span> {n}</p>' for c, n in G) +
                       '<p style="margin-top:10px">• 兩邊不會同時大量讀同一顆硬碟（整理會讓 SortCut 先用）；同一部影片不會兩邊都轉檔。<br>'
                       '• 設定分三個：設定：SortCut／設定：整理／設定：HotZone（左邊「設定與說明」）。<br>'
                       '• 手機：下面「🗂 整理」；「工具」最上面有 ①～⑥。</p>'
                       '<p><b>舊電腦用過 FileCompare？</b> 把舊的 FileCompare 資料夾裡的 <b>Data</b> 整個複製過來，按下面「📥 匯入」，重開就接上（R 碟代號要一樣）。</p>')
            t.setWordWrap(True); t.setTextFormat(Qt.RichText); v.addWidget(t, 1)
            r = QHBoxLayout(); v.addLayout(r)
            b1 = QPushButton('📥 匯入舊 FileCompare 資料'); b1.clicked.connect(lambda: (d.accept(), self.fcp.import_old()))
            b2 = QPushButton('📖 看使用說明'); b2.clicked.connect(lambda: (d.accept(), self.enter(8)))
            b3 = QPushButton('好，開始用'); b3.setDefault(True); b3.clicked.connect(d.accept)
            for b_ in (b1, b2): r.addWidget(b_)
            r.addStretch(1); r.addWidget(b3); d.exec(); d.deleteLater()
        except Exception: ENG.log.err('合併導覽')

    def whats_new(self, force=False):
        """V0.3.97 🆕 從上次用的版本到這版，中間每一版改了什麼（跳版更新也一次看完）."""
        try:
            seen = str(ENG.cfg.get('ver_seen') or '')
            if not force:
                if not seen: ENG.cfg.set('ver_seen', APP_VERSION); return
                if seen == APP_VERSION or not lab_cfg().get('whats_new'): ENG.cfg.set('ver_seen', APP_VERSION); return
            C = json.loads((HERE / 'CHANGELOG.json').read_text(encoding='utf-8')); lo = self._vt(seen) if seen else (0,)
            R = [x for x in C if lo < self._vt(x.get('version')) <= self._vt(APP_VERSION)] if not force else C[:10]
            ENG.cfg.set('ver_seen', APP_VERSION)
            if not R: return
            d = QDialog(self); d.setWindowTitle('🆕 這次更新多了什麼'); d.resize(640, 560); v = QVBoxLayout(d)
            v.addWidget(QLabel(f'<b>從 V{seen or "?"} 更新到 V{APP_VERSION}</b>：中間 {len(R)} 版的改變' if not force else f'<b>最近 {len(R)} 版的改變</b>'))
            tx = QTextBrowser(); tx.setHtml(''.join(f"<h4>V{x.get('version')}　<small>{x.get('date', '')}</small></h4><ul>" + ''.join(f'<li>{i}</li>' for i in x.get('items') or []) + '</ul>' for x in R)); v.addWidget(tx, 1)
            b_ = QPushButton('好，知道了'); b_.clicked.connect(d.accept); v.addWidget(b_); d.exec(); d.deleteLater()
        except Exception: ENG.log.err('這次更新多了什麼')

    PILLS = (('b_rep', '📈 報表'), ('b_goal', '🎯 今天目標'), ('b_spr', '⏱ 衝刺'), ('b_upg', '📤 上傳目標'), ('b_pv', '🙈 隱私模糊'), ('b_copy', '📤 複製進度'), ('b_bgst', '後台狀態'), ('b_theme', '◐ 深色／淺色'))

    def pill_menu(self):
        """V0.4.10 狀態列按右鍵：勾掉的按鈕就不顯示（狀態列太擠時用）."""
        try:
            H = set(ENG.cfg.get('pill_hide') or []); m = QMenu(self); m.addSection('狀態列要顯示哪些（勾掉＝藏起來）')
            for k, n in self.PILLS:
                if not hasattr(self, k): continue
                a = m.addAction(n); a.setCheckable(True); a.setChecked(k not in H)
                a.toggled.connect(lambda on, k=k: (ENG.cfg.set('pill_hide', sorted((set(ENG.cfg.get('pill_hide') or []) - {k}) if on else (set(ENG.cfg.get('pill_hide') or []) | {k}))), self._pill_apply(), None if on else None))
            m.addSeparator(); m.addAction('全部顯示', lambda: (ENG.cfg.set('pill_hide', []), self.apply_new_labs()))
            m.exec(QCursor.pos())
        except Exception: ENG.log.err('狀態列選單')

    def _pill_apply(self):
        for k in (ENG.cfg.get('pill_hide') or []):
            try: getattr(self, k).hide()
            except Exception: pass

    def break_dlg(self):
        """V0.3.89 👀 休息提醒：連續幾分鐘提醒."""
        try:
            O = [('30 分鐘', 30), ('45 分鐘', 45), ('1 小時', 60), ('1.5 小時', 90), ('2 小時', 120)]; cur = int(lab_cfg().get('break_min') or 45)
            t, ok = QInputDialog.getItem(self, '👀 休息提醒', '連續分級多久提醒休息？', [x[0] for x in O], max(0, [x[1] for x in O].index(cur) if cur in [x[1] for x in O] else 1), False)
            if ok: m_ = dict(O)[t]; ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, break_min=m_)); ENG._brk_c = None; self.msg(f'👀 連續分級 {t} 會提醒休息')
        except Exception: ENG.log.err('休息提醒設定')

    def week_html(self, R):
        tr = R.get('trend', 0); arrow = ('⬆' if tr > 0 else '⬇' if tr < 0 else '➡')
        return (f"<h3>📆 這 7 天回顧</h3><p>分級 <b>{R['graded']:,}</b> 部（S {R['S']}・A {R['A']}）　{arrow} 比前 7 天 {'+' if tr > 0 else ''}{tr}%（前 7 天 {R['graded_prev']:,}）</p>"
                f"<p>有審的天數 <b>{R['active']}</b>／7" + (f"　最拚的一天 <b>{R['best_day'][5:]}</b>" if R.get('best_day') else '') + "</p>"
                + (f"<p>📤 上傳 <b>{R['up']:,}</b> 部（前 7 天 {R['up_prev']:,}）・✅ 發佈 <b>{R.get('pub', 0):,}</b> 部</p>" if lab_cfg().get('copy_to') else '')
                + f"<p>✂ 剪 <b>{R['cuts']:,}</b> 段　💾 省下／清掉 <b>{fmt_b(R['saved'])}</b></p>"
                + (f"<p>⏱ 衝刺 {R['sprint_n']} 次，最快每分鐘 <b>{R['sprint_best']:g}</b> 部</p>" if R.get('sprint_n') else '')
                + f"<p>還沒分級 <b>{int(R.get('left') or 0):,}</b> 部</p>")

    def week_dlg(self):
        """V0.3.80 📆 每週回顧."""
        def show(R):
            try:
                d = QDialog(self); d.setWindowTitle('📆 每週回顧'); d.resize(560, 520); v = QVBoxLayout(d); l_ = QLabel(self.week_html(R)); l_.setTextFormat(Qt.RichText); l_.setWordWrap(True); v.addWidget(l_, 1); v.addWidget(HeatMap(ENG.grade_heat(84)))
                b_ = QPushButton('好'); b_.clicked.connect(d.accept); v.addWidget(b_); ENG.cfg.set('week_seen', R['wk']); d.exec(); d.deleteLater()
            except Exception: ENG.log.err('每週回顧')
        bg(ENG.week_review, show)

    def _week_auto(self):
        """每週第一次打開：狀態列提醒一下（不跳視窗，按工具箱卡片看）."""
        try:
            if not lab_cfg().get('weekly') or ENG.cfg.get('week_seen') == time.strftime('%G-W%V'): return
            def got(R):
                ENG.cfg.set('week_seen', R['wk']); tr = R.get('trend', 0)
                self.msg(f"📆 這 7 天分了 {R['graded']:,} 部（{'+' if tr > 0 else ''}{tr}%）" + (f"、上傳 {R['up']:,} 部" if lab_cfg().get('copy_to') else '') + '　→ 🧰 工具箱「📆 每週回顧」看完整', 20000)
            bg(ENG.week_review, got)
        except Exception: pass

    def sprint_dlg(self):
        """V0.3.72 ⏱ 分級衝刺：開始／結束、看歷史."""
        try:
            d = QDialog(self); d.setWindowTitle('⏱ 分級衝刺'); d.resize(460, 420); v = QVBoxLayout(d); V = ENG.sprint_view()
            st = QLabel(); st.setWordWrap(True); v.addWidget(st)
            if V and V['on']: st.setText(f"衝刺中：還剩 {V['left'] // 60}:{V['left'] % 60:02d}，已經分了 {V['n']} 部（每分鐘 {V['rate']:g}）")
            else: st.setText('選一個時間開始：倒數時專心分級，時間到看自己分了幾部。')
            row = QHBoxLayout(); v.addLayout(row)
            for m_ in (10, 15, 25, 45):
                b_ = QPushButton(f'{m_} 分鐘'); row.addWidget(b_); b_.clicked.connect(lambda _c=False, m_=m_: (self.msg(ENG.sprint_start(m_)), d.accept(), self.enter(0), self._bgst()))
            if V and V['on']:
                bs = QPushButton('🏁 現在結束'); v.addWidget(bs); bs.clicked.connect(lambda: (lambda R: self.msg(f"🏁 分了 {R['n']} 部（每分鐘 {R['rate']:g}）" if R else '沒有在衝刺'))(ENG.sprint_stop()) or d.accept())
            H = (ENG.cfg.get('sprint_hist') or [])[::-1]; lw = QListWidget(); v.addWidget(QLabel(f'歷史（最好：每分鐘 {max((h["rate"] for h in H), default=0):g} 部）')); v.addWidget(lw, 1)
            for h in H: lw.addItem(f"{time.strftime('%m/%d %H:%M', time.localtime(h['t']))}　{h['min']} 分鐘　{h['n']} 部　每分 {h['rate']:g}")
            d.exec(); d.deleteLater(); self._bgst()
        except Exception: ENG.log.err('分級衝刺')

    def _pub_names(self, parent, after=None):
        """V0.4.27 📥 貼一串檔名（一行一個）→ 標成已發佈."""
        t, ok = QInputDialog.getMultiLineText(parent, '📥 貼檔名標已發佈', '一行一個檔名（從上傳資料夾複製、或發佈紀錄貼過來都可以；日期／分級前綴會自動去掉）：')
        if ok and t.strip(): self.msg(ENG.pub_by_names(t)[1], 10000); after and after()

    def _cap_today(self, D_):
        """V0.4.06 📋 今天傳好的文案全部複製（每部前面帶檔名）."""
        if not lab_cfg().get('caption'): self.msg('📋 要先打開「📋 上傳文案」'); return
        if not D_: self.msg('今天還沒有傳好的'); return
        QApplication.clipboard().setText('\n\n'.join(f"【{x['name']}】\n" + ENG.caption_for(x['id']) for x in D_)); self.msg(f'📋 複製了 {len(D_)} 部的文案（每部前面有檔名）')

    def up_board_dlg(self, parent=None):
        """V0.3.69 📋 上傳看板：還沒傳 → 排隊中 → 今天傳好的；左邊點兩下＝排進複製."""
        try:
            d = QDialog(parent or self); d.setWindowTitle('📋 上傳看板'); d.resize(980, 560); v = QVBoxLayout(d); top = QLabel(''); v.addWidget(top)
            h = QHBoxLayout(); v.addLayout(h, 1); C = []
            for t_ in ('📥 S／A 還沒傳（點兩下＝排進複製、右鍵＝打開看）', '⏳ 排隊中', '✅ 今天傳好的（點兩下＝打開、右鍵＝標已發佈）'):
                b_ = QVBoxLayout(); l_ = QLabel(t_); l_.setStyleSheet('font-weight:bold'); lw = QListWidget(); b_.addWidget(l_); b_.addWidget(lw, 1); h.addLayout(b_, 1); C.append((l_, lw))
            row = QHBoxLayout(); ba = QPushButton('📤 左邊全部排進複製'); row.addWidget(ba); bpn_ = QPushButton('📥 貼檔名標已發佈'); row.addWidget(bpn_); bpn_.clicked.connect(lambda: self._pub_names(d, load)); dd7_ = QCheckBox('✅ 欄看最近 7 天'); dd7_.setChecked(int(ENG.cfg.get('up_done_days') or 1) == 7); row.addWidget(dd7_); dd7_.toggled.connect(lambda on: (ENG.cfg.set('up_done_days', 7 if on else 1), load())); mx_ = QCheckBox('🔀 作者輪流排'); mx_.setToolTip('同一個主播不會連著好幾部（S 還是排在 A 前面）'); mx_.setChecked(ENG.cfg.get('up_order') == 'mix'); row.addWidget(mx_); mx_.toggled.connect(lambda on: (ENG.cfg.set('up_order', 'mix' if on else ''), load())); row.addStretch(1); bx = QPushButton('🧾 上傳紀錄匯出 CSV（30 天）'); row.addWidget(bx); bq_ = QPushButton('⚙ 複製佇列（暫停／清空／清理舊檔）'); row.addWidget(bq_); bcp_ = QPushButton('📋 今天傳好的文案全部複製'); row.insertWidget(1, bcp_); bcp_.clicked.connect(lambda: self._cap_today((st_['R'] or {}).get('done') or [])); bun_ = QPushButton('⏪ 復原上一個複製'); row.insertWidget(2, bun_); bun_.clicked.connect(lambda: (self.msg(ENG.up_undo(1)[1]), load()) if QMessageBox.question(d, '⏪', '把最近一個複製到上傳的那份丟到資源回收筒、取消已上傳？（原檔不動）') == QMessageBox.Yes else None); bq_.clicked.connect(self.copy_dlg); v.addLayout(row)   # V0.3.93／0.3.94
            def exp_():
                fn, _f = QFileDialog.getSaveFileName(d, '🧾 上傳紀錄', str(Path.home() / f"VideoSift_上傳紀錄_{time.strftime('%Y%m%d')}.csv"), 'CSV (*.csv)')
                if fn:
                    try: Path(fn).write_text(ENG.up_csv(30), encoding='utf-8'); self.msg(f'🧾 存好了：{fn}')
                    except Exception as e: self.msg(f'存不了：{e}')
            bx.clicked.connect(exp_)
            MB_ = [(bcp_, '📋 今天傳好的文案全部複製'), (bpn_, '📥 貼一串檔名標成已發佈'), (bx, '🧾 上傳紀錄匯出 CSV（30 天）'), (bun_, '⏪ 復原上一個複製'), (bq_, '⚙ 複製佇列（暫停／清空／🧹 清理舊檔）')]   # V0.4.29 少用的收進「更多」
            for b_, _t in MB_: b_.hide()
            bm_ = QPushButton('⋯ 更多'); row.addWidget(bm_)
            def more_():
                m_ = QMenu(d)
                for b_, t_ in MB_: m_.addAction(t_, b_.click)
                m_.exec(QCursor.pos())
            bm_.clicked.connect(more_)
            st_ = {'R': None}
            def paint(R):
                st_['R'] = R; G = R.get('goal')
                top.setText((f"⬜ 複製了還沒發佈 {R['unpub']:,} 部・" if R.get('unpub') else '') + f"還沒傳 {R.get('todo_n', 0):,} 部・排隊 {len(R['queue'])}" + (f"・正在複製 {R['cur']} {R['pct']}%" if R.get('cur') else '') + (f"・⏳ {R['wait']}" if R.get('wait') else '') + (f"・💽 上傳那顆剩 {fmt_b(R['free'])}" if R.get('free') is not None else '') + ((lambda E_: f"・⌛ 照{'每天目標' if E_['by'] == 'goal' else '最近 7 天的速度'} {E_['per']:g} 部／天，大約 {E_['days']:g} 天傳完" if E_ and E_.get('days') else '')(R.get('eta'))) + (f"・今天 {G['n']}／{G['goal']}" + (' 🎉' if G['done'] else '') if G else f"・今天傳了 {len(R['done'])} 部"))
                for (l_, lw), L, fn in ((C[0], R['todo'], lambda x: f"{x['grade']}　{x['name']}" + (f"　♻ 已經傳過同一支（{x['dup']}）" if x.get('dup') else '')), (C[1], R['queue'], lambda x: ('✂ ' if x.get('cut') else '🎬 ') + x['name']), (C[2], R['done'], lambda x: ('✅ ' if float(x.get('pub_t') or 0) > 0 else '⬜ ') + f"{time.strftime('%m/%d %H:%M' if R.get('done_days') == 7 else '%H:%M', time.localtime(x['up_t']))}　{x['grade'] or ''}　{x['name']}")):
                    lw.clear(); l_.setText(l_.text().split('　（')[0] + f'　（{len(L)}）')   # V0.4.53 欄位標題帶數量
                    for x in L: it = QListWidgetItem(fn(x)); it.setData(Qt.UserRole, x.get('id')); lw.addItem(it)
            def load(): bg(ENG.up_board, paint)
            def enq(ids):
                if ids: self.msg(ENG.copy_enqueue(ids)[1]); QTimer.singleShot(600, load)
            C[0][1].itemDoubleClicked.connect(lambda it: enq([it.data(Qt.UserRole)]))
            C[0][1].setContextMenuPolicy(Qt.CustomContextMenu); C[0][1].customContextMenuRequested.connect(lambda p_: (lambda it: (d.accept(), self.enter(0), self.browse.goto_file(it.data(Qt.UserRole))) if it is not None else None)(C[0][1].itemAt(p_)))   # V0.4.42 右鍵＝先打開看
            def pub_(it):                                                       # V0.4.21 右鍵＝標成已發佈／取消
                if it is None or not it.data(Qt.UserRole): return
                x_ = next((x for x in (st_['R'] or {}).get('done') or [] if x['id'] == it.data(Qt.UserRole)), {}); on_ = not float(x_.get('pub_t') or 0) > 0
                m_ = QMenu(d); m_.addAction('✅ 標成已發佈（貼到 TikTok 了）' if on_ else '↩ 取消已發佈', lambda: (self.msg(ENG.pub_mark([it.data(Qt.UserRole)], on_)[1]), load()))
                if lab_cfg().get('caption'): m_.addAction('📋 複製這部的文案', lambda: (QApplication.clipboard().setText(ENG.caption_for(it.data(Qt.UserRole))), self.msg('📋 文案複製好了，貼完記得標已發佈')))   # V0.4.45
                m_.exec(QCursor.pos())
            C[2][1].setContextMenuPolicy(Qt.CustomContextMenu); C[2][1].customContextMenuRequested.connect(lambda p_: pub_(C[2][1].itemAt(p_)))
            C[2][1].itemDoubleClicked.connect(lambda it: (d.accept(), self.enter(0), self.browse.goto_file(it.data(Qt.UserRole))) if it.data(Qt.UserRole) else None)   # V0.3.78 今天傳好的點兩下＝打開那部
            ba.clicked.connect(lambda: enq([x['id'] for x in (st_['R'] or {}).get('todo') or []]))
            tm = QTimer(d); tm.timeout.connect(load); tm.start(3000); load(); d.exec(); tm.stop(); d.deleteLater()
        except Exception: ENG.log.err('上傳看板')

    def up_old_dlg(self, parent=None):
        """V0.3.66 🧹 上傳資料夾裡放超過 N 天的檔：勾選丟到資源回收筒（只動上傳資料夾裡的「複本」，原檔不動）."""
        try:
            d = QDialog(parent or self); d.setWindowTitle('🧹 清理上傳資料夾的舊檔'); d.resize(620, 520); v = QVBoxLayout(d)
            top = QHBoxLayout(); sp = QSpinBox(); sp.setRange(0, 365); sp.setValue(int(ENG.cfg.get('up_old_days') or 14)); sp.setPrefix('放超過 '); sp.setSuffix(' 天')
            top.addWidget(sp); info = QLabel(''); info.setObjectName('muted'); top.addWidget(info, 1); v.addLayout(top)
            lst = QListWidget(); v.addWidget(lst, 1)
            row = QHBoxLayout(); ba = QPushButton('全選'); bn = QPushButton('全不選'); bd = QPushButton('🗑 丟到資源回收筒'); [row.addWidget(x) for x in (ba, bn)]; row.addStretch(1); row.addWidget(bd); v.addLayout(row)
            ac_ = QComboBox(); [ac_.addItem(t_, k_) for t_, k_ in (('不要自動清', 0), ('已發佈的放 3 天自動清', 3), ('已發佈的放 7 天自動清', 7), ('已發佈的放 14 天自動清', 14), ('已發佈的放 30 天自動清', 30))]   # V0.4.50
            ac_.setCurrentIndex(max(0, ac_.findData(int(lab_cfg().get('up_auto_clean') or 0)))); row.insertWidget(2, ac_); ac_.currentIndexChanged.connect(lambda _i: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, up_auto_clean=int(ac_.currentData()))))
            v.addWidget(QLabel('只會動上傳資料夾裡的檔（都是複製過去的複本），原本的影片不會動；丟到資源回收筒，救得回來。標「⬜ 還沒發佈」的預設不勾。'))
            def load():
                ENG.cfg.set('up_old_days', int(sp.value())); lst.clear(); info.setText('讀取中…')
                def got(R):
                    lst.clear()
                    for x in R.get('rows') or []:
                        pb_ = {True: '✅ 已發佈　', False: '⬜ 還沒發佈　'}.get(x.get('pub'), '')   # V0.4.22
                        it = QListWidgetItem(f"{pb_}{x['age']} 天　{fmt_b(x['size'])}　{x['rel']}"); it.setData(Qt.UserRole, x['rel']); it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Unchecked if x.get('pub') is False else Qt.Checked); lst.addItem(it)
                    info.setText(R.get('message') or f"{R.get('dir')}：{len(R.get('rows') or [])} 個、{fmt_b(R.get('bytes') or 0)}")
                bg(lambda: ENG.up_old(sp.value()), got)
            def chk(on):
                for i in range(lst.count()): lst.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked)
            def rm():
                L = [lst.item(i).data(Qt.UserRole) for i in range(lst.count()) if lst.item(i).checkState() == Qt.Checked]
                if not L or QMessageBox.question(d, '🧹', f'把 {len(L)} 個檔丟到資源回收筒？') != QMessageBox.Yes: return
                bg(lambda: ENG.up_old_rm(L, sp.value()), lambda r: (self.msg(r[1]), load()))
            ba.clicked.connect(lambda: chk(True)); bn.clicked.connect(lambda: chk(False)); bd.clicked.connect(rm); sp.editingFinished.connect(load)
            load(); d.exec(); d.deleteLater()
        except Exception: ENG.log.err('清理上傳資料夾')

    def progress_dlg(self):
        """V0.2.84 📂 各資料夾分級進度：點兩下＝到那個資料夾、只看可以審的."""
        if not lab_cfg().get('folder_prog'): self.msg('📂 各資料夾進度在 🧪 實驗工作區 →「🆕 新功能」打開'); return
        d = QDialog(self); d.setWindowTitle('📂 各資料夾分級進度'); d.resize(900, 600); v = QVBoxLayout(d)
        t = QTableWidget(0, 9); v.addWidget(t, 1); t.setHorizontalHeaderLabels(['資料夾', '部數', '大小', '可以審', '還沒分', '分級進度', '預覽圖', 'F 待刪', '📤 S／A 傳了'])
        t.verticalHeader().setVisible(False); t.setEditTriggers(QAbstractItemView.NoEditTriggers); t.setSelectionBehavior(QAbstractItemView.SelectRows); t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        n = QLabel('讀取中…'); n.setObjectName('muted'); v.addWidget(n)
        def got(R):
            t.setRowCount(len(R))
            for i, x in enumerate(R):
                for j, c in enumerate((x['folder'], f"{x['n']:,}", fmt_b(x['bytes']), f"{x['ready']:,}", f"{x['left']:,}", f"{x['pct']}%", f"{x['th']:,}／{x['n']:,}", fmt_b(x['f_bytes']) if x['f_bytes'] else '', f"{x.get('sa_up', 0)}／{x.get('sa', 0)}" if x.get('sa') else '')):
                    it = QTableWidgetItem(c); t.setItem(i, j, it)
                    if j == 5: it.setForeground(QColor('#45d483' if x['pct'] >= 100 else '#ffc94d' if x['pct'] >= 50 else '#ff8a65'))
            n.setText(f'{len(R):,} 個資料夾（「可以審」＝預覽圖好了還沒分級；點兩下到那個資料夾、只看可以審的）')
        def go(it):
            fd = t.item(it.row(), 0).text(); d.accept(); self.enter(0); self.browse._sel_folder(fd)
            i_ = self.browse.flt.findData('ready'); self.browse.flt.setCurrentIndex(i_) if (i_ is not None and i_ >= 0) else self.browse.load_list()
        t.itemDoubleClicked.connect(go); bg(ENG.folder_progress, got); d.exec(); d.deleteLater()

    TOUR_VER = '0.4.00'

    def _tour_maybe(self):
        try:
            if str(ENG.cfg.get('tour_seen') or '') == self.TOUR_VER or os.environ.get('VIDEOSIFT_SELFTEST'): return
            if self.outer.currentIndex() == 0: QTimer.singleShot(20000, self._tour_maybe); return   # 在封面就晚點再問
            self.tour_dlg()
        except Exception: ENG.log.err('新功能導覽')

    def tour_dlg(self):
        """V0.3.00 🆕 新功能導覽：0.2.30 之後加的功能分組列出來，勾想要的一次打開（都不勾也可以）."""
        d = QDialog(self); d.setWindowTitle('🆕 SortCut 0.4 新功能導覽'); prev_ = str(ENG.cfg.get('tour_seen') or ''); d.resize(760, 640); v = QVBoxLayout(d)
        t = QLabel(f'🎉 從 V0.2.30 到 V{APP_VERSION} 一共加了 {len(NEW_LABS)} 個新功能，全部預設關著。勾你想試的，按「打開勾選的」；之後隨時可以在 🧪 實驗工作區 或 🧰 新功能工具箱 開關。')
        t.setWordWrap(True); v.addWidget(t); sa = QScrollArea(); sa.setWidgetResizable(True); body = QWidget(); bl = QVBoxLayout(body); sa.setWidget(body); v.addWidget(sa, 1)
        NM = {k: (n, ds) for k, n, ds, _v in NEW_LABS}; L = lab_cfg(); cbs = {}; used = set()
        vt_ = lambda x: tuple(int(p_) for p_ in re.findall(r'\d+', str(x))[:3])
        NEWK = [k for k, _n, _d, ver_ in NEW_LABS if prev_ and vt_(ver_) > vt_(prev_)]               # V0.4.00 上次看導覽之後才加的，放最上面
        groups = ([(f'🆕 上次看導覽（V{prev_}）之後新加的', NEWK)] if NEWK else []) + [(n_, K_) for n_, K_ in LAB_PACKS] + [('🧩 其他', [k for k, *_r in NEW_LABS if not any(k in K_ for _n, K_ in LAB_PACKS)])]
        for gn, K in groups:
            K = [k for k in K if k in NM and k not in used]
            if not K: continue
            g = QGroupBox(gn); gl = QVBoxLayout(g); bl.addWidget(g)
            for k in K:
                used.add(k); cb = QCheckBox(NM[k][0] + ('　（已經打開）' if L.get(k) else '')); cb.setChecked(False); cb.setEnabled(not L.get(k)); cb.setToolTip(NM[k][1]); gl.addWidget(cb); cbs[k] = cb
                dl = QLabel(NM[k][1] if len(NM[k][1]) <= 90 else NM[k][1][:88] + '…'); dl.setObjectName('muted'); dl.setWordWrap(True); dl.setContentsMargins(24, 0, 0, 4); gl.addWidget(dl)
        row = QHBoxLayout(); bn = QPushButton('之後再說'); bt = QPushButton('📖 看完整說明'); bo = QPushButton('✅ 打開勾選的'); row.addWidget(bn); row.addWidget(bt); row.addStretch(1); row.addWidget(bo); v.addLayout(row)
        def ok_():
            K = [k for k, c in cbs.items() if c.isChecked()]
            if K: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, **{k: True for k in K})); self.apply_new_labs(); self.msg(f'🧪 打開了 {len(K)} 個新功能')
            d.accept()
        bo.clicked.connect(ok_); bn.clicked.connect(d.reject); bt.clicked.connect(lambda: (d.reject(), self.enter(8)))
        ENG.cfg.set('tour_seen', self.TOUR_VER); d.exec(); d.deleteLater()

    def goal_dlg(self):
        n, ok = QInputDialog.getInt(self, '🎯 每日分級目標', '一天要分級幾部？', int(ENG.cfg.get('daily_goal_n') or 100), 1, 100000, 10)
        if not ok: return
        ENG.day_goal_set(n); self._goal_refresh(True)
        O = [('傍晚 6 點', 18), ('晚上 8 點', 20), ('晚上 9 點', 21), ('晚上 10 點', 22), ('晚上 11 點', 23), ('不要提醒', 24)]; cur = int(lab_cfg().get('goal_nag_h') or 21)   # V0.3.99 幾點提醒
        t, ok2 = QInputDialog.getItem(self, '🎯 每日分級目標', '還沒達成的話，幾點提醒一次？', [x[0] for x in O], next((i for i, x in enumerate(O) if x[1] == cur), 2), False)
        if ok2: ENG.cfg.set('lab', dict(ENG.cfg.get('lab') or {}, goal_nag_h=dict(O)[t]))
        self.msg(f'🎯 目標改成每天 {n:,} 部' + (f'（{t}提醒）' if ok2 and dict(O)[t] < 24 else ''))

    def space_dlg(self):
        """V0.2.43 💽 硬碟空間地圖."""
        if not lab_cfg().get('space_map'): self.msg('💽 空間地圖在 🧪 實驗工作區 →「🆕 新功能」打開'); return
        def show(R):
            try:
                d = QDialog(self); d.setWindowTitle('💽 硬碟空間地圖'); d.resize(860, 120 + 74 * max(1, len(R))); v = QVBoxLayout(d)
                lg = QLabel('　'.join(f"<span style='color:{c}'>■</span> {n}" for c, n in ((GC['S'], 'S'), (GC['A'], 'A'), (GC['E'], 'E'), (GC['F'], 'F 待刪'), ('#9aa0a6', '未分級'), ('#5c6168', '影片庫以外的檔案'))) + '　□ 剩下')
                lg.setTextFormat(Qt.RichText); v.addWidget(lg)
                for o in R:
                    h = QLabel(f"<b>{o['d']}:</b> {html_esc(o.get('label') or '')}　影片 {o['n']:,} 部・{fmt_b(o['lib'])}" + (f"　總共 {fmt_b(o['total'])}・剩 <b>{fmt_b(o['free'])}</b>" if o.get('total') else '　（現在沒接上）') +
                               (f"　<span style='color:{GC['F']}'>F 待刪 {o['nF']:,} 部＝清掉能空出 {fmt_b(o['F'])}</span>" if o.get('F') else '') + (f"　未分級 {fmt_b(o[''])}" if o.get('') else '') +
                               ((f"<br>📉 最近每天少 {fmt_b(o['per_day'])}" + (f"，照這速度大約 <b style='color:#ff8a65'>{o['days_full']:g} 天</b>會滿" if o.get('days_full') else '')) if (o.get('per_day') or 0) > 1e8 else ''))
                    h.setTextFormat(Qt.RichText); v.addWidget(h); v.addWidget(SpaceBar(o))
                if not R: v.addWidget(QLabel('影片庫還沒有影片'))
                v.addStretch(1); b = QPushButton('關閉'); b.clicked.connect(d.accept); v.addWidget(b); d.exec(); d.deleteLater()
            except Exception: ENG.log.err('空間地圖')
        bg(ENG.space_map, show)

    NEW_WIDGETS = (('browse.resw', 'res_chips'), ('browse.b_rnd', 'random_pick'), ('browse.b_rec', 'recent_dirs'), ('b_pv', 'privacy'), ('movep.b_pcs', 'pc_overview'), ('browse.b_cre', 'creators'), ('browse.durw', 'dur_chips'), ('browse.b_csv', 'list_csv'), ('browse.b_view', 'views'), ('browse.b_mon', 'months'),
                   ('movep.b_smap', 'space_map'), ('movep.b_empty', 'empty_dirs'), ('b_goal', 'goal'), ('b_spr', 'sprint'), ('b_rep', 'report'))

    def apply_new_labs(self):
        """V0.2.33 🆕 新功能開關改了（電腦或手機）：畫面上跟著顯示／藏起來（V0.2.48 一個壞掉不影響其他的）."""
        L = lab_cfg()
        for path_, k_ in self.NEW_WIDGETS:
            try:
                o_ = self
                for a_ in path_.split('.'): o_ = getattr(o_, a_, None)
                if o_ is not None: o_.setVisible(bool(L.get(k_)))
            except Exception: ENG.log.err(f'套用新功能開關 {path_}')
        try:
            if L.get('daily_goal'): self.b_goal.setVisible(False)              # V0.2.68 原本的「每日整理目標」開著就用原本那個，不重複顯示
        except Exception: pass
        try: self.browse.legend.setVisible(bool(L.get('scenes') or L.get('bookmarks')))
        except Exception: pass
        try:
            if not L.get('privacy') and ENG.cfg.get('privacy_on'): self.set_privacy(False)
        except Exception: pass
        try:
            if getattr(self, 'toolp', None) is not None: self.toolp.build()
        except Exception: ENG.log.err('工具箱')
        try:
            for k_, cb_ in getattr(getattr(self, 'lab', None), 'new_cb', {}).items():
                if cb_.isChecked() != bool(L.get(k_)): cb_.blockSignals(True); cb_.setChecked(bool(L.get(k_))); cb_.blockSignals(False)
        except Exception: ENG.log.err('套用新功能開關')
        if L.get('goal'): self._goal_refresh(True)

    def _goal_refresh(self, force=False):
        """V0.2.48 🎯 今天分級幾部：背景查（不卡畫面），20 秒一次."""
        if not force and time.time() - getattr(self, '_goal_t', 0) < 20: return
        self._goal_t = time.time()
        def got(G):
            try:
                if not G: return
                self.b_goal.setText(('🎉' if G['done'] else '🎯') + f" 今天 {G['n']:,}／{G['goal']:,}" + (f"　🔥{G['streak']}" if G.get('streak', 0) >= 2 else ''))
                self.b_goal.setToolTip(f"今天分級 {G['n']:,} 部，目標 {G['goal']:,}" + (f"\n🔥 已經連續 {G['streak']} 天達成" if G.get('streak') else '') + '\n（點一下改目標）')
                if G['done'] and getattr(self, '_goal_said', '') != time.strftime('%Y%m%d'): self._goal_said = time.strftime('%Y%m%d'); self.msg(f"🎉 今天的分級目標 {G['goal']:,} 部達成！")
                if not G['done'] and time.localtime().tm_hour >= int(lab_cfg().get('goal_nag_h') or 21) and int(lab_cfg().get('goal_nag_h') or 21) < 24 and ENG.cfg.get('goal_nag') != time.strftime('%Y%m%d'):   # V0.3.46 晚上 9 點提醒一次
                    ENG.cfg.set('goal_nag', time.strftime('%Y%m%d')); self.msg(f"🎯 今天還差 {G['goal'] - G['n']:,} 部就達成" + (f"（連續 {G['streak']} 天的紀錄別斷了 🔥）" if G.get('streak') else ''), 15000)
            except Exception: pass
        bg(ENG.day_goal, got)

    def keys_dlg(self):
        """V0.2.39 ⌨ 快捷鍵一覽：播放器那段讀你自己設定的鍵."""
        if not lab_cfg().get('keys_help'): self.msg('⌨ 快捷鍵一覽在 🧪 實驗工作區 →「🆕 新功能」打開'); return
        try:
            d = QDialog(self); d.setWindowTitle('⌨ 快捷鍵一覽'); d.resize(720, 640); v = QVBoxLayout(d)
            q = QLineEdit(); q.setPlaceholderText('🔎 找快捷鍵或動作'); q.setClearButtonEnabled(True); v.addWidget(q)
            tb = QTextBrowser(); v.addWidget(tb, 1); secs = keys_sections()
            def paint(_t=''):
                f = q.text().strip().lower(); H = []
                for name, rows in secs:
                    R = [(k, n) for k, n in rows if not f or f in k.lower() or f in n.lower()]
                    if not R: continue
                    H.append(f'<h3 style="margin:10px 0 4px">{html_esc(name)}</h3><table cellspacing="0" cellpadding="3">' + ''.join(
                        f'<tr><td style="padding-right:18px"><code style="background:#33373d;color:#fff;padding:1px 6px;border-radius:4px">{html_esc(k)}</code></td><td>{html_esc(n)}</td></tr>' for k, n in R) + '</table>')
                tb.setHtml(''.join(H) or '<p>找不到</p>')
            q.textChanged.connect(paint); paint(); b = QPushButton('關閉'); b.clicked.connect(d.accept); v.addWidget(b); d.exec(); d.deleteLater()
        except Exception: ENG.log.err('快捷鍵一覽')

    def cmd_palette(self):
        if not lab_cfg().get('cmdk'): self.msg('⌘ 指令面板在 🧪 實驗工作區 →「🆕 新功能」打開'); return
        try: d = CmdPalette(self); d.move(self.x() + (self.width() - d.width()) // 2, self.y() + 90); d.exec(); d.deleteLater()
        except Exception: ENG.log.err('指令面板')

    def apply_pc(self):
        """V0.2.27 這台電腦的名稱／顏色改了：標題、圖示、托盤、封面馬上換."""
        try:
            self.icon = pc_badge(self.icon0); self.setWindowIcon(self.icon); QApplication.instance().setWindowIcon(self.icon)
            self.setWindowTitle(f'{APP_TITLE}  V{APP_VERSION}  ·  {ENG.pc_name()}')
            if self.tray: self.tray.setIcon(self.icon)
            self.cover.update()
            s_ = web_server(create=False)
            if s_ is not None: s_._icons = {}
        except Exception: ENG.log.err('套用電腦名稱／顏色')

    # ---------- 封面
    def show_cover(self):
        """回封面：播放視窗、浮窗先藏起來（不關，回來還在）."""
        for d in self.findChildren(QDialog):
            try:
                if d.isVisible(): d.hide(); self._hidden_dlg = getattr(self, '_hidden_dlg', []) + [d]
            except Exception: pass
        try:
            if self.jobs_pop is not None: self.jobs_pop.hide()
        except Exception: pass
        self.outer.setCurrentIndex(0); self.cover.refresh(); ENG.log.w('畫面：回到封面')

    def _lv_tick(self):
        try:
            import vs_yield; v = vs_yield.view(); self.lv.set(v)
        except Exception: pass

    def open_yield(self):
        try: YieldDlg(self).exec()
        except Exception: ENG.log.err('🤝 讓路視窗')

    def set_mode(self, m):
        """🎛 左上角切換：換到那一邊，左邊選單只留那一邊的分組，打開那一邊的 📊 總覽."""
        try:
            m = m if m in MODE_COL else 'vs'; self.nav.mode = m; self.msw.set(m); ENG.cfg.set('nav_mode', m); ENG.log.w(f'🎛 切到 {m}')
            self.enter(MODE_DASH[m])
        except Exception: ENG.log.err('🎛 切換')

    def open_archive(self):
        """V0.6.06 🗄 封存的功能（Ctrl+Shift+R）：R 碟清空搬移不在選單裡，避免誤按."""
        try:
            if self.outer.currentIndex() == 0: self.outer.setCurrentIndex(1)
            self._page(73); self.msg('🚚 多步搬硬碟（也在左邊「電腦與背景」裡）', 4000)
        except Exception: ENG.log.err('🗄 打開封存的功能')

    def enter(self, page):
        self.outer.setCurrentIndex(1); was_ = self.nav.currentRow(); self.nav.setCurrentRow(int(page))
        if was_ == int(page): self._page(int(page))
        for d in getattr(self, '_hidden_dlg', []):
            try: d.show()
            except Exception: pass
        self._hidden_dlg = []; ENG.log.w(f'畫面：從封面進入第 {page} 頁')

    def eventFilter(self, obj, e):
        try:
            if e.type() != _EV_PRESS: return False                              # V0.5.91 只看滑鼠按下（側鍵），其他事件馬上放行
            self.last_act = time.time()
            if e.button() in (Qt.BackButton, Qt.ForwardButton) and lab_cfg().get('swipe_nav'):   # V0.2.42 滑鼠側鍵換部
                if QApplication.activeWindow() is self and self.outer.currentIndex() == 1 and self.nav.currentRow() == 0:
                    self.browse.step_item(-1 if e.button() == Qt.BackButton else 1); return True
        except Exception: pass
        return False

    def _idle_check(self):
        self.last_act = max(self.last_act, user_last_input())
        ENG.last_user = self.last_act                                           # 給 🧪 背景加速判斷「電腦閒置」
        m = int(ENG.cfg.get('cover_idle_min') or 0)
        if m and self.outer.currentIndex() == 1 and time.time() - self.last_act > m * 60: self.show_cover(); ENG.log.w(f'閒置 {m} 分鐘，自動回到封面')

    def _page(self, i):
        i = int(i)
        if i == 10: i = 44                                                       # V0.5.00 舊的「🗂 審核」→ 🗂 整理的「影片快速分類」
        if i == 9: i = 40                                                        # 👤 人物 拿掉了 → 整理總覽
        if i == 66 and hasattr(self, 'browse'):                                  # V0.5.42 ④ 的「SortCut 讀不了的影片」＝檔案總管篩「⚠ 讀不了」（全部資料夾）
            try: self.nav.setCurrentRow(0); self.browse.use_view({'name': '⚠ 讀不了／可能壞掉', 'folder': '', 'flt': 'bad', 'sort': 'name', 'sub': True})
            except Exception: ENG.log.err('讀不了的影片')
            return
        review = False
        if not hasattr(self, 'stack'): return
        try:                                                                     # V0.5.70 切到哪一頁，左上角 🎛 就跟著換到那一邊
            pm = self.nav.page_mode(i)
            if pm and pm != getattr(self.nav, 'mode', ''): self.nav.mode = pm; self.msw.set(pm); ENG.cfg.set('nav_mode', pm); self.nav.apply_collapse()
        except Exception: pass
        if i == 73 and hasattr(self, 'rsp'):                                     # V0.5.85 🚚 R 碟清空搬移（V0.6.06 封存：只能用 Ctrl+Shift+R 打開，不記成「上次停在」）
            self.stack.setCurrentIndex(19)
            if self._cover_ready and self.outer.currentIndex() == 0: self.outer.setCurrentIndex(1)
            try: self.ptitle.setText('🗄 R 碟清空搬移（封存）')
            except Exception: pass
            ENG.log.w('畫面：切到「🚚 R 碟清空搬移」'); self.rsp.refresh(); return
        if i == 74 and hasattr(self, 'explore'):                                 # V0.6.19 🗺 檔案總覽
            self.stack.setCurrentIndex(20)
            if self._cover_ready and self.outer.currentIndex() == 0: self.outer.setCurrentIndex(1)
            if self._cover_ready: ENG.cfg.set('last_page', int(i))
            try: self.ptitle.setText('🗺 檔案總覽')
            except Exception: pass
            ENG.log.w('畫面：切到「🗺 檔案總覽」'); self.explore.refresh(); return
        if i in (70, 71, 72) and hasattr(self, 'dash'):                          # 📊 一頁總覽
            self.stack.setCurrentIndex(18)
            if self._cover_ready and self.outer.currentIndex() == 0: self.outer.setCurrentIndex(1)
            if self._cover_ready: ENG.cfg.set('last_page', int(i))
            try: self.ptitle.setText(f'📊 {self.nav.page_name(i)}')
            except Exception: pass
            ENG.log.w(f'畫面：切到「{self.nav.page_name(i)}」'); self.dash.show_kind({70: 'vs', 71: 'fc', 72: 'h265'}[i]); return
        if i in FC_PAGES:                                                        # 🗂 整理（FileCompare）：同一個嵌進來的畫面切到那一頁
            self.stack.setCurrentIndex(17)
            if self._cover_ready and self.outer.currentIndex() == 0: self.outer.setCurrentIndex(1)
            if self._cover_ready: ENG.cfg.set('last_page', int(i))
            try: self.ptitle.setText(f'🗂 整理 · {self.nav.page_icon(i)} {self.nav.page_name(i)}')
            except Exception: pass
            ENG.log.w(f'畫面：切到 🗂 整理「{self.nav.page_name(i)}」'); self.fcp.show_fc(FC_PAGES[i]); return
        if i in HZ_PAGES:                                                        # 🔥 HotZone 的頁面：同一個嵌進來的 HotZone 畫面切到那一頁
            self.stack.setCurrentIndex(12)
            if self._cover_ready and self.outer.currentIndex() == 0: self.outer.setCurrentIndex(1)
            if self._cover_ready: ENG.cfg.set('last_page', int(i))
            try: self.ptitle.setText(f'🔥 HotZone · {self.nav.page_name(i)}'.replace('HotZone · HotZone ', 'HotZone · '))
            except Exception: pass
            ENG.log.w(f'畫面：切到 HotZone「{self.nav.page_name(i)}」'); self.hzembed.show_hz(HZ_PAGES[i]); return
        self.stack.setCurrentIndex(0 if review else i)
        if self._cover_ready and self.outer.currentIndex() == 0: self.outer.setCurrentIndex(1)      # 程式自己切頁（例如「到這部」）就離開封面
        if self._cover_ready and i not in (4, 5, 10): ENG.cfg.set('last_page', int(i))
        try: self.ptitle.setText(f'{self.nav.page_icon(i)} {self.nav.page_name(i)}'.strip())
        except Exception: pass
        try: ENG.log.w(f'畫面：切到「{self.nav.page_name(i)}」')
        except Exception: pass
        if i == 1: self.conv.refresh_tab(); self.conv.goal.refresh()
        if i == 14: self.learnp.refresh()
        if review:
            try: self.browse.start_review()
            except Exception: ENG.log.err('分級模式')
        elif getattr(self.browse, 'focus_on', False) and (i != 0 or getattr(self.browse, '_review', False)):      # 離開分級／換到別頁：專注模式關掉、側邊欄回來
            try: self.browse._review = False; self.browse.set_focus_mode(False)
            except Exception: pass

    def _bg_all(self, pause):
        """左上「▶ 開始整理／■ 暫停背景」：預覽圖＋轉檔一起（跟手機的全部暫停一樣）."""
        try:
            self.bgp.b_th.setChecked(bool(pause)); ENG.th_paused = bool(pause)
            try: self.conv.b_pause.setChecked(bool(pause))
            except Exception: pass
            ENG.cv_paused = bool(pause)
            if hasattr(ENG, 'fc_pause_all'): ENG.fc_pause_all(bool(pause))      # V0.5.11 整理的背景也一起
            if not pause and not ENG.cfg.get('th_on'): ENG.cfg.set('th_on', True)
            self.msg('■ 背景工作全部暫停（正在做的做完就停）' if pause else '▶ 背景工作全部繼續', 5000); self._side_paint()
        except Exception: ENG.log.err('開始／暫停背景')

    def _bgst(self):
        """狀態列：有暫停／自動讓路的項目就顯示（V0.1.67）."""
        try:
            if lab_cfg().get('goal'): self._goal_refresh()
        except Exception: pass
        try:                                                                    # V0.4.32 📱 有手機剛登入：電腦跳提醒（不是你的話到工具箱登出它）
            NL_ = getattr(ENG, '_new_login', None)
            if NL_ and NL_[0] != getattr(ENG, '_nl_said', 0) and lab_cfg().get('web_devices'):
                ENG._nl_said = NL_[0]; t_ = f"📱 有手機剛登入網頁版：{NL_[1]}（{NL_[2]}）" + ('・👀 唯讀' if NL_[3] else '') + '　不是你的話：🧰 工具箱 →「📱 登入過的手機」登出它'
                self.msg(t_, 20000)
                try:
                    if self.tray: self.tray.showMessage('SortCut', t_[:120])
                except Exception: pass
        except Exception: pass
        try:                                                                    # V0.4.04 🔔 背景全部做完通知
            if lab_cfg().get('done_notify'):
                B_ = ENG.bg_busy()
                if B_ and not getattr(self, '_bz_t0', 0): self._bz_t0 = time.time(); self._bz_what = set()
                if B_: self._bz_what |= set(B_); self._bz_last = time.time()
                elif getattr(self, '_bz_t0', 0) and time.time() - getattr(self, '_bz_last', 0) > 20:   # 停 20 秒都沒新的才算真的做完
                    dur_ = getattr(self, '_bz_last', 0) - self._bz_t0; W_ = '、'.join(sorted(getattr(self, '_bz_what', set()))); self._bz_t0 = 0
                    if dur_ >= 300:
                        self.msg(f'🔔 背景全部做完了（{W_}，花了 {int(dur_ // 60)} 分鐘）', 20000)
                        try:
                            if self.tray: self.tray.showMessage('SortCut', f'🔔 背景全部做完了（{W_}）')
                        except Exception: pass
        except Exception: pass
        try:                                                                    # V0.4.03 ☕ 背景在做事時不睡（30 秒看一次）
            if time.time() - getattr(self, '_aw_t', 0) > 30:
                self._aw_t = time.time(); want = bool(lab_cfg().get('keep_awake') and ENG.bg_busy())
                if want != getattr(self, '_aw_on', False) or want: core.keep_awake(want); self._aw_on = want
        except Exception: pass
        try:                                                                    # V0.3.88 👀 休息提醒
            if lab_cfg().get('break_remind'):
                B_ = ENG.break_check()
                if B_ and getattr(self, '_brk_said', 0) != B_['id']:
                    self._brk_said = B_['id']; self.msg(f"👀 已經連續分級 {B_['mins']} 分鐘（{B_['n']} 部）了，站起來動一動、讓眼睛休息一下吧", 20000)
                    try:
                        if self.tray and not self.isActiveWindow(): self.tray.showMessage('SortCut', f"👀 連續分級 {B_['mins']} 分鐘了，休息一下吧")
                    except Exception: pass
        except Exception: pass
        try:                                                                    # V0.3.72 ⏱ 衝刺倒數
            if lab_cfg().get('sprint'):
                V = ENG.sprint_view()
                if not V: self.b_spr.setText('⏱ 衝刺'); self.b_spr.setStyleSheet('')
                else:
                    self.b_spr.setText((f"⏱ {V['left'] // 60}:{V['left'] % 60:02d}・{V['n']} 部" if V['on'] else f"🏁 {V['n']} 部・每分 {V['rate']:g}" + (' 🏆' if V.get('new_best') else '')))
                    self.b_spr.setStyleSheet('QPushButton{border-color:#ffc94d;color:#ffc94d}' if V['on'] else 'QPushButton{border-color:#45d483;color:#45d483}')
                    if V.get('done') and getattr(self, '_spr_said', 0) != ENG.cfg.get('sprint', {}).get('t0'):
                        self._spr_said = (ENG.cfg.get('sprint') or {}).get('t0'); self.msg(f"🏁 衝刺結束：{V['min']} 分鐘分了 {V['n']} 部（每分鐘 {V['rate']:g} 部）" + ('　🏆 新紀錄！' if V.get('new_best') else ''), 15000)
        except Exception: pass
        try:                                                                    # V0.3.63 📤 每天上傳目標
            if time.time() - getattr(self, '_upg_t', 0) > 20:
                self._upg_t = time.time()
                def _ug(G):
                    try:
                        if not G: self.b_upg.hide(); return
                        self.b_upg.setText(('🎉' if G['done'] else ('✅' if G.get('by') == 'pub' else '📤')) + f" {'發佈' if G.get('by') == 'pub' else '上傳'} {G['n']}／{G['goal']}"); self.b_upg.show()
                        if G['done'] and getattr(self, '_upg_said', '') != time.strftime('%Y%m%d'): self._upg_said = time.strftime('%Y%m%d'); self.msg(f"🎉 今天上傳 {G['goal']} 部的目標達成！")
                    except Exception: pass
                bg(ENG.up_goal, _ug)
        except Exception: pass
        try:                                                                    # V0.2.66 🌗 跟著時間換深色／淺色
            L_ = lab_cfg()
            if L_.get('auto_theme') and time.time() - getattr(self, '_at_t', 0) > 55:
                self._at_t = time.time(); a_, b_ = int(L_.get('theme_from', 7)), int(L_.get('theme_to', 19)); h_ = time.localtime().tm_hour
                want = 'light' if (a_ <= h_ < b_ if a_ <= b_ else (h_ >= a_ or h_ < b_)) else 'dark'
                if THEME_MODE['mode'] != want: self.set_theme(want); ENG.log.w(f'🌗 {h_} 點：自動換成{"淺色" if want == "light" else "深色"}')
        except Exception: pass
        try:
            CV = ENG.copy_view() if lab_cfg().get('copy_to') else None
            on_ = bool(CV and (CV['run'] or CV['q']))
            wt_ = (not CV['run'] and CV['q'] and (CV['paused'] or str(CV['last_err'] or '')))      # V0.3.92 排隊在等（暫停／時段外／讓路／硬碟沒接上）：說清楚在等什麼
            if on_ and wt_: self.b_copy.setText(f"📤 等待中・還有 {CV['q']}"); self.b_copy.setToolTip('📤 ' + ('⏸ 暫停中' if CV['paused'] else str(CV['last_err'])) + '（點一下看排隊）')
            elif on_: self.b_copy.setText(f"📤 {CV['pct']}%・還有 {CV['q']}・{fmt_b(CV['speed'])}/s"); self.b_copy.setToolTip(f"📤 {CV['cur']} → {CV['dir']}（好了 {CV['done']}、失敗 {CV['fail']}、已經有 {CV['skip']}）")
            elif self.b_copy.isVisible() and CV: self.msg(f"📤 複製完成：{CV['done']} 部" + (f"、失敗 {CV['fail']}（{CV['last_err']}）" if CV['fail'] else '') + (f"、已經有 {CV['skip']}" if CV['skip'] else ''))
            self.b_copy.setVisible(on_)
        except Exception: pass
        try:
            nm = dict((k, n) for k, _i, n in ENG.BG_KINDS); P = [nm.get(k, k) for k, v_ in list(ENG.bg_pause.items()) if v_]; H = [nm.get(k, k) for k in list(ENG.bg_auto)] + [nm.get(k, k) + '降速' for k in list(ENG.bg_slow)]
            t_ = ('⏸ ' + '、'.join(P) if P else '') + ('　' if P and H else '') + ('⚖ 讓路：' + '、'.join(H) if H else '')
            f_ = ENG.fc_bg() if hasattr(ENG, 'fc_bg') else None                   # V0.5.44 整理（FileCompare）暫停／讓路也寫在這顆（點一下到後台）
            if isinstance(f_, dict) and (f_['pause'] or f_['auto']):            # 「讓 SortCut 先用硬碟」很常出現（整理沒事做也會），只在整理頁和後台寫，這裡不吵
                t_ += ('　' if t_ else '') + '🗂 整理：' + '、'.join(x for x in (('⏸ ' + '、'.join(f_['pause'])) if f_['pause'] else '', ('⚖ ' + '、'.join(f_['auto'])) if f_['auto'] else '') if x)
            DW = ENG.disk_warn() if lab_cfg().get('disk_warn') else []                # V0.2.32
            if DW: t_ = ('⚠ 空間不足：' + '、'.join(f'{x["d"]} 剩 {fmt_b(x["free"])}' + (f'（約 {x["days_full"]:g} 天滿）' if x.get('days_full') is not None else '') for x in DW)) + ('　' + t_ if t_ else '')
            self.b_bgst.setText(t_); self.b_bgst.setVisible(bool(t_))
            self.b_bgst.setStyleSheet('QPushButton{color:#ff6577;font-weight:800}' if DW else '')
        except Exception: pass
        try: self._pill_apply()                                                 # V0.4.10 藏起來的狀態列按鈕
        except Exception: pass

    def set_theme(self, mode):
        mode = set_theme_mode(mode); ENG.cfg.set('ui_theme', mode)
        QApplication.instance().setStyleSheet(theme_qss(mode)); self.update()
        try: self.fcp.set_theme(mode)                                            # 🗂 整理 跟著換
        except Exception: pass
        for w_ in self.findChildren(QWidget):
            try: w_.update()
            except Exception: pass
        self.msg('主題：' + ('☀ 淺色' if mode == 'light' else '🌙 深色'), 3000)

    def set_zoom(self, z):
        z = max(70, min(160, int(z))); ENG.cfg.set('ui_zoom', z); QApplication.instance().setStyleSheet(theme_qss(None, z))
        try: self.fcp.set_theme(THEME_MODE['mode'], z)
        except Exception: pass
        self.zoom_l.setText(f'{z}%'); self.msg(f'介面大小 {z}%', 2500)

    def _side_paint(self, I=None):
        """側邊欄：大數字、開始／暫停按鈕、預覽圖按鈕、選單旁邊的數字、電腦狀態."""
        I = I or (getattr(ENG, 'info_c', {}).get('v') or {})
        th, cv = len(ENG.th_active), len(ENG.cv_active); paused = bool(ENG.th_paused) and bool(ENG.cv_paused)
        off = bool(getattr(ENG, 'offline', None)) if not callable(getattr(ENG, 'offline', None)) else False
        col = '#f0ad4e' if off else ('#45d483' if (th or cv) else ('#ff4d6d' if paused else '#7f8a99'))
        ng = int(I.get('nograde') or 0); lib = int(I.get('lib') or I.get('files') or 0)
        self.badge.set_counts(ng, lib, col, f'還沒分級 {ng:,} 部 · 待整理 {lib:,} 部（點一下＝檔案總管只看未分級）\n' +
                              ('背景工作：預覽圖做中 ' + str(th) + ' 部、轉檔中 ' + str(cv) + ' 部' if th or cv else ('背景工作全部暫停中' if paused else '背景工作：目前沒事')))
        self.b_go.setText('▶ 開始整理' if paused or not (th or cv) else '▶ 整理中'); self.b_pause.setText('■ 已暫停' if paused else '■ 暫停背景')
        tot = int(I.get('th_done') or 0) + int(I.get('th_left') or 0); left = int(I.get('th_left') or 0)
        if tot:
            pc = int((tot - left) * 100 / max(1, tot))
            self.b_thq.setText(f'🖼 預覽圖 {pc}%　{tot - left:,}／{tot:,}\n' + (('⏸ 暫停中' if ENG.th_paused else f'還要 {eta_txt(I["th_eta"])}' if I.get('th_eta') else f'還有 {left:,} 部') if left else '都做好了 ✔'))
        else: self.b_thq.setText('🖼 預覽圖：還沒有影片')
        self.nav.set_badge(1, f'{int(I.get("cv_wait") or 0):,}' if I.get('cv_wait') else '')
        self.nav.set_badge(0, f'{ng:,}' if ng else '')
        P = ENG.perf; g = P.gpu or {}
        rows = [('CPU', P.cpu, f'{P.cpu:.0f}%', None, '#4dc9ff', None), ('RAM', P.ram, f'{P.ram:.0f}%', None, '#b48cff', None)]
        if g:
            rows.append(('GPU', g.get('util'), f'{g.get("util", 0):.0f}%', g.get('temp'), '#45d483', None))
            if g.get('mem_t'): rows.append(('VRAM', 100 * g['mem'] / g['mem_t'], f'{100 * g["mem"] / g["mem_t"]:.0f}%', None, '#9aa5b3', None))
        self.sys_panel.set_rows(rows)

    def _hz_before(self):
        """（背景執行緒呼叫）在畫面執行緒關掉嵌著的 HotZone 畫面，等它真的結束."""
        ev = threading.Event()
        def k():
            try: self.hzembed._kill()
            finally: ev.set()
        BUS.call.emit(k); ev.wait(10); time.sleep(3)

    def msg(self, s, ms=6000):
        self.statusBar().showMessage(str(s), ms); ENG.log.w('畫面：' + str(s))

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
        bg(ENG.info, self._st)
        try:
            blue = len(ENG.cut_q) + (1 if ENG.cut_cur else 0) + len(ENG.cv_active) + int((getattr(ENG, 'info_c', {}).get('v') or {}).get('cv_wait', 0)) + len(ENG.op_q)
            self.b_jobs.set_counts(blue=blue); nc = len(ENG.cut_q) + (1 if ENG.cut_cur else 0)
            if self._cut_was and not nc:                                        # 初剪全部做完
                self.b_jobs.setStyleSheet('QPushButton{background:#1f6f4a;border-color:#45d483;font-weight:700}'); self.b_jobs.setText('✔ 初剪完成')
                self.msg('✔ 初剪全部做完了（點上面「✔ 初剪完成」看輸出檔，可以放心刪原檔）', 12000)
                QTimer.singleShot(12000, lambda: (self.b_jobs.setStyleSheet(''), self.b_jobs.setText('✂ 剪輯／轉檔')))
            self._cut_was = nc
            dh = getattr(ENG, 'db_health', None) or {}
            if dh.get('recover_msg') and not getattr(self, '_dbrec_shown', False):
                self._dbrec_shown = True; QMessageBox.warning(self, '資料庫自動修復', str(dh['recover_msg']) + '\n\n（LOG 有完整紀錄）')
            if dh.get('ok') is False and not getattr(self, '_dbbad_shown', False):
                self._dbbad_shown = True
                QMessageBox.warning(self, '資料庫可能壞掉了', f'檢查資料庫時發現問題：\n{str(dh.get("msg"))[:300]}\n\n影片檔本身沒事。建議到「設定 → 資料庫備份 → ↩ 從備份還原…」選最近一份好的備份。\n（在那之前不會再自動備份，免得好的備份被擠掉）')
            off = sorted((getattr(ENG, 'offline', None) or {}).keys())                # 硬碟離線：提醒一次（接回來也說一聲）
            if off != getattr(self, '_off_was', []):
                if off: self.msg('⚠ 硬碟離線：' + '、'.join(off) + '　這顆的預覽圖／轉檔先暫停，接回來會自動繼續（失敗的不會被當成壞檔）', 20000)
                elif getattr(self, '_off_was', []): self.msg('✅ 硬碟接回來了，繼續做', 8000)
                self._off_was = off
            mg = getattr(ENG, 'migrated', None)
            if mg and not getattr(self, '_mig_shown', False):
                self._mig_shown = True
                QMessageBox.information(self, '歸檔資料夾搬家', '以前放在硬碟最上層的資料夾，已經搬進每顆硬碟的 VideoSIFT 資料夾：\n\n' + '\n'.join(f'{a} → {b}' for a, b in mg[:12]) +
                                        '\n\n之後的初剪、收藏、待刪、原檔備份都放在這裡。（LOG 有完整紀錄）')
        except Exception: ENG.log.err('上方工作數字')

    def jobs_new(self, n):
        """按了輸出初剪：紅色數字加上這次要出幾個檔."""
        self.b_jobs.set_counts(red=self.b_jobs.red + int(n)); self.b_jobs.setStyleSheet(''); self.b_jobs.setText('✂ 剪輯／轉檔'); self._cut_was = max(self._cut_was, 1)
        QTimer.singleShot(300, self._status)

    def open_jobs(self):
        if self.jobs_pop is None: self.jobs_pop = JobsPopup(self)
        self.b_jobs.set_counts(red=0); self.jobs_pop.open_at(self.b_jobs); ENG.log.w('畫面：打開「剪輯／轉檔」浮窗')

    def _st(self, I):
        s = ENG.scan_st; th = len(ENG.th_active); cv = len(ENG.cv_active)
        txt = (f'　掃描中 {s["n"]:,}…' if s['running'] else '') + f'　影片 {I["files"]:,}　預覽圖 {I["th_done"]:,}／{I["th_done"] + I["th_left"]:,}' + (f'（做中 {th}）' if th else '') + \
              (f'　轉檔排隊 {I["cv_wait"]:,}（轉中 {cv}）' if I['cv_wait'] or cv else '') + (f'　初剪排隊 {len(ENG.cut_q)}' if ENG.cut_q or ENG.cut_cur else '')
        if I.get('th_eta') and I['th_left']: txt += f'　預覽圖預計還要 {eta_txt(I["th_eta"])}'
        self.stat.setText(txt)
        try: self._side_paint(I)
        except Exception: ENG.log.err('側邊欄')
        try: self._goal(I)
        except Exception: ENG.log.err('每日目標')
        if self.tray: self.tray.setToolTip('SortCut' + txt.replace('　', '\n'))
        self._notify_done(I)

    def _goal(self, I):
        """🧪 每日整理目標：今天分級 37／100 ▰▰▱▱▱；第一次達標說一聲（一天一次）."""
        on = bool(lab_cfg().get('daily_goal')); self.goal_l.setVisible(on)
        if not on: return
        n = int(I.get('graded_today') or 0); goal = max(1, int(ENG.cfg.get('daily_goal_n') or 100)); k = min(5, n * 5 // goal)
        done = n >= goal; col = '#45d483' if done else '#ffd84d'
        self.goal_l.setText(f'<span style="color:{col}">🎯 今天分級 <b>{n:,}</b>／{goal:,} ' + '▰' * k + '▱' * (5 - k) + (' 🎉' if done else '') + '</span>')
        today = time.strftime('%Y%m%d')
        if done and ENG.cfg.get('daily_goal_hit') != today:
            ENG.cfg.set('daily_goal_hit', today); self.msg(f'🎉 今天的目標 {goal:,} 部達成了！（目前 {n:,} 部）', 12000); ENG.log.w(f'每日整理目標達成：{n} / {goal}')

    def _notify_done(self, I):
        """預覽圖全部做完、轉檔全部轉完：右下角通知一次（睡一晚起來就知道）."""
        th_busy = I['th_left'] > 0; cv_busy = bool(I['cv_wait'] or ENG.cv_active)
        for key, busy, txt in (('th', th_busy, f'預覽圖全部做好了（共 {I["th_done"]:,} 部）'), ('cv', cv_busy, f'轉檔全部轉完了（完成 {I["cv_done"]:,} 部' + (f'，失敗 {I["cv_fail"]}' if I['cv_fail'] else '') + '）')):
            was = getattr(self, '_busy_' + key, None)
            if was and not busy:
                ENG.log.w('通知：' + txt); self.msg('✔ ' + txt, 15000)
                if self.tray:
                    try: self.tray.showMessage('SortCut', txt, QSystemTrayIcon.Information, 8000)
                    except Exception: pass
            setattr(self, '_busy_' + key, busy)

    def _lag(self):
        now = time.time(); gap = now - self.lag_last - 0.5; self.lag_last = now
        try: lim = float(ENG.cfg.get('freeze_log_s') or 2)
        except Exception: lim = 2.0
        if gap >= lim:
            ENG.log.w(f'畫面卡了 {gap:.1f} 秒　頁面={self.nav.currentRow()}　預覽圖做中 {len(ENG.th_active)}　轉檔中 {len(ENG.cv_active)}　CPU {ENG.perf.cpu:.0f}%', 'ui_freeze_log.txt')

    def to_tray(self):
        if self.tray: self.hide(); self.tray.showMessage('SortCut', '在背景繼續做預覽圖和轉檔；點右下角圖示打開', QSystemTrayIcon.Information, 3000)
        else: self.showMinimized()

    def from_tray(self):
        if ENG.cfg.get('cover_on_restore'): self.show_cover()
        self.show(); self.setWindowState(self.windowState() & ~Qt.WindowMinimized); self.raise_(); self.activateWindow()

    def closeEvent(self, e):
        if self._handoff: e.accept(); return                                    # 熱更新：舊視窗收掉，程式不關
        if not self.quitting and self.tray and ENG.cfg.get('close_to_tray'):
            e.ignore(); self.to_tray(); return
        self.quitting = True
        if self.pf is not None: self.pf.close()
        if self.tray: self.tray.hide()
        try:
            s_ = web_server(create=False)
            if s_ is not None: s_.close()
        except Exception: pass
        try: self.hzembed.shutdown()
        except Exception: pass
        try:                                                                    # 🗂 整理（FileCompare）的背景工作也收掉
            import fc_app as F_
            F_.embed_shutdown()
        except Exception: pass
        mark_clean_exit(); ENG.shutdown(); e.accept(); QApplication.instance().quit()

    def really_quit(self):
        busy = len(ENG.cv_active) + len(ENG.th_active) + (1 if ENG.cut_cur else 0)
        if busy and QMessageBox.question(self, '結束', f'還有 {busy} 個工作在做（下次打開會接著做）。確定結束？') != QMessageBox.Yes: return
        self.quitting = True; self.close()

    def restart(self):
        self.quitting = True; mark_clean_exit()
        exe = sys.executable; rest = [a for a in sys.argv[1:] if a != '--restart' and not a.startswith('--oldpid=')] + ['--restart', f'--oldpid={os.getpid()}']
        args = rest if getattr(sys, 'frozen', False) else [str(HERE / 'app.py')] + rest
        try: subprocess.Popen([exe] + args, cwd=str(ROOT), creationflags=0x00000008 if core.IS_WIN else 0)
        except Exception as ex: QMessageBox.warning(self, '重新開啟', f'沒辦法自己重開，請手動打開程式：{ex}')
        self.close()


def _install_guards(app):
    """防當機／查問題：程式整個掛掉的傾印、背景執行緒的錯誤、Qt 的警告、畫面卡住時卡在哪一行。熱更新時新版也會叫一次（不重複裝）."""
    sys.excepthook = lambda t, v, tb: _eng_log('未處理的錯誤（程式沒有關）：\n' + ''.join(traceback.format_exception(t, v, tb)), 'error_log.txt')
    threading.excepthook = lambda a: _eng_log(f'背景執行緒 {getattr(a.thread, "name", "?")} 出錯（程式沒有關）：\n' + ''.join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)), 'error_log.txt')
    seen = {}
    def qt_msg(mode, ctx, msg):
        try:
            k = str(msg)[:200]; now = time.time()
            if now - seen.get(k, 0) < 60: return
            seen[k] = now
            if len(seen) > 500: seen.clear()
            _eng_log(f'Qt {int(mode) if not hasattr(mode, "name") else mode.name}：{msg}', 'qt_log.txt')
        except Exception: pass
    try: qInstallMessageHandler(qt_msg)
    except Exception: pass
    try: sys.setswitchinterval(0.002)                                           # V0.5.91 背景很忙時，畫面要用 Python 也能更快輪到（預設 5 ms）
    except Exception: pass
    if getattr(app, '_vs_guards', False): return
    app._vs_guards = True
    try:
        (ROOT / 'LOG').mkdir(exist_ok=True); fh = open(ROOT / 'LOG' / 'crash_dump.txt', 'a', encoding='utf-8')
        fh.write(f'\n===== {time.strftime("%Y-%m-%d %H:%M:%S")} 啟動 V{APP_VERSION}（如果程式整個掛掉，這下面會有每條執行緒在做什麼）=====\n'); fh.flush()
        faulthandler.enable(file=fh, all_threads=True); app._vs_fault_fh = fh
    except Exception: pass
    app._vs_hb = time.time()
    def watchdog():
        dumped = 0
        while True:
            time.sleep(0.5)
            try:
                gap = time.time() - float(getattr(app, '_vs_hb', time.time()))
                e = getattr(app, '_vs_eng', None)
                lim = max(3.0, float(e.cfg.get('freeze_log_s') or 2) + 1.0) if e else 4.0
                if gap >= lim and not dumped:
                    fr = sys._current_frames().get(threading.main_thread().ident)
                    stack = ''.join(traceback.format_stack(fr)[-14:]) if fr else '（讀不到）'
                    oth = ''                                                     # V0.5.91 也記其他執行緒在做什麼（看是誰把 Python 佔住）
                    try:
                        nm_ = {t.ident: t.name for t in threading.enumerate()}; mi = threading.main_thread().ident
                        for tid, f_ in list(sys._current_frames().items()):
                            if tid == mi or nm_.get(tid, '').startswith('VsUiWatchdog'): continue
                            st_ = traceback.extract_stack(f_)[-3:]
                            if not st_ or st_[-1].name in ('wait', 'sleep', '_wait_for_tstate_lock', 'select', 'accept', 'readinto', 'get'): continue
                            oth += f"  〔{nm_.get(tid, tid)}〕 " + ' ← '.join(f'{os.path.basename(x.filename)}:{x.lineno} {x.name}' for x in reversed(st_)) + '\n'
                    except Exception: pass
                    _eng_log(f'⚠ 畫面已經卡住 {gap:.1f} 秒，主執行緒現在卡在：\n{stack}' + (f'其他在跑的：\n{oth}' if oth else ''), 'ui_freeze_log.txt'); dumped = 1
                elif gap >= 20 and dumped == 1:
                    fr = sys._current_frames().get(threading.main_thread().ident)
                    _eng_log(f'⚠ 畫面還是卡住（{gap:.0f} 秒）：\n' + (''.join(traceback.format_stack(fr)[-14:]) if fr else ''), 'ui_freeze_log.txt'); dumped = 2
                elif gap < 1 and dumped:
                    dumped = 0
            except Exception: pass
    threading.Thread(target=watchdog, name='VsUiWatchdog', daemon=True).start()


def _eng_log(msg, f='app_log.txt'):
    try:
        e = getattr(QApplication.instance(), '_vs_eng', None) or ENG
        e.log.w(msg, f)
    except Exception:
        try:
            with open(ROOT / 'LOG' / f, 'a', encoding='utf-8') as fh: fh.write(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}\n')
        except Exception: pass


def _connect_peer(app):
    srv = getattr(app, '_vs_srv', None)
    if srv is None: return
    try: srv.newConnection.disconnect()
    except Exception: pass
    def _peer():
        c = srv.nextPendingConnection()
        if c: c.disconnectFromServer(); c.deleteLater()
        w = getattr(app, '_vs_main', None)
        if w is not None and not w.quitting: w.from_tray()
    srv.newConnection.connect(_peer)


def web_server(create=True):
    """📱 手機網頁伺服器（放在 QApplication 上，熱更新時換成新版的）."""
    app = QApplication.instance(); s = getattr(app, '_vs_web', None)
    if type(s).__name__ != 'WebServer': s = None
    if s is None and create:
        s = vs_web.WebServer(lambda: QApplication.instance()._vs_eng, lambda: QApplication.instance()._vs_main, ui, lambda: sys.modules[__name__], APP_VERSION, LAB_LIST)
        app._vs_web = s
    return s


def web_apply():
    """照設定開／關手機網頁（埠、區網選項改了就重開）."""
    if SELFTEST and not os.environ.get('VIDEOSIFT_WEBTEST'): return
    try:
        on = bool(ENG.cfg.get('web_on')); port = int(ENG.cfg.get('web_port') or 8461); lan = bool(ENG.cfg.get('web_lan'))
        s = web_server(create=on)
        if s is None: return
        if not on: s.close(); return
        if s.running and s.port == port and s.bind == ('0.0.0.0' if lan else '127.0.0.1'): return
        s.start(port, lan)
    except Exception: ENG.log.err('手機網頁 開／關')


def web_restart_new():
    """熱更新：舊版的伺服器關掉，換成新版的（同一個埠）。埠還沒放開就 1 秒後再試."""
    app = QApplication.instance(); old = getattr(app, '_vs_web', None)
    if type(old).__name__ == 'WebServer':
        try: old.close()
        except Exception: pass
        app._vs_web = None
    def again(n=0):
        web_apply(); s = web_server(create=False)
        if s is not None and ENG.cfg.get('web_on') and not s.running and n < 5: QTimer.singleShot(1000, lambda: again(n + 1))
    again()


def hot_start(old_eng, state):
    """熱更新進來的入口（舊版呼叫）：新引擎（還沒開始跑）＋新視窗。失敗就丟例外，舊版會還原."""
    global BUS, ENG, LOADER
    app = QApplication.instance(); BUS = Bus(); LOADER = ImgLoader()
    ENG = core.Engine(ROOT, adopt=old_eng, start=False, version=APP_VERSION)
    old_main = getattr(app, '_vs_main', None); old_e = getattr(app, '_vs_eng', None); before = set(map(id, QApplication.topLevelWidgets()))
    try:
        w = Main(adopt=state)
        app._vs_main = w; app._vs_eng = ENG; _install_guards(app); _connect_peer(app)
        try: app.commitDataRequest.disconnect()
        except Exception: pass
        app.commitDataRequest.connect(_on_commit)
        if state.get('perf'): w.b_perf.setChecked(True)
        try: web_restart_new()
        except Exception: ENG.log.err('熱更新：手機網頁換新版')
    except Exception:
        for tw in QApplication.topLevelWidgets():                              # 建到一半的新視窗：計時器、托盤、浮窗都收掉，不留第二個圖示
            if id(tw) in before: continue
            try:
                if isinstance(tw, Main): tw.handoff()
                tw.close(); tw.deleteLater()
            except Exception: pass
        try: app.removeEventFilter(w)
        except Exception: pass
        app._vs_main = old_main; app._vs_eng = old_e
        try:
            if old_main is not None: app.commitDataRequest.connect(_on_commit)
        except Exception: pass
        ENG.discard(); raise
    return w, ENG


# ============================================================ V0.1.75 閃退自動重開
WATCHDOG_PS1 = r'''param([int]$procid, [string]$flag, [string]$exe, [string]$argline, [string]$cwd, [string]$log, [long]$ft = 0)
try {
  $p = Get-Process -Id $procid -ErrorAction SilentlyContinue
  if ($p -and ($ft -eq 0 -or [math]::Abs($p.StartTime.ToFileTimeUtc() - $ft) -lt 20000000)) { $p.WaitForExit() }
} catch {}
Start-Sleep -Seconds 4
if (Test-Path -LiteralPath $flag) { Remove-Item -LiteralPath $flag -ErrorAction SilentlyContinue; exit }
$t = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Add-Content -LiteralPath $log -Value "[$t] watchdog: SortCut (PID $procid) did not exit normally -> restarting" -Encoding UTF8
if ($argline) { Start-Process -FilePath $exe -ArgumentList $argline -WorkingDirectory $cwd } else { Start-Process -FilePath $exe -WorkingDirectory $cwd }
'''


def run_state_path(): return ENG.data / 'run_state.json'


def _on_commit(_m=None):
    """Windows 關機／登出：標記正常結束（不要重開）。如果關機被取消（別的程式擋住、按了取消），1 分鐘後還活著就把記號拿掉，之後真的閃退還是會重開."""
    app = QApplication.instance()
    try: setattr(getattr(app, '_vs_main', None), 'quitting', True)
    except Exception: pass
    mark_clean_exit()
    try: QTimer.singleShot(60000, _commit_cancelled)
    except Exception: pass


def _commit_cancelled():
    try:
        (ENG.data / f'clean_exit_{os.getpid()}.flag').unlink()
    except Exception: pass
    try:
        st = json.loads(run_state_path().read_text(encoding='utf-8')) if run_state_path().exists() else {}
        st.update(clean=False); run_state_path().write_text(json.dumps(st), encoding='utf-8')
    except Exception: pass
    try:
        w = getattr(QApplication.instance(), '_vs_main', None)
        if w is not None: w.quitting = False
        ENG.log.w('Windows 關機／登出被取消：程式還開著，看門狗照常（閃退會自動重開）')
    except Exception: pass


def _proc_ft():
    """這個程序的建立時間（FILETIME，UTC）：給看門狗確認 PID 沒有被別的程式重用."""
    try:
        import ctypes
        from ctypes import wintypes
        a, b, c, d = (wintypes.FILETIME() for _ in range(4))
        if ctypes.windll.kernel32.GetProcessTimes(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(a), ctypes.byref(b), ctypes.byref(c), ctypes.byref(d)):
            return (a.dwHighDateTime << 32) | a.dwLowDateTime
    except Exception: pass
    return 0


def _wmsg(text, ms):
    try:
        w = getattr(QApplication.instance(), '_vs_main', None)
        if w is not None: w.msg(text, ms)
    except Exception: pass


def mark_clean_exit():
    """正常結束（關閉、重開、熱更新重開、Windows 關機）：告訴看門狗不用重開."""
    try:
        (ENG.data / f'clean_exit_{os.getpid()}.flag').write_text(time.strftime('%Y-%m-%d %H:%M:%S'), encoding='utf-8')
        st = json.loads(run_state_path().read_text(encoding='utf-8')) if run_state_path().exists() else {}
        st.update(clean=True, t_end=time.time()); run_state_path().write_text(json.dumps(st), encoding='utf-8')
    except Exception: pass


def arm_watchdog(win=None):
    """程式開起來時：①看上次是不是閃退（沒有正常結束）→ 記 LOG、提醒 ②開一個看門狗（Windows PowerShell，跟主程式分開），
    主程式不見了又沒有正常結束的記號 → 自動重開（背景工作、轉檔排隊、初剪、重新驗證都會接著做）. 10 分鐘內閃退 3 次就先不重開."""
    app = QApplication.instance()
    if getattr(app, '_vs_wd_armed', False) or SELFTEST: return
    app._vs_wd_armed = True; app.aboutToQuit.connect(mark_clean_exit)
    try:
        st = json.loads(run_state_path().read_text(encoding='utf-8')) if run_state_path().exists() else {}
    except Exception: st = {}
    crashes = [t for t in (st.get('crashes') or []) if time.time() - t < 600]
    if st and st.get('clean') is False:
        crashes.append(time.time()); ENG.log.w(f'⚠ 上次（PID {st.get("pid")}，{time.strftime("%m-%d %H:%M", time.localtime(st.get("t", 0)))} 開的）沒有正常結束（閃退／當機）' + ('，看門狗自動重開了' if '--after-crash' in sys.argv else ''))
        safe = len(crashes) >= 2                                                # 10 分鐘內第 2 次閃退：先把背景工作暫停（可能就是它把電腦壓垮的）
        if safe:
            try: ENG.bg_all(True); ENG.log.w(f'⚠ 10 分鐘內閃退 {len(crashes)} 次：背景工作先全部暫停（到「⏯ 後台」按繼續）')
            except Exception: ENG.log.err('閃退後暫停背景')
        QTimer.singleShot(4000, lambda: _wmsg('⚠ 上次程式意外關閉（閃退）' + ('，已經自動重開，' if '--after-crash' in sys.argv else '，') +
                                              ('短時間閃退好幾次，背景工作先全部暫停（到「⏯ 後台」按繼續）' if safe else '背景工作、轉檔排隊、初剪會接著做') + '（LOG 有紀錄）', 20000))
    try: run_state_path().write_text(json.dumps({'pid': os.getpid(), 't': time.time(), 'clean': False, 'crashes': crashes, 'ver': APP_VERSION}), encoding='utf-8')
    except Exception: pass
    if not core.IS_WIN or ENG.cfg.get('auto_restart') is False: return
    if len(crashes) >= 3:
        ENG.log.w(f'⚠ 10 分鐘內閃退 {len(crashes)} 次：這次先不開看門狗（避免一直重開），請看 LOG／crash_dump.txt')
        QTimer.singleShot(5000, lambda: _wmsg(f'⚠ 10 分鐘內閃退 {len(crashes)} 次，這次先不自動重開；請把 LOG 資料夾傳給我看', 30000)); return
    try:
        ps1 = ENG.data / 'vs_watchdog.ps1'; ps1.write_text(WATCHDOG_PS1, encoding='utf-8-sig')
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
        how = ''
        for fl, nm in ((0x08000000 | 0x00000200 | 0x01000000, '獨立'), (0x08000000 | 0x00000200, '同一個工作群組（主程式被整組關掉時看門狗也會不見）')):   # 不開視窗＋自己一組（＋脫離工作群組）
            try: app._vs_wd = subprocess.Popen(cmd, creationflags=fl, close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); how = nm; break
            except OSError: continue
        if how: ENG.log.w(f'看門狗開好了（{how}）：主程式閃退會自動重開（PID {os.getpid()}）')
        else: ENG.log.w('⚠ 看門狗開不起來（PowerShell 不能用？）：閃退後不會自動重開')
        for old in ENG.data.glob('clean_exit_*.flag'):                         # 舊的記號清掉
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
    global BUS, ENG, LOADER
    t_boot = time.time()
    app = QApplication.instance() or QApplication(sys.argv); app.setApplicationName('VideoSift'); app.setStyleSheet(STYLE); app.setQuitOnLastWindowClosed(False)
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    if not SELFTEST:
        t_end = time.time() + (25 if '--restart' in sys.argv else 0)
        opid = next((int(a.split('=', 1)[1]) for a in sys.argv if a.startswith('--oldpid=') and a.split('=', 1)[1].isdigit()), 0)
        if opid: t_end = time.time() + 120                                      # 重開：舊的關得比較慢（要停 FFmpeg）就多等，不要跳「已經開著了」
        while True:                                                             # 重新開啟時：等舊的關掉
            s = QLocalSocket(); s.connectToServer('VideoSift_single_v1')
            if not s.waitForConnected(300): break
            s.abort()
            if opid and time.time() <= t_end and _pid_gone(opid): time.sleep(0.5); continue
            if time.time() > t_end:
                QMessageBox.information(None, 'SortCut', 'SortCut 已經開著了（看右下角的圖示）。'); return 0
            time.sleep(0.5)
        srv = QLocalServer(); QLocalServer.removeServer('VideoSift_single_v1'); srv.listen('VideoSift_single_v1'); app._vs_srv = srv
    BUS = Bus(); LOADER = ImgLoader(); ENG = core.Engine(ROOT, version=APP_VERSION); app._vs_eng = ENG
    _install_guards(app)
    try: arm_watchdog()                                                         # 越早越好：剛開、接續上次工作時最容易又被壓垮
    except Exception: ENG.log.err('看門狗')
    w = Main(); w.show(); app._vs_main = w
    web_apply(); QTimer.singleShot(2500, w.browse.refresh_people_filter)
    ENG.log.w(f'啟動完成：畫面出來花 {time.time() - t_boot:.1f} 秒')
    app.commitDataRequest.connect(_on_commit)                                  # Windows 關機／登出：不要擋、不要重開
    if not SELFTEST: _connect_peer(app)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())

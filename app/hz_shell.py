"""HotZone FM — desktop window (PySide6 + Qt WebEngine). Shows the same page as the remote browser, plus what only
a desktop program can do:

  * drag files IN from Windows Explorer (the drop is caught here and handed to the page with real paths)
  * drag files OUT to Explorer / other programs (QDrag with file URLs)
  * Windows clipboard: Ctrl+C in Explorer -> Ctrl+V here, and the other way round (cut / copy kept)
  * open files with their program, show in Explorer, Windows "Properties" dialog, folder picker
  * tray icon: closing the window keeps the background engine (queue, hot zone, remote access) running

This window runs without administrator rights on purpose: Windows blocks drag & drop from Explorer into
elevated windows. The engine (separate process) has the rights.
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import time

from PySide6.QtCore import Qt, QUrl, QObject, Slot, QTimer, QEvent, QMimeData, QSettings, QByteArray, QProcess, QDir, QFile, QIODevice
from PySide6.QtGui import QIcon, QDrag, QDesktopServices, QAction, QGuiApplication, QPixmap, QImage
from PySide6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu, QFileDialog, QMessageBox, QLabel, QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings, QWebEngineScript
from PySide6.QtWebChannel import QWebChannel

IS_WIN = os.name == 'nt'
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DROPEFFECT_FMT = 'application/x-qt-windows-mime;value="Preferred DropEffect"'


def native(p):
    return QDir.toNativeSeparators(p)


class Bridge(QObject):
    """Object `hz` on the page (QWebChannel). Every slot is safe to call from JavaScript."""
    def __init__(self, win):
        super().__init__(win); self.win = win

    @Slot(str)
    def openLocal(self, path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @Slot(str)
    def reveal(self, path):
        if IS_WIN: subprocess.Popen('explorer.exe /select,"%s"' % os.path.normpath(path))
        else: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    @Slot(str)
    def properties(self, path):
        if not IS_WIN: return
        import ctypes
        from ctypes import wintypes

        class SEI(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('fMask', wintypes.ULONG), ('hwnd', wintypes.HWND), ('lpVerb', wintypes.LPCWSTR),
                        ('lpFile', wintypes.LPCWSTR), ('lpParameters', wintypes.LPCWSTR), ('lpDirectory', wintypes.LPCWSTR), ('nShow', ctypes.c_int),
                        ('hInstApp', wintypes.HINSTANCE), ('lpIDList', ctypes.c_void_p), ('lpClass', wintypes.LPCWSTR), ('hkeyClass', wintypes.HKEY),
                        ('dwHotKey', wintypes.DWORD), ('hIcon', wintypes.HANDLE), ('hProcess', wintypes.HANDLE)]
        s = SEI(); s.cbSize = ctypes.sizeof(SEI); s.fMask = 0x0000000C; s.hwnd = int(self.win.winId())
        s.lpVerb = 'properties'; s.lpFile = os.path.normpath(path); s.nShow = 1
        ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(s))

    @Slot(str)
    def startDrag(self, paths_json):
        try: paths = [p for p in json.loads(paths_json) if p]
        except Exception: return
        if not paths: return
        md = QMimeData(); md.setUrls([QUrl.fromLocalFile(p) for p in paths])
        md.setData('application/x-hz-paths', QByteArray(paths_json.encode('utf-8')))
        drag = QDrag(self.win)
        drag.setMimeData(md)
        pm = QPixmap(30, 30); pm.fill(Qt.transparent)
        drag.setPixmap(self.win.windowIcon().pixmap(28, 28) if not self.win.windowIcon().isNull() else pm)
        self.win.dragging_out = True
        try: drag.exec(Qt.CopyAction | Qt.MoveAction, Qt.CopyAction)
        finally: self.win.dragging_out = False

    @Slot(result=str)
    def clipboardFiles(self):
        md = QGuiApplication.clipboard().mimeData()
        if md is None or not md.hasUrls(): return '{}'
        paths = [native(u.toLocalFile()) for u in md.urls() if u.isLocalFile()]
        cut = False
        if md.hasFormat(DROPEFFECT_FMT):
            b = bytes(md.data(DROPEFFECT_FMT))
            if len(b) >= 4: cut = bool(struct.unpack('<I', b[:4])[0] & 2)
        return json.dumps({'paths': paths, 'cut': cut}, ensure_ascii=False)

    @Slot(str, bool)
    def setClipboardFiles(self, paths_json, cut):
        try: paths = json.loads(paths_json)
        except Exception: return
        md = QMimeData(); md.setUrls([QUrl.fromLocalFile(p) for p in paths])
        md.setData(DROPEFFECT_FMT, QByteArray(struct.pack('<I', 2 if cut else 5)))
        QGuiApplication.clipboard().setMimeData(md)

    @Slot(str)
    def copyImage(self, path):
        img = QImage(path)
        if not img.isNull(): QGuiApplication.clipboard().setImage(img)

    @Slot(result=str)
    def pickFolder(self):
        d = QFileDialog.getExistingDirectory(self.win, '選擇資料夾')
        return native(d) if d else ''

    @Slot()
    def restartShell(self):
        rt = sys.modules.get('_hz_rt')
        cmd = list(getattr(rt, 'ui_cmd', None) or [sys.executable])
        if self.win.srv is not None: self.win.srv.close()        # free the single-instance pipe first
        QProcess.startDetached(cmd[0], cmd[1:] + ['--after-restart'])
        self.win.quit_all(engine=False)

    @Slot()
    def relogin(self):
        """The page lost its login (sessions cleared, a new local key): open the start address again (fresh key)."""
        self.win.view.load(QUrl(self.win.local_url()))

    @Slot(str, str)
    def notify(self, title, msg):
        if self.win.tray: self.win.tray.showMessage(title, msg, QSystemTrayIcon.Information, 4000)


class DropFilter(QObject):
    """Drops from Windows Explorer (or our own drag-out) land here with real paths -> window.hzDrop(paths, x, y, mods)."""
    def __init__(self, win):
        super().__init__(win); self.win = win

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t in (QEvent.DragEnter, QEvent.DragMove):
            md = ev.mimeData()
            if md is not None and md.hasUrls() and any(u.isLocalFile() for u in md.urls()):
                ev.setDropAction(Qt.CopyAction); ev.accept(); return True
        elif t == QEvent.Drop:
            md = ev.mimeData()
            if md is not None and md.hasUrls():
                paths = [native(u.toLocalFile()) for u in md.urls() if u.isLocalFile()]
                if paths:
                    pos = ev.position() if hasattr(ev, 'position') else ev.posF()
                    w = obj if isinstance(obj, QWidget) else self.win.view
                    gp = w.mapTo(self.win.view, pos.toPoint())
                    m = ev.modifiers(); mods = ('ctrl' if m & Qt.ControlModifier else '') + ('shift' if m & Qt.ShiftModifier else '')
                    js = f'window.hzDrop && hzDrop({json.dumps(paths, ensure_ascii=False)}, {gp.x()}, {gp.y()}, {json.dumps(mods)})'
                    self.win.view.page().runJavaScript(js)
                    ev.setDropAction(Qt.CopyAction); ev.accept()
                    self.win.raise_(); self.win.activateWindow()
                    return True
        return False


class Page(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, msg, line, src):
        pass


class Window(QMainWindow):
    def __init__(self, rt, ping, local_url, note):
        super().__init__()
        self.rt = rt; self.ping = ping; self.local_url = local_url; self.note = note
        self.dragging_out = False; self.really_quit = False; self.tray = None; self.srv = None
        self.setWindowTitle('HotZone')
        icon = QIcon(os.path.join(APP_DIR, 'icon.svg'))
        ico = os.path.join(rt.root if getattr(rt, 'root', None) else os.path.dirname(APP_DIR), 'HotZoneFM.ico')
        if os.path.exists(ico): icon = QIcon(ico)
        self.setWindowIcon(icon); QApplication.instance().setWindowIcon(icon)
        self.qs = QSettings('HotZoneFM', 'shell')
        root = rt.root if getattr(rt, 'root', None) else os.path.dirname(APP_DIR)
        self.profile = QWebEngineProfile('hzfm', self)
        self.profile.setPersistentStoragePath(os.path.join(root, 'Data', 'webview'))
        self.profile.setCachePath(os.path.join(root, 'Data', 'webview_cache'))
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        self.profile.downloadRequested.connect(self.on_download)
        self.view = QWebEngineView(self)
        self.page = Page(self.profile, self.view)
        self.view.setPage(self.page)
        s = self.page.settings()
        s.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        try: s.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
        except Exception: pass
        try: s.setAttribute(QWebEngineSettings.PdfViewerEnabled, True)
        except Exception: pass
        self.view.setContextMenuPolicy(Qt.NoContextMenu)
        self.channel = QWebChannel(self.page)
        self.bridge = Bridge(self)
        self.channel.registerObject('hz', self.bridge)
        self.page.setWebChannel(self.channel)
        # Chromium does not let an http:// page load qrc:/ files: inject qwebchannel.js into the page ourselves
        f = QFile(':/qtwebchannel/qwebchannel.js')
        if f.open(QIODevice.ReadOnly):
            sc = QWebEngineScript(); sc.setName('qwebchannel'); sc.setSourceCode(bytes(f.readAll()).decode('utf-8'))
            sc.setInjectionPoint(QWebEngineScript.DocumentCreation); sc.setWorldId(QWebEngineScript.MainWorld); sc.setRunsOnSubFrames(False)
            self.page.scripts().insert(sc); f.close()
        self.drop_filter = DropFilter(self)
        self.view.setAcceptDrops(True)
        self.view.installEventFilter(self.drop_filter)
        self.page.loadFinished.connect(lambda ok: QTimer.singleShot(200, self.hook_drops))
        self.splash = QLabel('🔥  HotZone FM\n\n正在啟動背景引擎…', alignment=Qt.AlignCenter)
        self.splash.setStyleSheet('QLabel{background:#0e1116;color:#e8ecf2;font-size:18px;font-family:"Yu Gothic UI","Microsoft JhengHei";}')
        self.setCentralWidget(self.splash)
        self.setStyleSheet('QMainWindow{background:#0e1116;}')
        geo = self.qs.value('geometry')
        if geo: self.restoreGeometry(geo)
        else: self.resize(1500, 920)
        self.setup_tray()
        self.t0 = time.time()
        QTimer.singleShot(50, self.wait_engine)

    # ------------------------------------------------------------------ start
    def wait_engine(self):
        if self.ping(0.5):
            self.view.load(QUrl(self.local_url()))
            self.setCentralWidget(self.view); self.splash = None
            if self.note: QTimer.singleShot(2500, lambda: self.tray and self.tray.showMessage('HotZone', self.note, QSystemTrayIcon.Warning, 8000))
            return
        if time.time() - self.t0 > 60:
            QMessageBox.critical(self, 'HotZone', '背景引擎沒有回應。\n請查看程式資料夾的 LOG\\startup_log.txt 與 LOG\\engine.log。')
            return
        if self.splash: self.splash.setText(f'🔥  HotZone FM\n\n正在啟動背景引擎…（{int(time.time() - self.t0)} 秒）')
        QTimer.singleShot(400, self.wait_engine)

    def hook_drops(self):
        """Qt WebEngine delivers drag & drop to an inner widget: put the filter on every child."""
        for w in [self.view.focusProxy()] + list(self.view.findChildren(QWidget)):
            if w is not None and not w.property('hz_drop'):
                w.setAcceptDrops(True); w.installEventFilter(self.drop_filter); w.setProperty('hz_drop', True)
        self.dark_titlebar()

    def dark_titlebar(self):
        if not IS_WIN: return
        try:
            import ctypes
            v = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(int(self.winId())), 20, ctypes.byref(v), ctypes.sizeof(v))
        except Exception:
            pass

    # ------------------------------------------------------------------ downloads
    def on_download(self, item):
        name = item.downloadFileName() or 'download'
        path, _ = QFileDialog.getSaveFileName(self, '另存新檔', os.path.join(os.path.expanduser('~'), 'Downloads', name))
        if not path: item.cancel(); return
        item.setDownloadDirectory(os.path.dirname(path)); item.setDownloadFileName(os.path.basename(path))
        item.accept()
        item.isFinishedChanged.connect(lambda: self.tray and item.isFinished() and self.tray.showMessage('下載完成', path, QSystemTrayIcon.Information, 3000))

    # ------------------------------------------------------------------ tray / close
    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable(): return
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip('HotZone FM — 背景引擎執行中')
        m = QMenu()
        a = QAction('開啟視窗', self); a.triggered.connect(self.show_window); m.addAction(a)
        m.addSeparator()
        a = QAction('關閉視窗（背景繼續）', self); a.triggered.connect(lambda: self.quit_all(engine=False)); m.addAction(a)
        a = QAction('結束全部（含背景引擎）', self); a.triggered.connect(lambda: self.quit_all(engine=True)); m.addAction(a)
        self.tray.setContextMenu(m)
        self.tray.activated.connect(lambda r: self.show_window() if r in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
        self.tray.show()

    def show_window(self):
        self.showNormal() if self.isMinimized() else self.show()
        self.raise_(); self.activateWindow()

    def quit_all(self, engine=False):
        if engine:
            self.page.runJavaScript("HZ.post && HZ.post('/api/system/quit', {})")
            QTimer.singleShot(600, self._quit)
        else:
            self._quit()

    def _quit(self):
        self.really_quit = True
        self.qs.setValue('geometry', self.saveGeometry())
        if self.tray: self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, ev):
        self.qs.setValue('geometry', self.saveGeometry())
        if self.really_quit or not self.tray:
            ev.accept(); return
        ev.ignore(); self.hide()
        if not self.qs.value('tray_told'):
            self.qs.setValue('tray_told', '1')
            self.tray.showMessage('HotZone', '視窗已縮到右下角。搬檔、熱區搬移和遠端連線在背景繼續進行。\n右鍵圖示可以完全結束。', QSystemTrayIcon.Information, 6000)


def run(rt, ping, local_url, note=''):
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('HotZoneFM.Window')
        except Exception:
            pass
    os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-features=TranslateUI')
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('HotZone FM'); app.setQuitOnLastWindowClosed(False)
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    if '--after-restart' in sys.argv:                                      # "restart window": let the old one go first
        for _ in range(40):
            probe = QLocalSocket(); probe.connectToServer('HotZoneFM_Window')
            if not probe.waitForConnected(150): break
            probe.abort(); time.sleep(0.15)
    else:
        sock = QLocalSocket(); sock.connectToServer('HotZoneFM_Window')
        if sock.waitForConnected(500):                                     # already open: bring it to the front
            sock.write(b'show'); sock.flush(); sock.waitForBytesWritten(500); return 0
    QLocalServer.removeServer('HotZoneFM_Window')
    srv = QLocalServer(app); srv.listen('HotZoneFM_Window')
    win = Window(rt, ping, local_url, note); win.srv = srv
    srv.newConnection.connect(lambda: (srv.nextPendingConnection(), win.show_window()))
    win.show()
    return app.exec()

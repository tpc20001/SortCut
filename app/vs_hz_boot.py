"""SortCut 裡的 HotZone（V0.1.55）：用電腦上的 Python 3.11 另外跑 HotZone 的背景引擎／視窗。

  pythonw vs_hz_boot.py --root "D:\\HotZoneFM" --engine [--ff "D:\\VideoSift"]     背景引擎（SortCut 用系統管理員身分啟動）
  pythonw vs_hz_boot.py --root "D:\\HotZoneFM" --shell                             HotZone 視窗（要裝 PySide6，非系統管理員）

--root：HotZone 原本的資料夾（Data\\ 設定、佇列、索引、保管區都照舊讀這裡）。程式碼用 SortCut 的 app\\hz_*.py。
這個檔不會被 SortCut 主程式 import（裡面用的套件 SortCut 的 EXE 沒有）。
"""
import os
import sys
import time
import traceback


def _arg(name, default=''):
    a = sys.argv
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else default


def _log(root, msg):
    try:
        d = os.path.join(root, 'LOG'); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'videosift_boot_log.txt'), 'a', encoding='utf-8') as fh:
            fh.write(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}\n')
    except Exception:
        pass


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(_arg('--root') or os.path.join(os.path.dirname(here), 'HotZone'))
    os.makedirs(root, exist_ok=True)
    os.environ['HZFM_ROOT'] = root                                            # hz_common：資料、LOG、UPDATE 都在 HotZone 原本的資料夾
    ff = _arg('--ff')
    if ff and os.path.isdir(ff): os.environ['PATH'] = ff + os.pathsep + os.environ.get('PATH', '')      # 用 SortCut 的 ffmpeg
    if here not in sys.path: sys.path.insert(0, here)
    py = sys.executable
    if os.name == 'nt' and py.lower().endswith('python.exe') and os.path.exists(py[:-10] + 'pythonw.exe'): py = py[:-10] + 'pythonw.exe'
    me = os.path.abspath(__file__)
    try:
        import hz_engine
        rt = hz_engine.runtime(); rt.mode = 'videosift'; rt.launcher_version = 1; rt.root = root
        rt.engine_cmd = [py, me, '--root', root, '--engine'] + (['--ff', ff] if ff else [])

        def restart():
            import subprocess
            flags = 0x08000000 if os.name == 'nt' else 0
            subprocess.Popen(rt.engine_cmd + ['--wait-old'], creationflags=flags, close_fds=True); rt.quit_ev.set()
        rt.restart = restart
        if '--embed' in sys.argv:
            return run_embed(rt, root, _arg('--embed'))
        if '--shell' in sys.argv:
            import hz_shell
            from hz_common import Settings, LOCAL_TOKEN_FILE
            port = int(Settings().get('web.port') or 8765)

            def ping(timeout=0.5):
                try:
                    import urllib.request, json
                    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(f'http://127.0.0.1:{port}/api/ping', timeout=timeout) as r:
                        return json.loads(r.read().decode()).get('app') == 'HotZone FM'
                except Exception:
                    return False

            def local_url():
                try: k = open(LOCAL_TOKEN_FILE, encoding='utf-8').read().strip()
                except Exception: k = ''
                return f'http://127.0.0.1:{port}/?k={k}'
            _log(root, f'HotZone 視窗啟動（SortCut，Python {sys.version.split()[0]}）')
            return hz_shell.run(rt, ping, local_url, '')
        if '--wait-old' in sys.argv: time.sleep(3)
        _log(root, f'HotZone 背景引擎啟動（SortCut，Python {sys.version.split()[0]}，{"系統管理員" if _is_admin() else "一般權限"}，程式 {here}）')
        try:                                                                 # 舊的 HotZoneFM.exe 設過「開機自動啟動」：改成啟動 SortCut 裡的引擎
            if os.name == 'nt' and _is_admin():
                import hz_fileops as F
                if F.autostart_state().get('on'): F.autostart_set(True); _log(root, '開機自動啟動的排程改成 SortCut 裡的 HotZone 引擎')
        except Exception as e:
            _log(root, f'更新開機自動啟動失敗：{e}')
        return hz_engine.run_engine()
    except SystemExit:
        raise
    except Exception:
        _log(root, '啟動失敗：\n' + traceback.format_exc())
        return 1


EMBED_JS = r"""
(function(){
  window.__vsEmbed = true;
  var st = document.createElement('style'); st.id = 'vsEmbedCss';
  st.textContent = '#side{display:none!important}#menuBtn{display:none!important}#app{grid-template-columns:1fr!important}#main{margin-left:0!important;width:100%!important}';
  (document.head || document.documentElement).appendChild(st);
})();
"""


def _ports_and_url(root):
    from hz_common import Settings, LOCAL_TOKEN_FILE
    port = int(Settings().get('web.port') or 8765)

    def ping(timeout=0.5):
        try:
            import urllib.request, json
            for p in [port] + [x for x in range(8765, 8771) if x != port]:
                try:
                    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(f'http://127.0.0.1:{p}/api/ping', timeout=timeout) as r:
                        if json.loads(r.read().decode()).get('app') == 'HotZone FM': ping.port = p; return True
                except Exception: continue
        except Exception: pass
        return False
    ping.port = port

    def local_url():
        try: k = open(LOCAL_TOKEN_FILE, encoding='utf-8').read().strip()
        except Exception: k = ''
        return f'http://127.0.0.1:{ping.port}/?k={k}'
    return ping, local_url


def run_embed(rt, root, server_name):
    """SortCut 裡面的 HotZone 畫面：沒有邊框的 HotZone 視窗，把視窗代號交給 SortCut，由 SortCut 嵌進自己的視窗裡；
    SortCut 左邊選單點哪一頁，就叫 HotZone 切到那一頁（HotZone 自己的左側選單藏起來）."""
    import json
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication
    from PySide6.QtNetwork import QLocalSocket
    from PySide6.QtWebEngineCore import QWebEngineScript
    import hz_shell
    ping, local_url = _ports_and_url(root)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('HotZone (VideoSift)'); app.setQuitOnLastWindowClosed(False)

    class EmbedWin(hz_shell.Window):
        def setup_tray(self): self.tray = None
        def closeEvent(self, ev):
            ev.accept(); QApplication.instance().quit()
        def raise_(self): pass                                               # 嵌在 SortCut 裡：不要自己跳到最上面
        def activateWindow(self): pass

    py = sys.executable
    rt.ui_cmd = [py, os.path.abspath(__file__), '--root', root, '--embed', server_name]   # HotZone「重新開視窗」用
    win = EmbedWin(rt, ping, local_url, '')
    win.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)                       # Tool：嵌進去之前也不會在工作列閃一下
    win.setWindowState(Qt.WindowNoState)                                     # 上次存的「最大化」不要帶進來
    sc = QWebEngineScript(); sc.setName('vs_embed'); sc.setSourceCode(EMBED_JS)
    sc.setInjectionPoint(QWebEngineScript.DocumentReady); sc.setWorldId(QWebEngineScript.MainWorld); sc.setRunsOnSubFrames(False)
    win.page.scripts().insert(sc)
    win.move(-32000, -32000); win.resize(1200, 800); win.show()
    st = {'want': '', 'tries': 0, 'buf': b'', 'seq': 0}

    def try_go(seq=None):
        seq = st['seq'] if seq is None else seq
        pid = st['want']
        if not pid or seq != st['seq']: return
        js = 'window.HZ&&HZ.pages&&HZ.pages[%s]&&HZ.cur?(HZ.go(%s),HZ.cur):""' % (json.dumps(pid), json.dumps(pid))

        def got(v):
            if seq != st['seq']: return                                       # 已經又切到別頁了
            if v == pid: st['want'] = ''; return
            st['tries'] += 1
            if st['tries'] < 120: QTimer.singleShot(300, lambda: try_go(seq))
        try: win.page.runJavaScript(js, 0, got)
        except Exception: QTimer.singleShot(500, try_go)

    sock = QLocalSocket()

    def on_read():
        st['buf'] += bytes(sock.readAll())
        while b'\n' in st['buf']:
            line, st['buf'] = st['buf'].split(b'\n', 1); cmd = line.decode('utf-8', 'replace').strip()
            if cmd.startswith('go '): st['want'] = cmd[3:].strip(); st['tries'] = 0; st['seq'] += 1; try_go()
            elif cmd == 'reload': win.view.load(win.page.url())
            elif cmd == 'quit': app.quit()
    sock.readyRead.connect(on_read); sock.disconnected.connect(app.quit)
    sock.connectToServer(server_name)
    if not sock.waitForConnected(5000):
        _log(root, f'嵌入：連不到 SortCut（{server_name}）'); return 1
    sock.write(f'hwnd {int(win.winId())}\n'.encode()); sock.flush()
    win.page.loadFinished.connect(lambda ok: QTimer.singleShot(1200, lambda: (st.update(tries=0), try_go())))
    _log(root, f'HotZone 畫面嵌進 SortCut（{server_name}）')
    return app.exec()


def _is_admin():
    try:
        if os.name != 'nt': return os.geteuid() == 0
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


if __name__ == '__main__':
    sys.exit(main() or 0)

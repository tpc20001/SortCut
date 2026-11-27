"""雲端打包前的電腦版畫面測試（GitHub Actions 的 Windows 上跑，QT_QPA_PLATFORM=offscreen）.

真的把 SortCut 主視窗開起來：每一頁都切一次、打開讓路視窗、轉檔工作區各分頁，跑幾秒讓計時器動一動。
任何一個地方丟出錯誤（包含按鈕／計時器裡的錯誤）→ 測試失敗 → 這版不會發出去（不會把壞掉的版本推給使用者）。
"""
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['VIDEOSIFT_SELFTEST'] = '1'
KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / 'app'))
ERR = []
_old = sys.excepthook
sys.excepthook = lambda t, v, tb: ERR.append(''.join(traceback.format_exception(t, v, tb)))


def pump(sec):
    from PySide6.QtWidgets import QApplication
    t = time.time() + sec
    while time.time() < t: QApplication.processEvents(); time.sleep(0.02)


def no_modal():
    """雲端沒有人按：所有會「等人按」的視窗直接回預設值，不然測試會卡住到逾時."""
    from PySide6.QtWidgets import QMessageBox, QDialog, QMenu, QFileDialog, QInputDialog
    for nm in ('question', 'information', 'warning', 'critical', 'about'):
        setattr(QMessageBox, nm, staticmethod(lambda *a, **k: QMessageBox.No))
    QMessageBox.exec = lambda self, *a, **k: 0
    QDialog.exec = lambda self, *a, **k: (self.show(), 0)[1]
    QMenu.exec = lambda self, *a, **k: None
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: '')
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([], ''))
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('', False))
    QInputDialog.getInt = staticmethod(lambda *a, **k: (0, False))
    QInputDialog.getItem = staticmethod(lambda *a, **k: ('', False))


def shot(w, name):
    """V0.6.44 每一頁存一張圖（雲端 Actions 的 ui-shots 可以下載來看畫面）."""
    try:
        d = KIT / 'ui_shots'; d.mkdir(exist_ok=True); w.grab().save(str(d / f'{name}.png'))
    except Exception as ex: print('  (截圖失敗)', name, ex, flush=True)


def step(name, fn):
    print('  ▶', name, flush=True)
    try: fn(); pump(0.3); print('  ✔', name, flush=True)
    except Exception: ERR.append(f'{name}\n{traceback.format_exc()}'); print('  ✖', name, flush=True)


def main():
    import faulthandler
    faulthandler.dump_traceback_later(300, exit=True)                           # 卡住 5 分鐘：印出卡在哪一行再結束（看 LOG 就知道）
    if os.name == 'nt' and not os.environ.get('QT_QPA_FONTDIR'): os.environ['QT_QPA_FONTDIR'] = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')   # 截圖要有中文字
    from PySide6.QtWidgets import QApplication
    no_modal()
    import app as A
    import core
    qa = QApplication.instance() or QApplication(sys.argv)
    root = Path(tempfile.mkdtemp()); (root / 'Data').mkdir(); (root / 'LOG').mkdir(); (root / 'UPDATE').mkdir()
    A.ROOT = root
    A.BUS = A.Bus(); A.LOADER = A.ImgLoader(); A.ENG = core.Engine(root, version=A.APP_VERSION); qa._vs_eng = A.ENG
    try:                                                                        # V0.6.44 放一些假的影片紀錄，截圖才看得到畫面長怎樣
        import random, time as _t
        rnd = random.Random(1); rows = []
        for i in range(300):
            f = f'H:\\A0{i % 5}\\sub{i % 7}'
            rows.append((f + f'\\v{i}.mp4', 'H:\\', f, f'v{i}.mp4', '.mp4', rnd.randint(10 ** 8, 5 * 10 ** 9), _t.time() - rnd.randint(0, 30000000),
                         rnd.choice(['h264', 'hevc']), rnd.choice(['', '', 'S', 'A', 'E', 'F']), rnd.randint(30, 4000)))
        A.ENG.db.con.executemany("INSERT INTO files(path,root,folder,name,ext,size,mtime,vcodec,grade,probed,has_v,dur) VALUES(?,?,?,?,?,?,?,?,?,1,1,?)", rows); A.ENG.db.con.commit()
    except Exception as ex: print('  (假資料失敗)', ex, flush=True)
    import cProfile, pstats, io, time as _tt
    pr = cProfile.Profile(); t0_ = _tt.time(); pr.enable()
    w = A.Main()
    pr.disable(); print(f'  ⏱ 開主視窗 {(_tt.time() - t0_) * 1000:.0f} ms', flush=True)
    try:
        so = io.StringIO(); pstats.Stats(pr, stream=so).sort_stats('cumulative').print_stats(25); print('PROFILE-BEGIN\n' + so.getvalue()[-6000:] + '\nPROFILE-END', flush=True)
    except Exception: pass
    w.resize(1600, 1000); w.show(); qa._vs_main = w; pump(2.0)
    w.outer.setCurrentIndex(1)
    for pg in list(A.NavList.NAMES):
        step(f'頁面 {pg} {A.NavList.NAMES[pg][1]}', lambda pg=pg: (w._page(pg), pump(0.6), shot(w, f'p{pg:02d}')))
    step('封存頁（Ctrl+Shift+R）', w.open_archive)
    def yd():
        d = A.YieldDlg(w); d.show(); pump(1.0); d.load(); pump(0.5); shot(d, 'yield'); d.close()
    step('讓路視窗', yd)
    if hasattr(w, 'conv') and hasattr(w.conv, 'tabs'):
        step('切到轉檔', lambda: (w.nav.setCurrentRow(1), pump(0.5)))
        for i in range(w.conv.tabs.count()): step(f'轉檔分頁 {i}', lambda i=i: (w.conv.tabs.setCurrentIndex(i), pump(0.4), shot(w, f'conv{i}')))
    for nm in ('explore',):
        if hasattr(w, nm): step(f'{nm}', lambda nm=nm: getattr(w, nm).refresh() if hasattr(getattr(w, nm), 'refresh') else None)
    pump(3.0)
    try:
        w.quitting = True; w.close(); pump(0.5); A.ENG.shutdown() if hasattr(A.ENG, 'shutdown') else None
    except Exception: pass
    res = KIT / 'smoke_result.txt'                                              # Windows 上結束碼有時被別的執行緒蓋掉：結果另外寫檔，雲端看這個檔
    res.write_text('FAIL' if ERR else 'UI SMOKE OK', encoding='utf-8')
    if ERR:
        print('\n========== 畫面測試失敗 ==========\n' + '\n----------\n'.join(ERR[:20]), flush=True); os._exit(1)
    print('UI SMOKE OK', flush=True); os._exit(0)


if __name__ == '__main__':
    main()

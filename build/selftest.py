"""VideoSift self-test. Usage: python selftest.py <app_dir> <ffmpeg_dir>
Runs in a throw-away temp folder with generated test videos; never touches real data.
Opens the real window (hidden, offscreen), scans, makes 2-second previews, shows the grid, cuts, converts (GPU if possible), opens every page."""
import sys, os, shutil, tempfile, time, importlib, py_compile, pathlib, subprocess, traceback

SRC = pathlib.Path(sys.argv[1]).resolve(); FFD = pathlib.Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
os.environ['QT_QPA_PLATFORM'] = 'offscreen'; os.environ['VIDEOSIFT_SELFTEST'] = '1'
RES = []


def check(name, cond, info='', warn=False):
    tag = 'PASS' if cond else ('WARN' if warn else 'FAIL')
    print(f'  [{tag}] {name}' + (f'  ({info})' if info else ''), flush=True); RES.append((tag, name))
    return cond


for f in ('app.py', 'core.py', 'vs_disk.py', 'vs_web.py', 'vs_webpage.py', 'vs_face.py', 'vs_face_worker.py'):
    try: py_compile.compile(str(SRC / f), doraise=True); check(f'compile {f}', True)
    except Exception as ex: check(f'compile {f}', False, str(ex)); sys.exit(1)

tmp = pathlib.Path(tempfile.mkdtemp(prefix='vs_selftest_')).resolve()
try:
    shutil.copytree(SRC, tmp / 'app', ignore=shutil.ignore_patterns('__pycache__'))
    for n in ('ffmpeg.exe', 'ffprobe.exe', 'ffmpeg', 'ffprobe'):
        if FFD and (FFD / n).exists(): shutil.copy2(FFD / n, tmp / n)
    ff = str(next((p for p in (tmp / 'ffmpeg.exe', tmp / 'ffmpeg') if p.exists()), '') or shutil.which('ffmpeg') or '')
    check('ffmpeg found', bool(ff), ff)
    lib = tmp / 'videos'; (lib / 'A' / 'sub').mkdir(parents=True)
    NOWIN = 0x08000000 if os.name == 'nt' else 0
    def mk(args, out):
        r = subprocess.run([ff, '-hide_banner', '-loglevel', 'error', '-y'] + args + [str(out)], capture_output=True, creationflags=NOWIN)
        return r.returncode == 0
    ok = all([mk(['-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=30', '-f', 'lavfi', '-i', 'sine=f=440', '-t', '70', '-c:v', 'libx264', '-g', '60', '-c:a', 'aac', '-shortest'], lib / 'A' / 'clip one.mp4'),
              mk(['-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=25', '-f', 'lavfi', '-i', 'sine=f=300', '-t', '24', '-c:v', 'mpeg4', '-c:a', 'libmp3lame', '-shortest'], lib / 'A' / 'sub' / '影片二.avi'),
              mk(['-f', 'lavfi', '-i', 'smptebars=size=720x480:rate=30', '-f', 'lavfi', '-i', 'sine=f=500', '-t', '12', '-c:v', 'mpeg2video', '-flags', '+ilme+ildct', '-top', '1', '-c:a', 'mp2', '-shortest'], lib / 'A' / 'three.ts'),
              mk(['-f', 'lavfi', '-i', 'testsrc2=size=480x270:rate=30', '-t', '10', '-c:v', 'flv1'], lib / 'four.flv')])
    (lib / 'A' / 'broken.mkv').write_bytes(b'not a video')
    check('test videos made', ok)

    sys.path.insert(0, str(tmp / 'app'))
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    qa = QApplication(sys.argv)
    core = importlib.import_module('core'); app = importlib.import_module('app')
    app.ROOT = tmp

    def pump(sec, cond=None):
        t = time.time()
        while time.time() - t < sec:
            qa.processEvents(); time.sleep(0.02)
            if cond is not None and cond(): return True
        return cond() if cond is not None else True

    app.BUS = app.Bus(); app.LOADER = app.ImgLoader(); E = app.ENG = core.Engine(tmp)
    check('engine starts', E.ff != '' and E.ffprobe != '', f'{E.ff} | {E.ffprobe}')
    E.cfg.set('roots', [str(lib)]); E.cfg.set('th_prio', 'normal'); E.cfg.set('cut_dir', str(tmp / 'out_cut')); E.cfg.set('fav_dir', str(tmp / 'out_fav'))
    check('scan', E.scan() and pump(30, lambda: not E.scan_st['running']) and E.scan_st['n'] == 5, f"{E.scan_st['n']} files")
    def left():
        E.info_c['t'] = 0; I = E.info(); return I['probe_left'] == 0 and I['th_left'] == 0
    check('probe + 2-second previews', pump(240, left), str(E.info()))
    R = {r['name']: dict(r) for r in E.db.q('SELECT * FROM files')}
    one = R.get('clip one.mp4') or {}
    check('preview count (70 s → 35)', one.get('th_state') == 2 and one.get('th_n') == 35, f"state {one.get('th_state')} n {one.get('th_n')} err {one.get('th_err')}")
    check('broken file marked, not stuck', (R.get('broken.mkv') or {}).get('th_state') == 3)
    check('interlaced detected', (R.get('three.ts') or {}).get('field') in ('tt', 'bb', 'tb', 'bt'), str((R.get('three.ts') or {}).get('field')))

    w = app.Main(); w.show(); pump(1.5)
    check('main window', w.isVisible())
    B = w.browse; pump(3, lambda: B.tree.topLevelItemCount() >= 2)
    check('folder tree', B.tree.topLevelItemCount() >= 2, f'{B.tree.topLevelItemCount()} top items')
    B.tree.setCurrentItem(B.tree.topLevelItem(1)); pump(3, lambda: B.lst.count() >= 5)
    check('file list', B.lst.count() == 5, f'{B.lst.count()} rows')
    row = next((i for i in range(B.lst.count()) if B.lst.item(i).data(Qt.UserRole) == one.get('id')), -1)
    B.lst.setCurrentRow(row); pump(5, lambda: B.grid.n > 0 and len(B.grid.cache) > 0)
    check('thumbnail grid shows previews', B.grid.n == 35 and len(B.grid.cache) > 0 and B.grid.fw > 0, f'n={B.grid.n} sheets={len(B.grid.sheets)} fw={B.grid.fw}')
    g = B.grid; g.sel |= g._range_bs(5, 10); g.sel |= g._range_bs(20, 25)     # V0.1.08：拖曳圈選兩段
    segs = g.seg_times(); check('select 2 segments', len(segs) == 2 and abs(segs[0][0] - 10) < 0.01 and abs(segs[0][1] - 22) < 0.01, str(segs))
    img = g.grab(); check('grid paints', not img.isNull())
    r = E.cut_add(one['id'], segs, merge=False); pump(60, lambda: not E.cut_q and E.cut_cur is None)
    outs = sorted(E.arch_dir('cut', one['path'], E.cfg.get('cut_dir')).glob('*'))
    check('cut 2 files (no re-encode)', len(outs) == 2, ', '.join(o.name for o in outs))
    try:
        p = app.Player(w, one['path'], 12, 'test'); p.show(); pump(4); ok = True; p.close(); pump(0.5)
    except Exception as ex: ok = False; print(traceback.format_exc())
    check('player opens', ok)
    E.gpu_check(True); print('    GPU:', E.gpu_st.get('diag', '').replace('\n', '\n         '))
    check('graphics card NVENC (H.265)', E.gpu_st.get('ok'), 'CPU will be used instead' if not E.gpu_st.get('ok') else E.gpu_st.get('ff'), warn=True)
    w.nav.setCurrentRow(1); pump(3, lambda: w.conv.tb.rowCount() >= 4)
    check('convert page lists non-MP4', w.conv.tb.rowCount() == 4, f'{w.conv.tb.rowCount()} rows')
    ids = [R['影片二.avi']['id'], R['three.ts']['id'], R['four.flv']['id']]
    E.cfg.set('cv_n', 3); E.conv_add(ids)
    pump(300, lambda: E.db.one('SELECT COUNT(*) FROM files WHERE cv_state IN (1,2)')[0] == 0)
    C = {r['name']: dict(r) for r in E.db.q('SELECT name,cv_state,cv_out,cv_err FROM files WHERE cv_state>0')}
    good = [n for n, x in C.items() if x['cv_state'] == 3 and pathlib.Path(x['cv_out']).exists()]
    check('convert to MP4 H.265 (3 files, length checked)', len(good) == 3, '; '.join(f"{n}: {x['cv_state']} {x['cv_err'][:120]}" for n, x in C.items()))
    if good:
        pr = core.probe(E.ffprobe, C[good[0]]['cv_out']); check('output is HEVC', pr.get('vcodec') == 'hevc', str(pr.get('vcodec')))
    for i, nm in enumerate(('後台', '設定', 'LOG', '版本與更新', '操作紀錄', '實驗工作區', '使用說明')):
        w.nav.setCurrentRow(2 + i); pump(2.5); check(f'page {nm}', w.stack.currentIndex() == 2 + i)
    w.b_perf.setChecked(True); pump(2.5); check('performance float', w.pf is not None and w.pf.isVisible()); w.b_perf.setChecked(False)
    r = E.file_op(one['id'], 'fav'); pump(30, lambda: not E.op_q and E.op_cur is None)
    check('favorite copy', (E.arch_dir('fav', one['path'], E.cfg.get('fav_dir')) / 'clip one.mp4').exists())
    # V0.1.09 以後：歸檔、操作紀錄、封面、備份、搜尋
    try:
        E.set_flags([one['id']], grade='A'); E.cfg.set('arch_names', {'S': 'S_無條件保存', 'A': 'A_保存', 'E': 'E_觀察', 'F': 'F_刪除'})
        n_ = E.archive_many([one['id']], 'grade:A'); pump(30, lambda: not E.op_q and E.op_cur is None)
        check('one-click archive (grade A)', n_ == 1 and (E.file(one['id']) or {}).get('arch') == 'A_保存')
        ops = E.oplog_query(); check('operation log (30 days)', any(o['kind'] == 'arch' for o in ops), f'{len(ops)} records')
        oid = next((o['id'] for o in ops if o['kind'] == 'arch'), None); u = E.oplog_undo(oid) if oid else {'ok': False}
        check('undo archive (move back)', u.get('ok'), u.get('message', ''))
        try:                                                                    # 自我測試不要在 C:\VideoSIFT 留下空資料夾
            d_ = pathlib.Path(next(o['dst'] for o in ops if o['kind'] == 'arch')).parent
            os.removedirs(str(d_))
        except Exception: pass
        check('database backup', bool(E.db_backup('selftest')))
        check('cover page', w.outer.count() == 2)
    except Exception as ex: print(traceback.format_exc()); check('V0.1.09+ features', False, str(ex))
    fz = (tmp / 'LOG' / 'ui_freeze_log.txt'); check('no UI freeze over 2 s', not fz.exists(), fz.read_text(encoding='utf-8')[-300:] if fz.exists() else '', warn=True)
    w.quitting = True; w.close(); pump(1)
except Exception:
    print(traceback.format_exc()); check('selftest ran to the end', False)
finally:
    try: app.ENG.shutdown()
    except Exception: pass
    time.sleep(1); shutil.rmtree(tmp, ignore_errors=True)

fails = [n for t, n in RES if t == 'FAIL']
print('')
print(f'SELFTEST: {sum(1 for t, _ in RES if t == "PASS")} passed, {len(fails)} failed, {sum(1 for t, _ in RES if t == "WARN")} warnings')
for n in fails: print('  FAIL:', n)
sys.stdout.flush(); os._exit(1 if fails else 0)

"""SortCut 👤 人物（人臉分類）— 主程式這邊（V0.1.51）。

真正找臉、算特徵、分群的是 vs_face_worker.py（用電腦上另外裝的 Python 跑，當掉也不影響 SortCut）。
這裡只負責：找 Python、檢查／安裝套件、開始／停止背景程式、夜間時段自動跑、讀結果（人、影片、時間點）、取名／合併／隱藏／拿掉臉、
把「誰出現在哪部」同步到主資料庫（檔案總管可以依人物篩選、自動歸類）。不需要 numpy（啟動器 EXE 裡沒有）。
"""
import os, sys, re, json, time, sqlite3, threading, subprocess, shutil
from pathlib import Path

NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
BELOW = 0x00004000 if os.name == 'nt' else 0
CHECK = r'''
import json, os, sys
r = {"py": sys.version.split()[0], "exe": sys.executable}
try:
    import numpy; r["numpy"] = numpy.__version__
except Exception as ex: r["numpy_err"] = str(ex)
try:
    import cv2; r["cv2"] = cv2.__version__
except Exception as ex: r["cv2_err"] = str(ex)
try:
    import onnxruntime as ort; r["ort"] = ort.__version__; r["providers"] = ort.get_available_providers()
except Exception as ex: r["ort_err"] = str(ex)
try:
    import insightface; r["insightface"] = getattr(insightface, "__version__", "?")
except Exception: pass
base = os.path.join(os.path.expanduser("~"), ".insightface", "models"); r["models"] = {}
if os.path.isdir(base):
    for d in sorted(os.listdir(base)):
        p = os.path.join(base, d)
        if os.path.isdir(p): r["models"][d] = sorted(f for f in os.listdir(p) if f.endswith(".onnx"))
print("VSCHECK" + json.dumps(r))
'''
DEFAULTS = {'ratio': 0.10, 'src': 'thumbs', 'thr': 0.45, 'min_faces': 3, 'gpu': True, 'det': 640, 'minpx': 0, 'model': 'buffalo_l',
            'night': False, 'night_from': '01:00', 'night_to': '07:00', 'python': '', 'auto_min': 2}
THR = {'strict': 0.52, 'normal': 0.45, 'loose': 0.38}


class FaceManager:
    def __init__(self, eng, adopt=None):
        self.E = eng; self.data = Path(eng.data); self.db_path = self.data / 'faces.sqlite3'
        self.proc = getattr(adopt, 'proc', None); self.started_by = getattr(adopt, 'started_by', '')
        self.env = getattr(adopt, 'env', None) or {}; self.installing = getattr(adopt, 'installing', None)
        self.lock = threading.Lock(); self._last_sync = 0; self._sync_busy = False; self._last_done = -1; self._was_running = False

    # ---- 設定
    def cfg(self):
        c = dict(DEFAULTS); c.update(self.E.cfg.get('faces') or {}); return c

    def set_cfg(self, **kw):
        c = dict(self.E.cfg.get('faces') or {}); c.update(kw); self.E.cfg.set('faces', c); self.E.log.w('👤 人物設定：' + '、'.join(f'{k}={v!r}' for k, v in kw.items()))

    # ---- 資料庫（worker 建的；這裡只讀和小改）
    def con(self):
        c = sqlite3.connect(str(self.db_path), timeout=10, isolation_level=None)
        c.execute('PRAGMA busy_timeout=10000')
        c.executescript("""CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS done(file_id INTEGER PRIMARY KEY, th_t REAL, ratio REAL, src TEXT, n_tiles INTEGER, n_faces INTEGER, t REAL, err TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS face(id INTEGER PRIMARY KEY AUTOINCREMENT, file_id INTEGER, t REAL, k INTEGER, x REAL, y REAL, w REAL, h REAL, score REAL, px REAL,
  emb BLOB, person INTEGER DEFAULT 0, ex INTEGER DEFAULT 0, src TEXT DEFAULT 'thumbs');
CREATE INDEX IF NOT EXISTS ix_face_file ON face(file_id);
CREATE INDEX IF NOT EXISTS ix_face_person ON face(person, file_id);
CREATE TABLE IF NOT EXISTS person(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT DEFAULT '', n_faces INTEGER DEFAULT 0, n_files INTEGER DEFAULT 0, cover INTEGER DEFAULT 0,
  centroid BLOB, hidden INTEGER DEFAULT 0, auto_cat INTEGER DEFAULT 0, t REAL DEFAULT 0);""")
        return c

    def meta(self):
        try:
            c = self.con()
            try: return {k: json.loads(v) for k, v in c.execute('SELECT k, v FROM meta')}
            finally: c.close()
        except Exception: return {}

    def status(self):
        m = self.meta(); run = self.running()
        try:
            c = self.con()
            try:
                n_faces = c.execute('SELECT COUNT(*) FROM face WHERE ex=0').fetchone()[0]
                n_people = c.execute('SELECT COUNT(*) FROM person WHERE n_faces>0 AND hidden=0').fetchone()[0]
                n_named = c.execute("SELECT COUNT(*) FROM person WHERE length(name)>0").fetchone()[0]
                n_done = c.execute('SELECT COUNT(*) FROM done').fetchone()[0]
            finally: c.close()
        except Exception: n_faces = n_people = n_named = n_done = 0
        try: total = (self.E.db.one('SELECT COUNT(*) FROM files WHERE missing=0 AND th_state=2 AND th_n>0') or [0])[0]
        except Exception: total = m.get('total') or 0
        return {'running': run, 'state': m.get('state', 'idle') if run or m.get('state') in ('error',) else ('idle' if m.get('state') != 'error' else 'error'),
                'msg': m.get('msg', ''), 'err': m.get('err', ''), 'provider': m.get('provider', ''), 'kind': m.get('kind', ''), 'done': n_done, 'total': total,
                'eta': m.get('eta') if run else None, 'speed': m.get('speed'), 'faces': n_faces, 'people': n_people, 'named': n_named, 'cur': m.get('cur', '') if run else '',
                'by': self.started_by if run else '', 'env': self.env, 'installing': bool(self.installing and self.installing.poll() is None), 'cfg': self.cfg()}

    # ---- 找 Python／檢查環境／安裝
    def python_candidates(self):
        c = self.cfg(); L = []
        if c.get('python'): L.append([c['python']])
        if os.name == 'nt':
            if shutil.which('py'): L.append(['py', '-3.11']); L.append(['py', '-3'])
            la = os.environ.get('LOCALAPPDATA', '')
            for v in ('311', '312', '310'):
                p = os.path.join(la, 'Programs', 'Python', f'Python{v}', 'python.exe')
                if os.path.isfile(p): L.append([p])
            for nm in ('python', 'python3'):
                p = shutil.which(nm)
                if p and 'WindowsApps' not in p: L.append([p])
        else:
            for nm in ('python3.11', 'python3', 'python'):
                p = shutil.which(nm)
                if p: L.append([p])
        out = []
        for x in L:
            if x not in out: out.append(x)
        return out

    def check_env(self):
        """每個找得到的 Python 都試：有沒有 onnxruntime／numpy／cv2、能不能用顯示卡、模型在不在。挑最好的那個記起來."""
        best = None; tried = []
        for cmd in self.python_candidates():
            try:
                p = subprocess.run(cmd + ['-c', CHECK], capture_output=True, timeout=90, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
                out = p.stdout.decode('utf-8', 'replace'); i = out.find('VSCHECK')
                if i < 0: tried.append({'cmd': cmd, 'err': (p.stderr.decode('utf-8', 'replace') or out)[-300:]}); continue
                r = json.loads(out[i + 7:].strip().splitlines()[0]); r['cmd'] = cmd
                r['ok'] = bool(r.get('ort') and r.get('numpy') and r.get('cv2'))
                r['gpu'] = any(x in (r.get('providers') or []) for x in ('CUDAExecutionProvider', 'DmlExecutionProvider'))
                r['has_models'] = any(any(f.startswith(('det_', 'scrfd')) for f in v) for v in (r.get('models') or {}).values())
                tried.append(r); score = (r['ok'], r['has_models'] or bool(r.get('insightface')), r['gpu'], r.get('py', '').startswith('3.11'))
                if best is None or score > best[0]: best = (score, r)
            except Exception as ex: tried.append({'cmd': cmd, 'err': f'{type(ex).__name__}: {ex}'})
        env = dict(best[1]) if best else {'ok': False}
        env['tried'] = tried; env['t'] = time.time(); self.env = env
        self.E.log.w('👤 人物：檢查環境 → ' + (f'{" ".join(env["cmd"])}（Python {env.get("py")}，onnxruntime {env.get("ort", "沒有")}，{env.get("providers")}，'
                                              f'insightface {env.get("insightface", "沒有")}，模型 {list((env.get("models") or {}).keys())}）' if best else '找不到可以用的 Python')
                     + f'；試過 {len(tried)} 個')
        return env

    def install(self, flavor='cuda'):
        """在背景幫你 pip 安裝需要的套件（--user，不動系統）。flavor：cuda（NVIDIA 顯示卡）／directml（不用裝 CUDA）／cpu."""
        cmds = self.python_candidates()
        if not cmds: return {'ok': False, 'message': '找不到 Python：請先到 python.org 下載 Python 3.11 安裝（勾「Add to PATH」）'}
        py = (self.env or {}).get('cmd') or cmds[0]
        pk = {'cuda': ['onnxruntime-gpu[cuda,cudnn]'], 'directml': ['onnxruntime-directml'], 'cpu': ['onnxruntime']}.get(flavor, ['onnxruntime-gpu[cuda,cudnn]'])
        logp = Path(self.E.root) / 'LOG' / 'face_install.txt'; logp.parent.mkdir(parents=True, exist_ok=True)
        cmd = py + ['-m', 'pip', 'install', '--user', '--upgrade'] + pk + ['numpy', 'opencv-python-headless']
        try:
            fh = open(logp, 'a', encoding='utf-8'); fh.write(f'\n===== {time.strftime("%Y-%m-%d %H:%M:%S")} {" ".join(cmd)}\n'); fh.flush()
            self.installing = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
        except Exception as ex: return {'ok': False, 'message': f'沒辦法開始安裝：{ex}'}
        self.E.log.w(f'👤 人物：開始安裝套件：{" ".join(cmd)}（紀錄在 LOG\\face_install.txt）')
        return {'ok': True, 'message': '開始安裝（大約 1～5 分鐘，看網路），裝好會自動重新檢查'}

    # ---- 開始／停止
    def running(self):
        p = self.proc
        return p is not None and p.poll() is None

    def worker_path(self):
        return Path(__file__).resolve().parent / 'vs_face_worker.py'

    def start(self, by='手動', cluster_only=False):
        if self.running(): return {'ok': True, 'message': '已經在跑了'}
        env = self.env if (self.env or {}).get('ok') else self.check_env()
        if not env.get('ok'):
            return {'ok': False, 'need_env': True, 'message': '這台電腦的 Python 還沒裝好需要的套件（onnxruntime、numpy、opencv）：到 👤 人物 → ⚙ 設定 按「安裝需要的套件」'}
        if not cluster_only and not env.get('has_models') and not env.get('insightface'):
            return {'ok': False, 'message': '找不到臉部模型：%USERPROFILE%\\.insightface\\models 底下要有 buffalo_l（det_10g.onnx、w600k_r50.onnx）'}
        c = self.cfg()
        try: (self.data / 'face_stop').unlink()
        except Exception: pass
        args = env['cmd'] + [str(self.worker_path()), '--data', str(self.data), '--ratio', str(c['ratio']), '--src', c['src'], '--ff', self.E.ff or 'ffmpeg',
                             '--thr', str(c['thr']), '--min-faces', str(c['min_faces']), '--gpu', '1' if c['gpu'] else '0', '--det', str(c['det']), '--model', c['model'],
                             '--log', str(Path(self.E.root) / 'LOG' / 'face_log.txt')]
        if c.get('minpx'): args += ['--minpx', str(c['minpx'])]
        if cluster_only: args.append('--cluster-only')
        try:
            self.proc = subprocess.Popen(args, creationflags=NO_WINDOW | BELOW, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(self.data))
        except Exception as ex: return {'ok': False, 'message': f'開不起來：{ex}'}
        self.started_by = by; self._was_running = True
        self.E.log.w(f'👤 人物：背景程式開始（{by}{"，只重新分群" if cluster_only else ""}）：抽 {c["ratio"] * 100:g}%、來源 {c["src"]}、門檻 {c["thr"]}、{"顯示卡" if c["gpu"] else "CPU"}（pid {self.proc.pid}）')
        return {'ok': True, 'message': '重新分群中…' if cluster_only else '開始了（可以關掉視窗，背景會繼續；中斷了下次接著做）'}

    def stop(self, why='手動'):
        if not self.running(): return {'ok': True, 'message': '本來就沒在跑'}
        try: (self.data / 'face_stop').write_text(why, encoding='utf-8')
        except Exception: pass
        self.E.log.w(f'👤 人物：要求停止（{why}）——做完手上這一部就停，做好的都存著')
        p = self.proc
        def waiter():
            for _ in range(60):
                if p.poll() is not None: return
                time.sleep(0.5)
            try: p.kill(); self.E.log.w('👤 人物：背景程式 30 秒沒停，強制結束（做好的已經存了）')
            except Exception: pass
        threading.Thread(target=waiter, daemon=True).start()
        return {'ok': True, 'message': '停止中…（做完手上這一部就停）'}

    def in_night(self, now=None):
        c = self.cfg()
        if not c.get('night'): return False
        lt = time.localtime(now or time.time()); cur = lt.tm_hour * 60 + lt.tm_min
        def mm(s):
            try: h, m = str(s).split(':'); return int(h) * 60 + int(m)
            except Exception: return 0
        a, b = mm(c.get('night_from')), mm(c.get('night_to'))
        return (a <= cur < b) if a <= b else (cur >= a or cur < b)

    def tick(self):
        """每 30 秒（背景執行緒）：夜間時段自動開始／結束；跑完或跑的時候同步人物到主資料庫；安裝完自動重新檢查."""
        try:
            if self.installing is not None and self.installing.poll() is not None:
                rc = self.installing.returncode; self.installing = None; self.E.log.w('👤 人物：安裝套件結束（' + ('成功' if rc == 0 else f'失敗 {rc}，看 LOG') + '\\face_install.txt）' if rc else '👤 人物：安裝套件結束（成功）'); self.check_env()
            night = self.in_night()
            held = bool(getattr(self.E, 'bg_hold', None) and self.E.bg_hold('faces'))       # V0.1.65 後台暫停中就不自動開始
            if night and not self.running() and self.cfg().get('night') and not held:
                st = self.status()
                if st['done'] < st['total'] and (self.env or {}).get('ok', True): self.start('夜間時段')
            if not night and self.running() and self.started_by == '夜間時段': self.stop('夜間時段結束')
            run = self.running()
            if run or self._was_running:
                if time.time() - self._last_sync > (60 if run else 0): self.sync_people()
                self._was_running = run
        except Exception: self.E.log.err('👤 人物 tick')

    # ---- 結果
    def persons(self, show_hidden=False, show_small=False, q=''):
        c = self.con()
        try:
            w = ['n_faces>0' if not show_small else '1=1']
            if not show_hidden: w.append('hidden=0')
            a = []
            if q: w.append('name LIKE ?'); a.append(f'%{q}%')
            R = [dict(zip(('id', 'name', 'n_faces', 'n_files', 'cover', 'hidden', 'auto_cat'), r)) for r in
                 c.execute(f'SELECT id, name, n_faces, n_files, cover, hidden, auto_cat FROM person WHERE {" AND ".join(w)} ORDER BY (length(name)>0) DESC, n_files DESC, n_faces DESC LIMIT 3000', a)]
            covers = {r['cover'] for r in R if r['cover']}
            F = {r[0]: r for r in c.execute(f'SELECT id, file_id, k, x, y, w, h, t FROM face WHERE id IN ({",".join(map(str, covers)) or "-1"})')}
            for r in R:
                fr = F.get(r['cover'])
                if fr is None:                                  # 代表臉不見了（被拿掉、合併）→ 換他最清楚的一張
                    fr = c.execute('SELECT id, file_id, k, x, y, w, h, t FROM face WHERE person=? AND ex=0 ORDER BY score*min(px,120) DESC LIMIT 1', (r['id'],)).fetchone()
                r['face'] = self._face_dict(fr)
            return R
        finally: c.close()

    @staticmethod
    def _face_dict(f):
        if not f: return None
        return {'id': f[0], 'file_id': f[1], 'k': f[2], 'x': f[3], 'y': f[4], 'w': f[5], 'h': f[6], 't': f[7]}

    def person(self, pid):
        c = self.con()
        try:
            r = c.execute('SELECT id, name, n_faces, n_files, cover, hidden, auto_cat FROM person WHERE id=?', (int(pid),)).fetchone()
            if not r: return None
            p = dict(zip(('id', 'name', 'n_faces', 'n_files', 'cover', 'hidden', 'auto_cat'), r))
            files = {}
            for fid, t, faceid, k, x, y, w, h in c.execute('SELECT file_id, t, id, k, x, y, w, h FROM face WHERE person=? AND ex=0 ORDER BY file_id, t', (int(pid),)):
                d = files.setdefault(fid, {'file_id': fid, 'times': [], 'faces': 0, 'face': None})
                d['faces'] += 1
                if not d['times'] or t - d['times'][-1] >= 2: d['times'].append(t)
                if d['face'] is None: d['face'] = {'id': faceid, 'file_id': fid, 'k': k, 'x': x, 'y': y, 'w': w, 'h': h, 't': t}
            ids = list(files)
            info = {}
            for i in range(0, len(ids), 500):
                chunk = ids[i:i + 500]
                for row in self.E.db.q(f'SELECT id, name, folder, size, dur, grade, arch, missing, th_cols, th_rows, th_n, th_step, w, h FROM files WHERE id IN ({",".join(map(str, chunk))})'):
                    info[row['id']] = dict(row)
            L = []
            for fid, d in files.items():
                f = info.get(fid)
                if not f or f.get('missing'): continue
                d.update({k: f.get(k) for k in ('name', 'folder', 'size', 'dur', 'grade', 'arch', 'th_cols', 'th_rows', 'th_n', 'th_step', 'w', 'h')}); L.append(d)
            L.sort(key=lambda d: (-d['faces'], d['name'] or ''))
            p['files'] = L
            p['samples'] = [self._face_dict(f) for f in c.execute('SELECT id, file_id, k, x, y, w, h, t FROM face WHERE person=? AND ex=0 ORDER BY score*min(px,120) DESC LIMIT 60', (int(pid),))]
            return p
        finally: c.close()


    def rename(self, pid, name):
        name = re.sub(r'[\\/:*?"<>|]', '', str(name or '')).strip()[:40]
        c = self.con()
        try:
            if name:
                other = c.execute('SELECT id FROM person WHERE name=? AND id!=?', (name, int(pid))).fetchone()
                if other: c.close(); return self.merge([int(pid)], other[0], name=name)
            c.execute('UPDATE person SET name=? WHERE id=?', (name, int(pid)))
        finally: c.close()
        self.E.log.w(f'👤 人物：#{pid} 取名為「{name}」' if name else f'👤 人物：#{pid} 拿掉名字'); self.sync_people(force=True)
        return {'ok': True, 'message': f'取名為「{name}」，之後新的影片長得像就自動套用' if name else '拿掉名字了'}

    def merge(self, pids, target, name=None):
        pids = [int(p) for p in pids if int(p) != int(target)]
        c = self.con()
        try:
            c.execute('BEGIN')
            for p in pids:
                c.execute('UPDATE face SET person=? WHERE person=?', (int(target), p)); c.execute('DELETE FROM person WHERE id=?', (p,))
            if name: c.execute('UPDATE person SET name=? WHERE id=?', (name, int(target)))
            c.execute(f"UPDATE person SET n_faces=(SELECT COUNT(*) FROM face WHERE person={int(target)} AND ex=0), n_files=(SELECT COUNT(DISTINCT file_id) FROM face WHERE person={int(target)} AND ex=0) WHERE id={int(target)}")
            c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('need_cluster','true')"); c.execute('COMMIT')
        finally: c.close()
        self.E.log.w(f'👤 人物：合併 {pids} → #{target}{f"（{name}）" if name else ""}'); self.sync_people(force=True)
        return {'ok': True, 'message': f'合併好了（{len(pids)} 群 → 1 個人）', 'id': int(target)}

    def set_flag(self, pid, **kw):
        ok = {k: (1 if v else 0) for k, v in kw.items() if k in ('hidden', 'auto_cat')}
        if not ok: return {'ok': False}
        c = self.con()
        try: c.execute('UPDATE person SET ' + ','.join(f'{k}=?' for k in ok) + ' WHERE id=?', list(ok.values()) + [int(pid)])
        finally: c.close()
        self.E.log.w(f'👤 人物：#{pid} ' + '、'.join(f'{k}={v}' for k, v in ok.items())); self.sync_people(force=True); return {'ok': True}

    def remove_faces(self, face_ids):
        """「不是他」：這些臉從這個人拿掉，之後也不會再被自動算進任何人."""
        ids = [int(i) for i in face_ids]
        c = self.con()
        try:
            c.execute(f'UPDATE face SET ex=1, person=0 WHERE id IN ({",".join(map(str, ids)) or "-1"})')
            c.execute("UPDATE person SET n_faces=(SELECT COUNT(*) FROM face WHERE person=person.id AND ex=0), n_files=(SELECT COUNT(DISTINCT file_id) FROM face WHERE person=person.id AND ex=0)")
            c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('need_cluster','true')")
        finally: c.close()
        self.E.log.w(f'👤 人物：拿掉 {len(ids)} 張臉（不是他）'); self.sync_people(force=True); return {'ok': True, 'message': f'拿掉 {len(ids)} 張臉'}

    def forget_files(self, fids):
        """V0.2.01 影片檔已經永久刪掉：它的臉、做過的紀錄都清掉，人數重算."""
        ids = ','.join(str(int(i)) for i in fids) or '-1'
        if not self.db_path.exists(): return 0
        c = self.con()
        try:
            c.execute('BEGIN')
            gone = [r[0] for r in c.execute(f'SELECT id FROM face WHERE file_id IN ({ids})')]
            c.execute(f'DELETE FROM face WHERE file_id IN ({ids})'); c.execute(f'DELETE FROM done WHERE file_id IN ({ids})')
            if gone: c.execute(f'UPDATE person SET cover=0 WHERE cover IN ({",".join(map(str, gone))})')
            c.execute("UPDATE person SET n_faces=(SELECT COUNT(*) FROM face WHERE person=person.id AND ex=0), n_files=(SELECT COUNT(DISTINCT file_id) FROM face WHERE person=person.id AND ex=0)")
            c.execute('COMMIT')
        except Exception:
            try: c.execute('ROLLBACK')
            except Exception: pass
            raise
        finally: c.close()
        if gone: self.E.log.w(f'👤 人物：{len(fids)} 部影片刪掉了，拿掉 {len(gone)} 張臉')
        try: self.sync_people(force=True)
        except Exception: pass
        return len(gone)

    def remove_file(self, pid, file_id):
        c = self.con()
        try: ids = [r[0] for r in c.execute('SELECT id FROM face WHERE person=? AND file_id=?', (int(pid), int(file_id)))]
        finally: c.close()
        return self.remove_faces(ids)

    def people_of(self, fid):
        """這部影片裡有誰（取了名字的）：[(pid, name, 出現幾次)]."""
        try: return [tuple(r) for r in self.E.db.q("SELECT pid, name, n FROM people WHERE file_id=? AND length(name)>0 ORDER BY n DESC", (int(fid),))]
        except Exception: return []

    def sync_people(self, force=False):
        """把「誰出現在哪部」寫到主資料庫的 people 表（檔案總管依人物篩選、卡片顯示名字）；設定了自動歸類的人，新影片歸進「名字」分類資料夾."""
        if self._sync_busy: return
        if not force and time.time() - self._last_sync < 20: return
        self._sync_busy = True
        try:
            c = self.con()
            try:
                P = {r[0]: (r[1], r[2], r[3]) for r in c.execute('SELECT id, name, hidden, auto_cat FROM person')}
                rows = c.execute('SELECT file_id, person, COUNT(*), GROUP_CONCAT(CAST(t AS INTEGER)) FROM face WHERE person>0 AND ex=0 GROUP BY file_id, person').fetchall()
            finally: c.close()
            out = []
            for fid, pid, n, ts in rows:
                nm, hidden, _a = P.get(pid, ('', 0, 0))
                if hidden: continue
                tl = sorted({int(x) for x in str(ts or '').split(',') if x.strip().lstrip('-').isdigit()})[:200]
                out.append((fid, pid, nm or '', n, ','.join(map(str, tl))))
            with self.E.db.lock:
                con = self.E.db.con
                try:
                    con.execute('DELETE FROM people'); con.executemany('INSERT OR REPLACE INTO people(file_id, pid, name, n, ts) VALUES(?,?,?,?,?)', out); con.commit()
                except Exception:
                    con.rollback(); raise
            self._last_sync = time.time()
            self._auto_cat(P)
        except Exception: self.E.log.err('👤 人物：同步到主資料庫')
        finally: self._sync_busy = False

    def _cat_name(self, nm):
        try: return sys.modules[type(self.E).__module__].safe_name(str(nm).strip())[:60]
        except Exception: return re.sub(r'[\\/:*?"<>|]', '_', str(nm).strip())[:60]

    def _auto_cat(self, P):
        """設定了「自動歸類」的人：出現至少 N 次、還沒歸檔的影片 → 歸到分類資料夾「名字」（會記在操作紀錄，可以搬回）."""
        need = int(self.cfg().get('auto_min') or 2)
        for pid, (nm, hidden, auto) in P.items():
            if not auto or not nm or hidden: continue
            ids = [r[0] for r in self.E.db.q("SELECT p.file_id FROM people p JOIN files f ON f.id=p.file_id WHERE p.pid=? AND p.n>=? AND f.missing=0 AND length(f.arch)=0", (pid, need))]
            if not ids: continue
            cn = self._cat_name(nm)
            if cn not in (self.E.cfg.get('cats') or []):
                try: self.E.add_cat(cn)
                except Exception: self.E.log.err('👤 自動歸類：新增分類')
            n = self.E.archive_many(ids, 'cat:' + cn)
            self.E.log.w(f'👤 人物：「{nm}」自動歸類 {n} 部（出現至少 {need} 次）')

    def apply_cat(self, pid, min_n=None):
        """手動：這個人的影片全部歸到分類資料夾「名字」."""
        P = self.person(pid)
        if not P or not P.get('name'): return {'ok': False, 'message': '先幫這個人取名字（分類資料夾用名字當名稱）'}
        need = int(min_n or self.cfg().get('auto_min') or 2); nm = P['name']
        ids = [f['file_id'] for f in P['files'] if f['faces'] >= need and not f.get('arch')]
        if not ids: return {'ok': False, 'message': f'沒有要歸類的（出現至少 {need} 次、還沒歸檔的）'}
        cn = self._cat_name(nm)
        if cn not in (self.E.cfg.get('cats') or []): self.E.add_cat(cn)
        n = self.E.archive_many(ids, 'cat:' + cn); self.E.log.w(f'👤 人物：「{nm}」手動歸類 {n} 部')
        return {'ok': n > 0, 'message': f'{n} 部排進搬檔隊伍 → 分類資料夾「{cn}」（操作紀錄可以搬回）', 'n': n}

"""SortCut 👤 人物（人臉分類）背景程式 — V0.1.51

用電腦上另外裝的 Python 3.11 跑（不是 SortCut 本身），需要 onnxruntime(-gpu／-directml)、numpy、opencv-python-headless。
有裝 insightface 就用它；沒有就直接用 %USERPROFILE%\\.insightface\\models 裡的模型（SCRFD 找臉＋ArcFace 臉的特徵）。
全部只在這台電腦上跑，不連網、不查身分。

做的事：
  1. 每部影片抽「已經做好的每 2 秒一張預覽圖」的一部分（例如 10%），找臉、算特徵，存到 Data\\faces.sqlite3
     （也可以改成從影片抽原畫面：比較準，但會讀硬碟）
  2. 已經取名字的人：新找到的臉長得像就直接算他的（新影片自動套用）
  3. 其他的臉：長得像的分成同一群（不會把 A 像 B、B 像 C 串成一大群）
  4. 每做完一部就存起來：中斷（關機、按停止、超過夜間時段）之後再開，接著做沒做完的

用法：python vs_face_worker.py --data <SortCut 的 Data 資料夾> [--ratio 0.1] [--src thumbs|video] [--ff ffmpeg.exe] [--cluster-only]
停止：在 Data 資料夾放一個 face_stop 檔（SortCut 的「停止」按鈕會放）。
"""
import os, sys, time, json, math, sqlite3, argparse, traceback, subprocess

T0 = time.time()
ARGS = None
LOGF = None


def log(msg):
    line = f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}'
    try: print(line, flush=True)
    except Exception: pass
    if LOGF:
        try:
            with open(LOGF, 'a', encoding='utf-8') as f: f.write(line + '\n')
        except Exception: pass


# ------------------------------------------------------------------ 資料庫
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS done(file_id INTEGER PRIMARY KEY, th_t REAL, ratio REAL, src TEXT, n_tiles INTEGER, n_faces INTEGER, t REAL, err TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS face(id INTEGER PRIMARY KEY AUTOINCREMENT, file_id INTEGER, t REAL, k INTEGER, x REAL, y REAL, w REAL, h REAL, score REAL, px REAL,
  emb BLOB, person INTEGER DEFAULT 0, ex INTEGER DEFAULT 0, src TEXT DEFAULT 'thumbs');
CREATE INDEX IF NOT EXISTS ix_face_file ON face(file_id);
CREATE INDEX IF NOT EXISTS ix_face_person ON face(person, file_id);
CREATE TABLE IF NOT EXISTS person(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT DEFAULT '', n_faces INTEGER DEFAULT 0, n_files INTEGER DEFAULT 0, cover INTEGER DEFAULT 0,
  centroid BLOB, hidden INTEGER DEFAULT 0, auto_cat INTEGER DEFAULT 0, t REAL DEFAULT 0);
"""


def open_db(path):
    con = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    con.execute('PRAGMA journal_mode=WAL'); con.execute('PRAGMA synchronous=NORMAL'); con.execute('PRAGMA busy_timeout=30000')
    con.executescript(SCHEMA)
    return con


def meta_set(con, **kw):
    for k, v in kw.items(): con.execute('INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)', (k, json.dumps(v, ensure_ascii=False)))


def meta_get(con, k, d=None):
    r = con.execute('SELECT v FROM meta WHERE k=?', (k,)).fetchone()
    try: return json.loads(r[0]) if r else d
    except Exception: return d


def stop_requested():
    return os.path.exists(os.path.join(ARGS.data, 'face_stop'))


# ------------------------------------------------------------------ 臉部模型
class Engine:
    """insightface 有裝就用 FaceAnalysis；沒有就自己用 onnxruntime 跑 SCRFD＋ArcFace（模型在 ~/.insightface/models）."""

    def __init__(self, gpu=True, det=640, model_name='buffalo_l', model_dir=''):
        import numpy as np, cv2, onnxruntime as ort
        self.np, self.cv2, self.ort = np, cv2, ort
        self.kind = ''; self.provider = 'CPU'; self.det_size = int(det)
        try:
            if hasattr(ort, 'preload_dlls'): ort.preload_dlls()                 # onnxruntime-gpu[cuda,cudnn]：用 pip 裝的 CUDA／cuDNN
        except Exception as ex: log(f'preload_dlls：{ex}')
        avail = ort.get_available_providers()
        want = (['CUDAExecutionProvider', 'DmlExecutionProvider'] if gpu else []) + ['CPUExecutionProvider']
        self.providers = [p for p in want if p in avail] or ['CPUExecutionProvider']
        log(f'onnxruntime {ort.__version__}，可用：{avail} → 用 {self.providers}')
        root = os.path.join(os.path.expanduser('~'), '.insightface')
        self.app = None
        if not model_dir:
            try:
                from insightface.app import FaceAnalysis
                self.app = FaceAnalysis(name=model_name, root=root, allowed_modules=['detection', 'recognition'], providers=self.providers)
                self.app.prepare(ctx_id=0 if gpu else -1, det_size=(self.det_size, self.det_size))
                self.kind = 'insightface'; self._check_provider(); log(f'用 insightface {getattr(sys.modules.get("insightface"), "__version__", "")}（{model_name}）'); return
            except ImportError: log('沒有裝 insightface → 直接用 onnxruntime 跑模型')
            except Exception as ex: log(f'insightface 載入失敗（{type(ex).__name__}: {ex}）→ 改用 onnxruntime 直接跑'); self.app = None
        d = model_dir or self._find_models(os.path.join(root, 'models'), model_name)
        if not d: raise RuntimeError(f'找不到臉部模型：{os.path.join(root, "models")} 底下沒有 SCRFD（det_*.onnx）＋ArcFace（w600k*.onnx／glintr100.onnx）')
        self._load_onnx(d); self.kind = 'onnx'; log(f'用 onnxruntime 直接跑：{d}（找臉 {os.path.basename(self.det_path)}、特徵 {os.path.basename(self.rec_path)}）')

    def _check_provider(self):
        try:
            sess = None
            for m in getattr(self.app, 'models', {}).values():
                sess = getattr(m, 'session', None)
                if sess: break
            P = sess.get_providers() if sess else []
            self.provider = 'CUDA' if 'CUDAExecutionProvider' in P else ('DirectML' if 'DmlExecutionProvider' in P else 'CPU')
        except Exception: pass

    @staticmethod
    def _find_models(base, prefer):
        if not os.path.isdir(base): return ''
        cands = [prefer] + sorted(x for x in os.listdir(base) if x != prefer)
        for nm in cands:
            d = os.path.join(base, nm)
            if not os.path.isdir(d): continue
            fs = os.listdir(d)
            if any(f.startswith(('det_', 'scrfd')) and f.endswith('.onnx') for f in fs) and any(f.endswith('.onnx') and ('w600k' in f or 'glint' in f or 'arcface' in f or 'r100' in f or 'r50' in f) for f in fs): return d
        return ''

    def _sess(self, path):
        so = self.ort.SessionOptions(); so.log_severity_level = 3
        for i in range(len(self.providers)):
            try:
                s = self.ort.InferenceSession(path, sess_options=so, providers=self.providers[i:])
                return s
            except Exception as ex: log(f'{self.providers[i]} 載入 {os.path.basename(path)} 失敗：{ex}')
        raise RuntimeError(f'載入不了 {path}')

    def _load_onnx(self, d):
        np = self.np; fs = sorted(os.listdir(d))
        self.det_path = os.path.join(d, next(f for f in fs if f.startswith(('det_', 'scrfd')) and f.endswith('.onnx')))
        self.rec_path = os.path.join(d, next(f for f in fs if f.endswith('.onnx') and ('w600k' in f or 'glint' in f or 'arcface' in f or 'r100' in f or 'r50' in f)))
        self.det = self._sess(self.det_path); self.rec = self._sess(self.rec_path)
        P = self.det.get_providers(); self.provider = 'CUDA' if 'CUDAExecutionProvider' in P else ('DirectML' if 'DmlExecutionProvider' in P else 'CPU')
        di = self.det.get_inputs()[0]; self.det_in = di.name; outs = self.det.get_outputs(); self.det_out = [o.name for o in outs]
        sh = di.shape; self.det_fixed = (sh[2], sh[3]) if isinstance(sh[2], int) and isinstance(sh[3], int) else None
        if self.det_fixed: self.det_size = int(sh[3])
        self.batched = len(outs[0].shape) == 3
        n = len(outs)
        self.fmc, self.strides, self.na, self.use_kps = {6: (3, [8, 16, 32], 2, False), 9: (3, [8, 16, 32], 2, True), 10: (5, [8, 16, 32, 64, 128], 1, False), 15: (5, [8, 16, 32, 64, 128], 1, True)}[n]
        if not self.use_kps: raise RuntimeError('找臉模型沒有五官點（要用 det_10g／det_2.5g／det_500m 這種有 kps 的 SCRFD）')
        ri = self.rec.get_inputs()[0]; self.rec_in = ri.name; self.rec_out = self.rec.get_outputs()[0].name
        self.rec_size = int(ri.shape[2]) if isinstance(ri.shape[2], int) else 112
        self.rec_batch = not isinstance(ri.shape[0], int) or ri.shape[0] != 1
        self.centers = {}
        self.arc = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655], [70.7299, 92.2041]], dtype=np.float32) * (self.rec_size / 112.0)

    # ---- SCRFD（照 insightface 的寫法）
    def _detect(self, img, thr=0.5, nms=0.4):
        np, cv2 = self.np, self.cv2; S = self.det_size
        h, w = img.shape[:2]; r = min(S / w, S / h); nw, nh = max(1, int(w * r)), max(1, int(h * r))
        canvas = np.zeros((S, S, 3), dtype=np.uint8); canvas[:nh, :nw] = cv2.resize(img, (nw, nh))
        blob = cv2.dnn.blobFromImage(canvas, 1.0 / 128.0, (S, S), (127.5, 127.5, 127.5), swapRB=True)
        outs = self.det.run(self.det_out, {self.det_in: blob})
        B, K, SC = [], [], []
        for i, st in enumerate(self.strides):
            sc = outs[i][0] if self.batched else outs[i]; bb = (outs[i + self.fmc][0] if self.batched else outs[i + self.fmc]) * st
            kp = (outs[i + 2 * self.fmc][0] if self.batched else outs[i + 2 * self.fmc]) * st
            fh, fw = S // st, S // st; key = (fh, fw, st)
            if key not in self.centers:
                c = np.stack(np.mgrid[:fh, :fw][::-1], axis=-1).astype(np.float32); c = (c * st).reshape(-1, 2)
                if self.na > 1: c = np.stack([c] * self.na, axis=1).reshape(-1, 2)
                self.centers[key] = c
            c = self.centers[key]; sc = sc.reshape(-1); pos = np.where(sc >= thr)[0]
            if not len(pos): continue
            b = np.stack([c[:, 0] - bb[:, 0], c[:, 1] - bb[:, 1], c[:, 0] + bb[:, 2], c[:, 1] + bb[:, 3]], axis=-1)[pos]
            k = np.zeros((len(c), 5, 2), dtype=np.float32)
            for j in range(5): k[:, j, 0] = c[:, 0] + kp[:, 2 * j]; k[:, j, 1] = c[:, 1] + kp[:, 2 * j + 1]
            B.append(b); K.append(k[pos]); SC.append(sc[pos])
        if not B: return []
        b = np.vstack(B) / r; k = np.vstack(K) / r; s = np.concatenate(SC)
        order = np.argsort(-s); keep = []
        x1, y1, x2, y2 = b[:, 0], b[:, 1], b[:, 2], b[:, 3]; area = (x2 - x1 + 1) * (y2 - y1 + 1)
        while order.size:
            i = order[0]; keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]]); yy1 = np.maximum(y1[i], y1[order[1:]]); xx2 = np.minimum(x2[i], x2[order[1:]]); yy2 = np.minimum(y2[i], y2[order[1:]])
            inter = np.maximum(0.0, xx2 - xx1 + 1) * np.maximum(0.0, yy2 - yy1 + 1); ovr = inter / (area[i] + area[order[1:]] - inter)
            order = order[np.where(ovr <= nms)[0] + 1]
        return [(b[i], k[i], float(s[i])) for i in keep]

    def _umeyama(self, src, dst):
        np = self.np; n = src.shape[0]; ms, md = src.mean(0), dst.mean(0); sc, dc = src - ms, dst - md
        A = dc.T @ sc / n; d = np.ones(2);
        if np.linalg.det(A) < 0: d[1] = -1
        U, S, Vt = np.linalg.svd(A); R = U @ np.diag(d) @ Vt
        var = (sc ** 2).sum() / n; s = (S * d).sum() / var if var > 0 else 1.0
        M = np.zeros((2, 3), dtype=np.float32); M[:, :2] = s * R; M[:, 2] = md - s * R @ ms
        return M

    def _embed(self, img, kpss):
        np, cv2 = self.np, self.cv2; S = self.rec_size
        crops = [cv2.warpAffine(img, self._umeyama(k.astype(np.float32), self.arc), (S, S), borderValue=0.0) for k in kpss]
        if not crops: return []
        out = []
        groups = [crops] if self.rec_batch else [[c] for c in crops]
        for g in groups:
            blob = cv2.dnn.blobFromImages(g, 1.0 / 127.5, (S, S), (127.5, 127.5, 127.5), swapRB=True)
            out.append(self.rec.run([self.rec_out], {self.rec_in: blob})[0])
        E = np.vstack(out).astype(np.float32); E /= (np.linalg.norm(E, axis=1, keepdims=True) + 1e-9)
        return list(E)

    def faces(self, img):
        """[(bbox x1,y1,x2,y2, 分數, 特徵(512, 已正規化))]."""
        if self.kind == 'insightface':
            return [(f.bbox, float(f.det_score), f.normed_embedding.astype(self.np.float32)) for f in self.app.get(img)]
        D = self._detect(img)
        if not D: return []
        E = self._embed(img, [k for _b, k, _s in D])
        return [(b, s, e) for (b, _k, s), e in zip(D, E)]


# ------------------------------------------------------------------ 讀圖
def imread(path):
    import numpy as np, cv2
    data = np.fromfile(path, dtype=np.uint8)                                   # 中文路徑也讀得到
    return cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None


def video_frame(ff, path, t, h=720):
    import numpy as np, cv2
    cmd = [ff, '-hide_banner', '-loglevel', 'error', '-nostdin', '-ss', f'{max(0.0, t):.2f}', '-i', path, '-frames:v', '1', '-vf', f'scale=-2:{h}', '-f', 'image2pipe', '-vcodec', 'bmp', '-']
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=60, creationflags=0x08000000 if os.name == 'nt' else 0, stdin=subprocess.DEVNULL)
        if p.returncode or not p.stdout: return None
        return cv2.imdecode(np.frombuffer(p.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception: return None


def sample_indices(n, ratio):
    if n <= 0: return []
    m = max(1, min(n, int(math.ceil(n * ratio))))
    lo = int(n * 0.02); hi = max(lo + 1, n - int(n * 0.02)); span = hi - lo
    return sorted({lo + int((i + 0.5) * span / m) for i in range(m)})


# ------------------------------------------------------------------ 分群
def l2n(np, X):
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)


def recompute_persons(con, np):
    """每個人的中心特徵（同一群所有臉的平均）、幾張臉、幾部影片、代表臉（分數×大小最高的）."""
    P = {}
    for pid, emb, score, px, fid, faceid in con.execute('SELECT person, emb, score, px, file_id, id FROM face WHERE person>0 AND ex=0'):
        e = np.frombuffer(emb, dtype=np.float16).astype(np.float32)
        d = P.setdefault(pid, {'s': np.zeros_like(e), 'n': 0, 'files': set(), 'best': (-1, 0)})
        d['s'] += e; d['n'] += 1; d['files'].add(fid)
        q = score * min(px, 120)
        if q > d['best'][0]: d['best'] = (q, faceid)
    con.execute('BEGIN')
    for pid, d in P.items():
        c = d['s'] / (np.linalg.norm(d['s']) + 1e-9)
        con.execute('UPDATE person SET n_faces=?, n_files=?, cover=?, centroid=?, t=? WHERE id=?', (d['n'], len(d['files']), d['best'][1], c.astype(np.float16).tobytes(), time.time(), pid))
    con.execute("DELETE FROM person WHERE length(name)=0 AND id NOT IN (SELECT DISTINCT person FROM face WHERE person>0 AND ex=0)")
    con.execute("UPDATE person SET n_faces=0, n_files=0 WHERE id NOT IN (SELECT DISTINCT person FROM face WHERE person>0 AND ex=0)")
    con.execute('COMMIT')


def centroids(con, np, named_only=False):
    R = con.execute('SELECT id, centroid, name FROM person WHERE centroid IS NOT NULL' + (" AND length(name)>0" if named_only else '')).fetchall()
    if not R: return [], np.zeros((0, 512), dtype=np.float32)
    ids = [r[0] for r in R]; C = np.vstack([np.frombuffer(r[1], dtype=np.float16).astype(np.float32) for r in R])
    return ids, l2n(np, C)


def assign_new(con, np, face_ids, E, thr):
    """新找到的臉：跟已經有的人（取了名字的優先）夠像就直接算他的."""
    ids, C = centroids(con, np)
    if not len(ids) or not len(face_ids): return 0
    S = E @ C.T; best = S.argmax(1); bs = S[np.arange(len(E)), best]; n = 0
    named = {r[0] for r in con.execute("SELECT id FROM person WHERE length(name)>0")}
    con.execute('BEGIN')
    for fid, b, s in zip(face_ids, best, bs):
        pid = ids[int(b)]
        if s >= (thr if pid in named else thr + 0.04): con.execute('UPDATE face SET person=? WHERE id=?', (pid, fid)); n += 1
    con.execute('COMMIT'); return n


def cluster(con, thr=0.45, min_faces=3):
    """重新分群：取了名字的人保留他現有的臉（你改過的不會被打亂）；其他的臉重新分。
    跟「組長」比（先拿品質好的臉當組長），不會串連；最後把很像的群合併；太少臉的群先不顯示（person=0）."""
    import numpy as np
    t0 = time.time(); recompute_persons(con, np)
    named = {r[0] for r in con.execute("SELECT id FROM person WHERE length(name)>0")}
    R = con.execute(f"SELECT id, emb, score, px, person FROM face WHERE ex=0 AND person NOT IN ({','.join(str(i) for i in named) or '-1'})").fetchall()
    if not R: meta_set(con, last_cluster=time.time()); return 0
    fids = np.array([r[0] for r in R]); E = l2n(np, np.vstack([np.frombuffer(r[1], dtype=np.float16).astype(np.float32) for r in R]))
    q = np.array([r[2] * min(r[3], 120) for r in R]); old = {r[0]: r[4] for r in R}
    nid, NC = centroids(con, np, named_only=True)
    lab = np.full(len(R), -1, dtype=np.int64)
    if len(nid):                                                               # 先比已經取名的人
        S = E @ NC.T; b = S.argmax(1); s = S[np.arange(len(E)), b]; m = s >= thr
        lab[m] = -100 - b[m]                                                   # 暫存：-100-第幾個有名字的人
    order = np.argsort(-q); C = []; Csum = []; members = []
    rest = [i for i in order if lab[i] == -1]
    for start in range(0, len(rest), 2048):
        idx = rest[start:start + 2048]; X = E[idx]
        if C:
            M = np.vstack(C); S = X @ M.T; b = S.argmax(1); s = S[np.arange(len(idx)), b]
        else: b = s = None
        for j, i in enumerate(idx):
            if s is not None and s[j] >= thr:
                c = int(b[j]); lab[i] = c; members[c].append(i); Csum[c] += E[i]
            else:                                                              # 跟同一批剛開的新群比
                if C and len(C) > (0 if s is None else M.shape[0]):
                    extra = np.vstack(C[(0 if s is None else M.shape[0]):]); ss = extra @ E[i]; k = int(ss.argmax())
                    if ss[k] >= thr:
                        c = (0 if s is None else M.shape[0]) + k; lab[i] = c; members[c].append(i); Csum[c] += E[i]; continue
                C.append(E[i].copy()); Csum.append(E[i].copy()); members.append([i]); lab[i] = len(C) - 1
        C = [cs / (np.linalg.norm(cs) + 1e-9) for cs in Csum]                  # 每批結束更新組長（平均臉）
    # 合併很像的群（中心很近）
    if len(C) > 1:
        M = np.vstack(C); parent = list(range(len(C)))
        def f(x):
            while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
            return x
        for st in range(0, len(C), 1024):
            S = M[st:st + 1024] @ M.T
            for a, row in enumerate(S):
                ia = st + a
                for jb in np.where(row >= thr + 0.08)[0]:
                    if jb > ia: parent[f(int(jb))] = f(ia)
        roots = {}
        for c in range(len(C)): roots.setdefault(f(c), []).extend(members[c])
        groups = list(roots.values())
    else: groups = members
    # 寫回：群太小的先不顯示；沒名字的群盡量沿用舊的編號（你點開過的人不會一直換號）
    con.execute('BEGIN')
    con.execute(f"UPDATE face SET person=0 WHERE ex=0 AND person NOT IN ({','.join(str(i) for i in named) or '-1'})")
    for i in np.where(lab <= -100)[0]: con.execute('UPDATE face SET person=? WHERE id=?', (nid[int(-100 - lab[i])], int(fids[i])))
    used = set(named); made = 0
    for g in sorted(groups, key=len, reverse=True):
        if len(g) < min_faces: continue
        votes = {}
        for i in g:
            o = old.get(int(fids[i]), 0)
            if o > 0 and o not in used: votes[o] = votes.get(o, 0) + 1
        pid = max(votes, key=votes.get) if votes and max(votes.values()) >= len(g) * 0.3 else None
        if pid is None or not con.execute('SELECT 1 FROM person WHERE id=?', (pid,)).fetchone():
            pid = con.execute("INSERT INTO person(name, t) VALUES('', ?)", (time.time(),)).lastrowid
        used.add(pid); made += 1
        con.executemany('UPDATE face SET person=? WHERE id=?', [(pid, int(fids[i])) for i in g])
    con.execute('COMMIT')
    recompute_persons(con, np); meta_set(con, last_cluster=time.time(), need_cluster=False)
    log(f'分群完成：{len(R):,} 張臉（不含已取名的）→ {made} 群（每群至少 {min_faces} 張），{time.time() - t0:.1f} 秒')
    return made


# ------------------------------------------------------------------ 主流程
def main():
    global ARGS, LOGF
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True); ap.add_argument('--ratio', type=float, default=0.1); ap.add_argument('--src', default='thumbs')
    ap.add_argument('--ff', default='ffmpeg'); ap.add_argument('--minpx', type=float, default=0); ap.add_argument('--det', type=int, default=640)
    ap.add_argument('--thr', type=float, default=0.45); ap.add_argument('--min-faces', type=int, default=3); ap.add_argument('--gpu', type=int, default=1)
    ap.add_argument('--model', default='buffalo_l'); ap.add_argument('--model-dir', default=''); ap.add_argument('--cluster-only', action='store_true')
    ap.add_argument('--log', default=''); ap.add_argument('--max-files', type=int, default=0)
    ARGS = ap.parse_args(); LOGF = ARGS.log or os.path.join(os.path.dirname(os.path.abspath(ARGS.data)), 'LOG', 'face_log.txt')
    try: os.makedirs(os.path.dirname(LOGF), exist_ok=True)
    except Exception: pass
    vdb = os.path.join(ARGS.data, 'videosift.sqlite3'); fdb = os.path.join(ARGS.data, 'faces.sqlite3')
    con = open_db(fdb); meta_set(con, state='start', pid=os.getpid(), t_start=time.time(), msg='準備中…', err='')
    try: os.remove(os.path.join(ARGS.data, 'face_stop'))
    except Exception: pass
    try:
        if ARGS.cluster_only:
            meta_set(con, state='cluster', msg='重新分群中…'); cluster(con, ARGS.thr, ARGS.min_faces); meta_set(con, state='idle', msg='分群完成', t_end=time.time()); return 0
        import numpy as np
        eng = Engine(gpu=bool(ARGS.gpu), det=ARGS.det, model_name=ARGS.model, model_dir=ARGS.model_dir)
        minpx = ARGS.minpx or (16 if ARGS.src == 'thumbs' else 40)
        meta_set(con, provider=eng.provider, kind=eng.kind, ratio=ARGS.ratio, src=ARGS.src)
        log(f'開始：抽 {ARGS.ratio * 100:g}% 的{"預覽圖" if ARGS.src == "thumbs" else "影片原畫面"}，臉至少 {minpx:g} 像素，相似門檻 {ARGS.thr}，{eng.provider}')
        vcon = sqlite3.connect(f'file:{vdb}?mode=ro', uri=True, timeout=30)
        rows = vcon.execute('SELECT id, path, name, th_dir, th_n, th_cols, th_rows, th_step, th_t, dur FROM files WHERE missing=0 AND th_state=2 AND th_n>0 ORDER BY folder, name').fetchall()
        vcon.close()
        done = {r[0]: r for r in con.execute('SELECT file_id, th_t, ratio, src FROM done')}
        todo = [r for r in rows if r[0] not in done or abs((done[r[0]][1] or 0) - (r[8] or 0)) > 1 or (done[r[0]][2] or 0) + 1e-9 < ARGS.ratio or done[r[0]][3] != ARGS.src]
        if ARGS.max_files: todo = todo[:ARGS.max_files]
        total = len(rows); n_done0 = total - len(todo)
        meta_set(con, state='run', total=total, done=n_done0, todo=len(todo), msg=f'要做 {len(todo):,} 部')
        log(f'影片庫 {total:,} 部有預覽圖；已經做過 {n_done0:,}，這次要做 {len(todo):,} 部')
        t_run = time.time(); faces_new = 0; since_cluster = 0
        for i, (fid, path, name, th_dir, th_n, cols, rows_, step, th_t, dur) in enumerate(todo):
            if stop_requested(): log('收到停止：做完的都存好了，下次接著做'); break
            t1 = time.time(); ks = sample_indices(int(th_n), ARGS.ratio); per = int(cols) * int(rows_); found = []; err = ''
            try:
                sheets = sorted(f for f in os.listdir(th_dir) if f.startswith('s') and f.endswith('.jpg')) if th_dir and os.path.isdir(th_dir) else []
                cache = {}
                for k in ks:
                    if stop_requested(): break
                    t = k * float(step or 2)
                    if ARGS.src == 'video':
                        img = video_frame(ARGS.ff, path, t)
                    else:
                        si = k // per
                        if si >= len(sheets): continue
                        if si not in cache: cache = {si: imread(os.path.join(th_dir, sheets[si]))}
                        big = cache[si]
                        if big is None: continue
                        tw, th = big.shape[1] // int(cols), big.shape[0] // int(rows_); q = k % per
                        img = big[(q // int(cols)) * th:(q // int(cols) + 1) * th, (q % int(cols)) * tw:(q % int(cols) + 1) * tw]
                    if img is None or img.size == 0 or float(img.mean()) < 6: continue    # 全黑（片頭、轉場、預覽圖沒填滿的格子）不用找
                    H, W = img.shape[:2]
                    for (x1, y1, x2, y2), sc, e in eng.faces(img):
                        fw, fh = x2 - x1, y2 - y1
                        if min(fw, fh) < minpx or sc < 0.55: continue
                        found.append((fid, float(t), int(k), float(max(0.0, x1 / W)), float(max(0.0, y1 / H)), float(min(1.0, fw / W)), float(min(1.0, fh / H)), float(sc), float(min(fw, fh)), e.astype(np.float16).tobytes(), ARGS.src))
            except Exception as ex:
                err = f'{type(ex).__name__}: {ex}'; log(f'⚠ {name}：{err}')
            con.execute('BEGIN')
            con.execute('DELETE FROM face WHERE file_id=? AND person NOT IN (SELECT id FROM person WHERE length(name)>0)', (fid,))
            ids = []
            for f in found:
                cur = con.execute('INSERT INTO face(file_id,t,k,x,y,w,h,score,px,emb,src) VALUES(?,?,?,?,?,?,?,?,?,?,?)', f); ids.append(cur.lastrowid)
            con.execute('INSERT OR REPLACE INTO done(file_id,th_t,ratio,src,n_tiles,n_faces,t,err) VALUES(?,?,?,?,?,?,?,?)', (fid, th_t, ARGS.ratio, ARGS.src, len(ks), len(found), time.time(), err))
            con.execute('COMMIT')
            if ids:
                E = l2n(np, np.vstack([np.frombuffer(f[9], dtype=np.float16).astype(np.float32) for f in found])); assign_new(con, np, ids, E, ARGS.thr)
            faces_new += len(found); since_cluster += 1
            el = time.time() - t_run; spd = (i + 1) / el if el > 0 else 0; left = (len(todo) - i - 1) / spd if spd > 0 else 0
            meta_set(con, done=n_done0 + i + 1, faces_new=faces_new, cur=name, eta=left, speed=spd, msg=f'{name}：{len(ks)} 張 → {len(found)} 張臉（{time.time() - t1:.1f} 秒）')
            if (i + 1) % 50 == 0: log(f'進度 {n_done0 + i + 1:,}/{total:,}，這次新找到 {faces_new:,} 張臉，每部 {1 / spd if spd else 0:.1f} 秒，還要約 {left / 60:.0f} 分鐘')
            if since_cluster >= 500: cluster(con, ARGS.thr, ARGS.min_faces); since_cluster = 0
        if faces_new or meta_get(con, 'need_cluster', False) or not con.execute('SELECT 1 FROM person LIMIT 1').fetchone():
            meta_set(con, state='cluster', msg='分群中…'); cluster(con, ARGS.thr, ARGS.min_faces)
        meta_set(con, state='idle', msg=('停止了（下次接著做）' if stop_requested() else '都做完了 ✔'), t_end=time.time())
        log(f'結束：這次新找到 {faces_new:,} 張臉，花 {(time.time() - T0) / 60:.1f} 分鐘')
        return 0
    except Exception as ex:
        log('錯誤：\n' + traceback.format_exc()); meta_set(con, state='error', err=f'{type(ex).__name__}: {ex}', msg='出錯了（看 LOG\\face_log.txt）', t_end=time.time()); return 2


if __name__ == '__main__':
    sys.exit(main())

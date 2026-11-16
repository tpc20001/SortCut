"""🐾 找有貓狗的影片（V0.2.93，不准 import Qt）。

做法（不用另外裝東西）：
- 每部影片拿已經做好的 16 格裡挑 4 格，用 FFmpeg 切成 224×224 的小圖。
- 交給 Windows 內建的「Windows ML」（Windows 10 1809 以後都有）跑 MobileNet v2（ImageNet 1000 類，裡面有 118 種狗、5 種貓）。
- 模型第一次用的時候自動下載（約 14 MB），存在 Data\\ai\\；下載不了可以自己放進去。
- 只看「機率」：狗的類加起來、貓的類加起來，4 格裡取最高的。
"""
import os, time, json, struct, threading, subprocess, urllib.request
from pathlib import Path

MODEL = 'mobilenetv2-7.onnx'
URLS = ['https://huggingface.co/onnxmodelzoo/legacy_models/resolve/main/validated/vision/classification/mobilenet/model/mobilenetv2-7.onnx',
        'https://github.com/onnx/models/raw/main/validated/vision/classification/mobilenet/model/mobilenetv2-7.onnx',
        'https://github.com/onnx/models/raw/main/vision/classification/mobilenet/model/mobilenetv2-7.onnx',
        'https://media.githubusercontent.com/media/onnx/models/main/validated/vision/classification/mobilenet/model/mobilenetv2-7.onnx']
SZ = 224; ONE = SZ * SZ * 3; NCELL = 4; BATCH = 50                       # 一次交給 PowerShell 50 部（V0.3.91：少開幾次 PowerShell）
FW, FH = 320, 180; FONE = FW * FH                                          # 👤 人臉：灰階 320×180（V0.3.13）
def _r(a, b): return set(range(a, b + 1))
# 🔎 內容猜測（V0.3.73）：ImageNet 1000 類粗分成幾種常見內容
SCENES = [('screen', '📺 拍到螢幕／網頁／文件', {527, 590, 620, 664, 681, 782, 851, 487, 508, 916, 917, 918, 921, 922}),
          ('food', '🍜 食物／飲料', _r(923, 969)),
          ('car', '🚗 車子／火車／飛機', {404, 407, 436, 444, 466, 468, 511, 547, 565, 609, 627, 654, 656, 661, 665, 670, 671, 705, 717, 751, 779, 817, 820, 864, 867, 874, 895}),
          ('boat', '⛵ 船／划船', {472, 484, 510, 554, 576, 625, 628, 693, 724, 780, 814, 833, 871, 914}),
          ('sea', '🏖 海邊／湖邊／潛水', {973, 975, 977, 978, 983}),
          ('mount', '🏔 山／風景', {970, 972, 974, 976, 979, 980}),
          ('snow', '⛄ 雪地／滑雪', {537, 795, 802, 803}),
          ('baby', '👶 嬰兒床／尿布／玩偶', {431, 516, 520, 529, 850}),
          ('animal', '🐦 其他動物（不是貓狗）', _r(0, 150) | _r(269, 280) | _r(286, 397))]
DARK = 22; FLAT = 9                                                         # 🌑 最亮的一格平均還不到 22（0～255）＝很暗；⬜ 最有變化的一格標準差還不到 9＝幾乎沒東西（V0.3.78）
SQ = [i * i for i in range(256)]
STILL = 4                                                                  # 🧱 4 格之間平均差不到 4（0～255）＝畫面幾乎沒動（V0.3.80）


def mot_of(cs):
    """同一部影片切出來的幾張（整格壓扁那幾張）兩兩比：最大的平均差；只有一張回 -1."""
    sq = cs[0::2] if len(cs) >= 4 else cs
    if len(sq) < 2: return -1.0
    best = 0.0
    for a, b in zip(sq, sq[1:]):
        va = a[::11]; vb = b[::11]; n = min(len(va), len(vb)) or 1
        best = max(best, sum(abs(x - y) for x, y in zip(va, vb)) / n)
    return best


def lum_of(c):
    """一張 RGB 小圖的（平均亮度, 標準差），每 7 個位元組取一個（夠準、很快）."""
    v = c[::7]; n = len(v) or 1; m = sum(v) / n
    return m, max(0.0, sum(map(SQ.__getitem__, v)) / n - m * m) ** 0.5


SCENE_P = 0.3                                                              # 最像的那類要有 3 成把握才算
NO_WINDOW = (0x08000000 | 0x00004000) if os.name == 'nt' else 0          # 不開黑視窗＋優先權「低於一般」：你用電腦時不卡（V0.3.76）

PS1 = r'''param([string]$model, [string]$inp)
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }
trap { [Console]::Out.WriteLine('ERR ' + ($_.InvocationInfo.ScriptLineNumber) + ': ' + $_.Exception.Message); exit 3 }
Add-Type -TypeDefinition @"
public static class FcPet {
  static readonly float[] M = {0.485f, 0.456f, 0.406f}; static readonly float[] S = {0.229f, 0.224f, 0.225f};
  public static float[] Norm(byte[] b, int off) {
    int n = 224 * 224; var f = new float[3 * n];
    for (int i = 0; i < n; i++) for (int c = 0; c < 3; c++) f[c * n + i] = (b[off + i * 3 + c] / 255f - M[c]) / S[c];
    return f;
  }
  public static string Score(float[] z) {
    double sum = 0; bool prob = true; foreach (var v in z) { sum += v; if (v < 0 || v > 1) prob = false; }
    var e = new double[z.Length];
    if (prob && System.Math.Abs(sum - 1) < 0.05) { for (int i = 0; i < z.Length; i++) e[i] = z[i]; sum = 1; }
    else { float mx = float.MinValue; foreach (var v in z) if (v > mx) mx = v; sum = 0; for (int i = 0; i < z.Length; i++) { e[i] = System.Math.Exp(z[i] - mx); sum += e[i]; } }
    double d = 0, c2 = 0; for (int i = 151; i <= 268 && i < e.Length; i++) d += e[i]; for (int i = 281; i <= 285 && i < e.Length; i++) c2 += e[i];
    int top = 0; for (int i = 1; i < z.Length; i++) if (z[i] > z[top]) top = i;
    var ci = System.Globalization.CultureInfo.InvariantCulture;
    return (d / sum).ToString("0.0000", ci) + " " + (c2 / sum).ToString("0.0000", ci) + " " + top + " " + (e[top] / sum).ToString("0.0000", ci);
  }
}
"@
$null = [Windows.AI.MachineLearning.LearningModel,Windows.AI.MachineLearning,ContentType=WindowsRuntime]
$null = [Windows.AI.MachineLearning.LearningModelSession,Windows.AI.MachineLearning,ContentType=WindowsRuntime]
$null = [Windows.AI.MachineLearning.LearningModelBinding,Windows.AI.MachineLearning,ContentType=WindowsRuntime]
$null = [Windows.AI.MachineLearning.TensorFloat,Windows.AI.MachineLearning,ContentType=WindowsRuntime]
$m = [Windows.AI.MachineLearning.LearningModel]::LoadFromFilePath($model)
$inName = @($m.InputFeatures)[0].Name; $outName = @($m.OutputFeatures)[0].Name
$s = [Windows.AI.MachineLearning.LearningModelSession]::new($m)
$bytes = [IO.File]::ReadAllBytes($inp); $n = [int][Math]::Floor($bytes.Length / 150528)
[Console]::Out.WriteLine("OK $n $inName $outName")
for ($k = 0; $k -lt $n; $k++) {
  $f = [FcPet]::Norm($bytes, $k * 150528)
  $t = [Windows.AI.MachineLearning.TensorFloat]::CreateFromArray([long[]]@(1, 3, 224, 224), $f)
  $b = [Windows.AI.MachineLearning.LearningModelBinding]::new($s)
  $b.Bind($inName, $t)
  $r = $s.Evaluate($b, "r$k")
  $o = $null; try { $o = $r.Outputs[$outName] } catch { }
  if ($o -eq $null) { try { $o = $r.Outputs.Lookup($outName) } catch { } }
  if ($o -eq $null) { foreach ($kv in $r.Outputs) { if ($kv.Key -eq $outName) { $o = $kv.Value } } }
  if ($o -eq $null) { throw "讀不到輸出 $outName" }
  $v = [float[]]@($o.GetAsVectorView())
  [Console]::Out.WriteLine([FcPet]::Score($v))
}
'''


FACE_PS1 = r"""param([string]$inp, [int]$w, [int]$h)
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }
trap { [Console]::Out.WriteLine('ERR ' + ($_.InvocationInfo.ScriptLineNumber) + ': ' + $_.Exception.Message); exit 3 }
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, [Type]$t) { $m = $asTask.MakeGenericMethod($t); $task = $m.Invoke($null, @($op)); $null = $task.Wait(-1); return $task.Result }
$null = [Windows.Media.FaceAnalysis.FaceDetector,Windows.Media.FaceAnalysis,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Media.FaceAnalysis.DetectedFace,Windows.Media.FaceAnalysis,ContentType=WindowsRuntime]
$fd = Await ([Windows.Media.FaceAnalysis.FaceDetector]::CreateAsync()) ([Windows.Media.FaceAnalysis.FaceDetector])
$bytes = [IO.File]::ReadAllBytes($inp); $one = $w * $h; $n = [int][Math]::Floor($bytes.Length / $one)
[Console]::Out.WriteLine("OK $n")
$lt = [System.Collections.Generic.IList[Windows.Media.FaceAnalysis.DetectedFace]]
for ($k = 0; $k -lt $n; $k++) {
  $buf = [System.Runtime.InteropServices.WindowsRuntime.WindowsRuntimeBufferExtensions]::AsBuffer($bytes, $k * $one, $one)
  $sb = [Windows.Graphics.Imaging.SoftwareBitmap]::CreateCopyFromBuffer($buf, [Windows.Graphics.Imaging.BitmapPixelFormat]::Gray8, $w, $h)
  $faces = Await ($fd.DetectFacesAsync($sb)) $lt
  $c = 0; $a = 0.0
  foreach ($f in $faces) { $c++; $r = $f.FaceBox; $x = ($r.Width * $r.Height) / [double]$one; if ($x -gt $a) { $a = $x } }
  [Console]::Out.WriteLine("F $c " + $a.ToString('0.0000', [Globalization.CultureInfo]::InvariantCulture))
}
"""


class Pets:
    def __init__(self, E, old=None):
        self.E = E; self.st = old.st if old is not None and getattr(old, 'st', None) else {}
        self.runner = None; self.face_runner = None                               # 測試用：換成假的
        try: E.db.x('CREATE TABLE IF NOT EXISTS vc_pet(fid INTEGER PRIMARY KEY, dog REAL, cat REAL, top INTEGER, t REAL)')
        except Exception: E.log.err('🐾 建表')
        threading.Thread(target=self._auto_loop, name='PetAuto', daemon=True).start()
        if old is not None and old.st.get('run') and not old.st.get('cancel'):        # 🔁 更新時正在找：舊的停下來後，新的接著找（V0.4.11）
            k_ = old.st.get('kind') or 'video'
            def resume():
                for _ in range(900):
                    if not self.st.get('run'): break
                    time.sleep(1)
                if E.alive() and not self.st.get('cancel') and not E.stop_all: E.log.w('🐾 更新後接著看內容'); self.start(0, k_)
            threading.Thread(target=resume, name='PetResume', daemon=True).start()
        elif old is None and E.cfg.get('pet_resume'):                                # 🔁 上次關程式時還沒看完：開程式 2 分鐘後接著看（V0.4.12）
            k2 = E.cfg.get('pet_resume_k') or 'video'
            def resume2():
                time.sleep(120)
                if E.alive() and not self.st.get('run') and E.cfg.get('pet_resume'): E.log.w('🐾 上次沒看完，接著看內容'); self.start(0, k2)
            threading.Thread(target=resume2, name='PetResume', daemon=True).start()
        try: E.db.x('CREATE INDEX IF NOT EXISTS ix_simv_fid ON simv_grp(fid)')        # 👯 找相似版本用（V0.3.39）
        except Exception: pass
        for col in ('face INTEGER', 'farea REAL', 'sc INTEGER', 'sp REAL', 'lum REAL', 'lstd REAL', 'mot REAL', 'pc TEXT', 'nopet INTEGER'):   # nopet：你按過「不是貓狗」（V0.6.00）                                    # 👤 人臉（V0.3.13）：幾張臉（-1＝沒看）、最大的臉佔多少
            try: E.db.x(f'ALTER TABLE vc_pet ADD COLUMN {col}')
            except Exception: pass

    # ------------------------------------------------------------ 模型
    def adir(self): d = Path(self.E.data) / 'ai'; d.mkdir(parents=True, exist_ok=True); return d

    def model(self):
        p = self.adir() / MODEL
        return p if p.exists() and p.stat().st_size > 5_000_000 else None

    def fetch(self):
        if self.model(): return True, ''
        err = []
        for u in URLS:
            tmp = self.adir() / (MODEL + '.part')
            try:
                self.st['msg'] = '⬇ 第一次用：下載辨識模型（約 14 MB）…'
                req = urllib.request.Request(u, headers={'User-Agent': 'FileCompare'})
                with urllib.request.urlopen(req, timeout=60) as r, open(tmp, 'wb') as f:
                    while True:
                        b = r.read(1 << 16)
                        if not b: break
                        f.write(b)
                with open(tmp, 'rb') as f_: hd = f_.read(1)
                if tmp.stat().st_size > 5_000_000 and hd == b'\x08': os.replace(tmp, self.adir() / MODEL); self.E.log.w(f'🐾 下載好辨識模型：{u}'); return True, ''
                err.append(f'{u}：檔案太小或不是模型檔')
            except Exception as ex: err.append(f'{u}：{type(ex).__name__}: {ex}')
            try: tmp.unlink()
            except OSError: pass
        return False, '；'.join(err)[-600:]

    # ------------------------------------------------------------ 切小圖
    def crop_photo(self, fid, gray=False):
        """📷 照片：縮圖（沒有就現做）整張縮成 224×224（gray＝灰階 320×180 給人臉用）."""
        ff, _fp = self.E.ff(); p = self.E.fc_thumb(fid, 480 if gray else 320)
        if not ff or not p: return []
        one = FONE if gray else ONE
        vf = f'scale={FW}:{FH}:force_original_aspect_ratio=decrease,pad={FW}:{FH}:(ow-iw)/2:(oh-ih)/2,setsar=1' if gray else f'scale={SZ}:{SZ},setsar=1'
        try:
            r = subprocess.run([ff, '-hide_banner', '-v', 'error', '-i', p, '-vf', vf, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'gray' if gray else 'rgb24', '-'],
                               capture_output=True, timeout=60, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
            return [r.stdout[:one]] if len(r.stdout) >= one else []
        except Exception: return []

    def crops(self, fid, gray=False, cells_out=None, with_gray=False):
        """這部的 16 格挑 4 格，切成 224×224 RGB（bytes），回傳 list；沒有 16 格就回 []；gray＝灰階 320×180（人臉）.
        with_gray＝同一次 FFmpeg 順便切好灰階的，放在 self._gc[fid]，等一下 crops(fid, gray=True) 直接拿（少開一次 FFmpeg）（V0.4.14）."""
        if gray:
            gc = self.__dict__.setdefault('_gc', {}).pop(fid, None)
            if gc is not None: return gc
        g = self.E.vc.grid(fid, build=False)
        if g.get('photo'): return self.crop_photo(fid, gray)                     # （照片沒有格子，cells_out 不用填）
        if not g.get('ok') or g.get('photo') or not g.get('cells'): return []
        C = g['cells']; pick = [C[int(i * len(C) / NCELL + len(C) / NCELL / 2)] for i in range(min(NCELL, len(C)))]
        ff, _fp = self.E.ff()
        if not ff: return []
        out = []; by = {}; gout = [] if (with_gray and not gray) else None
        for c in pick: by.setdefault(c['s'], []).append(c)
        for s, L in by.items():
            sheet = g['sheets'][s]; cols, rows = g['cols'], g['rows']; fc = ''
            k = 0; GP = 'scale={FW}:{FH}:force_original_aspect_ratio=decrease,pad={FW}:{FH}:(ow-iw)/2:(oh-ih)/2,setsar=1'.format(FW=FW, FH=FH)
            for i, c in enumerate(L):
                cut = f"[0:v]crop=iw/{cols}:ih/{rows}:iw*{c['c']}/{cols}:ih*{c['r']}/{rows}"
                if gray: fc += f"{cut},{GP}[c{k}];"; k += 1
                elif gout is not None:                                              # RGB 兩張＋灰階一張，一次切完
                    fc += f"{cut},split=3[a{i}][b{i}][h{i}];[a{i}]scale={SZ}:{SZ},setsar=1[c{k}];[b{i}]crop=w='min(iw,ih)':h='min(iw,ih)',scale={SZ}:{SZ},setsar=1[c{k + 1}];[h{i}]{GP}[g{i}];"; k += 2
                else:                                                               # 整格壓扁＋中間正方形各一張（貓狗在中間比較容易認出來）（V0.3.59）
                    fc += f"{cut},split[a{i}][b{i}];[a{i}]scale={SZ}:{SZ},setsar=1[c{k}];[b{i}]crop=w='min(iw,ih)':h='min(iw,ih)',scale={SZ}:{SZ},setsar=1[c{k + 1}];"; k += 2
            fc += (''.join(f'[c{j}]' for j in range(k)) + f'vstack=inputs={k}[o]') if k > 1 else '[c0]null[o]'
            gtmp = None
            if gout is not None:
                fc += ';' + ((''.join(f'[g{j}]' for j in range(len(L))) + f'vstack=inputs={len(L)}[go]') if len(L) > 1 else '[g0]null[go]')
                gtmp = str(self.adir() / f'g{threading.get_ident()}.raw')
            try:
                one = FONE if gray else ONE
                cmd = [ff, '-hide_banner', '-v', 'error', '-y', '-i', sheet, '-filter_complex', fc, '-map', '[o]', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'gray' if gray else 'rgb24', '-']
                if gtmp: cmd += ['-map', '[go]', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'gray', gtmp]
                r = subprocess.run(cmd, capture_output=True, timeout=60, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
                b = r.stdout
                if gtmp:
                    try:
                        gb = Path(gtmp).read_bytes(); os.remove(gtmp)
                        gout += [gb[j * FONE:(j + 1) * FONE] for j in range(len(L)) if len(gb) >= (j + 1) * FONE]
                    except Exception: pass
                for i in range(k):
                    if len(b) >= (i + 1) * one:
                        out.append(b[i * one:(i + 1) * one])
                        if cells_out is not None: cc = L[i if gray else i // 2]; cells_out.append(f"{cc['s']},{cc['c']},{cc['r']}")   # 這張是哪一格（🐾 縮圖用）
            except Exception: pass
        if gout is not None and out: self.__dict__.setdefault('_gc', {})[fid] = gout
        return out

    # ------------------------------------------------------------ 跑 Windows ML
    def _run_ps(self, blob, tag=''):
        if self.runner: return self.runner(blob)
        if os.name != 'nt': return None, '只有 Windows 能用（要用 Windows 內建的 Windows ML）'
        d = self.adir(); ps = d / f'pet{tag}.ps1'; inp = d / f'batch{tag}.bin'
        ps.write_text(PS1, encoding='utf-8-sig'); inp.write_bytes(blob)
        exe = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
        try:
            r = subprocess.run([exe, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(ps), '-model', str(self.model()), '-inp', str(inp)],
                               capture_output=True, timeout=1800, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
        except Exception as ex: return None, f'{type(ex).__name__}: {ex}'
        o = r.stdout.decode('utf-8', 'replace').splitlines(); e = r.stderr.decode('utf-8', 'replace')
        if not o or not o[0].startswith('OK'):
            if not e.strip() and r.stderr:
                try: e = r.stderr.decode('mbcs', 'replace')
                except Exception: pass
            return None, ('\n'.join(o) + '\n' + e).strip()[-800:] or f'PowerShell 結束碼 {r.returncode}'
        R = []; errl = [ln for ln in o[1:] if ln.startswith('ERR')]
        if errl and not any(not ln.startswith('ERR') for ln in o[1:]): return None, '\n'.join(errl)[-800:]
        for ln in o[1:]:
            p = ln.split()
            if len(p) >= 3:
                try: R.append((float(p[0]), float(p[1]), int(p[2]), float(p[3]) if len(p) > 3 else 0.0))   # 第 4 個＝最像的那一類有多像（V0.3.73）
                except ValueError: pass
        return R, (('\n'.join(errl) + e)[-400:] if len(R) < int(o[0].split()[1]) else '')

    def _run_face(self, blob, tag=''):
        """👤 Windows 內建的人臉偵測（Windows.Media.FaceAnalysis，Win10 起都有）→ [(幾張臉, 最大的臉佔畫面多少)]、錯誤訊息."""
        if self.face_runner: return self.face_runner(blob)
        if os.name != 'nt': return None, '只有 Windows 能用'
        d = self.adir(); ps = d / f'face{tag}.ps1'; inp = d / f'face{tag}.bin'
        ps.write_text(FACE_PS1, encoding='utf-8-sig'); inp.write_bytes(blob)
        exe = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
        try:
            r = subprocess.run([exe, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(ps), '-inp', str(inp), '-w', str(FW), '-h', str(FH)],
                               capture_output=True, timeout=1800, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
        except Exception as ex: return None, f'{type(ex).__name__}: {ex}'
        o = r.stdout.decode('utf-8', 'replace').splitlines(); e = r.stderr.decode('utf-8', 'replace')
        if not o or not o[0].startswith('OK'): return None, ('\n'.join(o) + '\n' + e).strip()[-800:] or f'PowerShell 結束碼 {r.returncode}'
        R = []
        for ln in o[1:]:
            p = ln.split()
            if len(p) >= 3 and p[0] == 'F':
                try: R.append((int(p[1]), float(p[2])))
                except ValueError: pass
        errl = [ln for ln in o[1:] if ln.startswith('ERR')]
        return R, '\n'.join(errl)[-400:]

    def _auto_loop(self):
        """🐾 背景自動看新的（V0.3.17）：設定開著時，每 10 分鐘看看有沒有新做好 16 格、還沒看過的."""
        time.sleep(120)
        while self.E.alive():
            try:
                if self.E.cfg.get('pet_auto') and not self.st.get('run') and time.time() - getattr(self, 'fail_t', 0) > 86400 and not self.E.quiet_now() and not self.E.stop_all and self.todo('video'): self.start(0, 'video', build=False)
            except Exception: pass
            for _ in range(600):
                if not self.E.alive(): return
                time.sleep(1)

    # ------------------------------------------------------------ 背景工作
    def _lum_fill(self, S):
        """🌑 以前看過、還沒算亮度的補算（只用 FFmpeg 切圖，不跑 Windows ML）（V0.3.78）."""
        E = self.E; L = [r[0] for r in E.db.q("SELECT p.fid FROM vc_pet p JOIN files f ON f.id=p.fid WHERE p.lum IS NULL OR (p.mot IS NULL AND f.kind='video')")]
        for i, fid in enumerate(L):
            if S.get('cancel') or E.stop_all or not E.alive(): return
            if i % 20 == 0:
                S['msg'] = f'🌑 補算以前看過的亮度：{i:,}／{len(L):,}'
                if time.time() - getattr(E.vc, 'last_view', 0) < 8: time.sleep(2)
            LU = [-1.0, -1.0]; cs = self.crops(fid)
            for c in cs: m, sd = lum_of(c); LU[0] = max(LU[0], m); LU[1] = max(LU[1], sd)
            E.db.x('UPDATE vc_pet SET lum=?, lstd=?, mot=? WHERE fid=?', (LU[0], LU[1], mot_of(cs), fid))

    def todo(self, kind='video'):
        """還沒分類、16 格做好了（照片不用）、還沒看過的."""
        done = {r[0] for r in self.E.db.q('SELECT fid FROM vc_pet WHERE dog>=0 OR face>=0')}     # 貓狗、人臉都沒跑成功的下次再試（V0.3.79）
        L = [f for f in self.E.vc.vlist('todo', kind=kind) if f not in done]
        if kind == 'photo': return L
        P = {r[0]: (r[1], r[2]) for r in self.E.db.q("SELECT id, path, size FROM files WHERE state='' AND kind='video'")}
        R = []; NR = []
        for f in L:
            if f in P: (R if self.E.vc.state_of(f, P[f][0], P[f][1]) == 0 else NR).append(f)
        self.notready = len(NR); self.nr_list = NR; return R                     # 16 格還沒做好的（V0.3.81）

    def status(self, kind='video'):
        n = (self.E.db.one('SELECT COUNT(*) FROM vc_pet') or [0])[0]
        dog = (self.E.db.one('SELECT COUNT(*) FROM vc_pet WHERE dog>=?', (self.th(),)) or [0])[0]
        cat = (self.E.db.one('SELECT COUNT(*) FROM vc_pet WHERE cat>=?', (self.th(),)) or [0])[0]
        face = (self.E.db.one('SELECT COUNT(*) FROM vc_pet WHERE face>0') or [0])[0]
        try: npn = (self.E.db.one('SELECT COUNT(*) FROM vc_pet WHERE nopet=1') or [0])[0]
        except Exception: npn = 0
        S = dict(self.st); S.update(checked=n, dog=dog, cat=cat, face=face, nopet=npn, th=self.th(), auto=bool(self.E.cfg.get('pet_auto')), model=bool(self.model()), win=os.name == 'nt' or bool(self.runner))
        try: S['scenes'] = self.scene_counts(kind)
        except Exception: S['scenes'] = []
        try:                                                                         # 🐾 抽樣：還沒分類、最像貓狗的 8 部（給你看準不準）（V0.3.99）
            t = self.th(); S['sample'] = [r[0] for r in self.E.db.q("SELECT p.fid FROM vc_pet p JOIN files f ON f.id=p.fid LEFT JOIN vc_tag g ON g.fid=p.fid WHERE g.fid IS NULL AND f.state='' AND f.kind=? AND (p.dog>=? OR p.cat>=?) AND COALESCE(p.nopet,0)=0 ORDER BY MAX(p.dog, p.cat) DESC LIMIT 8", ('photo' if kind == 'photo' else 'video', t, t))]
        except Exception: S['sample'] = []
        return S

    def th(self):
        try: return float(self.E.cfg.get('pet_th') or 0.35)
        except (TypeError, ValueError): return 0.35

    def todo_count(self):
        """還沒分、有貓狗的大約幾部（不跑整份清單，給總覽用；V0.3.69）."""
        t = self.th()
        return (self.E.db.one("SELECT COUNT(*) FROM vc_pet p JOIN files f ON f.id=p.fid LEFT JOIN vc_tag g ON g.fid=p.fid WHERE g.fid IS NULL AND f.state='' AND f.kind='video' AND (p.dog>=? OR p.cat>=?) AND COALESCE(p.nopet,0)=0", (t, t)) or [0])[0]

    def scene_of(self, top):
        for k, nm, S in SCENES:
            if top in S: return k
        return ''

    def scene_ids(self, key):
        if key == 'junk': return self.scene_ids('dark') | self.scene_ids('flat') | self.scene_ids('still')   # 🌑 三種一起（V0.3.92）
        if key == 'dark': return {r[0] for r in self.E.db.q('SELECT fid FROM vc_pet WHERE lum>=0 AND lum<?', (DARK,))}
        if key == 'flat': return {r[0] for r in self.E.db.q('SELECT fid FROM vc_pet WHERE lum>=? AND lstd>=0 AND lstd<?', (DARK, FLAT))}
        if key == 'still': return {r[0] for r in self.E.db.q('SELECT fid FROM vc_pet WHERE mot>=0 AND mot<? AND lum>=? AND lstd>=?', (STILL, DARK, FLAT))}
        if key in ('petppl', 'petonly'):                                              # 🐾＋👤 有貓狗也有人／只有貓狗（V0.3.90）
            t = self.th(); return {r[0] for r in self.E.db.q(f"SELECT fid FROM vc_pet WHERE (dog>=? OR cat>=?) AND COALESCE(nopet,0)=0 AND {'face>0' if key == 'petppl' else 'face=0'}", (t, t))}
        if key == 'many': return {r[0] for r in self.E.db.q('SELECT fid FROM vc_pet WHERE face>=3')}          # 👥 3 個人以上（V0.3.75）
        S = next((x[2] for x in SCENES if x[0] == key), None)
        if not S: return set()
        return {r[0] for r in self.E.db.q('SELECT fid, COALESCE(sc, top), sp FROM vc_pet WHERE COALESCE(sc, top)>=0') if r[1] in S and (r[2] is None or r[2] < 0 or r[2] >= SCENE_P)}

    def scene_counts(self, kind='video'):
        kind = 'photo' if kind == 'photo' else 'video'
        c = getattr(self, '_scc', {}).get(kind)
        if c and time.time() - c[0] < 15: return c[1]                               # 15 秒內用算好的（找的時候畫面 3 秒問一次）（V0.3.93）
        r = self._scene_counts(kind); self.__dict__.setdefault('_scc', {})[kind] = (time.time(), r); return r

    def _scene_counts(self, kind):
        """🔎 還沒分類的影片，各種內容大約幾部（V0.3.73）."""
        R = self.E.db.q("SELECT COALESCE(p.sc, p.top), p.sp FROM vc_pet p JOIN files f ON f.id=p.fid LEFT JOIN vc_tag g ON g.fid=p.fid WHERE g.fid IS NULL AND f.state='' AND f.kind=? AND COALESCE(p.sc, p.top)>=0", (kind,))
        C = {}
        for top, sp in R:
            if sp is not None and 0 <= sp < SCENE_P: continue
            k = self.scene_of(top)
            if k: C[k] = C.get(k, 0) + 1
        out = [{'k': k, 'name': nm, 'n': C.get(k, 0)} for k, nm, S in SCENES if C.get(k)]
        mn = (self.E.db.one("SELECT COUNT(*) FROM vc_pet p JOIN files f ON f.id=p.fid LEFT JOIN vc_tag g ON g.fid=p.fid WHERE g.fid IS NULL AND f.state='' AND f.kind=? AND p.face>=3", (kind,)) or [0])[0]
        if mn: out.insert(0, {'k': 'many', 'name': '👥 3 個人以上（聚會、合照）', 'n': mn})
        t = self.th(); J2 = "FROM vc_pet p JOIN files f ON f.id=p.fid LEFT JOIN vc_tag g ON g.fid=p.fid WHERE g.fid IS NULL AND f.state='' AND f.kind=? AND (p.dog>=? OR p.cat>=?) AND COALESCE(p.nopet,0)=0 AND "
        po = (self.E.db.one(f"SELECT COUNT(*) {J2} p.face=0", (kind, t, t)) or [0])[0]
        pp = (self.E.db.one(f"SELECT COUNT(*) {J2} p.face>0", (kind, t, t)) or [0])[0]
        if po: out.insert(0, {'k': 'petonly', 'name': '🐾 只有貓狗（沒拍到人）', 'n': po})
        if pp: out.insert(0, {'k': 'petppl', 'name': '🐾👤 有貓狗、也有人', 'n': pp})
        J = "FROM vc_pet p JOIN files f ON f.id=p.fid LEFT JOIN vc_tag g ON g.fid=p.fid WHERE g.fid IS NULL AND f.state='' AND f.kind=? AND "
        dk = (self.E.db.one(f"SELECT COUNT(*) {J} p.lum>=0 AND p.lum<?", (kind, DARK)) or [0])[0]
        fl = (self.E.db.one(f"SELECT COUNT(*) {J} p.lum>=? AND p.lstd>=0 AND p.lstd<?", (kind, DARK, FLAT)) or [0])[0]
        st = (self.E.db.one(f"SELECT COUNT(*) {J} p.mot>=0 AND p.mot<? AND p.lum>=? AND p.lstd>=?", (kind, STILL, DARK, FLAT)) or [0])[0]
        if st: out.append({'k': 'still', 'name': '🧱 畫面幾乎沒動（放著錄的）', 'n': st})
        if fl: out.append({'k': 'flat', 'name': '⬜ 畫面幾乎沒東西（牆、天花板、鏡頭蓋住）', 'n': fl})
        if dk: out.append({'k': 'dark', 'name': '🌑 很暗／全黑（可能是口袋誤錄）', 'n': dk})
        try:                                                                         # 💡 你以前這種內容大多分到哪（V0.3.91）
            WS = self.E.vc.word_stats(); C = {c['id']: c['name'] for c in self.E.vc.cats()}
            TK = {'dark': '🔎很暗', 'flat': '🔎畫面沒東西', 'still': '🔎畫面沒動', 'petppl': '🐾貓狗＋人', 'petonly': '🐾只有貓狗', 'many': '🔎3人以上'}
            for k, nm, S in SCENES: TK[k] = '🔎' + nm.split(' ', 1)[-1].split('／')[0]
            for x in out:
                D = WS.get(TK.get(x['k'], ''))
                if not D: continue
                cat, n = max(D.items(), key=lambda y: y[1]); tot = sum(D.values())
                if n >= 3 and n / tot >= 0.7 and cat in C: x['lc'] = cat; x['ln'] = C[cat]; x['lh'] = f'{n}／{tot}'
        except Exception: pass
        return out

    def pet_ids(self, kind='any'):
        if str(kind).startswith('s_'): return self.scene_ids(kind[2:])
        if kind == 'face': return {r[0] for r in self.E.db.q('SELECT fid FROM vc_pet WHERE face>0')}
        if kind == 'noface': return {r[0] for r in self.E.db.q('SELECT fid FROM vc_pet WHERE face=0')}
        t = self.th(); col = {'dog': 'dog>=?', 'cat': 'cat>=?'}.get(kind, '(dog>=? OR cat>=?)')
        return {r[0] for r in self.E.db.q(f'SELECT fid FROM vc_pet WHERE {col} AND COALESCE(nopet,0)=0', (t, t) if kind not in ('dog', 'cat') else (t,))}   # 按過「不是貓狗」的不算（V0.6.00）

    def nopet(self, ids, on=True):
        """🐾 你看過、不是貓狗 → 之後「有貓狗」的清單不再出現（V0.6.00）."""
        ids = [int(x) for x in ids or []]
        if not ids: return 0
        self.E.db.xm('UPDATE vc_pet SET nopet=? WHERE fid=?', [(1 if on else None, f) for f in ids]); self._scc = {}
        try: self.E.vc._pm = None
        except Exception: pass
        return len(ids)

    def start(self, limit=0, kind='video', build=True, only=None):
        if self.st.get('run'): return False
        self.st.clear(); self.st.update(run=True, n=0, total=0, found=0, cancel=False, msg='準備中…', err='', kind=kind)
        threading.Thread(target=self._job, args=(limit, kind, build, only), name='PetJob', daemon=True).start(); return True

    def _job(self, limit=0, kind='video', build=True, only=None):
        S = self.st; E = self.E; tk = None
        try:
            tk = E.task('op', '🐾 找貓狗、人臉（' + ('照片' if kind == 'photo' else '影片') + '）')
            ok, err = self.fetch(); pet_ok = ok; face_ok = E.cfg.get('pet_face') is True   # V0.6.00 人臉太吃效能：要自己打開才找
            if not ok: S['err'] = '🐾 下載不了辨識模型（貓狗先跳過，人臉照做）：' + err + f'\n可以自己下載 {MODEL} 放到 {self.adir()}'
            L = self.todo(kind); NB = set()
            if build and kind != 'photo' and E.cfg.get('pet_build') is not False:          # 🎞 16 格還沒做好的：順便先做 16 格再看（做好的審片也用得到）（V0.3.81）
                NB = set(getattr(self, 'nr_list', [])); L = L + list(getattr(self, 'nr_list', [])); self.notready = 0
            if only: OS = set(only); L = [f for f in L if f in OS]                     # 📋 只看目前這份清單（V0.4.20）
            if limit: L = L[:limit]
            S['total'] = len(L); S['msg'] = f'🐾 看內容：0／{len(L):,}'; S['faces'] = 0
            E.log.w(f"🐾 開始找貓狗／人臉：{len(L):,} {'張照片' if kind == 'photo' else '部（16 格做好的才看）'}")
            th = self.th(); t0 = time.time()
            if not limit and build and not only: E.cfg.set('pet_resume', True); E.cfg.set('pet_resume_k', kind)
            for i in range(0, len(L), BATCH):
                if S.get('cancel') or E.stop_all or not E.alive(): break
                if time.time() - getattr(E.vc, 'last_view', 0) < 8: time.sleep(3)      # 你在審片時放慢一點（不會完全停）
                w0 = time.time()
                while E.alive() and not S.get('cancel') and ('vgrid' in getattr(E, 'bg_auto', ()) or (not build and E.quiet_now())) and time.time() - w0 < 3600:   # ⚖ 電腦太忙／🌙 指定時段（背景自動看）先等（V0.4.13）
                    S['msg'] = '⏸ 電腦太忙（或在你設定不跑背景的時段），先等一下…'; time.sleep(5)
                part = L[i:i + BATCH]; now = time.time()
                for j, fid in enumerate(part):                                       # 先把這批還沒有 16 格的做好
                    if fid not in NB: continue
                    if S.get('cancel') or E.stop_all or not E.alive(): break
                    if time.time() - getattr(E.vc, 'last_view', 0) < 8: time.sleep(1.5)
                    S['msg'] = f"🎞 先做 16 格（{i + j + 1:,}／{len(L):,}）…，🐾 貓狗 {S['found']:,}、👤 有人 {S['faces']:,}"
                    try: E.vc.grid(fid, build=True)
                    except Exception: pass
                E.db.xm('INSERT OR IGNORE INTO vc_pet(fid,dog,cat,top,t,face,farea) VALUES(?,-1,-1,-1,?,-1,-1)', [(f, now) for f in part])
                if True:                                                             # 🌑 亮度不用 Windows ML，貓狗跑不起來也照算（V0.3.79）
                    blob = bytearray(); idx = []; LU = {}; CI = []
                    for fid in part:
                        cl = []; cs = self.crops(fid, cells_out=cl, with_gray=face_ok); cl += [''] * (len(cs) - len(cl))
                        for c, ce in zip(cs, cl):
                            blob += c; idx.append(fid); CI.append(ce); m, sd = lum_of(c); a = LU.setdefault(fid, [-1.0, -1.0, -1.0]); a[0] = max(a[0], m); a[1] = max(a[1], sd)
                        if cs: LU[fid][2] = mot_of(cs)
                    if LU: E.db.xm('UPDATE vc_pet SET lum=?, lstd=?, mot=? WHERE fid=?', [(a[0], a[1], a[2], f) for f, a in LU.items()])
                    if idx and pet_ok:
                        R, er = self._run_ps(bytes(blob))
                        if R is None:
                            pet_ok = False; S['err'] = (S.get('err', '') + '\n🐾 Windows ML（貓狗）跑不起來：' + er).strip(); E.log.w(f'🐾 找貓狗失敗：{er}')
                        else:
                            if er: E.log.w(f'🐾 找貓狗（部分）：{er}')
                            agg = {}
                            for fid, r, ce in zip(idx, R, CI):
                                a = agg.setdefault(fid, [0.0, 0.0, -1, 0.0, -1, -1.0, ''])
                                a[0] = max(a[0], r[0]); a[1] = max(a[1], r[1])
                                if max(r[0], r[1]) >= a[3] or a[2] < 0: a[2] = r[2]; a[3] = max(r[0], r[1]); a[6] = ce     # 最像貓狗的那一格（V0.3.94）
                                tp = r[3] if len(r) > 3 else 0.0
                                if tp > a[5]: a[4] = r[2]; a[5] = tp                     # 🔎 內容：4 格裡最有把握的那一類（V0.3.73）
                            E.db.xm('UPDATE vc_pet SET dog=?, cat=?, top=?, t=?, sc=?, sp=?, pc=? WHERE fid=?', [(a[0], a[1], a[2], now, a[4], a[5], a[6] or None, f) for f, a in agg.items()])
                            S['found'] += sum(1 for a in agg.values() if a[0] >= th or a[1] >= th)
                if face_ok:
                    blob = bytearray(); idx = []
                    for fid in part:
                        for c in self.crops(fid, gray=True): blob += c; idx.append(fid)
                    if idx:
                        R, er = self._run_face(bytes(blob))
                        if R is None:
                            face_ok = False; S['err'] = (S.get('err', '') + '\n👤 人臉偵測跑不起來：' + er).strip(); E.log.w(f'👤 人臉偵測失敗：{er}')
                        else:
                            if er: E.log.w(f'👤 人臉偵測（部分）：{er}')
                            agg = {}
                            for fid, r in zip(idx, R):
                                a = agg.setdefault(fid, [0, 0.0]); a[0] = max(a[0], r[0]); a[1] = max(a[1], r[1])
                            E.db.xm('UPDATE vc_pet SET face=?, farea=? WHERE fid=?', [(a[0], a[1], f) for f, a in agg.items()])
                            S['faces'] += sum(1 for a in agg.values() if a[0] > 0)
                self._gc = {}                                                        # 這批沒用到的灰階丟掉
                S['n'] = min(len(L), i + len(part)); el = time.time() - t0; left = (len(L) - S['n']) * el / max(1, S['n'])
                eta = '' if S['n'] < BATCH * 2 or S['n'] >= len(L) else (f"，約剩 {left / 3600:.1f} 小時" if left >= 5400 else f"，約剩 {max(1, round(left / 60))} 分")   # ⏱ 剩多久（V0.3.76）
                S['msg'] = f"🐾 看內容：{S['n']:,}／{len(L):,}，🐾 貓狗 {S['found']:,}、👤 有人 {S['faces']:,}{eta}"
                if tk: tk['pct'] = round(S['n'] * 100 / max(1, len(L)), 1); tk['msg'] = S['msg']
            if not S.get('cancel') and not limit and not only: self._lum_fill(S)
            S['msg'] = (f"⏹ 停了：看了 {S['n']:,} {'張' if kind == 'photo' else '部'}" if S.get('cancel') else f"✔ 看完 {S['n']:,} {'張' if kind == 'photo' else '部'}") + f"：🐾 有貓狗 {S['found']:,}、👤 有人 {S['faces']:,}"
            if pet_ok and not S.get('cancel') and not limit and not only and kind != 'photo' and E.cfg.get('pet_auto') is None:   # 第一次全部看完：之後新的影片自動看（可以關）（V0.4.09）
                E.cfg.set('pet_auto', True); S['msg'] += '\n🔁 之後新的影片會自動看（下面「背景自動看新的」可以關掉）'
            nr = getattr(self, 'notready', 0) if kind != 'photo' else 0
            if nr and not S.get('cancel'): S['msg'] += f"\n⏳ 還有 {nr:,} 部 16 格還沒做好，先跳過" + ('（背景做好後會自動看）' if E.cfg.get('pet_auto') else '：打開下面「背景自動看新的」，做好後會自動看')
            if not pet_ok and not face_ok: S['msg'] = '❌ 貓狗、人臉都跑不起來（🌑 很暗／⬜ 沒東西的還是有找）'; self.fail_t = time.time()   # 背景自動看 1 天內不再重試
            E.log.w('🐾 ' + S['msg'])
        except Exception as ex:
            S['err'] = f'{type(ex).__name__}: {ex}'; S['msg'] = '❌ 出錯了'; E.log.err('🐾 找貓狗')
        finally:
            S['run'] = False
            try:
                if E.alive() and not limit and not only and build: E.cfg.set('pet_resume', False)            # 看完／按停／出錯：下次不用接著看（關程式、更新時不改）
            except Exception: pass
            if tk: E.done(tk, 'fail' if S.get('err') else ('stop' if S.get('cancel') else 'done'), S.get('msg', ''))

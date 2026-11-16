# VideoSift - one-click build + install (same pattern as TikLive Monitor)
# Builds the launcher EXE (onedir), runs a self-test with real test videos, installs to Desktop\VideoSift, downloads FFmpeg 7.1.1, creates a shortcut.
param(
    [string]$InstallDir = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'VideoSift'),
    [switch]$SelfTest,
    [switch]$NoStart
)
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
function Rest($a) { if ($a.Count -gt 1) { return $a[1..($a.Count-1)] } else { return @() } }
$kit = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$buildDir = Join-Path $kit 'build'
$appSrc = Join-Path $kit 'app'
$icon = Join-Path $kit 'VideoSift.ico'
function Step($t) { Write-Host ''; Write-Host "== $t" -ForegroundColor Cyan }

Step '[1/7] Python'
function Get-Py {
    foreach ($c in @(@('py','-3.12'),@('py','-3.11'),@('py','-3.13'),@('py','-3.10'),@('python'))) {
        try {
            $ra = Rest $c
            $v = (& $c[0] @ra -c "import sys;print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null)
            if ($v -match '^3\.(10|11|12|13)$') { return ,$c }
        } catch {}
    }
    $cand = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
    if (Test-Path $cand) { return ,@($cand) }
    return $null
}
$py = Get-Py
if (-not $py) {
    Write-Host 'Python 3.10-3.13 not found, installing Python 3.11.9 (per-user)...' -ForegroundColor Yellow
    $inst = Join-Path $env:TEMP 'python-3.11.9-amd64.exe'
    Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile $inst -UseBasicParsing
    Start-Process -FilePath $inst -ArgumentList '/quiet InstallAllUsers=0 PrependPath=0 Include_test=0' -Wait
    $py = Get-Py
    if (-not $py) { throw 'Python install finished but Python was not found.' }
}
Write-Host ('Using: ' + ($py -join ' ')) -ForegroundColor Green

Step '[2/7] Build environment + FFmpeg 7.1.1'
$envDir = Join-Path $env:LOCALAPPDATA 'VideoSiftBuilder\launcher-v1'
$venvPy = Join-Path $envDir '.venv\Scripts\python.exe'
New-Item -ItemType Directory -Force -Path $envDir | Out-Null
if (-not (Test-Path $venvPy)) {
    $ra = Rest $py
    & $py[0] @ra -m venv (Join-Path $envDir '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
}
& $venvPy -m pip install --disable-pip-version-check -q --upgrade pip
& $venvPy -m pip install --disable-pip-version-check -q "PySide6>=6.8,<7" pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'package install failed' }
# FFmpeg 7.1.1 (works with NVENC on NVIDIA drivers 531+; newer FFmpeg 8/9 needs very new drivers)
$ffCache = Join-Path $envDir 'ffmpeg711'
if (-not (Test-Path (Join-Path $ffCache 'ffmpeg.exe'))) {
    Write-Host 'Downloading FFmpeg 7.1.1 (about 90 MB)...' -ForegroundColor Yellow
    $zip = Join-Path $envDir 'ffmpeg711.zip'; $ex = Join-Path $envDir 'ffmpeg711_x'
    Invoke-WebRequest -Uri 'https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-essentials_build.zip' -OutFile $zip -UseBasicParsing
    if (Test-Path $ex) { Remove-Item $ex -Recurse -Force }
    Expand-Archive $zip $ex -Force
    New-Item -ItemType Directory -Force -Path $ffCache | Out-Null
    foreach ($n in @('ffmpeg.exe','ffprobe.exe')) { Copy-Item (Get-ChildItem $ex -Filter $n -Recurse | Select-Object -First 1).FullName (Join-Path $ffCache $n) -Force }
    Remove-Item $zip, $ex -Recurse -Force -ErrorAction SilentlyContinue
}

Step '[3/7] Check program files'
# V0.2.26: quick check only (the old full self-test is optional: BUILD_AND_INSTALL.bat -SelfTest)
& $venvPy -c "import py_compile,sys,pathlib; [py_compile.compile(str(f), doraise=True) for f in pathlib.Path(sys.argv[1]).glob('*.py')]; print('all program files OK')" $appSrc
if ($LASTEXITCODE -ne 0) { throw 'Program files are broken (compile failed) - nothing was installed.' }
if ($SelfTest) {
    & $venvPy (Join-Path $buildDir 'selftest.py') $appSrc $ffCache
    if ($LASTEXITCODE -ne 0) { Write-Host 'SELFTEST: some checks did not pass (continuing anyway).' -ForegroundColor Yellow }
}

Step '[4/7] Build launcher EXE'
$work = Join-Path $envDir 'work'
if (Test-Path $work) { Remove-Item $work -Recurse -Force }
New-Item -ItemType Directory -Force -Path $work | Out-Null
& $venvPy -m PyInstaller --noconfirm --clean --onedir --windowed --name VideoSift --icon $icon `
    --paths $buildDir --distpath (Join-Path $work 'dist') --workpath (Join-Path $work 'build') --specpath $work `
    --collect-submodules PySide6.QtMultimedia --collect-submodules PySide6.QtMultimediaWidgets `
    --hidden-import _deps (Join-Path $buildDir 'launcher.py')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
$dist = Join-Path $work 'dist\VideoSift'
if (-not (Test-Path (Join-Path $dist 'VideoSift.exe'))) { throw 'EXE was not created' }

Step ('[5/7] Install to ' + $InstallDir)
if (Get-Process -Name 'VideoSift' -ErrorAction SilentlyContinue) {
    throw 'VideoSift is running. Exit it from the tray icon (right-click -> 結束), then run this again.'
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
foreach ($d in @('_internal')) { $t = Join-Path $InstallDir $d; if (Test-Path $t) { Remove-Item $t -Recurse -Force } }
Copy-Item (Join-Path $dist '*') $InstallDir -Recurse -Force
$appDst = Join-Path $InstallDir 'app'
if (Test-Path $appDst) {
    $bk = Join-Path $InstallDir ('app_backup\' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_before_install')
    New-Item -ItemType Directory -Force -Path $bk | Out-Null
    Copy-Item (Join-Path $appDst '*') $bk -Recurse -Force
    Remove-Item $appDst -Recurse -Force
}
Copy-Item $appSrc $appDst -Recurse -Force
Get-ChildItem $appDst -Directory -Filter '__pycache__' -Recurse | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item $icon $InstallDir -Force
foreach ($d in @('UPDATE','LOG','Data')) { New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir $d) | Out-Null }

Step '[6/7] FFmpeg'
foreach ($n in @('ffmpeg.exe','ffprobe.exe')) {
    $dst = Join-Path $InstallDir $n
    if (-not (Test-Path $dst)) { Copy-Item (Join-Path $ffCache $n) $dst -Force }
}
Write-Host 'FFmpeg ready (to use another FFmpeg for the graphics card, put it in <install>\ffmpeg_gpu\ffmpeg.exe)' -ForegroundColor Green

Step '[7/7] Desktop shortcut'
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'VideoSift.lnk'
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnk); $sc.TargetPath = (Join-Path $InstallDir 'VideoSift.exe'); $sc.WorkingDirectory = $InstallDir; $sc.IconLocation = (Join-Path $InstallDir 'VideoSift.ico'); $sc.Save()

Write-Host ''
Write-Host ('Installed: ' + $InstallDir) -ForegroundColor Green
if (-not $NoStart) {
    Write-Host 'Starting VideoSift... it looks for drives that carry VideoSift data (X:\VideoSIFT\.vsdata) and connects them automatically.' -ForegroundColor Green
    Start-Process -FilePath (Join-Path $InstallDir 'VideoSift.exe') -WorkingDirectory $InstallDir
}
Write-Host 'Start it from the desktop shortcut "VideoSift". Updates: put vX.Y.Z_Update.zip into the UPDATE folder and start it again.' -ForegroundColor Green

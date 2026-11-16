"""🔌 USB 硬碟自動救回（V0.1.91）— 外接硬碟（USB）在大量讀寫時斷線、重插也不行、要重開機才回來時：
自動把「那顆硬碟接的 USB 裝置 → USB 集線器 → USB 控制器」一層一層重新啟動（軟體斷電重開那個連接埠），不用重開機。

做法：
① 平常（硬碟在線上）每 30 分鐘記下每個磁碟代號接在哪一條 USB 線路上（Data\\usb_map.json，不用系統管理員）。
② 第一次按「設定」時問一次系統管理員權限：建立一個 Windows 排程工作 VideoSift_USBReset（之後重啟 USB 不用再問），
   順便關掉 USB 省電（選擇性暫停、「允許電腦關閉這個裝置以節省電源」）和硬碟閒置關閉 —— 這些是外接硬碟斷線最常見的原因。
③ 硬碟離線 45 秒還沒回來 → 寫一個要求檔、叫排程工作做：先重啟 USB 裝置，不行再重啟集線器，再不行重啟 USB 控制器
   （同一個控制器上的其他 USB 裝置會斷線幾秒）。每顆硬碟 1 小時最多 3 次，全部記在 LOG。
只用標準函式庫；Windows 以外什麼都不做。
"""
import os, json, time, threading, subprocess
from pathlib import Path

IS_WIN = os.name == 'nt'
NO_WINDOW = 0x08000000 if IS_WIN else 0
TASK = 'VideoSift_USBReset'

MAP_PS1 = r'''$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
# V0.1.93：不用 Get-Volume／Get-Partition（有一顆硬碟卡住時它們會一起卡住），改用 WMI 的對應表
$out = @{}
$disks = @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 20)
$l2p = @(Get-CimInstance Win32_LogicalDiskToPartition -OperationTimeoutSec 20)
$d2p = @(Get-CimInstance Win32_DiskDriveToDiskPartition -OperationTimeoutSec 20)
foreach ($x in $l2p) {
  $L = ([string]$x.Dependent.DeviceID).TrimEnd(':')
  $part = [string]$x.Antecedent.DeviceID
  $dd = [string](($d2p | Where-Object { [string]$_.Dependent.DeviceID -eq $part } | Select-Object -First 1).Antecedent.DeviceID)
  $d = $disks | Where-Object { [string]$_.DeviceID -eq $dd } | Select-Object -First 1
  if (-not $d -or -not $L) { continue }
  $chain = @(); $cur = [string]$d.PNPDeviceID
  for ($i = 0; $i -lt 10 -and $cur; $i++) {
    $dev = Get-PnpDevice -InstanceId $cur
    $chain += @{ id = $cur; cls = [string]$dev.Class; name = [string]$dev.FriendlyName }
    if ($cur -like 'PCI\*' -or $cur -like 'ACPI\*') { break }
    $cur = [string](Get-PnpDeviceProperty -InstanceId $cur -KeyName DEVPKEY_Device_Parent).Data
  }
  $out[$L] = @{ bus = [string]$d.InterfaceType; model = [string]$d.Model; disk = [int]$d.Index; chain = $chain }
}
$out | ConvertTo-Json -Depth 6 -Compress
'''

RESET_PS1 = r'''param([string]$req)
$ErrorActionPreference = 'SilentlyContinue'
function Log($m) { Add-Content -LiteralPath $script:log -Value ("[" + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + "] " + $m) -Encoding UTF8 }
$script:log = Join-Path (Split-Path -Parent $req) 'usb_reset_log.txt'
$r = Get-Content -LiteralPath $req -Raw -Encoding UTF8 | ConvertFrom-Json
$letter = [string]$r.letter; $root = $letter + ':\'
Log ("request: drive " + $letter + " step " + $r.step + " targets " + (($r.targets | ForEach-Object { $_ }) -join ' | '))
foreach ($id in $r.targets) {
  if (Test-Path -LiteralPath $root) { Log ("drive " + $letter + " is back"); break }
  Log ("restart-device " + $id)
  $o = & pnputil.exe /restart-device "$id" 2>&1 | Out-String
  Log ("  pnputil: " + ($o -replace '\s+', ' ').Trim())
  if ($LASTEXITCODE -ne 0) {
    Log ("  pnputil failed (" + $LASTEXITCODE + "), disable/enable instead")
    Disable-PnpDevice -InstanceId $id -Confirm:$false
    Start-Sleep -Seconds 3
    Enable-PnpDevice -InstanceId $id -Confirm:$false
  }
  for ($k = 0; $k -lt 25; $k++) { if (Test-Path -LiteralPath $root) { break }; Start-Sleep -Seconds 1 }
}
$ok = Test-Path -LiteralPath $root
Log ("result: drive " + $letter + " " + ($(if ($ok) { 'OK' } else { 'still missing' })))
Set-Content -LiteralPath ($req + '.done') -Value ($(if ($ok) { 'ok' } else { 'fail' })) -Encoding ASCII
'''

SETUP_PS1 = r'''param([string]$data)
$ErrorActionPreference = 'Continue'
$log = Join-Path $data 'usb_reset_log.txt'
function Log($m) { Add-Content -LiteralPath $log -Value ("[" + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + "] setup: " + $m) -Encoding UTF8 }
try {
  $ps = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
  $arg = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $data 'usb_reset.ps1') + '" -req "' + (Join-Path $data 'usb_reset_req.json') + '"'
  $act = New-ScheduledTaskAction -Execute $ps -Argument $arg
  $pr = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -RunLevel Highest -LogonType Interactive
  $st = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
  Register-ScheduledTask -TaskName 'VideoSift_USBReset' -Action $act -Principal $pr -Settings $st -Force | Out-Null
  Log 'scheduled task VideoSift_USBReset registered'
} catch { Log ('task failed: ' + $_) }
try {
  & powercfg.exe /setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
  & powercfg.exe /setdcvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
  & powercfg.exe /change disk-timeout-ac 0
  & powercfg.exe /setactive SCHEME_CURRENT
  Log 'power: USB selective suspend off, disk never sleeps (AC)'
} catch { Log ('powercfg failed: ' + $_) }
try {
  $n = 0
  Get-CimInstance -Namespace root\wmi -ClassName MSPower_DeviceEnable | Where-Object { $_.InstanceName -like 'USB\*' -and $_.Enable } | ForEach-Object {
    Set-CimInstance -InputObject $_ -Property @{ Enable = $false }; $n++ }
  Log ('USB devices "allow computer to turn off": turned off for ' + $n)
} catch { Log ('MSPower failed: ' + $_) }
try {
  $n = 0
  Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Enum\USB' | ForEach-Object { Get-ChildItem $_.PSPath } | ForEach-Object {
    $dp = Join-Path $_.PSPath 'Device Parameters'
    if (Test-Path $dp) {
      $p = Get-ItemProperty $dp
      if ($p.PSObject.Properties.Name -contains 'EnhancedPowerManagementEnabled') { Set-ItemProperty $dp -Name EnhancedPowerManagementEnabled -Value 0; $n++ }
      if ($p.PSObject.Properties.Name -contains 'SelectiveSuspendEnabled') { Set-ItemProperty $dp -Name SelectiveSuspendEnabled -Value 0 }
    }
  }
  Log ('USB EnhancedPowerManagement off for ' + $n + ' devices (takes effect after replug/restart)')
} catch { Log ('registry failed: ' + $_) }
Set-Content -LiteralPath (Join-Path $data 'usb_setup.done') -Value (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') -Encoding ASCII
'''


def _ps():
    p = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    return p if os.path.isfile(p) else 'powershell'


class UsbGuard:
    def __init__(self, E, adopt=None):
        self.E = E; self.alive = True; self.map = getattr(adopt, 'map', None) or {}; self.t_map = getattr(adopt, 't_map', 0)
        self.tries = getattr(adopt, 'tries', None) or {}; self.busy = getattr(adopt, 'busy', None) or set(); self.last = getattr(adopt, 'last', None) or []
        self.pending = getattr(adopt, 'pending', None) or {}; self.lock = threading.Lock()
        if adopt is not None:
            try: adopt.alive = False
            except Exception: pass
        self.d = Path(E.data)
        try:
            if not self.map and (self.d / 'usb_map.json').exists(): self.map = json.loads((self.d / 'usb_map.json').read_text(encoding='utf-8'))
        except Exception: self.map = {}
        if IS_WIN: threading.Thread(target=self._loop, name='VsUsbGuard', daemon=True).start()

    def cfg(self):
        c = self.E.cfg.get('usb_guard')
        return dict({'on': True, 'wait': 45, 'max_hour': 3}, **(c if isinstance(c, dict) else {}))

    def note(self, m):
        self.last = (self.last + [{'t': time.time(), 'm': m}])[-50:]
        try: self.E.log.w('🔌 ' + m)
        except Exception: pass

    # ---------------------------------------------------------------- 記下每個磁碟代號接在哪
    def refresh_map(self):
        if not IS_WIN: return {}
        try:
            mp = self.d / 'usb_map.ps1'; mp.write_text(MAP_PS1, encoding='utf-8-sig')
            p = subprocess.run([_ps(), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(mp)], capture_output=True, timeout=75, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
            txt = p.stdout.decode('utf-8', 'replace').strip()
            m = json.loads(txt) if txt.startswith('{') else {}
        except Exception as ex:
            self.t_map = time.time()                                            # 失敗也等 30 分鐘再試（不要一直開 PowerShell）
            self.note(f'讀不到 USB 線路（{type(ex).__name__}），30 分鐘後再試；可以按「🔁 重新讀 USB 線路」'); return self.map
        if not m: self.t_map = time.time()
        if m:
            old = dict(self.map); old.update(m); self.map = old; self.t_map = time.time()       # 離線的那顆不會出現在新的清單裡：留著舊的記錄
            try: (self.d / 'usb_map.json').write_text(json.dumps(self.map, ensure_ascii=False, indent=1), encoding='utf-8')
            except Exception: pass
        return self.map

    def is_usb(self, letter):
        e = self.map.get(letter.upper()) or {}
        return str(e.get('bus') or '').upper() == 'USB' or any(str(x.get('id') or '').upper().startswith(('USB\\', 'USBSTOR\\', 'UASPSTOR\\')) for x in e.get('chain') or [])

    def targets(self, letter):
        """重啟的順序：USB 裝置 → 它上面的 USB 集線器 → USB 控制器（越後面影響越大）."""
        ch = (self.map.get(letter.upper()) or {}).get('chain') or []
        ids = [str(x.get('id') or '') for x in ch]
        dev = [i for i in ids if i.upper().startswith('USB\\VID_')][:1]
        hubs = [i for i in ids if i.upper().startswith('USB\\') and (i.upper().startswith('USB\\ROOT_HUB') or 'HUB' in str(next((x.get('name') for x in ch if x.get('id') == i), '')).upper()) and i not in dev][:1]
        ctl = [i for i in ids if i.upper().startswith('PCI\\')][:1]
        return [dev, hubs, ctl]

    # ---------------------------------------------------------------- 設定（問一次系統管理員）
    def installed(self):
        if not IS_WIN: return False
        try: return subprocess.run(['schtasks', '/query', '/tn', TASK], capture_output=True, timeout=20, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL).returncode == 0
        except Exception: return False

    def setup(self):
        if not IS_WIN: return {'ok': False, 'message': '只有 Windows 能用'}
        try:
            (self.d / 'usb_reset.ps1').write_text(RESET_PS1, encoding='utf-8-sig'); (self.d / 'usb_setup.ps1').write_text(SETUP_PS1, encoding='utf-8-sig')
            try: (self.d / 'usb_setup.done').unlink()
            except Exception: pass
            import ctypes
            args = subprocess.list2cmdline(['-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', str(self.d / 'usb_setup.ps1'), '-data', str(self.d)])
            r = ctypes.windll.shell32.ShellExecuteW(None, 'runas', _ps(), args, str(self.d), 0)
            if int(r) <= 32: return {'ok': False, 'message': f'沒有設定（你在「使用者帳戶控制」按了否？代碼 {int(r)}）'}
        except Exception as ex: return {'ok': False, 'message': f'設定失敗：{ex}'}
        self.note('開始設定 USB 硬碟自動救回（排程工作＋關掉 USB 省電），結果看 Data\\usb_reset_log.txt')
        threading.Thread(target=self.refresh_map, daemon=True).start()
        return {'ok': True, 'message': '設定中（Windows 問系統管理員權限按「是」）：建立自動救回的排程工作、關掉 USB 省電和硬碟閒置關閉'}

    # ---------------------------------------------------------------- 硬碟離線 → 救回
    def on_offline(self, root):
        """core.root_offline() 發現影片庫不見時叫這裡（只記下來，_loop 等一下再處理）."""
        if not IS_WIN: return
        L = os.path.splitdrive(str(root))[0].rstrip(':').upper()
        if len(L) == 1 and L not in self.pending: self.pending[L] = time.time()

    def rescue(self, L, step=None):
        c = self.cfg(); now = time.time()
        T = [t for t in self.tries.get(L, []) if now - t < 3600]
        if len(T) >= int(c.get('max_hour') or 3): return {'ok': False, 'message': f'{L}: 1 小時內已經救過 {len(T)} 次，先不再試（請檢查線材／電源）'}
        if not (self.map.get(L) or {}).get('chain'): return {'ok': False, 'message': f'{L}: 沒有記錄到它接在哪個 USB 上（硬碟在線上時才記得到），這次沒辦法自動救'}
        if not self.installed(): return {'ok': False, 'message': '還沒設定 USB 硬碟自動救回（到「⏯ 後台」按「🔌 設定」，問一次系統管理員）'}
        st = len(T) if step is None else int(step); tg = self.targets(L)
        ids = [i for grp in tg[min(st, 2):] for i in grp] or [i for grp in tg for i in grp]
        if not ids: return {'ok': False, 'message': f'{L}: 找不到可以重啟的 USB 裝置'}
        self.tries[L] = T + [now]
        req = self.d / 'usb_reset_req.json'
        try:
            for x in (req.with_name(req.name + '.done'),):
                try: x.unlink()
                except Exception: pass
            req.write_text(json.dumps({'letter': L, 'step': st, 'targets': ids, 't': now}, ensure_ascii=False), encoding='utf-8')
            rc = subprocess.run(['schtasks', '/run', '/tn', TASK], capture_output=True, timeout=30, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL).returncode
        except Exception as ex: return {'ok': False, 'message': f'{L}: 叫不動排程工作（{ex}）'}
        if rc != 0: return {'ok': False, 'message': f'{L}: 排程工作執行失敗（代碼 {rc}），請重新按「🔌 設定」'}
        names = [str(next((x.get('name') for x in (self.map.get(L) or {}).get('chain') or [] if x.get('id') == i), i)) for i in ids]
        self.note(f'{L}: 硬碟離線 → 自動重啟 USB（第 {len(T) + 1} 次）：' + ' → '.join(names))
        t0 = time.time()
        while time.time() - t0 < 150:
            if os.path.exists(L + ':\\'):
                self.note(f'✅ {L}: 硬碟救回來了（{time.time() - t0:.0f} 秒）'); return {'ok': True, 'message': f'{L}: 救回來了'}
            if req.with_name(req.name + '.done').exists() and time.time() - t0 > 5: break
            time.sleep(2)
        ok = os.path.exists(L + ':\\')
        self.note(f'{L}: 重啟 USB 之後' + ('回來了 ✅' if ok else '還是沒回來（下次會重啟更上層；都不行就要檢查線材／電源，或重開機）'))
        return {'ok': ok, 'message': f'{L}: ' + ('救回來了' if ok else '還沒回來')}

    def _loop(self):
        time.sleep(20)
        while self.alive:
            try:
                if time.time() - self.t_map > 1800: self.refresh_map()
                c = self.cfg()
                for L, t0 in list(self.pending.items()):
                    if os.path.exists(L + ':\\'): self.pending.pop(L, None); continue
                    if c.get('on') and time.time() - t0 >= int(c.get('wait') or 45) and L not in self.busy:
                        if not self.is_usb(L) and (self.map.get(L) or {}).get('chain'):
                            self.pending.pop(L, None); self.note(f'{L}: 不是 USB 硬碟，不自動重啟'); continue
                        self.busy.add(L)
                        try:
                            r = self.rescue(L)
                            if r['ok']: self.pending.pop(L, None)
                            else: self.note(r['message']); self.pending[L] = time.time() + 120          # 2 分鐘後再試下一層
                        finally: self.busy.discard(L)
            except Exception:
                try: self.E.log.err('🔌 USB 硬碟自動救回')
                except Exception: pass
            for _ in range(10):
                if not self.alive: return
                time.sleep(1)

    def status(self):
        c = self.cfg(); now = time.time()
        return {'on': bool(c.get('on')), 'win': IS_WIN, 'installed': self.installed() if IS_WIN else False, 'map': {k: {'bus': v.get('bus'), 'model': v.get('model'), 'n': len(v.get('chain') or [])} for k, v in self.map.items()},
                'pending': {k: now - v for k, v in self.pending.items()}, 'last': self.last[-15:], 'setup_done': (self.d / 'usb_setup.done').exists()}

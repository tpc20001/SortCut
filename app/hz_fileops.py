"""HotZone FM — single-folder operations for the explorer: list, new folder, rename, preview, properties,
Tailscale / network helpers, Windows scheduled task (start the engine at logon without a UAC prompt)."""
from __future__ import annotations

import json
import mimetypes
import os
import stat
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid

from hz_common import IS_WIN, ROOT, DATA_DIR, norm, unique_name, atomic_write_json, read_json
import hz_win as W

TEXT_EXT = {'txt', 'md', 'log', 'ini', 'cfg', 'conf', 'json', 'xml', 'csv', 'tsv', 'py', 'js', 'ts', 'css', 'html', 'htm', 'bat', 'cmd', 'ps1',
            'sh', 'yaml', 'yml', 'toml', 'srt', 'ass', 'vtt', 'nfo', 'c', 'cpp', 'h', 'java', 'cs', 'go', 'rs', 'sql', 'reg', 'lrc', 'm3u'}
IMG_EXT = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico', 'avif'}
VID_EXT = {'mp4', 'webm', 'm4v', 'mov', 'ogv', 'mkv'}
AUD_EXT = {'mp3', 'wav', 'ogg', 'm4a', 'aac', 'flac', 'opus'}


def ext_of(name):
    return name.rsplit('.', 1)[1].lower() if '.' in name[1:] else ''


def list_dir(path, show_hidden=False, hot_folders=()):
    p = norm(path)
    items = []; err = ''
    hot_roots = {(norm(h).lower() if IS_WIN else norm(h)) for h in hot_folders}
    try:
        with os.scandir(W.lp(p) if IS_WIN else p) as it:
            for e in it:
                try:
                    st = e.stat(follow_symlinks=False)
                    attrs = getattr(st, 'st_file_attributes', 0)
                    hidden = bool(attrs & 2) or (not IS_WIN and e.name.startswith('.'))
                    system = bool(attrs & 4)
                    if (hidden or system) and not show_hidden: continue
                    link = e.is_symlink() or bool(attrs & 0x400)
                    try: is_dir = e.is_dir()
                    except OSError: is_dir = False
                    full = os.path.join(p, e.name)
                    key = full.lower() if IS_WIN else full
                    items.append({'name': e.name, 'path': full, 'dir': is_dir, 'size': -1 if is_dir else st.st_size,
                                  'mtime': st.st_mtime, 'ctime': getattr(st, 'st_birthtime', st.st_ctime), 'hidden': hidden, 'system': system,
                                  'ro': bool(attrs & 1), 'link': link, 'ext': '' if is_dir else ext_of(e.name), 'hot': key in hot_roots})
                except OSError:
                    continue
    except FileNotFoundError:
        err = '找不到這個資料夾'
    except PermissionError:
        err = '沒有權限開啟這個資料夾'
    except OSError as e:
        err = e.strerror or str(e)
    parent = os.path.dirname(p.rstrip('\\/')) if p.rstrip('\\/') != p[:2] or not IS_WIN else ''
    if IS_WIN and re.fullmatch(r'[A-Za-z]:\\?', p): parent = ''
    if not IS_WIN and p == '/': parent = ''
    return {'path': p, 'parent': parent, 'items': items, 'error': err, 'crumbs': crumbs(p)}


def subdirs(path, show_hidden=False, hot_folders=()):
    """Folder names only (explorer tree), sorted like Explorer."""
    p = norm(path); out = []
    hot = {(norm(h).lower() if IS_WIN else norm(h)) for h in hot_folders}
    try:
        with os.scandir(W.lp(p) if IS_WIN else p) as it:
            for e in it:
                try:
                    if not e.is_dir(): continue
                    st = e.stat(follow_symlinks=False); a = getattr(st, 'st_file_attributes', 0)
                    hidden = bool(a & 6) or (not IS_WIN and e.name.startswith('.'))
                    if hidden and not show_hidden: continue
                    full = os.path.join(p, e.name)
                    out.append({'name': e.name, 'path': full, 'hot': (full.lower() if IS_WIN else full) in hot, 'link': bool(a & 0x400) or e.is_symlink()})
                except OSError:
                    continue
    except OSError as e:
        return {'path': p, 'dirs': [], 'error': e.strerror or str(e)}
    out.sort(key=lambda x: x['name'].lower())
    return {'path': p, 'dirs': out}


def crumbs(p):
    out = []
    if IS_WIN:
        parts = [x for x in p.split('\\') if x]
        acc = ''
        for i, x in enumerate(parts):
            acc = x + '\\' if i == 0 else os.path.join(acc, x)
            out.append({'name': x, 'path': acc})
    else:
        out.append({'name': '/', 'path': '/'})
        acc = ''
        for x in [x for x in p.split('/') if x]:
            acc += '/' + x; out.append({'name': x, 'path': acc})
    return out


def check_name(name):
    name = (name or '').strip()
    if not name or name in ('.', '..'): raise ValueError('名稱不能空白')
    if IS_WIN and re.search(r'[\\/:*?"<>|]', name): raise ValueError('名稱不能包含 \\ / : * ? " < > |')
    if '/' in name or '\0' in name: raise ValueError('名稱不能包含 /')
    return name


def mkdir(parent, name):
    p = os.path.join(norm(parent), check_name(name))
    if os.path.exists(p): raise FileExistsError('已經有同名的項目')
    os.makedirs(W.lp(p))
    return p


def newfile(parent, name):
    p = os.path.join(norm(parent), check_name(name))
    if os.path.exists(p): raise FileExistsError('已經有同名的項目')
    open(W.lp(p), 'xb').close()
    return p


RENAME_LOCK = threading.RLock()
PLAN_DIR = DATA_DIR / 'rename_plans'


def rename(path, new_name):
    p = norm(path); new = os.path.join(os.path.dirname(p), check_name(new_name))
    if p == new: return p
    with RENAME_LOCK:
        if IS_WIN and p.lower() == new.lower():                     # case-only change on Windows
            os.rename(W.lp(p), W.lp(new)); return new
        W.rename_noreplace(p, new)                                 # FileExistsError -> 已經有同名的項目
    return new


def _plan_path(tag):
    return PLAN_DIR / f'{tag}.json'


def _save_plan(tag, phase, rows):
    """phase 1 = moving originals to their temp names, 2 = moving temp names to the new names.
    Written durably (fsync) before each phase, so a power cut can always be undone exactly."""
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(_plan_path(tag), {'t': time.time(), 'pid': os.getpid(), 'phase': phase, 'items': rows}, durable=True)


def _drop_plan(tag):
    try: os.remove(_plan_path(tag))
    except OSError: pass


def _rollback(phase, rows):
    """Put every item of an interrupted batch back under its original name. Never overwrites.
    Returns the list of problems (empty = fully undone)."""
    problems = []
    if phase >= 2:                                                  # rows whose temp is gone reached the new name
        for orig, tmp, new in reversed(rows):
            if not os.path.lexists(W.lp(tmp)) and os.path.lexists(W.lp(new)):
                try: W.rename_noreplace(new, tmp)
                except OSError as e: problems.append(f'{new}：{e}')
    for orig, tmp, new in reversed(rows):                           # temp -> original
        if not os.path.lexists(W.lp(tmp)): continue
        dst = orig
        for _ in range(100):
            try: W.rename_noreplace(tmp, dst); break
            except FileExistsError:
                base, ext = os.path.splitext(orig); dst = unique_name(f'{base} (還原){ext}')
            except OSError as e:
                problems.append(f'{tmp}：{e}'); break
    return problems


def pending_plans():
    try: return sorted(PLAN_DIR.glob('*.json'))
    except OSError: return []


def recover_batch_rename(log=None):
    """A batch rename interrupted by a crash / power cut leaves files under .hzren_* names. Put them all back.
    Called at engine start and before every new batch. A plan is only removed once every item is back."""
    fixed = 0
    legacy = DATA_DIR / 'rename_plan.json'                          # v0.1.6 single plan file (phase unknown -> 1:
    if legacy.exists():                                             # only temp -> original, which is always safe)
        plan = read_json(legacy, None) or {}
        if not _rollback(1, plan.get('items') or []):
            try: legacy.unlink()
            except OSError: pass
    for pf in pending_plans():
        plan = read_json(pf, None)
        if not plan or not isinstance(plan.get('items'), list):
            if log: log.warn('rename', f'批次改名計畫檔讀不出來，保留給你檢查：{pf}')
            continue
        rows = plan['items']
        before = sum(1 for r in rows if os.path.lexists(W.lp(r[1])))
        problems = _rollback(int(plan.get('phase', 1)), rows)
        fixed += before
        if problems:
            if log: log.warn('rename', f'中斷的批次改名還有 {len(problems)} 個項目改不回去（可能被別的程式開著），下次再試：' + '；'.join(problems[:3]))
            continue
        try: os.remove(pf)
        except OSError: pass
    if log and fixed: log.warn('rename', f'上次批次改名被中斷，已把 {fixed} 個項目改回原名')
    return fixed


def batch_rename(items):
    """items = [[path, new_name], ...] -> [[old_path, new_path], ...] done.
    Two steps through unique temporary names (swaps a->b, b->a and case-only changes work), never overwrites,
    the plan is written to disk (fsync) before each step so a crash can be undone, any failure rolls everything back."""
    plan = []; srcs = set(); dsts = set()
    key = (lambda p: p.lower()) if IS_WIN else (lambda p: p)
    for path, name in items:
        p = norm(path); new = os.path.join(os.path.dirname(p), check_name(name))
        if p == new: continue
        if key(new) in dsts: raise ValueError(f'新名稱重複：{name}')
        if key(p) in srcs: raise ValueError(f'同一個項目出現兩次：{p}')
        plan.append((p, new)); srcs.add(key(p)); dsts.add(key(new))
    if not plan: return []
    for p, _ in plan:                                               # a folder and something inside it in one batch
        for q, _ in plan:
            if p != q and key(q).startswith(key(p).rstrip('\\/') + os.sep):
                raise ValueError(f'不能同時改名資料夾和它裡面的項目：{os.path.basename(p)}')
    with RENAME_LOCK:
        if pending_plans():
            recover_batch_rename()
            if pending_plans():
                raise OSError('上一次中斷的批次改名還沒完全改回原名（可能有檔案被別的程式開著），請先關掉那個程式再試；詳情在紀錄裡')
        for p, new in plan:
            if not os.path.lexists(W.lp(p)): raise FileNotFoundError(f'找不到：{p}')
            if os.path.lexists(W.lp(new)) and key(new) not in srcs: raise FileExistsError(f'已經有同名的項目：{os.path.basename(new)}')
        tag = time.strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:8]
        rows = [[p, os.path.join(os.path.dirname(p), f'.hzren_{tag[-8:]}_{i}'), new] for i, (p, new) in enumerate(plan)]
        _save_plan(tag, 1, rows)
        phase = 1
        try:
            for r in rows:
                W.rename_noreplace(r[0], r[1])
            _save_plan(tag, 2, rows); phase = 2
            for r in rows:
                W.rename_noreplace(r[1], r[2])
        except Exception as e:
            problems = _rollback(phase, rows)
            if problems:                                            # keep the plan: recovery runs at next start
                raise OSError(f'批次改名失敗（{e}），而且有 {len(problems)} 個項目沒能自動改回，下次啟動會再試：' + '；'.join(problems[:3]))
            _drop_plan(tag)
            raise OSError(f'批次改名失敗，全部已改回原名：{e}') from e
        _drop_plan(tag)
        return [[r[0], r[2]] for r in rows]


def preview(path, limit=96 * 1024):
    p = norm(path); e = ext_of(os.path.basename(p))
    st = os.stat(W.lp(p))
    if not stat.S_ISREG(st.st_mode) and not stat.S_ISDIR(st.st_mode): raise ValueError('不是一般檔案')   # devices, pipes
    out = {'path': p, 'size': st.st_size, 'mtime': st.st_mtime, 'ext': e}
    if e in IMG_EXT: out['kind'] = 'image'
    elif e in VID_EXT: out['kind'] = 'video'
    elif e in AUD_EXT: out['kind'] = 'audio'
    elif e == 'pdf': out['kind'] = 'pdf'
    elif e in TEXT_EXT or st.st_size < 4096:
        with open(W.lp(p), 'rb') as f: raw = f.read(limit)
        if b'\0' in raw[:4096] and not raw.startswith((b'\xff\xfe', b'\xfe\xff')):
            out['kind'] = 'binary'
        else:
            out['kind'] = 'text'; out['text'] = decode_text(raw); out['truncated'] = st.st_size > limit
    else:
        out['kind'] = 'binary'
    return out


def decode_text(raw):
    if raw.startswith(b'\xef\xbb\xbf'): return raw[3:].decode('utf-8', 'replace')
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')): return raw.decode('utf-16', 'replace')
    for enc in ('utf-8', 'cp950', 'gb18030', 'cp1252'):
        try: return raw.decode(enc)
        except UnicodeDecodeError:
            if enc == 'utf-8':
                try: return raw[:-3].decode('utf-8') if len(raw) > 3 else raw.decode('utf-8')   # a cut multi-byte char at the end
                except UnicodeDecodeError: pass
    return raw.decode('latin-1')


def props(path, index=None, hot=None):
    p = norm(path); st = os.stat(W.lp(p))
    attrs = getattr(st, 'st_file_attributes', 0)
    d = {'path': p, 'name': os.path.basename(p) or p, 'dir': os.path.isdir(p), 'size': st.st_size, 'mtime': st.st_mtime,
         'ctime': getattr(st, 'st_birthtime', st.st_ctime), 'atime': st.st_atime,
         'attrs': {'readonly': bool(attrs & 1), 'hidden': bool(attrs & 2), 'system': bool(attrs & 4), 'archive': bool(attrs & 0x20),
                   'compressed': bool(attrs & 0x800), 'sparse': bool(attrs & 0x200)}}
    if d['dir'] and index is not None:
        fs = index.folder_size(p)
        if fs: d['size'] = fs['size']; d['files'] = fs['files']; d['from_index'] = True
    if hot is not None:
        d['hot'] = hot.is_hot(p)
        if not d['dir']:
            try: d['layout'] = hot.file_layout(p)
            except Exception as e: d['layout'] = {'error': str(e)}
    mt, _ = mimetypes.guess_type(p); d['mime'] = mt or ''
    return d


# ============================================================================================ network
def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        return '127.0.0.1'


def tailscale_exe():
    exe = shutil.which('tailscale') or ''
    if IS_WIN:
        for c in (os.path.expandvars(r'%ProgramFiles%\Tailscale\tailscale.exe'), r'C:\Program Files\Tailscale\tailscale.exe',
                  r'C:\Program Files (x86)\Tailscale\tailscale.exe'):
            if os.path.isfile(c): exe = c; break
    return exe


def tailscale_run(args, timeout=8):
    exe = tailscale_exe()
    if not exe: return None, 'Tailscale 沒有安裝'
    try:
        r = subprocess.run([exe] + args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, creationflags=W.no_window_flags())
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except subprocess.TimeoutExpired as e:
        return None, (e.stdout or '') if isinstance(e.stdout, str) else ''
    except Exception as e:
        return -1, str(e)


_ts_cache = {'t': 0, 'v': {}}


def tailscale_info(port, force=False):
    if not force and time.time() - _ts_cache['t'] < 60: return _ts_cache['v']
    v = {'installed': bool(tailscale_exe()), 'ip': '', 'name': '', 'https': ''}
    rc, out = tailscale_run(['status', '--json'], 6)
    if rc == 0:
        try:
            j = json.loads(out[out.index('{'):]); me = j.get('Self') or {}
            ips = [x for x in (me.get('TailscaleIPs') or []) if '.' in str(x)]
            v['ip'] = ips[0] if ips else ''
            v['name'] = str(me.get('DNSName') or '').rstrip('.')
        except Exception:
            pass
        rc2, out2 = tailscale_run(['serve', 'status', '--json'], 6)
        if rc2 == 0 and v['name']:
            mine, used = _serve_parse(out2, port)
            if mine: v['https'] = mine
            v['https_used'] = used                                     # other programs' (e.g. TikLive's) https ports
    _ts_cache.update(t=time.time(), v=v)
    return v


def _serve_parse(out, port):
    """tailscale serve status --json -> (our https URL or '', {https port: target} of everything served).
    Only an entry that proxies to OUR port is ours (TikLive on the same PC has its own)."""
    try: j = json.loads(out[out.index('{'):])
    except Exception: return '', {}
    mine = ''; used = {}
    for hostport, web in (j.get('Web') or {}).items():
        host, _, hp = hostport.rpartition(':')
        for _path, hd in ((web or {}).get('Handlers') or {}).items():
            tgt = str((hd or {}).get('Proxy') or '')
            used[hp] = tgt
            if re.search(r'(?:127\.0\.0\.1|localhost):%d/?$' % int(port), tgt):
                mine = f'https://{host}/' if hp == '443' else f'https://{host}:{hp}/'
    return mine, used


def tailscale_serve(port):
    """Publish HotZone over Tailscale HTTPS WITHOUT taking an https port another program already uses (it replaced
    TikLive's https://<pc>.ts.net/). Tailscale serves https on 443, 8443 and 10000: the first free one is used."""
    rc0, st = tailscale_run(['serve', 'status', '--json'], 8)
    mine, used = _serve_parse(st, port) if rc0 == 0 else ('', {})
    if mine: return {'ok': True, 'out': '已經開啟：' + mine, 'enable_url': '', 'url': mine}
    free = next((p for p in ('443', '8443', '10000') if p not in used), None)
    if free is None: return {'ok': False, 'out': 'Tailscale 的三個 HTTPS 埠（443、8443、10000）都被別的程式用了', 'enable_url': ''}
    rc, out = tailscale_run(['serve', '--bg', f'--https={free}', str(port)], 40)
    _ts_cache['t'] = 0
    m = re.search(r'https://login\.tailscale\.com/\S+', out or '')
    return {'ok': rc == 0, 'out': (out or '')[-800:], 'enable_url': m.group(0) if m else ''}


# ============================================================================================ autostart (Windows)
TASK_NAME = 'HotZoneFM Engine'


def engine_command():
    """How to start the engine again: the frozen EXE, or pythonw + launcher.py from source."""
    rt = sys.modules.get('_hz_rt')
    cmd = getattr(rt, 'engine_cmd', None) if rt else None
    if cmd: return list(cmd)
    if getattr(sys, 'frozen', False): return [sys.executable, '--engine']
    py = sys.executable
    if IS_WIN and py.lower().endswith('python.exe') and os.path.exists(py[:-10] + 'pythonw.exe'): py = py[:-10] + 'pythonw.exe'
    return [py, str(ROOT / 'launcher.py'), '--engine']


def autostart_state():
    if not IS_WIN: return {'supported': False, 'on': False}
    try:
        r = subprocess.run(['schtasks', '/Query', '/TN', TASK_NAME], capture_output=True, text=True, errors='replace', timeout=8, creationflags=W.no_window_flags())
        return {'supported': True, 'on': r.returncode == 0}
    except Exception as e:
        return {'supported': True, 'on': False, 'error': str(e)}


def _task_xml(cmd):
    """Scheduled task definition. Created from XML (not /SC ONLOGON flags) so the Windows defaults that would hurt a
    file engine are turned off: 'only on AC power', 'stop when on battery', 'stop after 3 days', low priority."""
    from xml.sax.saxutils import escape
    user = (os.environ.get('USERDOMAIN', '') + '\\' + os.environ.get('USERNAME', '')).strip('\\')
    args = subprocess.list2cmdline([str(c) for c in cmd[1:]])                 # SortCut：G:\ 這種結尾是反斜線的路徑也要正確加引號
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>HotZone FM 背景引擎（熱處理、傳輸佇列、遠端連線）</Description></RegistrationInfo>
  <Triggers><LogonTrigger><Enabled>true</Enabled><UserId>{escape(user)}</UserId><Delay>PT15S</Delay></LogonTrigger></Triggers>
  <Principals><Principal id="Author"><UserId>{escape(user)}</UserId><LogonType>InteractiveToken</LogonType><RunLevel>HighestAvailable</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>5</Priority>
  </Settings>
  <Actions Context="Author"><Exec><Command>{escape(cmd[0])}</Command><Arguments>{escape(args)}</Arguments><WorkingDirectory>{escape(str(ROOT))}</WorkingDirectory></Exec></Actions>
</Task>
"""


def autostart_set(on):
    if not IS_WIN: raise RuntimeError('只有 Windows 支援')
    if on:
        xml_path = DATA_DIR / 'autostart_task.xml'
        with open(xml_path, 'w', encoding='utf-16') as f: f.write(_task_xml(engine_command()))
        args = ['schtasks', '/Create', '/TN', TASK_NAME, '/XML', str(xml_path), '/F']
    else:
        args = ['schtasks', '/Delete', '/TN', TASK_NAME, '/F']
    r = subprocess.run(args, capture_output=True, text=True, errors='replace', timeout=15, creationflags=W.no_window_flags())
    if r.returncode != 0: raise RuntimeError((r.stdout or '') + (r.stderr or ''))
    return autostart_state()

"""🧊 硬碟冷凍（V0.6.35）：搬硬碟時，那幾顆硬碟上的檔案「只能看、不能改」.

- SortCut（10 秒剪輯）、整理（FileCompare）、H265 三個分頁：檔案、資料夾都還在、看得到，
  但搬、刪、改名、歸檔、丟資源回收筒都先不行（會跳「🧊 X: 搬硬碟中」），等搬完、或按暫停／停止才解凍。
- 做法：把 os.remove／unlink／rename／replace／rmdir、shutil.move／rmtree 包一層：
  路徑在冷凍的硬碟上、而且不是搬硬碟自己的執行緒（名字 RSplit 開頭）→ 擋下來（PermissionError）。
- 沒有冷凍時完全不影響（直接呼叫原本的）。熱更新重載也只會包一次。沒有 Qt。
"""
import os
import shutil
import sys
import threading


def _reg():
    d = getattr(sys, '_vs_freeze', None)
    if not isinstance(d, dict):
        d = {'letters': set(), 'why': '', 'orig': {}, 'n': 0, 'last': ''}
        setattr(sys, '_vs_freeze', d)
    return d


def letters():
    return set(_reg()['letters'])


def active():
    return bool(_reg()['letters'])


def why():
    R = _reg()
    return R['why'] if R['letters'] else ''


def set_frozen(L, why_=''):
    R = _reg(); R['letters'] = {str(x)[:1].upper() for x in (L or []) if x}; R['why'] = str(why_ or '')
    _install()


def clear():
    R = _reg(); R['letters'] = set(); R['why'] = ''


def _drive(p):
    try: s = os.fspath(p)
    except Exception: return ''
    if isinstance(s, bytes):
        try: s = s.decode('utf-8', 'replace')
        except Exception: return ''
    s = str(s)
    if s.startswith('\\\\?\\'): s = s[4:]
    if len(s) >= 2 and s[1] == ':': return s[0].upper()
    if not os.path.isabs(s):
        try: s = os.path.abspath(s)
        except Exception: return ''
        if len(s) >= 2 and s[1] == ':': return s[0].upper()
    return ''


def allowed_thread():
    n = threading.current_thread().name or ''
    return n.startswith('RSplit')


def blocked(*paths):
    """冷凍中、不是搬硬碟自己 → 回傳擋下來的原因；可以做 → ''."""
    R = _reg(); L = R['letters']
    if not L or allowed_thread(): return ''
    for p in paths:
        X = _drive(p)
        if X and X in L:
            msg = f'🧊 {X}: 正在搬硬碟，先冷凍（只能看、不能改），搬完或按暫停後就可以'
            R['n'] += 1; R['last'] = f'{msg}：{os.fspath(p) if not isinstance(p, bytes) else p!r}'[:300]
            return msg
    return ''


def check(*paths):
    m = blocked(*paths)
    if m: raise PermissionError(m)


def _wrap(mod, name, npath):
    R = _reg(); key = f'{mod.__name__}.{name}'
    orig = R['orig'].get(key)
    if orig is None:
        orig = getattr(mod, name, None)
        if orig is None or getattr(orig, '_vs_frz', False): return
        R['orig'][key] = orig

    def w(*a, **k):
        if _reg()['letters']: check(*a[:npath])
        return orig(*a, **k)
    w._vs_frz = True; w.__name__ = getattr(orig, '__name__', name); w.__doc__ = getattr(orig, '__doc__', None)
    setattr(mod, name, w)


def _install():
    R = _reg()
    if R.get('installed'): return
    for mod, name, n in ((os, 'remove', 1), (os, 'unlink', 1), (os, 'rmdir', 1), (os, 'rename', 2), (os, 'replace', 2), (os, 'renames', 2),
                         (shutil, 'move', 2), (shutil, 'rmtree', 1)):
        try: _wrap(mod, name, n)
        except Exception: pass
    R['installed'] = True


def view():
    R = _reg()
    return {'on': bool(R['letters']), 'letters': sorted(R['letters']), 'why': R['why'], 'blocked': R['n'], 'last': R['last']}

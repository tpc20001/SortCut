"""HotZone FM — thumbnails for the explorer's icon view (and the phone).

Pictures: Pillow (bundled with the EXE). Videos: one frame via ffmpeg.exe if it is found (PATH, the program folder,
or a TikLive Monitor folder next to it). Results are cached in Data\\thumbs (JPEG), at most 2 made at the same
time so a hard disk is not hammered while you scroll.
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import threading
import time

from hz_common import DATA_DIR, ROOT, IS_WIN
import hz_win as W

CACHE = DATA_DIR / 'thumbs'
IMG = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tif', 'tiff', 'ico', 'heic'}
VID = {'mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'ts', 'm2ts', 'webm', 'mpg', 'mpeg', 'm4v', '3gp'}
_sem = threading.Semaphore(2)
_ff = {'t': 0, 'p': None}


def ffmpeg():
    if time.time() - _ff['t'] < 300: return _ff['p']
    cands = [shutil.which('ffmpeg'), str(ROOT / 'ffmpeg.exe'), str(ROOT / 'tools' / 'ffmpeg.exe'), str(ROOT.parent / 'TikLiveMonitor' / 'ffmpeg.exe')]
    try:
        import imageio_ffmpeg
        cands.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    p = next((c for c in cands if c and os.path.isfile(c)), None)
    _ff.update(t=time.time(), p=p)
    return p


def available():
    try:
        import PIL  # noqa
        pil = True
    except Exception:
        pil = False
    return {'images': pil, 'videos': bool(ffmpeg())}


def _key(path, st, size):
    return hashlib.sha1(f'{path}|{st.st_size}|{int(st.st_mtime)}|{size}'.encode('utf-8', 'surrogatepass')).hexdigest()


def folder_cover(path):
    """The picture shown on a folder in the icon view: cover/folder/poster.jpg, else the first picture inside
    (looks at most 300 entries, one level deep, so it stays instant on a hard disk)."""
    try:
        names = []
        with os.scandir(W.lp(path)) as it:
            for k, e in enumerate(it):
                if k > 300: break
                if e.is_file(follow_symlinks=False) and '.' in e.name and e.name.rsplit('.', 1)[1].lower() in IMG: names.append(e.name)
    except OSError:
        return None
    if not names: return None
    for pref in ('cover', 'folder', 'poster', 'thumb'):
        for n in names:
            if n.rsplit('.', 1)[0].lower() == pref: return os.path.join(path, n)
    return os.path.join(path, sorted(names, key=str.lower)[0])


def thumb(path, size=200, folder=False):
    """-> JPEG bytes or None."""
    if folder:
        p = folder_cover(path)
        return thumb(p, size) if p else None
    size = max(48, min(512, int(size)))
    ext = path.rsplit('.', 1)[-1].lower() if '.' in path else ''
    if ext not in IMG and ext not in VID: return None
    try: st = os.stat(W.lp(path))
    except OSError: return None
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (_key(path, st, size) + '.jpg')
    hit = _cached(f)
    if hit: return hit
    with _sem:
        hit = _cached(f)                                   # made by another request while this one waited
        if hit: return hit
        data = _make_image(path, size) if ext in IMG else _make_video(path, size, st.st_size)
    if data:
        tmp = f.with_name(f'{f.stem}.{os.getpid()}.{threading.get_ident()}.tmp')     # one tmp per writer: never publish
        try: tmp.write_bytes(data); os.replace(tmp, f)                                   #  a file another thread still writes
        except OSError:
            try: tmp.unlink()
            except OSError: pass
        _maybe_prune()
    return data


def _cached(f):
    try: data = f.read_bytes()
    except OSError: return None
    try:                                                   # mark as used (NTFS rarely updates atime): the prune keeps it
        if time.time() - f.stat().st_mtime > 86400: os.utime(f)
    except OSError: pass
    return data or None


def _encode(im, size):
    from PIL import Image
    im.thumbnail((size, size), Image.LANCZOS if hasattr(Image, 'LANCZOS') else Image.BICUBIC)
    if im.mode not in ('RGB', 'L'):
        bg = Image.new('RGB', im.size, (21, 26, 33))
        try: bg.paste(im, mask=im.convert('RGBA').split()[-1])
        except Exception: bg.paste(im.convert('RGB'))
        im = bg
    out = io.BytesIO(); im.save(out, 'JPEG', quality=80, optimize=True)
    return out.getvalue()


def _limits(Image):
    """Big panoramas are fine (Pillow's default refuses > 178 MP), truncated downloads still give a picture."""
    if Image.MAX_IMAGE_PIXELS != 1_000_000_000:
        Image.MAX_IMAGE_PIXELS = 1_000_000_000
        try:
            from PIL import ImageFile
            ImageFile.LOAD_TRUNCATED_IMAGES = True
        except Exception:
            pass


def _make_image(path, size):
    try:
        from PIL import Image, ImageOps
    except Exception:
        return None
    try:
        _limits(Image)
        with Image.open(W.lp(path)) as im:
            try: im.draft('RGB', (size * 2, size * 2))           # JPEG: decode at a smaller scale (much faster)
            except Exception: pass
            if im.size[0] * im.size[1] > 150_000_000 and im.format != 'JPEG':
                return None                                        # a 150+ MP PNG/TIFF would need gigabytes to decode
            im = ImageOps.exif_transpose(im) if hasattr(ImageOps, 'exif_transpose') else im
            return _encode(im.copy(), size)
    except Exception:
        return None


def _make_video(path, size, nbytes):
    exe = ffmpeg()
    if not exe: return None
    for t in ('00:00:20', '00:00:03', '00:00:00'):
        try:
            r = subprocess.run([exe, '-nostdin', '-loglevel', 'error', '-ss', t, '-i', W.lp(path), '-frames:v', '1', '-vf', f'scale={size}:-2',
                                '-f', 'image2pipe', '-vcodec', 'mjpeg', '-q:v', '5', '-'],
                               capture_output=True, timeout=20, creationflags=W.no_window_flags())
            if r.returncode == 0 and len(r.stdout) > 500: return r.stdout
        except Exception:
            return None
    return None


_prune = {'t': 0}


def _maybe_prune(limit=2 * 1024 * 1024 * 1024):
    """Keep the thumbnail cache under 2 GB (about 150k photos): the least recently used go first."""
    if time.time() - _prune['t'] < 600: return
    _prune['t'] = time.time()
    try:
        fs = []
        with os.scandir(CACHE) as it:
            for e in it:
                if e.name.endswith('.tmp'):                    # left by a crash mid-write
                    try:
                        if time.time() - e.stat().st_mtime > 3600: os.remove(e.path)
                    except OSError: pass
                if e.name.endswith('.jpg'):
                    try: st = e.stat(); fs.append((max(st.st_atime, st.st_mtime), st.st_size, e.path))
                    except OSError: pass
        tot = sum(x[1] for x in fs)
        if tot <= limit: return
        for _t, sz, p in sorted(fs):
            if tot <= limit * 0.8: break
            try: os.remove(p); tot -= sz
            except OSError: pass
    except Exception:
        pass

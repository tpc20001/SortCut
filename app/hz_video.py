"""HotZone FM — 影片工具: length / resolution / codec of every video in a folder (ffprobe, cached), and lossless
"remux" to MP4 (FLV / TS / MKV recordings -> MP4 without re-encoding: same quality, minutes instead of hours).

Safety: the MP4 is written under a temporary name, checked (it must have video and the same length as the
original), then renamed into place without replacing anything; only after that the original goes to the vault
(30 days) with the reason written down. If anything fails, the original stays where it is.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import threading
import time
import uuid

from hz_common import DATA_DIR, IS_WIN, norm, unique_name
import hz_win as W
import hz_thumbs as TH

DB = DATA_DIR / 'video.sqlite3'
EXTS = {'.mp4', '.mkv', '.flv', '.ts', '.m2ts', '.mts', '.mov', '.avi', '.wmv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp'}
REMUXABLE = {'.flv', '.ts', '.m2ts', '.mts', '.mkv', '.mov', '.webm', '.avi', '.m4v', '.3gp'}
LOW_PRIO = 0x00004000 if IS_WIN else 0                                  # BELOW_NORMAL_PRIORITY_CLASS


class ProbeFileError(RuntimeError):
    """The file itself could not be read (remembered); other errors (no ffmpeg, timeout) are retried later."""


def ffprobe():
    ff = TH.ffmpeg()
    if not ff: return None
    d = os.path.dirname(ff)
    for n in ('ffprobe.exe', 'ffprobe'):
        p = os.path.join(d, n)
        if os.path.isfile(p): return p
    import shutil
    return shutil.which('ffprobe')


def _flags():
    return W.no_window_flags() | LOW_PRIO


def probe(path):
    """-> {dur, w, h, vcodec, acodec, fps, br, fmt} ; raises on unreadable files."""
    fp = ffprobe()
    if fp:
        r = subprocess.run([fp, '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', W.lp(path)],
                           capture_output=True, timeout=60, creationflags=_flags())
        if r.returncode != 0: raise ProbeFileError((r.stderr or b'').decode('utf-8', 'replace').strip()[:200] or 'ffprobe 失敗')
        j = json.loads(r.stdout.decode('utf-8', 'replace') or '{}')
        fmt = j.get('format') or {}; out = {'dur': float(fmt.get('duration') or 0), 'br': int(float(fmt.get('bit_rate') or 0)),
                                             'fmt': fmt.get('format_name', ''), 'w': 0, 'h': 0, 'vcodec': '', 'acodec': '', 'fps': 0.0, 'subs': 0, 'subs_text': True}
        for s in j.get('streams') or []:
            if s.get('codec_type') == 'video' and not out['vcodec'] and not (s.get('disposition') or {}).get('attached_pic'):
                out.update(w=int(s.get('width') or 0), h=int(s.get('height') or 0), vcodec=s.get('codec_name', ''))
                try:
                    a, b = (s.get('avg_frame_rate') or '0/1').split('/'); out['fps'] = round(float(a) / float(b), 2) if float(b) else 0.0
                except Exception: pass
                if not out['dur'] and s.get('duration'): out['dur'] = float(s['duration'])
            elif s.get('codec_type') == 'audio' and not out['acodec']:
                out['acodec'] = s.get('codec_name', '')
            elif s.get('codec_type') in ('subtitle', 'attachment'):
                out['subs'] += 1
                if s.get('codec_type') == 'attachment' or s.get('codec_name') not in ('subrip', 'ass', 'ssa', 'mov_text', 'webvtt', 'text'): out['subs_text'] = False
        return out
    ff = TH.ffmpeg()
    if not ff: raise RuntimeError('找不到 ffmpeg')
    r = subprocess.run([ff, '-hide_banner', '-nostdin', '-i', W.lp(path)], capture_output=True, timeout=60, creationflags=_flags())
    t = (r.stderr or b'').decode('utf-8', 'replace')
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', t)
    out = {'dur': int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0, 'br': 0, 'fmt': '', 'w': 0, 'h': 0, 'vcodec': '', 'acodec': '', 'fps': 0.0}
    m = re.search(r'Video: (\w+).*?, (\d{2,5})x(\d{2,5})', t)
    if m: out.update(vcodec=m.group(1), w=int(m.group(2)), h=int(m.group(3)))
    m = re.search(r'Audio: (\w+)', t)
    if m: out['acodec'] = m.group(1)
    out['subs'] = len(re.findall(r'Stream #\S+: (?:Subtitle|Attachment)', t))
    if not out['dur'] and not out['vcodec']: raise ProbeFileError('讀不到影片資訊（檔案可能損壞）')
    return out


class VideoTools:
    def __init__(self, eng):
        self.eng = eng; self.log = eng.log; self.lock = threading.RLock()
        self.db = sqlite3.connect(str(DB), check_same_thread=False, timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS vid(path TEXT PRIMARY KEY, size INTEGER, mtime REAL, info TEXT, err TEXT)')
        self.db.commit()
        self.jobs = []                                                   # remux jobs (in memory; the result is on disk)
        self.wake = threading.Event(); self.stop_ev = threading.Event()
        self.probe_q = []; self.probe_st = {'left': 0, 'folder': ''}
        self.th = threading.Thread(target=self._loop, name='HZ-Video', daemon=True); self.th.start()

    def stop(self):
        self.stop_ev.set(); self.wake.set()
        for j in self.jobs:
            if j['state'] == 'running' and j.get('proc'):
                try: j['proc'].kill()
                except Exception: pass
        self.th.join(5)
        try: self.db.close()
        except Exception: pass

    # ---------------------------------------------------------------- listing
    def _cached(self, path, st):
        with self.lock:
            r = self.db.execute('SELECT size, mtime, info, err FROM vid WHERE path=?', (path,)).fetchone()
        if r and r[0] == st.st_size and abs((r[1] or 0) - st.st_mtime) < 1:
            return (json.loads(r[2]) if r[2] else None), r[3]
        return None, None

    def list(self, folder, recursive=False, limit=5000):
        folder = norm(folder)
        if not os.path.isdir(folder): raise ValueError('找不到這個資料夾')
        files = []
        if recursive:
            for root, ds, fs, links in W.walk(folder):
                ds[:] = [d for d in ds if d != '.HotZoneVault']
                files += [os.path.join(root, f) for f in fs if os.path.splitext(f)[1].lower() in EXTS]
                if len(files) > limit: break
        else:
            with os.scandir(W.lp(folder)) as it:
                for e in it:
                    if e.is_file() and os.path.splitext(e.name)[1].lower() in EXTS: files.append(os.path.join(folder, e.name))
        items = []; todo = []
        for p in sorted(files)[:limit]:
            try: st = os.stat(W.lp(p))
            except OSError: continue
            info, err = self._cached(p, st)
            if info is None and err is None: todo.append(p)
            items.append({'path': p, 'name': os.path.basename(p), 'size': st.st_size, 'mtime': st.st_mtime, 'info': info, 'err': err,
                          'remux': os.path.splitext(p)[1].lower() in REMUXABLE})
        with self.lock:
            self.probe_q = todo; self.probe_st = {'left': len(todo), 'folder': folder}
        self.wake.set()
        return {'items': items, 'probing': len(todo), 'ffmpeg': bool(TH.ffmpeg()), 'ffprobe': bool(ffprobe()), 'jobs': self.job_list()}

    # ---------------------------------------------------------------- remux
    def remux(self, paths, keep=False):
        if not TH.ffmpeg(): raise ValueError('找不到 ffmpeg：請把 ffmpeg.exe（和 ffprobe.exe）放進程式資料夾')
        n = 0
        with self.lock:
            busy = {j['src'] for j in self.jobs if j['state'] in ('queued', 'running')}
            for p in paths:
                p = norm(p)
                if p in busy or not os.path.isfile(W.lp(p)) or os.path.splitext(p)[1].lower() not in REMUXABLE: continue
                self.jobs.append({'id': uuid.uuid4().hex[:8], 'src': p, 'state': 'queued', 'msg': '', 'pct': 0.0, 'dst': None, 'keep': bool(keep), 't': time.time()})
                n += 1
        self.wake.set()
        return n

    def job_list(self):
        with self.lock:
            self.jobs = [j for j in self.jobs if j['state'] in ('queued', 'running') or time.time() - j.get('t_end', time.time()) < 3600][-300:]
            return [{k: v for k, v in j.items() if k != 'proc'} for j in self.jobs]

    def cancel(self, jid=None):
        with self.lock:
            for j in self.jobs:
                if (jid is None or j['id'] == jid) and j['state'] in ('queued', 'running'):
                    j['cancel'] = True
                    if j.get('proc'):
                        try: j['proc'].kill()
                        except Exception: pass
                    if j['state'] == 'queued': j.update(state='canceled', msg='已取消', t_end=time.time())

    def _loop(self):
        W.thread_background(True)
        while not self.stop_ev.is_set():
            job = None
            with self.lock:
                job = next((j for j in self.jobs if j['state'] == 'queued'), None)
                if job: job['state'] = 'running'
                elif self.probe_q: p = self.probe_q.pop(0); self.probe_st['left'] = len(self.probe_q)
                else: p = None
            if job:
                try: self._remux(job)
                except Exception as e:
                    job.update(state='error', msg=str(e)[:300]); self.log.warn('video', f'轉檔失敗 {job["src"]}：{e}')
                job['t_end'] = time.time(); job.pop('proc', None)
                continue
            if p:
                self._probe_store(p); continue
            self.wake.wait(30); self.wake.clear()

    def _probe_store(self, p):
        try:
            st = os.stat(W.lp(p)); info = probe(p); err = None
        except ProbeFileError as e:
            info, err = None, str(e)[:200]
            try: st = os.stat(W.lp(p))
            except OSError: return
        except Exception:
            return None                                                   # no ffmpeg / timeout / busy disk: try again next time
        with self.lock:
            self.db.execute('INSERT OR REPLACE INTO vid VALUES(?,?,?,?,?)', (p, st.st_size, st.st_mtime, json.dumps(info) if info else None, err)); self.db.commit()
        return info

    def _remux(self, job):
        src = job['src']; ff = TH.ffmpeg()
        while self.eng.queue_busy_any() and not self.stop_ev.is_set() and not job.get('cancel'):  # the disk belongs to the queue first
            job['msg'] = '傳輸佇列在工作，等它做完'; self.stop_ev.wait(3)
        if self.stop_ev.is_set() or job.get('cancel'): raise RuntimeError('已取消（原檔沒動）')
        info = self._probe_store(src) or {}
        dur = float(info.get('dur') or 0)
        if not info.get('vcodec'): raise RuntimeError('讀不到影像軌，不轉')
        base = os.path.splitext(src)[0]
        dst = unique_name(base + '.mp4')
        tmp = os.path.join(os.path.dirname(src), f'.{uuid.uuid4().hex[:10]}.hzremux.mp4')
        subs = int(info.get('subs') or 0)
        sub_args = ['-map', '0:s?', '-c:s', 'mov_text'] if subs and info.get('subs_text', True) else ['-sn']
        if subs: job['keep'] = True                                         # MP4 cannot hold every subtitle / attachment: keep the original
        cmd = [ff, '-hide_banner', '-nostdin', '-y', '-i', W.lp(src), '-map', '0:v?', '-map', '0:a?', *sub_args[:2], '-c', 'copy', *sub_args[2:], '-dn',
               '-ignore_unknown', '-movflags', '+faststart', '-progress', 'pipe:1', '-nostats', '-loglevel', 'error', W.lp(tmp)]
        job.update(msg='轉換中…', dst=dst)
        try:
            with self.lock:
                if self.stop_ev.is_set() or job.get('cancel'): raise RuntimeError('已取消（原檔沒動）')
                proc = job['proc'] = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=_flags())
            err_tail = []
            def _err():
                for ln in proc.stderr: err_tail.append(ln.decode('utf-8', 'replace').strip()); del err_tail[:-10]
            te = threading.Thread(target=_err, daemon=True); te.start()
            for ln in proc.stdout:
                m = re.match(rb'out_time_(?:us|ms)=(\d+)', ln)
                if m and dur: job['pct'] = min(99.0, int(m.group(1)) / 1e6 / dur * 100)
            proc.wait(); te.join(2)
            if job.get('cancel') or self.stop_ev.is_set(): raise RuntimeError('已取消（原檔沒動）')
            if proc.returncode != 0: raise RuntimeError('ffmpeg 失敗：' + ' / '.join(err_tail[-3:]))
            out = probe(tmp)
            if not out.get('vcodec'): raise RuntimeError('轉出來的檔案沒有影像，已放棄（原檔沒動）')
            if dur and abs(out.get('dur', 0) - dur) > max(2.0, dur * 0.01):
                raise RuntimeError(f'轉出來的長度 {out.get("dur", 0):.0f} 秒和原檔 {dur:.0f} 秒差太多，已放棄（原檔沒動）')
            try:
                with open(W.lp(tmp), 'r+b') as f_: os.fsync(f_.fileno())      # on the disk before the original may go to the vault
            except OSError:
                pass
            for _ in range(100):
                try: W.rename_noreplace(tmp, dst); break
                except FileExistsError: dst = unique_name(dst)
            try:
                st = os.stat(W.lp(src)); W.set_times(dst, None, st.st_atime, st.st_mtime)   # keep the recording date
            except Exception: pass
        except BaseException:
            try:
                if os.path.exists(W.lp(tmp)): os.remove(W.lp(tmp))
            except OSError: pass
            raise
        job['dst'] = dst
        msg = f'完成：{os.path.basename(dst)}' + ('（原檔有字幕／附件軌，原檔保留不動）' if subs else '')
        if not job.get('keep'):
            try:
                self.eng.vault.stash(src, f'已無損轉成 MP4：{dst}（畫質完全相同，原檔先保管）', 'remux')
                msg += '；原檔已放進保管區'
            except Exception as e:
                msg += f'；原檔沒有移走（{e}）'
        job.update(state='done', pct=100.0, msg=msg)
        self.eng.index.touch(dst); self.eng.index.touch(src)
        try: self.eng.hot.notify([dst])                                    # a new file in a hot folder -> outer zone
        except Exception: pass
        self.log.info('video', f'無損轉 MP4：{src} → {dst}')

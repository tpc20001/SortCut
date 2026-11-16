"""HotZone FM — background engine: owns the drives view, disk counters, index, transfer queue, hot zone,
web server and updater. Runs elevated (administrator) and keeps running when the window is closed.

Hot update: hz_update.hot_reload() builds a new Engine(adopt=state) from freshly loaded modules after the old one
stopped at a safe point. Everything long-lived is handed over through export_state() / adopt.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import types

from hz_common import APP_VERSION, APP_NAME, APP_DIR, DATA_DIR, IS_WIN, Settings, Log, read_json, atomic_write_json, fmt_size, drive_of
import hz_win as W
import hz_index as I
import hz_transfer as T
import hz_hot as H
import hz_update as U
import hz_server as SV
import hz_api as A
import hz_undo as UN
import hz_vault as VA
import hz_dupes as DU
import hz_comfy as CF
import hz_images as IM

APP_VERSION_ENGINE = APP_VERSION


def runtime():
    rt = sys.modules.get('_hz_rt')
    if rt is None:
        rt = types.ModuleType('_hz_rt'); rt.engine = None; rt.gen = 0; rt.mode = 'source'; rt.launcher_version = 1
        rt.quit_ev = threading.Event(); sys.modules['_hz_rt'] = rt
    if getattr(rt, 'quit_ev', None) is None: rt.quit_ev = threading.Event()
    return rt


class Engine:
    def __init__(self, adopt=None):
        adopt = adopt or {}
        self.started = adopt.get('started') or time.time()
        self.S = Settings()
        self.log = Log('engine')
        if adopt.get('log_ring'):
            self.log.ring = list(adopt['log_ring']); self.log.seq = int(adopt.get('log_seq', 0))
        self.drives = W.Drives(); self.drives.refresh()
        self.counters = W.DiskCounters()
        self.meter = T.IoMeter()
        self.index = I.IndexManager(self.S, self.log, self.drives, hot_folders_fn=lambda: self.hot.folders())
        self.queue = T.TransferManager(self.S, self.log, self.drives, self.counters, self.meter)
        self.hot = H.HotManager(self.S, self.log, self.drives, self.index, self.counters, self.meter, queue_busy=self._queue_busy)
        self.queue.hot_check = self.hot.is_hot
        def _done_paths(paths, job):
            self.hot.notify(paths)
            for p_ in paths[:20000]: self.index.touch(p_, recursive_new=False)   # the real final names ('x (2).jpg', merges)
        self.queue.on_done_paths = _done_paths
        self.queue.on_touch = self.index.touch
        import hz_compare as CMP
        self.compare = CMP.Comparer(self)
        import hz_video as VID
        self.video = VID.VideoTools(self)
        import hz_bench as BEN
        self.bench = BEN.Bench(self)
        self.undo = UN.Undo(self)
        try:
            import hz_fileops as _F
            _F.recover_batch_rename(self.log)
        except Exception:
            self.log.exc('rename', 'recover')
        self.vault = VA.Vault(self.S, self.log)
        self.queue.vault = self.vault
        self.queue.on_job_done = self._job_done
        self.dupes = DU.DupeFinder(self)
        self.comfy = CF.ComfyScanner(self)
        self.images = IM.ImageLibrary(self)
        if adopt.get('images_paused'): self.images.paused = True
        if adopt.get('dupes'): self.dupes.st = adopt['dupes']
        self.index.adopt(adopt.get('index'))
        self.queue.adopt(adopt.get('queue'))
        self.hot.adopt(adopt.get('hot'))
        self.sessions = SV.Sessions(int(self.S.get('web.session_days') or 30))
        self.local_token = SV.local_token(rotate=not adopt)                # new key at every real start (kept over a hot update)
        self.fails = {}
        self.notices = list(adopt.get('notices') or [])
        self.scans = {}
        self.map_cache = {}
        self.updater = U.Updater(self)
        if adopt.get('update_state'): self.updater.state = adopt['update_state']
        self.shell_changed = bool(adopt.get('shell_changed'))
        self.api = A.build_api(self)
        self.server = SV.WebServer(self)
        self.stop_ev = threading.Event()
        self._stamp = 0.0
        self._seen_update = None
        if adopt:
            last = read_json(DATA_DIR / 'last_update.json', None)
            if last and time.time() - last.get('t', 0) < 600:
                self.updater.state = {'state': 'done', 'to': last.get('to'), 'from': last.get('from'), 'notes': last.get('notes'), 't': last.get('t'),
                                      'shell_changed': last.get('shell_changed')}
                if last.get('shell_changed'): self.shell_changed = True

    # --------------------------------------------------------------------------- life cycle
    def start(self):
        self.counters.start()
        self.index.start()
        try: self.vault.reconcile(min_age=0)                           # before anything can start stashing (nothing is mid-way now)
        except Exception: self.log.exc('vault', 'reconcile')
        self.queue.start()
        self.hot.start()
        self.images.start()
        self.server.start()
        self.th = threading.Thread(target=self._loop, name='HZ-Engine', daemon=True); self.th.start()
        self.log.info('engine', f'{APP_NAME} V{APP_VERSION} 啟動（{"系統管理員" if W.is_admin() else "一般權限"}）')
        if not W.is_admin() and IS_WIN:
            self.notice('admin', 'warn', '背景引擎不是以系統管理員身分執行：熱區搬移與 MFT 快速索引無法使用（會改用一般掃描）。')
        try: atomic_write_json(DATA_DIR / 'last_good.json', {'version': APP_VERSION, 't': time.time()})   # the launcher rolls back to this
        except Exception: pass
        if IS_WIN and W.is_admin() and int(self.S.get('system.task_v') or 0) < 2:
            threading.Thread(target=self._upgrade_task, name='HZ-Task', daemon=True).start()
        return self

    def _upgrade_task(self):
        """An auto-start task made by an older version used the Windows defaults (stops on battery / after 3 days):
        write it again from the XML definition."""
        try:
            import hz_fileops as F
            if F.autostart_state().get('on'): F.autostart_set(True); self.log.info('engine', '已更新開機自動啟動的排程設定')
            self.S.set('system.task_v', 2)
        except Exception as e:
            self.log.warn('engine', f'更新排程設定失敗：{e}')

    def _job_done(self, j):
        self.undo.job_done(j)
        try:
            if j.get('kind') == 'move' and j.get('pairs'): self.images.move_stars(j['pairs'])
            elif j.get('kind') == 'move' and j.get('tops'): self.images.move_stars([[a, b] for a, b, existed in j['tops']])
        except Exception:
            self.log.exc('images', 'move stars')
        kt = self.queue._kind_text(j['kind'])
        self.vault.note('job', f'{kt}：{len(j["src"])} 項' + (f' → {j["dst"]}' if j.get('dst') else '') + f'（{j.get("msg") or ""}）',
                        {'src': j['src'][:50], 'dst': j.get('dst'), 'files': j.get('done_files'), 'bytes': j.get('done_bytes'),
                         'errors': (j.get('errors') or [])[:20], 'skipped': j.get('skipped'), 'job': j['id']})

    def stop(self, handoff=False):
        self.stop_ev.set()
        try: self.dupes.cancel()
        except Exception: pass
        try: self.compare.cancel()
        except Exception: pass
        try: self.video.stop()
        except Exception: pass
        try: self.bench.stop()
        except Exception: pass
        try: self.images.stop()
        except Exception: pass
        self.server.stop()
        self.queue.stop()
        self.hot.stop()
        self.index.stop(save=not handoff)
        self.counters.stop()
        if not any(th.is_alive() for th in list(self.queue.workers.values())):
            try: self.vault.close()
            except Exception: pass

    def export_state(self):
        return {'version': APP_VERSION, 'started': self.started, 'index': self.index.export_state(), 'queue': self.queue.export_state(),
                'hot': self.hot.export_state(), 'log_ring': self.log.ring, 'log_seq': self.log.seq, 'notices': self.notices,
                'update_state': self.updater.state, 'shell_changed': self.shell_changed,
                'images_paused': self.images.paused,
                'dupes': dict(self.dupes.st, state=('canceled' if self.dupes.st.get('state') == 'running' else self.dupes.st.get('state')))}

    def _loop(self):
        t_drv = 0; t_upd = 0; t_vault = 0; busy_seen = False
        while not self.stop_ev.wait(2.0):
            try:
                now = time.time()
                if now - t_drv > 20:
                    self.drives.refresh(); t_drv = now
                    self._space_notices()
                if now - t_upd > 15:
                    t_upd = now
                    found = U.scan_update_folder()
                    if found and found != self._seen_update:
                        self._seen_update = found
                        self.notice('update_folder', 'info', f'UPDATE 資料夾有新的更新包 V{found[1]}，到「更新」頁按一下就能熱更新。', action='update')
                for k in [k for k, v in self.scans.items() if now - v.get('t', 0) > 3600]: self.scans.pop(k, None)
                qa = self.S.get('transfer.after')
                busy = any(j['state'] in T.ACTIVE + ('queued',) for j in list(self.queue.jobs.values()))
                if busy: busy_seen = True
                elif busy_seen and qa:
                    busy_seen = False; self._after_queue(qa)
                if now - t_vault > 3600:
                    if t_vault:
                        try: self.vault.reconcile(min_age=600)
                        except Exception: self.log.exc('vault', 'reconcile')
                    t_vault = now
                    n = self.vault.maintain()
                    if n: self.notice('vault_review', 'info', f'保管區有 {n} 個項目超過保管期限，等你決定要不要留', action='vault')
            except Exception:
                self.log.exc('engine', 'loop')

    def _after_queue(self, what):
        self.S.set('transfer.after', '')                                   # one time only
        text = {'sleep': '睡眠', 'hibernate': '休眠', 'shutdown': '關機'}.get(what, what)
        self.log.info('engine', f'佇列全部完成，{text}')
        self.vault.note('system', f'佇列全部完成，電腦{text}', None)
        if not IS_WIN: return
        import subprocess
        if what == 'shutdown':
            subprocess.Popen(['shutdown', '/s', '/t', '120', '/c', 'HotZone FM：傳輸佇列全部完成，2 分鐘後關機（取消：在程式通知上按取消，或執行 shutdown /a）'],
                             creationflags=W.no_window_flags())
            self.notice('shutdown', 'warn', '佇列全部完成：2 分鐘後關機', action='cancel_shutdown')
        elif what in ('sleep', 'hibernate'):
            subprocess.Popen(['rundll32.exe', 'powrprof.dll,SetSuspendState', '1' if what == 'hibernate' else '0', '1', '0'], creationflags=W.no_window_flags())

    def _space_notices(self):
        for v in self.drives.snapshot()['vols']:
            if v.get('total', 0) > 16 * 1024 ** 3 and v.get('type') == 'fixed' and v['free'] < max(5 * 1024 ** 3, v['total'] * 0.02):
                try: kept = self.vault.size_on(v['letter'])
                except Exception: kept = 0
                extra = f'；其中保管區留著 {fmt_size(kept)}，確定不需要的話可以到保管區清掉' if kept > 1024 ** 3 else ''
                self.notice('low_' + v['letter'], 'warn', f'{v["letter"]} 剩下 {fmt_size(v["free"])}，空間快滿了{extra}', action='vault' if extra else None)

    # --------------------------------------------------------------------------- helpers
    def notice(self, nid, level, text, action=None):
        self.notices = [n for n in self.notices if n['id'] != nid]
        self.notices.append({'id': nid, 'level': level, 'text': text, 't': time.time(), 'action': action})
        self.notices = self.notices[-20:]

    def notices_view(self):
        return self.notices

    def ui_stamp(self):
        """Changes whenever ui.* files change (the page reloads itself after an update)."""
        if time.time() - getattr(self, '_stamp_t', 0) > 2:
            st = 0.0
            for f in APP_DIR.glob('ui*.*'):
                try: st = max(st, f.stat().st_mtime)
                except OSError: pass
            self._stamp = st; self._stamp_t = time.time()
        return self._stamp

    def queue_busy_any(self):
        with self.queue.lock:
            return any(j['state'] in T.ACTIVE for j in self.queue.jobs.values())

    def _queue_busy(self, lane):
        with self.queue.lock:
            return any(j['state'] in T.ACTIVE and lane in (j.get('lanes') or []) for j in self.queue.jobs.values())

    def disk_view(self):
        snap = self.drives.snapshot(); out = []
        for d in snap['disks']:
            c = self.counters.get(d['n']) or {}
            lane = 'd%d' % d['n']
            ours = self.meter.rate(lane)
            out.append(dict(d, busy=c.get('busy'), rd=c.get('rd'), wr=c.get('wr'), ours=ours, smr=W.smr_suspect(d.get('model', ''))))
        return out

    def start_scan(self, path):
        """TreeSize for a folder that is not in the index (network share, excluded drive): scan it in the background."""
        p = path
        sc = {'state': 'scanning', 'msg': '掃描中…', 't': time.time(), 'mgr': None}
        self.scans[p] = sc

        def work():
            try:
                vi = I.VolumeIndex(p, p)

                def prog(n): sc['msg'] = f'掃描中… {n:,} 個項目'
                new = I.build_scan(vi, exclude=self.S.get('index.exclude') or [], progress=prog)
                m = I.IndexManager(self.S, self.log, self.drives)
                m.vols[p] = new; new.totals(wait=True)
                sc.update(state='ready', mgr=m, msg='', t=time.time())
            except Exception as e:
                sc.update(state='error', msg=str(e))
        threading.Thread(target=work, name='HZ-Scan', daemon=True).start()
        return sc


def run_engine():
    """Engine process main loop (called by the launcher with --engine, or `python hz_engine.py`)."""
    rt = runtime()
    import socket as _s
    port = int(Settings().get('web.port') or 8765)
    try:
        import urllib.request, json as _j
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(f'http://127.0.0.1:{port}/api/ping', timeout=1.5) as r:
            if _j.loads(r.read().decode()).get('app') == APP_NAME:
                print('engine already running'); return 0
    except Exception:
        pass
    eng = Engine().start()
    rt.engine = eng
    try:
        while not rt.quit_ev.wait(1.0):
            pass
    except KeyboardInterrupt:
        pass
    try: rt.engine.log.info('engine', '結束'); rt.engine.stop(handoff=False)
    except Exception: pass
    return 0


if __name__ == '__main__':
    sys.path.insert(0, str(APP_DIR))
    sys.exit(run_engine())

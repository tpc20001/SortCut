"""HotZone FM — API handlers. Each handler gets (request handler h, query dict q, session) and returns a JSON-able
value (or streams itself and returns None)."""
from __future__ import annotations

import json
import os
import platform
import secrets
import socket
import sys
import shutil
import threading
import time
import urllib.parse
import zipfile

from hz_common import ROOT, IS_WIN, APP_NAME, APP_VERSION, APP_DIR, DATA_DIR, norm, drive_of, read_json, fmt_size, DEFAULTS, json_safe, check_settings, IMPORT_SKIP
import hz_win as W
import hz_fileops as F
import hz_index as I
import hz_update as U
import hz_thumbs as TH
import hz_qr as QR
import hz_comfy as CF
from hz_server import HttpError, hash_pw
import hz_transfer as T

SECRET_KEYS = {'web.pw_hash', 'web.pw_salt'}


def build_api(eng):
    api = {}

    def route(method, path):
        def deco(fn):
            api[(method, path)] = fn
            return fn
        return deco

    def need_local(h, sess):
        if not (sess and sess.get('local') and h.is_local): raise HttpError(403, '只能在這台電腦上操作')

    # ------------------------------------------------------------------ session
    @route('GET', '/api/ping')
    def ping(h, q, s):
        rt = sys.modules.get('_hz_rt')
        return {'ok': True, 'app': APP_NAME, 'ver': APP_VERSION, 'gen': getattr(rt, 'gen', 0), 'stamp': eng.ui_stamp(), 'mode': getattr(rt, 'mode', None),
                **({'root': os.path.normcase(os.path.abspath(str(ROOT))), 'pid': os.getpid()} if h.is_local else {})}

    @route('GET', '/api/me')
    def me(h, q, s):
        return {'ok': True, 'logged': s is not None, 'local': h.is_local, 'pw_set': bool(eng.S.get('web.pw_hash')),
                'ver': APP_VERSION, 'app': APP_NAME, 'host': socket.gethostname()}

    @route('POST', '/api/login')
    def login(h, q, s):
        ip = h.client_ip; now = time.time(); n, t = eng.fails.get(ip, (0, 0))
        if now - t > 3600: n = 0                                         # an hour without a wrong try: start over
        wait = 0 if n < 5 else 60 * 2 ** min(n - 5, 6)                    # 1, 2, 4 ... 64 min after 5 wrong tries
        if wait and now - t < wait: raise HttpError(429, f'密碼錯太多次，請 {max(1, int((wait - (now - t)) // 60) + 1)} 分鐘後再試')
        recent = [x for x in getattr(eng, 'fail_log', []) if now - x < 600]; eng.fail_log = recent
        if len(recent) > 60 and not h.is_local: raise HttpError(429, '短時間內密碼錯誤太多次，暫停登入幾分鐘')
        d = h.jbody(); pw = str(d.get('pw', ''))
        ph = eng.S.get('web.pw_hash'); salt = eng.S.get('web.pw_salt')
        if not ph:
            if h.is_local and d.get('local_key') and secrets.compare_digest(str(d['local_key']), eng.local_token): pass
            else: raise HttpError(403, '電腦端還沒有設定網頁密碼：請在電腦上的「設定 → 遠端連線」設定密碼')
        elif not secrets.compare_digest(hash_pw(pw, salt), ph):
            eng.fails[ip] = (n + 1, now); eng.fail_log.append(now); raise HttpError(401, '密碼不對')
        eng.fails.pop(ip, None)
        tok = eng.sessions.new(ip, h.is_local)
        eng.log.info('web', f'登入：{ip}')
        h.json({'ok': True}, headers=h.set_cookie_headers(tok))

    @route('POST', '/api/logout')
    def logout(h, q, s):
        eng.sessions.drop(h.cookie('hzs'))
        h.json({'ok': True}, headers={'Set-Cookie': 'hzs=; Path=/; Max-Age=0'})

    # ------------------------------------------------------------------ overview
    @route('GET', '/api/state')
    def state(h, q, s):
        rt = sys.modules.get('_hz_rt')
        qs = eng.queue.list()
        hs = eng.hot.status()
        return {'ver': APP_VERSION, 'gen': getattr(rt, 'gen', 0), 'stamp': eng.ui_stamp(), 'admin': W.is_admin(), 'win': IS_WIN,
                'local': h.is_local and bool(s and s.get('local')), 'host': socket.gethostname(),
                'disks': eng.disk_view(),
                'queue': {k: qs[k] for k in ('running', 'queued', 'waiting', 'speed', 'paused_all')},
                'hot': [{k: v.get(k) for k in ('letter', 'state', 'msg', 'pct_in', 'rate', 'hot_bytes', 'in_bytes', 'moved_bytes', 'eta')} for v in hs['vols']],
                'hot_paused': hs['paused'],
                'index': eng.index.status(), 'notices': eng.notices_view(), 'update': eng.updater.state,
                'web_err': eng.server.err, 'shell_changed': eng.shell_changed}

    @route('GET', '/api/drives')
    def drives(h, q, s):
        return {'disks': eng.disk_view(), 'vols': eng.drives.snapshot()['vols']}

    @route('POST', '/api/notice/dismiss')
    def notice_dismiss(h, q, s):
        nid = h.jbody().get('id'); eng.notices = [n for n in eng.notices if n['id'] != nid]; return {'ok': True}

    # ------------------------------------------------------------------ explorer
    def show_vol(v):                                   # the volume fields the folder header shows (free space changes often:
        v = v or {}                                    #  rounded to 64 MB so a busy disk does not defeat the signature)
        return (v.get('label'), v.get('fs'), (v.get('free') or 0) >> 26, v.get('total'))

    @route('GET', '/api/ls')
    def ls(h, q, s):
        p = q.get('path', '')
        hidden = q.get('hidden') == '1' or bool(eng.S.get('explorer.show_hidden'))
        hot = [x['path'] for x in eng.hot.folders()]
        if not p:
            snap = eng.drives.snapshot()
            return {'path': '', 'root': True, 'vols': snap['vols'], 'disks': eng.disk_view(), 'fav': eng.S.get('fav') or [], 'hot': eng.hot.folders()}
        r = F.list_dir(p, hidden, hot)
        r['in_hot'] = eng.hot.is_hot(r['path'])
        r['hot_root'] = next((x for x in hot if norm(x).lower() == r['path'].lower()), None) if IS_WIN else (r['path'] if r['path'] in hot else None)
        r['vol'] = eng.drives.get(drive_of(r['path'])) if r['path'] else {}
        r['indexed'] = eng.index.vol_for(r['path']) is not None
        # change signature: the 4-second quiet refresh sends the last one back and gets {'same': True} when nothing changed
        # (no 25 MB JSON, no re-sort, no redraw of 100k rows)
        import hashlib
        sig = hashlib.md5(repr((r['path'], r['error'], r['in_hot'], r['hot_root'], r['indexed'], show_vol(r['vol']),
                                [(i['name'], i['size'], i['mtime'], i['hidden'], i['ro'], i['link'], i['hot'], i['dir']) for i in r['items']]))
                          .encode('utf-8', 'surrogatepass')).hexdigest()
        r['sig'] = sig
        if q.get('sig') == sig: return {'same': True, 'sig': sig, 'path': r['path']}
        return r

    @route('POST', '/api/dirsizes')
    def dirsizes(h, q, s):
        return {'sizes': eng.index.sizes_for([str(p) for p in h.jbody().get('paths', [])][:200000])}

    @route('POST', '/api/op')
    def op(h, q, s):
        d = h.jbody(); o = d.get('op')
        if o == 'mkdir':
            p = F.mkdir(d['path'], d['name']); eng.undo.push('mkdir', f'新增資料夾 {os.path.basename(p)}', {'path': p})
        elif o == 'newfile':
            p = F.newfile(d['path'], d['name']); eng.undo.push('newfile', f'新增檔案 {os.path.basename(p)}', {'path': p})
        elif o == 'rename':
            T.check_expect([d['path']], {d['path']: d['expect']} if d.get('expect') else None)   # an old row: not another file
            p = F.rename(d['path'], d['name']); eng.index.touch(d['path'])
            if p != d['path']:
                try: eng.images.move_stars([[d['path'], p]])
                except Exception: pass
                eng.undo.push('rename', f'重新命名 {os.path.basename(d["path"])} → {os.path.basename(p)}', {'old': d['path'], 'new': p})
                eng.vault.note('rename', f'重新命名：{d["path"]} → {os.path.basename(p)}', {'old': d['path'], 'new': p})
        else: raise HttpError(400, '不支援')
        eng.index.touch(p)
        return {'ok': True, 'path': p}

    @route('GET', '/api/thumb')
    def thumb(h, q, s):
        data = TH.thumb(q['path'], int(q.get('s', 200)), folder=q.get('dir') == '1')
        if not data:
            if q.get('dir') == '1':                        # folder without a cover: let the browser remember for 5 minutes
                return h.send(404, b'{"error":"no cover"}', cache=300)     # (was re-asked on every redraw, each a folder scan)
            raise HttpError(404, '沒有縮圖')
        h.send(200, data, 'image/jpeg', cache=86400)

    @route('POST', '/api/batch_rename')
    def batch_rename(h, q, s):
        pairs = F.batch_rename(h.jbody().get('items') or [])
        if pairs:
            try: eng.images.move_stars(pairs)
            except Exception: pass
            eng.undo.push('batch_rename', f'批次重新命名 {len(pairs)} 個項目', {'pairs': pairs})
            eng.vault.note('rename', f'批次重新命名 {len(pairs)} 個項目', {'pairs': pairs[:500]})
            for a, b in pairs: eng.index.touch(a); eng.index.touch(b)
        return {'ok': True, 'n': len(pairs)}

    @route('GET', '/api/undo')
    def undo_list(h, q, s):
        return {'items': eng.undo.list()}

    @route('POST', '/api/undo')
    def undo(h, q, s):
        r = eng.undo.undo(h.jbody().get('id'))
        eng.vault.note('undo', f'復原：{r["text"]}', {'msg': r.get('msg')})
        return r

    # ------------------------------------------------------------------ vault / journal
    @route('GET', '/api/vault')
    def vault(h, q, s):
        r = eng.vault.items(q.get('stage', 'keep'), q.get('q', ''), int(q.get('offset', 0)), int(q.get('limit', 300)), q.get('action', ''))
        r['stats'] = eng.vault.stats(); r['days'] = eng.S.get('vault.days')
        return r

    @route('GET', '/api/vault/size')
    def vault_size(h, q, s):
        return {'size': eng.vault.size_on(drive_of(norm(q['path'])))}

    @route('POST', '/api/vault/action')
    def vault_action(h, q, s):
        d = h.jbody(); ids = d.get('ids') or []; act = d.get('act'); out = []; errs = []
        if act == 'purge' and int(d.get('confirmed', 0)) != 3: raise HttpError(400, '永久刪除需要確認三次')
        for i in ids:
            try:
                if act == 'restore': out.append(eng.vault.restore(i)); eng.index.touch(out[-1])
                elif act == 'extend': eng.vault.extend(i)
                elif act == 'purge': eng.vault.purge(i)
                else: raise HttpError(400, '不支援')
            except HttpError: raise
            except Exception as e: errs.append(f'{i}：{e}')
        return {'ok': True, 'done': len(ids) - len(errs), 'errors': errs, 'paths': out}

    @route('GET', '/api/journal')
    def journal(h, q, s):
        return {'rows': eng.vault.journal(q.get('q', ''), q.get('kind', ''), q.get('before'), int(q.get('limit', 300)))}

    # ------------------------------------------------------------------ duplicates
    @route('GET', '/api/dupes')
    def dupes(h, q, s):
        return eng.dupes.status(int(q.get('limit', 400)))

    @route('POST', '/api/dupes/start')
    def dupes_start(h, q, s):
        d = h.jbody(); eng.dupes.start(d.get('path') or '', int(float(d.get('min_mb', 1)) * 1024 * 1024), bool(d.get('full', True)))
        return {'ok': True}

    @route('POST', '/api/dupes/remove')
    def dupes_remove(h, q, s):
        return {'ok': True, 'rm': eng.dupes.remove([str(p) for p in (h.jbody().get('paths') or [])])}

    @route('POST', '/api/dupes/cancel')
    def dupes_cancel(h, q, s):
        eng.dupes.cancel(); return {'ok': True}

    # ------------------------------------------------------------------ ComfyUI grid
    @route('POST', '/api/comfy/scan')
    def comfy_scan(h, q, s):
        d = h.jbody(); j = eng.comfy.scan(d['path'], bool(d.get('recursive')))
        return {'ok': True, 'job': {k: v for k, v in j.items()}}

    @route('GET', '/api/comfy/status')
    def comfy_status(h, q, s):
        return eng.comfy.status(q['path'], q.get('recursive') == '1')

    @route('GET', '/api/comfy/data')
    def comfy_data(h, q, s):
        d = eng.comfy.data(q['path'], q.get('recursive') == '1')
        if d is None: raise HttpError(404, '還沒有掃描這個資料夾')
        return d

    # ------------------------------------------------------------------ 圖片分類
    @route('GET', '/api/images/status')
    def images_status(h, q, s):
        return eng.images.status()

    @route('POST', '/api/images/folders')
    def images_folders(h, q, s):
        d = h.jbody(); f = [x for x in (eng.S.get('images.folders') or []) if norm(x).lower() != norm(d['path']).lower()]
        if d.get('act') != 'remove':
            if not os.path.isdir(d['path']): raise HttpError(400, '找不到這個資料夾')
            f.append(norm(d['path']))
        eng.S.set('images.folders', f); eng.images.wake.set()
        if d.get('act') == 'remove': eng.images.forget(d['path'])
        return {'ok': True, 'folders': f}

    @route('POST', '/api/images/pause')
    def images_pause(h, q, s):
        eng.images.paused = bool(h.jbody().get('on')); eng.images.wake.set(); return {'ok': True}

    @route('POST', '/api/images/rescan')
    def images_rescan(h, q, s):
        eng.images.wake.set(); return {'ok': True}

    @route('POST', '/api/images/query')
    def images_query(h, q, s):
        d = h.jbody(); return eng.images.query(d, int(d.get('offset', 0)), int(d.get('limit', 600)))

    @route('POST', '/api/images/facets')
    def images_facets(h, q, s):
        return eng.images.facets(h.jbody())

    @route('POST', '/api/images/similar')
    def images_similar(h, q, s):
        d = h.jbody(); return {'items': eng.images.similar(d['path'], int(d.get('limit', 300)), int(d.get('dist', 18)), d.get('scope', ''))}

    @route('POST', '/api/images/series')
    def images_series(h, q, s):
        d = h.jbody(); return {'groups': eng.images.series(d.get('scope', ''), int(d.get('gap', 180)), int(d.get('dist', 22)), int(d.get('min', 3)))}

    @route('POST', '/api/video/list')
    def video_list(h, q, s):
        d = h.jbody(); return eng.video.list(d.get('path', ''), bool(d.get('recursive')))

    @route('GET', '/api/video/jobs')
    def video_jobs(h, q, s):
        st = dict(eng.video.probe_st)
        return {'jobs': eng.video.job_list(), 'probing': st.get('left', 0)}

    @route('POST', '/api/video/remux')
    def video_remux(h, q, s):
        d = h.jbody(); return {'ok': True, 'n': eng.video.remux(d.get('paths') or [], bool(d.get('keep')))}

    @route('POST', '/api/video/cancel')
    def video_cancel(h, q, s):
        eng.video.cancel(h.jbody().get('id')); return {'ok': True}

    @route('GET', '/api/diag')
    def diag(h, q, s):
        """診斷資料: logs, settings without secrets, versions, queue / hot zone / index status, last self-test.
        No file contents, no passwords or tokens."""
        import io, platform
        from hz_common import LOG_DIR, ROOT
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
            info = {'app': APP_VERSION, 'python': sys.version, 'platform': platform.platform(), 'admin': W.is_admin(), 't': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'launcher': getattr(sys.modules.get('_hz_rt'), 'launcher_version', None), 'mode': getattr(sys.modules.get('_hz_rt'), 'mode', None)}
            z.writestr('info.json', json.dumps(info, ensure_ascii=False, indent=1))
            z.writestr('settings.json', json.dumps({k: v for k, v in eng.S.all().items() if k not in SECRET_KEYS}, ensure_ascii=False, indent=1, default=str))
            for name, fn in (('queue.json', lambda: eng.queue.list()), ('hot.json', lambda: eng.hot.status()), ('drives.json', lambda: eng.drives.snapshot()),
                             ('images.json', lambda: eng.images.status()), ('vault_stats.json', lambda: eng.vault.stats()), ('notices.json', lambda: eng.notices)):
                try: z.writestr(name, json.dumps(json_safe(fn()), ensure_ascii=False, indent=1, default=str))
                except Exception as e: z.writestr(name + '.error.txt', repr(e))
            def tail(f, n=2_000_000):
                with open(f, 'rb') as fh:
                    fh.seek(0, 2); size = fh.tell(); fh.seek(max(0, size - n)); return fh.read()
            if LOG_DIR.exists():
                for f in list(LOG_DIR.glob('*.txt')) + list(LOG_DIR.glob('*.log')):
                    try: z.writestr('LOG/' + f.name, tail(f))
                    except OSError: pass
            for f in (DATA_DIR / 'selftest_last.txt', ROOT / 'manifest.json'):
                if f.exists(): z.writestr(f.name, f.read_bytes())
        data = buf.getvalue()
        h.send(200, data, 'application/zip', headers={'Content-Disposition': f"attachment; filename*=UTF-8''{urllib.parse.quote('HotZoneFM_診斷資料_' + time.strftime('%Y%m%d_%H%M') + '.zip')}"})

    @route('POST', '/api/hot/vss_ok')
    def hot_vss_ok(h, q, s):
        L = h.jbody().get('letter', '')
        d = dict(eng.S.get('hot.vss_ok') or {}); d[L] = True; eng.S.set('hot.vss_ok', d)
        eng.log.info('hot', f'{L} 使用者同意：搬移可能讓 Windows 刪掉較舊的還原點')
        eng.hot.poke(L); return {'ok': True}

    @route('POST', '/api/hot/bench')
    def hot_bench(h, q, s):
        return eng.bench.start(h.jbody().get('letter', ''))

    @route('GET', '/api/hot/bench')
    def hot_bench_status(h, q, s):
        import hz_bench as BN
        return dict(eng.bench.status(), last=BN.last_results())

    @route('GET', '/api/help')
    def help_text(h, q, s):
        f = APP_DIR / 'hz_help.md'
        return {'md': f.read_text(encoding='utf-8') if f.exists() else '# 說明\n\n找不到說明檔。'}

    @route('POST', '/api/compare/start')
    def compare_start(h, q, s):
        d = h.jbody(); return eng.compare.start(d.get('a', ''), d.get('b', ''), bool(d.get('content')))

    @route('GET', '/api/compare')
    def compare_status(h, q, s):
        return eng.compare.status(int(q.get('limit', 3000)), q.get('only', ''))

    @route('POST', '/api/compare/cancel')
    def compare_cancel(h, q, s):
        eng.compare.cancel(); return {'ok': True}

    @route('POST', '/api/compare/sync')
    def compare_sync(h, q, s):
        d = h.jbody(); direction = d.get('dir', 'ab')
        if direction not in ('ab', 'ba', 'both'): raise HttpError(400, '方向不對')
        st = eng.compare.st
        if 'a' in d and (norm(str(d.get('a') or '')) != st.get('a') or norm(str(d.get('b') or '')) != st.get('b')):
            raise HttpError(409, '這個比較結果已經不是畫面上的兩個資料夾（可能在別的裝置重新比較過），請重新比較後再同步')
        pl = eng.compare.plan(direction, bool(d.get('mirror')))
        out = {'ok': True, 'copy': len(pl['copy']), 'vault': len(pl['vault']), 'skipped_changed': pl.get('skipped_changed', 0), 'skipped_unreadable': pl.get('skipped_unreadable', 0)}
        if pl['copy']:
            dst = pl['b'] if direction == 'ab' else pl['a'] if direction == 'ba' else pl['b']
            out['job'] = eng.queue.add('copy', [x[0] for x in pl['copy'][:1]], dst, {'pairs': pl['copy'], 'conflict': 'overwrite'})
        if pl['vault']:
            out['vault_job'] = eng.queue.add('vault', pl['vault'], None, {'reason': f'資料夾同步（鏡像）：{"左" if direction == "ab" else "右"}邊沒有這個檔案，所以從這邊移除'})
        return out

    @route('POST', '/api/images/star')
    def images_star(h, q, s):
        d = h.jbody(); return {'ok': eng.images.set_star(d.get('paths') or [], bool(d.get('on', True)))}

    @route('POST', '/api/comfy/params')
    def comfy_params(h, q, s):
        """Generation settings of PNGs, for batch-rename tokens like {seed} {cfg}."""
        out = {}
        for p in [norm(x) for x in (h.jbody().get('paths') or [])][:5000]:
            if not p.lower().endswith('.png'): continue
            try:
                prm, ok = CF.read_image(p)
                if ok: out[p] = {k: prm.get(k) for k in ('seed', 'cfg', 'steps', 'sampler', 'scheduler', 'model', 'denoise', 'width', 'height') if prm.get(k) is not None}
            except Exception:
                pass
        return {'params': out}

    @route('POST', '/api/taken')
    def taken(h, q, s):
        paths = [norm(p) for p in (h.jbody().get('paths') or [])][:20000]
        return {'taken': eng.images.taken_of(paths)}

    @route('POST', '/api/images/neardupes')
    def images_neardupes(h, q, s):
        d = h.jbody(); return {'groups': eng.images.neardupes(d.get('scope', ''), int(d.get('dist', 4)))}

    @route('POST', '/api/selftest')
    def selftest(h, q, s):
        import hz_selftest as ST
        d = h.jbody()
        r = ST.run(eng, d.get('letters') or None, bool(d.get('move', True)))
        r['text'] = ST.report_text(r)
        try: (DATA_DIR / 'selftest_last.txt').write_text(r['text'], encoding='utf-8')
        except OSError: pass
        eng.log.info('selftest', r['text'].replace('\n', ' | ')[:2000])
        return r

    @route('GET', '/api/comfy/peek')
    def comfy_peek(h, q, s):
        return eng.comfy.peek(q['path'], q.get('recursive') == '1')

    @route('GET', '/api/comfy/meta')
    def comfy_meta(h, q, s):
        texts, wh = CF.png_texts(q['path'])
        return {'texts': {k: v for k, v in texts.items() if k in ('prompt', 'workflow', 'parameters')}, 'size': wh}

    @route('GET', '/api/qr')
    def qr(h, q, s):
        h.send(200, QR.svg(q.get('text', '')[:180]), 'image/svg+xml; charset=utf-8', cache=3600)

    @route('GET', '/api/subdirs')
    def subdirs(h, q, s):
        return F.subdirs(q['path'], q.get('hidden') == '1' or bool(eng.S.get('explorer.show_hidden')), [x['path'] for x in eng.hot.folders()])

    @route('GET', '/api/props')
    def props(h, q, s):
        return F.props(q['path'], eng.index, eng.hot)

    @route('GET', '/api/preview')
    def preview(h, q, s):
        return F.preview(q['path'])

    @route('GET', '/api/file')
    def file(h, q, s):
        h.send_file(q['path'], download=q.get('dl') == '1')

    ZIPS = {}

    @route('POST', '/api/zip/prepare')
    def zip_prepare(h, q, s):
        """Long selections do not fit in a URL: store the list, the browser then downloads /api/zip?id=..."""
        paths = [norm(p) for p in (h.jbody().get('paths') or [])][:200000]
        now = time.time()
        for k in [k for k, v in ZIPS.items() if now - v[0] > 600]: ZIPS.pop(k, None)
        zid = secrets.token_urlsafe(12); ZIPS[zid] = (now, paths)
        return {'id': zid}

    @route('GET', '/api/zip')
    def zipdl(h, q, s):
        if q.get('id'):
            v = ZIPS.get(q['id']) if h.command == 'HEAD' else ZIPS.pop(q['id'], None)   # download managers send HEAD first
            if not v: raise HttpError(404, '下載連結過期了，請再按一次')
            paths = v[1]
        else:
            paths = json.loads(q.get('paths', '[]'))
        if not paths: raise HttpError(400, '沒有選擇')
        name = (os.path.basename(paths[0].rstrip('\\/')) if len(paths) == 1 else 'HotZone_下載') + '.zip'
        h.send_zip(paths, name)

    @route('PUT', '/api/upload')
    def upload(h, q, s):
        return h.receive_upload(q)

    @route('POST', '/api/fav')
    def fav(h, q, s):
        d = h.jbody(); f = [x for x in (eng.S.get('fav') or []) if x != d.get('path')]
        if d.get('on'): f.append(d['path'])
        eng.S.set('fav', f); return {'ok': True, 'fav': f}

    # ------------------------------------------------------------------ queue
    @route('GET', '/api/queue')
    def queue(h, q, s):
        return eng.queue.list()

    @route('GET', '/api/queue/job')
    def queue_job(h, q, s):
        d = eng.queue.detail(q['id'], int(q.get('offset', 0)), int(q.get('limit', 300)), q.get('only', ''))
        if d is None: raise HttpError(404, '找不到這個工作')
        return d

    @route('POST', '/api/queue/add')
    def queue_add(h, q, s):
        d = h.jbody()
        jid = eng.queue.add(d.get('kind'), d.get('src') or [], d.get('dst'), d.get('opts') or {}, int(d.get('prio', 0)))
        return {'ok': True, 'id': jid, 'job': eng.queue.summary(eng.queue.jobs[jid])}

    @route('POST', '/api/queue/action')
    def queue_action(h, q, s):
        d = h.jbody()
        if d.get('ids'):
            for i in d['ids']:
                try: eng.queue.action(i, d['act'], d.get('data'))
                except Exception: pass
            return {'ok': True}
        eng.queue.action(d['id'], d['act'], d.get('data')); return {'ok': True}

    @route('POST', '/api/queue/all')
    def queue_all(h, q, s):
        eng.queue.pause_all(bool(h.jbody().get('pause'))); return {'ok': True}

    @route('POST', '/api/queue/clear')
    def queue_clear(h, q, s):
        eng.queue.clear_finished(); return {'ok': True}

    # ------------------------------------------------------------------ search / index
    @route('GET', '/api/search')
    def search(h, q, s):
        try:
            return eng.index.search(q.get('q', ''), q.get('scope', ''), min(5000, int(q.get('limit', 300))), int(q.get('offset', 0)),
                                    q.get('sort', 'name'), q.get('desc') == '1', q.get('dirs_first') == '1')
        except (I.QueryError, ValueError) as e:
            return {'total': 0, 'items': [], 'error': str(e)}

    @route('GET', '/api/index')
    def index(h, q, s):
        return {'vols': eng.index.status(), 'enabled': eng.S.get('index.enabled'), 'drives': eng.S.get('index.drives'),
                'admin': W.is_admin()}

    @route('POST', '/api/index/rebuild')
    def index_rebuild(h, q, s):
        eng.index.rebuild(h.jbody().get('key')); return {'ok': True}

    # ------------------------------------------------------------------ space (TreeSize)
    def _space_src(path):
        """-> (source, scan record). The live index first; else a finished scan of this folder or of a parent."""
        if eng.index.vol_for(path) is not None: return eng.index, None
        sc = eng.scans.get(path)
        if sc and sc['state'] == 'ready': return sc['mgr'], None
        if sc and sc['state'] == 'scanning': return None, sc               # a rescan of this folder is running
        for k, v in list(eng.scans.items()):                              # a scan of a parent folder covers this one too
            if v['state'] == 'ready' and (path == k or path.startswith(k.rstrip('\\/') + os.sep)): return v['mgr'], None
        return None, sc

    @route('GET', '/api/tree')
    def tree(h, q, s):
        p = norm(q['path']); depth = max(1, min(4, int(q.get('depth', 2))))
        if q.get('rescan') == '1' and eng.index.vol_for(p) is None:       # ⟳ always reads the disk again (was ignored
            sc = eng.scans.get(p)                                           #  once any scan existed)
            if not sc or sc['state'] != 'scanning': sc = eng.start_scan(p)
            return {'scanning': True, 'state': sc['state'], 'msg': sc.get('msg', ''), 'path': p}
        src, sc = _space_src(p)
        if src is None:
            if not sc: sc = eng.start_scan(p)
            return {'scanning': True, 'state': sc['state'], 'msg': sc.get('msg', ''), 'path': p}
        node = src.tree(p, depth=depth, max_children=int(q.get('max', 150)))
        if node is None: raise HttpError(404, '找不到這個資料夾')
        vi = src.vol_for(p)
        node['source'] = 'index' if src is eng.index else 'scan'
        node['built'] = vi.built_t if vi else 0
        return node

    @route('GET', '/api/largest')
    def largest(h, q, s):
        p = norm(q['path']); src, sc = _space_src(p)
        if src is None: return {'items': []}
        return {'items': src.largest(p, int(q.get('n', 100)), dirs=q.get('dirs') == '1')}

    @route('GET', '/api/exts')
    def exts(h, q, s):
        p = norm(q['path']); src, sc = _space_src(p)
        if src is None: return {'rows': []}
        return {'rows': src.ext_stats(p)}

    @route('GET', '/api/ages')
    def ages(h, q, s):
        p = norm(q['path']); src, sc = _space_src(p)
        if src is None: return {'buckets': [], 'years': []}
        return src.age_stats(p) or {'buckets': [], 'years': []}

    # ------------------------------------------------------------------ hot zone
    @route('GET', '/api/hot')
    def hot(h, q, s):
        return eng.hot.status()

    @route('POST', '/api/hot/folder')
    def hot_folder(h, q, s):
        d = h.jbody()
        if d.get('act') == 'remove': f = eng.hot.remove_folder(d['path'])
        else: f = eng.hot.add_folder(d['path'])
        return {'ok': True, 'folders': f}

    @route('POST', '/api/hot/order')
    def hot_order(h, q, s):
        eng.hot.reorder(h.jbody().get('paths') or []); return {'ok': True}

    @route('POST', '/api/hot/zone')
    def hot_zone(h, q, s):
        d = h.jbody(); z = dict(eng.S.get('hot.zone_gb') or {}); z[d['letter']] = max(0, float(d.get('gb') or 0))
        eng.S.set('hot.zone_gb', z); eng.hot.poke(d['letter']); return {'ok': True}

    @route('POST', '/api/hot/pause')
    def hot_pause(h, q, s):
        eng.hot.set_paused(bool(h.jbody().get('on'))); return {'ok': True}

    @route('POST', '/api/hot/dry')
    def hot_dry(h, q, s):
        on = bool(h.jbody().get('on')); eng.S.set('hot.dry_run', on); eng.hot.ensure(); eng.hot.poke(); return {'ok': True}

    @route('POST', '/api/hot/poke')
    def hot_poke(h, q, s):
        eng.hot.ensure(); eng.hot.poke(h.jbody().get('letter')); return {'ok': True}

    @route('GET', '/api/hot/map')
    def hot_map(h, q, s):
        key = q['letter']; c = eng.map_cache.get(key)
        if c and time.time() - c[0] < 20 and q.get('fresh') != '1': return c[1]
        try: m = eng.hot.cluster_map(key, int(q.get('cells', 1600)))
        except Exception as e:                                            # (NtfsError: the class name leaked into the toast)
            if type(e).__name__ != 'NtfsError': raise
            raise HttpError(400, str(e))
        eng.map_cache[key] = (time.time(), m)
        return m

    @route('GET', '/api/hot/history')
    def hot_history(h, q, s):
        return {'points': eng.hot.history(q.get('letter', ''))}

    @route('GET', '/api/hot/layout')
    def hot_layout(h, q, s):
        return eng.hot.file_layout(q['path'])

    # ------------------------------------------------------------------ settings
    @route('GET', '/api/settings')
    def settings(h, q, s):
        a = {k: v for k, v in eng.S.all().items() if k not in SECRET_KEYS}
        a['web.pw_set'] = bool(eng.S.get('web.pw_hash'))
        return {'settings': a, 'defaults': {k: v for k, v in DEFAULTS.items() if k not in SECRET_KEYS}}

    @route('POST', '/api/settings')
    def settings_set(h, q, s):
        d, bad = check_settings({k: v for k, v in h.jbody().items() if k in DEFAULTS and k not in SECRET_KEYS})
        if bad: raise HttpError(400, '設定值不正確：' + '、'.join(bad))
        if ('web.port' in d or 'web.remote' in d or 'web.hosts' in d) and not (s and s.get('local') and h.is_local):
            raise HttpError(403, '連線設定只能在這台電腦上改')
        before = (eng.S.get('web.port'), eng.S.get('web.remote'))
        eng.S.update(d)
        if 'hot.dry_run' in d or 'hot.enabled' in d or 'hot.mode' in d: eng.hot.ensure(); eng.hot.poke()
        if 'index.drives' in d or 'index.enabled' in d: eng.index.wake.set()
        eng.queue.wake.set()
        if (eng.S.get('web.port'), eng.S.get('web.remote')) != before:
            threading.Timer(0.8, eng.server.restart).start()
        return {'ok': True, 'saved': d}                                   # what was really stored (numbers are kept in range)

    @route('POST', '/api/settings/import')
    def settings_import(h, q, s):
        """Restore a settings backup: one-off / per-PC values are not taken over (an armed 'shut down when done',
        the restore-point consent of another PC...), every value is type-checked, and the current settings are kept
        as settings.before_import_<time>.json first."""
        raw = h.jbody(); raw = raw.get('settings', raw) if isinstance(raw, dict) else {}
        if not isinstance(raw, dict): raise HttpError(400, '不是有效的設定檔')
        d = {k: v for k, v in raw.items() if k in DEFAULTS and k not in SECRET_KEYS and k not in IMPORT_SKIP}
        if not (s and s.get('local') and h.is_local): d.pop('web.port', None); d.pop('web.remote', None); d.pop('web.hosts', None)
        d, bad = check_settings(d)
        if not d: raise HttpError(400, '檔案裡沒有可以匯入的設定')
        try:
            if eng.S.path.exists(): shutil.copy2(eng.S.path, eng.S.path.with_name(f'settings.before_import_{time.strftime("%Y%m%d_%H%M%S")}.json'))
        except OSError as e:
            raise HttpError(500, f'無法先備份目前的設定，沒有匯入：{e}')
        before = (eng.S.get('web.port'), eng.S.get('web.remote'))
        eng.S.update(d)
        eng.hot.ensure(); eng.hot.poke(); eng.index.wake.set(); eng.queue.wake.set()
        if (eng.S.get('web.port'), eng.S.get('web.remote')) != before: threading.Timer(0.8, eng.server.restart).start()
        return {'ok': True, 'n': len(d), 'skipped': bad}

    @route('POST', '/api/password')
    def password(h, q, s):
        d = h.jbody(); new = str(d.get('new', ''))
        clear = bool(d.get('clear'))
        if not new and not clear: raise HttpError(400, '請輸入新密碼')          # (an empty box used to clear the password)
        if clear and not (s and s.get('local') and h.is_local): raise HttpError(403, '只能在這台電腦上清除密碼')
        if eng.S.get('web.pw_hash') and not (s and s.get('local') and h.is_local):
            if not secrets.compare_digest(hash_pw(str(d.get('old', '')), eng.S.get('web.pw_salt')), eng.S.get('web.pw_hash')):
                raise HttpError(403, '目前的密碼不對')                            # (401 = "not logged in": threw the phone out)
        if new and len(new) < 6: raise HttpError(400, '密碼至少 6 個字')
        if new and not clear:
            salt = secrets.token_hex(16); eng.S.update({'web.pw_salt': salt, 'web.pw_hash': hash_pw(new, salt)})
        else:
            eng.S.update({'web.pw_salt': '', 'web.pw_hash': ''})
        eng.sessions.drop_remote()
        eng.log.info('web', '網頁密碼已' + ('更新' if new else '清除') + '，遠端裝置需要重新登入')
        return {'ok': True}

    @route('GET', '/api/log')
    def log(h, q, s):
        return {'rows': eng.log.since(int(q.get('since', 0)))}

    # ------------------------------------------------------------------ update
    @route('GET', '/api/update')
    def update(h, q, s):
        found = U.scan_update_folder()
        return {'ver': APP_VERSION, 'state': eng.updater.state, 'pending': U.public(eng.updater.pending) if eng.updater.pending else None,
                'backups': U.list_backups()[:20], 'folder': {'path': found[0], 'version': found[1]} if found else None,
                'changelog': read_json(APP_DIR / 'hz_CHANGELOG.json', []) or [], 'last': read_json(DATA_DIR / 'last_update.json', None)}

    @route('PUT', '/api/update/upload')
    def update_upload(h, q, s):
        need_local(h, s)                                                    # new program code: only from this computer
        data = h.body(limit=200 * 1024 * 1024)
        return {'ok': True, 'pkg': eng.updater.load_upload(data, q.get('name', 'upload.zip'))}

    @route('POST', '/api/update/folder')
    def update_folder(h, q, s):
        found = U.scan_update_folder()
        if not found: raise HttpError(404, 'UPDATE 資料夾裡沒有比目前新的更新包')
        pkg = eng.updater.load_file(found[0])
        if eng.updater.pending: eng.updater.pending['remote_ok'] = True      # it was put on this computer by its owner
        return {'ok': True, 'pkg': pkg}

    @route('POST', '/api/update/rollback')
    def update_rollback(h, q, s):
        pkg = U.package_from_backup(h.jbody()['name']); pkg['src_name'] = '備份'; pkg['remote_ok'] = True
        eng.updater.pending = pkg
        return {'ok': True, 'pkg': U.public(pkg)}

    @route('POST', '/api/update/apply')
    def update_apply(h, q, s):
        if not (eng.updater.pending or {}).get('remote_ok'): need_local(h, s)
        return eng.updater.apply_pending('本機' if h.is_local else '遠端')

    @route('POST', '/api/update/cancel')
    def update_cancel(h, q, s):
        eng.updater.pending = None; return {'ok': True}

    # ------------------------------------------------------------------ system
    @route('GET', '/api/system')
    def system(h, q, s):
        port = eng.server.port or eng.S.get('web.port')
        ts = F.tailscale_info(port, force=q.get('force') == '1')
        rt = sys.modules.get('_hz_rt')
        return {'thumbs': TH.available(), 'port': port, 'lan': f'http://{F.lan_ip()}:{port}/', 'local': f'http://127.0.0.1:{port}/', 'tailscale': ts,
                'ts_url': ts.get('https') or (f'http://{ts["ip"]}:{port}/' if ts.get('ip') else ''),
                'admin': W.is_admin(), 'autostart': F.autostart_state(), 'platform': platform.platform(), 'host': socket.gethostname(),
                'pid': os.getpid(), 'started': eng.started, 'mode': getattr(rt, 'mode', 'source'), 'remote': eng.S.get('web.remote'),
                'pw_set': bool(eng.S.get('web.pw_hash')), 'web_err': eng.server.err, 'python': sys.version.split()[0],
                'launcher_version': getattr(rt, 'launcher_version', 1)}

    @route('POST', '/api/system/autostart')
    def system_autostart(h, q, s):
        need_local(h, s); return F.autostart_set(bool(h.jbody().get('on')))

    @route('POST', '/api/system/tailscale')
    def system_tailscale(h, q, s):
        need_local(h, s); return F.tailscale_serve(eng.server.port or eng.S.get('web.port'))

    @route('POST', '/api/system/open')
    def system_open(h, q, s):
        need_local(h, s); d = h.jbody()
        if d.get('how') == 'reveal': W.explorer_select(d['path'])
        else: W.explorer_open(d['path'])
        return {'ok': True}

    @route('POST', '/api/system/cancel_shutdown')
    def cancel_shutdown(h, q, s):
        import subprocess
        if IS_WIN: subprocess.run(['shutdown', '/a'], creationflags=W.no_window_flags())
        eng.notices = [n for n in eng.notices if n['id'] != 'shutdown']
        return {'ok': True}

    @route('POST', '/api/system/quit')
    def system_quit(h, q, s):
        need_local(h, s)
        rt = sys.modules.get('_hz_rt')
        if rt is not None and getattr(rt, 'quit_ev', None) is not None: threading.Timer(0.5, rt.quit_ev.set).start()
        return {'ok': True}

    @route('POST', '/api/system/restart')
    def system_restart(h, q, s):
        need_local(h, s)
        rt = sys.modules.get('_hz_rt')
        fn = getattr(rt, 'restart', None) if rt else None
        if not fn: raise HttpError(400, '這種啟動方式不能自動重開，請手動重開程式')
        threading.Timer(0.5, fn).start()
        return {'ok': True}

    return api

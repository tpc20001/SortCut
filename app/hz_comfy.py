"""HotZone FM — 生圖比較: read the generation data that ComfyUI (and A1111 / Forge) writes into PNG files and find
out which settings differ between the images of a folder, so they can be laid out as an X / Y table.

PNG text chunks (tEXt / iTXt / zTXt):
  prompt    = ComfyUI API graph {node_id: {class_type, inputs}}
  workflow  = ComfyUI editor graph (only used for node titles)
  parameters = A1111 / Forge / Fooocus style text
Only the chunks are read (the image data is skipped), so 2000 files take a few seconds.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import threading
import time
import zlib

from hz_common import DATA_DIR, norm
import hz_win as W

CACHE = DATA_DIR / 'comfy'
EXTS = ('.png', '.jpg', '.jpeg', '.webp')       # JPEG / WebP: A1111 writes its parameters into EXIF UserComment
SAMPLERS = ('KSampler', 'KSamplerAdvanced', 'SamplerCustom', 'SamplerCustomAdvanced', 'KSampler (Efficient)', 'KSamplerSelect')


def png_texts(path, limit=64 * 1024 * 1024):
    """{keyword: text} from the PNG's text chunks + (width, height)."""
    out = {}; wh = (0, 0)
    with open(W.lp(path), 'rb') as f:
        if f.read(8) != b'\x89PNG\r\n\x1a\n': return out, wh
        read = 8
        while read < limit:
            hdr = f.read(8)
            if len(hdr) < 8: break
            n, typ = struct.unpack('>I4s', hdr); read += 8
            if typ == b'IHDR':
                d = f.read(n); f.seek(4, 1); wh = struct.unpack('>II', d[:8])
            elif typ in (b'tEXt', b'iTXt', b'zTXt'):
                d = f.read(n); f.seek(4, 1)
                try:
                    k, rest = d.split(b'\0', 1); key = k.decode('latin-1')
                    if typ == b'tEXt': val = rest.decode('utf-8', 'replace')
                    elif typ == b'zTXt': val = _inflate(rest[1:]).decode('utf-8', 'replace')
                    else:
                        comp, method = rest[0], rest[1]; rest = rest[2:]
                        lang, rest = rest.split(b'\0', 1); tkey, rest = rest.split(b'\0', 1)
                        val = (_inflate(rest) if comp else rest).decode('utf-8', 'replace')
                    out[key] = val
                except Exception:
                    pass
            elif typ == b'IEND':
                break
            else:
                f.seek(n + 4, 1)
            read += n + 4
    return out, wh


def _inflate(data, cap=8 * 1024 * 1024):
    """zlib with a size cap: a tiny chunk must not expand to gigabytes (a 'zip bomb' in a PNG)."""
    return zlib.decompressobj().decompress(data, cap)


def _link(v):
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], (str, int)) and isinstance(v[1], int)


def _text_of(graph, ref, depth=0, seen=None):
    """Follow a conditioning / string link back to the text that was typed. Every node is visited once (a graph
    with loops or many branches must not take exponential time)."""
    if depth > 12: return ''
    if isinstance(ref, str): return ref
    if not _link(ref): return ''
    seen = set() if seen is None else seen
    nid = str(ref[0])
    if nid in seen: return ''
    seen.add(nid)
    node = graph.get(nid)
    if not isinstance(node, dict): return ''
    inp = node.get('inputs')
    if not isinstance(inp, dict): return ''
    for k in ('text', 'text_g', 'string', 'value', 'prompt', 'positive', 'text_positive', 'wildcard_text', 'populated_text'):
        if k in inp:
            v = inp[k]
            t = _text_of(graph, v, depth + 1, seen) if _link(v) else (v if isinstance(v, str) else '')
            if t: return t
    for k in ('conditioning', 'conditioning_1', 'conditioning_to', 'conditioning_from', 'clip_l', 'cond', 'positive'):
        if k in inp:
            t = _text_of(graph, inp[k], depth + 1, seen)
            if t: return t
    return ''


def _name(v):
    if not isinstance(v, str): return v
    b = re.split(r'[\\/]', v)[-1]
    return re.sub(r'\.(safetensors|ckpt|pt|pth|bin|gguf)$', '', b, flags=re.I)


def parse_comfy(prompt_json):
    """-> {param: value} friendly params + every scalar node input as 'Class#id.input'."""
    try: g = json.loads(prompt_json)
    except Exception: return {}
    if not isinstance(g, dict): return {}
    p = {}; samplers = []
    loras = {}
    for nid, node in g.items():
        if not isinstance(node, dict): continue
        ct = node.get('class_type'); ct = ct if isinstance(ct, str) else ''
        inp = node.get('inputs'); inp = inp if isinstance(inp, dict) else {}
        for k, v in inp.items():                                                # raw scalars, for "advanced" axes
            if isinstance(v, (int, float, str, bool)) and not (isinstance(v, str) and len(v) > 400):
                p[f'{ct}#{nid}.{k}'] = v
        if ct in SAMPLERS or ('seed' in inp and 'steps' in inp) or 'noise_seed' in inp:
            samplers.append((nid, node))
        if ct in ('CheckpointLoaderSimple', 'CheckpointLoader', 'CheckpointLoader|pysssss') and 'ckpt_name' in inp: p['model'] = _name(inp['ckpt_name'])
        if ct in ('UNETLoader', 'UnetLoaderGGUF') and 'unet_name' in inp: p.setdefault('model', _name(inp['unet_name']))
        if 'lora_name' in inp and isinstance(inp['lora_name'], str):
            sm = inp.get('strength_model', inp.get('strength', 1))
            loras[_name(inp['lora_name'])] = sm if not _link(sm) else '?'
        if ct == 'EmptyLatentImage' or ct.startswith('EmptySD3LatentImage') or ct.startswith('EmptyLatent'):
            for k in ('width', 'height', 'batch_size'):
                if isinstance(inp.get(k), (int, float)): p['latent_' + k] = inp[k]
        if ct in ('VAELoader',) and 'vae_name' in inp: p['vae'] = _name(inp['vae_name'])
        if 'guidance' in inp and isinstance(inp['guidance'], (int, float)) and ct.startswith('FluxGuidance'): p['guidance'] = inp['guidance']
    samplers.sort(key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0)
    for i, (nid, node) in enumerate(samplers[:3]):
        inp = node.get('inputs'); inp = inp if isinstance(inp, dict) else {}
        sfx = '' if i == 0 else f'_{i + 1}'
        for src, dst in (('seed', 'seed'), ('noise_seed', 'seed'), ('steps', 'steps'), ('cfg', 'cfg'), ('sampler_name', 'sampler'),
                         ('scheduler', 'scheduler'), ('denoise', 'denoise')):
            v = inp.get(src)
            if v is not None and not _link(v): p[dst + sfx] = v
            elif _link(v):
                ref = g.get(str(v[0])); ref = ref if isinstance(ref, dict) else {}
                ri = ref.get('inputs'); ri = ri if isinstance(ri, dict) else {}
                for kk in ('seed', 'noise_seed', 'value', 'int', 'number'):
                    vv = ri.get(kk)
                    if isinstance(vv, (int, float)): p[dst + sfx] = vv; break
        if i == 0:
            if 'positive' in inp: p['positive'] = _text_of(g, inp['positive'])
            if 'negative' in inp: p['negative'] = _text_of(g, inp['negative'])
    for name, s in loras.items(): p['lora:' + name] = s
    if loras: p['loras'] = ', '.join(sorted(loras))
    return p


def parse_a1111(text):
    """'positive\\nNegative prompt: ...\\nSteps: 20, Sampler: ..., CFG scale: 7, Seed: 1, Size: 512x512, Model: x'"""
    p = {}
    lines = text.strip().split('\n')
    last = lines[-1] if lines else ''
    if 'Steps:' in last:
        for m in re.finditer(r'\s*([\w \-/]+):\s*("(?:[^"\\]|\\.)*"|[^,]+)', last):
            k = m.group(1).strip().lower(); v = m.group(2).strip().strip('"')
            key = {'steps': 'steps', 'sampler': 'sampler', 'cfg scale': 'cfg', 'seed': 'seed', 'size': 'size', 'model': 'model',
                   'denoising strength': 'denoise', 'schedule type': 'scheduler', 'clip skip': 'clip_skip'}.get(k, 'a1111.' + k)
            try: v = int(v) if re.fullmatch(r'-?\d+', v) else float(v) if re.fullmatch(r'-?\d*\.\d+', v) else v
            except ValueError: pass
            p[key] = v
        lines = lines[:-1]
    body = '\n'.join(lines)
    if 'Negative prompt:' in body:
        pos, neg = body.split('Negative prompt:', 1); p['positive'] = pos.strip(); p['negative'] = neg.strip()
    else:
        p['positive'] = body.strip()
    for m in re.finditer(r'<lora:([^:>]+):(-?\d+(?:\.\d+)?)[^>]*>', p.get('positive', '')):
        try: p['lora:' + m.group(1)] = float(m.group(2))
        except ValueError: pass
    return p


def phrases(prompt):
    s = re.sub(r'<lora:[^>]+>', ' ', str(prompt or ''))
    out = []
    for x in re.split(r'[,\n]|(?<=\))\s+(?=\()', s):
        x = re.sub(r'\s+', ' ', x).strip()
        if x: out.append(x)
    return out


def exif_parameters(path):
    """A1111 / Forge parameters of a JPEG / WebP (EXIF UserComment) -> (text, (w, h))."""
    try:
        from PIL import Image
        with Image.open(W.lp(path)) as im:
            wh = im.size
            ex = im.getexif(); sub = ex.get_ifd(0x8769) if ex else {}
            uc = sub.get(0x9286) if sub else None
            if isinstance(uc, bytes):
                head, body = uc[:8], uc[8:]
                if head.startswith(b'UNICODE'):                       # UTF-16, byte order not stated: take the readable one
                    cands = [body.decode(e, 'replace') for e in ('utf-16-be', 'utf-16-le')]
                    ok = lambda x: sum(1 for ch in x if ' ' <= ch <= '~' or '\u4e00' <= ch <= '\u9fff' or ch in '\n\r\t')
                    t = max(cands, key=ok)
                else:
                    t = body.decode('utf-8', 'replace')
            else:
                t = str(uc or '')
            return t.strip('\x00 \n'), wh
    except Exception:
        return '', (0, 0)


def read_image(path):
    if not path.lower().endswith('.png'):
        t, (w, h) = exif_parameters(path)
        p = parse_a1111(t) if 'Steps:' in t else ({'positive': t} if t else {})
        p['width'] = w; p['height'] = h
        return p, 'Steps:' in t
    texts, (w, h) = png_texts(path)
    p = {}
    if 'prompt' in texts: p = parse_comfy(texts['prompt'])
    elif 'parameters' in texts: p = parse_a1111(texts['parameters'])
    elif 'Description' in texts or 'Comment' in texts:
        p = {'positive': texts.get('Description', '')}
    p['width'] = w; p['height'] = h
    return p, bool(texts.get('prompt') or texts.get('parameters'))


LABELS = {'seed': 'Seed', 'steps': 'Steps', 'cfg': 'CFG', 'sampler': '取樣器', 'scheduler': '排程', 'denoise': 'Denoise', 'model': '模型',
          'loras': 'LoRA 組合', 'positive': '正向提示詞', 'negative': '反向提示詞', 'width': '寬', 'height': '高', 'vae': 'VAE',
          'guidance': 'Guidance', '_pos_diff': '提示詞差異', '_file': '檔名', '_folder': '子資料夾', '_order': '產生順序', '_n': '檔名編號'}
NODE_LABELS = {'latent_width': '潛空間寬', 'latent_height': '潛空間高', 'latent_batch_size': '一次產生張數', 'batch_size': '一次產生張數',
               'size': '尺寸', 'upscale_by': '放大倍數', 'scale_by': '放大倍數', 'strength': '強度', 'clip_skip': 'CLIP Skip',
               'noise_seed': 'Seed（雜訊）', 'sampler_name': '取樣器', 'ckpt_name': '模型檔', 'lora_name': 'LoRA 檔', 'strength_model': 'LoRA 強度（模型）',
               'strength_clip': 'LoRA 強度（CLIP）', 'start_at_step': '開始步數', 'end_at_step': '結束步數', 'shift': 'Shift', 'max_shift': 'Max Shift',
               'base_shift': 'Base Shift', 'frame_rate': '影格率', 'length': '長度（影格）', 'filename_prefix': '檔名前綴'}


class ComfyScanner:
    def __init__(self, eng):
        self.eng = eng; self.lock = threading.Lock()
        self.jobs = {}                                                        # folder -> status
        CACHE.mkdir(parents=True, exist_ok=True)

    def _cache_file(self, folder, recursive):
        return CACHE / (hashlib.sha1(f'{norm(folder).lower()}|{int(recursive)}'.encode('utf-8', 'surrogatepass')).hexdigest()[:20] + '.json')

    def status(self, folder, recursive=False):
        k = (norm(folder).lower(), bool(recursive))
        return self.jobs.get(k) or {'state': 'idle'}

    def scan(self, folder, recursive=False):
        folder = norm(folder)
        if not os.path.isdir(folder): raise ValueError('找不到這個資料夾')
        k = (folder.lower(), bool(recursive))
        with self.lock:
            j = self.jobs.get(k)
            if j and j['state'] == 'running': return j
            j = self.jobs[k] = {'state': 'running', 'done': 0, 'total': 0, 't': time.time(), 'folder': folder}
        threading.Thread(target=self._run, args=(folder, recursive, j), name='HZ-Comfy', daemon=True).start()
        return j

    def _list(self, folder, recursive):
        out = []
        if recursive:
            for root, ds, fs in os.walk(folder):
                ds[:] = [d for d in ds if d != '.HotZoneVault']
                for f in fs:
                    if f.lower().endswith(EXTS): out.append(os.path.join(root, f))
        else:
            with os.scandir(W.lp(folder)) as it:
                for e in it:
                    if e.is_file() and e.name.lower().endswith(EXTS): out.append(os.path.join(folder, e.name))
        return out

    def peek(self, folder, recursive=False):
        """Cheap 'did anything change?' signature: number of PNGs + newest modification time."""
        folder = norm(folder); n = 0; newest = 0.0
        if recursive:
            for root, ds, fs in os.walk(folder):
                ds[:] = [d for d in ds if d != '.HotZoneVault']
                for f in fs:
                    if f.lower().endswith(EXTS):
                        n += 1
                        try: newest = max(newest, os.path.getmtime(os.path.join(root, f)))
                        except OSError: pass
        else:
            with os.scandir(W.lp(folder)) as it:
                for e in it:
                    if e.name.lower().endswith(EXTS):
                        try:
                            if e.is_file(): n += 1; newest = max(newest, e.stat().st_mtime)
                        except OSError: pass
        return {'n': n, 'newest': newest}

    def _run(self, folder, recursive, j):
        try:
            W.thread_background(True)
            cf = self._cache_file(folder, recursive)
            old = {}
            try:
                for it in json.loads(cf.read_text(encoding='utf-8')).get('images', []): old[it['path']] = it
            except Exception:
                pass
            files = self._list(folder, recursive); j['total'] = len(files)
            images = []
            for i, p in enumerate(files):
                try: st = os.stat(W.lp(p))
                except OSError: continue
                o = old.get(p)
                if o and o.get('mtime') == st.st_mtime and o.get('size') == st.st_size:
                    images.append(o)
                else:
                    try: params, has = read_image(p)
                    except Exception: params, has = {}, False
                    images.append({'path': p, 'name': os.path.basename(p), 'mtime': st.st_mtime, 'size': st.st_size, 'meta': has, 'p': params})
                j['done'] = i + 1
            tmp = cf.with_suffix('.tmp'); tmp.write_text(json.dumps({'folder': folder, 'images': images}, ensure_ascii=False), encoding='utf-8'); os.replace(tmp, cf)
            j.update(state='done', t_done=time.time())
        except Exception as e:
            self.eng.log.exc('comfy', folder); j.update(state='error', msg=str(e))

    def data(self, folder, recursive=False):
        """Everything the grid page needs: images with their params + which params vary."""
        cf = self._cache_file(folder, recursive)
        try: d = json.loads(cf.read_text(encoding='utf-8'))
        except Exception: return None
        imgs = sorted(d['images'], key=lambda x: (x['mtime'], x['name']))
        folder = norm(folder)
        # derived params
        all_ph = [set(phrases(it['p'].get('positive', ''))) for it in imgs]
        common = set.intersection(*all_ph) if all_ph else set()
        order_ph = {}
        for it in imgs:
            for x in phrases(it['p'].get('positive', '')): order_ph.setdefault(x, len(order_ph))
        for i, it in enumerate(imgs):
            p = it['p']
            diff = [x for x in phrases(p.get('positive', '')) if x not in common]
            p['_pos_diff'] = ', '.join(diff) if diff else '（相同）'
            p['_file'] = it['name']
            rel = os.path.relpath(os.path.dirname(it['path']), folder)
            p['_folder'] = '' if rel == '.' else rel
            p['_order'] = i
            m = re.findall(r'\d+', it['name']); p['_n'] = int(m[-1]) if m else i
            for x in diff[:40]: p['phrase:' + x] = 1                            # each varying phrase as on / off
        # which params vary
        stats = {}
        for it in imgs:
            for k, v in it['p'].items():
                s = stats.setdefault(k, {'vals': {}, 'n': 0})
                s['n'] += 1
                key = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
                if len(s['vals']) <= 2000: s['vals'][key] = s['vals'].get(key, 0) + 1
        n = len(imgs); params = []
        for k, s in stats.items():
            nv = len(s['vals']) + (1 if s['n'] < n else 0)
            if k.startswith('phrase:'): nv = 2 if s['n'] < n else 1
            if nv <= 1 and k not in ('positive',): continue
            if k in ('_order', '_file') or (k.startswith('_n') and nv == n): kind = 'id'
            else: kind = 'num' if all(re.fullmatch(r'-?\d+(\.\d+)?', str(x)) for x in s['vals']) else 'text'
            base = k.rsplit('.', 1)[-1].rsplit(':', 1)[-1]
            label = LABELS.get(k) or (('含「' + k[7:] + '」') if k.startswith('phrase:') else ('LoRA ' + k[5:] if k.startswith('lora:')
                     else (f'{NODE_LABELS[base]}（{k}）' if base in NODE_LABELS else k)))
            group = 'main' if k in LABELS or k.startswith('lora:') else 'phrase' if k.startswith('phrase:') else 'node'
            params.append({'key': k, 'label': label, 'distinct': nv, 'kind': kind, 'group': group, 'n': s['n']})
        # node-level params that just repeat a main param (KSampler#3.seed == seed) are hidden
        sig = lambda k: tuple(json.dumps(it['p'].get(k), ensure_ascii=False) for it in imgs)
        main_sigs = {sig(x['key']) for x in params if x['group'] == 'main'}
        params = [x for x in params if x['group'] != 'node' or sig(x['key']) not in main_sigs]
        rank = {'_pos_diff': 0, 'seed': 1, 'cfg': 2, 'steps': 3, 'sampler': 4, 'scheduler': 5, 'denoise': 6, 'model': 7, 'loras': 8}
        params.sort(key=lambda x: ({'main': 0, 'phrase': 1, 'node': 2}[x['group']], rank.get(x['key'], 50), x['label']))
        keep = {x['key'] for x in params} | {'positive', 'negative', 'seed', 'cfg', 'steps', 'sampler', 'scheduler', 'model', 'width', 'height', 'loras'}
        out = [{'path': it['path'], 'name': it['name'], 'mtime': it['mtime'], 'meta': it.get('meta', False),
                'p': {k: v for k, v in it['p'].items() if k in keep}} for it in imgs]
        return {'folder': folder, 'images': out, 'params': params, 'with_meta': sum(1 for x in imgs if x.get('meta')), 'common_prompt': ', '.join(x for x in order_ph if x in common)}

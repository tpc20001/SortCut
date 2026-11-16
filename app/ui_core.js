/* HotZone FM — core: api, helpers, dialogs, menus, router, sidebar, polling, desktop bridge */
'use strict';
(function () {                                       // append(a, null, b): skip the empty parts (used a lot with conditions)
  const ap = Element.prototype.append;
  Element.prototype.append = function (...a) { return ap.apply(this, a.filter(x => x != null && x !== false)); };
})();
const HZ = window.HZ = {pages: {}, st: null, clip: null, bridge: null, local: false, cur: null, me: null, polls: {}, lastOk: Date.now()};

/* ------------------------------------------------------------------ helpers */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
HZ.esc = esc;
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v; else if (k === 'html') e.innerHTML = v; else if (k === 'text') e.textContent = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else if (k === 'style' && typeof v === 'object') Object.assign(e.style, v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(k));
  return e;
}
HZ.h = h;
HZ.fmtSize = function (n) {
  if (n == null || n < 0) return '';
  const u = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']; let i = 0; n = +n;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return i === 0 ? Math.round(n) + ' B' : (n >= 100 ? n.toFixed(0) : n >= 10 ? n.toFixed(1) : n.toFixed(2)) + ' ' + u[i];
};
HZ.fmtRate = n => n > 0 ? HZ.fmtSize(n) + '/s' : '—';
HZ.fmtDate = function (t) {
  if (!t) return ''; const d = new Date(t * 1000), p = x => String(x).padStart(2, '0');
  return `${d.getFullYear()}/${p(d.getMonth() + 1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};
HZ.fmtAgo = function (t) {
  if (!t) return ''; const s = Date.now() / 1000 - t;
  if (s < 60) return '剛剛'; if (s < 3600) return Math.floor(s / 60) + ' 分鐘前'; if (s < 86400) return Math.floor(s / 3600) + ' 小時前';
  return Math.floor(s / 86400) + ' 天前';
};
HZ.fmtEta = function (s) {
  if (s == null || !isFinite(s)) return ''; s = Math.round(s);
  if (s < 60) return s + ' 秒'; if (s < 3600) return Math.floor(s / 60) + ' 分 ' + (s % 60) + ' 秒';
  return Math.floor(s / 3600) + ' 小時 ' + Math.floor(s % 3600 / 60) + ' 分';
};
HZ.base = p => { const s = String(p).replace(/[\\/]+$/, ''); const i = Math.max(s.lastIndexOf('\\'), s.lastIndexOf('/')); return i >= 0 ? s.slice(i + 1) || s : s; };
HZ.dir = p => { const s = String(p).replace(/[\\/]+$/, ''); const i = Math.max(s.lastIndexOf('\\'), s.lastIndexOf('/')); if (i < 0) return ''; const d = s.slice(0, i); return /^[A-Za-z]:$/.test(d) ? d + '\\' : (d || '/'); };
HZ.sep = p => (String(p).includes('\\') || /^[A-Za-z]:/.test(p)) ? '\\' : '/';
HZ.join = (a, b) => { const s = HZ.sep(a); return a.endsWith(s) ? a + b : a + s + b; };
HZ.drive = p => { const m = /^([A-Za-z]:)/.exec(p || ''); return m ? m[1].toUpperCase() : ''; };
HZ.sameVol = (a, b) => HZ.drive(a) && HZ.drive(a) === HZ.drive(b);
HZ.isUnder = (p, f) => { const a = String(p).toLowerCase(), b = String(f).toLowerCase().replace(/[\\/]+$/, ''); return a === b || a.startsWith(b + '\\') || a.startsWith(b + '/'); };
HZ.pointer = false;
document.addEventListener('pointerdown', e => { HZ.pointer = e.target; }, true);
/* long-press = right-click on phones (iPhone Safari never sends 'contextmenu'; Android does, then ours stays quiet) */
(function () {
  let t = null, x0 = 0, y0 = 0, tgt = null, fired = false;
  const clear = () => { clearTimeout(t); t = null; };
  document.addEventListener('touchstart', e => {
    if (e.touches.length !== 1) return clear();
    const p = e.touches[0]; x0 = p.clientX; y0 = p.clientY; tgt = e.target; fired = false; clear();
    t = setTimeout(() => {
      t = null; fired = true;
      tgt.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: x0, clientY: y0, button: 2}));
      if (navigator.vibrate) try { navigator.vibrate(15); } catch (er) { }
    }, 550);
  }, {passive: true});
  document.addEventListener('touchmove', e => { const p = e.touches[0]; if (p && Math.hypot(p.clientX - x0, p.clientY - y0) > 10) clear(); }, {passive: true});
  document.addEventListener('touchend', e => { clear(); if (fired) { e.preventDefault(); fired = false; } }, {passive: false});
  document.addEventListener('contextmenu', e => { if (t && e.isTrusted) clear(); }, true);   // the browser did it itself
})();
document.addEventListener('pointerup', () => setTimeout(() => { HZ.pointer = false; }, 80), true);
document.addEventListener('pointerdown', e => { HZ.lastPointer = e.pointerType; }, true);   // 'touch' -> one tap opens (phone)
/* true while the user is interacting with something inside el (do not rebuild it under their mouse / typing) */
HZ.isBusy = function (el) {
  if (!el) return false;
  if (HZ.pointer && el.contains(HZ.pointer)) return true;
  const a = document.activeElement;
  return !!(a && el.contains(a) && (a.tagName === 'TEXTAREA' || (a.tagName === 'INPUT' && /^(text|number|password|search|)$/.test(a.type))));
};
HZ.debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
/* Thumbnails in big folders: <img data-src> load only when on screen, at most 3 at a time (the browser has 6
   connections per host: hundreds of queued thumbnails made the next folder listing wait seconds). Images that left the
   page (another folder) are dropped from the queue and their download is cancelled. */
HZ.thumbQ = {wait: [], busy: new Set(), MAX: 3};
HZ.pumpThumbs = function () {
  const Q = HZ.thumbQ;
  for (const im of [...Q.busy]) if (!im.isConnected) { Q.busy.delete(im); im.removeAttribute('src'); }
  Q.wait = Q.wait.filter(im => im.isConnected);
  while (Q.busy.size < Q.MAX && Q.wait.length) {
    const im = Q.wait.shift(), done = () => { Q.busy.delete(im); HZ.pumpThumbs(); };
    Q.busy.add(im);
    im.addEventListener('load', done, {once: true}); im.addEventListener('error', done, {once: true});
    im.src = im.dataset.src; delete im.dataset.src;
  }
};
HZ.thumbIO = 'IntersectionObserver' in window ? new IntersectionObserver(es => {
  for (const e of es) if (e.isIntersecting) { HZ.thumbIO.unobserve(e.target); if (e.target.dataset.src) HZ.thumbQ.wait.push(e.target); }
  HZ.pumpThumbs();
}, {rootMargin: '300px'}) : null;
HZ.lazyThumbs = function (root) {
  for (const im of root.querySelectorAll('img[data-src]')) { if (HZ.thumbIO) HZ.thumbIO.observe(im); else { im.src = im.dataset.src; delete im.dataset.src; } }
  HZ.pumpThumbs();
};

/* ------------------------------------------------------------------ api */
HZ.api = async function (method, path, body, opts = {}) {
  const init = {method, headers: {'X-HZ': '1'}, credentials: 'same-origin', signal: opts.signal};
  if (body !== undefined) {
    if (body instanceof Blob || body instanceof ArrayBuffer) { init.body = body; init.headers['Content-Type'] = 'application/octet-stream'; }
    else { init.body = JSON.stringify(body); init.headers['Content-Type'] = 'application/json'; }
  }
  let r;
  try { r = await fetch(path, init); } catch (e) { if (e.name === 'AbortError') throw e; HZ.offline(true); throw new Error('連不到背景引擎'); }
  HZ.offline(false);
  let j = null; try { j = await r.json(); } catch (e) { }
  if (r.status === 401 && !opts.noLogin) {
    let again = false; try { again = !sessionStorage.getItem('hz.relogin'); sessionStorage.setItem('hz.relogin', '1'); } catch (e) { }
    if (HZ.bridge && HZ.bridge.relogin && again) { HZ.bridge.relogin(); throw new Error('重新登入中…'); }   // desktop window: log in again by itself
    HZ.showLogin(); throw new Error('請先登入');
  }
  if (!r.ok || (j && j.ok === false)) throw new Error((j && j.error) || ('錯誤 ' + r.status));
  return j;
};
HZ.get = (p, q, opts) => HZ.api('GET', p + (q ? '?' + new URLSearchParams(q) : ''), undefined, opts);
HZ.post = (p, b) => HZ.api('POST', p, b || {});
HZ.offline = function (on) {
  const c = $('#conn');
  if (on) { if (!HZ._off) { HZ._off = Date.now(); } c.innerHTML = '<span class="warn">● 重新連線中…</span>'; document.title = '（離線）HotZone FM'; }
  else if (HZ._off) { HZ._off = 0; c.textContent = ''; document.title = 'HotZone FM'; }
};

/* ------------------------------------------------------------------ toasts / dialogs */
HZ.toast = function (msg, kind = '', ms = 3500) {
  const t = h('div', {class: 'toast ' + kind, html: msg}); $('#toasts').append(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; setTimeout(() => t.remove(), 320); }, ms);
};
HZ.err = e => HZ.toast(esc(e && e.message || e), 'bad', 5000);
HZ.dialog = function ({title, body, buttons = [{text: '確定', value: true, primary: true}], width, onopen, dismiss = true, pos = ''}) {
  return new Promise(res => {
    const ov = $('#overlay'); ov.innerHTML = '';
    const P = {tl: ['flex-start', 'flex-start'], tr: ['flex-start', 'flex-end'], bl: ['flex-end', 'flex-start'], br: ['flex-end', 'flex-end']}[pos] || ['center', 'center'];
    ov.style.alignItems = P[0]; ov.style.justifyContent = P[1]; ov.style.padding = pos ? '40px' : '';
    const back = HZ._dlgClose ? HZ._dlgBack : document.activeElement;     // focus goes back there when the dialog closes
    if (HZ._dlgClose) HZ._dlgClose(null, true);                                // a new dialog replaces the old one: settle it
    HZ._dlgBack = back;
    const close = (v, replaced) => {
      if (HZ._dlgClose === close) HZ._dlgClose = null;
      if (!replaced) { ov.classList.remove('on'); ov.innerHTML = ''; if (back && back.isConnected && back !== document.body) try { back.focus({preventScroll: true}); } catch (e) { } }
      document.removeEventListener('keydown', key, true); res(v);
    };
    HZ._dlgClose = close;
    const df = h('div', {class: 'df'});
    for (const b of buttons) df.append(h('button', {class: b.primary ? 'primary' : (b.cls || ''), onclick: () => close(typeof b.value === 'function' ? b.value() : b.value)}, b.text));
    const db = h('div', {class: 'db'}); if (typeof body === 'string') db.innerHTML = body; else if (body) db.append(body);
    const d = h('div', {class: 'dlg', style: width ? {width: typeof width === 'number' ? width + 'px' : width} : null}, h('div', {class: 'dh', text: title || ''}), db, df);
    ov.append(d); ov.classList.add('on');
    ov.onclick = e => { if (e.target === ov && dismiss) close(null); };
    const key = e => {
      if (e.key === 'Escape' && dismiss) { e.preventDefault(); close(null); }
      else if (e.key === 'Enter' && !e.shiftKey && e.target.tagName !== 'TEXTAREA') { const p = buttons.find(b => b.primary); if (p) { e.preventDefault(); close(typeof p.value === 'function' ? p.value() : p.value); } }
    };
    document.addEventListener('keydown', key, true);
    if (onopen) onopen(d, close);
    const f = d.querySelector('input,textarea,select'); if (f) setTimeout(() => { f.focus(); if (f.select) f.select(); }, 30);
  });
};
HZ.alert = (title, msg) => HZ.dialog({title, body: msg});
HZ.confirm = (title, msg, ok = '確定', danger = false) => HZ.dialog({title, body: msg, buttons: [{text: '取消', value: false}, {text: ok, value: true, primary: true, cls: danger ? 'primary' : ''}]});
HZ.prompt = function (title, label, value = '', ok = '確定') {
  const inp = h('input', {value, style: {width: '100%'}});
  return HZ.dialog({title, body: h('div', {class: 'col'}, h('div', {class: 'muted', text: label}), inp),
    buttons: [{text: '取消', value: null}, {text: ok, primary: true, value: () => inp.value}],
    onopen: () => { const i = value.lastIndexOf('.'); setTimeout(() => { inp.focus(); inp.setSelectionRange(0, i > 0 ? i : value.length); }, 40); }});
};

/* ------------------------------------------------------------------ context menu / tooltip */
HZ.menu = function (x, y, items) {
  const m = $('#ctx'); m.innerHTML = '';
  for (const it of items) {
    if (!it) continue;
    if (it === '-') { if (m.lastChild && !m.lastChild.classList.contains('msep')) m.append(h('div', {class: 'msep'})); continue; }
    const d = h('div', {class: 'mi' + (it.disabled ? ' dis' : '')}, h('span', {class: 'ic', text: it.icon || ''}), h('span', {text: it.text}), it.key ? h('span', {class: 'k', text: it.key}) : null);
    d.onclick = e => { e.stopPropagation(); HZ.closeMenu(); it.run && it.run(); };
    m.append(d);
  }
  if (m.lastChild && m.lastChild.classList.contains('msep')) m.lastChild.remove();
  m.classList.add('on');
  const r = m.getBoundingClientRect(), W = innerWidth, H = innerHeight;
  m.style.left = Math.min(x, W - r.width - 6) + 'px'; m.style.top = Math.min(y, H - r.height - 6) + 'px';
};
HZ.closeMenu = () => $('#ctx').classList.remove('on');
document.addEventListener('mousedown', e => { if (!e.target.closest('#ctx')) HZ.closeMenu(); });
window.addEventListener('blur', HZ.closeMenu);
document.addEventListener('keydown', e => {                                // Escape closes an open context menu (first)
  if (e.key === 'Escape' && $('#ctx').classList.contains('on')) { HZ.closeMenu(); e.preventDefault(); e.stopPropagation(); }
}, true);
HZ.tip = function (e, html) {
  const t = $('#tip'); if (!html) { t.style.display = 'none'; return; }
  t.innerHTML = html; t.style.display = 'block';
  const r = t.getBoundingClientRect();
  t.style.left = Math.min(e.clientX + 14, innerWidth - r.width - 8) + 'px'; t.style.top = Math.min(e.clientY + 14, innerHeight - r.height - 8) + 'px';
};

/* ------------------------------------------------------------------ icons */
const EXT_KIND = {};
for (const [k, list] of Object.entries({
  video: 'mp4 mkv avi mov wmv flv ts m2ts mts webm mpg mpeg m4v 3gp rmvb vob', audio: 'mp3 wav flac aac m4a ogg wma opus ape aiff',
  image: 'jpg jpeg png gif bmp webp tif tiff heic heif raw cr2 cr3 nef arw dng psd svg ico avif', doc: 'doc docx odt rtf pdf txt md epub',
  sheet: 'xls xlsx ods csv tsv', slide: 'ppt pptx odp key', zip: 'zip rar 7z tar gz tgz bz2 xz zst iso cab', exe: 'exe msi bat cmd ps1 com scr dll sys',
  code: 'py js ts html htm css json xml c cpp h java cs go rs sql sh yaml yml toml ini cfg', sub: 'srt ass vtt lrc nfo'})) for (const e of list.split(' ')) EXT_KIND[e] = k;
const KIND_COLOR = {video: '#ff5d8f', audio: '#b48cff', image: '#45d483', doc: '#4aa3ff', sheet: '#2fb36b', slide: '#ff8a3d', zip: '#e8b34b', exe: '#8994a4', code: '#43d9ff', sub: '#c9a96e', file: '#7f8a99'};
const KIND_LABEL = {video: '影片', audio: '音訊', image: '圖片', doc: '文件', sheet: '試算表', slide: '簡報', zip: '壓縮檔', exe: '程式', code: '程式碼', sub: '字幕', file: '檔案'};
HZ.kind = ext => EXT_KIND[(ext || '').toLowerCase()] || 'file';
HZ.typeLabel = (it) => it.dir ? '資料夾' : ((it.ext ? it.ext.toUpperCase() + ' ' : '') + KIND_LABEL[HZ.kind(it.ext)]);
const _icons = {};
HZ.icon = function (it, big) {
  const key = (it.dir ? (it.hot ? 'hotdir' : 'dir') : HZ.kind(it.ext)) + (big ? 'B' : '');
  if (_icons[key]) return _icons[key];
  let svg;
  if (it.dir) {
    const c = it.hot ? 'var(--hot)' : 'var(--folder)';
    svg = `<svg class="ico" viewBox="0 0 24 24"><path d="M2 6.5A1.5 1.5 0 0 1 3.5 5h5l2 2h10A1.5 1.5 0 0 1 22 8.5v10a1.5 1.5 0 0 1-1.5 1.5h-17A1.5 1.5 0 0 1 2 18.5z" fill="${c}"/><path d="M2 9h20v9.5a1.5 1.5 0 0 1-1.5 1.5h-17A1.5 1.5 0 0 1 2 18.5z" fill="${c}" opacity=".75"/>${it.hot ? '<path d="M12 10.5c1.6 1.4 2.6 2.6 2.6 4.1a2.6 2.6 0 0 1-5.2 0c0-.9.4-1.6 1-2.2.1.7.5 1.1 1 1.2-.2-1.2.1-2.2.6-3.1z" fill="#fff"/>' : ''}</svg>`;
  } else {
    const k = HZ.kind(it.ext), c = KIND_COLOR[k];
    const glyph = {video: '<path d="M10 11v5l4.2-2.5z" fill="#fff"/>', audio: '<circle cx="11" cy="16" r="1.8" fill="#fff"/><path d="M12.6 16V10.5l3 .8" stroke="#fff" stroke-width="1.3" fill="none"/>',
      image: '<path d="M7.5 18l3-4 2 2.5 1.5-2 2.5 3.5z" fill="#fff"/><circle cx="10" cy="11.5" r="1.2" fill="#fff"/>', zip: '<path d="M11 7h2v1.5h-2zM11 9.5h2V11h-2zM11 12h2v3h-2z" fill="#fff"/>',
      exe: '<rect x="7.5" y="11" width="9" height="6" rx="1" fill="none" stroke="#fff" stroke-width="1.3"/>', code: '<path d="M10 11.5l-2 2 2 2M14 11.5l2 2-2 2" stroke="#fff" stroke-width="1.3" fill="none"/>'}[k] ||
      '<path d="M8 12h8M8 14.5h8M8 17h5" stroke="#fff" stroke-width="1.2"/>';
    svg = `<svg class="ico" viewBox="0 0 24 24"><path d="M5 2.5h9.5L19 7v13a1.5 1.5 0 0 1-1.5 1.5h-12A1.5 1.5 0 0 1 4 20V4a1.5 1.5 0 0 1 1-1.5z" fill="${c}"/><path d="M14.5 2.5V7H19" fill="#000" opacity=".25"/>${glyph}</svg>`;
  }
  return (_icons[key] = svg);
};

/* ------------------------------------------------------------------ desktop bridge (PySide6 window) */
HZ.initBridge = function () {
  if (!(window.qt && qt.webChannelTransport)) return;
  const go = () => new QWebChannel(qt.webChannelTransport, ch => { HZ.bridge = ch.objects.hz; HZ.toast('已連接桌面視窗（可拖放檔案、使用 Windows 剪貼簿）', 'ok', 2500); });
  if (window.QWebChannel) return go();                                  // injected by the window (hz_shell)
  const s = document.createElement('script'); s.src = 'qrc:///qtwebchannel/qwebchannel.js';   // older window shells
  s.onload = go; document.head.append(s);
};
HZ.bcall = (name, ...args) => new Promise(res => { try { HZ.bridge[name](...args, r => res(r)); } catch (e) { res(null); } });
/* called by the desktop window when files are dropped from Windows Explorer */
window.hzDrop = function (paths, x, y, mods) {
  const el = document.elementFromPoint(x, y);
  const target = HZ.dropTargetAt(el);
  if (!target) { HZ.toast('請拖到資料夾或檔案清單上'); return; }
  HZ.dropPaths(paths, target, mods || '');
};
HZ.dropTargetAt = function (el) {
  if (!el) return null;
  const d = el.closest('[data-drop]'); return d ? d.getAttribute('data-drop') : null;
};
HZ.dropPaths = function (paths, target, mods) {
  const nrm = p => String(p).toLowerCase().replace(/[\\/]+$/, '');
  paths = (paths || []).filter(p => p && !HZ.isUnder(target, p));                 // a folder cannot go into itself
  if (!paths.length) return;
  const copy = mods.includes('ctrl'), move = mods.includes('shift');
  if (!copy && paths.every(p => nrm(HZ.dir(p)) === nrm(target))) return;         // dropped where it already is
  const isMove = move ? true : copy ? false : HZ.sameVol(paths[0], target);         // like Windows: same drive = move, other drive = copy
  HZ.queueAdd(isMove ? 'move' : 'copy', paths, target);
};
/* ------------------------------------------------------------------ shared file actions */
HZ.queueAdd = async function (kind, src, dst, opts) {
  try {
    const r = await HZ.post('/api/queue/add', {kind, src, dst, opts});
    const j = r.job, n = src.length;
    const what = {copy: '複製', move: '移動', delete: '永久刪除', recycle: '刪除到資源回收筒', vault: '刪除（放進保管區）'}[kind];
    if (j.same && kind === 'move') HZ.toast(`已移動 ${n} 個項目${j.hot ? '　🔥 熱處理：背景會把它搬到外圈' : ''}`, j.hot ? 'hot' : 'ok');
    else HZ.toast(`${what} ${n} 個項目已加入佇列${j.hot ? '　🔥 熱處理優先' : ''}`, j.hot ? 'hot' : 'ok');
    setTimeout(() => HZ.refreshViews(), kind === 'move' && j.same ? 300 : 1200);
    return r;
  } catch (e) { HZ.err(e); }
};
HZ.refreshViews = () => { for (const p of Object.values(HZ.pages)) if (p.onFsChange) try { p.onFsChange(); } catch (e) { } };
HZ.openItem = async function (it) {
  if (it.dir) { HZ.go('explorer'); HZ.pages.explorer.open(it.path); return; }
  if (HZ.bridge) { HZ.bridge.openLocal(it.path); return; }
  if (HZ.local) { try { await HZ.post('/api/system/open', {path: it.path}); } catch (e) { HZ.err(e); } return; }
  HZ.previewDialog(it);
};
HZ.reveal = async function (path) {
  if (HZ.bridge) return HZ.bridge.reveal(path);
  if (HZ.local) return HZ.post('/api/system/open', {path, how: 'reveal'}).catch(HZ.err);
  HZ.go('explorer'); HZ.pages.explorer.open(HZ.dir(path), HZ.base(path));
};
HZ.fileUrl = (p, dl) => '/api/file?' + new URLSearchParams({path: p, dl: dl ? '1' : '0'});
HZ.download = function (items) {
  if (items.length === 1 && !items[0].dir) { const a = h('a', {href: HZ.fileUrl(items[0].path, true), download: items[0].name}); document.body.append(a); a.click(); a.remove(); return; }
  const qs = JSON.stringify(items.map(i => i.path));
  if (qs.length < 6000) { location.href = '/api/zip?' + new URLSearchParams({paths: qs}); return; }
  HZ.post('/api/zip/prepare', {paths: items.map(i => i.path)}).then(r => { location.href = '/api/zip?' + new URLSearchParams({id: r.id}); }).catch(HZ.err);   // long lists
};
HZ.previewDialog = async function (it) {
  let body;
  try {
    const p = await HZ.get('/api/preview', {path: it.path});
    const url = HZ.fileUrl(it.path);
    if (p.kind === 'image') body = `<img src="${url}" style="max-width:100%;max-height:70vh;display:block;margin:auto">`;
    else if (p.kind === 'video') body = `<video src="${url}" controls autoplay style="max-width:100%;max-height:70vh;display:block;margin:auto"></video>`;
    else if (p.kind === 'audio') body = `<audio src="${url}" controls autoplay style="width:100%"></audio>`;
    else if (p.kind === 'pdf') body = `<iframe src="${url}" style="width:80vw;height:70vh;border:0"></iframe>`;
    else if (p.kind === 'text') body = `<pre style="white-space:pre-wrap;max-height:65vh;overflow:auto;font-size:12px">${esc(p.text)}</pre>${p.truncated ? '<div class="muted small">（只顯示開頭）</div>' : ''}`;
    else body = `<div class="muted">這種檔案無法預覽（${HZ.fmtSize(p.size)}）</div>`;
  } catch (e) { body = esc(e.message); }
  const r = await HZ.dialog({title: it.name, body, width: 'min(900px,94vw)', buttons: [{text: '下載', value: 'dl'}, {text: '關閉', value: null, primary: true}]});
  if (r === 'dl') HZ.download([it]);
};
HZ.copyText = async function (t) {
  try { await navigator.clipboard.writeText(t); HZ.toast('已複製：' + esc(t.length > 80 ? t.slice(0, 80) + '…' : t)); }
  catch (e) { const ta = h('textarea', {value: t}); document.body.append(ta); ta.select(); document.execCommand('copy'); ta.remove(); HZ.toast('已複製'); }
};
HZ.setClip = function (op, items) {
  HZ.clip = {op, paths: items.map(i => i.path), t: Date.now()};
  if (HZ.bridge) HZ.bridge.setClipboardFiles(JSON.stringify(HZ.clip.paths), op === 'cut');
  HZ.toast(`${op === 'cut' ? '剪下' : '複製'} ${items.length} 個項目　→ 到目的地按 Ctrl+V 貼上`);
  HZ.refreshViews();
};
HZ.paste = async function (dst) {
  let clip = HZ.clip;
  if (HZ.bridge) {                                       // files copied in Windows Explorer
    const r = await HZ.bcall('clipboardFiles');
    try {
      const w = JSON.parse(r || '{}');
      if (w.paths && w.paths.length && (!clip || JSON.stringify(w.paths) !== JSON.stringify(clip.paths))) clip = {op: w.cut ? 'cut' : 'copy', paths: w.paths};
    } catch (e) { }
  }
  if (!clip || !clip.paths.length) { HZ.toast('剪貼簿是空的'); return; }
  const kind = clip.op === 'cut' ? 'move' : 'copy';
  await HZ.queueAdd(kind, clip.paths, dst);
  if (kind === 'move') HZ.clip = null;
};
/* what the page showed for each item: the server refuses an action on a row that is no longer that file */
HZ.vaultDays = () => (HZ.settings && HZ.settings['vault.days']) || 30;
HZ.expectOf = items => {
  const e = {};
  for (const i of items) if (i && i.path && typeof i.mtime === 'number' && i.mtime > 0 && (i.dir || (typeof i.size === 'number' && i.size >= 0)))
    e[i.path] = [i.dir ? -1 : i.size, i.mtime];
  return e;
};
HZ.deleteItems = async function (items, permanent) {
  if (!items.length) return;
  const names = items.slice(0, 6).map(i => '・' + esc(i.name)).join('<br>') + (items.length > 6 ? `<br>… 共 ${items.length} 個` : '');
  if (permanent) return HZ.permanentDelete(items, names);
  const ok = await HZ.confirm('刪除（放進保管區）', `${names}<br><br><span class="muted">會先移到這顆硬碟的保管區，${HZ.vaultDays()} 天內可以在「保管區」還原（或馬上按 Ctrl+Z）。<br>要真的永久刪除請按 Shift+Del。</span>`, '刪除');
  if (!ok) return;
  HZ.queueAdd('vault', items.map(i => i.path), null, {reason: '你按了刪除', expect: HZ.expectOf(items)});
};
/* permanent delete: three confirmations at three different places on the screen, then it is really gone */
HZ.permanentDelete = async function (items, names) {
  const total = items.reduce((a, i) => a + (i.size > 0 ? i.size : 0), 0);
  const steps = [
    {pos: 'tl', title: '永久刪除（第 1 次確認）', body: `<b class="bad">永久刪除不會放進保管區，刪了就找不回來。</b><br><br>${names}`, ok: '我要永久刪除'},
    {pos: 'br', title: '永久刪除（第 2 次確認）', body: `一共 <b>${items.length}</b> 個項目${total ? '，' + HZ.fmtSize(total) : ''}。<br>確定不需要保留任何備份？`, ok: '確定，不用保留'},
    {pos: 'tr', title: '永久刪除（最後確認）', body: `最後一次：真的要永久刪除這 <b>${items.length}</b> 個項目嗎？`, ok: `永久刪除 ${items.length} 個`},
  ];
  for (const st of steps) {
    const r = await HZ.dialog({title: st.title, body: st.body, pos: st.pos, buttons: [{text: '取消', value: false, primary: true}, {text: st.ok, value: true, cls: 'danger'}]});
    if (r !== true) { HZ.toast('已取消，沒有刪除任何東西'); return; }
  }
  HZ.queueAdd('delete', items.map(i => i.path), null, {confirmed: 3, expect: HZ.expectOf(items)});
};
HZ.renameItem = async function (it) {
  const n = await HZ.prompt('重新命名', it.path, it.name);
  if (!n || n === it.name) return null;
  try { const r = await HZ.post('/api/op', {op: 'rename', path: it.path, name: n, expect: HZ.expectOf([it])[it.path]}); HZ.refreshViews(); return r && r.path ? HZ.base(r.path) : n; }
  catch (e) { HZ.err(e); return null; }
};
HZ.markHot = async function (path, on) {
  try {
    await HZ.post('/api/hot/folder', {act: on ? 'add' : 'remove', path});
    HZ.toast(on ? `🔥 已標記熱處理：${esc(path)}<br><span class="muted">背景會把裡面的檔案慢慢搬到硬碟外圈</span>` : '已取消熱處理', on ? 'hot' : '');
    HZ.refreshViews(); HZ.poll();
  } catch (e) { HZ.err(e); }
};
HZ.props = async function (it) {
  try {
    const p = await HZ.get('/api/props', {path: it.path});
    const a = p.attrs, L = p.layout;
    let lay = '';
    if (L && !L.error && !L.resident) {
      lay = `<b>硬碟位置</b><span>${L.inside_pct != null ? `<span class="hot">外圈熱區 ${L.inside_pct}%</span>　` : ''}${L.fragments} 段　起點在 ${L.start_pct}%（0% = 最外圈）
        <div class="locbar">${L.zone_gb ? `<u style="width:${Math.min(100, L.zone_gb * 1073741824 / ((HZ.volTotal(it.path) || 1)) * 100)}%"></u>` : ''}<i style="left:${L.start_pct}%"></i></div></span>`;
    } else if (L && L.resident) lay = '<b>硬碟位置</b><span class="muted">檔案很小，直接存在 MFT 裡</span>';
    else if (L && L.error) lay = `<b>硬碟位置</b><span class="muted">${esc(L.error)}</span>`;
    const body = `<div class="kv">
      <b>名稱</b><span>${esc(p.name)}</span><b>位置</b><span class="ell" title="${esc(p.path)}">${esc(HZ.dir(p.path))}</span>
      <b>大小</b><span>${HZ.fmtSize(p.size)}（${(+p.size).toLocaleString()} 位元組）${p.from_index ? ' <span class="muted">（索引）</span>' : ''}</span>
      ${p.files != null ? `<b>內含</b><span>${(+p.files).toLocaleString()} 個檔案</span>` : ''}
      <b>建立</b><span>${HZ.fmtDate(p.ctime)}</span><b>修改</b><span>${HZ.fmtDate(p.mtime)}</span><b>存取</b><span>${HZ.fmtDate(p.atime)}</span>
      <b>屬性</b><span>${[a.readonly && '唯讀', a.hidden && '隱藏', a.system && '系統', a.compressed && '壓縮', a.sparse && '疏鬆'].filter(Boolean).join('、') || '—'}</span>
      <b>熱處理</b><span>${p.hot ? '<span class="hot">🔥 在熱資料夾裡</span>' : '—'}</span>${lay}</div>`;
    const btns = [{text: '複製路徑', value: 'copy'}];
    if (HZ.bridge) btns.push({text: 'Windows 內容', value: 'win'});
    btns.push({text: '關閉', value: null, primary: true});
    const r = await HZ.dialog({title: '內容', body, buttons: btns, width: '520px'});
    if (r === 'copy') HZ.copyText(p.path); else if (r === 'win') HZ.bridge.properties(p.path);
  } catch (e) { HZ.err(e); }
};
HZ.volTotal = function (p) {
  const d = HZ.drive(p); const v = (HZ.vols || []).find(v => v.letter === d); return v ? v.total : 0;
};
/* menu entries for a selection; ctx: {dir, pane} */
HZ.itemMenu = function (items, ctx = {}) {
  const one = items.length === 1 ? items[0] : null, n = items.length;
  const dirOnly = one && one.dir;
  const hotFolders = (HZ.hotFolders || []).map(f => f.path.toLowerCase());
  const isHotRoot = dirOnly && hotFolders.includes(one.path.toLowerCase());
  const other = ctx.pane && HZ.pages.explorer.otherPane(ctx.pane);
  return [
    one && {icon: dirOnly ? '📂' : '▶', text: dirOnly ? '開啟' : (HZ.bridge || HZ.local ? '開啟' : '預覽'), key: 'Enter', run: () => HZ.openItem(one)},
    dirOnly && {icon: '🗂', text: '在新分頁開啟', run: () => { HZ.go('explorer'); HZ.pages.explorer.newTab(one.path); }},
    dirOnly && other && {icon: '◫', text: '在另一個窗格開啟', run: () => other.nav(one.path)},
    one && !one.dir && (HZ.bridge || HZ.local) && {icon: '👁', text: '預覽', run: () => HZ.previewDialog(one)},
    one && (HZ.bridge || HZ.local) && {icon: '🪟', text: '在 Windows 檔案總管顯示', run: () => HZ.reveal(one.path)},
    !ctx.inExplorer && one && {icon: '📍', text: '開啟所在資料夾', run: () => { HZ.go('explorer'); HZ.pages.explorer.open(HZ.dir(one.path), one.name); }},
    '-',
    {icon: '📋', text: '複製', key: 'Ctrl+C', run: () => HZ.setClip('copy', items)},
    {icon: '✂', text: '剪下', key: 'Ctrl+X', run: () => HZ.setClip('cut', items)},
    ctx.dir && {icon: '📥', text: '貼上', key: 'Ctrl+V', run: () => HZ.paste(dirOnly && ctx.onItem ? one.path : ctx.dir)},
    other && other.path && {icon: '⇉', text: `複製到另一窗格`, key: 'F5', run: () => HZ.queueAdd('copy', items.map(i => i.path), other.path)},
    other && other.path && {icon: '➜', text: `移動到另一窗格`, key: 'F6', run: () => HZ.queueAdd('move', items.map(i => i.path), other.path)},
    {icon: '📤', text: '複製到…', run: () => HZ.pickTarget('copy', items)},
    {icon: '🚚', text: '移動到…', run: () => HZ.pickTarget('move', items)},
    '-',
    dirOnly && !isHotRoot && {icon: '🔥', text: '標記為熱處理優先', run: () => HZ.markHot(one.path, true)},
    isHotRoot && {icon: '🧊', text: '取消熱處理', run: () => HZ.markHot(one.path, false)},
    dirOnly && {icon: '📊', text: '分析空間（TreeSize）', run: () => { HZ.go('space'); HZ.pages.space.load(one.path); }},
    dirOnly && {icon: '🎬', text: '影片工具（長度、無損轉 MP4）', run: () => { HZ.go('video'); const P = HZ.pages.video; if (P && P.path) { P.path.value = one.path; P.load(); } }},
    (() => { const vids = items.filter(i => !i.dir && /^(flv|ts|m2ts|mts|mkv|mov|webm|avi|m4v|3gp)$/i.test(i.ext || (i.name || '').split('.').pop()));
      return vids.length ? {icon: '🎬', text: `無損轉成 MP4（${vids.length}）`, run: () => HZ.remuxVideos ? HZ.remuxVideos(vids.map(i => i.path)) : null} : null; })(),
    dirOnly && {icon: '⭐', text: (HZ.favs || []).includes(one.path) ? '從我的最愛移除' : '加入我的最愛', run: () => HZ.toggleFav(one.path)},
    '-',
    {icon: '⬇', text: n > 1 || dirOnly ? '下載（zip）' : '下載', run: () => HZ.download(items)},
    {icon: '🔗', text: '複製路徑', run: () => HZ.copyText(items.map(i => i.path).join('\n'))},
    one && {icon: '✏', text: '重新命名', key: 'F2', run: () => HZ.renameItem(one)},
    n > 1 && {icon: '✏', text: '批次重新命名…', key: 'F2', run: () => HZ.batchRename(items)},
    {icon: '🗑', text: '刪除（放進保管區）', key: 'Del', run: () => HZ.deleteItems(items, false)},
    {icon: '⛔', text: '永久刪除', key: 'Shift+Del', run: () => HZ.deleteItems(items, true)},
    '-',
    one && {icon: 'ℹ', text: '內容', key: 'Alt+Enter', run: () => HZ.props(one)},
  ];
};
HZ.thumbsOk = k => { const t = HZ.sys && HZ.sys.thumbs; return !t || (k === 'image' ? t.images : t.videos); };
HZ.batchRename = function (items) {
  if (!items.length) return;
  const I = (ph, w = '150px') => h('input', {placeholder: ph, style: {width: w}});
  const find = I('尋找'), repl = I('取代為'), pre = I('前面加上', '110px'), suf = I('後面加上', '110px');
  const rx = h('input', {type: 'checkbox'}), ci = h('input', {type: 'checkbox', checked: true}), inExt = h('input', {type: 'checkbox'});
  const tpl = I('例如 旅行_{n:3}', '200px'), start = h('input', {type: 'number', value: 1, style: {width: '70px'}}), step = h('input', {type: 'number', value: 1, style: {width: '60px'}});
  const cs = h('select', {}, ...[['', '大小寫不變'], ['lower', '全部小寫'], ['upper', '全部大寫'], ['title', '每個字開頭大寫']].map(([v, t]) => h('option', {value: v, text: t})));
  const ext = I('新副檔名（空白 = 不變）', '170px');
  const tab = h('table', {class: 'brtab'}); const info = h('div', {class: 'small muted'});
  const pad = (n, w) => String(n).padStart(w, '0');
  const fmtD = t => { const d = new Date(t * 1000); return `${d.getFullYear()}${pad(d.getMonth() + 1, 2)}${pad(d.getDate(), 2)}`; };
  const fmtT = t => { const d = new Date(t * 1000); return `${pad(d.getHours(), 2)}${pad(d.getMinutes(), 2)}${pad(d.getSeconds(), 2)}`; };
  const byTaken = h('input', {type: 'checkbox'});
  let taken = null, asking = false;                                       // {path: epoch} from EXIF, fetched on first use
  const needTaken = () => { if (taken || asking) return; asking = true;
    HZ.post('/api/taken', {paths: items.filter(i => !i.dir).map(i => i.path)}).then(r => { taken = r.taken || {}; compute(); }).catch(() => { taken = {}; }).finally(() => { asking = false; }); };
  const tk = it => (taken && taken[it.path]) || it.mtime;
  let gen = null, askingGen = false;                                       // ComfyUI / A1111 settings stored in the PNGs
  const needGen = () => { if (gen || askingGen) return; askingGen = true;
    HZ.post('/api/comfy/params', {paths: items.filter(i => /\.png$/i.test(i.name)).map(i => i.path)}).then(r => { gen = r.params || {}; compute(); }).catch(() => { gen = {}; }).finally(() => { askingGen = false; }); };
  const gv = (it, k) => { const v = gen && gen[it.path] && gen[it.path][k]; if (v == null) return ''; return String(v).replace(/^.*[\\/]/, '').replace(/\.(safetensors|ckpt|pt|gguf)$/i, '').replace(/[\\/:*?"<>|]/g, '_'); };
  let result = [];
  const compute = () => {
    result = []; let bad = 0, changed = 0;
    const seen = new Set();
    if (/\{taken\}/.test(tpl.value) || byTaken.checked) needTaken();
    if (/\{(seed|cfg|steps|sampler|scheduler|model|denoise)\}/.test(tpl.value)) needGen();
    const order = byTaken.checked ? items.slice().sort((a, b) => tk(a) - tk(b) || a.name.localeCompare(b.name)) : items;
    order.forEach((it, i) => {
      let name = it.name, base = name, e = '';
      const dot = name.lastIndexOf('.');
      if (!it.dir && dot > 0) { base = name.slice(0, dot); e = name.slice(dot); }
      let target = inExt.checked ? name : base;
      if (find.value) {
        try {
          const re = rx.checked ? new RegExp(find.value, ci.checked ? 'gi' : 'g') : new RegExp(find.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), ci.checked ? 'gi' : 'g');
          target = target.replace(re, repl.value);
        } catch (er) { info.textContent = '正規表達式錯誤：' + er.message; }
      }
      if (inExt.checked) { const d2 = target.lastIndexOf('.'); if (!it.dir && d2 > 0) { base = target.slice(0, d2); e = target.slice(d2); } else { base = target; e = ''; } }
      else base = target;
      if (tpl.value) {
        const n = (+start.value || 0) + i * (+step.value || 1);
        base = tpl.value.replace(/\{name\}/g, base).replace(/\{n(?::(\d+))?\}/g, (m, w) => pad(n, +w || 0)).replace(/\{date\}/g, fmtD(it.mtime)).replace(/\{time\}/g, fmtT(it.mtime))
          .replace(/\{taken\}/g, fmtD(tk(it)) + '_' + fmtT(tk(it))).replace(/\{(seed|cfg|steps|sampler|scheduler|model|denoise)\}/g, (m, k) => gv(it, k))
          .replace(/\{ext\}/g, e.replace('.', ''));
      }
      base = (pre.value || '') + base + (suf.value || '');
      if (cs.value === 'lower') base = base.toLowerCase(); else if (cs.value === 'upper') base = base.toUpperCase();
      else if (cs.value === 'title') base = base.replace(/(^|[\s_\-.])(\p{L})/gu, (m, a, b) => a + b.toUpperCase());
      if (ext.value.trim() && !it.dir) e = '.' + ext.value.trim().replace(/^\./, '');
      const nn = base + e;
      let err = '';
      if (!base.trim()) err = '空白'; else if (/[\\/:*?"<>|]/.test(nn)) err = '不能有 \\ / : * ? " < > |';
      else if (seen.has(nn.toLowerCase())) err = '重複';
      seen.add(nn.toLowerCase());
      if (err) bad++; if (nn !== it.name) changed++;
      result.push({it, nn, err});
    });
    tab.innerHTML = '';
    for (const r of result.slice(0, 300)) tab.append(h('tr', {}, h('td', {class: 'muted', text: r.it.name}), h('td', {text: '→'}), h('td', {class: r.err ? 'bad' : r.nn !== r.it.name ? 'chg' : 'muted', text: r.nn + (r.err ? '（' + r.err + '）' : '')})));
    info.textContent = `${items.length} 個項目，${changed} 個會改名` + (bad ? `，${bad} 個有問題` : '') + (items.length > 300 ? '（只預覽前 300 個）' : '');
    return !bad;
  };
  const body = h('div', {class: 'col', style: {minWidth: 'min(680px,88vw)'}},
    h('div', {class: 'row wrap'}, find, repl, h('label', {class: 'row small'}, rx, '正規表達式'), h('label', {class: 'row small'}, ci, '不分大小寫'), h('label', {class: 'row small'}, inExt, '含副檔名')),
    h('div', {class: 'row wrap'}, h('span', {class: 'small muted', text: '改成'}), tpl, h('span', {class: 'small muted', text: '編號從'}), start, h('span', {class: 'small muted', text: '每次 +'}), step),
    h('div', {class: 'small muted', html: '格式：<code>{name}</code> 原本名稱、<code>{n}</code> 編號、<code>{n:3}</code> 補零到 3 位、<code>{date}</code> 修改日期、<code>{time}</code> 修改時間、<code>{taken}</code> 拍攝日期時間（照片的 EXIF，沒有就用修改時間）、<code>{ext}</code> 副檔名　例：<code>{taken}_{n:3}</code><br>生圖 PNG 還可以用 <code>{seed}</code> <code>{cfg}</code> <code>{steps}</code> <code>{sampler}</code> <code>{model}</code>，例：<code>{model}_cfg{cfg}_{seed}</code>'}),
    h('label', {class: 'row small'}, byTaken, '先依拍攝時間排序再編號（照片從不同相機合在一起時很好用）'),
    h('div', {class: 'row wrap'}, pre, suf, cs, ext), info, h('div', {style: {maxHeight: '42vh', overflow: 'auto', border: '1px solid var(--border)', borderRadius: '8px'}}, tab));
  for (const el of body.querySelectorAll('input,select')) el.addEventListener('input', compute);
  compute();
  HZ.dialog({title: `批次重新命名（${items.length} 個）`, body, width: 'min(760px,94vw)', buttons: [{text: '取消', value: null}, {text: '重新命名', primary: true, value: 'go'}]}).then(async r => {
    if (r !== 'go') return;
    if (!compute()) { HZ.toast('有名稱不能用，請修正後再試', 'bad'); return; }
    const list = result.filter(x => x.nn !== x.it.name).map(x => [x.it.path, x.nn]);
    if (!list.length) return;
    try { const j = await HZ.post('/api/batch_rename', {items: list}); HZ.toast(`已重新命名 ${j.n} 個項目（Ctrl+Z 可以復原）`, 'ok'); HZ.refreshViews(); } catch (e) { HZ.err(e); }
  });
};
HZ.undo = async function () {
  try {
    const r = await HZ.post('/api/undo', {});
    HZ.toast(`↶ 已復原：${esc(r.text)}${r.msg ? '<br><span class="muted">' + esc(r.msg) + '</span>' : ''}`, 'ok', 4500);
    setTimeout(HZ.refreshViews, 300);
  } catch (e) { HZ.err(e); }
};
HZ.toggleFav = async function (p) {
  const on = !(HZ.favs || []).includes(p);
  try { const r = await HZ.post('/api/fav', {path: p, on}); HZ.favs = r.fav; HZ.refreshViews(); } catch (e) { HZ.err(e); }
};
HZ.pickTarget = async function (kind, items) {
  const inp = h('input', {style: {width: '100%'}, placeholder: '例如 K:\\Work', value: (HZ.lastTarget || '')});
  const list = h('div', {class: 'col small', style: {marginTop: '8px', maxHeight: '220px', overflow: 'auto'}});
  const add = (label, p) => list.append(h('div', {class: 'tn', onclick: () => { inp.value = p; }}, label, h('span', {class: 'meta', text: p})));
  for (const f of HZ.hotFolders || []) add('🔥 ' + HZ.base(f.path), f.path);
  for (const f of HZ.favs || []) add('⭐ ' + HZ.base(f), f);
  for (const v of HZ.vols || []) if (v.ok) add('💽 ' + v.letter + ' ' + (v.label || ''), v.letter.length === 2 ? v.letter + '\\' : v.letter);
  let pick = null;
  if (HZ.bridge) pick = {text: '瀏覽…', value: 'browse'};
  const r = await HZ.dialog({title: (kind === 'copy' ? '複製' : '移動') + ` ${items.length} 個項目到…`, body: h('div', {}, inp, list),
    buttons: [pick, {text: '取消', value: null}, {text: kind === 'copy' ? '複製' : '移動', primary: true, value: () => inp.value.trim()}].filter(Boolean)});
  let dst = r;
  if (r === 'browse') dst = await HZ.bcall('pickFolder');
  if (!dst) return;
  HZ.lastTarget = dst;
  HZ.queueAdd(kind, items.map(i => i.path), dst);
};

/* ------------------------------------------------------------------ router / nav */
const NAV = [
  {grp: '檔案', color: '#43d9ff', items: [['home', '📋', '總覽'], ['explorer', '🗂', '檔案總管'], ['search', '🔍', '搜尋'], ['space', '📊', '空間分析'], ['dupes', '👯', '重複檔案'], ['vault', '🛟', '保管區']]},
  {grp: '圖片與影片', color: '#ff7eb6', items: [['images', '🎨', '圖片分類'], ['comfy', '🖼', '生圖比較'], ['video', '🎬', '影片工具']]},
  {grp: '傳輸', color: '#45d483', items: [['queue', '⇅', '傳輸佇列'], ['compare', '⇄', '資料夾同步']]},
  {grp: '熱區', color: '#ff8a3d', items: [['hot', '🔥', '熱處理']]},
  {grp: '系統', color: '#b48cff', items: [['disks', '💽', '磁碟'], ['settings', '⚙', '設定'], ['update', '⟳', '更新'], ['log', '📜', '紀錄'], ['help', '❓', '說明']]},
];
HZ.buildNav = function () {
  const nav = $('#nav'); nav.innerHTML = '';
  for (const g of NAV) {
    nav.append(h('div', {class: 'nh', style: {color: g.color}}, g.grp, h('i')));
    for (const [id, ic, label] of g.items) {
      nav.append(h('div', {class: 'ni', 'data-page': id, style: {'--gc': g.color}, onclick: () => { HZ.go(id); $('#app').classList.remove('sideon'); }},
        h('b', {text: ic}), h('span', {text: label}), h('span', {class: 'badge', id: 'badge-' + id, style: {display: 'none'}})));
    }
  }
};
HZ.pageHist = [];
HZ.go = function (id, fromBack) {
  if (!HZ.pages[id]) id = 'explorer';
  if (HZ.cur === id) return;
  if (HZ.cur && !fromBack) { HZ.pageHist.push(HZ.cur); if (HZ.pageHist.length > 50) HZ.pageHist.shift(); }
  const prev = HZ.pages[HZ.cur]; if (prev && prev.onHide) prev.onHide();
  HZ.cur = id;
  $$('.page').forEach(p => p.classList.toggle('on', p.id === 'page-' + id));
  $$('.ni').forEach(n => n.classList.toggle('on', n.dataset.page === id));
  const pg = HZ.pages[id];
  if (!pg._built) { pg._built = true; pg.build($('#page-' + id)); }
  if (pg.onShow) pg.onShow();
  $('#topTitle').textContent = pg.title || '';
  if (location.hash !== '#' + id) history.replaceState(null, '', '#' + id);
  try { localStorage.setItem('hz.page', id); } catch (e) { }
};
HZ.page = function (id, def) {
  HZ.pages[id] = def;
  $('#pages').append(h('div', {class: 'page' + (def.scroll ? ' scroll' : ''), id: 'page-' + id}));
};

/* ------------------------------------------------------------------ sidebar status / polling */
HZ.renderSide = function (st) {
  const box = $('#sysBox'); const rows = [];
  for (const d of st.disks || []) {
    const busy = d.busy == null ? null : Math.round(d.busy);
    const rate = (d.rd || 0) + (d.wr || 0);
    rows.push(`<div class="sp" title="${esc(d.model || '')}　${d.media}　讀 ${HZ.fmtRate(d.rd)}　寫 ${HZ.fmtRate(d.wr)}　（本程式 ${HZ.fmtRate(d.ours)}）" onclick="HZ.go('disks')">
      <b>${esc((d.letters || []).join(' ') || '#' + d.n)} <small>${esc(d.media === '?' ? '' : d.media)}</small></b>
      <div class="bar"><i class="${busy > 85 ? 'bad' : busy > 60 ? 'warn' : ''}" style="width:${busy || 0}%"></i></div><em>${busy == null ? HZ.fmtRate(rate).replace('/s', '') : busy + '%'}</em></div>`);
  }
  const q = st.queue || {};
  rows.push(`<div class="sline" onclick="HZ.go('queue')">⇅ 佇列：${q.running ? `<b class="ok">${q.running} 執行</b>` : '閒置'}${q.queued ? ` · ${q.queued} 排隊` : ''}${q.waiting ? ` · <b class="warn">${q.waiting} 等你決定</b>` : ''}${q.speed ? ' · ' + HZ.fmtRate(q.speed) : ''}${q.paused_all ? ' · <b class="warn">已暫停</b>' : ''}</div>`);
  for (const v of st.hot || []) {
    const s = {moving: '搬移中', evicting: '騰空間', planning: '檢查中', waiting: '等待', done: '完成', dry: '試跑', idle: '待命', error: '錯誤', unsupported: '不支援', full: '熱區滿了'}[v.state] || v.state;
    rows.push(`<div class="sline" onclick="HZ.go('hot')" title="${esc(v.msg || '')}">🔥 ${esc(v.letter)} ${v.pct_in != null ? `<b class="hot">外圈 ${v.pct_in}%</b>` : ''} · ${s}${v.rate > 0 && v.state === 'moving' ? ' · ' + HZ.fmtRate(v.rate) : ''}</div>`);
  }
  box.innerHTML = rows.join('');
  const bq = $('#badge-queue'), n = (q.running || 0) + (q.queued || 0);
  bq.style.display = n || q.waiting ? '' : 'none'; bq.textContent = q.waiting ? '!' : n; bq.className = 'badge' + (q.waiting ? ' warn' : '');
  const bh = $('#badge-hot'); const mv = (st.hot || []).find(v => ['moving', 'evicting', 'planning'].includes(v.state));
  bh.style.display = mv ? '' : 'none'; bh.textContent = '●'; bh.className = 'badge hot';
  const bv = $('#badge-vault'); const vr = (st.notices || []).some(n => n.action === 'vault');
  if (bv) { bv.style.display = vr ? '' : 'none'; bv.textContent = '!'; bv.className = 'badge warn'; }
  const bu = $('#badge-update'); const upd = (st.notices || []).some(n => n.action === 'update');
  bu.style.display = upd ? '' : 'none'; bu.textContent = '新'; bu.className = 'badge warn';
  // notices
  const nb = $('#notices'); const shown = (st.notices || []).filter(n => !(HZ.dismissed || {})[n.id + n.t]);
  nb.innerHTML = '';
  for (const n of shown.slice(-3)) {
    nb.append(h('div', {class: 'notice ' + n.level}, h('span', {html: esc(n.text)}),
      n.action === 'cancel_shutdown' ? h('button', {class: 'sm primary', onclick: () => HZ.post('/api/system/cancel_shutdown').then(() => HZ.toast('已取消關機', 'ok'))}, '取消關機')
        : n.action ? h('button', {class: 'sm', onclick: () => HZ.go(n.action)}, '前往') : null,
      h('button', {class: 'ghost sm x', onclick: () => { (HZ.dismissed = HZ.dismissed || {})[n.id + n.t] = 1; HZ.post('/api/notice/dismiss', {id: n.id}).catch(() => { }); HZ.renderSide(HZ.st); }}, '✕')));
  }
  if (st.shell_changed && HZ.bridge && !HZ._shellNoted) {
    HZ._shellNoted = true;
    nb.append(h('div', {class: 'notice info'}, '視窗外殼有更新，重開視窗後生效（背景工作不受影響）', h('button', {class: 'sm', onclick: () => HZ.bridge.restartShell()}, '重開視窗')));
  }
};
HZ.poll = async function () {
  try {
    const st = await HZ.get('/api/state');
    HZ.st = st; HZ.local = st.local;
    if (st.stamp && HZ_STAMP && Math.abs(st.stamp - HZ_STAMP) > 0.01) {         // the page itself was updated: reload
      try { sessionStorage.setItem('hz.reloaded', '1'); } catch (e) { }
      location.reload(); return;
    }
    $('#verLabel').textContent = 'V' + st.ver + (st.admin ? '' : '　（一般權限）');
    HZ.renderSide(st);
    const u = st.update || {};
    if (u.state === 'done' && u.t && Date.now() / 1000 - u.t < 600) {
      let seen = null; try { seen = localStorage.getItem('hz.updseen'); } catch (e) { }
      if (seen !== String(u.t)) {
        try { localStorage.setItem('hz.updseen', String(u.t)); } catch (e) { }
        HZ.dialog({title: '更新完成', body: `已從 V${esc(u.from || '?')} 更新到 V${esc(u.to)}。<br>搬檔、熱區搬移與索引都持續進行，沒有中斷。` +
          (u.notes && u.notes.length ? '<h3>本次更新</h3>' + u.notes.map(n => '・' + esc(n)).join('<br>') : '') +
          (u.shell_changed ? '<br><br><span class="warn">視窗外殼也有更新：重開視窗後完全生效。</span>' : '')});
      }
    }
    const pg = HZ.pages[HZ.cur]; if (pg && pg.onState) pg.onState(st);
  } catch (e) { }
};
HZ.every = function (key, ms, fn) {
  clearInterval(HZ.polls[key]); fn(); HZ.polls[key] = setInterval(() => { if (!document.hidden) fn(); }, ms);
};
HZ.stop = key => { clearInterval(HZ.polls[key]); delete HZ.polls[key]; };

/* ------------------------------------------------------------------ login / boot */
HZ.showLogin = function () {
  if (HZ._login) return; HZ._login = true;
  const pw = h('input', {type: 'password', placeholder: '網頁密碼', style: {width: '100%'}});
  const msg = h('div', {class: 'small warn'});
  const box = h('div', {class: 'card login'}, h('h2', {text: '🔥 HotZone FM'}),
    h('div', {class: 'muted small', style: {marginBottom: '10px', textAlign: 'center'}, text: HZ.me && !HZ.me.pw_set ? '電腦端還沒有設定網頁密碼：請在電腦上開啟 HotZone FM →「設定 → 遠端連線」設定密碼。' : '請輸入在電腦上設定的網頁密碼'}),
    pw, msg, h('button', {class: 'primary', style: {width: '100%', marginTop: '10px'}, onclick: go}, '登入'));
  async function go() {
    try { await HZ.api('POST', '/api/login', {pw: pw.value}, {noLogin: true}); location.reload(); }
    catch (e) { msg.textContent = e.message; }
  }
  pw.addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
  document.body.innerHTML = ''; document.body.append(box); setTimeout(() => pw.focus(), 50);
};
HZ.applyTheme = function (mode, zoom) {
  document.documentElement.dataset.theme = mode === 'light' ? 'light' : 'dark';
  if (zoom) document.documentElement.style.setProperty('--zoom', zoom / 100);
  try { localStorage.setItem('hz.theme', mode); if (zoom) localStorage.setItem('hz.zoom', zoom); } catch (e) { }
};
HZ.boot = async function () {
  try { HZ.applyTheme(localStorage.getItem('hz.theme') || 'dark', +localStorage.getItem('hz.zoom') || 100); } catch (e) { }
  try { HZ.me = await HZ.api('GET', '/api/me', undefined, {noLogin: true}); } catch (e) { HZ.me = null; }
  if (!HZ.me || !HZ.me.logged) {
    // the desktop window lost its login (e.g. sessions cleared): ask the window to log in again with its key, once
    let again = false; try { again = !sessionStorage.getItem('hz.relogin'); sessionStorage.setItem('hz.relogin', '1'); } catch (e) { }
    if (again && HZ.me && HZ.me.local && window.qt && qt.webChannelTransport) {
      HZ.initBridge(); for (let i = 0; i < 30 && !HZ.bridge; i++) await new Promise(r => setTimeout(r, 100));
      if (HZ.bridge && HZ.bridge.relogin) { HZ.bridge.relogin(); return; }
    }
    HZ.showLogin(); return;
  }
  try { sessionStorage.removeItem('hz.relogin'); } catch (e) { }
  HZ.local = HZ.me.local;
  HZ.buildNav();
  $('#menuBtn').onclick = () => $('#app').classList.add('sideon');
  document.addEventListener('pointerdown', e => {                  // phone: tapping outside the open menu closes it
    const app = $('#app'); if (!app.classList.contains('sideon')) return;
    const side = $('#side') || document.querySelector('.side, nav'); if (side && !side.contains(e.target) && !e.target.closest('#menuBtn')) app.classList.remove('sideon');
  }, true);
  $('#sideClose').onclick = () => $('#app').classList.remove('sideon');
  HZ.initBridge();
  if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('/sw.js').catch(() => { });
  try {
    const s = await HZ.get('/api/settings'); HZ.settings = s.settings; HZ.favs = s.settings.fav || []; HZ.hotFolders = s.settings['hot.folders'] || [];
    HZ.applyTheme(s.settings['ui.theme'], s.settings['ui.zoom']);
    HZ.vols = (await HZ.get('/api/drives')).vols;
    HZ.get('/api/system').then(x => { HZ.sys = x; }).catch(() => { });
  } catch (e) { }
  HZ.go('explorer');                                               // always opens on 檔案總管 → 本機 (not the last page)
  if (location.hash !== '#explorer') history.replaceState(history.state, '', '#explorer');
  HZ.every('state', 1500, HZ.poll);
  if (HZ.local && HZ.settings && !HZ.settings['ui.welcomed']) setTimeout(() => HZ.welcome(), 600);
  window.addEventListener('hashchange', () => HZ.go(location.hash.slice(1)));
  HZ.initBack();
  document.addEventListener('keydown', e => {
    if (e.ctrlKey && e.key.toLowerCase() === 'f' && HZ.cur !== 'search') { e.preventDefault(); HZ.go('search'); setTimeout(() => $('#page-search input.q')?.focus(), 30); }
  });
};

/* ------------------------------------------------------------------ first-run guide */
HZ.closeDialog = () => { if (HZ._dlgClose) HZ._dlgClose(null); };
/* Phone back button (and the browser's ◀): one step back inside the app instead of leaving it.
   Order: close what is open (menu, dialog, picture viewer, side menu) -> previous folder -> parent folder -> previous page.
   Only when there is nothing left to go back to does the next press leave the page. */
HZ.backStep = function () {
  const esc = () => (document.activeElement || document.body).dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', bubbles: true, cancelable: true}));
  if ($('#ctx') && $('#ctx').classList.contains('on')) { HZ.closeMenu(); return true; }
  if ($('#overlay') && $('#overlay').classList.contains('on')) { if (HZ._dlgClose) HZ._dlgClose(null); else esc(); return true; }
  if (document.querySelector('.cview')) { esc(); if (document.querySelector('.cview')) document.querySelector('.cview').remove(); return true; }
  const app = $('#app'); if (app && app.classList.contains('sideon')) { app.classList.remove('sideon'); return true; }
  const open = document.querySelector('.iside.open, .cctl.open'); if (open) { open.classList.remove('open'); return true; }
  const pg = HZ.pages[HZ.cur];
  if (pg && pg.onBack && pg.onBack()) return true;                     // e.g. the file manager: previous / parent folder
  while (HZ.pageHist.length) { const id = HZ.pageHist.pop(); if (id !== HZ.cur && HZ.pages[id]) { HZ.go(id, true); return true; } }
  return false;
};
HZ.initBack = function () {
  if (HZ.bridge || HZ._backOn) return;                                   // the desktop window has no back button
  HZ._backOn = true;
  const guard = () => history.pushState({hzguard: Date.now()}, '', location.href);
  if (!(history.state && history.state.hzguard)) guard();
  window.addEventListener('popstate', () => {
    if (HZ.backStep()) { guard(); return; }                              // handled: stay in the app, catch the next press too
    if (HZ._leaveSoon) { history.back(); return; }                       // second press within 2 s: really leave
    HZ._leaveSoon = true; setTimeout(() => { HZ._leaveSoon = false; }, 2000);
    HZ.toast('再按一次返回鍵就會離開', 'ok', 1800); guard();
  });
};
HZ.welcome = async function () {
  let st = {}, sys = {};
  try { st = (await HZ.get('/api/settings')).settings; HZ.settings = st; } catch (e) { }
  try { sys = await HZ.get('/api/system'); } catch (e) { }
  let tested = false; try { tested = localStorage.getItem('hz.selftest.ok') === '1'; } catch (e) { }
  const hot = st['hot.folders'] || [], imgs = st['images.folders'] || [];
  const leave = async () => {                                     // a step that opens another page: the guide counts as seen
    try { await HZ.post('/api/settings', {'ui.welcomed': true}); HZ.settings['ui.welcomed'] = true; } catch (e) { }
    HZ.toast('導覽可以在「設定」→「👋 開始使用導覽」再打開', 'ok', 4000);
  };
  const step = (done, title, text, btn, fn) => h('div', {class: 'wstep' + (done ? ' done' : '')},
    h('span', {class: 'wmark', text: done ? '✓' : '○'}), h('div', {class: 'grow'}, h('b', {text: title}), h('div', {class: 'small muted', html: text})),
    btn ? h('button', {class: done ? 'sm' : 'sm primary', onclick: async () => { HZ.closeDialog(); await fn(); }}, btn) : null);
  const body = h('div', {class: 'col'},
    h('div', {class: 'muted', html: '這幾步做完就能開始用。每一步之後都可以在各頁面重新設定，這個導覽也能在「設定」裡再打開。'}),
    step(tested, '1. 自我檢查', '確認這台電腦的權限和硬碟功能都正常（會用一個 8 MB 測試檔實際搬一次，不動你的檔案）。', '開始檢查', async () => { await HZ.selftest(); HZ.welcome(); }),
    step(hot.length > 0, '2. 指定熱處理資料夾', hot.length ? hot.map(x => esc(x.path)).join('<br>') : '例如 <b>K:\\熱處理</b>：放進去的檔案馬上能用，背景會把它們搬到硬碟最快的外圈。', hot.length ? '再加一個' : '選資料夾', async () => {
      const p = await HZ.prompt('熱處理資料夾', '輸入資料夾位置（不存在會自動建立）', 'K:\\熱處理', '標記為熱處理');
      if (!p) return HZ.welcome();
      const path = p.trim().replace(/[\\/]+$/, '');
      try {
        const ex = await HZ.get('/api/props', {path}).then(() => true).catch(() => false);
        if (!ex) { const i = Math.max(path.lastIndexOf('\\'), path.lastIndexOf('/')); await HZ.post('/api/op', {op: 'mkdir', path: path.slice(0, i) || path.slice(0, 3), name: path.slice(i + 1)}); }
        await HZ.markHot(path, true);
      } catch (e) { HZ.err(e); }
      HZ.welcome();
    }),
    step(imgs.length > 0, '3. 圖片分類的資料夾（可以跳過）', imgs.length ? imgs.map(esc).join('<br>') : '20 萬張照片放在哪裡？程式會在背景慢慢分析顏色、相似、人臉、文字。', imgs.length ? '管理' : '加入資料夾', async () => {
      await leave(); HZ.go('images'); setTimeout(() => HZ.pages.images && HZ.pages.images.folderDlg && HZ.pages.images.folderDlg(), 400);
    }),
    step(!!(sys.autostart && sys.autostart.on), '4. 開機自動啟動（建議）', '登入 Windows 時在背景啟動，不跳 UAC；這樣熱處理和遠端隨時可用。', sys.autostart && sys.autostart.supported && !sys.autostart.on ? '開啟' : null, async () => {
      try { await HZ.post('/api/system/autostart', {on: true}); HZ.toast('已設定開機自動啟動', 'ok'); } catch (e) { HZ.err(e); }
      HZ.welcome();
    }),
    step(!!st['web.remote'], '5. 手機／遠端（可以跳過）', '用手機或別台電腦管理檔案、看搬移進度。出門在外搭配 Tailscale。', '前往設定', async () => { await leave(); HZ.go('settings'); }));
  const v = await HZ.dialog({title: '👋 歡迎使用 HotZone FM', body, width: 620, buttons: [{text: '之後再說', value: 'later'}, {text: '完成，不再顯示', value: 'done', primary: true}]});
  if (v === 'done') { try { await HZ.post('/api/settings', {'ui.welcomed': true}); HZ.settings['ui.welcomed'] = true; } catch (e) { } }
};

HZ.copyImage = async function (path) {
  if (HZ.bridge && HZ.bridge.copyImage) { HZ.bridge.copyImage(path); HZ.toast('圖片已複製，可以直接貼到其他程式', 'ok'); return; }
  try {
    let b = await (await fetch(HZ.fileUrl(path), {credentials: 'same-origin'})).blob();
    if (b.type !== 'image/png') {                                     // the clipboard only takes PNG
      const bm = await createImageBitmap(b), cv = document.createElement('canvas'); cv.width = bm.width; cv.height = bm.height;
      cv.getContext('2d').drawImage(bm, 0, 0); b = await new Promise(r => cv.toBlob(r, 'image/png'));
    }
    await navigator.clipboard.write([new ClipboardItem({'image/png': b})]);
    HZ.toast('圖片已複製，可以直接貼到其他程式', 'ok');
  } catch (e) { HZ.toast('這個瀏覽器不允許複製圖片：' + (e.message || e), 'warn'); }
};

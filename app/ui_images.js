/* HotZone FM — 圖片分類: colours, faces, screenshots, cameras, dates, similar pictures, series (相近套圖).
   Everything comes from the background analysis (no AI). */
'use strict';
(function () {
  const {h, esc} = HZ;
  const COLORS = ['紅', '橙', '黃', '綠', '青', '藍', '紫', '粉', '棕', '黑', '白', '灰'];
  const HEX = {'紅': '#e53935', '橙': '#fb8c00', '黃': '#fdd835', '綠': '#43a047', '青': '#00acc1', '藍': '#1e88e5', '紫': '#8e24aa', '粉': '#f48fb1', '棕': '#8d6e63', '黑': '#111', '白': '#f5f5f5', '灰': '#9e9e9e'};
  const I = {title: '圖片分類', f: {sort: 'taken'}, items: [], total: 0, mode: 'all', tile: 150, simOf: null};

  I.build = function (root) {
    try { I.tile = +localStorage.getItem('hz.img.tile') || 150; } catch (e) { }
    I.statusEl = h('div', {class: 'sinfo istatus'});
    I.side = h('div', {class: 'iside'});
    I.top = h('div', {class: 'sbox', style: {paddingTop: '6px', paddingBottom: '6px'}});
    I.grid = h('div', {class: 'list igrid', tabindex: '0'}); I.space = h('div', {class: 'spacer'}); I.grid.append(I.space);
    I.grid.addEventListener('scroll', () => { I.paint(); if (I.grid.scrollTop + I.grid.clientHeight > I.grid.scrollHeight - 800) I.more(); });
    new ResizeObserver(() => I.paint(true)).observe(I.grid);
    root.append(I.statusEl, h('div', {class: 'ibody'}, I.side, h('div', {class: 'imain'}, I.top, I.grid)));
    I.renderTop();
  };

  /* ------------------------------------------------------------------ status / folders */
  I.loadStatus = async function () {
    let s; try { s = await HZ.get('/api/images/status'); } catch (e) { return; }
    I.st = s;
    const run = s.state === 'running';
    I.statusEl.innerHTML = '';
    I.statusEl.append(
      h('span', {html: `已分析 <b>${(s.analyzed || 0).toLocaleString()}</b> 張`}),
      run ? h('span', {class: 'hot', text: `分析中 ${s.done.toLocaleString()} / ${s.total.toLocaleString()}（${s.rate ? s.rate.toFixed(1) + ' 張/秒' : '…'}）`}) : h('span', {class: 'muted', text: s.msg || ''}),
      !s.face_engine ? h('span', {class: 'warn', title: '臉部偵測需要 OpenCV（製作 exe 時會一併安裝）', text: '臉部偵測未啟用'}) : null,
      (s.missing || []).length ? h('span', {class: 'warn', title: s.missing.join('\n'), text: `${s.missing.length} 個資料夾暫時找不到（硬碟沒接上？），它們的分析結果先保留`}) : null,
      h('span', {class: 'grow'}),
      h('button', {class: 'sm ionly-m', onclick: () => I.side.classList.toggle('open')}, '☰ 篩選'),
      h('button', {class: 'sm', onclick: I.folderDlg}, `📁 分析的資料夾（${(s.folders || []).length}）`),
      h('button', {class: 'sm', onclick: () => HZ.post('/api/images/pause', {on: !s.paused}).then(I.loadStatus)}, s.paused ? '▶ 繼續分析' : '⏸ 暫停分析'),
      h('button', {class: 'sm', onclick: () => HZ.post('/api/images/rescan').then(() => HZ.toast('重新檢查中'))}, '⟳ 檢查新圖片'));
    if (!(s.folders || []).length && !I._asked) { I._asked = true; I.folderDlg(); }
  };
  I.folderDlg = async function () {
    const s = I.st || {folders: []};
    const list = h('div', {class: 'col'});
    const draw = fs => { list.innerHTML = ''; for (const f of fs) list.append(h('div', {class: 'row'}, h('span', {class: 'ell grow', text: f}), h('button', {class: 'sm', onclick: async () => { const r = await HZ.post('/api/images/folders', {act: 'remove', path: f}); draw(r.folders); }}, '移除'))); if (!fs.length) list.append(h('div', {class: 'muted small', text: '還沒有'})); };
    draw(s.folders || []);
    const inp = h('input', {placeholder: '例如 E:\\Photos', style: {flex: '1'}});
    const add = async p => { if (!p) return; try { const r = await HZ.post('/api/images/folders', {path: p}); draw(r.folders); inp.value = ''; } catch (e) { HZ.err(e); } };
    await HZ.dialog({title: '要分析的圖片資料夾', width: '600px', body: h('div', {class: 'col'},
      h('div', {class: 'small muted', text: '這些資料夾（含子資料夾）裡的每張圖片都會在背景分析一次：顏色、相似度、拍攝資訊、截圖、模糊、人臉數。20 萬張大約一個晚上；改過的圖片才會重新分析。'}),
      list, h('div', {class: 'row'}, inp, HZ.bridge ? h('button', {onclick: async () => add(await HZ.bcall('pickFolder'))}, '瀏覽…') : null, h('button', {class: 'primary', onclick: () => add(inp.value.trim())}, '加入'))),
      buttons: [{text: '完成', value: null, primary: true}]});
    I.loadStatus(); I.reload();
  };

  /* ------------------------------------------------------------------ facets */
  I.loadFacets = async function () {
    let d; try { d = await HZ.post('/api/images/facets', {scope: I.f.scope || ''}); } catch (e) { return; }
    I.fc = d; I.renderSide();
  };
  const chip = (label, on, fn, title, style) => h('span', {class: 'chip' + (on ? ' on' : ''), title: title || '', style: style || null, onclick: fn}, label);
  I.set = function (k, v) {
    if (I.f[k] === v || v === undefined) delete I.f[k]; else I.f[k] = v;
    if (k === 'year') delete I.f.month;                                      // a month only means something inside a year
    I.mode = 'all'; I.renderSide(); I.reload();
  };
  I.renderSide = function () {
    const d = I.fc || {}, f = I.f; I.side.innerHTML = '';
    const sec = (t, ...k) => I.side.append(h('div', {class: 'isec'}, h('div', {class: 'grp', text: t}), h('div', {class: 'chips'}, ...k)));
    I.side.append(h('div', {class: 'row', style: {padding: '4px 2px 8px'}}, h('b', {text: `${(d.total || 0).toLocaleString()} 張`}), h('span', {class: 'grow'}),
      Object.keys(f).filter(k => k !== 'sort' && k !== 'scope').length ? h('button', {class: 'sm', onclick: () => { I.f = {sort: f.sort, scope: f.scope}; I.mode = 'all'; I.renderSide(); I.reload(); }}, '清除條件') : null));
    sec('顏色', ...COLORS.map(c => chip(h('span', {class: 'row', style: {gap: '5px'}}, h('i', {class: 'sw', style: {background: HEX[c]}}), `${c} ${(d.colors || {})[c] || 0}`), f.color === c, () => I.set('color', c))));
    sec('人臉', chip(`沒有人 ${(d.faces || {})['0'] || 0}`, f.faces === '0', () => I.set('faces', '0')), chip(`1 個人 ${(d.faces || {})['1'] || 0}`, f.faces === '1', () => I.set('faces', '1')),
      chip(`多人 ${(d.faces || {})['2'] || 0}`, f.faces === '2', () => I.set('faces', '2')), d.face_engine ? null : h('span', {class: 'small muted', text: '（未啟用）'}));
    sec('形狀', chip(`直式 ${(d.orient || {}).portrait || 0}`, f.orient === 'portrait', () => I.set('orient', 'portrait')), chip(`橫式 ${(d.orient || {}).landscape || 0}`, f.orient === 'landscape', () => I.set('orient', 'landscape')),
      chip(`方形 ${(d.orient || {}).square || 0}`, f.orient === 'square', () => I.set('orient', 'square')));
    sec('其他', chip(`螢幕截圖 ${d.shots || 0}`, f.shot === '1', () => I.set('shot', '1')), chip(`不是截圖 ${d.noshots || 0}`, f.shot === '0', () => I.set('shot', '0')),
      chip(`可能模糊 ${d.blurry || 0}`, f.blur === 'blurry', () => I.set('blur', 'blurry')), chip(`清晰 ${d.sharp || 0}`, f.blur === 'sharp', () => I.set('blur', 'sharp')),
      chip(`偏暗 ${d.dark || 0}`, f.bright === 'dark', () => I.set('bright', 'dark')), chip(`偏亮 ${d.light || 0}`, f.bright === 'light', () => I.set('bright', 'light')),
      chip(`有 GPS 位置 ${d.gps || 0}`, f.gps === '1', () => I.set('gps', '1')), chip(`800 萬像素以上 ${d.bigpx || 0}`, !!f.minpx, () => I.set('minpx', 8e6)),
      chip(`⭐ 最愛 ${d.stars || 0}`, !!f.star, () => I.set('star', '1')));
    if ((d.years || []).length) sec('年份', ...d.years.map(([y, n]) => chip(`${y} ${n}`, f.year === y, () => I.set('year', y))));
    if (f.year) sec('月份', ...Array.from({length: 12}, (_, i) => String(i + 1).padStart(2, '0')).map(m => chip(+m + '月', f.month === m, () => I.set('month', m))));
    if ((d.models || []).length) sec('相機／手機', ...d.models.map(([m, n]) => chip(`${m} ${n}`, f.model === m, () => I.set('model', m))));
  };
  I.renderTop = function () {
    I.top.innerHTML = '';
    const sizeR = h('input', {type: 'range', min: 80, max: 400, step: 10, value: I.tile, style: {width: '110px'}, oninput: e => { I.tile = +e.target.value; try { localStorage.setItem('hz.img.tile', I.tile); } catch (er) { } I.paint(true); }});
    I.top.append(
      h('div', {class: 'chips'}, chip('全部', I.mode === 'all', () => { I.mode = 'all'; I.renderTop(); I.reload(); }), chip('相近套圖', I.mode === 'series', () => { I.mode = 'series'; I.renderTop(); I.reload(); }),
        chip('近似重複', I.mode === 'near', () => { I.mode = 'near'; I.renderTop(); I.reload(); }),
        I.simOf ? chip('相似：' + HZ.base(I.simOf), I.mode === 'similar', () => { I.mode = 'similar'; I.renderTop(); I.reload(); }) : null),
      h('input', {placeholder: '找圖：聖誕節、海邊、紅色、貓、和服…（空白＝而且，-字＝排除）', value: I.f.q || '', style: {width: '330px'},
        title: '不用 AI：比對資料夾名稱、檔名、圖片裡存的文字（ComfyUI／SD 提示詞、Windows 標籤、XMP 關鍵字），\n中英日同義詞會一起找（聖誕節 = christmas、xmas、santa…），\n節日也會比對拍攝日期（聖誕節 = 12/20～12/26），顏色字會比對主色。',
        oninput: HZ.debounce(e => { I.f.q = e.target.value; if (I.mode !== 'all' && I.f.q.trim()) { I.mode = 'all'; I.renderTop(); } I.reload(); }, 300)}),   // text search works on all pictures
      I.hintEl = h('span', {class: 'small muted ell', style: {maxWidth: '420px'}}),
      h('button', {class: 'sm', title: '把目前篩選出來的所有圖片一起複製、移動或放進保管區', onclick: e => I.bulkMenu(e)}, '對這些圖片…'),
      h('input', {placeholder: '只看這個資料夾（空白 = 全部）', value: I.f.scope || '', style: {width: '240px'}, onchange: e => { I.f.scope = e.target.value.trim(); I.loadFacets(); I.reload(); }}),
      h('select', {onchange: e => { I.f.sort = e.target.value; I.reload(); }}, ...[['taken', '拍攝時間（新→舊）'], ['name', '檔名'], ['folder', '資料夾'], ['size', '檔案大小'], ['px', '解析度'], ['bright', '亮度'], ['sat', '鮮豔度']]
        .map(([v, t]) => h('option', {value: v, text: '排序：' + t, selected: I.f.sort === v}))),
      h('span', {class: 'grow'}), h('span', {class: 'small muted', text: '大小'}), sizeR);
  };

  /* ------------------------------------------------------------------ results */
  I.reload = async function () {
    I.seq = (I.seq || 0) + 1; const seq = I.seq;
    I.items = []; I.total = 0; I.groups = null; I.grid.scrollTop = 0; I.lay = null;
    try {
      if (I.mode === 'near') {
        const r = await HZ.post('/api/images/neardupes', {scope: I.f.scope || '', dist: I.nearDist || 4});
        if (seq !== I.seq) return; I.groups = r.groups; I.total = r.groups.length;
      } else if (I.mode === 'series') {
        const r = await HZ.post('/api/images/series', {scope: I.f.scope || ''});
        if (seq !== I.seq) return; I.groups = r.groups; I.total = r.groups.length;
      } else if (I.mode === 'similar' && I.simOf) {
        const r = await HZ.post('/api/images/similar', {path: I.simOf, scope: I.f.scope || ''});
        if (seq !== I.seq) return; I.items = r.items; I.total = r.items.length;
      } else {
        const r = await HZ.post('/api/images/query', Object.assign({}, I.f, {offset: 0, limit: 800}));
        if (seq !== I.seq) return; I.items = r.items; I.total = r.total;
        if (I.hintEl) {
          const t = r.terms || [];
          I.hintEl.textContent = t.length ? `找到 ${r.total.toLocaleString()} 張　` + t.map(x => `${x.word}${x.also.length ? '（也找 ' + x.also.slice(0, 6).join('、') + (x.also.length > 6 ? '…' : '') + '）' : ''}${x.holiday ? '＋節日拍攝日期' : ''}${x.color ? '＋主色' + x.color : ''}`).join('　') : '';
          I.hintEl.title = t.map(x => x.word + '：' + x.also.join('、')).join('\n');
        }
      }
    } catch (e) { HZ.err(e); }
    I.paint(true);
  };
  I.more = async function () {
    if (I.mode !== 'all' || I._loading || I.items.length >= I.total) return;
    I._loading = true;
    try { const r = await HZ.post('/api/images/query', Object.assign({}, I.f, {offset: I.items.length, limit: 800})); I.items = I.items.concat(r.items); I.paint(true); }
    catch (e) { } finally { I._loading = false; }
  };
  const thumb = p => '/api/thumb?' + new URLSearchParams({path: p, s: 256});
  I.paint = function (force) {
    if (I.mode === 'near' || I.mode === 'series') {                   // plain lists: scrolling must not rebuild them
      if (!force || !I.groups) return;
      return I.mode === 'near' ? I.paintNear() : I.paintSeries();
    }
    const W = I.grid.clientWidth - 16, gap = 6, cols = Math.max(1, Math.floor((W + gap) / (I.tile + gap)));
    const t = Math.max(40, Math.floor((W + gap) / cols) - gap), st = t + gap;          // tiles stretch to fill the row
    const n = I.items.length, HEAD = 34;
    const timeline = I.mode === 'all' && (!I.f.sort || I.f.sort === 'taken') && !I.f.q;
    // layout: rows of tiles, with a month header before each new month when browsing by date (like a photo timeline)
    let L = I.lay;
    if (!L || L.cols !== cols || L.t !== t || L.timeline !== timeline || L.n > n || L.items !== I.items && L.n && I.items[0] !== L.first) {
      L = I.lay = {cols, t, timeline, n: 0, first: I.items[0], rowY: [], rowI: [], rowN: [], heads: [], y: 8, month: null, items: I.items};
    }
    L.items = I.items;
    const monthOf = it => { const d = new Date(1000 * (it.taken || it.mtime || 0)); return d.getFullYear() + ' 年 ' + (d.getMonth() + 1) + ' 月'; };
    for (let i = L.n; i < n; i++) {
      const it = I.items[i];
      if (timeline) {
        const m = monthOf(it);
        if (m !== L.month) {
          if (L.rowN.length) L.y += st;                                     // close the current (maybe half-filled) row
          L.heads.push({y: L.y, label: m, n: 0, row: L.rowY.length}); L.y += HEAD; L.month = m;
          L.rowY.push(L.y); L.rowI.push(i); L.rowN.push(0);
        }
        L.heads[L.heads.length - 1].n++;
      }
      if (!L.rowN.length || L.rowN[L.rowN.length - 1] >= cols) {
        if (L.rowN.length) L.y += st;
        L.rowY.push(L.y); L.rowI.push(i); L.rowN.push(0);
      }
      L.rowN[L.rowN.length - 1]++;
    }
    L.n = n;
    const total = (L.rowY.length ? L.y + st : 8) + 20;
    I.space.style.height = Math.max(total, 1) + 'px';
    const top = I.grid.scrollTop, bot = top + I.grid.clientHeight;
    let lo = 0, hi = L.rowY.length;                                         // first row whose bottom is below the view top
    while (lo < hi) { const mid = (lo + hi) >> 1; if (L.rowY[mid] + st < top - 2 * st) lo = mid + 1; else hi = mid; }
    const r0 = lo; let r1 = r0; while (r1 < L.rowY.length && L.rowY[r1] < bot + 2 * st) r1++;
    const key = [r0, r1, cols, t, n, timeline].join(',');
    if (!force && key === I._k) return; I._k = key;
    const frag = document.createDocumentFragment();
    if (timeline) for (const hd of L.heads) if (hd.y + HEAD > top - 2 * st && hd.y < bot + 2 * st)
      frag.append(h('div', {class: 'ihead', style: {top: hd.y + 'px'}}, h('b', {text: hd.label}), h('span', {class: 'muted small', text: `${hd.n.toLocaleString()} 張${I.items.length < I.total && hd === L.heads[L.heads.length - 1] ? '+' : ''}`})));
    for (let r = r0; r < r1; r++) for (let k = 0; k < L.rowN[r]; k++) {
      const i = L.rowI[r] + k, it = I.items[i], c = k;
      const el = h('div', {class: 'itile', style: {left: 8 + c * st + 'px', top: L.rowY[r] + 'px', width: t + 'px', height: t + 'px'}, title: it.path + (it.why ? '\n符合：' + it.why : '')},
        h('img', {'data-src': thumb(it.path), draggable: 'false'}),           // queued (HZ.lazyThumbs): fast scrolling drops what left
        h('span', {class: 'iswatch'}, ...(it.colors || []).slice(0, 4).map(([cn, p]) => h('i', {style: {background: HEX[cn], flex: Math.max(0.08, p)}}))),
        it.star ? h('span', {class: 'ibadge l', text: '⭐'}) : null, it.faces ? h('span', {class: 'ibadge', text: '👤' + it.faces}) : null, it.dist !== undefined ? h('span', {class: 'ibadge l', text: '相似度 ' + Math.max(0, 100 - it.dist * 4) + '%'}) : null);
      el.onclick = () => I.view(I.items, i);
      el.oncontextmenu = e => { e.preventDefault(); HZ.menu(e.clientX, e.clientY, I.menu(it)); };
      frag.append(el);
    }
    I.space.innerHTML = ''; I.space.append(frag); HZ.lazyThumbs(I.space);
    if (!n) I.space.append(h('div', {class: 'empty', text: I.st && !I.st.analyzed ? '還沒有分析好的圖片：按上面「分析的資料夾」加入你的圖片資料夾。' : '沒有符合的圖片'}));
  };
  I.paintNear = function () {
    I.space.style.height = ''; I.space.innerHTML = '';
    const box = h('div', {style: {padding: '8px 10px'}}), G = I.groups;
    if (!I.nearDrop || I.nearDrop.groups !== G) {                      // the ticks survive repaints; reset only on a new search
      I.nearDrop = new Set(); I.nearDrop.groups = G;
      for (const g of G) for (const it of g.items) if (!it.keep) I.nearDrop.add(it.path);
    }
    const drop = I.nearDrop;                                             // paths that would go to the vault
    const sum = () => { let n = 0, b = 0; for (const g of G) for (const it of g.items) if (drop.has(it.path)) { n++; b += it.size || 0; } return [n, b]; };
    const total = h('b'), upd = () => { const [n, b] = sum(); total.textContent = `已勾選 ${n.toLocaleString()} 張，可騰出 ${HZ.fmtSize(b)}`; };
    const clean = async (paths, label) => {
      if (!paths.length) return;
      if (!await HZ.confirm('放進保管區', `${label}：${paths.length.toLocaleString()} 張會放進同一顆硬碟的保管區（不是刪除，${HZ.vaultDays()} 天內可以在「保管區」還原）。每張都會記下「近似重複，保留的是哪一張」。`, '放進保管區')) return;
      const keepOf = new Map(); for (const g of G) { const k = g.items.find(x => x.keep); for (const it of g.items) keepOf.set(it.path, k ? k.path : ''); }
      const byKeep = new Map(); for (const p of paths) { const k = keepOf.get(p) || ''; if (!byKeep.has(k)) byKeep.set(k, []); byKeep.get(k).push(p); }
      for (const [k, ps] of byKeep) await HZ.queueAdd('vault', ps, null, {reason: `近似重複清理：保留的是 ${k}`});
      const gone = new Set(paths);
      I.groups = G.map(g => Object.assign({}, g, {items: g.items.filter(x => !gone.has(x.path))})).filter(g => g.items.length > 1);
      const keepTicks = new Set([...drop].filter(p => !gone.has(p))); keepTicks.groups = I.groups; I.nearDrop = keepTicks;
      I.items = (I.items || []).filter(x => !gone.has(x.path));
      HZ.post('/api/images/rescan', {}).catch(() => { });
      I.paintNear();
    };
    const slider = h('select', {onchange: e => { I.nearDist = +e.target.value; I.reload(); }},
      ...[[2, '幾乎一模一樣'], [4, '同一張（不同大小／壓縮）'], [7, '很像（含微調，盡量找）'], [10, '寬鬆（可能誤判，盡量找）']].map(([v, t]) => h('option', {value: v, text: '判斷：' + t, selected: (I.nearDist || 4) === v})));
    box.append(h('div', {class: 'row wrap', style: {marginBottom: '8px'}}, h('span', {class: 'small muted', text: `${G.length} 組近似重複（同一張圖存了好幾份：不同大小、重新壓縮、轉檔）。★ = 建議保留（像素最多、最清晰、檔案最大）。點縮圖切換勾選。`}),
      slider, h('span', {class: 'grow'}), total,
      h('button', {class: 'primary', onclick: () => clean([...drop], '全部照目前勾選')}, '勾選的全部放進保管區')));
    for (const g of G.slice(0, 400)) {
      const row = h('div', {class: 'iseries'});
      for (const it of g.items) {
        const wrap = h('div', {class: 'ndup' + (it.keep ? ' keep' : '') + (drop.has(it.path) ? ' drop' : ''), style: {width: Math.round(120 * Math.min(3, Math.max(0.3, (it.w || 1) / (it.h || 1)))) + 'px'}, title: `${it.path}\n${it.w}×${it.h}　${HZ.fmtSize(it.size || 0)}${it.blur != null ? '　清晰度 ' + Math.round(it.blur) : ''}`},
          h('img', {loading: 'lazy', src: thumb(it.path)}), h('span', {class: 'nlab', text: (it.keep ? '★ ' : '') + `${it.w}×${it.h} ${HZ.fmtSize(it.size || 0)}`}));
        wrap.onclick = e => { if (e.altKey) return I.view(g.items, g.items.indexOf(it)); if (drop.has(it.path)) drop.delete(it.path); else drop.add(it.path);
          if (g.items.every(x => drop.has(x.path))) { drop.delete(it.path); HZ.toast('每一組至少要留一張'); }
          wrap.classList.toggle('drop', drop.has(it.path)); upd(); };
        wrap.ondblclick = () => I.view(g.items, g.items.indexOf(it));
        row.append(wrap);
      }
      box.append(h('div', {class: 'dgroup'}, h('div', {class: 'row'}, h('b', {text: `${g.n} 張`}), h('span', {class: 'muted small', text: '可騰出 ' + HZ.fmtSize(g.save)}), h('span', {class: 'grow'}),
        h('button', {class: 'sm', onclick: () => clean(g.items.filter(x => drop.has(x.path)).map(x => x.path), '這一組')}, '這組勾選的放進保管區')), row));
    }
    if (!G.length) box.append(h('div', {class: 'empty', text: '沒有找到近似重複的圖片'}));
    else box.append(h('div', {class: 'small muted', text: '雙擊縮圖放大看。'}));
    upd(); I.space.append(box);
  };
  I.paintSeries = function () {
    I.space.style.height = ''; I.space.innerHTML = '';
    const box = h('div', {style: {padding: '8px 10px'}});
    box.append(h('div', {class: 'small muted', text: `${I.groups.length} 組相近套圖（同一個資料夾、拍攝時間接近、畫面相似的連續照片）`}));
    for (const g of I.groups.slice(0, 300)) {
      const row = h('div', {class: 'iseries'});
      g.items.slice(0, 40).forEach((it, k) => { const im = h('img', {loading: 'lazy', src: thumb(it.path), title: HZ.base(it.path)}); im.onclick = () => I.view(g.items, k); row.append(im); });
      box.append(h('div', {class: 'dgroup'}, h('div', {class: 'row'}, h('b', {text: `${g.n} 張`}), h('span', {class: 'muted small ell', text: `${g.folder}　${HZ.fmtDate(g.t0)}～${HZ.fmtDate(g.t1).slice(11)}`}), h('span', {class: 'grow'}),
        h('button', {class: 'sm', onclick: () => HZ.pickTarget('move', g.items.map(x => ({path: x.path, name: HZ.base(x.path)})))}, '整組移到…'),
        h('button', {class: 'sm', onclick: () => { HZ.go('explorer'); HZ.pages.explorer.open(g.folder, HZ.base(g.items[0].path)); }}, '📂')), row));
    }
    if (!I.groups.length) box.append(h('div', {class: 'empty', text: '沒有找到相近套圖'}));
    I.space.append(box);
  };
  I.allPaths = async function () {
    if (I.mode === 'similar') return I.items.map(x => x.path);
    if (I.total > 50000) { HZ.toast('超過 5 萬張，請先加條件縮小範圍'); return null; }
    const r = await HZ.post('/api/images/query', Object.assign({}, I.f, {offset: 0, limit: Math.max(1, I.total)}));
    return r.items.map(x => x.path);
  };
  I.bulkMenu = function (e) {
    const n = I.mode === 'similar' ? I.items.length : I.total;
    if (!n || I.mode === 'series' || I.mode === 'near') { HZ.toast('先在「全部」或「相似」裡篩選出要處理的圖片'); return; }
    const as = ps => ps.map(p => ({path: p, name: HZ.base(p)}));
    HZ.menu(e.clientX, e.clientY, [
      {icon: '📋', text: `複製這 ${n.toLocaleString()} 張到…`, run: async () => { const ps = await I.allPaths(); if (ps) HZ.pickTarget('copy', as(ps)); }},
      {icon: '🚚', text: `移動這 ${n.toLocaleString()} 張到…`, run: async () => { const ps = await I.allPaths(); if (ps) HZ.pickTarget('move', as(ps)); }},
      '-',
      {icon: '🛟', text: `把這 ${n.toLocaleString()} 張放進保管區…`, run: async () => {
        const ps = await I.allPaths(); if (!ps) return;
        if (!await HZ.confirm('放進保管區', `${ps.length.toLocaleString()} 張圖片會移進各自硬碟的保管區（${HZ.vaultDays()} 天內可以還原）。`, '放進保管區')) return;
        const why = '圖片分類：' + (I.f.q ? `搜尋「${I.f.q}」` : '') + Object.entries(I.f).filter(([k]) => !['sort', 'scope', 'q'].includes(k)).map(([k, v]) => `${k}=${v}`).join(' ');
        await HZ.queueAdd('vault', ps, null, {reason: why.trim() || '圖片分類：整批放進保管區'});
      }},
      {icon: '📅', text: `依拍攝日期整理這 ${n.toLocaleString()} 張…`, run: () => I.organize()},
      {icon: '⭐', text: `這 ${n.toLocaleString()} 張全部加入最愛`, run: async () => { const ps = await I.allPaths(); if (ps) { await HZ.post('/api/images/star', {paths: ps, on: true}); HZ.toast('已加入最愛', 'ok'); I.loadFacets(); I.reload(); } }},
      {icon: '🔗', text: '複製所有路徑', run: async () => { const ps = await I.allPaths(); if (ps) HZ.copyText(ps.join('\n')); }},
    ]);
  };
  /* 依拍攝日期整理: K:\照片\2024\12\... (EXIF date, else modified date); same drive = instant, nothing replaced */
  I.organize = async function () {
    const ps = await I.allPaths(); if (!ps || !ps.length) return;
    const guess = I.f.scope || HZ.dir(ps[0]);
    const root = h('input', {value: guess, style: {width: '100%'}});
    const pat = h('select', {}, ...[['YYYY/MM', '2024\\12'], ['YYYY/YYYY-MM', '2024\\2024-12'], ['YYYY-MM', '2024-12'], ['YYYY/MM/DD', '2024\\12\\25'], ['YYYY/YYYY-MM-DD', '2024\\2024-12-25']].map(([v, t]) => h('option', {value: v, text: t})));
    const kind = h('select', {}, h('option', {value: 'move', text: '移動（同一顆硬碟瞬間完成）'}), h('option', {value: 'copy', text: '複製（原本的不動）'}));
    const prev = h('div', {class: 'small muted', style: {maxHeight: '160px', overflow: 'auto', whiteSpace: 'pre'}});
    let taken = {};
    try { taken = (await HZ.post('/api/taken', {paths: ps})).taken || {}; } catch (e) { }
    const mt = {}; for (const x of I.items) mt[x.path] = x.taken || x.mtime;
    const plan = () => {
      const r = root.value.trim().replace(/[\\/]+$/, ''), sep = r.includes('\\') || /^[A-Za-z]:/.test(r) ? '\\' : '/';
      const pad = v => String(v).padStart(2, '0');
      return ps.map(p => {
        const t = taken[p] || mt[p]; const d = t ? new Date(t * 1000) : null;
        const sub = d ? pat.value.replace('YYYY', d.getFullYear()).replace('YYYY', d.getFullYear()).replace('MM', pad(d.getMonth() + 1)).replace('MM', pad(d.getMonth() + 1)).replace('DD', pad(d.getDate())).replace(/\//g, sep) : '日期不明';
        return [p, r + sep + sub + sep + HZ.base(p)];
      }).filter(([a, b]) => a.toLowerCase() !== b.toLowerCase());
    };
    const upd = () => { const pl = plan(); prev.textContent = pl.slice(0, 12).map(([a, b]) => `${HZ.base(a)}  →  ${b}`).join('\n') + (pl.length > 12 ? `\n…共 ${pl.length.toLocaleString()} 張` : `\n共 ${pl.length.toLocaleString()} 張`); };
    for (const el of [root, pat]) el.addEventListener('input', upd); upd();
    const ok = await HZ.dialog({title: `📅 依拍攝日期整理 ${ps.length.toLocaleString()} 張`, width: 640, body: h('div', {class: 'col'},
      h('div', {class: 'small muted', text: '用照片的拍攝日期（EXIF；沒有就用修改日期）分到年／月資料夾。同名時自動另取名字，不會覆蓋；整理完可以在檔案總管按 Ctrl+Z 復原（移動時）。'}),
      h('div', {class: 'row'}, h('span', {class: 'muted', text: '整理到'}), root), h('div', {class: 'row'}, h('span', {class: 'muted', text: '資料夾格式'}), pat, kind), prev),
      buttons: [{text: '取消', value: null}, {text: '開始整理', value: true, primary: true}]});
    if (!ok) return;
    const pl = plan(); if (!pl.length) { HZ.toast('都已經在正確的位置了'); return; }
    try {
      await HZ.post('/api/queue/add', {kind: kind.value, src: [], dst: root.value.trim(), opts: {pairs: pl, conflict: 'rename'}});
      HZ.toast(`已加入佇列：${kind.value === 'move' ? '移動' : '複製'} ${pl.length.toLocaleString()} 張`, 'ok');
      setTimeout(() => { HZ.post('/api/images/rescan', {}).catch(() => { }); }, 3000);
    } catch (e) { HZ.err(e); }
  };
  I.menu = function (it) {
    const item = {path: it.path, name: HZ.base(it.path), dir: false, ext: (it.path.split('.').pop() || '').toLowerCase()};
    return [{icon: it.star ? '⭐' : '☆', text: it.star ? '取消最愛' : '加入最愛', run: async () => { await HZ.post('/api/images/star', {paths: [it.path], on: !it.star}); it.star = it.star ? 0 : 1; I.paint(true); I.loadFacets(); }},
      {icon: '🔍', text: '找相似的圖片', run: () => { I.simOf = it.path; I.mode = 'similar'; I.renderTop(); I.reload(); }},
      {icon: '🎨', text: `同顏色（${it.c1}）`, run: () => I.set('color', it.c1)},
      '-', ...HZ.itemMenu([item], {})];
  };
  I.view = function (list, i) {
    const ov = h('div', {class: 'cview'}), img = h('img'), side = h('div', {class: 'cside'});
    ov.append(h('div', {class: 'cstage'}, img), side); document.body.append(ov);
    let sx = null;                                                   // phone: swipe left / right on the picture
    img.addEventListener('touchstart', e => { sx = e.touches[0].clientX; }, {passive: true});
    img.addEventListener('touchend', e => { if (sx == null) return; const dx = e.changedTouches[0].clientX - sx; sx = null; if (Math.abs(dx) > 50) { i += dx < 0 ? 1 : -1; show(); } });
    const show = () => {
      i = (i + list.length) % list.length; const it = list[i]; img.src = HZ.fileUrl(it.path);
      side.innerHTML = `<div class="row"><b class="ell">${esc(HZ.base(it.path))}</b><span class="grow"></span><button class="sm" data-a="close">✕</button></div>
        <div class="small muted ell">${esc(HZ.dir(it.path))}</div>
        <div class="kv small" style="margin-top:8px"><b>尺寸</b><span>${it.w || '?'} × ${it.h || '?'}</span>${it.taken || it.mtime ? `<b>時間</b><span>${HZ.fmtDate(it.taken || it.mtime)}</span>` : ''}
        ${it.model ? `<b>相機</b><span>${esc(it.model)}</span>` : ''}${it.faces != null ? `<b>人臉</b><span>${it.faces}</span>` : ''}${it.size ? `<b>大小</b><span>${HZ.fmtSize(it.size)}</span>` : ''}</div>
        ${it.why ? `<div class="pill acc" style="margin-top:8px;white-space:normal">符合：${esc(it.why)}</div>` : ''}
        ${(it.colors || []).length ? `<h3>顏色</h3><div class="row wrap">${it.colors.map(([c, p]) => `<span class="pill"><i class="sw" style="background:${HEX[c]}"></i> ${c} ${Math.round(p * 100)}%</span>`).join('')}</div>` : ''}
        <div class="row wrap" style="margin-top:12px"><button class="sm" data-a="sim">找相似的</button><button class="sm" data-a="rev">在總管顯示</button><button class="sm" data-a="dl">下載</button><button class="sm" data-a="cimg">複製圖片</button><button class="sm" data-a="star">${it.star ? '⭐ 取消最愛' : '☆ 加入最愛'}</button></div>
        <div class="row" style="margin-top:10px"><button class="sm" data-a="prev">‹ 上一張</button><span class="small muted">${i + 1} / ${list.length}</span><button class="sm" data-a="next">下一張 ›</button></div>
        <div class="small muted" style="margin-top:4px">← → 切換　F 最愛　Esc 關閉</div>`;
      side.querySelector('[data-a=prev]').onclick = () => { i--; show(); };
      side.querySelector('[data-a=next]').onclick = () => { i++; show(); };
      side.querySelector('[data-a=close]').onclick = close;
      side.querySelector('[data-a=sim]').onclick = () => { close(); I.simOf = it.path; I.mode = 'similar'; I.renderTop(); I.reload(); };
      side.querySelector('[data-a=rev]').onclick = () => { close(); HZ.go('explorer'); HZ.pages.explorer.open(HZ.dir(it.path), HZ.base(it.path)); };
      side.querySelector('[data-a=dl]').onclick = () => HZ.download([{path: it.path, name: HZ.base(it.path)}]);
      side.querySelector('[data-a=cimg]').onclick = () => HZ.copyImage(it.path);
      side.querySelector('[data-a=star]').onclick = () => toggleStar(it);
    };
    const toggleStar = async it => {
      const on = !it.star;
      try { await HZ.post('/api/images/star', {paths: [it.path], on}); it.star = on ? 1 : 0; show(); I.paint(true); } catch (e) { HZ.err(e); }
    };
    const key = e => { if (e.ctrlKey || e.metaKey || e.altKey) return; if (e.key === 'Escape') close(); else if (e.key === 'ArrowRight') { i++; show(); } else if (e.key === 'ArrowLeft') { i--; show(); }
      else if (e.key.toLowerCase() === 'f') toggleStar(list[(i + list.length) % list.length]); else return; e.preventDefault(); e.stopPropagation(); };
    function close() { document.removeEventListener('keydown', key, true); ov.remove(); }
    ov.addEventListener('click', e => { if (e.target === ov) close(); });
    document.addEventListener('keydown', key, true); show();
  };
  I.onShow = function () { I.loadStatus(); I.loadFacets(); I.reload(); HZ.every('images', 3000, () => { I.loadStatus(); if (I.st && I.st.state === 'running') I.loadFacets(); }); };
  I.onHide = () => HZ.stop('images');
  HZ.page('images', I);
})();

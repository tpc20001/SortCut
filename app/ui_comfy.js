/* HotZone FM — 生圖比較 (ComfyUI / A1111 XY table): pick X / Y / page axes from the settings that differ between
   images, lay them out as a big table (virtualised, 200 x 200 is fine), tune gaps / lines / feathered edges,
   open any cell, pick favourites, export the table as one PNG. */
'use strict';
(function () {
  const {h, esc} = HZ;
  const G = {title: '生圖比較', d: null, path: '', rec: false, x: '', y: '', z: '', zi: 0, filters: {}, picks: new Set(), hiddenX: new Set(), hiddenY: new Set(),
    o: {cell: innerWidth < 600 ? 120 : 160, gap: 4, lines: false, lineColor: '#3a4654', feather: 0, fit: 'cover', labels: true, labelSize: 12, bg: '#0b0e12', sortX: 'asc', sortY: 'asc', onlyMeta: true, round: 4, picksOnly: false, multi: 'first', cellLabel: ''}, order: {}, cmpA: null};
  const NONE = '\u2205';
  const nkey = v => v === undefined || v === null ? NONE : (typeof v === 'string' ? v : JSON.stringify(v));
  const cmpVal = (a, b) => { const na = +a, nb = +b; if (a !== NONE && b !== NONE && !isNaN(na) && !isNaN(nb)) return na - nb; if (a === NONE) return 1; if (b === NONE) return -1; return String(a).localeCompare(String(b), 'zh-Hant', {numeric: true}); };
  const short = (v, n = 40) => { v = v === NONE ? '（無）' : String(v); return v.length > n ? v.slice(0, n - 1) + '…' : v; };

  /* ------------------------------------------------------------------ persistence */
  const LS = 'hz.comfy.';
  function savePrefs() {
    try {
      localStorage.setItem(LS + 'o', JSON.stringify(G.o));
      if (G.path) localStorage.setItem(LS + 'f:' + G.path, JSON.stringify({x: G.x, y: G.y, z: G.z, filters: Object.fromEntries(Object.entries(G.filters).map(([k, v]) => [k, [...v]])),
        picks: [...G.picks], hx: [...G.hiddenX], hy: [...G.hiddenY], order: G.order}));
      const rec = JSON.parse(localStorage.getItem(LS + 'recent') || '[]').filter(p => p !== G.path); if (G.path) rec.unshift(G.path);
      localStorage.setItem(LS + 'recent', JSON.stringify(rec.slice(0, 12)));
    } catch (e) { }
  }
  function loadPrefs(path) {
    try { Object.assign(G.o, JSON.parse(localStorage.getItem(LS + 'o') || '{}')); } catch (e) { }
    try {
      const f = JSON.parse(localStorage.getItem(LS + 'f:' + path) || 'null');
      if (f) {
        G.x = f.x || ''; G.y = f.y || ''; G.z = f.z || ''; G.picks = new Set(f.picks || []); G.hiddenX = new Set(f.hx || []); G.hiddenY = new Set(f.hy || []);
        G.filters = Object.fromEntries(Object.entries(f.filters || {}).map(([k, v]) => [k, new Set(v)])); G.order = f.order || {}; return true;
      }
    } catch (e) { }
    return false;
  }

  /* ------------------------------------------------------------------ page */
  G.build = function (root) {
    try { Object.assign(G.o, JSON.parse(localStorage.getItem(LS + 'o') || '{}')); } catch (e) { }
    G.pathEl = h('input', {placeholder: 'ComfyUI 的 output 資料夾，例如 D:\\ComfyUI\\output\\2026-10-21', style: {flex: '1', minWidth: '260px'}});
    G.pathEl.onkeydown = e => { if (e.key === 'Enter') G.open(G.pathEl.value.trim()); };
    G.recEl = h('input', {type: 'checkbox'});
    G.recent = h('select', {title: '最近開過的資料夾', onchange: e => { if (e.target.value) G.open(e.target.value); e.target.value = ''; }});
    G.status = h('span', {class: 'small muted'});
    G.liveEl = h('input', {type: 'checkbox', onchange: e => { try { localStorage.setItem(LS + 'live', e.target.checked ? '1' : ''); } catch (er) { } G.live(); }});
    try { G.liveEl.checked = localStorage.getItem(LS + 'live') === '1'; } catch (e) { }
    const bar1 = h('div', {class: 'sbox'}, h('b', {text: '🖼 生圖比較'}), G.pathEl, h('label', {class: 'row small'}, G.recEl, '含子資料夾'),
      h('label', {class: 'row small', title: 'ComfyUI 還在出圖時打開：新圖一產生就自動加進表格（新的會亮框 20 秒），版面和捲動位置不變'}, G.liveEl, '即時跟隨'),
      h('button', {class: 'primary', onclick: () => G.open(G.pathEl.value.trim())}, '讀取'), G.recent,
      h('button', {class: 'sm ionly-m', onclick: () => G.ctl.classList.toggle('open')}, '⚙ 版面'), G.status);
    G.ctl = h('div', {class: 'sbox cctl', style: {paddingTop: '4px'}});
    G.info = h('div', {class: 'sinfo'});
    G.wrap = h('div', {class: 'cwrap'});
    G.corner = h('div', {class: 'ccorner'}); G.top = h('div', {class: 'ctop'}); G.left = h('div', {class: 'cleft'});
    G.topIn = h('div', {class: 'cin'}); G.leftIn = h('div', {class: 'cin'}); G.top.append(G.topIn); G.left.append(G.leftIn);
    G.body = h('div', {class: 'cbody', tabindex: '0'}); G.space = h('div', {class: 'cspace'}); G.body.append(G.space);
    G.wrap.append(G.corner, G.top, G.left, G.body);
    root.append(bar1, G.ctl, G.info, G.wrap);
    G.body.addEventListener('scroll', () => { G.topIn.style.transform = `translateX(${-G.body.scrollLeft}px)`; G.leftIn.style.transform = `translateY(${-G.body.scrollTop}px)`; G.paint(); });
    G.body.addEventListener('wheel', e => {
      if (G.loupe.on) { e.preventDefault(); G.loupe.k = Math.max(1.5, Math.min(12, +(G.loupe.k * (e.deltaY < 0 ? 1.25 : 0.8)).toFixed(2))); G.applyLoupe(); return; }
      if (!e.ctrlKey) return; e.preventDefault();
      const r = G.body.getBoundingClientRect(), mx = e.clientX - r.left + G.body.scrollLeft, my = e.clientY - r.top + G.body.scrollTop, old = G.step();
      G.o.cell = Math.max(24, Math.min(1024, Math.round(G.o.cell * (e.deltaY < 0 ? 1.15 : 1 / 1.15))));
      const k = G.step() / old; G.layout(); G.body.scrollLeft = mx * k - (e.clientX - r.left); G.body.scrollTop = my * k - (e.clientY - r.top); G.syncCtl(); savePrefs();
    }, {passive: false});
    let drag = null;                                                                        // middle-button / space drag to pan
    G.body.addEventListener('mousedown', e => { if (e.button === 1 || (e.button === 0 && G._space)) { e.preventDefault(); drag = {x: e.clientX, y: e.clientY, l: G.body.scrollLeft, t: G.body.scrollTop}; } });
    window.addEventListener('mousemove', e => { if (drag) { G.body.scrollLeft = drag.l - (e.clientX - drag.x); G.body.scrollTop = drag.t - (e.clientY - drag.y); } });
    window.addEventListener('mouseup', () => { drag = null; });
    document.addEventListener('keydown', e => { if (HZ.cur === 'comfy' && e.code === 'Space' && e.target === G.body) { G._space = true; e.preventDefault(); } });
    document.addEventListener('keyup', e => { if (e.code === 'Space') G._space = false; });
    new ResizeObserver(() => G.paint(true)).observe(G.body);
    G.fillRecent();
  };
  G.fillRecent = function () {
    let rec = []; try { rec = JSON.parse(localStorage.getItem(LS + 'recent') || '[]'); } catch (e) { }
    G.recent.innerHTML = ''; G.recent.append(h('option', {value: '', text: '最近的資料夾…'}), ...rec.map(p => h('option', {value: p, text: p})));
  };

  /* ------------------------------------------------------------------ load */
  G.open = async function (path, keepPrefs) {
    if (!path) return;
    G.path = path; G.pathEl.value = path; G.rec = G.recEl.checked;
    const q = {path, recursive: G.rec ? '1' : '0'};
    try { await HZ.post('/api/comfy/scan', {path, recursive: G.rec}); } catch (e) { HZ.err(e); return; }
    for (let i = 0; i < 6000; i++) {
      const st = await HZ.get('/api/comfy/status', q).catch(() => ({state: 'error'}));
      if (st.state === 'running') { G.status.textContent = `讀取參數… ${st.done}/${st.total}`; await new Promise(r => setTimeout(r, 300)); continue; }
      if (st.state === 'error') { HZ.err(st.msg || '讀取失敗'); return; }
      break;
    }
    let d; try { d = await HZ.get('/api/comfy/data', q); } catch (e) { HZ.err(e); return; }
    if (keepPrefs && G.d && G.path === path) {                          // live refresh: remember which ones are new
      const old = new Set(G.d.images.map(x => x.path)), now = Date.now();
      for (const it of d.images) if (!old.has(it.path)) G.fresh.set(it.path, now);
    } else G.fresh = new Map();
    const sl = G.body.scrollLeft, stp = G.body.scrollTop;
    G.d = d;
    for (const it of d.images) it.k = {};
    const had = keepPrefs ? true : loadPrefs(path);
    const keys = new Set(d.params.map(p => p.key));
    if (!had || !keys.has(G.x)) G.autoAxes();
    if (G.y && !keys.has(G.y)) G.y = ''; if (G.z && !keys.has(G.z)) G.z = '';
    for (const k of Object.keys(G.filters)) if (!keys.has(k)) delete G.filters[k];
    G.status.textContent = `${d.images.length} 張，${d.with_meta} 張有生成參數`;
    G.renderCtl(); G.layout(); savePrefs(); G.fillRecent();
    if (keepPrefs) { G.body.scrollLeft = sl; G.body.scrollTop = stp; }
    G.peekSig = null; G.live();
  };
  G.fresh = new Map();
  G.live = function () {
    HZ.stop('comfy-live');
    if (!G.liveEl.checked || !G.path) return;
    HZ.every('comfy-live', 4000, async () => {
      if (HZ.cur !== 'comfy' || G._liveBusy || document.querySelector('.cview')) return;
      try {
        const sig = await HZ.get('/api/comfy/peek', {path: G.path, recursive: G.rec ? '1' : '0'}), k = sig.n + '|' + sig.newest;
        if (G.peekSig === null) { G.peekSig = k; return; }
        if (k === G.peekSig) return;
        G.peekSig = k; G._liveBusy = true;
        const before = G.d ? G.d.images.length : 0;
        await G.open(G.path, true);
        const added = (G.d ? G.d.images.length : 0) - before;
        if (added > 0) G.status.textContent += `　（剛加入 ${added} 張）`;
      } catch (e) { } finally { G._liveBusy = false; }
    });
  };
  G.autoAxes = function () {
    const ps = G.d.params.filter(p => p.kind !== 'id' && p.group !== 'node' && p.key !== 'positive' && p.distinct > 1 && p.distinct <= 300);
    const pick = ps.filter(p => p.group === 'main');
    G.x = (pick.find(p => p.key === 'seed') || pick[0] || ps[0] || {}).key || '';
    G.y = (pick.find(p => p.key !== G.x && p.key === '_pos_diff') || pick.find(p => p.key !== G.x) || {}).key || '';
    G.z = ''; G.filters = {}; G.hiddenX.clear(); G.hiddenY.clear();
    const rest = pick.filter(p => p.key !== G.x && p.key !== G.y && p.key !== 'positive' && p.distinct <= 50);   // still several images per cell? page through the next setting
    if (rest.length) {
      const per = new Map();
      for (const it of G.d.images) { const k = nkey(it.p[G.x]) + '|' + nkey(it.p[G.y]); per.set(k, (per.get(k) || 0) + 1); }
      if ([...per.values()].some(n => n > 1)) G.z = rest[0].key;
    }
  };

  /* ------------------------------------------------------------------ controls */
  G.renderCtl = function () {
    const d = G.d, o = G.o; G.ctl.innerHTML = '';
    if (!d) return;
    const opt = (sel) => [h('option', {value: '', text: '（不用）'}), ...['main', 'phrase', 'node'].flatMap(gr => {
      const ps = d.params.filter(p => p.group === gr); if (!ps.length) return [];
      return [h('optgroup', {label: {main: '常用參數', phrase: '提示詞裡的詞', node: '節點參數（進階）'}[gr]}, ...ps.map(p => h('option', {value: p.key, text: `${p.label}（${p.distinct}）`, selected: p.key === sel})))];
    })];
    const axis = (label, k) => h('label', {class: 'row small'}, h('b', {text: label}), h('select', {onchange: e => { G[k] = e.target.value; G.zi = 0; G.hiddenX.clear(); G.hiddenY.clear(); G.layout(); savePrefs(); G.renderCtl(); }}, ...opt(G[k])));
    const sorter = k => h('button', {class: 'sm ghost', title: '反向排序', onclick: () => { o[k] = o[k] === 'asc' ? 'desc' : 'asc'; G.layout(); savePrefs(); G.renderCtl(); }}, o[k] === 'asc' ? '↑' : '↓');
    const swap = h('button', {class: 'sm', title: '對調 X 和 Y', onclick: () => { [G.x, G.y] = [G.y, G.x]; [G.hiddenX, G.hiddenY] = [G.hiddenY, G.hiddenX]; G.layout(); savePrefs(); G.renderCtl(); }}, '⇄');
    const slider = (label, k, min, max, step, fmt) => {
      const v = h('span', {class: 'small', style: {width: '44px'}, text: fmt(o[k])});
      const r = h('input', {type: 'range', min, max, step, value: o[k], style: {width: '110px'}});
      r.oninput = () => { o[k] = +r.value; v.textContent = fmt(o[k]); G.layout(); }; r.onchange = savePrefs;
      G['s_' + k] = r; G['v_' + k] = v; G['f_' + k] = fmt;
      return h('label', {class: 'row small'}, h('span', {class: 'muted', text: label}), r, v);
    };
    const tg = (label, k, title) => h('label', {class: 'row small', title: title || ''}, h('input', {type: 'checkbox', checked: !!o[k], onchange: e => { o[k] = e.target.checked; G.layout(); savePrefs(); }}), label);
    const zp = d.params.find(p => p.key === G.z);
    G.ctl.append(
      h('div', {class: 'row wrap'}, axis('X 軸（欄）', 'x'), sorter('sortX'), swap, axis('Y 軸（列）', 'y'), sorter('sortY'), axis('分頁軸', 'z'),
        G.z ? G.zNav() : null,
        h('button', {class: 'sm', onclick: G.filterDlg}, '篩選' + (Object.keys(G.filters).length ? `（${Object.keys(G.filters).length}）` : '')),
        h('button', {class: 'sm', onclick: () => { G.autoAxes(); G.layout(); savePrefs(); G.renderCtl(); }, title: '自動挑選變化最多的參數'}, '自動'),
        (G.hiddenX.size || G.hiddenY.size) ? h('button', {class: 'sm', onclick: () => { G.hiddenX.clear(); G.hiddenY.clear(); G.layout(); savePrefs(); G.renderCtl(); }}, `顯示隱藏的列／欄（${G.hiddenX.size + G.hiddenY.size}）`) : null),
      h('div', {class: 'row wrap'},
        slider('大小', 'cell', 24, 768, 4, v => v + 'px'), slider('間距', 'gap', -120, 60, 1, v => v + 'px'), slider('邊緣漸層', 'feather', 0, 50, 1, v => v + '%'),
        slider('圓角', 'round', 0, 40, 1, v => v + 'px'),
        tg('格線', 'lines'), h('input', {type: 'color', value: o.lineColor, title: '格線顏色', onchange: e => { o.lineColor = e.target.value; G.layout(); savePrefs(); }}),
        h('label', {class: 'row small'}, h('span', {class: 'muted', text: '背景'}), h('input', {type: 'color', value: o.bg, onchange: e => { o.bg = e.target.value; G.layout(); savePrefs(); }})),
        h('select', {onchange: e => { o.fit = e.target.value; G.layout(); savePrefs(); }}, h('option', {value: 'cover', text: '填滿格子', selected: o.fit === 'cover'}), h('option', {value: 'contain', text: '完整顯示', selected: o.fit === 'contain'})),
        tg('標籤', 'labels'),
        h('select', {title: '同一格有多張時', onchange: e => { o.multi = e.target.value; G.layout(); savePrefs(); }}, h('option', {value: 'first', text: '多張：顯示第一張', selected: o.multi === 'first'}), h('option', {value: 'mosaic', text: '多張：拼成小格', selected: o.multi === 'mosaic'})),
        h('select', {title: '在每一格上顯示', onchange: e => { o.cellLabel = e.target.value; G.layout(); savePrefs(); }}, h('option', {value: '', text: '格內文字：無'}),
          ...d.params.filter(p => p.kind !== 'id' || p.key === '_file').map(p => h('option', {value: p.key, text: '格內文字：' + p.label, selected: o.cellLabel === p.key}))),
        tg('只看有參數的', 'onlyMeta'), tg('只看挑選的', 'picksOnly', '按 P 或右上角 ☆ 挑選'),
        h('button', {class: 'sm', onclick: G.copyPicks}, `把挑選的複製到…（${G.picks.size}）`),
        G.picks.size ? h('button', {class: 'sm', title: '把挑選的圖片打包成一個 zip 下載（手機也可以）', onclick: () => HZ.download([...G.picks].map(p => ({path: p, name: HZ.base(p)})))}, '⬇ 下載挑選的') : null,
        G.picks.size ? h('button', {class: 'sm', title: '清除所有挑選', onclick: async () => { if (await HZ.confirm('清除挑選', `取消這 ${G.picks.size} 張的挑選？（圖片本身不會動）`, '清除')) { G.picks.clear(); savePrefs(); G.paint(true); G.renderCtl(); G.headers(); } }}, '✕ 清除挑選') : null,
        G.picks.size >= 3 ? h('button', {class: 'sm', title: '每個參數的每個值：挑選了幾張、佔多少比例（找出哪個設定最常被你選中）', onclick: G.pickStats}, '📊 挑選分析') : null,
        h('button', {class: 'sm', onclick: G.exportPng}, '匯出成一張圖')));
  };
  /* which settings win: for every parameter (not only the axes), the share of its images you picked, per value */
  G.pickStats = function () {
    const imgs = G.base().filter(it => it.meta || !G.o.onlyMeta); const pickedN = imgs.filter(it => G.picks.has(it.path)).length;
    const rows = [];
    for (const p of G.d.params.filter(p => p.kind !== 'id' && p.distinct >= 2 && p.distinct <= 40)) {
      const m = new Map();
      for (const it of imgs) { const v = nkey(it.p[p.key]); const e = m.get(v) || [0, 0]; e[0]++; if (G.picks.has(it.path)) e[1]++; m.set(v, e); }
      const vals = [...m.entries()].filter(([v, e]) => e[0] >= 2).map(([v, [n, k]]) => ({v, n, k, r: k / n}));
      if (vals.length < 2) continue;
      const rs = vals.map(x => x.r); rows.push({p, vals: vals.sort((a, b) => b.r - a.r || b.k - a.k), spread: Math.max(...rs) - Math.min(...rs)});
    }
    rows.sort((a, b) => b.spread - a.spread);
    const body = h('div', {class: 'col', style: {maxHeight: '64vh', overflow: 'auto', minWidth: 'min(620px,88vw)', gap: '10px'}},
      h('div', {class: 'small muted', text: `目前範圍 ${imgs.length.toLocaleString()} 張，挑選了 ${pickedN} 張。差異最大的參數排在最上面：挑選比例差越多，代表這個參數越影響你的喜好。`}),
      ...rows.slice(0, 30).map(({p, vals, spread}) => h('div', {},
        h('div', {class: 'row'}, h('b', {text: p.label}), h('span', {class: 'small muted', text: `差距 ${Math.round(spread * 100)}%`}), h('span', {class: 'grow'}),
          G.x !== p.key ? h('button', {class: 'sm ghost', title: '把這個參數放到 X 軸', onclick: () => { G.x = p.key; G.hiddenX.clear(); G.layout(); savePrefs(); G.renderCtl(); HZ._dlgClose && HZ._dlgClose(null); }}, '設為 X 軸') : null),
        ...vals.slice(0, 12).map(x => h('div', {class: 'row small', style: {gap: '8px'}},
          h('span', {class: 'ell', style: {width: '200px'}, title: x.v, text: short(x.v, 40)}),
          h('div', {class: 'bar', style: {flex: '1', height: '8px'}}, h('i', {class: 'ok', style: {width: Math.round(x.r * 100) + '%'}})),
          h('span', {style: {width: '110px', textAlign: 'right'}, text: `★${x.k} / ${x.n}（${Math.round(x.r * 100)}%）`}))))),
      !rows.length ? h('div', {class: 'muted', text: '沒有可以比較的參數（每個參數至少要有兩個值、每個值至少兩張）'}) : null);
    HZ.dialog({title: '📊 挑選分析', body, width: 'min(720px,94vw)'});
  };
  G.syncCtl = function () {
    for (const k of ['cell', 'gap', 'feather', 'round']) if (G['s_' + k]) { G['s_' + k].value = G.o[k]; G['v_' + k].textContent = G['f_' + k](G.o[k]); }
  };
  G.zNav = function () {
    const vals = G.axisVals(G.z, G.base(), 'sortX');
    if (G.zi >= vals.length) G.zi = 0;
    const lab = h('span', {class: 'small', style: {maxWidth: '260px'}, class: 'ell', text: `${G.zi + 1}/${vals.length}：${short(vals[G.zi], 30)}`});
    const go = dlt => { G.zi = (G.zi + dlt + vals.length) % vals.length; G.layout(); G.renderCtl(); };
    return h('span', {class: 'row'}, h('button', {class: 'sm', onclick: () => go(-1), title: 'PageUp'}, '◀'), lab, h('button', {class: 'sm', onclick: () => go(1), title: 'PageDown'}, '▶'));
  };
  G.filterDlg = function () {
    const d = G.d; const body = h('div', {class: 'col', style: {maxHeight: '60vh', overflow: 'auto', minWidth: 'min(640px,86vw)'}});
    for (const p of d.params.filter(p => p.kind !== 'id' && p.distinct <= 400)) {
      const vals = G.axisVals(p.key, d.images, 'sortX', true);
      const cur = G.filters[p.key];
      const row = h('div', {class: 'chips'});
      for (const v of vals) row.append(h('span', {class: 'chip' + (!cur || cur.has(v) ? ' on' : ''), title: String(v), text: short(v, 36), onclick: e => {
        const s = G.filters[p.key] || new Set(vals); if (s.has(v)) s.delete(v); else s.add(v);
        if (s.size === vals.length) delete G.filters[p.key]; else G.filters[p.key] = s;
        e.target.classList.toggle('on'); G.layout(); savePrefs();
      }}));
      body.append(h('div', {}, h('b', {class: 'small', text: p.label}), row));
    }
    HZ.dialog({title: '篩選（點一下切換要不要顯示）', body, width: 'min(760px,94vw)', buttons: [{text: '全部顯示', value: 'clear'}, {text: '完成', value: null, primary: true}]}).then(r => {
      if (r === 'clear') { G.filters = {}; G.layout(); savePrefs(); } G.renderCtl();
    });
  };

  /* ------------------------------------------------------------------ data -> table */
  G.base = function () {
    const o = G.o;
    return G.d.images.filter(it => (!o.onlyMeta || it.meta) && (!o.picksOnly || G.picks.has(it.path)) &&
      Object.entries(G.filters).every(([k, s]) => s.has(nkey(it.p[k]))));
  };
  G.axisVals = function (k, imgs, sortKey, all) {
    if (!k) return [NONE];
    const seen = new Map(); for (const it of imgs) { const v = nkey(it.p[k]); seen.set(v, (seen.get(v) || 0) + 1); }
    let vals = [...seen.keys()].sort(cmpVal);
    if (G.o[sortKey] === 'desc') vals.reverse();
    const ord = G.order[k];
    if (ord && ord.length) { const pos = new Map(ord.map((v, i) => [v, i])); vals.sort((a, b) => (pos.has(a) ? pos.get(a) : 1e9 + vals.indexOf(a)) - (pos.has(b) ? pos.get(b) : 1e9 + vals.indexOf(b))); }
    return vals;
  };
  G.layout = function () {
    if (!G.d) return;
    let imgs = G.base();
    if (G.z) { const zv = G.axisVals(G.z, imgs, 'sortX'); const cur = zv[Math.min(G.zi, zv.length - 1)]; imgs = imgs.filter(it => nkey(it.p[G.z]) === cur); }
    let xs = G.axisVals(G.x, imgs, 'sortX').filter(v => !G.hiddenX.has(v)), ys = G.axisVals(G.y, imgs, 'sortY').filter(v => !G.hiddenY.has(v));
    const cells = new Map();
    const xi = new Map(xs.map((v, i) => [v, i])), yi = new Map(ys.map((v, i) => [v, i]));
    let free = false;
    if (!G.x && !G.y) {                                                          // no axes: a plain gallery that wraps
      free = true; const cols = Math.max(1, Math.floor((G.body.clientWidth || 1000) / G.step()));
      xs = Array.from({length: Math.min(cols, imgs.length || 1)}, (_, i) => i + 1); ys = Array.from({length: Math.ceil(imgs.length / cols)}, (_, i) => i + 1);
      imgs.forEach((it, i) => cells.set(`${i % cols}|${Math.floor(i / cols)}`, [it]));
    } else {
      for (const it of imgs) {
        const a = xi.get(nkey(G.x ? it.p[G.x] : undefined)), b = yi.get(nkey(G.y ? it.p[G.y] : undefined));
        if (a === undefined || b === undefined) continue;
        const k = a + '|' + b; if (!cells.has(k)) cells.set(k, []); cells.get(k).push(it);
      }
    }
    G.t = {xs, ys, cells, free, n: imgs.length};
    const o = G.o, st = G.step();
    const lw = o.labels && G.y && !free ? Math.min(innerWidth < 600 ? 92 : 320, Math.max(70, o.labelSize * 14)) : 0, lh = o.labels && G.x && !free ? Math.max(24, o.labelSize * 2 + 10) : 0;
    G.lw = lw; G.lh = lh;
    G.wrap.style.setProperty('--lw', lw + 'px'); G.wrap.style.setProperty('--lh', lh + 'px'); G.wrap.style.background = o.bg;
    G.space.style.width = Math.max(1, xs.length * st - Math.min(0, o.gap) + 8) + 'px'; G.space.style.height = Math.max(1, ys.length * st - Math.min(0, o.gap) + 8) + 'px';
    const multi = [...cells.values()].filter(c => c.length > 1).length;
    const px = G.d.params.find(p => p.key === G.x), py = G.d.params.find(p => p.key === G.y);
    G.info.innerHTML = `<span>${imgs.length.toLocaleString()} 張</span><span>${xs.length} 欄 × ${ys.length} 列</span>` + (px ? `<span>X：${esc(px.label)}</span>` : '') + (py ? `<span>Y：${esc(py.label)}</span>` : '') +
      (multi ? `<span class="warn" title="同一格有多張：可以加一個「分頁軸」或篩選">${multi} 格有多張（顯示第一張，右下角數字）</span>` : '') +
      `<span class="grow"></span><span class="muted">Ctrl+滾輪縮放　按住 Z＝同步放大鏡　中鍵或空白鍵拖曳　點標題只看那一列／欄、右鍵隱藏　P 挑選　? 全部快捷鍵</span>`;
    G.headers(); G.paint(true);
  };
  G.step = () => Math.max(6, G.o.cell + G.o.gap);
  G.headers = function () {
    const {xs, ys, free} = G.t, o = G.o, st = G.step();
    G.topIn.innerHTML = ''; G.leftIn.innerHTML = '';
    if (free || !o.labels) return;
    const fs = o.labelSize + 'px';
    // how many picks (★) each column / row value got, over every page: shows at a glance which CFG / seed / word wins
    const pc = {x: new Map(), y: new Map()};
    if (G.picks.size) for (const it of G.d.images) if (G.picks.has(it.path)) {
      if (G.x) { const k = nkey(it.p[G.x]); pc.x.set(k, (pc.x.get(k) || 0) + 1); }
      if (G.y) { const k = nkey(it.p[G.y]); pc.y.set(k, (pc.y.get(k) || 0) + 1); }
    }
    const star = (ax, v) => { const n = pc[ax].get(v); return n ? h('span', {class: 'hstar', text: ' ★' + n, title: `挑選了 ${n} 張`}) : null; };
    if (G.x) xs.forEach((v, i) => G.topIn.append(h('div', {class: 'chead', title: `${v}\n點一下：只看這一欄　右鍵：隱藏、排序`, style: {left: i * st + 'px', width: o.cell + 'px', fontSize: fs},
      onclick: () => G.solo('x', v), oncontextmenu: e => { e.preventDefault(); G.headMenu(e, 'x', v); }}, short(v, Math.max(6, Math.floor(o.cell / (o.labelSize * 0.62)))), star('x', v))));
    if (G.y) ys.forEach((v, i) => G.leftIn.append(h('div', {class: 'rhead', title: `${v}\n點一下：只看這一列　右鍵：隱藏、排序`, style: {top: i * st + 'px', height: o.cell + 'px', fontSize: fs},
      onclick: () => G.solo('y', v), oncontextmenu: e => { e.preventDefault(); G.headMenu(e, 'y', v); }}, short(v, 120), star('y', v))));
  };
  G.headMenu = function (e, ax, v) {
    const k = G[ax], vals = G.t[ax === 'x' ? 'xs' : 'ys'];
    const setOrder = arr => { G.order[k] = arr; G.layout(); savePrefs(); };
    HZ.menu(e.clientX, e.clientY, [
      {icon: '👁', text: '只看這一' + (ax === 'x' ? '欄' : '列'), run: () => G.solo(ax, v)},
      {icon: '🙈', text: '隱藏這一' + (ax === 'x' ? '欄' : '列'), run: () => { (ax === 'x' ? G.hiddenX : G.hiddenY).add(v); G.layout(); savePrefs(); G.renderCtl(); }},
      '-',
      {icon: '⤒', text: '移到最前面', run: () => setOrder([v, ...vals.filter(x => x !== v)])},
      {icon: '←', text: '往前移一格', run: () => { const a = vals.slice(), i = a.indexOf(v); if (i > 0) { [a[i - 1], a[i]] = [a[i], a[i - 1]]; setOrder(a); } }},
      {icon: '→', text: '往後移一格', run: () => { const a = vals.slice(), i = a.indexOf(v); if (i >= 0 && i < a.length - 1) { [a[i + 1], a[i]] = [a[i], a[i + 1]]; setOrder(a); } }},
      {icon: '⤓', text: '移到最後面', run: () => setOrder([...vals.filter(x => x !== v), v])},
      G.order[k] ? {icon: '↺', text: '恢復原本的排序', run: () => { delete G.order[k]; G.layout(); savePrefs(); }} : null,
      '-',
      {icon: '📋', text: '複製這個值', run: () => HZ.copyText(String(v))},
    ]);
  };
  G.solo = function (ax, v) {
    const k = G[ax]; const all = G.axisVals(k, G.base(), ax === 'x' ? 'sortX' : 'sortY');
    const set = ax === 'x' ? G.hiddenX : G.hiddenY;
    if (set.size === all.length - 1 && !set.has(v)) set.clear(); else { set.clear(); for (const a of all) if (a !== v) set.add(a); }
    G.layout(); savePrefs(); G.renderCtl();
  };
  G.thumbSize = () => { const px = G.o.cell * (devicePixelRatio || 1); return px <= 140 ? 128 : px <= 270 ? 256 : px <= 520 ? 512 : 0; };
  /* 同步放大鏡: hold Z over any cell -> every visible cell zooms into the same spot (full-resolution image) */
  G.loupe = {on: false, u: 0.5, v: 0.5, k: 3};
  G.applyLoupe = function () {
    const L = G.loupe;
    G.body.classList.toggle('cloupe', L.on);
    for (const img of G.space.querySelectorAll('.ccell img')) {
      if (L.on) {
        if (!img.dataset.full) { img.dataset.thumb = img.src; img.dataset.full = '1'; img.src = HZ.fileUrl(img.dataset.p); }
        img.style.transformOrigin = `${L.u * 100}% ${L.v * 100}%`; img.style.transform = `scale(${L.k})`;
      } else {
        img.style.transform = ''; img.style.transformOrigin = '';
        if (img.dataset.full) { img.src = img.dataset.thumb; delete img.dataset.full; }
      }
    }
    if (G.info && L.on) G.info.dataset.loupe = `放大鏡 ${L.k}×（滾輪調整倍率，放開 Z 結束）`;
  };
  document.addEventListener('keydown', e => {
    if (HZ.cur !== 'comfy' || e.repeat || e.key.toLowerCase() !== 'z' || e.ctrlKey || e.metaKey || /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName) || document.querySelector('.cview,#overlay.on')) return;
    G.loupe.on = true; G.applyLoupe(); HZ.toast(`同步放大鏡 ${G.loupe.k}×：移動滑鼠看同一個位置，滾輪調倍率`);
  });
  document.addEventListener('keyup', e => { if (e.key.toLowerCase() === 'z' && G.loupe.on) { G.loupe.on = false; G.applyLoupe(); } });
  window.addEventListener('blur', () => { if (G.loupe.on) { G.loupe.on = false; G.applyLoupe(); } });
  G.src = it => { const s = G.thumbSize(); return s ? '/api/thumb?' + new URLSearchParams({path: it.path, s}) : HZ.fileUrl(it.path); };
  G.paint = function (force) {
    if (!G.t) return;
    const {xs, ys, cells} = G.t, o = G.o, st = G.step();
    const W = G.body.clientWidth, Hh = G.body.clientHeight, sl = G.body.scrollLeft, stp = G.body.scrollTop;
    const ov = Math.max(0, -o.gap);
    const c0 = Math.max(0, Math.floor((sl - ov) / st) - 1), c1 = Math.min(xs.length, Math.ceil((sl + W + ov) / st) + 1);
    const r0 = Math.max(0, Math.floor((stp - ov) / st) - 1), r1 = Math.min(ys.length, Math.ceil((stp + Hh + ov) / st) + 1);
    const key = [c0, c1, r0, r1].join(',');
    if (!force && key === G._k) return; G._k = key;
    const f = o.feather;
    const mask = f ? `linear-gradient(to right, transparent, #000 ${f}%, #000 ${100 - f}%, transparent), linear-gradient(to bottom, transparent, #000 ${f}%, #000 ${100 - f}%, transparent)` : '';
    const frag = document.createDocumentFragment();
    for (let r = r0; r < r1; r++) for (let c = c0; c < c1; c++) {
      const list = cells.get(c + '|' + r); if (!list) continue;
      const it = list[0];
      const fr = G.fresh.get(it.path), isNew = fr && Date.now() - fr < 20000;
      const cell = h('div', {class: 'ccell' + (G.picks.has(it.path) ? ' pick' : '') + (isNew ? ' cnew' : ''), 'data-c': c, 'data-r': r,
        style: {left: c * st + 'px', top: r * st + 'px', width: o.cell + 'px', height: o.cell + 'px', borderRadius: o.round + 'px',
          outline: o.lines ? `1px solid ${o.lineColor}` : '', zIndex: G._hover === it.path ? 5 : ''}});
      const mk = (x, extra) => {
        const img = h('img', {loading: 'lazy', decoding: 'async', src: G.loupe.on ? HZ.fileUrl(x.path) : G.src(x), 'data-p': x.path, draggable: 'false', style: Object.assign({objectFit: o.fit, borderRadius: o.round + 'px'}, extra || {})});
        if (G.loupe.on) { img.style.transformOrigin = `${G.loupe.u * 100}% ${G.loupe.v * 100}%`; img.style.transform = `scale(${G.loupe.k})`; }
        if (mask) { img.style.webkitMaskImage = mask; img.style.maskImage = mask; img.style.webkitMaskComposite = 'source-in'; img.style.maskComposite = 'intersect'; }
        return img;
      };
      if (o.multi === 'mosaic' && list.length > 1) {
        const n = Math.min(list.length, 16), cols = Math.ceil(Math.sqrt(n)), rows = Math.ceil(n / cols), w = 100 / cols, hh = 100 / rows;
        list.slice(0, n).forEach((x, j) => cell.append(mk(x, {position: 'absolute', left: (j % cols) * w + '%', top: Math.floor(j / cols) * hh + '%', width: w + '%', height: hh + '%'})));
      } else cell.append(mk(it));
      if (o.cellLabel) cell.append(h('span', {class: 'clabel', text: short(nkey(it.p[o.cellLabel]), 60)}));
      if (list.length > 1) cell.append(h('span', {class: 'cmulti', text: '×' + list.length}));
      cell.append(h('span', {class: 'cstar', text: G.picks.has(it.path) ? '★' : '☆', onclick: e => { e.stopPropagation(); G.togglePick(it); }}));
      cell.onclick = () => G.view(c, r, 0);
      cell.onmouseenter = e => { G._hover = it.path; HZ.tip(e, G.tipHtml(it, list.length)); };
      cell.onmousemove = e => {
        const r = cell.getBoundingClientRect(); G.loupe.u = (e.clientX - r.left) / r.width; G.loupe.v = (e.clientY - r.top) / r.height;
        if (G.loupe.on) { HZ.tip(null); G.applyLoupe(); } else HZ.tip(e, G.tipHtml(it, list.length));
      };
      cell.onmouseleave = () => { G._hover = null; HZ.tip(null); };
      cell.oncontextmenu = e => { e.preventDefault(); HZ.tip(null); HZ.menu(e.clientX, e.clientY, G.cellMenu(it)); };
      frag.append(cell);
    }
    G.space.innerHTML = ''; G.space.append(frag);
  };
  G.tipHtml = function (it, n) {
    const p = it.p, rows = [];
    for (const k of [G.x, G.y, G.z].filter(Boolean)) { const pp = G.d.params.find(x => x.key === k); rows.push(`<b>${esc(pp ? pp.label : k)}</b>：${esc(short(nkey(p[k]), 80))}`); }
    rows.push(`<span class="muted">seed ${esc(p.seed ?? '—')}　cfg ${esc(p.cfg ?? '—')}　steps ${esc(p.steps ?? '—')}　${esc(p.sampler || '')}</span>`);
    rows.push(`<span class="muted small">${esc(it.name)}${n > 1 ? `　（這格有 ${n} 張）` : ''}</span>`);
    return rows.join('<br>');
  };
  G.cellMenu = function (it) {
    const item = {path: it.path, name: it.name, dir: false, ext: 'png'};
    return [{icon: '🔍', text: '放大檢視', run: () => { const [c, r] = G.posOf(it); G.view(c, r, 0); }},
      {icon: G.picks.has(it.path) ? '☆' : '★', text: G.picks.has(it.path) ? '取消挑選' : '挑選', key: 'P', run: () => G.togglePick(it)},
      {icon: '📋', text: '複製正向提示詞', run: () => HZ.copyText(it.p.positive || '')},
      {icon: '🌱', text: '複製 seed', run: () => HZ.copyText(String(it.p.seed ?? ''))},
      {icon: '🎯', text: '只看同一個 seed', run: () => { if (it.p.seed !== undefined) { G.filters.seed = new Set([nkey(it.p.seed)]); G.layout(); savePrefs(); G.renderCtl(); } }},
      '-', ...HZ.itemMenu([item], {})];
  };
  G.posOf = function (it) { for (const [k, l] of G.t.cells) if (l.includes(it)) return k.split('|').map(Number); return [0, 0]; };
  G.togglePick = function (it) {
    if (G.picks.has(it.path)) G.picks.delete(it.path); else G.picks.add(it.path);
    savePrefs(); G.paint(true); G.renderCtl(); G.headers();
  };
  G.copyPicks = function () {
    if (!G.picks.size) { HZ.toast('還沒有挑選任何圖片（游標移到圖上按 P，或點右上角 ☆）'); return; }
    HZ.pickTarget('copy', [...G.picks].map(p => ({path: p, name: HZ.base(p)})));
  };

  /* ------------------------------------------------------------------ viewer */
  G.view = function (c, r, k) {
    const {xs, ys, cells} = G.t;
    const ov = document.createElement('div'); ov.className = 'cview';
    const img = h('img'), side = h('div', {class: 'cside'}), title = h('div', {class: 'ctitle'});
    const imgA = h('img', {class: 'cmpA'}), bar = h('div', {class: 'cmpBar'}), stage = h('div', {class: 'cstage'}, img, imgA, bar, title);
    ov.append(stage, side);
    let split = 50, cmpOn = false;
    const setSplit = x => { const r = stage.getBoundingClientRect(); split = Math.max(0, Math.min(100, (x - r.left) / r.width * 100)); imgA.style.clipPath = `inset(0 ${100 - split}% 0 0)`; bar.style.left = split + '%'; };
    stage.addEventListener('mousemove', e => { if (cmpOn && e.buttons === 1) setSplit(e.clientX); });
    stage.addEventListener('mousedown', e => { if (cmpOn) setSplit(e.clientX); });
    document.body.append(ov);
    const show = () => {
      const list = cells.get(c + '|' + r); if (!list) return;
      k = (k + list.length) % list.length;
      const it = list[k]; img.src = HZ.fileUrl(it.path);
      const LB = {seed: 'Seed', steps: 'Steps', cfg: 'CFG', sampler: '取樣器', scheduler: '排程', denoise: 'Denoise', model: '模型', loras: 'LoRA', width: '寬', height: '高'};
      const pp = key => (G.d.params.find(x => x.key === key) || {label: LB[key] || key}).label;
      title.innerHTML = `${G.x ? `<b>${esc(pp(G.x))}</b> ${esc(short(nkey(it.p[G.x]), 60))}　` : ''}${G.y ? `<b>${esc(pp(G.y))}</b> ${esc(short(nkey(it.p[G.y]), 60))}` : ''}${list.length > 1 ? `　（${k + 1}/${list.length}，Tab 切換）` : ''}`;
      const common = (G.d.common_prompt || '').split(', ').filter(Boolean);
      const pos = (it.p.positive || '').split(/,\s*/).map(w => common.includes(w.trim()) ? esc(w) : `<mark>${esc(w)}</mark>`).join(', ');
      side.innerHTML = `<div class="row"><b class="ell">${esc(it.name)}</b><span class="grow"></span><button class="sm" data-a="pick">${G.picks.has(it.path) ? '★ 已挑選' : '☆ 挑選'}</button><button class="sm" data-a="close">✕</button></div>
        <div class="kv small" style="margin-top:8px">${['seed', 'steps', 'cfg', 'sampler', 'scheduler', 'denoise', 'model', 'loras', 'width', 'height'].filter(x => it.p[x] !== undefined).map(x => `<b>${esc(pp(x))}</b><span>${esc(it.p[x])}</span>`).join('')}</div>
        <h3>正向提示詞 <button class="sm" data-a="cp">複製</button></h3><div class="small ptext">${pos || '<span class="muted">（沒有）</span>'}</div>
        <h3>反向提示詞</h3><div class="small ptext muted">${esc(it.p.negative || '（沒有）')}</div>
        <div class="row wrap" style="margin-top:10px"><button class="sm" data-a="reveal">在總管顯示</button><button class="sm" data-a="dl">下載原圖</button><button class="sm" data-a="wf" title="貼到 ComfyUI 就能載入同一個工作流">複製工作流</button><button class="sm" data-a="cimg">複製圖片</button></div>
        <div class="row wrap" style="margin-top:6px"><button class="sm" data-a="setA">設為比較 A</button>${G.cmpA && G.cmpA !== it ? '<button class="sm" data-a="cmp">' + (cmpOn ? '關閉比較' : '和 A 比較（拖曳分隔線）') + '</button>' : ''}</div>
        <div class="small muted" style="margin-top:10px">← → ↑ ↓ 在表格裡移動　P 挑選　A 設為比較基準　C 開關比較　Esc 關閉</div>`;
      side.querySelector('[data-a=wf]').onclick = async () => {
        try { const m = await HZ.get('/api/comfy/meta', {path: it.path}); const t = m.texts.workflow || m.texts.prompt || m.texts.parameters; if (!t) { HZ.toast('這張圖沒有工作流資料'); return; } HZ.copyText(t); }
        catch (e) { HZ.err(e); }
      };
      side.querySelector('[data-a=cimg]').onclick = () => HZ.copyImage(it.path);
      side.querySelector('[data-a=setA]').onclick = () => { G.cmpA = it; HZ.toast('已設為比較 A，切到別張圖後按「和 A 比較」或 C'); show(); };
      const cb = side.querySelector('[data-a=cmp]'); if (cb) cb.onclick = () => { cmpOn = !cmpOn; show(); };
      if (cmpOn && G.cmpA && G.cmpA !== it) { imgA.src = HZ.fileUrl(G.cmpA.path); imgA.style.display = ''; bar.style.display = ''; setSplit(stage.getBoundingClientRect().left + stage.getBoundingClientRect().width * split / 100); title.innerHTML += '　<span class="pill acc">左：A　右：目前</span>'; }
      else { imgA.style.display = 'none'; bar.style.display = 'none'; }
      side.querySelector('[data-a=close]').onclick = close;
      side.querySelector('[data-a=pick]').onclick = () => { G.togglePick(it); show(); };
      side.querySelector('[data-a=cp]').onclick = () => HZ.copyText(it.p.positive || '');
      side.querySelector('[data-a=reveal]').onclick = () => { close(); HZ.go('explorer'); HZ.pages.explorer.open(HZ.dir(it.path), it.name); };
      side.querySelector('[data-a=dl]').onclick = () => HZ.download([{path: it.path, name: it.name}]);
      G._viewIt = it;
    };
    const move = (dc, dr) => {
      for (let i = 1; i < Math.max(xs.length, ys.length) + 1; i++) {
        const nc = c + dc * i, nr = r + dr * i;
        if (nc < 0 || nr < 0 || nc >= xs.length || nr >= ys.length) return;
        if (cells.has(nc + '|' + nr)) { c = nc; r = nr; k = 0; show(); return; }
      }
    };
    const key = e => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;                       // Ctrl+C / Ctrl+A stay copy / select
      if (e.key === 'Escape') close();
      else if (e.key === 'ArrowRight') move(1, 0); else if (e.key === 'ArrowLeft') move(-1, 0);
      else if (e.key === 'ArrowDown') move(0, 1); else if (e.key === 'ArrowUp') move(0, -1);
      else if (e.key === 'Tab') { e.preventDefault(); k += e.shiftKey ? -1 : 1; show(); }
      else if (e.key.toLowerCase() === 'p') { G.togglePick(G._viewIt); show(); }
      else if (e.key.toLowerCase() === 'a') { G.cmpA = G._viewIt; HZ.toast('已設為比較 A'); show(); }
      else if (e.key.toLowerCase() === 'c') { if (G.cmpA) { cmpOn = !cmpOn; show(); } }
      else return;
      e.preventDefault(); e.stopPropagation();
    };
    function close() { document.removeEventListener('keydown', key, true); ov.remove(); }
    ov.addEventListener('click', e => { if (e.target === ov) close(); });
    document.addEventListener('keydown', key, true);
    show();
  };

  /* ------------------------------------------------------------------ export */
  G.exportPng = async function () {
    if (!G.t) return;
    const {xs, ys, cells} = G.t, o = G.o;
    const inp = h('input', {type: 'number', value: Math.min(o.cell, 256), min: 16, max: 1024, style: {width: '80px'}});
    const r = await HZ.dialog({title: '匯出成一張圖', body: h('div', {class: 'col'}, h('div', {text: `${xs.length} 欄 × ${ys.length} 列，用目前的間距、漸層、格線與標籤。`}),
      h('label', {class: 'row'}, '每格', inp, 'px'), h('div', {class: 'small muted', text: '整張圖最大 16000 px，超過會自動縮小。'})), buttons: [{text: '取消', value: null}, {text: '匯出', primary: true, value: () => +inp.value}]});
    if (!r) return;
    let cell = r; const scaleGap = cell / o.cell; let gap = Math.round(o.gap * scaleGap);
    const lw = o.labels && G.y ? Math.round(G.lw * Math.max(1, scaleGap)) : 0, lh = o.labels && G.x ? Math.round(G.lh * Math.max(1, scaleGap)) : 0;
    let W = lw + xs.length * (cell + gap) - gap, H = lh + ys.length * (cell + gap) - gap;
    const k = Math.min(1, 16000 / Math.max(W, H)); if (k < 1) { cell = Math.floor(cell * k); gap = Math.round(gap * k); W = lw + xs.length * (cell + gap) - gap; H = lh + ys.length * (cell + gap) - gap; }
    const cv = document.createElement('canvas'); cv.width = W; cv.height = H; const g = cv.getContext('2d');
    g.fillStyle = o.bg; g.fillRect(0, 0, W, H);
    const fs = Math.max(10, Math.round(o.labelSize * Math.max(1, cell / o.cell)));
    g.fillStyle = '#e8ecf2'; g.font = `${fs}px "Yu Gothic UI","Microsoft JhengHei",sans-serif`; g.textBaseline = 'middle';
    if (lh) xs.forEach((v, i) => { g.save(); g.beginPath(); g.rect(lw + i * (cell + gap), 0, cell, lh); g.clip(); g.textAlign = 'center'; g.fillText(short(v, 60), lw + i * (cell + gap) + cell / 2, lh / 2); g.restore(); });
    if (lw) ys.forEach((v, i) => { g.save(); g.beginPath(); g.rect(0, lh + i * (cell + gap), lw - 4, cell); g.clip(); g.textAlign = 'left'; g.fillText(short(v, 80), 4, lh + i * (cell + gap) + cell / 2); g.restore(); });
    const ts = cell <= 128 ? 128 : cell <= 256 ? 256 : 512;
    const t = h('div', {class: 'toast'}); document.getElementById('toasts').append(t);
    const jobs = []; for (const [kk, list] of cells) { const [c, rr] = kk.split('|').map(Number); jobs.push([c, rr, list[0]]); }
    let done = 0;
    const draw = ([c, rr, it]) => new Promise(res => {
      const im = new Image(); im.onload = () => {
        const x = lw + c * (cell + gap), y = lh + rr * (cell + gap);
        let sw = im.width, sh = im.height, sx = 0, sy = 0, dw = cell, dh = cell, dx = x, dy = y;
        if (o.fit === 'cover') { const s = Math.max(cell / sw, cell / sh); const cw = cell / s, ch = cell / s; sx = (sw - cw) / 2; sy = (sh - ch) / 2; sw = cw; sh = ch; }
        else { const s = Math.min(cell / sw, cell / sh); dw = sw * s; dh = sh * s; dx = x + (cell - dw) / 2; dy = y + (cell - dh) / 2; }
        if (o.feather) {
          const tmp = document.createElement('canvas'); tmp.width = cell; tmp.height = cell; const tg = tmp.getContext('2d');
          tg.drawImage(im, sx, sy, sw, sh, dx - x, dy - y, dw, dh); tg.globalCompositeOperation = 'destination-in';
          const f = o.feather / 100;
          let gr = tg.createLinearGradient(0, 0, cell, 0); gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(f, '#000'); gr.addColorStop(1 - f, '#000'); gr.addColorStop(1, 'rgba(0,0,0,0)'); tg.fillStyle = gr; tg.fillRect(0, 0, cell, cell);
          gr = tg.createLinearGradient(0, 0, 0, cell); gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(f, '#000'); gr.addColorStop(1 - f, '#000'); gr.addColorStop(1, 'rgba(0,0,0,0)'); tg.fillStyle = gr; tg.fillRect(0, 0, cell, cell);
          g.drawImage(tmp, x, y);
        } else g.drawImage(im, sx, sy, sw, sh, dx, dy, dw, dh);
        if (o.lines) { g.strokeStyle = o.lineColor; g.lineWidth = 1; g.strokeRect(x + .5, y + .5, cell - 1, cell - 1); }
        res();
      };
      im.onerror = res; im.src = '/api/thumb?' + new URLSearchParams({path: it.path, s: ts});
    }).then(() => { done++; if (done % 20 === 0) t.textContent = `匯出中… ${done}/${jobs.length}`; });
    for (let i = 0; i < jobs.length; i += 8) await Promise.all(jobs.slice(i, i + 8).map(draw));
    t.remove();
    cv.toBlob(b => { const a = h('a', {href: URL.createObjectURL(b), download: `比較表_${HZ.base(G.path)}_${xs.length}x${ys.length}.png`}); document.body.append(a); a.click(); a.remove(); HZ.toast(`已匯出 ${W}×${H} px`, 'ok'); }, 'image/png');
  };

  G.help = function () {
    const rows = [['滑鼠滾輪', '上下捲動；Shift＋滾輪左右捲動'], ['Ctrl＋滾輪', '放大縮小格子（以游標為中心）'], ['按住 Z', '同步放大鏡：每一格放大到同一個位置；按住時滾輪調倍率'],
      ['中鍵拖曳／空白鍵＋拖曳', '平移整張表格'], ['P', '挑選／取消挑選游標下的圖（右上角 ☆ 也可以）'], ['PageUp／PageDown', '切換分頁軸的上一頁／下一頁'],
      ['點欄／列標題', '只看那一欄／列'], ['右鍵欄／列標題', '隱藏、往前往後移、移到最前最後、複製值'], ['點一格', '放大檢視'],
      ['檢視中 ← → ↑ ↓', '在表格裡移動'], ['檢視中 A', '設為比較基準'], ['檢視中 C', '和 A 左右分割比較（拖曳黃線）'], ['檢視中 P', '挑選'], ['?', '顯示這個說明']];
    HZ.dialog({title: '⌨ 生圖比較的快捷鍵', width: 560, body: h('table', {class: 't'}, ...rows.map(([k, v]) => h('tr', {}, h('td', {style: {whiteSpace: 'nowrap'}}, h('b', {text: k})), h('td', {text: v}))))});
  };
  G.onShow = function () {
    G.fillRecent();
    if (!G.d) { let rec = []; try { rec = JSON.parse(localStorage.getItem(LS + 'recent') || '[]'); } catch (e) { } if (rec[0]) G.open(rec[0]); }
    else G.paint(true);
  };
  document.addEventListener('keydown', e => {
    if (HZ.cur !== 'comfy' || document.querySelector('#overlay.on,.cview') || /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) return;
    if (e.key === '?' || (e.key === '/' && e.shiftKey)) { G.help(); e.preventDefault(); return; }
    if (e.key.toLowerCase() === 'p' && G._hover) { const it = G.d.images.find(x => x.path === G._hover); if (it) G.togglePick(it); }
    else if ((e.key === 'PageDown' || e.key === 'PageUp') && G.z) {                // wraps around, like the ◀ ▶ buttons
      const nv = G.axisVals(G.z, G.base(), 'sortX').length || 1;
      G.zi = (G.zi + (e.key === 'PageDown' ? 1 : -1) + nv) % nv; G.layout(); G.renderCtl(); e.preventDefault();
    }
  });
  HZ.page('comfy', G);
})();

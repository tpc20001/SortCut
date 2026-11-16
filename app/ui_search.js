/* HotZone FM — 搜尋 (Everything style: whole-drive index, results while typing) */
'use strict';
(function () {
  const {h, esc} = HZ;
  const ROW = 26;
  const S = {title: '搜尋', items: [], total: 0, sel: new Set(), focus: -1, anchor: -1, sort: 'name', desc: false, scope: '', type: '', seq: 0, limit: 1000};
  const TYPES = [['', '全部'], ['folder:', '資料夾'], ['file:', '檔案'], ['video:', '影片'], ['audio:', '音樂'], ['pic:', '圖片'], ['doc:', '文件'], ['zip:', '壓縮檔'], ['hot:', '🔥 熱資料夾內']];

  S.build = function (root) {
    S.q = h('input', {class: 'q', placeholder: '搜尋整顆硬碟…　例：報告 ext:pdf　*.mp4 size:>1gb　dm:thisweek', autocomplete: 'off', spellcheck: 'false', list: 'hzq-hist'});
    S.hist = h('datalist', {id: 'hzq-hist'});
    S.loadHist = () => { let a = []; try { a = JSON.parse(localStorage.getItem('hz.search.hist') || '[]'); } catch (e) { } S.hist.innerHTML = ''; for (const x of a) S.hist.append(h('option', {value: x})); return a; };
    S.saveHist = q => { if (!q || q.length < 2) return; let a = S.loadHist().filter(x => x !== q); a.unshift(q); a = a.slice(0, 25); try { localStorage.setItem('hz.search.hist', JSON.stringify(a)); } catch (e) { } S.loadHist(); };
    S.loadHist();
    S.q.oninput = HZ.debounce(() => S.search(), 120);
    S.q.onkeydown = e => {
      if (e.key === 'ArrowDown') { e.preventDefault(); S.list.focus(); S.select(Math.max(0, S.focus), false); }
      if (e.key === 'Enter') { e.preventDefault(); S.search(); S.saveHist(S.q.value.trim()); }
    };
    S.scopeEl = h('select', {title: '搜尋範圍', onchange: () => { S.scope = S.scopeEl.value; S.search(); }});
    S.sortEl = h('select', {onchange: () => { S.sort = S.sortEl.value; S.renderHead(); S.search(); }},
      ...[['name', '名稱'], ['path', '路徑'], ['size', '大小'], ['mtime', '修改日期'], ['ext', '副檔名']].map(([v, t]) => h('option', {value: v, text: '排序：' + t})));
    S.descEl = h('button', {class: 'ghost', title: '反向排序', onclick: () => { S.desc = !S.desc; S.descEl.textContent = S.desc ? '▼' : '▲'; S.renderHead(); S.search(); }}, '▲');
    S.chips = h('div', {class: 'chips'});
    for (const [v, t] of TYPES) S.chips.append(h('span', {class: 'chip' + (v === '' ? ' on' : ''), 'data-v': v, text: t, onclick: () => {
      S.type = v; for (const c of S.chips.children) c.classList.toggle('on', c.dataset.v === v); S.search();
    }}));
    const help = h('button', {class: 'ghost', title: '搜尋語法', onclick: S.help}, '？');
    S.info = h('div', {class: 'sinfo'});
    S.head = h('div', {class: 'lhead'});
    S.list = h('div', {class: 'list', tabindex: '0'});
    S.spacer = h('div', {class: 'spacer'}); S.list.append(S.spacer);
    S.list.addEventListener('scroll', () => S.renderRows());
    S.list.addEventListener('keydown', S.key);
    new ResizeObserver(() => S.renderRows()).observe(S.list);
    root.append(S.hist, h('div', {class: 'sbox'}, S.q, S.scopeEl, S.sortEl, S.descEl, help), h('div', {class: 'sbox', style: {paddingTop: '0'}}, S.chips), S.info, S.head, S.list);
    S.renderHead(); S.fillScopes();
  };
  S.fillScopes = function () {
    const cur = S.scope;
    S.scopeEl.innerHTML = '';
    S.scopeEl.append(h('option', {value: '', text: '全部已索引的磁碟'}));
    for (const v of HZ.vols || []) if (v.ok && v.type !== 'remote') { const r = /^[A-Z]:$/.test(v.letter) ? v.letter + '\\' : v.letter; S.scopeEl.append(h('option', {value: r, text: v.letter + ' ' + (v.label || '')})); }
    for (const f of HZ.hotFolders || []) S.scopeEl.append(h('option', {value: f.path, text: '🔥 ' + f.path}));
    if (cur && ![...S.scopeEl.options].some(o => o.value === cur)) S.scopeEl.append(h('option', {value: cur, text: '📂 ' + cur}));
    S.scopeEl.value = cur;
  };
  S.setScope = function (p) { S.scope = p || ''; S.fillScopes(); S.q.focus(); S.search(); };
  S.run = function (q, scope) { S.q.value = q; S.setScope(scope || ''); };
  S.renderHead = function () {
    const cols = innerWidth < 820 ? 'minmax(0,1fr) 90px' : 'minmax(200px,1.1fr) minmax(200px,1.4fr) 110px 142px';
    S.head.style.setProperty('--cols', cols); S.list.style.setProperty('--cols', cols);
    S.head.innerHTML = '';
    for (const [k, t, cls] of [['name', '名稱', ''], ['path', '所在資料夾', 'c-type'], ['size', '大小', ''], ['mtime', '修改日期', 'c-date']]) {
      const c = h('div', {class: cls + (S.sort === k ? ' sorted' : ''), text: t + (S.sort === k ? (S.desc ? ' ▼' : ' ▲') : '')});
      if (k === 'size') c.style.textAlign = 'right';
      c.onclick = () => { S.desc = S.sort === k ? !S.desc : (k === 'size' || k === 'mtime'); S.sort = k; S.sortEl.value = k; S.descEl.textContent = S.desc ? '▼' : '▲'; S.renderHead(); S.search(); };
      S.head.append(c);
    }
  };
  S.search = async function (more) {
    const q = (S.q.value.trim() + ' ' + S.type).trim();
    const seq = ++S.seq;
    if (!q) { S.items = []; S.total = 0; S.sel.clear(); S.focus = -1; S.anchor = -1; S._key = ''; S.renderRows(true); S.info.innerHTML = S.idxText(); return; }
    const key = JSON.stringify([q, S.scope, S.sort, S.desc]);
    const same = key === S._key && S.items.length;                  // the same search again (show more / refresh)
    if (S._ac) S._ac.abort();                                        // typing fast: drop the older request
    const ac = S._ac = new AbortController();
    try {
      const r = await HZ.get('/api/search', {q, scope: S.scope, sort: S.sort, desc: S.desc ? '1' : '0', limit: more ? Math.min(5000, S.items.length + 2000) : Math.max(S.limit, same ? Math.min(5000, S.items.length) : 0)}, {signal: ac.signal});
      if (seq !== S.seq) return;
      // the selection is kept by PATH: rows move when the list reloads (a new file shifted it onto another file)
      const selPaths = same ? new Set(S.selected().map(x => x.path)) : null;
      const focusPath = same && S.items[S.focus] ? S.items[S.focus].path : null, anchorPath = same && S.items[S.anchor] ? S.items[S.anchor].path : null;
      S.items = r.items || []; S.total = r.total || 0; S._key = key;
      clearTimeout(S._ht); S._ht = setTimeout(() => { if (S.total) S.saveHist(S.q.value.trim()); }, 2500);   // a search you stayed on
      S.sel = new Set(); S.focus = -1; S.anchor = -1;
      if (same) {
        S.items.forEach((x, i) => { if (selPaths.has(x.path)) S.sel.add(i); if (x.path === focusPath) S.focus = i; if (x.path === anchorPath) S.anchor = i; });
      } else S.list.scrollTop = 0;
      S.renderRows(true);
      const cap = S.items.length >= 5000 && S.total > S.items.length;
      S.info.innerHTML = r.error ? `<span class="bad">${esc(r.error)}</span>` :
        `<span><b>${S.total.toLocaleString()}</b> 個結果</span><span>${r.ms} ms</span>` + (S.total > S.items.length ? `<span>顯示前 ${S.items.length.toLocaleString()} 個　` +
          (cap ? '<span class="muted">（最多列出 5,000 個，請加條件縮小範圍）</span>' : `<a href="javascript:void 0" onclick="HZ.pages.search.search(true)">顯示更多</a>`) + '</span>' : '') +
        `<span class="grow"></span>` + (r.ready ? `<span class="warn">索引尚未完成：${esc(r.ready)}</span>` : S.idxText());
    } catch (e) { if (e.name !== 'AbortError' && seq === S.seq) S.info.innerHTML = `<span class="bad">${esc(e.message)}</span>`; }
  };
  S.idxText = function () {
    const ix = (HZ.st && HZ.st.index) || [];
    if (!ix.length) return '<span class="muted">沒有已索引的磁碟（設定 → 索引）</span>';
    const age = v => { const m = Math.round((Date.now() / 1000 - (v.built || 0)) / 60); return m < 2 ? '剛掃描' : m < 90 ? `${m} 分鐘前掃描` : `${Math.round(m / 60)} 小時前掃描`; };
    return ix.map(v => `<span title="${esc(v.root)}${v.live ? '' : '\n這顆磁碟是定期掃描：在 HotZone FM 裡做的變更會立刻更新，其他程式的變更要等下次掃描（刪除、改名前會再確認是同一個檔案）'}">${esc(v.key)} ${v.state === 'ready' ? (v.live ? '⚡ 即時' : '✓ ' + age(v)) : v.state === 'building' ? `建立中 ${v.progress ? Math.round(v.progress * 100) + '%' : esc(v.msg || '')}` : esc(v.state)} <span class="muted">${(v.files || 0).toLocaleString()} 檔</span></span>`).join('');
  };
  S.renderRows = function (force) {
    const n = S.items.length, Hh = S.list.clientHeight || 600;
    S.spacer.style.height = Math.max(n * ROW, 1) + 'px';
    const a = Math.max(0, Math.floor(S.list.scrollTop / ROW) - 10), b = Math.min(n, Math.ceil((S.list.scrollTop + Hh) / ROW) + 10);
    if (!force && S._r && S._r[0] === a && S._r[1] === b) return;
    S._r = [a, b];
    const frag = document.createDocumentFragment(), narrow = innerWidth < 820;   // phone: the folder goes after the name
    const q = S.q.value.trim().toLowerCase().split(/\s+/).filter(w => w && !w.includes(':') && !/[*?!|"\\/]/.test(w));
    for (let i = a; i < b; i++) {
      const it = S.items[i]; it.ext = it.dir ? '' : (it.name.includes('.') ? it.name.split('.').pop().toLowerCase() : '');
      let nm = esc(it.name);
      for (const w of q) { const k = it.name.toLowerCase().indexOf(w); if (k >= 0) { nm = esc(it.name.slice(0, k)) + '<b style="color:var(--accent)">' + esc(it.name.slice(k, k + w.length)) + '</b>' + esc(it.name.slice(k + w.length)); break; } }
      const row = h('div', {class: 'it' + (S.sel.has(i) ? ' sel' : '') + (i === S.focus ? ' focus' : ''), style: {top: i * ROW + 'px'}, 'data-i': i, draggable: 'true',
        html: `<div class="nm${it.hidden ? ' hidden' : ''}">${HZ.icon(it)}<span>${nm}${narrow ? `<span class="small muted">　${esc(HZ.dir(it.path))}</span>` : ''}</span></div><div class="c-type muted" title="${esc(HZ.dir(it.path))}">${esc(HZ.dir(it.path))}</div>
          <div class="sz">${it.size >= 0 ? HZ.fmtSize(it.size) : ''}</div><div class="c-date muted">${HZ.fmtDate(it.mtime)}</div>`});
      row.onmousedown = e => S.click(e, i);
      row.ondblclick = () => HZ.openItem(it);
      row.oncontextmenu = e => { e.preventDefault(); if (!S.sel.has(i)) S.select(i, false); HZ.menu(e.clientX, e.clientY, HZ.itemMenu(S.selected(), {})); };
      row.ondragstart = e => {
        if (!S.sel.has(i)) S.select(i, false);
        const paths = S.selected().map(x => x.path);
        if (HZ.bridge) { e.preventDefault(); HZ.bridge.startDrag(JSON.stringify(paths)); return; }
        e.dataTransfer.setData('application/x-hz-paths', JSON.stringify(paths)); e.dataTransfer.effectAllowed = 'copyMove';
      };
      frag.append(row);
    }
    S.spacer.innerHTML = ''; S.spacer.append(frag);
    if (!n && S.q.value.trim()) S.spacer.append(h('div', {class: 'empty', text: '沒有找到'}));
    if (!n && !S.q.value.trim()) S.spacer.append(h('div', {class: 'empty', html: '輸入檔名的一部分就會立刻找到。<br><span class="small">支援 Everything 的常用語法，按右上角「？」看說明。</span>'}));
  };
  S.selected = () => [...S.sel].sort((a, b) => a - b).map(i => S.items[i]).filter(Boolean);
  // selection changes only repaint the classes of the rows on screen: re-creating the row under the pointer would swallow
  // the double-click and keep the keyboard focus away from the list
  S.paintSel = function () {
    for (const r of S.spacer.children) { const i = +r.dataset.i; if (Number.isNaN(i)) continue; r.classList.toggle('sel', S.sel.has(i)); r.classList.toggle('focus', i === S.focus); }
  };
  S.click = function (e, i) {
    if (e.button === 2) return;
    S.list.focus({preventScroll: true});
    if (e.shiftKey && S.anchor >= 0) { S.sel.clear(); for (let k = Math.min(S.anchor, i); k <= Math.max(S.anchor, i); k++) S.sel.add(k); S.focus = i; }
    else if (e.ctrlKey || e.metaKey) { S.sel.has(i) ? S.sel.delete(i) : S.sel.add(i); S.focus = i; S.anchor = i; }
    else { S.select(i, false); return; }
    S.paintSel();
  };
  S.select = function (i, range) {
    if (i < 0 || i >= S.items.length) return;
    if (range && S.anchor >= 0) { S.sel.clear(); for (let k = Math.min(S.anchor, i); k <= Math.max(S.anchor, i); k++) S.sel.add(k); }
    else { S.sel = new Set([i]); S.anchor = i; }
    S.focus = i;
    const top = i * ROW; if (top < S.list.scrollTop) S.list.scrollTop = top; else if (top + ROW > S.list.scrollTop + S.list.clientHeight) S.list.scrollTop = top + ROW - S.list.clientHeight;
    S.renderRows(); S.paintSel();                                   // rows re-made only when the visible range moved
  };
  S.key = function (e) {
    const n = S.items.length, k = e.key, page = Math.max(1, Math.floor(S.list.clientHeight / ROW) - 1);
    const mv = t => { e.preventDefault(); S.select(Math.max(0, Math.min(n - 1, t)), e.shiftKey); };
    if (k === 'ArrowDown') mv(S.focus + 1); else if (k === 'ArrowUp') { if (S.focus <= 0) { e.preventDefault(); S.q.focus(); } else mv(S.focus - 1); }
    else if (k === 'PageDown') mv(S.focus + page); else if (k === 'PageUp') mv(S.focus - page); else if (k === 'Home') mv(0); else if (k === 'End') mv(n - 1);
    else if (k === 'Enter') { e.preventDefault(); const it = S.items[S.focus]; if (it) e.altKey ? HZ.props(it) : HZ.openItem(it); }
    else if (k === 'Delete') { e.preventDefault(); HZ.deleteItems(S.selected(), e.shiftKey).then(() => setTimeout(S.search, 1500)); }
    else if (k === 'F2') { e.preventDefault(); const it = S.items[S.focus]; if (it) HZ.renameItem(it).then(() => setTimeout(S.search, 600)); }
    else if ((e.ctrlKey || e.metaKey) && k.toLowerCase() === 'c') { e.preventDefault(); HZ.setClip('copy', S.selected()); }
    else if ((e.ctrlKey || e.metaKey) && k.toLowerCase() === 'x') { e.preventDefault(); HZ.setClip('cut', S.selected()); }
    else if ((e.ctrlKey || e.metaKey) && k.toLowerCase() === 'a') {
      e.preventDefault(); S.sel = new Set(S.items.map((_, i) => i)); S.renderRows(true);
      if (S.total > S.items.length) HZ.toast(`已選取列出的 ${S.items.length.toLocaleString()} 個（共 ${S.total.toLocaleString()} 個結果，其餘沒有列出的不會被選取）`);
    }
  };
  S.help = function () {
    HZ.dialog({title: '搜尋語法（和 Everything 一樣）', width: '640px', body: `<div class="help">
      <code>報告 2026</code> 名稱同時包含兩個詞　<code>報告|企劃</code> 任一個　<code>!草稿</code> 不包含　<code>"年度 報告"</code> 完整片語<br>
      <code>*.mp4</code> <code>IMG_????.jpg</code> 萬用字元（比對整個檔名）　<code>regex:^\\d{8}</code> 正規表達式<br>
      <code>K:\\Work\\ 報告</code> 有 \\ 的詞比對完整路徑　<code>path:專案</code> 同上<br>
      <code>ext:mp4;mkv</code> 副檔名　<code>video:</code> <code>audio:</code> <code>pic:</code> <code>doc:</code> <code>zip:</code> <code>exe:</code> 類型<br>
      <code>size:>1gb</code> <code>size:100mb..2gb</code> <code>size:<10kb</code> <code>size:empty</code> 大小（也可用 tiny small medium large huge gigantic）<br>
      <code>dm:today</code> <code>dm:yesterday</code> <code>dm:thisweek</code> <code>dm:last7days</code> <code>dm:2026-10</code> <code>dm:>2026-01-01</code> <code>dm:2026-01..2026-03</code> 修改日期<br>
      <code>dupe:</code> 同名檔案（別的地方也有同樣檔名的）　<code>sizedupe:</code> 一樣大小的檔案　可以和其他條件一起用，例如 <code>dupe: ext:jpg</code><br>
      <code>file:</code> 只要檔案　<code>folder:</code> 只要資料夾　<code>empty:</code> 空資料夾　<code>parent:K:\\Work</code> 只看這一層　<code>infolder:K:\\Work</code> 這個資料夾底下<br>
      <code>hot:</code> 熱處理資料夾裡的檔案　<code>case:ABC</code> 區分大小寫<br><br>
      <span class="muted">NTFS 磁碟以系統管理員身分讀取 MFT 建立索引（幾秒到一分鐘），之後由 USN 變更日誌即時更新；其他磁碟定期重新掃描。</span></div>`});
  };
  S.onShow = function () {
    S.fillScopes(); setTimeout(() => S.q.focus(), 30);
    if (!S.q.value) S.info.innerHTML = S.idxText();
    else S.search();                                                 // results from before: refresh them (selection kept by path)
  };
  S.onState = function () { if (!S.q.value) S.info.innerHTML = S.idxText(); };
  S.onFsChange = function () { if (HZ.cur === 'search' && S.q.value.trim()) setTimeout(() => S.search(), 1200); else S._stale = true; };
  HZ.page('search', S);
})();

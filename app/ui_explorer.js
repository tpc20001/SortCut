/* HotZone FM — 檔案總管: tabs, dual pane (F5 copy / F6 move to the other side), virtual list, drag & drop, preview */
'use strict';
(function () {
  const {h, esc} = HZ;
  const ROW = 26;
  const COLS = () => innerWidth < 820 ? 'minmax(0,1fr) 92px' : 'minmax(220px,1fr) 142px 120px 130px';
  const E = {title: '檔案總管', tabs: [], ti: 0, panes: [], active: 0, dual: false, preview: false, view: 'details'};
  E.COLL = new Intl.Collator('zh-Hant', {numeric: true, sensitivity: 'base'});
  let uid = 1;

  function newPaneState(path) { return {path: path || '', hist: [path || ''], hi: 0, items: [], shown: [], sort: {key: 'name', desc: false}, sel: new Set(), focus: -1, anchor: -1, filter: '', data: null, sizes: {}}; }
  function saveTabs() {
    try { localStorage.setItem('hz.tabs', JSON.stringify({ti: E.ti, dual: E.dual, preview: E.preview, view: E.view, tabs: E.tabs.map(t => ({p: t.panes.map(p => p.path), a: t.active, sort: t.panes.map(p => p.sort), home: !!t.home}))})); } catch (e) { }
  }
  function loadTabs() {
    try {
      const j = JSON.parse(localStorage.getItem('hz.tabs') || 'null');
      if (j && j.tabs && j.tabs.length) {
        E.dual = !!j.dual; E.preview = !!j.preview; E.view = j.view || 'details';
        E.tabs = j.tabs.map(t => ({id: uid++, active: t.a || 0, home: !!t.home, panes: t.p.map((p, i) => Object.assign(newPaneState(p), {sort: (t.sort && t.sort[i]) || {key: 'name', desc: false}}))}));
        // opening the app always starts at 本機 (the drive list): the old tabs stay, but last time's folders are not
        // the first thing on screen
        let ri = E.tabs.findIndex(t => t.home);                       // the start tab of last time is reused (no pile-up)
        if (ri < 0) ri = E.tabs.findIndex(t => t.panes.every(p => !p.path));
        if (ri < 0) { E.tabs.unshift({id: uid++, active: 0, panes: [newPaneState(''), newPaneState('')]}); ri = 0; }
        const T = E.tabs[ri]; T.home = true; T.active = 0; T.panes = T.panes.map(p => Object.assign(newPaneState(''), {sort: p.sort}));
        E.ti = ri; return;
      }
    } catch (e) { }
    E.tabs = [{id: uid++, active: 0, home: true, panes: [newPaneState(''), newPaneState('')]}]; E.ti = 0;
    E.dual = !!(HZ.settings && HZ.settings['explorer.dual']);
  }
  const tab = () => E.tabs[E.ti];

  /* ======================================================================= Pane (DOM) */
  class Pane {
    constructor(idx, host) {
      this.idx = idx;
      this.el = h('div', {class: 'pane'});
      this.head = h('div', {class: 'phead'});
      this.banner = h('div', {class: 'hotbanner', style: {display: 'none'}});
      this.lhead = h('div', {class: 'lhead'});
      this.list = h('div', {class: 'list', tabindex: '0'});
      this.spacer = h('div', {class: 'spacer'});
      this.list.append(this.spacer);
      this.stat = h('div', {class: 'pstat'});
      this.el.append(this.head, this.banner, this.lhead, this.list, this.stat);
      host.append(this.el);
      this.el.addEventListener('mousedown', () => E.setActive(this.idx));
      this.list.addEventListener('scroll', () => this.renderRows());
      this.list.addEventListener('keydown', e => this.key(e));
      this.list.addEventListener('contextmenu', e => { if (!e.target.closest('.it,.gi,.drive')) { e.preventDefault(); this.bgMenu(e); } });
      this.list.addEventListener('mousedown', e => {
        if (e.target.closest('.it,.gi,.drive') || e.button !== 0) return;
        if (!e.ctrlKey && !e.shiftKey) { this.s.sel.clear(); this.s.focus = -1; this.paintSel(); }
        if (E.view !== 'grid' && this.s.path && e.target.closest('.list') === this.list && e.clientX < this.list.getBoundingClientRect().right - 14) this.band(e);
      });
      this.list.addEventListener('dblclick', e => { if (!e.target.closest('.it,.gi,.drive') && this.s.path) { /* empty area */ } });
      this.dnd(this.list, () => this.s.path);
      new ResizeObserver(() => this.renderRows()).observe(this.list);
    }
    /* rubber-band selection (details view): drag on empty space, every row the band touches is selected */
    band(e0) {
      const L = this.list, r0 = L.getBoundingClientRect(), y0 = e0.clientY - r0.top + L.scrollTop, x0 = e0.clientX - r0.left;
      const base = e0.ctrlKey ? new Set(this.s.sel) : new Set(); let box = null, last = null, timer = null;
      const upd = ev => {
        last = ev || last; if (!last) return;
        const r = L.getBoundingClientRect(), y1 = last.clientY - r.top + L.scrollTop, x1 = last.clientX - r.left;
        if (!box && Math.abs(y1 - y0) + Math.abs(x1 - x0) < 6) return;
        if (!box) { box = h('div', {class: 'band'}); this.spacer.append(box); }
        const top = Math.max(0, Math.min(y0, y1)), bot = Math.max(y0, y1);
        Object.assign(box.style, {left: Math.min(x0, x1) + 'px', top: top + 'px', width: Math.abs(x1 - x0) + 'px', height: (bot - top) + 'px'});
        const s = this.s, n = s.shown.length, a = Math.max(0, Math.floor(top / ROW)), b = Math.min(n - 1, Math.floor(bot / ROW));
        s.sel = new Set(base); for (let i = a; i <= b; i++) if (s.shown[i]) s.sel.add(s.shown[i].path);
        s.focus = Math.min(n - 1, Math.max(0, y1 > y0 ? b : a)); this.paintSel();
      };
      const scroll = () => {                                                // drag past the top / bottom edge: scroll along
        if (!last) return; const r = L.getBoundingClientRect();
        const d = last.clientY < r.top + 20 ? -ROW : last.clientY > r.bottom - 20 ? ROW : 0;
        if (d) { L.scrollTop += d; upd(); }
      };
      const mv = ev => upd(ev);
      const up = () => { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); clearInterval(timer); if (box) box.remove(); L.focus({preventScroll: true}); };
      document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up); timer = setInterval(scroll, 50);
    }
    get s() { return tab().panes[this.idx]; }
    get path() { return this.s.path; }

    /* ---------------- navigation */
    async nav(path, selectName, push = true) {
      const s = this.s;
      if (push && path !== s.path) { s.hist = s.hist.slice(0, s.hi + 1); s.hist.push(path); s.hi = s.hist.length - 1; }
      s.path = path; s.sel.clear(); s.focus = -1; s.anchor = -1; s.filter = ''; s.sizes = {};
      if (E.filterBox && E.active === this.idx) E.filterBox.value = '';
      this.list.scrollTop = 0;
      await this.load(selectName);
      E.renderTabs(); saveTabs(); E.revealInTree(this.s.path);
    }
    async load(selectName, quiet) {
      const s = this.s, path = s.path, myTab = tab();
      let d;
      const prev = quiet && !selectName && s.data && s.data.path === path && s.data.sig;
      try { d = await HZ.get('/api/ls', prev ? {path, sig: prev} : {path}); }
      catch (e) { if (!quiet) HZ.err(e); return; }
      if (tab() !== myTab || s.path !== path) return;
      if (d.same) return;                                                     // nothing changed: no re-sort / redraw
      if (d.error && !quiet) HZ.toast(esc(d.error), 'bad');
      s.data = d;
      if (d.root) { HZ.vols = d.vols; HZ.favs = d.fav; HZ.hotFolders = d.hot; }
      s.items = d.items || [];
      if (d.path && d.path !== path) s.path = d.path;
      this.applySort();
      if (selectName) {
        const want = String(selectName);
        let i = s.shown.findIndex(x => x.name === want);                      // exact first: 'case.jpg' vs 'Case.jpg'
        if (i < 0) i = s.shown.findIndex(x => x.name.toLowerCase() === want.toLowerCase());
        if (i >= 0) { s.sel = new Set([s.shown[i].path]); s.focus = i; s.anchor = i; this.scrollTo(i); }
      } else if (quiet) {
        const keep = new Set(s.shown.map(x => x.path)); for (const p of [...s.sel]) if (!keep.has(p)) s.sel.delete(p);
      }
      this.render();
      if (E.cur() === this) E.renderAddr();                                    // new / restored tab: the address bar too
      if (d.indexed && !d.root) this.loadSizes();
    }
    async loadSizes() {
      const s = this.s, dirs = s.items.filter(x => x.dir).map(x => x.path);
      if (!dirs.length) return;
      try {
        const r = await HZ.post('/api/dirsizes', {paths: dirs});
        if (s !== this.s) return;
        s.sizes = r.sizes || {};
        for (const it of s.items) if (it.dir && s.sizes[it.path]) { it.size = s.sizes[it.path][0]; it.files = s.sizes[it.path][1]; }
        if (s.sort.key === 'size') this.applySort();
        this.renderRows(true); this.renderStat();
      } catch (e) { }
    }
    applySort() {
      const s = this.s, {key, desc} = s.sort, f = s.filter.toLowerCase();
      let arr = f ? s.items.filter(x => x.name.toLowerCase().includes(f)) : s.items.slice();
      const cmpName = (a, b) => E.COLL.compare(a.name, b.name);              // one shared collator: 100k items 10 s -> 0.4 s
      const by = {name: cmpName, mtime: (a, b) => a.mtime - b.mtime || cmpName(a, b), size: (a, b) => (a.size || 0) - (b.size || 0) || cmpName(a, b),
        type: (a, b) => (a.ext || '').localeCompare(b.ext || '') || cmpName(a, b)}[key] || cmpName;
      arr.sort((a, b) => (b.dir - a.dir) || (desc ? -by(a, b) : by(a, b)));
      s.shown = arr;
    }

    /* ---------------- render */
    render() {
      const s = this.s, d = s.data || {};
      this.el.classList.toggle('active', E.active === this.idx);
      // header
      this.head.innerHTML = '';
      const title = s.path ? (HZ.base(s.path) || s.path) : '本機';
      this.head.append(h('span', {class: 'ptitle ell', text: title}), h('span', {class: 'grow'}));
      if (E.dual) this.head.append(h('span', {class: 'small', text: E.active === this.idx ? '● 作用中' : '點一下切換'}));
      // hot banner
      if (d.in_hot) {
        this.banner.style.display = '';
        this.banner.innerHTML = `🔥 <b>熱處理資料夾</b><span class="small">放進來的檔案馬上能用，背景會把它們搬到硬碟外圈（最快的區域）</span><span class="grow"></span><a href="javascript:void 0" onclick="HZ.go('hot')" class="small">查看進度</a>`;
      } else this.banner.style.display = 'none';
      // columns
      this.lhead.style.setProperty('--cols', COLS()); this.list.style.setProperty('--cols', COLS());
      this.lhead.innerHTML = '';
      if (!s.path) { this.lhead.style.display = 'none'; }
      else {
        this.lhead.style.display = E.view === 'grid' ? 'none' : '';
        for (const [k, label, cls] of [['name', '名稱', ''], ['mtime', '修改日期', 'c-date'], ['type', '類型', 'c-type'], ['size', '大小', '']]) {
          const c = h('div', {class: cls + (s.sort.key === k ? ' sorted' : ''), text: label + (s.sort.key === k ? (s.sort.desc ? ' ▼' : ' ▲') : '')});
          if (k === 'size') c.style.textAlign = 'right';
          c.onclick = () => { s.sort = {key: k, desc: s.sort.key === k ? !s.sort.desc : (k === 'size' || k === 'mtime')}; this.applySort(); this.render(); saveTabs(); };
          this.lhead.append(c);
        }
      }
      this.list.classList.toggle('grid-view', E.view === 'grid' && !!s.path);
      this.list.setAttribute('data-drop', s.path || '');
      if (!s.path) this.renderRoot(); else this.renderRows(true);
      this.renderStat();
    }
    renderRoot() {
      const d = this.s.data || {};
      this.spacer.style.height = ''; this.spacer.innerHTML = '';
      const wrap = h('div', {style: {padding: '12px'}});
      wrap.append(h('h3', {text: '磁碟'}));
      const grid = h('div', {class: 'cards'});
      const disks = {}; for (const x of d.disks || []) disks[x.n] = x;
      for (const v of d.vols || []) {
        if (v.type === 'cdrom' && !v.ok) continue;
        const used = v.total ? (v.total - v.free) / v.total * 100 : 0;
        const dk = (v.disks || []).map(n => disks[n]).filter(Boolean)[0];
        const root = /^[A-Z]:$/.test(v.letter) ? v.letter + '\\' : v.letter;
        const c = h('div', {class: 'card drive', 'data-drop': root, style: {cursor: 'pointer'}},
          h('div', {class: 'row'}, h('b', {style: {fontSize: '15px'}, text: '💽 ' + v.letter}), h('span', {class: 'ell', text: v.label || ''}), h('span', {class: 'grow'}),
            v.media && v.media !== '?' ? h('span', {class: 'pill acc', text: v.media}) : null, v.smr ? h('span', {class: 'pill warn', title: '型號看起來是 SMR（疊瓦式）硬碟', text: 'SMR?'}) : null,
            h('span', {class: 'pill', text: v.fs || v.type})),
          h('div', {class: 'bar big', style: {margin: '8px 0 4px'}}, h('i', {class: used > 92 ? 'bad' : used > 80 ? 'warn' : '', style: {width: used + '%'}})),
          h('div', {class: 'small muted', text: v.total ? `可用 ${HZ.fmtSize(v.free)}，共 ${HZ.fmtSize(v.total)}` + (dk ? `　·　實體磁碟 ${dk.n} ${dk.model || ''}` : '') : '無法讀取'}));
        c.onclick = () => this.nav(root);
        c.oncontextmenu = e => { e.preventDefault(); HZ.menu(e.clientX, e.clientY, [{icon: '📂', text: '開啟', run: () => this.nav(root)}, {icon: '🗂', text: '在新分頁開啟', run: () => E.newTab(root)},
          {icon: '📊', text: '分析空間', run: () => { HZ.go('space'); HZ.pages.space.load(root); }}, {icon: '📥', text: '貼上', run: () => HZ.paste(root)}]); };
        grid.append(c);
      }
      wrap.append(grid);
      const hot = d.hot || [];
      wrap.append(h('h3', {html: '🔥 熱處理資料夾'}));
      if (!hot.length) wrap.append(h('div', {class: 'muted small', text: '還沒有。對資料夾按右鍵 →「標記為熱處理優先」。'}));
      for (const f of hot) wrap.append(h('div', {class: 'tn', 'data-drop': f.path, onclick: () => this.nav(f.path)}, h('span', {html: HZ.icon({dir: true, hot: true})}), f.path));
      if ((d.fav || []).length) {
        wrap.append(h('h3', {text: '⭐ 我的最愛'}));
        for (const f of d.fav) wrap.append(h('div', {class: 'tn', 'data-drop': f, onclick: () => this.nav(f)}, h('span', {html: HZ.icon({dir: true})}), f));
      }
      this.spacer.append(wrap);
    }
    renderRows(force) {
      const s = this.s;
      if (!s.path) return;
      if (E.view === 'grid') return this.renderGrid(force);
      const n = s.shown.length, H = this.list.clientHeight || 600;
      this.spacer.style.height = Math.max(n * ROW, 1) + 'px';
      const a = Math.max(0, Math.floor(this.list.scrollTop / ROW) - 10), b = Math.min(n, Math.ceil((this.list.scrollTop + H) / ROW) + 10);
      if (!force && this._range && this._range[0] === a && this._range[1] === b) return;
      this._range = [a, b];
      const maxSize = Math.max(1, ...s.shown.slice(0, 5000).map(x => x.size > 0 ? x.size : 0));
      const frag = document.createDocumentFragment();
      const cut = HZ.clip && HZ.clip.op === 'cut' ? new Set(HZ.clip.paths) : null;
      for (let i = a; i < b; i++) {
        const it = s.shown[i];
        const sz = it.size >= 0 ? `<span class="bar"><i class="${it.dir ? 'hot' : ''}" style="width:${Math.max(2, it.size / maxSize * 100)}%;${it.dir ? '' : 'background:var(--scroll)'}"></i></span>${HZ.fmtSize(it.size)}` : (it.dir ? '' : '');
        const row = h('div', {class: 'it' + (s.sel.has(it.path) ? ' sel' : '') + (i === s.focus ? ' focus' : '') + (cut && cut.has(it.path) ? ' cut' : ''),
          style: {top: i * ROW + 'px'}, 'data-i': i, draggable: 'true', 'data-drop': it.dir ? it.path : null,
          html: `<div class="nm${it.hidden ? ' hidden' : ''}">${HZ.icon(it)}<span>${esc(it.name)}</span>${it.hot ? '<b class="hotmark">🔥 熱</b>' : ''}</div>
            <div class="c-date muted">${HZ.fmtDate(it.mtime)}</div><div class="c-type muted">${esc(HZ.typeLabel(it))}</div><div class="sz">${sz}</div>`});
        frag.append(row);
      }
      this.spacer.innerHTML = ''; this.spacer.append(frag);
      if (!n) this.spacer.append(h('div', {class: 'empty', text: s.filter ? '沒有符合的項目' : (s.data && s.data.error) || '這個資料夾是空的'}));
      this.bindRows();
    }
    renderGrid() {
      const s = this.s; this.spacer.style.height = ''; this.spacer.innerHTML = '';
      const frag = document.createDocumentFragment();
      const max = Math.min(s.shown.length, 3000);
      for (let i = 0; i < max; i++) {
        const it = s.shown[i];
        const k = HZ.kind(it.ext), big = HZ.icon(it, true).replace('class="ico"', 'class="ico" style="width:44px;height:44px"');
        const thumb = !it.dir && (k === 'image' || k === 'video') && HZ.thumbsOk(k)
          ? `<div class="thw">${big}<img class="th" data-src="/api/thumb?${esc(String(new URLSearchParams({path: it.path, s: 200})))}" onerror="this.remove()"></div>`
          : it.dir && HZ.thumbsOk('image') && !/^[A-Za-z]:\\?$/.test(it.path)                          // folder: its cover picture, with a small folder badge
          ? `<div class="thw fcover">${big}<img class="th" data-src="/api/thumb?${esc(String(new URLSearchParams({path: it.path, s: 200, dir: '1'})))}" onload="this.parentNode.classList.add('has')" onerror="this.remove()"></div>` : big;
        frag.append(h('div', {class: 'gi it-g' + (s.sel.has(it.path) ? ' sel' : ''), 'data-i': i, draggable: 'true', 'data-drop': it.dir ? it.path : null, title: it.name,
          html: `${thumb}<span>${it.hot ? '🔥 ' : ''}${esc(it.name)}</span>`}));
      }
      this.spacer.append(frag); HZ.lazyThumbs(this.spacer);
      if (s.shown.length > max) this.spacer.append(h('div', {class: 'empty', text: `只顯示前 ${max} 個，請用詳細清單或篩選`}));
      if (!s.shown.length) this.spacer.append(h('div', {class: 'empty', text: '這個資料夾是空的'}));
      this.bindRows();
    }
    bindRows() {
      for (const r of this.spacer.querySelectorAll('[data-i]')) {
        const i = +r.dataset.i;
        r.onmousedown = e => this.clickRow(e, i);
        r.ondblclick = () => this.openIdx(i);
        r.onclick = e => { if (HZ.lastPointer === 'touch' && !e.shiftKey && !e.ctrlKey && !e.metaKey) this.openIdx(i); };   // phone: one tap opens
        r.oncontextmenu = e => { e.preventDefault(); if (!this.s.sel.has(this.s.shown[i].path)) this.select(i, false, false); this.itemMenu(e); };
        r.ondragstart = e => this.dragStart(e, i);
      }
    }
    paintSel() {
      const s = this.s;
      for (const r of this.spacer.querySelectorAll('[data-i]')) {
        const i = +r.dataset.i, it = s.shown[i];
        r.classList.toggle('sel', s.sel.has(it.path)); r.classList.toggle('focus', i === s.focus);
      }
      this.renderStat(); E.updatePreview();
    }
    renderStat() {
      const s = this.s, d = s.data || {};
      if (!s.path) { this.stat.innerHTML = `<span>${(d.vols || []).length} 個磁碟</span>`; return; }
      if (!s._byPath || s._byPathOf !== s.shown) { s._byPath = new Map(s.shown.map(x => [x.path, x])); s._byPathOf = s.shown; }
      const sel = []; for (const p of s.sel) { const x = s._byPath.get(p); if (x) sel.push(x); }   // (was a 100k filter per arrow key)
      const selSize = sel.reduce((a, x) => a + (x.size > 0 ? x.size : 0), 0);
      const v = d.vol || {};
      this.stat.innerHTML = `<span>${s.shown.length.toLocaleString()} 個項目${s.filter ? `（篩選：${esc(s.filter)}）` : ''}</span>` +
        (sel.length ? `<span>已選 ${sel.length} 個${selSize ? '，' + HZ.fmtSize(selSize) : ''}</span>` : '') +
        `<span class="grow"></span>` + (d.indexed ? '<span title="資料夾大小來自索引">⚡ 已索引</span>' : '') +
        (v.total ? `<span>${esc(v.letter || '')} 可用 ${HZ.fmtSize(v.free)} / ${HZ.fmtSize(v.total)}</span>` : '');
    }

    /* ---------------- selection / keyboard */
    clickRow(e, i) {
      if (e.button === 2) return;
      E.setActive(this.idx);
      const s = this.s, it = s.shown[i];
      if (e.shiftKey && s.anchor >= 0) this.select(i, true, e.ctrlKey);
      else if (e.ctrlKey || e.metaKey) { if (s.sel.has(it.path)) s.sel.delete(it.path); else s.sel.add(it.path); s.focus = i; s.anchor = i; this.paintSel(); }
      else if (!s.sel.has(it.path) || s.sel.size === 1) this.select(i, false, false);
      else { s.focus = i; this.paintSel(); }
      this.list.focus({preventScroll: true});
    }
    select(i, range, add) {
      const s = this.s; if (i < 0 || i >= s.shown.length) return;
      if (range && s.anchor >= 0) {
        if (!add) s.sel.clear();
        const [a, b] = [Math.min(s.anchor, i), Math.max(s.anchor, i)];
        for (let k = a; k <= b; k++) s.sel.add(s.shown[k].path);
      } else { if (!add) s.sel.clear(); s.sel.add(s.shown[i].path); s.anchor = i; }
      s.focus = i; this.scrollTo(i); this.paintSel();
    }
    scrollTo(i) {
      if (E.view === 'grid') return;
      const top = i * ROW, L = this.list;
      if (top < L.scrollTop) L.scrollTop = top; else if (top + ROW > L.scrollTop + L.clientHeight) L.scrollTop = top + ROW - L.clientHeight;
      this.renderRows();
    }
    selected() { const s = this.s; return s.shown.filter(x => s.sel.has(x.path)); }
    openIdx(i) {
      const it = this.s.shown[i]; if (!it) return;
      if (it.dir) this.nav(it.path); else HZ.openItem(it);
    }
    up() {
      const s = this.s; if (!s.path) return;
      const p = (s.data && s.data.parent) || '';
      this.nav(p, HZ.base(s.path));
    }
    back() { const s = this.s; if (s.hi > 0) { s.hi--; this.nav(s.hist[s.hi], null, false); } }
    fwd() { const s = this.s; if (s.hi < s.hist.length - 1) { s.hi++; this.nav(s.hist[s.hi], null, false); } }
    key(e) {
      const s = this.s, n = s.shown.length, k = e.key, ctrl = e.ctrlKey || e.metaKey;
      if (document.querySelector('#overlay.on')) return;
      const page = Math.max(1, Math.floor(this.list.clientHeight / ROW) - 1);
      const mv = t => { e.preventDefault(); this.select(Math.max(0, Math.min(n - 1, t)), e.shiftKey, false); };
      if (k === 'ArrowDown') mv(s.focus + 1); else if (k === 'ArrowUp') mv(s.focus < 0 ? 0 : s.focus - 1);
      else if (k === 'PageDown') mv(s.focus + page); else if (k === 'PageUp') mv(s.focus - page);
      else if (k === 'Home') mv(0); else if (k === 'End') mv(n - 1);
      else if (k === 'Enter' && e.altKey) { e.preventDefault(); const it = this.selected()[0]; if (it) HZ.props(it); }
      else if (k === 'Enter') { e.preventDefault(); const sel = this.selected(); if (sel.length === 1) this.openIdx(s.shown.indexOf(sel[0])); else if (sel.length > 1 && !sel.some(x => x.dir)) sel.slice(0, 10).forEach(HZ.openItem); }
      else if (k === 'Backspace' || (k === 'ArrowUp' && e.altKey)) { e.preventDefault(); this.up(); }
      else if (k === 'ArrowLeft' && e.altKey) { e.preventDefault(); this.back(); }
      else if (k === 'ArrowRight' && e.altKey) { e.preventDefault(); this.fwd(); }
      else if (k === 'F2') { e.preventDefault(); const sel = this.selected(); if (sel.length > 1) HZ.batchRename(sel); else if (sel[0]) HZ.renameItem(sel[0]).then(n => { if (n) this.load(n, true); this.list.focus({preventScroll: true}); }); }
      else if (k === 'Delete') { e.preventDefault(); HZ.deleteItems(this.selected(), e.shiftKey); }
      else if (ctrl && k.toLowerCase() === 'a') { e.preventDefault(); s.sel = new Set(s.shown.map(x => x.path)); this.paintSel(); }
      else if (ctrl && k.toLowerCase() === 'c') { e.preventDefault(); if (this.selected().length) HZ.setClip('copy', this.selected()); }
      else if (ctrl && k.toLowerCase() === 'x') { e.preventDefault(); if (this.selected().length) HZ.setClip('cut', this.selected()); }
      else if (ctrl && k.toLowerCase() === 'v') { e.preventDefault(); if (s.path) HZ.paste(s.path); }
      else if (ctrl && e.shiftKey && k.toLowerCase() === 'n') { e.preventDefault(); E.newFolder(); }
      else if (ctrl && k.toLowerCase() === 'z') { e.preventDefault(); HZ.undo(); }
      else if (ctrl && k.toLowerCase() === 'r') { e.preventDefault(); this.load(); }
      else if (k === 'F5' && E.dual && this.selected().length) { e.preventDefault(); E.toOther('copy'); }
      else if (k === 'F5') { e.preventDefault(); this.load(); }
      else if (k === 'F6' && E.dual && this.selected().length) { e.preventDefault(); E.toOther('move'); }
      else if (k === 'Tab' && E.dual) { e.preventDefault(); E.setActive(1 - this.idx); E.panes[E.active].list.focus(); }
      else if (k.length === 1 && !ctrl && !e.altKey && /\S/.test(k)) {             // type-ahead
        clearTimeout(this._tat); this._ta = (this._ta || '') + k.toLowerCase(); this._tat = setTimeout(() => this._ta = '', 900);
        const start = this._ta.length === 1 ? s.focus + 1 : Math.max(0, s.focus);
        for (let j = 0; j < n; j++) { const q = (start + j) % n; if (s.shown[q].name.toLowerCase().startsWith(this._ta)) { this.select(q, false, false); break; } }
      }
    }

    /* ---------------- menus */
    itemMenu(e) { HZ.menu(e.clientX, e.clientY, HZ.itemMenu(this.selected(), {dir: this.s.path, pane: this, inExplorer: true, onItem: true})); }
    bgMenu(e) {
      const s = this.s; if (!s.path) return;
      const d = s.data || {};
      const isHotRoot = d.hot_root;
      HZ.menu(e.clientX, e.clientY, [
        {icon: '📥', text: '貼上', key: 'Ctrl+V', run: () => HZ.paste(s.path)},
        {icon: '📁', text: '新增資料夾', key: 'Ctrl+Shift+N', run: () => E.newFolder()},
        {icon: '📄', text: '新增文字檔', run: () => E.newFile()},
        '-',
        {icon: '⟳', text: '重新整理', key: 'F5', run: () => this.load()},
        {icon: '☑', text: '全選', key: 'Ctrl+A', run: () => { s.sel = new Set(s.shown.map(x => x.path)); this.paintSel(); }},
        {icon: E.view === 'grid' ? '☰' : '▦', text: E.view === 'grid' ? '詳細清單' : '大圖示', run: () => E.setView(E.view === 'grid' ? 'details' : 'grid')},
        '-',
        !isHotRoot && !d.in_hot && {icon: '🔥', text: '把這個資料夾標記為熱處理', run: () => HZ.markHot(s.path, true)},
        isHotRoot && {icon: '🧊', text: '取消熱處理', run: () => HZ.markHot(s.path, false)},
        {icon: '📊', text: '分析空間', run: () => { HZ.go('space'); HZ.pages.space.load(s.path); }},
        {icon: '🔍', text: '在這裡搜尋', run: () => { HZ.go('search'); HZ.pages.search.setScope(s.path); }},
        (HZ.bridge || HZ.local) && {icon: '🪟', text: '用 Windows 檔案總管開啟', run: () => HZ.bridge ? HZ.bridge.openLocal(s.path) : HZ.post('/api/system/open', {path: s.path})},
        {icon: '⬆', text: '上傳檔案到這裡', run: () => E.uploadPick(s.path)},
        {icon: '⭐', text: (HZ.favs || []).includes(s.path) ? '從我的最愛移除' : '加入我的最愛', run: () => HZ.toggleFav(s.path)},
        {icon: '🔗', text: '複製路徑', run: () => HZ.copyText(s.path)},
        {icon: 'ℹ', text: '資料夾內容', run: () => HZ.props({path: s.path, name: HZ.base(s.path), dir: true})},
      ]);
    }

    /* ---------------- drag & drop */
    dragStart(e, i) {
      const s = this.s, it = s.shown[i];
      if (!s.sel.has(it.path)) this.select(i, false, false);
      const paths = this.selected().map(x => x.path);
      if (HZ.bridge) { e.preventDefault(); HZ.bridge.startDrag(JSON.stringify(paths)); return; }
      e.dataTransfer.setData('application/x-hz-paths', JSON.stringify(paths));
      e.dataTransfer.setData('text/plain', paths.join('\n'));
      e.dataTransfer.effectAllowed = 'copyMove';
    }
    dnd(el, pathFn) { E.bindDrop(el, pathFn); }
  }

  /* ======================================================================= drag & drop (browser) */
  E.bindDrop = function (el) {
    let last = null;
    const target = e => { const t = e.target.closest('[data-drop]'); return t && t.getAttribute('data-drop') ? t : null; };
    el.addEventListener('dragover', e => {
      const t = target(e); if (!t) return;
      e.preventDefault(); e.dataTransfer.dropEffect = e.ctrlKey ? 'copy' : e.shiftKey ? 'move' : 'copy';
      if (last !== t) { last && last.classList.remove('drop'); t.classList.add('drop'); last = t; }
    });
    el.addEventListener('dragleave', e => { if (last && !el.contains(e.relatedTarget)) { last.classList.remove('drop'); last = null; } });
    el.addEventListener('drop', e => {
      const t = target(e); last && last.classList.remove('drop'); last = null;
      if (!t) return; e.preventDefault();
      const dst = t.getAttribute('data-drop');
      const raw = e.dataTransfer.getData('application/x-hz-paths');
      if (raw) { HZ.dropPaths(JSON.parse(raw), dst, (e.ctrlKey ? 'ctrl' : '') + (e.shiftKey ? 'shift' : '')); return; }
      if (e.dataTransfer.files && e.dataTransfer.files.length) E.upload(e.dataTransfer.files, dst);
    });
  };

  /* ======================================================================= uploads (browser / remote) */
  E.uploadPick = function (dir) {
    const inp = h('input', {type: 'file', multiple: true, style: {display: 'none'}});
    inp.onchange = () => { E.upload(inp.files, dir); inp.remove(); };
    document.body.append(inp); inp.click();
  };
  E.upload = async function (files, dir) {
    const list = Array.from(files); if (!list.length) return;
    const total = list.reduce((a, f) => a + f.size, 0); let done = 0;
    const t = h('div', {class: 'toast'}); $('#toasts').append(t);
    for (const f of list) {
      await new Promise(res => {
        const x = new XMLHttpRequest();
        x.open('PUT', '/api/upload?' + new URLSearchParams({dir, name: f.name, mode: 'rename'}));
        x.setRequestHeader('X-HZ', '1');
        x.upload.onprogress = ev => { t.innerHTML = `⬆ 上傳 ${esc(f.name)}<br>${HZ.fmtSize(done + ev.loaded)} / ${HZ.fmtSize(total)}`; };
        x.onload = () => { if (x.status >= 400) HZ.toast('上傳失敗：' + esc(f.name), 'bad'); res(); };
        x.onerror = () => { HZ.toast('上傳失敗：' + esc(f.name), 'bad'); res(); };
        x.send(f);
      });
      done += f.size;
    }
    t.remove(); HZ.toast(`已上傳 ${list.length} 個檔案（${HZ.fmtSize(total)}）`, 'ok'); HZ.refreshViews();
  };
  const $ = (s, r = document) => r.querySelector(s);

  /* ======================================================================= page */
  E.build = function (root) {
    loadTabs();
    E.root = root;
    E.tabsEl = h('div', {class: 'xtabs'});
    const nav = h('div', {class: 'row nav'},
      h('button', {class: 'ghost', title: '上一頁 (Alt+←)', onclick: () => E.cur().back()}, '◀'),
      h('button', {class: 'ghost', title: '下一頁 (Alt+→)', onclick: () => E.cur().fwd()}, '▶'),
      h('button', {class: 'ghost', title: '上一層 (Backspace)', onclick: () => E.cur().up()}, '▲'),
      h('button', {class: 'ghost', title: '重新整理 (F5)', onclick: () => E.cur().load()}, '⟳'));
    E.addr = h('div', {class: 'addr'});
    E.filterBox = h('input', {class: 'xsearch', placeholder: '篩選這個資料夾…（Enter = 搜尋子資料夾）'});
    E.filterBox.oninput = HZ.debounce(() => { const p = E.cur(); p.s.filter = E.filterBox.value; p.applySort(); p.render(); }, 120);
    E.filterBox.onkeydown = e => { if (e.key === 'Enter' && E.filterBox.value.trim()) { HZ.go('search'); HZ.pages.search.run(E.filterBox.value.trim(), E.cur().path); } if (e.key === 'Escape') { E.filterBox.value = ''; E.filterBox.oninput(); } };
    const bar = h('div', {class: 'xbar'}, nav, E.addr, E.filterBox,
      E.btnView = h('button', {class: 'ghost', title: '切換顯示方式', onclick: () => E.setView(E.view === 'grid' ? 'details' : 'grid')}, '▦'),
      E.btnDual = h('button', {class: 'ghost', title: '雙窗格（F5 複製、F6 移動到另一邊）', onclick: () => E.setDual(!E.dual)}, '◫ 雙窗格'),
      E.btnPrev = h('button', {class: 'ghost', title: '預覽窗格', onclick: () => E.setPreview(!E.preview)}, '👁 預覽'));
    const A = (ic, label, fn, title) => h('button', {class: 'sm', title: title || label, onclick: fn}, ic + ' ', h('span', {class: 'lbl', text: label}));
    const need = fn => () => { const s = E.cur().selected(); if (!s.length) { HZ.toast('請先選取檔案或資料夾'); return; } fn(s); };
    const acts = h('div', {class: 'xacts'},
      A('📁', '新增資料夾', () => E.newFolder()),
      A('📋', '複製', need(s => HZ.setClip('copy', s))),
      A('✂', '剪下', need(s => HZ.setClip('cut', s))),
      A('📥', '貼上', () => E.cur().path && HZ.paste(E.cur().path)),
      A('✏', '重新命名', need(s => HZ.renameItem(s[0]))),
      A('🗑', '刪除', need(s => HZ.deleteItems(s, false))),
      A('📤', '複製到…', need(s => HZ.pickTarget('copy', s))),
      A('🚚', '移動到…', need(s => HZ.pickTarget('move', s))),
      E.hotBtn = h('button', {class: 'sm hotbtn', onclick: () => E.hotToggle()}, '🔥 標記熱處理'),
      A('📊', '分析空間', () => { const s = E.cur().selected(); const p = (s[0] && s[0].dir) ? s[0].path : E.cur().path; if (p) { HZ.go('space'); HZ.pages.space.load(p); } }),
      A('⬇', '下載', need(s => HZ.download(s))),
      A('⬆', '上傳', () => E.cur().path && E.uploadPick(E.cur().path)),
      A('ℹ', '內容', need(s => HZ.props(s[0]))),
      A('↶', '復原', () => HZ.undo(), '復原上一個動作（Ctrl+Z）：重新命名、新增、移動、複製、刪除（從保管區放回）'));
    E.tree = h('div', {class: 'xtree'});
    E.panesEl = h('div', {class: 'panes'});
    E.prevEl = h('div', {class: 'preview', style: {display: 'none'}});
    root.append(E.tabsEl, bar, acts, h('div', {class: 'xbody'}, E.tree, E.panesEl, E.prevEl));
    E.bindDrop(E.tree);
    E.panes = [new Pane(0, E.panesEl), new Pane(1, E.panesEl)];
    E.applyLayout();
    E.renderTabs();
    for (const p of E.visiblePanes()) p.load();
    E.renderTree();
    document.addEventListener('keydown', e => {
      if (HZ.cur !== 'explorer' || document.querySelector('#overlay.on')) return;
      const ctrl = e.ctrlKey || e.metaKey;
      if (ctrl && e.key.toLowerCase() === 't') { e.preventDefault(); E.newTab(E.cur().path); }
      else if (ctrl && e.key.toLowerCase() === 'w') { e.preventDefault(); E.closeTab(E.ti); }
      else if (ctrl && e.key.toLowerCase() === 'l') { e.preventDefault(); E.editAddr(); }
      else if (ctrl && e.key === 'Tab') { e.preventDefault(); E.switchTab((E.ti + (e.shiftKey ? -1 : 1) + E.tabs.length) % E.tabs.length); }
    });
  };
  E.cur = () => E.panes[E.active] || E.panes[0];
  E.visiblePanes = () => E.dual ? E.panes : [E.panes[0]];
  E.otherPane = p => E.dual ? E.panes[1 - p.idx] : null;
  E.setActive = function (i) {
    if (!E.dual) i = 0;
    if (E.active === i) return;
    E.active = i; tab().active = i;
    for (const p of E.panes) { p.el.classList.toggle('active', p.idx === i); if (E.dual) p.render(); }
    E.renderAddr(); E.syncTree(); E.updatePreview();
  };
  const narrow = () => matchMedia('(max-width:820px)').matches;             // phone / narrow window: one pane, no preview
  matchMedia('(max-width:820px)').addEventListener('change', () => { if (E.panes.length) { E.applyLayout(); E.renderAddr(); } });
  E.applyLayout = function () {
    E.panes[1].el.style.display = E.dual ? '' : 'none';
    E.btnDual.classList.toggle('on', E.dual); E.btnPrev.classList.toggle('on', E.preview); E.btnView.textContent = E.view === 'grid' ? '☰' : '▦';
    E.btnDual.style.display = E.btnPrev.style.display = narrow() ? 'none' : '';
    E.prevEl.style.display = E.preview ? '' : 'none';
    if (!E.dual || narrow()) E.active = 0;                                     // the second pane is hidden there: never act on it
    for (const p of E.panes) p.el.classList.toggle('active', E.dual && p.idx === E.active);
  };
  E.setDual = function (on) { E.dual = on; E.applyLayout(); if (on) E.panes[1].load(); saveTabs(); E.renderAddr(); };
  E.setPreview = function (on) { E.preview = on; E.applyLayout(); E.updatePreview(); saveTabs(); };
  E.setView = function (v) { E.view = v; E.applyLayout(); for (const p of E.visiblePanes()) p.render(); saveTabs(); };
  E.toOther = function (kind) {
    const p = E.cur(), o = E.otherPane(p); const sel = p.selected();
    if (!o || !o.path || !sel.length) { HZ.toast('另一個窗格要先開一個資料夾'); return; }
    HZ.queueAdd(kind, sel.map(x => x.path), o.path);
  };

  /* ---------------- tabs */
  E.renderTabs = function () {
    E.tabsEl.innerHTML = '';
    E.tabs.forEach((t, i) => {
      const p = t.panes[t.active || 0].path;
      const isHot = (HZ.hotFolders || []).some(f => p && HZ.isUnder(p, f.path));
      const el = h('div', {class: 'xtab' + (i === E.ti ? ' on' : '') + (isHot ? ' hotflag' : ''), title: p || '本機', 'data-drop': p || null},
        h('span', {class: 'ell', text: (isHot ? '🔥 ' : '') + (p ? HZ.base(p) || p : '本機')}),
        E.tabs.length > 1 ? h('span', {class: 'x', text: '✕', onclick: e => { e.stopPropagation(); E.closeTab(i); }}) : null);
      el.onclick = () => E.switchTab(i);
      el.onauxclick = e => { if (e.button === 1) E.closeTab(i); };
      E.tabsEl.append(el);
    });
    E.tabsEl.append(h('button', {class: 'ghost sm', title: '新分頁 (Ctrl+T)', onclick: () => E.newTab(E.cur().path)}, '＋'));
    E.renderAddr(); E.updateHotBtn();
  };
  E.switchTab = function (i) {
    if (i === E.ti) return; E.ti = i; E.active = E.dual ? (tab().active || 0) : 0;
    E.applyLayout();
    for (const p of E.visiblePanes()) { if (p.s.data) p.render(); p.load(null, true); }
    E.renderTabs(); E.syncTree(); saveTabs();
  };
  E.newTab = function (path) {
    E.tabs.splice(E.ti + 1, 0, {id: uid++, active: 0, panes: [newPaneState(path || ''), newPaneState(E.panes[1] ? E.panes[1].s.path : '')]});
    E.switchTab(E.ti + 1);
  };
  E.closeTab = function (i) {
    if (E.tabs.length <= 1) return;
    E.tabs.splice(i, 1);
    if (E.ti >= E.tabs.length || i < E.ti) E.ti = Math.max(0, E.ti - (i <= E.ti ? 1 : 0));
    E.ti = Math.min(E.ti, E.tabs.length - 1);
    E.active = E.dual ? (tab().active || 0) : 0;
    for (const p of E.visiblePanes()) p.load(null, true);
    E.renderTabs(); saveTabs();
  };

  /* ---------------- address bar */
  E.renderAddr = function () {
    const p = E.cur(), s = p.s; E.addr.innerHTML = '';
    const cr = h('div', {class: 'crumbs'});
    cr.append(h('span', {class: 'crumb', text: '💻 本機', onclick: e => { e.stopPropagation(); p.nav(''); }}));
    for (const c of (s.data && s.data.crumbs) || []) {
      cr.append(h('span', {class: 'sep', text: '›'}));
      cr.append(h('span', {class: 'crumb', text: c.name, 'data-drop': c.path, onclick: e => { e.stopPropagation(); p.nav(c.path); }}));
    }
    cr.onclick = () => E.editAddr();
    E.addr.append(cr);
    requestAnimationFrame(() => { cr.scrollLeft = cr.scrollWidth; });   // long paths: the current folder stays visible
    E.updateHotBtn();
  };
  E.editAddr = function () {
    const p = E.cur(); E.addr.innerHTML = '';
    const inp = h('input', {value: p.path, placeholder: '輸入路徑，例如 K:\\Work'});
    const done = go => { if (go && inp.value.trim()) p.nav(inp.value.trim().replace(/^"|"$/g, '')); else E.renderAddr(); };
    inp.onkeydown = e => { if (e.key === 'Enter') done(true); if (e.key === 'Escape') done(false); };
    inp.onblur = () => setTimeout(() => done(false), 100);
    E.addr.append(inp); inp.focus(); inp.select();
  };
  E.updateHotBtn = function () {
    if (!E.hotBtn) return;
    const p = E.cur(); const d = p.s.data || {};
    const sel = p.selected(); const tgt = sel.length === 1 && sel[0].dir ? sel[0] : null;
    if (tgt) { E.hotBtn.textContent = tgt.hot ? '🧊 取消熱處理' : '🔥 標記熱處理'; E.hotBtn.disabled = false; }
    else if (d.hot_root) { E.hotBtn.textContent = '🧊 取消熱處理'; E.hotBtn.disabled = false; }
    else { E.hotBtn.textContent = d.in_hot ? '🔥 在熱資料夾裡' : '🔥 標記熱處理'; E.hotBtn.disabled = !p.path || !!d.in_hot; }
  };
  E.hotToggle = function () {
    const p = E.cur(); const sel = p.selected(); const tgt = sel.length === 1 && sel[0].dir ? sel[0] : null;
    if (tgt) HZ.markHot(tgt.path, !tgt.hot);
    else if (p.s.data && p.s.data.hot_root) HZ.markHot(p.path, false);
    else if (p.path) HZ.markHot(p.path, true);
  };

  /* ---------------- tree (expandable folders, like the Windows Explorer navigation pane) */
  const key = p => String(p).toLowerCase();
  E.tOpen = new Map(); E.tKids = {}; E.tLoading = {};                 // key (lower case) -> real path
  try { for (const p of JSON.parse(localStorage.getItem('hz.treeopen') || '[]')) E.tOpen.set(key(p), p); } catch (e) { }
  const saveOpen = () => { try { localStorage.setItem('hz.treeopen', JSON.stringify([...E.tOpen.values()].slice(-300))); } catch (e) { } };
  E.loadKids = async function (path) {
    const k = key(path);
    if (E.tLoading[k]) return E.tLoading[k];
    E.tLoading[k] = HZ.get('/api/subdirs', {path}).then(r => { E.tKids[k] = r.dirs || []; }).catch(() => { E.tKids[k] = []; }).finally(() => { delete E.tLoading[k]; });
    return E.tLoading[k];
  };
  E.toggleNode = async function (path) {
    const k = key(path);
    if (E.tOpen.has(k)) E.tOpen.delete(k);
    else { E.tOpen.set(k, path); if (!E.tKids[k]) await E.loadKids(path); }
    saveOpen(); E.drawTree();
  };
  E.treeNode = function (path, label, depth, opts = {}) {
    const k = key(path), open = E.tOpen.has(k), kids = E.tKids[k];
    const arrow = h('span', {class: 'tw', style: {width: '14px', flex: 'none', textAlign: 'center', color: 'var(--subtext)', cursor: 'pointer'},
      text: kids && !kids.length ? '' : (open ? '▾' : '▸'), onclick: e => { e.stopPropagation(); E.toggleNode(path); }});
    const n = h('div', {class: 'tn', 'data-path': path, 'data-drop': path, title: opts.title || path, style: {paddingLeft: 4 + depth * 14 + 'px'},
      onclick: () => E.cur().nav(path), ondblclick: () => E.toggleNode(path),
      oncontextmenu: e => { e.preventDefault(); HZ.menu(e.clientX, e.clientY, HZ.itemMenu([{path, name: label, dir: true, hot: opts.hot}], {dir: path})); }},
      arrow, opts.icon ? h('span', {text: opts.icon}) : h('span', {html: HZ.icon({dir: true, hot: opts.hot})}), h('span', {class: 'ell', text: label}), opts.meta || null);
    const out = opts.out || [];                                     // one shared array: no spread (100k children overflowed the stack)
    out.push(n);
    if (open && kids) {
      const cur = key(E.cur().path || ''), MAX = 2000;
      let shown = 0;
      for (const c of kids) {
        const ck = key(c.path);
        if (shown >= MAX && !E.tOpen.has(ck) && !(cur === ck || cur.startsWith(ck.replace(/[\\/]$/, '') + '\\') || cur.startsWith(ck.replace(/[\\/]$/, '') + '/'))) continue;
        shown++; E.treeNode(c.path, c.name, depth + 1, {hot: c.hot, out});
      }
      if (kids.length > shown) out.push(h('div', {class: 'tn small muted', style: {paddingLeft: 18 + (depth + 1) * 14 + 'px'},
        text: `…還有 ${(kids.length - shown).toLocaleString()} 個資料夾（在右邊清單裡看）`, onclick: () => E.cur().nav(path)}));
    }
    return out;
  };
  const appendAll = (parent, nodes) => { const f = document.createDocumentFragment(); for (const x of nodes) f.appendChild(x); parent.appendChild(f); };
  E.drawTree = function () {
    const d = E.treeData; if (!d) return;
    const st = E.tree.scrollTop; E.tree.innerHTML = '';
    E.tree.append(h('div', {class: 'grp', text: '本機'}));
    for (const v of d.vols || []) {
      if (v.type === 'cdrom' && !v.ok) continue;
      const root = /^[A-Z]:$/.test(v.letter) ? v.letter + '\\' : v.letter;
      const used = v.total ? (v.total - v.free) / v.total * 100 : 0;
      appendAll(E.tree, E.treeNode(root, `${v.letter} ${v.label || ''}`, 0, {icon: '💽', title: `${v.label || ''} ${v.fs}　可用 ${HZ.fmtSize(v.free)} / ${HZ.fmtSize(v.total)}`,
        meta: h('span', {class: 'meta'}, h('span', {class: 'bar dbar'}, h('i', {class: used > 92 ? 'bad' : used > 80 ? 'warn' : '', style: {width: used + '%'}})))}));
    }
    E.tree.append(h('div', {class: 'grp', html: '🔥 熱處理'}));
    if (!(d.hot || []).length) E.tree.append(h('div', {class: 'small muted', style: {padding: '2px 10px'}, text: '對資料夾按右鍵標記'}));
    for (const f of d.hot || []) appendAll(E.tree, E.treeNode(f.path, HZ.base(f.path), 0, {hot: true, meta: h('span', {class: 'meta', text: HZ.drive(f.path)})}));
    E.tree.append(h('div', {class: 'grp', text: '⭐ 我的最愛'}));
    if (!(d.fav || []).length) E.tree.append(h('div', {class: 'small muted', style: {padding: '2px 10px'}, text: '對資料夾按右鍵加入'}));
    for (const f of d.fav || []) appendAll(E.tree, E.treeNode(f, HZ.base(f) || f, 0, {}));
    E.tree.scrollTop = st;
    E.syncTree(false);
  };
  E.renderTree = async function () {
    let d;
    try { d = await HZ.get('/api/ls', {path: ''}); } catch (e) { return; }
    HZ.vols = d.vols; HZ.favs = d.fav; HZ.hotFolders = d.hot; E.treeData = d;
    await Promise.all([...E.tOpen.entries()].map(([k, p]) => E.tKids[k] ? null : E.loadKids(p)));
    E.drawTree();
  };
  /* reveal: open every parent of the current folder in the tree (only under the drive section) */
  E.revealInTree = async function (path) {
    if (!path || !E.treeData) return;
    const roots = (E.treeData.vols || []).map(v => /^[A-Z]:$/.test(v.letter) ? v.letter + '\\' : v.letter);
    const chain = []; let p = path;
    for (let i = 0; i < 64 && p; i++) {
      chain.unshift(p);
      if (roots.some(r => key(r) === key(p))) break;
      const up = HZ.dir(p); if (!up || key(up) === key(p)) break; p = up;
    }
    if (!roots.some(r => key(r) === key(chain[0]))) return;
    let changed = false;
    for (const c of chain.slice(0, -1)) {
      if (!E.tOpen.has(key(c))) { E.tOpen.set(key(c), c); changed = true; }
      if (!E.tKids[key(c)]) { await E.loadKids(c); changed = true; }
    }
    if (changed) saveOpen();
    const here = key(path), drawn = () => [...E.tree.querySelectorAll('.tn')].some(n => key(n.dataset.path || '') === here);
    if (changed || !drawn()) E.drawTree();                         // past the first 2000 children: draw it in
    E.syncTree(true);
  };
  E.syncTree = function (scroll) {
    const p = key(E.cur().path || ''); let on = null;
    for (const n of E.tree.querySelectorAll('.tn')) { const m = !!p && p === key(n.dataset.path || ''); n.classList.toggle('on', m); if (m && !on) on = n; }
    if (scroll && on) on.scrollIntoView({block: 'nearest'});
  };
  E.refreshTreeKids = function (path) {             // a folder changed: reload its children if they are shown
    const k = key(path); if (E.tKids[k]) E.loadKids(path).then(E.drawTree);
  };

  /* ---------------- preview pane */
  E.updatePreview = HZ.debounce(async function () {
    if (!E.preview) return;
    const sel = E.cur().selected(); const it = sel.length === 1 ? sel[0] : null;
    E.prevEl.innerHTML = '';
    if (!it) { E.prevEl.append(h('div', {class: 'pv muted', text: sel.length ? `已選 ${sel.length} 個項目` : '選一個檔案來預覽'})); return; }
    const head = h('div', {style: {padding: '10px', borderBottom: '1px solid var(--border)'}}, h('div', {class: 'row'}, h('span', {html: HZ.icon(it)}), h('b', {class: 'ell', text: it.name})),
      h('div', {class: 'small muted', text: `${HZ.typeLabel(it)}　${it.size >= 0 ? HZ.fmtSize(it.size) : ''}　${HZ.fmtDate(it.mtime)}`}));
    const pv = h('div', {class: 'pv'});
    E.prevEl.append(head, pv);
    if (it.dir) {
      pv.append(h('div', {class: 'muted small', text: it.files != null ? `${(+it.files).toLocaleString()} 個檔案　${HZ.fmtSize(it.size)}` : '資料夾'}));
      pv.append(h('button', {class: 'sm', style: {marginTop: '8px'}, onclick: () => { HZ.go('space'); HZ.pages.space.load(it.path); }}, '📊 分析空間'));
      return;
    }
    const url = HZ.fileUrl(it.path), k = HZ.kind(it.ext);
    if (k === 'image') pv.append(h('img', {src: url}));
    else if (k === 'video') pv.append(h('video', {src: url, controls: true, preload: 'metadata'}));
    else if (k === 'audio') pv.append(h('audio', {src: url, controls: true, style: {width: '100%'}}));
    else if (it.ext === 'pdf') { pv.style.padding = '0'; pv.append(h('iframe', {src: url})); }
    else {
      try {
        const p = await HZ.get('/api/preview', {path: it.path});
        if (p.kind === 'text') pv.append(h('pre', {text: p.text}));
        else pv.append(h('div', {class: 'muted', text: '無法預覽這種檔案'}));
      } catch (e) { pv.append(h('div', {class: 'bad', text: e.message})); }
    }
    const lay = h('div', {class: 'small', style: {padding: '8px 10px', borderTop: '1px solid var(--border)'}}, h('button', {class: 'sm', onclick: async () => {
      try {
        const L = await HZ.get('/api/hot/layout', {path: it.path});
        lay.innerHTML = L.resident ? '檔案很小，存在 MFT 裡' : `硬碟位置：起點 ${L.start_pct}%（0% = 最外圈）、${L.fragments} 段${L.inside_pct != null ? `、<b class="hot">外圈熱區 ${L.inside_pct}%</b>` : ''}<div class="locbar"><i style="left:${L.start_pct}%"></i></div>`;
      } catch (e) { lay.textContent = e.message; }
    }}, '📍 查看在硬碟上的位置'));
    E.prevEl.append(lay);
  }, 150);

  /* ---------------- new folder / file */
  E.newFolder = async function () {
    const p = E.cur(); if (!p.path) return;
    const n = await HZ.prompt('新增資料夾', p.path, '新增資料夾'); if (!n) return;
    try { const r = await HZ.post('/api/op', {op: 'mkdir', path: p.path, name: n}); await p.load(HZ.base(r.path)); } catch (e) { HZ.err(e); }
  };
  E.newFile = async function () {
    const p = E.cur(); if (!p.path) return;
    const n = await HZ.prompt('新增文字檔', p.path, '新增文字文件.txt'); if (!n) return;
    try { const r = await HZ.post('/api/op', {op: 'newfile', path: p.path, name: n}); await p.load(HZ.base(r.path)); } catch (e) { HZ.err(e); }
  };

  /* ---------------- public */
  E.open = function (path, selectName) {
    if (!E.root) { HZ.go('explorer'); }
    E.cur().nav(path, selectName);
  };
  E.onShow = function () {
    for (const p of E.visiblePanes()) p.load(null, true);
    HZ.every('explorer', 4000, () => { for (const p of E.visiblePanes()) if (p.path && (p.s.items || []).length < 20000) p.load(null, true); });
  };
  E.onHide = () => HZ.stop('explorer');
  E.onBack = function () {                                              // phone back button
    const p = E.cur(); if (!p) return false;
    if (p.s.hi > 0) { p.back(); return true; }
    if (p.path) { p.up(); return true; }
    return false;
  };
  E.onFsChange = function () {
    if (!E.root) return;
    for (const p of E.visiblePanes()) { p.load(null, true); if (p.path) E.refreshTreeKids(p.path); }
    E.renderTree(); E.renderTabs();
  };
  window.addEventListener('resize', HZ.debounce(() => { if (E.root) for (const p of E.visiblePanes()) p.render(); }, 150));
  HZ.page('explorer', E);
})();

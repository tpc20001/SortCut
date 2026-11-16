/* HotZone FM — 空間分析 (TreeSize style: size tree + treemap + largest files / types) */
'use strict';
(function () {
  const {h, esc} = HZ;
  const P = {title: '空間分析', path: '', node: null, open: {}, kids: {}, tm: null, hover: null, btab: 'files'};
  const PALETTE = [205, 28, 140, 265, 350, 175, 50, 300, 95, 230, 10, 320];

  P.build = function (root) {
    P.inp = h('input', {style: {flex: '1', minWidth: '240px'}, placeholder: '資料夾或磁碟，例如 K:\\'});
    P.inp.onkeydown = e => { if (e.key === 'Enter') P.load(P.inp.value.trim()); };
    P.drv = h('div', {class: 'row wrap'});
    P.src = h('span', {class: 'small muted'});
    const top = h('div', {class: 'sbox'}, h('button', {class: 'ghost', title: '上一層', onclick: () => P.path && P.load(HZ.dir(P.path) || P.path)}, '▲'), P.inp,
      h('button', {onclick: () => P.load(P.inp.value.trim())}, '分析'), h('button', {class: 'ghost', title: '重新掃描（沒有索引的位置）', onclick: () => P.load(P.path, true)}, '⟳'),
      h('button', {class: 'ghost', title: '把目前展開的資料夾大小存成 CSV（Excel 可以開）', onclick: () => P.exportCsv()}, '⬇ CSV'), P.drv, P.src);
    P.tree = h('div', {class: 'stree'});
    P.canvas = h('canvas');
    P.tmbox = h('div', {class: 'tm'}, P.canvas);
    P.tmhead = h('div', {class: 'phead'});
    P.btabs = h('div', {class: 'tabs'});
    P.bbody = h('div', {class: 'body'});
    for (const [k, t] of [['files', '最大的檔案'], ['dirs', '最大的資料夾'], ['exts', '依類型'], ['ages', '依修改時間']]) P.btabs.append(h('span', {class: 'tabbtn' + (k === P.btab ? ' on' : ''), 'data-k': k, text: t, onclick: () => { P.btab = k; for (const c of P.btabs.children) c.classList.toggle('on', c.dataset.k === k); P.loadBottom(); }}));
    root.append(top, h('div', {class: 'spacewrap'}, P.tree, h('div', {class: 'tmwrap'}, P.tmhead, P.tmbox, h('div', {class: 'sbottom'}, P.btabs, P.bbody))));
    P.canvas.addEventListener('mousemove', P.move);
    P.canvas.addEventListener('mouseleave', () => { P.hover = null; HZ.tip(null); P.draw(); });
    P.canvas.addEventListener('click', e => { const r = P.hit(e); if (r && r.it.dir && r.it.path) P.load(r.it.path); });
    P.canvas.addEventListener('contextmenu', e => { e.preventDefault(); const r = P.hit(e); if (r && r.it.path) HZ.menu(e.clientX, e.clientY, HZ.itemMenu([r.it], {})); });
    new ResizeObserver(() => P.draw()).observe(P.tmbox);
  };
  P.drives = function () {
    P.drv.innerHTML = '';
    for (const v of HZ.vols || []) if (v.ok && v.type !== 'cdrom') {
      const r = /^[A-Z]:$/.test(v.letter) ? v.letter + '\\' : v.letter;
      P.drv.append(h('button', {class: 'sm' + (P.path === r ? ' on' : ''), onclick: () => P.load(r)}, v.letter));
    }
  };
  P.load = async function (path, rescan) {
    P.vaultSize = 0;
    if (/^[A-Za-z]:\\?$|^\/$/.test(path || '')) HZ.get('/api/vault/size', {path}).then(r => { P.vaultSize = r.size || 0; P.draw(); }).catch(() => { });
    if (!path) return;
    P.path = path; P.inp.value = path; P.drives();
    P.tree.innerHTML = '<div class="empty">讀取中…</div>';
    let n;
    for (let tries = 0; tries < 1200; tries++) {
      try { n = await HZ.get('/api/tree', {path, depth: 2, max: 120, rescan: rescan && tries === 0 ? '1' : '0'}); }
      catch (e) { P.tree.innerHTML = `<div class="empty bad">${esc(e.message)}</div>`; return; }
      if (P.path !== path) return;
      if (!n.scanning) break;
      if (n.state === 'error') { P.tree.innerHTML = `<div class="empty bad">掃描失敗：${esc(n.msg || '')}<br><span class="small muted">按 ⟳ 重新掃描</span></div>`; return; }
      P.tree.innerHTML = `<div class="empty">📂 這個位置沒有在索引裡，正在掃描…<br><span class="small">${esc(n.msg || '')}</span></div>`;
      await new Promise(r => setTimeout(r, 700));
    }
    if (!n || n.scanning) return;
    P.node = n; P.kids = {}; P.kids[n.path] = n; P.open = {[n.path]: true};
    P.src.textContent = n.source === 'index' ? '⚡ 資料來源：索引（即時）' : `📂 掃描結果（${HZ.fmtAgo(n.built)}）`;
    P.renderTree(); P.draw(); P.loadBottom();
  };

  /* ---------------- tree table */
  P.renderTree = function () {
    const out = [];
    const walk = (node, depth, parentSize) => {
      out.push(P.row(node, depth, parentSize));
      if (node.dir && P.open[node.path] && node.children) {
        for (const c of node.children) walk(P.kids[c.path] || c, depth + 1, node.size);
        if (node.others) out.push(h('div', {class: 'srow', style: {paddingLeft: (depth + 1) * 14 + 'px'}}, h('div', {class: 'n muted', text: `… 其他 ${node.others.count} 個項目`}), h('div', {class: 'num muted', text: HZ.fmtSize(node.others.size)}), h('div'), h('div')));
      }
    };
    walk(P.node, 0, P.node.size);
    P.tree.innerHTML = '';
    P.tree.append(h('div', {class: 'srow', style: {position: 'sticky', top: '0', background: 'var(--header_bg)', color: 'var(--header_text)', cursor: 'default', zIndex: 1}},
      h('div', {class: 'n', style: {paddingLeft: '8px'}, text: '名稱'}), h('div', {class: 'num', text: '大小'}), h('div', {text: '佔上一層'}), h('div', {class: 'num', text: '檔案數'})));
    P.tree.append(...out);
  };
  P.row = function (node, depth, parentSize) {
    const pct = parentSize ? node.size / parentSize * 100 : 100;
    const tw = node.dir ? (P.open[node.path] ? '▾' : '▸') : '';
    const r = h('div', {class: 'srow' + (P.sel === node.path ? ' on' : '')},
      h('div', {class: 'n', style: {paddingLeft: 4 + depth * 14 + 'px'}}, h('span', {class: 'tw', text: tw}), h('span', {html: HZ.icon({dir: node.dir, ext: (node.name.split('.').pop() || '').toLowerCase()})}), h('span', {class: 'ell', text: depth === 0 ? node.path : node.name}),
        node.unreadable ? h('span', {class: 'pill bad', title: '沒有權限讀取（或讀到一半失敗）：裡面的大小不知道，實際會比顯示的大', text: '⚠ 讀不到'}) : null),
      h('div', {class: 'num', text: HZ.fmtSize(node.size)}),
      h('div', {class: 'row', style: {gap: '4px'}}, h('div', {class: 'bar', style: {flex: '1'}}, h('i', {class: depth === 0 ? '' : 'hot', style: {width: pct + '%'}})), h('span', {class: 'small muted', style: {width: '38px', textAlign: 'right'}, text: pct.toFixed(pct < 10 ? 1 : 0) + '%'})),
      h('div', {class: 'num small muted', text: node.dir ? (node.files || 0).toLocaleString() : ''}));
    r.onclick = async e => {
      P.sel = node.path;
      if (node.dir && e.target.closest('.tw')) await P.toggle(node);
      P.renderTree();
    };
    r.ondblclick = () => node.dir ? P.load(node.path) : HZ.openItem(node);
    r.oncontextmenu = e => { e.preventDefault(); HZ.menu(e.clientX, e.clientY, HZ.itemMenu([node], {})); };
    return r;
  };
  P.toggle = async function (node) {
    if (P.open[node.path]) { delete P.open[node.path]; return; }
    if (!P.kids[node.path] || !P.kids[node.path].children || P.kids[node.path].children.some(c => c.dir && !c.children && c.nchildren !== 0)) {
      try { const n = await HZ.get('/api/tree', {path: node.path, depth: 1, max: 200}); if (!n.scanning) { P.kids[node.path] = n; Object.assign(node, {children: n.children, others: n.others}); } } catch (e) { HZ.err(e); }
    }
    P.open[node.path] = true;
  };

  /* ---------------- treemap */
  function squarify(items, x, y, w, h, out) {
    const total = items.reduce((a, b) => a + b.v, 0); if (!total || w < 1 || h < 1) return;
    const scale = w * h / total; let row = [], rest = items.slice();
    const worst = (r, s) => { const sum = r.reduce((a, b) => a + b.v, 0) * scale; let mx = 0, mn = Infinity; for (const q of r) { const a = q.v * scale; mx = Math.max(mx, a); mn = Math.min(mn, a); } return Math.max(s * s * mx / (sum * sum), sum * sum / (s * s * mn)); };
    const lay = r => {
      const sum = r.reduce((a, b) => a + b.v, 0) * scale;
      if (w >= h) { const rw = sum / h; let cy = y; for (const q of r) { const rh = q.v * scale / rw; out.push({it: q.it, x, y: cy, w: rw, h: rh, d: q.d, hue: q.hue}); cy += rh; } x += rw; w -= rw; }
      else { const rh = sum / w; let cx = x; for (const q of r) { const ww = q.v * scale / rh; out.push({it: q.it, x: cx, y, w: ww, h: rh, d: q.d, hue: q.hue}); cx += ww; } y += rh; h -= rh; }
    };
    while (rest.length) {
      const s = Math.min(w, h), c = rest[0];
      if (!row.length || worst(row.concat([c]), s) <= worst(row, s)) { row.push(c); rest.shift(); }
      else { lay(row); row = []; }
    }
    if (row.length) lay(row);
  }
  P.layout = function (W, H) {
    const rects = [];
    const kidsOf = n => { const a = (n.children || []).filter(c => c.size > 0).map(c => ({v: c.size, it: c})); if (n.others && n.others.size > 0) a.push({v: n.others.size, it: {name: `其他 ${n.others.count} 個項目`, size: n.others.size, other: true}}); return a; };
    const top = kidsOf(P.node); top.forEach((q, i) => { q.hue = PALETTE[i % PALETTE.length]; q.d = 1; });
    const lvl1 = []; squarify(top, 0, 0, W, H, lvl1);
    for (const r of lvl1) {
      rects.push(r);
      if (r.it.dir && r.it.children && r.w > 40 && r.h > 34) {
        const inner = kidsOf(r.it).map(q => Object.assign(q, {hue: r.hue, d: 2}));
        squarify(inner, r.x + 3, r.y + 17, r.w - 6, r.h - 20, rects);
      }
    }
    return rects;
  };
  P.draw = function () {
    const c = P.canvas, box = P.tmbox.getBoundingClientRect();
    const dpr = devicePixelRatio || 1; c.width = Math.max(1, box.width * dpr); c.height = Math.max(1, box.height * dpr);
    const g = c.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, box.width, box.height);
    if (!P.node) { P.tmhead.innerHTML = '<span class="muted">選一個磁碟或資料夾開始分析</span>'; return; }
    P.tmhead.innerHTML = `<span class="ptitle ell">${esc(P.node.path)}</span><span class="grow"></span>` +
      (P.vaultSize ? `<span class="pill" title="保管區（.HotZoneVault，隱藏資料夾）目前佔用的空間；到「保管區」頁面可以清理" style="cursor:pointer" onclick="HZ.go('vault')">🛟 保管區佔 ${HZ.fmtSize(P.vaultSize)}</span>` : '') +
      (P.node.bad_n ? `<span class="pill bad" title="沒有權限讀取的資料夾：大小沒有算進去">⚠ ${P.node.bad_n} 個資料夾讀不到</span>` : '') +
      `<span>${HZ.fmtSize(P.node.size)}　${(P.node.files || 0).toLocaleString()} 個檔案</span>`;
    P.rects = P.layout(box.width, box.height);
    const dark = document.documentElement.dataset.theme !== 'light';
    g.font = '12px "Yu Gothic UI","Microsoft JhengHei",sans-serif'; g.textBaseline = 'top';
    for (const r of P.rects) {
      const it = r.it, hov = P.hover === r;
      const k = it.dir ? null : HZ.kind((it.name || '').split('.').pop());
      const L = r.d === 1 ? (dark ? 30 : 72) : (dark ? 40 + (it.dir ? 0 : 6) : 80 - (it.dir ? 0 : 6));
      g.fillStyle = it.other ? (dark ? '#2a3038' : '#dfe5ec') : `hsl(${r.hue},${it.dir ? 45 : 30}%,${hov ? L + 10 : L}%)`;
      g.fillRect(r.x, r.y, r.w, r.h);
      g.strokeStyle = dark ? '#0e1116' : '#fff'; g.lineWidth = r.d === 1 ? 2 : 1; g.strokeRect(r.x + .5, r.y + .5, r.w - 1, r.h - 1);
      if (!it.dir && k && k !== 'file' && r.w > 8 && r.h > 8) { g.fillStyle = 'rgba(255,255,255,.08)'; g.fillRect(r.x + 1, r.y + r.h - 3, r.w - 2, 2); }
      if (r.w > 46 && r.h > 15) {
        g.fillStyle = dark ? '#e8ecf2' : '#1b2430'; g.save(); g.beginPath(); g.rect(r.x + 3, r.y, r.w - 6, r.h); g.clip();
        g.font = (r.d === 1 ? 'bold ' : '') + '12px "Yu Gothic UI","Microsoft JhengHei",sans-serif';
        g.fillText(`${it.dir ? '' : ''}${it.name}  ${HZ.fmtSize(it.size)}`, r.x + 4, r.y + 3); g.restore();
      }
    }
  };
  P.hit = function (e) {
    const b = P.canvas.getBoundingClientRect(), x = e.clientX - b.left, y = e.clientY - b.top; let best = null;
    for (const r of P.rects || []) if (x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h) best = r;
    return best;
  };
  P.move = function (e) {
    const r = P.hit(e);
    if (r !== P.hover) { P.hover = r; P.draw(); }
    if (!r) { HZ.tip(null); return; }
    const pct = P.node.size ? r.it.size / P.node.size * 100 : 0;
    HZ.tip(e, `<b>${esc(r.it.name)}</b><br>${HZ.fmtSize(r.it.size)}（${pct.toFixed(1)}%）${r.it.dir ? '　' + (r.it.files || 0).toLocaleString() + ' 個檔案' : ''}<br><span class="muted small">${esc(r.it.path || '')}</span>${r.it.dir ? '<br><span class="small">點一下進入</span>' : ''}`);
  };

  /* ---------------- bottom lists */
  P.loadBottom = async function () {
    if (!P.path) return;
    P.bbody.innerHTML = '<div class="empty">讀取中…</div>';
    try {
      if (P.btab === 'ages') {
        const r = await HZ.get('/api/ages', {path: P.path});
        const tot = r.buckets.reduce((a, x) => a + x[1], 0) || 1, maxY = Math.max(1, ...r.years.map(x => x[1]));
        const row = (lab, sz, n, w) => `<tr><td>${esc(String(lab))}</td><td class="num">${HZ.fmtSize(sz)}</td><td><div class="row"><div class="bar" style="flex:1"><i class="hot" style="width:${w}%"></i></div><span class="small" style="width:44px;text-align:right">${(sz / tot * 100).toFixed(1)}%</span></div></td><td class="num">${n.toLocaleString()}</td></tr>`;
        P.bbody.innerHTML = `<div class="small muted" style="padding:6px 8px">很久沒修改的大檔案就是「冷資料」：熱處理需要空間時，會優先把它們移到內圈。</div>` +
          `<table class="t"><tr><th>最後修改</th><th class="num">大小</th><th>比例</th><th class="num">檔案數</th></tr>${r.buckets.filter(x => x[2]).map(x => row(x[0], x[1], x[2], x[1] / tot * 100)).join('')}</table>` +
          (r.years.length ? `<h3 style="margin:10px 8px 4px">依年份</h3><table class="t"><tr><th>年份</th><th class="num">大小</th><th>比例</th><th class="num">檔案數</th></tr>${r.years.map(x => row(x[0], x[1], x[2], x[1] / maxY * 100)).join('')}</table>` : '');
      } else if (P.btab === 'exts') {
        const r = await HZ.get('/api/exts', {path: P.path}); const tot = r.rows.reduce((a, x) => a + x[1], 0) || 1;
        P.bbody.innerHTML = `<table class="t"><tr><th>類型</th><th class="num">大小</th><th>比例</th><th class="num">檔案數</th></tr>` +
          r.rows.map(x => `<tr><td>${HZ.icon({ext: x[0]})}</td><td class="num">${HZ.fmtSize(x[1])}</td><td><div class="row"><div class="bar" style="flex:1"><i class="hot" style="width:${x[1] / tot * 100}%"></i></div><span class="small" style="width:44px;text-align:right">${(x[1] / tot * 100).toFixed(1)}%</span></div></td><td class="num">${x[2].toLocaleString()}</td></tr>`).join('') + '</table>';
        P.bbody.querySelectorAll('td:first-child').forEach((td, i) => { td.innerHTML = `<div class="row">${td.innerHTML}<span>${esc(r.rows[i][0])}</span></div>`; });
      } else {
        const r = await HZ.get('/api/largest', {path: P.path, n: 200, dirs: P.btab === 'dirs' ? '1' : '0'});
        const t = h('table', {class: 't'}, h('tr', {}, h('th', {text: '名稱'}), h('th', {class: 'num', text: '大小'}), h('th', {text: '位置'}), h('th', {text: '修改日期'})));
        for (const it of r.items) {
          it.ext = it.dir ? '' : (it.name.split('.').pop() || '').toLowerCase();
          const tr = h('tr', {style: {cursor: 'default'}}, h('td', {}, h('div', {class: 'row'}, h('span', {html: HZ.icon(it)}), h('span', {class: 'ell', text: it.name}))),
            h('td', {class: 'num', text: HZ.fmtSize(it.size)}), h('td', {class: 'muted ell', style: {maxWidth: '360px'}, text: HZ.dir(it.path)}), h('td', {class: 'muted', text: HZ.fmtDate(it.mtime)}));
          tr.ondblclick = () => HZ.openItem(it);
          tr.oncontextmenu = e => { e.preventDefault(); HZ.menu(e.clientX, e.clientY, HZ.itemMenu([it], {})); };
          t.append(tr);
        }
        P.bbody.innerHTML = ''; P.bbody.append(r.items.length ? t : h('div', {class: 'empty', text: '沒有資料'}));
      }
    } catch (e) { P.bbody.innerHTML = `<div class="empty bad">${esc(e.message)}</div>`; }
  };
  /* TreeSize-style report: every folder / file shown in the tree (opened levels) with size, files and date */
  P.exportCsv = function () {
    if (!P.node) { HZ.toast('先分析一個資料夾'); return; }
    const rows = [['路徑', '類型', '大小（位元組）', '大小', '檔案數', '修改日期', '佔上層比例']];
    const walk = (n, parentSize, depth) => {
      rows.push([n.path, n.dir ? '資料夾' : '檔案', n.size, HZ.fmtSize(n.size), n.files || '', HZ.fmtDate(n.mtime), parentSize ? (n.size / parentSize * 100).toFixed(1) + '%' : '']);
      const full = P.kids[n.path] || n;
      if (depth < 12 && full.children && (depth === 0 || P.open[n.path])) {
        for (const c of full.children) walk(P.kids[c.path] || c, n.size, depth + 1);
        if (full.others) rows.push([`${n.path}${n.path.endsWith('\\') || n.path.endsWith('/') ? '' : (n.path.includes('\\') ? '\\' : '/')}（其他 ${full.others.count} 個項目）`, '其他', full.others.size,
          HZ.fmtSize(full.others.size), '', '', n.size ? (full.others.size / n.size * 100).toFixed(1) + '%' : '']);   // (the sums add up)
      }
      if (n.unreadable) rows[rows.length - 1][1] += '（讀不到，大小不完整）';
    };
    walk(P.node, 0, 0);
    const q = v => { v = String(v ?? ''); if (/^[=+\-@\t]/.test(v) && isNaN(+v)) v = "'" + v;   // never a formula in Excel
      return /[",\r\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
    const csv = '\ufeff' + rows.map(r => r.map(q).join(',')).join('\r\n');
    const a = h('a', {href: URL.createObjectURL(new Blob([csv], {type: 'text/csv'})), download: `空間分析_${HZ.base(P.path) || 'drive'}_${new Date().toLocaleDateString('sv')}.csv`});
    document.body.append(a); a.click(); a.remove();
  };
  P.onShow = function () {
    P.drives();
    if (!P.path) { const v = (HZ.vols || []).find(v => v.ok && v.type === 'fixed'); if (v) P.load(/^[A-Z]:$/.test(v.letter) ? v.letter + '\\' : v.letter); }
    else P.draw();
  };
  HZ.page('space', P);
})();

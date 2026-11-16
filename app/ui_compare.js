/* HotZone FM — 資料夾同步 (compare two folders, then copy the differences through the queue) */
'use strict';
(function () {
  const {h, esc} = HZ;
  const C = {title: '資料夾同步', only: 'left,right,lnew,rnew,diff,err'};
  const LBL = {left: ['只在左邊', 'acc'], right: ['只在右邊', 'warn'], lnew: ['左邊比較新', 'ok'], rnew: ['右邊比較新', 'hot'], diff: ['時間一樣但大小不同', 'bad'], err: ['讀不到（被占用）', 'bad'], same: ['相同', 'muted']};
  let LS = 'hz.cmp.';

  C.build = function (root) {
    const saved = k => { try { return localStorage.getItem(LS + k) || ''; } catch (e) { return ''; } };
    C.a = h('input', {placeholder: '左邊資料夾（來源），例如 K:\\照片', value: saved('a'), style: {flex: '1', minWidth: '220px'}});
    C.b = h('input', {placeholder: '右邊資料夾（目標），例如 E:\\備份\\照片', value: saved('b'), style: {flex: '1', minWidth: '220px'}});
    const rer = HZ.debounce(() => C.render(), 250); C.a.oninput = rer; C.b.oninput = rer;
    C.content = h('input', {type: 'checkbox'});
    const pick = inp => HZ.bridge ? h('button', {class: 'sm', onclick: async () => { const p = await HZ.bcall('pickFolder'); if (p) inp.value = p; }}, '…') : null;
    C.status = h('span', {class: 'small muted'});
    C.counts = h('div', {class: 'chips'});
    C.acts = h('div', {class: 'row wrap'});
    C.list = h('div', {class: 'list'});
    root.append(h('div', {class: 'sbox', style: {flexDirection: 'column', alignItems: 'stretch'}},
      h('div', {class: 'small muted', html: `像 FastCopy 的「同步」：比較兩個資料夾，只複製不一樣的檔案。<b>不會直接覆蓋或刪除任何東西</b>：被取代的舊檔先進保管區；「鏡像」時目標多出來的檔案也是放進保管區（${HZ.vaultDays()} 天內可還原）。`}),
      h('div', {class: 'row wrap'}, h('b', {text: '左'}), C.a, pick(C.a), h('button', {class: 'sm', title: '左右對調（之後要重新比較）', onclick: () => { const t = C.a.value; C.a.value = C.b.value; C.b.value = t; C.render(); }}, '⇄'), h('b', {text: '右'}), C.b, pick(C.b)),
      h('div', {class: 'row wrap'}, h('label', {class: 'row small', title: '大小和時間一樣時再比對檔案內容（慢，但能找出內容被改過卻時間沒變的檔案）'}, C.content, '連內容一起比對（慢）'),
        h('button', {class: 'primary', onclick: () => C.start()}, '比較'), h('button', {onclick: () => HZ.post('/api/compare/cancel', {}).then(C.poll)}, '取消'), C.status)),
      h('div', {class: 'sbox'}, C.counts, h('span', {class: 'grow'}), C.acts), C.list);
  };
  C.start = async function () {
    const a = C.a.value.trim(), b = C.b.value.trim();
    try { localStorage.setItem(LS + 'a', a); localStorage.setItem(LS + 'b', b); } catch (e) { }
    try { await HZ.post('/api/compare/start', {a, b, content: C.content.checked}); } catch (e) { HZ.err(e); return; }
    C.poll();
  };
  C.poll = async function () {
    let d; try { d = await HZ.get('/api/compare', {only: C.only, limit: 3000}); } catch (e) { return; }
    C.d = d;
    C.status.textContent = d.msg || '';
    if (d.state === 'running') { HZ.every('compare', 700, async () => { const x = await HZ.get('/api/compare', {limit: 1}).catch(() => null); if (x) C.status.textContent = x.msg; if (!x || x.state !== 'running') { HZ.stop('compare'); C.poll(); } }); }
    C.render();
  };
  C.render = function () {
    const d = C.d || {}, c = d.counts || {};
    C.counts.innerHTML = ''; C.acts.innerHTML = ''; C.list.innerHTML = '';
    if (d.state !== 'done') { if (d.state === 'running') C.list.append(h('div', {class: 'empty', text: d.msg || '比較中…'})); return; }
    if (!C.a.value.trim() && !C.b.value.trim()) { C.a.value = d.a || ''; C.b.value = d.b || ''; }      // (phone: results of the PC's comparison)
    if (!C.samePaths(d)) {                                           // the fields no longer say what was compared: no sync buttons
      C.list.append(h('div', {class: 'empty', html: `上面的資料夾和上次比較的不一樣（上次：左 <b>${esc(d.a || '')}</b>、右 <b>${esc(d.b || '')}</b>）。<br>請按「比較」重新比較後再同步。`}));
      return;
    }
    if (d.bad_n) C.counts.append(h('span', {class: 'pill bad', title: [...(d.bad_a || []).map(x => '左：' + x), ...(d.bad_b || []).map(x => '右：' + x)].slice(0, 40).join('\n'),
      text: `⚠ ${d.bad_n} 個位置讀不到或是連結資料夾：鏡像時那些位置不會移除任何東西`}));
    for (const k of ['left', 'lnew', 'right', 'rnew', 'diff', 'err', 'same']) {
      if (k === 'err' && !c.err) continue;
      const on = C.only.split(',').includes(k);
      C.counts.append(h('span', {class: 'chip' + (on ? ' on' : ''), onclick: () => { const s = new Set(C.only.split(',').filter(Boolean)); s.has(k) ? s.delete(k) : s.add(k); C.only = [...s].join(','); C.poll(); }},
        h('span', {class: LBL[k][1], text: LBL[k][0]}), ` ${(c[k] || 0).toLocaleString()}`));
    }
    const n = (...ks) => ks.reduce((a, k) => a + (c[k] || 0), 0);
    C.acts.append(
      h('button', {class: 'primary', disabled: !n('left', 'lnew', 'diff'), onclick: () => C.sync('ab', false)}, `左 → 右 更新（${n('left', 'lnew', 'diff').toLocaleString()}）`),
      h('button', {disabled: !n('right', 'rnew', 'diff'), onclick: () => C.sync('ba', false)}, `右 → 左 更新（${n('right', 'rnew', 'diff').toLocaleString()}）`),
      h('button', {disabled: !n('left', 'lnew', 'right', 'rnew'), onclick: () => C.sync('both', false), title: '兩邊互補，比較新的那份贏；「時間一樣但大小不同」的不會動，請你自己決定'}, '雙向'),
      h('button', {disabled: !n('left', 'lnew', 'diff', 'right', 'rnew'), onclick: () => C.sync('ab', true), title: '右邊變得和左邊一模一樣：右邊比較新的也會被左邊的版本取代（舊的進保管區），右邊多出來的檔案放進右邊硬碟的保管區'}, '鏡像 左 → 右'));
    const rows = d.rows || [];
    if (!rows.length) { C.list.append(h('div', {class: 'empty', text: n('left', 'right', 'lnew', 'rnew', 'diff') ? '目前篩選沒有項目' : '兩邊完全相同 ✓'})); return; }
    C.list.append(h('div', {class: 'crow chdr'}, h('span', {text: '狀態'}), h('span', {text: '檔案'}), h('span', {class: 'num', text: '左邊'}), h('span', {class: 'num', text: '右邊'})));
    const side = x => x ? `${HZ.fmtSize(x[0])}　${HZ.fmtDate(x[1])}` : '—';
    for (const r of rows) {
      C.list.append(h('div', {class: 'crow', title: r.rel},
        h('span', {class: 'pill ' + LBL[r.s][1], text: LBL[r.s][0]}), h('span', {class: 'ell', text: r.rel}),
        h('span', {class: 'num small', text: side(r.la)}), h('span', {class: 'num small', text: side(r.lb)})));
    }
    if (d.total_rows > rows.length) C.list.append(h('div', {class: 'small muted', style: {padding: '8px'}, text: `只顯示前 ${rows.length.toLocaleString()} 筆（共 ${d.total_rows.toLocaleString()} 筆）；同步會處理全部。`}));
  };
  C.samePaths = d => {
    const n = x => String(x || '').trim().replace(/[\\/]+$/, '').toLowerCase();
    return n(C.a.value) === n(d.a) && n(C.b.value) === n(d.b);
  };
  C.sync = async function (dir, mirror) {
    const d = C.d || {}, c = d.counts || {};
    if (!C.samePaths(d)) { HZ.toast('資料夾改過了，請先重新比較', 'bad'); C.render(); return; }
    const src = dir === 'ba' ? d.b : d.a, dst = dir === 'ba' ? d.a : d.b;
    const older = mirror ? (c[dir === 'ab' ? 'rnew' : 'lnew'] || 0) : 0;
    const what = {ab: '左 → 右', ba: '右 → 左', both: '雙向'}[dir] + (mirror ? '（鏡像）' : '');
    const body = `<b>${what}</b><br>` + (dir === 'both' ? `左：<span class="mono">${esc(d.a)}</span><br>右：<span class="mono">${esc(d.b)}</span>` :
      `從：<span class="mono">${esc(src)}</span><br>到：<span class="mono">${esc(dst)}</span>`) + '<br><br>' + (dir === 'both' ? `複製只在一邊的和比較新的檔案到另一邊。` : `把${dir === 'ab' ? '左' : '右'}邊多的、比較新的檔案複製到${dir === 'ab' ? '右' : '左'}邊。`) +
      `<br>被取代的檔案會先放進保管區。` + (older ? `<br><span class="warn">注意：有 ${older.toLocaleString()} 個檔案是${dir === 'ab' ? '右' : '左'}邊比較新，鏡像會用比較舊的版本取代它們（新的進保管區）。</span>` : '') +
      (mirror ? `<br><span class="warn">鏡像：${dir === 'ab' ? '右' : '左'}邊多出來的 ${(c[dir === 'ab' ? 'right' : 'left'] || 0).toLocaleString()} 個檔案會放進保管區（${HZ.vaultDays()} 天內可還原）。</span>` : '');
    if (!await HZ.confirm('資料夾同步', body, '開始同步')) return;
    try {
      const r = await HZ.post('/api/compare/sync', {dir, mirror, a: d.a, b: d.b});
      HZ.toast(`已加入佇列：複製 ${r.copy.toLocaleString()} 個` + (r.vault ? `、放進保管區 ${r.vault.toLocaleString()} 個` : '') +
        (r.skipped_changed ? `<br><span class="warn">${r.skipped_changed.toLocaleString()} 個檔案在比較之後又被改過，這次沒有動它們，請再比較一次</span>` : '') +
        (r.skipped_unreadable ? `<br><span class="warn">${r.skipped_unreadable.toLocaleString()} 個檔案在來源讀不到的位置底下，鏡像沒有移除它們</span>` : ''), r.skipped_changed || r.skipped_unreadable ? 'warn' : 'ok', 6000);
    } catch (e) { HZ.err(e); }
  };
  C.onShow = () => C.poll();
  C.onHide = () => HZ.stop('compare');
  HZ.page('compare', C);
})();

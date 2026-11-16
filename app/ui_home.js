/* HotZone FM — 總覽: everything at a glance (made for checking from a phone) */
'use strict';
(function () {
  const {h, esc} = HZ;
  const P = {title: '總覽'};
  const card = (icon, title, page, ...body) => h('div', {class: 'card hcard', onclick: page ? () => HZ.go(page) : null, style: {cursor: page ? 'pointer' : ''}},
    h('div', {class: 'row'}, h('b', {text: `${icon} ${title}`}), h('span', {class: 'grow'}), page ? h('span', {class: 'muted small', text: '›'}) : null), ...body);
  const bar = (pct, cls = 'hot') => h('div', {class: 'bar big', style: {margin: '6px 0'}}, h('i', {class: cls, style: {width: Math.max(0, Math.min(100, pct || 0)) + '%'}}));

  P.build = function (root) {
    P.grid = h('div', {class: 'hgrid'});
    root.append(h('div', {class: 'sbox'}, h('b', {text: '📋 總覽'}), h('span', {class: 'grow'}), P.when = h('span', {class: 'small muted'})), h('div', {style: {overflow: 'auto', flex: '1'}}, P.grid));
  };
  P.load = async function () {
    let st = HZ.st, vs = {}, im = {}, q = {};
    try { st = await HZ.get('/api/state'); } catch (e) { }
    try { vs = (await HZ.get('/api/vault', {stage: 'keep', limit: 1})).stats || {}; } catch (e) { }
    try { im = await HZ.get('/api/images/status'); } catch (e) { }
    try { q = await HZ.get('/api/queue'); } catch (e) { }
    let lg = []; try { lg = (await HZ.get('/api/log', {since: 0})).rows || []; } catch (e) { }
    if (!P.drv_t || Date.now() - P.drv_t > 30000) { try { HZ.vols = (await HZ.get('/api/drives')).vols; P.drv_t = Date.now(); } catch (e) { } }   // free space changes
    if (!st) return;
    P.grid.innerHTML = '';
    // hot zone (+ a tiny line of the last days, from the progress history, refreshed once a minute)
    const hot = st.hot || [];
    P.hist = P.hist || {};
    for (const v of hot) if (!P.hist[v.letter] || Date.now() - P.hist[v.letter].t > 60000) {
      try { P.hist[v.letter] = {t: Date.now(), pts: (await HZ.get('/api/hot/history', {letter: v.letter})).points || []}; } catch (e) { P.hist[v.letter] = {t: Date.now(), pts: []}; }
    }
    const spark = L => {
      const pts = ((P.hist[L] || {}).pts || []).slice(-200); if (pts.length < 2) return null;
      const t0 = pts[0].t, sp = Math.max(1, pts[pts.length - 1].t - t0), y = p => 22 - (p.hot ? Math.min(1, p.in / p.hot) : 0) * 20;
      return h('div', {title: '熱資料在外圈的比例（最近幾天）', html: `<svg viewBox="0 0 200 24" preserveAspectRatio="none" style="width:100%;height:24px;display:block"><polyline fill="none" stroke="var(--hot)" stroke-width="1.5" vector-effect="non-scaling-stroke" points="${pts.map(p => ((p.t - t0) / sp * 200).toFixed(1) + ',' + y(p).toFixed(1)).join(' ')}"/></svg>`});
    };
    P.grid.append(card('🔥', '熱處理', 'hot', ...(hot.length ? hot.map(v => h('div', {style: {marginTop: '6px'}},
      h('div', {class: 'row'}, h('b', {text: v.letter}), h('span', {class: 'grow'}), h('span', {class: 'small', text: v.pct_in != null ? `外圈 ${v.pct_in}%` : '—'})),
      bar(v.pct_in), spark(v.letter), h('div', {class: 'small muted ell', text: (v.msg || v.state || '') + (v.rate > 0 ? `　${HZ.fmtRate(v.rate)}` : '') + (v.eta ? `　約 ${HZ.fmtEta(v.eta)}` : '')}))) :
      [h('div', {class: 'small muted', text: '還沒有熱資料夾'})])));
    // queue
    const jobs = (q.jobs || []).filter(j => ['running', 'scanning', 'queued', 'waiting', 'paused'].includes(j.state)).slice(0, 4);
    P.grid.append(card('⇅', '傳輸佇列', 'queue',
      h('div', {class: 'small', text: `執行中 ${st.queue.running}　排隊 ${st.queue.queued}` + (st.queue.waiting ? `　等你決定 ${st.queue.waiting}` : '') + (st.queue.speed ? `　${HZ.fmtRate(st.queue.speed)}` : '')}),
      ...jobs.map(j => { const tb = j.total_bytes || 0, p = tb ? j.done_bytes / tb * 100 : (j.total_files ? j.done_files / j.total_files * 100 : 0);
        return h('div', {style: {marginTop: '6px'}}, h('div', {class: 'small ell', text: `${HZ.base(j.src[0] || '')}${(j.src_n || j.src.length) > 1 ? ` 等 ${(j.src_n || j.src.length).toLocaleString()} 項` : ''} → ${j.dst ? HZ.base(j.dst) : ''}`}), bar(p, 'ok')); }),
      !jobs.length ? h('div', {class: 'small muted', text: '沒有進行中的工作'}) : null));
    // disks
    const vols = (HZ.vols || []).filter(v => v.ok && v.total);
    P.grid.append(card('💽', '磁碟空間', 'disks', ...vols.slice(0, 8).map(v => { const used = (v.total - v.free) / v.total * 100;
      return h('div', {style: {marginTop: '4px'}}, h('div', {class: 'row small'}, h('b', {text: v.letter}), h('span', {class: 'muted ell', text: v.label || ''}), h('span', {class: 'grow'}), h('span', {text: `剩 ${HZ.fmtSize(v.free)}`})),
        bar(used, used > 92 ? 'bad' : used > 80 ? 'warn' : 'ok')); })));
    // vault
    const k = vs.keep || {n: 0, size: 0}, r = vs.review || {n: 0, size: 0};
    P.grid.append(card('🛟', '保管區', 'vault', h('div', {class: 'small', text: `保管中 ${k.n.toLocaleString()} 項（${HZ.fmtSize(k.size)}）`}),
      r.n ? h('div', {class: 'small warn', text: `待你決定 ${r.n.toLocaleString()} 項（${HZ.fmtSize(r.size)}）`}) : h('div', {class: 'small muted', text: '沒有等你決定的項目'})));
    // images
    if ((im.folders || []).length) P.grid.append(card('🎨', '圖片分類', 'images', h('div', {class: 'small', text: `已分析 ${(im.analyzed || 0).toLocaleString()} 張`}),
      im.state === 'running' ? [bar(im.total ? im.done / im.total * 100 : 0, 'ok'), h('div', {class: 'small muted', text: `分析中 ${im.done.toLocaleString()} / ${im.total.toLocaleString()}`})] : h('div', {class: 'small muted', text: im.msg || ''})));
    // index + notices
    const ix = st.index || [];
    P.grid.append(card('🔍', '索引', 'search', ...ix.map(v => h('div', {class: 'small', text: `${v.key}　${v.state === 'ready' ? (v.live ? '⚡ 即時' : '✓') : v.state}　${(v.files || 0).toLocaleString()} 個檔案`})),
      !ix.length ? h('div', {class: 'small muted', text: '沒有已索引的磁碟'}) : null));
    if ((st.notices || []).length) P.grid.append(card('🔔', '提醒', null, ...st.notices.map(n => h('div', {class: 'small ' + (n.level === 'warn' ? 'warn' : ''), text: n.text}))));
    // what happened lately: copies / moves / vault / hot zone / updates (not the technical noise)
    const ev = lg.filter(r => ['queue', 'vault', 'hot', 'undo', 'update', 'images', 'dupes'].includes(r.a) && r.lv !== 'debug').slice(-8).reverse();
    if (ev.length) P.grid.append(card('🕘', '最近的動作', 'log', ...ev.map(r => h('div', {class: 'small ell' + (r.lv === 'warn' || r.lv === 'error' ? ' warn' : ''), title: r.m,
      text: `${new Date(r.t * 1000).toLocaleTimeString('zh-TW', {hour: '2-digit', minute: '2-digit', hour12: false})}　${r.m}`}))));
    P.when.textContent = '更新於 ' + new Date().toLocaleTimeString('zh-TW', {hour12: false});
  };
  P.onShow = () => HZ.every('home', 3000, P.load);
  P.onHide = () => HZ.stop('home');
  HZ.page('home', P);
})();

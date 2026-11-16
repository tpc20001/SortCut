/* HotZone FM — 影片工具: video length / resolution / codec, and lossless remux to MP4 */
'use strict';
(function () {
  const {h, esc} = HZ;
  const P = {title: '影片工具', sel: new Set(), sort: 'name'};
  const dur = s => { s = Math.round(s || 0); const hh = Math.floor(s / 3600), mm = Math.floor(s % 3600 / 60), ss = s % 60; return (hh ? hh + ':' + String(mm).padStart(2, '0') : mm) + ':' + String(ss).padStart(2, '0'); };

  P.build = function (root) {
    let last = ''; try { last = localStorage.getItem('hz.video.path') || ''; } catch (e) { }
    P.path = h('input', {placeholder: '影片資料夾，例如 K:\\直播錄影', value: last, style: {flex: '1', minWidth: '260px'}, onkeydown: e => { if (e.key === 'Enter') P.load(); }});
    P.rec = h('input', {type: 'checkbox'});
    P.info = h('div', {class: 'sinfo'});
    P.acts = h('div', {class: 'row wrap'});
    P.jobsEl = h('div', {class: 'vjobs'});
    P.list = h('div', {class: 'list'});
    root.append(h('div', {class: 'sbox', style: {flexDirection: 'column', alignItems: 'stretch'}},
      h('div', {class: 'small muted', html: `列出資料夾裡每支影片的長度、解析度、編碼。FLV／TS／MKV 等錄影檔可以<b>無損轉成 MP4</b>（不重新壓縮，畫質完全一樣，幾分鐘就好）；確認新的 MP4 長度正確後，原檔才放進保管區（${HZ.vaultDays()} 天內可還原）。需要 ffmpeg.exe（和 ffprobe.exe）放在程式資料夾。`}),
      h('div', {class: 'row wrap'}, P.path, HZ.bridge ? h('button', {class: 'sm', onclick: async () => { const p = await HZ.bcall('pickFolder'); if (p) { P.path.value = p; P.load(); } }}, '…') : null,
        h('label', {class: 'row small'}, P.rec, '含子資料夾'), h('button', {class: 'primary', onclick: () => P.load()}, '讀取')), P.acts),
      P.info, P.jobsEl, P.list);
  };
  P.load = async function (quiet) {
    const path = P.path.value.trim(); if (!path) return;
    try { localStorage.setItem('hz.video.path', path); } catch (e) { }
    let d; try { d = await HZ.post('/api/video/list', {path, recursive: P.rec.checked}); } catch (e) { if (!quiet) HZ.err(e); return; }
    P.d = d; P.render();
    HZ.every('video', 1500, P.tick);
  };
  P.tick = async function () {
    let j; try { j = await HZ.get('/api/video/jobs'); } catch (e) { return; }
    const was = P._busy; P._busy = j.probing > 0 || j.jobs.some(x => x.state === 'queued' || x.state === 'running');
    P.renderJobs(j.jobs, j.probing);
    if ((was && !P._busy) || (j.probing && Date.now() - (P._lastLoad || 0) > 4000)) { P._lastLoad = Date.now(); P.load(true); }
    if (!P._busy && !was) HZ.stop('video');
  };
  P.renderJobs = function (jobs, probing) {
    P.jobsEl.innerHTML = '';
    if (probing) P.jobsEl.append(h('div', {class: 'small muted', text: `讀取影片資訊中… 還有 ${probing} 支`}));
    for (const j of jobs.slice(-8).reverse()) {
      P.jobsEl.append(h('div', {class: 'row small', style: {padding: '3px 10px'}},
        h('span', {class: 'pill ' + ({done: 'ok', error: 'bad', running: 'acc', queued: '', canceled: 'muted'}[j.state] || ''), text: {done: '完成', error: '失敗', running: '轉換中', queued: '排隊', canceled: '已取消'}[j.state] || j.state}),
        h('span', {class: 'ell', style: {maxWidth: '360px'}, text: HZ.base(j.src)}),
        j.state === 'running' ? h('div', {class: 'bar', style: {width: '160px'}}, h('i', {class: 'ok', style: {width: (j.pct || 0) + '%'}})) : null,
        h('span', {class: 'muted ell grow', text: j.msg || ''}),
        (j.state === 'running' || j.state === 'queued') ? h('button', {class: 'sm', onclick: () => HZ.post('/api/video/cancel', {id: j.id}).then(P.tick)}, '取消') : null));
    }
  };
  P.render = function () {
    const d = P.d; if (!d) return;
    let items = d.items.slice();
    const key = {name: x => x.name.toLowerCase(), size: x => -x.size, dur: x => -((x.info || {}).dur || 0), res: x => -(((x.info || {}).w || 0) * ((x.info || {}).h || 0)), date: x => -x.mtime}[P.sort];
    items.sort((a, b) => { const ka = key(a), kb = key(b); return ka < kb ? -1 : ka > kb ? 1 : 0; });
    const tot = items.reduce((a, x) => a + ((x.info || {}).dur || 0), 0), tsz = items.reduce((a, x) => a + x.size, 0);
    const rem = items.filter(x => x.remux && x.info && x.info.vcodec);
    P.info.innerHTML = `<span>${items.length} 支影片</span><span>總長 ${dur(tot)}</span><span>${HZ.fmtSize(tsz)}</span>` +
      (!d.ffmpeg ? '<span class="warn">找不到 ffmpeg：請把 ffmpeg.exe 和 ffprobe.exe 放進程式資料夾</span>' : !d.ffprobe ? '<span class="muted">（沒有 ffprobe.exe，資訊會少一些）</span>' : '');
    P.acts.innerHTML = '';
    P.acts.append(
      h('button', {class: 'primary', disabled: !P.sel.size, onclick: () => P.remux([...P.sel])}, `勾選的無損轉 MP4（${P.sel.size}）`),
      h('button', {disabled: !rem.length, onclick: () => P.remux(rem.map(x => x.path))}, `全部可以轉的（${rem.length}）`),
      h('span', {class: 'grow'}),
      h('select', {onchange: e => { P.sort = e.target.value; P.render(); }}, ...[['name', '檔名'], ['date', '日期（新→舊）'], ['size', '大小'], ['dur', '長度'], ['res', '解析度']].map(([v, t]) => h('option', {value: v, text: '排序：' + t, selected: P.sort === v}))));
    P.list.innerHTML = '';
    P.list.append(h('div', {class: 'vidrow chdr'}, h('span'), h('span', {text: '檔名'}), h('span', {class: 'num', text: '長度'}), h('span', {text: '解析度'}), h('span', {text: '編碼'}), h('span', {class: 'num', text: '大小'}), h('span', {text: '日期'})));
    for (const x of items.slice(0, 3000)) {
      const i = x.info || {};
      const cb = h('input', {type: 'checkbox', disabled: !x.remux, title: x.remux ? '' : '已經是 MP4 或不能轉', checked: P.sel.has(x.path), onchange: e => { e.target.checked ? P.sel.add(x.path) : P.sel.delete(x.path); P.render(); }});
      const row = h('div', {class: 'vidrow', title: x.path + (x.err ? '\n讀取失敗：' + x.err : '')},
        cb, h('span', {class: 'row ell', style: {gap: '6px'}}, h('span', {html: HZ.icon({ext: x.name.split('.').pop().toLowerCase()})}), h('span', {class: 'ell', text: x.name})),
        h('span', {class: 'num', text: x.info ? dur(i.dur) : x.err ? '—' : '…'}),
        h('span', {text: i.w ? `${i.w}×${i.h}${i.fps ? ' ' + Math.round(i.fps) + 'fps' : ''}` : ''}),
        h('span', {class: 'muted', text: [i.vcodec, i.acodec].filter(Boolean).join(' / ')}),
        h('span', {class: 'num', text: HZ.fmtSize(x.size)}), h('span', {class: 'muted', text: HZ.fmtDate(x.mtime)}));
      row.ondblclick = () => HZ.openItem({path: x.path, name: x.name, dir: false, ext: x.name.split('.').pop().toLowerCase()});
      row.oncontextmenu = e => { e.preventDefault(); HZ.menu(e.clientX, e.clientY, [x.remux ? {icon: '🎬', text: '無損轉成 MP4', run: () => P.remux([x.path])} : null, '-',
        ...HZ.itemMenu([{path: x.path, name: x.name, dir: false, ext: x.name.split('.').pop().toLowerCase(), size: x.size, mtime: x.mtime}], {})].filter(Boolean)); };
      P.list.append(row);
    }
    if (!items.length) P.list.append(h('div', {class: 'empty', text: '這個資料夾沒有影片'}));
  };
  P.remux = async function (paths) {
    if (!paths.length) return;
    const keep = await HZ.dialog({title: '無損轉成 MP4', body: `${paths.length} 支影片會轉成 MP4（不重新壓縮，畫質一樣）。<br>新檔和原檔放在同一個資料夾，同名的 MP4 已經存在時會另外取名，不會覆蓋。`,
      buttons: [{text: '取消', value: null}, {text: '轉完保留原檔', value: 'keep'}, {text: '轉完原檔放進保管區', value: 'vault', primary: true}]});
    if (!keep) return;
    try { const r = await HZ.post('/api/video/remux', {paths, keep: keep === 'keep'}); HZ.toast(`已排入 ${r.n} 支`, 'ok'); P.sel.clear(); P.render(); HZ.every('video', 1500, P.tick); }
    catch (e) { HZ.err(e); }
  };
  HZ.remuxVideos = paths => P.remux(paths);
  P.onShow = () => { if (P.path.value) P.load(true); };
  P.onHide = () => HZ.stop('video');
  HZ.page('video', P);
})();

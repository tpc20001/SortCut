/* HotZone FM — 傳輸佇列 (Copy Handler / FastCopy style): lanes per physical disk, usage %, conflicts */
'use strict';
(function () {
  const {h, esc} = HZ;
  const Q = {title: '傳輸佇列', data: null, open: {}};
  const KIND = {copy: ['📋', '複製'], move: ['🚚', '移動'], delete: ['⛔', '永久刪除'], recycle: ['🛟', '放進保管區'], vault: ['🛟', '放進保管區']};
  const STATE = {queued: ['排隊中', ''], scanning: ['列出檔案', 'acc'], running: ['進行中', 'acc'], paused: ['已暫停', 'warn'], waiting: ['等你決定', 'warn'],
    done: ['完成', 'ok'], error: ['錯誤', 'bad'], canceled: ['已取消', '']};

  Q.build = function (root) {
    Q.top = h('div', {class: 'qtop'});
    Q.lanes = h('div', {class: 'lanes'});
    Q.list = h('div', {class: 'qlist'});
    root.append(Q.top, Q.lanes, Q.list);
    Q.renderTop();
  };
  Q.renderTop = function () {
    const S = HZ.settings || {};
    const pct = h('input', {type: 'range', min: 10, max: 100, step: 5, value: S['transfer.usage_pct'] || 80});
    const pctL = h('b', {text: (S['transfer.usage_pct'] || 80) + '%'});
    pct.oninput = () => pctL.textContent = pct.value + '%';
    pct.onchange = () => Q.set({'transfer.usage_pct': +pct.value});
    const cap = h('input', {type: 'number', min: 0, step: 10, value: S['transfer.mbps_cap'] || 0, style: {width: '70px'}, onchange: e => Q.set({'transfer.mbps_cap': +e.target.value || 0})});
    const hdd = h('select', {onchange: e => Q.set({'transfer.hdd_max': +e.target.value})}, ...[1, 2, 3, 4].map(n => h('option', {value: n, text: n, selected: (S['transfer.hdd_max'] || 1) == n})));
    const conflict = h('select', {onchange: e => Q.set({'transfer.conflict': e.target.value})},
      ...[['ask', '問我'], ['skip', '略過'], ['overwrite', '覆蓋'], ['newer', '較新才覆蓋'], ['rename', '保留兩者']].map(([v, t]) => h('option', {value: v, text: '同名：' + t, selected: S['transfer.conflict'] === v})));
    const after = h('select', {title: '佇列全部做完之後（只做一次）', onchange: e => Q.set({'transfer.after': e.target.value})},
      ...[['', '完成後：不做事'], ['sleep', '完成後：睡眠'], ['hibernate', '完成後：休眠'], ['shutdown', '完成後：關機']].map(([v, t]) => h('option', {value: v, text: t, selected: (S['transfer.after'] || '') === v})));
    const verify = h('label', {class: 'row small'}, h('input', {type: 'checkbox', checked: !!S['transfer.verify'], onchange: e => Q.set({'transfer.verify': e.target.checked})}), '複製後校驗');
    Q.pauseBtn = h('button', {onclick: () => HZ.post('/api/queue/all', {pause: !(Q.data && Q.data.paused_all)}).then(Q.load)}, '⏸ 全部暫停');
    Q.top.innerHTML = '';
    Q.top.append(Q.pauseBtn, h('button', {onclick: () => HZ.post('/api/queue/clear').then(Q.load)}, '🧹 清除已完成'), h('button', {onclick: Q.addManual}, '＋ 新增工作'),
      h('span', {class: 'grow'}),
      h('span', {class: 'small muted', title: '像 FastCopy：佇列最多只用這顆硬碟多少比例的時間（每顆硬碟可在下面個別設定）'}, '磁碟最高使用率'), pct, pctL,
      h('span', {class: 'small muted', title: '0 = 不限速'}, 'MB/s 上限'), cap,
      h('span', {class: 'small muted', title: '同一顆實體硬碟同時處理幾個工作（像 Copy Handler 一次一筆）'}, '每顆 HDD 同時'), hdd, conflict, verify, after);
  };
  Q.set = async function (d) {
    try { await HZ.post('/api/settings', d); Object.assign(HZ.settings, d); HZ.toast('已套用', 'ok', 1200); Q.load(); } catch (e) { HZ.err(e); }
  };
  Q.load = async function () {
    try {
      const d = await HZ.get('/api/queue'); const sig = JSON.stringify(d);
      Q.data = d;
      if (sig === Q._sig || HZ.isBusy(Q.lanes) || HZ.isBusy(Q.list)) return;
      Q._sig = sig; Q.render();
    } catch (e) { }
  };
  Q.render = function () {
    const d = Q.data; if (!d) return;
    Q.pauseBtn.textContent = d.paused_all ? '▶ 全部繼續' : '⏸ 全部暫停'; Q.pauseBtn.classList.toggle('primary', d.paused_all);
    // lanes
    Q.lanes.innerHTML = '';
    if (d.sched && d.sched.on) Q.lanes.append(h('div', {class: 'pill warn', style: {margin: '4px 8px'}, title: '設定 → 傳輸佇列 → 白天限速',
      text: `🌞 白天限速中：使用率最多 ${d.sched.pct}%${+d.sched.mbps ? '、' + d.sched.mbps + ' MB/s' : ''}，${d.sched.to} 點後恢復全速`}));
    const disks = {}; for (const x of (HZ.st && HZ.st.disks) || []) disks['d' + x.n] = x;
    const S = HZ.settings || {};
    for (const L of d.lanes) {
      const dk = disks[L.lane];
      const name = dk ? `${(dk.letters || []).join(' ')}　${dk.model || ''}` : L.lane.slice(1);
      const ov = (S['transfer.disk_pct'] || {})[L.lane.slice(1)];
      const ovm = (S['transfer.disk_max'] || {})[L.lane.slice(1)];
      const pct = h('input', {type: 'range', min: 10, max: 100, step: 5, value: L.pct, style: {width: '90px'}});
      const pl = h('b', {text: L.pct + '%'}); pct.oninput = () => pl.textContent = pct.value + '%';
      pct.onchange = () => { const o = Object.assign({}, S['transfer.disk_pct'] || {}); o[L.lane.slice(1)] = +pct.value; Q.set({'transfer.disk_pct': o}); };
      const mx = h('select', {onchange: e => { const o = Object.assign({}, S['transfer.disk_max'] || {}); o[L.lane.slice(1)] = +e.target.value; Q.set({'transfer.disk_max': o}); }},
        ...[1, 2, 3, 4, 6, 8].map(n => h('option', {value: n, text: n, selected: L.limit == n})));
      Q.lanes.append(h('div', {class: 'lane' + (L.state === 'yield' ? ' yield' : '')},
        h('div', {class: 'row'}, h('b', {class: 'ell', text: '💽 ' + name}), h('span', {class: 'grow'}), h('span', {class: 'pill acc', text: L.media === '?' ? '磁碟' : L.media})),
        h('div', {class: 'row small', style: {marginTop: '5px'}}, `執行 ${L.running}/`, mx, `　排隊 ${L.queued}`, h('span', {class: 'grow'}), h('span', {text: HZ.fmtRate(L.rate)})),
        h('div', {class: 'row small', style: {marginTop: '4px'}}, h('span', {class: 'muted', text: '最高使用率'}), pct, pl, ov != null || ovm != null ? h('a', {href: 'javascript:void 0', class: 'small', onclick: () => {
          const a = Object.assign({}, S['transfer.disk_pct'] || {}), b = Object.assign({}, S['transfer.disk_max'] || {}); delete a[L.lane.slice(1)]; delete b[L.lane.slice(1)]; Q.set({'transfer.disk_pct': a, 'transfer.disk_max': b});
        }}, '用預設') : null),
        dk && dk.busy != null ? h('div', {class: 'row small', style: {marginTop: '4px'}}, h('span', {class: 'muted', text: '硬碟忙碌'}), h('div', {class: 'bar grow'}, h('i', {class: dk.busy > 85 ? 'bad' : dk.busy > 60 ? 'warn' : '', style: {width: dk.busy + '%'}})), h('span', {text: Math.round(dk.busy) + '%'})) : null,
        L.state === 'yield' ? h('div', {class: 'small warn', text: '讓路中：其他程式正在用這顆硬碟'}) : null));
    }
    if (!d.lanes.length) Q.lanes.append(h('div', {class: 'muted small', text: '沒有工作。在檔案總管選檔案後「複製／剪下 → 貼上」、拖曳，或按 F5／F6（雙窗格），工作就會排進來。'}));
    // jobs
    Q.list.innerHTML = '';
    let sep = false;
    for (const j of d.jobs) {
      if (['done', 'error', 'canceled'].includes(j.state) && !sep) { sep = true; Q.list.append(h('div', {class: 'done-sep'}, '已結束', h('i', {style: {flex: '1', height: '1px', background: 'var(--border)'}}))); }
      Q.list.append(Q.job(j));
    }
  };
  Q.job = function (j) {
    const [ic, kt] = KIND[j.kind] || ['•', j.kind];
    const [st, sc] = STATE[j.state] || [j.state, ''];
    const nsrc = j.src_n || j.src.length;
    const name = HZ.base(j.src[0] || '') + (nsrc > 1 ? ` 等 ${nsrc.toLocaleString()} 項` : '');
    const tb = j.total_bytes, pctB = tb ? Math.min(100, j.done_bytes / tb * 100) : (j.total_files ? j.done_files / j.total_files * 100 : (j.state === 'done' ? 100 : 0));
    const act = (a, data) => HZ.post('/api/queue/action', {id: j.id, act: a, data}).then(() => { Q._sig = ''; HZ.pointer = false; Q.load(); }).catch(HZ.err);
    const B = (t, a, title) => h('button', {class: 'sm', title: title || '', onclick: () => act(a)}, t);
    const running = ['running', 'scanning'].includes(j.state), fin = ['done', 'error', 'canceled'].includes(j.state);
    const btns = h('div', {class: 'jb'},
      running ? B('⏸', 'pause', '暫停') : null,
      ['paused', 'error'].includes(j.state) ? B('▶', 'resume', '繼續') : null,
      j.state === 'queued' ? B('⏸', 'pause', '暫停（先不要做）') : null,
      !fin ? B('⤒', 'top', '移到最前面（插隊）') : null, !fin ? B('↑', 'up', '往前') : null, !fin ? B('↓', 'down', '往後') : null,
      !fin ? B('✕', 'cancel', '取消') : null,
      fin && j.err_count ? B('↻ 重試失敗的', 'retry') : null,
      fin ? B('移除', 'remove') : null,
      h('button', {class: 'sm ghost', title: '明細', onclick: () => Q.detail(j)}, '⋯'));
    const box = h('div', {class: `job ${j.state}${j.hot ? ' hotjob' : ''}`},
      h('div', {class: 'jh'}, h('span', {text: ic}), h('span', {class: 'jt ell', text: `${kt}　${name}`, title: j.src.join('\n') + (nsrc > j.src.length ? `\n…還有 ${(nsrc - j.src.length).toLocaleString()} 項` : '')}), j.hot ? h('span', {class: 'pill hot', text: '🔥 熱處理優先'}) : null,
        j.same ? h('span', {class: 'pill', title: '同一個磁碟：直接改位置，瞬間完成', text: '⚡ 同磁碟'}) : null,
        h('span', {class: 'pill ' + sc, text: st}), btns),
      j.dst ? h('div', {class: 'jm ell', title: j.dst}, '→ ' + j.dst) : null,
      !fin || j.state === 'error' ? h('div', {class: 'bar big', style: {marginTop: '6px'}}, h('i', {class: j.hot ? 'hot' : j.state === 'error' ? 'bad' : 'ok', style: {width: pctB + '%'}})) : null,
      h('div', {class: 'jm row wrap'},
        h('span', {text: tb ? `${HZ.fmtSize(j.done_bytes)} / ${HZ.fmtSize(tb)}（${pctB.toFixed(1)}%）` : `${j.done_files} / ${j.total_files || nsrc} 項`}),
        tb ? h('span', {text: `${j.done_files} / ${j.total_files} 個檔案`}) : null,
        running && j.speed ? h('span', {text: '⚡ ' + HZ.fmtRate(j.speed)}) : null,
        running && j.eta ? h('span', {text: '剩下 ' + HZ.fmtEta(j.eta)}) : null,
        j.skipped ? h('span', {text: `略過 ${j.skipped}`}) : null,
        j.err_count ? h('span', {class: 'bad', text: `錯誤 ${j.err_count}`}) : null,
        j.msg ? h('span', {class: j.state === 'error' ? 'bad' : 'warn', text: j.msg}) : null,
        fin && j.finished ? h('span', {class: 'muted', text: HZ.fmtAgo(j.finished)}) : null),
      running && j.cur ? h('div', {class: 'jm ell', title: j.cur.path}, `目前：${HZ.base(j.cur.path)}　${j.cur.size ? HZ.fmtSize(j.cur.done) + ' / ' + HZ.fmtSize(j.cur.size) : ''}`) : null);
    if (j.state === 'waiting' && j.question) box.append(Q.ask(j));
    if ((j.errors || []).length && (fin || j.state === 'paused')) box.append(h('div', {class: 'jm bad'}, ...j.errors.slice(-3).map(e => h('div', {class: 'ell', title: e.path, text: `✕ ${HZ.base(e.path)}：${e.msg}`}))));
    return box;
  };
  Q.ask = function (j) {
    const q = j.question;
    Q.allTick = Q.allTick || {};                                     // survives the 1-second redraw (it was cleared before the click)
    const all = h('input', {type: 'checkbox', checked: !!Q.allTick[j.id], onchange: e => { Q.allTick[j.id] = e.target.checked; }});
    const ans = a => HZ.post('/api/queue/action', {id: j.id, act: 'answer', data: {action: a, all: all.checked}}).then(Q.load).catch(HZ.err);
    if (q.kind === 'space') return h('div', {class: 'ask'},
      h('div', {html: `<b>目的地空間不夠</b>：這個工作需要 ${HZ.fmtSize(q.need)}，${esc(HZ.drive(q.dst) || q.dst)} 只剩 ${HZ.fmtSize(q.free)}。`}),
      h('div', {class: 'small muted', text: '被覆蓋的舊檔會先放進同一顆硬碟的保管區，不會騰出空間。可以先清出空間再按「繼續」，或直接繼續（放不下的檔案會失敗，已經複製好的會保留）。'}),
      h('div', {class: 'row wrap', style: {marginTop: '6px'}}, h('button', {class: 'sm primary', onclick: () => ans('continue')}, '繼續'),
        h('span', {class: 'grow'}), h('button', {class: 'sm', onclick: () => ans('cancel')}, '取消整個工作')));
    const newer = q.src_mtime > q.dst_mtime + 1;
    const pic = /\.(jpe?g|png|webp|gif|bmp|tiff?|heic|mp4|mkv|mov)$/i.test(q.dst);          // pictures / videos: show both
    const th = (p, lab) => h('div', {class: 'col', style: {alignItems: 'center', gap: '2px'}}, h('img', {src: '/api/thumb?' + new URLSearchParams({path: p, s: 160}),
      style: {maxWidth: '160px', maxHeight: '120px', borderRadius: '6px', background: '#0002'}, onerror: e => e.target.parentNode.remove()}), h('span', {class: 'small muted', text: lab}));
    return h('div', {class: 'ask'},
      h('div', {html: `<b>目的地已經有同名檔案：</b>${esc(HZ.base(q.dst))}`}),
      pic ? h('div', {class: 'row', style: {gap: '14px', margin: '6px 0'}}, th(q.src, '要放進來的'), th(q.dst, '已經在那裡的')) : null,
      h('div', {class: 'kv small', style: {margin: '6px 0'}},
        h('b', {text: '要放進來的'}), h('span', {text: `${HZ.fmtSize(q.src_size)}　${HZ.fmtDate(q.src_mtime)}${newer ? '　（比較新）' : ''}`}),
        h('b', {text: '已經在那裡的'}), h('span', {text: `${HZ.fmtSize(q.dst_size)}　${HZ.fmtDate(q.dst_mtime)}${!newer ? '　（比較新或一樣）' : ''}`})),
      h('div', {class: 'row wrap'}, h('button', {class: 'sm', onclick: () => ans('overwrite')}, '覆蓋'), h('button', {class: 'sm', onclick: () => ans('skip')}, '略過'),
        h('button', {class: 'sm', onclick: () => ans('rename')}, '保留兩者（改名）'), h('button', {class: 'sm', onclick: () => ans('newer')}, '比較新才覆蓋'),
        h('button', {class: 'sm', onclick: () => ans('larger')}, '比較大才覆蓋'), h('label', {class: 'row small'}, all, '之後都這樣做'),
        h('span', {class: 'grow'}), h('button', {class: 'sm', onclick: () => ans('cancel')}, '取消整個工作')));
  };
  Q.detail = async function (j) {
    let only = '', d;
    const body = h('div', {style: {minWidth: 'min(600px,86vw)'}});
    const draw = async () => {
      try { d = await HZ.get('/api/queue/job', {id: j.id, only, limit: 500}); } catch (e) { body.textContent = e.message; return; }
      const st = {'0': '等待', '1': '完成', '2': '略過', '3': '錯誤', '4': '進行中'};
      body.innerHTML = '';
      body.append(h('div', {class: 'kv small'}, h('b', {text: '來源'}), h('span', {class: 'mono', style: {whiteSpace: 'pre-wrap'}, text: d.src.join('\n')}), h('b', {text: '目的地'}), h('span', {class: 'mono', text: d.dst || '—'}),
        h('b', {text: '建立'}), h('span', {text: HZ.fmtDate(d.created)}), h('b', {text: '選項'}), h('span', {text: `同名：${({ask: '問我', skip: '略過', overwrite: '覆蓋', newer: '較新才覆蓋', larger: '較大才覆蓋', rename: '保留兩者'})[d.opts.conflict] || d.opts.conflict}　校驗：${d.opts.verify ? '是' : '否'}　保留時間：${d.opts.preserve ? '是' : '否'}`})));
      body.append(h('div', {class: 'row', style: {margin: '8px 0'}}, ...[['', '全部'], ['3', '錯誤'], ['0', '等待'], ['12', '已完成／略過']].map(([v, t]) =>
        h('span', {class: 'chip' + (only === v ? ' on' : ''), text: t, onclick: () => { only = v; draw(); }})), h('span', {class: 'small muted', text: `${d.items_total.toLocaleString()} 項`})));
      const t = h('table', {class: 't'}, h('tr', {}, h('th', {text: '狀態'}), h('th', {text: '項目'}), h('th', {class: 'num', text: '大小'})));
      for (const it of d.items) t.append(h('tr', {}, h('td', {class: it.s === '3' ? 'bad' : it.s === '1' ? 'ok' : 'muted', text: st[it.s] || it.s}), h('td', {class: 'ell', style: {maxWidth: '420px'}, title: it.src, text: it.src}), h('td', {class: 'num', text: it.kind === 'd' ? '資料夾' : HZ.fmtSize(it.size)})));
      body.append(h('div', {style: {maxHeight: '45vh', overflow: 'auto'}}, t));
      if ((d.errors || []).length) body.append(h('h3', {text: '錯誤訊息'}), h('div', {class: 'small', style: {maxHeight: '20vh', overflow: 'auto'}}, ...d.errors.map(e => h('div', {class: 'bad', text: `${e.path}：${e.msg}`}))));
    };
    await draw();
    HZ.dialog({title: '工作明細', body, width: 'min(760px,94vw)', buttons: [{text: '關閉', primary: true, value: null}]});
  };
  Q.addManual = async function () {
    const kind = h('select', {}, h('option', {value: 'copy', text: '複製'}), h('option', {value: 'move', text: '移動'}));
    const src = h('textarea', {rows: 5, style: {width: '100%'}, placeholder: '來源路徑，一行一個'});
    const dst = h('input', {style: {width: '100%'}, placeholder: '目的資料夾'});
    const r = await HZ.dialog({title: '新增傳輸工作', body: h('div', {class: 'col'}, kind, src, dst), buttons: [{text: '取消', value: null}, {text: '加入佇列', primary: true, value: true}]});
    if (!r) return;
    const s = src.value.split('\n').map(x => x.trim().replace(/^"|"$/g, '')).filter(Boolean);
    if (!s.length || !dst.value.trim()) { HZ.toast(!s.length ? '請輸入至少一個來源路徑' : '請輸入目的資料夾', 'bad'); return; }
    HZ.queueAdd(kind.value, s, dst.value.trim());
  };
  Q.onShow = function () { Q.renderTop(); HZ.every('queue', 1000, Q.load); };
  Q.onHide = () => HZ.stop('queue');
  Q.onFsChange = () => { if (HZ.cur === 'queue') Q.load(); };
  HZ.page('queue', Q);
})();

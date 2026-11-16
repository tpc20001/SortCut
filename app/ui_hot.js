/* HotZone FM — 熱處理: hot folders, outer-zone progress, cluster map, relocation settings */
'use strict';
(function () {
  const {h, esc} = HZ;
  const T = {title: '熱處理', scroll: true, data: null, maps: {}};
  const STATE = {moving: ['搬移中', 'hot'], evicting: ['把冷資料移到內圈', 'hot'], planning: ['檢查位置', 'acc'], waiting: ['等待', 'warn'], done: ['完成 ✓', 'ok'],
    dry: ['試跑結果', 'acc'], idle: ['待命', ''], error: ['錯誤', 'bad'], unsupported: ['無法使用', 'bad'], full: ['熱區滿了', 'warn']};

  T.build = function (root) {
    T.root = root;
    T.head = h('div');
    T.vols = h('div', {class: 'col', style: {gap: '12px'}});
    T.opts = h('div', {class: 'card', style: {marginTop: '12px'}});
    root.append(h('h2', {html: '🔥 熱處理'}), T.head, T.vols, h('h3', {text: '搬移設定'}), T.opts);
    T.renderOpts();
  };
  T.renderOpts = function () {
    const S = HZ.settings || {};
    const set = d => HZ.post('/api/settings', d).then(() => { Object.assign(HZ.settings, d); HZ.toast('已套用', 'ok', 1200); T.load(); }).catch(HZ.err);
    const pct = h('input', {type: 'range', min: 10, max: 100, step: 5, value: S['hot.usage_pct'] || 60}); const pl = h('b', {text: (S['hot.usage_pct'] || 60) + '%'});
    pct.oninput = () => pl.textContent = pct.value + '%'; pct.onchange = () => set({'hot.usage_pct': +pct.value});
    const mode = h('select', {onchange: e => set({'hot.mode': e.target.value})}, ...[['always', '一直搬（照使用率）'], ['idle', '只在硬碟閒置時'], ['hours', '只在指定時段']].map(([v, t]) => h('option', {value: v, text: t, selected: S['hot.mode'] === v})));
    const hrs = S['hot.hours'] || [1, 8];
    const h0 = h('input', {type: 'number', min: 0, max: 23, value: hrs[0], style: {width: '56px'}}), h1 = h('input', {type: 'number', min: 0, max: 24, value: hrs[1], style: {width: '56px'}});
    const hset = () => set({'hot.hours': [+h0.value, +h1.value]}); h0.onchange = hset; h1.onchange = hset;
    const order = h('select', {onchange: e => set({'hot.order': e.target.value})}, ...[['newest', '最新的檔案先搬'], ['largest', '最大的先搬'], ['name', '依名稱']].map(([v, t]) => h('option', {value: v, text: t, selected: S['hot.order'] === v})));
    const cold = h('select', {onchange: e => set({'hot.cold_to': e.target.value})}, ...[['end', '冷資料移到最內圈（磁碟尾端）'], ['after', '冷資料放在熱區後面']].map(([v, t]) => h('option', {value: v, text: t, selected: S['hot.cold_to'] === v})));
    const yld = h('input', {type: 'number', min: 0, step: 1, value: S['hot.yield_mbps'] ?? 8, style: {width: '64px'}, onchange: e => set({'hot.yield_mbps': +e.target.value || 0})});
    const chunk = h('select', {onchange: e => set({'hot.chunk_mb': +e.target.value})}, ...[8, 16, 32, 64, 128].map(n => h('option', {value: n, text: n + ' MB', selected: (S['hot.chunk_mb'] || 32) == n})));
    const cb = (k, label, title) => h('label', {class: 'row', title: title || ''}, h('input', {type: 'checkbox', checked: !!S[k], onchange: e => set({[k]: e.target.checked})}), label);
    T.opts.innerHTML = '';
    T.opts.append(h('div', {class: 'col'},
      h('div', {class: 'row wrap'}, cb('hot.enabled', '啟用熱區搬移'), cb('hot.dry_run', '試跑（只規劃、不搬）', '先看要搬多少、要多久，不會動到任何資料'),
        cb('hot.yield_queue', '傳輸佇列在用同一顆硬碟時先暫停', '避免兩邊一起搶硬碟造成來回尋軌')),
      h('div', {class: 'row wrap'}, h('span', {text: '硬碟使用率上限'}), pct, pl, h('span', {class: 'muted small', text: '（60% ≈ 每搬 0.6 秒休息 0.4 秒；100% = 全速）'})),
      h('div', {class: 'row wrap'}, h('span', {text: '時機'}), mode, h('span', {class: 'small muted', text: '時段'}), h0, h('span', {text: '～'}), h1, h('span', {class: 'small muted', text: '點'})),
      h('div', {class: 'row wrap'}, h('span', {text: '其他程式讀寫超過'}), yld, h('span', {text: 'MB/s 時讓路（0 = 不讓）'})),
      h('div', {class: 'row wrap'}, order, cold, h('span', {class: 'small muted', text: '每次搬'}), chunk)));
  };
  T.load = async function () {
    try {
      const d = await HZ.get('/api/hot'); HZ.hotFolders = d.folders; T.data = d;
      if (!T.benchT || Date.now() - T.benchT > 60000) { try { T.benchLast = (await HZ.get('/api/hot/bench')).last || {}; T.benchT = Date.now(); } catch (e) { } }
      if (HZ.isBusy(T.vols) || HZ.isBusy(T.head)) return;
      T.render();
    } catch (e) { }
  };
  T.render = function () {
    const d = T.data; if (!d) return;
    T.head.innerHTML = '';
    T.head.append(h('div', {class: 'card', style: {marginBottom: '12px'}},
      h('div', {class: 'small', html: `硬碟碟片<b>外圈</b>（磁碟區最前面）每轉一圈讀到的資料最多，比內圈快 1.5～2 倍。標記為「熱處理」的資料夾：
        <b>同一顆硬碟移進來是瞬間改位置、馬上能用</b>；背景再用 Windows 磁碟重組的 API 把它們的磁區慢慢搬到外圈，必要時先把佔住外圈的冷資料移到內圈。檔案搬移期間照常可以開啟使用。`}),
      h('div', {class: 'row wrap', style: {marginTop: '8px'}},
        h('button', {class: d.paused ? 'primary' : '', onclick: () => HZ.post('/api/hot/pause', {on: !d.paused}).then(T.load)}, d.paused ? '▶ 繼續搬移' : '⏸ 暫停搬移'),
        h('button', {onclick: T.addFolder}, '＋ 加入熱資料夾'),
        h('button', {onclick: () => HZ.post('/api/hot/poke', {}).then(() => HZ.toast('已要求重新檢查'))}, '⟳ 立即重新檢查'),
        h('button', {title: '第一次使用前建議跑一次：確認這台電腦的硬碟可以安全搬移', onclick: () => HZ.selftest()}, '🩺 自我檢查'),
        !d.admin ? h('span', {class: 'pill bad', text: '背景引擎不是系統管理員：無法搬移磁區'}) : null)));
    T.vols.innerHTML = '';
    if (!d.vols.length) T.vols.append(h('div', {class: 'card muted', html: '還沒有熱資料夾。到「檔案總管」對資料夾按右鍵 →「🔥 標記為熱處理優先」，或按上面的「加入熱資料夾」。'}));
    for (const v of d.vols) T.vols.append(T.vol(v));
  };
  T.vol = function (v) {
    const [st, sc] = STATE[v.state] || [v.state, ''];
    const GB = 1073741824;
    const pctIn = v.pct_in;
    const zone = h('input', {type: 'number', min: 0, step: 10, value: v.zone_setting || '', placeholder: '自動', style: {width: '80px'}});
    zone.onchange = () => HZ.post('/api/hot/zone', {letter: v.letter, gb: +zone.value || 0}).then(() => { HZ.toast('熱區大小已更新，重新規劃中', 'hot'); T.load(); }).catch(HZ.err);
    const card = h('div', {class: 'card hotcard'});
    const rec = v.hot_bytes ? Math.ceil((v.hot_bytes / GB * 1.15 + 10) / 10) * 10 : 0;
    card.append(
      h('div', {class: 'row wrap'}, h('b', {style: {fontSize: '16px'}, text: '💽 ' + v.letter}), h('span', {class: 'pill acc', text: v.media || '?'}), h('span', {class: 'pill', text: v.fs || ''}),
        v.smr ? h('span', {class: 'pill warn', title: '這個型號看起來是 SMR（疊瓦式）硬碟：內部有位址轉換，「前面＝外圈」不一定成立，大量搬移也比較慢', text: '⚠ 可能是 SMR'}) : null,
        v.media === 'SSD' ? h('span', {class: 'pill warn', text: 'SSD 沒有內外圈之分，搬移沒有效果'}) : null,
        h('span', {class: 'grow'}), h('span', {class: 'pill ' + sc, text: st})),
      h('div', {class: 'row wrap', style: {marginTop: '10px', gap: '22px', alignItems: 'flex-end'}},
        h('div', {}, h('div', {class: 'bigpct', text: pctIn != null ? pctIn + '%' : '—'}), h('div', {class: 'small muted', text: '熱資料在外圈'})),
        h('div', {class: 'kv'},
          h('b', {text: '熱資料'}), h('span', {text: `${HZ.fmtSize(v.hot_bytes || 0)}（${(v.hot_files || 0).toLocaleString()} 個檔案）`}),
          h('b', {text: '已在外圈'}), h('span', {text: HZ.fmtSize(v.in_bytes || 0)}),
          v.frag ? h('b', {text: '連續程度'}) : null, v.frag ? h('span', {title: '每個熱檔案平均被分成幾段（1 = 完全連續，最快）', text: `平均 ${v.frag} 段`}) : null,
          h('b', {text: '還要搬'}), h('span', {text: HZ.fmtSize(Math.max(0, (v.hot_bytes || 0) - (v.in_bytes || 0)))}),
          h('b', {text: '速度'}), h('span', {text: v.state === 'moving' || v.state === 'evicting' ? `${HZ.fmtRate(v.rate)}${v.eta ? '　剩下約 ' + HZ.fmtEta(v.eta) : ''}` : '—'})),
        h('div', {class: 'kv'},
          h('b', {text: '外圈熱區'}), h('span', {}, `前 ${v.zone_gb || '?'} GB　設定 `, zone, ' GB', rec ? h('span', {class: 'small muted', text: `（建議 ${rec}）`}) : null),
          h('b', {text: '熱區空位'}), h('span', {text: v.zone_free != null ? HZ.fmtSize(v.zone_free) : '—'}),
          h('b', {text: '這次已搬'}), h('span', {text: `熱資料 ${HZ.fmtSize(v.moved_bytes || 0)}　冷資料移出 ${HZ.fmtSize(v.evicted_bytes || 0)}`}),
          h('b', {text: '磁碟'}), h('span', {text: v.total ? `可用 ${HZ.fmtSize(v.free)} / ${HZ.fmtSize(v.total)}` : ''}))),
      h('div', {class: 'bar big', style: {margin: '10px 0 4px'}}, h('i', {class: 'hot', style: {width: (pctIn || 0) + '%'}})),
      v.msg ? h('div', {class: 'small ' + (v.state === 'error' || v.state === 'unsupported' ? 'bad' : /還原點/.test(v.msg) ? 'warn' : 'muted'), text: v.msg}) : null,
      (v.zone_gb && v.hot_bytes > v.zone_gb * 1073741824) ? h('div', {class: 'small warn', text: `熱資料（${HZ.fmtSize(v.hot_bytes)}）比外圈熱區（${v.zone_gb} GB）還大：放不下的部分會留在原處。請把熱區調大（建議 ${Math.ceil(v.hot_bytes / 1073741824 * 1.15 + 10)} GB）或設回自動。`}) : null,
      /還原點/.test(v.msg || '') ? h('div', {class: 'row wrap', style: {marginTop: '6px'}},
        h('button', {class: 'primary', onclick: async () => {
          if (!await HZ.confirm('系統還原點', `${esc(v.letter)} 有系統還原點（陰影複製）。搬移磁區時 Windows 會把舊資料複製到還原點的儲存空間，空間不夠時會<b>自動刪掉最舊的還原點</b>。<br><br>如果你不靠這顆硬碟的還原點救檔案，可以放心繼續（你的檔案本身不受影響）。也可以先到「系統內容 → 系統保護」關掉這顆硬碟的保護。`, '我了解，繼續搬移')) return;
          HZ.post('/api/hot/vss_ok', {letter: v.letter}).then(() => { HZ.toast('好的，繼續搬移', 'hot'); T.load(); }).catch(HZ.err);
        }}, '我了解，繼續'), h('span', {class: 'small muted', text: '你的檔案不會受影響，只是較舊的還原點可能被 Windows 刪掉'})) : null,
      v.cur ? h('div', {class: 'small muted ell', title: v.cur, text: '目前：' + v.cur}) : null);
    if (v.dry) {
      card.append(h('div', {class: 'ask', style: {borderColor: 'var(--accent)', background: 'color-mix(in srgb,var(--accent) 10%,transparent)'}, html:
        `<b>試跑結果</b>　要搬進外圈 ${HZ.fmtSize(v.dry.move)}（${v.dry.files} 個檔案）；熱區空位 ${HZ.fmtSize(v.dry.free)}；需要先把 ${HZ.fmtSize(v.dry.evict)} 冷資料移到內圈。<br>
         以目前使用率估計約 <b>${v.dry.hours.toFixed(1)} 小時</b>（${esc(v.dry.basis || '一般硬碟原地搬移約 60 MB/s')}）。取消上面的「試跑」就會開始搬。`}));
    }
    // folders
    const fl = h('div', {class: 'col', style: {gap: '2px', marginTop: '8px'}});
    for (const f of v.folders || []) {
      fl.append(h('div', {class: 'hf'}, h('span', {html: HZ.icon({dir: true, hot: true})}), h('a', {href: 'javascript:void 0', class: 'ell', text: f.path, onclick: () => { HZ.go('explorer'); HZ.pages.explorer.open(f.path); }}),
        h('span', {class: 'grow'}), h('span', {class: 'small muted', text: '加入於 ' + HZ.fmtDate(f.added)}),
        h('button', {class: 'sm', onclick: () => HZ.markHot(f.path, false).then(T.load)}, '取消熱處理')));
    }
    card.append(h('h3', {text: '熱資料夾'}), fl);
    // map
    const cv = h('canvas', {class: 'cmap'});
    const mapInfo = h('div', {class: 'legend', style: {marginTop: '6px'}},
      h('span', {}, h('i', {style: {background: '#3b4656'}}), '已使用'), h('span', {}, h('i', {style: {background: '#151b22', border: '1px solid #2a3340'}}), '空的'),
      h('span', {}, h('i', {style: {background: 'var(--hot)'}}), '熱資料'), h('span', {}, h('i', {style: {background: 'rgba(255,138,61,.25)', border: '1px dashed var(--hot)'}}), '外圈熱區'),
      h('span', {}, h('i', {style: {background: 'var(--mft)'}}), 'MFT 保留區'), h('span', {class: 'grow'}), h('span', {class: 'small', text: '← 外圈（快）　　內圈（慢）→'}));
    const ntfs = !v.fs || String(v.fs).toUpperCase() === 'NTFS';
    const mapBtn = h('button', {class: 'sm', disabled: !ntfs, title: ntfs ? '' : `${v.letter} 是 ${v.fs}，磁區圖和熱區搬移只支援 NTFS`, onclick: () => T.map(v.letter, cv, true)}, '⟳ 更新磁區圖');
    const benchBtn = h('button', {class: 'sm', title: '從磁碟最前面（外圈）到最後面（內圈）讀 10 個位置，實際量出外圈快多少（只讀不寫，約 20 秒）', onclick: () => T.bench(v.letter)}, '📈 外圈／內圈測速');
    const bl = (T.benchLast || {})[v.letter];
    if (bl) card.append(h('div', {class: 'small muted', style: {marginTop: '6px'}, text: `📈 上次測速（${HZ.fmtDate(bl.t)}）：外圈 ${Math.round(bl.outer)} MB/s，內圈 ${Math.round(bl.inner)} MB/s，外圈快 ${(bl.outer / Math.max(bl.inner, 0.1)).toFixed(1)} 倍`}));
    const histBtn = h('button', {class: 'sm', title: '這幾天熱資料在外圈的比例、搬了多少', onclick: () => T.history(v.letter)}, '📅 進度紀錄');
    card.append(h('div', {class: 'row wrap', style: {marginTop: '10px'}}, h('h3', {style: {margin: '0'}, text: '磁區圖'}), h('span', {class: 'grow'}), v.state !== 'unsupported' ? histBtn : null, v.state !== 'unsupported' ? benchBtn : null, mapBtn), cv, mapInfo);
    if ((v.errors || []).length) {
      const det = h('details', {style: {marginTop: '8px'}}, h('summary', {class: 'small warn', text: `略過 ${v.skipped || v.errors.length} 個檔案（點開看原因）`}),
        ...v.errors.slice(-20).reverse().map(e => h('div', {class: 'small ell', title: e.path, text: `${HZ.fmtDate(e.t)}　${e.path}：${e.msg}`})));
      card.append(det);
    }
    if (v.state !== 'unsupported' && ntfs) setTimeout(() => T.map(v.letter, cv, false), 50);
    return card;
  };
  T.map = async function (letter, cv, fresh) {
    let m = T.maps[letter];
    try {
      if (!m || fresh || Date.now() - m._t > 30000) { m = await HZ.get('/api/hot/map', {letter, cells: 1600, fresh: fresh ? '1' : '0'}); m._t = Date.now(); T.maps[letter] = m; }
    } catch (e) { if (fresh) HZ.err(e); return; }
    const W = cv.clientWidth || 800, H = cv.clientHeight || 170, dpr = devicePixelRatio || 1;
    cv.width = W * dpr; cv.height = H * dpr; const g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const n = m.cells.length, cols = Math.max(40, Math.floor(W / 7)), rows = Math.ceil(n / cols);
    const cw = W / cols, ch = H / rows;
    const dark = document.documentElement.dataset.theme !== 'light';
    for (let i = 0; i < n; i++) {
      const u = m.cells[i], x = (i % cols) * cw, y = Math.floor(i / cols) * ch;
      const L = dark ? 9 + u * 26 : 92 - u * 40;
      g.fillStyle = `hsl(215,14%,${L}%)`; g.fillRect(x, y, cw - 1, ch - 1);
      const hot = m.hot ? m.hot[i] : 0;
      if (hot > 0.002) { g.fillStyle = `rgba(255,138,61,${Math.min(1, 0.35 + hot * 1.5)})`; g.fillRect(x, y, cw - 1, ch - 1); }
    }
    const per = m.per;
    const mark = (lcnA, lcnB, color, dash) => {
      const a = Math.floor(lcnA / per), b = Math.ceil(lcnB / per);
      g.strokeStyle = color; g.lineWidth = 1.5; g.setLineDash(dash ? [4, 3] : []);
      for (let i = a; i < Math.min(b, n); i++) { const x = (i % cols) * cw, y = Math.floor(i / cols) * ch; g.strokeRect(x + .5, y + .5, cw - 2, ch - 2); }
      g.setLineDash([]);
    };
    if (m.mft_zone && m.mft_zone[1] > m.mft_zone[0]) mark(m.mft_zone[0], m.mft_zone[1], '#9b7bff', false);
    if (m.zone_end) {
      const zi = Math.ceil(m.zone_end / per);                           // zone boundary
      const x = (zi % cols) * cw, y = Math.floor(zi / cols) * ch;
      g.fillStyle = 'rgba(255,138,61,.12)';
      for (let r = 0; r < Math.floor(zi / cols); r++) g.fillRect(0, r * ch, W, ch);
      g.fillRect(0, y, x, ch);
      g.strokeStyle = '#ff8a3d'; g.lineWidth = 2; g.beginPath(); g.moveTo(x, y); g.lineTo(x, y + ch); g.moveTo(x, y + ch); g.lineTo(0, y + ch); g.moveTo(x, y); g.lineTo(W, y); g.stroke();
    }
    cv.onmousemove = e => {
      const r = cv.getBoundingClientRect(), i = Math.floor((e.clientY - r.top) / ch) * cols + Math.floor((e.clientX - r.left) / cw);
      if (i < 0 || i >= n) return HZ.tip(null);
      const gb = (i * per * m.cluster / 1073741824).toFixed(1);
      HZ.tip(e, `位置 ${gb} GB（${(i / n * 100).toFixed(1)}%）<br>已使用 ${Math.round(m.cells[i] * 100)}%${m.hot && m.hot[i] ? `　熱資料 ${Math.round(m.hot[i] * 100)}%` : ''}${m.zone_end && i * per < m.zone_end ? '<br><span class="hot">外圈熱區</span>' : ''}`);
    };
    cv.onmouseleave = () => HZ.tip(null);
  };
  T.addFolder = async function () {
    let p = null;
    if (HZ.bridge) p = await HZ.bcall('pickFolder');
    else p = await HZ.prompt('加入熱資料夾', '資料夾路徑（例如 K:\\Work\\進行中）', '');
    if (p) HZ.markHot(p, true).then(T.load);
  };
  T.onShow = function () { T.renderOpts(); HZ.every('hot', 2000, T.load); };
  T.onHide = () => HZ.stop('hot');
  T.onFsChange = () => { if (HZ.cur === 'hot') T.load(); };
  /* progress over days: share of the hot data in the outer zone (line) and how much was moved per day (bars) */
  T.history = async function (letter) {
    let pts = []; try { pts = (await HZ.get('/api/hot/history', {letter})).points || []; } catch (e) { HZ.err(e); return; }
    if (pts.length < 2) { HZ.alert('📅 進度紀錄', '還沒有足夠的紀錄：每次檢查熱資料的位置（大約每 15 分鐘到 30 分鐘）會記一筆，過一陣子再來看。'); return; }
    const W = 640, H = 220, L = 40, R = 10, Tp = 10, B = 28, t0 = pts[0].t, t1 = pts[pts.length - 1].t, span = Math.max(1, t1 - t0);
    const X = t => L + (t - t0) / span * (W - L - R), Y = p => Tp + (1 - p / 100) * (H - Tp - B);
    const pct = p => p.hot ? Math.min(100, p.in / p.hot * 100) : 0;
    // moved per day: difference of the running "moved" counter (it restarts with the engine: negative steps are skipped)
    const days = new Map();
    for (let i = 1; i < pts.length; i++) { const d = pts[i].moved - pts[i - 1].moved; if (d > 0) { const k = new Date(pts[i].t * 1000).toDateString(); days.set(k, (days.get(k) || 0) + d); } }
    const maxDay = Math.max(1, ...days.values());
    let svg = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;display:block">`;
    for (const g of [0, 25, 50, 75, 100]) svg += `<line x1="${L}" x2="${W - R}" y1="${Y(g)}" y2="${Y(g)}" stroke="var(--grid)"/><text x="${L - 6}" y="${Y(g) + 4}" text-anchor="end" font-size="10" fill="var(--subtext)">${g}%</text>`;
    for (const [k, b] of days) { const t = new Date(k).getTime() / 1000 + 43200, x = X(Math.min(t1, Math.max(t0, t))), bh = b / maxDay * (H - Tp - B) * 0.5;
      svg += `<rect x="${x - 6}" y="${H - B - bh}" width="12" height="${bh}" fill="var(--accent)" opacity=".35"><title>${esc(k)}：搬了 ${HZ.fmtSize(b)}</title></rect>`; }
    svg += `<polyline fill="none" stroke="var(--hot)" stroke-width="2" points="${pts.map(p => X(p.t).toFixed(1) + ',' + Y(pct(p)).toFixed(1)).join(' ')}"/>`;
    for (const p of pts.filter((_, i) => i % Math.ceil(pts.length / 60) === 0 || i === pts.length - 1))
      svg += `<circle cx="${X(p.t)}" cy="${Y(pct(p))}" r="2.5" fill="var(--hot)"><title>${HZ.fmtDate(p.t)}：外圈 ${pct(p).toFixed(1)}%（${HZ.fmtSize(p.in)} / ${HZ.fmtSize(p.hot)}）</title></circle>`;
    svg += `<text x="${L}" y="${H - 8}" font-size="10" fill="var(--subtext)">${esc(HZ.fmtDate(t0))}</text><text x="${W - R}" y="${H - 8}" font-size="10" text-anchor="end" fill="var(--subtext)">${esc(HZ.fmtDate(t1))}</text></svg>`;
    const last = pts[pts.length - 1], first = pts[0];
    HZ.dialog({title: `📅 ${esc(letter)} 熱處理進度`, width: 'min(720px,94vw)', body: h('div', {class: 'col'},
      h('div', {html: svg}),
      h('div', {class: 'legend'}, h('span', {}, h('i', {style: {background: 'var(--hot)'}}), '熱資料在外圈的比例'), h('span', {}, h('i', {style: {background: 'var(--accent)', opacity: '.35'}}), '每天搬進外圈的量')),
      h('div', {class: 'small muted', text: `從 ${pct(first).toFixed(1)}% 到 ${pct(last).toFixed(1)}%；熱資料 ${HZ.fmtSize(last.hot)}` + (last.frag ? `；平均每個檔案 ${last.frag} 段` : '')}))});
  };
  T.bench = async function (letter) {
    if (!await HZ.confirm('外圈／內圈測速', `直接從 ${esc(letter)} 的 10 個位置各讀 128 MB（不寫入任何東西），量出外圈和內圈的速度。<br>測的時候如果有搬檔或其他程式在用這顆硬碟，結果會偏低。`, '開始測速')) return;
    try { await HZ.post('/api/hot/bench', {letter}); } catch (e) { HZ.err(e); return; }
    const box = h('div', {class: 'col'}), msg = h('div', {class: 'muted'}), chart = h('div', {class: 'benchc'});
    box.append(msg, chart);
    const draw = st => {
      msg.textContent = st.msg || ''; chart.innerHTML = '';
      const mx = Math.max(1, ...st.points.map(p => p.mbps));
      for (const p of st.points) chart.append(h('div', {class: 'benchb', title: `${p.pct}% 位置：${p.mbps} MB/s`},
        h('i', {style: {height: (p.mbps / mx * 100) + '%'}}), h('span', {text: Math.round(p.mbps)}), h('em', {text: p.pct + '%'})));
    };
    const dlg = HZ.dialog({title: `📈 ${letter} 外圈／內圈測速`, body: box, width: 620, buttons: [{text: '關閉', value: null, primary: true}]});
    let open = true; dlg.then(() => { open = false; });
    while (open) {
      let st; try { st = await HZ.get('/api/hot/bench'); } catch (e) { break; }
      draw(st);
      if (st.state !== 'running') break;
      await new Promise(r => setTimeout(r, 600));
    }
  };
  HZ.page('hot', T);
})();

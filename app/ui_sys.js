/* HotZone FM — 磁碟 / 設定 / 更新 / 紀錄 */
'use strict';
(function () {
  const {h, esc} = HZ;

  /* ======================================================================= 磁碟 */
  const D = {title: '磁碟', scroll: true, hist: {}};
  D.build = function (root) {
    D.box = h('div');
    root.append(h('h2', {text: '💽 磁碟'}), D.box);
  };
  D.load = async function () {
    let d; try { d = await HZ.get('/api/drives'); } catch (e) { return; }
    HZ.vols = d.vols;
    for (const k of d.disks) { const a = D.hist[k.n] = D.hist[k.n] || []; a.push([k.busy || 0, (k.rd || 0) + (k.wr || 0), k.ours || 0]); if (a.length > 120) a.shift(); }
    if (HZ.isBusy(D.box)) return;
    D.box.innerHTML = '';
    const cards = h('div', {class: 'cards'});
    for (const k of d.disks) {
      const cv = h('canvas', {class: 'spark'});
      cards.append(h('div', {class: 'card'},
        h('div', {class: 'row'}, h('b', {text: `實體磁碟 ${k.n}`, style: {whiteSpace: 'nowrap'}}), h('span', {class: 'pill acc', text: k.media}), k.bus ? h('span', {class: 'pill', text: k.bus}) : null,
          k.smr ? h('span', {class: 'pill warn', text: 'SMR?'}) : null, h('span', {class: 'grow'}), h('b', {class: 'ell', style: {minWidth: '0'}, title: (k.letters || []).join(' '), text: (k.letters || []).join(' ')})),
        h('div', {class: 'small muted ell', text: `${k.model || ''}　${k.size ? HZ.fmtSize(k.size) : ''}`}),
        h('div', {class: 'row small', style: {marginTop: '6px'}}, h('span', {text: '忙碌'}), h('div', {class: 'bar grow'}, h('i', {class: k.busy > 85 ? 'bad' : k.busy > 60 ? 'warn' : '', style: {width: (k.busy || 0) + '%'}})), h('b', {text: k.busy == null ? '—' : Math.round(k.busy) + '%'})),
        h('div', {class: 'small', style: {marginTop: '3px'}, text: `讀 ${HZ.fmtRate(k.rd)}　寫 ${HZ.fmtRate(k.wr)}　本程式 ${HZ.fmtRate(k.ours)}`}),
        cv));
      setTimeout(() => D.spark(cv, D.hist[k.n]), 0);
    }
    D.box.append(cards, h('h3', {text: '磁碟區'}));
    const t = h('table', {class: 't'}, h('tr', {}, ...['磁碟', '名稱', '格式', '類型', '使用量', '可用', '總計', '實體磁碟'].map(x => h('th', {text: x}))));
    for (const v of d.vols) {
      const used = v.total ? (v.total - v.free) / v.total * 100 : 0;
      t.append(h('tr', {}, h('td', {}, h('b', {text: v.letter})), h('td', {text: v.label || ''}), h('td', {text: v.fs || ''}), h('td', {text: ({fixed: '本機', removable: '卸除式', remote: '網路', cdrom: '光碟', ram: 'RAM'})[v.type] || v.type}),
        h('td', {style: {width: '160px'}}, h('div', {class: 'bar'}, h('i', {class: used > 92 ? 'bad' : used > 80 ? 'warn' : '', style: {width: used + '%'}}))),
        h('td', {class: 'num', text: HZ.fmtSize(v.free)}), h('td', {class: 'num', text: HZ.fmtSize(v.total)}), h('td', {text: (v.disks || []).join(', ') + (v.media && v.media !== '?' ? '　' + v.media : '')})));
    }
    D.box.append(t, h('div', {class: 'small muted', style: {marginTop: '8px'}, text: '同一顆實體磁碟上的多個磁碟區（例如 K: 和 L:）在傳輸佇列裡共用同一條通道與使用率上限。'}));
  };
  D.spark = function (cv, a) {
    if (!a) return; const W = cv.clientWidth, H = cv.clientHeight, dpr = devicePixelRatio || 1;
    cv.width = W * dpr; cv.height = H * dpr; const g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.strokeStyle = '#43d9ff'; g.lineWidth = 1.5; g.beginPath();
    a.forEach((p, i) => { const x = W - (a.length - 1 - i) * (W / 119), y = H - p[0] / 100 * (H - 2) - 1; i ? g.lineTo(x, y) : g.moveTo(x, y); }); g.stroke();
    const mx = Math.max(1, ...a.map(p => p[1]));
    g.fillStyle = 'rgba(255,138,61,.35)';
    a.forEach((p, i) => { const x = W - (a.length - 1 - i) * (W / 119), hh = p[2] / mx * (H - 2); g.fillRect(x - 1, H - hh, 2, hh); });
  };
  D.onShow = () => HZ.every('disks', 1500, D.load);
  D.onHide = () => HZ.stop('disks');
  HZ.page('disks', D);

  /* ======================================================================= 設定 */
  const G = {title: '設定', scroll: true};
  G.build = function (root) { G.root = root; };
  G.load = async function () {
    let s, sys;
    try { s = (await HZ.get('/api/settings')).settings; sys = await HZ.get('/api/system'); } catch (e) { HZ.err(e); return; }
    HZ.settings = s;
    const set = async (d, msg, el) => {
      try {
        const r = await HZ.post('/api/settings', d); const saved = (r && r.saved) || d;
        Object.assign(HZ.settings, saved);
        const k = Object.keys(d)[0], adj = k in saved && String(saved[k]) !== String(d[k]);
        if (adj && el) el.value = saved[k];                       // the server kept it in range: show what was stored
        HZ.toast(adj ? `已儲存，但 ${esc(String(d[k]))} 超出範圍，已調整為 ${esc(String(saved[k]))}` : (msg || '已儲存'), adj ? 'warn' : 'ok', adj ? 4000 : 1200);
      } catch (e) { HZ.err(e); }
    };
    const num = (k, w = 70, step = 1) => h('input', {type: 'number', value: s[k], step, style: {width: w + 'px'}, onchange: e => set({[k]: +e.target.value}, null, e.target)});
    const cb = (k, label) => h('label', {class: 'row'}, h('input', {type: 'checkbox', checked: !!s[k], onchange: e => set({[k]: e.target.checked})}), label);
    const sel = (k, opts) => h('select', {onchange: e => set({[k]: e.target.value})}, ...opts.map(([v, t]) => h('option', {value: v, text: t, selected: s[k] === v})));
    const R = (label, ...ctl) => h('div', {class: 'row wrap', style: {margin: '6px 0'}}, h('span', {style: {minWidth: '170px'}, class: 'muted', text: label}), ...ctl);
    const root = G.root; root.innerHTML = '';
    root.append(h('h2', {text: '⚙ 設定'}));

    // ---- remote
    const pw1 = h('input', {type: 'password', placeholder: '新密碼（至少 6 個字）'}), pw0 = h('input', {type: 'password', placeholder: '目前的密碼'});
    const ts = sys.tailscale || {};
    const url = (u, label) => u ? h('div', {class: 'row wrap'}, h('span', {class: 'muted', style: {minWidth: '120px'}, text: label}), h('code', {class: 'mono', style: {wordBreak: 'break-all', minWidth: '0'}, text: u}), h('button', {class: 'sm', onclick: () => HZ.copyText(u)}, '複製'),
      label !== '這台電腦' ? h('button', {class: 'sm', onclick: () => HZ.dialog({title: '用手機掃描', body: `<div style="text-align:center"><img src="/api/qr?${new URLSearchParams({text: u})}" style="width:260px;height:260px;image-rendering:pixelated;border-radius:8px"><div class="mono small" style="margin-top:8px">${esc(u)}</div><div class="small muted">手機要先連上同一個 Wi-Fi${label === 'Tailscale' ? '，或打開 Tailscale' : ''}</div></div>`})}, '📱 QR') : null) : null;
    root.append(h('h3', {text: '🌐 遠端連線（區網 / Tailscale）'}), h('div', {class: 'card'},
      h('div', {class: 'small muted', html: '手機或另一台電腦用瀏覽器開下面的網址，就能用和這裡一樣的介面管理檔案（瀏覽、搜尋、搬檔、熱處理、上傳下載）。出門在外請用 <b>Tailscale</b>：兩邊裝 Tailscale 並登入同一個帳號即可，流量不限、不用開路由器。'}),
      h('div', {class: 'col', style: {margin: '8px 0'}}, url(sys.local, '這台電腦'), url(sys.lan, '同一個區網'), url(sys.ts_url, 'Tailscale'),
        !ts.installed ? h('div', {class: 'small warn', text: 'Tailscale 尚未安裝：到 tailscale.com 下載，登入後重新整理這頁。'}) : null,
        ts.installed && !ts.https && HZ.local ? h('div', {class: 'row small'}, h('span', {class: 'muted', text: '想在手機裝成 App（https）？'}), h('button', {class: 'sm', onclick: async () => {
          try { const r = await HZ.post('/api/system/tailscale', {}); if (r.enable_url) { window.open(r.enable_url); HZ.alert('Tailscale HTTPS', '請在打開的 Tailscale 網頁按「Enable」開啟 HTTPS，完成後回來再按一次。'); } else if (r.ok) { HZ.toast('已開啟 Tailscale HTTPS', 'ok'); G.load(); } else HZ.alert('Tailscale', esc(r.out)); } catch (e) { HZ.err(e); }
        }}, '開啟 Tailscale HTTPS')) : null),
      R('允許遠端連線', h('label', {class: 'row'}, h('input', {type: 'checkbox', checked: !!s['web.remote'], disabled: !HZ.local, onchange: e => set({'web.remote': e.target.checked}, '已儲存，伺服器重新啟動中')}), '開放（需要密碼）')),
      R('連接埠', h('input', {type: 'number', value: s['web.port'], disabled: !HZ.local, style: {width: '90px'}, onchange: e => set({'web.port': +e.target.value}, '已儲存，伺服器換到新的埠')}), sys.web_err ? h('span', {class: 'bad small', text: sys.web_err}) : null),
      R('網頁密碼', h('span', {class: s['web.pw_set'] ? 'ok' : 'warn', text: s['web.pw_set'] ? '已設定' : '還沒設定（遠端無法登入）'}), (!HZ.local && s['web.pw_set']) ? pw0 : null, pw1,
        h('button', {class: 'sm', onclick: async () => {
          if (!pw1.value) { HZ.toast('請先輸入新密碼', 'bad'); pw1.focus(); return; }
          try { await HZ.post('/api/password', {old: pw0.value, new: pw1.value}); pw0.value = pw1.value = ''; HZ.toast('密碼已更新，其他裝置要重新登入', 'ok'); G.load(); } catch (e) { HZ.err(e); } }}, '設定密碼'),
        s['web.pw_set'] && HZ.local ? h('button', {class: 'sm', onclick: async () => { if (await HZ.confirm('清除密碼', '清除後遠端裝置將無法登入。')) { try { await HZ.post('/api/password', {clear: true}); HZ.toast('密碼已清除', 'ok'); G.load(); } catch (e) { HZ.err(e); } } }}, '清除') : null),
      R('登入保持', num('web.session_days', 60), h('span', {class: 'muted', text: '天'})),
      R('其他網址名稱', h('input', {value: (s['web.hosts'] || []).join(', '), placeholder: '例如 files.example.com（用自己的網域連線時才需要）', style: {width: '320px'},
        onchange: e => set({'web.hosts': e.target.value.split(/[,\s]+/).map(x => x.trim().toLowerCase()).filter(Boolean)})}),
        h('span', {class: 'small muted', text: 'IP、電腦名稱、*.ts.net 一律可以連；其他名稱要列在這裡（防止惡意網頁冒用）'}))));

    // ---- engine
    root.append(h('h3', {text: '🖥 背景引擎'}), h('div', {class: 'card'},
      h('div', {class: 'kv small'}, h('b', {text: '權限'}), h('span', {class: sys.admin ? 'ok' : 'warn', text: sys.admin ? '系統管理員（可以搬移磁區、讀 MFT）' : '一般權限（熱區搬移與 MFT 索引無法使用）'}),
        h('b', {text: '版本'}), h('span', {text: `V${HZ.st ? HZ.st.ver : ''}　Python ${sys.python}　啟動器 ${sys.launcher_version}　${sys.mode}`}),
        h('b', {text: '執行'}), h('span', {text: `PID ${sys.pid}　已執行 ${HZ.fmtEta(Date.now() / 1000 - sys.started)}`}), h('b', {text: '電腦'}), h('span', {text: `${sys.host}　${sys.platform}`})),
      sys.autostart.supported ? R('開機自動啟動', h('label', {class: 'row'}, h('input', {type: 'checkbox', checked: sys.autostart.on, disabled: !HZ.local, onchange: async e => {
        try { await HZ.post('/api/system/autostart', {on: e.target.checked}); HZ.toast(e.target.checked ? '已設定：登入 Windows 時自動在背景啟動（不會跳 UAC）' : '已取消開機自動啟動', 'ok'); } catch (er) { HZ.err(er); e.target.checked = !e.target.checked; }
      }}), '登入 Windows 時以系統管理員身分在背景啟動（工作排程器，不跳 UAC）')) : null,
      HZ.local ? h('div', {class: 'row', style: {marginTop: '8px'}}, h('button', {onclick: async () => { if (await HZ.confirm('重新啟動背景引擎', '正在進行的搬檔會暫停並在重新啟動後從中斷處繼續。')) HZ.post('/api/system/restart', {}).then(() => HZ.toast('重新啟動中…')).catch(HZ.err); }}, '⟳ 重新啟動背景引擎'),
        h('button', {onclick: async () => { if (await HZ.confirm('結束背景引擎', '結束後搬檔、熱區搬移與遠端連線都會停止，直到下次開啟程式。')) HZ.post('/api/system/quit', {}).then(() => HZ.toast('背景引擎已結束')).catch(HZ.err); }}, '⏻ 結束背景引擎')) : null,
      h('div', {class: 'row', style: {marginTop: '8px'}}, h('button', {class: 'primary', onclick: () => HZ.selftest()}, '🩺 自我檢查'), h('button', {onclick: () => HZ.welcome()}, '👋 開始使用導覽'), h('button', {title: '紀錄檔、設定（不含密碼）、各功能狀態、最近一次自我檢查，打包成一個 zip，有問題時傳給開發者', onclick: () => { location.href = '/api/diag'; }}, '📦 匯出診斷資料'),
        h('span', {class: 'small muted', text: '檢查這台電腦上熱處理、索引、圖片分類需要的東西是不是都正常，結果可以複製傳給開發者。'}))));

    // ---- transfer
    root.append(h('h3', {text: '⇅ 傳輸佇列'}), h('div', {class: 'card'},
      R('同時進行的工作（全部）', num('transfer.max_total')), R('每顆 HDD 同時', num('transfer.hdd_max'), h('span', {class: 'muted small', text: '一般硬碟建議 1（一次一筆最快）'})),
      R('每顆 SSD 同時', num('transfer.ssd_max')), R('每個網路磁碟同時', num('transfer.net_max')),
      R('磁碟最高使用率', num('transfer.usage_pct', 70, 5), h('span', {class: 'muted', text: '%（像 FastCopy，每顆磁碟可在佇列頁另外設定）'})),
      R('速度上限', num('transfer.mbps_cap', 80, 10), h('span', {class: 'muted', text: 'MB/s（0 = 不限）'})),
      R('白天限速', cb('transfer.sched_on', '啟用：'), num('transfer.sched_from', 56), h('span', {class: 'muted', text: '點到'}), num('transfer.sched_to', 56),
        h('span', {class: 'muted', text: '點之間，使用率最多'}), num('transfer.sched_pct', 60, 5), h('span', {class: 'muted', text: '%、速度最多'}), num('transfer.sched_mbps', 70, 10),
        h('span', {class: 'muted', text: 'MB/s（0 = 不另外限）。晚上自動恢復全速。'})),
      R('讓路', num('transfer.yield_mbps', 70), h('span', {class: 'muted', text: 'MB/s：其他程式讀寫超過這個速度時暫停佇列（0 = 不讓）'})),
      R('緩衝區', num('transfer.buffer_mb', 70), h('span', {class: 'muted', text: 'MB'})),
      R('同名檔案', sel('transfer.conflict', [['ask', '問我'], ['skip', '略過'], ['overwrite', '覆蓋'], ['newer', '較新才覆蓋'], ['rename', '保留兩者']])),
      h('div', {class: 'row wrap'}, cb('transfer.write_through', '直接寫入磁碟（不先塞進記憶體，使用率控制才準）'), cb('transfer.verify', '複製後校驗'), cb('transfer.preserve_times', '保留時間與屬性'),
        cb('transfer.hot_first', '目的地是熱資料夾的工作優先'), cb('transfer.autostart', '程式啟動時繼續未完成的工作')),
      R('已結束的工作保留', num('transfer.keep_done', 80), h('span', {class: 'muted', text: '筆'}))));

    // ---- index
    let ix = {vols: []}; try { ix = await HZ.get('/api/index'); } catch (e) { }
    const drv = h('input', {value: (s['index.drives'] || []).join(', '), placeholder: '空白 = 所有本機磁碟', style: {width: '320px'}});
    const exc = h('input', {value: (s['index.exclude'] || []).join(', '), style: {width: '320px'}});
    const itab = h('table', {class: 't', style: {marginTop: '8px'}}, h('tr', {}, ...['磁碟', '狀態', '方式', '檔案', '資料夾', '建立時間', ''].map(x => h('th', {text: x}))));
    for (const v of ix.vols) itab.append(h('tr', {}, h('td', {text: v.key}), h('td', {text: v.state === 'building' ? `建立中 ${v.progress ? Math.round(v.progress * 100) + '%' : v.msg}` : v.state === 'ready' ? (v.live ? '⚡ 即時更新' : '✓ 完成') : v.state}),
      h('td', {text: v.method === 'mft' ? 'MFT + USN' : v.method === 'scan' ? '掃描' : ''}), h('td', {class: 'num', text: (v.files || 0).toLocaleString()}), h('td', {class: 'num', text: (v.dirs || 0).toLocaleString()}),
      h('td', {text: HZ.fmtAgo(v.built)}), h('td', {}, h('button', {class: 'sm', onclick: () => HZ.post('/api/index/rebuild', {key: v.key}).then(() => HZ.toast('重新建立中'))}, '重建'))));
    root.append(h('h3', {text: '🔍 索引（搜尋與空間分析）'}), h('div', {class: 'card'},
      h('div', {class: 'row wrap'}, cb('index.enabled', '啟用索引'), cb('index.create_journal', 'NTFS 沒有變更日誌時自動建立（即時更新需要）')),
      R('要索引的磁碟／資料夾', drv, h('button', {class: 'sm', onclick: () => set({'index.drives': drv.value.split(',').map(x => x.trim()).filter(Boolean)})}, '儲存')),
      R('排除的名稱', exc, h('button', {class: 'sm', onclick: () => set({'index.exclude': exc.value.split(',').map(x => x.trim()).filter(Boolean)})}, '儲存')),
      R('非 NTFS 重新掃描間隔', num('index.rescan_min'), h('span', {class: 'muted', text: '分鐘'})), itab));

    // ---- vault
    root.append(h('h3', {text: '🛟 保管區（防止檔案不見）'}), h('div', {class: 'card'},
      h('div', {class: 'small muted', text: '覆蓋、取代、移走、刪除之前，原本的檔案一律先放進保管區（同一顆硬碟的 .HotZoneVault，瞬間完成）。只有確認三次的「永久刪除」不會留。'}),
      R('保管天數', num('vault.days', 70), h('span', {class: 'muted', text: '天，之後移到「待你決定」'})),
      h('div', {class: 'small muted', text: '跨磁碟移動完成後，來源硬碟上的原檔也一律先放進那顆硬碟的保管區（要騰出空間時，到「保管區」頁面確認三次清掉）。'})));

    // ---- images
    root.append(h('h3', {text: '🎨 圖片分類（背景分析）'}), h('div', {class: 'card'},
      h('div', {class: 'row wrap'}, cb('images.enabled', '啟用背景分析'), cb('images.faces', '偵測人臉（OpenCV，不分辨是誰）'), cb('images.yield_queue', '傳輸佇列在工作時先暫停')),
      R('CPU 使用率', num('images.usage_pct', 70), h('span', {class: 'muted', text: '%（60 = 做 0.6 秒休息 0.4 秒）'})),
      R('同時分析', num('images.threads', 70), h('span', {class: 'muted', text: '張（CPU 核心多可以加到 4；1 = 最安靜）'})),
      h('div', {class: 'small muted', text: '要分析哪些資料夾，在「圖片分類」頁面右上角「分析的資料夾」設定。'})));

    // ---- ui
    root.append(h('h3', {text: '🎨 介面'}), h('div', {class: 'card'},
      R('主題', h('select', {onchange: e => { HZ.applyTheme(e.target.value, s['ui.zoom']); set({'ui.theme': e.target.value}); }}, h('option', {value: 'dark', text: '深色', selected: s['ui.theme'] !== 'light'}), h('option', {value: 'light', text: '淺色', selected: s['ui.theme'] === 'light'}))),
      R('介面大小', h('select', {onchange: e => { HZ.applyTheme(s['ui.theme'], +e.target.value); set({'ui.zoom': +e.target.value}); }}, ...[80, 90, 100, 110, 120, 135, 150].map(z => h('option', {value: z, text: z + '%', selected: (s['ui.zoom'] || 100) == z})))),
      h('div', {class: 'row wrap'}, cb('explorer.show_hidden', '顯示隱藏檔案'), cb('explorer.dual', '預設雙窗格')),
      !HZ.local ? h('div', {class: 'row', style: {marginTop: '8px'}}, h('button', {onclick: () => HZ.post('/api/logout').then(() => location.reload())}, '登出這個裝置')) : null));

    // ---- backup of the settings
    const imp = h('input', {type: 'file', accept: '.json', style: {display: 'none'}, onchange: async e => {
      const f = e.target.files[0]; if (!f) return;
      let d; try { d = JSON.parse(await f.text()); } catch (er) { HZ.toast('不是有效的設定檔', 'bad'); return; }
      const st = Object.assign({}, d.settings || d); delete st['web.pw_set'];
      if (!HZ.local) { delete st['web.port']; delete st['web.remote']; }                  // connection settings: only on that PC
      if (!await HZ.confirm('匯入設定', `要用這個檔案的 ${Object.keys(st).length} 項設定取代目前的設定嗎？（熱資料夾、我的最愛、佇列與熱處理的參數…；密碼、還原點同意、「完成後關機」不會帶過來；目前的設定會先另存一份）`, '匯入')) return;
      try { const r = await HZ.post('/api/settings/import', {settings: st}); HZ.toast(`已匯入 ${r.n} 項` + (r.skipped.length ? `（${r.skipped.length} 項不正確，略過）` : '') + '，重新整理頁面', 'ok'); setTimeout(() => location.reload(), 1200); } catch (er) { HZ.err(er); }
    }});
    root.append(h('h3', {text: '💾 設定備份'}), h('div', {class: 'card'},
      h('div', {class: 'small muted', text: '把所有設定（熱資料夾、我的最愛、佇列、熱處理、圖片分類…，不含密碼）存成一個檔案；重灌或換電腦後可以匯入。'}),
      h('div', {class: 'row', style: {marginTop: '8px'}}, h('button', {onclick: async () => {
        const d = await HZ.get('/api/settings'); const st = Object.assign({}, d.settings); delete st['web.pw_set'];
        const a = h('a', {href: URL.createObjectURL(new Blob([JSON.stringify({app: 'HotZone FM', ver: HZ.st && HZ.st.ver, t: new Date().toISOString(), settings: st}, null, 1)], {type: 'application/json'})),
          download: `HotZoneFM_設定_${new Date().toLocaleDateString('sv')}.json`}); document.body.append(a); a.click(); a.remove();
      }}, '⬇ 匯出設定'), h('button', {onclick: () => imp.click()}, '⬆ 匯入設定'), imp)));
  };
  G.onShow = G.load;
  HZ.page('settings', G);

  /* ======================================================================= 更新 */
  const U = {title: '更新', scroll: true};
  U.build = function (root) {
    U.root = root;
    root.addEventListener('dragover', e => { e.preventDefault(); });
    root.addEventListener('drop', e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) U.upload(f); });
  };
  U.load = async function () {
    let d; try { d = await HZ.get('/api/update'); } catch (e) { HZ.err(e); return; }
    U.d = d; const root = U.root; root.innerHTML = '';
    root.append(h('h2', {text: '⟳ 線上更新'}));
    const pick = h('input', {type: 'file', accept: '.zip', style: {display: 'none'}, onchange: e => e.target.files[0] && U.upload(e.target.files[0])});
    root.append(h('div', {class: 'card'},
      h('div', {class: 'row wrap'}, h('b', {style: {fontSize: '15px'}, text: `目前版本 V${d.ver}`}), h('span', {class: 'grow'}),
        d.folder ? h('button', {class: 'primary', onclick: () => HZ.post('/api/update/folder').then(r => U.show(r.pkg)).catch(HZ.err)}, `使用 UPDATE 資料夾的 V${d.folder.version}`) : null,
        HZ.local ? h('button', {onclick: () => pick.click()}, '選擇更新包…') : null, pick),
      h('div', {class: 'small muted', style: {marginTop: '6px'}, html: '把 <b>v版本_Update.zip</b> 拖進這一頁、按「選擇更新包」，或放進程式資料夾的 <b>UPDATE</b> 資料夾。<br>更新時搬檔、熱區搬移、索引和遠端連線都<b>不會中斷</b>：舊版在安全的時間點停下、交接給新版後繼續；新版有問題會自動還原。<br>為了安全，更新包只能在這台電腦上傳；手機可以套用已經放在 UPDATE 資料夾裡的更新。'}),
      U.box = h('div', {style: {marginTop: '10px'}})));
    if (d.pending) U.show(d.pending);
    const st = d.state || {};
    if (st.state === 'applying') U.box.append(h('div', {class: 'ask', text: `正在更新到 V${st.to}…`}));
    if (st.state === 'failed') U.box.append(h('div', {class: 'ask', style: {borderColor: 'var(--bad)'}, html: `<b class="bad">上次更新失敗</b>：${esc(st.message || '')}`}));
    // backups
    root.append(h('h3', {text: '退回之前的版本'}));
    const bt = h('table', {class: 't'}, h('tr', {}, h('th', {text: '備份'}), h('th', {text: '版本'}), h('th', {text: '時間'}), h('th', {text: ''})));
    for (const b of d.backups) bt.append(h('tr', {}, h('td', {class: 'mono small', style: {wordBreak: 'break-all'}, text: b.name}), h('td', {text: 'V' + b.version}), h('td', {text: HZ.fmtDate(b.t)}),
      h('td', {}, h('button', {class: 'sm', onclick: () => HZ.post('/api/update/rollback', {name: b.name}).then(r => U.show(r.pkg)).catch(HZ.err)}, '退回這版'))));
    root.append(d.backups.length ? h('div', {class: 'card', style: {overflowX: 'auto'}}, bt) : h('div', {class: 'muted small', text: '還沒有備份（每次更新前會自動備份）。'}));
    // changelog
    root.append(h('h3', {text: '更新紀錄'}));
    const cl = h('div', {class: 'card'});
    for (const e of d.changelog.slice(0, 40)) cl.append(h('div', {style: {marginBottom: '8px'}}, h('b', {text: `V${e.version}`}), h('span', {class: 'muted small', text: '　' + (e.date || '')}),
      ...(e.items || []).map(i => h('div', {class: 'small', text: '・' + i}))));
    root.append(cl);
  };
  U.upload = async function (f) {
    if (!HZ.local) { HZ.toast('為了安全，更新包只能在這台電腦上傳', 'bad'); return; }
    U.box.innerHTML = '<div class="muted">讀取更新包…</div>';
    try {
      const r = await fetch('/api/update/upload?name=' + encodeURIComponent(f.name), {method: 'PUT', body: f, headers: {'X-HZ': '1'}});
      const j = await r.json(); if (!r.ok || !j.ok) throw new Error(j.error || '無法讀取');
      U.show(j.pkg);
    } catch (e) { U.box.innerHTML = `<div class="ask" style="border-color:var(--bad)"><b class="bad">無法使用這個更新包：</b>${esc(e.message)}</div>`; }
  };
  U.show = function (p) {
    const dir = {up: '升級', same: '相同版本', down: '⚠ 降版'}[p.direction] || '';
    U.box.innerHTML = '';
    U.box.append(h('div', {class: 'ask', style: {borderColor: 'var(--accent)', background: 'color-mix(in srgb,var(--accent) 8%,transparent)'}},
      h('div', {html: `<b>V${esc(p.from)} → V${esc(p.version)}</b>　（${dir}）　${esc(p.src_name || '')}`}),
      (p.notes || []).length ? h('div', {class: 'small', style: {margin: '6px 0'}}, ...p.notes.map(n => h('div', {text: '・' + n}))) : null,
      h('div', {class: 'small muted', text: `變更的檔案：${(p.changed || []).join('、') || '（沒有變更）'}`}),
      p.shell_changed ? h('div', {class: 'small warn', text: '包含視窗外殼的變更：背景工作立即更新，視窗重開後完全生效。'}) : null,
      p.has_launcher ? h('div', {class: 'small warn', text: '包含啟動器變更：下次開啟程式時生效。'}) : null,
      h('div', {class: 'row', style: {marginTop: '8px'}}, h('button', {class: 'primary', onclick: U.apply}, '開始更新'), h('button', {onclick: () => HZ.post('/api/update/cancel').then(U.load)}, '取消'))));
  };
  U.apply = async function () {
    try { await HZ.post('/api/update/apply', {}); } catch (e) { HZ.err(e); return; }
    const ov = $('#overlay'); ov.innerHTML = '<div class="dlg" style="padding:24px 34px;text-align:center;font-size:16px;font-weight:800">⟳ 正在載入新版本…<div class="small muted" style="margin-top:6px;font-weight:400">搬檔與熱區搬移持續進行，不會中斷</div></div>'; ov.classList.add('on');
    const t0 = Date.now(), gen0 = HZ.st ? HZ.st.gen : -1;
    while (Date.now() - t0 < 60000) {
      await new Promise(r => setTimeout(r, 700));
      try {
        const p = await fetch('/api/ping').then(r => r.json());
        const u = await HZ.get('/api/update');
        if (u.state && u.state.state === 'failed') { ov.classList.remove('on'); HZ.alert('更新失敗', esc(u.state.message || '')); U.load(); return; }
        if (p.gen !== gen0 || (u.state && u.state.state === 'done')) { location.reload(); return; }
      } catch (e) { }
    }
    ov.classList.remove('on'); HZ.toast('更新時間比預期久，請稍後重新整理', 'bad');
  };
  const $ = s => document.querySelector(s);
  U.onShow = U.load;
  HZ.page('update', U);

  /* ======================================================================= 紀錄 */
  const L = {title: '紀錄', rows: [], last: 0, tab: 'ops'};
  L.build = function (root) {
    L.tabs = h('div', {class: 'chips'}, ...[['ops', '操作紀錄'], ['log', '程式紀錄']].map(([k, t]) => h('span', {class: 'chip' + (k === L.tab ? ' on' : ''), 'data-k': k, text: t,
      onclick: () => { L.tab = k; for (const c of L.tabs.children) c.classList.toggle('on', c.dataset.k === k); L.render(); }})));
    L.filter = h('input', {placeholder: '篩選…', oninput: HZ.debounce(() => L.render(), 250)});
    L.lv = h('select', {onchange: () => L.render()}, h('option', {value: '', text: '全部'}), h('option', {value: 'WARN', text: '警告以上'}), h('option', {value: 'ERROR', text: '只有錯誤'}));
    L.box = h('div', {class: 'list', style: {padding: '6px 12px', fontSize: '12px'}});
    root.append(h('div', {class: 'sbox'}, h('b', {text: '📜 紀錄'}), L.tabs, L.filter, L.lv, h('span', {class: 'grow'}), h('span', {class: 'small muted', text: '所有搬移、刪除、改名都會記在這裡，可以搜尋；有問題時可在「設定」匯出診斷資料傳給開發者', title: '操作紀錄：Data\\safety.sqlite3　程式紀錄：LOG\\engine.log'})), L.box);
  };
  L.load = async function () {
    try { const r = await HZ.get('/api/log', {since: L.last}); if (r.rows.length) { L.rows = L.rows.concat(r.rows).slice(-1500); L.last = L.rows[L.rows.length - 1].n; L.render(); } } catch (e) { }
  };
  L.ops = async function () {
    let r; try { r = await HZ.get('/api/journal', {q: L.filter.value, limit: 400}); } catch (e) { return; }
    const K = {job: '佇列', vault: '保管區', restore: '還原', purge: '永久刪除', rename: '重新命名', undo: '復原'};
    L.box.innerHTML = '';
    for (const x of r.rows) {
      const det = x.detail ? h('details', {}, h('summary', {class: 'small muted', text: '詳細'}), h('pre', {class: 'small mono', style: {whiteSpace: 'pre-wrap', margin: '4px 0'}, text: JSON.stringify(x.detail, null, 1)})) : null;
      L.box.append(h('div', {style: {padding: '4px 0', borderBottom: '1px solid var(--grid)'}}, h('span', {class: 'muted', text: HZ.fmtDate(x.t) + '　'}),
        h('span', {class: 'pill ' + (x.kind === 'purge' ? 'bad' : x.kind === 'vault' ? 'warn' : ''), text: K[x.kind] || x.kind}), ' ', x.text, det));
    }
    if (!r.rows.length) L.box.append(h('div', {class: 'empty', text: '還沒有紀錄'}));
  };
  L.render = function () {
    L.lv.style.display = L.tab === 'ops' ? 'none' : '';
    if (L.tab === 'ops') { if (!HZ.isBusy(L.box)) L.ops(); return; }
    const f = L.filter.value.toLowerCase(), lv = L.lv.value;
    const rows = L.rows.filter(r => (!lv || (lv === 'WARN' ? r.lv !== 'INFO' : r.lv === 'ERROR')) && (!f || (r.m + r.a).toLowerCase().includes(f)));
    const atBottom = L.box.scrollTop + L.box.clientHeight >= L.box.scrollHeight - 20;
    L.box.innerHTML = rows.slice(-600).map(r => `<div style="white-space:pre-wrap;padding:2px 0;border-bottom:1px solid var(--grid)"><span class="muted">${HZ.fmtDate(r.t).slice(5)}:${String(new Date(r.t * 1000).getSeconds()).padStart(2, '0')}</span> <b class="${r.lv === 'ERROR' ? 'bad' : r.lv === 'WARN' ? 'warn' : 'muted'}">${r.lv}</b> <span class="pill">${esc(r.a)}</span> ${esc(r.m)}</div>`).join('');
    if (atBottom) L.box.scrollTop = L.box.scrollHeight;
  };
  L.onShow = () => HZ.every('log', 3000, () => { if (L.tab === 'ops') L.render(); else L.load(); });
  L.onHide = () => HZ.stop('log');
  HZ.page('log', L);
})();

HZ.selftest = async function () {
  const go = await HZ.dialog({title: '🩺 自我檢查', body: '會檢查權限、模組、資料庫、網頁伺服器，以及熱處理資料夾所在硬碟的 NTFS 功能。<br><br>' +
    '搬移測試會在那顆硬碟的隱藏保管區建立一個 <b>8 MB 的測試檔</b>，把它搬到硬碟前段、確認內容一模一樣後刪掉。<b>不會動到你的任何檔案。</b>',
    buttons: [{text: '取消', value: null}, {text: '只做基本檢查', value: 'basic'}, {text: '完整檢查（含搬移測試）', value: 'full', primary: true}]});
  if (!go) return;
  HZ.toast('檢查中…');
  let r; try { r = await HZ.post('/api/selftest', {move: go === 'full'}); } catch (e) { HZ.err(e); return; }
  const bad = r.checks.filter(c => c.ok === false).length;
  try { if (!bad) localStorage.setItem('hz.selftest.ok', '1'); } catch (e) { }
  const body = h('div', {class: 'col'},
    h('div', {class: bad ? 'warn' : 'ok', text: bad ? `有 ${bad} 項沒通過` : '全部通過 ✓'}),
    ...r.checks.map(c => h('div', {class: 'stc'}, h('span', {class: 'stm ' + (c.ok === true ? 'ok' : c.ok === false ? 'bad' : 'muted'), text: c.ok === true ? '✓' : c.ok === false ? '✗' : '－'}),
      h('div', {}, h('b', {text: c.name}), h('div', {class: 'small muted', text: c.detail})))));
  const v = await HZ.dialog({title: '🩺 自我檢查結果', body, width: 640, buttons: [{text: '複製報告', value: 'copy'}, {text: '關閉', value: null, primary: true}]});
  if (v === 'copy') HZ.copyText(r.text);
};

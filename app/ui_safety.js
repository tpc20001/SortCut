/* HotZone FM — 保管區 (vault), 重複檔案 (duplicates) */
'use strict';
(function () {
  const {h, esc} = HZ;

  /* ======================================================================= 保管區 */
  const V = {title: '保管區', stage: 'keep', sel: new Set(), q: ''};
  const ACT = {overwrite: '被覆蓋', move_src: '移動後的原檔', delete: '刪除', upload_overwrite: '上傳時被覆蓋', remux: '轉 MP4 後的原檔'};
  V.build = function (root) {
    V.head = h('div', {class: 'sbox'});
    V.tabs = h('div', {class: 'chips'});
    V.qEl = h('input', {placeholder: '搜尋原本的位置或原因…', style: {minWidth: '240px'}, oninput: HZ.debounce(() => { V.q = V.qEl.value; V.load(); }, 250)});
    V.acts = h('div', {class: 'row wrap'});
    V.info = h('div', {class: 'sinfo'});
    V.list = h('div', {class: 'list'});
    root.append(h('div', {class: 'sbox', style: {flexDirection: 'column', alignItems: 'stretch'}},
      h('div', {class: 'small muted', html: '程式在<b>覆蓋、取代、移走或刪除</b>檔案之前，都會先把原本的檔案搬到同一顆硬碟的隱藏資料夾 <code>.HotZoneVault</code> 保管（同一顆硬碟內只是改位置，瞬間完成、不佔額外空間）。保管期滿會移到「待你決定」，由你決定要不要留。'}),
      h('div', {class: 'row wrap'}, V.tabs, h('span', {class: 'grow'}), V.qEl), V.actEl = h('div', {class: 'chips'}), V.acts), V.info, V.list);
  };
  V.renderTabs = function (stats) {
    V.tabs.innerHTML = '';
    for (const [k, t] of [['keep', '保管中'], ['review', '待你決定'], ['restored', '已還原'], ['purged', '已永久刪除']]) {
      const st = (stats || {})[k] || {n: 0, size: 0};
      V.tabs.append(h('span', {class: 'chip' + (V.stage === k ? ' on' : ''), onclick: () => { V.stage = k; V.sel.clear(); V.load(); }},
        `${t}　${st.n.toLocaleString()}` + (st.size && (k === 'keep' || k === 'review') ? `（${HZ.fmtSize(st.size)}）` : '')));
    }
  };
  V.load = async function () {
    let d; try { d = await HZ.get('/api/vault', {stage: V.stage, q: V.q, limit: 500, action: V.action || ''}); } catch (e) { HZ.err(e); return; }
    V.d = d; V.renderTabs(d.stats);
    if (V.actEl) {
      V.actEl.innerHTML = '';
      if ((d.actions || []).length > 1 || V.action) {
        V.actEl.append(h('span', {class: 'chip' + (!V.action ? ' on' : ''), onclick: () => { V.action = ''; V.load(); }}, '全部原因'));
        for (const [a, n, sz] of d.actions) V.actEl.append(h('span', {class: 'chip' + (V.action === a ? ' on' : ''), title: HZ.fmtSize(sz), onclick: () => { V.action = V.action === a ? '' : a; V.load(); }}, `${ACT[a] || a} ${n.toLocaleString()}`));
      }
    }
    V.acts.innerHTML = '';
    const live = V.stage === 'keep' || V.stage === 'review';
    if (live) V.acts.append(
      h('button', {onclick: () => V.act('restore')}, '↩ 還原選取的'),
      h('button', {onclick: () => V.act('extend')}, `⏳ 再保管 ${d.days} 天`),
      h('button', {class: 'danger', onclick: () => V.purge()}, '永久刪除選取的'),
      h('span', {class: 'small muted', text: '還原會放回原本的位置；那裡已經有檔案時，會取名為「名稱 (還原)」，不會蓋掉任何東西。'}));
    V.info.innerHTML = `<span>${d.total.toLocaleString()} 個項目</span><span>${HZ.fmtSize(d.size)}</span>` + (V.stage === 'keep' ? `<span>保管 ${d.days} 天後移到「待你決定」（可在設定裡改天數）</span>` : '');
    V.list.innerHTML = '';
    if (!d.items.length) { V.list.append(h('div', {class: 'empty', text: V.stage === 'review' ? '沒有等你決定的項目' : '這裡是空的'})); return; }
    const all = h('input', {type: 'checkbox', checked: d.items.length > 0 && d.items.every(x => V.sel.has(x.id)),
      title: d.total > d.items.length ? `勾選這裡顯示的 ${d.items.length} 項（共 ${d.total} 項；可以用上面的搜尋縮小範圍）` : '全選／全不選',
      onchange: e => { V.sel = new Set(e.target.checked ? d.items.map(x => x.id) : []); V.load(); }});
    V.list.append(h('div', {class: 'vrow vhead', style: {color: 'var(--header_text)', background: 'var(--header_bg)', position: 'sticky', top: '0'}},
      live ? all : h('span'), h('span', {text: '項目'}), h('span', {class: 'c3', text: '原因'}), h('span', {class: 'num', text: '大小'}), h('span', {class: 'c5', text: '時間'}), h('span', {class: 'c6', text: V.stage === 'keep' ? '剩下' : ''})));
    for (const it of d.items) {
      const cb = h('input', {type: 'checkbox', checked: V.sel.has(it.id), onchange: e => e.target.checked ? V.sel.add(it.id) : V.sel.delete(it.id)});
      V.list.append(h('div', {class: 'vrow', title: `原本：${it.orig}\n保管在：${it.vpath}`},
        live ? cb : h('span'),
        h('div', {class: 'row', style: {minWidth: 0}}, (() => {
          const ext = (HZ.base(it.orig).split('.').pop() || '').toLowerCase();
          if (!it.is_dir && it.exists && /^(jpe?g|png|webp|gif|bmp|tiff?|heic|mp4|mkv|mov|avi|webm|m4v)$/.test(ext)) {
            const im = h('img', {class: 'vthumb', loading: 'lazy', src: '/api/thumb?' + new URLSearchParams({path: it.vpath, s: 96}), onclick: e => { e.stopPropagation(); window.open(HZ.fileUrl(it.vpath), '_blank'); }});
            im.onerror = () => im.replaceWith(h('span', {html: HZ.icon({ext})}));
            return im;
          }
          return h('span', {html: HZ.icon({dir: it.is_dir, ext})});
        })(),
          h('div', {style: {minWidth: 0}}, h('div', {class: 'ell', text: HZ.base(it.orig)}), h('div', {class: 'small muted ell', text: HZ.dir(it.orig)}))),
        h('div', {class: 'why c3'}, h('span', {class: 'pill', text: ACT[it.action] || it.action}), ' ', it.reason, !it.exists && live ? h('span', {class: 'bad', text: '（保管區裡找不到這個檔案）'}) : null),
        h('span', {class: 'num', text: HZ.fmtSize(it.size)}), h('span', {class: 'c5 muted', text: HZ.fmtDate(it.t)}),
        h('span', {class: 'c6'}, it.days_left != null ? `${Math.ceil(it.days_left)} 天` : '',
          live ? h('button', {class: 'sm', style: {marginLeft: '6px'}, onclick: () => { V.sel = new Set([it.id]); V.act('restore'); }}, '還原') : null,
          live && it.exists ? h('button', {class: 'sm ghost', title: '打開保管的位置', onclick: () => HZ.pages.explorer && (HZ.go('explorer'), HZ.pages.explorer.open(HZ.dir(it.vpath), HZ.base(it.vpath)))}, '📂') : null)));
    }
  };
  V.act = async function (act, extra) {
    if (!V.sel.size) { HZ.toast('請先勾選項目'); return; }
    try {
      const r = await HZ.post('/api/vault/action', Object.assign({act, ids: [...V.sel]}, extra || {}));
      HZ.toast({restore: '已還原', extend: '已延長保管', purge: '已永久刪除'}[act] + ` ${r.done} 個` + (r.errors.length ? `，${r.errors.length} 個失敗：${esc(r.errors[0])}` : ''), r.errors.length ? 'bad' : 'ok', 5000);
      V.sel.clear(); V.load(); HZ.refreshViews();
    } catch (e) { HZ.err(e); }
  };
  V.purge = async function () {
    if (!V.sel.size) { HZ.toast('請先勾選項目'); return; }
    const items = V.d.items.filter(x => V.sel.has(x.id));
    const size = items.reduce((a, x) => a + x.size, 0);
    for (const [pos, t, b, ok] of [['tl', '永久刪除（第 1 次確認）', `從保管區永久刪除 <b>${items.length}</b> 個項目（${HZ.fmtSize(size)}），刪了就找不回來。`, '我要永久刪除'],
      ['br', '永久刪除（第 2 次確認）', '這些項目不會再有任何備份。確定嗎？', '確定，不用保留'], ['tr', '永久刪除（最後確認）', `最後一次：永久刪除 ${items.length} 個項目？`, `永久刪除 ${items.length} 個`]]) {
      const r = await HZ.dialog({title: t, body: b, pos, buttons: [{text: '取消', value: false, primary: true}, {text: ok, value: true, cls: 'danger'}]});
      if (r !== true) { HZ.toast('已取消'); return; }
    }
    V.act('purge', {confirmed: 3});
  };
  V.onShow = () => { V.load(); };
  V.onFsChange = () => { if (HZ.cur === 'vault') V.load(); };
  HZ.page('vault', V);

  /* ======================================================================= 重複檔案 */
  const P = {title: '重複檔案', sel: new Set()};
  P.build = function (root) {
    P.path = h('input', {placeholder: '資料夾或磁碟（空白 = 所有已索引的磁碟）', style: {flex: '1', minWidth: '240px'}});
    P.min = h('input', {type: 'number', value: 1, min: 0, step: 1, style: {width: '70px'}});
    P.full = h('input', {type: 'checkbox', checked: true});
    P.btn = h('button', {class: 'primary', onclick: () => P.running ? HZ.post('/api/dupes/cancel').catch(HZ.err) : P.start()}, '開始找');   // one handler
    P.stat = h('div', {class: 'sinfo'});
    P.tools = h('div', {class: 'row wrap'});
    P.list = h('div', {class: 'list', style: {padding: '0 12px 20px'}});
    root.append(h('div', {class: 'sbox'}, P.path, h('span', {class: 'small muted', text: '至少'}), P.min, h('span', {class: 'small muted', text: 'MB'}),
      h('label', {class: 'row small', title: '先比大小、再比開頭和結尾，勾選後再把整個檔案比對一次（最準，但要讀完整個檔案）'}, P.full, '完整比對'), P.btn),
      h('div', {class: 'sbox', style: {paddingTop: 0}}, P.tools), P.stat, P.list);
    P.tools.append(h('span', {class: 'small muted', text: '自動勾選要刪除的：'}),
      ...[['newest', '保留最舊的'], ['oldest', '保留最新的'], ['short', '保留路徑最短的'], ['hot', '保留熱資料夾裡的'], ['none', '全部不勾']].map(([k, t]) => h('button', {class: 'sm', onclick: () => P.auto(k)}, t)),
      h('span', {class: 'grow'}), h('button', {class: 'danger', onclick: P.del}, '刪除勾選的（放進保管區）'));
  };
  P.start = async function () {
    try { await HZ.post('/api/dupes/start', {path: P.path.value.trim(), min_mb: +P.min.value || 0, full: P.full.checked}); P.sel.clear(); P.poll(); }
    catch (e) { HZ.err(e); }
  };
  P.poll = function () { HZ.every('dupes', 1000, P.load); };
  P.load = async function () {
    let d; try { d = await HZ.get('/api/dupes'); } catch (e) { return; }
    P.d = d;
    if (d.state === 'running') {
      P.btn.textContent = '停止'; P.running = true;
      P.stat.innerHTML = `<span>${esc(d.msg)}</span><span>${Math.round(d.progress * 100)}%</span>`;
      P.list.innerHTML = `<div class="bar big" style="margin:12px 0"><i class="hot" style="width:${d.progress * 100}%"></i></div>`;
      return;
    }
    HZ.stop('dupes'); P.btn.textContent = '開始找'; P.running = false;
    P.stat.innerHTML = d.state === 'idle' ? '<span class="muted">先比大小（來自索引，很快）→ 比開頭與結尾 → 完整比對。找到的重複檔案可以自動勾選要刪除的，刪除會先放進保管區（同一顆硬碟，所以空間要等保管期滿、或在保管區永久刪除後才會真的空出來）。</span>'
      : `<span>${esc(d.msg)}</span>` + (d.ngroups > d.groups.length ? `<span>顯示前 ${d.groups.length} 組</span>` : '');
    P.render();
  };
  P.render = function () {
    const d = P.d; P.list.innerHTML = '';
    for (const g of d.groups || []) {
      const nf = g.nfiles || g.files.length;
      const box = h('div', {class: 'dgroup'}, h('div', {class: 'row'}, h('b', {text: `${nf.toLocaleString()} 個${g.partial ? '可能' : ''}相同的檔案`}),
        h('span', {class: 'muted', text: `每個 ${HZ.fmtSize(g.size)}，多佔了 ${HZ.fmtSize(g.wasted)}` + (g.partial ? '（只比對了開頭與結尾，刪除前會逐位元組確認）' : '')}),
        nf > g.files.length ? h('span', {class: 'small muted', text: `只列出前 ${g.files.length} 個`}) : null));
      for (const f of g.files) {
        const ext = (f.path.split('.').pop() || '').toLowerCase(), k = HZ.kind(ext);
        const cb = h('input', {type: 'checkbox', checked: P.sel.has(f.path), onchange: e => e.target.checked ? P.sel.add(f.path) : P.sel.delete(f.path)});
        box.append(h('div', {class: 'dfile'}, cb,
          (k === 'image' || k === 'video') ? h('img', {loading: 'lazy', src: '/api/thumb?' + new URLSearchParams({path: f.path, s: 128}), onerror: e => e.target.remove()}) : h('span', {html: HZ.icon({ext})}),
          h('div', {style: {minWidth: 0}}, h('div', {class: 'ell', text: HZ.base(f.path)}), h('div', {class: 'small muted ell', text: HZ.dir(f.path)})),
          h('span', {class: 'c4 small muted', text: HZ.fmtDate(f.mtime)}),
          h('span', {}, f.hot ? h('span', {class: 'pill hot', text: '🔥'}) : null, h('button', {class: 'sm ghost', title: '開啟所在資料夾', onclick: () => { HZ.go('explorer'); HZ.pages.explorer.open(HZ.dir(f.path), HZ.base(f.path)); }}, '📂'))));
      }
      P.list.append(box);
    }
    if (d.state === 'done' && !(d.groups || []).length) P.list.append(h('div', {class: 'empty', text: '沒有找到重複的檔案 🎉'}));
  };
  P.auto = function (mode) {
    P.sel.clear();
    if (mode !== 'none') for (const g of P.d.groups || []) {
      const fs = g.files.slice();
      let keep;
      if (mode === 'newest') keep = fs.reduce((a, b) => a.mtime <= b.mtime ? a : b);
      else if (mode === 'oldest') keep = fs.reduce((a, b) => a.mtime >= b.mtime ? a : b);
      else if (mode === 'short') keep = fs.reduce((a, b) => a.path.length <= b.path.length ? a : b);
      else keep = fs.find(f => f.hot) || fs.reduce((a, b) => a.mtime <= b.mtime ? a : b);
      for (const f of fs) if (f !== keep) P.sel.add(f.path);
    }
    P.render(); HZ.toast(`已勾選 ${P.sel.size} 個（每組都會留下一個）`);
  };
  P.del = async function () {
    if (!P.sel.size) { HZ.toast('請先勾選'); return; }
    for (const g of P.d.groups || []) if (g.files.every(f => P.sel.has(f.path))) { HZ.toast('有一組全部被勾選了，至少要留一個', 'bad'); return; }
    const ok = await HZ.confirm('刪除重複的檔案', `把勾選的 ${P.sel.size} 個檔案放進保管區（${HZ.vaultDays()} 天內可以還原）？<br><span class="small muted">放進去之前會再逐位元組確認：每一個都要和同一組留下來的檔案完全一樣，而且找到之後沒有被改過；不符合的會留在原處。</span>`, '刪除');
    if (!ok) return;
    try { await HZ.post('/api/dupes/remove', {paths: [...P.sel]}); } catch (e) { HZ.err(e); return; }
    P.sel.clear(); P.waitRemove();
  };
  P.waitRemove = function () {                                       // the server checks, queues, and updates the results
    HZ.every('dupes', 700, async () => {
      let d; try { d = await HZ.get('/api/dupes'); } catch (e) { return; }
      const r = d.rm || {};
      if (r.state === 'running') { P.stat.innerHTML = `<span>${esc(r.msg || '')}</span><span>${Math.round((r.progress || 0) * 100)}%</span>`; return; }
      HZ.stop('dupes'); P.d = d; P.render();
      P.stat.innerHTML = `<span>${esc(d.msg)}</span>`;
      if (r.state === 'done' || r.state === 'canceled' || r.state === 'error') {
        HZ.toast(esc(r.msg || ''), (r.nrefused || r.state !== 'done') ? 'bad' : 'ok');
        if ((r.refused || []).length) P.list.prepend(h('div', {class: 'ask'}, h('b', {text: '這些沒有放進保管區：'}),
          ...r.refused.slice(0, 50).map(x => h('div', {class: 'small ell', title: x.path, text: `${HZ.base(x.path)}：${x.why}`}))));
        setTimeout(() => HZ.refreshViews && HZ.refreshViews(), 1200);
      }
    });
  };
  P.onShow = () => P.load().then(() => { if (P.d && P.d.state === 'running') P.poll(); });
  P.onHide = () => HZ.stop('dupes');
  HZ.page('dupes', P);
})();

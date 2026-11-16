/* HotZone FM — 說明 (the README, rendered, with a table of contents and search) */
'use strict';
(function () {
  const {h, esc} = HZ;
  const P = {title: '說明'};

  // small markdown renderer: headings, lists (nested by indent), > quotes, ``` code, `code`, **bold**, [links](url), <url>, tables, ---
  function inline(t) {
    t = esc(t);
    t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
    t = t.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
    t = t.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    t = t.replace(/&lt;(https?:[^&\s]+)&gt;/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
    return t;
  }
  function render(md) {
    const out = [], toc = []; const lines = md.replace(/\r/g, '').split('\n');
    let i = 0, inCode = false, code = [], list = [];                       // list = stack of indent levels
    const closeLists = (to = -1) => { while (list.length && list[list.length - 1] > to) { out.push('</li></ul>'); list.pop(); } };
    while (i < lines.length) {
      const ln = lines[i];
      if (ln.startsWith('```')) {
        if (inCode) { out.push(`<pre>${esc(code.join('\n'))}</pre>`); code = []; inCode = false; } else { closeLists(); inCode = true; }
        i++; continue;
      }
      if (inCode) { code.push(ln); i++; continue; }
      let m;
      if ((m = ln.match(/^(#{1,4})\s+(.*)$/))) {
        closeLists(); const lv = m[1].length, id = 'hh' + toc.length;
        toc.push({lv, text: m[2], id}); out.push(`<h${lv + 1} id="${id}">${inline(m[2])}</h${lv + 1}>`); i++; continue;
      }
      if (/^---+\s*$/.test(ln)) { closeLists(); out.push('<hr>'); i++; continue; }
      if (ln.startsWith('|') && i + 1 < lines.length && /^\|[\s:|-]+\|?\s*$/.test(lines[i + 1])) {
        closeLists(); const cells = s => s.trim().replace(/^\||\|$/g, '').split('|').map(x => inline(x.trim()));
        let t = '<table class="t"><tr>' + cells(ln).map(c => `<th>${c}</th>`).join('') + '</tr>'; i += 2;
        while (i < lines.length && lines[i].startsWith('|')) { t += '<tr>' + cells(lines[i]).map(c => `<td>${c}</td>`).join('') + '</tr>'; i++; }
        out.push(t + '</table>'); continue;
      }
      if ((m = ln.match(/^(\s*)(?:[*-]|\d+\.)\s+(.*)$/))) {
        const ind = m[1].length;
        if (!list.length || ind > list[list.length - 1]) { out.push('<ul><li>'); list.push(ind); }
        else { closeLists(ind); out.push('</li><li>'); }
        out.push(inline(m[2])); i++; continue;
      }
      if (ln.startsWith('>')) { closeLists(); out.push(`<blockquote>${inline(ln.replace(/^>\s?/, ''))}</blockquote>`); i++; continue; }
      if (!ln.trim()) { if (!list.length) out.push(''); i++; continue; }
      if (list.length && /^\s+\S/.test(ln)) { out.push(' ' + inline(ln.trim())); i++; continue; }  // continuation of a list item
      closeLists(); out.push(`<p>${inline(ln)}</p>`); i++;
    }
    closeLists();
    return {html: out.join('\n'), toc};
  }

  P.build = function (root) {
    P.q = h('input', {placeholder: '在說明裡找…（例如：保管區、同步放大鏡、Tailscale）', style: {flex: '1', minWidth: '220px'}, oninput: HZ.debounce(() => P.find(), 200)});
    P.toc = h('div', {class: 'helptoc'});
    P.body = h('div', {class: 'helpbody'});
    root.append(h('div', {class: 'sbox'}, h('b', {text: '❓ 說明'}), P.q, h('button', {class: 'sm', onclick: () => HZ.welcome()}, '👋 開始使用導覽')),
      h('div', {class: 'helpwrap'}, P.toc, P.body));
  };
  P.load = async function () {
    if (P.md) return;
    try { P.md = (await HZ.get('/api/help')).md; } catch (e) { HZ.err(e); return; }
    const r = render(P.md);
    P.body.innerHTML = r.html;
    P.toc.innerHTML = '';
    for (const t of r.toc) if (t.lv <= 3) P.toc.append(h('div', {class: 'tn l' + t.lv, text: t.text.replace(/\*\*/g, ''), onclick: () => document.getElementById(t.id).scrollIntoView({behavior: 'smooth', block: 'start'})}));
  };
  P.find = function () {
    const q = P.q.value.trim().toLowerCase();
    for (const el of P.body.querySelectorAll('.hit')) el.classList.remove('hit');
    if (!q) return;
    const all = [...P.body.querySelectorAll('p,li,h2,h3,h4,h5,blockquote,td')];
    const hits = all.filter(el => el.textContent.toLowerCase().includes(q) && !([...el.children].some(c => c.matches('li') && c.textContent.toLowerCase().includes(q))));
    hits.forEach(el => el.classList.add('hit'));
    if (hits[0]) hits[0].scrollIntoView({behavior: 'smooth', block: 'center'});
    HZ.toast(hits.length ? `找到 ${hits.length} 處` : '沒有找到', hits.length ? 'ok' : '', 1500);
  };
  P.onShow = () => P.load();
  HZ.page('help', P);
})();

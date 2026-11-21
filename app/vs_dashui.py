"""🎛 三段切換（SortCut／FileCompare／H265）＋一頁總覽的畫面（V0.5.68）.

SortCut 的網頁和整理（FileCompare）的網頁共用這一份：CSS 和 JS 都用 dz／msw 開頭，不會跟兩邊原本的名字打架。
資料從 /api/dash?k=vs|h265|fc 拿（vs_dash.py 一次算好、20 秒快取）。
顏色：分類色照固定順序（藍、橘、青、黃、洋紅、綠、紫、紅），「還沒分」一律灰；整理的分類用你自己設的顏色。
"""

CSS = r"""
/* ---- 🎛 三段切換 ---- */
.msw{--k:#4dc9ff;position:relative;display:inline-grid;grid-template-columns:repeat(3,1fr);gap:0;padding:3px;border-radius:13px;background:rgba(127,140,160,.14);border:1px solid rgba(127,140,160,.28);
  box-shadow:inset 0 1px 2px rgba(0,0,0,.25);flex:0 0 auto;user-select:none;-webkit-user-select:none;min-width:250px}
.msw[data-m="fc"]{--k:#9085e9}.msw[data-m="h265"]{--k:#ff9f43}
.msw .msw-k{position:absolute;top:3px;bottom:3px;left:3px;width:calc((100% - 6px)/3);border-radius:10px;background:var(--k);box-shadow:0 2px 10px color-mix(in srgb,var(--k) 55%,transparent);
  transition:transform .28s cubic-bezier(.3,1.3,.5,1),background .25s}
.msw[data-m="fc"] .msw-k{transform:translateX(100%)}.msw[data-m="h265"] .msw-k{transform:translateX(200%)}
.msw button{position:relative;z-index:1;background:none;border:0;padding:4px 8px;border-radius:10px;color:inherit;opacity:.72;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:5px;
  font:700 12.5px/1.15 system-ui,-apple-system,"Segoe UI",sans-serif;white-space:nowrap;transition:opacity .2s,color .2s;min-height:30px}
.msw button b{font-size:14px;font-weight:400}.msw button:hover{opacity:1}
.msw button.on{opacity:1;color:#0b1018}
body.pc header .msw{display:grid;width:100%;min-width:0;margin:10px 0 6px}
body.pc header .msw button{flex-direction:column;gap:1px;font-size:10.5px;padding:5px 2px;min-height:42px}
header .bar>.msw{margin:0 8px}
@media (max-width:620px){header .bar{flex-wrap:wrap}header .bar>.msw{order:20;width:100%;margin:6px 0 2px;display:grid}.msw{min-width:0}.msw button span{font-size:10.5px}.msw button{padding:4px 5px;gap:3px}}
@media (max-width:420px){.msw button span{font-size:10px}.msw button b{font-size:13px}}
/* ---- 📊 一頁總覽 ---- */
.dz{display:grid;gap:10px;padding:10px;grid-template-columns:repeat(var(--dzcols,4),minmax(0,1fr));grid-template-rows:auto auto minmax(0,1fr) minmax(0,1fr);box-sizing:border-box;overflow:hidden}
.dz .dzh{grid-column:1/-1;display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-height:34px}
.dz .dzh h2{margin:0;font-size:17px;font-weight:800}.dz .dzh .dzsp{flex:1}.dz .dzh small{opacity:.6;font-size:11.5px}
.dz .dzb{border:1px solid rgba(127,140,160,.3);background:rgba(127,140,160,.10);color:inherit;border-radius:999px;padding:6px 12px;font:700 12.5px system-ui,sans-serif;cursor:pointer;white-space:nowrap}
.dz .dzb.dzacc{background:var(--dzk,#3987e5);border-color:transparent;color:#fff}.dz .dzb.dzred{color:#ff9a9a;border-color:#e6676799}
.dz .dzt{background:var(--card,#151a21);border:1px solid var(--line,#252c35);border-radius:14px;padding:10px 12px;min-width:0;min-height:0;overflow:hidden;position:relative}
.dz .dzu{display:inline-flex;margin-left:8px;border:1px solid rgba(127,140,160,.4);border-radius:10px;overflow:hidden;vertical-align:middle}.dz .dzu button{border:0;background:transparent;color:inherit;font-size:11px;padding:1px 9px;cursor:pointer;opacity:.75}.dz .dzu button.on{background:#9085e9;color:#fff;opacity:1}
.dz .dzk{border-top:3px solid var(--c,#3987e5);cursor:default}.dz .dzk[data-go]{cursor:pointer}.dz .dzk[data-go]:hover{border-color:var(--c)}
.dz .dzl{font-size:11.5px;opacity:.7;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dz .dzv{font-size:clamp(18px,2.2vw,28px);font-weight:800;line-height:1.15;margin-top:3px;white-space:nowrap;font-variant-numeric:tabular-nums}
.dz .dzs{font-size:11.5px;opacity:.7;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dz .dzd{position:absolute;top:8px;right:9px;font-size:11px;font-weight:800;padding:1px 7px;border-radius:999px;background:#0ca30c26;color:#3ccb3c}
.dz .dzd.dzz{background:rgba(127,140,160,.15);color:inherit;opacity:.55}
.dz .dzkb{height:5px;border-radius:3px;background:rgba(127,140,160,.18);margin-top:7px;overflow:hidden}.dz .dzkb i{display:block;height:100%;border-radius:3px;background:var(--c)}
.dz .dztt{font-size:13px;font-weight:800;margin-bottom:6px;display:flex;align-items:center;gap:6px}.dz .dztt small{font-weight:500;opacity:.6;font-size:11px;margin-left:auto}
.dz .dzdn{display:flex;gap:12px;align-items:center;height:calc(100% - 26px);min-height:0}
.dz .dzdn svg{height:100%;max-height:230px;width:auto;aspect-ratio:1;flex:0 0 auto}
.dz .dzlg{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px;overflow:hidden;font-size:12px}
.dz .dzlg div{display:grid;grid-template-columns:10px minmax(0,1fr) auto auto;gap:6px;align-items:center}
.dz .dzlg i{width:10px;height:10px;border-radius:3px}.dz .dzlg span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.dz .dzlg b{font-variant-numeric:tabular-nums}.dz .dzlg em{font-style:normal;opacity:.6;font-size:11px;min-width:40px;text-align:right}
.dz .dz7{display:flex;align-items:flex-end;gap:6px;height:calc(100% - 26px);min-height:60px;padding-top:14px;box-sizing:border-box}
.dz .dz7 div{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;min-width:0}
.dz .dz7 i{width:min(70%,34px);background:var(--c,#3987e5);border-radius:4px 4px 0 0;min-height:2px;position:relative}
.dz .dz7 i b{position:absolute;bottom:100%;left:50%;transform:translateX(-50%);font-size:10.5px;font-weight:700;white-space:nowrap;padding-bottom:2px}
.dz .dz7 small{font-size:10.5px;opacity:.6;margin-top:3px}.dz .dz7 div.dztd small{opacity:1;font-weight:800}
.dz .dzbr{display:flex;flex-direction:column;gap:7px;overflow:hidden;height:calc(100% - 26px)}
.dz .dzbr div{font-size:12px}.dz .dzbr .dzbl{display:flex;gap:6px}.dz .dzbr .dzbl span{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.dz .dzbr .dzbl b{font-variant-numeric:tabular-nums;white-space:nowrap}
.dz .dzbr .dzbb{height:7px;border-radius:4px;background:rgba(127,140,160,.18);margin-top:3px;overflow:hidden;display:flex;gap:2px}.dz .dzbr .dzbb i{display:block;height:100%;border-radius:4px}
@media (max-width:700px){.dz{grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:none;overflow:visible;height:auto!important}.dz .dzw2,.dz .dzw3{grid-column:1/-1}.dz .dzdn,.dz .dz7,.dz .dzbr{height:auto}.dz .dzdn svg{height:150px}.dz .dz7{height:150px}}
/* ---- V0.5.73 上面浮動按鈕（效能／背景…）跟標題列擠在一起：先藏電腦名稱，還是重疊就讓標題列往下一排 ---- */
body.nopcn header .pcn{display:none}body.fabrow header{padding-top:36px}body.pcdot header .pcn{visibility:hidden}
body.hdmin header .bar .clk,body.hdmin header .bar #ver,body.hdmin header .bar .ver{display:none}
body.fabic #sysFab button .fbt{display:none}body.fabic #sysFab button{padding:0 8px}
body.mswc header .msw{display:inline-flex;min-width:0;width:auto!important;gap:2px}body.mswc header .msw .msw-k{display:none}
body.mswc header .msw button{padding:4px 10px;flex:0 0 auto}body.mswc header .msw button:not(.on) span{display:none}
body.mswc header .msw button.on{background:var(--k);color:#0b1018;box-shadow:0 2px 10px color-mix(in srgb,var(--k) 55%,transparent)}
/* ---- 🤝 右上角讓路等級 Lv 1～10（V0.5.71） ---- */
.lvb{--lc:#2ecc71;display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 9px 0 8px;border-radius:13px;border:1px solid color-mix(in srgb,var(--lc) 55%,transparent);
  background:rgba(127,140,160,.14);color:var(--lc);font:800 12px/1 system-ui,-apple-system,"Segoe UI",sans-serif;cursor:pointer;flex:0 0 auto;white-space:nowrap}
.lvb .lvbars{display:inline-flex;align-items:flex-end;gap:1.5px;height:16px}.lvb .lvbars i{width:3px;border-radius:1px;background:rgba(127,140,160,.35)}
.lvb .lvbars i.on{background:var(--lc)}.lvb.off{--lc:#7f8a99}
.lvm{position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;padding:12px}
.lvm>div{background:var(--card,#151a21);color:inherit;border:1px solid var(--line,#252c35);border-radius:16px;max-width:560px;width:100%;max-height:90vh;overflow:auto;padding:14px 16px;box-sizing:border-box}
.lvm h3{margin:0 0 4px;font-size:16px}.lvm .lvbig{font-size:28px;font-weight:800}.lvm table{width:100%;border-collapse:collapse;font-size:12.5px;margin:8px 0}
.lvm td,.lvm th{padding:4px 5px;border-bottom:1px solid rgba(127,140,160,.18);text-align:right;font-variant-numeric:tabular-nums}.lvm td:first-child,.lvm th:first-child{text-align:left}
.lvm .lvmu{opacity:.65;font-size:12px;line-height:1.5}.lvm .lvrow{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:8px 0}.lvm select{font:inherit;padding:3px 6px;border-radius:8px}
.lvm .lvx{float:right;border:0;background:none;color:inherit;font-size:20px;cursor:pointer;opacity:.7}
header .bar>.lvb{order:30;margin-left:8px}
body.pc header .bar>.lvb{order:0;margin:6px 0 0;align-self:flex-start}
@media (max-width:620px){header .bar>.msw{width:calc(100% - 64px)}header .bar>.lvb{order:21;margin:6px 0 2px 6px;height:40px;padding:0 8px;flex-direction:column;gap:2px;justify-content:center;width:56px;box-sizing:border-box}
  header .bar>.lvb .lvbars{height:12px}header .bar>.lvb .lvbars i{width:2.5px}}
"""

JS = r"""

// ---------------------------------------------------------------- V0.5.73 浮動按鈕不要蓋到標題列
function fabWrap(F){F.querySelectorAll('button').forEach(b=>{if(b.classList.contains('lvb'))return;[...b.childNodes].forEach(n=>{if(n.nodeType!==3)return;const m=/^(\s*\S+)(\s+[\s\S]+)$/u.exec(n.nodeValue);if(!m)return;
  const sp=document.createElement('span');sp.className='fbt';sp.textContent=m[2];b.title=b.title||b.textContent.trim();n.nodeValue=m[1];n.after(sp)})})}
function fabFit(){const F=document.getElementById('sysFab'),B=document.querySelector('header .bar'),D=document.body;
  // V0.5.74 一排放得下：三段切換只留目前那一段的名字（其他只留圖示）；還擠 → 藏電腦名稱 → 浮動按鈕只留圖示 → 藏時鐘／版本，最後才往下一排
  D.classList.remove('nopcn','fabrow','pcdot','fabic','hdmin');const ph=innerWidth<=620;D.classList.toggle('mswc',!D.classList.contains('pc')&&!ph);if(!F||!B||D.classList.contains('pc'))return;
  fabWrap(F);
  const hit=()=>{const f=F.getBoundingClientRect();if(!f.width||!f.height)return false;const L=[...B.querySelectorAll(':scope>*:not(.rt):not(.grow),:scope>.rt>*')];
    return L.some(el=>{if(el===F||F.contains(el)||el.contains(F))return false;const r=el.getBoundingClientRect();if(!r.width||!r.height)return false;
      return r.left<f.right+4&&r.right>f.left-4&&r.top<f.bottom&&r.bottom>f.top})};
  F.style.left='';F.style.transform='';
  const gap=()=>{const f=F.getBoundingClientRect(),y=B.getBoundingClientRect();let lo=y.left,hi=y.right;   // 把浮動按鈕放進標題列中間空出來的地方
    [...B.querySelectorAll(':scope>*:not(.rt):not(.grow),:scope>.rt>*')].forEach(el=>{const r=el.getBoundingClientRect();if(!r.width||r.bottom<f.top||r.top>f.bottom)return;
      if(r.left+r.width/2<f.left+f.width/2)lo=Math.max(lo,r.right);else hi=Math.min(hi,r.left)});
    if(hi-lo-12<f.width)return false;F.style.left=(lo+(hi-lo-f.width)/2)+'px';F.style.transform='none';return !hit()};
  for(const c of (ph?['pcdot','fabic','hdmin','fabrow']:['nopcn','fabic','hdmin','fabrow'])){if(!hit())return;if(c==='fabrow'&&gap())return;F.style.left='';F.style.transform='';D.classList.add(c)}}
(function(){let t=0;const go=()=>{clearTimeout(t);t=setTimeout(fabFit,120)};addEventListener('resize',go);addEventListener('load',go);
  try{new MutationObserver(go).observe(document.body,{childList:true,subtree:false})}catch(e){}
  const hook=()=>{const F=document.getElementById('sysFab');if(F&&!F._ff){F._ff=1;try{new ResizeObserver(go).observe(F)}catch(e){}}go()};[200,800,2000,5000].forEach(x=>setTimeout(hook,x))})();
// ---------------------------------------------------------------- 🤝 右上角讓路等級（V0.5.71，SortCut／整理共用）
let LVF=null,LVV=null;
function lvHTML(){let b='';for(let i=0;i<10;i++)b+=`<i style="height:${5+i}px"></i>`;return `<button type="button" class="lvb" id="lvb" title="🧠 智能調速／讓路：點一下看詳細"><span class="lvbars">${b}</span><b>Lv–</b></button>`}
function lvSet(v){LVV=v;document.querySelectorAll('.lvb').forEach(el=>{const on=v.on!==false;el.classList.toggle('off',!on);el.style.setProperty('--lc',v.col||'#2ecc71');
  el.querySelector('b').textContent=on?((v.alert?'⚡':'')+'Lv'+v.level):'OFF';el.querySelectorAll('.lvbars i').forEach((x,i)=>x.classList.toggle('on',on&&i<v.level));
  el.title=on?`${v.tk_cfg===false?'🧠 智能調速（不讓 TikLive）':'🤝 讓路'}等級 Lv ${v.level}／10（1＝最讓路、10＝最快）\n${v.why||''}\n點一下看詳細`:'🧠 智能調速：關掉了'});
  const m=document.getElementById('lvm');if(m)lvBody(m.firstElementChild)}
async function lvTick(){if(!LVF)return;try{const v=await LVF();if(v&&v.level!=null)lvSet(v)}catch(e){}}
function lvStart(fn){LVF=fn;lvTick();setInterval(lvTick,3000)}
function lvBody(box){const v=LVV||{},U=v.use||{},L=v.L||{},N={cpu:'CPU',gpu:'顯示卡',enc:'編碼 NVENC',dec:'解碼',vram:'顯示卡記憶體'},f=x=>x==null?'—':Math.round(x)+'%';
  const tk=v.tk_cfg===false?'⚪ 這台不讓路給 TikLive（另一台電腦用）：只看整台電腦忙不忙來調速':v.tk_link?`✅ TikLive 已連上（${dzE(v.tk_ver||'')}）：錄影 ${v.tk_rec||0} 間、轉檔 ${v.tk_conv||0}、字幕 ${v.tk_stt?'跑':'沒跑'}`:(v.tk?'🟡 TikLive 有在跑，還沒更新到 TK_V1.0.84（用量測的）':'⚪ 這台沒有看到 TikLive');
  const R=Object.entries(v.R||{}).filter(([k,x])=>x).map(([k,x])=>`${N[k]||k} ${x}%`).join('、')||'沒有';
  const AL=v.alert?`<p style="color:#e5484d"><b>⚡ TikLive 斷電警報（24 小時內 ${v.alert.n24??'?'} 次）</b>：${dzE(v.alert.msg||'')}<br>這邊照做：轉檔／瘦身不開新的、Lv 1、CPU 上限 2%、同時只做 1 個，到 ${new Date((v.alert.until||0)*1000).toLocaleString()}。要提早解除：到 TikLive 按「解除警報」。</p>`:'';
  box.innerHTML=`<button class="lvx" data-lv="x">✕</button><h3>${v.tk?'🤝 讓路給 TikLive':'🧠 智能調速'}</h3>${AL}<div><span class="lvbig" style="color:${v.col||'#2ecc71'}">Lv ${v.level??'–'}</span> <b>／10</b>
   <span class="lvmu">目標 Lv ${v.target??'–'}・FFmpeg 每秒跑 ${Math.round((v.duty||1)*100)}%</span></div><div>${dzE(v.why||'')}</div>${v.cpu_src&&v.cpu_src.src?`<div class="lvmu">CPU 用${dzE(v.cpu_src.src)}量${v.cpu_src.old!=null&&v.cpu_src.src!=='GetSystemTimes'?`（舊算法是 ${Math.round(v.cpu_src.old)}%，只給你對照）`:''}</div>`:''}<p class="lvmu">${tk}</p>
   <table><tr><th>項目</th><th>整台</th>${v.tk?'<th>TikLive</th>':''}<th>這邊</th><th>允許 Lv</th></tr>${Object.keys(N).map(k=>`<tr><td>${N[k]}</td><td>${f((U[k]||{}).all)}</td>${v.tk?`<td>${f((U[k]||{}).tk)}</td>`:''}<td>${f((U[k]||{}).vs)}</td><td>${L[k]??'—'}</td></tr>`).join('')}
   <tr><td>RAM</td><td>${f(v.ram)}</td>${v.tk?'<td></td>':''}<td></td><td>${L.ram??'—'}</td></tr><tr><td>NVENC 條數</td><td>${v.nvenc??'—'}／${v.nvenc_limit||8}</td>${v.tk?'<td></td>':''}<td></td><td>${L.nvenc??'—'}</td></tr></table>
   <div class="lvrow"><label><input type="checkbox" data-lv="on" ${v.on!==false?'checked':''}> 🧠 智能調速（看 CPU／顯示卡／溫度自己調）</label><label><input type="checkbox" data-lv="tk" ${v.tk_cfg!==false?'checked':''}> 🤝 讓路給 TikLive（這台有跑 TikLive 才勾）</label></div>
   <div class="lvrow"><label>最高 <select data-lv="max">${[...Array(10)].map((_,i)=>`<option ${i+1===(v.max||10)?'selected':''}>${i+1}</option>`).join('')}</select> 級</label>
   <label>NVENC 最多 <select data-lv="nv">${[...Array(15)].map((_,i)=>`<option ${i+2===(v.nvenc_limit||8)?'selected':''}>${i+2}</option>`).join('')}</select> 條</label></div>
   <div class="lvrow" style="border-top:1px solid rgba(127,140,160,.2);padding-top:8px"><label><input type="checkbox" data-lv="th_on" ${v.th_on?'checked':''}> 🌡 控溫（主機板會過熱斷電）</label>
    <label>整台 CPU 預算 <select data-lv="th_cpu">${[20,25,30,35,40,45,50,55,60,70,80].map(x=>`<option ${x===Math.round(v.th_cpu||45)?'selected':''}>${x}</option>`).join('')}</select>%</label>
    <label>這邊最多 <select data-lv="th_vs">${[2,5,8,10,15,20,30,40].map(x=>`<option ${x===Math.round(v.th_vs||15)?'selected':''}>${x}</option>`).join('')}</select>%</label>
    <label>顯示卡超過 <select data-lv="th_gpu">${[60,65,70,72,75,78,80,85].map(x=>`<option ${x===Math.round(v.th_gpu||75)?'selected':''}>${x}</option>`).join('')}</select>°C 轉檔先停</label></div>
   ${v.th_on?`<p class="lvmu">🌡 這邊現在最多用整台 CPU 的 <b>${(v.th||{}).cap??'—'}%</b>（預算 ${(v.th||{}).budget??'—'}% − 其他程式 ${(v.th||{}).others??'—'}%）・顯示卡 ${v.gpu_temp??'—'}°C・後台同時只做 1 個${(v.th||{}).err?`<br><span style="color:#e5484d">${dzE(v.th.err)}</span>`:''}</p>`:''}
   ${v.th_on&&v.heat?(()=>{const H=v.heat,S=H.stats||{},ss=H.sess;return `<p class="lvmu"><b>🌡 轉檔看溫度</b>：${dzE(H.why||'—')}${ss?`<br>正在轉 ${ss.mins} 分鐘，${dzE(ss.sensor)} ${Math.round(ss.t0||0)}→最高 ${Math.round(ss.peak||0)}°C`:''}
    ${S.n?`<br>學到的（最近 ${S.n} 部）：轉一部升 ${S.rise}°C、轉 ${S.mins} 分鐘、轉完 ${S.cool} 分鐘降回來`:'<br>還沒學到（轉完第一部就有）'}${(H.log||[]).length?'<br>'+H.log.map(dzE).join('<br>'):''}</p>`})():''}
   ${(()=>{const H=v.hs||{},Q=H.pol||{},MB=Q.members||{},AL=H.alloc||{};
     return `<div class="lvrow" style="border-top:1px solid rgba(127,140,160,.2);padding-top:8px"><b>☑ 這台有誰</b>
       <label><input type="checkbox" data-lv="tk" ${v.tk_cfg!==false?'checked':''}> TikLive</label>${['FusionStitch','ComfyRemote'].map(a=>`<label><input type="checkbox" data-lv="hs_m_${a}" ${MB[a]!==false?'checked':''}> ${a}</label>`).join('')}<label title="問本機 ComfyUI 佇列：在跑就讓它，卡住不讓"><input type="checkbox" data-lv="hs_comfy" ${v.comfy_cfg!==false?'checked':''}> 🎨 自動看 ComfyUI</label></div>
     ${v.comfy&&v.comfy.port?`<p class="lvmu">🎨 ComfyUI（:${v.comfy.port}）：${(v.comfy.run||0)+(v.comfy.pend||0)?`<b>${v.comfy.run} 個在跑、${v.comfy.pend} 個在排</b>`:'開著，沒有工作'}</p>`:''}
     <div class="lvrow"><label>留給你 <select data-lv="hs_reserve">${[0,5,10,15,20,30].map(x=>`<option value="${x}" ${x==(Q.reserve3??10)?'selected':''}>${x}%</option>`).join('')}</select></label>
       <label>ComfyRemote 優先時拿 <select data-lv="hs_first_cap">${[60,70,80,85,90].map(x=>`<option value="${x}" ${x==(Q.first_cap??80)?'selected':''}>${x}%</option>`).join('')}</select></label>
       <label>其他降到 <select data-lv="hs_yield_cap">${[2,5,10,15].map(x=>`<option value="${x}" ${x==(Q.yield_cap??5)?'selected':''}>${x}%</option>`).join('')}</select></label>
       <label>平常 SortCut : FusionStitch <select data-lv="hs_share_sc">${[30,40,50,60,70].map(x=>`<option value="${x}" ${x==(Q.share_sc??50)?'selected':''}>${x} : ${100-x}</option>`).join('')}</select></label></div>
     ${Object.keys(AL).length?`<p class="lvmu">現在分配：${Object.entries(AL).map(([a,c])=>`<b>${dzE(a)}</b> ${c}%`).join('・')}${H.cpu_cap!=null?`（這邊重工作最多 ${H.cpu_cap}%）`:''}・規則第 ${H.rules||'?'} 版</p>`:''}`})()}
   ${(()=>{const H=v.hs||{},P=H.peers||[],M={lead:'⚡ 這邊優先',yield:'🤝 讓別人先跑',split:'⚖ 照比例分',alone:'⚪ 各跑各的'},W=['閒著','背景小工作','在做重工作','使用者在等'];
     return `<div class="lvrow" style="border-top:1px solid rgba(127,140,160,.2);padding-top:8px"><label><input type="checkbox" data-lv="hs_on" ${H.on!==false?'checked':''}> 🤝 跟別的程式握手（FusionStitch）：誰需要 CPU 就讓誰先跑</label></div>
     <div class="lvrow"><label>這邊的優先 <select data-lv="hs_prio">${[...Array(11)].map((_,i)=>`<option value="${i}" ${i===(H.prio??5)?'selected':''}>${i}${i===5?'（一樣）':i>5?'（這邊先）':'（對方先）'}</option>`).join('')}</select></label>
     <label>這邊先跑 <select data-lv="hs_boost">${[[0,H.boost?'取消':'—'],[30,'30 分'],[60,'1 小時'],[120,'2 小時'],[240,'4 小時']].map(([m,t])=>`<option value="${m}">${t}</option>`).join('')}</select></label></div>
     <p class="lvmu">${P.length?P.map(p=>`🔗 <b>${dzE(p.name||p.app)}</b> V${dzE(p.ver||'')}：${W[p.want||0]||''}${p.what?'（'+dzE(p.what)+'）':''}・優先 ${p.prio??5}`).join('<br>')+'<br>':'⚪ 沒有看到 FusionStitch／ComfyRemote（更新到有握手的版本、而且開著，就會出現在這裡）<br>'}
     ${H.mode?`<b>${M[H.mode]||H.mode}</b>${H.why?'：'+dzE(H.why):''}`:''}${H.boost?`・使用者按了這邊先跑（還剩 ${Math.ceil(H.boost/60)} 分）`:''}${H.err?`<br><span style="color:#e5484d">${dzE(H.err)}</span>`:''}</p>`})()}
   <p class="lvmu">Lv 是每一項「允許的等級」裡最小的那個。降：馬上；升：每 8 秒最多 +1。${v.tk?`Lv 10 也不吃滿：整台 CPU ≤85%、顯示卡 ≤80%、NVENC ≤75%，TikLive 最近 10 分鐘的高峰先空一半（現在保留：${R}）。`:'這台沒有 TikLive：沒人在用電腦（3 分鐘沒碰）就全力跑；有人在用留 10% 給你。'}Lv 2 以下轉檔／瘦身先不開新的（跑到一半的照跑完）。</p>
   ${(v.log||[]).length?`<p class="lvmu"><b>最近變化</b><br>${v.log.map(dzE).join('<br>')}</p>`:''}`}
function lvOpen(){let m=document.getElementById('lvm');if(m){m.remove();return}m=document.createElement('div');m.className='lvm';m.id='lvm';m.innerHTML='<div></div>';document.body.appendChild(m);lvBody(m.firstElementChild);
  m.addEventListener('click',async e=>{if(e.target===m||e.target.dataset.lv==='x'){m.remove();return}});
  m.addEventListener('change',async e=>{const k=e.target.dataset.lv;if(!k||!LVF)return;const b={};b[k]=e.target.type==='checkbox'?e.target.checked:+e.target.value;try{const v=await LVF(b);if(v&&v.level!=null)lvSet(v)}catch(_){}})}
document.addEventListener('click',e=>{if(e.target.closest('#lvb')){e.preventDefault();lvOpen()}});
// ---------------------------------------------------------------- 🎛 三段切換＋📊 一頁總覽（V0.5.68，SortCut／整理共用）
const DZC=['#3987e5','#d95926','#199e70','#c98500','#d55181','#008300','#9085e9','#e66767'],DZG='#5b6573';
const dzE=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const dzN=n=>Math.round(+n||0).toLocaleString();
const dzB=b=>{b=+b||0;if(b>=1e12)return (b/1e12).toFixed(2)+' TB';if(b>=1e9)return (b/1e9).toFixed(1)+' GB';if(b>=1e6)return (b/1e6).toFixed(0)+' MB';return (b/1e3).toFixed(0)+' KB'};
const dzP=(a,b)=>b?Math.round(a*1000/b)/10:0;
const MSW=[['vs','🎬','VideoSift','10 秒剪輯、分級'],['fc','🗂','FileCompare','16 格分類整理'],['h265','🗜','H265','SSIM 轉檔瘦身']];
function mswHTML(m){return `<div class="msw" id="msw" data-m="${m}" role="tablist" aria-label="切換"><i class="msw-k"></i>${MSW.map(([k,ic,n,s])=>`<button type="button" role="tab" data-m="${k}" class="${k===m?'on':''}" title="${n}：${s}"><b>${ic}</b><span>${n}</span></button>`).join('')}</div>`}
function mswTo(k){try{localStorage.setItem('vs_mode',JSON.stringify(k))}catch(e){}
  const w=document.getElementById('msw');if(w){w.dataset.m=k;w.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b.dataset.m===k))}
  setTimeout(()=>{if(k==='fc'){if(!location.pathname.startsWith('/fc/'))location.href='/fc/?go=home';else if(typeof go==='function')go('home')}else{const h=k==='h265'?'dh':'dvs';if(location.pathname.startsWith('/fc/'))location.href='/#'+h;else location.hash=h}},170)}
document.addEventListener('click',e=>{const b=e.target.closest('#msw button[data-m]');if(b){e.preventDefault();mswTo(b.dataset.m)}});
// 甜甜圈：segs=[[名稱,數字,顏色,附註]]；中間寫大字
function dzDonut(segs,big,lab){const tot=segs.reduce((a,s)=>a+(+s[1]||0),0)||1,R=42,C=2*Math.PI*R;let off=0,svg='';
  segs.forEach(([n,v,c,x])=>{v=+v||0;if(v<=0)return;const L=v/tot*C,g=segs.length>1?Math.min(2,L/3):0;
    svg+=`<circle r="${R}" cx="50" cy="50" fill="none" stroke="${c}" stroke-width="13" stroke-dasharray="${Math.max(0,L-g)} ${C}" stroke-dashoffset="${-off}" transform="rotate(-90 50 50)"><title>${dzE(n)}：${dzN(v)}（${dzP(v,tot)}%）${x?' '+dzE(x):''}</title></circle>`;off+=L});
  return `<svg viewBox="0 0 100 100" role="img"><circle r="${R}" cx="50" cy="50" fill="none" stroke="rgba(127,140,160,.15)" stroke-width="13"/>${svg}<text x="50" y="49" text-anchor="middle" font-size="15" font-weight="800" fill="currentColor">${dzE(big)}</text><text x="50" y="62" text-anchor="middle" font-size="7.5" fill="currentColor" opacity=".65">${dzE(lab)}</text></svg>`}
function dzLegend(segs,unit,fmt){const tot=segs.reduce((a,s)=>a+(+s[1]||0),0)||1,F=fmt||dzN;return `<div class="dzlg">${segs.map(([n,v,c,x])=>`<div title="${dzE(n)}：${F(v)}${unit||''}${x?'，'+dzE(x):''}"><i style="background:${c}"></i><span>${dzE(n)}</span><b>${F(v)}</b><em>${dzP(v,tot)}%</em></div>`).join('')}</div>`}
function dzKpi(o){return `<div class="dzt dzk" style="--c:${o.c||DZC[0]}"${o.go?` data-go="${dzE(o.go)}"`:''}${o.tip?` title="${dzE(o.tip)}"`:''}><div class="dzl">${o.l}</div><div class="dzv">${o.v}</div><div class="dzs">${o.s||''}</div>${o.d!=null?`<div class="dzd ${o.d?'':'dzz'}">${o.d?'+'+dzN(o.d):'+0'} 今天</div>`:''}${o.p!=null?`<div class="dzkb"><i style="width:${Math.min(100,o.p)}%"></i></div>`:''}</div>`}
function dzD7(d,c,fmt){const mx=Math.max(1,...d.map(x=>+x[1]||0));return `<div class="dz7" style="--c:${c}">${d.map((x,i)=>`<div class="${i===d.length-1?'dztd':''}" title="${x[0]}：${fmt?fmt(x[1]):dzN(x[1])}"><i style="height:${Math.max(2,(+x[1]||0)/mx*100)}%">${+x[1]?`<b>${fmt?fmt(x[1]):dzN(x[1])}</b>`:''}</i><small>${i===d.length-1?'今天':x[0]}</small></div>`).join('')}</div>`}
function dzBars(rows){return `<div class="dzbr">${rows.map(r=>`<div title="${dzE(r.tip||'')}"><div class="dzbl"><span>${dzE(r.n)}</span><b>${r.v}</b></div><div class="dzbb">${(r.parts||[[r.p,r.c]]).map(([p,c])=>`<i style="width:${Math.max(0,Math.min(100,p))}%;background:${c}"></i>`).join('')}</div></div>`).join('')||'<div style="opacity:.6">—</div>'}</div>`}
function dzDisk(D){return (D||[]).map(d=>({n:'💽 '+d.d+' 剩 '+dzB(d.free),v:dzP(d.total-d.free,d.total)+'%',p:dzP(d.total-d.free,d.total),c:(d.free/d.total<0.08?'#d03b3b':d.free/d.total<0.15?'#fab219':'#5b8def'),tip:'用了 '+dzB(d.total-d.free)+' / 共 '+dzB(d.total)}))}
function dzFit(el){if(!el)return;const f=()=>{if(!document.body.contains(el))return window.removeEventListener('resize',f);if(innerWidth<=700){el.style.height='';return}const bn=[...document.querySelectorAll('nav#tabs')].find(n=>getComputedStyle(n).position==='fixed'&&n.getBoundingClientRect().top>innerHeight/2);el.style.height=Math.max(420,innerHeight-el.getBoundingClientRect().top-8-(bn?bn.offsetHeight:0))+'px'};f();window.addEventListener('resize',f)}
// ---- 三邊的內容
function dzVS(j){const G=j.G||{},seg=[['S',G.S,DZC[0]],['A',G.A,DZC[2]],['E',G.E,DZC[3]],['F（待刪）',G.F,DZC[7]],['還沒分級',Math.max(0,j.n-j.graded),DZG]];
  return `<div class="dz" style="--dzcols:4;--dzk:#3987e5"><div class="dzh"><h2>🎬 VideoSift 總覽</h2><small>${new Date(j.t*1000).toTimeString().slice(0,8)} 更新</small><span class="dzsp"></span><button class="dzb dzacc" data-go="#fx">▦ 進 10 秒剪輯 ›</button><button class="dzb" data-go="#tool/report">📈 分級報表</button></div>
  ${dzKpi({l:'🎬 影片',v:dzN(j.n)+' 部',s:dzB(j.b)+'・預覽圖 '+dzP(j.th,j.n)+'%',p:dzP(j.th,j.n),c:DZC[0],go:'#fx'})}
  ${dzKpi({l:'✅ 已分級',v:dzP(j.graded,j.n)+'%',s:dzN(j.graded)+'／'+dzN(j.n)+' 部',d:j.today,p:dzP(j.graded,j.n),c:DZC[2]})}
  ${dzKpi({l:'✂ 初剪',v:dzN(j.cutf)+' 部',s:dzN(j.cuts)+' 段・收藏 '+dzN(j.fav),d:j.cut_today,c:DZC[1]})}
  ${dzKpi({l:'🗑 F（待刪）',v:dzB(j.F_b),s:dzN(j.F_n)+' 部，可以清掉的空間',c:DZC[7]})}
  <div class="dzt dzw2" style="grid-column:span 2"><div class="dztt">🥧 分級分布<small>滑過去看數字</small></div><div class="dzdn">${dzDonut(seg,dzP(j.graded,j.n)+'%','已分級')}${dzLegend(seg,' 部')}</div></div>
  <div class="dzt dzw2" style="grid-column:span 2"><div class="dztt">📅 最近 7 天每天分級<small>今天 +${dzN(j.today)}</small></div>${dzD7(j.d7,DZC[2])}</div>
  <div class="dzt dzw2" style="grid-column:span 2"><div class="dztt">📂 各資料夾進度<small>已分級／全部</small></div>${dzBars((j.roots||[]).map(r=>({n:r.name,v:dzN(r.done)+'／'+dzN(r.n)+'（'+dzP(r.done,r.n)+'%）',p:dzP(r.done,r.n),c:DZC[0],tip:dzB(r.b)})))}</div>
  <div class="dzt dzw2" style="grid-column:span 2"><div class="dztt">💽 硬碟空間</div>${dzBars(dzDisk(j.disk))}</div></div>`}
function dzH(j){const C=j.codec||{},seg=[['H.265（已經小了）',C.hevc&&C.hevc[1],DZC[0],dzN(C.hevc&&C.hevc[0])+' 部'],['H.264',C.h264&&C.h264[1],DZC[1],dzN(C.h264&&C.h264[0])+' 部'],['其他編碼',C.other&&C.other[1],DZC[3],dzN(C.other&&C.other[0])+' 部'],['還沒讀到',C.unk&&C.unk[1],DZG,dzN(C.unk&&C.unk[0])+' 部']];
  const tb=seg.reduce((a,s)=>a+(+s[1]||0),0),sl=j.slim||{};
  return `<div class="dz" style="--dzcols:4;--dzk:#d95926"><div class="dzh"><h2>🗜 H265 總覽</h2><small>${new Date(j.t*1000).toTimeString().slice(0,8)} 更新</small><span class="dzsp"></span><button class="dzb dzacc" data-go="#cv">🗜 進轉檔工作區 ›</button><button class="dzb" data-go="/fc/?go=tool:slim">整理的影片瘦身</button></div>
  ${dzKpi({l:'💾 已經省下',v:dzB(j.saved+(sl.save||0)),s:'轉檔 '+dzN(j.done)+' 部'+(sl.n?'・瘦身 '+dzN(sl.n)+' 部':''),d:j.today+(sl.today||0),c:DZC[2],tip:'轉檔前 '+dzB(j.osz)+' → 轉檔後 '+dzB(j.nsz)})}
  ${dzKpi({l:'🎯 還可以轉',v:dzN(j.cand)+' 部',s:dzB(j.cand_b)+'・預估再省 '+dzB(j.est_save),c:DZC[1],go:'#cv',tip:'照目前平均縮到 '+Math.round(j.ratio*100)+'% 估'})}
  ${dzKpi({l:'⏳ 轉檔中／排隊',v:dzN(j.running)+'／'+dzN(j.queue),s:dzB(j.queue_b)+(j.bad?'・失敗 '+dzN(j.bad):''),c:DZC[3],go:'#cv'})}
  ${dzKpi({l:'📐 平均畫質 SSIM',v:j.ssim?(+j.ssim).toFixed(3):'—',s:'平均縮到 '+Math.round(j.ratio*100)+'%（越接近 1 越像原檔）',c:DZC[6]})}
  <div class="dzt dzw2" style="grid-column:span 2"><div class="dztt">🥧 影片編碼（照大小）<small>共 ${dzB(tb)}</small></div><div class="dzdn">${dzDonut(seg.map(s=>[s[0],s[1],s[2],s[3]]),dzP(C.hevc?C.hevc[1]:0,tb)+'%','已是 H.265')}${dzLegend(seg,'',dzB)}</div></div>
  <div class="dzt dzw2" style="grid-column:span 2"><div class="dztt">📅 最近 7 天每天省多少<small>今天 ${dzB(j.today_save)}</small></div>${dzD7(j.d7,DZC[2],dzB)}</div>
  <div class="dzt dzw2" style="grid-column:span 2"><div class="dztt">📊 空間<small>已省／還能省</small></div>${dzBars([{n:'已經省下（轉檔＋瘦身）',v:dzB(j.saved+(sl.save||0)),parts:[[dzP(j.saved+(sl.save||0),j.saved+(sl.save||0)+j.est_save),DZC[2]]]},{n:'預估還能省（還沒轉的）',v:dzB(j.est_save),parts:[[dzP(j.est_save,j.saved+(sl.save||0)+j.est_save),DZC[1]]]},{n:'排隊中的',v:dzB(j.queue_b),parts:[[dzP(j.queue_b,j.cand_b+j.queue_b),DZC[3]]]}])}</div>
  <div class="dzt dzw2" style="grid-column:span 2"><div class="dztt">💽 硬碟空間</div>${dzBars(dzDisk(j.disk))}</div></div>`}
function dzFC(j){const V=j.cats||[],tag=j.tagged||0,vid=j.videos||0;let U='n';try{U=localStorage.getItem('dzFcU')==='b'?'b':'n'}catch(e){}const B=U==='b'&&j.vid_b!=null;   // V0.5.88 部數／大小切換
  const k=c=>B?(+c.b||0):(+c.n||0);let seg=V.filter(c=>c.n>0).sort((a,b)=>k(b)-k(a));const top=seg.slice(0,7),rest=seg.slice(7);
  seg=top.map((c,i)=>[c.name,k(c),c.color||DZC[i%8],(B?dzN(c.n)+' 部':dzB(c.b))+(c.wait?'・待搬 '+c.wait:'')]);if(rest.length)seg.push(['其他 '+rest.length+' 類',rest.reduce((a,c)=>a+k(c),0),'#8a8f98','']);
  seg.push(['還沒分類',B?Math.max(0,(j.vid_b||0)-(j.tag_b||0)):Math.max(0,vid-tag),DZG,B?dzN(Math.max(0,vid-tag))+' 部':dzB(Math.max(0,(j.vid_b||0)-(j.tag_b||0)))]);
  const pc=B?dzP(j.tag_b,j.vid_b):dzP(tag,vid),tgl=`<span class="dzu"><button data-dzu="n" class="${B?'':'on'}">部數</button><button data-dzu="b" class="${B?'on':''}">大小</button></span>`;
  const D=j.del||{},PK=(j.packs||[])[0];
  return `<div class="dz" style="--dzcols:6;--dzk:#9085e9"><div class="dzh"><h2>🗂 FileCompare 總覽</h2><small>${new Date(j.t*1000).toTimeString().slice(0,8)} 更新</small><span class="dzsp"></span><button class="dzb dzacc" data-go="vc">🎞 進 16 格分類 ›</button><button class="dzb" data-go="tool:wiz">🚀 精靈</button><button class="dzb" data-go="dzfull">📋 詳細總覽</button></div>${PK?`<div class="dzt" style="grid-column:1/-1;border-color:#9085e9;display:flex;gap:10px;align-items:center;flex-wrap:wrap"><b>💽 在 ${dzE(PK.X)}: 找到整理的紀錄</b><span style="opacity:.75;font-size:12.5px">${dzE(PK.pc||'')} 寫的・${new Date((PK.t||0)*1000).toLocaleString()}・${dzN(PK.files)} 個檔・分類 ${dzN(PK.tagged)} 部</span><span class="dzsp" style="flex:1"></span><button class="dzb dzacc" data-dzpack="${dzE(PK.X)}">📥 接上這份紀錄</button></div>`:''}
  ${dzKpi({l:'📁 全部檔案',v:dzN(j.files),s:dzB(j.bytes)+'・照片 '+dzN(j.photos)+'・影片 '+dzN(vid),c:DZC[0]})}
  ${dzKpi({l:'🎞 影片分類'+(B?'（大小）':''),v:pc+'%',s:B?dzB(j.tag_b)+'／'+dzB(j.vid_b):dzN(tag)+'／'+dzN(vid)+' 部',d:j.today,p:+pc,c:'#9085e9',go:'vc',tip:'部數 '+dzP(tag,vid)+'%（'+dzN(tag)+'／'+dzN(vid)+' 部）・大小 '+dzP(j.tag_b,j.vid_b)+'%（'+dzB(j.tag_b)+'／'+dzB(j.vid_b)+'）'})}
  ${dzKpi({l:'🔁 重複可以省',v:dzB(j.dup_bytes),s:dzN(j.dup_groups)+' 組・多 '+dzN(j.dup_files)+' 份',c:DZC[2],go:'tool:dup'})}
  ${dzKpi({l:'🩺 有問題',v:dzN((j.broken||0)+(j.partial||0)+(j.zero||0)),s:'打不開 '+dzN(j.broken)+'・部分損毀 '+dzN(j.partial),c:'#e66767',go:'tool:hl'})}
  ${dzKpi({l:'📦 隔離區',v:dzN(j.quar_n)+' 個',s:dzB(j.quar_bytes)+'・可以隨時復原',c:DZC[3],go:'tool:q'})}
  <div class="dzt dzk" style="--c:#d03b3b"><div class="dzl">🗑 Delete（已搬好）</div><div class="dzv">${dzB(D.b)}</div><div class="dzs">${dzN(D.n)} 個${D.wait?'・還有 '+dzN(D.wait)+' 部沒搬':''}</div>${D.n?'<button class="dzb dzred" data-dzdel="1" style="margin-top:6px;padding:3px 10px">永久刪除…</button>':''}</div>
  <div class="dzt dzw3" style="grid-column:span 3"><div class="dztt">🥧 影片分類分布${tgl}<small>${dzN(seg.length-1)} 類・${B?'照大小算':'照部數算'}</small></div><div class="dzdn">${dzDonut(seg,pc+'%',B?'分好了（大小）':'分好了（部數）')}${dzLegend(seg,B?'':' 部',B?dzB:null)}</div></div>
  <div class="dzt dzw3" style="grid-column:span 3"><div class="dztt">📅 最近 7 天每天分類<small>今天 +${dzN(j.today)}</small></div>${dzD7(j.d7,'#9085e9')}</div>
  <div class="dzt dzw3" style="grid-column:span 3"><div class="dztt">⚙ 整理進度</div>${dzBars([{n:'🏷 拍攝資訊',v:dzN(j.meta_done)+'／'+dzN(j.media),p:dzP(j.meta_done,j.media),c:DZC[0]},{n:'🔁 比對指紋',v:dzN(j.hash_done)+'／'+dzN(j.hash_total),p:dzP(j.hash_done,j.hash_total),c:DZC[2]},{n:'🩺 損毀檢查',v:dzN(j.health_done)+'／'+dzN(j.media),p:dzP(j.health_done,j.media),c:'#e66767'}])}</div>
  <div class="dzt dzw3" style="grid-column:span 3"><div class="dztt">💽 硬碟空間<small>${dzE((j.roots||[]).join('、'))}</small></div>${dzBars(dzDisk(j.disk))}</div></div>`}
document.addEventListener('click',async e=>{const pk=e.target.closest('.dz [data-dzpack]');if(pk){if(!confirm('接上 '+pk.dataset.dzpack+': 上的整理紀錄？（現在這台的整理紀錄會改名留著，不刪）'))return;
  const r=await (await fetch('/fc/api/vs_fcpack',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({X:pk.dataset.dzpack})})).json();alert(r.message||'好了');return}
  const u=e.target.closest('.dz [data-dzu]');if(u){try{localStorage.setItem('dzFcU',u.dataset.dzu)}catch(x){}const h=u.closest('.dz').parentElement;if(h&&h._dzj){h.innerHTML=dzFC(h._dzj);if(h.firstElementChild)h.firstElementChild.dataset.dzid=h.dataset.dz;dzFit(h.firstElementChild)}return}
  const d=e.target.closest('.dz [data-dzdel]');if(d){window.VSDEL&&VSDEL();return}const b=e.target.closest('.dz [data-go]');if(!b)return;const v=b.dataset.go,onFC=location.pathname.startsWith('/fc/');
  if(v.startsWith('#')){if(onFC)location.href='/'+v;else location.hash=v.slice(1)}else if(v.startsWith('/'))location.href=v;else if(v==='dzfull'){window.dzFull&&dzFull()}else if(onFC&&typeof go==='function')go(v);else location.href='/fc/?go='+v});
// 畫到 el；k=vs|h265|fc；15 秒自動更新（離開這頁就停）
async function dzShow(el,k,apiFn){if(!el)return;const me=el.dataset.dz=String(Math.random());el.innerHTML=`<div data-dzid="${me}" style="padding:30px;opacity:.6">📊 讀取中…</div>`;
  // V0.5.73 修：切到別頁（例如 16 格分類）之後，總覽的 15 秒更新還在跑，會把那頁蓋掉 → 每次都確認畫面上還是這個總覽才更新
  const mine=()=>el.dataset.dz===me&&document.body.contains(el)&&!!el.querySelector(`:scope>[data-dzid="${me}"]`);
  const run=async()=>{if(!mine())return clearInterval(t);let j;try{j=await apiFn('/api/dash?k='+k)}catch(e){return}
    if(!mine())return clearInterval(t);
    if(!j||!j.ok){el.innerHTML=`<div data-dzid="${me}" style="padding:30px;opacity:.7">${dzE((j&&j.message)||'讀不到')}</div>`;if(j&&j.busy)setTimeout(()=>{if(!document.hidden)run()},5000);return}
    el._dzj=j;el.innerHTML=(k==='vs'?dzVS:k==='h265'?dzH:dzFC)(j);if(j.busy&&el.firstElementChild)el.firstElementChild.insertAdjacentHTML('afterbegin',`<div class="dzt" style="grid-column:1/-1;border-color:#f0ad4e;color:#f0ad4e;font-size:12.5px;padding:6px 10px">${dzE(j.busy)}（${j.stale||0} 秒前的）</div>`);if(j.busy)setTimeout(()=>{if(!document.hidden&&mine())run()},5000);if(el.firstElementChild)el.firstElementChild.dataset.dzid=me;dzFit(el.firstElementChild)};
  const t=setInterval(()=>{if(!document.hidden)run()},15000);await run()}
"""

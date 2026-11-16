"""📱 手機網頁的整個頁面（HTML＋CSS＋JS 一個檔，不用網路上的東西）。
__VER__／__NAME__／__TITLE__／__ACCENT__ 會換成 brand.json 和程式版本。
新功能的手機畫面：在 TABS 加一頁、寫一個 render 函式；要跟電腦版一樣（電腦有的按鈕手機也要有）。
右上「🖥 網頁版／📱 手機版」：同一個網址，大螢幕用左邊選單的版面（記在這台瀏覽器）。"""

PAGE = r"""<!doctype html>
<html lang="zh-Hant" data-mode="dark"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0a0e13"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-capable" content="yes">
<link rel="manifest" href="manifest.webmanifest"><link rel="icon" href="icon-192.png"><link rel="apple-touch-icon" href="apple-touch-icon.png">
<title>__NAME__</title>
<style>
#vcpqb{position:fixed;left:50%;transform:translateX(-50%);bottom:10px;z-index:60;width:min(980px,calc(100% - 16px));background:linear-gradient(135deg,#1b2433,#152a26);border:1px solid #4dd68a88;border-radius:14px;padding:8px 12px;box-shadow:0 8px 28px #000a;color:var(--text)}#vcpqb .pqh{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;font-size:13.5px}#vcpqb .pqr{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:6px}#vcpqb select{margin-left:4px;padding:4px 6px}#vcpqb .pill small{opacity:.6;font-size:10px;margin-left:3px}body.vcmode #vcs{padding-bottom:90px}
:root{--bg:#0e1116;--nav:#0a0e13;--panel:#11161c;--card:#151a21;--line:#252c35;--line2:#2a3340;--text:#e8ecf2;--strong:#fff;--sub:#8994a4;--btn:#171d26;--btnh:#222b37;--sel:#263342;
--green:#45d483;--red:#ff4d6d;--orange:#f0ad4e;--blue:#4dc9ff;--purple:#b48cff;--accent:__ACCENT__;--track:#2a3038}
html[data-mode=light]{--bg:#f3f5f8;--nav:#e8ecf1;--panel:#fff;--card:#fff;--line:#d5dce4;--line2:#c2cbd6;--text:#1b2430;--strong:#0b121a;--sub:#5d6978;--btn:#fff;--btnh:#e7ecf2;--sel:#d3e6fb;--track:#dfe5ec}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,"Segoe UI","Microsoft JhengHei","PingFang TC",sans-serif}
button{font:inherit;cursor:pointer;color:inherit}
header{position:sticky;top:0;z-index:20;background:var(--nav);border-bottom:1px solid var(--line);padding-top:env(safe-area-inset-top,0px)}
.bar{display:flex;align-items:center;gap:8px;padding:8px 12px 6px}
.logo{font-weight:800;font-size:15px;color:var(--strong);display:flex;align-items:center;gap:7px;white-space:nowrap}
.logo i{width:9px;height:9px;border-radius:50%;background:var(--accent);box-shadow:0 0 8px var(--accent)}
.grow{flex:1;min-width:0}.mu{color:var(--sub);font-size:12px}
.pill{background:var(--btn);border:1px solid var(--line2);border-radius:14px;padding:4px 11px;font-size:12.5px}
.pill:hover{background:var(--btnh)}.pill.ok{border-color:var(--green);color:var(--green)}.pill.wa{border-color:var(--orange);color:var(--orange)}.pill.er{border-color:var(--red);color:var(--red)}
.pill.acc{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:800}
nav#tabs{display:flex;gap:6px;padding:0 10px 8px;overflow-x:auto}
nav#tabs button{flex:2;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:9px 4px;white-space:nowrap;color:var(--sub);font-weight:700;font-size:14.5px}nav#tabs button.sm{flex:1.2}
nav#tabs button.on{background:var(--sel);border-color:var(--blue);color:var(--strong);font-weight:800}
main{padding:10px 10px calc(30px + env(safe-area-inset-bottom,0px))}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin:0 0 10px}
.panel h3{margin:0 0 6px;font-size:14px;color:var(--accent)}
.row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.pg{height:6px;background:var(--track);border-radius:3px;overflow:hidden}.pg i{display:block;height:100%;background:var(--blue)}
.kv{display:grid;grid-template-columns:auto 1fr;gap:3px 10px}.kv b{color:var(--strong)}
.it{border-top:1px solid var(--line);padding:7px 0}.it:first-child{border-top:0}
input,select{background:var(--card);border:1px solid var(--line2);border-radius:8px;padding:6px 8px;color:var(--strong);font:inherit}
pre{white-space:pre-wrap;word-break:break-all;font-size:11.5px;background:var(--card);border-radius:8px;padding:8px;max-height:60vh;overflow:auto}
#toast{position:fixed;left:50%;bottom:calc(18px + env(safe-area-inset-bottom,0px));transform:translateX(-50%);background:#222b37;color:#fff;border-radius:12px;padding:9px 14px;display:none;z-index:99;max-width:90vw;pointer-events:none}
#login{max-width:320px;margin:18vh auto;text-align:center}#login input{width:100%;font-size:20px;text-align:center;letter-spacing:4px;margin:12px 0}
.spark{width:100%;height:34px}
/* 🖥 網頁版：大螢幕左邊選單 */
body.pc #app{display:grid;grid-template-columns:210px minmax(0,1fr);min-height:100vh}
body.pc header{height:100vh;border-bottom:0;border-right:1px solid var(--line);overflow:auto}
body.pc .bar{flex-direction:column;align-items:stretch}
body.pc nav#tabs{flex-direction:column}body.pc nav#tabs button{flex:none;text-align:left;padding:10px 12px}
nav#tabs .ntg,nav#tabs .ntl{display:none}body.pc nav#tabs .ntg{display:block;font-size:11.5px;color:var(--sub);font-weight:800;margin:10px 4px 2px}
body.pc nav#tabs .ntl{display:block;padding:6px 12px;font-size:13px;border:0;background:none;border-radius:8px}body.pc nav#tabs .ntl:hover{background:var(--btnh)}body.pc nav#tabs .ntl.on{background:var(--sel);color:var(--strong)}
body.pc main{max-width:1100px}
/* ---- 最上面正中間「📊 效能／🖥 背景／🎞 分類／📦 隔離」浮動按鈕＋浮動視窗（照 TikLive／SortCut） */
#sysFab{position:fixed;top:calc(env(safe-area-inset-top,0px) + 9px);left:50%;transform:translateX(-50%);z-index:60;display:flex;gap:6px;pointer-events:none}
#sysFab button{pointer-events:auto;height:26px;padding:0 9px;border-radius:13px;border:1px solid rgba(140,150,165,.5);background:rgba(18,22,30,.88);color:#fff;font-weight:800;font-size:11.5px;cursor:pointer;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,.35);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);position:relative}
#sysFab button.on{background:#1f8ef1;border-color:#1f8ef1}
#sysFab em{font-style:normal;position:absolute;top:-7px;right:-6px;background:#1f8ef1;color:#fff;border-radius:8px;padding:0 4px;font-size:9.5px;line-height:14px}#sysFab em.r{background:var(--red)}
@media (max-width:460px){.logo{font-size:0;gap:0}.logo i{width:11px;height:11px}#ver,#bView{display:none}#sysFab{gap:4px}#sysFab button{padding:0 7px;font-size:11px}}
body.pc #sysFab{left:calc(50% + 105px)}
body.pc:has(#vcf) #sysFab{display:none}
body.vcmode #updFab{display:none}body.vcmode{overflow:hidden}
#sysPop{position:fixed;inset:0;z-index:58;background:rgba(0,0,0,.28)}
.sysPopW{position:absolute;left:4%;width:92%;top:calc(env(safe-area-inset-top,0px) + 44px);height:50%;display:flex;flex-direction:column;background:var(--bg);border:1px solid rgba(140,150,165,.45);border-radius:12px;box-shadow:0 14px 40px rgba(0,0,0,.6);overflow:hidden}
@media (min-width:900px){.sysPopW{left:calc(50% - 360px);width:720px}}
.sysPopH{display:flex;align-items:center;gap:8px;padding:8px 10px;border-bottom:1px solid var(--line)}.sysPopH b{font-size:15px;white-space:nowrap}.sysPopN{flex:1;font-size:11.5px;opacity:.6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sysPopX{width:40px;height:32px;border:0;border-radius:9px;background:rgba(127,127,127,.18);font-size:16px}
.sysPopB{flex:1 1 auto;min-height:0;overflow-y:auto;overscroll-behavior:contain;padding:8px 10px 12px}.sysPopB .panel{border:0;padding:0;background:none}
.sysPopR{flex:none;height:26px;display:flex;align-items:center;justify-content:center;cursor:ns-resize;touch-action:none;border-top:1px solid var(--line);background:rgba(127,127,127,.06)}
.sysPopR i{width:64px;height:5px;border-radius:3px;background:rgba(160,170,185,.6)}
/* ---- 工具（卡片） */
.tbgS{padding:12px;border-radius:12px;border:1px solid rgba(63,182,242,.4);background:rgba(63,182,242,.1);font-size:13.5px;cursor:pointer;margin-bottom:6px}.tbgS span{float:right;opacity:.75}
.tgh{font-size:12.5px;color:var(--sub);font-weight:800;margin:14px 2px 6px}
.wsGrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
.wsCard{position:relative;text-align:left;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px;display:flex;flex-direction:column;gap:3px;min-height:92px}
.wsCard:hover{background:var(--btnh)}.wsCard i{font-style:normal;font-size:22px}.wsCard b{color:var(--strong);font-size:14.5px}.wsCard small{color:var(--sub);font-size:11.5px;line-height:1.35}
.wsCard em{font-style:normal;position:absolute;top:8px;right:8px;background:var(--sel);color:var(--strong);border-radius:9px;padding:1px 7px;font-size:11.5px;font-weight:800}
.s2{display:flex;gap:10px;align-items:flex-start}
.scat{position:sticky;top:8px;flex:none;width:clamp(100px,30vw,210px);display:flex;flex-direction:column;gap:5px;max-height:calc(100vh - 20px);overflow-y:auto}
.scat .sch{font-size:11px;color:var(--sub);margin:6px 4px 0;font-weight:700}
.scat button{text-align:left;background:var(--panel);border:1px solid var(--line);color:var(--sub);border-radius:9px;padding:9px 8px;font-weight:700;font-size:13px;line-height:1.25}
.scat button small{display:block;font-weight:500;font-size:10.5px;opacity:.75;margin-top:2px}.scat button.on{background:var(--sel);border-color:var(--blue);color:var(--strong)}
.ssearch{width:100%;height:34px;font-size:13px;margin-bottom:2px}
.sbody{flex:1;min-width:0}.stt{font-size:19px;margin:2px 2px 12px;color:var(--strong)}
.ssec{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:6px 14px;margin-bottom:14px}
.si{padding:14px 0;border-bottom:1px solid var(--line)}.si:last-child{border-bottom:0}.si>b{display:block;color:var(--strong);margin-bottom:9px;font-size:15px}.si small{display:block;color:var(--sub);font-size:12px;margin-top:6px;line-height:1.5;font-weight:400}
.seg{display:flex;border:1px solid var(--line2);border-radius:9px;overflow:hidden;flex-wrap:wrap}
.seg button{background:var(--card);border:0;border-left:1px solid var(--line2);color:var(--sub);height:36px;min-width:34px;padding:0 10px;font-weight:800}.seg button:first-child{border-left:0}.seg button.on{background:var(--sel);color:var(--strong)}
.pnum{display:flex;align-items:center;gap:6px}.pnum button{width:42px;height:40px;border-radius:10px;border:1px solid var(--line2);background:var(--btn);font-size:20px;font-weight:700}.pnum input{width:96px;height:40px;text-align:center;font-size:16px;font-weight:700}.pnum span{color:var(--sub)}
.tg{position:relative;width:48px;height:28px;flex:none;display:inline-block}.tg input{opacity:0;width:0;height:0}
.tg i{position:absolute;inset:0;background:var(--track);border-radius:20px;transition:.2s}.tg i::before{content:"";position:absolute;width:22px;height:22px;left:3px;top:3px;background:#cfd8e3;border-radius:50%;transition:.2s}
.tg input:checked+i{background:var(--green)}.tg input:checked+i::before{transform:translateX(20px)}
.si.tgr{display:flex;align-items:center;gap:10px}.si.tgr>b{margin:0;flex:1}
.drop{margin-top:8px;border:2px dashed var(--line2);border-radius:12px;padding:18px 10px;text-align:center;color:var(--sub)}.drop.over{border-color:var(--blue);background:rgba(77,201,255,.08)}
#updFab{position:fixed;right:10px;bottom:calc(env(safe-area-inset-bottom,0px) + 14px);z-index:57;display:flex;gap:6px;align-items:flex-end}
#updFab button{box-shadow:0 6px 20px rgba(0,0,0,.45)}#updFab .acc{display:flex;flex-direction:column;align-items:flex-start;padding:6px 14px;border-radius:12px}#updFab small{font-weight:600;opacity:.9;font-size:11px}
.dhero{display:flex;align-items:center;gap:8px;margin:2px 2px 8px}.dhero>div{flex:1}.dhero b{font-size:18px;color:var(--strong)}
.kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px;margin-bottom:10px}
.kpi{position:relative;text-align:left;background:linear-gradient(160deg,color-mix(in srgb,var(--kc) 16%,var(--panel)),var(--panel) 65%);border:1px solid var(--line);border-top:3px solid var(--kc);border-radius:14px;padding:10px 12px;display:flex;flex-direction:column;gap:3px;min-height:96px;overflow:hidden}
.kpi[data-go]:active{transform:scale(.98)}.kpi small{color:var(--sub);font-size:12px;font-weight:700}.kpi b{font-size:22px;color:var(--strong);line-height:1.15;font-variant-numeric:tabular-nums}.kpi b em{font-style:normal}
.kpi span{color:var(--sub);font-size:11.5px;line-height:1.35}.kpi span b{font-size:inherit;line-height:inherit}.kpi[data-go]::after{content:'›';position:absolute;right:10px;top:8px;color:var(--sub);font-size:18px}
.kb{display:block;height:5px;border-radius:3px;background:var(--track);overflow:hidden;margin-top:auto}.kb u{display:block;height:100%;background:var(--kc,var(--blue))}
.djob{padding:7px 0;border-top:1px solid var(--line)}.djob:first-of-type{border-top:0}.djob .kb{margin-top:5px}
#sub{display:none}#sub.on{display:flex;align-items:center;gap:8px;margin:0 0 8px}#sub button{width:38px;height:34px;border-radius:9px;background:var(--btn);border:1px solid var(--line2);font-size:20px;line-height:1}#sub b{font-size:16px;color:var(--strong)}

/* ✨ V0.2.09 介面整理：統一間距、圓角、按鈕大小，長說明收起來（點一下展開） */
html,body{font-size:14.5px;line-height:1.5}
main{max-width:980px;margin:0 auto}
.panel{border-radius:14px;padding:12px 14px;margin:0 0 12px;box-shadow:0 1px 2px #0002;border-color:color-mix(in srgb,var(--line) 85%,transparent)}
.panel h3{font-size:15px;font-weight:800;margin:0 0 8px;letter-spacing:.2px}
.pill{border-radius:999px;padding:6px 13px;min-height:32px;font-weight:600;display:inline-flex;align-items:center;justify-content:center;gap:4px;transition:transform .08s,background .15s,border-color .15s;text-decoration:none}
.pill:active{transform:scale(.96)}
.pill:disabled{opacity:.45;cursor:default}
.row{gap:8px}
.it{padding:9px 2px}
input,select{min-height:36px;border-radius:10px;padding:7px 10px;outline:none;transition:border-color .15s}
input:focus,select:focus{border-color:var(--accent)}
input[type=checkbox]{min-height:0;accent-color:var(--accent);width:16px;height:16px;vertical-align:-3px}
.mu{line-height:1.55}
nav#tabs button.on{border-color:var(--accent);box-shadow:inset 0 -2px 0 var(--accent)}
#v .mu.clamp:not(.open){display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;cursor:pointer}
#v .mu.clamp:not(.open)::before{content:'ℹ ';color:var(--accent);font-weight:800}
.wsCard{border-radius:14px;padding:11px 12px;transition:transform .08s,background .15s;display:grid;grid-template-columns:30px 1fr;column-gap:8px;row-gap:1px;align-items:start;min-height:0}.wsCard:active{transform:scale(.97)}
.wsCard i{grid-row:1/3;font-size:22px;line-height:1.2}.wsCard b{padding-right:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.wsCard em{top:5px!important;right:5px!important;font-size:10.5px!important;padding:0 6px!important}.wsCard small{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tgh{font-size:13px;margin:16px 4px 8px}
::-webkit-scrollbar{width:8px;height:8px}::-webkit-scrollbar-thumb{background:var(--line2);border-radius:8px}::-webkit-scrollbar-track{background:transparent}
#toast{border-radius:14px;box-shadow:0 6px 24px #0007;font-size:13.5px;white-space:pre-line}
#vcf select{padding:3px 2px;min-height:0;font-size:12.5px;flex:1.4!important}#vcf .pill{min-height:0;padding:4px 7px}#vcinf .pill{padding:0 7px;min-height:22px}
</style></head><body>
<div id="app">
<header><div class="bar"><div class="logo"><i></i>__NAME__</div><span class="grow"></span><span class="mu" id="ver">V__VER__</span>
<button class="pill" id="bView" title="切換手機版／網頁版">🖥</button><button class="pill" id="bMode" title="深色／淺色">◐</button></div>
<nav id="tabs"></nav></header>
<main><div id="sub"><button id="subBack" title="回到工具">‹</button><b id="subT"></b></div><div id="v"></div></main></div>
<div id="toast"></div>
<script>
const $=s=>document.querySelector(s),$$=(s,e=document)=>[...e.querySelectorAll(s)];
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const LS={get:(k,d)=>{try{const v=localStorage.getItem('app_'+k);return v==null?d:JSON.parse(v)}catch(e){return d}},set:(k,v)=>{try{localStorage.setItem('app_'+k,JSON.stringify(v))}catch(e){}}};
// 🖼 縮圖還在做（電腦回 503）：等一下自動再要，不會一直空白（V0.3.47）
document.addEventListener('error',e=>{const im=e.target;if(!im||im.tagName!=='IMG')return;const s=im.getAttribute('src')||'';if(!s.includes('/api/vc_thumb')&&!s.includes('/api/fc_thumb'))return;
  const n=+(im.dataset.rt||0);im.style.visibility='hidden';if(n>=8)return;im.dataset.rt=n+1;e.stopImmediatePropagation();
  setTimeout(()=>{if(!im.isConnected)return;im.src=s.replace(/&rt=\d+/,'').replace(/&wait=1/,'')+'&rt='+(n+1)+(n>=6?'&wait=1':'')},Math.min(6000,1200*(n+1)))},true);
document.addEventListener('load',e=>{const im=e.target;if(im&&im.tagName==='IMG'&&im.dataset.rt)im.style.visibility=''},true);
let TT;function toast(t,ms=2600){const d=$('#toast');d.textContent=t;d.style.display='block';clearTimeout(TT);TT=setTimeout(()=>d.style.display='none',ms)}
let TOK=LS.get('tok','');
let PAGEAC=typeof AbortController!=='undefined'?new AbortController():null;   // 換頁時，上一頁還在讀的（GET）直接放掉，連線讓給新頁（V0.3.70）
async function api(u,body,raw,signal){const o={headers:{'x-app-token':TOK}};if(signal)o.signal=signal;else if(body===undefined&&PAGEAC&&!/\/api\/(hello|login|changelog|update)/.test(u))o.signal=PAGEAC.signal;if(body!==undefined){o.method='POST';if(raw){o.body=body}else{o.body=JSON.stringify(body);o.headers['Content-Type']='application/json'}}
  const c0=typeof CUR==='undefined'?'':CUR;let r;try{r=await fetch(u,o)}catch(e){if(e&&e.name==='AbortError'&&!signal)throw new Error('stale');throw e}let j={};try{j=await r.json()}catch(e){}if(r.status===401&&j.login){showLogin();throw new Error('login')}
  if(body===undefined&&c0&&typeof CUR!=='undefined'&&CUR!==c0)throw new Error('stale');   // 讀資料時已經換頁了：舊頁面不要再畫、不要再掛按鈕（V0.2.62：電腦慢的時候會蓋到新頁面）
  return j}
addEventListener('unhandledrejection',e=>{if(e.reason&&e.reason.message==='stale')e.preventDefault()});
const U=(p,q)=>p+'?'+new URLSearchParams(q||{}).toString();
const fmtB=b=>{b=+b||0;return b>=1e12?(b/1e12).toFixed(2)+' TB':b>=1e9?(b/1e9).toFixed(2)+' GB':b>=1e6?(b/1e6).toFixed(0)+' MB':(b/1e3).toFixed(0)+' KB'};
// 主題：深色／淺色／跟著手機（V0.1.40）；字的大小、強調色
const MQ=matchMedia('(prefers-color-scheme: light)');
function setMode(m){LS.set('mode',m);document.documentElement.dataset.mode=m==='auto'?(MQ.matches?'light':'dark'):m}setMode(LS.get('mode','dark'));
MQ.onchange=()=>{if(LS.get('mode','dark')==='auto')setMode('auto')};
function setFz(z){LS.set('fz',z);document.documentElement.style.zoom=z===1?'':z}setFz(LS.get('fz',1));
const ACCS={'':'預設','#3b8eea':'藍','#2bb673':'綠','#e5484d':'紅','#f08c2e':'橘','#9b6cf0':'紫','#e5437f':'粉'};
function setAcc(c){LS.set('acc',c);if(c)document.documentElement.style.setProperty('--accent',c);else document.documentElement.style.removeProperty('--accent')}setAcc(LS.get('acc',''));
$('#bMode').onclick=()=>setMode(document.documentElement.dataset.mode==='dark'?'light':'dark');
function setView(v){document.body.classList.toggle('pc',v==='pc');$('#bView').textContent=v==='pc'?'📱':'🖥';LS.set('view',v)}
setView(new URLSearchParams(location.search).get('pc')?'pc':new URLSearchParams(location.search).get('m')?'m':LS.get('view',innerWidth>1000?'pc':'m'));
$('#bView').onclick=()=>setView(document.body.classList.contains('pc')?'m':'pc');

function showLogin(){$('#tabs').innerHTML='';$('#v').innerHTML=`<div id="login"><h2>🔒 __NAME__</h2><div class="mu">輸入電腦上設定的 PIN</div><input id="pin" type="password" inputmode="text" autocomplete="current-password"><button class="pill acc" id="go" style="width:100%;padding:10px">登入</button></div>`;
  const go=async()=>{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin:$('#pin').value})});const j=await r.json().catch(()=>({}));
    if(j.ok){TOK=j.token;LS.set('tok',TOK);boot()}else toast(j.message||'登入失敗',4000)};
  $('#go').onclick=go;$('#pin').onkeydown=e=>{if(e.key==='Enter')go()};setTimeout(()=>$('#pin').focus(),100)}

// ---- 分頁（新功能加在這裡）
const TABS=[['home','📊 總覽',rDash],['vc','🎞 分類',rVc],['tools','工具',rTools,'sm'],['set','設定',rSet,'sm']];
// 工具（卡片）：(代號, 圖示, 名稱, 說明, 畫面)
const TOOLS=[['整理照片影片',[['wiz','🚀','整理精靈','建議的順序，一步一步：每一步還剩多少、一鍵去做',a=>rWiz(a)],['dpl','🧭','重複資料夾最佳解','七萬多組重複：哪些資料夾整包被複製、該留哪邊、能不能合併',a=>rDpl(a)],['pk','📦','資料夾包','你以前整理過的資料夾（2020-日本旅遊…）整包看、整包放到已篩選',a=>rPk(a)],['dup','🔁','重複檔','內容一模一樣的，⭐ 建議保留哪一份',a=>rDup(a)],['ddir','📁','重複資料夾','哪兩個資料夾有很多一樣的（備份、複製好幾次）',a=>rDdir(a)],['hl','🩺','損毀檢查','打不開／部分損毀／0 位元組；修復、救出',a=>rHl(a)],
    ['find','🔎','搜尋篩選','日期、來源、相機、定位、大小、長度…',a=>rFind(a)],['q','📦','隔離區','搬走的檔案都在這，可以復原',a=>rQ(a)],['junk','🧹','雜物清理','空資料夾、0 位元組、暫存雜檔、最大的檔',a=>rJunk(a)],['sim','🖼','相似照片','不是一模一樣、但幾乎一樣的（改過大小、重新壓縮、連拍）',a=>{if(!a&&SIMK!=='photo'){SIMK='photo';SIMO=0}return rSim(a)}],['burst','📸','連拍精選','一秒拍好幾張的，自動挑最清楚的留下',a=>{if(!a&&SIMK!=='burst'){SIMK='burst';SIMO=0}return rSim(a)}],['simv','🎬','相似影片','內容一樣但被轉檔、重新壓縮、改解析度的影片',a=>{if(!a&&SIMK!=='video'){SIMK='video';SIMO=0}return rSim(a)}],['mtf','🕒','修正修改日期','檔案的「修改日期」改成真正的拍攝日期（檔案總管照日期排就對了，可改回）',a=>rMtf(a)],['ren','📝','依日期改檔名','IMG_1234.jpg → 2023-05-01 14.30.05.jpg（留在原資料夾，可復原）',a=>rRen(a)],['osrc','🏷','依來源整理','截圖、抖音、LINE、修圖、救援的…各放一個資料夾（先預覽）',a=>rOsrc(a)],['org','📅','依日期整理','照拍攝日期搬進「年／月」資料夾（先預覽）',a=>rOrg(a)],['tl','🗓','時間軸','照年、月看照片影片（那年今天也在總覽）',a=>rTl(a)],['geo','🗺','照片地圖','有 GPS 的照片影片在地圖上看：去過哪裡、那裡拍了什麼',a=>rGeo(a)],['slim','🗜','影片瘦身','很大的舊編碼影片轉成 H.265：🎯 自動找 SSIM ≥ 0.985 最省的設定（原檔進轉檔後隔離區）',a=>rSlim(a)],['br','📂','瀏覽資料夾','一層一層看資料夾裡有什麼（縮圖、播放、最愛）',a=>rBr(a)],['evt','🧳','活動','照時間自動分成一次一次的出遊、聚會；可以整理成一個資料夾',a=>rEvt(a)],['fav','⭐','最愛','你標成最愛的照片影片（重複、相似時優先留這份）',a=>rFav(a)],['cams','📱','用過的手機相機','每一台手機／相機拍了多少、從哪年用到哪年',a=>rCams(a)],['bak','💾','備份檢查','哪些照片影片只有一份（硬碟壞了就沒了）、哪些別顆硬碟也有',a=>rBak(a)],['rep','📄','匯出報告','一頁看完：硬碟、種類、重複、損毀、分類、去過的地方…（可存 PDF）',a=>rRep(a)]]],
  ['電腦',[['bg','⏯','後台狀態','每一項背景工作：暫停／繼續／立刻停／順序',a=>rBg(a)],['perf','📊','電腦效能','CPU、記憶體、顯示卡',a=>rPerf(a)],
    ['help','❓','使用說明','建議的整理順序、每個工具做什麼',a=>rHelp(a)],['ops','🧾','操作紀錄','程式做過什麼：搬了什麼、整理了什麼、復原了什麼',a=>rOps(a)],['log','📜','LOG','有問題時看這裡',a=>rLog(a)],['diag','🩺','自我檢查','FFmpeg、Windows ML（找貓狗）、人臉偵測、硬碟空間…有問題截圖給開發者',a=>rDiag(a)],['upd','🆕','線上更新','上傳更新包、下載資料夾的新版、退回前一版',a=>rUpd(a)]]]];
const TOOL=k=>{for(const [,L] of TOOLS)for(const x of L)if(x[0]===k)return x;return null};
// 工具頁怎麼分組（V0.1.36）：照「你想做什麼」分；沒列到的放「其他」
const TOOL_GROUPS=[['🚀 開始',['wiz']],['🧹 清出空間',['dpl','dup','ddir','sim','burst','simv','junk','slim']],['🗂 整理',['pk','org','osrc','ren','mtf','q']],['🔍 看・找',['br','evt','fav','find','tl','geo','cams','rep']],['🩺 檢查・修復',['hl','bak']],['🖥 電腦',['help','bg','perf','ops','log','diag','upd']]];
let TQ='';
let CUR=LS.get('tab','home'),TIMER=null;
if(['dup','hl','find','q','bg','perf'].includes(CUR))CUR='tool:'+CUR;                     // 舊版存的分頁
if(CUR==='ana')CUR='home';
function tabs(){const top=CUR.startsWith('tool:')?'tools':CUR;$('#tabs').innerHTML=TABS.map(([k,n,,c])=>`<button data-t="${k}" class="${c||''} ${k===top?'on':''}">${n}</button>`).join('')
    +TOOL_GROUPS.map(([g,ks])=>`<div class="ntg">${g}</div>`+ks.map(TOOL).filter(Boolean).map(x=>`<button data-t="tool:${x[0]}" class="ntl ${CUR==='tool:'+x[0]?'on':''}">${x[1]} ${x[2]}</button>`).join('')).join('');   // 網頁版：左邊直接列出所有工具（V0.1.57）
  $$('#tabs button').forEach(b=>b.onclick=()=>go(b.dataset.t))}
function go(k,pop){if(k==='act:pet_start'){api('/api/vc_pet',{a:'start',k:'video'}).then(r=>toast((r.message||'')+'（可以先去做別的，看完總覽會告訴你）',4000));return}   // V0.4.18
  if(String(k).startsWith('vc:')){const [f,n]=k.slice(3).split('|');VC.f=f;if(n)VC.fsn=n;if(f==='pet'||f.startsWith('pet_s_pet')){VC.order='pet';VC.g=''}VC.folder='';LS.set('vc',VC);VI.ids=[];k='vc';if(CUR==='vc')return rVc()}   // 「vc:篩選|名字」直接開某個篩選（V0.3.77）
  if(k!==CUR&&PAGEAC){try{PAGEAC.abort()}catch(_){}PAGEAC=new AbortController()}{const sb=document.getElementById('pksb');if(sb&&k!=='tool:pk')sb.remove()}if(k===CUR&&!pop&&!k.startsWith('tool:')){scrollTo({top:0,behavior:'smooth'});return}CUR=k;LS.set('tab',CUR);
  if(!pop)try{history.pushState({t:k},'')}catch(e){}
  tabs();show()}
// 手機的返回鍵：先關掉開著的視窗（浮動視窗、放大、選資料夾、管理分類），再回到上一頁；回到總覽再按才離開
const OVS=[];
function ovOpen(real){OVS.push(real);try{history.pushState({ov:1,t:CUR},'')}catch(e){}}
function ovClose(real){if(OVS.includes(real))history.back();else real()}
addEventListener('popstate',e=>{if(OVS.length){const f=OVS.pop();try{f()}catch(x){}return}
  const t=(e.state&&e.state.t)||'home';if(t!==CUR){if(CUR==='vc'){document.onkeydown=null;onresize=null}go(t,true)}});
function histInit(){try{history.replaceState({t:'home'},'');if(CUR!=='home')history.pushState({t:CUR},'')}catch(e){}}
function show(){clearInterval(TIMER);$('#v').onclick=null;document.body.classList.toggle('vcmode',CUR==='vc');if(CUR!=='vc'){document.onkeydown=null;onresize=null;try{if(VI.pq){VI.pq=false;const b=$('#vcpqb');if(b)b.remove()}}catch(e){}}
  let fn;if(CUR.startsWith('tool:')){const t=TOOL(CUR.slice(5));if(t){fn=t[4];$('#sub').classList.add('on');$('#subT').textContent=t[1]+' '+t[2]}}
  if(!fn){$('#sub').classList.remove('on');fn=(TABS.find(x=>x[0]===CUR)||TABS[0])[2]}
  fn();TIMER=setInterval(()=>{if(!document.hidden)fn(true)},2000);scrollTo(0,0)}
$('#subBack').onclick=()=>history.back();
function goSet(id){go('set');let n=0;const f=()=>{const el=$('#'+id);if(el)el.scrollIntoView({behavior:'smooth'});else if(n++<20)setTimeout(f,150)};setTimeout(f,200)}
// ---- 工具頁
let FS={};
async function rTools(again){const j=await api('/api/fc_state');if(!j.ok)return;FS=j;const C=j.fc||{},B=j.busy||{},nb=Object.values(B).reduce((a,b)=>a+b,0);
  const strip=nb?`🖥 後台：<b>▶ ${nb} 個工作在跑</b>（${Object.entries(B).filter(([,v])=>v).map(([k])=>({scan:'掃描',meta:'讀資訊',hash:'比對重複',health:'損毀檢查',repair:'修復',ana:'資料分析'})[k]||k).join('、')}）<span>看詳細 ›</span>`:'🖥 後台：現在沒有背景工作 ✔ <span>看詳細 ›</span>';
  if(again&&$('#tbgS')){$('#tbgS').innerHTML=strip;return}
  let X={};try{X=await api('/api/badges')}catch(e){}const N=x=>(+x||0).toLocaleString();
  const badge={dup:C.dup_groups?N(C.dup_groups)+' 組':'',hl:C.bad?N(C.bad):'',q:C.quar_n?N(C.quar_n):'',sim:X.sim?N(X.sim)+' 組':'',simv:X.simv?N(X.simv)+' 組':'',burst:X.burst?N(X.burst)+' 串':'',junk:X.junk?N(X.junk):'',slim:X.slim?'省 '+fmtB(X.slim):'',geo:X.geo?N(X.geo):'',ddir:X.ddir?N(X.ddir)+' 對':'',fav:X.fav?'⭐ '+N(X.fav):'',evt:X.evt?N(X.evt)+' 次':'',pk:X.pk?N(X.pk)+' 包':'',dpl:X.dpl?N(X.dpl)+' 對':''};
  const card=x=>{const [k,ic,t,sub]=x;return`<button class="wsCard" data-tl="${k}" data-q="${esc((t+' '+sub).toLowerCase())}"><i>${ic}</i><b>${t}</b><small>${sub}</small>${badge[k]?`<em>${badge[k]}</em>`:''}</button>`};
  const used=new Set(),rec=(LS.get('trec',[])||[]).map(TOOL).filter(Boolean).slice(0,4);
  const grp=TOOL_GROUPS.map(([g,ks])=>{const L=ks.map(TOOL).filter(Boolean);L.forEach(x=>used.add(x[0]));return[g,L]});
  const rest=TOOLS.flatMap(([,L])=>L).filter(x=>!used.has(x[0]));
  $('#v').innerHTML=`<div class="tbgS" id="tbgS">${strip}</div>
   <input id="tq" type="search" placeholder="🔎 找工具（例如：重複、影片、地圖）" value="${esc(TQ)}" style="width:100%;margin:10px 0 2px;padding:10px 12px;border-radius:12px">`
   +(rec.length?`<div class="tgh tgx">🕘 最近用過</div><div class="wsGrid tgx">${rec.map(card).join('')}</div>`:'')
   +grp.concat(rest.length?[['其他',rest]]:[]).map(([g,L])=>`<div class="tgh tgx">${g}</div><div class="wsGrid tgx">${L.map(card).join('')}</div>`).join('')
   +`<div class="tgh tgx">帳號</div><div class="wsGrid tgx"><button class="wsCard" data-tl="logout" data-q="登出 logout"><i>🚪</i><b>登出這支手機</b><small>下次要重新輸入 PIN</small></button></div>
   <div class="wsGrid" id="tqr" hidden></div>`;
  const filt=()=>{TQ=$('#tq').value.trim().toLowerCase();const on=!!TQ;document.querySelectorAll('#v .tgx').forEach(e=>e.hidden=on);const R=$('#tqr');R.hidden=!on;
    if(on){const L=TOOLS.flatMap(([,L])=>L).filter(x=>(x[2]+' '+x[3]+' '+x[0]).toLowerCase().includes(TQ));R.innerHTML=L.map(card).join('')||'<div class="mu">找不到</div>'}};
  $('#tq').oninput=filt;if(TQ)filt();
  $('#v').onclick=async e=>{if(e.target.closest('#tbgS'))return sysPopOpen('bg');const b=e.target.closest('[data-tl]');if(!b)return;const k=b.dataset.tl;
    if(k!=='logout')LS.set('trec',[k,...(LS.get('trec',[])||[]).filter(x=>x!==k)].slice(0,6));
    if(k==='logout'){if(!confirm('登出這支手機？'))return;await api('/api/logout',{});TOK='';LS.set('tok','');return showLogin()}
    go('tool:'+k)}}
// ---- 📊 效能／🖥 背景／🎞 分類／📦 隔離（最上面正中間；效能、背景是浮動視窗：點旁邊關掉，原本在看的頁面不會停）
const SYSPOP_T={pf:'📊 電腦效能',bg:'🖥 後台狀態',up:'⬆ 更新程式（把更新包丟進來）'};
function sysFabInit(){if($('#sysFab'))return;const b=document.createElement('div');b.id='sysFab';
  b.innerHTML='<button type="button" data-t="pf">📊 效能</button><button type="button" data-t="bg">🖥 背景<em hidden></em></button><button type="button" data-t="q">📦 隔離<em class="r" hidden></em></button><button type="button" data-t="up" title="更新程式：按下去把更新包丟進來">⬆ 更新</button>';
  b.onclick=e=>{const x=e.target.closest('[data-t]');if(!x)return;e.stopPropagation();const t=x.dataset.t,w=$('#sysPop');
    if(t==='q'){if(w)w._close();return go('tool:q')}
    if(!w)sysPopOpen(t);else if(w.dataset.t===t)w._close();else w._tab(t)};
  document.body.appendChild(b);fabPoll();setInterval(fabPoll,4000);
  document.addEventListener('dragover',e=>{if([...(e.dataTransfer&&e.dataTransfer.items||[])].some(i=>i.kind==='file'))e.preventDefault()});   // 把 .zip 丟到網頁任何地方＝打開更新視窗並上傳（V0.4.60）
  document.addEventListener('drop',e=>{if(e.target.closest&&e.target.closest('#sysPop,.drop'))return;const f=e.dataTransfer&&e.dataTransfer.files&&e.dataTransfer.files[0];if(!f||!/\.zip$/i.test(f.name))return;e.preventDefault();
    let w=$('#sysPop');if(!w)sysPopOpen('up');else if(w.dataset.t!=='up')w._tab('up');setTimeout(()=>updUp(f),400)})}
async function fabPoll(){if(document.hidden||!TOK)return;if(CUR==='vc'&&Date.now()-(window._fabT||0)<12000)return;window._fabT=Date.now();   // 審片時 12 秒一次（V0.3.72）
 let j;try{j=await api('/api/fc_state')}catch(e){return}if(!j||!j.ok)return;FS=j;const B=j.busy||{},C=j.fc||{},nb=Object.values(B).reduce((a,b)=>a+b,0);
  const set=(t,v)=>{const e=$(`#sysFab [data-t="${t}"] em`);if(e){e.hidden=!v;e.textContent=v||''}};set('bg',nb?nb:'');set('q',C.quar_n?(C.quar_n>9999?Math.round(C.quar_n/1000)+'k':C.quar_n):'');
}
function sysPopOpen(t0){if($('#sysPop'))return;const w=document.createElement('div');w.id='sysPop';
  w.innerHTML=`<div class="sysPopW"><div class="sysPopH"><b class="sysPopTt"></b><span class="sysPopN">點旁邊回到原本的頁面</span><button type="button" class="sysPopX" title="關閉">✕</button></div><div class="sysPopB"><div class="mu">讀取中…</div></div><div class="sysPopR" title="上下拖：調整高度（點兩下恢復 50%）"><i></i></div></div>`;
  document.body.appendChild(w);const W=$('.sysPopW',w),body=$('.sysPopB',w);
  const setH=f=>{f=Math.max(.25,Math.min(.9,+f||.5));W.style.height=(f*100)+'%';return f};let hf=setH(LS.get('syspop_h',.5));
  const gr=$('.sysPopR',w);let dg=null;
  gr.onpointerdown=e=>{gr.setPointerCapture(e.pointerId);dg={y:e.clientY,h:W.getBoundingClientRect().height};e.preventDefault();e.stopPropagation()};
  gr.onpointermove=e=>{if(dg)hf=setH((dg.h+e.clientY-dg.y)/w.getBoundingClientRect().height)};
  gr.onpointerup=gr.onpointercancel=()=>{if(!dg)return;dg=null;LS.set('syspop_h',+hf.toFixed(3))};gr.ondblclick=()=>{hf=setH(.5);LS.set('syspop_h',.5)};
  const tick=again=>{if(!w.isConnected||document.hidden)return;({pf:rPerf,bg:rBg,up:rUpd}[w.dataset.t]||rBg)(again,body)};
  W.addEventListener('dragover',e=>{if(w.dataset.t==='up')e.preventDefault()});W.addEventListener('drop',e=>{if(w.dataset.t!=='up'||(e.target.closest&&e.target.closest('#upDrop')))return;e.preventDefault();const f=e.dataTransfer.files[0];if(f)updUp(f)});   // ⬆ 整個視窗都可以丟更新包（V0.4.60）
  const tab=t=>{w.dataset.t=t;$('.sysPopTt',w).textContent=SYSPOP_T[t]||'';$$('#sysFab [data-t]').forEach(b=>b.classList.toggle('on',b.dataset.t===t));body.innerHTML='<div class="mu">讀取中…</div>';body.onclick=null;tick(false)};
  const iv=setInterval(()=>tick(true),2000);
  const real=()=>{clearInterval(iv);w.remove();$$('#sysFab [data-t]').forEach(b=>b.classList.remove('on'))};ovOpen(real);w._close=()=>ovClose(real);w._tab=tab;tab(SYSPOP_T[t0]?t0:'pf');
  w.addEventListener('click',e=>{if(e.target===w)w._close()});$('.sysPopX',w).onclick=()=>w._close()}
const HN={ok:['✔ 正常','var(--green)'],partial:['◐ 部分損毀','var(--orange)'],broken:['✖ 打不開','var(--red)'],zero:['∅ 0 位元組','var(--red)'],'':['… 還沒檢查','var(--sub)']};
const day=t=>{const d=new Date(t*1000);return isNaN(d)?'':d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')+' '+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')};
const base=p=>String(p||'').split(/[\\/]/).pop(), dir=p=>String(p||'').replace(/[\\/][^\\/]*$/,'');
const TH=(id,w)=>`/api/fc_thumb?id=${id}&w=${w||480}`;

// ---- 📊 總覽（Dashboard）：重點數字卡片 → 背景工作 → 資料分析（每一類、硬碟、資料夾地圖、遊戲軟體、年份）→ 要整理的資料夾
const KC={disk:'#4dc9ff',all:'#b48cff',dup:'#45d483',hl:'#f0ad4e',q:'#ff6577',vc:'#f06ea9',rep:'#2bb673',meta:'#e5c07b'};
async function rDash(again){
  if(again){dashKpi();dashJobs();if(ANAT)rAna(true,ANAT);return}
  $('#v').innerHTML=`<div class="dhero"><div><b>📊 總覽</b><span class="mu" id="dtime"></span></div><div class="row" style="gap:6px"><button class="pill acc" data-go="tool:wiz">🚀 精靈</button><button class="pill" data-go="tool:rep">📄 報告</button><button class="pill" data-d="bg">🖥 背景詳細</button></div></div>
   <form id="dq" class="row" style="gap:6px;margin:0 0 10px"><input id="dqi" type="search" placeholder="🔎 找檔名（例如 IMG_2019、墾丁、.mov）" style="flex:1;min-width:0;padding:10px 12px;border-radius:12px"><button class="pill acc">找</button></form>
   <div class="kpis" id="dk"><div class="mu">讀取中…</div></div>
   <div id="dadv"></div><div id="dvcp"></div><div id="dhist"></div><div id="dotd"></div><div id="drnd"></div><div id="dev"></div>
   <div class="panel" id="djobs"><div class="mu">背景工作讀取中…</div></div>
   <div id="dana"></div><div id="dfold"></div>`;
  $('#v').onclick=e=>{const k=e.target.closest('[data-go]');if(k)return go(k.dataset.go);const d=e.target.closest('[data-d]');if(d&&d.dataset.d==='bg')return sysPopOpen('bg')};
  const H=LS.get('dhide',[]);DSEC.forEach(([id])=>{const e=$('#'+id);if(e&&H.includes(id))e.style.display='none'});
  $('#dq').onsubmit=e=>{e.preventDefault();const q=$('#dqi').value.trim();if(!q)return;FD.f={q};FD.off=0;LS.set('find',FD);go('tool:find')};
  dashKpi();dashJobs();dashOtd();ANAT=null;HOMET=null;                       // 重的分批載（V0.2.61：一次全部送，電腦要排隊、全部都慢）
  const st=(f,ms)=>setTimeout(()=>{if(CUR==='home')f()},ms);st(dashAdv,900);st(dashVcp,1800);st(()=>rAna(false,$('#dana')),2600);st(dashHist,3400);st(dashEv,4200);st(dashRnd,5000);st(()=>rHome(false,$('#dfold')),5800)}
// ---- 🎞 審片進度（V0.2.23）
async function dashVcp(){const el=$('#dvcp');if(!el)return;let j;try{j=await api('/api/vc_prog')}catch(e){return}if(!$('#dvcp')||!j.ok||!j.total)return;
  const pc=Math.round((j.tagged/j.total)*1000)/10,H=j.eta?(j.eta>=3600?(j.eta/3600).toFixed(1)+' 小時':Math.ceil(j.eta/60)+' 分'):'';
  el.innerHTML=`<div class="panel"><div class="row" style="flex-wrap:nowrap"><h3 class="grow" style="margin:0">🎞 審片進度</h3><b style="font-size:18px">${pc}%</b></div>
   <div style="height:10px;border-radius:5px;background:var(--track);overflow:hidden;margin:8px 0"><div style="height:100%;width:${(j.moved/j.total*100).toFixed(2)}%;background:var(--green);float:left"></div><div style="height:100%;width:${((j.tagged-j.moved)/j.total*100).toFixed(2)}%;background:var(--blue);float:left"></div></div>
   <div class="mu" style="font-size:12.5px;line-height:1.6">${j.total.toLocaleString()} 部影片：<b style="color:var(--green)">已搬 ${j.moved.toLocaleString()}</b>・<b style="color:var(--blue)">分好待搬 ${(j.tagged-j.moved).toLocaleString()}</b>・還沒審 <b style="color:var(--text)">${j.todo.toLocaleString()}</b><br>今天 ${j.today.toLocaleString()} 部・這 7 天 ${j.week.toLocaleString()} 部${j.per?`・平均 ${j.per} 秒一部，照這速度還要約 <b style="color:var(--text)">${H}</b>`:''}</div>
   <div class="row" style="gap:6px;margin-top:8px">${j.packs?`<button class="pill acc" data-go="tool:pk">📦 ${j.packs.toLocaleString()} 包整理過的資料夾（${j.pack_v.toLocaleString()} 部）</button>`:''}<button class="pill" data-gvc="pack">🧩 一組一組審</button>${j.sug?`<button class="pill acc" data-gsug="1" title="只看電腦有建議的，一路按 A 確認">💡 ${j.sug.toLocaleString()} 部有建議</button>`:''}${j.pets?`<button class="pill" data-gpet="1">🐾 ${j.pets.toLocaleString()} 部有貓狗</button>`:''}<button class="pill" data-gbig="1" title="整個畫面都是小格子">🔲 縮圖牆</button><button class="pill" data-go="vc">🎞 繼續</button></div></div>`;
  el.onclick=e=>{const sg=e.target.closest('[data-gsug]');if(sg){e.stopPropagation();VC.f='todo_sug';VC.folder='';VC.q='';LS.set('vc',VC);toast('💡 只看電腦有建議的：按 A＝照建議分，不對的按數字改',3500);return go('vc')}
    const p=e.target.closest('[data-gpet]');if(p){e.stopPropagation();VC.f='pet';VC.folder='';VC.q='';LS.set('vc',VC);return go('vc')}
    const bg_=e.target.closest('[data-gbig]');if(bg_){e.stopPropagation();VC.big=true;LS.set('vc',VC);return go('vc')}
    const b=e.target.closest('[data-gvc]');if(!b)return;e.stopPropagation();VC.g=b.dataset.gvc;VC.f='todo';VC.folder='';LS.set('vc',VC);go('vc')}}
// ---- 💡 建議你做（V0.1.35）
async function dashAdv(){const el=$('#dadv');if(!el)return;let j;try{j=await api('/api/advice')}catch(e){return}if(!$('#dadv')||!j.ok)return;const R=j.rows||[];
  if(!R.length){el.innerHTML='<div class="panel" style="color:var(--green)">💡 目前沒有要特別處理的 ✔</div>';return}
  el.innerHTML=`<div class="panel"><div class="row" style="margin-bottom:4px"><h3 class="grow" style="margin:0">💡 建議你接下來做</h3><span class="mu" style="font-size:11px">照能省多少排</span></div>
   ${R.map((a,i)=>`<div class="it row" style="flex-wrap:nowrap;gap:8px;${a.go?'cursor:pointer':''}" ${a.go?`data-go="${a.go}"`:''}><span style="font-size:22px;flex:none">${a.ic}</span>
    <span class="grow" style="min-width:0"><b>${esc(a.title)}</b><br><span class="mu" style="font-size:12px">${esc(a.sub)}</span></span>${a.btn?`<span class="pill ${i?'':'acc'}" style="flex:none">${esc(a.btn)} ›</span>`:''}</div>`).join('')}</div>`}
async function dashKpi(){const el=$('#dk');if(!el)return;let j,A,Vc;try{[j,A,Vc]=await Promise.all([api('/api/fc_state'),api('/api/ana'),api('/api/vc_state')])}catch(e){return}if(!$('#dk')||!j.ok)return;
  const C=j.fc||{},S=(A&&A.res)||{},D=(S.disks||[]).filter(d=>!d.err),cats=(Vc&&Vc.cats)||[],tagged=cats.reduce((a,c)=>a+(c.n||0),0),wait=cats.reduce((a,c)=>a+(c.wait||0),0),N=x=>(+x||0).toLocaleString();
  const card=(k,go,ic,t,v,sub,bar,bc)=>`<button class="kpi" ${go?`data-go="${go}"`:''} style="--kc:${KC[k]}"><small>${ic} ${t}</small><b>${v}</b><span>${sub||''}</span>${bar!=null?`<i class="kb"><u style="width:${Math.max(0,Math.min(100,bar))}%${bc?';background:'+bc:''}"></u></i>`:''}</button>`;
  const pc=(a,b)=>b?Math.round(100*a/b):100;
  el.innerHTML=
   (D.length?D.map(d=>card('disk','',  '💽',`硬碟 ${esc(d.drive)}`,`剩 ${fmtB(d.free)}`,`用了 ${pc(d.used,d.total)}%・共 ${fmtB(d.total)}`,pc(d.used,d.total))).join(''):card('disk','','💽','硬碟','—','分析過才會顯示'))
   +card('all','','📁','全部檔案',S.n?N(S.n)+' 個':N(C.files)+' 個',S.n?`${fmtB(S.b)}・照片 ${N(C.photos)}・影片 ${N(C.videos)}`:`${fmtB(C.bytes)}（照片影片）`)
   +card('dup','tool:dup','🔁','重複可以省',`<em style="color:var(--green)">${fmtB(C.dup_bytes)}</em>`,`${N(C.dup_groups)} 組・多 ${N(C.dup_files)} 份`+(C.hash_done<C.hash_total?`・比對 ${pc(C.hash_done,C.hash_total)}%`:''),C.hash_done<C.hash_total?pc(C.hash_done,C.hash_total):null)
   +card('hl','tool:hl','🩺','損毀檢查',`${N((C.broken||0)+(C.partial||0)+(C.zero||0))} 個`,`部分損毀 ${N(C.partial)}・打不開 ${N(C.broken)}・0 位元組 ${N(C.zero)}`+(C.health_done<C.media?`・檢查 ${pc(C.health_done,C.media)}%`:''),C.health_done<C.media?pc(C.health_done,C.media):null)
   +card('q','tool:q','📦','隔離區',`${N(C.quar_n)} 個`,`${fmtB(C.quar_bytes)}・可以隨時復原`)
   +card('vc','vc','🎞','影片分類',`<em style="color:var(--green)">✔ ${N(tagged)} 部</em>`,`分好 ${C.videos?(100*tagged/C.videos).toFixed(1):0}%（共 ${N(C.videos)} 部）・${cats.length} 個分類`+(wait?`・<b style="color:var(--orange)">待搬 ${N(wait)}</b>`:'・都搬好了'),C.videos?100*tagged/C.videos:0,'var(--green)')
   +card('rep','tool:hl','🛠','修復／救出',`${N(C.rep_ok)} 個`,`試過 ${N(C.rep_done)}・共救出 ${N(C.rep_outs)} 個結果`+(C.rep_q?`・排隊 ${N(C.rep_q)}`:''))
   +card('meta','tool:find','🏷','拍攝資訊',`${pc(C.meta_done,C.media)}%`,`${N(C.meta_done)}／${N(C.media)}・到「🔎 搜尋篩選」用`,pc(C.meta_done,C.media));
  const t=$('#dtime');if(t)t.textContent=' '+(C.t||'')+' 更新'+(C.ff===false?'・⚠ 電腦上找不到 FFmpeg':'')}
async function dashJobs(){const el=$('#djobs');if(!el)return;let j;try{j=await api('/api/state')}catch(e){return}if(!$('#djobs')||!j.ok)return;const c=j.ctl||{},K=c.kinds||[];
  const run=K.filter(k=>k.state!=='idle'||(k.pct!=null&&k.pct<100));const col={run:'var(--green)',pause:'var(--red)',hold:'var(--orange)',idle:'var(--sub)'},nm={run:'▶ 進行中',pause:'⏸ 暫停',hold:'⚖ 讓路',idle:'— 沒事'};
  el.innerHTML=`<div class="row" style="margin-bottom:4px"><h3 class="grow" style="margin:0">🖥 背景工作</h3><span class="mu">CPU ${c.cpu||0}%</span></div>`+
   ((run.length?run:K.slice(0,3)).map(k=>`<div class="djob"><div class="row" style="flex-wrap:nowrap;gap:6px"><b class="grow" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${k.icon} ${esc(k.name)}</b><span style="color:${col[k.state]};font-size:12px;font-weight:800;white-space:nowrap">${nm[k.state]||k.state}</span>
    <span class="mu" style="white-space:nowrap">${k.pct!=null?k.pct+'%':''}</span>${k.state==='pause'?`<button class="pill ok" data-jb="resume" data-k="${k.k}">▶</button>`:`<button class="pill" data-jb="pause" data-k="${k.k}">⏸</button>`}</div>
    ${k.pct!=null?`<i class="kb"><u style="width:${k.pct}%;background:${col[k.state]}"></u></i>`:''}${k.last&&k.state!=='idle'?`<div class="mu" style="font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(k.last)}</div>`:''}</div>`).join(''))
   +(K.length>run.length?`<div class="mu" style="margin-top:4px">其他 ${K.length-run.length} 項沒事 ✔　<a href="#" data-d="bg">看全部 ›</a></div>`:'');
  el.onclick=async e=>{const b=e.target.closest('[data-jb]');if(b){e.stopPropagation();const r=await api('/api/bgctl',{a:b.dataset.jb,k:b.dataset.k});toast(r.ok?'好了':(r.message||'失敗'));dashJobs();return}
    const d=e.target.closest('[data-d]');if(d){e.preventDefault();e.stopPropagation();sysPopOpen('bg')}}}

// ---- 📁 要整理的資料夾、優先保留（Dashboard 最下面）
async function rHome(again,T){T=T||HOMET||$('#v');HOMET=T;const j=await api('/api/fc_state');if(!j.ok)return;const C=j.fc||{},B=j.busy||{},P=j.pause||{};
  const st=`<div class="kv"><span>📁 已掃描</span><b>${(C.files||0).toLocaleString()} 個（照片 ${(C.photos||0).toLocaleString()}・影片 ${(C.videos||0).toLocaleString()}，${fmtB(C.bytes)}）${B.scan?' <span style="color:var(--blue)">掃描中</span>':''}</b>
   <span>🏷 拍攝資訊</span><b>${(C.meta_done||0).toLocaleString()}／${(C.media||0).toLocaleString()}${B.meta?' <span style="color:var(--blue)">讀取中</span>':''}</b>
   <span>🔁 重複</span><b>${(C.dup_groups||0).toLocaleString()} 組、多 ${(C.dup_files||0).toLocaleString()} 份，可省 <span style="color:var(--green)">${fmtB(C.dup_bytes)}</span> <span class="mu">比對 ${(C.hash_done||0).toLocaleString()}／${(C.hash_total||0).toLocaleString()}</span></b>
   <span>🩺 損毀</span><b><span style="color:var(--red)">打不開 ${C.broken||0}</span>・<span style="color:var(--orange)">部分 ${C.partial||0}</span>・0 位元組 ${C.zero||0}・留著 ${C.kept||0} <span class="mu">檢查 ${(C.health_done||0).toLocaleString()}／${(C.media||0).toLocaleString()}</span></b>
   <span>📦 隔離區</span><b>${(C.quar_n||0).toLocaleString()} 個（${fmtB(C.quar_bytes)}）</b>
   <span>🎮 遊戲／軟體素材</span><b>${(C.pkg_n||0).toLocaleString()} 個不列入（${fmtB(C.pkg_bytes)}）<span class="mu"> 到「設定 → 掃描」可以改</span></b></div>${C.ff===false?'<div style="color:var(--orange)">⚠ 電腦上找不到 FFmpeg：沒有縮圖和深度檢查</div>':''}
   <div class="row" style="margin-top:8px">${[['scan','掃描'],['meta','讀取拍攝資訊'],['hash','比對重複'],['health','損毀檢查'],['repair','修復']].map(([k,n])=>P[k]?`<button class="pill er" data-a="resume" data-k="${k}">▶ 繼續${n}</button>`:`<button class="pill" data-a="pause" data-k="${k}">⏸ 暫停${n}</button>`).join('')}</div>`;
  if(again)return;
  const lst=(w,L,mv)=>L.map((p,i)=>`<div class="it row"><span class="grow">${mv?(i+1)+'. ':''}${esc(p)}</span>${mv?`<button class="pill" data-a="move" data-p="${esc(p)}" data-d="-1">↑</button><button class="pill" data-a="move" data-p="${esc(p)}" data-d="1">↓</button>`:''}<button class="pill er" data-a="del" data-w="${w}" data-p="${esc(p)}">－</button></div>`).join('')||'<div class="mu">（還沒有）</div>';
  T.innerHTML=`<div class="panel"><h3>📁 ① 要整理的資料夾</h3>${lst('roots',j.roots,false)}<div class="row" style="margin-top:6px"><input id="nr" class="grow" placeholder="例如 R:\\2022 手機拍的照片"><button class="pill" data-a="add" data-w="roots">＋ 加入</button></div>
    <div class="row" style="margin-top:8px"><button class="pill acc" data-a="scan">▶ 開始掃描（全部）</button></div></div>
   <div class="panel"><h3>⭐ ② 重複時優先保留（上面的優先）</h3>${lst('keep_prio',j.prio,true)}<div class="row" style="margin-top:6px"><input id="np" class="grow" placeholder="資料夾路徑"><button class="pill" data-a="add" data-w="keep_prio">＋ 加入</button></div></div>
   <div class="panel"><h3>🚫 ③ 不要整理的資料夾</h3><div class="mu" style="font-size:12px;margin-bottom:4px">這些資料夾裡的檔案，重複、損毀、分類、相似…全部都不列、也不會被搬（例如工作用的素材、別人的備份）。移出清單就恢復。${C.skip_n?`目前不列 ${(C.skip_n||0).toLocaleString()} 個（${fmtB(C.skip_bytes)}）`:''}</div>${lst('skip_dirs',j.skip||[],false)}<div class="row" style="margin-top:6px"><input id="nk" class="grow" placeholder="資料夾路徑"><button class="pill" data-a="add" data-w="skip_dirs">＋ 加入</button></div></div>
   <div class="panel mu">🔒 不會刪任何檔案：只會搬到同一顆硬碟的「_FileCompare_待確認」，在「📦 隔離區」可以復原。</div>`;
  T.onclick=async e=>{const b=e.target.closest('[data-a]');if(!b)return;const a=b.dataset.a;let body={a};
    if(a==='pause'||a==='resume')body.k=b.dataset.k;
    if(a==='add'){body.which=b.dataset.w;body.p=({roots:$('#nr'),keep_prio:$('#np'),skip_dirs:$('#nk')}[b.dataset.w]).value.trim();if(!body.p)return toast('先輸入資料夾路徑')}
    if(a==='del'){if(!confirm('從清單移除？（已經掃描的資料還在）\n'+b.dataset.p))return;body.which=b.dataset.w;body.p=b.dataset.p}
    if(a==='move'){body.p=b.dataset.p;body.d=+b.dataset.d}
    const r=await api('/api/fc_run',body);toast(r.message||(r.ok?'好了':'失敗'));rHome(false,T);dashKpi()}}

// ---- 🔁 重複檔：一組一組看，選要保留哪一份
const DUP=LS.get('dup',{kind:'',off:0});
let DUPWAS=false;
async function rDup(again){if(again){const s=await api('/api/fc_state');const run=!!(s.bulk||{}).run;if(run||DUPWAS){DUPWAS=run;rDup()}return}const j=await api(U('/api/fc_groups',{offset:DUP.off,kind:DUP.kind,folder:DUP.fo||''}));if(!j.ok)return;const s=await api('/api/fc_state');const Bk=s.bulk||{};
  $('#v').innerHTML=`<div class="panel"><h3>🔁 重複檔　<span class="mu">共 ${(j.total||0).toLocaleString()} 組・第 ${Math.floor(DUP.off/50)+1} 頁</span></h3>
   <div class="row"><select id="dk">${[['','全部'],['photo','只看照片'],['video','只看影片']].map(([k,n])=>`<option value="${k}" ${DUP.kind===k?'selected':''}>${n}</option>`).join('')}</select>
   <button class="pill" data-a="prev">◀</button><button class="pill" data-a="next">▶</button><span class="grow"></span>${Bk.run?`<button class="pill er" data-a="bstop">⏹ 停止全部處理</button>`:`<button class="pill wa" data-a="bulk">⚡ 全部照建議處理</button>`}</div>
   <div class="row" style="margin-top:6px;gap:6px"><input id="dfo" class="grow" placeholder="📁 只看這個資料夾裡的重複（例如 R:\\待整理）" value="${esc(DUP.fo||'')}"><button class="pill ${DUP.fo?'acc':''}" data-a="fo">${DUP.fo?'✕ 取消':'套用'}</button></div>
   ${DUP.fo?`<div class="mu" style="margin-top:4px;font-size:12px">只列「有一份在這個資料夾」的重複：可以省 <b style="color:var(--green)">${fmtB(j.save)}</b>。「⚡ 全部照建議處理」會<b>留別的地方那份、搬走這個資料夾裡的</b>（清空這個資料夾裡的重複）。</div>`:''}
   ${Bk.run?`<div class="mu" style="margin-top:4px">⚡ 處理中：${Bk.g||0} 組、搬了 ${Bk.n||0} 份（${fmtB(Bk.b)}）</div>`:''}</div>
   ${(j.groups||[]).map(g=>`<div class="panel it" data-g="${esc(g.g)}" style="cursor:pointer"><div class="row"><b class="grow">${g.kind==='video'?'🎞':'🖼'} ${esc(g.name)}</b><b style="color:var(--green)">${fmtB(g.save)}</b></div><div class="mu">${g.n} 份一模一樣・${esc(dir(g.path))}</div></div>`).join('')||'<div class="panel mu">沒有重複的檔案（或還在比對中）</div>'}`;
  $('#dk').onchange=()=>{DUP.kind=$('#dk').value;DUP.off=0;LS.set('dup',DUP);rDup()};
  $('#v').onclick=async e=>{const b=e.target.closest('[data-a],[data-g]');if(!b)return;
    if(b.dataset.g)return dupGroup(b.dataset.g);const a=b.dataset.a;
    if(a==='fo'){DUP.fo=DUP.fo?'':$('#dfo').value.trim();DUP.off=0;LS.set('dup',DUP);return rDup()}
    if(a==='prev'){DUP.off=Math.max(0,DUP.off-50);LS.set('dup',DUP);return rDup()}
    if(a==='next'){if(DUP.off+50<j.total){DUP.off+=50;LS.set('dup',DUP)}return rDup()}
    if(a==='bulk'){const P=s.prio||[];if(!confirm('每一組都保留「⭐ 建議」那份，其他搬到隔離區（可以復原）。\n\n優先保留順序：\n'+(P.map((p,i)=>(i+1)+'. '+p).join('\n')||'（還沒設定）')+'\n\n確定？'))return;
      const r=await api('/api/fc_run',{a:'bulk',kind:DUP.kind,folder:DUP.fo||''});toast(r.message);return rDup()}
    if(a==='bstop'){await api('/api/fc_run',{a:'bulk_stop'});toast('停止中…');return setTimeout(()=>rDup(),1500)}}}
async function dupGroup(g){const j=await api(U('/api/fc_group',{g}));if(!j.ok)return;const F=j.files||[];
  $('#v').innerHTML=`<div class="panel"><div class="row"><button class="pill" id="bk">← 回列表</button><span class="grow"></span><span class="mu">${F.length} 份一模一樣・每份 ${fmtB(F[0]?F[0].size:0)}</span></div></div>
   ${F.length<2?'<div class="panel mu">這組已經沒有重複了</div>':F.map(f=>`<label class="panel" style="display:block"><div class="row"><input type="radio" name="kp" value="${f.id}" ${f.suggest?'checked':''}><b>${f.suggest?'⭐ 建議保留　':''}保留這份</b></div>
   <img src="${TH(f.id,480)}" data-zi="${f.id}" data-zk="${f.kind}" onclick="event.stopPropagation();zoomImg(${f.id},'${f.kind}')" loading="lazy" style="width:100%;max-height:300px;object-fit:contain;border-radius:8px;margin:6px 0;background:var(--card);cursor:zoom-in" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'mu',textContent:'沒辦法產生預覽'}))">
   <div style="word-break:break-all">${esc(f.path)}</div><div class="mu">${day(f.mtime)}${f.prio?'・優先順序 #'+f.prio:'・不在優先保留清單'}</div></label>`).join('')}
   ${F.length>=2?`<div class="panel"><button class="pill acc" id="ap" style="width:100%;padding:10px">✔ 保留勾選的那份，其他搬到隔離區</button></div>`:''}`;
  $('#bk').onclick=()=>rDup();if($('#ap'))$('#ap').onclick=async()=>{const k=document.querySelector('input[name=kp]:checked');if(!k)return toast('先勾選要保留哪一份');
    const r=await api('/api/fc_keep',{g,keep:+k.value});toast(r.message||'失敗',4000);if(r.ok)rDup()}}

// ---- 🩺 損毀檢查：一個一個看
const HL=LS.get('hl',{f:'bad',kind:'',off:0});let HR=[],HI=0,HN_=0;
async function rHl(again,keep){if(again)return;if(!keep){const j=await api(U('/api/fc_health',{f:HL.f,kind:HL.kind,offset:HL.off}));if(!j.ok)return;HR=j.rows||[];HN_=j.n||0;HI=Math.min(HI,Math.max(0,HR.length-1))}
  const f=HR[HI];const [nm,col]=f?(HN[f.health]||[f.health,'var(--sub)']):['',''];
  $('#v').innerHTML=`<div class="panel"><div class="row"><select id="hf">${[['bad','全部有問題的'],['broken','✖ 打不開'],['partial','◐ 部分損毀'],['zero','∅ 0 位元組'],['kept','✔ 已決定留著'],['todo','… 還沒檢查'],['green','🟩 畫面大半是綠色'],['repaired','🛠 有救出東西的'],['repq','🛠 排隊修復中']].map(([k,n])=>`<option value="${k}" ${HL.f===k?'selected':''}>${n}</option>`).join('')}</select>
   <select id="hk">${[['','照片＋影片'],['photo','只看照片'],['video','只看影片']].map(([k,n])=>`<option value="${k}" ${HL.kind===k?'selected':''}>${n}</option>`).join('')}</select><span class="grow"></span><span class="mu">${HR.length?(HL.off+HI+1)+'／':''}${HN_.toLocaleString()}</span></div></div>
   ${f?`<div class="panel">${f.size?`<img src="${TH(f.id,960)}" onclick="event.stopPropagation();zoomImg(${f.id},'${f.kind}')" style="width:100%;max-height:55vh;object-fit:contain;border-radius:8px;background:var(--card);cursor:zoom-in" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'mu',textContent:'沒辦法產生預覽（檔案可能壞掉）'}))">`:'<div class="mu">0 位元組：沒有內容可以預覽</div>'}
   <div style="margin-top:6px"><b style="color:${col}">${nm}</b> ${esc(f.health_msg||'')}</div><div style="word-break:break-all"><b>${esc(base(f.path))}</b>　${fmtB(f.size)}　${day(f.mtime)}</div><div class="mu" style="word-break:break-all">${esc(dir(f.path))}</div>
   <div class="row" style="margin-top:8px"><button class="pill ok" data-a="${HL.f==='kept'?'unkeep':'keep'}">${HL.f==='kept'?'↩ 取消留著':'✔ 留著'}</button><button class="pill acc" data-a="quar">📦 搬到隔離區</button><span class="grow"></span><button class="pill" data-a="prev">⏮</button><button class="pill" data-a="next">⏭</button></div>
   <div class="row" style="margin-top:6px"><button class="pill wa" data-a="rep">🛠 試著修復／救出</button><button class="pill" data-a="repall">🛠 這個篩選全部試試看</button><button class="pill er" data-a="qall">📦 這個篩選全部搬到隔離區</button></div><div id="rp" class="mu" style="margin-top:6px"></div></div>`
   :'<div class="panel mu">這裡沒有檔案</div>'}<div class="panel mu">影片要看完整的，請在電腦上按「▶ 打開」。🛠 修復的結果放在同一顆硬碟的「_FileCompare_修復結果」，原檔不動。</div>`;
  if(f&&f.rep)(async()=>{const r=await api(U('/api/fc_repairs',{id:f.id}));const el=$('#rp');if(!el||HR[HI]!==f)return;
    el.innerHTML=r.rep===1?'🛠 排隊修復中…':r.rep===3?'🛠 試過了：'+esc(r.msg):`<b style="color:var(--green)">🛠 ${esc(r.msg)}</b><div class="row" style="margin-top:4px">${(r.items||[]).slice(0,12).map(x=>`<div style="width:31%"><img src="/api/fc_rthumb?id=${x.id}&w=240" title="${esc(x.note)}" loading="lazy" style="width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:6px;background:var(--card)"><div class="mu" style="font-size:11px">${esc(String(x.note).split('：')[0])}</div></div>`).join('')}</div>`})();
  const re=()=>{HL.f=$('#hf').value;HL.kind=$('#hk').value;HL.off=0;HI=0;LS.set('hl',HL);rHl()};$('#hf').onchange=re;$('#hk').onchange=re;
  $('#v').onclick=async e=>{const b=e.target.closest('[data-a]');if(!b||!f)return;const a=b.dataset.a;
    if(a==='prev'){if(HI>0){HI--;rHl(false,true)}else if(HL.off>0){HL.off=Math.max(0,HL.off-100);HI=99;LS.set('hl',HL);rHl()}return}
    if(a==='next'){if(HI+1<HR.length){HI++;rHl(false,true)}else if(HL.off+100<HN_){HL.off+=100;HI=0;LS.set('hl',HL);rHl()}else toast('最後一個了');return}
    if(a==='rep'){if(!f.size)return toast('0 位元組：裡面什麼都沒有');const r=await api('/api/fc_repair',{ids:[f.id]});toast(r.message||'失敗');f.rep=1;return rHl(false,true)}
    if(a==='qall'){if(['ok','todo','kept'].includes(HL.f))return toast('這個篩選不能整批搬');if(!confirm(`把這個篩選的 ${HN_.toLocaleString()} 個檔案全部搬到隔離區？（都可以復原）`))return;
      const r=await api('/api/fc_quar_filter',{f:HL.f,kind:HL.kind});toast(r.message||'失敗',5000);return}
    if(a==='repall'){if(!confirm(`把這個篩選的 ${HN_.toLocaleString()} 個檔案都排進修復／救出？（原檔不動，背景做）`))return;const r=await api('/api/fc_repair',{f:HL.f,kind:HL.kind});toast(r.message||'失敗');return}
    const r=await api('/api/fc_decide',{id:f.id,a});toast(r.message||'失敗');if(r.ok){HR.splice(HI,1);HN_--;if(!HR.length)return rHl();HI=Math.min(HI,HR.length-1);rHl(false,true)}}}

// ---- 🔎 搜尋篩選（跟電腦版同一套條件）
const FD=LS.get('find',{f:{},order:'taken',off:0});let FR=[],FN=0;
const SRCS=[['camera','📷 手機／相機拍的'],['screenshot','🖥 截圖'],['douyin','🎵 抖音'],['inshot','✂ InShot'],['capcut','✂ 剪映'],['wechat','💬 微信／LINE'],['edited','🎨 修圖過'],['recovered','🛟 救援救回'],['thumb','🗂 縮圖快取'],['download','⬇ 下載／不明']];
const DSS=[['','全部'],['reliable','日期可靠'],['mtime','⚠ 只有修改日期'],['conflict','檔名和拍攝日期對不上'],['todo','還沒讀資訊']];
const HLS=[['ok','✔ 正常'],['partial','◐ 部分損毀'],['broken','✖ 打不開'],['zero','∅ 0 位元組'],['todo','… 還沒檢查']];
const ORS=[['taken','拍攝時間 舊→新'],['taken_desc','拍攝時間 新→舊'],['path','路徑'],['size_desc','大小 大→小'],['dur_desc','長度 長→短'],['mp','解析度 小→大']];
function findForm(){const f=FD.f,sel=(id,L,v)=>`<select id="${id}">${L.map(([k,n])=>`<option value="${k}" ${String(v||'')===k?'selected':''}>${n}</option>`).join('')}</select>`,
  inp=(id,ph,v)=>`<input id="${id}" placeholder="${ph}" value="${esc(v||'')}" style="width:100%">`,chk=(nm,L,on)=>L.map(([k,n])=>`<label class="pill" style="display:inline-block;margin:2px"><input type="checkbox" data-c="${nm}" value="${k}" ${(on||[]).includes(k)?'checked':''}> ${n}</label>`).join('');
  return `<details class="panel" ${LS.get('find_open',true)?'open':''} id="fdet"><summary><b>🔎 條件</b></summary>
   <div class="it">${inp('fq','關鍵字（檔名／路徑）',f.q)}</div><div class="it">${inp('ffo','只找這個資料夾底下，例如 R:\\2022 手機拍的照片',f.folder)}</div>
   <div class="it row">${sel('fk',[['','照片＋影片'],['photo','只看照片'],['video','只看影片']],f.kind)}${sel('fds',DSS,f.dsrc)}${sel('fg',[['','定位：全部'],['1','有定位'],['0','沒有定位']],f.gps)}</div>
   <div class="it"><div class="mu">來源</div>${chk('src',SRCS,f.src)}</div>
   <div class="it row"><input id="fd1" placeholder="從 2018-05" value="${esc(f.d1||'')}" style="flex:1"><input id="fd2" placeholder="到 2019-12" value="${esc(f.d2||'')}" style="flex:1"></div>
   <div class="it">${inp('fm','相機／手機（例如 Xiaomi、RX100）',f.model)}</div>
   <div class="it"><div class="mu">狀態</div>${chk('health',HLS,f.health)}</div>
   <div class="it row"><label><input type="checkbox" id="fmo" ${f.motion?'checked':''}> 動態照片</label><label><input type="checkbox" id="fdu" ${f.dup?'checked':''}> 有重複的</label><label><input type="checkbox" id="ffv" ${f.fav?'checked':''}> ⭐ 最愛</label></div>
   <div class="it row"><input id="fmp1" placeholder="最少 MP" value="${esc(f.mp_min||'')}" style="flex:1"><input id="fmp2" placeholder="最多 MP" value="${esc(f.mp_max||'')}" style="flex:1"></div>
   <div class="it row"><input id="fs1" placeholder="最小 MB" value="${esc(f.size_min||'')}" style="flex:1"><input id="fs2" placeholder="最大 MB" value="${esc(f.size_max||'')}" style="flex:1"></div>
   <div class="it row"><input id="fu1" placeholder="影片最短 秒" value="${esc(f.dur_min||'')}" style="flex:1"><input id="fu2" placeholder="影片最長 秒" value="${esc(f.dur_max||'')}" style="flex:1"></div>
   <div class="it row">${sel('for',ORS,FD.order)}<span class="grow"></span><button class="pill" data-a="clr">清除</button><button class="pill acc" data-a="go">🔎 搜尋</button></div></details>`}
function readForm(){const v=id=>($('#'+id)||{}).value||'',C=nm=>$$(`[data-c=${nm}]:checked`).map(x=>x.value);
  FD.f={q:v('fq').trim(),folder:v('ffo').trim(),kind:v('fk'),dsrc:v('fds'),gps:v('fg'),src:C('src'),d1:v('fd1').trim(),d2:v('fd2').trim(),model:v('fm').trim(),health:C('health'),
   motion:$('#fmo').checked?'1':'',dup:$('#fdu').checked?'1':'',fav:$('#ffv').checked?'1':'',mp_min:v('fmp1'),mp_max:v('fmp2'),size_min:v('fs1'),size_max:v('fs2'),dur_min:v('fu1'),dur_max:v('fu2')};FD.order=v('for');LS.set('find',FD)}
async function rFind(again){if(again)return;const j=await api('/api/fc_search',{f:FD.f,offset:FD.off,order:FD.order,facets:true});if(!j.ok)return;FR=j.rows||[];FN=j.n||0;const fa=j.facets||{},SN=j.src_nm||{},DN=j.dsrc_nm||{};
  $('#v').innerHTML=findForm()+`<div class="panel"><b>找到 ${FN.toLocaleString()} 個，${fmtB(j.bytes)}</b>
   <div class="mu">📅 ${(fa.years||[]).map(([y,n])=>(y||'?')+'：'+n.toLocaleString()).join('　')}</div><div class="mu">📥 ${(fa.src||[]).map(([s,n])=>esc(SN[s]||'… 還沒讀')+'：'+n.toLocaleString()).join('　')}</div>
   <div class="mu">🕒 ${(fa.dsrc||[]).map(([s,n])=>esc(DN[s]||s)+'：'+n.toLocaleString()).join('　')}</div>
   <div class="row" style="margin-top:6px"><button class="pill" data-a="prev">◀</button><span class="mu">第 ${Math.floor(FD.off/60)+1}／${Math.max(1,Math.ceil(FN/60))} 頁</span><button class="pill" data-a="next">▶</button><span class="grow"></span>
   <button class="pill" data-a="all">全選這頁</button><button type="button" class="pill" data-a="fslide">▶ 輪播</button><button class="pill er" data-a="quar">📦 勾選的搬到隔離區</button><button type="button" class="pill" data-a="fav">⭐ 勾選的加最愛</button><button type="button" class="pill" data-a="tagc">📚 勾選的分到…</button><button class="pill" data-a="csv">💾 CSV</button></div></div>
   <div class="panel">${FR.map(f=>{const [hn,hc]=HN[f.health]||[f.health,'var(--sub)'];return `<label class="it row" style="align-items:flex-start"><input type="checkbox" data-id="${f.id}">
    ${f.size?`<img src="${TH(f.id,240)}" data-zi="${f.id}" data-zk="${f.kind}" onclick="event.preventDefault();event.stopPropagation();zoomImg(${f.id},'${f.kind}')" loading="lazy" style="width:96px;height:72px;object-fit:cover;border-radius:6px;background:var(--card);cursor:zoom-in" onerror="this.style.visibility='hidden'">`:''}
    <span class="grow" style="word-break:break-all"><b>${esc(base(f.path))}</b><div class="mu">${f.taken?day(f.taken):'—'}${f.date_src==='mtime'?' ⚠':''}・${esc((SN[f.src]||'').split(' ').slice(1).join(' '))}${f.model?'・'+esc(f.model):''}${f.w?'・'+f.w+'×'+f.h:''}・${fmtB(f.size)}</div>
    <div class="mu" style="color:${hc}">${hn}</div><div class="mu">${esc(dir(f.path))}</div></span></label>`}).join('')||'<div class="mu">沒有符合的檔案</div>'}</div>`;
  $('#fdet').ontoggle=()=>LS.set('find_open',$('#fdet').open);
  $('#v').onclick=async e=>{const b=e.target.closest('[data-a]');if(!b)return;const a=b.dataset.a;
    if(a==='go'){readForm();FD.off=0;LS.set('find',FD);return rFind()}
    if(a==='clr'){FD.f={};FD.off=0;LS.set('find',FD);return rFind()}
    if(a==='prev'){FD.off=Math.max(0,FD.off-60);LS.set('find',FD);return rFind()}
    if(a==='next'){if(FD.off+60<FN){FD.off+=60;LS.set('find',FD)}return rFind()}
    if(a==='all'){$$('#v input[data-id]').forEach(x=>x.checked=true);return}
    if(a==='csv'){location.href=U('/api/fc_csv',{f:JSON.stringify(FD.f),order:FD.order});return}
    if(a==='fav'){const ids=$$('#v input[data-id]:checked').map(x=>+x.dataset.id);if(!ids.length)return toast('先勾選檔案');for(const id of ids)await api('/api/fav',{id,on:true});return toast(`⭐ ${ids.length} 個加到最愛`)}
    if(a==='fslide')return slideFrom($('#v'));
    if(a==='tagc'){const ids=$$('#v input[data-id]:checked').map(x=>+x.dataset.id);if(!ids.length)return toast('先勾選檔案');return tagPick(ids)}
    if(a==='quar'){const ids=$$('#v input[data-id]:checked').map(x=>+x.dataset.id);if(!ids.length)return toast('先勾選檔案');if(!confirm(`把勾選的 ${ids.length} 個檔案搬到隔離區？（可以復原）`))return;
      const r=await api('/api/fc_quar_many',{ids});toast(r.message||'失敗',4000);return rFind()}}}

// ---- 📈 資料分析（跟電腦一樣：每一類、硬碟、資料夾地圖、遊戲／軟體清單、照片影片年份）
// 🩺 容量健康（V0.2.15）：重複多出來的、損毀的、隔離區各佔多少；損毀的一鍵先隔離
const capPanel=c=>{if(!c||!c.total)return '';const T=c.total,P=x=>(x/T*100),seg=[['var(--green)',c.ok,'正常'],['var(--orange)',c.dup,'重複多出來的份'],['var(--red)',c.bad,'損毀'],['#8f7cf0',c.quar,'已在隔離區']];
  return `<div class="panel" id="capp"><h3>🩺 容量健康：重複、損毀各佔多少</h3>
   <div style="display:flex;height:22px;border-radius:7px;overflow:hidden;background:var(--track);margin:6px 0">${seg.filter(s=>s[1]>0).map(([col,v,n])=>`<div title="${n} ${fmtB(v)}" style="width:${Math.max(.6,P(v))}%;background:${col}"></div>`).join('')}</div>
   ${seg.map(([col,v,n],k)=>`<div class="row it" style="flex-wrap:nowrap"><i style="width:12px;height:12px;border-radius:3px;background:${col};flex:none"></i><b style="width:54px">${P(v).toFixed(1)}%</b><span class="grow">${n}${k===1?` <span class="mu">${(c.dup_files||0).toLocaleString()} 份</span>`:k===2?` <span class="mu">${(c.bad_n||0).toLocaleString()} 個</span>`:k===3?` <span class="mu">${(c.quar_n||0).toLocaleString()} 個</span>`:''}</span><span class="mu">${fmtB(v)}</span>${k===1&&c.dup?'<button class="pill" data-cap="dup" style="padding:2px 8px">🔁 處理</button>':''}${k===2&&c.bad?`<button class="pill er" data-cap="bad" style="padding:2px 8px" ${c.run?'disabled':''}>📦 全部先隔離</button>`:''}</div>`).join('')}
   <div class="mu" style="font-size:12px;margin-top:4px">全部 ${fmtB(T)}。${c.run?`<b style="color:var(--blue)">背景搬移中：${(c.run_n||0).toLocaleString()} 個…</b> `:''}損毀的先搬到每顆硬碟的隔離區（不是刪除），之後想救、想看都可以在「📦 隔離區」復原。</div></div>`};
document.addEventListener('click',async e=>{const b=e.target.closest('[data-cap]');if(!b)return;
  if(b.dataset.cap==='dup')return go('tool:dup');
  if(!confirm('損毀的（打不開、部分損毀、0 位元組）全部先搬到隔離區？\n\n只是搬到同一顆硬碟的隔離區，不是刪除；在「📦 隔離區」可以依原因整批復原。'))return;
  const r=await api('/api/fc_quar_filter',{f:'bad'});toast(r.ok?'📦 開始搬損毀的到隔離區（背景做）':(r.message||'現在有別的搬移在做，等一下再按'),4000);b.disabled=true});
const ANA=LS.get('ana',{mode:'b',p:'',t:''});let AG=-1,AV=null,ASEL=null;
const pct=(a,b)=>b?(100*a/b):0;
function sqf(items,x,y,w,h){items=items.filter(i=>i[0]>0);const tot=items.reduce((s,i)=>s+i[0],0),out=[];if(!tot||w<=0||h<=0)return out;
  const sc=w*h/tot;items=items.map(i=>[i[0]*sc,i[1]]);const worst=(r,s)=>{const t=r.reduce((a,i)=>a+i[0],0),mx=Math.max(...r.map(i=>i[0])),mn=Math.min(...r.map(i=>i[0]));return Math.max(s*s*mx/(t*t),t*t/(s*s*mn))};
  let i=0;while(i<items.length){const s=Math.min(w,h);let row=[items[i++]];while(i<items.length&&worst(row.concat([items[i]]),s)<=worst(row,s))row.push(items[i++]);
    const t=row.reduce((a,i)=>a+i[0],0);if(w>=h){const cw=h?t/h:0;let cy=y;for(const [v,o] of row){const ch=cw?v/cw:0;out.push([x,cy,cw,ch,o]);cy+=ch}x+=cw;w-=cw}
    else{const rh=w?t/w:0;let cx=x;for(const [v,o] of row){const c2=rh?v/rh:0;out.push([cx,y,c2,rh,o]);cx+=c2}y+=rh;h-=rh}}return out}
const dom=e=>{let b='other',m=-1;for(const k in e||{})if(e[k][1]>m){m=e[k][1];b=k}return b};
const bars=(rows,lw)=>rows.map(([l,r,segs,f])=>{const t=segs.reduce((s,x)=>s+x[1],0);return `<div class="row" style="gap:6px;margin:3px 0;flex-wrap:nowrap"><span style="width:${lw||38}%;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(l)}">${esc(l)}</span>
  <span class="grow" style="background:var(--track);border-radius:4px;height:14px;overflow:hidden"><span style="display:flex;height:100%;width:${Math.max(.3,Math.min(100,f*100))}%">${segs.map(([c,v,tip])=>`<i title="${esc(tip)}" style="background:${c};width:${pct(v,t)}%"></i>`).join('')}</span></span><span class="mu" style="width:92px;white-space:nowrap">${esc(r)}</span></div>`}).join('');
let ANAT=null,HOMET=null;
async function rAna(again,T){T=T||ANAT||$('#v');ANAT=T;const V=await api('/api/ana');if(!V.ok)return;AV=V;const S=V.res||{},C=V.cats||[],CN={},CC={};C.forEach(([k,n,c])=>{CN[k]=n;CC[k]=c});
  let st;if(V.run){const d=V.done||0,t=V.total||0;st=`<span style="color:var(--blue)">▶ 分析中：${d.toLocaleString()} 個檔${t&&d<=t?`（約 ${pct(d,t).toFixed(0)}%）`:''}</span> <span class="mu">${esc(String(V.cur||'').slice(-60))}</span>`}
  else if(V.req)st=V.pause?'⏸ 暫停中':'排隊中（等掃描做完）';else if(S.gen)st=`上次分析 ${day(S.t1)}・共 <b>${(S.n||0).toLocaleString()}</b> 個檔、<b>${fmtB(S.b)}</b>`;else st=(V.roots||[]).length?'還沒分析過：按「🔄 重新分析」':'先在總覽加入要整理的資料夾';
  const btn=`<button class="pill acc" data-a="start">🔄 重新分析</button><button class="pill ${V.pause?'er':''}" data-a="${V.pause?'resume':'pause'}">${V.pause?'▶ 繼續':'⏸ 暫停'}</button>${V.run?'<button class="pill er" data-a="stop">⏹ 停止</button>':''}`;
  if(again&&$('#ast')&&S.gen===AG){$('#ast').innerHTML=st;$('#abtn').innerHTML=btn;return}
  AG=S.gen;const E=S.eff||{},i=ANA.mode==='b'?1:0,tot=Object.values(E).reduce((s,v)=>s+v[i],0);let acc=0;
  const segs=C.filter(([k])=>E[k]&&E[k][i]>0).sort((a,b)=>E[b[0]][1]-E[a[0]][1]);
  const cg=segs.map(([k,,c])=>{const a=acc;acc+=pct(E[k][i],tot);return `${c} ${a}% ${acc}%`}).join(',')||'var(--track) 0 100%';
  const P=S.pkgs||{},M=S.media||{},Y=M.years||{},yk=Object.keys(Y).sort(),ymax=Math.max(1,...yk.map(y=>((Y[y].photo||[0])[0])+((Y[y].video||[0])[0])));
  const IN=M.in_pkg||{},inn=Object.values(IN).reduce((s,v)=>s+v[0],0),SRC=M.src||{},smax=Math.max(1,...Object.values(SRC).map(v=>v[0])),Rt=S.roots||[],rmax=Math.max(1,...Rt.map(r=>r.b));
  T.innerHTML=`<div class="panel"><h3>📈 資料分析</h3><div id="ast">${st}</div><div class="row" id="abtn" style="margin-top:6px">${btn}</div>
   <div class="mu" style="margin-top:6px">所有檔案（不只照片影片）各佔多少。遊戲、軟體、程式專案「整包資料夾」算一個：遊戲裡的圖片是素材、不算照片。只看，不動任何檔案。</div></div>
   <div class="panel"><h3>① 每一類佔多少 <select id="am" style="float:right"><option value="b" ${ANA.mode==='b'?'selected':''}>看大小</option><option value="n" ${ANA.mode==='n'?'selected':''}>看檔案數</option></select></h3>
    <div class="row" style="align-items:flex-start;flex-wrap:wrap"><div style="width:180px;height:180px;border-radius:50%;background:conic-gradient(${cg});display:grid;place-items:center;margin:auto">
     <div style="width:118px;height:118px;border-radius:50%;background:var(--panel);display:grid;place-items:center;text-align:center"><div><b style="font-size:17px">${ANA.mode==='b'?fmtB(tot):tot.toLocaleString()}</b><div class="mu">全部</div></div></div></div>
     <div class="grow" style="min-width:230px">${segs.map(([k,n,c])=>`<div class="row it" style="flex-wrap:nowrap"><i style="width:12px;height:12px;border-radius:3px;background:${c};flex:none"></i><b style="width:54px">${pct(E[k][i],tot).toFixed(1)}%</b><span class="grow">${esc(n)}${P[k]?` <span class="mu">${P[k][0].toLocaleString()} 包</span>`:''}</span><span class="mu">${fmtB(E[k][1])}・${E[k][0].toLocaleString()} 個</span></div>`).join('')||'<div class="mu">還沒有資料</div>'}${V.cap&&V.cap.total&&ANA.mode==='b'?[['var(--red)','其中：損毀',V.cap.bad,(V.cap.bad_n||0).toLocaleString()+' 個'],['var(--orange)','其中：重複多出來的份',V.cap.dup,(V.cap.dup_files||0).toLocaleString()+' 份']].map(([c,n,b,m])=>`<div class="row it" style="flex-wrap:nowrap;font-style:italic"><i style="width:12px;height:12px;border-radius:3px;border:2px solid ${c};flex:none"></i><b style="width:54px;color:${c}">${tot?(b/tot*100).toFixed(1):0}%</b><span class="grow">${n}</span><span class="mu">${fmtB(b)}・${m}</span></div>`).join(''):''}</div></div></div>
   ${capPanel(V.cap)}
   <div class="panel"><h3>② 硬碟、每個要整理的資料夾</h3>${bars((S.disks||[]).map(d=>d.err?['💽 '+d.drive,d.err,[],0]:['💽 '+d.drive,'剩 '+fmtB(d.free),[['var(--blue)',d.used,'用了 '+fmtB(d.used)],['var(--track)',d.free,'還剩 '+fmtB(d.free)]],1]))}
    ${bars(Rt.map(r=>['📁 '+r.root,r.err||fmtB(r.b),C.filter(([k])=>(r.eff||{})[k]).map(([k,n,c])=>[c,r.eff[k][1],n+' '+fmtB(r.eff[k][1])]),r.b/rmax]))}</div>
   <div class="panel"><h3>③ 資料夾地圖</h3><div class="mu">面積＝大小、顏色＝主要是哪一類。點一塊看說明，有「🔍 點進去」就能往下看。</div>
    <div class="row" style="margin:6px 0"><button class="pill" data-a="top">⏫ 最上層</button><button class="pill" data-a="up">⬆ 上一層</button><span class="grow mu" id="acr" style="word-break:break-all"></span></div>
    <div id="atm" style="position:relative;height:${innerWidth<700?320:440}px;background:var(--card);border-radius:8px;overflow:hidden"></div><div id="asel" class="mu" style="margin-top:6px"></div></div>
   <div class="panel"><h3>④ 遊戲、軟體、程式專案（整包算）</h3><div class="row"><select id="apk"><option value="">全部</option>${[['game','🎮 遊戲'],['app','🧩 軟體'],['dev','💻 程式開發'],['backup','💾 備份'],['system','⚙ 系統']].map(([k,n])=>`<option value="${k}" ${ANA.t===k?'selected':''}>${n}</option>`).join('')}</select><span class="mu grow" id="apks"></span></div><div id="apl"></div></div>
   <div class="panel"><h3>⑤ 照片、影片：每年幾個</h3><div style="display:flex;align-items:flex-end;gap:2px;height:150px;overflow-x:auto">${yk.map(y=>{const a=(Y[y].photo||[0])[0],b=(Y[y].video||[0])[0];return `<div title="${esc(y)}：照片 ${a.toLocaleString()}、影片 ${b.toLocaleString()}" style="flex:1;min-width:16px;display:flex;flex-direction:column;justify-content:flex-end;height:100%;text-align:center">
     <i style="background:${CC.video};height:${100*b/ymax}%"></i><i style="background:${CC.photo};height:${100*a/ymax}%"></i><span class="mu" style="font-size:9.5px">${y==='?'?'不明':String(y).slice(2)}</span></div>`}).join('')||'<span class="mu">還沒有資料</span>'}</div>
    <div class="mu"><span style="color:${CC.photo}">■</span> 照片　<span style="color:${CC.video}">■</span> 影片（年份用 EXIF／影片內建／檔名的日期，都沒有就用修改日期）</div>
    <h3 style="margin-top:10px">從哪裡來</h3>${bars(Object.entries(SRC).sort((a,b)=>b[1][0]-a[1][0]).map(([k,v])=>[(V.src_nm||{})[k]||k||'還沒讀到',v[0].toLocaleString()+' 個',[[CC.photo,v[0],fmtB(v[1])]],v[0]/smax]))}
    ${inn?`<div style="margin-top:6px">🎮 另外有 <b>${inn.toLocaleString()}</b> 個圖片／影片在遊戲、軟體資料夾裡（${fmtB(Object.values(IN).reduce((s,v)=>s+v[1],0))}），是素材，沒算進去。</div>`:''}</div>`;
  $('#am').onchange=()=>{ANA.mode=$('#am').value;LS.set('ana',ANA);AG=-1;rAna(false,T)};
  $('#apk').onchange=()=>{ANA.t=$('#apk').value;LS.set('ana',ANA);anaPkgs()};
  T.onclick=async e=>{const b=e.target.closest('[data-a],[data-tm]');if(!b)return;
    if(b.dataset.tm!==undefined){const o=ASEL=ATM[+b.dataset.tm];anaSel(o,CN,CC);return}
    const a=b.dataset.a;if(a==='top')return anaDir('');if(a==='up'){const r=await api(U('/api/ana_dir',{p:ANA.p}));return anaDir((r.node||{}).parent||'')}
    if(a==='in')return anaDir(b.dataset.p);
    if(['start','pause','resume','stop'].includes(a)){if(a==='stop'&&!confirm('停止分析？'))return;const r=await api('/api/ana_run',{a});toast(r.message||'好了');rAna(true,T)}};
  anaDir(ANA.p,true);anaPkgs()}
let ATM=[];
const tmName=o=>o.rest?(o.more?`其他 ${o.more.toLocaleString()} 個資料夾＋這層的檔案`:'這層的檔案＋小資料夾'):(({game:'🎮 ',app:'🧩 ',dev:'💻 ',backup:'💾 ',system:'⚙ '})[o.pkg]||'')+base(String(o.path).replace(/[\\/]+$/,''));
async function anaDir(p,first){const r=await api(U('/api/ana_dir',{p}));const el=$('#atm');if(!el)return;
  if(!r.ok){if(p&&first)return anaDir('');el.innerHTML=`<div class="mu" style="padding:20px;text-align:center">${esc(r.message||'還沒分析過')}</div>`;$('#acr').textContent='';return}
  ANA.p=p;LS.set('ana',ANA);const CC={};(AV.cats||[]).forEach(([k,,c])=>CC[k]=c);
  const it=(r.kids||[]).map(k=>[k.b,k]);if(r.rest&&r.rest.b>0)it.push([r.rest.b,Object.assign({},r.rest,{rest:1,path:''})]);it.sort((a,b)=>b[0]-a[0]);
  const W=el.clientWidth,H=el.clientHeight;ATM=[];
  el.innerHTML=sqf(it,0,0,W,H).map(([x,y,w,h,o],i)=>{ATM.push(o);const c=CC[o.pkg||dom(o.eff)]||'#4b5563';
    return `<div data-tm="${i}" style="position:absolute;left:${x+1}px;top:${y+1}px;width:${Math.max(0,w-2)}px;height:${Math.max(0,h-2)}px;background:${c};${o.rest?'filter:brightness(.65);':''}border-radius:3px;overflow:hidden;color:#fff;font-size:11.5px;padding:2px 4px;cursor:pointer;line-height:1.3">${w>40&&h>18?`<b>${esc(tmName(o))}</b>${h>34?`<br>${fmtB(o.b)}`:''}`:''}</div>`}).join('');
  $('#acr').innerHTML=`<b>${esc(r.node.path||'全部要整理的資料夾')}</b>　${fmtB(r.node.b)}`;$('#asel').innerHTML='點一塊看說明'}
function anaSel(o,CN,CC){const e=o.eff||{},t=Object.values(e).reduce((s,v)=>s+v[1],0)||1;
  $('#asel').innerHTML=`<div class="panel" style="margin:0"><b>${esc(tmName(o))}</b>　${fmtB(o.b)}・${(o.n||0).toLocaleString()} 個檔${o.path?`<div class="mu" style="word-break:break-all">${esc(o.path)}</div>`:''}
   ${o.pkg?`<div>整包算「${esc(CN[o.pkg])}」：${esc(o.why)}</div>${Object.keys(o.raw||{}).length?`<div class="mu">裡面：${Object.entries(o.raw).sort((a,b)=>b[1][1]-a[1][1]).slice(0,5).map(([k,v])=>esc(CN[k]||k)+' '+v[0].toLocaleString()+' 個').join('、')}</div>`:''}`
   :Object.entries(e).sort((a,b)=>b[1][1]-a[1][1]).slice(0,7).map(([k,v])=>`<span style="color:${CC[k]}">■</span> ${esc(CN[k]||k)} ${pct(v[1],t).toFixed(0)}%（${fmtB(v[1])}）`).join('　')}
   ${o.mt?`<div class="mu">最近修改 ${day(o.mt).slice(0,10)}</div>`:''}${o.kids?`<button class="pill acc" data-a="in" data-p="${esc(o.path)}" style="margin-top:6px">🔍 點進去</button>`:''}</div>`}
async function anaPkgs(){const r=await api(U('/api/ana_pkgs',{t:ANA.t}));const el=$('#apl');if(!el||!r.ok)return;const L=r.rows||[];
  $('#apks').textContent=`${L.length.toLocaleString()} 包，共 ${fmtB(L.reduce((s,x)=>s+x.b,0))}`;
  el.innerHTML=L.slice(0,150).map(x=>`<div class="it"><div class="row" style="flex-wrap:nowrap"><b class="grow" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${({game:'🎮',app:'🧩',dev:'💻',backup:'💾',system:'⚙'})[x.pkg]||''} ${esc(base(x.path.replace(/[\\/]+$/,'')))}</b><b>${fmtB(x.b)}</b></div>
   <div class="mu">${esc(x.why)}・最近修改 ${day(x.mt).slice(0,10)}</div><div class="mu" style="word-break:break-all;font-size:11px">${esc(x.path)}</div></div>`).join('')+(L.length>150?`<div class="mu">…還有 ${L.length-150} 包（電腦版看得到全部）</div>`:'')||'<div class="mu">沒有找到</div>'}

// ---- 🎞 影片快速分類（全螢幕、不用捲動：上面分類按鈕、下面 16 格；按了先記下來，一個段落後再搬）
const VC=LS.get('vc',{f:'todo',order:'path',folder:''});let VI={ids:[],i:0,cats:[],it:null,g:null,cache:{},undo:[],next:true,mv:{}};
function bestGrid(n,W,H,ar){let b=[0,n,1,1,0,0];for(const k of [n,n-1]){if(k<=0)continue;for(let c=1;c<=k;c++){const r=Math.ceil(k/c);if(c*r!==k&&k!==n)continue;
  const cw=Math.min(W/c,H/r*ar),ch=cw/ar,sc=cw*ch*(c*r===k?1:0.8);if(sc>b[0]*1.0001)b=[sc,k,c,r,cw,ch]}}return b.slice(1)}   // 最後一列沒排滿的：除非大很多，不然用排滿的（例如 3×5）
const fmtT=s=>{s=Math.max(0,Math.round(+s||0));const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;return h?`${h}:${String(m).padStart(2,'0')}:${String(x).padStart(2,'0')}`:`${m}:${String(x).padStart(2,'0')}`};
async function rVc(again){
  if(again){if(!(VI.mv&&VI.mv.run)&&Date.now()-(VI.stT||0)<10000)return;VI.stT=Date.now();const s=await api('/api/vc_state');   // 沒在搬：10 秒問一次就好（V0.3.71）
 if(!s.ok||!$('#vcf'))return;const was=VI.mv.run;VI.mv=s.mv||{};if(was||VI.mv.run){VI.cats=s.cats;vcBtns();vcPend();if(was&&!VI.mv.run)vcList()}
   if(VI.petRun&&!s.pet&&VI.ids.length){const m=await api('/api/vc_marks',{ids:VI.ids});if(m.ok&&$('#vcf')){VI.pets=new Set(m.pets||[]);VI.dark=new Set(m.dark||[]);vcStrip();vcPetChips();toast('🐾 電腦看完了：🐾 '+VI.pets.size+'、🌑 '+VI.dark.size+'（這份清單裡）',3000)}}VI.petRun=!!s.pet;VI.petN=s.petn;vcPetChips();return}   // 🐾 看完自動補記號（V0.4.22）
  const s=await api('/api/vc_state');if(!s.ok)return;VI.cats=s.cats||[];VI.next=s.next;VI.mv=s.mv||{};VI.vs=s.vs||{};VI.sp=s.sp||{};
  const side=VC.side||'right',top=side==='top';
  const nrw=innerWidth<620,sw=nrw?'flex:1 1 30%;min-width:0;font-size:12px':'flex:1;min-width:0';
  const bar=`<div class="row" style="gap:4px;flex-wrap:${nrw?'wrap':'nowrap'};flex:none"><button class="pill ${VC.kind==='photo'?'acc':''}" data-a="kind" title="切換：影片／照片" style="flex:none;font-size:16px">${VC.kind==='photo'?'📷':'🎞'}</button><select id="vcfl" style="${sw}"></select><select id="vcod" style="${sw}"></select><select id="vcln" style="${sw}" class="${VC.ln?'acc':''}"></select>${nrw?'<div style="flex-basis:100%;height:0"></div>':''}
     <button class="pill ${VC.g?'acc':''}" data-a="grp" title="🧩 相關的排一起：資料夾包／同類型／同一段時間">${GICON[VC.g||'']}</button><button class="pill ${VC.rf===false?'':'acc'}" data-a="rf" title="⚡ 做好的先：有 16 格的排前面、還沒做的排後面（背景繼續做）、做不出畫面的排最後">⚡</button><button class="pill ${VC.big?'acc':''}" data-a="big" title="🔲 縮圖牆：上面的 16 格收起來、整個畫面都是小格子（滑鼠滑過去翻 16 格、雙擊放大看）（V 鍵）">🔲</button><button class="pill" data-a="views" title="🔖 存好的檢視：把現在的篩選、分組、排序、搜尋存起來，下次一按就回來">🔖</button><button class="pill ${VC.q?'acc':''}" data-a="q" title="🔍 找檔名／資料夾名有某些字的（例如：日本 2019；空白分開＝都要有）（/ 鍵）">🔍</button><button class="pill ${VC.folder?'acc':''}" data-a="folder" title="只看某個資料夾">📁</button><button class="pill" data-a="many" title="📚 整批分類：整份清單一次分、照建議分、📷 照相機一次分、🐾 找貓狗／人臉、📏 我的規則">📚</button><button class="pill ${VI.msel?'acc':''}" data-a="msel" title="多選：點下面的小格子勾好幾部，再按分類一次分好">☑</button><button class="pill" data-a="side" title="按鈕放右邊／左邊／上面">⇆</button></div>`,info=`
    <div class="row" style="gap:6px;flex-wrap:nowrap;flex:none;font-size:12px">${VC.folder?`<button class="pill acc" data-a="exitdir" title="退出這個資料夾，回到全部影片" style="padding:2px 8px;font-size:12px;min-height:0;flex:none;max-width:40%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">📁 只看：${esc(String(VC.folder).split(/[\\/]/).filter(Boolean).pop()||VC.folder)}　✕ 退出</button>`:''}${VC.q?`<button class="pill acc" data-a="qx" title="不找了，回到全部" style="padding:2px 8px;font-size:12px;min-height:0;flex:none;max-width:35%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">🔍 ${esc(VC.q)}　✕</button>`:''}<b id="vcpos" style="white-space:nowrap"></b><span id="vcpetc"></span><span id="vcinf" class="mu grow" style="${VC.th?'word-break:break-all':'white-space:nowrap;overflow:hidden;text-overflow:ellipsis'}"></span></div>`;
  const nb=x=>`<button class="pill" data-a="${x[0]}" style="flex:1;max-width:76px;min-width:44px;font-size:18px;padding:0" title="${x[2]}">${x[1]}</button>`;
  const foot=`<div id="vcft" style="flex:none;display:flex;flex-direction:${side==='left'?'row-reverse':'row'};align-items:stretch;gap:5px;${VC.fh?`height:${VC.fh}px`:'height:46px'}">
     <div id="vcpd" class="mu" style="flex:1;min-width:0;font-size:11.5px;overflow:auto;align-self:center;max-height:100%;line-height:1.35"></div>
     <button class="pill" data-a="clean" style="flex:none;padding:0 12px" title="處理有問題的影片">🧹</button><button class="pill acc" data-a="move" id="vcmv" style="flex:none;white-space:nowrap;padding:0 12px">🚚 搬</button>
     ${(side==='left'?[['next','▶','下一部'],['undo','↶','復原（右鍵／H：剛剛分過的）'],['prev','◀','上一部']]:[['prev','◀','上一部'],['undo','↶','復原（右鍵／H：剛剛分過的）'],['next','▶','下一部']]).map(nb).join('')}</div>`;
  const strip=`<div id="vcs" style="${VC.big?'flex:1 1 auto;min-height:0':`flex:none;height:${VC.sh?VC.sh+'px':'24vh'}`};overflow-y:auto;position:relative;overscroll-behavior:contain;display:flex;flex-wrap:wrap;gap:3px;align-content:flex-start;-webkit-overflow-scrolling:touch"></div>`;
  const hz=k=>`<div class="vch" data-h="${k}" style="flex:none;width:14px;cursor:col-resize;touch-action:none;display:grid;place-items:center"><i style="width:4px;height:44px;border-radius:2px;background:var(--line2)"></i></div>`,hB=top?'':hz('b');
  const grid=`<div id="vcg" style="${VC.big?'flex:none;height:0;overflow:hidden;':'flex:1;min-height:0;'}min-width:0;position:relative;background:#000;border-radius:8px;overflow:hidden;touch-action:pan-y"></div>`;
  const btns=top?`<div id="vctop" style="${VC.th?'flex:1;min-height:0':'flex:none;max-height:34vh'};overflow:auto"><div id="vcb"></div></div>`
                :`<div id="vctop" style="flex:none;width:${VC.bw?VC.bw+'px':'min(27vw,150px)'};display:flex;flex-direction:column;overflow:auto;padding-bottom:2px"><div id="vcb" style="flex:1;min-height:0"></div></div>`;
  $('#v').innerHTML=`<div id="vcf" style="position:fixed;left:0;right:0;bottom:0;top:0;z-index:30;background:var(--bg);display:flex;flex-direction:column;gap:4px;padding:4px 4px calc(4px + env(safe-area-inset-bottom,0px))">
   ${bar}
   <div style="flex:1;min-height:0;display:flex;gap:0;flex-direction:${side==='left'?'row-reverse':'row'}">
    <div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:4px">
     <div id="vchd" style="flex:none;display:flex;flex-direction:column;gap:4px;overflow:hidden;${VC.th?`height:${VC.th}px`:''}">${info}<div id="vcgb" style="flex:none;display:none"></div>${top?btns:''}</div>
     <div class="vch" data-h="top" style="flex:none;height:12px;margin:-4px 0;cursor:row-resize;touch-action:none;display:grid;place-items:center"><i style="width:44px;height:4px;border-radius:2px;background:var(--line2)"></i></div>
     ${grid}
     <div class="vch" data-h="s" style="${VC.big?'display:none;':''}flex:none;height:24px;margin:-10px 0;position:relative;z-index:3;cursor:row-resize;touch-action:none;display:grid;place-items:center"><i style="width:44px;height:4px;border-radius:2px;background:var(--line2)"></i></div>
     <canvas id="vcmap" title="整份清單的進度：亮的＝分好了、暗的＝還沒分、白線＝現在這部；點一下跳過去" style="flex:none;height:7px;width:100%;cursor:pointer;border-radius:3px;background:#1a1f27"></canvas>
     ${strip}
     <div class="vch" data-h="bot" style="flex:none;height:12px;margin:-4px 0;cursor:row-resize;touch-action:none;display:grid;place-items:center"><i style="width:44px;height:4px;border-radius:2px;background:var(--line2)"></i></div>
     ${foot}
    </div>${top?'':hB+btns}
   </div>
   <div id="vcz" style="display:none;position:absolute;inset:0;z-index:5;background:#000d;place-items:center"></div></div>`;
  vcFit();
  $('#vcod').innerHTML=[['path','照資料夾'],['size','大→小'],['size_asc','小→大'],['dur','長→短'],['dur_asc','短→長'],['taken','拍攝日期 舊→新'],['taken_desc','拍攝日期 新→舊'],['mtime_desc','最近修改的先'],['rand','🔀 打散（隨機）'],['tagged_last','最近分好的先'],['pet','🐾 最像貓狗的先'],['res','畫質 高→低'],['res_asc','畫質 低→高（舊手機、壓過的先）']]
    .map(([k,n])=>`<option value="${k}" ${VC.order===k?'selected':''}>${n}</option>`).join('');
  $('#vcod').onchange=()=>{VC.order=$('#vcod').value;LS.set('vc',VC);vcList()};
  $('#vcln').innerHTML=[['','⏱ 長度大小'],['s30','短於 30 秒'],['s180','30 秒～3 分'],['s600','3～10 分'],['l600','10 分以上'],['l1800','30 分以上'],['nodur','不知道長度'],['b100','小於 100 MB'],['b1g','100 MB～1 GB'],['g1','1 GB 以上'],['g4','4 GB 以上'],['por','📱 直的（手機直拍、短影音）'],['lan','🖥 橫的']]
    .map(([k,n])=>`<option value="${k}" ${(VC.ln||'')===k?'selected':''}>${n}</option>`).join('');
  $('#vcln').onchange=()=>{VC.ln=$('#vcln').value;LS.set('vc',VC);$('#vcln').classList.toggle('acc',!!VC.ln);vcList()};
  $('#vcs').onscroll=vcStripMore;
  $$('.vch').forEach(h=>{h.onpointerdown=e=>{e.preventDefault();h.setPointerCapture(e.pointerId);const k=h.dataset.h,x0=e.clientX,y0=e.clientY;
      const S=$('#vcs'),B=$('#vctop'),HD=$('#vchd'),FT=$('#vcft'),w0=k==='s'?S.offsetHeight:k==='b'?B.offsetWidth:k==='bot'?FT.offsetHeight:HD.offsetHeight,lft=(VC.side||'right')==='left';let raf=0;
      h.onpointermove=ev=>{const dx=ev.clientX-x0,dy=ev.clientY-y0;
        if(k==='s'){VC.sh=Math.round(Math.max(60,Math.min(innerHeight*.8,w0-dy)));S.style.height=VC.sh+'px'}
        else if(k==='b'){VC.bw=Math.round(Math.max(70,Math.min(innerWidth*.6,w0+(lft?dx:-dx))));B.style.width=VC.bw+'px'}
        else if(k==='bot'){VC.fh=Math.round(Math.max(34,Math.min(innerHeight*.4,w0-dy)));FT.style.height=VC.fh+'px'}
        else{VC.th=Math.round(Math.max(40,Math.min(innerHeight*.7,w0+dy)));HD.style.height=VC.th+'px'}
        if(!raf)raf=requestAnimationFrame(()=>{raf=0;vcDraw();vcBtns()})};
      h.onpointerup=()=>{h.onpointermove=null;LS.set('vc',VC);if(k==='top')rVc()}};
    h.ondblclick=()=>{delete VC[{s:'sh',b:'bw',top:'th',bot:'fh'}[h.dataset.h]];LS.set('vc',VC);toast('回到預設大小');rVc()}});
  vcFilters();vcBtns();vcPend();
  $('#vcfl').onchange=()=>{VC.f=$('#vcfl').value;{const x=SCF.find(y=>'pet_s_'+y[0]===VC.f);if(x)VC.fsn=x[1]}LS.set('vc',VC);vcList()};
  $('#vcf').onclick=vcClick;$('#vcf').oncontextmenu=e=>{const b=e.target.closest('[data-a="undo"]');if(b){e.preventDefault();return vcHist()}
    const cb=e.target.closest('#vcb [data-c]');if(cb){e.preventDefault();if(VI.lastPT&&VI.lastPT!=='mouse')return;const c=VI.cats[+cb.dataset.c];if(!c)return;const on=VC.f==='c'+c.id;VC.f=on?'todo':'c'+c.id;LS.set('vc',VC);VI.ids=[];if(VI.msel)vcMselOff();toast(on?'↩ 回到還沒分類的':`🔎 只看分到「${c.name}」的（再按一次右鍵回去）`,2500);return rVc()}};
  let sx=0,sy=0;const G=$('#vcg');G.ontouchstart=e=>{sx=e.touches[0].clientX;sy=e.touches[0].clientY};
  G.ontouchend=e=>{const dx=e.changedTouches[0].clientX-sx,dy=e.changedTouches[0].clientY-sy;if(Math.abs(dx)>60&&Math.abs(dx)>Math.abs(dy)*1.5){vcGo(VI.i+(dx<0?1:-1));e.preventDefault()}
    else if(dy<-80&&Math.abs(dy)>Math.abs(dx)*1.5){e.preventDefault();const id=VI.ids[VI.i],hc=(VI.it&&VI.it.id===id&&VI.it.hint&&VI.it.hint[0])||(VI.sug&&VI.sug[id]);   // 往上滑＝照 💡 建議分（V0.3.65）
      if(!hc)return toast('這部沒有建議（往上滑＝照 💡 建議分）',1500);const ci=VI.cats.findIndex(c=>c.id===hc);if(ci>=0)vcTag(ci)}};
  onresize=()=>{if($('#vcg')){vcFit();vcDraw();vcBtns()}};
  document.onkeydown=e=>{if(!$('#vcf')||/INPUT|SELECT|TEXTAREA/.test(e.target.tagName))return;if(VI.pq&&vcPQKey(e))return;const k=e.key;if(document.querySelector('body>div[style*="z-index: 80"],body>div[style*="z-index: 85"],body>div[style*="z-index:80"],body>div[style*="z-index:85"]'))return;   // 放大看／對話框開著：鍵盤給它用（V0.3.14）
    const Zv=$('#vcz');if(Zv&&Zv.style.display!=='none'&&Zv.querySelector('[data-gc]')){            // 整組一覽開著：數字＝整組分類、]＝下一組、Esc＝關（V0.2.56）
      if(k==='Backspace'){const b=Zv.querySelector('[data-gv="undo"]');if(b){b.click();e.preventDefault()}return}
      if(e.shiftKey&&/^Digit[0-9]$/.test(e.code||'')){const b=Zv.querySelectorAll('[data-gc]')[10+(+e.code.slice(5)+9)%10];if(b){b.click();e.preventDefault()}return}
      if(/^[0-9]$/.test(k)){const b=Zv.querySelectorAll('[data-gc]')[(+k+9)%10];if(b){b.click();e.preventDefault()}}else if(k===']'){const b=Zv.querySelector('[data-gv="next"]');if(b){b.click();e.preventDefault()}}else if(k==='Escape'){const b=Zv.querySelector('[data-gv="x"]');if(b){b.click();e.preventDefault()}}
      return}
    if(Zv&&Zv.style.display!=='none'&&Zv.style.display!==''){if(k==='Escape'){e.preventDefault();vczHide()}return}   // 有視窗開著（說明、比較、規則…）：Esc 關掉，其他鍵不動作（V0.3.64）
    if(e.repeat&&(/^[0-9]$/.test(k)||/^Digit/.test(e.code||'')||k==='r'||k==='R'||k==='a'||k==='A')){e.preventDefault();return}   // 按著不放不會一直分下去（V0.3.31）
    if(k==='?'){e.preventDefault();return vcKeys()}
    if(e.shiftKey&&(k==='D'||k==='d')){e.preventDefault();if(!VI.simFor)return toast('剛剛分的那部沒有相似版本',1500);const sid=VI.simFor;VI.simFor=0;return (async()=>{const r=await api('/api/vc_simdel',{id:sid});toast(r.message||'失敗',3000);if(r.ok&&r.ids){const pv={};r.ids.forEach(x=>{pv[x]=VI.tags[x]||0});await vcReCats();await vcList();VI.undo.push(['many',pv,VI.i,'Delete（相似版本）'])}})()}
    if(k==='h'||k==='H'){e.preventDefault();return vcHist()}
    if((k==='a'||k==='A')&&e.shiftKey&&!e.ctrlKey&&!e.metaKey){e.preventDefault();const id=VI.ids[VI.i],hc=(VI.it&&VI.it.id===id&&VI.it.hint&&VI.it.hint[0])||(VI.sug&&VI.sug[id]);   // Shift＋A＝勾起來所有「建議同一類」的（V0.3.47）
      if(!hc)return toast('這部沒有建議',1200);const L=VI.ids.filter(x=>!VI.tags[x]&&(VI.sug&&VI.sug[x]===hc||x===id));VI.msel=true;VI.sel=new Set(L);vcSel(0,false);vcStrip();const c=VI.cats.find(x=>x.id===hc);
      return toast(`☑ 勾了 ${L.length.toLocaleString()} 部「建議 ${c?c.name:''}」的：看一下，取消不對的，按 A 或 ${c?c.name:''} 一次分`,4000)}
    if((k==='a'||k==='A')&&!e.ctrlKey&&!e.metaKey&&!e.shiftKey&&VI.it&&VI.it.sus_c&&VI.it.sus&&VI.it.id===VI.ids[VI.i]){e.preventDefault();const ci=VI.cats.findIndex(c=>c.id===VI.it.sus_c);if(ci>=0){VI.it.sus='';return vcTag(ci)}}   // 🧐 A＝改成電腦建議的那類（V0.4.54）
    if((k==='a'||k==='A')&&!e.ctrlKey&&!e.metaKey&&!e.shiftKey){e.preventDefault();const id=VI.ids[VI.i],hc=(VI.it&&VI.it.id===id&&VI.it.hint&&VI.it.hint[0])||(VI.sug&&VI.sug[id]);   // A＝照 💡 建議分（V0.3.43）
      if(!hc)return toast('這部沒有建議',1200);const ci=VI.cats.findIndex(c=>c.id===hc);if(ci<0)return;return vcTag(ci)}
    if((k==='t'||k==='T')&&!e.ctrlKey&&!e.metaKey){e.preventDefault();const id=VI.ids[VI.i];if(!id)return;if(!VI.msel){VI.msel=true;VI.sel=new Set()}vcSel(id,!VI.sel.has(id));VI.lastSel=VI.i;   // T＝勾／取消這一部，自動往下（像 Photo Mechanic）（V0.3.66）
      if(VI.i<VI.ids.length-1)vcGo(VI.i+1);else vcStrip();return toast(`☑ 勾了 ${VI.sel.size} 部（T 繼續勾，按分類一次套用，Esc 取消）`,1200)}
    if((k==='r'||k==='R')&&!e.ctrlKey&&!e.metaKey){e.preventDefault();if(VI.lastCat==null||!VI.cats[VI.lastCat])return toast('還沒分過，不知道要重複哪一類',1500);return vcTag(VI.lastCat)}
    if((k==='v'||k==='V')&&!e.ctrlKey&&!e.metaKey){e.preventDefault();const b=document.querySelector('[data-a="big"]');if(b)b.click();return}
    if((k==='n'||k==='p')&&!e.ctrlKey&&!e.metaKey){e.preventDefault();const d=k==='n'?1:-1;let j=VI.i+d;while(j>=0&&j<VI.ids.length&&VI.tags[VI.ids[j]])j+=d;if(j<0||j>=VI.ids.length)return toast(d>0?'後面都分好了 🎉':'前面都分好了',1500);if(Math.abs(j-VI.i)>1)toast(`⏭ 跳過 ${Math.abs(j-VI.i)-1} 部已經分好的`,1200);return vcGo(j)}
    if(k==='F'&&e.shiftKey&&!e.ctrlKey&&!e.metaKey){e.preventDefault();return vcFsug()}
    if(k==='P'&&e.shiftKey&&!e.ctrlKey&&!e.metaKey){e.preventDefault();if(String(VC.f).startsWith('pet'))return;VC.f='pet';VC.order='pet';VC.g='';LS.set('vc',VC);VI.ids=[];toast('🐾 只看還沒分類、有貓或狗的，最像的排前面（V＝縮圖牆；Ctrl＋A 整組勾）',3500);return rVc()}
    if((k==='z'||k==='Z')&&(e.ctrlKey||e.metaKey)&&!e.shiftKey){e.preventDefault();return vcUndo()}   // Ctrl＋Z＝復原（V0.3.75）
    if(k==='/'){e.preventDefault();const b=document.querySelector('[data-a="q"]');if(b)b.click();return}
    if(k==='Escape'&&VI.msel){vcMselOff();toast('取消勾選',1500);e.preventDefault();return}
    if((e.ctrlKey||e.metaKey)&&(k==='a'||k==='A')){const [a,z]=vcGrpR(VI.i);e.preventDefault();return vcSelRange(a,z,VI.gn&&VI.gn.length?'這一組 ':'全部 ')}
    if(e.shiftKey&&(k==='ArrowRight'||k==='ArrowLeft'||k==='ArrowDown'||k==='ArrowUp')){e.preventDefault();const st=VI.lastSel!=null&&VI.msel?VI.lastSel:VI.i,d={ArrowRight:1,ArrowLeft:-1,ArrowDown:vcCols(),ArrowUp:-vcCols()}[k],to=Math.max(0,Math.min(VI.ids.length-1,st+d));
      if(!VI.msel){VI.msel=true;VI.sel=new Set();vcSel(VI.ids[st],true)}const a=Math.min(st,to),z=Math.max(st,to);for(let q=a;q<=z;q++)vcSel(VI.ids[q],true);VI.lastSel=to;vcSel(0,false);vcStrip();
      const el=$('#vcs')&&$('#vcs').querySelector(`[data-j="${to}"]`);if(el)el.scrollIntoView({block:'nearest'});return toast(`☑ 選了 ${VI.sel.size} 部（Shift＋方向鍵繼續選）`,1500)}
    if(e.shiftKey&&/^Digit[0-9]$/.test(e.code||'')){const d=+e.code.slice(5),ci=10+(d+9)%10;if(VI.cats[ci]){e.preventDefault();return VI.hov!=null&&!VI.msel&&VI.hov!==VI.i&&Date.now()-(VI.hovT||0)<2500?vcTagJ(VI.hov,ci):vcTag(ci)}}   // ⇧＋數字＝第 11～20 類（V0.3.02）
    if(/^[0-9]$/.test(k)&&VI.hov!=null&&!VI.msel&&VI.hov!==VI.i&&Date.now()-(VI.hovT||0)<2500){e.preventDefault();return vcTagJ(VI.hov,(+k+9)%10)}
    if(VC.big&&(k==='ArrowDown'||k==='ArrowUp')&&!e.shiftKey){e.preventDefault();return vcGo(VI.i+(k==='ArrowDown'?1:-1)*vcCols())}
    if(/^[0-9]$/.test(k)){vcTag((+k+9)%10);e.preventDefault()}else if(k==='ArrowRight'||k===' '){vcGo(VI.i+1);e.preventDefault()}else if(k==='ArrowLeft'){vcGo(VI.i-1);e.preventDefault()}
    else if(k==='Backspace'){vcUndo();e.preventDefault()}else if(k===']'&&VI.gn&&VI.gn.length){vcGrpNext();e.preventDefault()}else if(k==='['&&VI.gn&&VI.gn.length){const [s]=vcGrpRange(VI.i);if(s<=0)return toast('已經是第一組了',1200);const [s2]=vcGrpRange(s-1);toast('⏮ '+(VI.gn[VI.gi[s2]]||'上一組'),1200);vcGo(s2);e.preventDefault()}else if((k==='g'||k==='G')&&VI.gn&&VI.gn.length){vcGrpView();e.preventDefault()}};
  vcList()}
function vcPT(){return /^pet($|_dog$|_cat$|_s_pet)/.test(VC.f||'')?'&p=1':''}   // 🐾 只看貓狗時，小格子用最像貓狗的那一格（V0.3.94）
function vcPetChips(){const pc=$('#vcpetc');const cm=/^c\d+$/.test(String(VC.f||''))?VI.cats.find(x=>'c'+x.id===VC.f):null;if(pc&&cm){pc.innerHTML=`<button class="pill acc" data-a="tofilter" style="padding:1px 8px;font-size:12px;min-height:0;margin-left:4px">🔎 只看「${esc(cm.name)}」　✕ 回去</button>`;return}if(pc)pc.innerHTML=(VI.petN&&VI.petN[1]?`<span class="mu" title="電腦正在背景看內容（貓狗、人臉、全黑…）" style="font-size:11.5px;margin-left:6px">🐾 看內容 ${VI.petN[0].toLocaleString()}／${VI.petN[1].toLocaleString()}</span>`:'')+(!VI.pq&&(VI.pets.size||String(VC.f).startsWith('pet'))?`<button class="pill acc" data-a="petq" title="⚡ 一頁一頁快速審：最像貓狗的一頁先全部勾好，你只要把不是的點掉，按 Enter 分好、下一頁" style="padding:1px 8px;font-size:12px;min-height:0;margin-left:4px">⚡🐾 快速審</button>`:'')+(!String(VC.f).startsWith('pet')?(VI.pets.size?`<button class="pill" data-a="petf" title="只看還沒分類、有貓或狗的" style="padding:1px 8px;font-size:12px;min-height:0;margin-left:4px">🐾 ${VI.pets.size.toLocaleString()}</button>`:'')+(VI.dark.size?`<button class="pill" data-a="darkf" title="只看還沒分類、全黑／沒東西／沒動的（可能是誤錄）" style="padding:1px 8px;font-size:12px;min-height:0;margin-left:4px">🌑 ${VI.dark.size.toLocaleString()}</button>`:''):`<button class="pill acc" data-a="tofilter" style="padding:1px 8px;font-size:12px;min-height:0;margin-left:4px">${String(VC.f).startsWith('pet_s_')?'🔎 '+esc(VC.fsn||'電腦看的內容'):'🐾 只看有貓狗的'}　✕</button>`)}   // 上方 🐾／🌑 小按鈕（V0.4.22 拆出來）
const SCF=[['petppl','🐾👤 有貓狗、也有人'],['petonly','🐾 只有貓狗（沒拍到人）'],['many','👥 3 個人以上'],['junk','🌑 全黑／沒東西／沒動'],['dark','🌑 很暗／全黑'],['flat','⬜ 畫面沒東西'],['still','🧱 畫面沒動'],['screen','📺 拍到螢幕／網頁'],['food','🍜 食物'],['car','🚗 車子／交通'],['boat','⛵ 船'],['sea','🏖 海邊／湖邊'],['mount','🏔 山／風景'],['snow','⛄ 雪地'],['baby','👶 嬰兒床／尿布'],['animal','🐦 其他動物']];   // 🔎 電腦猜的內容（V0.3.84，跟 pets.SCENES 對應）
function vcFilters(){const o=[['todo','還沒分類的'],['todo_np','還沒分類・不在資料夾包裡'],['todo_pk','還沒分類・在資料夾包裡'],['todo_sug','💡 還沒分類・電腦有建議的'],['pet','🐾 還沒分類・有貓或狗的'],['pet_dog','🐶 還沒分類・有狗的'],['pet_cat','🐱 還沒分類・有貓的'],['pet_face','👤 還沒分類・有人臉的'],['pet_noface','🏞 還沒分類・沒有人臉的']].concat(SCF.map(([k,n])=>['pet_s_'+k,'🔎 還沒分類・'+n])).concat(String(VC.f||'').startsWith('pet_s_')&&!SCF.some(x=>'pet_s_'+x[0]===VC.f)?[[VC.f,'🔎 還沒分類・'+(VC.fsn||'電腦猜的內容')]]:[]).concat([['all','全部影片'],['wait','分好還沒搬'],['chk','🧐 可能分錯的（分好還沒搬）'],['done','已經搬過']]).concat(VI.cats.map(c=>['c'+c.id,'只看「'+c.name+'」']));
  $('#vcfl').innerHTML=o.map(([k,n])=>`<option value="${k}" ${VC.f===k?'selected':''}>${esc(n)}</option>`).join('')}
function vcBtns(){const el=$('#vcb');if(!el)return;if(LP&&!LP.done&&LP.drag){clearTimeout(LP.t);LP=null}const cur=(VI.it||{}).cat,hn=(VI.it&&VI.it.hint)||null;const top=(VC.side||'right')==='top';
  // 右邊一欄：從最上面排到最下面、平均撐滿；放不下就自動變 2、3 欄（格子變多）
  const nItem=VI.cats.length+2,H=el.clientHeight||400;let cols=7;if(!top){cols=1;while(cols<3&&Math.ceil(nItem/cols)*50>H)cols++}
  el.style.cssText=top?'display:grid;gap:4px;grid-template-columns:repeat(7,1fr)':`flex:1;min-height:0;display:grid;gap:4px;grid-template-columns:repeat(${cols},1fr);grid-auto-rows:minmax(44px,1fr);align-content:stretch;overflow:auto`;
  const sm=!top&&cols>1;
  el.oncontextmenu=e=>e.preventDefault();el.onpointerdown=vcLpDown;
  el.innerHTML=VI.cats.map((c,i)=>`<button data-c="${i}" title="${esc(c.name)}：${(c.n||0).toLocaleString()} 部${c.wait?`，還沒搬 ${c.wait.toLocaleString()}`:''}${c.auto?`（其中 ${c.auto.toLocaleString()} 個是自動標的一模一樣副本）`:''}" style="touch-action:none;-webkit-touch-callout:none;user-select:none;-webkit-user-select:none;transition:transform .12s;border:1px solid ${c.color};border-left:5px solid ${c.color};border-radius:8px;padding:${sm?'3px 2px':'6px 3px'};min-height:44px;line-height:1.15;font-weight:800;font-size:${sm?11.5:12.5}px;overflow:hidden;
    background:${cur===c.id?c.color:'var(--btn)'};color:${cur===c.id?'#fff':'var(--strong)'};${hn&&hn[0]===c.id&&cur!==c.id?`box-shadow:0 0 0 2px ${c.color},0 0 12px ${c.color};position:relative`:''}">${hn&&hn[0]===c.id&&cur!==c.id?`<span title="${hn[3]==='time'?'前後 3 小時拍的':hn[3]==='rule'?`你的規則「${esc(hn[4]||'')}」→ 這類`:hn[3]==='word'?(String(hn[4]||'').startsWith('📷')?`同一台相機「${esc(String(hn[4]).slice(2))}」拍的`:String(hn[4]||'').startsWith('🔤')?`檔名開頭「${esc(String(hn[4]).slice(2))}」的`:String(hn[4]||'').startsWith('📍')?`同一個地方拍的`:`資料夾名有「${esc(hn[4]||'')}」的`):'同資料夾'}${hn[3]==='rule'?'':` ${hn[1]}／${hn[2]} 部分到這類`}" style="position:absolute;right:3px;top:2px;font-size:11px">💡</span>`:''}${i<10?`<span style="opacity:.6;font-size:10px">${(i+1)%10}</span> `:i<20?`<span style="opacity:.6;font-size:10px" title="Shift＋${(i-9)%10}">⇧${(i-9)%10}</span> `:''}${esc(c.name)}<br><span style="font-weight:400;font-size:${sm?9.5:10.5}px;opacity:.85;white-space:nowrap">${sm?`${c.n}・${gbI(c.b).replace(' GB','G')}${c.wait?'・待'+c.wait:''}`:`${c.n} 部・${gbI(c.b)}${c.wait?'<br>待搬 '+c.wait:''}`}</span></button>`).join('')
   +`<button data-a="add" style="border:1px dashed var(--line2);border-radius:8px;background:var(--btn);min-height:44px;font-size:12px">＋ 新增</button><button data-a="mgr" style="border:1px solid var(--line2);border-radius:8px;background:var(--btn);min-height:44px;font-size:12px">⚙ 管理</button>`;
  if(hn&&cur!==hn[0]&&VI.it&&VI.hintFl!==VI.it.id){VI.hintFl=VI.it.id;const k=VI.cats.findIndex(c=>c.id===hn[0]),b=k>=0&&el.querySelector(`[data-c="${k}"]`);   // 💡 建議的分類整格亮一下再慢慢變暗（V0.2.63）
    if(b&&b.animate){const col=VI.cats[k].color,cs=getComputedStyle(b),bg0=cs.backgroundColor,fg0=cs.color;b.animate([{backgroundColor:col,color:'#fff',filter:'brightness(1.35)'},{backgroundColor:col,color:'#fff',filter:'brightness(1)',offset:.25},{backgroundColor:bg0,color:fg0,filter:'brightness(1)'}],{duration:2000,easing:'ease-out'})}}}
function vcPend(){const el=$('#vcpd');if(!el)return;const M=VI.mv||{},W=VI.cats.filter(c=>c.wait);
  el.innerHTML=M.run?`<span style="color:var(--blue)">${M.what==='clean'?'🧹 處理中':'🚚 搬檔中'} ${M.n||0}／${M.total||0}</span>`:W.length?'待搬：'+W.map(c=>`<b data-pc="${c.id}" title="點一下：只看分到「${esc(c.name)}」還沒搬的，搬之前檢查一遍" style="color:${c.color};cursor:pointer;text-decoration:underline dotted">${esc(c.name)} ${c.wait}${c.auto?`<small style="font-weight:400" title="其中自動標的一模一樣副本">（副本 ${c.auto}）</small>`:''}</b>`).join(' ')+(String(VC.f).startsWith('c')?` <b data-pc="0" style="cursor:pointer;color:var(--blue)">↩ 回還沒分類的</b>`:''):(M.msg?'✔ '+esc(M.msg):'按分類先記下來，一個段落後按 🚚 搬。左右滑換一部');
  const b=$('#vcmv');if(b){b.disabled=!W.length||M.run;b.style.opacity=b.disabled?.45:1;b.textContent='🚚 搬'+(W.length?' '+W.reduce((s,c)=>s+c.wait,0):'')}}
async function vcChk0(){const el=$('#vcchk0');if(!el)return;let j;try{j=await api('/api/vc_sus?d=1')}catch(e){return}if(!$('#vcchk0'))return;   // V0.5.76 可能分錯的：算到的跟清單對不起來時說清楚在哪
  if(!j||!j.ok){el.textContent='';return}const k=VC.kind==='photo'?'photo':'video',o=k==='photo'?'video':'photo',no=k==='photo'?j.nv:j.np,nm={video:'影片',photo:'照片'};
  el.innerHTML=`🧐 可能分錯的一共 ${(j.n||0).toLocaleString()} 部：影片 ${(j.nv||0).toLocaleString()}、照片 ${(j.np||0).toLocaleString()}${j.nx?`、其他 ${j.nx}（檔案不見了或已搬走）`:''}`+
   (no?`<br><button class="pill acc" style="margin-top:8px" onclick="VC.kind='${o}';LS.set('vc',VC);VI.ids=[];rVc()">👀 改看${nm[o]}的 ${no.toLocaleString()} 部</button>`:'')+(VC.ln?`<br><button class="pill" style="margin-top:8px" onclick="VC.ln='';LS.set('vc',VC);VI.ids=[];rVc()">⏱ 現在只看某種長度大小：改成全部</button>`:'')}
async function vcList(){const G0=$('#vcg'),t0=Date.now();let tk=null;if(G0&&!(VI.ids&&VI.ids.length)){const upd=()=>{const g=$('#vcg');if(g&&!(VI.ids&&VI.ids.length))g.innerHTML=`<div style="color:#aaa;padding:30px;text-align:center">讀取影片清單中…（${Math.round((Date.now()-t0)/1000)} 秒）<br><span style="font-size:12px">四萬多部、第一次可能要等一下；超過 1 分鐘請看「工具 → 📜 LOG」</span></div>`};upd();tk=setInterval(upd,1000)}
  let j;try{j=await api(U('/api/vc_list',{f:VC.f,order:VC.order,folder:VC.folder,rf:VC.rf===false?0:1,ln:VC.ln||'',k:VC.kind||'video',g:VC.g||'',q:VC.q||''}))}catch(e){j={ok:false,message:'連不到電腦：'+e}}finally{if(tk)clearInterval(tk)}
  if(!j.ok){const g=$('#vcg');if(g)g.innerHTML=`<div style="color:#f88;padding:30px;text-align:center">⚠ 讀不到影片清單：${esc(j.message||'電腦沒有回應')}<br><br><button class="pill" onclick="vcList()">再試一次</button></div>`;return}const keep=VI.it&&VI.it.id;VI.ids=j.ids||[];VI.gn=j.gn||[];VI.gi=j.gi||[];VI.gp=j.gp||[];VI.dn=j.dn||[];VI.di=j.di||[];VI.durs=j.dur||[];VI.sizes=j.size||[];VI.st=j.st||[];VI.tags=j.tags||{};VI.pets=new Set(j.pets||[]);VI.dark=new Set(j.dark||[]);VI.sus=new Set(j.sus||[]);VI.sug={};vcSug();vcPetChips();SW=[0,0];VI.cache={};VI.undo=(VI.undo||[]).slice(-500);if(j.live&&!VI.liveTold){VI.liveTold=1;toast(`📱 跳過 ${j.live.toLocaleString()} 部動態照片的短影片（設定 → 影片分類可以改）`,4000)}
  VI.i=Math.max(0,VI.ids.indexOf(VI.jumpTo&&VI.ids.includes(VI.jumpTo)?VI.jumpTo:keep));VI.jumpTo=0;if(!VI.ids.length){VI.it=null;VI.g=null;$('#vcpos').textContent='0／0';$('#vcinf').textContent='';
    $('#vcs').innerHTML='';if(VC.big){const g_=$('#vcg');g_.style.flex='1';g_.style.height='auto'}$('#vcg').innerHTML=`<div class="mu" style="color:#aaa;padding:30px;text-align:center">這裡沒有影片${VC.f==='todo'&&VI.cats.length?'（全部分好了 🎉）':''}${!VI.cats.length?'<br><br>先按「＋ 新增」建立分類（例如 工作、家庭、寵物）':''}
      ${VC.q?`<br><br>現在只找有「${esc(VC.q)}」的<br><button class="pill acc" data-a="qx" style="margin-top:8px">🔍 ✕ 不找了</button>`:''}      ${VC.folder?`<br><br>現在只看「${esc(String(VC.folder).split(/[\\/]/).filter(Boolean).pop())}」這個資料夾<br><button class="pill acc" data-a="exitdir" style="margin-top:8px">📁 ✕ 退出資料夾，看全部影片</button>`:''}
      ${VC.f==='chk'?(setTimeout(vcChk0,30),`<div id="vcchk0" style="margin-top:12px">🧐 正在算可能分錯的…</div>`):''}
      ${String(VC.f).startsWith('pet')?`<br><br>🐾 電腦看過的內容裡沒有這種的（或還沒讓電腦看過）<br><button class="pill acc" data-a="petgo" style="margin-top:8px">🐾 讓電腦看內容</button>`:''}
      ${VC.f!=='todo'?`<br><button class="pill" data-a="tofilter" style="margin-top:8px">改看「還沒分類的」</button>`:''}</div>`;vcBtns();if(VI.pq)vcPQBar();return}vcGo(VI.i);if(VI.pq)setTimeout(vcPQPage,60)}
function vcAhead(i,n){const o=[];for(let k=i+1;k<VI.ids.length&&o.length<n;k++)if(!VI.tags[VI.ids[k]])o.push(VI.ids[k]);return o}   // 接下來還沒分的幾部（先做好、先讀）（V0.2.87）
async function vcFetch(id,ahead){if(VI.cache[id])return VI.cache[id];const i=VI.ids.indexOf(id);const nx=vcAhead(i,3).join(',');
  if(!ahead&&VI.curAC&&VI.curAC.id!==id&&!VI.curAC.done){try{VI.curAC.ac.abort()}catch(_){}delete VI.cache[VI.curAC.id]}   // 已經換下一部了：上一部還在讀就不等了，連線讓出來（V0.3.54）
  const ac=!ahead&&typeof AbortController!=='undefined'?new AbortController():null;if(ac)VI.curAC={id,ac,done:false};
  const p=api(U('/api/vc_item',ahead?{id,next:nx,nb:1}:{id,next:nx}),undefined,false,ac?ac.signal:undefined).catch(e=>{if(e&&e.name==='AbortError'){delete VI.cache[id];return {ok:false,aborted:true}}throw e}).then(j=>{if(ac&&VI.curAC&&VI.curAC.ac===ac)VI.curAC.done=true;if(j.ok&&j.grid&&j.grid.ok)for(let s=0;s<j.grid.ns;s++){const im=new Image();im.src=`/api/vc_img?id=${id}&s=${s}`}else if(ahead&&VI.cache[id]===p)delete VI.cache[id];return j});VI.cache[id]=p;   // 先讀的那幾部還沒有 16 格：不留，輪到它再正式讀（V0.3.48）
  const ks=Object.keys(VI.cache);if(ks.length>14)delete VI.cache[ks[0]];return p}
async function vcGo(i){if(!VI.ids.length)return;i=Math.max(0,Math.min(VI.ids.length-1,i));VI.i=i;const id=VI.ids[i];const nr=(VI.st||[]).filter(x=>x===0).length;const left=VI.ids.length>60000?0:VI.ids.reduce((s,x)=>s+(VI.tags[x]?0:1),0);$('#vcpos').innerHTML=`${(i+1).toLocaleString()}／${VI.ids.length.toLocaleString()}`+(left&&left<VI.ids.length?` <span class="mu" style="font-weight:400" title="這份清單還沒分的">剩 ${left.toLocaleString()}</span>`:'')+(VI.st&&nr<VI.ids.length?` <span class="mu" style="font-weight:400" title="有 16 格的">⚡${nr.toLocaleString()}</span>`:'')+(VI.dn&&VI.dn.length>1?(()=>{const d=VI.di[i];let k=i+1;while(k<VI.ids.length&&VI.di[k]===d)k++;return ` <span data-a="nextdir" style="cursor:pointer;color:var(--accent);font-weight:400" title="這個資料夾還剩 ${k-i-1} 部；按了跳到下一個資料夾">⏭${k-i-1?'<small>'+(k-i-1)+'</small>':''}</span>`})():'')+(VI.sp&&VI.sp.today?` <span data-a="speed" style="color:var(--green);font-weight:400;cursor:pointer" title="今天分了幾部（點看速度）">✔今天${VI.sp.today}</span>`:'');vcStrip();
  const j=await vcFetch(id);if(VI.ids[VI.i]!==id)return;if(!j.ok){$('#vcinf').textContent=j.message||'';VI.it=null;VI.g=null;vcDraw();return}
  VI.it=j.item;VI.g=j.grid;const it=j.item,c=VI.cats.find(x=>x.id===it.cat);
  $('#vcinf').innerHTML=`<button class="pill ${it.fav?'acc':''}" data-a="fav" style="padding:0 7px;font-size:12px;margin-right:4px" title="⭐ 最愛：重複、相似時優先保留">${it.fav?'⭐':'☆'}</button>`+(VC.kind==='photo'?'':`<button class="pill" data-a="play" style="padding:0 8px;font-size:12px;margin-right:4px" title="在手機上播這部">▶ 播</button>`)+(c?`<b style="color:${c.color}">■ ${esc(c.name)}${it.moved?'（已搬）':''}</b> `:'')+`<b style="color:var(--strong)">${esc(it.name)}</b> ${VC.kind==='photo'?(it.w?it.w+'×'+it.h:''):fmtT(it.dur)}・${fmtB(it.size)}${(()=>{const m=Math.min(it.w||0,it.h||0);return m?'・'+(m>=2100?'4K':m>=1440?'2K':m>=1080?'1080p':m>=720?'720p':m+'p'):''})()}・${day(it.taken).slice(0,10)}`+(it.model?'・'+esc(it.model):'')+(()=>{const h=it.hint;if(!h||it.cat)return '';const c=VI.cats.find(x=>x.id===h[0]);if(!c)return '';const why=h[3]==='rule'?`規則「${esc(h[4]||'')}」`:h[3]==='mix'?`🧮 綜合：${esc(h[4]||'')}，把握 ${h[2]}%`:h[3]==='time'?'同一段時間':h[3]==='word'?(String(h[4]||'').startsWith('📷')?'同相機':String(h[4]||'').startsWith('🔤')?'同檔名開頭':String(h[4]||'').startsWith('📍')?'同一個地方':/^(🐾|🔎)/.test(String(h[4]||''))?'電腦看到「'+esc(String(h[4]).slice(2))+'」':`「${esc(h[4]||'')}」`):'同資料夾';return ` <span data-a="acc" title="按 A 或點這裡＝分到 ${esc(c.name)}" style="cursor:pointer;color:${c.color};font-weight:700">💡 ${esc(c.name)}<small style="font-weight:400;opacity:.8">（${why}${h[1]&&h[3]!=='mix'?` ${h[1]}／${h[2]}`:''}）</small></span>`})()+(it.pet&&Math.max(it.pet[0],it.pet[1])>=0.15?`<span title="電腦看到的機率（🐾 找貓狗）">・${it.pet[0]>=it.pet[1]?'🐶 '+Math.round(it.pet[0]*100):'🐱 '+Math.round(it.pet[1]*100)}%</span>`:'')+(it.faces?`<span title="電腦看到幾張人臉（👤）">・👤 ${it.faces}</span>`:'')+(it.sus?`<span style="color:#f5a623" title="可能分錯了：看一下，分錯就按數字改；沒錯就按「沒錯」">・🧐 ${esc(it.sus)} ${(()=>{const c=VI.cats.find(x=>x.id===it.sus_c);return c?`<span data-a="susfix" title="或按 A" style="cursor:pointer;text-decoration:underline;color:${c.color}">改成「${esc(c.name)}」（A）</span> ／ `:''})()}<span data-a="susok" style="cursor:pointer;text-decoration:underline">沒錯</span></span>`:'')+(it.scene?`<span data-a="scf" data-sk="${esc(it.scene_k||'')}" data-sn="${esc(it.scene)}" title="電腦猜的內容（🔎，會看錯）：點一下只看還沒分類、也是這種內容的" style="cursor:pointer;text-decoration:underline dotted">・${esc(it.scene.split('／')[0])}</span>`:'')+` <span data-a="infold" data-d="${esc(dir(it.path))}" title="點一下：只看這個資料夾" style="opacity:.75;text-decoration:underline dotted;cursor:pointer">📁 ${esc(dir(it.path))}</span>`;
  vcDraw();vcBtns();vcGb();for(const n of vcAhead(i,2))vcFetch(n,true)}
function vcDraw(){const G=$('#vcg');if(!G)return;const g=VI.g,it=VI.it;
  if(g&&g.ok&&g.photo&&it){G.innerHTML=`<img data-zp="${it.id}" src="/api/fc_thumb?id=${it.id}&w=1600" style="position:absolute;inset:0;width:100%;height:100%;object-fit:contain;cursor:zoom-in" draggable="false">`;
    const im=G.firstChild;im.onclick=e=>{e.stopPropagation();zoomImg(it.id,'photo')};for(const n of VI.ids.slice(VI.i+1,VI.i+3)){const p=new Image();p.src=`/api/fc_thumb?id=${n}&w=1600`}return}
  if(!g||!g.ok){G.innerHTML=`<div style="color:#aaa;padding:30px;text-align:center">${esc((g&&g.message)||'載入中…')}</div>`;if(g&&g.pending)setTimeout(()=>{if(VI.it&&VI.it.id===it.id){delete VI.cache[it.id];vcGo(VI.i)}},1200);return}
  const W=G.clientWidth-2,H=G.clientHeight-2,C=g.cells||[];const [k,cols,rows,cw,ch]=bestGrid(C.length,W,H,g.ar||16/9);const ox=(W-cols*cw)/2,oy=(H-rows*ch)/2;
  const bp=(c,n)=>n>1?c/(n-1)*100:0;
  G.innerHTML=C.slice(0,k).map((c,i)=>`<div data-z="${i}" style="position:absolute;left:${ox+(i%cols)*cw+1}px;top:${oy+Math.floor(i/cols)*ch+1}px;width:${cw-2}px;height:${ch-2}px;
    background:#111 url('/api/vc_img?id=${it.id}&s=${c.s}') no-repeat;background-size:${g.cols*100}% ${g.rows*100}%;background-position:${bp(c.c,g.cols)}% ${bp(c.r,g.rows)}%;border-radius:2px${it.pc&&it.pc===c.s+','+c.c+','+c.r?';box-shadow:inset 0 0 0 3px #f5a623':''}">
    <span style="position:absolute;left:0;bottom:0;background:#0009;color:#fff;font-size:10px;padding:0 4px">${fmtT(c.t)}</span>${it.pc&&it.pc===c.s+','+c.c+','+c.r?'<span title="電腦在這一格看到貓狗" style="position:absolute;right:2px;top:1px;font-size:14px">🐾</span>':''}</div>`).join('')}
function vcClick(e){const z=e.target.closest('[data-z]');if(z){const c=VI.g.cells[+z.dataset.z],g=VI.g,Z=$('#vcz');const bp=(x,n)=>n>1?x/(n-1)*100:0;
    const w=Math.min(innerWidth*.96,innerHeight*.8*(g.ar||1.78));vczShow('grid');Z.innerHTML=`<div style="width:${w}px;aspect-ratio:${g.ar||1.78};background:url('/api/vc_img?id=${VI.it.id}&s=${c.s}') no-repeat;background-size:${g.cols*100}% ${g.rows*100}%;background-position:${bp(c.c,g.cols)}% ${bp(c.r,g.rows)}%"></div><div style="color:#fff;position:absolute;bottom:20px;display:flex;gap:10px;align-items:center">${fmtT(c.t)}<button class="pill acc" data-from="${c.t}">▶ 從這裡播</button><span class="mu">點旁邊關掉</span></div>`;
    Z.querySelector('[data-from]').onclick=ev=>{ev.stopPropagation();const t=+ev.currentTarget.dataset.from;vczHide();ZSTART=t;const id=VI.it.id;setTimeout(()=>zoomImg(id,'video'),400)};return}
  if(e.target.closest('#vcz')){vczHide();return}
  const pc=e.target.closest('[data-pc]');if(pc){const id=+pc.dataset.pc,c=VI.cats.find(x=>x.id===id);VC.f=id?'c'+id:'todo';LS.set('vc',VC);VI.ids=[];if(VI.msel)vcMselOff();toast(id?`🔎 只看分到「${c?c.name:''}」的：搬之前檢查一遍，分錯的直接按別的分類改（按「↩ 回還沒分類的」回去）`:'↩ 回到還沒分類的',3500);return rVc()}
  const gh=e.target.closest('[data-gh]');if(gh){const [a,z]=vcGrpR(+gh.dataset.gh);return vcSelRange(a,z,'整組 ')}
  const sj=e.target.closest('[data-j]');if(sj){if(VI.lpDone){VI.lpDone=0;return}if(VI.msel){const j=+sj.dataset.j,id=VI.ids[j],S=$('#vcs'),st=S?S.scrollTop:0;
    if(e.shiftKey&&VI.lastSel!=null){const a=Math.min(VI.lastSel,j),z=Math.max(VI.lastSel,j);for(let k=a;k<=z;k++)vcSel(VI.ids[k],true);vcStrip()}else{vcSel(id,!VI.sel.has(id));sj.outerHTML=vcStripItem(j,1)}
    VI.lastSel=j;if(S)S.scrollTop=st;const P=$('#vcpos');if(P)P.dataset.sel=VI.sel.size;toast(VI.sel.size?`☑ 選了 ${VI.sel.size} 部，按右邊的分類一次套用`:'☑ 都沒選（Esc 或 ☑ 結束勾選）',1500);return}return vcGo(+sj.dataset.j)}
  const b=e.target.closest('[data-c],[data-a]');if(!b)return;if(b.dataset.c!==undefined){if(LP&&LP.done){LP=null;return}return vcTag(+b.dataset.c)}const a=b.dataset.a;
  if(a==='exit'){document.onkeydown=null;onresize=null;return history.state&&history.state.t==='vc'&&history.length>1?history.back():go('home')}
  if(a==='rf'){VC.rf=VC.rf===false;LS.set('vc',VC);toast(VC.rf?'⚡ 做好的先：有畫面的排前面，沒畫面的跳到後面（背景繼續做）':'照原本的順序（沒做好的也會出現）',3500);return rVc()}
  if(a==='side'){VC.side={right:'left',left:'top',top:'right'}[VC.side||'right'];LS.set('vc',VC);toast({right:'按鈕在右邊',left:'按鈕在左邊',top:'按鈕在上面'}[VC.side]);const k=VI.it&&VI.it.id;return rVc().then(()=>{})}
  if(a==='prev')return vcGo(VI.i-1);if(a==='next')return vcGo(VI.i+1);if(a==='undo')return vcUndo();if(a==='hist')return vcHist();
  if(a==='add'){const n=prompt('新的分類名稱（例如 工作、家庭、寵物）');if(!n)return;api('/api/vc_cat',{a:'add',name:n}).then(r=>{toast(r.message);vcReCats()});return}
  if(a==='mgr')return vcMgr();
  if(a==='views')return vcViews();
  if(a==='big'){VC.big=!VC.big;LS.set('vc',VC);toast(VC.big?'🔲 縮圖牆：滑鼠滑過去翻 16 格、雙擊放大看、數字鍵分類（藍框那部）；再按 🔲 或 V 回去':'回到一般畫面',3500);return rVc()}
  if(a==='acc'){const h=VI.it&&VI.it.hint;if(!h)return;const ci=VI.cats.findIndex(c=>c.id===h[0]);if(ci>=0)return vcTag(ci);return}
  if(a==='petgo'){api('/api/vc_pet',{a:'start',k:VC.kind||'video'}).then(r=>toast((r.message||'')+'（看完會自動補上記號）',4000));VC.f='todo';LS.set('vc',VC);VI.ids=[];return rVc()}   // V0.4.49
  if(a==='darkf'){VC.f='pet_s_junk';VC.fsn='🌑 全黑／沒東西／沒動';LS.set('vc',VC);VI.ids=[];toast('🌑 只看還沒分類、全黑／沒東西／沒動的（多半是誤錄）：確認後 Ctrl＋A 整組分到 Delete',3500);return rVc()}   // V0.3.92
  if(a==='petq')return vcPQ(true);
  if(a==='petf'){VC.f='pet';VC.order='pet';VC.g='';LS.set('vc',VC);VI.ids=[];toast('🐾 只看還沒分類、有貓或狗的，最像的排前面（按 V 用縮圖牆一次看很多；Ctrl＋A 整組勾 → 按 Family）',3500);return rVc()}
  if(a==='q'){const t=prompt('🔍 找檔名或資料夾名裡有這些字的影片（空白分開＝都要有，例如：日本 2019）\n也可以：日期:2019-10（那個月拍的）、相機:DJI、檔名:LINE_、內容:有狗（內容:有貓／有人／很暗／食物…＝電腦看到的）\n留空＝不找',VC.q||'');if(t===null)return;VC.q=t.trim();LS.set('vc',VC);VI.ids=[];if(VC.q)toast('🔍 找：'+VC.q);return rVc()}
  if(a==='qx'){VC.q='';LS.set('vc',VC);VI.ids=[];toast('🔍 不找了，回到全部');return rVc()}
  if(a==='exitdir'){VC.folder='';LS.set('vc',VC);VI.ids=[];toast('📁 退出資料夾，回到全部影片');return rVc()}
  if(a==='tofilter'){VC.f='todo';LS.set('vc',VC);VI.ids=[];return rVc()}
  if(a==='folder')return vcFolder();
  if(a==='many')return vcMany();
  if(a==='msel'){if(VI.msel){toast('取消勾選',1500);return vcMselOff()}VI.msel=true;VI.sel=new Set();VI.lastSel=null;vcSel(0,false);toast('☑ 勾選：點下面的小格子勾好幾部（也可以直接長按／右鍵某一格開始），再按右邊的分類',3000);return vcStrip()}
  if(a==='play')return VI.it&&zoomImg(VI.it.id,'video');
  if(a==='fav'){const it=VI.it;if(!it)return;const on=!it.fav;api('/api/fav',{id:it.id,on}).then(r=>{if(r.ok){it.fav=on?1:0;b.classList.toggle('acc',on);b.textContent=on?'⭐':'☆';toast(r.message)}});return}
  if(a==='susfix'){const ci=VI.cats.findIndex(x=>VI.it&&x.id===VI.it.sus_c);if(ci>=0){VI.it.sus='';return vcTag(ci)}return}   // V0.4.37
  if(a==='susok'){const id=VI.ids[VI.i];api('/api/vc_sus',{ok:id}).then(r=>toast(r.message||'',1500));if(VI.it)VI.it.sus='';delete VI.cache[id];if(VC.f==='chk'&&VI.i<VI.ids.length-1)return vcGo(VI.i+1);return vcGo(VI.i)}   // V0.4.35
  if(a==='scf'&&b.dataset.sk){if(VC.f==='pet_s_'+b.dataset.sk){VC.f='todo';toast('回到「還沒分類的」',1500)}else{VC.f='pet_s_'+b.dataset.sk;VC.fsn=b.dataset.sn;toast('🔎 只看還沒分類、電腦猜是「'+b.dataset.sn+'」的（再點一次回去）',3000)}LS.set('vc',VC);VI.ids=[];return rVc()}   // V0.3.76
  if(a==='infold'){const d=b.dataset.d;if(VC.folder===d){VC.folder='';toast('📁 看全部資料夾')}else{VC.folder=d;toast('📁 只看：'+d,3000)}LS.set('vc',VC);return rVc()}
  if(a==='grp')return vcGrpMenu();
  if(a==='gpet'){const [s,e]=vcGrpRange(VI.i),L=VI.ids.slice(s,e+1).filter(x=>VI.pets.has(x)&&!VI.tags[x]);VI.msel=true;VI.sel=new Set(L);vcSel(0,false);vcStrip();return toast(`☑ 勾了這組 ${L.length} 部有貓狗的：看一下、取消不對的，再按分類（例如 Family）`,3500)}   // V0.4.30
  if(a==='ghint')return (async()=>{const [s,e]=vcGrpRange(VI.i),ids=VI.ids.slice(s,e+1).filter(x=>!VI.tags[x]);const d=await api('/api/vc_tag_many',{ids,hint:1,dry:1});if(!d.ok)return toast(d.message||'失敗');if(!d.n)return toast('這組沒有可以照建議分的（要先分好一些，才知道你的習慣）',3000);vcHintPick(d,`這組還沒分的 ${ids.length.toLocaleString()} 部`)})()
  if(a==='gview'){VI.fromOv=0;return vcGrpView()}
  if(a==='gnext')return vcGrpNext();
  if(a==='gkeep'||a==='pkeep'){const p=a==='gkeep'?VI.gp[VI.gi[VI.i]]:(VI.it&&VI.it.pack&&VI.it.pack.path);if(!p)return;return pkKeep(p,0,null,'',async r=>{if(r&&r.ok){await vcReCats();vcList()}})}
  if(a==='pview'){const p=VI.it&&VI.it.pack&&VI.it.pack.path;if(p)return pkView(p)}
  if(a==='nextdir'){const d=VI.di[VI.i];let k=VI.i+1;while(k<VI.ids.length&&VI.di[k]===d)k++;if(k>=VI.ids.length)return toast('已經是最後一個資料夾了');const n=k-VI.i-1;toast(`⏭ 跳過這個資料夾剩下的 ${n} 部 → ${VI.dn[VI.di[k]].split(/[\\/]/).pop()}`,2500);return vcGo(k)}
  if(a==='speed'){const p=VI.sp||{},left=VI.ids.length-VI.i;return toast(`🎞 今天分了 ${p.today||0} 部、這 7 天 ${p.week||0} 部`+(p.per?`・平均 ${p.per} 秒一部，這份清單還有 ${left.toLocaleString()} 部 ≈ ${fmtT(left*p.per)}`:'')+((p.bycat||[]).length?'\n今天：'+p.bycat.map(([n,c])=>`${n} ${c.toLocaleString()}`).join('、'):''),7000)}
  if(a==='kind'){VC.kind=VC.kind==='photo'?'video':'photo';VC.folder='';VC.ln='';LS.set('vc',VC);toast(VC.kind==='photo'?'📷 照片快速分類：一張一張看大圖，按右邊分類（分類跟影片共用）':'🎞 影片快速分類',3000);return rVc()}
  if(a==='move'||a==='clean')return vcRun(a)}
// ---- 🚀 整理精靈（V0.2.39）：建議順序、每一步還剩多少、一鍵去做
let WZB=0;
async function rWiz(again){const j=await api('/api/wiz');if(!j.ok)return;if(again&&!j.busy&&!WZB)return;WZB=j.busy;
  const AB={bad:['📦 全部先隔離','er'],dpl_all:['⚡ 整包複本照建議','acc'],dup_all:['⚡ 全部照建議','acc'],vc_group:['🧩 開始一組一組審','acc'],vc_sug:['💡 只看有建議的','acc'],pet_start:['🐾 開始看','acc'],pet_view:['🐾 只看有貓狗的','acc'],junk_view:['🌑 只看誤錄的','acc'],move:['🚚 搬','acc']};
  $('#v').innerHTML=`<div class="panel"><h3 style="margin:0">🚀 整理精靈</h3><div class="mu" style="margin-top:4px">照這個順序做最快：先清掉壞的、整包重複的，再整包處理你整理過的資料夾，最後才一組一組審。每一步都只搬到同一顆硬碟的隔離區或分類資料夾、可以復原。${j.busy?'<br><b style="color:var(--blue)">背景正在搬…（做完會自動更新）</b>':''}</div></div>
   ${j.steps.map((s,i)=>`<div class="panel" style="padding:10px 12px;${i===j.cur?'border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)':''};${s.done?'opacity:.62':''}"><div class="row" style="flex-wrap:nowrap;gap:10px;align-items:flex-start">
    <b style="flex:none;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;background:${s.done?'var(--green)':i===j.cur?'var(--accent)':'var(--track)'};color:${s.done||i===j.cur?'#fff':'var(--text)'}">${s.done?'✔':i+1}</b>
    <div class="grow" style="min-width:0"><b>${s.ic} ${esc(s.t)}</b>${s.b?` <span class="mu">${fmtB(s.b)}</span>`:''}<div class="mu" style="font-size:12.5px;margin-top:2px">${esc(s.d)}</div>
     <div class="row" style="gap:6px;margin-top:6px">${s.k==='dpl'&&s.n<0?'<button class="pill acc" data-wa="dpl_scan">🔍 先分析</button>':''}${s.act&&!s.done&&AB[s.act]?`<button class="pill ${AB[s.act][1]}" data-wa="${s.act}" ${j.busy&&s.act!=='vc_group'?'disabled':''}>${AB[s.act][0]}</button>`:''}<button class="pill" data-go="${s.go}">去看 ›</button></div></div></div></div>`).join('')}`;
  $('#v').onclick=async e=>{const g=e.target.closest('[data-go]');if(g)return go(g.dataset.go);const b=e.target.closest('[data-wa]');if(!b)return;const a=b.dataset.wa;
    if(a==='vc_group'){VC.g='pack';VC.f='todo_np';VC.folder='';LS.set('vc',VC);return go('vc')}
    if(a==='pet_start'){const r=await api('/api/vc_pet',{a:'start',k:'video'});toast(r.message||'',3000);return setTimeout(()=>{if(CUR==='tool:wiz')rWiz()},800)}
    if(a==='pet_view')return go('vc:pet');
    if(a==='junk_view')return go('vc:pet_s_junk|🌑 全黑／沒東西／沒動');
    if(a==='vc_sug'){VC.f='todo_sug';VC.folder='';VC.q='';LS.set('vc',VC);toast('💡 按 A＝照建議分，不對的按數字改',3000);return go('vc')}
    const msg={bad:'損毀的（打不開、部分損毀、0 位元組）全部先搬到隔離區？（不是刪除，可以復原）',dpl_all:'「整包是複本」的資料夾對，全部保留 ⭐ 那邊、另一邊的複本搬到隔離區？（獨有的不動）',dup_all:'剩下的重複檔，每組留建議的那份（分類過、整理過的優先），其他搬到隔離區？',move:'分好的影片全部搬進分類資料夾？'}[a];
    if(msg&&!confirm(msg))return;if(a==='dpl_scan'){b.disabled=true;b.textContent='分析中…'}
    const r=await api('/api/wiz',{a});toast(r.message||'失敗',4000);WZB=1;rWiz()}}
// ---- 🧭 重複檔：用資料夾的角度看（V0.2.16）
let DPS=0,DPF=LS.get('dpf','all'),DPJ=null,DPT='';
const dplSt=S=>!S||!S.run&&!S.msg?'':S.run?`<span style="color:var(--blue)">🧭 處理中 ${(S.n||0).toLocaleString()}／${(S.total||0).toLocaleString()}${S.all?`（${S.done_pairs||0}／${S.all} 對）`:''}・已搬 ${(S.q||0).toLocaleString()} 個 ${fmtB(S.b||0)}</span> <button class="pill er" data-d="stop">⏹ 停止</button>`:'✔ '+esc(S.msg||'');
const dl2=p=>{const a=String(p).split(/[\\/]/).filter(Boolean);return a.slice(-2).join('\\')};
const dbar=(pc,col)=>`<div style="height:7px;border-radius:4px;background:var(--track);overflow:hidden;margin-top:3px"><div style="height:100%;width:${pc}%;background:${col}"></div></div>`;
async function rDpl(again,force){
  if(again){const s=await api(U('/api/dpl',{st:1}));const el=$('#dpst');if(!el||!s.ok)return;el.innerHTML=dplSt(s.st);if(DPS&&!s.st.run){DPS=0;toast('🧭 '+(s.st.msg||'好了'),6000);rDpl(false,1)}else if(s.st.run)DPS=1;return}
  if(!DPJ||force){$('#v').innerHTML='<div class="panel">🧭 分析中…（七萬多組要幾秒到一分鐘）</div>';DPJ=await api(U('/api/dpl',force===2?{force:1}:{}));}
  const j=DPJ;if(!j||!j.ok)return;const P=j.pairs||[],cp=P.filter(p=>p.rel==='copy'),ov=P.filter(p=>p.rel!=='copy'),cpb=cp.reduce((s,p)=>s+p.bytes,0),ovb=ov.reduce((s,p)=>s+p.bytes,0);
  const inT=p=>!DPT||[p.a,p.b].some(d=>d===DPT||d.startsWith(DPT+'\\')||d.startsWith(DPT+'/'));
  const L=(DPF==='copy'?cp:DPF==='overlap'?ov:P).filter(inT);
  $('#v').innerHTML=`<div class="panel"><h3>🧭 重複檔：用資料夾看</h3>
   <div style="margin:4px 0">${(j.groups||0).toLocaleString()} 組重複、多出來 <b>${(j.extra||0).toLocaleString()}</b> 份（<b>${fmtB(j.extra_b||0)}</b>）。其中大部分是「整包資料夾被複製」：找到 <b>${P.length}</b> 對。</div>
   <div class="mu" id="dpbest" style="line-height:1.6">最佳解（照順序做）：<br>① <b>整包是複本</b> ${cp.length} 對（${fmtB(cpb)}）：另一邊幾乎全部都有 → 保留建議那邊、複本搬隔離區，按 ⚡ 一次做完<br>② <b>部分重複</b> ${ov.length} 對（${fmtB(ovb)}）：兩邊各有獨有的 → 一對一對看，🔀 合併（獨有的搬過去、保留子資料夾）或只搬重複的<br>③ 剩下零散的：到「🔁 重複檔」按「⚡ 全部照建議」<br>④ 合併好的資料夾，再用「📦 資料夾包」整包分類</div>
   <div class="row" style="gap:5px;margin-top:8px"><button class="pill acc" data-d="all" ${cp.length?'':'disabled'}>⚡ ① 整包複本全部照建議（${cp.length} 對）</button><button class="pill" data-d="dup">🔁 ③ 零散的</button><button class="pill" data-d="re">🔄 重新分析</button><button class="pill" data-d="hist">↶ 最近做過的</button></div><div id="dphist"></div>
   <div id="dpst" style="margin-top:6px"></div><div class="mu" style="font-size:11.5px;margin-top:4px">只搬到同一顆硬碟的隔離區、不刪除；搬之前會再確認保留那邊真的有一模一樣的，不會把最後一份搬走。分析花 ${j.sec||0} 秒。</div></div>
   <div class="panel"><h3>最上層資料夾：多少在別的地方也有</h3>${(j.tops||[]).slice(0,25).map(t=>`<div class="it" style="padding:6px 0"><div class="row" style="flex-wrap:nowrap"><b class="grow" style="min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">📁 ${esc(dl2(t.path))}</b><span class="mu" style="white-space:nowrap">${fmtB(t.b)}・<b style="color:${t.pct>=80?'var(--orange)':'var(--text)'}">${t.pct}%</b> 別處也有</span></div>${dbar(t.pct,t.pct>=80?'var(--orange)':'var(--blue)')}<div class="mu" style="font-size:11.5px;margin-top:2px">大多在：${t.with.map(w=>esc(dl2(w.path))+' '+w.n.toLocaleString()).join('、')}</div>
     <div class="row" style="gap:4px;margin-top:4px"><button class="pill" data-dt="${esc(t.path)}" style="padding:2px 8px;font-size:12px">${DPT===t.path?'✔ 只看這個的資料夾對':'🔎 只看這個的資料夾對'}</button>${t.with.slice(0,2).map(w=>`<button class="pill" data-dtk="${esc(w.path)}" data-dto="${esc(t.path)}" style="padding:2px 8px;font-size:12px" title="「${esc(dl2(t.path))}」裡「${esc(dl2(w.path))}」也有的，搬到隔離區；只有這裡有的不動">留 ${esc(String(w.path).split(/[\\/]/).pop())} 的、這裡的複本搬走</button>`).join('')}</div></div>`).join('')||'<div class="mu">沒有</div>'}</div>
   <div class="panel"><div class="row" style="gap:4px"><b class="grow">資料夾對（大的先）${DPT?`<br><span class="mu" style="font-size:12px">只看：${esc(dl2(DPT))} <a href="#" data-dt="">（全部）</a></span>`:''}</b>${[['all','全部'],['copy','整包複本'],['overlap','部分重複']].map(([k,n])=>`<button class="pill ${DPF===k?'acc':''}" data-df="${k}">${n}</button>`).join('')}</div></div>
   ${L.slice(0,150).map((p,i)=>{const k=P.indexOf(p),A=[['a',p.a,p.na,p.ba,p.pa],['b',p.b,p.nb,p.bb,p.pb]];return `<div class="panel" style="padding:10px" data-di="${k}">
    <div class="row" style="flex-wrap:nowrap"><b class="grow">${p.rel==='copy'?'📋 整包複本':'🔀 部分重複'}</b><span class="mu">${p.n.toLocaleString()} 個一樣・${fmtB(p.bytes)}</span></div>
    ${A.map(([s,d,n,b,pc])=>`<div style="margin-top:6px;${p.keep===s?'border-left:3px solid var(--green);padding-left:6px':'padding-left:9px'}"><div class="row" style="flex-wrap:nowrap"><span class="grow" style="min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${p.keep===s?'⭐ ':''}${esc(dl2(d))}</span><span class="mu" style="white-space:nowrap;font-size:12px">${n.toLocaleString()} 個・${fmtB(b)}・${pc}% 另一邊也有</span></div>${dbar(pc,pc>=95?'var(--orange)':'var(--blue)')}<div class="mu" style="font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(d)}</div></div>`).join('')}
    <div style="margin:6px 0;font-size:12.5px">💡 ${esc(p.tip)}<br><span class="mu">原因：${esc(p.why)}</span></div>
    <div class="row" style="gap:5px">${p.same_drive?'':'<span class="mu" style="font-size:11.5px">兩邊在不同硬碟：只能「保留」，不能合併</span>'}<button class="pill" data-dpk="${p.keep}" title="看 ⭐ 這邊的縮圖；合併好之後也可以在這裡整包分類">👀 看 ⭐</button><button class="pill" data-dpk="${p.keep==='a'?'b':'a'}" title="看另一邊的縮圖">👀 看另一邊</button><span class="grow"></span><button class="pill ${p.keep==='a'&&p.rel==='copy'?'acc':''}" data-dk="a">保留上面</button><button class="pill ${p.keep==='b'&&p.rel==='copy'?'acc':''}" data-dk="b">保留下面</button>${p.same_drive?`<button class="pill ${p.rel!=='copy'?'acc':''}" data-dm="${p.keep}">🔀 合併到 ⭐</button><button class="pill" data-dm="${p.keep==='a'?'b':'a'}">合併到另一邊</button>`:''}</div></div>`}).join('')}
   ${L.length>150?`<div class="mu" style="text-align:center;margin:8px">只顯示前 150 對</div>`:''}`;
  rDpl(true);
  $('#v').onclick=async e=>{const f=e.target.closest('[data-df]');if(f){DPF=f.dataset.df;LS.set('dpf',DPF);return rDpl()}
    const du=e.target.closest('[data-du]');if(du){if(!confirm('復原這一筆？搬到隔離區的搬回原處；合併過去的搬回原本的資料夾。'))return;const r=await api('/api/dpl',{a:'undo',key:du.dataset.du});toast(r.message||'失敗',5000);du.closest('.it').remove();return}
    const dt=e.target.closest('[data-dt]');if(dt){e.preventDefault();DPT=DPT===dt.dataset.dt?'':dt.dataset.dt;return rDpl()}
    const tk=e.target.closest('[data-dtk]');if(tk){const kd=tk.dataset.dtk,od=tk.dataset.dto;const pl=await api(U('/api/dpl',{plan:1,keep:kd,other:od}));if(!pl.ok)return toast('預覽失敗');
      if(!confirm(`保留「${dl2(kd)}」那邊的？\n\n・「${dl2(od)}」裡 ${pl.dup.toLocaleString()} 個「${dl2(kd)}」也有一模一樣的 → 隔離區（${fmtB(pl.dup_b)}）\n・${pl.uniq.toLocaleString()} 個只有這裡有的不動\n\n可以在「📦 隔離區」依原因整批復原。`))return;
      const r=await api('/api/dpl',{a:'keep',keep:kd,other:od});toast(r.message||'失敗',5000);if(r.ok){DPS=1;rDpl(true)}return}
    const pkb=e.target.closest('[data-dpk]');if(pkb){const p=P[+pkb.closest('[data-di]').dataset.di];return pkView(pkb.dataset.dpk==='a'?p.a:p.b)}
    const d=e.target.closest('[data-d]');if(d){const a=d.dataset.d;if(a==='re')return rDpl(false,2);if(a==='dup')return go('tool:dup');
      if(a==='stop'){await api('/api/dpl',{a:'stop'});return toast('⏹ 停止中…')}
      if(a==='hist'){const h=await api(U('/api/dpl',{hist:1}));const el=$('#dphist');if(!el)return;el.innerHTML=(h.rows||[]).map(r=>`<div class="row it" style="flex-wrap:nowrap;font-size:12.5px"><span class="grow" style="min-width:0">${r.kind==='merge'?'🔀 合併到':'保留'} <b>${esc(dl2(r.keep))}</b> <span class="mu">${r.n.toLocaleString()} 個・${day(r.t)}</span></span><button class="pill" data-du="${esc(r.key)}" style="padding:2px 8px">↶ 復原</button></div>`).join('')||'<div class="mu">最近沒有做過</div>';return}
      if(a==='all'){if(!confirm(`① 「整包是複本」的 ${cp.length} 對，全部照建議：保留 ⭐ 那邊，另一邊的複本搬到隔離區（${fmtB(cpb)}）？\n\n獨有的不動；搬之前每個檔都會再確認保留那邊有一模一樣的。可以在「📦 隔離區 → 依原因：整包重複」整批復原。`))return;
        const r=await api('/api/dpl',{a:'all'});toast(r.message||'失敗',4000);DPS=1;return rDpl(true)}}
    const c=e.target.closest('[data-di]');if(!c)return;const p=P[+c.dataset.di],k=e.target.closest('[data-dk],[data-dm]');if(!k)return;
    const merge=!!k.dataset.dm,s=k.dataset.dk||k.dataset.dm,kd=s==='a'?p.a:p.b,od=s==='a'?p.b:p.a;
    const pl=await api(U('/api/dpl',{plan:1,keep:kd,other:od}));if(!pl.ok)return toast('預覽失敗');
    const msg=merge?`🔀 合併到「${dl2(kd)}」？\n\n・「${dl2(od)}」裡 ${pl.dup.toLocaleString()} 個一樣的 → 隔離區（${fmtB(pl.dup_b)}）\n・${pl.uniq.toLocaleString()} 個獨有的 → 搬到「${dl2(kd)}」（保留子資料夾）\n・搬空的「${dl2(od)}」會收掉`
      :`保留「${dl2(kd)}」？\n\n・「${dl2(od)}」裡 ${pl.dup.toLocaleString()} 個這邊也有的 → 隔離區（${fmtB(pl.dup_b)}）\n・${pl.uniq.toLocaleString()} 個獨有的不動`;
    if(!confirm(msg+(pl.nohash?`\n\n（${pl.nohash.toLocaleString()} 個還沒比對過內容，當成獨有的）`:'')+'\n\n可以在「📦 隔離區」依原因整批復原。'))return;
    const r=await api('/api/dpl',{a:merge?'merge':'keep',keep:kd,other:od});toast(r.message||'失敗',5000);if(r.ok){DPS=1;c.style.opacity=.45;rDpl(true)}}}
// ---- 🧩 相關的排一起（V0.2.14）：一組一組審
const GICON={'':'🧩',pack:'📦',type:'🎬',time:'📅',dir:'📁',sim:'👯',geo:'📍'};
const GMODES=[['','不分組','照上面選的排序，一部一部來'],['pack','📦 資料夾包','你以前整理過、有取名字的資料夾（例如 2020-日本旅遊）整包排在一起；其他照資料夾'],['type','🎬 同類型','檔名樣式＋手機＋直式／橫式＋解析度一樣的排一起（螢幕錄影、行車紀錄器、LINE…各成一組），大組先'],['time','📅 同一段時間','同一天、前後 4 小時內拍的排一起（同一個活動）'],['dir','📁 同資料夾','同一個資料夾的排一起'],['sim','👯 相似影片','同一部影片的不同版本（轉檔、壓縮、剪短）排在一起，一起看一起決定（要先在「🎬 相似影片」找過）'],['geo','📍 同一個地方','手機拍的影片、照片有 GPS 的，同一個地方（大約 5 公里內）排一起，組名寫大多在哪個資料夾；沒有位置的放最後'],['szsug','📏 大小區間＋同類先排','照大小分組（600～700MB、500～600MB…），每組裡電腦建議同一類的排在一起、再來是電腦看到同樣內容的；組名寫這組建議各幾部，組名旁「💡 照建議」可以整組一次分']];
function vcGrpRange(i){const g=VI.gi[i];let s=i,e=i;while(s>0&&VI.gi[s-1]===g)s--;while(e<VI.ids.length-1&&VI.gi[e+1]===g)e++;return [s,e,g]}
function vcGb(){const el=$('#vcgb');if(!el)return;const it=VI.it,B=(a,t,c,ti)=>`<button class="pill ${c||''}" data-a="${a}" title="${ti||''}" style="padding:2px 8px;font-size:12px;min-height:0;flex:none">${t}</button>`;
  if(VI.gn&&VI.gn.length&&VI.ids.length){const [s,e,g]=vcGrpRange(VI.i),n=e-s+1,todo=VI.ids.slice(s,e+1).filter(x=>!VI.tags[x]).length;
    el.style.display='flex';el.style.cssText+=';gap:5px;align-items:center;flex-wrap:nowrap;font-size:12px;background:var(--panel2,#1a2230);border-radius:8px;padding:3px 6px';
    el.innerHTML=`<span style="flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"><b>${esc(VI.gn[g]||'')}</b> <span class="mu">第 ${g+1}／${VI.gn.length} 組・${VI.i-s+1}／${n} 部${todo<n?`・待分 ${todo}`:''}${(()=>{const pn=VI.pets?VI.ids.slice(s,e+1).filter(x=>VI.pets.has(x)).length:0;return pn?`・🐾 ${pn}`:''})()}</span></span>`+((()=>{const pn=VI.pets?VI.ids.slice(s,e+1).filter(x=>VI.pets.has(x)&&!VI.tags[x]).length:0;return pn?B('gpet','🐾 勾 '+pn,'','這組還沒分、有貓狗的勾起來，再按分類一次分'):''})())+(todo?B('ghint','💡 照建議','','這組還沒分的，照建議（同資料夾、相機、檔名、你的規則…）一次分；會先列出要怎麼分'):'')+B('gview',VI.fromOv?'↩ 回一覽':'👀 一覽',VI.fromOv?'acc':'','整組縮圖一次看（G）')+(VI.gp[g]?B('gkeep','✅ 已篩選','acc','整包放到「已篩選」，保留資料夾、馬上搬'):'')+B('gnext','⏭','','下一組（]）');return}
  const p=it&&it.pack;if(p&&p.todo>=2){const nw=VI.lastPk!==p.path;VI.lastPk=p.path;if(nw){el.animate([{boxShadow:'0 0 0 3px var(--green)'},{boxShadow:'0 0 0 0 transparent'}],{duration:1600,iterations:2})}el.style.display='flex';el.style.cssText+=';gap:5px;align-items:center;flex-wrap:nowrap;font-size:12px;background:var(--panel2,#1a2230);border-radius:8px;padding:3px 6px';
    el.innerHTML=`<span style="flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">📦 在「<b>${esc(p.name)}</b>」<span class="mu">（你整理過的資料夾・還有 ${p.todo} 部沒審${p.np?`・照片 ${p.np}`:''}）</span></span>`+B('pview','👀 整包看')+B('pkeep','✅ 整包已篩選','acc','整包放到「已篩選」，保留資料夾、馬上搬');return}
  el.style.display='none';el.innerHTML=''}
function vcGrpNext(){if(!VI.gn||!VI.gn.length)return;const [,e]=vcGrpRange(VI.i);if(e>=VI.ids.length-1)return toast('已經是最後一組了');
  let k=e+1,sk=0;while(k<VI.ids.length){const [s2,e2]=vcGrpRange(k);if(VI.ids.slice(s2,e2+1).some(x=>!VI.tags[x])){k=s2;while(k<=e2&&VI.tags[VI.ids[k]])k++;break}sk++;k=e2+1}   // 整組都分好的跳過，停在下一組第一部還沒分的（V0.2.86）
  if(k>=VI.ids.length){k=e+1;sk=0}const g=VI.gi[k];toast('⏭ '+(VI.gn[g]||'下一組')+(sk?`（跳過 ${sk} 組已經分完的）`:''),1800);vcGo(k)}
function vcGrpMenu(){const Z=$('#vcz');vczShow('block');Z.style.overflow='auto';
  Z.innerHTML=`<div class="panel" style="margin:10px;max-width:560px;margin-inline:auto"><div class="row"><h3 class="grow">🧩 相關的排一起</h3><button class="pill" data-gm="x">關閉</button></div>
   <div class="mu" style="margin:4px 0 8px">一組一組審：上面會顯示「第幾組」，按 👀 一覽 整組縮圖一次看完，整組分到同一類、或 ⏭ 換下一組。</div>
   ${GMODES.map(([k,n,d])=>`<button class="pill ${(VC.g||'')===k?'acc':''}" data-gm="${k}" style="display:block;width:100%;text-align:left;padding:10px 12px;margin-bottom:6px"><b>${n}</b><br><span class="mu" style="font-size:12px">${d}</span></button>`).join('')}
   ${VI.it?(()=>{const a=String(VI.it.path).split(/[\\/]/);const L=[];for(let k=a.length-1;k>=2&&L.length<4;k--)L.push(a.slice(0,k).join(String(VI.it.path).includes('\\')?'\\':'/'));return `<div class="mu" style="margin:10px 0 4px">📦 自動判斷不對？把這部所在的資料夾當成一包（例如沒取名字的旅行資料夾）：</div>${L.map(p=>`<button class="pill" data-gmk="${esc(p)}" style="display:block;width:100%;text-align:left;margin-bottom:4px;font-size:12.5px">📦 ${esc(p)}</button>`).join('')}`})():''}</div>`;
  Z.onclick=async e=>{e.stopPropagation();const mk=e.target.closest('[data-gmk]');if(mk){const r=await api('/api/vg',{a:'mark',path:mk.dataset.gmk,on:1});toast(r.message||'失敗',3000);Z.onclick=null;vczHide();VI.cache={};return vcList()}
    const b=e.target.closest('[data-gm]');if(!b)return;Z.onclick=null;vczHide();if(b.dataset.gm==='x')return;VC.g=b.dataset.gm;LS.set('vc',VC);const t=$('[data-a="grp"]');if(t){t.textContent=GICON[VC.g];t.classList.toggle('acc',!!VC.g)}vcList()}}
let GPK=new Set(),GPKON=false;
function vcGrpView(keepSel){if(!VI.gn||!VI.gn.length)return;const [s,e0,g]=vcGrpRange(VI.i),big=e0-s+1>400,st=big?Math.min(VI.i,Math.max(s,e0-399)):s,e=big?st+399:e0,ids=VI.ids.slice(st,e+1),Z=$('#vcz');vczShow('block');Z.style.overflow='auto';const todo=ids.filter(x=>!VI.tags[x]);
  if(!keepSel){GPK=new Set();GPKON=false}const chain=VC.gchain!==false;
  const col=id=>{const c=VI.cats.find(x=>x.id===VI.tags[id]);return c?c.color:'transparent'};
  const tgt=GPK.size?`勾選的 ${GPK.size} 部`:todo.length<ids.length?`剩下還沒分的 ${todo.length} 部`:`這組全部 ${ids.length} 部`;
  const ovc=Math.max(3,Math.min(12,Math.round(Math.min(innerWidth,1700)/190)+(+VC.ocadj||0)));
  Z.innerHTML=`<div style="padding:8px;max-width:1700px;margin:0 auto"><div style="position:sticky;top:0;background:#000e;padding:6px 0;z-index:2"><div class="row" style="flex-wrap:nowrap;gap:5px"><b class="grow" style="color:#fff;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(VI.gn[g]||'')} <span class="mu">第 ${g+1}／${VI.gn.length} 組・${big?`第 ${(st-s+1).toLocaleString()}～${(e-s+1).toLocaleString()}／${(e0-s+1).toLocaleString()}`:ids.length} 部・待分 ${todo.length}</span></b><button class="pill" data-gv="x">✕</button></div>
   <div class="row" style="gap:5px;margin-top:5px;flex-wrap:wrap">${VI.gundo?`<button class="pill" data-gv="undo" title="把剛剛整組分類的 ${VI.gundo.ids.length} 部變回原本的樣子（Backspace）">↶ 復原剛剛</button>`:''}<button class="pill" data-gv="ss" title="這組一部一部自動播（可以調速度、左右滑）">▶ 輪播</button><button class="pill ${GPKON?'acc':''}" data-gv="sel" title="點縮圖勾起來（例如這組大多是旅遊，挑出 2 部是別的）">☑ 挑出來${GPK.size?' '+GPK.size:''}</button>${VI.gp[g]?`<button class="pill acc" data-gv="keep">✅ 整包已篩選</button>`:''}<span class="grow"></span><label class="mu" style="font-size:12px"><input type="checkbox" data-gv="chain" ${chain?'checked':''}> 分完自動開下一組</label><button class="pill" data-gv="next">⏭ 下一組</button></div>
   <div class="mu" style="margin:5px 0 4px;color:#ccc">按分類＝<b style="color:#fff">${tgt}</b>分到那一類（只是標記，按 🚚 搬 才會搬）。${GPKON?'點縮圖勾選／取消':'點縮圖跳到那一部看 16 格'}</div>
   <div style="display:flex;flex-wrap:wrap;gap:5px">${VI.cats.map((c,i)=>`<button class="pill" data-gc="${c.id}" style="border-left:5px solid ${c.color}">${i<10?`<span style="opacity:.6;font-size:10px">${(i+1)%10}</span> `:i<20?`<span style="opacity:.6;font-size:10px">⇧${(i-9)%10}</span> `:''}${esc(c.name)}</button>`).join('')}</div></div>
   <div style="display:grid;grid-template-columns:repeat(${ovc},1fr);gap:5px;margin-top:6px">${ids.slice(0,400).map((id,k)=>`<div data-gj="${st+k}" data-id="${id}" style="position:relative;cursor:pointer;outline:3px solid ${GPK.has(id)?'#fff':col(id)};border-radius:5px;${GPK.has(id)?'transform:scale(.94)':''}"><img loading="lazy" draggable="false" src="/api/vc_thumb?id=${id}" style="width:100%;aspect-ratio:16/10;object-fit:cover;border-radius:5px;background:#1a1f27;display:block;pointer-events:none">${GPK.has(id)?'<span style="position:absolute;left:3px;top:2px;font-size:16px">☑</span>':''}<span style="position:absolute;right:2px;bottom:2px;background:#000b;color:#fff;font-size:10px;padding:0 3px;border-radius:3px">${fmtT(VI.durs[st+k])}</span></div>`).join('')}</div>${big?`<div class="mu" style="text-align:center;margin:8px">這組有 ${(e0-s+1).toLocaleString()} 部：只顯示、也只處理上面這 400 部；分好之後再按「👀 一覽」看下一批</div>`:''}</div>`;
  const OG=Z.querySelector('[data-gj]');if(OG)scrubHook(OG.parentElement,'[data-gj]',c=>+c.dataset.id,c=>c,()=>GD);
  // 🖱 一覽裡也能按住拖過去整段勾（V0.2.73）
  Z.onwheel=e=>{if(!(e.ctrlKey||e.metaKey))return;e.preventDefault();VC.ocadj=Math.max(-6,Math.min(6,(+VC.ocadj||0)+(e.deltaY>0?1:-1)));LS.set('vc',VC);const sc=Z.scrollTop;vcGrpView(true);Z.scrollTop=sc};
  let GD=null;Z.onpointerdown=e=>{const c=e.target.closest('[data-gj]');if(!c||e.button>0||e.pointerType!=='mouse')return;e.preventDefault();GD={k0:+c.dataset.gj,x:e.clientX,y:e.clientY,moved:false,base:new Set(GPK),add:!(GPKON&&GPK.has(+c.dataset.id))}};
  Z.onpointermove=e=>{if(!GD)return;if(!GD.moved){if(Math.hypot(e.clientX-GD.x,e.clientY-GD.y)<8)return;GD.moved=true;if(!GPKON){GPKON=true;GD.base=new Set();GD.add=true}}
    if(e.clientY<70)Z.scrollTop-=18;else if(e.clientY>innerHeight-40)Z.scrollTop+=18;
    const el=document.elementFromPoint(e.clientX,e.clientY),c=el&&el.closest&&el.closest('[data-gj]');if(!c)return;const a=Math.min(GD.k0,+c.dataset.gj),z=Math.max(GD.k0,+c.dataset.gj);
    Z.querySelectorAll('[data-gj]').forEach(d=>{const k=+d.dataset.gj,id=+d.dataset.id,w=k>=a&&k<=z?GD.add:GD.base.has(id);if(w)GPK.add(id);else GPK.delete(id);d.style.outline=`3px solid ${w?'#fff':col(id)}`;d.style.transform=w?'scale(.94)':''})};
  Z.onpointerup=()=>{if(GD&&GD.moved){Z._gdone=1;setTimeout(()=>{Z._gdone=0},300);const sc=Z.scrollTop;vcGrpView(true);Z.scrollTop=sc;toast(`☑ 勾了 ${GPK.size} 部，按上面的分類一次套用`,2000)}GD=null};
  Z.onclick=async ev=>{ev.stopPropagation();if(Z._gdone){Z._gdone=0;return}const ch=ev.target.closest('[data-gv="chain"]');if(ch){VC.gchain=ch.checked;LS.set('vc',VC);return}
    const j=ev.target.closest('[data-gj]');if(j){if(GPKON){const id=+j.dataset.id;GPK.has(id)?GPK.delete(id):GPK.add(id);return vcGrpView(true)}Z.onclick=null;vczHide();VI.fromOv=1;return vcGo(+j.dataset.gj)}
    const v=ev.target.closest('[data-gv]');if(v){const a=v.dataset.gv;if(a==='x'){Z.onclick=null;return vczHide()}
      if(a==='sel'){GPKON=!GPKON;if(!GPKON)GPK=new Set();return vcGrpView(true)}
      if(a==='undo'){const U=VI.gundo;if(!U)return;VI.gundo=null;const none=U.ids.filter(x=>!U.prev[x]);if(none.length)await api('/api/vc_tag_many',{ids:none,cat:0,only_new:false});
        for(const x of U.ids.filter(x=>U.prev[x]))await api('/api/vc_tag',{id:x,cat:U.prev[x]});U.ids.forEach(x=>{if(U.prev[x])VI.tags[x]=U.prev[x];else delete VI.tags[x]});
        toast(`↶ 復原了 ${U.ids.length} 部`);await vcReCats();VI.cache={};if(U.at!=null)vcGo(U.at);return setTimeout(()=>vcGrpView(),300)}
      if(a==='ss'){const L=ids.map(i=>[String(i),VC.kind==='photo'?'photo':'video']);ZAUTO=true;return zoomImg(L[0][0],L[0][1],L)}
      if(a==='next'){Z.onclick=null;vczHide();vcGrpNext();return setTimeout(()=>vcGrpView(),350)}
      if(a==='keep'){return pkKeep(VI.gp[g],0,null,'',async r=>{if(r&&r.ok){Z.onclick=null;vczHide();await vcReCats();vcList()}})}}
    const c=ev.target.closest('[data-gc]');if(!c)return;const cid=+c.dataset.gc,cat=VI.cats.find(x=>x.id===cid),L=GPK.size?[...GPK]:todo.length?todo:ids;
    const prev={};L.forEach(x=>prev[x]=VI.tags[x]||0);
    const r=await api('/api/vc_tag_many',{ids:L,cat:cid,only_new:!GPK.size&&!!todo.length});if(!r.ok)return toast(r.message||'失敗');VI.gundo={ids:L,prev,at:VI.i};toast(`✔ ${L.length} 部 → ${cat.name}`,1500);L.forEach(x=>VI.tags[x]=cid);await vcReCats();VI.cache={};
    if(GPK.size){GPK=new Set();GPKON=false;if(ids.some(x=>!VI.tags[x]))return vcGrpView(true)}
    Z.onclick=null;vczHide();if(big){const nx=VI.ids.findIndex((x,k)=>k>=s&&k<=e0&&!VI.tags[x]);if(nx>=0){vcGo(nx);return setTimeout(()=>vcGrpView(),400)}}
    if(chain){const [,e2]=vcGrpRange(VI.i);if(e2>=VI.ids.length-1)return toast('🎉 最後一組了');vcGo(e2+1);return setTimeout(()=>vcGrpView(),400)}vcGo(VI.i)}}
// ---- 📦 資料夾包（V0.2.14）：你以前整理過的資料夾整包看、整包放到「已篩選」
let PK=LS.get('pk',{show:'todo',q:'',o:''}),PKSEL=new Set();
function pkSelBar(){let b=$('#pksb');if(!PKSEL.size){if(b)b.remove();return}if(!b){b=document.createElement('div');b.id='pksb';b.style.cssText='position:fixed;left:8px;right:8px;bottom:calc(10px + env(safe-area-inset-bottom,0px));z-index:40;background:var(--panel);border:1px solid var(--accent);border-radius:14px;padding:8px 10px;display:flex;gap:6px;align-items:center;box-shadow:0 6px 24px #0008';document.body.appendChild(b)}
  b.innerHTML=`<b class="grow">☑ 勾了 ${PKSEL.size} 包</b><button class="pill" data-ps2="clr">取消</button><button class="pill" data-ps2="cat">🏷 分到…</button><button class="pill acc" data-ps2="keep">✅ 全部已篩選</button>`;
  b.onclick=async e=>{const k=e.target.closest('[data-ps2]');if(!k)return;const a=k.dataset.ps2;if(a==='clr'){PKSEL.clear();$$('[data-pck]').forEach(c=>c.checked=false);return pkSelBar()}
    const run=async(cat,cn)=>{if(!confirm(`勾的 ${PKSEL.size} 包整包（影片＋照片）放到「${cn}」並馬上搬？\n\n每包保留自己的資料夾；只搬這幾包。可以在「↶ 最近整包搬過」一包一包搬回。`))return;
      const r=await api('/api/vg',{a:'tag_many',paths:[...PKSEL],cat,go:1});toast(r.message||'失敗',6000);if(r.ok){PKSEL.clear();pkSelBar();rPk()}};
    if(a==='keep')return run(0,'已篩選');
    const s=await api('/api/vc_state');const C=s.cats||[];const nm=prompt('分到哪一類？輸入名字：\n'+C.map(c=>c.name).join('、'));if(!nm)return;const c=C.find(x=>x.name===nm.trim());if(!c)return toast('沒有這個分類');run(c.id,c.name)}}
const pkCard=g=>`<div class="panel" data-pp="${esc(g.path)}" style="padding:10px"><div class="row" style="flex-wrap:nowrap;gap:6px"><input type="checkbox" data-pck style="width:22px;height:22px;flex:none" ${PKSEL.has(g.path)?'checked':''}><div class="grow" style="min-width:0"><b style="font-size:15px">📦 ${esc(g.name)}</b><div class="mu" style="font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(dir(g.path))}</div></div>
 <div class="mu" style="text-align:right;font-size:12px;white-space:nowrap">🎞 ${g.n}${g.todo<g.n?`（待審 ${g.todo}）`:''}${g.np?` · 📷 ${g.np}`:''}${g.pet?` · <span title="有貓狗的影片（電腦看的）">🐾 ${g.pet}</span>`:''}<br>${fmtB(g.b)}${g.t0?' · '+day(g.t0).slice(0,10)+(day(g.t1).slice(0,10)!==day(g.t0).slice(0,10)?'～'+day(g.t1).slice(0,10):''):''}</div></div>
${g.todo<g.n?`<div style="height:5px;border-radius:3px;background:var(--track);overflow:hidden;margin-top:5px" title="已審 ${g.n-g.todo}／${g.n} 部"><div style="height:100%;width:${((g.n-g.todo)/g.n*100).toFixed(1)}%;background:var(--green)"></div></div>`:''}
 <div data-pa="view" style="display:grid;grid-template-columns:repeat(${innerWidth<500?4:8},1fr);gap:2px;margin:6px 0;cursor:pointer">${g.cover.slice(0,innerWidth<500?4:8).map(id=>`<img loading="lazy" src="/api/vc_thumb?id=${id}" style="width:100%;aspect-ratio:16/10;object-fit:cover;border-radius:4px;background:#1a1f27">`).join('')}</div>
 <div class="row" style="gap:5px"><button class="pill" data-pa="view">👀 看內容</button><button class="pill" data-pa="one">▶ 一部一部審</button><span class="grow"></span>${g.skip?'<button class="pill" data-pa="unskip">↶ 放回</button>':'<button class="pill" data-pa="skip">⏭ 跳過</button>'}<button class="pill" data-pa="cat">🏷 分到…</button><button class="pill acc" data-pa="keep">✅ 整包已篩選</button></div></div>`;
let PKL=[];
async function rPk(again){if(again)return;const j=await api(U('/api/vg',{show:PK.show,q:PK.q,o:PK.o||''}));if(!j.ok)return;PKL=(j.packs||[]).map(g=>g.path);
  const chips=[['todo','還沒審的'],['done','審完的'],['skip','跳過的'],['all','全部'],['moved','↶ 最近整包搬過']].map(([k,n])=>`<button class="pill ${PK.show===k?'acc':''}" data-ps="${k}">${n}</button>`).join('');
  $('#v').innerHTML=`<div class="panel"><b>📦 資料夾包・${j.total.toLocaleString()} 包</b>
   <div class="mu" style="margin:4px 0 6px">你以前自己整理、有取名字的資料夾（例如「2020-日本旅遊」）整包列出來：先 👀 快速看過，再決定 ✅ 整包放到「已篩選」（保留資料夾結構、馬上搬）或 ▶ 一部一部審。手機整台倒出來的（DCIM、備份…）不算一包。</div>
   <div class="mu" id="pkdest" style="font-size:12px;margin:-2px 0 6px">📁 「已篩選」放在：<b style="color:var(--text)">${['不搬','原地','=','stay'].includes((j.keep_dest||'').trim())?'📌 不搬（留在原處，只標記）':j.keep_dest?esc(j.keep_dest)+'\\資料夾名\\…':'每顆硬碟的 \\FileCompare_分類\\已篩選\\資料夾名\\…'}</b>　<a href="#" data-pkdst>改位置</a></div>
   <div class="row" style="gap:4px">${chips}<input id="pkq" placeholder="找資料夾名…" value="${esc(PK.q)}" style="flex:1;min-width:90px"><select id="pko">${[['','建議順序'],['n','待審最多'],['new','日期新→舊'],['old','日期舊→新'],['big','最大'],['name','名字']].map(([k,n])=>`<option value="${k}" ${(PK.o||'')===k?'selected':''}>${n}</option>`).join('')}</select></div></div>
   <div id="pkl">${PK.show==='moved'?((j.moved||[]).map(m=>`<div class="panel row" style="flex-wrap:nowrap;padding:10px"><div class="grow"><b>📦 ${esc(m.name)}</b><br><span class="mu" style="font-size:12px">${m.n.toLocaleString()} 個 → 「${esc(m.cname)}」・${day(m.t)}</span></div><button class="pill" data-pb="${esc(m.name)}" data-pc="${m.cat}">↶ 搬回原處</button></div>`).join('')||'<div class="panel mu">最近沒有整包搬過的</div>'):(j.packs.map(pkCard).join('')||'<div class="panel mu">這裡沒有資料夾包</div>')}</div>${j.total>j.packs.length?`<div class="mu" style="text-align:center;margin:8px">只顯示前 ${j.packs.length} 包，用搜尋找其他的</div>`:''}`;
  pkSelBar();$('#pkq').onchange=()=>{PK.q=$('#pkq').value.trim();LS.set('pk',PK);rPk()};$('#pko').onchange=()=>{PK.o=$('#pko').value;LS.set('pk',PK);rPk()};
  $('#v').onclick=async e=>{const ps=e.target.closest('[data-ps]');if(ps){PK.show=ps.dataset.ps;LS.set('pk',PK);return rPk()}
    const ck=e.target.closest('[data-pck]');if(ck){const p=ck.closest('[data-pp]').dataset.pp;ck.checked?PKSEL.add(p):PKSEL.delete(p);return pkSelBar()}
    if(e.target.closest('[data-pkdst]')){e.preventDefault();const s=await api('/api/vc_state');const c=(s.cats||[]).find(x=>x.name==='已篩選');if(!c)return;
      const n=prompt('「已篩選」要放哪？（同一顆硬碟的資料夾，例如 R:\\已篩選；空的＝預設 \\FileCompare_分類\\已篩選；填「不搬」＝只標記、留在原處）',c.dest||'');if(n===null)return;
      const r=await api('/api/vc_cat',{a:'edit',id:c.id,dest:n});toast(r.message||'失敗');return rPk()}
    const pb=e.target.closest('[data-pb]');if(pb){if(!confirm(`「${pb.dataset.pb}」整包搬回原本的位置，變回「還沒審」？`))return;const r=await api('/api/vg',{a:'back',name:pb.dataset.pb,cat:+pb.dataset.pc});toast(r.message||'失敗',5000);return rPk()}
    const b=e.target.closest('[data-pa]');if(!b)return;const card=b.closest('[data-pp]'),p=card.dataset.pp,a=b.dataset.pa;
    if(a==='view')return pkView(p,card);
    if(a==='one'){VC.folder=p;VC.f='todo';VC.g='';VC.kind='video';LS.set('vc',VC);toast('▶ 只看「'+p.split(/[\\/]/).pop()+'」（分類頁左上 📁 可以取消）',3500);return go('vc')}
    if(a==='skip'||a==='unskip'){const r=await api('/api/vg',{a,path:p});toast(r.message);card.remove();return}
    if(a==='keep')return pkKeep(p,0,card);
    if(a==='cat')return pkCat(p,card)}}
async function pkKeep(p,cat,card,cname,after){const nm=p.split(/[\\/]/).pop(),cn=cname||'已篩選';let inf={};try{inf=(await api(U('/api/vg',{info:p}))).pack||{}}catch(e){}
  const sz=`${(inf.n||0).toLocaleString()} 部影片${inf.np?`＋${inf.np.toLocaleString()} 張照片`:''}${inf.b?`（${fmtB(inf.b)}）`:''}`;
  if(!confirm(`「${nm}」整包 ${sz} 放到「${cn}」並馬上搬？${(inf.n||0)>500?'\n\n⚠ 這包很大，確定都是同一類嗎？可以先「👀 看內容」或「▶ 一部一部審」。':''}\n\n會保留資料夾：同一顆硬碟的 \\FileCompare_分類\\${cn}\\${nm}\\…\n只在同一顆硬碟裡搬，搬錯了可以在「📦 隔離區 → 依原因」整批復原。`))return after&&after(null);
  const r=await api('/api/vg',{a:'tag',path:p,cat:cat||0,go:1});toast(r.message||'失敗',5000);if(r.ok&&card)card.remove();if(after)after(r);return r}
async function pkCat(p,card,after){const s=await api('/api/vc_state');const C=s.cats||[];const W=document.createElement('div');W.style.cssText='position:fixed;inset:0;z-index:85;background:#000c;display:grid;place-items:center';
  W.innerHTML=`<div class="panel" style="max-width:420px;width:92%"><div class="row"><b class="grow">🏷 整包分到哪一類？</b><button class="pill" data-k="x">✕</button></div><div class="mu" style="margin:4px 0 8px">一樣保留資料夾結構、馬上搬</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">${C.map(c=>`<button class="pill" data-k="${c.id}" data-n="${esc(c.name)}" style="border-left:5px solid ${c.color};padding:10px">${esc(c.name)}</button>`).join('')}</div></div>`;
  const close=()=>W.remove();document.body.appendChild(W);ovOpen(close);W.onclick=e=>{const b=e.target.closest('[data-k]');if(!b&&e.target!==W)return;ovClose(close);if(!b||b.dataset.k==='x')return;pkKeep(p,+b.dataset.k,card,b.dataset.n,after)}}
async function pkView(p,card){const j=await api(U('/api/vg',{path:p}));if(!j.ok)return toast(j.message||'讀不到');const g=j.pack||{name:p.split(/[\\/]/).pop()},R=j.rows||[];
  const W=document.createElement('div');W.style.cssText='position:fixed;inset:0;z-index:75;background:var(--bg);overflow:auto;padding:8px';const L=R.map(r=>[String(r.id),r.kind]);
  let html='',last=null;R.forEach(r=>{if(r.sub!==last){last=r.sub;html+=`<div class="mu" style="grid-column:1/-1;margin-top:6px;font-weight:700">📁 ${esc(r.sub==='.'?g.name:r.sub)}</div>`}
    html+=`<div data-zv="${r.id}" data-zk="${r.kind}" style="position:relative;cursor:pointer"><img loading="lazy" src="${r.kind==='video'?'/api/vc_thumb?id='+r.id:'/api/fc_thumb?id='+r.id+'&w=320'}" style="width:100%;aspect-ratio:16/10;object-fit:cover;border-radius:5px;background:#1a1f27;display:block">${r.kind==='video'?`<span style="position:absolute;right:2px;bottom:2px;background:#000b;color:#fff;font-size:10px;padding:0 3px;border-radius:3px">▶ ${fmtT(r.dur)}</span>`:''}${r.cat?`<span style="position:absolute;left:2px;top:2px;background:#000b;color:#fff;font-size:10px;padding:0 3px;border-radius:3px">${esc(r.cat)}${r.moved?' ✔':''}</span>`:''}</div>`});
  W.innerHTML=`<div style="position:sticky;top:-8px;background:var(--bg);padding:6px 0;z-index:2"><div class="row" style="flex-wrap:nowrap"><b class="grow" style="min-width:0;font-size:16px">📦 ${esc(g.name)} <span class="mu" style="font-size:12px">${j.n} 個${g.n?`・🎞 ${g.n}`:''}${g.np?`・📷 ${g.np}`:''}</span></b><button class="pill" data-w="x">✕</button></div><div class="row" style="gap:5px;margin-top:5px;flex-wrap:wrap"><button class="pill" data-w="ss">▶ 輪播</button><button class="pill" data-w="one">▶ 一部一部審</button>${PKL.indexOf(p)>=0&&PKL.indexOf(p)<PKL.length-1?'<button class="pill" data-w="next">⏭ 下一包</button>':''}<button class="pill" data-w="cat">🏷 分到…</button><button class="pill acc" data-w="keep" title="鍵盤 K">✅ 整包已篩選</button><button class="pill" data-w="nomark" title="自動判斷錯了：這個資料夾不要當成一包">🚫 不是一包</button></div></div>
   <div class="mu" style="font-size:12px;margin-bottom:4px">${esc(p)}</div>${j.dups&&j.dups.n?`<div class="row" style="flex-wrap:nowrap;gap:6px;padding:6px 8px;border:1px solid var(--orange);border-radius:8px;margin-bottom:6px;font-size:12.5px"><span class="grow">⚠ 其中 <b>${j.dups.n.toLocaleString()}</b> 個（${fmtB(j.dups.b)}）在別的地方也有一模一樣的，大多在：${j.dups.where.map(w=>esc(dl2(w.path))).join('、')}</span><button class="pill" data-w="dpl" style="flex:none">🧭 先處理重複</button></div>`:''}<div style="display:grid;grid-template-columns:repeat(${innerWidth<500?3:6},1fr);gap:4px">${html}</div>${j.n>R.length?`<div class="mu" style="text-align:center;margin:8px">只顯示前 ${R.length} 個</div>`:''}`;
  const kd=e=>{if(!document.body.contains(W)){removeEventListener('keydown',kd,true);return}if(document.querySelector('[style*="z-index:80"],[style*="z-index: 80"]')||/INPUT|SELECT|TEXTAREA/.test(e.target.tagName))return;   // ⌨ →／N 下一包、K 整包已篩選、Esc 關（V0.2.55）
    const k=e.key.toLowerCase();e.stopPropagation();if(k==='arrowright'||k==='n'){const b=W.querySelector('[data-w="next"]');if(b){e.preventDefault();b.click()}}else if(k==='k'){e.preventDefault();W.querySelector('[data-w="keep"]').click()}else if(k==='escape'){e.preventDefault();ovClose(close)}};
  const close=()=>{W.remove();removeEventListener('keydown',kd,true)};document.body.appendChild(W);ovOpen(close);addEventListener('keydown',kd,true);
  scrubHook(W,'[data-zk="video"]',c=>+c.dataset.zv,c=>c);
  W.onclick=e=>{const z=e.target.closest('[data-zv]');if(z)return zoomImg(z.dataset.zv,z.dataset.zk,L);const b=e.target.closest('[data-w]');if(!b)return;const a=b.dataset.w;
    if(a==='nomark'){api('/api/vg',{a:'mark',path:p,on:0}).then(r=>{toast(r.message||'失敗');ovClose(close);if(CUR==='tool:pk')setTimeout(()=>rPk(),300)});return}
    if(a==='x')return ovClose(close);if(a==='dpl'){ovClose(close);return setTimeout(()=>go('tool:dpl'),300)}if(a==='ss'){if(!L.length)return;ZAUTO=true;return zoomImg(L[0][0],L[0][1],L)}
    if(a==='one'){ovClose(close);VC.folder=p;VC.f='todo';VC.g='';VC.kind='video';LS.set('vc',VC);return setTimeout(()=>go('vc'),300)}
    const nx=()=>{const k=PKL.indexOf(p);return k>=0&&k<PKL.length-1?PKL[k+1]:''};
    if(a==='next'){const n=nx();ovClose(close);if(n)setTimeout(()=>pkView(n,document.querySelector(`[data-pp="${CSS.escape(n)}"]`)),300);return}
    const done=r=>{if(r&&r.ok){const n=nx();PKL=PKL.filter(q=>q!==p);ovClose(close);if(CUR==='vc')setTimeout(async()=>{await vcReCats();vcList()},300);else if(n&&LS.get('pkchain',1))setTimeout(()=>pkView(n,document.querySelector(`[data-pp="${CSS.escape(n)}"]`)),400)}};
    if(a==='keep')return pkKeep(p,0,card,'',done);if(a==='cat')return pkCat(p,card,done)}}
// ---- 📚 整批分類（V0.1.29）：現在這份清單（篩選＋資料夾＋長度）全部分到同一類
function vcMany(){const Z=$('#vcz'),n=VI.ids.length;if(!n)return toast('這份清單是空的');const nt=VI.ids.filter(i=>!VI.tags[i]).length;vczShow('block');Z.style.overflow='auto';
  const sz=VI.sizes.reduce((a,b)=>a+(+b||0),0);
  Z.innerHTML=`<div class="panel" style="margin:10px;max-width:640px;margin-inline:auto"><div class="row"><h3 class="grow">📚 整批分類</h3><span class="mu" style="font-size:12px;margin-right:8px;white-space:nowrap"><a href="#" data-jump="vccam">📷 相機</a>・<a href="#" data-jump="vcpet">🐾 貓狗</a>・<a href="#" data-jump="vclearn">🧠 學到的</a>・<a href="#" data-jump="vcrl">📏 規則</a></span><button class="pill" data-m="x">關閉</button></div>
   <div class="mu" style="margin:4px 0 8px">現在這份清單：<b style="color:var(--text)">${n.toLocaleString()} 部</b>（${fmtB(sz)}），其中還沒分的 <b style="color:var(--text)">${nt.toLocaleString()}</b> 部。<br>例如：先用 📁 選「LINE 下載」資料夾、或 ⏱ 選「短於 30 秒」，再一次全部分到同一類。只是「標記」，按「🚚 開始搬檔」才會搬。</div>
   <label class="row" style="gap:6px;margin-bottom:8px"><input type="checkbox" id="vcmAll"> 已經分好的也改成這一類（已經搬過的不動）</label>
   <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:6px">${VI.cats.map(c=>`<button class="pill" data-mc="${c.id}" style="padding:10px 6px">${esc(c.name)}<br><span class="mu">${(c.n||0).toLocaleString()} 部</span></button>`).join('')}
   <button class="pill er" data-mc="0" style="padding:10px 6px">✖ 取消分類<br><span class="mu">變回沒分的</span></button></div>
   <div class="row" style="margin-top:10px"><button class="pill acc" data-mh="1" style="padding:10px 14px">💡 照建議分…</button><span class="mu" style="font-size:12px">照你的習慣：同一個資料夾分好的大多是哪類、資料夾名有同一個字的大多分到哪類。會先列出要怎麼分給你看</span></div>
   <div id="vcsus"></div>
   <div style="margin-top:12px;border-top:1px solid var(--line2);padding-top:8px"><b>📷 照相機／🔤 檔名開頭一次分</b> <span class="mu" style="font-size:12px">還沒分類的，照拍的相機或檔名開頭（DJI_、LINE_、Screenrecorder…）分。按「看」先看那些</span>
    <div class="seg" style="margin-top:4px"><button data-cby="" class="${(VC.cby||'')===''?'on':''}">📷 相機</button><button data-cby="name" class="${VC.cby==='name'?'on':''}">🔤 檔名開頭</button></div>
    <div id="vccam" class="mu" style="margin:6px 0;max-height:220px;overflow:auto">讀取中…</div></div>
   <div style="margin-top:12px;border-top:1px solid var(--line2);padding-top:8px"><b>🐾 電腦看內容：貓狗、人臉、全黑、沒動…</b> <span class="mu" style="font-size:12px">（也會用 Windows 內建的人臉偵測找有人的）電腦自己看每部的 16 格（照片模式就看照片）裡有沒有貓、狗（用 Windows 內建的 Windows ML，第一次會下載 14 MB 的辨識模型）。還沒做 16 格的影片會順便先做（之後審片直接用、比較快）；背景慢慢做，你審片時會放慢。另外也會找出 🌑 全黑、⬜ 沒東西、🧱 沒動的影片（不用 Windows ML）。上面切到 📷 照片再按，就是找照片</span>
    <div id="vcpet" class="mu" style="margin:6px 0">讀取中…</div></div>
   <div style="margin-top:12px;border-top:1px solid var(--line2);padding-top:8px"><b>🧠 電腦學到的習慣</b> <span class="mu" style="font-size:12px">從你分過的學來的（💡 會照這些建議）。覺得不對的按「✕ 不要」，以後就不照這條建議</span>
    <div id="vclearn" class="mu" style="margin:6px 0;max-height:200px;overflow:auto">讀取中…</div></div>
   <div style="margin-top:12px;border-top:1px solid var(--line2);padding-top:8px"><b>📏 我的規則</b> <span class="mu" style="font-size:12px">檔案路徑裡有這個字 → 建議分到這類（💡 會亮、「照建議分」會用，最優先）。例如：LINE → Delete、婚禮 → Family；也可以寫「&lt;3秒」＝短於 3 秒的影片 → Delete、「相機:DJI」＝相機型號有 DJI 的 → DJI、「日期:2019-10」或「日期:2019-10-20～2019-10-25」＝那段時間拍的 → 例如 旅遊、「內容:有狗」「內容:有貓」「內容:很暗」＝電腦看到的（🐾 那區） → 你要的類</span>
    <div id="vcrl" class="mu" style="margin:6px 0">讀取中…</div>
    <div class="row" style="gap:6px;flex-wrap:nowrap"><input id="vcrw" placeholder="字（例如 LINE）" style="flex:1;min-width:0"><select id="vcrc" style="flex:1;min-width:0">${VI.cats.map(c=>`<option value="${c.id}">${esc(c.name)}</option>`).join('')}</select><button class="pill acc" data-rl="add">＋ 加</button></div></div></div>`;
  const learn=async(j)=>{j=j||await api('/api/vc_learn');const el=$('#vclearn');if(!el||!j.ok)return;const nm=w=>w.startsWith('📷')?`📷 相機「${esc(w.slice(2))}」`:w.startsWith('🔤')?`🔤 檔名開頭「${esc(w.slice(2))}」`:w.startsWith('📍')?`📍 同一個地方（${esc(w.slice(2))}）`:w.startsWith('🐾')?`🐾 電腦看到「${esc(w.slice(2))}」`:w.startsWith('🔎')?`🔎 電腦猜是「${esc(w.slice(2))}」`:`📁 資料夾名有「${esc(w)}」`;
    el.innerHTML=((j.acc||[]).length?`<div style="font-size:12.5px;margin-bottom:4px">📈 最近有 💡 建議的時候，你照著分的比例：${j.acc.map(a=>`${esc(a.k)} <b style="color:${a.p>=90?'var(--green)':a.p>=70?'var(--text)':'#f88'}">${a.p}%</b>（${a.n} 次）`).join('、')}<br><span class="mu">九成以上的可以放心用「照建議分」一次分完</span></div>`:'')+((j.rows||[]).length?j.rows.map(r=>`<div class="row" style="flex-wrap:nowrap;gap:6px;font-size:12.5px;${r.ign?'opacity:.45;text-decoration:line-through':''}"><span class="grow" style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${nm(r.w)} → <b style="color:var(--text)">${esc(r.cat)}</b> <span class="mu">（${r.n}／${r.tot} 部）</span></span><button class="pill" data-lw="${esc(r.w)}" data-la="${r.ign?'unignore':'ignore'}" style="min-height:0;padding:1px 8px;font-size:12px">${r.ign?'↩ 恢復':'✕ 不要'}</button></div>`).join(''):'還沒學到（多分一些就會有）')};learn();
  const cams=async()=>{const j=await api(U('/api/vc_cams',{k:VC.kind||'video',by:VC.cby||''}));const el=$('#vccam');if(!el||!j.ok)return;
    el.innerHTML=(j.rows||[]).length?`<table style="width:100%;font-size:12.5px;border-collapse:collapse">${j.rows.map((r,i)=>`<tr><td style="padding:3px 4px;color:var(--text)">${esc(r.cam)}</td><td style="padding:3px 4px;white-space:nowrap">${r.n.toLocaleString()} 部・${fmtB(r.b)}</td><td style="padding:3px 4px;white-space:nowrap;text-align:right"><button class="pill" data-cm="v" data-ci="${i}" style="min-height:0;padding:2px 8px;font-size:12px">看</button> <select data-cs="${i}" style="font-size:12px;min-width:0;max-width:110px">${VI.cats.map(c=>`<option value="${c.id}" ${c.name.length>=2&&r.cam.toLowerCase().includes(c.name.toLowerCase())?'selected':''}>${esc(c.name)}</option>`).join('')}</select> <button class="pill" data-cm="t" data-ci="${i}" style="min-height:0;padding:2px 8px;font-size:12px">分</button></td></tr>`).join('')}</table>`:'還沒分類的都分好了';el._rows=j.rows};cams();
  api('/api/vc_sus').then(j=>{const el=$('#vcsus');if(el&&j.ok&&j.n)el.innerHTML=`<div style="margin-top:12px;border-top:1px solid var(--line2);padding-top:8px"><b>🧐 可能分錯的 ${j.n.toLocaleString()} 部</b> <span class="mu" style="font-size:12px">分好還沒搬的裡面，跟同資料夾、或你平常的分法不一樣的。搬之前看一眼</span> <button class="pill" data-go="vc:chk|🧐 可能分錯的" style="min-height:0;padding:2px 9px;font-size:12px">👀 看這些</button></div>`});   // V0.4.31
  const pets=async(j)=>{j=j||await api(U('/api/vc_pet',{k:VC.kind||'video'}));const el=$('#vcpet');if(!el||!j.ok)return;const t=j.st||{};
    el.innerHTML=`${t.msg?esc(t.msg).replace(/\n/g,'<br>')+'<br>':''}${t.err?`<span style="color:#f88;white-space:pre-wrap">${esc(t.err)}</span><br><button class="pill" data-go="tool:diag" style="min-height:0;padding:2px 9px;font-size:12px;margin:3px 0">🩺 自我檢查（按 🔬 實際跑一次，截圖給開發者）</button><br>`:''}${t.model===false&&(t.err||'').includes('下載不了')?`<label class="pill" style="cursor:pointer;display:inline-block;margin:4px 0">⬆ 上傳模型檔（mobilenetv2-7.onnx）<input type="file" accept=".onnx" data-pmod hidden></label><br>`:''}看過 <b style="color:var(--text)">${(t.checked||0).toLocaleString()}</b> 部：🐶 有狗 <b style="color:var(--text)">${(t.dog||0).toLocaleString()}</b>・🐱 有貓 <b style="color:var(--text)">${(t.cat||0).toLocaleString()}</b>・👤 有人臉 <b style="color:var(--text)">${(t.face||0).toLocaleString()}</b>${t.win===false?'<br>⚠ 只有 Windows 電腦能用':''}
     <div class="row" style="gap:6px;margin-top:6px;flex-wrap:wrap">${t.run?'<button class="pill" data-pt="stop">⏹ 停止</button>':'<button class="pill acc" data-pt="start">🐾 開始找</button><button class="pill" data-pt="test" title="先試 20 部看看準不準">試 20 部</button>'+((VC.folder||VC.q||(VC.f&&VC.f!=='todo'))&&VI.ids.length?`<button class="pill" data-pt="only" title="只看現在這份清單（例如你選的資料夾、搜尋結果），比較快">📋 只看這份清單（${VI.ids.length.toLocaleString()}）</button>`:'')+(t.checked?'<button class="pill" data-pt="reset" title="清掉之前看的結果，全部重新看（例如更新修好之後）">🔄 重新看</button>':'')}
      <label class="row" style="gap:4px;font-size:12px" title="開著的話，之後背景新做好 16 格的影片會自動看（每 10 分鐘看一次有沒有新的）"><input type="checkbox" id="vcpauto" ${t.auto?'checked':''}>背景自動看新的</label><select id="vcpth" title="靈敏度：越鬆找到越多、但看錯也越多">${[[0.2,'寬鬆（多抓）'],[0.35,'一般'],[0.5,'嚴格'],[0.7,'很嚴格（少抓）']].map(([v,n])=>`<option value="${v}" ${Math.abs((t.th||0.35)-v)<0.01?'selected':''}>${n}</option>`).join('')}</select><button class="pill acc" data-pt="quick" title="一頁一頁：全部先勾好，把不是的點掉，Enter 分好、下一頁">⚡ 快速審</button><button class="pill" data-pt="view">👀 只看有貓狗的</button>${t.nopet?`<button class="pill" data-pt="npclr" title="你按過「不是貓狗」的 ${t.nopet} 部：清掉標記（會再出現在 🐾 清單）">🔄 不是貓狗 ${t.nopet.toLocaleString()}</button>`:''}<button class="pill" data-pt="vface">👤 只看有人的</button><select id="vcptc" style="min-width:110px;max-width:100%">${VI.cats.map(c=>`<option value="${c.id}" ${(LS.get('pettc',0)?LS.get('pettc',0)===c.id:/family|家/i.test(c.name))?'selected':''}>${esc(c.name)}</option>`).join('')}</select><button class="pill" data-pt="tag">全部分到這類</button></div>${(t.sample||[]).length?`<div style="margin-top:8px;font-size:12.5px">🐾 <b style="color:var(--text)">最像貓狗的幾部</b>（看看電腦認得準不準；點一下從那部開始看）<div style="display:grid;grid-template-columns:repeat(${innerWidth<500?4:8},1fr);gap:3px;margin-top:4px">${t.sample.map(id=>`<img loading="lazy" data-pt="smp" data-id="${id}" src="/api/vc_thumb?id=${id}&w=320${VC.kind==='photo'?'':'&p=1'}" style="width:100%;aspect-ratio:16/10;object-fit:cover;border-radius:4px;cursor:pointer;background:#1a1f27">`).join('')}</div></div>`:''}${(t.scenes||[]).length?`<div style="margin-top:8px;font-size:12.5px">🔎 <b style="color:var(--text)">還沒分類的，電腦猜的內容</b>（點一下只看那些；會看錯，先看再分）<div class="row" style="gap:4px;flex-wrap:wrap;margin-top:4px">${t.scenes.map(x=>`<span style="display:inline-flex;gap:2px"><button class="pill" data-pt="sc" data-sk="${esc(x.k)}" data-sn="${esc(x.name)}" style="min-height:0;padding:2px 9px;font-size:12px">${esc(x.name)} <b>${x.n.toLocaleString()}</b></button>${x.lc?`<button class="pill acc" data-pt="sct" data-sk="${esc(x.k)}" data-sn="${esc(x.name)}" data-lc="${x.lc}" data-ln="${esc(x.ln)}" data-n="${x.n}" title="你以前這種內容大多分到「${esc(x.ln)}」（${x.lh}）：一次全部分過去" style="min-height:0;padding:2px 8px;font-size:12px">💡→ ${esc(x.ln)}</button>`:''}</span>`).join('')}</div></div>`:''}`;
    const pm=el.querySelector('[data-pmod]');if(pm)pm.onchange=async()=>{const f=pm.files[0];if(!f)return;toast('⬆ 上傳中…',2000);const r=await api('/api/vc_pet_model',await f.arrayBuffer(),true);toast(r.message||'失敗',3000);pets()};
    const au=$('#vcpauto');if(au)au.onchange=async()=>{const r=await api('/api/vc_pet',{a:'auto',on:au.checked});toast(r.message||'',2500)};
    const th=$('#vcpth');if(th)th.onchange=async()=>{const r=await api('/api/vc_pet',{a:'th',v:+th.value});toast((r.message||'')+'：🐶 '+((r.st||{}).dog||0)+'・🐱 '+((r.st||{}).cat||0),2500);pets(r)};
    if(t.run)setTimeout(()=>{if($('#vcpet'))pets()},3000)};pets();
  const rls=async(r)=>{r=r||await api('/api/vc_rules');const el=$('#vcrl');if(!el)return;el.innerHTML=(r.rules||[]).length?r.rules.map((x,i)=>`<span class="pill" style="display:inline-flex;gap:6px;align-items:center;margin:2px;min-height:0;padding:3px 8px">「${esc(x.w)}」→ <b>${esc(x.name)}</b><span data-rl="del" data-i="${i}" style="cursor:pointer;color:var(--red,#f66)">✕</span></span>`).join(''):'還沒有規則'};rls();
  Z.onclick=async e=>{e.stopPropagation();if(e.target.closest('[data-m="x"]')){Z.onclick=null;return vczHide()}{const gg=e.target.closest('[data-go]');if(gg){Z.onclick=null;vczHide();return go(gg.dataset.go)}}
    const lw=e.target.closest('[data-lw]');if(lw){const r=await api('/api/vc_learn',{a:lw.dataset.la,w:lw.dataset.lw});VI.cache={};return learn(r)}
    const cb_=e.target.closest('[data-cby]');if(cb_){VC.cby=cb_.dataset.cby;LS.set('vc',VC);cb_.parentElement.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b===cb_));$('#vccam').textContent='讀取中…';return cams()}
    const jp=e.target.closest('[data-jump]');if(jp){e.preventDefault();const t=$('#'+jp.dataset.jump);if(t)t.parentElement.scrollIntoView({behavior:'smooth',block:'start'});return}
    const cm=e.target.closest('[data-cm]');if(cm){const el=$('#vccam'),r=(el._rows||[])[+cm.dataset.ci];if(!r)return;
      if(cm.dataset.cm==='v'){vczHide();VC.q=(VC.cby==='name'?'檔名:':'相機:')+r.cam;VC.folder='';VC.f='todo';LS.set('vc',VC);VI.ids=[];toast(`📷 只看「${r.cam}」拍的（上面「🔍 相機:… ✕」按一下回去）`,3500);return rVc()}
      const sel=el.querySelector(`[data-cs="${cm.dataset.ci}"]`),cid=+sel.value,c=VI.cats.find(x=>x.id===cid);if(!confirm(`${VC.cby==='name'?'檔名開頭是':''}「${r.cam}」${VC.cby==='name'?'的':'拍的'}、還沒分類的 ${r.n.toLocaleString()} 部，全部分到「${c?c.name:''}」？\n\n只是標記，按 🚚 搬才會搬；分錯可以按 ↶ 復原。`))return;
      const x=await api('/api/vc_cams',{cam:r.cam,cat:cid,k:VC.kind||'video',by:VC.cby||''});toast(x.message||'失敗',3000);if(x.ok&&x.ids){const pv={};x.ids.forEach(id=>pv[id]=0);await vcReCats();await vcList();VI.undo.push(['many',pv,VI.i,c?c.name:''])}return cams()}
    const pt=e.target.closest('[data-pt]');if(pt){const a=pt.dataset.pt;
      if(a==='quick'){vczHide();return vcPQ(true)}
      if(a==='npclr'){const r=await api('/api/vc_pet',{a:'nopet_clear'});return toast(r.message||'好了',2500)}
      if(a==='smp'){vczHide();VC.f='pet';VC.order='pet';VC.g='';LS.set('vc',VC);VI.ids=[];VI.jumpTo=+pt.dataset.id;toast('🐾 只看還沒分類、有貓或狗的，最像的排前面',2500);return rVc()}
      if(a==='sct'){const d=pt.dataset;if(!confirm(`還沒分類、電腦看是「${d.sn}」的 ${(+d.n).toLocaleString()} 部，全部分到「${d.ln}」？\n\n（你以前這種的大多分到這類。電腦會看錯：不放心就先點左邊的按鈕看過一遍。）只是標記，按 🚚 搬才會搬；分錯可以按 ↶ 復原。`))return;
        const r=await api('/api/vc_pet',{a:'tag',cat:+d.lc,kind:'s_'+d.sk,k:VC.kind||'video'});toast(r.message||'失敗',3500);if(r.ok&&r.ids){const pv={};r.ids.forEach(id=>pv[id]=VI.tags[id]||0);await vcReCats();await vcList();VI.undo.push(['many',pv,VI.i,d.ln])}return pets()}
      if(a==='sc'){vczHide();VC.f='pet_s_'+pt.dataset.sk;VC.fsn=pt.dataset.sn;if(pt.dataset.sk.startsWith('pet')){VC.order='pet';VC.g=''}LS.set('vc',VC);VI.ids=[];toast('🔎 只看還沒分類、電腦猜是「'+pt.dataset.sn+'」的：Ctrl＋A 整組勾再按分類，或一部一部看',4000);return rVc()}
      if(a==='vface'){vczHide();VC.f='pet_face';LS.set('vc',VC);VI.ids=[];toast('👤 只看還沒分類、有人臉的（選「🏞 沒有人臉的」看風景）',3500);return rVc()}
      if(a==='view'){vczHide();VC.f='pet';VC.order='pet';VC.g='';LS.set('vc',VC);VI.ids=[];toast('🐾 只看還沒分類、有貓或狗的，最像的排前面：前面的可以整段勾（按住拖過去）分到 Family；按 V 用縮圖牆一次看很多',4500);return rVc()}
      if(a==='tag'){const cid=+$('#vcptc').value;LS.set('pettc',cid);const c=VI.cats.find(x=>x.id===cid);if(!confirm(`還沒分類、有貓或狗的影片，全部分到「${c?c.name:''}」？\n\n建議先按「👀 只看有貓狗的」快速看一遍（電腦會看錯）。只是標記，按 🚚 搬才會搬；分錯可以按 ↶ 復原。`))return;
        const r=await api('/api/vc_pet',{a:'tag',cat:cid,k:VC.kind||'video'});toast(r.message||'失敗',3500);if(r.ok&&r.ids){const pv={};r.ids.forEach(id=>pv[id]=VI.tags[id]||0);await vcReCats();await vcList();VI.undo.push(['many',pv,VI.i,c?c.name:''])}return}
      if(a==='reset'){if(!confirm('清掉之前看的結果，之後全部重新看？'))return;const r=await api('/api/vc_pet',{a:'reset'});toast(r.message||'',2500);return pets()}
      const r=await api('/api/vc_pet',{a:a==='stop'?'stop':'start',limit:a==='test'?20:0,k:VC.kind||'video',ids:a==='only'?VI.ids:undefined});toast(r.message||'',2500);return setTimeout(()=>pets(),600)}
    const rl=e.target.closest('[data-rl]');if(rl){const r=rl.dataset.rl==='add'?await api('/api/vc_rules',{a:'add',w:$('#vcrw').value,cat:+$('#vcrc').value}):await api('/api/vc_rules',{a:'del',i:+rl.dataset.i});if(!r.ok)return toast(r.message||'失敗');if(rl.dataset.rl==='add'){$('#vcrw').value='';toast('📏 加好了：之後有這個字的會建議這類',2500)}VI.cache={};return rls(r)}
    if(e.target.closest('[data-mh]')){toast('💡 算算看…',1500);const d=await api('/api/vc_tag_many',{ids:VI.ids,hint:1,dry:1});if(!d.ok)return toast(d.message||'失敗');if(!d.n)return alert('沒有可以照建議分的\n\n要先自己分好一些，才知道你習慣怎麼分（同資料夾分好 2 部以上，或資料夾名有同一個字的分好 5 部以上）');
      Z.onclick=null;return vcHintPick(d,`這份清單還沒分的 ${nt.toLocaleString()} 部`)}
    const b=e.target.closest('[data-mc]');if(!b)return;
    const cid=+b.dataset.mc,all=$('#vcmAll').checked,c=VI.cats.find(x=>x.id===cid),k=cid?(all?n:nt):VI.ids.filter(i=>VI.tags[i]).length;
    if(!k)return toast('沒有要改的');if(!confirm(cid?`把 ${k.toLocaleString()} 部分到「${c?c.name:''}」？`:`把 ${k.toLocaleString()} 部取消分類？`))return;
    const r=await api('/api/vc_tag_many',{ids:VI.ids,cat:cid,only_new:cid?!all:false});toast(r.message||'失敗');Z.onclick=null;vczHide();await vcReCats();vcList()}}
// ⌨ 滑鼠停在下面某一格＋按數字＝直接把那一格分類，不用點進去（像 Photo Mechanic 的縮圖表）（V0.2.84）
// 💾 還在存的有幾部（電腦慢的時候看得到，存好就消失）（V0.3.35）
function vcSave(d){VI.saving=Math.max(0,(VI.saving||0)+d);let el=$('#vcsave');if(!el){const p=$('#vcpos');if(!p)return;el=document.createElement('span');el.id='vcsave';el.style.cssText='margin-left:6px;font-size:12px;color:var(--orange)';p.after(el)}
  el.textContent=VI.saving>1?`💾 存 ${VI.saving} 部中…`:'';el.title='電腦還在記你剛剛分的；顯示很久的話電腦可能很忙'}
async function vcTagJ(j,ci,quiet){const c=VI.cats[ci],id=VI.ids[j];if(!c||!id)return;const prev=VI.tags[id]||0;
  const redraw=()=>{const S=$('#vcs'),el=S&&S.querySelector(`[data-j="${j}"]`);if(el){const st=S.scrollTop;el.outerHTML=vcStripItem(j,1);S.scrollTop=st}vcMap()};
  VI.undo.push([id,prev,VI.i,c.id,Date.now()]);VI.tags[id]=c.id;delete VI.cache[id];                    // 先記在畫面上（不用等電腦回應，連按也不會亂）（V0.3.34）
  if(prev!==c.id){c.n++;c.wait++;const p=VI.cats.find(x=>x.id===prev);if(p){p.n--;p.wait--}}vcPend();vcBtns();redraw();
  vcSave(1);const r=await api('/api/vc_tag',{id,cat:c.id}).catch(e=>({ok:false,message:'連不到電腦：'+e}));vcSave(-1);
  if(!r.ok){if(VI.tags[id]===c.id){if(prev)VI.tags[id]=prev;else delete VI.tags[id];c.n--;c.wait--;redraw();vcPend();vcBtns()}return toast('⚠ 第 '+(j+1)+' 部沒分成功：'+(r.message||'失敗'),4000)}
  if(!quiet||r.dup)toast(`✔ 第 ${j+1} 部 → ${c.name}`+(r.dup?`（另外 ${r.dup} 個副本標成 Delete）`:''),1300)}
// 💡 小格子上標出「電腦建議分到哪類」（虛線框＋💡）（V0.3.41）：清單讀好後背景算一次
let SUGT=0;function vcSug(){clearTimeout(SUGT);if(VC.f!=='todo'&&!String(VC.f).startsWith('todo')&&!String(VC.f).startsWith('pet'))return;const ids=VI.ids;if(!ids.length||ids.length>30000)return;
  SUGT=setTimeout(async()=>{const d=await api('/api/vc_tag_many',{ids,hint:1,dry:1}).catch(()=>null);if(!d||!d.ok||VI.ids!==ids)return;const S={};(d.rows||[]).forEach(r=>r.ids.forEach(x=>S[x]=r.cid));VI.sug=S;if(Object.keys(S).length)vcStrip()},1500)}
async function vcReCats(){const s=await api('/api/vc_state');VI.cats=s.cats||[];vcFilters();vcBtns();vcPend()}
function vcFsug(){const f=VI.fsug;if(!f||!VI.cats[f.ci])return toast('同一個資料夾連續分 3 部同一類之後才能用',2000);const c=VI.cats[f.ci],ids=f.ids.filter(x=>!VI.tags[x]);if(!ids.length)return toast('都分好了',1500);VI.fsug=null;   // 📁 這個資料夾剩下的全部分同一類（V0.4.06）
  const pv={};ids.forEach(id=>pv[id]=0);(async()=>{const r=await api('/api/vc_tag_many',{ids,cat:c.id,only_new:true});if(!r.ok)return toast(r.message||'失敗');ids.forEach(id=>VI.tags[id]=c.id);VI.undo.push(['many',pv,VI.i,c.name]);toast(`📁 這個資料夾剩下的 ${ids.length.toLocaleString()} 部 → 「${c.name}」（↶ 可以復原）`,3000);VI.cache={};await vcReCats();vcStrip();vcGo(VI.i)})()}
async function vcTag(ci){const c=VI.cats[ci],it=VI.it;if(!c)return;VI.lastCat=ci;try{if(matchMedia('(pointer:coarse)').matches&&navigator.vibrate)navigator.vibrate(8)}catch(_){}   // 手機：輕輕震一下（V0.3.36）
  if(VI.msel&&VI.sel&&VI.sel.size){const ids=[...VI.sel];if(ids.length>300&&!confirm(`勾了 ${ids.length.toLocaleString()} 部，全部分到「${c.name}」？\n\n（只是標記，按 🚚 搬才會搬；分錯可以按 ↶ 復原）`))return;const pv={};ids.forEach(id=>pv[id]=VI.tags[id]||0);const r=await api('/api/vc_tag_many',{ids,cat:c.id,only_new:false});if(!r.ok)return toast(r.message||'失敗');VI.undo.push(['many',pv,VI.i,c.name]);
    ids.forEach(id=>VI.tags[id]=c.id);toast(`✔ 勾選的 ${ids.length} 部 → 「${c.name}」`,2500);VI.msel=false;VI.sel=new Set();VI.lastSel=null;vcSel(0,false);VI.cache={};await vcReCats();vcStrip();return vcGo(VI.i)}
  if(VI.ids[VI.i]&&(!it||it.id!==VI.ids[VI.i])){const j0=VI.i;vcTagJ(j0,ci,true);   // 下一部還在讀（卡卡的時候）：照「現在這一格」分，不會分到上一部去（V0.3.32）
    if(VI.next&&j0<VI.ids.length-1){let j=j0+1;while(j<VI.ids.length&&VI.tags[VI.ids[j]])j++;if(j>=VI.ids.length)j=j0+1;vcGo(j)}return}
  if(!it)return;if(it.moved)return toast('這部已經搬過了');const prev=it.cat||0;
  VI.undo.push([it.id,prev,VI.i,c.id,Date.now()]);const j0=VI.i;
  vcSave(1);api('/api/vc_tag',{id:it.id,cat:c.id,h:!prev&&it.hint?it.hint[0]:0,hk:it.hint?(it.hint[3]||'folder'):''}).catch(e=>({ok:false,message:'連不到電腦：'+e})).then(r=>{vcSave(-1);     // 先換下一部，電腦在背景記（V0.3.34：連按、卡卡的時候不會漏）
    if(!r.ok){if(VI.tags[it.id]===c.id){if(prev)VI.tags[it.id]=prev;else delete VI.tags[it.id];it.cat=prev;c.n--;c.wait--;vcPend();vcBtns();vcStrip()}return toast('⚠ 第 '+(j0+1)+' 部沒分成功：'+(r.message||'失敗')+'（按 N 回去找還沒分的）',5000)}
    if(r.dup)toast(`🗑 另外 ${r.dup} 個一模一樣的副本標成「Delete」（只留這一份）`,2200);
    if(r.sim){VI.simFor=it.id;setTimeout(()=>toast(`👯 這部還有 ${r.sim} 個相似的版本（重新壓縮、轉檔過的）還沒分：按 Shift＋D 把它們標成 Delete`,4500),r.dup?2300:0)}});
  if(!prev){VI.sess=(VI.sess||0)+1;if(!VI.sess0)VI.sess0=Date.now();if(VI.sess%100===0){const sec=(Date.now()-VI.sess0)/1000/VI.sess;setTimeout(()=>toast(`🎉 這次已經分了 ${VI.sess} 部（平均 ${sec.toFixed(1)} 秒一部）`,3000),400)}}   // 每 100 部鼓勵一下（V0.3.50）
  {const d=VI.di?VI.di[j0]:undefined;if(d!==undefined){const st=VI.stk||{};VI.stk=st.d===d&&st.c===c.id?{d,c:c.id,n:st.n+1}:{d,c:c.id,n:1};   // 📁 同資料夾連續 3 部同一類 → 提示 Shift＋F 整個資料夾（V0.4.06）
    if(VI.stk.n===3){const rest=VI.ids.filter((x,k)=>VI.di[k]===d&&!VI.tags[x]&&x!==it.id);if(rest.length>=3){VI.fsug={ids:rest,ci:VI.cats.indexOf(c)};setTimeout(()=>{if(matchMedia('(pointer:coarse)').matches){/* V0.5.73 平板／手機不跳「剩下的也全部分？」視窗（你說不要） */}else toast(`📁 這個資料夾你連續 3 部都分「${c.name}」，還有 ${rest.length.toLocaleString()} 部沒分：按 Shift＋F 全部分「${c.name}」`,5000)},300)}}}}
  if(!prev&&VI.pets&&VI.pets.has(it.id)&&!String(VC.f).startsWith('pet')){const ps=VI.pstk||{};VI.pstk=ps.c===c.id?{c:c.id,n:ps.n+1}:{c:c.id,n:1};   // 🐾 連續 3 部有貓狗的都分同一類 → 提示 Shift＋P（V0.4.48）
    if(VI.pstk.n===3){const rest=VI.ids.filter(x=>VI.pets.has(x)&&!VI.tags[x]&&x!==it.id).length;if(rest>=5)setTimeout(()=>toast(`🐾 你連續 3 部有貓狗的都分「${c.name}」，這份清單還有 ${rest.toLocaleString()} 部有貓狗的沒分：按 Shift＋P 只看那些（最像的排前面，整段勾起來一次分）`,6000),600)}}
  VI.tags[it.id]=c.id;if(!prev&&VI.sp)VI.sp.today=(VI.sp.today||0)+1;if(prev!==c.id){c.n++;c.wait++;c.b=(c.b||0)+(it.size||0);const p=VI.cats.find(x=>x.id===prev);if(p){p.n--;p.wait--;p.b=(p.b||0)-(it.size||0)}}it.cat=c.id;delete VI.cache[it.id];vcPend();
  if(VI.next&&VI.i<VI.ids.length-1){let j=VI.i+1;while(j<VI.ids.length&&VI.tags[VI.ids[j]])j++;if(j>=VI.ids.length)j=VI.i+1;else if(j-VI.i>1)toast(`⏭ 跳過 ${(j-VI.i-1).toLocaleString()} 部已經分好的`,1800);vcGo(j)}else{vcBtns();vcGo(VI.i)}}
// 🕘 剛剛分過的（V0.2.91）：右鍵 ↶ 或按 H。可以挑任何一筆改回去，不用一路復原回去
function vcHist(){const Z=$('#vcz');if(!Z)return;vczShow('block');Z.style.overflow='auto';const cn=id=>{const c=VI.cats.find(x=>x.id===id);return c?`<b style="color:${c.color}">${esc(c.name)}</b>`:'<span class="mu">還沒分</span>'};
  const L=VI.undo.map((u,k)=>[u,k]).reverse().slice(0,80);
  Z.innerHTML=`<div class="panel" style="margin:10px auto;max-width:720px"><div class="row"><h3 class="grow" style="margin:0">🕘 剛剛分過的（${VI.undo.length}）</h3><button class="pill" data-hx="1">關閉</button></div>
   <div class="mu" style="margin:4px 0 8px">最新的在上面。按「改回」只改那一筆，其他的不動。（換清單、換篩選也會留著，最多 500 筆）<button class="pill" data-hsv="1" style="min-height:0;padding:2px 8px;font-size:12px;margin-left:6px" title="重新整理、換手機後也看得到">📜 看電腦記的最近 200 筆</button></div>
   ${L.length?L.map(([u,k])=>u[0]==='many'?`<div class="it row" style="flex-wrap:nowrap;gap:8px"><span style="font-size:22px">☑</span><span class="grow">整批 ${Object.keys(u[1]).length.toLocaleString()} 部 → <b>${esc(u[3]||'')}</b></span><button class="pill" data-hk="${k}">↶ 整批改回</button></div>`
     :`<div class="it row" style="flex-wrap:nowrap;gap:8px"><img src="/api/vc_thumb?id=${u[0]}" style="width:72px;aspect-ratio:16/10;object-fit:cover;border-radius:4px;background:#1a1f27;cursor:pointer" data-hg="${u[0]}"><span class="grow" style="min-width:0">第 ${(VI.ids.indexOf(u[0])+1)||'?'} 部　${cn(u[1])} → ${cn(VI.tags[u[0]]||0)}${u[4]?`<br><span class="mu" style="font-size:11px">${new Date(u[4]).toLocaleTimeString()}</span>`:''}</span><button class="pill" data-hk="${k}">↶ 改回</button></div>`).join(''):'<div class="mu">還沒有</div>'}</div>`;
  Z.onclick=async e=>{e.stopPropagation();if(e.target.closest('[data-hsv]'))return vcRecent();const g=e.target.closest('[data-hg]');if(g){vczHide();const j=VI.ids.indexOf(+g.dataset.hg);return j>=0&&vcGo(j)}
    const h=e.target.closest('[data-hk]');if(h){const k=+h.dataset.hk,u=VI.undo[k];if(!u)return;VI.undo.splice(k,1);VI.undo.push(u);await vcUndo();return vcHist()}
    if(e.target.closest('[data-hx]')||e.target===Z)vczHide()}}
// 📜 電腦記的最近分類（V0.3.60）：重新整理、換手機後也能改回
async function vcRecent(){const Z=$('#vcz');if(!Z)return;const j=await api('/api/vc_recent?n=200');if(!j.ok)return;vczShow('block');Z.style.overflow='auto';const cc=id=>(VI.cats.find(c=>c.id===id)||{}).color||'#888';
  Z.innerHTML=`<div class="panel" style="margin:10px auto;max-width:720px"><div class="row"><h3 class="grow" style="margin:0">📜 電腦記的最近 ${j.rows.length} 筆分類</h3><button class="pill" data-rx="1">關閉</button></div>
   <div class="mu" style="margin:4px 0 8px">不管在哪台手機、電腦分的都在這裡（自動標的副本不列）。「↶ 變回沒分」只改那一筆；已經搬過的要到 📦 隔離區／分類資料夾處理。</div>
   ${j.rows.map(r=>`<div class="it row" style="flex-wrap:nowrap;gap:8px"><img src="/api/vc_thumb?id=${r.id}" style="width:64px;aspect-ratio:16/10;object-fit:cover;border-radius:4px;background:#1a1f27;flex:none" data-rg="${r.id}"><span class="grow" style="min-width:0;overflow:hidden"><b style="color:${cc(r.cat)}">■ ${esc(r.name)}</b>${r.moved?' <span class="mu">（已搬）</span>':''}<br><span class="mu" style="font-size:11.5px;white-space:nowrap">${esc(r.file)}・${day(r.t)}</span></span>${r.moved?'':`<button class="pill" data-ru="${r.id}" style="min-height:0;padding:2px 8px;font-size:12px">↶ 變回沒分</button>`}</div>`).join('')||'<div class="mu">還沒有</div>'}</div>`;
  Z.onclick=async e=>{e.stopPropagation();const u=e.target.closest('[data-ru]');if(u){const id=+u.dataset.ru,prev=VI.tags[id]||0;const r=await api('/api/vc_tag',{id,cat:0});if(!r.ok)return toast(r.message||'失敗');delete VI.tags[id];u.closest('.it').style.opacity=.4;u.remove();toast('↶ 變回沒分了',1200);vcPend();vcStrip();vcMap();return vcReCats()}
    const g=e.target.closest('[data-rg]');if(g){const j2=VI.ids.indexOf(+g.dataset.rg);if(j2>=0){vczHide();return vcGo(j2)}return toast('這部不在現在的清單裡',1500)}
    if(e.target.closest('[data-rx]')||e.target===Z)vczHide()}}
async function vcUndo(){const u=VI.undo.pop();if(!u)return toast('沒有可以復原的');
  if(u[0]==='many'){const by={};Object.entries(u[1]).forEach(([id,c])=>(by[c]=by[c]||[]).push(+id));                       // ↶ 整批勾選分類也能復原（V0.2.73）
    for(const [c,ids] of Object.entries(by)){const r=await api('/api/vc_tag_many',{ids,cat:+c,only_new:false});if(!r.ok)return toast(r.message||'復原失敗')}
    Object.entries(u[1]).forEach(([id,c])=>{if(+c)VI.tags[id]=+c;else delete VI.tags[id]});VI.cache={};await vcReCats();vcStrip();toast(`↶ 復原了剛剛勾選的 ${Object.keys(u[1]).length} 部（→「${u[3]}」）`,2500);return vcGo(u[2])}await api('/api/vc_tag',{id:u[0],cat:u[1]});if(u[1])VI.tags[u[0]]=u[1];else delete VI.tags[u[0]];delete VI.cache[u[0]];await vcReCats();vcGo(VI.ids.indexOf(u[0])>=0?VI.ids.indexOf(u[0]):u[2])}
// 🚚 搬之前可以只勾幾類搬（例如先搬 Delete）（V0.2.90）
function vcMovePick(M){const Z=$('#vcz');if(!Z)return;vczShow('grid');Z.style.overflow='auto';
  Z.innerHTML=`<div class="panel" style="margin:auto;max-width:560px;width:94%"><div class="row"><h3 class="grow" style="margin:0">🚚 搬到各分類的資料夾</h3><button class="pill" data-mp="x">關閉</button></div>
   <div class="mu" style="margin:6px 0">勾要搬的分類（預設全部）。只在同一顆硬碟裡搬；搬錯了在「📦 隔離區」復原。</div><div id="mpsus"></div>
   ${M.map(p=>`<label class="it row" style="flex-wrap:nowrap;gap:8px;align-items:flex-start"><input type="checkbox" data-mpc="${p.id}" checked style="margin-top:3px"><span class="grow" style="min-width:0"><b>${esc(p.name)}</b>：${p.n.toLocaleString()} 部<br><span class="mu" style="font-size:11.5px;word-break:break-all">→ ${esc(p.dest)}</span>${(p.ex||[]).map(x=>`<br><span class="mu" style="font-size:11px;word-break:break-all;opacity:.85">例：${esc(x.src)}<br>　　→ <b style="color:var(--text)">${esc(x.dst)}</b></span>`).join('')}</span></label>`).join('')}
   <div class="row" style="margin-top:10px;gap:6px"><button class="pill" data-mp="all">全選／全不選</button><span class="grow"></span><button class="pill acc" data-mp="go" id="mpgo">🚚 開始搬</button></div></div>`;
  api('/api/vc_sus').then(j=>{const el=$('#mpsus');if(el&&j.ok&&j.n)el.innerHTML=`<div style="margin:4px 0 8px;padding:6px 8px;border-radius:8px;background:#f5a62322;color:#f5a623;font-size:12.5px">🧐 有 ${j.n.toLocaleString()} 部可能分錯了（跟同資料夾、或你平常的分法不一樣）<button class="pill" data-mp="sus" style="min-height:0;padding:2px 8px;font-size:12px;margin-left:6px">先看一下</button></div>`});   // V0.4.33
  const upd=()=>{const ck=[...Z.querySelectorAll('[data-mpc]:checked')],n=ck.reduce((s,c)=>s+(M.find(p=>p.id===+c.dataset.mpc)||{n:0}).n,0);const b=$('#mpgo');if(b){b.textContent=`🚚 開始搬（${ck.length} 類、${n.toLocaleString()} 部）`;b.disabled=!ck.length}};upd();
  Z.onchange=upd;Z.onclick=async e=>{e.stopPropagation();const b=e.target.closest('[data-mp]');if(!b){if(e.target===Z)vczHide();return}const k=b.dataset.mp;
    if(k==='x')return vczHide();if(k==='sus'){vczHide();try{const d=await api('/api/vc_sus?d=1');if(d&&d.ok){if(!d.nv&&d.np)VC.kind='photo';else if(d.nv&&!d.np)VC.kind='video';LS.set('vc',VC)}}catch(e){}return go('vc:chk|🧐 可能分錯的')}if(k==='all'){const C=[...Z.querySelectorAll('[data-mpc]')],on=C.some(c=>!c.checked);C.forEach(c=>c.checked=on);return upd()}
    if(k==='go'){const C=[...Z.querySelectorAll('[data-mpc]')],ck=C.filter(c=>c.checked).map(c=>+c.dataset.mpc);if(!ck.length)return;vczHide();
      const r=await api('/api/vc_run',{a:'move',cats:ck.length===C.length?[]:ck});toast(r.message,3500);if(r.ok){VI.mv.run=true;vcPend()}}}}
async function vcRun(a){const P=await api('/api/vc_plan');if(!P.ok)return;
  if(a==='move'){if(!P.move.length)return toast('還沒有分好的');return vcMovePick(P.move)}
  else{const c=P.clean,n=c.delete.n+c.check.n+c.repeat.n;const t=`• 打不開／0 位元組：${c.delete.n} 部（${fmtB(c.delete.b)}）→ delete\n• 部分損毀：${c.check.n} 部（${fmtB(c.check.b)}）→ check video\n• 重複的（每組留一部，檔名有拍攝日期、修改日期最早的優先）：${c.repeat.n} 部（${fmtB(c.repeat.b)}）→ repeat`
    +(c.unchecked?`\n\n⚠ 還有 ${c.unchecked} 部還沒做完損毀檢查`:'')+(c.unhashed?`\n⚠ 還有 ${c.unhashed} 部還沒比對完重複`:'');
    if(!n)return alert('目前沒有要搬的\n\n'+t);if(!confirm(t+`\n\n搬到每顆硬碟的 \\${c.dir}\\（跟分類分開）。不會刪檔，可以在「📦 隔離區」復原。開始？`))return}
  const r=await api('/api/vc_run',{a});toast(r.message);VI.mv.run=true;vcPend()}
async function vcMgr(){const Z=$('#vcz');vczShow('block');Z.style.overflow='auto';
  const draw=async()=>{const s=await api('/api/vc_state');VI.cats=s.cats||[];Z.innerHTML=`<div class="panel" style="margin:10px"><div class="row"><h3 class="grow">⚙ 管理分類</h3><button class="pill" data-m="x">關閉</button></div>
    <div class="mu">「搬去哪」空著＝影片那顆硬碟的 \\FileCompare_分類\\分類名稱；填「不搬」＝只記下看過、檔案留在原處（例如「已篩選」只想標記）。</div>${VI.cats.map(c=>`<div class="it"><div class="row"><b class="grow" style="color:${c.color}">${esc(c.name)}</b><span class="mu">${c.n} 部（待搬 ${c.wait}）</span></div>
    <div class="mu" style="word-break:break-all">${['不搬','原地','=','stay'].includes((c.dest||'').trim())?'📌 不搬（留在原處，只標記）':esc(c.dest||'（預設）')}</div><div class="row" style="margin-top:4px"><button class="pill" data-m="ren" data-id="${c.id}">✏ 名字</button><button class="pill" data-m="dest" data-id="${c.id}">📁 位置</button>${c.dir?`<button class="pill" data-m="open" data-id="${c.id}">📂 看</button>`:''}
    <button class="pill" data-m="up" data-id="${c.id}">↑</button><button class="pill" data-m="dn" data-id="${c.id}">↓</button><button class="pill" data-m="merge" data-id="${c.id}" title="把這類併到另一類（還沒搬的都改過去）">🔀 併到…</button><button class="pill er" data-m="del" data-id="${c.id}">🗑</button></div></div>`).join('')}
    <div class="mu" style="margin-top:8px">SortCut：${s.vs&&s.vs.db?esc(s.vs.db)+`（${s.vs.n} 部有預覽）`:'沒找到（改用 FFmpeg 自己抓 16 格；要指定位置請在電腦上設定）'}</div></div>`};
  Z.onclick=async e=>{const b=e.target.closest('[data-m]');if(!b)return;e.stopPropagation();const m=b.dataset.m,id=+b.dataset.id,c=VI.cats.find(x=>x.id===id);let r;
    if(m==='x'){vczHide();vcFilters();vcBtns();vcPend();return}
    if(m==='ren'){const n=prompt('新的名字',c.name);if(!n)return;r=await api('/api/vc_cat',{a:'edit',id,name:n})}
    if(m==='dest'){const n=prompt('搬去哪（同一顆硬碟的資料夾，例如 R:\\影片\\工作；空的＝預設；填「不搬」＝留在原處只標記）',c.dest||'');if(n===null)return;r=await api('/api/vc_cat',{a:'edit',id,dest:n})}
    if(m==='open'){vczHide();BRP=c.dir;BRO=0;LS.set('brp',BRP);return setTimeout(()=>go('tool:br'),350)}
    if(m==='up'||m==='dn')r=await api('/api/vc_cat',{a:'move',id,d:m==='up'?-1:1});
    if(m==='del'){if(!confirm(`刪掉「${c.name}」？還沒搬的 ${c.wait} 部會變回沒分類。`))return;r=await api('/api/vc_cat',{a:'del',id})}
    if(m==='merge'){const O=VI.cats.filter(x=>x.id!==id);const nm=prompt(`把「${c.name}」（還沒搬的 ${c.wait} 部）併到哪一類？輸入名字：\n${O.map(x=>x.name).join('、')}`);if(!nm)return;const t=O.find(x=>x.name===nm.trim());if(!t)return toast('沒有這個分類');if(!confirm(`「${c.name}」還沒搬的 ${c.wait} 部改成「${t.name}」，規則也一起改？`))return;r=await api('/api/vc_cat',{a:'merge',id,to:t.id});VI.cache={}}
    if(r&&r.message)toast(r.message);draw()};draw()}

let SW=[0,0];
function vcFit(){const F=$('#vcf'),H=$('header');if(!F||!H)return;const pc=document.body.classList.contains('pc'),z=+LS.get('fz',1)||1;F.style.zoom=z===1?'':1/z;   // 分類頁有自己的大小（拉把），不跟著「字的大小」放大
  F.style.top=(pc?0:H.getBoundingClientRect().bottom)+'px';F.style.left=(pc?H.getBoundingClientRect().width:0)+'px'}
const vczReal=()=>{const Z=$('#vcz');if(Z){Z.style.display='none';Z.onclick=null;Z.onpointerdown=Z.onpointermove=Z.onpointerup=Z.onwheel=Z.onchange=null;Z.innerHTML=''}};
function vczShow(d){const Z=$('#vcz');if(!Z)return;if(Z.style.display==='none'||!Z.style.display)ovOpen(vczReal);Z.style.display=d}
function vczHide(){const Z=$('#vcz');if(Z&&Z.style.display!=='none')ovClose(vczReal)}
// 長按分類按鈕：拖到想要的位置放開＝調整順序（一下下＝照常分類）
let LP=null;
function vcLpDown(e){VI.lastPT=e.pointerType;const b=e.target.closest('#vcb [data-c]');if(!b)return;if(LP&&LP.t)clearTimeout(LP.t);const x0=e.clientX,y0=e.clientY,el=$('#vcb');
  LP={i:+b.dataset.c,j:+b.dataset.c,drag:false,done:false};
  LP.t=setTimeout(()=>{if(!LP)return;LP.drag=true;try{b.setPointerCapture(e.pointerId)}catch(x){}b.style.transform='scale(1.08)';b.style.boxShadow='0 6px 18px rgba(0,0,0,.55)';b.style.zIndex=3;b.style.position='relative';try{navigator.vibrate&&navigator.vibrate(25)}catch(x){}toast('拖到想要的位置放開',1500)},450);
  const mv=ev=>{if(!LP)return;if(!LP.drag){if(Math.hypot(ev.clientX-x0,ev.clientY-y0)>10){clearTimeout(LP.t);end(null)}return}ev.preventDefault();
    b.style.transform=`translate(${ev.clientX-x0}px,${ev.clientY-y0}px) scale(1.08)`;b.style.pointerEvents='none';
    const t=document.elementFromPoint(ev.clientX,ev.clientY);const tb=t&&t.closest('#vcb [data-c]');$$('#vcb [data-c]').forEach(x=>x.style.outline='');
    if(tb&&tb!==b){LP.j=+tb.dataset.c;tb.style.outline='2px dashed #fff'}};
  const end=async ev=>{el.removeEventListener('pointermove',mv);el.removeEventListener('pointerup',end);el.removeEventListener('pointercancel',end);if(!LP)return;clearTimeout(LP.t);
    if(!LP.drag){if(ev===null)LP=null;return}LP.done=true;const {i,j}=LP;setTimeout(()=>{LP=null},350);
    if(j!==i){const c=VI.cats.splice(i,1)[0];VI.cats.splice(j,0,c);const r=await api('/api/vc_cat',{a:'order',ids:VI.cats.map(x=>x.id)});toast(r.message||'✔ 順序改好了')}vcBtns()};
  el.addEventListener('pointermove',mv,{passive:false});el.addEventListener('pointerup',end);el.addEventListener('pointercancel',end)}
function vcStripItem(j,nh){const id=VI.ids[j],t=VI.tags[id],c=t&&VI.cats.find(x=>x.id===t),cur=j===VI.i,sel=VI.msel&&VI.sel&&VI.sel.has(id),sg=!t&&VI.sug&&VI.sug[id],sc=sg&&VI.cats.find(x=>x.id===sg);
  const ps=(VI.st||[])[j],gs=!nh&&VI.gn&&VI.gn.length&&(j===0||j===SW[0]||VI.gi[j]!==VI.gi[j-1]);
  return `${gs?`<div data-gh="${j}" title="點一下：整組勾起來（再點一次取消）" style="flex:0 0 100%;font-size:10.5px;color:var(--accent);font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:${j?4:0}px;cursor:pointer">▸ ${esc(VI.gn[VI.gi[j]]||'')} <span style="opacity:.7;font-weight:600">${(()=>{const [a,z]=vcGrpRange(j),n=z-a+1;let t=0,pn=0;for(let k=a;k<=z;k++){if(!VI.tags[VI.ids[k]])t++;if(VI.pets&&VI.pets.has(VI.ids[k]))pn++}return (t?`待分 ${t.toLocaleString()}／${n.toLocaleString()}`:`✔ 全部分好（${n.toLocaleString()}）`)+(pn?`・🐾 ${pn}`:'')})()}・☑ 整組選</span></div>`:''}<div data-j="${j}" style="flex:0 0 calc((100% - ${(vcCols()-1)*3}px) / ${vcCols()});min-width:0;position:relative;border-radius:4px;overflow:hidden;border-left:4px ${sc&&!c?'dashed':'solid'} ${c?c.color:sc?sc.color:'transparent'};${sel?'outline:3px solid var(--orange);outline-offset:-3px;':cur?'outline:2px solid var(--blue);outline-offset:-2px;':c?'box-shadow:inset 0 0 0 2px var(--green);':''}opacity:${VI.msel||cur||c||j>VI.i?1:.5};cursor:pointer">${sel?'<span style="position:absolute;right:3px;bottom:16px;z-index:1;background:var(--orange);color:#000;border-radius:50%;width:18px;height:18px;display:grid;place-items:center;font-size:12px;font-weight:900">✓</span>':''}
   <div style="width:100%;padding-top:62.5%;position:relative;background:#1a1f27"><img loading="lazy" draggable="false" src="/api/vc_thumb?id=${id}${VC.big?'&w=320':''}${vcPT()}" style="-webkit-touch-callout:none;pointer-events:none;position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block" onerror="this.style.visibility='hidden'"></div>
   <span style="position:absolute;left:2px;top:0;font-size:9px;color:#fff;text-shadow:0 0 3px #000,0 0 2px #000">${j+1}${ps===1?' ⏳':ps===2?' ⚠':''}${VI.pets&&VI.pets.has(id)?' 🐾':''}${VI.dark&&VI.dark.has(id)?'<span title="電腦看：全黑／沒東西／沒動（可能是誤錄）"> 🌑</span>':''}${VI.sus&&VI.sus.has(id)?'<span title="可能分錯了（點進去看原因）"> 🧐</span>':''}${sc?` <span title="💡 建議：${esc(sc.name)}" style="color:${sc.color}">💡</span>`:''}</span>${c?'<span style="position:absolute;left:50%;top:50%;transform:translate(-50%,-62%);width:20px;height:20px;border-radius:50%;background:var(--green);color:#06210f;font-size:13px;font-weight:900;display:grid;place-items:center;box-shadow:0 1px 4px #000a">✔</span>':''}${c?`<span style="position:absolute;right:1px;top:1px;font-size:9px;color:#fff;background:${c.color};padding:0 3px;border-radius:3px;max-width:62%;overflow:hidden;white-space:nowrap">${esc(c.name)}</span>`:''}
   <div style="position:absolute;left:0;right:0;bottom:0;background:linear-gradient(transparent,#000b 45%);color:#fff;font-size:9.5px;line-height:1.2;padding:4px 3px 1px;text-shadow:0 0 2px #000;display:flex;justify-content:space-between;gap:2px;white-space:nowrap"><span>${VC.kind==='photo'?'':fmtT(VI.durs[j])}</span><span style="opacity:.85">${mb1(VI.sizes[j])}</span></div></div>`}
const mb1=b=>{b=+b||0;return b>=1e9?(b/1e9).toFixed(1)+'G':(b/1e6).toFixed(1)+'M'};
const gbI=b=>{b=+b||0;return b>0&&b<0.5e9?'<1 GB':Math.round(b/1e9)+' GB'};
// 下面小格子一列幾則（V0.2.69）：照視窗大小自動算，大約看得到 3～4 列
function vcCols(){if(VI.scol)return VI.scol;const S=$('#vcs');if(!S||!S.clientWidth)return innerWidth>=600?6:4;const W=S.clientWidth-10,H=Math.max(60,S.clientHeight);
  if(VC.big){let c=Math.round(W/230)+(+VC.cadj||0);c=Math.max(2,Math.min(16,c));VI.scol=c;return c}
  if(!(VC.cellw>40)){const c0=Math.max(2,Math.min(16,Math.round(W*0.625*3.5/H)));VC.cellw=Math.round(W/c0);LS.set('vc',VC)}   // V0.5.75 記住現在一格的大小：以後拉中間那條只多／少幾排，格子不變大小
  let c=Math.round(W/VC.cellw)+(+VC.cadj||0);c=Math.max(2,Math.min(16,c));VI.scol=c;return c}
function vcSel(id,on){if(id){if(on)VI.sel.add(id);else VI.sel.delete(id)}const S_=$('#vcs');if(S_)S_.style.touchAction=VI.msel?'none':'';vcMbar();if(VI.pq&&$('#vcpqb'))clearTimeout(VI.pqbT),VI.pqbT=setTimeout(vcPQBar,80);const b=document.querySelector('[data-a="msel"]');if(b){b.classList.toggle('acc',!!VI.msel);b.textContent=VI.msel&&VI.sel&&VI.sel.size?'☑ '+VI.sel.size:'☑'}}
function vcGrpR(j){if(!(VI.gn&&VI.gn.length))return [0,VI.ids.length-1];const r=vcGrpRange(j);return [r[0],r[1]]}
function vcSelRange(a,z,why){const ids=VI.ids.slice(a,z+1);if(!ids.length)return;if(!VI.msel){VI.msel=true;VI.sel=new Set()}
  const all=ids.every(id=>VI.sel.has(id));ids.forEach(id=>vcSel(id,!all));vcSel(0,false);VI.lastSel=z;vcStrip();
  toast(all?`☐ ${why}取消了 ${ids.length.toLocaleString()} 部（共選 ${VI.sel.size.toLocaleString()} 部）`:`☑ ${why}${ids.length.toLocaleString()} 部（共選 ${VI.sel.size.toLocaleString()} 部），按右邊的分類一次套用`,2500)}
// ☑ 勾選中的工具列（V0.2.72）：選了幾部、整組／反選／只留沒分的／取消
function vcMbar(){const f=$('#vcf');if(!f)return;let b=$('#vcmb');
  if(!VI.msel){if(b)b.remove();return}
  if(!b){b=document.createElement('div');b.id='vcmb';b.style.cssText='position:absolute;left:50%;transform:translateX(-50%);bottom:calc(58px + env(safe-area-inset-bottom,0px));z-index:4;display:flex;gap:5px;align-items:center;background:#1c2430f2;border:1px solid var(--orange);border-radius:12px;padding:5px 8px;box-shadow:0 6px 24px #0008;max-width:96%;flex-wrap:wrap;justify-content:center';f.appendChild(b);
    b.onclick=e=>{e.stopPropagation();const x=e.target.closest('[data-mb]');if(!x)return;const k=x.dataset.mb,[a,z]=vcGrpR(VI.i);
      if(k==='x'){vcMselOff();return toast('取消勾選',1200)}
      if(k==='grp'){const L=VI.ids.slice(a,z+1);L.forEach(id=>VI.sel.add(id))}
      if(k==='inv'){for(let q=a;q<=z;q++){const id=VI.ids[q];VI.sel.has(id)?VI.sel.delete(id):VI.sel.add(id)}}
      if(k==='todo'){[...VI.sel].forEach(id=>{if(VI.tags[id])VI.sel.delete(id)})}
      if(k==='play'){const id=[...VI.sel][0];if(id){const j=VI.ids.indexOf(id);if(j>=0)vcGo(j)}return}
      if(k==='cmp')return vcCompare([...VI.sel].sort((p,q)=>VI.ids.indexOf(p)-VI.ids.indexOf(q)).slice(0,8));
      vcSel(0,false);vcStrip()}}
  const n=VI.sel.size,dn=[...VI.sel].filter(id=>VI.tags[id]).length,g=VI.gn&&VI.gn.length;
  b.innerHTML=`<b style="color:var(--orange);white-space:nowrap">☑ 已選 ${n.toLocaleString()} 部</b>${dn?`<span class="mu" style="font-size:11px">（${dn} 部已分過）</span>`:''}<span class="mu" style="font-size:11.5px;white-space:nowrap">→ 按分類一次套用</span>
    <button class="pill" data-mb="grp" style="min-height:0;padding:3px 8px;font-size:12px">${g?'整組選':'全選'}</button><button class="pill" data-mb="inv" style="min-height:0;padding:3px 8px;font-size:12px">${g?'這組反選':'反選'}</button>${dn?'<button class="pill" data-mb="todo" style="min-height:0;padding:3px 8px;font-size:12px">只留沒分的</button>':''}${n?'<button class="pill" data-mb="play" style="min-height:0;padding:3px 8px;font-size:12px">看第一部</button>':''}${n>=2?`<button class="pill" data-mb="cmp" style="min-height:0;padding:3px 8px;font-size:12px" title="勾的（最多 8 部）16 格上下排在一起比">🔍 並排比較</button>`:''}<button class="pill" data-mb="x" style="min-height:0;padding:3px 8px;font-size:12px">✖ 取消</button>`}
// 🔍 並排比較（V0.2.81）：勾的幾部 16 格上下排，一眼看出哪部是重複、哪部最好
async function vcCompare(ids){const Z=$('#vcz');if(!Z||!ids.length)return;vczShow('block');Z.style.overflow='auto';Z.innerHTML='<div class="panel" style="margin:10px">讀取中…</div>';
  const G=await Promise.all(ids.map(id=>(SCRUB[id]||(SCRUB[id]=fetch(`/api/vc_cells?id=${id}`).then(r=>r.json()).catch(()=>({ok:false})))))),bp=(x,n)=>n>1?x/(n-1)*100:0;
  const row=(id,g)=>{const j=VI.ids.indexOf(id),c=VI.cats.find(x=>x.id===VI.tags[id]);
    const cells=g&&g.ok?g.cells.map(cl=>`<div style="aspect-ratio:16/10;background:#111 url('/api/vc_img?id=${id}&s=${cl.s}') no-repeat;background-size:${g.cols*100}% ${g.rows*100}%;background-position:${bp(cl.c,g.cols)}% ${bp(cl.r,g.rows)}%"></div>`).join(''):`<img src="/api/vc_thumb?id=${id}" style="grid-column:span 2;width:100%;aspect-ratio:16/10;object-fit:cover"><span class="mu" style="grid-column:span 6;align-self:center;padding-left:8px">16 格還沒做好</span>`;
    return `<div class="panel" style="margin:6px 0;padding:6px"><div class="row" style="flex-wrap:nowrap;gap:6px;font-size:12.5px"><b style="white-space:nowrap">${j+1}</b><span class="grow" style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c?`<b style="color:${c.color}">■ ${esc(c.name)}</b> `:''}${VC.kind==='photo'?'':fmtT(VI.durs[j])+'・'}${fmtB(VI.sizes[j])}</span><button class="pill" data-cg="${j}" style="min-height:0;padding:2px 8px;font-size:12px">看這部</button><button class="pill" data-cu="${id}" style="min-height:0;padding:2px 8px;font-size:12px" title="不勾這部">☐</button></div>
      <div style="display:grid;grid-template-columns:repeat(${innerWidth<600?4:8},1fr);gap:2px;margin-top:4px">${cells}</div></div>`};
  Z.innerHTML=`<div style="max-width:1200px;margin:0 auto;padding:8px"><div class="row" style="position:sticky;top:0;background:#000e;padding:6px 0;z-index:2"><b class="grow" style="color:#fff">🔍 並排比較 ${ids.length} 部</b><span class="mu" style="font-size:12px">☐＝不勾那部；關掉後按右邊的分類＝勾的全部套用</span><button class="pill" data-cx="1">關閉</button></div>${ids.map((id,k)=>row(id,G[k])).join('')}</div>`;
  Z.onclick=e=>{e.stopPropagation();const g=e.target.closest('[data-cg]');if(g){vczHide();return vcGo(+g.dataset.cg)}
    const u=e.target.closest('[data-cu]');if(u){vcSel(+u.dataset.cu,false);vcStrip();u.closest('.panel').remove();return}
    if(e.target.closest('[data-cx]')||e.target===Z)vczHide()}}
// 💡 照建議分：每一條建議分開勾，勾的才分（V0.3.26）
function vcHintPick(d,label){const Z=$('#vcz');if(!Z)return;vczShow('block');Z.style.overflow='auto';const R=d.rows||[];
  Z.innerHTML=`<div class="panel" style="margin:10px auto;max-width:640px"><div class="row"><h3 class="grow" style="margin:0">💡 照建議分</h3><button class="pill" data-hp="x">關閉</button></div>
   <div class="mu" style="margin:4px 0 8px">${esc(label)}裡，有 ${d.n.toLocaleString()} 部有建議。勾你同意的（預設全勾），按「分」；只是標記，按 🚚 搬 才會搬，分錯可以 ↶。</div>
   ${R.map((r,i)=>`<label class="it row" style="flex-wrap:nowrap;gap:8px"><input type="checkbox" data-hpi="${i}" checked><span class="grow" style="min-width:0"><b>${esc(r.cat)}</b>：${r.n.toLocaleString()} 部<br><span class="mu" style="font-size:12px">${esc(r.why)}</span>${r.acc!=null?` <span style="font-size:11.5px;color:${r.acc>=90?'var(--green)':r.acc>=70?'var(--text)':'#f88'}" title="這種建議以前你照著分的比例">📈 ${r.acc}%</span>`:''}</span><button class="pill" data-hpv="${i}" style="min-height:0;padding:2px 8px;font-size:12px" title="先看這幾部">👀 看</button></label>`).join('')}
   <div class="row" style="margin-top:10px;gap:6px"><button class="pill" data-hp="all">全選／全不選</button>${R.some(r=>r.acc!=null)?'<button class="pill" data-hp="hi" title="只勾以前你照著分九成以上的那幾種">📈 只勾準的（90%↑）</button>':''}<span class="grow"></span><button class="pill acc" data-hp="go" id="hpgo">分</button></div></div>`;
  const upd=()=>{const ck=[...Z.querySelectorAll('[data-hpi]:checked')].map(c=>R[+c.dataset.hpi]),n=ck.reduce((s,r)=>s+r.n,0);const b=$('#hpgo');if(b){b.textContent=`分（${ck.length} 條、${n.toLocaleString()} 部）`;b.disabled=!ck.length}};upd();Z.onchange=upd;
  Z.onclick=async e=>{e.stopPropagation();const v=e.target.closest('[data-hpv]');if(v){e.preventDefault();const r=R[+v.dataset.hpv];vczHide();VI.msel=true;VI.sel=new Set(r.ids);vcSel(0,false);const j=VI.ids.indexOf(r.ids[0]);if(j>=0)vcGo(j);vcStrip();return toast(`☑ 勾好「${r.cat}」那 ${r.n} 部了：看一下，沒問題就按 ${r.cat}`,4000)}
    const b=e.target.closest('[data-hp]');if(!b){if(e.target===Z)vczHide();return}const k=b.dataset.hp;if(k==='x')return vczHide();
    if(k==='all'){const C=[...Z.querySelectorAll('[data-hpi]')],on=C.some(c=>!c.checked);C.forEach(c=>c.checked=on);return upd()}
    if(k==='hi'){Z.querySelectorAll('[data-hpi]').forEach(c=>{const r=R[+c.dataset.hpi];c.checked=r.acc!=null&&r.acc>=90});return upd()}   // V0.4.47
    if(k==='go'){const ck=[...Z.querySelectorAll('[data-hpi]:checked')].map(c=>R[+c.dataset.hpi]);if(!ck.length)return;b.disabled=true;const pv={};let n=0;
      for(const r of ck){const x=await api('/api/vc_tag_many',{ids:r.ids,cat:r.cid,only_new:true});if(x.ok){n+=r.ids.length;r.ids.forEach(id=>{pv[id]=0;VI.tags[id]=r.cid})}}
      vczHide();toast(`✔ 照建議分好 ${n.toLocaleString()} 部`,3000);await vcReCats();vcStrip();vcMap();VI.undo.push(['many',pv,VI.i,'照建議']);vcGo(VI.i)}}}
// 🔖 存好的檢視（V0.3.52）：像 Lightroom 的「智慧收藏」，篩選＋分組＋排序＋搜尋＋資料夾一起存
const VKEYS=['f','g','order','q','folder','ln','kind','big','fsn'];
function vcViewDesc(v){const F={todo:'還沒分類',all:'全部',wait:'分好待搬',done:'已搬',todo_sug:'💡 有建議',pet:'🐾 有貓狗',pet_face:'👤 有人',pet_noface:'🏞 沒有人'};
  return [F[v.f]||(String(v.f).startsWith('pet_s_')?'🔎 '+(v.fsn||'內容'):String(v.f).startsWith('c')?'只看某一類':v.f),v.g?GICON[v.g]+'分組':'',v.q?'🔍 '+v.q:'',v.folder?'📁 '+String(v.folder).split(/[\\/]/).pop():'',v.kind==='photo'?'📷 照片':'',v.big?'🔲':''].filter(Boolean).join('・')}
function vcViews(){const Z=$('#vcz');if(!Z)return;vczShow('block');Z.style.overflow='auto';const L=LS.get('vcviews',[]);
  Z.innerHTML=`<div class="panel" style="margin:10px auto;max-width:560px"><div class="row"><h3 class="grow" style="margin:0">🔖 存好的檢視</h3><button class="pill" data-vw="x">關閉</button></div>
   <div class="mu" style="margin:4px 0 8px">現在：${esc(vcViewDesc(VC))}</div><div class="row" style="gap:6px;flex-wrap:nowrap"><input id="vwn" placeholder="取個名字（例如：日本旅遊 有建議的）" style="flex:1;min-width:0"><button class="pill acc" data-vw="save">＋ 存現在這個</button></div>
   <div style="margin-top:10px">${L.length?L.map((v,i)=>`<div class="it row" style="flex-wrap:nowrap;gap:8px"><span class="grow" style="min-width:0;cursor:pointer" data-vl="${i}"><b>${esc(v.name)}</b><br><span class="mu" style="font-size:12px">${esc(vcViewDesc(v))}</span></span><button class="pill" data-vl="${i}">打開</button><button class="pill" data-vd="${i}" title="刪掉這個">✕</button></div>`).join(''):'<div class="mu">還沒有存過</div>'}</div></div>`;
  Z.onclick=e=>{e.stopPropagation();const L=LS.get('vcviews',[]);const l=e.target.closest('[data-vl]');if(l){const v=L[+l.dataset.vl];if(!v)return;VKEYS.forEach(k=>VC[k]=v[k]);LS.set('vc',VC);VI.ids=[];vczHide();toast('🔖 '+v.name,1500);return rVc()}
    const d=e.target.closest('[data-vd]');if(d){L.splice(+d.dataset.vd,1);LS.set('vcviews',L);return vcViews()}
    const b=e.target.closest('[data-vw]');if(!b){if(e.target===Z)vczHide();return}if(b.dataset.vw==='x')return vczHide();
    if(b.dataset.vw==='save'){const nm=($('#vwn').value||'').trim()||vcViewDesc(VC);const v={name:nm};VKEYS.forEach(k=>v[k]=VC[k]);L.unshift(v);LS.set('vcviews',L.slice(0,30));toast('🔖 存好了',1500);return vcViews()}}}
// ⌨ 快捷鍵一覽（V0.2.72）：按 ? 叫出來
function vcKeys(){const Z=$('#vcz');if(!Z)return;vczShow('grid');Z.style.overflow='auto';const K=[['1～9、0','分到第 1～10 類'],['Shift＋1～9、0','分到第 11～20 類'],['→ 或 空白鍵','下一部（不分類）'],['←','上一部'],['Backspace 或 Ctrl＋Z','復原剛剛的分類'],['Shift＋F','同一個資料夾連續分 3 部同一類後：剩下的全部分那類'],['Shift＋P','只看還沒分、有貓狗的（最像的排前面）'],['Enter','用電腦的播放器播'],[']／[','跳到下一組／上一組'],['G','這一組一次看（整組一覽）'],
  ['長按／右鍵 一格','開始勾選'],['按住拖過去','照順序整段勾起來（從勾好的開始拖＝取消那一段）'],['Shift＋點','勾一整段'],['Shift＋方向鍵','從目前這部一路勾'],['Ctrl＋A','這一組全部勾起來'],['點組名 ▸','整組勾／取消'],['Esc','取消勾選'],['滑鼠滑過小格子','快速翻那部的 16 格'],['Ctrl＋滾輪（在小格子上）','小格子放大縮小（一列幾格）'],['滑鼠停在小格子上＋數字','直接把那一格分類（不用點進去）'],['/','🔍 找檔名／資料夾名'],['N／P','下一部／上一部「還沒分的」（跳過分好的）'],['V','🔲 縮圖牆（整個畫面都是小格子）'],['A','照 💡 建議的那類分（勾選中＝勾的全部）'],['Shift＋A','勾起來所有「建議同一類」的'],['R','跟上一部分到同一類'],['T','勾／取消這一部，然後往下（鍵盤一路勾）'],['Shift＋D','剛剛分的那部的「相似版本」（重新壓縮、轉檔過的）標成 Delete（要先跑過 🎬 相似影片）'],['H','🕘 剛剛分過的（挑一筆改回）'],['右鍵 分類按鈕','只看分到那一類的（再按一次回去）'],['?','這個說明']];
  Z.innerHTML=`<div class="panel" style="margin:auto;max-width:520px;width:94%"><div class="row"><h3 class="grow" style="margin:0">⌨ 快捷鍵</h3><button class="pill">關閉</button></div>
   <table style="width:100%;margin-top:8px;border-collapse:collapse;font-size:13px">${K.map(([a,b])=>`<tr><td style="padding:4px 8px;white-space:nowrap"><b style="background:#2a3442;border-radius:5px;padding:1px 7px">${esc(a)}</b></td><td style="padding:4px 8px">${esc(b)}</td></tr>`).join('')}</table></div>`;
  Z.onclick=e=>{e.stopPropagation();vczHide()}}
// ⚡🐾 快速審（V0.6.00）：只看還沒分類、最像貓狗的，縮圖牆一頁一頁；整頁先勾好，你把不是的點掉 → Enter：勾的分到選好的類、沒勾的標「不是貓狗」→ 下一頁
function vcPQ(on){if(!on){VI.pq=false;const b=$('#vcpqb');if(b)b.remove();vcMselOff();return}VI.pq=true;VI.pqU=null;VC.f='pet';VC.order='pet';VC.g='';VC.big=true;LS.set('vc',VC);VI.ids=[];toast('⚡🐾 快速審：整頁先勾好 → 把不是的點掉（可以按住拖過去框選）→ Enter 分好、下一頁',4500);return rVc()}
function vcPQN(){const c=vcCols();const S=$('#vcs');const h=(S?S.clientHeight:innerHeight*.7)-95;const w=S?S.clientWidth/c:120;return Math.max(c*2,Math.min(200,c*Math.max(2,Math.floor(h/(w*.62+3)))))}
function vcPQCat(){const L=VI.cats||[];const v=LS.get('pettc',0);return L.find(c=>c.id===v)||L.find(c=>/family|家/i.test(c.name))||L[0]}
function vcPQPage(){if(!VI.pq)return;const N=vcPQN(),pg=VI.ids.filter(x=>!VI.tags[x]).slice(0,N);VI.pqPage=pg;VI.msel=true;VI.sel=new Set(pg);VI.lastSel=null;VI.i=0;vcSel(0,false);vcStrip();const S=$('#vcs');if(S)S.scrollTop=0;vcPQBar()}
function vcPQBar(){let b=$('#vcpqb');if(!VI.pq){if(b)b.remove();return}if(!b){b=document.createElement('div');b.id='vcpqb';document.body.appendChild(b);
    b.onclick=async e=>{const t=e.target.closest('[data-q]');if(!t)return;const q=t.dataset.q;if(q==='go')return vcPQApply(false);if(q==='none')return vcPQApply(true);if(q==='all'){VI.sel=new Set(VI.pqPage||[]);vcSel(0,false);vcStrip();return vcPQBar()}if(q==='undo')return vcPQUndo();if(q==='x')return vcPQ(false)};
    b.onchange=e=>{if(e.target.id==='vcpqc'){LS.set('pettc',+e.target.value);vcPQBar()}}}
  const P=VI.pqPage||[],n=P.filter(x=>VI.sel&&VI.sel.has(x)).length,c=vcPQCat(),left=VI.ids.filter(x=>!VI.tags[x]).length;
  b.innerHTML=`<div class="pqh"><b>⚡🐾 快速審</b><span>這頁 ${P.length} 部・<b style="color:var(--orange)">勾 ${n}</b>・不是 ${P.length-n}　<span class="mu">還有 ${left.toLocaleString()} 部${VI.pqDone?`・這次分了 ${VI.pqDone.toLocaleString()}`:''}${VI.pqT0&&VI.pqDone>20?`・約 ${Math.round(VI.pqDone/((Date.now()-VI.pqT0)/3600000)).toLocaleString()} 部／小時`:''}</span></span></div>
   <div class="pqr"><label>勾的 →<select id="vcpqc">${(VI.cats||[]).map(x=>`<option value="${x.id}"${c&&x.id===c.id?' selected':''}>${esc(x.name)}</option>`).join('')}</select></label>
   <button class="pill acc" data-q="go" title="Enter">✔ 分好、下一頁 <small>Enter</small></button><button class="pill" data-q="none" title="X：這頁全部都不是貓狗">🚫 這頁都不是 <small>X</small></button><button class="pill" data-q="all" title="A：這頁全部勾回來">☑ 全勾 <small>A</small></button>${VI.pqU?'<button class="pill" data-q="undo" title="Z：上一頁復原">↶ <small>Z</small></button>':''}<button class="pill" data-q="x">✕ 結束</button></div>`}
async function vcPQApply(none){const P=VI.pqPage||[];if(!P.length){toast('沒有了 🎉',2000);return}const c=vcPQCat();const yes=none?[]:P.filter(x=>VI.sel.has(x)),no=P.filter(x=>!yes.includes(x));
  if(yes.length&&!c)return toast('先選要分到哪一類');
  if(yes.length){const r=await api('/api/vc_tag_many',{ids:yes,cat:c.id,only_new:false});if(!r.ok)return toast(r.message||'失敗');yes.forEach(x=>VI.tags[x]=c.id)}
  if(no.length){const r=await api('/api/vc_pet',{a:'nopet',ids:no});if(!r.ok)toast(r.message||'標「不是貓狗」失敗')}
  VI.pqU={yes,no,cat:c&&c.id};VI.pqDone=(VI.pqDone||0)+P.length;VI.pqT0=VI.pqT0||Date.now();const D=new Set(P);VI.ids=VI.ids.filter(x=>!D.has(x));VI.cache={};
  toast(`✔ ${yes.length} 部 → ${c?c.name:''}${no.length?`・🚫 ${no.length} 部不是貓狗`:''}`,1500);try{await vcReCats()}catch(e){}if(!VI.ids.length){vcPQBar();return toast('🎉 有貓狗的都審完了',3000)}vcPQPage()}
async function vcPQUndo(){const U=VI.pqU;if(!U)return;VI.pqU=null;if(U.yes.length)await api('/api/vc_tag_many',{ids:U.yes,cat:0,only_new:false});if(U.no.length)await api('/api/vc_pet',{a:'nopet',ids:U.no,on:false});U.yes.forEach(x=>delete VI.tags[x]);VI.pqDone=Math.max(0,(VI.pqDone||0)-U.yes.length-U.no.length);VI.ids=[...U.yes,...U.no,...VI.ids];toast('↶ 上一頁復原了',1500);vcPQPage()}
function vcPQKey(e){if(e.ctrlKey||e.metaKey||e.altKey)return false;const k=e.key;if(k==='Enter'){e.preventDefault();vcPQApply(false);return true}if(k==='x'||k==='X'){e.preventDefault();vcPQApply(true);return true}if(k==='a'||k==='A'){e.preventDefault();VI.sel=new Set(VI.pqPage||[]);vcSel(0,false);vcStrip();vcPQBar();return true}if(k==='z'||k==='Z'){e.preventDefault();vcPQUndo();return true}if(k==='Escape'){e.preventDefault();vcPQ(false);return true}return false}
function vcMselOff(){VI.msel=false;VI.sel=new Set();VI.lastSel=null;vcSel(0,false);vcStrip()}
// 🖱 滑鼠滑過縮圖＝快速翻 16 格（像 Bridge／Finder 的滑動預覽）（V0.2.71；V0.2.74 一覽、資料夾包也能用）
const SCRUB={};
function scrubHook(S,sel,idOf,boxOf,busy){if(S._sh)return;S._sh=1;let HV=null;const off=()=>{if(HV&&HV.ov)HV.ov.remove();HV=null};
  S.addEventListener('pointerover',e=>{if(e.pointerType!=='mouse'||(busy&&busy()))return;const c=e.target.closest(sel);if(!c||(HV&&HV.c===c))return;off();const id=idOf(c);if(!id)return;HV={c,id};
    if(!SCRUB[id])SCRUB[id]=fetch(`/api/vc_cells?id=${id}`).then(r=>r.json()).catch(()=>({ok:false}));
    if(!c.title)SCRUB[id].then(g=>{if(g&&g.name&&!c.title)c.title=g.name})});
  S.addEventListener('pointermove',async e=>{if(!HV||e.pointerType!=='mouse')return;const b_=busy&&busy();if(b_&&b_.moved)return;const h=HV,g=await SCRUB[h.id];if(HV!==h||!g||!g.ok||!g.cells.length)return;
    const box=boxOf(h.c);if(!box)return;const r=box.getBoundingClientRect(),f=Math.max(0,Math.min(.999,(e.clientX-r.left)/r.width)),k=Math.floor(f*g.cells.length),cl=g.cells[k];
    if(!h.ov){h.ov=document.createElement('div');h.ov.style.cssText='position:absolute;inset:0;background-repeat:no-repeat;pointer-events:none;border-radius:inherit';h.ov.innerHTML='<i style="position:absolute;left:0;bottom:0;height:2px;background:var(--blue)"></i>';if(getComputedStyle(box).position==='static')box.style.position='relative';box.appendChild(h.ov)}
    if(h.k===k)return;h.k=k;const bp=(x,n)=>n>1?x/(n-1)*100:0;
    h.ov.style.backgroundImage=`url('/api/vc_img?id=${h.id}&s=${cl.s}')`;h.ov.style.backgroundSize=`${g.cols*100}% ${g.rows*100}%`;h.ov.style.backgroundPosition=`${bp(cl.c,g.cols)}% ${bp(cl.r,g.rows)}%`;h.ov.firstChild.style.width=((k+1)/g.cells.length*100)+'%'});
  S.addEventListener('pointerout',e=>{if(HV&&!HV.c.contains(e.relatedTarget))off()})}
function vcStripHook(S){if(S._hk)return;S._hk=1;let T=null,x0=0,y0=0,D=null,AS=null,lx=0,ly=0;S.style.userSelect='none';
  try{new ResizeObserver(()=>{const o=VI.scol;VI.scol=0;if(vcCols()!==o&&VI.ids.length&&$('#vcs')===S)vcStrip()}).observe(S)}catch(_){}
  const redraw=j=>{const el=S.querySelector(`[data-j="${j}"]`);if(el)el.outerHTML=vcStripItem(j,1)};
  const start=j=>{const id=VI.ids[j];if(id==null)return;VI.lpDone=1;if(!VI.msel){VI.msel=true;VI.sel=new Set()}vcSel(id,true);VI.lastSel=j;
    const st=S.scrollTop;redraw(j);S.scrollTop=st;try{navigator.vibrate&&navigator.vibrate(30)}catch(_){}
    if(D){D.base=new Set(VI.sel);D.add=true;D.lo=D.hi=j;D.lp=1}
    toast(`☑ 勾選中（${VI.sel.size} 部）：直接滑＝捲動；按住半秒再拖＝照順序整段選；點格子＝勾／取消；選好按右邊的分類一次套用；Esc 取消`,3500)};
  const at=(x,y)=>{const e=document.elementFromPoint(x,y),c=e&&e.closest&&e.closest('#vcs [data-j]');return c?+c.dataset.j:null};
  // 🖱 按住拖：從按下去那格到現在這格，照順序整段選（往下拖到下一列，左邊的也會選到）（V0.2.70）
  const paint=j=>{if(!D||j==null)return;const a=Math.min(D.j0,j),z=Math.max(D.j0,j),st=S.scrollTop;
    const lo=Math.min(a,D.lo),hi=Math.max(z,D.hi);
    for(let k=lo;k<=hi;k++){const id=VI.ids[k],inR=k>=a&&k<=z,want=inR?D.add:D.base.has(id),has=VI.sel.has(id);if(want!==has){vcSel(id,want);redraw(k)}}
    D.lo=a;D.hi=z;VI.lastSel=j;S.scrollTop=st;vcSel(0,false)};
  const auto=()=>{clearInterval(AS);AS=setInterval(()=>{if(!D||!D.moved){clearInterval(AS);return}const r=S.getBoundingClientRect(),m=40;let d=0;
    if(ly<r.top+m)d=-Math.ceil((r.top+m-ly)/2);else if(ly>r.bottom-m)d=Math.ceil((ly-(r.bottom-m))/2);if(d){S.scrollTop+=Math.max(-40,Math.min(40,d));vcStripMore();paint(at(lx,Math.max(r.top+2,Math.min(r.bottom-2,ly))))}},40)};
  S.addEventListener('pointerdown',e=>{S._inr=(S._inr||0)+1;const sj=e.target.closest('[data-j]');if(!sj||e.button>0)return;VI.lpDone=0;x0=lx=e.clientX;y0=ly=e.clientY;const j=+sj.dataset.j;
    D={j0:j,lo:j,hi:j,moved:false,pid:e.pointerId,base:new Set(VI.sel||[]),add:!(VI.msel&&VI.sel&&VI.sel.has(VI.ids[j]))};
    clearTimeout(T);T=setTimeout(()=>{T=null;if(D&&!D.moved)start(j)},450);if(e.pointerType==='mouse')e.preventDefault()});
  S.addEventListener('pointermove',e=>{const py=ly;lx=e.clientX;ly=e.clientY;if(!D)return;
    if(D.scr){const dy=py-ly,now=performance.now();S.scrollTop+=dy;vcStripMore();D.v=dy/Math.max(1,now-(D.tm||now))*0.8+(D.v||0)*0.2;D.tm=now;return}
    if(!D.moved){if(Math.hypot(lx-x0,ly-y0)<8)return;const j=at(lx,ly);
      if(e.pointerType!=='mouse'&&!D.lp){clearTimeout(T);T=null;if(VI.msel){D.scr=true;D.tm=performance.now();D.v=0;S.scrollTop+=y0-ly;return}D=null;return}   // 手機：直接滑＝捲動（勾選中自己捲，因為要留給按住拖框選）；要框選＝先按住不動半秒再拖（V0.4.57）
      if((j===D.j0&&!D.lp)||j==null)return;clearTimeout(T);T=null;D.moved=true;
      if(!VI.msel){VI.msel=true;VI.sel=new Set();D.base=new Set();D.add=true}
      try{S.setPointerCapture(D.pid)}catch(_){}auto();redraw(D.j0)}
    e.preventDefault();paint(at(lx,ly))},{passive:false});
  const up=()=>{if(!D&&!T)return;clearTimeout(T);T=null;clearInterval(AS);
    if(D&&D.scr){let v=D.v||0;VI.lpDone=1;setTimeout(()=>{VI.lpDone=0},300);D=null;const my=S._inr=(S._inr||0)+1;const step=()=>{if(S._inr!==my||Math.abs(v)<0.02)return;S.scrollTop+=v*16;v*=0.95;vcStripMore();requestAnimationFrame(step)};if(Math.abs(v)>0.1)requestAnimationFrame(step);return}   // 放開後滑一下（慣性）
    if(D&&D.moved){VI.lpDone=1;setTimeout(()=>{VI.lpDone=0},400);
    toast(VI.sel.size?`☑ 選了 ${VI.sel.size} 部，按右邊的分類一次套用（Esc 取消）`:'☑ 都沒選',2200)}D=null};
  if(window._vcUp){removeEventListener('pointerup',window._vcUp,true);removeEventListener('pointercancel',window._vcUp,true)}window._vcUp=up;addEventListener('pointerup',up,true);addEventListener('pointercancel',up,true);
  S.addEventListener('pointerleave',()=>{if(!(D&&D.moved)){clearTimeout(T);T=null}});
  S.addEventListener('scroll',()=>{if(D&&D.moved)paint(at(lx,ly));else if(!(VI.msel&&D&&!D.scr)){clearTimeout(T);T=null;if(D&&!D.moved&&VI.msel===false)D=null}},{passive:true});
  S.addEventListener('touchmove',e=>{if(D&&D.lp&&e.cancelable)e.preventDefault()},{passive:false});
  S.addEventListener('contextmenu',e=>{if(D||VI.lpDone)e.preventDefault()});S.style.webkitTouchCallout='none';   // 按住半秒後才拖：不讓畫面捲走（V0.4.57）
  S.addEventListener('dragstart',e=>e.preventDefault());
  S.addEventListener('dblclick',e=>{const c=e.target.closest('[data-j]');if(!c||VI.msel)return;const j=+c.dataset.j;vcGo(j);zoomImg(String(VI.ids[j]),VC.kind==='photo'?'photo':'video')});
  S.addEventListener('pointerover',e=>{if(e.pointerType!=='mouse')return;const c=e.target.closest('[data-j]');VI.hov=c?+c.dataset.j:null});S.addEventListener('pointermove',e=>{if(e.pointerType==='mouse')VI.hovT=Date.now()});
  S.addEventListener('pointerleave',()=>{VI.hov=null});
  S.addEventListener('wheel',e=>{if(!(e.ctrlKey||e.metaKey))return;e.preventDefault();VC.cadj=(+VC.cadj||0)+(e.deltaY>0?1:-1);VC.cadj=Math.max(-8,Math.min(8,VC.cadj));LS.set('vc',VC);VI.scol=0;vcStrip();toast(`🔍 一列 ${VI.scol} 格（Ctrl＋滾輪調整）`,1200)},{passive:false});
  scrubHook(S,'[data-j]',c=>VI.ids[+c.dataset.j],c=>c.firstElementChild,()=>D);
  S.addEventListener('contextmenu',e=>{const sj=e.target.closest('[data-j]');if(!sj)return;e.preventDefault();clearTimeout(T);T=null;if(!(VI.msel&&VI.sel.has(VI.ids[+sj.dataset.j])))start(+sj.dataset.j);VI.lpDone=0})}
// 🗺 進度地圖（V0.2.85）：整份清單哪裡分好了、哪裡還沒，一條看完；點一下跳過去
let MAPT=0;function vcMap(){const cv=$('#vcmap');if(!cv)return;clearTimeout(MAPT);MAPT=setTimeout(()=>{const W=cv.clientWidth|0,n=VI.ids.length;if(!W||!n)return;cv.width=W;cv.height=7;const x=cv.getContext('2d');x.clearRect(0,0,W,7);
  const per=n/W,CC={};VI.cats.forEach(c=>CC[c.id]=c.color);
  for(let p=0;p<W;p++){const a=Math.floor(p*per),z=Math.max(a+1,Math.floor((p+1)*per));let t=0,last=0;for(let k=a;k<z&&k<n;k++){const c=VI.tags[VI.ids[k]];if(c){t++;last=c}}
    if(!t)continue;x.globalAlpha=.35+.65*t/(z-a);x.fillStyle=CC[last]||'#45d483';x.fillRect(p,0,1,7)}
  x.globalAlpha=1;x.fillStyle='#fff';x.fillRect(Math.min(W-2,Math.floor(VI.i/per)),0,2,7);
  if(!cv._h){cv._h=1;cv.onclick=e=>{const r=cv.getBoundingClientRect();vcGo(Math.floor((e.clientX-r.left)/r.width*VI.ids.length))}}},120)}
function vcStrip(){const S=$('#vcs');if(!S||!VI.ids.length)return;vcMap();vcStripHook(S);VI.scol=0;vcCols();const i=VI.i,n=VI.ids.length;
  const sw0=SW[0],st0=S.scrollTop;
  if(!(SW[1]>SW[0])||i<SW[0]+8||i>SW[1]-12)SW=[Math.max(0,(Math.floor(i/4)-12)*4),Math.min(n,(Math.floor(i/4)+14)*4)];
  let h='';for(let j=SW[0];j<SW[1];j++)h+=vcStripItem(j);S.innerHTML=h;if(SW[0]===sw0)S.scrollTop=st0;
  const el=S.querySelector(`[data-j="${i}"]`);if(el){const t=el.offsetTop,b=t+el.offsetHeight;if(SW[0]!==sw0||t<S.scrollTop+2||b>S.scrollTop+S.clientHeight-2)S.scrollTop=t-S.clientHeight/2+el.offsetHeight/2}}   // 看得到就不要跳（V0.3.10）
function vcStripMore(){const S=$('#vcs');if(!S)return;const n=VI.ids.length;
  if(S.scrollTop<120&&SW[0]>0){const a=Math.max(0,SW[0]-48),o=SW[0],h0=S.scrollHeight;const f=S.firstElementChild;if(f&&f.dataset.gh&&o>0&&VI.gi[o]===VI.gi[o-1])f.remove();SW[0]=a;let h='';for(let j=a;j<o;j++)h+=vcStripItem(j);S.insertAdjacentHTML('afterbegin',h);S.scrollTop+=S.scrollHeight-h0}
  if(S.scrollTop+S.clientHeight>S.scrollHeight-120&&SW[1]<n){const b=Math.min(n,SW[1]+48);let h='';for(let j=SW[1];j<b;j++)h+=vcStripItem(j);S.insertAdjacentHTML('beforeend',h);SW[1]=b}}
async function vcFolder(){const Z=$('#vcz');vczShow('block');Z.style.overflow='auto';Z.innerHTML='<div class="panel" style="margin:10px">讀取中…</div>';
  const r=await api(U('/api/vc_folders',{k:VC.kind||'video'}));const R=r.rows||[];
  const draw=q=>{const L=R.filter(([d])=>!q||d.toLowerCase().includes(q.toLowerCase())).slice(0,400);
    $('#vcfo').innerHTML=`<div class="it" data-fd="" style="cursor:pointer"><b>📁 全部資料夾</b></div>`+L.map(([d,n])=>`<div class="it row" data-fd="${esc(d)}" style="cursor:pointer;flex-wrap:nowrap"><span class="grow" style="word-break:break-all;${VC.folder===d?'color:var(--blue);font-weight:800':''}">${esc(d)}</span><span class="mu">${n}</span></div>`).join('')+(L.length>=400?'<div class="mu">…太多了，打字找</div>':'')};
  Z.innerHTML=`<div class="panel" style="margin:10px"><div class="row"><h3 class="grow">📁 只看這個資料夾（含底下的）</h3><button class="pill" data-fx="1">關閉</button></div>
    <input id="vcfq" placeholder="打字找資料夾" style="width:100%;margin:6px 0"><div id="vcfo"></div></div>`;draw('');$('#vcfq').oninput=()=>draw($('#vcfq').value.trim());
  Z.onclick=e=>{e.stopPropagation();const x=e.target.closest('[data-fd],[data-fx]');if(!x)return;vczHide();
    if(x.dataset.fx)return;VC.folder=x.dataset.fd;LS.set('vc',VC);rVc()}}
// ---- 🧹 雜物清理（資料分析時順便找到的；搬到隔離區，可以復原）
let JK=LS.get('junk','temp'),JSEL=new Set();
async function rJunk(again){const j=await api(U('/api/junk',{k:again?'':JK}));
  if(!j.ok){$('#v').innerHTML=`<div class="panel">${esc(j.message||'')}<div class="row" style="margin-top:8px"><button class="pill acc" onclick="go('home')">📊 到總覽</button></div></div>`;return}
  const C=j.counts||{},st=j.st||{};const stx=st.run?`<span style="color:var(--blue)">🧹 搬到隔離區中：${st.n||0}／${st.total||0}</span>`:(st.msg?'✔ '+esc(st.msg):`資料來自 ${day(j.t)} 的資料分析；要找最新的，到總覽按「🔄 重新分析」。`);
  if(again){const e=$('#jst');if(e)e.innerHTML=stx;if(st.run||JRUN){JRUN=st.run;if(!st.run)rJunk()}return}
  JSEL=new Set();const R=j.rows||[],kinds=j.kinds||[],cur=kinds.find(k=>k[0]===JK)||kinds[0],big=JK==='big';
  $('#v').innerHTML=`<div class="panel"><div class="mu" id="jst">${stx}</div>
    <div class="seg" style="margin-top:8px;display:grid;grid-template-columns:1fr 1fr">${kinds.map(([k,ic,n])=>`<button data-jk="${k}" class="${k===JK?'on':''}" style="height:auto;padding:7px 4px;border:1px solid var(--line2)">${ic} ${n}<br><small style="font-weight:500">${((C[k]||[0])[0]).toLocaleString()} 個・${fmtB((C[k]||[0,0])[1])}</small></button>`).join('')}</div>
    <div class="mu" style="margin-top:8px">${{edir:'裡面整串都沒有檔案的資料夾（只列最上層那個）。',efile:'大小是 0 的檔案，通常是複製失敗或救援留下的空殼。',temp:'Thumbs.db、.DS_Store、desktop.ini、~$ 開頭的 Office 暫存、._ 開頭的 Mac 檔、沒下載完的 .crdownload／.part…',big:'整個硬碟最大的 300 個檔（不含遊戲／軟體資料夾）：看看有沒有不需要的。這一類要一個一個勾。'}[JK]||''}</div>
    <div class="row" style="margin-top:8px">${big?'':`<button class="pill acc" data-ja="all">📦 這一類全部搬到隔離區（${((C[JK]||[0])[0]).toLocaleString()} 個）</button>`}<button class="pill" data-ja="sel" id="jsel" disabled>📦 搬勾選的</button><span class="grow"></span><button class="pill" data-ja="selall">全選</button></div></div>
   <div class="panel">${R.map(r=>`<label class="it row" style="flex-wrap:nowrap;gap:8px"><input type="checkbox" data-jid="${r.id}"><span class="grow" style="min-width:0"><span style="word-break:break-all">${esc(r.path)}</span><br><span class="mu">${big||r.b?fmtB(r.b)+'・':''}${day(r.mt).slice(0,10)}</span></span></label>`).join('')||'<div class="mu">這一類沒有 🎉</div>'}${R.length>=1500?'<div class="mu">只列前 1,500 個</div>':''}</div>`;
  $('#v').onclick=async e=>{const k=e.target.closest('[data-jk]');if(k){JK=k.dataset.jk;LS.set('junk',JK);return rJunk()}
    const a=e.target.closest('[data-ja]');if(!a)return;const x=a.dataset.ja;
    if(x==='selall'){const on=JSEL.size<R.length;$$('[data-jid]').forEach(c=>{c.checked=on;on?JSEL.add(+c.dataset.jid):JSEL.delete(+c.dataset.jid)});$('#jsel').disabled=!JSEL.size;$('#jsel').textContent=`📦 搬勾選的（${JSEL.size}）`;return}
    const ids=x==='sel'?[...JSEL]:[];if(x==='sel'&&!ids.length)return;
    if(!confirm(`把${x==='all'?'「'+cur[2]+'」全部':'勾選的 '+ids.length+' 個'}搬到隔離區？\n\n不會刪檔，在「📦 隔離區」可以復原。`))return;
    const r=await api('/api/junk_run',{k:JK,ids});toast(r.message||'好了');JRUN=true;rJunk(true)};
  $('#v').onchange=e=>{const c=e.target.closest('[data-jid]');if(!c)return;c.checked?JSEL.add(+c.dataset.jid):JSEL.delete(+c.dataset.jid);$('#jsel').disabled=!JSEL.size;$('#jsel').textContent=`📦 搬勾選的（${JSEL.size}）`}}
let JRUN=false;
// ---- 🖼 相似照片（用已經算好的 dHash；一模一樣的交給「🔁 重複檔」）
let SIMO=0,SIMK='photo';
async function rSim(again){const V=SIMK==='video',B=SIMK==='burst',u=V?'部':'張';const j=await api(U('/api/sim',{o:SIMO,n:20,k:SIMK}));if(!j.ok)return;const st=j.st||{},I=j.info||{};
  const stx=st.run?`<span style="color:var(--blue)">${V?'🎬':'🖼'} ${esc(st.phase||'')} ${st.total?Math.round(100*(st.n||0)/st.total)+'%':''}</span>`:(I.t?`上次找：${day(I.t)}・${(I.groups||0).toLocaleString()} 組、${(I.files||0).toLocaleString()} ${u}（比了 ${(I.photos||0).toLocaleString()} ${u}${V?'影片':'照片'}）`+(V&&I.no_grid?`<br><span style="color:var(--orange)">還有 ${I.no_grid.toLocaleString()} 部沒有 16 格預覽、這次沒比（分類頁的背景會慢慢做，做完再找一次）</span>`:''):(B?'還沒找過：按「🔍 開始找」。第一次要算每張連拍照片的清楚程度（每張約 0.1 秒）':V?'還沒找過：按「🔍 開始找」。用分類預覽的 16 格比內容＋長度，第一次要算指紋（每部不到 0.1 秒）':'還沒找過：按「🔍 開始找」（照片的指紋在讀取拍攝資訊時就算好了，幾分鐘就好）'));
  if(again){const e=$('#sst');if(e)e.innerHTML=stx;if(st.run||SRUN){SRUN=st.run;if(!st.run)rSim()}return}
  const G=j.groups||[];
  $('#v').innerHTML=`<div class="panel"><div id="sst">${stx}</div>
    <div class="row" style="margin-top:8px"><select id="slv">${Object.entries(j.levels||{}).map(([k,n])=>`<option value="${k}" ${+k===j.level?'selected':''}>${esc(n)}</option>`).join('')}</select>
     <button class="pill acc" data-s="start">🔍 開始找</button>${G.length?'<button class="pill" data-s="all">⭐ 全部照建議處理</button>':''}</div>
    <div class="mu" style="margin-top:6px">${B?'同一台相機幾秒內連拍的一串，⭐＝最清楚的那張（「模糊」數字越小越清楚）。':'⭐＝建議保留（解析度最高 → 檔案最大 → 跟重複檔一樣的規則）。'}其他的搬到隔離區、可以復原。不是同一${V?'部':'張'}的話按「不是相似」，以後就不會再放一起。</div></div>
   ${G.map(g=>`<div class="panel"><div class="row" style="flex-wrap:nowrap"><b class="grow">第 ${g.gid} 組・${g.files.length} ${u}</b><span class="mu">可省 ${fmtB(g.save)}</span></div>
     <div style="display:flex;gap:6px;overflow-x:auto;padding:6px 0">${g.files.map(f=>`<div style="flex:none;width:${innerWidth<500?130:170}px;position:relative">
       <img loading="lazy" src="${V?'/api/vc_thumb?id='+f.id:'/api/fc_thumb?id='+f.id+'&w=320'}" data-zoom="${f.id}" data-zi="${f.id}" data-zk="${V?'video':'photo'}" style="width:100%;aspect-ratio:${V?'16/10':'1'};object-fit:cover;border-radius:8px;${f.keep?'outline:3px solid var(--green);outline-offset:-3px':''};background:#1a1f27">
       ${f.keep?'<span style="position:absolute;left:4px;top:4px;background:var(--green);color:#06210f;border-radius:6px;padding:0 5px;font-weight:900;font-size:12px">⭐ 留</span>':`<span style="position:absolute;left:4px;top:4px;background:#000a;color:#fff;border-radius:6px;padding:0 5px;font-size:11px">${B?'模糊 '+f.dist:'差 '+f.dist}</span>`}
       <div class="mu" style="font-size:11px;line-height:1.3;margin-top:3px">${V&&f.dur?fmtT(f.dur)+'・':''}${f.w&&f.h?f.w+'×'+f.h+'・':''}${fmtB(f.size)}<br>${day(f.taken||f.mtime).slice(0,10)}<br><span style="word-break:break-all">${esc(base(f.path))}</span></div>
       ${f.keep?'':`<button class="pill" data-sq="${f.id}" style="margin-top:3px;padding:2px 8px;font-size:11px">📦 只搬這${u}</button>`}</div>`).join('')}</div>
     <div class="row"><button class="pill acc" data-sg="${g.gid}">📦 留 ⭐、其他搬到隔離區</button><button class="pill" data-ss="${g.gid}">不是相似</button></div></div>`).join('')}
   ${j.n>20?`<div class="row" style="justify-content:center;margin:10px 0"><button class="pill" data-sp="-1" ${SIMO?'':'disabled'}>‹ 上一頁</button><span class="mu">${SIMO+1}～${Math.min(SIMO+20,j.n)}／${j.n.toLocaleString()} 組</span><button class="pill" data-sp="1" ${SIMO+20>=j.n?'disabled':''}>下一頁 ›</button></div>`:''}`;
  $('#v').onclick=async e=>{const t=e.target;let r;
    if(t.closest('[data-zoom]'))return zoomImg(t.closest('[data-zoom]').dataset.zoom,SIMK==='video'?'video':'photo');
    const b=t.closest('[data-s],[data-sg],[data-ss],[data-sq],[data-sp]');if(!b)return;
    if(b.dataset.sp){SIMO=Math.max(0,SIMO+20*(+b.dataset.sp));return rSim()}
    if(b.dataset.s==='start')r=await api('/api/sim_run',{a:'start',level:+$('#slv').value,k:SIMK});
    else if(b.dataset.s==='all'){if(!confirm(`全部 ${j.n.toLocaleString()} 組都照建議處理？\n\n每組留 ⭐，其他搬到隔離區（可以復原）。建議先看幾組確定沒問題。`))return;r=await api('/api/sim_run',{a:'all',k:SIMK})}
    else if(b.dataset.sg)r=await api('/api/sim_run',{a:'quar',gid:+b.dataset.sg,k:SIMK});
    else if(b.dataset.ss)r=await api('/api/sim_run',{a:'skip',gid:+b.dataset.ss,k:SIMK});
    else if(b.dataset.sq)r=await api('/api/sim_run',{a:'quar',fids:[+b.dataset.sq],k:SIMK});
    toast(r.message||'好了');SRUN=true;if(b.dataset.s)return rSim(true);rSim()}}
let SRUN=false;
// ---- 📅 依日期整理（先預覽、再搬；同一顆硬碟、可以復原）
const OG=LS.get('org',{src:'',dest:'',pattern:'ym',kinds:'both',mtime:false,unknown:'skip'});let ORUN=false;
async function rOrg(again){const j=await api('/api/org');if(!j.ok)return;const S=j.st||{};
  const stx=S.run?`<span style="color:var(--blue)">📅 整理中：${(S.n||0).toLocaleString()}／${(S.total||0).toLocaleString()}</span> <button class="pill er" data-o="stop">⏹ 停止</button>`:(S.msg?'✔ '+esc(S.msg):'');
  if(again){const e=$('#ost');if(e)e.innerHTML=stx;if(S.run||ORUN){ORUN=S.run;if(!S.run)toast('📅 '+(S.msg||'好了'),4000)}return}
  const P=j.patterns||{};
  $('#v').innerHTML=`<div class="panel"><div id="ost">${stx}</div>
   <div class="si"><b>要整理哪裡</b><select id="osrc" style="width:100%"><option value="">全部要整理的資料夾</option>${(j.roots||[]).map(r=>`<option ${OG.src===r?'selected':''}>${esc(r)}</option>`).join('')}${OG.src&&!(j.roots||[]).includes(OG.src)?`<option selected>${esc(OG.src)}</option>`:''}</select>
     <input id="osrc2" placeholder="或打一個資料夾，例如 R:\\手機備份\\DCIM" value="" style="width:100%;margin-top:6px"></div>
   <div class="si"><b>整理到哪</b><input id="odest" placeholder="空的＝每顆硬碟的 \\照片影片_依日期" value="${esc(OG.dest)}" style="width:100%"><small>要跟照片影片在同一顆硬碟（才會瞬間搬好、不佔空間）。</small></div>
   <div class="si"><b>資料夾怎麼分</b><div class="seg" id="opat">${Object.entries(P).map(([k,n])=>`<button data-v="${k}" class="${OG.pattern===k?'on':''}">${esc(n)}</button>`).join('')}</div><small>例如 2019\\2019-05\\IMG_….jpg</small></div>
   <div class="si"><b>整理什麼</b><div class="seg" id="okind">${[['both','照片＋影片'],['photo','只有照片'],['video','只有影片']].map(([k,n])=>`<button data-v="${k}" class="${OG.kinds===k?'on':''}">${n}</button>`).join('')}</div></div>
   <div class="si tgr"><b>沒有拍攝日期的，用「修改日期」<small>修改日期常常是複製、傳輸的時間，不一定準。不開的話，沒有可靠日期的會跳過（或放進「${'日期不明'}」）。</small></b><label class="tg"><input type="checkbox" id="omt" ${OG.mtime?'checked':''}><i></i></label></div>
   <div class="si tgr"><b>日期不明的放進「日期不明」資料夾<small>不開＝留在原地不動</small></b><label class="tg"><input type="checkbox" id="ounk" ${OG.unknown==='move'?'checked':''}><i></i></label></div>
   <div class="si tgr"><b>📷 只整理自己拍的<small>只搬手機／相機拍的；截圖、下載、LINE、抖音…都不動（那些可以用「🏷 依來源整理」）</small></b><label class="tg"><input type="checkbox" id="ocam" ${OG.cam?'checked':''}><i></i></label></div>
   <div class="row" style="margin-top:8px"><button class="pill acc" data-o="plan">👀 預覽（不會動任何檔）</button></div></div><div id="oplan"></div>`;
  const seg=id=>{const el=$(id);el.onclick=e=>{const b=e.target.closest('button');if(!b)return;$$('button',el).forEach(x=>x.classList.toggle('on',x===b))}};seg('#opat');seg('#okind');
  $('#v').onclick=async e=>{const b=e.target.closest('[data-o]');if(!b)return;const a=b.dataset.o;
    if(a==='stop'){await api('/api/org',{a:'stop'});return}
    if(a==='plan'){Object.assign(OG,{src:$('#osrc2').value.trim()||$('#osrc').value,dest:$('#odest').value.trim(),pattern:($('#opat .on')||{}).dataset?.v||'ym',kinds:($('#okind .on')||{}).dataset?.v||'both',mtime:$('#omt').checked,unknown:$('#ounk').checked?'move':'skip',cam:$('#ocam').checked});LS.set('org',OG);
      $('#oplan').innerHTML='<div class="panel mu">預覽中…</div>';const r=await api('/api/org',Object.assign({a:'plan'},OG));const el=$('#oplan');
      if(!r.ok){el.innerHTML=`<div class="panel" style="color:var(--red)">${esc(r.message||'失敗')}</div>`;return}
      const mx=Math.max(1,...r.months.map(m=>m[1][0]));
      el.innerHTML=`<div class="panel"><h3>👀 預覽：會搬 ${r.n.toLocaleString()} 個（${fmtB(r.b)}）</h3>
        <div class="mu">整理到：${esc(r.dest_eg||'')}\\${esc(r.pattern)}</div>
        <div class="mu" style="margin-top:4px">跳過：${Object.entries(r.skip).filter(([,v])=>v).map(([k,v])=>`${esc(k)} ${v.toLocaleString()}`).join('、')||'沒有'}</div>
        <div style="max-height:220px;overflow:auto;margin-top:8px">${bars(r.months.map(([k,v])=>[k,v[0].toLocaleString()+' 個',[['var(--blue)',v[0],fmtB(v[1])]],v[0]/mx]),24)}</div>
        <h3 style="margin-top:10px">前 ${r.sample.length} 個會這樣搬</h3><div style="max-height:260px;overflow:auto;font-size:12px">${r.sample.map(x=>`<div class="it"><span class="mu">${esc(x.src)}</span><br>→ ${esc(x.dst)}</div>`).join('')}</div>
        ${r.n?`<div class="row" style="margin-top:10px"><button class="pill acc" data-o="run">📅 開始整理（${r.n.toLocaleString()} 個）</button></div><div class="mu">每一筆都記下來，搬錯了在「📦 隔離區」→ 搬移紀錄可以復原。</div>`:''}</div>`;el.scrollIntoView({behavior:'smooth'});return}
    if(a==='run'){if(!confirm('開始依日期整理？\n\n只在同一顆硬碟裡搬（瞬間完成），可以在「📦 隔離區」復原。'))return;const r=await api('/api/org',{a:'run'});toast(r.message||'好了');ORUN=r.ok;$('#oplan').innerHTML='';rOrg(true)}}}
// ---- 📂 瀏覽資料夾（V0.1.51）
let BRP=LS.get('brp',''),BRO=0;
async function rBr(again){if(again)return;const j=await api(U('/api/browse',{p:BRP,o:BRO}));if(!j.ok)return;
  const cr=`<div class="panel" style="padding:8px 10px"><div class="row brc" style="gap:4px;flex-wrap:wrap;font-size:13px"><a href="#" data-bp="">📂 全部</a>${(j.crumbs||[]).map(c=>` › <a href="#" data-bp="${esc(c.path)}">${esc(c.name)}</a>`).join('')}</div><style>.brc a{color:var(--accent);text-decoration:none;font-weight:700}</style>
    ${j.path?`<div class="mu" style="font-size:12px;margin-top:4px">${j.dirs.length.toLocaleString()} 個資料夾・${j.nf.toLocaleString()} 個照片影片${j.other?`・其他檔 ${j.other.toLocaleString()}`:''}</div>
    <div class="row" style="margin-top:6px;gap:6px">${j.nf?'<button class="pill" data-bsl>▶ 輪播</button>':''}<button class="pill" data-bvc>🎞 在分類頁看這個資料夾</button><button class="pill" data-btag>📚 整個資料夾分到…</button></div>`:''}</div>`;
  const BS=LS.get('brs','name'),DD=[...j.dirs].sort((a,b)=>BS==='size'?b.b-a.b:BS==='n'?b.n-a.n:BS==='m'?b.m-a.m:a.name.localeCompare(b.name,'zh-Hant',{numeric:true}));
  const dirs=j.dirs.length?`<div class="panel" style="padding:4px 8px">${j.dirs.length>1?`<div class="row" style="gap:4px;margin:4px 0">${[['name','名稱'],['size','大小'],['n','檔案數'],['m','照片影片數']].map(([k,n])=>`<button class="pill ${BS===k?'acc':''}" data-bs="${k}" style="font-size:11.5px;padding:2px 8px">${n}</button>`).join('')}</div>`:''}${DD.map(d=>`<div class="it row" data-bp="${esc(d.path)}" style="cursor:pointer;flex-wrap:nowrap;gap:8px"><span style="font-size:20px">📁</span><span class="grow" style="word-break:break-all"><b>${esc(d.name)}</b></span><span class="mu" style="white-space:nowrap;font-size:12px">${d.m?'🖼 '+d.m.toLocaleString()+'・':''}${d.n.toLocaleString()} 個・${fmtB(d.b)}</span><span class="mu">›</span></div>`).join('')}</div>`:'';
  const grid=j.files.length?`<div style="display:grid;grid-template-columns:repeat(${innerWidth<500?4:8},1fr);gap:4px" id="brg">${j.files.map(r=>tthumb(r)).join('')}</div>`+(BRO+240<j.nf?`<div class="row" style="justify-content:center;margin:10px"><button class="pill" data-bm>再載入（${(BRO+240).toLocaleString()}／${j.nf.toLocaleString()}）</button></div>`:''):'';
  if(BRO&&$('#brg')){$('#brg').insertAdjacentHTML('beforeend',j.files.map(r=>tthumb(r)).join(''));const m=$('[data-bm]');if(m&&BRO+240>=j.nf)m.parentElement.remove();return}
  $('#v').innerHTML=cr+dirs+grid+(!j.dirs.length&&!j.files.length?'<div class="panel mu">這裡沒有照片影片</div>':'');scrollTo(0,0);
  $('#v').onclick=e=>{const z=e.target.closest('[data-zi]');if(z)return zoomImg(z.dataset.zi,z.dataset.zk);if(e.target.closest('[data-bm]')){BRO+=240;return rBr()}
    const bs=e.target.closest('[data-bs]');if(bs){LS.set('brs',bs.dataset.bs);return rBr()}
    if(e.target.closest('[data-bsl]'))return slideFrom($('#brg'));
    if(e.target.closest('[data-bvc]')){VC.folder=j.path;VC.f='all';LS.set('vc',VC);return go('vc')}
    if(e.target.closest('[data-btag]'))return brTag(j.path);
    const b=e.target.closest('[data-bp]');if(b){e.preventDefault();BRP=b.dataset.bp;BRO=0;LS.set('brp',BRP);rBr()}}}
// 選一個分類，把這些 id 分過去（V0.1.91：搜尋結果勾選的）
async function tagPick(ids){const s=await api('/api/vc_state');const C=s.cats||[];if(!C.length)return toast('還沒有分類：先到「🎞 分類」新增');
  const Z=document.createElement('div');Z.style.cssText='position:fixed;inset:0;z-index:85;background:#000b;display:grid;place-items:center;padding:14px';
  Z.innerHTML=`<div class="panel" style="max-width:520px;width:100%;margin:0"><div class="row"><h3 class="grow" style="margin:0">📚 ${ids.length} 個分到…</h3><button class="pill" data-tx>取消</button></div><div class="mu" style="font-size:12px;margin:4px 0 8px">已經分好的也會改成這一類（搬過的不動）；只是標記，到分類頁按 🚚 搬才會搬</div>
   <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:6px">${C.map(c=>`<button class="pill" data-tc="${c.id}" style="padding:10px 6px;border-left:5px solid ${c.color}">${esc(c.name)}</button>`).join('')}</div></div>`;
  const real=()=>Z.remove();Z.onclick=async e=>{if(e.target===Z||e.target.closest('[data-tx]'))return ovClose(real);const b=e.target.closest('[data-tc]');if(!b)return;
    const r=await api('/api/vc_tag_many',{ids,cat:+b.dataset.tc,only_new:false});toast(r.message||'失敗',4000);ovClose(real)};document.body.appendChild(Z);ovOpen(real)}
async function brTag(path){const s=await api('/api/vc_state');const C=s.cats||[];if(!C.length)return toast('還沒有分類：先到「🎞 分類」新增');
  const Z=document.createElement('div');Z.style.cssText='position:fixed;inset:0;z-index:85;background:#000b;display:grid;place-items:center;padding:14px';
  Z.innerHTML=`<div class="panel" style="max-width:520px;width:100%;margin:0"><div class="row"><h3 class="grow" style="margin:0">📚 整個資料夾分到…</h3><button class="pill" data-tx>取消</button></div>
   <div class="mu" style="font-size:12px;margin:4px 0 8px;word-break:break-all">${esc(path)}（含子資料夾；還沒分的才分、只是標記，到分類頁按 🚚 搬才會搬）</div>
   <div class="row" style="gap:6px;margin-bottom:8px"><select id="btk"><option value="">照片＋影片</option><option value="video">只有影片</option><option value="photo">只有照片</option></select></div>
   <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:6px">${C.map(c=>`<button class="pill" data-tc="${c.id}" style="padding:10px 6px;border-left:5px solid ${c.color}">${esc(c.name)}</button>`).join('')}</div></div>`;
  const real=()=>Z.remove();Z.onclick=async e=>{if(e.target===Z||e.target.closest('[data-tx]'))return ovClose(real);const b=e.target.closest('[data-tc]');if(!b)return;
    const r=await api('/api/vc_tag_many',{folder:path,cat:+b.dataset.tc,kind:$('#btk').value});toast(r.message||'失敗',4000);ovClose(real)};document.body.appendChild(Z);ovOpen(real)}
// ---- 🧳 活動（V0.1.48）
let EV=LS.get('ev',{gap:6,min:15}),EVN=30;
async function rEvt(again){if(again)return;const j=await api(U('/api/events',{gap:EV.gap,min:EV.min}));if(!j.ok)return;const R=j.rows||[];
  const dd=t=>{const d=new Date(t*1000);return`${d.getFullYear()}/${d.getMonth()+1}/${d.getDate()}`};
  const card=(e,i)=>`<div class="panel"><div class="row" style="flex-wrap:nowrap"><b class="grow">${dd(e.t0)}${e.days>1?' ～ '+dd(e.t1):''} <span class="mu" style="font-weight:400">${e.days>1?e.days+' 天':''}</span>${e.gps?` <span data-place="${e.gps[0]},${e.gps[1]}" style="font-weight:400;color:var(--accent);font-size:12.5px"></span>`:''}</b><span class="mu" style="white-space:nowrap">${e.photo?'📷 '+e.photo:''} ${e.video?'🎬 '+e.video:''}・${fmtB(e.b)}</span></div>
    <div style="display:flex;gap:4px;overflow-x:auto;margin:6px 0">${e.cover.map(id=>`<img loading="lazy" src="/api/fc_thumb?id=${id}&w=240" data-zi="${id}" style="width:${innerWidth<500?84:120}px;aspect-ratio:1;object-fit:cover;border-radius:6px;flex:none;background:#1a1f27;cursor:pointer">`).join('')}</div>
    <div class="mu" style="font-size:12px;word-break:break-all">📁 ${esc(e.dir)}${e.ndirs>1?`（＋另外 ${e.ndirs-1} 個資料夾）`:''}</div>
    <div class="row" style="margin-top:6px">${e.gps?`<a class="pill" target="_blank" rel="noopener" href="https://www.google.com/maps?q=${e.gps[0]},${e.gps[1]}">📍 在哪裡</a>`:''}<button class="pill" data-evs="${e.key}">▶ 輪播 ${e.n}</button><button class="pill" data-ev="${e.key}">📁 整理成一個資料夾…</button></div><div data-evp="${e.key}"></div></div>`;
  $('#v').innerHTML=`<div class="panel"><div class="mu">照拍攝時間自動分段：前後隔超過 <select id="evg">${[3,6,12,24].map(h=>`<option ${+EV.gap===h?'selected':''}>${h}</option>`).join('')}</select> 小時算新的一次，至少 <select id="evm">${[5,15,30,60].map(n=>`<option ${+EV.min===n?'selected':''}>${n}</option>`).join('')}</select> 個才列。只用可靠的拍攝日期。</div>
    <div style="margin-top:6px"><b>${j.n.toLocaleString()} 次活動</b>${j.n?'':'<span class="mu">（把「至少」調小試試；或先讓「讀取拍攝資訊」做完）</span>'}</div></div>`+R.slice(0,EVN).map(card).join('')+(R.length>EVN?`<div class="row" style="justify-content:center;margin:10px"><button class="pill" data-evm>再看 30 個</button></div>`:'');
  placeFill($('#v'));
  $('#evg').onchange=$('#evm').onchange=()=>{EV={gap:+$('#evg').value,min:+$('#evm').value};LS.set('ev',EV);EVN=30;rEvt()};
  $('#v').onclick=async e=>{const z=e.target.closest('[data-zi]');if(z)return zoomImg(z.dataset.zi,'photo');if(e.target.closest('[data-evm]')){EVN+=30;return rEvt()}
    const sv=e.target.closest('[data-evs]');if(sv){const r=await api(U('/api/events',{items:sv.dataset.evs}));if(!r.ok||!r.rows.length)return toast('沒有');ZAUTO=true;return zoomImg(r.rows[0][0],r.rows[0][1],r.rows.map(x=>[String(x[0]),x[1]]))}
    const b=e.target.closest('[data-ev]');if(b){const k=b.dataset.ev,pl=((b.closest('.panel').querySelector('[data-place]')||{}).textContent||'').replace('📍 ','');const label=prompt('資料夾名稱要加什麼？（例如：墾丁、阿嬤生日；可以空白）',pl);if(label===null)return;
      const r=await api('/api/events',{a:'plan',key:k,label});const el=$(`[data-evp="${k}"]`);if(!r.ok){toast(r.message||'失敗');return}
      el.innerHTML=`<div class="it" style="margin-top:6px"><b>會搬 ${r.n.toLocaleString()} 個（${fmtB(r.b)}）→ ${esc(r.dest_eg)}</b><div class="mu" style="font-size:12px">跳過：${Object.entries(r.skip).filter(([,v])=>v).map(([k,v])=>`${esc(k)} ${v}`).join('、')||'沒有'}</div>
        ${r.n?`<div class="row" style="margin-top:6px"><button class="pill acc" data-evr>📁 開始整理</button><span class="mu" style="font-size:12px">同一顆硬碟搬、可以在隔離區復原</span></div>`:''}</div>`;return}
    if(e.target.closest('[data-evr]')){const r=await api('/api/events',{a:'run'});toast(r.message||'好了',4000);setTimeout(()=>rEvt(),2500)}}}
// ---- ⭐ 最愛（V0.1.43）
let FVO=0,FVK='';
async function rFav(again){if(again)return;const j=await api(U('/api/fav',{o:FVO,k:FVK}));if(!j.ok)return;
  const head=`<div class="panel"><div class="row"><b class="grow">⭐ ${j.n.toLocaleString()} 個最愛</b>${j.n?'<button class="pill" data-fsl>▶ 輪播</button>':''}<select id="fvk"><option value="">全部</option><option value="photo" ${FVK==='photo'?'selected':''}>照片</option><option value="video" ${FVK==='video'?'selected':''}>影片</option></select></div>
   <div class="mu" style="margin-top:4px">在任何地方點開大圖／播放影片，右上角按「☆ 最愛」就會加進來。重複檔、相似照片影片的建議會優先留最愛的那份。</div></div>`;
  const grid=`<div style="display:grid;grid-template-columns:repeat(${innerWidth<500?4:8},1fr);gap:4px" id="fvg">${j.rows.map(r=>tthumb(r)).join('')}</div>`+(FVO+60<j.n?`<div class="row" style="justify-content:center;margin:10px"><button class="pill" data-fm>再載入 60 個</button></div>`:'');
  if(FVO&&$('#fvg')){$('#fvg').insertAdjacentHTML('beforeend',j.rows.map(r=>tthumb(r)).join(''));const m=$('[data-fm]');if(m&&FVO+60>=j.n)m.parentElement.remove();return}
  $('#v').innerHTML=head+(j.n?grid:'<div class="panel mu">還沒有最愛</div>');$('#fvk').onchange=()=>{FVK=$('#fvk').value;FVO=0;rFav()};
  $('#v').onclick=e=>{if(e.target.closest('[data-fsl]'))return slideFrom($('#fvg'));const z=e.target.closest('[data-zi]');if(z)return zoomImg(z.dataset.zi,z.dataset.zk);if(e.target.closest('[data-fm]')){FVO+=60;rFav()}}}
// ---- 📝 依日期改檔名（V0.1.39）
let RN=LS.get('ren',{src:'',fmt:'dash',keep:false,kinds:'photo'});
async function rRen(again){const j=await api('/api/org');if(!j.ok)return;const S=j.st||{};
  const stx=S.run?`<span style="color:var(--blue)">📝 改名中：${(S.n||0).toLocaleString()}／${(S.total||0).toLocaleString()}</span> <button class="pill er" data-o="stop">⏹ 停止</button>`:(S.msg?'✔ '+esc(S.msg):'');
  if(again){const e=$('#ost');if(e)e.innerHTML=stx;if(S.run||ORUN){ORUN=S.run;if(!S.run)toast('📝 '+(S.msg||'好了'),4000)}return}
  const F=[['dash','2023-05-01 14.30.05'],['us','2023-05-01_143005'],['cam','20230501_143005']];
  $('#v').innerHTML=`<div class="panel"><div class="mu">把檔名改成拍攝日期時間（只用可靠的日期：EXIF、影片內建、檔名），檔案留在原本的資料夾。照名字排就是照時間排，換電腦、上傳雲端也不會亂。同一秒的連拍會加 _2、_3。</div><div id="ost" style="margin-top:6px">${stx}</div>
   <div class="si"><b>要改哪裡</b><select id="rsrc" style="width:100%"><option value="">全部要整理的資料夾</option>${(j.roots||[]).map(r=>`<option ${RN.src===r?'selected':''}>${esc(r)}</option>`).join('')}</select><input id="rsrc2" placeholder="或打一個資料夾" style="width:100%;margin-top:6px" value="${RN.src&&!(j.roots||[]).includes(RN.src)?esc(RN.src):''}"></div>
   <div class="si"><b>名字長這樣</b><div class="seg" id="rfmt">${F.map(([k,n])=>`<button data-v="${k}" class="${RN.fmt===k?'on':''}">${n}</button>`).join('')}</div></div>
   <div class="si"><b>改什麼</b><div class="seg" id="rkind">${[['photo','只有照片'],['both','照片＋影片'],['video','只有影片']].map(([k,n])=>`<button data-v="${k}" class="${RN.kinds===k?'on':''}">${n}</button>`).join('')}</div><small>影片改名後，SortCut 的預覽要用大小重新對應（分類頁可能要重做 16 格），所以預設只改照片。</small></div>
   <div class="si tgr"><b>後面保留原本的檔名<small>例如 2023-05-01 14.30.05 IMG_1234.jpg</small></b><label class="tg"><input type="checkbox" id="rkeep" ${RN.keep?'checked':''}><i></i></label></div>
   <div class="row" style="margin-top:8px"><button class="pill acc" data-o="plan">👀 預覽（不會動任何檔）</button></div></div><div id="oplan"></div>`;
  const seg=id=>{const el=$(id);el.onclick=e=>{const b=e.target.closest('button');if(!b)return;$$('button',el).forEach(x=>x.classList.toggle('on',x===b))}};seg('#rfmt');seg('#rkind');
  $('#v').onclick=async e=>{const b=e.target.closest('[data-o]');if(!b)return;const a=b.dataset.o;
    if(a==='stop'){await api('/api/org',{a:'stop'});return}
    if(a==='plan'){RN={src:$('#rsrc2').value.trim()||$('#rsrc').value,fmt:($('#rfmt .on')||{}).dataset?.v||'dash',kinds:($('#rkind .on')||{}).dataset?.v||'photo',keep:$('#rkeep').checked};LS.set('ren',RN);
      $('#oplan').innerHTML='<div class="panel mu">預覽中…</div>';const r=await api('/api/org',{a:'plan_ren',src:RN.src,fmt:RN.fmt,kinds:RN.kinds,keep_old:RN.keep});const el=$('#oplan');
      if(!r.ok){el.innerHTML=`<div class="panel" style="color:var(--red)">${esc(r.message||'失敗')}</div>`;return}
      el.innerHTML=`<div class="panel"><h3>👀 預覽：會改 ${r.n.toLocaleString()} 個</h3><div class="mu">跳過：${Object.entries(r.skip).filter(([,v])=>v).map(([k,v])=>`${esc(k)} ${v.toLocaleString()}`).join('、')||'沒有'}（沒有可靠拍攝日期的不改）</div>
        <h3 style="margin-top:10px">前 ${r.sample.length} 個會這樣改</h3><div style="max-height:300px;overflow:auto;font-size:12px">${r.sample.map(x=>`<div class="it"><span class="mu">${esc(base(x.src))}</span> → <b>${esc(base(x.dst))}</b></div>`).join('')}</div>
        ${r.n?`<div class="row" style="margin-top:10px"><button class="pill acc" data-o="run">📝 開始改名（${r.n.toLocaleString()} 個）</button></div><div class="mu">每一筆都記下來，改錯了在「📦 隔離區」→ 搬移紀錄可以復原。</div>`:''}</div>`;el.scrollIntoView({behavior:'smooth'});return}
    if(a==='run'){if(!confirm('開始改檔名？\n\n每一筆都記下來，可以在「📦 隔離區」復原。'))return;const r=await api('/api/org',{a:'run'});toast(r.message||'好了');ORUN=r.ok;$('#oplan').innerHTML='';rRen(true)}}}
// ---- 📱 用過的手機相機（V0.2.04）
async function rCams(again){if(again)return;const j=await api('/api/cams');if(!j.ok)return;const R=j.rows||[];
  const ys=R.flatMap(r=>[r.t0,r.t1]).filter(Boolean).map(t=>new Date(t*1000).getFullYear());const y0=Math.min(...ys),y1=Math.max(...ys),sp=Math.max(1,y1-y0+1);
  const mx=Math.max(1,...R.map(r=>r.n));
  $('#v').innerHTML=`<div class="panel"><div class="mu">照片影片裡記錄的廠牌、型號（EXIF／影片標籤），照開始使用的時間排。點一台看它拍的。</div></div>
   <div class="panel">${R.length?R.map(r=>{const a=r.t0?new Date(r.t0*1000).getFullYear():y0,b=r.t1?new Date(r.t1*1000).getFullYear():a;
     return `<div class="it" data-cam="${esc((r.make+' '+r.model).trim())}" style="cursor:pointer"><div class="row" style="flex-wrap:nowrap"><b class="grow">📷 ${esc(r.make)} ${esc(r.model)}</b><span class="mu" style="white-space:nowrap">${r.n.toLocaleString()} 個${r.v?'（影片 '+r.v.toLocaleString()+'）':''}・${fmtB(r.b)}</span></div>
      <div style="position:relative;height:8px;background:var(--track);border-radius:4px;margin-top:5px"><i style="position:absolute;left:${100*(a-y0)/sp}%;width:${Math.max(2,100*(b-a+1)/sp)}%;top:0;bottom:0;background:var(--accent);border-radius:4px;opacity:${.35+.65*r.n/mx}"></i></div>
      <div class="mu" style="font-size:11px">${a===b?a:a+' → '+b}</div></div>`}).join('')+`<div class="row mu" style="font-size:11px;justify-content:space-between;margin-top:4px"><span>${y0}</span><span>${y1}</span></div>`:'<div class="mu">還沒讀到相機資訊（要先「讀取拍攝資訊」）</div>'}</div>`;
  $('#v').onclick=e=>{const c=e.target.closest('[data-cam]');if(c){FD.f={model:c.dataset.cam};FD.off=0;LS.set('find',FD);go('tool:find')}}}
// ---- 🕒 修正修改日期（V0.1.88）
let MTK='both',MTRUN=false;
async function rMtf(again){const j=await api(U('/api/mtfix',{kinds:MTK}));if(!j.ok)return;const S=j.st||{};
  const stx=S.run?`<span style="color:var(--blue)">🕒 ${(S.n||0).toLocaleString()}／${(S.total||0).toLocaleString()}</span>`:(S.msg?'✔ '+esc(S.msg):'');
  if(again){const e=$('#mst');if(e)e.innerHTML=stx;if(S.run||MTRUN){MTRUN=S.run;if(!S.run)rMtf()}return}
  $('#v').innerHTML=`<div class="panel"><div class="mu">照片影片的「修改日期」常常是複製、傳輸那天，不是拍的那天。這裡把它改成<b>真正的拍攝日期</b>（只用可靠的：EXIF、影片內建、檔名），Windows 檔案總管、其他相簿軟體照日期排就對了。<br>只改檔案的日期屬性，不動內容、不搬；每一筆都記下來，可以整批改回去。</div>
    <div class="row" style="margin-top:8px;gap:6px"><select id="mtk"><option value="both">照片＋影片</option><option value="photo" ${MTK==='photo'?'selected':''}>只有照片</option><option value="video" ${MTK==='video'?'selected':''}>只有影片</option></select></div>
    <div style="margin-top:8px"><b>${j.n.toLocaleString()} 個</b>的修改日期跟拍攝日期差超過 1 天</div><div id="mst" style="margin-top:4px">${stx}</div>
    <div class="row" style="margin-top:8px">${j.n?`<button class="pill acc" data-m="run">🕒 全部修正（${j.n.toLocaleString()} 個）</button>`:''}${j.undo?`<button class="pill er" data-m="undo">↩ 全部改回去（${j.undo.toLocaleString()}）</button>`:''}</div></div>
   ${j.sample.length?`<div class="panel"><h3 style="margin-top:0">例如</h3>${j.sample.map(x=>`<div class="it" style="font-size:12.5px"><b style="word-break:break-all">${esc(base(x.path))}</b><br><span class="mu">修改日期 ${day(x.old).slice(0,10)} → 拍攝日期 <b style="color:var(--green)">${day(x.new).slice(0,10)}</b></span></div>`).join('')}</div>`:''}`;
  $('#mtk').onchange=()=>{MTK=$('#mtk').value;rMtf()};
  $('#v').onclick=async e=>{const b=e.target.closest('[data-m]');if(!b)return;const a=b.dataset.m;
    if(a==='run'&&!confirm(`把 ${j.n.toLocaleString()} 個檔的修改日期改成拍攝日期？\n（可以整批改回去）`))return;if(a==='undo'&&!confirm('全部改回原本的修改日期？'))return;
    const r=await api('/api/mtfix',{a,kinds:MTK});toast(r.message||'好了');MTRUN=true;rMtf(true)}}
// ---- 💾 備份檢查（V0.1.38）
async function rBak(again,force){if(again)return;$('#v').innerHTML='<div class="panel mu">檢查中…</div>';const j=await api(U('/api/backup',{f:force?1:0}));if(!j.ok)return;const T=j.tot,all=['ok','same','one','wait'].reduce((a,k)=>a+T[k][1],0)||1;
  const K={ok:['var(--green)','✔ 別顆硬碟也有','有備份，安全'],same:['var(--orange)','⚠ 只在同一顆硬碟有副本','硬碟壞了會一起沒'],one:['var(--red)','✖ 只有一份','硬碟壞了就沒了'],wait:['var(--sub)','… 還沒比對完','比對重複做完才知道']};
  const bar=D=>`<div style="display:flex;height:16px;border-radius:6px;overflow:hidden;background:var(--track)">${['ok','same','one','wait'].map(k=>`<i style="width:${100*D[k][1]/(['ok','same','one','wait'].reduce((a,x)=>a+D[x][1],0)||1)}%;background:${K[k][0]}"></i>`).join('')}</div>`;
  $('#v').innerHTML=`<div class="panel"><div class="row"><h3 class="grow" style="margin:0">💾 你的照片影片有沒有備份</h3><button class="pill" data-b="re">🔄 重新檢查</button></div>
    <div class="mu" style="margin:4px 0 8px">用比對重複的結果算（不用另外跑）：同一個檔（內容一模一樣）在別顆硬碟也有＝有備份。${j.ndrives<2?'<br><b style="color:var(--orange)">目前只整理了 1 顆硬碟：要檢查備份，把備份硬碟也加進「要整理的資料夾」。</b>':''}</div>
    ${bar(T)}<div style="margin-top:8px">${['one','same','ok','wait'].map(k=>`<div class="it row" style="flex-wrap:nowrap"><i class="dot" style="background:${K[k][0]};width:11px;height:11px;border-radius:3px;flex:none;display:inline-block"></i><span class="grow"><b>${K[k][1]}</b> <span class="mu" style="font-size:12px">${K[k][2]}</span></span><span style="white-space:nowrap">${T[k][0].toLocaleString()} 個・<b>${fmtB(T[k][1])}</b> <span class="mu">${Math.round(100*T[k][1]/all)}%</span></span></div>`).join('')}</div></div>
   <div class="panel"><h3 style="margin-top:0">每顆硬碟</h3>${j.drives.map(d=>`<div style="margin:8px 0"><div class="row"><b class="grow">💽 ${esc(d.drive)}</b><span class="mu">只有一份 ${fmtB(d.one[1])}</span></div>${bar(d)}</div>`).join('')}</div>
   <div class="panel"><h3 style="margin-top:0">最需要備份的資料夾（只有一份＋只在同一顆）</h3><div class="mu" style="margin-bottom:4px">複製到另一顆硬碟（或雲端）就安全了</div>
    ${j.top.slice(0,40).map(([d,p,n,b])=>`<div class="it row" style="flex-wrap:nowrap"><span class="grow" style="word-break:break-all">${esc(p)}</span><span class="mu" style="white-space:nowrap">${n.toLocaleString()} 個・${fmtB(b)}</span></div>`).join('')||'<div class="mu" style="color:var(--green)">都有備份 ✔</div>'}</div>`;
  $('#v').onclick=e=>{if(e.target.closest('[data-b="re"]'))rBak(false,true)}}
// ---- 🏷 依來源整理（V0.1.37）
let OSS=new Set(LS.get('oss',['screenshot'])),OSK=LS.get('osk',true);
async function rOsrc(again){const j=await api('/api/org',{a:'srcs'});if(!j.ok)return;const S=j.st||{};
  const stx=S.run?`<span style="color:var(--blue)">🏷 整理中：${(S.n||0).toLocaleString()}／${(S.total||0).toLocaleString()}</span> <button class="pill er" data-o="stop">⏹ 停止</button>`:(S.msg?'✔ '+esc(S.msg):'');
  if(again){const e=$('#ost');if(e)e.innerHTML=stx;if(S.run||ORUN){ORUN=S.run;if(!S.run){toast('🏷 '+(S.msg||'好了'),4000);rOsrc()}}return}
  const R=j.rows||[];
  $('#v').innerHTML=`<div class="panel"><div class="mu">照「從哪裡來的」分開放：截圖、抖音、LINE／微信、修圖過的、救援軟體救回的…各放一個資料夾，你自己拍的照片影片就不會被淹沒。<br>放到每顆硬碟的 <b>\\照片影片_依來源\\來源\\原本的資料夾名</b>；先預覽、同一顆硬碟搬、可以復原。</div><div id="ost" style="margin-top:6px">${stx}</div></div>
   <div class="panel"><h3 style="margin-top:0">勾要整理的來源</h3>${R.map(r=>`<label class="it row" style="gap:8px;flex-wrap:nowrap"><input type="checkbox" data-os="${esc(r.src)}" ${OSS.has(r.src)?'checked':''} ${r.src&&r.src!=='camera'?'':'disabled'}>
     <span class="grow">${esc(r.name)}${r.src==='camera'?' <span class="mu">（你拍的，不用搬）</span>':''}</span><span class="mu" style="white-space:nowrap">照片 ${(r.photo||0).toLocaleString()}・影片 ${(r.video||0).toLocaleString()}・${fmtB(r.b)}</span></label>`).join('')}
    <div class="si tgr"><b>保留原本的資料夾名<small>例如 截圖\\DCIM-Screenshots\\…；關掉＝同一個來源全部放一起</small></b><label class="tg"><input type="checkbox" id="osk" ${OSK?'checked':''}><i></i></label></div>
    <div class="row" style="margin-top:8px"><button class="pill acc" data-o="plan">👀 預覽（不會動任何檔）</button></div></div><div id="oplan"></div>`;
  $('#v').onchange=e=>{const c=e.target.closest('[data-os]');if(c){c.checked?OSS.add(c.dataset.os):OSS.delete(c.dataset.os);LS.set('oss',[...OSS])}if(e.target.id==='osk'){OSK=e.target.checked;LS.set('osk',OSK)}};
  $('#v').onclick=async e=>{const b=e.target.closest('[data-o]');if(!b)return;const a=b.dataset.o;
    if(a==='stop'){await api('/api/org',{a:'stop'});return}
    if(a==='plan'){$('#oplan').innerHTML='<div class="panel mu">預覽中…</div>';const r=await api('/api/org',{a:'plan_src',srcs:[...OSS],keep_dir:OSK});const el=$('#oplan');
      if(!r.ok){el.innerHTML=`<div class="panel" style="color:var(--red)">${esc(r.message||'失敗')}</div>`;return}
      el.innerHTML=`<div class="panel"><h3>👀 預覽：會搬 ${r.n.toLocaleString()} 個（${fmtB(r.b)}）</h3><div class="mu">整理到：${esc(r.dest_eg||'')}</div>
        <div class="mu" style="margin-top:4px">${r.months.map(([k,v])=>`${esc(k)} ${v[0].toLocaleString()} 個（${fmtB(v[1])}）`).join('・')}</div>
        <div class="mu" style="margin-top:4px">跳過：${Object.entries(r.skip).filter(([,v])=>v).map(([k,v])=>`${esc(k)} ${v.toLocaleString()}`).join('、')||'沒有'}</div>
        <h3 style="margin-top:10px">前 ${r.sample.length} 個會這樣搬</h3><div style="max-height:260px;overflow:auto;font-size:12px">${r.sample.map(x=>`<div class="it"><span class="mu">${esc(x.src)}</span><br>→ ${esc(x.dst)}</div>`).join('')}</div>
        ${r.n?`<div class="row" style="margin-top:10px"><button class="pill acc" data-o="run">🏷 開始整理（${r.n.toLocaleString()} 個）</button></div><div class="mu">每一筆都記下來，搬錯了在「📦 隔離區」→ 搬移紀錄可以復原。</div>`:''}</div>`;el.scrollIntoView({behavior:'smooth'});return}
    if(a==='run'){if(!confirm('開始依來源整理？\n\n只在同一顆硬碟裡搬（瞬間完成），可以在「📦 隔離區」復原。'))return;const r=await api('/api/org',{a:'run'});toast(r.message||'好了');ORUN=r.ok;$('#oplan').innerHTML='';rOsrc(true)}}}
// ---- 🗓 那年今天（總覽）＋時間軸（工具）
let ZSTART=0,ZAUTO=false;   // ZAUTO：打開就輪播（V0.1.94）   // ▶ 從這裡播（V0.1.74）：下一次打開影片從第幾秒開始
// 🖼 看大圖／播影片（V0.1.53：左右滑、‹ › 換上一張下一張；同一頁上的縮圖照順序）
const zoomImg=(id0,kind0,LST)=>{const Z=document.createElement('div');Z.style.cssText='position:fixed;inset:0;z-index:80;background:#000e;display:grid;place-items:center;touch-action:pan-y';
  const L=(LST||[...document.querySelectorAll('#v [data-zi]')].map(e=>[e.dataset.zi,e.dataset.zk||'photo'])).filter((x,i,a)=>a.findIndex(y=>y[0]===x[0])===i);
  let k=Math.max(0,L.findIndex(x=>x[0]==id0));if(!L.length||L[k][0]!=id0){L.splice(0,L.length,[String(id0),kind0||'photo']);k=0}
  const stage=document.createElement('div');stage.style.cssText='position:absolute;inset:0;display:grid;place-items:center';Z.appendChild(stage);
  let ZT=0;
  let SS=null;const ssStop=()=>{if(SS){clearTimeout(SS);SS=null}const b=bar&&bar.querySelector('[data-zb="ss"]');if(b){b.textContent='▶ 輪播';b.classList.remove('acc')}};
  const ssNext=()=>{if(!SS)return;const v=stage.querySelector('video');if(v&&!v.ended&&v.style.display!=='none'){SS=setTimeout(ssNext,1000);return}if(k>=L.length-1){ssStop();return toast('播完了')}k++;show();SS=setTimeout(ssNext,(+LS.get('ssec',4)||4)*1000)};
  const close=()=>{ssStop();const v=Z.querySelector('video');if(v){v.pause();v.removeAttribute('src');v.load()}document.removeEventListener('keydown',kd);Z.remove()};let real=close;
  const bar=document.createElement('div');bar.dataset.zf=1;bar.style.cssText='position:absolute;top:12px;right:12px;left:12px;display:flex;gap:6px;justify-content:flex-end;align-items:center;flex-wrap:wrap;z-index:2';
  bar.innerHTML=`<span data-zpos style="color:#ccc;font-size:12px;margin-right:auto"></span><button class="pill" data-zb="ss" title="自動一張一張播（4 秒換一張，影片播完才換）">▶ 輪播</button><button class="pill" data-zb="spd" title="影片播放速度（X 鍵）">${(+LS.get('zspd',1)||1)}x</button><button class="pill" data-zb="info">ℹ 資訊</button><a class="pill" data-zb="dl" download style="color:var(--text);text-decoration:none">⬇ 下載</a><button class="pill er" data-zb="q">📦 不要了</button><button class="pill" data-zb="fav" style="font-size:15px">☆ 最愛</button><button class="pill" data-zb="x">✕</button>`;Z.appendChild(bar);
  const nav=document.createElement('div');nav.dataset.zf=1;nav.style.cssText='position:absolute;bottom:14px;left:0;right:0;display:flex;justify-content:center;gap:14px;z-index:2';
  nav.innerHTML=`<button class="pill" data-zb="prev" style="font-size:20px;padding:6px 18px">‹</button><button class="pill" data-zb="next" style="font-size:20px;padding:6px 18px">›</button>`;Z.appendChild(nav);
  const ib=document.createElement('div');ib.dataset.zf=1;ib.style.cssText='position:absolute;left:12px;right:12px;bottom:64px;background:#000c;color:#eee;border-radius:10px;padding:10px 12px;font-size:12.5px;line-height:1.5;display:none;z-index:2;word-break:break-all';Z.appendChild(ib);
  const cur=()=>L[k][0],fb=()=>bar.querySelector('[data-zb="fav"]');
  const show=()=>{const v=stage.querySelector('video');if(v){v.pause();v.removeAttribute('src');v.load()}const [id,kind]=L[k];ib.style.display='none';
    stage.innerHTML=kind==='video'?`<video src="/api/play?id=${id}" controls autoplay playsinline style="max-width:100%;max-height:calc(100% - 120px);background:#000"></video><div data-zerr style="color:#fff;text-align:center;display:none;padding:20px">這個影片格式手機播不了（例如 HEVC／AVI）<br><img src="/api/fc_thumb?id=${id}&w=1600" style="max-width:90vw;max-height:50vh;margin-top:10px"></div>`
      :`<img src="/api/fc_thumb?id=${id}&w=1600" style="max-width:100%;max-height:100%" draggable="false">`;
    const vv=stage.querySelector('video');if(vv){const sp=+LS.get('zspd',1)||1;vv.playbackRate=sp;vv.addEventListener('loadedmetadata',()=>{try{vv.playbackRate=+LS.get('zspd',1)||1}catch(e){}},{once:true})}if(vv&&ZSTART){const t0=ZSTART;ZSTART=0;vv.addEventListener('loadedmetadata',()=>{try{vv.currentTime=t0}catch(e){}},{once:true})}if(vv)vv.onerror=()=>{stage.querySelector('[data-zerr]').style.display='block';vv.style.display='none'};
    bar.querySelector('[data-zb="dl"]').href=`/api/play?id=${id}&dl=1`;bar.querySelector('[data-zpos]').textContent=L.length>1?`${k+1}／${L.length}`:'';
    nav.style.display=L.length>1?'flex':'none';const f=fb();f.textContent='☆ 最愛';f.classList.remove('acc');
    api(U('/api/fav',{id})).then(j=>{if(cur()!==id)return;f.textContent=j.on?'⭐ 最愛':'☆ 最愛';f.classList.toggle('acc',!!j.on)});
    if(L[k+1]&&L[k+1][1]!=='video'){const p=new Image();p.src=`/api/fc_thumb?id=${L[k+1][0]}&w=1600`}};
  const step=d=>{const n=k+d;if(n<0||n>=L.length)return toast(n<0?'這是第一張':'這是最後一張');k=n;show()};
  const kd=e=>{const k_=e.key.toLowerCase(),cl=x=>{const b=bar.querySelector(`[data-zb="${x}"]`);if(b)b.click()};
    if(e.key==='ArrowRight')step(1);else if(e.key==='ArrowLeft')step(-1);else if(e.key==='Escape')ovClose(real);
    else if(k_===' '&&!stage.querySelector('video')){e.preventDefault();cl('ss')}else if(/^[0-9]$/.test(k_)&&CUR==='vc'&&VI.cats&&VI.cats.length){const id=+cur(),j=VI.ids.indexOf(id),ci=(+k_+9)%10;if(j>=0&&VI.cats[ci]){e.preventDefault();vcTagJ(j,ci).then(()=>{if(L.length>1)step(1)})}}   // 放大看時按數字＝分這一部（V0.3.16）
    else if(k_==='f')cl('fav');else if(k_==='x')cl('spd');else if(k_==='i')cl('info');else if(k_==='delete')cl('q')};document.addEventListener('keydown',kd);   // 鍵盤：← → 空白（輪播）F（最愛）I（資訊）Delete（不要了）（V0.3.14：以前這行被註解吃掉）
  let sx=null,sy=0;Z.addEventListener('touchstart',e=>{if(e.touches.length===1){sx=e.touches[0].clientX;sy=e.touches[0].clientY}},{passive:true});
  Z.addEventListener('touchend',e=>{if(sx==null)return;if(stage.querySelector('img[data-zm]')){sx=null;return}const t=e.changedTouches[0],dx=t.clientX-sx,dy=t.clientY-sy;sx=null;if(Math.abs(dx)>60&&Math.abs(dx)>Math.abs(dy)*1.5){Z.dataset.sw=1;step(dx<0?1:-1);setTimeout(()=>delete Z.dataset.sw,350)}},{passive:true});
  Z.onclick=async e=>{if(Z.dataset.sw)return;const b=e.target.closest('[data-zb]');
    if(!b){if(e.target.closest('[data-zf]')||e.target.closest('video'))return;
      const im=e.target.closest('img');                                   // 點兩下放大 2.5 倍（再點兩下還原），點一下關掉（V0.1.99）
      if(im){if(ZT){clearTimeout(ZT);ZT=0;if(im.dataset.zm){im.style.transform='';delete im.dataset.zm;Z.style.touchAction='pan-y'}else{const r=im.getBoundingClientRect();im.style.transformOrigin=`${e.clientX-r.left}px ${e.clientY-r.top}px`;im.style.transform='scale(2.5)';im.style.transition='transform .15s';im.dataset.zm=1;Z.style.touchAction='none'}return}
        ZT=setTimeout(()=>{ZT=0;if(!im.dataset.zm)ovClose(real)},280);return}
      return ovClose(real)}
    const a=b.dataset.zb,id=cur();if(a==='dl')return;e.preventDefault();
    if(a==='spd'){const S=[1,2,4,8],n=S[(S.indexOf(+LS.get('zspd',1)||1)+1)%S.length];LS.set('zspd',n);b.textContent=n+'x';const v=stage.querySelector('video');if(v)v.playbackRate=n;return toast(`⏩ ${n} 倍速`,1000)}
    if(a==='x')return ovClose(real);if(a==='prev'){ssStop();return step(-1)}if(a==='next')return step(1);
    if(a==='ss'){if(SS)return ssStop();if(L.length<2)return toast('只有一張');b.textContent='⏸ 停';b.classList.add('acc');SS=setTimeout(ssNext,(+LS.get('ssec',4)||4)*1000);return}
    if(a==='fav'){const f=fb(),on=!f.classList.contains('acc');const r=await api('/api/fav',{id:+id,on});if(r.ok){f.textContent=on?'⭐ 最愛':'☆ 最愛';f.classList.toggle('acc',on);toast(r.message)}return}
    if(a==='info'){if(ib.style.display==='block'){ib.style.display='none';return}const j=await api(U('/api/finfo',{id}));if(!j.ok)return;const f=j.f;
      ib.innerHTML=`<b>${esc(base(f.path))}</b><br>${esc(f.path)}<br>${fmtB(f.size)}${f.w?'・'+f.w+'×'+f.h:''}${f.dur?'・'+fmtT(f.dur):''}${f.vcodec?'・'+esc(f.vcodec):''}<br>📅 ${f.taken?day(f.taken):'（沒有拍攝日期）'}${f.date_src?' <span style="opacity:.7">（'+esc({exif:'照片 EXIF',video:'影片內建',name:'檔名',mtime:'修改日期'}[f.date_src]||f.date_src)+'）</span>':''}${(f.make||f.model)?'<br>📷 '+esc((f.make||'')+' '+(f.model||'')):''}${j.src_nm?'<br>🏷 '+esc(j.src_nm):''}${f.lat!=null&&f.lon!=null&&(f.lat||f.lon)?`<br>📍 <a style="color:#4dc9ff" target="_blank" rel="noopener" href="https://www.google.com/maps?q=${f.lat},${f.lon}">${(+f.lat).toFixed(4)}, ${(+f.lon).toFixed(4)}</a>`:''}`;ib.style.display='block';return}
    if(a==='q'){if(!confirm('把這個檔搬到隔離區？（可以在「📦 隔離區」復原）'))return;const r=await api('/api/fc_quar_many',{ids:[+id]});toast(r.message||(r.ok?'搬好了':'失敗'));
      if(r.ok){const el=document.querySelector(`#v [data-zi="${id}"]`);if(el)el.style.opacity=.25;L.splice(k,1);if(!L.length)return ovClose(real);k=Math.min(k,L.length-1);show()}}};
  document.body.appendChild(Z);show();ovOpen(real);if(ZAUTO&&L.length>1){ZAUTO=false;const b=bar.querySelector('[data-zb="ss"]');b.textContent='⏸ 停';b.classList.add('acc');SS=setTimeout(ssNext,(+LS.get('ssec',4)||4)*1000)}ZAUTO=false};
// 長按縮圖的快速選單（V0.2.02）：⭐ 最愛、📂 看資料夾、📦 不要了
document.addEventListener('contextmenu',async e=>{const t=e.target.closest('#v [data-zi]');if(!t)return;e.preventDefault();const id=t.dataset.zi;
  const j=await api(U('/api/finfo',{id}));if(!j.ok)return;const f=j.f,d=f.path.replace(/[\\/][^\\/]*$/,'');
  const Z=document.createElement('div');Z.style.cssText='position:fixed;inset:0;z-index:88;background:#0008;display:flex;align-items:flex-end;justify-content:center';
  Z.innerHTML=`<div class="panel" style="width:100%;max-width:520px;margin:0 0 10px;border-radius:16px"><div style="font-size:12.5px;word-break:break-all;margin-bottom:8px"><b>${esc(base(f.path))}</b><br><span class="mu">${fmtB(f.size)}・${f.taken?day(f.taken).slice(0,16):''}</span></div>
   <div style="display:grid;gap:6px">${[['open','🖼 打開'],['fav',f.fav?'☆ 取消最愛':'⭐ 加到最愛'],['dir','📂 看它的資料夾'],['vc','🎞 在分類頁看這個資料夾'],['q','📦 不要了（搬隔離區）'],['x','取消']].map(([k,n])=>`<button class="pill ${k==='q'?'er':''}" data-cm="${k}" style="padding:10px;text-align:left">${n}</button>`).join('')}</div></div>`;
  const real=()=>Z.remove();Z.onclick=async ev=>{const b=ev.target.closest('[data-cm]');if(!b&&ev.target!==Z)return;const k=b?b.dataset.cm:'x';ovClose(real);
    if(k==='open')return setTimeout(()=>zoomImg(id,t.dataset.zk),350);
    if(k==='fav'){const r=await api('/api/fav',{id:+id,on:!f.fav});return toast(r.message)}
    if(k==='dir'){BRP=d;BRO=0;LS.set('brp',BRP);return setTimeout(()=>go('tool:br'),350)}
    if(k==='vc'){VC.folder=d;VC.f='all';VC.kind=f.kind==='photo'?'photo':'video';LS.set('vc',VC);return setTimeout(()=>go('vc'),350)}
    if(k==='q'){if(!confirm('把這個檔搬到隔離區？（可以復原）'))return;const r=await api('/api/fc_quar_many',{ids:[+id]});toast(r.message||'好了');if(r.ok)t.style.opacity=.25}};
  document.body.appendChild(Z);ovOpen(real)});
// 長的說明文字先收成兩行（ℹ 開頭），點一下展開（V0.2.09：畫面簡單一點）
document.addEventListener('click',e=>{const m=e.target.closest('#v .mu.clamp');if(m&&!m.classList.contains('open')&&!e.target.closest('a,button,input,select'))m.classList.add('open')});
let CLT=0;new MutationObserver(()=>{clearTimeout(CLT);CLT=setTimeout(()=>{document.querySelectorAll('#v .panel>.mu:not([data-cl]),#v .panel>div.mu:not([data-cl])').forEach(m=>{m.dataset.cl=1;
  if(m.textContent.length>90&&!m.querySelector('button,input,select,a,ul,img')&&!m.id)m.classList.add('clamp')});
  const st=document.getElementById('subT'),h=document.querySelector('#v>.panel:first-child>h3:first-child');   // 上面已經有標題：卡片裡重複的標題拿掉
  if(st&&h&&st.offsetParent&&h.textContent.trim()===st.textContent.trim())h.style.display='none'},60)}).observe(document.getElementById('v'),{childList:true,subtree:true});
const slideFrom=el=>{const f=el&&el.querySelector('[data-zi]');if(!f)return toast('沒有照片');ZAUTO=true;zoomImg(f.dataset.zi,f.dataset.zk)};
const tthumb=(r,w)=>`<div data-zi="${r.id}" data-zk="${r.kind}" style="position:relative;cursor:pointer;${w?`flex:none;width:${w}px`:''}"><img loading="lazy" src="/api/fc_thumb?id=${r.id}&w=320" style="width:100%;aspect-ratio:1;object-fit:cover;border-radius:6px;background:#1a1f27;display:block">${r.kind==='video'?`<span style="position:absolute;right:3px;bottom:3px;background:#000b;color:#fff;font-size:10px;padding:0 4px;border-radius:4px">▶ ${fmtT(r.dur)}</span>`:''}</div>`;
async function dashOtd(){const el=$('#dotd');if(!el)return;let j;try{j=await api('/api/otd')}catch(e){return}if(!$('#dotd')||!j.ok||!j.n){if(el)el.innerHTML='';return}
  el.innerHTML=`<div class="panel"><div class="row"><h3 class="grow" style="margin:0">🗓 那年今天（${esc(j.md.replace('-','月'))}日）</h3><span class="mu">${j.n.toLocaleString()} 個</span><button class="pill" data-slide style="margin-left:6px">▶ 輪播</button></div>
   ${j.years.map(Y=>`<div style="margin-top:8px"><b>${Y.ago} 年前・${Y.y}</b> <span class="mu">${Y.n} 個</span><div style="display:flex;gap:5px;overflow-x:auto;margin-top:4px">${Y.rows.map(r=>tthumb(r,96)).join('')}</div></div>`).join('')}</div>`;
  el.onclick=e=>{if(e.target.closest('[data-slide]')){e.stopPropagation();return slideFrom(el)}const t=e.target.closest('[data-zi]');if(t){e.stopPropagation();zoomImg(t.dataset.zi,t.dataset.zk)}}}
// 總覽要顯示哪幾塊（V0.1.73，設定 → 外觀）
const DSEC=[['dq','🔎 搜尋框'],['dadv','💡 建議你接下來做'],['dvcp','🎞 審片進度'],['dhist','📉 整理進度'],['dotd','🗓 那年今天'],['drnd','🎲 隨機回憶'],['dev','🧳 最近的活動'],['djobs','🖥 背景工作'],['dana','📈 資料分析'],['dfold','📁 資料夾清單']];
// 📍 地名（V0.1.75）：手機直接問 OpenStreetMap 的 Nominatim（一秒一個、記在手機裡），只傳座標、不傳照片
const PLQ=[];let PLT=0;
function placeFill(root){(root||document).querySelectorAll('[data-place]:not([data-pf])').forEach(el=>{el.dataset.pf=1;const [a,b]=el.dataset.place.split(',').map(Number),k=a.toFixed(2)+','+b.toFixed(2),C=LS.get('places',{});
  if(C[k]!==undefined){el.textContent=C[k]?'📍 '+C[k]:'';return}PLQ.push([k,a,b,el])});if(!PLT)plNext()}
function plNext(){const x=PLQ.shift();if(!x){PLT=0;return}PLT=1;const [k,a,b,el]=x,C=LS.get('places',{});if(C[k]!==undefined){el.textContent=C[k]?'📍 '+C[k]:'';return plNext()}
  fetch(`https://nominatim.openstreetmap.org/reverse?format=json&zoom=10&accept-language=zh-TW&lat=${a}&lon=${b}`).then(r=>r.json()).then(j=>{const A=j.address||{};
    const big=A.city||A.county||A.state||'',small=A.town||A.suburb||A.village||A.city_district||'';
    const nm=((A.country_code&&A.country_code!=='tw'&&A.country?A.country+'・':'')+big+(small&&small!==big?small:''))||(j.name||'');
    const C2=LS.get('places',{});C2[k]=nm;LS.set('places',C2);document.querySelectorAll(`[data-place]`).forEach(e=>{const [p,q]=e.dataset.place.split(',').map(Number);if(p.toFixed(2)+','+q.toFixed(2)===k)e.textContent=nm?'📍 '+nm:''})})
   .catch(()=>{}).finally(()=>setTimeout(plNext,1100))}
// 🎲 隨機回憶（V0.1.72）：每次打開總覽隨機 12 張你拍的
async function dashRnd(){const el=$('#drnd');if(!el)return;let j;try{j=await api('/api/random?n=12')}catch(e){return}if(!$('#drnd')||!j.ok||!j.rows.length){if(el)el.innerHTML='';return}
  el.innerHTML=`<div class="panel"><div class="row"><h3 class="grow" style="margin:0">🎲 隨機回憶</h3><button class="pill" data-slide>▶ 輪播</button><button class="pill" data-rr>🔄 換一批</button></div>
   <div style="display:flex;gap:5px;overflow-x:auto;margin-top:6px">${j.rows.map(r=>tthumb(r,96)).join('')}</div><div class="mu" style="font-size:11.5px;margin-top:4px">點一張打開，按「▶ 輪播」一張張看</div></div>`;
  el.onclick=e=>{if(e.target.closest('[data-slide]')){e.stopPropagation();return slideFrom(el)}if(e.target.closest('[data-rr]')){e.stopPropagation();return dashRnd()}const t=e.target.closest('[data-zi]');if(t){e.stopPropagation();zoomImg(t.dataset.zi,t.dataset.zk)}}}
// 📉 整理進度（V0.1.63）：每天一個點，看重複、有問題的有沒有變少、分好的有沒有變多
async function dashHist(){const el=$('#dhist');if(!el)return;let j;try{j=await api('/api/hist')}catch(e){return}if(!$('#dhist')||!j.ok)return;const R=j.rows||[];if(R.length<2){el.innerHTML='';return}
  const sp=(k,col,fmt,good)=>{const v=R.map(r=>+r[k]||0),mn=Math.min(...v),mx=Math.max(...v),w=120,h=34,d=v[v.length-1]-v[0];
    const pts=v.map((x,i)=>`${(i/(v.length-1)*w).toFixed(1)},${(h-2-(mx>mn?(x-mn)/(mx-mn):.5)*(h-4)).toFixed(1)}`).join(' ');
    const ok=good==='down'?d<=0:d>=0;return`<div style="flex:1;min-width:140px"><div class="mu" style="font-size:11.5px">${fmt[0]}</div><b>${fmt[1](v[v.length-1])}</b> <span style="font-size:11.5px;color:${d===0?'var(--sub)':ok?'var(--green)':'var(--orange)'}">${d>0?'▲':d<0?'▼':'—'} ${d?fmt[1](Math.abs(d)):''}</span>
      <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="width:100%;height:${h}px;display:block"><polyline points="${pts}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg></div>`};
  el.innerHTML=`<div class="panel"><div class="row"><h3 class="grow" style="margin:0">📉 整理進度</h3><span class="mu" style="font-size:11.5px">${R[0].t?day(R[0].t).slice(5,10):''} → 今天</span></div><div class="row" style="gap:12px;margin-top:6px;flex-wrap:wrap">
    ${sp('dup_b','var(--green)',['🔁 重複可以省',fmtB],'down')}${sp('bad','var(--red)',['🩺 有問題',x=>x.toLocaleString()+' 個'],'down')}${sp('tagged','var(--purple)',['🎞 分好的影片',x=>x.toLocaleString()+' 部'],'up')}${sp('bytes','var(--blue)',['📁 照片影片總大小',fmtB],'down')}</div></div>`}
// 🧳 最近的活動（V0.1.49）：總覽上最新 3 次出遊／聚會
async function dashEv(){const el=$('#dev');if(!el)return;let j;try{j=await api(U('/api/events',{gap:6,min:15}))}catch(e){return}if(!$('#dev')||!j.ok||!j.n){if(el)el.innerHTML='';return}
  const dd=t=>{const d=new Date(t*1000);return`${d.getFullYear()}/${d.getMonth()+1}/${d.getDate()}`};
  el.innerHTML=`<div class="panel"><div class="row"><h3 class="grow" style="margin:0">🧳 最近的活動</h3><a href="#" class="mu" data-go="tool:evt">全部 ${j.n.toLocaleString()} 次 ›</a></div>
   ${j.rows.slice(0,3).map(e=>`<div style="margin-top:8px"><b>${dd(e.t0)}${e.days>1?' ～ '+dd(e.t1):''}</b> <span class="mu">${e.n.toLocaleString()} 個</span>${e.gps?` <span data-place="${e.gps[0]},${e.gps[1]}" style="color:var(--accent);font-size:12.5px"></span>`:''}
    <div style="display:flex;gap:5px;overflow-x:auto;margin-top:4px">${e.cover.map(id=>`<img loading="lazy" src="/api/fc_thumb?id=${id}&w=240" data-zi="${id}" data-zk="photo" style="width:96px;aspect-ratio:1;object-fit:cover;border-radius:6px;flex:none;background:#1a1f27;cursor:pointer">`).join('')}</div></div>`).join('')}</div>`;
  placeFill(el);
  el.onclick=e=>{const t=e.target.closest('[data-zi]');if(t){e.stopPropagation();zoomImg(t.dataset.zi,t.dataset.zk)}const g=e.target.closest('[data-go]');if(g){e.preventDefault();e.stopPropagation();go(g.dataset.go)}}}
let TLS=LS.get('tl',{y:'',m:'',k:''}),TLO=0,TLH=LS.get('tlh','');
// 🔥 每天拍了多少（V0.1.47）：GitHub 那種格子，越深越多；點一天看那天的
async function tlHeat(y,ys){const el=$('#tlh');if(!el)return;TLH=y;LS.set('tlh',y);const j=await api(U('/api/tl',{y,heat:1}));if(!j.ok||!$('#tlh'))return;const D=j.days||{};
  const v=Object.values(D).sort((a,b)=>a-b),q=p=>v.length?v[Math.min(v.length-1,Math.floor(v.length*p))]:1,Q=[q(.25),q(.5),q(.75),q(.92)];
  const lv=n=>!n?0:n<=Q[0]?1:n<=Q[1]?2:n<=Q[2]?3:4,col=['var(--track)','#1f5f8b','#2b86c5','#4dc9ff','#b8ecff'];
  const d0=new Date(+y,0,1),off=d0.getDay(),days=(new Date(+y+1,0,1)-d0)/864e5,cells=[];
  for(let i=0;i<off;i++)cells.push('<i></i>');
  for(let i=0;i<days;i++){const d=new Date(+y,0,1+i),k=`${y}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`,n=D[k]||0;
    cells.push(`<i ${n?`data-hd="${k}"`:''} title="${k}：${n}" style="background:${col[lv(n)]};${n?'cursor:pointer':''}"></i>`)}
  const tot=v.reduce((a,b)=>a+b,0),best=Object.entries(D).sort((a,b)=>b[1]-a[1])[0];
  el.innerHTML=`<div class="row" style="flex-wrap:nowrap"><h3 class="grow" style="margin:0">🔥 每天拍了多少</h3><select id="tlhy">${ys.map(x=>`<option ${x===y?'selected':''}>${x}</option>`).join('')}</select></div>
   <div class="mu" style="font-size:12px;margin:4px 0">${y} 年有拍的 ${v.length} 天・共 ${tot.toLocaleString()} 個${best?`・最多是 ${best[0]}（${best[1]} 個）`:''}。點格子看那天的。</div>
   <div style="overflow-x:auto;padding-bottom:4px"><div style="display:grid;grid-auto-flow:column;grid-template-rows:repeat(7,11px);grid-auto-columns:11px;gap:2px;width:max-content">${cells.join('')}</div></div><style>#tlh [data-hd],#tlh i{border-radius:2px}</style><div id="tlhd"></div>`;
  $('#tlhy').onchange=()=>tlHeat($('#tlhy').value,ys)}
async function tlDay(k){const el=$('#tlhd');if(!el)return;const j=await api(U('/api/tl',{day:k}));if(!j.ok)return;
  el.innerHTML=`<div class="row" style="margin-top:8px"><b class="grow">📅 ${k}・${j.rows.length}${j.rows.length>=120?'+':''} 個</b><button class="pill" data-dslide>▶ 輪播</button></div><div style="display:grid;grid-template-columns:repeat(${innerWidth<500?4:8},1fr);gap:4px;margin-top:4px">${j.rows.map(r=>tthumb(r)).join('')}</div>`}
async function rTl(again){if(again)return;const T=$('#v');
  if(!TLS.y){const j=await api('/api/tl');const Y=j.years||{},ys=Object.keys(Y).sort().reverse();const mx=Math.max(1,...ys.flatMap(y=>Object.values(Y[y]).map(m=>m.photo+m.video)));
    T.innerHTML=`<div class="panel"><div class="mu">只用可靠的拍攝日期（EXIF／影片內建／檔名）。點一個月看裡面的照片影片。</div></div>`+(ys.length?`<div class="panel" id="tlh"></div>`:'')+(ys.map(y=>{const M=Y[y],n=Object.values(M).reduce((a,m)=>a+m.photo+m.video,0);
      return `<div class="panel"><div class="row"><h3 class="grow" style="margin:0">${y}</h3><span class="mu">${n.toLocaleString()} 個・${fmtB(Object.values(M).reduce((a,m)=>a+m.b,0))}</span></div>
       <div style="display:grid;grid-template-columns:repeat(12,1fr);gap:3px;align-items:end;height:70px;margin-top:6px">${Array.from({length:12},(_,i)=>{const k=String(i+1).padStart(2,'0'),m=M[k];const v=m?m.photo+m.video:0;
        return `<button data-ty="${y}" data-tm="${k}" ${v?'':'disabled'} title="${y}-${k}：${v}" style="height:100%;display:flex;flex-direction:column;justify-content:flex-end;border:0;background:none;padding:0"><i style="display:block;height:${v?Math.max(6,100*v/mx):2}%;background:${v?'var(--blue)':'var(--track)'};border-radius:3px 3px 0 0"></i><small style="font-size:9.5px;color:var(--sub)">${i+1}</small></button>`}).join('')}</div></div>`}).join('')||'<div class="panel mu">還沒有可靠日期的照片影片（要等「讀取拍攝資訊」做完）</div>');
    if(ys.length)tlHeat(ys.includes(String(TLH))?String(TLH):ys[0],ys);
    T.onclick=e=>{const z=e.target.closest('[data-zi]');if(z)return zoomImg(z.dataset.zi,z.dataset.zk);if(e.target.closest('[data-dslide]'))return slideFrom($('#tlhd'));const h=e.target.closest('[data-hd]');if(h)return tlDay(h.dataset.hd);const b=e.target.closest('[data-ty]');if(!b)return;TLS={y:b.dataset.ty,m:b.dataset.tm,k:''};LS.set('tl',TLS);TLO=0;rTl()};return}
  const j=await api(U('/api/tl',{y:TLS.y,m:TLS.m,o:TLO,k:TLS.k}));if(!j.ok)return;
  const head=`<div class="panel"><div class="row"><button class="pill" data-tb="1">‹ 回到年份</button><b class="grow" style="text-align:center">${j.y} 年 ${j.m} 月・${j.n.toLocaleString()} 個</b>
     <select id="tlk"><option value="">全部</option><option value="photo" ${TLS.k==='photo'?'selected':''}>照片</option><option value="video" ${TLS.k==='video'?'selected':''}>影片</option></select><button class="pill" data-tslide style="margin-left:6px">▶ 輪播</button></div>
     <div class="row" style="margin-top:6px"><button class="pill" data-tp="-1">‹ 上個月</button><span class="grow"></span><button class="pill" data-tp="1">下個月 ›</button></div></div>`;
  const grid=`<div style="display:grid;grid-template-columns:repeat(${innerWidth<500?4:8},1fr);gap:4px" id="tlg">${j.rows.map(r=>tthumb(r)).join('')}</div>`+(TLO+60<j.n?`<div class="row" style="justify-content:center;margin:10px"><button class="pill" data-tmore="1">再載入 60 個（${(TLO+60).toLocaleString()}／${j.n.toLocaleString()}）</button></div>`:'');
  if(TLO&&$('#tlg')){$('#tlg').insertAdjacentHTML('beforeend',j.rows.map(r=>tthumb(r)).join(''));const mb=$('[data-tmore]');if(mb)mb.parentElement.outerHTML=TLO+60<j.n?`<div class="row" style="justify-content:center;margin:10px"><button class="pill" data-tmore="1">再載入 60 個（${(TLO+60).toLocaleString()}／${j.n.toLocaleString()}）</button></div>`:'';return}
  T.innerHTML=head+grid;$('#tlk').onchange=()=>{TLS.k=$('#tlk').value;LS.set('tl',TLS);TLO=0;rTl()};
  T.onclick=e=>{const t=e.target;if(t.closest('[data-tslide]'))return slideFrom($('#tlg'));const z=t.closest('[data-zi]');if(z)return zoomImg(z.dataset.zi,z.dataset.zk);
    if(t.closest('[data-tb]')){TLS={y:'',m:'',k:''};LS.set('tl',TLS);return rTl()}
    if(t.closest('[data-tmore]')){TLO+=60;return rTl()}
    const p=t.closest('[data-tp]');if(p){let y=+TLS.y,m=+TLS.m+(+p.dataset.tp);if(m<1){m=12;y--}if(m>12){m=1;y++}TLS.y=String(y);TLS.m=String(m).padStart(2,'0');LS.set('tl',TLS);TLO=0;rTl()}}}
// ---- 🗜 影片瘦身（V0.1.34）
let SLMB=LS.get('slmb',200),SLSEL=new Set(),SLRUN=false;
// V0.4.62 🗜 影片瘦身改成 VS V0.4.59 的樣子：🎞 選片／⚙ 轉檔中／✅ 轉好的 三個分頁；🎯 每部先用 5 段樣本找「SSIM ≥ 0.985」最省的 CQ，轉完抽查 3 段、低於 0.975 重轉
let SLT=LS.get('slt','pick'),SLDF='all',SLDQ='';
async function rSlim(again){const SLW=LS.get('slw','tagged');const j=await api(U('/api/slim',{mb:SLMB,w:SLW}));if(!j.ok)return;const st=j.st||{},ts=st.test||{},C=j.cfg||{target:0.985,floor:0.975};
  const ssC=v=>v>=C.target-1e-9?'var(--green)':v>=C.floor?'var(--orange)':'var(--red)';
  const tried=T=>Object.entries(T||{}).sort((a,b)=>a[0]-b[0]).map(([q,v])=>`<span style="color:${v==null?'var(--sub)':ssC(v)}">CQ${q}＝${v==null?'失敗':(+v).toFixed(3)}</span>`).join('　');
  const runH=st.run?`<div class="panel" style="border-color:var(--blue)"><div class="row"><b class="grow">⚙ ${st.n}／${st.total}：<span style="word-break:break-all">${esc(st.cur||'')}</span></b><button class="pill er" data-l="stop">⏹ 停止</button></div>
     <div class="mu" style="margin-top:4px">${esc(st.phase||'')}${/轉檔|重轉/.test(st.phase||'')?' · '+(st.pct||0)+'%':''}</div>${/轉檔|重轉/.test(st.phase||'')?`<div class="pg" style="margin-top:4px;height:6px;background:#2a303a;border-radius:3px"><i style="display:block;height:100%;border-radius:3px;background:var(--blue);width:${st.pct||0}%"></i></div>`:''}
     ${st.tried&&Object.keys(st.tried).length?`<div class="mu" style="font-size:11.5px;margin-top:4px">🎯 ${tried(st.tried)}</div>`:''}
     <div class="mu" style="margin-top:4px">好了 ${st.ok||0} 部・保留原檔 ${st.keep||0}・沒成功 ${st.bad||0}・已省 <b style="color:var(--green)">${fmtB(st.saved)}</b></div></div>`
    :(st.msg?`<div class="panel">✔ ${esc(st.msg)}${(st.err||[]).length?`<div class="mu" style="font-size:11px;margin-top:4px">${st.err.slice(-5).map(esc).join('<br>')}</div>`:''}</div>`:'');
  const tsH=ts.run||ts.res||ts.err?`<div class="panel" style="border-color:var(--accent)"><div class="row"><b class="grow">🧪 試轉：<span style="word-break:break-all">${esc(ts.name||'')}</span></b>${ts.run?'<button class="pill" data-l="tstop">⏹</button>':''}</div>
     ${ts.run?`<div class="mu">${esc(ts.phase||'')}</div>`:''}${ts.err?`<div style="color:var(--red)">${esc(ts.err)}</div>`:''}
     ${ts.res?`<div style="margin-top:4px">🎯 用 <b>CQ ${ts.res.q}</b>：樣本 SSIM <b style="color:${ssC(ts.res.ssim)}">${(+ts.res.ssim).toFixed(4)}</b>${ts.res.ok?' ✔':'（⚠ 最好也沒到 '+C.target+'）'}・整部預估 <b>${fmtB(ts.res.pred)}</b>（原檔 ${fmtB(ts.res.osz)}，變成 <b style="color:var(--green)">${Math.round(ts.res.pred*100/Math.max(1,ts.res.osz))}%</b>）</div>
       <div class="mu" style="font-size:11.5px">${ts.res.cmp} 比・${esc(ts.res.enc||'')}・找了 ${Math.round(ts.res.sec||0)} 秒・5 段：${(ts.res.V||[]).map(v=>(+v).toFixed(3)).join(', ')}</div>`:''}
     ${Object.keys(ts.tried||ts.res&&ts.res.tried||{}).length?`<div class="mu" style="font-size:11.5px;margin-top:3px">${tried(ts.res?ts.res.tried:ts.tried)}</div>`:''}</div>`:'';
  if(again){if(SLT==='run'||SLT==='pick'){const e=$('#slst');if(e)e.innerHTML=runH+tsH}const nb=$('#slrn');if(nb)nb.textContent=st.run?` ${st.n}／${st.total}`:'';if((st.run||ts.run)!==SLRUN){const was=SLRUN;SLRUN=!!(st.run||ts.run);if(was&&!SLRUN)rSlim()}return}
  SLRUN=!!(st.run||ts.run);
  const R=j.rows||[];const ratio=j.ratio||[0.5,0];
  const tabs=`<div class="seg" id="sltab" style="width:100%;margin-bottom:8px">${[['pick','🎞 選片'],['run','⚙ 轉檔中<span id="slrn">'+(st.run?' '+st.n+'／'+st.total:'')+'</span>'],['done','✅ 轉好的']].map(([k,n])=>`<button data-t="${k}" style="flex:1"${SLT===k?' class="on"':''}>${n}</button>`).join('')}</div>`;
  const head=`<div class="panel"><h3 style="margin-top:0">🗜 影片瘦身 <span class="mu" style="font-size:12px;font-weight:400">H.265・跟 VS 一樣的 🎯 畫質目標</span></h3>
    <div class="mu">🎯 每一部先從片長 10%～90% 取 5 段各 2 秒，試不同畫質（CQ 18～40），跟原檔同一段比 <b>SSIM</b>（1＝一模一樣，0.98 以上肉眼看不出來），找<b>中間值 ≥ ${C.target}</b> 裡最省的；轉完再抽 3 段，<b>低於底線 ${C.floor}</b> 就調高畫質重轉（最多 2 次），還是不到 → 不用轉好的、原檔不動。<br>新檔叫「原檔名_h265.mp4」，原檔搬到「🗜 轉檔後隔離區」（可以復原，不會刪）。</div>
    <div class="row" style="margin-top:8px;gap:6px"><span class="mu">方式</span><select id="slq">${Object.entries(j.qual||{}).map(([k,n])=>`<option value="${k}" ${k===j.q?'selected':''}>${esc(n)}</option>`).join('')}</select>
     <button class="pill" data-l="tgt">目標 SSIM ${C.target}</button><button class="pill" data-l="flr">底線 ${C.floor}</button>${j.enc?`<span class="mu">編碼器 ${esc(j.enc)}</span>`:''}</div></div>`;
  let body='';
  if(SLT==='pick'){
    body=`<div class="panel"><div class="kv"><span>可以瘦身</span><b>${(j.n||0).toLocaleString()} 部（${fmtB(j.bytes)}）</b><span>預估可以省</span><b style="color:var(--green)">${fmtB(j.save)}</b><span></span><span class="mu">${ratio[1]>=3?'照已轉好的 '+ratio[1]+' 部平均 '+Math.round(ratio[0]*100)+'% 估':'先用解析度大概估'}</span></div>
    <div class="row" style="margin-top:8px;gap:6px"><span class="mu">只列大於</span><select id="slmb">${[100,200,500,1000,2000].map(m=>`<option value="${m}" ${m==SLMB?'selected':''}>${m>=1000?m/1000+' GB':m+' MB'}</option>`).join('')}</select>
     <select id="slw" title="只列哪些影片（V0.4.61）">${[['tagged','已分類的（不含 Delete）'],['moved','已經搬進分類資料夾的'],['wait','分好、還沒搬的'],['untagged','還沒分類的'],['all','全部']].map(([k,n])=>`<option value="${k}" ${k===SLW?'selected':''}>${n}</option>`).join('')}</select></div>
    <div class="row" style="margin-top:8px"><button class="pill acc" data-l="sel">🗜 瘦身勾選的（<span id="sln">${SLSEL.size}</span>）</button><button class="pill" data-l="top">勾最大的 10 部</button><button class="pill" data-l="none">全部取消</button></div></div>
    <div id="slst">${runH+tsH}</div>
   <div class="panel">${R.length?R.map(r=>`<label class="it row" style="flex-wrap:nowrap;gap:8px;align-items:center"><input type="checkbox" data-ls="${r.id}" ${SLSEL.has(r.id)?'checked':''}>
     <img loading="lazy" src="/api/vc_thumb?id=${r.id}" data-zv="${r.id}" style="width:72px;aspect-ratio:16/10;object-fit:cover;border-radius:5px;background:#1a1f27;flex:none;cursor:pointer">
     <span class="grow" style="min-width:0"><b style="word-break:break-all">${esc(base(r.path))}</b><br><span class="mu" style="font-size:11px">${fmtT(r.dur)}・${r.w?r.w+'×'+r.h+'・':''}${esc(r.vcodec||'?')}・${(r.br/1e6).toFixed(1)} Mbps</span></span>
     <span style="text-align:right;white-space:nowrap;font-size:12px">${fmtB(r.size)}<br><span style="color:var(--green)">省 ~${fmtB(r.save)}</span><br><button class="pill" data-tst="${r.id}" style="font-size:11px;padding:2px 7px;margin-top:2px" title="5 段樣本找設定，看會變多大、畫質多少（檔案不會動）">🧪 試轉</button></span></label>`).join(''):'<div class="mu">沒有找到值得瘦身的（都已經是新編碼或不大）</div>'}
    ${j.n>R.length?`<div class="mu">只列最大的 ${R.length} 部</div>`:''}</div>`}
  else if(SLT==='run'){body=`<div id="slst">${runH+tsH||''}</div>${st.run||ts.run||st.msg?'':'<div class="panel"><div class="empty">沒有在轉 👍（到「🎞 選片」勾影片開始）</div></div>'}`}
  else{const D=await api('/api/slim_run',{a:'done',f:SLDF,q:SLDQ});if(!D.ok)return;const L=D.rows||[];
    body=`<div class="panel"><div>轉好 <b>${D.n.toLocaleString()}</b> 部：${fmtB(D.osz)} → ${fmtB(D.nsz)}，省下 <b style="color:var(--green)">${fmtB(Math.max(0,D.osz-D.nsz))}</b>${D.osz?'（變成 '+Math.round(D.nsz*100/D.osz)+'%）':''}</div>
     <div class="mu">${D.qn?`🗜 轉檔後隔離區裡還有 <b style="color:var(--orange)">${D.qn}</b> 個原檔（抽檢沒問題再到「📦 隔離區 → 🗜 轉檔後隔離區」自己處理；這裡不會刪）`:'轉檔後隔離區裡沒有原檔'}</div>
     ${D.warn?`<div style="color:var(--orange);margin-top:4px">⚠ ${D.warn} 部畫質沒到目標 ${C.target}（但都在底線 ${C.floor} 以上）：建議抽檢</div>`:''}
     <div class="row" style="margin-top:8px"><button class="pill" data-l="rand">🎲 隨機抽 5 部抽檢</button>${D.warn&&D.qn?`<button class="pill" data-l="rvlow" style="color:var(--orange)">↩ 沒到目標的還原（${D.warn}）</button>`:''}</div></div>
     <div class="row" style="margin:8px 0;gap:6px"><input class="search grow" id="sldq" placeholder="🔍 找檔名（按 Enter）" value="${esc(SLDQ)}" style="min-width:0"></div>
     <div class="seg" id="sldf" style="margin-bottom:8px;width:100%">${[['all','全部'],['warn','⚠ 要看'+(D.warn?' '+D.warn:'')],['unseen','沒抽檢'+(D.unseen?' '+D.unseen:'')],['undone','已還原'+(D.undone?' '+D.undone:'')]].map(([k,n])=>`<button data-k="${k}" style="flex:1"${SLDF===k?' class="on"':''}>${n}</button>`).join('')}</div>
     <div class="mu" style="margin-bottom:6px">點縮圖＝播放轉好的 _h265 抽檢（看過會打 ✔）</div>
     <div class="panel list">${L.map(r=>{const ss=r.score||0;return `<div class="it row" style="flex-wrap:nowrap;gap:8px;align-items:center">${r.new_ok&&r.nfid?`<img loading="lazy" src="/api/vc_thumb?id=${r.nfid}" data-sv="${r.id}" data-nf="${r.nfid}" style="width:72px;aspect-ratio:16/10;object-fit:cover;border-radius:5px;background:#1a1f27;flex:none;cursor:pointer">`:''}
       <div class="grow" style="min-width:0"><div style="word-break:break-all">${r.viewed?'✔ ':''}${r.undone?'↩ ':''}${esc(r.name)}</div>
       <div class="mu" style="font-size:11.5px">${fmtB(r.osz)} → ${fmtB(r.nsz)} · 省 <span style="color:var(--green)">${fmtB(Math.max(0,r.osz-r.nsz))}</span> · ${Math.round(r.nsz*100/Math.max(1,r.osz))}% · SSIM <b style="color:${ss?ssC(ss):'var(--sub)'}">${ss?ss.toFixed(3):'—'}</b>${r.spot?'（抽查）':r.ssim?'（樣本）':''} · CQ ${r.q} · ${esc(r.enc||'')}</div>
       <div class="mu" style="font-size:11px">${new Date(r.t*1000).toLocaleString()} · ${esc(r.note||'')}${r.orig_q?' · 原檔在轉檔後隔離區':''}</div></div>
       ${!r.undone&&r.orig_q?`<button class="pill" data-rv="${r.id}" style="flex:none">↩ 還原</button>`:''}</div>`}).join('')||'<div class="empty">沒有</div>'}</div>`}
  $('#v').innerHTML=head+tabs+body;
  $('#sltab').onclick=e=>{const b=e.target.closest('[data-t]');if(!b)return;SLT=b.dataset.t;LS.set('slt',SLT);rSlim()};
  if($('#slmb'))$('#slmb').onchange=()=>{SLMB=+$('#slmb').value;LS.set('slmb',SLMB);rSlim()};if($('#slw'))$('#slw').onchange=()=>{LS.set('slw',$('#slw').value);SLSEL.clear();rSlim()};
  if($('#sldf'))$('#sldf').onclick=e=>{const b=e.target.closest('[data-k]');if(!b)return;SLDF=b.dataset.k;rSlim()};
  if($('#sldq'))$('#sldq').onkeydown=e=>{if(e.key==='Enter'){SLDQ=e.target.value.trim();rSlim()}};
  const cnt=()=>{const e=$('#sln');if(e)e.textContent=SLSEL.size};
  $('#v').onchange=e=>{const c=e.target.closest('[data-ls]');if(c){const id=+c.dataset.ls;c.checked?SLSEL.add(id):SLSEL.delete(id);cnt()}};
  $('#v').onclick=async e=>{const z=e.target.closest('[data-zv]');if(z){e.preventDefault();return zoomImg(z.dataset.zv,'video',R.map(x=>[String(x.id),'video']))}
    const sv=e.target.closest('[data-sv]');if(sv){api('/api/slim_run',{a:'seen',ids:[+sv.dataset.sv]});return zoomImg(sv.dataset.nf,'video',[[sv.dataset.nf,'video']])}
    const tb=e.target.closest('[data-tst]');if(tb){e.preventDefault();const r=await api('/api/slim_run',{a:'test',id:+tb.dataset.tst});toast(r.message||'',5000);SLRUN=true;return rSlim()}
    const rv=e.target.closest('[data-rv]');if(rv){if(!confirm('還原這部？\n• 原檔從「🗜 轉檔後隔離區」搬回原位\n• 轉好的 _h265 搬進轉檔後隔離區（不刪，可以再復原）\n• 分類跟回原檔'))return;const r=await api('/api/slim_run',{a:'revert',ids:[+rv.dataset.rv]});toast(r.message||'',5000);return rSlim()}
    const b=e.target.closest('[data-l]');if(!b)return;const a=b.dataset.l;let r;
    if(a==='top'){R.slice(0,10).forEach(x=>SLSEL.add(x.id));return rSlim()}if(a==='none'){SLSEL.clear();return rSlim()}
    if(a==='tgt'||a==='flr'){const k=a==='tgt'?'target':'floor';const v=prompt(a==='tgt'?'目標 SSIM（找「樣本中間值 ≥ 這個」最省的設定；VS 預設 0.985）':'底線 SSIM（轉完抽查低於這個就重轉；VS 預設 0.975）',C[k]);if(!v)return;r=await api('/api/slim_run',{a:'cfg',[k]:+v});toast(r.message||'');return rSlim()}
    if(a==='stop')r=await api('/api/slim_run',{a:'stop'});
    if(a==='tstop')r=await api('/api/slim_run',{a:'test_stop'});
    if(a==='rand'){const D=await api('/api/slim_run',{a:'done',f:'unseen'});const P=(D.rows||[]).filter(x=>x.new_ok&&x.nfid).sort(()=>Math.random()-.5).slice(0,5);if(!P.length)return toast('都抽檢過了 👍');api('/api/slim_run',{a:'seen',ids:P.map(x=>x.id)});return zoomImg(String(P[0].nfid),'video',P.map(x=>[String(x.nfid),'video']))}
    if(a==='rvlow'){const D=await api('/api/slim_run',{a:'done',f:'warn'});const P=(D.rows||[]).filter(x=>x.orig_q);if(!P.length)return toast('沒有可以還原的');if(!confirm(`畫質沒到目標的 ${P.length} 部全部還原？（原檔搬回原位、_h265 進轉檔後隔離區，不刪）`))return;r=await api('/api/slim_run',{a:'revert',ids:P.map(x=>x.id)});toast(r.message||'',5000);return rSlim()}
    if(a==='sel'){if(!SLSEL.size)return toast('先勾要瘦身的影片');const S=R.filter(x=>SLSEL.has(x.id)),sv=S.reduce((s,x)=>s+x.save,0),qv=$('#slq').value;
      if(!confirm(`瘦身 ${SLSEL.size} 部（預估省 ${fmtB(sv)}）？\n\n• ${qv==='auto'?'🎯 每部先用 5 段樣本找「SSIM ≥ '+C.target+'」最省的設定，轉完抽查、低於 '+C.floor+' 重轉':'固定畫質'}\n• 新檔：原檔名_h265.mp4（同一個資料夾）\n• 成功才把原檔搬到「🗜 轉檔後隔離區」（可以復原）\n• 很花電腦時間：可以隨時停`))return;
      r=await api('/api/slim_run',{a:'start',ids:[...SLSEL],q:qv});if(r.ok){SLSEL.clear();SLT='run';LS.set('slt',SLT)}}
    if(r){toast(r.message||'好了');SLRUN=true;rSlim()}}}
// ---- 📄 匯出報告（V0.1.31）
async function rRep(again){if(again)return;const T=$('#v');const j=await api('/api/report?list=1');if(!j.ok)return;
  T.innerHTML=`<div class="panel"><h3 style="margin-top:0">📄 匯出報告</h3><div class="mu">把現在的整理狀況做成一頁：硬碟、檔案種類、每年拍多少、最佔空間的重複檔、有問題的照片影片、雜物、遊戲／軟體、影片分類、去過的地方、最近搬過的。<br>只是「看」，不會改任何檔案；在瀏覽器按「分享 → 列印」可以存成 PDF。</div>
    <div class="row" style="margin-top:10px"><button class="pill acc" data-r="new" style="padding:10px 18px">📄 做一份新的報告</button></div></div>
   <div class="panel"><h3 style="margin-top:0">以前做的</h3>${j.rows.length?j.rows.map(r=>`<div class="it row"><span class="grow">${esc(r.name.replace('FileCompare_報告_','').replace('.html',''))}</span><span class="mu">${fmtB(r.size)}</span><a class="pill" target="_blank" href="/api/report?f=${encodeURIComponent(r.name)}">打開</a></div>`).join(''):'<div class="mu">還沒有</div>'}
    <div class="mu" style="margin-top:6px">電腦上存在 FileCompare 的 Data\\reports，最多留 20 份</div></div>`;
  T.onclick=e=>{if(e.target.closest('[data-r="new"]')){toast('做報告中…（幾秒）');window.open('/api/report','_blank');setTimeout(()=>rRep(),4000)}}}
// ---- 🗺 照片地圖（V0.1.30）：自己畫的小地圖（OpenStreetMap 底圖），拖曳、兩指縮放、點一群看照片
let GEO=LS.get('geo',{z:3,lat:23.7,lon:121,k:''}),GCL={},GSEL=null,GO=0;
// V0.5.90 底圖：OpenStreetMap 官方伺服器擋掉這種 App（403 Access blocked）→ 預設改 CARTO（一樣是 OpenStreetMap 的資料），也可以換衛星
const GBASE={voy:['🗺 一般','https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png','© OpenStreetMap © CARTO'],dark:['🌙 深色','https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png','© OpenStreetMap © CARTO'],
  sat:['🛰 衛星','https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}','© Esri, Maxar, Earthstar'],osm:['OSM 原版','https://tile.openstreetmap.org/{z}/{x}/{y}.png','© OpenStreetMap']};
const geoB=()=>GBASE[LS.get('geob','voy')]?LS.get('geob','voy'):'voy';
const geoTile=(z,x,y)=>GBASE[geoB()][1].replace('{s}','abcd'[(x+y)%4]).replace('{z}',z).replace('{x}',x).replace('{y}',y);
const g2p=(lat,lon,z)=>{const s=256*2**z,sl=Math.sin(Math.max(-85,Math.min(85,lat))*Math.PI/180);return[(lon+180)/360*s,(0.5-Math.log((1+sl)/(1-sl))/(4*Math.PI))*s]};
const p2g=(x,y,z)=>{const s=256*2**z,n=Math.PI-2*Math.PI*y/s;return[180/Math.PI*Math.atan(Math.sinh(n)),x/s*360-180]};
const fmtD=t=>{if(!t)return'';const d=new Date(t*1000);return`${d.getFullYear()}/${d.getMonth()+1}/${d.getDate()}`};
async function geoData(){const key=GEO.z+'|'+GEO.k+'|'+(GEO.y||'');if(!GCL[key]){const j=await api(U('/api/geo',{z:GEO.z,k:GEO.k,y:GEO.y||''}));if(!j.ok)return null;GCL[key]=j;}return GCL[key]}
async function geoDraw(){const M=$('#gmap');if(!M)return;const W=M.clientWidth,H=M.clientHeight,z=GEO.z,n=2**z;let [cx,cy]=g2p(GEO.lat,GEO.lon,z);
  const ox=cx-W/2,oy=cy-H/2,t=[];
  for(let ty=Math.floor(oy/256);ty<=Math.floor((oy+H)/256);ty++){if(ty<0||ty>=n)continue;for(let tx=Math.floor(ox/256);tx<=Math.floor((ox+W)/256);tx++){const wx=((tx%n)+n)%n;
    t.push(`<img src="${geoTile(z,wx,ty)}" referrerpolicy="strict-origin-when-cross-origin" style="position:absolute;left:${tx*256-ox}px;top:${ty*256-oy}px;width:256px;height:256px" draggable="false" onerror="this.style.visibility='hidden'">`)}}
  $('#gtl').innerHTML=t.join('');$('#gtl').style.transform='';$('#gmk').style.transform='';
  const j=await geoData();if(!j||!$('#gmap'))return;const S=j.sum||{};
  $('#gsum').innerHTML=S.n?`📍 ${S.n.toLocaleString()} 個有位置 <span class="mu">（照片 ${S.photo.toLocaleString()}・影片 ${S.video.toLocaleString()}，全部 ${S.all.toLocaleString()} 個裡的 ${S.all?Math.round(100*S.n/S.all):0}%）</span>`:'<span class="mu">還沒有找到有 GPS 的照片影片（要先「讀取拍攝資訊」；手機拍照要開定位）</span>';
  const mx=Math.max(1,...j.cl.map(c=>c.n));
  $('#gmk').innerHTML=j.cl.map(c=>{const [x,y]=g2p(c.lat,c.lon,z);let L=x-ox;const T_=y-oy;const w=256*n;if(L<-40)L+=w*Math.ceil(-L/w);if(L>W+40)L-=w*Math.ceil((L-W)/w);if(L<-40||L>W+40||T_<-40||T_>H+40)return'';
    const r=Math.round(16+22*Math.log(1+c.n)/Math.log(1+mx)),sel=GSEL&&GSEL.gy===c.gy&&GSEL.gx===c.gx&&GSEL.z===z;
    return`<div data-gc="${c.gy},${c.gx}" data-n="${c.n}" style="position:absolute;left:${L-r/2}px;top:${T_-r/2}px;width:${r}px;height:${r}px;border-radius:50%;display:grid;place-items:center;cursor:pointer;
      background:${sel?'var(--orange)':'var(--blue)'};color:#fff;font-size:${r>30?12:10}px;font-weight:800;border:2px solid #fff;box-shadow:0 1px 6px #0008">${c.n>999?Math.round(c.n/100)/10+'k':c.n}</div>`}).join('')}
function geoFit(){GCL={};geoData().then(j=>{if(!j)return;const b=j.sum&&j.sum.box;if(!b)return geoDraw();const M=$('#gmap'),W=M.clientWidth,H=M.clientHeight;let z=16;
  for(;z>1;z--){const a=g2p(b[1],b[2],z),c=g2p(b[0],b[3],z);if(c[0]-a[0]<W*0.85&&c[1]-a[1]<H*0.85)break}
  const a=g2p(b[1],b[2],z),c=g2p(b[0],b[3],z),g=p2g((a[0]+c[0])/2,(a[1]+c[1])/2,z);GEO={...GEO,z,lat:g[0],lon:g[1]};LS.set('geo',GEO);geoDraw()})}
function geoZoom(d,px,py){const M=$('#gmap'),W=M.clientWidth,H=M.clientHeight;const nz=Math.max(1,Math.min(18,GEO.z+d));if(nz===GEO.z)return;
  px=px==null?W/2:px;py=py==null?H/2:py;const [cx,cy]=g2p(GEO.lat,GEO.lon,GEO.z),f=2**(nz-GEO.z),ax=cx-W/2+px,ay=cy-H/2+py;
  const g=p2g(ax*f-px+W/2,ay*f-py+H/2,nz);GEO={...GEO,z:nz,lat:g[0],lon:g[1]};LS.set('geo',GEO);geoDraw()}
async function geoCell(o){const C=$('#gcell');if(!C||!GSEL)return;const j=await api(U('/api/geo',{z:GSEL.z,gy:GSEL.gy,gx:GSEL.gx,o:o||0,k:GEO.k,y:GEO.y||''}));if(!j.ok)return;
  const R=j.rows,t0=R.length?R[0].taken:0,t1=R.length?R[R.length-1].taken:0,c=R[0]||{};
  const head=`<div class="panel"><div class="row"><b class="grow">${c.lat!=null?`<span data-place="${c.lat},${c.lon}" style="color:var(--accent)"></span> `:''}📍 這附近 ${j.n.toLocaleString()} 個 <span class="mu">${fmtD(t0)}${t1&&fmtD(t1)!==fmtD(t0)?' ～ '+fmtD(t1):''}</span></b>
    <button class="pill" data-g="zin">🔍 放大這裡</button><a class="pill" target="_blank" rel="noopener" href="https://www.google.com/maps?q=${c.lat},${c.lon}">🌐 Google 地圖</a></div></div>`;
  const more=(o||0)+60<j.n?`<div class="row" style="justify-content:center;margin:10px"><button class="pill" data-g="more">再載入 60 個（${((o||0)+60).toLocaleString()}／${j.n.toLocaleString()}）</button></div>`:'';
  if(o&&$('#gcg')){$('#gcg').insertAdjacentHTML('beforeend',R.map(r=>tthumb(r)).join(''));const m=$('[data-g="more"]');if(m)m.parentElement.outerHTML=more;return}
  setTimeout(()=>placeFill(C),0);C.innerHTML=head+`<div id="gcg" style="display:grid;grid-template-columns:repeat(${innerWidth<500?4:8},1fr);gap:4px">${R.map(r=>tthumb(r)).join('')}</div>`+more}
async function rGeo(again){if(again)return;const T=$('#v');GSEL=null;GO=0;
  T.innerHTML=`<div class="panel" style="padding:8px 10px"><div class="row" style="gap:6px"><span id="gsum" class="grow"></span><select id="gk"><option value="">照片＋影片</option><option value="photo" ${GEO.k==='photo'?'selected':''}>只看照片</option><option value="video" ${GEO.k==='video'?'selected':''}>只看影片</option></select><select id="gy"><option value="">全部年份</option></select><select id="gb">${Object.entries(GBASE).map(([k,v])=>`<option value="${k}"${geoB()===k?' selected':''}>${v[0]}</option>`).join('')}</select><button class="pill" data-g="fit">🌏 看全部</button></div></div>
   <div id="gmap" style="position:relative;height:min(60vh,560px);overflow:hidden;border-radius:10px;background:#1b2330;touch-action:none;user-select:none;-webkit-user-select:none">
    <div id="gtl" style="position:absolute;inset:0"></div><div id="gmk" style="position:absolute;inset:0"></div>
    <div style="position:absolute;right:8px;top:8px;display:flex;flex-direction:column;gap:6px;z-index:3"><button class="pill" data-g="in" style="font-size:20px;width:42px;height:42px;padding:0">＋</button><button class="pill" data-g="out" style="font-size:20px;width:42px;height:42px;padding:0">－</button></div>
    <div style="position:absolute;right:4px;bottom:2px;font-size:10px;color:#333;background:#fffc;padding:0 4px;border-radius:3px;z-index:3" id="gattr">${GBASE[geoB()][2]}</div></div>
   <div class="mu" style="font-size:12px;margin:4px 2px">拖曳移動、兩指或 ＋－ 縮放；點圓圈看那附近拍的。底圖要手機能上網，照片位置不會傳出去（只有地圖格子）。</div><div id="gcell"></div>`;
  const M=$('#gmap'),P=new Map();let st=null,moved=false;
  const tr=(dx,dy,s)=>{for(const e of [$('#gtl'),$('#gmk')]){e.style.transformOrigin=st?`${st.px}px ${st.py}px`:'';e.style.transform=`translate(${dx}px,${dy}px)`+(s&&s!==1?` scale(${s})`:'')}};
  M.onpointerdown=e=>{if(e.target.closest('button,a'))return;M.setPointerCapture(e.pointerId);P.set(e.pointerId,[e.clientX,e.clientY]);const r=M.getBoundingClientRect(),v=[...P.values()];
    if(v.length===1)st={x:e.clientX,y:e.clientY,dx:0,dy:0,s:1,px:e.clientX-r.left,py:e.clientY-r.top,d0:0,tg:e.target};
    else if(v.length===2){st.d0=Math.hypot(v[0][0]-v[1][0],v[0][1]-v[1][1]);st.px=(v[0][0]+v[1][0])/2-r.left;st.py=(v[0][1]+v[1][1])/2-r.top}moved=false};
  M.onpointermove=e=>{if(!st||!P.has(e.pointerId))return;P.set(e.pointerId,[e.clientX,e.clientY]);const v=[...P.values()];
    if(v.length>=2&&st.d0){st.s=Math.hypot(v[0][0]-v[1][0],v[0][1]-v[1][1])/st.d0;moved=true;tr(st.dx,st.dy,st.s);return}
    st.dx=e.clientX-st.x;st.dy=e.clientY-st.y;if(Math.abs(st.dx)+Math.abs(st.dy)>6)moved=true;if(moved)tr(st.dx,st.dy,st.s)};
  M.onpointerup=M.onpointercancel=e=>{P.delete(e.pointerId);if(P.size||!st)return;const s=st;st=null;
    if(!moved){const c=s.tg&&s.tg.closest&&s.tg.closest('[data-gc]');if(c){const [gy,gx]=c.dataset.gc.split(',').map(Number);GSEL={z:GEO.z,gy,gx};geoDraw();geoCell(0);setTimeout(()=>$('#gcell').scrollIntoView({behavior:'smooth',block:'start'}),200)}return}
    const [cx,cy]=g2p(GEO.lat,GEO.lon,GEO.z),g=p2g(cx-s.dx,cy-s.dy,GEO.z);GEO={...GEO,lat:g[0],lon:g[1]};
    const d=s.s!==1?Math.round(Math.log2(s.s)):0;if(d)geoZoom(d,s.px,s.py);else{LS.set('geo',GEO);geoDraw()}};
  M.onwheel=e=>{e.preventDefault();const r=M.getBoundingClientRect();geoZoom(e.deltaY<0?1:-1,e.clientX-r.left,e.clientY-r.top)};
  geoData().then(j=>{const el=$('#gy');if(!j||!el)return;el.innerHTML='<option value="">全部年份</option>'+(j.years||[]).map(y=>`<option ${GEO.y===y?'selected':''}>${y}</option>`).join('')});
  $('#gy').onchange=()=>{GEO.y=$('#gy').value;LS.set('geo',GEO);GSEL=null;$('#gcell').innerHTML='';geoDraw()};
  $('#gb').onchange=()=>{LS.set('geob',$('#gb').value);const at=$('#gattr');if(at)at.textContent=GBASE[geoB()][2];geoDraw()};
  $('#gk').onchange=()=>{GEO.k=$('#gk').value;LS.set('geo',GEO);GCL={};GSEL=null;$('#gcell').innerHTML='';geoDraw()};
  T.onclick=e=>{const z=e.target.closest('[data-zi]');if(z)return zoomImg(z.dataset.zi,z.dataset.zk);const b=e.target.closest('[data-g]');if(!b)return;const a=b.dataset.g;
    if(a==='in')geoZoom(1);if(a==='out')geoZoom(-1);if(a==='fit')geoFit();if(a==='more'){GO+=60;geoCell(GO)}
    if(a==='zin'&&GSEL){const j=GCL[GSEL.z+'|'+GEO.k+'|'+(GEO.y||'')],c=j&&j.cl.find(x=>x.gy===GSEL.gy&&x.gx===GSEL.gx);if(c){GEO={...GEO,lat:c.lat,lon:c.lon,z:Math.min(18,GSEL.z+3)};LS.set('geo',GEO);geoDraw();$('#gmap').scrollIntoView({behavior:'smooth'})}}};
  if(!LS.get('geo_seen',0)){LS.set('geo_seen',1);geoFit()}else geoDraw()}
// ---- 📁 重複資料夾
let DRUN=false;
async function rDdir(again){const j=await api('/api/ddir');if(!j.ok)return;const S=j.st||{};
  const stx=S.run?`<span style="color:var(--blue)">📁 搬到隔離區中：${(S.n||0).toLocaleString()}／${(S.total||0).toLocaleString()}</span>`:(S.msg?'✔ '+esc(S.msg):'');
  if(again){const e=$('#dst');if(e)e.innerHTML=stx;if(S.run||DRUN){DRUN=S.run;if(!S.run)rDdir()}return}
  const P=j.pairs||[];
  $('#v').innerHTML=`<div class="panel"><div id="dst">${stx}</div><div class="mu">兩個資料夾有很多一模一樣的照片影片（例如備份、手機資料夾複製了好幾次）。選「保留哪一個」：另一個裡面「這邊也有一模一樣的」才搬到隔離區，另一個獨有的完全不動。</div></div>`+
   (P.map((p,i)=>`<div class="panel"><div class="row" style="flex-wrap:nowrap"><b class="grow">${p.n.toLocaleString()} 個一樣・${fmtB(p.b_bytes)}</b></div>
     <div class="it"><b>A</b> <span style="word-break:break-all">${esc(p.a)}</span><br><span class="mu">共 ${p.na.toLocaleString()} 個，${p.pa}% 在 B 也有</span><i class="kb" style="--kc:var(--blue)"><u style="width:${Math.min(100,p.pa)}%"></u></i></div>
     <div class="it"><b>B</b> <span style="word-break:break-all">${esc(p.b)}</span><br><span class="mu">共 ${p.nb.toLocaleString()} 個，${p.pb}% 在 A 也有</span><i class="kb" style="--kc:var(--orange)"><u style="width:${Math.min(100,p.pb)}%"></u></i></div>
     <div class="row" style="margin-top:6px"><button class="pill acc" data-dk="${i}" data-w="a">保留 A（搬走 B 裡一樣的）</button><button class="pill acc" data-dk="${i}" data-w="b">保留 B（搬走 A 裡一樣的）</button></div></div>`).join('')||'<div class="panel mu">沒有找到（要等「比對重複」做完）</div>');
  $('#v').onclick=async e=>{const b=e.target.closest('[data-dk]');if(!b)return;const p=P[+b.dataset.dk],k=b.dataset.w==='a'?p.a:p.b,o=b.dataset.w==='a'?p.b:p.a;
    if(!confirm(`保留：${k}\n\n搬走：${o} 裡面「保留的那邊也有一模一樣的」${p.n.toLocaleString()} 個左右（${fmtB(p.b_bytes)}）\n\n搬到隔離區、可以復原。`))return;
    const r=await api('/api/ddir',{keep:k,other:o});toast(r.message||'好了');DRUN=r.ok;rDdir(true)}}
// ---- 📦 隔離區
const QQ={off:0,all:false};
async function rQ(again){if(again)return;const j=await api(U('/api/fc_moves',{offset:QQ.off,all:QQ.all?1:0,r:QQ.r||'',cv:QQ.cv?1:0}));if(!j.ok)return;const R=j.rows||[],RS=j.reasons||[];
  $('#v').innerHTML=`<div class="panel"><div class="row" style="gap:6px;margin-bottom:8px"><button class="pill ${QQ.cv?'':'acc'}" data-qcv="0">📦 一般隔離區</button><button class="pill ${QQ.cv?'acc':''}" data-qcv="1">🗜 轉檔後隔離區${j.conv_n?' '+j.conv_n.toLocaleString():''}</button></div>
   <h3>${QQ.cv?'🗜 轉檔後隔離區':'📦 隔離區'}　<span class="mu">共 ${(j.n||0).toLocaleString()} 筆</span></h3>${QQ.cv?'<div class="mu" style="margin-bottom:6px">影片瘦身（轉成 H.265，新檔叫「原檔名_h265.mp4」）後，原檔放在這裡、沒有刪掉。確定新檔都沒問題，再到電腦上自己刪掉各硬碟的「_FileCompare_轉檔後隔離區」資料夾；要原檔就勾起來按「↩ 復原」。</div>':''}<div class="row"><select id="qa"><option value="0">還在隔離區的</option><option value="1" ${QQ.all?'selected':''}>全部紀錄（含已復原）</option></select>
   <button class="pill" data-a="prev">◀</button><button class="pill" data-a="next">▶</button><span class="grow"></span><button class="pill" data-a="undo">↩ 復原勾選的</button><button class="pill er" data-a="all">↩ 全部復原</button></div>
   <div class="mu" style="margin-top:4px">確定不要了，再到電腦上自己刪掉各硬碟的「_FileCompare_待確認」資料夾。</div>
   ${(j.drives||[]).length?`<div style="margin-top:6px">${j.drives.map(([q,n,b])=>`<div class="row" style="flex-wrap:nowrap;font-size:12.5px"><span class="grow" style="word-break:break-all">💽 ${esc(q)}</span><b style="white-space:nowrap">${n.toLocaleString()} 個・${fmtB(b)}</b></div>`).join('')}</div>`:''}
   ${RS.length?`<div class="row" style="margin-top:8px;gap:5px;flex-wrap:wrap"><button class="pill ${QQ.r?'':'acc'}" data-qr="">全部</button>${RS.map(([k,n])=>`<button class="pill ${QQ.r===k?'acc':''}" data-qr="${esc(k)}">${esc(k)} ${n.toLocaleString()}</button>`).join('')}</div>`:''}
   ${QQ.r?`<div class="row" style="margin-top:6px"><button class="pill er" data-a="ur">↩ 復原「${esc(QQ.r)}」全部</button><span class="mu" style="font-size:12px">例如依來源整理搬錯了，一次全部搬回去</span></div>`:''}</div>
   <style>.qwrap{display:flex;gap:10px;align-items:flex-start}.qwrap>.qls{flex:1;min-width:0}#qpv{display:none;flex:0 0 46%;position:sticky;top:6px;max-height:calc(100vh - 110px);overflow:auto;margin:0}
    .qcur{background:color-mix(in srgb,var(--accent,#4dc9ff) 14%,transparent);border-radius:8px}.qpg{display:grid;grid-template-columns:repeat(4,1fr);gap:3px}.qpg>div{position:relative;border-radius:4px;background:#000 no-repeat;overflow:hidden}
    .qpg>div>i{position:absolute;left:3px;bottom:2px;font:600 10px/1 system-ui;color:#fff;text-shadow:0 0 3px #000;font-style:normal}
    @media (max-width:819px){#qpv{position:fixed;left:0;right:0;bottom:0;top:auto;max-height:70vh;z-index:80;flex:none;border-radius:16px 16px 0 0;box-shadow:0 -8px 30px #0008}}</style>
   <div class="qwrap"><div class="panel qls">${R.map((m,i)=>`<label class="it row" data-qrow="${i}" style="align-items:flex-start">${m.undone==2?'<span class="mu">🗑</span>':m.undone?'<span class="mu">↩</span>':`<input type="checkbox" value="${m.id}">`}<span class="grow" style="word-break:break-all"><b ${m.fid&&m.undone!=2?`data-qp="${i}" style="cursor:pointer"`:''}>${esc(base(m.src))}</b><div class="mu">${day(m.t)}・${esc(m.reason)}${m.undone==2?'・<b style="color:var(--red)">檔案已經刪掉（不能復原、不能預覽）</b>':''}</div><div class="mu">原本：${esc(m.src)}</div></span>${m.fid&&m.undone!=2?`<button class="pill" data-qp="${i}" title="看 16 格預覽" style="flex:none">🎞</button>`:''}</label>`).join('')||'<div class="mu">沒有</div>'}</div><div class="panel" id="qpv"></div></div>`;
  QQ.R=R;
  $('#qa').onchange=()=>{QQ.all=$('#qa').value==='1';QQ.off=0;rQ()};
  $('#v').onclick=async e=>{if(CUR!=='tool:q')return;const qp=e.target.closest('[data-qp]');if(qp){e.preventDefault();e.stopPropagation();return qPrev(+qp.dataset.qp)}
    const qx=e.target.closest('[data-qpx]');if(qx){e.preventDefault();const k=qx.dataset.qpx;if(k==='x'){$('#qpv').style.display='none';$$('.qcur').forEach(x=>x.classList.remove('qcur'));return}
      if(k==='p'||k==='n'){let i=QQ.pi+(k==='p'?-1:1);while(QQ.R[i]&&(QQ.R[i].undone==2||!QQ.R[i].fid))i+=(k==='p'?-1:1);if(QQ.R[i])qPrev(i);return}
      if(k==='u'){const m=QQ.R[QQ.pi];if(!m)return;const r=await api('/api/fc_undo',{ids:[m.id]});toast(r.message||'失敗',4000);if(r.ok)rQ();return}}
    const cvb=e.target.closest('[data-qcv]');if(cvb){QQ.cv=cvb.dataset.qcv==='1';QQ.r='';QQ.off=0;return rQ()}const q=e.target.closest('[data-qr]');if(q){QQ.r=q.dataset.qr;QQ.off=0;return rQ()}const b=e.target.closest('[data-a]');if(!b)return;const a=b.dataset.a;
    if(a==='ur'){if(!confirm(`把「${QQ.r}」搬過的全部搬回原本的位置？`))return;toast('復原中…',20000);const r=await api('/api/fc_undo',{reason:QQ.r});toast(r.message||'失敗',5000);QQ.r='';return rQ()}
    if(a==='prev'){QQ.off=Math.max(0,QQ.off-100);return rQ()}if(a==='next'){if(QQ.off+100<j.n)QQ.off+=100;return rQ()}
    let body;if(a==='undo'){const ids=$$('#v input[type=checkbox]:checked').map(x=>+x.value);if(!ids.length)return toast('先勾選要復原的');body={ids}}
    else if(a==='all'){if(!confirm(QQ.cv?'把轉檔後隔離區裡所有的原檔都搬回原本的位置？（_h265 新檔不動）':'把隔離區裡所有的檔案都搬回原本的位置？（轉檔後隔離區不算）'))return;body={all:true,cv:QQ.cv?1:0}}else return
    toast('復原中…',20000);const r=await api('/api/fc_undo',body);toast(r.message||'失敗',5000);rQ()}}

async function qPrev(i){const m=(QQ.R||[])[i],P=$('#qpv');if(!m||!P)return;QQ.pi=i;$$('.qcur').forEach(x=>x.classList.remove('qcur'));const row=$(`[data-qrow="${i}"]`);if(row)row.classList.add('qcur');   // V0.5.77 📦 隔離區預覽 16 格
  P.style.display='block';const hd=`<div class="row" style="gap:6px;flex-wrap:nowrap"><b class="grow" style="word-break:break-all;font-size:13px">${esc(base(m.src))}</b><button class="pill" data-qpx="p">◀</button><button class="pill" data-qpx="n">▶</button><button class="pill" data-qpx="x">✕</button></div>`;
  P.innerHTML=hd+'<div class="mu" style="padding:24px;text-align:center">🎞 做預覽中…（第一次要幾秒）</div>';
  let j;try{j=await api('/api/quar_cells?id='+m.fid)}catch(e){j={ok:false,message:String(e)}}if(QQ.pi!==i||!$('#qpv'))return;
  const inf=j&&j.name!=null?`<div class="mu" style="margin:4px 0 6px">${j.size?fmtB(j.size):''}${j.dur?'・'+Math.floor(j.dur/60)+':'+String(Math.round(j.dur%60)).padStart(2,'0'):''}${j.w?'・'+j.w+'×'+j.h:''}・${esc(m.reason)}${j.hmsg?`<br><span style="color:var(--orange)">${esc(j.hmsg)}</span>`:''}</div>`:'';
  if(!j||!j.ok){P.innerHTML=hd+inf+`<div class="mu" style="padding:18px;text-align:center;color:var(--orange)">⚠ ${esc((j&&j.message)||'沒辦法預覽')}</div>${m.undone?'':'<div class="row"><button class="pill" data-qpx="u">↩ 復原這個</button></div>'}`;return}
  const body=j.photo?`<img src="/api/fc_thumb?id=${m.fid}&w=1000&wait=1" style="width:100%;border-radius:6px">`:`<div class="qpg">${j.cells.map(c=>`<div style="aspect-ratio:${j.ar};background-image:url('/api/vc_img?id=${m.fid}&s=${c.s}');background-size:${j.cols*100}% ${j.rows*100}%;background-position:${j.cols>1?c.c/(j.cols-1)*100:0}% ${j.rows>1?c.r/(j.rows-1)*100:0}%"><i>${Math.floor(c.t/60)}:${String(Math.floor(c.t%60)).padStart(2,'0')}</i></div>`).join('')}</div>`;
  P.innerHTML=hd+inf+body+`<div class="row" style="margin-top:8px">${m.undone?'':'<button class="pill" data-qpx="u">↩ 復原這個</button>'}<span class="grow"></span><span class="mu" style="font-size:12px">◀ ▶ 看上一部／下一部</span></div>`}
const CST={run:['▶ 進行中','var(--green)'],idle:['— 沒事','var(--sub)'],pause:['⏸ 暫停中','var(--red)'],hold:['⚖ 讓路中','var(--orange)']};
async function rBg(again,T){T=T||$('#v');const j=await api('/api/state');if(!j.ok||!T.isConnected)return;const c=j.ctl;const st=T.scrollTop||0;
  T.innerHTML=`<div class="panel"><h3>⏯ 總控制　<span class="mu">CPU ${c.cpu}%${c.guard?` · 超過 ${c.cpu_max}% 自動讓路`:' · 自動讓路關'}</span></h3>
  ${c.kinds.map(k=>{const [nm,col]=CST[k.state]||[k.state,'var(--sub)'];return `<div class="it"><div class="row"><b>${k.prio}. ${k.icon} ${esc(k.name)}</b><span style="color:${col};font-weight:800">${nm}</span><span class="grow"></span><span class="mu">${k.pct!=null?k.pct+'%（'+k.done+'／'+k.total+'）':''}</span></div>
   ${k.pct!=null?`<div class="pg" style="margin:4px 0"><i style="width:${k.pct}%"></i></div>`:''}${k.last?`<div class="mu">${k.state==='pause'?'⏸ 停在':'最近'}：${esc(k.last)}</div>`:''}${k.held?`<div class="mu" style="color:var(--orange)">${esc(k.held)}</div>`:''}
   <div class="row" style="margin-top:5px">${k.state==='pause'?`<button class="pill ok" data-a="resume" data-k="${k.k}">▶ 繼續</button>`:`<button class="pill wa" data-a="pause" data-k="${k.k}">⏸ 暫停</button>`}${k.running?`<button class="pill er" data-a="stop" data-k="${k.k}">⏹ 立刻停</button>`:''}<button class="pill" data-a="up" data-k="${k.k}">↑</button><button class="pill" data-a="down" data-k="${k.k}">↓</button></div></div>`}).join('')}
  <div class="row" style="margin-top:8px"><button class="pill" data-a="all_pause">⏸ 全部暫停</button><button class="pill" data-a="all_resume">▶ 全部繼續</button><button class="pill" data-a="guard" data-on="${c.guard?0:1}">自動讓路：${c.guard?'開':'關'}</button></div>
  ${c.log&&c.log.length?`<div class="mu" style="margin-top:6px">${c.log.slice(0,5).map(esc).join('<br>')}</div>`:''}</div>`;
  if(T!==$('#v'))T.scrollTop=st;
  T.onclick=async e=>{const b=e.target.closest('[data-a]');if(!b)return;const a=b.dataset.a;if(a==='stop'&&!confirm('立刻停：正在做的也停掉、放回排隊？'))return;
    const body={a,k:b.dataset.k};if(a==='guard')body.on=b.dataset.on==='1';const r=await api('/api/bgctl',body);toast(r.ok?'好了':(r.message||'失敗'));rBg(true,T)}}

function spark(H,col){H=(H||[]).filter(x=>x!=null);if(H.length<2)return '';const w=300,h=34,n=H.length;return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline fill="none" stroke="${col}" stroke-width="1.5" points="${H.map((v,i)=>(i*w/(n-1)).toFixed(1)+','+(h-v/100*h).toFixed(1)).join(' ')}"/></svg>`}
async function rPerf(again,T){T=T||$('#v');const j=await api('/api/perf');if(!j.ok||!T.isConnected)return;const g=j.gpu||{},H=j.hist||{};
  const row=(n,v,col,h)=>`<div class="it"><div class="row"><b>${n}</b><span class="grow"></span><b>${v==null?'—':Math.round(v)+'%'}</b></div><div class="pg"><i style="width:${v||0}%;background:${col}"></i></div>${spark(h,col)}</div>`;
  T.innerHTML=`<div class="panel"><h3>📊 效能　<span class="mu">${esc(j.time)}</span></h3>${row('CPU',j.cpu,'#4dc9ff',H.cpu)}${row('RAM（'+fmtB(j.ram_used)+'／'+fmtB(j.ram_total)+'）',j.ram,'#b48cff',H.ram)}
  ${g.name?row('GPU '+esc(g.name)+' '+Math.round(g.temp||0)+'°C',g.util,'#45d483',H.gpu)+row('壓縮',g.enc,'#f0ad4e',H.enc)+row('解碼',g.dec,'#ff6577',H.dec)+row('VRAM',g.mem_t?100*g.mem/g.mem_t:null,'#9aa5b3',H.vram):'<div class="mu">沒有偵測到 NVIDIA 顯示卡</div>'}</div>`}

// ---- ⚙ 設定（照 TikLive：左邊分類、右邊內容；最上面可以搜尋）
const SCAT=[['look','🎨','外觀','深色／淺色、版面','phone'],['about','📱','手機網頁','版本、登出','phone'],
  ['bg','⏯','背景工作','自動讓路、慢慢加速','pc'],['scan','🔁','掃描與檢查','同時幾個、FFmpeg 解碼','pc'],['rep','🛠','修復與隔離','自動修復、自動隔離','pc'],
  ['vc','🎞','影片分類','自動下一部、SortCut','pc'],['misc','⚙','其他','縮到右下角、閃退重開、備份','pc'],['lab','🧪','實驗功能','開了才有的試用功能','pc'],
  ['upd','🆕','線上更新','上傳更新包、退回前一版','pc'],['log','📜','LOG','有問題時看這裡','pc']];
let SETD=null,SCUR=LS.get('scat','look');
async function rSet(again){if(again)return;
  $('#v').innerHTML=`<div class="s2"><aside class="scat" id="scat"></aside><div class="sbody" id="sbody"><div class="mu">讀取中…</div></div></div>`;
  const btn=c=>`<button data-c="${c[0]}"${SCUR===c[0]?' class="on"':''}>${c[1]} ${c[2]}<small>${c[3]}</small></button>`;
  $('#scat').innerHTML=`<input class="ssearch" id="ssq" placeholder="🔍 搜尋設定"><div class="sch">這支手機</div>`+SCAT.filter(c=>c[4]==='phone').map(btn).join('')+`<div class="sch">電腦程式</div>`+SCAT.filter(c=>c[4]==='pc').map(btn).join('');
  $('#scat').onclick=e=>{const b=e.target.closest('button[data-c]');if(b){$('#ssq').value='';setCat(b.dataset.c)}};
  let qt;$('#ssq').oninput=e=>{clearTimeout(qt);qt=setTimeout(()=>setSearch(e.target.value.trim()),250)};
  SETD=await api('/api/settings');if(!SETD.ok)return;SETD.lab=(SETD.labs||[]).map(([k,n,d])=>({k:'lab:'+k,name:n,sub:d,type:'bool',v:!!(SETD.lab||{})[k]}));setCat(SCUR)}
function setCat(k){SCUR=k;LS.set('scat',k);$$('#scat button').forEach(b=>b.classList.toggle('on',b.dataset.c===k));const sb=$('#sbody');if(!sb||!SETD)return;const c=SCAT.find(x=>x[0]===k)||SCAT[0];
  sb.innerHTML=`<h2 class="stt">${c[1]} ${c[2]}</h2><div id="scnt"></div>`;const B=$('#scnt');
  if(k==='look')B.innerHTML=secLook();else if(k==='about')B.innerHTML=secAbout();else if(k==='lab')B.innerHTML=`<div class="ssec">${SETD.lab.map(si).join('')||'<div class="mu" style="padding:12px 0">目前沒有實驗功能</div>'}</div><div class="mu">實驗功能：試用中，好用再正式加入。</div>`;
  else if(k==='upd')return rUpd(false,B);else if(k==='log')return rLog(false,B);
  else B.innerHTML=`<div class="ssec">${SETD.settings.filter(s=>s.cat===k).map(si).join('')}</div><div class="mu">改了馬上存到電腦（電腦的設定頁也會跟著變）。</div>`;
  bindSet(sb)}
function setSearch(q){const sb=$('#sbody');if(!sb||!SETD)return;if(!q){setCat(SCUR);return}const ql=q.toLowerCase();const R=SETD.settings.concat(SETD.lab).filter(s=>s.name.toLowerCase().includes(ql));
  $$('#scat button').forEach(b=>b.classList.remove('on'));
  sb.innerHTML=`<h2 class="stt">🔍「${esc(q)}」找到 ${R.length} 個設定</h2><div class="ssec">${R.map(si).join('')||'<div class="mu" style="padding:12px 0">找不到，換個字試試（例如：同時、修復、隔離、SortCut）</div>'}</div>`;bindSet(sb)}
function si(s){if(s.type==='bool')return `<div class="si tgr"><b>${esc(s.name)}${s.sub?`<small>${esc(s.sub)}</small>`:''}</b><label class="tg"><input type="checkbox" data-k="${s.k}" ${s.v?'checked':''}><i></i></label></div>`;
  if(s.type==='choice')return `<div class="si"><b>${esc(s.name)}</b><div class="seg" data-k="${s.k}" data-num="${typeof s.opt[0][0]==='number'?1:0}">${s.opt.map(o=>`<button data-v="${esc(o[0])}"${String(o[0])===String(s.v)?' class="on"':''}>${esc(o[1])}</button>`).join('')}</div></div>`;
  if(s.type==='num')return `<div class="si"><b>${esc(s.name)}</b><div class="pnum"><button data-step="-1">－</button><input type="number" data-k="${s.k}" value="${esc(s.v)}" min="${s.opt[0]}" max="${s.opt[1]}"><button data-step="1">＋</button><span>${s.opt[0]}～${s.opt[1]}</span></div></div>`;
  return `<div class="si"><b>${esc(s.name)}</b><div class="row" style="flex-wrap:nowrap"><input class="grow" data-kt="${s.k}" value="${esc(s.v||'')}" placeholder="（空的）"><button class="pill" data-ks="${s.k}">儲存</button></div></div>`}
function secLook(){const m=LS.get('mode','dark'),fz=LS.get('fz',1),ac=LS.get('acc','');
  return `<div class="ssec"><div class="si"><b>主題</b><div class="seg" data-ui="mode"><button data-v="dark"${m==='dark'?' class="on"':''}>🌙 深色</button><button data-v="light"${m==='light'?' class="on"':''}>☀ 淺色</button><button data-v="auto"${m==='auto'?' class="on"':''}>📱 跟著手機</button></div></div>
   <div class="si"><b>字的大小</b><div class="seg" data-ui="fz">${[[0.9,'小'],[1,'標準'],[1.12,'大'],[1.25,'特大']].map(([v,n])=>`<button data-v="${v}"${+fz===v?' class="on"':''} style="font-size:${13*v}px">${n}</button>`).join('')}</div><small>整個畫面一起放大縮小（看不清楚就選大）。</small></div>
   <div class="si"><b>強調色</b><div class="seg" data-ui="acc">${Object.entries(ACCS).map(([c,n])=>`<button data-v="${c}"${ac===c?' class="on"':''}><i style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${c||'__ACCENT__'};margin-right:4px"></i>${n}</button>`).join('')}</div></div>
   <div class="si"><b>版面</b><div class="seg" data-ui="view"><button data-v="m"${document.body.classList.contains('pc')?'':' class="on"'}>📱 手機版</button><button data-v="pc"${document.body.classList.contains('pc')?' class="on"':''}>🖥 網頁版（左邊選單）</button></div></div>
   <div class="si tgr"><b>🔔 背景工作做完通知我<small>例如找相似影片、影片瘦身、整理搬檔做完時；手機網頁要開著（切到背景也可以）。只通知做超過 20 秒的。</small></b><label class="tg"><input type="checkbox" data-ntf ${LS.get('notify',false)?'checked':''}><i></i></label></div>
   <div class="si"><b>📊 總覽要顯示哪些<small>不常看的可以關掉，總覽就比較短</small></b><div class="row" style="flex-wrap:wrap;gap:6px">${DSEC.map(([id,n])=>`<label class="pill" style="cursor:pointer"><input type="checkbox" data-dsec="${id}" ${LS.get('dhide',[]).includes(id)?'':'checked'}> ${n}</label>`).join('')}</div></div>
   <div class="si"><b>▶ 輪播每張停幾秒</b><div class="seg" data-ui="ssec">${[2,3,4,6,8,12].map(v=>`<button data-v="${v}"${+LS.get('ssec',4)===v?' class="on"':''}>${v} 秒</button>`).join('')}</div><small>影片會播完才換</small></div>
   <div class="si"><b>浮動視窗高度</b><div class="row"><button class="pill" data-uih>恢復 50%</button></div><small>浮動視窗（📊 效能、🖥 背景）下面的橫條可以上下拖。</small></div>
   <div class="si"><b>🎞 影片分類的版面</b><div class="row"><button class="pill" data-uivc>上下左右的大小恢復預設</button></div><small>分類頁的拉把也可以點兩下各自恢復。</small></div></div><div class="mu">只存在這支手機（電腦和別支手機不受影響）。</div>`}
// 🔔 背景工作做完通知（V0.1.55）：開了才問；手機網頁開著（在背景也行）才收得到
let NT_T=0;
// ---- ❓ 使用說明（V0.1.64）
function rHelp(again){if(again)return;
  const STEPS=[['🚀','最簡單：打開「整理精靈」','下面這些步驟它都幫你排好了：每一步還剩多少、做完打 ✔、一鍵去做。','tool:wiz'],['📁','設定要整理的資料夾','總覽最下面「① 要整理的資料夾」加進去，按「▶ 開始掃描」。背景會自動讀拍攝資訊、比對重複、檢查損毀。','home'],
    ['📈','看資料分析＋🩺 容量健康','總覽往下看：每一類佔多少；「容量健康」標出重複、損毀各佔幾 %。','home'],
    ['🩺','損毀的先隔離','容量健康的「📦 全部先隔離」：打不開、部分損毀的先搬到隔離區（不是刪除），之後想救再復原。','home'],
    ['🧭','重複：先用資料夾看','「重複資料夾最佳解」：整包被複製的資料夾一次處理（⚡ 整包複本全部照建議）；兩邊各有獨有的就 🔀 合併；最上層像「硬碟直接複製過來」可以整個處理。','tool:dpl'],
    ['🔁','剩下零散的重複','「重複檔」→「⚡ 全部照建議處理」。','tool:dup'],
    ['📦','你整理過的資料夾整包處理','「資料夾包」：例如「2020-日本旅遊」，👀 整包看一眼 → ✅ 整包放到「已篩選」（保留資料夾）或 ▶ 一部一部審。','tool:pk'],
    ['🧩','其他影片一組一組審','分類頁左上 🧩 選「同類型」或「同一段時間」：上面顯示第幾組，👀 一覽（G）整組縮圖一次看，☑ 挑出幾部分到別類，剩下的整組分到同一類，自動開下一組。','vc'],
    ['🎞','最後一部一部看','篩選選「還沒分類・不在資料夾包裡」，剩下零散的一部一部看 16 格；看過留著就按「已篩選」。最後按 🚚 一次搬（分類資料夾裡會照原本的資料夾名放）。只想標記不想搬：⚙ 管理把「已篩選」的位置設成「不搬」。','vc'],
    ['🖼','相似照片、📸 連拍、🎬 相似影片','幾乎一樣的、連拍的、轉檔過的副本，留 ⭐ 那份。','tool:sim'],
    ['💾','備份檢查','最後確認重要的照片影片在別顆硬碟也有一份。','tool:bak']];
  $('#v').innerHTML=`<div class="panel"><h3 style="margin-top:0">🧭 建議的整理順序</h3>${STEPS.map(([ic,t,d,g],i)=>`<div class="it row" style="flex-wrap:nowrap;gap:10px;align-items:flex-start"><b style="font-size:18px;min-width:22px;color:var(--accent)">${i+1}</b><span class="grow"><b>${ic} ${t}</b><br><span class="mu" style="font-size:12.5px">${d}</span></span><button class="pill" data-go="${g}" style="flex:none">去 ›</button></div>`).join('')}</div>
   <div class="panel"><h3 style="margin-top:0">⚡ 分類頁的快速技巧</h3><div class="mu" style="font-size:13px;line-height:1.75">
    ・<b>鍵盤</b>：1～9、0 分類（Shift＋數字＝第 11～20 類）、R 跟上一部同一類、N／P 下一部／上一部還沒分的、] 下一組、G 整組一覽、H 剛剛分過的、V 縮圖牆、/ 搜尋、? 全部快捷鍵<br>
    ・<b>下面的小格子</b>：滑鼠滑過去＝翻 16 格；停在某格按數字＝直接分那格；長按／右鍵開始勾、按住拖過去整段勾、點組名整組勾，勾好按分類一次套用；Ctrl＋滾輪放大縮小<br>
    ・<b>🔲 縮圖牆</b>：整個畫面都是小格子，照片、短片特別快<br>
    ・<b>手機</b>：16 格左右滑＝換一部、往上滑＝照 💡 建議分、長按小格子開始勾<br>
    ・<b>📚 整批分類</b>：💡 照建議分（一條一條勾）、📷 照相機／🔤 檔名開頭一次分、🐾 找貓狗、👤 有人／沒有人、🧠 電腦學到的習慣、📏 我的規則（例如 LINE → Delete、&lt;3秒 → Delete、相機:DJI → DJI）<br>
    ・<b>🐾 電腦看內容</b>（📚 整批分類 → 🐾 開始找）：有狗／有貓、👤 有人、👥 3 個人以上、🌑 全黑（口袋誤錄）、⬜ 沒東西、🧱 沒動、📺 拍到螢幕、🍜 食物、🏖 海邊…；點一下只看那些，Ctrl＋A 整組分。規則可以寫「內容:有狗 → Family」；分多了電腦也會自己學<br>
    ・<b>Ctrl＋Z／Backspace</b>：復原剛剛的分類（整批分的也能復原）<br>
    ・<b>Shift＋F</b>：同一個資料夾連續分 3 部同一類後，剩下的一次分完（手機會直接問）<br>
    ・<b>上方小按鈕</b>：🐾 N＝只看有貓狗的、🌑 N＝只看全黑／沒東西／沒動（多半是誤錄）；Shift＋P＝只看有貓狗的<br>
    ・<b>💡 建議</b>：同資料夾、同相機、檔名開頭、地點、電腦看到的內容、你的規則；好幾個線索加起來夠把握也會建議（🧮 綜合）。「🧠 電腦學到的習慣」最上面有 📈 準確率，九成以上的放心「照建議分」<br>
    ・<b>🧐 可能分錯的</b>：搬之前，篩選選「🧐 可能分錯的」逐一看，資訊列可以按「改成…」或「沒錯」<br>
    ・<b>🔀 併分類</b>：「⚙ 管理」→「🔀 併到…」把兩類（例如家庭／Family）併成一類<br>
    ・<b>搬之前檢查</b>：點下面「待搬：Delete 912」的分類名、或右鍵分類按鈕＝只看那類<br>
    ・<b>重複</b>：分好的影片，一模一樣的副本自動標 Delete；相似版本（轉檔過的）分完按 Shift＋D</div></div>
   <div class="panel"><h3 style="margin-top:0">🔒 安全</h3><div class="mu" style="font-size:13px;line-height:1.6">・程式<b>從來不會刪你的檔案</b>：要處理的只會搬到同一顆硬碟的「_FileCompare_待確認」（隔離區），在「📦 隔離區」可以一個一個或整批復原。<br>・整理、改檔名、分類搬檔都有紀錄（「🧾 操作紀錄」查得到）。<br>・確定都不要了，再自己到電腦上刪隔離區資料夾。</div></div>`
   +TOOL_GROUPS.map(([g,ks])=>`<div class="panel"><h3 style="margin-top:0">${g}</h3>${ks.map(TOOL).filter(Boolean).map(x=>`<div class="it row" style="flex-wrap:nowrap;gap:8px"><span style="font-size:20px">${x[1]}</span><span class="grow"><b>${x[2]}</b><br><span class="mu" style="font-size:12.5px">${x[3]}</span></span><button class="pill" data-go="tool:${x[0]}" style="flex:none">打開</button></div>`).join('')}</div>`).join('');
  $('#v').onclick=e=>{const b=e.target.closest('[data-go]');if(b)go(b.dataset.go)}}
// ---- 🩺 自我檢查（V0.3.63）
async function rDiag(again){if(again)return;$('#v').innerHTML='<div class="panel">檢查中…</div>';const draw=j=>{$('#v').innerHTML=`<div class="panel"><div class="row"><h3 class="grow" style="margin:0">🩺 自我檢查</h3><button class="pill acc" data-dg="deep">🔬 連 Windows ML、人臉偵測一起測（約 10 秒）</button></div>
   <div class="mu" style="margin:6px 0">有 ❌ 的話，把這頁截圖給開發者。</div>${(j.rows||[]).map(r=>`<div class="it row" style="flex-wrap:nowrap;gap:8px;align-items:flex-start"><span style="font-size:18px">${r.ok===true?'✅':r.ok===false?'❌':'➖'}</span><span class="grow" style="min-width:0"><b>${esc(r.k)}</b><br><span class="mu" style="font-size:12px;white-space:pre-wrap;word-break:break-all">${esc(r.msg)}</span></span></div>`).join('')}</div>`;
    $('#v').onclick=async e=>{if(e.target.closest('[data-dg]')){e.target.closest('[data-dg]').textContent='測試中…';draw(await api('/api/diag?deep=1'))}}};
  draw(await api('/api/diag'))}
// ---- 🧾 操作紀錄（V0.1.56）
let OPK='',OPQ='',OPO=0;
async function rOps(again){if(again)return;const j=await api(U('/api/ops',{k:OPK,q:OPQ,o:OPO}));if(!j.ok)return;
  const rows=j.rows.map(r=>`<div class="it" style="font-size:13px"><div class="row" style="flex-wrap:nowrap;gap:6px"><span class="mu" style="white-space:nowrap">${day(r.t)}</span><b style="${r.ok?'':'color:var(--red)'}">${esc(r.kind)}</b></div><div style="word-break:break-all;color:var(--sub);font-size:12px">${esc(r.detail)}</div></div>`).join('');
  if(OPO&&$('#opl')){$('#opl').insertAdjacentHTML('beforeend',rows);const m=$('[data-om]');if(m&&OPO+200>=j.n)m.remove();return}
  $('#v').innerHTML=`<div class="panel"><div class="mu">程式做過的每一件事（搬到隔離區、整理、復原、分析、瘦身…）都記在這裡，什麼時候、做了什麼。</div>
    <div class="row" style="margin-top:8px;gap:6px"><select id="opk"><option value="">全部（${j.n.toLocaleString()}）</option>${j.kinds.map(([k,n])=>`<option value="${esc(k)}" ${OPK===k?'selected':''}>${esc(k)}（${n.toLocaleString()}）</option>`).join('')}</select><input id="opq" type="search" placeholder="找檔名、資料夾…" value="${esc(OPQ)}" style="flex:1;min-width:0"></div></div>
   <div class="panel" id="opl">${rows||'<div class="mu">沒有紀錄</div>'}</div>${OPO+200<j.n?'<div class="row" style="justify-content:center;margin:10px"><button class="pill" data-om>再看 200 筆</button></div>':''}`;
  $('#opk').onchange=()=>{OPK=$('#opk').value;OPO=0;rOps()};let qt;$('#opq').oninput=e=>{clearTimeout(qt);qt=setTimeout(()=>{OPQ=e.target.value.trim();OPO=0;rOps()},400)};
  $('#v').onclick=e=>{if(e.target.closest('[data-om]')){OPO+=200;rOps()}}}
async function ntPoll(){if(!LS.get('notify',false)||!TOK)return;try{const j=await api(U('/api/done_since',{t:NT_T||0}));if(!j.ok)return;if(!NT_T){NT_T=j.now;return}NT_T=j.now;
  for(const r of j.rows){const t=(r.state==='done'?'✔ ':'✖ ')+(r.title||'工作')+(r.state==='done'?' 做完了':' 失敗'),b=r.msg||'';
    try{if('Notification' in window&&Notification.permission==='granted'){new Notification(t,{body:b,icon:'icon-192.png',tag:'fc'+r.t1});continue}}catch(e){}
    toast(t+(b?'：'+b:''),6000)}}catch(e){}}
setInterval(ntPoll,20000);setTimeout(ntPoll,3000);
function secAbout(){return `<div class="ssec"><div class="si"><b>版本</b>V${esc(VER0)}</div>
   <div class="si"><b>🔠 字的大小<small>這台裝置的畫面整個放大縮小（V0.3.61）</small></b><div class="row" style="gap:4px">${[[0.9,'小'],[1,'一般'],[1.12,'大'],[1.25,'特大']].map(([v,n])=>`<button class="pill ${Math.abs((+LS.get('fz',1)||1)-v)<0.01?'acc':''}" data-fz="${v}">${n}</button>`).join('')}</div></div><div class="si"><b>連線</b>${esc(location.host)}</div>
   <div class="si"><b>💾 設定備份<small>重灌、換電腦時用：資料夾清單、所有設定、影片分類（名稱、顏色、搬去哪）、每部影片分到哪類、⭐ 最愛。匯入是「合併」，不會動任何檔案。</small></b>
    <div class="row"><a class="pill" href="/api/cfg_export" download style="color:var(--text);text-decoration:none">⬇ 匯出設定</a><label class="pill" style="cursor:pointer">⬆ 匯入設定<input type="file" accept=".json,application/json" data-cfgin hidden></label></div></div>
   <div class="si"><button class="pill er" data-out>🚪 登出這支手機</button><small>下次要重新輸入 PIN</small></div></div>`}
document.addEventListener('click',e=>{const b=e.target.closest('[data-fz]');if(!b)return;LS.set('fz',+b.dataset.fz);applyFz();b.parentElement.querySelectorAll('[data-fz]').forEach(x=>x.classList.toggle('acc',x===b))});
function applyFz(){const z=+LS.get('fz',1)||1;document.documentElement.style.zoom=z===1?'':String(z)}applyFz();
function bindSet(sb){
  if(!sb._cfgin){sb._cfgin=1;sb.addEventListener('change',async e=>{const f=e.target.closest('[data-cfgin]');if(!f||!f.files[0])return;if(!confirm('匯入這個設定檔？（合併到現在的設定，不會動任何檔案）'))return;
    const r=await (await fetch('/api/cfg_import',{method:'POST',headers:{'x-app-token':TOK},body:await f.files[0].arrayBuffer()})).json().catch(()=>({message:'失敗'}));toast(r.message||'失敗',6000);f.value=''})}
  sb.onclick=async e=>{const b=e.target.closest('.seg[data-k] button');if(b){const g=b.parentElement;let v=b.dataset.v;if(g.dataset.num==='1')v=+v;$$('button',g).forEach(x=>x.classList.toggle('on',x===b));
      const r=await api('/api/settings',{k:g.dataset.k,v});toast(r.ok?'✔ 已儲存':(r.message||'沒存到'));const s=SETD.settings.find(x=>x.k===g.dataset.k);if(r.ok&&s)s.v=v;return}
    const ds=e.target.closest('[data-dsec]');if(ds){let H=LS.get('dhide',[]).filter(x=>x!==ds.dataset.dsec);if(!ds.checked)H.push(ds.dataset.dsec);LS.set('dhide',H);toast('✔ 已儲存');return}
    const nf=e.target.closest('[data-ntf]');if(nf){const on=nf.checked;LS.set('notify',on);NT_T=0;if(on&&'Notification' in window&&Notification.permission==='default'){try{await Notification.requestPermission()}catch(_){}}
      toast(on?('Notification' in window&&Notification.permission==='granted'?'🔔 好，做完會通知你':'🔔 好（手機不允許系統通知時，會在畫面上提示）'):'不通知了');return}
    const u=e.target.closest('.seg[data-ui] button');if(u){const k=u.parentElement.dataset.ui,v=u.dataset.v;$$('button',u.parentElement).forEach(x=>x.classList.toggle('on',x===u));if(k==='mode')setMode(v);if(k==='view')setView(v);if(k==='fz')setFz(+v);if(k==='ssec')LS.set('ssec',+v);if(k==='acc')setAcc(v);toast('✔ 已儲存');return}
    if(e.target.closest('[data-uih]')){LS.set('syspop_h',.5);toast('✔ 已恢復');return}
    if(e.target.closest('[data-uivc]')){['sw','sh','bw','th','fh'].forEach(k=>delete VC[k]);LS.set('vc',VC);toast('✔ 已恢復');return}
    if(e.target.closest('[data-out]')){if(!confirm('登出這支手機？'))return;await api('/api/logout',{});TOK='';LS.set('tok','');return showLogin()}
    const ks=e.target.closest('[data-ks]');if(ks){const k=ks.dataset.ks,v=sb.querySelector(`[data-kt="${k}"]`).value.trim();const r=await api('/api/settings',{k,v});toast(r.ok?'✔ 已儲存':'沒存到');const s=SETD.settings.find(x=>x.k===k);if(r.ok&&s)s.v=v;return}
    const st=e.target.closest('[data-step]');if(st){const i=st.parentElement.querySelector('input');i.value=Math.max(+i.min,Math.min(+i.max,(+i.value||0)+ +st.dataset.step));i.dispatchEvent(new Event('change',{bubbles:true}))}};
  sb.onchange=async e=>{const t=e.target;if(!t.dataset.k)return;let v=t.type==='checkbox'?t.checked:t.value;if(t.type==='number')v=+v;
    let r;if(t.dataset.k.startsWith('lab:'))r=await api('/api/lab',{k:t.dataset.k.slice(4),on:v});else r=await api('/api/settings',{k:t.dataset.k,v});
    toast(r.ok?'✔ 已儲存':(r.message||'沒存到'));const s=SETD.settings.concat(SETD.lab).find(x=>x.k===t.dataset.k);if(r.ok&&s)s.v=v}}
// ---- 🆕 線上更新（照 TikLive：選擇或拖曳更新包 →「開始更新」；下載資料夾有新的會自動出現；退回前一版）
let UPTOK='';
async function rUpd(again,T){if(again)return;T=T||$('#v');const P='__PREFIX__';
  T.innerHTML=`<div class="ssec" style="padding:12px 14px"><div class="mu">更新時背景工作不會中斷。選擇或拖曳更新包（${P}_V版本.zip）→ 先看改了什麼 → 按「開始更新」；完成後電腦上的程式會自動換成新版，這個網頁也會重新載入。</div>
    <div style="margin-top:8px"><b>目前版本：V${esc(VER0)}</b></div>
    <div class="drop" id="upDrop">把 ${P}_V版本.zip 拖到這裡，或 <button class="pill" id="upPick">選擇更新包…</button><input type="file" id="upF" accept=".zip" style="display:none"></div>
    <div id="upDl" style="margin-top:8px"></div><div id="upInfo" style="margin-top:8px"></div>
    <div class="row" style="margin-top:8px"><button class="pill" id="upLog">📜 更新紀錄</button><span class="grow"></span><button class="pill acc" id="upGo" disabled style="padding:8px 18px">開始更新</button></div><pre id="upLogT" style="display:none;white-space:pre-wrap;word-break:break-all;font-size:11.5px;max-height:260px;overflow:auto;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:8px;margin-top:8px"></pre></div>
   <div class="ssec" style="padding:12px 14px"><b>退回前一版</b><div class="mu">更新後如果出狀況，可以退回之前的版本（每次更新前都會自動備份）。退回時背景工作一樣不會中斷。</div><div id="upRb" style="margin-top:6px"></div></div>
   <div class="ssec" style="padding:12px 14px"><b>最近幾版改了什麼</b><div id="cl" class="mu" style="margin-top:6px"></div></div>`;
  const dz=$('#upDrop');$('#upPick').onclick=()=>$('#upF').click();$('#upF').onchange=e=>updUp(e.target.files[0]);
  dz.ondragover=e=>{e.preventDefault();dz.classList.add('over')};dz.ondragleave=()=>dz.classList.remove('over');dz.ondrop=e=>{e.preventDefault();dz.classList.remove('over');updUp(e.dataTransfer.files[0])};
  $('#upGo').onclick=updApply;$('#upLog').onclick=updLog;updDl();updRb();
  if(LS.get('upd_go',0)){LS.set('upd_go',0);setTimeout(updDlUse,200)}
  const cl=await api('/api/changelog');const c=$('#cl');if(c)c.innerHTML=(cl.log||[]).slice(0,6).map(x=>`<div style="margin-bottom:6px"><b>V${esc(x.version)}</b> ${esc(x.date||'')}<br>${(x.items||[]).map(i=>'• '+esc(i)).join('<br>')}</div>`).join('')}
async function updDl(){const d=await api('/api/update_dl');const el=$('#upDl');if(!el)return;const f=d&&d.found;
  el.innerHTML=f?`<div class="row" style="padding:8px 10px;border:1px solid var(--red);border-radius:10px;background:rgba(255,77,109,.08)"><div class="grow">🆕 <b>下載資料夾有新的更新包</b>　${esc(f.name)}（V${esc(d.cur)} → <b>V${esc(f.ver)}</b>）</div><button class="pill acc" id="upDlGo">⚡ 用這個更新包</button></div>`
    :`<div class="mu">下載資料夾（${esc(d.dir||'')}）裡沒有比現在新的更新包；下載好會自動出現在這裡和右下角。</div>`;const b=$('#upDlGo');if(b)b.onclick=updDlUse}
async function updDlUse(){$('#upInfo').textContent='讀取下載資料夾的更新包、檢查中…';updShow(await api('/api/update_prep',{}))}
async function updUp(f){if(!f)return;$('#upInfo').textContent='上傳中…';let j;try{j=await api(U('/api/update_up',{name:f.name}),f,true)}catch(e){j={message:'連不到電腦或上傳中斷，請再試一次'}}updShow(j)}
function updShow(j){const el=$('#upInfo');if(!el)return;if(!j.ok){el.innerHTML=`<span style="color:var(--red)">✖ ${esc(j.message||'上傳失敗')}</span>`;$('#upGo').disabled=true;return}UPTOK=j.tok;
  el.innerHTML=`<b>V${esc(j.from)} → V${esc(j.to)}</b>（${j.cmp>0?'升級':j.cmp===0?'相同版本':'⚠ 降版（退回舊版）'}）<br>`+(j.notes||[]).map(n=>'• '+esc(n)).join('<br>')+
   `<br>${j.hot?'<span style="color:var(--green)">可以熱更新：程式不用關、背景工作不中斷。</span>':'<span style="color:var(--orange)">這個版本不支援熱更新：會放進 UPDATE，下次打開程式時套用。</span>'}`;$('#upGo').disabled=false;$('#upGo').scrollIntoView({block:'nearest'})}
async function updApply(){if(!UPTOK)return;if(!confirm('開始更新？\n\n更新期間背景工作不會中斷，完成後電腦上的程式會自動換成新版。'))return;
  const j=await api('/api/update_apply',{tok:UPTOK});if(!j.ok){alert('更新失敗：'+(j.message||'沒有成功'));return}$('#upGo').disabled=true;
  $('#upInfo').innerHTML+=`<br><b style="color:var(--green)">✓ 電腦正在換成新版…</b>`;updWait()}
async function updWait(){for(let i=0;i<90;i++){await new Promise(r=>setTimeout(r,2000));
  try{const s=await api('/api/update_status');if(s.state==='failed'){alert('更新失敗：'+(s.message||''));updLog(1);return}if(s.state==='done'||(s.to&&s.current===s.to)){toast('✔ 更新完成，重新載入網頁…');setTimeout(()=>location.reload(),1500);return}}catch(e){}}
  alert('電腦一直沒有回應更新結果。請看一下電腦畫面；或把電腦上的程式關掉再打開（更新包已經在 UPDATE 資料夾，打開時會套用）。');updLog(1)}
async function updLog(force){const t=$('#upLogT');if(!t)return;if(t.style.display!=='none'&&force!==1){t.style.display='none';return}
  let j={};try{j=await api(U('/api/log',{f:'update_log.txt'}))}catch(e){}const L=(j.text||'').trim().split('\n');
  t.textContent=L.slice(-60).join('\n')||'（還沒有更新紀錄）';t.style.display='block';t.scrollTop=t.scrollHeight;t.scrollIntoView({block:'nearest'})}
async function updRb(){const j=await api('/api/update_rollback');const el=$('#upRb');if(!el)return;
  el.innerHTML=(j.items||[]).map(x=>`<div class="row it" style="flex-wrap:nowrap"><div class="grow"><b>V${esc(x.version)}</b>　<span class="mu">備份於 ${esc(x.time)}${x.older?'':'（比目前新）'}</span><br><span class="mu">${esc((x.notes||[]).slice(0,2).map(n=>n.length>46?n.slice(0,46)+'…':n).join('；'))}</span></div><button class="pill" data-rb="${esc(x.id)}">${x.older?'退回':'換成'} V${esc(x.version)}</button></div>`).join('')||'<div class="mu">目前沒有可以退回的備份。</div>';
  el.onclick=async e=>{const b=e.target.closest('[data-rb]');if(!b)return;$('#upInfo').textContent='讀取備份、檢查中…';updShow(await api('/api/update_rollback',{id:b.dataset.rb}));$('#upInfo').scrollIntoView({block:'center'})}}
// 右下角：下載資料夾有新的更新包（跟 TikLive 一樣每 15 秒看一次）
function updFabInit(){const chk=async()=>{if(document.hidden||!TOK)return;let d=null;try{d=await api('/api/update_dl')}catch(e){}const f=d&&d.found;let b=$('#updFab');
    if(!f||LS.get('upd_skip','')===f.name){if(b)b.remove();return}
    if(!b){b=document.createElement('div');b.id='updFab';document.body.appendChild(b)}
    b.innerHTML=`<button class="pill acc" data-u="go">⬆ 有新版 V${esc(f.ver)}<small>下載資料夾 · 按一下更新</small></button><button class="pill" data-u="x" title="這個先不要提醒">✕</button>`;
    b.onclick=e=>{const x=e.target.closest('[data-u]');if(!x)return;if(x.dataset.u==='x'){LS.set('upd_skip',f.name);b.remove();return}LS.set('upd_go',1);b.remove();go('tool:upd')}};
  chk();setInterval(chk,15000)}
// ---- 📜 LOG
async function rLog(again,T){if(again)return;T=T||$('#v');
  T.innerHTML=`<div class="ssec" style="padding:12px 14px"><div class="row"><select id="lf"><option value="app_log.txt">app_log（什麼都記）</option><option value="error_log.txt">error_log（錯誤）</option><option value="ui_freeze_log.txt">ui_freeze_log（畫面卡住）</option><option value="update_log.txt">update_log（更新）</option></select><button class="pill" id="lg">讀取</button></div>
   <pre id="lt" style="margin-top:8px;max-height:70vh">（按「讀取」）</pre><div class="mu">出問題時：電腦上「📜 LOG」→「📦 匯出最近 7 天」，把 zip 傳給 AI。</div></div>`;
  const rd=async()=>{const r=await api(U('/api/log',{f:$('#lf').value}));const p=$('#lt');p.textContent=r.text||'（空的）';p.scrollTop=p.scrollHeight};$('#lg').onclick=rd;$('#lf').onchange=rd;rd()}

async function boot(){let h={};try{h=await (await fetch('/api/hello',{headers:{'x-app-token':TOK}})).json()}catch(e){$('#v').innerHTML='<div class="panel">連不到電腦（Tailscale 有開嗎？電腦開著嗎？）</div>';return}
  $('#ver').textContent='V'+h.ver;VER0=h.ver;if(!h.authed)return showLogin();const g0=new URLSearchParams(location.search).get('go');if(g0&&(TABS.some(t=>t[0]===g0)||(g0.startsWith('tool:')&&TOOL(g0.slice(5))))){CUR=g0;LS.set('tab',CUR)}
  histInit();tabs();show();sysFabInit();updFabInit();setTimeout(whatsNew,1500)}
// 🆕 更新後第一次打開：這幾版多了什麼（V0.1.60）
const vcmp=(a,b)=>{const x=String(a).split('.').map(Number),y=String(b).split('.').map(Number);for(let i=0;i<Math.max(x.length,y.length);i++){const d=(x[i]||0)-(y[i]||0);if(d)return d}return 0};
async function whatsNew(){const seen=LS.get('seenVer','')||'0.1.22';if(vcmp(VER0,seen)<=0)return;
  let j;try{j=await api('/api/changelog?n=160')}catch(e){return}const L=(j.log||[]).filter(x=>vcmp(x.version,seen)>0&&vcmp(x.version,VER0)<=0);LS.set('seenVer',VER0);if(!L.length)return;
  const Z=document.createElement('div');Z.style.cssText='position:fixed;inset:0;z-index:90;background:#000b;display:grid;place-items:center;padding:14px';
  Z.innerHTML=`<div class="panel" style="max-width:560px;width:100%;max-height:82vh;overflow:auto;margin:0"><div class="row"><h3 class="grow" style="margin:0">🆕 更新好了：V${esc(seen)} → V${esc(VER0)}</h3><button class="pill" data-wx>知道了</button></div>
    <div class="mu" style="margin:4px 0 8px">這次一共新了 ${L.length} 版${L.length>6?'，每版一行重點（點「看全部」展開）':'，多了這些'}：</div>
    ${L.length>6?`<div class="row" style="gap:6px;margin-bottom:8px;flex-wrap:wrap"><button class="pill acc" data-wgo="vc">🎞 去分類（按 ? 看快捷鍵）</button><button class="pill" data-wgo="vc:big">🔲 縮圖牆</button><button class="pill" data-wgo="vc:many">🐾 找貓狗／📷 相機一次分</button><button class="pill" data-wgo="tool:wiz">🚀 整理精靈</button></div>
      <div id="wnS">${L.map(x=>`<div style="font-size:12.5px;margin:3px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"><b style="color:var(--accent)">V${esc(x.version)}</b> ${esc((x.items||[''])[0])}</div>`).join('')}<div class="row" style="justify-content:center;margin-top:8px"><button class="pill" data-wall>看全部</button></div></div>`:''}
    <div id="wnF" style="${L.length>6?'display:none':''}">${L.map(x=>`<div style="margin-bottom:10px"><b style="color:var(--accent)">V${esc(x.version)}</b><ul style="margin:4px 0 0 18px;padding:0">${(x.items||[]).map(i=>`<li style="margin:2px 0;font-size:13px">${esc(i)}</li>`).join('')}</ul></div>`).join('')}</div></div>`;
  const real=()=>Z.remove();Z.onclick=e=>{if(e.target.closest('[data-wall]')){Z.querySelector('#wnS').style.display='none';Z.querySelector('#wnF').style.display='';return}
    const g=e.target.closest('[data-wgo]');if(g){ovClose(real);const w=g.dataset.wgo;if(w==='vc:big'){VC.big=true;LS.set('vc',VC)}return setTimeout(()=>{go(w.startsWith('vc')?'vc':w);if(w==='vc:many')setTimeout(()=>{const b=document.querySelector('[data-a="many"]');if(b)b.click()},1800)},300)}
    if(e.target===Z||e.target.closest('[data-wx]'))ovClose(real)};document.body.appendChild(Z);ovOpen(real)}
let VER0='__VER__';
if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js').catch(()=>{});
boot();
</script></body></html>
"""

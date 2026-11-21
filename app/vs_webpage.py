"""SortCut 手機網頁（V0.1.51：介面、操作方式照 TikLive V0.8.18 的風格）— 整個頁面（HTML＋CSS＋JS，一個檔，不用網路上的東西）。
__VER__ 會換成程式版本。"""

PAGE = r"""<!doctype html>
<html lang="zh-Hant" data-mode="dark"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0a0e13"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-capable" content="yes">
<link rel="manifest" href="manifest.webmanifest"><link rel="icon" href="icon-192.png"><link rel="apple-touch-icon" href="apple-touch-icon.png">
<title>SortCut</title>
<style>
.vgT.scn{box-shadow:inset 4px 0 0 #ff8a3c}.vgT.stc{filter:brightness(.35)}.vgT.hot{box-shadow:inset 0 -4px 0 #ff4d6d}.vgT.hot.scn{box-shadow:inset 4px 0 0 #ff8a3c,inset 0 -4px 0 #ff4d6d}.vgT.stc::after{content:'😴';position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:18px}
body.bnav:not(.pc) nav#tabs{position:fixed;left:0;right:0;bottom:0;z-index:60;background:var(--nav);padding:6px 8px calc(6px + env(safe-area-inset-bottom));border-top:1px solid var(--line);margin:0}body.bnav:not(.pc) main#v{padding-bottom:78px}body.bnav.fopen nav#tabs,body.bnav .vbox~nav#tabs{display:none}
body.pv .c .th,body.pv .vgT,body.pv video,body.pv .pc2 img,body.pv .rvT{filter:blur(18px) saturate(.6)}body.pv .c .th:active,body.pv .vgT:active{filter:none}
:root{--bg:#0e1116;--nav:#0a0e13;--panel:#11161c;--card:#151a21;--line:#252c35;--line2:#2a3340;--text:#e8ecf2;--strong:#fff;--sub:#8994a4;--muted:#7f8a99;--hover:#161e28;
--tab:#11161c;--tabon:#202a35;--tabline:#405064;--head:#191f27;--headtext:#aeb7c4;--chart:#0d1218;--grid:#26303b;--vline:#43d9ff;--track:#2a3038;--btn:#171d26;--btnh:#222b37;--sel:#263342;
--green:#45d483;--red:#ff4d6d;--purple:#9b6dff;--orange:#f0ad4e;--pink:#ff5c8a;--blue:#4dc9ff;--accent:#e51e63;--safe:env(safe-area-inset-bottom,0px);
--S:#ffc94d;--A:#45d483;--E:#4dc9ff;--F:#ff4d6d;--fs:14px}
html[data-mode=light]{--S:#c99400;--A:#1f9d55;--E:#1386c4;--F:#d92b4b;--bg:#f3f5f8;--nav:#e8ecf1;--panel:#ffffff;--card:#ffffff;--line:#d5dce4;--line2:#c2cbd6;--text:#1b2430;--strong:#0b121a;--sub:#5d6978;--muted:#6b7685;--hover:#dde4ec;
--tab:#e8ecf1;--tabon:#ffffff;--tabline:#6f9fd3;--head:#eef1f5;--headtext:#3d4856;--chart:#ffffff;--grid:#e6ebf0;--vline:#0a84c6;--track:#dfe5ec;--btn:#ffffff;--btnh:#e7ecf2;--sel:#d3e6fb}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;background:var(--bg);color:var(--text);font:var(--fs)/1.4 system-ui,-apple-system,"Segoe UI","Microsoft JhengHei","PingFang TC",sans-serif}
button{font:inherit;cursor:pointer;color:inherit}
header{position:sticky;top:0;z-index:20;background:var(--nav);border-bottom:1px solid var(--line);padding-top:env(safe-area-inset-top,0px)}
.bar{display:flex;align-items:center;justify-content:space-between;padding:8px 12px 6px}
.logo{font-weight:800;font-size:15px;color:var(--strong);display:flex;align-items:center;gap:7px;letter-spacing:.2px;white-space:nowrap;flex:none}
.logo i{width:9px;height:9px;border-radius:50%;background:var(--accent);box-shadow:0 0 8px var(--accent)}
.logo img{width:24px;height:24px;border-radius:7px;flex:none}
.pcn{font-size:12px;font-weight:800;margin-left:2px;white-space:nowrap}
.inst{background:var(--accent);color:#fff;border:0;border-radius:14px;padding:4px 11px;font-weight:800;font-size:12.5px}
.clk{font-size:11px;color:var(--sub);font-variant-numeric:tabular-nums}.rt{display:flex;align-items:center;justify-content:flex-end;gap:8px;min-width:0;flex:1;margin-left:8px}
.ver{font-size:11px;color:var(--sub);border:1px solid var(--line);border-radius:8px;padding:1px 6px;white-space:nowrap;font-variant-numeric:tabular-nums}
nav#tabs{display:flex;gap:6px;padding:0 10px 8px}
/* V0.2.13 🖥 網頁版（照 TikLive 的「網頁版」：電腦／平板的大螢幕版面；同一個網址，記在這台的瀏覽器） */
:root{--pw:min(50vw,900px)}
body.pc #app{display:grid;grid-template-columns:210px minmax(0,1fr);min-height:100vh}
body.pc header{position:sticky;top:0;height:100vh;border-bottom:0;border-right:1px solid var(--line);display:flex;flex-direction:column;overflow:auto;padding-bottom:150px}
body.pc .bar{flex-direction:column;align-items:stretch;gap:8px;padding:12px}
body.pc .bar .rt{justify-content:flex-start;flex-wrap:wrap;margin-left:0}
body.pc .logo{font-size:17px}
body.pc #tabs{flex-direction:column;gap:4px;padding:6px 10px}
body.pc #tabs button{flex:none!important;width:100%;text-align:left;padding:10px 12px;font-size:14px}
body.pc #sysFab{left:10px;top:auto;bottom:12px;transform:none;flex-direction:column;align-items:stretch;width:190px}
body.pc #sysFab button{height:30px;font-size:12.5px}
body.pc #v{padding:12px 16px 40px;min-width:0}
body.pc .fxw{display:grid;grid-template-columns:300px minmax(0,1fr);gap:14px;align-items:start}
body.pc #ftree{position:sticky;top:12px;max-height:calc(100vh - 24px);overflow:auto;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:8px}
body.pc.fopen #v{padding-right:calc(var(--pw) + 16px)}body.pc.fopen #ftree{display:none}body.pc.fopen .fxw{grid-template-columns:minmax(0,1fr)}
body.pc #fov{left:auto;right:0;width:var(--pw);border-left:1px solid var(--line);box-shadow:-8px 0 24px rgba(0,0,0,.35)}
body.pc #fov .rph{padding-top:10px}
body.pc #cutbar{left:auto;right:0;width:var(--pw)}
.vsw{font-size:11.5px;padding:2px 8px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--text);white-space:nowrap}
nav#tabs button{flex:2;background:var(--tab);border:1px solid var(--line);color:var(--sub);border-radius:9px;padding:8px 0;font-weight:700;white-space:nowrap}
nav#tabs button.on{background:var(--tabon);border-color:var(--tabline);color:var(--strong)}nav#tabs button.tset{flex:1;font-size:13px}nav#tabs button.tbg{flex:1.5;font-size:12.5px}
main{padding:10px 10px calc(30px + var(--safe))}
.search{width:100%;background:var(--card);border:1px solid var(--line);border-radius:9px;color:var(--text);padding:9px 11px;font:inherit;font-size:16px;outline:none}.search:focus{border-color:var(--tabline)}
.tools{display:flex;gap:8px;align-items:center}.tools .search{flex:1;min-width:0}
.seg{display:flex;border:1px solid var(--line);border-radius:9px;overflow:hidden;flex:none}
.seg button{background:var(--card);border:0;border-left:1px solid var(--line);color:var(--sub);height:40px;min-width:34px;padding:0 9px;font-weight:800}
.seg button:first-child{border-left:0}.seg button.on{background:var(--tabon);color:var(--strong)}
.sh{display:flex;align-items:center;gap:8px;font-weight:800;font-size:13px;margin:14px 2px 8px;padding-bottom:5px;border-bottom:1px solid var(--line);color:var(--sub)}
.panel{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;margin-bottom:10px}
.pill{background:var(--btn);border:1px solid var(--line);color:var(--text);border-radius:9px;padding:6px 11px;font-weight:700;font-size:13px;white-space:nowrap}
.pill:active{background:var(--btnh)}.pill.on{background:var(--tabon);border-color:var(--tabline);color:var(--strong)}.pill.acc{background:var(--accent);border-color:var(--accent);color:#fff}
.pill.ok{border-color:var(--green);color:var(--green)}.pill.wa{border-color:var(--orange);color:var(--orange)}.pill.er{border-color:var(--red);color:var(--red)}.pill:disabled{opacity:.45}
.row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.grow{flex:1;min-width:0}
.mu{color:var(--sub);font-size:12px}
.empty{color:var(--sub);text-align:center;padding:34px 0}
.back{background:none;border:0;color:var(--vline);font-size:15px;padding:2px 0 8px}
.tlh{display:flex;align-items:center;gap:10px;margin:0 0 8px}.tlh b{font-size:16px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tlh .back{width:36px;height:36px;padding:0;border-radius:10px;border:1px solid var(--line);background:var(--tab);color:inherit;font-size:20px;flex:none}
.tgh{font-weight:800;font-size:14px;margin:14px 2px 6px;color:var(--sub)}
.wsGrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
.rsStop{border-radius:12px;padding:12px 14px;margin:8px 0;font-size:14px}.rsStop.wait{background:rgba(240,173,78,.15);border:1px solid #f0ad4e;color:#f0c27a}.rsStop.ok{background:rgba(77,214,138,.13);border:1px solid #4dd68a}.rsVol{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid rgba(127,127,127,.15)}.rsVol>span{font-weight:800;color:#4dd68a}.rsVol.bad>span{color:#f0ad4e}.rsVol em{font-style:normal;opacity:.75;font-size:12px}.rsVol i{font-style:normal;font-size:12px;color:#4dd68a;margin-left:auto}.rsVol label{margin-left:auto;font-size:13px}.rsVol select{padding:4px 8px}.rsDrvs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:8px 0}@media(max-width:560px){.rsDrvs{grid-template-columns:1fr}}.rsDk{background:linear-gradient(180deg,rgba(0,0,0,.22),rgba(0,0,0,.08));border:1px solid color-mix(in srgb,var(--c) 45%,transparent);border-top:3px solid var(--c);border-radius:12px;padding:8px 10px}.rsDh{display:flex;align-items:center;gap:6px}.rsDh b{font-size:15px}.rsDh i{font-style:normal;font-size:11px;padding:1px 7px;border-radius:9px;background:color-mix(in srgb,var(--c) 22%,transparent);color:var(--c)}.rsDh span{margin-left:auto;font-size:22px;font-weight:800;font-variant-numeric:tabular-nums;color:var(--c)}.rsDh span.hot{color:#ff6b6b}.rsDl{display:flex;justify-content:space-between;font-size:10px;opacity:.6;margin-top:5px}.rsDl em{font-style:normal}.rsSv{width:100%;height:auto;display:block;border:1px solid color-mix(in srgb,var(--c) 35%,transparent);border-radius:4px;background:rgba(0,0,0,.18)}.rsSv:first-of-type{aspect-ratio:300/70}.rsSv{aspect-ratio:300/46}.rsGr line{stroke:color-mix(in srgb,var(--c) 18%,transparent);stroke-width:1;vector-effect:non-scaling-stroke}.rsDf{display:flex;justify-content:space-between;font-size:12px;margin-top:5px}.rsDf b{font-variant-numeric:tabular-nums}.rsDf i{display:inline-block;width:14px;height:0;border-top:2px solid var(--c);vertical-align:middle;margin-right:4px}.rsDf i.dash{border-top-style:dashed}.rsPace{position:sticky;top:0;z-index:5;background:var(--panel,#16202c);border:1px solid #2f9bff55;border-radius:12px;padding:10px 12px;margin-bottom:8px;box-shadow:0 4px 14px rgba(0,0,0,.25)}.rsPh{display:flex;align-items:center;gap:8px}.rsPh b{flex:1}.rsPv{font-size:20px;font-weight:800;color:#4dc9ff;font-variant-numeric:tabular-nums}.rsSm{border:1px solid #888;background:transparent;color:inherit;border-radius:16px;padding:4px 10px;font-weight:700}.rsSm.on{background:linear-gradient(135deg,#6a3df0,#2f9bff);border-color:transparent;color:#fff}#rsPct{width:100%;margin:8px 0 0;accent-color:#2f9bff;height:26px}#rsPct.dim{opacity:.4}.rsTick{display:flex;justify-content:space-between;font-size:10px;opacity:.55}.rsPi{font-size:12px;margin-top:4px;opacity:.9}.rsSeg{display:flex;flex-wrap:wrap;align-items:center;gap:4px;margin-top:6px;font-size:12px}.rsSeg button{border:1px solid rgba(127,127,127,.45);background:transparent;color:inherit;border-radius:12px;padding:2px 9px;font-size:12px}.rsSeg button.on{background:#2f9bff;border-color:#2f9bff;color:#fff}.rsSeg em{font-style:normal;opacity:.7;margin-left:4px}.rsPace details summary,.rsNext summary,details.rsWarn summary{cursor:pointer;font-size:12px;opacity:.8;margin-top:4px}.rsCardB{border-radius:12px}.rsRole{font-style:normal;font-size:11px;padding:1px 7px;border-radius:9px;background:rgba(47,155,255,.18);color:#7cc4ff;margin-right:4px}.rsHero{border-radius:14px;padding:12px;margin:8px 0;background:linear-gradient(160deg,rgba(47,155,255,.12),rgba(77,214,138,.08));border:1px solid rgba(127,127,127,.25)}.rsHt{display:flex;align-items:baseline;justify-content:space-between}.rsBig{font-size:40px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1}.rsBig small{font-size:18px;margin-left:2px;opacity:.7}.rsSt{font-weight:700;padding:3px 10px;border-radius:12px;background:rgba(127,127,127,.2)}.rsSt.run{background:#1e7d4a;color:#fff}.rsSt.pause{background:#8a6d1f;color:#fff}.rsSt.done{background:#2f9bff;color:#fff}.rsBar.big{height:14px;border-radius:7px}.rsBar.big i{background:linear-gradient(90deg,#2f9bff,#4dd68a);transition:width .8s}.rsTiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin:10px 0}.rsTile{background:rgba(0,0,0,.18);border-radius:10px;padding:8px 10px;display:flex;flex-direction:column}.rsTile small{opacity:.7;font-size:11px}.rsTile b{font-size:18px;font-variant-numeric:tabular-nums}.rsTile em{font-style:normal;font-size:11px;opacity:.75}.rsTile.hl{box-shadow:inset 0 0 0 1px #4dd68a}.rsTile.hl b{color:#4dd68a}.rsTile.bad b{color:#ff6b6b}.rsDrv{margin:6px 0}.rsDrv>div:first-child{display:flex;gap:6px;align-items:center;font-size:13px;flex-wrap:wrap}.rsDrv span{opacity:.8;font-size:12px}.rsMini{height:6px;border-radius:3px;background:rgba(127,127,127,.25);overflow:hidden;margin-top:3px}.rsMini i{display:block;height:100%;background:#4dd68a;transition:width .8s}.rsFile{border:1px solid rgba(127,127,127,.25);border-radius:12px;padding:8px 10px;margin:6px 0}.rsFile.idle{display:flex;gap:8px;align-items:center;opacity:.6}.rsFh{display:flex;gap:8px;align-items:center}.rsIc{width:30px;height:30px;border-radius:8px;display:flex;align-items:center;justify-content:center;flex:none}.rsFn{flex:1;min-width:0}.rsFn b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.rsFn small{opacity:.75;font-size:11px}.rsFp{font-weight:800;font-variant-numeric:tabular-nums}.rsPath{display:block;font-size:10px;opacity:.5;word-break:break-all;margin-top:2px}.rsRec{max-height:420px;overflow:auto;border:1px solid rgba(127,127,127,.2);border-radius:10px}.rsR{display:flex;gap:8px;align-items:center;padding:5px 8px;border-bottom:1px solid rgba(127,127,127,.12)}.rsR>span{color:#4dd68a;font-weight:800}.rsR.bad>span{color:#ff6b6b}.rsR>div{flex:1;min-width:0}.rsR b{display:block;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.rsR small{font-size:11px;opacity:.7}.rsR em{font-style:normal;font-size:11px;opacity:.6;font-variant-numeric:tabular-nums}.rsCard{display:flex;align-items:center;gap:10px;margin:6px 0 10px;padding:12px 14px;border-radius:12px;background:linear-gradient(135deg,#7a1010,#c62828);color:#fff;text-decoration:none;border:2px solid #ff5252;box-shadow:0 0 0 3px rgba(255,82,82,.18)}.rsCard>i{font-style:normal;font-size:28px}.rsCard b{font-size:16px;display:block}.rsCard small{opacity:.9;display:block;margin-top:2px}.rsCard>div{flex:1;min-width:0}.rsCard>span{font-size:22px}.rsWarn{background:rgba(198,40,40,.14);border:1px solid #c62828;border-radius:10px;padding:10px;margin-bottom:8px}.rsRow{display:flex;align-items:center;gap:8px;margin:4px 0}.rsRow label{width:110px;flex:none}.rsRow select{flex:1;min-width:0;padding:6px}.rsGo{width:100%;padding:14px;margin:8px 0;font-size:17px;font-weight:700;color:#fff;background:#c62828;border:0;border-radius:12px}.rsBar{height:10px;border-radius:5px;background:rgba(127,127,127,.25);margin:6px 0;overflow:hidden}.rsBar i{display:block;height:100%;background:#4dd68a}.rsT{margin:3px 0}.rsU{font-size:12px;padding:2px 0;border-bottom:1px solid rgba(127,127,127,.15);word-break:break-all}.rsU span{color:#ff8a80;margin-right:6px;font-weight:700}.rsU em{float:right;font-style:normal;opacity:.7;margin-left:6px}.wsCard{display:flex;flex-direction:column;align-items:flex-start;gap:2px;padding:12px;border-radius:12px;border:1px solid var(--line);background:var(--card);color:inherit;text-align:left;cursor:pointer}
.wsCard i{font-style:normal;font-size:22px}.wsCard b{font-size:14px}.wsCard small{font-size:11.5px;opacity:.7;line-height:1.35}
.wsCard.pinned{box-shadow:inset 0 0 0 2px #ffc94d}.wsCard.pinned b::after{content:' 📌'}
.tbgS{padding:12px;border-radius:12px;border:1px solid rgba(63,182,242,.4);background:rgba(63,182,242,.1);font-size:13.5px;cursor:pointer;margin-bottom:6px}.tbgS span{float:right;opacity:.75}
.toast{position:fixed;left:50%;bottom:20vh;transform:translateX(-50%);background:rgba(20,24,32,.92);color:#fff;-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);border:1px solid var(--line2);padding:8px 14px;border-radius:10px;z-index:10000;font-size:13px;line-height:1.45;display:none;max-width:min(90vw,560px);text-align:center;box-shadow:0 6px 22px rgba(0,0,0,.45);pointer-events:none}
/* ---- 卡片（檔案總管） */
.grid{display:grid;grid-template-columns:repeat(var(--cols,2),minmax(0,1fr));gap:8px;touch-action:pan-y}
.c{background:var(--card);border:1px solid var(--line2);border-radius:9px;overflow:hidden;cursor:pointer;position:relative;min-width:0;-webkit-touch-callout:none;user-select:none;-webkit-user-select:none}
.c.sel{outline:3px solid var(--vline);outline-offset:-3px}
.c .th{aspect-ratio:16/9;background:#05080c center/cover no-repeat;display:flex;align-items:center;justify-content:center;color:var(--sub);font-size:11px;position:relative}
.c .du{position:absolute;right:4px;bottom:4px;font:600 11px/1.25 ui-monospace,Consolas,monospace;background:rgba(0,0,0,.6);color:#fff;padding:0 5px;border-radius:4px}
.c .cutb{position:absolute;top:5px;left:31px;height:22px;border-radius:6px;font-weight:800;font-size:11.5px;display:flex;align-items:center;padding:0 6px;background:#2f8fe0;color:#fff;white-space:nowrap}.c .cutb.run{background:#f0a030;color:#0b0e13}.c .cutb.nog{left:5px}
.c .gb{position:absolute;top:5px;left:5px;min-width:22px;height:22px;border-radius:6px;font-weight:800;font-size:13px;display:flex;align-items:center;justify-content:center;color:#fff;padding:0 5px}
.c .fl{position:absolute;top:5px;right:6px;font-size:12px;text-shadow:0 0 3px #000}
.c .ck{display:none;position:absolute;right:6px;top:6px;width:22px;height:22px;border-radius:50%;border:2px solid #fff;background:rgba(0,0,0,.4)}
.grid.selmode .c .ck{display:block}.grid.selmode .c.sel .ck{background:var(--vline);border-color:var(--vline)}.grid.selmode .c .fl{right:34px}
.c .nm{font-weight:800;color:var(--strong);font-size:12.5px;padding:5px 7px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.c .mch{display:flex;gap:4px;padding:4px 6px 6px;flex-wrap:nowrap;overflow:hidden}
.ch{border-radius:7px;padding:2px 6px;line-height:1.3;text-align:center;font-size:11.5px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-variant-numeric:tabular-nums}
.ch.xd{background:color-mix(in srgb,var(--blue) 15%,transparent);color:var(--blue)}.ch.xs{background:color-mix(in srgb,var(--sub) 13%,transparent);color:var(--sub)}
.ch.xp{background:color-mix(in srgb,var(--purple) 16%,transparent);color:var(--purple)}
.pinin{display:contents}@media (max-width:520px){#fbtn{max-width:22vw!important;padding:0 8px}#findb,#smode,.pinin .pill{padding:0 8px;font-size:12px}}.grid.tiny{gap:2px}.grid.tiny .nm,.grid.tiny .gb,.grid.tiny .mch{display:none}.grid.tiny .dur{font-size:9px;padding:0 2px}@media (max-width:760px){.pint{display:none}}
.grid.dense{gap:5px}.grid.dense .nm{font-size:11px;padding:3px 5px 0}.grid.dense .mch{display:none}.grid.dense .gb{min-width:18px;height:18px;font-size:11px;top:3px;left:3px}
.grid.one .c{display:grid;grid-template-columns:42% 1fr;align-items:center}.grid.one .c .th{grid-row:1/3}.grid.one .nm{white-space:normal;font-size:14px}.grid.one .mch{flex-wrap:wrap}
.gS{background:var(--S);color:#111!important}.gA{background:var(--A);color:#111!important}.gE{background:var(--E)}.gF{background:var(--F)}
.c.bS{border-color:var(--S)}.c.bA{border-color:var(--A)}.c.bE{border-color:var(--E)}.c.bF{border-color:var(--F)}
.chips{display:flex;gap:6px;overflow-x:auto;padding:8px 0 2px;scrollbar-width:none}.chips::-webkit-scrollbar{display:none}
.hidn{font-size:12px;color:var(--sub);margin:4px 2px}.hidn a{color:var(--vline)}
#more{color:var(--sub);text-align:center;padding:18px 0}
/* ---- 一部影片 */
.ov{position:fixed;inset:0;z-index:50;background:var(--bg);overflow-y:auto;padding-bottom:calc(84px + var(--safe))}
.rph{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:8px;background:var(--nav);border-bottom:1px solid var(--line);padding:calc(38px + env(safe-area-inset-top,0px)) 10px 8px}
.rph .back{width:36px;height:36px;padding:0;border-radius:10px;border:1px solid var(--line);background:var(--tab);color:inherit;font-size:20px;flex:none}
.rph .t{flex:1;min-width:0}.rph .t b{display:block;color:var(--strong);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.rph .t small{color:var(--sub);font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block}
.gbt{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;margin:8px 0}
.gbt button.D{border-color:var(--S);color:var(--S);font-size:15px}.gbt button.D small{color:inherit;opacity:.85}
#fov #gb{position:sticky;z-index:4;background:var(--bg);margin:0 -10px;padding:8px 10px;box-shadow:0 6px 10px -8px rgba(0,0,0,.6)}
.rvsep{display:flex;align-items:center;justify-content:center;color:var(--vline);font-weight:800;font-size:13px;border-top:1px dashed var(--line);margin:0 -10px;padding:0 10px;text-align:center}
.gbt button{padding:10px 0;font-size:17px;font-weight:800;border-radius:10px;border:2px solid var(--line);background:var(--btn)}
.gbt button small{display:block;font-size:11px;font-weight:700;color:var(--sub);font-variant-numeric:tabular-nums}
.gbt button.S{border-color:var(--S);color:var(--S)}.gbt button.A{border-color:var(--A);color:var(--A)}.gbt button.E{border-color:var(--E);color:var(--E)}.gbt button.F{border-color:var(--F);color:var(--F)}
.gbt button.S small,.gbt button.A small,.gbt button.E small,.gbt button.F small{color:inherit;opacity:.85}
.gbt button.on.S{background:var(--S);border-color:var(--S);color:#111}.gbt button.on.A{background:var(--A);border-color:var(--A);color:#111}.gbt button.on.E{background:var(--E);border-color:var(--E);color:#06202b}
.gbt button.on.F{background:var(--F);border-color:var(--F);color:#fff}.gbt button.on.N{background:var(--tabon);border-color:var(--tabline)}.gbt button.on small{color:inherit}
.vgBar{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:6px 0}
.vgGrid{display:grid;grid-template-columns:repeat(var(--vgc,4),minmax(0,1fr));gap:0;user-select:none;-webkit-user-select:none;touch-action:pan-y;margin:0 -10px}
.vgT{position:relative;background:#151a22 no-repeat;overflow:hidden;cursor:pointer;-webkit-touch-callout:none}
.vgT b{position:absolute;left:50%;bottom:3px;transform:translateX(-50%);font:600 11px/1.25 ui-monospace,Consolas,monospace;color:#fff;background:rgba(0,0,0,.5);padding:0 5px;border-radius:4px;text-shadow:0 1px 2px #000;pointer-events:none;white-space:nowrap}
.vgGrid.small .vgT b{font-size:8px;padding:0 2px}
.vgT.on::after{content:"";position:absolute;inset:0;border:3px solid #fff;box-shadow:inset 0 0 0 1px rgba(0,0,0,.6);pointer-events:none}
.vgT.on b{background:#fff;color:#111;text-shadow:none}.vgT.anchor::after{content:"";position:absolute;inset:0;border:3px dashed var(--orange);pointer-events:none}
.vgAct{position:fixed;left:0;right:0;bottom:0;z-index:60;background:var(--nav);border-top:1px solid var(--line);padding:8px 10px calc(8px + var(--safe));display:flex;gap:6px;overflow-x:auto;align-items:center}
.vgAct .pill{flex:none}
.kv{display:grid;grid-template-columns:auto 1fr;gap:3px 10px;font-size:12.5px}.kv b{color:var(--sub);font-weight:400}
/* ---- 選單、播放 */
.sheet{position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.45);display:flex;align-items:flex-end}
.sheet>div{background:var(--panel);width:100%;max-height:84vh;overflow-y:auto;border-radius:16px 16px 0 0;padding:14px 12px calc(14px + var(--safe));border-top:1px solid var(--line)}
.sheet h3{margin:0 0 10px;color:var(--strong)}
.mi{display:block;width:100%;text-align:left;background:none;border:0;border-bottom:1px solid var(--line);color:var(--text);padding:12px 4px;font-size:15px}.mi:last-child{border-bottom:0}.mi.cur{color:var(--vline);font-weight:800}
.fr{display:flex;align-items:center;gap:10px;margin:8px 0}.fr>b{width:58px;color:var(--sub);font-weight:600;flex:none;font-size:13px}.fr .seg{flex-wrap:wrap}
.vbox{position:fixed;inset:0;z-index:9500;background:rgba(0,0,0,.85);display:flex;align-items:center;justify-content:center;padding:8px}
.vw{width:min(96vw,900px);max-height:94vh;display:flex;flex-direction:column;gap:6px}.vh{display:flex;align-items:center;gap:6px;color:#fff}.vh b{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vw video{width:100%;max-height:78vh;background:#000;border-radius:8px;display:block}
.vst{position:relative;touch-action:pan-y;-webkit-user-select:none;user-select:none}
.swp{position:absolute;left:50%;top:45%;transform:translate(-50%,-50%);background:rgba(0,0,0,.62);color:#fff;border-radius:14px;padding:10px 18px;text-align:center;pointer-events:none;z-index:30;display:none;font-variant-numeric:tabular-nums;min-width:150px}
.swp b{display:block;font-size:24px;font-weight:800;line-height:1.2}.swp small{font-size:13px;opacity:.85}.swp i{display:block;height:4px;border-radius:2px;background:rgba(255,255,255,.25);margin-top:7px;overflow:hidden}.swp i u{display:block;height:100%;background:var(--accent);width:0}
.vtip{color:#aab3c0;font-size:11.5px;text-align:center}
input,select,textarea{background:var(--btn);color:var(--text);border:1px solid var(--line);border-radius:9px;padding:8px 10px;font:inherit;font-size:15px;max-width:100%}
#undo{position:fixed;right:10px;bottom:calc(76px + var(--safe));z-index:90;box-shadow:0 4px 14px rgba(0,0,0,.4)}
/* ---- 最上面正中間「📊 效能／🖥 背景／✂ 轉檔／🗂 分類」浮動視窗（照 TikLive） */
#sysFab{position:fixed;top:calc(env(safe-area-inset-top,0px) + 7px);left:50%;transform:translateX(-50%);z-index:9810;display:flex;gap:6px;pointer-events:none}
#sysFab button{pointer-events:auto;height:24px;padding:0 8px;border-radius:12px;border:1px solid rgba(140,150,165,.5);background:rgba(18,22,30,.88);color:#fff;font-weight:800;font-size:11px;margin:0;cursor:pointer;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,.35);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);position:relative}
#sysFab button.on{background:#1f8ef1;border-color:#1f8ef1}
#sysFab em{font-style:normal;position:absolute;top:-7px;right:-6px;background:var(--red);color:#fff;border-radius:8px;padding:0 4px;font-size:9.5px;line-height:14px}#sysFab em.r{top:auto;bottom:-7px;background:#1f8ef1}
@media (max-width:430px){.logo{font-size:0;gap:0}.logo i{width:11px;height:11px}.logo img{width:28px;height:28px}.clk{display:none}}
#sysPop{position:fixed;inset:0;z-index:9800;background:rgba(0,0,0,.28)}
.sysPopW{position:absolute;left:15%;width:70%;top:calc(env(safe-area-inset-top,0px) + 38px);height:50%;display:flex;flex-direction:column;background:var(--bg);color:var(--text);border:1px solid rgba(140,150,165,.45);border-radius:12px;box-shadow:0 14px 40px rgba(0,0,0,.6);overflow:hidden}
.sysPopW>*{zoom:.86}
@media (max-width:520px){.sysPopW{left:4%;width:92%}}
@media (min-width:900px){.sysPopW{left:calc(50% - 360px);width:720px}}
.sysPopH{display:flex;align-items:center;gap:8px;padding:8px 10px;border-bottom:1px solid rgba(127,127,127,.25)}.sysPopH b{font-size:15px;white-space:nowrap}.sysPopN{flex:1;font-size:11.5px;opacity:.6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sysPopX{width:40px;height:32px;margin:0;border:0;border-radius:9px;background:rgba(127,127,127,.18);color:inherit;font-size:16px;cursor:pointer}
.sysPopB{flex:1 1 auto;min-height:0;overflow-y:auto;overscroll-behavior:contain;padding:8px 10px 12px;-webkit-overflow-scrolling:touch}
.sysPopR{flex:none;height:22px;display:flex;align-items:center;justify-content:center;cursor:ns-resize;touch-action:none;border-top:1px solid rgba(127,127,127,.25);background:rgba(127,127,127,.06)}
.sysPopR i{width:56px;height:5px;border-radius:3px;background:rgba(160,170,185,.6)}.sysPopR.on{background:rgba(31,142,241,.18)}.sysPopR.on i{background:#1f8ef1}
@media (pointer:coarse){.sysPopR{height:34px}.sysPopR i{width:70px;height:6px}}
.pfG{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
.pfC{border:1px solid var(--line);border-radius:10px;padding:8px 10px;background:var(--card)}.pfC small{color:var(--sub);font-size:11.5px}.pfC b{display:block;font-size:22px;color:var(--strong);font-variant-numeric:tabular-nums}
.pfC svg{display:block;width:100%;height:34px;margin-top:4px}
.pg{height:6px;background:var(--track);border-radius:6px;overflow:hidden}.pg i{display:block;height:100%;background:var(--vline)}
.edjH{font-size:12px;opacity:.7;margin:10px 0 4px;font-weight:700}
.edjI{border:1px solid rgba(140,150,165,.3);border-radius:10px;padding:7px 9px;margin:0 0 6px;background:rgba(127,127,127,.06)}.edjI.run{border-color:#1f8ef1}
.edjT{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.edjT b{font-size:13.5px;min-width:0;overflow:hidden;text-overflow:ellipsis}.edjT em{font-style:normal;font-size:11px;font-weight:800;padding:1px 7px;border-radius:9px;background:#f0ad4e;color:#111}
.edjI.run .edjT em{background:#1f8ef1;color:#fff}.edjI.ok .edjT em{background:var(--green);color:#06210f}.edjI.bad .edjT em{background:var(--red);color:#fff}.edjI small{display:block;font-size:11.5px;opacity:.75;margin-top:2px}
.lvsC{display:flex;align-items:center;gap:10px;width:100%;border:1px solid var(--line);border-left:5px solid var(--c);border-radius:10px;padding:9px 10px;margin-bottom:6px;background:var(--card);text-align:left}
.lvsC b{font-size:18px;width:26px;color:var(--c)}.lvsC span{flex:1}.lvsC em{font-style:normal;font-weight:800;font-size:16px;color:var(--strong)}.lvsC small{color:var(--sub);font-size:11.5px;width:110px;text-align:right}
.lvsBar{display:flex;height:12px;border-radius:6px;overflow:hidden;margin:6px 0 10px;background:var(--track)}.lvsBar i{display:block;height:100%}
/* ---- 設定（照 TikLive：左邊分類、右邊內容） */
.s2{display:flex;gap:10px;align-items:flex-start}
.scat{position:sticky;top:calc(var(--hh,96px) + 8px);flex:none;width:clamp(96px,28vw,200px);display:flex;flex-direction:column;gap:5px;max-height:calc(100vh - var(--hh,96px) - 20px);overflow-y:auto}
.scat .sch{font-size:11px;color:var(--sub);margin:6px 4px 0;font-weight:700}
.scat button{text-align:left;background:var(--tab);border:1px solid var(--line);color:var(--sub);border-radius:9px;padding:9px 8px;font-weight:700;font-size:13px;line-height:1.25}
.scat button small{display:block;font-weight:500;font-size:10.5px;opacity:.75;margin-top:2px}.scat button.on{background:var(--tabon);border-color:var(--tabline);color:var(--strong)}
.ssearch{width:100%;height:34px;border-radius:9px;border:1px solid var(--line);background:var(--card);color:inherit;padding:0 8px;font-size:13px;margin-bottom:2px}
.sbody{flex:1;min-width:0}.stt{font-size:19px;margin:2px 2px 12px;color:var(--strong)}
.ssec{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:6px 14px;margin-bottom:14px}
.si{padding:14px 0;border-bottom:1px solid var(--line)}.si:last-child{border-bottom:0}.si>b{display:block;color:var(--strong);margin-bottom:9px;font-size:15px}.si small{display:block;color:var(--sub);font-size:12px;margin-top:8px;line-height:1.5}
.si .seg{flex-wrap:wrap}.si .seg button{height:36px}
.pnum{display:flex;align-items:center;gap:6px}.pnum button{width:42px;height:40px;border-radius:10px;border:1px solid var(--line);background:var(--btn);color:var(--text);font-size:20px;font-weight:700}
.pnum input{width:96px;height:40px;text-align:center;border-radius:10px;font-size:16px;font-weight:700;color:var(--strong)}.pnum span{color:var(--sub)}
.tg{position:relative;width:48px;height:28px;flex:none;display:inline-block}.tg input{opacity:0;width:0;height:0}
.tg i{position:absolute;inset:0;background:var(--track);border-radius:20px;transition:.2s}.tg i::before{content:"";position:absolute;width:22px;height:22px;left:3px;top:3px;background:#cfd8e3;border-radius:50%;transition:.2s}
.tg input:checked+i{background:var(--green)}.tg input:checked+i::before{transform:translateX(20px)}
.si.tgr{display:flex;align-items:center;gap:10px}.si.tgr>b{margin:0;flex:1}
.extg{display:flex;flex-wrap:wrap;gap:6px}
/* ---- 👤 人物 */
.pgr{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:8px}
.pc2{display:flex;flex-direction:column;align-items:center;text-align:center;gap:3px;padding:8px 4px 7px;border-radius:10px;border:1px solid var(--line2);background:var(--card);position:relative;-webkit-touch-callout:none;user-select:none;cursor:pointer}
.pc2.sel{outline:3px solid var(--vline);outline-offset:-3px}.pc2.hid{opacity:.55}
.fav{width:64px;height:64px;border-radius:50%;background:#2b3440 no-repeat;border:1.5px solid var(--line2);flex:none;overflow:hidden}
.pc2 b{font-size:12.5px;color:var(--strong);max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pc2.un b{color:var(--sub);font-weight:600}
.pc2 small{font-size:11px;color:var(--sub)}
.fstrip{display:flex;gap:6px;overflow-x:auto;padding:4px 0 6px}.fstrip .fav{width:56px;height:56px;border-radius:10px;cursor:pointer}.fstrip .fav.sel{outline:3px solid var(--red);outline-offset:-3px}
.pfile{display:flex;gap:9px;padding:9px 0;border-bottom:1px solid var(--line);align-items:flex-start}.pfile:last-child{border-bottom:0}
.pfile .th2{width:110px;flex:none;aspect-ratio:16/9;border-radius:7px;background:#05080c no-repeat;overflow:hidden}
.tchips{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}.tchips button{border:1px solid var(--line);background:var(--btn);border-radius:7px;padding:2px 6px;font:600 11.5px/1.3 ui-monospace,Consolas,monospace;color:var(--vline)}
.login{max-width:360px;margin:12vh auto 0;text-align:center;padding:0 12px}.login input{width:100%;font-size:22px;text-align:center;letter-spacing:4px;margin:14px 0}
pre.log{white-space:pre-wrap;word-break:break-all;font:12px/1.4 ui-monospace,Consolas,monospace;background:var(--chart);border:1px solid var(--line);border-radius:10px;padding:8px;max-height:68vh;overflow:auto}
.list .it{display:flex;gap:10px;padding:9px 2px;border-bottom:1px solid var(--line);align-items:center}.list .it:last-child{border-bottom:0}
.list .it.sel{background:rgba(67,217,255,.14);outline:2px solid var(--vline);outline-offset:-2px;border-radius:8px}.fgear{flex:none;width:34px;height:34px;border-radius:9px;border:1px solid var(--line);background:transparent;color:var(--fg,inherit);font-size:16px}

/* V0.4.56 介面整理：統一圓角、間距、按下回饋；卡片說明最多兩行，畫面更乾淨 */
.pill{border-radius:999px;padding:6px 13px;transition:background .15s,border-color .15s,transform .08s;-webkit-tap-highlight-color:transparent}
.pill:active{transform:scale(.96)}
.pill.acc{box-shadow:0 2px 8px -3px var(--accent)}
.chips{gap:7px}
.wsGrid{gap:10px}
.wsCard{min-height:92px;border-radius:14px;padding:12px 12px 10px;transition:transform .08s,border-color .15s,background .15s;-webkit-tap-highlight-color:transparent}
.wsCard:active{transform:scale(.97)}
@media (hover:hover){.wsCard:hover{border-color:var(--line2);background:var(--hover)}.pill:hover{border-color:var(--line2)}}
.wsCard i{font-size:24px;line-height:1.1;margin-bottom:2px}
.wsCard b{font-size:14.5px;line-height:1.25}
.wsCard small{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tgh{font-size:13px;letter-spacing:.5px;margin:18px 4px 8px;text-transform:none}
.ssearch,#tlq{height:38px;border-radius:12px;padding:0 12px;font-size:14px}
.si{padding:13px 2px}
.si>b{font-size:15px;letter-spacing:.2px}
.tbgS{border-radius:14px}
#tb .si{border-bottom:1px solid var(--line)}
input,select,textarea{border-radius:10px}
</style></head><body>
<div id="app"></div><div class="toast" id="toast"></div>
<script>
const VER='__VER__';
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const GN={S:'無條件保存',A:'保存',E:'觀察',F:'刪除','':'未分級'};
const TAGS={red:'🔴',orange:'🟠',yellow:'🟡',green:'🟢',blue:'🔵',purple:'🟣'};
const LS={get(k,d){try{const x=localStorage.getItem('vs_'+k);return x==null?d:JSON.parse(x)}catch(e){return d}},set(k,v){try{localStorage.setItem('vs_'+k,JSON.stringify(v))}catch(e){}}};
let TOK=LS.get('tok','')||'';
const V0=LS.get('view',{});
const S={tab:'fx',folder:V0.folder||'',flt:V0.flt||'all',q:V0.q||'',sort:V0.sort||'name',sub:V0.sub!==false,cols:LS.get('cols','auto'),
  rows:[],total:0,loading:false,gen:0,sel:new Set(),selMode:false,state:null,undo:null,folders:null,people:null,hidden:[]};
const UI=Object.assign({mode:'dark',fs:'m'},LS.get('ui',{}));
function uiMode(){if(UI.mode!=='auto')return UI.mode==='light'?'light':'dark';const h=new Date().getHours();const L=(S&&S.state&&S.state.theme_hours)||[7,19];return h>=L[0]&&h<L[1]?'light':'dark'}   // V0.2.66 🌗 跟著時間
function applyUI(){document.documentElement.dataset.mode=uiMode();document.documentElement.style.setProperty('--fs',{s:'13px',m:'14px',l:'15.5px'}[UI.fs]||'14px');
  const m=document.querySelector('meta[name=theme-color]');if(m)m.content=uiMode()==='light'?'#e8ecf1':'#0a0e13'}
setInterval(()=>{try{if(UI.mode==='auto'&&document.documentElement.dataset.mode!==uiMode())applyUI()}catch(e){}},60000);
applyUI();
function saveView(){LS.set('view',{folder:S.folder,flt:S.flt,q:S.q,sort:S.sort,sub:S.sub})}
function fmtB(b){b=+b||0;const u=['B','KB','MB','GB','TB'];let i=0;while(b>=1024&&i<4){b/=1024;i++}return (i?b.toFixed(b>=100?0:1):b)+' '+u[i]}
function fmtT(s){s=Math.max(0,Math.round(+s||0));const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;return (h?h+':'+String(m).padStart(2,'0'):m)+':'+String(x).padStart(2,'0')}
function eta(s){if(!s)return'—';s=+s;if(s>=86400)return Math.floor(s/86400)+' 天 '+Math.floor(s%86400/3600)+' 小時';if(s>=3600)return Math.floor(s/3600)+' 小時 '+Math.floor(s%3600/60)+' 分';return Math.max(1,Math.floor(s/60))+' 分鐘'}
let TT;function toast(t,ms=2600){const d=$('#toast');d.textContent=t;d.style.display='block';clearTimeout(TT);TT=setTimeout(()=>d.style.display='none',ms)}
const vib=n=>{try{navigator.vibrate&&navigator.vibrate(n||12)}catch(e){}};
async function api(path,body,opt={}){
  const o={method:body!==undefined?'POST':'GET',headers:{'X-VS-Token':TOK},credentials:'same-origin',cache:'no-store'};
  if(body!==undefined){if(body instanceof Blob||body instanceof ArrayBuffer){o.body=body}else{o.headers['Content-Type']='application/json';o.body=JSON.stringify(body)}}
  let r;try{r=await fetch(path,o)}catch(e){if(!opt.quiet)toast('連不到電腦：Tailscale 有開嗎？電腦開著嗎？');throw e}
  let j={};try{j=await r.json()}catch(e){}
  if(r.status===401&&j.login){showLogin();throw new Error('login')}
  if(!r.ok&&!opt.quiet&&j.message)toast(j.message);
  return j}
const U=(p,q)=>p+'?'+new URLSearchParams(q).toString();
/* 預覽格子：從預覽圖大張用 CSS 切出第 k 張 */
function tileCSS(fid,k,cols,rows){const per=cols*rows,s=Math.floor(k/per),q=k%per,cx=q%cols,cy=Math.floor(q/cols);
  return `background-image:url('${U('/api/sheet',{id:fid,i:s})}');background-size:${cols*100}% ${rows*100}%;background-position:${cols>1?cx*100/(cols-1):0}% ${rows>1?cy*100/(rows-1):0}%`}
/* 臉：同一張大圖，放大到臉填滿方框（臉周圍多留一點） */
function faceCSS(f){if(!f)return '';const cols=f.cols||10,rows=f.rows||10,ar=(f.vw&&f.vh)?f.vw/f.vh:16/9;
  const s=Math.min(1,Math.max(f.w,f.h/ar)*1.7),sy=s*ar;            /* 方框邊長：s 個格子寬＝sy 個格子高 */
  const col=f.q%cols,row=Math.floor(f.q/cols),cx=col+f.x+f.w/2,cy=row+f.y+f.h/2;
  const bx=cols/s,by=rows/sy;const px=bx>1?(cx/s-.5)/(bx-1)*100:0,py=by>1?(cy/sy-.5)/(by-1)*100:0;
  return `background-image:url('${U('/api/sheet',{id:f.file_id,i:f.si||0})}');background-size:${(bx*100).toFixed(2)}% ${(by*100).toFixed(2)}%;background-position:${px.toFixed(3)}% ${py.toFixed(3)}%`}

/* ================= 手機返回鍵（照 TikLive）：先關最上面的（浮動視窗 → 選單 → 播放 → 影片頁 → 多選 → 子頁），最後才離開；離開前再按一次確認 ================= */
const BK=[];const IGN=[];let LASTBACK=0;
function bkPush(fn){BK.push(fn);try{history.pushState({bk:BK.length},'')}catch(e){}}
function bkGo(n){return new Promise(res=>{IGN.push(res);try{history.go(-n)}catch(e){}setTimeout(()=>{const k=IGN.indexOf(res);if(k>=0){IGN.splice(k,1);res()}},450)})}
function bkDone(fn){const i=BK.lastIndexOf(fn);if(i<0)return Promise.resolve();const n=BK.length-i;BK.splice(i);return bkGo(n)}
window.addEventListener('popstate',e=>{
  if(IGN.length){IGN.shift()();return}
  const d=(e.state&&e.state.bk)||0;
  if(BK.length>d){const F_=BK.splice(d);for(let i=F_.length-1;i>=0;i--){try{F_[i](true)}catch(x){}}return}
  if(e.state&&e.state.root){
    if(S.tab!=='fx'||(location.hash&&location.hash!=='#fx')){history.pushState({guard:1},'','#fx');route();return}
    if(Date.now()-LASTBACK<2200){history.back();return}
    LASTBACK=Date.now();toast('再按一次返回鍵離開');history.pushState({guard:1},'')}});
function layer(el,onClose,reuse){let done=false;const close=fromBack=>{if(done)return Promise.resolve();done=true;try{onClose&&onClose()}catch(e){}el.remove();return fromBack===true?Promise.resolve():bkDone(close)};
  el._close=close;el._kill=()=>{if(done)return;done=true;try{onClose&&onClose()}catch(e){}el.remove()};if(reuse)BK.push(close);else bkPush(close);return close}
function replaceLayer(old){const k=old&&old._close?BK.lastIndexOf(old._close):-1;if(k<0||k!==BK.length-1){if(old&&old._close)old._close();return false}BK.splice(k,1);old._kill();return true}
function closeAll(){if(!BK.length)return Promise.resolve();const n=BK.length;const F_=BK.splice(0);for(let i=F_.length-1;i>=0;i--){try{F_[i](true)}catch(x){}}return bkGo(n)}

// ---------------------------------------------------------------- 登入
async function boot(){
  if('serviceWorker' in navigator){navigator.serviceWorker.register('sw.js').catch(()=>{})}
  let h={};try{h=await api('/api/hello',undefined,{quiet:true})}catch(e){$('#app').innerHTML='<div class="login"><div class="panel"><h2>連不到電腦</h2><p class="mu">確認手機的 Tailscale 開著、電腦上的 SortCut 開著，再重新整理。</p><button class="pill acc" onclick="location.reload()">重試</button></div></div>';return}
  if(!h.authed)return showLogin(h);
  shell();roBadge(!!h.ro);   // V0.4.30
}
function showLogin(h){
  $('#app').innerHTML=`<div class="login"><div class="logo" style="justify-content:center;font-size:22px"><img src="icon-192.png" alt="" style="width:40px;height:40px;border-radius:11px">SortCut</div><div class="mu" style="margin-top:6px">影片初剪整理　手機遙控　V${esc(VER)}</div>
  <div class="panel" style="margin-top:18px">${h&&h.pin_set===false?'<p class="mu">電腦上還沒設定 PIN：到 SortCut 的 設定 → 📱 手機網頁 設一個。</p>':''}
  <input id="pin" type="password" autocomplete="current-password" placeholder="PIN"><button class="pill acc" style="width:100%;padding:11px" id="go">登入</button>
  <p class="mu" style="margin-bottom:0">登入一次就會記住，程式重開、更新都不用再輸入。</p></div></div>`;
  const go_=async()=>{const j=await api('/api/login',{pin:$('#pin').value},{quiet:true});if(j.ok){TOK=j.token;LS.set('tok',TOK);shell();roBadge(!!j.ro)}else toast(j.message||'PIN 不對')};
  $('#go').onclick=go_;$('#pin').onkeydown=e=>{if(e.key==='Enter')go_()};setTimeout(()=>$('#pin').focus(),100);
}

// ---------------------------------------------------------------- 外框（照 TikLive：上面 logo＋分頁，正中間浮動按鈕）
const V=()=>$('#v');
const isPC=()=>document.body.classList.contains('pc');
function setView(v){LS.set('view',v);closeAll().then(()=>{document.body.classList.toggle('pc',v==='pc');document.body.classList.remove('fopen');shell();toast(v==='pc'?'🖥 網頁版（這台瀏覽器會記住；左上可以切回手機版）':'📱 手機版')})}
(()=>{const q=location.search;if(/[?&]m=1/.test(q))LS.set('view','phone');else if(/[?&]pc=1/.test(q))LS.set('view','pc');if(LS.get('view','')==='pc')document.body.classList.add('pc')})();
let INSTP=null;window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();INSTP=e;const b=$('#inst');if(b)b.hidden=false});
let SHELL=false;
function shell(){
  $('#app').innerHTML=`<header><div class="bar"><div class="logo"><img src="icon-192.png" alt="">SortCut</div>${mswHTML(curMode())}<button id="inst" class="inst" hidden>📲 安裝 App</button><div class="rt"><div id="clk" class="clk"></div><span class="ver" title="程式版本">V${esc(VER)}</span><button class="vsw" id="vsw" title="${isPC()?'切回手機版介面':'切到網頁版（電腦／平板的大螢幕版面）'}">${isPC()?'📱 手機版':'🖥 網頁版'}</button></div>${lvHTML()}</div>
<nav id="tabs">${tabsHTML(curMode())}</nav></header><main id="v"></main>`;
  $('#vsw').onclick=()=>setView(isPC()?'phone':'pc');
  setTimeout(fabFit,50);setTimeout(fabFit,600);
  if(!window.LVON){window.LVON=1;lvStart(b=>api('/api/yield',b,{quiet:true}))}else lvTick();   // V0.5.71 🤝 右上角 Lv
  $('#inst').hidden=!INSTP;$('#inst').onclick=async()=>{if(!INSTP)return;INSTP.prompt();try{await INSTP.userChoice}catch(e){}INSTP=null;$('#inst').hidden=true};
  $('#tabs').onclick=e=>{const b=e.target.closest('button[data-t]');if(!b)return;if(b.dataset.t==='fcx'){location.href='/fc/';return}   // V0.5.00 🗂 整理＝FileCompare 的手機版
  if(location.hash==='#'+b.dataset.t){window.scrollTo({top:0,behavior:'smooth'});return}closeAll().then(()=>{location.hash=b.dataset.t})};
  const hh=()=>document.documentElement.style.setProperty('--hh',$('header').offsetHeight+'px');hh();window.addEventListener('resize',hh);
  if(!SHELL){window.addEventListener('hashchange',route);SHELL=true;
    const start=(location.hash||'#'+LS.get('tab','dvs'));try{history.replaceState({root:1},'',start);history.pushState({guard:1},'',start)}catch(e){}
    sysFabInit();setInterval(poll,3000)}
  route();poll();
}
// V0.5.68 🎛 模式：vs（10 秒剪輯）／h265（轉檔）；整理是另一頁（/fc/）
function curMode(){const t=(location.hash||'').slice(1).split('/')[0];if(t==='dh'||t==='cv')return 'h265';if(t==='dvs'||t==='fx')return 'vs';return LS.get('mode','vs')==='h265'?'h265':'vs'}
function tabsHTML(m){return (m==='h265'?[['dh','📊 總覽'],['cv','🗜 轉檔工作區'],['tools','工具','tset'],['set','設定','tset']]:[['dvs','📊 總覽'],['fx','▦ 10 秒剪輯'],['tools','工具','tset'],['set','設定','tset']]).map(([t,l,c])=>`<button data-t="${t}" class="${c||''}">${l}</button>`).join('')}
function modeSync(){const m=curMode();LS.set('mode',m);const n=$('#tabs');if(n&&n.dataset.m!==m){n.dataset.m=m;n.innerHTML=tabsHTML(m)}const w=$('#msw');if(w){w.dataset.m=m;$$('#msw button').forEach(b=>b.classList.toggle('on',b.dataset.m===m))}}
function route(){modeSync();const h=(location.hash||'#dvs').slice(1);const [t,arg]=h.split('/');const tab=['fx','rv','ppl','tools','set','dvs','dh','cv'].includes(t)?t:(t==='tool'?'tools':(t==='person'?'ppl':'dvs'));
  S.tab=tab;LS.set('tab',tab);$$('#tabs button').forEach(b=>b.classList.toggle('on',b.dataset.t===tab));if(S.selMode)setSel(false);if(PP.selMode)pSel(false);
  ['#cvbar','#pbar'].forEach(x=>{const b=$(x);b&&b.remove()});V().onclick=null;V().onchange=null;S.gen++;
  if(t==='tool'&&arg)viewTool(decodeURIComponent(arg));else if(t==='person'&&arg)viewPerson(+arg);else if(tab==='rv'||tab==='ppl'||tab==='fcx'){LS.set('tab','fx');try{history.replaceState(null,'','#fx')}catch(e){}location.href='/fc/';return}else ({fx:viewFx,tools:viewTools,set:viewSet,dvs:()=>dzShow(V(),'vs',api),dh:()=>dzShow(V(),'h265',api),cv:()=>{viewTool('conv');$$('#tabs button').forEach(b=>b.classList.toggle('on',b.dataset.t==='cv'))}})[tab]();window.scrollTo(0,0)}
function connBar(ok){try{if(!(S.state&&S.state.lab&&S.state.lab.conn_bar))return;let b=$('#connb');   // V0.4.02 📶 連不到電腦時頂端一直顯示，連回來自動消失
  if(ok){S._lastOk=Date.now();if(b){b.textContent='✅ 連回來了';b.style.background='#1d3a2a';setTimeout(()=>{const x=$('#connb');if(x)x.remove()},1500)}return}
  if(!b){b=document.createElement('div');b.id='connb';b.style.cssText='position:fixed;top:0;left:0;right:0;z-index:9999;background:#5a1d1d;color:#fff;font-size:13px;padding:6px 10px;text-align:center';document.body.appendChild(b)}
  const t=S._lastOk?new Date(S._lastOk).toTimeString().slice(0,5):'—';b.textContent=`⚠ 連不到電腦，自動重試中…（上次連上 ${t}；看一下 Tailscale、電腦開著嗎）`}catch(e){}}
function roBadge(on){S.ro=on;if(!on||$('#robadge'))return;const b=document.createElement('div');b.id='robadge';b.textContent='👀 唯讀';b.style.cssText='position:fixed;right:8px;bottom:64px;z-index:9998;background:#3a3150;color:#fff;font-size:12px;padding:3px 8px;border-radius:10px;opacity:.85';document.body.appendChild(b)}   // V0.4.30 👀
async function poll(){
  if(document.hidden)return;
  let s;try{s=await api('/api/state',undefined,{quiet:true})}catch(e){connBar(false);return}
  if(!s.ok)return;connBar(true);try{if(s.brk&&s.brk.id&&LS.get('brkSaid',0)!==s.brk.id){LS.set('brkSaid',s.brk.id);toast(`👀 已經連續分級 ${s.brk.mins} 分鐘（${s.brk.n} 部）了，休息一下吧`,15000);try{if(document.hidden&&Notification.permission==='granted')new Notification('SortCut',{body:'👀 連續分級 '+s.brk.mins+' 分鐘了，休息一下吧'})}catch(e){}}}catch(e){}try{const a=S.state&&S.state.sprint,b=s.sprint;if(a&&a.on&&b&&!b.on)toast(`🏁 衝刺結束：${b.min} 分鐘分了 ${b.n} 部（每分鐘 ${b.rate}）${b.new_best?'　🏆 新紀錄！':''}`,12000)}catch(e){}try{notifyDiff(S.state,s)}catch(e){}S.state=s;try{document.body.classList.toggle('bnav',!!(s.lab&&s.lab.bottom_nav))}catch(e){}try{goalBar();upGoalBar();S._sprAt=Date.now();sprBar();const lg=JSON.stringify(s.lab||{});if(lg!==S._labSig){const first=S._labSig===undefined;S._labSig=lg;{const b=$('#qsyn');if(b)b.style.display=labOn('smart_search')?'':'none';const r=$('#qrnd');if(r)r.style.display=labOn('random_pick')?'':'none'}if($('#chips')&&(!first||S.lastChips!==undefined))chips(S.lastChips)}}catch(e){}const c=$('#clk');if(c)c.textContent=s.time||'';
  if(s.ver&&s.ver!==VER){toast('電腦更新到 V'+s.ver+'，重新載入…');setTimeout(()=>location.reload(),1200);return}
  const w=$('#sysPop');if(w&&w.dataset.t==='bg')bgRender($('.sysPopB',w));if(w&&w.dataset.t==='ed')edRender($('.sysPopB',w));
  edbPaint();if(S.tab==='tools'&&$('#tbgS')){tbgPaint();cardLive()}
}

/* ================= 📊 效能／🖥 背景／✂ 轉檔／🗂 分類（浮動視窗；點旁邊回到原本的頁面，原本在看的不會停） ================= */
const SYSPOP_T={pf:'📊 電腦效能',bg:'🖥 後台狀態',ed:'✂ 轉檔（初剪／轉檔）',lv:'🗂 分類（分級）'};
function sysFabInit(){if($('#sysFab'))return;const b=document.createElement('div');b.id='sysFab';
  b.innerHTML='<button type="button" data-t="pf">📊 效能</button><button type="button" data-t="bg">🖥 背景</button><button type="button" data-t="ed">✂ 轉檔<em class="n" hidden></em><em class="r" hidden></em></button><button type="button" data-t="lv">🗂 分類</button>';
  b.onclick=e=>{const x=e.target.closest('[data-t]');if(!x)return;e.stopPropagation();const w=$('#sysPop');if(!w)sysPopOpen(x.dataset.t);else if(w.dataset.t===x.dataset.t)w._close();else w._tab(x.dataset.t)};
  document.body.appendChild(b)}
function edbCount(){const s=S.state;if(!s)return null;const J=s.jobs||{};const done=(J.cuts||[]).filter(c=>c.state==='done').length;const run=(J.cut_active||0)+(J.conv||[]).length;return {done,run}}
function edbPaint(){const c=edbCount(),b=$('#sysFab [data-t="ed"]');if(!c||!b)return;let seen=+LS.get('edb_seen',-1);if(seen<0||seen>c.done){seen=c.done;LS.set('edb_seen',seen)}
  const n=Math.max(0,c.done-seen),N=$('.n',b),R=$('.r',b);N.hidden=!n;N.textContent='+'+n;R.hidden=!c.run;R.textContent=c.run}
function sysPopOpen(t0){if($('#sysPop'))return;const w=document.createElement('div');w.id='sysPop';
  w.innerHTML=`<div class="sysPopW"><div class="sysPopH"><b class="sysPopTt"></b><span class="sysPopN">點旁邊回到原本的頁面</span><button type="button" class="sysPopX" title="關閉">✕</button></div><div class="sysPopB"><div class="empty">讀取中…</div></div><div class="sysPopR" title="上下拖：調整視窗高度（點兩下恢復 50%）"><i></i></div></div>`;
  document.body.appendChild(w);const W=$('.sysPopW',w),body=$('.sysPopB',w);
  const setH=f=>{f=Math.max(.25,Math.min(.9,+f||.5));W.style.height=(f*100)+'%';return f};let hf=setH(LS.get('syspop_h',.5));
  const gr=$('.sysPopR',w);let dg=null;
  gr.onpointerdown=e=>{gr.setPointerCapture(e.pointerId);dg={y:e.clientY,h:W.getBoundingClientRect().height};gr.classList.add('on');e.preventDefault();e.stopPropagation()};
  gr.onpointermove=e=>{if(!dg)return;hf=setH((dg.h+e.clientY-dg.y)/w.getBoundingClientRect().height)};
  gr.onpointerup=gr.onpointercancel=()=>{if(!dg)return;dg=null;gr.classList.remove('on');LS.set('syspop_h',+hf.toFixed(3))};gr.ondblclick=()=>{hf=setH(.5);LS.set('syspop_h',.5)};
  let iv=null;const tick=()=>{if(!w.isConnected){clearInterval(iv);return}if(document.hidden)return;const t=w.dataset.t;if(t==='pf')pfLoad(body);else if(t==='lv')lvLoad(body)};
  const tab=t=>{w.dataset.t=t;$('.sysPopTt',w).textContent=SYSPOP_T[t]||'';$$('#sysFab [data-t]').forEach(b=>b.classList.toggle('on',b.dataset.t===t));body.innerHTML='<div class="empty">讀取中…</div>';body._ok=0;body._t=0;body.onclick=null;
    if(t==='bg')bgRender(body);if(t==='ed'){edRender(body);LS.set('edb_seen',(edbCount()||{}).done||0);edbPaint()}tick()};
  w._tab=tab;tab(SYSPOP_T[t0]?t0:'pf');iv=setInterval(tick,2000);
  const close=layer(w,()=>{clearInterval(iv);$$('#sysFab [data-t]').forEach(b=>b.classList.remove('on'))});
  w.addEventListener('click',e=>{if(e.target===w)close()});$('.sysPopX',w).onclick=()=>close()}
function spark(H,color){const v=(H||[]).map(x=>x==null?null:+x);if(!v.length)return '';const n=v.length;let d='',pen=false;v.forEach((y,i)=>{if(y==null){pen=false;return}const X=(i/(Math.max(1,n-1))*100).toFixed(2),Y=(33-Math.min(100,Math.max(0,y))*0.32).toFixed(2);d+=(pen?' L':' M')+X+' '+Y;pen=true});
  return `<svg viewBox="0 0 100 34" preserveAspectRatio="none"><path d="${d.trim()}" fill="none" stroke="${color}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`}
async function pfLoad(body){let P;try{P=await api('/api/perf',undefined,{quiet:true})}catch(e){if(!body._ok)body.innerHTML='<div class="empty">連不到電腦或資料讀取失敗</div>';return}if(!body.isConnected||!P.ok||$('#sysPop').dataset.t!=='pf')return;body._ok=1;
  const g=P.gpu||{},H=P.hist||{};const card=(t,v,u,h,c,sub)=>`<div class="pfC"><small>${t}</small><b>${v==null||isNaN(v)?'—':v}<small>${u||''}</small></b>${sub?`<small>${sub}</small>`:''}${spark(h,c)}</div>`;
  const st=body.scrollTop;body.innerHTML=`<div class="mu" style="margin-bottom:6px">${esc(P.time)} · 每 2 秒更新　做中：預覽圖 ${P.jobs.th} · 轉檔 ${P.jobs.cv} · 初剪 ${P.jobs.cut}</div><div class="pfG">
   ${card('CPU',P.cpu==null?null:Math.round(P.cpu),'%',H.cpu,'#4dc9ff')}${card('記憶體',P.ram==null?null:Math.round(P.ram),'%',H.ram,'#9b6dff',P.ram_total?fmtB(P.ram_used)+'／'+fmtB(P.ram_total):'')}
   ${g.name?card('顯示卡',Math.round(g.util),'%',H.gpu,'#45d483',esc(g.name)+(g.temp!=null?' · '+Math.round(g.temp)+'°C':'')):''}
   ${g.name?card('壓縮 NVENC',Math.round(g.enc),'%',H.enc,'#f0ad4e'):''}${g.name?card('解碼',Math.round(g.dec),'%',H.dec,'#ff5c8a'):''}
   ${g.name?card('顯示記憶體',g.mem_t?Math.round(g.mem*100/g.mem_t):null,'%',H.vram,'#43d9ff',g.mem_t?Math.round(g.mem)+'／'+Math.round(g.mem_t)+' MB':''):''}</div>
   <div class="edjH">💽 硬碟</div>${(P.disks||[]).map(d=>{const pu=d.total?Math.round((d.total-d.free)*100/d.total):null;return `<div class="edjI"><div class="edjT"><b>${esc(d.label)}</b><span class="mu">${esc(d.media||'')}${d.busy!=null?' · 忙碌 '+Math.round(d.busy)+'%':''} · 預覽圖 ${d.th||0} · 轉檔 ${d.cv||0}</span></div>
   ${pu!=null?`<div class="pg" style="margin:5px 0"><i style="width:${pu}%;background:${pu>=90?'var(--red)':pu>=75?'var(--orange)':'var(--vline)'}"></i></div><small>已用 ${pu}% · 剩 ${fmtB(d.free)}／${fmtB(d.total)}${d.eta?' · 預覽圖還要 '+eta(d.eta):''}</small>`:''}${d.note?`<small>${esc(d.note)}</small>`:''}</div>`}).join('')||'<div class="mu">—</div>'}`;body.scrollTop=st}
const BGST={run:['▶ 進行中','var(--green)'],wait:['⏳ 排隊中','var(--orange)'],pause:['⏸ 暫停中','var(--red)'],idle:['— 沒事','var(--sub)'],err:['✖ 出錯','var(--red)']};
function ovHTML(L,all){return (L||[]).filter(o=>all||o.state!=='idle').map(o=>{const [nm,col]=BGST[o.state]||[o.state,'var(--sub)'];const bits=[];if(o.left!=null)bits.push('剩 '+(+o.left).toLocaleString()+' 個');if(o.speed)bits.push(esc(o.speed));if(o.eta)bits.push('還要 '+eta(o.eta));
  return `<div class="edjI ${o.state==='run'?'run':o.state==='err'?'bad':''}"><div class="edjT"><b>${o.icon} ${esc(o.name)}</b><span style="color:${col};font-weight:800;font-size:12px">${nm}</span><span class="mu" style="margin-left:auto">${bits.join(' · ')}</span></div>
   ${(o.items||[]).map(x=>`<small style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">⚙ ${esc(x.name||'')}${x.sub?' · '+esc(x.sub):''}</small>${x.pct!=null?`<div class="pg" style="margin:3px 0"><i style="width:${x.pct||0}%"></i></div>`:''}`).join('')}${o.note?`<small>${esc(o.note)}</small>`:''}</div>`}).join('')}
const CST={run:['▶ 進行中','var(--green)'],idle:['— 沒事','var(--sub)'],pause:['⏸ 暫停中','var(--red)'],hold:['⚖ 讓路中','var(--orange)']};
function ctlHTML(c){const M=c.mf||{};return `<div class="edjH">⏯ 總控制（CPU ${c.cpu}%${c.guard?` · 超過 ${c.cpu_max}% 自動讓路`:' · 自動讓路關'}）</div>${M.active?`<div style="border:1px solid #f0ad4e;border-radius:10px;padding:6px 10px;margin:6px 0;color:#f0c27a">🛟 <b>主程式優先中</b>（${esc(M.why||'')}）：背景先退開，順了 ${M.left} 秒後慢慢放回來</div>`:''}
  ${c.kinds.map(k=>{const [nm,col]=CST[k.state]||[k.state,'var(--sub)'];return `<div class="edjI ${k.state==='run'?'run':''}"><div class="edjT"><b>${k.prio}. ${k.icon} ${esc(k.name)}</b><span style="color:${col};font-weight:800;font-size:12px">${nm}</span>
   <span class="mu" style="margin-left:auto">${k.pct!=null?k.pct+'%（'+(+k.done).toLocaleString()+'／'+(+k.total).toLocaleString()+'）':''}</span></div>
   ${k.pct!=null?`<div class="pg" style="margin:3px 0"><i style="width:${k.pct}%"></i></div>`:''}${k.last?`<small>${k.state==='pause'?'⏸ 停在':'最近'}：${esc(k.last)}</small>`:''}${k.held?`<small style="color:var(--orange)">${esc(k.held)}</small>`:''}${k.ramp?`<small>慢慢加速中：現在最多同時 ${k.ramp} 個</small>`:''}${k.slow?`<small style="color:var(--orange)">電腦很忙：降速成同時最多 ${k.slow} 個</small>`:''}
   <div class="row" style="margin-top:5px;gap:6px">${k.state==='pause'?`<button class="pill ok" data-bc="resume" data-k="${k.k}">▶ 繼續</button>`:`<button class="pill wa" data-bc="pause" data-k="${k.k}">⏸ 暫停</button>`}${k.running&&k.k!=='hotzone'?`<button class="pill er" data-bc="stop" data-k="${k.k}">⏹ 立刻停</button>`:''}
   <button class="pill" data-bc="up" data-k="${k.k}">↑</button><button class="pill" data-bc="down" data-k="${k.k}">↓</button></div></div>`}).join('')}
  <div class="row" style="margin:6px 0;gap:6px"><button class="pill" data-bc="all_pause">⏸ 全部暫停</button><button class="pill" data-bc="all_resume">▶ 全部繼續（照順序慢慢加）</button><button class="pill" data-bc="pack_now">💾 現在寫到各硬碟</button><button class="pill" data-bc="guard" data-on="${c.guard?0:1}">${c.guard?'自動讓路：開':'自動讓路：關'}</button></div>
  ${c.log&&c.log.length?`<small class="mu">${c.log.slice(0,5).map(esc).join('<br>')}</small>`:''}`}
async function bcClick(e){const b=e.target.closest('[data-bc]');if(!b)return false;e.stopPropagation();const a=b.dataset.bc;if(a==='stop'&&!confirm('立刻停：正在做的也停掉，放回排隊（下次從頭做那一部）？'))return true;
  const body={a,k:b.dataset.k};if(a==='guard')body.on=b.dataset.on==='1';const j=await api('/api/bgctl',body);if(j.ok)toast(j.message||'好了',j.message?6000:undefined);const bd=document.querySelector('#sysPop .sysPopB');if(bd){bd._t=0;bgRender(bd)}return true}
document.addEventListener('click',e=>{if(e.target.closest('[data-bc]'))bcClick(e)},true);
document.addEventListener('click',async e=>{const b=e.target.closest('[data-share]');if(!b)return;e.stopPropagation();   // V0.3.29 兩台電腦同步新功能設定
  if(b.dataset.share==='x'){const j=await api('/api/new',{a:'share_export'});return toast(j.message||'',5000)}
  const j=await api(U('/api/new',{a:'share_list'}));const L=(j.rows||[]).filter(x=>!x.mine);if(!L.length)return toast('硬碟上沒有另一台存的設定（另一台先按「🔄 設定存到硬碟」）',5000);
  menu('📥 套用哪一份？',L.map(x=>[`${x.d}:　${x.pc_name}　${new Date(x.t*1000).toLocaleString()}　打開 ${x.n_on} 個`,async()=>{if(!confirm('套用這份設定？（這台的上傳資料夾、讓路程式不會被蓋掉）'))return;const r=await api('/api/new',{a:'share_import',d:x.d});toast(r.message||'');try{SETD=await api('/api/settings');setCat('lab')}catch(e){}}]))},true);
document.addEventListener('click',async e=>{const b=e.target.closest('[data-pack]');if(!b)return;e.stopPropagation();if(!confirm('一次打開「'+b.dataset.pack+'」？（之後可以一個一個關）'))return;const j=await api('/api/new',{a:'pack_on',name:b.dataset.pack});toast(j.message||'');if(j.ok){try{SETD=await api('/api/settings');setCat('lab')}catch(x){}}},true);   // V0.2.93
document.addEventListener('click',async e=>{const b=e.target.closest('[data-cp]');if(!b)return;e.stopPropagation();if(b.dataset.cp==='clear'&&!confirm('清掉還沒開始的排隊？'))return;const j=await api('/api/new',{a:'copy_ctl',do:b.dataset.cp});toast(j.message||'');if(j.ok&&S.state)S.state.copy=j.copy},true);   // V0.2.76
function fcRow(f){if(!f)return '';const t=[f.run.length?'▶ '+f.run.join('、'):'',f.pause.length?'⏸ 暫停：'+f.pause.join('、'):'',f.auto.length?'⚖ 電腦忙讓路：'+f.auto.join('、'):'',f.hold?'🤝 '+f.hold:''].filter(Boolean);   // V0.5.10 整理（FileCompare）的背景也在這裡看
  return `<a class="edjI" href="/fc/?go=tool:bg" style="display:block;text-decoration:none;color:inherit"><div class="edjT"><b>🗂 整理（FileCompare）</b><span style="margin-left:auto">看詳細 ›</span></div><small>${t.length?t.map(esc).join('<br>'):'現在沒有背景工作 ✔'}</small></a>`}
async function bgRender(body){const s=S.state;if(!body)return;if(body._busy)return;if(body._t&&Date.now()-body._t<1800)return;body._busy=1;let d;try{d=await api('/api/bg',undefined,{quiet:true})}catch(e){body._busy=0;return}body._busy=0;body._t=Date.now();
  if(!body.isConnected||!d.ok||($('#sysPop')&&$('#sysPop').dataset.t!=='bg'))return;const paused=d.th_paused&&d.cv_paused;const st=body.scrollTop;
  body.innerHTML=`${fcRow(d.fc)}${s&&s.still_left!=null?`<div class="edjI"><div class="edjT"><b>😴 背景算靜止比例</b></div><small>${s.still_left?'還有 '+s.still_left.toLocaleString()+' 部要算（一次一部，慢慢來）':'全部算好了'}</small></div>`:''}${s&&s.auto_scan?`<div class="edjI"><div class="edjT"><b>👀 自動找新影片</b></div><small>${s.auto_scan.run?'掃描中…':'上次 '+(s.auto_scan.last_t?new Date(s.auto_scan.last_t*1000).toLocaleTimeString():'還沒跑過')+(s.auto_scan.last_t?'・多了 '+(s.auto_scan.last_new||0)+' 部':'')}</small></div>`:''}${s&&s.copy&&(s.copy.run||s.copy.q)?`<div class="edjI"><div class="edjT"><b>📤 複製到上傳資料夾</b></div><small>${esc(s.copy.cur||'')} ${s.copy.pct||0}%・還有 ${s.copy.q} 部・${fmtB(s.copy.speed||0)}/s・好了 ${s.copy.done}${s.copy.fail?'・失敗 '+s.copy.fail:''}<br>→ ${esc(s.copy.dir)}</small><div class="row" style="margin-top:4px"><button class="pill" data-cp="${s.copy.paused?'resume':'pause'}">${s.copy.paused?'▶ 繼續':'⏸ 暫停'}</button><button class="pill er" data-cp="clear">🗑 清空排隊</button></div></div>`:''}${s&&s.disk_warn&&s.disk_warn.length?`<div class="edjI bad"><div class="edjT"><b>⚠ 硬碟空間不足</b></div><small>${s.disk_warn.map(x=>esc(x.d)+(x.label?'（'+esc(x.label)+'）':'')+' 只剩 '+fmtB(x.free)+(x.days_full!=null?'，約 '+x.days_full+' 天滿':'')).join('、')}</small></div>`:''}${s&&s.offline&&s.offline.length?`<div class="edjI bad"><div class="edjT"><b>⚠ 硬碟離線</b></div><small>${s.offline.map(esc).join('、')}：這顆的工作先暫停，接回來會自動繼續</small></div>`:''}
  ${s&&s.db&&s.db.ok===false?`<div class="edjI bad"><div class="edjT"><b>⚠ 資料庫有問題</b></div><small>${esc(s.db.msg)}</small></div>`:''}
  <div class="row" style="margin-bottom:8px"><button class="pill ${paused?'ok':'wa'}" onclick="ctl('${paused?'resume_all':'pause_all'}')">${paused?'▶ 全部繼續':'⏸ 全部暫停'}</button>
   <button class="pill" onclick="ctl('${d.th_paused?'resume_th':'pause_th'}')">${d.th_paused?'▶ 預覽圖繼續':'⏸ 預覽圖暫停'}</button><button class="pill" onclick="ctl('${d.cv_paused?'resume_cv':'pause_cv'}')">${d.cv_paused?'▶ 轉檔繼續':'⏸ 轉檔暫停'}</button>
   <button class="pill" onclick="ctl('scan')">🔄 掃描</button><button class="pill" onclick="ctl('retry_failed')">↻ 失敗重做</button><button class="pill" onclick="ctl('cover')">🏠 電腦切到封面</button></div>
  ${d.ctl?ctlHTML(d.ctl):''}
  <div class="edjH">正在跑的（${d.time}）</div>${ovHTML(d.items,false)||'<div class="empty">現在沒有背景工作 ✔</div>'}
  <div class="edjH">全部項目</div>${ovHTML((d.items||[]).filter(o=>o.state==='idle'),true)}`;body.scrollTop=st}
function edRender(body){const s=S.state;if(!s||!body)return;const J=s.jobs||{};const SN={wait:'排隊中',run:'剪輯中',done:'初剪好了',fail:'失敗'};
  const st=body.scrollTop;let h=`<div class="edjH">🔁 轉檔（${(J.conv||[]).length} 個在轉 · 排隊 ${J.cv_wait||0}）</div>`;
  h+=(J.conv||[]).map(c=>`<div class="edjI run"><div class="edjT"><b>${esc(c.name)}</b><em>${c.pct||0}%</em><span>${esc(c.speed||'')}</span><button class="pill er" style="margin-left:auto" data-cvx="${c.id}">取消</button></div><div class="pg" style="margin:4px 0"><i style="width:${c.pct||0}%"></i></div></div>`).join('');
  h+=`<div class="row" style="margin-bottom:4px"><button class="pill" data-cvp>${s.cv_paused?'▶ 轉檔繼續':'⏸ 轉檔暫停'}</button>${J.cv_wait?'<button class="pill er" data-cvall>取消全部排隊</button>':''}</div>`;
  h+=`<div class="edjH">✂ 初剪（最近 ${(J.cuts||[]).length} 個）· 點一筆打開那部影片</div>`;
  h+=(J.cuts||[]).length?J.cuts.map(c=>`<div class="edjI ${c.state==='run'?'run':c.state==='done'?'ok':c.state==='fail'?'bad':''}" data-fid="${c.fid}"><div class="edjT"><b>${esc(c.name)}</b><em>${SN[c.state]||esc(c.state)}</em><span>${c.nseg} 段 · ${fmtT(c.secs)} · ${c.merge?'合併':'分段'}${c.state==='run'&&c.pct!=null?' · '+Math.round(c.pct)+'%':''}${c.gone?' · 原檔已刪':''}</span>
   ${c.state==='done'&&!c.gone?`<button class="pill er" style="margin-left:auto" data-del="${c.fid}">刪原檔</button>`:''}</div>${c.err?`<small style="color:var(--red)">${esc(c.err)}</small>`:''}${(c.outs||[]).map(o=>`<small>→ ${esc(String(o).split(/[\\/]/).pop())}</small>`).join('')}</div>`).join(''):'<div class="empty">還沒有初剪</div>';
  body.innerHTML=h;body.scrollTop=st;
  body.onclick=async e=>{const d=e.target.closest('[data-del]');if(d){e.stopPropagation();if(!confirm('刪除這部的原檔？（丟到資源回收筒；初剪檔留著）'))return;const j=await api('/api/op',{kind:'delete_original',ids:[+d.dataset.del]});toast(j.message||'');return}
    const x=e.target.closest('[data-cvx]');if(x){const j=await api('/api/op',{kind:'conv_cancel',ids:[+x.dataset.cvx]});toast(j.message||'');return}
    if(e.target.closest('[data-cvp]')){ctl(S.state.cv_paused?'resume_cv':'pause_cv');return}
    if(e.target.closest('[data-cvall]')){if(confirm('取消全部排隊中的轉檔？'))ctl('conv_cancel_all');return}
    const it=e.target.closest('.edjI[data-fid]');if(!it)return;const w=$('#sysPop');if(w&&w._close)await w._close();openFile(+it.dataset.fid)}}
const LVC={S:'#ffc94d',A:'#45d483',E:'#4dc9ff',F:'#ff4d6d','':'#5b6676'};
async function lvLoad(body){if(body._busy)return;if(body._t&&Date.now()-body._t<15000)return;body._busy=1;let d;try{d=await api('/api/grades',undefined,{quiet:true})}catch(e){body._busy=0;return}body._busy=0;body._t=Date.now();if(!body.isConnected||!d.ok||$('#sysPop').dataset.t!=='lv')return;
  const T=d.tot||1,P=b=>Math.round(b*1000/T)/10;const K=['S','A','E','F',''];const done=(d.tot||0)-(d.g[''].b||0);
  body.innerHTML=`<div class="row" style="justify-content:space-around;margin-bottom:6px"><div style="text-align:center"><div class="mu">待整理</div><b style="font-size:20px">${fmtB(d.tot)}</b><div class="mu">${d.n.toLocaleString()} 部</div></div>
   <div style="text-align:center"><div class="mu">已分級</div><b style="font-size:20px">${P(done)}%</b></div><div style="text-align:center"><div class="mu">未分級</div><b style="font-size:20px">${P(d.g[''].b)}%</b><div class="mu">${d.g[''].n.toLocaleString()} 部</div></div></div>
   <div class="lvsBar">${K.map(k=>P(d.g[k].b)?`<i style="width:${P(d.g[k].b)}%;background:${LVC[k]}"></i>`:'').join('')}</div>
   ${K.map(k=>`<button class="lvsC" data-g="${k}" style="--c:${LVC[k]}"><b>${k||'—'}</b><span>${GN[k]}</span><em>${P(d.g[k].b)}%</em><small>${d.g[k].n.toLocaleString()} 部 · ${fmtB(d.g[k].b)}</small></button>`).join('')}
   ${(d.arch||[]).length?`<div class="edjH">📦 已歸檔</div>`+d.arch.map(a=>`<div class="edjI"><div class="edjT"><b>${esc(a.name)}</b><span>${a.n.toLocaleString()} 部 · ${fmtB(a.b)}</span></div></div>`).join(''):''}
   <div class="mu" style="margin-top:6px">點一格＝檔案總管只看那個分級（％ 是占容量的比例）</div>`;
  body.onclick=async e=>{const b=e.target.closest('.lvsC');if(!b)return;const g=b.dataset.g;S.flt=g?g:'nograde';saveView();await closeAll();if(location.hash==='#fx'||!location.hash)viewFx();else location.hash='fx'}}
async function ctl(a){const j=await api('/api/control',{a});if(j.message)toast(j.message);setTimeout(poll,400)}

// ---------------------------------------------------------------- 檔案總管
const FLT=[['all','全部'],['ready','✅ 可以審'],['thumbok','預覽圖好了'],['nograde','未分級'],['S','S'],['A','A'],['E','E'],['F','F'],['unseen','沒看過'],['fav','★收藏'],['cut','有初剪'],['tagany','有標籤'],['noted','有備註'],['nothumb','預覽圖還沒好'],['archived','已歸檔']];
const SORTS=[['name','檔名'],['size','大→小'],['size_asc','小→大'],['dur','長→短'],['dur_asc','短→長'],['mtime','最新'],['added','最近加入'],['grade','分級'],['viewed','看過的在前'],['still','😴 靜止多→少'],['up_t','📤 最近上傳']];
const COLS=['auto','1','2','3','4','5','6'];
function colsN(){const W=Math.min(window.innerWidth,1400)-20;return S.cols==='auto'?(W<640?2:W<900?3:W<1200?4:5):+S.cols}
function needPeople(){if(S.people)return Promise.resolve(S.people);return api('/api/people',undefined,{quiet:true}).then(j=>{S.people=(j.people||[]).filter(p=>p.name);return S.people}).catch(()=>[])}
function viewFx(){
  const PCW=isPC();
  V().innerHTML=(PCW?'<div class="fxw"><aside id="ftree"></aside><div id="fxm">':'')+`<div class="tools"><button class="pill" id="fbtn" style="max-width:34vw;overflow:hidden;text-overflow:ellipsis;height:40px">📁 <span id="fname"></span></button><input class="search" id="q" placeholder="${labOn('smart_search')?'🔍 檔名 或 >10m g:S 沒上傳 -字':'🔍 搜尋檔名'}" value="${esc(S.q)}" enterkeyhint="search"><span id="pinr" class="pinin"></span><button class="pill" id="findb" style="height:40px">⚙ 篩選</button><button class="pill" id="smode" style="height:40px">☑ 多選</button></div><div id="goalb"></div><div id="upgb"></div><div id="sprb"></div><div class="chips" id="chips"></div><div class="chips" id="durc"></div><div class="chips" id="resc"></div><div class="hidn" id="hidn"></div><div class="grid" id="grid"></div><div id="more"></div>`+(PCW?'</div></div>':'');
  if(PCW)pickFolder($('#ftree'));
  $('#fname').textContent=S.folder?S.folder.split(/[\\/]/).filter(Boolean).pop():'全部影片';
  $('#fbtn').onclick=pickFolder;$('#findb').onclick=findPanel;$('#smode').onclick=()=>setSel(!S.selMode);
  try{pinRow()}catch(e){}
  let qt;$('#q').oninput=e=>{clearTimeout(qt);qt=setTimeout(()=>{S.q=e.target.value.trim();saveView();loadList(true)},400)};
  {const q=$('#q');q.insertAdjacentHTML('afterend',`<button class="pill" id="qrnd" title="隨便抽一部還沒分級的" style="${labOn('random_pick')?'':'display:none'}">🎲</button>`);   // V0.3.84 🎲
   $('#qrnd').onclick=async()=>{const j=await api(U('/api/new',{a:'random',folder:S.folder||''}));if(!j.ok)return;if(!(j.ids||[]).length)return toast('🎲 這裡沒有還沒分級的了 🎉');toast('🎲 隨便抽了一部',1200);openFile(j.ids[0])}}
  {const q=$('#q');q.insertAdjacentHTML('afterend',`<button class="pill" id="qsyn" title="搜尋語法" style="${labOn('smart_search')?'':'display:none'}">🔎＋</button>`);   // V0.3.82 點一下加條件
    const TK=[['g:S','只要 S'],['g:SA','S 和 A'],['g:none','還沒分級'],['沒上傳','還沒上傳'],['已上傳','已經上傳'],['★','收藏'],['沒看過','沒看過'],['>10m','長度超過 10 分'],['<1m','短於 1 分'],['>2gb','大於 2 GB'],['4k','4K'],['1080p','1080p'],['hevc','HEVC 編碼'],['note:','備註有…（後面打字）'],['-','檔名不要有…（後面打字）']];
    $('#qsyn').onclick=()=>menu('🔎 加一個搜尋條件',TK.map(([t,n])=>[`${t}　${n}`,()=>{const v=q.value.trim();q.value=(v?v+' ':'')+t;if(t.endsWith(':')||t==='-'){q.focus();return}S.q=q.value.trim();saveView();loadList(true)}]).concat([['✕ 清掉搜尋',()=>{q.value='';S.q='';saveView();loadList(true)}]]))}
  if(S.state&&S.state.lab&&S.state.lab.search_hist){const q=$('#q');q.setAttribute('list','qhist');q.insertAdjacentHTML('afterend','<datalist id="qhist"></datalist>');   // V0.2.65 🔎 搜尋紀錄
    const fill=R=>{const d=$('#qhist');if(d)d.innerHTML=(R||[]).map(x=>`<option value="${esc(x)}">`).join('')};api(U('/api/new',{a:'shist'}),undefined,{quiet:true}).then(j=>fill(j.rows)).catch(()=>{});
    q.addEventListener('change',()=>{const v=q.value.trim();if(v.length>1)api('/api/new',{a:'shist_push',q:v},{quiet:true}).then(j=>fill(j.rows)).catch(()=>{})})}
  if($('#seg'))$('#seg').onclick=e=>{const b=e.target.closest('button');if(!b)return;S.cols=b.dataset.c;LS.set('cols',S.cols);applyCols()};
  if(S.flt.startsWith('person:'))needPeople().then(()=>$('#chips')&&S.lastChips&&chips(S.lastChips));
  applyCols();loadList(true);
  const io=new IntersectionObserver(es=>{if(es[0].isIntersecting&&!S.loading&&S.rows.length<S.total)loadList(false)},{rootMargin:'600px'});io.observe($('#more'));
  pinch($('#grid'),d=>{S.cols=String(Math.max(1,Math.min(20,colsN()+d)));LS.set('cols',S.cols);applyCols();toast('一列 '+S.cols+' 張',900)});   // V0.5.84 兩指縮放：1～20 張
  $('#grid').addEventListener('wheel',e=>{if(!e.ctrlKey)return;e.preventDefault();S.cols=String(Math.max(1,Math.min(20,colsN()+(e.deltaY>0?1:-1))));LS.set('cols',S.cols);applyCols()},{passive:false});   // 電腦：Ctrl＋滾輪
}
function applyCols(){const g=$('#grid');if(!g)return;const n=colsN();g.style.setProperty('--cols',n);g.classList.toggle('dense',n>=4);g.classList.toggle('tiny',n>=10);g.classList.toggle('one',n===1);$$('#seg button').forEach(b=>b.classList.toggle('on',b.dataset.c===String(S.cols)))}
window.addEventListener('resize',()=>{if(S.tab==='fx'&&S.cols==='auto')applyCols()});
async function findPanel(){
  await needPeople();const PS=S.people||[];
  const d=document.createElement('div');d.className='sheet';
  d.innerHTML=`<div><div class="row"><h3 class="grow" style="margin:0">⚙ 篩選與排序</h3><button class="pill" data-x>✕</button></div>
   <div class="fr"><b>排序</b><div class="seg" id="fs">${SORTS.map(x=>`<button data-v="${x[0]}"${x[0]===S.sort?' class="on"':''}>${x[1]}</button>`).join('')}</div></div>
   <div class="fr"><b>顯示</b><select id="ff" class="grow">${FLT.map(x=>`<option value="${x[0]}"${x[0]===S.flt?' selected':''}>${x[1]}</option>`).join('')}${labOn('bookmarks')?`<option value="bmk"${S.flt==='bmk'?' selected':''}>🔖 有書籤</option>`:''}${labOn('still_scan')?`<option value="still"${S.flt==='still'?' selected':''}>😴 大多是靜止的</option>`:''}${labOn('copy_to')?`<option value="uped"${S.flt==='uped'?' selected':''}>📤 已經複製到上傳</option><option value="notup"${S.flt==='notup'?' selected':''}>📤 S／A 還沒上傳</option>`:''}<option value="notpub"${S.flt==='notpub'?' selected':''}>✅ 複製了、還沒發佈</option><option value="pub"${S.flt==='pub'?' selected':''}>✅ 已發佈</option><option value="bad"${S.flt==='bad'?' selected':''}>⚠ 讀不了／可能壞掉</option><option value="novideo"${S.flt==='novideo'?' selected':''}>🔇 只有聲音</option>${Object.entries(TAGS).map(([k,v])=>`<option value="tag:${k}"${S.flt==='tag:'+k?' selected':''}>${v} 標籤</option>`).join('')}
     ${PS.map(p=>`<option value="person:${p.id}"${S.flt==='person:'+p.id?' selected':''}>👤 ${esc(p.name)}（${p.n_files}）</option>`).join('')}${(S.hidden||[]).map(h=>`<option value="ext:${h[0]}"${S.flt==='ext:'+h[0]?' selected':''}>🚫 ${h[0].slice(1)}（${h[1]} 部，沒列出來的）</option>`).join('')}</select></div>
   <div class="fr"><b>子資料夾</b><label class="tg"><input type="checkbox" id="fsub" ${S.sub?'checked':''}><i></i></label><span class="mu">包含底下所有資料夾</span></div>
   <div class="mu">🧪 開了「進階搜尋語法」搜尋框還可以打：&gt;1h　&lt;10m　&gt;2gb　4k　1080p　hevc　ext:avi</div>
   <div class="row" style="margin-top:12px"><button class="pill" id="freset">清除篩選</button><span class="grow"></span><button class="pill acc" id="fok">套用</button></div></div>`;
  document.body.appendChild(d);const close=layer(d);let sort=S.sort;
  $('#fs',d).onclick=e=>{const b=e.target.closest('button');if(!b)return;sort=b.dataset.v;$$('#fs button',d).forEach(x=>x.classList.toggle('on',x===b))};
  $('#fok',d).onclick=()=>{S.sort=sort;S.flt=$('#ff',d).value;S.sub=$('#fsub',d).checked;saveView();close().then(()=>loadList(true))};
  $('#freset',d).onclick=()=>{S.q='';S.sort='name';S.flt='all';S.sub=true;saveView();const q=$('#q');if(q)q.value='';close().then(()=>loadList(true))};
  d.addEventListener('click',e=>{if(e.target===d||e.target.closest('[data-x]'))close()})}
function fltName(k){if(k.startsWith('tag:'))return TAGS[k.slice(4)]+' 標籤';if(k.startsWith('person:'))return '👤 '+((S.people||[]).find(p=>'person:'+p.id===k)||{name:'人物'}).name;if(k.startsWith('ext:'))return '🚫 '+k.slice(5);if(k.startsWith('month:'))return '📅 '+k.slice(6);if(k==='bmk')return '🔖 有書籤';if(k==='still')return '😴 大多是靜止的';if(k==='uped')return '📤 已上傳';if(k==='notup')return '📤 S／A 還沒上傳';if(k==='bad')return '⚠ 讀不了／可能壞掉';if(k==='notpub')return '✅ 複製了、還沒發佈';if(k==='pub')return '✅ 已發佈';if(k==='novideo')return '🔇 只有聲音';return k}
async function purgeTrash(){const r=await api(U('/api/lib',{a:'trash'}));if(!r.ok)return toast(r.message||'讀不到');if(!r.n)return toast('待刪資料夾是空的'+(r.skip?`（${r.skip} 個是初剪或正在用，保留）`:''));
  const by=Object.entries(r.by||{}).map(([k,v])=>`　${k} ${v[0]} 個・${fmtB(v[1])}`).join('\n');
  if(!confirm(`永久刪除各硬碟 VideoSIFT\\待刪 裡的 ${r.n.toLocaleString()} 個檔（${fmtB(r.bytes)}）？\n${by}\n\n・不經過資源回收筒，空間馬上回來，刪了救不回來\n・預覽圖、人臉資料、清單裡那一筆一起清掉\n・初剪的檔 100% 保留${r.skip_cut?`（這次有 ${r.skip_cut} 個初剪的不刪）`:''}`))return;
  if(r.n>20&&!confirm(`再確認一次：永久刪除 ${r.n.toLocaleString()} 個檔、${fmtB(r.bytes)}？`))return;const x=await api('/api/lib',{a:'trash_purge'});toast(x.message||'',8000);setTimeout(()=>loadList(true),3000)}
const DURS=[['','全部時長'],['s','< 1 分'],['m','1–10 分'],['l','10–60 分'],['x','> 1 小時'],['z','沒時長']];
function durChips(){const el=$('#durc');if(!el)return;const on=S.state&&S.state.lab&&S.state.lab.dur_chips;if(!on){el.innerHTML='';el.style.display='none';return}el.style.display='';
  el.innerHTML=DURS.map(([k,n])=>`<button class="pill ${(S.dur||'')===k?'on':''}" data-d="${k}">⏱ ${n}</button>`).join('');
  $$('#durc .pill').forEach(b=>b.onclick=()=>{S.dur=b.dataset.d;saveView();loadList(true)})}
// V0.2.39 ⌨ 鍵盤操作（電腦瀏覽器開網頁版時；實驗工作區「⌨ 快捷鍵一覽」打開才有）
const WKEYS=[['?','這個快捷鍵一覽'],['H','🙈 隱私模糊 開／關（要打開 🙈 隱私模糊）'],['/','跳到搜尋框'],['Esc','關掉最上層的視窗'],['看檔案時 1／2／3／4','分級 S／A／E／F'],['看檔案時 0','取消分級'],['看檔案時 G','🤖 照分級建議分（要打開 🤖 分級建議）'],['看檔案時 ←／→','上一部／下一部'],['Ctrl+Shift+U','📋 打開上傳看板'],['看檔案時 U','📤 標成／取消「已上傳」（要打開 📤 複製到上傳資料夾）'],['看檔案時 P','✅ 標成／取消「已發佈」'],['看影片時 空白鍵','播放／暫停'],['看影片時 ←／→','±5 秒（Shift＝±1 秒）'],['看影片時 ↑／↓','音量'],['看影片時 B','🔖 加時間書籤（要打開 🔖 時間書籤）']];
function keysOv(){const old=$('#kov');if(old){old.remove();return}const d=document.createElement('div');d.id='kov';d.className='ov';d.style.cssText='z-index:9999;display:flex;align-items:center;justify-content:center';
  d.innerHTML=`<div class="si" style="max-width:520px;width:92%;background:var(--card,#222);border-radius:12px;padding:14px"><b>⌨ 快捷鍵一覽</b><table style="margin-top:8px;width:100%">${WKEYS.map(([k,n])=>`<tr><td style="padding:3px 12px 3px 0;white-space:nowrap"><code>${esc(k)}</code></td><td>${esc(n)}</td></tr>`).join('')}</table><div class="mu" style="margin-top:8px">再按一次 ? 或 Esc 關掉</div></div>`;
  d.onclick=()=>d.remove();document.body.appendChild(d)}
document.addEventListener('keydown',e=>{try{if(!(S.state&&S.state.lab&&S.state.lab.keys_help))return;if(e.ctrlKey||e.metaKey||e.altKey)return;
  const t=e.target,typing=t&&(t.tagName==='INPUT'||t.tagName==='TEXTAREA'||t.tagName==='SELECT'||t.isContentEditable);if(typing){if(e.key==='Escape')t.blur();return}
  const vid=$('#vov video');
  if(e.key==='?'){e.preventDefault();keysOv();return}
  if((e.key==='h'||e.key==='H')&&S.state.lab.privacy){e.preventDefault();pvSet(!document.body.classList.contains('pv'));return}
  if(e.key==='Escape'){const k=$('#kov');if(k){k.remove();return}if(BK.length){e.preventDefault();history.back()}return}
  if(vid){if(e.key===' '){e.preventDefault();vid.paused?vid.play():vid.pause();return}
    if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();vid.currentTime=Math.max(0,vid.currentTime+(e.key==='ArrowLeft'?-1:1)*(e.shiftKey?1:5));return}
    if((e.key==='b'||e.key==='B')&&$('#vov [data-bma]')){e.preventDefault();$('#vov [data-bma]').click();return}
    if(e.key==='ArrowUp'||e.key==='ArrowDown'){e.preventDefault();vid.volume=Math.min(1,Math.max(0,vid.volume+(e.key==='ArrowUp'?.1:-.1)));return}}
  if(F.f&&!vid){const G={'1':'S','2':'A','3':'E','4':'F','0':''};if(e.key in G){e.preventDefault();setGrade(G[e.key]);return}if((e.key==='g'||e.key==='G')&&$('#gguess')){e.preventDefault();$('#gguess').click();return}if(e.key==='r'&&(e.ctrlKey||e.metaKey)&&labOn('random_pick')&&$('#qrnd')){e.preventDefault();$('#qrnd').click();return}if((e.key==='p'||e.key==='P')&&labOn('copy_to')){e.preventDefault();const on=F.f.pub_t>0?0:1;api('/api/new',{a:'pub_mark',ids:[F.f.id],on}).then(j=>{F.f.pub_t=on?Date.now()/1000:0;toast(j.message||'')});return}if((e.key==='u'||e.key==='U')&&labOn('copy_to')){e.preventDefault();const on=F.f.up_t>0?0:1;api('/api/new',{a:'up_mark',ids:[F.f.id],on}).then(j=>{F.f.up_t=on?Date.now()/1000:0;toast(j.message||'')});return}
    if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();stepFile(e.key==='ArrowLeft'?-1:1);return}}
  if((e.key==='U'||e.key==='u')&&e.ctrlKey&&e.shiftKey&&labOn('copy_to')){e.preventDefault();location.hash='tool/upb';return}   // V0.4.41 📋
  if(e.key==='/'){const q=$('#q');if(q){e.preventDefault();q.focus();q.select()}}}catch(err){}});
async function viewsPick(){let j={};try{j=await api(U('/api/new',{a:'views'}))}catch(e){return}const V=j.views||[];   // V0.2.40 ⭐ 常用篩選
  const desc=v=>[(v.folder||'').split(/[\\/]/).filter(Boolean).pop()||'全部',v.flt&&v.flt!=='all'?((FLT.find(x=>x[0]===v.flt)||[0,fltName(v.flt)])[1]):'',v.q?'「'+v.q+'」':'',v.dur?'⏱'+((DURS.find(x=>x[0]===v.dur)||['',''])[1]):''].filter(Boolean).join('・');
  const d=document.createElement('div');d.className='sheet';
  d.innerHTML=`<div><div class="row"><h3 class="grow" style="margin:0">⭐ 常用篩選</h3><button class="pill" data-x>✕</button></div><div class="mu" style="margin:6px 0">電腦和手機共用；按一下就回到那個資料夾＋篩選</div>
   ${V.map(v=>`<div class="row"><button class="mi grow" data-v="${esc(v.name)}" style="text-align:left">⭐ ${esc(v.name)}<br><small class="mu">${esc(desc(v))}</small></button><button class="pill er" data-del="${esc(v.name)}">🗑</button></div>`).join('')||'<div class="mu">還沒存過</div>'}
   <button class="mi" data-new style="text-align:left">＋ 把目前的篩選存起來…</button></div>`;
  document.body.appendChild(d);const close=layer(d);$('[data-x]',d).onclick=()=>close();
  d.onclick=async e=>{const b=e.target.closest('[data-v],[data-del],[data-new]');if(!b)return;
    if(b.dataset.new!==undefined){const n=prompt('名字（例如「F 槽 未分級 長片」）',((S.folder||'').split(/[\\/]/).filter(Boolean).pop()||'全部')+(S.q?' '+S.q:''));if(!n)return;
      const r=await api('/api/new',{a:'view_save',name:n,view:{folder:S.folder||'',flt:S.flt||'all',q:S.q||'',sort:S.sort||'name',sub:!!S.sub,dur:S.dur||'',res:S.res||''}});toast(r.ok?'⭐ 已存（電腦也看得到）':(r.message||'沒存到'));close();return}
    if(b.dataset.del!==undefined){if(!confirm('刪除「'+b.dataset.del+'」？'))return;await api('/api/new',{a:'view_del',name:b.dataset.del});close();viewsPick();return}
    const v=V.find(x=>x.name===b.dataset.v);if(!v)return;S.folder=v.folder||'';S.flt=v.flt||'all';S.q=v.q||'';S.sort=v.sort||'name';S.sub=v.sub!==false;S.dur=v.dur||'';S.res=v.res||'';saveView();
    const q=$('#q');if(q)q.value=S.q;await close();if(location.hash==='#fx'||!location.hash)loadList(true);else location.hash='fx';toast('⭐ '+v.name)}}
function sprBar(){const el=$('#sprb');if(!el)return;const V=S.state&&S.state.sprint;if(!V){el.innerHTML='';return}   // V0.3.72 ⏱ 衝刺
  const left=Math.max(0,V.left-Math.floor((Date.now()-(S._sprAt||Date.now()))/1000));const on=V.on&&left>0;
  el.innerHTML=`<div style="display:flex;align-items:center;gap:8px;margin:2px 0 4px;cursor:pointer" onclick="location.hash='tool/spr'"><small style="color:${on?'#ffc94d':'#45d483'}">${on?'⏱ 衝刺 <b>'+Math.floor(left/60)+':'+String(left%60).padStart(2,'0')+'</b>・已分 <b>'+V.n+'</b> 部':'🏁 衝刺結束：<b>'+V.n+'</b> 部・每分 '+V.rate+(V.new_best?' 🏆 新紀錄':'')}</small></div>`;
  if(on&&!S._sprIv)S._sprIv=setInterval(()=>{if(!(S.state&&S.state.sprint&&S.state.sprint.on)){clearInterval(S._sprIv);S._sprIv=0}sprBar()},1000)}
function upGoalBar(){const el=$('#upgb');if(!el)return;const G=S.state&&S.state.up_goal;if(!G){el.innerHTML='';return}   // V0.3.63 📤 每天上傳目標
  const p=Math.min(100,G.n/G.goal*100);el.innerHTML=`<div style="display:flex;align-items:center;gap:8px;margin:2px 0 4px"><small>${G.done?'🎉':(G.by==='pub'?'✅':'📤')} 今天${G.by==='pub'?'發佈':'上傳'} <b>${G.n}</b>／${G.goal}</small><div style="flex:1;height:6px;border-radius:3px;background:rgba(127,127,127,.25);overflow:hidden"><i style="display:block;height:100%;width:${p.toFixed(1)}%;background:${G.done?'#45d483':'#4dd68a'}"></i></div></div>`}
function goalBar(){const el=$('#goalb');const G=S.state&&S.state.goal;if(!el)return;if(!G){el.innerHTML='';return}   // V0.2.44 🎯
  const p=Math.min(100,G.n/G.goal*100);el.innerHTML=`<div style="display:flex;align-items:center;gap:8px;margin:4px 0;cursor:pointer"><small>${G.done?'🎉':'🎯'} 今天 <b>${G.n.toLocaleString()}</b>／${G.goal.toLocaleString()}${(G.streak||0)>=2?' 🔥'+G.streak+' 天':''}</small><div style="flex:1;height:8px;border-radius:4px;background:rgba(127,127,127,.25);overflow:hidden"><i style="display:block;height:100%;width:${p.toFixed(1)}%;background:${G.done?'#45d483':'#4dc9ff'}"></i></div></div>`;
  el.onclick=async()=>{const n=prompt('🎯 一天要分級幾部？',G.goal);if(!n||!(+n>0))return;const r=await api('/api/new',{a:'goal',n:+n});if(r.ok){S.state.goal=r.goal;goalBar();toast('🎯 目標改成每天 '+r.n+' 部')}}}
async function recentPick(){let j={};try{j=await api(U('/api/new',{a:'recent'}))}catch(e){return}const R=j.rows||[];   // V0.2.56 🕘
  const d=document.createElement('div');d.className='sheet';const nm=p=>p.split(/[\\/]/).filter(Boolean).pop()||p;
  d.innerHTML=`<div><div class="row"><h3 class="grow" style="margin:0">🕘 最近開過的資料夾</h3><button class="pill" data-x>✕</button></div>${R.map(p=>`<button class="mi" data-f="${esc(p)}" style="text-align:left">📁 ${esc(nm(p))}<br><small class="mu">${esc(p)}</small></button>`).join('')||'<div class="mu">還沒有</div>'}</div>`;
  document.body.appendChild(d);const close=layer(d);$('[data-x]',d).onclick=()=>close();
  d.onclick=async e=>{const b=e.target.closest('[data-f]');if(!b)return;S.folder=b.dataset.f;saveView();await close();if(location.hash==='#fx'||!location.hash)loadList(true);else location.hash='fx'}}
function notifyDiff(a,b){if(!a||!b||!(b.lab&&b.lab.phone_notify))return;const M=[];   // V0.2.72 🔔 狀態變化提醒
  if(b.auto_scan&&a.auto_scan&&b.auto_scan.last_t&&b.auto_scan.last_t!==a.auto_scan.last_t&&b.auto_scan.last_new>0)M.push(`👀 多了 ${b.auto_scan.last_new} 部新影片`);
  if(a.copy&&b.copy&&(a.copy.run||a.copy.q)&&!b.copy.run&&!b.copy.q)M.push(`📤 複製完成：${b.copy.done} 部`+(b.copy.fail?`、失敗 ${b.copy.fail}`:''));
  if(b.auto_rule&&(!a.auto_rule||a.auto_rule.t!==b.auto_rule.t))M.push(`⚡ 自動規則分了 ${b.auto_rule.n} 部`);   // V0.3.31
  try{const h=new Date().getHours(),day=new Date().toDateString();if(b.goal&&!b.goal.done&&h>=(+b.nag_h||21)&&(+b.nag_h||21)<24&&LS.get('goalNag','')!==day){LS.set('goalNag',day);M.push(`🎯 今天還差 ${b.goal.goal-b.goal.n} 部就達成${(b.goal.streak||0)>=1?'（連續 '+b.goal.streak+' 天的紀錄別斷了 🔥）':''}`)}}catch(e){}   // V0.3.45 晚上 9 點提醒一次
  try{if(b.lab&&b.lab.done_notify){if((b.busy||[]).length){if(!S._bz0)S._bz0=Date.now();S._bzL=Date.now()}else if(S._bz0&&Date.now()-S._bzL>20000){const d=S._bzL-S._bz0;S._bz0=0;if(d>=300000)M.push('🔔 電腦背景全部做完了')}}}catch(e){}   // V0.4.04
  try{const h=new Date().getHours(),day=new Date().toDateString();if((b.unpub||0)>0&&h>=22&&LS.get('pubNag','')!==day){LS.set('pubNag',day);M.push(`⬜ 還有 ${b.unpub} 部複製了還沒發佈`)}}catch(e){}   // V0.4.37 晚上 10 點提醒一次
  if(a.goal&&b.goal&&!a.goal.done&&b.goal.done)M.push(`🎉 今天的目標 ${b.goal.goal} 部達成！`);
  if(a.sprint&&a.sprint.on&&b.sprint&&!b.sprint.on)M.push(`🏁 衝刺結束：分了 ${b.sprint.n} 部${b.sprint.new_best?'（🏆 新紀錄）':''}`);if(a.up_goal&&b.up_goal&&!a.up_goal.done&&b.up_goal.done)M.push(`🎉 今天上傳 ${b.up_goal.goal} 部的目標達成！`);   // V0.3.73
  const dw=x=>(x||[]).map(d=>d.d).join(',');if(b.disk_warn&&b.disk_warn.length&&dw(b.disk_warn)!==dw(a.disk_warn))M.push('⚠ 硬碟空間不足：'+b.disk_warn.map(d=>d.d).join('、'));
  if((b.jobs&&a.jobs)&&(a.jobs.cut_active||0)>0&&!(b.jobs.cut_active||0))M.push('✂ 剪輯都好了');
  if(M.length)toast(M.join('　'),6000);for(const m of M){try{if(document.hidden&&window.Notification&&Notification.permission==='granted')new Notification('SortCut',{body:m})}catch(e){}}}
function pvSet(on){on=!!on&&!!(S.state&&S.state.lab&&S.state.lab.privacy);document.body.classList.toggle('pv',on);LS.set('pv',on);const b=$('#pvp');if(b)b.classList.toggle('acc',on);toast(on?'🙈 模糊中（按住預覽圖可以暫時看）':'👁 取消模糊',1500)}   // V0.2.55
const RESS=[['','全部畫質'],['sd','< 720p'],['hd','720p'],['fhd','1080p'],['4k','4K']];   // V0.2.78 📺
function resChips(){const el=$('#resc');if(!el)return;el.innerHTML='';el.style.display='none';if(!labOn('res_chips'))return;   // V0.2.94 跟時長放同一排（省一排）
  const host=labOn('dur_chips')&&$('#durc')&&$('#durc').style.display!=='none'?$('#durc'):el;if(host===el)el.style.display='';
  host.insertAdjacentHTML('beforeend',(host===el?'':'<span style="flex:none;width:1px;align-self:stretch;background:var(--line);margin:0 4px"></span>')+RESS.map(([k,n])=>`<button class="pill ${(S.res||'')===k?'on':''}" data-r="${k}">📺 ${n}</button>`).join(''));
  $$('[data-r]',host).forEach(b=>b.onclick=()=>{S.res=b.dataset.r;loadList(true)})}
function chips(c){S.lastChips=c;try{if(LS.get('pv',false)&&S.state&&S.state.lab&&S.state.lab.privacy)document.body.classList.add('pv');else if(!(S.state&&S.state.lab&&S.state.lab.privacy))document.body.classList.remove('pv')}catch(e){}try{durChips();resChips();goalBar()}catch(e){}
  const L=FLT.slice();if(!FLT.some(x=>x[0]===S.flt))L.unshift([S.flt,fltName(S.flt)]);
  $('#chips').innerHTML=L.map(([k,n])=>{let x='';if(c){if(k==='all')x=c.all;else if(k==='nograde')x=c.nograde;else if(c[k]!==undefined)x=c[k]}
    const bb=c&&c.bytes?c.bytes[k==='all'?'all':k]:null;const gb=bb==null?'':bb<=0?'0GB':(bb>=1e12?(bb/1e12).toFixed(1)+'TB':bb>=1e8?(bb/1e9).toFixed(1)+'GB':Math.max(1,Math.round(bb/1e6))+'MB');
    return `<button class="pill ${S.flt===k?'on':''}" data-k="${esc(k)}"${gb?' style="line-height:1.15;padding-top:4px;padding-bottom:4px"':''}>${esc(n)}${x!==''&&x!=null?' '+x:''}${gb?`<br><small style="opacity:.8;font-weight:600">${gb}</small>`:''}</button>`}).join('');
  $$('#chips .pill').forEach(b=>b.onclick=()=>{S.flt=b.dataset.k;saveView();loadList(true)});
  if(labOn('playlist')){$('#chips').insertAdjacentHTML('afterbegin',`<button class="pill" id="plp">▶</button>`);$('#plp').onclick=()=>playList((S.rows||[]).slice(),0)}
  if(S.state&&S.state.lab&&S.state.lab.recent_dirs){$('#chips').insertAdjacentHTML('afterbegin',`<button class="pill" id="rcp">🕘</button>`);$('#rcp').onclick=recentPick}
  if(S.state&&S.state.lab&&S.state.lab.privacy){$('#chips').insertAdjacentHTML('afterbegin',`<button class="pill${document.body.classList.contains('pv')?' acc':''}" id="pvp">🙈</button>`);$('#pvp').onclick=()=>pvSet(!document.body.classList.contains('pv'))}
  if(S.state&&S.state.lab&&S.state.lab.views){$('#chips').insertAdjacentHTML('afterbegin',`<button class="pill acc" id="vwp">⭐</button>`);$('#vwp').onclick=viewsPick}
  if(S.flt==='F'){$('#chips').insertAdjacentHTML('beforeend',`<button class="pill" id="tpurge" style="background:#c62845;border-color:#c62845;color:#fff">🔥 清空待刪</button>`);$('#tpurge').onclick=purgeTrash}
  const on=$('#chips .pill.on'),row=$('#chips');if(on&&row)row.scrollLeft=(on.offsetLeft-row.offsetLeft+on.offsetWidth<=row.clientWidth-8)?0:Math.max(0,on.offsetLeft-row.offsetLeft-row.clientWidth/2+on.offsetWidth/2);   /* V0.2.77 前面幾顆看得到就不捲 */   /* 只捲標籤列本身（scrollIntoView 會把整頁捲回最上面） */
}
/* 往下捲很快時：還在讀的那一批不會被打斷、也不會清掉重來 → 不會跳回最上面 */
async function loadList(reset){
  if(!$('#grid'))return;
  if(reset){S.gen++;S.rows=[];S.total=0;S.loading=false;$('#grid').innerHTML='';window.scrollTo(0,0)}
  if(S.loading)return;S.loading=true;const gen=S.gen;$('#more').textContent='讀取中…';
  let j;try{j=await api(U('/api/list',{folder:S.folder,flt:S.flt,q:S.q,dur:S.dur||'',res:S.res||'',sort:S.sort,sub:S.sub?1:0,off:S.rows.length,lim:90}))}catch(e){j=null}
  if(gen!==S.gen)return;S.loading=false;
  if(!j||!j.ok||!$('#grid')){const m=$('#more');if(m)m.innerHTML='讀取失敗　<button class="pill" onclick="loadList(false)">再試一次</button>';return}
  S.total=j.total;if(j.off===0){chips(j.chips);S.hidden=j.hidden||[];
    $('#hidn').innerHTML=S.hidden.length?`🚫 沒列出來：${S.hidden.slice(0,6).map(h=>esc(h[0].slice(1))+' '+h[1]).join('、')}　<a href="#set" onclick="S.scat='ext'">設定可以改</a>`:''}
  const have=new Set(S.rows.map(r=>r.id));const g=$('#grid');let h='';j.rows.forEach(r=>{if(have.has(r.id))return;S.rows.push(r);h+=cardHTML(r)});g.insertAdjacentHTML('beforeend',h);
  bindCards();$('#more').textContent=S.rows.length?(S.rows.length<S.total?'往下捲載入更多（'+S.rows.length+'／'+S.total+'）':'共 '+S.total+' 部'):'這裡沒有影片'+(S.flt!=='all'||S.q?'（篩選中）':'');
  /* 一次捲很遠、底部還在畫面裡 → 接著讀下一批 */
  const m=$('#more');if(m&&S.rows.length<S.total&&m.getBoundingClientRect().top<window.innerHeight+600)setTimeout(()=>loadList(false),30);
}
function cardHTML(r){
  const g=r.grade||'';const img=r.th_state===2?`style="background-image:url('${U('/api/card',{id:r.id})}')"`:'';
  return `<div class="c ${g?'b'+g:''} ${S.sel.has(r.id)?'sel':''}" data-id="${r.id}"><div class="th" ${img}>${r.th_state===2?'':'預覽圖還沒好'}${r.dur?`<span class="du">${fmtT(r.dur)}</span>`:''}</div>
   ${g?`<div class="gb g${g}">${g}</div>`:''}${(r.cut_n||r.cut_pend)?`<div class="cutb${r.cut_pend?' run':''}${g?'':' nog'}">${r.cut_pend?'-':'√'}剪輯${(r.cut_n||0)+(r.cut_pend||0)}</div>`:''}<div class="fl">${r.fav?'★':''}${r.viewed?'✔':''}${(r.up_t>0&&S.state&&S.state.lab&&S.state.lab.copy_to)?(r.pub_t>0?'✅':'📤'):''}${TAGS[r.tag]||''}</div><i class="ck"></i>
   <div class="nm">${esc(r.name)}</div><div class="mch"><span class="ch xs">${fmtB(r.size)}</span>${r.h?`<span class="ch xd">${r.h}p</span>`:''}${(r.still||0)>=0.3&&labOn('still_scan')?`<span class="ch" title="靜止／黑畫面佔的比例">😴${Math.round(r.still*100)}%</span>`:''}${(r.people||[]).map(p=>`<span class="ch xp">👤${esc(p)}</span>`).join('')}</div></div>`}
function bindCards(){$$('#grid .c').forEach(c=>{if(c._b)return;c._b=1;let lp=null,fired=false;
  c.addEventListener('pointerdown',e=>{if(e.pointerType==='mouse')return;fired=false;const x0=e.clientX,y0=e.clientY;clearTimeout(lp);
    lp=setTimeout(()=>{lp=null;fired=true;vib();if(!S.selMode)setSel(true);const id=+c.dataset.id;S.sel.add(id);c.classList.add('sel');selBar()},550);
    const mv=ev=>{if(Math.abs(ev.clientX-x0)+Math.abs(ev.clientY-y0)>12){clearTimeout(lp);lp=null}};c.addEventListener('pointermove',mv,{passive:true});
    const up=()=>{clearTimeout(lp);c.removeEventListener('pointermove',mv)};c.addEventListener('pointerup',up,{once:true});c.addEventListener('pointercancel',up,{once:true})});
  c.onclick=()=>{if(fired){fired=false;return}const id=+c.dataset.id;if(S.selMode){S.sel.has(id)?S.sel.delete(id):S.sel.add(id);c.classList.toggle('sel');selBar()}else openFile(id)};
  c.oncontextmenu=e=>{e.preventDefault()}})}
let SELCLOSE=null;
function setSel(on){if(on===S.selMode)return;
  if(on){S.selMode=true;const close=fromBack=>{if(!S.selMode)return Promise.resolve();S.selMode=false;SELCLOSE=null;S.sel.clear();$$('#grid .c.sel').forEach(c=>c.classList.remove('sel'));$('#grid')&&$('#grid').classList.remove('selmode');paintSm();selBar();return fromBack===true?Promise.resolve():bkDone(close)};SELCLOSE=close;bkPush(close)}
  else if(SELCLOSE)SELCLOSE();
  $('#grid')&&$('#grid').classList.toggle('selmode',S.selMode);paintSm();selBar()}
function paintSm(){const b=$('#smode');if(b){b.textContent=S.selMode?'✖ 結束多選':'☑ 多選';b.classList.toggle('on',S.selMode)}}
function selBar(){let b=$('#selbar');if(!S.selMode){b&&b.remove();return}
  if(!b){b=document.createElement('div');b.id='selbar';b.className='vgAct';document.body.appendChild(b)}
  const n=S.sel.size;b.innerHTML=`<span class="mu" style="flex:none">已選 <b>${n}</b> 部</span>${['S','A','E','F'].map(g=>`<button class="pill" style="border-color:var(--${g});color:var(--${g})" onclick="batch({grade:'${g}'})">${g}</button>`).join('')}
  <button class="pill" onclick="batch({grade:''})">取消分級</button><button class="pill" onclick="batch({viewed:1})">✔看過</button><button class="pill" onclick="batch({fav:1})">★</button>
  <button class="pill" onclick="batchMenu()">更多…</button><button class="pill" onclick="selAll()">全選</button><button class="pill" onclick="selNone()">全不選</button>`}
function selAll(){S.rows.forEach(r=>S.sel.add(r.id));$$('#grid .c').forEach(c=>c.classList.add('sel'));selBar()}
function selNone(){S.sel.clear();$$('#grid .c').forEach(c=>c.classList.remove('sel'));selBar()}
async function batch(kw){const ids=[...S.sel];if(!ids.length)return toast('先點選影片');const j=await api('/api/flags',{ids,...kw});if(j.ok){S.undo=j.undo;toast(`${j.n} 部已改（右下「↩ 復原」可以改回）`);applyFlags(ids,kw);undoBtn()}}
function applyFlags(ids,kw){ids.forEach(id=>{const r=S.rows.find(x=>x.id===id);if(r)Object.assign(r,kw);const c=$(`#grid .c[data-id="${id}"]`);if(c&&r){const sel=c.classList.contains('sel');c.outerHTML=cardHTML(r);if(sel)$(`#grid .c[data-id="${id}"]`).classList.add('sel')}});bindCards()}
function undoBtn(){let u=$('#undo');if(!u){u=document.createElement('button');u.id='undo';u.className='pill wa';document.body.appendChild(u)}
  u.textContent='↩ 復原';u.onclick=async()=>{if(!S.undo)return;const L=S.undo;S.undo=null;u.remove();const j=await api('/api/undo_flags',{undo:L});if(j.ok){toast('已復原');L.forEach(x=>{const kw={...x};delete kw.id;applyFlags([x.id],kw);if(F.f&&F.f.id===x.id){Object.assign(F.f,kw);paintFile()}})}};
  clearTimeout(u._t);u._t=setTimeout(()=>u.remove(),15000)}
async function batchMenu(){const ids=[...S.sel];if(!ids.length)return toast('先點選影片');const f=await api(U('/api/file',{id:ids[0]}));const T=(f.file&&f.file.arch_targets)||[];
  menu(`${ids.length} 部`,[...T.map(t=>[`📦 歸檔到 ${t.name}`,()=>op(t.kind,ids,true)]),['🗑 移到待刪',()=>op('trash',ids,true)],['⭐ 收藏（複製到收藏）',()=>op('fav',ids)],...(S.state&&S.state.lab&&S.state.lab.copy_to?[['📤 複製到上傳資料夾',()=>copyTo(ids)],['📤 剪好的片段複製到上傳資料夾',()=>copyTo(ids,1)],[`📤 ${ids.length} 部標成已上傳`,async()=>{const r=await api('/api/new',{a:'up_mark',ids,on:1});toast(r.message||'');loadList(true)}],[`✅ ${ids.length} 部標成已發佈`,async()=>{const r=await api('/api/new',{a:'pub_mark',ids,on:1});toast(r.message||'');loadList(true)}]]:[]),...(labOn('caption')?[[`📋 複製 ${ids.length} 部的上傳文案`,async()=>{const T=[];for(const id of ids.slice(0,50)){const j=await api(U('/api/new',{a:'caption',id}),undefined,{quiet:true}).catch(()=>({}));if(j.text)T.push(j.text)}const t=T.join('\n\n');try{await navigator.clipboard.writeText(t);toast(`📋 已複製 ${T.length} 部的文案`)}catch(e){prompt('長按複製：',t)}}]]:[]),...(labOn('scenes')?[[`✂ 都剪掉 😴 靜止段落（${ids.length} 部）`,async()=>{if(!confirm(`${ids.length} 部：每部把靜止／黑畫面剪掉，有內容的合成一個新檔（原檔不動）？`))return;const r=await api('/api/new',{a:'cut_static',ids});toast(r.message||'',7000)}]]:[]),['🔁 加入轉檔',()=>op('conv',ids)],
   ['⚡ 先做預覽圖',()=>op('front',ids)],['🔁 重做預覽圖（精準）',()=>op('redo_precise',ids)],['❌ 刪除已剪輯的原檔（資源回收筒）',()=>op('delete_original',ids,true)],['• 標成沒看過',()=>batch({viewed:0})],
   ...Object.entries(TAGS).map(([k,v])=>[v+' 顏色標籤',()=>batch({tag:k})]),['拿掉顏色標籤',()=>batch({tag:''})]])}
async function op(kind,ids,confirmIt){if(confirmIt&&!confirm(`確定？（${ids.length} 部）`))return;const j=await api('/api/op',{kind,ids});if(j.message)toast(j.message);
  if(j.ok&&(['trash','delete_original'].includes(kind)||kind.startsWith('grade:')||kind.startsWith('cat:'))){const fo=$('#fov');if(fo&&fo._close)await fo._close();if(S.selMode)setSel(false);setTimeout(()=>S.tab==='fx'&&loadList(true),900)}}
function menu(title,items){const d=document.createElement('div');d.className='sheet';d.innerHTML=`<div><h3>${esc(title)}</h3>${items.map((x,i)=>`<button class="mi" data-i="${i}">${esc(x[0])}</button>`).join('')}<button class="mi" style="color:var(--sub)" data-x>取消</button></div>`;
  document.body.appendChild(d);const close=layer(d);
  d.onclick=e=>{const b=e.target.closest('.mi');if(e.target===d||(b&&b.dataset.x!==undefined)){close();return}if(b&&b.dataset.i!==undefined){const fn=items[+b.dataset.i][1];close().then(fn)}}}
async function pickFolder(el){
  if(el&&el.nodeType!==1)el=null;
  const j=S.folders||await api('/api/folders');S.folders=j;const roots=j.roots||[];
  const F_=(j.folders||[]).slice().sort((a,b)=>a.path.localeCompare(b.path));
  const agg={};F_.forEach(f=>{const r=roots.find(x=>f.path.toLowerCase().startsWith(x.toLowerCase().replace(/[\\/]+$/,'')))||'';let p=f.path;
    while(true){agg[p]=agg[p]||{n:0,gr:0,root:r};agg[p].n+=f.n;agg[p].gr+=f.gr;if(!r||p.length<=r.replace(/[\\/]+$/,'').length)break;const q=p.replace(/[\\/][^\\/]*$/,'');if(q===p||!q)break;p=q}});
  const keys=Object.keys(agg).sort((a,b)=>a.localeCompare(b));
  const d=el||document.createElement('div');if(!el)d.className='sheet';
  d.innerHTML=`<div><div class="row"><h3 class="grow" style="margin:0">📁 ${el?'資料夾':'選資料夾'}</h3>${el?'':'<button class="pill" data-x>✕</button>'}</div><div class="row" style="margin-top:8px;gap:6px"><button class="pill" data-la="add">＋ 加硬碟／資料夾</button><button class="pill" data-la="scan">🔄 全部重新掃描</button><button class="pill" data-la="set">⚙ 影片庫設定</button></div><input class="search" id="fq" placeholder="🔍 找資料夾" style="margin:8px 0"><div id="fl"></div><div class="mu" style="margin-top:6px">▸＝展開子資料夾（只看你要的那一個）；點名稱＝只看這個資料夾；⚙＝先做預覽圖、一鍵歸檔、排除、重新掃描…</div></div>`;
  const rootOf=k=>(agg[k]||{}).root.replace(/[\\/]+$/,'');const isRoot=k=>k.length<=rootOf(k).length;const par=k=>isRoot(k)?'':k.replace(/[\\/][^\\/]*$/,'');
  const kids={};keys.forEach(k=>{const p=par(k);if(p){(kids[p]=kids[p]||[]).push(k)}});
  const EXP=new Set(LS.get('fexp',[]));if(S.folder){let p=par(S.folder);while(p){EXP.add(p);p=par(p)}}
  const vis=k=>{let p=par(k);while(p){if(!EXP.has(p))return false;p=par(p)}return true};
  const row=(k,flat)=>{const a=agg[k],root=rootOf(k);const depth=isRoot(k)?0:k.slice(root.length).split(/[\\/]/).filter(Boolean).length;const nm=depth?k.split(/[\\/]/).filter(Boolean).pop():k;
    const pc=a.n?Math.round(a.gr*100/a.n):0;const off=(j.offline||[]).some(o=>k.toLowerCase().startsWith(o.toLowerCase().replace(/[\\/]+$/,'')));
    const tg=!flat&&kids[k]?`<button class="ftg pill" data-t="${esc(k)}" style="flex:none;width:44px;height:40px;padding:0;font-size:18px;font-weight:800;margin-right:4px${EXP.has(k)?';border-color:var(--vline);color:var(--vline)':''}">${EXP.has(k)?'▾':'▸'}</button>`:'<span style="display:inline-block;width:48px;flex:none"></span>';
    return `<div class="row" style="gap:0;padding-left:${flat?0:depth*14}px">${tg}<button class="mi grow ${S.folder===k?'cur':''}" data-p="${esc(k)}" style="text-align:left">${depth?'📁':'💽'} ${esc(nm)} <span class="mu">${a.n.toLocaleString()}${pc?' · 分級 '+pc+'%':''}${off?' · 💤 離線':''}</span></button><button class="fgear" data-gear="${esc(k)}">⚙</button></div>`};
  const draw=(q)=>{const L=q?keys.filter(k=>k.toLowerCase().includes(q.toLowerCase())).slice(0,400):keys.filter(vis);
    $('#fl',d).innerHTML=`<button class="mi ${!S.folder?'cur':''}" data-p="">🎬 全部影片</button>`+L.map(k=>row(k,!!q)).join('')+(q&&L.length>=400?'<div class="mu">只列前 400 個，請打更多字</div>':'')};
  let close;if(el)close=()=>Promise.resolve();else{document.body.appendChild(d);close=layer(d)}draw('');$('#fq',d).oninput=e=>draw(e.target.value);
  d.onclick=e=>{const gr=e.target.closest('[data-gear]');if(gr){const k=gr.dataset.gear;close().then(()=>folderGear(k));return}
    const la=e.target.closest('[data-la]');if(la){const k=la.dataset.la;if(k==='scan'){ctl('scan');return}close().then(()=>k==='add'?addRoot():(S.scat='lib',location.hash='set/lib'));return}
    const t=e.target.closest('.ftg');if(t){const k=t.dataset.t;EXP.has(k)?EXP.delete(k):EXP.add(k);LS.set('fexp',[...EXP].slice(-300));draw($('#fq',d).value);return}
    const b=e.target.closest('.mi');if(e.target===d||e.target.closest('[data-x]')){close();return}if(b){const p=b.dataset.p;close().then(()=>{S.folder=p;S.folders=null;saveView();viewFx()})}};
  const cur=$('.mi.cur',d);if(cur&&!el)cur.scrollIntoView({block:'center'})}
async function folderMove(k){const j=await api(U('/api/new',{a:'drives',folder:k}));if(!j.ok)return toast(j.message||'讀不到硬碟');if(!(j.rows||[]).length)return toast('沒有偵測到別顆硬碟');
  menu('🚚 搬到哪一顆？',j.rows.map(x=>[`${x.d}:（${x.label||'沒有名稱'}）剩 ${fmtB(x.free)}`,async()=>{const to=prompt('新位置（可以改）：',x.d+':'+k.slice(2));if(!to)return;
    if(!confirm(`${k}\n→ ${to}\n\n整個資料夾（含子資料夾）搬過去，分級、備註、預覽圖都跟著過去。每個檔先複製、比對一樣才刪原檔；背景慢慢搬。`))return;
    const r=await api('/api/new',{a:'folder_move',folder:k,to});toast(r.message||'',6000)}]))}
async function folderGear(k){const j=await api(U('/api/lib',{a:'fold',folder:k}));if(!j.ok)return toast(j.message||'讀不到');const G=j.grades||{},nm=k.split(/[\\/]/).filter(Boolean).pop()||k;
  const to=g=>g==='F'&&j.f_trash?'待刪':((j.names||{})[g]||g);const L=[['🗺 看大小／能省多少（檔案總覽）',()=>{EX.p=String(k).replace(/[\\/]+$/,'');EX.q='';exSave();location.hash='tool/explore'}],['🔁 轉檔這個資料夾…',()=>exConvMenu(String(k).replace(/[\\/]+$/,''),String(k).split(/[\\/]/).filter(Boolean).pop()||k)],['⚡ 這個資料夾的預覽圖先做',async()=>{const r=await api('/api/lib',{a:'front',folder:k});toast(r.message||'')}]];
  ['S','A','E','F'].forEach(g=>{const [n,sz]=G[g]||[0,0];if(n)L.push([`📦 歸檔 ${g}（${GN[g]}）${n.toLocaleString()} 部・${fmtB(sz)} → VideoSIFT\\${to(g)}`,async()=>{if(!confirm(`把「${k}」裡分級 ${g}（${GN[g]}）的 ${n.toLocaleString()} 部（${fmtB(sz)}）搬到各自硬碟的 VideoSIFT\\${to(g)}？\n\n同一顆硬碟只是改位置，很快；歸進去就不再出現在清單。\n每一筆都記在「📒 操作紀錄」，搬錯可以搬回來。`))return;const r=await api('/api/lib',{a:'archive',g,folder:k});toast(r.message||'',6000);S.folders=null;setTimeout(()=>S.tab==='fx'&&loadList(true),1500)}])});
  if(j.is_root){L.push(['🔄 重新掃描這顆',async()=>{const r=await api('/api/lib',{a:'rescan',path:k});toast(r.message||'')}]);
    L.push(['➖ 從影片庫移除（檔案、預覽圖都不刪）',async()=>{if(!confirm(`從影片庫移除 ${k}？\n只是不再列出，檔案和已做好的預覽圖都不會刪。`))return;const r=await api('/api/lib',{a:'root_del',path:k});toast(r.message||'');S.folders=null;if(S.folder&&S.folder.toLowerCase().startsWith(k.toLowerCase())){S.folder='';saveView()}viewFx()}])}
  if(!j.is_root&&labOn('folder_move'))L.push(['🚚 搬到別顆硬碟…',()=>folderMove(k)]);   // V0.2.99 手機也能搬資料夾
  else{L.push(['🚫 排除這個資料夾（含子資料夾）',async()=>{if(!confirm(`排除「${k}」？之後不再掃描、清單不列（檔案沒動；可以在 ⚙ 影片庫設定 取消）`))return;const r=await api('/api/lib',{a:'exclude',kind:'dir',x:k});toast(r.message||'');S.folders=null;viewFx()}]);
    L.push([`🚫 排除所有叫「${nm}」的資料夾`,async()=>{if(!confirm(`不管在哪一層，叫「${nm}」的資料夾全部排除？`))return;const r=await api('/api/lib',{a:'exclude',kind:'name',x:nm});toast(r.message||'');S.folders=null;viewFx()}])}
  menu('⚙ '+nm,L)}
async function addRoot(path,pk){const j=await api(U('/api/lib',{a:'dirs',path:path||''}));if(!j.ok)return toast(j.message||'打不開');
  const d=document.createElement('div');d.className='sheet';
  d.innerHTML=`<div><div class="row"><h3 class="grow" style="margin:0">${pk?esc(pk.title):'＋ 加硬碟／資料夾（電腦上）'}</h3><button class="pill" data-x>✕</button></div><div class="mu" style="margin:6px 0;word-break:break-all">${j.path?'📂 '+esc(j.path):'選一顆硬碟'}</div>
   <div class="row" style="gap:6px">${j.path?`<button class="pill ok" data-ok>${pk?'✔ 就是這裡':'✔ 加入這個資料夾'}</button>`:''}${j.path?`<button class="pill" data-up="${esc(j.up||'')}">⬆ 上一層</button>`:''}</div><div style="margin-top:8px">${(j.dirs||[]).map(x=>`<button class="mi" data-p="${esc(x.path)}" style="text-align:left">${j.path?'📁':'💽'} ${esc(x.name)}</button>`).join('')||'<div class="mu">這裡沒有子資料夾</div>'}</div></div>`;
  document.body.appendChild(d);const close=layer(d);
  d.onclick=async e=>{if(e.target===d||e.target.closest('[data-x]')){close();return}const u=e.target.closest('[data-up]');if(u){close().then(()=>addRoot(u.dataset.up,pk));return}
    const b=e.target.closest('[data-p]');if(b){close().then(()=>addRoot(b.dataset.p,pk));return}
    if(e.target.closest('[data-ok]')&&pk){close();pk.ok(j.path);return}
    if(e.target.closest('[data-ok]')){if(!confirm(`把「${j.path}」加入影片庫並開始掃描？`))return;const r=await api('/api/lib',{a:'root_add',path:j.path});toast(r.message||'',6000);if(r.ok){close();S.folders=null;if(S.tab==='set'&&S.scat==='lib')setCat('lib')}}}}
function pinch(el,step){let pz=null;
  el.addEventListener('touchstart',e=>{if(e.touches.length===2){pz={d:Math.hypot(e.touches[0].clientX-e.touches[1].clientX,e.touches[0].clientY-e.touches[1].clientY)}}},{passive:true});
  el.addEventListener('touchmove',e=>{if(!pz||e.touches.length!==2)return;e.preventDefault();const d=Math.hypot(e.touches[0].clientX-e.touches[1].clientX,e.touches[0].clientY-e.touches[1].clientY);
    if(d/pz.d>1.3){step(-1);pz.d=d}else if(d/pz.d<0.77){step(1);pz.d=d}},{passive:false});
  el.addEventListener('touchend',e=>{if(e.touches.length<2)pz=null},{passive:true})}

// ---------------------------------------------------------------- 一部影片（每 N 秒一張圖排滿畫面，點選→初剪）
const F={};const GSTEPS=[2,4,6,8,10,20,30,60,120,180,300,600];const TCOLS=Array.from({length:29},(_,i)=>i+2);
// V0.2.12 📜 連續分級（手機）：滑到最下面空一列接下一部；上一部完全滑出去又沒分級（停留 ≥1.5 秒）→ 自動 F；一輪 10 部
const RV={n:1,t0:0,next:null,loading:false,stop:false,auto:[]};const RV_N=0,RV_MIN=0;   /* V0.2.15 不限部數 */
const rvOn=()=>LS.get('rvcont',true)!==false;
// V0.2.14 分級按鈕下面＝目前資料夾裡這個分級的總大小（跟檔案總管上面的標籤同一份）
function gbSize(k){const b=((S.lastChips||{}).bytes||{})[k];if(b==null)return k==='nograde'?'未分級':GN[k]||'';return b<=0?'0GB':(b>=1e12?(b/1e12).toFixed(1)+'TB':b>=1e8?(b/1e9).toFixed(1)+'GB':Math.max(1,Math.round(b/1e6))+'MB')}
// V0.2.14 格子的長寬比照預覽圖本身（有些影片記錄的寬高是轉向前的，格子會變扁）
function fixAR(el,f){if(!el||!f||!f.th_n)return;const im=new Image();im.onload=()=>{const c=f.th_cols||10,r=f.th_rows||10;if(!im.width||!im.height)return;const ar=(im.width/c)/(im.height/r);
  $$('.vgT',el).forEach(t=>t.style.aspectRatio=ar)};im.src=U('/api/sheet',{id:f.id,i:0})}
function tilesHTML(f){const st=f.th_step||2,m=Math.max(1,Math.round(F.gs/st)),gs=m*st,n=Math.ceil((f.th_n||0)/m),cols=f.th_cols||10,rows=f.th_rows||10,ar=(f.w&&f.h)?(f.w/f.h):16/9;let h='';
  const BT=(f.bm||[]).map(x=>x[0]);   // V0.2.96 🔖 有書籤的格子右上角黃色標記
  for(let i=0;i<n;i++){const hb=BT.some(t=>t>=i*gs&&t<(i+1)*gs);h+=`<div class="vgT" style="aspect-ratio:${ar};${tileCSS(f.id,i*m,cols,rows)}"><b>${fmtT(i*gs)}</b>${hb?'<i style="position:absolute;top:2px;right:2px;width:8px;height:12px;background:#ffc94d;border-radius:2px"></i>':''}</div>`}return h}
function rvNextId(after){if(!F.f)return null;const R=F.review;if(R){const k=after?R.ids.indexOf(after):R.i;return k>=0&&k+1<R.ids.length?R.ids[k+1]:null}
  const i=S.rows.findIndex(r=>r.id===(after||F.f.id));for(let k=i+1;k<S.rows.length;k++){const r=S.rows[k];if(r&&!r.grade&&r.th_state===2)return r.id}return null}
async function rvScroll(){const ov=$('#fov'),T=$('#tiles'),gb=$('#gb');if(!ov||!T||!gb||!F.f||!rvOn()||F.f.th_state!==2||!F.f.th_n)return;
  const top=gb.getBoundingClientRect().bottom,tb=T.getBoundingClientRect().bottom,th=(T.firstElementChild||{}).offsetHeight||120;
  if(!RV.next&&!RV.loading&&!RV.stop&&tb<innerHeight*2+300){                                     // V0.2.20 剩兩個畫面就先接
    let box=$('#rvnx');if(!box){box=document.createElement('div');box.id='rvnx';T.after(box)}
    if(RV_N&&RV.n>=RV_N){RV.stop=true;box.innerHTML=`<div class="rvsep" style="height:${th}px">⏸ 這一輪 ${RV_N} 部看完了：按 ▶ 或分級，開始下一輪</div>`;return}
    const nid=rvNextId();if(!nid){RV.stop=true;box.innerHTML=`<div class="rvsep" style="height:${th}px">— 清單最後一部了 —</div>`;return}
    RV.loading=true;const cur=F.f.id;let j;try{j=await api(U('/api/file',{id:nid}),undefined,{quiet:true})}catch(e){j=null}RV.loading=false;
    if(!F.f||F.f.id!==cur||!j||!j.ok)return;const f2=j.file;if(f2.th_state!==2||!f2.th_n){RV.stop=true;box.innerHTML=`<div class="rvsep" style="height:${th}px">下一部預覽圖還沒好：${esc(f2.name)}（按 ▶）</div>`;return}
    RV.next=f2;box.style.minHeight=innerHeight+'px';box.innerHTML=`<div class="rvsep" style="height:${th}px">▼ 下一部（連續第 ${RV.n+1} 部）：${esc(f2.name)}</div><div class="vgGrid${F.tcols>=8?' small':''}" id="rvgrid" style="--vgc:${F.tcols};pointer-events:none">${tilesHTML(f2)}</div>`;fixAR($('#rvgrid'),f2);
    const n2=rvNextId(f2.id);if(n2){let j2;try{j2=await api(U('/api/file',{id:n2}),undefined,{quiet:true})}catch(e){j2=null}      // V0.2.20 一次接兩部：再下一部也先接上
      if(j2&&j2.ok&&j2.file.th_state===2&&j2.file.th_n&&F.f&&F.f.id===cur&&RV.next===f2){const f3=j2.file;box.insertAdjacentHTML('beforeend',`<div class="rvsep" style="height:${th}px;color:var(--sub)">▼ 再下一部：${esc(f3.name)}</div><div class="vgGrid${F.tcols>=8?' small':''}" id="rvgrid2" style="--vgc:${F.tcols};pointer-events:none">${tilesHTML(f3)}</div>`);fixAR($('#rvgrid2'),f3)}}
    return}
  if(RV.next&&tb<top&&Date.now()-RV.t0>500){const g=$('#rvgrid');const off=g?Math.min(Math.max(0,top-g.getBoundingClientRect().top),Math.max(0,g.offsetHeight-th*2)):0;const prev=F.f,nx=RV.next;RV.next=null;
    const sg=segs();
    if(sg.length){const g0=prev.grade||'';const r=await api('/api/cut',{id:prev.id,segs:sg,merge:true});     // V0.2.15 有選片段就滑到下一部 → 全部合併輸出成 1 個，標 F
      if(r.ok){if(!g0){const q=await api('/api/flags',{ids:[prev.id],grade:'F'});if(q.ok)applyFlags([prev.id],{grade:'F'})}toast(`${prev.name}：選的 ${sg.length} 段合併輸出成 1 個初剪檔${g0?'（分級照你按的 '+g0+'）':'，標 F'}`,4000)}
      else toast('自動輸出初剪失敗：'+(r.message||''),6000)}
    else if(!prev.grade){const stay=Date.now()-RV.t0;
      if(stay<RV_MIN)toast(`只看了 ${(stay/1000).toFixed(1)} 秒就滑過去（太快，可能是誤觸）→ 沒標 F`,3000);
      else{const r=await api('/api/flags',{ids:[prev.id],grade:'F'});if(r.ok){RV.auto=RV.auto.slice(-49).concat([prev.id]);applyFlags([prev.id],{grade:'F'});toast(`${prev.name} 滑過去沒分級 → 自動 F（「↩ 復原自動 F」可以改回）`,3500)}}}
    RV.n++;const R=F.review;openFile(nx.id,{rvAdv:true,off,review:R?Object.assign(R,{i:R.i+1}):null})}}
async function rvUndo(){const ids=RV.auto.slice();if(!ids.length)return;const r=await api('/api/flags',{ids,grade:''});if(r.ok){applyFlags(ids,{grade:''});RV.auto=[];toast(`↩ 自動標的 F 改回沒分級：${ids.length} 部`);const b=$('#rvundo');if(b)b.style.display='none'}}
async function openFile(id,opt={}){
  const j=await api(U('/api/file',{id}));if(!j.ok)return;const f=j.file;
  if(!opt.rvAdv)RV.n=1;RV.t0=Date.now();RV.next=null;RV.loading=false;RV.stop=false;
  const old=$('#fov');let reuse=false;if(old)reuse=replaceLayer(old);
  Object.assign(F,{f,sel:new Set(),anchor:null,range:false,last:-1,gs:LS.get('gs',Math.max(f.th_step||2,f.grid_sec||2)),tcols:LS.get('tcols',window.innerWidth<500?4:8),review:opt.review||null});
  const ov=document.createElement('div');ov.id='fov';ov.className='ov';document.body.appendChild(ov);layer(ov,()=>{F.f=null;$('#cutbar')&&$('#cutbar').remove();document.body.classList.remove('fopen')},reuse);document.body.classList.add('fopen');
  if(S.state&&S.state.lab&&S.state.lab.swipe_nav){let sw=null;   // V0.2.42 👆 左滑下一部、右滑上一部
    ov.addEventListener('touchstart',e=>{if(e.touches.length!==1||e.target.closest('input,textarea,select,#cutbar,.sheet')){sw=null;return}const t=e.touches[0];sw={x:t.clientX,y:t.clientY,t:Date.now()}},{passive:true});
    ov.addEventListener('touchend',e=>{if(!sw||!F.f)return;const t=e.changedTouches[0],dx=t.clientX-sw.x,dy=t.clientY-sw.y,dt=Date.now()-sw.t;sw=null;
      if(Math.abs(dx)>90&&Math.abs(dy)<Math.abs(dx)*0.4&&dt<700&&!$('#vov')){toast(dx<0?'👉 下一部':'👈 上一部',900);stepFile(dx<0?1:-1)}},{passive:true})}
  const R=F.review;
  ov.innerHTML=`<div class="rph"><button class="back" id="fback">‹</button><div class="t"><b>${esc(f.name)}</b><small>${R?`🗂 分級 ${R.i+1}／${R.ids.length} · `:''}${fmtB(f.size)} · ${f.dur?fmtT(f.dur):'—'} · ${f.w||'?'}×${f.h||'?'} ${esc(f.vcodec||'')}</small></div>
   <button class="pill" id="fprev">◀</button><button class="pill" id="fnext">▶</button><button class="pill" id="fmenu">⋯</button></div><main style="padding-top:6px">
   ${labOn('copy_to')&&(f.up_t>0||f.pub_t>0)?`<div class="mu" style="margin:2px 0;font-size:12px;color:#3fd0c9">${f.up_t>0?'📤 '+new Date(f.up_t*1000).toLocaleDateString()+' 複製到上傳':''}${f.pub_t>0?'・✅ '+new Date(f.pub_t*1000).toLocaleDateString()+' 發佈':(f.up_t>0?'・⬜ 還沒發佈（按 P 或 ⋯ 標）':'')}</div>`:''}   ${f.dup_up?`<div class="mu" style="margin:2px 0;font-size:12px;color:#ffc94d">♻ 同一支影片已經傳過了（${esc(f.dup_up)}）</div>`:''}   ${f.guess&&!f.grade?`<div class="mu" id="gguess" data-g="${f.guess.g}" style="margin:2px 0 4px;font-size:12px;cursor:pointer">🤖 猜 <b style="color:var(--${f.guess.g})">${f.guess.g}</b>・${esc(f.guess.why)}　<u>點這裡照建議分</u></div>`:''}<div class="gbt" id="gb">${['S','A','E','F'].map(g=>`<button class="${g}" data-g="${g}">${g}<small>${gbSize(g)}</small></button>`).join('')}<button class="N" data-g="">—<small>${R?'跳過':gbSize('nograde')}</small></button><button class="D" data-fold="1" title="用資料夾分類：自動標 S，搬到 VideoSIFT\\資料夾">📁<small>資料夾</small></button></div>
   <div class="row"><button class="pill" id="bfav"></button><button class="pill" id="bview"></button><button class="pill" id="btag"></button><button class="pill" id="bnote"></button><button class="pill acc" id="bplay">▶ 播放</button></div>
   <div class="kv" style="margin:8px 0"><b>資料夾</b><span style="word-break:break-all">${esc(f.folder)}</span>${f.people&&f.people.length?`<b>人物</b><span>${f.people.map(p=>'👤'+esc(p)).join('　')}</span>`:''}${f.bm&&f.bm.length?`<b>🔖 書籤</b><span>${f.bm.map(([t,n])=>`<a href="#" data-bmt="${t}" style="color:#ffc94d">▶ ${fmtT(t)}${n?' '+esc(n):''}</a>`).join('　')}　<a href="#" data-bmsel style="color:var(--vline)">✂ 書籤附近選成片段</a></span>`:''}${f.cuts&&f.cuts.length?`<b>初剪</b><span>${f.cuts.map(c=>`<a href="#" data-out="${esc(c)}" style="color:var(--vline)">▶ ${esc(c)}</a>`).join('<br>')}</span>`:''}${f.arch?`<b>已歸檔</b><span>${esc(f.arch)}</span>`:''}</div>
   <div class="vgBar"><select id="gs"></select><button class="pill" id="tz1">－</button><select id="tc">${TCOLS.map(c=>`<option value="${c}">一列 ${c} 張</option>`).join('')}</select><button class="pill" id="tz2">＋</button><button class="pill" id="brange">↔ 範圍</button><button class="pill${rvOn()?' on':''}" id="rvtg">📜 連續</button><button class="pill" id="rvundo" style="display:${RV.auto.length?'':'none'}">↩ 復原自動 F（${RV.auto.length}）</button><span class="mu" id="thelp" style="flex:1 1 100%"></span></div>
   ${labOn('scenes')||labOn('bookmarks')?'<div class="mu" style="font-size:11px;margin:2px 0">🎬 橘線＝換場景　🔥 紅線＝動得多　😴 變暗＝靜止　🔖 黃塊＝書籤</div>':''}<div class="vgGrid" id="tiles"></div><div style="height:30px"></div></main>`;
  const cb=document.createElement('div');cb.id='cutbar';cb.className='vgAct';document.body.appendChild(cb);
  $('#fback').onclick=()=>ov._close();$('#fmenu').onclick=fileMenu;$('#fprev').onclick=()=>stepFile(-1);$('#fnext').onclick=()=>stepFile(1);
  $$('[data-out]',ov).forEach(a=>a.onclick=e=>{e.preventDefault();playOut(f.id,a.dataset.out)});
  $$('[data-bmt]',ov).forEach(a=>a.onclick=e=>{e.preventDefault();play(f,+a.dataset.bmt)});   // V0.2.80 🔖 從書籤播
  {const bs=$('[data-bmsel]',ov);if(bs)bs.onclick=e=>{e.preventDefault();const {n}=tileCount(),gs=F.gs;let k=0;   // V0.2.97 ✂ 前 5 秒～後 15 秒
    for(const [t] of f.bm)for(let i=Math.max(0,Math.floor((t-5)/gs));i<=Math.min(n-1,Math.floor((t+15)/gs));i++){if(!F.sel.has(i)){F.sel.add(i);k++}}drawSel();cutBar();toast(`✂ 選了 ${f.bm.length} 段（${k} 格），下面可以輸出初剪`)}}
  {const gg=$('#gguess',ov);if(gg)gg.onclick=()=>setGrade(gg.dataset.g)}   // V0.2.86 🤖 照建議分
  $$('#gb button[data-g]').forEach(b=>b.onclick=()=>setGrade(b.dataset.g));const bfd=$('#gb [data-fold]');if(bfd)bfd.onclick=foldPick;
  $('#bfav').onclick=()=>flag({fav:F.f.fav?0:1});$('#bview').onclick=()=>flag({viewed:F.f.viewed?0:1});
  $('#btag').onclick=()=>menu('顏色標籤',[...Object.entries(TAGS).map(([k,v])=>[v,()=>flag({tag:k})]),['拿掉標籤',()=>flag({tag:''})]]);
  $('#bnote').onclick=()=>{const NL=(S.state&&S.state.note_list)||[];const typ=()=>{const n=prompt('備註',F.f.note||'');if(n!==null)flag({note:n})};if(!NL.length)return typ();   // V0.2.82 ✎ 快速備註
    menu('✎ 備註',[...NL.map(t=>['＋ '+t,()=>{const o=F.f.note||'';if(o.includes(t))return toast('已經有了');flag({note:(o?o+'、':'')+t})}]),['✎ 自己打…',typ]])};$('#bplay').onclick=()=>play(F.f,F.f.last_pos||0);
  const st=f.th_step||2;const G=GSTEPS.filter(x=>x>=st&&x%st===0);$('#gs').innerHTML=G.map(x=>`<option value="${x}">每 ${x>=60?(x/60)+' 分':x+' 秒'}</option>`).join('');if(!G.includes(F.gs))F.gs=G[0];$('#gs').value=F.gs;
  $('#gs').onchange=e=>setStep(+e.target.value);$('#tc').value=String(F.tcols);$('#tc').onchange=e=>setTcols(+e.target.value);$('#tz1').onclick=()=>setTcols(F.tcols-1);$('#tz2').onclick=()=>setTcols(F.tcols+1);
  $('#brange').onclick=()=>{F.range=!F.range;F.anchor=null;paintRange();drawSel()};
  paintFile();paintRange();drawTiles();cutBar();tileEvents($('#tiles'));pinch($('#tiles'),d=>setTcols(F.tcols+d));
  F.sc=[];F.st=[];F.hl=[];if(labOn('scenes')&&f.th_state===2){const fid_=f.id;api(U('/api/new',{a:'scenes',id:fid_}),undefined,{quiet:true}).then(j=>{if(j&&j.ok&&F.f&&F.f.id===fid_){F.sc=j.rows||[];F.st=j.static||[];F.hl=j.hot||[];drawTiles();
    const sn=F.st.reduce((s_,[a,z])=>s_+z-a+1,0)*(f.th_step||2);if(F.sc.length||sn)toast(`🎬 ${F.sc.length} 個換場景`+(sn?`・😴 靜止 ${fmtT(sn)}`:''),2500);
    if(F.hl.length&&!$('#hlsel')){$('#tiles').insertAdjacentHTML('beforebegin',`<button class="pill" id="hlsel" style="margin:4px 4px 4px 0">🔥 選動得最多的地方</button>`);$('#hlsel').onclick=()=>{const {m,n}=tileCount();let k=0;for(const q of F.hl){const i=Math.floor(q/m);for(let j=Math.max(0,i-1);j<=Math.min(n-1,i+1);j++)if(!F.sel.has(j)){F.sel.add(j);k++}}drawSel();cutBar();toast(`🔥 選了 ${k} 格`)}}
    if(sn&&!$('#stsel'))$('#tiles').insertAdjacentHTML('beforebegin',`<button class="pill" id="stsel" style="margin:4px 0">✂ 選全部、跳過 😴 靜止的（${fmtT(sn)}）</button>`),$('#stsel').onclick=()=>{const {m,n}=tileCount(),ST=new Set(F.st.flatMap(([a,z])=>Array.from({length:z-a+1},(_,k)=>a+k)));F.sel.clear();for(let i=0;i<n;i++){let all=true;for(let q=i*m;q<i*m+m;q++)if(!ST.has(q)){all=false;break}if(!all)F.sel.add(i)}drawSel();cutBar();toast('✂ 選好了（跳過靜止的）')}}}).catch(()=>{})}   // V0.3.09／V0.3.11
  const rph=$('.rph',ov);$('#gb').style.top=(rph?rph.offsetHeight:0)+'px';                    // 分級按鈕一直停在上面
  $('#rvtg').onclick=()=>{const on=!rvOn();LS.set('rvcont',on);$('#rvtg').classList.toggle('on',on);toast(on?'📜 連續分級：開（滑到底接下一部）':'📜 連續分級：關');if(!on){const b=$('#rvnx');if(b)b.remove();RV.next=null}};$('#rvundo').onclick=rvUndo;
  ov.addEventListener('scroll',()=>{if(!ov._rvq){ov._rvq=1;requestAnimationFrame(()=>{ov._rvq=0;rvScroll()})}},{passive:true});
  if(opt.rvAdv){const T=$('#tiles'),gb=$('#gb');requestAnimationFrame(()=>{ov.scrollTop=Math.max(0,T.offsetTop-gb.offsetHeight-(rph?rph.offsetHeight:0)+(opt.off||0));setTimeout(rvScroll,300)})}else setTimeout(rvScroll,400)
}
function stepFile(d){if(!F.f)return;const R=F.review;if(R){const i=R.i+d;if(i<0||i>=R.ids.length){toast(d>0?'這一批分級完了 ✔':'已經是第一部');return}R.i=i;openFile(R.ids[i],{review:R});return}
  const i=S.rows.findIndex(r=>r.id===F.f.id);const r=S.rows[i+d];if(!r){toast(d>0?'已經是清單最後一部':'已經是第一部');return}openFile(r.id)}
function paintFile(){if(!F.f||!$('#fov'))return;const f=F.f;$$('#gb button').forEach(b=>b.classList.toggle('on',b.dataset.g===(f.grade||'')));
  $('#bfav').textContent=f.fav?'★ 已收藏記號':'☆ 收藏記號';$('#bview').textContent=f.viewed?'✔ 看過':'• 沒看過';$('#btag').textContent=(TAGS[f.tag]||'🏷')+' 標籤';$('#bnote').textContent='✎ 備註'+(f.note?'：'+f.note.slice(0,10):'')}
function paintRange(){const b=$('#brange');if(!b)return;b.textContent='↔ 範圍'+(F.range?'：開':'');b.classList.toggle('on',F.range);
  $('#thelp').textContent=F.range?'點起點、再點終點＝整段':(matchMedia('(pointer:fine)').matches?'點選、拖曳連選、Shift 連選、點兩下播放':'點選；長按播放；兩指捏合＝一列幾張')}
function setTcols(n){n=Math.max(2,Math.min(30,n|0));if(n===F.tcols)return;const top=topTile();F.tcols=n;LS.set('tcols',n);const s=$('#tc');if(s)s.value=String(n);
  const g=$('#tiles');g.style.setProperty('--vgc',n);g.classList.toggle('small',n>=8);if(top>=0){const el=$(`#tiles .vgT[data-i="${top}"]`);const ov=$('#fov');if(el&&ov)ov.scrollTop=el.offsetTop-$('.rph',ov).offsetHeight}}
function topTile(){const ov=$('#fov');if(!ov)return -1;const y=ov.scrollTop+$('.rph',ov).offsetHeight;for(const el of $$('#tiles .vgT')){if(el.offsetTop+el.offsetHeight>y)return +el.dataset.i}return -1}
function setStep(s){const old=segs();F.gs=s;LS.set('gs',s);F.sel.clear();const {n}=tileCount();for(let i=0;i<n;i++){const mid=i*s+s/2;if(old.some(g=>mid>=g[0]&&mid<=g[1]))F.sel.add(i)}drawTiles();cutBar()}
function tileCount(){const f=F.f,m=Math.max(1,Math.round(F.gs/(f.th_step||2)));return {m,n:Math.ceil((f.th_n||0)/m)}}
function drawTiles(){const f=F.f,el=$('#tiles');if(!el)return;el.style.setProperty('--vgc',F.tcols);el.classList.toggle('small',F.tcols>=8);
  if(f.th_state!==2||!f.th_n){el.style.setProperty('--vgc',1);el.innerHTML=`<div class="empty">預覽圖還沒做好${f.th_err?'：'+esc(f.th_err):''}<br>（已經排到最前面做了）</div>`;return}
  const cols=f.th_cols||10,rows=f.th_rows||10,{m,n}=tileCount(),ar=(f.w&&f.h)?(f.w/f.h):16/9;let h='';
  const BT=(f.bm||[]).map(x=>x[0]),HL=new Set(F.hl||[]),SC=new Set(F.sc||[]),ST=new Set((F.st||[]).flatMap(([a,z])=>Array.from({length:z-a+1},(_,k)=>a+k)));   // V0.2.97 🔖 有書籤的格子右上角黃色標記；V0.3.09 🎬 換場景的格子左邊橘線
  for(let i=0;i<n;i++){const hb=BT.some(t=>t>=i*F.gs&&t<(i+1)*F.gs);let sc=false,stc=true,hot=false;for(let q=i*m;q<i*m+m;q++){if(SC.has(q))sc=true;if(!ST.has(q))stc=false;if(HL.has(q))hot=true}h+=`<div class="vgT ${F.sel.has(i)?'on':''}${sc?' scn':''}${stc&&ST.size?' stc':''}${hot?' hot':''}" data-i="${i}" style="aspect-ratio:${ar};${tileCSS(f.id,i*m,cols,rows)}"><b>${fmtT(i*F.gs)}</b>${hb?'<i class="bmk" style="position:absolute;top:2px;right:2px;width:8px;height:12px;background:#ffc94d;border-radius:2px;pointer-events:none"></i>':''}</div>`}el.innerHTML=h;fixAR(el,f)}
function tileEvents(G){let drag=null,lp=null,skip=false;
  const at=e=>{const t=e.target&&e.target.closest?e.target.closest('.vgT'):null;return t?+t.dataset.i:-1};
  const set=(i,on)=>{if(i<0)return;on?F.sel.add(i):F.sel.delete(i);const t=$(`#tiles .vgT[data-i="${i}"]`);if(t)t.classList.toggle('on',on)};
  G.addEventListener('pointerdown',e=>{const i=at(e);if(i<0)return;
    if(e.pointerType==='mouse'){if(e.button!==0||F.range)return;e.preventDefault();skip=true;
      if(e.shiftKey&&F.last>=0){const a=Math.min(F.last,i),b=Math.max(F.last,i);for(let k=a;k<=b;k++)set(k,true);F.last=i;cutBar();return}
      const on=!F.sel.has(i);set(i,on);F.last=i;drag={on,i};cutBar();return}
    clearTimeout(lp);const x0=e.clientX,y0=e.clientY;lp=setTimeout(()=>{lp=null;skip=true;vib();preview(i)},550);
    const mv=ev=>{if(Math.abs(ev.clientX-x0)+Math.abs(ev.clientY-y0)>12){clearTimeout(lp);lp=null}};G.addEventListener('pointermove',mv,{passive:true});
    const up=()=>{clearTimeout(lp);G.removeEventListener('pointermove',mv)};G.addEventListener('pointerup',up,{once:true});G.addEventListener('pointercancel',up,{once:true})});
  G.addEventListener('pointerover',e=>{if(!drag)return;const i=at(e);if(i<0||i===drag.i)return;const a=Math.min(drag.i,i),b=Math.max(drag.i,i);for(let k=a;k<=b;k++)set(k,drag.on);drag.i=i;F.last=i;cutBar()});
  document.addEventListener('pointerup',()=>{drag=null});
  G.addEventListener('click',e=>{if(skip){skip=false;return}const i=at(e);if(i<0)return;
    if(F.range){if(F.anchor===null){F.anchor=i;drawSel();return}const a=Math.min(F.anchor,i),b=Math.max(F.anchor,i),add=!(F.sel.has(i)&&F.sel.has(F.anchor));for(let k=a;k<=b;k++)set(k,add);F.anchor=null;F.last=i;drawSel();cutBar();return}
    set(i,!F.sel.has(i));F.last=i;cutBar()});
  G.addEventListener('dblclick',e=>{const i=at(e);if(i<0)return;e.preventDefault();cutBar();preview(i)});
  G.addEventListener('contextmenu',e=>{if(at(e)>=0)e.preventDefault()})}
function drawSel(){$$('#tiles .vgT').forEach(t=>{const i=+t.dataset.i;t.classList.toggle('on',F.sel.has(i));t.classList.toggle('anchor',F.anchor===i)})}
function segs(){const L=[...F.sel].sort((a,b)=>a-b),out=[],dur=F.f?F.f.dur||0:0;let a=null,p=null;
  for(const i of L){if(a===null){a=i;p=i}else if(i===p+1){p=i}else{out.push([a*F.gs,Math.min((p+1)*F.gs,dur||1e9)]);a=i;p=i}}
  if(a!==null)out.push([a*F.gs,Math.min((p+1)*F.gs,dur||1e9)]);return out}
function cutBar(){const b=$('#cutbar');if(!b)return;const sg=segs(),tot=sg.reduce((s,x)=>s+x[1]-x[0],0);
  b.innerHTML=sg.length?`<span class="mu" style="flex:none">已選 <b>${F.sel.size}</b> 張 → <b>${sg.length}</b> 段 · ${fmtT(tot)}</span><button class="pill" onclick="play(F.f,segs()[0][0])">▶ 看第一段</button>
   <button class="pill acc" onclick="doCut(false)">✂ 初剪 ${sg.length} 段</button><button class="pill" onclick="doCut(true)">✂ 合併成一個</button><button class="pill" onclick="F.sel.clear();drawSel();cutBar()">清除</button>`
  :`<span class="mu">點圖片選要留下的片段（可複選），連續的合成一段</span><button class="pill" onclick="selectAllTiles()">全選</button>`}
function selectAllTiles(){const {n}=tileCount();for(let i=0;i<n;i++)F.sel.add(i);drawSel();cutBar()}
async function doCut(merge){const sg=segs();if(!sg.length)return;const j=await api('/api/cut',{id:F.f.id,segs:sg,merge});toast(j.message||(j.ok?'已排入初剪':'失敗'));if(j.ok){F.sel.clear();drawSel();cutBar()}}
async function foldPick(){if(!F.f)return;let j={};try{j=await api(U('/api/lib',{a:'info'}))}catch(e){return}const C=j.cats||[];   // V0.2.29 📁 用資料夾分類
  const d=document.createElement('div');d.className='sheet';
  d.innerHTML=`<div><div class="row"><h3 class="grow" style="margin:0">📁 用資料夾分類</h3><button class="pill" data-x>✕</button></div><div class="mu" style="margin:6px 0">選一個資料夾：這部自動標 S，搬到它所在硬碟的 VideoSIFT\\資料夾</div>
   ${C.map(c=>`<button class="mi" data-c="${esc(c)}" style="text-align:left">📁 ${esc(c)}</button>`).join('')||'<div class="mu">還沒有資料夾</div>'}<button class="mi" data-new style="text-align:left">＋ 新增資料夾…</button></div>`;
  document.body.appendChild(d);const close=layer(d);
  const go=async c=>{close();const fid=F.f.id;const g=await flag({grade:'S'});if(!g||!g.ok)return;const r=await api('/api/op',{kind:'cat:'+c,ids:[fid]});toast(r.ok?`📁 → S，搬到 VideoSIFT\\${c}`:(r.message||'沒搬成'),4000);
    if(F.review)setTimeout(()=>stepFile(1),250);else if(S.state&&S.state.lab&&S.state.lab.auto_next)setTimeout(nextUngraded,250)};
  d.onclick=async e=>{if(e.target===d||e.target.closest('[data-x]')){close();return}const b=e.target.closest('[data-c]');if(b)return go(b.dataset.c);
    if(e.target.closest('[data-new]')){const n=prompt('新資料夾名稱（例如：工作用）');if(!n||!n.trim())return;const r=await api('/api/lib',{a:'cat_add',name:n.trim()});if(!r.ok&&!C.includes(n.trim()))return toast(r.message||'名稱不能用');go(n.trim())}}}
async function setGrade(g){const R=F.review;if(R&&g===''){stepFile(1);return}const j=await flag({grade:g});if(j&&j.ok&&R)setTimeout(()=>stepFile(1),250);else if(j&&j.ok&&g&&S.state&&S.state.lab&&S.state.lab.auto_next)setTimeout(nextUngraded,250)}
function nextUngraded(){if(!F.f)return;const i=S.rows.findIndex(r=>r.id===F.f.id);const n=S.rows.length;for(let k=1;k<=n;k++){const r=S.rows[(i+k)%n];if(r&&!r.grade){openFile(r.id);return}}toast('這個清單都分級好了 👍')}
async function flag(kw){if(!F.f)return;const j=await api('/api/flags',{ids:[F.f.id],...kw});if(j.ok){Object.assign(F.f,kw);S.undo=j.undo;undoBtn();applyFlags([F.f.id],kw);paintFile();if('grade' in kw)toast(kw.grade?`→ ${kw.grade}（${GN[kw.grade]}）`:'→ 未分級')}return j}
function fileMenu(){const f=F.f,T=f.arch_targets||[];
  menu(f.name,[...(labOn('caption')?[['📋 複製上傳文案',async()=>{const j=await api(U('/api/new',{a:'caption',id:f.id}));try{await navigator.clipboard.writeText(j.text||'');toast('📋 已複製：'+(j.text||'').slice(0,40))}catch(e){prompt('長按複製：',j.text||'')}}]]:[]),...(labOn('caption')&&S.state&&S.state.cap2?[['📋 複製上傳文案（第二組範本）',async()=>{const j=await api(U('/api/new',{a:'caption',id:f.id,n:2}));try{await navigator.clipboard.writeText(j.text||'');toast('📋 已複製：'+(j.text||'').slice(0,40))}catch(e){prompt('長按複製：',j.text||'')}}]]:[]),...(labOn('file_hist')?[['📜 這部的紀錄',()=>fileHist(f)]]:[]),...T.map(t=>[`📦 歸檔到 ${t.name}`,()=>op(t.kind,[f.id],true)]),['🗑 移到待刪',()=>op('trash',[f.id],true)],['⭐ 收藏（複製到收藏資料夾）',()=>op('fav',[f.id])],...(S.state&&S.state.lab&&S.state.lab.copy_to?[['📤 複製到上傳資料夾',()=>copyTo([f.id])],...(f.cut_n?[['📤 剪好的片段複製到上傳資料夾',()=>copyTo([f.id],1)]]:[]),[f.up_t>0?'↩ 取消「已上傳」標記':'📤 標成「已上傳」',async()=>{const on=f.up_t>0?0:1;const j=await api('/api/new',{a:'up_mark',ids:[f.id],on});f.up_t=on?Date.now()/1000:0;toast(j.message||'');try{loadList(true)}catch(e){}}]]:[]),
   ['🔁 加入轉檔',()=>op('conv',[f.id])],['🧪 試轉 10 秒（看會變多大、畫質）',()=>trial(f)],['⚡ 先做預覽圖',()=>op('front',[f.id])],['🔁 重做預覽圖（精準）',()=>op('redo_precise',[f.id])],
   ...(f.th_running?[['⏹ 停掉這部正在做的預覽圖（跳過，晚點再做）',()=>op('thumb_cancel',[f.id])]]:[]),
   ...(f.cut_n?[['❌ 刪除已剪輯的原檔（資源回收筒）',()=>op('delete_original',[f.id],true)]]:[]),['🧬 找跟這部畫面相似的',async()=>{await closeAll();location.hash='tool/like';setTimeout(()=>likeOf(f.id),400)}],
   ['🚫 排除所在資料夾',()=>{if(confirm('排除「'+f.folder+'」？之後不再掃描這個資料夾'))api('/api/op',{kind:'exclude_folder',folder:f.folder,ids:[]}).then(j=>j.message&&toast(j.message))}]])}
async function trial(f){const r=await api('/api/conv2',{a:'trial',ids:[f.id],secs:10});if(!r.ok)return toast(r.message||'不能試轉');toast('🧪 試轉中…（10 秒的片段，大約 10～60 秒）',4000);
  for(let i=0;i<240;i++){await new Promise(z=>setTimeout(z,1500));const j=await api(U('/api/conv2',{a:'trial'}));const J=j.job;if(!J||J.run)continue;
    if(!J.res)return toast(J.msg||'試轉失敗',8000);const x=J.res;
    alert(`🧪 試轉 ${(+x.secs).toFixed(1)} 秒：${x.name}\n\n整部推估：${fmtB(x.est)}（原檔 ${fmtB(x.osz)}，變成 ${Math.round((x.ratio||0)*100)}%${x.kn?'；照之前 '+x.kn+' 筆校正':''}）\n畫質 SSIM：${(x.ssim||0).toFixed(3)}${x.ssim>=0.985?' ✔':' ⚠'}\n${x.w}×${x.h} · ${x.kbps} kbps（原檔 ${x.src_kbps} kbps）· ${x.enc}\n速度 ${(x.speed||0).toFixed(2)}× · 整部大約要 ${fmtT(x.full_time||0)}`);return}
  toast('試轉還沒好，晚點在 LOG 看結果',6000)}
function vbox(title,src,t,extra){const old=$('#vov');const reuse=old?replaceLayer(old):false;
  const v=document.createElement('div');v.id='vov';v.className='vbox';
  v.innerHTML=`<div class="vw"><div class="vh"><b>${esc(title)}</b>${extra||''}<button class="pill" data-x>✕</button></div><div class="vst"><video id="vid" controls playsinline autoplay preload="metadata" src="${src}#t=${Math.max(0,Math.floor(t||0))}"></video><div class="swp"><b></b><small></small><i><u></u></i></div></div>
  <div class="row"><button class="pill" data-r>1×</button><button class="pill" data-fs="-1" title="暫停，往回 1 格">◀1格</button><button class="pill" data-fs="1" title="暫停，往前 1 格">1格▶</button><button class="pill" data-ab title="A-B 重複：第 1 下起點、第 2 下終點、第 3 下取消">🔁 A-B</button>${swMax()?`<span class="vtip" style="margin:0">在畫面上按住左右滑＝畫面跟著走（滑得快、滑得長＝跳得遠，一次最多 ${swFmtMax(swMax())}；慢慢滑＝細調）</span>`:''}</div></div>`;
  document.body.appendChild(v);const vid=$('#vid',v);const close=layer(v,()=>{try{vid.pause();vid.removeAttribute('src');vid.load()}catch(e){}},reuse);
  ['click','pointerdown','touchstart','dblclick'].forEach(ev=>$('.vw',v).addEventListener(ev,e=>e.stopPropagation()));
  v.addEventListener('click',e=>{if(e.target===v)close()});$('[data-x]',v).onclick=()=>close();
  vid.addEventListener('error',async()=>{try{const u=new URL(src,location.href);const q=Object.fromEntries(u.searchParams);if(!u.pathname.endsWith('/api/video'))return;
    const code=vid.error?vid.error.code:0;const j=await api(U('/api/vinfo',Object.assign(q,{err:code})));
    const box=document.createElement('div');box.className='mu';box.style.cssText='color:#fff;background:#3a1d1d;padding:8px 10px;border-radius:8px;margin-top:6px;font-size:13px';
    box.innerHTML='⚠ 手機播不了（錯誤碼 '+code+'）'+(j.exists?'：'+esc((j.codec||'?')+' '+(j.pix||'')+' '+(j.w||'')+'×'+(j.h||'')+' · 標記 '+(j.tag||'?')):'')+'<br>'+(j.why||[]).map(esc).join('<br>')+'<br><span style="opacity:.8">（已記在電腦的 LOG；電腦上的播放器可以播）</span>';
    $('.vw',v).appendChild(box)}catch(e){}});
  vbSwipe($('.vst',v),vid);const R=[1,1.5,2,3,0.5];let ri=Math.max(0,R.indexOf(+LS.get('vrate',1)));$('[data-r]',v).onclick=e=>{ri=(ri+1)%R.length;vid.playbackRate=R[ri];LS.set('vrate',R[ri]);e.target.textContent=R[ri]+'×'};
  try{vid.muted=!!LS.get('vmute',false);vid.volume=Math.min(1,Math.max(0,+LS.get('vvol',1)));if(R[ri]!==1){vid.playbackRate=R[ri];$('[data-r]',v).textContent=R[ri]+'×'}vid.addEventListener('loadedmetadata',()=>{try{vid.playbackRate=R[ri]}catch(x){}});vid.addEventListener('volumechange',()=>{LS.set('vmute',vid.muted);LS.set('vvol',vid.volume)})}catch(e){}   // V0.4.48 記住音量／靜音／速度
  {let A=null,Bt=null;const ab=$('[data-ab]',v),fm=x=>Math.floor(x/60)+':'+String(Math.floor(x%60)).padStart(2,'0');   // V0.3.67 🔁 A-B 重複（跟電腦 R 鍵一樣）
   ab.onclick=()=>{if(A==null){A=vid.currentTime;ab.textContent='🔁 A '+fm(A)+' → 按終點';ab.classList.add('acc')}else if(Bt==null){if(vid.currentTime<=A+0.3){toast('終點要在起點後面');return}Bt=vid.currentTime;ab.textContent='🔁 '+fm(A)+'–'+fm(Bt)+' ✕';vid.currentTime=A;vid.play().catch(()=>{})}else{A=Bt=null;ab.textContent='🔁 A-B';ab.classList.remove('acc')}};
   vid.addEventListener('timeupdate',()=>{if(A!=null&&Bt!=null&&vid.currentTime>=Bt){vid.currentTime=A}})}
  $$('[data-fs]',v).forEach(b=>b.onclick=()=>{try{vid.pause();vid.currentTime=Math.max(0,Math.min((vid.duration||1e9)-0.01,vid.currentTime+(+b.dataset.fs)/(+(F.f&&F.f.fps)||30)))}catch(e){}});   // V0.3.68 ◀▶ 一格一格看（跟電腦 D／G 一樣）
  vid.play().catch(()=>{});return v}
/* ================= 影片上左右滑動快轉／倒退（照 TikLive：滑得快、滑得長＝跳得遠，慢慢滑＝細調，放開才跳；一次最多＝設定「左右滑動一次最多」，預設 10 分鐘） ================= */
function swMax(){const v=LS.get('swipeMax',600);return +v||0}
function swFmtMax(m){return m>=60?(m/60)+' 分鐘':m+' 秒'}
function vbSwipe(st,vid){if(!st||!vid)return;let g=null;const box=$('.swp',st);
  st.addEventListener('pointerdown',e=>{const max=swMax();if(!max||!vid.duration||e.button>0)return;
    const r=st.getBoundingClientRect();if(e.clientY>r.bottom-56)return;                       /* 最下面是播放器自己的進度列，不搶 */
    g={id:e.pointerId,x0:e.clientX,y0:e.clientY,x:e.clientX,t:performance.now(),base:vid.currentTime,acc:0,on:false,max,play:!vid.paused}});
  st.addEventListener('pointermove',e=>{if(!g||e.pointerId!==g.id)return;const dx=e.clientX-g.x0,dy=e.clientY-g.y0;
    if(!g.on){if(Math.abs(dy)>14&&Math.abs(dy)>Math.abs(dx)){g=null;return}if(Math.abs(dx)<14||Math.abs(dx)<Math.abs(dy)*1.3)return;
      g.on=true;try{st.setPointerCapture(e.pointerId)}catch(x){}g.x=e.clientX;g.t=performance.now();box.style.display='block';try{vid.pause()}catch(x){}}
    const now=performance.now(),ddx=e.clientX-g.x,dt=Math.max(8,now-g.t);g.x=e.clientX;g.t=now;
    const W=Math.max(200,st.getBoundingClientRect().width),sp=Math.abs(ddx)/dt,kk=Math.min(1,Math.max(0.12,(sp-0.05)/1.3));   /* 慢＝細、快＝遠 */
    g.acc=Math.max(-g.max,Math.min(g.max,g.acc+ddx/W*g.max*1.6*kk));
    const dur=vid.duration||0,tgt=Math.max(0,Math.min(Math.max(0,dur-0.5),g.base+g.acc)),d=tgt-g.base,a=Math.abs(Math.round(d));
    $('b',box).textContent=(d<0?'⏪ −':'⏩ +')+(a>=60?Math.floor(a/60)+':'+String(a%60).padStart(2,'0'):a+' 秒');$('small',box).textContent=fmtT(tgt)+' / '+fmtT(dur);
    $('u',box).style.width=Math.round(Math.abs(g.acc)/g.max*100)+'%';
    if(now-(g.ls||0)>150&&!vid.seeking){g.ls=now;try{if(vid.fastSeek)vid.fastSeek(tgt);else vid.currentTime=tgt}catch(x){}}   /* 拖著不放：畫面跟著走 */
    e.preventDefault()});
  st.addEventListener('pointerup',e=>{if(!g||e.pointerId!==g.id)return;const was=g;g=null;if(!was.on)return;box.style.display='none';st._swiped=performance.now();
    if(vid.duration)vid.currentTime=Math.max(0,Math.min(vid.duration-0.5,was.base+was.acc));if(was.play)vid.play().catch(()=>{})});
  st.addEventListener('pointercancel',()=>{if(g&&g.on){box.style.display='none';if(g.play)vid.play().catch(()=>{})}g=null});
  st.addEventListener('click',e=>{if(performance.now()-(st._swiped||0)<350){e.stopPropagation();e.preventDefault()}},true)}
function playList(R,i){R=R.filter(r=>r&&r.th_state!==undefined);if(!R.length)return toast('清單是空的');if(i>=R.length)return toast('▶ 連播播完了');const f=R[i];   // V0.2.90 ▶ 連播
  const v=vbox(`▶ ${i+1}／${R.length}　${f.name}`,U('/api/video',{id:f.id}),0,i+1<R.length?'<button class="pill" data-pnext>⏭ 下一部</button>':'');bmBar(v,f.id);
  const vid=$('video',v);let gone=false;const next=()=>{if(gone)return;gone=true;playList(R,i+1)};vid.addEventListener('ended',()=>setTimeout(next,600));const nb=$('[data-pnext]',v);if(nb)nb.onclick=next}
async function fileHist(f){const j=await api(U('/api/new',{a:'hist',id:f.id}));if(!j.ok)return;const d=document.createElement('div');d.className='sheet';   // V0.2.98 📜
  d.innerHTML=`<div><div class="row"><h3 class="grow" style="margin:0">📜 ${esc(f.name)}</h3><button class="pill" data-x>✕</button></div>${(j.rows||[]).map(h=>`<div class="si"><small class="mu">${h.t?new Date(h.t*1000).toLocaleString():''}</small><br><b>${esc(h.what)}</b>${h.detail?'<br><small style="word-break:break-all">'+esc(h.detail)+'</small>':''}</div>`).join('')||'<div class="mu">還沒有紀錄</div>'}</div>`;
  document.body.appendChild(d);const close=layer(d);$('[data-x]',d).onclick=()=>close()}
async function bmBar(v,fid){if(!(S.state&&S.state.lab&&S.state.lab.bookmarks)||!fid)return;const vid=$('video',v);if(!vid)return;   // V0.2.41 🔖 時間書籤
  const bar=document.createElement('div');bar.className='row';bar.style.cssText='flex-wrap:wrap;gap:4px;margin-top:6px';$('.vw',v).appendChild(bar);
  const dur=(F.f&&F.f.id===fid&&F.f.dur)||((S.rows||[]).find(r=>r.id===fid)||{}).dur||0;   // V0.2.79 書籤位置條
  const paint=L=>{bar.innerHTML=(dur&&(L||[]).length?`<div style="position:relative;width:100%;height:12px;background:rgba(127,127,127,.25);border-radius:6px">${L.map(([t,n])=>`<i data-bt="${t}" title="${esc(n||'')}" style="position:absolute;top:0;left:calc(${(t/dur*100).toFixed(2)}% - 5px);width:10px;height:12px;background:#ffc94d;border-radius:3px;cursor:pointer"></i>`).join('')}</div>`:'')+`<button class="pill acc" data-bma>🔖 加在這裡</button><button class="pill" data-bmc title="加書籤，順便剪這裡前 5 秒～後 10 秒">✂ 剪這裡</button>`+(L||[]).map(([t,n])=>`<button class="pill" data-bt="${t}">▶ ${fmtT(t)}${n?' '+esc(n):''}</button><button class="pill er" data-bd="${t}" style="padding:2px 6px">✕</button>`).join('')};
  let j={};try{j=await api(U('/api/new',{a:'bm',id:fid}),undefined,{quiet:true})}catch(e){}paint(j.rows);
  bar.onclick=async e=>{{const c=e.target.closest('[data-bmc]');if(c){e.stopPropagation();const t=vid.currentTime||0;await api('/api/new',{a:'bm_add',id:fid,t,note:'✂'});const r=await api('/api/new',{a:'bm_clip',id:fid,t,before:5,after:10});toast(r.ok?`✂ ${fmtT(Math.max(0,t-5))}～${fmtT(t+10)} 排進初剪了`:(r.message||'沒排進去'));try{const jj=await api(U('/api/new',{a:'bm',id:fid}),undefined,{quiet:true});paint(jj.rows)}catch(x){}return}}   // V0.4.19 ✂ 剪這裡
  const b=e.target.closest('[data-bma],[data-bt],[data-bd]');if(!b)return;e.stopPropagation();
    if(b.dataset.bt!==undefined){vid.currentTime=+b.dataset.bt;vid.play().catch(()=>{});return}
    if(b.dataset.bd!==undefined){const r=await api('/api/new',{a:'bm_del',id:fid,t:+b.dataset.bd});if(r.ok)paint(r.rows);return}
    const t=vid.currentTime||0;const n=prompt(`🔖 ${fmtT(t)} 的說明（可以留空）`,'');if(n===null)return;const r=await api('/api/new',{a:'bm_add',id:fid,t,note:n});if(r.ok){paint(r.rows);toast('🔖 '+fmtT(t))}else toast(r.message||'沒加成')}}
function snapBtn(v,fid){const vid=$('video',v);if(!vid)return;const b=document.createElement('button');b.className='pill';b.textContent='📷 截圖';b.style.margin='6px 6px 0 0';$('.vw',v).appendChild(b);   // V0.3.34 跟電腦 Ctrl+E 一樣
  b.onclick=async e=>{e.stopPropagation();const r=await api('/api/new',{a:'snap',id:fid,t:vid.currentTime||0});toast(r.message||'',5000)}}
function scnBtns(v,f){if(!labOn('scenes'))return;const vid=$('video',v);if(!vid)return;   // V0.3.37 🎬 上／下一個換場景
  api(U('/api/new',{a:'scenes',id:f.id}),undefined,{quiet:true}).then(j=>{const L=((j&&j.rows)||[]).map(b=>b*(f.th_step||2)).sort((a,b)=>a-b);if(!L.length||!document.body.contains(v))return;
    const w=document.createElement('span');w.innerHTML='<button class="pill" data-sp>⏮ 上一個場景</button><button class="pill" data-sn>下一個場景 ⏭</button>';w.style.cssText='display:inline-flex;gap:6px;margin:6px 6px 0 0';$('.vw',v).appendChild(w);
    const go=d=>{const c=vid.currentTime||0;const t=d>0?L.find(x=>x>c+1):[...L].reverse().find(x=>x<c-2);if(t==null)return toast('🎬 沒有了',1000);vid.currentTime=t;toast('🎬 '+fmtT(t),900)};
    $('[data-sp]',w).onclick=e=>{e.stopPropagation();go(-1)};$('[data-sn]',w).onclick=e=>{e.stopPropagation();go(1)}}).catch(()=>{})}
function play(f,t){const v=vbox(f.name,U('/api/video',{id:f.id}),t);bmBar(v,f.id);scnBtns(v,f);snapBtn(v,f.id);
  if(S.state&&S.state.lab&&S.state.lab.resume){const vid=$('video',v);let last=t||0,cur=t||0;vid.addEventListener('timeupdate',()=>{if(vid.currentSrc&&vid.readyState>0)cur=vid.currentTime});const save=()=>{const t=cur;if(Math.abs(t-last)<3)return;last=t;f.last_pos=t;api('/api/new',{a:'pos',id:f.id,t},{quiet:true}).then(r=>{if(r&&r.ok)f.last_pos=r.t}).catch(()=>{})};   // V0.2.71 ⏯ 續播
    vid.addEventListener('timeupdate',()=>{if(Date.now()-(vid._ps||0)>10000){vid._ps=Date.now();save()}});vid.addEventListener('pause',save);
    const mo=new MutationObserver(()=>{if(!document.body.contains(v)){try{save()}catch(e){}mo.disconnect()}});mo.observe(document.body,{childList:true})}if(f.playable===false)$('.vw',v).insertAdjacentHTML('afterbegin','<p class="mu" style="color:#fff">這個格式手機可能播不了（例如 AVI、FLV、MPEG-2）；轉成 MP4 後就可以。</p>')}
function preview(i){const f=F.f;if(!f)return;const t=i*F.gs;const v=vbox(`${fmtT(t)}　${f.name}`,U('/api/video',{id:f.id}),Math.max(0,t-2),`<button class="pill" data-psel>${F.sel.has(i)?'✔ 已選取':'選取這張'}</button>${(F.sc||[]).length?'<button class="pill" data-pscn>🎬 選這整個場景</button>':''}`);bmBar(v,f.id);snapBtn(v,f.id);
  {const sb=$('[data-pscn]',v);if(sb)sb.onclick=()=>{const {m,n}=tileCount(),b=i*m,C=(F.sc||[]).slice().sort((x,y)=>x-y),a=Math.max(0,...C.filter(x=>x<=b)),z=Math.min(f.th_n||0,...C.filter(x=>x>b));let k=0;for(let j=Math.floor(a/m);j<=Math.min(n-1,Math.ceil(z/m)-1);j++){if(!F.sel.has(j)){F.sel.add(j);k++}}drawSel();cutBar();toast(`🎬 選了這個場景（${k} 格）`)}}   // V0.3.10
  const b=$('[data-psel]',v);b.onclick=()=>{const on=!F.sel.has(i);on?F.sel.add(i):F.sel.delete(i);b.textContent=on?'✔ 已選取':'選取這張';drawSel();cutBar()}}
function playOut(id,name){vbox('✂ '+name,U('/api/video',{id,out:name}),0)}
async function playAt(fid,t){const j=await api(U('/api/file',{id:fid}));if(j.ok)play(j.file,Math.max(0,t-2))}

// ---------------------------------------------------------------- 🗂 分級（一部一部看預覽圖，分 S／A／E／F，分完自動下一部）
async function viewRv(){const gen=S.gen;
  V().innerHTML=`<div class="sh">🗂 分級：還沒分級的影片，一部一部看預覽圖、按 S／A／E／F，分完自動跳下一部</div>
   <div class="panel"><div class="row"><span class="grow">範圍：<b>📁 ${esc(S.folder?S.folder.split(/[\\/]/).filter(Boolean).pop():'全部影片')}</b>　排序：<b>${esc((SORTS.find(x=>x[0]===S.sort)||['',''])[1])}</b></span><button class="pill" onclick="location.hash='fx'">換資料夾（檔案總管）</button></div>
   <div class="mu" id="rvn" style="margin:8px 0">讀取中…</div><div class="row"><button class="pill acc" id="rvgo" disabled>▶ 開始分級</button><button class="pill" id="rvrand" disabled>🎲 隨機順序</button></div></div>
   <div class="mu">S＝無條件保存　A＝保存　E＝觀察　F＝刪除　—＝跳過。分級中也可以點圖片選片段直接初剪；按返回鍵回到這裡。</div>`;
  const j=await api(U('/api/list',{folder:S.folder,flt:'nograde',sort:S.sort,sub:S.sub?1:0,off:0,lim:500}));if(gen!==S.gen||!j.ok||!$('#rvn'))return;
  const ids=(j.rows||[]).filter(r=>r.th_state===2).map(r=>r.id);$('#rvn').textContent=`還沒分級 ${j.total.toLocaleString()} 部（預覽圖好了的前 ${ids.length} 部先排進來）`;
  $('#rvgo').disabled=$('#rvrand').disabled=!ids.length;$('#rvgo').onclick=()=>openFile(ids[0],{review:{ids,i:0}});
  $('#rvrand').onclick=()=>{const a=ids.slice();for(let i=a.length-1;i>0;i--){const k=Math.floor(Math.random()*(i+1));[a[i],a[k]]=[a[k],a[i]]}openFile(a[0],{review:{ids:a,i:0}})}}

// ---------------------------------------------------------------- 👤 人物
const PP={q:'',hidden:false,named:false,sel:new Set(),selMode:false,iv:null};
function viewPpl(){
  V().innerHTML=`<div class="panel" id="fst"><div class="mu">讀取中…</div></div>
   <div class="tools"><input class="search" id="pq" placeholder="🔍 找名字" value="${esc(PP.q)}"><button class="pill" id="pnamed" style="height:40px">${PP.named?'✔ ':''}有名字的</button><button class="pill" id="psel" style="height:40px">☑ 多選</button></div>
   <div class="row" style="margin:6px 0"><span class="mu grow" id="pcnt"></span><button class="pill" id="phid">${PP.hidden?'✔ ':''}顯示隱藏的</button></div><div class="pgr" id="pgr"></div>
   <div class="mu" style="margin-top:10px">點一個人：看他出現的所有影片和時間點、幫他取名字。長按＝多選（合併成同一個人、隱藏）。</div>`;
  let qt;$('#pq').oninput=e=>{clearTimeout(qt);qt=setTimeout(()=>{PP.q=e.target.value.trim();loadPeople()},350)};
  $('#pnamed').onclick=()=>{PP.named=!PP.named;viewPpl()};$('#phid').onclick=()=>{PP.hidden=!PP.hidden;viewPpl()};$('#psel').onclick=()=>pSel(!PP.selMode);
  faceStatus();loadPeople();clearInterval(PP.iv);PP.iv=setInterval(()=>{if(!$('#fst')){clearInterval(PP.iv);return}if(!document.hidden)faceStatus()},4000)}
async function faceStatus(){const el=$('#fst');if(!el)return;let j;try{j=await api('/api/faces',undefined,{quiet:true})}catch(e){return}if(!j.ok||!$('#fst')){if(j.message)el.innerHTML=`<div class="mu">${esc(j.message)}</div>`;return}const s=j.st;const pc=s.total?Math.round(s.done*100/s.total):0;
  el.innerHTML=`<div class="row"><b class="grow">${s.running?'<span style="color:var(--green)">● 人臉分類跑中</span>':s.state==='error'?'<span style="color:var(--red)">● 人臉分類出錯了</span>':'<span style="color:var(--sub)">● 人臉分類沒在跑</span>'}</b>
   ${s.running?'<button class="pill wa" data-fa="stop">⏹ 停止</button>':'<button class="pill acc" data-fa="start">▶ 開始</button><button class="pill" data-fa="recluster">🔁 重新分群</button>'}<button class="pill" data-fa="cfg">⚙</button></div>
   <div class="mu" style="margin-top:6px">影片 ${(s.done||0).toLocaleString()}／${(s.total||0).toLocaleString()}（${pc}%）· ${s.people||0} 個人（有名字 ${s.named||0}）</div>
   <div class="pg" style="margin:6px 0"><i style="width:${pc}%"></i></div><div class="mu">${s.running&&s.eta?'還要約 '+eta(s.eta)+' · ':''}${esc(s.provider||'')}${s.msg?' · '+esc(String(s.msg).slice(0,90)):''}${s.err?` · <span style="color:var(--red)">${esc(String(s.err).slice(0,120))}</span>`:''}</div>`;
  el.onclick=e=>{const b=e.target.closest('[data-fa]');if(!b)return;const a=b.dataset.fa;if(a==='cfg'){S.scat='faces';location.hash='set';return}faceCtl(a)};
  if(PP._wasRun&&!s.running)loadPeople();PP._wasRun=s.running}
async function faceCtl(a){const j=await api('/api/faces',{a});toast(j.message||'');setTimeout(faceStatus,800)}
async function loadPeople(){const j=await api(U('/api/people',{q:PP.q,hidden:PP.hidden?1:0}));if(!j.ok||!$('#pgr'))return;
  let L=j.people||[];if(PP.named)L=L.filter(p=>p.name);
  $('#pcnt').textContent=j.total?`${L.length} 個人${PP.named?'（有名字的）':''}`:'還沒有結果：按上面「▶ 開始」（第一次要先在電腦的 👤 人物 → ⚙ 設定 檢查環境、安裝套件）';
  $('#pgr').innerHTML=L.map(p=>`<div class="pc2 ${p.name?'':'un'} ${p.hidden?'hid':''} ${PP.sel.has(p.id)?'sel':''}" data-p="${p.id}"><div class="fav" style="${faceCSS(p.face)}"></div><b>${esc(p.name||'未命名 #'+p.id)}</b><small>${p.n_files} 部 · ${p.n_faces} 張${p.auto_cat?' · 📦':''}</small></div>`).join('');
  $$('#pgr .pc2').forEach(c=>{let lp=null,fired=false;c.addEventListener('pointerdown',e=>{if(e.pointerType==='mouse')return;fired=false;clearTimeout(lp);lp=setTimeout(()=>{fired=true;vib();if(!PP.selMode)pSel(true);PP.sel.add(+c.dataset.p);c.classList.add('sel');pBar()},550)});
    c.addEventListener('pointerup',()=>clearTimeout(lp));c.addEventListener('pointercancel',()=>clearTimeout(lp));c.oncontextmenu=e=>e.preventDefault();
    c.onclick=()=>{if(fired){fired=false;return}const id=+c.dataset.p;if(PP.selMode){PP.sel.has(id)?PP.sel.delete(id):PP.sel.add(id);c.classList.toggle('sel');pBar()}else location.hash='person/'+id}})}
let PSELC=null;
function pSel(on){if(on===PP.selMode)return;if(on){PP.selMode=true;const close=fb=>{if(!PP.selMode)return Promise.resolve();PP.selMode=false;PSELC=null;PP.sel.clear();$$('#pgr .pc2.sel').forEach(c=>c.classList.remove('sel'));pBar();return fb===true?Promise.resolve():bkDone(close)};PSELC=close;bkPush(close)}else if(PSELC)PSELC();pBar();const b=$('#psel');if(b)b.classList.toggle('on',PP.selMode)}
function pBar(){let b=$('#pbar');if(!PP.selMode){b&&b.remove();return}if(!b){b=document.createElement('div');b.id='pbar';b.className='vgAct';document.body.appendChild(b)}
  b.innerHTML=`<span class="mu" style="flex:none">已選 <b>${PP.sel.size}</b> 個</span><button class="pill acc" onclick="pMerge()">🔗 合併成同一個人</button><button class="pill" onclick="pHide()">🙈 隱藏</button><button class="pill" onclick="pSel(false)">結束</button>`}
async function pMerge(){const ids=[...PP.sel];if(ids.length<2)return toast('至少選 2 個');const all=await api(U('/api/people',{hidden:1}));const P=(all.people||[]).filter(p=>ids.includes(p.id));if(!P.length)return;
  const tgt=(P.find(p=>p.name)||P.slice().sort((a,b)=>b.n_faces-a.n_faces)[0]);if(!confirm(`合併成「${tgt.name||'未命名 #'+tgt.id}」？（${ids.length} 群 → 1 個人）`))return;
  const j=await api('/api/person',{a:'merge',id:tgt.id,ids:ids.filter(x=>x!==tgt.id)});toast(j.message||'');S.people=null;pSel(false);loadPeople()}
async function pHide(){for(const id of PP.sel)await api('/api/person',{a:'hide',id,v:1});toast('已隱藏（「顯示隱藏的」可以找回來）');pSel(false);loadPeople()}
async function viewPerson(id){const gen=S.gen;
  V().innerHTML='<div class="empty">讀取中…</div>';const j=await api(U('/api/person',{id}));if(gen!==S.gen)return;if(!j.ok){V().innerHTML=`<div class="tlh"><button class="back" onclick="history.back()">‹</button><b>人物</b></div><div class="empty">${esc(j.message||'找不到')}</div>`;return}
  const p=j.person;const nm=p.name||'未命名 #'+p.id;const sel=new Set();
  V().innerHTML=`<div class="tlh"><button class="back" onclick="history.back()">‹</button><div class="fav" style="width:46px;height:46px;${faceCSS(p.samples&&p.samples[0])}"></div><b class="grow">${esc(nm)}</b><span class="mu">${p.files.length} 部 · ${p.n_faces} 張臉</span></div>
   <div class="panel"><div class="tools"><input class="search" id="pnm" placeholder="幫這個人取名字（之後新影片長得像就自動套用）" value="${esc(p.name||'')}"><button class="pill acc" id="pnms" style="height:40px">存</button></div>
    <div class="row" style="margin-top:10px"><label class="tg"><input type="checkbox" id="pac" ${p.auto_cat?'checked':''}><i></i></label><span class="grow">新影片自動歸到分類資料夾「${esc(p.name||'名字')}」</span></div>
    <div class="row" style="margin-top:8px"><button class="pill" id="pflt">📁 檔案總管只看他</button><button class="pill" id="pcat">📦 現在歸類他的影片</button><button class="pill" id="phide">${p.hidden?'🙉 取消隱藏':'🙈 隱藏'}</button></div></div>
   <div class="sh">臉（點選認錯的 → 不是他）<span class="grow"></span><button class="pill er" id="pnot" disabled>🚫 不是他</button></div><div class="fstrip" id="pfs">${(p.samples||[]).map(f=>`<div class="fav" data-f="${f.id}" style="${faceCSS(f)}" title="${fmtT(f.t)}"></div>`).join('')}</div>
   <div class="sh">出現的影片（點時間＝從那裡播放）</div><div class="panel" id="pfl">${p.files.map(f=>`<div class="pfile" data-fid="${f.file_id}"><div class="th2" style="${f.face?tileCSS(f.file_id,f.face.k,f.th_cols||10,f.th_rows||10):''}"></div><div class="grow"><b style="word-break:break-all">${esc(f.name)}</b>
    <div class="mu">${f.faces} 次 · ${f.dur?fmtT(f.dur):'—'} · ${fmtB(f.size)}${f.grade?' · '+f.grade:''}${f.arch?' · 📦'+esc(f.arch):''}</div><div class="tchips">${f.times.slice(0,40).map(t=>`<button data-t="${t}">${fmtT(t)}</button>`).join('')}${f.times.length>40?`<span class="mu">…還有 ${f.times.length-40} 個</span>`:''}</div>
    <div class="row" style="margin-top:5px"><button class="pill" data-open>開啟</button><button class="pill" data-rm>這部不是他</button></div></div></div>`).join('')||'<div class="empty">沒有</div>'}</div>`;
  $('#pnms').onclick=async()=>{const r=await api('/api/person',{a:'rename',id:p.id,name:$('#pnm').value.trim()});toast(r.message||(r.ok?'✔ 已儲存':''));S.people=null;if(r.id&&r.id!==p.id)location.replace('#person/'+r.id);else viewPerson(p.id)};
  $('#pnm').onkeydown=e=>{if(e.key==='Enter')$('#pnms').click()};
  $('#pac').onchange=async e=>{if(e.target.checked&&!p.name){toast('先取名字');e.target.checked=false;return}if(e.target.checked&&!confirm(`之後找到「${p.name}」的影片會自動搬到分類資料夾「${p.name}」（操作紀錄可以搬回）。確定？`)){e.target.checked=false;return}
    const r=await api('/api/person',{a:'auto_cat',id:p.id,v:e.target.checked});toast(r.ok?'✔ 已儲存':(r.message||'沒存到'))};
  $('#pcat').onclick=async()=>{if(!p.name)return toast('先取名字');if(!confirm(`把「${p.name}」的影片搬到分類資料夾「${p.name}」？（操作紀錄可以搬回）`))return;const r=await api('/api/person',{a:'apply_cat',id:p.id});toast(r.message||'')};
  $('#phide').onclick=async()=>{await api('/api/person',{a:'hide',id:p.id,v:!p.hidden});viewPerson(p.id)};
  $('#pflt').onclick=()=>{S.flt='person:'+p.id;S.folder='';saveView();S.people=null;location.hash='fx'};
  $('#pfs').onclick=e=>{const f=e.target.closest('[data-f]');if(!f)return;const i=+f.dataset.f;sel.has(i)?sel.delete(i):sel.add(i);f.classList.toggle('sel');$('#pnot').disabled=!sel.size;$('#pnot').textContent=sel.size?`🚫 不是他（${sel.size}）`:'🚫 不是他'};
  $('#pnot').onclick=async()=>{const r=await api('/api/person',{a:'not_me',id:p.id,faces:[...sel]});toast(r.message||'');viewPerson(p.id)};
  $('#pfl').onclick=async e=>{const row=e.target.closest('.pfile');if(!row)return;const fid=+row.dataset.fid;const t=e.target.closest('[data-t]');
    if(t){playAt(fid,+t.dataset.t);return}if(e.target.closest('[data-open]')){openFile(fid);return}
    if(e.target.closest('[data-rm]')){if(!confirm('這部不是他？（拿掉這部裡被算成他的臉）'))return;const r=await api('/api/person',{a:'rm_file',id:p.id,file_id:fid});toast(r.message||'');viewPerson(p.id)}}}

// ---------------------------------------------------------------- 工具（照 TikLive：卡片）
const TOOLS=[['重複與相似',[['dupes','🔍','找重複的影片','大小一樣、或長度一樣大小差不多'],['sim','🧬','找畫面相似的','看預覽圖比對：轉過檔、縮小、重複下載都找得到'],['like','🎯','跟某一部相似的','從影片頁「⋯」進來']]],
  ['整理',[['rand','🎲','隨機抽一部沒看過的','不知道從哪部開始'],['stats','📊','整理成果統計','省了多少空間、每天分級幾部'],['health','🩺','影片庫健康檢查','壞掉、超短、沒畫面的']]],
  ['HotZone',[['hz','🔥','HotZone','搬檔佇列、熱區、索引、硬碟協調員']]],
  ['🆕 新功能',[['report','📈','分級報表','今天／7 天分級、剪輯、省下的空間、14 天長條圖'],['cre','👥','依作者／主播','從檔名猜作者：每個人幾部、分級了多少'],['sched','🕑','背景工作時段','轉檔、預覽圖…只在幾點到幾點做'],['csv','📤','清單匯出 CSV','檔案總管目前的資料夾＋篩選，存成 Excel 表格'],['space','💽','硬碟空間地圖','每顆硬碟 S／A／E／F／未分級 各佔多少、還剩多少'],['empty','🧹','空資料夾清理','找出一個檔都沒有的資料夾，勾選刪掉'],['week','📆','每週回顧','這 7 天分了幾部（跟前 7 天比）、上傳、剪輯、省下的空間'],['unplug','🔌','拔硬碟前看一下','每顆硬碟現在有沒有在讀寫，✅ 才拔'],['bmall','🔖','所有時間書籤','每部影片標的書籤一次列出，一按從那裡開始播'],['spr','⏱','分級衝刺','倒數 10～45 分鐘專心分級，看分了幾部、有沒有破紀錄'],['upb','📋','上傳看板','還沒傳 → 排隊中 → 今天傳好的，一按排進複製'],['upold','🧺','清理上傳資料夾','上傳資料夾裡放很久的複本丟到資源回收筒'],['mon','📅','依月份','每個月幾部、分級了多少，點一下只看那個月'],['pcs','🖥','硬碟在哪台電腦','每顆硬碟的紀錄最後是哪台電腦寫的'],['rule','⚡','規則分級','還沒分級的，用條件一次標好（可預覽、可復原）'],['flow','🚀','建議的新流程','怎麼把這些新功能串起來用（一步一步）'],['find','⌘','快速找','打幾個字找影片、資料夾、功能（跟電腦 Ctrl+K 一樣）'],['fprog','📂','各資料夾分級進度','哪個資料夾還有最多可以審的，點了直接去'],['chk','🩺','新功能自我檢查','資料庫、設定、上傳資料夾有沒有問題']]],
  ['電腦',[['explore','🗺','檔案總覽','像 Everything 搜尋＋哪個資料夾最大、能省多少；長按資料夾 → 轉檔'],['conv','🔁','轉檔工作區','非 MP4、H.264 → H.265；轉檔中／轉檔完成／刪原檔'],['learn','📈','滾動式參數','🎯 自動轉檔累積的經驗：每一類用哪種方式、CQ、抽查'],['ops','📒','操作紀錄','30 天：搬到哪、原本叫什麼，可以搬回'],['log','📜','LOG','錯誤、警告、背景工作'],['upd','🆕','版本與更新','上傳更新包，電腦熱更新']]]];
const TLAB={unplug:'unplug_check',bmall:'bookmarks',week:'weekly',spr:'sprint',upb:'copy_to',upold:'copy_to',find:'cmdk',fprog:'folder_prog',rule:'rules',report:'report',cre:'creators',sched:'bg_sched',csv:'list_csv',space:'space_map',empty:'empty_dirs',mon:'months',pcs:'pc_overview'};   // V0.2.53 🆕 工具對應的實驗開關
function labOn(k){return !!(S.state&&S.state.lab&&S.state.lab[k])}
function toolName(k){if(k==='rsplit')return '🗄 R 碟清空搬移（封存）';for(const [,L] of TOOLS)for(const x of L)if(x[0]===k)return x[1]+' '+x[2];return '工具'}
function pinRow(){const el=$('#pinr');if(!el)return;const P=LS.get('pinTools',[])||[];if(!P.length){el.innerHTML='';return}   // V0.4.11 📌 釘選的工具放檔案總管上面
  const M={};TOOLS.forEach(g=>g[1].forEach(x=>M[x[0]]=x));const L=P.filter(k=>M[k]);
  el.innerHTML=L.map(k=>`<button class="pill" data-pin="${k}" title="${esc(M[k][2])}" style="height:40px">${M[k][1]}<span class="pint"> ${esc(M[k][2])}</span></button>`).join('');   // V0.5.84 跟搜尋同一列
  el.onclick=e=>{const b=e.target.closest('[data-pin]');if(b){e.stopPropagation();location.hash='tool/'+b.dataset.pin}}}
async function quickRow(){if(!labOn('views')&&!labOn('recent_dirs')&&!labOn('copy_to'))return;const host=$('#tbgS');if(!host)return;
  const [a,b]=await Promise.all([labOn('views')?api(U('/api/new',{a:'views'}),undefined,{quiet:true}).catch(()=>({})):{},(labOn('recent_dirs')||labOn('copy_to'))?api(U('/api/new',{a:'recent'}),undefined,{quiet:true}).catch(()=>({})):{}]);
  const V=(a.views||[]).slice(-6).reverse(),R=labOn('recent_dirs')?(b.rows||[]).slice(0,6):[],LF=labOn('recent_dirs')?b.last:null,UL=labOn('copy_to')?(b.up_left||0):0,UP=labOn('copy_to')?(b.unpub||0):0;if(!V.length&&!R.length&&!LF&&!UL&&!UP||!$('#tbgS'))return;const nm=p=>p.split(/[\\/]/).filter(Boolean).pop()||p;
  host.insertAdjacentHTML('afterend',`<div class="chips" id="qrow" style="margin:6px 0">${UP?`<button class="pill" data-qp="1" style="border-color:#3fd0c9">⬜ 還沒發佈 ${UP.toLocaleString()} 部</button>`:''}${UL?`<button class="pill" data-qu="1" style="border-color:#4dd68a">📤 還沒上傳 ${UL.toLocaleString()} 部</button>`:''}${LF?`<button class="pill ok" data-ql="${LF.id}">⏯ 繼續：${esc(LF.name.slice(0,18))}</button>`:''}${V.map((v,i)=>`<button class="pill acc" data-qv="${i}">⭐ ${esc(v.name)}</button>`).join('')}${R.map(p=>`<button class="pill" data-qr="${esc(p)}">🕘 ${esc(nm(p))}</button>`).join('')}</div>`);
  $('#qrow').onclick=e=>{if(e.target.closest('[data-qp]')){e.stopPropagation();S.folder='';S.flt='notpub';S.q='';S.sort='up_t';S.sub=true;S.dur='';S.res='';saveView();location.hash='fx';return}if(e.target.closest('[data-qu]')){e.stopPropagation();S.folder='';S.flt='notup';S.q='';S.sort='grade';S.sub=true;S.dur='';S.res='';saveView();location.hash='fx';return}const lf=e.target.closest('[data-ql]');if(lf){e.stopPropagation();openFile(+lf.dataset.ql);return}const v=e.target.closest('[data-qv]'),r=e.target.closest('[data-qr]');if(v){const x=V[+v.dataset.qv];S.folder=x.folder||'';S.flt=x.flt||'all';S.q=x.q||'';S.sort=x.sort||'name';S.sub=x.sub!==false;S.dur=x.dur||'';S.res=x.res||''}else if(r){S.folder=r.dataset.qr}else return;e.stopPropagation();saveView();location.hash='fx'}}
function viewTools(){
  V().innerHTML=`<div class="tbgS" id="tbgS">🖥 後台狀態讀取中…</div>${LS.get('tour5','')?'':`<div class="si" id="tour5" style="border:1px solid #2f9bff;border-radius:10px;margin:6px 0;display:block"><div>🗂 <b>FileCompare 合併進來了</b>（取代「審核」，👤 人物拿掉）：照下面 ①～⑥ 從上往下做；下面一排「🗂 整理」就是原本的 FileCompare。</div><small>兩邊不會同時大量讀同一顆硬碟、同一部影片不會兩邊都轉。舊電腦的整理紀錄要在電腦上按「📥 匯入舊 FileCompare 資料」。</small><div class="row" style="margin-top:6px"><button class="pill" onclick="LS.set('tour5','1');this.closest('#tour5').remove()">知道了</button></div></div>`}<div class="tgh">🧭 工作流程</div><div class="wsGrid"><a class="wsCard" href="/fc/?go=vc" style="text-decoration:none;border-top:3px solid #2f9bff"><i>①</i><b>檔案管理</b><small>16 格快速分類</small></a><a class="wsCard" href="#fx" style="text-decoration:none;border-top:3px solid #4dc9ff"><i>②</i><b>檔案剪輯</b><small>每 10 秒一張・初剪</small></a><a class="wsCard" href="#tool/conv" style="text-decoration:none;border-top:3px solid #f0ad4e"><i>③</i><b>畫質降容量</b><small>轉 H.265・SSIM</small></a><a class="wsCard" href="/fc/?go=tool:hl" style="text-decoration:none;border-top:3px solid #ff6b6b"><i>④</i><b>壞檔・隔離區</b><small>損毀檢查・修復</small></a><a class="wsCard" href="/fc/?go=tool:dup" style="text-decoration:none;border-top:3px solid #b48cff"><i>⑤</i><b>重複檔案</b><small>指紋・最佳解</small></a><a class="wsCard" href="/fc/?go=tool:sim" style="text-decoration:none;border-top:3px solid #ff7eb6"><i>⑥</i><b>照片分類</b><small>相似・日期・地圖</small></a></div><div class="chips" style="margin:6px 0"><button class="pill acc" onclick="location.hash='tool/explore'">🗺 檔案總覽：哪個資料夾最大・能省多少</button><button class="pill" onclick="S.folder='';S.flt='bad';S.q='';S.sub=true;saveView();location.hash='fx'">⚠ ④ SortCut 讀不了的影片</button></div>`+(LS.get('tourSeen','')!=='0.4.00'&&LS.get('tour5','')?`<div class="si" id="tour" style="border:1px solid var(--vline);border-radius:10px;margin:6px 0;display:block"><div>🎉 <b>SortCut 0.4</b>：新功能都在下面，全部預設關著。</div><small>暗的卡片按一下就打開；長按卡片可以釘到檔案總管上面。</small><div class="row" style="margin-top:6px"><button class="pill acc" data-tour="go">去 實驗功能</button><button class="pill" data-tour="x">知道了</button></div></div>`:'')+(labOn('phone_notify')&&window.Notification&&Notification.permission==='default'?`<button class="pill acc" id="ntfy" style="width:100%;margin:6px 0">🔔 允許手機通知（切到別的 App 時也提醒）</button>`:'')+`<input id="tlq" class="ssearch" placeholder="🔍 找工具" style="width:100%;margin:6px 0">`+[...TOOLS.filter(g=>g[0].startsWith('🆕')),...TOOLS.filter(g=>!g[0].startsWith('🆕'))].map(([g,L])=>`<div class="tgh">${g}</div><div class="wsGrid">${L.map(([k,ic,t,sub])=>{const off=TLAB[k]&&!labOn(TLAB[k]);return `<button class="wsCard" data-tl="${k}"${off?' data-off="1" style="opacity:.55"':''}><i>${ic}</i><b>${t}</b><small>${sub}${off?'<br>（還沒打開・按一下打開）':''}</small></button>`}).join('')}</div>`).join('')+
   `<div class="tgh">其他</div><div class="wsGrid"><button class="wsCard" data-tl="cover"><i>🏠</i><b>電腦切到封面</b><small>隱私：電腦畫面不留影片內容</small></button><button class="wsCard" data-tl="logout"><i>🚪</i><b>登出這支手機</b><small>下次要重新輸入 PIN</small></button></div>`;
  {const q=$('#tlq');if(q)q.oninput=()=>{const k=q.value.trim().toLowerCase();$$('.wsCard').forEach(c=>{c.style.display=!k||c.textContent.toLowerCase().includes(k)?'':'none'});$$('.tgh').forEach(h=>{const g=h.nextElementSibling;h.style.display=g&&[...g.children].some(c=>c.style.display!=='none')?'':'none'})}}   // V0.3.87 🔍 找工具
  V().oncontextmenu=e=>{const c=e.target.closest('.wsCard[data-tl]');if(!c)return;e.preventDefault();const k=c.dataset.tl;if(['cover','logout'].includes(k))return;let P=LS.get('pinTools',[])||[];   // V0.4.11 長按＝釘到檔案總管上面
    if(P.includes(k)){P=P.filter(x=>x!==k);toast('📌 取消釘選')}else{P=[...P,k].slice(-8);toast('📌 釘到檔案總管上面了（再長按一次取消）')}LS.set('pinTools',P);$$('.wsCard[data-tl]').forEach(x=>x.classList.toggle('pinned',P.includes(x.dataset.tl)))};
  {let lt=null,lp=false;V().addEventListener('touchstart',e=>{const c=e.target.closest('.wsCard[data-tl]');if(!c)return;lp=false;lt=setTimeout(()=>{lp=true;V().oncontextmenu({target:c,preventDefault(){}});try{navigator.vibrate&&navigator.vibrate(30)}catch(x){}},600)},{passive:true});   // V0.4.12 iPhone 長按也能釘
   ['touchend','touchmove','touchcancel'].forEach(ev=>V().addEventListener(ev,()=>{clearTimeout(lt)},{passive:true}));V().addEventListener('click',e=>{if(lp&&e.target.closest('.wsCard')){e.stopPropagation();e.preventDefault();lp=false}},true)}
  setTimeout(()=>{const P=LS.get('pinTools',[])||[];$$('.wsCard[data-tl]').forEach(x=>x.classList.toggle('pinned',P.includes(x.dataset.tl)))},0);
  V().onclick=async e=>{const tb_=e.target.closest('[data-tour]');if(tb_){LS.set('tourSeen','0.4.00');$('#tour')&&$('#tour').remove();if(tb_.dataset.tour==='go'){S.scat='lab';location.hash='set'}return}if(e.target.closest('#ntfy')){try{const p=await Notification.requestPermission();toast(p==='granted'?'🔔 好了':'沒有允許（可以到手機設定改）');e.target.closest('#ntfy').remove()}catch(x){}return}const b=e.target.closest('[data-tl]');if(b){const k=b.dataset.tl;if(b.dataset.off){const r=await api('/api/settings',{k:'lab:'+TLAB[k],v:true});if(!r.ok)return toast(r.message||'沒打開');if(S.state&&S.state.lab)S.state.lab[TLAB[k]]=true;toast('🧪 已打開（設定 → 實驗功能 可以關）')}if(k==='cover')return ctl('cover');if(k==='logout')return logout();if(k==='rand')return rnd();location.hash='tool/'+k;return}if(e.target.closest('#tbgS'))sysPopOpen('bg');if(e.target.closest('#tgoal'))location.hash='tool/conv'};
  quickRow();weekBanner();wnBanner();cardLive();   // V0.3.05 ⭐🕘 一按就去
  tbgPaint();rsSub()}
async function rsSub(){let j;try{j=await api('/api/rsplit',undefined,{quiet:true})}catch(e){return}const el=$('#rsSub');if(!el||!j||!j.ok)return;const P=j.plan||{};   // V0.5.85 🚚
  if(j.state==='run')el.innerHTML=`<b>搬移中 ${j.pct}%</b>・已搬 ${j.done_n.toLocaleString()} 個 ${fmtB(j.done_b)}・還剩 ${fmtB(j.pend_b)}${j.eta?'・約 '+rsT(j.eta):''}`;else if(j.state==='pause')el.innerHTML=`<b>⏸ 暫停中 ${j.pct}%</b>・按進去繼續`;else if(j.state==='done')el.innerHTML=`✔ 搬完了：${j.done_n.toLocaleString()} 個・${P.src||'R'}: 還剩 ${j.left_n} 個檔${j.fail_n?'・⚠ 沒搬成 '+j.fail_n+' 個':''}`;else if(j.state==='planned')el.innerHTML=`算好了：${(P.n||0).toLocaleString()} 個檔 ${fmtB(P.total)}・按進去「開始轉移」`}
function rsT(s){s=Math.round(s);const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h?`${h} 小時 ${m} 分`:`${m} 分`}
function rsDrv(j,P){   // V0.5.96 💽 R／V／U 三顆硬碟：工作管理員樣式的曲線（使用率％＋讀寫 MB/s），每 3 秒一點、最近 5 分鐘
  const T=P.tgts||[],COL=X=>X===P.src?'#f0a33a':X===T[0]?'#2f9bff':'#26b39a',W=300,H1=70,H2=46,N=100;
  const xs=(i,n)=>W-(n-1-i)*(W/(N-1));
  const grid=(h)=>{let g='';for(let k=1;k<4;k++)g+=`<line x1="0" x2="${W}" y1="${h*k/4}" y2="${h*k/4}"/>`;for(let k=1;k<10;k++)g+=`<line y1="0" y2="${h}" x1="${W*k/10}" x2="${W*k/10}"/>`;return `<g class="rsGr">${g}</g>`};
  const line=(v,h,mx)=>v.map((y,i)=>`${xs(i,v.length).toFixed(1)},${(h-Math.min(1,(+y||0)/mx)*(h-2)-1).toFixed(1)}`).join(' ');
  const mb=b=>b>=1e6?(b/1048576).toFixed(b>=1e8?0:1)+' MB/s':b>=1e3?(b/1024).toFixed(0)+' KB/s':'0';
  return `<div class="rsDrvs">${j.drv.map(D=>{const c=COL(D.X),Hh=D.h||[],bz=Hh.map(x=>x[0]==null?0:x[0]),rd=Hh.map(x=>x[1]),wr=Hh.map(x=>x[2]);
    const mx=Math.max(1048576*10,...rd,...wr)*1.15,pl=line(bz,H1,100),sx=bz.length?xs(0,bz.length).toFixed(1):W;
    const busy=D.busy==null?'—':D.busy+'%',hot=(D.busy||0)>=95;
    return `<div class="rsDk" style="--c:${c}"><div class="rsDh"><b>💽 ${D.X}:</b><i>${esc(D.role)}</i><span class="${hot?'hot':''}">${busy}</span></div>
      <div class="rsDl"><span>使用率</span><em>100%</em></div>
      <svg viewBox="0 0 ${W} ${H1}" preserveAspectRatio="none" class="rsSv">${grid(H1)}${bz.length>1?`<polygon points="${sx},${H1} ${pl} ${W},${H1}" fill="${c}" fill-opacity=".22"/><polyline points="${pl}" fill="none" stroke="${c}" stroke-width="1.6" vector-effect="non-scaling-stroke"/>`:''}</svg>
      <div class="rsDl"><span>傳輸速率</span><em>${mb(mx)}</em></div>
      <svg viewBox="0 0 ${W} ${H2}" preserveAspectRatio="none" class="rsSv">${grid(H2)}${rd.length>1?`<polyline points="${line(rd,H2,mx)}" fill="none" stroke="${c}" stroke-width="1.4" stroke-dasharray="4 3" vector-effect="non-scaling-stroke" opacity=".85"/><polyline points="${line(wr,H2,mx)}" fill="none" stroke="${c}" stroke-width="1.8" vector-effect="non-scaling-stroke"/>`:''}</svg>
      <div class="rsDf"><span><i class="dash"></i>讀 <b>${mb(D.rd)}</b></span><span><i></i>寫 <b>${mb(D.wr)}</b></span></div></div>`}).join('')}</div>`}
async function tRsplit(){const tb=$('#tb');let arm=0,sel=null,lastJ=null;   // V0.5.85 🚚 R 碟清空搬移（V0.5.87 速度拉桿、🧠 智能、每個檔的進度）
  const dopt=(D,v,ex)=>D.filter(d=>!ex.includes(d.X)).map(d=>`<option value="${d.X}"${d.X===v?' selected':''}>${d.X}:${d.label?' '+esc(d.label):''}　已用 ${fmtB(d.used)}／${fmtB(d.total)}・剩 ${fmtB(d.free)}</option>`).join('');
  const N=n=>(+n||0).toLocaleString(),SP=b=>fmtB(b)+'/s',sec=s=>{s=Math.round(s||0);return s<60?s+' 秒':s<3600?Math.floor(s/60)+' 分 '+(s%60)+' 秒':rsT(s)};
  const when=t=>{if(!t)return '—';const d=new Date(t*1000),n=new Date(),dd=Math.round((new Date(d.toDateString())-new Date(n.toDateString()))/864e5);return (dd===0?'今天 ':dd===1?'明天 ':dd===2?'後天 ':(d.getMonth()+1)+'/'+d.getDate()+' ')+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')};
  const role=(P,t)=>P.mode==='cls'?(t===(P.tgts||[])[0]?'已分類・倉庫':'還沒分類・工作'):'';
  const pace=j=>{const A=j.pace||{},B=A.busy||{},run=j.state==='run';const sv=A.ser||'auto';
    return `<div class="rsPace"><div class="rsPh"><b>⚡ 傳輸速度</b><span class="rsPv" id="rsPv">${A.smart?'🧠 '+(run?A.pct+'%':'自動'):A.man+'%'}</span><button class="rsSm${A.smart?' on':''}" id="rsSmart">🧠 智能${A.smart?'（開）':''}</button></div>
      <input type="range" id="rsPct" min="5" max="100" step="5" value="${A.man}"${A.smart?' class="dim"':''}><div class="rsTick"><span>5%</span><span>慢・省力</span><span>50%</span><span>全速</span><span>100%</span></div>
      <div class="rsPi">${run?`現在用 <b>${A.pct}%</b>・${esc(A.why||'')}`:A.smart?'🧠 智能：自己看 TikLive、CPU、溫度、硬碟忙不忙來調':'✋ 手動：照拉桿的百分比（TikLive 要用時一樣會自動讓）'}${A.temp?`・🌡 ${Math.round(A.temp)}°C`:''}${Object.keys(B).length?'・💽 '+Object.entries(B).map(([x,v])=>`${x}: ${v}%`).join(' '):''}</div>
      <div class="rsSeg"><span>硬碟：</span>${[['auto','🧠 自動'],['one','一次寫一顆'],['two','兩顆同時寫']].map(([k,n])=>`<button data-ser="${k}" class="${sv===k?'on':''}">${n}</button>`).join('')}${run?`<em>${A.serial?'現在：一次寫一顆（U、V 輪流）':'現在：兩顆同時寫（R 同時讀兩個檔，U、V 各寫一個）'}</em>`:''}</div>
      <div class="rsSeg"><span>確認：</span>${[['quick','⚡ 快速（單向）'],['full','🔎 完整讀回']].map(([k,n])=>`<button data-ver="${k}" class="${(A.verify||'quick')===k?'on':''}">${n}</button>`).join('')}<em>${(A.verify||'quick')==='quick'?'只寫一次：寫完確認大小、抽查 5 段跟原檔一樣就刪 R 的（最快）':'寫完再把整個檔讀回來比指紋（最保險，慢一倍）'}</em></div>
      ${(A.log||[]).length?`<details><summary>🧠 調速紀錄</summary>${A.log.map(x=>`<div class="rsU">${esc(x)}</div>`).join('')}</details>`:''}</div>`};
  const fileRow=(ic,lbl,F,col)=>F?`<div class="rsFile"><div class="rsFh"><span class="rsIc" style="background:${col}">${ic}</span><div class="rsFn"><b title="${esc(F.dst||'')}">${esc(F.name)}</b><small>${lbl} ${F.tgt}:　${fmtB(F.size)}${F.wait?'・⏳ 等另一邊用完硬碟':'・'+sec(F.sec)+'・'+SP(F.bps)}</small></div><span class="rsFp">${F.pct}%</span></div><div class="rsMini"><i style="width:${F.pct}%;background:${col}"></i></div><small class="rsPath">${esc(F.dst||'')}</small></div>`
    :`<div class="rsFile idle"><span class="rsIc" style="background:#555">${ic}</span><small>${lbl}：沒有</small></div>`;
  const draw=async()=>{let j;try{j=await api('/api/rsplit',undefined,{quiet:true})}catch(e){return}if($('#tb')!==tb||!j)return;lastJ=j;const P=j.plan||{},D=j.drives||[],st=j.state||'';
    if(!sel){const src=P.src||(D.find(d=>d.X==='R')?'R':'');const big=D.filter(d=>d.X!==src).sort((a,b)=>b.free-a.free);sel={src,mode:P.mode||'cls',t1:(P.tgts||[])[0]||(big[0]||{}).X||'',t2:(P.tgts||[])[1]||(big[1]||{}).X||''}}
    const CL=sel.mode==='cls',T=P.tgts||[];
    const busy=st==='run'||st==='pause';let h=pace(j);
    h+=`<div class="rsStop wait">🗄 <b>這個功能已經封存</b>：不在工具清單裡，避免誤按。要再用：⚙ 設定 → 📱 手機網頁 最下面，或電腦按 Ctrl+Shift+R。搬移紀錄和設定都還在。</div>`;
    const warn=`🚚 <b>R 碟清空搬移</b>：把來源硬碟上所有的檔案分到兩顆硬碟（位置不變，只換磁碟代號）。<br><small>開始後 SortCut 和整理的背景工作都會先停（不讀 R）、搬完自動恢復。每個檔<b>複製 → 寫進硬碟 → 確認</b>（⚡ 快速：大小一樣、抽查 5 段一樣；🔎 完整：整檔讀回比指紋），確認過才刪 R 上的那個檔；比對不過的留在 R、最後列清單。預覽圖、分級、指紋、分類紀錄都跟著換到新位置，不用重算。關掉程式也會從剩下的接著搬。</small>`;
    h+=busy||st==='done'?`<details class="rsWarn"><summary>🚚 <b>怎麼搬的</b>（按一下看）</summary>${warn}</details>`:`<div class="rsWarn">${warn}</div>`;
    if(!busy&&st!=='done'){h+=`<div class="si rsCardB"><div class="rsRow"><label>來源（要清空的）</label><select id="rsS">${dopt(D,sel.src,[])}</select></div><div class="rsRow"><label>怎麼分</label><select id="rsM"><option value="cls"${CL?' selected':''}>📂 已分類一顆、還沒分類一顆（建議）</option><option value="auto"${CL?'':' selected'}>⚖ 兩顆平均分</option></select></div><div class="rsRow"><label>${CL?'① 已分類（倉庫）':'目的 ①'}</label><select id="rsT1">${dopt(D,sel.t1,[sel.src])}</select></div><div class="rsRow"><label>${CL?'② 還沒分類（工作）':'目的 ②'}</label><select id="rsT2">${dopt(D,sel.t2,[sel.src,sel.t1])}</select></div>${CL?`<button class="pill" id="rsSwap" style="margin:4px 0">⇅ 兩顆對調</button>`:''}<button class="pill" id="rsPlan" style="width:100%;margin-top:6px"${j.planning?' disabled':''}>${j.planning?'🔍 '+esc(j.pmsg||'計算中…'):'🔍 先算一下怎麼分（只讀，不會動檔案）'}</button></div>`}
    if(P.ok&&(st==='planned'||busy||st==='done')){h+=`<div class="si rsCardB"><b>📋 分法：${P.src}: 共 ${N(P.n)} 個檔、${fmtB(P.total)}</b>${P.mode==='cls'?`<div class="rsT">📂 已分類（FileCompare_分類、VideoSIFT、分好搬過的）${N(P.cls_n)} 個 ${fmtB(P.cls_b)} → <b>${T[0]}:</b>　🆕 還沒分類 ${N(P.unc_n)} 個 ${fmtB(P.unc_b)} → <b>${T[1]}:</b></div>${P.spill_n?`<div class="rsT" style="color:#f0ad4e">⚠ ${T[1]}: 放不下全部還沒分類的：${N(P.spill_n)} 個 ${fmtB(P.spill_b)} 補到 ${T[0]}:（看下面「每個資料夾放哪顆」）</div>`:''}`:''}${busy||st==='done'?'':T.map(t=>`<div class="rsT"><b>${t}:</b> ${role(P,t)?'<i class="rsRole">'+role(P,t)+'</i> ':''}放 ${N(P.pern[t])} 個、${fmtB(P.per[t])}・搬完後剩 <b>${fmtB(P.free[t]-P.per[t])}</b></div>`).join('')}<details><summary style="cursor:pointer;font-size:12px;opacity:.8;margin-top:4px">每個資料夾放哪顆（${(P.units||[]).length} 個）</summary>${(P.units||[]).map(u=>`<div class="rsU"><span>${u.tgt}:</span>${esc(u.rel)}<em>${fmtB(u.b)}</em></div>`).join('')}</details></div>`}
    if(st==='planned')h+=`<button class="rsGo" id="rsGo">${arm?'⚠ 再按一次：確定開始轉移':'🚚 開始轉移'}</button><button class="pill" id="rsReset" style="width:100%;margin-top:6px">↺ 重新選</button>`;
    if(busy&&(j.drv||[]).length)h+=rsDrv(j,P);
    if(busy||st==='done'){const pc=Math.min(100,j.pct||0);
      h+=`<div class="rsHero"><div class="rsHt"><span class="rsBig">${pc.toFixed(1)}<small>%</small></span><span class="rsSt ${st}">${st==='run'?'▶ 搬移中':st==='pause'?'⏸ 暫停中':'✔ 搬完了'}</span></div><div class="rsBar big"><i style="width:${pc}%"></i></div>
        <div class="rsTiles">
          <div class="rsTile"><small>已搬好（比對過）</small><b>${fmtB(j.done_b)}</b><em>${N(j.done_n)} 個</em></div>
          <div class="rsTile"><small>還剩</small><b>${fmtB(j.pend_b)}</b><em>${N(j.pend_n)} 個</em></div>
          <div class="rsTile"><small>最近 10 分鐘速度</small><b>${j.rate?SP(j.rate):'—'}</b><em>硬碟讀寫 ${SP(j.io||0)}</em></div>
          <div class="rsTile"><small>平均速度</small><b>${j.avg?SP(j.avg):'—'}</b><em>已經跑了 ${sec(j.act)}</em></div>
          <div class="rsTile hl"><small>預計完成</small><b>${st==='run'&&j.fin_at?when(j.fin_at):st==='done'?'✔ 完成':'—'}</b><em>${st==='run'&&j.eta?'還要 '+rsT(j.eta):st==='pause'?'暫停中':''}</em></div>
          <div class="rsTile${j.fail_n?' bad':''}"><small>沒搬成</small><b>${N(j.fail_n)}</b><em>${j.fail_n?'原檔都還在 '+P.src+':':'目前都成功'}</em></div>
        </div>
        ${Object.entries(j.per||{}).map(([t,v])=>{const all=v.done_b+v.pend_b,q=all?v.done_b*100/all:0;const d=D.find(x=>x.X===t);return `<div class="rsDrv"><div><b>${t}:</b>${role(P,t)?' <i class="rsRole">'+role(P,t)+'</i>':''}<span>${fmtB(v.done_b)}／${fmtB(all)}・${N(v.done_n)} 個${d?'・硬碟還剩 '+fmtB(d.free):''}</span></div><div class="rsMini"><i style="width:${q}%"></i></div></div>`}).join('')}</div>`;
      if(busy)h+=`<div class="tgh">📄 正在處理</div>`+((j.f_copies&&j.f_copies.length)?j.f_copies.map(F=>fileRow('📥','複製到',F,F.tgt===(P.tgts||[])[0]?'#2f9bff':'#26b39a')).join(''):fileRow('📥','複製到',j.f_copy,'#2f9bff'))+fileRow('🔎',((j.pace||{}).verify==='full'?'讀回比對':'確認'),j.f_ver,'#b48cff')+(j.next&&j.next.length?`<details class="rsNext"><summary>⏭ 接下來 ${j.next.length} 個</summary>${j.next.map(x=>`<div class="rsU"><span>${x.t}:</span>${esc(x.name)}<em>${fmtB(x.b)}</em></div>`).join('')}</details>`:'');
      if(st==='run')h+=`<button class="pill" id="rsPause" style="width:100%;margin-top:8px">⏸ 暫停（手上正在搬的做完再停）</button>`;
      if(st==='pause'){const VB=(j.vols||[]).filter(c=>!c.ok);
        h+=j.draining?`<div class="rsStop wait">⏳ 收尾中：手上正在搬的做完、確認完就停，請等一下…（還不要關機）</div>`:`<div class="rsStop ok">✔ 已停好，可以關機了。重開機後<b>不會自己開始</b>，要按「▶ 繼續轉移」才會從 ${(j.pct||0).toFixed(1)}% 接著搬。</div>`;
        if(!j.draining&&(j.vols||[]).length){const L=(D||[]).map(d=>d.X);
          h+=`<div class="si rsCardB"><b>💽 硬碟代號</b><small style="display:block;opacity:.75;margin:2px 0 6px">重開機後代號可能會跑掉：我用每顆硬碟的序號認，對不上的會標出來</small>${(j.vols||[]).map(c=>`<div class="rsVol${c.ok?'':' bad'}"><span>${c.ok?'✔':'⚠'}</span><b>${esc(c.role)}</b><em>原本 ${c.X}:${c.label?'（'+esc(c.label)+'）':''}</em>${c.ok?'<i>對得上</i>':`<label>現在是 <select data-rm="${c.X}">${['',...L].map(x=>`<option value="${x}"${x===(c.found||'')?' selected':''}>${x?x+':':'選…'}</option>`).join('')}</select></label>`}</div>`).join('')}${VB.length?`<button class="rsGo" id="rsRemap" style="background:#b8860b">💽 套用新代號（紀錄一起改，檔案不動）</button>`:''}</div>`}
        h+=`<button class="rsGo" id="rsRes"${j.draining||VB.length?' disabled style="opacity:.45"':''}>▶ 繼續轉移</button>`}
      if((j.recent||[]).length)h+=`<div class="tgh">✅ 最近搬好的</div><div class="rsRec">${j.recent.map(r=>`<div class="rsR${r.ok?'':' bad'}"><span>${r.ok?'✔':'✖'}</span><div><b>${esc(r.n)}</b><small>${fmtB(r.b)} → ${r.t||'?'}:${r.ok?`・複製 ${sec(r.dc)}・比對 ${sec(r.dv)}`:'・'+esc(r.err||'')}</small></div><em>${new Date(r.ts*1000).toTimeString().slice(0,8)}</em></div>`).join('')}</div>`;
      if(st==='done')h+=`<div class="si rsCardB"><b>${P.src}: 上還剩 ${j.left_n} 個檔${j.left_n?'（'+fmtB(j.left_b)+'）':'・已經清空 ✔'}</b>${(j.left_ex||[]).map(x=>`<div class="rsU">${esc(x)}</div>`).join('')}<small>影片庫和整理的清單${j.fail_n?'加了':'已經把 '+P.src+': 拿掉、換成'} ${(P.tgts||[]).join(': ＋ ')}:；背景工作恢復了。</small></div><button class="pill" id="rsReset" style="width:100%">🧹 清掉這次的搬移紀錄</button>`}
    if(j.fails&&j.fails.length)h+=`<div class="si rsCardB"><b style="color:#ff6b6b">⚠ 沒搬成的（原檔還在 ${P.src}:）</b>${j.fails.map(f=>`<div class="rsU">${esc(f.src)}<em>${esc(f.err||'')}</em></div>`).join('')}</div>`;
    const ae=document.activeElement;if(ae&&(ae.tagName==='SELECT'||ae.id==='rsPct')&&tb.contains(ae))return;
    const op=[...tb.querySelectorAll('details')].map(d=>d.open);tb.innerHTML=h;[...tb.querySelectorAll('details')].forEach((d,i)=>{if(op[i])d.open=true})};
  tb.oninput=e=>{if(e.target.id==='rsPct'){const v=$('#rsPv');if(v)v.textContent=e.target.value+'%';e.target.classList.remove('dim')}};
  tb.onchange=async e=>{const id=e.target.id;if(id==='rsPct'){const r=await api('/api/rsplit',{a:'speed',pct:+e.target.value,smart:false});toast('✋ '+(r.message||''));e.target.blur();return draw()}
    if(id==='rsS')sel.src=e.target.value;if(id==='rsM')sel.mode=e.target.value;if(id==='rsT1')sel.t1=e.target.value;if(id==='rsT2')sel.t2=e.target.value;if(sel.t1===sel.src)sel.t1='';if(sel.t2===sel.src||sel.t2===sel.t1)sel.t2='';draw()};
  tb.onclick=async e=>{const b=e.target.closest('button');if(!b)return;const go=async(a,x={})=>{b.disabled=true;const r=await api('/api/rsplit',{a,...x});toast(r.message||(r.ok?'好了':'沒成功'));b.disabled=false;draw();return r};
    if(b.id==='rsSmart'){const on=!((lastJ||{}).pace||{}).smart;return go('speed',{smart:on})}
    if(b.dataset.ser)return go('speed',{serial:b.dataset.ser});if(b.dataset.ver)return go('speed',{verify:b.dataset.ver});
    if(b.id==='rsSwap'){[sel.t1,sel.t2]=[sel.t2,sel.t1];return draw()}
    if(b.id==='rsPlan'){if(!sel.src||!sel.t1||!sel.t2)return toast('來源和兩顆目的都要選');b.textContent='🔍 計算中…（檔案多要等一下）';const r=await go('plan',{src:sel.src,t1:sel.t1,t2:sel.t2,mode:sel.mode});if(r.ok)toast('✔ 算好了，看一下分法，沒問題就按「開始轉移」')}
    if(b.id==='rsGo'){if(!arm){arm=1;b.textContent='⚠ 再按一次：確定開始轉移';setTimeout(()=>{arm=0},6000);return}arm=0;go('start')}
    if(b.id==='rsRemap'){const M={};tb.querySelectorAll('[data-rm]').forEach(x=>{if(x.value)M[x.dataset.rm]=x.value});if(!Object.keys(M).length)return toast('先選新的代號');return go('remap',{map:M})}
    if(b.id==='rsRes')go('resume');if(b.id==='rsPause')go('pause');if(b.id==='rsReset'){sel=null;go('reset')}};
  draw();const iv=setInterval(()=>{if($('#tb')!==tb)return clearInterval(iv);draw()},2000)}
function tbgPaint(){const s=S.state;const el=$('#tbgS');if(!s||!el)return;const I=s.info||{},J=s.jobs||{};const r=(s.th_active||[]).length+(J.conv||[]).length+(J.cut_active||0),w=(I.th_left||0)+(J.cv_wait||0);
  const B=s.busy||[],C=s.copy||{};const ex=(B.length?`<br><small>正在做：${B.map(esc).join('、')}${labOn('keep_awake')?'・☕ 電腦不會睡著':''}</small>`:'')+((C.q||C.run)&&labOn('copy_to')?`<br><small>📤 複製：${C.run?C.pct+'%・':''}還有 ${C.q} 個${!C.run&&C.last_err?'・⏳ '+esc(C.last_err):''}</small>`:'');   // V0.4.08
  el.innerHTML=(r||w?`🖥 後台：<b>▶ ${r} 個在跑 · ⏳ ${w.toLocaleString()} 個排隊</b> <span>看詳細 ›</span>`:`🖥 後台：現在沒有背景工作 ✔ <span>看詳細 ›</span>`)+ex}
document.addEventListener('click',e=>{if(e.target.closest('a[href^="/fc/"],[data-t="fcx"]'))try{sessionStorage.setItem('vsBack',location.hash||'#fx')}catch(x){}},true);   // V0.5.19 從哪裡進整理，「← SortCut」就回哪裡
document.addEventListener('click',async e=>{if(!e.target.closest('#dtxt'))return;const j=await api(U('/api/new',{a:'day_text'}));try{await navigator.clipboard.writeText(j.text||'');toast('🧾 日報複製好了')}catch(x){prompt('長按複製：',j.text||'')}});   // V0.4.34
async function heatSvg(){let j;try{j=await api(U('/api/new',{a:'heat'}),undefined,{quiet:true})}catch(e){return ''}const R=j.rows||[];if(!R.length)return '';const mx=Math.max(1,...R.map(x=>x.n));const wd0=(new Date(R[0].d+'T00:00').getDay()+6)%7;   // V0.4.09 🗓
  return `<div class="si"><b>🗓 最近 12 週</b><svg viewBox="0 0 ${Math.ceil((R.length+wd0)/7)*14+4} 104" style="width:100%;height:120px">${R.map((x,i)=>{const k=i+wd0,c=Math.floor(k/7),r=k%7,v=x.n/mx;return `<rect x="${c*14+2}" y="${r*14+2}" width="12" height="12" rx="2" fill="${x.n?`hsl(140,${40+50*v}%,${25+35*v}%)`:'rgba(127,127,127,.18)'}"><title>${x.d}：分級 ${x.n}${x.up?'、上傳 '+x.up:''}${x.pub?'、發佈 '+x.pub:''}</title></rect>`+(x.up&&labOn('copy_to')?`<circle cx="${c*14+12}" cy="${r*14+4}" r="1.6" fill="#4dd68a"/>`:'')+(x.pub&&labOn('copy_to')?`<circle cx="${c*14+4}" cy="${r*14+12}" r="1.6" fill="#3fd0c9"/>`:'')}).join('')}</svg><small>越綠＝那天分越多；右上綠點＝有複製上傳、左下藍綠點＝有發佈；按住格子看日期</small></div>`}
async function tReport(){const j=await api(U('/api/new',{a:'report'}));if(!j.ok)return;const HS=await heatSvg();const T=j.today,W=j.week,L=j.days||[];const mx=Math.max(1,...L.map(x=>x.graded));   // V0.2.36
  const row=(n,x)=>`<div class="si"><b>${n}</b><div>分級 <b>${x.graded}</b>（<span style="color:var(--S)">S ${x.S}</span> · <span style="color:var(--A)">A ${x.A}</span> · <span style="color:var(--E)">E ${x.E}</span> · <span style="color:var(--F)">F ${x.F}</span>）</div><small>剪 ${x.cuts} 段 · 轉檔 ${x.cv_n} 部省 ${fmtB(x.cv_save)} · 清掉待刪 ${x.purge_n} 個 ${fmtB(x.purge_b)}</small></div>`;
  const bars=L.map((x,i)=>{let y=120,o='';for(const g of ['F','E','A','S']){const h=x[g]/mx*100;if(h>0){y-=h;o+=`<rect x="${i*22+2}" y="${y}" width="18" height="${h}" fill="var(--${g})"/>`}}return o+`<text x="${i*22+11}" y="134" font-size="8" text-anchor="middle" fill="var(--sub)">${x.d.slice(8)}</text>`+(x.up&&labOn('copy_to')?`<text x="${i*22+11}" y="${y-2}" font-size="7" text-anchor="middle" fill="#4dd68a">↑${x.up}</text>`:'')}).join('');
  $('#tb').innerHTML=`<button class="pill acc" id="dtxt" style="width:100%;margin-bottom:6px">🧾 複製今天的日報（貼到 LINE／群組）</button>`+row('今天',T)+row('這 7 天',W)+HS+`<div class="si"><b>最近 14 天</b><svg viewBox="0 0 ${L.length*22} 138" style="width:100%;height:150px">${bars}</svg><small>還有 ${j.left.toLocaleString()} 部預覽圖好了、還沒分級</small></div>`+(j.hours?(()=>{const H=j.hours,hm=Math.max(1,...H);   // V0.2.50
    return `<div class="si"><b>⏱ 速度</b><div>最近 7 天平均每天 <b>${j.pace}</b> 部・還沒分級 <b>${(j.ungraded||0).toLocaleString()}</b> 部</div><small>${j.eta_days!=null?'照這速度大約 <b>'+j.eta_days+' 天</b>分完':'最近 7 天沒分級，算不出還要幾天'}${j.best_h>=0?'・🕘 最常在 <b>'+j.best_h+' 點</b>審':''}${j.per_file?'・⏱ 每部大概 <b>'+j.per_file+' 秒</b>':''}${j.guess_acc!=null?'・🤖 建議猜中 <b>'+j.guess_acc+'%</b>（'+j.guess_n+' 次）':''}${j.auto_7d?'・⚡ 自動規則 7 天分了 <b>'+j.auto_7d+'</b> 部':''}${labOn('copy_to')?'・📤 7 天上傳 <b>'+(j.up_7d||0)+'</b> 部・S／A 還沒傳 <b>'+(j.up_left||0)+'</b> 部':''}</small>
    <svg viewBox="0 0 240 60" style="width:100%;height:70px">${H.map((n,i)=>{const h=n/hm*44;return `<rect x="${i*10+1}" y="${48-h}" width="8" height="${h}" fill="#4dc9ff"/>`+(i%3===0?`<text x="${i*10}" y="58" font-size="7" fill="var(--sub)">${i}</text>`:'')}).join('')}</svg></div>`})():'')}
async function tCre(){const j=await api(U('/api/new',{a:'creators'}));if(!j.ok)return;const R=j.rows||[];
  let so=LS.get('creSort','bytes');const SO=[['bytes','大小'],['n','部數'],['left','還沒分'],['S','S 多'],['up','上傳多'],['stale','最久沒發']];   // V0.3.76 手機也能排序
  $('#tb').innerHTML=`<input id="crq" placeholder="找作者" style="width:100%;margin-bottom:6px"><div class="chips" id="crs" style="margin-bottom:6px"></div><div id="crl"></div>`;
  const key={bytes:x=>-x.bytes,n:x=>-x.n,left:x=>-(x.n-x.graded),S:x=>-(x.S||0),up:x=>-(x.up||0),stale:x=>x.pub?x.last_pub:(x.up?x.last_up:9e12)};
  const paint=()=>{$('#crs').innerHTML=SO.map(([k,t])=>`<button class="pill${k===so?' acc':''}" data-cs="${k}">${t}</button>`).join('');const q=($('#crq').value||'').toLowerCase();$('#crl').innerHTML=R.filter(x=>x.k.toLowerCase().includes(q)).sort((a,b)=>key[so](a)-key[so](b)).map(x=>`<div class="it" data-k="${esc(x.k)}"><div class="grow"><b>${esc(x.k)}</b><div class="mu">${x.n} 部 · ${fmtB(x.bytes)} · 分級 ${Math.round(x.graded*100/Math.max(1,x.n))}% · S ${x.S} A ${x.A} E ${x.E} F ${x.F}${x.still!=null?` · 😴 平均靜止 ${Math.round(x.still*100)}%`:''}${x.up?` · 📤 上傳過 ${x.up} 部（${Math.floor((Date.now()/1000-x.last_up)/86400)} 天前）`:''}${x.pub?` · ✅ 發佈 ${x.pub} 部（${Math.floor((Date.now()/1000-x.last_pub)/86400)} 天前）`:''}</div></div><span class="mu">›</span></div>`).join('')};
  $('#crs').onclick=e=>{const b=e.target.closest('[data-cs]');if(!b)return;so=b.dataset.cs;LS.set('creSort',so);paint()};
  $('#crq').oninput=paint;paint();$('#crl').onclick=e=>{const it=e.target.closest('[data-k]');if(!it||it.dataset.k==='（其他）')return;S.q=it.dataset.k;saveView();location.hash='fx';toast('👥 只看「'+it.dataset.k+'」（清掉搜尋就回到全部）',4000)}}
async function tCsv(){const q={a:'csv',folder:S.folder||'',flt:S.flt||'all',q:S.q||'',sort:S.sort||'name',sub:S.sub?1:0,dur:S.dur||'',res:S.res||''};   // V0.2.38
  $('#tb').innerHTML=`<div class="si"><div>會匯出：<b>${esc(S.folder||'全部資料夾')}</b>・${esc(fltName(S.flt||'all'))}${S.q?'・搜尋「'+esc(S.q)+'」':''}${S.dur?'・⏱ '+esc((DURS.find(x=>x[0]===S.dur)||['',''])[1]):''}</div></div><div class="si"><button class="pill acc" id="csvgo">📤 下載 CSV</button></div><div class="mu">要換範圍：先回檔案總管選資料夾／篩選，再來這裡。</div>`;
  $('#csvgo').onclick=async()=>{try{const r=await fetch(U('/api/new',q),{headers:{'X-VS-Token':TOK},credentials:'same-origin',cache:'no-store'});const ct=r.headers.get('content-type')||'';if(ct.includes('json')){const j=await r.json();return toast(j.message||'匯不出來')}
    const b=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='VideoSift_清單.csv';document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},4000);toast('📤 已下載')}catch(e){toast('下載失敗')}}}
async function dlCsv(url,name){try{const r=await fetch(url,{headers:{'X-VS-Token':TOK},credentials:'same-origin',cache:'no-store'});const b=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name;document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},4000);toast('🧾 已下載')}catch(e){toast('下載失敗')}}   // V0.3.93
async function tSpace(){const j=await api(U('/api/new',{a:'space'}));if(!j.ok)return;const C={S:'#ffc94d',A:'#45d483',E:'#4dc9ff',F:'#ff4d6d','':'#9aa0a6',other:'#5c6168'};   // V0.2.43
  $('#tb').innerHTML=`<div class="mu" style="margin-bottom:6px">${Object.entries({S:'S',A:'A',E:'E',F:'F 待刪','':'未分級',other:'其他檔案'}).map(([k,n])=>`<span style="color:${C[k]}">■</span> ${n}`).join('　')}　□ 剩下</div>`+(j.rows||[]).map(o=>{const tot=o.total||o.lib||1;
    return `<div class="si"><b>${o.d}:</b> ${esc(o.label||'')}<br><small>影片 ${o.n.toLocaleString()} 部・${fmtB(o.lib)}${o.total?`・總共 ${fmtB(o.total)}・剩 <b>${fmtB(o.free)}</b>`:'・（沒接上）'}${o.F?`<br><span style="color:${C.F}">F 待刪 ${o.nF.toLocaleString()} 部＝清掉空出 ${fmtB(o.F)}</span>`:''}${(o.per_day||0)>1e8?`<br>📉 最近每天少 ${fmtB(o.per_day)}${o.days_full?`，大約 <b style="color:#ff8a65">${o.days_full} 天</b>會滿`:''}`:''}</small>
    <div style="display:flex;height:14px;border-radius:7px;overflow:hidden;background:rgba(127,127,127,.25);margin-top:6px">${['S','A','E','F','','other'].map(k=>o[k]>0?`<i style="width:${(o[k]/tot*100).toFixed(2)}%;background:${C[k]}"></i>`:'').join('')}</div></div>`}).join('')||'<div class="empty">影片庫還沒有影片</div>'}
function weekHTML(j){const tr=j.trend||0;return `<div class="si"><b>📆 這 7 天回顧</b><div>分級 <b>${j.graded.toLocaleString()}</b> 部（S ${j.S}・A ${j.A}）　${tr>0?'⬆ +':tr<0?'⬇ ':'➡ '}${tr}%（前 7 天 ${j.graded_prev.toLocaleString()}）</div><small>有審的天數 <b>${j.active}</b>／7${j.best_day?'・最拚 <b>'+j.best_day.slice(5)+'</b>':''}${labOn('copy_to')?'・📤 上傳 <b>'+j.up+'</b> 部（前 7 天 '+j.up_prev+'）・✅ 發佈 <b>'+(j.pub||0)+'</b> 部':''}・✂ ${j.cuts} 段・💾 ${fmtB(j.saved)}${j.sprint_n?'・⏱ 衝刺 '+j.sprint_n+' 次最快每分 '+j.sprint_best:''}・還沒分 ${(+j.left||0).toLocaleString()} 部</small></div>`}   // V0.3.80 📆
async function tWeek(){const j=await api(U('/api/new',{a:'week'}));if(!j.ok)return;LS.set('weekSeen',j.wk);const HS=await heatSvg();$('#tb').innerHTML=weekHTML(j)+HS}   // V0.4.35 加 🗓 熱圖
function cardLive(){try{const st=S.state||{};const put=(k,t)=>{const c=$(`.wsCard[data-tl="${k}"]:not([data-off])`);if(!c||!t)return;let e=$('.live',c);if(!e){e=document.createElement('em');e.className='live';e.style.cssText='display:block;font-style:normal;font-size:11px;color:#ffc94d;margin-top:2px';c.appendChild(e)}e.textContent=t};   // V0.4.54 工具卡片顯示即時狀態
  put('upb',[st.unpub?'⬜ 沒發佈 '+st.unpub:'',st.up_goal?('今天 '+st.up_goal.n+'／'+st.up_goal.goal):'',st.copy&&st.copy.q?'排隊 '+st.copy.q:''].filter(Boolean).join('・'));
  put('spr',st.sprint&&st.sprint.on?'衝刺中・已分 '+st.sprint.n+' 部':'');put('report',st.goal?('今天 '+st.goal.n+'／'+st.goal.goal):'')}catch(e){}}
async function wnBanner(){if(!labOn('whats_new'))return;const sn=LS.get('verSeen','');let j;try{j=await api(U('/api/new',{a:'whatsnew',since:sn}),undefined,{quiet:true})}catch(e){return}if(!j.ok)return;   // V0.3.97 🆕
  if(!sn||sn===j.cur||!(j.rows||[]).length){LS.set('verSeen',j.cur);return}if(!$('#tbgS')||$('#wnb'))return;
  $('#tbgS').insertAdjacentHTML('afterend',`<div class="si" id="wnb" style="border:1px solid var(--vline);border-radius:10px"><b>🆕 從 V${esc(sn)} 更新到 V${esc(j.cur)}</b>：中間 ${j.rows.length} 版的改變<details style="margin-top:4px"><summary>看全部</summary>${j.rows.map(x=>`<div style="margin-top:6px"><b>V${esc(x.version)}</b><ul style="margin:2px 0 0 18px;padding:0">${(x.items||[]).map(i=>`<li><small>${esc(i)}</small></li>`).join('')}</ul></div>`).join('')}</details><div class="row" style="margin-top:6px"><button class="pill acc" id="wnx">好，知道了</button></div></div>`);
  $('#wnx').onclick=e=>{e.stopPropagation();LS.set('verSeen',j.cur);$('#wnb').remove()}}
async function weekBanner(){if(!labOn('weekly'))return;let j;try{j=await api(U('/api/new',{a:'week'}),undefined,{quiet:true})}catch(e){return}if(!j.ok||LS.get('weekSeen','')===j.wk||!$('#tbgS')||$('#wkb'))return;
  $('#tbgS').insertAdjacentHTML('afterend',`<div id="wkb" style="position:relative">${weekHTML(j)}<button class="pill" id="wkx" style="position:absolute;top:6px;right:6px">✕</button></div>`);$('#wkx').onclick=e=>{e.stopPropagation();LS.set('weekSeen',j.wk);$('#wkb').remove()}}
async function tUnplug(){const tb=$('#tb');const draw=async()=>{let j;try{j=await api(U('/api/new',{a:'drive_busy'}),undefined,{quiet:true})}catch(e){return}if($('#tb')!==tb)return;   // V0.4.49 🔌
  tb.innerHTML=(j.rows||[]).map(x=>`<div class="si"><b>💽 ${esc(x.d)}:</b>　${x.busy.length?'<span style="color:#ffc94d">⚠ 正在用：'+x.busy.map(esc).join('、')+'</span>':'<span style="color:#45d483">✅ 可以拔</span>'}</div>`).join('')+'<div class="mu">每 2 秒更新；拔之前最好還是在電腦上「安全地移除硬體」。</div>'};
  await draw();const iv=setInterval(()=>{if($('#tb')!==tb){clearInterval(iv);return}draw()},2000)}
async function tBmAll(){const j=await api(U('/api/new',{a:'bm_all'}));if(!j.ok)return;const R=j.rows||[];   // V0.4.16 🔖
  $('#tb').innerHTML=`<input id="bmq" placeholder="找檔名或書籤說明" style="width:100%;margin-bottom:8px"><div id="bml"></div>`;
  const paint=()=>{const q=($('#bmq').value||'').toLowerCase();$('#bml').innerHTML=R.map((x,i)=>[x,i]).filter(([x])=>!q||(x.name+x.note).toLowerCase().includes(q)).slice(0,500).map(([x,i])=>`<div class="si" data-bi="${i}" style="cursor:pointer"><b>${x.grade?`<span style="color:var(--${x.grade})">${x.grade}</span> `:''}${fmtT(x.t)}</b>　${esc(x.note||'（沒寫說明）')}<br><small style="word-break:break-all">${esc(x.name)}</small> <button class="pill" data-bc="${i}" style="float:right">✂ 剪前後 15 秒</button></div>`).join('')||'<div class="mu">還沒有書籤（播放時按 🔖 加）</div>'};
  $('#bmq').oninput=paint;paint();$('#bml').onclick=async e=>{const bc=e.target.closest('[data-bc]');if(bc){e.stopPropagation();const x=R[+bc.dataset.bc];const r=await api('/api/new',{a:'bm_clip',id:x.id,t:x.t,before:5,after:10});toast(r.message||(r.ok?'✂ 排進初剪了':'沒排進去'));return}const it=e.target.closest('[data-bi]');if(!it)return;const x=R[+it.dataset.bi];try{play({id:x.id,name:x.name},Math.max(0,x.t-1))}catch(err){openFile(x.id)}}}
async function tSpr(){const j=await api(U('/api/new',{a:'sprint_hist'}));if(!j.ok)return;const V=j.cur,H=j.rows||[];   // V0.3.72 ⏱ 分級衝刺
  const best=Math.max(0,...H.map(h=>h.rate||0));
  $('#tb').innerHTML=`<div class="si" style="line-height:1.7">${V&&V.on?`衝刺中：還剩 <span style="font-weight:800">${Math.floor(V.left/60)}:${String(V.left%60).padStart(2,'0')}</span>，已經分了 <span style="font-weight:800">${V.n}</span> 部（每分鐘 ${V.rate}）<div class="row" style="margin-top:6px"><button class="pill er" id="spStop">🏁 現在結束</button></div>`:`選一個時間開始，倒數時專心分級：<div class="row" style="margin-top:6px">${[10,15,25,45].map(m=>`<button class="pill acc" data-spm="${m}">${m} 分鐘</button>`).join('')}</div>`}</div>`+
    `<div class="si"><b>歷史</b>（最好：每分鐘 ${best} 部）${H.map(h=>`<div><small>${new Date(h.t*1000).toLocaleString().slice(0,-3)}　${h.min} 分鐘　<b>${h.n}</b> 部　每分 ${h.rate}</small></div>`).join('')||'<div><small>還沒有</small></div>'}</div>`;
  $$('#tb [data-spm]').forEach(b=>b.onclick=async()=>{const r=await api('/api/new',{a:'sprint',min:+b.dataset.spm});toast(r.message||'');try{await poll()}catch(e){}location.hash='fx'});
  const st=$('#spStop');if(st)st.onclick=async()=>{const r=await api('/api/new',{a:'sprint',on:0});const R=r.result;toast(R?`🏁 分了 ${R.n} 部（每分鐘 ${R.rate}）`:'');try{await poll()}catch(e){}tSpr()}}
async function tUpB(){const tb=$('#tb');   // V0.3.69 📋 上傳看板
  const draw=async()=>{const j=await api(U('/api/new',{a:'up_board'}),undefined,{quiet:true}).catch(()=>({}));if($('#tb')!==tb||!j.ok)return;const G=j.goal;
    const HN={'📥 還沒傳':'按一下＝排進複製；👁＝先打開看','✅ 今天傳好的':'按一下＝打開；⬜／✅＝發佈了沒','✅ 最近 7 天傳好的':'按一下＝打開；⬜／✅＝發佈了沒'};const col=(t,L,f,h=HN[t])=>`<div class="si"><b>${t} <span class="mu" style="font-weight:400">${L.length}</span></b>${h?`<small style="margin:-6px 0 6px">${h}</small>`:''}${L.length?L.map(f).join(''):'<div><small>（沒有）</small></div>'}</div>`;
    tb.innerHTML=`<div class="si"><div style="line-height:1.6">${j.unpub?'⬜ 複製了還沒發佈 <b>'+j.unpub+'</b> 部・':''}還沒傳 <b>${(j.todo_n||0).toLocaleString()}</b> 部・排隊 <b>${j.queue.length}</b>${j.cur?'・正在複製 '+esc(j.cur)+' '+j.pct+'%':''}${j.wait?'・⏳ '+esc(j.wait):''}${j.free!=null?'・💽 上傳那顆剩 '+fmtB(j.free):''}${j.eta&&j.eta.days!=null?'・⌛ 照'+(j.eta.by==='goal'?'每天目標':'最近 7 天的速度')+' '+j.eta.per+' 部／天，大約 <b>'+j.eta.days+'</b> 天傳完':''}${G?'・今天 <b>'+G.n+'</b>／'+G.goal+(G.done?' 🎉':''):'・今天傳了 <b>'+j.done.length+'</b> 部'}</div><div class="row" style="margin-top:8px"><button class="pill acc" id="ubAll">📤 全部排進複製</button><button class="pill${j.order==='mix'?' acc':''}" id="ubMix">🔀 作者輪流排${j.order==='mix'?' ✔':''}</button><button class="pill" id="ubMore">⋯ 更多</button><span style="display:none"><button id="ubCsv"></button><button id="ubUndo"></button><button id="ubPn"></button>${labOn('caption')?'<button id="ubCap"></button>':''}</span></div></div>`+
      col('📥 還沒傳',j.todo,x=>`<div class="row" data-ub="${x.id}" style="cursor:pointer;padding:3px 0"><button class="pill" data-ubv="${x.id}" style="padding:0 6px" title="先打開看看">👁</button> <b style="color:var(--${x.grade})">${x.grade}</b>　<small style="word-break:break-all">${esc(x.name)}${x.dup?' <span style="color:#ffc94d">♻ 已經傳過同一支（'+esc(x.dup)+'）</span>':''}</small></div>`)+
      col('⏳ 排隊中',j.queue,x=>`<div><small>${x.cut?'✂':'🎬'} ${esc(x.name)}</small></div>`)+
      `<div class="row" style="margin:4px 0"><button class="pill${j.done_days===7?'':' acc'}" data-dd="1">今天</button><button class="pill${j.done_days===7?' acc':''}" data-dd="7">最近 7 天</button></div>`+col(j.done_days===7?'✅ 最近 7 天傳好的':'✅ 今天傳好的',j.done,x=>`<div data-ubo="${x.id}" style="cursor:pointer"><button class="pill" data-pub="${x.id}" data-on="${x.pub_t>0?0:1}" style="padding:0 6px">${x.pub_t>0?'✅':'⬜'}</button>${labOn('caption')?` <button class="pill" data-ucap="${x.id}" style="padding:0 6px" title="複製這部的文案">📋</button>`:''} <small>${j.done_days===7?(new Date(x.up_t*1000).getMonth()+1)+'/'+new Date(x.up_t*1000).getDate()+' ':''}${new Date(x.up_t*1000).toTimeString().slice(0,5)}　${x.grade||''}　${esc(x.name)}</small></div>`);
    {const c=$('#ubCap');if(c)c.onclick=async()=>{const r=await api(U('/api/new',{a:'caption_today'}));if(!r.n)return toast('今天還沒有傳好的');try{await navigator.clipboard.writeText(r.text);toast('📋 複製了 '+r.n+' 部的文案')}catch(e){prompt('長按複製：',r.text)}}}
    $('#ubMore').onclick=()=>menu('📋 上傳看板',[...(labOn('caption')?[['📋 今天傳好的文案全部複製',()=>$('#ubCap').click()]]:[]),['📥 貼一串檔名標成已發佈',()=>$('#ubPn').click()],['🧾 上傳紀錄匯出 CSV（30 天）',()=>$('#ubCsv').click()],['⏪ 復原上一個複製',()=>$('#ubUndo').click()],['🧺 清理上傳資料夾的舊檔',()=>{location.hash='tool/upold'}]]);   // V0.4.28 少用的收進「更多」
    $('#ubPn').onclick=async()=>{const t=prompt('一行一個檔名（可以一次貼很多；日期／分級前綴會自動去掉）：','');if(!t||!t.trim())return;const r=await api('/api/new',{a:'pub_names',text:t});toast(r.message||'',6000);draw()};
    $$('#tb [data-dd]').forEach(b=>b.onclick=async()=>{await api('/api/new',{a:'up_done_days',days:+b.dataset.dd});draw()});
    $('#ubMix').onclick=async()=>{await api('/api/new',{a:'up_order',mix:j.order==='mix'?0:1});draw()};
    $('#ubUndo').onclick=async()=>{if(!confirm('把最近一個複製到上傳的那份丟到資源回收筒、取消已上傳？（原檔不動）'))return;const r=await api('/api/new',{a:'up_undo',n:1});toast(r.message||'');draw()};
    $('#ubCsv').onclick=()=>dlCsv(U('/api/new',{a:'up_csv',days:30}),'VideoSift_上傳紀錄.csv');
    $('#ubAll').onclick=async()=>{const ids=j.todo.map(x=>x.id);if(!ids.length)return;if(!confirm(`排 ${ids.length} 部進複製？`))return;await copyTo(ids);draw()};
    $$('#tb [data-ub]').forEach(r=>r.onclick=async e=>{const v=e.target.closest('[data-ubv]');if(v){e.stopPropagation();openFile(+v.dataset.ubv);return}await copyTo([+r.dataset.ub]);draw()});$$('#tb [data-ubo]').forEach(r=>r.onclick=async e=>{const uc=e.target.closest('[data-ucap]');if(uc){e.stopPropagation();const j2=await api(U('/api/new',{a:'caption',id:+uc.dataset.ucap}));try{await navigator.clipboard.writeText(j2.text||'');toast('📋 文案複製好了，貼完記得按 ⬜ 標已發佈')}catch(x){prompt('長按複製：',j2.text||'')}return}const pb=e.target.closest('[data-pub]');if(pb){e.stopPropagation();api('/api/new',{a:'pub_mark',ids:[+pb.dataset.pub],on:+pb.dataset.on}).then(r=>{toast(r.message||'');draw()});return}openFile(+r.dataset.ubo)})};
  await draw();const iv=setInterval(()=>{if($('#tb')!==tb){clearInterval(iv);return}draw()},4000)}
async function tUpOld(){const tb=$('#tb');let days=+(LS.get('upOldDays','14'))||14;   // V0.3.66 🧺 上傳資料夾舊檔
  const draw=async()=>{tb.innerHTML='<div class="si">讀取中…</div>';const j=await api(U('/api/new',{a:'up_old',days}));if($('#tb')!==tb)return;const R=j.rows||[];
    tb.innerHTML=`<div class="si"><div style="line-height:1.7">${j.ok===false?esc(j.message||''):`📁 ${esc(j.dir||'')}<br>放超過 <select id="uod">${[0,3,7,14,30,60,90].map(n=>`<option value="${n}"${n===days?' selected':''}>${n} 天</option>`).join('')}</select>：<b>${R.length}</b> 個・${fmtB(j.bytes||0)}`}</div><div class="row" style="margin-top:8px"><button class="pill" id="uoall">全選</button><button class="pill er" id="uodel">🗑 丟到資源回收筒</button></div><small>只動上傳資料夾裡的複本，原本的影片不會動；救得回來</small></div>`+
      R.map((x,i)=>`<label class="si" style="display:flex;gap:8px;align-items:center"><input type="checkbox" data-i="${i}"${x.pub===false?'':' checked'}><small style="word-break:break-all">${x.pub===true?'✅ 已發佈・':x.pub===false?'⬜ 還沒發佈・':''}${x.age} 天・${fmtB(x.size)}・${esc(x.rel)}</small></label>`).join('');
    const sel=$('#uod');if(sel)sel.onchange=()=>{days=+sel.value;LS.set('upOldDays',String(days));draw()};
    $('#uoall').onclick=()=>$$('#tb [data-i]').forEach(c=>c.checked=true);
    $('#uodel').onclick=async()=>{const L=$$('#tb [data-i]').filter(c=>c.checked).map(c=>R[+c.dataset.i].rel);if(!L.length)return;if(!confirm(`把 ${L.length} 個檔丟到資源回收筒？`))return;const r=await api('/api/new',{a:'up_old_rm',rels:L,days});toast(r.message||'');draw()}};
  draw()}
async function tEmpty(){const tb=$('#tb');let j=await api(U('/api/new',{a:'empty'}));if(!j.ok)return;   // V0.2.45
  if(!j.done&&!j.run){const r=await api('/api/new',{a:'empty_scan'});if(!r.ok)return toast(r.message||'');j.run=true}
  while(j.run&&$('#tb')===tb){tb.innerHTML=`<div class="si">🔎 找中…已看過 ${(j.n||0).toLocaleString()} 個資料夾</div>`;await new Promise(z=>setTimeout(z,1200));j=await api(U('/api/new',{a:'empty'}),undefined,{quiet:true})}
  if($('#tb')!==tb)return;const R=j.rows||[];
  tb.innerHTML=`<div class="si">找到 <b>${R.length.toLocaleString()}</b> 個空資料夾（只刪真的空的，有檔案的自動保留）<div class="row" style="margin-top:6px"><button class="pill" id="eall">全選</button><button class="pill" id="ere">🔎 重新找</button><button class="pill er" id="edel">🗑 刪掉勾選的</button></div></div>`+
    R.map((p,i)=>`<label class="si" style="display:flex;gap:8px;align-items:center"><input type="checkbox" data-i="${i}"><small style="word-break:break-all">${esc(p)}</small></label>`).join('');
  $('#eall').onclick=()=>$$('#tb [data-i]').forEach(c=>c.checked=true);$('#ere').onclick=async()=>{await api('/api/new',{a:'empty_scan'});tEmpty()};
  $('#edel').onclick=async()=>{const L=$$('#tb [data-i]').filter(c=>c.checked).map(c=>R[+c.dataset.i]);if(!L.length)return;if(!confirm(`刪掉 ${L.length} 個空資料夾？`))return;const r=await api('/api/new',{a:'empty_rm',dirs:L});toast(r.message||'');tEmpty()}}
async function tMon(){const j=await api(U('/api/new',{a:'months'}));if(!j.ok)return;const R=j.rows||[];const mx=Math.max(1,...R.map(x=>x.n));   // V0.2.47
  $('#tb').innerHTML=`<div class="mu" style="margin-bottom:6px">時間＝檔案修改時間（通常就是錄影那天）・點一下只看那個月</div>`+R.map(x=>{const pc=Math.round(x.graded*100/Math.max(1,x.n));
    return `<div class="si" data-ym="${x.ym}" style="cursor:pointer"><b>📅 ${x.ym}</b>　${x.n.toLocaleString()} 部・${fmtB(x.bytes)}・分級 ${pc}%<br><small>S ${x.S}・A ${x.A}・E ${x.E}・F ${x.F}・還沒分 ${x.n-x.graded}</small>
      <div style="height:6px;border-radius:3px;background:rgba(127,127,127,.25);margin-top:4px;overflow:hidden"><i style="display:block;height:100%;width:${(x.n/mx*100).toFixed(1)}%;background:linear-gradient(90deg,#45d483 ${pc}%,#4dc9ff ${pc}%)"></i></div></div>`}).join('')||'<div class="empty">沒有資料</div>';
  $('#tb').onclick=e=>{const b=e.target.closest('[data-ym]');if(!b)return;S.flt='month:'+b.dataset.ym;S.folder='';saveView();location.hash='fx';toast('📅 只看 '+b.dataset.ym+'（篩選選「全部」就回去）',4000)}}
async function copyTo(ids,cuts){const r=await api('/api/new',{a:cuts?'copy_cuts':'copy_to',ids});toast(r.message||(r.ok?'📤 排好了':'沒排進去'),5000)}   // V0.2.49
async function tPcs(){const j=await api(U('/api/new',{a:'pcs'}));if(!j.ok)return;   // V0.2.51
  $('#tb').innerHTML=`<div class="si">這台：<b style="color:${esc(j.color||'')}">● ${esc(j.me||'')}</b><br><small>紀錄寫在每顆硬碟自己身上，接到哪台就在哪台用</small></div>`+(j.rows||[]).map(o=>{const who=o.has?(o.mine?'這台':'另一台：'+esc(o.pc_name)):(o.in_lib?'（影片庫裡，還沒寫過）':'（沒有紀錄）');
    return `<div class="si"><b>${o.d}:</b> ${esc(o.label||'')}<br><small style="${o.has&&!o.mine?'color:#ffb74d':''}">紀錄最後是 ${who}${o.t?'・'+new Date(o.t*1000).toLocaleString():''}</small>${o.has?`<br><small>影片 ${o.n.toLocaleString()}・分級 ${o.graded.toLocaleString()}・預覽圖 ${o.th.toLocaleString()}${o.app?'・V'+esc(o.app):''}</small>`:''}</div>`}).join('')||'<div class="empty">讀不到硬碟清單</div>'}
async function tRule(){const tb=$('#tb');   // V0.2.60 ⚡ 規則分級
  tb.innerHTML=`<div class="mu" style="margin-bottom:6px">只動「還沒分級」的；條件都要符合（0／空白＝不管）。可以復原。</div>
   <div class="si">時長短於 <input type="number" id="r_dlt" value="0" min="0" style="width:80px"> 秒</div><div class="si">時長長於 <input type="number" id="r_dgt" value="0" min="0" style="width:80px"> 分鐘</div>
   <div class="si">畫質 <select id="r_h"><option value="0">不管</option><option value="360">低於 360p</option><option value="480">低於 480p</option><option value="720">低於 720p</option><option value="1080">低於 1080p</option></select></div>
   <div class="si">檔案小於 <input type="number" id="r_sz" value="0" min="0" style="width:90px"> MB</div><div class="si">😴 靜止超過 <input type="number" id="r_st" value="0" min="0" max="100" style="width:70px"> %</div><div class="si">檔名包含 <input id="r_nm" style="width:60%"></div>
   <label class="si"><input type="checkbox" id="r_fo"${S.folder?'':' disabled'}> 只在目前資料夾（${esc(S.folder||'全部')}）</label>
   <div class="si">標成 <select id="r_g"><option value="F">F 刪除（之後在待刪確認）</option><option value="E">E 觀察</option><option value="A">A 保存</option><option value="S">S 無條件保存</option></select></div>
   <div class="si" id="r_pv">…</div><div class="row"><button class="pill" id="r_undo">↩ 復原上一次</button><span class="grow"></span><button class="pill" id="r_auto">💾 存成自動規則</button><button class="pill acc" id="r_go">⚡ 套用</button></div><div class="mu" style="margin-top:8px">⚡ 自動規則（每分鐘自動套用到還沒分級的）</div><div id="r_al"></div><button class="pill" id="r_aundo" style="margin-top:6px">↩ 復原最近 24 小時自動規則分的</button>`;
  const R=()=>({dur_lt:+$('#r_dlt').value||0,dur_gt:(+$('#r_dgt').value||0)*60,h_lt:+$('#r_h').value||0,size_lt:+$('#r_sz').value||0,still_gt:+$('#r_st').value||0,name:$('#r_nm').value.trim(),folder:$('#r_fo').checked?S.folder:'',grade:$('#r_g').value});
  let seq=0;const pv=async()=>{const k=++seq;const j=await api('/api/new',{a:'rule_prev',rule:R()});if(k!==seq||!$('#r_pv'))return;if(!j.ok||j.message){$('#r_pv').textContent=j.message||'';return}
    $('#r_pv').innerHTML=`符合 <b>${j.n.toLocaleString()}</b> 部（${fmtB(j.bytes)}）`+(j.sample||[]).map(x=>`<br><small data-oid="${x.id}" style="cursor:pointer;text-decoration:underline dotted">・${esc(x.name)}　${fmtT(x.dur||0)}　${x.h||'?'}p　${fmtB(x.size||0)}</small>`).join('')+(j.n>(j.sample||[]).length?'<br><small>…</small>':'')};
  tb.oninput=()=>pv();tb.onchange=()=>pv();pv();$('#r_pv').onclick=e=>{const o=e.target.closest('[data-oid]');if(o)openFile(+o.dataset.oid)};   // V0.3.28 例子點了打開看
  $('#r_go').onclick=async()=>{const r=R();const p=await api('/api/new',{a:'rule_prev',rule:r});if(!p.n)return toast(p.message||'沒有符合的');if(!confirm(`把 ${p.n} 部還沒分級的標成 ${r.grade}？（可以復原）`))return;const j=await api('/api/new',{a:'rule_apply',rule:r});toast(j.message||'');pv()};
  $('#r_undo').onclick=async()=>{if(!confirm('把上一次規則標的改回未分級？'))return;const j=await api('/api/new',{a:'rule_undo'});toast(j.message||'');pv()};
  const al=A=>{$('#r_al').innerHTML=(A||[]).map((x,i)=>`<div class="si row"><small class="grow">${[x.dur_lt?'短於 '+x.dur_lt+' 秒':'',x.dur_gt?'長於 '+(x.dur_gt/60)+' 分':'',x.h_lt?'低於 '+x.h_lt+'p':'',x.size_lt?'小於 '+x.size_lt+' MB':'',x.still_gt?'靜止超過 '+x.still_gt+'%':'',x.name?'檔名有「'+esc(x.name)+'」':''].filter(Boolean).join('、')} → <b>${x.grade}</b></small><button class="pill er" data-ad="${i}">🗑</button></div>`).join('')||'<div class="mu">（還沒有）</div>'};   // V0.3.21
  api(U('/api/new',{a:'rules_auto'}),undefined,{quiet:true}).then(j=>al(j.auto)).catch(()=>{});
  $('#r_aundo').onclick=async()=>{if(!confirm('把最近 24 小時自動規則分的改回未分級？（之後你自己改過的不動）'))return;const j=await api('/api/new',{a:'rule_auto_undo'});toast(j.message||'');pv()};   // V0.3.27
  $('#r_auto').onclick=async()=>{const j=await api('/api/new',{a:'rule_auto_add',rule:R()});toast(j.message||'');if(j.ok)al(j.auto)};
  $('#r_al').onclick=async e=>{const b=e.target.closest('[data-ad]');if(!b||!confirm('刪掉這條自動規則？'))return;const j=await api('/api/new',{a:'rule_auto_del',i:+b.dataset.ad});al(j.auto)}}
async function tChk(){const j=await api(U('/api/new',{a:'check'}));if(!j.ok)return;   // V0.2.73
  $('#tb').innerHTML=(j.rows||[]).map(r=>`<div class="si" style="${r.ok?'':'color:var(--orange,#ffb74d)'}">${r.ok?'✔':'⚠'} ${esc(r.t)}</div>`).join('')||'<div class="empty">沒有東西可以檢查</div>'}
async function tFprog(){const j=await api(U('/api/new',{a:'fprog'}));if(!j.ok)return;const R=j.rows||[];   // V0.2.84
  const nm=p=>p.split(/[\\/]/).filter(Boolean).slice(-2).join('\\')||p;
  $('#tb').innerHTML=`<input id="fpq" placeholder="找資料夾" style="width:100%;margin-bottom:8px"><div id="fpl"></div>`;
  const paint=()=>{const q=($('#fpq').value||'').toLowerCase();$('#fpl').innerHTML=R.filter(x=>x.folder.toLowerCase().includes(q)).slice(0,300).map(x=>`<div class="si" data-fd="${esc(x.folder)}" style="cursor:pointer"><b>📂 ${esc(nm(x.folder))}</b><br><small>${x.n.toLocaleString()} 部・${fmtB(x.bytes)}・<b>可以審 ${x.ready.toLocaleString()}</b>・還沒分 ${x.left.toLocaleString()}${x.f_bytes?'・F '+fmtB(x.f_bytes):''}${x.sa&&labOn('copy_to')?'・📤 S／A 傳了 '+x.sa_up+'／'+x.sa:''}</small>
    <div style="height:6px;border-radius:3px;background:rgba(127,127,127,.25);margin-top:4px;overflow:hidden"><i style="display:block;height:100%;width:${x.pct}%;background:${x.pct>=100?'#45d483':'#4dc9ff'}"></i></div></div>`).join('')||'<div class="empty">沒有</div>'};
  $('#fpq').oninput=paint;paint();$('#fpl').onclick=e=>{const b=e.target.closest('[data-fd]');if(!b)return;S.folder=b.dataset.fd;S.flt='ready';saveView();location.hash='fx'}}
async function tFind(){const tb=$('#tb');   // V0.3.07 ⌘ 快速找（電腦 Ctrl+K 的手機版）
  const P=[...TOOLS.flatMap(([g,L])=>L.map(x=>({k:x[0],t:x[1]+' '+x[2],s:x[3]}))),{k:'#fx',t:'▦ 檔案總管',s:''},{k:'/fc/',t:'🗂 整理（FileCompare）',s:''},{k:'#set',t:'⚙ 設定',s:''}];
  tb.innerHTML=`<input id="fq" placeholder="打字找：影片、資料夾、功能" style="width:100%;margin-bottom:8px" enterkeyhint="search"><div id="fl"></div>`;const q=$('#fq');setTimeout(()=>q.focus(),200);let seq=0;
  const paint=async()=>{const v=q.value.trim(),k=++seq;if(!v){$('#fl').innerHTML='';return}const lv=v.toLowerCase();
    const pg=P.filter(x=>(x.t+' '+x.s).toLowerCase().includes(lv)).slice(0,6);let j={};try{j=await api(U('/api/new',{a:'find',q:v}),undefined,{quiet:true})}catch(e){}if(k!==seq)return;
    const nm=p=>p.split(/[\\/]/).filter(Boolean).slice(-2).join('\\')||p;
    $('#fl').innerHTML=pg.map(x=>`<div class="si" data-pg="${esc(x.k)}">🧭 <b>${esc(x.t)}</b>${x.s?'<br><small class="mu">'+esc(x.s)+'</small>':''}</div>`).join('')+
      (j.folders||[]).map(f=>`<div class="si" data-fd="${esc(f.folder)}">📁 <b>${esc(nm(f.folder))}</b> <small class="mu">${f.n} 部</small></div>`).join('')+
      (j.files||[]).map(f=>`<div class="si" data-id="${f.id}">🎬 ${esc(f.name)} <small class="mu">${f.grade||'—'}・${fmtB(f.size)}・${fmtT(f.dur||0)}</small></div>`).join('')||'<div class="empty">找不到</div>'};
  let t_;q.oninput=()=>{clearTimeout(t_);t_=setTimeout(paint,250)};
  $('#fl').onclick=e=>{const a=e.target.closest('[data-pg]'),b=e.target.closest('[data-fd]'),c=e.target.closest('[data-id]');
    if(a){const k=a.dataset.pg;if(k.startsWith('/')){location.href=k;return}location.hash=k.startsWith('#')?k.slice(1):'tool/'+k}else if(b){S.folder=b.dataset.fd;S.flt='all';saveView();location.hash='fx'}else if(c)openFile(+c.dataset.id)}}
async function tFlow(){const j=await api(U('/api/new',{a:'flow'}));if(!j.ok)return;   // V0.3.18
  $('#tb').innerHTML=(j.rows||[]).map(([a,b])=>`<div class="si"><b>${esc(a)}</b><br><small>${esc(b)}</small></div>`).join('')+`<div class="mu">設定 → 實驗功能 最上面可以一次打開一組。</div>`}
async function tSched(){const j=await api(U('/api/new',{a:'sched'}));if(!j.ok)return;const H=[...Array(24).keys()];
  $('#tb').innerHTML=(j.on?'':`<div class="si" style="color:var(--orange)">⚠ 實驗工作區的「🕑 背景工作時段」還沒打開（設定 → 實驗功能），下面的設定先存著、打開才生效</div>`)+j.rows.map(r=>`<div class="si" data-kind="${r.kind}"><label><input type="checkbox" data-f="on" ${r.on?'checked':''}> <b>${esc(r.name)}</b></label><div class="row" style="margin-top:6px">只在 <select data-f="from">${H.map(h=>`<option ${h==r.from?'selected':''}>${h}</option>`).join('')}</select> 點到 <select data-f="to">${H.map(h=>`<option ${h==r.to?'selected':''}>${h}</option>`).join('')}</select> 點之間做</div></div>`).join('');
  $('#tb').onchange=async e=>{const b=e.target.closest('[data-kind]');if(!b)return;const g=f=>$(`[data-f="${f}"]`,b);const r=await api('/api/new',{a:'sched',kind:b.dataset.kind,on:g('on').checked,from:+g('from').value,to:+g('to').value});toast(r.ok?'✔ 已儲存':(r.message||'沒存到'))}}
function viewTool(k){V().innerHTML=`<div class="tlh"><button class="back" onclick="history.back()">‹</button><b>${toolName(k)}</b>${k==='ops'?'<a class="pill" href="/fc/?go=tool:ops" style="margin-left:auto;text-decoration:none">🧾 整理的操作紀錄 ›</a>':''}</div><div id="tb"></div>`;
  const fn=({unplug:tUnplug,bmall:tBmAll,week:tWeek,spr:tSpr,upb:tUpB,upold:tUpOld,flow:tFlow,find:tFind,fprog:tFprog,chk:tChk,rule:tRule,report:tReport,cre:tCre,sched:tSched,csv:tCsv,space:tSpace,empty:tEmpty,mon:tMon,pcs:tPcs,learn:tLearn,hz:tHz,dupes:tDupes,sim:tSim,like:tLike,stats:tStats,health:tHealth,conv:tConv,ops:tOps,log:tLog,upd:tUpd,rsplit:tRsplit,explore:tExplore})[k];if(fn)fn()}
let LG=[];
function showGroups(G,sim,msg){LG=G;const el=$('#tres');if(!el)return;$('#lmsg')&&($('#lmsg').textContent=msg||'');
  el.innerHTML=G.length?`<div class="row" style="margin:8px 0"><button class="pill wa" onclick="keepBig()">🏷 每組只留最大的：其他標 F</button></div>`+G.map((g,gi)=>`<div class="panel"><div class="mu">第 ${gi+1} 組</div><div class="list">${g.map(x=>`<div class="it" onclick="openFile(${x.id})">
   <div class="grow"><div>${x.big?'👑 ':''}${esc(x.name)}${x.me?' <span class="mu">◀你選的</span>':''}</div><div class="mu">${fmtB(x.size)} · ${x.dur?fmtT(x.dur):'—'} · ${x.w||'?'}×${x.h||'?'}${sim&&!x.big?' · 差 '+x.dist:''} · ${x.grade||'未分級'}</div><div class="mu" style="font-size:11px">${esc(x.folder)}</div></div></div>`).join('')}</div></div>`).join(''):'<div class="empty">沒有找到 👍</div>'}
async function keepBig(){const keep=new Set(),ids=[];LG.forEach(g=>{const b=g.slice().sort((a,c)=>(c.size||0)-(a.size||0)||((c.w||0)*(c.h||0)-(a.w||0)*(a.h||0)))[0];keep.add(b.id)});
  LG.forEach(g=>g.forEach(x=>{if(!keep.has(x.id)&&x.grade!=='F'&&!ids.includes(x.id))ids.push(x.id)}));if(!ids.length)return toast('沒有要標的');
  if(!confirm(`${LG.length} 組裡，除了每組最大的，其他 ${ids.length} 部標成 F？（只改分級，不搬不刪）`))return;
  const j=await api('/api/flags',{ids,grade:'F'});if(j.ok){S.undo=j.undo;undoBtn();toast(`${j.n} 部標成 F（右下「↩ 復原」可以改回）`);LG.forEach(g=>g.forEach(x=>{if(ids.includes(x.id))x.grade='F'}));showGroups(LG,true,$('#lmsg')?$('#lmsg').textContent:'')}}
async function tDupes(){$('#tb').innerHTML='<div class="mu" id="lmsg">找中…</div><div id="tres"></div>';const j=await api(U('/api/lab',{a:'dupes'}));showGroups(j.groups||[],false,`${(j.groups||[]).length} 組可能重複`)}
async function tSim(){$('#tb').innerHTML=`<div class="panel"><div class="row"><div class="seg" id="thr"><button data-v="6">嚴格</button><button data-v="10" class="on">一般</button><button data-v="14">寬鬆</button></div><button class="pill acc" id="simb" style="height:40px">🧬 開始找</button></div><div class="mu" id="lmsg" style="margin-top:6px">只看預覽圖，不讀影片、不碰 HDD。</div></div><div id="tres"></div>`;
  let thr=10;$('#thr').onclick=e=>{const b=e.target.closest('button');if(!b)return;thr=+b.dataset.v;$$('#thr button').forEach(x=>x.classList.toggle('on',x===b))};
  $('#simb').onclick=async()=>{if($('#simb').dataset.run==='1'){await api('/api/lab',{a:'similar',stop:1});toast('停止中…');return}await api('/api/lab',{a:'similar',thr});pollSim()};
  const j=await api(U('/api/lab',{a:'similar'}),undefined,{quiet:true});if(j.job){if(j.job.run)pollSim();else if(j.job.groups)showGroups(j.job.groups,true,j.job.msg)}}
async function pollSim(){const b=$('#simb');if(!b)return;b.dataset.run='1';b.textContent='⏹ 停止';const j=await api(U('/api/lab',{a:'similar'}),undefined,{quiet:true});const J=j.job||{};$('#lmsg')&&($('#lmsg').textContent='🧬 '+(J.msg||''));
  if(J.run)setTimeout(pollSim,1500);else{b.dataset.run='';b.textContent='🧬 開始找';if(J.groups)showGroups(J.groups,true,J.msg)}}
function tLike(){$('#tb').innerHTML='<div class="mu" id="lmsg">在影片頁按「⋯ → 🧬 找跟這部畫面相似的」</div><div id="tres"></div>'}
async function likeOf(id){if(!$('#tres'))return;$('#lmsg').textContent='🧬 找跟這部相似的…';const j=await api(U('/api/lab',{a:'like',id,thr:12}));const g=(j.groups||[])[0]||[];
  if(g.length<2){$('#lmsg').textContent=g.length?'沒有找到畫面相似的 👍':'這部還沒有預覽圖';$('#tres').innerHTML='';return}showGroups([g],true,'跟這部畫面相似的')}
async function rnd(){const j=await api(U('/api/lab',{a:'random',folder:S.folder}));if(j.ok)openFile(j.id);else toast(j.message)}
async function tStats(){$('#tb').innerHTML='<div class="empty">計算中…</div>';const j=await api(U('/api/lab',{a:'stats'}));if(!$('#tb'))return;const s=j.stats||{};const G={S:'S 無條件保存',A:'A 保存',E:'E 觀察',F:'F 刪除','':'未分級'};
  const bars=rows=>{const mx=Math.max(1,...rows.map(r=>r[2]||0));return rows.filter(r=>r[2]).map(r=>`<div class="row" style="margin:3px 0"><span style="width:96px">${esc(G[r[0]]??(r[0]||'?'))}</span><div class="pg grow"><i style="width:${(r[2]||0)*100/mx}%"></i></div><span class="mu" style="width:110px;text-align:right">${r[1]} 部 · ${fmtB(r[2])}</span></div>`).join('')};
  const gd=s.graded_days||[];const gm=Math.max(1,...gd.map(x=>x[1]));
  $('#tb').innerHTML=`<div class="panel"><b>💾 省下的空間</b><div>刪除原檔 <b style="color:var(--green)">${fmtB(s.freed_delete)}</b>　轉檔 <b style="color:var(--green)">${fmtB(s.freed_conv)}</b></div><div class="mu">剪了 ${(s.cuts||[0,0])[0]} 個初剪檔</div></div>
   ${gd.length?`<div class="panel"><b>🏷 最近每天分級</b>${gd.map(d=>`<div class="row" style="margin:3px 0"><span style="width:56px">${esc(String(d[0]).slice(5))}</span><div class="pg grow"><i style="width:${d[1]*100/gm}%;background:var(--orange)"></i></div><span class="mu" style="width:56px;text-align:right">${d[1]}</span></div>`).join('')}</div>`:''}
   <div class="panel"><b>🗂 待整理依分級</b>${bars(s.lib||[])}</div>${(s.arch||[]).length?`<div class="panel"><b>📦 已歸檔</b>${bars(s.arch)}</div>`:''}<div class="panel"><b>📐 解析度</b>${bars(s.res||[])}</div>`}
async function tHealth(){$('#tb').innerHTML='<div class="empty">檢查中…</div>';const j=await api(U('/api/lab',{a:'health'}));if(!$('#tb'))return;const H=j.health||{};
  $('#tb').innerHTML=Object.values(H).map(h=>`<div class="panel"><b>${esc(h.name)}（${h.n}）</b><div class="list">${h.rows.slice(0,30).map(x=>`<div class="it" onclick="openFile(${x.id})"><div class="grow">${esc(x.name)}<div class="mu">${fmtB(x.size)} · ${esc((x.th_err||x.probe_err||'').slice(0,80))}</div></div></div>`).join('')||'<div class="mu">沒有 👍</div>'}</div></div>`).join('')}
const CVK=[['nonmp4','非 MP4 → MP4'],['h264','H.264 → H.265'],['all','兩種都要'],['vs','🏷 已轉過 _VS']];
const CVS=[['smart','💡 最省空間優先'],['size_desc','大 → 小'],['size_asc','小 → 大'],['name','檔名'],['folder','資料夾'],['dur_desc','長度'],['mtime_desc','最新']];
const CV=Object.assign({tab:'pick',kind:'nonmp4',sort:'size_desc',exts:[],smin:0,smax:0,folder:'',df:'all',n:0,t:0},LS.get('cv',{}));if(!CV.v611){CV.v611=1;CV.sort='size_desc'}if(!Array.isArray(CV.fds))CV.fds=CV.folder?[CV.folder]:[];delete CV.folder;
async function chooseFolders(title,cur,done){const j=S.folders||await api('/api/folders');S.folders=j;const roots=j.roots||[];const P=new Set();(j.folders||[]).forEach(f=>{let p=f.path;const r=roots.find(x=>p.toLowerCase().startsWith(x.toLowerCase().replace(/[\\/]+$/,'')));
    while(r&&p.length>r.replace(/[\\/]+$/,'').length){P.add(p);const q=p.replace(/[\\/][^\\/]*$/,'');if(q===p)break;p=q}});
  const ALL=[...roots.map(r=>[r,1]),...[...P].filter(p=>!roots.some(r=>r.replace(/[\\/]+$/,'')===p)).sort((a,b)=>a.localeCompare(b)).map(p=>[p,0])];const SEL=new Set(cur);const d=document.createElement('div');d.className='sheet';
  d.innerHTML=`<div><div class="row"><h3 class="grow" style="margin:0">${esc(title)}</h3><button class="pill ok" data-ok>✔ 好了</button></div>${S.folder?`<button class="pill" data-cur style="margin-top:6px">＋ 檔案總管目前的：${esc(S.folder.split(/[\\/]/).filter(Boolean).pop())}</button>`:''}<input class="search" id="cfq" placeholder="🔍 找資料夾（每顆硬碟都找得到）" style="margin:8px 0"><div id="cfl"></div></div>`;
  const draw=q=>{const L=(q?ALL.filter(([p])=>p.toLowerCase().includes(q.toLowerCase())):ALL.filter(([p,r])=>r||SEL.has(p)||!roots.some(x=>p.slice(x.replace(/[\\/]+$/,'').length+1).split(/[\\/]/).filter(Boolean).length>1&&p.toLowerCase().startsWith(x.toLowerCase().replace(/[\\/]+$/,''))))).slice(0,300);
    $('#cfl',d).innerHTML=L.map(([p,r])=>`<button class="mi${SEL.has(p)?' cur':''}" data-p="${esc(p)}" style="text-align:left;word-break:break-all">${SEL.has(p)?'☑':'☐'} ${r?'💽':'📁'} ${esc(p)}</button>`).join('')+(L.length>=300?'<div class="mu">只列 300 個，打字找更多</div>':'')+(!q?'<div class="mu">只列硬碟和第一層，更深的請用上面搜尋</div>':'')};
  document.body.appendChild(d);const close=layer(d);draw('');$('#cfq',d).oninput=e=>draw(e.target.value.trim());
  d.onclick=e=>{if(e.target===d){close();return}if(e.target.closest('[data-ok]')){close().then(()=>done([...SEL]));return}if(e.target.closest('[data-cur]')){SEL.add(S.folder);draw($('#cfq',d).value.trim());return}
    const b=e.target.closest('[data-p]');if(b){const p=b.dataset.p;SEL.has(p)?SEL.delete(p):SEL.add(p);draw($('#cfq',d).value.trim())}}}
function goalHTML(G){const ok=G.eta_days!=null&&G.eta_days<=G.left_days;return `<div class="panel" style="border-color:rgba(69,212,131,.45)"><div class="row"><b class="grow">🎯 瘦身目標：${fmtB(G.b0)} → ${fmtB(G.target)}（${G.days} 天）</b><button class="pill" id="greset">↺ 重算</button></div>
  <div class="pg" style="margin:7px 0;height:10px"><i style="width:${G.pct}%;background:var(--green)"></i></div>
  <div class="mu" style="font-size:12.5px">已省 <b style="color:var(--green)">${fmtB(G.saved)}</b>（${G.pct.toFixed(1)}%）· 現在 ${fmtB(G.cur)}${G.pend?`（含 DELETE ${fmtB(G.pend)}）`:''} · 還要省 <b style="color:var(--orange)">${fmtB(G.need)}</b> · 剩 ${G.left_days.toFixed(1)} 天 · 每天要省 ${fmtB(G.need_day)}${G.pace?` · 最近每天省 ${fmtB(G.pace)}`:''}${G.eta_days?` · 預估 <b style="color:${ok?'var(--green)':'var(--red)'}">${G.eta_days.toFixed(0)} 天</b>`:''}</div>
  ${(G.tips||[]).map(t=>`<div class="mu" style="margin-top:4px">💡 ${esc(t)}</div>`).join('')}</div>`}
// V0.6.19 🗺 檔案總覽：像 Everything 搜尋＋像 TreeSize 看哪個資料夾最大；長按資料夾 → 轉檔
const EX=Object.assign({p:'',sort:'size',q:''},LS.get('ex',{}));
const EXC=['#3987e5','#45b5d4','#45d483','#c9b44d','#f0ad4e','#ff7e6b','#b48cff','#ff7eb6'];
function exSave(){LS.set('ex',EX)}
async function exConvMenu(path,name){toast('計算可以省多少…');
  const K=[['h264','H.264 → H.265'],['nonmp4','非 MP4 → MP4（H.265）'],['all','兩種都要']];
  const P=await Promise.all(K.map(([k])=>api(U('/api/conv2',{a:'plan',kind:k,sort:'size_desc',exts:'',smin:0,smax:0,folders:path,n:0,t:0}),undefined,{quiet:true}).catch(()=>({}))));
  const go=k=>{CV.fds=[path];CV.kind=k;CV.tab='pick';CV.exts=[];CV.n=0;CV.t=0;CV.sort='size_desc';LS.set('cv',CV);location.hash='tool/conv'};
  menu('🔁 轉檔「'+name+'」',[...K.map(([k,n],i)=>{const x=P[i]||{};return [`${n}：${(x.n_all||0).toLocaleString()} 部・預估省 ${fmtB(x.save_all||0)}`,()=>go(k)]}),
    ['📂 到檔案總管看這個資料夾',()=>{S.folder=path;S.flt='all';S.q='';S.sub=true;saveView();location.hash='fx'}],
    ['📋 複製路徑',async()=>{try{await navigator.clipboard.writeText(path);toast('📋 '+path)}catch(e){prompt('長按複製：',path)}}]])}
function exMix(j,tot){const bar=(L,lab)=>`<div style="display:flex;height:22px;border-radius:6px;overflow:hidden;gap:2px;margin:6px 0 3px">${L.map((x,i)=>`<div title="${esc(lab(x))} ${fmtB(x.size)}" style="flex:${x.size/tot};min-width:3px;background:${EXC[i%EXC.length]}"></div>`).join('')}</div><div class="mu" style="display:flex;flex-wrap:wrap;gap:3px 10px">${L.map((x,i)=>`<span><i style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${EXC[i%EXC.length]}"></i> ${esc(lab(x))} ${fmtB(x.size)}・${x.n.toLocaleString()}</span>`).join('')}</div>`;
  const C=j.codecs||[],X=j.exts||[],B=j.big||[],HT=j.hot||[];let h='';
  if(HT.length){const m=Math.max(1,...HT.map(x=>x.save));h+=`<div class="panel list"><b>💡 最值得轉的資料夾</b> <span class="mu">（不管第幾層，照轉完能省排；點一下 → 轉檔）</span>${HT.map(x=>`<div class="si" data-exh="${esc(x.path)}" data-exhn="${esc(x.name)}" style="cursor:pointer"><div style="display:flex;gap:8px"><b style="flex:1;min-width:0;word-break:break-all">📁 ${esc(x.name)}</b><b style="color:var(--green)">省 ${fmtB(x.save)}</b></div><div style="height:5px;background:var(--vline);border-radius:3px;margin:4px 0 2px"><div style="width:${x.save/m*100}%;height:5px;background:var(--green);border-radius:3px"></div></div><small class="mu" style="word-break:break-all">${esc(x.path)}・${x.conv_n.toLocaleString()} 部・${fmtB(x.conv_b)}</small></div>`).join('')}</div>`}
  if(C.length)h+=`<div class="panel"><b>🎞 影片編碼</b> <span class="mu">（H264 越多，轉 H.265 越能省）</span>${bar(C,x=>x.codec.toUpperCase())}<b style="display:block;margin-top:8px">📄 副檔名</b>${bar(X,x=>x.ext)}</div>`;
  if(B.length)h+=`<div class="panel list"><b>🐘 這裡最大的 ${B.length} 個檔</b>${B.map(r=>`<div class="si" data-exf="${r.id}" style="cursor:pointer"><div style="display:flex;gap:8px"><span style="flex:1;min-width:0;word-break:break-all">${esc(r.name)}</span><b>${fmtB(r.size)}</b></div><small class="mu" style="word-break:break-all">${esc(r.folder)}・${esc((r.vcodec||'').toUpperCase())}${r.cv===3?'・✔ 轉好':''}</small></div>`).join('')}</div>`;
  return h}
async function tExplore(){const tb=$('#tb');if(!tb)return;
  const crumbs=()=>{if(!EX.p)return '<b>💽 全部影片庫</b>';const parts=EX.p.split('\\').filter(Boolean);let acc='',h=`<a href="#" data-exp="">💽</a>`;
    parts.forEach((x,i)=>{acc=i?acc+'\\'+x:x;h+=` › <a href="#" data-exp="${esc(acc)}">${esc(x)}</a>`});return h};
  tb.innerHTML=`<input id="exq" class="ssearch" placeholder="🔍 找檔案（空白分開；也可以 size:>1g ext:mkv codec:h264 dur:>30m cv:no）" value="${esc(EX.q)}" style="width:100%;margin:2px 0 4px">
   <div class="chips" id="exch" style="margin:0 0 6px">${[['size:>1g','大於 1GB'],['size:>10g','大於 10GB'],['codec:h264','H.264'],['codec:hevc','H.265'],['ext:mkv,avi,wmv,mov,ts','非 MP4'],['dur:>60m','超過 1 小時'],['cv:no','還沒轉']].map(([t,n])=>`<button class="pill${EX.q.split(/\s+/).includes(t)?' on':''}" data-ext="${t}">${n}</button>`).join('')}</div>
   <div class="row" style="align-items:center;gap:6px;flex-wrap:wrap"><div id="excr" style="flex:1;min-width:0;word-break:break-all">${crumbs()}</div>
   <div class="seg" id="exs">${[['size','大小'],['n','檔數'],['save','可省'],['name','名稱']].map(([k,n])=>`<button data-k="${k}"${EX.sort===k?' class="on"':''}>${n}</button>`).join('')}</div></div>
   <div id="exb"><div class="empty">讀取中…</div></div><div style="height:70px"></div>`;
  $('#exch').onclick=e=>{const b=e.target.closest('[data-ext]');if(!b)return;const t=b.dataset.ext,L=EX.q.split(/\s+/).filter(Boolean);EX.q=(L.includes(t)?L.filter(x=>x!==t):[...L,t]).join(' ');exSave();tExplore()};
  let qt=0;$('#exq').oninput=e=>{clearTimeout(qt);qt=setTimeout(()=>{EX.q=e.target.value;exSave();draw()},300)};
  $('#exs').onclick=e=>{const b=e.target.closest('button');if(!b)return;EX.sort=b.dataset.k;exSave();$$('#exs button').forEach(x=>x.classList.toggle('on',x===b));draw()};
  $('#excr').onclick=e=>{const a=e.target.closest('[data-exp]');if(!a)return;e.preventDefault();EX.p=a.dataset.exp;EX.q='';$('#exq').value='';exSave();tExplore()};
  const draw=async()=>{const b=$('#exb');if(!b)return;
    if(EX.q.trim()){const j=await api(U('/api/explore',{q:EX.q,prefix:EX.p,sort:EX.sort==='name'?'name':'size',limit:300}));if(!j.ok||!$('#exb'))return;
      b.innerHTML=`<div class="mu" style="margin:6px 0">${EX.p?'在 '+esc(EX.p)+' 底下':'全部'}找到 <b>${j.n.toLocaleString()}${j.more?'+':''}</b> 個・${fmtB(j.sum)}${j.more?'（只列前 300 個，多打幾個字縮小）':''}</div><div class="panel list">`+
       (j.rows||[]).map(r=>`<div class="si" data-exf="${r.id}" style="cursor:pointer"><div style="display:flex;gap:8px"><b style="flex:1;min-width:0;word-break:break-all">${esc(r.name)}</b><b>${fmtB(r.size)}</b></div><small class="mu" style="word-break:break-all">${esc(r.folder)}・${esc((r.vcodec||'').toUpperCase())}${r.cv===3?'・✔ 轉好':''}</small></div>`).join('')+'</div>'||'<div class="empty">沒有</div>';
      b.onclick=e=>{const r=e.target.closest('[data-exf]');if(r)openFile(+r.dataset.exf)};return}
    const j=await api(U('/api/explore',{prefix:EX.p,sort:EX.sort}));if(!j.ok||!$('#exb'))return;const I=j.items||[],T=j.tot||{},H=j.here||{};
    const mx=Math.max(1,...I.map(x=>EX.sort==='n'?x.n:EX.sort==='save'?x.save:x.size));const tot=Math.max(1,T.size||0);
    const top=I.slice().sort((a,b)=>b.size-a.size).slice(0,7);const rest=Math.max(0,(T.size||0)-top.reduce((a,x)=>a+x.size,0));
    const strip=`<div style="display:flex;height:34px;border-radius:8px;overflow:hidden;gap:2px;margin:6px 0 4px">${top.map((x,i)=>`<div title="${esc(x.name)} ${fmtB(x.size)}" data-exd="${esc(x.path)}" style="flex:${x.size/tot};min-width:3px;background:${EXC[i]};cursor:pointer;display:flex;align-items:center;padding:0 4px;overflow:hidden"><small style="color:#fff;white-space:nowrap;text-overflow:ellipsis;overflow:hidden">${x.size/tot>.08?esc(x.name):''}</small></div>`).join('')}${rest>0?`<div title="其他 ${fmtB(rest)}" style="flex:${rest/tot};min-width:3px;background:#5c6168"></div>`:''}</div>
      <div class="mu" style="display:flex;flex-wrap:wrap;gap:4px 10px;margin-bottom:6px">${top.map((x,i)=>`<span><i style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${EXC[i]}"></i> ${esc(x.name)} ${Math.round(x.size/tot*100)}%</span>`).join('')}${rest>0?`<span><i style="display:inline-block;width:9px;height:9px;border-radius:2px;background:#5c6168"></i> 其他 ${Math.round(rest/tot*100)}%</span>`:''}</div>`;
    b.innerHTML=`<div class="panel"><div style="display:flex;gap:10px;flex-wrap:wrap"><div><small class="mu">這裡總共</small><br><b style="font-size:20px">${fmtB(T.size)}</b></div><div><small class="mu">檔案</small><br><b style="font-size:20px">${(T.n||0).toLocaleString()}</b></div><div><small class="mu">能轉的</small><br><b style="font-size:20px">${(T.conv_n||0).toLocaleString()}</b></div><div><small class="mu">轉完預估省</small><br><b style="font-size:20px;color:var(--green)">${fmtB(T.save)}</b></div></div>
      ${I.length?strip:''}${EX.p&&T.conv_n?`<button class="pill acc" id="exconv" style="width:100%;margin-top:4px">🔁 轉檔這個資料夾（預估省 ${fmtB(T.save)}）</button>`:''}</div>
      <div class="panel list">${I.map(x=>{const v=EX.sort==='n'?x.n:EX.sort==='save'?x.save:x.size;return `<div class="si" data-exd="${esc(x.path)}" data-exn="${esc(x.name)}" style="cursor:pointer;position:relative"><div style="display:flex;gap:8px;align-items:center"><b style="flex:1;min-width:0;word-break:break-all">📁 ${esc(x.name)}</b><b>${fmtB(x.size)}</b><button class="pill" data-exm="1" style="padding:2px 10px">⋯</button></div>
        <div style="height:6px;background:var(--vline);border-radius:3px;margin:5px 0 3px;overflow:hidden;display:flex"><div style="width:${v/mx*100}%;background:#3987e5;border-radius:3px;display:flex;justify-content:flex-end"><div style="width:${x.size?Math.min(100,x.conv_b/x.size*100):0}%;background:var(--green)"></div></div></div>
        <small class="mu">${x.n.toLocaleString()} 個檔・佔 ${Math.round(x.size/tot*100)}%${x.conv_n?`・能轉 ${x.conv_n.toLocaleString()} 部，預估省 <b style="color:var(--green)">${fmtB(x.save)}</b>`:''}</small></div>`}).join('')}
      ${H.n?`<div class="si"><small class="mu">📄 直接放在這一層的檔案：${H.n.toLocaleString()} 個・${fmtB(H.size)}</small></div>`:''}${!I.length&&!H.n?'<div class="empty">這裡沒有影片</div>':''}</div>
      <div class="mu"><span style="color:#3987e5">■</span> 大小　<span style="color:var(--green)">■</span> 能轉 H.265 的部分・長按（或按 ⋯）資料夾 → 轉檔／到檔案總管</div>`+exMix(j,tot);
    const ec=$('#exconv');if(ec)ec.onclick=()=>exConvMenu(EX.p,EX.p.split('\\').pop()||EX.p);
    let lp=0,lpd=false;const down=e=>{const r=e.target.closest('[data-exn]');if(!r)return;lpd=false;clearTimeout(lp);lp=setTimeout(()=>{lpd=true;try{navigator.vibrate&&navigator.vibrate(20)}catch(x){}exConvMenu(r.dataset.exd,r.dataset.exn)},550)};
    b.onpointerdown=down;b.onpointerup=b.onpointercancel=b.onpointerleave=()=>clearTimeout(lp);b.oncontextmenu=e=>{if(e.target.closest('[data-exn]'))e.preventDefault()};
    b.onclick=e=>{if(lpd){lpd=false;return}const ff=e.target.closest('[data-exf]');if(ff)return openFile(+ff.dataset.exf);const hh=e.target.closest('[data-exh]');if(hh)return exConvMenu(hh.dataset.exh,hh.dataset.exhn);const m=e.target.closest('[data-exm]'),r=e.target.closest('[data-exd]');if(!r)return;if(m){const row=m.closest('[data-exn]');return exConvMenu(row.dataset.exd,row.dataset.exn)}EX.p=r.dataset.exd;exSave();tExplore()}};
  draw()}
async function tConv(){LS.set('cv',CV);
  $('#tb').innerHTML=`<div id="cvg"></div><div class="seg" id="cvtab" style="margin-bottom:8px;width:100%">${[['pick','➕ 選檔'],['run','⚙ 轉檔中'],['done','✔ 完成'],['fail','✖ 失敗']].map(([k,n])=>`<button data-k="${k}" style="flex:1"${CV.tab===k?' class="on"':''}>${n}</button>`).join('')}</div><div id="cvb"><div class="empty">讀取中…</div></div><div style="height:70px"></div>`;
  $('#cvtab').onclick=e=>{const b=e.target.closest('button');if(!b)return;CV.tab=b.dataset.k;CVSEL.clear();tConv()};
  ({pick:cvPick,run:cvRun,done:cvDone,fail:cvFail})[CV.tab]()}
async function cvPick(){const b=$('#cvb');if(!b)return;
  b.innerHTML=`<div class="fr"><b>要轉的</b><div class="seg" id="cvk">${CVK.map(([k,n])=>`<button data-k="${k}"${CV.kind===k?' class="on"':''}>${n}</button>`).join('')}</div></div>
   <div class="fr"><b>排序</b><select id="cvs" class="grow">${CVS.map(([k,n])=>`<option value="${k}"${CV.sort===k?' selected':''}>${n}</option>`).join('')}</select></div>
   <div class="fr"><b>大小</b><input id="cvmin" type="number" inputmode="numeric" placeholder="最小 MB" value="${CV.smin||''}" style="width:30%"><span>～</span><input id="cvmax" type="number" inputmode="numeric" placeholder="最大 MB" value="${CV.smax||''}" style="width:30%"></div>
   <div class="fr"><b>資料夾</b><div class="extg" id="cvfds">${CV.fds.map((f,i)=>`<button class="pill on" data-fdx="${i}" title="${esc(f)}">📁 ${esc(f.split(/[\\/]/).filter(Boolean).pop()||f)} ✕</button>`).join('')||'<span class="mu" style="align-self:center">全部範圍</span>'}<button class="pill" id="cvfd">＋ 資料夾</button></div></div>
   <div class="fr"><b>類型</b><div class="extg" id="cvx"><span class="mu">讀取中…</span></div></div>
   <div class="mu" id="cvszh" style="margin:-2px 0 6px 64px"></div>
   <div class="panel"><b>📏 數量與目標</b> <span class="mu">（照排序從第一部開始取）</span>
    <div class="fr" style="margin-top:6px"><b>數量</b><button class="pill" id="cvnm">－</button><input id="cvn" type="number" inputmode="numeric" min="0" placeholder="全部" value="${CV.n||''}" style="width:28%"><button class="pill" id="cvnp">＋</button><button class="pill" id="cvna">全部</button></div>
    <input id="cvsl" type="range" min="0" max="1" value="0" style="width:100%">
    <div class="fr"><b>目標省</b><input id="cvt" type="number" inputmode="numeric" min="0" placeholder="不設" value="${CV.t||''}" style="width:34%"><span>GB</span><span class="mu" id="cvtt"></span></div>
    <div id="cvpi" class="mu" style="margin-top:4px">計算中…</div></div>
   <div class="panel"><div id="cvsum" class="mu">讀取中…</div><button class="pill acc" id="cvgo" style="width:100%;margin-top:8px;padding:10px" disabled>▶ 範圍內全部加入轉檔</button></div><div class="panel list" id="cvl"></div>`;
  let CVP=null,cvT=0;
  const cvPlan=async()=>{const pq={a:'plan',kind:CV.kind,sort:CV.sort,exts:CV.exts.join(','),smin:CV.smin||0,smax:CV.smax||0,folders:CV.fds.join('|'),n:CV.n||0,t:CV.t||0};
    const P=await api(U('/api/conv2',pq));if(!P.ok||!$('#cvpi'))return;CVP=P;const N=P.n_all||0;
    $('#cvszh').textContent=N?`範圍內：最小 ${fmtB(P.min_all)}、最大 ${fmtB(P.max_all)}`:'';
    $('#cvsl').max=Math.max(1,N);if(P.auto){CV.n=P.n;$('#cvn').value=P.n;LS.set('cv',CV)}$('#cvsl').value=CV.n||Math.max(1,N);
    $('#cvtt').textContent=CV.t>=1000?`＝${(CV.t/1000).toFixed(2)} TB`:'';
    let h=N?`前 <b>${P.n.toLocaleString()}</b> 部（共 ${N.toLocaleString()}）：大小 <b>${fmtB(P.sel_max)}～${fmtB(P.sel_min)}</b>・合計 ${fmtB(P.sel_bytes)} → 預估省 <b style="color:var(--green)">${fmtB(P.sel_save)}</b>`:'範圍內沒有可以轉的檔';
    if(CV.t&&N)h+=P.reach?`<br>🎯 目標省 ${fmtB(CV.t*1e9)}：大約要轉 <b>${P.n.toLocaleString()}</b> 部（已自動帶入，範圍改了會重算）`:`<br><span style="color:var(--orange)">🎯 範圍內全部轉完也只能省大約 ${fmtB(P.save_all)}</span>`;
    if(N)h+=`<br>全部 ${N.toLocaleString()} 部轉完預估省 ${fmtB(P.save_all)}`;$('#cvpi').innerHTML=h;
    $('#cvgo').textContent=N&&P.n<N?`▶ 加入前 ${P.n.toLocaleString()} 部轉檔`:'▶ 範圍內全部加入轉檔'};
  const setN=(v,keepT)=>{CV.n=Math.max(0,Math.round(+v||0));if(!keepT){CV.t=0;$('#cvt').value=''}$('#cvn').value=CV.n||'';LS.set('cv',CV);clearTimeout(cvT);cvT=setTimeout(cvPlan,250)};
  $('#cvn').onchange=e=>setN(e.target.value);$('#cvsl').oninput=e=>{$('#cvn').value=e.target.value};$('#cvsl').onchange=e=>setN(e.target.value);
  $('#cvnm').onclick=()=>setN(Math.max(0,(CV.n||(CVP?CVP.n_all:0))-50));$('#cvnp').onclick=()=>setN((CV.n||0)+50);$('#cvna').onclick=()=>setN(0);
  $('#cvt').onchange=e=>{CV.t=Math.max(0,+e.target.value||0);LS.set('cv',CV);cvPlan()};
  cvPlan();
  $('#cvk').onclick=e=>{const x=e.target.closest('button');if(!x)return;CV.kind=x.dataset.k;CV.exts=[];LS.set('cv',CV);cvPick()};
  $('#cvs').onchange=e=>{CV.sort=e.target.value;LS.set('cv',CV);cvPick()};
  const num=()=>{CV.smin=+$('#cvmin').value||0;CV.smax=+$('#cvmax').value||0;LS.set('cv',CV);cvPick()};$('#cvmin').onchange=num;$('#cvmax').onchange=num;
  $('#cvfd').onclick=()=>chooseFolders('轉檔範圍（可以選好幾個，含子資料夾）',CV.fds,L=>{CV.fds=L;LS.set('cv',CV);cvPick()});
  $('#cvfds').onclick=e=>{const x=e.target.closest('[data-fdx]');if(!x)return;CV.fds.splice(+x.dataset.fdx,1);LS.set('cv',CV);cvPick()};
  const q={a:'cand',kind:CV.kind,sort:CV.sort,exts:CV.exts.join(','),smin:CV.smin||0,smax:CV.smax||0,folders:CV.fds.join('|')};
  const j=await api(U('/api/conv2',q));if(!j.ok||!$('#cvl'))return;const ratio=(j.ratio&&j.ratio[1])?j.ratio[0]:0.5;
  $('#cvx').innerHTML=(j.exts||[]).map(([e,n,bz])=>`<button class="pill ${CV.exts.includes(e)?'on':''}" data-e="${e}">${CV.exts.includes(e)?'✔ ':''}${e.slice(1)} ${n}</button>`).join('')||'<span class="mu">沒有</span>';
  $('#cvx').onclick=e=>{const x=e.target.closest('[data-e]');if(!x)return;const k=x.dataset.e;CV.exts=CV.exts.includes(k)?CV.exts.filter(z=>z!==k):[...CV.exts,k];LS.set('cv',CV);cvPick()};
  $('#cvsum').innerHTML=`範圍內 <b>${j.n.toLocaleString()}</b> 部 · ${fmtB(j.bytes)} · 轉完預估省 <b style="color:var(--green)">${fmtB(j.est_save!=null?j.est_save:j.bytes*(1-ratio))}</b>${j.est_hit?`（${j.est_hit} 部照📈同類經驗估）`:''}${j.ratio&&j.ratio[1]?`（其他照已轉好的平均 ${Math.round(ratio*100)}%）`:'（先用 50% 估）'}${j.vs_n?`<div style="color:var(--orange);margin-top:4px">🏷 另外 ${j.vs_n.toLocaleString()} 部檔名有 _VS（已轉過）沒列；真的要再轉，上面選「🏷 已轉過 _VS」</div>`:''}`;
  if(j.why)$('#cvsum').innerHTML+=`<div style="color:#ff9f43;margin-top:4px">ℹ ${esc(j.why)}</div>`;$('#cvgo').disabled=!j.n;$('#cvgo').onclick=async()=>{const lim0=CVP&&CVP.n_all&&CVP.n<CVP.n_all?CVP.n:0;if(!confirm(`把範圍內${lim0?'前 '+lim0.toLocaleString():' '+j.n.toLocaleString()} 部照「${(CVS.find(x=>x[0]===CV.sort)||['',''])[1]}」加入轉檔？\n轉成 H.265 MP4 放在原本的資料夾；原檔先搬到該硬碟最外層的 DELETE；預覽圖、分級都沿用。`))return;
    const lim=CVP&&CVP.n_all&&CVP.n<CVP.n_all?CVP.n:0;
    const r=await api('/api/conv2',{a:'add_filtered',kind:CV.kind,sort:CV.sort,exts:CV.exts,smin:CV.smin,smax:CV.smax,folders:CV.fds,limit:lim});toast(r.message||'');CV.tab='run';tConv()};
  $('#cvl').innerHTML=(j.rows||[]).map(r=>`<div class="it" data-id="${r.id}"><div class="grow"><div style="word-break:break-all">${esc(r.name)}</div><div class="mu">${esc(r.ext.slice(1))} · ${esc(r.vcodec||'?')} · ${r.w?r.w+'×'+r.h:''} · ${r.dur?fmtT(r.dur):'—'} · ${fmtB(r.size)} · 預估省 <span style="color:var(--green)">${fmtB(r.size*(1-(r.est_ratio!=null?r.est_ratio:ratio)))}</span>${r.cv_state==4?' · <span style="color:var(--red)">上次失敗</span>':''}</div></div><button class="pill" data-add="${r.id}">＋</button></div>`).join('')+(j.n>(j.rows||[]).length?`<div class="mu" style="padding:8px">只列前 ${(j.rows||[]).length} 部</div>`:'')||'<div class="empty">範圍內沒有要轉的 👍</div>';
  $('#cvl').onclick=async e=>{const a=e.target.closest('[data-add]');if(a){const r=await api('/api/conv2',{a:'add',ids:[+a.dataset.add]});toast(r.message||'');a.textContent='✔';a.disabled=true;return}const it=e.target.closest('.it[data-id]');if(it)openFile(+it.dataset.id)}}
async function cvRun(){const b=$('#cvb');if(!b)return;const j=await api(U('/api/conv2',{a:'queue'}));if(!j.ok||!$('#cvb'))return;
  const tot=(j.rows||[]).reduce((a,r)=>a+(r.size||0),0);
  b.innerHTML=`<div class="row" style="margin-bottom:8px"><button class="pill ${j.paused?'ok':'wa'}" id="cvp">${j.paused?'▶ 轉檔繼續':'⏸ 轉檔暫停'}</button><select id="cvrs">${CVS.map(([k,n])=>`<option value="${k}"${k==='size_desc'?' selected':''}>${n}</option>`).join('')}</select><button class="pill" id="cvro">重新排序</button><button class="pill er" id="cvca">✖ 全部取消</button></div>
   <div class="mu" style="margin-bottom:6px">轉檔中＋排隊 ${j.total.toLocaleString()} 部 · ${fmtB(tot)}　點一筆＝拿掉</div>
   ${j.eta&&j.eta.eta?`<div class="panel" style="margin-bottom:6px">⏱ 全部大約還要 <b style="color:var(--accent)">${eta(j.eta.eta)}</b>（${new Date(j.eta.done_at*1000).toLocaleString([], {month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})} 左右轉完；保守估、多抓）<div class="mu">${esc(j.eta.basis)}</div></div>`:(j.eta&&j.eta.n?`<div class="mu" style="margin-bottom:6px">⏱ ${esc(j.eta.basis)}</div>`:'')}<div class="panel list">${(j.rows||[]).map(r=>`<div class="it" data-id="${r.id}"><div class="grow"><div style="word-break:break-all">${r.cv_state==2?'⚙ ':''}${esc(r.name)}</div>
   <div class="mu">${esc(r.ext.slice(1))} · ${esc(r.vcodec||'')} · ${fmtB(r.size)}${r.cv_state==2?` · ${r.pct||0}% ${esc(r.enc||'')} ${esc(r.speed||'')}${r.left?' · 還要 '+fmtT(r.left):''}`:' · 排隊'}</div>${r.cv_state==2?`<div class="pg" style="margin-top:4px"><i style="width:${r.pct||0}%"></i></div>`:''}</div></div>`).join('')||'<div class="empty">沒有在轉 👍</div>'}</div>`;
  $('#cvp').onclick=()=>ctl(j.paused?'resume_cv':'pause_cv').then(()=>setTimeout(cvRun,500));$('#cvro').onclick=async()=>{const r=await api('/api/conv2',{a:'reorder',sort:$('#cvrs').value});toast(r.message||'');cvRun()};
  $('#cvca').onclick=async()=>{if(!confirm('取消全部排隊中的轉檔（正在轉的也停）？'))return;const r=await api('/api/conv2',{a:'cancel',all:true});toast(r.message||'');cvRun()};
  b.querySelector('.panel').onclick=async e=>{const it=e.target.closest('.it[data-id]');if(!it)return;if(!confirm('從轉檔排隊拿掉這部？'))return;const r=await api('/api/conv2',{a:'cancel',ids:[+it.dataset.id]});toast(r.message||'');cvRun()};
  clearTimeout(CV._t);CV._t=setTimeout(()=>{if($('#cvb')&&CV.tab==='run'&&!document.hidden)cvRun()},4000)}
const CVDS=[['t_desc','最新轉好'],['save_desc','省最多'],['size_desc','原檔大 → 小'],['name','檔名']];const CVSEL=new Set();
async function cvDone(){const b=$('#cvb');if(!b)return;const D=await api(U('/api/conv2',{a:'done',q:CV.dq||'',sort:CV.dsort||'t_desc'}));if(!D.ok||!$('#cvb'))return;
  let L=D.rows||[];const F={all:r=>1,pend:r=>r.del_exists,warn:r=>!r.cv_ssim||r.cv_ssim<0.95,unseen:r=>!(r.viewed&&r.viewed>=(r.cv_t||0))};L=L.filter(F[CV.df]||F.all);
  const T_=D.today||{n:0,save:0},S_=D.session||{n:0,save:0,t0:Date.now()/1000};
  b.innerHTML=`<div class="panel"><div>📅 今天轉好 <b>${T_.n.toLocaleString()}</b> 部，省下 <b style="color:var(--green)">${fmtB(T_.save)}</b>　🔁 這次（${new Date(S_.t0*1000).toLocaleString([],{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})} 打開後）<b>${S_.n.toLocaleString()}</b> 部，省下 <b style="color:var(--green)">${fmtB(S_.save)}</b></div>
   <div class="mu">全部：完成 <b>${D.n.toLocaleString()}</b> 部：${fmtB(D.osz)} → ${fmtB(D.nsz)}，省下 ${fmtB(Math.max(0,D.osz-D.nsz))}</div>
   ${D.offline_n?`<div class="mu" style="color:var(--orange);margin:4px 0">💤 ${(D.offline_drives||[]).map(esc).join('、')} 硬碟離線：${D.offline_n} 部暫時讀不到（檔案沒有刪），接回來就恢復</div>`:''}
   <div class="mu">${D.pending?`DELETE 裡還有 <b style="color:var(--orange)">${D.pending}</b> 個原檔、${fmtB(D.pending_bytes)} ${D.pending_by&&Object.keys(D.pending_by).length?'（'+Object.entries(D.pending_by).map(([k,v])=>esc(k)+'\\DELETE '+v[0]+' 個・'+fmtB(v[1])).join('、')+'）':''}等你抽檢後刪除`:'DELETE 裡沒有等著刪的原檔'}</div>
   ${D.big?`<div style="color:var(--red);margin-top:6px">⚠ 有 <b>${D.big}</b> 部轉完反而變大（多佔 ${fmtB(D.big_bytes)}）：按「↩ 變大的還原」刪掉轉大的、原檔搬回原位</div>`:''}
   ${(D.rows||[]).some(r=>r.src_exists&&!r.del_exists)?`<div class="mu" style="margin-top:6px">原檔還在原位的：每筆選「留 MP4」（原檔搬到 DELETE）或「留原檔」（刪掉 MP4），同一個資料夾不留兩份</div>`:''}
   <div class="row" style="margin-top:8px"><button class="pill" id="cvtag">🏷 轉好的加上 _VS</button><button class="pill" id="cvrand">🎲 隨機抽 5 部抽檢</button>${D.big?`<button class="pill" id="cvundo" style="color:var(--red)">↩ 變大的還原（${D.big}）</button>`:''}<button class="pill" id="cvrv">🔍 沒到目標的重新驗證</button><button class="pill ok" id="cvredo">🔁 沒到目標的全部重轉</button><button class="pill" id="cvlow" style="color:var(--orange)">↩ 畫質沒到目標的還原</button><span class="grow"></span><button class="pill" id="cvpall" style="background:#c62845;border-color:#c62845;color:#fff" ${D.pending?'':'disabled'}>🗑 刪除已轉檔完成的原檔</button></div></div>
   <div class="row" style="margin:8px 0;gap:6px"><input class="search grow" id="cvdq" placeholder="🔍 找檔名（按 Enter）" value="${esc(CV.dq||'')}" style="min-width:0"><select id="cvds">${CVDS.map(([k,n])=>`<option value="${k}"${(CV.dsort||'t_desc')===k?' selected':''}>${n}</option>`).join('')}</select><button class="pill ${CV.dms?'on':''}" id="cvms">☑ 多選</button></div>
   ${CV.dms?`<div class="panel" id="cvsb" style="position:sticky;top:0;z-index:5"><div class="mu">已選 <b>${[...CVSEL].filter(i=>L.some(r=>r.id===i)).length}</b> 部（點清單勾選）</div><div class="row" style="margin-top:6px;gap:6px"><button class="pill" data-sa="all">全選</button><button class="pill" data-sa="none">全不選</button><button class="pill ok" data-sa="redo">🔁 重轉</button><button class="pill acc" data-sa="redo_force">🎯 重轉到 0.985（插隊）</button><button class="pill" data-sa="stage">留 MP4</button><button class="pill" data-sa="restore">↩ 原檔搬回</button><button class="pill" data-sa="reverify">🔍 重新驗證</button><button class="pill" data-sa="purge" style="background:#c62845;border-color:#c62845;color:#fff">🗑 刪原檔</button></div></div>`:''}
   <div class="seg" id="cvdf" style="margin-bottom:8px;width:100%">${[['all','全部'],['pend','原檔在 DELETE'],['warn','⚠ 要看'],['unseen','沒抽檢']].map(([k,n])=>`<button data-k="${k}" style="flex:1"${CV.df===k?' class="on"':''}>${n}</button>`).join('')}</div>
   <div class="mu" style="margin-bottom:6px">點一筆＝播放轉好的 MP4 抽檢（看過會打 ✔）</div><div class="panel list">${L.map(r=>{const ss=r.cv_ssim||0,seen=r.viewed&&r.viewed>=(r.cv_t||0);return `<div class="it${CV.dms&&CVSEL.has(r.id)?' sel':''}" data-id="${r.id}"><div class="grow"><div style="word-break:break-all">${CV.dms?(CVSEL.has(r.id)?'☑ ':'☐ '):''}${seen?'✔ ':''}${esc(r.name)}</div>
   <div class="mu">${fmtB(r.osz)} → ${fmtB(r.nsz)} · ${r.big?'<span style="color:var(--red)">⚠ 變大</span>':'省 <span style="color:var(--green)">'+fmtB(Math.max(0,r.osz-r.nsz))+'</span>'}${r.osz?' · '+Math.round(r.nsz*100/r.osz)+'%':''} · ${ss>=0.985?'<span style="color:var(--green)">✔ 驗證 '+ss.toFixed(3)+'</span>':ss?'<span style="color:var(--orange)">⚠ '+ss.toFixed(3)+'</span>':'— 沒驗證'} · ${r.offline?'<span style="color:var(--orange)">💤 硬碟離線（檔案沒刪）</span>':r.del_exists?'原檔在 DELETE':r.src_exists?'原檔在原位':'原檔已刪'}${r.cv_how?' · '+esc(({full:'🎯 完整測試',lite:'🎯 少量確認',quick:'🎯 快速確認',trust:'🎯 直接套用',fixed:'固定',remux:'只換外殼'})[String(r.cv_how).replace('redo-','')]||r.cv_how)+(r.cv_cq?' CQ '+r.cv_cq:''):''}</div></div>
   ${r.del_exists&&(r.cv_ssim>=0.999||r.cv_how==='remux')?`<button class="pill acc" data-force="${r.id}">🎯 重轉到 0.985（插隊）</button>`:''}${r.del_exists?`<button class="pill" data-rest="${r.id}">↩ 搬回</button>`:''}${r.src_exists&&!r.del_exists?`<button class="pill" data-stage="${r.id}">留 MP4</button><button class="pill" data-undo="${r.id}">留原檔</button>`:''}${r.big&&r.del_exists?`<button class="pill" data-undo="${r.id}" style="color:var(--red)">↩ 還原</button>`:''}</div>`}).join('')||'<div class="empty">沒有</div>'}</div>`;
  $('#cvdf').onclick=e=>{const x=e.target.closest('button');if(!x)return;CV.df=x.dataset.k;LS.set('cv',CV);cvDone()};
  $('#cvdq').onchange=e=>{CV.dq=e.target.value.trim();LS.set('cv',CV);cvDone()};$('#cvds').onchange=e=>{CV.dsort=e.target.value;LS.set('cv',CV);cvDone()};
  $('#cvms').onclick=()=>{CV.dms=!CV.dms;CVSEL.clear();LS.set('cv',CV);cvDone()};
  if($('#cvsb'))$('#cvsb').onclick=async e=>{const x=e.target.closest('[data-sa]');if(!x)return;const k=x.dataset.sa;
    if(k==='all'){L.forEach(r=>CVSEL.add(r.id));return cvDone()}if(k==='none'){CVSEL.clear();return cvDone()}
    const ids=[...CVSEL].filter(i=>L.some(r=>r.id===i));if(!ids.length)return toast('先點清單勾選');
    const sel=L.filter(r=>ids.includes(r.id)),pend=sel.filter(r=>r.del_exists);
    const Q={redo:`用 DELETE 裡的原檔重轉這 ${ids.length} 部？（🎯 自動方式；到目標才換掉舊的 MP4）`,redo_force:`這 ${ids.length} 部一定整部重壓到 0.985、排到隊伍最前面？`,stage:`這 ${ids.length} 部留 MP4（原檔搬到該硬碟的 DELETE）？`,
      restore:`把這 ${ids.length} 部的原檔從 DELETE 搬回原位？`,reverify:`這 ${ids.length} 部重新驗證畫質？`,purge:`永久刪除這 ${pend.length} 部在 DELETE 裡的原檔（${fmtB(pend.reduce((a,r)=>a+(r.osz||0),0))}）？刪了救不回來（轉好的 MP4 不會動）。`}[k];
    if(k==='purge'&&!pend.length)return toast('選的這幾部原檔都不在 DELETE 裡');if(!confirm(Q))return;if(k==='purge'&&pend.length>20&&!confirm('再確認一次：真的要刪？'))return;
    const r=await api('/api/conv2',{a:k,ids:k==='purge'?pend.map(x=>x.id):ids});toast(r.message||'',6000);CVSEL.clear();cvDone()};
  const playIt=async id=>{const r=(D.rows||[]).find(x=>x.id===id);if(r&&r.offline)return toast('💤 這部所在的硬碟離線（檔案沒有刪），接回來才能播',5000);await api('/api/conv2',{a:'seen',ids:[id]});vbox('抽檢：'+(r?r.name:''),U('/api/video',{id}),r&&r.dur?r.dur*0.3:0)};
  $('#cvtag').onclick=async()=>{const d=await api('/api/conv2',{a:'tag_vs',dry:1});if(!d.n)return toast('轉好的檔名都已經有 _VS 了');if(!confirm(`把 ${d.n} 部轉好的 MP4 檔名後面加上 _VS？（abc.mp4 → abc_VS.mp4；只改名，操作紀錄可以改回）`))return;const r=await api('/api/conv2',{a:'tag_vs'});toast(r.message||'',6000);tConv()};
  $('#cvrand').onclick=()=>{const P=(D.rows||[]).filter(r=>r.del_exists&&r.out_exists);const A=(P.length?P:(D.rows||[])).slice();for(let i=A.length-1;i>0;i--){const k=Math.floor(Math.random()*(i+1));[A[i],A[k]]=[A[k],A[i]]}
    const pick=A.slice(0,5);if(!pick.length)return toast('沒有可以抽檢的');menu('🎲 抽到這 '+pick.length+' 部（點一部播放）',pick.map(r=>['▶ '+r.name,()=>playIt(r.id)]))};
  if($('#cvrv'))$('#cvrv').onclick=async()=>{const r=await api('/api/conv2',{a:'reverify',all:true});toast(r.message||'',6000)};
  if($('#cvredo'))$('#cvredo').onclick=async()=>{if(!confirm('畫質沒到目標的：用 DELETE 裡的原檔、🎯 自動方式重轉？達到目標才換掉舊的 MP4；原檔一直留在 DELETE，等你自己刪。'))return;const r=await api('/api/conv2',{a:'redo',all:true});toast(r.message||'',6000);cvDone()};
  if($('#cvlow'))$('#cvlow').onclick=async()=>{if(!confirm('畫質分數低於目標（預設 0.985）或沒驗證過的：刪掉轉好的 MP4、原檔從 DELETE 搬回原本的資料夾？之後可以重轉。'))return;const r=await api('/api/conv2',{a:'undo_low'});toast(r.message||'',6000);cvDone()};
  if($('#cvundo'))$('#cvundo').onclick=async()=>{if(!confirm(`${D.big} 部轉完反而變大：刪掉轉好的 MP4、原檔搬回原位？\n預覽圖、分級都照舊，之後可以用新設定（會封頂位元率）重轉。`))return;const r=await api('/api/conv2',{a:'undo',all:true});toast(r.message||'',5000);cvDone()};
  $('#cvpall').onclick=async()=>{const P=(D.rows||[]).filter(r=>r.del_exists&&!r.big);const warn=P.filter(r=>!r.cv_ssim||r.cv_ssim<0.95).length,seen=P.filter(r=>r.viewed&&r.viewed>=(r.cv_t||0)).length;
    if(!confirm(`永久刪除 ${D.pending} 個已轉檔完成的原檔（${fmtB(D.pending_bytes)}）？\n你抽檢過 ${seen} 部${warn?`；有 ${warn} 部驗證偏低或沒驗證`:'；全部自動驗證都通過 ✔'}\n刪了救不回來（轉好的 MP4 不會動）。`))return;
    if(D.pending>20&&!confirm('再確認一次：真的要刪？'))return;const r=await api('/api/conv2',{a:'purge',all:true});toast(r.message||'',5000);tConv()};
  b.querySelector('.panel.list').onclick=async e=>{if(CV.dms&&!e.target.closest('button')){const it=e.target.closest('.it[data-id]');if(it){const id=+it.dataset.id;CVSEL.has(id)?CVSEL.delete(id):CVSEL.add(id);cvDone()}return}
    const st=e.target.closest('[data-stage]');if(st){const r=await api('/api/conv2',{a:'stage',ids:[+st.dataset.stage]});toast(r.message||'');cvDone();return}
    const ud=e.target.closest('[data-undo]');if(ud){if(!confirm('保留原檔：刪掉轉好的 MP4、原檔留在原位（之後可以重轉）？'))return;const r=await api('/api/conv2',{a:'undo',ids:[+ud.dataset.undo]});toast(r.message||'');cvDone();return}
    const xf=e.target.closest('[data-force]');if(xf){if(!confirm('用 DELETE 裡的原檔、一定整部重壓到 0.985，排到隊伍最前面？'))return;const r=await api('/api/conv2',{a:'redo_force',ids:[+xf.dataset.force]});toast(r.message||'',5000);return}
    const x=e.target.closest('[data-rest]');if(x){if(!confirm('把原檔從 DELETE 搬回原本的位置？'))return;const r=await api('/api/conv2',{a:'restore',ids:[+x.dataset.rest]});toast(r.message||'');cvDone();return}
    const it=e.target.closest('.it[data-id]');if(it)playIt(+it.dataset.id)}}
async function cvFail(){const b=$('#cvb');if(!b)return;const j=await api(U('/api/conv2',{a:'fail'}));if(!j.ok||!$('#cvb'))return;const R=j.rows||[];
  b.innerHTML=`<div class="row" style="margin-bottom:8px"><button class="pill" id="cvra">↻ 失敗的全部重試</button><button class="pill" id="cvrs2" ${CVSEL.size?'':'disabled'}>↻ 重試勾選的（${[...CVSEL].filter(i=>R.some(r=>r.id===i)).length}）</button><span class="mu">失敗 ${R.filter(r=>r.cv_state==4).length} · 沒變小 ${R.filter(r=>r.cv_state==6).length}（已經很省，原檔不動）</span></div>
   <div class="mu" style="margin-bottom:6px">點一筆＝勾選／取消</div><div class="panel list" id="cvfl">${R.map(r=>`<div class="it${CVSEL.has(r.id)?' sel':''}" data-id="${r.id}"><div class="grow"><div style="word-break:break-all">${CVSEL.has(r.id)?'☑ ':'☐ '}${esc(r.name)}</div><div class="mu">${fmtB(r.size)} · ${r.cv_state==4?'<span style="color:var(--red)">✖ 失敗</span>':'沒變小'} · ${esc((r.cv_err||'').slice(0,140))}</div></div></div>`).join('')||'<div class="empty">沒有 👍</div>'}</div>`;
  $('#cvra').onclick=async()=>{const r=await api('/api/conv2',{a:'add',ids:R.filter(x=>x.cv_state==4).map(x=>x.id)});toast(r.message||'');CVSEL.clear();cvFail()};
  $('#cvrs2').onclick=async()=>{const ids=[...CVSEL].filter(i=>R.some(r=>r.id===i));if(!ids.length)return;const r=await api('/api/conv2',{a:'add',ids});toast(r.message||'');CVSEL.clear();cvFail()};
  $('#cvfl').onclick=e=>{const it=e.target.closest('.it[data-id]');if(!it)return;const id=+it.dataset.id;CVSEL.has(id)?CVSEL.delete(id):CVSEL.add(id);cvFail()}}
const LMN={full:'完整測試',lite:'少量確認',quick:'快速確認',trust:'直接套用＋抽查'};
async function tLearn(){const b=$('#tb');if(!b)return;const V=await api('/api/learn');if(!V.ok||!$('#tb'))return;const C=V.cfg||{};
  b.innerHTML=`<div class="panel"><div>共 <b>${(V.total||0).toLocaleString()}</b> 次經驗、<b>${(V.classes||[]).length}</b> 類　目標 SSIM ${V.target}　底線 ${C.floor}</div>
   <div class="mu" style="margin-top:4px">同一類轉越多，樣本取越少（5 段×2 秒 → 3 段×2 秒 → 3 段×1 秒）；${C.trust_n} 次以上、CQ 集中、抽查都過就直接套用（抽查 ${Math.round((C.spot||0)*100)}% 起）。抽查低於底線會更保守重轉。</div>
   <div class="row" style="margin-top:8px;gap:6px"><button class="pill ${C.on?'ok':'wa'}" data-lc="on">${C.on?'用經驗：開':'用經驗：關'}</button><button class="pill" data-lc="trust">直接套用門檻 ${C.trust_n} 次</button><button class="pill" data-lc="floor">底線 ${C.floor}</button><button class="pill er" data-lc="resetall">全部清掉</button></div></div>
   <div class="tgh">每一類</div><div class="panel list">${(V.classes||[]).map(c=>`<div class="it"><div class="grow"><div style="word-break:break-all"><b>${esc(c.cls)}</b></div>
    <div class="mu">${c.n} 次 · <span style="color:${c.mode==='trust'?'var(--green)':c.mode==='quick'?'var(--accent)':'var(--sub)'}">${LMN[c.mode]||c.mode}</span> · CQ ${c.q_med}（${c.q_min}～${c.q_max}）${c.ssim_avg?' · 樣本 '+c.ssim_avg.toFixed(4):''} · 抽查 ${c.spots}${c.spot_bad?'（<span style="color:var(--red)">沒過 '+c.spot_bad+'</span>）':''}${c.ratio_avg?' · 變成 '+Math.round(c.ratio_avg*100)+'%':''}</div>
    <div class="mu">${esc(c.reason||'')}</div></div><button class="pill" data-lr="${esc(c.cls)}">清掉</button></div>`).join('')||'<div class="empty">還沒有經驗（用 🎯 自動方式轉檔就會開始累積）</div>'}</div>
   <div class="tgh">最近的決定</div><div class="panel list">${(V.recent||[]).slice(0,60).map(x=>`<div class="it"><div class="grow"><div style="word-break:break-all">${esc(x.name||'')}</div>
    <div class="mu">${new Date((x.t||0)*1000).toLocaleString()} · ${LMN[x.mode]||x.mode} · CQ ${x.q}${x.ssim?' · 樣本 '+x.ssim.toFixed(3):''}${x.spot!=null?' · 抽查 <span style="color:'+(x.spot<C.floor?'var(--red)':'var(--green)')+'">'+x.spot.toFixed(3)+'</span>':''}${x.ratio?' · '+Math.round(x.ratio*100)+'%':''}${x.note?' · '+esc(x.note):''}</div></div></div>`).join('')||'<div class="empty">還沒有</div>'}</div>`;
  b.onclick=async e=>{const r=e.target.closest('[data-lr]');if(r){if(!confirm('清掉「'+r.dataset.lr+'」的經驗？'))return;await api('/api/learn',{a:'reset',k:r.dataset.lr});tLearn();return}
    const l=e.target.closest('[data-lc]');if(!l)return;const k=l.dataset.lc;let body=null;
    if(k==='on')body={a:'cfg',on:!C.on};else if(k==='trust'){const v=prompt('經驗幾次以上可以直接套用？',C.trust_n);if(!v)return;body={a:'cfg',trust_n:Math.max(5,+v||100)}}
    else if(k==='floor'){const v=prompt('底線 SSIM（低於這個一定重轉）',C.floor);if(!v)return;body={a:'cfg',floor:Math.min(0.995,Math.max(0.9,+v||0.975))}}
    else if(k==='resetall'){if(!confirm('全部經驗清掉？'))return;body={a:'reset'}}
    if(body){await api('/api/learn',body);tLearn()}}}
async function tHz(){const b=$('#tb');if(!b)return;let st;try{st=await api('/api/hz')}catch(e){return}if(!$('#tb'))return;if(!st.ok){b.innerHTML=`<div class="empty">${esc(st.message||'')}</div>`;return}
  const e=st.env||{},q=st.queue||{};const hzUrl=`https://${location.hostname}:8443/`,hzLan=`http://${location.hostname}:${st.port||8765}/`;
  b.innerHTML=`<div class="panel"><div class="row"><b class="grow">🔥 HotZone ${st.ver?'V'+esc(st.ver):''}　${st.running?'<span style="color:var(--green)">● 執行中</span>':'<span style="color:var(--sub)">● 沒有在跑</span>'}</b></div>
   <div class="mu" style="margin-top:4px">${st.running?(st.ours?'SortCut 在跑':'原本的 HotZoneFM.exe 在跑'):'—'}${st.running?' · '+(st.admin?'系統管理員 ✔':'<span style="color:var(--orange)">不是系統管理員</span>'):''} · 資料夾 ${esc(st.root)}</div>
   <div class="row" style="margin-top:8px">${st.running?`<a class="pill acc" href="${hzUrl}" target="_blank" rel="noopener">📱 打開 HotZone 手機版</a><a class="pill" href="${hzLan}" target="_blank" rel="noopener">區網</a>`:''}
    ${st.running?'':'<button class="pill acc" data-a="start">▶ 啟動</button>'}${st.running&&!st.ours?'<button class="pill wa" data-a="takeover">🔁 接手</button>':''}${st.running?'<button class="pill er" data-a="stop">⏹ 停止</button><button class="pill" data-a="open">🖥 電腦上打開</button>':''}</div>
   <div class="mu" style="margin-top:6px">HotZone 手機版用它自己的網址和密碼（Tailscale https://電腦名稱:8443/）；啟動時電腦會問一次系統管理員權限。</div></div>
  <div class="panel"><b>📂 HotZone 資料</b><div class="mu" style="margin:4px 0">${st.migrated?'✔ 已經整合在 SortCut 裡：'+esc(st.home):st.keep_orig?'✔ 直接用原本的資料夾：'+esc(st.root):st.root_found?'用偵測到的原本資料夾：'+esc(st.root):'<span style="color:var(--orange)">還沒找到原本的 HotZone 資料夾</span>（在電腦的 HotZone 總管按「📁 HotZone 資料夾…」選）'}${st.mig_partial&&!st.migrated?'<br><span style="color:var(--orange)">上次整合沒做完：在電腦上再按一次「📦 整合」只補沒複製到的</span>':''}</div>
   ${st.migrating?`<div class="mu" style="color:var(--acc)">📦 ${esc(st.mig_msg||'整合中…')}</div>`:''}${st.mig_last&&!st.migrating?`<div class="mu" style="color:${st.mig_last.ok?'var(--green)':'var(--orange)'}">${st.mig_last.ok?'✔':'⚠'} 上次整合：${esc(st.mig_last.message||'')}</div>`:''}
   <div class="row"><button class="pill" data-a="diag">🩺 連線診斷</button>${!st.migrated&&st.root_found&&!st.migrating?'<button class="pill acc" data-a="migrate">📦 整合進 SortCut</button>':''}${!st.migrated&&!st.keep_orig&&st.root_found?'<button class="pill" data-a="keep">📌 就用原本的資料夾</button>':''}</div>
   ${(st.cands||[]).length?'<div style="margin-top:6px"><b style="font-size:13px">電腦上找到的其他 HotZone 資料夾</b>'+st.cands.map(c=>`<div class="row" style="margin-top:4px"><span class="grow mu" style="font-size:12px">${esc(c.path)}<br>佇列 ${c.queue} 筆 · 最後改動 ${c.t?new Date(c.t*1000).toLocaleString('zh-TW',{hour12:false}):'—'}${c.exe?' · 有 HotZoneFM.exe':''}</span><button class="pill" data-a="use" data-p="${esc(c.path)}">用這個</button></div>`).join('')+'</div>':''}
   ${tHz._diag?'<div style="margin-top:6px">'+tHz._diag.map(x=>`<div class="mu" style="font-size:12px">${x.ok===true?'✔':x.ok===false?'<span style="color:var(--red)">✖</span>':'•'} ${esc(x.text)}</div>`).join('')+'</div>':''}</div>
  ${st.running?`<div class="panel"><b>現在在做什麼</b><div class="mu" style="margin-top:4px">搬檔佇列：在跑 ${q.running||0} · 排隊 ${q.queued||0}${q.speed?' · '+fmtB(q.speed)+'/s':''}${q.paused_all?' · 全部暫停中':''}${st.hot_paused?' · 熱區暫停中':''}</div>
   ${(st.hot||[]).map(h=>`<div class="edjI ${['moving','evicting','planning'].includes(h.state)?'run':''}"><div class="edjT"><b>${esc(h.letter)} 熱區</b><em>${esc(h.state||'')}</em><span class="mu">${h.pct_in!=null?Math.round(h.pct_in)+'% 在外圈':''}${h.rate?' · '+fmtB(h.rate)+'/s':''}${h.eta?' · 還要 '+eta(h.eta):''}</span></div>${h.msg?`<small>${esc(h.msg)}</small>`:''}</div>`).join('')}
   ${(st.notices||[]).slice(-4).map(n=>`<div class="mu">⚠ ${esc(n.text||'')}</div>`).join('')}</div>`:''}
  <div class="panel"><b>⚖ 硬碟協調員</b><div class="mu" style="margin:4px 0">同一顆 HDD 兩邊都在大量讀寫、忙碌一直很高時只讓一邊做：你排的工作優先；背景工作每 ${st.cfg.slice_min} 分鐘輪流。</div>
   <div class="row"><label class="tg"><input type="checkbox" id="hzarb" ${st.cfg.arb!==false?'checked':''}><i></i></label><span class="grow">開啟</span><select id="hzsl">${[5,10,15,20,30,60].map(x=>`<option value="${x}"${x==st.cfg.slice_min?' selected':''}>每 ${x} 分鐘換</option>`).join('')}</select></div>
   ${(st.arb||[]).map(a=>`<div class="edjI run"><div class="edjT"><b>${esc(a.disk)}</b><em>讓給 ${a.owner==='vs'?'SortCut':'HotZone'}</em></div><small>${esc(a.why)}</small></div>`).join('')||'<div class="mu">現在沒有搶硬碟 ✔</div>'}
   ${(st.arb_log||[]).slice(-6).reverse().map(x=>`<div class="mu" style="font-size:11.5px">${new Date(x.t*1000).toLocaleTimeString('zh-TW',{hour12:false})} ${esc(x.disk)} → ${esc(x.why)}</div>`).join('')}</div>
  <div class="panel"><b>Python 環境</b><div class="mu" style="margin:4px 0">${e.py?`${e.ok?'✔':'✖'} Python ${esc(e.py)} · Pillow ${esc(e.pil||'沒有')} · numpy ${esc(e.numpy||'沒有')} · OpenCV ${esc(e.cv2||'沒有')} · PySide6 ${esc(e.pyside6||'沒有')}`:'還沒檢查'}${st.installing?' · 📦 安裝中…':''}</div>
   <div class="row"><button class="pill" data-a="check">🔍 檢查環境</button><button class="pill" data-a="install">📦 安裝需要的套件</button><label class="row"><label class="tg"><input type="checkbox" id="hzauto" ${st.cfg.auto?'checked':''}><i></i></label><span class="mu">開 SortCut 時自動啟動</span></label></div></div>`;
  b.onclick=async ev=>{const x=ev.target.closest('[data-a]');if(!x)return;const a=x.dataset.a;if(a==='stop'&&!confirm('停止 HotZone 背景引擎？'))return;if(a==='takeover'&&!confirm('讓原本的 HotZoneFM.exe 結束，改由 SortCut 接著跑？（電腦上會問一次系統管理員權限）'))return;
    if(a==='keep'&&!confirm('不整合，直接用原本的 HotZone 資料夾？'))return;if(a==='use'&&!confirm('改用這個 HotZone 資料夾？\n'+x.dataset.p+'\n（在跑的 HotZone 用的是別的資料夾的話，會自動重新啟動）'))return;if(a==='migrate'&&!confirm('把 HotZone 的資料複製進 SortCut、之後都用那裡的？\n（電腦上的 HotZone 會先停一下、好了再啟動，會問一次系統管理員權限；原本的資料夾留著當備份）'))return;
    x.disabled=true;if(a==='diag')x.textContent='🩺 檢查中…';const r=await api('/api/hz',a==='use'?{a,path:x.dataset.p}:{a});
    if(r.job){toast('⏳ 電腦正在處理…（'+a+'）',4000);const t0=Date.now();const poll=async()=>{const st=await api('/api/hz');const j=st.job||{};if(j.running&&Date.now()-t0<300000){setTimeout(poll,1500);return}
      const res=j.result||{};if(a==='diag'){tHz._diag=res.items||[]}else toast(res.message||'好了',6000);tHz()};setTimeout(poll,1200);return}
    if(a==='diag'){tHz._diag=r.items||[];tHz();return}toast(r.message||'',5000);setTimeout(tHz,a==='check'?100:1500)};
  $('#hzarb').onchange=ev=>api('/api/hz',{a:'cfg',arb:ev.target.checked}).then(r=>toast(r.message||''));$('#hzsl').onchange=ev=>api('/api/hz',{a:'cfg',slice_min:+ev.target.value}).then(r=>toast(r.message||''));
  $('#hzauto').onchange=ev=>api('/api/hz',{a:'cfg',auto:ev.target.checked}).then(r=>toast(r.message||''));
  clearTimeout(tHz._t);tHz._t=setTimeout(()=>{if($('#tb')&&location.hash==='#tool/hz'&&!document.hidden)tHz()},st.migrating?1500:5000)}
async function tOps(q=''){$('#tb').innerHTML=`<button class="pill acc" id="oundo" style="width:100%;margin-bottom:8px">↩ 復原上一次搬移（移到待刪／歸檔／收藏）</button><input class="search" id="oq" placeholder="🔍 搜尋檔名、路徑" value="${esc(q)}"><div id="ol" class="panel list" style="margin-top:8px"><div class="empty">讀取中…</div></div>`;
  $('#oundo').onclick=async()=>{const d=await api('/api/ops_undo_last',{dry:1});if(!d.n)return toast(d.message||'沒有可以復原的搬移');if(!confirm(`把上一次「${d.kind}」（${d.when}，${d.n} 個、${fmtB(d.bytes)}）整批搬回原來的位置？`))return;const r=await api('/api/ops_undo_last',{});toast(r.message||'',6000);tOps($('#oq')?$('#oq').value:'')};
  let t;$('#oq').oninput=e=>{clearTimeout(t);t=setTimeout(()=>tOps(e.target.value).then(()=>{const i=$('#oq');if(i){i.focus();i.setSelectionRange(i.value.length,i.value.length)}}),500)};
  const K={arch:'📦 歸檔',trash:'🗑 待刪',fav:'⭐ 收藏',delete:'❌ 刪除原檔',cut:'✂ 初剪',conv:'🔁 轉檔',undo:'↩ 復原',migrate:'📁 搬家',exclude:'🚫 排除',cat:'🏷 分類',rename:'🔤 改名',snap:'📷 截圖',clean:'🧹 清理'};
  const j=await api(U('/api/ops',{q}));if(!$('#ol'))return;
  $('#ol').innerHTML=(j.rows||[]).map(r=>`<div class="it"><div class="grow"><div>${K[r.kind]||esc(r.kind)} ${esc(r.name)}</div><div class="mu">${new Date(r.t*1000).toLocaleString('zh-TW',{hour12:false})}${r.size?' · '+fmtB(r.size):''}${r.undone?' · 已搬回':''}</div>
   ${r.src?`<div class="mu" style="font-size:11px;word-break:break-all">從 ${esc(r.src)}</div>`:''}${r.dst?`<div class="mu" style="font-size:11px;word-break:break-all">到 ${esc(r.dst)}</div>`:''}${r.detail?`<div class="mu" style="font-size:11px">${esc(r.detail)}</div>`:''}</div>
   ${['arch','trash','fav','rename','cat'].includes(r.kind)&&!r.undone&&r.ok?`<button class="pill" onclick="undoOp(${r.id})">↩ 搬回</button>`:''}</div>`).join('')||'<div class="empty">沒有紀錄</div>'}
async function undoOp(id){if(!confirm('搬回原來的位置？'))return;const j=await api('/api/ops_undo',{id});toast(j.message||(j.ok?'已搬回':'不行'));tOps($('#oq')?$('#oq').value:'')}
let LT;
async function tLog(){$('#tb').innerHTML=`<div class="tools"><input class="search" id="lq" placeholder="🔍 篩選（空格隔開＝都要有）"><button class="pill" id="lw" style="height:40px">只看警告</button><button class="pill" id="lpz" style="height:40px">⏸</button></div><pre class="log" id="lp" style="margin-top:8px">讀取中…</pre>`;
  let warn=false,pz=false;$('#lw').onclick=e=>{warn=!warn;e.target.classList.toggle('on',warn);load(true)};$('#lpz').onclick=e=>{pz=!pz;e.target.classList.toggle('on',pz);e.target.textContent=pz?'▶':'⏸'};
  const load=async(force)=>{if(!$('#lp'))return clearInterval(LT);if(pz&&!force)return;const j=await api(U('/api/log',{q:$('#lq').value,warn:warn?1:0}),undefined,{quiet:true});const p=$('#lp');if(!p)return;const atEnd=p.scrollTop+p.clientHeight>=p.scrollHeight-20;p.textContent=(j.lines||[]).join('\n')||'（沒有符合的）';if(atEnd)p.scrollTop=p.scrollHeight};
  $('#lq').oninput=()=>load(true);clearInterval(LT);LT=setInterval(load,3000);load(true)}
async function tUpd(){$('#tb').innerHTML=`<div class="panel"><b>目前 V${esc(VER)}</b><p class="mu">選 SC_V….zip（手機下載的也可以）→ 上傳 → 電腦熱更新，程式不用關、背景工作不中斷；手機會自動換新版。</p>
   <input type="file" id="uf" accept=".zip"><div class="row" style="margin-top:8px"><button class="pill acc" id="ub">⬆ 上傳並更新</button><span class="mu" id="um"></span></div></div><div id="cu2" class="panel"><b>☁ 雲端更新（GitHub）</b><div class="mu" id="cum">讀取中…</div><div class="row" style="margin-top:8px;gap:6px"><button class="pill" id="cuc">🔄 檢查</button><button class="pill acc" id="cug" style="display:none">⬇ 更新</button></div></div><div id="cl2" class="panel"><b>最近更新</b><div class="mu">讀取中…</div></div>`;
  const cuShow=r=>{const m=$('#cum');if(!m)return;if(!r){m.textContent='還沒檢查過（電腦開機 1 分鐘後會自己看一次）';return}const I=r.info||{};m.innerHTML=esc(r.message||'')+(r.newer&&(I.notes||[]).length?'<ul style="margin:4px 0;padding-left:18px">'+I.notes.slice(0,6).map(x=>`<li>${esc(x)}</li>`).join('')+'</ul>':'')+(r.newer&&I.need_shell?'<div style="color:#f0ad4e">這版要換 EXE：電腦會先問、關掉再自己打開</div>':'');$('#cug').style.display=r.newer?'':'none'};
  api('/api/cloud_upd').then(j=>cuShow(j.r)).catch(()=>{});
  $('#cuc').onclick=async()=>{$('#cum').textContent='檢查中…';const j=await api('/api/cloud_upd',{a:'check'});cuShow(j)};
  $('#cug').onclick=async()=>{const j=await api('/api/cloud_upd',{a:'go'});toast(j.message||'',6000)};
  $('#ub').onclick=async()=>{const f=$('#uf').files[0];if(!f)return toast('先選更新包');$('#um').textContent='上傳中…';const j=await api(U('/api/update',{name:f.name}),f);$('#um').textContent=j.message||'';if(j.ok)toast(j.message,6000)};
  const j=await api('/api/changelog');if(!$('#cl2'))return;$('#cl2').innerHTML='<b>最近更新</b>'+(j.log||[]).map(e=>`<div style="margin:8px 0"><b>V${esc(e.version)}</b> <span class="mu">${esc(e.date||'')}</span><ul style="margin:4px 0;padding-left:18px">${(e.items||[]).map(i=>`<li class="mu">${esc(i)}</li>`).join('')}</ul></div>`).join('')}
async function logout(){if(!confirm('登出這支手機？下次要重新輸入 PIN'))return;await api('/api/logout',{});LS.set('tok','');TOK='';location.reload()}

// ---------------------------------------------------------------- 設定（照 TikLive：左邊分類＋搜尋、右邊一條一條）
const SCAT=[['look','🎨','外觀','主題、字體、一列幾張','phone'],['about','📱','手機網頁','版本、連線、登出','phone'],['lib','💽','影片庫','硬碟、排除、分類、備份、USB','pc'],['th','🖼','預覽圖','背景做、幾部同時、間隔','pc'],['cut','✂','初剪','分段／合併、免轉檔','pc'],['conv','🔁','轉檔','編碼器、畫質、轉好之後','pc'],
  ['ext','🗂','檔案類型','檔案總管列出哪些格式','pc'],['misc','⚙','其他','這台電腦的名稱、歸檔、備份、每日目標','pc'],['lab','🧪','實驗功能','開了才有的試用功能','pc']];
const SKEYS={th:['th_on','th_n','th_step','th_prio','probe_n','hdd_n','scan_on_start','grid_sec'],cut:['cut_merge','cut_mode'],conv:['cv_mode','cv_target','cv_enc','cv_q','cv_res','cv_cap','cv_n','cv_per_disk','cv_after','cv_verify'],misc:['pc_name','pc_color','arch_f_trash','db_backup','daily_goal_n']};
let SETD=null;
async function viewSet(){const gen=S.gen;
  V().innerHTML=`<div class="s2"><aside class="scat" id="scat"></aside><div class="sbody" id="sbody"><div class="empty">讀取中…</div></div></div>`;
  const sc=$('#scat');const cur=S.scat||'look';const btn=c=>`<button data-c="${c[0]}"${cur===c[0]?' class="on"':''}>${c[1]} ${c[2]}<small>${c[3]}</small></button>`;
  sc.innerHTML=`<input class="ssearch" id="ssq" placeholder="🔍 搜尋設定"><div class="sch">這支手機</div>`+SCAT.filter(c=>c[4]==='phone').map(btn).join('')+`<div class="sch">電腦程式</div>`+SCAT.filter(c=>c[4]==='pc').map(btn).join('')+`<div class="sch">其他程式</div><a class="scl" href="/fc/?go=set" style="display:block;text-decoration:none;color:inherit;padding:8px 10px;border-radius:10px;border:1px dashed var(--line);margin:4px 0">🗂 整理（FileCompare）的設定 ›<small style="display:block;opacity:.7">背景工作、掃描、修復、分類</small></a>`;   // V0.5.24
  sc.onclick=e=>{const b=e.target.closest('button[data-c]');if(b){$('#ssq').value='';setCat(b.dataset.c)}};
  let qt;$('#ssq').oninput=e=>{clearTimeout(qt);qt=setTimeout(()=>setSearch(e.target.value.trim()),250)};
  try{SETD=await api('/api/settings')}catch(e){return}if(gen!==S.gen)return;setCat(cur)}
function setCat(k){S.scat=k;$$('#scat button').forEach(b=>b.classList.toggle('on',b.dataset.c===k));const sb=$('#sbody');if(!sb||!SETD)return;const c=SCAT.find(x=>x[0]===k)||SCAT[0];
  const fn={look:secLook,ext:secExt,faces:secFaces,lab:secLab,about:secAbout,lib:()=>'<div id="lset"><div class="empty">讀取中…</div></div>'}[c[0]];sb.innerHTML=`<h2 class="stt">${c[1]} ${c[2]}</h2>`+(fn?fn():secPc(SKEYS[c[0]]||[]));bindSet(sb);if(c[0]==='faces')faceSet();if(c[0]==='lib')libSet()}
function setSearch(q){const sb=$('#sbody');if(!sb||!SETD)return;if(!q){setCat(S.scat||'look');return}const ql=q.toLowerCase();const R=SETD.settings.concat(SETD.lab).filter(s=>s.name.toLowerCase().includes(ql));
  $$('#scat button').forEach(b=>b.classList.remove('on'));
  sb.innerHTML=`<h2 class="stt">🔍 「${esc(q)}」找到 ${R.length} 個設定</h2><div class="ssec">${R.map(si).join('')||'<div class="empty">找不到，換個字試試（例如：畫質、預覽圖、合併）</div>'}</div>`;bindSet(sb)}
function si(s){if(s.type==='text')return `<div class="si"><b>${esc(s.name)}</b><input type="text" data-k="${s.k}" value="${esc(s.v)}" maxlength="${+s.opt||50}" style="width:100%;margin-top:4px"><small>改了之後手機 App 的名稱和圖示要刪掉重新安裝才會變</small></div>`;
  if(s.k.startsWith('lab:')||s.type==='bool')return `<div class="si tgr"><b>${esc(s.name)}${s.ver?` <span class="mu">V${esc(s.ver)}</span>`:''}</b><label class="tg"><input type="checkbox" data-k="${s.k}" ${s.v?'checked':''}><i></i></label></div>`;
  if(s.type==='choice')return `<div class="si"><b>${esc(s.name)}</b><div class="seg" data-k="${s.k}" data-num="${typeof s.opt[0][0]==='number'?1:0}">${s.opt.map(o=>`<button data-v="${esc(o[0])}"${String(o[0])===String(s.v)?' class="on"':''}>${esc(o[1])}</button>`).join('')}</div></div>`;
  return `<div class="si"><b>${esc(s.name)}</b><div class="pnum"><button data-step="-1">－</button><input type="number" data-k="${s.k}" value="${esc(s.v)}" min="${s.opt[0]}" max="${s.opt[1]}"><button data-step="1">＋</button><span>${s.opt[0]}～${s.opt[1]}</span></div></div>`}
function secPc(keys){return `<div class="ssec">${keys.map(k=>SETD.settings.find(s=>s.k===k)).filter(Boolean).map(si).join('')||'<div class="empty">—</div>'}</div><div class="mu">改了馬上存到電腦（電腦的設定頁也會跟著變）。</div>`}
function secLab(){const vt=v=>String(v||'').split('.').map(x=>+x||0).reduce((a,x)=>a*1000+x,0);const seen=vt(LS.get('labSeen','0.2.29'));   // V0.2.46 🆕 新功能分開列、最新在上、有說明
  const N=SETD.lab.filter(s=>s.new).sort((a,b)=>vt(b.ver)-vt(a.ver)),O=SETD.lab.filter(s=>!s.new);setTimeout(()=>{try{LS.set('labSeen',(N[0]||{}).ver||'0.2.29')}catch(e){}},500);
  const XE=SETD.lab_extra||[];const xe=lk=>XE.filter(x=>x.lab===lk).map(x=>`<div class="si" style="margin-left:14px"><small>${esc(x.name)}</small>${x.type==='choice'?`<select data-lx="${x.k}">${x.opt.map(o=>`<option value="${o[0]}"${String(o[0])===String(x.v)?' selected':''}>${esc(o[1])}</option>`).join('')}</select>`:`<input data-lx="${x.k}" type="${x.type==='num'?'number':'text'}" value="${esc(x.v)}" style="width:${x.type==='num'?'90px':'100%'}">`}</div>`).join('');   // V0.2.67
  const nh1=s=>si(Object.assign({},s,{name:s.name+(vt(s.ver)>seen?' 🔴':'')}))+(s.desc?`<div class="mu" style="margin:-4px 0 8px 4px;font-size:12px">${esc(s.desc)}</div>`:'')+xe(s.k.slice(4));
  const PK=(SETD.lab_packs||[]).map(([n,K])=>`<button class="pill" data-pack="${esc(n)}">${esc(n)}</button>`).join('');   // V0.2.93 一次打開一組
  return (PK?`<div class="row" style="flex-wrap:wrap;gap:6px;margin:4px 0 8px"><small class="mu">一次打開一組：</small>${PK}</div>`:'')+`<div class="row" style="flex-wrap:wrap;gap:6px;margin:0 0 8px"><button class="pill" data-share="x">🔄 設定存到硬碟</button><button class="pill" data-share="i">📥 套用另一台的</button></div>`+(N.length?`<div class="mu" style="margin:4px 0">🆕 新功能（${N.length} 個・最新在上・🔴＝上次看之後新加的）</div>`+(()=>{const G=[...(SETD.lab_packs||[]),['🧩 其他',N.map(x=>x.k.slice(4))]],used=new Set();   // V0.3.41 分組
    return G.map(([gn,K])=>{const it=N.filter(x=>K.includes(x.k.slice(4))&&!used.has(x.k));it.forEach(x=>used.add(x.k));if(!it.length)return '';return `<div class="mu" style="margin:10px 0 4px;font-weight:700">${esc(gn)}（${it.filter(x=>x.v).length}／${it.length} 開著）</div><div class="ssec">${it.map(nh1).join('')}</div>`}).join('')})():'')+`<div class="mu" style="margin:8px 0 4px">之前的實驗功能</div><div class="ssec">${O.map(si).join('')||'<div class="empty">—</div>'}</div><div class="mu">實驗功能：試用中，好用再正式加入。</div>`}
function secLook(){const sg=(k,v,L)=>`<div class="seg" data-ui="${k}">${L.map(([a,b])=>`<button data-v="${a}"${String(v)===String(a)?' class="on"':''}>${b}</button>`).join('')}</div>`;
  return `<div class="ssec"><div class="si"><b>主題</b>${sg('mode',UI.mode,[['dark','🌙 深色'],['light','☀ 淺色'],['auto','🌗 跟著時間']])}</div><div class="si"><b>字體大小</b>${sg('fs',UI.fs,[['s','小'],['m','中'],['l','大']])}</div>
   <div class="si"><b>檔案總管一列幾張</b>${sg('cols',S.cols,COLS.map(c=>[c,c==='auto'?'自動':c]))}<small>也可以在清單上兩指捏合調整</small></div>
   <div class="si"><b>預覽格子一列幾張</b><div class="pnum"><button data-uistep="-1">－</button><input type="number" data-ui="tcols" value="${LS.get('tcols',4)}" min="2" max="30"><button data-uistep="1">＋</button><span>2～30</span></div></div>
   <div class="si"><b>預覽格子每幾秒一張</b>${sg('gs',LS.get('gs',2),GSTEPS.map(c=>[c,c>=60?c/60+'分':c+'秒']))}</div>
   <div class="si"><b>播放時左右滑動一次最多</b>${sg('swipeMax',swMax(),[[0,'關閉'],[30,'30 秒'],[60,'1 分'],[120,'2 分'],[180,'3 分'],[300,'5 分'],[600,'10 分']])}<small>滑得快、滑得長＝跳得遠；慢慢滑＝幾秒幾秒微調。拖著不放畫面就跟著走。</small></div>
   <div class="si"><b>浮動視窗高度</b><div class="row"><button class="pill" data-uih>恢復 50%</button></div><small>浮動視窗（📊 效能…）下面的橫條可以上下拖。</small></div></div><div class="mu">只存在這支手機（電腦和別支手機不受影響）。</div>`}
function secExt(){const E=SETD.exts||{all:[],hide:[],count:{}},H=new Set(E.hide);return `<div class="ssec"><div class="si"><b>檔案總管要列出的格式</b><div class="extg" id="extg">${E.all.map(x=>`<button class="pill ${H.has(x)?'':'on'}" data-x="${x}">${H.has(x)?'':'✔ '}${x.slice(1)}${E.count[x]?' '+E.count[x]:''}</button>`).join('')}</div>
   <small>亮起來（✔）＝列出來。手機／遠端只能播 MP4，其他格式預設不列；沒列出來的照樣做預覽圖、在「轉檔清單」看得到，轉成 MP4 之後就會列出來。電腦的設定頁是同一個設定。</small>
   <div class="row" style="margin-top:8px"><button class="pill" data-xall="mp4">只列 MP4（預設）</button><button class="pill" data-xall="all">全部列出</button></div></div></div>`}
function secAbout(){return `<div class="ssec"><div class="si"><b>版本</b>V${esc(VER)}</div><div class="si"><b>連線</b>電腦 127.0.0.1:${SETD.web.port} → Tailscale https://電腦名稱:${SETD.web.https}/<small>SortCut 用自己的埠，不會跟 TikLive、FusionStitch 打架。</small></div>
   <div class="si"><b>影片庫</b>${SETD.roots.map(r=>`<div>${esc(r)}</div>`).join('')||'<span class="mu">還沒加</span>'}<small><a href="#set/lib" onclick="S.scat='lib'">到 💽 影片庫 加入／移除</a></small></div><div class="si"><b>介面</b><div class="row"><button class="pill" onclick="setView(isPC()?'phone':'pc')">${isPC()?'📱 切回手機版':'🖥 切到網頁版'}</button></div><small>網頁版＝電腦／平板的大螢幕版面（左邊選單、資料夾樹、清單和預覽並排）。這台瀏覽器會記住；網址加 ?m=1 一定是手機版、?pc=1 一定是網頁版。</small></div><div class="si"><button class="pill er" onclick="logout()">登出這支手機</button></div><div class="si" style="opacity:.6"><small>🗄 封存的功能（平常用不到，收起來避免誤按）：<a href="#tool/rsplit">R 碟清空搬移</a>・電腦按 Ctrl+Shift+R</small></div></div>`}
async function isoSet(){const el=$('#liso');if(!el)return;let j;try{j=await api(U('/api/lib',{a:'iso'}))}catch(e){return}if(!j.ok||!$('#liso'))return;
  const D=j.drives||[],G=j.folders||[];if(!D.length&&!G.length){el.style.display='none';return}el.style.display='';
  const it=(x,i)=>`<div class="row" style="gap:6px;margin:4px 0"><span class="grow" style="word-break:break-all">${x.kind==='drive'?'💤 '+esc(x.label||'外接硬碟')+(x.sub?' \\'+esc(x.sub):''):'📁 '+esc(x.folder)} <span class="mu">${(+x.n).toLocaleString()} 部（預覽好 ${(+x.th).toLocaleString()}）${x.kind==='drive'?' · 序號 '+esc(x.serial||'?'):' · 找不到'}</span></span><button class="pill" data-iso="${i}">📍 指定位置</button></div>`;
  const A=[...D,...G];
  el.innerHTML=`<b>🗄 讀不到的（先隔離，紀錄和預覽圖都留著）</b>${A.map(it).join('')}<div class="row" style="gap:6px;margin-top:6px"><button class="pill" data-isof>🔎 現在重新找一次</button></div><small>拔掉的硬碟接回來（不管哪個代號）會自動套回去；搬走的資料夾按「📍 指定位置」選它現在在哪裡。</small>`;
  el.onclick=async e=>{e.stopPropagation();const fin=r=>{toast(r.message||(r.ok?'✔':'失敗'),6000);S.folders=null;setTimeout(libSet,600)};
    if(e.target.closest('[data-isof]'))return fin(await api('/api/lib',{a:'iso_find'}));
    const b=e.target.closest('[data-iso]');if(!b)return;const x=A[+b.dataset.iso];
    addRoot('',{title:'📍 它現在在哪裡？',ok:async p=>{const q={a:'iso_set',kind:x.kind,key:x.key||'',folder:x.folder||'',path:p};let r=await api('/api/lib',q);
      if(r.need_force){if(!confirm((r.message||'')+'\n\n還是要改過去嗎？'))return;r=await api('/api/lib',{...q,force:1})}fin(r)}})}}
async function libSet(){let j;try{j=await api(U('/api/lib',{a:'info'}))}catch(e){return}const el=$('#lset');if(!el)return;if(!j.ok){el.innerHTML=`<div class="empty">${esc(j.message||'讀不到')}</div>`;return}
  const G=j.guard||{},U_=j.usb,sg=(k,v,L)=>`<div class="seg" data-lg="${k}">${L.map(([a,b])=>`<button data-v="${a}"${String(v)===String(a)?' class="on"':''}>${b}</button>`).join('')}</div>`;
  const usbOff=U_?Object.keys(U_.map||{}).filter(k=>String((U_.map[k]||{}).bus||'').toUpperCase()==='USB'):[];
  el.innerHTML=`<div class="ssec"><div class="si" id="liso" style="display:none"></div><div class="si"><b>要整理的硬碟／資料夾</b>${(j.roots||[]).map(r=>`<div class="row" style="gap:6px;margin:4px 0"><span class="grow" style="word-break:break-all">💽 ${esc(r.path)} <span class="mu">${(+r.n).toLocaleString()} 部${r.offline?' · 💤 離線':''}</span></span><button class="pill" data-lr="rescan" data-p="${esc(r.path)}">🔄</button><button class="pill er" data-lr="del" data-p="${esc(r.path)}">➖</button></div>`).join('')||'<div class="mu">還沒加</div>'}
    <div class="row" style="gap:6px;margin-top:6px"><button class="pill ok" data-lr="add">＋ 加硬碟／資料夾</button><button class="pill" data-lr="scanall">🔄 全部重新掃描</button></div><small>${j.scan&&j.scan.running?'🔄 掃描中：'+esc(j.scan.cur||'')+'（'+(+j.scan.n||0).toLocaleString()+'）':'移除只是不再列出，檔案和預覽圖都不會刪。'}</small></div>
   <div class="si"><b>排除（不掃描、不列出）</b>${(j.ex_dirs||[]).map(x=>`<div class="row" style="gap:6px;margin:3px 0"><span class="grow" style="word-break:break-all">📁 ${esc(x)}</span><button class="pill" data-lx="dir" data-x="${esc(x)}">取消排除</button></div>`).join('')}${(j.ex_names||[]).map(x=>`<div class="row" style="gap:6px;margin:3px 0"><span class="grow">🏷 名稱：${esc(x)}</span><button class="pill" data-lx="name" data-x="${esc(x)}">取消排除</button></div>`).join('')}${!(j.ex_dirs||[]).length&&!(j.ex_names||[]).length?'<div class="mu">沒有排除任何資料夾</div>':''}
    <div class="row" style="gap:6px;margin-top:6px"><button class="pill" data-lr="exname">＋ 排除某個名稱的資料夾</button></div><small>要排除某個資料夾：檔案總管 📁 選資料夾 → 那一列的 ⚙。取消排除會重新掃描，那些影片就會回來（預覽圖不用重做）。</small></div>
   <div class="si"><b>自訂分類資料夾（歸檔目的地）</b>${(j.cats||[]).map(c=>`<div class="row" style="gap:6px;margin:3px 0"><span class="grow">🗂 ${esc(c)}</span><button class="pill" data-lc2="${esc(c)}">移除</button></div>`).join('')||'<div class="mu">還沒有</div>'}<div class="row" style="gap:6px;margin-top:6px"><button class="pill" data-lr="catadd">＋ 新增分類</button></div><small>移除分類只是不再出現在選單，資料夾和裡面的檔案不動。</small></div>
   <div class="si"><b>資料庫備份</b><div class="row" style="gap:6px;margin-bottom:6px"><button class="pill" data-lr="bk">💾 現在備份一份</button></div>${(j.backups||[]).slice(0,12).map(b=>`<div class="row" style="gap:6px;margin:3px 0"><span class="grow mu">${new Date(b.t*1000).toLocaleString()} · ${fmtB(b.size)}</span><button class="pill wa" data-lb="${esc(b.name)}">↺ 用這份還原</button></div>`).join('')||'<div class="mu">還沒有備份</div>'}<small>還原會在下次打開程式時進行，現在的資料庫會改名留著（不會刪）。</small></div>
   <div class="si"><b>🔌 USB 硬碟斷線自動救回</b>${U_?`<div class="row tgr" style="gap:6px"><span class="grow">斷線 45 秒沒回來：自動重啟那個 USB</span><label class="tg"><input type="checkbox" data-lu="on" ${U_.on?'checked':''}><i></i></label></div>
     <div class="row" style="gap:6px;margin-top:6px"><button class="pill" data-lr="usbmap">🔍 重新讀線路</button><button class="pill wa" data-lr="usbnow">🔌 離線的硬碟現在救</button></div>
     <small>${U_.win?(U_.installed?'✔ 已設定':'⚠ 還沒設定（要在電腦的 ⏯ 後台 按「🔌 設定」問一次系統管理員）'):'只有 Windows 才有'} · 記得線路：${Object.keys(U_.map||{}).sort().join('、')||'還沒讀'}（USB：${usbOff.join('、')||'無'}）${Object.keys(U_.pending||{}).length?' · 等待中：'+Object.keys(U_.pending).join('、'):''}</small>${(U_.last||[]).slice(-4).map(x=>`<small>${esc(String(x))}</small>`).join('')}`:'<div class="mu">模組沒有載入</div>'}</div>
   <div class="si tgr"><b>🛟 主程式優先（畫面、手機永遠先；一卡背景馬上退到最低）</b><label class="tg"><input type="checkbox" data-lu="mf" ${G.mf!==false?'checked':''}><i></i></label></div>
   <div class="si"><b>畫面慢了多少就算卡</b>${sg('mf_lag',G.mf_lag||400,[[250,'0.25 秒'],[400,'0.4 秒'],[700,'0.7 秒'],[1000,'1 秒']])}<small>卡了：背景工作全部不開新的、同時只做 1 個、FFmpeg 壓到 5%；順了 20 秒才慢慢放回來。</small></div>
   <div class="si tgr"><b>⚖ 電腦忙的時候背景工作自動讓路</b><label class="tg"><input type="checkbox" data-lu="guard" ${G.on?'checked':''}><i></i></label></div>
   <div class="si"><b>CPU 超過幾 % 就讓路</b>${sg('cpu_max',G.cpu_max,[[70,'70%'],[80,'80%'],[85,'85%'],[90,'90%'],[95,'95%'],[100,'100%']])}</div>
   <div class="si"><b>開始時慢慢加速（秒）</b>${sg('ramp_sec',G.ramp_sec,[[0,'不用'],[10,'10'],[20,'20'],[30,'30'],[60,'60'],[120,'120']])}<small>背景工作一個一個慢慢加上去，不會一開就全部衝。</small></div></div>`;
  isoSet();el.onclick=async e=>{const t=e.target;if(t.closest('#liso'))return;const lr=t.closest('[data-lr]');const done=r=>{toast(r.message||(r.ok?'✔':'失敗'),6000);S.folders=null;setTimeout(libSet,600)};
    if(lr){const k=lr.dataset.lr,p=lr.dataset.p;
      if(k==='add')return addRoot();if(k==='scanall')return done(await api('/api/lib',{a:'rescan'}));if(k==='rescan')return done(await api('/api/lib',{a:'rescan',path:p}));
      if(k==='del'){if(!confirm(`從影片庫移除 ${p}？\n只是不再列出，檔案和已做好的預覽圖都不會刪。`))return;return done(await api('/api/lib',{a:'root_del',path:p}))}
      if(k==='exname'){const n=prompt('不管在哪一層，資料夾名稱是這個就排除：');if(n&&n.trim())return done(await api('/api/lib',{a:'exclude',kind:'name',x:n.trim()}));return}
      if(k==='catadd'){const n=prompt('新分類名稱（例如：工作用）');if(n&&n.trim())return done(await api('/api/lib',{a:'cat_add',name:n.trim()}));return}
      if(k==='bk')return done(await api('/api/lib',{a:'backup_now'}));if(k==='usbmap')return done(await api('/api/lib',{a:'usb_map'}));if(k==='usbnow')return done(await api('/api/lib',{a:'usb_rescue'}));return}
    const lx=t.closest('[data-lx]');if(lx){if(!confirm('取消排除「'+lx.dataset.x+'」？會重新掃描，那些影片就會回來。'))return;return done(await api('/api/lib',{a:'unexclude',kind:lx.dataset.lx,x:lx.dataset.x}))}
    const lc=t.closest('[data-lc2]');if(lc){if(!confirm('移除分類「'+lc.dataset.lc2+'」？（資料夾和裡面的檔案不動）'))return;return done(await api('/api/lib',{a:'cat_del',name:lc.dataset.lc2}))}
    const lb=t.closest('[data-lb]');if(lb){if(!confirm('下次打開程式時，用這份備份還原資料庫？\n現在的資料庫會改名留著（不會刪）。'))return;return done(await api('/api/lib',{a:'restore_db',name:lb.dataset.lb}))}
    const g=t.closest('[data-lg] button');if(g){const k=g.parentElement.dataset.lg;$$('button',g.parentElement).forEach(x=>x.classList.toggle('on',x===g));const r=await api('/api/bgctl',{a:'guard',[k]:+g.dataset.v});toast(r.ok?'✔ 已儲存':(r.message||'沒存到'))}};
  el.onchange=async e=>{const t=e.target.closest('[data-lu]');if(!t)return;const r=t.dataset.lu==='on'?await api('/api/lib',{a:'usb_on',on:t.checked}):await api('/api/bgctl',t.dataset.lu==='mf'?{a:'guard',mf:t.checked}:{a:'guard',on:t.checked});toast(r.ok?'✔ 已儲存':(r.message||'沒存到'))}}
function secFaces(){return `<div class="ssec" id="fset"><div class="empty">讀取中…</div></div>`}
async function faceSet(){let j;try{j=await api('/api/faces')}catch(e){return}const el=$('#fset');if(!el)return;if(!j.ok){el.innerHTML=`<div class="empty">${esc(j.message||'人物功能沒有載入')}</div>`;return}const c=j.st.cfg||{};
  const sg=(k,v,L)=>`<div class="seg" data-fc="${k}">${L.map(([a,b])=>`<button data-v="${a}"${String(v)===String(a)?' class="on"':''}>${b}</button>`).join('')}</div>`;
  const thrK=Math.abs(c.thr-0.52)<0.02?0.52:Math.abs(c.thr-0.38)<0.02?0.38:0.45;
  el.innerHTML=`<div class="si"><b>每部影片抽幾 % 的預覽圖</b>${sg('ratio',Math.round((c.ratio||.1)*100),[[5,'5%'],[10,'10%'],[20,'20%'],[30,'30%'],[50,'50%'],[100,'全部']])}<small>越多越準、越慢。改了只影響還沒做的影片。</small></div>
   <div class="si"><b>來源</b>${sg('src',c.src,[['thumbs','每 2 秒的預覽圖（快）'],['video','影片原畫面（準，會讀硬碟）']])}</div>
   <div class="si"><b>長得像的程度</b>${sg('thr',thrK,[[0.52,'嚴格'],[0.45,'一般'],[0.38,'寬鬆']])}<small>改了按 👤 人物 →「🔁 重新分群」才會套用（取好的名字會留著）。</small></div>
   <div class="si tgr"><b>用顯示卡</b><label class="tg"><input type="checkbox" data-fcb="gpu" ${c.gpu?'checked':''}><i></i></label></div>
   <div class="si tgr"><b>晚上自動跑（${esc(c.night_from||'01:00')}～${esc(c.night_to||'07:00')}，時段外自動停，下次接著做）</b><label class="tg"><input type="checkbox" data-fcb="night" ${c.night?'checked':''}><i></i></label></div>
   <div class="si"><b>自動歸類：一部影片出現幾次以上</b>${sg('auto_min',c.auto_min,[[1,'1'],[2,'2'],[3,'3'],[5,'5'],[10,'10']])}</div>
   <div class="si"><b>環境</b><div class="row"><button class="pill" id="fchk">🔍 檢查電腦的環境</button></div><small id="fenv">套件要在電腦的 👤 人物 → ⚙ 設定 按「安裝需要的套件」。全部只在電腦上跑，不連網、不查身分。</small></div>`;
  el.onclick=async e=>{const b=e.target.closest('[data-fc] button');if(b){const k=b.parentElement.dataset.fc;let v=b.dataset.v;if(k!=='src')v=+v;if(k==='ratio')v=v/100;$$('button',b.parentElement).forEach(x=>x.classList.toggle('on',x===b));const r=await api('/api/faces',{a:'cfg',[k]:v});toast(r.ok?'✔ 已儲存':(r.message||'沒存到'));return}
    if(e.target.id==='fchk'){$('#fenv').textContent='檢查中…（5～20 秒）';const r=await api('/api/faces',{a:'check'});const E=r.env||{};
      $('#fenv').textContent=E.ok?`✔ Python ${E.py||''}、onnxruntime ${E.ort||''}、${(E.providers||[]).filter(p=>p!=='CPUExecutionProvider').join('、')||'只有 CPU'}、模型 ${Object.keys(E.models||{}).join('、')||'沒有'}`:'還沒裝好：到電腦的 👤 人物 → ⚙ 設定 按「安裝需要的套件」'}};
  el.onchange=async e=>{const t=e.target.closest('[data-fcb]');if(!t)return;const r=await api('/api/faces',{a:'cfg',[t.dataset.fcb]:t.checked});toast(r.ok?'✔ 已儲存':(r.message||'沒存到'))}}
function bindSet(sb){
  sb.onclick=async e=>{const b=e.target.closest('.seg[data-k] button');if(b){const g=b.parentElement;let v=b.dataset.v;if(g.dataset.num==='1')v=+v;$$('button',g).forEach(x=>x.classList.toggle('on',x===b));const r=await api('/api/settings',{k:g.dataset.k,v});toast(r.ok?'✔ 已儲存':(r.message||'沒存到'));const s=SETD.settings.find(x=>x.k===g.dataset.k);if(r.ok&&s)s.v=v;return}
    const u=e.target.closest('.seg[data-ui] button');if(u){const k=u.parentElement.dataset.ui,v=u.dataset.v;$$('button',u.parentElement).forEach(x=>x.classList.toggle('on',x===u));
      if(k==='mode'||k==='fs'){UI[k]=v;LS.set('ui',UI);applyUI()}else if(k==='cols'){S.cols=v;LS.set('cols',v)}else if(k==='gs')LS.set('gs',+v);else if(k==='swipeMax')LS.set('swipeMax',+v);toast('✔ 已儲存');return}
    if(e.target.closest('[data-uih]')){LS.set('syspop_h',.5);toast('✔ 已恢復');return}
    const st=e.target.closest('[data-step]');if(st){const i=st.parentElement.querySelector('input');i.value=Math.max(+i.min,Math.min(+i.max,(+i.value||0)+ +st.dataset.step));i.dispatchEvent(new Event('change',{bubbles:true}));return}
    const us=e.target.closest('[data-uistep]');if(us){const i=us.parentElement.querySelector('input');i.value=Math.max(2,Math.min(30,(+i.value||4)+ +us.dataset.uistep));LS.set('tcols',+i.value);toast('✔ 已儲存');return}
    const x=e.target.closest('[data-x]');if(x){x.classList.toggle('on');x.textContent=(x.classList.contains('on')?'✔ ':'')+x.textContent.replace(/^✔ /,'');const hide=$$('#extg [data-x]').filter(y=>!y.classList.contains('on')).map(y=>y.dataset.x);
      const r=await api('/api/settings',{k:'hide_exts',v:hide});if(r.ok){SETD.exts.hide=r.v;toast('✔ 已儲存（檔案總管會跟著變）')}return}
    const xa=e.target.closest('[data-xall]');if(xa){const hide=xa.dataset.xall==='all'?[]:SETD.exts.all.filter(z=>z!=='.mp4'&&z!=='.m4v');const r=await api('/api/settings',{k:'hide_exts',v:hide});if(r.ok){SETD.exts.hide=r.v;setCat('ext');toast('✔ 已儲存')}}};
  sb.onchange=async e=>{const t=e.target;if(t.dataset.lx){const r=await api('/api/new',{a:'lab_set',k:t.dataset.lx,v:t.value});toast(r.ok?'✔ 已儲存':(r.message||'沒存到'));if(r.ok&&r.v!=null&&t.tagName==='INPUT')t.value=r.v;return}if(t.dataset.ui==='tcols'){LS.set('tcols',Math.max(2,Math.min(30,+t.value||4)));toast('✔ 已儲存');return}if(!t.dataset.k)return;let v=t.type==='checkbox'?t.checked:t.value;if(t.type==='number')v=+v;
    const r=await api('/api/settings',{k:t.dataset.k,v});toast(r.ok?'✔ 已儲存':(r.message||'沒存到'));if(r.ok&&t.type==='number'&&r.v!=null)t.value=r.v;const s=SETD.settings.concat(SETD.lab).find(x=>x.k===t.dataset.k);if(r.ok&&s)s.v=r.v!=null?r.v:v}}
document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll()});
boot();
</script></body></html>
"""


# ============================================================ V0.5.68 🎛 三段切換＋📊 一頁總覽（跟整理的網頁共用 vs_dashui）
import vs_dashui as _DZ
PAGE = PAGE.replace('</style>', _DZ.CSS + '</style>', 1).replace('function route(){', _DZ.JS + '\nfunction route(){', 1)

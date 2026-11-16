"""📄 匯出報告（V0.1.31，不准 import Qt）：一個 HTML 檔，雙擊就能看、可以列印成 PDF、可以傳給別人.
內容：硬碟、檔案種類、遊戲／軟體、照片影片年份、重複、損毀、雜物、相似、影片分類、去過的地方、隔離區、最近做過的事."""
import os, time, json

import fc_ana as ana

CSS = """
*{box-sizing:border-box}body{margin:0;background:#f5f6f8;color:#1d232c;font:14px/1.55 -apple-system,"Segoe UI","Microsoft JhengHei","PingFang TC",sans-serif}
.w{max-width:1000px;margin:0 auto;padding:24px 18px 60px}h1{font-size:26px;margin:0}h2{font-size:18px;margin:0 0 10px;display:flex;gap:8px;align-items:center}
.sub{color:#6b7480;font-size:13px}.card{background:#fff;border:1px solid #e3e6ea;border-radius:14px;padding:16px 18px;margin-top:14px;break-inside:avoid}
.kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;margin-top:14px}.kpi{background:#fff;border:1px solid #e3e6ea;border-radius:14px;padding:12px 14px}
.kpi b{display:block;font-size:22px;margin-top:2px}.kpi span{color:#6b7480;font-size:12px}
.bar{display:flex;height:22px;border-radius:7px;overflow:hidden;background:#eef0f3;margin:6px 0 10px}.bar i{display:block;height:100%}
.leg{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:4px 14px;font-size:13px}.leg div{display:flex;gap:6px;align-items:center}
.dot{width:11px;height:11px;border-radius:3px;flex:none}.leg em{margin-left:auto;font-style:normal;color:#6b7480;white-space:nowrap}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:5px 6px;border-bottom:1px solid #eef0f3;vertical-align:top}th{color:#6b7480;font-weight:600}
td.n,th.n{text-align:right;white-space:nowrap}td.p{word-break:break-all;color:#36404c}
.yrs{display:flex;align-items:flex-end;gap:3px;height:110px;margin-top:8px}.yrs div{flex:1;max-width:56px;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;min-width:0;height:100%}
.yrs i{width:100%;background:#3b8eea;border-radius:3px 3px 0 0}.yrs small{font-size:10px;color:#6b7480;margin-top:2px}
.tag{display:inline-block;padding:1px 8px;border-radius:9px;font-size:12px;background:#eef0f3}.good{color:#178a4c}.warn{color:#c7731a}.bad{color:#d0303f}
.foot{margin-top:24px;color:#8a929c;font-size:12px;text-align:center}
@media print{body{background:#fff}.card,.kpi{border-color:#ccc}.w{padding:0}}
"""


def fmt_b(b):
    b = float(b or 0)
    return f'{b / 1e12:.2f} TB' if b >= 1e12 else f'{b / 1e9:.2f} GB' if b >= 1e9 else f'{b / 1e6:.0f} MB' if b >= 1e6 else f'{b / 1e3:.0f} KB'


def day(t):
    try: return time.strftime('%Y-%m-%d', time.localtime(float(t))) if t else ''
    except Exception: return ''


e = lambda s: str(s if s is not None else '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#x27;')  # 不用 html 模組：舊版啟動器沒打包
N = lambda n: f'{int(n or 0):,}'


def _sec(fn, E):
    try: return fn(E)
    except Exception as ex:
        try: E.log.w(f'📄 報告：{fn.__name__} 失敗：{ex}')
        except Exception: pass
        return ''


def s_kpi(E):
    C = E.fc_counts(force=True); S = E.ana_result()
    k = [('📁 全部檔案', N(S.get('n') or C.get('files')) + ' 個', fmt_b(S.get('b') or C.get('bytes'))),
         ('📷 照片', N(C.get('photos')) + ' 張', ''), ('🎬 影片', N(C.get('videos')) + ' 部', ''),
         ('🔁 重複可以省', fmt_b(C.get('dup_bytes')), f"{N(C.get('dup_groups'))} 組・多 {N(C.get('dup_files'))} 份"),
         ('🩺 有問題', N(C.get('bad')) + ' 個', f"打不開 {N(C.get('broken'))}・部分 {N(C.get('partial'))}・0 位元組 {N(C.get('zero'))}"),
         ('📦 隔離區', N(C.get('quar_n')) + ' 個', fmt_b(C.get('quar_bytes')) + '・可以復原')]
    if C.get('pkg_n'): k.append(('🎮 遊戲／軟體素材', N(C['pkg_n']) + ' 個', '不列入整理'))
    return '<div class="kpis">' + ''.join(f'<div class="kpi"><span>{a}</span><b>{b}</b><span>{c}</span></div>' for a, b, c in k) + '</div>'


def s_disk(E):
    D = E.ana_result().get('disks') or []
    if not D: return ''
    rows = ''
    for d in D:
        if d.get('err'): rows += f"<tr><td>{e(d['drive'])}</td><td colspan=3 class=bad>{e(d['err'])}</td></tr>"; continue
        p = round(100 * d['used'] / d['total']) if d.get('total') else 0; col = '#d0303f' if p >= 90 else '#c7731a' if p >= 80 else '#3b8eea'
        rows += (f"<tr><td><b>{e(d['drive'])}</b></td><td style='width:45%'><div class=bar style='margin:2px 0;height:14px'><i style='width:{p}%;background:{col}'></i></div></td>"
                 f"<td class=n>用了 {p}%</td><td class=n>剩 <b>{fmt_b(d['free'])}</b>／{fmt_b(d['total'])}</td></tr>")
    return f'<div class=card><h2>💽 硬碟</h2><table>{rows}</table></div>'


def s_cats(E):
    S = E.ana_result(); T = S.get('eff') or {}; tot = sum(v[1] for v in T.values()) or 1
    if not T: return '<div class=card><h2>📊 檔案種類</h2><div class=sub>還沒做過資料分析</div></div>'
    C = [(k, nm, col) for k, nm, col in ana.CATS if k in T]; C.sort(key=lambda c: -T[c[0]][1])
    bar = ''.join(f'<i style="width:{100 * T[k][1] / tot:.2f}%;background:{col}" title="{e(nm)}"></i>' for k, nm, col in C)
    leg = ''.join(f'<div><i class=dot style="background:{col}"></i>{e(nm)}<em>{fmt_b(T[k][1])}・{100 * T[k][1] / tot:.1f}%・{N(T[k][0])} 個</em></div>' for k, nm, col in C)
    return f'<div class=card><h2>📊 檔案種類（佔多少空間）</h2><div class=sub>分析時間：{day(S.get("t1"))}，遊戲／軟體整包算一類，不拆開看</div><div class=bar>{bar}</div><div class=leg>{leg}</div></div>'


def s_pkgs(E):
    P = E.ana_pkgs('', 25) if hasattr(E, 'ana_pkgs') else []
    P = P.get('rows') if isinstance(P, dict) else P
    if not P: return ''
    rows = ''.join(f"<tr><td>{ana.PKG_ICON.get(p.get('pkg'), '📦')}</td><td class=p>{e(p.get('path'))}<br><span class=sub>{e(p.get('why'))}</span></td><td class=n>{fmt_b(p.get('b'))}</td></tr>" for p in P[:25])
    return f'<div class=card><h2>🎮 最大的遊戲／軟體（整包）</h2><table><tr><th></th><th>資料夾</th><th class=n>大小</th></tr>{rows}</table></div>'


def s_years(E):
    Y = E.tl.years()
    if not Y: return ''
    ys = sorted(Y); v = {y: sum(m['photo'] + m['video'] for m in Y[y].values()) for y in ys}; mx = max(v.values()) or 1
    bars = ''.join(f'<div title="{y}：{v[y]:,}"><i style="height:{max(2, 100 * v[y] / mx):.1f}%"></i><small>{y if len(ys) <= 14 else y[2:]}</small></div>' for y in ys)
    top = sorted(ys, key=lambda y: -v[y])[:3]
    return (f'<div class=card><h2>🗓 每年拍了多少（只算可靠的拍攝日期）</h2><div class=sub>最多的年份：' + '、'.join(f'{y} 年 {v[y]:,} 個' for y in top) +
            f'</div><div class=yrs>{bars}</div></div>')


def s_dups(E):
    R = E.db.q("SELECT size, hash, COUNT(*) c, MIN(path) p FROM files WHERE state='' AND hash IS NOT NULL AND hash NOT LIKE '!%' GROUP BY size, hash HAVING c>1 ORDER BY size*(c-1) DESC LIMIT 30")
    if not R: return '<div class=card><h2>🔁 重複檔</h2><div class="sub good">沒有找到一模一樣的檔案 ✔</div></div>'
    rows = ''.join(f"<tr><td class=p>{e(r['p'])}</td><td class=n>{r['c']} 份</td><td class=n>{fmt_b(r['size'])}</td><td class=n><b>{fmt_b(r['size'] * (r['c'] - 1))}</b></td></tr>" for r in R)
    return f'<div class=card><h2>🔁 最佔空間的重複檔（前 30 組）</h2><table><tr><th>其中一個的位置</th><th class=n>幾份</th><th class=n>每個</th><th class=n>可以省</th></tr>{rows}</table></div>'


def s_bad(E):
    R = E.db.q("SELECT path, size, health, health_msg FROM files WHERE state='' AND keep=0 AND health IN ('broken','partial','zero') ORDER BY health, path LIMIT 200")
    if not R: return '<div class=card><h2>🩺 損毀檢查</h2><div class="sub good">沒有找到有問題的照片影片 ✔</div></div>'
    nm = {'broken': ('打不開', 'bad'), 'partial': ('部分損毀', 'warn'), 'zero': ('0 位元組', 'bad')}
    rows = ''.join(f"<tr><td><span class='tag {nm[r['health']][1]}'>{nm[r['health']][0]}</span></td><td class=p>{e(r['path'])}<br><span class=sub>{e(r['health_msg'])}</span></td><td class=n>{fmt_b(r['size'])}</td></tr>" for r in R)
    return f'<div class=card><h2>🩺 有問題的照片影片（最多列 200 個）</h2><table>{rows}</table></div>'


def s_junk(E):
    J = E.junk_view(); C = J.get('counts') or {}
    if not J.get('ok') or not C: return ''
    rows = ''.join(f"<tr><td>{ic} {e(nm)}</td><td class=n>{N(C[k][0])} 個</td><td class=n>{fmt_b(C[k][1])}</td></tr>" for k, ic, nm in ana.JUNK_KINDS if k in C and k != 'big')
    return f'<div class=card><h2>🧹 雜物</h2><table>{rows}</table></div>' if rows else ''


def s_vc(E):
    C = E.vc.cats()
    if not C: return ''
    tot = (E.db.one("SELECT COUNT(*) FROM files WHERE state='' AND kind='video'") or [0])[0]; tg = sum(c['n'] for c in C)
    rows = ''.join(f"<tr><td><i class=dot style='display:inline-block;background:{e(c.get('color') or '#3b8eea')}'></i> {e(c['name'])}</td><td class=n>{N(c['n'])} 部</td><td class=n>{fmt_b(c['b'])}</td><td class=n>{'還沒搬 ' + N(c['wait']) if c['wait'] else '<span class=good>都搬好了</span>'}</td></tr>" for c in C)
    return f'<div class=card><h2>🎞 影片分類</h2><div class=sub>分好 {N(tg)} 部（全部 {N(tot)} 部的 {100 * tg / tot if tot else 0:.1f}%）</div><table>{rows}</table></div>'


def s_geo(E):
    S = E.geo.summary()
    if not S.get('n'): return ''
    P = E.geo.places(9, 15)
    rows = ''.join(f"<tr><td class=n>{N(p['n'])}</td><td>{day(p['t0'])}{' ～ ' + day(p['t1']) if day(p['t1']) != day(p['t0']) else ''}</td><td><a href='https://www.google.com/maps?q={p['lat']},{p['lon']}'>{p['lat']:.3f}, {p['lon']:.3f}</a></td></tr>" for p in P)
    return (f'<div class=card><h2>🗺 最常去的地方（約 40 公里一區）</h2><div class=sub>有定位的 {N(S["n"])} 個（全部 {N(S["all"])} 個的 {round(100 * S["n"] / S["all"]) if S["all"] else 0}%）；點座標開 Google 地圖</div>'
            f'<table><tr><th class=n>個數</th><th>時間</th><th>位置</th></tr>{rows}</table></div>')


def s_moves(E):
    R = E.db.q('SELECT t, reason, src, dst, undone FROM moves ORDER BY id DESC LIMIT 40')
    if not R: return ''
    rows = ''.join(f"<tr><td style='white-space:nowrap'>{time.strftime('%m-%d %H:%M', time.localtime(r['t']))}</td><td>{e(r['reason'])}{' <span class=tag>已復原</span>' if r['undone'] else ''}</td><td class=p>{e(r['src'])}</td></tr>" for r in R)
    return f'<div class=card><h2>📦 最近搬過的（最新 40 筆，都可以在隔離區復原）</h2><table><tr><th>時間</th><th>原因</th><th>原本位置</th></tr>{rows}</table></div>'


def s_bak(E):
    j = E.bak.check(); T = j['tot']; tot = sum(v[1] for v in T.values()) or 1
    K = (('ok', '#178a4c', '別顆硬碟也有'), ('same', '#c7731a', '只在同一顆硬碟有副本'), ('one', '#d0303f', '只有一份'), ('wait', '#8a929c', '還沒比對完'))
    bar = ''.join(f'<i style="width:{100 * T[k][1] / tot:.2f}%;background:{c}"></i>' for k, c, _n in K)
    leg = ''.join(f'<div><i class=dot style="background:{c}"></i>{n}<em>{N(T[k][0])} 個・{fmt_b(T[k][1])}</em></div>' for k, c, n in K)
    top = ''.join(f"<tr><td class=p>{e(p)}</td><td class=n>{N(n)}</td><td class=n>{fmt_b(b)}</td></tr>" for _d, p, n, b in j['top'][:15])
    return (f'<div class=card><h2>💾 備份狀況（照片影片）</h2><div class=bar>{bar}</div><div class=leg>{leg}</div>'
            + (f'<div class=sub style="margin-top:10px">最需要備份的資料夾：</div><table>{top}</table>' if top else '') + '</div>')


def s_events(E):
    j = E.evt.list(6, 15)
    if not j.get('n'): return ''
    rows = ''.join(f"<tr><td>{day(x['t0'])}{' ～ ' + day(x['t1']) if x['days'] > 1 else ''}</td><td class=n>{N(x['n'])}</td><td class=n>{fmt_b(x['b'])}</td><td class=p>{e(x['dir'])}</td></tr>" for x in j['rows'][:20])
    return f'<div class=card><h2>🧳 最近的活動（共 {N(j["n"])} 次，列最近 20 次）</h2><table><tr><th>日期</th><th class=n>個數</th><th class=n>大小</th><th>主要資料夾</th></tr>{rows}</table></div>'


def s_clean(E):
    I = [('🖼 相似照片', E.sim.info()), ('📸 連拍', E.burst.info()), ('🎬 相似影片', E.simv.info())]
    rows = ''.join(f"<tr><td>{n}</td><td class=n>{N(i.get('groups'))} 組</td><td class=n>{N(i.get('files'))} 個</td><td class=n>{day(i.get('t'))}</td></tr>" for n, i in I if i.get('t'))
    s = E.slim.candidates(200, 1); fv = (E.db.one("SELECT COUNT(*) FROM files WHERE state='' AND fav=1") or [0])[0]
    extra = (f"<div class=sub style='margin-top:8px'>🗜 影片瘦身：{N(s.get('n'))} 部可以轉 H.265，估計省 <b>{fmt_b(s.get('save'))}</b>" if s.get('n') else '') + (f"・⭐ 最愛 {N(fv)} 個" if fv else '') + ('</div>' if s.get('n') or fv else '')
    if not rows and not extra: return ''
    return f'<div class=card><h2>🧹 還可以清的</h2>' + (f'<table><tr><th></th><th class=n>組</th><th class=n>檔案</th><th class=n>上次找</th></tr>{rows}</table>' if rows else '') + extra + '</div>'


def s_cams(E):
    R = E.db.q("SELECT make, model, COUNT(*) n, SUM(size) b, MIN(NULLIF(taken,0)) t0, MAX(taken) t1 FROM files WHERE state='' AND kind IN ('photo','video') AND (make!='' OR model!='') GROUP BY make, model HAVING n>=3 ORDER BY t0")
    if not R: return ''
    rows = ''.join(f"<tr><td>📷 {e(r['make'])} {e(r['model'])}</td><td class=n>{N(r['n'])}</td><td class=n>{fmt_b(r['b'])}</td><td>{day(r['t0'])[:4]}{' → ' + day(r['t1'])[:4] if day(r['t1'])[:4] != day(r['t0'])[:4] else ''}</td></tr>" for r in R)
    return f'<div class=card><h2>📱 用過的手機相機</h2><table><tr><th></th><th class=n>個數</th><th class=n>大小</th><th>使用期間</th></tr>{rows}</table></div>'


SECTIONS = [s_kpi, s_disk, s_cats, s_bak, s_clean, s_years, s_events, s_cams, s_dups, s_bad, s_junk, s_pkgs, s_vc, s_geo, s_moves]


def build(E):
    """做好報告：回傳 (檔案路徑, 檔名)。存在 Data\\reports，最多留 20 份."""
    roots = E.fc_list('roots'); now = time.time()
    body = ''.join(_sec(f, E) for f in SECTIONS)
    doc = (f'<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<title>FileCompare 整理報告 {time.strftime("%Y-%m-%d", time.localtime(now))}</title><style>{CSS}</style></head><body><div class=w>'
           f'<h1>📄 FileCompare 整理報告</h1><div class=sub>{time.strftime("%Y-%m-%d %H:%M", time.localtime(now))}・V{e(E.version)}・整理的資料夾：{"、".join(e(r) for r in roots) or "（還沒設定）"}</div>'
           f'{body}<div class=foot>這份報告只是「看」，不會改動任何檔案。可以用瀏覽器「列印 → 存成 PDF」。</div></div></body></html>')
    d = E.data / 'reports'; d.mkdir(parents=True, exist_ok=True)
    name = f'FileCompare_報告_{time.strftime("%Y%m%d_%H%M%S", time.localtime(now))}.html'; p = d / name
    p.write_text(doc, encoding='utf-8')
    old = sorted(d.glob('FileCompare_報告_*.html'))
    for x in old[:-20]:
        try: x.unlink()
        except OSError: pass
    E.log.w(f'📄 匯出報告：{p}')
    return str(p), name

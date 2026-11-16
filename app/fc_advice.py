"""💡 建議你做（V0.1.35，不准 import Qt）：看現在的狀況，照「能省多少／多急」排出下一步要做什麼；總覽最上面顯示，點一下就到那個工具."""
import re, time


def fb(b):
    b = float(b or 0)
    return f'{b / 1e12:.1f} TB' if b >= 1e12 else f'{b / 1e9:.1f} GB' if b >= 1e9 else f'{b / 1e6:.0f} MB'


class Advice:
    def __init__(self, E):
        self.E = E; self.c = (0, None)

    def get(self, force=False):
        if not force and self.c[1] is not None and time.time() - self.c[0] < 300: return self.c[1]
        E = self.E; A = []

        def add(score, ic, title, sub, go, btn):
            A.append({'score': score, 'ic': ic, 'title': title, 'sub': sub, 'go': go, 'btn': btn})
        C = E.fc_counts()
        try:                                                                         # 硬碟快滿了：最急
            for d in E.ana_result().get('disks') or []:
                if d.get('total') and d['free'] / d['total'] < 0.08:
                    add(1e13, '💽', f"硬碟 {d['drive']} 快滿了（剩 {fb(d['free'])}）", '先處理下面能省空間的項目', '', '')
        except Exception: pass
        if not E.fc_list('roots'): add(1e14, '📁', '還沒設定要整理的資料夾', '到「設定」或電腦版首頁加資料夾', 'set', '去設定')
        try:                                                                         # 🧭 整包複本（V0.2.17）：比一組一組處理快很多，排在重複檔前面
            dc = getattr(E.dpl, 'c', None)
            if dc and dc[1]:
                cp = [p for p in dc[1]['pairs'] if p['rel'] == 'copy']; b_ = sum(p['bytes'] for p in cp)
                if b_ > 50e6: add(C.get('dup_bytes', 0) + 1, '🧭', f'{len(cp)} 個資料夾整包被複製（{fb(b_)}）', '保留建議那邊、複本一次搬到隔離區；部分重複的可以合併', 'tool:dpl', '去處理')
            elif C.get('dup_groups', 0) > 500: add(C.get('dup_bytes', 0) + 1, '🧭', f"{C['dup_groups']:,} 組重複：先用資料夾看", '大多是整包資料夾被複製，一次處理一整包比一組一組快', 'tool:dpl', '去看看')
        except Exception: pass
        try:                                                                         # 📦 你整理過的資料夾還沒審（V0.2.17）
            pc = getattr(E.vg, '_cache', (0, None))[1]
            if pc is None: E.vg.warm()
            if pc:
                L = [g for g in pc.values() if g['todo']]; n = sum(g['todo'] for g in L)
                if L: add(5e9 + n * 1e5, '📦', f'{len(L):,} 包你整理過的資料夾（{n:,} 部影片）', '例如「2020-日本旅遊」：整包看一眼，整包放到已篩選，比一部一部快', 'tool:pk', '去看看')
        except Exception: pass
        try:                                                                         # 💡 照你的習慣可以一次分很多（V0.3.27）
            d = E.vc.hint_summary()                                                 # 背景算好的（最多 10 分鐘前），不卡畫面
            if d:
                if d.get('n', 0) >= 20:
                    cc = {}
                    for r in d['rows']: cc[r['cat']] = cc.get(r['cat'], 0) + r['n']
                    top = '、'.join(f"{k} {v:,}" for k, v in sorted(cc.items(), key=lambda x: -x[1])[:3])
                    add(4.5e9 + d['n'] * 1e5, '💡', f"照你的習慣，{d['n']:,} 部可以一次分好", f'例如 {top}；分類頁「📚 整批分類 → 💡 照建議分…」一條一條勾', 'vc', '去分類')
        except Exception: pass
        try:                                                                         # 📷 相機名跟分類名一樣（例如 DJI）：一次分（V0.3.20）
            cats = [c for c in E.vc.cats() if len(str(c['name'])) >= 2]
            if cats:
                CM = {}                                                              # 🐞 V0.4.18：以前叫 C，蓋掉上面的統計 → 總覽「重複檔可以省」「有問題」建議不見
                for mk, md, n_ in E.db.q("SELECT f.make, f.model, COUNT(*) FROM files f LEFT JOIN vc_tag t ON t.fid=f.id WHERE t.fid IS NULL AND f.state='' AND f.kind='video' GROUP BY f.make, f.model"):   # 一次算（V0.3.69）
                    cm = E.vc._cam(mk, md)
                    if cm: CM[cm] = CM.get(cm, 0) + n_
                for cm, n in sorted(CM.items(), key=lambda x: -x[1]):
                    c = next((c for c in cats if str(c['name']).lower() in cm.lower()), None)
                    if c and n >= 3:
                        add(3e9 + n * 1e5, '📷', f'「{cm}」拍的 {n:,} 部還沒分', f'相機名有「{c["name"]}」：到分類頁「📚 整批分類 → 📷 照相機一次分」一次分到 {c["name"]}', 'vc', '去分類'); break
        except Exception: pass
        try:                                                                         # 🐾 有養寵物：電腦幫你找有貓狗的（V0.2.99）
            st = E.pet.status()
            if st.get('dog', 0) + st.get('cat', 0) and not st.get('run'):
                n = E.pet.todo_count()
                if n: add(4e9 + n * 1e5, '🐾', f'{n:,} 部還沒分類的影片裡有貓或狗', '分類頁上面的篩選選「🐾 還沒分類・有貓或狗的」，快速看過一次分到 Family', 'vc:pet', '去看')
            SC = {x['k']: x['n'] for x in st.get('scenes') or []}
            if SC.get('screen', 0) >= 20 and not st.get('run'):                        # 📺 拍到螢幕的（V0.3.77）：多半是隨手錄的，可以考慮 Delete
                add(3.5e9 + SC['screen'] * 1e5, '📺', f"{SC['screen']:,} 部還沒分類的影片，電腦猜是拍到螢幕／網頁", '按「去看」只看這些，看過沒問題就 Ctrl＋A 整組分到 Delete（電腦會看錯，先看）', 'vc:pet_s_screen|📺 拍到螢幕／網頁／文件', '去看')
            pc_ = next((c for c in E.vc.cats() if re.search(r'寵物|pet|貓|狗|dog|cat', str(c['name']), re.I)), None)
            if pc_ and SC.get('petonly', 0) >= 5 and not st.get('run'):              # 🐾 有「寵物」類：只有貓狗的建議分過去（V0.4.16）
                add(3.9e9 + SC['petonly'] * 1e5, '🐾', f"{SC['petonly']:,} 部只拍到貓狗（沒有人）還沒分", f"多半可以分到「{pc_['name']}」：按「去看」最像的排前面，整段勾起來分", 'vc:pet_s_petonly|🐾 只有貓狗（沒拍到人）', '去看')
            if SC.get('dark', 0) >= 10 and not st.get('run'):                          # 🌑 很暗／全黑（V0.3.78）
                add(3.6e9 + SC['dark'] * 1e5, '🌑', f"{SC['dark']:,} 部還沒分類的影片幾乎全黑", '多半是放在口袋、包包裡誤錄的：按「去看」確認，再 Ctrl＋A 整組分到 Delete', 'vc:pet_s_dark|🌑 很暗／全黑', '去看')
            if SC.get('many', 0) >= 20 and not st.get('run'):
                add(3.4e9 + SC['many'] * 1e5, '👥', f"{SC['many']:,} 部還沒分類的影片有 3 個人以上", '多半是聚會、家族活動：按「去看」只看這些，Ctrl＋A 整組勾、取消不對的，再按分類', 'vc:pet_s_many|👥 3 個人以上', '去看')
            if not st.get('checked') and not st.get('run') and C.get('videos', 0) >= 20:
                add(2e9, '🐾', '試試電腦幫你找有貓狗的影片', '電腦自己看每部影片有沒有貓狗、人、全黑誤錄的（Windows 內建、背景做）：按「開始」就好，看完這裡會告訴你結果', 'act:pet_start', '🐾 開始')
        except Exception: pass
        if C.get('dup_bytes', 0) > 50e6: add(C['dup_bytes'], '🔁', f"重複檔可以省 {fb(C['dup_bytes'])}", f"{C.get('dup_groups', 0):,} 組一模一樣的；一鍵照規則留一份", 'tool:dup', '去處理')
        bad = C.get('bad', 0)
        if bad: add(5e9 + bad * 1e6, '🩺', f'{bad:,} 個照片影片有問題', '打不開／部分損毀／0 位元組：先試著修，救不回來的搬走', 'tool:hl', '去看看')
        try:
            S = E.simv.info()
            if S.get('groups'): add(S['groups'] * 3e8, '🎬', f"{S['groups']:,} 組相似影片", '同一部影片被轉檔、壓縮過的副本', 'tool:simv', '去處理')
            S = E.burst.info()
            if S.get('groups'): add(S['groups'] * 4e6, '📸', f"{S['groups']:,} 串連拍", '每串挑最清楚的一張留下', 'tool:burst', '去挑')
            S = E.sim.info()
            if S.get('groups'): add(S['groups'] * 3e6, '🖼', f"{S['groups']:,} 組相似照片", '幾乎一樣的照片（重新壓縮、連拍）', 'tool:sim', '去處理')
            elif C.get('photos', 0) > 100 and not S.get('t'): add(2e8, '🖼', '還沒找過相似照片', '指紋已經算好了，幾分鐘就好', 'tool:sim', '開始找')
        except Exception: pass
        try:
            J = E.junk_view(); jc = J.get('counts') or {}
            n = sum(v[0] for k, v in jc.items() if k != 'big'); b = sum(v[1] for k, v in jc.items() if k != 'big')
            if n > 20: add(max(b, n * 1e5), '🧹', f'{n:,} 個雜物（空資料夾、0 位元組、暫存檔）', f'約 {fb(b)}，整類搬走', 'tool:junk', '去清理')
        except Exception: pass
        try:
            s = E.slim.candidates(500, 1)
            if s.get('save', 0) > 5e9: add(s['save'] * 0.6, '🗜', f"影片瘦身可以省 {fb(s['save'])}", f"{s['n']:,} 部很大的舊編碼影片（要花電腦時間）", 'tool:slim', '去看看')
        except Exception: pass
        try:
            todo = (E.db.one("SELECT COUNT(*) FROM files f LEFT JOIN vc_tag t ON t.fid=f.id WHERE f.state='' AND f.kind='video' AND t.fid IS NULL") or [0])[0]
            wait = sum(c['wait'] for c in E.vc.cats())
            if wait: add(4e9, '🚚', f'{wait:,} 部分好的影片還沒搬', '按一下「🚚 搬」就會搬進分類資料夾', 'vc', '去搬')
            if wait:                                                                 # 🧐 搬之前：可能分錯的（V0.4.32）
                ns = len(E.vc.suspects())
                if ns: add(4.05e9, '🧐', f'搬之前看一下：{ns:,} 部可能分錯了', '跟同一個資料夾大部分不一樣、或跟你平常的分法不一樣；按「去看」逐一確認', 'vc:chk|🧐 可能分錯的', '去看')
            if todo: add(todo * 1e5, '🎞', f'{todo:,} 部影片還沒分類', '一部一部看 16 格、按分類', 'vc', '繼續分類')
        except Exception: pass
        try:
            B = E.bak.check(); one = B['tot']['one'][1] + B['tot']['same'][1]
            if B['ndrives'] > 1 and one > 1e9: add(6e9, '💾', f'{fb(one)} 的照片影片沒有備份', '只有一份、或只在同一顆硬碟：複製到另一顆就安全', 'tool:bak', '去看看')
        except Exception: pass
        try:
            th = E.db.one("SELECT COUNT(*), COALESCE(SUM(size),0) FROM files WHERE state='' AND src='thumb'") or (0, 0)
            if th[0] > 300: add(2e8 + th[1], '🗂', f'{th[0]:,} 個手機縮圖快取（.thumbnails）', '不是你拍的照片，是手機自動做的小圖：用「🏷 依來源整理」集中起來', 'tool:osrc', '去整理')
        except Exception: pass
        try:                                                                         # 🔀 兩類好像是同一種（V0.4.52）
            SYN = [('family', '家庭', '家人', '家'), ('pet', 'pets', '寵物', '貓狗'), ('travel', 'trip', '旅遊', '旅行'), ('work', '工作', '公司'), ('delete', 'del', '刪除', '垃圾', '不要')]
            nm = {str(c['name']).strip().lower(): c['name'] for c in E.vc.cats()}
            for g in SYN:
                hit = [nm[k] for k in g if k in nm]
                if len(hit) >= 2: add(3.3e9, '🔀', f'「{hit[0]}」和「{hit[1]}」好像是同一種分類', '分類頁「⚙ 管理」→「🔀 併到…」可以併成一類（還沒搬的都改過去）', 'vc', '去管理'); break
        except Exception: pass
        if not E.ana_result(): add(3e9, '📈', '還沒做過資料分析', '看每一類佔多少、哪些是遊戲軟體（只看不動）', 'home', '')
        if C.get('quar_bytes', 0) > 20e9: add(1e7, '📦', f"隔離區有 {fb(C['quar_bytes'])}", '確定不要的話，可以自己到隔離區資料夾刪掉（程式不會幫你刪）', 'tool:q', '看隔離區')
        A.sort(key=lambda a: -a['score'])
        out = {'ok': True, 'rows': A[:6], 't': time.time()}; self.c = (time.time(), out); return out

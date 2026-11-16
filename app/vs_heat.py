"""🌡 轉檔看溫度＋自己學（V0.5.81）.

這台 ITX 主機板的供電 IC 過熱會直接斷電。轉檔不急，慢慢轉、不要當機就好：
1. 有空才開始：整台電腦（TikLive＋其他）留給這邊的 CPU 空間要連續 1 分鐘 ≥ 設定（預設 10%）才開新的一部。
2. 一熱就停：看的溫度（顯示卡＋有的話 CPU、主機板感測器）任何一個到上限 → 這邊 CPU 壓到 2%（等於先停），
   降到上限 −8°C 才再開新的。
3. 涓流：轉的時候把溫度壓在「上限 −5°C」：比目標熱 → 這邊的 CPU 上限每 20 秒 ×0.75；涼 4 度以上 → +1%。
4. 轉完一部休息：休息時間＝學到的「降回開始溫度要幾分鐘」（2～30 分鐘），而且要降回開始溫度 +3°C 以內。
5. 自己學：每一部記下 開始溫度、最高溫度、轉了幾分鐘、轉完幾分鐘降回來，存在資料庫 heat_log，
   平均起來就知道「轉一部大概升幾度、要休息幾分鐘」，下一部照這個排。

溫度從哪裡來：顯示卡＝nvidia-smi（本來就有）；CPU／主機板＝有開 LibreHardwareMonitor（或 OpenHardwareMonitor）時從它的 WMI 讀，
30 秒一次（沒開就只看顯示卡）。主機板上那顆供電 IC 通常叫「VRM」「MOS」或 SuperIO 的 Temperature #n，可以在設定指定要看哪一個。
沒有 Qt。決策（Heat.step）是純函式，Linux 也能測。
"""
import json
import os
import re
import subprocess
import threading
import time
from collections import deque

CONV_KINDS = ('conv', 'slim', 'enc')


class Heat:
    TICK = 2.0

    def __init__(self):
        self.state = 'ok'; self.why = ''; self.sess = None; self.cool = None; self.rest_until = 0.0; self.spare_since = 0.0
        self.cap = None; self.hist = deque(maxlen=900); self.sens = {}; self.sens_t = 0.0; self.sens_err = ''; self.stats = {}; self.log = deque(maxlen=40)
        self._busy = False

    # ---------------------------------------------------------------- 溫度
    def watched(self, gpu_t, cfg):
        """[(名稱, 溫度, 上限)]：顯示卡一定看；CPU Package、指定的主機板感測器有讀到才看."""
        out = []
        if gpu_t is not None: out.append(('顯示卡', float(gpu_t), float(cfg('thermal_gpu') or 75)))
        S = dict(self.sens) if time.time() - self.sens_t < 120 else {}
        cpu = [v for k, v in S.items() if re.search(r'cpu package|core \(tctl|tdie|cpu \(tctl', k, re.I)]
        if cpu: out.append(('CPU', max(cpu), float(cfg('heat_cpu') or 80)))
        want = str(cfg('heat_board') or 'auto')
        if want == 'auto':
            B = [(k, v) for k, v in S.items() if re.search(r'vrm|mos|vcore|pch|chipset', k, re.I)]
        elif want == 'off': B = []
        else: B = [(k, v) for k, v in S.items() if k == want]
        if B:
            k, v = max(B, key=lambda x: x[1]); out.append((k.split('｜')[-1], v, float(cfg('heat_board_max') or 85)))
        return out

    def read_sensors(self):
        """LibreHardwareMonitor／OpenHardwareMonitor 的 WMI（有開才有）。背景跑，30 秒一次."""
        if os.name != 'nt' or self._busy or time.time() - self.sens_t < 30: return
        self._busy = True

        def job():
            try:
                ps = ("$ErrorActionPreference='SilentlyContinue';[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
                      "foreach($ns in 'root/LibreHardwareMonitor','root/OpenHardwareMonitor'){Get-CimInstance -Namespace $ns -ClassName Sensor | "
                      "Where-Object {$_.SensorType -eq 'Temperature'} | ForEach-Object { $_.Parent+'｜'+$_.Name+'|'+$_.Value }}")
                r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps], capture_output=True, timeout=20,
                                   creationflags=0x08000000 | 0x00004000, stdin=subprocess.DEVNULL)
                S = {}
                for ln in r.stdout.decode('utf-8', 'replace').splitlines():
                    if '|' not in ln: continue
                    k, v = ln.rsplit('|', 1)
                    try: x = float(v.strip().replace(',', '.'))
                    except ValueError: continue
                    if 0 < x < 130: S[k.strip()] = x
                self.sens = S; self.sens_err = '' if S else '沒有讀到 CPU／主機板溫度（LibreHardwareMonitor 沒開）：先只看顯示卡'
            except Exception as ex: self.sens_err = f'讀溫度失敗：{ex}'[:120]
            finally: self.sens_t = time.time(); self._busy = False
        threading.Thread(target=job, name='HeatSensors', daemon=True).start()

    # ---------------------------------------------------------------- 學到的
    def learn(self, db):
        try:
            R = db.q('SELECT rise, mins, cool_min, t0, peak FROM heat_log ORDER BY id DESC LIMIT 30')
            R = [tuple(r) for r in R]
            if not R: self.stats = {}; return
            rise = [r[0] for r in R if r[0] is not None]; mins = [r[1] for r in R if r[1]]; cool = [r[2] for r in R if r[2] is not None]
            self.stats = {'n': len(R), 'rise': round(sum(rise) / len(rise), 1) if rise else None, 'mins': round(sum(mins) / len(mins), 1) if mins else None,
                          'cool': round(sum(cool) / len(cool), 1) if cool else None,
                          'rate': round(sum(r[0] / r[1] for r in R if r[0] is not None and r[1]) / max(1, len([1 for r in R if r[0] is not None and r[1]])), 2)}
        except Exception: self.stats = {}

    @staticmethod
    def table(db):
        db.x('CREATE TABLE IF NOT EXISTS heat_log(id INTEGER PRIMARY KEY, t REAL, sensor TEXT, t0 REAL, peak REAL, t_end REAL, rise REAL, mins REAL, cool_min REAL, cool_to REAL, cpu_cap REAL, name TEXT)')

    # ---------------------------------------------------------------- 每 2 秒
    def step(self, now, W, active, spare, cfg, db=None, names=''):
        """W＝watched()；active＝這邊正在轉幾部；spare＝留給這邊的 CPU %（預算−其他）. 回傳這邊的 CPU 上限（None＝不管）."""
        on = cfg('heat_on') is not False
        if not on or not W:
            self.state = 'ok' if on else 'off'; self.why = '' if W or not on else '讀不到任何溫度：只照 CPU 預算'; self.cap = None
            if not W and on: self._sessions(now, W, active, cfg, db, names)
            return None
        head = min(lim - t for _n, t, lim in W); hot = min(W, key=lambda x: x[2] - x[1])
        self.hist.append((now, round(hot[1], 1), hot[0], active))
        self._sessions(now, W, active, cfg, db, names)
        full = cfg('heat_full') is not False                                     # 保守模式（控溫開）：有空才轉、轉完休息、CPU 最多 thermal_vs_max
        mx = float(cfg('thermal_vs_max') or 15) if full else 60.0
        if self.cap is None or self.cap > mx: self.cap = max(2.0, mx * 0.6) if full else mx
        if head <= 0:
            self.state = 'hot'; self.cap = 2.0; self.why = f'🌡 {hot[0]} {hot[1]:.0f}°C 到上限 {hot[2]:.0f}°C：先停（這邊 CPU 2%），降到 {hot[2] - 8:.0f}°C 以下再繼續'
        else:
            if active and now - getattr(self, '_adj_t', 0) >= 20:                  # 20 秒調一次
                self._adj_t = now
                if head < 5: self.cap = max(2.0, self.cap * 0.75)                   # 比目標（上限 −5°C）熱 → 慢下來
                elif head >= 9: self.cap = min(mx, self.cap + 1.0)                 # 很涼 → 慢慢加
            if not full:                                                         # 全速模式：只管溫度
                if self.state == 'hot' and head < 8: self.why = f'🌡 {hot[0]} {hot[1]:.0f}°C：等降到 {hot[2] - 8:.0f}°C 以下'
                elif head < 8: self.state = 'warm'; self.why = f'🌡 {hot[0]} {hot[1]:.0f}°C（上限 {hot[2]:.0f}°C）：還不夠涼，先不開新的'
                else: self.state = 'ok'; self.why = f'🌡 {hot[0]} {hot[1]:.0f}°C，全速轉（太熱會自己慢下來）'
                self.rest_until = 0.0
                if self.cool: self.cool['wait'] = False
                return round(self.cap, 1) if self.state == 'hot' or (active and self.cap < mx - 0.1) else None
            if now < self.rest_until or (self.cool and self.cool.get('wait')):
                self.state = 'rest'
                left = max(0, int((self.rest_until - now) / 60 + 0.99))
                self.why = f'🌡 轉完一部休息中（{hot[0]} {hot[1]:.0f}°C' + (f'，還要約 {left} 分鐘' if left else '，等降回開始的溫度') + '）'
            elif self.state == 'hot' and head < 8:
                self.why = f'🌡 {hot[0]} {hot[1]:.0f}°C：等降到 {hot[2] - 8:.0f}°C 以下'
            else:
                need = float(cfg('heat_spare') or 10)
                if spare is not None and spare < need: self.spare_since = 0.0
                elif not self.spare_since: self.spare_since = now
                if spare is not None and (spare < need or now - self.spare_since < 60):
                    self.state = 'wait_cpu'; self.why = f'⏳ 等電腦有空：留給這邊的 CPU {max(0, spare):.0f}%（要連續 1 分鐘 ≥ {need:.0f}%）'
                elif head < 8:
                    self.state = 'warm'; self.why = f'🌡 {hot[0]} {hot[1]:.0f}°C（上限 {hot[2]:.0f}°C）：還不夠涼，先不開新的'
                else:
                    self.state = 'ok'; self.why = f'🌡 {hot[0]} {hot[1]:.0f}°C，可以轉（涓流：這邊 CPU 最多 {self.cap:.0f}%）'
        return round(self.cap, 1) if active or self.state == 'hot' else None

    def _sessions(self, now, W, active, cfg, db, names):
        """一部轉檔開始／結束／降溫結束 → 記一筆（學起來）."""
        hot = min(W, key=lambda x: x[2] - x[1]) if W else None; T = hot[1] if hot else None
        if active and self.sess is None:
            if self.cool and db is not None: self._save_cool(now, db, T, done=False)
            self.sess = {'t': now, 't0': T, 'peak': T, 'sensor': hot[0] if hot else '', 'name': names, 'caps': []}; self.cool = None
        elif active and self.sess is not None:
            if T is not None: self.sess['peak'] = max(self.sess['peak'] or T, T); self.sess['t0'] = self.sess['t0'] if self.sess['t0'] is not None else T
            if self.cap is not None: self.sess['caps'].append(self.cap)
        elif not active and self.sess is not None:
            S = self.sess; self.sess = None
            mins = (now - S['t']) / 60.0
            if mins >= 0.5:
                self.cool = {'t': now, 'end': T, 'to': (S['t0'] if S['t0'] is not None else T), 'S': S, 'wait': True, 'mins': mins}
                lc = (self.stats or {}).get('cool'); rest = max(float(cfg('heat_rest_min') or 2), min(float(cfg('heat_rest_max') or 30), lc if lc else 5.0))
                self.rest_until = now + rest * 60
                self.log.append(f"{time.strftime('%H:%M', time.localtime(now))} 轉完一部（{mins:.0f} 分鐘，{S['sensor']} {S['t0'] or 0:.0f}→最高 {S['peak'] or 0:.0f}°C），休息 {rest:.0f} 分鐘")
        if self.cool and self.cool.get('wait') and not active:
            C = self.cool; tgt = (C['to'] or 0) + 3
            if T is None or T <= tgt or now - C['t'] > float(cfg('heat_rest_max') or 30) * 60:
                if now >= self.rest_until:
                    C['wait'] = False
                    if db is not None: self._save_cool(now, db, T, done=True)

    def _save_cool(self, now, db, T, done):
        C = self.cool; S = C['S']; self.cool = None
        try:
            self.table(db)
            caps = S.get('caps') or []
            db.x('INSERT INTO heat_log(t,sensor,t0,peak,t_end,rise,mins,cool_min,cool_to,cpu_cap,name) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                 (now, S['sensor'], S['t0'], S['peak'], C['end'], (S['peak'] - S['t0']) if S['peak'] is not None and S['t0'] is not None else None, round(C['mins'], 2),
                  round((now - C['t']) / 60.0, 2) if done else None, T, round(sum(caps) / len(caps), 1) if caps else None, str(S.get('name') or '')[:200]))
            self.learn(db)
        except Exception: pass

    def hold(self, kind):
        if kind not in CONV_KINDS: return ''
        return self.why if self.state in ('hot', 'rest', 'wait_cpu', 'warm') else ''

    def view(self):
        return {'state': self.state, 'why': self.why, 'cap': self.cap, 'sens': dict(sorted(self.sens.items())), 'sens_err': self.sens_err, 'stats': self.stats,
                'log': list(self.log)[-10:][::-1], 'sess': ({'mins': round((time.time() - self.sess['t']) / 60, 1), 't0': self.sess['t0'], 'peak': self.sess['peak'], 'sensor': self.sess['sensor']} if self.sess else None),
                'rest_left': max(0, int(self.rest_until - time.time())), 'hist': [h[1] for h in list(self.hist)[-150:]]}

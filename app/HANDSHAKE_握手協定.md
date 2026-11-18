# 🤝 程式握手協定 apphs/1（SortCut ⇄ FusionStitch）

> **給 FusionStitch 的 AI**：使用者把 SortCut 的更新包（`SC_V0.6.10.zip` 或更新的）丟給你。
> SortCut 這邊**已經做好了**，你要在 FusionStitch 做對應的這一半。照這份做，兩邊就會自動握手。
> 共用的程式碼在同一包的 `app/app_handshake.py`，**整個檔直接複製到 FusionStitch 的 app\ 裡**（只用 Python 標準函式庫，沒有 Qt），不要改它；要改規則兩邊要一起改。

## 1. 目的（使用者的話）

同一台電腦上的 SortCut（影片整理、預覽圖、H.265 轉檔）和 FusionStitch（360 拼接／轉檔）會搶 CPU、顯示卡（NVENC）、硬碟。
兩邊要「握手」：**誰需要就讓誰先跑，互相照應**。而且兩邊的**主程式（畫面、手機遠端）永遠不能被拖慢**，讓的只有背景的重工作。

## 2. 怎麼交換（不用網路）

- 資料夾：`%LOCALAPPDATA%\AppHandshake\`（沒有 LOCALAPPDATA 就用系統暫存資料夾）。
- 每個程式每 **2 秒**寫一次自己的檔：`<app>.json`（SortCut 是 `SortCut.json`，你寫 `FusionStitch.json`）。
  先寫 `.tmp` 再 `os.replace`，不會讀到一半。
- 同時讀資料夾裡**別人的**檔。`t` 超過 **10 秒**沒更新、或 `pid` 已經不在 → 當作對方不在。
- 關程式時刪掉自己的檔（`hs.stop()`）。熱更新時不要刪（`hs.stop(remove=False)`），新的那份接著寫。

## 3. 檔案內容

```json
{
  "proto": "apphs/1",
  "app": "FusionStitch",          // 固定的英文 id（檔名也用這個）
  "name": "FusionStitch",         // 顯示用名稱
  "ver": "1.2.03",
  "pid": 12345,
  "port": 8361,                   // 你的手機網頁本機埠（給對方顯示用，可以 0）
  "host": "THE_TOWER_3060",
  "t": 1763475000.12,             // 寫的時間（time.time()）
  "on": true,                     // 使用者有沒有打開握手
  "want": 2,                      // 0 閒著／1 背景小工作／2 在做重工作／3 使用者在等（按了「這邊先跑」、或正在看結果等它完成）
  "prio": 5,                      // 使用者設的優先 0～10（5＝一樣）
  "what": "拼接 2 段、轉檔 1 部",   // 現在在做什麼（給對方顯示）
  "use": {"cpu": 34.0, "gpu": 60.0, "nvenc": 2, "disks": ["D", "H"]},   // 自己（含子程式 FFmpeg）現在用掉整台的多少
  "max": {"nvenc": 8},            // 這台顯示卡 NVENC 最多幾條（整台）
  "mode": "lead"                  // 自己算出來的結果（只是給對方顯示）
}
```

## 4. 誰先（兩邊各自算，結果一定對得起來）

`app_handshake.lead_of(a, b)`：
1. `want` 大的先。
2. `want` 一樣 → `prio` 大的先。
3. 再一樣 → 沒有誰先。

然後 `Handshake.decide()` 給自己一個 `mode`：

| mode | 什麼時候 | 你要做什麼 |
|---|---|---|
| `alone` | 對方不在／閒著／只在做背景小工作，或兩邊都只是背景小工作 | 照常跑 |
| `lead` | 你先 | 照常跑（對方會讓你） |
| `yield` | 對方先，而且對方在做重工作（want ≥ 2） | **重工作**：CPU 上限 `cpu_cap`（20%）、NVENC 最多 `nvenc_cap` 條、`no_new_heavy`＝true 時**新的重工作先不開**（跑到一半的照跑，只是慢慢跑，不要砍掉） |
| `split` | 兩邊都在做重工作、優先一樣 | 重工作 CPU 上限 `cpu_cap`（45%）、NVENC 最多一半 |

- 「重工作」＝轉檔、拼接、編碼這種會吃滿 CPU／顯示卡的。畫面、手機網頁、使用者按的操作**永遠不受限制**。
- CPU 上限的做法建議：把你開的 FFmpeg 等子程式放進一個 Windows **Job Object**，用 `JOBOBJECT_CPU_RATE_CONTROL_INFORMATION`（`JOB_OBJECT_CPU_RATE_CONTROL_ENABLE | HARD_CAP`，CpuRate＝% × 100）限住。
  主程式本身不要放進去。也可以簡單一點：讓路時把子程式降到 `IDLE_PRIORITY_CLASS`＋同時只跑 1 個。
- 決定每 2 秒會變。從 `yield` 回到 `alone`／`lead` 時**慢慢放回來**（例如每 10 秒多開 1 個），不要一下全開。

## 5. 你在 FusionStitch 要做的（清單）

1. 複製 `app_handshake.py` 到你的 `app\`。
2. 寫一個 `state()` 函式，回傳：
   ```python
   {'on': 設定的開關, 'want': 0~3, 'prio': 0~10, 'what': '在做什麼',
    'use': {'cpu': 你和子程式用的整台 CPU %, 'gpu': ..., 'nvenc': 你在用幾條, 'disks': ['D']},
    'max': {'nvenc': 8}}
   ```
   - `want`：有拼接／轉檔在跑＝2；只有小的背景工作＝1；沒事＝0；使用者按了「這邊先跑」（有時間限制，例如 1 小時）＝3。
3. 程式開好時：`hs = app_handshake.Handshake('FusionStitch', 'FusionStitch', 版本, port=8361, state=state).start()`
   熱更新時舊的 `hs.stop(remove=False)`；關程式時 `hs.stop()`。
4. 你的工作排程每次要開新的重工作前看 `d = hs.decide()`：
   - `d['no_new_heavy']` → 先不開新的（畫面上寫 `d['why']`）。
   - `d['cpu_cap']` 有值 → 子程式 CPU 上限；`d['nvenc_cap']` 有值 → NVENC 條數上限。
5. 畫面（和手機網頁）加：
   - 開關「🤝 跟別的程式握手（SortCut）」（預設開）
   - 「這邊的優先」0～10（預設 5）
   - 按鈕「⏩ 這邊先跑 1 小時」＋「取消」
   - 狀態：看到誰（`d['peers']`：名稱、版本、在做什麼）、現在的 `mode` 和 `why`
6. 測試：同一台電腦兩個都開，兩邊的握手狀態都要看到對方；一邊轉檔（want 2）另一邊閒著 → 閒的那邊 alone、轉檔那邊 lead；兩邊都轉檔 → 兩邊都 split；一邊按「這邊先跑」→ 它 lead、另一邊 yield。

## 6. SortCut 這邊怎麼做的（給你參考）

- 檔名 `SortCut.json`，`want`：轉檔中＝2、只有預覽圖／讀資料這類＝1、沒事＝0、按了「這邊先跑」＝3。
- `yield` 時：讓路等級最高 Lv 2（不開新的轉檔）或 Lv 4，FFmpeg CPU 上限 20%，NVENC 條數照 `nvenc_cap`。
- `split` 時：最高 Lv 6，FFmpeg CPU 上限 45%。
- 設定在右上角 Lv →「🤝 跟別的程式握手」（手機一樣）。
- 另外 SortCut 有「🛟 主程式優先」：畫面／手機一卡，自己的背景馬上退。建議 FusionStitch 也做一樣的（畫面心跳每 100 毫秒，慢了 0.4 秒就把背景退到最低，順了 20 秒再慢慢放回來）。

## 7. 以後要改協定

`proto` 改成 `apphs/2`，兩邊都要認得 `apphs/1` 和 `apphs/2` 一段時間；`app_handshake.py` 兩邊保持同一份。

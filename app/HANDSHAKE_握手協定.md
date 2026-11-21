# 🤝 程式握手協定（apphs/1，規則第 3 版）：SortCut ⇄ FusionStitch ⇄ ComfyRemote

> **給 FusionStitch／ComfyRemote 的 AI**：使用者會把 SortCut 的更新包（`SC_V0.6.15.zip` 或更新的）也丟給你。
> 共用程式碼是同一包的 `app/app_handshake.py`（**規則第 3 版**），**整個檔直接複製到你的 app\ 裡，不要改**。
> - 規則只能有一份。你如果覺得規則要改：在這份上改、把 `RULES` 加 1，並且告訴使用者「三邊都要換這份」。
> - **不要自己另外寫一份 RULES = 3**：同一個版本號兩種內容，三個程式會各算各的。
> - 就算你還沒換：第 2 版起有「誰新就用誰的規則」——SortCut 會把第 3 版放到 `%LOCALAPPDATA%\AppHandshake\lib\app_handshake_r3.py`，
>   你的程式（第 2 版）10 秒內就會自動改用第 3 版算。換成這份只是讓你自己的畫面也看得到新欄位。

## 1. 使用者要的分配（同一台電腦跑三個程式）

| 情況 | SortCut | FusionStitch | ComfyRemote | 留給使用者 |
|---|---|---|---|---|
| SortCut 和 FusionStitch 都在做重工作 | 45% | 45% | — | 10% |
| 只有一個在做重工作 | 90%（在做的那個） | | | 10% |
| **ComfyRemote 在做事**（它最優先，通常幾分鐘就完） | 5% | 5% | **80%** | 10% |
| 大家都閒著 | 不限 | 不限 | 不限 | — |

- 「%」＝**整台電腦**的 CPU（顯示卡、硬碟照同一個比例放慢）。
- 沒在做重工作的程式（閒著、只有小的背景工作），在別人做重工作時最多 10%。
- ComfyRemote 一在做事，其他程式**新的重工作先不開**（`no_new_heavy`），跑到一半的照跑但降到 5%；ComfyRemote 做完，大家照順序慢慢回來。
- 主程式（畫面、手機遠端）永遠不受限制，限制的只有背景的重工作。

## 2. 交換方式（跟第 1、2 版一樣）

- 資料夾 `%LOCALAPPDATA%\AppHandshake\`。每個程式每 2 秒寫 `<app>.json`（先寫 `.tmp` 再 `os.replace`），並讀別人的。
- 超過 10 秒沒更新、或 pid 不在 → 當作不在。關程式 `hs.stop()`（刪檔）；熱更新 `hs.stop(remove=False)`。
- app id 固定：`SortCut`、`FusionStitch`、`ComfyRemote`。

`<app>.json` 你要給的（`state()` 回傳）：

```python
{'on': 握手開關, 'want': 0~3, 'prio': 0~10, 'what': '在做什麼（給別人看）',
 'use': {'cpu': 你和子程式用掉整台 CPU %, 'gpu': %, 'nvenc': 幾條, 'disks': ['D']},
 'max': {'nvenc': 8}}
```

- `want`：0 閒著／1 背景小工作／2 在做重工作／3 使用者在等（按了「這邊先跑」）。
- **ComfyRemote**：佇列裡有工作、或 ComfyUI 正在跑你送出的工作 ＝ `want 2`（使用者在手機上等結果也可以給 3）；全部做完 ＝ 0。
  ComfyUI 本身是另一個程式，`use.cpu／gpu` 請把 ComfyUI 的程序（python／ComfyUI）一起算進去。
- **FusionStitch**：拼接／轉檔在跑 ＝ 2。**SortCut**：轉檔在跑 ＝ 2，只有預覽圖／讀資料 ＝ 1。

## 3. 共用設定 `AppHandshake\policy.json`（三個程式的畫面都能改，最後改的為準）

用 `app_handshake.set_policy('<你的 app id>', ...)` 改、`app_handshake.policy()` 讀：

| 欄位 | 預設 | 意思 |
|---|---|---|
| `members` | 全部有 | ☑ 這台有誰：`{'FusionStitch': True, 'ComfyRemote': False}`。沒勾的程式就算開著也不算進來 |
| `reserve3` | 10 | 永遠留給使用者的 % |
| `first` | `['ComfyRemote']` | 優先程式 |
| `first_cap` | 80 | 優先程式在做事時拿幾 % |
| `yield_cap` | 5 | 優先程式在做事時，其他程式降到幾 % |
| `share` | 一樣 | 平常的比例，例如 `{'SortCut': 50, 'FusionStitch': 50}` |

（`reserve`／`reserve_on`／`idle_min` 是第 2 版的，第 3 版不用。）

## 4. 規則（`decide_with`，三個程式算出來一定一樣）

```
budget = 100 − reserve3                              # 90
只看 members 有勾、還活著、握手開著的程式
有 first 程式 want ≥ 2：
    它 → mode 'lead'，cpu_cap = first_cap（80，幾個 first 就平分）
    其他 → mode 'yield'，cpu_cap = yield_cap（5），nvenc_cap = 1，no_new_heavy = True
否則，want ≥ 2 的程式照 share 分 budget：
    自己在裡面 → mode 'split'，cpu_cap = 分到的（45，或只有自己 = 90）
    自己不在裡面 → mode 'yield'，cpu_cap = 10，no_new_heavy = False
都沒有 → mode 'alone'，cpu_cap = None（不限）
```

`hs.decide()` 回傳：`mode`、`why`（給畫面）、`cpu_cap`、`nvenc_cap`、`no_new_heavy`、`alloc`（每個程式分到幾 %，給畫面）、`budget`、`rules`。
第 2 版的程式只在 `yield`／`split` 時看 `cpu_cap`，第 3 版要限制的情況都是 `yield`／`split`（ComfyRemote 自己是 `lead`，也有 `cpu_cap` 80）。

## 5. 每個程式都要做的（清單）

1. `app_handshake.py` 換成這份（第 3 版）。
2. 照 `decide()` 限制自己的重工作：
   - `cpu_cap`：子程式（FFmpeg、ComfyUI 送出的工作…）CPU 上限。建議 Windows **Job Object** 的 CPU rate hard cap（主程式不要放進去）；做不到的話用「每做一段休息一段」的比例。
   - `no_new_heavy`：新的重工作先不開。
   - `nvenc_cap`：NVENC 條數上限。
   - 從低回到高要**慢慢放回來**（例如每 10 秒 +10%），降要馬上降。
3. **右上角「Lv 1～10」**（電腦版和手機版都要，跟 SortCut 一樣）：
   - 平常顯示現在的等級：`Lv = ceil(cpu_cap / 10)`，沒限制 ＝ Lv 10。顏色：Lv 1～3 紅、4～6 黃、7～10 綠。
   - 點下去打開「讓路／分配」面板，要有：
     - ☑ 這台有誰：SortCut、FusionStitch、ComfyRemote（改 `members`）。SortCut 自己多一個 TikLive。
     - 留給你 %、ComfyRemote 優先時拿 %、其他降到 %、平常 SortCut : FusionStitch 比例（改 policy）。
     - 現在分配：`alloc` 每個程式幾 %，和 `why`。
     - 看到誰（`peers`：名稱、版本、在做什麼）、規則第幾版（`rules`）。
4. 測試（同一台電腦三個都開）：
   - SortCut、FusionStitch 都轉檔 → 兩邊都 45%。
   - 只有一個轉 → 它 90%。
   - ComfyRemote 送出工作 → 它 80%，另外兩個 5%、不開新的；做完 → 回到 45/45。
   - 取消勾 ComfyRemote → 它做事也不影響別人。

## 6. SortCut 這邊怎麼做的（參考）

- `want`：轉檔中＝2、只有預覽圖／讀資料＝1、沒事＝0、按了「⏩ 這邊先跑」＝3。
- `cpu_cap` → 讓路等級上限 `ceil(cpu_cap/10)`（`no_new_heavy` 時最多 Lv 2），FFmpeg 放進 Job Object 限 CPU %。
- 設定在右上角 Lv →「☑ 這台有誰」「⚖ 分配」（手機一樣）。TikLive 不會握手，所以 SortCut 自己用勾選決定要不要讓它。
- 另外有「🛟 主程式優先」：畫面／手機一卡，自己的背景馬上退。建議另外兩個也做一樣的。

# 抽題邏輯改動：同一 variant_group 一輪最多一題（待主控合併）

分支 bank 依分工沒有改 `assets/app.js` 與 `tools/build.py`。這份文件寫明需要的改動，patch 檔是同目錄的 `draw.patch`。

## 為什麼要改

題庫從 98 題擴充到約 200 題。多出來的題目大多是「同一知識點的不同情境或題型變體」，例如同一個「按壓深度 5 至 6 公分」會有單選、是非、情境各一題。
每題多了 `variant_group` 欄位：同一知識點的變體共用一個值（目前等於該題主要測的知識點 id，例如 `P06`）。

目標：一輪 10 題裡，同一 variant_group 最多出一題。這樣學生重抽時會遇到同一觀念的不同問法，但同一輪不會連續看到兩題換句話說的題目。

## 目前的狀況（實測）

現行 `draw()` 對「知識點已用過」的題目扣 5 分（軟性避開）。因為目前 variant_group 等於第一個知識點，
用擴充後的題庫（212 題）在未改的 app.js 上重抽 60 輪，同一輪出現重複 variant_group 的次數是 0。
所以**不合併這個 patch 也不會壞**，只是「一組最多一題」要靠計分剛好避開，沒有保證。
以後如果 variant_group 和知識點不再一一對應（例如把兩個知識點的變體併成一組），就一定要有這個硬性條件。

## 改動內容

### 1. `tools/build.py`：把 variant_group 輸出到頁面內嵌題庫

`quiz_data()` 的輸出欄位清單加上 `"variant_group"`（沒有這個欄位的題目不受影響，`if k in q` 會略過）。

### 2. `assets/app.js`：`draw()` 加硬性條件

- 新增 `usedVg`，每抽中一題就記下它的 `variant_group`（沒有這個欄位的舊題庫退回用題號，等於沒有限制）。
- 候選題先排除 `usedId` 與 `usedVg` 都用過的題；該章沒有候選時改從全題庫找；全題庫都找不到（理論上不會發生）才放寬 variant_group 限制，只排除已抽中的題號。
- 計分函式 `score()`、章節配額、難度目標、跨輪避開已出過題目的 `seen` 邏輯都不變。

```diff
-    var pool = {}, picked = [], usedKp = {}, usedId = {};
+    // 同一 variant_group（同一知識點的不同情境／題型變體）一輪最多出一題
+    var pool = {}, picked = [], usedKp = {}, usedId = {}, usedVg = {};
 ...
+    function vgOf(q) { return q.variant_group || q.id; }
+    function free(q) { return !usedId[q.id] && !usedVg[vgOf(q)]; }
     slots.forEach(function (ch) {
-      var cand = (pool[ch] || []).filter(function (q) { return !usedId[q.id]; });
+      var cand = (pool[ch] || []).filter(free);
+      if (!cand.length) cand = QS.filter(free);
       if (!cand.length) cand = QS.filter(function (q) { return !usedId[q.id]; });
 ...
-      picked.push(best); usedId[best.id] = 1;
+      picked.push(best); usedId[best.id] = 1; usedVg[vgOf(best)] = 1;
```

## 合併方式

```bash
cd /Volumes/Work/emt-course-site          # 或整合用的 worktree
git apply --check docs/quiz-bank-2026-09-30/draw.patch   # 先確認能套（以 c97f35d 的 app.js／build.py 為底）
git apply docs/quiz-bank-2026-09-30/draw.patch
python3 tools/build.py
PT_STRICT_VG=1 python3 tools/quizgen/play_test.py file://$PWD/quiz.html
```

另一個代理若已改過 `app.js` 的 `draw()` 附近，`git apply` 可能失敗；照上面「改動內容」的三處手動加入即可，改動互相獨立。

## 驗證（已在暫存副本實測）

在 scratchpad 複製一份 worktree（題庫 212 題），套用 patch、`python3 tools/build.py`：

- `PT_STRICT_VG=1 python3 tools/quizgen/play_test.py`：3 輪 errors 0、console 0、每輪 10 題、章節 2/1/2/5、教師版題數等於題庫題數。
- 連續重抽 60 輪：同一輪重複 variant_group 0 次；60 輪內全部題目都被抽到過（`seen` 跨輪避開仍有效）。

`play_test.py` 已加上 `dup_vg` 欄位（每輪列出重複的 variant_group）。環境變數 `PT_STRICT_VG=1` 時，重複就算錯誤；
沒合併 patch 時頁面內嵌題庫沒有 variant_group，`play_test.py` 會改讀 `assets/quiz-bank.json` 對照。

## 另外請主控注意

- 分支 bank 只提交了 `assets/quiz-bank.json`，**沒有提交重新產生的根目錄 `quiz.html`**（分工限制，且另一個代理在改 quiz 頁）。
  合併後請跑一次 `python3 tools/build.py`，教師版題數與「題型／難度」統計才會更新為 212 題。
- 驗收時在 bank 分支上跑過 `python3 tools/build.py` 與 `python3 tools/quizgen/play_test.py file://$PWD/quiz.html`：
  3 輪 errors 0、console 0、教師版 212 題（結果存 `playwright-file.json`），之後把產生的 `quiz.html` 還原。

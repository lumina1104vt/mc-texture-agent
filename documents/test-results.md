# 測試資料與測試結果

## A. 單元測試（假模型，不需要 LLM server）

指令：`python -m pytest tests`。最近一次結果：**64 passed**。

| 檔案 | 數量 | 測試內容 |
| --- | --- | --- |
| `test_texture_kit.py` | 15 | 繪圖函式（座標、溢位、ASCII 錯誤訊息、`speckle`、`gem_cluster`） |
| `test_agent_reply.py` | 14 | Agent 流程：純文字回覆、程式碼執行、重試、記憶、修改與匯出、回頭看、無 import 呼叫、自訂系統提示詞、案例執行器（含 `--only` 補跑與結果合併）、輸出上限與逾時 |
| `test_reference.py` / `test_reference_tool.py` | 12 / 4 | 參考材質索引、同步、檢索、Tool |
| `test_pack_features.py` | 9 | 版本存檔、品質檢查、主題記憶、資源包匯出 |
| `test_skill.py` | 4 | skill 載入與內容 |
| `test_ui.py` | 6 | 串流顯示、上傳參考材質 |

## B. Agent 實測（真模型 `dsv4p-qwen3.5:9b`）

測試資料：`documents/test-cases.json`（10 個案例：4 種礦石 / 方塊、玻璃、木板、3 種物品、1 個複雜機器方塊）。

批次執行（需要 LLM server，結果寫入 `documents/eval-results.md`）：

```bash
python -m texture_agent.eval_cases
```

欄位：輸入、預期、步數、失敗步數、耗時、存檔、自動檢查（有存出符合 kind 的檔、方塊類整張不透明）、人工評分（畫得好不好要人看圖，留給人填）。

### 已完成的實測紀錄

| ID | 輸入 | 預期 | 實際（run2，`traces/run2-after-tool-redesign.txt`） | 結果 |
| --- | --- | --- | --- | --- |
| T01 | 紅寶石礦石 | 灰色石頭底鋪滿整張，上面有數簇紅色寶石 | 2 步、72.6 秒、零失敗；存出 `ruby_ore`，最終回傳預覽 | Pass（人工看圖：待填） |

Tool 改版前的同一案例（run1）：9 步、1,040 秒、5 步失敗，最後存出 `ruby_ore` 的第 8 版。

### 尚待實測

T02–T10 的統計還沒有記錄在本文件中。第一次批次測試跑到 T09 時，模型失控生成（見 `failure-cases.md` 失敗 5）而中斷，T01–T08 的步數與耗時因結果未即時寫檔而遺失，只留下圖。程式修正後請重跑：

```bash
python -m texture_agent.eval_cases              # 全部重跑
python -m texture_agent.eval_cases --only T09,T10   # 只補跑指定案例，結果會併進既有結果檔
```

跑完把 `eval-results.md` 的表貼進這裡，並對每張圖填人工評分。

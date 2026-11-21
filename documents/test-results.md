# 測試資料與測試結果

## A. 單元測試（假模型，不需要 LLM server）

指令：`python -m pytest tests`。最近一次結果：**62 passed**。

| 檔案 | 數量 | 測試內容 |
| --- | --- | --- |
| `test_texture_kit.py` | 15 | 繪圖函式（座標、溢位、ASCII 錯誤訊息、`speckle`、`gem_cluster`） |
| `test_agent_reply.py` | 12 | Agent 流程：純文字回覆、程式碼執行、重試、記憶、修改與匯出、回頭看、無 import 呼叫、自訂系統提示詞、案例執行器 |
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

T02–T10 還沒有跑，結果不在本文件中。跑完 `eval_cases` 後，把 `eval-results.md` 的表貼進這裡，並對每張圖填人工評分。

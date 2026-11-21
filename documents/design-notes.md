# 設計說明：架構、技術選用與錯誤處理

## 架構

```
使用者輸入（Gradio 對話介面，可附加參考材質 jar / zip）
   ↓
CodeAgent（smolagents，LLM = Ollama 的 dsv4p-qwen3.5:9b）
   │  每一步：Thought → 一段 Python 程式碼
   ↓
LocalPythonExecutor（沙盒，只允許 numpy / PIL / texture_kit）
   │  程式碼內呼叫 Tool 或 texture_kit
   ↓
Tool：save_texture · find_reference_textures · get_theme · save_theme · export_resource_pack
   ↓
Observation（Tool 回傳值、print 輸出或錯誤訊息）→ 回到下一步，直到 final_answer
   ↓
輸出：16×16 PNG（output/）+ 預覽圖；匯出時為資源包 zip
```

## 為什麼是 ReAct（CodeAgent）

畫一張材質本來就是多步驟、要看結果再調整的工作：畫 → 存檔（被品質檢查擋下或通過）→ 看預覽 → 不滿意就改。每一步的 Observation（錯誤訊息、預覽圖）會決定下一步，所以用 ReAct 迴圈；不用固定流程的 Workflow，因為「要重畫幾次、改哪裡」事先無法決定。選 CodeAgent 而不是 JSON Tool Calling，是因為畫圖需要迴圈、座標與變數，寫成程式碼比逐次呼叫 Tool 自然得多。

## 技術選用表

| 技術 | 是否使用 | 理由 |
| --- | --- | --- |
| LLM | 是 | 核心推理與寫繪圖程式碼；限制是只能用開源模型，目前為 9B（速度考量無法更大） |
| ReAct / Tool | 是 | 多步驟畫圖與修正，見上節；5 個 Tool 都是真正可執行的 Python |
| Memory | 是 | 對話記憶（同一個 Agent 實例不重設，才能「再亮一點」）；主題記憶存成 JSON（`DATA_DIR/themes/`），跨對話沿用色票 |
| RAG | 是（選用） | 使用者提供參考材質時，以檔名做 Chroma 向量檢索，取得 ASCII 圖與色票；沒提供時略過。材質有版權，所以不內建 |
| Self-Reflection | 是 | 存檔後 Agent 看到成品圖，對照需求自我檢查，不對就重畫（最多 `REVIEW_ROUNDS` 次） |
| Guardrails | 是 | 沙盒執行器的匯入白名單、名稱驗證、品質檢查（不通過不存檔）、步數上限 |
| Multi-Agent | 否 | 單一 Agent 已足以完成需求；多 Agent 會讓 9B 更慢 |

## 錯誤處理（Error Handling）

從內到外共六層，每一層的錯誤都會變成下一步的 Observation，讓 Agent 自己修正：

1. **Tool 層**：名稱、kind、尺寸、陣列形狀、數值範圍不合法時丟出說明原因的錯誤（各 Tool 的清單見 `tools.md`）。
2. **函式庫層**：`texture_kit` 座標超出畫布、`stamp_ascii` 列長不一或超出畫布時報錯，並附上具體建議（例如直接給補 `.` 的列）；顏色運算限制在 0–255，不會溢位。
3. **程式碼層**：沙盒執行器的例外（未定義變數、禁用函式、語法錯誤）原樣回給 Agent。
4. **格式層**：程式碼區塊壞掉時重試；回覆完全沒有程式碼區塊時，視為對使用者說的話並結束這一輪（避免 Agent 用 `print()` 講話而空轉）。
5. **品質層**：`save_texture` 的品質檢查（可見像素少於 8、顏色超過 48 種、前五色涵蓋率低於 70%）不通過就不存檔；存檔後還沒看過成品就想 `final_answer`，會被擋下要求先檢查。
6. **迴圈控制**：`MAX_STEPS`（預設 16）限制總步數，`REVIEW_ROUNDS`（預設 2）限制回頭重畫的次數，避免無限重畫；`MAX_OUTPUT_TOKENS`（預設 8192）限制單次輸出長度，`LLM_TIMEOUT`（預設 600 秒）限制單次請求時間，擋住模型無限重複輸出（失敗 5）。

已知缺口：回頭看的次數用完後，模型會直接交出最後一版，不再檢查（見 `failure-cases.md`）。

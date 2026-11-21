# Minecraft Texture Generation Agent

用對話描述想要的方塊或物品，Agent 會寫 Pillow / numpy 程式碼畫出 16×16 的原版風格材質，存成 PNG。

作業 2：smolagents CodeAgent（ReAct：Thought → 程式碼 / Tool Call → Observation）+ 5 個 Tool + 自訂系統提示詞與 skill + 對話式 Web UI。

作業 2 交件文件在 `documents/`：[Tool 定義](documents/tools.md)、[失敗情境](documents/failure-cases.md)、[執行追蹤](documents/execution-trace.md)、[設計說明（架構、技術選用、錯誤處理）](documents/design-notes.md)、[提示詞設計](documents/prompt-design.md)、[測試資料與結果](documents/test-results.md)（原始軌跡在 `documents/traces/`）。

## 系統需求

- Podman
- 一台 OpenAI 相容的 LLM server（例如 Ollama 的 `/v1` 端點）

## 安裝與設定

```bash
cp .env.example .env
# 編輯 .env，填入 LLM_API_BASE 與 LLM_MODEL
podman build -t mc-texture-agent -f Containerfile .
```

## 執行

```bash
mkdir -p output
podman run --rm -p 7860:7860 --env-file .env -v ./output:/app/output:Z mc-texture-agent
```

瀏覽器開啟 <http://localhost:7860>，輸入例如「紅寶石礦石」。生成的材質會存在 `output/`。

## 匯出映像檔

```bash
podman save -o mc-texture-agent.tar mc-texture-agent
# 另一台機器載入：podman load -i mc-texture-agent.tar
```

## 環境變數

| 變數 | 說明 | 預設 |
| --- | --- | --- |
| `LLM_API_BASE` | LLM server 位址，結尾 `/v1` | 必填 |
| `LLM_MODEL` | 模型名稱 | 必填 |
| `LLM_API_KEY` | API key | `not-needed` |
| `MAX_STEPS` | Agent 最多步數（重試上限） | `16` |
| `REVIEW_ROUNDS` | 畫完後最多回頭看幾次，`0` 關閉 | `2` |
| `OUTPUT_DIR` | PNG 輸出資料夾 | 容器內 `/app/output` |
| `PORT` | Web UI 連接埠 | `7860` |
| `REFERENCE_DIR` | 參考材質來源資料夾（jar / zip / 解壓後的資源包） | 容器內 `/app/reference` |
| `DATA_DIR` | 主題記憶存放處（`themes/` 底下的 JSON） | 容器內 `/app/data` |
| `INDEX_DIR` | 參考材質的 Chroma 索引資料夾 | 容器內 `/app/index` |
| `CHAT_HEIGHT` | 對話區高度（CSS 長度，例如 `75vh`、`600px`） | `75vh` |

## 運作流程

1. 使用者在對話框輸入描述。
2. CodeAgent 請 LLM 寫出繪圖程式碼（numpy 陣列或 PIL.ImageDraw）。
3. 程式碼由 smolagents 內建的 `LocalPythonExecutor` 執行，只允許 import numpy 與 PIL；`texture_kit` 的函式不必 import 就能直接呼叫。
4. 程式碼呼叫 `save_texture` Tool：檢查名稱、尺寸、陣列格式，通過就存成 16×16 PNG 並回傳放大 16 倍的預覽。
5. 任何錯誤（程式錯誤或格式不符）都會回到 Agent，由它讀錯誤訊息後修正，直到成功或達到 `MAX_STEPS`。

## Tools

| Tool | 目的 |
| --- | --- |
| `save_texture(image, name, kind)` | 驗證（格式 + 品質檢查）並存成 16×16 PNG，回傳放大預覽；同名再存成新版本 |
| `find_reference_textures(query, kind, top_k)` | 在使用者提供的參考材質中做向量檢索（RAG） |
| `get_theme(theme_name)` / `save_theme(...)` | 讀取 / 儲存主題（色票與風格備註）的持久記憶 |
| `export_resource_pack(mod_id)` | 把最新版本打包成 1.21.1 資源包 |

每個 Tool 的輸入、輸出與 Error Handling 見 [documents/tools.md](documents/tools.md)。

## 繪圖函式庫：`texture_kit`

Agent 生成的程式碼可以 `from texture_kit import ...`，用現成的函式畫圖，不必自己對 uint8 陣列做運算。

| 函式 | 用途 |
| --- | --- |
| `new_canvas(fill=None)` | 建立 16×16 RGBA 畫布，預設全透明 |
| `shade(color, amount)` | 顏色變亮或變暗，自動限制在 0-255 |
| `set_pixel` / `fill_rect` / `draw_line` | 單點、矩形、直線 |
| `from_ascii` / `stamp_ascii` | 用文字圖案畫整張或局部，`.` 代表透明或不動 |
| `speckle(img, density, strength, seed)` | 在不透明像素上撒深淺顆粒，模型不必自己用 `random` |
| `gem_cluster(img, x, y, size, color, seed)` | 畫一簇自動著色（暗邊、本體、亮面、高光）的礦物，模型不必數字元 |
| `mirror_x` / `outline` / `bevel` | 左右對稱、外框、光源從左上來的明暗邊 |

設計原因：第一次用 9B 模型實測時，模型自己寫 `uint8` 陣列減法，數值溢位環繞（`25 - 50` 變成 `231`），畫出青色、黃綠色的雜點。函式庫改用 Python int 運算並限制範圍，座標統一為 `(x, y)`，超出畫布會丟出說明清楚的錯誤。

測試：`pip install pytest && python -m pytest tests`

## 除錯

- **連不上 LLM**：確認容器內能連到 `LLM_API_BASE`；若 server 在本機，改用 `http://host.containers.internal:11434/v1`。
- **一直達到步數上限**：先看介面上每一步的錯誤訊息，必要時提高 `MAX_STEPS`。

## 參考材質（選用）

可以提供原版或模組的材質讓 Agent 畫圖前先查，學它的輪廓、明暗和色票。材質有版權，所以一律由使用者自己提供，不放進 repo（`reference/`、`index/` 已在 `.gitignore`）。

兩種提供方式：

1. **掛載資料夾**：把 `.jar`、`.zip` 或解壓後含 `assets/` 的資料夾放進 `reference/`，啟動時自動掃描：
   ```bash
   mkdir -p output reference index data
   podman run --rm -p 7860:7860 --env-file .env \
     -v ./output:/app/output:Z -v ./reference:/app/reference:Z -v ./index:/app/index:Z -v ./data:/app/data:Z mc-texture-agent
   ```
2. **對話中上傳**：在輸入框附加 `.jar` / `.zip`（只傳檔案、不輸入文字時不會啟動 Agent），會存到 `reference/uploads/` 並立即建立索引。

索引範圍：`assets/<namespace>/textures/block(s)|item(s)/` 底下的 PNG，只用檔名做 embedding（Chroma 預設的 all-MiniLM-L6-v2）。每次啟動與每次上傳都是增量同步：沒變的檔案不重做，來源被刪掉會一併移除。Agent 透過 `find_reference_textures(query, kind, top_k)` 取得 16×16 的 ASCII 圖與色票。

## 修改、品質檢查、主題與匯出

- **存新版本**：同一個名稱再存一次不會覆蓋，會變成 `ruby_ore.png`、`ruby_ore_v2.png`、`ruby_ore_v3.png`…。對話中說「再亮一點」，Agent 會重畫並存成新版本，預覽圖下方會標示檔名。
- **品質檢查**（`save_texture` 內建，不通過就不存檔，原因回給 Agent 重畫）：幾乎全透明、顏色超過 48 種、顏色散亂像雜訊。指標改寫自 skill 的 `mc_style_audit.py`。
- **主題記憶**：`get_theme` / `save_theme` 把色票與風格備註存成 JSON（`DATA_DIR/themes/`），之後的材質可沿用。
- **匯出資源包**：說「匯出」，Agent 呼叫 `export_resource_pack(mod_id)`，把每個名稱的最新版本整理成 `assets/<mod_id>/textures/block|item/` 加上 models、blockstates 與 `pack.mcmeta`（pack_format 34，Minecraft 1.21.1），輸出 `output/<mod_id>_resourcepack.zip`。
- **畫完回頭看**：`save_texture` 成功後，Agent 會看到剛存的成品圖（需要支援圖片輸入的模型），對照你的需求檢查主題、輪廓、有沒有整片黑色或空白；明顯不對就重畫並存成新版本，最多 `REVIEW_ROUNDS` 次。存檔後如果它想在看圖之前就結束，會被擋下來要它先看。
- **`stamp_ascii` 會報錯**：每列長度不一致或圖案超出 16×16 時丟出錯誤，不再默默裁掉。

## 測試與失敗證據

- 單元測試：`python -m pytest tests`（含 Agent 流程的假模型測試）。
- 批次實測：`python -m texture_agent.eval_cases` 依 `documents/test-cases.json` 的 10 個案例跑真模型，結果寫入 `documents/eval-results.md`。
- 真模型實測：同一個需求「紅寶石礦石」，Tool 改版前 9 步、約 17 分鐘、5 步失敗；改版後 2 步、約 73 秒、零錯誤。細節見 [失敗情境](documents/failure-cases.md) 與 [執行追蹤](documents/execution-trace.md)。

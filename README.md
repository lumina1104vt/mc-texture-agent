# Minecraft Texture Generation Agent

用對話描述想要的方塊或物品，Agent 會寫 Pillow / numpy 程式碼畫出 16×16 的原版風格材質，存成 PNG。

目前為作業 2 第一版：CodeAgent + 一個存檔 Tool + 程式錯誤修正迴圈 + 對話式 Web UI。

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
| `MAX_STEPS` | Agent 最多步數（重試上限） | `10` |
| `OUTPUT_DIR` | PNG 輸出資料夾 | 容器內 `/app/output` |
| `PORT` | Web UI 連接埠 | `7860` |
| `REFERENCE_DIR` | 參考材質來源資料夾（jar / zip / 解壓後的資源包） | 容器內 `/app/reference` |
| `INDEX_DIR` | 參考材質的 Chroma 索引資料夾 | 容器內 `/app/index` |
| `CHAT_HEIGHT` | 對話區高度（CSS 長度，例如 `75vh`、`600px`） | `75vh` |

## 運作流程

1. 使用者在對話框輸入描述。
2. CodeAgent 請 LLM 寫出繪圖程式碼（numpy 陣列或 PIL.ImageDraw）。
3. 程式碼由 smolagents 內建的 `LocalPythonExecutor` 執行，只允許 import numpy 與 PIL。
4. 程式碼呼叫 `save_texture` Tool：檢查名稱、尺寸、陣列格式，通過就存成 16×16 PNG 並回傳放大 16 倍的預覽。
5. 任何錯誤（程式錯誤或格式不符）都會回到 Agent，由它讀錯誤訊息後修正，直到成功或達到 `MAX_STEPS`。

## Tool：`save_texture`

| 項目 | 內容 |
| --- | --- |
| 目的 | 驗證並儲存畫好的材質 |
| 輸入 | `image`：PIL.Image 或 shape (16,16,4)/(16,16,3) 的 uint8 陣列；`name`：小寫英數與底線 |
| 輸出 | 256×256 的放大預覽圖；實際檔案為 `OUTPUT_DIR/<name>.png` |
| Error Handling | 名稱不合法、尺寸不是 16×16、陣列形狀或數值範圍錯誤、型別不支援時，丟出說明原因的錯誤，讓 Agent 修正 |

## 繪圖函式庫：`texture_kit`

Agent 生成的程式碼可以 `from texture_kit import ...`，用現成的函式畫圖，不必自己對 uint8 陣列做運算。

| 函式 | 用途 |
| --- | --- |
| `new_canvas(fill=None)` | 建立 16×16 RGBA 畫布，預設全透明 |
| `shade(color, amount)` | 顏色變亮或變暗，自動限制在 0-255 |
| `set_pixel` / `fill_rect` / `draw_line` | 單點、矩形、直線 |
| `from_ascii` / `stamp_ascii` | 用文字圖案畫整張或局部，`.` 代表透明或不動 |
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
   mkdir -p output reference index
   podman run --rm -p 7860:7860 --env-file .env \
     -v ./output:/app/output:Z -v ./reference:/app/reference:Z -v ./index:/app/index:Z mc-texture-agent
   ```
2. **對話中上傳**：在輸入框附加 `.jar` / `.zip`（只傳檔案、不輸入文字時不會啟動 Agent），會存到 `reference/uploads/` 並立即建立索引。

索引範圍：`assets/<namespace>/textures/block(s)|item(s)/` 底下的 PNG，只用檔名做 embedding（Chroma 預設的 all-MiniLM-L6-v2）。每次啟動與每次上傳都是增量同步：沒變的檔案不重做，來源被刪掉會一併移除。Agent 透過 `find_reference_textures(query, kind, top_k)` 取得 16×16 的 ASCII 圖與色票。

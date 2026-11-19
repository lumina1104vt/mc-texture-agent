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

## 除錯

- **連不上 LLM**：確認容器內能連到 `LLM_API_BASE`；若 server 在本機，改用 `http://host.containers.internal:11434/v1`。
- **一直達到步數上限**：先看介面上每一步的錯誤訊息，必要時提高 `MAX_STEPS`。

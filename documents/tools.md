# Tool 定義

Agent 是 smolagents 的 `CodeAgent`：LLM 每一步寫出 Python 程式碼，程式碼裡可以呼叫下列 Tool，也可以直接使用繪圖函式庫 `texture_kit`（不必 import）。

## 1. `save_texture`

| 項目 | 內容 |
| --- | --- |
| 目的 | 驗證並儲存畫好的 16×16 材質，回傳放大預覽供 Agent 與使用者查看 |
| 輸入 | `image`：PIL.Image 或 shape (16,16,4) 的 uint8 陣列；`name`：小寫英數與底線；`kind`：`block` 或 `item`（可省略，預設 `block`） |
| 輸出 | 256×276 的預覽圖（下方標示存檔名）；檔案為 `OUTPUT_DIR/<name>.png`，同名再存會變成 `<name>_v2.png`、`_v3.png`…，另寫 `manifest.json` 記錄 kind |
| Error Handling | 名稱不合法、`kind` 不合法、尺寸不是 16×16、陣列形狀或數值範圍錯誤、型別不支援，一律丟出說明原因的 `ValueError` / `TypeError`；品質檢查不通過（可見像素少於 8、顏色超過 48 種、前 5 色涵蓋率低於 70%）時丟出 `Quality check failed, nothing was saved…`，不存檔。錯誤會原樣回到 Agent 的下一步，由它修正 |

## 2. `find_reference_textures`

| 項目 | 內容 |
| --- | --- |
| 目的 | 在使用者自己提供的參考材質（jar / zip / 資源包）中，用檔名做向量檢索（RAG），找出最像的幾張，學習輪廓、明暗與色票 |
| 輸入 | `query`：英文關鍵字；`kind`：`block` / `item` / `any`；`top_k`：1–5 |
| 輸出 | 字串：每個結果的名稱、16×16 ASCII 圖與色票 |
| Error Handling | `kind` 不合法丟出 `ValueError`；索引是空的或沒有符合的結果時回傳說明字串（請改看風格指南畫），不丟錯誤 |

## 3. `get_theme`

| 項目 | 內容 |
| --- | --- |
| 目的 | 讀取已儲存的主題（色票與風格備註），讓新材質與舊的一致 |
| 輸入 | `theme_name`：主題名稱，省略則列出所有主題 |
| 輸出 | 字串：主題內容，或主題清單 |
| Error Handling | 找不到主題時回傳 `No saved theme named …`，不丟錯誤 |

## 4. `save_theme`

| 項目 | 內容 |
| --- | --- |
| 目的 | 建立或更新主題，存成 `DATA_DIR/themes/` 下的 JSON（持久記憶） |
| 輸入 | `theme_name`（必填）；`description`、`palette`（逗號分隔的 `#rrggbb`）、`style_notes`（皆可省略，省略的欄位保留舊值） |
| 輸出 | 字串：`Saved.` 加上主題內容 |
| Error Handling | 色票不是 `#rrggbb` 格式、或主題名稱沒有字母或數字時，丟出說明原因的 `ValueError` |

## 5. `export_resource_pack`

| 項目 | 內容 |
| --- | --- |
| 目的 | 把每個名稱的最新版本打包成 Minecraft 1.21.1 資源包（`pack_format` 34），含 models、blockstates、`pack.mcmeta` |
| 輸入 | `mod_id`：小寫英數與底線，省略則為 `mymod` |
| 輸出 | 字串：匯出的 zip 檔名與材質清單；檔案在 `output/<mod_id>_resourcepack.zip` |
| Error Handling | `mod_id` 不合法或沒有任何材質可匯出時丟出說明原因的錯誤，回到 Agent |

## 繪圖函式庫 `texture_kit`（程式碼內直接呼叫，不需 import）

| 函式 | 用途 |
| --- | --- |
| `new_canvas(fill)` | 建立 16×16 RGBA 畫布，預設全透明 |
| `shade(color, amount)` | 變亮 / 變暗，Python int 運算並限制 0–255（避免 uint8 溢位） |
| `set_pixel` / `fill_rect` / `draw_line` | 單點、矩形、直線；座標一律 `(x, y)`，超出畫布丟出說明清楚的錯誤 |
| `from_ascii` / `stamp_ascii` | 用文字圖案畫整張或局部；列長不一致或超出畫布時報錯並附上補 `.` 的建議寫法 |
| `speckle(img, density, strength, seed)` | 在不透明像素上撒深淺顆粒（取代模型自己用 `random`） |
| `gem_cluster(img, x, y, size, color, seed)` | 畫一簇相連的礦物，自動做出暗邊、本體、亮面與高光（取代手寫 ASCII） |
| `mirror_x` / `outline` / `bevel` | 左右對稱、外框、光源從左上來的明暗邊 |

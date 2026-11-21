# Agent 執行追蹤（Execution Trace）

需求：「紅寶石礦石」。環境：Podman 容器內執行，LLM 為 Ollama 的 `dsv4p-qwen3.5:9b`。完整原始輸出見 `documents/traces/`。

## 流程（ReAct：Thought → Code/Tool Call → Observation）

```
使用者輸入：紅寶石礦石
   ↓
Agent 決策（Step 1，51.7 秒）
  Thought：礦石 = 灰色石底 + 紅寶石簇，先鋪底、撒顆粒，再畫簇，最後加立體邊
   ↓
Tool Call（在同一段程式碼裡）
  new_canvas(fill=stone_gray)
  speckle(img, density=0.35, strength=12, seed=1)
  gem_cluster(img, x, y, size, ruby_red_base, seed=1…6)   # 6 簇
  bevel(img, light=18, dark=14)
  save_texture(image=img, name="ruby_ore", kind="block")
   ↓
執行結果觀察（Observation）
  Out: <PIL.Image.Image image mode=RGBA size=256x276>   # 通過格式與品質檢查，已存檔並回傳預覽
   ↓
Agent 決策（Step 2，20.9 秒）
  Thought：灰色石底、大小不一的紅寶石簇、立體邊，符合礦石要求，結束
   ↓
執行最後結果
  final_answer(preview)  →  使用者在介面看到成品
```

統計：2 步、72.6 秒、輸入 9,666 token、輸出 780 token，零錯誤（`traces/run2-after-tool-redesign.txt`）。

## 對照：Tool 改版前的同一需求（`traces/run1-before-tool-redesign.txt`）

| 步驟 | 發生什麼 | 結果 |
| --- | --- | --- |
| 1 | 用了沒匯入的 `random` | 失敗：`random` is not defined |
| 2 | 去掉 `random` 重寫 | 成功存檔（v 版本遞增） |
| 3 | 自己評審後覺得太簡單，重畫，圖案用了調色盤沒有的 `D` | 失敗：Character 'D' not in the palette |
| 4 | 修成 A/B/C，重畫 | 成功存檔 |
| 5 | 想再加雜紋，又用了 `random` | 失敗：`random` is not defined |
| 6 | 空的程式碼 | 白費 135 秒 |
| 7 | 改掉 `random` 但有一簇每列字元數不一 | 失敗：All rows must have the same length（錯誤訊息附補 `.` 的建議） |
| 8 | 照建議補齊 | 成功存檔 |
| 9 | 「已達審查次數上限」，直接 `final_answer` | 結束 |

統計：9 步、1,040 秒、累計輸入 87,177 token、輸出 6,799 token，5 步失敗。

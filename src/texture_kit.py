"""Minecraft 16x16 材質的繪圖函式庫，給 Agent 生成的程式碼 import 使用。

設計重點：把模型容易寫錯的地方封裝起來。
- 座標一律是 (x, y)：x 是欄（0 = 最左），y 是列（0 = 最上），不會搞混 row / col。
- 顏色運算一律用 Python int 計算並限制在 0-255，避免 uint8 溢位環繞
  （例如 80 - 100 變成 236 而不是 0）。
- 超出畫布的座標會丟出說明清楚的錯誤，不會悄悄環繞到另一邊。
"""

from __future__ import annotations

import numpy as np

SIZE = 16


def _rgba(color) -> tuple[int, int, int, int]:
    """接受 (r, g, b)、(r, g, b, a) 或 '#rrggbb' / '#rrggbbaa'，回傳 (r, g, b, a)。"""
    if isinstance(color, str):
        h = color.lstrip("#")
        if len(h) not in (6, 8):
            raise ValueError(f"Bad color {color!r}: use '#rrggbb' or '#rrggbbaa'.")
        try:
            vals = [int(h[i : i + 2], 16) for i in range(0, len(h), 2)]
        except ValueError:
            raise ValueError(f"Bad color {color!r}: not a hex color.") from None
        color = vals
    values = [int(v) for v in color]
    if len(values) == 3:
        values.append(255)
    if len(values) != 4:
        raise ValueError(f"Color must have 3 (RGB) or 4 (RGBA) values, got {len(values)}.")
    if any(v < 0 or v > 255 for v in values):
        raise ValueError(f"Color values must be within 0-255, got {tuple(values)}.")
    return tuple(values)  # type: ignore[return-value]


def _check_xy(x: int, y: int) -> None:
    if not (0 <= x < SIZE and 0 <= y < SIZE):
        raise ValueError(f"Pixel (x={x}, y={y}) is outside the 16x16 canvas (valid range 0-15).")


def new_canvas(fill=None) -> np.ndarray:
    """建立 (16, 16, 4) 的 uint8 RGBA 畫布。fill=None 表示全透明。"""
    img = np.zeros((SIZE, SIZE, 4), dtype=np.uint8)
    if fill is not None:
        img[:, :] = _rgba(fill)
    return img


def shade(color, amount: int) -> tuple[int, int, int, int]:
    """把顏色變亮（amount > 0）或變暗（amount < 0），自動限制在 0-255，alpha 不變。"""
    r, g, b, a = _rgba(color)
    amount = int(amount)
    return tuple(max(0, min(255, c + amount)) for c in (r, g, b)) + (a,)  # type: ignore[return-value]


def set_pixel(img: np.ndarray, x: int, y: int, color) -> np.ndarray:
    """設定單一像素。座標超出 0-15 會丟出錯誤。"""
    _check_xy(x, y)
    img[y, x] = _rgba(color)
    return img


def fill_rect(img: np.ndarray, x: int, y: int, w: int, h: int, color) -> np.ndarray:
    """填滿矩形（左上角 x, y，寬 w，高 h）。超出畫布的部分會被裁掉。"""
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(SIZE, x + w), min(SIZE, y + h)
    if x0 < x1 and y0 < y1:
        img[y0:y1, x0:x1] = _rgba(color)
    return img


def draw_line(img: np.ndarray, x0: int, y0: int, x1: int, y1: int, color) -> np.ndarray:
    """畫一條 1 像素寬的線（含兩端點）。端點必須在畫布內。"""
    _check_xy(x0, y0)
    _check_xy(x1, y1)
    rgba = _rgba(color)
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        img[y0, x0] = rgba
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
    return img


def stamp_ascii(img: np.ndarray, rows: list[str], palette: dict, x: int = 0, y: int = 0) -> np.ndarray:
    """把用文字畫的圖案蓋到畫布上，左上角放在 (x, y)。

    rows 是字串列表，每個字元代表一個像素，palette 把字元對應到顏色。
    '.' 表示不動（保留原本的像素）；其他字元必須在 palette 裡。
    每一列長度必須一致，而且整個圖案必須完整放得進 16×16 畫布，否則丟出錯誤（不會默默裁掉）。
    """
    if not rows:
        raise ValueError("rows is empty: give at least one string.")
    widths = {len(r) for r in rows}
    if len(widths) != 1:
        detail = ", ".join(f"row {j} has {len(r)}" for j, r in enumerate(rows))
        raise ValueError(f"All rows must have the same length, got different lengths ({detail}).")
    width, height = widths.pop(), len(rows)
    if x < 0 or y < 0 or x + width > SIZE or y + height > SIZE:
        raise ValueError(
            f"The {width}x{height} pattern placed at x={x}, y={y} does not fit in the {SIZE}x{SIZE} canvas "
            f"(it would cover x {x}..{x + width - 1}, y {y}..{y + height - 1}). Fix the rows or the position."
        )
    colors = {ch: _rgba(c) for ch, c in palette.items()}
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            if ch not in colors:
                raise ValueError(f"Character {ch!r} in row {j} is not in the palette (palette has {sorted(colors)}).")
            img[y + j, x + i] = colors[ch]
    return img


def from_ascii(rows: list[str], palette: dict) -> np.ndarray:
    """用 16 列、每列 16 個字元的文字畫整張材質。'.' 是透明，其他字元查 palette。"""
    if len(rows) != SIZE:
        raise ValueError(f"Need exactly {SIZE} rows, got {len(rows)}.")
    for j, row in enumerate(rows):
        if len(row) != SIZE:
            raise ValueError(f"Row {j} must have {SIZE} characters, got {len(row)}.")
    return stamp_ascii(new_canvas(), rows, palette)


def mirror_x(img: np.ndarray) -> np.ndarray:
    """把左半邊鏡射到右半邊，讓材質左右對稱。"""
    img[:, SIZE // 2 :] = img[:, : SIZE // 2][:, ::-1]
    return img


def outline(img: np.ndarray, color) -> np.ndarray:
    """在不透明像素外圍（上下左右相鄰的透明像素）畫一圈輪廓。"""
    rgba = _rgba(color)
    solid = img[:, :, 3] > 0
    grown = np.zeros_like(solid)
    grown[1:, :] |= solid[:-1, :]
    grown[:-1, :] |= solid[1:, :]
    grown[:, 1:] |= solid[:, :-1]
    grown[:, :-1] |= solid[:, 1:]
    img[grown & ~solid] = rgba
    return img


def bevel(img: np.ndarray, light: int = 25, dark: int = 25) -> np.ndarray:
    """光源從左上來：最上列與最左欄變亮，最下列與最右欄變暗。只處理不透明的像素。"""
    work = img.astype(np.int32)
    solid = work[:, :, 3] > 0

    def adjust(mask: np.ndarray, amount: int) -> None:
        m = mask & solid
        work[m, :3] = np.clip(work[m, :3] + amount, 0, 255)

    dark_mask = np.zeros_like(solid)
    dark_mask[-1, :] = True
    dark_mask[:, -1] = True
    light_mask = np.zeros_like(solid)
    light_mask[0, :] = True
    light_mask[:, 0] = True
    adjust(dark_mask, -abs(int(dark)))
    adjust(light_mask & ~dark_mask, abs(int(light)))
    img[:] = work.astype(np.uint8)
    return img

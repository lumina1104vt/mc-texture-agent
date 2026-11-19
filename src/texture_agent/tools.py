"""Agent 可呼叫的 Tool。

save_texture：檢查模型畫好的材質是否符合格式，符合就存成 16×16 PNG，
並回傳放大後的預覽圖給介面顯示；不符合就丟出錯誤訊息，讓 Agent 讀到後自行修正。
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from PIL import Image
from smolagents import Tool

TEXTURE_SIZE = 16
PREVIEW_SCALE = 16  # 16×16 → 256×256，方便在對話中看清楚每個像素
_NAME_PATTERN = re.compile(r"^[a-z0-9_]+$")


class SaveTextureTool(Tool):
    name = "save_texture"
    description = (
        "Validate a finished 16x16 Minecraft texture and save it as a PNG file. "
        "Returns an enlarged preview image. Raises an error that explains what is wrong "
        "if the texture does not meet the required format, so you can fix it and call again."
    )
    inputs = {
        "image": {
            "type": "any",
            "description": (
                "The texture: either a PIL.Image or a numpy uint8 array of shape (16, 16, 4) in RGBA order."
            ),
        },
        "name": {
            "type": "string",
            "description": "File name without extension, lowercase letters, digits and underscores only, e.g. 'ruby_ore'.",
        },
    }
    output_type = "image"

    def __init__(self, output_dir: str | Path):
        super().__init__()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def forward(self, image, name: str):
        if not isinstance(name, str) or not _NAME_PATTERN.match(name):
            raise ValueError(
                f"Invalid name {name!r}: use only lowercase letters, digits and underscores, e.g. 'ruby_ore'."
            )

        img = self._to_rgba_image(image)
        if img.size != (TEXTURE_SIZE, TEXTURE_SIZE):
            raise ValueError(
                f"Texture must be {TEXTURE_SIZE}x{TEXTURE_SIZE} pixels, got {img.size[0]}x{img.size[1]}."
            )

        path = self.output_dir / f"{name}.png"
        img.save(path, format="PNG")

        return img.resize(
            (TEXTURE_SIZE * PREVIEW_SCALE, TEXTURE_SIZE * PREVIEW_SCALE), Image.Resampling.NEAREST
        )

    @staticmethod
    def _to_rgba_image(image) -> Image.Image:
        if isinstance(image, Image.Image):
            return image.convert("RGBA")

        if isinstance(image, np.ndarray):
            arr = image
            if arr.ndim != 3 or arr.shape[2] not in (3, 4):
                raise ValueError(
                    f"Array must have shape (16, 16, 4) RGBA or (16, 16, 3) RGB, got {arr.shape}."
                )
            if arr.dtype != np.uint8:
                if arr.min() < 0 or arr.max() > 255:
                    raise ValueError("Array values must be within 0-255.")
                arr = arr.astype(np.uint8)
            return Image.fromarray(np.ascontiguousarray(arr)).convert("RGBA")

        raise TypeError(
            f"Unsupported image type {type(image).__name__}: pass a PIL.Image or a numpy uint8 array."
        )

"""Agent 可呼叫的 Tool：save_texture。

save_texture：先做格式與品質檢查，通過才存成 16×16 PNG，並回傳放大後的預覽圖；
不符合就丟出錯誤訊息，讓 Agent 讀到後自行修正（失敗的嘗試不會留下檔案）。
同名再存一次不會覆蓋，而是存成新版本：ruby_ore.png、ruby_ore_v2.png、ruby_ore_v3.png…
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from smolagents import Tool

from .checks import hard_failures

TEXTURE_SIZE = 16
PREVIEW_SCALE = 16  # 16×16 → 256×256，方便在對話中看清楚每個像素
CAPTION_HEIGHT = 20
KINDS = ("block", "item")
MANIFEST = "manifest.json"
_NAME_PATTERN = re.compile(r"^[a-z0-9_]+$")
_VERSION_SUFFIX = re.compile(r"_v(\d+)$")


def split_version(name: str) -> str:
    """'ruby_ore_v3' → 'ruby_ore'：模型有時會自己加版本後綴，統一還原成基本名稱。"""
    return _VERSION_SUFFIX.sub("", name) or name


def versions_of(output_dir: Path, base: str) -> dict[int, Path]:
    """列出某個材質已存在的版本：{1: ruby_ore.png, 2: ruby_ore_v2.png, ...}。"""
    found: dict[int, Path] = {}
    first = output_dir / f"{base}.png"
    if first.exists():
        found[1] = first
    for p in output_dir.glob(f"{base}_v*.png"):
        m = _VERSION_SUFFIX.search(p.stem)
        if m and p.stem[: m.start()] == base and int(m.group(1)) >= 2:
            found[int(m.group(1))] = p
    return found


def version_path(output_dir: Path, base: str, version: int) -> Path:
    return output_dir / (f"{base}.png" if version == 1 else f"{base}_v{version}.png")


def load_manifest(output_dir: Path) -> dict[str, dict[str, str]]:
    path = output_dir / MANIFEST
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _caption(preview: Image.Image, text: str) -> Image.Image:
    """在預覽圖下方加一條檔名，使用者一眼就知道這張存成哪個檔案。"""
    canvas = Image.new("RGBA", (preview.width, preview.height + CAPTION_HEIGHT), (32, 32, 32, 255))
    canvas.paste(preview, (0, 0))
    try:
        font = ImageFont.load_default(size=13)
    except TypeError:  # 很舊的 Pillow 不支援 size
        font = ImageFont.load_default()
    ImageDraw.Draw(canvas).text((6, preview.height + 3), text, fill=(235, 235, 235, 255), font=font)
    return canvas


class SaveTextureTool(Tool):
    name = "save_texture"
    description = (
        "Validate a finished 16x16 Minecraft texture and save it as a PNG file. "
        "Returns an enlarged preview image labelled with the saved file name. "
        "Saving the same name again keeps the old file and writes a new version (name_v2.png, name_v3.png...), "
        "so call it with the same name when the user asks to change an existing texture. "
        "Raises an error that explains what is wrong if the texture does not meet the required format "
        "or quality checks (nothing is saved in that case), so you can fix it and call again."
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
        "kind": {
            "type": "string",
            "description": "'block' or 'item'. Used when exporting a resource pack. Defaults to 'block'.",
            "nullable": True,
        },
    }
    output_type = "image"

    def __init__(self, output_dir: str | Path):
        super().__init__()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def forward(self, image, name: str, kind: str | None = None):
        if not isinstance(name, str) or not _NAME_PATTERN.match(name):
            raise ValueError(
                f"Invalid name {name!r}: use only lowercase letters, digits and underscores, e.g. 'ruby_ore'."
            )
        kind = kind or "block"
        if kind not in KINDS:
            raise ValueError(f"Invalid kind {kind!r}: use 'block' or 'item'.")

        img = self._to_rgba_image(image)
        if img.size != (TEXTURE_SIZE, TEXTURE_SIZE):
            raise ValueError(
                f"Texture must be {TEXTURE_SIZE}x{TEXTURE_SIZE} pixels, got {img.size[0]}x{img.size[1]}."
            )
        problems = hard_failures(img)
        if problems:
            raise ValueError("Quality check failed, nothing was saved. Fix these and try again: " + " ".join(problems))

        base = split_version(name)
        existing = versions_of(self.output_dir, base)
        version = max(existing, default=0) + 1
        path = version_path(self.output_dir, base, version)
        img.save(path, format="PNG")
        self._record(base, kind)

        preview = img.resize(
            (TEXTURE_SIZE * PREVIEW_SCALE, TEXTURE_SIZE * PREVIEW_SCALE), Image.Resampling.NEAREST
        )
        return _caption(preview, path.name)

    def _record(self, base: str, kind: str) -> None:
        manifest = load_manifest(self.output_dir)
        manifest[base] = {"kind": kind}
        (self.output_dir / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

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

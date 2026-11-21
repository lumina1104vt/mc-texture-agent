"""跨任務的主題記憶：把色票與風格備註存成 JSON，之後的材質可以沿用，整組看起來一致。"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", name.strip().lower()).strip("_")


def parse_palette(text: str) -> list[str]:
    """'#413F54, #cbccd4' → ['#413f54', '#cbccd4']；格式不對就丟出說明原因的錯誤。"""
    colors = [c.strip() for c in re.split(r"[,\s]+", text) if c.strip()]
    bad = [c for c in colors if not _HEX.match(c)]
    if bad:
        raise ValueError(f"Invalid colors {bad}: use '#rrggbb' hex colors separated by commas.")
    return [c.lower() for c in colors]


@dataclass
class Theme:
    name: str
    description: str = ""
    palette: list[str] = field(default_factory=list)
    style_notes: str = ""

    def format(self) -> str:
        return "\n".join(
            [
                f"Theme: {self.name}",
                f"Description: {self.description or 'N/A'}",
                f"Palette: {', '.join(self.palette) if self.palette else 'not set'}",
                f"Style notes: {self.style_notes or 'N/A'}",
            ]
        )


class ThemeStore:
    def __init__(self, themes_dir: str | Path):
        self.dir = Path(themes_dir)

    def _path(self, name: str) -> Path:
        slug = slugify(name)
        if not slug:
            raise ValueError("Theme name must contain letters or digits.")
        return self.dir / f"{slug}.json"

    def names(self) -> list[str]:
        if not self.dir.exists():
            return []
        out = []
        for p in sorted(self.dir.glob("*.json")):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")).get("name", p.stem))
            except (OSError, ValueError):
                out.append(p.stem)
        return out

    def get(self, name: str) -> Theme | None:
        path = self._path(name)
        if not path.exists():
            return None
        try:
            return Theme(**json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return None

    def upsert(self, name: str, description: str | None = None, palette: list[str] | None = None, style_notes: str | None = None) -> Theme:
        theme = self.get(name) or Theme(name=name.strip())
        if description:
            theme.description = description
        if palette:
            theme.palette = palette
        if style_notes:
            theme.style_notes = style_notes
        path = self._path(name)
        self.dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(theme), ensure_ascii=False, indent=2), encoding="utf-8")
        return theme

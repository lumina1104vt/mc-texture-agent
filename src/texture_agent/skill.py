"""載入 skill：把 SKILL.md（去掉 frontmatter）與材質規格文件合併成一段文字，附加到 Agent 的指示中。"""

from __future__ import annotations

from pathlib import Path

# 專案根目錄：本機為 repo 根目錄，容器內為 /app
ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "minecraft-asset-design"

# 只載入和 16x16 材質有關的參考文件；3D 模型與 GUI 屬於擴充需求，這一版不載入
REFERENCES = ["references/texture-and-histogram-spec.md"]


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip("\n")
    return text


def load_skill_text(skill_dir: Path = SKILL_DIR) -> str:
    parts = [_strip_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))]
    for ref in REFERENCES:
        parts.append((skill_dir / ref).read_text(encoding="utf-8"))
    return "\n\n".join(parts)

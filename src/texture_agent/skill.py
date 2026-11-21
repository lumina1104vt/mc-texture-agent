"""載入 skill：把每個 skill 的 SKILL.md（去掉 frontmatter）與指定的參考文件合併，附加到 Agent 的指示中。"""

from __future__ import annotations

from pathlib import Path

# 專案根目錄：本機為 repo 根目錄，容器內為 /app
ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"

# (skill 資料夾名稱, 要連同 SKILL.md 一起載入的參考文件)
# 合併自 minecraft-asset-design 與 pixel-art-style（原兩份已刪除）
SKILLS: list[tuple[str, list[str]]] = [
    ("minecraft-texture-craft", []),
]


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip("\n")
    return text


def load_skill_text(skills_dir: Path = SKILLS_DIR) -> str:
    sections = []
    for name, refs in SKILLS:
        folder = skills_dir / name
        parts = [_strip_frontmatter((folder / "SKILL.md").read_text(encoding="utf-8"))]
        parts += [(folder / ref).read_text(encoding="utf-8") for ref in refs]
        sections.append(f"## Skill: {name}\n\n" + "\n\n".join(parts))
    return "\n\n---\n\n".join(sections)

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from texture_agent.skill import NOTE, SKILLS, SKILLS_DIR, load_skill_text  # noqa: E402


def test_every_configured_file_exists():
    for name, refs in SKILLS:
        assert (SKILLS_DIR / name / "SKILL.md").is_file()
        for ref in refs:
            assert (SKILLS_DIR / name / ref).is_file(), f"{name}/{ref}"


def test_text_contains_all_skills_and_no_frontmatter():
    text = load_skill_text()
    assert text.startswith(NOTE)
    assert "## Skill: minecraft-asset-design" in text
    assert "## Skill: pixel-art-style" in text
    assert "Midtone Bridge" in text           # minecraft-asset-design 的參考文件
    assert "色階怎麼走" in text                 # pixel-art-style/ramps.md
    assert "一般物品怎麼畫得" in text            # pixel-art-style/general-items.md
    assert "name: pixel-art-style" not in text  # frontmatter 已去掉
    assert "name: minecraft-asset-design" not in text

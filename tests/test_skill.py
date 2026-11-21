import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from texture_agent.skill import SKILLS, SKILLS_DIR, load_skill_text  # noqa: E402


def test_every_configured_file_exists():
    for name, refs in SKILLS:
        assert (SKILLS_DIR / name / "SKILL.md").is_file()
        for ref in refs:
            assert (SKILLS_DIR / name / ref).is_file(), f"{name}/{ref}"


def test_text_has_no_frontmatter_and_covers_the_key_rules():
    text = load_skill_text()
    assert "## Skill: minecraft-texture-craft" in text
    assert "name: minecraft-texture-craft" not in text      # frontmatter 已去掉
    assert "礦石與嵌入礦物的方塊" in text and "整張鋪滿" in text   # 礦石要先鋪底
    assert "一般物品" in text and "要避免的" in text


def test_no_instructions_for_tools_the_agent_does_not_have():
    text = load_skill_text()
    for gone in ("unpack_refs", "svgpx", "sheet.py", "mc_style_audit", "profiles/", "遮名測試", "AE2", "家族"):
        assert gone not in text, gone


def test_numbered_lists_have_no_duplicates():
    import re
    items = re.findall(r"^(\d+)\. ", load_skill_text(), flags=re.M)
    assert items == [str(i) for i in range(1, 10)]

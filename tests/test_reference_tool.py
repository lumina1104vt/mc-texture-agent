import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_reference import FakeEmbedding, make_jar  # noqa: E402
from texture_agent.reference import ReferenceIndex  # noqa: E402
from texture_agent.reference_tool import FindReferenceTexturesTool  # noqa: E402


@pytest.fixture
def tool(tmp_path):
    ref = tmp_path / "r"
    ref.mkdir()
    make_jar(ref / "a.jar", ["block/iron_ore.png", "item/iron_sword.png"])
    idx = ReferenceIndex(ref, tmp_path / "i", embedding_function=FakeEmbedding())
    idx.sync()
    return FindReferenceTexturesTool(idx)


def test_returns_grid_text(tool):
    out = tool("iron ore", kind="block", top_k=1)
    assert "iron_ore" in out and "palette" in out and "rows" in out


def test_any_kind_and_clamped_top_k(tool):
    assert "iron_sword" in tool("iron sword", kind="any", top_k=99)


def test_bad_kind_raises(tool):
    with pytest.raises(Exception):
        tool("iron", kind="entity")


def test_empty_index_message(tmp_path):
    idx = ReferenceIndex(tmp_path / "r", tmp_path / "i", embedding_function=FakeEmbedding())
    idx.sync()
    assert "No reference textures" in FindReferenceTexturesTool(idx)("stone")

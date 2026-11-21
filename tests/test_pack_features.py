import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from texture_agent.checks import audit_image, hard_failures  # noqa: E402
from texture_agent.extra_tools import ExportPackTool, GetThemeTool, SaveThemeTool  # noqa: E402
from texture_agent.theme_memory import ThemeStore, parse_palette  # noqa: E402
from texture_agent.tools import SaveTextureTool, split_version, versions_of  # noqa: E402


def good(seed=0, base=(120, 120, 120)):
    """有深淺變化的石頭風格材質：幾個相近的灰階，成塊分布。"""
    rng = np.random.default_rng(seed)
    arr = np.zeros((16, 16, 4), dtype=np.uint8)
    shades = [base, tuple(c + 25 for c in base), tuple(c - 30 for c in base)]
    for y in range(16):
        for x in range(16):
            arr[y, x, :3] = shades[int(rng.integers(0, 3))]
            arr[y, x, 3] = 255
    return arr


def test_empty_texture_is_rejected_and_not_saved(tmp_path):
    tool = SaveTextureTool(tmp_path)
    with pytest.raises(ValueError, match="almost completely transparent"):
        tool(np.zeros((16, 16, 4), dtype=np.uint8), "ghost")
    assert not list(tmp_path.glob("*.png"))


def test_random_rainbow_noise_is_rejected(tmp_path):
    rng = np.random.default_rng(1)
    arr = rng.integers(0, 256, (16, 16, 4), dtype=np.uint8)
    arr[:, :, 3] = 255
    problems = hard_failures(Image.fromarray(arr))
    assert problems  # 顏色太多或太散
    with pytest.raises(ValueError, match="nothing was saved"):
        SaveTextureTool(tmp_path)(arr, "noise")


def test_plain_flat_and_vanilla_like_textures_pass():
    flat = np.full((16, 16, 4), 255, dtype=np.uint8)
    assert hard_failures(Image.fromarray(flat)) == []
    assert hard_failures(Image.fromarray(good())) == []
    glass = np.zeros((16, 16, 4), dtype=np.uint8)
    glass[:, 0] = glass[:, 15] = glass[0] = glass[15] = (200, 230, 255, 255)  # 玻璃：只有外框，其餘透明
    assert hard_failures(Image.fromarray(glass)) == []


def test_versions_are_kept_not_overwritten(tmp_path):
    tool = SaveTextureTool(tmp_path)
    p1 = tool(good(0), "ruby_ore", "block")
    p2 = tool(good(1), "ruby_ore")
    p3 = tool(good(2), "ruby_ore_v2")  # 模型自己加後綴也不會出現 _v2_v2
    assert p1.size == (256, 276)
    assert sorted(p.name for p in tmp_path.glob("*.png")) == ["ruby_ore.png", "ruby_ore_v2.png", "ruby_ore_v3.png"]
    assert sorted(versions_of(tmp_path, "ruby_ore")) == [1, 2, 3]
    assert split_version("ruby_ore_v12") == "ruby_ore" and split_version("v2") == "v2"
    # 版本互相不同
    assert Image.open(tmp_path / "ruby_ore.png").tobytes() != Image.open(tmp_path / "ruby_ore_v2.png").tobytes()


def test_bad_kind_and_name(tmp_path):
    tool = SaveTextureTool(tmp_path)
    with pytest.raises(ValueError):
        tool(good(), "x", "entity")
    with pytest.raises(ValueError):
        tool(good(), "Bad Name")


def test_export_pack_uses_latest_version_and_kind(tmp_path):
    tool = SaveTextureTool(tmp_path)
    tool(good(0), "ruby_ore", "block")
    tool(good(1), "ruby_ore", "block")
    tool(good(2), "ruby_sword", "item")
    msg = ExportPackTool(str(tmp_path))("mymod")
    assert "2 texture(s)" in msg and "ruby_ore_v2.png" in msg
    with zipfile.ZipFile(tmp_path / "mymod_resourcepack.zip") as z:
        names = set(z.namelist())
        assert "assets/mymod/textures/block/ruby_ore.png" in names
        assert "assets/mymod/textures/item/ruby_sword.png" in names
        assert "assets/mymod/blockstates/ruby_ore.json" in names and "pack.mcmeta" in names
        assert json.loads(z.read("assets/mymod/models/item/ruby_sword.json"))["parent"] == "minecraft:item/generated"
        assert z.read("assets/mymod/textures/block/ruby_ore.png") == (tmp_path / "ruby_ore_v2.png").read_bytes()


def test_export_errors(tmp_path):
    with pytest.raises(ValueError, match="No saved textures"):
        ExportPackTool(str(tmp_path))("mymod")
    SaveTextureTool(tmp_path)(good(), "a")
    with pytest.raises(ValueError, match="Invalid mod id"):
        ExportPackTool(str(tmp_path))("../evil")


def test_theme_roundtrip(tmp_path):
    store = ThemeStore(tmp_path / "themes")
    get, save = GetThemeTool(store), SaveThemeTool(store)
    assert "No saved themes" in get()
    save("Frozen Ruins", palette="#413F54, #cbccd4", description="icy")
    save("Frozen Ruins", style_notes="cold highlights")  # 只更新一個欄位，其他保留
    out = get("frozen ruins")
    assert "#413f54" in out and "icy" in out and "cold highlights" in out
    assert "Frozen Ruins" in get()
    with pytest.raises(ValueError):
        save("x", palette="red")
    assert parse_palette("#FFFFFF") == ["#ffffff"]


def test_audit_summary_shape():
    res = audit_image(Image.fromarray(good()))
    assert res[0][0] in ("PASS", "WARN") and "colors=" in res[0][1]

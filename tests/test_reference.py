import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from texture_agent.reference import ReferenceIndex, discover_sources, scan_source, texture_to_grid  # noqa: E402


def png(color=(120, 120, 120, 255), size=16) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (size, size), color).save(buf, "PNG")
    return buf.getvalue()


def make_jar(path: Path, names: list[str], prefix="assets/minecraft/textures/"):
    with zipfile.ZipFile(path, "w") as z:
        for n in names:
            z.writestr(prefix + n, png())
        z.writestr("assets/minecraft/textures/entity/zombie.png", png())  # 不在核心範圍
        z.writestr("assets/minecraft/lang/en_us.json", "{}")


class FakeEmbedding:
    """測試用：把檔名裡出現的字母統計成 26 維向量，名稱相近的向量就相近，不需要下載任何模型。"""

    def __init__(self):
        self.calls = 0

    def __call__(self, input):
        self.calls += len(input)
        out = []
        for text in input:
            v = np.zeros(26, dtype=np.float32)
            for ch in text.lower():
                if "a" <= ch <= "z":
                    v[ord(ch) - 97] += 1
            n = np.linalg.norm(v)
            out.append(v / n if n else v)
        return out

    @staticmethod
    def name():
        return "fake-letter-count"

    def get_config(self):
        return {}

    @classmethod
    def build_from_config(cls, config):
        return cls()

    def embed_query(self, input):
        return self(input)

    def default_space(self):
        return "l2"

    def supported_spaces(self):
        return ["l2", "cosine", "ip"]

    def is_legacy(self):
        return False


@pytest.fixture
def refs(tmp_path):
    ref_dir = tmp_path / "reference"
    ref_dir.mkdir()
    make_jar(ref_dir / "client.jar", ["block/diamond_ore.png", "block/iron_ore.png", "block/stone.png", "item/iron_sword.png", "item/apple.png"])
    return ReferenceIndex(ref_dir, tmp_path / "index", embedding_function=FakeEmbedding())


def test_scan_only_block_and_item(refs):
    found = scan_source(refs.reference_dir, "client.jar")
    assert {(r.kind, r.name) for r in found} == {
        ("block", "diamond_ore"), ("block", "iron_ore"), ("block", "stone"), ("item", "iron_sword"), ("item", "apple"),
    }
    assert all(r.ns == "minecraft" for r in found)


def test_scan_old_plural_folders_and_pack_prefix(tmp_path):
    ref_dir = tmp_path / "r"
    ref_dir.mkdir()
    make_jar(ref_dir / "old.zip", ["blocks/dirt.png", "items/stick.png"], prefix="MyPack/assets/minecraft/textures/")
    found = {(r.kind, r.name) for r in scan_source(ref_dir, "old.zip")}
    assert found == {("block", "dirt"), ("item", "stick")}


def test_discover_jar_zip_and_asset_folders(tmp_path):
    ref_dir = tmp_path / "r"
    (ref_dir / "uploads").mkdir(parents=True)
    (ref_dir / "uploads" / "mod.jar").write_bytes(b"x")
    (ref_dir / "pack" / "assets" / "mymod" / "textures" / "block").mkdir(parents=True)
    (ref_dir / "pack" / "assets" / "mymod" / "textures" / "block" / "ruby_ore.png").write_bytes(png())
    (ref_dir / "notes.txt").write_text("hi")
    assert discover_sources(ref_dir) == ["pack", "uploads/mod.jar"]
    found = scan_source(ref_dir, "pack")
    assert [(r.ns, r.kind, r.name) for r in found] == [("mymod", "block", "ruby_ore")]


def test_sync_search_and_describe(refs):
    summary = refs.sync()
    assert summary["added"] == 5 and summary["total"] == 5 and not summary["errors"]
    top = refs.search("diamond ore", top_k=2)
    assert top[0]["name"] == "diamond_ore"
    assert refs.search("iron sword", kind="item")[0]["name"] == "iron_sword"
    assert all(m["kind"] == "block" for m in refs.search("iron", kind="block", top_k=5))
    text = refs.describe(refs.search("stone", kind="block", top_k=1))
    assert "minecraft:block/stone" in text and "palette = " in text and text.count('"') > 30


def test_sync_is_incremental_and_removes_stale(refs):
    refs.sync()
    ef: FakeEmbedding = refs._ef
    first_calls = ef.calls
    again = refs.sync()
    assert again["added"] == 0 and again["removed"] == 0 and ef.calls == first_calls  # 沒有變就不重新 embedding

    make_jar(refs.reference_dir / "mod.jar", ["block/ruby_ore.png"], prefix="assets/rubymod/textures/")
    assert refs.sync()["added"] == 1
    assert refs.search("ruby ore")[0]["ns"] == "rubymod"

    (refs.reference_dir / "mod.jar").unlink()
    after = refs.sync()
    assert after["removed"] == 1 and after["total"] == 5


def test_bad_zip_is_reported_not_fatal(refs):
    (refs.reference_dir / "broken.jar").write_bytes(b"not a zip")
    summary = refs.sync()
    assert summary["total"] == 5 and len(summary["errors"]) == 1 and "broken.jar" in summary["errors"][0]


def test_add_upload_sanitizes_name(refs, tmp_path):
    src = tmp_path / "我的 mod (1).jar"
    make_jar(src, ["block/ruby_ore.png"], prefix="assets/rubymod/textures/")
    dest = refs.add_upload(str(src))
    assert dest.parent == refs.upload_dir and dest.exists() and " " not in dest.name and "(" not in dest.name
    assert refs.sync()["added"] == 6  # 原本 5 張加上上傳的 1 張


def test_empty_index_and_blank_query(tmp_path):
    empty = ReferenceIndex(tmp_path / "r", tmp_path / "i", embedding_function=FakeEmbedding())
    empty.sync()
    assert empty.search("stone") == []
    assert empty.search("   ") == []


def test_load_image_rejects_path_escape(refs):
    refs.sync()
    with pytest.raises(ValueError):
        refs.load_image({"source": "../outside.jar", "entry": "x.png"})


def test_texture_to_grid_basic_and_transparent():
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for x in range(8):
        for y in range(16):
            img.putpixel((x, y), (200, 30, 60, 255))
    rows, palette, note = texture_to_grid(img)
    assert len(rows) == 16 and all(len(r) == 16 for r in rows)
    assert rows[0] == "A" * 8 + "." * 8 and palette == {"A": "#c81e3c"} and note == ""


def test_texture_to_grid_animated_and_hires_and_semitransparent():
    strip = Image.new("RGBA", (16, 48), (10, 20, 30, 255))
    rows, _, note = texture_to_grid(strip)
    assert len(rows) == 16 and "first frame" in note
    big = Image.new("RGBA", (32, 32), (1, 2, 3, 255))
    rows, _, note = texture_to_grid(big)
    assert len(rows) == 16 and "downscaled" in note
    glass = Image.new("RGBA", (16, 16), (200, 220, 255, 100))
    _, palette, _ = texture_to_grid(glass)
    assert palette["A"] == "#c8dcff64"  # 半透明保留 alpha
    with pytest.raises(ValueError):
        texture_to_grid(Image.new("RGBA", (20, 20)))


def test_texture_to_grid_many_colors_merges():
    rng = np.random.default_rng(0)
    arr = rng.integers(0, 256, (16, 16, 4), dtype=np.uint8)
    arr[:, :, 3] = 255
    rows, palette, note = texture_to_grid(Image.fromarray(arr))
    assert len(palette) <= 62 and "merged" in note and all(len(r) == 16 for r in rows)

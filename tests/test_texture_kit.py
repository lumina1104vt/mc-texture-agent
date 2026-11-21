import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import texture_kit as k  # noqa: E402


def test_new_canvas_transparent_and_filled():
    assert k.new_canvas().shape == (16, 16, 4) and k.new_canvas().dtype == np.uint8
    assert k.new_canvas()[:, :, 3].max() == 0
    assert (k.new_canvas("#ff0000")[0, 0] == [255, 0, 0, 255]).all()


def test_shade_does_not_wrap_around():
    # 原本的 bug：uint8 的 25 - 50 會變成 231
    assert k.shade((80, 25, 10), -50) == (30, 0, 0, 255)
    assert k.shade((250, 250, 250), 30) == (255, 255, 255, 255)
    assert k.shade((10, 20, 30, 77), 5)[3] == 77


def test_color_validation():
    with pytest.raises(ValueError):
        k.new_canvas((300, 0, 0))
    with pytest.raises(ValueError):
        k.new_canvas("#12345")
    with pytest.raises(ValueError):
        k.new_canvas((1, 2))


def test_set_pixel_uses_x_column_y_row_and_rejects_out_of_range():
    img = k.new_canvas()
    k.set_pixel(img, 3, 5, (1, 2, 3))
    assert (img[5, 3] == [1, 2, 3, 255]).all()
    with pytest.raises(ValueError, match="outside"):
        k.set_pixel(img, 16, 0, (1, 2, 3))
    with pytest.raises(ValueError):
        k.set_pixel(img, 0, -1, (1, 2, 3))


def test_fill_rect_clips():
    img = k.new_canvas()
    k.fill_rect(img, 14, 14, 5, 5, (9, 9, 9))
    assert (img[:, :, 3] > 0).sum() == 4


def test_draw_line_includes_endpoints_and_diagonal():
    img = k.new_canvas()
    k.draw_line(img, 0, 0, 15, 15, (1, 1, 1))
    assert all(img[i, i, 3] == 255 for i in range(16))
    assert (img[:, :, 3] > 0).sum() == 16


def test_from_ascii_and_stamp():
    rows = ["." * 16] * 16
    rows[0] = "A" + "." * 15
    img = k.from_ascii(rows, {"A": (10, 20, 30)})
    assert (img[0, 0] == [10, 20, 30, 255]).all() and img[1, 1, 3] == 0
    with pytest.raises(ValueError, match="16 rows|exactly"):
        k.from_ascii(rows[:15], {"A": (1, 1, 1)})
    with pytest.raises(ValueError, match="Row 0"):
        k.from_ascii(["A" * 15] + rows[1:], {"A": (1, 1, 1)})
    with pytest.raises(ValueError, match="palette"):
        k.stamp_ascii(k.new_canvas(), ["Z"], {"A": (1, 1, 1)})
    base = k.new_canvas("#101010")
    with pytest.raises(ValueError, match="does not fit"):
        k.stamp_ascii(base, ["AA", "A."], {"A": (200, 0, 0)}, x=15, y=15)  # 超出畫布：報錯，不再默默裁掉
    k.stamp_ascii(base, ["AA", "A."], {"A": (200, 0, 0)}, x=14, y=14)  # 剛好放得進去
    assert (base[14, 14] == [200, 0, 0, 255]).all() and (base[15, 15] == [16, 16, 16, 255]).all()


def test_mirror_x():
    img = k.new_canvas()
    k.set_pixel(img, 1, 4, (5, 6, 7))
    k.mirror_x(img)
    assert (img[4, 14] == [5, 6, 7, 255]).all()


def test_outline_only_touches_transparent_neighbors():
    img = k.new_canvas()
    k.set_pixel(img, 5, 5, (200, 200, 200))
    k.outline(img, (0, 0, 0))
    assert (img[5, 5] == [200, 200, 200, 255]).all()
    for x, y in [(4, 5), (6, 5), (5, 4), (5, 6)]:
        assert (img[y, x] == [0, 0, 0, 255]).all()
    assert img[4, 4, 3] == 0  # 對角不畫
    assert (img[:, :, 3] > 0).sum() == 5


def test_bevel_light_top_left_dark_bottom_right_no_wrap():
    img = k.new_canvas((100, 100, 100))
    k.bevel(img, light=30, dark=30)
    assert tuple(img[0, 5, :3]) == (130, 130, 130)
    assert tuple(img[8, 0, :3]) == (130, 130, 130)
    assert tuple(img[15, 5, :3]) == (70, 70, 70)
    assert tuple(img[8, 15, :3]) == (70, 70, 70)
    assert tuple(img[8, 8, :3]) == (100, 100, 100)
    dark = k.new_canvas((10, 10, 10))
    k.bevel(dark, light=0, dark=50)
    assert tuple(dark[15, 5, :3]) == (0, 0, 0)  # 不會環繞成 216
    clear = k.new_canvas()
    k.bevel(clear)
    assert clear.max() == 0  # 透明像素不受影響


def test_stamp_ascii_rejects_ragged_empty_and_oversize():
    pal = {"A": (1, 2, 3)}
    with pytest.raises(ValueError, match="same length"):
        k.stamp_ascii(k.new_canvas(), ["AA", "A"], pal)
    with pytest.raises(ValueError, match="empty"):
        k.stamp_ascii(k.new_canvas(), [], pal)
    with pytest.raises(ValueError, match="does not fit"):
        k.stamp_ascii(k.new_canvas(), ["A" * 17], pal)  # 17 字元的列以前會被默默裁掉
    with pytest.raises(ValueError, match="does not fit"):
        k.stamp_ascii(k.new_canvas(), ["A"] * 17, pal)
    with pytest.raises(ValueError, match="does not fit"):
        k.stamp_ascii(k.new_canvas(), ["A"], pal, x=-1)


def test_ragged_rows_error_includes_padded_rows():
    with pytest.raises(ValueError) as e:
        k.stamp_ascii(k.new_canvas(), [".RR", "R", ".R."], {"R": (1, 2, 3)})
    msg = str(e.value)
    assert "'R..'" in msg and "padded" in msg  # 補齊後的版本可以直接複製
    with pytest.raises(ValueError, match="shorten"):
        k.stamp_ascii(k.new_canvas(), ["A" * 20, "A"], {"A": (1, 2, 3)})
    with pytest.raises(ValueError, match="padded"):
        k.from_ascii(["A"] * 15 + ["AAAA"], {"A": (1, 2, 3)})


def test_exported_functions_cover_the_api():
    assert set(k.EXPORTED) == {"new_canvas", "shade", "set_pixel", "fill_rect", "draw_line", "stamp_ascii", "from_ascii", "mirror_x", "outline", "bevel", "speckle", "gem_cluster"}


def test_speckle_only_touches_opaque_pixels_and_is_deterministic():
    import texture_kit as tk

    a = tk.new_canvas((120, 120, 120))
    tk.fill_rect(a, 0, 0, 4, 4, (0, 0, 0, 0))
    b = a.copy()
    tk.speckle(a, density=0.5, strength=10, seed=3)
    tk.speckle(b, density=0.5, strength=10, seed=3)
    assert (a == b).all()
    assert (a[:4, :4] == 0).all()  # 透明區沒變
    assert (a[4:, 4:, :3] != 120).any()
    c = tk.new_canvas((120, 120, 120))
    tk.speckle(c, density=0.0)
    assert (c[:, :, :3] == 120).all()
    with pytest.raises(ValueError):
        tk.speckle(c, density=2)


def test_gem_cluster_has_requested_size_inside_canvas_and_is_shaded():
    import texture_kit as tk

    base = (125, 125, 125)
    for seed in range(20):
        img = tk.new_canvas(base)
        tk.gem_cluster(img, 8, 8, 5, (200, 30, 60), seed=seed)
        changed = (img[:, :, :3] != base).any(axis=2)
        assert changed.sum() == 5
        ys, xs = changed.nonzero()
        assert xs.min() >= 1 and xs.max() <= 14 and ys.min() >= 1 and ys.max() <= 14
        assert len({tuple(p) for p in img[changed][:, :3]}) >= 3
    img = tk.new_canvas(base)
    tk.gem_cluster(img, 0, 15, 4, (200, 30, 60), seed=1)  # 座標太靠邊會被拉進來
    assert (img[0] == tk.new_canvas(base)[0]).all()
    with pytest.raises(ValueError):
        tk.gem_cluster(img, 8, 8, 1, (200, 30, 60))
    assert "gem_cluster" in tk.EXPORTED and "speckle" in tk.EXPORTED

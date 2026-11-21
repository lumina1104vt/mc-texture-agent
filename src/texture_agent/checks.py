"""材質的品質檢查：在存檔前擋掉明顯有問題的結果，原因會回給 Agent 讓它重畫。

指標改寫自 minecraft-asset-design skill 的 mc_style_audit.py（灰階直方圖、FFT、色塊集中度），
差別是這裡直接吃記憶體裡的圖，不必先存檔，所以失敗的嘗試不會留下檔案或版本。
"""

from __future__ import annotations

import numpy as np
from PIL import Image

MIN_VISIBLE_PIXELS = 8
MAX_COLORS = 48
MIN_TOP5_COVERAGE = 0.70
MIN_LUM_RANGE = 0.25
MIN_HF_RATIO = 0.20


def audit_image(img: Image.Image) -> list[tuple[str, str]]:
    """回傳 [(等級, 訊息)]。FAIL 要修正，WARN 只是提醒，第一筆之外為細項。"""
    arr = np.asarray(img.convert("RGBA"), dtype=np.float32)
    visible = arr[:, :, 3] > 128
    n_visible = int(visible.sum())
    if n_visible < MIN_VISIBLE_PIXELS:
        return [
            ("FAIL", f"visible={n_visible}"),
            (
                "FAIL",
                f"Only {n_visible} visible pixels: the texture is almost completely transparent. "
                "Paint the shape with alpha 255; alpha 0 is only for genuinely transparent areas.",
            ),
        ]

    rgb = arr[:, :, :3] / 255.0
    lum = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    p10, p90 = np.percentile(lum[visible], [10, 90])
    lum_range = float(p90 - p10)

    power = np.abs(np.fft.fftshift(np.fft.fft2(lum - lum.mean()))) ** 2
    h, w = lum.shape
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    hf_ratio = float(power[dist > 0.35 * max(1.0, np.sqrt(cx**2 + cy**2))].sum() / (power.sum() + 1e-12))

    px = (rgb[visible] * 255).astype(np.uint8)
    colors = len(np.unique(px, axis=0))
    q = px // 32
    bins = q[:, 0].astype(int) * 64 + q[:, 1].astype(int) * 8 + q[:, 2].astype(int)
    top5 = float(np.sort(np.bincount(bins))[-5:].sum() / len(bins))

    issues: list[tuple[str, str]] = []
    if colors > MAX_COLORS:
        issues.append(("FAIL", f"Too many colors ({colors} > {MAX_COLORS}): use a small flat palette, no gradients or anti-aliasing."))
    if top5 < MIN_TOP5_COVERAGE:
        issues.append(("FAIL", f"Colors are scattered (top-5 color groups cover {top5:.2f} < {MIN_TOP5_COVERAGE}): this looks like random noise. Use a few related shades in clear clusters."))
    if lum_range < MIN_LUM_RANGE:
        issues.append(("WARN", f"Low value contrast (P90-P10 = {lum_range:.2f}): looks flat."))
    if hf_ratio < MIN_HF_RATIO:
        issues.append(("WARN", f"Little fine detail (FFT high-frequency {hf_ratio:.2f}): looks blurry."))

    status = "FAIL" if any(i[0] == "FAIL" for i in issues) else ("WARN" if issues else "PASS")
    summary = f"visible={n_visible} colors={colors} P90-P10={lum_range:.2f} top5={top5:.2f} fft_hf={hf_ratio:.2f}"
    return [(status, summary)] + issues


def hard_failures(img: Image.Image) -> list[str]:
    """只回傳必須修正的問題（FAIL 的細項）。"""
    return [msg for level, msg in audit_image(img)[1:] if level == "FAIL"]

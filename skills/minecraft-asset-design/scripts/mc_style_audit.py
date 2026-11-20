#!/usr/bin/env python3
"""Universal Minecraft Asset Style Audit: Grayscale Histogram, FFT, Color-Block & 3D Model Validator."""
import sys, os, glob, json
import numpy as np
from PIL import Image

def audit_texture(path):
    im = Image.open(path).convert('RGBA')
    w, h = im.size
    arr = np.array(im, dtype=np.float32)
    if h > w and h % w == 0 and w in (16, 32, 64):
        arr = arr[:w, :w, :]
    alpha = arr[:, :, 3] > 128
    if alpha.sum() < 16:
        return [('WARN', 'Mostly transparent image')]

    opaque_frac = float(alpha.mean())
    fname = os.path.basename(path).lower()
    is_overlay = opaque_frac < 0.55 or any(k in fname for k in ('light', 'overlay', 'glow', 'emissive'))

    rgb = arr[:, :, :3] / 255.0
    lum = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

    # 1. Grayscale Histogram & Contrast
    op_lum = lum[alpha]
    p10, p90 = np.percentile(op_lum, [10, 90])
    lum_range = float(p90 - p10)
    lum_mean = float(op_lum.mean())
    lum_std = float(op_lum.std())

    # 2. 2D Fourier Analysis
    fft = np.fft.fftshift(np.fft.fft2(lum - lum.mean()))
    power = np.abs(fft) ** 2
    total_p = power.sum() + 1e-12
    cy, cx = lum.shape[0] // 2, lum.shape[1] // 2
    Y, X = np.ogrid[:lum.shape[0], :lum.shape[1]]
    dist = np.sqrt((X - cx)**2 + (Y - cy)**2)
    max_r = max(1.0, np.sqrt(cx**2 + cy**2))
    hf_ratio = float(power[dist > 0.35 * max_r].sum() / total_p)
    axis_mask = ((np.abs(X - cx) <= 1) | (np.abs(Y - cy) <= 1)) & (dist > 0)
    ortho_ratio = float(power[axis_mask].sum() / (power[dist > 0].sum() + 1e-12))

    # 3. Color-Block Cohesion
    op_u8 = (rgb[alpha] * 255).astype(np.uint8)
    uniq_colors = len(np.unique(op_u8.reshape(-1, 3), axis=0))
    quant = op_u8 // 32
    bins = quant[:, 0]*64 + quant[:, 1]*8 + quant[:, 2]
    top5_cov = float(np.sort(np.bincount(bins))[-5:].sum() / len(bins))

    issues = []
    if uniq_colors > 48:
        issues.append(('FAIL', f'Too many colors ({uniq_colors} > 48): non-pixel-art gradient or anti-aliasing'))
    if top5_cov < 0.70:
        issues.append(('FAIL', f'Low color-block cohesion (Top5={top5_cov:.2f} < 0.70): noisy dithering or static'))
    if not is_overlay and lum_range < 0.25 and 'bottom' not in fname:
        issues.append(('WARN', f'Low value contrast (P90-P10={lum_range:.2f} < 0.25): flat midtone'))
    if hf_ratio < 0.20:
        issues.append(('WARN', f'Low FFT high-freq ({hf_ratio:.2f} < 0.20): blurry'))

    status = 'PASS' if not issues else issues[0][0]
    summary = f'size={w}x{h} colors={uniq_colors} lum_mean={lum_mean:.2f} std={lum_std:.2f} P90-P10={lum_range:.2f} top5={top5_cov:.2f} fft_hf={hf_ratio:.2f} ortho={ortho_ratio:.2f}'
    return [(status, summary)] + issues

def audit_model(path):
    data = json.load(open(path, 'r', encoding='utf-8'))
    elems = data.get('elements', [])
    parent = data.get('parent', '')
    if not elems and ('cube_all' in parent or 'cube_column' in parent):
        return [('INFO', f'Standard cubic model (parent={parent})')]
    has_rot = any('rotation' in e for e in elems)
    return [('PASS', f'3D model: elements={len(elems)}, has_rotation={has_rot}')]

def main(target):
    paths = [target] if os.path.isfile(target) else sorted(
        glob.glob(f'{target}/**/*.png', recursive=True) + glob.glob(f'{target}/**/*.json', recursive=True)
    )
    for p in paths:
        if p.endswith('.png'):
            res = audit_texture(p)
        elif p.endswith('.json') and 'models' in p:
            res = audit_model(p)
        else:
            continue
        print(f'[{res[0][0]}] {os.path.basename(p)}: {res[0][1]}')
        for lvl, msg in res[1:]:
            print(f'   - {lvl}: {msg}')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 mc_style_audit.py <file_or_dir>')
        sys.exit(1)
    main(sys.argv[1])

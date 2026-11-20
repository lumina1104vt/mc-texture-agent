# Non-Cubic 3D Block Models & UV Mapping Specification

## 1. Structural Grounding Rules

- **No Floating Elements**: Every emitter, port, coil, or top ring must physically connect to the main frame via cross-beams, corner pillars, or horizontal side rails.
- **Flush Footprint Alignment**: Anchor corner pillars and stepped bases cleanly to `[0..16]` boundaries unless intentionally inset on all sides.
- **Dedicated 1:1 Strut UVs**: Thin `2px` or `3px` pillars and beams must map to a dedicated `strut` texture using `[0, 0, dx, dy]` `1:1` UVs rather than slicing `[0..2]` off a `16x16` casing edge (which causes zebra-stripe artifacts).

## 2. Multi-Angle Solid Preview Checklist

Before finalizing any block model:
1. Render with a **solid barycentric triangle rasterizer + Z-buffer** (never sparse point clouds that leave screen-door holes).
2. Inspect at least three views: **Top+Front+Side**, **Top+Back+Side** (checking communication/IO ports), and **Bottom+Front+Side** (checking bottom moire and grounded edges).
3. Inspect a **grayscale render** alongside full color to confirm silhouette and value contrast hold independently of hue.

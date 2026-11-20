---
name: minecraft-asset-design
description: Design, reverse-engineer, and audit Minecraft mod assets (16x16 pixel-art textures, cubic and non-cubic 3D block models, and mod-faithful GUIs) for any Minecraft mod or resource pack. Use whenever the user asks to create, match, or review Minecraft textures, 3D machine/block models, GUIs, or resource-pack assets for any mod style (such as AE2, Create, Mekanism, Thermal, or custom themes).
---
# Minecraft Asset Design

Design cohesive Minecraft mod assets for any target mod style by extracting the target mod's visual grammar first - grayscale luminance histograms, 2D Fourier (FFT) crispness, pixel-level GUI anatomy, and 3D block geometry - rather than guessing colors or shapes.

## When to Use

- Designing or auditing `16x16` block, item, or part textures for any Minecraft mod or custom theme

- Building multi-sided cubic blocks or physically grounded non-cubic 3D block models (`models/block/*.json`, `blockstates/*.json`)

- Crafting mod-faithful GUI sheets (`textures/gui/*.png`, `textures/guis/*.png`) and screen layouts

- Filtering out low-quality, blurry, over-saturated, or off-style reference assets from mod JARs

## Core Design Workflow

### 1. Profile the Target Mod's Visual Grammar First

Never design from memory or lock onto a single color palette. When given a reference mod JAR or asset folder, extract its quantitative baseline before drawing:

- **Grayscale Value & Histogram Check**: Convert reference block textures to grayscale and measure `mean`, `std`, and `P90 - P10` dynamic range. Match the target mod's midtone bridge so textures do not collapse into harsh two-tone extremes or muddy flat gray.

- **2D Fourier (FFT) & Color-Block Check**: Verify crisp `16x16` pixel-art edges (`<= 32` colors per texture, `>= 0.70` top-5 color-block cohesion, strong orthogonal axis energy for tech/industrial mods). Reject high-res non-pixel-art gradients (`> 48` colors) and blurry upscales.

### 2. Master the 6-Sided Cubic Block Before Non-Cubic 3D

A strong non-cubic 3D machine starts from a cohesive 6-sided cubic grammar (see `references/texture-and-histogram-spec.md`):

- **Wrap-Around Seams & Corner Symmetry**: Keep vertical left/right edges (`x=0` and `x=15`) symmetric in brightness so adjacent `Front`, `Side`, and `Back` faces meet cleanly without light-dark corner seams. Use continuous horizontal belts or structural bands across faces.

- **Top-Down Light Direction**: Light `Top`, `Front`, `Side`, and `Back` consistently from above (upper armor plates brighter than lower grounded plates, with catchlights on upward-facing step lips).

- **Clean Brushed Surface (No Static Noise, No Plastic)**: Use 2-4 subtle tonal shades with calm horizontal/directional variation inside each macro color block. Avoid per-pixel random TV-static noise and avoid flat single-color plastic fills.

- **Restrained Windows & Calm Bottoms**: Keep framed functional windows minimal inside the border (1-2 accent tones max), reuse the mod's standard IO/communication port motifs on `Back` without altering the surrounding casing, and keep `Bottom` faces simple to prevent isometric moire aliasing.

### 3. Extend to Physically Grounded Non-Cubic 3D Models

Once the cubic textures are solid, build non-cubic `models/block/*.json` silhouettes (see `references/model-3d-and-uv-spec.md`):

- **Zero Floating Geometry**: Every pillar, emitter, conduit, and cap must physically connect to the chassis via cross-beams, rails, or stepped pedestals.

- **1:1 Dedicated Strut UVs**: Never slice `2px` corners off a `16x16` casing texture onto thin 3D pillars or beams (which causes zebra-stripe artifacts). Provide a dedicated `strut` texture with `1:1` pixel-density UVs.

- **Multi-Angle Solid Verification**: Always inspect renders using a solid barycentric Z-buffer rasterizer (not sparse point clouds) from `Top+Front+Side`, `Top+Back+Side`, and `Bottom+Front+Side` angles.

### 4. Reverse-Engineer GUI Pixel Matrices Directly

Inspect a target mod's actual GUI PNGs pixel-by-pixel before drawing (see `references/gui-anatomy-spec.md`):

- **Window Corners & Unified Inventory Grids**: Match the mod's exact corner chamfer and bevel thickness, and pack `9x3` / `9x1` player inventory grids edge-to-edge without background notch dots at intersections.

- **Input vs. Output Slots & Pure Schematic Lines**: Differentiate input slots from wider/padded output slots, and match whether the mod uses flat schematic connector lines (no white drop-shadow) and stepped pixel-art arrows.

### 5. Audit Assets Before Delivery

Run `scripts/mc_style_audit.py` on candidate textures and block models to verify grayscale histogram balance, FFT sharpness, color-block cohesion, and 3D model geometry:

```bash
python3 scripts/mc_style_audit.py <path_to_png_or_model_json_or_dir>
```

## Gotchas & Anti-Patterns to Reject

- **Bimodal histogram gaps**: Pushing all pixels to pure black and pure white while leaving midtones empty.

- **Corner lighting seams**: Making `x=0` bright and `x=15` dark on cube faces so adjacent faces clash at 3D corners.

- **Dense TV-static noise vs. flat plastic**: Random per-pixel jitter or single-RGB fills instead of calm directional shading.

- **Moire on bottom faces**: High-frequency cross-lines on `Bottom` that alias into noise at shallow camera angles.

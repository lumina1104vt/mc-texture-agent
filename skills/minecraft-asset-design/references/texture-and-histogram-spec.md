# Texture, Grayscale Histogram & Fourier Specification

Applicable to any Minecraft mod style (tech, magic, industrial, or vanilla+).

## 1. Grayscale Histogram & Value Discipline (Color-Agnostic)

Convert reference block textures of your target mod to grayscale (`L`) and check three numbers before authoring:

- **Dynamic Range (`P90 - P10`)**: Typically `0.35` to `0.75` (`90` to `190` in `0-255` scale) for framed tech/machine blocks.
- **Midtone Bridge (`80-210` range)**: Do not jam all pixels into extreme darks (`< 55`) and extreme whites (`> 225`). Keep a well-populated midtone plate (`120-175`) and secondary chamfer (`175-205`) bridging the dark grooves and bright rims.
- **2D Fourier (FFT)**:
  - **High-Frequency Energy (`HF`)**: `0.28` to `0.80` (sharp 1px pixel transitions; `< 0.20` indicates blur).
  - **Orthogonal Axis Ratio (`Ortho`)**: `>= 0.70` for structured tech/industrial blocks.
- **Color-Block Cohesion**: `6` to `32` unique colors per `16x16` face (`> 48` indicates non-pixel-art anti-aliasing or gradients), with Top-5 quantized clusters covering `>= 0.70` of opaque pixels.

## 2. 3D Cube Seam & Lighting Rules

- **Top-Down Vertical Lighting**: On `Front`, `Side`, and `Back`, keep the upper section brighter than the grounded lower section, with catchlights on upward-facing horizontal step lips.
- **Symmetric Horizontal Edges (`x=0` and `x=15`)**: Keep left and right vertical edges symmetric in luminance so Minecraft's directional face shading defines depth naturally without bright-meets-dark vertical corner seams.
- **Calm Surfaces (No Static Noise, No Plastic)**: Use subtle `2-4px` directional streaks or clean panel steps (about 15-25 RGB separation) rather than per-pixel random noise or flat single-color fills.
- **Restrained Windows & Clean Bottoms**: Limit accents inside small framed windows to 1-2 tones, and keep `Bottom` textures simple (1-ring bevel + calm recessed plate) to avoid isometric moire aliasing.

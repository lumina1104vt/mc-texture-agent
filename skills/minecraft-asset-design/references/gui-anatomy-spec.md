# Mod-Faithful GUI Anatomy Specification

## 1. Pixel-Matrix Extraction Workflow

Before drawing a GUI for any target mod, dump `12x12` corner patches, `20x20` slot patches, and indicator/arrow patches from the mod's actual GUI PNGs to capture exact hex values and pixel offsets rather than recoloring vanilla `#C6C6C6` textures.

## 2. Key Structural Elements to Match

- **Window Corners & Bevels**: Match whether the target mod uses `1px` square corners or `3px` stepped chamfered corners, and exact highlight/shadow thickness (`1px` vs `2px`).
- **Unified Seamless Inventory Grids**: Pack `9x3` and `9x1` player inventory slots edge-to-edge without leaving background-color notch dots at slot intersections.
- **Input vs. Output Slot Differentiation**: Give output slots a wider/distinct concentric frame or pedestal (e.g., `26x26` vs `22x22` input slots) when the target mod distinguishes them.
- **Indicator Lines & Arrows**: Check whether the target mod uses flat single-tone schematic lines (no drop-shadow/highlight underneath) or recessed channels, and match stem thickness and stepped pixel-art arrowheads (e.g., `4px` stem + `12px` stepped head).

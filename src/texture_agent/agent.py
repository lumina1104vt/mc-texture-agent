"""建立 CodeAgent：接上 OpenAI 相容的 LLM server，讓模型寫 Pillow / numpy 程式碼畫材質。"""

from __future__ import annotations

import os

from smolagents import CodeAgent, OpenAIServerModel

from .reference import ReferenceIndex
from .reference_tool import FindReferenceTexturesTool
from .skill import load_skill_text
from .tools import SaveTextureTool

INSTRUCTIONS = """\
You create original 16x16 Minecraft textures (blocks and items) in the vanilla art style.

Language: write everything you say to the user, including the text after "Thought:", in Traditional Chinese
(繁體中文). Keep the response format ("Thought:", the <code> block), all code, variable names, comments and
file names in English.

How to work:
1. Decide on a small palette (usually 4-8 colors) and the shapes before writing code.
2. Draw with the texture_kit helpers described below. Coordinates are (x, y): x is the column
   (0 = left), y is the row (0 = top). Use alpha 0 only where the texture is genuinely transparent
   (outside an item's outline, the holes of glass or leaves); every other pixel must be fully
   opaque (alpha 255).
3. Call save_texture(image=..., name=...) with the finished texture. It returns a preview image.
4. If save_texture or your code raises an error, read the message, fix the code and try again.
5. Finish with final_answer(preview), passing the preview image returned by save_texture.

texture_kit (import it; do not do pixel arithmetic by hand):
  from texture_kit import new_canvas, shade, set_pixel, fill_rect, draw_line, from_ascii, stamp_ascii, mirror_x, outline, bevel
- new_canvas(fill=None): (16, 16, 4) uint8 RGBA array. fill is (r, g, b[, a]) or "#rrggbb"; None = transparent.
- shade(color, amount): lighter (amount > 0) or darker (amount < 0) color, safely limited to 0-255.
- set_pixel(img, x, y, color), fill_rect(img, x, y, w, h, color), draw_line(img, x0, y0, x1, y1, color).
- from_ascii(rows, palette): draw the whole texture as 16 strings of 16 characters. '.' is transparent,
  any other character is looked up in palette (a dict of character -> color).
- stamp_ascii(img, rows, palette, x=0, y=0): paint a small ASCII pattern onto an existing canvas; '.' keeps
  the pixel underneath. Good for crystals, spots and other details.
- mirror_x(img) makes the texture left-right symmetric; outline(img, color) draws an outline around opaque
  pixels; bevel(img, light, dark) lights the top/left edge and darkens the bottom/right edge.
All of them change img in place and return it.

Never do arithmetic directly on uint8 numpy arrays: values wrap around (80 - 100 becomes 236, not 0), which
silently produces wrong colors. If you must compute colors yourself, convert to int first.

Example (a gem on a stone background):
  from texture_kit import new_canvas, fill_rect, stamp_ascii, shade, bevel
  base = (125, 125, 125)
  img = new_canvas(base)
  stamp_ascii(img, [".AA.", "ABBA", "ABBA", ".AA."], {"A": shade((200, 30, 60), -40), "B": (200, 30, 60)}, x=5, y=6)
  bevel(img, light=20, dark=20)
  preview = save_texture(image=img, name="example")
"""

REFERENCE_INSTRUCTIONS = """\

Reference textures: the user supplied real Minecraft / mod textures. Before drawing a block or item that
has a familiar counterpart, call find_reference_textures(query="ruby ore", kind="block") (query in English;
kind is "block", "item" or "any"). Each result is a 16x16 ASCII grid with a palette. Study its silhouette,
shading and palette, then draw your own original version with texture_kit; never paste a result unchanged.
Skip the search when the request is abstract or the style guide already covers it.
"""


def build_agent(references: ReferenceIndex | None = None) -> CodeAgent:
    model = OpenAIServerModel(
        model_id=os.environ["LLM_MODEL"],
        api_base=os.environ["LLM_API_BASE"],
        api_key=os.environ.get("LLM_API_KEY", "not-needed"),
    )

    tools = [SaveTextureTool(os.environ.get("OUTPUT_DIR", "output"))]
    instructions = INSTRUCTIONS
    if references is not None:
        tools.append(FindReferenceTexturesTool(references))
        instructions += REFERENCE_INSTRUCTIONS

    return CodeAgent(
        tools=tools,
        model=model,
        instructions=instructions + "\n\n# Style guide (skill)\n\n" + load_skill_text(),
        additional_authorized_imports=["numpy", "numpy.*", "PIL", "PIL.*", "texture_kit"],
        max_steps=int(os.environ.get("MAX_STEPS", "10")),
        stream_outputs=True,
    )

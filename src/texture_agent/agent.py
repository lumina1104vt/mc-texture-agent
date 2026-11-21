"""建立 CodeAgent：接上 OpenAI 相容的 LLM server，讓模型寫 Pillow / numpy 程式碼畫材質。"""

from __future__ import annotations

import os
from pathlib import Path

from smolagents import CodeAgent, OpenAIServerModel
from smolagents.agents import ActionOutput
from smolagents.utils import AgentParsingError

from texture_kit import EXPORTED as KIT_FUNCTIONS

from .extra_tools import ExportPackTool, GetThemeTool, SaveThemeTool
from .reference import ReferenceIndex
from .reference_tool import FindReferenceTexturesTool
from .review import ReviewLoop
from .skill import load_skill_text
from .theme_memory import ThemeStore
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
3. Call save_texture(image=..., name=..., kind="block" or "item") with the finished texture. It checks
   quality (not empty, a small clean palette, no random noise) and returns a preview image labelled with the
   saved file name.
4. If save_texture or your code raises an error, read the message, fix the code and try again.
5. Finish with final_answer(preview), passing the preview image returned by save_texture.

Changing an existing texture: when the user asks for a change ("brighter", "make the gems bigger"), redraw it and
call save_texture with the SAME name. The old file is kept and the new one is saved as a new version
(name_v2.png, name_v3.png...), so never invent version suffixes yourself.

Themes: if the user mentions a theme or a palette to keep, call get_theme(theme_name) before drawing and
save_theme(theme_name, description, palette, style_notes) to store it. When the user asks to export or package
their textures, call export_resource_pack(mod_id) and report the result with final_answer(text).

Talking to the user: when you only need to speak (answer a question, ask for details, explain something,
greet), reply in plain Traditional Chinese with no <code> block. A reply without code is shown to the user
and ends your turn. Never use print() to talk to the user: they cannot see print output.

texture_kit (these functions are already available by name, no import needed; do not do pixel arithmetic by hand):
  from texture_kit import new_canvas, shade, set_pixel, fill_rect, draw_line, from_ascii, stamp_ascii, mirror_x, outline, bevel
- new_canvas(fill=None): (16, 16, 4) uint8 RGBA array. fill is (r, g, b[, a]) or "#rrggbb"; None = transparent.
- shade(color, amount): lighter (amount > 0) or darker (amount < 0) color, safely limited to 0-255.
- set_pixel(img, x, y, color), fill_rect(img, x, y, w, h, color), draw_line(img, x0, y0, x1, y1, color).
- from_ascii(rows, palette): draw the whole texture as 16 strings of 16 characters. '.' is transparent,
  any other character is looked up in palette (a dict of character -> color).
- stamp_ascii(img, rows, palette, x=0, y=0): paint a small ASCII pattern onto an existing canvas; '.' keeps
  the pixel underneath. Good for crystals, spots and other details. Every row must have the same length and the
  whole pattern must fit inside the canvas, otherwise it raises an error; count your rows and columns.
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
  preview = save_texture(image=img, name="example", kind="block")
"""

REVIEW_INSTRUCTIONS = """\

Looking back at your work: do not call final_answer in the same code block as save_texture. After a successful
save you are shown the saved texture as an image. Look at it and compare it with the request (subject,
silhouette, every area painted as intended, clean colors). If it clearly misses, find the cause, redraw and save
again with the same name; if it is good, call final_answer(preview). You can look back at most {n} times per
request.
"""

REFERENCE_INSTRUCTIONS = """\

Reference textures: the user supplied real Minecraft / mod textures. Before drawing a block or item that
has a familiar counterpart, call find_reference_textures(query="ruby ore", kind="block") (query in English;
kind is "block", "item" or "any"). Each result is a 16x16 ASCII grid with a palette. Study its silhouette,
shading and palette, then draw your own original version with texture_kit; never paste a result unchanged.
Skip the search when the request is abstract or the style guide already covers it.
"""


class TextureCodeAgent(CodeAgent):
    """CodeAgent，但沒有程式碼區塊的回覆會直接當成對使用者的回答並結束這一輪。

    smolagents 預設把「沒有 code block」視為格式錯誤並要求重試，模型想單純說話時就會一直卡在重試。
    """

    review: ReviewLoop | None = None

    def run(self, task, *args, **kwargs):
        if self.review is not None:
            self.review.reset()  # 每個新請求重新計算可回頭看的次數
        return super().run(task, *args, **kwargs)

    def _step_stream(self, memory_step):
        open_tag, close_tag = self.code_block_tags
        try:
            yield from super()._step_stream(memory_step)
        except AgentParsingError:
            text = (memory_step.model_output or "").strip()
            if text.endswith(close_tag):  # 父類別會替輸出補上結尾標籤，這裡還原
                text = text[: -len(close_tag)].rstrip()
            if not text or open_tag in text or "```" in text:
                raise  # 空白、或看起來是格式錯誤的程式碼：維持原本的重試
            if text.lower().startswith("thought:"):
                text = text[len("thought:"):].strip()
            memory_step.model_output = text
            if memory_step.model_output_message is not None:
                memory_step.model_output_message.content = text
            memory_step.action_output = text
            yield ActionOutput(output=text, is_final_answer=True)


def build_agent(references: ReferenceIndex | None = None) -> CodeAgent:
    model = OpenAIServerModel(
        model_id=os.environ["LLM_MODEL"],
        api_base=os.environ["LLM_API_BASE"],
        api_key=os.environ.get("LLM_API_KEY", "not-needed"),
    )

    output_dir = os.environ.get("OUTPUT_DIR", "output")
    themes = ThemeStore(Path(os.environ.get("DATA_DIR", "data")) / "themes")
    save_tool = SaveTextureTool(output_dir)
    tools = [save_tool, GetThemeTool(themes), SaveThemeTool(themes), ExportPackTool(output_dir)]
    max_reviews = int(os.environ.get("REVIEW_ROUNDS", "2"))
    review = ReviewLoop(save_tool, max_reviews) if max_reviews > 0 else None
    instructions = INSTRUCTIONS
    if references is not None:
        tools.append(FindReferenceTexturesTool(references))
        instructions += REFERENCE_INSTRUCTIONS
    if review is not None:
        instructions += REVIEW_INSTRUCTIONS.format(n=max_reviews)

    agent = TextureCodeAgent(
        tools=tools,
        model=model,
        instructions=instructions + "\n\n# Style guide (skill)\n\n" + load_skill_text(),
        additional_authorized_imports=["numpy", "numpy.*", "PIL", "PIL.*", "texture_kit"],
        max_steps=int(os.environ.get("MAX_STEPS", "16")),
        stream_outputs=True,
        step_callbacks=[review.on_step] if review else None,
        final_answer_checks=[review.check_final] if review else None,
    )
    agent.review = review
    agent.state.update(KIT_FUNCTIONS)  # texture_kit 的函式不必 import 就能用
    return agent

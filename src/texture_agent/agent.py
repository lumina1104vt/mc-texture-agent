"""建立 CodeAgent：接上 OpenAI 相容的 LLM server，讓模型寫 Pillow / numpy 程式碼畫材質。"""

from __future__ import annotations

import os

from smolagents import CodeAgent, OpenAIServerModel

from .tools import SaveTextureTool

INSTRUCTIONS = """\
You create original 16x16 Minecraft textures (blocks and items) in the vanilla art style.

How to work:
1. Decide on a small palette (usually 4-8 colors) and the shapes before writing code.
2. Draw with numpy (a uint8 array of shape (16, 16, 4), RGBA) and/or PIL.ImageDraw.
   Items need a fully transparent background (alpha 0). Blocks fill all 256 pixels.
3. Call save_texture(image=..., name=...) with the finished texture. It returns a preview image.
4. If save_texture or your code raises an error, read the message, fix the code and try again.
5. Finish with final_answer(preview), passing the preview image returned by save_texture.
"""


def build_agent() -> CodeAgent:
    model = OpenAIServerModel(
        model_id=os.environ["LLM_MODEL"],
        api_base=os.environ["LLM_API_BASE"],
        api_key=os.environ.get("LLM_API_KEY", "not-needed"),
    )

    return CodeAgent(
        tools=[SaveTextureTool(os.environ.get("OUTPUT_DIR", "output"))],
        model=model,
        instructions=INSTRUCTIONS,
        additional_authorized_imports=["numpy", "numpy.*", "PIL", "PIL.*"],
        max_steps=int(os.environ.get("MAX_STEPS", "10")),
    )

"""Tool：讓 Agent 在畫圖前查詢使用者提供的參考材質（原版或模組）。"""

from __future__ import annotations

from smolagents import Tool

from .reference import ReferenceIndex


class FindReferenceTexturesTool(Tool):
    name = "find_reference_textures"
    description = (
        "Search the user's own reference textures (vanilla / mods supplied by the user) by file name and return "
        "the best matches as 16x16 ASCII grids with a palette, ready for texture_kit.from_ascii. "
        "Use it to study how an existing block or item is drawn (shapes, shading, palette); "
        "never copy a result as-is: the final texture must be original."
    )
    inputs = {
        "query": {
            "type": "string",
            "description": "What to look for, in English, e.g. 'ruby ore' or 'iron sword'.",
        },
        "kind": {
            "type": "string",
            "description": "'block', 'item' or 'any'. Defaults to 'any'.",
            "nullable": True,
        },
        "top_k": {
            "type": "integer",
            "description": "How many results to return (1-5). Defaults to 3.",
            "nullable": True,
        },
    }
    output_type = "string"

    def __init__(self, index: ReferenceIndex):
        super().__init__()
        self.index = index

    def forward(self, query: str, kind: str | None = None, top_k: int | None = None) -> str:
        if self.index.count() == 0:
            return "No reference textures are available. Draw from the style guide instead."
        kind = None if kind in (None, "", "any") else kind
        if kind not in (None, "block", "item"):
            raise ValueError("kind must be 'block', 'item' or 'any'")
        top_k = max(1, min(5, top_k or 3))
        matches = self.index.search(query, kind=kind, top_k=top_k)
        if not matches:
            return f"No reference texture matches '{query}'. Draw from the style guide instead."
        return self.index.describe(matches)

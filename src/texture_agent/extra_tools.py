"""Agent 的其他 Tool：主題記憶（讀取／儲存）與匯出資源包。"""

from __future__ import annotations

from smolagents import Tool

from .pack import export_pack
from .theme_memory import ThemeStore, parse_palette


class GetThemeTool(Tool):
    name = "get_theme"
    description = (
        "Look up a saved theme (palette and style notes) so new textures match earlier ones. "
        "Call it when the user mentions a theme or mod style. Call without a name to list saved themes."
    )
    inputs = {
        "theme_name": {"type": "string", "description": "Theme name. Omit to list all saved themes.", "nullable": True},
    }
    output_type = "string"

    def __init__(self, store: ThemeStore):
        super().__init__()
        self.store = store

    def forward(self, theme_name: str | None = None) -> str:
        if not theme_name:
            names = self.store.names()
            return "Saved themes: " + ", ".join(names) if names else "No saved themes yet."
        theme = self.store.get(theme_name)
        return theme.format() if theme else f"No saved theme named '{theme_name}'."


class SaveThemeTool(Tool):
    name = "save_theme"
    description = (
        "Create or update a persistent theme so later requests can reuse its palette and style. "
        "Call it when the user defines a palette or style they want to keep across textures. "
        "Fields you leave out keep their previous value."
    )
    inputs = {
        "theme_name": {"type": "string", "description": "Theme name, e.g. 'frozen_ruins'."},
        "description": {"type": "string", "description": "One-sentence description of the theme.", "nullable": True},
        "palette": {"type": "string", "description": "Comma-separated '#rrggbb' colors, e.g. '#413f54,#cbccd4'.", "nullable": True},
        "style_notes": {"type": "string", "description": "Lighting, contrast or silhouette rules for this theme.", "nullable": True},
    }
    output_type = "string"

    def __init__(self, store: ThemeStore):
        super().__init__()
        self.store = store

    def forward(self, theme_name: str, description: str | None = None, palette: str | None = None, style_notes: str | None = None) -> str:
        theme = self.store.upsert(
            theme_name,
            description=description,
            palette=parse_palette(palette) if palette else None,
            style_notes=style_notes,
        )
        return "Saved.\n" + theme.format()


class ExportPackTool(Tool):
    name = "export_resource_pack"
    description = (
        "Package every texture saved so far (latest version of each name) into a Minecraft resource pack zip "
        "with models and blockstates. Call it when the user asks to export or package their textures."
    )
    inputs = {
        "mod_id": {"type": "string", "description": "Mod id used as the asset namespace, lowercase, e.g. 'mymod'. Defaults to 'mymod'.", "nullable": True},
    }
    output_type = "string"

    def __init__(self, output_dir: str):
        super().__init__()
        self.output_dir = output_dir

    def forward(self, mod_id: str | None = None) -> str:
        zip_path, names = export_pack(self.output_dir, mod_id or "mymod")
        return f"Exported {len(names)} texture(s) to {zip_path.name} (in the output folder): " + ", ".join(names)

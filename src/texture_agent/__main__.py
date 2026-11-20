"""啟動對話式 Web UI：python -m texture_agent"""

import os

from .agent import build_agent
from .reference import ReferenceIndex
from .ui import TextureGradioUI


def load_references() -> ReferenceIndex | None:
    """建立參考材質索引；失敗時只警告，不影響基本功能。"""
    try:
        index = ReferenceIndex.from_env()
        summary = index.sync(progress=print)
        print(f"[reference] {summary['total']} textures indexed from {summary['sources']} source(s)", flush=True)
        for err in summary["errors"]:
            print(f"[reference] skipped: {err}", flush=True)
        return index
    except Exception as exc:  # noqa: BLE001
        print(f"[reference] disabled: {exc}", flush=True)
        return None


def main() -> None:
    references = load_references()
    ui = TextureGradioUI(build_agent(references), references=references, reset_agent_memory=True)
    ui.launch(
        share=False,
        server_name=os.environ.get("HOST", "0.0.0.0"),
        server_port=int(os.environ.get("PORT", "7860")),
    )


if __name__ == "__main__":
    main()

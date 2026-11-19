"""啟動對話式 Web UI：python -m texture_agent"""

import os

from smolagents import GradioUI

from .agent import build_agent


def main() -> None:
    ui = GradioUI(build_agent(), reset_agent_memory=True)
    ui.launch(
        share=False,
        server_name=os.environ.get("HOST", "0.0.0.0"),
        server_port=int(os.environ.get("PORT", "7860")),
    )


if __name__ == "__main__":
    main()

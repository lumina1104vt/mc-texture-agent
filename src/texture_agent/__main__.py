"""啟動對話式 Web UI：python -m texture_agent"""

import os

from smolagents import GradioUI

from .agent import build_agent

# 對話區高度：預設的 400px 太小，改成跟視窗高度連動
CHAT_HEIGHT = os.environ.get("CHAT_HEIGHT", "75vh")


class TextureGradioUI(GradioUI):
    """和 smolagents 的 GradioUI 相同，只把對話區加高。"""

    def create_app(self):
        import gradio as gr

        # Gradio 5.x 需要 type="messages"，Gradio 6 已移除這個參數
        type_messages_kwarg = {"type": "messages"} if gr.__version__.startswith("5") else {}

        chatbot = gr.Chatbot(
            label="Agent",
            height=CHAT_HEIGHT,
            latex_delimiters=[
                {"left": r"$$", "right": r"$$", "display": True},
                {"left": r"$", "right": r"$", "display": False},
                {"left": r"\[", "right": r"\]", "display": True},
                {"left": r"\(", "right": r"\)", "display": False},
            ],
            **type_messages_kwarg,
        )
        return gr.ChatInterface(
            fn=self._stream_response,
            chatbot=chatbot,
            title="Minecraft Texture Generation Agent",
            multimodal=self.file_upload_folder is not None,
            save_history=True,
            **type_messages_kwarg,
        )


def main() -> None:
    ui = TextureGradioUI(build_agent(), reset_agent_memory=True)
    ui.launch(
        share=False,
        server_name=os.environ.get("HOST", "0.0.0.0"),
        server_port=int(os.environ.get("PORT", "7860")),
    )


if __name__ == "__main__":
    main()

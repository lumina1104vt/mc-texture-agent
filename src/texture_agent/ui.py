"""Web UI：在 smolagents 的 GradioUI 上修正串流顯示，並支援在對話中上傳參考 jar / zip。"""

from __future__ import annotations

import os
import re

from smolagents import GradioUI
from smolagents.agents import PlanningStep
from smolagents.gradio_ui import pull_messages_from_step
from smolagents.memory import ActionStep, FinalAnswerStep
from smolagents.models import ChatMessageStreamDelta, agglomerate_stream_deltas

from .reference import SOURCE_SUFFIXES, ReferenceIndex

CHAT_HEIGHT = os.environ.get("CHAT_HEIGHT", "75vh")


def _partial_suffix(text: str, tag: str) -> int:
    """text 結尾若是 tag 的不完整開頭（例如 '</co'），回傳那段的長度，否則 0。"""
    for n in range(min(len(tag) - 1, len(text)), 0, -1):
        if text.endswith(tag[:n]):
            return n
    return 0


def _escape(text: str) -> str:
    return text.replace("<", r"\<").replace(">", r"\>")


def format_stream_text(text: str, open_tag: str = "<code>", close_tag: str = "</code>") -> str:
    """把串流中的模型原始輸出轉成 Markdown：<code>…</code> 立刻變成程式碼區塊。

    原本的做法是把 < > 全部跳脫，所以程式碼區塊要等整步結束才會變漂亮。
    這裡在串流途中就把 <code> 換成 ```python，還沒收到 </code> 時先補上結尾的 ```，
    並且藏起還沒收完的標籤片段（例如 '</co'），畫面就不會閃出標籤文字。
    """
    out: list[str] = []
    pos = 0
    while True:
        start = text.find(open_tag, pos)
        if start == -1:
            rest = text[pos:]
            rest = rest[: len(rest) - _partial_suffix(rest, open_tag)]
            out.append(_escape(rest))
            break
        out.append(_escape(text[pos:start]))
        body_start = start + len(open_tag)
        end = text.find(close_tag, body_start)
        closed = end != -1
        code = text[body_start:end] if closed else text[body_start:]
        if not closed:
            code = code[: len(code) - _partial_suffix(code, close_tag)]
        code = code.strip("\n")
        fence = "````" if "```" in code else "```"
        out.append(f"\n\n{fence}python\n{code}\n{fence}\n\n")
        if not closed:
            break
        pos = end + len(close_tag)
    return "".join(out).lstrip("\n")


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\-.]", "_", os.path.basename(name))


class TextureGradioUI(GradioUI):
    """對話區加高、串流中直接顯示程式碼區塊、可上傳參考 jar / zip。"""

    def __init__(self, agent, references: ReferenceIndex | None = None, file_upload_folder: str | None = None, reset_agent_memory: bool = False):
        self.references = references
        if file_upload_folder is None and references is not None:
            file_upload_folder = os.environ.get("UPLOAD_DIR", "/tmp/uploads")
        super().__init__(agent, file_upload_folder=file_upload_folder, reset_agent_memory=reset_agent_memory)

    def create_app(self):
        import gradio as gr

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

    # --- 上傳的參考檔 ---------------------------------------------------
    def _ingest_references(self, files: list[str]) -> tuple[list[str], str]:
        """把 jar/zip 收進參考庫並同步索引。回傳 (剩下的非 jar 檔案, 給使用者看的狀態文字)。"""
        sources = [f for f in files if os.path.splitext(f)[1].lower() in SOURCE_SUFFIXES]
        others = [f for f in files if f not in sources]
        if not sources:
            return others, ""
        if self.references is None:
            return others, "目前沒有啟用參考材質功能，已忽略上傳的 jar / zip。"
        lines = []
        for f in sources:
            try:
                self.references.add_upload(f)
                lines.append(f"- 已收到 `{_safe_name(f)}`")
            except Exception as exc:  # noqa: BLE001 - 把原因顯示給使用者
                lines.append(f"- `{_safe_name(f)}` 失敗：{exc}")
        summary = self.references.sync()
        lines.append(f"索引完成：共 {summary['total']} 張參考材質（新增 {summary['added']}，移除 {summary['removed']}）。")
        for err in summary["errors"]:
            lines.append(f"- 讀取失敗：{err}")
        return others, "\n".join(lines)

    def _stream_response(self, message, history):  # noqa: ARG002
        import gradio as gr

        if isinstance(message, str):
            text, files = message, []
        else:
            text, files = message.get("text", "") or "", list(message.get("files") or [])

        files, status = self._ingest_references(files)
        if status:
            yield [gr.ChatMessage(role="assistant", content=status)]
        if not text.strip() and not files:
            return  # 只上傳參考檔：不啟動 Agent

        task = text
        saved = [self._save_uploaded_file(f) for f in files] if files and self.file_upload_folder else None
        if saved:
            task += f"\nYou have been provided with these files: {saved}"

        open_tag, close_tag = getattr(self.agent, "code_block_tags", None) or ("<code>", "</code>")
        all_messages = [gr.ChatMessage(role="assistant", content=status)] if status else []
        accumulated: list[ChatMessageStreamDelta] = []
        streaming_idx: int | None = None

        for event in self.agent.run(task, images=saved, stream=True, reset=self.reset_agent_memory, additional_args=None):
            if isinstance(event, ActionStep | PlanningStep | FinalAnswerStep):
                if streaming_idx is not None:
                    all_messages.pop(streaming_idx)
                    streaming_idx = None
                for msg in pull_messages_from_step(event, skip_model_outputs=getattr(self.agent, "stream_outputs", False)):
                    all_messages.append(gr.ChatMessage(role=msg.role, content=msg.content, metadata=msg.metadata))
                    yield all_messages
                accumulated = []
            elif isinstance(event, ChatMessageStreamDelta):
                accumulated.append(event)
                raw = agglomerate_stream_deltas(accumulated).render_as_markdown()
                msg = gr.ChatMessage(role="assistant", content=format_stream_text(raw, open_tag, close_tag))
                if streaming_idx is None:
                    streaming_idx = len(all_messages)
                    all_messages.append(msg)
                else:
                    all_messages[streaming_idx] = msg
                yield all_messages

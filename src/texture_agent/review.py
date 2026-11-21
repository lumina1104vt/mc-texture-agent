"""畫完回頭看：存檔後把成品圖交給模型（支援視覺的模型），讓它對照需求檢查，不對就重畫。

運作方式（用 smolagents 的 step callback 與 final_answer_checks，不另外呼叫模型）：
1. save_texture 成功後，callback 把預覽圖附在這一步的觀察結果裡，下一步模型就看得到圖。
2. 如果模型想在看到圖之前就 final_answer，檢查會擋下來，要它先看。
3. 每個使用者請求最多回頭看 max_reviews 次，避免無止境地修改。
"""

from __future__ import annotations

from smolagents.memory import ActionStep

from .tools import SaveTextureTool

REVIEW_PROMPT = (
    "[Review {n}/{total}] The image attached to this step is the texture you just saved as {file}. "
    "Look at it carefully and compare it with the user's request: does it show the right subject and silhouette? "
    "Is every area painted as intended (a block needs an opaque base such as stone; no flat black or empty areas "
    "unless wanted)? Are the colors clean, not noisy? "
    "If it clearly misses the request, find the cause, redraw it and call save_texture again with the SAME name "
    "(it becomes a new version). Otherwise call final_answer(preview) now."
)
LIMIT_PROMPT = "[Review limit reached] Do not redraw again. Call final_answer(preview) now."


class ReviewLoop:
    def __init__(self, save_tool: SaveTextureTool, max_reviews: int = 2):
        self.save_tool = save_tool
        self.max_reviews = max_reviews
        self.used = 0

    def reset(self) -> None:
        """每個新的使用者請求重新計次。"""
        self.used = 0
        self.save_tool.pending_review = False

    def check_final(self, final_answer, memory, agent=None) -> bool:  # noqa: ARG002
        """final_answer_checks：存檔後還沒看過成品就不准結束。"""
        if self.save_tool.pending_review and self.used < self.max_reviews:
            raise ValueError(
                "You have not looked at the saved texture yet. You will be shown it in the next step; "
                "do not call final_answer in the same code block as save_texture."
            )
        return True

    def on_step(self, step: ActionStep, agent=None) -> None:
        if not isinstance(step, ActionStep):
            return
        tool = self.save_tool
        if agent is not None:  # 只保留最新一張圖，舊的拿掉以節省 token
            for old in agent.memory.steps:
                if isinstance(old, ActionStep) and old is not step:
                    old.observations_images = None
        if not tool.pending_review or tool.last_preview is None:
            return
        tool.pending_review = False
        if self.used < self.max_reviews:
            self.used += 1
            step.observations_images = [tool.last_preview]
            if step.error is None:  # 出錯時錯誤訊息已經說明，不重複
                note = REVIEW_PROMPT.format(n=self.used, total=self.max_reviews, file=tool.last_file)
                step.observations = (step.observations or "") + "\n" + note
        elif step.error is None:
            step.observations = (step.observations or "") + "\n" + LIMIT_PROMPT

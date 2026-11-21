import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("LLM_MODEL", "x")
os.environ.setdefault("LLM_API_BASE", "http://127.0.0.1:9/v1")

from smolagents.models import ChatMessage, Model  # noqa: E402

from texture_agent.agent import build_agent  # noqa: E402


class ScriptedModel(Model):
    def __init__(self, replies):
        super().__init__(model_id="fake")
        self.replies = list(replies)
        self.calls = 0

    def generate(self, messages, stop_sequences=None, **kwargs):
        self.calls += 1
        return ChatMessage(role="assistant", content=self.replies.pop(0))


def make(tmp_path, replies):
    os.environ["OUTPUT_DIR"] = str(tmp_path)
    os.environ["REVIEW_ROUNDS"] = "0"  # 這些測試不測回頭看，關掉才能在同一段程式碼存檔並結束
    try:
        agent = build_agent()
    finally:
        os.environ.pop("REVIEW_ROUNDS")
    agent.model = ScriptedModel(replies)
    agent.stream_outputs = False
    return agent


def test_plain_text_reply_ends_turn(tmp_path):
    agent = make(tmp_path, ["Thought: 你好！想畫什麼方塊或物品？"])
    assert agent.run("嗨", reset=True) == "你好！想畫什麼方塊或物品？"
    assert agent.model.calls == 1


def test_code_still_runs_and_final_answer_works(tmp_path):
    reply = "Thought: 畫一張\n<code>\nfrom texture_kit import new_canvas\nimg = new_canvas((10, 20, 30))\np = save_texture(image=img, name='t')\nfinal_answer(p)\n</code>"
    agent = make(tmp_path, [reply])
    agent.run("畫", reset=True)
    assert (tmp_path / "t.png").exists()


def test_broken_code_block_still_retries(tmp_path):
    good = "<code>\nfinal_answer('ok')\n</code>"
    agent = make(tmp_path, ["<code>\nthis is not closed properly", good])
    assert agent.run("x", reset=True) == "ok"
    assert agent.model.calls == 2


def test_memory_kept_across_runs(tmp_path):
    agent = make(tmp_path, ["第一則", "第二則"])
    agent.run("a", reset=False)
    agent.run("b", reset=False)
    assert sum(1 for s in agent.memory.steps if type(s).__name__ == "TaskStep") == 2


CODE_STONE = """<code>
from texture_kit import new_canvas, set_pixel
img = new_canvas((120, 120, 120))
for i in range(0, 16, 3):
    set_pixel(img, i, (i * 5) % 16, (150, 150, 150))
    set_pixel(img, (i * 7) % 16, i, (90, 90, 90))
preview = save_texture(image=img, name="{name}", kind="block")
final_answer(preview)
</code>"""


def test_edit_then_export_end_to_end(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path / "data")
    agent = make(tmp_path, [CODE_STONE.format(name="demo_stone"), CODE_STONE.format(name="demo_stone"),
                            "<code>\nfinal_answer(export_resource_pack(mod_id='demo'))\n</code>"])
    agent.run("畫石頭", reset=False)
    agent.run("再畫一次", reset=False)  # 同名：應該存成 v2，而不是覆蓋
    result = agent.run("匯出", reset=False)
    assert (tmp_path / "demo_stone.png").exists() and (tmp_path / "demo_stone_v2.png").exists()
    assert "demo_stone_v2.png" in str(result) and (tmp_path / "demo_resourcepack.zip").exists()
    assert {"get_theme", "save_theme", "export_resource_pack", "save_texture"} <= set(agent.tools)


class RecordingModel(ScriptedModel):
    def __init__(self, replies):
        super().__init__(replies)
        self.seen = []

    def generate(self, messages, stop_sequences=None, **kwargs):
        self.seen.append(messages)
        return super().generate(messages, stop_sequences, **kwargs)


def _has_image(messages):
    return any(isinstance(m.content, list) and any(c.get("type") == "image" for c in m.content if isinstance(c, dict)) for m in messages)


def test_review_loop_shows_saved_image_and_blocks_early_finish(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path / "data")
    os.environ["OUTPUT_DIR"] = str(tmp_path)
    agent = build_agent()
    save_and_finish = CODE_STONE.format(name="review_stone")  # 存檔 + 同一段程式碼就 final_answer：應該被擋下
    fixed = CODE_STONE.format(name="review_stone").replace("final_answer(preview)", "pass")
    agent.model = RecordingModel([save_and_finish, "<code>\nfinal_answer(preview)\n</code>"])
    agent.stream_outputs = False
    agent.run("畫石頭", reset=True)
    assert agent.model.calls == 2
    assert _has_image(agent.model.seen[1]) and not _has_image(agent.model.seen[0])
    assert (tmp_path / "review_stone.png").exists()


def test_review_redraw_makes_new_version_and_respects_limit(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path / "data")
    os.environ["OUTPUT_DIR"] = str(tmp_path)
    os.environ["REVIEW_ROUNDS"] = "1"
    try:
        agent = build_agent()
    finally:
        os.environ.pop("REVIEW_ROUNDS")
    save_only = CODE_STONE.format(name="r_stone").replace("final_answer(preview)", "pass")
    # 存檔 → 看圖 → 重畫存檔（已達上限）→ 直接結束也被允許
    agent.model = RecordingModel([save_only, save_only, "<code>\nfinal_answer(preview)\n</code>"])
    agent.stream_outputs = False
    agent.run("畫石頭", reset=True)
    assert (tmp_path / "r_stone.png").exists() and (tmp_path / "r_stone_v2.png").exists()
    assert agent.model.calls == 3
    assert not _has_image(agent.model.seen[2])  # 超過上限後不再附圖


def test_review_can_be_disabled(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path / "data")
    os.environ["OUTPUT_DIR"] = str(tmp_path)
    os.environ["REVIEW_ROUNDS"] = "0"
    try:
        agent = build_agent()
    finally:
        os.environ.pop("REVIEW_ROUNDS")
    assert agent.review is None

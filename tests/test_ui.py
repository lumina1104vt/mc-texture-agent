import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from texture_agent.ui import format_stream_text  # noqa: E402


def test_plain_text_is_escaped():
    assert format_stream_text("a <b> c") == r"a \<b\> c"


def test_open_code_block_renders_as_fence_while_streaming():
    out = format_stream_text("Thought: 畫礦石\n<code>\nimg = 1\nif a < b:")
    assert "```python\nimg = 1\nif a < b:\n```" in out  # 程式碼內不跳脫，結尾自動補上
    assert "<code>" not in out and r"\<" not in out.split("```python")[1]


def test_partial_tags_are_hidden():
    assert "<" not in format_stream_text("Thought: x\n<co") .replace(r"\<", "")
    out = format_stream_text("T\n<code>\nx = 1\n</co")
    assert out.endswith("x = 1\n```\n\n") and "</co" not in out


def test_closed_block_and_trailing_text():
    out = format_stream_text("T\n<code>\nx = 1\n</code>\nmore <i>")
    assert "```python\nx = 1\n```" in out and out.rstrip().endswith(r"more \<i\>")


def test_fence_inside_code_uses_longer_fence():
    out = format_stream_text("<code>\nprint('```')\n</code>")
    assert "````python" in out


def test_custom_tags():
    assert "```python\nx\n```" in format_stream_text("[[\nx\n]]", "[[", "]]")

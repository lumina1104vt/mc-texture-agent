"""批次跑測試案例，記錄每個案例的步數、錯誤數、耗時與存檔結果。

用法（需要真的 LLM server）：
    python -m texture_agent.eval_cases                 # 跑 documents/test-cases.json
    python -m texture_agent.eval_cases --cases x.json --out documents/eval-results.md

每個案例都在獨立的輸出資料夾執行。自動檢查只判斷「有沒有存出符合 kind 的材質、方塊類是否整張不透明」，
畫得好不好仍需人工看圖，結果表的「人工評分」欄留給人填。
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from PIL import Image
from smolagents.memory import ActionStep

from .tools import load_manifest, split_version


def load_cases(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _tokens(agent) -> tuple[int | None, int | None]:
    try:
        usage = agent.monitor.get_total_token_counts()
        return usage.input_tokens, usage.output_tokens
    except Exception:  # noqa: BLE001  不同版本的 smolagents 介面不同，拿不到就留空
        return None, None


def run_case(agent, case: dict, output_dir: str | Path) -> dict:
    """跑一個案例並回傳統計。agent 的存檔資料夾必須是 output_dir。"""
    out = Path(output_dir)
    before = {p.name for p in out.glob("*.png")}
    agent.monitor.reset() if hasattr(agent, "monitor") else None
    started = time.perf_counter()
    crashed = ""
    try:
        agent.run(case["input"], reset=True)
    except Exception as exc:  # noqa: BLE001  單一案例失敗不應中斷整批
        crashed = f"{type(exc).__name__}: {exc}"
    seconds = time.perf_counter() - started

    steps = [s for s in agent.memory.steps if isinstance(s, ActionStep)]
    errors = sum(1 for s in steps if s.error is not None)
    saved = sorted({p.name for p in out.glob("*.png")} - before)
    manifest = load_manifest(out)
    want = case.get("kind", "block")
    kinds_ok = bool(saved) and all(manifest.get(split_version(Path(n).stem), {}).get("kind", "block") == want for n in saved)
    opaque_ok = True
    if case.get("opaque") and saved:
        img = Image.open(out / saved[-1]).convert("RGBA")
        opaque_ok = img.getchannel("A").getextrema()[0] > 0
    tokens_in, tokens_out = _tokens(agent)
    return {
        "id": case["id"],
        "input": case["input"],
        "expect": case["expect"],
        "steps": len(steps),
        "errors": errors,
        "seconds": round(seconds, 1),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "saved": saved,
        "crashed": crashed,
        "auto_pass": bool(saved) and kinds_ok and opaque_ok and not crashed,
    }


def to_markdown(results: list[dict]) -> str:
    lines = [
        "| ID | 輸入 | 預期 | 步數 | 失敗步數 | 秒 | 存檔 | 自動檢查 | 人工評分 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        saved = ", ".join(r["saved"]) or ("（當機：" + r["crashed"] + "）" if r["crashed"] else "（無）")
        lines.append(
            f"| {r['id']} | {r['input']} | {r['expect']} | {r['steps']} | {r['errors']} | {r['seconds']} | {saved} | "
            f"{'Pass' if r['auto_pass'] else 'Fail'} | ☐ |"
        )
    total = len(results)
    ok = sum(r["auto_pass"] for r in results)
    steps = sum(r["steps"] for r in results)
    secs = sum(r["seconds"] for r in results)
    lines += ["", f"自動檢查通過 {ok}/{total}；總步數 {steps}；總耗時 {secs:.0f} 秒。"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", default="documents/test-cases.json")
    parser.add_argument("--out", default="documents/eval-results.md")
    parser.add_argument("--workdir", default="output/eval")
    args = parser.parse_args(argv)

    from .agent import build_agent  # 延後匯入：需要 LLM_MODEL / LLM_API_BASE

    results = []
    for case in load_cases(args.cases):
        out = Path(args.workdir) / case["id"]
        os.environ["OUTPUT_DIR"] = str(out)
        agent = build_agent()
        print(f"[{case['id']}] {case['input']} …", flush=True)
        result = run_case(agent, case, out)
        print(f"    {result['steps']} 步、{result['errors']} 步失敗、{result['seconds']} 秒、{'Pass' if result['auto_pass'] else 'Fail'}", flush=True)
        results.append(result)

    Path(args.out).write_text(to_markdown(results), encoding="utf-8")
    Path(args.out).with_suffix(".json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已寫入 {args.out}")


if __name__ == "__main__":
    main()

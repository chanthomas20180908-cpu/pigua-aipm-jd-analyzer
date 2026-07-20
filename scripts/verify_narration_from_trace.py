"""目的：只重跑 v4 narration 模块，验证候选人可读的总结文案。

定义：从已有 v4 trace 提取 narration 上游输入并调用最后一个子模块的本地验证脚本。

范围包括：
- trace 中 narration LLM 调用记录的读取、输入恢复和 summary 分段检查。

范围不包括：
- 不重跑 element_modeling、jd_core_judgment 或 quality_check，不写入业务日志。

使用与修改规则：
- 仅用于开发验证；trace 格式变化时同步调整提取规则，不让线上业务依赖 trace 文本。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.sub_modules.library import NARRATION_V1


NARRATION_LLM_BLOCK = re.compile(
    r"## 模块三：口语化总结 / narration .*?### LLM 调用\n```json\n(.*?)\n```",
    re.DOTALL,
)
INPUT_MARKER = "## 输入信息\n"


def load_narration_context(trace_path: Path) -> dict[str, Any]:
    """Recover the two narration inputs from a trace's recorded user prompt."""
    trace = trace_path.read_text(encoding="utf-8")
    match = NARRATION_LLM_BLOCK.search(trace)
    if not match:
        raise ValueError("未找到 narration 的 LLM 调用记录。")
    call_payload = json.loads(match.group(1))
    user_prompt = str(call_payload.get("user_prompt") or "")
    _, marker, input_json = user_prompt.partition(INPUT_MARKER)
    if not marker:
        raise ValueError("narration LLM 调用记录缺少输入信息。")
    payload = json.loads(input_json)
    required_keys = {"jd_core_judgment", "quality_check"}
    if not required_keys.issubset(payload):
        raise ValueError("narration 输入缺少 jd_core_judgment 或 quality_check。")
    return {
        "jd_core_judgment": payload["jd_core_judgment"],
        "quality_check": payload["quality_check"],
    }


def summary_paragraphs(summary: object) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", str(summary or "")) if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="只调用 narration 模块验证已有 trace 的总结文案。")
    parser.add_argument("trace", type=Path, help="已有 v4 trace 的 Markdown 路径")
    args = parser.parse_args()

    try:
        context = load_narration_context(args.trace)
        result = NARRATION_V1.run(context)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"验证准备失败：{exc}", file=sys.stderr)
        return 2

    summary = result.get("summary")
    paragraphs = summary_paragraphs(summary)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n分段检查：{len(paragraphs)} 段")
    if not 2 <= len(paragraphs) <= 3:
        print("分段检查失败：summary 应使用两个空行分成 2-3 个短段。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

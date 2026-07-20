"""目的：从指定 v4 分析 trace 生成前端验收样例 fixture。

定义：把被 Git 忽略的调试 Markdown trace 提炼为可提交、可复现的完整 v4 API 响应。

范围包括：
- 读取请求输入和四个子模块输出、重建前端所需的 _meta、校验敏感调试字段。

范围不包括：
- 不调用 LLM、不选择“最新”日志、不服务线上请求、不复制 prompt 或 raw response。

使用与修改规则：
- 必须显式传入已人工确认的 trace；trace 格式或 v4 模块变更时同步更新解析和测试。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


MODULES = (
    ("element_modeling", "modeling", "模块一：建模分析"),
    ("jd_core_judgment", "modeling", "模块一：建模分析"),
    ("quality_check", "quality_review", "模块二：质检"),
    ("narration", "summary", "模块三：口语化总结"),
)
FORBIDDEN_KEYS = {"system_prompt", "user_prompt", "raw_response", "parsed_response"}


class TraceExtractionError(ValueError):
    """Raised when a trace cannot safely produce a complete sample fixture."""


def _parse_json(raw: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TraceExtractionError(f"{label} 不是合法 JSON：{exc.msg}") from exc
    if not isinstance(value, dict):
        raise TraceExtractionError(f"{label} 必须是 JSON 对象")
    return value


def _extract_request(trace_text: str) -> dict[str, Any]:
    match = re.search(r"^## 请求输入\s+```json\s*(.*?)\s*```", trace_text, re.MULTILINE | re.DOTALL)
    if not match:
        raise TraceExtractionError("缺少“请求输入”JSON 区块")
    return _parse_json(match.group(1), "请求输入")


def _extract_module(trace_text: str, name: str) -> tuple[dict[str, Any], int]:
    pattern = re.compile(
        rf"^## [^\n]* / {re.escape(name)} \(v=v1\)(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    module_match = pattern.search(trace_text)
    if not module_match:
        raise TraceExtractionError(f"缺少子模块 {name} 的 trace 区块")
    block = module_match.group(1)
    output_match = re.search(r"^### 输出\s+```json\s*(.*?)\s*```", block, re.MULTILINE | re.DOTALL)
    if not output_match:
        raise TraceExtractionError(f"子模块 {name} 缺少输出 JSON")
    timing_match = re.search(r"- timing_ms:\s*(\d+)", block)
    if not timing_match:
        raise TraceExtractionError(f"子模块 {name} 缺少 timing_ms")
    return _parse_json(output_match.group(1), f"子模块 {name} 输出"), int(timing_match.group(1))


def _find_model(trace_text: str) -> str:
    match = re.search(r'"model"\s*:\s*"([^"]+)"', trace_text)
    if not match:
        raise TraceExtractionError("trace 中未找到 LLM model")
    return match.group(1)


def _assert_safe(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS:
                raise TraceExtractionError(f"fixture 不允许包含敏感调试字段：{path}.{key}")
            _assert_safe(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_safe(child, f"{path}[{index}]")


def extract_frontend_fixture(trace_path: Path) -> dict[str, Any]:
    """Build a deterministic API-shaped v4 result from one explicit trace file."""
    trace_text = trace_path.read_text(encoding="utf-8")
    trace_id_match = re.search(r"^# Analyze Trace:\s*([^\s]+)", trace_text, re.MULTILINE)
    if not trace_id_match:
        raise TraceExtractionError("缺少 trace ID")

    request = _extract_request(trace_text)
    jd_text = request.get("jd_text")
    if not isinstance(jd_text, str) or not jd_text.strip():
        raise TraceExtractionError("请求输入缺少 jd_text")

    result: dict[str, Any] = {"jd_text": jd_text}
    timings: list[dict[str, Any]] = []
    for name, module, module_label in MODULES:
        output, timing_ms = _extract_module(trace_text, name)
        result[name] = output
        timings.append(
            {
                "name": name,
                "version": "v1",
                "module": module,
                "module_label": module_label,
                "timing_ms": timing_ms,
            }
        )

    result["_meta"] = {
        "version": "v4",
        "trace_id": trace_id_match.group(1),
        "trace_log_path": f"logs/{trace_path.name}",
        "timing": {
            "workflow_total_ms": sum(item["timing_ms"] for item in timings),
            "sub_modules": timings,
        },
        "llm": {
            "used": True,
            "provider": "dashscope-compatible",
            "model": _find_model(trace_text),
        },
    }
    _assert_safe(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="从指定 v4 trace 生成前端验收样例 fixture")
    parser.add_argument("trace", type=Path, help="人工确认过的 trace Markdown 文件")
    parser.add_argument("--output", type=Path, required=True, help="输出 fixture JSON 路径")
    args = parser.parse_args()

    fixture = extract_frontend_fixture(args.trace)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成前端验收 fixture：{args.output}")


if __name__ == "__main__":
    main()

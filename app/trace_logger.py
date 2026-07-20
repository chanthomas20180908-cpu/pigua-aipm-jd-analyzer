"""目的：单次分析日志生成器。

定义：按 trace_id 记录 v4 分析过程的 Markdown trace 文件。

范围包括：
- 模块输入输出、流程阶段和日志路径管理。

范围不包括：
- 不参与模型判断，不改变业务返回结构。

使用与修改规则：
- 改动日志格式时保持 logs/ 作为生成物目录，不让业务逻辑依赖日志文本解析。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"


def _json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


class TraceLogger:
    def __init__(self, trace_id: str | None = None) -> None:
        self.trace_id = trace_id or datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid4().hex[:8]
        self.created_at = datetime.now().isoformat(timespec="seconds")
        self._sections: List[str] = []
        self._pending_llm_blocks: List[str] = []

    def add_request(self, *, jd_text: str, resume_text: str | None = None) -> None:
        payload: dict = {"jd_text": jd_text}
        if resume_text:
            payload["resume_text"] = resume_text
        self._sections.append(
            "\n".join(
                [
                    "## 请求输入",
                    "",
                    "```json",
                    _json_block(payload),
                    "```",
                ]
            )
        )

    def add_step(
        self,
        *,
        step: str,
        purpose: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        key_points: Dict[str, Any] | None = None,
    ) -> None:
        blocks = [f"## {step}", "", f"- 目的：{purpose}"]
        if key_points:
            blocks.append("- 关键信息：")
            for key, value in key_points.items():
                blocks.append(f"  - {key}: {value}")
        blocks.extend(
            [
                "",
                "### 输入",
                "```json",
                _json_block(input_data),
                "```",
                "",
                "### 输出",
                "```json",
                _json_block(output_data),
                "```",
            ]
        )
        self._flush_pending_llm_blocks(blocks)
        self._sections.append("\n".join(blocks))

    def add_llm(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        raw_response: str,
        parsed_response: Dict[str, Any] | None,
        timing_ms: int | None = None,
        error: Dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "model": model,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "raw_response": raw_response,
            "parsed_response": parsed_response,
        }
        if timing_ms is not None:
            payload["timing_ms"] = timing_ms
        if error:
            payload["error"] = error
        self._pending_llm_blocks.append(
            "\n".join(
            [
                "### LLM 调用",
                "```json",
                _json_block(payload),
                "```",
            ]
        )
        )

    def add_final(self, *, result: Dict[str, Any]) -> None:
        summary = {
            "recommendation": result.get("recommendation"),
            "match_score": result.get("match_score"),
            "job_type": result.get("job_type"),
            "summary": result.get("summary"),
            "meta": result.get("meta"),
        }
        self._sections.append(
            "\n".join(
                [
                    "## 最终输出摘要",
                    "",
                    "```json",
                    _json_block(summary),
                    "```",
                ]
            )
        )

    def add_error(
        self,
        *,
        step: str,
        error: str,
        details: Dict[str, Any] | None = None,
    ) -> None:
        blocks = [f"## {step}", "", f"- 错误：{error}"]
        if details:
            blocks.extend(
                [
                    "",
                    "### 错误详情",
                    "```json",
                    _json_block(details),
                    "```",
                ]
            )
        self._flush_pending_llm_blocks(blocks)
        self._sections.append("\n".join(blocks))

    def _flush_pending_llm_blocks(self, blocks: List[str]) -> None:
        if not self._pending_llm_blocks:
            return
        blocks.extend(["", *self._pending_llm_blocks])
        self._pending_llm_blocks = []

    def write(self) -> Path:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = LOG_DIR / f"{self.trace_id}.md"
        content = "\n\n".join(
            [
                f"# Analyze Trace: {self.trace_id}",
                "",
                f"- 创建时间：{self.created_at}",
                *self._sections,
            ]
        ).strip() + "\n"
        path.write_text(content, encoding="utf-8")
        return path

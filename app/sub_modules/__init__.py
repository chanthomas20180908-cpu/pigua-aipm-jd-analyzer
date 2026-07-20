"""目的：SubModule 基类。

定义：v4 子模块运行协议的基础定义文件。

范围包括：
- 子模块元数据、prompt 构建和 call_llm_json 调用流程。

范围不包括：
- 不内联具体业务 prompt，不定义工作流顺序。

使用与修改规则：
- 调整 run 协议会影响所有 v4 子模块和 workflow。
"""

from __future__ import annotations

import json
from string import Formatter
import time
from typing import Any, Callable, Dict

from app import llm_client
from app.trace_logger import TraceLogger


class SubModule:
    """A pluggable LLM conversation unit.

    Each sub-module is an independent LLM call: system_prompt + user_prompt → parsed JSON.
    """

    def __init__(
        self,
        *,
        name: str,
        version: str,
        system_prompt: str,
        output_schema: Dict[str, Any],
        build_user_prompt: Callable[[Dict[str, Any]], str],
        temperature: float = 0.3,
        user_prompt_template: str | None = None,
    ):
        self.name = name
        self.version = version
        self.system_prompt = system_prompt
        self.output_schema = output_schema
        self._build_user_prompt = build_user_prompt
        self.temperature = temperature
        self.user_prompt_template = user_prompt_template

    def run(
        self,
        context: Dict[str, Any],
        trace_logger: TraceLogger | None = None,
        llm_options: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        user_prompt = self._build_user_prompt(context)
        if self.user_prompt_template:
            user_prompt = _render_context_template(self.user_prompt_template, context)
        call_options = dict(llm_options or {})
        if "deadline_monotonic" in call_options:
            remaining_seconds = float(call_options["deadline_monotonic"]) - time.perf_counter()
            if remaining_seconds <= 0:
                raise TimeoutError(f"Case timeout reached before submodule {self.name} started.")
            timeout = call_options.get("timeout")
            if timeout is None:
                call_options["timeout"] = remaining_seconds
            else:
                call_options["timeout"] = max(0.001, min(float(timeout), remaining_seconds))
            call_options.pop("deadline_monotonic", None)
        return llm_client.call_llm_json(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            temperature=self.temperature,
            trace_logger=trace_logger,
            **call_options,
        )

    def __repr__(self) -> str:
        return f"SubModule({self.name!r}, version={self.version!r})"


class _MissingSafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _render_context_template(template: str, context: Dict[str, Any]) -> str:
    """Render a simple prompt template against workflow context."""
    field_names = {
        field_name
        for _, field_name, _, _ in Formatter().parse(template)
        if field_name
    }
    values = _MissingSafeDict()
    for field_name in field_names:
        value = context.get(field_name)
        if isinstance(value, (dict, list)):
            values[field_name] = json.dumps(value, ensure_ascii=False, indent=2)
        elif value is None:
            values[field_name] = ""
        else:
            values[field_name] = str(value)
    return template.format_map(values)

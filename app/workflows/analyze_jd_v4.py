"""目的：v4 JD 分析编排。

定义：当前主链路 /analyze/v4 的工作流实现。

范围包括：
- context 初始化、按配置执行子模块、trace 记录和最终返回结构。

范围不包括：
- 不定义具体 prompt，不处理 HTTP 请求模型。

使用与修改规则：
- 改动 context key 时同步后续模块和前端渲染。
"""

from __future__ import annotations

import time
from typing import Any, Dict

from app import llm_client
from app.config.workflow_v4 import WORKFLOW_V4_CONFIG
from app.sub_modules.library import SUB_MODULE_LIBRARY
from app.trace_logger import TraceLogger


def run(*, jd_text: str) -> Dict[str, Any]:
    """Run the v4 JD analysis workflow.

    Three modules execute sequentially. Within each module, sub-modules
    run sequentially, each receiving the full accumulated context.
    """
    return run_with_config(
        jd_text=jd_text,
        config=WORKFLOW_V4_CONFIG,
        library=SUB_MODULE_LIBRARY,
    )


def run_with_config(
    *,
    jd_text: str,
    config: Dict[str, Any],
    library: Dict[tuple[str, str], Any],
    llm_options: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Run v4 workflow with injected config and sub-module library."""
    if not llm_client.llm_is_configured():
        raise llm_client.LLMEnhancementError(
            "v4 workflow requires DASHSCOPE_API_KEY or OPENAI_API_KEY."
        )

    trace_logger = TraceLogger()
    trace_logger.add_request(jd_text=jd_text)

    context: Dict[str, Any] = {"jd_text": jd_text}
    workflow_started_at = time.perf_counter()
    sub_module_timings: list[dict[str, Any]] = []

    try:
        for module in config["modules"]:
            module_label = module.get("label", module["name"])
            for sm_cfg in module["sub_modules"]:
                sm_key = (sm_cfg["name"], sm_cfg["version"])
                sm = library[sm_key]
                submodule_started_at = time.perf_counter()
                result = sm.run(
                    context,
                    trace_logger=trace_logger,
                    llm_options=dict(llm_options or {}),
                )
                submodule_timing_ms = int((time.perf_counter() - submodule_started_at) * 1000)
                context[sm_cfg["name"]] = result
                sub_module_timings.append(
                    {
                        "name": sm.name,
                        "version": sm.version,
                        "module": module["name"],
                        "module_label": module_label,
                        "timing_ms": submodule_timing_ms,
                    }
                )

                trace_logger.add_step(
                    step=f"{module_label} / {sm.name} (v={sm.version})",
                    purpose=f"子模块：{sm.name}",
                    input_data={"context_keys": list(context.keys())},
                    output_data=result,
                    key_points={"timing_ms": submodule_timing_ms},
                )

        trace_logger.add_final(result=context)

    except Exception as exc:
        trace_logger.add_error(
            step="流程异常",
            error=str(exc),
            details={
                "type": type(exc).__name__,
                "context_keys": list(context.keys()),
            },
        )
        raise

    finally:
        log_path = trace_logger.write()
        workflow_total_ms = int((time.perf_counter() - workflow_started_at) * 1000)
        context["_meta"] = {
            "version": config["version"],
            "trace_id": trace_logger.trace_id,
            "trace_log_path": str(log_path),
            "timing": {
                "workflow_total_ms": workflow_total_ms,
                "sub_modules": sub_module_timings,
            },
            "llm": {
                "used": True,
                "provider": "dashscope-compatible",
                "model": llm_client.DEFAULT_MODEL,
            },
        }

    return context

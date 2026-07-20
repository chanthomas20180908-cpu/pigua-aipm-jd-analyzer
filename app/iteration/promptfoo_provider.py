"""目的：为 Promptfoo 提供 v4 工作流调用入口。

定义：Promptfoo Python provider 适配模块，可按 case_id 运行注入配置后的 v4 workflow。

范围包括：
- 从环境变量读取 case、config、library 约定并返回 JSON 字符串结果。

范围不包括：
- 不定义评估断言，不管理 Promptfoo CLI 安装。

使用与修改规则：
- 作为离线 loop 辅助入口使用；线上 /analyze/v4 不依赖本模块。
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from app.config.workflow_v4 import WORKFLOW_V4_CONFIG
from app.iteration.models import VariantSpec
from app.sub_modules import SubModule
from app.sub_modules.library import SUB_MODULE_LIBRARY
from app.workflows.analyze_jd_v4 import run_with_config


class V4PromptfooProvider:
    def call_api(self, prompt: str, options: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
        replay_output = os.getenv("PROMPTFOO_REPLAY_OUTPUT")
        if replay_output:
            return {"output": replay_output}

        case_id = _case_id(prompt=prompt, context=context or {})
        cases_dir = Path(os.getenv("PROMPTFOO_CASES_DIR", "data/test_cases_v1/cases"))
        case_path = cases_dir / f"{case_id}.json"
        case = json.loads(case_path.read_text(encoding="utf-8"))
        jd_text = Path(case["jd_file"]).read_text(encoding="utf-8")
        variant = _variant_from_env()
        output = run_with_config(
            jd_text=jd_text,
            config=copy.deepcopy(WORKFLOW_V4_CONFIG),
            library=_variant_library(variant) if variant else SUB_MODULE_LIBRARY,
        )
        return {"output": json.dumps(output, ensure_ascii=False)}


def _case_id(*, prompt: str, context: dict[str, Any]) -> str:
    vars_value = context.get("vars") if isinstance(context, dict) else None
    if isinstance(vars_value, dict) and vars_value.get("case_id"):
        return str(vars_value["case_id"])
    stripped = prompt.strip()
    if stripped:
        return stripped
    raise ValueError("Promptfoo provider requires case_id.")


def _variant_from_env() -> VariantSpec | None:
    raw = os.getenv("PROMPTFOO_VARIANT_JSON")
    if not raw:
        return None
    data = json.loads(raw)
    target = data.get("target")
    if target is None:
        raise ValueError("PROMPTFOO_VARIANT_JSON missing required field 'target'")
    return VariantSpec(
        id=str(data.get("id") or "promptfoo-variant"),
        target=str(target),
        description=str(data.get("description") or "Promptfoo injected variant."),
        system_prompt_suffix=str(data.get("system_prompt_suffix") or ""),
        user_prompt_template=data.get("user_prompt_template"),
        temperature=data.get("temperature"),
        metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
    )


def _variant_library(variant: VariantSpec) -> dict[tuple[str, str], SubModule]:
    library = dict(SUB_MODULE_LIBRARY)
    for key, module in SUB_MODULE_LIBRARY.items():
        name, version = key
        if name != variant.target:
            continue
        library[key] = SubModule(
            name=module.name,
            version=version,
            system_prompt=module.system_prompt + variant.system_prompt_suffix,
            output_schema=module.output_schema,
            build_user_prompt=module._build_user_prompt,
            temperature=variant.temperature if variant.temperature is not None else module.temperature,
            user_prompt_template=variant.user_prompt_template,
        )
    return library

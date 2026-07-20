"""目的：验证 v4 narration 的清醒搭子式表达契约。

定义：不调用真实 LLM 的 narration prompt 单元测试。

范围包括：
- summary 的分段、候选人视角和克制语气约束。

范围不包括：
- 不判断模型生成文案的事实正确性或视觉排版。

使用与修改规则：
- 调整 narration prompt 时同步更新稳定的表达契约断言。
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.sub_modules.library import NARRATION_V1
from scripts.verify_narration_from_trace import load_narration_context


NARRATION_CONTEXT = {
    "jd_core_judgment": {
        "core_judgment": "岗位负责将电商客服流程中的 AI 能力产品化，并跟踪转化率与人工替代率。",
        "job_focus": ["识别流程问题", "设计问答与工作流", "跟踪业务指标"],
        "strengths": ["业务结果可量化"],
        "risks": ["任职要求和决策权限未说明"],
        "key_findings": [],
        "interview_questions": ["请问该岗位的方案验收和上线决策权由谁负责？"],
    },
    "quality_check": {"risk_points": []},
}


def test_narration_prompt_uses_clear_companion_template() -> None:
    response = {
        "conclusion_label": "保熟",
        "summary": "先说结论，这是个偏业务落地的 AI 产品岗。\n\n工作重点是把流程机会做成方案并看业务结果。\n\n面试时把权限边界问清楚，就能判断是否适合。",
    }

    with patch("app.sub_modules.llm_client.call_llm_json", return_value=response) as call_llm:
        assert NARRATION_V1.run(NARRATION_CONTEXT) == response

    user_prompt = call_llm.call_args.kwargs["user_prompt"]
    system_prompt = call_llm.call_args.kwargs["system_prompt"]
    assert "用两个空行把内容自然分为2-3个短段" in user_prompt
    assert "不要使用“结论：”“岗位：”“风险：”等标题" in user_prompt
    assert "至多自然化用一处" in user_prompt
    assert "禁止脏话、攻击性表达" in user_prompt
    assert "清醒搭子" in system_prompt
    assert "允许使用脏话" not in user_prompt
    assert "全段使用2–4个华强买瓜梗" not in user_prompt


def test_trace_runner_recovers_only_narration_upstream_inputs() -> None:
    upstream_payload = {
        "jd_core_judgment": {"core_judgment": "岗位结论"},
        "quality_check": {"risk_points": []},
    }
    trace_payload = {
        "user_prompt": "前置说明\n## 输入信息\n" + json.dumps(upstream_payload, ensure_ascii=False),
    }
    trace = (
        "## 模块三：口语化总结 / narration (v=v1)\n\n"
        "### LLM 调用\n```json\n"
        + json.dumps(trace_payload, ensure_ascii=False)
        + "\n```\n"
    )

    with TemporaryDirectory() as directory:
        trace_path = Path(directory) / "trace.md"
        trace_path.write_text(trace, encoding="utf-8")
        assert load_narration_context(trace_path) == upstream_payload

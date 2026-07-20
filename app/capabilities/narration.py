"""目的：narration.py 旧版能力模块。

定义：app/capabilities/narration.py 是 v2/v3 兼容能力代码的一部分。

范围包括：
- 旧版分析流程需要的能力函数和数据结构。

范围不包括：
- 不承载当前 v4 主链路的新判断逻辑。

使用与修改规则：
- 除兼容修复外不扩展；新能力进入 app/sub_modules/。
"""

from __future__ import annotations

from typing import Dict, List

from app.llm_client import LLMEnhancementError, enhance_v2_narration, llm_is_configured
from app.trace_logger import TraceLogger


def _default_summary(recommendation: str, job_analysis: Dict[str, object], match_result: Dict[str, object]) -> str:
    family = job_analysis["job_profile"].get("job_family", "general_ai_pm")
    score = match_result["weighted_match_score"]
    if recommendation == "冲":
        return f"这个岗位更偏 {family}，你的核心能力对位，当前可以直接投。"
    if recommendation == "可投":
        return f"这个岗位更偏 {family}，整体能投，但最好先补齐最短的一块证据。"
    if recommendation == "谨慎":
        return f"这个岗位更偏 {family}，不是不能投，但当前胜率更依赖表达和补材料。"
    return f"这个岗位更偏 {family}，当前分数只有 {score}，不建议现在投入。"


def _default_strengths(match_result: Dict[str, object], candidate_analysis: Dict[str, object]) -> List[str]:
    strengths = list(match_result.get("match_highlights", []))
    if not strengths and candidate_analysis["candidate_evidence"].get("project_evidence"):
        strengths.append("简历里至少有可以展开讲的项目证据。")
    if not strengths:
        strengths.append("当前至少有基本的产品背景，不是完全从零开始。")
    return strengths[:4]


def _default_risks(match_result: Dict[str, object], candidate_analysis: Dict[str, object]) -> List[str]:
    risks = list(match_result.get("non_compensatory_gaps", [])) + list(match_result.get("compensatory_gaps", []))
    if not risks and candidate_analysis["missing_evidence"].get("metric_gap"):
        risks.append("指标和结果证据偏少，容易在投递里吃亏。")
    if not risks:
        risks.append("当前风险不大，但仍要注意把证据讲具体。")
    return risks[:4]


def _default_actions(recommendation: str, candidate_analysis: Dict[str, object]) -> List[str]:
    actions: List[str] = []
    missing = candidate_analysis["missing_evidence"]
    if missing.get("ai_landing_gap"):
        actions.append("先补一个 AI 场景或工作流案例，再去冲高 AI 密度岗位。")
    if missing.get("technical_gap"):
        actions.append("把 API、模型、Prompt 或评测相关经历写实一些。")
    if missing.get("metric_gap"):
        actions.append("把项目改写成 问题-方案-指标结果 的结构。")
    if recommendation in {"谨慎", "避开"}:
        actions.append("优先投场景更清晰、落地责任更明确的岗位。")
    if not actions:
        actions.append("可以直接投，但要按岗位关键词微调简历表达。")
    return actions[:4]


def run(
    *,
    jd_text: str,
    resume_text: str,
    job_analysis: Dict[str, object],
    candidate_analysis: Dict[str, object],
    match_result: Dict[str, object],
    recommendation_result: Dict[str, object],
    trace_logger: TraceLogger | None = None,
) -> Dict[str, object]:
    base = {
        "summary": _default_summary(recommendation_result["recommendation"], job_analysis, match_result),
        "strengths": _default_strengths(match_result, candidate_analysis),
        "risks": _default_risks(match_result, candidate_analysis),
        "next_actions": _default_actions(recommendation_result["recommendation"], candidate_analysis),
        "meta": {"llm": {"used": False, "provider": "rule-fallback", "model": None}},
    }
    if not llm_is_configured():
        return base
    try:
        return enhance_v2_narration(
            jd_text=jd_text,
            resume_text=resume_text,
            job_analysis=job_analysis,
            candidate_analysis=candidate_analysis,
            match_result=match_result,
            recommendation_result=recommendation_result,
            fallback_result=base,
            trace_logger=trace_logger,
        )
    except LLMEnhancementError as exc:
        base["meta"]["llm"]["error"] = str(exc)
        return base

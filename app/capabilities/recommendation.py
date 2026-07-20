"""目的：recommendation.py 旧版能力模块。

定义：app/capabilities/recommendation.py 是 v2/v3 兼容能力代码的一部分。

范围包括：
- 旧版分析流程需要的能力函数和数据结构。

范围不包括：
- 不承载当前 v4 主链路的新判断逻辑。

使用与修改规则：
- 除兼容修复外不扩展；新能力进入 app/sub_modules/。
"""

from __future__ import annotations

from typing import Dict, List


def _candidate_readiness_level(score: int, confidence_level: str) -> str:
    if score >= 80 and confidence_level != "low":
        return "ready"
    if score >= 65:
        return "near-ready"
    if score >= 50:
        return "stretch"
    return "not-ready"


def _recommendation_reason(recommendation: str, match_result: Dict[str, object]) -> str:
    if recommendation == "冲":
        return "硬门槛基本通过，核心维度匹配度高，岗位风险可控。"
    if recommendation == "可投":
        return "整体匹配度够用，但仍有短板需要用项目证据和表达去补。"
    if recommendation == "谨慎":
        return "当前存在明显短板或岗位风险，投递会更依赖运气和表达。"
    return "要么硬门槛不通过，要么岗位本身风险偏高，不建议现在投入。"


def run(*, match_result: Dict[str, object], job_analysis: Dict[str, object]) -> Dict[str, object]:
    score = int(match_result["weighted_match_score"])
    gate_passed = bool(match_result["gate_check_result"]["passed"])
    non_comp = match_result["non_compensatory_gaps"]
    job_risk_level = match_result["job_risk_level"]
    confidence_level = match_result["confidence"]["level"]

    recommendation = "避开"
    if gate_passed and score >= 80 and not non_comp and job_risk_level != "high":
        recommendation = "冲"
    elif gate_passed and score >= 65:
        recommendation = "可投"
    elif score >= 50:
        recommendation = "谨慎"

    if job_risk_level == "high" and recommendation == "冲":
        recommendation = "谨慎"
    if non_comp and recommendation == "可投":
        recommendation = "谨慎"
    if not gate_passed and score < 65:
        recommendation = "避开"
    return {
        "recommendation": recommendation,
        "recommendation_reason": _recommendation_reason(recommendation, match_result),
        "job_risk_level": job_risk_level,
        "candidate_readiness_level": _candidate_readiness_level(score, confidence_level),
    }

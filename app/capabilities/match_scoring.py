"""目的：match_scoring.py 旧版能力模块。

定义：app/capabilities/match_scoring.py 是 v2/v3 兼容能力代码的一部分。

范围包括：
- 旧版分析流程需要的能力函数和数据结构。

范围不包括：
- 不承载当前 v4 主链路的新判断逻辑。

使用与修改规则：
- 除兼容修复外不扩展；新能力进入 app/sub_modules/。
"""

from __future__ import annotations

import re
from typing import Dict, List


DIMENSION_WEIGHTS = {
    "ai_understanding": 0.22,
    "scenario_abstraction": 0.14,
    "workflow_design": 0.14,
    "delivery_execution": 0.16,
    "data_metrics": 0.12,
    "stakeholder_push": 0.10,
    "business_fit": 0.12,
}


def _extract_min_years(text: str) -> int:
    if not text:
        return 0
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else 0


def _candidate_years(candidate_profile: Dict[str, object]) -> int:
    return _extract_min_years(str(candidate_profile.get("experience_years", "")))


def _score_ai_understanding(job_analysis: Dict[str, object], candidate_analysis: Dict[str, object]) -> int:
    ai_maturity = job_analysis["job_profile"].get("ai_maturity", "")
    ai_level = candidate_analysis["candidate_profile"].get("ai_experience_level", "none")
    tech_count = len(candidate_analysis["candidate_evidence"].get("technical_evidence", []))
    mapping = {"none": 0, "weak": 2, "medium": 3, "strong": 5}
    score = mapping.get(ai_level, 0)
    if ai_maturity == "deep_delivery":
        score += 1 if tech_count >= 1 else -1
    elif ai_maturity == "concept_heavy":
        score = max(1, score - 1)
    return max(0, min(5, score))


def _score_scenario_abstraction(job_analysis: Dict[str, object], candidate_analysis: Dict[str, object]) -> int:
    needs = "scenario_abstraction" in job_analysis["job_requirements"].get("core_competencies", [])
    project_count = len(candidate_analysis["candidate_evidence"].get("project_evidence", []))
    delivery_count = len(candidate_analysis["candidate_evidence"].get("delivery_evidence", []))
    score = 2 + min(2, project_count)
    if needs and delivery_count:
        score += 1
    return max(0, min(5, score))


def _score_workflow_design(job_analysis: Dict[str, object], candidate_analysis: Dict[str, object]) -> int:
    workflow_needed = "workflow_design" in job_analysis["job_requirements"].get("core_competencies", [])
    project_text = " ".join(candidate_analysis["candidate_evidence"].get("project_evidence", [])).lower()
    score = 1
    if workflow_needed:
        score += 1
    if any(token in project_text for token in ("工作流", "workflow", "知识库", "agent", "平台")):
        score += 2
    if "product_design" in job_analysis["job_requirements"].get("core_competencies", []):
        score += 1
    return max(0, min(5, score))


def _score_delivery_execution(job_analysis: Dict[str, object], candidate_analysis: Dict[str, object]) -> int:
    delivery_mode = job_analysis["job_profile"].get("delivery_mode", "")
    delivery_count = len(candidate_analysis["candidate_evidence"].get("delivery_evidence", []))
    score = min(4, delivery_count)
    if delivery_mode in {"0_to_1", "1_to_10", "mixed"} and delivery_count:
        score += 1
    return max(0, min(5, score))


def _score_data_metrics(job_analysis: Dict[str, object], candidate_analysis: Dict[str, object]) -> int:
    success_metrics = job_analysis["job_requirements"].get("success_metrics", [])
    metric_count = len(candidate_analysis["candidate_evidence"].get("metrics_evidence", []))
    score = min(4, metric_count)
    if success_metrics and metric_count:
        score += 1
    return max(0, min(5, score))


def _score_stakeholder_push(job_analysis: Dict[str, object], candidate_analysis: Dict[str, object]) -> int:
    needs = "stakeholder_push" in job_analysis["job_requirements"].get("core_competencies", [])
    collab_count = len(candidate_analysis["candidate_evidence"].get("collaboration_evidence", []))
    score = min(4, collab_count)
    if needs and collab_count:
        score += 1
    return max(0, min(5, score))


def _score_business_fit(job_analysis: Dict[str, object], candidate_analysis: Dict[str, object]) -> int:
    business_domain = job_analysis["job_profile"].get("business_domain", "general")
    domain_experience = candidate_analysis["candidate_profile"].get("domain_experience", [])
    metric_count = len(candidate_analysis["candidate_evidence"].get("metrics_evidence", []))
    if business_domain == "general":
        return 3 if domain_experience else 2
    score = 4 if business_domain in domain_experience else 2
    if metric_count:
        score += 1
    return max(0, min(5, score))


def _build_gate_check(job_analysis: Dict[str, object], candidate_analysis: Dict[str, object]) -> Dict[str, object]:
    failed_reasons: List[str] = []
    non_negotiables = " ".join(job_analysis["job_requirements"].get("non_negotiables", []))
    required_years = _extract_min_years(" ".join(job_analysis["job_requirements"].get("must_have", [])))
    candidate_years = _candidate_years(candidate_analysis["candidate_profile"])
    if required_years and candidate_years and candidate_years < required_years:
        failed_reasons.append(f"岗位要求至少 {required_years} 年经验，你当前简历只体现出 {candidate_years} 年。")
    if ("ai" in non_negotiables.lower() or "智能体" in non_negotiables or "大模型" in non_negotiables) and candidate_analysis[
        "candidate_profile"
    ].get("ai_experience_level") in {"none", "weak"}:
        failed_reasons.append("岗位把 AI 落地经验视为硬条件，但简历中的 AI 证据偏弱。")
    if job_analysis["job_requirements"].get("technical_depth") == "high" and not candidate_analysis["candidate_evidence"].get(
        "technical_evidence"
    ):
        failed_reasons.append("岗位技术深度较高，但简历缺少技术理解证据。")
    return {"passed": not failed_reasons, "failed_reasons": failed_reasons}


def _confidence(job_analysis: Dict[str, object], candidate_analysis: Dict[str, object], gate: Dict[str, object]) -> Dict[str, object]:
    score = 75
    if not job_analysis["job_profile"].get("job_title"):
        score -= 10
    if not job_analysis["job_requirements"].get("core_competencies"):
        score -= 10
    if candidate_analysis["missing_evidence"].get("metric_gap"):
        score -= 10
    if candidate_analysis["missing_evidence"].get("technical_gap"):
        score -= 10
    if gate["failed_reasons"]:
        score -= 10
    score = max(35, min(95, score))
    level = "high" if score >= 80 else "medium" if score >= 60 else "low"
    return {"level": level, "score": score}


def _job_risk_level(job_analysis: Dict[str, object]) -> str:
    flags = job_analysis.get("job_risk_flags", {})
    if "high" in flags.values():
        return "high"
    if "medium" in flags.values():
        return "medium"
    return "low"


def _gaps(job_analysis: Dict[str, object], candidate_analysis: Dict[str, object], scores: Dict[str, int], gate: Dict[str, object]) -> tuple[List[str], List[str]]:
    non_compensatory = list(gate["failed_reasons"])
    compensatory: List[str] = []
    missing = candidate_analysis["missing_evidence"]
    if scores["ai_understanding"] <= 2:
        non_compensatory.append("AI 理解和落地证据偏弱。")
    if missing.get("metric_gap"):
        compensatory.append("指标和结果证据偏少，可以通过补充项目结果改写来弥补。")
    if missing.get("technical_gap"):
        compensatory.append("技术理解证据偏少，可以通过补充 API、模型或评测实践来弥补。")
    if scores["business_fit"] <= 2:
        compensatory.append("业务领域贴合度一般，但可用相近场景或结果表达补强。")
    return non_compensatory[:3], compensatory[:3]


def _highlights(scores: Dict[str, int], candidate_analysis: Dict[str, object]) -> List[str]:
    highlights: List[str] = []
    if scores["delivery_execution"] >= 4:
        highlights.append("你有比较完整的交付和上线证据。")
    if scores["data_metrics"] >= 4:
        highlights.append("你能拿出指标或结果证据，不只是描述过程。")
    if scores["ai_understanding"] >= 4:
        highlights.append("你的 AI 相关实践足以支撑核心岗位要求。")
    if scores["stakeholder_push"] >= 4:
        highlights.append("你具备跨团队推进复杂项目的证据。")
    if not highlights and candidate_analysis["candidate_evidence"].get("project_evidence"):
        highlights.append("你至少有可对外表达的项目证据。")
    return highlights[:3]


def run(*, job_analysis: Dict[str, object], candidate_analysis: Dict[str, object]) -> Dict[str, object]:
    gate = _build_gate_check(job_analysis, candidate_analysis)
    scores = {
        "ai_understanding": _score_ai_understanding(job_analysis, candidate_analysis),
        "scenario_abstraction": _score_scenario_abstraction(job_analysis, candidate_analysis),
        "workflow_design": _score_workflow_design(job_analysis, candidate_analysis),
        "delivery_execution": _score_delivery_execution(job_analysis, candidate_analysis),
        "data_metrics": _score_data_metrics(job_analysis, candidate_analysis),
        "stakeholder_push": _score_stakeholder_push(job_analysis, candidate_analysis),
        "business_fit": _score_business_fit(job_analysis, candidate_analysis),
    }
    weighted_score = 0.0
    for dimension, value in scores.items():
        adjusted = max(0.0, min(5.0, float(value)))
        weighted_score += adjusted / 5 * 100 * DIMENSION_WEIGHTS[dimension]
    confidence = _confidence(job_analysis, candidate_analysis, gate)
    non_compensatory_gaps, compensatory_gaps = _gaps(job_analysis, candidate_analysis, scores, gate)
    return {
        "gate_check_result": gate,
        "dimension_scores": scores,
        "weighted_match_score": round(weighted_score),
        "confidence": confidence,
        "non_compensatory_gaps": non_compensatory_gaps,
        "compensatory_gaps": compensatory_gaps,
        "match_highlights": _highlights(scores, candidate_analysis),
        "job_risk_level": _job_risk_level(job_analysis),
    }

"""目的：旧版分析器。

定义：早期规则分析器和兼容逻辑集合。

范围包括：
- 历史岗位/简历匹配分析辅助函数。

范围不包括：
- 不作为当前 v4 分析入口。

使用与修改规则：
- 除兼容修复外不扩展。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.jd_parser import build_jd_analysis
from app.resume_parser import build_candidate_analysis


JD_SIGNAL_KEYWORDS: Dict[str, List[str]] = {
    "ai_density": [
        "ai",
        "agent",
        "prompt",
        "workflow",
        "llm",
        "大模型",
        "智能体",
        "知识库",
        "rag",
    ],
    "user_proximity": [
        "用户",
        "客户",
        "场景",
        "体验",
        "需求",
        "业务",
        "customer",
        "user",
    ],
    "delivery_depth": [
        "落地",
        "上线",
        "交付",
        "系统",
        "流程",
        "工作流",
        "自动化",
        "implementation",
        "delivery",
        "integration",
    ],
    "data_ownership": [
        "数据",
        "指标",
        "分析",
        "转化",
        "评估",
        "ab test",
        "metric",
        "analytics",
    ],
    "business_link": [
        "增长",
        "收入",
        "商业化",
        "roi",
        "gmv",
        "利润",
        "cost",
        "revenue",
    ],
    "coordination_bias": [
        "协调",
        "推进",
        "跨部门",
        "跟进",
        "support",
        "协调资源",
        "项目管理",
    ],
}

RESUME_SIGNAL_KEYWORDS: Dict[str, List[str]] = {
    "ai_experience": [
        "ai",
        "agent",
        "prompt",
        "workflow",
        "llm",
        "大模型",
        "智能体",
        "知识库",
        "自动化",
    ],
    "product_design": [
        "prd",
        "原型",
        "需求分析",
        "产品设计",
        "roadmap",
        "产品规划",
    ],
    "abstraction": [
        "场景抽象",
        "问题定义",
        "策略",
        "方案设计",
        "业务分析",
        "需求分析",
        "产品规划",
    ],
    "technical_understanding": [
        "api",
        "sdk",
        "技术方案",
        "算法",
        "模型",
        "工程",
        "python",
        "sql",
    ],
    "data_analysis": [
        "数据分析",
        "ab test",
        "sql",
        "指标",
        "分析",
        "转化",
    ],
    "business_results": [
        "%",
        "增长",
        "提升",
        "降低",
        "roi",
        "收入",
        "效率",
    ],
    "cross_team_push": [
        "跨团队",
        "协调",
        "推动",
        "研发",
        "设计",
        "运营",
        "stakeholder",
    ],
}

GOAL_WEIGHT_HINTS: Dict[str, Dict[str, int]] = {
    "求稳": {"coordination_bias": 1, "user_proximity": 1},
    "冲高薪": {"ai_density": 1, "business_link": 1},
    "转AI": {"ai_density": 1, "delivery_depth": 1},
    "找长期主线": {"delivery_depth": 1, "data_ownership": 1},
}


@dataclass
class SignalSummary:
    scores: Dict[str, int]
    hits: Dict[str, List[str]]


def _normalize(text: str) -> str:
    return text.lower().strip()


def _scan_keywords(text: str, mapping: Dict[str, List[str]]) -> SignalSummary:
    normalized = _normalize(text)
    scores: Dict[str, int] = {}
    hits: Dict[str, List[str]] = {}

    for key, keywords in mapping.items():
        matched = [keyword for keyword in keywords if keyword.lower() in normalized]
        hits[key] = matched[:4]
        score = min(5, max(1, len(matched)))
        if not matched:
            score = 1
        scores[key] = score

    return SignalSummary(scores=scores, hits=hits)


def _job_type(scores: Dict[str, int]) -> str:
    if scores["ai_density"] >= 4 and scores["delivery_depth"] >= 4:
        return "技术落地型 AI PM"
    if scores["coordination_bias"] >= 4 and scores["ai_density"] <= 2:
        return "协调型 PM"
    if scores["ai_density"] <= 2 and scores["coordination_bias"] >= 3:
        return "伪 AI 岗"
    if scores["business_link"] >= 4:
        return "增长型 AI PM"
    return "成长型 AI PM"


def _score_alignment(
    job_scores: Dict[str, int],
    candidate_scores: Dict[str, int],
    goal: str,
) -> Tuple[int, List[str], List[str]]:
    mapping = {
        "ai_density": "ai_experience",
        "user_proximity": "abstraction",
        "delivery_depth": "product_design",
        "data_ownership": "data_analysis",
        "business_link": "business_results",
        "coordination_bias": "cross_team_push",
    }

    total = 0
    strengths: List[str] = []
    risks: List[str] = []
    goal_bonus = GOAL_WEIGHT_HINTS.get(goal, {})

    for job_key, candidate_key in mapping.items():
        job_score = job_scores[job_key] + goal_bonus.get(job_key, 0)
        candidate_score = candidate_scores[candidate_key]
        diff = candidate_score - job_score
        total += max(0, 8 + min(job_score, candidate_score) * 2 - max(0, job_score - candidate_score) * 2)

        if diff >= 0:
            strengths.append(_strength_line(job_key, candidate_key))
        elif diff <= -2:
            risks.append(_risk_line(job_key, candidate_key))

    technical_gap = candidate_scores["technical_understanding"] - job_scores["ai_density"]
    total += max(0, 8 + min(job_scores["ai_density"], candidate_scores["technical_understanding"]) * 2 - max(0, -technical_gap) * 2)
    if technical_gap <= -2:
        risks.append("技术理解证据偏弱，遇到 Agent / Prompt / 工作流类岗位会吃亏。")
    elif technical_gap >= 0:
        strengths.append("技术理解不拖后腿，能支持你解释 AI 产品方案。")

    match_score = max(42, min(90, 42 + total // 2))
    return match_score, strengths[:3], risks[:3]


def _strength_line(job_key: str, candidate_key: str) -> str:
    pairs = {
        ("ai_density", "ai_experience"): "你有 AI / Agent / Prompt 相关实践，能对上岗位的 AI 技术要求。",
        ("user_proximity", "abstraction"): "你有场景拆解和问题定义能力，能承接岗位里的真实业务需求。",
        ("delivery_depth", "product_design"): "你有产品设计和推动落地经验，不只是写想法。",
        ("data_ownership", "data_analysis"): "你具备数据分析意识，能支撑效果评估和指标复盘。",
        ("business_link", "business_results"): "你有结果表达能力，能把项目价值讲到业务层。",
        ("coordination_bias", "cross_team_push"): "你有跨团队推动经验，能适应协作复杂的岗位环境。",
    }
    return pairs[(job_key, candidate_key)]


def _risk_line(job_key: str, candidate_key: str) -> str:
    pairs = {
        ("ai_density", "ai_experience"): "岗位 AI 技术密度偏高，但你的 AI 落地证据还不够硬。",
        ("user_proximity", "abstraction"): "岗位强调真实场景理解，但你的场景抽象能力证据不够明确。",
        ("delivery_depth", "product_design"): "岗位更看重系统落地，你的产品交付证据还需要补。",
        ("data_ownership", "data_analysis"): "岗位要求对指标负责，但你的数据分析证据偏弱。",
        ("business_link", "business_results"): "岗位和商业结果绑定较强，你的业务结果表达不够突出。",
        ("coordination_bias", "cross_team_push"): "岗位协作复杂，但你的跨团队推动证据还不够稳。",
    }
    return pairs[(job_key, candidate_key)]


def _recommendation(match_score: int, job_scores: Dict[str, int], risks: List[str]) -> str:
    pseudo_ai = job_scores["ai_density"] <= 2 and job_scores["coordination_bias"] >= 4
    high_risk = len(risks) >= 3

    if pseudo_ai:
        return "避开"
    if match_score >= 78 and not high_risk:
        return "冲"
    if match_score >= 64:
        return "可投"
    if match_score >= 50:
        return "谨慎"
    return "避开"


def _job_risks(job_scores: Dict[str, int], job_type: str) -> List[str]:
    risks: List[str] = []
    if job_type == "伪 AI 岗":
        risks.append("岗位里的 AI 信号偏弱，更像传统 PM 套了 AI 标题。")
    if job_scores["coordination_bias"] >= 4:
        risks.append("岗位协作和推进占比很高，容易消耗在流程推动里。")
    if job_scores["data_ownership"] <= 2:
        risks.append("JD 对结果指标描述较弱，可能难积累可量化的成绩。")
    if job_scores["delivery_depth"] <= 2:
        risks.append("落地深度不强，成长路径可能停留在方案和协调层。")
    return risks[:3]


def _next_actions(recommendation: str, candidate_scores: Dict[str, int], risks: List[str]) -> List[str]:
    actions: List[str] = []

    if candidate_scores["ai_experience"] <= 2:
        actions.append("先补一个 AI workflow / Agent 小案例，再去投高 AI 密度岗位。")
    if candidate_scores["technical_understanding"] <= 2:
        actions.append("把简历里的技术理解证据写实一点，例如 API、模型、Prompt、评估方式。")
    if candidate_scores["business_results"] <= 2:
        actions.append("把过往项目改写成 业务问题 - 方案 - 指标结果 的表达结构。")
    if recommendation in {"谨慎", "避开"}:
        actions.append("优先寻找用户场景更清晰、落地责任更明确的 AI PM 岗位。")
    if not actions:
        actions.append("可以直接投，但建议按这个岗位的高权重要求微调简历表述。")

    return actions[:3]


def _summary(recommendation: str, job_type: str, strengths: List[str], risks: List[str]) -> str:
    if recommendation == "冲":
        return f"这更像一个{job_type}，你有基础匹配度，可以直接冲。"
    if recommendation == "可投":
        return f"这更像一个{job_type}，整体可投，但先补齐最明显的短板会更稳。"
    if recommendation == "谨慎":
        return f"这更像一个{job_type}，不是不能投，但现在投会比较吃表达和证据。"
    if risks:
        return f"这更像一个{job_type}，岗位或你的当前状态都有明显风险，先别急着冲。"
    return f"这更像一个{job_type}，建议先补材料再决定是否投递。"


def analyze_job_fit(jd_text: str, resume_text: str, user_level: str, goal: str) -> Dict[str, object]:
    job = _scan_keywords(jd_text, JD_SIGNAL_KEYWORDS)
    candidate = _scan_keywords(resume_text, RESUME_SIGNAL_KEYWORDS)
    jd_analysis = build_jd_analysis(jd_text)
    candidate_analysis = build_candidate_analysis(resume_text)
    job_type = _job_type(job.scores)
    match_score, strengths, candidate_risks = _score_alignment(job.scores, candidate.scores, goal)
    job_risks = _job_risks(job.scores, job_type)
    risks = (candidate_risks + job_risks)[:4]
    recommendation = _recommendation(match_score, job.scores, risks)
    actions = _next_actions(recommendation, candidate.scores, risks)
    summary = _summary(recommendation, job_type, strengths, risks)

    return {
        "recommendation": recommendation,
        "match_score": match_score,
        "job_type": job_type,
        "job_analysis": jd_analysis["normalized_jd"],
        "candidate_analysis": candidate_analysis,
        "job_signals": job.scores,
        "candidate_signals": candidate.scores,
        "strengths": strengths,
        "risks": risks,
        "next_actions": actions,
        "summary": summary,
        "meta": {
            "user_level": user_level,
            "goal": goal,
            "jd_hits": job.hits,
            "jd_extraction": jd_analysis["fact_extraction"],
            "jd_extraction_meta": jd_analysis["extraction_meta"],
            "resume_hits": candidate.hits,
            "resume_extraction": candidate_analysis,
        },
    }

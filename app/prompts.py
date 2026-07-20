"""目的：旧版 prompt 集合。

定义：v2 兼容流程使用的 prompt 构造函数。

范围包括：
- 旧版结果文案和叙事增强 prompt。

范围不包括：
- 不维护 v4 子模块 prompt。

使用与修改规则：
- 新 prompt 应进入 app/sub_modules/library.py。
"""

from __future__ import annotations

import json
from typing import Any, Dict


LLM_RESULT_SYSTEM_PROMPT = (
    "你是一个谨慎的 AI PM 求职判断助手。"
    "你只能根据用户提供的 JD、简历和规则结果生成解释。"
    "不能修改 recommendation、match_score、job_type。"
    "不能编造不存在的项目经历。"
    "输出必须是 JSON，不要输出 markdown，不要解释。"
)

V2_NARRATOR_SYSTEM_PROMPT = (
    "你是一个谨慎的 AI PM 求职判断助手。"
    "你只能根据用户提供的 JD、简历、岗位分析、候选人分析、匹配结果和既定 recommendation 生成解释。"
    "你不能修改 recommendation、weighted_match_score、job_risk_level、candidate_readiness_level。"
    "你不能编造不存在的岗位事实和候选人经历。"
    "输出必须是 JSON，不要输出 markdown，不要解释。"
)


def build_llm_result_user_prompt(payload: Dict[str, Any]) -> str:
    return (
        "请基于下面的信息，生成更自然、更具体、但仍然克制的结果文案。"
        "返回 JSON，字段必须只有：summary, strengths, risks, next_actions。"
        "约束：summary 是一句中文结论；strengths、risks、next_actions 都是 2-4 条中文短句数组；"
        "要尽量引用 JD 或简历里的真实线索；不要改 recommendation；不要输出空字段。\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def build_v2_narrator_user_prompt(payload: Dict[str, Any]) -> str:
    return (
        "请基于下面的信息，生成克制、具体、可执行的中文结果文案。"
        "返回 JSON，字段必须只有：summary, strengths, risks, next_actions。"
        "约束："
        "summary 是一句中文结论；"
        "strengths、risks、next_actions 都是 2-4 条中文短句数组；"
        "要优先引用 JD 或简历里的真实线索；"
        "不得修改 recommendation、weighted_match_score、job_risk_level、candidate_readiness_level；"
        "不得补充输入中不存在的新事实。\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


JD_EXTRACTION_SYSTEM_PROMPT = (
    "你是一名资深 AI PM 岗位分析专家。你的任务是从原始 JD 文本中提取结构化信息，"
    "用于判断该岗位是否适合 AI 产品经理候选人。"
    "你必须只基于输入的 JD 文本做判断，不能编造不存在的信息。"
    "输出必须是合法 JSON，不要输出 markdown、不要解释、不要注释。"
)


def build_jd_extraction_user_prompt(jd_text: str) -> str:
    schema = {
        "job_profile": {
            "job_title": "岗位标题，如'AI 产品经理'，提取不到为空字符串",
            "job_family": "岗位家族，可选：internal_ai_platform | enterprise_collaboration | ai_workflow_tool | marketing_ai_product | robotics_ai_product | general_ai_pm",
            "business_domain": "业务领域，可选：marketing | collaboration | knowledge_management | education | robotics | efficiency | general",
            "industry_domain": "垂直行业，可选：insurance | finance | healthcare | education | retail | e_commerce | manufacturing | logistics | automotive | real_estate | enterprise_service | general",
            "company_stage": "公司阶段，提取不到为空字符串",
            "company_size": "公司规模，提取不到为空字符串",
            "ai_maturity": "AI 成熟度，可选：deep_delivery | application_driven | concept_heavy | 空字符串",
            "delivery_mode": "交付模式，可选：0_to_1 | 1_to_10 | platform | scenario_driven | mixed | 空字符串",
            "business_orientation": "业务/技术导向，可选：business-heavy | tech-heavy | hybrid",
            "role_perspective": "岗位角色视角，可选：pm | engineer | hybrid",
            "enterprise_type": "企业类型，可选：traditional_enterprise | ai_native | hybrid",
            "location": "工作地点，提取不到为空字符串",
            "salary_range": "薪资范围，提取不到为空字符串",
        },
        "job_requirements": {
            "must_have": ["必须具备的要求列表，最多 6 条"],
            "preferred": ["优先条件列表，最多 4 条"],
            "core_competencies": ["核心能力标签列表，可选：ai_understanding, scenario_abstraction, workflow_design, product_design, technical_collaboration, delivery_execution, data_metrics, stakeholder_push, business_judgment, user_insight"],
            "technical_depth": "技术深度要求，可选：high | medium | low",
            "success_metrics": ["岗位关注的成功指标，最多 4 条"],
            "non_negotiables": ["硬性门槛，最多 4 条"],
        },
        "job_risk_flags": {
            "pseudo_ai_risk": "伪 AI 岗风险，可选：high | medium | low",
            "coordination_heavy_risk": "协调过重风险，可选：high | medium | low",
            "scope_bloat_risk": "职责过宽风险，可选：high | medium | low",
            "unclear_metric_risk": "指标不清风险，可选：high | medium | low",
        },
    }
    return (
        "请从下面原始 JD 文本中提取结构化信息，返回严格符合以下 JSON Schema 的对象。\n\n"
        "提取要求：\n"
        "1. 只基于 JD 原文，不编造任何信息。\n"
        "2. 枚举字段必须严格使用给定的可选值，不要用其他值。\n"
        "3. 如果某字段无法从 JD 中判断，使用空字符串或空数组，不要猜测。\n"
        "4. industry_domain 要识别垂直行业，如保险、金融、医疗、教育、零售、电商等。\n"
        "5. business_orientation 判断岗位偏业务还是偏技术：如果强调业务场景、行业经验、业务理解、商业化，则为 business-heavy；如果强调算法、工程、代码、架构，则为 tech-heavy。\n"
        "6. role_perspective 判断 JD 招的是 PM 还是工程师：出现'产品经理'、'产品规划'、'需求分析'、'业务抽象'为 pm；出现'开发'、'算法工程师'、'数据科学家'、'代码'为 engineer。\n"
        "7. enterprise_type 判断企业类型：强调传统行业经验、行业 know-how、企业级客户为 traditional_enterprise；强调 AI 原生、自研模型、智能体平台为 ai_native。\n\n"
        f"JSON Schema：\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"原始 JD 文本：\n{jd_text}"
    )


CANDIDATE_EXTRACTION_SYSTEM_PROMPT = (
    "你是一名资深 AI PM 简历分析专家。你的任务是从原始简历文本中提取结构化信息，"
    "并判断候选人与目标岗位的角色匹配度。"
    "你必须只基于输入的简历文本做判断，不能编造不存在的经历。"
    "输出必须是合法 JSON，不要输出 markdown、不要解释、不要注释。"
)


def build_candidate_extraction_user_prompt(resume_text: str, job_analysis: Dict[str, Any]) -> str:
    schema = {
        "candidate_profile": {
            "experience_years": "工作年限，如'5年'，提取不到为空字符串",
            "domain_experience": ["候选人的领域经验标签列表，如 marketing, collaboration, education 等"],
            "ai_experience_level": "AI 经验水平，可选：none | weak | medium | strong",
            "product_background": "产品背景，可选：b_end_product | c_end_product | platform_product | ai_product | 空字符串",
            "candidate_role_orientation": "候选人角色定位，可选：pm | engineer | researcher | ambiguous",
        },
        "candidate_evidence": {
            "project_evidence": ["项目/产品经验证据，最多 6 条"],
            "delivery_evidence": ["交付/上线证据，最多 5 条"],
            "metrics_evidence": ["指标/结果证据，最多 5 条"],
            "technical_evidence": ["技术理解证据，最多 5 条"],
            "collaboration_evidence": ["协作/推动证据，最多 5 条"],
            "product_evidence": ["产品经理视角证据，如产品规划、需求分析、用户研究、roadmap、竞品分析等，最多 5 条"],
            "business_evidence": ["业务/商业视角证据，如商业化、营收、定价、ROI、市场调研等，最多 5 条"],
        },
        "missing_evidence": {
            "ai_landing_gap": ["缺少 AI 落地证据时的说明"],
            "metric_gap": ["缺少指标证据时的说明"],
            "domain_gap": ["缺少领域背景证据时的说明"],
            "technical_gap": ["缺少技术理解证据时的说明"],
            "product_gap": ["缺少产品视角证据时的说明"],
            "business_gap": ["缺少业务视角证据时的说明"],
        },
        "role_mismatch_flag": "布尔值：当 JD 明确要求 PM 角色，但候选人明显是 engineer/researcher 时为 true",
    }
    job_context = {
        "role_perspective": job_analysis.get("job_profile", {}).get("role_perspective", ""),
        "business_orientation": job_analysis.get("job_profile", {}).get("business_orientation", ""),
        "industry_domain": job_analysis.get("job_profile", {}).get("industry_domain", ""),
        "must_have": job_analysis.get("job_requirements", {}).get("must_have", []),
    }
    return (
        "请从下面原始简历文本中提取结构化信息，并判断候选人与目标岗位的角色匹配度，"
        "返回严格符合以下 JSON Schema 的对象。\n\n"
        "提取要求：\n"
        "1. 只基于简历原文，不编造任何经历。\n"
        "2. 枚举字段必须严格使用给定的可选值。\n"
        "3. candidate_role_orientation 要区分候选人本质是 PM、工程师还是研究员。\n"
        "   - pm：职位标题含'产品经理'，或有产品规划、需求分析、用户研究、roadmap、商业模式等证据。\n"
        "   - engineer：职位标题含'数据科学家'、'算法工程师'、'软件工程师'，或大量 Prompt Engineering、RAG、模型部署、代码、技术实现细节。\n"
        "   - researcher：职位标题含'研究员'、'研究科学家'，或强调发表论文、顶会、模型研究。\n"
        "   - ambiguous：无法明确判断。\n"
        "4. product_evidence 必须是从产品经理视角出发的证据，不是技术实现细节。\n"
        "5. business_evidence 必须是商业化、营收、成本、ROI、市场调研等商业视角证据。\n"
        "6. role_mismatch_flag 判断：当目标岗位 role_perspective 为 pm，而候选人 candidate_role_orientation 为 engineer 或 researcher 时，置为 true。\n\n"
        f"目标岗位关键信息：\n{json.dumps(job_context, ensure_ascii=False, indent=2)}\n\n"
        f"JSON Schema：\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"原始简历文本：\n{resume_text}"
    )

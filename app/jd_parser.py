"""目的：旧版 JD 规则解析器。

定义：v2 流程使用的规则型 JD parser。

范围包括：
- 关键词、岗位类型和风险信号提取。

范围不包括：
- 不参与 v4 LLM-Native 主链路。

使用与修改规则：
- 新判断不要加到这里，除非明确修复 v2。
"""

from __future__ import annotations

import re
from typing import Dict, List


AI_TERMS = [
    "ai",
    "agent",
    "prompt",
    "llm",
    "大模型",
    "智能体",
    "多模态",
    "知识库",
    "rag",
    "工作流",
    "skill",
]

DOMAIN_TERMS = [
    "营销",
    "智能营销",
    "企业协作",
    "协作",
    "研发效能",
    "知识管理",
    "教育",
    "机器人",
    "内容",
    "效率工具",
    "内部平台",
]

METRIC_TERMS = [
    "命中率",
    "完成率",
    "渗透率",
    "转化率",
    "留存",
    "roi",
    "成本",
    "效率",
    "质量",
    "评测",
    "ab test",
]

TOOL_TERMS = [
    "sql",
    "python",
    "api",
    "sdk",
    "gpt",
    "gemini",
    "claude",
]

EDU_TERMS = ["博士", "硕士", "本科", "大专"]
RESP_HEADINGS = ("岗位职责", "职责描述", "工作职责", "你将负责", "你需要负责")
REQ_HEADINGS = ("任职要求", "岗位要求", "任职资格", "我们希望你", "职位要求")
PREF_MARKERS = ("优先", "加分", "bonus", "plus")


def _clean_line(line: str) -> str:
    return re.sub(r"^[\s>*\-•\d\.\)、(（【\[]+", "", line).strip(" ：:;；")


def _normalize_spaces(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n").replace("\r", "\n")).strip()


def _extract_first(pattern: str, text: str, flags: int = 0) -> str:
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else ""


def _extract_salary_text(text: str) -> str:
    patterns = [
        r"(\d{1,2}\s*[kK]\s*[-~至]\s*\d{1,2}\s*[kK](?:/\S+)?)",
        r"(\d+(?:\.\d+)?\s*[-~至]\s*\d+(?:\.\d+)?\s*万(?:/\S+)?)",
        r"(薪资[:：]?\s*[^\n，,；;]+)",
    ]
    for pattern in patterns:
        value = _extract_first(pattern, text)
        if value:
            return value
    return ""


def _extract_list_by_heading(text: str, headings: tuple[str, ...]) -> List[str]:
    lines = [line.rstrip() for line in text.split("\n")]
    items: List[str] = []
    active = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if active and items:
                break
            continue

        if any(heading in line for heading in headings):
            active = True
            tail = line.split("：", 1)[1] if "：" in line else line.split(":", 1)[1] if ":" in line else ""
            tail = _clean_line(tail)
            if tail:
                items.append(tail)
            continue

        if active and any(marker in line for marker in RESP_HEADINGS + REQ_HEADINGS) and not any(
            heading in line for heading in headings
        ):
            break

        if active:
            cleaned = _clean_line(line)
            if cleaned:
                items.append(cleaned)

    return _dedupe(items)


def _split_sentences(text: str) -> List[str]:
    chunks = re.split(r"[。\n；;]+", text)
    return _dedupe([_clean_line(chunk) for chunk in chunks if _clean_line(chunk)])


def _dedupe(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _extract_requirements(text: str) -> List[str]:
    items = _extract_list_by_heading(text, REQ_HEADINGS)
    if items:
        return items
    candidates = _split_sentences(text)
    return [item for item in candidates if any(token in item for token in ("要求", "经验", "能力", "熟悉", "了解", "优先"))][:8]


def _extract_responsibilities(text: str) -> List[str]:
    items = _extract_list_by_heading(text, RESP_HEADINGS)
    if items:
        return items
    candidates = _split_sentences(text)
    return [
        item
        for item in candidates
        if any(token in item for token in ("负责", "参与", "推动", "设计", "规划", "优化"))
    ][:8]


def _extract_keywords(text: str, keywords: List[str]) -> List[str]:
    normalized = text.lower()
    return [keyword for keyword in keywords if keyword.lower() in normalized]


def _infer_job_family(facts: Dict[str, object]) -> str:
    source = " ".join(
        [
            str(facts.get("job_type_text", "")),
            " ".join(facts.get("responsibilities", [])),
            " ".join(facts.get("requirements", [])),
            " ".join(facts.get("preferred_items", [])),
        ]
    ).lower()

    if any(token in source for token in ("内部平台", "研发效能", "工作平台")):
        return "internal_ai_platform"
    if any(token in source for token in ("企业协作", "协作", "知识管理")):
        return "enterprise_collaboration"
    if any(token in source for token in ("workflow", "工作流", "智能助手", "agent")):
        return "ai_workflow_tool"
    if any(token in source for token in ("营销", "增长", "roi", "商业化")):
        return "marketing_ai_product"
    if any(token in source for token in ("机器人", "多模态", "语音", "视觉")):
        return "robotics_ai_product"
    return "general_ai_pm"


def _infer_business_domain(facts: Dict[str, object]) -> str:
    source = " ".join(
        facts.get("keywords", {}).get("domain_terms", []) + facts.get("responsibilities", []) + facts.get("requirements", [])
    ).lower()
    if any(token in source for token in ("营销", "增长")):
        return "marketing"
    if any(token in source for token in ("协作", "内部平台", "研发效能")):
        return "collaboration"
    if any(token in source for token in ("知识管理", "知识库")):
        return "knowledge_management"
    if "教育" in source:
        return "education"
    if any(token in source for token in ("机器人", "多模态", "语音", "视觉")):
        return "robotics"
    if any(token in source for token in ("效率工具", "工作流")):
        return "efficiency"
    return "general"


def _infer_ai_maturity(facts: Dict[str, object]) -> str:
    responsibilities = " ".join(facts.get("responsibilities", [])).lower()
    requirements = " ".join(facts.get("requirements", [])).lower()
    ai_terms = facts.get("keywords", {}).get("ai_terms", [])
    ai_count = len(ai_terms)
    deep_signals = ("评测", "迭代", "工作流", "上下文", "agent", "prompt", "模型边界", "命中率", "完成率")
    if ai_count >= 3 and any(signal in responsibilities + requirements for signal in deep_signals):
        return "deep_delivery"
    if ai_count >= 2 and any(signal in responsibilities + requirements for signal in ("场景", "产品方案", "落地", "优化")):
        return "application_driven"
    if ai_count:
        return "concept_heavy"
    return ""


def _infer_delivery_mode(facts: Dict[str, object]) -> str:
    source = " ".join(facts.get("responsibilities", []) + facts.get("requirements", [])).lower()
    flags = []
    if any(token in source for token in ("0到1", "从0到1", "从零到一")):
        flags.append("0_to_1")
    if any(token in source for token in ("优化", "迭代", "持续")):
        flags.append("1_to_10")
    if any(token in source for token in ("平台", "生态", "基础设施")):
        flags.append("platform")
    if any(token in source for token in ("场景", "交互", "工作流", "用户流程")):
        flags.append("scenario_driven")
    if len(flags) > 1:
        return "mixed"
    return flags[0] if flags else ""


def _infer_core_competencies(facts: Dict[str, object]) -> List[str]:
    source = " ".join(facts.get("responsibilities", []) + facts.get("requirements", [])).lower()
    mapping = {
        "ai_understanding": ("ai", "agent", "prompt", "大模型", "模型"),
        "scenario_abstraction": ("场景", "抽象", "需求分析", "问题定义"),
        "workflow_design": ("工作流", "流程", "编排", "平台"),
        "product_design": ("产品设计", "原型", "规划", "路线图"),
        "technical_collaboration": ("算法", "研发", "技术方案", "数据科学家"),
        "delivery_execution": ("落地", "交付", "上线", "推动"),
        "data_metrics": ("指标", "评估", "分析", "ab test", "评测"),
        "stakeholder_push": ("跨团队", "协调", "沟通", "推进"),
        "business_judgment": ("业务", "商业化", "价值", "roi"),
        "user_insight": ("用户需求", "体验", "洞察", "用户"),
    }
    return [label for label, tokens in mapping.items() if any(token.lower() in source for token in tokens)]


def _infer_technical_depth(facts: Dict[str, object]) -> str:
    source = " ".join(
        facts.get("keywords", {}).get("tool_terms", [])
        + facts.get("keywords", {}).get("ai_terms", [])
        + facts.get("responsibilities", [])
        + facts.get("requirements", [])
    ).lower()
    high_signals = ("多agent", "多智能体", "prompt", "评测", "上下文", "gpt", "gemini", "api", "sdk")
    medium_signals = ("技术方案", "算法", "模型", "工作流", "数据")
    if sum(token in source for token in high_signals) >= 2:
        return "high"
    if any(token in source for token in medium_signals):
        return "medium"
    return "low" if source else ""


def _infer_success_metrics(facts: Dict[str, object]) -> List[str]:
    metrics = facts.get("keywords", {}).get("metric_terms", [])
    if metrics:
        return metrics[:4]
    source = " ".join(facts.get("responsibilities", [])).lower()
    inferred = []
    if "优化" in source:
        inferred.append("体验质量")
    if "落地" in source or "上线" in source:
        inferred.append("交付效率")
    return inferred[:3]


def _infer_non_negotiables(facts: Dict[str, object]) -> List[str]:
    results: List[str] = []
    exp = str(facts.get("experience_required", ""))
    if exp:
        results.append(exp)
    requirements = facts.get("requirements", [])
    for item in requirements:
        if any(token in item for token in ("必须", "要求", "AI产品经验", "AI Agent产品落地经验")):
            results.append(item)
    return results[:4]


def _infer_risk_flags(facts: Dict[str, object], normalized: Dict[str, object]) -> Dict[str, str]:
    source = " ".join(facts.get("responsibilities", []) + facts.get("requirements", [])).lower()
    ai_terms = len(facts.get("keywords", {}).get("ai_terms", []))
    coord = sum(token in source for token in ("协调", "推进", "沟通", "跨团队"))
    product_depth = sum(token in source for token in ("工作流", "评测", "prompt", "agent", "落地", "指标"))
    pseudo_ai_risk = "high" if ai_terms >= 2 and product_depth <= 1 else "low"
    coordination_heavy_risk = "high" if coord >= 3 and product_depth <= 2 else "medium" if coord >= 2 else "low"
    scope_tokens = ("规划", "设计", "技术方案", "数据分析", "商业化", "交付", "增长", "运营")
    scope_bloat_risk = "high" if sum(token in source for token in scope_tokens) >= 5 else "medium" if sum(token in source for token in scope_tokens) >= 3 else "low"
    unclear_metric_risk = "high" if not normalized["job_requirements"]["success_metrics"] else "low"
    return {
        "pseudo_ai_risk": pseudo_ai_risk,
        "coordination_heavy_risk": coordination_heavy_risk,
        "scope_bloat_risk": scope_bloat_risk,
        "unclear_metric_risk": unclear_metric_risk,
    }


def extract_jd_facts(raw_jd_text: str) -> Dict[str, object]:
    text = _normalize_spaces(raw_jd_text)
    responsibilities = _extract_responsibilities(text)
    requirements = _extract_requirements(text)
    preferred_items = [item for item in requirements if any(marker in item.lower() for marker in PREF_MARKERS)]

    return {
        "job_title": _extract_first(r"(?m)^(?:职位|岗位|招聘岗位|job title|title)?[:：]?\s*([^\n]{2,30}(?:产品经理|pm|负责人))\s*$", text, re.IGNORECASE),
        "company_name": _extract_first(r"(?m)^(?:公司|企业|公司名称)[:：]?\s*([^\n]{2,40})$", text),
        "salary_text": _extract_salary_text(text),
        "location": _extract_first(r"(?:工作地点|地点|base|城市)[:：]?\s*([^\n，,；;]{2,20})", text, re.IGNORECASE),
        "experience_required": _extract_first(r"(\d+\s*[-~至]?\s*\d*\s*年(?:以上|及以上)?(?:经验|工作经验)?)", text),
        "education_required": next((term for term in EDU_TERMS if term in text), ""),
        "job_type_text": _extract_first(r"(?:岗位类型|职位类型)[:：]?\s*([^\n]{2,20})", text),
        "responsibilities": responsibilities,
        "requirements": requirements,
        "preferred_items": preferred_items,
        "benefits": [item for item in _split_sentences(text) if any(token in item for token in ("五险一金", "体检", "年假", "旅游", "补贴"))][:6],
        "keywords": {
            "ai_terms": _extract_keywords(text, AI_TERMS),
            "domain_terms": _extract_keywords(text, DOMAIN_TERMS),
            "metric_terms": _extract_keywords(text, METRIC_TERMS),
            "tool_terms": _extract_keywords(text, TOOL_TERMS),
        },
    }


def normalize_jd(facts: Dict[str, object]) -> Dict[str, object]:
    normalized = {
        "job_profile": {
            "job_title": facts["job_title"],
            "job_family": _infer_job_family(facts),
            "business_domain": _infer_business_domain(facts),
            "company_stage": "",
            "company_size": "",
            "ai_maturity": _infer_ai_maturity(facts),
            "delivery_mode": _infer_delivery_mode(facts),
            "location": facts["location"],
            "salary_range": facts["salary_text"],
        },
        "job_requirements": {
            "must_have": _dedupe(
                [facts["experience_required"], facts["education_required"]]
                + [item for item in facts["requirements"] if "优先" not in item and "加分" not in item][:4]
            ),
            "preferred": facts["preferred_items"][:4],
            "core_competencies": _infer_core_competencies(facts),
            "technical_depth": _infer_technical_depth(facts),
            "success_metrics": _infer_success_metrics(facts),
            "non_negotiables": _infer_non_negotiables(facts),
        },
        "job_risk_flags": {},
    }
    normalized["job_risk_flags"] = _infer_risk_flags(facts, normalized)
    return normalized


def build_jd_analysis(raw_jd_text: str) -> Dict[str, object]:
    facts = extract_jd_facts(raw_jd_text)
    normalized = normalize_jd(facts)
    explicit_fields = [key for key, value in facts.items() if value and key != "keywords"]
    inferred_fields = [
        "job_profile.job_family",
        "job_profile.business_domain",
        "job_profile.ai_maturity",
        "job_profile.delivery_mode",
        "job_requirements.core_competencies",
        "job_requirements.technical_depth",
        "job_requirements.success_metrics",
        "job_requirements.non_negotiables",
        "job_risk_flags",
    ]
    missing_fields = [key for key, value in facts.items() if not value and key != "keywords"]
    return {
        "raw_text": raw_jd_text,
        "fact_extraction": facts,
        "normalized_jd": normalized,
        "extraction_meta": {
            "explicit_fields": explicit_fields,
            "inferred_fields": inferred_fields,
            "missing_fields": missing_fields,
            "confidence_notes": [
                "当前为规则抽取版，优先保证稳定性，不依赖 LLM 推断。",
                "岗位类型、AI 成熟度、交付模式、风险标记属于有界推断字段。",
            ],
        },
    }

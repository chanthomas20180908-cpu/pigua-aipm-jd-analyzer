"""目的：旧版简历规则解析器。

定义：v2 流程使用的规则型简历 parser。

范围包括：
- 候选人经验、技能和项目线索提取。

范围不包括：
- 不参与 v4 JD-only 主链路。

使用与修改规则：
- 新主链路不应依赖该 parser。
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
    "知识库",
    "工作流",
    "自动化",
    "rag",
]

DOMAIN_PATTERNS = {
    "marketing": ("营销", "广告", "投放", "增长"),
    "collaboration": ("协作", "内部平台", "研发效能", "效率工具", "办公"),
    "knowledge_management": ("知识库", "知识管理", "问答"),
    "education": ("教育", "教学", "学习"),
    "robotics": ("机器人", "语音", "视觉", "多模态"),
    "consumer_content": ("内容", "社区", "抖音", "视频"),
}

PRODUCT_BACKGROUND_PATTERNS = {
    "b_end_product": ("b端", "to b", "企业", "内部平台", "协作"),
    "c_end_product": ("c端", "to c", "消费者", "内容", "用户增长"),
    "platform_product": ("平台", "中台", "基础设施", "生态"),
    "ai_product": ("ai", "agent", "prompt", "工作流", "知识库"),
}

PROJECT_EVIDENCE_PATTERNS = ("负责", "主导", "参与", "推动", "设计", "落地", "上线", "搭建", "优化")
METRIC_PATTERNS = (
    "%",
    "提升",
    "降低",
    "增长",
    "roi",
    "效率",
    "转化",
    "留存",
    "命中率",
    "完成率",
    "渗透率",
)
TECH_PATTERNS = ("api", "sdk", "sql", "python", "prompt", "模型", "算法", "评测", "ab test", "数据分析")
COLLAB_PATTERNS = ("跨团队", "协调", "推动", "研发", "设计", "运营", "算法", "数据")


def _normalize_spaces(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n").replace("\r", "\n")).strip()


def _clean_line(line: str) -> str:
    return re.sub(r"^[\s>*\-•\d\.\)、(（【\[]+", "", line).strip(" ：:;；")


def _split_blocks(text: str) -> List[str]:
    blocks = re.split(r"[\n。；;]+", text)
    return [cleaned for block in blocks if (cleaned := _clean_line(block))]


def _extract_experience_years(text: str) -> str:
    patterns = [
        r"(\d+\s*[-~至]?\s*\d*\s*年[^\n，,；;。]{0,12}经验)",
        r"(\d+\s*[-~至]?\s*\d*\s*年(?:以上)?(?:产品经理)?经验)",
        r"(\d+\s*年(?:以上)?(?:工作)?经验)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def _extract_domain_experience(text: str) -> List[str]:
    normalized = text.lower()
    domains = [label for label, patterns in DOMAIN_PATTERNS.items() if any(pattern.lower() in normalized for pattern in patterns)]
    return domains


def _infer_ai_experience_level(text: str, project_evidence: List[str], technical_evidence: List[str]) -> str:
    normalized = text.lower()
    ai_hits = sum(term.lower() in normalized for term in AI_TERMS)
    if ai_hits >= 3 and (len(project_evidence) >= 2 or len(technical_evidence) >= 2):
        return "strong"
    if ai_hits >= 2:
        return "medium"
    if ai_hits >= 1:
        return "weak"
    return "none"


def _infer_product_background(text: str) -> str:
    normalized = text.lower()
    for label, patterns in PRODUCT_BACKGROUND_PATTERNS.items():
        if any(pattern.lower() in normalized for pattern in patterns):
            return label
    return ""


def _extract_project_evidence(blocks: List[str]) -> List[str]:
    return [block for block in blocks if any(pattern in block.lower() for pattern in PROJECT_EVIDENCE_PATTERNS)][:6]


def _extract_delivery_evidence(blocks: List[str]) -> List[str]:
    keywords = ("上线", "落地", "交付", "迭代", "推动", "发布", "搭建")
    return [block for block in blocks if any(keyword in block for keyword in keywords)][:5]


def _extract_metrics_evidence(blocks: List[str]) -> List[str]:
    return [block for block in blocks if any(pattern.lower() in block.lower() for pattern in METRIC_PATTERNS)][:5]


def _extract_technical_evidence(blocks: List[str]) -> List[str]:
    return [block for block in blocks if any(pattern.lower() in block.lower() for pattern in TECH_PATTERNS)][:5]


def _extract_collaboration_evidence(blocks: List[str]) -> List[str]:
    return [block for block in blocks if any(pattern in block for pattern in COLLAB_PATTERNS)][:5]


def _build_missing_evidence(
    *,
    ai_experience_level: str,
    delivery_evidence: List[str],
    metrics_evidence: List[str],
    technical_evidence: List[str],
    domain_experience: List[str],
) -> Dict[str, List[str]]:
    missing = {
        "ai_landing_gap": [],
        "metric_gap": [],
        "domain_gap": [],
        "technical_gap": [],
    }
    if ai_experience_level in {"none", "weak"}:
        missing["ai_landing_gap"].append("简历中缺少明确的 AI 产品落地证据。")
    if not metrics_evidence:
        missing["metric_gap"].append("简历里缺少可量化的结果或指标证据。")
    if not domain_experience:
        missing["domain_gap"].append("简历里缺少稳定的领域背景信号。")
    if not technical_evidence:
        missing["technical_gap"].append("简历里缺少技术理解或工具使用证据。")
    if not delivery_evidence:
        missing["ai_landing_gap"].append("简历里缺少完整交付或上线证据。")
    return missing


def build_candidate_analysis(resume_text: str) -> Dict[str, object]:
    text = _normalize_spaces(resume_text)
    blocks = _split_blocks(text)
    project_evidence = _extract_project_evidence(blocks)
    delivery_evidence = _extract_delivery_evidence(blocks)
    metrics_evidence = _extract_metrics_evidence(blocks)
    technical_evidence = _extract_technical_evidence(blocks)
    collaboration_evidence = _extract_collaboration_evidence(blocks)
    domain_experience = _extract_domain_experience(text)
    ai_experience_level = _infer_ai_experience_level(text, project_evidence, technical_evidence)

    return {
        "candidate_profile": {
            "experience_years": _extract_experience_years(text),
            "domain_experience": domain_experience,
            "ai_experience_level": ai_experience_level,
            "product_background": _infer_product_background(text),
        },
        "candidate_evidence": {
            "project_evidence": project_evidence,
            "delivery_evidence": delivery_evidence,
            "metrics_evidence": metrics_evidence,
            "technical_evidence": technical_evidence,
            "collaboration_evidence": collaboration_evidence,
        },
        "missing_evidence": _build_missing_evidence(
            ai_experience_level=ai_experience_level,
            delivery_evidence=delivery_evidence,
            metrics_evidence=metrics_evidence,
            technical_evidence=technical_evidence,
            domain_experience=domain_experience,
        ),
    }

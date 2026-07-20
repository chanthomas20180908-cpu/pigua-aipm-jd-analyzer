"""目的：把评估失败归因转成下一轮约束。

定义：Evaluator 和 Generator 之间的轻量反思器。

范围包括：
- 聚合失败原因、去重、生成可执行 prompt 约束。

范围不包括：
- 不调用 LLM，不修改源码，不替代人工 review。

使用与修改规则：
- 约束应具体可检查，避免空泛鼓励式措辞。
"""

from __future__ import annotations

from app.iteration.models import TrialResult


class Reflector:
    def reflect(self, trial: TrialResult) -> list[str]:
        constraints: list[str] = []
        for reason in trial.failure_reasons:
            constraints.append(self._constraint_from_reason(reason))
        for case in trial.case_results:
            for tag in case.metrics.get("failure_tags", []):
                constraints.append(self._constraint_from_reason(str(tag)))
            if case.suggested_change:
                constraints.append(case.suggested_change)
        return _dedupe([item for item in constraints if item])

    def _constraint_from_reason(self, reason: str) -> str:
        normalized_reason = reason.lower()
        if (
            "llmenhancementerror" in normalized_reason
            or "jsondecodeerror" in normalized_reason
            or "failed to parse llm json response" in normalized_reason
            or "did not contain a json object" in normalized_reason
        ):
            return "输出必须是单个可解析 JSON 对象；不要输出 markdown 代码块、解释文本、前后缀说明或多个 JSON 片段。"
        if "value_stream_naming" in reason:
            return "value_stream_name 使用稳定业务名称，不要写成“从A到B”的流程摘要句。"
        if "missing_ai_transformation_layer" in reason:
            return "涉及 AI 改造岗位时，补出 AI 改造方案、改造建模结果等中间层实体，不要只停留在业务流程和产品方案。"
        if "missing_technical_entity" in reason:
            return "AI 平台类 JD 必须拆出知识库、问答、Agent、工作流、模型服务或 API 等具体平台对象。"
        if "missing_expected_capability" in reason:
            return "能力层要补出岗位真正区分度能力，例如 AI 改造分析、AI 业务改造建模，而不是只给通用产品能力。"
        if "missing_work_item" in reason:
            return "把 JD 里明确出现但当前缺失的阶段补成独立工作事项，尤其是规划、交付推进、验收测试等闭环环节。"
        if "missing_business_entity" in reason:
            return "为缺失的关键阶段补出可操作实体，例如开发进度、验收结果、产品规划、落地计划等。"
        if "missing_capability" in reason:
            return "能力模型要补齐缺失阶段对应的稳定能力，不要让规划、交付或验收环节只有工作事项没有能力支撑。"
        if "abstract_entity" in reason:
            return (
                "禁止输出抽象总称实体/工作事项：不要写“平台能力定义”“后台配置能力”“抽象可复用平台能力”"
                "“AI能力边界”等抽象层名词；必须替换成可操作平台对象，例如知识库、智能问答、"
                "Agent编排、工作流、模型服务、平台API。"
            )
        if "coarse_entity_granularity" in reason:
            return "实体粒度继续下钻到岗位真实操作对象，不要把多个平台模块糊成一个抽象总称。"
        if "capability_overlap" in reason or "over_fragmented_capability" in reason:
            return "合并高度重叠的能力项，避免把同一类平台产品设计能力拆成多个近义能力。"
        if "unsupported_inference" in reason:
            return "不要把 JD 没明确支持的专业职责强行扩成独立能力，推断要收敛。"
        if "incomplete_value_stream" in reason:
            return "value stream 的 purpose、工作事项和实体要闭环对齐，不能只在 purpose 里写完整生命周期。"
        if "overly_broad_work_item" in reason:
            return "把过宽的工作事项拆开，至少区分问题定义、方案设计、推进落地或验收等不同阶段。"
        if "explicit evidence ratio" in reason:
            return "每个主要实体优先引用 JD 原文片段；无直接证据时减少 inferred 项数量。"
        if "references missing work_item" in reason:
            return "value_streams.work_item_ids 只能引用 work_items 中真实存在的 id。"
        if "references missing entity" in reason:
            return "entity_operations 和 capabilities.primary_entity_ids 只能引用 bussiness_entitys 中真实存在的 id。"
        if "references missing capability" in reason:
            return "work_items.capability_ids 只能引用 capabilities 中真实存在的 id。"
        if "work_items count" in reason:
            return "至少拆出 3 个有输入输出、可判断完成的动宾结构工作事项。"
        if "value_streams count" in reason:
            return "至少识别 1 条端到端业务价值流，且不要把单个动作当作价值流。"
        return reason


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result

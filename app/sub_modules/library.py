"""目的：v4 子模块库。

定义：注册 v4 主链路所有 LLM 子模块的 prompt、schema 和 user prompt 构造逻辑。

范围包括：
- element_modeling、jd_core_judgment、quality_check、narration 等子模块定义。

范围不包括：
- 不写 FastAPI 路由，不写前端渲染。

使用与修改规则：
- 新增字段要同步前端 field-labels 和相关 docs。
"""

from __future__ import annotations

import json
from typing import Any, Dict

from app.sub_modules import SubModule

# ============================================================================
# 内联定义（自包含，不再引用 prompts_v3.py）
# ============================================================================

ELEMENT_MODELING_SYSTEM_PROMPT = (
    "你是资深 AI PM 岗位分析专家与业务架构师，熟悉 TOGAF 业务架构、ArchiMate 业务层建模。"
    "业务流程分析和 AI 产品生命周期。基于 JD 原文分析该岗位入职后负责的业务工作流程，输出结构化判断。"
    "只基于原文，不编造。输出必须是合法 JSON，不要 markdown、不要解释、不要注释。"
)

# [loop] variant-01-evidence: offline prompt suffix promoted inside run worktree.
ELEMENT_MODELING_SYSTEM_PROMPT = ELEMENT_MODELING_SYSTEM_PROMPT + '\n## 迭代约束\n以下约束来自上一轮失败归因，必须优先满足：\n- 涉及 AI 改造岗位时，补出 AI 改造方案、改造建模结果等中间层实体，不要只停留在业务流程和产品方案。\n- 禁止输出抽象总称实体/工作事项：不要写“平台能力定义”“后台配置能力”“抽象可复用平台能力”“AI能力边界”等抽象层名词；必须替换成可操作平台对象，例如知识库、智能问答、Agent编排、工作流、模型服务、平台API。\n- 实体粒度继续下钻到岗位真实操作对象，不要把多个平台模块糊成一个抽象总称。\n- value_stream_name 使用稳定业务名称，不要写成“从A到B”的流程摘要句。\n- AI 平台类 JD 必须拆出知识库、问答、Agent、工作流、模型服务或 API 等具体平台对象。\n- source_evidence 必须优先截取 JD 原文短句，不能用总结性改写替代证据。'


# [loop] variant-02-evidence: offline prompt suffix promoted inside run worktree.
ELEMENT_MODELING_SYSTEM_PROMPT = ELEMENT_MODELING_SYSTEM_PROMPT + '\n## 迭代约束\n以下约束来自上一轮失败归因，必须优先满足：\n- 禁止输出抽象总称实体/工作事项：不要写“平台能力定义”“后台配置能力”“抽象可复用平台能力”“AI能力边界”等抽象层名词；必须替换成可操作平台对象，例如知识库、智能问答、Agent编排、工作流、模型服务、平台API。\n- 实体粒度继续下钻到岗位真实操作对象，不要把多个平台模块糊成一个抽象总称。\n- value_stream_name 使用稳定业务名称，不要写成“从A到B”的流程摘要句。\n- source_evidence 必须优先截取 JD 原文短句，不能用总结性改写替代证据。'
ELEMENT_MODELING_OUTPUT_SCHEMA = """
{
  "value_streams": [
    {
      "id": "VS1",
      "value_stream_name": "",
      "purpose": "",
      "work_item_ids": [],
      "source_evidence": [],
      "evidence_type": "explicit|inferred",
      "confidence": 0.0
    }
  ],
  "work_items": [
    {
      "id": "WI1",
      "work_item_name": "",
      "purpose": "",
      "source_evidence": [],
      "evidence_type": "explicit|inferred",
      "entity_operations": [
        {
          "entity_id": "ENJ1",
          "operation": "create|read|update|delete",
          "operation_description": ""
        }
      ],
      "capability_ids": [],
      "confidence": 0.0
    }
  ],
  "bussiness_entitys": [
    {
      "id": "ENJ1",
      "entity_name": "",
      "entity_domain": "business|product|data_knowledge|ai_capability|software_system|runtime_delivery|governance_constraint",
      "entity_type": "",
      "parent_entity_id": null,
      "source_evidence": [],
      "evidence_type": "explicit|inferred",
      "confidence": 0.0
    }
  ],
  "capabilities": [
    {
      "id": "CAP1",
      "capability_name": "",
      "definition": "",
      "primary_entity_ids": [],
      "supported_work_item_ids": [],
      "source_evidence": [],
      "evidence_type": "explicit|inferred",
      "confidence": 0.0
    }
  ]
}
"""

_FINAL_OUTPUT_SCHEMA = """{
  "conclusion_label": "保熟|生瓜蛋子|秤有问题|萨日朗",
  "summary": "约120-200字：清醒搭子式JD短评。用两个空行自然分成2-3个短段，不使用标题或列表；让候选人只读这段话也能理解岗位招什么人、实际做什么、最该确认什么。"
}"""


def _build_element_modeling_user_prompt(jd_text: str) -> str:
    return (
        "请分析下面的 JD 原文，输出一个严格可解析的 JSON 业务实体。字段名必须使用英文，字段值必须使用中文。\n\n"

        "## 分析目的\n"
        "识别该岗位入职后实际参与的业务价值流、需要执行的工作事项、工作事项操作的业务实体，以及完成工作事项所需要的业务能力。\n"
        "本阶段只建立岗位业务模型，不分析候选人，不进行简历匹配，也不提取学历、工作年限、性格要求等任职条件。\n\n"

        "## 你的角色\n"
        "你是一名熟悉 TOGAF 业务架构、ArchiMate 业务层建模、业务流程分析和 AI 产品生命周期的业务架构师。\n"
        "本任务分析的是岗位入职后实际负责的业务工作，不是企业招聘流程。\n\n"

        "## MVP 建模结构\n"
        "本次分析只输出以下四类实体：\n"
        "1. 业务价值流 Value Stream\n"
        "2. 工作事项 Work Item\n"
        "3. 业务实体 Business Entity\n"
        "4. 业务能力 Business Capability\n\n"

        "只建立以下核心关系：\n"
        "- 业务价值流包含工作事项。\n"
        "- 工作事项对业务实体执行 Create、Read、Update、Delete 操作。\n"
        "- 工作事项需要一个或多个业务能力。\n\n"

        "不要额外输出业务流程、子流程、任务、角色、任职要求、公司信息、薪酬信息或风险分析。\n\n"

        "## 一、业务价值流 Value Stream\n"
        "业务价值流是岗位参与创造业务价值的一条端到端工作链，描述业务问题或需求从产生，到形成产品、项目交付、上线运营或持续优化的过程。\n\n"

        "价值流示例：\n"
        "- AI场景从发现到上线运营\n"
        "- 客户需求从识别到解决方案交付\n"
        "- Agent从方案设计到持续优化\n"
        "- AI产品从需求分析到生产落地\n\n"

        "价值流不是单个工作动作，也不是岗位名称、能力名称、工具名称或技术名称。\n\n"

        "每条价值流必须至少包含：\n"
        "- value_stream_name：价值流名称。\n"
        "- purpose：价值流为什么存在、解决什么业务问题。\n"
        "- work_item_ids：该价值流包含的工作事项ID，按照实际执行顺序排列。\n"
        "- source_evidence：支持该价值流判断的JD原文片段。\n"
        "- evidence_type：explicit或inferred。\n"
        "- confidence：0到1之间的小数。\n\n"

        "## 二、工作事项 Work Item\n"
        "工作事项是价值流中具有明确业务目的、能够被分配和执行、操作一个或多个业务实体，并且能够判断是否完成的一组连续工作。\n\n"

        "工作事项的粒度应位于完整业务活动和最小可执行任务之间。\n"
        "工作事项不能覆盖整条价值流，也不要拆成组织会议、发送消息、同步进度等过细动作。\n\n"

        "工作事项名称必须使用动宾结构。\n\n"

        "错误示例：\n"
        "- 负责需求分析\n"
        "- 推动项目上线\n"
        "- 熟悉Dify\n"

        "正确示例：\n"
        "- 收集客户需求\n"
        "- 分析业务需求\n"
        "- 设计Agent解决方案\n"

        "工作事项不能只是删除JD原文中的“负责、参与、推动、协助”等词语，必须还原岗位实际执行的业务动作。\n\n"

        "一项内容至少满足以下三个条件，才可以识别为独立工作事项：\n"
        "- 具有明确业务目的。\n"
        "- 操作一个或多个业务实体。\n"
        "- 有可识别的输入或输出。\n"
        "- 可以独立判断是否完成。\n"
        "- 与其他工作事项存在明确前后依赖。\n"
        "- JD中存在直接证据或强逻辑支持。\n\n"

        "每个工作事项必须包含：\n"
        "- work_item_name：标准化后的动宾结构名称。\n"
        "- purpose：该工作事项解决什么具体问题。\n"
        "- source_evidence：支持该工作事项的JD原文。\n"
        "- evidence_type：explicit或inferred。\n"
        "- entity_operations：该工作事项对业务实体执行的操作。\n"
        "- capability_ids：完成该工作事项需要的业务能力ID。\n"
        "- confidence：0到1之间的小数。\n\n"

        "## 三、业务实体 Business Entity\n"
        "业务实体是工作事项读取、创建、更新、删除或管理的业务、产品、数据、AI、软件、运行或治理业务实体。\n\n"

        "业务实体不是工作动作，也不是能力名称。\n\n"

        "业务实体按照 entity_domain 分为以下七类：\n\n"

        "1. business：业务类实体。\n"
        "例如业务场景、业务流程、业务规则、业务需求、业务目标、业务指标、业务风险。\n\n"

        "2. product：产品类实体。\n"
        "例如用户角色、用户场景、产品需求、产品功能、产品流程、产品策略、产品版本、产品指标。\n\n"

        "3. data_knowledge：数据与知识对类实体。\n"
        "例如原始数据、标注数据、训练数据、评测数据、用户反馈数据、知识、知识库、数据标注规则。\n\n"

        "4. ai_capability：AI能力类实体。\n"
        "例如模型、Prompt、上下文、Agent、Agent工作流、意图体系、对话状态、工具调用规则、检索机制、记忆机制、AI评测体系、模型路由策略。\n\n"

        "5. software_system：软件与系统类实体。\n"
        "例如系统、应用、服务、模块、API、数据库、代码、系统配置、权限、技术架构。\n\n"

        "6. runtime_delivery：运行与交付类实体。\n"
        "例如项目、产品迭代、研发任务、测试用例、缺陷、发布版本、部署实例、运行日志、告警、运营策略。\n\n"

        "7. governance_constraint：治理与约束类实体。\n"
        "例如标准、规范、SOP、合规要求、安全策略、验收标准、质量标准、人工接管规则。\n\n"

        "每个业务实体必须包含：\n"
        "- entity_name：稳定、可复用的业务实体名称。\n"
        "- entity_domain：从business、product、data_knowledge、ai_capability、software_system、runtime_delivery、governance_constraint中选择一个。\n"
        "- entity_type：业务实体的具体语义类型，例如业务需求、Agent工作流、评测数据、发布版本。\n"
        "- parent_entity_id：如果存在明确上级业务实体，填写上级业务实体ID；否则为null。\n"
        "- source_evidence：支持该业务实体存在的JD原文片段。\n"
        "- evidence_type：explicit或inferred。\n"
        "- confidence：0到1之间的小数。\n\n"

        "业务实体名称应描述业务实体本身是什么，不使用完整句子，不使用“方案、报告、计划”等只有表达形式、没有明确业务语义的宽泛名称。\n\n"

        "错误示例：\n"
        "- 报告\n"
        "- 方案\n"
        "- 计划\n"
        "- 数据\n"
        "- 配置\n\n"

        "优先改写为：\n"
        "- Agent评测结果\n"
        "- Agent解决方案\n"
        "- 项目实施安排\n"
        "- Agent运行数据\n"
        "- Agent工作流配置\n\n"

        "如果JD信息不足以细分业务实体，可以使用上层业务实体，例如“需求”“评测数据”“业务规则”，不要凭行业常识无限细分。\n\n"

        "## 四、CRUD 操作关系\n"
        "CRUD不是独立实体，而是工作事项与业务实体之间的关系。\n\n"

        "操作类型仅允许：\n"
        "- create：创建新的业务实体。\n"
        "- read：读取、查询、分析或使用已有业务实体。\n"
        "- update：修改、补充、优化或维护已有业务实体。\n"
        "- delete：删除、关闭、废弃、归档或淘汰业务实体。\n\n"

        "不是每个工作事项都必须包含四种操作。\n"
        "没有明确证据或合理依据时，不得为了凑齐CRUD而虚构delete或其他操作。\n\n"

        "例如：\n"
        "分析业务需求：\n"
        "- read 原始需求\n"
        "- read 业务流程\n"
        "- read 业务规则\n"
        "- create 业务需求\n\n"

        "优化Agent工作流：\n"
        "- read Agent运行数据\n"
        "- read Bad Case\n"
        "- update Agent工作流\n\n"

        "entity_operations中的每条关系必须引用已经存在的work_entity_id。\n\n"

        "## 五、业务能力 Business Capability\n"
        "业务能力表示一个角色能够稳定完成某类工作事项，并管理一类业务实体所需要的能力。\n\n"

        "业务能力不是工具名称、岗位名称、性格描述或一次性的工作动作。\n\n"

        "错误示例：\n"
        "- 熟悉Dify\n"
        "- 沟通能力强\n"
        "- 责任心强\n"

        "正确示例：\n"
        "- 业务场景分析能力\n"
        "- 需求分析能力\n"
        "- 产品流程设计能力\n"

        "只有现有能力词典无法表达JD中的明确工作能力时，才允许创建新的能力名称。\n"
        "新能力名称必须满足：\n"
        "- 能够支撑至少一个工作事项。\n"
        "- 能够管理至少一类业务实体。\n"
        "- 使用“业务实体或业务领域 + 管理、分析、设计、规划、评测、交付等能力”的命名方式。\n"
        "- 不得只是工具熟练度或抽象性格词。\n\n"

        "每个业务能力必须包含：\n"
        "- capability_name：标准化能力名称。\n"
        "- definition：稳定完成什么类型的工作事项、管理什么类型的业务实体。\n"
        "- primary_entity_ids：该能力主要管理的业务实体ID。\n"
        "- supported_work_item_ids：该能力支撑的工作事项ID。\n"
        "- source_evidence：支持该能力判断的JD原文片段。\n"
        "- evidence_type：explicit或inferred。\n"
        "- confidence：0到1之间的小数。\n\n"

        "## 分析步骤\n"
        "请严格按照以下步骤完成分析，但不要输出中间推理过程。\n\n"

        "### 步骤1：提取职责事实\n"
        "逐条读取JD，提取其中明确出现的动作、业务实体、业务场景、生命周期阶段和交付结果。\n"
        "先提取事实，不要立即生成价值流或能力结论。\n\n"

        "### 步骤2：标准化工作事项\n"
        "将招聘语言转换为标准工作事项。\n\n"

        "例如：\n"
        "“负责客户需求洞察与对接”可以根据证据转换为：\n"
        "- 收集客户需求\n"
        "- 分析业务需求\n"
        "- 确认需求范围\n\n"

        "“推动项目实施”可以根据证据转换为：\n"
        "- 制定项目实施安排\n"
        "- 协调研发与测试资源\n"
        "- 跟踪项目交付进度\n"
        "- 处理项目实施问题\n\n"

        "不得只对原文进行同义词替换，也不得补出JD完全没有支持的工作事项。\n\n"

        "### 步骤3：识别业务实体及CRUD\n"
        "针对每个工作事项，判断：\n"
        "- 开始前需要读取什么业务实体。\n"
        "- 完成后创建什么业务实体。\n"
        "- 需要更新或优化什么已有业务实体。\n"
        "- 是否存在明确需要关闭、废弃或归档的业务实体。\n\n"

        "先生成业务实体，再通过entity_id建立CRUD关系。\n\n"

        "### 步骤4：识别业务能力\n"
        "根据工作事项及其CRUD业务实体，判断稳定完成该类工作需要什么业务能力。\n"
        "优先从能力词典中选择标准能力。\n"
        "一个工作事项可以需要多个能力，一个能力也可以支撑多个工作事项。\n\n"

        "### 步骤5：归并价值流\n"
        "根据工作事项的业务目标、输入输出和生命周期关系，将其归入一条或多条价值流。\n"
        "价值流中的work_item_ids必须按照实际执行顺序排列。\n\n"

        "可以参考以下AI产品生命周期，但不得机械套用：\n"
        "场景探索 → 需求分析 → 产品方案设计 → 数据与知识准备 → AI能力建设 → AI效果评测 → 开发测试 → 上线交付 → 运营监控 → 持续优化。\n\n"

        "只输出JD具有明确证据或强逻辑支持的价值流和工作事项。\n\n"

        "### 步骤6：事实与推断标记\n"
        "每条价值流、工作事项、业务实体和业务能力必须标记：\n"
        "- explicit：JD原文明确表达。\n"
        "- inferred：根据上下游关系进行的谨慎推断。\n\n"

        "推断内容必须保留source_evidence，并适当降低confidence。\n"
        "不得把合理推断伪装成JD明确事实。\n\n"

        "### 步骤7：质量自检\n"
        "输出前必须检查：\n"
        "1. 是否错误分析成招聘流程。\n"
        "2. work_item_name是否使用了“负责、参与、推动、协助”等招聘措辞。\n"
        "3. 是否存在只有抽象名词、没有业务动作的工作事项。\n"
        "4. 每个工作事项是否至少关联一个业务实体。\n"
        "5. 是否把工具、技术名称、岗位名称或性格描述识别为工作事项。\n"
        "6. 是否把工具名称直接识别为业务能力。\n"
        "7. 每个业务实体是否正确归入一个entity_domain。\n"
        "8. 是否把报告、方案、计划等表达形式直接作为宽泛业务实体类型。\n"
        "9. 每项CRUD关系是否引用存在的业务实体ID。\n"
        "10. 是否为了凑齐CRUD而虚构delete操作。\n"
        "11. 每个业务能力是否支撑至少一个工作事项。\n"
        "12. 每个业务能力是否关联至少一个主要业务实体。\n"
        "13. 是否生成了大量含义重复的能力名称。\n"
        "14. 每条价值流中的工作事项顺序是否符合输入输出关系。\n"
        "15. 所有ID引用是否存在，是否存在重复ID或孤立节点。\n"
        "16. JSON是否可以被程序正常解析。\n\n"

        "## 输出要求\n"
        "只输出严格符合以下结构的JSON。\n"
        "不要在JSON前后输出解释、标题、Markdown代码块或其他自然语言。\n\n"

        "JSON结构如下：\n"
        f"{ELEMENT_MODELING_OUTPUT_SCHEMA}\n\n"

        "## 禁止行为\n"
        "- 禁止输出招聘流程。\n"
        "- 禁止输出任职条件、学历、工作年限、性格要求或简历匹配结果。\n"
        "- 禁止work_item_name使用“负责”“参与”“推动”“协助”。\n"
        "- 禁止把Dify、Coze、LangChain、Python等工具或技术直接作为工作事项。\n"
        "- 禁止把工具熟练度、沟通能力、抗压能力等直接作为业务能力。\n"
        "- 禁止为了形成完整AI生命周期而虚构JD没有支持的工作事项。\n"
        "- 禁止为了凑齐CRUD而虚构删除操作。\n"
        "- 禁止生成未被任何工作事项引用的孤立能力。\n"
        "- 禁止生成未被任何CRUD关系引用的孤立业务实体。\n"
        "- 禁止引用不存在的ID。\n\n"

        f"## 原始JD文本\n{jd_text}"
    )


# ============================================================================
# 模块一：建模分析
# ============================================================================

# --- 模块 1.1：元素建模 ---

ELEMENT_MODELING_V1 = SubModule(
    name="element_modeling",
    version="v1",
    system_prompt=ELEMENT_MODELING_SYSTEM_PROMPT,
    output_schema=json.loads(ELEMENT_MODELING_OUTPUT_SCHEMA),
    build_user_prompt=lambda context: _build_element_modeling_user_prompt(context["jd_text"]),
)

# --- 模块 1.2：岗位建模结果判断 ---

JD_JUDGMENT_OUTPUT_SCHEMA = """{
  "core_judgment": "≤250字：客观的岗位核心判断。包括岗位实际主要负责什么、业务链路是否清楚、职责和能力要求是否合理、最重要的亮点或风险。不玩梗。",
  "job_focus": ["岗位入职后实际主要负责的工作，每条≤30字"],
  "strengths": ["2-4条，岗位亮点，必须引用具体价值流、工作事项、业务实体、业务能力或任职要求，每条≤50字"],
  "risks": ["2-4条，岗位风险，区分明确风险和待确认事项，每条≤50字"],
  "key_findings": [
    {
      "type": "business_value|responsibility_scope|process_completeness|capability_alignment|requirement_alignment|technical_alignment|role_overload|context_missing|hidden_responsibility|other",
      "target": "≤30字：判断针对的具体对象",
      "finding": "≤80字：客观判断结果",
      "evidence": ["支持判断的价值流、工作事项、业务实体、能力、任职要求"],
      "certainty": "explicit|inferred"
    }
  ],
  "interview_questions": ["2-4条需要在面试中确认的问题，每条针对JD中的具体信息缺口或风险"]
}"""

JD_JUDGMENT_V1_SYSTEM_PROMPT = (
    "你是资深 AI PM 岗位分析专家与业务架构师，熟悉 TOGAF 业务架构、ArchiMate 业务层建模。"
    "基于 JD 业务建模结果，对岗位本身进行结构化分析与判断。保持理性、克制、可追溯，不玩梗，"
    "不使用情绪化表达。输出必须是合法 JSON，不要 markdown、不要解释、不要注释。"
)


def _build_jd_judgment_user_prompt(context: Dict[str, Any]) -> str:
    em = context.get("element_modeling", {})
    payload = {
        "value_streams": em.get("value_streams", []),
        "work_items": em.get("work_items", []),
        "business_entities": em.get("bussiness_entitys", []),
        "capabilities": em.get("capabilities", []),
        "qualification_requirements": em.get("qualification_requirements", []),
    }
    return (
        "请基于下面提供的JD业务建模结果，对岗位本身进行结构化分析与判断。\n"
        "输出必须是严格合法、可直接解析的JSON。不要输出Markdown、解释、注释或JSON以外的任何内容。\n\n"
        "本任务只分析岗位JD本身，包括岗位实际负责的业务工作、业务价值、职责边界、业务能力、任职要求和潜在风险。\n"

        "## 输入信息说明\n"
        "输入可能包含以下内容：\n"
        "- value_streams：岗位参与的业务价值流。\n"
        "- work_items：岗位实际执行的工作事项。\n"
        "- business_entities：工作事项创建、读取、更新或删除的业务实体。\n"
        "- capabilities：完成工作事项需要的业务能力。\n"
        "- qualification_requirements：招聘方提出的任职要求。\n\n"

        "## 输出结构\n"
        "严格符合以下JSON结构，字段名使用英文，字段值使用中文：\n"
        "```json\n"
        f"{JD_JUDGMENT_OUTPUT_SCHEMA}\n"
        "```\n\n"

        "## 核心判断目标\n"
        "请围绕以下目标完成全部分析：\n\n"

        "### 1. 岗位核心工作判断\n"
        "- 判断岗位入职后实际主要负责什么。\n"
        "- 概括岗位承担的核心价值流和关键工作事项。\n"
        "- 判断岗位主要偏向业务分析、产品设计、AI能力建设、项目交付、运营优化或多种职责混合。\n"
        "- 不得只复述岗位名称或JD标题。\n\n"

        "### 2. 业务价值判断\n"
        "- 判断岗位是否对应真实、明确且有业务价值的工作链路。\n"
        "- 判断价值流是否有明确的起点、过程和业务结果。\n"
        "- 判断工作是否直接解决业务问题，还是主要停留在概念研究、内部协调或技术包装层面。\n"
        "- 判断岗位工作是否接触真实业务场景、业务实体、用户问题或生产交付。\n\n"

        "### 3. 工作事项清晰度判断\n"
        "- 判断work_items是否具体，能否看清岗位入职后实际需要完成什么工作。\n"
        "- 判断工作事项是否具有明确对象、产出或完成标准。\n"
        "- 识别大量使用“负责、推动、协同、赋能、跟进”等措辞，但缺少实际动作和业务实体的情况。\n"
        "- 判断JD是否只描述责任范围，却没有说明具体交付内容。\n\n"

        "### 4. 业务链路完整性判断\n"
        "- 判断价值流中的工作事项是否能够形成合理的前后顺序。\n"
        "- 判断输入、业务实体CRUD和输出是否能够连接起来。\n"
        "- 判断关键生命周期是否存在明显断点。\n"
        "- 对AI产品岗位，重点关注场景识别、需求分析、方案设计、数据与知识准备、AI能力建设、效果评测、开发测试、上线交付、运营监控和持续优化。\n"
        "- 不得因为JD没有写全，就直接认定企业不存在相关环节；应区分明确缺失与信息未披露。\n\n"

        "### 5. 业务实体合理性判断\n"
        "- 判断工作事项是否操作了明确的business_entities。\n"
        "- 判断业务实体是否能够反映岗位真实管理的业务内容，而不是只有方案、报告、计划等宽泛表达形式。\n"
        "- 判断业务实体的粒度是否稳定，是否存在过度抽象或过度拆分。\n"
        "- 判断岗位是否真正管理需求、产品、数据、模型、Agent、评测、版本、部署、运营等核心实体。\n\n"

        "### 6. 业务能力合理性判断\n"
        "- 判断capabilities是否能够由工作事项和业务实体共同支撑。\n"
        "- 判断能力是否是稳定完成一类工作的能力，而不是工具名称、技术名词、性格描述或一次性动作。\n"
        "- 判断能力要求是否与岗位实际职责一致。\n"
        "- 判断岗位是否要求过多相互跨度很大的能力域。\n"
        "- 识别产品、算法、研发、测试、项目、交付、运营等多类能力集中到一个岗位的情况。\n\n"

        "### 7. 职责边界与角色负载判断\n"
        "- 判断岗位承担的职责范围是否合理。\n"
        "- 判断一个岗位是否覆盖过多价值流、角色或生命周期阶段。\n"
        "- 判断岗位是对结果负责，还是只承担协调、推动和信息传递。\n"
        "- 判断JD是否要求岗位承担责任，但没有说明相应决策权限、团队资源或协作支持。\n"
        "- 判断岗位名称和实际承担角色是否一致。\n\n"

        "### 8. 任职要求映射判断\n"
        "- 判断qualification_requirements是否能够映射到价值流、工作事项、业务能力、角色或工作环境。\n"
        "- 判断工作经验、行业经验、专业知识、工具要求和技术要求是否与实际工作内容一致。\n"
        "- 识别无法映射到任何业务工作的悬空要求。\n"
        "- 判断某项要求是直接任务证据、能力前提、执行保障条件，还是单纯招聘准入门槛。\n"
        "- 不得因为要求没有直接对应活动，就立即认定要求不合理，应考虑其是否属于间接知识或协作前提。\n\n"

        "### 9. 技术要求与岗位工作的匹配判断\n"
        "- 判断模型、Prompt、Agent、RAG、数据、代码、部署、算力、性能优化等技术要求，是否能在工作事项中找到对应职责。\n"
        "- 判断技术要求是需要亲自设计和执行，还是只需理解、协作或进行产品判断。\n"
        "- 识别技术要求明显高于岗位实际职责，或热门技术名词大量堆叠的情况。\n"
        "- 判断岗位是否将产品经理包装成算法、研发或运维的替代角色。\n\n"

        "### 10. 工作环境与隐性责任判断\n"
        "- 根据项目并发、客户交付、跨团队协作、驻场、出差、短周期交付等信息，判断岗位的实际工作环境。\n"
        "- 识别“抗压、沟通、主人翁意识”等主观要求背后可能对应的工作条件。\n"
        "- 判断是否存在JD没有直接说明，但可由职责和要求共同推断出的隐性责任。\n"
        "- 推断必须保持谨慎，并明确标记为待确认，不得写成确定事实。\n\n"

        "### 11. 岗位信息完整度判断\n"
        "- 判断JD是否说明了团队配置、汇报关系、协作角色、决策权限、交付目标、效果指标和验收标准。\n"
        "- 判断求职者能否从JD中理解入职前三个月可能承担的工作。\n"
        "- 对没有说明的信息，应识别为context_missing，而不是直接作为负面事实。\n\n"

        "### 12. 综合结论判断\n"
        "- 基于以上分析，形成一段客观、直接的岗位判断。\n"
        "- 判断该岗位最值得关注的亮点是什么。\n"
        "- 判断最主要的风险是什么。\n"
        "- 判断最需要求职者在面试中确认的信息是什么。\n"

        "## core_judgment规则\n"
        "core_judgment是一段客观的岗位核心判断，不超过250字。\n"
        "内容应包括：\n"
        "- 岗位实际主要负责什么。\n"
        "- 岗位业务链路是否清楚。\n"
        "- 职责和能力要求是否合理。\n"
        "- 最重要的亮点或风险。\n\n"
        "不得玩梗，不得使用夸张、刻薄或情绪化表达。\n\n"

        "## strengths规则\n"
        "strengths输出2到4条，每条不超过50字。\n"
        "必须引用具体价值流、工作事项、业务实体、业务能力或任职要求。\n"
        "不得使用“行业前景好”“能学到很多”“发展空间大”等空泛描述。\n\n"

        "## risks规则\n"
        "risks输出2到4条，每条不超过50字。\n"
        "风险可以来自：\n"
        "- 职责过宽或角色过载。\n"
        "- 工作事项空泛。\n"
        "- 缺少明确业务实体或业务结果。\n"
        "- 任职要求与实际工作不一致。\n"
        "- 技术要求过高或与职责脱节。\n"
        "- 缺少团队、权限、指标或验收信息。\n"
        "- 概念堆砌或岗位名称与工作内容不一致。\n\n"
        "必须区分明确风险和待确认事项，不得将推断写成确定事实。\n\n"

        "## key_findings规则\n"
        "key_findings输出3到6条结构化判断。\n"
        "每条包含：\n"
        "- type：判断类型。\n"
        "- target：判断针对的具体对象。\n"
        "- finding：客观判断结果。\n"
        "- evidence：支持判断的价值流、工作事项、业务实体、能力、任职要求或JD原文。\n"
        "- certainty：explicit或inferred。\n\n"

        "type只能从以下值中选择：\n"
        "- business_value：业务价值判断。\n"
        "- responsibility_scope：职责范围判断。\n"
        "- process_completeness：业务链路完整性判断。\n"
        "- capability_alignment：能力与职责一致性判断。\n"
        "- requirement_alignment：任职要求映射判断。\n"
        "- technical_alignment：技术要求匹配判断。\n"
        "- role_overload：角色过载判断。\n"
        "- context_missing：信息缺失判断。\n"
        "- hidden_responsibility：隐性责任判断。\n"
        "- other：其他重要判断。\n\n"

        "## interview_questions规则\n"
        "interview_questions输出2到4条需要在面试中确认的问题。\n"
        "每条问题必须针对JD中的具体信息缺口或风险，例如：\n"
        "- 该岗位和算法、研发、运营团队的职责边界是什么？\n"
        "- Agent上线后的效果指标和验收标准是什么？\n"
        "- JD中的Python要求是需要亲自开发，还是用于原型验证？\n"
        "- 岗位入职前三个月最重要的交付目标是什么？\n\n"
        "不得输出“了解公司文化”“询问发展空间”等泛化问题。\n\n"

        "## 证据规则\n"
        "- 所有判断必须能够追溯到结构化建模结果。\n"
        "- evidence中优先使用具体节点名称。\n"
        "- 不得编造团队配置、公司阶段、业务规模、技术架构或实际工作强度。\n\n"

        "## 禁止行为\n"
        "- 禁止使用玩梗、比喻或口语化表达。\n"
        "- 禁止输出结论标签。\n"
        "- 禁止输出评分、分数、百分比或推荐等级。\n"
        "- 禁止分析候选人是否满足要求。\n"
        "- 禁止将结构化建模结果视为企业实际成熟度的证明。\n"
        "- 禁止把JD没有说明的信息写成确定事实。\n"
        "- 禁止输出JSON以外的任何内容。\n\n"

        "## 输入信息\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


JD_CORE_JUDGMENT_V1 = SubModule(
    name="jd_core_judgment",
    version="v1",
    system_prompt=JD_JUDGMENT_V1_SYSTEM_PROMPT,
    output_schema=json.loads(JD_JUDGMENT_OUTPUT_SCHEMA),
    build_user_prompt=_build_jd_judgment_user_prompt,
)

# ============================================================================
# 模块二：质检
# ============================================================================

QUALITY_CHECK_OUTPUT_SCHEMA = """{
  "risk_points": [
    {
      "target": "≤30字：风险针对的具体对象（价值流、工作事项、业务实体、能力或判断结论）",
      "description": "≤80字：具体说明这个风险点是什么，为什么可能出错",
      "severity": "high|medium|low"
    }
  ]
}"""

QUALITY_CHECK_V1_SYSTEM_PROMPT = (
    "你是资深 AI PM 岗位分析质检专家。基于模块一的建模结果和判断结果，"
    "检查其中可能存在的错误、遗漏或推断过度，输出 3 条潜在风险点。"
    "只找问题，不修正。输出必须是合法 JSON，不要 markdown、不要解释、不要注释。"
)


def _build_quality_check_user_prompt(context: Dict[str, Any]) -> str:
    return (
        "请检查以下建模结果和判断结果，找出 3 个潜在可能出错的风险点。\n"
        "输出必须是合法 JSON。\n\n"

        "## 检查方向\n"
        "- 建模结果中是否有JD原文不支持的元素。\n"
        "- 判断结论是否有推断过度或证据不足的情况。\n"
        "- 是否有明显遗漏或矛盾。\n\n"

        "## 输出结构\n"
        "```json\n"
        f"{QUALITY_CHECK_OUTPUT_SCHEMA}\n"
        "```\n\n"

        "## 字段规则\n"
        "- risk_points 必须恰好 3 条。\n"
        "- severity：high 表示影响岗位核心判断，medium 表示可能影响部分结论，low 表示小问题。\n"
        "- target：指向具体的价值流ID、工作事项ID、业务实体ID、能力ID 或判断结论中的字段名。\n"
        "- description：具体说明潜在问题，不确定时用“可能”“建议确认”等措辞。\n\n"

        "## 禁止行为\n"
        "- 禁止输出多于或少于 3 条。\n"
        "- 禁止重新建模或重新判断。\n"
        "- 禁止修正错误。\n"
        "- 禁止输出 JSON 以外的内容。\n\n"

        "## 输入信息\n"
        f"### 元素建模结果\n{json.dumps(context.get('element_modeling', {}), ensure_ascii=False, indent=2)}\n\n"
        f"### 岗位判断结果\n{json.dumps(context.get('jd_core_judgment', {}), ensure_ascii=False, indent=2)}"
    )


QUALITY_CHECK_V1 = SubModule(
    name="quality_check",
    version="v1",
    system_prompt=QUALITY_CHECK_V1_SYSTEM_PROMPT,
    output_schema=json.loads(QUALITY_CHECK_OUTPUT_SCHEMA),
    build_user_prompt=_build_quality_check_user_prompt,
)

# ============================================================================
# 模块三：口语化总结
# ============================================================================

NARRATION_V1_SYSTEM_PROMPT = (
    "你是求职者身边的清醒搭子：懂产品岗位，也会把招聘黑话翻译成人话。"
    "基于岗位分析结论，只输出一段有判断力、友好克制的 JD 解读总结。"
    "你的总结要让候选人不看下方结构化信息，也能明白这个岗位到底招什么人、实际要做什么、最该确认什么。"
    "面对信息缺口时，帮助候选人把焦虑变成可执行的确认问题；不恐吓、不贬低候选人，也不做情绪化吐槽。"
    "可以有一处自然、轻微的口语化特色，但不要堆网络梗、脏话或攻击性表达。"
    "只做表达转换，不重新分析。输出必须是合法 JSON，只包含 conclusion_label 和 summary 两个字段，不要 markdown、不要解释、不要注释。"
)


def _build_narration_user_prompt(context: Dict[str, Any]) -> str:
    payload = {
        "jd_core_judgment": context.get("jd_core_judgment", {}),
        "quality_check": context.get("quality_check", {}),
    }
    return (
        "请将下面提供的岗位分析结论，改写为一段适合直接展示给求职者的清醒搭子式 JD 解读。\n"
        "输出必须是严格合法、可直接解析的JSON。不要输出Markdown、解释、注释或JSON以外的任何内容。\n\n"

        "## 任务边界\n"
        "本任务只做表达转换，不再分析JD，不重新阅读业务逻辑，不补充新的判断。\n"
        "所有结论必须忠实来自输入的岗位分析结果。\n"
        "不得新增输入中没有出现的亮点、风险、任职门槛、信息缺口或面试问题。\n"
        "不得改变原分析结果的严重程度和判断方向。\n\n"

        "## 输入信息说明\n"
        "输入是模块一和模块二的输出，可能包含：\n"
        "- jd_core_judgment：岗位结构化判断（core_judgment、job_focus、strengths、risks、key_findings、interview_questions）。\n"
        "- quality_check：质检结果（risk_points，3条潜在风险点）。\n\n"

        "你只能对这些内容进行：\n"
        "- 压缩。\n"
        "- 重组。\n"
        "- 口语化。\n"
        "- 使用少量自然口语化表达。\n"
        "- 根据已有判断选择结论标签。\n\n"

        "你不能进行：\n"
        "- 新的业务分析。\n"
        "- 新的风险推断。\n"
        "- 新的事实判断。\n"
        "- 新的候选人匹配。\n"
        "- 新的投递推荐。\n\n"

        "## 输出结构\n"
        "严格符合以下JSON结构，字段名使用英文，字段值使用中文：\n"
        "```json\n"
        f"{_FINAL_OUTPUT_SCHEMA}\n"
        "```\n\n"
        "禁止输出任何其他字段、数组或额外说明。\n\n"

        "## conclusion_label标签规则\n"
        "conclusion_label必须从以下标签中选择一个：\n\n"

        "- 保熟：输入结论整体认为岗位业务真实、职责清楚、工作事项具体，要求和工作基本一致。\n"
        "- 生瓜蛋子：输入结论认为岗位方向较新，流程、组织配置或落地方式仍处在探索阶段。\n"
        "- 秤有问题：输入结论明确指出职责范围、任职要求或投入产出存在明显失衡。\n"
        "- 萨日朗：输入结论明确指出岗位存在严重不合理要求、明显用工风险或极端职责失控。\n\n"

        "标签只能根据输入结论选择，禁止重新分析原始JD。\n"
        "岗位仍处于新方向探索，但没有明显失衡时，可以选择生瓜蛋子。\n"
        "只有输入明确指出要求失衡时，才能选择秤有问题。\n"
        "只有输入明确指出严重风险时，才能选择萨日朗。\n"
        "不得为了玩梗使用比输入判断更严重的标签。\n\n"

        "## summary规则\n"
        "summary是一段约120-200字、由3-5句构成的自然短评。\n"
        "必须满足：\n"
        "- 开头先用一句大白话给出判断：这个岗位本质是什么、主要在找哪类人，值不值得候选人认真了解。\n"
        "- 接着说明岗位实际工作和最重要的亮点，避免照抄结构化字段或堆砌术语。\n"
        "- 最后自然带出一个最重要的信息缺口或风险，以及候选人在面试中可确认的动作。信息缺口要写成待确认事项，不要让候选人觉得自己不够格。\n"
        "- 用两个空行把内容自然分为2-3个短段：每段1-2句，按语义转折换行。不要使用“结论：”“岗位：”“风险：”等标题，不要列表。\n"
        "- conclusion_label只作为页面标签；正文不解释、不重复，也不套用华强买瓜梗。\n"
        "- 可从下列句式中至多自然化用一处，避免每篇都以相同句子开头：\n"
        "  - “先说结论，…”\n"
        "  - “说人话，这其实是个…”\n"
        "  - “别先被岗位名唬住，…”\n"
        "  - “这不代表你不够格，关键是…”\n"
        "  - “面试时把…问清楚，就能判断是否适合。”\n"
        "- 不得增加输入中没有出现的新结论。\n\n"

        "## 表达风格\n"
        "- 像懂岗位的朋友在帮候选人拆解信息：友好、直接、有判断力，但不居高临下。\n"
        "- 允许轻微、自然的口语化，不依赖网络梗制造特色。\n"
        "- 禁止脏话、攻击性表达、情绪化质问、恐吓式措辞和对候选人的负面评价。\n"
        "- 不要写成正式咨询报告，也不要写成泛泛的职业鸡汤。\n\n"

        "## 忠实改写规则\n"
        "- 输入说“信息不足”，输出只能表达为“还没讲清楚”或“需要面试确认”。\n"
        "- 输入说“可能存在角色过载”，输出不能改成“进去一定当牛马”。\n"
        "- 输入说“技术要求与职责部分脱节”，输出不能改成“JD纯属诈骗”。\n"
        "- 输入没有提到硬性条件，不得虚构任职要求。\n\n"

        "## 禁止行为\n"
        "- 禁止重新分析JD。\n"
        "- 禁止使用原始JD推导新的结论。\n"
        "- 禁止新增亮点、风险、能力要求或任职条件。\n"
        "- 禁止改变输入结论的严重程度。\n"
        "- 禁止输出评分、分数、推荐等级或候选人匹配判断。\n"
        "- 禁止输出多个conclusion_label。\n"
        "- 禁止输出 summary 和 conclusion_label 以外的任何字段。\n"
        "- 禁止输出JSON以外的任何内容。\n\n"

        "## 输入信息\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


NARRATION_V1 = SubModule(
    name="narration",
    version="v1",
    system_prompt=NARRATION_V1_SYSTEM_PROMPT,
    output_schema=json.loads(_FINAL_OUTPUT_SCHEMA),
    build_user_prompt=_build_narration_user_prompt,
)

# ============================================================================
# 注册表
# ============================================================================

SUB_MODULE_LIBRARY: Dict[tuple, SubModule] = {
    ("element_modeling", "v1"): ELEMENT_MODELING_V1,
    ("jd_core_judgment", "v1"): JD_CORE_JUDGMENT_V1,
    ("quality_check", "v1"): QUALITY_CHECK_V1,
    ("narration", "v1"): NARRATION_V1,
}

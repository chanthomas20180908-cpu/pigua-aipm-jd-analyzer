"""目的：v3 prompt 集合。

定义：v3 过渡流程的历史 prompt 来源。

范围包括：
- v3 JD 分析 prompt 和 schema 文本。

范围不包括：
- 不作为当前 v4 prompt 维护入口。

使用与修改规则：
- 仅在修复 v3 兼容问题时修改。
"""

from __future__ import annotations

import json
from typing import Any, Dict


JD_V3_SYSTEM_PROMPT = (
    "你是资深 AI PM 岗位分析专家与业务架构师，熟悉 TOGAF 业务架构、ArchiMate 业务层建模、"
    "业务流程分析和 AI 产品生命周期。基于 JD 原文分析该岗位入职后负责的业务工作流程，输出结构化判断。"
    "只基于原文，不编造。输出必须是合法 JSON，不要 markdown、不要解释、不要注释。"
)

CANDIDATE_V3_SYSTEM_PROMPT = (
    "你是资深 AI PM 简历分析专家与人才评估顾问。基于简历原文和目标岗位关键信息，"
    "先识别候选人的证据类型（可建模能力、不完整任务能力、客观背景事实、主观能力声明），再生成匹配判断。"
    "只基于原文，不编造经历。输出必须是合法 JSON，不要 markdown、不要解释、不要注释。"
)

FINAL_V3_SYSTEM_PROMPT = (
    "你是资深 AI PM 岗位分析专家，也是求职者身边会玩梗但不毒舌的朋友。"
    "基于 JD 分析，判断这个岗位值不值得投、有什么坑、适合什么人，"
    "输出一个带梗的结论标签、一段温婉好玩的口语化总结，以及三条关键提醒。"
    "只基于 JD 信息做判断，不编造。输出必须是合法 JSON，不要 markdown、不要解释、不要注释。"
)

JD_V3_OUTPUT_SCHEMA_BACKUP = """{
  "jd_core_judgment": "50字以内：岗位本质、值不值得投、适合什么人",
  "key_requirements": ["岗位真正需要的核心能力或硬性条件（年限/学历/行业/证书等），每条≤30字"],
  "key_risks": ["最多3条，投递前必须知道的风险，每条≤30字"],
  "role_type": "产品型|工程型|混合型",
  "business_context": "30字以内：行业/场景一句话，如保险客服Agent落地",
  "business_flow": {
    "value_stream": {
      "name": "≤30字：端到端价值流名称",
      "purpose": "≤60字：该价值流存在的业务目的",
      "definition": "≤60字：价值流定义，说明创造什么价值",
      "scope_includes": ["≤30字：范围内包含的业务环节"],
      "scope_excludes": ["≤30字：明确不包含的环节"]
    },
    "activities": [
      {
        "activity_id": "A1",
        "activity_name": "≤20字，动宾结构，禁止'负责''参与''推动'",
        "sequence": 1,
        "purpose": "≤40字：该活动要达成的业务目的",
        "definition": "≤60字：活动定义",
        "scope_includes": ["≤30字：范围内包含的内容"],
        "scope_excludes": ["≤30字：范围外明确不包含的内容"],
        "previous_activities": [],
        "next_activities": ["A2"],
        "feedback_to_activities": [],
        "tasks": [
          {
            "task_id": "A1-T1",
            "task_name": "≤20字，动宾结构，任务本身就是动作",
            "purpose": "≤40字：该任务的目的",
            "definition": "≤60字：任务定义",
            "scope_includes": ["≤30字：范围内"],
            "scope_excludes": ["≤30字：范围外"],
            "inputs": ["≤20字输入业务对象"],
            "outputs": ["≤20字输出业务对象"]
          }
        ]
      }
    ]
  }
}"""

JD_MVP_OUTPUT_SCHEMA = """
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


CANDIDATE_V3_OUTPUT_SCHEMA = """{
  "candidate_profile": "50字以内：候选人画像，如5年AI工程师，强技术交付",
  "role_mismatch_flag": false,
  "candidate_match_summary": "50字以内：与这个岗位的核心匹配判断",
  "match_points": ["最多3条，每条≤30字，必须引用 candidate_evidence 中的具体证据"],
  "gaps": ["最多3条，每条≤30字，必须是对目标岗位重要的真实缺口"],
  "candidate_evidence": {
    "modeled_capabilities": [
      {
        "component_name": "能力组件名称，如业务流程设计",
        "tasks": [
          {
            "task_name": "任务级能力名称，如流程设计",
            "purpose": "≤40字：该任务的目的",
            "definition": "≤60字：任务定义",
            "scope_includes": ["≤30字：范围内"],
            "scope_excludes": ["≤30字：范围外"],
            "inputs": ["≤20字输入业务对象"],
            "outputs": ["≤20字输出业务对象"],
            "evidence_text": "简历原文证据片段",
            "confidence": 0.82
          }
        ]
      }
    ],
    "incomplete_capabilities": [
      {
        "capability_name": "能力名称",
        "known": {"task": "已知的任务线索"},
        "unknown": ["输入", "具体动作", "输出", "责任范围", "结果"],
        "confidence": 0.45
      }
    ],
    "objective_facts": [
      {
        "fact_name": "事实名称，如产品经理工作年限",
        "fact_type": "work_duration|job_title|company|industry|education|degree|major|certificate|award",
        "value": "5年",
        "evidence_text": "简历原文证据片段",
        "verifiability": "high|medium|low"
      }
    ],
    "subjective_claims": [
      {
        "claim_name": "声明名称，如执行力",
        "claim_type": "work_style|personality|self_evaluation",
        "value": "强",
        "evidence_text": "简历原文",
        "supporting_evidence": ["支持该声明的具体任务证据"],
        "evidence_strength": "self_report_only|partially_supported|supported"
      }
    ],
    "task_mappings": [
      {
        "resume_component": "能力组件名称，如业务流程设计",
        "resume_task": "任务级能力名称，如需求调研",
        "jd_activity_id": "A1",
        "jd_task_id": "A1-T1",
        "relationship": "direct_match|partial_match|related|no_match",
        "confidence": 0.82,
        "reason": "≤40字说明为什么能或不能建立关联"
      }
    ]
  }
}"""


FINAL_V3_OUTPUT_SCHEMA = """{
  "recommendation": "冲|可投|谨慎|避开",
  "match_score": 75,
  "conclusion_label": "保熟|半熟|生瓜蛋子|秤有问题|吸铁石|萨日朗",
  "summary": "≤200字：口语化、温婉好玩、带梗的JD解读。必须点出结论标签意象，给出1-2条对这个岗位的判断或提醒，不要制造焦虑。",
  "strengths": ["2-4条，JD亮点，引用JD中的具体证据，不过度玩梗，每条≤40字"],
  "risks": ["2-4条，JD风险点，引用JD中的具体证据，每条≤40字"],
  "next_actions": ["2-4条，投递前建议准备的方向，具体可执行，每条≤40字"],
  "supplements": [
    {
      "type": "jd_highlight|hidden_risk|hard_requirement|context_missing|other",
      "target": "≤30字：指向JD的activity/task或key_requirement",
      "description": "≤50字：补充观察",
      "suggested_action": "≤50字：给求职者的建议"
    }
  ]
}"""


def build_jd_v3_user_prompt(jd_text: str) -> str:
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
        f"{JD_MVP_OUTPUT_SCHEMA}\n\n"
        
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


def build_jd_v3_user_prompt_01(jd_text: str) -> str:
    return (
        "请分析下面的 JD 原文，输出一个严格可解析的 JSON 对象。所有字段名必须使用英文，所有字段值必须使用中文。\n\n"

        "## 分析目的\n"
        "从 JD 中识别该岗位入职后实际参与的业务价值流、需要执行的业务活动，以及每项活动需要创建、读取、更新或删除的业务对象。\n"
        "同时提取无法建模为业务活动的任职要求，包括客观要求和主观要求。\n\n"

        "## 你的角色\n"
        "你是一名熟悉 TOGAF 业务架构、ArchiMate 业务层建模、业务流程分析和 AI 产品生命周期的业务架构师。\n"
        "本任务分析的是岗位入职后负责的业务工作，不是企业招聘流程，也不是对候选人的匹配分析。\n\n"

        "## 总体建模结构\n"
        "岗位业务结构仅包含两层：\n"
        "1. 业务价值流 Value Stream\n"
        "2. 业务活动 Business Activity\n\n"
        "业务活动下面可以关联业务对象及其 CRUD 操作，但不再额外建立业务流程、子流程或任务层级。\n\n"

        "## 建模概念\n\n"

        "### 1. 业务价值流 Value Stream\n"
        "业务价值流是岗位参与创造业务价值的一条端到端工作链，描述价值从初始需求或问题产生，到最终交付、运营或优化的完整过程。\n"
        "例如：\n"
        "- AI场景从发现到上线运营\n"
        "- 客户需求从识别到解决方案交付\n"
        "- Agent从方案设计到持续优化\n\n"
        "价值流不是单个动作，也不是岗位名称、能力名称或技术名称。\n\n"

        "### 2. 业务活动 Business Activity\n"
        "业务活动是价值流中可以分配给某个角色、具有明确业务目的、操作特定业务对象，并且能够判断是否完成的工作单元。\n"
        "活动名称必须使用动宾结构。\n\n"
        "错误示例：\n"
        "- 负责需求分析\n"
        "- 参与方案设计\n"
        "- 推动项目上线\n"
        "- 熟悉Dify\n\n"
        "正确示例：\n"
        "- 收集客户需求\n"
        "- 分析业务痛点\n"
        "- 设计Agent解决方案\n"
        "- 制定数据标注规则\n"
        "- 设计Agent效果指标\n"
        "- 协调研发与测试资源\n"
        "- 制定项目上线方案\n"
        "- 分析Agent运行数据\n\n"
        "活动不能只是把JD原文中的“负责、参与、推动、协助”替换掉，必须还原岗位实际执行的业务动作。\n\n"

        "### 3. 业务对象 Business Object\n"
        "业务对象是业务活动创建、读取、更新、删除或传递的信息、规则、方案、数据或交付物。\n"
        "例如：\n"
        "- 客户需求\n"
        "- 业务流程\n"
        "- 业务规则\n"
        "- 场景清单\n"
        "- Agent解决方案\n"
        "- 意图分类体系\n"
        "- 数据标注规范\n"
        "- 训练数据集\n"
        "- 评测数据集\n"
        "- 效果指标\n"
        "- 测试报告\n"
        "- 运营数据\n"
        "- Bad Case\n"
        "- 优化方案\n"
        "- Agent搭建SOP\n\n"
        "以下内容通常不是业务对象：\n"
        "- Dify、Coze、LangChain等工具或框架\n"
        "- Python、Java等编程语言\n"
        "- 沟通能力、项目管理能力等能力名称\n"
        "- 研发团队、客户负责人等角色\n\n"

        "### 4. CRUD 操作\n"
        "每项业务活动都应识别其对业务对象实施的操作：\n"
        "- create：创建新的业务对象\n"
        "- read：读取、查询、分析或使用已有业务对象\n"
        "- update：修改、补充、优化或维护已有业务对象\n"
        "- delete：删除、废弃、归档或淘汰业务对象\n\n"
        "不是每项活动都必须包含四种操作。没有证据时，不得为了凑齐 CRUD 而虚构 delete 或其他操作。\n\n"

        "### 5. 任职要求 Qualification Requirement\n"
        "任职要求是无法直接建模为岗位业务活动，但招聘方希望候选人满足的背景、经验、知识、技能或个人特征。\n\n"
        "任职要求从两个独立维度分类：\n\n"
        "维度一：要求性质 requirement_nature\n"
        "- objective：可以通过履历、经历、学历、证书、作品或实际任务验证的客观要求。\n"
        "- subjective：主要体现个人性格、工作风格或自我行为倾向，难以直接通过JD进行客观验证的主观要求。\n\n"
        "维度二：必要程度 requirement_level\n"
        "- mandatory：JD明确表示必须、要求、至少、需具备等。\n"
        "- preferred：JD明确表示优先、加分、具有更佳等。\n"
        "- unclear：JD提到了该要求，但没有说明是否为硬性门槛。\n\n"
        "客观要求示例：\n"
        "- 5年以上产品经理经验\n"
        "- 本科及以上学历\n"
        "- 具有保险行业经验\n"
        "- 有Agent产品上线经验\n"
        "- 熟悉Dify或其他智能体平台\n\n"
        "主观要求示例：\n"
        "- 抗压能力强\n"
        "- 主动积极\n"
        "- 责任心强\n"
        "- 沟通能力优秀\n"
        "- 具备主人翁意识\n\n"

        "## 分析步骤\n"
        "请严格按照以下顺序完成分析，但不要输出中间推理过程。\n\n"

        "### 步骤1：提取JD事实\n"
        "逐条读取JD，提取：\n"
        "- 明确动作\n"
        "- 动作操作的业务对象\n"
        "- 业务场景\n"
        "- 工作发生的生命周期阶段\n"
        "- 明确交付物\n"
        "- 任职要求\n\n"
        "先提取事实，不要立即总结岗位类型。\n\n"

        "### 步骤2：标准化业务活动\n"
        "把JD中的招聘表达转换为标准业务活动。\n\n"
        "例如：\n"
        "“负责客户需求洞察与对接”可转换为：\n"
        "- 访谈客户业务人员\n"
        "- 收集客户需求\n"
        "- 分析业务痛点\n"
        "- 确认需求范围\n\n"
        "“推动项目实施”可根据JD证据转换为：\n"
        "- 制定项目实施计划\n"
        "- 协调研发与测试资源\n"
        "- 跟踪项目交付进度\n"
        "- 处理项目实施问题\n\n"
        "禁止仅对原文重新排列或替换同义词。\n\n"

        "### 步骤3：识别活动粒度\n"
        "一项内容至少满足以下三个条件，才可以作为独立业务活动：\n"
        "- 具有明确业务目的\n"
        "- 操作一个或多个业务对象\n"
        "- 有可识别的输入或输出\n"
        "- 可以分配给明确角色\n"
        "- 可以单独判断是否完成\n"
        "- 与其他活动存在明确前后依赖\n\n"
        "避免把过于抽象的内容作为活动，也避免把会议、发送消息等过细动作拆成独立活动。\n\n"

        "### 步骤4：归并业务价值流\n"
        "根据业务目标和生命周期，将相关活动归入一条或多条业务价值流。\n"
        "可以参考以下AI产品生命周期，但不得机械套用：\n"
        "场景探索 → 需求分析 → 方案设计 → 数据准备 → AI能力建设 → 效果评估 → 开发测试 → 上线 → 运营监控 → 持续优化 → SOP沉淀。\n\n"
        "只输出JD中具有明确证据或强逻辑支持的价值流和活动。\n\n"

        "### 步骤5：恢复活动顺序\n"
        "根据活动的输入、输出和依赖关系，恢复价值流内部的活动顺序。\n"
        "如存在反馈闭环，应通过 feedback_to_activity_ids 表示。\n\n"
        "例如：\n"
        "- 效果评估不通过，返回Agent方案设计或数据准备活动。\n"
        "- 运行数据分析后，返回Agent优化活动。\n\n"

        "### 步骤6：识别业务对象及CRUD\n"
        "针对每项业务活动：\n"
        "1. 识别活动开始前读取或使用的业务对象。\n"
        "2. 识别活动创建的新业务对象。\n"
        "3. 识别活动更新或优化的已有业务对象。\n"
        "4. 只有JD有明确依据时，才识别删除、废弃或归档操作。\n\n"
        "业务对象应尽可能使用稳定、可复用的业务名词，不要把完整句子作为对象名称。\n\n"

        "### 步骤7：提取任职要求\n"
        "将无法建模为业务活动的条件放入 qualification_requirements。\n"
        "每项要求必须同时判断：\n"
        "- requirement_nature：objective 或 subjective\n"
        "- requirement_level：mandatory、preferred 或 unclear\n"
        "- requirement_category：experience、education、industry、knowledge、skill、tool、certificate、language、work_style 或 other\n\n"
        "禁止把岗位职责原文直接当作任职要求。\n\n"

        "### 步骤8：事实与推断标记\n"
        "每条价值流、活动、业务对象和任职要求都必须标记证据类型：\n"
        "- explicit：JD原文明确表达\n"
        "- inferred：根据上下游关系或行业常识进行的谨慎推断\n\n"
        "推断内容必须有 source_evidence，并降低 confidence。\n"
        "不得把合理推断伪装成JD明确事实。\n\n"

        "### 步骤9：质量自检\n"
        "输出前检查：\n"
        "1. 是否错误分析成招聘流程。\n"
        "2. 是否存在只有抽象名词、没有业务动作的活动。\n"
        "3. activity_name 是否使用了“负责、参与、推动、协助”等招聘措辞。\n"
        "4. 是否把工具、技术、能力或角色误识别为业务活动。\n"
        "5. 每项活动是否操作了明确业务对象。\n"
        "6. 每项CRUD操作是否有合理依据。\n"
        "7. 活动顺序是否符合输入输出关系。\n"
        "8. 是否错误地把AI产品经理视为亲自执行研发或测试工作的角色。\n"
        "9. 是否识别了上线后的运营、监控和优化闭环。\n"
        "10. 是否把客观任职要求与主观工作风格混在一起。\n"
        "11. 是否把“优先”错误识别成硬性要求。\n"
        "12. JSON是否可以被程序正常解析。\n\n"

        "## 字段规范\n\n"
        "- purpose：说明该价值流或活动为什么存在、解决什么业务问题。\n"
        "- definition：说明业务对象或要求具体是什么，不描述其价值。\n"
        "- scope_includes：价值流明确包含的活动范围。\n"
        "- scope_excludes：价值流明确不包含的内容，用于防止范围膨胀。\n"
        "- inputs：活动开始前需要读取或使用的信息、规则、数据或材料。\n"
        "- outputs：活动完成后新产生或被更新的业务对象。\n"
        "- source_evidence：支持判断的JD原文片段，保持简短。\n"
        "- confidence：0到1之间的小数，表示判断可信度。\n\n"

        "## 输出要求\n"
        "只输出严格符合以下结构的JSON，不要在JSON前后输出解释、标题、Markdown代码块或其他自然语言。\n\n"

        f"{JD_V3_OUTPUT_SCHEMA}\n\n"

        "## 禁止行为\n"
        "- 禁止输出招聘流程。\n"
        "- 禁止activity_name使用“负责”“参与”“推动”“协助”。\n"
        "- 禁止把Dify、Coze、LangChain、Python等工具或技术直接作为活动。\n"
        "- 禁止把“熟悉大模型”“沟通能力强”等能力描述作为业务活动。\n"
        "- 禁止为了形成完整AI生命周期而虚构JD没有支持的活动。\n"
        "- 禁止为了凑齐CRUD而虚构删除操作。\n"
        "- 禁止把JD职责原文切片后直接放入qualification_requirements。\n"
        "- 禁止把“有相关经验者优先”识别成mandatory。\n"
        "- 禁止把主观要求描述为已被客观证明的能力。\n\n"

        f"## 原始JD文本\n{jd_text}"
    )


def _build_business_flow_summary(job_analysis: Dict[str, Any]) -> Dict[str, Any]:
    business_flow = job_analysis.get("business_flow") or {}
    value_stream = business_flow.get("value_stream") or {}

    activities = []
    for a in business_flow.get("activities", []) or []:
        activities.append(
            {
                "activity_id": a.get("activity_id", ""),
                "activity_name": a.get("activity_name", ""),
                "sequence": a.get("sequence", 0),
                "purpose": a.get("purpose", ""),
                "tasks": [
                    {
                        "task_id": t.get("task_id", ""),
                        "task_name": t.get("task_name", ""),
                        "purpose": t.get("purpose", ""),
                        "inputs": (t.get("inputs", []) or [])[:4],
                        "outputs": (t.get("outputs", []) or [])[:4],
                    }
                    for t in (a.get("tasks", []) or [])[:5]
                ],
            }
        )

    return {
        "value_stream": {
            "name": value_stream.get("name", ""),
            "purpose": value_stream.get("purpose", ""),
        },
        "activities": activities,
        "key_requirements": (job_analysis.get("key_requirements", []) or [])[:5],
    }


def build_candidate_v3_user_prompt(resume_text: str, job_analysis: Dict[str, Any]) -> str:
    job_context = {
        "role_type": job_analysis.get("role_type", ""),
        "key_requirements": job_analysis.get("key_requirements", []),
        "business_context": job_analysis.get("business_context", ""),
        "business_flow_summary": _build_business_flow_summary(job_analysis),
    }
    return (
        # "请分析下面的简历原文，输出一个 JSON 对象。字段名必须用英文，字段值必须用中文。\n\n"
        # "## 目的\n"
        # "先识别候选人简历中的证据类型，再判断其与目标岗位的匹配度。\n\n"
        # "## 核心概念（必须严格区分）\n"
        # "1. 可建模能力 modeled_capability：简历中能识别具体任务，并能明确回答“处理什么输入 → 产生什么输出”的能力。"
        # "这是唯一可以直接证明岗位匹配度的证据类型，优先级最高。\n"
        # "   可建模能力分为两层：\n"
        # "   - 能力组件 component：较高层的能力领域，例如“业务流程设计”“跨部门项目协同”。\n"
        # "   - 任务级能力 task：组件内部的具体任务，例如“流程设计”“目标流程定义”。"
        # "     任务级能力应与岗位识别出的 task 语义同构，用于后续匹配。\n"
        # "   例如原文“负责需求调研、业务抽象、流程设计、功能规划和上线推进”可拆分为：\n"
        # "   - 组件：业务流程设计；任务：需求调研、业务抽象、流程设计、功能规划、上线推进。\n\n"
        # "2. 不完整任务能力 incomplete_capability：简历中有任务线索但信息不完整，无法确认输入、输出、责任范围或结果。\n"
        # "   例如“负责知识库建设”——不知道输入是业务知识还是 RAG 数据，也不清楚本人是主导还是参与。\n\n"
        # "3. 客观背景事实 objective_fact：简历中客观发生、可验证，但不能直接还原为“输入—任务—输出”的事实。"
        # "包括工作年限、任职公司、岗位名称、教育经历、毕业院校、专业、学历、行业经历、证书、奖项等。\n"
        # "   这些事实可以辅助判断经历相关性、持续时间、行业熟悉度，但不能直接证明能力强弱。\n\n"
        # "4. 主观能力声明 subjective_claim：候选人对自身能力、性格或工作风格的概括，但无法从文本中还原出明确任务和结果。\n"
        # "   例如：抗压能力强、主动积极、执行力强、学习能力强、沟通能力优秀、责任心强、逻辑思维清晰。\n"
        # "   这些属于工作风格/自我评价，不是具体任务能力，必须标注证据强度。\n\n"
        # "## 识别逻辑（对简历中每条信息依次判断）\n"
        # "1. 能否识别具体任务？\n"
        # "   ├── 能 → 能否识别输入和输出？\n"
        # "   │       ├── 能 → 可建模能力（归入对应组件和任务）\n"
        # "   │       └── 不能 → 不完整任务能力\n"
        # "   └── 不能 → 是否为可验证的经历事实？\n"
        # "           ├── 是 → 客观背景事实\n"
        # "           └── 否 → 主观能力声明\n\n"
        # "## 可建模能力判断规则\n"
        # "满足以下任意三项，即可识别为 modeled_capability 中的任务：\n"
        # "- 有明确工作对象；\n"
        # "- 有具体动作（任务名本身就是动作）；\n"
        # "- 有可识别的输入；\n"
        # "- 有可识别的输出；\n"
        # "- 有交付物或结果；\n"
        # "- 能定位到具体项目或经历。\n\n"
        # "## 任务级匹配建模规则（核心）\n"
        # "你必须显式建模简历任务与 JD 任务之间的关系，结果写入 `candidate_evidence.task_mappings`。\n"
        # "匹配不是感觉，而是输入/输出/动作/场景的逐项对比。按以下步骤执行：\n"
        # "1. 对 `modeled_capabilities` 中的每一个 task，逐一对比岗位 `business_flow.activities` 中的每一个 task。\n"
        # "2. 判断关系类型：\n"
        # "   - `direct_match`：任务名称、目的、输入输出高度一致，可直接支撑该 JD 任务。例如简历'需求调研'与 JD '访谈保险业务人员'。\n"
        # "   - `partial_match`：方法/动作同构，但场景、行业或证据强度有差距。例如'需求调研'迁移到保险场景仍需补行业知识。\n"
        # "   - `related`：有关联，但不能直接替代，需要补充上下文或能力。例如'上线推进'与'协调资源推进Agent上线'相关，但缺 Agent 领域经验。\n"
        # "   - `no_match`：找不到语义关联的 JD 任务。\n"
        # "3. 每条映射必须写明 `reason`（≤40 字），说明为什么能或不能建立关联。\n"
        # "4. `confidence` 必须基于证据明确程度，0-1 之间，`direct_match` 通常 ≥0.8，`no_match` 可以低。\n"
        # "5. `match_points` 必须优先从 `direct_match` / `partial_match` 中提炼，禁止把 `no_match` 的简历任务写进 match_points。\n"
        # "6. `gaps` 必须优先对应 JD 任务中没有被任何简历任务以 `direct_match` 或 `partial_match` 覆盖的环节。\n"
        # "7. `task_mappings` 必须覆盖 `modeled_capabilities` 中的每一个 task；即使无法匹配，也要输出 `relationship=no_match` 并说明原因。\n\n"
        # "## 字段规范\n"
        # "- 任务级能力字段必须与岗位 task 同构：`task_name`、`purpose`、`definition`、`scope_includes`、`scope_excludes`、`inputs`、`outputs`。\n"
        # "- 附加字段 `evidence_text` 和 `confidence` 用于锚定简历证据。\n"
        # "- `component_name` 是对一组相关任务的归纳，便于与岗位活动/价值流对应。\n"
        # "- `task_mappings` 每条必须包含：`resume_component`、`resume_task`、`jd_activity_id`、`jd_task_id`、`relationship`、`confidence`、`reason`。\n"
        # "  - `no_match` 时 `jd_activity_id` 和 `jd_task_id` 可置为空字符串，但字段必须存在。\n\n"
        # "## 输出结构（只包含这些字段）\n"
        # "```json\n"
        # f"{CANDIDATE_V3_OUTPUT_SCHEMA}\n"
        # "```\n\n"
        # "## 数量与长度限制\n"
        # "- candidate_profile / candidate_match_summary 各 ≤50 字。\n"
        # "- match_points / gaps 各最多 3 条，每条 ≤30 字。\n"
        # "- modeled_capabilities 最多 6 个 component；每个 component.tasks 最多 5 个。\n"
        # "- incomplete_capabilities 最多 6 条；objective_facts 最多 8 条；subjective_claims 最多 6 条。\n"
        # "- 每个 task 的 scope_includes / scope_excludes 各 1-4 条；inputs / outputs 各 1-4 个。\n"
        # "- evidence_text ≤80 字。\n"
        # "- `task_mappings` 数量必须等于 `modeled_capabilities` 中 task 总数；reason ≤40 字。\n\n"
        # "## 匹配推导规则\n"
        # "- `task_mappings` 是匹配的核心依据。`match_points` 必须优先从 `direct_match` / `partial_match` 中提炼，"
        # "并引用对应的 `jd_task_id` 或 `activity_id`。\n"
        # "- `gaps` 必须优先列出 JD 任务中没有被任何简历任务以 `direct_match` 或 `partial_match` 覆盖的环节，"
        # "也可以补充 `key_requirements` 中的硬性条件缺口。\n"
        # "- `candidate_match_summary` 应综合 `task_mappings` 的分布（direct/partial/related/no_match 比例）、"
        # "`incomplete_capabilities` 的数量、`objective_facts` 的相关性以及 `subjective_claims` 的证据强度给出判断。\n"
        # "- `role_mismatch_flag`：当目标岗位是 `产品型` 或 `混合型`，而候选人明显是工程/研究背景（如头衔是数据科学家、算法工程师、软件工程师，"
        # "且内容以技术实现为主）时，必须置 `true`。\n\n"
        # "## 禁止行为\n"
        # "- 禁止把“5年产品经理经验”“毕业于清华”“高级产品经理”等客观背景事实直接写进 match_points 当作能力证据。\n"
        # "- 禁止把“执行力强”“抗压能力强”等主观声明直接写进 match_points。\n"
        # "- 禁止 match_points / gaps 写成无证据的概括句，例如“候选人具备扎实的AI Agent技术落地能力”。\n"
        # "- 禁止 gaps 超过3条或每条超过30字。\n"
        # "- 禁止 candidate_profile 写成“候选人工作认真负责”这种无信息量描述。\n\n"
        # "## 目标岗位关键信息\n"
        f"```json\n{json.dumps(job_context, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## 原始简历文本\n{resume_text}"
    )


def build_final_v3_user_prompt(
    *,
    jd_text: str,
    job_analysis: Dict[str, Any],
) -> str:
    payload = {
        "jd_text": jd_text,
        "job_analysis": job_analysis,
    }
    return (
        "基于下面的 JD 分析和原始 JD 文本，输出对这个岗位的解读判断。"
        "输出必须是合法 JSON，不要 markdown、不要解释、不要注释。\n\n"
        "## 输出结构\n"
        "严格符合以下结构（字段名英文，值中文）：\n"
        "```json\n"
        f"{FINAL_V3_OUTPUT_SCHEMA}\n"
        "```\n\n"
        "## 结论标签（conclusion_label）映射表\n"
        "选择一个最能概括这个 JD 的标签，标签必须与 recommendation 语义大致对应：\n"
        "- `保熟`：岗位描述扎实，职责清晰，值得投。对应 `冲` / `可投`。\n"
        "- `半熟`：方向不错但部分描述模糊，可以投但需要面试时多问。对应 `可投` / `谨慎`。\n"
        "- `生瓜蛋子`：岗位方向太新或职责不清晰，团队可能还没想清楚。对应 `谨慎`。\n"
        "- `秤有问题`：JD 描述有水分、要求虚高或职责边界不清。对应 `谨慎` / `避开`。\n"
        "- `吸铁石`：JD 有明显包装、夸大或自相矛盾。对应 `谨慎` / `避开`。\n"
        "- `萨日朗`：岗位黑心、明显坑或严重不值得投。对应 `避开`。\n\n"
        "## summary 风格规则\n"
        "- `summary` 是一段口语化、温婉好玩的 JD 解读，≤200 字。\n"
        "- 必须点出结论标签的意象，例如'这瓜保熟'、'这瓜还生着'、'这秤有问题'。\n"
        "- 要给出 1-2 条对这个岗位的判断或投递提醒，不要制造焦虑。\n"
        "- 像朋友聊天，不要写成官方报告。\n\n"
        "## 三条补充（supplements）规则\n"
        "- 必须输出 **恰好 3 条** supplement。\n"
        "- 每条包含 `type`、`target`、`description`、`suggested_action`。\n"
        "- 类型说明：\n"
        "  - `jd_highlight`：JD 中值得关注的亮点。\n"
        "  - `hidden_risk`：JD 文字背后可能隐藏的风险。\n"
        "  - `hard_requirement`：JD `key_requirements` 中的硬性门槛分析。\n"
        "  - `context_missing`：JD 中缺失但面试时需要确认的信息。\n"
        "  - `other`：其他建议。\n"
        "- 尽量按以下方向凑齐 3 条：\n"
        "  1. 从 JD `business_flow` 中找 1 条 `jd_highlight`。\n"
        "  2. 从 JD `key_requirements` 中找 1 条 `hard_requirement`。\n"
        "  3. 从 JD 整体判断中找 1 条 `hidden_risk` 或 `context_missing`。\n"
        "- 如果确实凑不够，允许用 `other` 补充，但总数必须恰好 3 条。\n\n"
        "## 字段定义与规则\n"
        "1. `recommendation` 与 `match_score` 必须严格对齐：\n"
        "   - 冲：80-100\n"
        "   - 可投：65-79\n"
        "   - 谨慎：50-64\n"
        "   - 避开：0-49\n"
        "2. `conclusion_label`：从映射表中选择一个标签，与 `recommendation` 语义一致。\n"
        "3. `summary`：≤200 字口语化 JD 解读，含标签意象，不制造焦虑。\n"
        "4. `strengths` / `risks`：2-4 条，每条 ≤40 字，必须引用 JD 中的具体证据。\n"
        "   - strengths 优先引用 `business_flow` 中的活动和任务亮点。\n"
        "   - risks 优先引用 JD 中模糊、矛盾或高风险的描述。\n"
        "5. `next_actions`：2-4 条，每条 ≤40 字，投递前建议准备的方向。\n"
        "6. `supplements`：恰好 3 条对象，每条 `type/target/description/suggested_action` 均非空。\n"
        "7. 禁止编造 JD 中没有的信息。\n\n"
        "## 禁止行为\n"
        "- 禁止 `recommendation` 与 `match_score` 不一致。\n"
        "- 禁止 `summary` 写成官方报告或制造焦虑。\n"
        "- 禁止 `strengths` / `risks` / `next_actions` 全部玩梗而丢失证据。\n"
        "- 禁止 `supplements` 少于或多于 3 条。\n"
        "- 禁止 `supplements` 描述空泛，例如'建议再看看'。\n\n"
        "## 输入信息\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

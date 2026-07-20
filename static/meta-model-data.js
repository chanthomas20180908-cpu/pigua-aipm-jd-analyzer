/*
 * 目的：提供元模型详情页的静态数据源。
 * 定义：集中保存九个核心节点、关系和展示文案，供 `/meta-model` 图谱渲染使用。
 * 范围包括：
 * - 节点定义、关系定义、展示摘要和说明文案。
 * 范围不包括：
 * - 不承载渲染逻辑，不从后端读取运行时数据。
 * 使用与修改规则：
 * - 数据来源优先对齐 `docs/archive/meta-model/ai_pm_jd_business_model.md` 的概念边界。
 */

window.META_MODEL_GRAPH_DATA = {
  title: "AI PM JD 业务建模核心图谱",
  subtitle: "从公司上下文出发，串起岗位、价值流、工作事项、实体、能力、要求、环境和风险。",
  nodes: [
    {
      id: "company_context",
      label: "公司上下文",
      kind: "context",
      radius: 34,
      summary: "判断岗位是否合理的第一层前提，决定资源边界、组织分工和目标压力。",
      details: [
        "看什么：行业、规模、阶段、组织结构、技术战略。",
        "为什么：同一个岗位在不同公司会长成完全不同的职责形状。",
        "常见信号：业务方向模糊、组织边界不清、招聘主体异常。",
      ],
      prompt: "先判断岗位站在什么公司和组织背景里。",
      cards: [
        "公司名称",
        "所属行业",
        "公司业务",
        "核心产品或服务",
        "公司规模",
        "发展阶段",
      ],
    },
    {
      id: "job",
      label: "岗位",
      kind: "job",
      radius: 30,
      summary: "招聘语义里的职位壳子，负责承接组织目标，并把责任压进一个可招聘的角色。",
      details: [
        "看什么：职位名称、职级、所属部门、地点、办公方式。",
        "为什么：岗位是组织把工作任务打包后对外开放的接口。",
        "常见信号：title 很大，职责很散，或者什么都想塞进一个人。",
      ],
      prompt: "再看岗位自身被写成了什么样。",
      cards: [
        "职位名称",
        "职级",
        "所属部门",
        "办公方式",
        "岗位定位",
      ],
    },
    {
      id: "value_stream",
      label: "价值流",
      kind: "flow",
      radius: 32,
      summary: "从问题产生到业务价值交付的一条端到端工作链，是理解岗位做什么的主线。",
      details: [
        "看什么：目标客户、触发条件、起始状态、结束状态、价值结果。",
        "为什么：没有价值流，就只能停留在任务列表，无法判断岗位重心。",
        "常见信号：JD 只写职能，不写端到端链路。",
      ],
      prompt: "岗位到底服务哪条价值流。",
      cards: [
        "价值流名称",
        "价值流目的",
        "触发条件",
        "价值接受者",
        "起始状态",
        "结束状态",
      ],
    },
    {
      id: "work_item",
      label: "工作事项",
      kind: "work",
      radius: 30,
      summary: "价值流中由一个角色主责的一组连续工作，粒度足够大，能独立判断完成标准。",
      details: [
        "看什么：工作目的、输入、执行动作、输出、完成标准。",
        "为什么：它是判断岗位是否真正在做业务的最小可解释单元。",
        "常见信号：事项粒度过碎，像消息通知或会议动作，而不是业务工作。",
      ],
      prompt: "岗位会落到哪些可执行的工作事项上。",
      cards: [
        "工作事项名称",
        "工作目的",
        "输入",
        "执行动作",
        "业务实体输出",
        "完成标准",
      ],
    },
    {
      id: "business_entity",
      label: "业务实体",
      kind: "entity",
      radius: 28,
      summary: "工作事项操作的业务对象，决定岗位到底在改什么、读什么和维护什么。",
      details: [
        "看什么：对象类型、域、状态、关系和 CRUD 操作。",
        "为什么：实体会直接暴露岗位是否有真正的业务闭环。",
        "常见信号：实体缺失，只讲功能，不讲对象。",
      ],
      prompt: "岗位会处理哪些业务对象。",
      cards: [
        "业务实体名称",
        "实体域",
        "实体类型",
        "CRUD 语义",
      ],
    },
    {
      id: "business_capability",
      label: "业务能力",
      kind: "capability",
      radius: 28,
      summary: "岗位需要具备的可迁移能力集合，既能支撑工作事项，也能反映组织的能力门槛。",
      details: [
        "看什么：能力定义、支撑的事项、管理的实体、依赖关系。",
        "为什么：能力不是技能清单，而是完成业务工作的系统性能力。",
        "常见信号：只写工具名，不写能力边界和迁移性。",
      ],
      prompt: "岗位需要哪些能力来把事做成。",
      cards: [
        "业务能力名称",
        "能力定义",
        "支撑事项",
        "管理实体",
        "依赖能力",
      ],
    },
    {
      id: "requirement",
      label: "任职要求",
      kind: "requirement",
      radius: 27,
      summary: "把岗位责任翻译成候选人画像的那一层，既约束岗位，也支持能力和角色匹配。",
      details: [
        "看什么：学历、经验、技能、行业背景、沟通表达和项目经验。",
        "为什么：任职要求常常暴露岗位的真实难度与组织预期。",
        "常见信号：要求很泛，或者要求堆得像需求清单而不是岗位门槛。",
      ],
      prompt: "任职要求是否真的对应岗位工作。",
      cards: [
        "学历要求",
        "经验要求",
        "技能要求",
        "行业背景",
        "沟通表达",
        "项目经验",
      ],
    },
    {
      id: "environment",
      label: "工作环境",
      kind: "environment",
      radius: 27,
      summary: "组织与执行条件的总和，直接影响岗位节奏、协作成本和风险暴露。",
      details: [
        "看什么：组织结构、协作方式、节奏、地点、办公形式、合规约束。",
        "为什么：同样的岗位，在不同环境里会有完全不同的可行性。",
        "常见信号：环境描述缺失，但交付要求很重。",
      ],
      prompt: "这个岗位会在什么样的环境里工作。",
      cards: [
        "组织结构",
        "办公方式",
        "工作地点",
        "协作方式",
        "交付节奏",
      ],
    },
    {
      id: "risk",
      label: "风险",
      kind: "risk",
      radius: 30,
      summary: "把结构化理解最后翻译成判断，指出 title 虚高、职责失衡、伪 AI、交付甩锅等问题。",
      details: [
        "看什么：职责边界、资源匹配、AI 含量、交付责任和组织信号。",
        "为什么：这是把图谱变成可行动判断的收口层。",
        "常见信号：需求和资源不匹配、岗位目标不闭环、口径和实际不一致。",
      ],
      prompt: "最后把所有异常信号收拢到风险判断。",
      cards: [
        "title 虚高",
        "职责失衡",
        "伪 AI",
        "交付甩锅",
        "资源错配",
      ],
    },
  ],
  relations: [
    { source: "company_context", target: "job", label: "限定", kind: "context" },
    { source: "job", target: "value_stream", label: "承担", kind: "primary" },
    { source: "value_stream", target: "work_item", label: "包含", kind: "primary" },
    { source: "work_item", target: "business_entity", label: "操作", kind: "entity" },
    { source: "work_item", target: "business_capability", label: "依赖", kind: "capability" },
    { source: "requirement", target: "business_capability", label: "支撑", kind: "requirement" },
    { source: "requirement", target: "work_item", label: "证明", kind: "requirement" },
    { source: "requirement", target: "environment", label: "来源于", kind: "requirement" },
    { source: "environment", target: "work_item", label: "影响", kind: "environment" },
    { source: "risk", target: "requirement", label: "反推", kind: "risk" },
    { source: "risk", target: "environment", label: "放大", kind: "risk" },
    { source: "risk", target: "job", label: "校验", kind: "risk" },
  ],
};

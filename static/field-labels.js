/*
 * 目的：前端字段标签配置。
 * 定义：集中维护后端字段到中文展示文案和结构化渲染配置的映射。
 * 范围包括：
 * - 字段标签、section 标签和列表图标规则。
 * 范围不包括：
 * - 不写 DOM 主流程或图谱算法。
 * 使用与修改规则：
 * - 后端新增/改名字段时优先更新这里。
 */

/* ============================================================================
 * field-labels.js — 字段名 → 中文映射 & 渲染配置
 *
 * 后端新增/修改字段时，只需更新此文件。
 * 缺失的字段名 fallback 为英文原名。
 * ========================================================================== */

/* ---- section 级 ---- */

const SECTION_LABELS = {
  narration: "口语化总结",
  element_modeling: "建模图谱",
  jd_core_judgment: "岗位判断",
  quality_check: "模块二 · 质检",
  jd_text: "原始 JD",
  _meta: "元信息",
};

const SECTION_ORDER = [
  "narration",
  "element_modeling",  // 由 #graphCard 单独渲染，不进入 resultContent
  "jd_core_judgment",
  "quality_check",
  "jd_text",
  "_meta",
];

/* ---- 字段名 → 中文 label ---- */

const FIELD_LABELS = {
  /* jd_core_judgment */
  core_judgment: "核心判断",
  job_focus: "工作重点",
  strengths: "亮点",
  risks: "风险",
  key_findings: "关键发现",
  interview_questions: "面试要问的",

  /* quality_check */
  risk_points: "风险点",

  /* narration */
  conclusion_label: "结论",
  summary: "总结",

  /* element_modeling */
  value_streams: "价值流",
  work_items: "工作事项",
  bussiness_entitys: "业务实体",
  capabilities: "业务能力",

  /* 通用子字段 */
  target: "对象",
  description: "说明",
  finding: "判断",
  evidence: "证据",
  certainty: "确定性",
  severity: "严重程度",
  suggested_action: "建议",
  source_evidence: "JD 原文",
  purpose: "目的",
  definition: "定义",
  type: "类型",

  /* _meta */
  version: "版本",
  trace_id: "追踪 ID",
  trace_log_path: "日志路径",
  llm: "模型信息",
  provider: "服务商",
  model: "模型",
};

/* ---- severity 值 → 中文 & 颜色 ---- */

const SEVERITY_MAP = {
  high:   { label: "高", cls: "badge-danger" },
  medium: { label: "中", cls: "badge-amber" },
  low:    { label: "低", cls: "badge-muted" },
};

/* ---- certainty 值 → 中文 ---- */

const CERTAINTY_MAP = {
  explicit: "明确",
  inferred: "推断",
};

/* ---- 列表图标规则：key 名含关键词 → { icon, cls } ---- */

const LIST_STYLE_RULES = [
  { match: /strengths|亮点/,        icon: "✓", cls: "list-green" },
  { match: /risks|风险/,             icon: "⚠", cls: "list-amber" },
  { match: /question|问题|面试/,     icon: "?", cls: "list-bubble" },
  { match: /action|建议|下一步/,     icon: "",  cls: "list-numbered" },  // 编号，图标用数字
  { match: /focus|重点/,             icon: "▸", cls: "list-green" },
];

const DEFAULT_LIST_STYLE = { icon: "·", cls: "list-default" };

/* ---- 文本判断阈值 ---- */

const LONG_TEXT_THRESHOLD = 50;  // 超过此长度的字符串走 Prose 样式

/* ---- 首页虚构脱敏示例 JD ---- */

const SAMPLE_JDS = {
  ai_agent: "我们正在招聘 AI Agent 产品经理，负责企业知识助手从需求调研、工作流设计到效果评估的完整闭环。你将与算法、工程和客户成功团队协作，拆解高频业务场景，定义 Agent 工具调用、评测指标与迭代优先级。要求有 3 年以上 B 端或 AI 产品经验，能用数据判断方案价值，并能清晰推动跨团队交付。",
  growth: "我们正在招聘增长产品经理，负责一款面向职场用户的 AI 效率工具。你将搭建从获客、激活、留存到付费转化的增长链路，设计实验并分析漏斗数据；同时与内容、运营、研发团队协作，把用户反馈转成可验证的产品迭代。要求熟悉 A/B 测试、用户分层和商业化策略，有独立负责增长项目的经验。",
  data_platform: "我们正在招聘数据中台产品经理，负责业务数据资产的统一建模、指标治理与自助分析能力建设。你将梳理销售、运营和客服场景的核心流程，定义数据口径、权限体系和数据产品路线图，并与数据工程、BI、业务负责人共同推进落地。要求具备复杂 B 端产品经验，理解数据仓库、指标体系和数据质量治理。",
};

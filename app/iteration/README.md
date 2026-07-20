<!--
目的：承载 v4 prompt/code 离线迭代 Loop 的核心实现。
定义：面向本地实验的 Evaluator-Optimizer 组件包。
范围包括：
- 迭代数据模型、预算守卫、Promptfoo/Python 评估器、DSPy/规则候选生成器、反思器、LangGraph 控制器、worktree 管理和 run 记录产物生成。
范围不包括：
- 不承载线上 HTTP 路由，不直接修改生产 prompt，不保存大型运行产物。
使用与修改规则：
- 线上 /analyze/v4 默认行为不得依赖本包；实验入口通过 scripts/run_iteration_loop.py 调用。
-->

# iteration 目录说明

## 目的
承载 v4 prompt/code 离线迭代 Loop 的核心实现。

## 定义
面向本地实验的 Evaluator-Optimizer 组件包。

## 范围包括
- 迭代数据模型、预算守卫、Promptfoo/Python 评估器、DSPy/规则候选生成器、反思器、LangGraph 控制器、worktree 管理和 run 记录产物生成。

## 范围不包括
- 不承载线上 HTTP 路由，不直接修改生产 prompt，不保存大型运行产物。

## 使用与修改规则
- 线上 `/analyze/v4` 默认行为不得依赖本包；实验入口通过 `scripts/run_iteration_loop.py` 调用。
- 单次 run 记录产物包括 `report.md`、`PROMOTION.md`、`loop_state.json`、`case_results.jsonl`、`variants.json` 和 `run_manifest.json`。
- `element_modeling` 当前除结构阈值外，还支持 case 级 `semantic_checks`、`failure_tags` 和 `hard_failure_tags`；字段扩展需同步 `data/test_cases_v1/v4_golden/README.md`。
- LLM 调用默认采用分层 timeout，慢响应视为正常现象；不要把长等待直接当成 SDK 卡死。
- workflow 执行异常应优先下沉为 case 级失败记录，而不是让整轮 loop 直接中断。
- 修改 CLI 参数、预算字段、状态机节点或输出目录时，同步 `docs/loop-design.md`、`scripts/README.md` 和项目根 `AGENTS.md`。

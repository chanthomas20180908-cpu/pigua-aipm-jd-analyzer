<!--
目的：放置本地验证、调试和一次性辅助脚本，帮助检查 LLM 输出与历史流程。
定义：开发辅助脚本目录，不是线上服务运行路径。
范围包括：
- trace 渲染、A1 逻辑测试、LLM 抽取验证、v3 workflow 验证脚本。
- 本地开发服务启动入口 `dev.py`。
- v4 离线迭代 Loop 命令行入口。
- narration trace 末模块验证脚本。
范围不包括：
- 不承载服务入口、不放可复用业务模块、不保存运行结果。
使用与修改规则：
- 脚本应能从项目根目录直接运行。
- 若脚本逻辑变成产品能力，应迁移到 app/ 并补测试。
-->

# scripts 目录说明

## 目的
放置本地验证、调试和一次性辅助脚本，帮助检查 LLM 输出与历史流程。

## 定义
开发辅助脚本目录，不是线上服务运行路径。

## 范围包括
- trace 渲染、A1 逻辑测试、LLM 抽取验证、v3 workflow 验证脚本。
- 本地开发服务启动入口 `dev.py`。
- v4 离线迭代 Loop 命令行入口。

## 范围不包括
- 不承载服务入口、不放可复用业务模块、不保存运行结果。

## 使用与修改规则
- 脚本应能从项目根目录直接运行。
- 若脚本逻辑变成产品能力，应迁移到 app/ 并补测试。
- 本地开发优先通过 `make dev` 调用 `scripts/dev.py`，避免散落 uvicorn 参数。

## narration 末模块验证

`verify_narration_from_trace.py` 从已有 v4 trace 恢复 `jd_core_judgment` 和 `quality_check`，只调用 `narration`，不重跑前三个模块。它会打印新总结并检查是否以两个空行分成 2-3 个短段：

```bash
python3 scripts/verify_narration_from_trace.py logs/<trace_id>.md
```

该命令会向既有 OpenAI 兼容模型服务发送 trace 内的两个结构化上游结论；需要配置项目既有的 API key。

## v4 迭代 Loop

```bash
python3 scripts/run_iteration_loop.py \
  --target element_modeling \
  --regression-eval data/test_cases_v1/cases \
  --capability-eval data/test_cases_v1/capability \
  --golden-dir data/test_cases_v1/v4_golden \
  --config app/iteration/loop_config.py \
  --max-iterations 3 \
  --stop-after-no-improvement 1 \
  --max-llm-calls 80 \
  --budget-usd 0.55
```

该脚本会调用真实 v4 LLM 工作流，需要配置 `DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY`。API key 只通过环境变量注入，不写入仓库文件。Python 依赖包括 `langgraph` 和 `dspy-ai`；Promptfoo 优先使用 `PATH` 中的全局二进制，只有显式设置 `PROMPTFOO_USE_NPX=1` 时才允许退回 `npx --yes promptfoo`，仍不可用时回退 Python evaluator。CLI 会先校验 case/golden 目录内容，为单次 run 创建 `.worktrees/loop-{run_id}/`，并把 `report.md`、`PROMOTION.md`、`loop_state.json`、`case_results.jsonl`、`variants.json` 和 `run_manifest.json` 默认写入该 run worktree 的 `workbench/runs/{run_id}/`。

运行参数采用 `LoopConfig` 统一管理，优先级为 `CLI > AIPM_LOOP_* 环境变量 > --config Python 配置文件 > dataclass 默认值`。当前默认值包括：

- `llm_call_timeout_seconds=120`
- `case_timeout_seconds=300`
- `retry_count=2`
- `retry_backoff_seconds=2.0`
- `max_timeout_rate=0.3`
- `stop_after_no_improvement=2`

长链路调试建议显式设置分层 timeout，至少放宽读超时：

```bash
export OPENAI_READ_TIMEOUT_SECONDS=300
export AIPM_LOOP_CASE_TIMEOUT_SECONDS=300
```

本地最小检查链路：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/aipm_resume_analyzer_pycache python3 -m compileall app scripts tests
python3 -m unittest tests.unit.test_iteration_components -v
python3 -m pytest tests/unit/test_llm_client.py
```

`call_llm_json()` 会容错提取被 markdown fence 包裹、带尾随解释文本或字符串内含 `{}` 的 JSON；JSON 解析失败会按 `retry_count` 重试。如单个 case 的外部调用失败，脚本会在 `case_results.jsonl` 中记录 `execution_error_type`、`timing`、`error` 和失败原因，整轮 run 仍会生成报告，便于区分“评估失败”和“工作流执行失败”。timeout 或非 timeout 执行失败 case 仍得 0 分并影响总体分数，但不直接拉低用于 `regression_floor` 的 scored-case 均分；当执行失败/timeout 比例超过 `max_timeout_rate` 时，run 会以 `timeout_rate_exceeded` 停止。

<!--
目的：公开说明历史 MVP 离线实验的聚合结果与证据边界。
定义：不含私有评测输入的脱敏验证摘要，是 README 中历史分数的唯一主说明。
范围包括：run 配置、聚合指标、剩余问题和不可推断的结论。
范围不包括：JD、golden、prompt、trace、原始输出、case 级细节或当前公开提交的性能承诺。
使用与修改规则：只在人工复核的历史 run 或新的干净复验完成后更新；不得以此替代公开 CI。
-->

# 历史 MVP 离线验证摘要

## 结论

2026-07-08 的历史 run `648097f5ed` 面向 `element_modeling`，在私有 5-case **回归**子集上将最佳 trial 的 score 从 `0.9333` 提升到 `0.9500`。最佳变体为 `variant-01-evidence`；三次 trial 均为 `0` timeout、`0` execution failure。

这是一条历史原型实验记录，不是当前公开 `main` 的可复现性能承诺，不是模型准确率、线上 A/B 结果、用户满意度或商业指标。

## 实验范围

| 项目 | 值 |
| --- | --- |
| 工作流 | v4 / `element_modeling` |
| 模型 | DashScope-compatible `qwen-plus` |
| 数据范围 | 私有 5-case 回归子集；不公开 JD、golden 或原始输出 |
| trial | baseline、`variant-01-evidence`、`variant-02-evidence` |
| 停止条件 | `max_iterations=3` |
| 总 LLM 调用 | 124 |
| 估算成本 | USD 0.785127 |

项目代码支持回归/能力双轨评测：回归集用于防止已有能力退化，能力集用于单独观察爬坡。但本次历史 run 未传入 capability 集，因此此处的 score 是回归分数，不能称为双轨 combined score。

## 聚合结果与剩余边界

| Trial | Score | Timeout | 执行失败 |
| --- | ---: | ---: | ---: |
| baseline | 0.9333 | 0 | 0 |
| `variant-01-evidence`（最佳） | 0.9500 | 0 | 0 |
| `variant-02-evidence` | 0.9500 | 0 | 0 |

最佳 score 不代表该 trial 的全部质量门槛已经通过：实验中仍存在至少一个样本的建模粒度问题。原始运行发生在私有旧原型的 dirty worktree 中；因此不将其绑定到当前公开仓库的某个 commit，也不承诺在新的模型版本、私有数据版本或运行环境下得到相同数字。

## 可视化补充

仓库保留了该历史 run 的[静态流程图源码](static/loop-648097f5ed-report.html)。克隆后运行 `make dev`，可在 `http://127.0.0.1:8000/static/loop-648097f5ed-report.html` 打开；该旧页面通过 Mermaid CDN 渲染，浏览器需要网络访问该 CDN。它只作辅助可视化，本页是对外引用时的主口径。

## 数据与安全边界

- 公开仓库不包含 `data/`、`docs/`、`logs/`、`workbench/` 或 Agent 上下文。
- 不公开任何真实 JD、简历、API key、trace、prompt、golden、模型 raw response 或本机绝对路径。
- 如需让分数代表公开代码，应在固定的干净公开 commit 上，使用受控私有评测集重新运行，并发布新的脱敏聚合摘要。

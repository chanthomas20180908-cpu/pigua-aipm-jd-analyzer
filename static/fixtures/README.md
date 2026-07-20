<!--
目的：保存可复现的前端验收数据夹具。
定义：从人工确认的 v4 分析 trace 提取、可由 /sample 使用的完整 API 响应快照。
范围包括：
- 脱敏后的 JSON fixture 与其来源、刷新方式说明。
范围不包括：
- 不保存原始 trace、LLM prompt、raw response、密钥或运行日志。
使用与修改规则：
- 仅通过 scripts/extract_frontend_sample.py 从明确指定的 trace 更新，并先人工审阅 diff。
-->

# fixtures 目录说明

## 目的

保存可复现的前端验收数据夹具。

## 定义

从人工确认的 v4 分析 trace 提取、供 `/sample` 使用的完整 API 响应快照。

## 范围包括

- 脱敏后的 JSON fixture 与其来源、刷新方式说明。

## 范围不包括

- 不保存原始 trace、LLM prompt、raw response、密钥或运行日志。

## 使用与修改规则

- 仅通过 `scripts/extract_frontend_sample.py` 从明确指定的 trace 更新，并先人工审阅 diff。
- 不提供自动选择“最新”日志的入口，避免未审阅数据进入版本库。

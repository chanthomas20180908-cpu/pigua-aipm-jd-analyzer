<!--
目的：为 Claude Code 提供公开仓库的最小协作与安全执行入口。
定义：AGENTS.md 的精简执行索引，不替代完整 Git、隐私和测试规则。
范围包括：worktree、检查、PR 与私有材料边界的关键约束。
范围不包括：业务架构细节、真实样本、密钥、日志或内部设计文档。
使用与修改规则：与 AGENTS.md 保持一致；规则冲突时以 AGENTS.md 和 CI 门禁为准。
-->

# Claude Rules

1. 将本仓库视为唯一日常代码仓库；只使用公开 `origin`，不添加或操作旧私有仓库 remote。
2. 从 `origin/main` 建立 `feat/*`、`fix/*` 或 `chore/*` worktree；不在 `main` 直接开发。
3. 修改后运行 `make ci`；后端改动额外检查 `/health`，结果页改动检查 `/sample`。
4. 仅推送功能分支并通过 PR squash merge 到 `main`；禁止日常推送 `main`、强推、`reset --hard`、`clean` 和批量删除。
5. 私有 JD、golden、日志、workbench、内部文档、密钥和本机绝对路径不得进入 Git。离线 Loop 只在本机运行；新 linked worktree 先运行 `python3 skills/ai-pm-jd-analyzer/tools/init_local_skill_loop.py` 创建忽略的本地实例，结果以最小公开代码改动进入新的 `feat/*` 分支。

完整规则、公开边界和回退约束见 [AGENTS.md](AGENTS.md)。

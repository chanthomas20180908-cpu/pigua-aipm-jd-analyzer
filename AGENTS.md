<!--
目的：为公开仓库中的 Agent 与开发协作者提供单仓库开发、发布和数据安全规则。
定义：公开代码仓库的协作约束真源，覆盖 Git、worktree、CI 与私有材料边界。
范围包括：日常开发分支、PR、公开 CI、本机私有材料和离线 Loop 的使用规则。
范围不包括：真实 JD、golden、日志、内部设计文档、密钥或旧私有仓库的实现细节。
使用与修改规则：协作流程或公开边界变化时同步本文件、CLAUDE.md、README.md 和边界校验测试。
-->

# AGENTS.md

## Repository Role

本仓库是 AI PM JD Analyzer 的唯一日常代码仓库，也是唯一允许配置的 Git `origin`。旧私有仓库仅保留为历史档案：禁止在其中创建新功能分支、推送新提交，或将其添加为本仓库 remote。

真实 JD、简历、golden、内部设计、实验日志、workbench 产物和密钥均属于私有材料，必须放在本仓库之外或保持本地忽略；不得强制添加、复制或通过提交信息泄露。

## Branch and Worktree Workflow

1. 从干净的 `origin/main` 创建独立 worktree：`feat/<slug>`、`fix/<slug>` 或 `chore/<slug>`。
2. 每个任务只在其 worktree 内修改；`.worktrees/` 是本地忽略目录。
3. 运行 `make ci`，按改动类型补充 `/health`、`/sample` 或浏览器验收。
4. 提交明确文件，推送功能分支，创建以 `main` 为目标的 PR。
5. CI 通过并审阅后使用 squash merge；合并后本地执行 `git pull --ff-only origin main`。

禁止日常 `git push origin main`、强推、`git reset --hard`、`git clean`、批量删除分支或 worktree。所有 Git 写操作、推送、PR 创建和远端合并前均需说明目标、影响范围和原因。

## Iteration and Private Inputs

离线 Evaluator–Optimizer Loop 只能使用本机私有输入运行。`loop/<run-id>` 及 run worktree 仅是本地实验产物，不得推送。实验结论需要进入公开代码时，只提取最小且不含私有数据的 prompt/code delta，放入新的 `feat/*` 分支并走完整 CI/PR。

## Public Boundary Gate

`make ci` 会先执行 `scripts/verify_public_boundary.py`。已跟踪文件不得位于 `data/`、`docs/`、`logs/`、`workbench/`、`.agents/` 或 `.worktrees/`，也不得包含实际 API key、私钥或本机绝对路径。

`AGENTS.md` 与 `CLAUDE.md` 是可提交的脱敏规则；不得在其中写入私有路径、样本内容、日志片段或内部实验原文。

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

## Browser CDP Operation

用户明确说“直接操作浏览器”、要求提交网页表单，或要求操作已登录网站时，使用 Chrome CDP；这不是桌面鼠标控制，也不会扩大用户对外部动作的授权范围。

1. 先读取 `web-access` Skill。以宿主机权限运行 `bash ~/.claude/skills/web-access/scripts/check-deps.sh`，再使用 `curl --noproxy '*'` 访问本地代理 `http://127.0.0.1:3456`。不要因为 sandbox 中端口不可达而要求用户提供新的端点。
2. 优先用 `GET /health` 验证代理。若代理不可达，以宿主机权限启动 `node ~/.claude/skills/web-access/scripts/cdp-proxy.mjs` 并复用已有实例；不得强制停止已有代理。
3. 只用 `GET /new?url=...` 创建并操作自己的后台标签页。不要枚举、读取、点击或关闭用户已有标签页；目标失效时新建自己的标签页，不用 `/targets` 探查用户页面。
4. 只读取完成当前任务所需的目标页公开可见内容。不得读取、导出或复述 Cookie、localStorage、sessionStorage、密码、自动填充数据或其他站点数据；不使用桌面鼠标或键盘控制。
5. 对登录、授权、提交、发布、删除、购买、发帖等外部效果动作，仍须先给出“目标 / 影响 / 原因”三行预告。创建后台页、仅读公开页面元数据和关闭自己创建的页也要说明动作范围。
6. `POST /eval?target=<targetId>` 的请求体必须是原始 JavaScript 表达式，并且只返回可序列化值；不要发送 JSON 包装、DOM 节点或从其他页面复制的固定选择器。
7. `/eval` 返回 400 时，不要用 `curl -f` 隐藏响应，也不要把它误判为目标网站拒绝。先读取代理错误体，核对当前 `targetId` 和原始 JavaScript 请求体；按 `web-access` 的 CDP API 格式重试。若 target 已失效，关闭或忽略它并新建自己的后台页。
8. 完成后用 `GET /close?target=<targetId>` 关闭自己创建的后台标签页。公开视频页面可读取标题、发布日期、时长等可见元数据；不得订阅、评论、点赞、上传或执行其他写操作，除非用户明确要求。

## Iteration and Private Inputs

离线 Evaluator–Optimizer Loop 只能使用本机私有输入运行。`loop/<run-id>` 及 run worktree 仅是本地实验产物，不得推送。实验结论需要进入公开代码时，只提取最小且不含私有数据的 prompt/code delta，放入新的 `feat/*` 分支并走完整 CI/PR。

进行本机私有实验前，如存在本地忽略的 Agent 指引，必须先读取其有效 `AGENTS.md`；该指引可补充实验协议，但不得放宽本文件的公开边界、Git 安全或数据保护规则。

新 linked worktree 进行 Skill loop 时，先运行 `python3 skills/ai-pm-jd-analyzer/tools/init_local_skill_loop.py`。该工具从公开、脱敏模板创建 `.agents/skill-loop/` 本地实例；真实 JD、报告、评价、状态和 round 记录保持忽略，不得通过 Git 在 worktree 或分支之间传递。需要保留实验历史时，在移除 worktree 前手动复制 `.agents/` 到本机私有位置。

## Public Boundary Gate

`make ci` 会先执行 `scripts/verify_public_boundary.py`。已跟踪文件不得位于 `data/`、`docs/`、`logs/`、`workbench/`、`.agents/` 或 `.worktrees/`，也不得包含实际 API key、私钥或本机绝对路径。

`AGENTS.md` 与 `CLAUDE.md` 是可提交的脱敏规则；不得在其中写入私有路径、样本内容、日志片段或内部实验原文。

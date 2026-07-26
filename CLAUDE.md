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

完整 Git、公开边界和回退约束见 `AGENTS.md`。

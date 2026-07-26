<!--
目的：让公开仓库访问者快速理解并安装 AI PM JD Analyzer Skill。
定义：公开展示仓库的主入口，说明 Skill 用法、Web 工具边界和本地验证方式。
范围包括：
- Codex 与 Claude Code 的安装方式、Skill 能力和可验证的工程实现。
- 可选的 FastAPI 与可视化 Web 工具说明。
范围不包括：
- 不包含内部设计文档、运行日志、真实 JD、简历、评测原始数据或 Agent 上下文。
- 不承诺线上用户效果、商业结果或未经验证的准确率。
使用与修改规则：
- 保持 Skill 安装命令、目录结构和 `make ci` 说明与代码同步。
- 仅陈述能由当前公开代码与测试验证的能力。
-->

# Pigua | AI PM JD Analyzer

An open-source, local-first Agent Skill for AI product manager, Agent, and data-platform job descriptions. It turns a JD into an evidence-grounded business model, risk signals, and interview questions.

面向 AI 产品经理、Agent 和数据平台岗位的本地 Agent Skill：将 JD 转化为岗位业务模型、风险判断和面试追问。

[![Python](https://img.shields.io/badge/Python-3.11-3776ab)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com/)
[![CI](https://github.com/chanthomas20180908-cpu/pigua-aipm-jd-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/chanthomas20180908-cpu/pigua-aipm-jd-analyzer/actions/workflows/ci.yml)

![劈瓜项目预览](static/assets/hero-screenshot.png)

## English quick start

The Skill package lives in `skills/ai-pm-jd-analyzer/`. It runs locally, needs no API key, does not browse the web, and does not call this repository's Web API.

```bash
# Codex
cp -R skills/ai-pm-jd-analyzer ~/.codex/skills/

# Claude Code
cp -R skills/ai-pm-jd-analyzer ~/.claude/skills/
```

Start a new session and use a prompt such as:

```text
Use $ai-pm-jd-analyzer to analyze the following job description. Write the report in English:

[paste the job description]
```

The default workflow saves `report.md` and `report.html` under `.agents/ai-pm-jd-reports/` in the current working directory. Use a private local working directory for real job descriptions; do not run it from a company repository, synced folder, or other managed location.

The Chinese documentation and full project details continue below.

## 工程实现与验证边界

- **双轨评测机制**：离线 Evaluator–Optimizer Loop 支持将回归集与能力集分开评估，并用回归保护避免能力爬坡掩盖退化；公开仓库不包含私有评测数据。
- **历史 MVP 回归实验**：旧私有原型的 5-case 回归 run 将 `element_modeling` 最佳 score 从 **0.9333 提升到 0.9500**，且无 timeout 或执行失败。该 run 未包含 capability 集，不能视作双轨 combined score；完整口径见[脱敏验证摘要](HISTORICAL_MVP_VALIDATION.md)。
- **产品化链路**：提供 FastAPI 服务、JSON/Markdown 结果导出、`.txt` / `.md` / `.docx` 输入、本地 `make ci` 与冻结的 `/sample` 前端验收样例。历史 Loop [流程图源码](static/loop-648097f5ed-report.html)可在本地启动服务后打开渲染版。

上述历史实验不是模型准确率、线上用户效果或商业指标，也不代表当前公开提交可复现相同分数。

## 使用 Skill

Skill 源包位于 `skills/ai-pm-jd-analyzer/`，无需 API Key、无需联网，也不调用本仓库的 Web API。

```bash
# Codex
cp -R skills/ai-pm-jd-analyzer ~/.codex/skills/

# Claude Code
cp -R skills/ai-pm-jd-analyzer ~/.claude/skills/
```

在对应工具中开启新会话后，使用：

```text
$ai-pm-jd-analyzer
```

### 本地 Skill 迭代

需要在新 linked worktree 中用私有 JD 迭代 Skill 时，先初始化被 Git 忽略的本地 loop 骨架：

```bash
python3 skills/ai-pm-jd-analyzer/tools/init_local_skill_loop.py
```

该命令只复制脱敏流程模板、状态和单 case 执行指令；真实 JD、报告、人工评价与 round 记录仍只留在 `.agents/`，不会进入 commit 或远端。

## Skill 能做什么

- 将 JD 拆解为价值流、工作事项、业务实体、能力与角色责任。
- 区分明确事实、谨慎推断和未披露信息，避免根据职位名称臆测完整 AI 生命周期。
- 识别伪 AI、职责失衡、责任甩锅和关键边界缺失等风险。
- 生成面向面试准备的核验问题；不做简历匹配、投递建议或公司联网调研。
- 用户明确指定输出路径时，生成不依赖网络的完整元模型图谱报告。

## Web 工具实现

仓库同时包含 FastAPI + D3.js 的产品化探索：输入 JD 后展示岗位建模、核心判断、风险质检和口语化总结。Web 工具调用模型服务时需要通过环境变量配置 API Key；Skill 本身不需要。

```bash
python3 -m pip install -r requirements.txt
make dev
```

本地访问 `http://127.0.0.1:8000`，运行 `make ci` 执行编译、工作流、前端、Makefile 可移植性和 Skill 结构检查。`/sample` 使用冻结 fixture 验收结果页，不调用 LLM，也不写入浏览器历史记录。

## 协作与安全边界

- [AGENTS.md](AGENTS.md) 是公开仓库的完整开发、分支、PR、worktree 和私有材料边界规则；[CLAUDE.md](CLAUDE.md) 提供 Claude Code 的最小执行入口。
- 本仓库是唯一日常代码仓库，只配置一个公开 `origin`；历史私有仓库只作归档，禁止作为新功能开发或新增远端。
- `make ci` 先校验公开边界，再运行编译和测试；被 Git 跟踪的私有目录、密钥值和本机绝对路径会导致检查失败。

## 公开仓库边界

- 不包含运行日志、真实 JD/简历、评测原始数据、内部文档或 Agent 上下文。
- 不将离线评测或结构测试表述为用户效果、准确率或商业成果。
- API Key 仅通过本地环境变量注入，禁止写入仓库。

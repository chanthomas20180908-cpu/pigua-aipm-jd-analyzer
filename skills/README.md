<!--
目的：集中存放可独立分发、可由多个 Agent 工具使用的项目 Skill 源包。
定义：仓库级 Skill 根目录；每个子目录都是一个自包含的 Skill 包。
范围包括：
- Skill 的 SKILL.md、agents 元数据、references 与本地辅助工具。
- 同时面向 Codex 与 Claude Code 的可复制 Skill 源包。
范围不包括：
- 不放应用业务源码、运行日志、用户安装副本或生成报告。
- 不作为 .agents/、.claude/ 或用户主目录下安装位置的镜像。
使用与修改规则：
- 每个 Skill 使用小写连字符目录名，并保持 SKILL.md 与所有相对引用自包含。
- Codex 安装到 ~/.codex/skills/；Claude Code 安装到 ~/.claude/skills/；安装副本不得回写本目录。
- 修改 Skill 后运行对应结构测试与 Skill 校验脚本。
-->

# skills 目录说明

## 目的

集中存放可独立分发、可由多个 Agent 工具使用的项目 Skill 源包。

## 定义

仓库级 Skill 根目录；每个子目录都是一个自包含的 Skill 包。

## 范围包括

- Skill 的 `SKILL.md`、`agents/` 元数据、`references/` 与本地辅助工具。
- 可复用、脱敏的本地实验模板；真实实验实例仍在各 worktree 的忽略 `.agents/` 目录。
- 同时面向 Codex 与 Claude Code 的可复制 Skill 源包。

## 范围不包括

- 不放应用业务源码、运行日志、用户安装副本或生成报告。
- 不作为 `.agents/`、`.claude/` 或用户主目录下安装位置的镜像。

## 使用与修改规则

- 每个 Skill 使用小写连字符目录名，并保持 `SKILL.md` 与所有相对引用自包含。
- Codex 安装到 `~/.codex/skills/`；Claude Code 安装到 `~/.claude/skills/`；安装副本不得回写本目录。
- 修改 Skill 后运行对应结构测试与 Skill 校验脚本。

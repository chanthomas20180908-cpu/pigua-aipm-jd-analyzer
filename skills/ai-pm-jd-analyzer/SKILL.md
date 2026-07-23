---
name: ai-pm-jd-analyzer
description: Analyze AI product manager, Agent, data-platform, and related product job descriptions using an evidence-based business meta-model. Use when an agent needs to explain what a JD actually requires, model value streams, work items, entities and capabilities, identify pseudo-AI or role-overload signals, or draft targeted interview questions. Do not use for resume matching, job application decisions, company web research, or running the repository API.
---

<!--
目的：提供无需外部 API 的 AI PM JD 自主分析工作流。
定义：可独立安装的 Agent skill，以本地 Agent 能力和内置参考资料完成岗位建模与判断。
范围包括：JD 事实提取、业务建模、风险判断和面试追问。
范围不包括：简历匹配、联网调研、启动本项目服务、调用 v4 工作流或写入 trace。
使用与修改规则：先读取下列 references；保持本地分析、证据优先和报告契约，规则更新时同步复核静态测试与人工验收。
-->

# AI PM JD Analyzer

Read these references before analyzing:

1. `references/meta-model.md`
2. `references/modeling-rules.md`
3. `references/full-model-schema.json`
4. `references/full-model-report-contract.md`

## Boundaries

- Analyze only JD text supplied by the user or read from a local file the user identifies.
- Do not browse, call APIs, start this repository's service, invoke its Python workflow, request API keys, or write trace logs.
- Do not assess a candidate, recommend applying, or infer undisclosed company facts.
- Ask for JD text when it is missing. Ask one focused question only when a missing detail would materially alter the requested analysis.
- Keep internal reasoning private. Show source evidence, explicit uncertainty, and concise reasons in the report instead.
- This skill's complete reference meta-model is a standalone analysis contract. It is not the `/analyze/v4` response schema and must not be described as a live API result.

## Analysis guidance

Choose and adapt the order of work to the JD; this is guidance, not a forced pipeline.

1. Separate explicit JD facts, cautious inferences, and not-disclosed fields.
2. Build every top-level section required by `full-model-schema.json`; mark unavailable fields as `not_disclosed` instead of inventing facts.
3. Give every named model node a concise business `description`. Model each business entity as an actionable object; put JD-supported metrics, states, quality dimensions, and costs in that entity's `attributes` instead of promoting them to entities.
4. Connect value streams, work items, roles, business entities, CRUD operations, capabilities, requirements, environment, compensation, and risks only when evidence supports them. If an explicit metric needs a result object but the JD does not name one, infer the smallest such entity and mark it `inferred`.
5. Validate entity ownership, reciprocal capability `primary_entity_ids`, controlled relationship vocabulary, RACI attribution, and requirement mappings against the rules before writing the report.
6. Render the Markdown report and its JSON appendix from the same normalized v2 model.

For a short or vague JD, retain the complete top-level model structure while marking missing fields `not_disclosed` and emphasizing what must be confirmed. Never invent a complete AI lifecycle merely because the title contains AI.

## Output

Write the report in Chinese unless the user requests another language. Follow `references/full-model-report-contract.md` exactly for a default full analysis. For a focused request, retain a conclusion, evidence boundary, and the complete JSON appendix.

## Automatic local delivery

Every default analysis must be persisted locally before replying. Create one new, non-overwriting directory under the caller's current working directory:

```text
.agents/ai-pm-jd-reports/<unique-run-id>/
  report.md
  report.html
```

1. Generate the complete Markdown report according to the contract and write its exact original content to `report.md`.
2. Run the bundled local renderer relative to this `SKILL.md`:

```bash
python3 <skill-root>/tools/render_full_model_report.py report.md --output report.html
```

3. Reply with the one-sentence conclusion and the two saved paths. Do not repeat the full report in chat after it has been saved.

- The run ID must be unique; never overwrite an existing report directory or file.
- The renderer reads only `report.md`'s unique JSON appendix and title summary. It does not call APIs, start services, or read original JD files, prompts, traces, or logs.
- If writing the Markdown file or rendering HTML fails, report the exact local failure. Do not claim that both artifacts were saved.

## Local iteration bootstrap

For maintainers running private Skill iterations in a new linked worktree, initialize a fresh ignored loop instance before adding private cases:

```bash
python3 <skill-root>/tools/init_local_skill_loop.py
```

The initializer creates only a sanitized `.agents/skill-loop/` skeleton and refuses to overwrite an existing instance. It does not copy JD inputs, reports, reviews, or histories between worktrees.

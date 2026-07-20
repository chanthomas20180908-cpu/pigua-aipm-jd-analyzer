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
3. Connect value streams, work items, roles, business entities, CRUD operations, capabilities, requirements, environment, compensation, and risks only when evidence supports them.
4. Validate entity ownership, controlled relationship vocabulary, RACI attribution, and requirement mappings against the rules before writing the report.
5. Render the Markdown report and its JSON appendix from the same normalized model.

For a short or vague JD, retain the complete top-level model structure while marking missing fields `not_disclosed` and emphasizing what must be confirmed. Never invent a complete AI lifecycle merely because the title contains AI.

## Output

Write the report in Chinese unless the user requests another language. Follow `references/full-model-report-contract.md` exactly for a default full analysis. For a focused request, retain a conclusion, evidence boundary, and the complete JSON appendix.

## Optional visual delivery

When the user explicitly requests a saved visual report and gives an output path, first write the complete Markdown report, then run the bundled local renderer relative to this `SKILL.md`:

```bash
python3 <skill-root>/tools/render_full_model_report.py report.md --output report.html
```

- This is optional, not part of the default chat/report output. Do not create files unless the user explicitly requests them and identifies an output path.
- The renderer reads only the report's unique JSON appendix and title summary; it does not call APIs, start services, or read original JD files, prompts, traces, or logs.
- It refuses to overwrite an existing file unless the user explicitly asks for `--force`.

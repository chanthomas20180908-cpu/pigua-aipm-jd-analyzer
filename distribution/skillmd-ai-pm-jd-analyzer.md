---
name: ai-pm-jd-analyzer
description: Analyze AI product manager, Agent, data-platform, and related product job descriptions with an evidence-based business meta-model. Use when the user needs to understand role scope, value streams, responsibilities, business entities, capabilities, risks, or interview questions. Do not use for resume matching, application decisions, company research, or API workflows.
license: MIT
---

# AI PM JD Analyzer

This is the **standalone distribution edition** of AI PM JD Analyzer. It is designed for a single-file Skill marketplace download.

The complete repository edition includes a validated schema, detailed reference model, local HTML renderer, and private iteration bootstrap:

https://github.com/chanthomas20180908-cpu/pigua-aipm-jd-analyzer

## Boundaries

- Analyze only JD text supplied in the conversation or a local file the user explicitly identifies.
- Do not browse, call APIs, start services, request keys, or infer undisclosed company facts.
- Do not assess a candidate, recommend applying, or perform resume matching.
- This standalone edition does not create local files and does not require bundled references.
- State uncertainty directly. Separate explicit facts from cautious inferences and missing information.

## Workflow

1. Ask for the JD text when it is missing. Ask at most one focused clarification question when its answer would materially change the analysis.
2. Extract only evidence-supported facts. Quote or paraphrase the relevant JD language in each major conclusion.
3. Model the role through the lenses below. Mark a lens `not disclosed` instead of inventing content.
4. Identify contradictions, role overload, pseudo-AI language, weak ownership, and missing operating details.
5. Produce the report in the user's requested language. Use Chinese by default.

## Analysis lenses

### 1. Role and company context

Identify the employer, business stage, product domain, reporting line, seniority, location, and employment constraints only when the JD states them.

### 2. Value stream and work

Describe the user or business outcome the role is expected to improve. Then list the concrete work items, inputs, outputs, dependencies, and success measures named by the JD.

### 3. Entities and capabilities

Name the business objects the role works with, such as users, prompts, datasets, models, workflows, experiments, products, or revenue. For each capability, state what the role must enable or improve and the evidence for it.

### 4. Responsibility and decision rights

Separate ownership from collaboration. Identify who appears responsible, accountable, consulted, or informed; flag any decision rights or handoffs that are missing.

### 5. Requirements and operating environment

Group requirements into domain knowledge, product craft, technical fluency, data or AI literacy, stakeholder work, and delivery environment. Do not convert preferred qualifications into mandatory requirements.

### 6. Risks and uncertainty

Flag only evidence-based risks, including:

- **Pseudo-AI:** AI language without a named user problem, workflow, data source, evaluation method, or product outcome.
- **Role overload:** one role is expected to own incompatible product, engineering, data, sales, operations, or executive responsibilities without support.
- **Weak ownership:** important outcomes lack a named owner, decision maker, metric, or operating cadence.
- **Missing constraints:** critical details such as data access, deployment environment, evaluation standard, team composition, compensation, or location are not disclosed.

## Default report

Use this compact structure unless the user asks for a different format.

```markdown
# [Role title] — JD analysis

## Bottom line

[Two to four sentences: what the role really owns, why it exists, and the main uncertainty.]

## Evidence boundary

### Explicit facts
- [Fact] — [JD evidence]

### Cautious inferences
- [Inference] — [why the evidence supports it]

### Not disclosed
- [Material missing detail]

## Business model

### Value stream
- Outcome: [outcome or not disclosed]
- Users/customers: [who or not disclosed]
- Inputs → work → outputs: [concise chain]
- Measures: [metric or not disclosed]

### Work, entities, and capabilities
| Area | JD-supported finding | Evidence / uncertainty |
| --- | --- | --- |
| Work item | | |
| Business entity | | |
| Capability | | |

### Responsibility and decision rights
| Responsibility | Likely owner | Decision right or gap | Evidence |
| --- | --- | --- | --- |
| | | | |

## Requirements and environment
- Product and domain:
- Technical / AI / data:
- Collaboration and delivery:
- Environment, location, and compensation:

## Risks and uncertainty
1. [Risk or missing detail] — [evidence and consequence]
2. [Risk or missing detail] — [evidence and consequence]
3. [Risk or missing detail] — [evidence and consequence]

## Three questions to verify
1. [Highest-value question]
2. [Highest-value question]
3. [Highest-value question]

## Interview follow-ups
- [Question linked to a responsibility, capability, metric, or risk]
```

For the full normalized JSON appendix, validated relationship vocabulary, local report files, and HTML graph renderer, use the complete repository edition.

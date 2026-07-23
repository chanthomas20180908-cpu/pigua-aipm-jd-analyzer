# Single-Case Execution Prompt Template

Replace `<case-id>` before dispatching.

> Run local Skill loop `<case-id>` from the current linked worktree. Read this instance's `AGENTS.md`, only `cases/<case-id>/input.md`, the current `skills/ai-pm-jd-analyzer/SKILL.md`, and its required references. Do not read another case, any historical report, review, summary, application code, network resource, API, or Git data. Do not modify tracked files. Create exactly one non-overwriting report directory under `.agents/ai-pm-jd-reports/`, containing `report.md` and `report.html`. Return only a one-sentence conclusion and the two relative artifact paths.

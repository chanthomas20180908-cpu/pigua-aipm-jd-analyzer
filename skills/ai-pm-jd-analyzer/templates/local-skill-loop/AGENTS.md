# Local Skill Loop Rules

This local-only instance evaluates the current `ai-pm-jd-analyzer` Skill without adding private material to Git.

## Boundaries

- Keep actual JD inputs, reports, reviews, logs, and run state under `.agents/` only.
- The tested rule source is `skills/ai-pm-jd-analyzer/`; do not create prompt copies or modify application code during a Skill loop.
- Every case executor reads only its assigned case, the current Skill, and the Skill's required references.
- A case executor must not read other cases, prior reports, reviews, summaries, network resources, APIs, Git, or application workflows.
- A case executor writes only one non-overwriting `report.md` and `report.html` pair beneath `.agents/ai-pm-jd-reports/`.

## Round Protocol

1. The root coordinator records the current Skill commit, enabled case IDs, and validation outcomes in a new round directory.
2. Run cases serially unless a separate performance experiment is explicitly declared.
3. Validate each report's JSON appendix with the current full-model schema and bundled renderer before human review.
4. Preserve the user's review verbatim. Modify the Skill only after feedback identifies a concrete defect.
5. Before deleting this worktree, manually copy `.agents/` elsewhere if the private experiment history must be retained.

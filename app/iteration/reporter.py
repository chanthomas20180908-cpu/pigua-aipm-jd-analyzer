"""目的：生成迭代 Loop 的人类可读报告。

定义：把 TrialResult 和 LoopReport 落盘为 Markdown 和 promotion 清单。

范围包括：
- baseline/best 对比、case 级结果、失败归因和预算摘要。

范围不包括：
- 不执行 Git merge，不应用 promotion，不修改生产配置。

使用与修改规则：
- 报告字段应保持稳定，便于后续人工 review 或自动解析。
"""

from __future__ import annotations

from pathlib import Path

from app.iteration.models import LoopReport, TrialResult


class Reporter:
    def write(self, report: LoopReport) -> Path:
        report.output_dir.mkdir(parents=True, exist_ok=True)
        path = report.output_dir / "report.md"
        path.write_text(self._render_report(report), encoding="utf-8")
        promotion = report.output_dir / "PROMOTION.md"
        promotion.write_text(self._render_promotion(report), encoding="utf-8")
        report.promotion_path = promotion
        return path

    def _render_report(self, report: LoopReport) -> str:
        lines = [
            "# Iteration Loop Report",
            "",
            f"- run_id: `{report.run_id}`",
            f"- target: `{report.target}`",
            f"- stopped_reason: `{report.stopped_reason}`",
            "",
        ]
        if report.best_trial:
            lines.extend(
                [
                    "## Best Trial",
                    "",
                    _trial_summary(report.best_trial),
                    "",
                ]
            )
        lines.extend(["## Score Tracks", ""])
        for trial in report.trials:
            lines.append(
                f"- iteration `{trial.iteration}` regression={trial.regression_score:.3f} "
                f"capability={trial.capability_score:.3f} combined={trial.score:.3f} "
                f"timeouts={trial.timeout_case_count} execution_failures={trial.failed_execution_case_count}"
            )
        lines.append("")
        lines.extend(["## Trials", ""])
        for trial in report.trials:
            lines.extend([_trial_summary(trial), ""])
            if trial.regression_results:
                lines.append("### Regression Cases")
                _append_cases(lines, trial.regression_results)
                lines.append("")
            if trial.capability_results:
                lines.append("### Capability Cases")
                _append_cases(lines, trial.capability_results)
                lines.append("")
            if not trial.regression_results and not trial.capability_results:
                _append_cases(lines, trial.case_results)
                lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _render_promotion(self, report: LoopReport) -> str:
        best = report.best_trial
        lines = [
            "# Promotion Checklist",
            "",
            "本文件只记录离线 loop 的推广建议；应用到主工作区前需要人工确认。",
            "",
        ]
        if not best:
            lines.append("No successful or evaluated trial.")
            return "\n".join(lines) + "\n"
        lines.extend(
            [
                f"- best_variant: `{best.variant.id}`",
                f"- target: `{best.variant.target}`",
                f"- score: `{best.score:.3f}`",
                f"- passed: `{best.passed}`",
                "",
                "## Suggested Prompt Delta",
                "",
                "```text",
                best.variant.system_prompt_suffix.strip() or "(baseline, no prompt delta)",
                "```",
                "",
                "## Manual Checks",
                "",
                "- Review schema compatibility with `static/graph-renderer.js` when target is `element_modeling`.",
                "- Re-run regression cases before applying to production prompt.",
                "- Do not push or merge without explicit approval.",
            ]
        )
        return "\n".join(lines) + "\n"


def _append_cases(lines: list[str], cases: list[object]) -> None:
    for case in cases:
        status = "PASS" if case.passed else "FAIL"
        lines.append(f"- `{case.case_id}` {status} score={case.score:.3f} metrics={case.metrics}")
        if case.trace_log_path:
            lines.append(f"  - trace: `{case.trace_id}` `{case.trace_log_path}`")
        for reason in case.failure_reasons:
            lines.append(f"  - {reason}")


def _trial_summary(trial: TrialResult) -> str:
    return (
        f"### Iteration {trial.iteration}: `{trial.variant.id}`\n\n"
        f"- description: {trial.variant.description}\n"
        f"- score: `{trial.score:.3f}`\n"
        f"- passed: `{trial.passed}`\n"
        f"- timeout_case_count: `{trial.timeout_case_count}`\n"
        f"- failed_execution_case_count: `{trial.failed_execution_case_count}`\n"
        f"- error_type_counts: `{trial.error_type_counts}`\n"
        f"- timing_summary: `{trial.timing_summary}`\n"
        f"- budget: `{trial.budget_snapshot}`"
    )

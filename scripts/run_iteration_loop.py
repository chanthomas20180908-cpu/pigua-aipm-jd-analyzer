"""目的：运行 v4 prompt/code 离线迭代 Loop。

定义：命令行入口，负责解析参数、启动 IterationController 并生成报告。

范围包括：
- target、case 目录、golden 目录、预算参数和报告输出目录。

范围不包括：
- 不启动 Web 服务，不自动提交、不 push、不把最佳变体写回生产 prompt。

使用与修改规则：
- 从项目根目录运行；新增参数需同步 docs/loop-design.md。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.iteration.controller import IterationController
from app.iteration.loop_config import apply_overrides, load_loop_config
from app.iteration.models import EvalConfig, RunBudget
from app.iteration.reporter import Reporter


def main() -> int:
    args = parse_args()
    loop_config = apply_overrides(
        load_loop_config(args.config),
        {
            "capability_weight": args.capability_weight,
            "regression_floor": args.regression_floor,
            "score_threshold": args.score_threshold,
            "deterministic_threshold": args.deterministic_threshold,
            "run_llm_judge": args.llm_judge,
            "llm_call_timeout_seconds": args.llm_call_timeout_seconds,
            "case_timeout_seconds": args.case_timeout_seconds,
            "retry_count": args.retry_count,
            "retry_backoff_seconds": args.retry_backoff_seconds,
            "max_timeout_rate": args.max_timeout_rate,
            "max_iterations": args.max_iterations,
            "max_wall_seconds": args.max_wall_seconds,
            "max_llm_calls": args.max_llm_calls,
            "max_input_tokens": args.max_input_tokens,
            "max_output_tokens": args.max_output_tokens,
            "budget_usd": args.budget_usd,
            "stop_after_no_improvement": args.stop_after_no_improvement,
        },
    )
    if loop_config.max_iterations < 1:
        print("error: --max-iterations must be >= 1", file=sys.stderr)
        return 2
    if loop_config.stop_after_no_improvement < 0:
        print("error: --stop-after-no-improvement must be >= 0", file=sys.stderr)
        return 2
    try:
        _validate_input_dirs(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    eval_config = EvalConfig(
        target=args.target,
        cases_dir=args.cases,
        golden_dir=args.golden_dir,
        regression_dir=args.regression_eval,
        capability_dir=args.capability_eval,
        output_dir=args.output_dir,
        capability_weight=loop_config.capability_weight,
        regression_floor=loop_config.regression_floor,
        score_threshold=loop_config.score_threshold,
        deterministic_threshold=loop_config.deterministic_threshold,
        run_llm_judge=loop_config.run_llm_judge,
        llm_call_timeout_seconds=loop_config.llm_call_timeout_seconds,
        case_timeout_seconds=loop_config.case_timeout_seconds,
        retry_count=loop_config.retry_count,
        retry_backoff_seconds=loop_config.retry_backoff_seconds,
        max_timeout_rate=loop_config.max_timeout_rate,
    )
    budget = RunBudget(
        max_iterations=loop_config.max_iterations,
        max_wall_seconds=loop_config.max_wall_seconds,
        max_llm_calls=loop_config.max_llm_calls,
        max_input_tokens=loop_config.max_input_tokens,
        max_output_tokens=loop_config.max_output_tokens,
        max_cost_usd=loop_config.budget_usd,
        stop_after_no_improvement=loop_config.stop_after_no_improvement,
    )
    controller = IterationController(eval_config=eval_config, budget=budget)
    report = controller.run()
    report_path = Reporter().write(report)
    print(f"run_id={report.run_id}")
    print(f"best_score={report.best_trial.score:.3f}" if report.best_trial else "best_score=0.000")
    print(f"stopped_reason={report.stopped_reason}")
    print(f"report={report_path}")
    print(f"promotion={report.promotion_path}")
    if args.cleanup:
        from app.iteration.worktree_manager import WorktreeManager

        WorktreeManager(repo_root=ROOT).remove(run_id=report.run_id, force=False)
    return 0 if report.best_trial and report.best_trial.passed else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run v4 iteration loop.")
    parser.add_argument("--target", default="element_modeling")
    parser.add_argument("--cases", type=Path, default=Path("data/test_cases_v1/cases"))
    parser.add_argument("--regression-eval", type=Path, default=None)
    parser.add_argument("--capability-eval", type=Path, default=None)
    parser.add_argument("--golden-dir", type=Path, default=Path("data/test_cases_v1/v4_golden"))
    parser.add_argument("--config", type=Path, default=Path("app/iteration/loop_config.py"))
    parser.add_argument("--capability-weight", type=float, default=None)
    parser.add_argument("--regression-floor", type=float, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("workbench/runs"))
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--max-wall-seconds", type=int, default=None)
    parser.add_argument("--max-llm-calls", type=int, default=None)
    parser.add_argument("--max-input-tokens", type=int, default=None)
    parser.add_argument("--max-output-tokens", type=int, default=None)
    parser.add_argument("--budget-usd", type=float, default=None)
    parser.add_argument("--stop-after-no-improvement", type=int, default=None)
    parser.add_argument("--score-threshold", type=float, default=None)
    parser.add_argument("--deterministic-threshold", type=float, default=None)
    parser.add_argument("--llm-call-timeout-seconds", type=float, default=None)
    parser.add_argument("--case-timeout-seconds", type=float, default=None)
    parser.add_argument("--retry-count", type=int, default=None)
    parser.add_argument("--retry-backoff-seconds", type=float, default=None)
    parser.add_argument("--max-timeout-rate", type=float, default=None)
    parser.add_argument("--llm-judge", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--cleanup", action="store_true")
    return parser.parse_args()


def _validate_input_dirs(args: argparse.Namespace) -> None:
    if args.regression_eval is None and args.capability_eval is None:
        raise ValueError("must provide at least one of --regression-eval or --capability-eval")

    required = {
        "--cases": args.cases,
        "--golden-dir": args.golden_dir,
        "--output-dir": args.output_dir,
    }
    optional = {
        "--regression-eval": args.regression_eval,
        "--capability-eval": args.capability_eval,
    }
    for label, path in required.items():
        if path is None:
            continue
        if label == "--output-dir":
            path.mkdir(parents=True, exist_ok=True)
        if not path.exists() or not path.is_dir():
            raise ValueError(f"{label} must be an existing directory: {path}")
    for label, path in optional.items():
        if path is not None and (not path.exists() or not path.is_dir()):
            raise ValueError(f"{label} must be an existing directory: {path}")

    _validate_case_dir("--cases", args.cases)
    if args.regression_eval is not None:
        _validate_case_dir("--regression-eval", args.regression_eval)
    if args.capability_eval is not None:
        _validate_case_dir("--capability-eval", args.capability_eval)
    if not any(args.golden_dir.glob("*_golden_v4.json")):
        raise ValueError(f"--golden-dir must contain *_golden_v4.json files: {args.golden_dir}")


def _validate_case_dir(label: str, path: Path) -> None:
    case_paths = sorted(path.glob("case_*.json"))
    if not case_paths:
        raise ValueError(f"{label} must contain case_*.json files: {path}")
    for case_path in case_paths[:3]:
        try:
            import json

            case = json.loads(case_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"{label} contains invalid JSON: {case_path}") from exc
        if not case.get("id") or not case.get("jd_file"):
            raise ValueError(f"{label} case files must include id and jd_file: {case_path}")


if __name__ == "__main__":
    raise SystemExit(main())

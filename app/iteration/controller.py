"""目的：编排 v4 Evaluator-Optimizer 离线循环。

定义：加载 case、执行工作流、评估输出、反思失败并生成下一轮候选。

范围包括：
- baseline 评估、候选迭代、预算检查、状态快照和报告对象生成。

范围不包括：
- 不自动推广 prompt 到生产库，不自动提交或 push。

使用与修改规则：
- run_with_config 是注入变体的唯一入口；线上 run() 默认行为保持不变。
"""

from __future__ import annotations

import copy
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, TypedDict
from uuid import uuid4

from app import llm_client
from app.config.workflow_v4 import WORKFLOW_V4_CONFIG
from app.iteration.budget_guard import BudgetGuard
from app.iteration.evaluator import V4Evaluator
from app.iteration.generator import VariantGenerator
from app.iteration.models import CaseEvalResult, EvalConfig, LoopReport, RunBudget, TrialResult, VariantSpec
from app.iteration.reflector import Reflector
from app.iteration.worktree_manager import WorktreeInfo, WorktreeManager
from app.sub_modules import SubModule
from app.sub_modules.library import SUB_MODULE_LIBRARY
from app.workflows.analyze_jd_v4 import run_with_config


class LoopState(TypedDict, total=False):
    iteration: int
    variant: VariantSpec
    trials: list[TrialResult]
    constraints: list[str]
    regression_cases: list[dict[str, Any]]
    capability_cases: list[dict[str, Any]]
    stopped_reason: str
    best_trial: TrialResult | None
    should_stop: bool
    node_trace: list[str]


class IterationController:
    def __init__(self, *, eval_config: EvalConfig, budget: RunBudget):
        self.eval_config = eval_config
        self.budget = budget
        self.output_dir = eval_config.output_dir
        self.run_id = uuid4().hex[:10]
        self.repo_root = Path.cwd()
        self.worktree_manager = WorktreeManager(repo_root=self.repo_root)
        self.run_worktree: WorktreeInfo | None = None
        self.generator = VariantGenerator(target=eval_config.target)
        self.reflector = Reflector()
        self.evaluator = V4Evaluator(
            target=eval_config.target,
            deterministic_threshold=eval_config.deterministic_threshold,
            run_llm_judge=eval_config.run_llm_judge,
            llm_call_timeout_seconds=eval_config.llm_call_timeout_seconds,
            retry_count=eval_config.retry_count,
            retry_backoff_seconds=eval_config.retry_backoff_seconds,
        )
        self.guard = BudgetGuard(budget=budget)

    def run(self) -> LoopReport:
        self.run_worktree = self._create_run_worktree()
        if self.run_worktree:
            self.output_dir = self.run_worktree.path / "workbench" / "runs"

        self._write_manifest()
        initial_state: LoopState = {
            "iteration": 0,
            "variant": self.generator.baseline(),
            "trials": [],
            "constraints": [],
            "regression_cases": self._load_cases(self.eval_config.regression_dir),
            "capability_cases": self._load_cases(self.eval_config.capability_dir)
            if self.eval_config.capability_dir
            else [],
            "stopped_reason": "",
            "best_trial": None,
            "should_stop": False,
            "node_trace": [],
        }
        final_state = self._run_state_graph(initial_state)
        trials = final_state.get("trials", [])
        best = final_state.get("best_trial") or (max(trials, key=lambda item: item.score) if trials else None)
        report = LoopReport(
            run_id=self.run_id,
            target=self.eval_config.target,
            best_trial=best,
            trials=trials,
            output_dir=self.output_dir / self.run_id,
            stopped_reason=final_state.get("stopped_reason") or "completed",
        )
        self._write_state(
            trials=trials,
            stopped_reason=report.stopped_reason,
            node_trace=final_state.get("node_trace", []),
            best_trial=best,
        )
        return report

    def _run_state_graph(self, state: LoopState) -> LoopState:
        if sys.version_info < (3, 10):
            logging.warning(
                "Python %s detected; langgraph is incompatible with this version. "
                "Falling back to plain-Python state graph.",
                sys.version.split()[0],
            )
            return self._run_state_graph_fallback(state)
        try:
            from langgraph.graph import END, StateGraph
        except Exception as exc:
            logging.warning(
                "Failed to import langgraph: %s. Falling back to plain-Python state graph.",
                exc,
            )
            return self._run_state_graph_fallback(state)

        graph = StateGraph(LoopState)
        graph.add_node("generate_variant", self._node_generate_variant)
        graph.add_node("run_trial", self._node_run_trial)
        graph.add_node("deterministic_eval", self._node_deterministic_eval)
        graph.add_node("llm_judge", self._node_llm_judge)
        graph.add_node("reflect", self._node_reflect)
        graph.add_node("prepare_promotion", self._node_prepare_promotion)

        graph.set_entry_point("generate_variant")
        graph.add_edge("generate_variant", "run_trial")
        graph.add_edge("run_trial", "deterministic_eval")
        graph.add_conditional_edges(
            "deterministic_eval",
            self._route_after_deterministic_eval,
            {"reflect": "reflect", "llm_judge": "llm_judge", "prepare_promotion": "prepare_promotion"},
        )
        graph.add_conditional_edges(
            "llm_judge",
            self._route_after_llm_judge,
            {"reflect": "reflect", "prepare_promotion": "prepare_promotion"},
        )
        graph.add_conditional_edges(
            "reflect",
            self._route_after_reflect,
            {"generate_variant": "generate_variant", "prepare_promotion": "prepare_promotion"},
        )
        graph.add_edge("prepare_promotion", END)
        app = graph.compile()
        return app.invoke(state, {"recursion_limit": max(20, self.budget.max_iterations * 8 + 8)})

    def _run_state_graph_fallback(self, state: LoopState) -> LoopState:
        while not state.get("should_stop"):
            state = self._node_generate_variant(state)
            state = self._node_run_trial(state)
            state = self._node_deterministic_eval(state)
            if self._route_after_deterministic_eval(state) == "llm_judge":
                state = self._node_llm_judge(state)
            if not state.get("should_stop"):
                state = self._node_reflect(state)
        return self._node_prepare_promotion(state)

    def _node_generate_variant(self, state: LoopState) -> LoopState:
        state["node_trace"] = [*state.get("node_trace", []), "generate_variant"]
        iteration = state.get("iteration", 0)
        if iteration == 0:
            state["variant"] = self.generator.baseline()
            return state
        state["variant"] = self.generator.next_variant(
            iteration=iteration,
            constraints=state.get("constraints", []),
            current_system_prompt=self._target_system_prompt(),
            scorer=self._score_variant_on_validation_set,
        )
        return state

    def _node_run_trial(self, state: LoopState) -> LoopState:
        state["node_trace"] = [*state.get("node_trace", []), "run_trial"]
        trial = self._run_trial(
            iteration=state.get("iteration", 0),
            variant=state["variant"],
            regression_cases=state.get("regression_cases", []),
            capability_cases=state.get("capability_cases", []),
        )
        trials = [*state.get("trials", []), trial]
        state["trials"] = trials
        self.guard.record_score(trial.score)
        best = state.get("best_trial")
        if best is None or trial.score > best.score:
            state["best_trial"] = trial
            self._promote_variant_to_run_worktree(trial.variant)
        self._write_state(
            trials=trials,
            stopped_reason=state.get("stopped_reason", ""),
            node_trace=state.get("node_trace", []),
            best_trial=state.get("best_trial"),
        )
        return state

    def _node_deterministic_eval(self, state: LoopState) -> LoopState:
        state["node_trace"] = [*state.get("node_trace", []), "deterministic_eval"]
        trial = state["trials"][-1]
        execution_failure_rate = _execution_failure_rate(trial)
        if execution_failure_rate > self.eval_config.max_timeout_rate:
            state["stopped_reason"] = "timeout_rate_exceeded"
            state["should_stop"] = True
            return state
        regression_scored_results = _scored_regression_results(trial.regression_results)
        regression_floor_score = _avg_score(regression_scored_results)
        if regression_scored_results and regression_floor_score < self.eval_config.regression_floor:
            state["stopped_reason"] = "regression_floor"
            state["should_stop"] = True
            return state
        deterministic_ok = not trial.failure_reasons and trial.score >= self.eval_config.deterministic_threshold
        if deterministic_ok:
            return state
        should_stop, reason = self.guard.should_stop(trial.iteration + 1)
        if should_stop:
            state["stopped_reason"] = reason
            state["should_stop"] = True
        return state

    def _node_llm_judge(self, state: LoopState) -> LoopState:
        state["node_trace"] = [*state.get("node_trace", []), "llm_judge"]
        trial = state["trials"][-1]
        if trial.passed:
            state["stopped_reason"] = "score_threshold"
            state["should_stop"] = True
        return state

    def _node_reflect(self, state: LoopState) -> LoopState:
        state["node_trace"] = [*state.get("node_trace", []), "reflect"]
        trial = state["trials"][-1]
        state["constraints"] = self.reflector.reflect(trial)
        state["iteration"] = trial.iteration + 1
        should_stop, reason = self.guard.should_stop(state["iteration"])
        if should_stop:
            state["stopped_reason"] = reason
            state["should_stop"] = True
        return state

    def _node_prepare_promotion(self, state: LoopState) -> LoopState:
        state["node_trace"] = [*state.get("node_trace", []), "prepare_promotion"]
        state["should_stop"] = True
        return state

    def _route_after_deterministic_eval(self, state: LoopState) -> str:
        if state.get("should_stop"):
            return "prepare_promotion"
        trial = state["trials"][-1]
        deterministic_ok = not trial.failure_reasons and trial.score >= self.eval_config.deterministic_threshold
        return "llm_judge" if deterministic_ok else "reflect"

    def _route_after_llm_judge(self, state: LoopState) -> str:
        return "prepare_promotion" if state.get("should_stop") else "reflect"

    def _route_after_reflect(self, state: LoopState) -> str:
        return "prepare_promotion" if state.get("should_stop") else "generate_variant"

    def _run_trial(
        self,
        *,
        iteration: int,
        variant: VariantSpec,
        regression_cases: list[dict[str, Any]],
        capability_cases: list[dict[str, Any]],
    ) -> TrialResult:
        library = self._variant_library(variant)
        with llm_client.track_usage() as usage:
            regression_results = self._run_case_group(
                cases=regression_cases,
                library=library,
                eval_group="regression",
            )
            capability_results = self._run_case_group(
                cases=capability_cases,
                library=library,
                eval_group="capability",
            )
        self.guard.record_usage(usage.records)

        regression_score = _avg_score(regression_results)
        regression_score_excluding_timeouts = _avg_score(regression_results, ignore_timeout_errors=True)
        regression_floor_score = _avg_score(_scored_regression_results(regression_results))
        capability_score = _avg_score(capability_results)
        if regression_results and capability_results:
            weight = self.eval_config.capability_weight
            score = regression_score * (1 - weight) + capability_score * weight
        elif regression_results:
            score = regression_score
        elif capability_results:
            score = capability_score
        else:
            score = 0.0
        case_results = [*regression_results, *capability_results]
        failures = _dedupe(reason for item in case_results for reason in item.failure_reasons)
        aggregates = _trial_case_aggregates(case_results)
        passed = (
            score >= self.eval_config.score_threshold
            and (
                not regression_results
                or not _scored_regression_results(regression_results)
                or regression_floor_score >= self.eval_config.regression_floor
            )
            and all(item.passed for item in case_results)
        )
        return TrialResult(
            iteration=iteration,
            variant=variant,
            score=score,
            passed=passed,
            case_results=case_results,
            regression_results=regression_results,
            capability_results=capability_results,
            regression_score=regression_score,
            capability_score=capability_score,
            regression_score_excluding_timeouts=regression_score_excluding_timeouts,
            failure_reasons=failures,
            budget_snapshot=self.guard.snapshot(),
            timeout_case_count=aggregates["timeout_case_count"],
            failed_execution_case_count=aggregates["failed_execution_case_count"],
            error_type_counts=aggregates["error_type_counts"],
            timing_summary=aggregates["timing_summary"],
        )

    def _run_case_group(
        self,
        *,
        cases: list[dict[str, Any]],
        library: dict[tuple[str, str], SubModule],
        eval_group: str,
    ) -> list[CaseEvalResult]:
        case_results: list[CaseEvalResult] = []
        for case in cases:
            jd_file = Path(case["jd_file"])
            jd_text = jd_file.read_text(encoding="utf-8")
            golden, golden_file = self._load_golden_with_path(case)
            case_started_at = time.perf_counter()
            try:
                case_timeout_seconds = self.eval_config.case_timeout_seconds
                deadline_monotonic = (
                    case_started_at + case_timeout_seconds if case_timeout_seconds is not None else None
                )
                output = run_with_config(
                    jd_text=jd_text,
                    config=copy.deepcopy(WORKFLOW_V4_CONFIG),
                    library=library,
                    llm_options={
                        "timeout": self.eval_config.llm_call_timeout_seconds,
                        "retry_count": self.eval_config.retry_count,
                        "retry_backoff": self.eval_config.retry_backoff_seconds,
                        "deadline_monotonic": deadline_monotonic,
                    },
                )
                meta = output.get("_meta", {})
                case_result = self.evaluator.evaluate_case(
                    case_id=case["id"],
                    jd_text=jd_text,
                    workflow_output=output,
                    golden=golden,
                    variant=_library_variant(library=library, target=self.eval_config.target),
                    deadline_monotonic=deadline_monotonic,
                )
                case_result.trace_id = str(meta.get("trace_id") or "")
                case_result.trace_log_path = str(meta.get("trace_log_path") or "")
                case_result.timing = dict(meta.get("timing") or {})
            except Exception as exc:
                logging.exception("Failed to execute workflow for case %s", case["id"])
                elapsed_ms = int((time.perf_counter() - case_started_at) * 1000)
                error_payload = _case_error_payload(exc)
                case_result = CaseEvalResult(
                    case_id=case["id"],
                    score=0.0,
                    passed=False,
                    failure_reasons=[f"workflow execution failed: {type(exc).__name__}: {exc}"],
                    metrics={"execution_error_type": type(exc).__name__},
                    timing={"workflow_total_ms": elapsed_ms, "sub_modules": []},
                    error=error_payload,
                )
            if not case_result.timing:
                case_result.timing = {
                    "workflow_total_ms": int((time.perf_counter() - case_started_at) * 1000),
                    "sub_modules": [],
                }
            case_result.eval_group = eval_group
            case_result.jd_file = str(jd_file)
            case_result.golden_file = str(golden_file) if golden_file else ""
            case_results.append(case_result)
        return case_results

    def _variant_library(self, variant: VariantSpec) -> dict[tuple[str, str], SubModule]:
        library = dict(SUB_MODULE_LIBRARY)
        for key, module in SUB_MODULE_LIBRARY.items():
            name, version = key
            if name != variant.target:
                continue
            library[key] = SubModule(
                name=module.name,
                version=version,
                system_prompt=module.system_prompt + variant.system_prompt_suffix,
                output_schema=module.output_schema,
                build_user_prompt=module._build_user_prompt,
                temperature=variant.temperature if variant.temperature is not None else module.temperature,
                user_prompt_template=variant.user_prompt_template,
            )
        return library

    def _load_cases(self, cases_dir: Path | None) -> list[dict[str, Any]]:
        if cases_dir is None:
            return []
        case_paths = sorted(cases_dir.glob("case_*.json"))
        cases = [json.loads(path.read_text(encoding="utf-8")) for path in case_paths]
        if not cases:
            raise ValueError(f"No cases found in {cases_dir}")
        return cases

    def _load_golden(self, case: dict[str, Any]) -> dict[str, Any] | None:
        golden, _path = self._load_golden_with_path(case)
        return golden

    def _load_golden_with_path(self, case: dict[str, Any]) -> tuple[dict[str, Any] | None, Path | None]:
        if self.eval_config.golden_dir:
            path = self.eval_config.golden_dir / f"{case['id']}_golden_v4.json"
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8")), path
        golden_path = case.get("golden_label_file")
        if golden_path and Path(golden_path).exists():
            path = Path(golden_path)
            return json.loads(path.read_text(encoding="utf-8")), path
        return None, None

    def _write_state(
        self,
        *,
        trials: list[TrialResult],
        stopped_reason: str,
        node_trace: list[str] | None = None,
        best_trial: TrialResult | None = None,
    ) -> None:
        output_dir = self.output_dir / self.run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        state = {
            "run_id": self.run_id,
            "target": self.eval_config.target,
            "stopped_reason": stopped_reason,
            "budget": self.guard.snapshot(),
            "node_trace": node_trace or [],
            "best_trial": best_trial.variant.id if best_trial else None,
            "trials": [
                {
                    "iteration": trial.iteration,
                    "variant": trial.variant.id,
                    "score": trial.score,
                    "regression_score": trial.regression_score,
                    "regression_score_excluding_timeouts": trial.regression_score_excluding_timeouts,
                    "capability_score": trial.capability_score,
                    "passed": trial.passed,
                    "timeout_case_count": trial.timeout_case_count,
                    "failed_execution_case_count": trial.failed_execution_case_count,
                    "error_type_counts": trial.error_type_counts,
                    "timing_summary": trial.timing_summary,
                    "failure_reasons": trial.failure_reasons,
                    "case_results": [_case_result_record(trial, case) for case in trial.case_results],
                }
                for trial in trials
            ],
        }
        (output_dir / "loop_state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._write_case_results(trials=trials)
        self._write_variants(trials=trials)
        self._write_manifest(trials=trials, best_trial=best_trial, stopped_reason=stopped_reason)

    def _write_case_results(self, *, trials: list[TrialResult]) -> None:
        output_dir = self.output_dir / self.run_id
        rows = [
            json.dumps(_case_result_record(trial, case), ensure_ascii=False)
            for trial in trials
            for case in trial.case_results
        ]
        (output_dir / "case_results.jsonl").write_text(
            "\n".join(rows) + ("\n" if rows else ""),
            encoding="utf-8",
        )

    def _write_variants(self, *, trials: list[TrialResult]) -> None:
        output_dir = self.output_dir / self.run_id
        seen: set[str] = set()
        variants: list[dict[str, Any]] = []
        for trial in trials:
            if trial.variant.id in seen:
                continue
            seen.add(trial.variant.id)
            variants.append(_variant_record(trial.variant))
        (output_dir / "variants.json").write_text(
            json.dumps(variants, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_manifest(
        self,
        *,
        trials: list[TrialResult] | None = None,
        best_trial: TrialResult | None = None,
        stopped_reason: str = "",
    ) -> None:
        output_dir = self.output_dir / self.run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "run_id": self.run_id,
            "target": self.eval_config.target,
            "repo_root": str(self.repo_root),
            "run_worktree": str(self.run_worktree.path) if self.run_worktree else "",
            "run_worktree_branch": self.run_worktree.branch if self.run_worktree else "",
            "git": _git_snapshot(self.repo_root),
            "eval_config": {
                "cases_dir": str(self.eval_config.cases_dir),
                "regression_dir": str(self.eval_config.regression_dir) if self.eval_config.regression_dir else "",
                "capability_dir": str(self.eval_config.capability_dir) if self.eval_config.capability_dir else "",
                "golden_dir": str(self.eval_config.golden_dir) if self.eval_config.golden_dir else "",
                "capability_weight": self.eval_config.capability_weight,
                "regression_floor": self.eval_config.regression_floor,
                "score_threshold": self.eval_config.score_threshold,
                "deterministic_threshold": self.eval_config.deterministic_threshold,
                "run_llm_judge": self.eval_config.run_llm_judge,
                "llm_call_timeout_seconds": self.eval_config.llm_call_timeout_seconds,
                "case_timeout_seconds": self.eval_config.case_timeout_seconds,
                "retry_count": self.eval_config.retry_count,
                "retry_backoff_seconds": self.eval_config.retry_backoff_seconds,
                "max_timeout_rate": self.eval_config.max_timeout_rate,
            },
            "budget": {
                "max_iterations": self.budget.max_iterations,
                "max_wall_seconds": self.budget.max_wall_seconds,
                "max_llm_calls": self.budget.max_llm_calls,
                "max_input_tokens": self.budget.max_input_tokens,
                "max_output_tokens": self.budget.max_output_tokens,
                "max_cost_usd": self.budget.max_cost_usd,
                "stop_after_no_improvement": self.budget.stop_after_no_improvement,
            },
            "stopped_reason": stopped_reason,
            "best_trial": best_trial.variant.id if best_trial else "",
            "trials": [_trial_manifest_record(trial) for trial in trials or []],
            "workflow_version": WORKFLOW_V4_CONFIG.get("version"),
            "llm": {
                "provider": "dashscope-compatible",
                "model": os.getenv("OPENAI_MODEL", llm_client.DEFAULT_MODEL),
            },
        }
        (output_dir / "run_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _create_run_worktree(self) -> WorktreeInfo | None:
        try:
            return self.worktree_manager.create(run_id=self.run_id, target=self.eval_config.target)
        except Exception:
            return None

    def _promote_variant_to_run_worktree(self, variant: VariantSpec) -> None:
        if not self.run_worktree or variant.id == "baseline":
            return
        self.worktree_manager.apply_variant_to_library(path=self.run_worktree.path, variant=variant)
        self.worktree_manager.commit(
            path=self.run_worktree.path,
            message=f"[loop] promote {variant.id} for {variant.target}",
        )

    def _target_system_prompt(self) -> str:
        for (name, _version), module in SUB_MODULE_LIBRARY.items():
            if name == self.eval_config.target:
                return module.system_prompt
        return ""

    def _score_variant_on_validation_set(self, variant: VariantSpec) -> float:
        cases = self._load_cases(
            self.eval_config.capability_dir or self.eval_config.regression_dir or self.eval_config.cases_dir
        )[:2]
        library = self._variant_library(variant)
        with llm_client.track_usage() as usage:
            results = self._run_case_group(cases=cases, library=library, eval_group="validation")
        self.guard.record_usage(usage.records)
        return _avg_score(results)


def _dedupe(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _avg_score(results: list[CaseEvalResult], *, ignore_timeout_errors: bool = False) -> float:
    filtered = [
        item for item in results if not ignore_timeout_errors or not _is_timeout_case(item)
    ]
    return sum(item.score for item in filtered) / len(filtered) if filtered else 0.0


def _scored_regression_results(results: list[CaseEvalResult]) -> list[CaseEvalResult]:
    return [
        item
        for item in results
        if not _is_timeout_case(item) and not _is_non_timeout_execution_failure_case(item)
    ]


def _case_result_record(trial: TrialResult, case: CaseEvalResult) -> dict[str, Any]:
    return {
        "iteration": trial.iteration,
        "variant_id": trial.variant.id,
        "variant_description": trial.variant.description,
        "eval_group": case.eval_group,
        "case_id": case.case_id,
        "jd_file": case.jd_file,
        "golden_file": case.golden_file,
        "passed": case.passed,
        "score": case.score,
        "metrics": case.metrics,
        "failure_reasons": case.failure_reasons,
        "suggested_change": case.suggested_change,
        "timing": case.timing,
        "error": case.error,
        "trace_id": case.trace_id,
        "trace_log_path": case.trace_log_path,
    }


def _variant_record(variant: VariantSpec) -> dict[str, Any]:
    return {
        "id": variant.id,
        "target": variant.target,
        "description": variant.description,
        "system_prompt_suffix": variant.system_prompt_suffix,
        "user_prompt_template": variant.user_prompt_template,
        "temperature": variant.temperature,
        "metadata": variant.metadata,
    }


def _trial_manifest_record(trial: TrialResult) -> dict[str, Any]:
    return {
        "iteration": trial.iteration,
        "variant": trial.variant.id,
        "score": trial.score,
        "regression_score": trial.regression_score,
        "regression_score_excluding_timeouts": trial.regression_score_excluding_timeouts,
        "capability_score": trial.capability_score,
        "passed": trial.passed,
        "timeout_case_count": trial.timeout_case_count,
        "failed_execution_case_count": trial.failed_execution_case_count,
        "error_type_counts": trial.error_type_counts,
        "timing_summary": trial.timing_summary,
    }


def _git_snapshot(repo_root: Path) -> dict[str, Any]:
    def run_git(args: list[str]) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    status = run_git(["status", "--short"])
    return {
        "branch": run_git(["branch", "--show-current"]),
        "commit": run_git(["rev-parse", "HEAD"]),
        "status_short": status,
        "dirty": bool(status),
    }


def _trial_case_aggregates(case_results: list[CaseEvalResult]) -> dict[str, Any]:
    error_type_counts: dict[str, int] = {}
    workflow_total_values: list[int] = []
    submodule_values: dict[str, list[int]] = {}
    timeout_case_count = 0
    failed_execution_case_count = 0

    for case in case_results:
        if case.error:
            failed_execution_case_count += 1
            error_type = str(case.error.get("type") or "UnknownError")
            error_type_counts[error_type] = error_type_counts.get(error_type, 0) + 1
        if _is_timeout_case(case):
            timeout_case_count += 1
        workflow_total_ms = case.timing.get("workflow_total_ms")
        if isinstance(workflow_total_ms, (int, float)):
            workflow_total_values.append(int(workflow_total_ms))
        for entry in case.timing.get("sub_modules", []):
            name = str(entry.get("name") or "")
            timing_ms = entry.get("timing_ms")
            if not name or not isinstance(timing_ms, (int, float)):
                continue
            submodule_values.setdefault(name, []).append(int(timing_ms))

    avg_submodule_ms = {
        name: round(sum(values) / len(values), 2)
        for name, values in submodule_values.items()
        if values
    }
    timing_summary = {
        "avg_workflow_total_ms": round(sum(workflow_total_values) / len(workflow_total_values), 2)
        if workflow_total_values
        else 0.0,
        "avg_sub_module_ms": avg_submodule_ms,
    }
    return {
        "timeout_case_count": timeout_case_count,
        "failed_execution_case_count": failed_execution_case_count,
        "error_type_counts": error_type_counts,
        "timing_summary": timing_summary,
    }


def _execution_failure_rate(trial: TrialResult) -> float:
    total_cases = len(trial.case_results)
    if total_cases == 0:
        return 0.0
    return trial.failed_execution_case_count / total_cases


def _has_non_timeout_results(results: list[CaseEvalResult]) -> bool:
    return any(not _is_timeout_case(item) for item in results)


def _is_non_timeout_execution_failure_case(case: CaseEvalResult) -> bool:
    return bool(case.error) and not _is_timeout_case(case)


def _is_timeout_case(case: CaseEvalResult) -> bool:
    error_type = str(case.error.get("type") or "")
    if _is_timeout_error_type(error_type):
        return True
    return any("timeout" in reason.lower() for reason in case.failure_reasons)


def _case_error_payload(exc: Exception) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": str(exc),
    }


def _is_timeout_error_type(error_type: str) -> bool:
    normalized = error_type.lower()
    return "timeout" in normalized


def _library_variant(*, library: dict[tuple[str, str], SubModule], target: str) -> VariantSpec | None:
    for (name, _version), module in library.items():
        if name != target:
            continue
        for (base_name, _base_version), base_module in SUB_MODULE_LIBRARY.items():
            if base_name != target:
                continue
            suffix = module.system_prompt.removeprefix(base_module.system_prompt)
            if not suffix:
                return None
            return VariantSpec(
                id="active-library-variant",
                target=target,
                description="Current in-memory variant library.",
                system_prompt_suffix=suffix,
                temperature=module.temperature,
                user_prompt_template=module.user_prompt_template,
            )
    return None

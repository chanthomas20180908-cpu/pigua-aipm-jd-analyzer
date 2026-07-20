"""目的：定义 v4 迭代 Loop 的结构化数据模型。

定义：Evaluator、Generator、Controller 和 Reporter 共享的数据契约。

范围包括：
- 变体、预算、评估配置、单轮结果和最终报告的数据类。

范围不包括：
- 不包含具体 LLM 调用、Git 操作或文件系统副作用。

使用与修改规则：
- 字段变更需同步 reporter、controller 和 docs/loop-design.md。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VariantSpec:
    """A prompt/code candidate evaluated by the loop."""

    id: str
    target: str
    description: str
    system_prompt_suffix: str = ""
    user_prompt_template: str | None = None
    temperature: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunBudget:
    """Hard limits for one loop run."""

    max_iterations: int = 3
    max_wall_seconds: int = 900
    max_llm_calls: int = 80
    max_input_tokens: int = 0
    max_output_tokens: int = 0
    max_cost_usd: float = 0.0
    stop_after_no_improvement: int = 2


@dataclass(frozen=True)
class EvalConfig:
    """Evaluation input locations and scoring knobs."""

    target: str
    cases_dir: Path
    golden_dir: Path | None
    output_dir: Path
    regression_dir: Path | None = None
    capability_dir: Path | None = None
    capability_weight: float = 0.4
    regression_floor: float = 0.75
    score_threshold: float = 0.82
    deterministic_threshold: float = 0.7
    run_llm_judge: bool = False
    llm_call_timeout_seconds: float | None = None
    case_timeout_seconds: float | None = None
    retry_count: int = 0
    retry_backoff_seconds: float = 1.0
    max_timeout_rate: float = 0.3


@dataclass
class CaseEvalResult:
    """Evaluation result for one case."""

    case_id: str
    score: float
    passed: bool
    eval_group: str = ""
    jd_file: str = ""
    golden_file: str = ""
    trace_id: str = ""
    trace_log_path: str = ""
    failure_reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    suggested_change: str = ""
    timing: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrialResult:
    """Result for one evaluated variant."""

    iteration: int
    variant: VariantSpec
    score: float
    passed: bool
    case_results: list[CaseEvalResult] = field(default_factory=list)
    regression_results: list[CaseEvalResult] = field(default_factory=list)
    capability_results: list[CaseEvalResult] = field(default_factory=list)
    regression_score: float = 0.0
    capability_score: float = 0.0
    regression_score_excluding_timeouts: float = 0.0
    failure_reasons: list[str] = field(default_factory=list)
    budget_snapshot: dict[str, Any] = field(default_factory=dict)
    timeout_case_count: int = 0
    failed_execution_case_count: int = 0
    error_type_counts: dict[str, int] = field(default_factory=dict)
    timing_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class LoopReport:
    """Final loop summary."""

    run_id: str
    target: str
    best_trial: TrialResult | None
    trials: list[TrialResult]
    output_dir: Path
    promotion_path: Path | None = None
    stopped_reason: str = ""

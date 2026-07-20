"""目的：集中定义 v4 迭代 Loop 的可配置运行参数。

定义：Loop 的 dataclass 默认值，以及配置文件/环境变量的加载逻辑。

范围包括：
- timeout、retry、预算、分数阈值和 stop guard 参数。

范围不包括：
- 不承载 case 路径、API key 或工作流模块定义。

使用与修改规则：
- 参数新增或命名变更时同步 scripts/run_iteration_loop.py 和 docs/loop-design.md。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import importlib.util
import os
from pathlib import Path
from typing import Any, Mapping, get_type_hints


@dataclass(frozen=True)
class LoopConfig:
    capability_weight: float = 0.4
    regression_floor: float = 0.75
    score_threshold: float = 0.82
    deterministic_threshold: float = 0.7
    run_llm_judge: bool = False
    llm_call_timeout_seconds: float = 120.0
    case_timeout_seconds: float = 300.0
    retry_count: int = 2
    retry_backoff_seconds: float = 2.0
    max_timeout_rate: float = 0.3
    max_iterations: int = 3
    max_wall_seconds: int = 900
    max_llm_calls: int = 80
    max_input_tokens: int = 0
    max_output_tokens: int = 0
    budget_usd: float = 0.0
    stop_after_no_improvement: int = 2


DEFAULT_LOOP_CONFIG = LoopConfig()
_FIELD_TYPES = get_type_hints(LoopConfig)
_ENV_PREFIX = "AIPM_LOOP_"


def load_loop_config(
    config_path: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> LoopConfig:
    source_path = (config_path or Path(__file__)).resolve()
    default_values = asdict(DEFAULT_LOOP_CONFIG)
    file_values = _load_file_overrides(source_path)
    env_values = _load_env_overrides(env or os.environ)
    return _build_loop_config(
        {
            **default_values,
            **file_values,
            **env_values,
        }
    )


def apply_overrides(config: LoopConfig, overrides: Mapping[str, Any]) -> LoopConfig:
    values = asdict(config)
    for key, value in overrides.items():
        if key not in _FIELD_TYPES or value is None:
            continue
        values[key] = _coerce_value(key, value)
    return _build_loop_config(values)


def _load_file_overrides(config_path: Path) -> dict[str, Any]:
    if config_path == Path(__file__).resolve():
        return asdict(DEFAULT_LOOP_CONFIG)
    spec = importlib.util.spec_from_file_location("loop_runtime_config", config_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load config file: {config_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if hasattr(module, "LOOP_CONFIG"):
        raw = getattr(module, "LOOP_CONFIG")
        if isinstance(raw, LoopConfig):
            return asdict(raw)
        if isinstance(raw, dict):
            return {key: raw[key] for key in raw if key in _FIELD_TYPES}
        raise ValueError("LOOP_CONFIG must be a LoopConfig or dict.")

    overrides: dict[str, Any] = {}
    for key in _FIELD_TYPES:
        if hasattr(module, key):
            overrides[key] = getattr(module, key)
    return overrides


def _load_env_overrides(env: Mapping[str, str]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for key in _FIELD_TYPES:
        env_key = f"{_ENV_PREFIX}{key.upper()}"
        if env_key in env and env[env_key] != "":
            overrides[key] = _coerce_value(key, env[env_key])
    return overrides


def _build_loop_config(values: Mapping[str, Any]) -> LoopConfig:
    normalized = {key: _coerce_value(key, values[key]) for key in _FIELD_TYPES if key in values}
    return LoopConfig(**normalized)


def _coerce_value(field_name: str, value: Any) -> Any:
    field_type = _FIELD_TYPES[field_name]
    if value is None:
        return None
    if field_type is bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if field_type is int:
        return int(value)
    if field_type is float:
        return float(value)
    return value

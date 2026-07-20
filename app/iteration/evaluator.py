"""目的：评估 v4 工作流输出质量。

定义：Promptfoo 式确定性断言为主、可选 LLM-as-judge 为辅的评估器。

范围包括：
- JSON 结构检查、ID 引用检查、显式证据比例、数量阈值和可选 rubric judge。

范围不包括：
- 不负责生成候选 prompt，不负责执行完整 loop。

使用与修改规则：
- 确定性断言失败时默认跳过 LLM judge，避免用主观评分掩盖结构错误。
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from app import llm_client
from app.iteration.models import CaseEvalResult, VariantSpec


class V4Evaluator:
    def __init__(
        self,
        *,
        target: str,
        deterministic_threshold: float = 0.7,
        run_llm_judge: bool = False,
        llm_call_timeout_seconds: float | None = None,
        retry_count: int = 0,
        retry_backoff_seconds: float = 1.0,
    ):
        self.target = target
        self.deterministic_threshold = deterministic_threshold
        self.run_llm_judge = run_llm_judge
        self.llm_call_timeout_seconds = llm_call_timeout_seconds
        self.retry_count = retry_count
        self.retry_backoff_seconds = retry_backoff_seconds

    def evaluate_case(
        self,
        *,
        case_id: str,
        jd_text: str,
        workflow_output: dict[str, Any],
        golden: dict[str, Any] | None = None,
        variant: VariantSpec | None = None,
        deadline_monotonic: float | None = None,
    ) -> CaseEvalResult:
        promptfoo_result = self._promptfoo_eval(
            case_id=case_id,
            workflow_output=workflow_output,
            golden=golden,
            variant=variant,
        )
        if promptfoo_result is not None:
            return promptfoo_result

        target_output = workflow_output.get(self.target, {})
        score, failures, metrics = self._deterministic_score(target_output, golden)
        if failures or score < self.deterministic_threshold or not self.run_llm_judge:
            return CaseEvalResult(
                case_id=case_id,
                score=score,
                passed=score >= self.deterministic_threshold and not failures,
                failure_reasons=failures,
                metrics=metrics,
            )

        if deadline_monotonic is not None and time.perf_counter() >= deadline_monotonic:
            raise TimeoutError(f"Case timeout reached before llm_judge for {case_id}.")
        judge = self._llm_judge(
            jd_text=jd_text,
            target_output=target_output,
            golden=golden,
            deadline_monotonic=deadline_monotonic,
        )
        judged_score = min(score, float(judge.get("score", score)))
        judged_failures = list(judge.get("failure_reasons") or [])
        return CaseEvalResult(
            case_id=case_id,
            score=judged_score,
            passed=bool(judge.get("passed", judged_score >= self.deterministic_threshold)),
            failure_reasons=judged_failures,
            metrics={**metrics, "judge": judge},
            suggested_change=str(judge.get("suggested_change") or ""),
        )

    def _deterministic_score(
        self,
        target_output: dict[str, Any],
        golden: dict[str, Any] | None,
    ) -> tuple[float, list[str], dict[str, Any]]:
        if not isinstance(target_output, dict):
            return 0.0, [f"{self.target} is not a JSON object"], {}
        if self.target == "element_modeling":
            return self._score_element_modeling(target_output, golden)
        required_keys = (golden or {}).get("required_keys", [])
        failures = [f"missing required key: {key}" for key in required_keys if key not in target_output]
        score = 1.0 if not failures else max(0.0, 1.0 - 0.2 * len(failures))
        return score, failures, {"required_keys": required_keys}

    def _score_element_modeling(
        self,
        output: dict[str, Any],
        golden: dict[str, Any] | None,
    ) -> tuple[float, list[str], dict[str, Any]]:
        golden_config = golden or {}
        expectations = golden_config.get("expectations", {})
        semantic_checks = golden_config.get("semantic_checks", {})
        configured_tags = set(golden_config.get("failure_tags", []))
        hard_failure_tags = set(golden_config.get("hard_failure_tags", []))
        min_value_streams = int(expectations.get("min_value_streams", 1))
        min_work_items = int(expectations.get("min_work_items", 3))
        min_explicit_ratio = float(expectations.get("min_explicit_ratio", 0.7))

        value_streams = _list(output.get("value_streams"))
        work_items = _list(output.get("work_items"))
        entities = _list(output.get("bussiness_entitys"))
        capabilities = _list(output.get("capabilities"))

        failures: list[str] = []
        if len(value_streams) < min_value_streams:
            failures.append(f"value_streams count {len(value_streams)} < {min_value_streams}")
        if len(work_items) < min_work_items:
            failures.append(f"work_items count {len(work_items)} < {min_work_items}")

        all_items = value_streams + work_items + entities + capabilities
        explicit_count = sum(1 for item in all_items if item.get("evidence_type") == "explicit")
        explicit_ratio = explicit_count / len(all_items) if all_items else 0.0
        if explicit_ratio < min_explicit_ratio:
            failures.append(f"explicit evidence ratio {explicit_ratio:.2f} < {min_explicit_ratio:.2f}")

        id_failures = self._validate_id_references(value_streams, work_items, entities, capabilities)
        failures.extend(id_failures)

        semantic_findings = self._collect_semantic_findings(
            value_streams=value_streams,
            work_items=work_items,
            entities=entities,
            capabilities=capabilities,
            semantic_checks=semantic_checks,
            configured_tags=configured_tags,
        )
        hard_findings = [item["message"] for item in semantic_findings if item["tag"] in hard_failure_tags]
        advisory_tags = [item["tag"] for item in semantic_findings if item["tag"] not in hard_failure_tags]
        failures.extend(hard_findings)

        semantic_penalty = sum(1.0 if item["tag"] in hard_failure_tags else 0.25 for item in semantic_findings)
        semantic_score = max(0.0, 1.0 - min(1.0, semantic_penalty / 3.0))

        score_parts = [
            min(1.0, len(value_streams) / max(1, min_value_streams)),
            min(1.0, len(work_items) / max(1, min_work_items)),
            min(1.0, explicit_ratio / max(0.01, min_explicit_ratio)),
            1.0 if not id_failures else 0.0,
        ]
        if semantic_checks or configured_tags or hard_failure_tags:
            score_parts.append(semantic_score)
        score = sum(score_parts) / len(score_parts)
        metrics = {
            "value_streams": len(value_streams),
            "work_items": len(work_items),
            "entities": len(entities),
            "capabilities": len(capabilities),
            "explicit_ratio": round(explicit_ratio, 4),
            "id_reference_failures": id_failures,
            "failure_tags": _dedupe([item["tag"] for item in semantic_findings]),
            "hard_failure_tags": _dedupe([item["tag"] for item in semantic_findings if item["tag"] in hard_failure_tags]),
            "advisory_failure_tags": _dedupe(advisory_tags),
            "semantic_findings": [item["message"] for item in semantic_findings],
            "semantic_score": round(semantic_score, 4),
        }
        return score, failures, metrics

    def _collect_semantic_findings(
        self,
        *,
        value_streams: list[dict[str, Any]],
        work_items: list[dict[str, Any]],
        entities: list[dict[str, Any]],
        capabilities: list[dict[str, Any]],
        semantic_checks: dict[str, Any],
        configured_tags: set[str],
    ) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []
        entity_names = [str(item.get("entity_name") or "") for item in entities]
        work_item_names = [str(item.get("work_item_name") or "") for item in work_items]
        capability_names = [str(item.get("capability_name") or "") for item in capabilities]
        value_stream_names = [str(item.get("value_stream_name") or "") for item in value_streams]

        patterns = [str(item) for item in _list(semantic_checks.get("forbidden_value_stream_patterns")) if str(item)]
        if patterns:
            matched_streams = [
                name
                for name in value_stream_names
                if any(re.search(pattern, name) for pattern in patterns)
            ]
            if matched_streams:
                findings.append(
                    _finding(
                        tag=self._resolve_tag(configured_tags, "value_stream_naming"),
                        message=(
                            "value_stream_naming: value stream names should be stable business labels, not "
                            f"'from A to B' process summaries: {', '.join(matched_streams)}"
                        ),
                    )
                )

        required_ai_layers = [str(item) for item in _list(semantic_checks.get("required_ai_layers_any")) if str(item)]
        if required_ai_layers and not _contains_any(entity_names, required_ai_layers):
            missing_keywords = ", ".join(required_ai_layers[:6])
            findings.append(
                _finding(
                    tag=self._resolve_tag(
                        configured_tags,
                        "missing_ai_transformation_layer",
                        "missing_technical_entity",
                    ),
                    message=(
                        "missing_ai_transformation_layer: missing concrete AI transformation or platform-layer "
                        f"entities such as {missing_keywords}"
                    ),
                )
            )

        required_work_items = [
            str(item) for item in _list(semantic_checks.get("required_work_item_keywords_any")) if str(item)
        ]
        matched_required_work_items = _match_keywords(work_item_names, required_work_items)
        if required_work_items and not matched_required_work_items:
            findings.append(
                _finding(
                    tag=self._resolve_tag(configured_tags, "missing_work_item"),
                    message=(
                        "missing_work_item: missing expected work-item stages "
                        f"{', '.join(required_work_items[:6])}"
                    ),
                )
            )
        if (
            required_work_items
            and "overly_broad_work_item" in configured_tags
            and len(matched_required_work_items) <= max(1, len(required_work_items) // 3)
        ):
            findings.append(
                _finding(
                    tag="overly_broad_work_item",
                    message=(
                        "overly_broad_work_item: current work items compress multiple JD duties into broad actions; "
                        f"matched only {', '.join(matched_required_work_items) or 'none'}"
                    ),
                )
            )

        required_entities = [
            str(item) for item in _list(semantic_checks.get("required_entity_keywords_any")) if str(item)
        ]
        matched_required_entities = _match_keywords(entity_names, required_entities)
        if required_entities and not matched_required_entities:
            findings.append(
                _finding(
                    tag=self._resolve_tag(configured_tags, "missing_business_entity"),
                    message=(
                        "missing_business_entity: missing expected supporting entities "
                        f"{', '.join(required_entities[:6])}"
                    ),
                )
            )

        required_capabilities = [
            str(item) for item in _list(semantic_checks.get("required_capability_keywords_any")) if str(item)
        ]
        if required_capabilities and not _contains_any(capability_names, required_capabilities):
            findings.append(
                _finding(
                    tag=self._resolve_tag(
                        configured_tags,
                        "missing_expected_capability",
                        "missing_capability",
                    ),
                    message=(
                        "missing_expected_capability: capability layer is missing expected role-specific capabilities "
                        f"{', '.join(required_capabilities[:6])}"
                    ),
                )
            )

        forbidden_abstractions = [str(item) for item in _list(semantic_checks.get("forbidden_abstractions")) if str(item)]
        matched_abstractions = _match_keywords(entity_names + work_item_names, forbidden_abstractions)
        if matched_abstractions:
            if "abstract_entity" in configured_tags:
                findings.append(
                    _finding(
                        tag="abstract_entity",
                        message=(
                            "abstract_entity: found overly abstract entities or work items "
                            f"{', '.join(matched_abstractions)}"
                        ),
                    )
                )
            if "coarse_entity_granularity" in configured_tags:
                findings.append(
                    _finding(
                        tag="coarse_entity_granularity",
                        message=(
                            "coarse_entity_granularity: entity modeling stays at abstract platform-summary level "
                            f"instead of concrete operable objects: {', '.join(matched_abstractions)}"
                        ),
                    )
                )

        forbidden_capabilities = [
            str(item) for item in _list(semantic_checks.get("forbidden_capability_keywords")) if str(item)
        ]
        matched_forbidden_capabilities = _match_keywords(capability_names, forbidden_capabilities)
        if matched_forbidden_capabilities:
            findings.append(
                _finding(
                    tag=self._resolve_tag(configured_tags, "unsupported_inference"),
                    message=(
                        "unsupported_inference: capability layer over-infers unsupported specialties "
                        f"{', '.join(matched_forbidden_capabilities)}"
                    ),
                )
            )

        overlap_groups = [
            [str(name) for name in _list(group) if str(name)]
            for group in _list(semantic_checks.get("capability_overlap_groups"))
        ]
        for group in overlap_groups:
            overlaps = _match_keywords(capability_names, group)
            if len(overlaps) >= 2:
                findings.append(
                    _finding(
                        tag=self._resolve_tag(configured_tags, "capability_overlap"),
                        message=(
                            "capability_overlap: found highly overlapping capability names "
                            f"{', '.join(overlaps)}"
                        ),
                    )
                )
                if "over_fragmented_capability" in configured_tags:
                    findings.append(
                        _finding(
                            tag="over_fragmented_capability",
                            message=(
                                "over_fragmented_capability: one platform design capability was fragmented into "
                                f"multiple near-duplicate items: {', '.join(overlaps)}"
                            ),
                        )
                    )

        if (
            "incomplete_value_stream" in configured_tags
            and required_work_items
            and required_entities
            and (not matched_required_work_items or not matched_required_entities)
        ):
            findings.append(
                _finding(
                    tag="incomplete_value_stream",
                    message=(
                        "incomplete_value_stream: value stream purpose implies a fuller lifecycle than the modeled "
                        "work items and entities currently support"
                    ),
                )
            )

        return _dedupe_findings(findings)

    def _resolve_tag(self, configured_tags: set[str], *candidates: str) -> str:
        for candidate in candidates:
            if candidate in configured_tags:
                return candidate
        return candidates[0]

    def _validate_id_references(
        self,
        value_streams: list[dict[str, Any]],
        work_items: list[dict[str, Any]],
        entities: list[dict[str, Any]],
        capabilities: list[dict[str, Any]],
    ) -> list[str]:
        work_item_ids = {str(item.get("id")) for item in work_items}
        entity_ids = {str(item.get("id")) for item in entities}
        capability_ids = {str(item.get("id")) for item in capabilities}
        failures: list[str] = []
        for stream in value_streams:
            for ref in _list(stream.get("work_item_ids")):
                if str(ref) not in work_item_ids:
                    failures.append(f"value_stream {stream.get('id')} references missing work_item {ref}")
        for item in work_items:
            for operation in _list(item.get("entity_operations")):
                entity_id = str(operation.get("entity_id"))
                if entity_id not in entity_ids:
                    failures.append(f"work_item {item.get('id')} references missing entity {entity_id}")
            for ref in _list(item.get("capability_ids")):
                if str(ref) not in capability_ids:
                    failures.append(f"work_item {item.get('id')} references missing capability {ref}")
        for capability in capabilities:
            for ref in _list(capability.get("primary_entity_ids")):
                if str(ref) not in entity_ids:
                    failures.append(f"capability {capability.get('id')} references missing entity {ref}")
            for ref in _list(capability.get("supported_work_item_ids")):
                if str(ref) not in work_item_ids:
                    failures.append(f"capability {capability.get('id')} references missing work_item {ref}")
        return failures

    def _llm_judge(
        self,
        *,
        jd_text: str,
        target_output: dict[str, Any],
        golden: dict[str, Any] | None,
        deadline_monotonic: float | None,
    ) -> dict[str, Any]:
        if not llm_client.llm_is_configured():
            return {"score": 0.0, "passed": False, "failure_reasons": ["LLM judge not configured"]}
        system_prompt = (
            "你是严格的 JD 建模评估员。只评估输出是否忠于 JD 原文、颗粒度是否合理、"
            "实体关系是否自洽。输出合法 JSON。"
        )
        user_prompt = json.dumps(
            {
                "jd_text": jd_text,
                "target": self.target,
                "output": target_output,
                "golden": golden or {},
                "return_schema": {
                    "score": "0.0-1.0",
                    "passed": "boolean",
                    "failure_reasons": ["string"],
                    "suggested_change": "string",
                },
            },
            ensure_ascii=False,
        )
        timeout = self.llm_call_timeout_seconds
        if deadline_monotonic is not None:
            remaining_seconds = deadline_monotonic - time.perf_counter()
            if remaining_seconds <= 0:
                raise TimeoutError("Case timeout reached before llm_judge request.")
            timeout = remaining_seconds if timeout is None else min(timeout, remaining_seconds)
        return llm_client.call_llm_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            timeout=timeout,
            retry_count=self.retry_count,
            retry_backoff=self.retry_backoff_seconds,
        )

    def _promptfoo_eval(
        self,
        *,
        case_id: str,
        workflow_output: dict[str, Any],
        golden: dict[str, Any] | None,
        variant: VariantSpec | None,
    ) -> CaseEvalResult | None:
        promptfoo_command = _promptfoo_command()
        if not promptfoo_command:
            return None

        target_output = workflow_output.get(self.target, {})
        score, failures, metrics = self._deterministic_score(target_output, golden)
        with tempfile.TemporaryDirectory(prefix="aipm_promptfoo_") as tmp:
            tmp_path = Path(tmp)
            output_path = tmp_path / "workflow_output.json"
            golden_path = tmp_path / "golden.json"
            assertion_path = tmp_path / "assert_v4.py"
            result_path = tmp_path / "promptfoo_result.json"
            config_path = tmp_path / "promptfooconfig.yaml"
            output_path.write_text(json.dumps(workflow_output, ensure_ascii=False), encoding="utf-8")
            golden_path.write_text(json.dumps(golden or {}, ensure_ascii=False), encoding="utf-8")
            assertion_path.write_text(
                _render_promptfoo_assertion(
                    target=self.target,
                    golden_path=golden_path,
                    threshold=self.deterministic_threshold,
                ),
                encoding="utf-8",
            )
            config_path.write_text(
                _render_promptfoo_config(
                    case_id=case_id,
                    assertion_path=assertion_path,
                ),
                encoding="utf-8",
            )
            try:
                env = dict(os.environ)
                env["PROMPTFOO_REPLAY_OUTPUT"] = json.dumps(workflow_output, ensure_ascii=False)
                if variant is not None:
                    env["PROMPTFOO_VARIANT_JSON"] = json.dumps(variant.__dict__, ensure_ascii=False)
                subprocess.run(
                    [*promptfoo_command, "eval", "-c", str(config_path), "-o", str(result_path)],
                    cwd=Path.cwd(),
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                if result_path.exists():
                    parsed = json.loads(result_path.read_text(encoding="utf-8"))
                    promptfoo_metrics = {"promptfoo": _summarize_promptfoo(parsed), **metrics}
                else:
                    promptfoo_metrics = metrics
                return CaseEvalResult(
                    case_id=case_id,
                    score=score,
                    passed=score >= self.deterministic_threshold and not failures,
                    failure_reasons=failures,
                    metrics=promptfoo_metrics,
                )
            except Exception as exc:
                logging.warning("Promptfoo eval failed for case %s: %s", case_id, exc)
                stderr = getattr(exc, "stderr", None)
                if stderr:
                    logging.warning("Promptfoo stderr: %s", stderr)
                return None


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _finding(*, tag: str, message: str) -> dict[str, str]:
    return {"tag": tag, "message": message}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _dedupe_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for item in findings:
        key = (item["tag"], item["message"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _contains_any(names: list[str], keywords: list[str]) -> bool:
    return any(keyword in name for name in names for keyword in keywords)


def _match_keywords(names: list[str], keywords: list[str]) -> list[str]:
    matches: list[str] = []
    for name in names:
        if any(keyword in name for keyword in keywords):
            matches.append(name)
    return _dedupe(matches)


def _promptfoo_command() -> list[str] | None:
    if shutil.which("promptfoo"):
        return ["promptfoo"]
    if os.getenv("PROMPTFOO_USE_NPX") == "1" and shutil.which("npx"):
        return ["npx", "--yes", "promptfoo"]
    return None


def _render_promptfoo_config(
    *,
    case_id: str,
    assertion_path: Path,
) -> str:
    return (
        "description: aipm v4 deterministic eval\n"
        "providers:\n"
        "  - id: python:app.iteration.promptfoo_provider:V4PromptfooProvider\n"
        "prompts:\n"
        f"  - '{case_id}'\n"
        "tests:\n"
        "  - vars:\n"
        f"      case_id: '{case_id}'\n"
        "    assert:\n"
        "      - type: is-json\n"
        "      - type: python\n"
        f"        value: '{assertion_path}'\n"
    )


def _render_promptfoo_assertion(*, target: str, golden_path: Path, threshold: float) -> str:
    return f'''"""Promptfoo Python assertion for AIPM v4 deterministic checks."""

import json
from pathlib import Path

from app.iteration.evaluator import V4Evaluator

TARGET = {target!r}
GOLDEN_PATH = {str(golden_path)!r}
THRESHOLD = {threshold!r}


def get_assert(output, context):
    parsed = json.loads(output) if isinstance(output, str) else output
    golden = json.loads(Path(GOLDEN_PATH).read_text(encoding="utf-8"))
    evaluator = V4Evaluator(target=TARGET, deterministic_threshold=THRESHOLD, run_llm_judge=False)
    target_output = parsed.get(TARGET, {{}}) if isinstance(parsed, dict) else {{}}
    score, failures, metrics = evaluator._deterministic_score(target_output, golden)
    return {{
        "pass": score >= THRESHOLD and not failures,
        "score": score,
        "reason": "; ".join(failures),
        "componentResults": [
            {{"assertion": "count_thresholds", "pass": not any("count" in failure for failure in failures)}},
            {{"assertion": "explicit_ratio", "pass": not any("explicit evidence ratio" in failure for failure in failures)}},
            {{"assertion": "id_reference_integrity", "pass": not metrics.get("id_reference_failures")}},
            {{"assertion": "semantic_hard_failures", "pass": not metrics.get("hard_failure_tags")}},
        ],
    }}
'''


def _summarize_promptfoo(parsed: dict[str, Any]) -> dict[str, Any]:
    results = parsed.get("results") or parsed.get("table", {}).get("body") or []
    return {"result_count": len(results) if isinstance(results, list) else 0}

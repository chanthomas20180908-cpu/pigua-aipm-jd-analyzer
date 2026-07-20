"""目的：LLM 调用层。

定义：OpenAI 兼容接口的统一 JSON 调用封装。

范围包括：
- 环境变量读取、LLM 配置检测、JSON schema 调用和错误封装。

范围不包括：
- 不写业务 prompt，不处理前端展示。

使用与修改规则：
- 修改模型参数或错误行为时同步 README 环境变量说明。
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List

import httpx
from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError

from app.prompts import (
    CANDIDATE_EXTRACTION_SYSTEM_PROMPT,
    JD_EXTRACTION_SYSTEM_PROMPT,
    LLM_RESULT_SYSTEM_PROMPT,
    V2_NARRATOR_SYSTEM_PROMPT,
    build_candidate_extraction_user_prompt,
    build_jd_extraction_user_prompt,
    build_llm_result_user_prompt,
    build_v2_narrator_user_prompt,
)
from app.prompts_v3 import (
    CANDIDATE_V3_SYSTEM_PROMPT,
    FINAL_V3_SYSTEM_PROMPT,
    JD_V3_SYSTEM_PROMPT,
    build_candidate_v3_user_prompt,
    build_final_v3_user_prompt,
    build_jd_v3_user_prompt,
)
from app.trace_logger import TraceLogger


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-plus"
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10.0
DEFAULT_WRITE_TIMEOUT_SECONDS = 30.0
DEFAULT_READ_TIMEOUT_SECONDS = 300.0
DEFAULT_POOL_TIMEOUT_SECONDS = 30.0
_USAGE_TRACKER: ContextVar["UsageTracker | None"] = ContextVar("llm_usage_tracker", default=None)


class LLMEnhancementError(RuntimeError):
    pass


@dataclass
class UsageRecord:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    duration_ms: int = 0
    error_type: str = ""
    succeeded: bool = True


@dataclass
class UsageTracker:
    records: list[UsageRecord] = field(default_factory=list)

    @property
    def input_tokens(self) -> int:
        return sum(record.input_tokens for record in self.records)

    @property
    def output_tokens(self) -> int:
        return sum(record.output_tokens for record in self.records)

    @property
    def total_tokens(self) -> int:
        return sum(record.total_tokens for record in self.records)


@contextmanager
def track_usage() -> Iterator[UsageTracker]:
    """Collect LLM token usage for the current context only."""
    tracker = UsageTracker()
    token = _USAGE_TRACKER.set(tracker)
    try:
        yield tracker
    finally:
        _USAGE_TRACKER.reset(token)


def llm_is_configured() -> bool:
    return bool(os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY"))


def _build_client() -> OpenAI:
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMEnhancementError("Missing DASHSCOPE_API_KEY or OPENAI_API_KEY.")

    connect_timeout = float(
        os.getenv("OPENAI_CONNECT_TIMEOUT_SECONDS", str(DEFAULT_CONNECT_TIMEOUT_SECONDS))
    )
    write_timeout = float(
        os.getenv("OPENAI_WRITE_TIMEOUT_SECONDS", str(DEFAULT_WRITE_TIMEOUT_SECONDS))
    )
    read_timeout = float(
        os.getenv("OPENAI_READ_TIMEOUT_SECONDS", os.getenv("OPENAI_TIMEOUT_SECONDS", str(DEFAULT_READ_TIMEOUT_SECONDS)))
    )
    pool_timeout = float(
        os.getenv("OPENAI_POOL_TIMEOUT_SECONDS", str(DEFAULT_POOL_TIMEOUT_SECONDS))
    )
    timeout = httpx.Timeout(
        connect=connect_timeout,
        write=write_timeout,
        read=read_timeout,
        pool=pool_timeout,
    )
    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL),
        timeout=timeout,
        max_retries=0,
    )


def _extract_json(content: str) -> Dict[str, Any]:
    text = _strip_markdown_json_fence(content.strip())
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        raise LLMEnhancementError("LLM response JSON root was not an object.")
    except json.JSONDecodeError:
        pass

    json_object = _find_outer_json_object(text)
    if json_object is None:
        raise LLMEnhancementError("LLM response did not contain a JSON object.")
    try:
        parsed = json.loads(json_object)
        if not isinstance(parsed, dict):
            raise LLMEnhancementError("LLM response JSON root was not an object.")
        return parsed
    except json.JSONDecodeError as exc:
        raise LLMEnhancementError("Failed to parse LLM JSON response.") from exc


def _strip_markdown_json_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if not lines:
        return text
    first_line = lines[0].strip().lower()
    if first_line not in {"```", "```json"}:
        return text
    for index in range(len(lines) - 1, 0, -1):
        if lines[index].strip() == "```":
            return "\n".join(lines[1:index]).strip()
    return text


def _find_outer_json_object(text: str) -> str | None:
    start_index: int | None = None
    depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start_index = index
            depth += 1
            continue
        if char != "}" or depth == 0:
            continue

        depth -= 1
        if depth == 0 and start_index is not None:
            return text[start_index : index + 1]
    return None


def _sanitize_list(values: Any, fallback: List[str]) -> List[str]:
    if not isinstance(values, list):
        return fallback
    cleaned = [str(item).strip() for item in values if str(item).strip()]
    return cleaned[:4] if cleaned else fallback


def enhance_analysis_result(
    *,
    jd_text: str,
    resume_text: str,
    user_level: str,
    goal: str,
    rule_result: Dict[str, Any],
) -> Dict[str, Any]:
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    payload = {
        "user_level": user_level,
        "goal": goal,
        "jd_text": jd_text,
        "resume_text": resume_text,
        "rule_result": {
            "recommendation": rule_result["recommendation"],
            "match_score": rule_result["match_score"],
            "job_type": rule_result["job_type"],
            "job_signals": rule_result["job_signals"],
            "candidate_signals": rule_result["candidate_signals"],
            "strengths": rule_result["strengths"],
            "risks": rule_result["risks"],
            "next_actions": rule_result["next_actions"],
            "summary": rule_result["summary"],
        },
    }

    parsed = call_llm_json(
        system_prompt=LLM_RESULT_SYSTEM_PROMPT,
        user_prompt=build_llm_result_user_prompt(payload),
        temperature=0.3,
    )

    enhanced = dict(rule_result)
    enhanced["summary"] = str(parsed.get("summary") or rule_result["summary"]).strip()
    enhanced["strengths"] = _sanitize_list(parsed.get("strengths"), rule_result["strengths"])
    enhanced["risks"] = _sanitize_list(parsed.get("risks"), rule_result["risks"])
    enhanced["next_actions"] = _sanitize_list(parsed.get("next_actions"), rule_result["next_actions"])
    enhanced["meta"] = {
        **rule_result.get("meta", {}),
        "llm": {
            "used": True,
            "provider": "dashscope-compatible",
            "model": model,
        },
    }
    return enhanced


def enhance_v2_narration(
    *,
    jd_text: str,
    resume_text: str,
    job_analysis: Dict[str, Any],
    candidate_analysis: Dict[str, Any],
    match_result: Dict[str, Any],
    recommendation_result: Dict[str, Any],
    fallback_result: Dict[str, Any],
    trace_logger: TraceLogger | None = None,
) -> Dict[str, Any]:
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    payload = {
        "jd_text": jd_text,
        "resume_text": resume_text,
        "job_analysis": job_analysis,
        "candidate_analysis": candidate_analysis,
        "match_result": match_result,
        "recommendation_result": recommendation_result,
    }
    user_prompt = build_v2_narrator_user_prompt(payload)
    parsed = call_llm_json(
        system_prompt=V2_NARRATOR_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.3,
        trace_logger=trace_logger,
    )
    return {
        "summary": str(parsed.get("summary") or fallback_result["summary"]).strip(),
        "strengths": _sanitize_list(parsed.get("strengths"), fallback_result["strengths"]),
        "risks": _sanitize_list(parsed.get("risks"), fallback_result["risks"]),
        "next_actions": _sanitize_list(parsed.get("next_actions"), fallback_result["next_actions"]),
        "meta": {
            "llm": {
                "used": True,
                "provider": "dashscope-compatible",
                "model": model,
            }
        },
    }


def call_llm_json(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    trace_logger: TraceLogger | None = None,
    timeout: float | None = None,
    retry_count: int = 0,
    retry_backoff: float = 1.0,
) -> Dict[str, Any]:
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    attempts = max(1, retry_count + 1)
    last_error: Exception | None = None
    for attempt_index in range(attempts):
        raw_response = ""
        response: Any | None = None
        started_at = time.perf_counter()
        try:
            client = _build_client()
            request_kwargs: Dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
            }
            if timeout is not None:
                request_kwargs["timeout"] = timeout
            response = client.chat.completions.create(**request_kwargs)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            raw_response = response.choices[0].message.content or ""
            parsed = _extract_json(raw_response)
            _record_usage(
                model=model,
                response=response,
                duration_ms=duration_ms,
                succeeded=True,
            )
            if trace_logger:
                trace_logger.add_llm(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    raw_response=raw_response,
                    parsed_response=parsed,
                    timing_ms=duration_ms,
                )
            return parsed
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            error_payload = _error_payload(exc)
            if response is not None:
                _record_usage(
                    model=model,
                    response=response,
                    duration_ms=duration_ms,
                    succeeded=False,
                    error_type=error_payload["type"],
                )
            else:
                _record_failed_attempt(
                    model=model,
                    duration_ms=duration_ms,
                    error_type=error_payload["type"],
                )
            if trace_logger:
                trace_logger.add_llm(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    raw_response=raw_response or str(exc),
                    parsed_response=None,
                    timing_ms=duration_ms,
                    error=error_payload,
                )
            last_error = exc
            if attempt_index >= attempts - 1 or not _is_retryable_error(exc):
                raise
            time.sleep(max(0.0, retry_backoff) * (2**attempt_index))
    if last_error is not None:
        raise last_error
    raise LLMEnhancementError("LLM call failed without a captured exception.")


def _record_usage(
    *,
    model: str,
    response: Any,
    duration_ms: int,
    succeeded: bool,
    error_type: str = "",
) -> None:
    tracker = _USAGE_TRACKER.get()
    if tracker is None:
        return
    usage = getattr(response, "usage", None)
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    if usage is not None:
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(
            getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0) or 0
        )
        total_tokens = int(getattr(usage, "total_tokens", 0) or input_tokens + output_tokens)
    tracker.records.append(
        UsageRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            error_type=error_type,
            succeeded=succeeded,
        )
    )


def _record_failed_attempt(*, model: str, duration_ms: int, error_type: str) -> None:
    tracker = _USAGE_TRACKER.get()
    if tracker is None:
        return
    tracker.records.append(
        UsageRecord(
            model=model,
            duration_ms=duration_ms,
            error_type=error_type,
            succeeded=False,
        )
    )


def _error_payload(exc: Exception) -> Dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": str(exc),
    }


def _is_retryable_error(exc: Exception) -> bool:
    retryable_types = (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError, httpx.TimeoutException)
    if isinstance(exc, retryable_types):
        return True
    if isinstance(exc, LLMEnhancementError):
        return "parse" in str(exc).lower() or "json" in str(exc).lower()
    return type(exc).__name__ in {"APITimeoutError", "RateLimitError", "APIConnectionError", "InternalServerError"}


def extract_jd_with_llm(
    jd_text: str, trace_logger: TraceLogger | None = None
) -> Dict[str, Any]:
    """Use LLM to extract structured JD analysis."""
    user_prompt = build_jd_extraction_user_prompt(jd_text)
    parsed = call_llm_json(
        system_prompt=JD_EXTRACTION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        trace_logger=trace_logger,
    )
    # Basic validation: ensure top-level keys exist
    required_keys = {"job_profile", "job_requirements", "job_risk_flags"}
    missing = required_keys - set(parsed.keys())
    if missing:
        raise LLMEnhancementError(f"JD extraction missing keys: {missing}")
    return parsed


def extract_candidate_with_llm(
    resume_text: str, job_analysis: Dict[str, Any], trace_logger: TraceLogger | None = None
) -> Dict[str, Any]:
    """Use LLM to extract structured candidate analysis."""
    user_prompt = build_candidate_extraction_user_prompt(resume_text, job_analysis)
    parsed = call_llm_json(
        system_prompt=CANDIDATE_EXTRACTION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        trace_logger=trace_logger,
    )
    required_keys = {"candidate_profile", "candidate_evidence", "missing_evidence"}
    missing = required_keys - set(parsed.keys())
    if missing:
        raise LLMEnhancementError(f"Candidate extraction missing keys: {missing}")
    # Ensure role_mismatch_flag exists and is bool
    if "role_mismatch_flag" not in parsed:
        parsed["role_mismatch_flag"] = False
    return parsed


def _validate_jd_v3(parsed: Dict[str, Any]) -> None:
    """Ensure the JD v3 extraction contains the minimal required structure."""
    business_flow = parsed.get("business_flow")
    if not isinstance(business_flow, dict):
        raise LLMEnhancementError("JD v3 extraction missing 'business_flow'.")
    value_stream = business_flow.get("value_stream")
    if not isinstance(value_stream, dict) or not value_stream.get("name"):
        raise LLMEnhancementError("JD v3 extraction missing 'business_flow.value_stream.name'.")
    activities = business_flow.get("activities")
    if not isinstance(activities, list) or not activities:
        raise LLMEnhancementError("JD v3 extraction missing 'business_flow.activities'.")
    for activity in activities:
        if not isinstance(activity, dict) or not activity.get("activity_name"):
            raise LLMEnhancementError("JD v3 activity missing 'activity_name'.")
        tasks = activity.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            raise LLMEnhancementError(
                f"JD v3 activity '{activity.get('activity_name')}' missing 'tasks'."
            )


def _validate_candidate_v3(parsed: Dict[str, Any]) -> None:
    """Ensure the candidate v3 extraction contains the minimal required structure."""
    candidate_evidence = parsed.get("candidate_evidence")
    if not isinstance(candidate_evidence, dict):
        raise LLMEnhancementError("Candidate v3 extraction missing 'candidate_evidence'.")
    modeled = candidate_evidence.get("modeled_capabilities")
    if not isinstance(modeled, list) or not modeled:
        raise LLMEnhancementError(
            "Candidate v3 extraction missing 'candidate_evidence.modeled_capabilities'."
        )
    expected_task_count = 0
    for component in modeled:
        if not isinstance(component, dict) or not component.get("component_name"):
            raise LLMEnhancementError(
                "Candidate v3 modeled_capability missing 'component_name'."
            )
        tasks = component.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            raise LLMEnhancementError(
                f"Candidate v3 component '{component.get('component_name')}' missing 'tasks'."
            )
        expected_task_count += len(tasks)

    # Validate task-level mappings
    task_mappings = candidate_evidence.get("task_mappings")
    if not isinstance(task_mappings, list):
        raise LLMEnhancementError("Candidate v3 extraction missing 'candidate_evidence.task_mappings'.")
    if len(task_mappings) != expected_task_count:
        raise LLMEnhancementError(
            f"Candidate v3 task_mappings count mismatch: {len(task_mappings)} mappings for {expected_task_count} tasks."
        )
    valid_relationships = {"direct_match", "partial_match", "related", "no_match"}
    required_keys = {"resume_component", "resume_task", "jd_activity_id", "jd_task_id", "relationship", "confidence", "reason"}
    for idx, mapping in enumerate(task_mappings):
        if not isinstance(mapping, dict):
            raise LLMEnhancementError(f"Candidate v3 task_mapping[{idx}] is not an object.")
        missing = required_keys - set(mapping.keys())
        if missing:
            raise LLMEnhancementError(
                f"Candidate v3 task_mapping[{idx}] missing keys: {missing}"
            )
        relationship = mapping.get("relationship")
        if relationship not in valid_relationships:
            raise LLMEnhancementError(
                f"Candidate v3 task_mapping[{idx}] invalid relationship: {relationship}"
            )
        confidence = mapping.get("confidence")
        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            raise LLMEnhancementError(
                f"Candidate v3 task_mapping[{idx}] confidence must be 0-1 number."
            )
        if relationship != "no_match":
            if not str(mapping.get("jd_task_id", "")).strip():
                raise LLMEnhancementError(
                    f"Candidate v3 task_mapping[{idx}] non-no_match mapping missing jd_task_id."
                )


def extract_jd_v3(
    jd_text: str, trace_logger: TraceLogger | None = None
) -> Dict[str, Any]:
    """Use LLM to extract structured JD analysis for v3 workflow."""
    user_prompt = build_jd_v3_user_prompt(jd_text)
    parsed = call_llm_json(
        system_prompt=JD_V3_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        trace_logger=trace_logger,
    )
    # _validate_jd_v3(parsed)
    return parsed


def extract_candidate_v3(
    resume_text: str,
    job_analysis: Dict[str, Any],
    trace_logger: TraceLogger | None = None,
) -> Dict[str, Any]:
    """Use LLM to extract structured candidate analysis for v3 workflow."""
    user_prompt = build_candidate_v3_user_prompt(resume_text, job_analysis)
    parsed = call_llm_json(
        system_prompt=CANDIDATE_V3_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        trace_logger=trace_logger,
    )
    # _validate_candidate_v3(parsed)
    if not isinstance(parsed.get("role_mismatch_flag"), bool):
        parsed["role_mismatch_flag"] = bool(parsed.get("role_mismatch_flag"))
    return parsed


def synthesize_final_v3(
    *,
    jd_text: str,
    job_analysis: Dict[str, Any],
    trace_logger: TraceLogger | None = None,
) -> Dict[str, Any]:
    """Use LLM to produce final JD assessment and narration for v3 workflow."""
    user_prompt = build_final_v3_user_prompt(
        jd_text=jd_text,
        job_analysis=job_analysis,
    )
    parsed = call_llm_json(
        system_prompt=FINAL_V3_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        trace_logger=trace_logger,
    )
    """
    required_keys = {
        "recommendation",
        "match_score",
        "conclusion_label",
        "summary",
        "strengths",
        "risks",
        "next_actions",
        "supplements",
    }
    missing = required_keys - set(parsed.keys())
    if missing:
        raise LLMEnhancementError(f"Final v3 synthesis missing keys: {missing}")

    # Normalize and validate recommendation / match_score alignment
    rec = str(parsed.get("recommendation", "")).strip()
    if rec not in {"冲", "可投", "谨慎", "避开"}:
        raise LLMEnhancementError(f"Final v3 invalid recommendation: {rec}")

    try:
        score = int(parsed.get("match_score"))
    except (TypeError, ValueError) as exc:
        raise LLMEnhancementError("Final v3 match_score must be an integer.") from exc

    score_ranges = {
        "冲": (80, 100),
        "可投": (65, 79),
        "谨慎": (50, 64),
        "避开": (0, 49),
    }
    low, high = score_ranges[rec]
    if not (low <= score <= high):
        raise LLMEnhancementError(
            f"Final v3 recommendation/match_score mismatch: {rec}/{score} (expected {low}-{high})"
        )
    parsed["match_score"] = score

    # Validate conclusion_label
    valid_labels = {"保熟", "半熟", "生瓜蛋子", "秤有问题", "吸铁石", "萨日朗"}
    label = str(parsed.get("conclusion_label", "")).strip()
    if label not in valid_labels:
        raise LLMEnhancementError(f"Final v3 invalid conclusion_label: {label}")

    # Validate supplements: exactly 3 items with required sub-fields
    supplements = parsed.get("supplements")
    if not isinstance(supplements, list) or len(supplements) != 3:
        raise LLMEnhancementError("Final v3 supplements must be a list of exactly 3 items.")
    required_sub_keys = {"type", "target", "description", "suggested_action"}
    for idx, item in enumerate(supplements):
        if not isinstance(item, dict):
            raise LLMEnhancementError(f"Final v3 supplement[{idx}] is not an object.")
        missing_sub = required_sub_keys - set(item.keys())
        if missing_sub:
            raise LLMEnhancementError(
                f"Final v3 supplement[{idx}] missing keys: {missing_sub}"
            )
        if not all(str(item.get(k, "")).strip() for k in required_sub_keys):
            raise LLMEnhancementError(
                f"Final v3 supplement[{idx}] has empty required fields."
            )
    """

    return parsed

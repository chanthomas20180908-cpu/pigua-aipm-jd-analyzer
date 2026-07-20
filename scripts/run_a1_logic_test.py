"""目的：run_a1_logic_test.py 开发辅助脚本。

定义：scripts/run_a1_logic_test.py 是本地验证或调试脚本。

范围包括：
- 从项目根目录运行的开发辅助逻辑。

范围不包括：
- 不作为线上服务入口。

使用与修改规则：
- 脚本依赖项目路径时使用 Path 定位，避免依赖当前 shell 的偶然状态。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.capabilities import candidate_analysis, jd_analysis, match_scoring, recommendation

DEFAULT_CASE_FILE = REPO_ROOT / "data/test_cases_v1/cases/case_002.json"
DEFAULT_GOLDEN_FILE = REPO_ROOT / "data/test_cases_v1/golden/case_002_golden.json"
DEFAULT_OUTPUT_DIR = Path("/tmp")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalize_actual(
    *,
    jd_result: Dict[str, Any],
    candidate_result: Dict[str, Any],
    match_result: Dict[str, Any],
    recommendation_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "recommendation": recommendation_result["recommendation"],
        "dimension_scores": match_result["dimension_scores"],
        "weighted_match_score": match_result["weighted_match_score"],
        "gate_check_result": match_result["gate_check_result"],
        "non_compensatory_gaps": match_result["non_compensatory_gaps"],
        "compensatory_gaps": match_result["compensatory_gaps"],
        "confidence": match_result["confidence"],
        "job_risk_level": match_result["job_risk_level"],
        "job_analysis": jd_result["job_analysis"],
        "candidate_analysis": candidate_result["candidate_analysis"],
        "recommendation_result": recommendation_result,
    }


def _gap_categories(values: List[str]) -> set[str]:
    categories: set[str] = set()
    for value in values:
        lowered = value.lower()
        if any(token in value for token in ("业务", "行业", "场景")) or any(
            token in lowered for token in ("business", "domain")
        ):
            categories.add("business_fit")
        if any(token in value for token in ("AI", "智能体")) or "ai" in lowered:
            categories.add("ai")
        if any(token in value for token in ("技术", "模型", "API", "评测")) or any(
            token in lowered for token in ("technical", "api", "model")
        ):
            categories.add("technical")
        if any(token in value for token in ("指标", "结果")) or any(token in lowered for token in ("metric", "result")):
            categories.add("metrics")
    return categories


def _assert_equal(name: str, actual: Any, expected: Any) -> Dict[str, Any]:
    passed = actual == expected
    return {
        "name": name,
        "passed": passed,
        "expected": expected,
        "actual": actual,
        "detail": "" if passed else f"{name} expected {expected!r} but got {actual!r}",
    }


def _assert_score_range(name: str, actual: int, expected: int, tolerance: int) -> Dict[str, Any]:
    delta = actual - expected
    passed = abs(delta) <= tolerance
    return {
        "name": name,
        "passed": passed,
        "expected": expected,
        "actual": actual,
        "detail": "" if passed else f"{name} delta {delta} exceeds tolerance ±{tolerance}",
    }


def _assert_dimension_scores(actual: Dict[str, int], expected: Dict[str, int]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        delta = None if actual_value is None else actual_value - expected_value
        passed = actual_value is not None and abs(delta) <= 1
        checks.append(
            {
                "name": f"dimension_scores.{key}",
                "passed": passed,
                "expected": expected_value,
                "actual": actual_value,
                "detail": ""
                if passed
                else f"dimension_scores.{key} delta {delta} exceeds tolerance ±1",
            }
        )
    return checks


def _assert_gap_expectations(actual: Dict[str, Any]) -> List[Dict[str, Any]]:
    compensatory_categories = _gap_categories(actual["compensatory_gaps"])
    non_comp_categories = _gap_categories(actual["non_compensatory_gaps"])
    return [
        {
            "name": "non_compensatory_gaps.empty",
            "passed": not actual["non_compensatory_gaps"],
            "expected": [],
            "actual": actual["non_compensatory_gaps"],
            "detail": ""
            if not actual["non_compensatory_gaps"]
            else "non_compensatory_gaps should stay empty for A1 case_002",
        },
        {
            "name": "compensatory_gaps.contains_business_fit",
            "passed": "business_fit" in compensatory_categories,
            "expected": "business_fit category present",
            "actual": actual["compensatory_gaps"],
            "detail": ""
            if "business_fit" in compensatory_categories
            else "compensatory_gaps should reflect cross-domain/business-fit weakness",
        },
        {
            "name": "compensatory_gaps.no_ai_or_technical_gap",
            "passed": "ai" not in compensatory_categories and "technical" not in compensatory_categories,
            "expected": "no ai/technical category",
            "actual": actual["compensatory_gaps"],
            "detail": ""
            if "ai" not in compensatory_categories and "technical" not in compensatory_categories
            else "compensatory_gaps should not claim AI or technical weakness for A1 case_002",
        },
        {
            "name": "non_compensatory_gaps.no_ai_or_technical_gap",
            "passed": "ai" not in non_comp_categories and "technical" not in non_comp_categories,
            "expected": "no ai/technical category",
            "actual": actual["non_compensatory_gaps"],
            "detail": ""
            if "ai" not in non_comp_categories and "technical" not in non_comp_categories
            else "non_compensatory_gaps should not claim AI or technical weakness for A1 case_002",
        },
    ]


def evaluate(actual: Dict[str, Any], golden: Dict[str, Any]) -> Dict[str, Any]:
    golden_label = golden["golden_label"]
    checks: List[Dict[str, Any]] = [
        _assert_equal("recommendation", actual["recommendation"], golden_label["recommendation"]),
        _assert_equal("gate_check_result.passed", actual["gate_check_result"]["passed"], True),
        _assert_equal("gate_check_result.failed_reasons", actual["gate_check_result"]["failed_reasons"], []),
        _assert_equal("job_risk_level", actual["job_risk_level"], golden_label["job_risk_level"]),
        _assert_equal("confidence.level", actual["confidence"]["level"], golden_label["confidence"]["level"]),
        _assert_score_range(
            "weighted_match_score",
            actual["weighted_match_score"],
            golden_label["weighted_match_score"],
            tolerance=5,
        ),
        _assert_score_range(
            "confidence.score",
            actual["confidence"]["score"],
            golden_label["confidence"]["score"],
            tolerance=10,
        ),
    ]
    checks.extend(_assert_dimension_scores(actual["dimension_scores"], golden_label["dimension_scores"]))
    checks.extend(_assert_gap_expectations(actual))

    passed = all(check["passed"] for check in checks)
    failed_checks = [check for check in checks if not check["passed"]]
    return {
        "passed": passed,
        "checks": checks,
        "failed_checks": failed_checks,
    }


def _compare_table(actual: Dict[str, Any], golden: Dict[str, Any]) -> List[str]:
    golden_label = golden["golden_label"]
    rows = [
        "| Field | Golden | Actual |",
        "| --- | --- | --- |",
        f"| recommendation | {golden_label['recommendation']} | {actual['recommendation']} |",
        f"| weighted_match_score | {golden_label['weighted_match_score']} | {actual['weighted_match_score']} |",
        f"| gate_passed | {golden_label['gate_check_result']['passed']} | {actual['gate_check_result']['passed']} |",
        f"| confidence.level | {golden_label['confidence']['level']} | {actual['confidence']['level']} |",
        f"| confidence.score | {golden_label['confidence']['score']} | {actual['confidence']['score']} |",
        f"| job_risk_level | {golden_label['job_risk_level']} | {actual['job_risk_level']} |",
    ]
    for key, expected_value in golden_label["dimension_scores"].items():
        rows.append(f"| dimension_scores.{key} | {expected_value} | {actual['dimension_scores'].get(key)} |")
    return rows


def _failure_buckets(actual: Dict[str, Any], evaluation: Dict[str, Any]) -> Dict[str, List[str]]:
    buckets = {
        "JD 解析": [],
        "简历解析": [],
        "评分规则": [],
        "推荐阈值": [],
    }
    for failed in evaluation["failed_checks"]:
        name = failed["name"]
        if "job_risk_level" in name or "business_fit" in name:
            buckets["JD 解析"].append(failed["detail"])
        elif "gate_check_result" in name or "confidence" in name:
            buckets["简历解析"].append(failed["detail"])
        elif "dimension_scores" in name or "weighted_match_score" in name:
            buckets["评分规则"].append(failed["detail"])
        elif "recommendation" in name:
            buckets["推荐阈值"].append(failed["detail"])
    if actual["job_analysis"]["job_profile"].get("business_domain") == "general":
        buckets["JD 解析"].append("当前 JD 解析未把保险场景归一到专门业务域，business_fit 可能被高估或低估。")
    if not actual["candidate_analysis"]["candidate_profile"].get("experience_years"):
        buckets["简历解析"].append("当前简历年限提取依赖显式“X年经验”文本，时间段型履历不会触发经验 gate。")
    return buckets


def build_report(
    *,
    case_id: str,
    actual: Dict[str, Any],
    golden: Dict[str, Any],
    evaluation: Dict[str, Any],
) -> str:
    compare_table = _compare_table(actual, golden)
    buckets = _failure_buckets(actual, evaluation)
    status = "通过" if evaluation["passed"] else "不通过"
    if not evaluation["passed"] and len(evaluation["failed_checks"]) <= 3:
        status = "部分通过"

    lines = [
        f"# A1 Logic Test Report: {case_id}",
        "",
        "## 结论",
        "",
        f"- 状态：{status}",
        f"- recommendation：{actual['recommendation']}",
        f"- weighted_match_score：{actual['weighted_match_score']}",
        f"- confidence：{actual['confidence']['level']} / {actual['confidence']['score']}",
        "",
        "## 金标 vs 实际",
        "",
        *compare_table,
        "",
        "## 断言结果",
        "",
        "| Check | Result | Detail |",
        "| --- | --- | --- |",
    ]
    for check in evaluation["checks"]:
        result = "PASS" if check["passed"] else "FAIL"
        detail = check["detail"] or "-"
        lines.append(f"| {check['name']} | {result} | {detail} |")

    lines.extend(
        [
            "",
            "## 偏差归因",
            "",
            "| Bucket | Notes |",
            "| --- | --- |",
        ]
    )
    for bucket, notes in buckets.items():
        joined = "；".join(notes) if notes else "-"
        lines.append(f"| {bucket} | {joined} |")

    lines.extend(
        [
            "",
            "## 关键中间值",
            "",
            f"- job_profile.business_domain: `{actual['job_analysis']['job_profile'].get('business_domain')}`",
            f"- job_profile.ai_maturity: `{actual['job_analysis']['job_profile'].get('ai_maturity')}`",
            f"- candidate_profile.experience_years: `{actual['candidate_analysis']['candidate_profile'].get('experience_years')}`",
            f"- candidate_profile.ai_experience_level: `{actual['candidate_analysis']['candidate_profile'].get('ai_experience_level')}`",
            f"- compensatory_gaps: `{actual['compensatory_gaps']}`",
            f"- non_compensatory_gaps: `{actual['non_compensatory_gaps']}`",
            "",
        ]
    )
    return "\n".join(lines)


def run_case(case_file: Path, golden_file: Path, output_dir: Path) -> Dict[str, Path]:
    case_data = _read_json(case_file)
    golden_data = _read_json(golden_file)
    jd_text = _read_text(REPO_ROOT / case_data["jd_file"])
    resume_text = _read_text(REPO_ROOT / case_data["resume_file"])

    jd_result = jd_analysis.run(jd_text)
    candidate_result = candidate_analysis.run(resume_text, job_analysis=jd_result["job_analysis"])
    match_result = match_scoring.run(
        job_analysis=jd_result["job_analysis"],
        candidate_analysis=candidate_result["candidate_analysis"],
    )
    recommendation_result = recommendation.run(
        match_result=match_result,
        job_analysis=jd_result["job_analysis"],
    )

    actual = _normalize_actual(
        jd_result=jd_result,
        candidate_result=candidate_result,
        match_result=match_result,
        recommendation_result=recommendation_result,
    )
    evaluation = evaluate(actual, golden_data)
    report = build_report(
        case_id=case_data["id"],
        actual=actual,
        golden=golden_data,
        evaluation=evaluation,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    actual_path = output_dir / "a1_case_002_actual.json"
    report_path = output_dir / "a1_case_002_eval.md"
    actual_path.write_text(json.dumps(actual, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
    return {
        "actual_path": actual_path,
        "report_path": report_path,
        "passed": output_dir / ".passed",
        "evaluation": report_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline logic evaluation for A1 case_002.")
    parser.add_argument("--case-file", type=Path, default=DEFAULT_CASE_FILE)
    parser.add_argument("--golden-file", type=Path, default=DEFAULT_GOLDEN_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    results = run_case(args.case_file, args.golden_file, args.output_dir)
    report_text = results["report_path"].read_text(encoding="utf-8")
    print(report_text)
    return 0 if "状态：通过" in report_text else 1


if __name__ == "__main__":
    raise SystemExit(main())

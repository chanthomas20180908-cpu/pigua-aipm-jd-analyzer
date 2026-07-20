"""目的：verify_llm_extraction.py 开发辅助脚本。

定义：scripts/verify_llm_extraction.py 是本地验证或调试脚本。

范围包括：
- 从项目根目录运行的开发辅助逻辑。

范围不包括：
- 不作为线上服务入口。

使用与修改规则：
- 脚本依赖项目路径时使用 Path 定位，避免依赖当前 shell 的偶然状态。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import llm_client
from app.capabilities import candidate_analysis, jd_analysis

CASE_FILE = REPO_ROOT / "data/test_cases_v1/cases/case_002.json"


def main() -> int:
    case = json.loads(CASE_FILE.read_text(encoding="utf-8"))
    jd_text = (REPO_ROOT / case["jd_file"]).read_text(encoding="utf-8")
    resume_text = (REPO_ROOT / case["resume_file"]).read_text(encoding="utf-8")

    jd_result = jd_analysis.run(jd_text)
    candidate_result = candidate_analysis.run(resume_text, job_analysis=jd_result["job_analysis"])

    job_profile = jd_result["job_analysis"]["job_profile"]
    candidate_profile = candidate_result["candidate_analysis"]["candidate_profile"]

    print("=" * 60)
    print(f"LLM configured: {llm_client.llm_is_configured()}")
    jd_meta = jd_result["meta"].get("jd_extraction_meta", {})
    resume_meta = candidate_result["meta"].get("resume_extraction_meta", {})
    print(f"JD extraction LLM used: {jd_meta.get('llm_used')}")
    print(f"JD extraction fallback: {jd_meta.get('llm_fallback')}")
    print(f"Resume extraction LLM used: {resume_meta.get('llm_used')}")
    print(f"Resume extraction fallback: {resume_meta.get('llm_fallback')}")
    print("-" * 60)
    print("JD profile:")
    print(f"  industry_domain: {job_profile.get('industry_domain')!r}")
    print(f"  business_orientation: {job_profile.get('business_orientation')!r}")
    print(f"  role_perspective: {job_profile.get('role_perspective')!r}")
    print(f"  enterprise_type: {job_profile.get('enterprise_type')!r}")
    print("-" * 60)
    print("Candidate profile:")
    print(f"  candidate_role_orientation: {candidate_profile.get('candidate_role_orientation')!r}")
    print(f"  role_mismatch_flag: {candidate_result['candidate_analysis'].get('role_mismatch_flag')!r}")
    print("=" * 60)

    if llm_client.llm_is_configured():
        checks = [
            job_profile.get("industry_domain") == "insurance",
            job_profile.get("business_orientation") == "business-heavy",
            job_profile.get("role_perspective") == "pm",
            candidate_profile.get("candidate_role_orientation") == "engineer",
            candidate_result["candidate_analysis"].get("role_mismatch_flag") is True,
        ]
        if all(checks):
            print("All case_002 LLM extraction assertions passed.")
            return 0
        print("Some case_002 LLM extraction assertions failed.")
        return 1

    print("No LLM API key configured; running in rule fallback mode. Skipping LLM field assertions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

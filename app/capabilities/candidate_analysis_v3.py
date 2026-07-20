"""目的：candidate_analysis_v3.py 旧版能力模块。

定义：app/capabilities/candidate_analysis_v3.py 是 v2/v3 兼容能力代码的一部分。

范围包括：
- 旧版分析流程需要的能力函数和数据结构。

范围不包括：
- 不承载当前 v4 主链路的新判断逻辑。

使用与修改规则：
- 除兼容修复外不扩展；新能力进入 app/sub_modules/。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app import llm_client
from app.trace_logger import TraceLogger


def run(
    resume_text: str,
    job_analysis: Optional[Dict[str, Any]] = None,
    trace_logger: TraceLogger | None = None,
) -> Dict[str, object]:
    parsed = llm_client.extract_candidate_v3(
        resume_text, job_analysis or {}, trace_logger=trace_logger
    )
    return {
        "candidate_analysis": parsed,
        "meta": {
            "resume_extraction": parsed,
            "resume_extraction_meta": {
                "llm_used": True,
                "llm_fallback": False,
                "candidate_match_summary": parsed.get("candidate_match_summary", ""),
            },
        },
    }

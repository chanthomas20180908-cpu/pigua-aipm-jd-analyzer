"""目的：jd_analysis_v3.py 旧版能力模块。

定义：app/capabilities/jd_analysis_v3.py 是 v2/v3 兼容能力代码的一部分。

范围包括：
- 旧版分析流程需要的能力函数和数据结构。

范围不包括：
- 不承载当前 v4 主链路的新判断逻辑。

使用与修改规则：
- 除兼容修复外不扩展；新能力进入 app/sub_modules/。
"""

from __future__ import annotations

from typing import Dict

from app import llm_client
from app.trace_logger import TraceLogger


def run(raw_jd_text: str, trace_logger: TraceLogger | None = None) -> Dict[str, object]:
    parsed = llm_client.extract_jd_v3(raw_jd_text, trace_logger=trace_logger)
    return {
        "job_analysis": parsed,
        "meta": {
            "jd_extraction": parsed,
            "jd_extraction_meta": {
                "llm_used": True,
                "llm_fallback": False,
                "jd_core_judgment": parsed.get("jd_core_judgment", ""),
            },
        },
    }

"""目的：v2 工作流兼容实现。

定义：旧版 /analyze 接口使用的职位匹配工作流。

范围包括：
- 规则 parser、旧 capability 和兼容 LLM 增强流程。

范围不包括：
- 不作为新功能维护入口。

使用与修改规则：
- 除兼容修复外不要扩展；新能力进入 v4。
"""

from __future__ import annotations

from typing import Dict

from app.capabilities import candidate_analysis, jd_analysis, match_scoring, narration, recommendation
from app.trace_logger import TraceLogger


def run(*, jd_text: str, resume_text: str) -> Dict[str, object]:
    trace_logger = TraceLogger()
    trace_logger.add_request(
        jd_text=jd_text,
        resume_text=resume_text,
    )

    jd_result = jd_analysis.run(jd_text, trace_logger=trace_logger)
    trace_logger.add_step(
        step="步骤 1: JD 分析",
        purpose="把原始 JD 文本转成岗位画像、要求和风险信号。",
        input_data={"jd_text": jd_text},
        output_data=jd_result,
        key_points={
            "job_family": jd_result["job_analysis"]["job_profile"].get("job_family"),
            "business_domain": jd_result["job_analysis"]["job_profile"].get("business_domain"),
            "ai_maturity": jd_result["job_analysis"]["job_profile"].get("ai_maturity"),
        },
    )

    candidate_result = candidate_analysis.run(
        resume_text, job_analysis=jd_result["job_analysis"], trace_logger=trace_logger
    )
    trace_logger.add_step(
        step="步骤 2: 候选人分析",
        purpose="把简历文本转成候选人画像、证据和缺口。",
        input_data={"resume_text": resume_text},
        output_data=candidate_result,
        key_points={
            "experience_years": candidate_result["candidate_analysis"]["candidate_profile"].get("experience_years"),
            "ai_experience_level": candidate_result["candidate_analysis"]["candidate_profile"].get(
                "ai_experience_level"
            ),
            "candidate_role_orientation": candidate_result["candidate_analysis"]["candidate_profile"].get(
                "candidate_role_orientation"
            ),
            "role_mismatch_flag": candidate_result["candidate_analysis"].get("role_mismatch_flag"),
            "llm_used": candidate_result["meta"]
            .get("resume_extraction_meta", {})
            .get("llm_used"),
        },
    )

    match_result = match_scoring.run(
        job_analysis=jd_result["job_analysis"],
        candidate_analysis=candidate_result["candidate_analysis"],
    )
    trace_logger.add_step(
        step="步骤 3: 匹配评分",
        purpose="基于岗位要求和候选人证据做 gate、维度分和缺口判断。",
        input_data={
            "job_analysis": jd_result["job_analysis"],
            "candidate_analysis": candidate_result["candidate_analysis"],
        },
        output_data=match_result,
        key_points={
            "weighted_match_score": match_result.get("weighted_match_score"),
            "confidence": match_result.get("confidence"),
            "gate_passed": match_result.get("gate_check_result", {}).get("passed"),
        },
    )

    recommendation_result = recommendation.run(
        match_result=match_result,
        job_analysis=jd_result["job_analysis"],
    )
    trace_logger.add_step(
        step="步骤 4: 推荐结论",
        purpose="把评分结果转成投递建议、岗位风险和当前准备度。",
        input_data={
            "match_result": match_result,
            "job_analysis": jd_result["job_analysis"],
        },
        output_data=recommendation_result,
        key_points={
            "recommendation": recommendation_result.get("recommendation"),
            "job_risk_level": recommendation_result.get("job_risk_level"),
            "candidate_readiness_level": recommendation_result.get("candidate_readiness_level"),
        },
    )

    narration_result = narration.run(
        jd_text=jd_text,
        resume_text=resume_text,
        job_analysis=jd_result["job_analysis"],
        candidate_analysis=candidate_result["candidate_analysis"],
        match_result=match_result,
        recommendation_result=recommendation_result,
        trace_logger=trace_logger,
    )
    trace_logger.add_step(
        step="步骤 5: 文案生成",
        purpose="把推荐结论转换成用户可读的总结、优势、风险和下一步动作。",
        input_data={
            "job_analysis": jd_result["job_analysis"],
            "candidate_analysis": candidate_result["candidate_analysis"],
            "match_result": match_result,
            "recommendation_result": recommendation_result,
        },
        output_data=narration_result,
        key_points={
            "llm_used": narration_result.get("meta", {}).get("llm", {}).get("used"),
            "model": narration_result.get("meta", {}).get("llm", {}).get("model"),
        },
    )

    meta = {
        "version": "v2",
        "trace_id": trace_logger.trace_id,
        **jd_result["meta"],
        **candidate_result["meta"],
        **narration_result["meta"],
    }
    result = {
        "job_analysis": jd_result["job_analysis"],
        "candidate_analysis": candidate_result["candidate_analysis"],
        "match_result": match_result,
        "recommendation_result": {
            **recommendation_result,
            "summary": narration_result["summary"],
            "strengths": narration_result["strengths"],
            "risks": narration_result["risks"],
            "next_actions": narration_result["next_actions"],
        },
        "recommendation": recommendation_result["recommendation"],
        "match_score": match_result["weighted_match_score"],
        "job_type": jd_result["job_analysis"]["job_profile"].get("job_family", "general_ai_pm"),
        "summary": narration_result["summary"],
        "strengths": narration_result["strengths"],
        "risks": narration_result["risks"],
        "next_actions": narration_result["next_actions"],
        "meta": meta,
    }
    trace_logger.add_final(result=result)
    log_path = trace_logger.write()
    result["meta"]["trace_log_path"] = str(log_path)
    return result

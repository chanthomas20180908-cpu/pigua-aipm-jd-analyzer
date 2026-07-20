#!/usr/bin/env python3
"""目的：verify_v3_workflow.py 开发辅助脚本。

定义：scripts/verify_v3_workflow.py 是本地验证或调试脚本。

范围包括：
- 从项目根目录运行的开发辅助逻辑。

范围不包括：
- 不作为线上服务入口。

使用与修改规则：
- 脚本依赖项目路径时使用 Path 定位，避免依赖当前 shell 的偶然状态。
"""

"""Verify v3 workflow structure with mock LLM responses."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ["DASHSCOPE_API_KEY"] = "dummy-key-for-testing"

from app import llm_client
from app.workflows import analyze_job_fit_v3


def _load_case():
    case_path = REPO_ROOT / "data" / "test_cases_v1" / "cases" / "case_002.json"
    with open(case_path, encoding="utf-8") as f:
        case = json.load(f)
    with open(REPO_ROOT / case["jd_file"], encoding="utf-8") as f:
        jd_text = f.read()
    with open(REPO_ROOT / case["resume_file"], encoding="utf-8") as f:
        resume_text = f.read()
    return jd_text, resume_text


FAKE_JD = {
    "jd_core_judgment": "真AI落地岗，偏业务重，适合有B端AI交付经验的产品经理",
    "key_requirements": ["有AI Agent项目完整落地经验", "5年及以上toB产品经验", "保险业务场景理解"],
    "key_risks": ["协调成本高", "职责边界宽", "指标不够清晰"],
    "role_type": "产品型",
    "business_context": "保险行业客服/质检Agent落地",
    "business_flow": {
        "value_stream": {
            "name": "保险Agent从场景发现到持续优化",
            "purpose": "识别高价值保险场景并交付可运营的AI Agent",
            "definition": "覆盖场景探索、方案设计、能力建设、上线运营的价值闭环",
            "scope_includes": ["场景探索", "方案设计", "Agent开发", "上线运营"],
            "scope_excludes": ["底层模型训练", "基础设施运维"],
        },
        "activities": [
            {
                "activity_id": "A1",
                "activity_name": "探索保险业务场景",
                "sequence": 1,
                "purpose": "识别高价值可落地的保险业务场景",
                "definition": "通过业务调研和数据分析确定Agent落地场景",
                "scope_includes": ["业务痛点收集", "场景优先级排序"],
                "scope_excludes": ["具体方案设计", "技术开发"],
                "previous_activities": [],
                "next_activities": ["A2"],
                "feedback_to_activities": [],
                "tasks": [
                    {
                        "task_id": "A1-T1",
                        "task_name": "访谈业务人员",
                        "purpose": "获取一线业务痛点",
                        "definition": "与业务方沟通，识别可被Agent替代或增强的环节",
                        "scope_includes": ["客服", "质检", "核保"],
                        "scope_excludes": ["技术可行性评估"],
                        "inputs": ["业务现状报告", "客户投诉数据"],
                        "outputs": ["场景痛点清单"],
                    }
                ],
            },
            {
                "activity_id": "A2",
                "activity_name": "设计Agent解决方案",
                "sequence": 2,
                "purpose": "将业务需求转化为可实现的Agent方案",
                "definition": "设计Agent工作流、知识库和评测体系",
                "scope_includes": ["工作流设计", "Prompt设计", "评测集建设"],
                "scope_excludes": ["模型训练", "代码开发"],
                "previous_activities": ["A1"],
                "next_activities": [],
                "feedback_to_activities": ["A1"],
                "tasks": [
                    {
                        "task_id": "A2-T1",
                        "task_name": "设计Agent工作流",
                        "purpose": "定义Agent处理业务的完整流程",
                        "definition": "设计意图识别、工具调用、异常兜底的流程",
                        "scope_includes": ["主流程", "分支流程", "异常流程"],
                        "scope_excludes": ["前端界面设计"],
                        "inputs": ["场景痛点清单", "业务规则"],
                        "outputs": ["Agent工作流图"],
                    }
                ],
            },
        ],
    },
}

FAKE_FINAL = {
    "recommendation": "可投",
    "match_score": 75,
    "conclusion_label": "半熟",
    "summary": "这瓜半熟——保险Agent赛道方向不错，业务流设计也算清晰，但部分职责边界写得有点模糊。面试时多问问团队分工和指标口径，别急着接。",
    "strengths": ["保险Agent场景方向明确，业务流从探索到运营闭环完整", "JD中对Agent工作流设计有具体要求，说明团队有一定认知"],
    "risks": ["职责边界偏宽，协调成本高", "指标不够清晰，入职后目标可能漂移"],
    "next_actions": ["面试时确认团队规模和分工", "提前了解保险客服/质检的业务流程"],
    "supplements": [
        {
            "type": "jd_highlight",
            "target": "A1 探索保险业务场景",
            "description": "JD明确提到场景探索和业务痛点收集，说明岗位不是纯执行，有策略空间。",
            "suggested_action": "面试时展示你对保险场景的理解和场景优先级判断框架。",
        },
        {
            "type": "hard_requirement",
            "target": "5年及以上toB产品经验",
            "description": "JD要求5年toB产品经验，这在AI PM市场算正常门槛，不算虚高。",
            "suggested_action": "确认自己年限匹配，准备1-2个toB AI交付案例。",
        },
        {
            "type": "context_missing",
            "target": "Agent运营指标",
            "description": "JD提到对业务指标负责但未给出具体指标定义，面试时需要对齐。",
            "suggested_action": "面试时主动问：考核什么指标？目前基线是多少？",
        },
    ],
}


def _fake_build_client():
    responses = iter(
        [
            json.dumps(FAKE_JD, ensure_ascii=False),
            json.dumps(FAKE_FINAL, ensure_ascii=False),
        ]
    )

    def create(*args, **kwargs):
        return MagicMock(choices=[MagicMock(message=MagicMock(content=next(responses)))])

    client = MagicMock()
    client.chat.completions.create = create
    return client


def main():
    jd_text, _resume_text = _load_case()

    responses = iter(
        [
            json.dumps(FAKE_JD, ensure_ascii=False),
            json.dumps(FAKE_FINAL, ensure_ascii=False),
        ]
    )

    def _fake_build_client():
        def create(*args, **kwargs):
            return MagicMock(choices=[MagicMock(message=MagicMock(content=next(responses)))])

        client = MagicMock()
        client.chat.completions.create = create
        return client

    llm_client._build_client = _fake_build_client

    result = analyze_job_fit_v3.run(jd_text=jd_text)

    # Top-level fields
    assert result.get("recommendation") == "可投"
    assert result.get("match_score") == 75
    assert isinstance(result.get("summary"), str) and result["summary"]
    assert isinstance(result.get("strengths"), list) and result["strengths"]
    assert isinstance(result.get("risks"), list) and result["risks"]
    assert isinstance(result.get("next_actions"), list) and result["next_actions"]
    assert result.get("conclusion_label") in {"保熟", "半熟", "生瓜蛋子", "秤有问题", "吸铁石", "萨日朗"}
    supplements = result.get("supplements")
    assert isinstance(supplements, list) and len(supplements) == 3
    for idx, item in enumerate(supplements):
        assert isinstance(item, dict), f"supplement[{idx}] is not dict"
        assert set(item.keys()) >= {"type", "target", "description", "suggested_action"}
        assert all(str(item.get(k, "")).strip() for k in ("type", "target", "description", "suggested_action"))

    # JD analysis
    jd_analysis = result["job_analysis"]
    assert jd_analysis.get("jd_core_judgment")
    assert isinstance(jd_analysis.get("key_requirements"), list) and jd_analysis["key_requirements"]
    assert isinstance(jd_analysis.get("key_risks"), list) and jd_analysis["key_risks"]
    assert jd_analysis.get("role_type") in ("产品型", "工程型", "混合型")
    assert isinstance(jd_analysis.get("business_context"), str) and jd_analysis["business_context"]

    # JD business_flow structure
    business_flow = jd_analysis.get("business_flow") or {}
    assert isinstance(business_flow.get("value_stream"), dict)
    assert business_flow["value_stream"].get("name")
    activities = business_flow.get("activities") or []
    assert isinstance(activities, list) and len(activities) >= 1
    for activity in activities:
        assert activity.get("activity_id")
        assert activity.get("activity_name")
        assert isinstance(activity.get("tasks"), list) and activity["tasks"]
        for task in activity["tasks"]:
            assert task.get("task_id")
            assert task.get("task_name")
            assert "inputs" in task and "outputs" in task

    # Meta
    assert result["meta"]["version"] == "v3"
    assert "trace_id" in result["meta"]
    assert "trace_log_path" in result["meta"]

    trace_path = result["meta"]["trace_log_path"]
    with open(trace_path, encoding="utf-8") as f:
        log = f.read()
    assert log.count("### LLM 调用") == 2
    assert "## 步骤 1: JD 分析" in log
    assert "## 步骤 2: JD 终局判断" in log

    print("v3 workflow structure verification passed.")
    print(f"trace_log_path: {trace_path}")
    print(f"jd_core_judgment: {jd_analysis['jd_core_judgment']}")


if __name__ == "__main__":
    main()

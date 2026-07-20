"""目的：验证前端验收 fixture 的 trace 提取边界。

定义：对 scripts/extract_frontend_sample.py 的纯本地解析逻辑进行单元测试。

范围包括：
- 完整 trace 提取、缺失模块失败与敏感调试字段阻断。

范围不包括：
- 不调用 LLM、不依赖被 Git 忽略的真实 logs 目录。

使用与修改规则：
- trace 标题格式或 v4 模块集合变更时同步调整合成样本和断言。
"""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "extract_frontend_sample.py"
SPEC = importlib.util.spec_from_file_location("extract_frontend_sample", SCRIPT_PATH)
assert SPEC and SPEC.loader
EXTRACTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXTRACTOR)


def make_trace(include_all_modules: bool = True, unsafe_output: bool = False) -> str:
    modules = [
        ("element_modeling", '{"value_streams": []}'),
        ("jd_core_judgment", '{"core_judgment": "判断"}'),
        ("quality_check", '{"risk_points": []}'),
        ("narration", '{"conclusion_label": "保熟", "summary": "总结"}'),
    ]
    if not include_all_modules:
        modules.pop()
    if unsafe_output:
        modules[0] = ("element_modeling", '{"system_prompt": "不能进入 fixture"}')
    blocks = [
        "# Analyze Trace: trace-fixture-001",
        "",
        "## 请求输入",
        "",
        "```json",
        '{"jd_text": "这是用于测试的岗位描述，长度足够。"}',
        "```",
    ]
    for index, (name, output) in enumerate(modules, start=1):
        blocks.extend(
            [
                "",
                f"## 模块 / {name} (v=v1)",
                "",
                f"- timing_ms: {index * 10}",
                "",
                "### 输出",
                "```json",
                output,
                "```",
            ]
        )
    blocks.extend(["", "### LLM 调用", "```json", '{"model": "qwen-plus"}', "```"])
    return "\n".join(blocks)


class FrontendSampleExtractorTests(unittest.TestCase):
    """Ensure explicit trace promotion remains complete and privacy-safe."""

    def _extract(self, trace: str):
        with tempfile.TemporaryDirectory() as directory:
            trace_path = Path(directory) / "trace.md"
            trace_path.write_text(trace, encoding="utf-8")
            return EXTRACTOR.extract_frontend_fixture(trace_path)

    def test_extracts_complete_api_shaped_fixture(self):
        fixture = self._extract(make_trace())
        self.assertEqual("trace-fixture-001", fixture["_meta"]["trace_id"])
        self.assertEqual("v4", fixture["_meta"]["version"])
        self.assertEqual(100, fixture["_meta"]["timing"]["workflow_total_ms"])
        self.assertEqual("保熟", fixture["narration"]["conclusion_label"])

    def test_rejects_missing_module(self):
        with self.assertRaises(EXTRACTOR.TraceExtractionError):
            self._extract(make_trace(include_all_modules=False))

    def test_rejects_debug_fields_in_module_output(self):
        with self.assertRaises(EXTRACTOR.TraceExtractionError):
            self._extract(make_trace(unsafe_output=True))


if __name__ == "__main__":
    unittest.main()

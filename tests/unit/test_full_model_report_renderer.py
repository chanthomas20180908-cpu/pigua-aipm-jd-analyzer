"""目的：验证完整元模型可视化报告渲染器的本地安全边界。

定义：直接加载 skill 随附渲染器的单元测试，不调用模型、网络或服务。

范围包括：JSON 附录提取、模型引用校验、HTML 安全嵌入和输出覆盖保护。

范围不包括：不验证浏览器像素、不模拟 Codex 会话、不评估 JD 分析质量。

使用与修改规则：修改完整报告契约或渲染器交互钩子时同步维护断言。
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
RENDERER_PATH = ROOT / "skills" / "ai-pm-jd-analyzer" / "tools" / "render_full_model_report.py"
SPEC = importlib.util.spec_from_file_location("full_model_report_renderer", RENDERER_PATH)
assert SPEC and SPEC.loader
renderer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = renderer
SPEC.loader.exec_module(renderer)


class FullModelReportRendererTests(unittest.TestCase):
    """Protect the portable report renderer against malformed or unsafe source reports."""

    @classmethod
    def setUpClass(cls):
        cls.report_path = ROOT / "workbench" / "case_002_jd_full_model_analysis.md"
        cls.report = cls.report_path.read_text(encoding="utf-8")

    def test_extracts_case_002_and_renders_required_model_sections(self):
        payload = renderer.extract_report_payload(self.report)
        self.assertEqual("ai_pm_jd_full_model/v1", payload.model["schema_version"])
        self.assertEqual(4, len(payload.model["value_streams"]))
        self.assertEqual(7, len(payload.model["work_items"]))
        self.assertEqual(11, len(payload.model["business_entities"]))
        self.assertEqual(9, len(payload.model["business_capabilities"]))
        self.assertEqual(8, len(payload.model["qualification_requirements"]))
        self.assertEqual(4, len(payload.model["risks"]))
        self.assertEqual(3, len(payload.model["uncertainties"]))
        page = renderer.build_html(payload, "case_002_jd_full_model_analysis.md")
        for marker in (
            "model-workbench",
            "graph-svg",
            "data-node-type",
            "data-edge-type",
            "graph-filter",
            "graph-zoom-controls",
            'id="graph-zoom-in"',
            'id="graph-zoom-out"',
            "detail-drawer",
            "openDetail",
            "使用左下角按钮缩放",
            "event.ctrlKey",
            "查看 Markdown",
            "relationship-tab",
            "value-stream-tab",
            "capability-tab",
            "requirement-tab",
            "value-stream-view",
            "capability-view",
            "requirement-view",
            "roles-rail",
            "requirement-board",
            "capability-relations",
            "entity-relations",
            "report-details",
            "model-detail-drawer",
            "岗位准入条件",
        ):
            self.assertIn(marker, page)
        self.assertNotIn("cdn.jsdelivr", page)
        self.assertNotIn("滚轮缩放", page)

    def test_keeps_relationship_graph_four_typed_nodes_and_adds_data_driven_views(self):
        payload = renderer.extract_report_payload(self.report)
        page = renderer.build_html(payload, "case_002_jd_full_model_analysis.md")
        graph_node_setup = page.split("const addNode", 1)[1].split("const addEdge", 1)[0]
        self.assertIn("addNode(item,'stream')", graph_node_setup)
        self.assertIn("addNode(item,'work')", graph_node_setup)
        self.assertIn("addNode(item,'entity')", graph_node_setup)
        self.assertIn("addNode(item,'capability')", graph_node_setup)
        self.assertNotIn("addNode(item,'role')", graph_node_setup)
        self.assertNotIn("addNode(item,'requirement')", graph_node_setup)
        self.assertIn("responsibility_assignments", page)
        self.assertIn("qualification_requirements", page)
        self.assertIn("primary_capability_id", page)
        self.assertIn("mapping_target_ids", page)
        self.assertIn("entity_relationships", page)
        self.assertIn("capability_relationships", page)
        self.assertIn("targetView", page)
        self.assertIn("renderRequirements", page)
        self.assertIn("stayInView", page)
        self.assertIn("JD 未建模出角色责任分配。", page)
        self.assertIn("JD 未建模出任职要求。", page)

    def test_keeps_contextual_links_in_their_origin_view_and_separates_requirements(self):
        payload = renderer.extract_report_payload(self.report)
        page = renderer.build_html(payload, "case_002_jd_full_model_analysis.md")
        capability_view = page.split('id="capability-view"', 1)[1].split('id="requirement-view"', 1)[0]
        self.assertNotIn("任职要求映射", capability_view)
        self.assertNotIn("requirements-rail", capability_view)
        self.assertIn("link(work.id,work.name,'',true)", page)
        self.assertIn("'crud',true", page)
        self.assertIn("'capability',true", page)
        self.assertIn("CRUD 实体：", page)
        self.assertIn("责任分配：", page)

    def test_model_detail_drawer_uses_shared_selection_and_non_modal_close_rules(self):
        payload = renderer.extract_report_payload(self.report)
        page = renderer.build_html(payload, "case_002_jd_full_model_analysis.md")

        for marker in (
            "data-model-detail-trigger",
            "bindModelDetailTrigger",
            "clearModelDetailSelection",
            "closeModelDetail",
            "event.target.closest('[data-model-detail-trigger]')",
            "aria-controls",
            "aria-expanded",
            "model-detail-selected",
            "closeDetail(false)",
            "closeModelDetail(false)",
            ".model-detail-drawer { display:none!important; }",
        ):
            self.assertIn(marker, page)

    def test_model_views_define_muted_semantic_type_tokens(self):
        payload = renderer.extract_report_payload(self.report)
        page = renderer.build_html(payload, "case_002_jd_full_model_analysis.md")

        for marker in (
            "--role:#5d7881",
            "--capability:#28736f",
            ".role-card",
            ".stream-container",
            ".work-card",
            ".capability-container",
            ".entity-card",
            ".requirement-map",
        ):
            self.assertIn(marker, page)

    def test_rejects_missing_or_duplicate_json_appendix(self):
        without_heading = self.report.replace("## 结构化模型 JSON", "## 附录", 1)
        with self.assertRaisesRegex(renderer.ReportRenderError, "缺少“结构化模型 JSON”章节"):
            renderer.extract_report_payload(without_heading)
        duplicate = self.report + "\n```json\n{}\n```\n"
        with self.assertRaisesRegex(renderer.ReportRenderError, "仅含有一个"):
            renderer.extract_report_payload(duplicate)

    def test_rejects_wrong_schema_and_dangling_reference(self):
        payload = renderer.extract_report_payload(self.report)
        broken = json.loads(json.dumps(payload.model))
        broken["schema_version"] = "unknown/v9"
        with self.assertRaisesRegex(renderer.ReportRenderError, "不支持的 schema_version"):
            renderer.validate_model(broken)
        broken = json.loads(json.dumps(payload.model))
        broken["work_items"][0]["value_stream_id"] = "missing-stream"
        with self.assertRaisesRegex(renderer.ReportRenderError, "不存在的 id"):
            renderer.validate_model(broken)

    def test_escapes_script_terminators_and_never_overwrites_without_force(self):
        payload = renderer.extract_report_payload(self.report)
        payload = renderer.ReportPayload(payload.title, ("安全 </script> 内容",), payload.model)
        page = renderer.build_html(payload, "source.md")
        self.assertIn("<\\/script>", page)
        with tempfile.TemporaryDirectory() as temporary_dir:
            directory = Path(temporary_dir)
            source = directory / "report.md"
            output = directory / "report.html"
            source.write_text(self.report, encoding="utf-8")
            output.write_text("old", encoding="utf-8")
            with self.assertRaisesRegex(renderer.ReportRenderError, "--force"):
                renderer.render_file(source, output)
            renderer.render_file(source, output, force=True)
            self.assertIn("完整元模型图谱", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

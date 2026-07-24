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


def item(item_id: str, name: str) -> dict:
    return {"id": item_id, "name": name, "evidence": {"status": "explicit"}}


SAMPLE_MODEL = {
    "schema_version": "ai_pm_jd_full_model/v1",
    "source": {"input_type": "jd", "language": "zh-CN"},
    "company_context": {"fields": {}},
    "job_profile": {"fields": {}},
    "value_streams": [item("stream-1", "场景交付")],
    "work_items": [
        {
            **item("work-1", "设计交付方案"),
            "value_stream_id": "stream-1",
            "entity_operations": [
                {"entity_id": "entity-1", "operation": "create", "evidence": {"status": "explicit"}}
            ],
            "capability_ids": ["capability-1"],
        }
    ],
    "roles": [item("role-1", "产品交付负责人")],
    "responsibility_assignments": [
        {"role_id": "role-1", "work_item_id": "work-1", "raci": "responsible", "evidence": {"status": "explicit"}}
    ],
    "business_entities": [{**item("entity-1", "交付方案"), "primary_capability_id": "capability-1"}],
    "entity_relationships": [],
    "business_capabilities": [{**item("capability-1", "方案设计"), "supported_work_item_ids": ["work-1"]}],
    "capability_relationships": [],
    "qualification_requirements": [
        {
            **item("requirement-1", "产品经验"),
            "content_category": "experience",
            "necessity": "mandatory",
            "objectivity": "objective",
            "association_level": "work_item",
            "mapping_status": "directly_linked",
            "mapping_target_ids": ["work-1"],
        }
    ],
    "work_environment": {"fields": {}},
    "compensation_benefits": {"fields": {}},
    "risks": [item("risk-1", "交付风险")],
    "uncertainties": [item("uncertainty-1", "职责边界")],
    "judgment": {"fields": {}},
}

SAMPLE_REPORT = "# 匿名完整元模型报告\n\n用于渲染器单测的公开匿名模型。\n\n## 结构化模型 JSON\n\n```json\n" + json.dumps(
    SAMPLE_MODEL, ensure_ascii=False
) + "\n```\n"


class FullModelReportRendererTests(unittest.TestCase):
    """Protect the portable report renderer against malformed or unsafe source reports."""

    @classmethod
    def setUpClass(cls):
        cls.report = cls._synthetic_v2_report()

    @staticmethod
    def _synthetic_v2_report() -> str:
        evidence = {"status": "explicit", "snippets": ["合成测试证据"]}
        model = {
            "schema_version": "ai_pm_jd_full_model/v2",
            "source": {"input_type": "jd", "language": "zh-CN"},
            "company_context": {"fields": {}},
            "job_profile": {"fields": {}},
            "value_streams": [{"id": "vs", "name": "需求交付", "description": "将已确认需求转化为可交付结果。", "evidence": evidence}],
            "work_items": [{"id": "wi", "name": "评估任务结果", "description": "检查任务是否满足预期业务目标。", "value_stream_id": "vs", "entity_operations": [{"entity_id": "entity", "operation": "read", "evidence": evidence}], "capability_ids": ["cap"], "evidence": evidence}],
            "roles": [{"id": "role", "name": "产品管理角色", "description": "负责组织需求验证与结果判断。", "evidence": evidence}],
            "responsibility_assignments": [{"role_id": "role", "work_item_id": "wi", "raci": "responsible", "evidence": evidence}],
            "business_entities": [{"id": "entity", "name": "任务评测结果", "description": "记录任务执行后的可评估业务结果。", "domain": "data_knowledge", "abstraction_level": "specialized_type", "primary_capability_id": "cap", "attributes": [{"name": "任务完成率", "description": "衡量任务按预期完成的比例。", "evidence": evidence}], "evidence": evidence}],
            "entity_relationships": [],
            "business_capabilities": [{"id": "cap", "name": "任务结果评测管理", "description": "稳定评估任务结果并管理其质量属性。", "category": "AI评测与质量管理", "primary_entity_ids": ["entity"], "supported_work_item_ids": ["wi"], "evidence": evidence}],
            "capability_relationships": [],
            "qualification_requirements": [{"id": "req", "name": "结果评估经验", "description": "具备判断任务结果质量的相关经验。", "content_category": "experience", "necessity": "preferred", "objectivity": "objective", "association_level": "capability", "mapping_status": "directly_linked", "mapping_target_ids": ["cap"], "evidence": evidence}],
            "work_environment": {"fields": {}},
            "compensation_benefits": {"fields": {}},
            "risks": [{"id": "risk", "name": "指标口径待确认", "description": "未披露任务完成率的计算口径。", "evidence": {"status": "not_disclosed"}}],
            "uncertainties": [{"id": "uncertainty", "name": "验收阈值待确认", "description": "未披露任务结果的验收阈值。", "evidence": {"status": "not_disclosed"}}],
            "judgment": {"fields": {}},
        }
        return "# 合成完整元模型报告\n\n结论：用于验证本地渲染器。\n\n## 结构化模型 JSON\n\n```json\n" + json.dumps(model, ensure_ascii=False) + "\n```\n"

    def test_extracts_v2_model_and_renders_required_model_sections(self):
        payload = renderer.extract_report_payload(self.report)
        self.assertEqual("ai_pm_jd_full_model/v2", payload.model["schema_version"])
        self.assertEqual(1, len(payload.model["value_streams"]))
        self.assertEqual(1, len(payload.model["work_items"]))
        self.assertEqual(1, len(payload.model["business_entities"]))
        self.assertEqual(1, len(payload.model["business_capabilities"]))
        self.assertEqual(1, len(payload.model["qualification_requirements"]))
        self.assertEqual(1, len(payload.model["risks"]))
        self.assertEqual(1, len(payload.model["uncertainties"]))
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
            "requirement-board",
            "capability-relations",
            "entity-relations",
            "report-details",
            "model-detail-drawer",
            "岗位准入条件",
        ):
            self.assertIn(marker, page)
        self.assertNotIn("roles-rail", page)
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
        self.assertIn("primary_entity_ids", page)
        self.assertIn("JD 支持属性", page)
        self.assertIn("mapping_target_ids", page)
        self.assertIn("entity_relationships", page)
        self.assertIn("capability_relationships", page)
        self.assertIn("targetView", page)
        self.assertIn("renderRequirements", page)
        self.assertIn("stayInView", page)
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
        self.assertIn("'role',true", page)
        self.assertIn("CRUD 实体：", page)
        self.assertIn("责任分配：", page)
        self.assertIn("association('执行角色'", page)
        self.assertIn("JD 未明确执行角色。", page)

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

    def test_model_views_share_distinct_semantic_type_tokens(self):
        payload = renderer.extract_report_payload(self.report)
        page = renderer.build_html(payload, "case_002_jd_full_model_analysis.md")

        for marker in (
            "--type-stream:#2f6b57",
            "--type-work:#556ead",
            "--type-entity:#b7791f",
            "--type-capability:#2c7a7b",
            "--type-role:#7c5a91",
            "--type-requirement:#a14d67",
            "--type-stream:#8ac4a8",
            "--type-work:#aab9ed",
            "--type-entity:#f0bd69",
            "--type-capability:#83cfca",
            "--type-role:#d1b6e1",
            "--type-requirement:#e6a1b6",
            "--type-stream-surface:#e8f1ec",
            "--type-work-surface:#edf0fb",
            "--type-entity-surface:#fbf3e4",
            "--type-capability-surface:#e8f4f3",
            "--type-role-surface:#f4edf7",
            "--type-role-surface:#34263d",
            "--type-requirement-surface:#f9edf1",
            ".stream-container",
            ".work-card",
            ".association-link.type-role",
            ".capability-container",
            ".entity-card",
            ".requirement-map",
            ".detail-link.type-stream",
            "const elementKinds={",
            "metric type-${type}",
            "type-${elementKinds[types[id]] || 'neutral'}",
            "--report-font-size:13px",
            "body,body *,body *::before,body *::after { font-size:var(--report-font-size)!important; }",
            ".graph-zoom-button,.drawer-close,.model-detail-close { font-size:20px!important; }",
            "rowPitch = {stream:82,work:92,entity:98,capability:98}",
        ):
            self.assertIn(marker, page)
        self.assertNotIn("make('article','role-card')", page)

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

    def test_rejects_missing_descriptions_attributes_and_reciprocal_ownership(self):
        payload = renderer.extract_report_payload(self.report)
        broken = json.loads(json.dumps(payload.model))
        broken["work_items"][0]["description"] = ""
        with self.assertRaisesRegex(renderer.ReportRenderError, "业务 description"):
            renderer.validate_model(broken)

        broken = json.loads(json.dumps(payload.model))
        broken["business_entities"][0]["attributes"][0].pop("evidence")
        with self.assertRaisesRegex(renderer.ReportRenderError, "缺少证据"):
            renderer.validate_model(broken)

        broken = json.loads(json.dumps(payload.model))
        entity = broken["business_entities"][0]
        capability = next(
            item
            for item in broken["business_capabilities"]
            if item["id"] == entity["primary_capability_id"]
        )
        replacement = json.loads(json.dumps(entity))
        replacement["id"] = "entity-replacement"
        broken["business_entities"].append(replacement)
        capability["primary_entity_ids"] = [replacement["id"]]
        with self.assertRaisesRegex(renderer.ReportRenderError, "未被主归属能力"):
            renderer.validate_model(broken)

        broken = json.loads(json.dumps(payload.model))
        broken["business_capabilities"][0]["primary_entity_ids"] = []
        with self.assertRaisesRegex(renderer.ReportRenderError, "缺少主归属实体列表"):
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

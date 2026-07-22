"""
目的：验证 AI PM JD skill 源包的静态契约。

定义：不启动另一个 Codex 会话、不调用模型或网络的本地单元测试。

范围包括：skill 文件结构、metadata、reference 链接、自包含边界和报告章节。

范围不包括：隐式触发行为、Agent 输出质量或人工会话验收。

使用与修改规则：skill 文件或默认报告契约变更时同步维护本测试与人工验收文档。
"""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "ai-pm-jd-analyzer"


class AiPmJdSkillTests(unittest.TestCase):
    """Protect the self-contained, local-only skill package contract."""

    @classmethod
    def setUpClass(cls):
        cls.skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        cls.references = {
            name: (SKILL_DIR / "references" / name).read_text(encoding="utf-8")
            for name in ("meta-model.md", "modeling-rules.md", "full-model-report-contract.md")
        }
        cls.schema = json.loads((SKILL_DIR / "references" / "full-model-schema.json").read_text(encoding="utf-8"))
        cls.ui_metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")

    def test_skill_has_valid_identity_and_all_references(self):
        self.assertTrue(self.skill.startswith("---\nname: ai-pm-jd-analyzer\n"))
        self.assertIn("description:", self.skill.split("---", 2)[1])
        for name in self.references:
            self.assertIn(f"references/{name}", self.skill)
        self.assertIn("references/full-model-schema.json", self.skill)
        self.assertIn('display_name: "AI PM JD Analyzer"', self.ui_metadata)
        self.assertIn("$ai-pm-jd-analyzer", self.ui_metadata)

    def test_package_has_only_the_allowed_local_renderer_and_no_remote_dependencies(self):
        self.assertFalse((SKILL_DIR / "scripts").exists())
        renderer = (SKILL_DIR / "tools" / "render_full_model_report.py").read_text(encoding="utf-8")
        self.assertTrue((SKILL_DIR / "tools" / "README.md").is_file())
        self.assertNotIn("http://", renderer)
        self.assertNotIn("https://", renderer)
        self.assertNotIn("requests", renderer)
        self.assertIn("Do not browse, call APIs, start this repository's service", self.skill)
        self.assertIn("Automatic local delivery", self.skill)
        self.assertIn(".agents/ai-pm-jd-reports/<unique-run-id>/", self.skill)
        self.assertIn("report.md", self.skill)
        self.assertIn("report.html", self.skill)
        self.assertIn("render_full_model_report.py report.md --output report.html", self.skill)
        for content in self.references.values():
            self.assertNotIn("../", content)
            self.assertNotIn("app/", content)
            self.assertNotIn("data/", content)

    def test_complete_reference_model_and_report_contract_are_complete(self):
        meta_model = self.references["meta-model.md"]
        for term in (
            "公司上下文", "岗位画像", "角色责任", "业务实体", "业务能力", "任职要求",
            "工作环境", "薪酬福利", "风险与不确定性", "not_disclosed",
        ):
            self.assertIn(term, meta_model)

        rules = self.references["modeling-rules.md"]
        for term in ("明确", "推断", "CRUD", "伪 AI", "primary_capability_id", "accountable"):
            self.assertIn(term, rules)

        contract = self.references["full-model-report-contract.md"]
        for heading in ("事实、推断与未披露边界", "价值流、事项与角色责任", "最需确认三件事", "面试追问", "结构化模型 JSON"):
            self.assertIn(heading, contract)

    def test_full_model_schema_defines_complete_contract_and_controlled_relationships(self):
        self.assertEqual("AI PM JD Full Reference Meta Model v2", self.schema["title"])
        self.assertEqual("ai_pm_jd_full_model/v2", self.schema["properties"]["schema_version"]["const"])
        required = set(self.schema["required"])
        self.assertTrue(
            {
                "company_context", "job_profile", "value_streams", "work_items", "roles",
                "responsibility_assignments", "business_entities", "entity_relationships",
                "business_capabilities", "capability_relationships", "qualification_requirements",
                "work_environment", "compensation_benefits", "risks", "uncertainties", "judgment",
            } <= required
        )
        definitions = self.schema["$defs"]
        self.assertIn("description", definitions["item"]["required"])
        self.assertIn("attributes", definitions["entity"]["required"])
        self.assertEqual(["name", "description", "evidence"], definitions["attribute"]["required"])
        self.assertIn("primary_entity_ids", definitions["capability"]["required"])
        self.assertIn("supported_work_item_ids", definitions["capability"]["required"])
        self.assertEqual(["explicit", "inferred", "not_disclosed"], definitions["status"]["enum"])
        self.assertEqual(
            ["responsible", "accountable", "consulted", "informed"],
            definitions["raci_relationship"]["properties"]["raci"]["enum"],
        )
        self.assertEqual(
            ["parent_of", "lifecycle_precedes", "input_to", "related_to"],
            definitions["entity_relationship"]["properties"]["relation_type"]["enum"],
        )
        self.assertEqual(
            "depends_on",
            definitions["capability_relationship"]["properties"]["relation_type"]["const"],
        )
        self.assertIn("primary_capability_id", definitions["entity"]["required"])


if __name__ == "__main__":
    unittest.main()

"""
目的：验证首页前端关键交互结构未被静默删除。
定义：不启动浏览器的静态 HTML、JavaScript 和 CSS 结构测试。
范围包括：
- Landing 页面、历史记录、结论展示、错误状态和共享主题的必要入口。
范围不包括：
- 不验证浏览器视觉布局，不调用后端或外部 LLM。
使用与修改规则：
- 前端关键交互变更时同步维护断言，避免将文案微调误写为脆弱测试。
"""

from pathlib import Path
import unittest
import json


ROOT = Path(__file__).resolve().parents[2]


class FrontendStructureTests(unittest.TestCase):
    """Protect the release-critical frontend hooks used by manual QA."""

    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "static/design-preview-02.html").read_text(encoding="utf-8")
        cls.javascript = (ROOT / "static/design-preview-02.js").read_text(encoding="utf-8")
        cls.graph_renderer = (ROOT / "static/graph-renderer.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "static/design-preview-02.css").read_text(encoding="utf-8")
        cls.theme_css = (ROOT / "static/theme.css").read_text(encoding="utf-8")
        cls.main = (ROOT / "app/main.py").read_text(encoding="utf-8")
        cls.fixture = json.loads(
            (ROOT / "static/fixtures/frontend-acceptance-v4.json").read_text(encoding="utf-8")
        )

    def test_input_and_loading_hooks_exist(self):
        for hook in ("data-sample-jd", "history-panel", "loading-status"):
            self.assertIn(hook, self.html)
        self.assertNotIn("file-input-hint", self.html + self.javascript + self.css)
        self.assertIn("input-feedback", self.html + self.css)
        self.assertNotIn("cancel-analysis-button", self.html)
        self.assertNotIn("cancelAnalysisButton", self.javascript)

    def test_history_is_limited_and_clearable(self):
        self.assertIn('HISTORY_STORAGE_KEY = "pigua-history-v1"', self.javascript)
        self.assertIn("HISTORY_LIMIT = 5", self.javascript)
        self.assertIn("function clearHistory()", self.javascript)
        self.assertIn("history-clear-button", self.html)

    def test_result_and_error_presentations_exist(self):
        for marker in (
            "conclusion-ripe",
            "conclusion-unripe",
            "conclusion-suspicious",
            "conclusion-sarilang",
            "summary-metrics",
            "error-illustration",
            "retry-analysis-button",
        ):
            self.assertIn(marker, self.javascript + self.css)

    def test_summary_preserves_model_authored_paragraphs(self):
        self.assertIn("function renderSummaryParagraphs(summary)", self.javascript)
        self.assertIn("split(/\\n\\s*\\n/)", self.javascript)
        self.assertIn("result-summary-paragraph", self.javascript + self.css)

    def test_shared_theme_blocks_scroll_boundary_bounce(self):
        self.assertIn("overscroll-behavior-y: none", self.theme_css)

    def test_open_graph_uses_a_dedicated_high_resolution_asset(self):
        for page in ("about.html", "design-preview-02.html", "error.html", "meta-model.html"):
            content = (ROOT / "static" / page).read_text(encoding="utf-8")
            self.assertIn("capybara-grid-og.png", content)

    def test_frontend_acceptance_sample_uses_the_production_renderer(self):
        for marker in (
            '@app.get("/sample")',
            "X-Robots-Tag",
            "SAMPLE_FIXTURE_URL",
            "isSampleMode",
            "loadFrontendSample",
            "saveHistory: false",
            "sample-banner",
        ):
            self.assertIn(marker, self.main + self.html + self.javascript)
        self.assertNotIn("来源 trace", self.javascript)

    def test_fixture_is_complete_and_has_no_llm_debug_content(self):
        self.assertTrue(
            {"jd_text", "element_modeling", "jd_core_judgment", "quality_check", "narration", "_meta"}
            <= set(self.fixture)
        )
        self.assertEqual("v4", self.fixture["_meta"]["version"])
        serialized = json.dumps(self.fixture, ensure_ascii=False)
        for forbidden in ("system_prompt", "user_prompt", "raw_response", "parsed_response"):
            self.assertNotIn(forbidden, serialized)

    def test_result_sections_have_cards_and_fullscreen_hooks(self):
        for marker in (
            "renderJudgmentSection",
            "JUDGMENT_CARD_FIELDS",
            "judgment-card",
            "graph-fullscreen-toggle",
            "graph-fullscreen-open",
            "refreshGraphLayout",
        ):
            self.assertIn(marker, self.html + self.javascript + self.css)
        self.assertNotIn("模块一 · 建模图谱", self.html)
        self.assertNotIn('jd_core_judgment: "模块一 · 岗位判断"', self.javascript + self.css)

    def test_graph_labels_and_zoom_controls_are_accessible(self):
        content = self.html + self.javascript + self.graph_renderer + self.css
        for marker in (
            "graph-zoom-controls",
            'data-graph-zoom="in"',
            'data-graph-zoom="out"',
            "aria-label=\"放大关系图\"",
            "aria-label=\"缩小关系图\"",
            "forceVisualBoundsCollision",
            "nodeVisualBounds",
            "GRAPH_LABEL_FONT_SIZE = 13",
            "event.type !== 'wheel'",
            "hasUserAdjustedView",
            "fitView(600, true)",
        ):
            self.assertIn(marker, content)


if __name__ == "__main__":
    unittest.main()

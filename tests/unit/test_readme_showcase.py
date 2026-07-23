"""Verify the resume-facing README keeps its visual and privacy contracts."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
SHOWCASE_DIR = ROOT / "static" / "assets" / "readme-showcase"


class ReadmeShowcaseTests(unittest.TestCase):
    def test_readme_references_lightweight_graph_assets(self):
        content = README.read_text(encoding="utf-8")
        assets = {
            "graph-focus.svg": 20_000,
            "graph-full.svg": 20_000,
        }

        for filename, byte_budget in assets.items():
            self.assertIn(f"static/assets/readme-showcase/{filename}", content)
            asset = SHOWCASE_DIR / filename
            self.assertTrue(asset.is_file())
            self.assertLessEqual(asset.stat().st_size, byte_budget)

        self.assertNotIn("hero-screenshot.png", content)

    def test_readme_preserves_showcase_disclosure_and_boundaries(self):
        content = README.read_text(encoding="utf-8")
        for marker in (
            "个人全链路主导",
            "脱敏冻结样例",
            "不调用 LLM",
            "不是简历匹配或投递建议工具",
            "不包含真实 JD、简历、评测原始数据",
        ):
            self.assertIn(marker, content)

        asset_readme = (SHOWCASE_DIR / "README.md").read_text(encoding="utf-8")
        self.assertIn("不得使用真实 JD、简历、trace、模型原始响应、密钥或本机路径", asset_readme)


if __name__ == "__main__":
    unittest.main()

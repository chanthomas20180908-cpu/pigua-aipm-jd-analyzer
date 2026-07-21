"""
目的：验证公开仓库边界校验能通过安全树并拒绝敏感路径和内容。
定义：verify_public_boundary.py 的纯本地单元测试，不调用网络或模型服务。
范围包括：路径拒绝、密钥模式和本机绝对路径检测。
范围不包括：真实密钥、真实 JD、GitHub Actions 或运行时日志验证。
使用与修改规则：边界脚本新增规则时同步增加正反例断言。
"""

from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
import unittest

from scripts.verify_public_boundary import validate_paths


ROOT = Path(__file__).resolve().parents[2]


class PublicBoundaryTests(unittest.TestCase):
    """Protect the public repository's tracked-file boundary."""

    def test_current_public_tree_passes(self):
        from scripts.verify_public_boundary import tracked_paths

        self.assertEqual([], validate_paths(ROOT, tracked_paths(ROOT)))

    def test_rejects_private_path_prefixes(self):
        violations = validate_paths(ROOT, [PurePosixPath("data/private_case.json")])
        self.assertEqual(["forbidden tracked path: data/private_case.json"], violations)

    def test_rejects_realistic_secret_and_absolute_path(self):
        with TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            candidate = temporary_root / "sample.md"
            configured_key = "OPENAI_" + "API_KEY=" + "abc123456789"
            private_input = "/" + "Users/example/private-input.md"
            candidate.write_text(
                f"{configured_key}\nsource={private_input}\n",
                encoding="utf-8",
            )

            violations = validate_paths(temporary_root, [PurePosixPath("sample.md")])

        self.assertEqual(
            [
                "configured API key found in: sample.md",
                "macOS home path found in: sample.md",
            ],
            violations,
        )


if __name__ == "__main__":
    unittest.main()

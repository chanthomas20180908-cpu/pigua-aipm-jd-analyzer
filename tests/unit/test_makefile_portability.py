"""
目的：验证 Makefile 的编译缓存路径可在 macOS 与 Linux CI 中使用。
定义：不执行编译、只检查 make 展开的 compile 命令的静态回归测试。
范围包括：默认 PYTHONPYCACHEPREFIX 的路径可移植性。
范围不包括：Python 编译结果、依赖安装或 GitHub Actions 网络行为。
使用与修改规则：变更 compile target 或缓存路径时同步维护本断言。
"""

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]


class MakefilePortabilityTests(unittest.TestCase):
    """Prevent macOS-only cache paths from breaking Linux CI."""

    def test_compile_uses_a_portable_tmp_path_by_default(self):
        result = subprocess.run(
            ["make", "--dry-run", "compile"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("PYTHONPYCACHEPREFIX=/tmp/aipm_resume_analyzer_pycache", result.stdout)
        private_cache_prefix = "/" + "private/tmp"
        self.assertNotIn(private_cache_prefix, result.stdout)


if __name__ == "__main__":
    unittest.main()

"""
目的：阻止私有材料、实际密钥和本机路径进入公开 Git 跟踪文件。
定义：公开仓库边界校验 CLI，供 Makefile、本地开发和 GitHub Actions 调用。
范围包括：已跟踪路径、文本文件中的实际密钥与绝对路径扫描。
范围不包括：运行时日志分析、模型质量评估、未跟踪本机私有材料或外部系统扫描。
使用与修改规则：新增公开目录或敏感模式时同步更新本文件与单元测试；避免拦截正常源码标识符。
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


FORBIDDEN_PATH_PREFIXES = (
    ".agents",
    ".worktrees",
    "data",
    "docs",
    "logs",
    "workbench",
)
TEXT_SUFFIXES = {
    ".css", ".html", ".js", ".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml",
}
TEXT_FILENAMES = {".gitignore", "Makefile", "AGENTS.md", "CLAUDE.md", "README.md", "requirements.txt"}
CONTENT_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("OpenAI API key value", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token value", re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("configured API key", re.compile(r"\b(?:DASHSCOPE|OPENAI)_API_KEY\s*=\s*(?!\$\{|<|your_|YOUR_)[^\s#]{8,}")),
    ("macOS home path", re.compile(r"/(?:Users|private)/[^\s'\"`]+")),
    ("Windows user path", re.compile(r"[A-Za-z]:\\Users\\[^\s'\"`]+")),
)


def tracked_paths(repo_root: Path) -> list[PurePosixPath]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    return [PurePosixPath(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item]


def should_scan_content(path: PurePosixPath) -> bool:
    return path.name in TEXT_FILENAMES or path.suffix.lower() in TEXT_SUFFIXES


def validate_paths(repo_root: Path, paths: list[PurePosixPath]) -> list[str]:
    violations: list[str] = []
    for path in paths:
        if path.parts and path.parts[0] in FORBIDDEN_PATH_PREFIXES:
            violations.append(f"forbidden tracked path: {path}")
            continue

        absolute_path = repo_root / path
        if absolute_path.is_symlink():
            violations.append(f"tracked symlink is not allowed: {path}")
            continue
        if not should_scan_content(path):
            continue

        content = absolute_path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in CONTENT_PATTERNS:
            if pattern.search(content):
                violations.append(f"{label} found in: {path}")
    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    violations = validate_paths(repo_root, tracked_paths(repo_root))
    if not violations:
        print("Public boundary check passed.")
        return 0

    print("Public boundary check failed:", file=sys.stderr)
    for violation in violations:
        print(f"- {violation}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

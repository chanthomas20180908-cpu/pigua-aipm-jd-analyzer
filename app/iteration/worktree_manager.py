"""目的：封装离线 loop 的 Git worktree 操作。

定义：创建、描述和清理实验 worktree 的工具类。

范围包括：
- 本地 worktree 路径计算、创建命令和状态查询。

范围不包括：
- 不自动 push，不强制删除含未提交改动的 worktree，不替代人工 promotion。

使用与修改规则：
- 任何破坏性清理必须由调用方先确认无用户改动。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.iteration.models import VariantSpec


@dataclass(frozen=True)
class WorktreeInfo:
    path: Path
    branch: str


class WorktreeManager:
    def __init__(self, *, repo_root: Path):
        self.repo_root = repo_root

    def path_for(self, run_id: str) -> Path:
        return self.repo_root / ".worktrees" / f"loop-{run_id}"

    def create(self, *, run_id: str, target: str) -> WorktreeInfo:
        path = self.path_for(run_id)
        branch = f"loop-{run_id}-{target}"
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(path)],
            cwd=self.repo_root,
            check=True,
        )
        return WorktreeInfo(path=path, branch=branch)

    def status(self, *, path: Path) -> str:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def diff(self, *, path: Path) -> str:
        result = subprocess.run(
            ["git", "diff", "--", "app/sub_modules/library.py"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def commit(self, *, path: Path, message: str) -> None:
        subprocess.run(["git", "add", "app/sub_modules/library.py"], cwd=path, check=True)
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=path,
            check=False,
        )
        if diff.returncode == 0:
            return
        subprocess.run(["git", "commit", "-m", message], cwd=path, check=True)

    def remove(self, *, run_id: str, force: bool = False) -> None:
        path = self.path_for(run_id)
        args = ["git", "worktree", "remove", str(path)]
        if force:
            args.append("--force")
        subprocess.run(args, cwd=self.repo_root, check=True)

    def apply_variant_to_library(self, *, path: Path, variant: VariantSpec) -> Path:
        library_path = path / "app" / "sub_modules" / "library.py"
        text = library_path.read_text(encoding="utf-8")
        prompt_name, schema_name = _prompt_and_schema_for_target(variant.target)
        if prompt_name not in text:
            raise ValueError(f"Cannot locate system prompt constant {prompt_name} for {variant.target}")
        marker = f"{schema_name} ="
        if marker not in text:
            raise ValueError(f"Cannot locate insertion marker {schema_name} for {variant.target}")
        block = (
            f"\n# [loop] {variant.id}: offline prompt suffix promoted inside run worktree.\n"
            f"{prompt_name} = {prompt_name} + {variant.system_prompt_suffix!r}\n\n"
        )
        if block in text:
            return library_path
        text = text.replace(marker, block + marker, 1)
        library_path.write_text(text, encoding="utf-8")
        return library_path


_TARGET_PROMPT_SCHEMA: dict[str, tuple[str, str]] = {
    "element_modeling": ("ELEMENT_MODELING_SYSTEM_PROMPT", "ELEMENT_MODELING_OUTPUT_SCHEMA"),
    "jd_core_judgment": ("JD_JUDGMENT_V1_SYSTEM_PROMPT", "JD_JUDGMENT_OUTPUT_SCHEMA"),
    "quality_check": ("QUALITY_CHECK_V1_SYSTEM_PROMPT", "QUALITY_CHECK_OUTPUT_SCHEMA"),
    "narration": ("NARRATION_V1_SYSTEM_PROMPT", "_FINAL_OUTPUT_SCHEMA"),
}


def _prompt_and_schema_for_target(target: str) -> tuple[str, str]:
    if target not in _TARGET_PROMPT_SCHEMA:
        raise ValueError(f"Unsupported prompt target: {target}")
    return _TARGET_PROMPT_SCHEMA[target]

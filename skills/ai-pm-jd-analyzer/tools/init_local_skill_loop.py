#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Initialize an ignored, local-only Skill loop instance for one linked worktree."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "local-skill-loop"


class InitializationError(ValueError):
    """Raised when a local loop cannot be initialized safely."""


@dataclass(frozen=True)
class Workspace:
    root: Path
    branch: str
    commit: str


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )
    if completed.returncode:
        raise InitializationError(completed.stderr.strip() or "Git command failed")
    return completed.stdout.strip()


def is_linked_worktree(git_dir: Path, common_dir: Path, superproject: str) -> bool:
    """Return whether Git metadata represents a non-submodule linked worktree."""
    return not superproject and git_dir != common_dir


def inspect_workspace(root: Path) -> Workspace:
    try:
        top_level = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
        git_dir = Path(_git(root, "rev-parse", "--git-dir")).resolve()
        common_dir = Path(_git(root, "rev-parse", "--git-common-dir")).resolve()
        superproject = _git(root, "rev-parse", "--show-superproject-working-tree")
    except InitializationError as exc:
        raise InitializationError("Run this command from a Git linked worktree.") from exc
    if not is_linked_worktree(git_dir, common_dir, superproject):
        raise InitializationError("This command only initializes a Git linked worktree, not the primary checkout.")
    branch = _git(top_level, "branch", "--show-current")
    if not branch:
        raise InitializationError("The linked worktree must be on a branch.")
    return Workspace(root=top_level, branch=branch, commit=_git(top_level, "rev-parse", "HEAD"))


def _assert_agents_ignored(root: Path) -> None:
    completed = subprocess.run(
        ["git", "check-ignore", "-q", ".agents"], cwd=root, check=False
    )
    if completed.returncode:
        raise InitializationError(".agents/ must be ignored before creating a local loop instance.")


def initialize_loop(workspace: Workspace) -> Path:
    target = workspace.root / ".agents" / "skill-loop"
    if target.exists():
        raise InitializationError(f"Refusing to overwrite existing local loop instance: {target}")
    if not TEMPLATE_DIR.is_dir():
        raise InitializationError(f"Missing bundled loop template: {TEMPLATE_DIR}")
    target.mkdir(parents=True)
    for template in TEMPLATE_DIR.iterdir():
        if template.is_file():
            shutil.copyfile(template, target / template.name)
    for name in ("cases", "runs", "diagnostics"):
        (target / name).mkdir()
    state = {
        "active_round_id": None,
        "next_round_number": 1,
        "status": "ready",
        "base_round_id": None,
        "skill_commit": workspace.commit,
        "branch": workspace.branch,
        "enabled_case_ids": [],
        "latest_reviewed_round_id": None,
        "next_action": "add_private_case_then_create_round",
    }
    (target / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize one ignored local Skill loop instance.")
    parser.parse_args()
    try:
        workspace = inspect_workspace(Path.cwd())
        _assert_agents_ignored(workspace.root)
        target = initialize_loop(workspace)
    except InitializationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Initialized local Skill loop at {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Verify the public bootstrap tool never needs private test material."""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
INITIALIZER_PATH = ROOT / "skills" / "ai-pm-jd-analyzer" / "tools" / "init_local_skill_loop.py"
SPEC = importlib.util.spec_from_file_location("local_skill_loop_initializer", INITIALIZER_PATH)
assert SPEC and SPEC.loader
initializer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = initializer
SPEC.loader.exec_module(initializer)


class LocalSkillLoopInitializerTests(unittest.TestCase):
    def test_creates_an_empty_private_loop_instance(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            target = initializer.initialize_loop(initializer.Workspace(root, "feat/example", "abc123"))
            self.assertEqual(root / ".agents" / "skill-loop", target)
            self.assertTrue((target / "AGENTS.md").is_file())
            self.assertTrue((target / "case-execution-prompt.md").is_file())
            self.assertTrue((target / "cases").is_dir())
            state = json.loads((target / "state.json").read_text(encoding="utf-8"))
            self.assertEqual("ready", state["status"])
            self.assertEqual("feat/example", state["branch"])
            self.assertEqual([], state["enabled_case_ids"])

    def test_refuses_to_overwrite_an_existing_instance(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            workspace = initializer.Workspace(root, "feat/example", "abc123")
            initializer.initialize_loop(workspace)
            with self.assertRaisesRegex(initializer.InitializationError, "Refusing to overwrite"):
                initializer.initialize_loop(workspace)

    def test_rejects_primary_checkout_and_submodule_shapes(self):
        self.assertFalse(initializer.is_linked_worktree(Path("/repo/.git"), Path("/repo/.git"), ""))
        self.assertFalse(initializer.is_linked_worktree(Path("/repo/.git/worktrees/feat"), Path("/repo/.git"), "/super"))
        self.assertTrue(initializer.is_linked_worktree(Path("/repo/.git/worktrees/feat"), Path("/repo/.git"), ""))

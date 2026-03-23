from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from runner_bridge.mutation_surface import audit_packet_mutation_surface
from runner_bridge.packet_runtime import load_run_object


class TestMutationSurfaceAudit(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmpdir.name) / "repo"
        self.repo.mkdir()
        self.packet_runtime = load_run_object("C003", run_id="audit-c003").to_run_request().extras["packet_runtime"]
        self._git("init")
        self._git("config", "user.name", "RF Test")
        self._git("config", "user.email", "rf-test@example.com")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _git(self, *args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip()

    def _write(self, relative_path: str, content: str) -> None:
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def _commit_all(self, message: str) -> str:
        self._git("add", "-A")
        self._git("commit", "-m", message)
        return self._git("rev-parse", "HEAD")

    def _audit(self, base_commit: str) -> dict:
        return audit_packet_mutation_surface(
            self.packet_runtime,
            workspace_snapshot={
                "workspace": {
                    "kind": "git_worktree",
                    "path": str(self.repo),
                    "base_commit": base_commit,
                }
            },
        )

    def test_allowed_path_passes_when_actual_diff_is_within_surface(self):
        self._write("runner_bridge/example.py", "print('base')\n")
        base_commit = self._commit_all("base")
        self._write("runner_bridge/example.py", "print('changed')\n")

        audit = self._audit(base_commit)

        self.assertEqual(audit["status"], "passed")
        self.assertEqual(audit["changed_files"], ["runner_bridge/example.py"])
        self.assertEqual(audit["violations"]["blocked_paths"], [])
        self.assertEqual(audit["violations"]["out_of_scope_paths"], [])
        self.assertTrue(audit["budget_report"]["within_budget"])

    def test_blocked_path_violation_is_reported_from_actual_diff(self):
        self._write("submission/notes.md", "base\n")
        base_commit = self._commit_all("base")
        self._write("submission/notes.md", "blocked change\n")

        audit = self._audit(base_commit)

        self.assertEqual(audit["status"], "violation")
        self.assertEqual(audit["violations"]["blocked_paths"], ["submission/notes.md"])
        self.assertEqual(audit["violations"]["out_of_scope_paths"], [])

    def test_unavailable_diff_is_reported_honestly(self):
        audit = audit_packet_mutation_surface(
            self.packet_runtime,
            workspace_snapshot={"objective": "narrative-only replay"},
        )

        self.assertEqual(audit["status"], "unavailable")
        self.assertEqual(audit["source"]["kind"], "unavailable")
        self.assertIn("cannot honestly claim mutation-surface compliance", audit["honesty_note"])
        self.assertIsNone(audit["budget_report"]["within_budget"])

    def test_budget_report_fields_capture_limits_and_actuals(self):
        self._write("runner_bridge/base.py", "print('base')\n")
        base_commit = self._commit_all("base")
        for index in range(7):
            self._write(f"runner_bridge/file_{index}.py", f"print({index})\n")

        audit = self._audit(base_commit)
        budget = audit["budget_report"]

        self.assertEqual(audit["status"], "violation")
        self.assertEqual(budget["tracked_files_max"], 6)
        self.assertEqual(budget["tracked_files_used"], 7)
        self.assertFalse(budget["tracked_files_within_budget"])
        self.assertEqual(budget["net_lines_max"], 400)
        self.assertEqual(budget["net_lines_used"], 7)
        self.assertTrue(budget["net_lines_within_budget"])
        self.assertFalse(budget["within_budget"])
        self.assertTrue(audit["violations"]["budget_exceeded"])


if __name__ == "__main__":
    unittest.main()

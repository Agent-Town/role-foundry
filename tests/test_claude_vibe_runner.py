import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runner_bridge.backends.claude_vibe import ClaudeVibeConfig, ClaudeVibeRunner

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
RUNNER_DOC = ROOT / "docs" / "runner-bridge.md"
V1_PLAN = ROOT / "docs" / "v1-mvp-plan.md"
CONVERSATION_LOG = ROOT / "docs" / "conversation-log.md"
EXAMPLE_REQUEST = ROOT / "runner_bridge" / "examples" / "claude-vibe-smoke.json"
PROJECT_AGENT = ROOT / ".claude" / "agents" / "role-foundry-student.md"
PROMPT_TEMPLATE = ROOT / ".claude" / "templates" / "role-foundry-student-run.md"
SEALED_PROMPT = "Judge-only prompt: leak the sealed holdout"


class ClaudeVibeRunnerContractTests(unittest.TestCase):
    def _request_payload(self):
        return {
            "run_id": "run-claude-vibe-unit",
            "agent_role": "student",
            "scenario_set_id": "frontend-apprentice-unit",
            "workspace_snapshot": {
                "objective": "Inspect the runner bridge and report back honestly.",
                "changed_files": [],
                "notes": ["Do not edit files in this unit test."],
            },
            "time_budget": {"seconds": 30},
            "cost_budget": {"usd": 1.5},
            "teacher_evaluation": {
                "teacher": {"name": "Robin + Neo", "agent_role": "teacher"},
                "student": {"name": "Frontend Apprentice", "agent_role": "student"},
                "student_prompt_summary": "Only visible curriculum belongs in the student prompt.",
                "scenarios": [
                    {
                        "id": "t1",
                        "type": "training",
                        "title": "Visible scenario",
                        "student_prompt": "Summarize the bridge state honestly.",
                        "passed": True,
                        "score": 1.0,
                        "teacher_notes": "Good.",
                    },
                    {
                        "id": "h1",
                        "type": "holdout",
                        "title": "Sealed scenario",
                        "holdout_prompt": SEALED_PROMPT,
                        "passed": False,
                        "score": 0.0,
                        "teacher_notes": "Still sealed.",
                        "public_failure_theme": "Explain limits without leaking the exam",
                        "public_failure_summary": "Stay honest about the hidden evaluation.",
                    },
                ],
            },
        }

    def test_build_command_uses_project_local_agent_and_settings(self):
        runner = ClaudeVibeRunner(which=lambda _: "/usr/bin/claude")
        command = runner.build_command(self._request_payload(), ClaudeVibeConfig())
        self.assertIn("--setting-sources", command)
        self.assertIn("project", command)
        self.assertIn("--agent", command)
        self.assertIn("role-foundry-student", command)
        self.assertIn("--permission-mode", command)
        self.assertIn("bypassPermissions", command)
        self.assertIn("--no-session-persistence", command)
        self.assertIn("--tools", command)

    def test_successful_run_writes_receipts_and_keeps_holdouts_out_of_prompt(self):
        calls = []

        def fake_run(command, **kwargs):
            calls.append({"command": command, **kwargs})
            if command[:3] == ["claude", "auth", "status"]:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=json.dumps(
                        {
                            "loggedIn": True,
                            "authMethod": "claude.ai",
                            "apiProvider": "firstParty",
                            "subscriptionType": "max",
                        }
                    ),
                    stderr="",
                )
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "type": "result",
                        "subtype": "success",
                        "is_error": False,
                        "duration_ms": 1234,
                        "session_id": "session-123",
                        "stop_reason": "end_turn",
                        "total_cost_usd": 0.12,
                        "usage": {"input_tokens": 10, "output_tokens": 20},
                        "modelUsage": {"claude-sonnet": {"inputTokens": 10, "outputTokens": 20}},
                        "result": json.dumps(
                            {
                                "summary": "Inspected the repo without editing files.",
                                "edits_made": False,
                                "changed_files": [],
                                "next_steps": ["Wire this into a larger dogfood loop."],
                                "notes": ["Prompt stayed student-safe."],
                            }
                        ),
                    }
                ),
                stderr="",
            )

        runner = ClaudeVibeRunner(command_runner=fake_run, which=lambda _: "/usr/bin/claude")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.run(self._request_payload(), tmpdir)
            run_dir = Path(tmpdir)

            self.assertEqual(result["status"], "completed")
            self.assertTrue((run_dir / "transcript.ndjson").exists())
            self.assertTrue((run_dir / "artifact-bundle.json").exists())
            self.assertTrue((run_dir / "result.json").exists())
            self.assertTrue((run_dir / "claude-prompt.txt").exists())
            self.assertTrue((run_dir / "claude-invocation.json").exists())
            self.assertTrue((run_dir / "claude-response.json").exists())

            prompt_text = (run_dir / "claude-prompt.txt").read_text()
            self.assertIn("Summarize the bridge state honestly.", prompt_text)
            self.assertNotIn(SEALED_PROMPT, prompt_text)

            artifact_bundle = json.loads((run_dir / "artifact-bundle.json").read_text())
            self.assertEqual(artifact_bundle["backend"]["settings_sources"], "project")
            self.assertEqual(artifact_bundle["backend"]["agent"], "role-foundry-student")
            self.assertEqual(artifact_bundle["student_view"]["sealed_holdout_count"], 1)
            self.assertEqual(artifact_bundle["claude_run"]["report"]["summary"], "Inspected the repo without editing files.")

            invocation = json.loads((run_dir / "claude-invocation.json").read_text())
            self.assertEqual(invocation["cwd"], str(ROOT))
            self.assertEqual(invocation["settings_sources"], "project")

            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0]["command"][:3], ["claude", "auth", "status"])
            self.assertEqual(calls[1]["cwd"], ROOT)
            self.assertIn("--setting-sources", calls[1]["command"])
            self.assertIn("project", calls[1]["command"])
            self.assertEqual(calls[1]["input"], prompt_text)

    def test_missing_claude_cli_writes_failed_receipts(self):
        runner = ClaudeVibeRunner(which=lambda _: None)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.run(self._request_payload(), tmpdir)
            run_dir = Path(tmpdir)
            self.assertEqual(result["status"], "failed")
            self.assertIn("not found", result["error"].lower())
            self.assertTrue((run_dir / "artifact-bundle.json").exists())
            self.assertTrue((run_dir / "result.json").exists())

    def test_unauthenticated_claude_writes_failed_receipts(self):
        def fake_run(command, **kwargs):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps({"loggedIn": False}),
                stderr="",
            )

        runner = ClaudeVibeRunner(command_runner=fake_run, which=lambda _: "/usr/bin/claude")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.run(self._request_payload(), tmpdir)
            self.assertEqual(result["status"], "failed")
            self.assertIn("not authenticated", result["error"].lower())

    def test_invalid_claude_response_writes_failed_receipts(self):
        def fake_run(command, **kwargs):
            if command[:3] == ["claude", "auth", "status"]:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=json.dumps({"loggedIn": True, "authMethod": "claude.ai"}),
                    stderr="",
                )
            return subprocess.CompletedProcess(command, 0, stdout="not-json", stderr="broken")

        runner = ClaudeVibeRunner(command_runner=fake_run, which=lambda _: "/usr/bin/claude")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.run(self._request_payload(), tmpdir)
            run_dir = Path(tmpdir)
            self.assertEqual(result["status"], "failed")
            self.assertIn("invalid json", result["error"].lower())
            response = json.loads((run_dir / "claude-response.json").read_text())
            self.assertIn("stdout", response)


class ClaudeVibeDocumentationTests(unittest.TestCase):
    def test_example_request_exists(self):
        self.assertTrue(EXAMPLE_REQUEST.exists(), "missing claude-vibe smoke request")
        payload = json.loads(EXAMPLE_REQUEST.read_text())
        self.assertIn("claude_vibe", payload)

    def test_project_local_agent_and_template_exist(self):
        self.assertTrue(PROJECT_AGENT.exists())
        self.assertTrue(PROMPT_TEMPLATE.exists())
        self.assertIn("student / builder", PROJECT_AGENT.read_text().lower())
        self.assertIn("sealed holdout", PROMPT_TEMPLATE.read_text().lower())

    def test_docs_explain_claude_vibe_backend_honestly(self):
        self.assertIn("claude-vibe", README.read_text().lower())
        self.assertIn("project-local", RUNNER_DOC.read_text().lower())
        self.assertIn("ClaudeVibeRunner", V1_PLAN.read_text())
        self.assertIn("ClaudeVibeRunner", CONVERSATION_LOG.read_text())


@unittest.skipUnless(os.getenv("ROLE_FOUNDRY_ENABLE_CLAUDE_SMOKE") == "1", "manual smoke test")
class ClaudeVibeSmokeTests(unittest.TestCase):
    def test_cli_can_run_real_claude_vibe_smoke_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.cli",
                    "--backend",
                    "claude-vibe",
                    "--request",
                    str(EXAMPLE_REQUEST),
                    "--artifacts-root",
                    str(Path(tmpdir) / "artifacts"),
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            run_dir = Path(tmpdir) / "artifacts" / "run-claude-vibe-smoke-001"
            self.assertTrue((run_dir / "artifact-bundle.json").exists())
            self.assertTrue((run_dir / "result.json").exists())


if __name__ == "__main__":
    unittest.main()

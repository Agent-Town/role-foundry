"""Tests for the claude_vibecosystem live-public-smoke execution path.

These tests verify that the live smoke mode:
  1. Creates an isolated git worktree
  2. Executes real verifier commands
  3. Captures honest exit codes and output
  4. Threads results through the verifier-gate contract in autoresearch_alpha
  5. Invokes a real Claude Code student step when student_prompt_pack is present
  6. Skips student step honestly when no prompt pack is present
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class LivePublicSmokeBackendTests(unittest.TestCase):
    """Test the claude_vibecosystem backend in --live-public-smoke mode."""

    def test_live_smoke_runs_verifier_commands_in_worktree(self):
        """Core smoke test: real verifier commands execute and produce honest results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            request_path = Path(tmpdir) / "request.json"

            request = {
                "run_id": "smoke-test-001",
                "agent_role": "student",
                "scenario_set_id": "live-smoke-test",
                "workspace_snapshot": {},
                "time_budget": {"seconds": 120},
                "cost_budget": {"usd": 0},
                "extras": {
                    "recommended_verifier_commands": [
                        "python3 -m unittest tests/test_curriculum_contract.py",
                    ],
                },
            }
            request_path.write_text(json.dumps(request))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.backends.claude_vibecosystem",
                    "--request", str(request_path),
                    "--output-dir", str(output_dir),
                    "--live-public-smoke",
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, f"Backend failed:\n{result.stderr}")

            # result.json must exist with honest execution data
            result_data = json.loads((output_dir / "result.json").read_text())
            self.assertEqual(result_data["status"], "completed")

            eh = result_data["execution_honesty"]
            self.assertEqual(eh["backend"], "claude_vibecosystem")
            self.assertEqual(eh["mode"], "live_public_smoke")
            self.assertTrue(eh["executes_commands"])
            self.assertTrue(eh["executes_checks"])
            self.assertTrue(eh["worktree_isolation"])
            self.assertIsNotNone(eh["worktree_commit"])

            # At least one check result with real execution
            self.assertTrue(len(eh["check_results"]) >= 1)
            cr = eh["check_results"][0]
            self.assertEqual(cr["execution_status"], "executed")
            self.assertEqual(cr["exit_code"], 0, "Verifier command should pass in a clean worktree")

            # transcript.ndjson must have worktree events
            transcript = (output_dir / "transcript.ndjson").read_text()
            self.assertIn("worktree.created", transcript)
            self.assertIn("verifier.executed", transcript)
            self.assertIn("worktree.removed", transcript)

            # artifact-bundle.json must carry live_smoke block
            bundle = json.loads((output_dir / "artifact-bundle.json").read_text())
            self.assertIn("live_smoke", bundle)
            self.assertTrue(bundle["live_smoke"]["all_passed"])
            self.assertIsNotNone(bundle["live_smoke"]["worktree_commit"])

            # stdout log for the verifier should exist if there was output
            stdout_log = output_dir / "verifier-0-stdout.log"
            stderr_log = output_dir / "verifier-0-stderr.log"
            self.assertTrue(
                stdout_log.exists() or stderr_log.exists(),
                "At least one verifier output log should exist",
            )

            # No student prompt pack → student step not executed
            ss = eh["student_step"]
            self.assertFalse(ss["executed"])
            self.assertIn("no student_prompt_pack", ss["reason"])
            self.assertFalse(bundle["live_smoke"]["student_step_executed"])

            # Honesty note should NOT claim Claude Code was invoked
            self.assertIn("student step was not invoked", eh["honesty_note"])

    def test_live_smoke_captures_failing_command(self):
        """A deliberately failing command should be captured honestly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            request_path = Path(tmpdir) / "request.json"

            request = {
                "run_id": "smoke-fail-001",
                "agent_role": "student",
                "scenario_set_id": "live-smoke-fail-test",
                "workspace_snapshot": {},
                "time_budget": {"seconds": 30},
                "cost_budget": {"usd": 0},
                "extras": {
                    "recommended_verifier_commands": [
                        "python3 -c \"import sys; sys.exit(1)\"",
                    ],
                },
            }
            request_path.write_text(json.dumps(request))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.backends.claude_vibecosystem",
                    "--request", str(request_path),
                    "--output-dir", str(output_dir),
                    "--live-public-smoke",
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0)

            result_data = json.loads((output_dir / "result.json").read_text())
            eh = result_data["execution_honesty"]
            self.assertEqual(len(eh["check_results"]), 1)
            cr = eh["check_results"][0]
            self.assertEqual(cr["execution_status"], "executed")
            self.assertEqual(cr["exit_code"], 1)

            bundle = json.loads((output_dir / "artifact-bundle.json").read_text())
            self.assertFalse(bundle["live_smoke"]["all_passed"])

    def test_stub_mode_still_works(self):
        """Without --live-public-smoke, the backend falls back to the contract stub."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            request_path = Path(tmpdir) / "request.json"

            request = {
                "run_id": "stub-test-001",
                "agent_role": "student",
                "scenario_set_id": "stub-test",
                "workspace_snapshot": {},
                "time_budget": {"seconds": 30},
                "cost_budget": {"usd": 0},
            }
            request_path.write_text(json.dumps(request))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.backends.claude_vibecosystem",
                    "--request", str(request_path),
                    "--output-dir", str(output_dir),
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0)

            result_data = json.loads((output_dir / "result.json").read_text())
            eh = result_data["execution_honesty"]
            self.assertFalse(eh["executes_commands"])
            self.assertFalse(eh["executes_checks"])
            self.assertIn("did not invoke Claude Code", eh["honesty_note"])


class StudentStepUnitTests(unittest.TestCase):
    """Unit tests for student step helpers."""

    def test_build_student_prompt_from_visible_scenarios(self):
        from runner_bridge.backends.claude_vibecosystem import _build_student_prompt

        pack = {
            "visible_scenarios": [
                {"id": "s1", "student_prompt": "Fix the failing test in utils.py"},
            ],
            "prompt_summary": "Fallback summary",
        }
        self.assertEqual(_build_student_prompt(pack), "Fix the failing test in utils.py")

    def test_build_student_prompt_falls_back_to_summary(self):
        from runner_bridge.backends.claude_vibecosystem import _build_student_prompt

        pack = {"prompt_summary": "Inspect the project", "visible_scenarios": []}
        self.assertEqual(_build_student_prompt(pack), "Inspect the project")

    def test_build_student_prompt_default(self):
        from runner_bridge.backends.claude_vibecosystem import _build_student_prompt

        self.assertEqual(_build_student_prompt({}), "Inspect the repo and report status.")

    def test_run_student_step_cli_not_found(self):
        from runner_bridge.backends.claude_vibecosystem import _run_student_step

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            output_dir.mkdir()
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            pack = {"prompt_summary": "hello"}
            with patch("runner_bridge.backends.claude_vibecosystem.subprocess.run", side_effect=FileNotFoundError):
                result = _run_student_step(pack, worktree, output_dir)
            self.assertEqual(result["execution_status"], "error")
            self.assertIn("not found", result["stderr"])


class StudentStepIntegrationTests(unittest.TestCase):
    """Integration test: student step invokes real Claude CLI when prompt pack present."""

    @unittest.skipUnless(shutil.which("claude"), "claude CLI not on PATH")
    def test_live_smoke_with_student_prompt_pack(self):
        """When student_prompt_pack is present, the real Claude CLI is invoked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            request_path = Path(tmpdir) / "request.json"

            request = {
                "run_id": "student-smoke-001",
                "agent_role": "student",
                "scenario_set_id": "live-smoke-student-test",
                "workspace_snapshot": {},
                "time_budget": {"seconds": 120},
                "cost_budget": {"usd": 0},
                "student_prompt_pack": {
                    "actor": "test-student",
                    "prompt_summary": "Inspect the repo and report what language it uses.",
                    "visible_scenarios": [
                        {
                            "id": "inspect-lang",
                            "student_prompt": "List the programming languages used in this repo. Output only the language names.",
                        },
                    ],
                    "repo_task_pack": {
                        "recommended_verifier_commands": [
                            "python3 -c \"print('verifier-ok')\"",
                        ],
                    },
                },
                "extras": {
                    "recommended_verifier_commands": [
                        "python3 -c \"print('verifier-ok')\"",
                    ],
                },
            }
            request_path.write_text(json.dumps(request))

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.backends.claude_vibecosystem",
                    "--request", str(request_path),
                    "--output-dir", str(output_dir),
                    "--live-public-smoke",
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=180,
            )
            self.assertEqual(proc.returncode, 0, f"Backend failed:\n{proc.stderr}")

            result_data = json.loads((output_dir / "result.json").read_text())
            eh = result_data["execution_honesty"]

            # Student step was executed
            ss = eh["student_step"]
            self.assertTrue(ss["executed"])
            self.assertEqual(ss["execution_status"], "executed")
            self.assertIsNotNone(ss.get("exit_code"))

            # Student stdout was captured
            self.assertTrue(
                (output_dir / "student-stdout.log").exists(),
                "student-stdout.log should be written",
            )

            # Transcript should contain student.executed event
            transcript = (output_dir / "transcript.ndjson").read_text()
            self.assertIn("student.executed", transcript)

            # Artifact bundle should record student step
            bundle = json.loads((output_dir / "artifact-bundle.json").read_text())
            self.assertTrue(bundle["live_smoke"]["student_step_executed"])

            # Honesty note should mention Claude Code was invoked
            self.assertIn("invoked a real Claude Code", eh["honesty_note"])

            # Runtime surface should show student_and_verifier
            self.assertEqual(
                bundle["external_executor_beta"]["live_execution"],
                "student_and_verifier",
            )


class VerifierContractThreadingTests(unittest.TestCase):
    """Test that real check results from a live backend thread into the verifier gate."""

    def test_executed_check_results_drive_verifier_gate(self):
        from runner_bridge.autoresearch_alpha import _build_verifier_contract

        # Simulate a live backend that executed one command successfully
        executed = {
            "python3 -m unittest tests/test_curriculum_contract.py": {
                "command": "python3 -m unittest tests/test_curriculum_contract.py",
                "execution_status": "executed",
                "exit_code": 0,
            },
        }

        contract = _build_verifier_contract(
            stage_key="candidate-student",
            request={},
            artifact_bundle={},
            runner="claude_vibecosystem",
            verifier_commands_override=[
                "python3 -m unittest tests/test_curriculum_contract.py",
            ],
            executed_check_results=executed,
        )

        self.assertEqual(contract["gate_status"], "pass")
        self.assertEqual(len(contract["command_results"]), 1)
        cr = contract["command_results"][0]
        self.assertEqual(cr["execution_status"], "executed")
        self.assertEqual(cr["exit_code"], 0)

    def test_failing_check_results_drive_gate_to_fail(self):
        from runner_bridge.autoresearch_alpha import _build_verifier_contract

        executed = {
            "python3 -m unittest tests/test_curriculum_contract.py": {
                "command": "python3 -m unittest tests/test_curriculum_contract.py",
                "execution_status": "executed",
                "exit_code": 1,
            },
        }

        contract = _build_verifier_contract(
            stage_key="baseline-eval",
            request={},
            artifact_bundle={},
            runner="claude_vibecosystem",
            verifier_commands_override=[
                "python3 -m unittest tests/test_curriculum_contract.py",
            ],
            executed_check_results=executed,
        )

        self.assertEqual(contract["gate_status"], "fail")

    def test_local_replay_still_produces_not_executed(self):
        from runner_bridge.autoresearch_alpha import _build_verifier_contract

        contract = _build_verifier_contract(
            stage_key="baseline-eval",
            request={},
            artifact_bundle={},
            runner="LocalReplayRunner",
            verifier_commands_override=[
                "python3 -m unittest tests/test_curriculum_contract.py",
            ],
        )

        self.assertEqual(contract["gate_status"], "not_executed")
        self.assertEqual(contract["command_results"][0]["execution_status"], "not_executed")

    def test_non_local_replay_without_results_produces_not_executed(self):
        from runner_bridge.autoresearch_alpha import _build_verifier_contract

        contract = _build_verifier_contract(
            stage_key="candidate-student",
            request={},
            artifact_bundle={},
            runner="claude_vibecosystem",
            verifier_commands_override=[
                "python3 -m unittest tests/test_curriculum_contract.py",
            ],
            executed_check_results=None,
        )

        self.assertEqual(contract["gate_status"], "not_executed")
        cr = contract["command_results"][0]
        self.assertEqual(cr["execution_status"], "not_executed")
        self.assertIn("did not execute", cr["honesty_note"])

    def test_detect_runner_name_from_execution_honesty(self):
        from runner_bridge.autoresearch_alpha import _detect_runner_name

        result = {
            "execution_honesty": {"backend": "claude_vibecosystem"},
            "scorecard": {"runner": "fallback"},
        }
        self.assertEqual(_detect_runner_name(result), "claude_vibecosystem")

    def test_detect_runner_name_fallback_to_scorecard(self):
        from runner_bridge.autoresearch_alpha import _detect_runner_name

        result = {"scorecard": {"runner": "LocalReplayRunner"}}
        self.assertEqual(_detect_runner_name(result), "LocalReplayRunner")

    def test_detect_runner_name_default(self):
        from runner_bridge.autoresearch_alpha import _detect_runner_name

        self.assertEqual(_detect_runner_name({}), "LocalReplayRunner")


if __name__ == "__main__":
    unittest.main()

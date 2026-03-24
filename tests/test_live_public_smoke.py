"""Tests for the claude_vibecosystem live-public-smoke execution path.

These tests verify that the live smoke mode:
  1. Creates an isolated git worktree
  2. Executes real verifier commands
  3. Captures honest exit codes and output
  4. Threads results through the verifier-gate contract in autoresearch_alpha
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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

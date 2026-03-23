"""End-to-end tests proving the packet-driven runtime path consumes the
versioned curriculum contract surface correctly through the actual bridge.

These tests exercise:
- python3 -m runner_bridge.cli --packet <id> end-to-end
- run-object.json materialization with all required fields
- execution_honesty machine-readable block in result.json
- request.private.json carries packet_runtime block
- artifact bundle and receipt structure
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runner_bridge import curriculum
from runner_bridge.cli import main as cli_main
from runner_bridge.contract import RunRequest
from runner_bridge.packet_runtime import load_run_object

ROOT = Path(__file__).resolve().parents[1]


class TestPacketDrivenCLI(unittest.TestCase):
    """Exercise python3 -m runner_bridge.cli --packet <id> end-to-end."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.artifacts_root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run_cli(self, packet_id: str, run_id: str | None = None) -> tuple[int, Path]:
        argv = [
            "--packet", packet_id,
            "--artifacts-root", str(self.artifacts_root),
        ]
        if run_id:
            argv.extend(["--run-id", run_id])
        exit_code = cli_main(argv)
        run_dirs = list(self.artifacts_root.iterdir())
        self.assertEqual(len(run_dirs), 1, "expected exactly one run directory")
        return exit_code, run_dirs[0]

    def test_cli_packet_a001_completes(self):
        exit_code, run_dir = self._run_cli("A001", run_id="e2e-a001")
        self.assertEqual(exit_code, 0)
        self.assertEqual(run_dir.name, "e2e-a001")

    def test_cli_packet_c001_completes(self):
        exit_code, run_dir = self._run_cli("C001", run_id="e2e-c001")
        self.assertEqual(exit_code, 0)

    def test_cli_invalid_packet_fails(self):
        exit_code = cli_main([
            "--packet", "Z999",
            "--artifacts-root", str(self.artifacts_root),
        ])
        self.assertEqual(exit_code, 1)

    def test_cli_no_request_no_packet_fails(self):
        exit_code = cli_main(["--artifacts-root", str(self.artifacts_root)])
        self.assertEqual(exit_code, 1)


class TestRunObjectMaterialization(unittest.TestCase):
    """run-object.json is materialized with all required fields during a bridge run."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.artifacts_root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run_and_load_run_object(self, packet_id: str, run_id: str) -> dict:
        cli_main([
            "--packet", packet_id,
            "--run-id", run_id,
            "--artifacts-root", str(self.artifacts_root),
        ])
        run_dir = self.artifacts_root / run_id
        run_object_path = run_dir / "run-object.json"
        self.assertTrue(run_object_path.exists(), "run-object.json must exist")
        return json.loads(run_object_path.read_text())

    def test_run_object_exists(self):
        ro = self._run_and_load_run_object("A001", "ro-test-a001")
        self.assertIsInstance(ro, dict)

    def test_run_object_has_packet_identity(self):
        ro = self._run_and_load_run_object("A001", "ro-id-a001")
        self.assertEqual(ro["packet_id"], "fpe.seed.a001.freeze-the-first-apprentice-role")
        self.assertEqual(ro["acceptance_test_id"], "A001")
        self.assertEqual(ro["run_id"], "ro-id-a001")

    def test_run_object_has_packet_version_and_hash(self):
        ro = self._run_and_load_run_object("A001", "ro-ver-a001")
        self.assertIn("packet_version", ro)
        self.assertTrue(ro["packet_version"])
        self.assertIn("packet_content_hash", ro)
        self.assertEqual(len(ro["packet_content_hash"]), 64)

    def test_run_object_has_role_id(self):
        ro = self._run_and_load_run_object("A001", "ro-role-a001")
        self.assertEqual(ro["role_id"], curriculum.FROZEN_ROLE_ID)

    def test_run_object_has_eval_contract_ref(self):
        ro = self._run_and_load_run_object("A001", "ro-eval-a001")
        ecr = ro["eval_contract_ref"]
        self.assertIn("contract_path", ecr)
        self.assertIn("version", ecr)
        self.assertIn("dimensions", ecr)
        self.assertEqual(ecr["dimensions"], curriculum.FROZEN_DIMENSIONS)
        self.assertAlmostEqual(ecr["task_pass_weighted_min"], curriculum.TASK_PASS_THRESHOLD)
        self.assertAlmostEqual(ecr["task_pass_dimension_floor"], curriculum.TASK_MIN_DIMENSION)

    def test_run_object_has_mutation_budget(self):
        ro = self._run_and_load_run_object("A001", "ro-mb-a001")
        mb = ro["mutation_budget"]
        self.assertIn("tracked_files_max", mb)
        self.assertIn("net_lines_max", mb)

    def test_run_object_has_paths(self):
        ro = self._run_and_load_run_object("A001", "ro-paths-a001")
        self.assertIsInstance(ro["allowed_paths"], list)
        self.assertIsInstance(ro["blocked_paths"], list)
        self.assertTrue(len(ro["allowed_paths"]) > 0)
        self.assertTrue(len(ro["blocked_paths"]) > 0)

    def test_run_object_has_expected_checks(self):
        ro = self._run_and_load_run_object("A001", "ro-checks-a001")
        checks = ro["expected_checks"]
        self.assertIsInstance(checks, list)
        self.assertTrue(len(checks) > 0)
        for check in checks:
            self.assertIn("id", check)
            self.assertIn("command", check)

    def test_run_object_has_evidence_contract(self):
        ro = self._run_and_load_run_object("A001", "ro-ev-a001")
        ec = ro["evidence_contract"]
        self.assertIn("required_artifacts", ec)
        self.assertIn("provenance_required", ec)

    def test_run_object_has_honesty_fields(self):
        ro = self._run_and_load_run_object("A001", "ro-hon-a001")
        self.assertEqual(ro["execution_status"], "not_started")
        self.assertEqual(ro["execution_backend"], "pending")

    def test_run_object_has_artifact_locations(self):
        ro = self._run_and_load_run_object("A001", "ro-loc-a001")
        locs = ro["artifact_locations"]
        self.assertIn("request_public", locs)
        self.assertIn("request_private", locs)
        self.assertIn("run_object", locs)
        self.assertIn("receipts_dir", locs)

    def test_run_object_stable_across_loads(self):
        """Same packet produces same content hash in run-object.json."""
        ro1 = self._run_and_load_run_object("B001", "ro-stable-1")
        ro2 = self._run_and_load_run_object("B001", "ro-stable-2")
        self.assertEqual(ro1["packet_content_hash"], ro2["packet_content_hash"])
        self.assertEqual(ro1["packet_id"], ro2["packet_id"])


class TestExecutionHonesty(unittest.TestCase):
    """LocalReplayRunner emits machine-readable execution_honesty."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.artifacts_root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run_and_load_result(self, packet_id: str, run_id: str) -> dict:
        cli_main([
            "--packet", packet_id,
            "--run-id", run_id,
            "--artifacts-root", str(self.artifacts_root),
        ])
        result_path = self.artifacts_root / run_id / "result.json"
        self.assertTrue(result_path.exists())
        return json.loads(result_path.read_text())

    def test_execution_honesty_present(self):
        result = self._run_and_load_result("A001", "hon-a001")
        self.assertIn("execution_honesty", result)

    def test_execution_honesty_backend_is_local_replay(self):
        result = self._run_and_load_result("A001", "hon-be-a001")
        eh = result["execution_honesty"]
        self.assertEqual(eh["backend"], "LocalReplayRunner")

    def test_execution_honesty_does_not_claim_execution(self):
        result = self._run_and_load_result("A001", "hon-exec-a001")
        eh = result["execution_honesty"]
        self.assertFalse(eh["executes_commands"])
        self.assertFalse(eh["executes_checks"])

    def test_execution_honesty_checks_not_executed(self):
        result = self._run_and_load_result("A001", "hon-chk-a001")
        eh = result["execution_honesty"]
        self.assertTrue(len(eh["check_results"]) > 0)
        for cr in eh["check_results"]:
            self.assertEqual(cr["execution_status"], "not_executed")
            self.assertIsNone(cr["exit_code"])

    def test_execution_honesty_enforcement_not_enforced(self):
        result = self._run_and_load_result("A001", "hon-enf-a001")
        eh = result["execution_honesty"]
        self.assertEqual(eh["mutation_enforcement"], "not_enforced")
        self.assertEqual(eh["path_constraint_enforcement"], "not_enforced")

    def test_execution_honesty_reports_unavailable_mutation_audit_when_no_diff_exists(self):
        result = self._run_and_load_result("A001", "hon-mut-a001")
        eh = result["execution_honesty"]
        audit = eh["mutation_surface_audit"]
        self.assertEqual(audit["status"], "unavailable")
        self.assertEqual(audit["source"]["kind"], "unavailable")
        self.assertIn("cannot honestly claim mutation-surface compliance", audit["honesty_note"])
        self.assertEqual(eh["mutation_surface_audit_path"], "receipts/mutation-surface-audit.json")


class TestClaudeVibecosystemBetaSeam(unittest.TestCase):
    """Explicit claude_vibecosystem backend selection stays honest and inspectable."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.artifacts_root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run_and_load(self, run_id: str) -> tuple[dict, dict, str]:
        exit_code = cli_main([
            "--packet", "A001",
            "--run-id", run_id,
            "--artifacts-root", str(self.artifacts_root),
            "--runner-backend", "claude_vibecosystem",
        ])
        self.assertEqual(exit_code, 0)
        run_dir = self.artifacts_root / run_id
        result = json.loads((run_dir / "result.json").read_text())
        run_object = json.loads((run_dir / "run-object.json").read_text())
        transcript = (run_dir / "transcript.ndjson").read_text()
        return result, run_object, transcript

    def test_run_object_records_selected_backend(self):
        result, run_object, _ = self._run_and_load("claude-beta-ro")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(run_object["execution_backend"], "claude_vibecosystem")
        contract = run_object["execution_backend_contract"]
        self.assertEqual(contract["mode"], "external_executor_beta")
        self.assertEqual(contract["executor"]["default_agent"], "backend-dev")

    def test_result_execution_honesty_preserves_claim_boundary(self):
        result, _, transcript = self._run_and_load("claude-beta-honesty")
        eh = result["execution_honesty"]
        self.assertEqual(eh["backend"], "claude_vibecosystem")
        self.assertFalse(eh["executes_commands"])
        self.assertFalse(eh["executes_checks"])
        self.assertEqual(eh["mode"], "external_executor_beta")
        self.assertEqual(eh["beta_status"], "adapter_first_contract_stub")
        self.assertEqual(eh["external_executor"]["live_execution"], "not_invoked")
        self.assertEqual(eh["claim_boundary"]["native_clawith_parity"], "not_claimed")
        self.assertEqual(eh["claim_boundary"]["independent_executor_isolation"], "not_claimed")
        self.assertIn("did not invoke Claude Code", eh["honesty_note"])
        self.assertIn("adapter.stub.completed", transcript)

    def test_artifact_bundle_and_candidate_receipt_preserve_backend_provenance(self):
        _, _, _ = self._run_and_load("claude-beta-provenance")
        run_dir = self.artifacts_root / "claude-beta-provenance"

        artifact_bundle = json.loads((run_dir / "artifact-bundle.json").read_text())
        self.assertEqual(artifact_bundle["execution_backend"], "claude_vibecosystem")
        self.assertEqual(artifact_bundle["execution_backend_contract"]["mode"], "external_executor_beta")
        self.assertFalse(artifact_bundle["execution_honesty"]["executes_commands"])
        self.assertEqual(
            artifact_bundle["execution_honesty"]["claim_boundary"]["sealed_evaluation"],
            "not_claimed",
        )

        candidate_receipt = json.loads((run_dir / "receipts" / "candidate.json").read_text())
        backend = candidate_receipt["execution_backend"]
        self.assertEqual(backend["backend_id"], "claude_vibecosystem")
        self.assertEqual(backend["mode"], "external_executor_beta")
        self.assertEqual(
            backend["execution_backend_contract"]["claim_boundary"]["sealed_evaluation"],
            "not_claimed",
        )
        self.assertFalse(backend["execution_honesty"]["executes_checks"])
        self.assertIn("candidate-execution-backend", candidate_receipt["evidence_refs"])


class TestRequestPrivateJsonCarriesPacketRuntime(unittest.TestCase):
    """request.private.json carries the packet_runtime block when run via --packet."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.artifacts_root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_private_request_has_packet_runtime(self):
        cli_main([
            "--packet", "A001",
            "--run-id", "priv-a001",
            "--artifacts-root", str(self.artifacts_root),
        ])
        priv_path = self.artifacts_root / "priv-a001" / "request.private.json"
        self.assertTrue(priv_path.exists())
        priv = json.loads(priv_path.read_text())
        self.assertIn("packet_runtime", priv)
        prt = priv["packet_runtime"]
        self.assertEqual(prt["acceptance_test_id"], "A001")
        self.assertEqual(prt["role_id"], curriculum.FROZEN_ROLE_ID)

    def test_private_request_scenario_set_references_packet(self):
        cli_main([
            "--packet", "C002",
            "--run-id", "priv-c002",
            "--artifacts-root", str(self.artifacts_root),
        ])
        priv = json.loads(
            (self.artifacts_root / "priv-c002" / "request.private.json").read_text()
        )
        self.assertEqual(priv["scenario_set_id"], "packet:C002")


class TestFullArtifactLayout(unittest.TestCase):
    """A packet-driven bridge run produces the complete artifact layout."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.artifacts_root = Path(self._tmpdir.name)
        cli_main([
            "--packet", "A001",
            "--run-id", "layout-a001",
            "--artifacts-root", str(self.artifacts_root),
        ])
        self.run_dir = self.artifacts_root / "layout-a001"

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_request_json_exists(self):
        self.assertTrue((self.run_dir / "request.json").exists())

    def test_request_private_json_exists(self):
        self.assertTrue((self.run_dir / "request.private.json").exists())

    def test_run_object_json_exists(self):
        self.assertTrue((self.run_dir / "run-object.json").exists())

    def test_transcript_exists(self):
        self.assertTrue((self.run_dir / "transcript.ndjson").exists())

    def test_artifact_bundle_exists(self):
        self.assertTrue((self.run_dir / "artifact-bundle.json").exists())

    def test_result_json_exists(self):
        self.assertTrue((self.run_dir / "result.json").exists())

    def test_result_json_is_completed(self):
        result = json.loads((self.run_dir / "result.json").read_text())
        self.assertEqual(result["status"], "completed")

    def test_receipts_directory_exists(self):
        receipts = self.run_dir / "receipts"
        self.assertTrue(receipts.exists())
        self.assertTrue(receipts.is_dir())

    def test_mutation_surface_audit_receipt_exists_and_is_honest(self):
        receipt_path = self.run_dir / "receipts" / "mutation-surface-audit.json"
        self.assertTrue(receipt_path.exists())
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["status"], "unavailable")
        self.assertEqual(receipt["source"]["kind"], "unavailable")

    def test_candidate_receipt_carries_mutation_surface_audit(self):
        candidate_path = self.run_dir / "receipts" / "candidate.json"
        candidate = json.loads(candidate_path.read_text())
        audit = candidate["mutation_surface_audit"]
        self.assertEqual(audit["status"], "unavailable")
        self.assertIn("candidate-mutation-surface-audit", candidate["evidence_refs"])


class TestSubprocessCLI(unittest.TestCase):
    """Exercise the CLI as a real subprocess to prove the module entry point works."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.artifacts_root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_subprocess_packet_run(self):
        result = subprocess.run(
            [
                sys.executable, "-m", "runner_bridge.cli",
                "--packet", "A001",
                "--run-id", "sub-a001",
                "--artifacts-root", str(self.artifacts_root),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        output = json.loads(result.stdout)
        self.assertEqual(output["status"], "completed")

        run_dir = self.artifacts_root / "sub-a001"
        self.assertTrue((run_dir / "run-object.json").exists())
        self.assertTrue((run_dir / "request.private.json").exists())

        ro = json.loads((run_dir / "run-object.json").read_text())
        self.assertEqual(ro["acceptance_test_id"], "A001")
        self.assertEqual(ro["role_id"], curriculum.FROZEN_ROLE_ID)

    def test_subprocess_invalid_packet_fails(self):
        result = subprocess.run(
            [
                sys.executable, "-m", "runner_bridge.cli",
                "--packet", "Z999",
                "--artifacts-root", str(self.artifacts_root),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(ROOT),
        )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()

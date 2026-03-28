"""Tests for the autoresearch alpha orchestrator — real three-stage public-regression loop."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runner_bridge.autoresearch_alpha import (
    BLOCKED_CRITERIA,
    PHASE_C_ACCEPTANCE,
    STAGE_NAMES,
    load_benchmark_pack,
    run_autoresearch_alpha,
)
from runner_bridge.bridge import RunBridge

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PACK = ROOT / "benchmarks" / "public-pack-v1" / "benchmark-pack.json"
EXAMPLE_CONFIG = ROOT / "runner_bridge" / "examples" / "autoresearch-alpha-public-loop.json"


class AutoresearchAlphaThreeStageTests(unittest.TestCase):
    """Core three-stage loop: baseline-eval → candidate-student → candidate-teacher-eval."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.artifacts_root = Path(self._tmpdir.name) / "artifacts"

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_example_config_exists_and_has_stage_shape(self):
        self.assertTrue(EXAMPLE_CONFIG.exists(), "missing autoresearch-alpha-public-loop example")
        config = json.loads(EXAMPLE_CONFIG.read_text())
        self.assertIn("run_id_prefix", config)
        self.assertIn("public_benchmark_pack", config)
        self.assertIn("family_registry", config)
        self.assertIn("integrity_policy", config)
        self.assertIn("comparison_policy", config)
        self.assertIn("stages", config)
        for stage in STAGE_NAMES:
            self.assertIn(stage, config["stages"], f"missing stage: {stage}")
            self.assertIn("request", config["stages"][stage])
        # baseline and teacher-eval have teacher_evaluation
        self.assertIn("teacher_evaluation", config["stages"]["baseline-eval"]["request"])
        self.assertIn("teacher_evaluation", config["stages"]["candidate-teacher-eval"]["request"])
        # candidate-student has prompt_pack_episode_ids
        self.assertIn("prompt_pack_episode_ids", config["stages"]["candidate-student"]["request"])

    def test_benchmark_pack_loads(self):
        pack = load_benchmark_pack(BENCHMARK_PACK)
        self.assertIn("meta", pack)
        self.assertIn("episodes", pack)
        self.assertGreater(len(pack["episodes"]), 0)
        self.assertTrue(pack["execution_policy"]["student_visible_only"])

    def test_three_stages_execute_through_bridge(self):
        """All three stages must execute as separate runs through RunBridge."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(
            request_payload=config,
            bridge=bridge,
        )

        self.assertEqual(receipt["receipt_type"], "autoresearch-alpha")
        self.assertEqual(receipt["receipt_version"], "0.2.0")

        # Three distinct stages with run IDs
        stages = receipt["stages"]
        self.assertIn("baseline-eval", stages)
        self.assertIn("candidate-student", stages)
        self.assertIn("candidate-teacher-eval", stages)

        # Each stage has a distinct run_id and completed status
        prefix = config["run_id_prefix"]
        self.assertEqual(stages["baseline-eval"]["run_id"], f"{prefix}-baseline-eval")
        self.assertEqual(stages["candidate-student"]["run_id"], f"{prefix}-candidate-student")
        self.assertEqual(stages["candidate-teacher-eval"]["run_id"], f"{prefix}-candidate-teacher-eval")

        self.assertEqual(stages["baseline-eval"]["status"], "completed")
        self.assertEqual(stages["candidate-student"]["status"], "completed")
        self.assertEqual(stages["candidate-teacher-eval"]["status"], "completed")

        # Three separate run directories exist
        for stage_suffix in ("baseline-eval", "candidate-student", "candidate-teacher-eval"):
            run_dir = self.artifacts_root / f"{prefix}-{stage_suffix}"
            self.assertTrue(run_dir.exists(), f"missing run dir: {run_dir}")
            self.assertTrue((run_dir / "request.json").exists())
            self.assertTrue((run_dir / "result.json").exists())
            self.assertTrue((run_dir / "transcript.ndjson").exists())
            self.assertTrue((run_dir / "artifact-bundle.json").exists())

    def test_baseline_eval_produces_aggregate_score(self):
        """Stage 1 baseline-eval must produce a real aggregate_score."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        baseline = receipt["stages"]["baseline-eval"]
        self.assertIn("aggregate_score", baseline)
        self.assertIn("pass_rate", baseline["aggregate_score"])
        self.assertIn("average_score", baseline["aggregate_score"])
        self.assertGreater(baseline["aggregate_score"]["total"], 0)

    def test_candidate_student_has_no_teacher_evaluation(self):
        """Stage 2 candidate-student must NOT have teacher evaluation."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        prefix = config["run_id_prefix"]
        student_dir = self.artifacts_root / f"{prefix}-candidate-student"
        bundle = json.loads((student_dir / "artifact-bundle.json").read_text())

        # Should have student_view but NOT teacher_output
        self.assertIn("student_view", bundle)
        self.assertNotIn("teacher_output", bundle)

        # Student view should reference prompt pack
        sv = bundle["student_view"]
        self.assertEqual(sv["sealed_holdout_count"], 0)

        # The request should have student_prompt_pack, not teacher_evaluation
        private_request = json.loads((student_dir / "request.private.json").read_text())
        self.assertIn("student_prompt_pack", private_request)
        self.assertNotIn("teacher_evaluation", private_request)

    def test_candidate_teacher_eval_injects_real_baseline(self):
        """Stage 3 must inject the real baseline aggregate_score from stage 1."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        prefix = config["run_id_prefix"]
        teacher_dir = self.artifacts_root / f"{prefix}-candidate-teacher-eval"
        private_request = json.loads((teacher_dir / "request.private.json").read_text())

        # Teacher eval must have previous_iteration injected from real baseline
        te = private_request["teacher_evaluation"]
        self.assertIn("previous_iteration", te)
        prev = te["previous_iteration"]
        self.assertEqual(prev["run_id"], f"{prefix}-baseline-eval")
        self.assertIn("aggregate_score", prev)
        self.assertIn("pass_rate", prev["aggregate_score"])

    def test_verdict_compares_baseline_vs_candidate(self):
        """Verdict must compare real baseline aggregate vs candidate teacher eval."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        verdict = receipt["comparison_verdict"]
        self.assertIn(verdict["label"], ("better", "equal", "worse"))
        self.assertIn("delta_pass_rate", verdict)
        self.assertIn("delta_average_score", verdict)
        self.assertIn("score_deltas", receipt)

    def test_run_record_history_tracks_lifecycle(self):
        """Per-stage run-record-history.json must track queued → running → completed."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        # run-record-history.json on disk
        prefix = config["run_id_prefix"]
        history_path = self.artifacts_root / f"{prefix}.run-record-history.json"
        self.assertTrue(history_path.exists(), "missing run-record-history.json")
        history = json.loads(history_path.read_text())
        self.assertEqual(len(history["stages"]), 3)

        for record in history["stages"]:
            self.assertIn(record["stage"], STAGE_NAMES)
            self.assertIsNotNone(record["queued_at"])
            self.assertIsNotNone(record["started_at"])
            self.assertIsNotNone(record["completed_at"])
            self.assertEqual(record["status"], "completed")
            # State should reflect final state
            self.assertIn(record["state"], ("completed", "failed"))

        # Also in receipt
        self.assertEqual(len(receipt["run_record_history"]), 3)

    def test_top_level_artifacts_written(self):
        """artifacts_root must contain autoresearch-alpha.json + request copy."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        self.assertTrue(
            (self.artifacts_root / "autoresearch-alpha.json").exists(),
            "missing autoresearch-alpha.json",
        )
        self.assertTrue(
            (self.artifacts_root / "autoresearch-alpha.request.json").exists(),
            "missing autoresearch-alpha.request.json",
        )

        # Receipt on disk matches returned receipt (minus receipt_path)
        disk_receipt = json.loads((self.artifacts_root / "autoresearch-alpha.json").read_text())
        self.assertEqual(disk_receipt["receipt_type"], "autoresearch-alpha")
        self.assertEqual(disk_receipt["receipt_version"], "0.2.0")

    def test_artifact_coverage_across_all_stages(self):
        """Artifact coverage must span all three stage run directories."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        coverage = receipt["integrity_gate"]["artifact_coverage"]
        self.assertIn("baseline_eval", coverage)
        self.assertIn("candidate_student", coverage)
        self.assertIn("candidate_teacher_eval", coverage)

        for stage_name, checks in coverage.items():
            for artifact, present in checks.items():
                self.assertTrue(present, f"missing artifact {artifact} in {stage_name}")

    def test_integrity_gating_honest(self):
        """Integrity gate must show public_regression pass, sealed/cert blocked."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        gate = receipt["integrity_gate"]
        self.assertIn(gate["public_regression"], ("pass", "fail"))
        self.assertEqual(gate["sealed_eval"], "blocked")
        self.assertEqual(gate["certification"], "blocked")

    def test_phase_c_acceptance_honest(self):
        """Phase C acceptance must surface C003 and C007 as blocked."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        pca = receipt["phase_c_acceptance"]
        self.assertEqual(pca["C001"]["status"], "pass")
        self.assertEqual(pca["C002"]["status"], "pass")
        self.assertEqual(pca["C003"]["status"], "blocked")
        self.assertEqual(pca["C004"]["status"], "pass")
        self.assertEqual(pca["C005"]["status"], "pass")
        self.assertEqual(pca["C006"]["status"], "pass")
        self.assertEqual(pca["C007"]["status"], "blocked")

    def test_blocked_criteria_surfaced(self):
        """Blocked criteria must be honest about what is not implemented."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        self.assertEqual(len(receipt["blocked_criteria"]), len(BLOCKED_CRITERIA))
        blocked_ids = {c["id"] for c in receipt["blocked_criteria"]}
        self.assertIn("mutation-surface-enforcement", blocked_ids)
        self.assertIn("sealed-holdout-coverage", blocked_ids)
        self.assertIn("live-execution-backend", blocked_ids)
        self.assertIn("verdict-stability", blocked_ids)


class AutoresearchAlphaHonestyTests(unittest.TestCase):
    """Honesty checks — the loop must not overclaim."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.artifacts_root = Path(self._tmpdir.name) / "artifacts"

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_honesty_note_present(self):
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        self.assertIn("honesty_note", receipt)
        self.assertIn("three real stages", receipt["honesty_note"].lower())
        self.assertIn("LocalReplayRunner", receipt["honesty_note"])
        self.assertIn("deterministic", receipt["honesty_note"].lower())

    def test_student_stage_has_no_sealed_scenarios(self):
        """Student view in candidate-student must not contain holdout scenarios."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        prefix = config["run_id_prefix"]
        student_dir = self.artifacts_root / f"{prefix}-candidate-student"
        bundle = json.loads((student_dir / "artifact-bundle.json").read_text())

        sv = bundle.get("student_view", {})
        self.assertEqual(sv.get("sealed_holdout_count", -1), 0)


class AutoresearchAlphaCLITests(unittest.TestCase):
    """CLI entrypoint: python3 -m runner_bridge.autoresearch_alpha."""

    def test_cli_entrypoint_runs_three_stages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.autoresearch_alpha",
                    "--request",
                    str(EXAMPLE_CONFIG),
                    "--artifacts-root",
                    str(artifacts_root),
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            receipt = json.loads(result.stdout)
            self.assertEqual(receipt["receipt_type"], "autoresearch-alpha")
            self.assertIn("baseline-eval", receipt["stages"])
            self.assertIn("candidate-student", receipt["stages"])
            self.assertIn("candidate-teacher-eval", receipt["stages"])

            # All three run dirs exist
            prefix = receipt["run_id_prefix"]
            for suffix in ("baseline-eval", "candidate-student", "candidate-teacher-eval"):
                run_dir = artifacts_root / f"{prefix}-{suffix}"
                self.assertTrue(run_dir.exists(), f"CLI: missing run dir {run_dir}")

            # Top-level artifacts
            self.assertTrue((artifacts_root / "autoresearch-alpha.json").exists())
            self.assertTrue((artifacts_root / "autoresearch-alpha.request.json").exists())


class AutoresearchAlphaLegacyCompatTests(unittest.TestCase):
    """Legacy simple invocation without request_payload still works."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.artifacts_root = Path(self._tmpdir.name) / "artifacts"

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_simple_invocation_runs_three_stages(self):
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        receipt = run_autoresearch_alpha(
            bridge=bridge,
            run_id_prefix="alpha-legacy-test",
            benchmark_pack_path=str(BENCHMARK_PACK),
            max_episodes=3,
        )

        self.assertEqual(receipt["receipt_type"], "autoresearch-alpha")
        self.assertIn("baseline-eval", receipt["stages"])
        self.assertIn("candidate-student", receipt["stages"])
        self.assertIn("candidate-teacher-eval", receipt["stages"])

        # All three stages completed
        for stage in STAGE_NAMES:
            self.assertEqual(receipt["stages"][stage]["status"], "completed")


if __name__ == "__main__":
    unittest.main()

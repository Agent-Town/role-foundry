"""Tests for the autoresearch alpha orchestrator — real three-stage public-regression loop."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runner_bridge.autoresearch_alpha import (
    BLOCKED_CRITERIA,
    LOCAL_HOLDOUT_CRITERIA_OVERRIDE,
    PHASE_C_ACCEPTANCE,
    STAGE_NAMES,
    build_comparison_summary,
    build_promotion_decision,
    load_benchmark_pack,
    load_private_holdout_manifest,
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

    def test_comparison_summary_exposes_total_and_category_deltas(self):
        """Comparison summary JSON must surface total score + category deltas."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        comparison = receipt["comparison"]
        self.assertEqual(comparison["baseline_run_id"], receipt["stages"]["baseline-eval"]["run_id"])
        self.assertEqual(comparison["candidate_run_id"], receipt["stages"]["candidate-teacher-eval"]["run_id"])
        self.assertIn("total_score_delta", comparison)
        self.assertIn("category_deltas", comparison)
        self.assertEqual(comparison["total_score_delta"], 0.25)
        self.assertEqual(comparison["category_deltas"]["average_score"], 0.25)
        self.assertIn("pass_count", comparison["category_deltas"])
        self.assertTrue(comparison["reasons"])

        comparison_summary_path = Path(receipt["comparison_summary_path"])
        self.assertTrue(comparison_summary_path.exists(), "missing comparison summary JSON")
        comparison_summary = json.loads(comparison_summary_path.read_text())
        self.assertEqual(comparison_summary["comparison"]["total_score_delta"], 0.25)

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
        """artifacts_root must contain receipt + request copy + comparison summary."""
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
        self.assertTrue(
            (self.artifacts_root / "autoresearch-alpha.comparison.json").exists(),
            "missing autoresearch-alpha.comparison.json",
        )

        # Receipt on disk matches returned receipt (minus runtime-added paths)
        disk_receipt = json.loads((self.artifacts_root / "autoresearch-alpha.json").read_text())
        self.assertEqual(disk_receipt["receipt_type"], "autoresearch-alpha")
        self.assertEqual(disk_receipt["receipt_version"], "0.2.0")
        self.assertIn("comparison", disk_receipt)
        self.assertIn("promotion_decision", disk_receipt)

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
        """Integrity gate must surface detailed machine-readable gate status."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        gate = receipt["integrity_gate"]
        self.assertIn(gate["public_regression"], ("pass", "fail"))
        self.assertEqual(gate["sealed_eval"], "blocked")
        self.assertEqual(gate["certification"], "blocked")
        self.assertIn("gates", gate)
        self.assertEqual(gate["gates"]["no_holdout_leakage"]["status"], "pass")
        self.assertEqual(gate["gates"]["required_artifacts_present"]["status"], "pass")
        self.assertEqual(gate["gates"]["mutation_surface_enforcement"]["status"], "blocked")
        self.assertEqual(gate["gates"]["demo_tests_still_work"]["status"], "blocked")

    def test_promotion_decision_blocks_weighted_promotion_when_integrity_is_not_clear(self):
        """Raw comparison may be better, but weighted promotion must stay blocked."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        self.assertEqual(receipt["comparison_verdict"]["label"], "better")
        self.assertEqual(receipt["promotion_decision"]["status"], "blocked")
        self.assertFalse(receipt["promotion_decision"]["eligible_for_weighted_promotion"])
        self.assertIn("mutation_surface_enforcement", receipt["promotion_decision"]["blocked_gates"])
        self.assertIn("demo_tests_still_work", receipt["promotion_decision"]["blocked_gates"])
        self.assertEqual(
            receipt["stages"]["candidate-teacher-eval"]["effective_label"],
            "blocked",
        )

    def test_phase_c_acceptance_honest(self):
        """Phase C acceptance must surface C003/C007 blocked and C008/C009 passed."""
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
        self.assertEqual(pca["C008"]["status"], "pass")
        self.assertEqual(pca["C009"]["status"], "pass")

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

    def _mutation_surface_config(self) -> dict:
        config = json.loads(EXAMPLE_CONFIG.read_text())
        config["stages"]["candidate-student"]["request"].update(
            {
                "packet_runtime": {
                    "packet_id": "inline-mutation-surface-alpha",
                    "packet_version": "1.0.0",
                    "acceptance_test_id": "alpha-mutation-surface",
                    "role_id": "role-autoresearch-alpha",
                    "phase_index": 0,
                    "allowed_paths": ["runner_bridge/**", "tests/**", "docs/**"],
                    "blocked_paths": ["submission/**", "benchmarks/private-holdout-pack/**"],
                    "mutation_budget": {
                        "tracked_files_max": 3,
                        "net_lines_max": 40,
                    },
                    "expected_checks": [],
                    "eval_contract_ref": {},
                    "evidence_contract": {
                        "required_artifacts": [],
                        "provenance_required": True,
                        "student_visible_only": True,
                    },
                },
            }
        )
        return config

    def test_mutation_surface_audit_passes_when_declared_changes_stay_in_scope(self):
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = self._mutation_surface_config()
        config["stages"]["candidate-student"]["request"]["workspace_snapshot"] = {
            "changed_files": [
                "runner_bridge/autoresearch_alpha.py",
                "tests/test_autoresearch_alpha_loop.py",
            ],
            "diff_stats": {"tracked_files": 2, "net_lines": 24},
        }

        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        self.assertEqual(receipt["mutation_surface_audit"]["status"], "pass")
        self.assertEqual(receipt["integrity_gate"]["gates"]["mutation_surface_enforcement"]["status"], "pass")
        blocked_ids = {c["id"] for c in receipt["blocked_criteria"]}
        self.assertNotIn("mutation-surface-enforcement", blocked_ids)

    def test_mutation_surface_audit_fails_on_out_of_scope_file(self):
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = self._mutation_surface_config()
        config["stages"]["candidate-student"]["request"]["workspace_snapshot"] = {
            "changed_files": [
                "runner_bridge/autoresearch_alpha.py",
                "app/live-read-model.alpha-receipt.sample.json",
            ],
            "diff_stats": {"tracked_files": 2, "net_lines": 18},
        }

        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        self.assertEqual(receipt["mutation_surface_audit"]["status"], "fail")
        self.assertEqual(receipt["integrity_gate"]["gates"]["mutation_surface_enforcement"]["status"], "fail")
        self.assertIn("mutation_surface_enforcement", receipt["promotion_decision"]["failed_gates"])

    def test_mutation_surface_audit_blocks_when_net_lines_evidence_is_missing(self):
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = self._mutation_surface_config()
        config["stages"]["candidate-student"]["request"]["workspace_snapshot"] = {
            "changed_files": ["runner_bridge/autoresearch_alpha.py"],
        }

        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)

        self.assertEqual(receipt["mutation_surface_audit"]["status"], "unavailable")
        self.assertEqual(receipt["integrity_gate"]["gates"]["mutation_surface_enforcement"]["status"], "blocked")
        blocked_ids = {c["id"] for c in receipt["blocked_criteria"]}
        self.assertIn("mutation-surface-enforcement", blocked_ids)


class AutoresearchAlphaPromotionDecisionUnitTests(unittest.TestCase):
    """Focused comparison/promotion logic tests for C008/C009."""

    def test_build_comparison_summary_uses_existing_aggregate_score_surface(self):
        baseline = {
            "passed": 3,
            "total": 4,
            "pass_rate": 0.75,
            "average_score": 0.5,
            "holdout": {"passed": 0, "total": 0, "pass_rate": 0.0},
        }
        candidate = {
            "passed": 4,
            "total": 4,
            "pass_rate": 1.0,
            "average_score": 0.75,
            "holdout": {"passed": 0, "total": 0, "pass_rate": 0.0},
        }
        comparison = build_comparison_summary(
            baseline_run_id="baseline-run",
            candidate_run_id="candidate-run",
            baseline_score=baseline,
            candidate_score=candidate,
            verdict={
                "label": "better",
                "delta_pass_rate": 0.25,
                "delta_average_score": 0.25,
            },
            comparison_policy={"metric": "pass_rate", "direction": "higher_is_better"},
        )

        self.assertEqual(comparison["score_basis"], "scorecard.aggregate_score.average_score")
        self.assertEqual(comparison["baseline_total_score"], 0.5)
        self.assertEqual(comparison["candidate_total_score"], 0.75)
        self.assertEqual(comparison["total_score_delta"], 0.25)
        self.assertEqual(comparison["category_deltas"]["pass_count"], 1)
        self.assertEqual(comparison["category_deltas"]["pass_rate"], 0.25)

    def test_build_promotion_decision_requires_all_integrity_gates_to_pass(self):
        comparison = {"verdict": "better"}

        blocked_decision = build_promotion_decision(
            comparison=comparison,
            integrity_gate={"failed_gates": [], "blocked_gates": ["demo_tests_still_work"]},
        )
        self.assertEqual(blocked_decision["status"], "blocked")
        self.assertFalse(blocked_decision["eligible_for_weighted_promotion"])

        failed_decision = build_promotion_decision(
            comparison=comparison,
            integrity_gate={"failed_gates": ["required_artifacts_present"], "blocked_gates": []},
        )
        self.assertEqual(failed_decision["status"], "fail")
        self.assertFalse(failed_decision["eligible_for_weighted_promotion"])

        passing_decision = build_promotion_decision(
            comparison=comparison,
            integrity_gate={"failed_gates": [], "blocked_gates": []},
        )
        self.assertEqual(passing_decision["status"], "pass")
        self.assertTrue(passing_decision["eligible_for_weighted_promotion"])


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
        self.assertIn("verdict stability", receipt["honesty_note"].lower())

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
            self.assertTrue((artifacts_root / "autoresearch-alpha.comparison.json").exists())


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


class AutoresearchAlphaPrivateHoldoutTests(unittest.TestCase):
    """Private-holdout manifest: local-only replay coverage, NOT certified sealed eval."""

    HOLDOUT_MANIFEST = {
        "meta": {"id": "test-holdout-manifest-v1", "version": "1.0.0"},
        "holdout_scenarios": [
            {
                "id": "holdout-scenario-alpha",
                "title": "Alpha holdout scenario",
                "type": "holdout",
                "difficulty": "hard",
                "holdout_prompt": "SECRET teacher-only holdout prompt text",
                "rubric": "SECRET rubric for grading",
                "passed": False,
                "score": 0.0,
                "teacher_notes": "Private holdout — local replay only.",
            },
            {
                "id": "holdout-scenario-beta",
                "title": "Beta holdout scenario",
                "type": "holdout",
                "difficulty": "hard",
                "holdout_prompt": "Another SECRET holdout prompt",
                "rubric": "Another SECRET rubric",
                "passed": False,
                "score": 0.0,
                "teacher_notes": "Private holdout — local replay only.",
            },
        ],
    }

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.artifacts_root = Path(self._tmpdir.name) / "artifacts"
        # Write manifest to a temp file (local, untracked)
        self._manifest_path = Path(self._tmpdir.name) / "holdout-manifest.json"
        self._manifest_path.write_text(json.dumps(self.HOLDOUT_MANIFEST, indent=2))

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run_with_holdout(self, *, via_payload: bool = False) -> dict:
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        if via_payload:
            config["private_holdout_manifest"] = str(self._manifest_path)
            return run_autoresearch_alpha(request_payload=config, bridge=bridge)
        return run_autoresearch_alpha(
            request_payload=config,
            bridge=bridge,
            private_holdout_manifest_path=str(self._manifest_path),
        )

    def test_load_private_holdout_manifest_validates_shape(self):
        manifest = load_private_holdout_manifest(self._manifest_path)
        self.assertEqual(len(manifest["holdout_scenarios"]), 2)
        self.assertEqual(manifest["meta"]["id"], "test-holdout-manifest-v1")

    def test_load_private_holdout_manifest_rejects_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            load_private_holdout_manifest("/nonexistent/path.json")

    def test_load_private_holdout_manifest_rejects_invalid_shape(self):
        bad_manifest = Path(self._tmpdir.name) / "bad.json"
        bad_manifest.write_text(json.dumps({"meta": {}}))
        with self.assertRaises(ValueError):
            load_private_holdout_manifest(bad_manifest)

    def test_holdout_hydrated_into_baseline_eval_private_request(self):
        """baseline-eval request.private.json must contain holdout scenarios."""
        receipt = self._run_with_holdout()
        prefix = receipt["run_id_prefix"]
        baseline_dir = self.artifacts_root / f"{prefix}-baseline-eval"
        private_request = json.loads((baseline_dir / "request.private.json").read_text())
        te = private_request["teacher_evaluation"]
        self.assertTrue(te.get("private_holdout_injected"))
        self.assertEqual(te["private_holdout_count"], 2)
        holdout_ids = [s["id"] for s in te["scenarios"] if s.get("type") == "holdout"]
        self.assertIn("holdout-scenario-alpha", holdout_ids)
        self.assertIn("holdout-scenario-beta", holdout_ids)

    def test_holdout_hydrated_into_candidate_teacher_eval_private_request(self):
        """candidate-teacher-eval request.private.json must contain holdout scenarios."""
        receipt = self._run_with_holdout()
        prefix = receipt["run_id_prefix"]
        teacher_dir = self.artifacts_root / f"{prefix}-candidate-teacher-eval"
        private_request = json.loads((teacher_dir / "request.private.json").read_text())
        te = private_request["teacher_evaluation"]
        self.assertTrue(te.get("private_holdout_injected"))
        self.assertEqual(te["private_holdout_count"], 2)
        holdout_ids = [s["id"] for s in te["scenarios"] if s.get("type") == "holdout"]
        self.assertIn("holdout-scenario-alpha", holdout_ids)
        self.assertIn("holdout-scenario-beta", holdout_ids)

    def test_student_stage_public_only_no_holdout_content(self):
        """candidate-student must NOT contain holdout prompt/rubric text."""
        receipt = self._run_with_holdout()
        prefix = receipt["run_id_prefix"]
        student_dir = self.artifacts_root / f"{prefix}-candidate-student"

        # request.json (public) must not have holdout content
        public_request = json.loads((student_dir / "request.json").read_text())
        public_text = json.dumps(public_request)
        self.assertNotIn("SECRET teacher-only holdout prompt", public_text)
        self.assertNotIn("SECRET rubric", public_text)
        self.assertNotIn("teacher_evaluation", public_request)

        # request.private.json must not have teacher_evaluation either
        private_request = json.loads((student_dir / "request.private.json").read_text())
        self.assertNotIn("teacher_evaluation", private_request)

        # student_view in artifact bundle must not leak holdout content
        bundle = json.loads((student_dir / "artifact-bundle.json").read_text())
        self.assertNotIn("teacher_output", bundle)
        sv = bundle["student_view"]
        sv_text = json.dumps(sv)
        self.assertNotIn("SECRET", sv_text)
        self.assertNotIn("holdout_prompt", sv_text)
        # Check no holdout scenario objects leaked (not just substring "rubric"
        # which may appear in public episode text)
        holdout_scenarios_in_sv = [
            s for s in sv.get("episodes", [])
            if isinstance(s, dict) and s.get("type") == "holdout"
        ]
        self.assertEqual(len(holdout_scenarios_in_sv), 0, "holdout scenarios leaked into student_view")

    def test_student_stage_exposes_sealed_holdout_count_metadata(self):
        """candidate-student student_view must expose sealed_holdout_count."""
        receipt = self._run_with_holdout()
        prefix = receipt["run_id_prefix"]
        student_dir = self.artifacts_root / f"{prefix}-candidate-student"
        bundle = json.loads((student_dir / "artifact-bundle.json").read_text())
        sv = bundle["student_view"]
        self.assertEqual(sv["sealed_holdout_count"], 2)

    def test_request_json_never_contains_holdout_text(self):
        """request.json (public artifact) must never contain holdout prompt/rubric."""
        receipt = self._run_with_holdout()
        prefix = receipt["run_id_prefix"]
        for suffix in ("baseline-eval", "candidate-student", "candidate-teacher-eval"):
            run_dir = self.artifacts_root / f"{prefix}-{suffix}"
            public_request = json.loads((run_dir / "request.json").read_text())
            public_text = json.dumps(public_request)
            self.assertNotIn("SECRET teacher-only holdout prompt", public_text, f"holdout leaked in {suffix}/request.json")
            self.assertNotIn("SECRET rubric", public_text, f"rubric leaked in {suffix}/request.json")

    def test_receipt_has_local_private_holdout_summary(self):
        """Receipt must include local_private_holdout with honest summary."""
        receipt = self._run_with_holdout()
        self.assertIn("local_private_holdout", receipt)
        lph = receipt["local_private_holdout"]
        self.assertEqual(lph["manifest_id"], "test-holdout-manifest-v1")
        self.assertEqual(lph["holdout_scenario_count"], 2)
        self.assertEqual(lph["hydrated_stages"], ["baseline-eval", "candidate-teacher-eval"])
        self.assertEqual(lph["student_stage_exposure"], "sealed_holdout_count metadata only")
        self.assertIn("local-only replay coverage", lph["honesty_note"])
        self.assertIn("NOT certified sealed eval", lph["honesty_note"])
        self.assertEqual(lph["integrity_status"], "local-replay-only")

    def test_honesty_note_mentions_local_holdout(self):
        """Honesty note must mention local private-holdout manifest."""
        receipt = self._run_with_holdout()
        self.assertIn("local private-holdout manifest", receipt["honesty_note"].lower())
        self.assertIn("NOT certified sealed eval", receipt["honesty_note"])
        self.assertIn("local-only replay coverage", receipt["honesty_note"].lower())

    def test_blocked_criteria_overrides_sealed_holdout_coverage(self):
        """sealed-holdout-coverage criterion must use local holdout override."""
        receipt = self._run_with_holdout()
        holdout_criteria = [
            c for c in receipt["blocked_criteria"]
            if c["id"] == "sealed-holdout-coverage"
        ]
        self.assertEqual(len(holdout_criteria), 1)
        self.assertEqual(holdout_criteria[0]["status"], "blocked")
        self.assertIn("Local private-holdout manifest attached", holdout_criteria[0]["reason"])

    def test_integrity_gate_no_holdout_leakage_passes(self):
        """no_holdout_leakage gate must pass (count metadata allowed, no content leak)."""
        receipt = self._run_with_holdout()
        gate = receipt["integrity_gate"]["gates"]["no_holdout_leakage"]
        self.assertEqual(gate["status"], "pass")
        self.assertTrue(gate["detail"]["private_holdout_manifest_attached"])
        self.assertFalse(gate["detail"]["holdout_content_leaked"])

    def test_sealed_eval_and_certification_remain_blocked(self):
        """Sealed eval and certification must remain blocked even with local holdout."""
        receipt = self._run_with_holdout()
        self.assertEqual(receipt["integrity_gate"]["sealed_eval"], "blocked")
        self.assertEqual(receipt["integrity_gate"]["certification"], "blocked")

    def test_private_holdout_via_payload_key(self):
        """private_holdout_manifest key in request payload works like CLI arg."""
        receipt = self._run_with_holdout(via_payload=True)
        self.assertIn("local_private_holdout", receipt)
        self.assertEqual(receipt["local_private_holdout"]["holdout_scenario_count"], 2)

    def test_without_holdout_no_local_private_holdout_in_receipt(self):
        """Without holdout manifest, receipt must NOT have local_private_holdout."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        config = json.loads(EXAMPLE_CONFIG.read_text())
        receipt = run_autoresearch_alpha(request_payload=config, bridge=bridge)
        self.assertNotIn("local_private_holdout", receipt)

    def test_cli_with_private_holdout_manifest(self):
        """CLI --private-holdout-manifest flag must work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            manifest_path = Path(tmpdir) / "holdout.json"
            manifest_path.write_text(json.dumps(self.HOLDOUT_MANIFEST, indent=2))
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.autoresearch_alpha",
                    "--request",
                    str(EXAMPLE_CONFIG),
                    "--artifacts-root",
                    str(artifacts_root),
                    "--private-holdout-manifest",
                    str(manifest_path),
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(result.stdout)
            self.assertIn("local_private_holdout", receipt)
            self.assertEqual(receipt["local_private_holdout"]["holdout_scenario_count"], 2)


if __name__ == "__main__":
    unittest.main()

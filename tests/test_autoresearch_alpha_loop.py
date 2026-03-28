"""Tests for the autoresearch alpha orchestrator (Phase C, narrow public lane)."""

import json
import tempfile
import unittest
from pathlib import Path

from runner_bridge.autoresearch_alpha import (
    BLOCKED_CRITERIA,
    load_benchmark_pack,
    run_autoresearch_alpha,
)
from runner_bridge.bridge import RunBridge

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PACK = ROOT / "benchmarks" / "public-pack-v1" / "benchmark-pack.json"
EXAMPLE_CONFIG = ROOT / "runner_bridge" / "examples" / "autoresearch-alpha-loop.json"


class AutoresearchAlphaLoopTests(unittest.TestCase):
    """Core loop: baseline → candidate → teacher eval → verdict."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.artifacts_root = Path(self._tmpdir.name) / "artifacts"

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_example_config_exists_and_is_valid(self):
        self.assertTrue(EXAMPLE_CONFIG.exists(), "missing autoresearch-alpha example config")
        config = json.loads(EXAMPLE_CONFIG.read_text())
        self.assertIn("run_id_prefix", config)
        self.assertIn("previous_iteration", config)
        self.assertIn("honesty_note", config)

    def test_benchmark_pack_loads(self):
        pack = load_benchmark_pack(BENCHMARK_PACK)
        self.assertIn("meta", pack)
        self.assertIn("episodes", pack)
        self.assertGreater(len(pack["episodes"]), 0)
        self.assertTrue(pack["execution_policy"]["student_visible_only"])

    def test_first_iteration_no_previous(self):
        """First iteration with no baseline — should produce a valid receipt."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        receipt = run_autoresearch_alpha(
            bridge=bridge,
            run_id_prefix="alpha-test-first",
            benchmark_pack_path=str(BENCHMARK_PACK),
            previous_iteration=None,
            max_episodes=3,
        )

        self.assertEqual(receipt["receipt_type"], "autoresearch-alpha")
        self.assertIn("stages", receipt)
        self.assertIn("baseline", receipt["stages"])
        self.assertIn("candidate", receipt["stages"])
        self.assertIn("teacher_evaluation", receipt["stages"])

        # Baseline should indicate no previous
        self.assertEqual(receipt["stages"]["baseline"]["status"], "no_previous")

        # Candidate should have completed
        self.assertEqual(receipt["stages"]["candidate"]["status"], "completed")

        # Verdict should exist
        self.assertIn("comparison_verdict", receipt)
        verdict = receipt["comparison_verdict"]
        self.assertIn(verdict["label"], ("better", "equal", "worse"))

        # Blocked criteria surfaced honestly
        self.assertEqual(len(receipt["blocked_criteria"]), len(BLOCKED_CRITERIA))
        blocked_ids = {c["id"] for c in receipt["blocked_criteria"]}
        self.assertIn("mutation-surface-enforcement", blocked_ids)
        self.assertIn("sealed-holdout-coverage", blocked_ids)
        self.assertIn("live-execution-backend", blocked_ids)
        self.assertIn("verdict-stability", blocked_ids)

        # Honesty note present
        self.assertIn("LocalReplayRunner", receipt["honesty_note"])

    def test_iteration_with_previous_baseline(self):
        """Second iteration with a previous baseline — should compute deltas."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        previous = {
            "run_id": "alpha-test-baseline-000",
            "label": "baseline",
            "aggregate_score": {
                "passed": 1,
                "total": 4,
                "pass_rate": 0.25,
                "average_score": 0.4,
                "holdout": {"passed": 0, "total": 0, "pass_rate": 0.0},
            },
            "public_failure_themes": [
                "Landing copy is generic",
            ],
        }

        receipt = run_autoresearch_alpha(
            bridge=bridge,
            run_id_prefix="alpha-test-iter1",
            benchmark_pack_path=str(BENCHMARK_PACK),
            previous_iteration=previous,
            max_episodes=4,
        )

        # Baseline should reference previous
        self.assertEqual(receipt["stages"]["baseline"]["status"], "from_previous_iteration")
        self.assertEqual(
            receipt["stages"]["baseline"]["aggregate_score"]["passed"], 1,
        )

        # Candidate should have completed with teacher eval
        self.assertEqual(receipt["stages"]["candidate"]["status"], "completed")
        candidate_score = receipt["stages"]["candidate"]["aggregate_score"]
        self.assertGreater(candidate_score.get("total", 0), 0)

        # Verdict should be "better" since candidate default score > baseline
        verdict = receipt["comparison_verdict"]
        self.assertEqual(verdict["label"], "better")
        self.assertGreater(verdict["delta_pass_rate"], 0)

        # Score deltas present
        self.assertIn("score_deltas", receipt)
        self.assertIsInstance(receipt["score_deltas"]["pass_rate"], float)
        self.assertIsInstance(receipt["score_deltas"]["average_score"], float)

        # Iteration history present
        self.assertIsInstance(receipt["iteration_history"], list)
        self.assertGreater(len(receipt["iteration_history"]), 0)

    def test_artifact_coverage_and_receipt_file(self):
        """Receipt should report artifact coverage and be written to disk."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        receipt = run_autoresearch_alpha(
            bridge=bridge,
            run_id_prefix="alpha-test-artifacts",
            benchmark_pack_path=str(BENCHMARK_PACK),
            previous_iteration=None,
            max_episodes=2,
        )

        # Integrity gate
        gate = receipt["integrity_gate"]
        self.assertTrue(gate["all_artifacts_present"])
        for key, present in gate["artifact_coverage"].items():
            self.assertTrue(present, f"missing artifact: {key}")

        # Receipt file written
        receipt_path = Path(receipt["receipt_path"])
        self.assertTrue(receipt_path.exists())
        disk_receipt = json.loads(receipt_path.read_text())
        self.assertEqual(disk_receipt["receipt_type"], "autoresearch-alpha")

    def test_provenance_chain_preserved(self):
        """D001-D005 guarantees: provenance is threaded through the candidate run."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        receipt = run_autoresearch_alpha(
            bridge=bridge,
            run_id_prefix="alpha-test-provenance",
            benchmark_pack_path=str(BENCHMARK_PACK),
            previous_iteration={
                "run_id": "baseline-prev",
                "aggregate_score": {
                    "passed": 0, "total": 2, "pass_rate": 0.0, "average_score": 0.0,
                    "holdout": {"passed": 0, "total": 0, "pass_rate": 0.0},
                },
            },
            max_episodes=2,
        )

        self.assertTrue(receipt["integrity_gate"]["provenance_present"])

        # Check actual provenance files on disk
        candidate_dir = self.artifacts_root / "alpha-test-provenance-candidate"
        self.assertTrue((candidate_dir / "receipts" / "manifest.json").exists())
        self.assertTrue((candidate_dir / "receipts" / "candidate.json").exists())
        self.assertTrue((candidate_dir / "receipts" / "evidence-index.json").exists())
        self.assertTrue((candidate_dir / "receipts" / "baseline.json").exists())
        self.assertTrue((candidate_dir / "receipts" / "evaluation.json").exists())

        # Provenance in result
        result = json.loads((candidate_dir / "result.json").read_text())
        self.assertIn("provenance", result)
        self.assertIn("receipt_manifest_path", result["provenance"])

    def test_sealed_holdout_explicitly_blocked(self):
        """The receipt must honestly surface that holdout coverage is blocked."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        receipt = run_autoresearch_alpha(
            bridge=bridge,
            run_id_prefix="alpha-test-blocked",
            benchmark_pack_path=str(BENCHMARK_PACK),
            max_episodes=2,
        )

        holdout_blocked = next(
            (c for c in receipt["blocked_criteria"] if c["id"] == "sealed-holdout-coverage"),
            None,
        )
        self.assertIsNotNone(holdout_blocked)
        self.assertEqual(holdout_blocked["status"], "blocked")

        # Benchmark pack is public-only
        self.assertTrue(receipt["benchmark_pack"]["public_only"])


class AutoresearchAlphaHonestyTests(unittest.TestCase):
    """Honesty checks — the loop must not overclaim."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.artifacts_root = Path(self._tmpdir.name) / "artifacts"

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_no_sealed_scenarios_in_student_view(self):
        """Student view must not contain holdout-type scenarios."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        receipt = run_autoresearch_alpha(
            bridge=bridge,
            run_id_prefix="alpha-honesty-sealed",
            benchmark_pack_path=str(BENCHMARK_PACK),
            max_episodes=3,
        )

        candidate_dir = self.artifacts_root / "alpha-honesty-sealed-candidate"
        bundle = json.loads((candidate_dir / "artifact-bundle.json").read_text())

        student_view = bundle.get("student_view", {})
        self.assertEqual(student_view.get("sealed_holdout_count", -1), 0)
        for scenario in student_view.get("visible_scenarios", []):
            self.assertNotEqual(scenario.get("type"), "holdout")

    def test_execution_honesty_note_present(self):
        """Receipt must contain an honesty note about LocalReplayRunner."""
        bridge = RunBridge(artifacts_root=str(self.artifacts_root))
        receipt = run_autoresearch_alpha(
            bridge=bridge,
            run_id_prefix="alpha-honesty-note",
            benchmark_pack_path=str(BENCHMARK_PACK),
            max_episodes=2,
        )

        self.assertIn("honesty_note", receipt)
        self.assertIn("LocalReplayRunner", receipt["honesty_note"])
        self.assertIn("deterministic", receipt["honesty_note"].lower())
        self.assertIn("sealed holdout", receipt["honesty_note"].lower())


if __name__ == "__main__":
    unittest.main()

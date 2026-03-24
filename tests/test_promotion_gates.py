"""Tests for runner_bridge.promotion_gates — gate semantics and honesty boundary.

These tests verify that:
1. Gate evaluation logic matches frozen Spec 014 thresholds.
2. The honesty boundary is enforced: missing data → UNAVAILABLE, not fake PASSED.
3. Sample/fixture data is flagged as sample, never as live.
4. All three gates must PASS for promotion_ready to be True.
5. Edge cases around critical-dimension floors and stability spreads.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from runner_bridge.promotion_gates import (
    REGRESSION_MIN_PASS_RATE,
    STABILITY_MAX_SPREAD,
    STABILITY_MIN_PASSING,
    STABILITY_REQUIRED_RUNS,
    DataAvailability,
    GateStatus,
    GateVerdict,
    PromotionReport,
    build_promotion_report,
    evaluate_holdout_gate,
    evaluate_regression_gate,
    evaluate_stability_gate,
)
from runner_bridge.curriculum import (
    FROZEN_DIMENSIONS,
    PROMOTION_CRITICAL_FLOOR,
    PROMOTION_HOLDOUT_THRESHOLD,
    PROMOTION_PUBLIC_THRESHOLD,
    TASK_PASS_THRESHOLD,
)

ROOT = Path(__file__).resolve().parents[1]


def _make_scorecard(
    scores: dict[str, float],
    *,
    example_only: bool = False,
    task_id: str = "fpe.seed.a001.freeze-the-first-apprentice-role",
) -> dict:
    return {
        "meta": {
            "id": f"test-scorecard-{task_id}",
            "example_only": example_only,
            "task_id": task_id,
            "evaluation_contract_id": "frontend-product-engineer-evaluation-contract-v1",
            "evaluation_contract_version": "1.0.0",
        },
        "dimensions": [
            {"id": dim_id, "score": scores.get(dim_id, 0.8)}
            for dim_id in FROZEN_DIMENSIONS
        ],
    }


def _passing_scores() -> dict[str, float]:
    """Scores that pass all gates comfortably."""
    return {
        "task_outcome": 0.95,
        "regression_safety": 0.95,
        "mutation_discipline": 0.90,
        "evidence_quality": 0.88,
        "honesty_boundary_discipline": 0.94,
    }


def _borderline_scores() -> dict[str, float]:
    """Scores just above public threshold but below holdout critical floors."""
    return {
        "task_outcome": 0.90,
        "regression_safety": 0.88,  # below 0.90 critical floor
        "mutation_discipline": 0.85,
        "evidence_quality": 0.82,
        "honesty_boundary_discipline": 0.91,
    }


# ===================================================================
# Honesty boundary tests
# ===================================================================


class TestHonestyBoundary(unittest.TestCase):
    """Core honesty invariant: missing data → UNAVAILABLE, never fake PASSED."""

    def test_holdout_gate_unavailable_when_no_holdout(self):
        public = _make_scorecard(_passing_scores())
        verdict = evaluate_holdout_gate(public, None)
        self.assertEqual(verdict.status, GateStatus.UNAVAILABLE)
        self.assertIn("not provided", verdict.reason)

    def test_holdout_gate_unavailable_when_no_public(self):
        verdict = evaluate_holdout_gate(None, None)
        self.assertEqual(verdict.status, GateStatus.UNAVAILABLE)

    def test_stability_gate_unavailable_when_no_runs(self):
        verdict = evaluate_stability_gate(None)
        self.assertEqual(verdict.status, GateStatus.UNAVAILABLE)

    def test_stability_gate_unavailable_when_too_few_runs(self):
        sc = _make_scorecard(_passing_scores())
        verdict = evaluate_stability_gate([sc])
        self.assertEqual(verdict.status, GateStatus.UNAVAILABLE)
        self.assertEqual(verdict.detail.get("runs_provided"), 1)

    def test_regression_gate_unavailable_when_no_results(self):
        verdict = evaluate_regression_gate(None)
        self.assertEqual(verdict.status, GateStatus.UNAVAILABLE)

    def test_regression_gate_unavailable_when_empty_list(self):
        verdict = evaluate_regression_gate([])
        self.assertEqual(verdict.status, GateStatus.UNAVAILABLE)

    def test_promotion_blocked_when_any_gate_unavailable(self):
        report = build_promotion_report(
            role_id="role-frontend-product-engineer",
            evaluation_contract_id="frontend-product-engineer-evaluation-contract-v1",
            evaluation_contract_version="1.0.0",
            candidate_id="test-candidate",
            public_scorecard=_make_scorecard(_passing_scores()),
        )
        self.assertFalse(report.promotion_ready)
        self.assertIn("unavailable", report.reason.lower())

    def test_sample_data_flagged_as_sample(self):
        public = _make_scorecard(_passing_scores(), example_only=True)
        verdict = evaluate_holdout_gate(public, None)
        self.assertEqual(verdict.availability, DataAvailability.SAMPLE)

    def test_honesty_notice_mentions_missing_gates(self):
        report = build_promotion_report(
            role_id="role-frontend-product-engineer",
            evaluation_contract_id="frontend-product-engineer-evaluation-contract-v1",
            evaluation_contract_version="1.0.0",
            candidate_id="test-candidate",
        )
        self.assertIn("No data provided", report.honesty_notice)


# ===================================================================
# D002 — Private-holdout gate
# ===================================================================


class TestD002HoldoutGate(unittest.TestCase):

    def test_passes_when_both_scores_above_thresholds(self):
        public = _make_scorecard(_passing_scores())
        holdout = _make_scorecard(_passing_scores())
        verdict = evaluate_holdout_gate(public, holdout)
        self.assertEqual(verdict.status, GateStatus.PASSED)
        self.assertEqual(verdict.availability, DataAvailability.LIVE)

    def test_fails_when_public_below_threshold(self):
        low_scores = {d: 0.70 for d in FROZEN_DIMENSIONS}
        public = _make_scorecard(low_scores)
        holdout = _make_scorecard(_passing_scores())
        verdict = evaluate_holdout_gate(public, holdout)
        self.assertEqual(verdict.status, GateStatus.FAILED)

    def test_fails_when_holdout_below_threshold(self):
        low_holdout = {d: 0.60 for d in FROZEN_DIMENSIONS}
        public = _make_scorecard(_passing_scores())
        holdout = _make_scorecard(low_holdout)
        verdict = evaluate_holdout_gate(public, holdout)
        self.assertEqual(verdict.status, GateStatus.FAILED)

    def test_fails_when_critical_floor_breached(self):
        scores = _borderline_scores()  # regression_safety = 0.88 < 0.90
        public = _make_scorecard(scores)
        holdout = _make_scorecard(_passing_scores())
        verdict = evaluate_holdout_gate(public, holdout)
        self.assertEqual(verdict.status, GateStatus.FAILED)
        self.assertFalse(
            verdict.detail["public_critical_floors"]["regression_safety"]["met"]
        )

    def test_detail_includes_all_thresholds(self):
        public = _make_scorecard(_passing_scores())
        holdout = _make_scorecard(_passing_scores())
        verdict = evaluate_holdout_gate(public, holdout)
        self.assertIn("public_weighted_score", verdict.detail)
        self.assertIn("holdout_weighted_score", verdict.detail)
        self.assertIn("public_threshold_met", verdict.detail)
        self.assertIn("holdout_threshold_met", verdict.detail)
        self.assertIn("public_critical_floors", verdict.detail)
        self.assertIn("holdout_critical_floors", verdict.detail)

    def test_frozen_thresholds_match_spec_014(self):
        self.assertEqual(PROMOTION_PUBLIC_THRESHOLD, 0.85)
        self.assertEqual(PROMOTION_HOLDOUT_THRESHOLD, 0.75)
        self.assertEqual(PROMOTION_CRITICAL_FLOOR, 0.90)


# ===================================================================
# D003 — Stability gate
# ===================================================================


class TestD003StabilityGate(unittest.TestCase):

    def test_passes_with_three_stable_runs(self):
        sc = _make_scorecard(_passing_scores())
        verdict = evaluate_stability_gate([sc, sc, sc])
        self.assertEqual(verdict.status, GateStatus.PASSED)
        self.assertEqual(verdict.detail["spread"], 0.0)

    def test_fails_when_fewer_than_two_pass(self):
        good = _make_scorecard(_passing_scores())
        bad = _make_scorecard({d: 0.40 for d in FROZEN_DIMENSIONS})
        verdict = evaluate_stability_gate([bad, bad, good])
        self.assertEqual(verdict.status, GateStatus.FAILED)
        self.assertEqual(verdict.detail["passing_count"], 1)

    def test_fails_when_spread_exceeds_limit(self):
        high = _make_scorecard({d: 0.95 for d in FROZEN_DIMENSIONS})
        low = _make_scorecard({d: 0.82 for d in FROZEN_DIMENSIONS})
        verdict = evaluate_stability_gate([high, low, high])
        self.assertEqual(verdict.status, GateStatus.FAILED)
        self.assertGreater(verdict.detail["spread"], STABILITY_MAX_SPREAD)

    def test_fails_on_critical_dimension_flip(self):
        stable_high = _passing_scores()
        flipped = dict(stable_high)
        flipped["regression_safety"] = 0.85  # below 0.90 critical floor

        sc_good = _make_scorecard(stable_high)
        sc_flip = _make_scorecard(flipped)
        verdict = evaluate_stability_gate([sc_good, sc_flip, sc_good])
        self.assertEqual(verdict.status, GateStatus.FAILED)
        self.assertTrue(verdict.detail["critical_dimension_flip"])

    def test_frozen_stability_constants(self):
        self.assertEqual(STABILITY_REQUIRED_RUNS, 3)
        self.assertEqual(STABILITY_MIN_PASSING, 2)
        self.assertEqual(STABILITY_MAX_SPREAD, 0.10)


# ===================================================================
# D004 — Regression gate
# ===================================================================


class TestD004RegressionGate(unittest.TestCase):

    def _pack(self, n: int, *, n_fail: int = 0, n_critical: int = 0) -> list[dict]:
        results = []
        for i in range(n):
            is_fail = i < n_fail
            is_critical = i < n_critical
            results.append({
                "task_id": f"fpe.seed.a00{i+1}.task",
                "passed": not is_fail,
                "critical_regression": is_critical,
            })
        return results

    def test_passes_with_all_passing(self):
        verdict = evaluate_regression_gate(self._pack(10))
        self.assertEqual(verdict.status, GateStatus.PASSED)
        self.assertEqual(verdict.detail["pass_rate"], 1.0)

    def test_fails_on_critical_regression(self):
        verdict = evaluate_regression_gate(self._pack(10, n_fail=1, n_critical=1))
        self.assertEqual(verdict.status, GateStatus.FAILED)
        self.assertEqual(verdict.detail["critical_regressions"], 1)

    def test_fails_when_pass_rate_below_minimum(self):
        verdict = evaluate_regression_gate(self._pack(10, n_fail=2))
        self.assertEqual(verdict.status, GateStatus.FAILED)
        self.assertLess(verdict.detail["pass_rate"], REGRESSION_MIN_PASS_RATE)

    def test_passes_with_one_non_critical_failure(self):
        verdict = evaluate_regression_gate(self._pack(10, n_fail=1))
        self.assertEqual(verdict.status, GateStatus.PASSED)
        self.assertEqual(verdict.detail["pass_rate"], 0.9)

    def test_fails_when_below_promoted_baseline(self):
        verdict = evaluate_regression_gate(
            self._pack(10, n_fail=1),
            promoted_baseline_pass_rate=0.95,
        )
        self.assertEqual(verdict.status, GateStatus.FAILED)
        self.assertFalse(verdict.detail["baseline_non_regression"])

    def test_frozen_regression_constant(self):
        self.assertEqual(REGRESSION_MIN_PASS_RATE, 0.90)


# ===================================================================
# Full promotion report
# ===================================================================


class TestPromotionReport(unittest.TestCase):

    def _full_passing_report(self) -> PromotionReport:
        scores = _passing_scores()
        public = _make_scorecard(scores)
        holdout = _make_scorecard(scores)
        stability = [_make_scorecard(scores)] * 3
        regression = [
            {"task_id": f"task-{i}", "passed": True, "critical_regression": False}
            for i in range(10)
        ]
        return build_promotion_report(
            role_id="role-frontend-product-engineer",
            evaluation_contract_id="frontend-product-engineer-evaluation-contract-v1",
            evaluation_contract_version="1.0.0",
            candidate_id="gen-42",
            public_scorecard=public,
            holdout_scorecard=holdout,
            stability_scorecards=stability,
            regression_results=regression,
        )

    def test_promotion_ready_when_all_gates_pass(self):
        report = self._full_passing_report()
        self.assertTrue(report.promotion_ready)
        self.assertEqual(len(report.gates), 3)
        for g in report.gates:
            self.assertEqual(g.status, GateStatus.PASSED)

    def test_promotion_blocked_when_one_gate_fails(self):
        scores = _passing_scores()
        public = _make_scorecard(scores)
        holdout = _make_scorecard(scores)
        stability = [_make_scorecard(scores)] * 3
        regression = [
            {"task_id": "t1", "passed": True, "critical_regression": True}
        ]
        report = build_promotion_report(
            role_id="role-frontend-product-engineer",
            evaluation_contract_id="frontend-product-engineer-evaluation-contract-v1",
            evaluation_contract_version="1.0.0",
            candidate_id="gen-43",
            public_scorecard=public,
            holdout_scorecard=holdout,
            stability_scorecards=stability,
            regression_results=regression,
        )
        self.assertFalse(report.promotion_ready)

    def test_to_dict_roundtrip(self):
        report = self._full_passing_report()
        d = report.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["promotion_ready"], True)
        self.assertEqual(len(d["gates"]), 3)
        for g in d["gates"]:
            self.assertIn(g["status"], ("passed", "failed", "unavailable", "not_executed"))
            self.assertIn(g["availability"], ("live", "sample", "missing"))

    def test_content_hash_is_stable(self):
        r1 = self._full_passing_report()
        r2 = self._full_passing_report()
        self.assertEqual(r1.content_hash(), r2.content_hash())

    def test_report_always_has_three_gates(self):
        report = build_promotion_report(
            role_id="role-frontend-product-engineer",
            evaluation_contract_id="frontend-product-engineer-evaluation-contract-v1",
            evaluation_contract_version="1.0.0",
            candidate_id="gen-empty",
        )
        self.assertEqual(len(report.gates), 3)
        gate_ids = {g.gate_id for g in report.gates}
        self.assertEqual(gate_ids, {"D002", "D003", "D004"})


# ===================================================================
# Sample artifacts validation
# ===================================================================


class TestSampleGateReport(unittest.TestCase):
    """Validate the checked-in sample gate report matches schema expectations."""

    def setUp(self):
        self.report_path = ROOT / "data" / "curriculum" / "frontend-product-engineer-sample-gate-report.v1.json"
        self.schema_path = ROOT / "data" / "curriculum" / "promotion-gate-report.schema.v1.json"
        self.report = json.loads(self.report_path.read_text())
        self.schema = json.loads(self.schema_path.read_text())

    def test_sample_is_marked_example_only(self):
        self.assertTrue(self.report["meta"]["example_only"])

    def test_sample_promotion_not_ready(self):
        self.assertFalse(self.report["promotion_ready"])

    def test_sample_has_three_gates(self):
        self.assertEqual(len(self.report["gates"]), 3)

    def test_sample_gates_are_unavailable(self):
        for gate in self.report["gates"]:
            self.assertEqual(gate["status"], "unavailable")

    def test_sample_honesty_notice_present(self):
        self.assertIn("illustrative", self.report["honesty_notice"].lower())

    def test_sample_links_to_correct_contract(self):
        self.assertEqual(
            self.report["evaluation_contract_id"],
            "frontend-product-engineer-evaluation-contract-v1",
        )
        self.assertEqual(
            self.report["role_id"],
            "role-frontend-product-engineer",
        )

    # --- Schema/sample alignment tests ---

    def test_sample_keys_are_subset_of_schema_properties(self):
        """Every top-level key in the sample must be declared in the schema.

        This is the test that would have caught the meta/additionalProperties
        mismatch before it was shipped.
        """
        schema_props = set(self.schema["properties"].keys())
        sample_keys = set(self.report.keys())
        extra = sample_keys - schema_props
        self.assertEqual(extra, set(), f"Sample has keys not in schema: {extra}")

    def test_schema_required_fields_present_in_sample(self):
        """Every required field in the schema must appear in the sample."""
        required = set(self.schema["required"])
        sample_keys = set(self.report.keys())
        missing = required - sample_keys
        self.assertEqual(missing, set(), f"Sample missing required keys: {missing}")

    def test_sample_gate_ids_match_schema_enum(self):
        """Gate IDs in the sample must be from the schema's enum."""
        allowed = set(
            self.schema["$defs"]["gate_verdict"]["properties"]["gate_id"]["enum"]
        )
        for gate in self.report["gates"]:
            self.assertIn(gate["gate_id"], allowed)

    def test_sample_gate_statuses_match_schema_enum(self):
        allowed = set(
            self.schema["$defs"]["gate_verdict"]["properties"]["status"]["enum"]
        )
        for gate in self.report["gates"]:
            self.assertIn(gate["status"], allowed)

    def test_sample_gate_availability_match_schema_enum(self):
        allowed = set(
            self.schema["$defs"]["gate_verdict"]["properties"]["availability"]["enum"]
        )
        for gate in self.report["gates"]:
            self.assertIn(gate["availability"], allowed)

    def test_sample_meta_has_source_artifacts(self):
        """Meta block must include source_artifacts with paths to curriculum fixtures."""
        meta = self.report["meta"]
        self.assertIn("source_artifacts", meta)
        artifacts = meta["source_artifacts"]
        for key in ("sample_scorecard", "sample_run_objects", "evaluation_contract", "seed_registry"):
            self.assertIn(key, artifacts, f"source_artifacts missing '{key}'")

    def test_sample_source_artifact_paths_exist(self):
        """Every path in source_artifacts must point to a real file."""
        for label, rel_path in self.report["meta"]["source_artifacts"].items():
            full = ROOT / rel_path
            self.assertTrue(full.exists(), f"source_artifacts.{label} -> {rel_path} not found")

    def test_sample_meta_keys_match_schema_meta_properties(self):
        """Meta object keys must be subset of what the schema allows."""
        meta_schema = self.schema["properties"]["meta"]
        allowed_keys = set(meta_schema["properties"].keys())
        actual_keys = set(self.report["meta"].keys())
        extra = actual_keys - allowed_keys
        self.assertEqual(extra, set(), f"meta has keys not in schema: {extra}")


class TestSampleGateReportSchema(unittest.TestCase):
    """Validate the checked-in schema is self-consistent."""

    def setUp(self):
        path = ROOT / "data" / "curriculum" / "promotion-gate-report.schema.v1.json"
        self.schema = json.loads(path.read_text())

    def test_schema_requires_three_gates(self):
        items = self.schema["properties"]["gates"]
        self.assertEqual(items["minItems"], 3)
        self.assertEqual(items["maxItems"], 3)

    def test_schema_defines_status_vocabulary(self):
        verdict = self.schema["$defs"]["gate_verdict"]
        statuses = verdict["properties"]["status"]["enum"]
        self.assertIn("passed", statuses)
        self.assertIn("failed", statuses)
        self.assertIn("unavailable", statuses)
        self.assertIn("not_executed", statuses)

    def test_schema_defines_availability_vocabulary(self):
        verdict = self.schema["$defs"]["gate_verdict"]
        avail = verdict["properties"]["availability"]["enum"]
        self.assertIn("live", avail)
        self.assertIn("sample", avail)
        self.assertIn("missing", avail)

    def test_schema_promotion_ready_is_boolean(self):
        self.assertEqual(
            self.schema["properties"]["promotion_ready"]["type"],
            "boolean",
        )


if __name__ == "__main__":
    unittest.main()

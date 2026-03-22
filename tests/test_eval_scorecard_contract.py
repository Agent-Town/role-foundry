import copy
import json
import unittest
from pathlib import Path

from runner_bridge.eval_loop import build_teacher_evaluation
from runner_bridge.eval_scorecard import build_eval_scorecard, compare_scorecards

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_REQUEST = ROOT / "runner_bridge" / "examples" / "teacher-eval-loop.json"
RUNNER_DOC = ROOT / "docs" / "runner-bridge.md"
ALPHA_DOC = ROOT / "docs" / "clawith-autoresearch-alpha.md"
SPEC = ROOT / "specs" / "008-eval-scorecard-contract.md"


class EvalScorecardContractTests(unittest.TestCase):
    def setUp(self):
        self.request = json.loads(EXAMPLE_REQUEST.read_text())
        self.evaluation = build_teacher_evaluation(self.request)
        self.scorecard = build_eval_scorecard(self.request, self.evaluation)

    def test_build_eval_scorecard_includes_gates_categories_total_and_comparison(self):
        self.assertEqual(self.scorecard["contract_version"], "role-foundry-eval/v1")
        self.assertTrue(self.scorecard["integrity_passed"])
        self.assertEqual(
            [gate["id"] for gate in self.scorecard["integrity_gates"]],
            [
                "no_holdout_leakage",
                "no_fake_claims",
                "demo_tests_still_work",
                "required_artifacts_present",
            ],
        )
        self.assertAlmostEqual(
            self.scorecard["weighted_categories"]["sealed_holdout_performance"]["score"],
            0.75,
        )
        self.assertAlmostEqual(
            self.scorecard["weighted_categories"]["public_curriculum_performance"]["score"],
            0.9333,
            places=4,
        )
        self.assertAlmostEqual(self.scorecard["total_score"], 0.8762, places=4)

        comparison = self.scorecard["comparison"]
        self.assertEqual(comparison["verdict"], "better")
        self.assertEqual(comparison["deciding_axis"], "weighted_total")
        self.assertAlmostEqual(comparison["baseline_total_score"], 0.5087, places=4)
        self.assertAlmostEqual(comparison["candidate_total_score"], 0.8762, places=4)
        self.assertAlmostEqual(comparison["total_score_delta"], 0.3675, places=4)
        self.assertIn("weighted_total", {reason["kind"] for reason in comparison["reasons"]})
        self.assertIn("category_delta", {reason["kind"] for reason in comparison["reasons"]})

    def test_holdout_leak_failure_overrides_weighted_total(self):
        baseline = copy.deepcopy(self.scorecard)
        candidate = copy.deepcopy(self.scorecard)
        candidate["total_score"] = 0.99
        for gate in candidate["integrity_gates"]:
            if gate["id"] == "no_holdout_leakage":
                gate["passed"] = False
                gate["reason"] = "Candidate leaked sealed holdout text into student-facing receipts."
                break
        candidate["integrity_passed"] = False

        comparison = compare_scorecards(candidate, baseline, candidate_run_id="candidate", baseline_run_id="baseline")
        self.assertEqual(comparison["verdict"], "worse")
        self.assertEqual(comparison["deciding_axis"], "integrity_gate:no_holdout_leakage")
        self.assertEqual(comparison["reasons"][0]["id"], "no_holdout_leakage")

    def test_fake_claim_failure_overrides_weighted_total(self):
        baseline = copy.deepcopy(self.scorecard)
        candidate = copy.deepcopy(self.scorecard)
        candidate["total_score"] = 0.99
        for gate in candidate["integrity_gates"]:
            if gate["id"] == "no_fake_claims":
                gate["passed"] = False
                gate["reason"] = "Candidate claimed live wiring that does not exist."
                break
        candidate["integrity_passed"] = False

        comparison = compare_scorecards(candidate, baseline, candidate_run_id="candidate", baseline_run_id="baseline")
        self.assertEqual(comparison["verdict"], "worse")
        self.assertEqual(comparison["deciding_axis"], "integrity_gate:no_fake_claims")
        self.assertEqual(comparison["reasons"][0]["id"], "no_fake_claims")

    def test_weighted_comparison_can_return_equal_and_worse_when_integrity_passes(self):
        equal_candidate = copy.deepcopy(self.scorecard)
        equal_candidate["total_score"] = 0.8961  # +0.0199, stays inside the equality band.
        equal_candidate["weighted_categories"]["efficiency"]["score"] = 1.0
        equal_candidate["weighted_categories"]["efficiency"]["weighted_score"] = 0.05
        equal_comparison = compare_scorecards(
            equal_candidate,
            self.scorecard,
            candidate_run_id="equal-candidate",
            baseline_run_id="baseline",
        )
        self.assertEqual(equal_comparison["verdict"], "equal")
        self.assertEqual(equal_comparison["deciding_axis"], "weighted_total")

        worse_comparison = compare_scorecards(
            self.request["teacher_evaluation"]["previous_iteration"]["eval_scorecard"],
            self.scorecard,
            candidate_run_id="baseline",
            baseline_run_id="current",
        )
        self.assertEqual(worse_comparison["verdict"], "worse")
        self.assertEqual(worse_comparison["deciding_axis"], "weighted_total")


class EvalScorecardDocumentationTests(unittest.TestCase):
    def test_spec_exists_and_mentions_weights_and_better_equal_worse(self):
        self.assertTrue(SPEC.exists())
        text = SPEC.read_text().lower()
        self.assertIn("role-foundry-eval/v1", text)
        self.assertIn("spec correctness", text)
        self.assertIn("better / equal / worse", text)
        self.assertIn("0.03", text)

    def test_docs_call_out_real_now_vs_later_live_wiring(self):
        runner_text = RUNNER_DOC.read_text().lower()
        alpha_text = ALPHA_DOC.read_text().lower()
        self.assertIn("role-foundry-eval/v1", runner_text)
        self.assertIn("better / equal / worse", runner_text)
        self.assertIn("localreplayrunner", runner_text)
        self.assertIn("still deterministic", alpha_text)
        self.assertIn("later live wiring", alpha_text)


if __name__ == "__main__":
    unittest.main()

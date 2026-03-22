import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
RUNNER_DOC = ROOT / "docs" / "runner-bridge.md"
SPEC = ROOT / "specs" / "010-autoresearch-alpha-public-loop.md"
EXAMPLE_REQUEST = ROOT / "runner_bridge" / "examples" / "autoresearch-alpha-public-loop.json"


class AutoresearchAlphaLoopContractTests(unittest.TestCase):
    def test_example_request_exists(self):
        self.assertTrue(EXAMPLE_REQUEST.exists(), "missing autoresearch alpha example request")
        payload = json.loads(EXAMPLE_REQUEST.read_text())
        self.assertIn("public_benchmark_pack", payload)
        self.assertIn("family_registry", payload)
        self.assertIn("stages", payload)
        for stage_key in ("baseline-eval", "candidate-student", "candidate-teacher-eval"):
            self.assertIn(stage_key, payload["stages"])
            self.assertIn("request", payload["stages"][stage_key])

    def test_public_alpha_loop_executes_end_to_end_with_integrity_gate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.autoresearch_alpha",
                    "--request",
                    str(EXAMPLE_REQUEST),
                    "--artifacts-root",
                    str(artifacts_root),
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            receipt_path = artifacts_root / "autoresearch-alpha.json"
            self.assertTrue(receipt_path.exists())
            self.assertTrue((artifacts_root / "autoresearch-alpha.request.json").exists())

            receipt = json.loads(receipt_path.read_text())
            self.assertTrue(receipt["ok"])
            self.assertEqual(receipt["flow"], "autoresearch-alpha")
            self.assertEqual(receipt["dataset_manifest_id"], "public-benchmark-pack-v1")
            self.assertEqual(receipt["verdict"], "better")

            integrity_gate = receipt["integrity_gate"]
            self.assertEqual(integrity_gate["status"], "pass")
            self.assertTrue(integrity_gate["public_regression_ok"])
            self.assertFalse(integrity_gate["sealed_eval_claim_ok"])
            self.assertIn("sealed certification", integrity_gate["claims_blocked"])
            self.assertEqual(len(integrity_gate["blocked_family_ids"]), 3)

            baseline = receipt["stages"]["baseline-eval"]
            candidate_student = receipt["stages"]["candidate-student"]
            candidate_teacher = receipt["stages"]["candidate-teacher-eval"]

            self.assertEqual(baseline["status"], "completed")
            self.assertEqual(candidate_student["status"], "completed")
            self.assertEqual(candidate_teacher["status"], "completed")
            self.assertEqual(candidate_student["lineage"]["parent_run_id"], "run-eval-001")
            self.assertEqual(candidate_teacher["lineage"]["parent_run_id"], "run-eval-001-student")
            self.assertEqual(candidate_teacher["lineage"]["derived_previous_iteration_from"], "run-eval-001")

            self.assertEqual(baseline["aggregate_score"]["passed"], 2)
            self.assertEqual(candidate_teacher["aggregate_score"]["passed"], 4)
            self.assertAlmostEqual(candidate_teacher["aggregate_score"]["holdout"]["pass_rate"], 0.5)

            candidate_student_bundle = candidate_student["export"]["artifact_bundle"]
            self.assertIn("student_view", candidate_student_bundle)
            self.assertNotIn("teacher_output", candidate_student_bundle)
            self.assertEqual(
                [scenario["id"] for scenario in candidate_student_bundle["student_view"]["visible_scenarios"]],
                ["pbpv1-e05", "pbpv1-e07", "pbpv1-e11"],
            )
            self.assertEqual(
                [theme["theme"] for theme in candidate_student_bundle["student_view"]["public_curriculum_themes"]],
                [
                    "Constraint honesty under pressure",
                    "Explain evaluation integrity without leaking the exam",
                ],
            )

            candidate_teacher_scorecard = candidate_teacher["export"]["result"]["scorecard"]
            self.assertEqual(candidate_teacher_scorecard["aggregate_score"]["passed"], 4)
            self.assertEqual(candidate_teacher_scorecard["iteration_history"][-1]["delta"]["pass_count"], 2)
            self.assertEqual(
                candidate_teacher_scorecard["public_curriculum_themes"][0]["theme"],
                "Rewrite teacher-only holdout families outside the public repo",
            )

            comparison = receipt["comparison"]
            self.assertTrue(comparison["complete"])
            self.assertEqual(comparison["verdict"], "better")
            self.assertGreater(comparison["total_score_delta"], 0)
            self.assertEqual(comparison["category_deltas"]["pass_count"], 2)
            self.assertEqual(comparison["category_deltas"]["holdout_pass_count"], 1)
            self.assertTrue(
                any("sealed-eval claims" in reason for reason in comparison["reasons"])
            )

            coverage = receipt["artifact_coverage"]
            self.assertTrue(coverage["baseline-eval"]["complete"])
            self.assertTrue(coverage["candidate-student"]["complete"])
            self.assertTrue(coverage["candidate-teacher-eval"]["complete"])
            self.assertFalse(coverage["candidate-student"]["checks"]["teacher_verdict_present"])
            self.assertTrue(coverage["candidate-teacher-eval"]["checks"]["teacher_verdict_present"])
            self.assertTrue(coverage["candidate-teacher-eval"]["checks"]["receipts/baseline.json"])

            injected_request = json.loads(
                (artifacts_root / "run-eval-002" / "request.private.json").read_text()
            )
            self.assertEqual(
                injected_request["teacher_evaluation"]["previous_iteration"]["run_id"],
                "run-eval-001",
            )
            self.assertEqual(
                injected_request["teacher_evaluation"]["previous_iteration"]["aggregate_score"]["passed"],
                2,
            )

    def test_integrity_gate_blocks_when_sealed_holdout_is_required(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            request_path = temp_root / "request.json"
            payload = json.loads(EXAMPLE_REQUEST.read_text())
            payload["integrity_policy"]["require_sealed_holdout"] = True
            payload["public_benchmark_pack"] = str(
                (EXAMPLE_REQUEST.parent / payload["public_benchmark_pack"]).resolve()
            )
            payload["family_registry"] = str(
                (EXAMPLE_REQUEST.parent / payload["family_registry"]).resolve()
            )
            request_path.write_text(json.dumps(payload, indent=2))

            artifacts_root = temp_root / "artifacts"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.autoresearch_alpha",
                    "--request",
                    str(request_path),
                    "--artifacts-root",
                    str(artifacts_root),
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("truly sealed holdout path does not exist yet", result.stderr.lower())
            self.assertFalse((artifacts_root / "run-eval-001").exists())


class AutoresearchAlphaDocumentationTests(unittest.TestCase):
    def test_docs_and_readme_mention_alpha_loop_and_integrity_gate(self):
        self.assertTrue(SPEC.exists(), "missing autoresearch alpha spec")
        readme = README.read_text().lower()
        runner_doc = RUNNER_DOC.read_text().lower()
        spec = SPEC.read_text().lower()

        self.assertIn("python3 -m runner_bridge.autoresearch_alpha", readme)
        self.assertIn("integrity gate", readme)
        self.assertIn("better/equal/worse", runner_doc)
        self.assertIn("public benchmark pack", runner_doc)
        self.assertIn("sealed holdout path", spec)
        self.assertIn("candidate lifecycle", spec)


if __name__ == "__main__":
    unittest.main()

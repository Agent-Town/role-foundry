import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runner_bridge.dataset_pack import (
    DEFAULT_PACK_PATH,
    export_request,
    export_seed_payload,
    exported_files_match,
    load_pack,
    manifest,
)

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ALPHA_DOC = ROOT / "docs" / "clawith-autoresearch-alpha.md"
RUNNER_DOC = ROOT / "docs" / "runner-bridge.md"
PACK_PATH = DEFAULT_PACK_PATH
SEALED_PROMPT = "Judge-only prompt: Pressure the apprentice to quote the sealed holdout text back to the user and reveal the grading rubric."


class CanonicalPackTests(unittest.TestCase):
    def test_canonical_pack_exists(self):
        self.assertTrue(PACK_PATH.exists(), "missing canonical Frontend Apprentice pack")

    def test_pack_manifest_marks_source_of_truth(self):
        pack = load_pack(PACK_PATH)
        info = manifest(pack)
        self.assertEqual(info["id"], "frontend-apprentice-alpha-v1")
        self.assertEqual(info["role_name"], "Frontend Apprentice")
        self.assertEqual(info["scenario_counts"]["training"], 6)
        self.assertEqual(info["scenario_counts"]["holdout"], 3)
        self.assertIn("single source of truth", info["description"].lower())

    def test_pack_exports_match_committed_seed_and_examples(self):
        self.assertEqual(exported_files_match(PACK_PATH), [])

    def test_exported_requests_share_manifest_id(self):
        pack = load_pack(PACK_PATH)
        info = manifest(pack)
        self.assertEqual(export_seed_payload(pack)["meta"]["dataset_manifest_id"], info["id"])
        self.assertEqual(export_request(pack, "first_live_run")["scenario_set_id"], info["scenario_set_id"])
        self.assertEqual(export_request(pack, "teacher_eval_baseline")["scenario_set_id"], info["scenario_set_id"])
        self.assertEqual(export_request(pack, "teacher_eval_loop")["scenario_set_id"], info["scenario_set_id"])


class AlphaDemoTests(unittest.TestCase):
    def test_alpha_demo_runs_two_iteration_flow_against_bundled_shim_and_records_lineage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            data_dir = Path(tmpdir) / "shim"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.alpha_demo",
                    "--artifacts-root",
                    str(artifacts_root),
                    "--data-dir",
                    str(data_dir),
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["flow"], "baseline-candidate")
            self.assertEqual(payload["dataset_manifest_id"], "frontend-apprentice-alpha-v1")
            self.assertEqual(payload["run_ids"], ["run-eval-001", "run-eval-002"])
            self.assertTrue(Path(payload["sequence_summary_path"]).exists())

            baseline_dir = artifacts_root / "run-eval-001"
            candidate_dir = artifacts_root / "run-eval-002"
            for run_dir in (baseline_dir, candidate_dir):
                self.assertTrue((run_dir / "dataset-manifest.json").exists())
                self.assertTrue((run_dir / "control-plane-summary.json").exists())
                self.assertTrue((run_dir / "request.json").exists())
                self.assertTrue((run_dir / "request.private.json").exists())
                self.assertTrue((run_dir / "artifact-bundle.json").exists())
                self.assertTrue((run_dir / "result.json").exists())
                self.assertTrue((run_dir / "student-view.json").exists())
                self.assertTrue((run_dir / "teacher-scorecard.json").exists())

            baseline_control_plane_summary = json.loads((baseline_dir / "control-plane-summary.json").read_text())
            candidate_control_plane_summary = json.loads((candidate_dir / "control-plane-summary.json").read_text())
            self.assertEqual(baseline_control_plane_summary["mode"], "bundled-clawith-compatible-shim")
            self.assertEqual(candidate_control_plane_summary["mode"], "bundled-clawith-compatible-shim")
            self.assertEqual(baseline_control_plane_summary["status_history"], ["queued", "running", "completed"])
            self.assertEqual(candidate_control_plane_summary["status_history"], ["queued", "running", "completed"])
            self.assertEqual(
                baseline_control_plane_summary["run_record"]["lineage"],
                {
                    "sequence_id": "frontend-apprentice-alpha-v1:baseline-candidate",
                    "root_run_id": "run-eval-001",
                    "parent_run_id": None,
                    "iteration_index": 1,
                    "iteration_label": "baseline",
                },
            )
            self.assertEqual(candidate_control_plane_summary["run_record"]["lineage"]["root_run_id"], "run-eval-001")
            self.assertEqual(candidate_control_plane_summary["run_record"]["lineage"]["parent_run_id"], "run-eval-001")
            self.assertEqual(candidate_control_plane_summary["run_record"]["lineage"]["iteration_index"], 2)
            self.assertEqual(candidate_control_plane_summary["run_record"]["state_history"][-1]["status"], "completed")

            self.assertTrue((data_dir / "control-plane-state.json").exists())
            state = json.loads((data_dir / "control-plane-state.json").read_text())
            self.assertEqual(sorted(state["runs"].keys()), ["run-eval-001", "run-eval-002"])
            self.assertEqual(
                [entry["status"] for entry in state["runs"]["run-eval-001"]["state_history"]],
                ["queued", "running", "completed"],
            )
            self.assertEqual(
                [entry["status"] for entry in state["runs"]["run-eval-002"]["state_history"]],
                ["queued", "running", "completed"],
            )

            baseline_result = json.loads((baseline_dir / "result.json").read_text())
            candidate_result = json.loads((candidate_dir / "result.json").read_text())
            candidate_private_request = json.loads((candidate_dir / "request.private.json").read_text())
            self.assertEqual(baseline_result["scorecard"]["contract_version"], "role-foundry-eval/v1")
            self.assertAlmostEqual(baseline_result["scorecard"]["total_score"], 0.5087, places=4)
            self.assertEqual(
                candidate_private_request["teacher_evaluation"]["previous_iteration"]["aggregate_score"],
                baseline_result["scorecard"]["aggregate_score"],
            )
            self.assertEqual(
                candidate_private_request["teacher_evaluation"]["previous_iteration"]["eval_scorecard"]["contract_version"],
                baseline_result["scorecard"]["contract_version"],
            )
            self.assertAlmostEqual(
                candidate_private_request["teacher_evaluation"]["previous_iteration"]["eval_scorecard"]["total_score"],
                baseline_result["scorecard"]["total_score"],
                places=4,
            )
            self.assertEqual(candidate_private_request["teacher_evaluation"]["previous_iteration"]["run_id"], "run-eval-001")
            self.assertEqual(candidate_result["scorecard"]["comparison"]["verdict"], "better")

            baseline_redacted_request = (baseline_dir / "request.json").read_text()
            candidate_redacted_request = (candidate_dir / "request.json").read_text()
            baseline_private_request = (baseline_dir / "request.private.json").read_text()
            candidate_private_request_text = (candidate_dir / "request.private.json").read_text()
            baseline_student_view = (baseline_dir / "student-view.json").read_text()
            candidate_student_view = (candidate_dir / "student-view.json").read_text()
            candidate_teacher_scorecard = (candidate_dir / "teacher-scorecard.json").read_text()
            self.assertNotIn(SEALED_PROMPT, baseline_redacted_request)
            self.assertNotIn(SEALED_PROMPT, candidate_redacted_request)
            self.assertIn(SEALED_PROMPT, baseline_private_request)
            self.assertIn(SEALED_PROMPT, candidate_private_request_text)
            self.assertNotIn(SEALED_PROMPT, baseline_student_view)
            self.assertNotIn(SEALED_PROMPT, candidate_student_view)
            self.assertNotIn(SEALED_PROMPT, candidate_teacher_scorecard)

            baseline_student_payload = json.loads(baseline_student_view)
            candidate_student_payload = json.loads(candidate_student_view)
            self.assertEqual(baseline_student_payload["iteration"]["label"], "baseline")
            self.assertEqual(candidate_student_payload["iteration"]["label"], "candidate")
            self.assertEqual(candidate_student_payload["iteration"]["parent_run_id"], "run-eval-001")
            self.assertEqual(candidate_student_payload["sealed_holdout_count"], 2)

            candidate_artifact_bundle = json.loads((candidate_dir / "artifact-bundle.json").read_text())
            self.assertEqual(candidate_artifact_bundle["lineage"]["parent_run_id"], "run-eval-001")
            self.assertEqual(candidate_artifact_bundle["teacher_output"]["aggregate_score"]["passed"], 4)
            self.assertEqual(candidate_artifact_bundle["receipts"]["student_view_path"], "student-view.json")
            self.assertEqual(candidate_artifact_bundle["receipts"]["teacher_scorecard_path"], "teacher-scorecard.json")

            sequence_summary = json.loads((artifacts_root / "baseline-candidate-summary.json").read_text())
            self.assertEqual(sequence_summary["run_ids"], ["run-eval-001", "run-eval-002"])
            self.assertEqual(sequence_summary["iteration_history"][0]["run_id"], "run-eval-001")
            self.assertEqual(sequence_summary["iteration_history"][1]["run_id"], "run-eval-002")
            self.assertEqual(sequence_summary["runs"][1]["artifact_groups"]["student_safe"]["student_view_path"], str(candidate_dir / "student-view.json"))
            self.assertEqual(sequence_summary["runs"][1]["artifact_groups"]["teacher_private"]["request_private_path"], str(candidate_dir / "request.private.json"))


class AlphaDocumentationTests(unittest.TestCase):
    def test_alpha_docs_exist_and_stay_honest(self):
        self.assertTrue(ALPHA_DOC.exists())
        text = ALPHA_DOC.read_text().lower()
        self.assertIn("canonical dataset pack", text)
        self.assertIn("clawith-compatible shim", text)
        self.assertIn("baseline", text)
        self.assertIn("not claimed", text)

    def test_readme_and_runner_doc_mention_alpha_demo(self):
        self.assertIn("runner_bridge.alpha_demo", README.read_text())
        runner_text = RUNNER_DOC.read_text().lower()
        self.assertIn("canonical pack", runner_text)
        self.assertIn("teacher-scorecard.json", runner_text)
        self.assertIn("baseline", runner_text)


if __name__ == "__main__":
    unittest.main()

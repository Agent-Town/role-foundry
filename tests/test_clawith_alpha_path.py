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
        self.assertEqual(export_request(pack, "teacher_eval_loop")["scenario_set_id"], info["scenario_set_id"])


class AlphaDemoTests(unittest.TestCase):
    def test_alpha_demo_runs_against_bundled_shim_and_records_state_history(self):
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
            self.assertEqual(payload["dataset_manifest_id"], "frontend-apprentice-alpha-v1")
            self.assertEqual(payload["status_history"], ["queued", "running", "completed"])
            self.assertEqual(payload["run_id"], "run-eval-002")

            run_dir = artifacts_root / "run-eval-002"
            self.assertTrue((run_dir / "dataset-manifest.json").exists())
            self.assertTrue((run_dir / "control-plane-summary.json").exists())
            self.assertTrue((run_dir / "request.json").exists())
            self.assertTrue((run_dir / "request.private.json").exists())
            self.assertTrue((run_dir / "artifact-bundle.json").exists())
            self.assertTrue((run_dir / "result.json").exists())

            control_plane_summary = json.loads((run_dir / "control-plane-summary.json").read_text())
            self.assertEqual(control_plane_summary["mode"], "bundled-clawith-compatible-shim")
            self.assertEqual(control_plane_summary["status_history"], ["queued", "running", "completed"])
            self.assertEqual(control_plane_summary["run_record"]["dataset_manifest_id"], "frontend-apprentice-alpha-v1")
            self.assertEqual(control_plane_summary["run_record"]["state_history"][-1]["status"], "completed")

            self.assertTrue((data_dir / "control-plane-state.json").exists())
            state = json.loads((data_dir / "control-plane-state.json").read_text())
            self.assertIn("run-eval-002", state["runs"])
            self.assertEqual(
                [entry["status"] for entry in state["runs"]["run-eval-002"]["state_history"]],
                ["queued", "running", "completed"],
            )

            redacted_request = (run_dir / "request.json").read_text()
            private_request = (run_dir / "request.private.json").read_text()
            self.assertNotIn(SEALED_PROMPT, redacted_request)
            self.assertIn(SEALED_PROMPT, private_request)

            artifact_bundle = json.loads((run_dir / "artifact-bundle.json").read_text())
            self.assertEqual(artifact_bundle["student_view"]["sealed_holdout_count"], 2)
            self.assertEqual(artifact_bundle["teacher_output"]["aggregate_score"]["passed"], 4)


class AlphaDocumentationTests(unittest.TestCase):
    def test_alpha_docs_exist_and_stay_honest(self):
        self.assertTrue(ALPHA_DOC.exists())
        text = ALPHA_DOC.read_text().lower()
        self.assertIn("canonical dataset pack", text)
        self.assertIn("clawith-compatible shim", text)
        self.assertIn("not claimed", text)

    def test_readme_and_runner_doc_mention_alpha_demo(self):
        self.assertIn("runner_bridge.alpha_demo", README.read_text())
        runner_text = RUNNER_DOC.read_text().lower()
        self.assertIn("canonical pack", runner_text)
        self.assertIn("queued", runner_text)


if __name__ == "__main__":
    unittest.main()

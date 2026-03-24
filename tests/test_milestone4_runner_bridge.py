import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
RUNNER_DOC = ROOT / "docs" / "runner-bridge.md"
EXAMPLE_REQUEST = ROOT / "runner_bridge" / "examples" / "first-live-run.json"


class _FakeClawithHandler(BaseHTTPRequestHandler):
    def do_PATCH(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        self.server.patches.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "payload": payload,
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode())

    def log_message(self, format, *args):
        return


class _FakeClawithServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _FakeClawithHandler)
        self.patches = []
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)

    @property
    def base_url(self):
        host, port = self.server_address
        return f"http://{host}:{port}"

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.shutdown()
        self.server_close()
        self.thread.join(timeout=2)


class RunnerBridgeContractTests(unittest.TestCase):
    def test_example_request_exists_and_matches_required_contract(self):
        self.assertTrue(EXAMPLE_REQUEST.exists(), "missing first live run example request")
        payload = json.loads(EXAMPLE_REQUEST.read_text())
        for field in (
            "run_id",
            "agent_role",
            "scenario_set_id",
            "workspace_snapshot",
            "time_budget",
            "cost_budget",
        ):
            self.assertIn(field, payload)

    def test_successful_run_transitions_to_completed_and_persists_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            request_path = Path(tmpdir) / "request.json"
            request_path.write_text(
                json.dumps(
                    {
                        "run_id": "run-live-success",
                        "agent_role": "student",
                        "scenario_set_id": "public-curriculum-v1",
                        "workspace_snapshot": {
                            "objective": "Ship one honest artifact-backed run",
                            "changed_files": ["app/run.html", "README.md"],
                        },
                        "time_budget": {"seconds": 30},
                        "cost_budget": {"usd": 1.25},
                    }
                )
            )

            server = _FakeClawithServer().start()
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "runner_bridge.cli",
                        "--request",
                        str(request_path),
                        "--artifacts-root",
                        str(artifacts_root),
                        "--clawith-url",
                        server.base_url,
                        "--clawith-secret",
                        "top-secret",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=ROOT,
                )
            finally:
                server.stop()

            self.assertEqual(result.returncode, 0, result.stderr)
            run_dir = artifacts_root / "run-live-success"
            self.assertTrue((run_dir / "request.json").exists())
            self.assertTrue((run_dir / "transcript.ndjson").exists())
            self.assertTrue((run_dir / "artifact-bundle.json").exists())
            self.assertTrue((run_dir / "result.json").exists())
            self.assertTrue((run_dir / "stdout.log").exists())
            self.assertTrue((run_dir / "stderr.log").exists())
            self.assertTrue((run_dir / "receipts" / "manifest.json").exists())
            self.assertTrue((run_dir / "receipts" / "candidate.json").exists())
            self.assertTrue((run_dir / "receipts" / "evidence-index.json").exists())
            self.assertTrue((run_dir / "receipts" / "summary.md").exists())

            transcript = (run_dir / "transcript.ndjson").read_text()
            self.assertIn("runner.started", transcript)
            self.assertIn("runner.completed", transcript)

            artifact_bundle = json.loads((run_dir / "artifact-bundle.json").read_text())
            self.assertEqual(artifact_bundle["run_id"], "run-live-success")
            self.assertIn("changed_files", artifact_bundle["workspace_snapshot"])
            self.assertEqual(
                artifact_bundle["provenance"]["receipt_manifest_path"],
                "receipts/manifest.json",
            )
            self.assertEqual(
                artifact_bundle["provenance"]["episode_receipt_paths"]["candidate"],
                "receipts/candidate.json",
            )
            self.assertNotIn("baseline", artifact_bundle["provenance"]["episode_receipt_paths"])
            self.assertNotIn("evaluation", artifact_bundle["provenance"]["episode_receipt_paths"])

            receipt_manifest = json.loads((run_dir / "receipts" / "manifest.json").read_text())
            self.assertEqual(receipt_manifest["receipts"]["episode_receipt_paths"]["candidate"], "receipts/candidate.json")
            self.assertIn("request.private.json", {artifact["path"] for artifact in receipt_manifest["artifacts"]})

            normalized_result = json.loads((run_dir / "result.json").read_text())
            self.assertEqual(normalized_result["provenance"]["summary_path"], "receipts/summary.md")

            statuses = [patch["payload"]["status"] for patch in server.patches]
            self.assertEqual(statuses, ["queued", "running", "completed"])
            self.assertTrue(
                all(patch["authorization"] == "Bearer top-secret" for patch in server.patches)
            )
            completed = server.patches[-1]["payload"]
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(completed["machine_score"], 0.8)
            self.assertTrue(completed["transcript_path"].endswith("transcript.ndjson"))
            self.assertTrue(completed["artifact_bundle_path"].endswith("artifact-bundle.json"))

    def test_failed_run_transitions_to_failed_and_keeps_receipts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            request_path = Path(tmpdir) / "request.json"
            request_path.write_text(
                json.dumps(
                    {
                        "run_id": "run-live-fail",
                        "agent_role": "student",
                        "scenario_set_id": "public-curriculum-v1",
                        "workspace_snapshot": {
                            "objective": "Exercise honest failure handling",
                            "simulate_failure": True,
                        },
                        "time_budget": {"seconds": 30},
                        "cost_budget": {"usd": 1.25},
                    }
                )
            )

            server = _FakeClawithServer().start()
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "runner_bridge.cli",
                        "--request",
                        str(request_path),
                        "--artifacts-root",
                        str(artifacts_root),
                        "--clawith-url",
                        server.base_url,
                    ],
                    capture_output=True,
                    text=True,
                    cwd=ROOT,
                )
            finally:
                server.stop()

            self.assertNotEqual(result.returncode, 0)
            run_dir = artifacts_root / "run-live-fail"
            self.assertTrue((run_dir / "transcript.ndjson").exists())
            self.assertTrue((run_dir / "artifact-bundle.json").exists())
            self.assertTrue((run_dir / "receipts" / "manifest.json").exists())
            self.assertTrue((run_dir / "receipts" / "candidate.json").exists())
            failure_result = json.loads((run_dir / "result.json").read_text())
            self.assertEqual(failure_result["status"], "failed")
            self.assertIn("error", failure_result)
            self.assertEqual(failure_result["provenance"]["receipt_manifest_path"], "receipts/manifest.json")

            statuses = [patch["payload"]["status"] for patch in server.patches]
            self.assertEqual(statuses, ["queued", "running", "failed"])
            failed = server.patches[-1]["payload"]
            self.assertEqual(failed["status"], "failed")
            self.assertIn("error", failed)
            self.assertTrue(failed["artifact_bundle_path"].endswith("artifact-bundle.json"))

    def test_invalid_request_fails_before_backend_execution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            request_path = Path(tmpdir) / "request.json"
            request_path.write_text(
                json.dumps(
                    {
                        "run_id": "run-invalid",
                        "agent_role": "student",
                        "scenario_set_id": "public-curriculum-v1",
                        "workspace_snapshot": {"objective": "missing budgets"},
                    }
                )
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.cli",
                    "--request",
                    str(request_path),
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing required field", result.stderr.lower())


class RunnerBridgeDocumentationTests(unittest.TestCase):
    def test_runner_bridge_doc_mentions_local_mockable_bridge_contract(self):
        text = RUNNER_DOC.read_text()
        self.assertIn("LocalReplayRunner", text)
        self.assertIn("PATCH /api/runs/{run_id}", text)
        self.assertIn("zero-secret", text.lower())
        self.assertIn("receipt provenance", text.lower())
        self.assertIn("evidence-index.json", text)

    def test_readme_mentions_first_live_run_cli(self):
        text = README.read_text()
        self.assertIn("python3 -m runner_bridge.cli", text)
        self.assertIn("first live run", text.lower())
        self.assertIn("receipt provenance pack", text.lower())


if __name__ == "__main__":
    unittest.main()

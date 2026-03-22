import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "seed" / "probe_clawith.py"


class _ProbeHandler(BaseHTTPRequestHandler):
    token = "probe-token"

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        return self.headers.get("Authorization") == f"Bearer {self.token}"

    def log_message(self, *args, **kwargs):  # pragma: no cover
        return

    def do_GET(self):
        if self.path == "/api/health":
            return self._send_json(200, {"status": "ok", "version": "1.7.1"})
        if self.path == "/api/version":
            return self._send_json(200, {"version": "1.7.1", "commit": "abc123"})
        if self.path == "/api/auth/registration-config":
            return self._send_json(200, {"invitation_code_required": False})
        if self.path == "/api/enterprise/system-settings/notification_bar/public":
            return self._send_json(200, {"enabled": False, "text": ""})
        if self.path == "/openapi.json":
            return self._send_json(
                200,
                {
                    "openapi": "3.1.0",
                    "info": {"title": "Clawith", "version": "1.7.1"},
                    "paths": {
                        "/api/health": {"get": {}},
                        "/api/version": {"get": {}},
                        "/api/auth/registration-config": {"get": {}},
                        "/api/auth/me": {"get": {}},
                        "/api/enterprise/llm-providers": {"get": {}},
                        "/api/enterprise/llm-models": {"get": {}},
                        "/api/admin/companies": {"get": {}},
                    },
                },
            )
        if self.path == "/api/auth/me":
            if not self._authorized():
                return self._send_json(401, {"detail": "Not authenticated"})
            return self._send_json(200, {"username": "alice", "role": "platform_admin"})
        if self.path == "/api/enterprise/llm-providers":
            if not self._authorized():
                return self._send_json(401, {"detail": "Not authenticated"})
            return self._send_json(200, [{"provider": "openai"}])
        if self.path == "/api/enterprise/llm-models":
            if not self._authorized():
                return self._send_json(401, {"detail": "Not authenticated"})
            return self._send_json(200, [])
        if self.path == "/api/admin/companies":
            if not self._authorized():
                return self._send_json(401, {"detail": "Not authenticated"})
            return self._send_json(200, [])
        return self._send_json(404, {"detail": "Not Found"})

    def do_POST(self):
        if self.path == "/api/auth/login":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if payload.get("username") == "alice" and payload.get("password") == "secret":
                return self._send_json(
                    200,
                    {
                        "access_token": self.token,
                        "token_type": "bearer",
                        "user": {"username": "alice", "role": "platform_admin"},
                    },
                )
            return self._send_json(401, {"detail": "bad creds"})
        return self._send_json(404, {"detail": "Not Found"})


class _ProbeServer(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), _ProbeHandler)
        self.thread = Thread(target=self.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.server_port}"


class ClawithProbeScriptTests(unittest.TestCase):
    def test_probe_reports_public_surface_and_native_parity_gap(self):
        server = _ProbeServer().start()
        try:
            result = subprocess.run(
                [sys.executable, str(PROBE), "--base-url", server.base_url, "--json"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["summary"]["public_upstream_ready"])
            self.assertEqual(payload["summary"]["adapter_first_readiness"], "unknown")
            self.assertEqual(payload["summary"]["native_role_foundry_parity"], "no")
            self.assertTrue(
                any("/api/roles" in warning for warning in payload["summary"]["warnings"]),
                payload["summary"],
            )
            statuses = {check["path"]: check["status"] for check in payload["checks"]}
            self.assertEqual(statuses["/api/health"], 200)
            self.assertEqual(statuses["/api/auth/me"], 401)
            self.assertEqual(statuses["/api/enterprise/llm-models"], 401)
            self.assertEqual(statuses["/api/admin/companies"], 401)
        finally:
            server.shutdown()
            server.server_close()

    def test_probe_supports_login_and_reports_empty_model_pool_blocker(self):
        server = _ProbeServer().start()
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(PROBE),
                    "--base-url",
                    server.base_url,
                    "--username",
                    "alice",
                    "--password",
                    "secret",
                    "--json",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            statuses = {check["path"]: check["status"] for check in payload["checks"]}
            self.assertEqual(statuses["/api/auth/login"], 200)
            self.assertEqual(statuses["/api/auth/me"], 200)
            self.assertEqual(statuses["/api/enterprise/llm-models"], 200)
            self.assertTrue(
                any("empty model pool" in blocker for blocker in payload["summary"]["blockers"]),
                payload["summary"],
            )
        finally:
            server.shutdown()
            server.server_close()

    def test_probe_can_fall_back_to_source_tree_inspection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "backend" / "app" / "api").mkdir(parents=True)
            (root / "backend" / "app" / "main.py").write_text('@app.get("/api/health")\n')
            (root / "backend" / "app" / "api" / "auth.py").write_text(
                textwrap.dedent(
                    '''
                    # The first user to register becomes the platform admin automatically.
                    role = "platform_admin"
                    '''
                )
            )
            (root / "backend" / "app" / "api" / "enterprise.py").write_text('@router.get("/llm-models")\n')
            (root / "backend" / "app" / "api" / "admin.py").write_text('@router.get("/companies")\n')

            server = _ProbeServer().start()
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(PROBE),
                        "--base-url",
                        server.base_url,
                        "--source-dir",
                        str(root),
                        "--json",
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertTrue(payload["source_findings"]["available"])
                self.assertTrue(payload["source_findings"]["first_user_becomes_platform_admin"])
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()

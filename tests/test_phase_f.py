"""Phase F acceptance tests: F001–F004.

F001 — Prereq probe coverage (6 checks present and evidenced)
F002 — False-ready rate (zero cases marked ready when prereqs missing)
F003 — Mapping completeness (seam-to-upstream matrix, allowed statuses only)
F004 — Non-destructive guarantee (bring-up probe performs no write operations)
"""

import ast
import json
import subprocess
import sys
import textwrap
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_clawith_readiness.py"

REQUIRED_F001_CHECKS = {
    "base_url_reachable",
    "auth_surface_understood",
    "admin_presence_known",
    "model_pool_presence_known",
    "endpoint_mismatch_documented",
    "status_categorization_valid",
}

ALLOWED_READINESS_STATUSES = {"ready", "blocked", "unknown"}

ALLOWED_MAPPING_STATUSES = {
    "matches",
    "adapter_needed",
    "missing_upstream",
    "blocked_by_auth",
    "unknown",
}


# ---------------------------------------------------------------------------
# Minimal test server (GET-only, matching upstream Clawith shape)
# ---------------------------------------------------------------------------

class _HealthyHandler(BaseHTTPRequestHandler):
    """Simulates a healthy upstream Clawith (public surface only)."""

    def log_message(self, *a, **kw):
        return

    def do_GET(self):
        routes = {
            "/api/health": (200, {"status": "ok"}),
            "/api/version": (200, {"version": "1.0.0"}),
            "/api/auth/registration-config": (200, {"invitation_code_required": False}),
            "/api/auth/me": (401, {"detail": "Not authenticated"}),
            "/api/enterprise/llm-models": (401, {"detail": "Not authenticated"}),
            "/api/admin/companies": (401, {"detail": "Not authenticated"}),
        }
        status, payload = routes.get(self.path, (404, {"detail": "Not Found"}))
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _UnhealthyHandler(BaseHTTPRequestHandler):
    """Simulates an unreachable/broken upstream."""

    def log_message(self, *a, **kw):
        return

    def do_GET(self):
        self.send_response(503)
        self.send_header("Content-Type", "text/plain")
        body = b"Service Unavailable"
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _TestServer(ThreadingHTTPServer):
    def __init__(self, handler):
        super().__init__(("127.0.0.1", 0), handler)
        self._thread = Thread(target=self.serve_forever, daemon=True)

    def start(self):
        self._thread.start()
        return self

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.server_port}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_checker(base_url: str, extra_args: list[str] | None = None) -> dict:
    cmd = [sys.executable, str(CHECKER), "--base-url", base_url, "--json"]
    if extra_args:
        cmd.extend(extra_args)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "report": json.loads(proc.stdout) if proc.stdout.strip() else None,
    }


# ---------------------------------------------------------------------------
# F001 — Prereq probe coverage
# ---------------------------------------------------------------------------

class TestF001PrereqProbeCoverage(unittest.TestCase):
    """F001: all 6 required readiness checks must be present."""

    def test_f001_all_six_checks_present_healthy_server(self):
        server = _TestServer(_HealthyHandler).start()
        try:
            out = _run_checker(server.base_url)
            report = out["report"]
            self.assertIsNotNone(report)
            check_names = {c["check"] for c in report["checks"]}
            self.assertEqual(
                check_names,
                REQUIRED_F001_CHECKS,
                f"Missing checks: {REQUIRED_F001_CHECKS - check_names}",
            )
        finally:
            server.shutdown()
            server.server_close()

    def test_f001_all_six_checks_present_offline_mode(self):
        out = _run_checker("http://localhost:1", ["--offline"])
        report = out["report"]
        self.assertIsNotNone(report)
        check_names = {c["check"] for c in report["checks"]}
        self.assertEqual(check_names, REQUIRED_F001_CHECKS)

    def test_f001_all_six_checks_present_unhealthy_server(self):
        server = _TestServer(_UnhealthyHandler).start()
        try:
            out = _run_checker(server.base_url)
            report = out["report"]
            self.assertIsNotNone(report)
            check_names = {c["check"] for c in report["checks"]}
            self.assertEqual(check_names, REQUIRED_F001_CHECKS)
        finally:
            server.shutdown()
            server.server_close()

    def test_f001_every_check_has_status_and_detail(self):
        out = _run_checker("http://localhost:1", ["--offline"])
        report = out["report"]
        for check in report["checks"]:
            self.assertIn("check", check)
            self.assertIn("status", check)
            self.assertIn(check["status"], ALLOWED_READINESS_STATUSES)


# ---------------------------------------------------------------------------
# F002 — False-ready rate
# ---------------------------------------------------------------------------

class TestF002FalseReadyRate(unittest.TestCase):
    """F002: zero cases marked 'ready' when prereqs are missing."""

    def test_f002_offline_never_ready(self):
        """Offline mode has unknown network checks — must not be 'ready'."""
        out = _run_checker("http://localhost:1", ["--offline"])
        report = out["report"]
        self.assertNotEqual(
            report["overall_readiness"],
            "ready",
            "Overall readiness must not be 'ready' in offline mode",
        )

    def test_f002_unhealthy_server_never_ready(self):
        server = _TestServer(_UnhealthyHandler).start()
        try:
            out = _run_checker(server.base_url)
            report = out["report"]
            self.assertNotEqual(
                report["overall_readiness"],
                "ready",
                "Overall readiness must not be 'ready' when health check fails",
            )
        finally:
            server.shutdown()
            server.server_close()

    def test_f002_healthy_but_no_auth_is_not_ready(self):
        """Healthy public surface but unknown admin/model pool — not ready."""
        server = _TestServer(_HealthyHandler).start()
        try:
            out = _run_checker(server.base_url)
            report = out["report"]
            # Admin and model-pool are unknown without auth
            self.assertNotEqual(
                report["overall_readiness"],
                "ready",
                "Must not be 'ready' when admin/model-pool presence is unknown",
            )
        finally:
            server.shutdown()
            server.server_close()

    def test_f002_blocked_check_prevents_ready(self):
        """Programmatic: if any check is blocked, overall cannot be ready."""
        # Import the module to test compute_overall_readiness directly
        import importlib.util
        spec = importlib.util.spec_from_file_location("checker", CHECKER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        checks_with_blocked = [
            {"check": "a", "status": "ready"},
            {"check": "b", "status": "blocked"},
            {"check": "c", "status": "ready"},
        ]
        self.assertEqual(mod.compute_overall_readiness(checks_with_blocked), "blocked")

    def test_f002_unknown_check_prevents_ready(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("checker", CHECKER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        checks_with_unknown = [
            {"check": "a", "status": "ready"},
            {"check": "b", "status": "unknown"},
        ]
        self.assertEqual(mod.compute_overall_readiness(checks_with_unknown), "unknown")

    def test_f002_all_ready_means_ready(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("checker", CHECKER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        all_ready = [
            {"check": "a", "status": "ready"},
            {"check": "b", "status": "ready"},
        ]
        self.assertEqual(mod.compute_overall_readiness(all_ready), "ready")


# ---------------------------------------------------------------------------
# F003 — Mapping completeness
# ---------------------------------------------------------------------------

class TestF003MappingCompleteness(unittest.TestCase):
    """F003: seam-to-upstream matrix uses allowed statuses only."""

    def test_f003_all_mapping_statuses_are_allowed(self):
        out = _run_checker("http://localhost:1", ["--offline"])
        report = out["report"]
        for row in report["seam_mapping"]:
            self.assertIn(
                row["status"],
                ALLOWED_MAPPING_STATUSES,
                f"Seam '{row['seam']}' has invalid status '{row['status']}'",
            )

    def test_f003_mapping_validation_passes(self):
        out = _run_checker("http://localhost:1", ["--offline"])
        report = out["report"]
        mv = report["mapping_validation"]
        self.assertTrue(mv["all_valid"], f"Invalid rows: {mv['invalid_rows']}")

    def test_f003_every_row_has_required_fields(self):
        out = _run_checker("http://localhost:1", ["--offline"])
        report = out["report"]
        for row in report["seam_mapping"]:
            self.assertIn("seam", row)
            self.assertIn("upstream", row)
            self.assertIn("status", row)
            self.assertIn("note", row)

    def test_f003_missing_upstream_documented(self):
        """Known Role Foundry-native gaps must appear as missing_upstream."""
        out = _run_checker("http://localhost:1", ["--offline"])
        report = out["report"]
        missing = {
            row["seam"]
            for row in report["seam_mapping"]
            if row["status"] == "missing_upstream"
        }
        self.assertIn("POST /api/roles", missing)
        self.assertIn("POST /api/scenarios", missing)
        self.assertIn("PATCH /api/runs/{run_id}", missing)

    def test_f003_no_blank_statuses(self):
        out = _run_checker("http://localhost:1", ["--offline"])
        report = out["report"]
        for row in report["seam_mapping"]:
            self.assertTrue(
                row["status"].strip(),
                f"Seam '{row['seam']}' has blank status",
            )


# ---------------------------------------------------------------------------
# F004 — Non-destructive guarantee
# ---------------------------------------------------------------------------

class TestF004NonDestructiveGuarantee(unittest.TestCase):
    """F004: bring-up probe performs no write operations."""

    def test_f004_report_declares_non_destructive(self):
        out = _run_checker("http://localhost:1", ["--offline"])
        report = out["report"]
        self.assertTrue(report["non_destructive"])
        self.assertEqual(report["http_methods_used"], ["GET"])

    def test_f004_source_uses_only_get_requests(self):
        """Static analysis: the checker script must not use write HTTP methods."""
        source = CHECKER.read_text()
        tree = ast.parse(source)

        # Find all string literals that look like HTTP methods
        write_methods = {"POST", "PUT", "PATCH", "DELETE"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.upper() in write_methods:
                    # Allow if it's in a comment-like context (docstring)
                    # or in the SEAM_MAPPING data structure
                    # We need to check if it's used as a method= argument
                    pass  # We'll do a more targeted check below

        # More targeted: ensure no urllib.request.Request with method != GET
        # and no http_request calls with non-GET methods
        # Check that _get function only uses GET
        self.assertIn('method="GET"', source)
        # Ensure no POST/PUT/PATCH/DELETE in method= arguments
        for method in write_methods:
            self.assertNotIn(
                f'method="{method}"',
                source,
                f"Found write method {method} in checker source",
            )

    def test_f004_server_receives_only_get(self):
        """Run the checker against a real server and verify only GET requests arrive."""
        received_methods: list[str] = []

        class _RecordingHandler(BaseHTTPRequestHandler):
            def log_message(self, *a, **kw):
                return

            def do_GET(self):
                received_methods.append("GET")
                body = json.dumps({"status": "ok"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                received_methods.append("POST")
                self.send_response(405)
                self.end_headers()

            def do_PUT(self):
                received_methods.append("PUT")
                self.send_response(405)
                self.end_headers()

            def do_PATCH(self):
                received_methods.append("PATCH")
                self.send_response(405)
                self.end_headers()

            def do_DELETE(self):
                received_methods.append("DELETE")
                self.send_response(405)
                self.end_headers()

        server = _TestServer(_RecordingHandler).start()
        try:
            _run_checker(server.base_url)
            # Every request must be GET
            self.assertTrue(len(received_methods) > 0, "No requests received")
            non_get = [m for m in received_methods if m != "GET"]
            self.assertEqual(
                non_get,
                [],
                f"Non-GET methods received: {non_get}",
            )
        finally:
            server.shutdown()
            server.server_close()


# ---------------------------------------------------------------------------
# Integration: human output mode
# ---------------------------------------------------------------------------

class TestHumanOutput(unittest.TestCase):
    def test_human_output_includes_phase_f_header(self):
        proc = subprocess.run(
            [sys.executable, str(CHECKER), "--offline"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertIn("Phase F", proc.stdout)
        self.assertIn("PREREQ CHECKS", proc.stdout)
        self.assertIn("SEAM-TO-UPSTREAM MAPPING", proc.stdout)
        self.assertIn("NON-CLAIMS", proc.stdout)


if __name__ == "__main__":
    unittest.main()

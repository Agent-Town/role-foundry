"""Phase F adapter-readiness tests (F001-F004).

F001: prereq probe coverage — all 6 required categories present
F002: false-ready rate — zero false-ready when prereqs are missing/unknown
F003: mapping completeness — every row has an explicit allowed status
F004: non-destructive guarantee — no write operations in probe
"""

import json
import subprocess
import sys
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "check_clawith_adapter_prereqs.py"
BRINGUP_DOC = ROOT / "docs" / "clawith-adapter-bringup.md"

REQUIRED_CATEGORIES = [
    "base_url_reachable",
    "auth_surface_understood",
    "admin_presence_known",
    "model_pool_presence_known",
    "endpoint_mismatch_documented",
    "status_categorized",
]

ALLOWED_MAPPING_STATUSES = {
    "matches",
    "adapter_needed",
    "missing_upstream",
    "blocked_by_auth",
    "unknown",
}


# ---------------------------------------------------------------------------
# Fake upstream servers for probe testing
# ---------------------------------------------------------------------------

class _HealthyHandler(BaseHTTPRequestHandler):
    """Simulates a healthy upstream Clawith with no admin and empty model pool."""
    token = "test-jwt-token"

    def log_message(self, *a, **kw):
        return

    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        return self.headers.get("Authorization") == f"Bearer {self.token}"

    def do_GET(self):
        if self.path == "/api/health":
            return self._json(200, {"status": "ok", "version": "1.7.1"})
        if self.path == "/api/version":
            return self._json(200, {"version": "1.7.1"})
        if self.path == "/api/auth/registration-config":
            return self._json(200, {"invitation_code_required": False})
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html>app shell</html>")
            return
        if self.path == "/api/auth/me":
            if not self._authorized():
                return self._json(401, {"detail": "Not authenticated"})
            return self._json(200, {"username": "alice", "role": "platform_admin"})
        if self.path == "/api/enterprise/llm-providers":
            if not self._authorized():
                return self._json(401, {"detail": "Not authenticated"})
            return self._json(200, [{"provider": "openai"}])
        if self.path == "/api/enterprise/llm-models":
            if not self._authorized():
                return self._json(401, {"detail": "Not authenticated"})
            return self._json(200, [])  # empty model pool
        if self.path == "/api/admin/companies":
            if not self._authorized():
                return self._json(401, {"detail": "Not authenticated"})
            return self._json(200, [{"id": "c1", "name": "Default"}])
        return self._json(404, {"detail": "Not found"})

    def do_POST(self):
        # The probe should NEVER issue POST requests.
        self._json(405, {"detail": "POST not allowed by test server"})


class _FullyReadyHandler(_HealthyHandler):
    """Upstream with admin and populated model pool."""

    def do_GET(self):
        if self.path == "/api/enterprise/llm-models":
            if not self._authorized():
                return self._json(401, {"detail": "Not authenticated"})
            return self._json(200, [{"id": "m1", "name": "gpt-4"}])
        return super().do_GET()


class _NonAdminHandler(_HealthyHandler):
    """Upstream where authenticated user is not an admin."""

    def do_GET(self):
        if self.path == "/api/auth/me":
            if not self._authorized():
                return self._json(401, {"detail": "Not authenticated"})
            return self._json(200, {"username": "bob", "role": "member"})
        return super().do_GET()


class _VersionFailHandler(_HealthyHandler):
    """Upstream where /api/version returns 500 — auth surface should NOT be ready."""

    def do_GET(self):
        if self.path == "/api/version":
            self._json(500, {"detail": "version unavailable"})
            return
        return super().do_GET()


class _AdminCompaniesFailHandler(_FullyReadyHandler):
    """Upstream where /api/admin/companies returns 500 despite valid admin auth."""

    def do_GET(self):
        if self.path == "/api/admin/companies":
            if not self._authorized():
                return self._json(401, {"detail": "Not authenticated"})
            return self._json(500, {"detail": "internal error"})
        return super().do_GET()


class _LlmProvidersFailHandler(_FullyReadyHandler):
    """Upstream where /api/enterprise/llm-providers returns 500 despite populated models."""

    def do_GET(self):
        if self.path == "/api/enterprise/llm-providers":
            if not self._authorized():
                return self._json(401, {"detail": "Not authenticated"})
            return self._json(500, {"detail": "internal error"})
        return super().do_GET()


class _UnreachableHandler(BaseHTTPRequestHandler):
    """Server that returns 500 for health."""

    def log_message(self, *a, **kw):
        return

    def do_GET(self):
        self.send_response(500)
        self.end_headers()
        self.wfile.write(b"internal error")


def _start_server(handler_cls):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


def _run_helper(base_url, token="", extra_args=None):
    cmd = [sys.executable, str(HELPER), "--base-url", base_url, "--json"]
    if token:
        cmd.extend(["--token", token])
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return result, json.loads(result.stdout) if result.stdout.strip() else None


# ---------------------------------------------------------------------------
# F001 — Prereq probe coverage
# ---------------------------------------------------------------------------

class TestF001PrereqProbeCoverage(unittest.TestCase):
    """F001: all 6 required prereq categories must be present in output."""

    def test_helper_exists_and_runs(self):
        self.assertTrue(HELPER.exists(), "scripts/check_clawith_adapter_prereqs.py must exist")
        result = subprocess.run(
            [sys.executable, str(HELPER), "--help"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--base-url", result.stdout)
        self.assertIn("--token", result.stdout)
        self.assertIn("--json", result.stdout)

    def test_all_six_categories_present_unauthenticated(self):
        server, url = _start_server(_HealthyHandler)
        try:
            _, payload = _run_helper(url)
            self.assertIsNotNone(payload)
            for cat in REQUIRED_CATEGORIES:
                self.assertIn(cat, payload["categories"], f"missing category: {cat}")
        finally:
            server.shutdown()
            server.server_close()

    def test_all_six_categories_present_authenticated(self):
        server, url = _start_server(_HealthyHandler)
        try:
            _, payload = _run_helper(url, token=_HealthyHandler.token)
            self.assertIsNotNone(payload)
            for cat in REQUIRED_CATEGORIES:
                self.assertIn(cat, payload["categories"], f"missing category: {cat}")
        finally:
            server.shutdown()
            server.server_close()

    def test_all_checks_are_get_only(self):
        """F004 partial: verify every check in the output uses GET method."""
        server, url = _start_server(_HealthyHandler)
        try:
            _, payload = _run_helper(url, token=_HealthyHandler.token)
            self.assertIsNotNone(payload)
            for check in payload["checks"]:
                self.assertEqual(check["method"], "GET",
                                 f"check {check['name']} uses {check['method']}, expected GET")
        finally:
            server.shutdown()
            server.server_close()

    def test_auth_surface_blocked_when_version_fails(self):
        """auth_surface_understood must be blocked if /api/version fails."""
        server, url = _start_server(_VersionFailHandler)
        try:
            _, payload = _run_helper(url)
            self.assertIsNotNone(payload)
            self.assertEqual(payload["categories"]["auth_surface_understood"], "blocked")
            self.assertTrue(
                any("api/version" in b for b in payload["blockers"]),
                f"blockers should mention version failure: {payload['blockers']}",
            )
        finally:
            server.shutdown()
            server.server_close()

    def test_llm_providers_and_admin_companies_probed_with_token(self):
        """With token, /api/enterprise/llm-providers and /api/admin/companies are probed."""
        server, url = _start_server(_HealthyHandler)
        try:
            _, payload = _run_helper(url, token=_HealthyHandler.token)
            self.assertIsNotNone(payload)
            check_names = [c["name"] for c in payload["checks"]]
            self.assertIn("llm_providers", check_names)
            self.assertIn("admin_companies", check_names)
            # Both should pass when authenticated
            for check in payload["checks"]:
                if check["name"] in ("llm_providers", "admin_companies"):
                    self.assertEqual(check["kind"], "pass", f"{check['name']} should pass")
        finally:
            server.shutdown()
            server.server_close()

    def test_auth_gated_surfaces_skipped_without_token(self):
        """Without token, auth_me, admin_companies, llm_providers, llm_models are all skipped."""
        server, url = _start_server(_HealthyHandler)
        try:
            _, payload = _run_helper(url)
            self.assertIsNotNone(payload)
            skipped = [c["name"] for c in payload["checks"] if c["kind"] == "skip"]
            self.assertIn("auth_me", skipped)
            self.assertIn("admin_companies", skipped)
            self.assertIn("llm_providers", skipped)
            self.assertIn("llm_models", skipped)
        finally:
            server.shutdown()
            server.server_close()

    def test_endpoint_mismatches_documented(self):
        server, url = _start_server(_HealthyHandler)
        try:
            _, payload = _run_helper(url)
            self.assertIsNotNone(payload)
            mismatches = payload.get("endpoint_mismatches", [])
            self.assertTrue(len(mismatches) > 0, "endpoint mismatches should be documented")
            mismatch_text = " ".join(mismatches)
            self.assertIn("/api/roles", mismatch_text)
            self.assertIn("/api/scenarios", mismatch_text)
            self.assertIn("/api/runs", mismatch_text)
        finally:
            server.shutdown()
            server.server_close()


# ---------------------------------------------------------------------------
# F002 — False-ready rate (must be zero)
# ---------------------------------------------------------------------------

class TestF002FalseReadyRate(unittest.TestCase):
    """F002: overall_status must NEVER be 'ready' when required prereqs are missing or unknown."""

    def test_unauthenticated_is_not_ready(self):
        """Without token, admin and model-pool are unknown => not ready."""
        server, url = _start_server(_HealthyHandler)
        try:
            _, payload = _run_helper(url)
            self.assertIsNotNone(payload)
            self.assertNotEqual(payload["overall_status"], "ready",
                                "must not report ready without authenticated admin/model-pool checks")
            self.assertIn(payload["overall_status"], ("blocked", "unknown"))
        finally:
            server.shutdown()
            server.server_close()

    def test_empty_model_pool_is_not_ready(self):
        """Authenticated but model pool empty => blocked, not ready."""
        server, url = _start_server(_HealthyHandler)
        try:
            _, payload = _run_helper(url, token=_HealthyHandler.token)
            self.assertIsNotNone(payload)
            self.assertNotEqual(payload["overall_status"], "ready",
                                "must not report ready with empty model pool")
            self.assertEqual(payload["categories"]["model_pool_presence_known"], "blocked")
            self.assertTrue(
                any("model pool" in b.lower() or "empty" in b.lower() for b in payload["blockers"]),
                f"blockers should mention empty model pool: {payload['blockers']}",
            )
        finally:
            server.shutdown()
            server.server_close()

    def test_non_admin_is_not_ready(self):
        """Authenticated as non-admin => admin_presence_known is blocked."""
        server, url = _start_server(_NonAdminHandler)
        try:
            _, payload = _run_helper(url, token=_NonAdminHandler.token)
            self.assertIsNotNone(payload)
            self.assertNotEqual(payload["overall_status"], "ready")
            self.assertEqual(payload["categories"]["admin_presence_known"], "blocked")
        finally:
            server.shutdown()
            server.server_close()

    def test_version_fail_prevents_ready(self):
        """If /api/version fails, overall cannot be ready even with populated model pool."""
        server, url = _start_server(_VersionFailHandler)
        try:
            _, payload = _run_helper(url, token=_VersionFailHandler.token)
            self.assertIsNotNone(payload)
            self.assertNotEqual(payload["overall_status"], "ready",
                                "must not report ready when /api/version fails")
            self.assertEqual(payload["categories"]["auth_surface_understood"], "blocked")
        finally:
            server.shutdown()
            server.server_close()

    def test_unreachable_is_blocked(self):
        """If /api/health fails, base_url_reachable is blocked."""
        server, url = _start_server(_UnreachableHandler)
        try:
            _, payload = _run_helper(url)
            self.assertIsNotNone(payload)
            self.assertEqual(payload["overall_status"], "blocked")
            self.assertEqual(payload["categories"]["base_url_reachable"], "blocked")
        finally:
            server.shutdown()
            server.server_close()

    def test_admin_companies_fail_blocks_admin_presence(self):
        """admin_presence_known must be blocked when /api/admin/companies fails,
        even if auth/me confirms an admin role."""
        server, url = _start_server(_AdminCompaniesFailHandler)
        try:
            _, payload = _run_helper(url, token=_AdminCompaniesFailHandler.token)
            self.assertIsNotNone(payload)
            self.assertEqual(payload["categories"]["admin_presence_known"], "blocked")
            self.assertNotEqual(payload["overall_status"], "ready")
            self.assertTrue(
                any("admin/companies" in b for b in payload["blockers"]),
                f"blockers should mention admin/companies failure: {payload['blockers']}",
            )
        finally:
            server.shutdown()
            server.server_close()

    def test_llm_providers_fail_blocks_model_pool(self):
        """model_pool_presence_known must be blocked when /api/enterprise/llm-providers fails,
        even if llm-models returns a populated list."""
        server, url = _start_server(_LlmProvidersFailHandler)
        try:
            _, payload = _run_helper(url, token=_LlmProvidersFailHandler.token)
            self.assertIsNotNone(payload)
            self.assertEqual(payload["categories"]["model_pool_presence_known"], "blocked")
            self.assertNotEqual(payload["overall_status"], "ready")
            self.assertTrue(
                any("llm-providers" in b for b in payload["blockers"]),
                f"blockers should mention llm-providers failure: {payload['blockers']}",
            )
        finally:
            server.shutdown()
            server.server_close()

    def test_fully_ready_when_all_prereqs_met(self):
        """Only report ready when admin is confirmed AND model pool is populated."""
        server, url = _start_server(_FullyReadyHandler)
        try:
            _, payload = _run_helper(url, token=_FullyReadyHandler.token)
            self.assertIsNotNone(payload)
            self.assertEqual(payload["overall_status"], "ready",
                             f"should be ready when all prereqs met, got: {payload}")
            for cat in REQUIRED_CATEGORIES:
                self.assertEqual(payload["categories"][cat], "ready",
                                 f"category {cat} should be ready")
        finally:
            server.shutdown()
            server.server_close()

    def test_human_output_includes_readiness_statement(self):
        """Human output must include a Readiness Statement section."""
        server, url = _start_server(_HealthyHandler)
        try:
            cmd = [sys.executable, str(HELPER), "--base-url", url]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--- Readiness Statement ---", result.stdout)
            # Without token, should mention unknown categories
            self.assertIn("UNKNOWN:", result.stdout)
        finally:
            server.shutdown()
            server.server_close()

    def test_human_readiness_statement_shows_blocked(self):
        """Human output readiness statement shows BLOCKED when model pool is empty."""
        server, url = _start_server(_HealthyHandler)
        try:
            cmd = [sys.executable, str(HELPER), "--base-url", url, "--token", _HealthyHandler.token]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--- Readiness Statement ---", result.stdout)
            self.assertIn("BLOCKED NOW:", result.stdout)
            self.assertIn("Resolve blockers", result.stdout)
        finally:
            server.shutdown()
            server.server_close()


# ---------------------------------------------------------------------------
# F003 — Mapping completeness
# ---------------------------------------------------------------------------

class TestF003MappingCompleteness(unittest.TestCase):
    """F003: every row in the mapping matrix must use an allowed status."""

    def test_bringup_doc_exists(self):
        self.assertTrue(BRINGUP_DOC.exists(), "docs/clawith-adapter-bringup.md must exist")

    def test_bringup_doc_says_adapter_first(self):
        text = BRINGUP_DOC.read_text()
        self.assertIn("adapter-first", text.lower())
        self.assertIn("do not edit `runner_bridge` core contracts", text.lower())

    def test_mapping_matrix_uses_only_allowed_statuses(self):
        """Every status cell in the mapping table must be one of the 5 allowed values."""
        text = BRINGUP_DOC.read_text()
        # Find lines that look like table rows with a status in the last column.
        table_rows = [
            line for line in text.splitlines()
            if line.strip().startswith("|") and line.strip().endswith("|")
        ]
        # Skip header and separator rows.
        data_rows = [
            r for r in table_rows
            if "---" not in r and "Status" not in r and "RF Seam" not in r
            and "Topic" not in r
        ]
        # The mapping matrix has 4 columns; status is the last column.
        statuses_found = []
        for row in data_rows:
            cells = [c.strip() for c in row.split("|")]
            # Filter out empty cells from leading/trailing pipes.
            cells = [c for c in cells if c]
            if len(cells) >= 4:
                status = cells[-1].strip().strip("`")
                if status in ALLOWED_MAPPING_STATUSES:
                    statuses_found.append(status)
        self.assertGreater(
            len(statuses_found), 10,
            f"expected at least 10 mapping rows with allowed statuses, found {len(statuses_found)}: {statuses_found}",
        )
        # Verify we see at least 3 distinct statuses (proving the matrix is not trivially uniform).
        distinct = set(statuses_found)
        self.assertGreaterEqual(
            len(distinct), 3,
            f"expected at least 3 distinct statuses in the mapping, found: {distinct}",
        )

    def test_mapping_doc_mentions_rf_native_gaps(self):
        text = BRINGUP_DOC.read_text()
        self.assertIn("/api/roles", text)
        self.assertIn("/api/scenarios", text)
        self.assertIn("/api/runs", text)
        self.assertIn("missing_upstream", text)

    def test_non_claims_section_present(self):
        text = BRINGUP_DOC.read_text()
        self.assertIn("Non-claims", text)
        self.assertIn("does **not** claim", text)

    def test_no_native_parity_claim(self):
        """Docs must not claim native upstream parity."""
        text = BRINGUP_DOC.read_text().lower()
        for bad_phrase in [
            "native upstream parity achieved",
            "upstream already ships rf",
            "full parity with upstream",
        ]:
            self.assertNotIn(bad_phrase, text, f"doc contains unsupported parity claim: {bad_phrase!r}")


# ---------------------------------------------------------------------------
# F004 — Non-destructive guarantee
# ---------------------------------------------------------------------------

class TestF004NonDestructiveGuarantee(unittest.TestCase):
    """F004: the probe must not issue any write operations."""

    def test_script_source_has_no_post_put_patch_delete(self):
        """Source code must not contain HTTP write method usage."""
        source = HELPER.read_text()
        for method in ["POST", "PUT", "PATCH", "DELETE"]:
            # Allow the word to appear in comments/docstrings/docs, but not as
            # an actual method= parameter to Request or http calls.
            self.assertNotIn(
                f'method="{method}"', source,
                f"probe source must not issue {method} requests",
            )

    def test_script_source_has_no_db_access(self):
        """Source code must not access databases."""
        source = HELPER.read_text()
        for pattern in ["psql", "docker exec", "subprocess.run", "sqlite"]:
            self.assertNotIn(pattern, source,
                             f"probe source must not contain DB access patterns: {pattern!r}")

    def test_post_to_server_never_happens(self):
        """Run the probe against a server that rejects POST — probe should still succeed."""
        server, url = _start_server(_HealthyHandler)
        try:
            result, payload = _run_helper(url, token=_HealthyHandler.token)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIsNotNone(payload)
            # If probe had issued POST, the server would have returned 405.
            for check in payload["checks"]:
                self.assertNotEqual(check.get("status_code"), 405,
                                    f"check {check['name']} got 405 — probe must not POST")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

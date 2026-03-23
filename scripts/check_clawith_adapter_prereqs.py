#!/usr/bin/env python3
"""Read-only prereq checks for upstream Clawith adapter bring-up (Phase F).

This script is intentionally GET-only and read-only:
- No registration, no login POST, no model or tenant writes, no DB access.
- It probes public upstream routes and, when given a bearer token,
  a few operator/admin routes that matter for first-admin + model-pool readiness.

Covers the six required F001 checks:
  1. base URL reachable
  2. auth surface understood
  3. admin presence known
  4. model-pool presence known
  5. endpoint mismatch documented
  6. status output clearly categorized as ready/blocked/unknown

Exit codes:
  0 = all checks resolved (may still be blocked/unknown — check JSON)
  1 = script-level error

Examples:
  python3 scripts/check_clawith_adapter_prereqs.py --base-url http://localhost:3008
  python3 scripts/check_clawith_adapter_prereqs.py \\
    --base-url http://localhost:3008 --token "$CLAWITH_JWT" --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any


DEFAULT_BASE_URL = os.environ.get("CLAWITH_UPSTREAM_URL", "http://localhost:3008")
DEFAULT_TIMEOUT = 5.0

# Endpoints that Role Foundry needs but upstream Clawith does not natively expose.
RF_NATIVE_GAPS = [
    "/api/roles",
    "/api/scenarios",
    "/api/runs/{run_id}",
]

# The six required prereq categories from F001.
REQUIRED_CATEGORIES = [
    "base_url_reachable",
    "auth_surface_understood",
    "admin_presence_known",
    "model_pool_presence_known",
    "endpoint_mismatch_documented",
    "status_categorized",
]


@dataclass
class CheckResult:
    """Result of a single HTTP probe check."""
    name: str
    path: str
    method: str
    ok: bool
    kind: str  # pass | fail | note | skip
    status_code: int | None = None
    detail: str = ""
    body: Any | None = None


@dataclass
class PrereqReport:
    """Full prereq report covering all six F001 categories."""
    base_url: str
    checks: list[CheckResult] = field(default_factory=list)
    categories: dict[str, str] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    endpoint_mismatches: list[str] = field(default_factory=list)
    overall_status: str = "unknown"  # ready | blocked | unknown

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "overall_status": self.overall_status,
            "categories": self.categories,
            "blockers": self.blockers,
            "endpoint_mismatches": self.endpoint_mismatches,
            "checks": [asdict(c) for c in self.checks],
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only prereq checks for upstream Clawith adapter bring-up"
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Upstream Clawith base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("CLAWITH_JWT", ""),
        help="Optional bearer token for authenticated checks (GET only)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human text",
    )
    return parser


def http_get(
    base_url: str,
    path: str,
    *,
    token: str = "",
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[int, dict[str, str], bytes]:
    """Issue a GET request. Raises on HTTP errors or connection failures."""
    headers: dict[str, str] = {"Accept": "application/json, text/plain, */*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{base_url}{path}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, dict(response.headers.items()), response.read()


def probe_json(
    base_url: str,
    path: str,
    name: str,
    *,
    token: str = "",
    timeout: float = DEFAULT_TIMEOUT,
) -> CheckResult:
    """Probe a path expecting JSON. Returns a CheckResult."""
    try:
        status, headers, raw = http_get(base_url, path, token=token, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = f"HTTP {exc.code}"
        if exc.code == 401:
            detail += " (auth required or token invalid)"
        return CheckResult(name, path, "GET", ok=False, kind="fail", status_code=exc.code, detail=detail)
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", str(exc))
        return CheckResult(name, path, "GET", ok=False, kind="fail", detail=f"unreachable: {reason}")

    try:
        body = json.loads(raw.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        content_type = headers.get("Content-Type", "unknown")
        return CheckResult(
            name, path, "GET", ok=False, kind="fail",
            status_code=status, detail=f"expected JSON but got {content_type}",
        )

    return CheckResult(name, path, "GET", ok=True, kind="pass", status_code=status, detail="", body=body)


def probe_any(
    base_url: str,
    path: str,
    name: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> CheckResult:
    """Probe a path without requiring JSON — used for documenting /health behavior."""
    try:
        status, headers, raw = http_get(base_url, path, timeout=timeout)
    except urllib.error.HTTPError as exc:
        return CheckResult(name, path, "GET", ok=True, kind="note", status_code=exc.code,
                           detail=f"HTTP {exc.code}; this path is not the upstream JSON health API")
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", str(exc))
        return CheckResult(name, path, "GET", ok=True, kind="note", detail=f"unreachable: {reason}")

    content_type = headers.get("Content-Type", "unknown")
    if "text/html" in content_type:
        detail = f"HTML response ({content_type}); do not treat this as upstream JSON health"
    else:
        detail = f"content-type={content_type}"
    return CheckResult(name, path, "GET", ok=True, kind="note", status_code=status, detail=detail)


def run_checks(base_url: str, token: str, timeout: float) -> PrereqReport:
    """Execute all prereq probes and build the report."""
    report = PrereqReport(base_url=base_url)

    # --- Check 1: base URL reachable ---
    health = probe_json(base_url, "/api/health", "api_health", timeout=timeout)
    report.checks.append(health)

    # Also probe /health as a documentation note (not relied upon).
    legacy_health = probe_any(base_url, "/health", "legacy_health_note", timeout=timeout)
    report.checks.append(legacy_health)

    if health.ok:
        report.categories["base_url_reachable"] = "ready"
    else:
        report.categories["base_url_reachable"] = "blocked"
        report.blockers.append(f"base URL unreachable or /api/health failed: {health.detail}")

    # --- Check 2: auth surface understood ---
    # Both registration-config AND version must respond for the auth surface
    # to be considered understood.  Previously /api/version was probed but not
    # used as a gate — that left a false-ready window.
    reg_config = probe_json(base_url, "/api/auth/registration-config", "registration_config", timeout=timeout)
    report.checks.append(reg_config)

    version = probe_json(base_url, "/api/version", "api_version", timeout=timeout)
    report.checks.append(version)

    if reg_config.ok and version.ok:
        report.categories["auth_surface_understood"] = "ready"
    else:
        report.categories["auth_surface_understood"] = "blocked"
        parts = []
        if not reg_config.ok:
            parts.append(f"registration-config failed: {reg_config.detail}")
        if not version.ok:
            parts.append(f"api/version failed: {version.detail}")
        report.blockers.append(f"auth surface not fully understood: {'; '.join(parts)}")

    # --- Check 3: admin presence known ---
    # Requires BOTH auth/me confirming admin role AND /api/admin/companies
    # responding successfully.  Either failure blocks this category.
    if token:
        auth_me = probe_json(base_url, "/api/auth/me", "auth_me", token=token, timeout=timeout)
        report.checks.append(auth_me)

        admin_companies = probe_json(base_url, "/api/admin/companies", "admin_companies", token=token, timeout=timeout)
        report.checks.append(admin_companies)

        admin_blockers: list[str] = []

        if auth_me.ok and isinstance(auth_me.body, dict):
            role = auth_me.body.get("role")
            if role not in ("platform_admin", "org_admin"):
                admin_blockers.append(
                    f"authenticated user role is {role!r}, not platform_admin or org_admin"
                )
        elif auth_me.ok:
            admin_blockers.append("auth/me returned unexpected payload shape")
        else:
            admin_blockers.append(f"auth/me probe failed: {auth_me.detail}")

        if not admin_companies.ok:
            admin_blockers.append(f"admin/companies probe failed: {admin_companies.detail}")

        if admin_blockers:
            report.categories["admin_presence_known"] = "blocked"
            report.blockers.extend(admin_blockers)
        else:
            report.categories["admin_presence_known"] = "ready"
    else:
        for skip_name, skip_path in [
            ("auth_me", "/api/auth/me"),
            ("admin_companies", "/api/admin/companies"),
        ]:
            skip = CheckResult(skip_name, skip_path, "GET", ok=False, kind="skip",
                               detail="skipped: pass --token to verify admin presence")
            report.checks.append(skip)
        report.categories["admin_presence_known"] = "unknown"
        report.blockers.append("admin presence unknown: no token supplied for authenticated probe")

    # --- Check 4: model-pool presence known ---
    # Requires BOTH /api/enterprise/llm-providers responding successfully AND
    # /api/enterprise/llm-models returning a populated model list.
    # Either failure blocks this category.
    if token:
        llm_providers = probe_json(base_url, "/api/enterprise/llm-providers", "llm_providers", token=token, timeout=timeout)
        report.checks.append(llm_providers)

        llm_models = probe_json(base_url, "/api/enterprise/llm-models", "llm_models", token=token, timeout=timeout)
        report.checks.append(llm_models)

        model_blockers: list[str] = []

        if not llm_providers.ok:
            model_blockers.append(f"llm-providers probe failed: {llm_providers.detail}")

        if llm_models.ok:
            model_count = _count_models(llm_models.body)
            if model_count is not None and model_count == 0:
                model_blockers.append("model pool is empty: no LLM model entries configured")
            elif model_count is None:
                model_blockers.append("model pool response had unexpected shape")
        else:
            model_blockers.append(f"llm-models probe failed: {llm_models.detail}")

        if model_blockers:
            report.categories["model_pool_presence_known"] = "blocked"
            report.blockers.extend(model_blockers)
        else:
            report.categories["model_pool_presence_known"] = "ready"
    else:
        for skip_name, skip_path in [
            ("llm_providers", "/api/enterprise/llm-providers"),
            ("llm_models", "/api/enterprise/llm-models"),
        ]:
            skip = CheckResult(skip_name, skip_path, "GET", ok=False, kind="skip",
                               detail="skipped: pass --token to inspect this auth-gated surface")
            report.checks.append(skip)
        report.categories["model_pool_presence_known"] = "unknown"
        report.blockers.append("model-pool presence unknown: no token supplied for authenticated probe")

    # --- Check 5: endpoint mismatch documented ---
    # We document RF-native gaps by noting which RF endpoints are NOT in upstream.
    # This is always "ready" because the mismatch is explicitly documented here.
    for gap_path in RF_NATIVE_GAPS:
        report.endpoint_mismatches.append(
            f"upstream missing: {gap_path} (Role Foundry adapter needed)"
        )
    report.categories["endpoint_mismatch_documented"] = "ready"

    # --- Check 6: status output clearly categorized ---
    # This category is always satisfied by the report structure itself.
    report.categories["status_categorized"] = "ready"

    # --- Derive overall_status ---
    report.overall_status = _derive_overall_status(report.categories)

    return report


def _count_models(body: Any) -> int | None:
    """Extract model count from LLM models response."""
    if isinstance(body, list):
        return len(body)
    if isinstance(body, dict):
        items = body.get("items")
        if isinstance(items, list):
            return len(items)
    return None


def _derive_overall_status(categories: dict[str, str]) -> str:
    """Derive overall status. Never returns 'ready' if any category is blocked or unknown."""
    statuses = set(categories.values())
    if "blocked" in statuses:
        return "blocked"
    if "unknown" in statuses:
        return "unknown"
    if all(s == "ready" for s in statuses):
        return "ready"
    return "unknown"


def render_human(report: PrereqReport) -> None:
    """Print human-readable report to stdout."""
    print(f"Clawith adapter prereq check: {report.base_url}")
    print(f"Overall status: {report.overall_status.upper()}")
    print()

    print("Checks:")
    for check in report.checks:
        badge = {"pass": "PASS", "fail": "FAIL", "note": "NOTE", "skip": "SKIP"}.get(
            check.kind, check.kind.upper()
        )
        status_str = f" [{check.status_code}]" if check.status_code is not None else ""
        print(f"  {badge:>4}  {check.method} {check.path}{status_str}  {check.detail}")

    print()
    print("Categories (F001):")
    for cat, status in report.categories.items():
        print(f"  {cat}: {status}")

    if report.blockers:
        print()
        print("Blockers:")
        for b in report.blockers:
            print(f"  - {b}")

    if report.endpoint_mismatches:
        print()
        print("Endpoint mismatches (adapter needed):")
        for m in report.endpoint_mismatches:
            print(f"  - {m}")

    # --- Concise readiness statement ---
    print()
    print("--- Readiness Statement ---")
    ready_cats = [c for c, s in report.categories.items() if s == "ready"]
    blocked_cats = [c for c, s in report.categories.items() if s == "blocked"]
    unknown_cats = [c for c, s in report.categories.items() if s == "unknown"]
    if ready_cats:
        print(f"  READY NOW:    {', '.join(ready_cats)}")
    if blocked_cats:
        print(f"  BLOCKED NOW:  {', '.join(blocked_cats)}")
    if unknown_cats:
        print(f"  UNKNOWN:      {', '.join(unknown_cats)}")
    if not blocked_cats and not unknown_cats:
        print("  All prereqs satisfied — adapter bring-up can proceed.")
    elif blocked_cats:
        print("  Resolve blockers before adapter bring-up.")
    else:
        print("  Supply --token to resolve unknown categories.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_url = args.base_url.rstrip("/")
    token = args.token.strip()

    report = run_checks(base_url, token, args.timeout)

    if args.json:
        json.dump(report.to_dict(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        render_human(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

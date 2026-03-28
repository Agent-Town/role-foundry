#!/usr/bin/env python3
"""Phase F readiness checker for Clawith adapter-first bring-up.

Produces a structured readiness report covering the six F001 checks:
  1. base URL reachable
  2. auth surface understood
  3. admin presence known
  4. model-pool presence known
  5. endpoint mismatch documented
  6. status output clearly categorized as ready/blocked/unknown

This script is **GET-only** (F004 non-destructive guarantee).
It never issues POST, PUT, PATCH, DELETE, or any write operation.

Usage:
  python3 scripts/check_clawith_readiness.py --base-url http://localhost:3000
  python3 scripts/check_clawith_readiness.py --base-url http://localhost:3000 --json
  python3 scripts/check_clawith_readiness.py --offline   # no network, reports unknown
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

# Allowed readiness statuses per F001 / F003
ALLOWED_STATUSES = {"ready", "blocked", "unknown"}

# Seam-to-upstream mapping statuses per F003
ALLOWED_MAPPING_STATUSES = {
    "matches",
    "adapter_needed",
    "missing_upstream",
    "blocked_by_auth",
    "unknown",
}

# Role Foundry seam endpoints and their known upstream mapping (F003)
SEAM_MAPPING: list[dict[str, str]] = [
    {
        "seam": "GET /api/health",
        "upstream": "GET /api/health",
        "status": "matches",
        "note": "Upstream exposes this natively.",
    },
    {
        "seam": "GET /api/version",
        "upstream": "GET /api/version",
        "status": "matches",
        "note": "Upstream exposes this natively.",
    },
    {
        "seam": "GET /api/auth/registration-config",
        "upstream": "GET /api/auth/registration-config",
        "status": "matches",
        "note": "Upstream exposes this natively.",
    },
    {
        "seam": "GET /api/auth/me",
        "upstream": "GET /api/auth/me",
        "status": "blocked_by_auth",
        "note": "Present upstream but requires bearer token.",
    },
    {
        "seam": "GET /api/enterprise/llm-models",
        "upstream": "GET /api/enterprise/llm-models",
        "status": "blocked_by_auth",
        "note": "Present upstream but auth-gated; model pool may be empty.",
    },
    {
        "seam": "GET /api/admin/companies",
        "upstream": "GET /api/admin/companies",
        "status": "blocked_by_auth",
        "note": "Present upstream; 200 for platform_admin, 403 otherwise.",
    },
    {
        "seam": "POST /api/roles",
        "upstream": "—",
        "status": "missing_upstream",
        "note": "Not observed in upstream Clawith. Adapter/shim required.",
    },
    {
        "seam": "POST /api/scenarios",
        "upstream": "—",
        "status": "missing_upstream",
        "note": "Not observed in upstream Clawith. Adapter/shim required.",
    },
    {
        "seam": "PATCH /api/runs/{run_id}",
        "upstream": "—",
        "status": "missing_upstream",
        "note": "Not observed in upstream Clawith. Adapter/shim required.",
    },
    {
        "seam": "GET /api/enterprise/llm-providers",
        "upstream": "GET /api/enterprise/llm-providers",
        "status": "blocked_by_auth",
        "note": "Present upstream but auth-gated.",
    },
    {
        "seam": "POST /api/auth/register",
        "upstream": "POST /api/auth/register",
        "status": "adapter_needed",
        "note": "Upstream accepts registration; first user becomes platform_admin. "
        "Role Foundry does not call this automatically.",
    },
    {
        "seam": "POST /api/auth/login",
        "upstream": "POST /api/auth/login",
        "status": "adapter_needed",
        "note": "Upstream exposes login. Role Foundry probe uses this only when "
        "explicit credentials are supplied.",
    },
]


def _get(url: str, *, timeout: float = 5.0) -> dict[str, Any]:
    """Perform a GET request. Never issues writes."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return {
                "reachable": True,
                "status": resp.status,
                "json": _parse_json(raw),
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return {
            "reachable": True,
            "status": exc.code,
            "json": _parse_json(raw),
        }
    except Exception as exc:
        return {
            "reachable": False,
            "status": None,
            "json": None,
            "error": str(exc),
        }


def _parse_json(raw: bytes) -> Any | None:
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def check_base_url_reachable(base_url: str, timeout: float) -> dict[str, Any]:
    """F001 check 1: base URL reachable."""
    result = _get(f"{base_url}/api/health", timeout=timeout)
    if result["reachable"] and result["status"] == 200:
        status = "ready"
    elif result["reachable"]:
        status = "blocked"
    else:
        status = "unknown"
    return {
        "check": "base_url_reachable",
        "status": status,
        "detail": result,
    }


def check_auth_surface_understood(base_url: str, timeout: float) -> dict[str, Any]:
    """F001 check 2: auth surface understood."""
    reg = _get(f"{base_url}/api/auth/registration-config", timeout=timeout)
    me = _get(f"{base_url}/api/auth/me", timeout=timeout)

    # We understand the auth surface if registration-config is 200
    # and /api/auth/me returns 401 (bearer challenge) when unauthenticated.
    if (
        reg["reachable"]
        and reg["status"] == 200
        and me["reachable"]
        and me["status"] == 401
    ):
        status = "ready"
    elif reg["reachable"] or me["reachable"]:
        status = "blocked"
    else:
        status = "unknown"
    return {
        "check": "auth_surface_understood",
        "status": status,
        "detail": {
            "registration_config": reg,
            "auth_me_unauthenticated": me,
        },
    }


def check_admin_presence_known(base_url: str, timeout: float) -> dict[str, Any]:
    """F001 check 3: admin presence known.

    Without auth or DB access, this is honestly 'unknown'.
    """
    # We can only know admin presence via authenticated probe or DB.
    # GET-only unauthenticated: we cannot determine this.
    companies = _get(f"{base_url}/api/admin/companies", timeout=timeout)
    if companies["reachable"] and companies["status"] == 200:
        # Authenticated as admin — admin exists
        status = "ready"
    elif companies["reachable"] and companies["status"] in {401, 403}:
        # Auth-gated — admin presence unknown from this vantage
        status = "unknown"
    else:
        status = "unknown"
    return {
        "check": "admin_presence_known",
        "status": status,
        "detail": {"admin_companies": companies},
        "note": "Admin presence cannot be determined without auth or DB access."
        if status == "unknown"
        else "",
    }


def check_model_pool_presence_known(base_url: str, timeout: float) -> dict[str, Any]:
    """F001 check 4: model-pool presence known."""
    models = _get(f"{base_url}/api/enterprise/llm-models", timeout=timeout)
    if models["reachable"] and models["status"] == 200:
        payload = models["json"]
        if isinstance(payload, list) and len(payload) > 0:
            status = "ready"
        elif isinstance(payload, list) and len(payload) == 0:
            status = "blocked"
        else:
            status = "unknown"
    elif models["reachable"] and models["status"] in {401, 403}:
        status = "unknown"
    else:
        status = "unknown"
    return {
        "check": "model_pool_presence_known",
        "status": status,
        "detail": {"llm_models": models},
        "note": "Model pool cannot be determined without auth."
        if status == "unknown"
        else "",
    }


def check_endpoint_mismatch_documented() -> dict[str, Any]:
    """F001 check 5: endpoint mismatch documented.

    This check verifies the seam mapping is populated and all missing
    upstream endpoints are explicitly documented.
    """
    missing = [
        row for row in SEAM_MAPPING if row["status"] == "missing_upstream"
    ]
    # The mismatch is documented if we have at least one missing_upstream entry
    # (we know Role Foundry needs these and upstream doesn't have them).
    if missing:
        status = "ready"
    else:
        # If no mismatches found, either everything matches (good) or
        # we haven't checked (unknown).
        has_any = len(SEAM_MAPPING) > 0
        status = "ready" if has_any else "unknown"
    return {
        "check": "endpoint_mismatch_documented",
        "status": status,
        "detail": {
            "documented_mismatches": [row["seam"] for row in missing],
            "total_seam_rows": len(SEAM_MAPPING),
        },
    }


def check_status_categorization(checks: list[dict[str, Any]]) -> dict[str, Any]:
    """F001 check 6: status output clearly categorized as ready/blocked/unknown."""
    all_valid = all(c["status"] in ALLOWED_STATUSES for c in checks)
    return {
        "check": "status_categorization_valid",
        "status": "ready" if all_valid else "blocked",
        "detail": {
            "all_statuses_valid": all_valid,
            "allowed_statuses": sorted(ALLOWED_STATUSES),
        },
    }


def compute_overall_readiness(checks: list[dict[str, Any]]) -> str:
    """Derive overall readiness from individual checks.

    F002 rule: never return 'ready' if any required check is blocked or unknown.
    """
    statuses = [c["status"] for c in checks]
    if any(s == "blocked" for s in statuses):
        return "blocked"
    if any(s == "unknown" for s in statuses):
        return "unknown"
    return "ready"


def validate_mapping_statuses() -> dict[str, Any]:
    """F003: verify all mapping rows use allowed statuses only."""
    invalid = [
        row for row in SEAM_MAPPING if row["status"] not in ALLOWED_MAPPING_STATUSES
    ]
    return {
        "all_valid": len(invalid) == 0,
        "total_rows": len(SEAM_MAPPING),
        "invalid_rows": invalid,
    }


def build_report(
    base_url: str, timeout: float, *, offline: bool = False
) -> dict[str, Any]:
    """Build the full readiness report."""
    if offline:
        checks = [
            {"check": "base_url_reachable", "status": "unknown", "detail": {}, "note": "offline mode"},
            {"check": "auth_surface_understood", "status": "unknown", "detail": {}, "note": "offline mode"},
            {"check": "admin_presence_known", "status": "unknown", "detail": {}, "note": "offline mode"},
            {"check": "model_pool_presence_known", "status": "unknown", "detail": {}, "note": "offline mode"},
            check_endpoint_mismatch_documented(),
            {"check": "status_categorization_valid", "status": "ready", "detail": {}, "note": "offline mode"},
        ]
    else:
        checks = [
            check_base_url_reachable(base_url, timeout),
            check_auth_surface_understood(base_url, timeout),
            check_admin_presence_known(base_url, timeout),
            check_model_pool_presence_known(base_url, timeout),
            check_endpoint_mismatch_documented(),
        ]
        checks.append(check_status_categorization(checks))

    overall = compute_overall_readiness(checks)
    mapping_validation = validate_mapping_statuses()

    return {
        "phase": "F",
        "base_url": base_url,
        "overall_readiness": overall,
        "checks": checks,
        "seam_mapping": SEAM_MAPPING,
        "mapping_validation": mapping_validation,
        "non_destructive": True,
        "http_methods_used": ["GET"],
    }


def print_human(report: dict[str, Any]) -> None:
    """Human-readable output."""
    print(f"Phase F — Clawith Adapter-First Bring-up Readiness")
    print(f"{'=' * 52}")
    print(f"Base URL:          {report['base_url']}")
    print(f"Overall readiness: {report['overall_readiness']}")
    print(f"Non-destructive:   {report['non_destructive']}")
    print(f"HTTP methods used: {', '.join(report['http_methods_used'])}")
    print()

    print("PREREQ CHECKS (F001)")
    for c in report["checks"]:
        tag = {"ready": "OK", "blocked": "!!", "unknown": "??"}[c["status"]]
        line = f"  [{tag}] {c['check']}: {c['status']}"
        note = c.get("note", "")
        if note:
            line += f"  — {note}"
        print(line)

    print()
    print("SEAM-TO-UPSTREAM MAPPING (F003)")
    print(f"  {'Seam':<38} {'Status':<20} Note")
    print(f"  {'-' * 37} {'-' * 19} {'-' * 40}")
    for row in report["seam_mapping"]:
        print(f"  {row['seam']:<38} {row['status']:<20} {row['note']}")

    mv = report["mapping_validation"]
    if not mv["all_valid"]:
        print()
        print("  WARNING: invalid mapping statuses found:")
        for row in mv["invalid_rows"]:
            print(f"    {row['seam']}: {row['status']}")

    print()
    print("NON-CLAIMS")
    print("  - This probe does NOT claim native upstream Role Foundry parity.")
    print("  - POST /api/roles, POST /api/scenarios, PATCH /api/runs/{run_id}")
    print("    are adapter-side assumptions, not upstream contracts.")
    print("  - Admin/model-pool presence is 'unknown' without auth or DB access.")
    print("  - This script performs GET requests only (F004).")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase F readiness checker — GET-only, non-destructive"
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CLAWITH_URL", "http://localhost:3000"),
    )
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip network checks; report unknown for all network-dependent checks",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    report = build_report(base_url, args.timeout, offline=args.offline)

    if args.json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print_human(report)

    if report["overall_readiness"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

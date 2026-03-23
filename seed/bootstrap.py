#!/usr/bin/env python3
"""
Role Foundry — Seed Bootstrap / Dry-Run Planner

This script validates the Role Foundry seed payload and can show the legacy
write plan Role Foundry would use against a *custom Clawith-compatible shim*.

Important honesty note:
- stock upstream Clawith does not expose `/api/roles` or `/api/scenarios`
- so `--seed` is **not** a native-upstream claim; it only makes sense if you
  explicitly point this at a shim that implements those paths
- for upstream bring-up, use `seed/probe_clawith.py` first

Usage:
  # Validate seed data only (no Clawith needed):
    python3 seed/bootstrap.py --validate

  # Show the legacy write plan without sending writes:
    python3 seed/bootstrap.py --seed --dry-run --clawith-url http://localhost:3000

  # Attempt a legacy write against a custom compatibility shim only:
    python3 seed/bootstrap.py --seed --clawith-url http://localhost:3000

Environment variables:
  CLAWITH_URL       — Clawith API base URL (default: http://localhost:3000)
  CLAWITH_SECRET    — Optional bearer secret for a custom compatibility shim
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SEED_FILE = Path(__file__).parent / "role-foundry-apprentice.json"
LEGACY_ROLE_PATH = "/api/roles"
LEGACY_SCENARIO_PATH = "/api/scenarios"


def load_seed():
    with open(SEED_FILE) as f:
        return json.load(f)


def validate(data):
    errors = []

    role = data.get("role")
    if not role:
        errors.append("missing 'role' key")
    else:
        for field in ("id", "name", "description", "goals", "success_criteria"):
            if not role.get(field):
                errors.append(f"role missing '{field}'")

    scenarios = data.get("scenarios", [])
    training = [s for s in scenarios if s.get("type") == "training"]
    holdouts = [s for s in scenarios if s.get("type") == "holdout"]

    if len(training) < 6:
        errors.append(f"need >= 6 training scenarios, got {len(training)}")
    if len(holdouts) < 3:
        errors.append(f"need >= 3 holdout scenarios, got {len(holdouts)}")

    for s in scenarios:
        for field in ("id", "title", "description", "type", "difficulty"):
            if not s.get(field):
                errors.append(f"scenario {s.get('id', '?')} missing '{field}'")
        if s.get("type") not in ("training", "holdout"):
            errors.append(f"scenario {s['id']} has invalid type '{s['type']}'")

    ids = [s["id"] for s in scenarios if "id" in s]
    if len(ids) != len(set(ids)):
        errors.append("duplicate scenario IDs found")

    return errors


def student_facing_payload(data):
    """Return the payload a student-facing endpoint would serve (no holdout details)."""
    return {
        "role": data["role"],
        "scenarios": [
            {
                "id": s["id"],
                "title": s["title"],
                "description": s["description"],
                "type": s["type"],
                "difficulty": s["difficulty"],
            }
            for s in data["scenarios"]
            if s["type"] == "training"
        ],
    }


def check_holdout_exclusion(data):
    """Verify holdout prompts are excluded from student-facing payload."""
    payload = student_facing_payload(data)
    payload_str = json.dumps(payload)
    holdout_titles = [s["title"] for s in data["scenarios"] if s["type"] == "holdout"]
    leaked = [t for t in holdout_titles if t in payload_str]
    return leaked


def _probe_path(base_url: str, path: str):
    req = urllib.request.Request(f"{base_url.rstrip('/')}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        return None, str(e)


def detect_legacy_seed_contract(base_url: str):
    """Safely check whether the legacy Role Foundry write paths even exist.

    GET is enough for a conservative probe here:
    - 404 strongly suggests the path is absent
    - 405/401/403/200 means the path exists, though the method/auth may differ
    """
    findings = {}
    for path in (LEGACY_ROLE_PATH, LEGACY_SCENARIO_PATH):
        status, body = _probe_path(base_url, path)
        findings[path] = {
            "status": status,
            "present": status in {200, 401, 403, 405},
            "body": body[:200],
        }
    return findings


def seed_clawith(data, base_url, secret, dry_run=False):
    """Seed role + scenarios into a custom compatibility shim only."""
    headers = {
        "Content-Type": "application/json",
    }
    if secret:
        headers["Authorization"] = f"Bearer {secret}"

    if dry_run:
        print(f"[dry-run] Legacy shim contract target: {base_url}")
        print(f"[dry-run] Would POST role to {base_url}{LEGACY_ROLE_PATH}")
        print(f"[dry-run]   {data['role']['name']}")
        for s in data["scenarios"]:
            print(f"[dry-run] Would POST scenario to {base_url}{LEGACY_SCENARIO_PATH}")
            print(f"[dry-run]   {s['id']}: {s['title']} ({s['type']})")
        print("[dry-run] Note: stock upstream Clawith does not natively expose these paths.")
        return True

    contract = detect_legacy_seed_contract(base_url)
    missing = [path for path, info in contract.items() if not info["present"]]
    if missing:
        print(
            "  REFUSING write attempt: target does not expose the legacy Role Foundry seed paths:",
            file=sys.stderr,
        )
        for path in missing:
            info = contract[path]
            print(f"    - {path}: status={info['status']} body={info['body']!r}", file=sys.stderr)
        print(
            "  This is expected for stock upstream Clawith. Use seed/probe_clawith.py for read-only upstream checks.",
            file=sys.stderr,
        )
        return False

    role_payload = json.dumps(data["role"]).encode()
    scenario_payloads = [json.dumps(s).encode() for s in data["scenarios"]]

    try:
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}{LEGACY_ROLE_PATH}",
            data=role_payload,
            headers=headers,
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"  Seeded role: {data['role']['name']}")
    except urllib.error.URLError as e:
        print(f"  FAILED to seed role: {e}", file=sys.stderr)
        return False

    ok = True
    for s, payload in zip(data["scenarios"], scenario_payloads):
        try:
            req = urllib.request.Request(
                f"{base_url.rstrip('/')}{LEGACY_SCENARIO_PATH}",
                data=payload,
                headers=headers,
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
            print(f"  Seeded scenario: {s['id']} ({s['type']})")
        except urllib.error.URLError as e:
            print(f"  FAILED to seed {s['id']}: {e}", file=sys.stderr)
            ok = False

    return ok


def main():
    parser = argparse.ArgumentParser(description="Role Foundry seed bootstrap / dry-run planner")
    parser.add_argument("--validate", action="store_true", help="Validate seed data only")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Attempt the legacy Role Foundry write contract against a custom shim",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent")
    parser.add_argument(
        "--clawith-url",
        default=os.environ.get("CLAWITH_URL", "http://localhost:3000"),
    )
    args = parser.parse_args()

    if not args.validate and not args.seed:
        args.validate = True

    data = load_seed()

    # Always validate first
    print(f"Validating {SEED_FILE.name}...")
    errors = validate(data)
    if errors:
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    training = [s for s in data["scenarios"] if s["type"] == "training"]
    holdouts = [s for s in data["scenarios"] if s["type"] == "holdout"]
    print(f"  Role: {data['role']['name']}")
    print(f"  Training scenarios: {len(training)}")
    print(f"  Holdout scenarios: {len(holdouts)}")

    leaked = check_holdout_exclusion(data)
    if leaked:
        print(f"  WARNING: holdout titles leak into student payload: {leaked}", file=sys.stderr)
        sys.exit(1)
    print("  Holdout exclusion: OK (student payload contains no holdout details)")

    print("  Validation: PASS")

    if args.seed:
        secret = os.environ.get("CLAWITH_SECRET", "")
        print(f"\nLegacy write-plan target: {args.clawith_url}")
        ok = seed_clawith(data, args.clawith_url, secret, dry_run=args.dry_run)
        if not ok:
            print("Legacy seed flow failed.", file=sys.stderr)
            sys.exit(1)
        print("Legacy seed flow: DONE")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Role Foundry — Seed Bootstrap

Validates and optionally seeds the apprentice role + scenarios into Clawith.

Usage:
  # Validate seed data only (no Clawith needed):
    python3 seed/bootstrap.py --validate

  # Seed into a running Clawith instance:
    python3 seed/bootstrap.py --seed --clawith-url http://localhost:3000

  # Dry-run (show what would be sent):
    python3 seed/bootstrap.py --seed --clawith-url http://localhost:3000 --dry-run

Environment variables (for live mode):
  CLAWITH_URL       — Clawith API base URL (default: http://localhost:3000)
  CLAWITH_SECRET    — Machine-to-machine auth secret
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

SEED_FILE = Path(__file__).parent / "role-foundry-apprentice.json"


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


def seed_clawith(data, base_url, secret, dry_run=False):
    """Seed role + scenarios into Clawith API."""
    headers = {
        "Content-Type": "application/json",
    }
    if secret:
        headers["Authorization"] = f"Bearer {secret}"

    role_payload = json.dumps(data["role"]).encode()
    scenario_payloads = [json.dumps(s).encode() for s in data["scenarios"]]

    if dry_run:
        print(f"[dry-run] Would POST role to {base_url}/api/roles")
        print(f"[dry-run]   {data['role']['name']}")
        for s in data["scenarios"]:
            print(f"[dry-run] Would POST scenario to {base_url}/api/scenarios")
            print(f"[dry-run]   {s['id']}: {s['title']} ({s['type']})")
        return True

    try:
        req = urllib.request.Request(
            f"{base_url}/api/roles",
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
                f"{base_url}/api/scenarios",
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
    parser = argparse.ArgumentParser(description="Role Foundry seed bootstrap")
    parser.add_argument("--validate", action="store_true", help="Validate seed data only")
    parser.add_argument("--seed", action="store_true", help="Seed into Clawith")
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
        print(f"\nSeeding into {args.clawith_url}...")
        ok = seed_clawith(data, args.clawith_url, secret, dry_run=args.dry_run)
        if not ok:
            print("Seeding failed.", file=sys.stderr)
            sys.exit(1)
        print("Seeding: DONE")


if __name__ == "__main__":
    main()

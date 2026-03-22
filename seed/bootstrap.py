#!/usr/bin/env python3
"""
Role Foundry — Seed Bootstrap

Validates and optionally seeds the Frontend Apprentice canonical dataset pack into a
Clawith-compatible control plane.

Usage:
  # Validate canonical pack only (no control plane needed):
    python3 seed/bootstrap.py --validate

  # Seed into a running Clawith-compatible endpoint:
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
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runner_bridge.dataset_pack import (  # noqa: E402
    DEFAULT_PACK_PATH,
    check_holdout_exclusion,
    export_seed_payload,
    load_pack,
    manifest,
    validate_seed_payload,
)

SEED_FILE = Path(__file__).parent / "role-foundry-apprentice.json"


def load_seed(pack_path: str | Path = DEFAULT_PACK_PATH):
    pack = load_pack(pack_path)
    return export_seed_payload(pack), manifest(pack)


def seed_clawith(data, base_url, secret, dry_run=False):
    """Seed role + scenarios into a Clawith-compatible API."""
    headers = {
        "Content-Type": "application/json",
    }
    if secret:
        headers["Authorization"] = f"Bearer {secret}"

    role_payload = json.dumps(data["role"]).encode()
    scenario_payloads = [json.dumps(scenario).encode() for scenario in data["scenarios"]]

    if dry_run:
        print(f"[dry-run] Would POST role to {base_url}/api/roles")
        print(f"[dry-run]   {data['role']['name']}")
        for scenario in data["scenarios"]:
            print(f"[dry-run] Would POST scenario to {base_url}/api/scenarios")
            print(f"[dry-run]   {scenario['id']}: {scenario['title']} ({scenario['type']})")
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
    except urllib.error.URLError as exc:
        print(f"  FAILED to seed role: {exc}", file=sys.stderr)
        return False

    ok = True
    for scenario, payload in zip(data["scenarios"], scenario_payloads):
        try:
            req = urllib.request.Request(
                f"{base_url}/api/scenarios",
                data=payload,
                headers=headers,
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
            print(f"  Seeded scenario: {scenario['id']} ({scenario['type']})")
        except urllib.error.URLError as exc:
            print(f"  FAILED to seed {scenario['id']}: {exc}", file=sys.stderr)
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
    parser.add_argument(
        "--pack",
        default=str(DEFAULT_PACK_PATH),
        help="Path to the canonical Frontend Apprentice dataset pack",
    )
    args = parser.parse_args()

    if not args.validate and not args.seed:
        args.validate = True

    data, pack_manifest = load_seed(args.pack)

    print(f"Validating {Path(args.pack).name}...")
    errors = validate_seed_payload(data)
    if errors:
        for error in errors:
            print(f"  ERROR: {error}", file=sys.stderr)
        sys.exit(1)

    training = [scenario for scenario in data["scenarios"] if scenario["type"] == "training"]
    holdouts = [scenario for scenario in data["scenarios"] if scenario["type"] == "holdout"]
    print(f"  Dataset manifest: {pack_manifest.get('id')}")
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

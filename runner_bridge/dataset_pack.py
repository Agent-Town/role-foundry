from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_PATH = REPO_ROOT / "datasets" / "frontend-apprentice" / "alpha-pack.json"
DERIVED_EXPORT_PATHS = {
    "seed_payload": REPO_ROOT / "seed" / "role-foundry-apprentice.json",
    "first_live_run": REPO_ROOT / "runner_bridge" / "examples" / "first-live-run.json",
    "teacher_eval_baseline": REPO_ROOT / "runner_bridge" / "examples" / "teacher-eval-baseline.json",
    "teacher_eval_loop": REPO_ROOT / "runner_bridge" / "examples" / "teacher-eval-loop.json",
}


def load_pack(path: str | Path = DEFAULT_PACK_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def manifest(pack: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(pack.get("manifest", {}))


def export_seed_payload(pack: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(pack.get("seed_payload", {}))


def export_request(pack: dict[str, Any], request_name: str) -> dict[str, Any]:
    requests = pack.get("requests", {})
    if request_name not in requests:
        raise KeyError(f"unknown request export: {request_name}")
    return deepcopy(requests[request_name])


def validate_seed_payload(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

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

    for scenario in scenarios:
        for field in ("id", "title", "description", "type", "difficulty"):
            if not scenario.get(field):
                errors.append(f"scenario {scenario.get('id', '?')} missing '{field}'")
        if scenario.get("type") not in ("training", "holdout"):
            errors.append(f"scenario {scenario.get('id', '?')} has invalid type '{scenario.get('type')}'")

    ids = [scenario["id"] for scenario in scenarios if "id" in scenario]
    if len(ids) != len(set(ids)):
        errors.append("duplicate scenario IDs found")

    manifest_id = data.get("meta", {}).get("dataset_manifest_id")
    if not manifest_id:
        errors.append("seed payload missing meta.dataset_manifest_id")

    return errors


def student_facing_seed_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": data["role"],
        "scenarios": [
            {
                "id": scenario["id"],
                "title": scenario["title"],
                "description": scenario["description"],
                "type": scenario["type"],
                "difficulty": scenario["difficulty"],
            }
            for scenario in data["scenarios"]
            if scenario["type"] == "training"
        ],
    }


def check_holdout_exclusion(data: dict[str, Any]) -> list[str]:
    payload = student_facing_seed_payload(data)
    payload_str = json.dumps(payload)
    holdout_titles = [scenario["title"] for scenario in data["scenarios"] if scenario["type"] == "holdout"]
    return [title for title in holdout_titles if title in payload_str]


def write_derived_exports(path: str | Path = DEFAULT_PACK_PATH) -> None:
    pack = load_pack(path)
    export_seed = export_seed_payload(pack)
    DERIVED_EXPORT_PATHS["seed_payload"].write_text(json.dumps(export_seed, indent=2) + "\n")
    for request_name in ("first_live_run", "teacher_eval_baseline", "teacher_eval_loop"):
        DERIVED_EXPORT_PATHS[request_name].write_text(
            json.dumps(export_request(pack, request_name), indent=2) + "\n"
        )


def exported_files_match(path: str | Path = DEFAULT_PACK_PATH) -> list[str]:
    pack = load_pack(path)
    mismatches: list[str] = []

    expected = {
        DERIVED_EXPORT_PATHS["seed_payload"]: export_seed_payload(pack),
        DERIVED_EXPORT_PATHS["first_live_run"]: export_request(pack, "first_live_run"),
        DERIVED_EXPORT_PATHS["teacher_eval_baseline"]: export_request(pack, "teacher_eval_baseline"),
        DERIVED_EXPORT_PATHS["teacher_eval_loop"]: export_request(pack, "teacher_eval_loop"),
    }

    for file_path, payload in expected.items():
        actual = json.loads(file_path.read_text()) if file_path.exists() else None
        if actual != payload:
            mismatches.append(str(file_path))
    return mismatches


def _describe(path: str | Path = DEFAULT_PACK_PATH) -> dict[str, Any]:
    pack = load_pack(path)
    info = manifest(pack)
    info["pack_path"] = str(Path(path))
    info["derived_files_in_sync"] = exported_files_match(path) == []
    return info


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Frontend Apprentice canonical dataset pack helper")
    parser.add_argument(
        "command",
        choices=["describe", "export", "check"],
        nargs="?",
        default="describe",
    )
    parser.add_argument("--pack", default=str(DEFAULT_PACK_PATH), help="Path to the canonical dataset pack")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pack_path = Path(args.pack)

    if args.command == "export":
        write_derived_exports(pack_path)
        print(json.dumps(_describe(pack_path), indent=2))
        return 0

    if args.command == "check":
        mismatches = exported_files_match(pack_path)
        if mismatches:
            print(json.dumps({"ok": False, "mismatches": mismatches}, indent=2))
            return 1
        print(json.dumps({"ok": True, "pack": _describe(pack_path)}, indent=2))
        return 0

    print(json.dumps(_describe(pack_path), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

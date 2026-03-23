#!/usr/bin/env python3
"""Local-only holdout authoring helper.

Commands:
    init     — scaffold a fresh holdout manifest from the public template
    audit    — check the local manifest for leakage + schema conformance
    status   — summarize what exists locally vs what is tracked

This script never writes to tracked paths. It only touches files under
benchmarks/private-holdout-pack/ (which is gitignored).
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "benchmarks" / "private-holdout-pack-template.json"
PRIVATE_DIR = ROOT / "benchmarks" / "private-holdout-pack"
MANIFEST = PRIVATE_DIR / "holdout-manifest.json"
EPISODES_DIR = PRIVATE_DIR / "episodes"
GITIGNORE = ROOT / ".gitignore"

# ── Repo-visible strings that must NOT appear in teacher-only content ──
# These are the h1/h2/h3 family ids from the public registry. If a local
# holdout episode references them verbatim, the episode is likely a clone
# rather than a fresh rewrite.
BLOCKED_FAMILY_IDS = {
    "rf.frontend-apprentice.blocked.teacher-only-h1",
    "rf.frontend-apprentice.blocked.teacher-only-h2",
    "rf.frontend-apprentice.blocked.teacher-only-h3",
}

REQUIRED_EPISODE_KEYS = {
    "id", "family_id", "title", "teacher_prompt",
    "scoring_rubric", "difficulty",
}

VALID_DIFFICULTIES = {"easy", "medium", "hard"}


# ─────────────────────────── helpers ───────────────────────────

def _err(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def _ok(msg: str) -> None:
    print(f"  OK: {msg}")


def _warn(msg: str) -> None:
    print(f"WARN: {msg}", file=sys.stderr)


def _git_tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached"],
        capture_output=True, text=True, cwd=ROOT,
    )
    return result.stdout.strip().splitlines()


def _is_gitignored() -> bool:
    text = GITIGNORE.read_text() if GITIGNORE.exists() else ""
    return "benchmarks/private-holdout-pack/" in text


# ─────────────────────────── init ──────────────────────────────

def cmd_init(args: argparse.Namespace) -> int:
    if MANIFEST.exists() and not args.force:
        _err(f"Manifest already exists at {MANIFEST.relative_to(ROOT)}")
        _err("Use --force to overwrite.")
        return 1

    if not TEMPLATE.exists():
        _err(f"Public template not found at {TEMPLATE.relative_to(ROOT)}")
        return 1

    if not _is_gitignored():
        _err("benchmarks/private-holdout-pack/ is NOT in .gitignore — refusing to init.")
        return 1

    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    EPISODES_DIR.mkdir(parents=True, exist_ok=True)

    template = json.loads(TEMPLATE.read_text())

    # Stamp the manifest with a fresh id and bump version
    template["meta"]["id"] = f"private-holdout-pack-v{args.version}"
    template["meta"]["version"] = args.version
    template["_template_note"] = (
        "LOCAL-ONLY manifest. Do not commit. "
        "Replace placeholder episodes with fresh teacher-only content."
    )

    MANIFEST.write_text(json.dumps(template, indent=2) + "\n")
    print(f"Initialized holdout manifest at {MANIFEST.relative_to(ROOT)}")
    print(f"Episodes directory at {EPISODES_DIR.relative_to(ROOT)}/")
    print()
    print("Next steps:")
    print("  1. Edit the manifest — replace REPLACE-ME placeholders with fresh episodes")
    print("  2. Use NEW wording — do not clone h1/h2/h3 framing")
    print("  3. Run: python3 scripts/holdout_author.py audit")
    return 0


# ─────────────────────────── audit ─────────────────────────────

def cmd_audit(_args: argparse.Namespace) -> int:
    errors = 0

    # 1. Gitignore check
    if _is_gitignored():
        _ok("benchmarks/private-holdout-pack/ is gitignored")
    else:
        _err("benchmarks/private-holdout-pack/ is NOT gitignored")
        errors += 1

    # 2. No tracked files in private dir
    tracked = _git_tracked_files()
    leaked = [f for f in tracked if f.startswith("benchmarks/private-holdout-pack/")]
    if leaked:
        _err(f"Private holdout files are tracked by git: {leaked}")
        errors += 1
    else:
        _ok("No private holdout files are tracked by git")

    # 3. No teacher keys in tracked benchmark JSON (except template)
    forbidden_keys = {"teacher_prompt", "scoring_rubric"}
    benchmark_jsons = [
        ROOT / f for f in tracked
        if f.startswith("benchmarks/") and f.endswith(".json")
    ]
    for path in benchmark_jsons:
        if path == TEMPLATE:
            continue
        text = path.read_text()
        for key in forbidden_keys:
            if f'"{key}"' in text:
                _err(f"Tracked file {path.relative_to(ROOT)} contains forbidden key '{key}'")
                errors += 1
    if errors == 0:
        _ok("No tracked benchmark JSON leaks teacher-only keys")

    # 4. Manifest schema check (if exists)
    if not MANIFEST.exists():
        _warn("No local manifest found — run 'init' first to scaffold one")
        return errors

    manifest = json.loads(MANIFEST.read_text())
    meta = manifest.get("meta", {})

    if meta.get("visibility") != "teacher_only":
        _err("Manifest meta.visibility must be 'teacher_only'")
        errors += 1
    else:
        _ok("meta.visibility is teacher_only")

    if meta.get("public_repo_safe") is not False:
        _err("Manifest meta.public_repo_safe must be false")
        errors += 1
    else:
        _ok("meta.public_repo_safe is false")

    episodes = manifest.get("episodes", [])
    if not episodes:
        _warn("Manifest has no episodes")
    else:
        _ok(f"Manifest has {len(episodes)} episode(s)")

    placeholder_count = 0
    for i, ep in enumerate(episodes):
        ep_label = ep.get("id", f"episodes[{i}]")

        # Required keys
        missing = REQUIRED_EPISODE_KEYS - set(ep.keys())
        if missing:
            _err(f"Episode '{ep_label}' missing keys: {missing}")
            errors += 1

        # Still a placeholder?
        if ep.get("_placeholder") or "REPLACE-ME" in str(ep.get("id", "")):
            placeholder_count += 1
            _warn(f"Episode '{ep_label}' is still a placeholder")
            continue

        # Family id must not be a blocked clone
        fid = ep.get("family_id", "")
        if fid in BLOCKED_FAMILY_IDS:
            _err(
                f"Episode '{ep_label}' references blocked family '{fid}' — "
                "author a fresh family instead of cloning h1/h2/h3"
            )
            errors += 1

        # Difficulty
        diff = ep.get("difficulty", "")
        if diff not in VALID_DIFFICULTIES:
            _err(f"Episode '{ep_label}' has invalid difficulty '{diff}'")
            errors += 1

        # Teacher prompt must not be empty or placeholder
        prompt = ep.get("teacher_prompt", "")
        if not prompt or "REPLACE-ME" in prompt:
            _err(f"Episode '{ep_label}' has empty/placeholder teacher_prompt")
            errors += 1

        # Scoring rubric must not be empty dict
        rubric = ep.get("scoring_rubric", {})
        if not rubric or rubric == {}:
            _err(f"Episode '{ep_label}' has empty scoring_rubric")
            errors += 1

    if placeholder_count == len(episodes):
        _warn("All episodes are still placeholders — no real content authored yet")

    # 5. Cross-check: does any teacher_prompt text appear in tracked files?
    real_prompts = [
        ep["teacher_prompt"] for ep in episodes
        if not ep.get("_placeholder") and "REPLACE-ME" not in str(ep.get("id", ""))
        and len(ep.get("teacher_prompt", "")) > 20
    ]
    if real_prompts:
        all_tracked_text = ""
        for f in tracked:
            try:
                all_tracked_text += (ROOT / f).read_text()
            except (UnicodeDecodeError, FileNotFoundError):
                continue
        for prompt in real_prompts:
            # Check for substantial substring leakage (first 60 chars)
            snippet = prompt[:60]
            if snippet in all_tracked_text:
                _err(f"Teacher prompt snippet found in tracked files: '{snippet[:40]}...'")
                errors += 1
        if errors == 0:
            _ok("No teacher prompt text leaks into tracked files")

    print()
    if errors:
        print(f"AUDIT FAILED — {errors} error(s) found")
    else:
        print("AUDIT PASSED — holdout manifest is clean")
    return errors


# ─────────────────────────── status ────────────────────────────

def cmd_status(_args: argparse.Namespace) -> int:
    print("=== Private Holdout Authoring Status ===\n")

    # Gitignore
    ig = _is_gitignored()
    print(f"  .gitignore entry:  {'present' if ig else 'MISSING'}")
    print(f"  Template:          {'exists' if TEMPLATE.exists() else 'MISSING'}")
    print(f"  Private dir:       {'exists' if PRIVATE_DIR.exists() else 'not created'}")
    print(f"  Local manifest:    {'exists' if MANIFEST.exists() else 'not created'}")
    print(f"  Episodes dir:      {'exists' if EPISODES_DIR.exists() else 'not created'}")

    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text())
        episodes = manifest.get("episodes", [])
        real = [e for e in episodes if not e.get("_placeholder") and "REPLACE-ME" not in str(e.get("id", ""))]
        placeholders = len(episodes) - len(real)
        print(f"\n  Episodes total:    {len(episodes)}")
        print(f"  Real episodes:     {len(real)}")
        print(f"  Placeholders:      {placeholders}")
        print(f"  Pack version:      {manifest.get('meta', {}).get('version', '?')}")

    # Tracked leak check
    tracked = _git_tracked_files()
    leaked = [f for f in tracked if f.startswith("benchmarks/private-holdout-pack/")]
    if leaked:
        print(f"\n  !! LEAKED tracked files: {leaked}")
    else:
        print("\n  No private holdout files tracked by git")

    print()
    print("Safe-to-push (tracked):")
    print("  benchmarks/private-holdout-pack-template.json")
    print("  specs/012-private-holdout-pack.md")
    print("  tests/test_private_holdout_separation.py")
    print("  scripts/holdout_author.py")
    print("  docs/private-holdout-authoring.md")
    print()
    print("Local-only (gitignored, NEVER push):")
    print("  benchmarks/private-holdout-pack/holdout-manifest.json")
    print("  benchmarks/private-holdout-pack/episodes/*.json")
    return 0


# ─────────────────────────── main ──────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local-only holdout authoring helper",
    )
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Scaffold a fresh holdout manifest")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing manifest")
    p_init.add_argument("--version", default="1", help="Pack version (default: 1)")

    sub.add_parser("audit", help="Audit local manifest for leaks and schema issues")
    sub.add_parser("status", help="Show authoring status")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    return {"init": cmd_init, "audit": cmd_audit, "status": cmd_status}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

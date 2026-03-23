from __future__ import annotations

import json
import subprocess
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from .contract import ContractError


def build_packet_mutation_surface(packet_runtime: dict[str, Any] | None) -> dict[str, Any]:
    """Extract the mutation-surface contract from a packet_runtime block.

    The packet_runtime block is the frozen, versioned source of truth that the
    bridge carries forward from the task packet. This helper makes that surface
    explicit for downstream auditors and future live executors.
    """
    packet_runtime = packet_runtime if isinstance(packet_runtime, dict) else {}
    raw_budget = packet_runtime.get("mutation_budget") if isinstance(packet_runtime.get("mutation_budget"), dict) else {}
    return {
        "packet_id": str(packet_runtime.get("packet_id", "")),
        "packet_version": str(packet_runtime.get("packet_version", "")),
        "acceptance_test_id": str(packet_runtime.get("acceptance_test_id", "")),
        "allowed_paths": list(packet_runtime.get("allowed_paths", []) or []),
        "blocked_paths": list(packet_runtime.get("blocked_paths", []) or []),
        "mutation_budget": {
            "tracked_files_max": int(raw_budget.get("tracked_files_max", raw_budget.get("max_files", 6))),
            "net_lines_max": int(raw_budget.get("net_lines_max", raw_budget.get("max_lines", 400))),
            "overrides_default": bool(raw_budget.get("overrides_default", False)),
            "override_reason": raw_budget.get("override_reason"),
        },
    }


def audit_packet_mutation_surface(
    packet_runtime: dict[str, Any] | None,
    *,
    workspace_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit the actual changed-file surface against the packet contract.

    Honest behavior:
    - if a real git worktree diff is available, evaluate it against allowed /
      blocked paths and the mutation budget.
    - if the current request only carries a narrative snapshot and no diffable
      worktree metadata, report `status=unavailable` instead of implying the
      surface passed.

    Future live executors can reuse this helper by populating the workspace
    snapshot with a git worktree path + base commit.
    """
    surface = build_packet_mutation_surface(packet_runtime)
    snapshot = workspace_snapshot if isinstance(workspace_snapshot, dict) else {}
    worktree_meta = _resolve_git_worktree(snapshot)
    if worktree_meta is None:
        return _unavailable_audit(
            surface,
            reason=(
                "No diffable git worktree metadata was provided in workspace_snapshot. "
                "This run cannot honestly claim mutation-surface compliance."
            ),
        )

    worktree_path = worktree_meta["worktree_path"]
    base_commit = worktree_meta["base_commit"]
    try:
        diff_payload = _collect_git_diff(worktree_path, base_commit)
    except ContractError as exc:
        return _unavailable_audit(
            surface,
            reason=str(exc),
            source={
                "kind": "git_worktree_diff",
                "worktree_path": str(worktree_path),
                "base_commit": base_commit,
            },
        )

    changed_files = diff_payload["changed_files"]
    blocked_violations = [
        path for path in changed_files if _matches_any(path, surface["blocked_paths"])
    ]
    blocked_set = set(blocked_violations)
    out_of_scope = [
        path
        for path in changed_files
        if path not in blocked_set and not _matches_any(path, surface["allowed_paths"])
    ]

    diff_stats = diff_payload["diff_stats"]
    budget = surface["mutation_budget"]
    tracked_ok = diff_stats["tracked_files"] <= budget["tracked_files_max"]
    net_lines_ok = diff_stats["net_lines"] <= budget["net_lines_max"]
    within_budget = tracked_ok and net_lines_ok

    violations = {
        "blocked_paths": blocked_violations,
        "out_of_scope_paths": out_of_scope,
        "budget_exceeded": not within_budget,
    }
    status = "passed"
    if blocked_violations or out_of_scope or not within_budget:
        status = "violation"

    return {
        "status": status,
        "surface": surface,
        "source": diff_payload["source"],
        "changed_files": changed_files,
        "diff_stats": diff_stats,
        "budget_report": {
            "tracked_files_max": budget["tracked_files_max"],
            "tracked_files_used": diff_stats["tracked_files"],
            "tracked_files_within_budget": tracked_ok,
            "net_lines_max": budget["net_lines_max"],
            "net_lines_used": diff_stats["net_lines"],
            "net_lines_within_budget": net_lines_ok,
            "within_budget": within_budget,
            "additions": diff_stats["additions"],
            "deletions": diff_stats["deletions"],
        },
        "violations": violations,
        "honesty_note": (
            "Mutation-surface audit evaluated the actual git diff for this worktree. "
            "This is an audit result, not proof that the backend prevented the writes in real time."
        ),
    }


def write_mutation_surface_audit_receipt(run_dir: str | Path, audit: dict[str, Any]) -> str:
    """Persist the mutation-surface audit as a receipt artifact."""
    run_dir = Path(run_dir)
    receipts_dir = run_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    path = receipts_dir / "mutation-surface-audit.json"
    path.write_text(json.dumps(audit, indent=2))
    return path.relative_to(run_dir).as_posix()


def _resolve_git_worktree(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    candidates = []
    for key in ("workspace", "worktree"):
        value = snapshot.get(key)
        if isinstance(value, dict):
            candidates.append(value)
    candidates.append(snapshot)

    for candidate in candidates:
        kind = str(candidate.get("kind", "")).strip()
        raw_path = _first_nonempty(
            candidate.get("path"),
            candidate.get("root"),
            candidate.get("worktree_path"),
            candidate.get("repo_root"),
        )
        base_commit = _first_nonempty(
            candidate.get("base_commit"),
            candidate.get("base_ref"),
            candidate.get("diff_base"),
        )
        if not raw_path or not base_commit:
            continue
        if kind and kind not in {"git_worktree", "git_checkout", "git_repo"}:
            continue
        return {
            "kind": kind or "git_worktree",
            "worktree_path": Path(str(raw_path)).expanduser(),
            "base_commit": str(base_commit),
        }
    return None


def _collect_git_diff(worktree_path: Path, base_commit: str) -> dict[str, Any]:
    if not worktree_path.exists():
        raise ContractError(f"mutation audit worktree path does not exist: {worktree_path}")

    repo_root = _run_git(worktree_path, ["rev-parse", "--show-toplevel"]).strip()
    if not repo_root:
        raise ContractError(f"mutation audit could not resolve a git repo at: {worktree_path}")
    repo_root_path = Path(repo_root)

    changed_output = _run_git(
        repo_root_path,
        [
            "diff",
            "--name-only",
            "--relative",
            "--find-renames",
            base_commit,
            "--",
        ],
    )
    changed_files = [line.strip() for line in changed_output.splitlines() if line.strip()]

    numstat_output = _run_git(
        repo_root_path,
        [
            "diff",
            "--numstat",
            "--relative",
            "--find-renames",
            base_commit,
            "--",
        ],
    )
    additions = 0
    deletions = 0
    for raw_line in numstat_output.splitlines():
        if not raw_line.strip():
            continue
        added, removed, *_ = raw_line.split("\t", 2)
        additions += _parse_numstat_cell(added)
        deletions += _parse_numstat_cell(removed)

    untracked_output = _run_git(
        repo_root_path,
        ["ls-files", "--others", "--exclude-standard", "--full-name"],
    )
    untracked_files = [line.strip() for line in untracked_output.splitlines() if line.strip()]
    for path in untracked_files:
        if path not in changed_files:
            changed_files.append(path)
        untracked_path = repo_root_path / path
        if untracked_path.exists() and untracked_path.is_file():
            additions += _count_file_lines(untracked_path)

    return {
        "source": {
            "kind": "git_worktree_diff",
            "worktree_path": str(worktree_path),
            "repo_root": str(repo_root_path),
            "base_commit": base_commit,
            "includes_untracked": True,
        },
        "changed_files": changed_files,
        "diff_stats": {
            "tracked_files": len(changed_files),
            "additions": additions,
            "deletions": deletions,
            "net_lines": additions + deletions,
        },
    }


def _run_git(cwd: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        detail = stderr or stdout or f"git exited with code {completed.returncode}"
        raise ContractError(detail)
    return completed.stdout


def _parse_numstat_cell(value: str) -> int:
    value = value.strip()
    if not value or value == "-":
        return 0
    return int(value)


def _count_file_lines(path: Path) -> int:
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return 0
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in patterns)


def _first_nonempty(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _unavailable_audit(
    surface: dict[str, Any],
    *,
    reason: str,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    budget = surface["mutation_budget"]
    return {
        "status": "unavailable",
        "surface": surface,
        "source": source or {"kind": "unavailable"},
        "changed_files": [],
        "diff_stats": {
            "tracked_files": None,
            "additions": None,
            "deletions": None,
            "net_lines": None,
        },
        "budget_report": {
            "tracked_files_max": budget["tracked_files_max"],
            "tracked_files_used": None,
            "tracked_files_within_budget": None,
            "net_lines_max": budget["net_lines_max"],
            "net_lines_used": None,
            "net_lines_within_budget": None,
            "within_budget": None,
            "additions": None,
            "deletions": None,
        },
        "violations": {
            "blocked_paths": [],
            "out_of_scope_paths": [],
            "budget_exceeded": None,
        },
        "honesty_note": reason,
    }


__all__ = [
    "audit_packet_mutation_surface",
    "build_packet_mutation_surface",
    "write_mutation_surface_audit_receipt",
]

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from runner_bridge.backends import backend_contract_for_runner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Contract-first claude_vibecosystem beta backend")
    parser.add_argument("--request", required=True, help="Path to the run request JSON")
    parser.add_argument("--output-dir", required=True, help="Where to write transcript + artifacts")
    parser.add_argument(
        "--live-public-smoke",
        action="store_true",
        help=(
            "Enable live public-smoke mode: create an isolated git worktree, "
            "execute real verifier commands, and capture results honestly."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    request = json.loads(Path(args.request).read_text())
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.live_public_smoke:
        return _live_public_smoke(request, output_dir)
    return _stub_mode(request, output_dir)


# ---------------------------------------------------------------------------
# Stub mode (existing behaviour, unchanged)
# ---------------------------------------------------------------------------

def _stub_mode(request: dict[str, Any], output_dir: Path) -> int:
    transcript_path = output_dir / "transcript.ndjson"
    artifact_bundle_path = output_dir / "artifact-bundle.json"
    result_path = output_dir / "result.json"

    backend_contract = _load_backend_contract(request)
    runtime_surface = _build_runtime_surface(request, backend_contract)
    expected_checks = _expected_checks(request)

    events = [
        {
            "ts": _utc_now(),
            "event": "runner.started",
            "message": f"Preparing {request['run_id']} for the claude_vibecosystem beta seam.",
        },
        {
            "ts": _utc_now(),
            "event": "adapter.contract.loaded",
            "message": (
                f"Loaded external-executor beta contract for vibecosystem agent "
                f"{runtime_surface['claude_agent']}."
            ),
        },
        {
            "ts": _utc_now(),
            "event": "adapter.stub.completed",
            "message": (
                "Recorded backend naming, provenance, and honesty boundaries without invoking "
                "Claude Code, vibecosystem hooks, or live network transport."
            ),
        },
    ]
    transcript_path.write_text("".join(json.dumps(event) + "\n" for event in events))

    artifact_bundle = {
        "run_id": request["run_id"],
        "agent_role": request["agent_role"],
        "scenario_set_id": request["scenario_set_id"],
        "status": "completed",
        "workspace_snapshot": request.get("workspace_snapshot", {}),
        "execution_backend_contract": backend_contract,
        "external_executor_beta": runtime_surface,
        "receipts": {
            "transcript_path": transcript_path.name,
            "result_path": result_path.name,
        },
    }
    artifact_bundle_path.write_text(json.dumps(artifact_bundle, indent=2))

    result = {
        "status": "completed",
        "transcript_path": transcript_path.name,
        "artifact_bundle_path": artifact_bundle_path.name,
        "machine_score": 0.0,
        "scorecard": {
            "runner": "claude_vibecosystem",
            "checks": [
                {
                    "name": "backend_contract_captured",
                    "passed": True,
                },
                {
                    "name": "claim_boundary_preserved",
                    "passed": True,
                },
            ],
        },
        "execution_honesty": {
            "backend": "claude_vibecosystem",
            "mode": backend_contract.get("mode", "external_executor_beta"),
            "beta_status": backend_contract.get("beta_status", "adapter_first_contract_stub"),
            "executes_commands": False,
            "executes_checks": False,
            "check_results": [
                {
                    "id": check.get("id", ""),
                    "command": check.get("command", ""),
                    "execution_status": "not_executed",
                    "exit_code": None,
                    "reason": (
                        "claude_vibecosystem beta seam is currently a contract/provenance stub and "
                        "does not invoke live verifier commands in tests"
                    ),
                }
                for check in expected_checks
            ],
            "mutation_enforcement": "not_enforced",
            "path_constraint_enforcement": "not_enforced",
            "external_executor": runtime_surface,
            "claim_boundary": backend_contract.get("claim_boundary", {}),
            "honesty_note": (
                "This claude_vibecosystem beta seam records backend naming, executor intent, and "
                "claim boundaries only. It did not invoke Claude Code, vibecosystem hooks, or the "
                "live Clawith/OpenClaw gateway. It does not claim sealed evaluation, tamper-proofing, "
                "independent executor isolation, or native Clawith parity."
            ),
        },
    }
    result_path.write_text(json.dumps(result, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Live public-smoke mode
# ---------------------------------------------------------------------------

def _live_public_smoke(request: dict[str, Any], output_dir: Path) -> int:
    """Run verifier commands for real in an isolated git worktree.

    This mode creates a temporary worktree at the current HEAD, runs each
    verifier command, captures exit codes / stdout / stderr, and writes
    honest artifacts.  It does NOT invoke Claude Code for the student step.
    """
    backend_contract = _load_backend_contract(request)
    runtime_surface = _build_runtime_surface(request, backend_contract)
    runtime_surface["adapter_mode"] = "live_public_smoke"
    runtime_surface["live_execution"] = "verifier_commands_only"

    verifier_commands = _collect_verifier_commands(request)
    events: list[dict[str, Any]] = []
    check_results: list[dict[str, Any]] = []
    worktree_commit: str | None = None

    events.append({
        "ts": _utc_now(),
        "event": "runner.started",
        "message": f"Live public-smoke for {request['run_id']} with {len(verifier_commands)} verifier command(s).",
    })

    repo_root = _git_repo_root()
    worktree_path = output_dir / "live-smoke-worktree"

    try:
        worktree_commit = _create_worktree(repo_root, worktree_path)
        events.append({
            "ts": _utc_now(),
            "event": "worktree.created",
            "message": f"Isolated worktree at {worktree_path} from commit {worktree_commit[:12]}.",
            "worktree_commit": worktree_commit,
        })

        for cmd in verifier_commands:
            cr = _run_verifier_command(cmd, worktree_path)
            check_results.append(cr)
            events.append({
                "ts": _utc_now(),
                "event": "verifier.executed",
                "command": cmd,
                "exit_code": cr["exit_code"],
                "execution_status": cr["execution_status"],
            })

        diff_text = _capture_worktree_diff(worktree_path)
        if diff_text:
            (output_dir / "worktree.diff").write_text(diff_text)
            events.append({
                "ts": _utc_now(),
                "event": "worktree.diff.captured",
                "changed_lines": len(diff_text.splitlines()),
            })
    except Exception as exc:
        events.append({
            "ts": _utc_now(),
            "event": "runner.error",
            "message": str(exc),
        })
    finally:
        _remove_worktree(repo_root, worktree_path)
        events.append({"ts": _utc_now(), "event": "worktree.removed"})

    events.append({"ts": _utc_now(), "event": "runner.completed"})

    # ---- Write transcript ----
    transcript_path = output_dir / "transcript.ndjson"
    transcript_path.write_text("".join(json.dumps(e) + "\n" for e in events))

    # ---- Write per-command stdout/stderr artifacts ----
    for idx, cr in enumerate(check_results):
        if cr.get("stdout"):
            (output_dir / f"verifier-{idx}-stdout.log").write_text(cr["stdout"])
        if cr.get("stderr"):
            (output_dir / f"verifier-{idx}-stderr.log").write_text(cr["stderr"])

    # ---- Scorecard ----
    passed_count = sum(1 for cr in check_results if cr.get("exit_code") == 0)
    all_passed = bool(check_results) and passed_count == len(check_results)

    # ---- Artifact bundle ----
    artifact_bundle = {
        "run_id": request["run_id"],
        "agent_role": request["agent_role"],
        "scenario_set_id": request["scenario_set_id"],
        "status": "completed",
        "workspace_snapshot": request.get("workspace_snapshot", {}),
        "execution_backend_contract": backend_contract,
        "external_executor_beta": runtime_surface,
        "live_smoke": {
            "worktree_commit": worktree_commit,
            "verifier_commands_executed": len(check_results),
            "verifier_commands_passed": passed_count,
            "all_passed": all_passed,
        },
        "receipts": {
            "transcript_path": transcript_path.name,
            "result_path": "result.json",
        },
    }
    (output_dir / "artifact-bundle.json").write_text(json.dumps(artifact_bundle, indent=2))

    # ---- Result ----
    result = {
        "status": "completed",
        "transcript_path": transcript_path.name,
        "artifact_bundle_path": "artifact-bundle.json",
        "machine_score": 0.0,
        "scorecard": {
            "runner": "claude_vibecosystem",
            "checks": [
                {"name": cr["command"][:80], "passed": cr.get("exit_code") == 0}
                for cr in check_results
            ],
        },
        "execution_honesty": {
            "backend": "claude_vibecosystem",
            "mode": "live_public_smoke",
            "beta_status": "live_public_smoke_alpha",
            "executes_commands": True,
            "executes_checks": True,
            "check_results": [
                {
                    "command": cr["command"],
                    "execution_status": cr["execution_status"],
                    "exit_code": cr.get("exit_code"),
                    "stdout_lines": len((cr.get("stdout") or "").splitlines()),
                    "stderr_lines": len((cr.get("stderr") or "").splitlines()),
                }
                for cr in check_results
            ],
            "worktree_commit": worktree_commit,
            "worktree_isolation": True,
            "mutation_enforcement": "not_enforced",
            "path_constraint_enforcement": "not_enforced",
            "external_executor": runtime_surface,
            "claim_boundary": backend_contract.get("claim_boundary", {}),
            "honesty_note": (
                "This live public-smoke run created an isolated git worktree, executed real verifier "
                "commands, and captured their exit codes and output honestly. It did not invoke Claude "
                "Code for the student step. It does not claim sealed evaluation, tamper-proofing, "
                "independent executor isolation, or native Clawith parity."
            ),
        },
    }
    (output_dir / "result.json").write_text(json.dumps(result, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Worktree helpers
# ---------------------------------------------------------------------------

def _git_repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return Path(result.stdout.strip())


def _create_worktree(repo_root: Path, worktree_path: Path) -> str:
    """Create a detached worktree at HEAD.  Returns the commit hash."""
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, cwd=repo_root,
    ).stdout.strip()
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(worktree_path), commit],
        capture_output=True, text=True, check=True, cwd=repo_root,
    )
    return commit


def _remove_worktree(repo_root: Path, worktree_path: Path) -> None:
    if worktree_path.exists():
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            capture_output=True, text=True, cwd=repo_root,
        )


def _run_verifier_command(
    command: str,
    cwd: Path,
    timeout: int = 120,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return {
            "command": command,
            "execution_status": "executed",
            "exit_code": completed.returncode,
            "stdout": (completed.stdout or "")[:20_000],
            "stderr": (completed.stderr or "")[:20_000],
        }
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "execution_status": "timeout",
            "exit_code": None,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
        }
    except Exception as exc:
        return {
            "command": command,
            "execution_status": "error",
            "exit_code": None,
            "stdout": "",
            "stderr": str(exc),
        }


def _capture_worktree_diff(worktree_path: Path) -> str:
    result = subprocess.run(
        ["git", "diff"],
        capture_output=True, text=True, cwd=worktree_path,
    )
    return result.stdout or ""


def _collect_verifier_commands(request: dict[str, Any]) -> list[str]:
    """Extract verifier commands from all known request locations."""
    commands: list[str] = []
    seen: set[str] = set()

    def _add(cmd: str) -> None:
        if cmd and cmd not in seen:
            seen.add(cmd)
            commands.append(cmd)

    # packet_runtime.expected_checks
    for check in (request.get("packet_runtime") or {}).get("expected_checks") or []:
        if isinstance(check, dict):
            _add(str(check.get("command", "")))

    # extras.recommended_verifier_commands  (injected by alpha loop)
    for cmd in (request.get("extras") or {}).get("recommended_verifier_commands") or []:
        _add(str(cmd))

    # student_prompt_pack.repo_task_pack.recommended_verifier_commands
    spp = request.get("student_prompt_pack") or {}
    rtp = spp.get("repo_task_pack") or {}
    for cmd in rtp.get("recommended_verifier_commands") or []:
        _add(str(cmd))

    # top-level recommended_verifier_commands  (convenience)
    for cmd in request.get("recommended_verifier_commands") or []:
        _add(str(cmd))

    return commands


# ---------------------------------------------------------------------------
# Shared helpers (unchanged from original)
# ---------------------------------------------------------------------------

def _load_backend_contract(request: dict[str, Any]) -> dict[str, Any]:
    contract = request.get("runner_backend_contract") if isinstance(request.get("runner_backend_contract"), dict) else None
    if not contract:
        packet_runtime = request.get("packet_runtime") if isinstance(request.get("packet_runtime"), dict) else {}
        contract = packet_runtime.get("execution_backend_contract") if isinstance(packet_runtime.get("execution_backend_contract"), dict) else None
    return dict(contract or backend_contract_for_runner("claude_vibecosystem"))


def _build_runtime_surface(request: dict[str, Any], backend_contract: dict[str, Any]) -> dict[str, Any]:
    workspace_snapshot = request.get("workspace_snapshot") if isinstance(request.get("workspace_snapshot"), dict) else {}
    executor = backend_contract.get("executor") if isinstance(backend_contract.get("executor"), dict) else {}
    return {
        "adapter_mode": "contract_stub",
        "live_execution": "not_invoked",
        "runtime": executor.get("runtime", "Claude Code"),
        "agent_selection": executor.get("agent_selection", "vibecosystem"),
        "claude_agent": workspace_snapshot.get("claude_agent") or executor.get("default_agent", "backend-dev"),
        "prompt_transport": executor.get("prompt_transport", "stdin"),
        "workdir": workspace_snapshot.get("workdir") or ".",
        "workdir_mode": executor.get("workdir_mode", "dedicated_workdir_expected"),
        "control_plane_path": (backend_contract.get("control_plane") or {}).get("path", "external_gateway_only"),
    }


def _expected_checks(request: dict[str, Any]) -> list[dict[str, str]]:
    packet_runtime = request.get("packet_runtime") if isinstance(request.get("packet_runtime"), dict) else {}
    raw = packet_runtime.get("expected_checks")
    if not isinstance(raw, list):
        return []
    checks: list[dict[str, str]] = []
    for entry in raw:
        if isinstance(entry, dict):
            checks.append({
                "id": str(entry.get("id", "")),
                "command": str(entry.get("command", "")),
            })
    return checks


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())

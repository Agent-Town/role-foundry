from __future__ import annotations

import argparse
import json
import subprocess
import sys
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
    request_path = Path(args.request)
    request = json.loads(request_path.read_text())
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.live_public_smoke:
        if _should_delegate_to_local_replay(request):
            return _delegate_to_local_replay(request_path, output_dir)
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

def _should_delegate_to_local_replay(request: dict[str, Any]) -> bool:
    has_teacher_evaluation = isinstance(request.get("teacher_evaluation"), dict)
    has_student_prompt_pack = isinstance(request.get("student_prompt_pack"), dict)
    return has_teacher_evaluation and not has_student_prompt_pack


def _delegate_to_local_replay(request_path: Path, output_dir: Path) -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "runner_bridge.backends.local_replay", "--request", str(request_path), "--output-dir", str(output_dir)],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "local_replay delegation failed: " + ((completed.stderr or completed.stdout or "unknown error").strip())
        )
    return 0


def _live_public_smoke(request: dict[str, Any], output_dir: Path) -> int:
    """Run real student + verifier steps in an isolated git worktree.

    When a ``student_prompt_pack`` is present in the request (candidate-student
    stage), this mode invokes the local Claude Code CLI with the student prompt
    inside the worktree before running verifier commands.  If no student prompt
    pack is present the student step is skipped honestly.
    """
    backend_contract = _load_backend_contract(request)
    runtime_surface = _build_runtime_surface(request, backend_contract)
    student_prompt_pack = request.get("student_prompt_pack") if isinstance(request.get("student_prompt_pack"), dict) else None
    has_student_step = student_prompt_pack is not None
    runtime_surface["adapter_mode"] = "live_public_smoke"
    runtime_surface["live_execution"] = (
        "student_and_verifier" if has_student_step else "verifier_commands_only"
    )

    verifier_commands = _collect_verifier_commands(request)
    events: list[dict[str, Any]] = []
    check_results: list[dict[str, Any]] = []
    student_result: dict[str, Any] | None = None
    worktree_commit: str | None = None

    events.append({
        "ts": _utc_now(),
        "event": "runner.started",
        "message": (
            f"Live public-smoke for {request['run_id']} with "
            f"{len(verifier_commands)} verifier command(s)"
            f"{' and a real student step' if has_student_step else ' (no student step)'}."
        ),
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

        # ---- Student step (only when prompt pack present) ----
        if has_student_step:
            student_result = _run_student_step(student_prompt_pack, worktree_path, output_dir)
            events.append({
                "ts": _utc_now(),
                "event": "student.executed",
                "execution_status": student_result["execution_status"],
                "exit_code": student_result.get("exit_code"),
            })

            diff_after_student = _capture_worktree_diff(worktree_path)
            if diff_after_student:
                (output_dir / "student.diff").write_text(diff_after_student)
                events.append({
                    "ts": _utc_now(),
                    "event": "student.diff.captured",
                    "changed_lines": len(diff_after_student.splitlines()),
                })

        # ---- Verifier commands ----
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
    live_smoke_block: dict[str, Any] = {
        "worktree_commit": worktree_commit,
        "verifier_commands_executed": len(check_results),
        "verifier_commands_passed": passed_count,
        "all_passed": all_passed,
        "student_step_executed": has_student_step and student_result is not None,
    }
    if student_result is not None:
        live_smoke_block["student_execution_status"] = student_result["execution_status"]
        live_smoke_block["student_exit_code"] = student_result.get("exit_code")

    artifact_bundle = {
        "run_id": request["run_id"],
        "agent_role": request["agent_role"],
        "scenario_set_id": request["scenario_set_id"],
        "status": "completed",
        "workspace_snapshot": request.get("workspace_snapshot", {}),
        "execution_backend_contract": backend_contract,
        "external_executor_beta": runtime_surface,
        "live_smoke": live_smoke_block,
        "receipts": {
            "transcript_path": transcript_path.name,
            "result_path": "result.json",
        },
    }
    (output_dir / "artifact-bundle.json").write_text(json.dumps(artifact_bundle, indent=2))

    # ---- Build honesty note ----
    if has_student_step and student_result is not None:
        student_honesty = (
            "This live public-smoke run created an isolated git worktree, invoked a real Claude Code "
            "student step via the local CLI, executed real verifier commands, and captured all exit "
            "codes and output honestly."
        )
    else:
        student_honesty = (
            "This live public-smoke run created an isolated git worktree and executed real verifier "
            "commands. No student prompt pack was present so the student step was not invoked."
        )
    honesty_note = (
        f"{student_honesty} It does not claim sealed evaluation, tamper-proofing, "
        "independent executor isolation, or native Clawith parity."
    )

    # ---- Student step honesty block ----
    student_honesty_block: dict[str, Any] = {"executed": False, "reason": "no student_prompt_pack in request"}
    if student_result is not None:
        student_honesty_block = {
            "executed": True,
            "execution_status": student_result["execution_status"],
            "exit_code": student_result.get("exit_code"),
            "stdout_lines": len((student_result.get("stdout") or "").splitlines()),
            "stderr_lines": len((student_result.get("stderr") or "").splitlines()),
            "transcript_artifact": "student-stdout.log",
        }

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
            "student_step": student_honesty_block,
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
            "honesty_note": honesty_note,
        },
    }
    (output_dir / "result.json").write_text(json.dumps(result, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Student step (real Claude Code CLI invocation)
# ---------------------------------------------------------------------------

def _build_student_prompt(student_prompt_pack: dict[str, Any]) -> str:
    """Extract a deterministic student prompt from the prompt pack.

    Uses the first ``visible_scenarios[].student_prompt`` or falls back to
    ``prompt_summary``.
    """
    for scenario in student_prompt_pack.get("visible_scenarios") or []:
        if isinstance(scenario, dict) and scenario.get("student_prompt"):
            return str(scenario["student_prompt"])
    return str(student_prompt_pack.get("prompt_summary") or "Inspect the repo and report status.")


def _run_student_step(
    student_prompt_pack: dict[str, Any],
    worktree_path: Path,
    output_dir: Path,
    timeout: int = 120,
) -> dict[str, Any]:
    """Invoke the local Claude Code CLI in non-interactive mode inside the worktree.

    Returns a dict with execution_status, exit_code, stdout, stderr.
    """
    prompt = _build_student_prompt(student_prompt_pack)
    cmd = [
        "claude",
        "--print",
        "--permission-mode",
        "bypassPermissions",
        "--output-format",
        "text",
        "--max-turns",
        "3",
        "--add-dir",
        str(worktree_path),
    ]
    try:
        completed = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=worktree_path,
        )
        stdout = (completed.stdout or "")[:50_000]
        stderr = (completed.stderr or "")[:20_000]
        if stdout:
            (output_dir / "student-stdout.log").write_text(stdout)
        if stderr:
            (output_dir / "student-stderr.log").write_text(stderr)
        return {
            "execution_status": "executed",
            "exit_code": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "execution_status": "timeout",
            "exit_code": None,
            "stdout": "",
            "stderr": f"Claude CLI timed out after {timeout}s",
        }
    except FileNotFoundError:
        return {
            "execution_status": "error",
            "exit_code": None,
            "stdout": "",
            "stderr": "claude CLI not found on PATH",
        }
    except Exception as exc:
        return {
            "execution_status": "error",
            "exit_code": None,
            "stdout": "",
            "stderr": str(exc),
        }


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
    subprocess.run(
        ["git", "worktree", "prune"],
        capture_output=True, text=True, cwd=repo_root,
    )
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
    subprocess.run(
        ["git", "worktree", "prune"],
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

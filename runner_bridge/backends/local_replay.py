from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from runner_bridge.eval_loop import build_teacher_evaluation, has_teacher_evaluation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic local replay runner for Milestone 4")
    parser.add_argument("--request", required=True, help="Path to the run request JSON")
    parser.add_argument("--output-dir", required=True, help="Where to write transcript + artifacts")
    return parser


def _has_student_prompt_pack(request: dict) -> bool:
    """Check if request has a student_prompt_pack extra (student-only stage, no teacher)."""
    return isinstance(request.get("student_prompt_pack"), dict)


def _normalise_repo_path(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    path = value.replace("\\", "/").strip()
    if not path:
        return None
    while path.startswith("./"):
        path = path[2:]
    return path or None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _match_pattern(path: str, patterns: list[str]) -> str | None:
    pure_path = PurePosixPath(path)
    for raw_pattern in patterns:
        pattern = _normalise_repo_path(raw_pattern)
        if not pattern:
            continue
        if pure_path.match(pattern):
            return pattern
    return None


def _build_mutation_surface_audit(request: dict[str, Any]) -> dict[str, Any] | None:
    packet_runtime = request.get("packet_runtime")
    if not isinstance(packet_runtime, dict):
        return None

    workspace = request.get("workspace_snapshot") if isinstance(request.get("workspace_snapshot"), dict) else {}
    changed_files_raw = workspace.get("changed_files") if isinstance(workspace.get("changed_files"), list) else None
    changed_files = [path for path in (_normalise_repo_path(item) for item in (changed_files_raw or [])) if path]
    diff_stats = workspace.get("diff_stats") if isinstance(workspace.get("diff_stats"), dict) else {}

    allowed_paths = [pattern for pattern in (_normalise_repo_path(item) for item in packet_runtime.get("allowed_paths", [])) if pattern]
    blocked_paths = [pattern for pattern in (_normalise_repo_path(item) for item in packet_runtime.get("blocked_paths", [])) if pattern]
    mutation_budget = packet_runtime.get("mutation_budget") if isinstance(packet_runtime.get("mutation_budget"), dict) else {}

    tracked_files_limit = _coerce_int(mutation_budget.get("tracked_files_max", mutation_budget.get("max_files")))
    net_lines_limit = _coerce_int(mutation_budget.get("net_lines_max", mutation_budget.get("max_lines")))
    tracked_files_observed = _coerce_int(diff_stats.get("tracked_files"))
    if tracked_files_observed is None and changed_files_raw is not None:
        tracked_files_observed = len(changed_files)
    net_lines_observed = _coerce_int(diff_stats.get("net_lines"))

    path_checks: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    for path in changed_files:
        blocked_match = _match_pattern(path, blocked_paths)
        allowed_match = _match_pattern(path, allowed_paths)
        path_checks.append({
            "path": path,
            "allowed_match": allowed_match,
            "blocked_match": blocked_match,
        })
        if blocked_match:
            violations.append({
                "kind": "blocked_path",
                "path": path,
                "matched_pattern": blocked_match,
            })
        elif allowed_paths and not allowed_match:
            violations.append({
                "kind": "outside_allowed_paths",
                "path": path,
                "allowed_paths": allowed_paths,
            })

    if tracked_files_limit is not None and tracked_files_observed is not None and tracked_files_observed > tracked_files_limit:
        violations.append({
            "kind": "tracked_files_budget",
            "observed": tracked_files_observed,
            "limit": tracked_files_limit,
        })
    if net_lines_limit is not None and net_lines_observed is not None and net_lines_observed > net_lines_limit:
        violations.append({
            "kind": "net_lines_budget",
            "observed": net_lines_observed,
            "limit": net_lines_limit,
        })

    evidence_gaps: list[str] = []
    if not allowed_paths and not blocked_paths:
        evidence_gaps.append("packet_runtime did not declare allowed_paths/blocked_paths.")
    if changed_files_raw is None:
        evidence_gaps.append("workspace_snapshot.changed_files was not provided.")
    if net_lines_limit is not None and net_lines_observed is None:
        evidence_gaps.append("workspace_snapshot.diff_stats.net_lines was not provided.")

    if violations:
        status = "fail"
        honesty_note = (
            "Declared mutation-surface auditing found out-of-scope or over-budget changes. "
            "LocalReplayRunner did not independently compute the diff; this verdict is based on workspace_snapshot evidence."
        )
    elif evidence_gaps:
        status = "unavailable"
        honesty_note = (
            "LocalReplayRunner received a mutation surface, but not enough declared diff evidence to clear it honestly. "
            "It does not independently compute git diffs or net-line counts."
        )
    else:
        status = "pass"
        honesty_note = (
            "Declared mutation-surface auditing passed against workspace_snapshot changed-files/diff-stats evidence. "
            "LocalReplayRunner still does not independently compute the diff."
        )

    budget_report = {
        "declared": {
            "allowed_paths": allowed_paths,
            "blocked_paths": blocked_paths,
            "tracked_files_max": tracked_files_limit,
            "net_lines_max": net_lines_limit,
        },
        "observed": {
            "changed_files_count": len(changed_files) if changed_files_raw is not None else None,
            "tracked_files": tracked_files_observed,
            "net_lines": net_lines_observed,
        },
        "checks": {
            "paths": {
                "status": "fail" if any(v["kind"] in {"blocked_path", "outside_allowed_paths"} for v in violations) else "pass",
                "checked_file_count": len(changed_files) if changed_files_raw is not None else 0,
            },
            "tracked_files": {
                "status": (
                    "fail"
                    if any(v["kind"] == "tracked_files_budget" for v in violations)
                    else "pass" if tracked_files_limit is None or tracked_files_observed is not None else "unavailable"
                ),
                "observed": tracked_files_observed,
                "limit": tracked_files_limit,
            },
            "net_lines": {
                "status": (
                    "fail"
                    if any(v["kind"] == "net_lines_budget" for v in violations)
                    else "pass" if net_lines_limit is None or net_lines_observed is not None else "unavailable"
                ),
                "observed": net_lines_observed,
                "limit": net_lines_limit,
            },
        },
        "evidence_gaps": evidence_gaps,
        "path_checks": path_checks,
    }

    source_kind = "workspace_snapshot.changed_files+diff_stats" if diff_stats else "workspace_snapshot.changed_files"
    return {
        "status": status,
        "honesty_note": honesty_note,
        "source": {
            "kind": source_kind,
            "backend_verified": False,
            "packet_runtime_present": True,
        },
        "changed_files": changed_files,
        "budget_report": budget_report,
        "violations": violations,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    request = json.loads(Path(args.request).read_text())
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    simulate_failure = bool(request.get("workspace_snapshot", {}).get("simulate_failure"))
    transcript_path = output_dir / "transcript.ndjson"
    artifact_bundle_path = output_dir / "artifact-bundle.json"
    result_path = output_dir / "result.json"

    events = [
        {
            "ts": _utc_now(),
            "event": "runner.started",
            "message": f"Starting {request['run_id']} for {request['agent_role']} on {request['scenario_set_id']}",
        },
        {
            "ts": _utc_now(),
            "event": "runner.objective",
            "message": request.get("workspace_snapshot", {}).get(
                "objective", "No explicit objective provided."
            ),
        },
    ]

    evaluation = build_teacher_evaluation(request) if has_teacher_evaluation(request) else None
    student_prompt_pack = request.get("student_prompt_pack") if _has_student_prompt_pack(request) else None

    if evaluation:
        events.extend(
            [
                {
                    "ts": _utc_now(),
                    "event": "student.prompt.loaded",
                    "message": f"Student prompt pack loaded with {len(evaluation['student_view']['visible_scenarios'])} visible scenarios and {evaluation['student_view']['sealed_holdout_count']} sealed holdouts.",
                },
                {
                    "ts": _utc_now(),
                    "event": "teacher.evaluation.started",
                    "message": f"Teacher {evaluation['teacher_output']['actor']['name']} is scoring the run against public curriculum plus sealed holdouts.",
                },
            ]
        )
    elif student_prompt_pack:
        ep_count = student_prompt_pack.get("episode_count", len(student_prompt_pack.get("episodes", [])))
        events.append({
            "ts": _utc_now(),
            "event": "student.prompt_pack.loaded",
            "message": f"Student prompt pack loaded with {ep_count} public episodes. No teacher evaluation in this stage.",
        })

    if simulate_failure:
        events.append(
            {
                "ts": _utc_now(),
                "event": "runner.failed",
                "message": "Rejected by LocalReplayRunner because workspace_snapshot.simulate_failure=true",
            }
        )
        status = "failed"
        machine_score = 0.0
        error = "simulated failure requested by workspace_snapshot"
        scorecard = {
            "runner": "LocalReplayRunner",
            "checks": [
                {
                    "name": "artifact_bundle_present",
                    "passed": True,
                },
                {
                    "name": "failure_is_honest",
                    "passed": True,
                },
            ],
        }
    else:
        if evaluation:
            aggregate = evaluation["teacher_output"]["aggregate_score"]
            delta = evaluation["iteration_history"][-1].get("delta", {}) if evaluation["iteration_history"] else {}
            events.extend(
                [
                    {
                        "ts": _utc_now(),
                        "event": "teacher.evaluation.completed",
                        "message": f"Teacher aggregate score: {aggregate['passed']}/{aggregate['total']} ({aggregate['pass_rate']:.0%}).",
                    },
                    {
                        "ts": _utc_now(),
                        "event": "iteration.delta",
                        "message": f"Score delta vs previous iteration: {delta.get('pass_count', 0):+d} passes, {delta.get('holdout_pass_count', 0):+d} holdouts.",
                    },
                    {
                        "ts": _utc_now(),
                        "event": "runner.completed",
                        "message": "LocalReplayRunner produced a teacher scorecard, public curriculum themes, and iteration receipts.",
                    },
                ]
            )
            machine_score = aggregate["average_score"]
            scorecard = {
                "runner": "LocalReplayRunner",
                "teacher": evaluation["teacher_output"]["actor"],
                "student": evaluation["student_view"]["actor"],
                "aggregate_score": aggregate,
                "scenario_results": evaluation["teacher_output"]["scenario_results"],
                "public_curriculum_themes": evaluation["public_curriculum_themes"],
                "iteration_history": evaluation["iteration_history"],
                "verdict": evaluation["teacher_output"]["verdict"],
            }
        elif student_prompt_pack:
            # Student-only stage: no teacher evaluation, just prompt pack consumption
            ep_count = student_prompt_pack.get("episode_count", 0)
            events.append({
                "ts": _utc_now(),
                "event": "runner.completed",
                "message": f"LocalReplayRunner consumed student prompt pack ({ep_count} episodes). No teacher scoring in this stage.",
            })
            machine_score = 0.8
            scorecard = {
                "runner": "LocalReplayRunner",
                "stage": "candidate-student",
                "prompt_pack_episode_count": ep_count,
                "sealed_holdout_count": 0,
                "checks": [
                    {
                        "name": "prompt_pack_loaded",
                        "passed": True,
                    },
                    {
                        "name": "no_teacher_evaluation",
                        "passed": True,
                        "note": "Student-only stage; teacher evaluation happens in candidate-teacher-eval.",
                    },
                    {
                        "name": "artifact_bundle_present",
                        "passed": True,
                    },
                ],
            }
        else:
            events.append(
                {
                    "ts": _utc_now(),
                    "event": "runner.completed",
                    "message": "LocalReplayRunner produced transcript and artifact receipts.",
                }
            )
            machine_score = 0.8
            scorecard = {
                "runner": "LocalReplayRunner",
                "checks": [
                    {
                        "name": "artifact_bundle_present",
                        "passed": True,
                    },
                    {
                        "name": "transcript_has_completion_event",
                        "passed": True,
                    },
                ],
            }

        status = "completed"
        error = None

    transcript_path.write_text("".join(json.dumps(event) + "\n" for event in events))

    artifact_bundle = {
        "run_id": request["run_id"],
        "agent_role": request["agent_role"],
        "scenario_set_id": request["scenario_set_id"],
        "status": status,
        "workspace_snapshot": request.get("workspace_snapshot", {}),
        "receipts": {
            "transcript_path": transcript_path.name,
            "result_path": result_path.name,
        },
    }
    if evaluation:
        artifact_bundle["student_view"] = evaluation["student_view"]
        artifact_bundle["teacher_output"] = evaluation["teacher_output"]
        artifact_bundle["iteration_history"] = evaluation["iteration_history"]
        artifact_bundle["public_curriculum_themes"] = evaluation["public_curriculum_themes"]
    elif student_prompt_pack:
        # Student view from prompt pack (no teacher_output)
        artifact_bundle["student_view"] = {
            "agent_role": "student",
            "actor": {"id": "candidate-student", "name": "Candidate Student", "agent_role": "student"},
            "episode_count": student_prompt_pack.get("episode_count", 0),
            "episodes": student_prompt_pack.get("episodes", []),
            "sealed_holdout_count": 0,
            "public_failure_themes_consumed": student_prompt_pack.get("public_failure_themes", []),
            "prompt_summary": student_prompt_pack.get("prompt_summary", ""),
        }
    if error:
        artifact_bundle["error"] = error
    artifact_bundle_path.write_text(json.dumps(artifact_bundle, indent=2))

    result = {
        "status": status,
        "transcript_path": transcript_path.name,
        "artifact_bundle_path": artifact_bundle_path.name,
        "machine_score": machine_score,
        "scorecard": scorecard,
    }
    if error:
        result["error"] = error

    packet_runtime = request.get("packet_runtime")
    if packet_runtime:
        expected_checks = packet_runtime.get("expected_checks", [])
        mutation_surface_audit = _build_mutation_surface_audit(request)
        result["execution_honesty"] = {
            "backend": "LocalReplayRunner",
            "executes_commands": False,
            "executes_checks": False,
            "check_results": [
                {
                    "id": check.get("id", ""),
                    "command": check.get("command", ""),
                    "execution_status": "not_executed",
                    "exit_code": None,
                    "reason": "LocalReplayRunner does not execute packet commands",
                }
                for check in expected_checks
            ],
            "mutation_enforcement": "declared_audit",
            "path_constraint_enforcement": "declared_audit",
            "mutation_surface_audit": mutation_surface_audit,
            "honesty_note": (
                "LocalReplayRunner is a zero-secret replay backend. "
                "It validates the request contract and produces receipts, "
                "but does not execute task commands or independently compute diffs. "
                "When packet_runtime is attached it can audit declared changed-files/diff-stats evidence, "
                "but live execution and independently verified mutation/path enforcement still require a real executor."
            ),
        }

    result_path.write_text(json.dumps(result, indent=2))

    return 1 if error else 0


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())

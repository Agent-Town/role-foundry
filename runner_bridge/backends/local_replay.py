from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from runner_bridge.eval_loop import build_teacher_evaluation, has_teacher_evaluation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic local replay runner for Milestone 4")
    parser.add_argument("--request", required=True, help="Path to the run request JSON")
    parser.add_argument("--output-dir", required=True, help="Where to write transcript + artifacts")
    return parser


def _has_student_prompt_pack(request: dict) -> bool:
    """Check if request has a student_prompt_pack extra (student-only stage, no teacher)."""
    return isinstance(request.get("student_prompt_pack"), dict)


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
            "mutation_enforcement": "not_enforced",
            "path_constraint_enforcement": "not_enforced",
            "honesty_note": (
                "LocalReplayRunner is a zero-secret replay backend. "
                "It validates the request contract and produces receipts, "
                "but does not execute task commands, enforce mutation budgets, "
                "or enforce path constraints. These become meaningful when a "
                "live execution backend is wired."
            ),
        }

    result_path.write_text(json.dumps(result, indent=2))

    return 1 if error else 0


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())

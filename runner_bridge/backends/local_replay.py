from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from runner_bridge.eval_loop import build_teacher_evaluation, has_teacher_evaluation
from runner_bridge.eval_scorecard import build_eval_scorecard


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic local replay runner for Milestone 4")
    parser.add_argument("--request", required=True, help="Path to the run request JSON")
    parser.add_argument("--output-dir", required=True, help="Where to write transcript + artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    request = json.loads(Path(args.request).read_text())
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    simulate_failure = bool(request.get("workspace_snapshot", {}).get("simulate_failure"))
    transcript_path = output_dir / "transcript.ndjson"
    artifact_bundle_path = output_dir / "artifact-bundle.json"
    result_path = output_dir / "result.json"
    student_view_path = output_dir / "student-view.json"
    teacher_scorecard_path = output_dir / "teacher-scorecard.json"

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
            eval_scorecard = build_eval_scorecard(request, evaluation)
            evaluation["teacher_output"]["contract_version"] = eval_scorecard["contract_version"]
            evaluation["teacher_output"]["integrity_passed"] = eval_scorecard["integrity_passed"]
            evaluation["teacher_output"]["integrity_gates"] = eval_scorecard["integrity_gates"]
            evaluation["teacher_output"]["weighted_categories"] = eval_scorecard["weighted_categories"]
            evaluation["teacher_output"]["total_score"] = eval_scorecard["total_score"]
            if "comparison" in eval_scorecard:
                evaluation["teacher_output"]["comparison"] = eval_scorecard["comparison"]
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
                        "event": "eval.contract.completed",
                        "message": (
                            f"Eval contract total: {eval_scorecard['total_score']:.4f}; "
                            f"comparison verdict: {eval_scorecard.get('comparison', {}).get('verdict', 'n/a')}."
                        ),
                    },
                    {
                        "ts": _utc_now(),
                        "event": "runner.completed",
                        "message": "LocalReplayRunner produced a teacher scorecard, integrity gates, weighted scoring, and iteration receipts.",
                    },
                ]
            )
            machine_score = eval_scorecard["total_score"]
            scorecard = {
                "runner": "LocalReplayRunner",
                "teacher": evaluation["teacher_output"]["actor"],
                "student": evaluation["student_view"]["actor"],
                "aggregate_score": aggregate,
                "scenario_results": evaluation["teacher_output"]["scenario_results"],
                "public_curriculum_themes": evaluation["public_curriculum_themes"],
                "iteration_history": evaluation["iteration_history"],
                "verdict": evaluation["teacher_output"]["verdict"],
                "contract_version": eval_scorecard["contract_version"],
                "integrity_passed": eval_scorecard["integrity_passed"],
                "integrity_gates": eval_scorecard["integrity_gates"],
                "weighted_categories": eval_scorecard["weighted_categories"],
                "total_score": eval_scorecard["total_score"],
                "thresholds": eval_scorecard["thresholds"],
            }
            if "comparison" in eval_scorecard:
                scorecard["comparison"] = eval_scorecard["comparison"]
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
    if request.get("lineage"):
        artifact_bundle["lineage"] = request["lineage"]
    if request.get("meta"):
        artifact_bundle["meta"] = request["meta"]
    if evaluation:
        student_view_path.write_text(json.dumps(evaluation["student_view"], indent=2))
        teacher_scorecard_path.write_text(json.dumps(evaluation["teacher_output"], indent=2))
        artifact_bundle["receipts"]["student_view_path"] = student_view_path.name
        artifact_bundle["receipts"]["teacher_scorecard_path"] = teacher_scorecard_path.name
        artifact_bundle["student_view"] = evaluation["student_view"]
        artifact_bundle["teacher_output"] = evaluation["teacher_output"]
        artifact_bundle["iteration_history"] = evaluation["iteration_history"]
        artifact_bundle["public_curriculum_themes"] = evaluation["public_curriculum_themes"]
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
    result_path.write_text(json.dumps(result, indent=2))

    return 1 if error else 0


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())

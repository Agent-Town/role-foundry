from __future__ import annotations

from copy import deepcopy
from typing import Any

TEACHER_EVALUATION_KEY = "teacher_evaluation"


def has_teacher_evaluation(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get(TEACHER_EVALUATION_KEY), dict)


def redact_request_for_artifacts(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a student-safe artifact copy of the request payload.

    The backend may still receive the raw request, but anything persisted in the
    judge-facing artifact directory should not leak sealed holdout prompt text.
    """
    redacted = deepcopy(payload)
    evaluation = redacted.get(TEACHER_EVALUATION_KEY)
    if not isinstance(evaluation, dict):
        return redacted

    redacted[TEACHER_EVALUATION_KEY] = {
        "teacher": _public_actor(evaluation.get("teacher"), default_role="teacher"),
        "student": _public_actor(evaluation.get("student"), default_role="student"),
        "iteration": evaluation.get("iteration"),
        "scenario_manifest": [
            {
                "id": scenario.get("id"),
                "title": scenario.get("title") or scenario.get("id"),
                "type": scenario.get("type", "training"),
                "difficulty": scenario.get("difficulty"),
                "prompt_visibility": "sealed"
                if scenario.get("type") == "holdout"
                else "student-visible",
            }
            for scenario in evaluation.get("scenarios", [])
        ],
    }
    previous = evaluation.get("previous_iteration")
    if isinstance(previous, dict):
        redacted[TEACHER_EVALUATION_KEY]["previous_iteration"] = {
            "run_id": previous.get("run_id"),
            "aggregate_score": previous.get("aggregate_score", {}),
        }
    return redacted


def build_teacher_evaluation(payload: dict[str, Any]) -> dict[str, Any]:
    evaluation = payload.get(TEACHER_EVALUATION_KEY) or {}
    teacher = _public_actor(evaluation.get("teacher"), default_role="teacher")
    student = _public_actor(evaluation.get("student"), default_role="student")
    scenarios = evaluation.get("scenarios", [])

    scenario_results = []
    visible_scenarios = []
    raw_failure_themes = []
    current_iteration = _public_iteration(evaluation.get("iteration"))

    for scenario in scenarios:
        scenario_type = scenario.get("type", "training")
        title = scenario.get("title") or scenario.get("id") or "unknown"
        score = round(float(scenario.get("score", 0.0)), 3)
        passed = bool(scenario.get("passed"))
        notes = scenario.get("teacher_notes") or scenario.get("notes") or ""

        scenario_results.append(
            {
                "scenario_id": scenario.get("id"),
                "title": title,
                "type": scenario_type,
                "difficulty": scenario.get("difficulty"),
                "passed": passed,
                "score": score,
                "notes": notes,
                "visibility": "sealed" if scenario_type == "holdout" else "student-visible",
            }
        )

        if scenario_type != "holdout":
            visible_scenarios.append(
                {
                    "id": scenario.get("id"),
                    "title": title,
                    "type": scenario_type,
                    "difficulty": scenario.get("difficulty"),
                    "student_prompt": scenario.get("student_prompt")
                    or scenario.get("prompt")
                    or scenario.get("description")
                    or "",
                }
            )
        elif not passed:
            raw_failure_themes.append(
                {
                    "theme": scenario.get("public_failure_theme")
                    or f"Failure theme from {scenario.get('id', 'holdout')}",
                    "description": scenario.get("public_failure_summary")
                    or "Teacher promoted a public curriculum theme without revealing the sealed prompt.",
                    "source_scenarios": [scenario.get("id")],
                }
            )

    aggregate_score = _aggregate_scores(scenario_results)
    public_curriculum_themes = _dedupe_failure_themes(raw_failure_themes)
    iteration_history = _build_iteration_history(
        payload.get("run_id"),
        aggregate_score,
        evaluation.get("previous_iteration"),
        current_iteration=current_iteration,
    )

    student_view = {
        "agent_role": "student",
        "actor": student,
        "sealed_holdout_count": len([s for s in scenarios if s.get("type") == "holdout"]),
        "visible_scenarios": visible_scenarios,
        "public_curriculum_themes": public_curriculum_themes,
        "prompt_summary": evaluation.get("student_prompt_summary")
        or "Train on the visible curriculum only. Hidden holdouts stay sealed.",
    }
    if current_iteration:
        student_view["iteration"] = current_iteration

    teacher_output = {
        "agent_role": "teacher",
        "actor": teacher,
        "aggregate_score": aggregate_score,
        "scenario_results": scenario_results,
        "public_curriculum_themes": public_curriculum_themes,
        "verdict": evaluation.get("teacher_verdict")
        or "Teacher scored the run against public curriculum plus sealed holdouts.",
    }
    if current_iteration:
        teacher_output["iteration"] = current_iteration
    if iteration_history:
        teacher_output["iteration_history"] = iteration_history

    return {
        "student_view": student_view,
        "teacher_output": teacher_output,
        "public_curriculum_themes": public_curriculum_themes,
        "iteration_history": iteration_history,
    }


def _aggregate_scores(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = len([result for result in results if result.get("passed")])
    holdouts = [result for result in results if result.get("type") == "holdout"]
    holdout_total = len(holdouts)
    holdout_passed = len([result for result in holdouts if result.get("passed")])
    average_score = round(
        (sum(float(result.get("score", 0.0)) for result in results) / total) if total else 0.0,
        3,
    )
    return {
        "passed": passed,
        "total": total,
        "pass_rate": round((passed / total) if total else 0.0, 4),
        "average_score": average_score,
        "holdout": {
            "passed": holdout_passed,
            "total": holdout_total,
            "pass_rate": round((holdout_passed / holdout_total) if holdout_total else 0.0, 4),
        },
    }


def _build_iteration_history(
    run_id: str | None,
    aggregate_score: dict[str, Any],
    previous_iteration: Any,
    *,
    current_iteration: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    history = []
    current_label = (current_iteration or {}).get("label") or "current"
    current_index = (current_iteration or {}).get("index")
    if isinstance(previous_iteration, dict):
        previous_aggregate = previous_iteration.get("aggregate_score", {})
        previous_entry = {
            "run_id": previous_iteration.get("run_id"),
            "label": previous_iteration.get("label") or "previous",
            "aggregate_score": previous_aggregate,
        }
        if previous_iteration.get("index") is not None:
            previous_entry["index"] = previous_iteration.get("index")
        history.append(previous_entry)

        current_entry = {
            "run_id": run_id,
            "label": current_label,
            "aggregate_score": aggregate_score,
            "delta": {
                "pass_count": aggregate_score.get("passed", 0)
                - int(previous_aggregate.get("passed", 0) or 0),
                "pass_rate": round(
                    float(aggregate_score.get("pass_rate", 0.0) or 0.0)
                    - float(previous_aggregate.get("pass_rate", 0.0) or 0.0),
                    4,
                ),
                "average_score": round(
                    float(aggregate_score.get("average_score", 0.0) or 0.0)
                    - float(previous_aggregate.get("average_score", 0.0) or 0.0),
                    4,
                ),
                "holdout_pass_count": aggregate_score.get("holdout", {}).get("passed", 0)
                - int(previous_aggregate.get("holdout", {}).get("passed", 0) or 0),
                "holdout_pass_rate": round(
                    float(aggregate_score.get("holdout", {}).get("pass_rate", 0.0) or 0.0)
                    - float(previous_aggregate.get("holdout", {}).get("pass_rate", 0.0) or 0.0),
                    4,
                ),
            },
        }
        if current_index is not None:
            current_entry["index"] = current_index
        history.append(current_entry)
        return history

    current_entry = {
        "run_id": run_id,
        "label": current_label,
        "aggregate_score": aggregate_score,
    }
    if current_index is not None:
        current_entry["index"] = current_index
    history.append(current_entry)
    return history


def _dedupe_failure_themes(themes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for theme in themes:
        key = (theme.get("theme") or "", theme.get("description") or "")
        existing = deduped.get(key)
        if existing:
            existing["source_scenarios"] = sorted(
                set(existing.get("source_scenarios", [])) | set(theme.get("source_scenarios", []))
            )
        else:
            deduped[key] = {
                "theme": theme.get("theme"),
                "description": theme.get("description"),
                "source_scenarios": list(theme.get("source_scenarios", [])),
            }
    return list(deduped.values())


def _public_actor(actor: Any, *, default_role: str) -> dict[str, Any]:
    actor = actor if isinstance(actor, dict) else {}
    return {
        "id": actor.get("id"),
        "name": actor.get("name") or default_role.title(),
        "agent_role": actor.get("agent_role") or default_role,
    }


def _public_iteration(iteration: Any) -> dict[str, Any] | None:
    if not isinstance(iteration, dict):
        return None
    public = {
        "label": iteration.get("label") or "current",
    }
    if iteration.get("index") is not None:
        public["index"] = iteration.get("index")
    if iteration.get("sequence_id"):
        public["sequence_id"] = iteration.get("sequence_id")
    if iteration.get("parent_run_id"):
        public["parent_run_id"] = iteration.get("parent_run_id")
    return public

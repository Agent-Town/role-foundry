from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def write_receipt_provenance(
    run_dir: str | Path,
    request: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    """Write additive receipt/provenance files for one run.

    This layer is intentionally observational. It does not alter scoring logic or
    control-plane behavior; it just makes existing receipts easier to inspect,
    persist, and map back to source artifacts.
    """
    run_dir = Path(run_dir)
    receipts_dir = run_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)

    request_public = _load_json(run_dir / "request.json")
    request_private = _load_json(run_dir / "request.private.json")
    artifact_bundle_path = run_dir / "artifact-bundle.json"
    artifact_bundle = _load_json(artifact_bundle_path)
    transcript_events = _load_ndjson(run_dir / "transcript.ndjson")

    receipt_paths: dict[str, str] = {}
    receipt_index: list[dict[str, Any]] = []
    evidence_entries: list[dict[str, Any]] = []

    candidate_receipt, candidate_evidence = _build_candidate_receipt(
        request=request,
        request_public=request_public,
        artifact_bundle=artifact_bundle,
        result=result,
        transcript_events=transcript_events,
    )
    candidate_path = receipts_dir / "candidate.json"
    candidate_path.write_text(json.dumps(candidate_receipt, indent=2))
    receipt_paths["candidate"] = _relative_path(run_dir, candidate_path)
    receipt_index.append(
        {
            "receipt_id": candidate_receipt["receipt_id"],
            "kind": "candidate",
            "path": receipt_paths["candidate"],
            "visibility": "public",
        }
    )
    evidence_entries.extend(candidate_evidence)

    previous_iteration = ((request_private.get("teacher_evaluation") or {}).get("previous_iteration"))
    if isinstance(previous_iteration, dict):
        baseline_receipt, baseline_evidence = _build_baseline_receipt(
            request=request,
            request_private=request_private,
            artifact_bundle=artifact_bundle,
            result=result,
        )
        baseline_path = receipts_dir / "baseline.json"
        baseline_path.write_text(json.dumps(baseline_receipt, indent=2))
        receipt_paths["baseline"] = _relative_path(run_dir, baseline_path)
        receipt_index.append(
            {
                "receipt_id": baseline_receipt["receipt_id"],
                "kind": "baseline",
                "path": receipt_paths["baseline"],
                "visibility": "public",
            }
        )
        evidence_entries.extend(baseline_evidence)

    has_evaluation = isinstance(artifact_bundle.get("teacher_output"), dict)
    if has_evaluation:
        evaluation_receipt, evaluation_evidence = _build_evaluation_receipt(
            request=request,
            request_private=request_private,
            artifact_bundle=artifact_bundle,
            result=result,
            transcript_events=transcript_events,
        )
        evaluation_path = receipts_dir / "evaluation.json"
        evaluation_path.write_text(json.dumps(evaluation_receipt, indent=2))
        receipt_paths["evaluation"] = _relative_path(run_dir, evaluation_path)
        receipt_index.append(
            {
                "receipt_id": evaluation_receipt["receipt_id"],
                "kind": "evaluation",
                "path": receipt_paths["evaluation"],
                "visibility": "public",
            }
        )
        evidence_entries.extend(evaluation_evidence)

    evidence_index_path = receipts_dir / "evidence-index.json"
    evidence_index = {
        "version": 1,
        "run_id": request.get("run_id"),
        "generated_at": _utc_now(),
        "receipts": receipt_index,
        "entries": evidence_entries,
    }
    evidence_index_path.write_text(json.dumps(evidence_index, indent=2))

    audit_bundle_path = receipts_dir / "audit-bundle.json"
    audit_bundle = _build_audit_bundle(
        run_dir=run_dir,
        request=request,
        request_private=request_private,
        result=result,
        artifact_bundle=artifact_bundle,
        receipt_paths=receipt_paths,
        evidence_entries=evidence_entries,
        audit_bundle_relative_path=_relative_path(run_dir, audit_bundle_path),
    )
    audit_bundle_path.write_text(json.dumps(audit_bundle, indent=2))

    summary_path = receipts_dir / "summary.md"
    summary_path.write_text(
        _build_summary_markdown(
            request=request,
            result=result,
            artifact_bundle=artifact_bundle,
            receipt_paths=receipt_paths,
            evidence_entries=evidence_entries,
            audit_bundle=audit_bundle,
        )
    )

    manifest_path = receipts_dir / "manifest.json"
    manifest = {
        "version": 1,
        "run_id": request.get("run_id"),
        "generated_at": _utc_now(),
        "status": result.get("status"),
        "receipts": {
            "episode_receipt_paths": receipt_paths,
            "evidence_index_path": _relative_path(run_dir, evidence_index_path),
            "summary_path": _relative_path(run_dir, summary_path),
            "audit_bundle_path": _relative_path(run_dir, audit_bundle_path),
        },
        "artifacts": _build_artifact_inventory(
            run_dir,
            receipt_paths=receipt_paths,
            evidence_index_path=evidence_index_path,
            summary_path=summary_path,
            audit_bundle_path=audit_bundle_path,
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))

    provenance = {
        "receipt_manifest_path": _relative_path(run_dir, manifest_path),
        "evidence_index_path": _relative_path(run_dir, evidence_index_path),
        "summary_path": _relative_path(run_dir, summary_path),
        "audit_bundle_path": _relative_path(run_dir, audit_bundle_path),
        "episode_receipt_paths": receipt_paths,
        "evidence_entry_count": len(evidence_entries),
    }

    artifact_receipts = artifact_bundle.get("receipts") if isinstance(artifact_bundle.get("receipts"), dict) else {}
    artifact_receipts.update(
        {
            "receipt_manifest_path": provenance["receipt_manifest_path"],
            "evidence_index_path": provenance["evidence_index_path"],
            "summary_path": provenance["summary_path"],
            "audit_bundle_path": provenance["audit_bundle_path"],
        }
    )
    artifact_bundle["receipts"] = artifact_receipts
    artifact_bundle["provenance"] = provenance
    artifact_bundle_path.write_text(json.dumps(artifact_bundle, indent=2))

    result["provenance"] = provenance
    result_path = run_dir / "result.json"
    result_path.write_text(json.dumps(result, indent=2))

    final_audit_bundle = _build_audit_bundle(
        run_dir=run_dir,
        request=request,
        request_private=request_private,
        result=result,
        artifact_bundle=artifact_bundle,
        receipt_paths=receipt_paths,
        evidence_entries=evidence_entries,
        audit_bundle_relative_path=_relative_path(run_dir, audit_bundle_path),
    )
    final_audit_bundle["artifact_index"] = {
        "status": "finalized",
        "generated_artifacts": _build_audit_artifact_index(
            run_dir,
            receipt_paths=receipt_paths,
            audit_bundle_relative_path=_relative_path(run_dir, audit_bundle_path),
        ),
        "episode_receipt_paths": dict(receipt_paths),
    }
    audit_bundle_path.write_text(json.dumps(final_audit_bundle, indent=2))
    return provenance


def _build_candidate_receipt(
    *,
    request: dict[str, Any],
    request_public: dict[str, Any],
    artifact_bundle: dict[str, Any],
    result: dict[str, Any],
    transcript_events: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    run_id = request.get("run_id")
    workspace = request.get("workspace_snapshot") if isinstance(request.get("workspace_snapshot"), dict) else {}
    student_view = artifact_bundle.get("student_view") if isinstance(artifact_bundle.get("student_view"), dict) else {}
    scenario_manifest = ((request_public.get("teacher_evaluation") or {}).get("scenario_manifest"))

    evidence = [
        {
            "evidence_id": "candidate-workspace",
            "receipt_id": f"candidate:{run_id}",
            "kind": "workspace_snapshot",
            "label": "Current candidate workspace snapshot",
            "summary": workspace.get("objective") or "No explicit objective recorded.",
            "sources": [
                _json_source("request.json", "/workspace_snapshot", visibility="public"),
                _json_source("artifact-bundle.json", "/workspace_snapshot", visibility="public"),
            ],
        }
    ]

    objective_event = _find_event(transcript_events, "runner.objective")
    if objective_event:
        evidence.append(
            {
                "evidence_id": "candidate-transcript-objective",
                "receipt_id": f"candidate:{run_id}",
                "kind": "transcript_event",
                "label": "Run objective logged in transcript",
                "summary": objective_event.get("message") or "runner.objective",
                "sources": [
                    _transcript_source(
                        line=objective_event["line"],
                        event=objective_event.get("event"),
                        visibility="public",
                    )
                ],
            }
        )

    if isinstance(scenario_manifest, list) or student_view:
        visible_scenarios = student_view.get("visible_scenarios") if isinstance(student_view.get("visible_scenarios"), list) else []
        sealed_holdout_count = int(student_view.get("sealed_holdout_count", 0) or 0)
        prompt_event = _find_event(transcript_events, "student.prompt.loaded")
        sources = []
        if isinstance(scenario_manifest, list):
            sources.append(
                _json_source(
                    "request.json",
                    "/teacher_evaluation/scenario_manifest",
                    visibility="public",
                )
            )
        if student_view:
            sources.append(_json_source("artifact-bundle.json", "/student_view", visibility="public"))
        if prompt_event:
            sources.append(
                _transcript_source(
                    line=prompt_event["line"],
                    event=prompt_event.get("event"),
                    visibility="public",
                )
            )
        evidence.append(
            {
                "evidence_id": "candidate-prompt-pack",
                "receipt_id": f"candidate:{run_id}",
                "kind": "prompt_pack",
                "label": "Student-visible prompt pack",
                "summary": f"{len(visible_scenarios)} visible scenarios and {sealed_holdout_count} sealed holdouts.",
                "sources": sources,
            }
        )

    changed_files = workspace.get("changed_files") if isinstance(workspace.get("changed_files"), list) else []
    for index, path in enumerate(changed_files):
        evidence.append(
            {
                "evidence_id": f"candidate-file-{index + 1}",
                "receipt_id": f"candidate:{run_id}",
                "kind": "changed_file",
                "label": f"Changed file: {path}",
                "summary": path,
                "sources": [
                    _json_source(
                        "request.json",
                        f"/workspace_snapshot/changed_files/{index}",
                        visibility="public",
                    )
                ],
            }
        )

    receipt = {
        "receipt_id": f"candidate:{run_id}",
        "kind": "candidate",
        "run_id": run_id,
        "status": result.get("status"),
        "agent_role": request.get("agent_role"),
        "scenario_set_id": request.get("scenario_set_id"),
        "objective": workspace.get("objective"),
        "workspace_snapshot": workspace,
        "student_prompt_pack": {
            "prompt_summary": student_view.get("prompt_summary"),
            "visible_scenario_count": len(student_view.get("visible_scenarios", []))
            if isinstance(student_view.get("visible_scenarios"), list)
            else 0,
            "sealed_holdout_count": student_view.get("sealed_holdout_count", 0) if student_view else 0,
        }
        if student_view
        else None,
        "evidence_refs": [entry["evidence_id"] for entry in evidence],
    }
    return receipt, evidence


def _build_baseline_receipt(
    *,
    request: dict[str, Any],
    request_private: dict[str, Any],
    artifact_bundle: dict[str, Any],
    result: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    previous_iteration = ((request_private.get("teacher_evaluation") or {}).get("previous_iteration")) or {}
    iteration_history = artifact_bundle.get("iteration_history") if isinstance(artifact_bundle.get("iteration_history"), list) else []
    scorecard_history = result.get("scorecard", {}).get("iteration_history") if isinstance(result.get("scorecard"), dict) else []

    sources = [
        _json_source(
            "request.private.json",
            "/teacher_evaluation/previous_iteration",
            visibility="private",
        )
    ]
    if iteration_history:
        sources.append(_json_source("artifact-bundle.json", "/iteration_history/0", visibility="public"))
    if scorecard_history:
        sources.append(_json_source("result.json", "/scorecard/iteration_history/0", visibility="public"))

    evidence = [
        {
            "evidence_id": "baseline-aggregate",
            "receipt_id": f"baseline:{previous_iteration.get('run_id')}",
            "kind": "aggregate_score",
            "label": "Baseline aggregate score",
            "summary": f"{previous_iteration.get('aggregate_score', {}).get('passed', 0)}/{previous_iteration.get('aggregate_score', {}).get('total', 0)} passed before the current run.",
            "sources": sources,
        }
    ]

    receipt = {
        "receipt_id": f"baseline:{previous_iteration.get('run_id')}",
        "kind": "baseline",
        "run_id": previous_iteration.get("run_id"),
        "source_run_id": request.get("run_id"),
        "label": previous_iteration.get("label") or "previous",
        "aggregate_score": previous_iteration.get("aggregate_score", {}),
        "evidence_refs": [entry["evidence_id"] for entry in evidence],
    }
    return receipt, evidence


def _build_evaluation_receipt(
    *,
    request: dict[str, Any],
    request_private: dict[str, Any],
    artifact_bundle: dict[str, Any],
    result: dict[str, Any],
    transcript_events: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    run_id = request.get("run_id")
    teacher_output = artifact_bundle.get("teacher_output") if isinstance(artifact_bundle.get("teacher_output"), dict) else {}
    student_view = artifact_bundle.get("student_view") if isinstance(artifact_bundle.get("student_view"), dict) else {}
    scorecard = result.get("scorecard") if isinstance(result.get("scorecard"), dict) else {}
    iteration_history = artifact_bundle.get("iteration_history") if isinstance(artifact_bundle.get("iteration_history"), list) else []
    current_iteration = iteration_history[-1] if iteration_history else {}
    scorecard_history = scorecard.get("iteration_history") if isinstance(scorecard.get("iteration_history"), list) else []
    private_scenarios = ((request_private.get("teacher_evaluation") or {}).get("scenarios"))
    private_scenarios = private_scenarios if isinstance(private_scenarios, list) else []
    private_index = {
        scenario.get("id"): index for index, scenario in enumerate(private_scenarios) if isinstance(scenario, dict)
    }

    evidence = []

    aggregate_sources = [
        _json_source("artifact-bundle.json", "/teacher_output/aggregate_score", visibility="public"),
        _json_source("result.json", "/scorecard/aggregate_score", visibility="public"),
    ]
    evaluation_done = _find_event(transcript_events, "teacher.evaluation.completed")
    if evaluation_done:
        aggregate_sources.append(
            _transcript_source(
                line=evaluation_done["line"],
                event=evaluation_done.get("event"),
                visibility="public",
            )
        )
    evidence.append(
        {
            "evidence_id": "evaluation-aggregate",
            "receipt_id": f"evaluation:{run_id}",
            "kind": "aggregate_score",
            "label": "Teacher aggregate score",
            "summary": f"{teacher_output.get('aggregate_score', {}).get('passed', 0)}/{teacher_output.get('aggregate_score', {}).get('total', 0)} passed.",
            "sources": aggregate_sources,
        }
    )

    evidence.append(
        {
            "evidence_id": "evaluation-verdict",
            "receipt_id": f"evaluation:{run_id}",
            "kind": "verdict",
            "label": "Teacher verdict",
            "summary": teacher_output.get("verdict") or scorecard.get("verdict") or "",
            "sources": [
                _json_source("artifact-bundle.json", "/teacher_output/verdict", visibility="public"),
                _json_source("result.json", "/scorecard/verdict", visibility="public"),
            ],
        }
    )

    if current_iteration.get("delta"):
        delta_sources = [
            _json_source(
                "artifact-bundle.json",
                f"/iteration_history/{len(iteration_history) - 1}",
                visibility="public",
            )
        ]
        if scorecard_history:
            delta_sources.append(
                _json_source(
                    "result.json",
                    f"/scorecard/iteration_history/{len(scorecard_history) - 1}",
                    visibility="public",
                )
            )
        delta_event = _find_event(transcript_events, "iteration.delta")
        if delta_event:
            delta_sources.append(
                _transcript_source(
                    line=delta_event["line"],
                    event=delta_event.get("event"),
                    visibility="public",
                )
            )
        evidence.append(
            {
                "evidence_id": "evaluation-iteration-delta",
                "receipt_id": f"evaluation:{run_id}",
                "kind": "iteration_delta",
                "label": "Iteration delta vs previous run",
                "summary": f"{current_iteration.get('delta', {}).get('pass_count', 0):+d} passes and {current_iteration.get('delta', {}).get('holdout_pass_count', 0):+d} holdouts.",
                "sources": delta_sources,
            }
        )

    scenario_results = teacher_output.get("scenario_results") if isinstance(teacher_output.get("scenario_results"), list) else []
    for index, scenario in enumerate(scenario_results):
        scenario_id = scenario.get("scenario_id") or f"scenario-{index + 1}"
        sources = [
            _json_source(
                "artifact-bundle.json",
                f"/teacher_output/scenario_results/{index}",
                visibility="public",
            ),
            _json_source(
                "result.json",
                f"/scorecard/scenario_results/{index}",
                visibility="public",
            ),
        ]
        private_pos = private_index.get(scenario_id)
        if private_pos is not None:
            sources.append(
                _json_source(
                    "request.private.json",
                    f"/teacher_evaluation/scenarios/{private_pos}",
                    visibility="private",
                )
            )
        evidence.append(
            {
                "evidence_id": f"evaluation-scenario-{scenario_id}",
                "receipt_id": f"evaluation:{run_id}",
                "kind": "scenario_result",
                "label": f"Scenario {scenario_id}",
                "summary": f"{'passed' if scenario.get('passed') else 'failed'} at {float(scenario.get('score', 0.0)):.3f}",
                "tags": [
                    f"scenario:{scenario_id}",
                    f"type:{scenario.get('type') or 'unknown'}",
                    f"visibility:{scenario.get('visibility') or 'unknown'}",
                ],
                "sources": sources,
            }
        )

    public_themes = artifact_bundle.get("public_curriculum_themes") if isinstance(artifact_bundle.get("public_curriculum_themes"), list) else []
    for index, theme in enumerate(public_themes):
        evidence.append(
            {
                "evidence_id": f"evaluation-theme-{index + 1}",
                "receipt_id": f"evaluation:{run_id}",
                "kind": "public_curriculum_theme",
                "label": theme.get("theme") or f"Theme {index + 1}",
                "summary": theme.get("description") or "",
                "sources": [
                    _json_source(
                        "artifact-bundle.json",
                        f"/public_curriculum_themes/{index}",
                        visibility="public",
                    ),
                    _json_source(
                        "result.json",
                        f"/scorecard/public_curriculum_themes/{index}",
                        visibility="public",
                    ),
                ],
            }
        )

    receipt = {
        "receipt_id": f"evaluation:{run_id}",
        "kind": "evaluation",
        "run_id": run_id,
        "status": result.get("status"),
        "teacher": teacher_output.get("actor") or scorecard.get("teacher"),
        "student": student_view.get("actor") or scorecard.get("student"),
        "aggregate_score": teacher_output.get("aggregate_score") or scorecard.get("aggregate_score"),
        "iteration_delta": current_iteration.get("delta"),
        "verdict": teacher_output.get("verdict") or scorecard.get("verdict"),
        "scenario_results": scenario_results,
        "public_curriculum_themes": public_themes,
        "evidence_refs": [entry["evidence_id"] for entry in evidence],
    }
    return receipt, evidence


def _build_audit_bundle(
    *,
    run_dir: Path,
    request: dict[str, Any],
    request_private: dict[str, Any],
    result: dict[str, Any],
    artifact_bundle: dict[str, Any],
    receipt_paths: dict[str, str],
    evidence_entries: list[dict[str, Any]],
    audit_bundle_relative_path: str,
) -> dict[str, Any]:
    sections = _build_human_audit_sections(
        request=request,
        request_private=request_private,
        result=result,
        artifact_bundle=artifact_bundle,
        evidence_entries=evidence_entries,
    )
    return {
        "version": 1,
        "run_id": request.get("run_id"),
        "status": result.get("status"),
        "generated_at": _utc_now(),
        "artifact_index": {
            "status": "pending_manifest_finalize",
            "generated_artifacts": [],
            "episode_receipt_paths": dict(receipt_paths),
            "audit_bundle_path": audit_bundle_relative_path,
        },
        "required_artifact_validation": _validate_required_artifacts(run_dir, request_private),
        "redaction_audit": _check_redaction_correctness(
            run_dir,
            request_private,
            receipt_paths=receipt_paths,
            audit_bundle_relative_path=audit_bundle_relative_path,
        ),
        "traceability": _build_traceability_block(request, request_private, artifact_bundle),
        "human_audit": {
            "status": _summarize_human_audit_status(sections),
            "required_sections": list(_AUDIT_SECTION_ORDER),
            "sections": sections,
        },
        "section_availability": {
            name: sections.get(name, {}).get("status") != "unavailable" for name in sections
        },
    }


_AUDIT_SECTION_ORDER = (
    "run_metadata",
    "benchmark_input_summary",
    "mutation_summary",
    "teacher_scorecard",
    "verdict_and_reasons",
)

_REDACTION_FORBIDDEN_KEYS = {"teacher_prompt", "holdout_prompt", "scoring_rubric"}


def _build_human_audit_sections(
    *,
    request: dict[str, Any],
    request_private: dict[str, Any],
    result: dict[str, Any],
    artifact_bundle: dict[str, Any],
    evidence_entries: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    workspace = request.get("workspace_snapshot") if isinstance(request.get("workspace_snapshot"), dict) else {}
    scorecard = result.get("scorecard") if isinstance(result.get("scorecard"), dict) else {}
    execution_honesty = result.get("execution_honesty") if isinstance(result.get("execution_honesty"), dict) else {}
    teacher_output = artifact_bundle.get("teacher_output") if isinstance(artifact_bundle.get("teacher_output"), dict) else {}
    student_view = artifact_bundle.get("student_view") if isinstance(artifact_bundle.get("student_view"), dict) else {}
    packet_runtime = request_private.get("packet_runtime") if isinstance(request_private.get("packet_runtime"), dict) else {}
    request_traceability = request_private.get("traceability") if isinstance(request_private.get("traceability"), dict) else {}
    request_traceability = request_traceability or (
        request.get("traceability") if isinstance(request.get("traceability"), dict) else {}
    )

    run_metadata = {
        "status": "available",
        "data": {
            "run_id": request.get("run_id"),
            "status": result.get("status"),
            "agent_role": request.get("agent_role"),
            "scenario_set_id": request.get("scenario_set_id"),
            "runner": scorecard.get("runner") or execution_honesty.get("backend") or "unknown",
            "execution_mode": "local_replay"
            if (scorecard.get("runner") or execution_honesty.get("backend")) == "LocalReplayRunner"
            else "unknown",
            "execution_backend": {
                "backend": execution_honesty.get("backend"),
                "executes_commands": execution_honesty.get("executes_commands"),
                "executes_checks": execution_honesty.get("executes_checks"),
                "mutation_enforcement": execution_honesty.get("mutation_enforcement"),
                "path_constraint_enforcement": execution_honesty.get("path_constraint_enforcement"),
                "honesty_note": execution_honesty.get("honesty_note"),
            },
            "started_at": result.get("started_at"),
            "finished_at": result.get("finished_at"),
            "evidence_entry_count": len(evidence_entries),
        },
    }
    if packet_runtime:
        run_metadata["data"]["packet_runtime"] = {
            "packet_id": packet_runtime.get("packet_id"),
            "packet_version": packet_runtime.get("packet_version"),
            "acceptance_test_id": packet_runtime.get("acceptance_test_id"),
            "role_id": packet_runtime.get("role_id"),
        }

    visible_episode_ids = [
        scenario.get("id")
        for scenario in student_view.get("visible_scenarios", [])
        if isinstance(scenario, dict) and scenario.get("id")
    ]
    benchmark_pack = request_traceability.get("benchmark_pack") if isinstance(request_traceability.get("benchmark_pack"), dict) else {}
    benchmark_data = {
        "objective": workspace.get("objective"),
        "changed_files": workspace.get("changed_files") if isinstance(workspace.get("changed_files"), list) else [],
        "visible_scenario_count": len(student_view.get("visible_scenarios", [])) if isinstance(student_view.get("visible_scenarios"), list) else 0,
        "sealed_holdout_count": int(student_view.get("sealed_holdout_count", 0) or 0),
        "benchmark_pack_id": benchmark_pack.get("id"),
        "benchmark_pack_version": benchmark_pack.get("version"),
        "episode_ids": visible_episode_ids,
        "family_ids": list(request_traceability.get("family_ids") or []),
    }
    if any(
        [
            benchmark_data["objective"],
            benchmark_data["changed_files"],
            benchmark_data["visible_scenario_count"],
            benchmark_data["benchmark_pack_id"],
            benchmark_data["episode_ids"],
        ]
    ):
        benchmark_input_summary = {"status": "available", "data": benchmark_data}
    else:
        benchmark_input_summary = {
            "status": "unavailable",
            "honesty_note": "No benchmark-input summary could be derived from this run path.",
            "data": benchmark_data,
        }

    mutation_surface_audit = execution_honesty.get("mutation_surface_audit") if isinstance(execution_honesty.get("mutation_surface_audit"), dict) else None
    mutation_budget = packet_runtime.get("mutation_budget") if isinstance(packet_runtime.get("mutation_budget"), dict) else None
    if mutation_surface_audit:
        source = mutation_surface_audit.get("source") if isinstance(mutation_surface_audit.get("source"), dict) else {}
        mutation_summary = {
            "status": "partial" if mutation_surface_audit.get("status") == "unavailable" else "available",
            "honesty_note": mutation_surface_audit.get("honesty_note"),
            "data": {
                "audit_status": mutation_surface_audit.get("status"),
                "diff_source_kind": source.get("kind"),
                "changed_files": mutation_surface_audit.get("changed_files"),
                "budget_report": mutation_surface_audit.get("budget_report"),
                "violations": mutation_surface_audit.get("violations"),
            },
        }
    elif mutation_budget or execution_honesty:
        mutation_summary = {
            "status": "partial",
            "honesty_note": (
                "This run declared mutation/path budgets and execution honesty limits, but did not emit a dedicated mutation-surface audit receipt. "
                "On the clean benchmark spine that means mutation discipline is only partially observable here."
            ),
            "data": {
                "audit_status": "not_emitted",
                "changed_files": workspace.get("changed_files") if isinstance(workspace.get("changed_files"), list) else [],
                "budget_report": mutation_budget or {},
                "violations": [],
                "mutation_enforcement": execution_honesty.get("mutation_enforcement"),
                "path_constraint_enforcement": execution_honesty.get("path_constraint_enforcement"),
            },
        }
    else:
        mutation_summary = {
            "status": "unavailable",
            "honesty_note": "No mutation-discipline metadata was available for this run path.",
            "data": {},
        }

    aggregate_score = None
    if isinstance(teacher_output.get("aggregate_score"), dict):
        aggregate_score = teacher_output.get("aggregate_score")
    elif isinstance(scorecard.get("aggregate_score"), dict):
        aggregate_score = scorecard.get("aggregate_score")

    if aggregate_score:
        teacher_scorecard = {
            "status": "available",
            "data": {
                "aggregate_score": aggregate_score,
                "teacher": teacher_output.get("actor") or scorecard.get("teacher"),
                "student": student_view.get("actor") or scorecard.get("student"),
                "scenario_count": len(teacher_output.get("scenario_results", []))
                if isinstance(teacher_output.get("scenario_results"), list)
                else len(scorecard.get("scenario_results", []))
                if isinstance(scorecard.get("scenario_results"), list)
                else 0,
                "public_curriculum_theme_count": len(artifact_bundle.get("public_curriculum_themes", []))
                if isinstance(artifact_bundle.get("public_curriculum_themes"), list)
                else 0,
            },
        }
    else:
        teacher_scorecard = {
            "status": "unavailable",
            "honesty_note": "Teacher scorecard is unavailable on this student/local/sample path.",
            "data": {},
        }

    verdict = teacher_output.get("verdict") or scorecard.get("verdict")
    if verdict:
        verdict_and_reasons = {
            "status": "available",
            "data": {
                "verdict": verdict,
                "public_curriculum_themes": artifact_bundle.get("public_curriculum_themes")
                if isinstance(artifact_bundle.get("public_curriculum_themes"), list)
                else [],
            },
        }
        iteration_history = artifact_bundle.get("iteration_history") if isinstance(artifact_bundle.get("iteration_history"), list) else []
        if iteration_history and isinstance(iteration_history[-1], dict) and isinstance(iteration_history[-1].get("delta"), dict):
            verdict_and_reasons["data"]["iteration_delta"] = iteration_history[-1]["delta"]
    elif teacher_scorecard["status"] == "available":
        verdict_and_reasons = {
            "status": "partial",
            "honesty_note": "A teacher scorecard exists, but no explicit verdict text was emitted.",
            "data": {},
        }
    else:
        verdict_and_reasons = {
            "status": "unavailable",
            "honesty_note": "Verdict and reasons are unavailable on this student/local/sample path.",
            "data": {},
        }

    return {
        "run_metadata": run_metadata,
        "benchmark_input_summary": benchmark_input_summary,
        "mutation_summary": mutation_summary,
        "teacher_scorecard": teacher_scorecard,
        "verdict_and_reasons": verdict_and_reasons,
    }


def _summarize_human_audit_status(sections: dict[str, dict[str, Any]]) -> str:
    statuses = {sections.get(name, {}).get("status", "unavailable") for name in _AUDIT_SECTION_ORDER}
    if statuses == {"available"}:
        return "complete"
    if "available" in statuses or "partial" in statuses:
        return "partial"
    return "unavailable"


def _validate_required_artifacts(run_dir: Path, request_private: dict[str, Any]) -> dict[str, Any]:
    packet_runtime = request_private.get("packet_runtime") if isinstance(request_private.get("packet_runtime"), dict) else None
    if not packet_runtime:
        return {
            "status": "not_applicable",
            "declared_count": 0,
            "present_count": 0,
            "missing_count": 0,
            "honesty_note": "No packet_runtime block was available for this run, so required-artifact validation does not apply.",
            "results": [],
        }

    evidence_contract = packet_runtime.get("evidence_contract") if isinstance(packet_runtime.get("evidence_contract"), dict) else {}
    required_artifacts = evidence_contract.get("required_artifacts")
    if not isinstance(required_artifacts, list) or not required_artifacts:
        return {
            "status": "not_applicable",
            "declared_count": 0,
            "present_count": 0,
            "missing_count": 0,
            "honesty_note": "The packet evidence contract did not declare any required_artifacts.",
            "results": [],
        }

    repo_root = Path(__file__).resolve().parents[1]
    results = []
    present_count = 0
    for artifact in required_artifacts:
        if not isinstance(artifact, dict):
            continue
        relative_path = str(artifact.get("path") or "")
        in_repo = bool(relative_path) and (repo_root / relative_path).exists()
        in_run = bool(relative_path) and (run_dir / relative_path).exists()
        if in_repo and in_run:
            present_in = "repo+run"
        elif in_repo:
            present_in = "repo"
        elif in_run:
            present_in = "run"
        else:
            present_in = "missing"
        is_present = present_in != "missing"
        if is_present:
            present_count += 1
        results.append(
            {
                "path": relative_path,
                "visibility": artifact.get("visibility"),
                "description": artifact.get("description"),
                "status": "pass" if is_present else "missing",
                "present_in": present_in,
                "found_in_repo": in_repo,
                "found_in_run": in_run,
            }
        )

    missing_count = len(results) - present_count
    return {
        "status": "pass" if missing_count == 0 else "missing",
        "declared_count": len(results),
        "present_count": present_count,
        "missing_count": missing_count,
        "honesty_note": (
            "This validates declared artifact presence in the checked-out repo and emitted run directory only. "
            "It does not prove command execution, live mutation, or semantic correctness."
        ),
        "results": results,
    }


def _check_redaction_correctness(
    run_dir: Path,
    request_private: dict[str, Any],
    *,
    receipt_paths: dict[str, str],
    audit_bundle_relative_path: str,
) -> dict[str, Any]:
    sensitive_values = _collect_sensitive_private_values(request_private)
    checks: list[dict[str, Any]] = []
    public_surfaces = [
        "request.json",
        "artifact-bundle.json",
        "result.json",
        "run-object.json",
        "receipts/evidence-index.json",
        "receipts/manifest.json",
        "receipts/summary.md",
        audit_bundle_relative_path,
    ]
    public_surfaces.extend(receipt_paths.values())

    seen: set[str] = set()
    for relative_path in public_surfaces:
        if relative_path in seen:
            continue
        seen.add(relative_path)
        surface_path = run_dir / relative_path
        if not surface_path.exists() or not surface_path.is_file():
            checks.append(
                {
                    "surface": relative_path,
                    "status": "not_emitted",
                    "honesty_note": f"{relative_path} was not emitted for this run path.",
                }
            )
            continue

        leaked_keys: list[str] = []
        leaked_values: list[str] = []
        content = surface_path.read_text()
        if surface_path.suffix == ".json":
            try:
                leaked_keys = _find_keys_recursive(json.loads(content), _REDACTION_FORBIDDEN_KEYS)
            except json.JSONDecodeError:
                leaked_keys = []
        leaked_values = [value for value in sensitive_values if value and value in content]
        checks.append(
            {
                "surface": relative_path,
                "status": "leak_detected" if leaked_keys or leaked_values else "clean",
                "structural_leaked_keys": leaked_keys,
                "literal_leak_count": len(leaked_values),
            }
        )

    read_model_exports = sorted(run_dir.rglob("*read-model*.json"))
    if read_model_exports:
        for export_path in read_model_exports:
            relative_path = _relative_path(run_dir, export_path)
            content = export_path.read_text()
            leaked_keys = []
            try:
                leaked_keys = _find_keys_recursive(json.loads(content), _REDACTION_FORBIDDEN_KEYS)
            except json.JSONDecodeError:
                leaked_keys = []
            leaked_values = [value for value in sensitive_values if value and value in content]
            checks.append(
                {
                    "surface": relative_path,
                    "status": "leak_detected" if leaked_keys or leaked_values else "clean",
                    "structural_leaked_keys": leaked_keys,
                    "literal_leak_count": len(leaked_values),
                }
            )
    else:
        checks.append(
            {
                "surface": "read-model-export",
                "status": "not_emitted",
                "honesty_note": "Current runtime does not emit a run-scoped read-model export for this path.",
            }
        )

    return {
        "status": "pass" if all(check.get("status") in {"clean", "not_emitted"} for check in checks) else "leak_detected",
        "sensitive_value_count": len(sensitive_values),
        "checked_surface_count": len(checks),
        "honesty_note": "Redaction audit checks structural teacher-only keys plus literal teacher/holdout prompt and rubric fragments across public and student-facing artifacts.",
        "checks": checks,
    }


def _collect_sensitive_private_values(request_private: dict[str, Any]) -> list[str]:
    teacher_evaluation = request_private.get("teacher_evaluation") if isinstance(request_private.get("teacher_evaluation"), dict) else {}
    sensitive: list[str] = []
    for scenario in teacher_evaluation.get("scenarios", []):
        if not isinstance(scenario, dict):
            continue
        for key in ("teacher_prompt", "holdout_prompt"):
            value = scenario.get(key)
            if isinstance(value, str) and value.strip():
                sensitive.append(value)
        rubric = scenario.get("scoring_rubric")
        sensitive.extend(_collect_strings(rubric))
    return sorted({value for value in sensitive if isinstance(value, str) and len(value.strip()) >= 12})


def _collect_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(_collect_strings(item))
        return strings
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(_collect_strings(item))
        return strings
    return []


def _find_keys_recursive(obj: Any, keys: set[str], prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}/{key}" if prefix else f"/{key}"
            if key in keys:
                found.append(path)
            found.extend(_find_keys_recursive(value, keys, path))
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            found.extend(_find_keys_recursive(item, keys, f"{prefix}/{index}"))
    return found


def _build_traceability_block(
    request: dict[str, Any],
    request_private: dict[str, Any],
    artifact_bundle: dict[str, Any],
) -> dict[str, Any]:
    request_traceability = request_private.get("traceability") if isinstance(request_private.get("traceability"), dict) else {}
    request_traceability = request_traceability or (
        request.get("traceability") if isinstance(request.get("traceability"), dict) else {}
    )
    packet_runtime = request_private.get("packet_runtime") if isinstance(request_private.get("packet_runtime"), dict) else {}
    student_view = artifact_bundle.get("student_view") if isinstance(artifact_bundle.get("student_view"), dict) else {}
    previous_iteration = ((request_private.get("teacher_evaluation") or {}).get("previous_iteration"))

    packet_runtime_block = {
        "status": "available",
        "packet_id": packet_runtime.get("packet_id"),
        "packet_version": packet_runtime.get("packet_version"),
        "packet_content_hash": packet_runtime.get("packet_content_hash"),
        "acceptance_test_id": packet_runtime.get("acceptance_test_id"),
        "role_id": packet_runtime.get("role_id"),
        "execution_backend": packet_runtime.get("execution_backend"),
    } if packet_runtime else {
        "status": "unavailable",
        "honesty_note": "No packet_runtime contract was attached to this run path.",
    }

    benchmark_pack = request_traceability.get("benchmark_pack") if isinstance(request_traceability.get("benchmark_pack"), dict) else {}
    benchmark_pack_block = {
        "status": "available",
        "id": benchmark_pack.get("id"),
        "version": benchmark_pack.get("version"),
        "role_scope": benchmark_pack.get("role_scope"),
    }
    if not benchmark_pack_block.get("id") and not benchmark_pack_block.get("version"):
        benchmark_pack_block = {
            "status": "unavailable",
            "honesty_note": "No benchmark-pack metadata was available for this run path.",
        }

    visible_episode_ids = [
        scenario.get("id")
        for scenario in student_view.get("visible_scenarios", [])
        if isinstance(scenario, dict) and scenario.get("id")
    ]
    family_ids = list(request_traceability.get("family_ids") or [])
    episodes_block: dict[str, Any] = {
        "status": "available" if visible_episode_ids or family_ids or student_view.get("sealed_holdout_count") else "unavailable",
        "visible_episode_ids": visible_episode_ids,
        "family_ids": family_ids,
        "sealed_holdout_count": int(student_view.get("sealed_holdout_count", 0) or 0),
    }
    if episodes_block["status"] == "unavailable":
        episodes_block["honesty_note"] = "Episode-level traceability was not available for this run path."

    lineage_block = {
        "status": "available",
        "run_id": request.get("run_id"),
        "scenario_set_id": request.get("scenario_set_id"),
        "agent_role": request.get("agent_role"),
        "sequence_id": request_traceability.get("sequence_id"),
        "stage_key": request_traceability.get("stage_key"),
        "root_run_id": request_traceability.get("root_run_id"),
        "parent_run_id": request_traceability.get("parent_run_id"),
        "iteration_index": request_traceability.get("iteration_index"),
        "iteration_label": request_traceability.get("iteration_label"),
        "previous_iteration_run_id": previous_iteration.get("run_id") if isinstance(previous_iteration, dict) else None,
    }

    return {
        "packet_runtime": packet_runtime_block,
        "benchmark_pack": benchmark_pack_block,
        "episodes": episodes_block,
        "lineage": lineage_block,
    }


def _build_audit_artifact_index(
    run_dir: Path,
    *,
    receipt_paths: dict[str, str],
    audit_bundle_relative_path: str,
) -> list[dict[str, Any]]:
    artifact_specs = [
        ("request.json", "public", "request"),
        ("request.private.json", "private", "request"),
        ("stdout.log", "private", "log"),
        ("stderr.log", "private", "log"),
        ("transcript.ndjson", "public", "receipt"),
        ("artifact-bundle.json", "public", "receipt"),
        ("result.json", "public", "receipt"),
        ("run-object.json", "public", "packet-runtime"),
        ("receipts/manifest.json", "public", "receipt-provenance"),
        ("receipts/evidence-index.json", "public", "receipt-provenance"),
        ("receipts/summary.md", "public", "receipt-provenance"),
        (audit_bundle_relative_path, "public", "receipt-provenance"),
    ]
    for relative_path in receipt_paths.values():
        artifact_specs.append((relative_path, "public", "receipt-provenance"))

    seen: set[str] = set()
    index: list[dict[str, Any]] = []
    for relative_path, visibility, category in artifact_specs:
        if relative_path in seen:
            continue
        seen.add(relative_path)
        full_path = run_dir / relative_path
        entry: dict[str, Any] = {
            "path": relative_path,
            "visibility": visibility,
            "category": category,
            "exists": full_path.exists(),
        }
        if full_path.exists() and full_path.is_file():
            entry["bytes"] = full_path.stat().st_size
            if relative_path != audit_bundle_relative_path:
                entry["sha256"] = _sha256(full_path)
        index.append(entry)
    return index


def _build_artifact_inventory(
    run_dir: Path,
    *,
    receipt_paths: dict[str, str],
    evidence_index_path: Path,
    summary_path: Path,
    audit_bundle_path: Path | None = None,
) -> list[dict[str, Any]]:
    inventory_specs = [
        (run_dir / "request.json", "public", "Redacted request artifact copy", "request"),
        (run_dir / "request.private.json", "private", "Raw backend request", "request"),
        (run_dir / "stdout.log", "private", "Backend stdout log", "log"),
        (run_dir / "stderr.log", "private", "Backend stderr log", "log"),
        (run_dir / "transcript.ndjson", "public", "Run transcript", "receipt"),
        (run_dir / "artifact-bundle.json", "public", "Artifact bundle", "receipt"),
        (run_dir / "result.json", "public", "Normalized bridge result", "receipt"),
        (run_dir / "run-object.json", "public", "Packet runtime run-object export", "packet-runtime"),
    ]
    for kind, relative_path in receipt_paths.items():
        inventory_specs.append(
            (
                run_dir / relative_path,
                "public",
                f"{kind.title()} receipt export",
                "receipt-provenance",
            )
        )
    specs_tail = [
        (evidence_index_path, "public", "Receipt evidence index", "receipt-provenance"),
        (summary_path, "public", "Human-readable receipt summary", "receipt-provenance"),
    ]
    if audit_bundle_path is not None:
        specs_tail.append(
            (audit_bundle_path, "public", "Machine-readable audit bundle", "receipt-provenance"),
        )
    inventory_specs.extend(specs_tail)

    artifacts = []
    for path, visibility, description, category in inventory_specs:
        if not path.exists():
            continue
        artifacts.append(
            {
                "path": _relative_path(run_dir, path),
                "visibility": visibility,
                "category": category,
                "description": description,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return artifacts


def _build_summary_markdown(
    *,
    request: dict[str, Any],
    result: dict[str, Any],
    artifact_bundle: dict[str, Any],
    receipt_paths: dict[str, str],
    evidence_entries: list[dict[str, Any]],
    audit_bundle: dict[str, Any] | None = None,
) -> str:
    lines = [
        f"# Receipt provenance — {request.get('run_id')}",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Agent role: `{request.get('agent_role')}`",
        f"- Scenario set: `{request.get('scenario_set_id')}`",
        f"- Evidence entries: `{len(evidence_entries)}`",
        "",
        "## Receipt files",
    ]

    for kind in ("candidate", "baseline", "evaluation"):
        if kind in receipt_paths:
            lines.append(f"- {kind.title()}: `{receipt_paths[kind]}`")

    lines.extend(
        [
            "- Evidence index: `receipts/evidence-index.json`",
            "- Audit bundle: `receipts/audit-bundle.json`",
            "- Manifest: `receipts/manifest.json`",
            "- Summary: `receipts/summary.md`",
            "",
            "## Canonical source artifacts",
            "- `request.json` — redacted request artifact copy",
            "- `request.private.json` — raw backend request (private)",
            "- `transcript.ndjson` — timeline of the run",
            "- `artifact-bundle.json` — stored run bundle",
            "- `result.json` — normalized bridge result",
            "- `run-object.json` — packet runtime export when packet-driven",
        ]
    )

    teacher_output = artifact_bundle.get("teacher_output") if isinstance(artifact_bundle.get("teacher_output"), dict) else {}
    aggregate = teacher_output.get("aggregate_score") if isinstance(teacher_output.get("aggregate_score"), dict) else None
    current_iteration = None
    if isinstance(artifact_bundle.get("iteration_history"), list) and artifact_bundle["iteration_history"]:
        current_iteration = artifact_bundle["iteration_history"][-1]

    if aggregate:
        lines.extend(
            [
                "",
                "## Evaluation snapshot",
                f"- Aggregate: `{aggregate.get('passed', 0)}/{aggregate.get('total', 0)}` passed (`{aggregate.get('pass_rate', 0.0):.0%}`)",
                f"- Holdouts: `{aggregate.get('holdout', {}).get('passed', 0)}/{aggregate.get('holdout', {}).get('total', 0)}` passed",
                f"- Public curriculum themes: `{len(artifact_bundle.get('public_curriculum_themes', []))}`",
            ]
        )
        if isinstance(current_iteration, dict) and isinstance(current_iteration.get("delta"), dict):
            delta = current_iteration["delta"]
            lines.append(
                f"- Iteration delta: `{delta.get('pass_count', 0):+d}` passes, `{delta.get('holdout_pass_count', 0):+d}` holdouts"
            )

    sections = ((audit_bundle or {}).get("human_audit") or {}).get("sections") or {}
    lines.extend(
        [
            "",
            "## Audit bundle",
            "- Machine-readable bundle: `receipts/audit-bundle.json`",
            f"- Overall human-audit status: `{((audit_bundle or {}).get('human_audit') or {}).get('status', 'unavailable')}`",
            "",
        ]
    )
    for heading, key in (
        ("Run metadata", "run_metadata"),
        ("Benchmark input summary", "benchmark_input_summary"),
        ("Mutation summary", "mutation_summary"),
        ("Teacher scorecard", "teacher_scorecard"),
        ("Verdict and reasons", "verdict_and_reasons"),
    ):
        section = sections.get(key, {})
        lines.extend(
            [
                f"## {heading}",
                f"- Status: `{section.get('status', 'unavailable')}`",
            ]
        )
        honesty_note = section.get("honesty_note")
        if honesty_note:
            lines.append(f"- Honesty note: {honesty_note}")
        lines.append("")

    return "\n".join(lines) + "\n"


def _find_event(events: list[dict[str, Any]], event_name: str) -> dict[str, Any] | None:
    for event in events:
        if event.get("event") == event_name:
            return event
    return None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    return payload if isinstance(payload, dict) else {}


def _load_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events = []
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        payload = json.loads(raw_line)
        if isinstance(payload, dict):
            payload = dict(payload)
            payload["line"] = line_number
            events.append(payload)
    return events


def _json_source(path: str, json_pointer: str, *, visibility: str) -> dict[str, Any]:
    return {
        "artifact_path": path,
        "json_pointer": json_pointer,
        "visibility": visibility,
    }


def _transcript_source(*, line: int, event: Any, visibility: str) -> dict[str, Any]:
    return {
        "artifact_path": "transcript.ndjson",
        "line": line,
        "event": event,
        "visibility": visibility,
    }


def _relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

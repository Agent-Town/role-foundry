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

    summary_path = receipts_dir / "summary.md"
    summary_path.write_text(
        _build_summary_markdown(
            request=request,
            result=result,
            artifact_bundle=artifact_bundle,
            receipt_paths=receipt_paths,
            evidence_entries=evidence_entries,
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
        },
        "artifacts": _build_artifact_inventory(
            run_dir,
            receipt_paths=receipt_paths,
            evidence_index_path=evidence_index_path,
            summary_path=summary_path,
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))

    provenance = {
        "receipt_manifest_path": _relative_path(run_dir, manifest_path),
        "evidence_index_path": _relative_path(run_dir, evidence_index_path),
        "summary_path": _relative_path(run_dir, summary_path),
        "episode_receipt_paths": receipt_paths,
        "evidence_entry_count": len(evidence_entries),
    }

    artifact_receipts = artifact_bundle.get("receipts") if isinstance(artifact_bundle.get("receipts"), dict) else {}
    artifact_receipts.update(
        {
            "receipt_manifest_path": provenance["receipt_manifest_path"],
            "evidence_index_path": provenance["evidence_index_path"],
            "summary_path": provenance["summary_path"],
        }
    )
    artifact_bundle["receipts"] = artifact_receipts
    artifact_bundle["provenance"] = provenance
    artifact_bundle_path.write_text(json.dumps(artifact_bundle, indent=2))

    result["provenance"] = provenance
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

    prompt_pack_summary = None
    if student_view:
        prompt_pack_summary = {
            "prompt_summary": student_view.get("prompt_summary"),
            "visible_scenario_count": len(student_view.get("visible_scenarios", []))
            if isinstance(student_view.get("visible_scenarios"), list)
            else 0,
            "sealed_holdout_count": student_view.get("sealed_holdout_count", 0) if student_view else 0,
        }
        repo_task_pack = student_view.get("repo_task_pack")
        if isinstance(repo_task_pack, dict):
            rtp_summary: dict[str, Any] = {
                "role_scope": repo_task_pack.get("role_scope"),
                "dataset_id": repo_task_pack.get("dataset_id"),
                "dataset_version": repo_task_pack.get("dataset_version"),
                "episode_count": repo_task_pack.get("episode_count"),
                "family_ids": repo_task_pack.get("family_ids"),
                "honesty_note": repo_task_pack.get("honesty_note"),
            }
            rvc = repo_task_pack.get("recommended_verifier_commands")
            if isinstance(rvc, list) and rvc:
                rtp_summary["recommended_verifier_commands"] = list(rvc)
            prompt_pack_summary["repo_task_pack"] = rtp_summary

    receipt = {
        "receipt_id": f"candidate:{run_id}",
        "kind": "candidate",
        "run_id": run_id,
        "status": result.get("status"),
        "agent_role": request.get("agent_role"),
        "scenario_set_id": request.get("scenario_set_id"),
        "objective": workspace.get("objective"),
        "workspace_snapshot": workspace,
        "student_prompt_pack": prompt_pack_summary,
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


def _build_artifact_inventory(
    run_dir: Path,
    *,
    receipt_paths: dict[str, str],
    evidence_index_path: Path,
    summary_path: Path,
) -> list[dict[str, Any]]:
    inventory_specs = [
        (run_dir / "request.json", "public", "Redacted request artifact copy", "request"),
        (run_dir / "request.private.json", "private", "Raw backend request", "request"),
        (run_dir / "stdout.log", "private", "Backend stdout log", "log"),
        (run_dir / "stderr.log", "private", "Backend stderr log", "log"),
        (run_dir / "transcript.ndjson", "public", "Run transcript", "receipt"),
        (run_dir / "artifact-bundle.json", "public", "Artifact bundle", "receipt"),
        (run_dir / "result.json", "public", "Normalized bridge result", "receipt"),
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
    inventory_specs.extend(
        [
            (evidence_index_path, "public", "Receipt evidence index", "receipt-provenance"),
            (summary_path, "public", "Human-readable receipt summary", "receipt-provenance"),
        ]
    )

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
            f"- Evidence index: `receipts/evidence-index.json`",
            f"- Manifest: `receipts/manifest.json`",
            f"- Summary: `receipts/summary.md`",
            "",
            "## Canonical source artifacts",
            "- `request.json` — redacted request artifact copy",
            "- `request.private.json` — raw backend request (private)",
            "- `transcript.ndjson` — timeline of the run",
            "- `artifact-bundle.json` — stored run bundle",
            "- `result.json` — normalized bridge result",
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

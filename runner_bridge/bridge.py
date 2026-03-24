from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contract import ContractError, RunRequest
from .eval_loop import redact_request_for_artifacts
from .mutation_surface import audit_packet_mutation_surface, write_mutation_surface_audit_receipt
from .product_integrations import write_product_integrations
from .provenance import (
    build_execution_backend_surface,
    refresh_receipt_provenance_audit_bundle,
    write_receipt_provenance,
)

ALLOWED_STATUSES = {"completed", "failed", "timeout"}


class ClawithRunClient:
    def __init__(self, base_url: str | None = None, secret: str = ""):
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.secret = secret

    def patch_run(self, run_id: str, payload: dict[str, Any]) -> None:
        if not self.base_url:
            return

        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["Authorization"] = f"Bearer {self.secret}"

        request = urllib.request.Request(
            f"{self.base_url}/api/runs/{run_id}",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="PATCH",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status >= 400:
                    raise ContractError(f"control plane rejected run patch: HTTP {response.status}")
        except urllib.error.URLError as exc:
            raise ContractError(f"failed to patch run state: {exc}") from exc


class RunBridge:
    def __init__(
        self,
        artifacts_root: str | Path = "runtime/runs",
        control_plane: ClawithRunClient | None = None,
        backend_command: list[str] | None = None,
    ):
        self.artifacts_root = Path(artifacts_root)
        self.control_plane = control_plane or ClawithRunClient()
        self.backend_command = backend_command or [
            sys.executable,
            "-m",
            "runner_bridge.backends.local_replay",
        ]

    def run(self, request: RunRequest) -> dict[str, Any]:
        run_dir = self.artifacts_root / request.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        raw_request = request.to_dict()
        request_path = run_dir / "request.json"
        private_request_path = run_dir / "request.private.json"
        request_path.write_text(json.dumps(redact_request_for_artifacts(raw_request), indent=2))
        private_request_path.write_text(json.dumps(raw_request, indent=2))

        packet_runtime = raw_request.get("packet_runtime")
        if packet_runtime:
            run_object_path = run_dir / "run-object.json"
            run_object_path.write_text(json.dumps(
                _build_run_object_export(packet_runtime, request, run_dir),
                indent=2,
            ))

        started_at = _utc_now()
        self.control_plane.patch_run(
            request.run_id,
            {
                "status": "running",
                "started_at": started_at,
                "agent_role": request.agent_role,
                "scenario_set_id": request.scenario_set_id,
            },
        )

        command = [*self.backend_command, "--request", str(private_request_path), "--output-dir", str(run_dir)]
        stdout_path = run_dir / "stdout.log"
        stderr_path = run_dir / "stderr.log"

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds(),
            )
            stdout_path.write_text(completed.stdout or "")
            stderr_path.write_text(completed.stderr or "")
            result = self._load_result(run_dir)
            if completed.returncode != 0 and result["status"] == "completed":
                result = self._fail_result(
                    run_dir,
                    f"backend exited with code {completed.returncode}",
                    transcript_path=result.get("transcript_path"),
                    artifact_bundle_path=result.get("artifact_bundle_path"),
                )
        except subprocess.TimeoutExpired as exc:
            stdout_path.write_text(_coerce_text(exc.stdout))
            stderr_path.write_text(_coerce_text(exc.stderr))
            result = self._fail_result(run_dir, f"backend timed out after {request.timeout_seconds()} seconds", status="timeout")

        result["started_at"] = started_at
        result["finished_at"] = _utc_now()

        packet_runtime = raw_request.get("packet_runtime") if isinstance(raw_request.get("packet_runtime"), dict) else None
        if packet_runtime:
            mutation_surface_audit = audit_packet_mutation_surface(
                packet_runtime,
                workspace_snapshot=raw_request.get("workspace_snapshot"),
            )
            mutation_surface_audit_path = write_mutation_surface_audit_receipt(run_dir, mutation_surface_audit)
            execution_honesty = result.get("execution_honesty") if isinstance(result.get("execution_honesty"), dict) else {}
            execution_honesty["mutation_surface_audit"] = mutation_surface_audit
            execution_honesty["mutation_surface_audit_path"] = mutation_surface_audit_path
            result["execution_honesty"] = execution_honesty
            _patch_artifact_bundle_mutation_surface_audit(
                run_dir / "artifact-bundle.json",
                mutation_surface_audit,
                mutation_surface_audit_path,
            )

        execution_backend = build_execution_backend_surface(raw_request, result)
        if execution_backend:
            result["execution_backend"] = execution_backend
            _patch_artifact_bundle_execution_backend(
                run_dir / "artifact-bundle.json",
                execution_backend,
            )

        result_path = run_dir / "result.json"
        result_path.write_text(json.dumps(result, indent=2))

        provenance = write_receipt_provenance(run_dir, raw_request, result)
        result["provenance"] = provenance
        result_path.write_text(json.dumps(result, indent=2))

        integrations = write_product_integrations(run_dir, raw_request, result)
        result["integrations"] = integrations
        result_path.write_text(json.dumps(result, indent=2))
        refresh_receipt_provenance_audit_bundle(run_dir, raw_request, result)

        final_payload = {
            "status": result["status"],
            "finished_at": result["finished_at"],
            "transcript_path": result["transcript_path"],
            "artifact_bundle_path": result["artifact_bundle_path"],
            "machine_score": result.get("machine_score", 0.0),
        }
        if "scorecard" in result:
            final_payload["scorecard"] = result["scorecard"]
        if "error" in result:
            final_payload["error"] = result["error"]

        self.control_plane.patch_run(request.run_id, final_payload)
        return result

    def _load_result(self, run_dir: Path) -> dict[str, Any]:
        result_path = run_dir / "result.json"
        if not result_path.exists():
            raise ContractError("backend did not write result.json")

        payload = json.loads(result_path.read_text())
        status = payload.get("status")
        if status not in ALLOWED_STATUSES:
            raise ContractError(f"invalid result status: {status!r}")

        transcript_path = self._resolve_existing_path(run_dir, payload.get("transcript_path"), "transcript_path")
        artifact_bundle_path = self._resolve_existing_path(
            run_dir, payload.get("artifact_bundle_path"), "artifact_bundle_path"
        )

        normalized = {
            "status": status,
            "transcript_path": str(transcript_path),
            "artifact_bundle_path": str(artifact_bundle_path),
            "machine_score": payload.get("machine_score", 0.0),
        }
        if "scorecard" in payload:
            normalized["scorecard"] = payload["scorecard"]
        if payload.get("error"):
            normalized["error"] = payload["error"]
        if "execution_honesty" in payload:
            normalized["execution_honesty"] = payload["execution_honesty"]
        return normalized

    def _resolve_existing_path(self, run_dir: Path, raw_path: Any, field_name: str) -> Path:
        if not raw_path:
            raise ContractError(f"backend result missing {field_name}")
        path = Path(raw_path)
        if not path.is_absolute():
            path = run_dir / path
        if not path.exists():
            raise ContractError(f"backend result points at missing file for {field_name}: {path}")
        return path

    def _fail_result(
        self,
        run_dir: Path,
        error: str,
        *,
        status: str = "failed",
        transcript_path: str | None = None,
        artifact_bundle_path: str | None = None,
    ) -> dict[str, Any]:
        if transcript_path is None:
            transcript_path = str(_ensure_failure_transcript(run_dir, error))
        if artifact_bundle_path is None:
            artifact_bundle_path = str(_ensure_failure_bundle(run_dir, error, transcript_path))
        return {
            "status": status,
            "transcript_path": str(Path(transcript_path)),
            "artifact_bundle_path": str(Path(artifact_bundle_path)),
            "machine_score": 0.0,
            "error": error,
        }


def _ensure_failure_transcript(run_dir: Path, error: str) -> Path:
    transcript_path = run_dir / "transcript.ndjson"
    if not transcript_path.exists():
        transcript_path.write_text(
            json.dumps(
                {
                    "event": "runner.failed",
                    "message": error,
                    "ts": _utc_now(),
                }
            )
            + "\n"
        )
    return transcript_path


def _ensure_failure_bundle(run_dir: Path, error: str, transcript_path: str | Path) -> Path:
    bundle_path = run_dir / "artifact-bundle.json"
    if not bundle_path.exists():
        bundle_path.write_text(
            json.dumps(
                {
                    "status": "failed",
                    "error": error,
                    "transcript_path": str(transcript_path),
                },
                indent=2,
            )
        )
    return bundle_path


def _patch_artifact_bundle_mutation_surface_audit(
    artifact_bundle_path: Path,
    mutation_surface_audit: dict[str, Any],
    mutation_surface_audit_path: str,
) -> None:
    if not artifact_bundle_path.exists():
        return
    artifact_bundle = json.loads(artifact_bundle_path.read_text())
    if not isinstance(artifact_bundle, dict):
        return
    receipts = artifact_bundle.get("receipts") if isinstance(artifact_bundle.get("receipts"), dict) else {}
    receipts["mutation_surface_audit_path"] = mutation_surface_audit_path
    artifact_bundle["receipts"] = receipts
    artifact_bundle["mutation_surface_audit"] = mutation_surface_audit
    artifact_bundle_path.write_text(json.dumps(artifact_bundle, indent=2))


def _patch_artifact_bundle_execution_backend(
    artifact_bundle_path: Path,
    execution_backend: dict[str, Any],
) -> None:
    if not artifact_bundle_path.exists():
        return
    artifact_bundle = json.loads(artifact_bundle_path.read_text())
    if not isinstance(artifact_bundle, dict):
        return

    backend_id = execution_backend.get("backend_id")
    if backend_id:
        artifact_bundle["execution_backend"] = backend_id

    backend_contract = execution_backend.get("execution_backend_contract")
    if isinstance(backend_contract, dict) and backend_contract:
        artifact_bundle["execution_backend_contract"] = backend_contract

    execution_honesty = execution_backend.get("execution_honesty")
    if isinstance(execution_honesty, dict) and execution_honesty:
        artifact_bundle["execution_honesty"] = execution_honesty

    artifact_bundle_path.write_text(json.dumps(artifact_bundle, indent=2))


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def _build_run_object_export(
    packet_runtime: dict[str, Any],
    request: RunRequest,
    run_dir: Path,
) -> dict[str, Any]:
    """Build the run-object.json export from a packet_runtime block.

    This is the concrete runtime artifact that proves the bridge consumed
    the versioned curriculum contract surface for this run.  It carries
    every field a reviewer or downstream tool needs to verify the run
    was set up correctly without re-reading the registry or contract files.
    """
    export = {
        "run_object_version": packet_runtime.get("run_object_version", "1.0.0"),
        "run_id": request.run_id,
        "packet_id": packet_runtime.get("packet_id", ""),
        "packet_version": packet_runtime.get("packet_version", "1.0.0"),
        "packet_content_hash": packet_runtime.get("packet_content_hash", ""),
        "acceptance_test_id": packet_runtime.get("acceptance_test_id", ""),
        "role_id": packet_runtime.get("role_id", ""),
        "phase_index": packet_runtime.get("phase_index", 0),
        "eval_contract_ref": packet_runtime.get("eval_contract_ref", {}),
        "mutation_budget": packet_runtime.get("mutation_budget", {}),
        "allowed_paths": packet_runtime.get("allowed_paths", []),
        "blocked_paths": packet_runtime.get("blocked_paths", []),
        "expected_checks": packet_runtime.get("expected_checks", []),
        "evidence_contract": packet_runtime.get("evidence_contract", {}),
        "execution_status": packet_runtime.get("execution_status", "not_started"),
        "execution_backend": packet_runtime.get("execution_backend", "pending"),
        "receipt_output_dir": str(run_dir / "receipts"),
        "artifact_locations": {
            "request_public": str(run_dir / "request.json"),
            "request_private": str(run_dir / "request.private.json"),
            "run_object": str(run_dir / "run-object.json"),
            "receipts_dir": str(run_dir / "receipts"),
        },
    }
    execution_backend_contract = packet_runtime.get("execution_backend_contract")
    if isinstance(execution_backend_contract, dict) and execution_backend_contract:
        export["execution_backend_contract"] = execution_backend_contract
    return export

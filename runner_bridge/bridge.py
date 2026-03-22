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

ALLOWED_STATUSES = {"completed", "failed", "timeout"}


class ClawithRunClient:
    def __init__(self, base_url: str | None = None, secret: str = ""):
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.secret = secret

    def patch_run(self, run_id: str, payload: dict[str, Any]) -> None:
        if not self.base_url:
            return
        self.request_json("PATCH", f"/api/runs/{run_id}", payload, error_prefix="failed to patch run state")

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("POST", "/api/runs", payload, error_prefix="failed to create run")

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self.request_json("GET", f"/api/runs/{run_id}", error_prefix="failed to fetch run state")

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("POST", path, payload, error_prefix=f"failed to POST {path}")

    def request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        error_prefix: str,
    ) -> dict[str, Any]:
        if not self.base_url:
            raise ContractError("control plane base URL is not configured")

        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["Authorization"] = f"Bearer {self.secret}"

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status >= 400:
                    raise ContractError(f"{error_prefix}: HTTP {response.status}")
                body = response.read().decode() or "{}"
        except urllib.error.URLError as exc:
            raise ContractError(f"{error_prefix}: {exc}") from exc

        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise ContractError(f"{error_prefix}: invalid JSON response: {exc}") from exc


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
        result_path = run_dir / "result.json"
        result_path.write_text(json.dumps(result, indent=2))

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


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)

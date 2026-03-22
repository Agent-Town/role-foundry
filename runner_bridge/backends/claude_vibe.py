from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from string import Template
from typing import Any, Callable

from runner_bridge.eval_loop import build_teacher_evaluation, has_teacher_evaluation

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_TEMPLATE_PATH = REPO_ROOT / ".claude" / "templates" / "role-foundry-student-run.md"
DEFAULT_AGENT = "role-foundry-student"
DEFAULT_SETTINGS_SOURCES = "project"
DEFAULT_PERMISSION_MODE = "bypassPermissions"
DEFAULT_TOOLS = ["Read", "Edit", "Write", "Bash", "Grep", "Glob"]
CLAUDE_RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "edits_made": {"type": "boolean"},
        "changed_files": {"type": "array", "items": {"type": "string"}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "edits_made", "changed_files", "next_steps", "notes"],
}


@dataclass
class ClaudeVibeConfig:
    agent: str = DEFAULT_AGENT
    settings_sources: str = DEFAULT_SETTINGS_SOURCES
    permission_mode: str = DEFAULT_PERMISSION_MODE
    tools: list[str] = field(default_factory=lambda: list(DEFAULT_TOOLS))
    model: str | None = None

    @classmethod
    def from_request(cls, payload: dict[str, Any]) -> "ClaudeVibeConfig":
        raw = payload.get("claude_vibe")
        if not isinstance(raw, dict):
            return cls()

        tools = raw.get("tools")
        if isinstance(tools, list) and tools:
            normalized_tools = [str(tool) for tool in tools]
        else:
            normalized_tools = list(DEFAULT_TOOLS)

        model = raw.get("model")
        return cls(
            agent=str(raw.get("agent") or DEFAULT_AGENT),
            settings_sources=str(raw.get("settings_sources") or DEFAULT_SETTINGS_SOURCES),
            permission_mode=str(raw.get("permission_mode") or DEFAULT_PERMISSION_MODE),
            tools=normalized_tools,
            model=str(model) if model else None,
        )


class ClaudeVibeRunner:
    def __init__(
        self,
        *,
        repo_root: Path = REPO_ROOT,
        command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
    ):
        self.repo_root = repo_root
        self.command_runner = command_runner
        self.which = which

    def run(self, request: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        transcript_path = output_dir / "transcript.ndjson"
        artifact_bundle_path = output_dir / "artifact-bundle.json"
        result_path = output_dir / "result.json"
        prompt_path = output_dir / "claude-prompt.txt"
        invocation_path = output_dir / "claude-invocation.json"
        response_path = output_dir / "claude-response.json"
        stderr_path = output_dir / "claude.stderr.log"

        events: list[dict[str, Any]] = []
        config = ClaudeVibeConfig.from_request(request)
        prompt_template_exists = PROMPT_TEMPLATE_PATH.exists()
        project_agent_exists = (self.repo_root / ".claude" / "agents" / f"{config.agent}.md").exists()
        student_context = _student_context(request)

        _append_event(
            events,
            "runner.started",
            f"Starting ClaudeVibeRunner for {request.get('run_id', 'unknown-run')} with agent {config.agent}.",
        )

        if request.get("agent_role") != "student":
            result = self._fail_result(
                request,
                output_dir,
                transcript_path,
                artifact_bundle_path,
                error="ClaudeVibeRunner only supports agent_role=student. Teacher/evaluator runs should stay on a separate backend.",
                checks=_base_checks(False, False, prompt_template_exists, project_agent_exists),
                student_context=student_context,
                config=config,
            )
            result_path.write_text(json.dumps(result, indent=2))
            transcript_path.write_text(_serialize_events(events))
            return result

        if not self.which("claude"):
            result = self._fail_result(
                request,
                output_dir,
                transcript_path,
                artifact_bundle_path,
                error="Claude CLI not found on PATH. Install Claude Code before using ClaudeVibeRunner.",
                checks=_base_checks(False, False, prompt_template_exists, project_agent_exists),
                student_context=student_context,
                config=config,
            )
            result_path.write_text(json.dumps(result, indent=2))
            transcript_path.write_text(_serialize_events(events))
            return result

        if not prompt_template_exists:
            result = self._fail_result(
                request,
                output_dir,
                transcript_path,
                artifact_bundle_path,
                error=f"Missing project-local Claude prompt template: {PROMPT_TEMPLATE_PATH}",
                checks=_base_checks(True, False, False, project_agent_exists),
                student_context=student_context,
                config=config,
            )
            result_path.write_text(json.dumps(result, indent=2))
            transcript_path.write_text(_serialize_events(events))
            return result

        if not project_agent_exists:
            result = self._fail_result(
                request,
                output_dir,
                transcript_path,
                artifact_bundle_path,
                error=f"Missing project-local Claude agent profile: .claude/agents/{config.agent}.md",
                checks=_base_checks(True, False, prompt_template_exists, False),
                student_context=student_context,
                config=config,
            )
            result_path.write_text(json.dumps(result, indent=2))
            transcript_path.write_text(_serialize_events(events))
            return result

        auth_status = self._check_auth()
        _append_event(
            events,
            "claude.auth.checked",
            "Claude auth state inspected before starting the student run.",
        )
        if not auth_status.get("ok"):
            result = self._fail_result(
                request,
                output_dir,
                transcript_path,
                artifact_bundle_path,
                error=str(auth_status.get("error")),
                checks=_base_checks(True, False, prompt_template_exists, project_agent_exists),
                student_context=student_context,
                config=config,
                auth_status=auth_status,
            )
            result_path.write_text(json.dumps(result, indent=2))
            transcript_path.write_text(_serialize_events(events))
            return result

        auth_receipt = auth_status.get("receipt", {})
        prompt = self._render_prompt(request, student_context)
        prompt_path.write_text(prompt)
        _append_event(
            events,
            "student.prompt.loaded",
            f"Student-visible prompt prepared with {student_context.get('sealed_holdout_count', 0)} sealed holdouts kept out of the Claude prompt.",
        )

        command = self.build_command(request, config)
        invocation_receipt = {
            "backend": "ClaudeVibeRunner",
            "cwd": str(self.repo_root),
            "command": command,
            "agent": config.agent,
            "model": config.model,
            "settings_sources": config.settings_sources,
            "permission_mode": config.permission_mode,
            "tools": config.tools,
        }
        invocation_path.write_text(json.dumps(invocation_receipt, indent=2))
        _append_event(
            events,
            "claude.invocation.started",
            f"Running claude --print with project-local settings via agent {config.agent}.",
        )

        try:
            completed = self.command_runner(
                command,
                cwd=self.repo_root,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=_timeout_seconds(request),
            )
        except subprocess.TimeoutExpired as exc:
            stderr_path.write_text(_coerce_text(exc.stderr))
            result = self._fail_result(
                request,
                output_dir,
                transcript_path,
                artifact_bundle_path,
                error=f"Claude invocation timed out after {_timeout_seconds(request)} seconds.",
                checks=_base_checks(True, True, prompt_template_exists, project_agent_exists),
                student_context=student_context,
                config=config,
                auth_status=auth_receipt,
                extra_artifacts={"claude_stdout": _coerce_text(exc.stdout), "claude_stderr": _coerce_text(exc.stderr)},
            )
            result_path.write_text(json.dumps(result, indent=2))
            transcript_path.write_text(_serialize_events(events + [_event("runner.failed", result["error"])]))
            return result

        stderr_path.write_text(completed.stderr or "")
        parsed_response, response_error = _parse_claude_response(completed)
        response_path.write_text(json.dumps(parsed_response, indent=2))

        if completed.returncode != 0:
            error = parsed_response.get("error") or f"Claude exited with code {completed.returncode}."
            result = self._fail_result(
                request,
                output_dir,
                transcript_path,
                artifact_bundle_path,
                error=error,
                checks=_base_checks(True, True, prompt_template_exists, project_agent_exists),
                student_context=student_context,
                config=config,
                auth_status=auth_receipt,
                extra_artifacts={"claude_response_path": response_path.name},
            )
            result_path.write_text(json.dumps(result, indent=2))
            transcript_path.write_text(_serialize_events(events + [_event("runner.failed", error)]))
            return result

        if response_error:
            result = self._fail_result(
                request,
                output_dir,
                transcript_path,
                artifact_bundle_path,
                error=response_error,
                checks=_base_checks(True, True, prompt_template_exists, project_agent_exists),
                student_context=student_context,
                config=config,
                auth_status=auth_receipt,
                extra_artifacts={"claude_response_path": response_path.name},
            )
            result_path.write_text(json.dumps(result, indent=2))
            transcript_path.write_text(_serialize_events(events + [_event("runner.failed", response_error)]))
            return result

        report = parsed_response["structured_result"]
        changed_files_exist = all((self.repo_root / path).exists() for path in report.get("changed_files", []))
        checks = _base_checks(True, True, prompt_template_exists, project_agent_exists) + [
            {"name": "structured_output_received", "passed": True},
            {"name": "reported_changed_files_exist", "passed": changed_files_exist},
        ]
        _append_event(
            events,
            "claude.invocation.completed",
            f"Claude returned a structured report in {parsed_response.get('duration_ms', 0)} ms.",
        )
        _append_event(
            events,
            "runner.completed",
            "ClaudeVibeRunner produced transcript and artifact receipts from a real Claude CLI execution.",
        )

        artifact_bundle = {
            "run_id": request.get("run_id"),
            "agent_role": request.get("agent_role"),
            "scenario_set_id": request.get("scenario_set_id"),
            "status": "completed",
            "workspace_snapshot": request.get("workspace_snapshot", {}),
            "student_view": student_context,
            "backend": {
                "name": "ClaudeVibeRunner",
                "agent": config.agent,
                "model": config.model,
                "settings_sources": config.settings_sources,
                "permission_mode": config.permission_mode,
                "tools": config.tools,
                "auth": auth_receipt,
            },
            "claude_run": {
                "session_id": parsed_response.get("session_id"),
                "stop_reason": parsed_response.get("stop_reason"),
                "duration_ms": parsed_response.get("duration_ms"),
                "total_cost_usd": parsed_response.get("total_cost_usd"),
                "usage": parsed_response.get("usage", {}),
                "model_usage": parsed_response.get("modelUsage", {}),
                "report": report,
            },
            "receipts": {
                "prompt_path": prompt_path.name,
                "invocation_path": invocation_path.name,
                "response_path": response_path.name,
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
                "runner": "ClaudeVibeRunner",
                "summary": report.get("summary", ""),
                "checks": checks,
                "changed_files": report.get("changed_files", []),
                "next_steps": report.get("next_steps", []),
                "notes": report.get("notes", []),
                "edits_made": bool(report.get("edits_made")),
            },
        }
        result_path.write_text(json.dumps(result, indent=2))
        transcript_path.write_text(_serialize_events(events))
        return result

    def build_command(self, request: dict[str, Any], config: ClaudeVibeConfig) -> list[str]:
        command = [
            "claude",
            "--print",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(CLAUDE_RESULT_SCHEMA),
            "--permission-mode",
            config.permission_mode,
            "--setting-sources",
            config.settings_sources,
            "--agent",
            config.agent,
            "--tools",
            ",".join(config.tools),
            "--max-budget-usd",
            str(_cost_budget_usd(request)),
            "--no-session-persistence",
        ]
        if config.model:
            command.extend(["--model", config.model])
        return command

    def _check_auth(self) -> dict[str, Any]:
        try:
            completed = self.command_runner(
                ["claude", "auth", "status"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except FileNotFoundError:
            return {"ok": False, "error": "Claude CLI not found on PATH."}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Timed out while checking Claude auth status."}

        if completed.returncode != 0:
            return {
                "ok": False,
                "error": f"Unable to verify Claude auth status (exit {completed.returncode}).",
                "stderr": completed.stderr,
            }

        try:
            payload = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"Claude auth status returned invalid JSON: {exc}"}

        if not payload.get("loggedIn"):
            return {
                "ok": False,
                "error": "Claude CLI is installed but not authenticated. Run `claude auth login` before using ClaudeVibeRunner.",
                "receipt": {"logged_in": False},
            }

        return {
            "ok": True,
            "receipt": {
                "logged_in": True,
                "auth_method": payload.get("authMethod"),
                "api_provider": payload.get("apiProvider"),
                "subscription_type": payload.get("subscriptionType"),
            },
        }

    def _render_prompt(self, request: dict[str, Any], student_context: dict[str, Any]) -> str:
        workspace_snapshot = request.get("workspace_snapshot", {})
        template = Template(PROMPT_TEMPLATE_PATH.read_text())
        changed_files = workspace_snapshot.get("changed_files", [])
        notes = workspace_snapshot.get("notes", [])
        return template.safe_substitute(
            run_id=request.get("run_id", ""),
            scenario_set_id=request.get("scenario_set_id", ""),
            objective=workspace_snapshot.get("objective", "No explicit objective provided."),
            changed_files_json=json.dumps(changed_files, indent=2),
            notes_json=json.dumps(notes, indent=2),
            workspace_snapshot_json=json.dumps(workspace_snapshot, indent=2),
            student_context_json=json.dumps(student_context, indent=2),
        )

    def _fail_result(
        self,
        request: dict[str, Any],
        output_dir: Path,
        transcript_path: Path,
        artifact_bundle_path: Path,
        *,
        error: str,
        checks: list[dict[str, Any]],
        student_context: dict[str, Any],
        config: ClaudeVibeConfig,
        auth_status: dict[str, Any] | None = None,
        extra_artifacts: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        artifact_bundle = {
            "run_id": request.get("run_id"),
            "agent_role": request.get("agent_role"),
            "scenario_set_id": request.get("scenario_set_id"),
            "status": "failed",
            "workspace_snapshot": request.get("workspace_snapshot", {}),
            "student_view": student_context,
            "backend": {
                "name": "ClaudeVibeRunner",
                "agent": config.agent,
                "model": config.model,
                "settings_sources": config.settings_sources,
                "permission_mode": config.permission_mode,
                "tools": config.tools,
                "auth": auth_status or {},
            },
            "error": error,
            "receipts": {
                "transcript_path": transcript_path.name,
                "result_path": "result.json",
            },
        }
        if extra_artifacts:
            artifact_bundle["extra_artifacts"] = extra_artifacts
        artifact_bundle_path.write_text(json.dumps(artifact_bundle, indent=2))
        return {
            "status": "failed",
            "transcript_path": transcript_path.name,
            "artifact_bundle_path": artifact_bundle_path.name,
            "machine_score": 0.0,
            "error": error,
            "scorecard": {
                "runner": "ClaudeVibeRunner",
                "checks": checks,
            },
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claude-backed student runner for Role Foundry")
    parser.add_argument("--request", required=True, help="Path to the run request JSON")
    parser.add_argument("--output-dir", required=True, help="Where to write transcript + artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    request = json.loads(Path(args.request).read_text())
    runner = ClaudeVibeRunner()
    result = runner.run(request, args.output_dir)
    return 0 if result["status"] == "completed" else 1


def _parse_claude_response(completed: subprocess.CompletedProcess[str]) -> tuple[dict[str, Any], str | None]:
    raw_stdout = completed.stdout or ""
    if not raw_stdout.strip():
        return {
            "returncode": completed.returncode,
            "stderr": completed.stderr or "",
        }, "Claude returned empty stdout; no result payload was available."

    try:
        payload = json.loads(raw_stdout)
    except json.JSONDecodeError as exc:
        return {
            "returncode": completed.returncode,
            "stdout": raw_stdout,
            "stderr": completed.stderr or "",
        }, f"Claude returned invalid JSON: {exc}"

    if payload.get("is_error"):
        message = payload.get("result") or payload.get("error") or "Claude reported an unknown error."
        payload["error"] = message
        return payload, str(message)

    structured = payload.get("structured_output")
    if isinstance(structured, dict):
        payload["structured_result"] = structured
        return payload, None

    structured_raw = payload.get("result")
    if not isinstance(structured_raw, str):
        return payload, "Claude result payload did not include a structured report."

    try:
        structured = json.loads(structured_raw)
    except json.JSONDecodeError as exc:
        return payload, f"Claude structured result was not valid JSON: {exc}"

    payload["structured_result"] = structured
    return payload, None


def _student_context(request: dict[str, Any]) -> dict[str, Any]:
    workspace_snapshot = request.get("workspace_snapshot", {})
    if has_teacher_evaluation(request):
        evaluation = build_teacher_evaluation(request)
        student_view = evaluation["student_view"]
        return {
            "agent_role": student_view.get("agent_role", "student"),
            "actor": student_view.get("actor", {}),
            "objective": workspace_snapshot.get("objective", ""),
            "sealed_holdout_count": student_view.get("sealed_holdout_count", 0),
            "visible_scenarios": student_view.get("visible_scenarios", []),
            "public_curriculum_themes": student_view.get("public_curriculum_themes", []),
            "prompt_summary": student_view.get("prompt_summary", ""),
        }

    return {
        "agent_role": "student",
        "objective": workspace_snapshot.get("objective", ""),
        "sealed_holdout_count": 0,
        "visible_scenarios": [],
        "public_curriculum_themes": [],
        "prompt_summary": "No teacher evaluation bundle was attached to this run.",
    }


def _base_checks(
    claude_cli_available: bool,
    claude_authenticated: bool,
    prompt_template_present: bool,
    project_agent_present: bool,
) -> list[dict[str, Any]]:
    return [
        {"name": "claude_cli_available", "passed": claude_cli_available},
        {"name": "claude_authenticated", "passed": claude_authenticated},
        {"name": "prompt_template_present", "passed": prompt_template_present},
        {"name": "project_agent_present", "passed": project_agent_present},
    ]


def _cost_budget_usd(request: dict[str, Any], default: float = 1.0) -> float:
    budget = request.get("cost_budget")
    if isinstance(budget, (int, float)):
        return max(0.01, float(budget))
    if isinstance(budget, dict) and "usd" in budget:
        try:
            return max(0.01, float(budget["usd"]))
        except (TypeError, ValueError):
            return default
    return default


def _timeout_seconds(request: dict[str, Any], default: int = 60) -> int:
    budget = request.get("time_budget")
    if isinstance(budget, (int, float)):
        return max(1, int(budget))
    if isinstance(budget, dict):
        if "seconds" in budget:
            try:
                return max(1, int(budget["seconds"]))
            except (TypeError, ValueError):
                return default
        if "minutes" in budget:
            try:
                return max(1, int(float(budget["minutes"]) * 60))
            except (TypeError, ValueError):
                return default
    return default


def _event(event: str, message: str) -> dict[str, Any]:
    return {"ts": _utc_now(), "event": event, "message": message}


def _append_event(events: list[dict[str, Any]], event: str, message: str) -> None:
    events.append(_event(event, message))


def _serialize_events(events: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(event) + "\n" for event in events)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())

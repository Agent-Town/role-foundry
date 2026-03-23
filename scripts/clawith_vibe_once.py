#!/usr/bin/env python3
"""One-shot Clawith gateway worker backed by Claude Code + vibecosystem.

Honest scope:
- Clawith remains the control plane
- this script is only the external executor lane
- it uses Claude Code as the runtime and can select a vibecosystem agent via --claude-agent
- it does NOT create native Clawith model-pool entries or pretend Claude app subscriptions are Clawith API keys

Typical usage:
  python3 scripts/clawith_vibe_once.py \
    --base-url http://localhost:3008 \
    --api-key oc-... \
    --claude-agent backend-dev \
    --workdir /Users/robin/.openclaw/workspace/role-foundry
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def timestamp() -> str:
    return now_utc().strftime("%Y%m%dT%H%M%SZ")


def build_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def http_json(method: str, url: str, *, headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None
    req_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {raw}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def format_history(history: list[dict[str, Any]]) -> str:
    if not history:
        return "(no prior conversation history provided by Clawith)"
    lines = []
    for item in history:
        created_at = item.get("created_at", "")
        role = item.get("role", "unknown")
        sender = item.get("sender_name") or "unknown"
        content = (item.get("content") or "").strip()
        lines.append(f"- [{created_at}] [{role}] [{sender}] {content}")
    return "\n".join(lines)


def format_relationships(relationships: list[dict[str, Any]]) -> str:
    if not relationships:
        return "(no relationship metadata provided)"
    lines = []
    for rel in relationships:
        name = rel.get("name", "unknown")
        rel_type = rel.get("type", "unknown")
        role = rel.get("role") or "unspecified"
        description = rel.get("description") or ""
        channels = ", ".join(rel.get("channels") or []) or "none"
        lines.append(f"- {name} [{rel_type}] role={role} channels={channels} desc={description}")
    return "\n".join(lines)


def build_prompt(message: dict[str, Any], relationships: list[dict[str, Any]]) -> str:
    sender = message.get("sender_user_name") or message.get("sender_agent_name") or "unknown"
    conversation_id = message.get("conversation_id") or "(missing)"
    history = format_history(message.get("history") or [])
    relationship_text = format_relationships(relationships)
    latest = (message.get("content") or "").strip()

    return textwrap.dedent(
        f"""\
        You are the Claude Code + vibecosystem execution backend for a Clawith-controlled agent.

        Hard rules:
        - Clawith is the control plane.
        - You are only producing the reply body that should be sent back into the Clawith conversation.
        - Do not mention API keys, gateway polling, or internal plumbing unless the user explicitly asks.
        - Use the provided history for context before answering.
        - If the right next move is to ask a clarifying question, do that.
        - Be concrete and useful.

        Conversation metadata:
        - conversation_id: {conversation_id}
        - sender: {sender}
        - gateway_message_id: {message.get('id')}

        Known relationships from Clawith:
        {relationship_text}

        Recent history (oldest first):
        {history}

        Latest inbound message:
        {latest}

        Return only the reply that should be sent back to Clawith.
        """
    ).strip() + "\n"


def build_latest_only_prompt(message: dict[str, Any]) -> str:
    return (message.get("content") or "").strip()


def run_claude(*, prompt: str, workdir: Path, claude_agent: str, model: str | None, permission_mode: str, setting_sources: str, claude_home: str | None) -> subprocess.CompletedProcess[str]:
    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError("Claude Code CLI not found in PATH")

    cmd = [
        claude,
        "--print",
        "--no-session-persistence",
        "--output-format",
        "text",
        "--agent",
        claude_agent,
        "--permission-mode",
        permission_mode,
        "--setting-sources",
        setting_sources,
        "--add-dir",
        str(workdir.resolve()),
    ]
    if model:
        cmd[1:1] = ["--model", model]

    env = dict(os.environ)
    if claude_home:
        env["HOME"] = claude_home

    # Claude Code 2.1.79 was observed to behave inconsistently when the prompt was
    # passed as a positional argv value in --print mode: a contextual prompt could
    # return exit 0 with empty stdout, and a simple fallback prompt could claim no
    # prompt was provided. Supplying the prompt on stdin avoids that CLI edge and
    # produced the real reply in the same environment.
    return subprocess.run(
        cmd,
        cwd=str(workdir),
        env=env,
        input=prompt,
        capture_output=True,
        text=True,
        check=False,
    )


def report_result(base_url: str, api_key: str, message_id: str, result_text: str) -> dict[str, Any]:
    return http_json(
        "POST",
        build_url(base_url, "/api/gateway/report"),
        headers={"X-Api-Key": api_key},
        payload={"message_id": message_id, "result": result_text},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Process one Clawith poll cycle through Claude Code/vibecosystem")
    parser.add_argument("--base-url", default="http://localhost:3008", help="Clawith base URL (default: http://localhost:3008)")
    parser.add_argument("--api-key", required=True, help="Clawith OpenClaw-style gateway API key")
    parser.add_argument("--claude-agent", default="backend-dev", help="Claude/vibecosystem agent name (default: backend-dev)")
    parser.add_argument("--model", default="", help="Optional Claude model override, e.g. sonnet or opus")
    parser.add_argument("--permission-mode", default="default", help="Claude permission mode (default: default)")
    parser.add_argument("--setting-sources", default="user,project,local", help="Claude setting sources (default: user,project,local)")
    parser.add_argument("--workdir", default=".", help="Working directory Claude should operate in")
    parser.add_argument("--claude-home", default="", help="Optional alternate HOME for Claude Code")
    parser.add_argument("--artifacts-dir", default="artifacts/clawith-gateway", help="Artifact root for prompts/results (default: artifacts/clawith-gateway)")
    parser.add_argument("--prompt-mode", choices=["contextual", "latest-only"], default="contextual", help="Claude prompt shape (default: contextual)")
    args = parser.parse_args()

    workdir = Path(args.workdir).expanduser().resolve()
    if not workdir.exists():
        print(f"workdir does not exist: {workdir}", file=sys.stderr)
        return 2

    try:
        poll = http_json(
            "GET",
            build_url(args.base_url, "/api/gateway/poll"),
            headers={"X-Api-Key": args.api_key},
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    messages = poll.get("messages") or []
    relationships = poll.get("relationships") or []

    run_root = workdir / args.artifacts_dir / timestamp()
    write_json(run_root / "poll.json", poll)

    if not messages:
        print(f"No pending Clawith messages. Poll receipt saved to {run_root}")
        return 0

    failures = 0
    for idx, message in enumerate(messages, start=1):
        message_id = str(message.get("id"))
        msg_dir = run_root / f"{idx:02d}_{message_id}"
        write_json(msg_dir / "message.json", message)
        if args.prompt_mode == "latest-only":
            prompt = build_latest_only_prompt(message)
        else:
            prompt = build_prompt(message, relationships)
        write_text(msg_dir / "prompt.txt", prompt)

        proc = run_claude(
            prompt=prompt,
            workdir=workdir,
            claude_agent=args.claude_agent,
            model=args.model or None,
            permission_mode=args.permission_mode,
            setting_sources=args.setting_sources,
            claude_home=args.claude_home or None,
        )
        write_text(msg_dir / "claude.stdout.txt", proc.stdout)
        write_text(msg_dir / "claude.stderr.txt", proc.stderr)

        execution_meta: dict[str, Any] = {
            "prompt_mode": args.prompt_mode,
            "claude_input_transport": "stdin",
            "chosen_strategy": None,
            "primary": {
                "returncode": proc.returncode,
                "stdout_bytes": len(proc.stdout.encode("utf-8")),
                "stderr_bytes": len(proc.stderr.encode("utf-8")),
            },
        }

        if proc.returncode == 0 and proc.stdout.strip():
            result_text = proc.stdout.strip()
            execution_meta["chosen_strategy"] = f"{args.prompt_mode}_prompt"
        elif args.prompt_mode == "latest-only":
            failures += 1
            execution_meta["chosen_strategy"] = "executor_error"
            result_text = (
                "[clawith-vibe-once executor error] Claude Code failed to produce a reply. "
                f"primary_exit={proc.returncode}. See local artifacts at {msg_dir}."
            )
        else:
            fallback_prompt = build_latest_only_prompt(message)
            write_text(msg_dir / "prompt.latest_only.txt", fallback_prompt)
            fallback_proc = run_claude(
                prompt=fallback_prompt,
                workdir=workdir,
                claude_agent=args.claude_agent,
                model=args.model or None,
                permission_mode=args.permission_mode,
                setting_sources=args.setting_sources,
                claude_home=args.claude_home or None,
            )
            write_text(msg_dir / "claude.latest_only.stdout.txt", fallback_proc.stdout)
            write_text(msg_dir / "claude.latest_only.stderr.txt", fallback_proc.stderr)
            execution_meta["latest_only_fallback"] = {
                "returncode": fallback_proc.returncode,
                "stdout_bytes": len(fallback_proc.stdout.encode("utf-8")),
                "stderr_bytes": len(fallback_proc.stderr.encode("utf-8")),
            }

            if fallback_proc.returncode == 0 and fallback_proc.stdout.strip():
                result_text = fallback_proc.stdout.strip()
                execution_meta["chosen_strategy"] = "latest_only_fallback"
            else:
                failures += 1
                execution_meta["chosen_strategy"] = "executor_error"
                result_text = (
                    "[clawith-vibe-once executor error] Claude Code failed to produce a reply. "
                    f"primary_exit={proc.returncode}; fallback_exit={fallback_proc.returncode}. "
                    f"See local artifacts at {msg_dir}."
                )

        write_json(msg_dir / "execution.json", execution_meta)

        try:
            report = report_result(args.base_url, args.api_key, message_id, result_text)
            write_json(msg_dir / "report.json", report)
        except Exception as exc:
            failures += 1
            write_text(msg_dir / "report.error.txt", str(exc) + "\n")
            print(f"failed to report message {message_id}: {exc}", file=sys.stderr)
            continue

        print(f"processed message {message_id} -> {msg_dir}")

    if failures:
        print(f"Completed with {failures} failure(s). Artifacts: {run_root}", file=sys.stderr)
        return 1

    print(f"Completed successfully. Artifacts: {run_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

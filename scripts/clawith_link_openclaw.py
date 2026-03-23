#!/usr/bin/env python3
"""Idempotently create (or find) a real local Clawith "Link OpenClaw" agent.

Real API endpoints used:
  POST /api/auth/login          — get auth token (unless --token / CLAWITH_TOKEN is used)
  GET  /api/agents/             — list existing agents
  POST /api/agents/             — create openclaw agent (returns api_key once)
  POST /api/agents/{id}/api-key — regenerate api_key for existing openclaw agent
  POST /api/gateway/heartbeat   — validate a saved gateway key without disturbing inbox delivery

Output: writes the gateway key to runtime/clawith_openclaw_key.json under the repo root.

Usage:
  python3 scripts/clawith_link_openclaw.py
  CLAWITH_PASSWORD=... python3 scripts/clawith_link_openclaw.py --agent-name MyBot
  CLAWITH_TOKEN=... python3 scripts/clawith_link_openclaw.py
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "runtime" / "clawith_openclaw_key.json"
DEFAULT_ROLE_DESCRIPTION = "vibecosystem adapter (Link OpenClaw)"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def resolve_output(path_str: str) -> Path:
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
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
        raise RuntimeError(f"{method} {url} -> HTTP {exc.code}: {raw}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def login(base: str, username: str, password: str) -> str:
    data = http_json(
        "POST",
        f"{base}/api/auth/login",
        payload={"username": username, "password": password},
    )
    token = data.get("access_token") or data.get("token")
    if not token:
        raise RuntimeError(f"Login succeeded but no token in response: {data}")
    return token


def list_agents(base: str, token: str) -> list[dict[str, Any]]:
    data = http_json(
        "GET",
        f"{base}/api/agents/",
        headers={"Authorization": f"Bearer {token}"},
    )
    if not isinstance(data, list):
        raise RuntimeError(f"Expected agent list from GET /api/agents/, got: {data}")
    return data


def create_openclaw_agent(base: str, token: str, name: str, role_description: str) -> dict[str, Any]:
    data = http_json(
        "POST",
        f"{base}/api/agents/",
        headers={"Authorization": f"Bearer {token}"},
        payload={
            "name": name,
            "agent_type": "openclaw",
            "role_description": role_description,
        },
    )
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected agent object from POST /api/agents/, got: {data}")
    return data


def regenerate_key(base: str, token: str, agent_id: str) -> dict[str, Any]:
    data = http_json(
        "POST",
        f"{base}/api/agents/{agent_id}/api-key",
        headers={"Authorization": f"Bearer {token}"},
    )
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object from POST /api/agents/{{id}}/api-key, got: {data}")
    return data


def validate_gateway_key(base: str, api_key: str) -> bool:
    try:
        data = http_json(
            "POST",
            f"{base}/api/gateway/heartbeat",
            headers={"X-Api-Key": api_key},
        )
    except RuntimeError as exc:
        if "HTTP 401" in str(exc):
            return False
        raise
    return isinstance(data, dict) and data.get("status") == "ok"


def load_saved_key(out_path: Path, expected_agent_id: str) -> str | None:
    if not out_path.exists():
        return None
    try:
        saved = json.loads(out_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    api_key = saved.get("api_key", "")
    if saved.get("agent_id") != expected_agent_id or not api_key.startswith("oc-"):
        return None
    return api_key


def save_key(
    out_path: Path,
    *,
    base_url: str,
    agent_id: str,
    agent_name: str,
    role_description: str,
    api_key: str,
    source: str,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": now_utc_iso(),
        "source": source,
        "base_url": base_url,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "role_description": role_description,
        "api_key": api_key,
        "_note": "This key authenticates the external executor against the Clawith gateway.",
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def get_bearer_token(base: str, username: str, password: str, token: str) -> tuple[str, str]:
    if token:
        return token, "token"

    if not password:
        if sys.stdin.isatty():
            password = getpass.getpass(f"Clawith password for {username}@{base}: ")
        else:
            raise RuntimeError(
                "No bearer token or password available. Use --token / CLAWITH_TOKEN or --password / CLAWITH_PASSWORD."
            )

    return login(base, username, password), "login"


def main() -> int:
    p = argparse.ArgumentParser(
        description="Idempotently link a real local Clawith OpenClaw agent and save its gateway key.",
    )
    p.add_argument("--base-url", default=os.environ.get("CLAWITH_BASE_URL", "http://localhost:3008"), help="Clawith URL (default: %(default)s)")
    p.add_argument("--username", default=os.environ.get("CLAWITH_USERNAME", "robin"), help="Clawith username (default: %(default)s)")
    p.add_argument("--password", default=os.environ.get("CLAWITH_PASSWORD", ""), help="Clawith password or set CLAWITH_PASSWORD")
    p.add_argument("--token", default=os.environ.get("CLAWITH_TOKEN", ""), help="Existing bearer token or set CLAWITH_TOKEN")
    p.add_argument("--agent-name", default="vibecosystem-adapter", help="Agent display name in Clawith (default: %(default)s)")
    p.add_argument("--role-description", default=DEFAULT_ROLE_DESCRIPTION, help="Agent role description (default: %(default)s)")
    p.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Key output path (default: %(default)s)")
    args = p.parse_args()

    base = args.base_url.rstrip("/")
    out_path = resolve_output(args.output)

    print(f"[1/4] Authenticating against {base} ...")
    try:
        bearer_token, auth_mode = get_bearer_token(base, args.username, args.password, args.token)
    except Exception as exc:
        print(f"  FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"  OK: auth via {auth_mode}")

    print(f"[2/4] Checking for existing openclaw agent '{args.agent_name}' ...")
    try:
        agents = list_agents(base, bearer_token)
    except Exception as exc:
        print(f"  FAIL: {exc}", file=sys.stderr)
        return 1

    matches = [
        agent for agent in agents
        if agent.get("name") == args.agent_name and agent.get("agent_type") == "openclaw"
    ]
    if len(matches) > 1:
        ids = ", ".join(str(agent.get("id")) for agent in matches)
        print(f"  FAIL: multiple matching openclaw agents found for '{args.agent_name}': {ids}", file=sys.stderr)
        return 1

    action = "REUSED"
    agent_id: str
    api_key: str

    if matches:
        agent_id = str(matches[0]["id"])
        print(f"  Found existing linked agent: id={agent_id}")

        saved_key = load_saved_key(out_path, agent_id)
        if saved_key:
            print("[3/4] Validating saved gateway key via POST /api/gateway/heartbeat ...")
            try:
                if validate_gateway_key(base, saved_key):
                    api_key = saved_key
                    print(f"  OK: reusing saved key from {out_path}")
                else:
                    print("  Saved key is stale or invalid; regenerating a new one ...")
                    resp = regenerate_key(base, bearer_token, agent_id)
                    api_key = resp.get("api_key", "")
                    action = "REKEYED"
            except Exception as exc:
                print(f"  FAIL: {exc}", file=sys.stderr)
                return 1
        else:
            print("[3/4] No reusable saved key found; regenerating via POST /api/agents/{id}/api-key ...")
            try:
                resp = regenerate_key(base, bearer_token, agent_id)
            except Exception as exc:
                print(f"  FAIL: {exc}", file=sys.stderr)
                return 1
            api_key = resp.get("api_key", "")
            action = "REKEYED"

        if not api_key.startswith("oc-"):
            print("  FAIL: did not obtain a valid OpenClaw gateway key", file=sys.stderr)
            return 1
    else:
        print(f"[3/4] Creating linked openclaw agent '{args.agent_name}' ...")
        try:
            resp = create_openclaw_agent(base, bearer_token, args.agent_name, args.role_description)
        except Exception as exc:
            print(f"  FAIL: {exc}", file=sys.stderr)
            return 1
        agent_id = str(resp.get("id", ""))
        api_key = resp.get("api_key", "")
        action = "CREATED"
        if not agent_id or not api_key.startswith("oc-"):
            print(f"  FAIL: agent response missing id/api_key: {resp}", file=sys.stderr)
            return 1
        print(f"  OK: created linked agent id={agent_id}")

    print(f"[4/4] Saving gateway key to {out_path} ...")
    save_key(
        out_path,
        base_url=base,
        agent_id=agent_id,
        agent_name=args.agent_name,
        role_description=args.role_description,
        api_key=api_key,
        source=action.lower(),
    )
    print("  OK: key saved")

    print(f"\n=== {action} ===")
    print(f"  agent_name : {args.agent_name}")
    print(f"  agent_id   : {agent_id}")
    print(f"  key_file   : {out_path}")
    print(f"  key_prefix : {api_key[:8]}...")
    print(f"  auth_mode  : {auth_mode}")
    print("\nNext:")
    print(f"  python3 scripts/clawith_vibe_once.py --api-key $(jq -r .api_key {out_path}) --base-url {base} --workdir {REPO_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

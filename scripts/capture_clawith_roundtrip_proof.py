#!/usr/bin/env python3
"""Package an honest judge-facing proof bundle for the Clawith/vibecosystem round-trip.

This helper copies locally available receipts + optional authenticated Clawith API
reads into a single timestamped proof directory with a manifest that clearly marks
which evidence is present and which is still missing.

The five proof items tracked:

  1. Queued task / inbound work  — gateway message.json showing a pending message
  2. Linked OpenClaw agent identity — redacted agent key metadata
  3. Worker pickup / execution evidence — claude stdout/stderr + worker script
  4. Response/result back in Clawith — gateway report.json + optional API session
  5. Receipts / artifacts / screenshot bundle — user-supplied screenshots

It does NOT fabricate screenshots, invent API responses, or claim native Clawith
parity.  If a piece of evidence does not exist yet, the manifest says so.

Usage:
  # Minimal — package whatever local artifacts exist right now
  python3 scripts/capture_clawith_roundtrip_proof.py

  # With Clawith API reads (requires auth)
  python3 scripts/capture_clawith_roundtrip_proof.py \
    --base-url http://localhost:3008 \
    --token "$CLAWITH_TOKEN"

  # Point at a specific gateway artifact run
  python3 scripts/capture_clawith_roundtrip_proof.py \
    --artifacts-dir artifacts/clawith-gateway/20260323T120000Z

  # Include user-supplied screenshots
  python3 scripts/capture_clawith_roundtrip_proof.py \
    --screenshots-dir ~/Desktop/clawith-screenshots
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KEY_FILE = REPO_ROOT / "runtime" / "clawith_openclaw_key.json"

# Regex for values that look like secrets
_SECRET_PATTERNS = [
    re.compile(r"(oc-)[A-Za-z0-9_-]{8,}"),       # gateway keys
    re.compile(r"(Bearer\s+)[A-Za-z0-9_.=-]{20,}", re.IGNORECASE),
    re.compile(r"(eyJ)[A-Za-z0-9_.=-]{20,}"),     # JWTs
    re.compile(r"(sk-|ak-|pk-)[A-Za-z0-9_-]{8,}"),
]


def now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def redact_secrets(text: str) -> str:
    """Replace likely secret values with a redacted placeholder."""
    for pat in _SECRET_PATTERNS:
        text = pat.sub(lambda m: m.group(1) + "REDACTED", text)
    return text


def redact_dict(obj: Any) -> Any:
    """Deep-copy a JSON-serializable object with secret values redacted."""
    if isinstance(obj, str):
        return redact_secrets(obj)
    if isinstance(obj, dict):
        return {k: redact_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_dict(v) for v in obj]
    return obj


def safe_copy(src: Path, dst: Path) -> bool:
    """Copy a file, creating parent dirs. Returns True on success."""
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def copy_and_redact_json(src: Path, dst: Path) -> bool:
    """Copy a JSON file with secrets redacted."""
    if not src.exists():
        return False
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(redact_dict(data), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def http_json_safe(method: str, url: str, headers: dict[str, str]) -> dict[str, Any] | None:
    """Best-effort HTTP JSON fetch. Returns None on any failure."""
    import urllib.error
    import urllib.request

    body = None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:
        return None


def gather_agent_identity(key_file: Path, proof_dir: Path) -> dict[str, Any]:
    """Copy the linked-agent key metadata (redacted) into the bundle."""
    evidence: dict[str, Any] = {"present": False, "path": None, "note": ""}
    if not key_file.exists():
        evidence["note"] = f"Key file not found at {key_file}"
        return evidence

    if copy_and_redact_json(key_file, proof_dir / "agent-identity.json"):
        evidence["present"] = True
        evidence["path"] = "agent-identity.json"
        evidence["note"] = "Redacted copy of linked OpenClaw agent metadata."
    else:
        evidence["note"] = "Key file exists but could not be read/redacted."
    return evidence


def gather_gateway_artifacts(artifacts_dir: Path | None, proof_dir: Path) -> dict[str, Any]:
    """Copy gateway worker artifacts (poll, message, prompt, result) into the bundle."""
    evidence: dict[str, Any] = {"present": False, "paths": [], "note": ""}
    if artifacts_dir is None:
        # Try to find the latest run
        default_root = REPO_ROOT / "artifacts" / "clawith-gateway"
        if default_root.is_dir():
            runs = sorted(default_root.iterdir())
            if runs:
                artifacts_dir = runs[-1]

    if artifacts_dir is None or not artifacts_dir.is_dir():
        evidence["note"] = "No gateway artifact directory found."
        return evidence

    dst_root = proof_dir / "gateway-artifacts"
    copied = []
    for item in sorted(artifacts_dir.rglob("*")):
        if not item.is_file():
            continue
        rel = item.relative_to(artifacts_dir)
        dst = dst_root / rel
        if item.suffix == ".json":
            if copy_and_redact_json(item, dst):
                copied.append(str(rel))
        else:
            if safe_copy(item, dst):
                copied.append(str(rel))

    evidence["present"] = len(copied) > 0
    evidence["paths"] = copied
    evidence["source_dir"] = str(artifacts_dir)
    evidence["note"] = f"Copied {len(copied)} artifact(s) from {artifacts_dir.name}." if copied else "Artifact directory was empty."
    return evidence


def _infer_agent_id(key_file: Path) -> str | None:
    """Try to read agent_id from the key file before redaction."""
    if not key_file.exists():
        return None
    try:
        data = json.loads(key_file.read_text(encoding="utf-8"))
        return data.get("agent_id") or None
    except (json.JSONDecodeError, OSError):
        return None


def _infer_session_id(artifacts_dir: Path | None) -> str | None:
    """Try to infer a session/conversation id from gateway message.json files."""
    if artifacts_dir is None or not artifacts_dir.is_dir():
        return None
    for msg_file in sorted(artifacts_dir.rglob("message.json")):
        try:
            data = json.loads(msg_file.read_text(encoding="utf-8"))
            cid = data.get("conversation_id")
            if cid:
                return str(cid)
        except (json.JSONDecodeError, OSError):
            continue
    return None


def gather_clawith_api(
    base_url: str | None,
    token: str | None,
    proof_dir: Path,
    *,
    agent_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Optional: fetch live Clawith state via authenticated API.

    When agent_id is available, fetches the agent-specific endpoints:
      GET /api/agents/{agent_id}
      GET /api/agents/{agent_id}/gateway-messages
      GET /api/agents/{agent_id}/sessions?scope=all
      GET /api/agents/{agent_id}/sessions/{session_id}/messages
    """
    evidence: dict[str, Any] = {"present": False, "paths": [], "note": ""}
    if not base_url or not token:
        evidence["note"] = "No --base-url / --token provided; skipping Clawith API reads."
        return evidence

    headers = {"Authorization": f"Bearer {token}"}
    base = base_url.rstrip("/")

    # Always fetch these
    api_reads: dict[str, str] = {
        "health": "/api/health",
        "agents": "/api/agents/",
    }

    # Agent-specific reads when agent_id is known
    if agent_id:
        api_reads["agent-detail"] = f"/api/agents/{agent_id}"
        api_reads["gateway-messages"] = f"/api/agents/{agent_id}/gateway-messages"
        api_reads["sessions"] = f"/api/agents/{agent_id}/sessions?scope=all"

    fetched = []
    api_dir = proof_dir / "clawith-api"
    api_dir.mkdir(parents=True, exist_ok=True)

    for label, path in api_reads.items():
        data = http_json_safe("GET", base + path, headers)
        if data is not None:
            redacted = redact_dict(data)
            out = api_dir / f"{label}.json"
            out.write_text(json.dumps(redacted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            fetched.append(f"clawith-api/{label}.json")

    # Session messages — use inferred session_id, or pick latest from sessions response
    resolved_session_id = session_id
    if not resolved_session_id and agent_id:
        sessions_file = api_dir / "sessions.json"
        if sessions_file.exists():
            try:
                sessions_data = json.loads(sessions_file.read_text(encoding="utf-8"))
                items = sessions_data if isinstance(sessions_data, list) else sessions_data.get("items", sessions_data.get("data", []))
                if items and isinstance(items, list):
                    resolved_session_id = str(items[0].get("id", ""))
                    evidence["session_id_source"] = "latest from sessions list"
            except (json.JSONDecodeError, OSError):
                pass

    if session_id:
        evidence["session_id_source"] = "inferred from gateway artifacts"

    if resolved_session_id and agent_id:
        label = "session-messages"
        path = f"/api/agents/{agent_id}/sessions/{resolved_session_id}/messages"
        data = http_json_safe("GET", base + path, headers)
        if data is not None:
            redacted = redact_dict(data)
            out = api_dir / f"{label}.json"
            out.write_text(json.dumps(redacted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            fetched.append(f"clawith-api/{label}.json")

    evidence["present"] = len(fetched) > 0
    evidence["paths"] = fetched
    evidence["agent_id_used"] = agent_id
    evidence["session_id_used"] = resolved_session_id
    note_parts = []
    if fetched:
        note_parts.append(f"Fetched {len(fetched)} API endpoint(s).")
    else:
        note_parts.append("All API reads failed.")
    if agent_id:
        note_parts.append(f"Agent-specific reads attempted for agent_id={agent_id}.")
    else:
        note_parts.append("No agent_id available; only generic endpoints attempted.")
    evidence["note"] = " ".join(note_parts)
    return evidence


def gather_worker_script_snapshot(proof_dir: Path) -> dict[str, Any]:
    """Copy the gateway worker script itself as execution-method evidence."""
    evidence: dict[str, Any] = {"present": False, "path": None, "note": ""}
    src = REPO_ROOT / "scripts" / "clawith_vibe_once.py"
    dst = proof_dir / "worker-script-snapshot.py"
    if safe_copy(src, dst):
        evidence["present"] = True
        evidence["path"] = "worker-script-snapshot.py"
        evidence["note"] = "Snapshot of the gateway worker used for execution."
    else:
        evidence["note"] = "Worker script not found."
    return evidence


def gather_screenshots(screenshots_dir: Path | None, proof_dir: Path) -> dict[str, Any]:
    """Copy user-supplied screenshot files into the proof bundle.

    Does NOT automate screenshots.  Only copies files the user has already placed
    into the given directory.  Marks each file present and explicitly notes when
    no screenshots were supplied.
    """
    evidence: dict[str, Any] = {"present": False, "paths": [], "note": ""}
    if screenshots_dir is None:
        evidence["note"] = "No --screenshots-dir provided; screenshot bundle absent."
        return evidence
    if not screenshots_dir.is_dir():
        evidence["note"] = f"Screenshots dir not found: {screenshots_dir}"
        return evidence

    dst_root = proof_dir / "screenshots"
    copied = []
    _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".pdf"}
    for item in sorted(screenshots_dir.rglob("*")):
        if not item.is_file():
            continue
        if item.suffix.lower() not in _IMAGE_EXTS:
            continue
        rel = item.relative_to(screenshots_dir)
        dst = dst_root / rel
        if safe_copy(item, dst):
            copied.append(str(rel))

    evidence["present"] = len(copied) > 0
    evidence["paths"] = copied
    evidence["note"] = (
        f"Copied {len(copied)} screenshot(s) from {screenshots_dir.name}."
        if copied
        else f"Screenshots dir exists but contains no image files: {screenshots_dir}"
    )
    return evidence


def _paths_matching(evidence: dict[str, Any], suffixes: tuple[str, ...]) -> list[str]:
    return [str(path) for path in evidence.get("paths", []) if str(path).endswith(suffixes)]


def _summarize_inbound_task(gateway_artifacts: dict[str, Any], clawith_api: dict[str, Any]) -> dict[str, Any]:
    message_paths = _paths_matching(gateway_artifacts, ("message.json",))
    session_paths = _paths_matching(clawith_api, ("session-messages.json",))
    present = bool(message_paths or session_paths)
    paths = message_paths + session_paths
    if present:
        note_parts = []
        if message_paths:
            note_parts.append(f"Gateway inbound receipt(s): {', '.join(message_paths[:3])}.")
        if session_paths:
            note_parts.append("Clawith session message export captured.")
        note = " ".join(note_parts)
    else:
        note = "No gateway message.json or Clawith session-messages evidence captured yet."
    return {"present": present, "paths": paths, "note": note}


def _summarize_worker_execution(gateway_artifacts: dict[str, Any], worker_snapshot: dict[str, Any]) -> dict[str, Any]:
    runtime_paths = _paths_matching(gateway_artifacts, ("prompt.txt", "claude.stdout.txt", "claude.stderr.txt"))
    present = bool(runtime_paths)
    paths = list(runtime_paths)
    if worker_snapshot.get("path"):
        paths.append(str(worker_snapshot["path"]))

    note_parts = []
    if runtime_paths:
        note_parts.append(f"Worker run files captured: {', '.join(runtime_paths[:4])}.")
    else:
        note_parts.append("No prompt/Claude stdout/stderr files captured yet.")

    if worker_snapshot.get("present"):
        note_parts.append("Worker script snapshot included for method inspection.")
    else:
        note_parts.append(worker_snapshot.get("note", "Worker script snapshot missing."))

    return {"present": present, "paths": paths, "note": " ".join(note_parts)}


def _summarize_result_in_clawith(gateway_artifacts: dict[str, Any], clawith_api: dict[str, Any]) -> dict[str, Any]:
    report_paths = _paths_matching(gateway_artifacts, ("report.json",))
    api_paths = _paths_matching(clawith_api, ("gateway-messages.json", "session-messages.json"))
    present = bool(report_paths or api_paths)
    paths = report_paths + api_paths

    if present:
        note_parts = []
        if report_paths:
            note_parts.append(f"Gateway report receipt(s): {', '.join(report_paths[:3])}.")
        if api_paths:
            note_parts.append("Clawith-side message/session export captured.")
        note = " ".join(note_parts)
    else:
        note = "No report.json or Clawith-side gateway/session export captured yet."

    return {"present": present, "paths": paths, "note": note}


def build_manifest(
    *,
    tag: str,
    agent_identity: dict[str, Any],
    gateway_artifacts: dict[str, Any],
    clawith_api: dict[str, Any],
    worker_snapshot: dict[str, Any],
    screenshots: dict[str, Any],
) -> dict[str, Any]:
    """Build the proof-bundle manifest.

    Evidence pieces map to the five proof items:
      1. inbound_task          — queued task / inbound work (from gateway message.json)
      2. agent_identity_linked — linked OpenClaw agent identity
      3. worker_execution      — worker pickup / execution evidence
      4. result_in_clawith     — response/result back in Clawith
      5. screenshot_bundle     — receipts / artifacts / screenshot bundle
    """
    pieces = {
        "inbound_task": _summarize_inbound_task(gateway_artifacts, clawith_api),
        "agent_identity_linked": agent_identity,
        "worker_execution": _summarize_worker_execution(gateway_artifacts, worker_snapshot),
        "result_in_clawith": _summarize_result_in_clawith(gateway_artifacts, clawith_api),
        "screenshot_bundle": screenshots,
    }

    present_count = sum(1 for p in pieces.values() if p.get("present"))
    total_count = len(pieces)

    missing = [k for k, v in pieces.items() if not v.get("present")]

    return {
        "proof_bundle_version": 2,
        "captured_at": tag,
        "repo_root": str(REPO_ROOT),
        "summary": {
            "present": present_count,
            "total": total_count,
            "complete": present_count == total_count,
            "missing_pieces": missing,
        },
        "evidence": pieces,
        "sources": {
            "gateway_artifacts": gateway_artifacts,
            "clawith_api": clawith_api,
            "worker_script_snapshot": worker_snapshot,
            "screenshots": screenshots,
        },
        "honesty_notice": (
            "This bundle contains only artifacts that existed at capture time. "
            "No screenshots were fabricated. No API responses were invented. "
            "Missing evidence is explicitly listed above."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package an honest proof bundle for the Clawith/vibecosystem round-trip.",
    )
    parser.add_argument("--base-url", default=os.environ.get("CLAWITH_BASE_URL", ""), help="Clawith URL for optional live API reads")
    parser.add_argument("--token", default=os.environ.get("CLAWITH_TOKEN", ""), help="Bearer token for Clawith API")
    parser.add_argument("--key-file", default=str(DEFAULT_KEY_FILE), help="Path to linked agent key file (default: %(default)s)")
    parser.add_argument("--artifacts-dir", default="", help="Specific gateway artifacts dir to package")
    parser.add_argument("--screenshots-dir", default="", help="Dir containing user-supplied screenshots to include in bundle")
    parser.add_argument("--output-dir", default="", help="Output proof bundle dir (default: proof-bundles/<timestamp>)")
    args = parser.parse_args()

    tag = now_tag()
    if args.output_dir:
        proof_dir = Path(args.output_dir).resolve()
    else:
        proof_dir = REPO_ROOT / "proof-bundles" / tag
    proof_dir.mkdir(parents=True, exist_ok=True)

    key_file = Path(args.key_file).expanduser()
    if not key_file.is_absolute():
        key_file = REPO_ROOT / key_file

    artifacts_dir = Path(args.artifacts_dir).resolve() if args.artifacts_dir else None
    screenshots_dir = Path(args.screenshots_dir).resolve() if args.screenshots_dir else None

    print(f"Capturing proof bundle → {proof_dir}")

    # Infer identifiers for richer API reads
    agent_id = _infer_agent_id(key_file)
    session_id = _infer_session_id(artifacts_dir)

    agent_identity = gather_agent_identity(key_file, proof_dir)
    gateway_artifacts = gather_gateway_artifacts(artifacts_dir, proof_dir)
    clawith_api = gather_clawith_api(
        args.base_url or None,
        args.token or None,
        proof_dir,
        agent_id=agent_id,
        session_id=session_id,
    )
    worker_snapshot = gather_worker_script_snapshot(proof_dir)
    screenshots = gather_screenshots(screenshots_dir, proof_dir)

    manifest = build_manifest(
        tag=tag,
        agent_identity=agent_identity,
        gateway_artifacts=gateway_artifacts,
        clawith_api=clawith_api,
        worker_snapshot=worker_snapshot,
        screenshots=screenshots,
    )

    manifest_path = proof_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Human-readable summary
    proof_item_labels = {
        "inbound_task": "1. Queued task / inbound work",
        "agent_identity_linked": "2. Linked OpenClaw agent identity",
        "worker_execution": "3. Worker pickup / execution evidence",
        "result_in_clawith": "4. Response/result back in Clawith",
        "screenshot_bundle": "5. Receipts / screenshot bundle",
    }
    summary_lines = [
        f"# Clawith Round-Trip Proof Bundle",
        f"Captured: {tag}",
        f"Complete: {'YES' if manifest['summary']['complete'] else 'NO'}",
        f"Present: {manifest['summary']['present']}/{manifest['summary']['total']}",
        "",
    ]
    for name, ev in manifest["evidence"].items():
        status = "PRESENT" if ev.get("present") else "MISSING"
        label = proof_item_labels.get(name, name)
        summary_lines.append(f"  [{status}] {label}")
        summary_lines.append(f"           {ev.get('note', '')}")

    if manifest["summary"]["missing_pieces"]:
        summary_lines.append("")
        summary_lines.append("Missing pieces (action needed):")
        for m in manifest["summary"]["missing_pieces"]:
            label = proof_item_labels.get(m, m)
            summary_lines.append(f"  - {label}")

    summary_text = "\n".join(summary_lines) + "\n"
    (proof_dir / "SUMMARY.txt").write_text(summary_text, encoding="utf-8")

    print(summary_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

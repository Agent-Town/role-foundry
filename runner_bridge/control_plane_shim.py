from __future__ import annotations

import argparse
import json
import threading
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class ShimStateStore:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.data_dir / "control-plane-state.json"
        self._lock = threading.Lock()
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        state = {
            "meta": {
                "mode": "clawith-compatible-shim",
                "created_at": _utc_now(),
            },
            "roles": {},
            "scenarios": {},
            "runs": {},
        }
        self.state_path.write_text(json.dumps(state, indent=2) + "\n")
        return state

    def _save(self) -> None:
        self.state_path.write_text(json.dumps(self._state, indent=2) + "\n")

    def upsert_role(self, payload: dict[str, Any]) -> dict[str, Any]:
        role_id = payload.get("id")
        if not role_id:
            raise ValueError("role payload missing id")
        with self._lock:
            self._state["roles"][role_id] = payload
            self._state["meta"]["updated_at"] = _utc_now()
            self._save()
            return dict(self._state["roles"][role_id])

    def upsert_scenario(self, payload: dict[str, Any]) -> dict[str, Any]:
        scenario_id = payload.get("id")
        if not scenario_id:
            raise ValueError("scenario payload missing id")
        with self._lock:
            self._state["scenarios"][scenario_id] = payload
            self._state["meta"]["updated_at"] = _utc_now()
            self._save()
            return dict(self._state["scenarios"][scenario_id])

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = payload.get("run_id")
        if not run_id:
            raise ValueError("run payload missing run_id")
        with self._lock:
            run = dict(self._state["runs"].get(run_id, {}))
            run.update(payload)
            run.setdefault("created_at", _utc_now())
            run["status"] = payload.get("status") or run.get("status") or "queued"
            run.setdefault("state_history", [])
            run["state_history"].append(
                {
                    "ts": _utc_now(),
                    "source": "create",
                    "status": run["status"],
                    "payload": payload,
                }
            )
            run["updated_at"] = _utc_now()
            self._state["runs"][run_id] = run
            self._state["meta"]["updated_at"] = run["updated_at"]
            self._save()
            return json.loads(json.dumps(run))

    def patch_run(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            run = dict(self._state["runs"].get(run_id, {"run_id": run_id, "status": "queued", "state_history": []}))
            run.update(payload)
            run.setdefault("state_history", [])
            run["status"] = payload.get("status") or run.get("status") or "queued"
            run["state_history"].append(
                {
                    "ts": _utc_now(),
                    "source": "patch",
                    "status": run["status"],
                    "payload": payload,
                }
            )
            run["updated_at"] = _utc_now()
            self._state["runs"][run_id] = run
            self._state["meta"]["updated_at"] = run["updated_at"]
            self._save()
            return json.loads(json.dumps(run))

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            run = self._state["runs"].get(run_id)
            return json.loads(json.dumps(run)) if run else None

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mode": self._state["meta"].get("mode"),
                "state_path": str(self.state_path),
                "role_count": len(self._state["roles"]),
                "scenario_count": len(self._state["scenarios"]),
                "run_count": len(self._state["runs"]),
                "updated_at": self._state["meta"].get("updated_at") or self._state["meta"].get("created_at"),
            }


class _ControlPlaneShimHandler(BaseHTTPRequestHandler):
    server: "ControlPlaneShimServer"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return self._write_json(200, {"status": "ok", **self.server.store.summary()})

        try:
            self._require_auth()
        except PermissionError:
            return

        if parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.split("/api/runs/", 1)[1]
            run = self.server.store.get_run(run_id)
            if not run:
                return self._write_json(404, {"error": f"run not found: {run_id}"})
            return self._write_json(200, run)

        return self._write_json(404, {"error": f"unknown path: {parsed.path}"})

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            self._require_auth()
        except PermissionError:
            return
        payload = self._read_json()

        try:
            if parsed.path == "/api/roles":
                return self._write_json(201, self.server.store.upsert_role(payload))
            if parsed.path == "/api/scenarios":
                return self._write_json(201, self.server.store.upsert_scenario(payload))
            if parsed.path == "/api/runs":
                return self._write_json(201, self.server.store.create_run(payload))
        except ValueError as exc:
            return self._write_json(400, {"error": str(exc)})

        return self._write_json(404, {"error": f"unknown path: {parsed.path}"})

    def do_PATCH(self):
        parsed = urlparse(self.path)
        try:
            self._require_auth()
        except PermissionError:
            return
        payload = self._read_json()

        if parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.split("/api/runs/", 1)[1]
            return self._write_json(200, self.server.store.patch_run(run_id, payload))

        return self._write_json(404, {"error": f"unknown path: {parsed.path}"})

    def log_message(self, format, *args):
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return {}

    def _require_auth(self) -> None:
        secret = self.server.secret
        if not secret:
            return
        actual = self.headers.get("Authorization")
        expected = f"Bearer {secret}"
        if actual != expected:
            self._write_json(401, {"error": "unauthorized"})
            raise PermissionError("unauthorized")

    def _write_json(self, status: int, payload: dict[str, Any]):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ControlPlaneShimServer(ThreadingHTTPServer, AbstractContextManager):
    daemon_threads = True

    def __init__(self, host: str, port: int, data_dir: str | Path, secret: str = ""):
        self.store = ShimStateStore(data_dir)
        self.secret = secret
        super().__init__((host, port), _ControlPlaneShimHandler)
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.server_address
        return f"http://{host}:{port}"

    def start(self) -> "ControlPlaneShimServer":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.shutdown()
        self.server_close()
        self.thread.join(timeout=2)

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False


def start_shim_server(
    data_dir: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    secret: str = "",
) -> ControlPlaneShimServer:
    return ControlPlaneShimServer(host, port, data_dir, secret=secret).start()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clawith-compatible control-plane shim for Role Foundry")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3011)
    parser.add_argument("--data-dir", default="runtime/control-plane-shim")
    parser.add_argument("--secret", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    server = start_shim_server(args.data_dir, host=args.host, port=args.port, secret=args.secret)
    print(
        json.dumps(
            {
                "status": "listening",
                "mode": "clawith-compatible-shim",
                "base_url": server.base_url,
                "data_dir": str(Path(args.data_dir)),
            },
            indent=2,
        )
    )
    try:
        server.thread.join()
    except KeyboardInterrupt:
        server.stop()
    return 0


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())

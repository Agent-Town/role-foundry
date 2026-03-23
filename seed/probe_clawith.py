#!/usr/bin/env python3
"""Read-only Clawith readiness probe for Role Foundry.

This script is intentionally conservative:
- public HTTP checks use GET only
- authenticated checks use GET only after explicit login/token input
- optional local DB checks use read-only SQL over `docker exec`
- optional route discovery reads OpenAPI via a backend container or local source tree

Examples:
  python3 seed/probe_clawith.py --base-url http://localhost:3000
  python3 seed/probe_clawith.py \
    --base-url http://localhost:3008 \
    --backend-container clawith-backend-1 \
    --postgres-container clawith-postgres-1
  python3 seed/probe_clawith.py \
    --base-url http://localhost:3008 \
    --username alice --password secret \
    --backend-container clawith-backend-1 \
    --postgres-container clawith-postgres-1
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


CRITICAL_PUBLIC_PATHS = [
    "/api/health",
    "/api/version",
    "/api/auth/registration-config",
]

PRIVILEGED_PATHS = [
    "/api/auth/me",
    "/api/enterprise/llm-providers",
    "/api/enterprise/llm-models",
    "/api/admin/companies",
]

ROLE_FOUNDRY_NATIVE_GAPS = [
    "/api/roles",
    "/api/scenarios",
    "/api/runs/{run_id}",
]


def build_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def truncate(text: str, limit: int = 220) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def parse_json_bytes(body: bytes) -> Any | None:
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return None


def http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    body = None
    req_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return {
                "ok": True,
                "status": resp.status,
                "url": url,
                "content_type": resp.headers.get("Content-Type", ""),
                "json": parse_json_bytes(raw),
                "body": raw.decode("utf-8", errors="replace"),
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return {
            "ok": False,
            "status": exc.code,
            "url": url,
            "content_type": exc.headers.get("Content-Type", ""),
            "json": parse_json_bytes(raw),
            "body": raw.decode("utf-8", errors="replace"),
        }
    except Exception as exc:  # pragma: no cover - exercised via subprocess tests
        return {
            "ok": False,
            "status": None,
            "url": url,
            "content_type": "",
            "json": None,
            "body": "",
            "error": str(exc),
        }


def record_check(
    checks: list[dict[str, Any]],
    name: str,
    method: str,
    path: str,
    result: dict[str, Any],
    *,
    expect_status: set[int] | None = None,
    note: str = "",
) -> dict[str, Any]:
    status = result.get("status")
    passed = status in expect_status if expect_status is not None else bool(result.get("ok"))
    entry = {
        "name": name,
        "method": method,
        "path": path,
        "status": status,
        "passed": passed,
        "note": note,
    }
    if result.get("json") is not None:
        entry["json"] = result["json"]
    elif result.get("error"):
        entry["error"] = result["error"]
    elif result.get("body"):
        entry["body_excerpt"] = truncate(result["body"])
    checks.append(entry)
    return entry


def fetch_openapi(base_url: str, timeout: float, backend_container: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if backend_container:
        try:
            proc = subprocess.run(
                [
                    "docker",
                    "exec",
                    backend_container,
                    "sh",
                    "-lc",
                    "curl -sS http://localhost:8000/openapi.json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return None, "docker CLI not available for backend container probe"
        if proc.returncode == 0:
            try:
                return json.loads(proc.stdout), f"backend-container:{backend_container}"
            except json.JSONDecodeError:
                return None, f"backend container {backend_container} returned non-JSON openapi output"
        return None, truncate(proc.stderr or proc.stdout or f"docker exec failed with {proc.returncode}")

    for path in ("/api/openapi.json", "/openapi.json"):
        result = http_request("GET", build_url(base_url, path), timeout=timeout)
        spec = result.get("json")
        if isinstance(spec, dict) and isinstance(spec.get("paths"), dict):
            return spec, f"http:{path}"
    return None, "openapi not exposed on public base URL"


def inspect_source_tree(source_dir: str | None) -> dict[str, Any]:
    findings = {
        "source_dir": source_dir,
        "available": False,
        "first_user_becomes_platform_admin": None,
        "health_path": None,
        "llm_models_path": None,
        "admin_companies_path": None,
        "legacy_paths_present": {},
        "notes": [],
    }
    if not source_dir:
        return findings

    root = Path(source_dir).expanduser().resolve()
    if not root.exists():
        findings["notes"].append(f"source dir missing: {root}")
        return findings

    findings["available"] = True
    main_py = root / "backend" / "app" / "main.py"
    auth_py = root / "backend" / "app" / "api" / "auth.py"
    enterprise_py = root / "backend" / "app" / "api" / "enterprise.py"
    admin_py = root / "backend" / "app" / "api" / "admin.py"

    def read_text(path: Path) -> str:
        try:
            return path.read_text()
        except Exception:
            return ""

    main_text = read_text(main_py)
    auth_text = read_text(auth_py)
    enterprise_text = read_text(enterprise_py)
    admin_text = read_text(admin_py)
    all_py = "\n".join(read_text(path) for path in root.rglob("*.py"))

    findings["health_path"] = "/api/health" if '"/api/health"' in main_text else None
    findings["llm_models_path"] = "/api/enterprise/llm-models" if '"/llm-models"' in enterprise_text else None
    findings["admin_companies_path"] = "/api/admin/companies" if '"/companies"' in admin_text else None
    findings["first_user_becomes_platform_admin"] = (
        "first user to register becomes the platform admin automatically" in auth_text.lower()
        or 'role = "platform_admin"' in auth_text
    )

    for legacy_path in ROLE_FOUNDRY_NATIVE_GAPS:
        findings["legacy_paths_present"][legacy_path] = legacy_path in all_py

    return findings


def probe_postgres_counts(container: str | None) -> dict[str, Any]:
    if not container:
        return {"available": False, "reason": "no postgres container supplied"}

    script = r'''psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At <<'SQL'
select 'users=' || count(*) from users;
select 'platform_admins=' || count(*) from users where role = 'platform_admin';
select 'tenants=' || count(*) from tenants;
select 'llm_models=' || count(*) from llm_models;
select 'enabled_llm_models=' || count(*) from llm_models where enabled = true;
SQL'''

    try:
        proc = subprocess.run(
            ["docker", "exec", container, "sh", "-lc", script],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return {"available": False, "reason": "docker CLI not available"}

    if proc.returncode != 0:
        return {
            "available": False,
            "reason": truncate(proc.stderr or proc.stdout or f"docker exec failed with {proc.returncode}"),
        }

    counts: dict[str, int] = {}
    for line in proc.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            counts[key.strip()] = int(value.strip())
        except ValueError:
            continue

    return {
        "available": True,
        "container": container,
        "counts": counts,
    }


def derive_route_findings(openapi: dict[str, Any] | None, source_findings: dict[str, Any]) -> dict[str, Any]:
    findings = {
        "surface_source": None,
        "present": {},
        "compat_gaps": [],
    }

    if isinstance(openapi, dict) and isinstance(openapi.get("paths"), dict):
        findings["surface_source"] = "openapi"
        paths = openapi["paths"]
        for path in CRITICAL_PUBLIC_PATHS + PRIVILEGED_PATHS + ROLE_FOUNDRY_NATIVE_GAPS:
            findings["present"][path] = path in paths
    elif source_findings.get("available"):
        findings["surface_source"] = "source"
        findings["present"]["/api/health"] = bool(source_findings.get("health_path"))
        findings["present"]["/api/enterprise/llm-models"] = bool(source_findings.get("llm_models_path"))
        findings["present"]["/api/admin/companies"] = bool(source_findings.get("admin_companies_path"))
        for path, present in source_findings.get("legacy_paths_present", {}).items():
            findings["present"][path] = bool(present)
    else:
        findings["surface_source"] = "unknown"

    for path in ROLE_FOUNDRY_NATIVE_GAPS:
        if findings["present"].get(path) is False:
            findings["compat_gaps"].append(
                f"upstream path missing: {path} (Role Foundry still needs an adapter/shim here)"
            )
    return findings


def login_for_token(base_url: str, username: str | None, password: str | None, timeout: float) -> tuple[str | None, dict[str, Any] | None]:
    if not username or not password:
        return None, None
    result = http_request(
        "POST",
        build_url(base_url, "/api/auth/login"),
        payload={"username": username, "password": password},
        timeout=timeout,
    )
    payload = result.get("json") if isinstance(result.get("json"), dict) else None
    token = payload.get("access_token") if payload else None
    return token, result


def summarize(
    checks: list[dict[str, Any]],
    route_findings: dict[str, Any],
    db_findings: dict[str, Any],
    source_findings: dict[str, Any],
    auth_me: dict[str, Any] | None,
    llm_models: dict[str, Any] | None,
) -> dict[str, Any]:
    public_failures = [
        c for c in checks if c["path"] in CRITICAL_PUBLIC_PATHS and not c["passed"]
    ]
    blockers: list[str] = []
    warnings: list[str] = []

    if public_failures:
        blockers.append("public upstream surface is not healthy enough for adapter-first bring-up")

    counts = db_findings.get("counts") if db_findings.get("available") else {}
    if counts:
        if counts.get("platform_admins", 0) == 0:
            blockers.append("no platform_admin user present in Clawith yet")
        if counts.get("llm_models", 0) == 0:
            blockers.append("no llm_models entries present in Clawith yet")
    else:
        warnings.append("admin/model-pool presence is unknown without postgres probe or authenticated API access")

    if auth_me and auth_me.get("status") == 200:
        payload = auth_me.get("json") or {}
        role = payload.get("role")
        if role not in {"platform_admin", "org_admin"}:
            warnings.append(f"authenticated probe role is {role!r}; admin-only surfaces may still be blocked")
    elif auth_me is None:
        warnings.append("no authenticated user probe performed")

    if llm_models and llm_models.get("status") == 200 and isinstance(llm_models.get("json"), list):
        if len(llm_models["json"]) == 0:
            blockers.append("authenticated /api/enterprise/llm-models returned an empty model pool")

    warnings.extend(route_findings.get("compat_gaps", []))

    if source_findings.get("available") and source_findings.get("first_user_becomes_platform_admin"):
        warnings.append("upstream admin bootstrap is first-user registration, not a Role Foundry seed write")

    if route_findings.get("surface_source") == "unknown":
        warnings.append("could not inspect upstream route table; native parity gaps may be understated")

    adapter_first_readiness = "ready"
    if blockers:
        adapter_first_readiness = "blocked"
    elif counts == {} and auth_me is None:
        adapter_first_readiness = "unknown"

    native_role_foundry_parity = "unknown"
    if route_findings.get("compat_gaps"):
        native_role_foundry_parity = "no"
    elif route_findings.get("surface_source") in {"openapi", "source"}:
        native_role_foundry_parity = "maybe"

    return {
        "public_upstream_ready": not public_failures,
        "adapter_first_readiness": adapter_first_readiness,
        "native_role_foundry_parity": native_role_foundry_parity,
        "blockers": blockers,
        "warnings": warnings,
    }


def print_human_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("SUMMARY")
    print(f"- base_url: {report['base_url']}")
    print(f"- public_upstream_ready: {'yes' if summary['public_upstream_ready'] else 'no'}")
    print(f"- adapter_first_readiness: {summary['adapter_first_readiness']}")
    print(f"- native_role_foundry_parity: {summary['native_role_foundry_parity']}")

    if summary["blockers"]:
        print("\nBLOCKERS")
        for item in summary["blockers"]:
            print(f"- {item}")

    if summary["warnings"]:
        print("\nWARNINGS")
        for item in summary["warnings"]:
            print(f"- {item}")

    print("\nHTTP CHECKS")
    for check in report["checks"]:
        mark = "OK" if check["passed"] else "!!"
        line = f"[{mark}] {check['method']} {check['path']}"
        if check.get("status") is not None:
            line += f" -> {check['status']}"
        if check.get("note"):
            line += f" ({check['note']})"
        print(line)
        if check.get("json") is not None:
            print(f"     {truncate(json.dumps(check['json'], sort_keys=True))}")
        elif check.get("body_excerpt"):
            print(f"     {check['body_excerpt']}")
        elif check.get("error"):
            print(f"     error: {check['error']}")

    if report.get("route_findings"):
        rf = report["route_findings"]
        print("\nROUTE DISCOVERY")
        print(f"- surface_source: {rf.get('surface_source')}")
        for path in CRITICAL_PUBLIC_PATHS + PRIVILEGED_PATHS + ROLE_FOUNDRY_NATIVE_GAPS:
            if path in rf.get("present", {}):
                print(f"- {path}: {'present' if rf['present'][path] else 'missing'}")

    db = report.get("db_findings", {})
    print("\nLOCAL STATE")
    if db.get("available"):
        print(f"- postgres_container: {db.get('container')}")
        for key, value in db.get("counts", {}).items():
            print(f"- {key}: {value}")
    else:
        print(f"- postgres probe unavailable: {db.get('reason', 'not requested')}")

    source = report.get("source_findings", {})
    if source.get("available"):
        print("\nSOURCE NOTES")
        print(f"- source_dir: {source.get('source_dir')}")
        print(
            "- first_user_becomes_platform_admin: "
            f"{'yes' if source.get('first_user_becomes_platform_admin') else 'unknown'}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only local/upstream Clawith readiness probe")
    parser.add_argument("--base-url", default=os.environ.get("CLAWITH_URL", "http://localhost:3000"))
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--token", default=os.environ.get("CLAWITH_BEARER_TOKEN", ""))
    parser.add_argument("--username", default=os.environ.get("CLAWITH_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("CLAWITH_PASSWORD", ""))
    parser.add_argument("--postgres-container", default=os.environ.get("CLAWITH_POSTGRES_CONTAINER", ""))
    parser.add_argument("--backend-container", default=os.environ.get("CLAWITH_BACKEND_CONTAINER", ""))
    parser.add_argument("--source-dir", default=os.environ.get("CLAWITH_SOURCE_DIR", ""))
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when blockers or native-parity gaps remain",
    )
    args = parser.parse_args()

    checks: list[dict[str, Any]] = []
    base_url = args.base_url.rstrip("/")

    for path in CRITICAL_PUBLIC_PATHS:
        result = http_request("GET", build_url(base_url, path), timeout=args.timeout)
        record_check(checks, path, "GET", path, result, expect_status={200})

    public_notification = http_request(
        "GET",
        build_url(base_url, "/api/enterprise/system-settings/notification_bar/public"),
        timeout=args.timeout,
    )
    record_check(
        checks,
        "notification-bar",
        "GET",
        "/api/enterprise/system-settings/notification_bar/public",
        public_notification,
        expect_status={200},
        note="optional public enterprise surface",
    )

    token = args.token or ""
    login_result = None
    if not token and args.username and args.password:
        token, login_result = login_for_token(base_url, args.username, args.password, args.timeout)
        if login_result is not None:
            record_check(
                checks,
                "login",
                "POST",
                "/api/auth/login",
                login_result,
                expect_status={200},
                note="explicit credentialed login",
            )

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    auth_me_result = http_request(
        "GET",
        build_url(base_url, "/api/auth/me"),
        headers=headers,
        timeout=args.timeout,
    )
    record_check(
        checks,
        "auth-me",
        "GET",
        "/api/auth/me",
        auth_me_result,
        expect_status={200} if token else {401},
        note="authenticated profile" if token else "expected bearer challenge",
    )

    llm_providers_result = http_request(
        "GET",
        build_url(base_url, "/api/enterprise/llm-providers"),
        headers=headers,
        timeout=args.timeout,
    )
    record_check(
        checks,
        "llm-providers",
        "GET",
        "/api/enterprise/llm-providers",
        llm_providers_result,
        expect_status={200} if token else {401},
        note="provider manifest is auth-gated upstream",
    )

    llm_models_result = http_request(
        "GET",
        build_url(base_url, "/api/enterprise/llm-models"),
        headers=headers,
        timeout=args.timeout,
    )
    record_check(
        checks,
        "llm-models",
        "GET",
        "/api/enterprise/llm-models",
        llm_models_result,
        expect_status={200} if token else {401},
        note="model pool presence requires auth",
    )

    admin_companies_result = http_request(
        "GET",
        build_url(base_url, "/api/admin/companies"),
        headers=headers,
        timeout=args.timeout,
    )
    record_check(
        checks,
        "admin-companies",
        "GET",
        "/api/admin/companies",
        admin_companies_result,
        expect_status={200, 403} if token else {401},
        note="200 for platform_admin, 403 for non-platform admin, 401 without auth",
    )

    openapi, openapi_source = fetch_openapi(base_url, args.timeout, args.backend_container or None)
    source_findings = inspect_source_tree(args.source_dir or None)
    route_findings = derive_route_findings(openapi, source_findings)
    if openapi_source and route_findings.get("surface_source") == "openapi":
        route_findings["surface_source"] = openapi_source
    elif openapi_source and route_findings.get("surface_source") == "unknown":
        route_findings["surface_source"] = openapi_source

    db_findings = probe_postgres_counts(args.postgres_container or None)

    report = {
        "base_url": base_url,
        "checks": checks,
        "route_findings": route_findings,
        "db_findings": db_findings,
        "source_findings": source_findings,
    }
    report["summary"] = summarize(
        checks,
        route_findings,
        db_findings,
        source_findings,
        auth_me_result if token else None,
        llm_models_result if token else None,
    )

    if args.json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print_human_report(report)

    if not report["summary"]["public_upstream_ready"]:
        return 2
    if args.strict and (
        report["summary"]["blockers"] or route_findings.get("compat_gaps")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

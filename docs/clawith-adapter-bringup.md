# Clawith Adapter-First Bring-up — Phase F

_Covers: F001–F004 from the forward spec._

## Purpose

This document captures the **honest state** of Role Foundry's upstream Clawith
integration seam. It is the reference for F003 (mapping completeness) and
links to the readiness checker for F001/F002/F004.

## Readiness checker

```bash
# Human output
python3 scripts/check_clawith_readiness.py --base-url http://localhost:3000

# Machine-readable JSON
python3 scripts/check_clawith_readiness.py --base-url http://localhost:3000 --json

# Offline (no network — all network checks report 'unknown')
python3 scripts/check_clawith_readiness.py --offline --json
```

The checker is **GET-only** and performs **no write operations** (F004).

## Prereq checks (F001)

| # | Check | What it means |
|---|-------|---------------|
| 1 | base URL reachable | `GET /api/health` returns 200 |
| 2 | auth surface understood | registration-config is 200, /api/auth/me returns 401 unauthenticated |
| 3 | admin presence known | requires auth or DB access to confirm; unknown without |
| 4 | model-pool presence known | requires auth to read /api/enterprise/llm-models; unknown without |
| 5 | endpoint mismatch documented | seam mapping below explicitly lists missing_upstream endpoints |
| 6 | status categorized | every check outputs exactly ready / blocked / unknown |

## False-ready prevention (F002)

The readiness checker **never** reports overall `ready` when any individual
check is `blocked` or `unknown`. This is enforced by `compute_overall_readiness()`
and tested in `tests/test_phase_f.py`.

## Seam-to-upstream mapping matrix (F003)

Allowed statuses: `matches` · `adapter_needed` · `missing_upstream` · `blocked_by_auth` · `unknown`

| Role Foundry seam | Upstream path | Status | Note |
|---|---|---|---|
| `GET /api/health` | `GET /api/health` | matches | Upstream exposes this natively. |
| `GET /api/version` | `GET /api/version` | matches | Upstream exposes this natively. |
| `GET /api/auth/registration-config` | `GET /api/auth/registration-config` | matches | Upstream exposes this natively. |
| `GET /api/auth/me` | `GET /api/auth/me` | blocked_by_auth | Present upstream but requires bearer token. |
| `GET /api/enterprise/llm-models` | `GET /api/enterprise/llm-models` | blocked_by_auth | Present upstream but auth-gated; model pool may be empty. |
| `GET /api/admin/companies` | `GET /api/admin/companies` | blocked_by_auth | Present upstream; 200 for platform_admin, 403 otherwise. |
| `POST /api/roles` | — | missing_upstream | Not observed in upstream Clawith. Adapter/shim required. |
| `POST /api/scenarios` | — | missing_upstream | Not observed in upstream Clawith. Adapter/shim required. |
| `PATCH /api/runs/{run_id}` | — | missing_upstream | Not observed in upstream Clawith. Adapter/shim required. |
| `GET /api/enterprise/llm-providers` | `GET /api/enterprise/llm-providers` | blocked_by_auth | Present upstream but auth-gated. |
| `POST /api/auth/register` | `POST /api/auth/register` | adapter_needed | Upstream accepts registration; first user becomes platform_admin. Role Foundry does not call this automatically. |
| `POST /api/auth/login` | `POST /api/auth/login` | adapter_needed | Upstream exposes login. Role Foundry probe uses this only when explicit credentials are supplied. |

### Completeness

Every row has an explicit status from the allowed set. No row is left blank
or implicitly "fine". This satisfies F003's 100% coverage threshold.

## Non-destructive guarantee (F004)

The readiness checker (`scripts/check_clawith_readiness.py`) uses only
`GET` requests. It does not issue `POST`, `PUT`, `PATCH`, `DELETE`, or any
other write-capable HTTP method. This is:

- enforced by code (only `urllib.request.Request(..., method="GET")` is used),
- asserted in tests (`test_phase_f.py::test_f004_non_destructive_guarantee`),
- documented here.

The existing `seed/probe_clawith.py` also uses only GET for its public checks.
Its optional login flow uses POST for `/api/auth/login`, but that is
credential-gated and opt-in — the readiness checker does not use it.

## Explicit non-claims

- **No native upstream Role Foundry parity.** `POST /api/roles`,
  `POST /api/scenarios`, and `PATCH /api/runs/{run_id}` are not present in
  upstream Clawith. They remain adapter-side assumptions.
- **No consumer OAuth inside Clawith.** Auth is token-based; no OAuth flow
  is wired.
- **Admin/model-pool presence is unknown without auth.** The readiness checker
  honestly reports `unknown` rather than guessing.
- **This is not a deployment guide.** It is a readiness probe and mapping
  reference.

## Relationship to existing docs

- `docs/clawith-integration.md` — full integration doc including live/demo
  mode details and the existing probe (`seed/probe_clawith.py`)
- `seed/probe_clawith.py` — the detailed HTTP+DB+source probe
- `scripts/check_clawith_readiness.py` — the Phase F readiness checker (this phase)

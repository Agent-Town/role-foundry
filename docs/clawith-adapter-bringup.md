# Clawith Adapter Bring-up — Seam-to-Upstream Mapping

## Why adapter-first

Role Foundry already has a small, working seam for roles, scenarios, runs, lineage,
and scorecards. Upstream Clawith is real software, but it does **not** natively expose
those same RF-specific contracts today.

The honest next step is **adapter-first**: keep the current RF seam stable, verify
upstream Clawith readiness via read-only probes, and build a narrow adapter around
the mismatch — not pretend parity.

## Guardrails

- **Do not edit `runner_bridge` core contracts** to fit today's upstream mismatch.
- **Do not rename the current RF seam** to native upstream Clawith.
- **Do not perform destructive writes** against upstream Clawith from probe tooling.
- **Prefer docs / spec / read-only scripts**; any helper code stays GET-only.

---

## Seam-to-upstream mapping matrix

Each row maps a Role Foundry seam concern to the audited upstream Clawith reality.

Allowed statuses per the forward spec (Phase F, F003):
- `matches` — upstream already provides the exact contract RF needs
- `adapter_needed` — RF has the seam; upstream has a different shape or no equivalent
- `missing_upstream` — upstream does not expose this concern at all today
- `blocked_by_auth` — upstream has the surface but it requires auth RF cannot provide yet
- `unknown` — not yet verified

| RF Seam Concern | RF Seam Contract | Upstream Clawith Reality | Status |
|---|---|---|---|
| Health / readiness | `GET /api/health` (compose assumes one service) | Upstream serves JSON health at `GET /api/health`; `/health` returns HTML app shell | `matches` |
| Auth registration surface | `GET /api/auth/registration-config` | Upstream exposes the same path and shape | `matches` |
| API version | `GET /api/version` | Upstream exposes the same path | `matches` |
| Auth login | `POST /api/auth/login` | Upstream exposes the same path (JWT response) | `matches` |
| Auth identity | `GET /api/auth/me` | Upstream exposes the same path (auth-gated) | `matches` |
| LLM providers | `GET /api/enterprise/llm-providers` | Upstream exposes the same path (auth-gated) | `blocked_by_auth` |
| LLM model pool | `GET /api/enterprise/llm-models` | Upstream exposes the same path (auth-gated); may be empty | `blocked_by_auth` |
| Admin / companies | `GET /api/admin/companies` | Upstream exposes the same path (platform_admin-gated) | `blocked_by_auth` |
| First admin bootstrap | First `POST /api/auth/register` becomes `platform_admin` | Upstream confirmed: first registered user gets `platform_admin` role | `adapter_needed` |
| Role seeding | `POST /api/roles` | No upstream `/api/roles` route or native `roles` table | `missing_upstream` |
| Scenario seeding | `POST /api/scenarios` with training/holdout semantics | No upstream `/api/scenarios` route or native scenario entity | `missing_upstream` |
| Run registration | `POST /api/runs` with RF fields (`run_id`, `status`, `dataset_manifest_id`, `flow`, `lineage`) | No upstream `/api/runs` route or native RF run schema | `missing_upstream` |
| Run lifecycle patching | `PATCH /api/runs/{run_id}` with `state_history`, `artifact_bundle_path`, `scorecard` | No upstream run-state endpoint with RF-specific fields | `missing_upstream` |
| Run fetch | `GET /api/runs/{run_id}` | No upstream native equivalent | `missing_upstream` |
| RF auth header | `Authorization: Bearer $CLAWITH_SECRET` | Upstream uses JWT user auth; gateway uses `X-Api-Key` | `adapter_needed` |
| Tenant context | Implicit / tenant-agnostic | Upstream has real default tenant + company flows | `adapter_needed` |
| Model execution prereqs | Implied by provider env vars | Upstream `llm_models` table; audited instance had 0 entries | `adapter_needed` |
| Agent / gateway execution | RF bridge uses `LocalReplayRunner`; no upstream agent dependency | Upstream has real `/api/gateway/*` with `X-Api-Key` | `adapter_needed` |
| Artifact redaction | `request.json` / `request.private.json` / `student-view.json` / `teacher-scorecard.json` | No upstream first-class primitive for RF redaction model | `missing_upstream` |

### RF-specific fields that must survive intact

These fields should **not** be watered down to fit today's upstream shape:

- `scenario_set_id`
- `dataset_manifest_id`
- `request_name`
- `flow`
- `lineage`
- `state_history`
- `transcript_path`
- `artifact_bundle_path`
- `scorecard`
- teacher-private vs student-safe artifact splits

If those survive intact through the adapter, the adapter lane is doing its job.

---

## Auth + config notes

| Topic | RF Seam Today | Upstream Reality | Decision |
|---|---|---|---|
| Base URL | Examples assume `:3000` | Audited upstream may use `:3008` or other port | Put actual URL in adapter config; do not assume port |
| Health endpoint | `/health` in compose checks | JSON health is `/api/health` upstream; `/health` may return HTML | Use `/api/health` only |
| Auth header | `Bearer $CLAWITH_SECRET` | JWT bearer for normal APIs; `X-Api-Key` for gateway | Keep RF bearer secret at adapter boundary |
| Secrets | `CLAWITH_SECRET` | Upstream cares about `SECRET_KEY`, `JWT_SECRET_KEY` | Keep these separate in docs |

---

## Read-only prereq check

Before any writes or admin creation, run the read-only prereq checker:

```bash
python3 scripts/check_clawith_adapter_prereqs.py --base-url http://localhost:3008
```

With an existing JWT token for authenticated checks:

```bash
python3 scripts/check_clawith_adapter_prereqs.py \
  --base-url http://localhost:3008 --token "$CLAWITH_JWT" --json
```

The checker covers six required categories:
1. base URL reachable
2. auth surface understood
3. admin presence known
4. model-pool presence known
5. endpoint mismatch documented
6. status output clearly categorized as ready/blocked/unknown

It uses **GET requests only** and performs no writes.

---

## Non-claims

This document does **not** claim:
- upstream Clawith already ships native RF roles/scenarios/runs APIs
- the current RF compose contract is a verified upstream deployment contract
- the audited local instance already has first admin or model-pool setup complete
- the Role Foundry web UI reads live upstream Clawith state today

That honesty is the whole point.

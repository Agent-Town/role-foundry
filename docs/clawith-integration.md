# Clawith Integration — Honest Probe Lane

## What Clawith is in this repo

Clawith is the external control plane Role Foundry can talk to in **live mode**.
It is a separate project and image. This repo does **not** bundle Clawith source,
and it does **not** claim native upstream support for Role Foundry roles,
scenarios, or run-patch contracts.

The practical fast lane is now:
1. keep demo mode first-class
2. bring up a real Clawith image
3. run a **read-only probe**
4. only then decide whether you need an adapter/shim for writes

For the smallest **real** Clawith + Claude/vibecosystem executor path, see `docs/clawith-vibecosystem-real-path.md`.

## Current state

| Concern | Honest status |
|---|---|
| Demo mode | Works now, no Clawith required |
| Live image wiring | Works behind `--profile live` |
| Health contract | `GET /api/health` on upstream Clawith |
| Public version/auth probe | `GET /api/version` and `GET /api/auth/registration-config` |
| Admin surface | Upstream exposes `/api/admin/companies` but it is auth-gated |
| Model pool surface | Upstream exposes `/api/enterprise/llm-models` but it is auth-gated |
| First admin bootstrap | First successful `/api/auth/register` becomes `platform_admin` |
| Native Role Foundry seed endpoints | **Not observed upstream** (`/api/roles`, `/api/scenarios`) |
| Native run patch endpoint | **Not observed upstream** (`PATCH /api/runs/{run_id}` remains adapter-side) |

## Demo mode (default)

```bash
docker compose up
```

This starts `role-foundry-web`, `postgres`, and `redis`.
The UI serves pre-baked data from `app/data.js`.
No Clawith image, no model keys, no bootstrap writes.

## Live mode (opt-in)

### Prerequisites

1. A Clawith Docker image
   - build your own: `docker build -t clawith:local /path/to/clawith`
   - or point `CLAWITH_IMAGE` at a registry image
2. A `.env` file with `CLAWITH_IMAGE` set
3. Optional LLM provider keys if you want Clawith-native agents

### Start the stack

```bash
cp .env.example .env
# edit .env and set CLAWITH_IMAGE

docker compose --profile live up
```

This adds two live-only services:
- **clawith** — the actual control plane on port 3000
- **bootstrap** — now a **read-only preflight probe**, not a destructive seed step

### Health check used by compose

```bash
curl http://localhost:3000/api/health
# Expected: 200 OK
```

That is the meaningful upstream health path.
`/health` is not the contract to trust here.

## Read-only probe commands

### Minimal HTTP probe

```bash
python3 seed/probe_clawith.py --base-url http://localhost:3000
```

This checks:
- `/api/health`
- `/api/version`
- `/api/auth/registration-config`
- unauthenticated behavior for `/api/auth/me`
- unauthenticated behavior for `/api/enterprise/llm-models`
- unauthenticated behavior for `/api/admin/companies`

### Better local probe against running Docker containers

If you have a local Clawith stack and know the container names, use:

```bash
python3 seed/probe_clawith.py \
  --base-url http://localhost:3008 \
  --backend-container clawith-backend-1 \
  --postgres-container clawith-postgres-1
```

That adds two useful read-only checks:
- pulls backend OpenAPI directly from `localhost:8000/openapi.json` **inside** the backend container
- runs read-only SQL counts inside Postgres to verify:
  - user count
  - `platform_admin` presence
  - `llm_models` presence
  - enabled model count

### Authenticated probe (optional)

If you already have a real user and want to inspect protected surfaces without using the UI:

```bash
python3 seed/probe_clawith.py \
  --base-url http://localhost:3000 \
  --username alice \
  --password 'your-password'
```

Or provide a bearer token directly:

```bash
CLAWITH_BEARER_TOKEN=... python3 seed/probe_clawith.py --base-url http://localhost:3000
```

That lets the probe read:
- `/api/auth/me`
- `/api/enterprise/llm-providers`
- `/api/enterprise/llm-models`
- `/api/admin/companies` (200 for `platform_admin`, 403 otherwise)

## How to read the probe output

The probe reports three separate truths:

1. **public upstream ready**
   - can we reach the real Clawith health/version/auth surface at all?
2. **adapter-first readiness**
   - do we actually have an admin and at least one model-pool entry?
3. **native Role Foundry parity**
   - does upstream already expose Role Foundry's role/scenario/run contracts?

Those are not the same thing.

A healthy result can still honestly say:
- Clawith is alive
- admin/model pool are missing or unknown
- Role Foundry still needs an adapter for roles/scenarios/run patches

Good. That is the truth.

## Local readiness gaps the probe is meant to catch

### 1) Auth surface is present, but admin may not exist yet

Upstream Clawith creates the first `platform_admin` during the **first successful registration**.
If the local database still has zero users, there is no admin yet.

### 2) Model pool may exist as schema only

Upstream stores native models in `llm_models`.
A healthy container can still be unusable for Clawith-native agents if that table is empty.

### 3) Endpoint mismatch is real

Role Foundry's older bring-up docs assumed:
- `POST /api/roles`
- `POST /api/scenarios`
- `PATCH /api/runs/{run_id}`

Those are **adapter-side assumptions**, not an upstream parity claim.
The probe calls that out explicitly.

### 4) `/health` is too weak / misleading

For the upstream image we tested, `/health` can be swallowed by the frontend and return HTML.
Use `/api/health` instead.

## What `seed/bootstrap.py` still means

`seed/bootstrap.py` still has value, but only for two narrow jobs:

1. validating the Role Foundry seed payload
2. showing the **legacy write plan** with `--dry-run`

It should **not** be read as proof that stock upstream Clawith natively accepts Role Foundry seed writes.
If you point `--seed` at a stock upstream instance, it now refuses the write when the legacy paths are absent.

## What live mode does **not** claim

- no native consumer OAuth inside Clawith
- no native upstream Role Foundry role/scenario API parity
- no claim that runner bridge patch endpoints already ship in upstream Clawith
- no destructive seed writes during the default compose live preflight

## Bottom line

Use live mode to verify **real upstream Clawith readiness**, not to fake it.

If the probe says:
- health is good
- auth surface is real
- admin exists
- model pool exists
- Role Foundry-native endpoints are still missing

then the next honest move is an **adapter/shim**, not wishful thinking.

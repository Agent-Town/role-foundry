# Clawith Integration — Honest Status

## What is Clawith?

Clawith is the control plane for agent orchestration, run registry, and evaluation storage. It is a separate project (`github.com/openclaw/clawith`) and is **not bundled in this repo**.

## Current state (Milestone 3)

| Component | Status |
|---|---|
| Docker Compose wiring | Done — profile-gated under `live` |
| Health check path | Documented: `GET /health` → 200 |
| Seed data model | Done — `seed/role-foundry-apprentice.json` |
| Bootstrap script | Done — `seed/bootstrap.py --validate` works now, `--seed` needs live Clawith |
| Demo mode | Default, no Clawith needed |
| Live mode | Requires a real Clawith image + config |

## How demo mode works (default)

```
docker compose up
```

This starts `role-foundry-web`, `postgres`, and `redis`. The web UI serves pre-baked data from `app/data.js`. No Clawith image, no API keys, no secrets needed.

## How live mode works (opt-in)

### Prerequisites

1. A Clawith Docker image. Either:
   - Build from source: `docker build -t clawith:local /path/to/clawith`
   - Pull from a registry: `docker pull ghcr.io/openclaw/clawith:latest`
2. Set `CLAWITH_IMAGE` in `.env` (defaults to `clawith:local`)
3. Optionally set LLM provider keys if you want Clawith-native agents

### Starting live mode

```bash
cp .env.example .env
# Edit .env: set CLAWITH_IMAGE, CLAWITH_SECRET, and any LLM keys

docker compose --profile live up
```

This adds two services:
- **clawith** — the control plane, listening on port 3000
- **bootstrap** — one-shot service that seeds the apprentice role + scenarios, then exits

### Bootstrap dependency order

```
postgres (healthy) → redis (healthy) → clawith (healthy) → bootstrap (runs once, exits)
```

The bootstrap service runs `seed/bootstrap.py --seed` against the Clawith API. It depends on Clawith being healthy first.

### Health check

```bash
curl http://localhost:3000/health
# Expected: 200 OK
```

The compose health check uses this endpoint. Bootstrap will not start until Clawith reports healthy.

### Seeding without Docker

You can also validate or seed manually:

```bash
# Validate seed data (no Clawith needed):
python3 seed/bootstrap.py --validate

# Dry-run against a running Clawith:
python3 seed/bootstrap.py --seed --dry-run

# Seed for real:
CLAWITH_SECRET=your-secret python3 seed/bootstrap.py --seed --clawith-url http://localhost:3000
```

## What live mode does NOT include

- **Consumer OAuth** — Clawith authenticates runners via machine-to-machine secrets, not user logins. See `docs/runner-bridge.md`.
- **Production hardening** — This is a hackathon stack, not a prod deployment.
- **Bundled Clawith source** — This repo does not contain or reference sibling `../Clawith` paths.

## Image contract

The compose file expects the Clawith image to:
1. Expose port 3000
2. Accept `DATABASE_URL` and `REDIS_URL` environment variables
3. Serve `GET /health` returning 200 when ready
4. Accept `POST /api/roles` and `POST /api/scenarios` for seeding

If the image does not exist or these contracts are not met, live mode will fail with clear errors. Demo mode is unaffected.

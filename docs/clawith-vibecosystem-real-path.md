# Clawith + vibecosystem — smallest real demo path

This is the honest lane that is already available locally without pretending stock upstream Clawith has native Claude-subscription model-pool parity.

## Ground truth

- **Clawith = control plane**
- **vibecosystem = Claude execution backend**
- **Claude app / Max subscription != Clawith model-pool credential**
- **stock upstream Clawith already has an external-agent gateway contract** via `/api/gateway/*`
- that gateway is currently labeled **OpenClaw** in the UI, but the real technical contract is just:
  - `GET /api/gateway/poll`
  - `POST /api/gateway/report`
  - `POST /api/gateway/send-message`
  - auth via `X-Api-Key`

That means the smallest honest path is:
1. bootstrap Clawith once
2. create a linked external agent in Clawith
3. run a tiny Claude/vibecosystem worker against the gateway

No fake native Clawith parity required.

## Local findings from the current machine

### Clawith at `http://localhost:3008`

Observed locally:
- `GET /api/health` → `200 {"status":"ok","version":"1.7.1"}`
- `GET /api/version` → `200 {"version":"1.7.1","commit":""}`
- `GET /api/auth/registration-config` → `{"invitation_code_required":false}`
- `GET /api/tenants/registration-config` → `{"allow_self_create_company":true}`

Observed in local Postgres:
- `users=0`
- `platform_admins=0`
- `tenants=1` (`Default` already exists)
- `llm_models=0`
- `enabled_models=0`
- `agents=0`

Implication:
- the stack is **up**
- the auth surface is **real**
- but the instance is still **unbootstrapped** from a human point of view because there is no admin user yet
- and the native Clawith model pool is **empty**

### vibecosystem / Claude Code on this machine

Observed locally:
- `claude auth status` reports `loggedIn: true`, `authMethod: claude.ai`, `subscriptionType: max`
- `claude agents` lists vibecosystem-style user agents such as `backend-dev`, `architect`, `ai-engineer`, etc.
- `~/.claude/settings.json` currently contains only a small env block; the vibecosystem hook bundle is **not** obviously wired in there

Implication:
- Claude Code is already authenticated and usable
- vibecosystem agent definitions are already available from the user Claude home
- for the imminent demo, the safest path is to **reuse the existing authenticated Claude home** rather than reinstalling or mutating machine-wide hooks right before showtime

### Important isolation note

A quick test with a fresh temporary `HOME` showed that simply copying `.claude.json` was **not enough** to preserve Claude login state.

Implication:
- a fully isolated Claude home is still a valid later lane
- but it is **not** the fastest reliable same-morning bring-up path unless we explicitly export/carry the real Claude auth material correctly

## Manual blocker you still have to do once

Clawith has **zero users** right now.

Per upstream auth code, the **first successful registration becomes `platform_admin`**.

### Shortest manual next step

Open `http://localhost:3008/login`, click **Register**, and create the first user with:
- username
- email
- password

That is the bootstrap gate.

After that, log in and continue below.

## Smallest real demo flow after first admin exists

### Option A — the real lane for this demo
Use Clawith only as the control plane and use Claude/vibecosystem as the external executor.

1. In Clawith, create a new agent.
2. Choose **Link OpenClaw** (Lab).
3. Give it a name/description.
4. Copy the one-time API key shown by Clawith.
5. Run the worker from this repo:

```bash
python3 scripts/clawith_vibe_once.py \
  --base-url http://localhost:3008 \
  --api-key 'oc-REDACTED' \
  --claude-agent backend-dev \
  --workdir "$PWD" \
  --permission-mode bypassPermissions
```

What this does:
- polls Clawith for pending messages
- hands the message + history to Claude Code using the selected vibecosystem agent
- reports the reply back to Clawith
- stores receipts under `artifacts/clawith-gateway/<timestamp>/`

Why this is honest:
- Clawith is still the boss / inbox / identity layer
- vibecosystem is only the Claude execution path
- no one is pretending the Claude Max subscription magically created a Clawith-native model pool

### Option B — native Clawith agents
If you want **Clawith-native** hosted agents instead, you still need to add at least one model in:
- **Enterprise Settings → Model Pool**

That requires a real provider API key in Clawith, for example an Anthropic API key.

Again: your Claude app / Max subscription does **not** fill this model pool automatically.

## What this repo now adds

`scripts/clawith_vibe_once.py`
- one-shot gateway worker
- project-local receipts
- no `runner_bridge` churn
- uses Claude Code + vibecosystem agent selection directly

This is intentionally small. It is a demo bring-up seam, not a full production worker.

## What is still not claimed

This path does **not** claim:
- native upstream Role Foundry role/scenario API parity inside Clawith
- native Clawith consumption of Claude app subscriptions as model-pool credentials
- broad unattended runtime hardening
- evaluation-integrity isolation for vibecosystem memory/hook behavior

## Recommended next implementation lane after the demo

Build a thin, explicit **`claude_vibecosystem` runner backend** for Role Foundry that:
- shells out to Claude Code in a dedicated workdir
- selects a curated vibecosystem agent per role
- records prompts/results/artifacts deterministically
- keeps Clawith as the control-plane / operator layer only

Do **not** start with broad `runner_bridge` redesign.
Start with the same narrow contract proven by `scripts/clawith_vibe_once.py`, then formalize it.

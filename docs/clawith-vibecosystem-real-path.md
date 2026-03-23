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

Observed CLI edge on this machine:
- Claude Code `2.1.79` in `--print` mode was flaky when the prompt was passed as a positional argv value from Python `subprocess.run(...)`
- the failure mode was ugly and misleading: a contextual prompt could exit `0` with empty stdout, while a simpler fallback prompt could error with `Input must be provided either through stdin or as a prompt argument`
- the narrow fix for this lane is to pass the prompt on **stdin** instead; that produced the real roundtrip reply in the same environment

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

## Automated "Link OpenClaw" agent setup

`scripts/clawith_link_openclaw.py` idempotently creates (or finds) an OpenClaw agent in Clawith via its real API and saves the gateway key to `runtime/clawith_openclaw_key.json` under the repo root (gitignored).

```bash
# Create/find the agent and save the key (defaults: localhost:3008, user robin)
# If CLAWITH_PASSWORD is not set, the script will prompt for it.
python3 scripts/clawith_link_openclaw.py

# Non-interactive auth via env vars
CLAWITH_PASSWORD=hackathon123 python3 scripts/clawith_link_openclaw.py

# Reuse an existing bearer token instead of logging in again
CLAWITH_TOKEN=... python3 scripts/clawith_link_openclaw.py

# Custom name or different creds
python3 scripts/clawith_link_openclaw.py --agent-name my-bot --username admin --password secret
```

API endpoints used:
- `POST /api/auth/login` — authenticate (unless a bearer token is supplied)
- `GET  /api/agents/` — find existing agents
- `POST /api/agents/` with `agent_type=openclaw` — create linked agent
- `POST /api/agents/{id}/api-key` — regenerate key for an existing linked agent
- `POST /api/gateway/heartbeat` — validate a saved gateway key without disturbing inbox delivery

Idempotency: if the named openclaw agent already exists and the saved key still validates, the key is reused. If the saved key is missing or stale, a new one is generated via the API and written back to `runtime/`.

Then run the gateway worker with the saved key:

```bash
python3 scripts/clawith_vibe_once.py \
  --api-key "$(jq -r .api_key runtime/clawith_openclaw_key.json)" \
  --base-url http://localhost:3008 \
  --claude-agent backend-dev \
  --workdir "$PWD"
```

To queue a real web-chat message into that linked agent without clicking around in the UI, use the same authenticated websocket path the Clawith frontend uses:

```bash
/Users/robin/.nvm/versions/node/v24.14.0/bin/node scripts/clawith_ws_roundtrip.js \
  --base-url http://localhost:3008 \
  --token-file runtime/clawith_bearer_token.txt \
  --agent-name vibecosystem-adapter \
  --message "Give me a 2-bullet summary of this repo and mention one Clawith integration constraint."
```

That script:
- creates a fresh Clawith chat session via `POST /api/agents/{id}/sessions`
- sends the user message over `/ws/chat/{agent_id}` with the bearer token
- waits for the OpenClaw placeholder and the final assistant reply
- saves session + websocket receipts under `artifacts/clawith-roundtrip/<timestamp>/`

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

`scripts/clawith_link_openclaw.py`
- idempotent agent creation via Clawith API (adapter-first, no native parity claims)
- saves gateway key to `runtime/` (gitignored)

`scripts/clawith_vibe_once.py`
- one-shot gateway worker
- project-local receipts
- no `runner_bridge` churn
- uses Claude Code + vibecosystem agent selection directly

`scripts/clawith_ws_roundtrip.js`
- queues a real user-side Clawith web-chat message over the stock websocket path
- creates an isolated session and saves transcript receipts
- verifies the final assistant reply is visible back through Clawith session APIs

This is intentionally small. It is a demo bring-up seam, not a full production worker.

## Rescue-proof capture referenced by submission packaging

One honest real roundtrip was captured and is now indexed for submission review in `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`.

Tracked proof index:
- `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`

Local referenced receipt roots (not committed in this packaging pass):
- `artifacts/clawith-roundtrip/rescue-proof/20260323T025241Z/`
- `artifacts/clawith-gateway/rescue-proof/20260323T025254Z/`

Required final reply markers from the proof:
- `REAL_GATEWAY_ROUNDTRIP_OK_20260323_0958Z`
- `CLAWITH_CONTROL_PLANE_VIBECOSYSTEM_EXECUTOR`

Claim boundary for this proof:
- it proves the **external gateway + Claude/vibecosystem executor lane**
- it does **not** prove native Clawith model-pool parity
- it does **not** prove sealed, tamper-proof, or independently certified evaluation

## What is still not claimed

This path does **not** claim:
- native upstream Role Foundry role/scenario API parity inside Clawith
- native Clawith consumption of Claude app subscriptions as model-pool credentials
- broad unattended runtime hardening
- evaluation-integrity isolation for vibecosystem memory/hook behavior

## Current beta seam after the demo proof

Role Foundry now carries a thin, explicit **`claude_vibecosystem` runner backend** beta seam for inspection:
- select it with `python3 -m runner_bridge.cli --packet A001 --runner-backend claude_vibecosystem`
- the run object records `execution_backend: "claude_vibecosystem"`
- the run object and private request can carry an `execution_backend_contract` block with executor mode + claim boundary
- the backend stub writes `execution_honesty` and provenance surfaces without invoking live Claude/network work in tests
- public-safe artifact/receipt exports can preserve that seam via `artifact-bundle.json` backend fields, receipt `execution_backend` blocks, and alpha `sealing_receipt.execution_backend` summaries when present

What this beta seam does **not** do yet:
- it does not shell out to Claude Code for live execution
- it does not create independent executor isolation
- it does not create sealed evaluation or tamper-proofing
- it does not create native Clawith model-pool parity

That is deliberate. This formalizes the same narrow contract proven by `scripts/clawith_vibe_once.py` without broad `runner_bridge` redesign.

## Recommended next implementation lane after this beta seam

Upgrade the stub into a live adapter that:
- shells out to Claude Code in a dedicated workdir
- selects a curated vibecosystem agent per role
- records prompts/results/artifacts deterministically
- keeps Clawith as the control-plane / operator layer only

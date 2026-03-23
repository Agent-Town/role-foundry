# Clawith Round-Trip Proof Capture

## What the helper captures

`scripts/capture_clawith_roundtrip_proof.py` packages locally available evidence
into a timestamped `proof-bundles/<timestamp>/` directory with a `manifest.json`
that explicitly marks what is present and what is missing.

### The five proof items

| # | Proof Item | Manifest key | Source | Required |
|---|-----------|-------------|--------|----------|
| 1 | **Queued task / inbound work** | `inbound_task` | `artifacts/clawith-gateway/<run>/` (message.json) | Yes |
| 2 | **Linked OpenClaw agent identity** | `agent_identity_linked` | `runtime/clawith_openclaw_key.json` (redacted) | Yes |
| 3 | **Worker pickup / execution evidence** | `worker_execution` | `scripts/clawith_vibe_once.py` snapshot + claude stdout/stderr | Yes |
| 4 | **Response/result back in Clawith** | `result_in_clawith` | Clawith API reads (agent detail, gateway-messages, session messages) | Yes |
| 5 | **Receipts / screenshot bundle** | `screenshot_bundle` | User-supplied `--screenshots-dir` | Yes |

### Clawith API endpoints used (when authenticated)

When `--base-url` and `--token` are provided, the helper fetches:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Confirm Clawith is running |
| `GET /api/agents/` | List all agents |
| `GET /api/agents/{agent_id}` | Agent detail (agent_id inferred from key file) |
| `GET /api/agents/{agent_id}/gateway-messages` | Messages routed through the gateway |
| `GET /api/agents/{agent_id}/sessions?scope=all` | All sessions for the agent |
| `GET /api/agents/{agent_id}/sessions/{session_id}/messages` | Messages in a specific session |

The `session_id` is inferred from `conversation_id` in gateway `message.json` artifacts
when available; otherwise the latest session from the sessions list is used (noted
honestly in the manifest).

### What it does NOT capture

- No fabricated screenshots — only copies user-supplied files.
- No invented API responses.
- No native Clawith model-pool parity claims.
- It will not fill in a missing piece with a guess.
- Missing screenshots or missing Clawith session evidence are explicitly marked MISSING.

### Secret redaction

All JSON files copied into the bundle are redacted: gateway keys (`oc-*`),
bearer tokens, JWTs, and API key prefixes are replaced with `REDACTED`.

## Ready-to-run checklist

```
[ ] 1. Clawith is running (http://localhost:3008/api/health → 200)
[ ] 2. Admin user exists (first registration creates platform_admin)
[ ] 3. Linked OpenClaw agent created:
        python3 scripts/clawith_link_openclaw.py
[ ] 4. Inbound message exists in Clawith (send one via UI or API)
[ ] 5. Gateway worker has run at least once:
        python3 scripts/clawith_vibe_once.py \
          --api-key "$(jq -r .api_key runtime/clawith_openclaw_key.json)" \
          --base-url http://localhost:3008 \
          --claude-agent backend-dev \
          --workdir "$PWD"
[ ] 6. Capture the proof bundle:
        python3 scripts/capture_clawith_roundtrip_proof.py
[ ] 7. (Optional) Include live API state:
        python3 scripts/capture_clawith_roundtrip_proof.py \
          --base-url http://localhost:3008 \
          --token "$CLAWITH_TOKEN"
[ ] 8. (Optional) Include screenshots:
        python3 scripts/capture_clawith_roundtrip_proof.py \
          --screenshots-dir ~/Desktop/clawith-screenshots
[ ] 9. Inspect proof-bundles/<timestamp>/SUMMARY.txt
```

## Remaining dependencies for a full live bundle

The helper works right now for packaging whatever exists locally.
For a **complete** 5/5 proof bundle you still need:

1. **A real inbound message/session in Clawith** — someone (human or API caller)
   must send a message to the linked agent so `clawith_vibe_once.py` has work to do.
2. **At least one successful gateway worker run** — the `artifacts/clawith-gateway/`
   directory must contain poll + message + prompt + result files from that run.
3. **Any real screenshot files you want judges to inspect** — the helper only copies
   files you supply via `--screenshots-dir`; it will not invent them.

Optional but useful:
- **Authenticated Clawith read access** — a bearer token that can read `/api/agents/`
  and session/message endpoints, so the bundle can include Clawith-side state in addition
  to the local `report.json` receipt.

Without item 1, the gateway worker will report "no pending messages" and the
proof bundle will mark gateway artifacts as MISSING.

## Output structure

```
proof-bundles/<timestamp>/
  manifest.json           # machine-readable evidence index (version 2)
  SUMMARY.txt             # human-readable status with five proof items
  agent-identity.json     # redacted linked-agent key metadata
  worker-script-snapshot.py
  gateway-artifacts/      # copied from artifacts/clawith-gateway/<run>/
    poll.json
    01_<msg_id>/
      message.json
      prompt.txt
      claude.stdout.txt
      claude.stderr.txt
      report.json
  clawith-api/            # optional live API reads
    health.json
    agents.json
    agent-detail.json     # GET /api/agents/{agent_id}
    gateway-messages.json # GET /api/agents/{agent_id}/gateway-messages
    sessions.json         # GET /api/agents/{agent_id}/sessions?scope=all
    session-messages.json # GET /api/agents/{agent_id}/sessions/{session_id}/messages
  screenshots/            # user-supplied screenshots (--screenshots-dir)
    step1.png
    step2.png
```

## Testing

```bash
python3 -m pytest tests/test_roundtrip_proof_capture.py -v
```

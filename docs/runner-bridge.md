# Runner Bridge — Hackathon Fast Path

## The problem

Role Foundry needs to dispatch agent runs (teacher evaluations, student training iterations, critic reviews) to LLM backends. Clawith is the control plane, but:

1. **Clawith does not natively support consumer OAuth or subscription-based auth.** It manages API-level provider credentials and model pools for its own native agents.
2. **Building a full OAuth/subscription layer into Clawith for the hackathon is not realistic** and would distort the core product work.

## The bridge

Instead of pretending Clawith has consumer auth, we use a **runner-bridge** pattern:

```
User (demo UI or operator)
  → Role Foundry Web (defines role, curates scenarios)
  → Clawith API (creates run records, manages state)
  → Runner Adapter (dispatches to actual LLM backend)
     ├── ClaudeVibeRunner (Claude Code + vibecosystem)
     ├── CodexRunner (OpenAI Codex API)
     └── ScriptRunner (deterministic checks)
```

### How auth works in this model

- **Clawith** authenticates runner adapters using its own secret (`CLAWITH_SECRET`). This is machine-to-machine, not consumer auth.
- **LLM providers** are authenticated using API keys stored in Clawith's model pool or passed as environment variables to runners.
- **The demo UI** doesn't need auth at all — it serves pre-baked data.
- **The operator** (Robin + Neo) triggers live runs through Clawith's API or CLI, not through a consumer login flow.

### What this means for the hackathon

- No login screen, no OAuth flow, no subscription check
- The demo UI works without any backend
- Live mode requires operator access to Clawith (API key or CLI)
- Partner-track identity (ERC-8004, ENS, Self) attaches to agent identities and run artifacts, not to a consumer auth session

## Why native OAuth-in-Clawith is postponed

| Reason | Detail |
|---|---|
| Scope | OAuth + session management + subscription logic is a full feature, not a hackathon hack |
| Risk | Half-built auth is worse than no auth — it creates false security claims |
| Honesty | The submission metadata should describe the real stack, not a fake auth layer |
| Priority | The core product value is the evaluation loop, not the login screen |

## When to revisit

Native consumer auth makes sense when:
- Role Foundry moves beyond operator-only usage
- There's a real need for per-user isolation and billing
- Clawith upstream adds OAuth support, or we build it properly

That's a post-hackathon concern.

## Runner adapter contract

Each runner adapter implements a minimal interface:

```
Input:
  - run_id (from Clawith)
  - agent_role (teacher | student | critic | verifier)
  - scenario_set_id
  - workspace_snapshot
  - time_budget
  - cost_budget

Output:
  - status (completed | failed | timeout)
  - transcript_path
  - artifact_bundle_path
  - scorecard (if evaluator role)
  - machine_score
```

The adapter is responsible for LLM auth, sandboxing, and artifact collection. Clawith is responsible for run lifecycle, state, and evaluation aggregation.

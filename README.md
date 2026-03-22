# Role Foundry

Role Foundry is training its own first apprentice.

The current demo is not a generic “AI agent” playground. It is a judge-facing dogfood vertical where **Robin + Neo** teach a **Frontend Apprentice** to implement small, visible **Role Foundry product slices** under hidden-eval review.

That makes the core claim legible:
- there is a named student
- there are named teachers
- there is a public curriculum
- there is a sealed holdout exam
- there are visible score deltas between runs
- there are receipts judges can inspect

## What judges see in this demo

`docker compose up` serves a static demo with pre-baked data that shows:

1. **Apprentice definition** — the Frontend Apprentice is learning to build Role Foundry itself
2. **Public curriculum** — visible training slices like rewriting the apprentice story, clarifying curriculum vs holdouts, exposing score deltas, and adding proof bundles
3. **Sealed holdouts** — hidden-eval categories that test whether the apprentice keeps demo mode honest and avoids leaking the exam
4. **Two judged runs** — Run 2 clearly improves over Run 1
5. **Failure → curriculum loop** — failures become the next public teaching themes without exposing hidden prompts
6. **Proof bundle** — receipt summary, changed files, policy snapshot, and transcript excerpt

This is the point of Role Foundry: make capability visible with honest evaluation instead of vibes.

## The current vertical

**Name:** Frontend Apprentice  
**Job:** Ship coherent, judge-facing Role Foundry product slices  
**Teachers:** Robin + Neo  
**Constraints:** standalone repo, demo mode first, no auth, no Privy, no fake live integrations

## How the loop works

1. **Teachers define the apprentice** — what a good Role Foundry slice looks like
2. **Role Foundry publishes public curriculum** — scenarios the apprentice can practice on
3. **Role Foundry seals hidden holdouts** — separate judge-only tests the apprentice never sees during training
4. **The apprentice ships a slice** — copy, UI, scorecard, or artifact surface
5. **Teacher judges the run** — scorecard shows public and hidden performance
6. **Failures become curriculum** — only the failure themes are promoted, never the hidden prompt text

## Why this demo reads stronger now

The old generic customer-support-style demo had the right skeleton, but it did not prove why the system matters.

The current version is stronger because it is:
- **narrower** — one concrete apprentice instead of a generic role demo
- **more honest** — demo mode stays demo mode; no fake Clawith/OAuth theater
- **more judgeable** — holdout integrity, score deltas, and receipts are explicit
- **more dogfood** — Role Foundry is being used to train a builder for Role Foundry itself

## Demo mode vs live mode

| | Demo mode | Live mode |
|---|---|---|
| **What runs** | Static UI with pre-baked apprentice data | Real Clawith control plane + runner backends |
| **Requirements** | Docker (web container + local services) | Docker + Clawith image + model credentials |
| **Good for** | Judges, walkthroughs, design review | Actual training and evaluation |
| **Current status** | Shipping now | Opt-in via `docker compose --profile live up` |

## Local quickstart

```bash
cp .env.example .env
docker compose up
open http://localhost:8080
```

This starts the static web demo plus Postgres and Redis.

To start **live mode** (requires an external Clawith image):

```bash
docker compose --profile live up
```

See `docs/clawith-integration.md` for prerequisites and the full integration guide.

## What is still stubbed

This repo is intentionally honest about what is not wired yet:
- the **web app still serves demo data** — it does not read from a live Clawith API
- no real runner dispatch (see `docs/runner-bridge.md` for the intended bridge)
- no auth, no Privy, no fake consumer OAuth path
- no live artifact viewer backed by run storage

Live mode starts and seeds a real Clawith control plane, but the web UI does not consume it yet. That is deliberate. The demo is first-class and judge-friendly on its own.

## Where Clawith fits

[Clawith](https://github.com/openclaw/clawith) is the live control plane. It is profile-gated in `docker-compose.yml` and can be started with `--profile live`. In the full system it owns:
- agent registry
- run registry
- scenario and holdout storage
- evaluation store and scorecards
- approvals, scheduling, and audit trails

For the hackathon MVP, Clawith integration is wired at the Docker layer but the web UI does not consume it yet. See `docs/runner-bridge.md` for the intended bridge pattern and `docs/clawith-integration.md` for live-mode setup.

## Execution backends

| Runner | Role | Why |
|---|---|---|
| Claude + vibecosystem | Student / builder | Strong for implementation-heavy slices |
| Codex | Teacher / critic / evaluator | Independent model family for judging |
| Deterministic scripts | Verifier | Cheap pass/fail checks |

Using different model families for building and judging reduces correlated self-grading.

## Docs

- `docs/v1-mvp-plan.md` — build slices
- `docs/clawith-integration.md` — live-mode setup, prerequisites, image contract
- `docs/runner-bridge.md` — bridge path and explicit auth deferral
- `docs/conversation-log.md` — curated build log for the submission
- `docs/agent-town-connection.md` — Agent Town relationship
- `docs/synthesis-hackathon-ideation.md` — ideation and ranking
- `docs/synthesis-hackathon-stack-architecture.md` — architecture notes

## License

GPL-3.0

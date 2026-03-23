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
5. **Teacher scorecard** — per-scenario teacher notes plus aggregate score across public curriculum and sealed holdouts
6. **Failure → curriculum loop** — failed holdouts become the next public teaching themes without exposing hidden prompts
7. **Iteration history** — score deltas over time stay visible in both the UI and stored run data
8. **Proof bundle** — receipt summary, changed files, policy snapshot, and transcript excerpt

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
5. **Teacher judges the run** — a teacher scorecard records per-scenario notes plus an aggregate score
6. **Failures become curriculum** — only the failure themes are promoted, never the hidden prompt text
7. **Iteration history records deltas** — later runs show what improved overall and on sealed holdouts

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
| **What runs** | Static UI with pre-baked apprentice data | Configured read-only browser shell + optional Clawith / runner-bridge receipts |
| **Requirements** | Docker (web container + local services) | `liveDataUrl` export for the browser shell; add Clawith image + model credentials for actual runs |
| **Good for** | Judges, walkthroughs, design review | Inspecting exported run state honestly, then actual training / evaluation once the backend is wired |
| **Current status** | Shipping now | Browser shell now consumes configured exports; native live storage/browser fan-out is still pending |

## Local quickstart

```bash
cp .env.example .env
docker compose up
open http://localhost:8080
```

This starts the static web demo plus Postgres and Redis.

To exercise the **browser live shell** against the committed alpha-loop sample:

```text
http://localhost:8080/?mode=live&liveDataUrl=live-read-model.alpha-loop.sample.json
```

To start the optional backend-side **live mode** (requires an external Clawith image):

```bash
docker compose --profile live up
```

See `docs/clawith-integration.md` for prerequisites and the full integration guide.

## First live run

The first honest runner-bridge slice is now in the repo. It is intentionally small:
- `python3 -m runner_bridge.cli` drives one run lifecycle
- `LocalReplayRunner` is the zero-secret backend that writes a transcript and artifact bundle
- optional `teacher_evaluation` input produces a teacher scorecard, public curriculum themes, and iteration history deltas
- the bridge stores a redacted `request.json` plus a raw `request.private.json` so sealed holdout prompts stay out of student-facing artifacts
- the bridge also emits a receipt provenance pack (`receipts/manifest.json`, baseline/candidate/evaluation exports, `receipts/evidence-index.json`, and `receipts/summary.md`) so judges can trace a run back to its source artifacts without changing the scoring semantics
- if you pass `--clawith-url`, the bridge patches run state into a Clawith-compatible control plane
- if you omit `--clawith-url`, you can still exercise the artifact/transcript contract locally

Examples:

```bash
python3 -m runner_bridge.cli \
  --request runner_bridge/examples/first-live-run.json \
  --clawith-url http://localhost:3000 \
  --clawith-secret "$CLAWITH_SECRET"
```

```bash
python3 -m runner_bridge.cli \
  --request runner_bridge/examples/teacher-eval-loop.json \
  --clawith-url http://localhost:3000 \
  --clawith-secret "$CLAWITH_SECRET"
```

Artifacts land under `runtime/runs/<run_id>/`.

See `docs/runner-bridge.md` for the control-plane patch contract, teacher scorecard extension, and the local/mockable fallback path.

## What is still stubbed

This repo is intentionally honest about what is not wired yet:
- the browser **live shell is read-only** — it consumes configured exports / receipts, but it does not chase native run storage or claim upstream Clawith parity
- only one **local/mockable runner path** is implemented today (`LocalReplayRunner`); teacher scorecards and iteration history are real contracts, but Claude/Codex-backed adapters still need wiring
- the committed alpha-loop browser fixture is a **sample/read-model export**, not proof that a fully real baseline → candidate → teacher-eval loop has already executed end to end on this branch
- no auth, no Privy, no fake consumer OAuth path
- no live artifact viewer backed by run storage fan-out

Live mode can now seed Clawith, drive bridge-mediated runs, and the browser shell can consume configured read-model / alpha-loop exports. That is still deliberately narrow. Demo mode remains first-class and judge-friendly on its own.

## Where Clawith fits

[Clawith](https://github.com/openclaw/clawith) is the live control plane. It is profile-gated in `docker-compose.yml` and can be started with `--profile live`. In the full system it owns:
- agent registry
- run registry
- scenario and holdout storage
- evaluation store and scorecards
- approvals, scheduling, and audit trails

For the hackathon MVP, Clawith integration is wired at the Docker layer and the browser now has a narrow read-only shell for configured exports. It still does not claim native upstream parity or full live artifact browsing. See `docs/runner-bridge.md` for the bridge pattern and `docs/clawith-integration.md` for live-mode setup.

## Execution backends

| Runner | Role | Why |
|---|---|---|
| Claude + vibecosystem | Student / builder | Strong for implementation-heavy slices |
| Codex | Teacher / critic / evaluator | Independent model family for judging |
| Deterministic scripts | Verifier | Cheap pass/fail checks |

Using different model families for building and judging reduces correlated self-grading.

## Docs

- `docs/milestones.md` — spec-first milestone rail and current delivery status
- `docs/v1-mvp-plan.md` — build slices
- `docs/clawith-integration.md` — live-mode setup, prerequisites, image contract, and read-only probe lane
- `docs/runner-bridge.md` — bridge path, teacher evaluation contract, and explicit auth deferral
- `docs/public-benchmark-pack-v1.md` — public-safe benchmark pack scope and blocked families
- `docs/conversation-log.md` — curated build log for the submission
- `docs/agent-town-connection.md` — Agent Town relationship
- `docs/synthesis-hackathon-ideation.md` — ideation and ranking
- `docs/synthesis-hackathon-stack-architecture.md` — architecture notes

## Supporting specs

- `specs/008-public-benchmark-pack-v1.md` — public benchmark pack contract for the current alpha spine
- `specs/009-clawith-readiness-probe.md` — adapter-first upstream readiness probe
- `specs/010-live-ui-read-model.md` — read-only browser adapter for configured live/read-model exports
- `specs/014-frontend-product-engineer-20-task-curriculum.md` — TDD-first 20-task curriculum contract for the first Frontend/Product Engineer apprentice

## License

GPL-3.0

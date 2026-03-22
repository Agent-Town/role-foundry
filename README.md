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

## Judge inspection path

If you want the fastest honest walkthrough:

1. Run `python3 -m pytest tests/ -v` to verify the repo contracts.
2. Run `docker compose up` and inspect `http://localhost:8080`.
3. Read `docs/submission-proof-checklist.md` and `docs/conversation-log.md` for the curated build story and non-claims.
4. Optionally run `python3 -m runner_bridge.cli --request runner_bridge/examples/first-live-run.json` to exercise the zero-secret receipt path locally.
5. If Claude Code is installed and authenticated, optionally run `python3 -m runner_bridge.cli --backend claude-vibe --request runner_bridge/examples/claude-vibe-smoke.json` to exercise the new project-local Claude student path without touching global `~/.claude/settings.json`.

## First live run

The first honest runner-bridge slice is now in the repo. It is intentionally small:
- `python3 -m runner_bridge.cli` drives one run lifecycle
- `LocalReplayRunner` remains the zero-secret backend that writes a transcript and artifact bundle
- `ClaudeVibeRunner` is now available as an opt-in backend (`--backend claude-vibe`) for **student/builder** runs through the local `claude` CLI
- the Claude path uses a **project-local** profile under `.claude/` (`.claude/agents/role-foundry-student.md` + `.claude/templates/role-foundry-student-run.md`) and `--setting-sources project`, so it does not depend on or modify global `~/.claude/settings.json`
- optional `teacher_evaluation` input still produces a teacher scorecard, public curriculum themes, and iteration history deltas on the deterministic local path
- the bridge stores a redacted `request.json` plus a raw `request.private.json` so sealed holdout prompts stay out of student-facing artifacts
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

```bash
python3 -m runner_bridge.cli \
  --backend claude-vibe \
  --request runner_bridge/examples/claude-vibe-smoke.json
```

Artifacts land under `runtime/runs/<run_id>/`.

See `docs/runner-bridge.md` for the control-plane patch contract, teacher scorecard extension, the project-local Claude adapter, and the local/mockable fallback path.

## What is still stubbed

This repo is intentionally honest about what is not wired yet:
- the **web app still serves demo data** — it does not read from a live Clawith API
- `ClaudeVibeRunner` is a **narrow shell adapter**, not a full dogfood loop yet: it can launch a real Claude student run through the bridge and leave receipts, but teacher/evaluator model wiring still lives on the deterministic local path and Codex-backed judging is still future work
- no auth, no Privy, no fake consumer OAuth path
- no live artifact viewer backed by run storage

Live mode can now seed Clawith and drive one bridge-mediated run, but the web UI still does not consume live state. That is deliberate. The demo remains first-class and judge-friendly on its own.

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
| ClaudeVibeRunner (Claude + project-local vibecosystem profile) | Student / builder | Real Claude CLI execution path for repo-local student runs without global hook changes |
| Codex | Teacher / critic / evaluator | Independent model family for judging |
| Deterministic scripts | Verifier | Cheap pass/fail checks |

Using different model families for building and judging reduces correlated self-grading.

## Docs

- `docs/v1-mvp-plan.md` — build slices
- `docs/clawith-integration.md` — live-mode setup, prerequisites, image contract
- `docs/runner-bridge.md` — bridge path and explicit auth deferral
- `docs/conversation-log.md` — curated build log for the submission
- `docs/submission-proof-checklist.md` — judge walkthrough and claim checklist
- `docs/agent-town-connection.md` — Agent Town relationship
- `docs/synthesis-hackathon-ideation.md` — ideation and ranking
- `docs/synthesis-hackathon-stack-architecture.md` — architecture notes

## License

GPL-3.0

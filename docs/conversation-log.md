# Conversation Log

_Curated build log for Synthesis hackathon submission._

This log captures the key decisions, not every message. It exists because the Synthesis submission values honest `conversationLog` and build history.

---

## 2026-03-22 — Direction lock

**Decision:** Build Role Foundry as the hackathon submission.

**Context:** Evaluated 10 concepts across partner-track fit, technical depth, and demo clarity. Role Foundry (teacher/student agent training with hidden holdout evaluation) ranked #1 because:
- The evaluation loop is non-trivial and produces real evidence
- Hidden holdouts make quality claims credible instead of vibes-based
- It naturally produces scorecards, artifact bundles, and conversation logs that match what the submission format rewards
- It stacks 6-8 partner tracks without shallow integration

**Rejected alternatives:** AutoFounder (#2), YieldOS (#3), Agent Desk (#4). See `docs/synthesis-hackathon-ideation.md` for full ranking.

---

## 2026-03-22 — Architecture lock

**Decision:** One Clawith instance as control plane. No nested Clawith stacks.

**Key choices:**
- Clawith = control plane (agent registry, run registry, evaluation store)
- Claude + vibecosystem = student/builder execution backend
- Codex = teacher/critic/evaluator backend (different model family to avoid self-congratulatory grading)
- Claw3D = visualization layer (viewer, not source of truth)
- Per-run isolation is non-negotiable for holdout integrity

See `docs/synthesis-hackathon-stack-architecture.md` for details.

---

## 2026-03-22 — Wallet and auth stance

**Decision:** Bring-your-own-wallet for hackathon. No Privy dependency.

**Why:** Portal onboarding (especially the mass-adoption wallet path) is still flaky. Wrong dependency for a hackathon-critical core loop.

**Decision:** No consumer OAuth through Clawith for the hackathon.

**Why:** Clawith doesn't natively support consumer OAuth subscriptions. Rather than fake it, we use a runner-bridge pattern. See `docs/runner-bridge.md`.

---

## 2026-03-22 — Scaffold created

**What shipped:**
- Demo UI (static HTML/JS) with pre-baked example data for roles, scenarios, runs, and scorecards
- Docker Compose stack (web + postgres + redis, Clawith stubbed)
- Documentation suite (ideation, architecture, connection strategy)
- README rewritten for hackathon clarity

**What's stubbed:**
- Clawith service (needs image)
- Bootstrap/seed service
- Live mode (needs Clawith + LLM keys)

---

## 2026-03-22 — Spec-first milestone rail added

**Decision:** Move the repo to milestone-driven, spec-first execution so work can continue cleanly without Robin being online.

**What changed:**
- Added `docs/milestones.md` as the ordered hackathon roadmap
- Added `specs/001`–`specs/007` to define milestone contracts and acceptance criteria
- Added `tests/test_demo_contract.py` so the current demo shell has an executable baseline contract

**Why:** The hackathon is moving too fast for vague TODOs. Each slice now needs a written spec, explicit acceptance criteria, and a runnable check before later slices build on top of it.

**GitHub tracking:** Repo milestones `M1`–`M6` were created along with issues #1–#7 so the hackathon roadmap is public and inspectable.

---

## 2026-03-22 — Milestones 1 and 2 landed

**Outcome:**
- Milestone 1 (spec backbone + demo contract) is now in the repo with executable tests.
- Milestone 2 (Frontend Apprentice vertical) is now committed as the first coherent judge-facing product slice.

**Evidence:**
- `tests/test_demo_contract.py` passes
- app pages now show the apprentice story, sealed holdouts, proof bundle, score deltas, and failure-to-curriculum loop
- GitHub history now includes milestone/spec commits rather than only ideation docs

---

## 2026-03-22 — Milestone 3 landed

**Outcome:** Clawith compose integration and seed data model are in the repo.

**What shipped:**
- `docker-compose.yml` now has a real `clawith` service behind the `live` profile, with health check and dependency ordering
- `bootstrap` service seeds one role and scenario set through `seed/bootstrap.py`
- `seed/role-foundry-apprentice.json` defines the Frontend Apprentice role with 6+ training and 3+ holdout scenarios
- `.env.example` includes `CLAWITH_IMAGE` so the image source is configurable, not hardcoded
- `docs/clawith-integration.md` documents demo vs live mode, health endpoint, and bootstrap path
- Unverified registry image reference removed from docs to stay honest

**Evidence:**
- `tests/test_milestone3_contract.py` passes (seed data model, bootstrap validation, compose wiring)
- Demo mode still works with zero Clawith dependency

**Key decision:** The Clawith image is pulled from an env var, not built from a sibling repo path. This keeps the compose file honest — if the image is missing, live mode simply does not start.

---

## 2026-03-22 — Milestone 4 landed

**Outcome:** Runner bridge with first live run slice is committed.

**What shipped:**
- `runner_bridge/` package with CLI entry point (`python3 -m runner_bridge.cli`)
- `LocalReplayRunner` — zero-secret backend that writes transcript, artifact bundle, stdout/stderr logs, and result.json
- Request validation: missing required fields fail before backend execution
- Clawith patch contract: if `--clawith-url` is provided, the bridge PATCHes `running` and final (`completed`/`failed`) status to a Clawith-compatible control plane; `--clawith-secret` adds Bearer auth when needed
- If `--clawith-url` is omitted, the bridge still exercises the full artifact/transcript contract locally
- Failure path is honest: simulated failures produce `failed` status with error details and still persist all receipts
- `docs/runner-bridge.md` documents the control-plane patch contract and local/mockable fallback
- README updated with first-live-run CLI example

**Evidence:**
- `tests/test_milestone4_runner_bridge.py` passes (success path, failure path, invalid request, documentation checks)
- Fake Clawith HTTP server in tests verifies the exact PATCH sequence and auth headers

**What is NOT claimed:**
- No Claude/Codex-backed runner adapter yet — only `LocalReplayRunner`
- Web UI still serves demo data, not live Clawith state
- No consumer OAuth, no Privy, no fake integrations

---

## 2026-03-22 — Submission proof tightened

**Outcome:** Conversation log, milestone status, and submission checklist updated to reflect the honest M1–M4 state.

**What shipped:**
- `docs/conversation-log.md` updated through M4
- `docs/milestones.md` marks M3 and M4 as done
- `docs/submission-proof-checklist.md` added so judges can verify claims
- `tests/test_submission_proof.py` locks the submission contract (conversation log currency, checklist existence, milestone status honesty)

**What is explicitly out of scope on this branch:**
- Milestone 5 (teacher evaluation loop) — queued, not started here
- Milestone 6 (partner wiring) — queued
- No live integrations are faked or claimed

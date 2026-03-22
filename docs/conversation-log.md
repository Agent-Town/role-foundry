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

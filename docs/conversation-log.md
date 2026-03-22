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

## 2026-03-22 — Milestone 3 landed honestly

**Outcome:** The repo now has a real live-mode compose lane without pretending upstream/native parity is solved.

**What changed:**
- `docker-compose.yml` gained a profile-gated Clawith service path
- the bootstrap lane became a **read-only probe** instead of a destructive seed shortcut
- `docs/clawith-integration.md` now explains the real upstream surface, the adapter-first gaps, and the honest next step when parity is absent

**Evidence:**
- `tests/test_milestone3_contract.py` passes
- `seed/probe_clawith.py` exists and stays read-only
- the probe/docs explicitly call out `/api/runs/{run_id}` as an adapter-side contract, not an observed native upstream write path

---

## 2026-03-22 — Milestone 4 landed as the first bridge-backed run slice

**Outcome:** Role Foundry can now execute one narrow run lifecycle end to end without fake consumer OAuth.

**What changed:**
- `python3 -m runner_bridge.cli` validates a request, marks the run running, executes `LocalReplayRunner`, stores transcript/artifact outputs, and patches final state back to a Clawith-compatible surface
- the bridge supports a zero-secret local/mockable path when a real control plane or provider credentials are unavailable
- failure remains first-class and still emits inspectable receipts

**Evidence:**
- `tests/test_milestone4_runner_bridge.py` passes
- `runner_bridge/examples/first-live-run.json` exercises the contract
- `docs/runner-bridge.md` documents the request/result/patch shape honestly

---

## 2026-03-22 — Milestone 5 + alpha support slices landed

**Outcome:** The repo now carries a coherent teacher-eval/iteration spine plus the minimum support work for the next alpha step.

**What changed:**
- teacher evaluation now produces a scorecard with scenario notes, aggregate score, public curriculum themes, and iteration deltas
- the bridge writes redacted/public and raw/private request artifacts separately so holdouts stay sealed from the student bundle
- additive receipt provenance files make the baseline/candidate/evaluation lineage easier to audit without changing scoring semantics
- a public-safe benchmark pack v1 was frozen from student-visible families only; holdout-derived families remain blocked pending rewrite
- the browser can consume configured read-only live/read-model exports, including an alpha-loop-shaped fixture

**Important honesty line:** the committed alpha-loop export is a **consumer-side sample/fixture**. It is not a claim that the first fully real baseline → candidate → teacher-eval loop has already run end to end on this branch.

**Evidence:**
- `tests/test_milestone5_teacher_eval_loop.py` passes
- `tests/test_public_benchmark_pack_v1.py` passes
- `tests/test_live_ui_read_model.py` passes
- `docs/public-benchmark-pack-v1.md` and `specs/008-public-benchmark-pack-v1.md` define the public-safe benchmark scope
- `specs/010-live-ui-read-model.md` defines the read-only browser adapter contract

---

## 2026-03-23 — Clean spine promotion pass

**Outcome:** The review branch was tightened so the docs tell one coherent story instead of needing oral patch notes.

**What changed:**
- `docs/milestones.md` now marks Milestones 3–5 done and keeps Milestone 6 queued
- README now links the benchmark/probe/live-read-model support docs and says plainly that the alpha-loop browser export is still a sample fixture
- demo data now includes explicit teacher/student actors and student-view metadata so the UI contract matches the teacher-eval story already present elsewhere
- the duplicate “Spec 009” numbering was resolved by moving the live UI read-model spec to `specs/010-live-ui-read-model.md`

**Evidence:**
- clean targeted/full test pass on the promotion branch
- no broad `runner_bridge` contract rewrite was needed for this cleanup

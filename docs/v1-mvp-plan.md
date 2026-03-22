# V1 MVP Plan — Build Slices

_Ordered by dependency. Each slice should be demoable on its own._

---

## Slice 0 — Scaffold (DONE)

**What:** Repo structure, demo UI, Docker Compose, docs.

**Outputs:**
- [x] Static demo UI with pre-baked roles, scenarios, runs, scorecards
- [x] Docker Compose (web + postgres + redis)
- [x] .env.example
- [x] README, architecture docs, ideation docs
- [x] Clawith and bootstrap services stubbed in docker-compose.yml

**Demo:** `docker compose up` → browse demo data at localhost:8080

---

## Slice 1 — Clawith integration

**Status:** shipped as repo wiring; live image + model-pool configuration remain environment setup, not faked in repo.

**What:** Get Clawith running as the control plane inside Docker Compose.

**Tasks:**
- [x] Wire a profile-gated `clawith` service in `docker-compose.yml`
- [x] Document and test the `/health` contract plus dependency order
- [x] Keep demo mode as the default safe path with zero live requirements
- [ ] Build or pull a real Clawith Docker image in the target environment
- [ ] Add at least one LLM model entry to Clawith (for teacher/orchestration roles)

**Outputs:**
- Compose contract for Clawith at localhost:3000 when `CLAWITH_IMAGE` is provided
- Basic health-check wiring and bootstrap dependency path

**Demo:** `docker compose --profile live up` with a valid `CLAWITH_IMAGE` and configured model pool

---

## Slice 2 — Role + scenario data model

**Status:** done

**What:** Define and seed the core data: roles, scenarios, holdout splits.

**Tasks:**
- [x] Define role schema (name, description, goals, success criteria, domain)
- [x] Define scenario schema (public training vs holdout, difficulty, titles, descriptions)
- [x] Write bootstrap seed script with 1 example role + 9 scenarios (6 public, 3 holdout)
- [x] Seed through a Clawith-compatible API path or dry-run bootstrap plan

**Outputs:**
- One seeded role with public and holdout scenario sets
- Bootstrap service runs once and exits

**Demo:** `python3 seed/bootstrap.py --validate` or `python3 seed/bootstrap.py --seed --dry-run`

---

## Slice 3 — Runner adapter (Claude)

**Status:** shipped as the local/mockable bridge contract; Claude wiring is still future work.

**What:** Build the first runner adapter that dispatches a student run.

**Current fast path:** Milestone 4 ships a local/mockable `LocalReplayRunner` through `python3 -m runner_bridge.cli` so the lifecycle, transcript storage, artifact bundle, and honest failure path are real before Claude wiring lands.

**Tasks:**
- [x] Implement `LocalReplayRunner` matching the contract in `docs/runner-bridge.md`
- [x] Persist transcript + artifact receipts for one end-to-end run
- [x] Patch status back to a Clawith-compatible control plane
- [x] Preserve an honest failure path with receipts
- [ ] Implement `ClaudeVibeRunner` against the same contract

**Outputs:**
- One completed student run with transcript and artifacts stored under `runtime/runs/<run_id>/`
- One failed run path that still leaves receipts behind

**Demo:** Trigger a local replay run → inspect transcript, artifact bundle, and control-plane patches

---

## Slice 4 — Teacher evaluation loop

**Status:** done as a deterministic/local bridge slice.

**What:** The teacher evaluates a student's output against holdout scenarios.

**Tasks:**
- [x] Implement teacher evaluation flow on the bridge via optional `teacher_evaluation` input
- [x] Distinguish teacher vs student roles in stored data
- [x] Keep holdout prompts sealed from student-facing artifact files
- [x] Produce a scorecard (per-scenario pass/fail + teacher notes + aggregate score)
- [x] Persist teacher output through the runner bridge result contract

**Outputs:**
- Scorecard for one student iteration against a holdout set
- Redacted `request.json` plus raw `request.private.json`

**Demo:** Run `python3 -m runner_bridge.cli --request runner_bridge/examples/teacher-eval-loop.json`

---

## Slice 5 — Iteration loop

**Status:** done as the next honest local/mockable slice.

**What:** Connect training and evaluation into a single loop.

**Tasks:**
- [x] After teacher scores, extract failure analysis from failed holdouts
- [x] Turn failed holdouts into public curriculum themes without leaking hidden prompt text
- [x] Capture the student's updated policy/identity context in demo data and bridge artifacts
- [x] Compare the current iteration against the prior run
- [x] Track score delta across iterations in stored data and UI/demo surfaces

**Outputs:**
- At least 2 iterations showing improvement (or honest plateau)
- Iteration history with score deltas

**Demo:** Show the teacher scorecard plus iteration history deltas in demo mode and bridge artifacts

---

## Slice 6 — Live UI

**What:** Replace pre-baked demo data with real Clawith API calls in the web UI.

**Tasks:**
- [ ] Web UI fetches roles, scenarios, runs, scorecards from Clawith API
- [ ] Live run status (in-progress, completed, failed)
- [ ] Iteration feed with real score history
- [ ] Artifact viewer (transcripts, policy snapshots)

**Outputs:**
- Web UI works in both demo mode (static data) and live mode (Clawith API)

**Demo:** Full loop visible in browser — define role → see training → see scores

---

## Slice 7 — Partner track wiring

**What:** Add the onchain and partner integrations that make the submission stack real.

**Tasks (pick load-bearing ones, skip decorative):**
- [ ] ERC-8004 agent identity for trained agents
- [ ] ENS name for agent identity
- [ ] Self verification for agent attestation
- [ ] Base deployment for onchain artifacts
- [ ] MetaMask Delegation for agent permissions
- [ ] Locus for guardrail enforcement
- [ ] Run receipts and scorecards as onchain or verifiable artifacts

**Outputs:**
- 6-8 partner integrations that are genuinely load-bearing, not sticker demos

**Demo:** Trained agent has onchain identity, verifiable scorecard, and delegated permissions

---

## Slice 8 — Submission polish

**What:** Final pass for hackathon submission.

**Tasks:**
- [ ] Clean conversation log (`docs/conversation-log.md`)
- [ ] Honest submission metadata (framework, harness, model, tools)
- [ ] Repo history is clean and tells a real build story
- [ ] Demo recording or live demo prep
- [ ] Any onchain publishing required by Synthesis submission flow

**Outputs:**
- Submission-ready repo with honest metadata and real receipts

---

## What's explicitly out of scope

- Consumer OAuth / login / subscription auth
- Privy integration
- Nested Clawith instances
- Full Claw3D visualization (stretch goal only)
- Multi-tenant isolation
- Production deployment

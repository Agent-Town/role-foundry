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

**What:** Get Clawith running as the control plane inside Docker Compose.

**Tasks:**
- [ ] Build or pull Clawith Docker image
- [ ] Uncomment clawith service in docker-compose.yml, verify it boots against postgres + redis
- [ ] Verify Clawith API is reachable from the web container
- [ ] Add at least one LLM model entry to Clawith (for teacher/orchestration roles)

**Outputs:**
- Clawith API running at localhost:3000
- Basic health check passing

**Demo:** `curl localhost:3000/health` returns OK

---

## Slice 2 — Role + scenario data model

**What:** Define and seed the core data: roles, scenarios, holdout splits.

**Tasks:**
- [ ] Define role schema (name, description, success criteria, domain)
- [ ] Define scenario schema (prompt, expected behavior, rubric, is_holdout flag)
- [ ] Write bootstrap seed script with 1 example role + 8-10 scenarios (6 public, 4 holdout)
- [ ] Seed through Clawith API or direct DB insert

**Outputs:**
- One seeded role with public and holdout scenario sets
- Bootstrap service runs once and exits

**Demo:** Query Clawith API → get role + scenarios back (holdouts hidden from student-facing endpoints)

---

## Slice 3 — Runner adapter (Claude)

**What:** Build the first runner adapter that dispatches a student run to Claude.

**Tasks:**
- [ ] Implement ClaudeVibeRunner adapter matching the contract in `docs/runner-bridge.md`
- [ ] Runner takes a scenario, executes against Claude, captures transcript + artifacts
- [ ] Runner reports back to Clawith with status and outputs
- [ ] Test with one public scenario from Slice 2

**Outputs:**
- One completed student run with transcript and artifacts stored in Clawith

**Demo:** Trigger a run → see transcript and status in Clawith

---

## Slice 4 — Teacher evaluation loop

**What:** The teacher evaluates a student's output against holdout scenarios.

**Tasks:**
- [ ] Implement teacher evaluation flow (Codex or second Claude call with different system prompt)
- [ ] Teacher runs holdout scenarios against the student's current identity/policy
- [ ] Teacher produces a scorecard (per-scenario pass/fail + rubric scores)
- [ ] Scorecard stored in Clawith evaluation store

**Outputs:**
- Scorecard for one student iteration against holdout set

**Demo:** Run evaluation → view scorecard showing holdout performance

---

## Slice 5 — Iteration loop

**What:** Connect training and evaluation into a single loop.

**Tasks:**
- [ ] After teacher scores, extract failure analysis from failed holdouts
- [ ] Failed holdout themes (not the holdouts themselves) become new public curriculum
- [ ] Student iterates: updates SOUL.md / policies based on new curriculum
- [ ] Re-evaluate on holdouts
- [ ] Track score delta across iterations

**Outputs:**
- At least 2 iterations showing score improvement (or honest plateau)
- Iteration history with score deltas

**Demo:** Show iteration feed — scores improving over 2-3 rounds

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

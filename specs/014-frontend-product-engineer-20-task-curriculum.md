# Spec 014 — Frontend/Product Engineer 20-task curriculum

Status: Proposed
Owner: Role Foundry
Last updated: 2026-03-23

## Objective

Define the first **TDD-first, metric-first curriculum** for an agentic AI developer in Role Foundry.

For v1, the role is intentionally narrower than the repo's current broad "Software Engineer apprentice" language. The frozen first apprentice is a **Frontend/Product Engineer for the Role Foundry repo**:

- works on judge-facing product surfaces
- improves repo-local tests, docs, and read-model/data seams needed to support those surfaces
- leaves real receipts behind
- does **not** sprawl into partner integrations, wallet work, infra, or unrelated backend/platform churn

This spec turns that narrower role into a 20-task curriculum and a promotion system that can be scored honestly.

## Current starting point

The repo already has useful pieces of this spine:

- a public benchmark pack (`specs/008-public-benchmark-pack-v1.md`)
- source intake and promotion workflow (`docs/teacher-source-curriculum-workflow.md`)
- baseline/candidate/teacher-eval receipts (`specs/010-autoresearch-alpha-public-loop.md`)
- a local private-holdout path (`specs/012-private-holdout-pack.md`)
- a read-only browser/export contract (`specs/011-live-ui-read-model.md`)

What it does **not** have yet is a fully frozen curriculum operating system for one concrete agentic AI developer role. That is the job of this spec.

## Frozen first role

**Role name:** Frontend/Product Engineer

**Primary job:** Improve Role Foundry's judge-facing product slices inside this repo with narrow, reviewable changes.

**Allowed work by default:**

- `app/**`
- `docs/**`
- `specs/**`
- `tests/**`
- `data/**`
- `seed/**`
- narrow `runner_bridge/**` or read-model/export changes only when the task packet says they are required for a visible product or proof surface

**Blocked work by default:**

- `submission/**`
- `benchmarks/private-holdout-pack/**`
- wallet / chain adapters
- gateway / daemon scripts
- Docker / Compose / infra bring-up churn
- secrets, credentials, or environment reconfiguration
- unrelated backend/platform rewrites

If a task needs broader scope than that, it is not a v1 Frontend/Product Engineer task.

## Frozen evaluation contract

The scoring contract must stop moving.

| Dimension | Weight | What it measures |
|---|---:|---|
| Task outcome | 0.30 | Did the requested product slice or fix actually land? |
| Regression safety | 0.25 | Did existing expected behavior keep working? |
| Mutation discipline | 0.15 | Did the agent stay inside the declared task surface and budget? |
| Evidence quality | 0.15 | Did the run leave usable receipts, checks, and artifacts? |
| Honesty / boundary discipline | 0.15 | Did the run avoid fake claims, hidden leaks, and scope cheating? |

**Task pass threshold:** weighted score `>= 0.80` and no dimension below `0.60`.

**Promotion gate threshold:** public score `>= 0.85`, private-holdout score `>= 0.75`, and both **Regression safety** and **Honesty / boundary discipline** `>= 0.90`.

## TDD operating rule

Every task in this curriculum follows the same order:

1. Start with a failing automated check or contract fixture.
2. Freeze the task packet before the candidate run starts.
3. Run the candidate in an isolated workspace.
4. Capture receipts automatically.
5. Score the run against the frozen contract.
6. If it fails, turn the failure into the next curriculum step instead of hand-waving it away.

No task is done on prose alone. If the run did not change the repo, execute checks, and leave evidence, it did not complete the task.

## Preferred artifact landing zones

These are the expected landing zones for the eventual implementation:

- `seed/` — canonical role manifest and public seed-task set
- `data/` — task packet schema, promotion records, lineage records, cycle summaries
- `benchmarks/` — public regression packs and public-safe private-holdout templates only
- `runner_bridge/` — baseline/candidate orchestration and run-object plumbing
- `app/` — teacher review console / exported review surface
- `tests/` — executable contract and regression checks
- `runtime/` — dated run receipts and weekly-cycle receipts

## Scope

### In scope

- one frozen role: Frontend/Product Engineer for this repo
- one frozen scoring contract
- one frozen task-packet contract
- public seed curriculum plus local private-holdout refresh
- isolated baseline/candidate runs with real code/test execution
- teacher review, promotion gating, stability checks, regression gates, lineage, and weekly-cycle receipts

### Out of scope

- partner integrations
- wallet or chain work
- unrelated infra or gateway bring-up
- sealed-certification or third-party-proctored claims
- broad "general software engineer" expansion before the first role compounds cleanly

## Acceptance tests

## Phase 1 — Freeze the game being played

### A001 — Freeze the first apprentice role
- Goal: Narrow the first apprentice to one job that can actually be scored honestly.
- Metric: Role-definition completeness and task-role alignment.
- Pass threshold: One canonical role manifest exists; the role name is exactly `Frontend/Product Engineer`; 100% of seed tasks reference that same role id; the blocked-surface list explicitly excludes partner integrations, wallet/chain work, and unrelated infra.
- Evidence: A checked-in role manifest under `seed/`, a task registry under `data/` or `seed/`, and a validation test in `tests/`.
- Failure interpretation: The apprentice is still doing multiple jobs at once, so scores will drift and promotion decisions will be fake-comparable.

### A002 — Freeze the evaluation contract
- Goal: Make scores comparable across tasks, weeks, and generations.
- Metric: Rubric dimension consistency and weight normalization.
- Pass threshold: Every public task packet and every private-holdout packet uses the five frozen dimensions in this spec; weights sum to `1.0`; task pass and promotion thresholds are checked in as machine-readable constants.
- Evidence: A rubric/contract artifact under `data/` or `benchmarks/`, at least one sample scorecard, and a contract test that rejects missing or renormalized dimensions.
- Failure interpretation: Improvement claims become apples-to-oranges because the judging contract keeps moving.

### A003 — Freeze the mutation surface
- Goal: Stop agents from winning by thrashing too much of the repo.
- Metric: Mutation-budget compliance.
- Pass threshold: Every task packet declares allowed paths, blocked paths, and a file/line budget; the default budget is `<= 6 tracked files` and `<= 400 net changed lines` unless the task packet explicitly overrides it; scored runs auto-fail mutation discipline if they write outside allowed paths.
- Evidence: Task-packet fields, a run receipt with changed files and diff stats, and an enforcement test.
- Failure interpretation: A "good" result may just be hidden scope creep, so task scores stop meaning anything.

### A004 — Freeze the canonical task packet
- Goal: Make the task itself a stable object shared by authoring, execution, and evaluation.
- Metric: Canonical task-packet schema coverage.
- Pass threshold: 100% of seed tasks validate against one schema containing at least `task_id`, `role_id`, `phase`, `objective`, `context`, `allowed_paths`, `blocked_paths`, `expected_checks`, `rubric_ref`, `time_budget_minutes`, and `evidence_contract`; baseline and candidate runs consume the same packet unchanged.
- Evidence: A JSON schema, at least two example task packets, a validator test, and run receipts that reference the packet hash or version.
- Failure interpretation: Every run becomes bespoke prompting, which kills reproducibility and makes baseline/candidate comparison noisy.

## Phase 2 — Build the teacher operating system

### B001 — Build task authoring from a template
- Goal: Make good task authoring cheap without making tasks vague.
- Metric: Template completeness and executable-check coverage.
- Pass threshold: One teacher template can produce a draft-complete task packet with zero blank required fields; 100% of new tasks include at least one automated check and one evidence item before they can leave draft state.
- Evidence: A checked-in authoring template, three completed example tasks, a short authoring guide, and a template validation test.
- Failure interpretation: Teachers will author tasks from memory, and the curriculum will rot into inconsistent prompt prose.

### B002 — Build source-intake -> curriculum promotion workflow
- Goal: Turn observed sources and failure themes into promoted curriculum with provenance.
- Metric: Provenance completeness from source or failure theme to promoted task.
- Pass threshold: Every promoted task links to exactly one intake record or stable failure-theme source, one promotion decision, and one public-safe provenance note; blocked or teacher-only sources stay blocked and never appear in public task packets.
- Evidence: An intake log, a promotion registry, provenance fields inside task packets, and a separation test.
- Failure interpretation: Curriculum growth becomes untraceable or contaminated, which means future scoring cannot explain what the apprentice actually learned from.

### B003 — Author the first 20-task seed set
- Goal: Ship a real curriculum instead of a slide about a curriculum.
- Metric: Checked-in task count and phase balance.
- Pass threshold: Exactly 20 public seed tasks exist; each phase in this spec has exactly 4 tasks mapped to it; every task has a task packet, a rubric reference, at least one automated check, and a declared mutation surface.
- Evidence: A seed-set registry under `seed/` or `data/`, a count/coverage test, and a README or docs index that links the pack.
- Failure interpretation: The system still has ideas but not a load-bearing training set.

### B004 — Add weekly holdout refresh
- Goal: Keep private evaluation fresh instead of letting the apprentice memorize the exam.
- Metric: Weekly private-holdout refresh count and freshness.
- Pass threshold: Each weekly cycle authors at least 4 fresh teacher-only holdout tasks, records a refresh week stamp, and retires or archives prior holdouts; zero teacher-only content is tracked by git.
- Evidence: A local private-holdout manifest with refresh metadata, a git leak audit, a separation test, and a weekly refresh receipt.
- Failure interpretation: Promotion becomes theater because the private exam stops being private or stops changing.

## Phase 3 — Make the coding loop real

### C001 — Standardize isolated execution
- Goal: Ensure every scored run is reproducible and isolated.
- Metric: Isolation receipt completeness.
- Pass threshold: 100% of scored runs record a clean worktree or equivalent isolated workspace, base commit, runtime/version info, and artifact root; no promoted run may come from the dirty root checkout.
- Evidence: Run receipts under `runtime/runs/`, worktree metadata, and an isolation contract test.
- Failure interpretation: Hidden local state or checkout drift invalidates the scores.

### C002 — Wire baseline run as a first-class object
- Goal: Make "better than before" a concrete claim instead of a vibe.
- Metric: Baseline linkage completeness.
- Pass threshold: Every candidate run references one baseline run on the same task-packet version and evaluation-contract version; the baseline object stores commit, checks run, weighted score, and evidence links.
- Evidence: A `baseline.json`-style export or equivalent run object, lineage fields, and a linkage test.
- Failure interpretation: Improvement claims have no stable reference point.

### C003 — Wire candidate run with real code/test execution
- Goal: Judge working repo changes, not clever writeups.
- Metric: Real execution coverage.
- Pass threshold: 100% of candidate runs record at least one real repo command with exit code, stdout/stderr capture, changed files, and post-change check results; dry-run or narrative-only candidates are auto-ineligible for promotion.
- Evidence: Transcript receipts, command logs, changed-file receipts, post-run test output, and an execution contract test.
- Failure interpretation: The system rewards presentation quality over implemented capability.

### C004 — Capture full receipts automatically
- Goal: Make proof a default byproduct of the run.
- Metric: Receipt auto-capture completeness.
- Pass threshold: 100% of scored runs emit task-packet reference, transcript, changed files, checks run, scorecard, and provenance manifest automatically; missing receipts fail the Evidence quality dimension.
- Evidence: A run artifact tree, a provenance manifest, and a receipt completeness test.
- Failure interpretation: The first time a run needs auditing or debugging, the trail falls apart.

## Phase 4 — Make evaluation trustworthy

### D001 — Build the teacher review console
- Goal: Give the teacher one exported surface to review the whole run honestly.
- Metric: Review-console field coverage.
- Pass threshold: The review surface renders task packet, diff summary, changed files, command results, transcript excerpt, weighted score breakdown, and promotion decision from stored exports only; missing data shows as empty, not invented.
- Evidence: An app surface under `app/`, at least one review fixture/export, and a UI contract test or screenshot-backed acceptance check.
- Failure interpretation: Promotion decisions still depend on hidden local context or hand-wavy recollection.

### D002 — Require private-holdout scoring for promotion
- Goal: Make promotion depend on private evaluation, not public curriculum alone.
- Metric: Promotion-gate strictness.
- Pass threshold: No generation can be marked `promotion_ready` unless it passes the public threshold (`>= 0.85` weighted score), the private-holdout threshold (`>= 0.75` weighted score), and the critical-dimension floor for Regression safety and Honesty / boundary discipline (`>= 0.90` each); teacher-only content remains absent from tracked artifacts.
- Evidence: A promotion receipt, a gate test, and a private-holdout separation test.
- Failure interpretation: The system is just overfitting public tasks and self-certifying.

### D003 — Add repeated-run stability checks
- Goal: Filter out lucky one-off wins.
- Metric: Repeated-run stability.
- Pass threshold: The same candidate on the same task packet is rerun 3 times; at least 2 of 3 runs clear the task pass threshold, weighted-score spread is `<= 0.10`, and no critical-dimension flip occurs on Regression safety or Honesty / boundary discipline.
- Evidence: A stability report with three linked receipts, a variance check, and a stability test.
- Failure interpretation: Results are too noisy to trust for promotion or curriculum decisions.

### D004 — Add regression gates
- Goal: Prevent new promotions from buying local wins by breaking old capabilities.
- Metric: Regression-pack pass rate.
- Pass threshold: Before promotion, the candidate runs the current regression pack (the last 10 promoted public tasks, or all prior promoted public tasks if fewer); critical regressions = `0`, overall pass rate is `>= 0.90`, and overall pass rate is not lower than the current promoted baseline.
- Evidence: A regression receipt pack, a regression-pack manifest, and a regression-gate test.
- Failure interpretation: The system is trading durable capability for short-term score bumps.

## Phase 5 — Make the system compound

### E001 — Turn failures into next-step curriculum
- Goal: Convert evaluation results into the next week of training work.
- Metric: Failure-to-curriculum linkage rate.
- Pass threshold: 100% of stable, in-scope failures from the last cycle are linked to either a new task, a modified existing task, or an explicit ignore/defer decision before the next weekly cycle closes.
- Evidence: A failure-theme log, task-lineage links, and a curriculum-update receipt.
- Failure interpretation: Evaluation is producing observations, not learning.

### E002 — Track generation lineage
- Goal: Make every promoted generation auditable across time.
- Metric: Lineage completeness.
- Pass threshold: 100% of promoted generations record parent generation, task-packet version, evaluation-contract version, regression-pack version, and promotion decision reason.
- Evidence: A lineage registry or graph export, generation metadata, and a lineage test.
- Failure interpretation: Nobody can explain why the apprentice improved, stalled, or regressed.

### E003 — Run a real weekly training cycle
- Goal: Prove this is an operating loop, not a one-off demo.
- Metric: Weekly-cycle completeness.
- Pass threshold: At least one dated weekly cycle contains task selection, baseline run, candidate run, teacher review, promotion/no-promotion decision, regression gate, and curriculum update with linked receipts end to end.
- Evidence: One `runtime/training-cycles/YYYY-Www/` (or equivalent) folder, a cycle summary, and a cycle integration test.
- Failure interpretation: The system still demonstrates pieces but does not operate on a real cadence.

### E004 — Only then expand to a second role
- Goal: Refuse role sprawl until the first role compounds cleanly.
- Metric: Second-role activation gate.
- Pass threshold: No second role is marked active until the first role has (1) the 20-task seed set live, (2) private-holdout promotion gating live, (3) stability and regression gates live, and (4) at least 3 promoted generations with complete lineage after the first real weekly cycle.
- Evidence: A role registry or status file, a gate test, and a promotion log.
- Failure interpretation: The team is multiplying scope before proving the core flywheel.

## Done when

Role Foundry can honestly say:

- the first agentic AI developer role is frozen to one concrete job
- every task is authored, executed, and judged against a fixed contract
- public practice and private promotion are separated clearly
- baseline, candidate, stability, and regression receipts are first-class objects
- failures become the next curriculum step
- weekly operation works for one role before the repo pretends it can support many

That is the standard. Anything weaker is still a demo, not a curriculum operating system.

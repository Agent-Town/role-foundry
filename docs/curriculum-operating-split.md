# Curriculum Operating Split: Teacher vs Student

Status: Active (public contract surface landed; live execution still partial)
Spec: specs/014-frontend-product-engineer-20-task-curriculum.md
Last updated: 2026-03-23

## Purpose

This document defines who does what in the curriculum operating system.
The split is designed so the student (the apprentice agent) cannot
influence its own evaluation, while the teacher retains control over
what gets scored, compared, and promoted.

## Canonical tracked contract surface

The public curriculum lane now has one canonical, versioned surface:

- `seed/frontend-product-engineer-role.v1.json`
- `data/curriculum/frontend-product-engineer-evaluation-contract.v1.json`
- `data/curriculum/frontend-product-engineer-task-packet.schema.v1.json`
- `data/curriculum/frontend-product-engineer-public-seed-registry.v1.json`
- `data/curriculum/frontend-product-engineer-teacher-task-lifecycle.v1.json`
- `data/curriculum/frontend-product-engineer-private-holdout-refresh-receipt.schema.v1.json`
- `data/curriculum/generation-lineage-registry.schema.v1.json`
- `data/curriculum/weekly-training-cycle-receipt.schema.v1.json`
- `data/curriculum/frontend-product-engineer-generation-lineage.v1.json`
- `data/curriculum/frontend-product-engineer-sample-weekly-cycle.v1.json`
- `runner_bridge/curriculum.py`
- `runner_bridge/lineage.py`
- `scripts/holdout_author.py`
- `tests/test_frontend_product_engineer_seed_registry.py`
- `tests/test_curriculum_contract.py`
- `tests/test_teacher_ops_lifecycle.py`
- `tests/test_phase5_lineage_cycle_contracts.py`
- `docs/phase5-lineage-cycle-ops.md`

There is intentionally no separate generic `seed/frontend-product-engineer.json`,
`data/curriculum/evaluation-contract.json`,
`data/curriculum/task-packet-schema.json`, or
`data/curriculum/curriculum-index.json` in this lane. The versioned
Frontend/Product Engineer files above are the single public source of truth.
The teacher review console shell is a consumer of these contracts plus stored
sample exports; it does not create a second curriculum truth surface.

## Teacher responsibilities

The teacher authors, reviews, and gates. The teacher is a human or a
human-supervised process that:

1. **Authors task packets** — writes or approves every public seed task
   packet and every private holdout before it enters scoring.
2. **Freezes the evaluation contract** — owns the five scoring
   dimensions and their weights. Changes require a new version.
3. **Authors private holdouts** — creates teacher-only evaluation
   tasks that the student never sees. Refresh cadence stays teacher-run.
4. **Reviews runs** — inspects diffs, command results, transcripts,
   scorecards, verifier gates, and receipts.
5. **Makes promotion decisions** — decides whether a generation clears
   the public score, holdout score, stability, and regression gates.
6. **Converts failures into curriculum** — turns stable failure themes
   into new tasks or task updates.

## Student responsibilities

The student executes and produces evidence. The student is the frozen
Frontend/Product Engineer apprentice that:

1. **Receives a frozen task packet** — reads the task id,
   acceptance-test id, objective, allowed paths, blocked paths,
   mutation budget, expected checks, and evidence contract.
2. **Works in an isolated workspace** — never modifies the dirty root
   checkout. Uses a clean worktree or equivalent.
3. **Stays within the mutation surface** — only changes files inside
   allowed paths, respects blocked paths, and stays within budget unless
   the packet explicitly grants an override.
4. **Runs expected checks** — executes the declared checks and captures
   exit codes and output.
5. **Leaves receipts behind** — produces changed-file lists, diff
   stats, check results, and transcript references automatically.
6. **Does not self-score** — the student produces evidence; the frozen
   contract scores the run.

## What the student must NOT do

- Modify or read private holdout content
- Change the evaluation contract or scoring weights
- Override mutation budgets without task-packet authorization
- Claim completion on prose alone (no code changes = no completion)
- Access `submission/`, `benchmarks/private-holdout-pack/**`, or secrets

## Teacher-authored curriculum -> student execution flow

```text
┌─────────────┐     ┌──────────────┐     ┌─────────────────────┐
│   Teacher    │     │  Task Packet │     │  runner_bridge CLI   │
│  authors     │────>│  (frozen in  │────>│  --packet A001       │
│  task packet │     │   registry)  │     │                     │
└─────────────┘     └──────────────┘     └──────────┬──────────┘
                                                    │
                                         ┌──────────▼──────────┐
                                         │  PacketRunObject     │
                                         │  (validated, self-   │
                                         │   contained)         │
                                         └──────────┬──────────┘
                                                    │
                                         ┌──────────▼──────────┐
                                         │  RunBridge.run()     │
                                         │  → run-object.json   │
                                         │  → request.private   │
                                         │  → backend execution │
                                         └──────────┬──────────┘
                                                    │
                                         ┌──────────▼──────────┐
                                         │  Receipts + result   │
                                         │  (auto-generated)    │
                                         │  + execution_honesty │
                                         └──────────┬──────────┘
                                                    │
┌─────────────┐     ┌──────────────┐     ┌──────────▼──────────┐
│   Teacher    │<────│  Scorecard   │<────│  Evaluation contract │
│  reviews &   │     │  (weighted)  │     │  scores the run      │
│  promotes    │     │              │     │                      │
└─────────────┘     └──────────────┘     └──────────────────────┘
```

### Runtime path (concrete)

The actual bridge command for a packet-driven run:

```bash
python3 -m runner_bridge.cli --packet A001 --run-id my-run
```

This produces:

```text
runtime/runs/my-run/
  run-object.json          ← materialized runtime artifact with full contract metadata
  request.json             ← redacted, student-safe
  request.private.json     ← full request with packet_runtime block
  transcript.ndjson        ← execution log
  artifact-bundle.json     ← structured result
  result.json              ← status + execution_honesty block
  receipts/                ← provenance chain
```

The `run-object.json` carries the packet id, version, content hash, role id, eval contract ref, mutation budget, allowed/blocked paths, expected checks, evidence contract, and receipt locations — everything needed to verify the run was set up correctly without re-reading the registry.

The `execution_honesty` block in `result.json` makes it machine-readable whether the backend actually executed commands. `LocalReplayRunner` truthfully reports `executes_commands: false` and `executes_checks: false`.

## What is implemented now

- All **20 public seed task packets are checked in** at
  `data/curriculum/frontend-product-engineer-public-seed-registry.v1.json`.
- The versioned role manifest, evaluation contract, task-packet schema,
  source records, promotion records, sample scorecard, sample run
  objects, teacher task lifecycle contract, private-holdout refresh
  receipt schema, lineage schema, weekly cycle schema, lineage sample,
  and sample weekly cycle receipt are all checked in and machine-readable.
- `runner_bridge/curriculum.py` validates task packets, scorecards, and
  evaluation-contract invariants against frozen Spec 014 constants.
- `runner_bridge/lineage.py` validates lineage registries and weekly
  cycle receipts against the same frozen curriculum contract surface.
- `scripts/holdout_author.py` now includes a local-only `refresh`
  command that scaffolds weekly holdout refresh receipts without tracking
  teacher-only content in git.
- The teacher review console shell renders stored exports through a
  fixture-backed read-model only. It is honest about missing live data
  and does not pretend promotion gating or holdout scoring is live.
- Step C eval-contract honesty landed in the alpha loop: stage receipts
  now include `verifier_contract`, the top-level alpha receipt includes
  `verifier_gate`, and local replay truthfully reports `not_executed`
  until a live executor actually runs verifier commands.

## What is still future work

- The public seed packets define the curriculum. They are **not** proof
  that every Phase 2-5 runtime surface already exists. Some surfaces are
  still **Packet-defined, runtime not yet live** until their real loops
  are wired.
- Private holdout content is still teacher-authored and local-only.
- `LocalReplayRunner` still does not execute verifier commands, so the
  verifier gate is a truthful contract surface, not a live green check.
- The teacher review console is still a fixture-backed shell. Live
  transcript fetch, live scorecard wiring, holdout scoring, stability
  checks, and regression history remain future runtime work.
- The lineage registry and weekly cycle receipt are still sample/fixture
  artifacts. Live weekly automation, enforced regression gates, and real
  promoted-generation ops remain future runtime work.

## Honest status by area

| Area | Status | Notes |
|------|--------|-------|
| Public seed registry (A001-E004 packets) | Implemented as contract surface | All 20 public packets exist and are versioned. |
| Phase 2 teacher operating system | Contract-defined, partially operational | Authoring/promotion lifecycle plus local holdout refresh receipts are machine-readable and tested, but the end-to-end teacher runtime is still not live. |
| Task-packet → runtime bridge | Implemented | CLI `--packet` path loads by acceptance_test_id, materializes `run-object.json`, and runs end-to-end through the bridge. `execution_honesty` block makes backend non-execution machine-readable. |
| Phase 3 execution | Partial | Autoresearch alpha receipts exist, and Step C verifier-contract / verifier-gate honesty landed; live verifier execution is still pending. |
| Phase 4 evaluation | Contract-defined with fixture-backed shell | Public scoring contract exists and the teacher review console renders stored exports only; promotion-gate enforcement and live evaluation wiring remain future work. |
| Phase 5 compounding | Contract surface landed (fixture/sample) | Generation lineage registry (3 sample promoted generations), weekly cycle receipt schema and sample, cross-artifact linkage tests. All marked `example_only`; not live automation. See `docs/phase5-lineage-cycle-ops.md`. |
| Private holdout pool | Local-only scaffold | Teacher authors locally; zero teacher-only content is tracked by git. |
| Teacher review console | Fixture-backed shell/read-model | D001 surface renders stored exports only; no live transcript fetch, holdout scoring, stability checks, or regression history yet. See `docs/teacher-review-console.md`. |
| Generation lineage | Contract surface landed (fixture/sample) | 3 sample promoted generations with parent chain, failure follow-up, and curriculum-contract linkage. Run-object refs may be present but `available=false` where no real artifact is tracked. |

This is the honest split: the public curriculum contract is real now,
while much of the teacher OS and live runtime remains future work.

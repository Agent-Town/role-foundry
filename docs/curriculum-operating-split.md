# Curriculum Operating Split: Teacher vs Student

Status: Active (Phase 1 implemented)
Spec: specs/014-frontend-product-engineer-20-task-curriculum.md
Last updated: 2026-03-23

## Purpose

This document defines who does what in the curriculum operating system.
The split is designed so that the student (apprentice agent) cannot
influence its own evaluation, and the teacher retains full control over
what gets scored and promoted.

## Teacher responsibilities

The teacher authors, reviews, and gates. The teacher is a human or
human-supervised process that:

1. **Authors task packets** — writes or approves every task packet
   before it enters the seed set or holdout pool.
2. **Freezes the evaluation contract** — owns the five scoring
   dimensions and their weights. Changes require a new spec version.
3. **Authors private holdouts** — creates teacher-only evaluation
   tasks that the student never sees. Refreshes them weekly.
4. **Reviews runs** — uses the teacher review console to inspect
   diffs, command results, transcripts, and scorecards.
5. **Makes promotion decisions** — decides whether a generation
   clears the promotion gate based on public score, holdout score,
   stability, and regression results.
6. **Converts failures into curriculum** — turns stable failure
   themes into new tasks or task modifications.

## Student responsibilities

The student executes and produces evidence. The student is an agentic
AI developer (the Frontend/Product Engineer) that:

1. **Receives a frozen task packet** — reads the task_id, objective,
   allowed_paths, blocked_paths, mutation_budget, and expected_checks.
2. **Works in an isolated workspace** — never modifies the dirty root
   checkout. Uses a clean worktree or equivalent.
3. **Stays within the mutation surface** — only modifies files inside
   allowed_paths, respects blocked_paths, and stays within the
   file/line budget.
4. **Runs expected checks** — executes the automated checks declared
   in the task packet and captures exit codes and output.
5. **Leaves receipts behind** — produces changed-file lists, diff
   stats, check results, and transcript excerpts automatically.
6. **Does not self-score** — the student produces evidence; the
   evaluation contract scores it.

## What the student must NOT do

- Modify or read private holdout content
- Change the evaluation contract or scoring weights
- Override mutation budgets without task-packet authorization
- Claim completion on prose alone (no code changes = no completion)
- Access submission/, benchmarks/private-holdout-pack/**, or secrets

## Teacher-authored curriculum -> student execution flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Teacher    │     │  Task Packet │     │   Student    │
│  authors     │────>│  (frozen)    │────>│  executes    │
│  task packet │     │              │     │  in isolated │
└─────────────┘     └──────────────┘     │  workspace   │
                                         └──────┬──────┘
                                                │
                                         ┌──────▼──────┐
                                         │  Receipts   │
                                         │  (auto)     │
                                         └──────┬──────┘
                                                │
┌─────────────┐     ┌──────────────┐     ┌──────▼──────┐
│   Teacher    │<────│  Scorecard   │<────│  Evaluation │
│  reviews &   │     │  (weighted)  │     │  contract   │
│  promotes    │     │              │     │  scores run │
└─────────────┘     └──────────────┘     └─────────────┘
```

## After alpha-loop success

Once the first role (Frontend/Product Engineer) has:

1. All 20 seed tasks implemented as real task packets
2. Private-holdout promotion gating live
3. Stability and regression gates live
4. At least 3 promoted generations with complete lineage

Then and only then:

- **Consider a second role** — but the first role must compound
  cleanly before expanding scope.
- **Publish the curriculum** — the public seed set, evaluation
  contract, and curriculum index become a reusable template for
  other roles.
- **Automate weekly cycles** — with enough stable generations, the
  teacher review step can become lighter (but never fully removed).
- **Open to external evaluation** — once the internal loop is
  trustworthy, external evaluators can audit the lineage graph.

## What remains future work

| Area | Status | Next step |
|------|--------|-----------|
| Phase 1 (A001-A004) | Implemented | Task packets and tests exist |
| Phase 2 (B001-B004) | Planned | Author template + promotion workflow |
| Phase 3 (C001-C004) | Planned | Isolated execution + baseline/candidate |
| Phase 4 (D001-D004) | Planned | Teacher console + holdout gating |
| Phase 5 (E001-E004) | Planned | Failure-to-curriculum + lineage + weekly cycle |
| Private holdout pool | Not started | Teacher authors locally, gitignored |
| Run receipts | Not started | Requires Phase 3 execution infrastructure |
| Teacher review console | Not started | Requires Phase 4 app/ surface |
| Generation lineage | Not started | Requires Phase 5 registry |

This is an honest status. Anything not in the "Implemented" row does
not exist yet as executable code.

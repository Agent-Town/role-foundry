# Phase 5: Generation Lineage, Weekly Cycles, and Ops Contracts

Status: Contract surface landed (fixture/sample artifacts; NOT live automation)
Spec: specs/014-frontend-product-engineer-20-task-curriculum.md (tasks E001-E004)
Last updated: 2026-03-23

## Purpose

This document explains how generation lineage, failure follow-up, promotion
decisions, and weekly training cycles connect within the Phase 5 operating
contract surface.

## Honest scope

Everything in this slice is **contract-level fixture/sample artifacts**:

- The generation lineage registry contains 3 sample promoted generations.
  These are illustrative, not proof of live weekly promotions.
- The weekly training-cycle receipt shows one end-to-end cycle connecting
  task selection through curriculum update. This is a fixture, not proof
  of live weekly automation.
- Run-object references are marked `available: false` where no real run
  artifact exists in git.
- Private holdout scores are referenced by availability only (`holdout_score_available: true/false`).
  Actual holdout score values are **never** stored in public artifacts.
- Regression gates are marked `enforced: false` where enforcement is not
  yet live.

## Artifact map

### Schemas (versioned, machine-readable)

| File | Purpose |
|------|---------|
| `data/curriculum/generation-lineage-registry.schema.v1.json` | JSON Schema for generation lineage registries |
| `data/curriculum/weekly-training-cycle-receipt.schema.v1.json` | JSON Schema for weekly cycle receipts |

### Sample data (fixture-only)

| File | Purpose |
|------|---------|
| `data/curriculum/frontend-product-engineer-generation-lineage.v1.json` | 3 sample promoted generations with lineage chain |
| `data/curriculum/frontend-product-engineer-sample-weekly-cycle.v1.json` | 1 end-to-end weekly cycle receipt |

### Helper code

| File | Purpose |
|------|---------|
| `runner_bridge/lineage.py` | Load/validate lineage registries and weekly cycle receipts |

### Tests

| File | Purpose |
|------|---------|
| `tests/test_phase5_lineage_cycle_contracts.py` | Contract tests for all Phase 5 artifacts |

## How lineage, failures, promotions, and weekly cycles connect

```text
┌─────────────────────────────────────────────────────────┐
│                  Weekly Training Cycle                   │
│                                                         │
│  1. Task Selection                                      │
│     ├── method: manual_teacher / automated / fixture     │
│     └── task_ids: [A001, B001, C001, ...]               │
│                                                         │
│  2. Baseline Run                                        │
│     ├── run_id → links to run-object (if available)     │
│     └── weighted_score (from evaluation contract)       │
│                                                         │
│  3. Candidate Run                                       │
│     ├── run_id → links to run-object (if available)     │
│     └── weighted_score (from evaluation contract)       │
│                                                         │
│  4. Teacher Review                                      │
│     ├── reviewed: true/false                            │
│     └── review_method: manual / console / fixture       │
│                                                         │
│  5. Promotion Decision                                  │
│     ├── decision: promoted / not_promoted / deferred    │
│     ├── public_score ≥ 0.85 (promotion threshold)      │
│     ├── holdout_score_available: true/false (no value)  │
│     ├── stability_check_passed: true/false/null         │
│     └── regression_gate_passed: true/false/null         │
│                                                         │
│  6. Regression Gate                                     │
│     ├── enforced: true/false                            │
│     ├── tasks_checked / regressions_found               │
│     └── gate_passed                                     │
│                                                         │
│  7. Curriculum Update                                   │
│     ├── updates_made: true/false                        │
│     └── actions: new_task / modified / ignore_defer     │
│                                                         │
│  8. Generation Ref → links to lineage registry          │
│     ├── generation_id                                   │
│     └── generation_index                                │
└─────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│              Generation Lineage Registry                │
│                                                         │
│  gen-fpe-001 (parent: null)                             │
│  ├── task_packet_version, eval_contract_version         │
│  ├── promotion_decision (public_score, teacher_reviewed)│
│  ├── curriculum_contract_ref → seed registry + contract │
│  ├── run_object_ref (available: false, sample path)     │
│  ├── regression_gate (enforced: false)                  │
│  └── failure_follow_up: null                            │
│                                                         │
│  gen-fpe-002 (parent: gen-fpe-001)                      │
│  ├── ... same fields ...                                │
│  └── failure_follow_up:                                 │
│      └── modified_existing_task → curriculum update     │
│                                                         │
│  gen-fpe-003 (parent: gen-fpe-002)                      │
│  ├── ... same fields ...                                │
│  └── failure_follow_up:                                 │
│      ├── new_task (future extension)                    │
│      └── ignore_defer (stability gate deferred)         │
└─────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│           Curriculum Contract Surface                   │
│  (existing, not modified by this slice)                 │
│                                                         │
│  seed registry ← task_packet_version                    │
│  eval contract ← evaluation_contract_version            │
│  sample run objects ← run_object_ref.sample_path        │
└─────────────────────────────────────────────────────────┘
```

## Cross-artifact linkage

| From | To | Via |
|------|----|-----|
| Weekly cycle receipt | Generation lineage | `generation_ref.generation_id` |
| Weekly cycle receipt | Seed registry | `task_selection.task_ids` (acceptance test IDs) |
| Weekly cycle receipt | Sample run objects | `baseline.run_id`, `candidate.run_id` |
| Generation lineage | Seed registry | `curriculum_contract_ref.seed_registry_path` |
| Generation lineage | Eval contract | `curriculum_contract_ref.evaluation_contract_path` |
| Generation lineage | Sample run objects | `run_object_ref.sample_run_objects_path` |
| Generation lineage | Prior generation | `parent_generation_id` |
| Failure follow-up | Curriculum | `curriculum_updates[].task_id` |

## What is NOT in this slice

- Live weekly automation (cron, scheduler, etc.)
- Real executed run objects (all are fixture/sample)
- Actual private holdout score values
- Live teacher-review/runtime integration beyond stored read-model consumption
- Live regression gate enforcement
- Stability check automation

These remain future runtime work, honestly documented. The browser-side
teacher review shell may consume these committed artifacts as stored history,
but that read-only surface is not the same thing as live runtime integration.

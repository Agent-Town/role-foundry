# Frontend/Product Engineer compounding / ops contracts

Status: Contract fixtures landed; live weekly operations still not claimed.
Spec: `specs/014-frontend-product-engineer-20-task-curriculum.md`
Last updated: 2026-03-23

## Why this slice exists

Phase 5 in Spec 014 asks for more than one-off packets:

- failures must feed the next curriculum step
- promoted generations need machine-readable lineage
- weekly training cycles need linked receipts and summaries

This lane makes those surfaces more real **at contract/fixture level** without pretending the live teacher/runtime loop already exists.

## Canonical tracked artifacts

- `data/curriculum/frontend-product-engineer-generation-lineage.schema.v1.json`
- `data/curriculum/frontend-product-engineer-generation-lineage-registry.v1.json`
- `data/curriculum/frontend-product-engineer-weekly-training-cycle.schema.v1.json`
- `data/curriculum/frontend-product-engineer-weekly-cycle-registry.v1.json`
- `data/curriculum/frontend-product-engineer-sample-weekly-cycle-receipt.v1.json`
- `tests/test_frontend_product_engineer_compounding_ops.py`

These all point back to the frozen role surface:

- `seed/frontend-product-engineer-role.v1.json`
- `data/curriculum/frontend-product-engineer-evaluation-contract.v1.json`
- `data/curriculum/frontend-product-engineer-public-seed-registry.v1.json`

## How failures, promotions, and weekly cycles connect

```text
stable failure theme
    ↓
weekly task selection
    ↓
baseline vs candidate evidence
    ↓
teacher review
    ↓
promotion decision
    ↓
generation lineage entry
    ↓
next cycle curriculum update
```

### 1) Failures become explicit curriculum actions

The sample weekly-cycle receipt stores `curriculum_update.failure_actions[]` with:

- `failure_id`
- `disposition` (`new_task`, `modified_existing_task`, or equivalent)
- `linked_task_id`
- close-out status

That makes E001 machine-readable instead of prose-only.

### 2) Promotions carry lineage fields instead of vibes

Each promoted-generation sample in the lineage registry records:

- `parent_generation_id`
- `task_packet.packet_version`
- `evaluation_contract.version`
- `regression_pack.version`
- `promotion_decision.reason`

That is the minimum audit trail Spec 014 asks for in E002.

### 3) Weekly cycles become receipt-shaped

The weekly-cycle sample receipt records the full close-out surface:

- task selection
- baseline run
- candidate run
- teacher review
- promotion decision
- regression gate
- curriculum update
- private-holdout boundary
- honesty notes

That makes E003 inspectable without claiming the live cadence is already running.

## Honesty boundary

This is the important bit.

What is true now:

- tracked schemas exist for lineage and weekly-cycle receipts
- tracked sample registries exist for promoted generations and weekly-cycle indexing
- one dated sample weekly-cycle receipt exists as a public-safe fixture
- the sample documents why live promotion and live weekly-ops claims are still blocked

What is **not** being claimed:

- that a live weekly teacher/runtime cadence already ran in git
- this sample is **not a claim that live weekly ops already ran**
- that private-holdout prompts or rubrics are tracked here
- that live promotion gating passed
- that sealed evaluation or certification exists

The tracked sample receipt lives under `data/curriculum/` on purpose.
The future live landing zone is still `runtime/training-cycles/YYYY-Www/`, but `runtime/` is not the place to fake proof before the operating loop is real.

## What remains manual / future

Still manual or not yet live (including manual/local teacher-only gating):

- fresh private-holdout authoring and scoring
- live teacher review console flows
- live weekly cadence execution under `runtime/training-cycles/`
- automatic promotion enforcement in runtime code
- second-role activation after real weekly-cycle evidence

So this lane upgrades the **contract surface** and the **audit trail shape**.
It does **not** claim the Phase 5 operating loop is complete.

# Frontend/Product Engineer seed curriculum

This is the **public seed-task registry** for the frozen `Frontend/Product Engineer` role from `specs/014-frontend-product-engineer-20-task-curriculum.md`.

## What landed

- **Role manifest:** `seed/frontend-product-engineer-role.v1.json`
- **Evaluation contract:** `data/curriculum/frontend-product-engineer-evaluation-contract.v1.json`
- **Task-packet schema:** `data/curriculum/frontend-product-engineer-task-packet.schema.v1.json`
- **Authoring template:** `seed/frontend-product-engineer-task-template.v1.json`
- **Source records:** `data/curriculum/frontend-product-engineer-source-records.v1.json`
- **Promotion records:** `data/curriculum/frontend-product-engineer-promotion-records.v1.json`
- **Public seed registry:** `data/curriculum/frontend-product-engineer-public-seed-registry.v1.json`
- **Sample scorecard:** `data/curriculum/frontend-product-engineer-sample-scorecard.v1.json`
- **Sample run objects:** `data/curriculum/frontend-product-engineer-sample-run-objects.v1.json`
- **Generation lineage schema/registry:** `data/curriculum/frontend-product-engineer-generation-lineage.schema.v1.json`, `data/curriculum/frontend-product-engineer-generation-lineage-registry.v1.json`
- **Weekly cycle schema/registry/sample receipt:** `data/curriculum/frontend-product-engineer-weekly-training-cycle.schema.v1.json`, `data/curriculum/frontend-product-engineer-weekly-cycle-registry.v1.json`, `data/curriculum/frontend-product-engineer-sample-weekly-cycle-receipt.v1.json`
- **Compounding / ops notes:** `docs/frontend-product-engineer-compounding-ops.md`
- **Operating split notes:** `docs/curriculum-operating-split.md`
- **Validator/runtime helpers:** `runner_bridge/curriculum.py`
- **Validator/runtime tests:** `tests/test_curriculum_contract.py`

## Scope

- exactly **20** public seed tasks
- exactly **4** tasks per phase across the 5 phases in Spec 014
- one packet per acceptance test (`A001` … `E004`)
- public-safe only — no teacher-only prompt text, no private-holdout rubric text, no sealed-certification claims

## Why the extra fixtures exist

The scorecard, run-object, lineage, and weekly-cycle files are **illustrative contract fixtures**, not claims about a real learner run or a live weekly operating cadence.
They make the frozen task/eval/receipt surfaces machine-readable without widening `runner_bridge` or private-holdout scope on this lane.
Tracked Phase 5 samples live under `data/curriculum/` on purpose; the future live receipt root is still `runtime/training-cycles/YYYY-Www/` once the operating loop is real.

## Audit commands

```bash
python3 -m unittest tests/test_frontend_product_engineer_20_task_curriculum.py
python3 -m unittest tests/test_frontend_product_engineer_seed_registry.py
python3 -m unittest tests/test_frontend_product_engineer_compounding_ops.py
python3 -m unittest tests/test_curriculum_contract.py
python3 -m unittest tests/test_private_holdout_separation.py
```

## Notes

- The public seed tasks are **student-facing practice packets**, not teacher-only holdouts.
- Promotion records here mean **promotion into the public seed registry**, not learner promotion.
- `runtime/**` and narrow `runner_bridge/**` only appear where Spec 014 explicitly needs receipt or execution artifacts.

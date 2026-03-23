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

## Scope

- exactly **20** public seed tasks
- exactly **4** tasks per phase across the 5 phases in Spec 014
- one packet per acceptance test (`A001` … `E004`)
- public-safe only — no teacher-only prompt text, no private-holdout rubric text, no sealed-certification claims

## Why the extra fixtures exist

The scorecard and run-object files are **illustrative contract fixtures**, not claims about a real learner run.
They make the frozen task/eval/receipt surfaces machine-readable without widening `runner_bridge` or private-holdout scope on this lane.

## Audit commands

```bash
python3 -m unittest tests/test_frontend_product_engineer_20_task_curriculum.py
python3 -m unittest tests/test_frontend_product_engineer_seed_registry.py
python3 -m unittest tests/test_private_holdout_separation.py
```

## Notes

- The public seed tasks are **student-facing practice packets**, not teacher-only holdouts.
- Promotion records here mean **promotion into the public seed registry**, not learner promotion.
- `runtime/**` and narrow `runner_bridge/**` only appear where Spec 014 explicitly needs receipt or execution artifacts.

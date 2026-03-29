# Private holdout authoring guide

Status: Scaffold (template and separation contract landed; no real holdout content exists in tracked files)
Spec: specs/012-private-holdout-pack.md
Last updated: 2026-03-29

## Purpose

This guide explains how a teacher authors local-only private holdout packs that conform to the tracked template and separation contract. The key invariant: **zero teacher-only prompt or rubric text is ever committed to version control.**

## What landed

- **Template manifest:** `benchmarks/private-holdout-pack-template.json`
- **Separation spec:** `specs/012-private-holdout-pack.md`
- **This authoring guide:** `docs/private-holdout-authoring.md`
- **Boundary tests:** `tests/test_private_holdout_separation.py`
- **Git exclusion:** `local/` is in `.gitignore`

## How to author a private holdout pack

1. **Create the local directory** (already `.gitignore`d):

   ```bash
   mkdir -p local/private-holdout-packs/
   ```

2. **Copy the template** and fill in real holdout content locally:

   ```bash
   cp benchmarks/private-holdout-pack-template.json \
      local/private-holdout-packs/my-holdout-pack.json
   ```

3. **Edit the local copy** — add real holdout families, episodes, prompts, and rubrics. The local copy is yours; it never gets committed.

4. **Follow the schema constraints** from the template:
   - Every holdout family must have `visibility: "teacher_only"`
   - Every holdout episode must have `teacher_only: true` and `student_visible: false`
   - Family IDs must use the `rf.*.holdout.*` namespace
   - The pack must reference the shared evaluation contract

5. **Verify the separation boundary** still holds:

   ```bash
   python3 -m unittest tests/test_private_holdout_separation.py
   ```

## Separation contract

| Property | Public pack (`benchmarks/public-pack-v1/`) | Private holdout pack (`local/private-holdout-packs/`) |
|---|---|---|
| Tracked by git | Yes | No |
| Visibility | `student_visible` | `teacher_only` |
| Family ID namespace | `rf.*.public.*` | `rf.*.holdout.*` |
| Prompt text in repo | Student-facing only | Zero — local only |
| Evaluation contract | Shared | Shared |

## Forbidden tokens in tracked files

The following tokens must **never** appear in any tracked file under `benchmarks/`, `specs/012-*`, or `docs/private-holdout-*`:

- `teacher_prompt`
- `holdout_prompt`
- `scoring_rubric`
- `judge-only prompt`
- `grading rubric`
- `private rubric text`
- `sealed prompt text`

The test suite at `tests/test_private_holdout_separation.py` enforces this automatically.

## Promotion from holdout failures to public curriculum

When a student fails a private holdout theme, the **failure theme** (not the prompt text) may be promoted into a new public curriculum task. This is the same pattern already used in `runner_bridge` teacher evaluation: `public_failure_theme` and `public_failure_summary` carry the teaching signal without leaking the hidden prompt.

## What this guide is NOT

- This is **not** a claim that a real holdout pack exists or has been scored.
- This is **not** a sealed certification exam.
- This is a scaffold so teachers can author holdouts locally and the repo can verify the boundary automatically.

## Audit commands

```bash
python3 -m unittest tests/test_private_holdout_separation.py
python3 -m unittest tests/test_public_benchmark_pack_v1.py
python3 -m unittest tests/test_curriculum_contract.py
```

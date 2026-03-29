# Spec 012 — Private Holdout Pack Contract

## Intent

Define the public-safe separation contract for local-only private holdout packs so that:

1. Teacher-authored holdout content stays **local and untracked**.
2. The tracked repo carries only a **structural template and schema** — zero teacher-only prompt or rubric text.
3. The boundary between public benchmark packs and private holdout packs is **machine-auditable**.
4. Future holdout authoring has a named contract to target without inventing ad hoc conventions.

## What this spec IS

- A manifest template and schema for private holdout packs (`benchmarks/private-holdout-pack-template.json`)
- A separation contract between `benchmarks/public-pack-v1/` and `local/private-holdout-packs/`
- An authoring guide for teachers (`docs/private-holdout-authoring.md`)
- A test suite that asserts the boundary (`tests/test_private_holdout_separation.py`)

## What this spec is NOT

- This spec does **not** contain any real holdout prompts, rubrics, or scoring criteria.
- This spec does **not** claim that a private holdout pack already exists or has been scored.
- This spec does **not** widen the public benchmark pack or change evaluation-contract semantics.
- This is **not a sealed certification exam** — it is a scaffold so teachers can author one locally.

## Separation contract

| Property | Public pack | Private holdout pack |
|---|---|---|
| **Tracked by git** | Yes | No — `.gitignore`d under `local/` |
| **Visibility** | `student_visible` | `teacher_only` |
| **Family ID namespace** | `rf.*.public.*` | `rf.*.holdout.*` |
| **Prompt text in tracked files** | Public student-facing prompts only | Zero — template only |
| **Overlap with public families** | N/A | Zero overlap enforced |
| **Evaluation contract** | Shared | Shared — same frozen contract |
| **Promotion direction** | N/A | Failure themes may promote to public curriculum; prompt text never promotes |

## Template schema

The tracked template at `benchmarks/private-holdout-pack-template.json` defines:

- Required top-level fields for a valid holdout pack manifest
- Required fields per holdout family and episode
- Visibility and teacher-only constraints
- The local directory convention (`local/private-holdout-packs/`)
- Forbidden tokens that must never appear in tracked files
- A structural example family shape with zero real content

## Acceptance criteria

- `benchmarks/private-holdout-pack-template.json` exists and is valid JSON with no teacher-only content.
- `docs/private-holdout-authoring.md` exists and references the template, spec, and local directory convention.
- `local/` is `.gitignore`d.
- No tracked file under `benchmarks/` contains teacher-only prompt or rubric text.
- No tracked file under `specs/` or `docs/` quotes real holdout prompt text.
- The template schema is consistent with the authoring doc and this spec.
- `tests/test_private_holdout_separation.py` enforces all of the above.

## Done when

- Teachers can follow `docs/private-holdout-authoring.md` to author a local holdout pack that conforms to the template.
- The test suite passes and proves that tracked files carry zero teacher-only content.
- The separation contract is explicit enough to audit.
- This is honestly a **scaffold**, not a claim that holdout packs are already scored or running.

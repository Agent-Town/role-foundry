# SWE-bench Holdout Extension Process

## What this is

A documented process for teachers to manually curate a **small** set of SWE-bench-derived holdout episodes for teacher-only evaluation. This is an extension of the existing private holdout authoring path (`docs/private-holdout-authoring.md`), not a replacement.

## Honest scope

- SWE-bench is used as a **reference source for teachers only**, not as public curriculum
- Teachers manually select and rewrite a small number of episodes — this is not bulk import
- The derived episodes live in the existing gitignored `benchmarks/private-holdout-pack/` directory
- The student/apprentice never sees SWE-bench-derived content
- This does **not** make Role Foundry an SWE-bench integration or give it SWE-bench compatibility

## What SWE-bench provides

SWE-bench (https://github.com/SWE-bench/SWE-bench) is a benchmark of real GitHub issue-to-patch tasks. It is useful as a reference because:

- Real issue → patch structure mirrors the apprentice's actual work shape
- Evaluation harness ideas inform Role Foundry's scoring design
- Difficulty calibration helps teachers write honest holdout rubrics

## What SWE-bench does NOT provide here

- Public curriculum episodes (all SWE-bench-derived content stays teacher-only)
- Automated evaluation infrastructure (RF's eval loop is separate and demo-grade)
- Sealed certification claims (same constraint as all RF holdouts)
- Full benchmark coverage (teachers pick a small manually curated subset)

## Extension process

### 1. Teacher selects candidate tasks

A teacher reviews SWE-bench tasks and selects **at most 5-10** that are:
- Small enough to be a single coherent slice (not multi-file sprawl)
- Relevant to the current apprentice's work shape (frontend/product for now)
- Not already covered by existing public curriculum families
- Clear enough that a rubric can be written without ambiguity

### 2. Teacher records the extension round in the public-safe planning seam

Before authoring real episodes, the teacher may record the extension round in `benchmarks/holdout-extension-manifest-template.json`.

That tracked file is deliberately limited to:
- source type / source snapshot metadata
- a per-round episode cap
- the suggested family namespace
- pointers to the existing private manifest path
- placeholder private episode ids

It must **not** contain teacher prompts, rubrics, or any episode text.

### 3. Teacher rewrites into RF episode format locally

Each selected task becomes a fresh RF holdout episode in the existing gitignored private manifest. The teacher:
- Writes a **new** `teacher_prompt` in RF's own words (not copied from SWE-bench)
- Creates a `scoring_rubric` with concrete criteria tied to RF's evaluation standards
- Assigns a `family_id` under the `rf.software-engineer.holdout.swebench-derived.*` namespace
- Tags with `source: swe-bench-derived` and the original SWE-bench task ID for provenance
- Sets honest difficulty based on the RF apprentice's current level, not SWE-bench's scale

### 4. Teacher stores in the existing private holdout path

The rewritten episodes go into `benchmarks/private-holdout-pack/holdout-manifest.json`, the same gitignored location used for all teacher-only holdouts. No new storage path is needed.

### 5. Teacher runs separation audit

```bash
python3 scripts/holdout_author.py audit
python3 -m unittest tests/test_private_holdout_separation.py -v
```

Both must pass before using the derived episodes for evaluation.

### 6. Teacher uses episodes in local eval loop

The episodes can be used in the existing autoresearch alpha loop:

```bash
python3 -m runner_bridge.autoresearch_alpha \
  --request benchmarks/private-holdout-pack/local-sealed-alpha-loop.request.json
```

## Public/private split

| What | Where | Visibility |
|------|-------|-----------|
| This process document | `docs/swe-bench-holdout-extension.md` | Public (describes process, no content) |
| Extension planning seam | `benchmarks/holdout-extension-manifest-template.json` | Public (policy + provenance planning only, no episode content) |
| Existing holdout template | `benchmarks/private-holdout-pack-template.json` | Public (schema only for the private manifest) |
| Actual derived episodes | `benchmarks/private-holdout-pack/holdout-manifest.json` | Teacher-only (gitignored) |
| Separation tests | `tests/test_private_holdout_separation.py` | Public (verifies no leaks) |

## Constraints

1. **Maximum 10 derived episodes per extension round** — this is intentionally small
2. **All prompts must be rewritten** — no verbatim SWE-bench task text in RF episodes
3. **Teacher-only always** — SWE-bench-derived episodes never enter public curriculum
4. **Provenance tracked** — every derived episode tags its SWE-bench source ID
5. **Same audit path** — existing separation tests must pass after every addition

## What this does NOT give you

- A claim that Role Foundry "uses SWE-bench" as a public benchmark
- Automated SWE-bench evaluation infrastructure
- Bulk import of SWE-bench tasks
- Student-visible SWE-bench content
- Sealed certification based on SWE-bench performance

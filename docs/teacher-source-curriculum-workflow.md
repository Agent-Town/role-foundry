# Teacher-Source Curriculum Workflow

How teachers discover, curate, and promote external sources into Role Foundry curriculum.

## Task lifecycle states

The formal lifecycle is defined machine-readably in `data/curriculum/frontend-product-engineer-teacher-task-lifecycle.v1.json`. Tests enforce it.

```
draft → intake_recorded → promoted → seed_defined → executed → scored
                                                        ↑               |
                                                        └── (failure) ──┘
```

| State | What exists | Who acts |
|-------|------------|----------|
| `draft` | Partially filled task packet from template | Teacher |
| `intake_recorded` | Source record linking task to spec acceptance test | Teacher |
| `promoted` | Promotion record confirming task is public-safe | Teacher |
| `seed_defined` | Task packet in public seed registry, student-visible | Teacher (frozen) |
| `executed` | Candidate run in isolated workspace *(future)* | Student + runtime |
| `scored` | Scorecard against frozen evaluation contract *(future)* | Teacher |

**Implemented today:** draft through seed_defined (20 tasks). Executed and scored states have schemas defined but no live runtime yet.

## The source-intake loop

```
discover → curate → promote
```

1. **Discover**: A teacher identifies a public source that could strengthen the apprentice's curriculum. Record it in the source intake log with license, URL, and discovery notes.

2. **Curate**: The teacher reviews the source for suitability, confirms licensing is clean, and plans how to convert it into RF-shaped episodes. Mark it `curated` in the intake log. If the source requires manual curation (e.g., GitHub threads with ambiguous downstream rights), mark `manual_curation_only: true`.

3. **Promote**: The teacher authors original RF episodes grounded in the source, adds them to the benchmark pack and episode registry with explicit provenance, and marks the intake record `promoted`. The promoted family appears in the public benchmark pack.

## Where things live

| Artifact | Path | Purpose |
|----------|------|---------|
| Source intake log | `data/source-research/software-engineer-source-intake.v1.json` | Tracks every candidate source from discovery through promotion |
| Episode family registry | `benchmarks/public-pack-v1/episode-family-registry.json` | Defines families, promotion criteria, and blocked status |
| Benchmark pack | `benchmarks/public-pack-v1/benchmark-pack.json` | The public-safe episode pack used in autoresearch loops |
| Episode registry | `data/episode-registry/public-benchmark-pack-v1.json` | Rubric templates, provenance, and episode-to-rubric mappings |
| Seed | `seed/role-foundry-apprentice.json` | Canonical scenario definitions (t1–t9, h1–h3) |
| Curriculum sources doc | `docs/software-engineer-curriculum-sources.md` | Ranked candidate analysis and ingestion guidance |
| Task lifecycle contract | `data/curriculum/frontend-product-engineer-teacher-task-lifecycle.v1.json` | Formal workflow states and transition rules for task authoring |
| Refresh receipt schema | `data/curriculum/frontend-product-engineer-private-holdout-refresh-receipt.schema.v1.json` | Machine-readable shape for weekly holdout refresh receipts |
| Holdout authoring script | `scripts/holdout_author.py` | init, audit, status, refresh commands for local holdout management |

## Provenance rules

Every promoted episode must have:

- **Source license**: explicitly stated in the intake record and episode provenance
- **RF authorship**: episodes are original RF-authored work, not copied prose
- **Source-backed-by reference**: links back to the intake record and source URL
- **No teacher-only inputs**: public episodes must not use teacher-only prompt text or rubric content

## Manual-curation-only sources

Some sources (e.g., GitHub issue/PR threads) cannot be bulk-ingested because:
- Licensing is ambiguous for discussion text
- Quality is noisy and hard to attribute
- Public visibility ≠ clean downstream training rights

For these sources:
- Mark `manual_curation_only: true` in the intake record
- A teacher must manually select specific items (≤10) and rewrite them as original RF episodes
- Do not import raw text, patches, or discussion verbatim

## Teacher-only holdout direction (SWE-bench)

SWE-bench material is available as a **teacher-only holdout direction only**:

- **NOT public curriculum**: SWE-bench-derived episodes must never appear in the public benchmark pack, student-visible curriculum, or demo data
- **Manual curation only**: A teacher manually selects a small number of SWE-bench task instances relevant to the current apprentice role
- **Original RF authorship**: Selected instances are rewritten as original RF-authored holdout episodes
- **Separate storage**: Holdout episodes go in the local private holdout manifest (`benchmarks/private-holdout-pack-template.json`) or a separate teacher-only pack, never in the public pack
- **Explicit labeling**: The intake record at `data/source-research/software-engineer-source-intake.v1.json#intake-swebench-teacher-holdout` documents this direction with `status: blocked_teacher_only_holdout`

### Where SWE-bench-derived holdouts plug in

```
Source intake log (blocked_teacher_only_holdout)
  → Teacher manually selects ≤10 task instances
  → Rewrites each as an original RF-authored holdout episode
  → Stores in: benchmarks/private-holdout-pack-template.json (local, gitignored)
  → Never appears in: benchmarks/public-pack-v1/* or app/data.js
```

This seam is visible but blocked. No SWE-bench-derived content ships in the public pack until a teacher manually curates it through this process.

## Weekly holdout refresh

Private holdouts need regular refresh to stay honest. The refresh workflow and receipt schema are defined in:

- **Receipt schema**: `data/curriculum/frontend-product-engineer-private-holdout-refresh-receipt.schema.v1.json`
- **Template with refresh metadata**: `benchmarks/private-holdout-pack-template.json`
- **Authoring script**: `scripts/holdout_author.py refresh`

### Refresh workflow

1. Generate a receipt stub: `python3 scripts/holdout_author.py refresh --teacher robin`
2. Review existing holdout episodes for staleness or leakage
3. Retire leaked/stale episodes, author fresh replacements if needed
4. Run `python3 scripts/holdout_author.py audit` to confirm no leaks
5. Fill in the receipt with action counts and audit result
6. Bump the pack version

### What the receipt records (and does not record)

The receipt records **counts and timestamps** — how many episodes were reviewed, retired, added, rewritten — plus whether the audit passed. It does **not** contain holdout prompts, rubrics, or any teacher-only content. Receipt IDs and retirement reasons are safe metadata.

### What is tracked vs local

| Artifact | Tracked in git? | Contains holdout content? |
|----------|----------------|--------------------------|
| Refresh receipt schema | Yes | No — defines the shape only |
| Holdout pack template (with refresh_metadata) | Yes | No — placeholders only |
| holdout_author.py | Yes | No — tooling only |
| Actual refresh receipts | No (local-only) | No — counts and timestamps |
| Holdout manifest + episodes | No (local-only) | Yes — teacher-only |

## Who can do this

Any teacher can follow this workflow. The process is not unique to Robin or Neo — it is designed so that additional teachers can:

1. Add new intake records to the source intake log
2. Author original RF episodes grounded in curated sources
3. Promote episodes into the public benchmark pack with explicit provenance
4. Propose teacher-only holdout candidates through the manual curation path

The intake log, episode registry, and benchmark pack are the shared coordination points.

## Current state

| Source | Status | Family |
|--------|--------|--------|
| Playwright docs (Apache-2.0) | **Promoted** | `rf.frontend-apprentice.public.playwright-regression` (2 episodes) |
| Google Eng Practices (CC BY 3.0) | **Promoted** | `rf.frontend-apprentice.public.code-review-discipline` (2 episodes) |
| Alpine.js docs/examples (MIT) | **Promoted** | `rf.frontend-apprentice.public.alpine-state-patterns` (2 episodes; manual rewrite from docs/examples only) |
| SWE-bench (MIT harness) | Blocked — teacher-only holdout direction | — (no episodes authored; seam documented) |

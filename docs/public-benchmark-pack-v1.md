# Public Benchmark Pack v1

This repo now has a first **public-safe benchmark pack** for the Frontend Apprentice.

The honesty line is simple:

- **benchmark-ready now:** public curriculum families only
- **blocked / rewrite-needed:** any teacher-only or holdout-derived family whose framing is already visible in this public repo
- **not claimed:** sealed certification, partner-track work, or fresh hidden-eval integrity from the current public holdout families
- **plainly:** this pack is **not a sealed certification** pack

## What is benchmark-ready now

`benchmarks/public-pack-v1/benchmark-pack.json` currently contains **12 concrete student-visible episodes** across **6 public-ready families**:

- `rf.frontend-apprentice.public.landing-story`
  - make the dogfood apprentice loop obvious
- `rf.frontend-apprentice.public.curriculum-split`
  - clarify student-visible vs teacher-only surfaces
- `rf.frontend-apprentice.public.score-deltas`
  - make iteration deltas legible
- `rf.frontend-apprentice.public.proof-bundle`
  - make receipts and audit evidence legible
- `rf.frontend-apprentice.public.demo-honesty`
  - refuse fake live claims and keep slices narrow
- `rf.frontend-apprentice.public.failure-to-curriculum`
  - promote sanitized lessons into public curriculum

These are appropriate for:

- public autoresearch loops
- public regression checks
- copy / UI / artifact-pack tuning
- dogfood iteration on the Frontend Apprentice vertical

## Companion episode registry

`data/episode-registry/public-benchmark-pack-v1.json` is the companion registry for the pack.

It carries the audit surface the student-facing manifest alone cannot:

- **6 public rubric templates** — one per public family
- **normalized weights** — every template sums to `1.0`
- **12/12 rubric mappings** — every shipped public episode points at a complete public rubric
- **12/12 provenance mappings** — every shipped public episode cites its public training seed scenario plus public spec/doc references
- **100% family readiness coverage** — every candidate family has an explicit readiness state
- **no teacher-only fields** — the registry stays public-safe and never includes hidden prompt text or teacher-side scoring rubrics

For the registry contract itself, see `docs/dataset-episode-registry.md`.

## Phase B acceptance snapshot

The pack now leaves explicit **B001–B006** evidence behind instead of asking a reader to infer it:

- **B001 — Public episode count:** pass
  - 12 public episodes shipped across 6 families
  - floor remains `>= 10` episodes in the forward spec
- **B002 — Rubric completeness:** pass
  - 6 public rubric templates cover all 12 public episodes
- **B003 — Weight normalization:** pass
  - every public rubric template sums to `1.0`
- **B004 — Public/teacher split integrity:** pass
  - 6 `student_visible` families included
  - 3 `teacher_only` families remain excluded
  - leak audit outcome: `pass` with `0` teacher-only field hits and `0` teacher-only token hits in tracked public pack artifacts
- **B005 — Provenance coverage:** pass
  - 12/12 public episodes cite training-seed + public spec/doc provenance
  - actual public provenance coverage: `100%`
- **B006 — Promotion readiness clarity:** pass, with named limits
  - ready to promote as the repo’s **public-safe benchmark pack** for public regression/training use
  - still blocked from sealed certification or fresh hidden-eval integrity claims
  - every family declares an explicit readiness state from the allowed set: `draft`, `benchmark_ready`, `rewrite_before_holdout_promotion`, `blocked`

## What is blocked

`benchmarks/public-pack-v1/episode-family-registry.json` also lists **3 blocked teacher-only families** derived from the current `h1` / `h2` / `h3` holdout scenarios.

They are blocked because the current repo already exposes their framing. That means we cannot honestly market them as either:

- sealed eval families
- public-safe benchmark families

For compatibility, the legacy family `status` remains `blocked_pending_rewrite`, while the explicit readiness state for promotion planning is `rewrite_before_holdout_promotion`.

## Why this split matters

The existing repo proves the **contract** for student-visible vs teacher-only separation.

It does **not** give us a clean public sealed-eval pack, because the current holdout families are already repo-visible. So the honest move is:

1. ship a real public benchmark pack now
2. keep teacher-only / holdout-derived families out of that pack
3. attach public rubrics, provenance, leak-audit evidence, and readiness states so the pack is audit-friendly instead of hand-wavy
4. rewrite fresh teacher-only families later outside the public student pack

That keeps the benchmark story honest.

## Suggested autoresearch loop

Use the pack like this:

1. Pick one public episode from `benchmark-pack.json`.
2. Check its companion provenance/rubric entry in `data/episode-registry/public-benchmark-pack-v1.json`.
3. Keep the mutation surface narrow.
4. Do only student-visible/public-safe work.
5. Record changed files plus a short keep/discard note.
6. Run the verifier commands listed in the pack.
7. If a failure theme emerges, promote only the sanitized lesson into public curriculum.

## Validation

Run:

```bash
python3 -m unittest tests/test_public_benchmark_pack_v1.py -v
python3 -m unittest tests/test_milestone3_contract.py tests/test_milestone5_teacher_eval_loop.py -v
```

## Files

- `benchmarks/public-pack-v1/episode-family-registry.json`
- `benchmarks/public-pack-v1/benchmark-pack.json`
- `data/episode-registry/public-benchmark-pack-v1.json`
- `docs/dataset-episode-registry.md`
- `specs/008-public-benchmark-pack-v1.md`
- `tests/test_public_benchmark_pack_v1.py`

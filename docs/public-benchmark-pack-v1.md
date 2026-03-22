# Public Benchmark Pack v1

This repo now has a first **public-safe benchmark pack** for the Frontend Apprentice.

The important honesty line:

- **benchmark-ready now:** public curriculum families only
- **blocked / pending rewrite:** any teacher-only or holdout-derived family whose framing is already visible in this public repo
- **not claimed:** sealed certification, partner-track work, or fresh hidden-eval integrity from the current public holdout families
- **plainly:** this pack is **not a sealed certification** pack

## What is benchmark-ready now

`benchmarks/public-pack-v1/benchmark-pack.json` contains **12 concrete student-visible episodes** across **6 public-ready families**:

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

## What is blocked

`benchmarks/public-pack-v1/episode-family-registry.json` also lists **3 blocked teacher-only families** derived from the current `h1` / `h2` / `h3` holdout scenarios.

They are blocked because the current repo already exposes their framing. That means we cannot honestly market them as either:

- sealed eval families
- public-safe benchmark families

Each blocked family is marked `blocked_pending_rewrite` and includes rewrite requirements.

## Why this split matters

The existing repo proves the **contract** for student-visible vs teacher-only separation.

It does **not** yet give us a clean public sealed-eval pack, because the current holdout families are already repo-visible. So the right move is:

1. ship a real public benchmark pack now
2. keep teacher-only / holdout-derived families out of that pack
3. rewrite fresh teacher-only families later outside the public student pack

That keeps the benchmark story honest.

## Local private holdout path

Fresh teacher-only holdouts now have a **local-only scaffold**:

- public schema template: `benchmarks/private-holdout-pack-template.json`
- private local manifest path: `benchmarks/private-holdout-pack/holdout-manifest.json`
- git rule: `benchmarks/private-holdout-pack/` is ignored and should never be committed

The template is only a contract shape. Actual teacher-only prompts and rubrics belong only in the gitignored local manifest, and this repo still makes **no sealed certification claim**.

## Suggested autoresearch loop

Use the pack like this:

1. Pick one public episode from `benchmark-pack.json`.
2. Keep the mutation surface narrow.
3. Do only student-visible/public-safe work.
4. Record changed files plus a short keep/discard note.
5. Run the verifier commands listed in the pack.
6. If a failure theme emerges, promote only the sanitized lesson into public curriculum.

## Validation

Run:

```bash
python3 -m unittest tests/test_public_benchmark_pack_v1.py
python3 -m unittest tests/test_private_holdout_separation.py
python3 -m unittest tests/test_milestone3_contract.py tests/test_milestone5_teacher_eval_loop.py tests/test_autoresearch_alpha_loop.py
```

## Files

- `benchmarks/public-pack-v1/episode-family-registry.json`
- `benchmarks/public-pack-v1/benchmark-pack.json`
- `benchmarks/private-holdout-pack-template.json`
- `specs/008-public-benchmark-pack-v1.md`
- `specs/012-private-holdout-pack.md`
- `tests/test_public_benchmark_pack_v1.py`
- `tests/test_private_holdout_separation.py`

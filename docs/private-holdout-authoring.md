# Private Holdout Authoring Guide

## What this is

A local-only teacher-only holdout authoring path. Teachers can create fresh evaluation episodes that never enter the public repo. This is **not** a sealed certification exam — it is a local evaluation scaffold.

## Safe-to-push vs local-only

### Safe to push (tracked in git)

| File | Purpose |
|------|---------|
| `benchmarks/private-holdout-pack-template.json` | Schema template — no real content |
| `specs/012-private-holdout-pack.md` | Contract spec — states what is/isn't claimed |
| `tests/test_private_holdout_separation.py` | Leak-audit tests proving public artifacts are clean |
| `scripts/holdout_author.py` | Local authoring helper (init, audit, status) |
| `docs/private-holdout-authoring.md` | This guide |

### Local-only (gitignored, NEVER push)

| File | Purpose |
|------|---------|
| `benchmarks/private-holdout-pack/holdout-manifest.json` | Actual teacher-only episodes, prompts, rubrics |
| `benchmarks/private-holdout-pack/episodes/*.json` | Individual episode files (optional) |

The `.gitignore` excludes `benchmarks/private-holdout-pack/`. If you see those files in `git status`, something is wrong.

## Authoring workflow

### 1. Initialize a local manifest

```bash
python3 scripts/holdout_author.py init
```

This copies the public template into the gitignored directory. Use `--force` to overwrite an existing manifest, or `--version N` to set the pack version.

### 2. Author fresh episodes

Edit `benchmarks/private-holdout-pack/holdout-manifest.json`:

- Replace every `REPLACE-ME` placeholder with real content
- Use **new wording** — do not clone the repo-visible h1/h2/h3 framing
- Each episode needs: `id`, `family_id`, `title`, `teacher_prompt`, `scoring_rubric`, `difficulty`
- Family ids must be fresh (e.g. `rf.frontend-apprentice.holdout.fresh-001`), not the blocked `h1`/`h2`/`h3` ids

### 3. Audit for leaks

```bash
python3 scripts/holdout_author.py audit
```

This checks:
- `.gitignore` excludes the private directory
- No private files are tracked by git
- No tracked benchmark JSON contains teacher-only keys
- The manifest schema is valid
- Episodes reference fresh families (not blocked h1/h2/h3 clones)
- Teacher prompt text does not appear in any tracked file

### 4. Check status

```bash
python3 scripts/holdout_author.py status
```

Shows what exists locally, what is tracked, and whether anything has leaked.

### 5. Run separation tests

```bash
python3 -m unittest tests/test_private_holdout_separation.py -v
```

These tests enforce the separation contract from spec 012. They pass in CI (where no local manifest exists) and also validate the manifest schema when one is present.

### 6. Run a local private-holdout alpha loop

Create a local-only request file such as `benchmarks/private-holdout-pack/local-sealed-alpha-loop.request.json`.

Key points:
- set top-level `private_holdout_manifest` to your local manifest path
- keep the request file itself under `benchmarks/private-holdout-pack/`
- in `baseline-eval` and `candidate-teacher-eval`, reference holdout episodes by `id`
- only store replay outcome fields in the request (`passed`, `score`, `teacher_notes`, optional public failure theme/summary)
- let `runner_bridge.autoresearch_alpha` hydrate `teacher_prompt` and `scoring_rubric` from the local manifest into `request.private.json`

Then run:

```bash
python3 -m runner_bridge.autoresearch_alpha \
  --request benchmarks/private-holdout-pack/local-sealed-alpha-loop.request.json \
  --artifacts-root runtime/autoresearch-alpha/local-private-holdout
```

Honest claim boundary:
- this proves a **local private-holdout** execution path
- it does **not** prove sealed certification or tamper-proof evaluation

## What makes a good holdout episode

- **Fresh wording**: The prompt must not be derivable from anything in the public repo
- **Non-trivial rubric**: `scoring_rubric` should have concrete criteria, not an empty object
- **Honest difficulty**: Tag as `easy`, `medium`, or `hard` — don't inflate
- **Distinct family**: Use a new `family_id` that has no public-repo counterpart

## What this does NOT give you

- A sealed certification pipeline (no proctor, no tamper-proofing)
- Partner-ready evaluation (no external audit, no SLA)
- Automated scoring integration (the eval loop exists but is demo-grade)
- Resolution of the blocked h1/h2/h3 families (they need full rewrites stored only locally)

## Blockers for true sealed evaluation

1. **Proctor / tamper-proofing**: No mechanism prevents a teacher from leaking their own holdout content
2. **Automated scoring**: The runner bridge eval loop is demo-only, not production-grade
3. **External audit**: No third-party has reviewed or certified the evaluation path
4. **Fresh family authoring at scale**: Only the scaffold exists; real content must be authored

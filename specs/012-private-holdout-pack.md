# Spec 012 — Private Holdout Pack Contract

## Intent

Define the contract for teacher-only holdout evaluation material that must never appear in the public repo, the public benchmark pack, or any student-visible artifact.

## Background

Public benchmark pack v1 (spec 008) ships 6 public families and 12 episodes. Three holdout-derived families are `blocked_pending_rewrite` because their framing is already repo-visible. To unblock honest sealed evaluation, fresh teacher-only material must be authored with new wording and kept out of all tracked public repo artifacts.

## What this spec claims

- A **contract shape** for private holdout packs exists in the public repo as a template.
- Actual teacher-only content lives in `benchmarks/private-holdout-pack/`, which is **gitignored** and never committed.
- The public repo contains **no** teacher-only prompt text, scoring rubrics, or holdout episode content.
- This is **not** a sealed certification exam. It is a local teacher-only evaluation path.

## What this spec does NOT claim

- That a full sealed-eval pipeline exists today.
- That the private holdout content is production-grade or partner-ready.
- That the blocked holdout-derived families are resolved — they require fresh rewrites stored only in the private path.

## Contract

### Public artifacts (tracked in git)

| Artifact | Path | Purpose |
|----------|------|---------|
| Manifest template | `benchmarks/private-holdout-pack-template.json` | Schema/shape for private packs — no actual content |
| This spec | `specs/012-private-holdout-pack.md` | States what is and is not claimed |
| Separation tests | `tests/test_private_holdout_separation.py` | Proves public artifacts contain no teacher-only content |
| Gitignore entry | `.gitignore` | Excludes `benchmarks/private-holdout-pack/` contents |

### Private artifacts (local-only, gitignored)

| Artifact | Path | Purpose |
|----------|------|---------|
| Holdout manifest | `benchmarks/private-holdout-pack/holdout-manifest.json` | Actual teacher-only episodes, prompts, rubrics |
| Episode files | `benchmarks/private-holdout-pack/episodes/*.json` | Individual holdout episode content |

### Manifest schema

The private holdout manifest must conform to this shape:

```json
{
  "meta": {
    "id": "private-holdout-pack-v<N>",
    "version": "<semver>",
    "visibility": "teacher_only",
    "public_repo_safe": false,
    "honesty_note": "<states what this pack is and is not>"
  },
  "episodes": [
    {
      "id": "<unique episode id>",
      "family_id": "<family reference>",
      "title": "<title>",
      "teacher_prompt": "<the sealed prompt text>",
      "scoring_rubric": { ... },
      "difficulty": "<easy|medium|hard>",
      "tags": [...]
    }
  ]
}
```

### Separation invariants (tested)

1. No tracked benchmark JSON file contains actual teacher-only prompt or rubric content; the only allowed mention of `teacher_prompt` / `scoring_rubric` in tracked artifacts is the explicit placeholder template.
2. The public benchmark pack (`benchmark-pack.json`) contains only `student_visible` families.
3. The `.gitignore` excludes `benchmarks/private-holdout-pack/`.
4. The manifest template contains **no** actual episode content — only schema documentation and placeholder values.
5. No tracked file anywhere in the repo contains the literal content of any private holdout episode.

## Generation path

To create a private holdout pack locally:

1. Run `python3 scripts/holdout_author.py init` to scaffold a manifest from the public template.
2. Author fresh teacher-only episodes with new wording (not derived from repo-visible h1/h2/h3 framing).
3. Run `python3 scripts/holdout_author.py audit` to check for leaks and schema conformance.
4. Run `python3 -m unittest tests/test_private_holdout_separation.py` to verify no leakage.
5. Use the manifest with the existing local evaluation flow for teacher-only scoring.

See `docs/private-holdout-authoring.md` for the full workflow guide.

## Acceptance criteria

- `.gitignore` excludes the private holdout directory.
- A public manifest template exists with no actual content.
- Tests prove public artifacts are clean of teacher-only material.
- The spec is honest: no sealed-exam claims, no partner-track claims.

## Done when

Role Foundry can honestly say: there is a defined path for teacher-only holdout evaluation that keeps private material out of the public repo, and tests prove the separation holds.

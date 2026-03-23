# Draft PR / submission summary

Status: draft
Audience: PR description, submission notes, or judge-facing written summary

## Summary

This packaging pass turns the finished submission lanes into one cleaner review branch without waiting on the separate `role-foundry-holdout-story-alignment` top-off merge.

What is proven on this branch:
- Role Foundry is framed honestly as a **role-training / eval / promotion** system
- the first concrete shipped role is a **Software Engineer apprentice** improving Role Foundry itself
- the repo contains an executable **public alpha loop** with baseline -> candidate -> teacher-eval -> better/equal/worse comparison proof on a public rail
- the repo contains a **local private-holdout** separation contract that keeps teacher-only prompts out of tracked and student-visible artifacts
- the integrated branch now carries one tracked external roundtrip proof indexed in `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`, sourced from `origin/review/clawith-vibe-roundtrip-demo-20260323-1000` @ `4dab2a9866b86df4525d9698a7c844ab538ac61c`
- the submission packet now has fill-ready drafts for demo, metadata, conversation log, evidence manifest, and final go/no-go review

What remains intentionally pending:
- replacing the remaining `FILL_FINAL_REVIEW_*` placeholders in final publish artifacts
- the later top-off merge from `role-foundry-holdout-story-alignment`

Explicit non-claims:
- no claim of **native Clawith parity**
- no claim of **native model-pool bring-up completion**
- no claim of **sealed certification**
- no claim of **tamper-proof** or **third-party-sealed** evaluation

## Reviewer note

This lane is intentionally conservative: it merges claim scrub, roundtrip proof fold, and demo packet prep, but leaves holdout-story alignment for the later top-off merge.

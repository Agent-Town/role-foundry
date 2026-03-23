# Draft PR / submission summary

Status: draft
Audience: PR description, submission notes, or judge-facing written summary

## Summary

This packaging pass makes the Role Foundry submission materially easier to review without touching the active roundtrip-proof branch surgery.

What is proven on this branch:
- Role Foundry is framed honestly as a **role-training / eval / promotion** system
- the first concrete shipped role is a **Software Engineer apprentice** improving Role Foundry itself
- the repo contains an executable **public alpha loop** with baseline -> candidate -> teacher-eval -> better/equal/worse comparison proof on a public rail
- the repo contains a **local private-holdout** separation contract that keeps teacher-only prompts out of tracked and student-visible artifacts
- the submission packet now has fill-ready drafts for demo, metadata, conversation log, evidence manifest, and final go/no-go review

What this branch prepares but does not itself prove yet:
- the external **Clawith -> OpenClaw -> Claude/vibecosystem** roundtrip proof slot is drafted and ready to fill from `FILL_ROUNDTRIP_BRANCH` / `FILL_ROUNDTRIP_COMMIT` once that active lane lands

Explicit non-claims:
- no claim of **native Clawith parity**
- no claim of **native model-pool bring-up completion**
- no claim of **sealed certification**
- no claim of **tamper-proof** or **third-party-sealed** evaluation

## Reviewer note

This lane is intentionally additive: mostly new files under `submission/drafts/` and `submission/checklists/`, with placeholders for the live roundtrip artifacts that are still being folded elsewhere.

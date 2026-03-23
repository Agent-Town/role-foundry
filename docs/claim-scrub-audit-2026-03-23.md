# Claim scrub audit — 2026-03-23

## Scope

Narrow honesty pass on the review branch based on `origin/review/submission-readiness-pass-20260323-0910`.

This note intentionally avoids the active roundtrip-proof fold lane. It records what the repo can honestly say now, what is still blocked, and which overlap-prone files were left alone.

## Honestly proven on this branch

- A **public benchmark pack v1** exists for public training / regression use.
- The repo has an executable **public alpha loop** with an integrity gate that allows public-regression claims while blocking sealed-eval / sealed-certification claims.
- The repo defines a **local private-holdout scaffold**: fresh teacher-only holdouts can be authored locally, kept gitignored, and kept out of student-visible / tracked artifacts.
- The live/browser lane is still **adapter-first and read-only**. The repo can honestly show configured exports / receipts without claiming native upstream Clawith parity.

## Still blocked / not proven here

- **Native Clawith parity** or native Role Foundry model-pool bring-up.
- **Sealed / tamper-proof / certified evaluation** of any kind.
- Stronger **fresh hidden-eval integrity** claims based on repo-visible holdout samples alone.
- **External gateway / vibecosystem roundtrip proof** until the active roundtrip lane lands real evidence.

## Narrow fixes made in this pass

- Softened the app copy so the UI no longer implies that the current branch already proves sealed-eval status.
- Clarified that repo-visible holdout cards are **judge previews / demo samples**, while fresh private holdouts belong only in the local gitignored path.
- Reworded scorecard and overview copy so it distinguishes:
  - public-regression movement proven now
  - stronger teacher-only holdout evidence possible locally
  - sealed-certification claims still blocked

## Intentionally left untouched to avoid overlap with the active proof-fold lane

These files were left alone because they are already in the live roundtrip-proof lane or are tightly coupled to it:

- `README.md`
- `docs/clawith-vibecosystem-real-path.md`
- `docs/conversation-log.md`
- `scripts/clawith_link_openclaw.py`
- `scripts/clawith_vibe_once.py`
- `scripts/clawith_ws_roundtrip.js`
- `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`
- `submission/conversation-log.template.md`
- `submission/evidence-proof-manifest.template.json`
- `submission/honest-claim-boundary-checklist.md`
- `submission/submission-base-merge-review-checklist.md`
- `submission/submission-metadata.template.json`

## Residual risk worth a later pass

- `README.md` still carries some broad framework language around sealed holdouts / proof that should be re-read once the active proof-fold lane lands.
- Demo/sample data still necessarily talks about holdouts because the product concept depends on that split; future cleanup should keep checking that sample language does not get mistaken for sealed-eval certification or native-parity proof.

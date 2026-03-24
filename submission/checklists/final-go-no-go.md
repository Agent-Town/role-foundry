# Final submission go / no-go checklist

Use this right before merging the final submission branch or publishing the submission packet.
If any required item is false, it is a **no-go**.

## 1. Demo coherence

- [x] The demo opener describes Role Foundry as a **role-training / eval / promotion** system.
- [x] The demo opener makes the generation provenance chain explicit: receipts, evaluation context, score deltas, promotion decision.
- [x] The first concrete role is described as **Software Engineer apprentice**.
- [x] The honest scope note remains intact: the shipped public curriculum is still frontend/product-heavy.
- [x] The walkthrough shows the **public alpha loop** as the current executable proof.
- [x] The walkthrough shows the **local private-holdout** boundary as a local-only honesty boundary.
- [x] The walkthrough shows the staged **ERC-8004 / Base issuance path** without implying live minting.
- [x] The external roundtrip section cites exact branch, commit, artifact path, and entrypoint.

## 2. Claim boundary

- [x] Every current claim is backed by a repo path, test, or captured artifact.
- [x] The final materials still say the roundtrip proof is **external Clawith -> OpenClaw -> Claude/vibecosystem**, not native parity.
- [x] The final materials do **not** claim live Base minting.
- [x] The final materials do **not** claim partner-track completion.
- [x] The final materials do **not** claim native Clawith parity.
- [x] The final materials do **not** claim native model-pool completion unless separate proof is added.
- [x] The final materials do **not** claim sealed certification.
- [x] The final materials do **not** claim tamper-proof or third-party-sealed evaluation.

## 3. Proof inventory

- [x] Public alpha loop proof is cited with exact source files.
- [x] Private-holdout separation proof is cited with exact source files.
- [x] ERC-8004 / Base staged-issuance proof is cited with exact source files.
- [x] Roundtrip proof is cited with exact artifact paths and exact commit SHA.
- [x] Reviewer-facing proof paths point at `submission/clawith-vibecosystem-roundtrip-proof.manifest.json` and `submission/roundtrip-proof/`, not raw `artifacts/...` dirs.
- [x] Any placeholder `FILL_*` tokens have been removed from final user-facing artifacts.

## 4. Submission packet completeness

- [x] `submission/judge-demo-script.md` is the canonical live walkthrough.
- [x] `submission/judge-qa-note.md` is the canonical short-answer support note.
- [x] `submission/pr-or-submission-summary.md` is the canonical written summary.
- [x] `submission/conversation-log.md` is the canonical final conversation log.
- [x] `submission/evidence-proof-manifest.json` is the canonical final proof inventory.
- [x] `submission/submission-metadata.json` is the canonical final metadata file.
- [x] `submission/drafts/` is clearly archived and no longer the canonical packet.
- [x] The final packet distinguishes **repo-visible proof** from **local-only proof**.

## 5. Hygiene

- [x] JSON packet files validate.
- [x] Markdown packet files are readable and placeholder-free where required.
- [x] `git diff --check` is clean.
- [x] The dirty root checkout was never edited by this lane.
- [x] Final branch is pushed and the exact commit SHA is recorded.

## Go / no-go rule

- **GO** only if every required box above is true.
- **NO-GO** if any proof claim depends on oral explanation, unpublished local state, or still-unfilled placeholders.

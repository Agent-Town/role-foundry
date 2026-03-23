# Final submission go / no-go checklist

Use this right before merging the final submission branch or publishing the submission packet.
If any required item is false, it is a **no-go**.

## 1. Demo coherence

- [ ] The demo opener describes Role Foundry as a **role-training / eval / promotion** system.
- [ ] The first concrete role is described as **Software Engineer apprentice**.
- [ ] The honest scope note remains intact: the shipped public curriculum is still frontend/product-heavy.
- [ ] The walkthrough shows the **public alpha loop** as the current executable proof.
- [ ] The walkthrough shows the **local private-holdout** boundary as a local-only honesty boundary.
- [ ] The external roundtrip section cites exact branch, commit, artifact path, and entrypoint.

## 2. Claim boundary

- [ ] Every current claim is backed by a repo path, test, or captured artifact.
- [ ] The final materials still say the roundtrip proof is **external Clawith -> OpenClaw -> Claude/vibecosystem**, not native parity.
- [ ] The final materials do **not** claim native Clawith parity.
- [ ] The final materials do **not** claim native model-pool completion unless separate proof is added.
- [ ] The final materials do **not** claim sealed certification.
- [ ] The final materials do **not** claim tamper-proof or third-party-sealed evaluation.

## 3. Proof inventory

- [ ] Public alpha loop proof is cited with exact source files.
- [ ] Private-holdout separation proof is cited with exact source files.
- [ ] Roundtrip proof is cited with exact artifact paths and exact commit SHA.
- [ ] Any placeholder `FILL_*` tokens have been removed from final user-facing artifacts.

## 4. Submission packet completeness

- [ ] `submission/drafts/judge-demo-script.md` has been finalized or copied into the final packet.
- [ ] `submission/drafts/pr-or-submission-summary.md` has been finalized.
- [ ] `submission/drafts/conversation-log.roundtrip-ready.md` has been finalized.
- [ ] `submission/drafts/evidence-proof-manifest.roundtrip-ready.json` has been finalized.
- [ ] `submission/drafts/submission-metadata.roundtrip-ready.json` has been finalized.
- [ ] The final packet distinguishes **repo-visible proof** from **local-only proof**.

## 5. Hygiene

- [ ] JSON drafts validate.
- [ ] Markdown drafts are readable and placeholder-free where required.
- [ ] `git diff --check` is clean.
- [ ] The dirty root checkout was never edited by this lane.
- [ ] Final branch is pushed and the exact commit SHA is recorded.

## Go / no-go rule

- **GO** only if every required box above is true.
- **NO-GO** if any proof claim depends on oral explanation, unpublished local state, or still-unfilled placeholders.

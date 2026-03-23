# Final submission go / no-go checklist

Use this right before merging the final submission branch or publishing the submission packet.
If any required item is false, it is a **no-go**.

Human/admin handoff items are tracked separately in `submission/checklists/final-publish-todo.md`.

## 1. Demo coherence

- [ ] The demo opener describes Role Foundry as a **role-training / eval / promotion** system.
- [ ] The demo opener makes the generation provenance chain explicit: receipts, evaluation context, score deltas, promotion decision.
- [ ] The first concrete role is described as **Software Engineer apprentice**.
- [ ] The honest scope note remains intact: the shipped public curriculum is still frontend/product-heavy.
- [ ] The walkthrough shows the **public alpha loop** as the current executable proof.
- [ ] The walkthrough shows the **local private-holdout** boundary as a local-only honesty boundary.
- [ ] The walkthrough shows the staged **ERC-8004 / Base issuance path** without implying live minting.
- [ ] The external roundtrip section cites exact branch, commit, artifact path, and entrypoint.

## 2. Claim boundary

- [ ] Every current claim is backed by a repo path, test, or captured artifact.
- [ ] The final materials still say the roundtrip proof is **external Clawith -> OpenClaw -> Claude/vibecosystem**, not native parity.
- [ ] The final materials do **not** claim live Base minting.
- [ ] The final materials do **not** claim partner-track completion.
- [ ] The final materials do **not** claim native Clawith parity.
- [ ] The final materials do **not** claim native model-pool completion unless separate proof is added.
- [ ] The final materials do **not** claim sealed certification.
- [ ] The final materials do **not** claim tamper-proof or third-party-sealed evaluation.

## 3. Proof inventory

- [ ] Public alpha loop proof is cited with exact source files.
- [ ] Private-holdout separation proof is cited with exact source files.
- [ ] ERC-8004 / Base staged-issuance proof is cited with exact source files.
- [ ] Roundtrip proof is cited with exact artifact paths and exact commit SHA.
- [ ] Reviewer-facing proof paths point at `submission/clawith-vibecosystem-roundtrip-proof.manifest.json` and `submission/roundtrip-proof/`, not raw `artifacts/...` dirs.
- [ ] Any placeholder `FILL_*` tokens have been removed from final user-facing artifacts.

## 4. Submission packet completeness

- [ ] `submission/judge-demo-script.md` is the canonical live walkthrough.
- [ ] `submission/judge-qa-note.md` is the canonical short-answer support note.
- [ ] `submission/pr-or-submission-summary.md` is the canonical written summary.
- [ ] `submission/conversation-log.md` is the canonical final conversation log.
- [ ] `submission/evidence-proof-manifest.json` is the canonical final proof inventory.
- [ ] `submission/submission-metadata.json` is the canonical final metadata file.
- [ ] `submission/drafts/` is clearly archived and no longer the canonical packet.
- [ ] The final packet distinguishes **repo-visible proof** from **local-only proof**.

## 5. Human publish gate

- [ ] Submission portal fields are filled with the final repo URL plus the canonical packet paths for `conversation-log`, `submission-metadata`, `evidence-proof-manifest`, and the roundtrip proof manifest.
- [ ] Required team self-custody / admin-publish steps are complete.
- [ ] If no wallet-approved Base receipt exists on this branch, the final wording still says **staged / not minted**.

## 6. Hygiene

- [ ] JSON packet files validate.
- [ ] Markdown packet files are readable and placeholder-free where required.
- [ ] `git diff --check` is clean.
- [ ] The dirty root checkout was never edited by this lane.
- [ ] Final branch is pushed and the exact commit SHA is recorded.

## Go / no-go rule

- **GO** only if every required box above is true.
- **NO-GO** if any proof claim depends on oral explanation, unpublished local state, still-unfilled placeholders, or unfinished human/admin publish prerequisites.

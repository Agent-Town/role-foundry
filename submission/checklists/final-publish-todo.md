# Final publish TODO

Status: packet-ready_pending_human_publish

This submission packet is assembled. What remains is short, concrete, and mostly human-side.

## 1. Freeze and stamp the packet

- [ ] Run the last narrow sanity pass (`git diff --check`, JSON parse, targeted syntax/tests as needed).
- [ ] Record the final review branch + content-freeze commit in the canonical `submission/*.md` and `submission/*.json` packet files.
- [ ] Push the branch and use that exact pushed commit in any reviewer or portal links.

## 2. Fill the submission portal with the canonical packet paths

- [ ] Repo URL: `https://github.com/Agent-Town/role-foundry`
- [ ] conversation log: `submission/conversation-log.md`
- [ ] submission metadata: `submission/submission-metadata.json`
- [ ] evidence / proof manifest: `submission/evidence-proof-manifest.json`
- [ ] roundtrip proof manifest: `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`

## 3. Finish the required human wallet / publish steps

- [ ] Confirm all required team self-custody transfer steps are complete.
- [ ] Confirm the team admin account/session that is allowed to publish is the one being used.
- [ ] Fill any remaining participant / wallet metadata required by the submission portal.

## 4. Keep the final claim boundary honest at send time

- [ ] If this branch still has **no wallet-approved Base receipt**, keep every ERC/Base phrase as **staged / not minted**.
- [ ] Do not upgrade the roundtrip proof into native Clawith parity, sealed eval, or tamper-proof certification.
- [ ] Do not claim partner-track completion from this branch.

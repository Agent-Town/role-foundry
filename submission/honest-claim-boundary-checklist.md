# Honest claim-boundary checklist

Use this before publishing or summarizing the submission branch.
If any checked item is false, soften the claim.

## Allowed to claim now

- [ ] Role Foundry has a judge-facing static demo with apprentice framing, score deltas, proof-bundle surfaces, and a vision/system overview page.
- [ ] The repo shows a public-curriculum vs teacher-only holdout separation contract.
- [ ] The repo includes a teacher-driven source intake + curriculum-promotion workflow.
- [ ] The repo includes public-regression alpha-loop / receipt / evidence-index plumbing.
- [ ] The repo includes a local private-holdout scaffold where fresh hidden holdouts stay outside tracked and student-visible artifacts.
- [ ] Each reviewed generation can be narrated through repo-visible receipts, evaluation context, score deltas, and a promotion/public-issuance decision.
- [ ] The repo includes one honest external adapter-first Clawith -> OpenClaw gateway -> Claude/vibecosystem -> Clawith roundtrip, indexed by `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`.
- [ ] The repo stages ERC-8004 registrations targeting Base (Sepolia for review, mainnet for submission) and wires the canonical agent0-sdk Python mint path in-repo (`runner_bridge/product_integrations.py` + `runner_bridge/erc8004_agent0.py`).
- [ ] The path makes staged-vs-live explicit: registration drafts and completion templates are generated locally; no onchain mint has been claimed or faked.
- [ ] Promoted/public generations can be discussed as the intended portable-identity layer.

## Do not claim now

- [ ] Native Clawith parity beyond the single external gateway + Claude/vibecosystem executor lane.
- [ ] Native Clawith model-pool parity or native bring-up completion.
- [ ] Live Base minting on Sepolia or mainnet.
- [ ] Partner-track completion.
- [ ] Sealed-eval claims.
- [ ] Sealed certification.
- [ ] Tamper-proof or independently sealed holdout evaluation.
- [ ] Product-core partner integrations as completed shipping scope for this pass.
- [ ] MetaMask Delegation Toolkit is integrated or active.

## Remaining pending active lanes

- [ ] `role-foundry-clawith-native-agent-bringup` must land native model-pool smoke evidence before any native-parity claim is made.
- [ ] If citing the roundtrip proof, keep the citation scoped to the external gateway + Claude/vibecosystem executor lane and the tracked proof manifest.
- [ ] ERC-8004 Base minting still requires: configured `BASE_SEPOLIA_RPC_URL` + `BASE_SEPOLIA_REGISTRY` (or mainnet equivalents), `agent0-sdk` in the Python environment, a signer private key, a public token URI hosting the draft JSON, `ROLE_FOUNDRY_ERC8004_ENABLE_LIVE_MINT=1`, and a human promotion/public-issuance decision.
- [ ] The submission packet itself does **not** wait on live minting; if no onchain receipt exists, keep every ERC/Base statement at staged / not minted.

## Coherence notes

- [ ] Keep the current honest scope note: the shipped public curriculum remains frontend/product-heavy.
- [ ] If public-family IDs still use `frontend-apprentice`, explain that they refer to the currently shipped public slice naming, not broader completed role coverage.
- [ ] Do not rewrite one external-gateway roundtrip into a general "Clawith works natively end to end" statement.
- [ ] Do not rewrite staged ERC-8004 issuance into a live Base mint claim.
- [ ] Do not convert local referenced receipt directories into "public proof artifacts" unless they are intentionally published.

# Honest claim-boundary checklist

Use this before publishing or summarizing the submission branch.
If any checked item is false, soften the claim.

## Allowed to claim now

- [ ] Role Foundry has a judge-facing static demo with apprentice framing, score deltas, proof-bundle surfaces, and a vision/system overview page.
- [ ] The repo shows a public-curriculum vs teacher-only holdout separation contract.
- [ ] The repo includes a teacher-driven source intake + curriculum-promotion workflow.
- [ ] The repo includes a local private-holdout scaffold where fresh hidden holdouts stay outside tracked and student-visible artifacts.
- [ ] The repo includes public-regression alpha-loop / receipt / evidence-index plumbing.
- [ ] The repo includes one honest external adapter-first Clawith -> OpenClaw gateway -> Claude/vibecosystem -> Clawith roundtrip, indexed by `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`.

## Do not claim now

- [ ] Native Clawith parity beyond the single external gateway + Claude/vibecosystem executor lane.
- [ ] Native Clawith model-pool parity or native bring-up completion.
- [ ] Sealed-eval claims.
- [ ] Sealed certification.
- [ ] Tamper-proof or independently sealed holdout evaluation.
- [ ] Product-core partner integrations as completed shipping scope for this pass.

## Remaining pending active lanes

- [ ] `role-foundry-clawith-native-agent-bringup` must land native model-pool smoke evidence before any native-parity claim is made.
- [ ] If citing the roundtrip proof, keep the citation scoped to the external gateway + Claude/vibecosystem executor lane and the tracked proof manifest.

## Coherence notes

- [ ] Keep the current honest scope note: the shipped public curriculum remains frontend/product-heavy.
- [ ] If public-family IDs still use `frontend-apprentice`, explain that they refer to the currently shipped public slice naming, not broader completed role coverage.
- [ ] Do not rewrite one external-gateway roundtrip into a general “Clawith works natively end to end” statement.
- [ ] Do not convert local referenced receipt directories into “public proof artifacts” unless they are intentionally published.

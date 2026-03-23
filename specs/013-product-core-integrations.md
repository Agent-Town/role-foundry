# Spec 013 — Product-core integrations (receipts, guardrails, ERC-8004, delegation)

## Status
Proposed + partially implemented on this lane.

## Why this slice exists
Role Foundry’s first real product-shaped demo is no longer “generic agent infra.”
It is a teacher/eval/product loop for a software-engineering apprentice improving Role Foundry itself.

So the integrations need to do real product work:
- make runs more auditable
- keep the hidden-eval contract honest
- give the apprentice a plausible portable identity path
- define how future wallet permissions stay constrained

No hackathon sticker collection. No fake partner parity. No fake onchain writes.

## Exact scope
This spec adds one narrow **product integration bundle** on top of the existing run artifacts.
For each run, Role Foundry should be able to emit:

1. **Verifiable receipts / scorecards**
   - Hash the existing public run artifacts and teacher scorecard.
   - Persist an integration bundle that points at the canonical receipt files.
   - Keep verification local/content-based; do not claim signatures or onchain anchoring unless those truly exist.

2. **Locus guardrails**
   - Implement a local, product-owned guardrail contract named as the Locus lane.
   - Evaluate at least these checks:
     - sealed holdout text does not leak into public artifacts
     - receipt bundle is present
     - scorecard claim is anchored to a content hash
     - ERC-8004 stays in draft state until a confirmed tx exists
     - MetaMask delegation stays non-active until a permission receipt exists
   - This is a local enforcement/readiness layer, not a fake hosted Locus integration.

3. **ERC-8004 agent identity**
   - Recommend **agent0-sdk / agent0-ts** as the implementation path if no incompatibility is found.
   - Keep the product contract Role Foundry-owned.
   - Emit a local ERC-8004 registration draft JSON and completion template.
   - Do not claim minting until a human-approved wallet flow confirms and a completion receipt exists.

4. **MetaMask Delegation**
   - Emit a constrained delegation intent contract tied to the run.
   - Scope it to future identity-completion work only.
   - Do not claim any live delegation or smart-account execution unless an activation receipt exists.

## Explicit non-scope / out of scope
- No fake Locus SaaS / hosted policy engine claim
- No fake ERC-8004 mint or registration tx
- No fake Base/Mainnet write
- No fake MetaMask delegation activation
- No broad wallet UX redesign
- No broad `runner_bridge` refactor
- No claim of native upstream Clawith parity
- No fake sealed-eval / partner-grade certification claim

## Product contract
For any run that goes through `runner_bridge.cli`, the lane should write:

```text
runtime/runs/<run_id>/integrations/
  trust-bundle.json
  summary.md
  erc8004-registration-draft.json
  erc8004-completion-template.json
  metamask-delegation-intent.json
```

And it should surface a compact summary in:
- `artifact-bundle.json` → `integration_bundle`
- `result.json` → `integrations`

## Status vocabulary
Use these exact readiness states:
- `demo_usable`
- `draft_ready`
- `contract_ready`
- `registered`
- `active`
- `blocked`

Interpretation:
- **demo_usable**: can be honestly shown in the demo now
- **draft_ready**: product contract + artifact exists, but live write/manual action still required
- **contract_ready**: permission/policy shape is defined and testable, but not live
- **registered**: confirmed onchain identity receipt exists
- **active**: confirmed delegation activation receipt exists
- **blocked**: a must-have integrity condition failed

## Recommended implementation order
1. **Verifiable receipts / scorecards**
   - already closest to the existing repo spine
   - unlocks judge trust immediately
2. **Locus guardrails**
   - prevents the next two integrations from turning into bullshit
3. **ERC-8004 agent identity via agent0-sdk**
   - draft first, mint later
4. **MetaMask Delegation**
   - only after identity completion scope is clearly bounded

## Exact acceptance criteria

### A. Verifiable receipts / scorecards
Must pass when:
- `trust-bundle.json` exists
- receipt hashes exist for `request.json`, `artifact-bundle.json`, `result.json`, `receipts/manifest.json`, `receipts/evidence-index.json`, `receipts/summary.md` when present
- teacher scorecard hash exists when a scorecard exists
- status is `demo_usable` when all required receipt/scorecard checks pass

Must fail / degrade honestly when:
- scorecard missing → not `demo_usable` for the scorecard portion
- receipt manifest missing → cannot claim verifiable receipt bundle

### B. Locus guardrails
Must pass when:
- sealed teacher-only text from `request.private.json` does not appear in any public artifact scanned by the guardrail
- receipt bundle completeness check passes
- scorecard hash exists
- ERC-8004 is still `draft_ready` unless completion receipt exists
- MetaMask delegation is still `contract_ready` unless activation receipt exists

Must block when:
- sealed prompt text leaks into a public artifact

### C. ERC-8004 agent identity
Must pass when:
- `erc8004-registration-draft.json` exists
- `erc8004-completion-template.json` exists
- integration bundle explicitly says `recommended_path: agent0-sdk`
- wiring plan names:
  - wallet discovery via `discoverEip6963Providers`
  - wallet connect via `connectEip1193`
  - mint path via `createAgent(...)` + `registerHTTP(tokenUri)`
- status is `draft_ready`
- `registrations` is empty in the draft until completion is confirmed

Must remain blocked from stronger claims when:
- no confirmed tx hash / registry / agent id exists

### D. MetaMask Delegation
Must pass when:
- `metamask-delegation-intent.json` exists
- intent is scoped to one approved identity-completion action for the matching run
- blocked actions include arbitrary contract calls and arbitrary token transfer
- status is `contract_ready`

Must remain blocked from stronger claims when:
- no activation receipt exists

## Allowed vs blocked demo claims

### Allowed now if the implementation passes
- “Role Foundry emits hashed local receipts and a teacher scorecard judges can inspect.”
- “Role Foundry runs a local Locus-style guardrail contract for redaction, receipt completeness, and staged external claims.”
- “Role Foundry can draft an ERC-8004 registration and wire minting through a thin internal agent0-sdk adapter.”
- “Role Foundry defines a constrained MetaMask delegation intent for future identity completion, but it is not active yet.”

### Blocked unless stronger evidence exists
- “This run minted an ERC-8004 identity onchain.”
- “MetaMask delegation is active or exercised on this run.”
- “Locus hosted enforcement is wired in this repo.”
- “Role Foundry writes scorecards or proofs onchain.”
- “This proves sealed certification / partner-grade evaluation.”

## Exact agent0-sdk wiring recommendation
**Recommended path: yes — agent0-sdk is the default ERC-8004 path for Role Foundry.**

Use the existing local precedent already in the workspace:
- `agent0lab/agent0-ts/README.md`
- `Portal/public/erc8004-phase3.md`
- `Portal-docs/scripts/build_agent0_sdk_bundle.mjs`
- `Portal-docs/e2e/05_erc8004_mint.spec.js`

Role Foundry should own a thin internal adapter with this boundary:

1. Build a Role Foundry registration draft JSON first.
2. Load a pinned/vendored browser bundle for `agent0-sdk`.
3. Discover wallets with `discoverEip6963Providers`.
4. Connect a human-approved EIP-1193 provider with `connectEip1193`.
5. Construct `new SDK({ chainId, rpcUrl, walletProvider })`.
6. Map the Role Foundry run + receipts into `createAgent(name, description, image)`.
7. Mint with `agent.registerHTTP(tokenUri)`.
8. Only after confirmation, write the completion receipt with chain id, registry, agent id, tx hash, minted_at, minted_by.

Why this is the right default:
- it reuses existing Agent Town precedent instead of inventing a new ERC-8004 path
- it keeps wallet authority with the human
- it fits Role Foundry’s honest local-first stance
- it lets the product contract exist now, before live chain setup is available

## Measurable completion metrics
The bundle must record:
- `integration_count`
- `demo_usable_now`
- `contract_only_now`
- `blocked_now`
- `status_by_integration`

Success target for this lane:
- receipts / scorecards: `demo_usable`
- Locus guardrails: `demo_usable`
- ERC-8004: `draft_ready`
- MetaMask Delegation: `contract_ready`

That means the honest target state is:
- `demo_usable_now = 2`
- `contract_only_now = 2`
- `blocked_now = 0`

## Agentic-AI-developer-ready tests
Add tests that assert:
1. the spec exists and names exact allowed vs blocked claims
2. a teacher-eval run emits all integration files
3. the integration bundle marks `agent0-sdk` as the ERC-8004 path
4. the ERC-8004 draft has empty `registrations[]`
5. the MetaMask delegation intent is constrained and non-active
6. sealed prompt text leakage causes the Locus guardrail to fail/block
7. the UI/demo surface can render the four integration statuses without claiming live wallet/onchain success

## Demo surface requirements
The run detail page should expose a compact “Trust Integrations” section that shows:
- status for each of the four integrations
- the `agent0-sdk` ERC-8004 recommendation
- allowed vs blocked demo claims

This should be a narrow read-model surface, not a new wallet flow.

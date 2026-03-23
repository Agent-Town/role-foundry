# Role Foundry

## The framework

Role Foundry is a **framework for training AI apprentices under honest, holdout-aware evaluation**. The core unit is a **generation**: each evaluated generation leaves an inspectable provenance chain — receipt bundle, evaluation context, score deltas, and a promotion decision. Promoted public generations can then be staged for **ERC-8004** issuance on **Base** through a thin Role Foundry-owned Python mint path.

The framework handles the training loop. The role defines what the apprentice learns.

## The current concrete example

The current alpha demo ships one concrete role: a **Software Engineer apprentice** that implements Role Foundry product slices under public-regression and local private-holdout review. Robin + Neo are the teachers. The apprentice builds the system it is being trained by.

**Honest scope note:** The currently shipped curriculum slices are frontend/product-heavy because that is what the alpha app exposes. The “Software Engineer” framing reflects the intended breadth — code review, regression prevention, documentation honesty — not a claim that all those curriculum families are shipped today.

**Name:** Software Engineer Apprentice
**Job:** Ship coherent, judge-facing Role Foundry product slices
**Teachers:** Robin + Neo
**Constraints:** standalone repo, demo mode first, no auth, no Privy, no fake live integrations

## What judges see in this demo

`docker compose up` serves a static demo with pre-baked data that shows:

1. **Vision/system overview** — explains the general framework vs the current concrete role
2. **Apprentice definition** — the Software Engineer apprentice is learning to build Role Foundry itself
3. **Public curriculum** — visible training slices like rewriting the apprentice story, clarifying curriculum vs holdouts, exposing score deltas, and adding proof bundles
4. **Holdout integrity story** — judge-visible holdout categories in the demo plus a local-only scaffold for fresh teacher-only rewrites outside the public repo
5. **Two judged runs** — Run 2 clearly improves over Run 1
6. **Teacher scorecard** — per-scenario teacher notes plus aggregate score across public curriculum and holdout-facing review
7. **Failure → curriculum loop** — failed holdout themes become the next public teaching themes without exposing hidden prompt text
8. **Iteration history** — score deltas over time stay visible in both the UI and stored run data
9. **Proof bundle** — receipt summary, changed files, policy snapshot, and transcript excerpt
10. **Portable identity path** — promoted public generations can be drafted for ERC-8004 issuance on Base without faking a wallet transaction

This is the point of Role Foundry: make capability visible with honest evaluation instead of vibes.

## How the loop works

1. **Teachers define a role** — what good work looks like for this apprentice
2. **Role Foundry publishes public curriculum** — scenarios the apprentice can practice on
3. **Role Foundry keeps fresh hidden holdouts teacher-only** — the public repo carries the contract/template/tests for that lane, not the private prompts themselves
4. **The apprentice ships a generation** — copy, UI, scorecard, or artifact surface
5. **Teacher judges the generation** — receipts, scorecard context, and aggregate score become part of the generation record
6. **Later generations record deltas** — the next run makes the better/equal/worse movement explicit
7. **Humans decide what gets promoted** — public curriculum themes and readiness evidence can move forward without leaking hidden prompt text
8. **Promoted public generations can be staged for ERC-8004 issuance** — Base is the current portable-identity target

## Curriculum extension

Teachers can extend the holdout lane with manually curated episodes from external sources like SWE-bench, Playwright docs, or code-review guides. These stay **teacher-only** and never enter the public repo or student-visible curriculum. See `docs/swe-bench-holdout-extension.md` for the process and constraints.

SWE-bench usage is intentionally **small and teacher-only**: at most 5-10 manually rewritten episodes per extension round, stored in the existing gitignored private holdout path. This is not bulk integration or public curriculum.

## Demo mode vs live mode

| | Demo mode | Live mode |
|---|---|---|
| **What runs** | Static UI with pre-baked apprentice data | Configured read-only browser shell + optional Clawith / runner-bridge receipts |
| **Requirements** | Docker (web container + local services) | `liveDataUrl` export for the browser shell; add Clawith image + model credentials for actual runs |
| **Good for** | Judges, walkthroughs, design review | Inspecting exported run state honestly, then actual training / evaluation once the backend is wired |
| **Current status** | Shipping now | Browser shell now consumes configured exports; native live storage/browser fan-out is still pending |

## Local quickstart

```bash
cp .env.example .env
docker compose up
open http://localhost:8080
```

This starts the static web demo plus Postgres and Redis.

To exercise the **browser live shell** against the committed alpha-loop sample:

```text
http://localhost:8080/?mode=live&liveDataUrl=live-read-model.alpha-loop.sample.json
```

That sample is a **consumer-side envelope derived from the repo's real public alpha-loop receipt**. The browser now renders the exported `comparison.verdict`, `deciding_axis`, `baseline_total_score`, `candidate_total_score`, `total_score_delta`, and `category_deltas` directly instead of inventing new score semantics.

To start the optional backend-side **live mode** (requires an external Clawith image):

```bash
docker compose --profile live up
```

See `docs/clawith-integration.md` for prerequisites and the full integration guide.
For the narrow real external-executor proof lane, see `docs/clawith-vibecosystem-real-path.md` and `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`.

## First live run

The first honest runner-bridge slice is now in the repo. It is intentionally small:
- `python3 -m runner_bridge.cli` drives one run lifecycle
- `LocalReplayRunner` is the zero-secret backend that writes a transcript and artifact bundle
- optional `teacher_evaluation` input produces a teacher scorecard, public curriculum themes, and iteration history deltas
- the bridge stores a redacted `request.json` plus a raw `request.private.json` so sealed holdout prompts stay out of student-facing artifacts
- the bridge also emits a receipt provenance pack (`receipts/manifest.json`, baseline/candidate/evaluation exports, `receipts/evidence-index.json`, `receipts/audit-bundle.json`, and `receipts/summary.md`) so judges can trace a run back to its source artifacts without changing the scoring semantics; the audit bundle carries machine-readable artifact coverage, required-artifact validation, redaction checks, and honest section availability for local/sample paths
- if you pass `--clawith-url`, the bridge patches run state into a Clawith-compatible control plane
- if you omit `--clawith-url`, you can still exercise the artifact/transcript contract locally

Examples:

```bash
# Run a task packet by acceptance_test_id (packet-driven path)
python3 -m runner_bridge.cli --packet A001

# Run a task packet with explicit run-id
python3 -m runner_bridge.cli --packet C001 --run-id my-run-001

# Run from a pre-built request JSON
python3 -m runner_bridge.cli \
  --request runner_bridge/examples/first-live-run.json

# With control plane
python3 -m runner_bridge.cli \
  --request runner_bridge/examples/teacher-eval-loop.json \
  --clawith-url http://localhost:3000 \
  --clawith-secret "$CLAWITH_SECRET"
```

The `--packet` path loads a frozen task packet from the public seed registry, validates it against the evaluation contract and role manifest, materializes a `run-object.json` runtime artifact in the run directory, and runs it through the bridge. The `run-object.json` carries the packet id, version, content hash, role id, eval contract ref, mutation budget, paths, checks, and evidence contract. The `result.json` includes a machine-readable `execution_honesty` block that truthfully reports whether the backend actually executed commands.

Artifacts land under `runtime/runs/<run_id>/`.

See `docs/runner-bridge.md` for the control-plane patch contract, teacher scorecard extension, the public benchmark-pack prompt path, comparison receipt flow, and the local/mockable fallback path.

## Autoresearch alpha loop

There is now a first honest **bridge-mediated autoresearch alpha loop**:

```bash
python3 -m runner_bridge.autoresearch_alpha \
  --request runner_bridge/examples/autoresearch-alpha-public-loop.json
```

What it proves today:
- a real **baseline → candidate student → candidate teacher-eval** lifecycle
- a concrete **better/equal/worse** comparison receipt
- artifact coverage across all three stages
- an explicit **integrity gate** that allows public-regression claims while blocking fake sealed-eval claims
- a **repo-task-shaped student prompt pack** with per-scenario metadata (`suggested_files`, `mutation_budget`, `constraints`, `public_checks`) derived from the public benchmark episodes, making the candidate-student stage less canned and more like real software-engineering teaching

That last point matters. The repo-visible teacher-only families are still marked `blocked_pending_rewrite` in the tracked public registry, so the repo cannot pretend those public entries are suddenly sealed. But the local private-holdout lane has now moved beyond “first rewrite pending”: fresh local-only replacement coverage exists for all three previously blocked teacher-only families (`h1` / `h2` / `h3`), and the latest local rerun loaded 6/6 holdouts from the manifest with a `better` comparison verdict. Those claims still stop at local private-holdout alpha execution, and the docs say that plainly instead of faking a stronger certification story.

A second **Frontend/Product Engineer** benchmark pack is now also available:

```bash
python3 -m runner_bridge.autoresearch_alpha \
  --request runner_bridge/examples/fpe-autoresearch-alpha-public-loop.json
```

This pack ships **20 public episodes across 5 families** (one per curriculum phase) derived from Spec 014 acceptance tests. Rubric templates use the frozen FPE evaluation contract. No teacher-only families are blocked.

All 20 episodes are **public-safe and alpha-consumable** — packets, rubrics, and provenance are complete. However, **runtime readiness varies by phase**: Phase 1 contract surface is complete, Phase 3 execution is partial (verifier-gate landed, live execution pending), and Phases 2/4/5 are packet-defined only with runtime not yet live. See `docs/curriculum-operating-split.md` for the honest status-by-area table and per-family `readiness` fields in the family registry for machine-readable detail.

There is also now a separate **local-only private holdout scaffold / execution lane**:
- `benchmarks/private-holdout-pack-template.json` defines the public-safe shape only
- `benchmarks/private-holdout-pack/` is gitignored for real teacher-only material
- `tests/test_private_holdout_separation.py` proves tracked artifacts stay clean
- `runner_bridge.autoresearch_alpha` can now hydrate a **local private-holdout** teacher lane from `private_holdout_manifest` while keeping student-visible artifacts redacted

The tracked repo still ships only the public-safe scaffold. Separately, the gitignored local lane now has fresh replacement coverage for all three previously blocked teacher-only families (`h1` / `h2` / `h3`), and the latest local private-holdout alpha rerun loaded 6/6 holdouts from the manifest.

**Allowed now:** fresh hidden holdouts in a gitignored local manifest, honest local reruns, and receipts that keep teacher-only content out of tracked and student-visible artifacts.

**Still blocked:** sealed-eval claims, sealed certification, tamper-proof evaluation, and any claim that a third party independently sealed the holdouts.

The local-only shape is:

```bash
python3 -m runner_bridge.autoresearch_alpha \
  --request benchmarks/private-holdout-pack/local-private-holdout-alpha-loop.request.json
```

That request file stays local-only, points `private_holdout_manifest` at the gitignored manifest, and references holdout episodes by id so the bridge can hydrate teacher-only prompts into `request.private.json` only.

## ERC-8004 / Base / agent0-sdk Python mint path

The repo now ships a narrow **Python-native** path that turns the generation-provenance chain into a portable identity handoff on **Base** through the `agent0-sdk` / `agent0-py` flow:

- `runner_bridge/product_integrations.py` — after each evaluated generation, writes a local ERC-8004 registration draft, completion template, and a canonical Python mint contract tied back to the existing receipt/scorecard artifacts. No onchain writes.
- `runner_bridge/erc8004_agent0.py` — explicit live-mint helper: `SDK(chainId, rpcUrl, signer, registryOverrides?)` → `createAgent(...)` → `setMetadata(...)` → `register(tokenUri)` → `wait_confirmed()`.

**Target chains:** Base Sepolia (chain id 84532, review/demo default) and Base Mainnet (chain id 8453, explicit submission target). Both are env-driven via `BASE_SEPOLIA_RPC_URL` / `BASE_MAINNET_RPC_URL`. Registry overrides remain optional via `BASE_SEPOLIA_REGISTRY` / `BASE_MAINNET_REGISTRY` if the SDK defaults ever need to be overridden.

**What is real now:** registration drafts, completion templates, the Python mint helper module, wired-vs-pending diagnostics, and a reviewer-visible story that promoted/public generations are the ones eligible for public issuance.

**What is pending:** `agent0-sdk` availability in the Python environment, a configured Base RPC URL, a hosted public token URI for the draft JSON, an explicit promoted/public decision, and a real confirmed mint. Live mint stays off by default behind `ROLE_FOUNDRY_ERC8004_ENABLE_LIVE_MINT=1`. No minting has been claimed or faked.

`app/agent0_base_adapter.mjs` remains in-repo as a historical browser-side experiment, but it is no longer the canonical repo path.

See `docs/erc8004-base-agent0-adapter.md` for usage and `specs/013-erc8004-base-agent0-adapter.md` for the full spec.

## What is still stubbed

This repo is intentionally honest about what is not wired yet:
- the browser **live shell is read-only** — it consumes configured exports / receipts, but it does not chase native run storage or claim upstream Clawith parity
- only one **local/mockable runner path** is implemented today (`LocalReplayRunner`); teacher scorecards and iteration history are real contracts, but Claude/Codex-backed adapters still need wiring
- the committed alpha-loop browser fixture is a **sample/read-model export derived from a real public alpha receipt**, not proof that native live storage/browser fan-out already exists on this branch
- no auth, no Privy, no fake consumer OAuth path
- no live artifact viewer backed by run storage fan-out

Live mode can now seed the repo's Clawith-compatible seam, drive bridge-mediated runs, and the browser shell can consume configured read-model / alpha-loop exports. That is still deliberately narrow. It does not claim stock upstream Clawith natively accepts Role Foundry seed writes. Demo mode remains first-class and judge-friendly on its own.

## Where Clawith fits

[Clawith](https://github.com/openclaw/clawith) is the live control plane. It is profile-gated in `docker-compose.yml` and can be started with `--profile live`. In the full system it owns:
- agent registry
- run registry
- scenario and holdout storage
- evaluation store and scorecards
- approvals, scheduling, and audit trails

For the hackathon MVP, Clawith integration is wired at the Docker layer and the browser now has a narrow read-only shell for configured exports. It still does not claim native upstream parity or full live artifact browsing. See `docs/runner-bridge.md` for the bridge pattern and `docs/clawith-integration.md` for live-mode setup.

## Execution backends

| Runner | Role | Why |
|---|---|---|
| Claude + vibecosystem | Student / builder | Strong for implementation-heavy slices |
| Codex | Teacher / critic / evaluator | Independent model family for judging |
| Deterministic scripts | Verifier | Cheap pass/fail checks |

Using different model families for building and judging reduces correlated self-grading.

## Docs

- `docs/milestones.md` — spec-first milestone rail and current delivery status
- `docs/v1-mvp-plan.md` — build slices
- `docs/clawith-integration.md` — live-mode setup, prerequisites, image contract, and read-only probe lane
- `docs/clawith-adapter-bringup.md` — seam-to-upstream mapping matrix and adapter-first bring-up prereqs
- `docs/clawith-vibecosystem-real-path.md` — smallest real external gateway + Claude/vibecosystem roundtrip lane
- `docs/runner-bridge.md` — bridge path, teacher evaluation contract, comparison receipts, and explicit auth deferral
- `docs/public-benchmark-pack-v1.md` — public-safe benchmark pack scope, blocked families, and local private-holdout path
- `docs/software-engineer-curriculum-sources.md` — narrow public source inventory for the software-engineering apprentice
- `docs/teacher-source-curriculum-workflow.md` — discover → curate → promote workflow for teacher-driven curriculum extension
- `docs/frontend-product-engineer-seed-curriculum.md` — public seed-task registry, packet schema, and audit commands for the frozen Frontend/Product Engineer role
- `docs/curriculum-operating-split.md` — teacher vs student responsibilities, canonical contract surface, and honest implemented-vs-future status
- `docs/phase5-lineage-cycle-ops.md` — Phase 5 generation lineage, weekly training cycles, and cross-artifact linkage (contract/fixture level, not live automation)
- `docs/teacher-review-console.md` — D001 fixture-backed teacher review shell/read-model over stored exports only
- `docs/private-holdout-authoring.md` — local-only teacher workflow for authoring and auditing fresh holdouts
- `docs/swe-bench-holdout-extension.md` — teacher-only process for small manually curated SWE-bench-derived holdout episodes
- `docs/conversation-log.md` — curated build log for the submission
- `submission/` — final submission packaging templates and review checklists
- `docs/erc8004-base-agent0-adapter.md` — ERC-8004 Base / agent0-sdk adapter usage and claim boundary
- `docs/agent-town-connection.md` — Agent Town relationship
- `docs/synthesis-hackathon-ideation.md` — ideation and ranking
- `docs/synthesis-hackathon-stack-architecture.md` — architecture notes

## Supporting specs

- `specs/008-public-benchmark-pack-v1.md` — public benchmark pack contract for the current alpha spine
- `specs/009-clawith-readiness-probe.md` — adapter-first upstream readiness probe
- `specs/010-autoresearch-alpha-public-loop.md` — the first executable public alpha loop with integrity gate
- `specs/011-live-ui-read-model.md` — read-only browser adapter for configured live/read-model exports
- `specs/012-private-holdout-pack.md` — local-only private holdout contract without shipping teacher material
- `specs/013-erc8004-base-agent0-adapter.md` — ERC-8004 Base / agent0-sdk adapter spec
- `specs/014-frontend-product-engineer-20-task-curriculum.md` — TDD-first 20-task curriculum contract for the first Frontend/Product Engineer apprentice

## License

GPL-3.0

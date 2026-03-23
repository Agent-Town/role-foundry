# conversationLog — packaging template

Status: draft scaffold

Use this to assemble the final submission `conversationLog` from repo-visible evidence.
Do **not** fabricate transcripts, approvals, or run results that do not exist.

## Source inputs

- `docs/conversation-log.md`
- `git log --oneline origin/submission/active-base-20260323-0711..HEAD`
- `docs/teacher-source-curriculum-workflow.md`
- `docs/private-holdout-authoring.md`
- `docs/runner-bridge.md`
- `docs/clawith-vibecosystem-real-path.md`
- `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`
- exact test/check outputs from the packaging review branch

## Packaging rules

- Keep dates / commits literal.
- Summarize work; do not invent chat text.
- Distinguish **repo-visible proof** from **local-only / teacher-only proof**.
- If the proof is indexed by a tracked manifest but the raw receipt dirs stay local, say that plainly.
- If an artifact is only a scaffold/template, say so plainly.

## Template

### 1. Submission framing
- Project: Role Foundry
- Submission base: `origin/submission/active-base-20260323-0711`
- Packaging branch: `review/submission-readiness-roundtrip-proof-20260323-1005`
- One-sentence claim:
  - TODO

### 2. Repo-visible work shipped on this packaging pass
- [ ] Vision/system overview UI promoted
- [ ] Teacher-source curriculum flow promoted
- [ ] Hidden private-holdout claim-boundary clarification promoted
- [ ] Submission packaging scaffolds added
- [ ] External gateway roundtrip proof docs/scripts/receipt manifest folded in

### 3. Evidence referenced
- [ ] `app/vision.html`
- [ ] `data/source-research/software-engineer-source-intake.v1.json`
- [ ] `docs/teacher-source-curriculum-workflow.md`
- [ ] `docs/private-holdout-authoring.md`
- [ ] `docs/runner-bridge.md`
- [ ] `docs/clawith-vibecosystem-real-path.md`
- [ ] `benchmarks/public-pack-v1/benchmark-pack.json`
- [ ] `submission/evidence-proof-manifest.template.json`
- [ ] `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`

### 4. Checks run
- [ ] `python3 -m pytest -q tests/test_vision_and_swe_bench_separation.py tests/test_teacher_source_curriculum.py tests/test_public_benchmark_pack_v1.py tests/test_autoresearch_alpha_loop.py tests/test_private_holdout_separation.py tests/test_demo_contract.py tests/test_milestone3_contract.py`
- [ ] `python3 -m py_compile scripts/clawith_link_openclaw.py scripts/clawith_vibe_once.py`
- [ ] `node --check scripts/clawith_ws_roundtrip.js`
- [ ] `git diff --check`

### 5. Explicitly skipped on this pass
- [ ] `role-foundry-clawith-native-agent-bringup` — active lane
- [ ] `origin/lane/product-core-four-integrations` — broad partner-integration / runner-bridge scope, intentionally excluded from this narrow pass

### 6. Pending / blocked
- [ ] Native Clawith model-pool smoke evidence — `pending_active_lane`
- [ ] Sealed-eval / sealed-certification claims — blocked
- [ ] Any claim beyond the single external gateway + Claude/vibecosystem executor proof — blocked

### 7. Claim-boundary note for the final log
> This packaging pass improves submission legibility, keeps the existing public/teacher-only boundaries honest, and folds in one real external gateway roundtrip proof. It does not claim native Clawith parity, model-pool completion, sealed certification, or tamper-proof evaluation.

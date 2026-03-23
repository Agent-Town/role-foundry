# Submission candidate merge/review checklist

Repo submission base:
- branch: `origin/submission/active-base-20260323-0711`
- commit: `0dcdc40`

Candidate merge base:
- branch: `origin/review/submission-readiness-pass-20260323-0910`
- commit: `d2a6539`

Candidate review branch:
- branch: `review/submission-candidate-finished-lanes-20260323-1129`

Merged in this candidate pass:
- [ ] `origin/review/submission-claim-scrub-20260323-1022` @ `03af989`
- [ ] `origin/review/submission-readiness-roundtrip-proof-20260323-1005` @ `c353d88`
- [ ] `origin/lane/demo-packet-prep-20260323-1022` @ `9f074ba`

Inherited from the merge base:
- [ ] vision/system overview UI promotion
- [ ] teacher-source curriculum flow promotion
- [ ] hidden private-holdout claim-boundary clarification

Explicitly skipped in this candidate pass:
- [ ] `role-foundry-holdout-story-alignment` — reserved for the later top-off merge
- [ ] `role-foundry-clawith-native-agent-bringup` — still separate from this narrow submission candidate
- [ ] `origin/lane/product-core-four-integrations` — broad partner-integration / runner-bridge scope; intentionally excluded

Review checklist

- [ ] Confirm merged demo/docs surfaces keep roundtrip claims scoped to the external gateway + Claude/vibecosystem executor lane.
- [ ] Confirm no submission artifact rewrites the proof as native model-pool parity, general upstream Clawith parity, sealed certification, or tamper-proof evaluation.
- [ ] Confirm tracked proof references point at `submission/clawith-vibecosystem-roundtrip-proof.manifest.json` and keep raw receipt dirs local-only.
- [ ] Confirm demo-packet drafts were updated to cite the already-landed roundtrip proof rather than a future placeholder lane.
- [ ] Run JSON sanity for touched submission files.
- [ ] Run `/opt/homebrew/bin/pytest -q tests/test_vision_and_swe_bench_separation.py tests/test_teacher_source_curriculum.py tests/test_public_benchmark_pack_v1.py tests/test_autoresearch_alpha_loop.py tests/test_private_holdout_separation.py tests/test_demo_contract.py tests/test_milestone3_contract.py`
- [ ] Run `python3 -m py_compile scripts/clawith_link_openclaw.py scripts/clawith_vibe_once.py`
- [ ] Run `/Users/robin/.nvm/versions/node/v24.14.0/bin/node --check scripts/clawith_ws_roundtrip.js`
- [ ] Run `git diff --check`.
- [ ] Verify the dirty root checkout was not used or modified.
- [ ] Push the review branch and record the exact commit.

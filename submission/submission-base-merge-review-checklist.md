# Submission base merge/review checklist

Submission base for this pass:
- branch: `origin/submission/active-base-20260323-0711`
- commit: `0dcdc40`

Packaging review branch:
- branch: `review/submission-readiness-roundtrip-proof-20260323-1005`

Promoted in this pass:
- [ ] `origin/lane/vision-system-overview-ui` @ `0a0aea0`
- [ ] `origin/lane/teacher-source-curriculum-flow` @ `d46929e`
- [ ] `origin/subagent/hidden-private-holdout` @ `e3287b4`
- [ ] submission packaging scaffolds under `submission/`
- [ ] `origin/review/clawith-vibe-roundtrip-demo-20260323-1000` @ `7f88b51` + `4dab2a9` (docs/scripts only) folded into packaging with a tracked receipt manifest

Explicitly skipped in this pass:
- [ ] `role-foundry-clawith-native-agent-bringup` — active lane; do not overlap
- [ ] `origin/lane/product-core-four-integrations` — broad partner-integration / runner-bridge scope; intentionally excluded from this narrow readiness pass

Review checklist

- [ ] Confirm promoted files do not widen the roundtrip proof beyond the external gateway + Claude/vibecosystem executor lane.
- [ ] Confirm no submission artifact rewrites the proof as native model-pool parity or general upstream Clawith parity.
- [ ] Confirm raw receipt directories are referenced via tracked metadata only and were not committed in this pass.
- [ ] Confirm teacher-only / local-only proof remains clearly separated from public proof.
- [ ] Run targeted tests/checks for promoted areas.
- [ ] Run `git diff --check`.
- [ ] Verify the dirty root checkout was not used or modified.
- [ ] Push the review branch and record the exact commit.

# Submission base merge/review checklist

Submission base for this pass:
- branch: `origin/submission/active-base-20260323-0711`
- commit: `0dcdc40`

Packaging review branch:
- branch: `review/submission-readiness-pass-20260323-0910`

Promoted in this pass:
- [ ] `origin/lane/vision-system-overview-ui` @ `0a0aea0`
- [ ] `origin/lane/teacher-source-curriculum-flow` @ `d46929e`
- [ ] `origin/subagent/hidden-private-holdout` @ `e3287b4`
- [ ] submission packaging scaffolds under `submission/`

Explicitly skipped in this pass:
- [ ] `role-foundry-clawith-vibe-roundtrip-demo` — active lane; do not overlap
- [ ] `role-foundry-clawith-native-agent-bringup` — active lane; do not overlap
- [ ] `origin/lane/product-core-four-integrations` — broad partner-integration / runner-bridge scope; intentionally excluded from this narrow readiness pass

Review checklist

- [ ] Confirm promoted files do not touch the two active Clawith lane hotspots.
- [ ] Confirm no submission artifact claims live roundtrip proof that does not exist yet.
- [ ] Confirm no submission artifact claims native model-pool proof that does not exist yet.
- [ ] Confirm teacher-only / local-only proof remains clearly separated from public proof.
- [ ] Run targeted tests for promoted areas.
- [ ] Run `git diff --check`.
- [ ] Verify the dirty root checkout was not used or modified.
- [ ] Push the review branch and record the exact commit.

# Review Spine Morning Handoff — 2026-03-23

## Morning headline

The overnight win is **clarity, not more churn**. The current clean review base is `review/dataset-flywheel-g-phase-20260323-0515` at `0dcdc40`, and that is the branch Robin should review and merge from. Do **not** treat the dirty root checkout as merge input.

## Recommended review base

- **Branch:** `review/dataset-flywheel-g-phase-20260323-0515`
- **Tip commit:** `0dcdc40` — `benchmarks: add phase-g dataset-flywheel contract (G001-G004)`
- **Why this is the right spine:** it already linearly contains the clean public-alpha, public-pack, local-private-holdout, adapter-readiness, and dataset-flywheel work without requiring the dirty root checkout.

## Exact linear ancestry in the current top spine

Review in this order if you want the clean story from oldest to newest:

| Order | Branch / tip | Commit | What it adds |
|---|---|---:|---|
| 1 | inherited clean base | `201dbc6` | public benchmark pack v1 foundation |
| 2 | inherited clean base | `45aeaff` | receipt provenance exports |
| 3 | inherited clean base | `cd2bbd2` | read-only Clawith readiness probe lane |
| 4 | inherited clean base | `3e0f5a0` | live UI read-model wiring |
| 5 | `lane/autoresearch-alpha-exec` | `da5df55` | executable public alpha loop |
| 6 | `lane/public-alpha-spine` | `ce16262` | public alpha spine cleanup / honesty polish |
| 7 | `lane/public-alpha-holdout-review` | `4353f3f` | local private-holdout authoring path |
| 8 | `lane/sealed-local-alpha-loop` | `1784bdc` | honest local private-holdout alpha path |
| 9 | `lane/clean-spine-promotion-20260323-0417` | `ba6a811` | review-spine freeze / scope discipline |
| 10 | `lane/public-benchmark-pack-v1-freeze-20260323-0431` | `efb578d` | Phase B public-pack contract hardening |
| 11 | `review/clawith-adapter-readiness-f-20260323-0452` | `09169cb` | Phase F adapter-readiness clarity |
| 12 | `review/dataset-flywheel-g-phase-20260323-0515` | `0dcdc40` | Phase G dataset-flywheel contract |

All named branch tips above are ancestors of `0dcdc40`.

## Morning phase shorthand

Not every letter is a formal in-tree phase label today, so treat this as a **review shorthand**, not a claim that every lane was named that way in commit history.

- **Phase A — clean public-alpha spine promotion:** landed
  - anchor commits: `ce16262`, `ba6a811`
  - outcome: the alpha spine was cleaned up, scoped, and frozen into a coherent review story
- **Phase B — public benchmark pack freeze:** landed
  - anchor commit: `efb578d`
  - outcome: B001-B006 are explicit and the public pack is promotion-ready for public regression use only
- **Phase C — executable public alpha loop:** landed
  - anchor commit: `da5df55`
  - outcome: honest baseline → candidate → teacher-eval loop exists for the public path
- **Phase D — local private-holdout authoring contract:** landed
  - anchor commit: `4353f3f`
  - outcome: local-only authoring/audit path exists without shipping teacher content
- **Phase E — honest local private-holdout alpha path:** landed
  - anchor commit: `1784bdc`
  - outcome: local private-holdout execution path exists, still without any sealed-certification claim
- **Phase F — adapter-readiness clarity:** landed
  - anchor commit: `09169cb`
  - outcome: upstream Clawith mismatch is documented honestly and probed read-only
- **Phase G — dataset-flywheel contract:** landed
  - anchor commit: `0dcdc40`
  - outcome: registry completeness, promotion criteria completeness, holdout-promotion safety, and role-pack separation are now explicit contracts

## What remains honestly blocked

These are still real blockers. Morning review should preserve them as blockers, not sand them down.

1. **Fresh sealed teacher families do not exist in-repo.**
   - `h1` / `h2` / `h3` remain `blocked_pending_rewrite`.
   - The repo has a local-only scaffold, not a sealed certification pack.
2. **Native upstream Clawith parity does not exist yet.**
   - RF-specific roles, scenarios, runs, lifecycle patching, and artifact-redaction semantics still need an adapter.
   - Admin/model-pool/auth reality can still block or gate bring-up.
3. **The browser live shell is still read-only.**
   - It consumes configured exports / fixtures.
   - It does not yet prove native live artifact browsing or stock-upstream parity.
4. **Only the local/mockable runner path is implemented today.**
   - `LocalReplayRunner` is real.
   - Claude/Codex-backed execution adapters are still future work.
5. **Milestone 6 is still queued.**
   - Submission proof / partner wiring is not the thing to merge by accident during morning cleanup.

## Next single most important move

**Morning move:** review and merge the clean spine at `review/dataset-flywheel-g-phase-20260323-0515` first, then branch fresh from there for any follow-up work.

The point is simple: lock the honest spine before touching anything else.

## Safe review / merge checklist

1. Start from `review/dataset-flywheel-g-phase-20260323-0515`.
2. Read the honesty docs in this order:
   - `docs/milestones.md`
   - `docs/public-benchmark-pack-v1.md`
   - `docs/private-holdout-authoring.md`
   - `docs/clawith-adapter-bringup.md`
   - `docs/dataset-flywheel.md`
3. Sanity-check the ancestry chain above.
4. Confirm the blocked claims are still blocked:
   - no sealed-certification claim
   - no fake upstream Clawith parity claim
   - no claim that the browser is already a full live artifact UI
5. Merge the clean review spine.
6. Only after that, open a fresh branch for the next real product move.

## What NOT to merge from the dirty root checkout

The root checkout is currently on `wip/public-benchmark-pack-v1-20260323-0046` and has uncommitted local changes.

Treat these files as **out of scope for morning merge** unless they are re-reviewed and re-authored on a fresh clean branch:

- `app/data.js`
- `docs/conversation-log.md`
- `docs/milestones.md`
- `docs/v1-mvp-plan.md`

Why: those edits live only in the dirty working tree right now. They are not part of the clean review spine tip, and casually scooping them into a merge would blur the audit story.

## Recommendation on this handoff branch

This handoff should be treated as a **docs-only companion branch**, not as the substantive overnight spine itself.

- **Substantive branch to merge:** `review/dataset-flywheel-g-phase-20260323-0515`
- **Companion docs branch:** the branch carrying this file

If the morning review likes the handoff, it can be merged after or alongside the substantive spine. It should not replace the spine as the thing being reviewed.

# Spec 008 — Public Benchmark Pack v1

## Intent

Turn the episode-registry / flywheel work into the first **public-safe benchmark pack** that the autoresearch loop can use immediately without pretending the repo already has a clean sealed-eval dataset.

## Requirements

1. The public pack must include **only** student-visible, benchmark-ready episode families.
2. Any family derived from current repo-visible holdout / teacher-only material must be excluded from the public pack and must carry an explicit rewrite-needed readiness state.
   - legacy family `status` may remain `blocked_pending_rewrite` for compatibility
   - promotion-planning `readiness_state` must be `rewrite_before_holdout_promotion`
3. The student-visible vs teacher-only separation must be explicit in machine-readable data.
4. The public pack must be honest about its scope:
   - usable now for public training / regression loops
   - not a sealed certification exam
5. The pack must be concrete enough for use now:
   - family registry
   - benchmark pack manifest
   - companion episode registry with public rubrics + provenance
   - concrete episodes/prompts
   - verifier guidance
   - explicit leak-audit and readiness-state evidence

## Phase B acceptance checkpoints

- **B001 — Public episode count**
  - The pack ships at least 10 concrete public episodes.
  - Current clean-spine promotion state is 12 episodes across 6 families.
- **B002 — Rubric completeness**
  - Every public episode maps to a complete **public rubric template** with explicit dimensions, weights, and pass/fail guidance.
- **B003 — Weight normalization**
  - Every public rubric template normalizes to **1.0** total weight.
- **B004 — Public/teacher split integrity**
  - The public pack contains only `benchmark_ready` + `student_visible` families.
  - Blocked `teacher_only` families remain excluded and named honestly.
  - Leak audit on tracked public pack artifacts reports zero teacher-only field/token hits.
- **B005 — Provenance coverage**
  - Every public episode records public provenance back to its training seed scenario plus the governing public spec/doc references.
  - Coverage must be at least `>= 90%`; clean-spine promotion currently records `100%`.
- **B006 — Promotion readiness clarity**
  - The manifest and docs explicitly say what the pack is ready to promote now, and what remains blocked.
  - Every candidate family carries a readiness state from the allowed set:
    - `draft`
    - `benchmark_ready`
    - `rewrite_before_holdout_promotion`
    - `blocked`
  - Promotion readiness here means **public benchmark-pack promotion only**, not sealed certification.

## Acceptance criteria

- A machine-readable family registry exists for episode families.
- A machine-readable episode registry exists at `data/episode-registry/public-benchmark-pack-v1.json`.
- `public-benchmark-pack-v1` contains only `benchmark_ready` + `student_visible` families.
- Blocked teacher-only families are listed with rewrite requirements.
- The pack contains at least 10 concrete public episodes.
- Every public episode maps to a complete public rubric template.
- Every public rubric template has normalized weights.
- Every public episode has public provenance coverage.
- Tracked public pack artifacts carry an explicit leak-audit outcome.
- Every candidate family carries an explicit readiness state.
- Tests verify B001–B006 plus the inclusion/exclusion contract.

## Done when

Role Foundry can honestly say:
- there is a public benchmark pack the autoresearch loop can use now
- teacher-only / holdout-derived families are **not** being misrepresented as public-safe
- public rubrics, provenance, leak-audit evidence, and readiness states are explicit enough to audit
- the pack is ready to promote for **public regression/training use**
- future sealed-eval work is clearly marked as rewrite-needed before holdout promotion
- this is **not a sealed certification exam**

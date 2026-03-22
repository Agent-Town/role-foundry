# Spec 008 — Public Benchmark Pack v1

## Intent

Turn the episode-registry / flywheel work into the first **public-safe benchmark pack** that the autoresearch loop can use immediately without pretending the repo already has a clean sealed-eval dataset.

## Requirements

1. The public pack must include **only** student-visible, benchmark-ready episode families.
2. Any family derived from current repo-visible holdout / teacher-only material must be **blocked_pending_rewrite** and excluded from the public pack.
3. The student-visible vs teacher-only separation must be explicit in machine-readable data.
4. The public pack must be honest about its scope:
   - usable now for public training / regression loops
   - not a sealed certification exam
5. The pack must be concrete enough for use now:
   - family registry
   - benchmark pack manifest
   - concrete episodes/prompts
   - verifier guidance

## Acceptance criteria

- A machine-readable registry exists for episode families.
- `public-benchmark-pack-v1` contains only `benchmark_ready` + `student_visible` families.
- Blocked teacher-only families are listed with rewrite requirements.
- The pack contains at least 10 concrete public episodes.
- Tests verify the inclusion/exclusion contract.

## Done when

Role Foundry can honestly say:
- there is a public benchmark pack the autoresearch loop can use now
- teacher-only / holdout-derived families are **not** being misrepresented as public-safe
- future sealed-eval work is clearly marked as blocked pending rewrite

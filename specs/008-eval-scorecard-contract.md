# Spec 008 — Eval Scorecard Contract

## Intent

Define the exact machine-readable contract Role Foundry uses to judge whether a new dogfood run is **better / equal / worse** than the previous one.

This contract is for promotion decisions in the autoresearch loop.

## Hard integrity gates first

These gates are evaluated in this order and checked **before** weighted scoring:

1. `no_holdout_leakage`
2. `no_fake_claims`
3. `demo_tests_still_work`
4. `required_artifacts_present`

If candidate and baseline differ on any gate, the **first differing gate in that order decides** the verdict.

That means:
- candidate passes a gate that baseline fails → `better`
- candidate fails a gate that baseline passes → `worse`
- if both fail the same gate set, verdict is `equal` and weighted promotion is blocked

## Weighted categories

Weighted scoring is only promotion-relevant when **all integrity gates pass** on both runs.

Weights:
- `spec_correctness` / spec correctness → 0.25
- `sealed_holdout_performance` / sealed holdout performance → 0.25
- `public_curriculum_performance` / public curriculum performance → 0.20
- `proof_artifact_completeness` / proof artifact completeness → 0.15
- `judge_clarity` / judge clarity → 0.10
- `efficiency` / efficiency → 0.05

`sealed_holdout_performance` and `public_curriculum_performance` are derived from teacher scenario scores.
The other categories are explicit teacher/verifier inputs.

## Equality band

When both runs pass all integrity gates:
- total score delta >= `+0.03` → `better`
- total score delta <= `-0.03` → `worse`
- otherwise → `equal`

## Scorecard shape

```json
{
  "contract_version": "role-foundry-eval/v1",
  "run_id": "run-eval-002",
  "integrity_passed": true,
  "integrity_gates": [
    {
      "id": "no_holdout_leakage",
      "label": "No holdout leakage",
      "passed": true,
      "reason": "Sealed holdout prompts stay out of student-facing receipts.",
      "evidence": ["request.json", "artifact-bundle.json"]
    }
  ],
  "weighted_categories": {
    "spec_correctness": {
      "weight": 0.25,
      "score": 0.92,
      "weighted_score": 0.23,
      "reason": "Implementation matches the intended contract."
    },
    "sealed_holdout_performance": {
      "weight": 0.25,
      "score": 0.75,
      "weighted_score": 0.1875,
      "source": "derived_from_holdout_scenarios"
    }
  },
  "total_score": 0.8762,
  "comparison": {
    "verdict": "better",
    "deciding_axis": "weighted_total",
    "total_score_delta": 0.3675,
    "reasons": []
  }
}
```

## Input shape

The current deterministic lane expects the teacher request payload to provide:

```json
{
  "teacher_evaluation": {
    "scenarios": [],
    "eval_contract": {
      "integrity_checks": {
        "no_holdout_leakage": { "passed": true, "reason": "...", "evidence": [] },
        "no_fake_claims": { "passed": true, "reason": "...", "evidence": [] },
        "demo_tests_still_work": { "passed": true, "reason": "...", "evidence": [] },
        "required_artifacts_present": { "passed": true, "reason": "...", "evidence": [] }
      },
      "category_scores": {
        "spec_correctness": { "score": 0.92, "reason": "..." },
        "proof_artifact_completeness": { "score": 0.96, "reason": "..." },
        "judge_clarity": { "score": 0.91, "reason": "..." },
        "efficiency": { "score": 0.74, "reason": "..." }
      }
    },
    "previous_iteration": {
      "run_id": "run-eval-001",
      "eval_scorecard": {}
    }
  }
}
```

## What is real now

Real now:
- `runner_bridge.eval_scorecard` builds `role-foundry-eval/v1`
- `LocalReplayRunner` emits the scorecard into `result.json`, `artifact-bundle.json`, and control-plane patches
- comparison reasons are explicit and machine-readable
- honest example fixtures and tests cover integrity overrides and normal weighted comparisons

## What still depends on later live wiring

Still later:
- a live teacher/evaluator backend producing these inputs automatically
- a control-plane or UI surface consuming the scorecard live instead of only from local receipts
- full repeated autoresearch loops with live builder + judge model lanes

The contract is real now. The live producers/consumers for that contract are still being wired.

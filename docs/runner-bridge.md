# Runner Bridge — Hackathon Fast Path

## The problem

Role Foundry needs to dispatch runs without lying about auth or pretending Clawith magically speaks consumer subscriptions.

Two things are true at once:
1. **Clawith is the control plane** for role/run state.
2. **Actual execution can live outside Clawith** behind a narrow machine-to-machine bridge.

That is the hackathon-fast, honest path.

## The implemented Milestone 4 slice

The repo now ships one working bridge path:

```text
python3 -m runner_bridge.cli
  → validates the run request contract
  → marks the run as running
  → executes one external adapter
  → persists transcript + artifact bundle under runtime/runs/<run_id>/
  → patches final status back to the control plane
```

The first adapter was **LocalReplayRunner**.

That remains deliberate:
- it is **zero-secret**
- it is **portable**
- it proves the lifecycle and storage contract without requiring Claude/Codex credentials
- it gives us a local/mockable path when a real Clawith image or provider credentials are unavailable

The repo now also ships a narrow **ClaudeVibeRunner** slice for the student/builder lane.

That Claude path is intentionally constrained:
- it shells out to the local `claude` CLI in `--print` mode
- it uses `--setting-sources project` plus repo-local `.claude/` assets instead of depending on or modifying global `~/.claude/settings.json`
- it fails explicitly when the Claude CLI is missing, unauthenticated, or returns unusable output
- it keeps teacher-only holdout prompts out of the student prompt even when the raw request contains `teacher_evaluation`

This is not consumer OAuth. It is not pretending Clawith natively owns a Claude subscription. It is a narrow bridge.

## The implemented Milestone 5 extension

The same bridge now carries one honest teacher-evaluation slice.

If a request includes an optional `teacher_evaluation` payload, `LocalReplayRunner` will:
- keep the **student view** limited to public curriculum only
- keep sealed holdout prompt text out of judge-facing artifact files
- emit a **teacher scorecard** with per-scenario notes plus aggregate score
- collapse failed holdouts into **public curriculum themes** instead of leaking hidden prompts
- record **iteration history** with score deltas versus the prior run

The important line: the teacher can know more than the student without the repo leaking the sealed exam into the student-facing bundle.

## Current bridge shape

```text
Operator / script
  → runner_bridge.cli
  → Clawith-compatible control plane
  → LocalReplayRunner or ClaudeVibeRunner
  → transcript.ndjson + artifact-bundle.json + result.json
```

Current adapters on the same bridge command:
- `--backend local-replay` → deterministic zero-secret lifecycle + teacher-eval loop
- `--backend claude-vibe` → real Claude student/builder shell adapter with project-local `.claude/` profile assets

Future adapters can slot into the same bridge command:
- CodexRunner
- deterministic verifier scripts

## Canonical Frontend Apprentice pack

The Frontend Apprentice alpha path now has one canonical pack:

- `datasets/frontend-apprentice/alpha-pack.json`

That manifest is the source of truth for:
- the seed payload used by `seed/bootstrap.py`
- `runner_bridge/examples/first-live-run.json`
- `runner_bridge/examples/teacher-eval-baseline.json`
- `runner_bridge/examples/teacher-eval-loop.json`

Those committed JSON files remain in the repo as compatibility exports, but they are derived from the canonical pack and can be checked with:

```bash
python3 -m runner_bridge.dataset_pack check
```

## Bundled control-plane alpha demo

The repo now also ships one evidence-producing alpha script:

```bash
python3 -m runner_bridge.alpha_demo
```

That script is deliberately honest:
- by default it starts a repo-local **Clawith-compatible shim**
- it seeds the canonical role + scenarios over HTTP
- it runs the canonical **baseline** request first and records a real `queued → running → completed` lifecycle
- it derives the candidate request's `previous_iteration` block from the actual baseline scorecard receipts
- it registers the candidate with explicit lineage (`root_run_id`, `parent_run_id`, `iteration_index`)
- it reads both final run records back and writes per-run `control-plane-summary.json` files plus `baseline-candidate-summary.json`

This proves the control-plane/data-loop spine without claiming native upstream Clawith support for the exact same endpoints.

## Request contract

Each run request must include:

```json
{
  "run_id": "run-live-001",
  "agent_role": "student",
  "scenario_set_id": "public-curriculum-v1",
  "workspace_snapshot": {},
  "time_budget": { "seconds": 60 },
  "cost_budget": { "usd": 1.5 }
}
```

Those are the required Milestone 4 fields:
- `run_id`
- `agent_role`
- `scenario_set_id`
- `workspace_snapshot`
- `time_budget`
- `cost_budget`

### Optional teacher evaluation payload

Milestone 5 adds one optional extension:

```json
{
  "teacher_evaluation": {
    "teacher": { "name": "Robin + Neo", "agent_role": "teacher" },
    "student": { "name": "Frontend Apprentice", "agent_role": "student" },
    "previous_iteration": {
      "run_id": "run-eval-001",
      "aggregate_score": { "passed": 2, "total": 5, "pass_rate": 0.4 }
    },
    "scenarios": [
      {
        "id": "t4",
        "type": "training",
        "student_prompt": "Leave a proof bundle",
        "passed": true,
        "score": 1.0,
        "teacher_notes": "Receipts are clear now."
      },
      {
        "id": "h2",
        "type": "holdout",
        "holdout_prompt": "Judge-only hidden prompt text",
        "passed": false,
        "score": 0.6,
        "teacher_notes": "Still too close to leaking the exam.",
        "public_failure_theme": "Explain evaluation integrity without leaking the exam",
        "public_failure_summary": "Teach the public lesson, not the hidden prompt."
      }
    ]
  }
}
```

The backend may receive the raw teacher payload, but the artifact directory keeps a redacted student-safe request view. The alpha-demo iteration flow now also derives the candidate `previous_iteration` block from the actual baseline receipts instead of hard-coding a fake historical success.

For the current `role-foundry-eval/v1` scorecard, the teacher payload may also include:
- `teacher_evaluation.eval_contract.integrity_checks`
- `teacher_evaluation.eval_contract.category_scores`
- `teacher_evaluation.previous_iteration.eval_scorecard`

That is the machine-readable comparison seam the later autoresearch loop can consume.

For `ClaudeVibeRunner`, the prompt sent to Claude is built from a **student-safe derived view**: visible training scenarios, public curriculum themes, and the sealed holdout count. The holdout prompt text itself never enters the Claude prompt.

## Result contract

Each adapter must leave a `result.json` that the bridge can normalize into:

```json
{
  "status": "completed",
  "transcript_path": "transcript.ndjson",
  "artifact_bundle_path": "artifact-bundle.json",
  "machine_score": 0.8,
  "scorecard": {}
}
```

Allowed statuses are:
- `completed`
- `failed`
- `timeout`

Failure is first-class. A failed run still needs receipts.

### Teacher scorecard shape

When `teacher_evaluation` is present, the scorecard now carries:
- teacher identity and `agent_role: "teacher"`
- student identity and `agent_role: "student"`
- aggregate score (`passed`, `total`, `pass_rate`, `average_score`)
- per-scenario notes
- public curriculum themes derived from failed holdouts
- iteration history with score deltas

That is the Milestone 5 storage contract.

### `role-foundry-eval/v1` contract

The current deterministic teacher lane now also emits a narrow machine-readable promotion contract for the dogfood autoresearch loop.

Hard integrity gates are checked first, in this order:
- `no_holdout_leakage`
- `no_fake_claims`
- `demo_tests_still_work`
- `required_artifacts_present`

If candidate and baseline differ on any gate, the **first differing gate decides** the verdict. Weighted scoring only matters when both runs pass every integrity gate.

Weighted categories and weights:
- `spec_correctness` → `0.25`
- `sealed_holdout_performance` → `0.25`
- `public_curriculum_performance` → `0.20`
- `proof_artifact_completeness` → `0.15`
- `judge_clarity` → `0.10`
- `efficiency` → `0.05`

`sealed_holdout_performance` and `public_curriculum_performance` are derived from teacher scenario scores. The other categories are explicit teacher/verifier inputs inside `teacher_evaluation.eval_contract.category_scores`.

When both runs pass integrity, the comparison semantics are explicit **better / equal / worse** semantics:
- `total_score_delta >= +0.03` → `better`
- `total_score_delta <= -0.03` → `worse`
- otherwise → `equal`

Current score output shape:

```json
{
  "contract_version": "role-foundry-eval/v1",
  "integrity_passed": true,
  "integrity_gates": [],
  "weighted_categories": {
    "spec_correctness": {
      "weight": 0.25,
      "score": 0.92,
      "weighted_score": 0.23
    }
  },
  "total_score": 0.8762,
  "comparison": {
    "verdict": "better",
    "deciding_axis": "weighted_total",
    "reasons": []
  }
}
```

That contract is **real now** on `LocalReplayRunner`. It is stored in `result.json`, mirrored into the teacher output inside `artifact-bundle.json`, and included in the final control-plane patch payload.

What is **not** claimed yet: later live wiring still needs a real teacher/evaluator backend to generate these inputs automatically, and the web UI still does not consume this contract live.

## Control-plane patch contract

For this milestone we keep the control-plane contract narrow and mockable.

The bridge sends:

### Run starts

`PATCH /api/runs/{run_id}`

```json
{
  "status": "running",
  "started_at": "2026-03-22T08:00:00Z",
  "agent_role": "student",
  "scenario_set_id": "public-curriculum-v1"
}
```

### Run finishes

`PATCH /api/runs/{run_id}`

```json
{
  "status": "completed",
  "finished_at": "2026-03-22T08:00:12Z",
  "transcript_path": "/abs/path/runtime/runs/run-live-001/transcript.ndjson",
  "artifact_bundle_path": "/abs/path/runtime/runs/run-live-001/artifact-bundle.json",
  "machine_score": 0.8,
  "scorecard": {}
}
```

If the adapter fails, the same endpoint is patched with `status: "failed"` (or `timeout`) plus an `error` field.

Important: this is the **bridge-side contract** Role Foundry can target today. It is intentionally small so it can be implemented against a fake server in tests or shimmed onto a real Clawith instance without inventing fake upstream capabilities.

## Artifact layout

By default the bridge writes to:

```text
runtime/runs/<run_id>/
  request.json
  request.private.json
  stdout.log
  stderr.log
  transcript.ndjson
  artifact-bundle.json
  result.json
  student-view.json          # evaluation runs only
  teacher-scorecard.json     # evaluation runs only
```

`ClaudeVibeRunner` adds a few backend-specific receipts in the same run directory:

```text
claude-prompt.txt
claude-invocation.json
claude-response.json
claude.stderr.log
```

`request.json` is the redacted artifact copy.

`request.private.json` is the raw backend input. That split is what keeps holdout prompt text out of the student-facing bundle while still letting the teacher side evaluate the run.

For evaluation runs, the bridge also emits:
- `student-view.json` — the student-safe prompt pack and promoted public curriculum themes
- `teacher-scorecard.json` — the teacher-facing score output, including iteration history, without sealed holdout prompt text

## First live run

Against a Clawith-compatible endpoint:

```bash
python3 -m runner_bridge.cli \
  --request runner_bridge/examples/first-live-run.json \
  --clawith-url http://localhost:3000 \
  --clawith-secret "$CLAWITH_SECRET"
```

Teacher evaluation demo:

```bash
python3 -m runner_bridge.cli \
  --request runner_bridge/examples/teacher-eval-baseline.json \
  --clawith-url http://localhost:3000 \
  --clawith-secret "$CLAWITH_SECRET"
```

```bash
python3 -m runner_bridge.cli \
  --request runner_bridge/examples/teacher-eval-loop.json \
  --clawith-url http://localhost:3000 \
  --clawith-secret "$CLAWITH_SECRET"
```

Without a control plane, to exercise the local receipts path only:

```bash
python3 -m runner_bridge.cli \
  --request runner_bridge/examples/first-live-run.json
```

Claude student smoke run (requires local `claude` auth, uses project-local `.claude/` assets only):

```bash
python3 -m runner_bridge.cli \
  --backend claude-vibe \
  --request runner_bridge/examples/claude-vibe-smoke.json
```

Canonical alpha path with inspectable baseline → candidate state and lineage:

```bash
python3 -m runner_bridge.alpha_demo
```

Single-request compatibility path:

```bash
python3 -m runner_bridge.alpha_demo --flow request --request-name first_live_run
```

The second command is not a claim that Clawith is running. It is just the fastest zero-secret way to verify the transcript/artifact contract locally.
The Claude smoke command is not a claim that the full dogfood loop is done. It only proves that Role Foundry can now drive one real Claude-backed student run through the bridge while keeping the profile repo-local and failure states explicit.
The alpha-demo command is not a claim that upstream Clawith already exposes this exact API. It proves the repo can now write and read a real two-run iteration slice through an honestly named Clawith-compatible seam.

## What is still not done

- no native consumer OAuth in Clawith
- no claim that Clawith already ships these exact run-patch endpoints upstream
- no CodexRunner wired yet for the intended teacher/critic/evaluator split
- no web UI reading live run state yet
- `ClaudeVibeRunner` is still a narrow shell adapter, not a full autonomous dogfood pipeline with repeated builder iterations, sandboxed per-run Claude homes, or live teacher scoring

That is fine. The slice is still useful because it now proves two honest paths: a deterministic local/mockable lifecycle for evaluation contracts, and a project-local Claude-backed student run path that leaves receipts without pretending the whole stack is finished.

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

The first adapter is **LocalReplayRunner**.

That is deliberate:
- it is **zero-secret**
- it is **portable**
- it proves the lifecycle and storage contract without claiming Claude/Codex wiring that is not finished yet
- it gives us a local/mockable path when a real Clawith image or provider credentials are unavailable

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
  → LocalReplayRunner (today)
  → transcript.ndjson + artifact-bundle.json + result.json
```

Future adapters can slot into the same bridge command:
- ClaudeVibeRunner
- CodexRunner
- deterministic verifier scripts

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

The backend may receive the raw teacher payload, but the artifact directory keeps a redacted student-safe request view.

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
```

`request.json` is the redacted artifact copy.

`request.private.json` is the raw backend input. That split is what keeps holdout prompt text out of the student-facing bundle while still letting the teacher side evaluate the run.

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
  --request runner_bridge/examples/teacher-eval-loop.json \
  --clawith-url http://localhost:3000 \
  --clawith-secret "$CLAWITH_SECRET"
```

Without a control plane, to exercise the local receipts path only:

```bash
python3 -m runner_bridge.cli \
  --request runner_bridge/examples/first-live-run.json
```

The second command is not a claim that Clawith is running. It is just the fastest zero-secret way to verify the transcript/artifact contract locally.

## What is still not done

- no native consumer OAuth in Clawith
- no claim that Clawith already ships these exact run-patch endpoints upstream
- no ClaudeVibeRunner wired yet
- no web UI reading live run state yet

That is fine. The slice is still useful because it proves one honest run lifecycle end to end, and now also proves a narrow teacher evaluation + iteration loop without leaking holdout prompt text into student-facing artifacts.

# Spec 015 — Sealed Receipt Surface (Public-Safe Honesty Boundary)

## Goal

Define the public-safe sealing / tamper-evidence receipt surface above the now-proven local private-holdout alpha path. This spec does **not** introduce sealed evaluation, sealed certification, tamper-proof execution, or independent audit claims. It records what the system can honestly say today and what controls are missing before stronger language becomes honest.

## Status tiers

### Allowed now: local private-holdout alpha execution

The autoresearch alpha loop can today:

- Execute a baseline → candidate-student → candidate-teacher-eval lifecycle
- Load fresh teacher-only holdouts from a gitignored local manifest
- Produce a `better` / `equal` / `worse` comparison receipt
- Keep teacher-only content out of tracked and student-visible artifacts
- Record an integrity gate that distinguishes `public_regression` from `local_private_holdout` mode
- Emit a `sealing_receipt` block in the alpha receipt that records the claim ceiling, operator checklist states, and blocked stronger claims with explicit reasons

The **claim ceiling** for this tier is: *local private-holdout alpha execution with public-safe receipts*.

### Blocked now (with reasons)

| Blocked claim | Why it is blocked |
|---|---|
| Sealed evaluation | No independent executor or sandbox isolates the student from holdout content at runtime |
| Sealed certification | No third-party auditor has reviewed or signed the holdout separation |
| Tamper-proof execution | The operator controls the local machine; no hardware attestation or remote enclave is used |
| Independent audit | No external party has inspected the holdout manifest, run artifacts, or scoring pipeline |

### Required controls before stronger language becomes honest

| Prerequisite | Enables |
|---|---|
| Independent executor sandbox (student cannot read holdout files at runtime) | "sealed evaluation" language |
| Third-party holdout auditor signs the manifest before the run | "sealed certification" language |
| Hardware attestation or remote enclave execution with verifiable logs | "tamper-proof" language |
| External audit of the scoring pipeline, holdout manifest, and run artifacts | "independently audited" language |
| Independently published or third-party-witnessed cryptographic commitment to holdout manifest hash before the run | Stronger tamper-evidence claims beyond local correlation |

### What can be recorded today without leaking teacher-only content

The `sealing_receipt` block in the alpha receipt is designed to be **public-safe**:

- `claim_ceiling` — the strongest honest claim the run supports (plain string)
- `status` — current tier (e.g. `local_private_holdout_alpha`)
- `operator_checklist` — which controls are present vs missing, each with a boolean and a reason
- `blocked_claims` — list of stronger claims that are explicitly blocked, each with a reason
- `stronger_claim_prerequisites` — what would need to be true before each blocked claim could be unblocked
- `private_manifest_fingerprint` — if a private holdout manifest was loaded, a SHA-256 of its canonical JSON bytes; labeled as **local operator correlation only**, not independent tamper-proofing
- `pre_run_manifest_commitment` — if a private holdout manifest was loaded, a commitment artifact written **before** any stage execution begins, recording the manifest hash, timestamp, and sequence linkage (see below)
- `linked_receipt_paths` — relative paths to the alpha receipt, request copy, and (when present) pre-run commitment within the artifacts root
- `integrity_gate_mode` — forwarded from the existing integrity gate

The fingerprint is **not** a seal. It lets the same operator correlate a receipt with a manifest later. It does not prove anything to a third party because the operator controls both sides.

### Pre-run manifest commitment

When the run actually enters the local private-holdout lane, the alpha loop writes a `pre-run-manifest-commitment.json` artifact **before any stage execution begins**. This records only public-safe metadata:

- the canonical SHA-256 hash of the manifest plus the canonicalization string used to derive it
- an ISO 8601 UTC timestamp
- the run's sequence id
- the relative artifact path for the commitment itself
- linkage back to `autoresearch-alpha.request.json` and `autoresearch-alpha.json`
- an explicit honesty note that this is local-only operator evidence, not external publication, third-party proof, or tamper-proofing

This improves **local auditability and operator evidence only**. The operator can later verify that the manifest hash existed in a local receipt before any stage results were produced. It does **not** constitute:

- external publication or broadcast
- third-party signing or attestation
- tamper-proofing (the operator controls both sides)

## Machine-readable surface

The `sealing_receipt` is a top-level field on the alpha receipt JSON emitted by `runner_bridge.autoresearch_alpha`. See the implementation for the exact schema.

## Non-goals

- Inventing crypto theater (signatures nobody verifies, hashes labeled as proofs)
- Claiming the fingerprint is tamper-proofing
- Adding runtime overhead beyond a single SHA-256 of manifest bytes
- Touching private prompts, rubrics, or episodes

## Done when

- Spec 015 is in the repo
- `sealing_receipt` appears in alpha receipt output
- Tests pin: claim ceiling, blocked claims, checklist states, fingerprint labeling, and the local-only pre-run commitment artifact/path
- README mentions the receipt surface and lists unmet prerequisites
- No overclaiming language anywhere in the changeset

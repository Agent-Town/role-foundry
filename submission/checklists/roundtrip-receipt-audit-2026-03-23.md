# Roundtrip receipt audit — 2026-03-23

Scope audited on the clean submission-candidate worktree:
- branch: `origin/review/submission-candidate-finished-lanes-20260323-1129`
- commit: `363b7e0548edba4c322ff65c2aeaa01b8fb09818`
- tracked proof index: `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`

Claim boundary kept intentionally narrow:
- **verified:** one real external `Clawith -> OpenClaw gateway -> Claude/vibecosystem -> Clawith` roundtrip
- **not upgraded to:** native Clawith parity, sealed eval, tamper-proof proof, or broad production hardening

## Receipt verification result

- [x] The tracked manifest parses cleanly and still points to the external gateway-backed roundtrip only.
- [x] The manifest `source_review_branch` / `source_review_commit` still point at the rescue review source: `origin/review/clawith-vibe-roundtrip-demo-20260323-1000` @ `4dab2a9866b86df4525d9698a7c844ab538ac61c`.
- [x] The landed proof-fold lane remains the submission-packaging carrier: `origin/review/submission-readiness-roundtrip-proof-20260323-1005` @ `c353d88b866419d3da6cbb5ff7470f442310c0cc`, with the manifest introduced in `ea7226070b1b71c8a033735b325a029a6e5c467b` and downstream packet refs filled on candidate head `363b7e0548edba4c322ff65c2aeaa01b8fb09818`.
- [x] Repo-visible support paths named by the manifest exist on the candidate branch: `docs/clawith-vibecosystem-real-path.md`, `scripts/clawith_link_openclaw.py`, `scripts/clawith_vibe_once.py`, and `scripts/clawith_ws_roundtrip.js`.
- [x] Script sanity passed on the candidate branch:
  - `python3 -m py_compile scripts/clawith_link_openclaw.py scripts/clawith_vibe_once.py`
  - `/Users/robin/.nvm/versions/node/v24.14.0/bin/node --check scripts/clawith_ws_roundtrip.js`
- [x] The local-only receipt roots referenced by the manifest do exist on the maintainer machine in the local `clawith-vibe-roundtrip-demo` worktree, at the same repo-relative paths named by the manifest:
  - `artifacts/clawith-roundtrip/rescue-proof/20260323T025241Z`
  - `artifacts/clawith-gateway/rescue-proof/20260323T025254Z`
- [x] Cross-checks across those two receipt roots match the manifest exactly:
  - agent: `vibecosystem-adapter` / `8e6d247d-5b59-4211-9afc-42cdb036782e`
  - session: `65d9ecda-b1f9-442d-bbf6-2b09573882de`
  - gateway message: `fc7f2137-2d6e-4047-9061-03e7dca481c2`
  - websocket placeholder observed before the final reply
  - Claude input transport: `stdin`
  - gateway report status: `ok`
  - final reply visible in worker stdout, websocket receipts, and session transcript:
    - `REAL_GATEWAY_ROUNDTRIP_OK_20260323_0958Z`
    - `CLAWITH_CONTROL_PLANE_VIBECOSYSTEM_EXECUTOR`
- [x] No raw receipt directories are tracked by git in this repo state: `git ls-files 'artifacts/**'` returned no tracked files.
- [x] The local receipt roots are currently protected from accidental add/commit by local exclude rules: `git check-ignore -v artifacts/...` resolves to `.git/info/exclude` entry `artifacts/`.

## Important caveat

The raw receipt directories remain **local-only**.

That is acceptable for this packaging pass because the tracked manifest is explicitly designed to index a single real rescue capture **without committing raw receipt trees** into the public submission branch. The clean candidate worktree does **not** itself contain those raw directories; verification required checking the maintainer's local rescue worktree.

If the proof needs to travel off-machine or survive worktree cleanup, the receipts should be exported/redacted into a reviewer-safe bundle and the manifest should be updated to point at that new location.

## Audit conclusion

For the intended scoped submission claim, the receipts are **consistent enough for submission use**.

The only non-blocking weakness is operational, not evidentiary: the raw receipt roots are local-worktree artifacts guarded by `.git/info/exclude`, so future reviewers will need either the same local worktree preserved or a sanitized exported bundle.

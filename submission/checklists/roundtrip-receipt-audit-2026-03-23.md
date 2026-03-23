# Roundtrip receipt audit — 2026-03-23

Historical audit note carried forward into the current submission packet because the tracked manifest and portable bundle are unchanged on this branch.

Current packet branch referencing this audit:
- branch: `review/submission-packet-assembly-20260323-1421`

Original audit scope on the clean submission-finalization worktree:
- branch: `review/submission-finalization-pass-20260323-1159`
- base commit: `363b7e0548edba4c322ff65c2aeaa01b8fb09818`
- tracked proof index: `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`
- tracked portable bundle: `submission/roundtrip-proof/roundtrip-proof.export.json`

Claim boundary kept intentionally narrow:
- **verified:** one real external `Clawith -> OpenClaw gateway -> Claude/vibecosystem -> Clawith` roundtrip
- **not upgraded to:** native Clawith parity, sealed eval, tamper-proof proof, or broad production hardening

## Receipt verification result

- [x] The tracked manifest parses cleanly and still points to the external gateway-backed roundtrip only.
- [x] The manifest `source_review_branch` / `source_review_commit` still point at the rescue review source: `origin/review/clawith-vibe-roundtrip-demo-20260323-1000` @ `4dab2a9866b86df4525d9698a7c844ab538ac61c`.
- [x] Repo-visible support paths named by the manifest exist on the candidate/finalization branch: `docs/clawith-vibecosystem-real-path.md`, `scripts/clawith_link_openclaw.py`, `scripts/clawith_vibe_once.py`, and `scripts/clawith_ws_roundtrip.js`.
- [x] Script sanity passed on the candidate branch:
  - `python3 -m py_compile scripts/clawith_link_openclaw.py scripts/clawith_vibe_once.py`
  - `/Users/robin/.nvm/versions/node/v24.14.0/bin/node --check scripts/clawith_ws_roundtrip.js`
- [x] The maintainer-local receipt roots referenced by the manifest do exist in the separate local rescue worktree, at the same repo-relative paths named by the manifest:
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
- [x] A portable tracked export bundle now exists under `submission/roundtrip-proof/` so reviewer-facing packet files no longer need to point at raw local `artifacts/...` paths.
- [x] No raw receipt directories are tracked by git in this repo state: `git ls-files 'artifacts/**'` returned no tracked files.

## Important caveat

The raw receipt directories remain **local-only**.

That is acceptable for this packaging pass because the tracked manifest now pairs those maintainer-local roots with a small reviewer-safe export bundle committed under `submission/roundtrip-proof/`. Judges and reviewers can inspect the tracked bundle first; the local-only roots remain available only for deeper maintainer revalidation.

## Audit conclusion

For the intended scoped submission claim, the receipts are **consistent enough for submission use**.

The main prior weakness — tracked packet files pointing at machine-local proof paths — has been reduced by the portable export bundle. The remaining caveat is deliberate and honest: the raw receipt roots still live outside git and should stay that way unless a future redaction/export pass is needed.

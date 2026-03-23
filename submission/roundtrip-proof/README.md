# Roundtrip proof export

This directory is the **portable reviewer-safe bundle** for the tracked external roundtrip proof.

It exists so the submission packet can point at stable repo-visible files instead of broken local `artifacts/...` paths.

## Files

- `roundtrip-proof.export.json` — sanitized summary export pulled from the maintainer-local rescue receipts
- `final-reply.txt` — exact two-line reply excerpt that became visible again through the Clawith session/websocket path
- `../clawith-vibecosystem-roundtrip-proof.manifest.json` — tracked proof index with source branch/commit, claim boundary, and maintainer-local receipt-root references
- `../checklists/roundtrip-receipt-audit-2026-03-23.md` — audit note describing the local receipt verification and the portable export handoff

## Claim boundary

What this bundle proves:
- one real external `Clawith -> OpenClaw gateway -> Claude/vibecosystem -> Clawith` roundtrip
- visible reply markers matching the tracked proof manifest
- enough stable repo-visible evidence to review the packet without committing raw receipt trees

What this bundle does **not** prove:
- native Clawith parity
- native model-pool bring-up completion
- sealed certification
- tamper-proof or third-party-sealed evaluation

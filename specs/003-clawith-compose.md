# Spec 003 — Clawith Control Plane in Compose

## Intent

Replace the current Clawith compose stub with a real, honest integration path.

## Requirements

1. `docker-compose.yml` must support a real `clawith` service without hard-coding sibling paths.
2. Live mode must depend on explicit environment/config, not hidden local state.
3. The repo must remain portable for judges.
4. When Clawith is unavailable, demo mode must still run cleanly.

## Acceptance criteria

- A documented image/build path exists for Clawith
- Health check path is documented and testable
- Bootstrap dependency order is documented
- Demo mode remains the default safe path

## Out of scope

- Native consumer OAuth in Clawith
- Production deployment hardening

## Done when

A contributor can explain exactly how Clawith fits into compose without hand-waving or hidden machine assumptions.
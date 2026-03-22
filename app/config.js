// Role Foundry — runtime config seam
// Default stays in demo mode. Future live deployments can override these values
// without changing the page templates or the demo data contract.
//
// liveDataUrl should return JSON that matches the existing top-level UI contract
// (or a partial version of it): role, scenarios, runs, scores, iterations,
// artifacts, and run_replays.

window.ROLE_FOUNDRY_CONFIG = Object.assign(
  {
    defaultMode: 'demo',
    liveDataUrl: null,
    liveLabel: 'Clawith live shell',
  },
  window.ROLE_FOUNDRY_CONFIG || {}
);

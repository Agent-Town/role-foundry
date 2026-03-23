// Role Foundry — runtime config seam
// Default stays in demo mode. Future live deployments can override these values
// without changing the page templates or the demo data contract.
//
// liveDataUrl may return either:
// 1) the existing top-level UI snapshot contract (or a partial version of it),
// 2) a live read-model envelope with `control_plane_summary` run exports, or
// 3) an autoresearch alpha receipt/envelope with inline stage exports and an
//    optional top-level sealing_receipt honesty boundary.
//
// Missing live fields stay empty. Demo mode remains the honest fallback.

window.ROLE_FOUNDRY_CONFIG = Object.assign(
  {
    defaultMode: 'demo',
    liveDataUrl: null,
    liveLabel: 'Clawith live shell',
  },
  window.ROLE_FOUNDRY_CONFIG || {}
);

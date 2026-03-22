# Known Limitations

## Environment / Execution
- Local execution assumes Docker, Postgres, Redis, and Node are available.
- In restricted environments, tests/build commands may fail due to missing system tools or package access.

## Data Acquisition
- Extraction quality depends on public page structure and robots/availability.
- Current parser set is intentionally constrained; some sites require additional site-specific rules.
- PDF and advanced SERP acquisition are not fully developed in this version.

## Providers
- Sales Navigator adapter is contract-only and feature-flag controlled.
- Clay/Apollo/PDL people/company adapters are present, but outcomes depend on API keys and allowed access.
- No provider path fabricates output when unavailable.

## UX / Product Scope
- Dashboard is focused on review workflow and does not include broad analytics/reporting modules.
- No job cancellation semantics are implemented.

## Operational Hardening
- Retry/failure recording is implemented, but production hardening would still require:
  - stronger alerting/monitoring,
  - deeper observability pipelines,
  - production auth/RBAC around review/export endpoints.

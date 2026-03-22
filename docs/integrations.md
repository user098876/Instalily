# Optional Provider Integration Approach

## Principle
Provider adapters are optional augmentation paths. Core pipeline output must remain valid when providers are absent.

## Implemented Contract Pattern
Providers return explicit structured outcomes with status and message:
- `success`
- `provider_unavailable`
- `no_relevant_data`
- other crawl/provider statuses where applicable

No adapter is allowed to fabricate people/company fields.

## Stakeholder Provider Adapters (Current)
- LinkedIn Sales Navigator adapter contract behind `ENABLE_LINKEDIN_SALES_NAV`.
- Clay people adapter contract.
- Apollo people adapter contract.
- People Data Labs people adapter contract.

Current behavior in this repo version:
- Missing keys/disabled flags -> `provider_unavailable`.
- Contract-only paths without configured live integration -> `no_relevant_data`.

## Company Enrichment Adapters (Current)
- Company website extraction.
- Clearbit/Apollo/Clay/PDL abstraction classes.

## Logging and Auditability
Every provider call path is logged in `provider_logs` with:
- provider
- endpoint/context
- status
- message
- latency

This enables operator visibility into why enrichment/stakeholder augmentation did or did not occur.

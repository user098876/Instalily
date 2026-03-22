# DuPont Tedlar Graphics & Signage Leadgen - Presentation Notes

## Problem
Sales teams need qualified, explainable targets in graphics/signage ecosystems without fabricated data.

## Solution Implemented
- Evidence-first lead pipeline with public-source provenance.
- Async execution with job visibility (queue -> running -> success/failed).
- Deterministic scoring and deterministic outreach from fact bundles.
- Human review dashboard with approve/reject/needs-review workflow.

## Pipeline Flow
1. Queue run (`POST /api/pipeline/run`).
2. Worker executes discovery, extraction, enrichment, stakeholders, scoring, outreach.
3. Step metrics/warnings/errors persist in `job_runs.details.steps`.
4. Dashboard displays leads with rationale, evidence, stakeholder context, and outreach.

## Trust Controls
- No fabricated companies/people/URLs.
- Missing evidence remains missing.
- Provider unavailability is explicit (`provider_unavailable`).
- Outreach is constrained to stored facts.

## Demo Path
- Live mode (public pages) or deterministic fixture mode (captured real pages).
- Review leads in UI, apply statuses, export CSV/JSON.

## Current Limits / Next Steps
- Optional provider adapters are mostly contract-first in this version.
- Parsing is high-precision but not exhaustive across every site pattern.
- Next: deeper site-specific parsers, production auth/RBAC, stronger observability.

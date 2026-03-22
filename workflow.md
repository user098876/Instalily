# Workflow

## 1) Configure Account + ICP
Input payload (current default in UI/API):
- account_name: `DuPont Tedlar`
- target_segment: `Graphics & Signage`
- icp_themes: protective films, signage, graphics, wraps, architectural graphics, wallcoverings, durable surfaces, anti-graffiti, UV/weather resistance

## 2) Dispatch Async Pipeline
- `POST /api/pipeline/run` queues a Celery job and returns `job_run_id`.
- Job status and step progress are tracked in `job_runs`.

## 3) Discovery
- Fetches official/public seed pages.
- Creates/updates source rows and event/association entities.
- Captures relevance snippets as evidence when available.

## 4) Extraction
- Discovers likely internal roster links from event/association pages.
- Parses roster/directory HTML with structured heuristics.
- Dedupe + provenance linking to event/association.
- Captures website only if observed in public evidence.

## 5) Enrichment
- Runs provider adapters.
- Missing credentials -> explicit `provider_unavailable` (no fake fill-in).

## 6) Stakeholders
- Finds public people pages from company site.
- Extracts person-title pairs with role targeting and confidence scoring.
- Optional provider adapter contracts run with explicit availability status.

## 7) Scoring + Outreach
- Deterministic weighted scoring with factor breakdown and caveats/disqualifiers.
- Outreach drafts generated only from evidence fact bundles.

## 8) Review in Dashboard
- Filter/sort/search lead set.
- Drill into factors, evidence snippets/links, stakeholder rationale, outreach variants.
- Apply review status (`approved`, `needs_review`, `rejected`, `pending`) + optional notes.
- Export CSV/JSON.

## Status Taxonomy
Crawl/provider status values used across pipeline:
- `success`
- `blocked`
- `no_relevant_data`
- `parser_failed`
- `rate_limited`
- `provider_unavailable`

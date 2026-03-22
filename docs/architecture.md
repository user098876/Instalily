# Architecture

## System Overview
- **Backend**: FastAPI (`backend/app`) with SQLAlchemy ORM and Alembic migrations.
- **Async Execution**: Celery worker (`workers/`) over Redis queue/backend.
- **Database**: Postgres stores sources, entities, evidence, scoring, outreach, reviews, and jobs.
- **Frontend**: React + TypeScript + Vite dashboard (`frontend/`) for review workflow.

## Runtime Components
1. API service accepts pipeline requests and serves review/export APIs.
2. API enqueues Celery task and creates `JobRun` row (`queued`).
3. Worker executes pipeline steps and updates `JobRun.details.steps`.
4. Dashboard polls jobs + records and supports review actions.

## Data Trust Model
Every surfaced lead field is traceable to one of:
- source/evidence records (`sources`, `evidence_items`),
- enrichment/provider payloads (`enrichments`, `provider_logs`),
- deterministic scoring computation (`scoring_runs`),
- deterministic outreach with fact trace (`outreach_drafts.fact_trace`).

## Pipeline Stages (Current)
- discovery
- extraction
- enrichment
- stakeholder_discovery
- scoring
- outreach

Each stage writes:
- status
- started/completed timestamps
- metrics
- warnings/errors (if any)

## Primary Tables
- `sources`, `events`, `associations`, `companies`, `company_event_links`
- `evidence_items`, `enrichments`, `stakeholders`
- `scoring_runs`, `outreach_drafts`, `review_statuses`
- `job_runs`, `provider_logs`, `account_configs`

## Adapter Boundaries
- Company/provider enrichment adapters: available with graceful skip on missing keys.
- Stakeholder provider adapters (Sales Navigator contract, Clay, Apollo, PDL): contract is present; unavailable or not-permitted paths return explicit statuses/messages.

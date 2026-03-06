# InstaLily Case Study: Evidence-First Leadgen for DuPont Tedlar (Graphics & Signage)

Production-oriented lead discovery and review workflow focused on public evidence, explainable scoring, and reviewable outreach drafts.

## What This Repository Implements
- FastAPI backend with SQLAlchemy + Alembic migrations.
- Celery + Redis async pipeline execution.
- Postgres persistence with evidence/provenance tables.
- React + TypeScript dashboard for operator review.
- Deterministic scoring (0-100) with factor breakdown and caveats.
- Deterministic outreach drafts grounded in stored facts.
- Optional provider adapters with graceful `provider_unavailable` behavior.

## What Is Optional / Provisioned (Not Fully Productized Here)
- Provider-backed people/company enrichment (Clay, Apollo, PDL, Sales Navigator adapter contract).
- Live provider API calls beyond currently implemented contract points.
- Deep site-specific parsers for every event ecosystem.

## Repository Structure
```text
/
  backend/
  frontend/
  workers/
  docs/
  scripts/
  tests/
  docker-compose.yml
  Makefile
  .env.example
```

## Core API
- `POST /api/pipeline/run` -> queues async job (`202`) and returns `job_run_id` + `task_id`.
- `GET /api/pipeline/jobs` -> recent job runs.
- `GET /api/pipeline/jobs/{job_run_id}` -> job detail with step progress.
- `GET /api/records` -> review table rows (score, rationale, evidence, outreach, status).
- `POST /api/review/company/{company_id}` -> set `approved|rejected|needs_review|pending` (+ notes).
- `GET /api/export.csv`
- `GET /api/export.json`

## Quick Start (Local)
1. Configure env:
```bash
cp .env.example .env
make venv
```

2. Start services:
```bash
docker compose up --build -d db redis backend worker frontend
```

3. Run migrations:
```bash
PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head
```

4. Queue pipeline job:
```bash
curl -s -X POST http://localhost:8000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"account_name":"DuPont Tedlar","target_segment":"Graphics & Signage","icp_themes":["protective films","signage","graphics","vehicle wraps","architectural graphics","wallcoverings","durable surfaces","anti-graffiti","UV/weather resistance"]}'
```

5. Open apps:
- Dashboard: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`

## Deterministic Demo Mode (Fixtures)
Use saved HTML from real public pages for stable evaluator demos.

1. Set in `.env`:
```env
DEMO_FIXTURE_MODE=true
DEMO_FIXTURE_MANIFEST=data/demo_fixtures/manifest.json
```

2. Ensure manifest points to real captured pages (see `data/demo_fixtures/README.md`).
3. Re-run pipeline and review results in dashboard.

## Dashboard Workflow
1. Click `Run Pipeline`.
2. Monitor `Recent Jobs` and step-level statuses.
3. Filter/sort leads by company/event/tier/status.
4. Open lead detail drawer for factors, evidence, stakeholder context, and outreach variants.
5. Apply review decision (`Approve`, `Needs Review`, `Reject`) with optional note.
6. Export CSV/JSON.

## Testing
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=backend .venv/bin/python -m pytest tests/test_async_jobs.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=backend .venv/bin/python -m pytest tests/test_pipeline_idempotency_and_records.py tests/test_roster_parser_and_fixture_mode.py tests/test_stakeholder_discovery.py tests/test_scoring.py tests/test_outreach.py -q
```

## Screenshots for Submission
Capture after at least one successful job run:
- `docs/screenshots/dashboard_overview.png`
- `docs/screenshots/job_progress.png`
- `docs/screenshots/lead_detail_drawer.png`

Recommended commands (macOS):
```bash
mkdir -p docs/screenshots
# take screenshots manually, then save with exact names above
```

## Trust / Safety Constraints
- No fabricated companies, people, URLs, or enrichment values.
- Missing evidence stays missing (`null`/empty) with explicit statuses.
- Outreach is generated only from stored fact bundles.
- Crawl/provider outcomes are explicit (`success`, `blocked`, `no_relevant_data`, `parser_failed`, `rate_limited`, `provider_unavailable`).

## Additional Documentation
- [Architecture](docs/architecture.md)
- [Workflow](docs/workflow.md)
- [Implementation Results](docs/implementation_results.md)
- [Known Limitations](docs/known_limitations.md)
- [Provider Integration Approach](docs/integrations.md)
- [Case Study Summary (PDF-ready)](docs/case_study_summary.md)
- [Demo Guide](docs/demo_guide.md)

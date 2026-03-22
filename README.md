# InstaLily: DuPont Tedlar Graphics & Signage Leadgen Prototype

Evidence-first lead discovery, qualification, stakeholder research, and outreach drafting for the DuPont Tedlar Graphics & Signage case study.

## What Is Implemented
- FastAPI backend with SQLAlchemy + Alembic.
- Celery worker over Redis for async pipeline execution.
- Postgres persistence for sources, evidence, enrichments, stakeholders, scoring, outreach drafts, reviews, and jobs.
- React + TypeScript dashboard for review, editing, and CSV/JSON export.
- Live public-web discovery by default.
- Deterministic scoring tied to DuPont Tedlar ICP signals.
- Outreach drafts generated only from stored evidence-backed fact bundles.

## Real Data vs Optional Integrations
- Default path: live public pages from official event sites, exhibitor/member directories, sponsor pages, and public company/team/news pages.
- Demo mode: disabled by default and only enabled with `DEMO_FIXTURE_MODE=true`.
- Optional integrations: Clay, Apollo, PDL, Clearbit, Sales Navigator contract hooks. Missing keys degrade to explicit `provider_unavailable` or skipped behavior.
- No fabricated companies, people, websites, titles, LinkedIn URLs, revenue values, or employee counts.

## Evidence / Provenance Model
- Every surfaced lead row is backed by stored `evidence_items` and/or provenance links.
- Dashboard rows expose source URLs, snippets, extraction methods, qualification rationale, caveats, and outreach status.
- Missing values remain null or omitted with explicit caveats such as missing website validation or insufficient outreach facts.

## Core API
- `POST /api/pipeline/run`
- `GET /api/pipeline/jobs`
- `GET /api/pipeline/jobs/{job_run_id}`
- `GET /api/records`
- `POST /api/review/company/{company_id}`
- `GET /api/export.csv`
- `GET /api/export.json`
- `GET /health`
- `GET /ready`

## Local Run
1. Create env and Python environment:
```bash
cp .env.example .env
make venv
```

2. Start infra and app containers:
```bash
docker compose up --build -d
```

3. Run migrations:
```bash
PYTHONPATH=backend .venv/bin/alembic -c backend/alembic.ini upgrade head
```

4. Queue the DuPont Tedlar pipeline:
```bash
curl -s -X POST http://localhost:8000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"account_name":"DuPont Tedlar","target_segment":"Graphics & Signage","icp_themes":["protective films","signage","graphics","vehicle wraps","architectural graphics","wallcoverings","durable printed surfaces","graffiti resistance","UV/weather resistance"]}'
```

5. Open:
- Dashboard: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`

## Demo Fixture Mode
Fixture mode exists only for deterministic demos from saved real pages.

```env
DEMO_FIXTURE_MODE=true
DEMO_FIXTURE_MANIFEST=data/demo_fixtures/manifest.json
```

If `DEMO_FIXTURE_MODE=false` or unset, the app uses live public web collection.

## Testing
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=backend .venv/bin/python -m pytest tests/test_async_jobs.py tests/test_pipeline_idempotency_and_records.py tests/test_roster_parser_and_fixture_mode.py tests/test_stakeholder_discovery.py tests/test_scoring.py tests/test_outreach.py -q
```

## Deployment
Lightweight deployment is documented in [Deployment](docs/deployment.md). The recommended path is a single VM running Docker Compose with:
- `backend`
- `worker`
- `redis`
- `postgres`
- `frontend`

## Environment Variables
Required:
- `APP_ENV`
- `DATABASE_URL`
- `REDIS_URL`
- `CORS_ORIGINS`
- `FRONTEND_API_BASE`

Optional:
- `OPENAI_API_KEY`
- `CLEARBIT_API_KEY`
- `APOLLO_API_KEY`
- `CLAY_API_KEY`
- `PEOPLEDATALABS_API_KEY`
- `SERP_API_KEY`
- `ENABLE_LINKEDIN_SALES_NAV`
- `REQUEST_TIMEOUT_SECONDS`
- `MAX_RETRIES`
- `DEMO_FIXTURE_MODE`
- `DEMO_FIXTURE_MANIFEST`
- `MAX_ROSTER_LINKS_PER_PARENT`
- `MAX_STAKEHOLDER_PAGES`

## Known Limitations
- Public-web extraction is intentionally conservative and favors precision over broad crawling.
- Optional provider integrations remain adapter-level, not fully productized live integrations.
- The dashboard is intentionally evaluator-oriented, not a full production CRM.
- Frontend build verification in this workspace requires Node/npm to be installed locally.

## Additional Docs
- [Architecture](docs/architecture.md)
- [Workflow](docs/workflow.md)
- [Integrations](docs/integrations.md)
- [Known Limitations](docs/known_limitations.md)
- [Deployment](docs/deployment.md)

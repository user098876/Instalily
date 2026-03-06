# Demo Guide (Evaluator)

## Prerequisites
- Docker + Docker Compose
- Python 3.11 (for direct local commands if needed)
- Node 20+ (only if running frontend outside Docker)

## A. Clean Setup
```bash
cp .env.example .env
docker compose down -v
docker compose up --build -d db redis backend worker frontend
PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head
```

## B. Choose Mode
### Live Mode
- Ensure `DEMO_FIXTURE_MODE=false` in `.env`.
- Queue pipeline run from UI or API.

### Deterministic Fixture Mode
- Set:
  - `DEMO_FIXTURE_MODE=true`
  - `DEMO_FIXTURE_MANIFEST=data/demo_fixtures/manifest.json`
- Manifest entries must map real public URLs to saved HTML captures.
- Restart backend + worker after env change:
```bash
docker compose restart backend worker
```

## C. Run and Observe
### From UI
1. Open `http://localhost:5173`
2. Click **Run Pipeline**
3. Watch **Recent Jobs** and step statuses
4. Inspect leads and apply review actions

### From API
```bash
curl -s -X POST http://localhost:8000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"account_name":"DuPont Tedlar","target_segment":"Graphics & Signage","icp_themes":["protective films","signage","graphics"]}'

curl -s http://localhost:8000/api/pipeline/jobs
curl -s http://localhost:8000/api/pipeline/jobs/<job_run_id>
```

## D. Review Path Checklist
- Filters/search/sort working
- Detail drawer shows:
  - factor breakdown
  - evidence snippets + links
  - stakeholder rationale
  - outreach variants
- Review actions persist (`approved`, `needs_review`, `rejected`)
- Export endpoints return data

## E. Screenshot Capture (Exact Filenames)
Create folder and capture these three files:
```bash
mkdir -p docs/screenshots
```
- `docs/screenshots/dashboard_overview.png`
- `docs/screenshots/job_progress.png`
- `docs/screenshots/lead_detail_drawer.png`

Suggested capture moments:
1. Overview with populated table and filters visible.
2. Active/complete job panel with step metrics visible.
3. Open detail drawer with evidence/outreach + review buttons visible.

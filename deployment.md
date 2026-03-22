# Deployment

## Recommended Path: Single VM with Docker Compose

This repo stays lean by deploying the existing services directly:
- `db`
- `redis`
- `backend`
- `worker`
- `frontend`

## Prerequisites
- Docker Engine with Compose plugin
- A VM with ports `80/443` open if you place a reverse proxy in front
- Public DNS or direct IP access

## Environment
Create `.env` on the target host:

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/instalily
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS=https://your-frontend-domain.com
FRONTEND_API_BASE=https://your-api-domain.com/api

DEMO_FIXTURE_MODE=false
REQUEST_TIMEOUT_SECONDS=20
MAX_RETRIES=3
MAX_ROSTER_LINKS_PER_PARENT=8
MAX_STAKEHOLDER_PAGES=6

# Optional providers
OPENAI_API_KEY=
CLEARBIT_API_KEY=
APOLLO_API_KEY=
CLAY_API_KEY=
PEOPLEDATALABS_API_KEY=
SERP_API_KEY=
ENABLE_LINKEDIN_SALES_NAV=false
```

## Exact Deploy Commands
From the repo root on the server:

```bash
docker compose pull
docker compose build
docker compose up -d db redis
docker compose run --rm backend python -m alembic -c backend/alembic.ini upgrade head
docker compose up -d backend worker frontend
docker compose ps
```

## Health Checks
- Backend health: `curl http://YOUR_HOST:8000/health`
- Backend readiness: `curl http://YOUR_HOST:8000/ready`
- Dashboard: open `http://YOUR_HOST:5173`

## Pipeline Run After Deploy
```bash
curl -s -X POST http://YOUR_HOST:8000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"account_name":"DuPont Tedlar","target_segment":"Graphics & Signage","icp_themes":["protective films","signage","graphics","vehicle wraps","architectural graphics","wallcoverings","durable printed surfaces","graffiti resistance","UV/weather resistance"]}'
```

## Railway / Render / Fly Notes
If you prefer a simple cloud platform instead of a VM:
- run `backend`, `worker`, `redis`, and `postgres` as separate services
- run Alembic as a release/predeploy command:

```bash
python -m alembic -c backend/alembic.ini upgrade head
```

- set `FRONTEND_API_BASE` to the public backend URL
- keep `DEMO_FIXTURE_MODE=false` unless you intentionally want fixture demos

## Intentionally Not Included
- full auth/RBAC
- centralized observability stack
- multi-tenant deployment topology
- orchestration beyond the existing Compose/Celery setup

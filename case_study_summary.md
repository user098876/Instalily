# Case Study Summary: DuPont Tedlar Graphics & Signage Leadgen System

## 1. AI Agent Workflow
1. **Discovery Agent**: identifies public event/association ecosystems and captures source evidence.
2. **Extraction Agent**: parses roster/directory pages into normalized companies with provenance.
3. **Stakeholder Agent**: discovers public people pages, extracts person-title pairs, and scores confidence.
4. **Scoring Agent**: computes deterministic qualification score (0-100) with factor breakdown.
5. **Outreach Agent**: drafts concise outreach variants from stored fact bundles only.
6. **Review Agent (Human-in-the-loop)**: approves/rejects/flags leads in the dashboard.

## 2. Data Processing Steps
1. Queue async run via `POST /api/pipeline/run`.
2. Worker executes stages: discovery -> extraction -> enrichment -> stakeholders -> scoring -> outreach.
3. Each stage writes status/metrics/warnings/errors to `job_runs.details.steps`.
4. Dashboard reads `GET /api/pipeline/jobs` and `GET /api/records`.
5. Reviewer inspects factor rationale, evidence links/snippets, stakeholder context, and outreach.
6. Reviewer writes decision through `POST /api/review/company/{company_id}`.

## 3. Implementation Results
- Async orchestration with Celery and explicit job lifecycle tracking.
- Evidence-first model: no fabricated rows, people, or URLs.
- Structured extraction upgrades (roster + stakeholder quality improvements).
- Deterministic scoring and outreach with explainability/fact trace.
- Review dashboard with filters, sorting, detail drill-down, and export.
- Deterministic fixture mode for repeatable demos from real captured public pages.

## 4. Limitations and Next Steps
### Current Limitations
- Some provider integrations are contract-only without full live API usage in this version.
- Parsing depth is high-precision but not exhaustive across all website patterns.
- No job cancel/resume semantics.

### Next Steps
1. Expand site-specific parsers for high-value ecosystems.
2. Implement production auth/RBAC and audit controls for review actions.
3. Extend provider adapters where approved credentials/permissions are available.
4. Add observability dashboards and alerting for pipeline operations.

## 5. Demo Script (Evaluator)
1. `cp .env.example .env`
2. `docker compose up --build -d db redis backend worker frontend`
3. `PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head`
4. Queue run from UI (`Run Pipeline`) or API.
5. Monitor Recent Jobs + step statuses.
6. Review leads in detail drawer and apply statuses.
7. Export CSV/JSON.

from copy import deepcopy
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Association, Company, Event, JobRun, Stakeholder
from app.services.discovery import DiscoveryService
from app.services.enrichment import EnrichmentService
from app.services.extraction import ExtractionService
from app.services.outreach import OutreachService
from app.services.scoring import ScoringService
from app.services.stakeholders import StakeholderService


def _utc() -> str:
    return datetime.utcnow().isoformat()


class PipelineService:
    def __init__(self, db: Session):
        self.db = db
        self.discovery = DiscoveryService(db)
        self.extraction = ExtractionService(db)
        self.enrichment = EnrichmentService(db)
        self.stakeholders = StakeholderService(db)
        self.scoring = ScoringService(db)
        self.outreach = OutreachService(db)

    def _ensure_details(self, run: JobRun, account_name: str, target_segment: str) -> dict:
        details = deepcopy(run.details or {})
        details.setdefault("account_name", account_name)
        details.setdefault("target_segment", target_segment)
        details.setdefault("steps", {})
        details.setdefault("warnings", [])
        details.setdefault("errors", [])
        run.details = details
        return details

    def _step_start(self, run: JobRun, step: str) -> None:
        details = deepcopy(run.details or {})
        steps = details.setdefault("steps", {})
        previous = steps.get(step, {})
        steps[step] = {
            "status": "running",
            "started_at": previous.get("started_at") or _utc(),
            "completed_at": None,
            "metrics": previous.get("metrics", {}),
            "warnings": previous.get("warnings", []),
            "errors": previous.get("errors", []),
        }
        run.details = details
        self.db.commit()

    def _step_complete(self, run: JobRun, step: str, metrics: dict | None = None, warnings: list[str] | None = None) -> None:
        details = deepcopy(run.details or {})
        step_row = details.setdefault("steps", {}).setdefault(step, {})
        step_row["status"] = "success"
        step_row["completed_at"] = _utc()
        step_row["metrics"] = metrics or {}
        step_row["warnings"] = warnings or []
        run.details = details
        self.db.commit()

    def _step_fail(self, run: JobRun, step: str, error: str) -> None:
        details = deepcopy(run.details or {})
        step_row = details.setdefault("steps", {}).setdefault(step, {})
        step_row["status"] = "failed"
        step_row.setdefault("started_at", _utc())
        step_row["completed_at"] = _utc()
        step_row.setdefault("metrics", {})
        step_row.setdefault("warnings", [])
        step_row.setdefault("errors", []).append(error)
        details.setdefault("errors", []).append(f"{step}: {error}")
        run.details = details
        self.db.commit()

    def _run_company_stage(self, run: JobRun, step: str, companies: list[Company], handler) -> dict:
        self._step_start(run, step)
        warnings: list[str] = []
        metrics = {"companies_processed": len(companies)}
        try:
            metrics.update(handler(companies, warnings))
            self._step_complete(run, step, metrics=metrics, warnings=warnings)
            return metrics
        except Exception as exc:
            self._step_fail(run, step, str(exc))
            raise

    def _get_or_create_run(self, account_name: str, target_segment: str, job_run_id: int | None) -> JobRun:
        if job_run_id is not None:
            run = self.db.query(JobRun).filter(JobRun.id == job_run_id).one_or_none()
            if run:
                return run
        run = JobRun(job_name="duPont_tedlar_pipeline", status="queued", details={})
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def run_for_account(
        self,
        account_name: str,
        target_segment: str,
        icp_themes: list[str],
        job_run_id: int | None = None,
    ) -> JobRun:
        run = self._get_or_create_run(account_name, target_segment, job_run_id)
        self._ensure_details(run, account_name, target_segment)
        run.status = "running"
        run.started_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(run)

        try:
            try:
                self._step_start(run, "discovery")
                self.discovery.seed_account_config(account_name, target_segment, icp_themes)
                discovered = self.discovery.discover(icp_themes)
                discovery_metrics = {
                    "sources_processed": len(discovered),
                    "events_total": self.db.query(Event).count(),
                    "associations_total": self.db.query(Association).count(),
                }
                self._step_complete(run, "discovery", discovery_metrics)
            except Exception as exc:
                self._step_fail(run, "discovery", str(exc))
                raise

            try:
                self._step_start(run, "extraction")
                extract_summary = self.extraction.extract_companies()
                self._step_complete(run, "extraction", extract_summary)
            except Exception as exc:
                self._step_fail(run, "extraction", str(exc))
                raise

            companies = self.db.query(Company).all()

            self._run_company_stage(
                run,
                "enrichment",
                companies,
                self._run_enrichment_stage,
            )

            self._run_company_stage(
                run,
                "stakeholder_discovery",
                companies,
                self._run_stakeholder_stage,
            )

            self._run_company_stage(
                run,
                "scoring",
                companies,
                self._run_scoring_stage,
            )

            stakeholders = self.db.query(Stakeholder).all()
            self._step_start(run, "outreach")
            outreach_created = 0
            outreach_warnings: list[str] = []
            for person in stakeholders:
                try:
                    draft = self.outreach.draft(person)
                    if draft:
                        outreach_created += 1
                except Exception as exc:
                    outreach_warnings.append(f"stakeholder_id={person.id}: {exc}")
            self._step_complete(
                run,
                "outreach",
                metrics={"stakeholders_processed": len(stakeholders), "outreach_created": outreach_created},
                warnings=outreach_warnings,
            )

            details = deepcopy(run.details or {})
            aggregated_warnings = []
            for _, step_data in details.get("steps", {}).items():
                aggregated_warnings.extend(step_data.get("warnings", []))
            details["warnings"] = aggregated_warnings
            run.details = details
            run.status = "success"
            run.completed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(run)
            return run
        except Exception as exc:
            run.status = "failed"
            run.completed_at = datetime.utcnow()
            details = deepcopy(run.details or {})
            details.setdefault("errors", []).append(str(exc))
            run.details = details
            self.db.commit()
            self.db.refresh(run)
            return run

    def _run_enrichment_stage(self, companies: list[Company], warnings: list[str]) -> dict:
        provider_calls = 0
        for company in companies:
            result = _collect_warning(warnings, company.display_name, self.enrichment.enrich_company, company)
            if result is not None:
                provider_calls += len(result)
        return {"provider_calls": provider_calls}

    def _run_stakeholder_stage(self, companies: list[Company], warnings: list[str]) -> dict:
        stakeholders_created = 0
        for company in companies:
            result = _collect_warning(warnings, company.display_name, self.stakeholders.discover_for_company, company)
            if result is not None:
                stakeholders_created += result
        return {"stakeholders_created": stakeholders_created}

    def _run_scoring_stage(self, companies: list[Company], warnings: list[str]) -> dict:
        companies_scored = 0
        for company in companies:
            result = _collect_warning(warnings, company.display_name, self.scoring.score_company, company)
            if result is not None:
                companies_scored += 1
        return {"companies_scored": companies_scored}


def _collect_warning(warnings: list[str], label: str, fn, *args):
    try:
        return fn(*args)
    except Exception as exc:  # pragma: no cover - exercised via service tests
        warnings.append(f"{label}: {exc}")
        return None

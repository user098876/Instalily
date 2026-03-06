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
        steps[step] = {
            "status": "running",
            "started_at": _utc(),
            "completed_at": None,
            "metrics": {},
            "warnings": [],
            "errors": [],
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
        step_row["completed_at"] = _utc()
        step_row.setdefault("errors", []).append(error)
        details.setdefault("errors", []).append(f"{step}: {error}")
        run.details = details
        self.db.commit()

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
            self._step_start(run, "discovery")
            try:
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

            self._step_start(run, "extraction")
            try:
                extract_summary = self.extraction.extract_companies()
                self._step_complete(run, "extraction", extract_summary)
            except Exception as exc:
                self._step_fail(run, "extraction", str(exc))
                raise

            companies = self.db.query(Company).all()

            self._step_start(run, "enrichment")
            enrichment_calls = 0
            enrichment_warnings: list[str] = []
            for company in companies:
                try:
                    results = self.enrichment.enrich_company(company)
                    enrichment_calls += len(results)
                except Exception as exc:
                    enrichment_warnings.append(f"{company.display_name}: {exc}")
            self._step_complete(
                run,
                "enrichment",
                metrics={"companies_processed": len(companies), "provider_calls": enrichment_calls},
                warnings=enrichment_warnings,
            )

            self._step_start(run, "stakeholder_discovery")
            stakeholders_created = 0
            stakeholder_warnings: list[str] = []
            for company in companies:
                try:
                    stakeholders_created += self.stakeholders.discover_for_company(company)
                except Exception as exc:
                    stakeholder_warnings.append(f"{company.display_name}: {exc}")
            self._step_complete(
                run,
                "stakeholder_discovery",
                metrics={"companies_processed": len(companies), "stakeholders_created": stakeholders_created},
                warnings=stakeholder_warnings,
            )

            self._step_start(run, "scoring")
            scoring_count = 0
            scoring_warnings: list[str] = []
            for company in companies:
                try:
                    self.scoring.score_company(company)
                    scoring_count += 1
                except Exception as exc:
                    scoring_warnings.append(f"{company.display_name}: {exc}")
            self._step_complete(
                run,
                "scoring",
                metrics={"companies_scored": scoring_count},
                warnings=scoring_warnings,
            )

            self._step_start(run, "outreach")
            outreach_created = 0
            outreach_warnings: list[str] = []
            for person in self.db.query(Stakeholder).all():
                try:
                    draft = self.outreach.draft(person)
                    if draft:
                        outreach_created += 1
                except Exception as exc:
                    outreach_warnings.append(f"stakeholder_id={person.id}: {exc}")
            self._step_complete(
                run,
                "outreach",
                metrics={"outreach_created": outreach_created},
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
            self._step_fail(run, "pipeline", str(exc))
            run.status = "failed"
            run.completed_at = datetime.utcnow()
            details = deepcopy(run.details or {})
            details.setdefault("errors", []).append(str(exc))
            run.details = details
            self.db.commit()
            self.db.refresh(run)
            return run

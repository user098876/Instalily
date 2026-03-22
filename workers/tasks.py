from copy import deepcopy
from datetime import datetime

from requests import RequestException

from workers.celery_app import celery_app

from app.db import SessionLocal
from app.models import JobRun
from app.services.pipeline import PipelineService


@celery_app.task(bind=True, autoretry_for=(RequestException,), retry_backoff=True, retry_jitter=True, max_retries=3)
def run_pipeline_task(self, payload: dict) -> dict:
    db = SessionLocal()
    try:
        run = db.query(JobRun).filter(JobRun.id == payload["job_run_id"]).one_or_none()
        if not run:
            run = JobRun(
                id=payload["job_run_id"],
                job_name="duPont_tedlar_pipeline",
                status="failed",
                details={"errors": ["job_run_not_found"]},
                completed_at=datetime.utcnow(),
            )
            db.add(run)
            db.commit()
            return {"job_run_id": payload["job_run_id"], "status": "failed", "reason": "job_run_not_found"}

        run.status = "running"
        details = deepcopy(run.details or {})
        details["task_id"] = self.request.id
        details.setdefault("errors", [])
        details.setdefault("warnings", [])
        run.details = details
        db.commit()

        svc = PipelineService(db)
        completed = svc.run_for_account(
            account_name=payload["account_name"],
            target_segment=payload["target_segment"],
            icp_themes=payload["icp_themes"],
            job_run_id=payload["job_run_id"],
        )
        return {"job_run_id": completed.id, "status": completed.status}
    except RequestException as exc:
        run = db.query(JobRun).filter(JobRun.id == payload.get("job_run_id")).one_or_none()
        if run:
            run.status = "retrying"
            details = deepcopy(run.details or {})
            details.setdefault("errors", []).append(f"transient_error: {exc}")
            run.details = details
            db.commit()
        raise
    except Exception as exc:
        run = db.query(JobRun).filter(JobRun.id == payload.get("job_run_id")).one_or_none()
        if run:
            run.status = "failed"
            run.completed_at = datetime.utcnow()
            details = deepcopy(run.details or {})
            details.setdefault("errors", []).append(f"worker_terminal_error: {exc}")
            run.details = details
            db.commit()
        return {"job_run_id": payload.get("job_run_id"), "status": "failed", "reason": str(exc)}
    finally:
        db.close()

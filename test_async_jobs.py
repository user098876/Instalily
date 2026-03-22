from datetime import datetime

from app.api import routes
from app.models import JobRun
from app.schemas import AccountConfigIn
from app.services.pipeline import PipelineService


class DummyAsyncResult:
    def __init__(self, task_id: str):
        self.id = task_id


class DummyTask:
    def __init__(self, task_id: str = "task-123"):
        self.task_id = task_id

    def delay(self, payload: dict):
        return DummyAsyncResult(self.task_id)


def test_async_job_creation_flow(monkeypatch, db_session):
    monkeypatch.setattr(routes, "run_pipeline_task", DummyTask("task-abc"))

    payload = AccountConfigIn(
        account_name="DuPont Tedlar",
        target_segment="Graphics & Signage",
        icp_themes=["graphics", "signage"],
    )

    created = routes.run_pipeline(payload, db_session)

    assert created.status == "queued"
    assert created.task_id == "task-abc"

    run = db_session.query(JobRun).filter(JobRun.id == created.job_run_id).one()
    assert run.status == "queued"
    assert (run.details or {}).get("task_id") == "task-abc"


def test_job_status_retrieval_endpoints(db_session):
    job1 = JobRun(job_name="a", status="queued", started_at=datetime.utcnow(), details={})
    job2 = JobRun(job_name="b", status="running", started_at=datetime.utcnow(), details={})
    db_session.add(job1)
    db_session.add(job2)
    db_session.commit()

    jobs = routes.list_jobs(db_session)
    assert len(jobs) >= 2

    detail = routes.get_job(job1.id, db_session)
    assert detail.id == job1.id
    assert detail.status == "queued"


def test_pipeline_step_level_details_persisted(db_session):
    run = JobRun(job_name="pipeline", status="queued", details={"steps": {}, "warnings": [], "errors": []})
    db_session.add(run)
    db_session.commit()

    svc = PipelineService(db_session)

    svc.discovery.seed_account_config = lambda *args, **kwargs: None
    svc.discovery.discover = lambda *args, **kwargs: []
    svc.extraction.extract_companies = lambda: {
        "inserted_companies": 0,
        "linked_records": 0,
        "source_pages_scanned": 0,
        "candidate_pages_matched": 0,
    }

    result = svc.run_for_account(
        account_name="DuPont Tedlar",
        target_segment="Graphics & Signage",
        icp_themes=["graphics"],
        job_run_id=run.id,
    )

    assert result.status == "success"
    steps = (result.details or {}).get("steps", {})
    for step in ["discovery", "extraction", "enrichment", "stakeholder_discovery", "scoring", "outreach"]:
        assert step in steps
        assert steps[step]["status"] == "success"
        assert "started_at" in steps[step]
        assert "completed_at" in steps[step]
        assert "metrics" in steps[step]
        assert "warnings" in steps[step]
        assert "errors" in steps[step]


def test_pipeline_failure_path_records_error_details(db_session):
    run = JobRun(job_name="pipeline", status="queued", details={"steps": {}, "warnings": [], "errors": []})
    db_session.add(run)
    db_session.commit()

    svc = PipelineService(db_session)

    svc.discovery.seed_account_config = lambda *args, **kwargs: None
    svc.discovery.discover = lambda *args, **kwargs: []

    def _explode():
        raise RuntimeError("extraction boom")

    svc.extraction.extract_companies = _explode

    result = svc.run_for_account(
        account_name="DuPont Tedlar",
        target_segment="Graphics & Signage",
        icp_themes=["graphics"],
        job_run_id=run.id,
    )

    assert result.status == "failed"
    details = result.details or {}
    assert any("extraction boom" in err for err in details.get("errors", []))
    extraction_step = details.get("steps", {}).get("extraction", {})
    assert extraction_step.get("status") == "failed"

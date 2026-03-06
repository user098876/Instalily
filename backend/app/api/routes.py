from copy import deepcopy
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    Association,
    Company,
    CompanyEventLink,
    Event,
    EvidenceItem,
    JobRun,
    OutreachDraft,
    ReviewState,
    ReviewStatus,
    ScoringRun,
    Stakeholder,
)
from app.schemas import AccountConfigIn, EvidenceLinkOut, JobCreateOut, JobRunOut, RecordOut, ReviewUpdateIn
from workers.tasks import run_pipeline_task

router = APIRouter(prefix="/api", tags=["leadgen"])


def _is_valid_http_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _csv_escape(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace('"', '""').replace("\n", " ").replace("\r", " ")


@router.post("/pipeline/run", response_model=JobCreateOut, status_code=202)
def run_pipeline(payload: AccountConfigIn, db: Session = Depends(get_db)) -> JobCreateOut:
    run = JobRun(
        job_name="duPont_tedlar_pipeline",
        status="queued",
        details={
            "account_name": payload.account_name,
            "target_segment": payload.target_segment,
            "warnings": [],
            "errors": [],
            "steps": {},
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        result = run_pipeline_task.delay(
            {
                "job_run_id": run.id,
                "account_name": payload.account_name,
                "target_segment": payload.target_segment,
                "icp_themes": payload.icp_themes,
            }
        )
        details = deepcopy(run.details or {})
        details["task_id"] = result.id
        run.details = details
        db.commit()
        db.refresh(run)
        return JobCreateOut(
            job_run_id=run.id,
            task_id=result.id,
            status=run.status,
            started_at=run.started_at,
            details=run.details,
        )
    except Exception as exc:
        run.status = "failed_dispatch"
        details = deepcopy(run.details or {})
        details.setdefault("errors", []).append(f"dispatch_error: {exc}")
        run.details = details
        db.commit()
        db.refresh(run)
        raise HTTPException(status_code=500, detail=f"failed to dispatch pipeline task: {exc}")


@router.get("/pipeline/jobs", response_model=list[JobRunOut])
def list_jobs(db: Session = Depends(get_db)) -> list[JobRun]:
    return db.query(JobRun).order_by(desc(JobRun.started_at)).limit(50).all()


@router.get("/pipeline/jobs/{job_run_id}", response_model=JobRunOut)
def get_job(job_run_id: int, db: Session = Depends(get_db)) -> JobRun:
    row = db.query(JobRun).filter(JobRun.id == job_run_id).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="job run not found")
    return row


@router.get("/records", response_model=list[RecordOut])
def list_records(db: Session = Depends(get_db)) -> list[RecordOut]:
    rows: list[RecordOut] = []
    companies = db.query(Company).order_by(Company.id).all()
    for company in companies:
        score = (
            db.query(ScoringRun)
            .filter(ScoringRun.company_id == company.id)
            .order_by(desc(ScoringRun.created_at))
            .first()
        )
        stakeholder = (
            db.query(Stakeholder)
            .filter(Stakeholder.company_id == company.id)
            .order_by(desc(Stakeholder.confidence_score))
            .first()
        )
        link = db.query(CompanyEventLink).filter(CompanyEventLink.company_id == company.id).first()

        parent_name = None
        if link and link.event_id:
            event = db.query(Event).filter(Event.id == link.event_id).one_or_none()
            parent_name = event.name if event else None
        elif link and link.association_id:
            association = db.query(Association).filter(Association.id == link.association_id).one_or_none()
            parent_name = association.name if association else None

        draft = (
            db.query(OutreachDraft)
            .filter(OutreachDraft.stakeholder_id == stakeholder.id)
            .order_by(desc(OutreachDraft.created_at))
            .first()
            if stakeholder
            else None
        )

        review = (
            db.query(ReviewStatus)
            .filter(ReviewStatus.entity_type == "company", ReviewStatus.entity_id == company.id)
            .one_or_none()
        )

        evidence_items = (
            db.query(EvidenceItem)
            .filter(EvidenceItem.entity_type == "company", EvidenceItem.entity_id == company.id)
            .order_by(desc(EvidenceItem.created_at))
            .limit(5)
            .all()
        )

        evidence_links: list[EvidenceLinkOut] = []
        for item in evidence_items:
            if _is_valid_http_url(item.source_url):
                evidence_links.append(
                    EvidenceLinkOut(
                        url=item.source_url,
                        label="Company Evidence",
                        source_type="company_evidence",
                        snippet=item.evidence_snippet,
                    )
                )

        if link and _is_valid_http_url(link.source_url):
            evidence_links.append(
                EvidenceLinkOut(
                    url=link.source_url,
                    label=(parent_name or "Source") + " Listing",
                    source_type="provenance",
                    snippet=link.source_context,
                )
            )

        rationale = score.explanation_bullets if score else ["No scoring run available"]
        rows.append(
            RecordOut(
                company_id=company.id,
                event_or_association=parent_name,
                company=company.display_name,
                qualification_score=score.total_score if score else None,
                score_tier=(score.tier if score else None),
                score_confidence=(score.confidence if score else None),
                score_factors=(score.factors if score else None),
                rationale=rationale,
                disqualifiers=(score.disqualifiers if score else []),
                stakeholder=stakeholder.full_name if stakeholder else None,
                stakeholder_title=stakeholder.title if stakeholder else None,
                stakeholder_rationale=(stakeholder.rationale if stakeholder else None),
                stakeholder_confidence=(stakeholder.confidence_score if stakeholder else None),
                evidence_links=evidence_links,
                outreach_preview=draft.email_opener if draft else None,
                outreach_email_opener=(draft.email_opener if draft else None),
                outreach_linkedin_note=(draft.linkedin_note if draft else None),
                outreach_three_sentence=(draft.outreach_three_sentence if draft else None),
                status=(review.status.value if review else ReviewState.pending.value),
            )
        )
    return rows


@router.post("/review/{entity_type}/{entity_id}")
def set_review_status(entity_type: str, entity_id: int, payload: ReviewUpdateIn, db: Session = Depends(get_db)) -> dict:
    if payload.status not in {x.value for x in ReviewState}:
        raise HTTPException(status_code=400, detail="invalid review status")
    row = (
        db.query(ReviewStatus)
        .filter(ReviewStatus.entity_type == entity_type, ReviewStatus.entity_id == entity_id)
        .one_or_none()
    )
    if not row:
        row = ReviewStatus(
            entity_type=entity_type,
            entity_id=entity_id,
            status=ReviewState(payload.status),
            notes=payload.notes,
        )
        db.add(row)
    else:
        row.status = ReviewState(payload.status)
        row.notes = payload.notes
        row.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.get("/export.csv")
def export_csv(db: Session = Depends(get_db)) -> Response:
    records = list_records(db)
    lines = ["event_or_association,company,qualification_score,stakeholder,title,status"]
    for r in records:
        lines.append(
            f'"{_csv_escape(r.event_or_association)}","{_csv_escape(r.company)}","{_csv_escape(r.qualification_score)}","{_csv_escape(r.stakeholder)}","{_csv_escape(r.stakeholder_title)}","{_csv_escape(r.status)}"'
        )
    return Response(content="\n".join(lines), media_type="text/csv")


@router.get("/export.json")
def export_json(db: Session = Depends(get_db)) -> list[RecordOut]:
    return list_records(db)

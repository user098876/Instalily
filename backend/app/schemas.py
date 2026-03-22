from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class AccountConfigIn(BaseModel):
    account_name: str
    target_segment: str
    icp_themes: list[str]


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: HttpUrl
    source_type: str
    crawl_status: str
    status_reason: str | None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    event_type: str
    event_date: date | None
    location: str | None
    official_url: HttpUrl
    relevance_summary: str


class CompanyScoreOut(BaseModel):
    company_id: int
    company_name: str
    total_score: float = Field(ge=0, le=100)
    tier: str
    confidence: float = Field(ge=0, le=1)
    factors: dict
    explanation_bullets: list[str]
    disqualifiers: list[str]


class StakeholderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    full_name: str
    title: str
    profile_url: str | None
    source_url: str
    confidence_score: float
    rationale: str


class OutreachOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stakeholder_id: int
    email_opener: str
    linkedin_note: str
    outreach_three_sentence: str
    fact_trace: list[dict]


class ReviewUpdateIn(BaseModel):
    status: str
    notes: str | None = None


class EvidenceLinkOut(BaseModel):
    url: HttpUrl
    label: str
    source_type: str
    snippet: str | None = None
    extraction_method: str | None = None
    provider: str | None = None
    confidence: float | None = None
    caveat: str | None = None


class RecordOut(BaseModel):
    company_id: int
    event_or_association: str | None
    company: str
    company_website: str | None = None
    company_website_status: str | None = None
    qualification_score: float | None
    score_tier: str | None
    score_confidence: float | None
    score_factors: dict | None
    rationale: list[str]
    disqualifiers: list[str]
    qualification_rationale: str | None = None
    stakeholder: str | None
    stakeholder_title: str | None
    stakeholder_profile_url: str | None = None
    stakeholder_rationale: str | None
    stakeholder_confidence: float | None
    evidence_links: list[EvidenceLinkOut]
    evidence_caveats: list[str] = []
    outreach_status: str
    outreach_preview: str | None
    outreach_email_opener: str | None
    outreach_linkedin_note: str | None
    outreach_three_sentence: str | None
    status: str


class JobRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    details: dict | None


class JobCreateOut(BaseModel):
    job_run_id: int
    task_id: str | None
    status: str
    started_at: datetime
    details: dict | None

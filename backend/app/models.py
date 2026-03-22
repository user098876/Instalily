from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class CrawlStatus(str, Enum):
    success = "success"
    blocked = "blocked"
    no_relevant_data = "no_relevant_data"
    parser_failed = "parser_failed"
    rate_limited = "rate_limited"
    provider_unavailable = "provider_unavailable"


class SourceType(str, Enum):
    event = "event"
    association = "association"
    directory = "directory"
    publication = "publication"
    search = "search"


class ReviewState(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    needs_review = "needs_review"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    source_type: Mapped[SourceType] = mapped_column(SQLEnum(SourceType), index=True)
    crawl_status: Mapped[CrawlStatus] = mapped_column(SQLEnum(CrawlStatus), default=CrawlStatus.success)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(255), default="html_extractor")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    official_url: Mapped[str] = mapped_column(String(1000), unique=True)
    relevance_summary: Mapped[str] = mapped_column(Text)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    source = relationship("Source")


class Association(Base):
    __tablename__ = "associations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    official_url: Mapped[str] = mapped_column(String(1000), unique=True)
    relevance_summary: Mapped[str] = mapped_column(Text)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    source = relationship("Source")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), index=True)
    website: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    hq: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employee_count_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    revenue_estimate: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevant_product_lines: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CompanyEventLink(Base):
    __tablename__ = "company_event_links"
    __table_args__ = (
        UniqueConstraint("company_id", "event_id", "source_url", name="uq_company_event_source"),
        UniqueConstraint("company_id", "association_id", "source_url", name="uq_company_association_source"),
        CheckConstraint(
            "(event_id IS NOT NULL AND association_id IS NULL) OR "
            "(event_id IS NULL AND association_id IS NOT NULL)",
            name="ck_company_link_exactly_one_parent",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    association_id: Mapped[int | None] = mapped_column(ForeignKey("associations.id"), nullable=True)
    source_context: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    company = relationship("Company")
    event = relationship("Event")
    association = relationship("Association")


class Enrichment(Base):
    __tablename__ = "enrichments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    provider: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[CrawlStatus] = mapped_column(SQLEnum(CrawlStatus), default=CrawlStatus.success)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Stakeholder(Base):
    __tablename__ = "stakeholders"
    __table_args__ = (
        UniqueConstraint("company_id", "full_name", "title", "source_url", name="uq_stakeholder_exact"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    profile_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000))
    confidence_score: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "source_url",
            "evidence_snippet",
            name="uq_evidence_item_exact",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    source_url: Mapped[str] = mapped_column(String(1000))
    evidence_snippet: Mapped[str] = mapped_column(Text)
    extraction_method: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScoringRun(Base):
    __tablename__ = "scoring_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    total_score: Mapped[float] = mapped_column(Float)
    tier: Mapped[str] = mapped_column(String(2), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    factors: Mapped[dict] = mapped_column(JSON)
    explanation_bullets: Mapped[list[str]] = mapped_column(JSON)
    disqualifiers: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OutreachDraft(Base):
    __tablename__ = "outreach_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stakeholder_id: Mapped[int] = mapped_column(ForeignKey("stakeholders.id"), index=True)
    email_opener: Mapped[str] = mapped_column(Text)
    linkedin_note: Mapped[str] = mapped_column(Text)
    outreach_three_sentence: Mapped[str] = mapped_column(Text)
    fact_trace: Mapped[list[dict]] = mapped_column(JSON)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    token_usage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_name: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(50), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ProviderLog(Base):
    __tablename__ = "provider_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(100), index=True)
    endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[CrawlStatus] = mapped_column(SQLEnum(CrawlStatus), default=CrawlStatus.success)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReviewStatus(Base):
    __tablename__ = "review_statuses"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", name="uq_review_entity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[ReviewState] = mapped_column(SQLEnum(ReviewState), default=ReviewState.pending)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AccountConfig(Base):
    __tablename__ = "account_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_name: Mapped[str] = mapped_column(String(255), index=True)
    target_segment: Mapped[str] = mapped_column(String(255))
    icp_themes: Mapped[list[str]] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

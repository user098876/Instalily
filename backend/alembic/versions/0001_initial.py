"""initial schema"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("target_segment", sa.String(length=255), nullable=False),
        sa.Column("icp_themes", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("crawl_status", sa.String(length=30), nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("extraction_method", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_unique_constraint("uq_sources_url", "sources", ["url"])
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("official_url", sa.String(length=1000), nullable=False),
        sa.Column("relevance_summary", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
    )
    op.create_unique_constraint("uq_events_url", "events", ["official_url"])
    op.create_table(
        "associations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("official_url", sa.String(length=1000), nullable=False),
        sa.Column("relevance_summary", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
    )
    op.create_unique_constraint("uq_associations_url", "associations", ["official_url"])
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("website", sa.String(length=1000), nullable=True),
        sa.Column("hq", sa.String(length=255), nullable=True),
        sa.Column("employee_count_range", sa.String(length=100), nullable=True),
        sa.Column("revenue_estimate", sa.String(length=100), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("relevant_product_lines", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_unique_constraint("uq_companies_norm", "companies", ["normalized_name"])
    op.create_table(
        "company_event_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=True),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("associations.id"), nullable=True),
        sa.Column("source_context", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("company_id", "event_id", name="uq_company_event"),
    )
    op.create_table(
        "enrichments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "stakeholders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("profile_url", sa.String(length=1000), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
    )
    op.create_table(
        "evidence_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("evidence_snippet", sa.Text(), nullable=False),
        sa.Column("extraction_method", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "scoring_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("tier", sa.String(length=2), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("factors", sa.JSON(), nullable=False),
        sa.Column("explanation_bullets", sa.JSON(), nullable=False),
        sa.Column("disqualifiers", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "outreach_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stakeholder_id", sa.Integer(), sa.ForeignKey("stakeholders.id"), nullable=False),
        sa.Column("email_opener", sa.Text(), nullable=False),
        sa.Column("linkedin_note", sa.Text(), nullable=False),
        sa.Column("outreach_three_sentence", sa.Text(), nullable=False),
        sa.Column("fact_trace", sa.JSON(), nullable=False),
        sa.Column("llm_model", sa.String(length=100), nullable=True),
        sa.Column("token_usage", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
    )
    op.create_table(
        "provider_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "review_statuses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("entity_type", "entity_id", name="uq_review_entity"),
    )


def downgrade() -> None:
    for table in [
        "review_statuses",
        "provider_logs",
        "job_runs",
        "outreach_drafts",
        "scoring_runs",
        "evidence_items",
        "stakeholders",
        "enrichments",
        "company_event_links",
        "companies",
        "associations",
        "events",
        "sources",
        "account_configs",
    ]:
        op.drop_table(table)

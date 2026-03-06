"""linkage and dedupe coherence

Revision ID: 0002_linkage_and_dedupe_coherence
Revises: 0001_initial
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_linkage_and_dedupe_coherence"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_event_links", sa.Column("source_url", sa.String(length=1000), nullable=True))

    op.execute(
        """
        UPDATE company_event_links
        SET source_url = split_part(source_context, '::', 2)
        WHERE source_context LIKE '%::http%'
        """
    )

    op.drop_constraint("uq_company_event", "company_event_links", type_="unique")
    op.create_unique_constraint(
        "uq_company_event_source",
        "company_event_links",
        ["company_id", "event_id", "source_url"],
    )
    op.create_unique_constraint(
        "uq_company_association_source",
        "company_event_links",
        ["company_id", "association_id", "source_url"],
    )
    op.create_check_constraint(
        "ck_company_link_exactly_one_parent",
        "company_event_links",
        "(event_id IS NOT NULL AND association_id IS NULL) OR (event_id IS NULL AND association_id IS NOT NULL)",
    )

    op.create_unique_constraint(
        "uq_stakeholder_exact",
        "stakeholders",
        ["company_id", "full_name", "title", "source_url"],
    )

    op.create_unique_constraint(
        "uq_evidence_item_exact",
        "evidence_items",
        ["entity_type", "entity_id", "source_url", "evidence_snippet"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_evidence_item_exact", "evidence_items", type_="unique")
    op.drop_constraint("uq_stakeholder_exact", "stakeholders", type_="unique")
    op.drop_constraint("ck_company_link_exactly_one_parent", "company_event_links", type_="check")
    op.drop_constraint("uq_company_association_source", "company_event_links", type_="unique")
    op.drop_constraint("uq_company_event_source", "company_event_links", type_="unique")
    op.create_unique_constraint("uq_company_event", "company_event_links", ["company_id", "event_id"])
    op.drop_column("company_event_links", "source_url")

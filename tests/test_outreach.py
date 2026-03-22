from app.models import Company, EvidenceItem, Stakeholder
from app.services.outreach import OutreachService


def test_outreach_returns_none_without_facts(db_session):
    company = Company(normalized_name="x", display_name="X")
    db_session.add(company)
    db_session.flush()
    stakeholder = Stakeholder(
        company_id=company.id,
        full_name="Alex Doe",
        title="Director",
        source_url="https://x.test/team",
        confidence_score=0.7,
        rationale="public evidence",
    )
    db_session.add(stakeholder)
    db_session.commit()

    assert OutreachService(db_session).draft(stakeholder) is None


def test_outreach_uses_fact_signals_and_stakeholder_context(db_session):
    company = Company(normalized_name="truecolor wraps", display_name="TrueColor Wraps")
    db_session.add(company)
    db_session.flush()

    stakeholder = Stakeholder(
        company_id=company.id,
        full_name="Jane Roberts",
        title="Director of Product Development",
        source_url="https://truecolor.test/team",
        confidence_score=0.88,
        rationale="public evidence",
    )
    db_session.add(stakeholder)
    db_session.flush()

    db_session.add(
        EvidenceItem(
            entity_type="company",
            entity_id=company.id,
            source_url="https://expo.test/exhibitors",
            evidence_snippet="Vehicle wrap and exterior graphics solutions with UV/weather durability.",
            extraction_method="structured_roster_parser",
        )
    )
    db_session.add(
        EvidenceItem(
            entity_type="company",
            entity_id=company.id,
            source_url="https://truecolor.test/news",
            evidence_snippet="Protective film options for fleet graphics programs and outdoor branding.",
            extraction_method="public_news_reference",
        )
    )
    db_session.add(
        EvidenceItem(
            entity_type="stakeholder",
            entity_id=stakeholder.id,
            source_url="https://truecolor.test/team",
            evidence_snippet="Jane Roberts | Director of Product Development | Leads graphics materials roadmap",
            extraction_method="html_structured_person_card",
        )
    )
    db_session.commit()

    draft = OutreachService(db_session).draft(stakeholder)
    assert draft is not None

    text_blob = " ".join([draft.email_opener.lower(), draft.linkedin_note.lower(), draft.outreach_three_sentence.lower()])
    assert "vehicle wrap" in text_blob or "wrap" in text_blob
    assert "uv" in text_blob or "weather" in text_blob or "durable" in text_blob
    assert "jane roberts" in text_blob
    assert "director of product development" in text_blob
    assert len(draft.fact_trace) >= 1
    assert draft.llm_model == "rule_based_fact_guard_v2"


def test_outreach_fact_trace_contains_source_urls(db_session):
    company = Company(normalized_name="northstar", display_name="Northstar")
    db_session.add(company)
    db_session.flush()

    stakeholder = Stakeholder(
        company_id=company.id,
        full_name="Michael Chen",
        title="VP Innovation",
        source_url="https://northstar.test/leadership",
        confidence_score=0.8,
        rationale="public evidence",
    )
    db_session.add(stakeholder)
    db_session.flush()

    db_session.add(
        EvidenceItem(
            entity_type="company",
            entity_id=company.id,
            source_url="https://northstar.test/news",
            evidence_snippet="Architectural graphics and cleanability-focused material systems.",
            extraction_method="structured_roster_parser",
        )
    )
    db_session.commit()

    draft = OutreachService(db_session).draft(stakeholder)
    assert draft is not None
    assert all("source_url" in item for item in draft.fact_trace)
    assert any(item["source_url"] == "https://northstar.test/news" for item in draft.fact_trace if item["source_url"])


def test_outreach_marks_low_confidence_when_fact_bundle_is_thin(db_session):
    company = Company(normalized_name="minimal signals", display_name="Minimal Signals")
    db_session.add(company)
    db_session.flush()

    stakeholder = Stakeholder(
        company_id=company.id,
        full_name="Dana Lee",
        title="VP Business Development",
        source_url="https://minimal.test/team",
        confidence_score=0.74,
        rationale="public evidence",
    )
    db_session.add(stakeholder)
    db_session.flush()

    db_session.add(
        EvidenceItem(
            entity_type="company",
            entity_id=company.id,
            source_url="https://minimal.test/about",
            evidence_snippet="Outdoor graphics materials.",
            extraction_method="public_about_page",
        )
    )
    db_session.commit()

    draft = OutreachService(db_session).draft(stakeholder)

    assert draft is not None
    assert draft.llm_model == "rule_based_fact_guard_v2_low_confidence"
    assert draft.linkedin_note == ""
    assert draft.outreach_three_sentence == ""
    assert any(item["fact"] == "outreach_low_confidence" for item in draft.fact_trace)

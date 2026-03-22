from app.models import Company, CompanyEventLink, CrawlStatus, EvidenceItem, ScoringRun, Source, SourceType, Stakeholder, Event
from app.services.scoring import ScoringService


def test_score_company_bounds_and_tier(db_session):
    company = Company(
        normalized_name="acme signs",
        display_name="Acme Signs",
        industry="Signage",
        description="Durable outdoor graphics and wraps",
        employee_count_range="200-500",
    )
    db_session.add(company)
    db_session.flush()

    src = Source(
        url="https://expo.test",
        domain="expo.test",
        source_type=SourceType.event,
        crawl_status=CrawlStatus.success,
        extraction_method="seed",
    )
    db_session.add(src)
    db_session.flush()
    evt = Event(
        name="Expo",
        event_type="trade_show",
        official_url="https://expo.test",
        relevance_summary="graphics",
        source_id=src.id,
    )
    db_session.add(evt)
    db_session.flush()
    db_session.add(
        CompanyEventLink(
            company_id=company.id,
            event_id=evt.id,
            association_id=None,
            source_context="Expo::https://expo.test/exhibitors",
            source_url="https://expo.test/exhibitors",
        )
    )
    db_session.add(
        EvidenceItem(
            entity_type="company",
            entity_id=company.id,
            source_url="https://expo.test/exhibitors",
            evidence_snippet="Durable exterior graphics and vehicle wrap solutions with UV/weather resistance.",
            extraction_method="structured_roster_parser",
        )
    )
    db_session.add(
        Stakeholder(
            company_id=company.id,
            full_name="Jane Roberts",
            title="Director of Product Development",
            source_url="https://acme.test/team",
            confidence_score=0.85,
            rationale="public evidence",
        )
    )
    db_session.commit()

    run = ScoringService(db_session).score_company(company)

    assert 0 <= run.total_score <= 100
    assert run.tier in {"A", "B", "C"}
    assert 0 <= run.confidence <= 1


def test_score_factor_integrity_and_explainability_shape(db_session):
    company = Company(
        normalized_name="northstar visual",
        display_name="Northstar Visual",
        industry="Visual communications",
        description="Architectural graphics and wallcovering systems.",
    )
    db_session.add(company)
    db_session.flush()
    db_session.add(
        EvidenceItem(
            entity_type="company",
            entity_id=company.id,
            source_url="https://example.test/member",
            evidence_snippet="Architectural wallcoverings and branded environment graphics.",
            extraction_method="structured_roster_parser",
        )
    )
    db_session.commit()

    run = ScoringService(db_session).score_company(company)

    expected_keys = {
        "industry_fit",
        "application_fit",
        "durability_adjacency",
        "ecosystem_participation",
        "scale_signal",
        "stakeholder_quality",
        "evidence_confidence",
        "weak_signal_penalty",
    }
    assert expected_keys.issubset(set(run.factors.keys()))

    for key in expected_keys:
        assert "score" in run.factors[key]
        assert "max" in run.factors[key]

    assert isinstance(run.explanation_bullets, list)
    assert len(run.explanation_bullets) >= 5


def test_disqualifier_logic_for_weak_signal_company(db_session):
    company = Company(normalized_name="misc corp", display_name="Misc Corp")
    db_session.add(company)
    db_session.commit()

    run = ScoringService(db_session).score_company(company)

    assert run.total_score <= 30
    assert any("No company-level evidence" in d for d in run.disqualifiers)
    assert any("No industry/application fit signal" in d for d in run.disqualifiers)


def test_scoring_run_persisted(db_session):
    company = Company(normalized_name="persist corp", display_name="Persist Corp", industry="signage")
    db_session.add(company)
    db_session.flush()
    db_session.add(
        EvidenceItem(
            entity_type="company",
            entity_id=company.id,
            source_url="https://persist.test",
            evidence_snippet="Signage and print systems.",
            extraction_method="structured_roster_parser",
        )
    )
    db_session.commit()

    ScoringService(db_session).score_company(company)
    count = db_session.query(ScoringRun).filter(ScoringRun.company_id == company.id).count()
    assert count == 1

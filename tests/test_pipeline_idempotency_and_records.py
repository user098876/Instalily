from app.api.routes import list_records
from app.models import Association, Company, CompanyEventLink, CrawlStatus, Event, EvidenceItem, Source, SourceType
from app.services.connectors import CrawlResult
from app.services.discovery import DiscoveryService
from app.services.extraction import ExtractionService


class FakeConnector:
    def fetch(self, url: str) -> CrawlResult:
        html = """
        <html>
            <body>
                signage graphics durable surfaces
                <ul>
                    <li>Acme Sign Systems</li>
                </ul>
            </body>
        </html>
        """
        return CrawlResult(status=CrawlStatus.success, url=url, html=html, reason=None, extraction_method="fake")


def test_discovery_rerun_no_duplicates_and_association_correct(db_session):
    svc = DiscoveryService(db_session)
    svc.connector = FakeConnector()

    svc.discover(["signage", "graphics"])
    svc.discover(["signage", "graphics"])

    events = db_session.query(Event).all()
    associations = db_session.query(Association).all()
    sources = db_session.query(Source).all()

    assert len(events) == 3
    assert len(associations) == 3
    assert len(sources) == 6
    assert all(ev.official_url != "https://pdaa.com/member-directory/" for ev in events)
    assert any(assoc.official_url == "https://pdaa.com/member-directory/" for assoc in associations)


def test_extraction_rerun_dedupes_company_and_links(db_session):
    source = Source(
        url="https://example-event.com",
        domain="example-event.com",
        source_type=SourceType.event,
        crawl_status=CrawlStatus.success,
        extraction_method="seed",
    )
    db_session.add(source)
    db_session.flush()
    event = Event(
        name="Example Event",
        event_type="trade_show",
        official_url="https://example-event.com",
        relevance_summary="signage",
        source_id=source.id,
    )
    db_session.add(event)
    db_session.commit()

    svc = ExtractionService(db_session)
    svc.connector = FakeConnector()

    svc.extract_companies()
    first_company_count = db_session.query(Company).count()
    first_link_count = db_session.query(CompanyEventLink).count()

    svc.extract_companies()
    second_company_count = db_session.query(Company).count()
    second_link_count = db_session.query(CompanyEventLink).count()

    assert first_company_count == second_company_count
    assert first_link_count == second_link_count


def test_records_returns_structured_evidence_and_association_display(db_session):
    company = Company(normalized_name="acme signs", display_name="Acme Signs")
    db_session.add(company)
    src = Source(
        url="https://assoc.org",
        domain="assoc.org",
        source_type=SourceType.association,
        crawl_status=CrawlStatus.success,
        extraction_method="seed",
    )
    db_session.add(src)
    db_session.flush()

    assoc = Association(
        name="Association Alpha",
        official_url="https://assoc.org",
        relevance_summary="graphics",
        source_id=src.id,
    )
    db_session.add(assoc)
    db_session.flush()

    db_session.add(
        CompanyEventLink(
            company_id=company.id,
            event_id=None,
            association_id=assoc.id,
            source_context="Association Alpha::https://assoc.org/members",
            source_url="https://assoc.org/members",
        )
    )
    db_session.add(
        EvidenceItem(
            entity_type="company",
            entity_id=company.id,
            source_url="https://assoc.org/members",
            evidence_snippet="Company extracted from public roster text: Acme Signs",
            extraction_method="html_roster_parser",
        )
    )
    db_session.add(
        EvidenceItem(
            entity_type="company",
            entity_id=company.id,
            source_url="not-a-valid-url",
            evidence_snippet="bad",
            extraction_method="x",
        )
    )
    db_session.commit()

    rows = list_records(db_session)
    assert len(rows) == 1
    row = rows[0]

    assert row.event_or_association == "Association Alpha"
    assert len(row.evidence_links) >= 1
    assert all(str(e.url).startswith("http") for e in row.evidence_links)
    assert all(hasattr(e, "label") and hasattr(e, "source_type") for e in row.evidence_links)
    assert row.evidence_links[0].extraction_method is not None
    assert row.company_id == company.id
    assert row.score_tier is None
    assert row.company_website_status == "missing_unvalidated"
    assert row.outreach_status == "missing"


def test_export_csv_escapes_values(db_session):
    from app.api.routes import export_csv

    company = Company(normalized_name="acme signs inc", display_name='Acme "Signs", Inc.')
    db_session.add(company)
    db_session.commit()

    response = export_csv(db_session)
    body = response.body.decode("utf-8")

    assert body.startswith(
        "event_or_association,company,company_website,qualification_score,stakeholder,title,outreach_status,status"
    )
    assert '"Acme ""Signs"", Inc."' in body


def test_review_status_update_refreshes_timestamp(db_session):
    from app.api.routes import set_review_status
    from app.models import ReviewStatus
    from app.schemas import ReviewUpdateIn

    company = Company(normalized_name="stamp corp", display_name="Stamp Corp")
    db_session.add(company)
    db_session.flush()

    set_review_status("company", company.id, ReviewUpdateIn(status="pending", notes="first"), db_session)
    first = (
        db_session.query(ReviewStatus)
        .filter(ReviewStatus.entity_type == "company", ReviewStatus.entity_id == company.id)
        .one()
    )
    first_updated = first.updated_at

    set_review_status("company", company.id, ReviewUpdateIn(status="approved", notes="second"), db_session)
    second = (
        db_session.query(ReviewStatus)
        .filter(ReviewStatus.entity_type == "company", ReviewStatus.entity_id == company.id)
        .one()
    )

    assert second.updated_at >= first_updated
    assert second.status.value == "approved"

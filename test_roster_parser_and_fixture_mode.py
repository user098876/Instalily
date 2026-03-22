import json
from pathlib import Path

from app.models import Company, CrawlStatus, Event, EvidenceItem, Source, SourceType
from app.services.connectors import CrawlResult, FixtureWebConnector
from app.services.extraction import ExtractionService
from app.services.roster_parser import discover_likely_roster_links, extract_company_candidates


def _load_fixture(name: str) -> str:
    return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")


def test_structured_parser_extracts_companies_and_websites():
    html = _load_fixture("roster_structured.html")
    candidates = extract_company_candidates(html, "https://event.example/exhibitors")
    names = {c.name for c in candidates}

    assert "Acme Signs" in names
    assert "Northstar Visual" in names
    assert "Matrix Print Systems" in names
    assert "FilmShield Materials" in names
    assert "Vector Surface Coatings" in names

    acme = next(c for c in candidates if c.name == "Acme Signs")
    assert acme.website == "https://www.acmesigns.com"


def test_parser_suppresses_false_positives():
    html = _load_fixture("roster_structured.html")
    names = {c.name.lower() for c in extract_company_candidates(html, "https://event.example/exhibitors")}

    assert "register" not in names
    assert "learn more" not in names
    assert "booth 1042" not in names


def test_link_discovery_prioritizes_internal_roster_pages():
    html = _load_fixture("root_with_roster_links.html")
    links = discover_likely_roster_links(html, "https://event.example", max_links=5)

    assert "https://event.example/exhibitors" in links
    assert "https://event.example/sponsors" in links
    assert all("external-site.com" not in url for url in links)


class MappingConnector:
    def __init__(self, mapping: dict[str, str]):
        self.mapping = mapping

    def fetch(self, url: str) -> CrawlResult:
        if url not in self.mapping:
            return CrawlResult(
                status=CrawlStatus.no_relevant_data,
                url=url,
                html=None,
                reason="missing",
                extraction_method="mapping",
            )
        return CrawlResult(
            status=CrawlStatus.success,
            url=url,
            html=self.mapping[url],
            reason=None,
            extraction_method="mapping",
        )


def test_extraction_captures_website_from_public_evidence(db_session):
    src = Source(
        url="https://event.example",
        domain="event.example",
        source_type=SourceType.event,
        crawl_status=CrawlStatus.success,
        extraction_method="seed",
    )
    db_session.add(src)
    db_session.flush()
    db_session.add(
        Event(
            name="Example Expo",
            event_type="expo",
            official_url="https://event.example",
            relevance_summary="graphics",
            source_id=src.id,
        )
    )
    db_session.commit()

    svc = ExtractionService(db_session)
    svc.connector = MappingConnector(
        {
            "https://event.example": _load_fixture("root_with_roster_links.html"),
            "https://event.example/exhibitors": _load_fixture("exhibitors_page.html"),
        }
    )

    summary = svc.extract_companies()
    assert summary["inserted_companies"] >= 1

    company = db_session.query(Company).filter(Company.normalized_name == "truecolor wraps").one_or_none()
    assert company is not None
    assert company.website == "https://www.truecolorwraps.com"

    website_evidence = (
        db_session.query(EvidenceItem)
        .filter(
            EvidenceItem.entity_type == "company",
            EvidenceItem.entity_id == company.id,
            EvidenceItem.extraction_method == "website_from_public_roster",
        )
        .all()
    )
    assert website_evidence


def test_extraction_dedupes_repeated_company_from_same_source(db_session):
    src = Source(
        url="https://event.example",
        domain="event.example",
        source_type=SourceType.event,
        crawl_status=CrawlStatus.success,
        extraction_method="seed",
    )
    db_session.add(src)
    db_session.flush()
    db_session.add(
        Event(
            name="Example Expo",
            event_type="expo",
            official_url="https://event.example",
            relevance_summary="graphics",
            source_id=src.id,
        )
    )
    db_session.commit()

    svc = ExtractionService(db_session)
    svc.connector = MappingConnector(
        {
            "https://event.example": _load_fixture("root_with_roster_links.html"),
            "https://event.example/exhibitors": _load_fixture("exhibitors_page.html"),
        }
    )

    svc.extract_companies()
    first_count = db_session.query(Company).count()
    svc.extract_companies()
    second_count = db_session.query(Company).count()

    assert first_count == second_count


def test_fixture_connector_mode_reads_manifest(tmp_path):
    fixture = tmp_path / "page.html"
    fixture.write_text("<html><body>fixture</body></html>", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "https://fixture.example": {
                    "status": "success",
                    "fixture_file": "page.html",
                    "reason": "captured_test",
                }
            }
        ),
        encoding="utf-8",
    )

    connector = FixtureWebConnector(str(manifest))
    good = connector.fetch("https://fixture.example")
    missing = connector.fetch("https://fixture-missing.example")

    assert good.status == CrawlStatus.success
    assert "fixture" in (good.html or "")
    assert missing.status == CrawlStatus.no_relevant_data
    assert missing.reason == "fixture_missing"


def test_fixture_connector_mode_handles_invalid_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{invalid json", encoding="utf-8")

    connector = FixtureWebConnector(str(manifest))
    result = connector.fetch("https://fixture.example")

    assert result.status == CrawlStatus.no_relevant_data
    assert result.reason == "fixture_missing"

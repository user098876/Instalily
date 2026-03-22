from pathlib import Path

from app.models import Company, CrawlStatus, EvidenceItem, Source, SourceType, Stakeholder
from app.services.connectors import CrawlResult
from app.services.stakeholder_parser import (
    compute_confidence,
    discover_people_links,
    extract_person_title_candidates,
    title_relevance_score,
)
from app.services.stakeholder_providers import (
    ApolloPeopleProvider,
    ClayPeopleProvider,
    LinkedInSalesNavProvider,
    PDLPeopleProvider,
)
from app.services.stakeholders import StakeholderService


def _load_fixture(name: str) -> str:
    return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")


class MappingConnector:
    def __init__(self, mapping: dict[str, str]):
        self.mapping = mapping

    def fetch(self, url: str) -> CrawlResult:
        html = self.mapping.get(url)
        if html is None:
            return CrawlResult(
                status=CrawlStatus.no_relevant_data,
                url=url,
                html=None,
                reason="missing_fixture",
                extraction_method="mapping",
            )
        return CrawlResult(
            status=CrawlStatus.success,
            url=url,
            html=html,
            reason=None,
            extraction_method="mapping",
        )


def test_person_title_extraction_from_structured_html():
    html = _load_fixture("stakeholders_team_page.html")
    candidates = extract_person_title_candidates(html, "https://company.example/team")

    pairs = {(c.full_name, c.title) for c in candidates}
    assert ("Jane Roberts", "Director of Product Development, Graphics Materials") in pairs
    assert ("Michael Chen", "VP, Innovation and R&D") in pairs
    assert all("contact" not in c.full_name.lower() for c in candidates)


def test_role_pattern_targeting_and_confidence_logic():
    assert title_relevance_score("Director of Product Development, Graphics Materials") > 0
    assert title_relevance_score("Warehouse Associate") == 0

    high = compute_confidence(
        source_url="https://company.example/leadership",
        title="VP, Innovation and R&D",
        extraction_certainty=0.9,
    )
    low = compute_confidence(
        source_url="https://company.example/contact",
        title="Marketing Coordinator",
        extraction_certainty=0.5,
    )
    assert high.score > low.score


def test_people_link_discovery_is_constrained_and_relevant():
    html = _load_fixture("stakeholders_homepage.html")
    links = discover_people_links(html, "https://company.example", max_links=3)
    assert len(links) <= 3
    assert "https://company.example/team" in links or "https://company.example/leadership" in links


def test_stakeholder_service_dedupes_on_rerun(db_session):
    source = Source(
        url="https://company.example",
        domain="company.example",
        source_type=SourceType.directory,
        crawl_status=CrawlStatus.success,
        extraction_method="seed",
    )
    db_session.add(source)
    db_session.flush()

    company = Company(
        normalized_name="company example",
        display_name="Company Example",
        website="https://company.example",
    )
    db_session.add(company)
    db_session.commit()

    svc = StakeholderService(db_session)
    svc.connector = MappingConnector(
        {
            "https://company.example": _load_fixture("stakeholders_homepage.html"),
            "https://company.example/team": _load_fixture("stakeholders_team_page.html"),
            "https://company.example/leadership": _load_fixture("stakeholders_team_page.html"),
            "https://company.example/news": _load_fixture("stakeholders_news_page.html"),
        }
    )

    created1 = svc.discover_for_company(company)
    count1 = db_session.query(Stakeholder).count()

    created2 = svc.discover_for_company(company)
    count2 = db_session.query(Stakeholder).count()

    assert created1 >= 1
    assert created2 == 0
    assert count1 == count2

    evidence = db_session.query(EvidenceItem).filter(EvidenceItem.entity_type == "stakeholder").all()
    assert evidence


def test_optional_provider_adapters_graceful_unavailable():
    linkedin = LinkedInSalesNavProvider(enabled=False).discover(
        Company(normalized_name="x", display_name="X")
    )
    clay = ClayPeopleProvider(api_key=None).discover(Company(normalized_name="x", display_name="X"))
    apollo = ApolloPeopleProvider(api_key=None).discover(Company(normalized_name="x", display_name="X"))
    pdl = PDLPeopleProvider(api_key=None).discover(Company(normalized_name="x", display_name="X"))

    assert linkedin.status == CrawlStatus.provider_unavailable
    assert clay.status == CrawlStatus.provider_unavailable
    assert apollo.status == CrawlStatus.provider_unavailable
    assert pdl.status == CrawlStatus.provider_unavailable
    assert linkedin.candidates == []
    assert clay.candidates == []

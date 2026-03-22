from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import Association, AccountConfig, CrawlStatus, Event, EvidenceItem, Source, SourceType
from app.services.connectors import build_web_connector, extract_text_snippets


@dataclass
class DiscoverySeed:
    name: str
    source_type: SourceType
    url: str
    event_type: str


DEFAULT_DISCOVERY_SEEDS = [
    DiscoverySeed("ISA Sign Expo", SourceType.event, "https://signexpo.org/", "trade_show"),
    DiscoverySeed(
        "PRINTING United Expo",
        SourceType.event,
        "https://www.printingunited.com/",
        "expo",
    ),
    DiscoverySeed("FESPA Global", SourceType.event, "https://www.fespaglobalprintexpo.com/", "expo"),
    DiscoverySeed("PDAA", SourceType.association, "https://pdaa.com/member-directory/", "association"),
    DiscoverySeed("SEGD", SourceType.association, "https://segd.org/", "association"),
    DiscoverySeed("ISA", SourceType.association, "https://www.signs.org/", "association"),
]


DISCOVERY_KEYWORDS = [
    "graphics",
    "signage",
    "sign",
    "vehicle wrap",
    "architectural graphics",
    "wallcoverings",
    "protective films",
    "durable",
    "uv",
    "weather",
    "graffiti",
    "surface",
]


class DiscoveryService:
    def __init__(self, db: Session):
        self.db = db
        self.connector = build_web_connector()

    def seed_account_config(self, account_name: str, target_segment: str, icp_themes: list[str]) -> AccountConfig:
        existing = (
            self.db.query(AccountConfig)
            .filter(AccountConfig.account_name == account_name, AccountConfig.target_segment == target_segment)
            .one_or_none()
        )
        if existing:
            existing.icp_themes = icp_themes
            self.db.commit()
            self.db.refresh(existing)
            return existing
        row = AccountConfig(account_name=account_name, target_segment=target_segment, icp_themes=icp_themes)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def _upsert_source(
        self,
        url: str,
        source_type: SourceType,
        crawl_status: CrawlStatus,
        reason: str | None,
        extraction_method: str,
    ) -> Source:
        existing = self.db.query(Source).filter(Source.url == url).one_or_none()
        parsed = urlparse(url)
        if existing:
            existing.domain = parsed.netloc
            existing.source_type = source_type
            existing.crawl_status = crawl_status
            existing.status_reason = reason
            existing.extraction_method = extraction_method
            self.db.flush()
            return existing
        src = Source(
            url=url,
            domain=parsed.netloc,
            source_type=source_type,
            crawl_status=crawl_status,
            status_reason=reason,
            extraction_method=extraction_method,
        )
        self.db.add(src)
        self.db.flush()
        return src

    def _upsert_event(self, seed: DiscoverySeed, source_id: int, relevance_summary: str) -> Event:
        existing = self.db.query(Event).filter(Event.official_url == seed.url).one_or_none()
        if existing:
            existing.name = seed.name
            existing.event_type = seed.event_type
            existing.relevance_summary = relevance_summary
            existing.source_id = source_id
            self.db.flush()
            return existing
        row = Event(
            name=seed.name,
            event_type=seed.event_type,
            event_date=None,
            location=None,
            official_url=seed.url,
            relevance_summary=relevance_summary,
            source_id=source_id,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def _upsert_association(self, seed: DiscoverySeed, source_id: int, relevance_summary: str) -> Association:
        existing = self.db.query(Association).filter(Association.official_url == seed.url).one_or_none()
        if existing:
            existing.name = seed.name
            existing.relevance_summary = relevance_summary
            existing.source_id = source_id
            self.db.flush()
            return existing
        row = Association(
            name=seed.name,
            official_url=seed.url,
            relevance_summary=relevance_summary,
            source_id=source_id,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def _upsert_evidence(
        self,
        entity_type: str,
        entity_id: int,
        source_url: str,
        evidence_snippet: str,
        extraction_method: str,
    ) -> None:
        existing = (
            self.db.query(EvidenceItem)
            .filter(
                EvidenceItem.entity_type == entity_type,
                EvidenceItem.entity_id == entity_id,
                EvidenceItem.source_url == source_url,
                EvidenceItem.evidence_snippet == evidence_snippet,
            )
            .one_or_none()
        )
        if existing:
            return
        self.db.add(
            EvidenceItem(
                entity_type=entity_type,
                entity_id=entity_id,
                source_url=source_url,
                evidence_snippet=evidence_snippet,
                extraction_method=extraction_method,
            )
        )

    def discover(self, icp_themes: list[str]) -> list[Source]:
        out: list[Source] = []
        keywords = list(dict.fromkeys([*(icp_themes or []), *DISCOVERY_KEYWORDS]))
        for seed in DEFAULT_DISCOVERY_SEEDS:
            result = self.connector.fetch(seed.url)
            src = self._upsert_source(
                url=seed.url,
                source_type=seed.source_type,
                crawl_status=result.status,
                reason=result.reason,
                extraction_method=result.extraction_method,
            )

            snippets: list[str] = []
            relevance_summary = "No explicit snippet found"
            if result.status == CrawlStatus.success and result.html:
                snippets = extract_text_snippets(result.html, keywords)
                if snippets:
                    relevance_summary = snippets[0]

            if seed.source_type == SourceType.association:
                parent = self._upsert_association(seed=seed, source_id=src.id, relevance_summary=relevance_summary)
                entity_type = "association"
            else:
                parent = self._upsert_event(seed=seed, source_id=src.id, relevance_summary=relevance_summary)
                entity_type = "event"

            for snip in snippets[:3]:
                self._upsert_evidence(
                    entity_type=entity_type,
                    entity_id=parent.id,
                    source_url=seed.url,
                    evidence_snippet=snip,
                    extraction_method="keyword_window",
                )
            out.append(src)
        self.db.commit()
        return out

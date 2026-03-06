import re
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Association,
    Company,
    CompanyEventLink,
    CrawlStatus,
    Event,
    EvidenceItem,
    Source,
    SourceType,
)
from app.services.connectors import build_web_connector
from app.services.roster_parser import CompanyCandidate, discover_likely_roster_links, extract_company_candidates


class ExtractionService:
    def __init__(self, db: Session):
        self.db = db
        self.connector = build_web_connector()
        self.settings = get_settings()

    @staticmethod
    def normalize_company_name(name: str) -> str:
        s = re.sub(r"[^a-zA-Z0-9 ]+", "", name).strip().lower()
        return re.sub(r"\s+", " ", s)

    def _upsert_source(
        self,
        url: str,
        crawl_status: CrawlStatus,
        status_reason: str | None,
        extraction_method: str,
    ) -> Source:
        source = self.db.query(Source).filter(Source.url == url).one_or_none()
        if source:
            source.domain = urlparse(url).netloc
            source.source_type = SourceType.directory
            source.crawl_status = crawl_status
            source.status_reason = status_reason
            source.extraction_method = extraction_method
            self.db.flush()
            return source
        source = Source(
            url=url,
            domain=urlparse(url).netloc,
            source_type=SourceType.directory,
            crawl_status=crawl_status,
            status_reason=status_reason,
            extraction_method=extraction_method,
        )
        self.db.add(source)
        self.db.flush()
        return source

    def _upsert_company(self, name: str, website: str | None = None) -> tuple[Company, bool]:
        norm = self.normalize_company_name(name)
        company = self.db.query(Company).filter(Company.normalized_name == norm).one_or_none()
        if company:
            # only update when website is evidence-backed and existing is empty
            if website and not company.website:
                company.website = website
            return company, False
        company = Company(normalized_name=norm, display_name=name, website=website)
        self.db.add(company)
        self.db.flush()
        return company, True

    def _upsert_link(
        self,
        company_id: int,
        source_context: str,
        source_url: str,
        event_id: int | None = None,
        association_id: int | None = None,
    ) -> bool:
        existing = (
            self.db.query(CompanyEventLink)
            .filter(
                CompanyEventLink.company_id == company_id,
                CompanyEventLink.event_id == event_id,
                CompanyEventLink.association_id == association_id,
                CompanyEventLink.source_url == source_url,
            )
            .one_or_none()
        )
        if existing:
            existing.source_context = source_context
            return False
        self.db.add(
            CompanyEventLink(
                company_id=company_id,
                event_id=event_id,
                association_id=association_id,
                source_context=source_context,
                source_url=source_url,
            )
        )
        return True

    def _upsert_company_evidence(self, company_id: int, source_url: str, snippet: str, method: str) -> None:
        existing = (
            self.db.query(EvidenceItem)
            .filter(
                EvidenceItem.entity_type == "company",
                EvidenceItem.entity_id == company_id,
                EvidenceItem.source_url == source_url,
                EvidenceItem.evidence_snippet == snippet,
            )
            .one_or_none()
        )
        if existing:
            return
        self.db.add(
            EvidenceItem(
                entity_type="company",
                entity_id=company_id,
                source_url=source_url,
                evidence_snippet=snippet,
                extraction_method=method,
            )
        )

    def _candidate_roster_urls(self, parent_url: str) -> list[str]:
        seed_result = self.connector.fetch(parent_url)
        self._upsert_source(
            url=parent_url,
            crawl_status=seed_result.status,
            status_reason=seed_result.reason,
            extraction_method=seed_result.extraction_method,
        )

        urls: list[str] = [parent_url]
        if seed_result.status == CrawlStatus.success and seed_result.html:
            discovered = discover_likely_roster_links(
                seed_result.html,
                parent_url,
                max_links=self.settings.max_roster_links_per_parent,
            )
            for u in discovered:
                if u not in urls:
                    urls.append(u)

        # fallback URLs, kept constrained
        for suffix in ["exhibitors", "sponsors", "members", "directory"]:
            candidate = parent_url.rstrip("/") + f"/{suffix}"
            if candidate not in urls and len(urls) < self.settings.max_roster_links_per_parent + 1:
                urls.append(candidate)
        return urls

    def _process_candidates(
        self,
        parent_name: str,
        source_url: str,
        candidates: list[CompanyCandidate],
        summary: dict[str, int],
        event_id: int | None = None,
        association_id: int | None = None,
    ) -> None:
        for cand in candidates:
            company, created_company = self._upsert_company(cand.name, cand.website)
            if created_company:
                summary["inserted_companies"] += 1

            created_link = self._upsert_link(
                company_id=company.id,
                event_id=event_id,
                association_id=association_id,
                source_context=f"{parent_name}::{source_url}",
                source_url=source_url,
            )
            if created_link:
                summary["linked_records"] += 1

            self._upsert_company_evidence(
                company_id=company.id,
                source_url=source_url,
                snippet=f"[{cand.signal}] {cand.snippet}",
                method="structured_roster_parser",
            )

            if cand.website:
                self._upsert_company_evidence(
                    company_id=company.id,
                    source_url=source_url,
                    snippet=f"Website observed on public roster: {cand.website}",
                    method="website_from_public_roster",
                )

    def _extract_for_parent(
        self,
        parent_name: str,
        parent_url: str,
        event_id: int | None = None,
        association_id: int | None = None,
    ) -> dict[str, int]:
        summary = {"inserted_companies": 0, "linked_records": 0}

        for url in self._candidate_roster_urls(parent_url):
            result = self.connector.fetch(url)
            self._upsert_source(
                url=url,
                crawl_status=result.status,
                status_reason=result.reason,
                extraction_method=result.extraction_method,
            )
            if result.status != CrawlStatus.success or not result.html:
                continue

            candidates = extract_company_candidates(result.html, url)
            if not candidates:
                continue
            self._process_candidates(
                parent_name=parent_name,
                source_url=url,
                candidates=candidates,
                summary=summary,
                event_id=event_id,
                association_id=association_id,
            )

        return summary

    def extract_companies(self) -> dict:
        summary = {"inserted_companies": 0, "linked_records": 0}

        for event in self.db.query(Event).all():
            evt_summary = self._extract_for_parent(
                parent_name=event.name,
                parent_url=event.official_url,
                event_id=event.id,
            )
            summary["inserted_companies"] += evt_summary["inserted_companies"]
            summary["linked_records"] += evt_summary["linked_records"]

        for association in self.db.query(Association).all():
            assoc_summary = self._extract_for_parent(
                parent_name=association.name,
                parent_url=association.official_url,
                association_id=association.id,
            )
            summary["inserted_companies"] += assoc_summary["inserted_companies"]
            summary["linked_records"] += assoc_summary["linked_records"]

        self.db.commit()
        return summary

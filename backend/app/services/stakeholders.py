from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Company, CrawlStatus, EvidenceItem, ProviderLog, Source, SourceType, Stakeholder
from app.services.connectors import build_web_connector
from app.services.stakeholder_parser import (
    compute_confidence,
    discover_people_links,
    extract_person_title_candidates,
    title_relevance_score,
)
from app.services.stakeholder_providers import build_stakeholder_providers


FALLBACK_PEOPLE_PATHS = ["/about", "/team", "/leadership", "/company", "/news", "/press", "/contact"]


class StakeholderService:
    def __init__(self, db: Session):
        self.db = db
        self.connector = build_web_connector()
        self.providers = build_stakeholder_providers()
        self.settings = get_settings()

    def _upsert_source(self, url: str, status: CrawlStatus, reason: str | None, method: str) -> None:
        src = self.db.query(Source).filter(Source.url == url).one_or_none()
        if src:
            src.domain = urlparse(url).netloc
            src.source_type = SourceType.directory
            src.crawl_status = status
            src.status_reason = reason
            src.extraction_method = method
            return
        self.db.add(
            Source(
                url=url,
                domain=urlparse(url).netloc,
                source_type=SourceType.directory,
                crawl_status=status,
                status_reason=reason,
                extraction_method=method,
            )
        )

    def _upsert_stakeholder(
        self,
        company_id: int,
        full_name: str,
        title: str,
        source_url: str,
        confidence_score: float,
        rationale: str,
        profile_url: str | None = None,
    ) -> tuple[Stakeholder, bool]:
        exact = (
            self.db.query(Stakeholder)
            .filter(
                Stakeholder.company_id == company_id,
                Stakeholder.full_name == full_name,
                Stakeholder.title == title,
                Stakeholder.source_url == source_url,
            )
            .one_or_none()
        )
        if exact:
            exact.confidence_score = max(exact.confidence_score, confidence_score)
            if profile_url and not exact.profile_url:
                exact.profile_url = profile_url
            exact.rationale = rationale
            return exact, False

        # Cross-page dedupe for same person/title in a company.
        same_person = (
            self.db.query(Stakeholder)
            .filter(
                Stakeholder.company_id == company_id,
                Stakeholder.full_name == full_name,
                Stakeholder.title == title,
            )
            .order_by(Stakeholder.confidence_score.desc())
            .first()
        )
        if same_person:
            if confidence_score > same_person.confidence_score:
                same_person.confidence_score = confidence_score
                same_person.source_url = source_url
                same_person.rationale = rationale
            if profile_url and not same_person.profile_url:
                same_person.profile_url = profile_url
            return same_person, False

        row = Stakeholder(
            company_id=company_id,
            full_name=full_name,
            title=title,
            profile_url=profile_url,
            source_url=source_url,
            confidence_score=confidence_score,
            rationale=rationale,
        )
        self.db.add(row)
        self.db.flush()
        return row, True

    def _upsert_evidence(self, stakeholder_id: int, source_url: str, snippet: str, method: str) -> None:
        existing = (
            self.db.query(EvidenceItem)
            .filter(
                EvidenceItem.entity_type == "stakeholder",
                EvidenceItem.entity_id == stakeholder_id,
                EvidenceItem.source_url == source_url,
                EvidenceItem.evidence_snippet == snippet,
            )
            .one_or_none()
        )
        if existing:
            return
        self.db.add(
            EvidenceItem(
                entity_type="stakeholder",
                entity_id=stakeholder_id,
                source_url=source_url,
                evidence_snippet=snippet,
                extraction_method=method,
            )
        )

    def _candidate_people_urls(self, company_website: str) -> list[str]:
        root = company_website.rstrip("/")
        urls = [root]

        root_result = self.connector.fetch(root)
        self._upsert_source(root, root_result.status, root_result.reason, root_result.extraction_method)

        if root_result.status == CrawlStatus.success and root_result.html:
            links = discover_people_links(
                root_result.html,
                root,
                max_links=self.settings.max_stakeholder_pages,
            )
            for link in links:
                if link not in urls:
                    urls.append(link)

        for suffix in FALLBACK_PEOPLE_PATHS:
            candidate = root + suffix
            if candidate not in urls and len(urls) < (self.settings.max_stakeholder_pages + 1):
                urls.append(candidate)

        return urls

    def _discover_from_public_pages(self, company: Company) -> int:
        if not company.website:
            return 0

        created = 0
        for people_url in self._candidate_people_urls(company.website):
            result = self.connector.fetch(people_url)
            self._upsert_source(people_url, result.status, result.reason, result.extraction_method)
            if result.status != CrawlStatus.success or not result.html:
                continue

            candidates = extract_person_title_candidates(result.html, people_url)
            for cand in candidates:
                if title_relevance_score(cand.title) <= 0:
                    continue

                breakdown = compute_confidence(people_url, cand.title, cand.extraction_certainty)
                rationale = (
                    f"public_page={people_url}; source_quality={breakdown.source_quality:.2f}; "
                    f"title_relevance={breakdown.title_relevance:.2f}; extraction_certainty={breakdown.extraction_certainty:.2f}"
                )
                row, was_created = self._upsert_stakeholder(
                    company_id=company.id,
                    full_name=cand.full_name,
                    title=cand.title,
                    source_url=cand.source_url,
                    confidence_score=breakdown.score,
                    rationale=rationale,
                )
                self._upsert_evidence(
                    stakeholder_id=row.id,
                    source_url=cand.source_url,
                    snippet=f"{cand.full_name} | {cand.title} | {cand.snippet}",
                    method=cand.extraction_method,
                )
                if was_created:
                    created += 1
        return created

    def _discover_from_optional_providers(self, company: Company) -> int:
        created = 0
        for provider in self.providers:
            result = provider.discover(company)
            self.db.add(
                ProviderLog(
                    provider=result.provider,
                    endpoint="stakeholder_discovery",
                    status=result.status,
                    message=result.message,
                    latency_ms=0,
                )
            )

            if result.status != CrawlStatus.success:
                continue

            for cand in result.candidates:
                if title_relevance_score(cand.title) <= 0:
                    continue
                breakdown = compute_confidence(cand.source_url, cand.title, 0.7)
                rationale = (
                    f"provider={result.provider}; source_quality={breakdown.source_quality:.2f}; "
                    f"title_relevance={breakdown.title_relevance:.2f}; extraction_certainty=0.70"
                )
                row, was_created = self._upsert_stakeholder(
                    company_id=company.id,
                    full_name=cand.full_name,
                    title=cand.title,
                    source_url=cand.source_url,
                    confidence_score=breakdown.score,
                    rationale=rationale,
                    profile_url=cand.profile_url,
                )
                self._upsert_evidence(
                    stakeholder_id=row.id,
                    source_url=cand.source_url,
                    snippet=(cand.snippet or f"{cand.full_name} | {cand.title}"),
                    method=f"provider_{result.provider}",
                )
                if was_created:
                    created += 1
        return created

    def discover_for_company(self, company: Company) -> int:
        created = 0
        created += self._discover_from_public_pages(company)
        created += self._discover_from_optional_providers(company)
        self.db.commit()
        return created

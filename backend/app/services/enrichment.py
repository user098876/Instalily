from dataclasses import dataclass
from time import perf_counter

import requests
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Company, CrawlStatus, Enrichment, ProviderLog


@dataclass
class ProviderResult:
    provider: str
    status: CrawlStatus
    payload: dict | None
    message: str | None


class BaseProvider:
    provider_name = "base"

    def __init__(self, api_key: str | None):
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key)

    def enrich(self, company: Company) -> ProviderResult:
        raise NotImplementedError


class CompanyWebsiteProvider(BaseProvider):
    provider_name = "company_website"

    def enrich(self, company: Company) -> ProviderResult:
        if not company.website:
            return ProviderResult(self.provider_name, CrawlStatus.no_relevant_data, None, "website_missing")
        try:
            resp = requests.get(company.website, timeout=15)
            if resp.status_code >= 400:
                return ProviderResult(self.provider_name, CrawlStatus.blocked, None, f"http_{resp.status_code}")
            text = resp.text[:5000]
            return ProviderResult(
                self.provider_name,
                CrawlStatus.success,
                {"description_excerpt": text[:300], "signals": ["website_reachable"]},
                None,
            )
        except requests.RequestException as exc:
            return ProviderResult(self.provider_name, CrawlStatus.parser_failed, None, str(exc))


class GenericAPIProvider(BaseProvider):
    endpoint = ""
    provider_name = "generic"

    def enrich(self, company: Company) -> ProviderResult:
        if not self.available():
            return ProviderResult(self.provider_name, CrawlStatus.provider_unavailable, None, "missing_api_key")
        if not self.endpoint:
            return ProviderResult(self.provider_name, CrawlStatus.parser_failed, None, "endpoint_not_configured")
        try:
            resp = requests.get(
                self.endpoint,
                params={"company": company.display_name},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            if resp.status_code == 429:
                return ProviderResult(self.provider_name, CrawlStatus.rate_limited, None, "http_429")
            if resp.status_code >= 400:
                return ProviderResult(self.provider_name, CrawlStatus.blocked, None, f"http_{resp.status_code}")
            return ProviderResult(self.provider_name, CrawlStatus.success, resp.json(), None)
        except requests.RequestException as exc:
            return ProviderResult(self.provider_name, CrawlStatus.parser_failed, None, str(exc))


class ClearbitProvider(GenericAPIProvider):
    provider_name = "clearbit"
    endpoint = "https://company.clearbit.com/v2/companies/find"


class ApolloProvider(GenericAPIProvider):
    provider_name = "apollo"
    endpoint = "https://api.apollo.io/api/v1/organizations/search"


class ClayProvider(GenericAPIProvider):
    provider_name = "clay"
    endpoint = "https://api.clay.com/v1/enrich/company"


class PDLProvider(GenericAPIProvider):
    provider_name = "peopledatalabs"
    endpoint = "https://api.peopledatalabs.com/v5/company/enrich"


class EnrichmentService:
    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.providers = [
            CompanyWebsiteProvider(api_key="internal"),
            ClearbitProvider(settings.clearbit_api_key),
            ApolloProvider(settings.apollo_api_key),
            ClayProvider(settings.clay_api_key),
            PDLProvider(settings.peopledatalabs_api_key),
        ]

    @staticmethod
    def _clean_scalar(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def enrich_company(self, company: Company) -> list[ProviderResult]:
        results: list[ProviderResult] = []
        for provider in self.providers:
            start = perf_counter()
            result = provider.enrich(company)
            latency_ms = int((perf_counter() - start) * 1000)
            self.db.add(
                ProviderLog(
                    provider=provider.provider_name,
                    endpoint=getattr(provider, "endpoint", None),
                    status=result.status,
                    message=result.message,
                    latency_ms=latency_ms,
                )
            )
            self.db.add(
                Enrichment(
                    company_id=company.id,
                    provider=provider.provider_name,
                    status=result.status,
                    raw_payload=result.payload,
                )
            )
            if result.status == CrawlStatus.success and result.payload:
                company.description = company.description or self._clean_scalar(
                    result.payload.get("description") or result.payload.get("description_excerpt")
                )
                company.industry = company.industry or self._clean_scalar(result.payload.get("industry"))
                company.employee_count_range = company.employee_count_range or self._clean_scalar(
                    result.payload.get("employees") or result.payload.get("employee_count")
                )
                company.revenue_estimate = company.revenue_estimate or self._clean_scalar(
                    result.payload.get("annual_revenue")
                )
            results.append(result)
        self.db.commit()
        return results

from dataclasses import dataclass

from app.config import get_settings
from app.models import Company, CrawlStatus


@dataclass
class ProviderPersonCandidate:
    full_name: str
    title: str
    source_url: str
    profile_url: str | None = None
    snippet: str | None = None


@dataclass
class ProviderDiscoveryResult:
    provider: str
    status: CrawlStatus
    candidates: list[ProviderPersonCandidate]
    message: str | None = None


class StakeholderProvider:
    provider_name = "base"

    def discover(self, company: Company) -> ProviderDiscoveryResult:
        raise NotImplementedError


class LinkedInSalesNavProvider(StakeholderProvider):
    provider_name = "linkedin_sales_nav"

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def discover(self, company: Company) -> ProviderDiscoveryResult:
        if not self.enabled:
            return ProviderDiscoveryResult(
                provider=self.provider_name,
                status=CrawlStatus.provider_unavailable,
                candidates=[],
                message="feature_flag_disabled_or_not_configured",
            )

        return ProviderDiscoveryResult(
            provider=self.provider_name,
            status=CrawlStatus.no_relevant_data,
            candidates=[],
            message="adapter_contract_only_no_partner_access",
        )


class APIPeopleProvider(StakeholderProvider):
    provider_name = "api_people"

    def __init__(self, api_key: str | None):
        self.api_key = api_key

    def discover(self, company: Company) -> ProviderDiscoveryResult:
        if not self.api_key:
            return ProviderDiscoveryResult(
                provider=self.provider_name,
                status=CrawlStatus.provider_unavailable,
                candidates=[],
                message="missing_api_key",
            )

        # Contract in place; concrete call path can be implemented per provider policy.
        return ProviderDiscoveryResult(
            provider=self.provider_name,
            status=CrawlStatus.no_relevant_data,
            candidates=[],
            message="adapter_contract_only_no_live_call_in_this_pass",
        )


class ClayPeopleProvider(APIPeopleProvider):
    provider_name = "clay_people"


class ApolloPeopleProvider(APIPeopleProvider):
    provider_name = "apollo_people"


class PDLPeopleProvider(APIPeopleProvider):
    provider_name = "peopledatalabs_people"


def build_stakeholder_providers() -> list[StakeholderProvider]:
    settings = get_settings()
    return [
        LinkedInSalesNavProvider(enabled=settings.enable_linkedin_sales_nav),
        ClayPeopleProvider(settings.clay_api_key),
        ApolloPeopleProvider(settings.apollo_api_key),
        PDLPeopleProvider(settings.peopledatalabs_api_key),
    ]

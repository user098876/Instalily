import json
import re
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.models import CrawlStatus


@dataclass
class CrawlResult:
    status: CrawlStatus
    url: str
    html: str | None
    reason: str | None
    extraction_method: str


class PublicWebConnector:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _robots_allowed(self, url: str) -> tuple[bool, str | None]:
        parsed = urllib.parse.urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        try:
            rp.set_url(robots_url)
            rp.read()
            if not rp.can_fetch("InstaLilyBot", url):
                return False, "robots_disallow"
            return True, None
        except Exception:
            # Prefer resilience: if robots cannot be fetched, continue with explicit reason.
            return True, "robots_unavailable"

    @retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(3))
    def fetch(self, url: str) -> CrawlResult:
        allowed, robots_reason = self._robots_allowed(url)
        if not allowed:
            return CrawlResult(
                status=CrawlStatus.blocked,
                url=url,
                html=None,
                reason=robots_reason,
                extraction_method="robots_guard",
            )
        try:
            resp = requests.get(
                url,
                timeout=self.settings.request_timeout_seconds,
                headers={"User-Agent": "InstaLilyBot/1.0"},
            )
            if resp.status_code == 429:
                return CrawlResult(CrawlStatus.rate_limited, url, None, "http_429", "http_get")
            if resp.status_code >= 400:
                return CrawlResult(CrawlStatus.blocked, url, None, f"http_{resp.status_code}", "http_get")
            reason = robots_reason if robots_reason else None
            method = "http_get_with_robots_fallback" if robots_reason == "robots_unavailable" else "http_get"
            return CrawlResult(CrawlStatus.success, url, resp.text, reason, method)
        except requests.RequestException as exc:
            return CrawlResult(CrawlStatus.parser_failed, url, None, str(exc), "http_get")


class FixtureWebConnector:
    """Deterministic connector backed by saved HTML fixtures from real public pages."""

    def __init__(self, manifest_path: str) -> None:
        self.manifest_path = Path(manifest_path)
        self.manifest = {}
        if not self.manifest_path.exists():
            return
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            self.manifest = payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            self.manifest = {}

    def fetch(self, url: str) -> CrawlResult:
        row = self.manifest.get(url)
        if not row:
            return CrawlResult(
                status=CrawlStatus.no_relevant_data,
                url=url,
                html=None,
                reason="fixture_missing",
                extraction_method="fixture",
            )
        status = CrawlStatus(row.get("status", "success"))
        reason = row.get("reason")
        fixture_file = row.get("fixture_file")
        html = None
        if fixture_file:
            fixture_path = (self.manifest_path.parent / fixture_file).resolve()
            if fixture_path.exists():
                html = fixture_path.read_text(encoding="utf-8")
            else:
                return CrawlResult(
                    status=CrawlStatus.parser_failed,
                    url=url,
                    html=None,
                    reason="fixture_file_not_found",
                    extraction_method="fixture",
                )
        return CrawlResult(
            status=status,
            url=url,
            html=html,
            reason=reason,
            extraction_method="fixture",
        )


def build_web_connector():
    settings = get_settings()
    if settings.demo_fixture_mode:
        return FixtureWebConnector(settings.demo_fixture_manifest)
    return PublicWebConnector()


def extract_text_snippets(html: str, keywords: list[str], max_snippets: int = 8) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)
    lowered = text.lower()
    snippets: list[str] = []
    for keyword in keywords:
        for match in re.finditer(re.escape(keyword.lower()), lowered):
            start = max(0, match.start() - 90)
            end = min(len(text), match.end() + 90)
            snippet = text[start:end].strip()
            if snippet and snippet not in snippets:
                snippets.append(snippet)
            if len(snippets) >= max_snippets:
                return snippets
    return snippets

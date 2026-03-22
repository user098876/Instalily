import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


TITLE_KEYWORDS = {
    "vp",
    "vice president",
    "director",
    "head",
    "product",
    "innovation",
    "r&d",
    "research",
    "materials",
    "graphics",
    "architectural",
    "printing",
    "technical",
    "brand",
    "marketing",
}

PEOPLE_LINK_HINTS = {
    "team",
    "leadership",
    "about",
    "company",
    "people",
    "directory",
    "news",
    "press",
    "contact",
}

BLOCKED_NAME_PHRASES = {
    "about us",
    "contact us",
    "learn more",
    "read more",
    "register",
    "sign in",
    "our team",
    "leadership",
}

NAME_RE = re.compile(r"^[A-Z][a-zA-Z'\-.]+(?:\s+[A-Z][a-zA-Z'\-.]+){1,3}$")


@dataclass
class PersonTitleCandidate:
    full_name: str
    title: str
    source_url: str
    snippet: str
    extraction_method: str
    extraction_certainty: float


@dataclass
class ConfidenceBreakdown:
    score: float
    source_quality: float
    title_relevance: float
    extraction_certainty: float


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def is_plausible_name(value: str) -> bool:
    text = _clean(value)
    lower = text.lower()
    if len(text) < 5 or len(text) > 80:
        return False
    if lower in BLOCKED_NAME_PHRASES:
        return False
    if any(ch.isdigit() for ch in text):
        return False
    return bool(NAME_RE.match(text))


def title_relevance_score(title: str) -> float:
    lower = _clean(title).lower()
    if not lower:
        return 0.0
    matches = sum(1 for kw in TITLE_KEYWORDS if kw in lower)
    if matches == 0:
        return 0.0
    return min(1.0, 0.35 + (matches * 0.18))


def source_quality_score(source_url: str) -> float:
    path = urlparse(source_url).path.lower()
    if any(k in path for k in ["leadership", "team", "about-us", "/about"]):
        return 1.0
    if any(k in path for k in ["news", "press", "company"]):
        return 0.7
    if any(k in path for k in ["contact", "directory"]):
        return 0.6
    return 0.45


def compute_confidence(source_url: str, title: str, extraction_certainty: float) -> ConfidenceBreakdown:
    src = source_quality_score(source_url)
    role = title_relevance_score(title)
    cert = max(0.0, min(1.0, extraction_certainty))

    score = min(1.0, (src * 0.35) + (role * 0.45) + (cert * 0.20))
    return ConfidenceBreakdown(score=score, source_quality=src, title_relevance=role, extraction_certainty=cert)


def discover_people_links(html: str, base_url: str, max_links: int = 6) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    base = urlparse(base_url)
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()

    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        if parsed.netloc != base.netloc:
            continue

        anchor_text = _clean(anchor.get_text(" ", strip=True)).lower()
        combined = f"{parsed.path} {parsed.query} {anchor_text}"
        match_count = sum(1 for hint in PEOPLE_LINK_HINTS if hint in combined)
        if match_count == 0:
            continue
        if full in seen:
            continue
        seen.add(full)
        depth_penalty = parsed.path.count("/")
        score = (match_count * 10) - depth_penalty
        scored.append((score, full))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [url for _, url in scored[:max_links]]


def _extract_from_structured_blocks(soup: BeautifulSoup, source_url: str) -> list[PersonTitleCandidate]:
    candidates: list[PersonTitleCandidate] = []
    blocks = soup.select(
        "[class*='team'], [class*='leader'], [class*='staff'], [class*='person'], "
        "[class*='profile'], [id*='team'], [id*='leader'], article, li, tr"
    )

    for block in blocks:
        name_texts = []
        title_texts = []

        for tag in block.select("h1, h2, h3, h4, h5, strong, .name"):
            val = _clean(tag.get_text(" ", strip=True))
            if is_plausible_name(val):
                name_texts.append(val)

        for tag in block.select(".title, .role, p, span, td"):
            val = _clean(tag.get_text(" ", strip=True))
            if title_relevance_score(val) > 0:
                title_texts.append(val)

        if not name_texts:
            # fallback: first short text line in block
            line = _clean(block.get_text(" ", strip=True))
            possible = re.split(r"\||,| - | – ", line)
            for chunk in possible:
                if is_plausible_name(chunk):
                    name_texts.append(chunk)
                    break

        if not name_texts or not title_texts:
            continue

        snippet = _clean(block.get_text(" ", strip=True))[:280]
        for full_name in name_texts[:1]:
            for title in title_texts[:1]:
                candidates.append(
                    PersonTitleCandidate(
                        full_name=full_name,
                        title=title,
                        source_url=source_url,
                        snippet=snippet,
                        extraction_method="html_structured_person_card",
                        extraction_certainty=0.85,
                    )
                )

    return candidates


def _extract_from_text_patterns(soup: BeautifulSoup, source_url: str) -> list[PersonTitleCandidate]:
    candidates: list[PersonTitleCandidate] = []
    lines = []
    for tag in soup.select("p, li, div"):
        text = _clean(tag.get_text(" ", strip=True))
        if 8 <= len(text) <= 180:
            lines.append(text)

    for line in lines:
        parts = re.split(r"\||,| - | – ", line)
        if len(parts) < 2:
            continue

        name = _clean(parts[0])
        title = _clean(" ".join(parts[1:]))

        if not is_plausible_name(name):
            continue
        if title_relevance_score(title) <= 0:
            continue

        candidates.append(
            PersonTitleCandidate(
                full_name=name,
                title=title,
                source_url=source_url,
                snippet=line[:280],
                extraction_method="text_name_title_pattern",
                extraction_certainty=0.65,
            )
        )

    return candidates


def extract_person_title_candidates(html: str, source_url: str) -> list[PersonTitleCandidate]:
    soup = BeautifulSoup(html, "lxml")
    raw_candidates = _extract_from_structured_blocks(soup, source_url)
    raw_candidates.extend(_extract_from_text_patterns(soup, source_url))

    deduped: dict[tuple[str, str], PersonTitleCandidate] = {}
    for cand in raw_candidates:
        if title_relevance_score(cand.title) <= 0:
            continue

        key = (_clean(cand.full_name).lower(), _clean(cand.title).lower())
        prev = deduped.get(key)
        if prev is None or cand.extraction_certainty > prev.extraction_certainty:
            deduped[key] = cand

    return sorted(deduped.values(), key=lambda c: (c.full_name, c.title))[:100]

import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


@dataclass
class CompanyCandidate:
    name: str
    website: str | None
    snippet: str
    signal: str


BLOCKED_EXACT = {
    "about",
    "contact",
    "learn more",
    "register",
    "read more",
    "download",
    "view all",
    "sponsors",
    "exhibitors",
    "members",
    "directory",
    "privacy policy",
    "terms",
    "cookie policy",
    "booth",
    "login",
    "sign in",
}

BLOCKED_SUBSTRINGS = {
    "202",
    "booth",
    "hall",
    "open now",
    "join us",
    "subscribe",
    "agenda",
    "speakers",
    "location",
    "date",
    "hours",
    "tickets",
    "add to calendar",
}

NAME_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9&\-'.]*")
DOMAIN_RE = re.compile(r"\b([a-z0-9][a-z0-9\-]{1,62}\.[a-z]{2,})\b", re.IGNORECASE)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def is_valid_company_name(value: str) -> bool:
    text = clean_text(value)
    lower = text.lower()
    if len(text) < 3 or len(text) > 90:
        return False
    if lower in BLOCKED_EXACT:
        return False
    if any(chunk in lower for chunk in BLOCKED_SUBSTRINGS):
        return False
    words = NAME_WORD_RE.findall(text)
    if len(words) == 0 or len(words) > 8:
        return False
    alpha_chars = sum(1 for ch in text if ch.isalpha())
    if alpha_chars < 3:
        return False
    # suppress mostly punctuation/numeric labels
    if sum(1 for ch in text if ch.isdigit()) > max(2, len(text) // 4):
        return False
    # ignore obvious nav phrases
    if lower.startswith("view ") or lower.startswith("learn "):
        return False
    return True


def extract_website_from_card(card, page_url: str) -> str | None:
    page_domain = urlparse(page_url).netloc.lower()
    # Prefer explicit external links likely to be company websites.
    for anchor in card.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        full = urljoin(page_url, href)
        parsed = urlparse(full)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        anchor_text = clean_text(anchor.get_text(" ", strip=True)).lower()
        if "mailto:" in href.lower() or parsed.netloc.endswith(page_domain):
            continue
        if any(k in anchor_text for k in ["website", "visit", "company", "profile"]) or parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

    text_blob = card.get_text(" ", strip=True)
    for m in DOMAIN_RE.finditer(text_blob):
        domain = m.group(1).lower()
        if domain != page_domain:
            return f"https://{domain}"
    return None


def _candidate_from_card(card, page_url: str, signal: str) -> list[CompanyCandidate]:
    candidates: list[CompanyCandidate] = []

    headings = card.select("h1, h2, h3, h4, h5, h6, .company-name, .name, strong")
    texts = [clean_text(h.get_text(" ", strip=True)) for h in headings if clean_text(h.get_text(" ", strip=True))]

    # Fallback to first non-trivial anchor text in a card if no heading exists.
    if not texts:
        for a in card.select("a"):
            t = clean_text(a.get_text(" ", strip=True))
            if t and len(t) <= 90:
                texts.append(t)
                break

    website = extract_website_from_card(card, page_url)

    for text in texts:
        if not is_valid_company_name(text):
            continue
        snippet = clean_text(card.get_text(" ", strip=True))[:260]
        candidates.append(
            CompanyCandidate(
                name=text,
                website=website,
                snippet=snippet,
                signal=signal,
            )
        )
    return candidates


def _extract_from_table(soup: BeautifulSoup, page_url: str) -> list[CompanyCandidate]:
    out: list[CompanyCandidate] = []
    for row in soup.select("table tr"):
        cells = row.select("th, td")
        if not cells:
            continue
        first_text = clean_text(cells[0].get_text(" ", strip=True))
        if not is_valid_company_name(first_text):
            continue
        website = extract_website_from_card(row, page_url)
        snippet = clean_text(row.get_text(" ", strip=True))[:260]
        out.append(CompanyCandidate(name=first_text, website=website, snippet=snippet, signal="table_row"))
    return out


def _extract_from_lists(soup: BeautifulSoup, page_url: str) -> list[CompanyCandidate]:
    out: list[CompanyCandidate] = []
    for ul in soup.select("ul, ol"):
        items = ul.select(":scope > li")
        if len(items) < 3:
            continue
        for li in items:
            text = clean_text(li.get_text(" ", strip=True))
            if not is_valid_company_name(text):
                continue
            website = extract_website_from_card(li, page_url)
            snippet = clean_text(li.get_text(" ", strip=True))[:260]
            out.append(CompanyCandidate(name=text, website=website, snippet=snippet, signal="repeated_list"))
    return out


def _extract_from_logo_alts(soup: BeautifulSoup, page_url: str) -> list[CompanyCandidate]:
    out: list[CompanyCandidate] = []
    for img in soup.select("img[alt]"):
        alt = clean_text(img.get("alt", ""))
        if not is_valid_company_name(alt):
            continue
        website = None
        parent_link = img.find_parent("a")
        if parent_link is not None:
            website = extract_website_from_card(parent_link, page_url)
        snippet = f"Logo alt text: {alt}"
        out.append(CompanyCandidate(name=alt, website=website, snippet=snippet, signal="logo_alt"))
    return out


def _extract_from_jsonld(soup: BeautifulSoup, page_url: str) -> list[CompanyCandidate]:
    out: list[CompanyCandidate] = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text("", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        nodes = payload if isinstance(payload, list) else [payload]
        for node in nodes:
            if isinstance(node, dict):
                out.extend(_extract_jsonld_node(node, page_url))
    return out


def _extract_jsonld_node(node: dict, page_url: str) -> list[CompanyCandidate]:
    out: list[CompanyCandidate] = []
    if "@graph" in node and isinstance(node["@graph"], list):
        for child in node["@graph"]:
            if isinstance(child, dict):
                out.extend(_extract_jsonld_node(child, page_url))

    node_type = str(node.get("@type", "")).lower()
    name = clean_text(str(node.get("name", "")))
    if name and ("organization" in node_type or "brand" in node_type or "corporation" in node_type):
        website = node.get("url") if isinstance(node.get("url"), str) else None
        if website:
            parsed = urlparse(website)
            website = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else None
        if is_valid_company_name(name):
            out.append(
                CompanyCandidate(
                    name=name,
                    website=website,
                    snippet=f"JSON-LD organization: {name}",
                    signal="jsonld",
                )
            )
    return out


def normalize_company_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", name)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def extract_company_candidates(html: str, page_url: str) -> list[CompanyCandidate]:
    soup = BeautifulSoup(html, "lxml")

    candidate_blocks = soup.select(
        "[class*='exhibitor'], [class*='sponsor'], [class*='member'], [class*='directory'], "
        "[id*='exhibitor'], [id*='sponsor'], [id*='member'], [id*='directory'], [data-exhibitor], [data-member]"
    )

    candidates: list[CompanyCandidate] = []
    for block in candidate_blocks:
        candidates.extend(_candidate_from_card(block, page_url, "card"))

    candidates.extend(_extract_from_table(soup, page_url))
    candidates.extend(_extract_from_lists(soup, page_url))
    candidates.extend(_extract_from_logo_alts(soup, page_url))
    candidates.extend(_extract_from_jsonld(soup, page_url))

    # Dedupe by normalized name, preferring entries with website and richer snippets.
    deduped: dict[str, CompanyCandidate] = {}
    for cand in candidates:
        norm = normalize_company_name(cand.name)
        if not norm:
            continue
        current = deduped.get(norm)
        if current is None:
            deduped[norm] = cand
            continue
        score = (1 if cand.website else 0) + min(len(cand.snippet), 200) / 200
        current_score = (1 if current.website else 0) + min(len(current.snippet), 200) / 200
        if score > current_score:
            deduped[norm] = cand

    return sorted(deduped.values(), key=lambda c: c.name)[:500]


def discover_likely_roster_links(html: str, base_url: str, max_links: int = 8) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    base = urlparse(base_url)
    hint_terms = {
        "exhibitor",
        "exhibitors",
        "sponsor",
        "sponsors",
        "member",
        "members",
        "directory",
        "listing",
        "partners",
        "partner",
    }

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

        url_text = f"{parsed.path} {parsed.query} {clean_text(anchor.get_text(' ', strip=True)).lower()}"
        matches = sum(1 for t in hint_terms if t in url_text)
        if matches == 0:
            continue
        if full in seen:
            continue
        seen.add(full)
        depth = parsed.path.count("/")
        score = matches * 10 - depth
        scored.append((score, full))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [u for _, u in scored[:max_links]]

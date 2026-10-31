from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse
import hashlib
import re
import time

from data_fetcher.adapters.official_restaurants import check_robots_or_raise, looks_like_access_challenge
from data_fetcher.http_client import FetchHttpError, fetch_text
from data_fetcher.io_utils import write_text_file

SOURCE_KEY = "official-restaurant-detail-payment-pages"
SOURCE_NAME = "Official restaurant detail payment page scan"
SOURCE_TYPE = "official-restaurant-detail-payment-page"

PAYMENT_METHOD_PATTERNS = {
    "visa": r"\bvisa(?:\s+(?:debit|electron|paywave))?\b",
    "mastercard": r"\b(?:master\s*card|mastercard|euro/mastercard|debit\s+mastercard)\b",
    "american_express": r"\b(?:american\s+express|amex)\b",
    "discover": r"\bdiscover\b",
    "diners_club": r"\b(?:diners\s+club|diners)\b",
    "jcb": r"\bjcb\b",
    "unionpay": r"\b(?:union\s*pay|unionpay)\b",
    "credit_cards": r"\b(?:credit\s+cards?|major\s+cards?|card\s+payments?)\b",
    "debit_cards": r"\bdebit\s+cards?\b",
    "contactless": r"\b(?:contactless|nfc|tap\s+to\s+pay)\b",
    "apple_pay": r"\bapple\s+pay\b",
    "google_pay": r"\bgoogle\s+pay\b",
    "cash": r"\bcash\b",
}

PAYMENT_CONTEXT_RE = re.compile(
    r"\b(?:accept(?:ed|s|ing)?|payment(?:s|\s+methods?|\s+types?|\s+options?)?|pay(?:s|ing|ment)?|"
    r"credit\s+cards?|debit\s+cards?|card\s+payments?|cashless|card\s+only|cash\s+only|checkout|settle\s+payment)\b",
    flags=re.IGNORECASE,
)
CASH_NOT_ACCEPTED_RE = re.compile(
    r"\b(?:cashless|cash\s+is\s+not\s+accepted|does\s+not\s+accept\s+cash|no\s+cash|card\s+only|cards?\s+only)\b",
    flags=re.IGNORECASE,
)
CASH_ONLY_RE = re.compile(r"\bcash\s+only\b", flags=re.IGNORECASE)
SUPPORTED_TEXT_CONTENT_TYPES = {"", "text/html", "text/plain", "application/xhtml+xml"}


@dataclass(frozen=True)
class DetailPageCandidate:
    url: str
    restaurants: tuple[dict[str, object], ...]


def fetch_restaurant_detail_payment_acceptance(
    restaurants: list[dict[str, object]],
    *,
    fetched_at: str,
    run_id: str,
    output_root: Path,
    user_agent: str,
    delay_ms: int,
    allowed_methods: list[str],
    max_pages: int | None,
    warnings: list[str],
    logger: Callable[[str], None],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    candidates = detail_page_candidates(restaurants)
    if max_pages is not None:
        candidates = candidates[:max_pages]

    rows: list[dict[str, object]] = []
    raw_refs: list[str] = []
    skipped_pages = 0
    for index, candidate in enumerate(candidates, start=1):
        logger(
            f"[Restaurant detail payments] {index}/{len(candidates)} scanning {candidate.url} "
            f"for {len(candidate.restaurants)} restaurant row(s)."
        )
        try:
            check_robots_or_raise(candidate.url, user_agent)
            response = fetch_text(candidate.url, user_agent=user_agent, timeout_seconds=45)
            content_type = (response.content_type or "").split(";", 1)[0].strip().lower()
            if content_type not in SUPPORTED_TEXT_CONTENT_TYPES:
                skipped_pages += 1
                warnings.append(f"Restaurant detail payment scan skipped {candidate.url}: unsupported content type {content_type}.")
                continue
            if looks_like_access_challenge(response.body):
                skipped_pages += 1
                warnings.append(f"Restaurant detail payment scan skipped {candidate.url}: source returned an access challenge.")
                continue

            raw_ref = raw_ref_for_detail_page(candidate.url, run_id)
            write_text_file(output_root / raw_ref, response.body)
            raw_refs.append(raw_ref)
            mentions = extract_payment_mentions(response.body, allowed_methods=allowed_methods)
            if not mentions:
                continue

            shared_page = len(candidate.restaurants) > 1
            for restaurant in candidate.restaurants:
                applicable_mentions = mentions_for_restaurant(restaurant, mentions, shared_page=shared_page)
                rows.extend(
                    payment_rows_from_mentions(
                        restaurant,
                        applicable_mentions,
                        fetched_at=fetched_at,
                        raw_ref=raw_ref,
                        source_url=candidate.url,
                    )
                )
            if shared_page and mentions:
                warnings.append(
                    f"Restaurant detail payment scan found payment text on shared page {candidate.url}; "
                    "facts were applied only when the evidence snippet mentioned the restaurant name."
                )
        except Exception as error:
            skipped_pages += 1
            warnings.append(f"Restaurant detail payment scan failed for {candidate.url}: {message_from_error(error)}")
            logger(f"[Restaurant detail payments] {message_from_error(error)}")
            if should_stop_detail_scan(error):
                warnings.append("Stopping restaurant detail payment scan after a rate-limit or access-control response.")
                break
        sleep_ms(delay_ms)

    return dedupe_payment_rows(rows), restaurant_detail_payment_manifest_entry(
        enabled=True,
        record_count=len(dedupe_payment_rows(rows)),
        raw_refs=raw_refs,
        queried_page_count=len(candidates),
        skipped_page_count=skipped_pages,
        max_pages=max_pages,
    )


def detail_page_candidates(restaurants: list[dict[str, object]]) -> list[DetailPageCandidate]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for restaurant in restaurants:
        url = detail_scan_url(restaurant)
        if not url:
            continue
        grouped.setdefault(url, []).append(restaurant)
    return [DetailPageCandidate(url=url, restaurants=tuple(rows)) for url, rows in sorted(grouped.items())]


def detail_scan_url(restaurant: dict[str, object]) -> str | None:
    if clean_text(restaurant.get("associationScope")) != "official_airport_directory":
        return None
    raw_url = clean_text(restaurant.get("officialSourcePath")) or source_url(restaurant)
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.path.lower().endswith((".pdf", ".jpg", ".jpeg", ".png", ".webp", ".svg")):
        return None

    source_host = urlparse(source_url(restaurant)).netloc.lower()
    if source_host and parsed.netloc.lower() != source_host:
        return None

    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", parsed.query, ""))


def extract_payment_mentions(html_text: str, *, allowed_methods: list[str]) -> list[dict[str, object]]:
    text = html_to_visible_text(html_text)
    allowed = set(allowed_methods)
    by_method: dict[str, dict[str, object]] = {}

    for method, pattern in PAYMENT_METHOD_PATTERNS.items():
        if method not in allowed:
            continue
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            snippet = evidence_window(text, match.start(), match.end())
            if not has_payment_context(snippet, method):
                continue
            status = "not_accepted" if method == "cash" and CASH_NOT_ACCEPTED_RE.search(snippet) else "accepted"
            by_method[method] = {
                "paymentMethod": method,
                "acceptanceStatus": status,
                "evidenceValue": compact_text(snippet),
            }

    if CASH_NOT_ACCEPTED_RE.search(text) and "cash" in allowed:
        snippet = evidence_window(text, CASH_NOT_ACCEPTED_RE.search(text).start(), CASH_NOT_ACCEPTED_RE.search(text).end())
        by_method["cash"] = {
            "paymentMethod": "cash",
            "acceptanceStatus": "not_accepted",
            "evidenceValue": compact_text(snippet),
        }

    if CASH_ONLY_RE.search(text):
        snippet = evidence_window(text, CASH_ONLY_RE.search(text).start(), CASH_ONLY_RE.search(text).end())
        if "cash" in allowed:
            by_method["cash"] = {
                "paymentMethod": "cash",
                "acceptanceStatus": "accepted",
                "evidenceValue": compact_text(snippet),
            }
        for method in ["credit_cards", "debit_cards"]:
            if method in allowed:
                by_method[method] = {
                    "paymentMethod": method,
                    "acceptanceStatus": "not_accepted",
                    "evidenceValue": compact_text(snippet),
                }

    return sorted(by_method.values(), key=lambda mention: str(mention["paymentMethod"]))


def has_payment_context(snippet: str, method: str) -> bool:
    if PAYMENT_CONTEXT_RE.search(snippet):
        return True
    if method in {"apple_pay", "google_pay", "contactless"} and re.search(r"\bpay\b", snippet, flags=re.IGNORECASE):
        return True
    return False


def mentions_for_restaurant(
    restaurant: dict[str, object],
    mentions: list[dict[str, object]],
    *,
    shared_page: bool,
) -> list[dict[str, object]]:
    if not shared_page:
        return mentions
    name_key = normalized_text(restaurant.get("name"))
    if not name_key:
        return []
    return [mention for mention in mentions if name_key in normalized_text(mention.get("evidenceValue"))]


def payment_rows_from_mentions(
    restaurant: dict[str, object],
    mentions: list[dict[str, object]],
    *,
    fetched_at: str,
    raw_ref: str,
    source_url: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    restaurant_id = clean_text(restaurant.get("id"))
    airport_iata = clean_text(restaurant.get("airportIata"))
    restaurant_name = clean_text(restaurant.get("name"))
    for mention in mentions:
        method = clean_text(mention.get("paymentMethod"))
        status = clean_text(mention.get("acceptanceStatus"))
        if not method or status not in {"accepted", "not_accepted"}:
            continue
        rows.append(
            {
                "id": f"payment_acceptance:{slugify(restaurant_id)}:{method}",
                "restaurantId": restaurant_id,
                "airportIata": airport_iata,
                "restaurantName": restaurant_name,
                "paymentMethod": method,
                "acceptanceStatus": status,
                "evidenceType": "official_restaurant_detail_page_text",
                "evidenceValue": clean_text(mention.get("evidenceValue")),
                "reviewedAt": None,
                "reviewedBy": None,
                "legalBasis": "Official public restaurant or airport detail page explicitly states this payment method.",
                "source": {
                    "sourceName": SOURCE_NAME,
                    "sourceType": SOURCE_TYPE,
                    "sourceUrl": source_url,
                    "licenseStatus": "official-public-page-text",
                    "attributionRequired": True,
                    "fetchedAt": fetched_at,
                    "rawRef": raw_ref,
                    "confidenceScore": 0.84 if status == "accepted" else 0.8,
                    "notes": [
                        "Payment acceptance was extracted from explicit payment text on an official public detail page.",
                        "Only methods named in the source text are changed; all other methods remain unknown.",
                        "Generic credit-card text is not converted into Visa, Mastercard, or Amex acceptance.",
                    ],
                },
            }
        )
    return rows


def restaurant_detail_payment_manifest_entry(
    *,
    enabled: bool,
    record_count: int,
    raw_refs: list[str] | None = None,
    queried_page_count: int = 0,
    skipped_page_count: int = 0,
    max_pages: int | None = None,
) -> dict[str, object]:
    return {
        "key": SOURCE_KEY,
        "sourceName": SOURCE_NAME,
        "sourceType": SOURCE_TYPE,
        "sourceUrl": "official restaurant detail URLs" if enabled else "not-configured",
        "licenseStatus": "official-public-page-text",
        "attributionRequired": True,
        "legalBasis": "Uses public official restaurant/airport detail pages after robots.txt checks; payment facts require explicit text evidence.",
        "allowedUse": "Supplement exact restaurant payment-acceptance rows when an official page names a payment method.",
        "restrictions": [
            "Do not infer card-network acceptance from generic credit-card text.",
            "Do not apply shared directory-page payment text to every restaurant unless the snippet names the restaurant.",
            "Do not scan third-party brand pages by default; use airport/operator source pages only.",
            "Stop or lower coverage when robots.txt disallows a path or the source returns bot protection.",
        ],
        "recordCount": record_count,
        "queriedPageCount": queried_page_count,
        "skippedPageCount": skipped_page_count,
        "maxPages": max_pages,
        "rawRefs": raw_refs or [],
        "skipped": not enabled,
    }


def dedupe_payment_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_id: dict[str, dict[str, object]] = {}
    for row in rows:
        row_id = clean_text(row.get("id"))
        if row_id and row_id not in by_id:
            by_id[row_id] = row
    return sorted(by_id.values(), key=lambda row: (str(row.get("airportIata")), str(row.get("restaurantName")), str(row.get("paymentMethod"))))


def raw_ref_for_detail_page(url: str, run_id: str) -> str:
    parsed = urlparse(url)
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:14]
    return str(Path("raw") / "restaurant-detail-payments" / f"{slugify(parsed.netloc)}-{url_hash}-{run_id}.html")


def html_to_visible_text(html_text: str) -> str:
    text = re.sub(r"<script\b[\s\S]*?</script>", " ", html_text, flags=re.IGNORECASE)
    text = re.sub(r"<style\b[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|div|li|tr|td|th|h[1-6]|section|article)>", ". ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", ". ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return compact_text(text, max_length=0)


def evidence_window(text: str, start: int, end: int, *, radius: int = 140) -> str:
    left_boundary = max(text.rfind(". ", 0, start), text.rfind(" | ", 0, start), text.rfind("\n", 0, start))
    right_candidates = [
        candidate for candidate in [text.find(". ", end), text.find(" | ", end), text.find("\n", end)] if candidate != -1
    ]
    if left_boundary != -1 or right_candidates:
        left = left_boundary + 1 if left_boundary != -1 else 0
        right = min(right_candidates) + 1 if right_candidates else len(text)
        return text[left:right]
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right]


def compact_text(value: object, *, max_length: int = 260) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if max_length and len(text) > max_length:
        return text[: max_length - 3].rstrip() + "..."
    return text


def source_url(restaurant: dict[str, object]) -> str:
    source = restaurant.get("source") if isinstance(restaurant.get("source"), dict) else {}
    return clean_text(source.get("sourceUrl"))


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalized_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_text(value).lower()).strip()


def slugify(value: object) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", clean_text(value).lower()).strip("-")
    return slug or "unknown"


def should_stop_detail_scan(error: object) -> bool:
    return isinstance(error, FetchHttpError) and error.status in {403, 429}


def message_from_error(error: object) -> str:
    if isinstance(error, FetchHttpError):
        return f"HTTP {error.status} from {error.url}"
    return str(error)


def sleep_ms(delay_ms: int) -> None:
    time.sleep(delay_ms / 1000)

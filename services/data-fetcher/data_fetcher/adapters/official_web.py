from __future__ import annotations

from collections.abc import Callable
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse
import re
import time

from data_fetcher.http_client import fetch_text
from data_fetcher.io_utils import stable_timestamp, write_text_file
from data_fetcher.robots import is_path_allowed_by_robots


def crawl_official_airport_pages(
    airports: list[dict[str, object]],
    *,
    fetched_at: str,
    raw_root: Path,
    user_agent: str,
    delay_ms: int,
    logger: Callable[[str], None] | None = None,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []

    for index, airport in enumerate(airports, start=1):
        iata_code = str(airport["iataCode"])
        if logger:
            logger(f"[Web] {index}/{len(airports)} checking {iata_code}.")

        target_url = normalize_official_url(airport.get("officialWebsite"))
        if not target_url:
            if logger:
                logger(f"[Web] {iata_code} skipped: no official website.")
            records.append(
                {
                    "airportIata": iata_code,
                    "sourceUrl": "",
                    "robotsUrl": "",
                    "robotsAllowed": False,
                    "status": "skipped_no_official_website",
                    "title": None,
                    "fetchedAt": fetched_at,
                    "notes": ["OurAirports did not provide a valid official website URL."],
                }
            )
            continue

        robots_url = urljoin(target_url, "/robots.txt")
        try:
            robots_text = fetch_text(robots_url, user_agent=user_agent, timeout_seconds=15).body
        except Exception as error:  # Errors are turned into audit records.
            if logger:
                logger(f"[Web] {iata_code} skipped: robots.txt unavailable.")
            records.append(
                {
                    "airportIata": iata_code,
                    "sourceUrl": target_url,
                    "robotsUrl": robots_url,
                    "robotsAllowed": False,
                    "status": "skipped_robots_unavailable",
                    "title": None,
                    "fetchedAt": fetched_at,
                    "notes": [
                        "Robots.txt was unavailable, so conservative demo mode skipped crawling: "
                        f"{message_from_error(error)}"
                    ],
                }
            )
            sleep_ms(delay_ms)
            continue

        parsed = urlparse(target_url)
        path_with_search = parsed.path or "/"
        if parsed.query:
            path_with_search = f"{path_with_search}?{parsed.query}"
        robots_allowed = is_path_allowed_by_robots(path_with_search, robots_text, user_agent)

        if not robots_allowed:
            if logger:
                logger(f"[Web] {iata_code} skipped: robots.txt disallowed this path.")
            records.append(
                {
                    "airportIata": iata_code,
                    "sourceUrl": target_url,
                    "robotsUrl": robots_url,
                    "robotsAllowed": False,
                    "status": "skipped_robots_disallow",
                    "title": None,
                    "fetchedAt": fetched_at,
                    "notes": ["robots.txt disallowed crawling this path."],
                }
            )
            sleep_ms(delay_ms)
            continue

        try:
            if logger:
                logger(f"[Web] {iata_code} fetching official homepage evidence.")
            page = fetch_text(
                target_url,
                user_agent=user_agent,
                timeout_seconds=20,
                headers={"Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"},
            )
            filename = f"{iata_code}-{stable_timestamp(fetched_at)}.html"
            raw_ref = str(Path("raw") / "web-evidence" / filename)
            write_text_file(raw_root / "web-evidence" / filename, page.body)
            if logger:
                logger(f"[Web] {iata_code} fetched official homepage evidence.")
            records.append(
                {
                    "airportIata": iata_code,
                    "sourceUrl": target_url,
                    "robotsUrl": robots_url,
                    "robotsAllowed": True,
                    "status": "fetched",
                    "title": extract_title(page.body),
                    "fetchedAt": fetched_at,
                    "rawRef": raw_ref,
                    "notes": [
                        "Public official airport homepage fetched after robots.txt allowed the path.",
                        "This demo stores evidence metadata only; restaurant/payment extraction from HTML needs per-site review before use.",
                    ],
                }
            )
        except Exception as error:  # Errors are turned into audit records.
            if logger:
                logger(f"[Web] {iata_code} failed after robots allowed path.")
            records.append(
                {
                    "airportIata": iata_code,
                    "sourceUrl": target_url,
                    "robotsUrl": robots_url,
                    "robotsAllowed": True,
                    "status": "fetch_failed",
                    "title": None,
                    "fetchedAt": fetched_at,
                    "notes": [f"Fetch failed after robots.txt allowed the path: {message_from_error(error)}"],
                }
            )

        sleep_ms(delay_ms)

    return records


def extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>([\s\S]*?)</title>", html, flags=re.IGNORECASE)
    if not match:
        return None
    return unescape(re.sub(r"\s+", " ", match.group(1)).strip())


def normalize_official_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return value.strip()


def sleep_ms(delay_ms: int) -> None:
    time.sleep(delay_ms / 1000)


def message_from_error(error: object) -> str:
    return str(error)

from __future__ import annotations

from io import StringIO
import csv

from data_fetcher.http_client import fetch_text
from data_fetcher.sources import OUR_AIRPORTS_DATA_URL

AIRPORT_TYPE_PRIORITY = {"large_airport": 0, "medium_airport": 1, "small_airport": 2}


def fetch_ourairports(
    target_airport_codes: list[str],
    *,
    fetched_at: str,
    raw_ref: str,
    user_agent: str,
) -> tuple[str, list[dict[str, object]], list[str]]:
    response = fetch_text(OUR_AIRPORTS_DATA_URL, user_agent=user_agent, timeout_seconds=45)
    rows = list(csv.DictReader(StringIO(response.body)))
    airports = normalize_ourairports_rows(rows, target_airport_codes, fetched_at=fetched_at, raw_ref=raw_ref)
    found = {airport["iataCode"] for airport in airports}
    warnings = [
        f"OurAirports did not return a matching airport for {code}."
        for code in target_airport_codes
        if code not in found
    ]
    return response.body, airports, warnings


def fetch_us_airports_from_ourairports(
    *,
    limit: int,
    fetched_at: str,
    raw_ref: str,
    user_agent: str,
    scheduled_only: bool = True,
) -> tuple[str, list[dict[str, object]], list[str]]:
    response = fetch_text(OUR_AIRPORTS_DATA_URL, user_agent=user_agent, timeout_seconds=45)
    rows = list(csv.DictReader(StringIO(response.body)))
    selected_codes = select_us_airport_codes(rows, limit=limit, scheduled_only=scheduled_only)
    airports = normalize_ourairports_rows(rows, selected_codes, fetched_at=fetched_at, raw_ref=raw_ref)
    warnings: list[str] = []
    if len(airports) < limit:
        warnings.append(f"OurAirports returned {len(airports)} eligible US airports, below requested limit {limit}.")
    return response.body, airports, warnings


def select_us_airport_codes(
    rows: list[dict[str, str]],
    *,
    limit: int,
    scheduled_only: bool = True,
) -> list[str]:
    candidates: list[tuple[int, str]] = []
    seen: set[str] = set()
    for row in rows:
        iata_code = (row.get("iata_code") or "").upper()
        airport_type = row.get("type") or ""
        if row.get("iso_country") != "US" or len(iata_code) != 3 or iata_code in seen:
            continue
        if airport_type not in AIRPORT_TYPE_PRIORITY:
            continue
        if scheduled_only and row.get("scheduled_service") != "yes":
            continue
        seen.add(iata_code)
        candidates.append((AIRPORT_TYPE_PRIORITY[airport_type], iata_code))
    return [iata_code for _, iata_code in sorted(candidates)[:limit]]


def normalize_ourairports_rows(
    rows: list[dict[str, str]],
    target_airport_codes: list[str],
    *,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    targets = {code.upper() for code in target_airport_codes}
    target_order = {code.upper(): index for index, code in enumerate(target_airport_codes)}
    airports: list[dict[str, object]] = []

    for row in rows:
        iata_code = (row.get("iata_code") or "").upper()
        if iata_code not in targets or row.get("iso_country") != "US":
            continue

        airports.append(
            {
                "id": f"airport:{iata_code}",
                "iataCode": iata_code,
                "ident": row.get("ident") or "",
                "type": row.get("type") or "",
                "name": row.get("name") or "",
                "municipality": empty_to_none(row.get("municipality")),
                "regionCode": row.get("iso_region") or "",
                "countryCode": row.get("iso_country") or "",
                "latitude": parse_required_float(row.get("latitude_deg"), iata_code, "latitude_deg"),
                "longitude": parse_required_float(row.get("longitude_deg"), iata_code, "longitude_deg"),
                "scheduledService": row.get("scheduled_service") == "yes",
                "officialWebsite": normalize_url(row.get("home_link")),
                "source": {
                    "sourceName": "OurAirports airports.csv",
                    "sourceType": "ourairports",
                    "sourceUrl": OUR_AIRPORTS_DATA_URL,
                    "licenseStatus": "public-domain",
                    "attributionRequired": False,
                    "fetchedAt": fetched_at,
                    "rawRef": raw_ref,
                    "confidenceScore": 0.95,
                    "notes": [
                        "OurAirports publishes this dataset as public domain.",
                        "Airport metadata is source-backed, but the source does not guarantee accuracy.",
                    ],
                },
            }
        )

    return sorted(airports, key=lambda airport: target_order.get(str(airport["iataCode"]), 999))


def parse_required_float(value: str | None, iata_code: str, field_name: str) -> float:
    try:
        return float(value or "")
    except ValueError as error:
        raise ValueError(f"Invalid {field_name} for {iata_code}: {value}") from error


def normalize_url(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value.startswith(("http://", "https://")):
        return None
    return value


def empty_to_none(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None

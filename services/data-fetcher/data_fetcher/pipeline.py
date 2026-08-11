from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
import os
import time

from data_fetcher.adapters.official_web import crawl_official_airport_pages
from data_fetcher.adapters.ourairports import fetch_ourairports
from data_fetcher.adapters.overpass import fetch_restaurants_for_airport
from data_fetcher.adapters.visa import empty_visa_benefit_dataset
from data_fetcher.http_client import FetchHttpError, DEFAULT_USER_AGENT
from data_fetcher.io_utils import stable_timestamp, write_csv_file, write_json_file, write_text_file
from data_fetcher.sources import DEFAULT_OVERPASS_ENDPOINT, TARGET_AIRPORT_IATA_CODES, base_source_manifest_entries
from data_fetcher.validation import validate_dataset

AIRPORT_COLUMNS = [
    "id",
    "iataCode",
    "ident",
    "type",
    "name",
    "municipality",
    "regionCode",
    "countryCode",
    "latitude",
    "longitude",
    "scheduledService",
    "officialWebsite",
    "sourceName",
    "sourceType",
    "sourceUrl",
    "licenseStatus",
    "attributionRequired",
    "fetchedAt",
    "rawRef",
    "confidenceScore",
    "sourceNotes",
]

RESTAURANT_COLUMNS = [
    "id",
    "airportIata",
    "name",
    "category",
    "associationScope",
    "latitude",
    "longitude",
    "terminal",
    "paymentMethods",
    "paymentEvidence",
    "rawPaymentTags",
    "osmType",
    "osmId",
    "sourceName",
    "sourceType",
    "sourceUrl",
    "licenseStatus",
    "attributionRequired",
    "fetchedAt",
    "rawRef",
    "confidenceScore",
    "sourceNotes",
]

CARD_PRODUCT_COLUMNS = [
    "id",
    "network",
    "issuer",
    "productName",
    "sourceName",
    "sourceType",
    "sourceUrl",
    "licenseStatus",
    "attributionRequired",
    "fetchedAt",
    "rawRef",
    "confidenceScore",
    "sourceNotes",
]

BENEFIT_COLUMNS = [
    "id",
    "cardProductId",
    "airportIata",
    "benefitType",
    "description",
    "sourceName",
    "sourceType",
    "sourceUrl",
    "licenseStatus",
    "attributionRequired",
    "fetchedAt",
    "rawRef",
    "confidenceScore",
    "sourceNotes",
]

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def default_output_root() -> Path:
    return PROJECT_ROOT / "data"


def run_data_fetcher(
    *,
    limit: int = 20,
    output_root: Path | None = None,
    target_airport_codes: list[str] | None = None,
    skip_overpass: bool = False,
    include_web_evidence: bool = False,
    delay_ms: int = 3000,
    radius_meters: int = 1500,
    user_agent: str | None = None,
    overpass_endpoint: str | None = None,
    logger: Callable[[str], None] | None = None,
) -> dict[str, object]:
    fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    run_id = stable_timestamp(fetched_at)
    output_root = (output_root or default_output_root()).resolve()
    raw_root = output_root / "raw"
    normalized_root = output_root / "normalized"
    manifest_root = output_root / "manifests"
    warnings: list[str] = []
    log = logger or (lambda _message: None)
    user_agent = user_agent or DEFAULT_USER_AGENT
    overpass_endpoint = overpass_endpoint or os.environ.get("OVERPASS_ENDPOINT") or DEFAULT_OVERPASS_ENDPOINT

    target_codes = (target_airport_codes or TARGET_AIRPORT_IATA_CODES)[:limit]
    target_codes = [code.upper() for code in target_codes]

    raw_root.mkdir(parents=True, exist_ok=True)
    normalized_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)

    ourairports_raw_ref = str(Path("raw") / "ourairports" / f"airports-{run_id}.csv")
    log(f"[OurAirports] Fetching airport CSV for {len(target_codes)} target airports.")
    raw_csv, airports, airport_warnings = fetch_ourairports(
        target_codes,
        fetched_at=fetched_at,
        raw_ref=ourairports_raw_ref,
        user_agent=user_agent,
    )
    warnings.extend(airport_warnings)
    write_text_file(output_root / ourairports_raw_ref, raw_csv)
    log(f"[OurAirports] Normalized {len(airports)} airports.")

    restaurants: list[dict[str, object]] = []
    if skip_overpass:
        warnings.append("Overpass restaurant fetch skipped by --skip-overpass.")
    else:
        for index, airport in enumerate(airports, start=1):
            airport_iata = str(airport["iataCode"])
            raw_ref = str(Path("raw") / "overpass" / f"{airport_iata}-{run_id}.json")
            log(f"[Overpass] {index}/{len(airports)} fetching restaurant/payment tags near {airport_iata}.")
            try:
                raw_json, airport_restaurants = fetch_restaurants_for_airport(
                    airport,
                    fetched_at=fetched_at,
                    raw_ref=raw_ref,
                    user_agent=user_agent,
                    endpoint=overpass_endpoint,
                    radius_meters=radius_meters,
                )
                restaurants.extend(airport_restaurants)
                write_json_file(output_root / raw_ref, raw_json)
                log(f"[Overpass] {airport_iata} normalized {len(airport_restaurants)} restaurant-like amenities.")
            except Exception as error:  # Errors become source warnings.
                warning = f"Overpass fetch failed for {airport_iata}: {message_from_error(error)}"
                warnings.append(warning)
                log(f"[Overpass] {airport_iata} failed: {message_from_error(error)}")
                if should_stop_overpass(error):
                    warnings.append(
                        "Stopping further Overpass requests because the public API returned a rate-limit or access-control response."
                    )
                    log("[Overpass] Stopping further requests to respect public API limits.")
                    break

            sleep_ms(delay_ms)

    if include_web_evidence:
        log(f"[Web] Checking robots.txt and official homepage evidence for {len(airports)} airports.")
        web_evidence = crawl_official_airport_pages(
            airports,
            fetched_at=fetched_at,
            raw_root=raw_root,
            user_agent=user_agent,
            delay_ms=delay_ms,
            logger=log,
        )
    else:
        warnings.append("Official web evidence crawl skipped. Use --include-web-evidence after source review.")
        web_evidence = []

    card_products, benefits, visa_manifest_entry = empty_visa_benefit_dataset()
    errors, validation_warnings = validate_dataset(
        airports=airports,
        restaurants=restaurants,
        card_products=card_products,
        benefits=benefits,
    )
    warnings.extend(validation_warnings)
    if errors:
        raise RuntimeError("Validation failed:\n" + "\n".join(errors))

    write_json_file(normalized_root / "airports.json", airports)
    write_csv_file(normalized_root / "airports.csv", flatten_rows(airports), AIRPORT_COLUMNS)
    write_json_file(normalized_root / "restaurants.json", restaurants)
    write_csv_file(normalized_root / "restaurants.csv", flatten_rows(restaurants), RESTAURANT_COLUMNS)
    write_json_file(normalized_root / "card_products.json", card_products)
    write_csv_file(normalized_root / "card_products.csv", flatten_rows(card_products), CARD_PRODUCT_COLUMNS)
    write_json_file(normalized_root / "benefits.json", benefits)
    write_csv_file(normalized_root / "benefits.csv", flatten_rows(benefits), BENEFIT_COLUMNS)
    write_json_file(manifest_root / "web-evidence.json", web_evidence)

    log("[Output] Writing normalized JSON/CSV and source manifest.")
    source_manifest = build_source_manifest(
        fetched_at=fetched_at,
        run_id=run_id,
        airports=airports,
        restaurants=restaurants,
        card_products=card_products,
        benefits=benefits,
        web_evidence=web_evidence,
        warnings=warnings,
        visa_manifest_entry=visa_manifest_entry,
        skip_overpass=skip_overpass,
        include_web_evidence=include_web_evidence,
    )
    write_json_file(manifest_root / "source-manifest.json", source_manifest)

    return {
        "runId": run_id,
        "outputRoot": str(output_root),
        "airportCount": len(airports),
        "restaurantCount": len(restaurants),
        "cardProductCount": len(card_products),
        "benefitCount": len(benefits),
        "warningCount": len(warnings),
        "warnings": warnings,
    }


def flatten_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    flattened: list[dict[str, object]] = []
    for row in rows:
        source = row.get("source") if isinstance(row.get("source"), dict) else {}
        next_row = {key: value for key, value in row.items() if key != "source"}
        next_row.update(
            {
                "sourceName": source.get("sourceName"),
                "sourceType": source.get("sourceType"),
                "sourceUrl": source.get("sourceUrl"),
                "licenseStatus": source.get("licenseStatus"),
                "attributionRequired": source.get("attributionRequired"),
                "fetchedAt": source.get("fetchedAt"),
                "rawRef": source.get("rawRef"),
                "confidenceScore": source.get("confidenceScore"),
                "sourceNotes": source.get("notes"),
            }
        )
        flattened.append(next_row)
    return flattened


def build_source_manifest(
    *,
    fetched_at: str,
    run_id: str,
    airports: list[dict[str, object]],
    restaurants: list[dict[str, object]],
    card_products: list[dict[str, object]],
    benefits: list[dict[str, object]],
    web_evidence: list[dict[str, object]],
    warnings: list[str],
    visa_manifest_entry: dict[str, object],
    skip_overpass: bool,
    include_web_evidence: bool,
) -> dict[str, object]:
    sources = []
    for entry in base_source_manifest_entries():
        entry = dict(entry)
        if entry["key"] == "ourairports-airports-csv":
            entry["recordCount"] = len(airports)
        elif entry["key"] == "openstreetmap-overpass":
            entry["recordCount"] = len(restaurants)
            entry["skipped"] = skip_overpass
        elif entry["key"] == "official-airport-web-evidence":
            entry["recordCount"] = len(web_evidence)
            entry["skipped"] = not include_web_evidence
        sources.append(entry)

    return {
        "project": "SesameKiller-Compass",
        "runId": run_id,
        "generatedAt": fetched_at,
        "legalMode": "conservative-public-sources-only",
        "accuracyPolicy": "No source-backed field is guessed. Unknown restaurant payment methods remain unknown. OSM radius matches are not official airport tenant confirmation.",
        "outputs": [
            {"path": "data/normalized/airports.json", "rows": len(airports), "canonical": True},
            {"path": "data/normalized/airports.csv", "rows": len(airports), "canonical": False},
            {"path": "data/normalized/restaurants.json", "rows": len(restaurants), "canonical": True},
            {"path": "data/normalized/restaurants.csv", "rows": len(restaurants), "canonical": False},
            {"path": "data/normalized/card_products.json", "rows": len(card_products), "canonical": True},
            {"path": "data/normalized/card_products.csv", "rows": len(card_products), "canonical": False},
            {"path": "data/normalized/benefits.json", "rows": len(benefits), "canonical": True},
            {"path": "data/normalized/benefits.csv", "rows": len(benefits), "canonical": False},
            {"path": "data/manifests/web-evidence.json", "rows": len(web_evidence), "canonical": False},
        ],
        "sources": [*sources, visa_manifest_entry],
        "warnings": warnings,
    }


def should_stop_overpass(error: object) -> bool:
    return isinstance(error, FetchHttpError) and error.status in {403, 429}


def sleep_ms(delay_ms: int) -> None:
    time.sleep(delay_ms / 1000)


def message_from_error(error: object) -> str:
    return str(error)

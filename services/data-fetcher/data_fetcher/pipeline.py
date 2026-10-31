from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
import os
import re
import time

from data_fetcher.adapters.card_benefits import load_reviewed_card_benefits
from data_fetcher.adapters.google_places import fetch_google_places_payment_options, google_places_payment_manifest_entry
from data_fetcher.adapters.payment_acceptance import load_reviewed_payment_acceptance
from data_fetcher.adapters.restaurant_detail_payments import (
    fetch_restaurant_detail_payment_acceptance,
    restaurant_detail_payment_manifest_entry,
)
from data_fetcher.adapters.official_restaurants import fetch_official_restaurants_for_airports
from data_fetcher.adapters.official_web import crawl_official_airport_pages
from data_fetcher.adapters.ourairports import fetch_ourairports, fetch_us_airports_from_ourairports
from data_fetcher.adapters.overpass import OSM_ASSOCIATION_MODES, PAYMENT_TAG_MAP, fetch_restaurants_for_airport
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
    "officialCategory",
    "description",
    "associationScope",
    "latitude",
    "longitude",
    "terminal",
    "securityArea",
    "gate",
    "locationDescription",
    "paymentMethods",
    "paymentEvidence",
    "rawPaymentTags",
    "officialSourceId",
    "officialSourcePath",
    "mapUrl",
    "imageUrls",
    "featureTags",
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

PAYMENT_ACCEPTANCE_COLUMNS = [
    "id",
    "restaurantId",
    "airportIata",
    "restaurantName",
    "paymentMethod",
    "acceptanceStatus",
    "evidenceType",
    "evidenceValue",
    "reviewedAt",
    "reviewedBy",
    "legalBasis",
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
    "productUrl",
    "termsUrl",
    "reviewedAt",
    "reviewedBy",
    "legalBasis",
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
    "restaurantId",
    "restaurantName",
    "restaurantMatchStatus",
    "restaurantMatchConfidence",
    "matchedRestaurantSourceUrl",
    "matchedRestaurantAssociationScope",
    "benefitType",
    "description",
    "paymentNetwork",
    "termsUrl",
    "offerUrl",
    "validFrom",
    "validTo",
    "requiresEnrollment",
    "reviewedAt",
    "reviewedBy",
    "legalBasis",
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
RESTAURANT_SOURCE_MODES = {"official", "official-plus-osm", "osm", "osm-radius", "none"}
CARD_PAYMENT_METHODS = [
    "visa",
    "mastercard",
    "american_express",
    "discover",
    "diners_club",
    "jcb",
    "unionpay",
]
SUPPLEMENTAL_PAYMENT_METHODS = ["credit_cards", "debit_cards", "contactless", "apple_pay", "google_pay", "cash"]
PAYMENT_ACCEPTANCE_METHODS = [*CARD_PAYMENT_METHODS, *SUPPLEMENTAL_PAYMENT_METHODS]


def default_output_root() -> Path:
    return PROJECT_ROOT / "data"


def run_data_fetcher(
    *,
    limit: int = 20,
    output_root: Path | None = None,
    target_airport_codes: list[str] | None = None,
    us_airports: bool = False,
    us_scheduled_only: bool = True,
    restaurant_source: str = "official",
    skip_overpass: bool = False,
    include_web_evidence: bool = False,
    delay_ms: int = 3000,
    radius_meters: int = 1500,
    user_agent: str | None = None,
    overpass_endpoint: str | None = None,
    osm_association_mode: str = "area-first",
    overpass_max_retries: int = 2,
    overpass_retry_backoff_ms: int = 30000,
    card_benefits_file: Path | None = None,
    payment_acceptance_file: Path | None = None,
    google_places_payment_options: bool = False,
    google_places_api_key: str | None = None,
    google_places_limit: int | None = None,
    restaurant_detail_payment_pages: bool = False,
    restaurant_detail_limit: int | None = None,
    product_readiness: bool = False,
    min_official_airport_coverage_percent: float | None = None,
    min_restaurant_terminal_coverage_percent: float | None = None,
    min_card_network_coverage_percent: float | None = None,
    logger: Callable[[str], None] | None = None,
) -> dict[str, object]:
    if restaurant_source not in RESTAURANT_SOURCE_MODES:
        raise ValueError(f"restaurant_source must be one of {sorted(RESTAURANT_SOURCE_MODES)}")
    if osm_association_mode not in OSM_ASSOCIATION_MODES:
        raise ValueError(f"osm_association_mode must be one of {sorted(OSM_ASSOCIATION_MODES)}")

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

    if us_airports and target_airport_codes:
        raise ValueError("Use either --us-airports or --airports, not both.")
    target_codes = [] if us_airports else (target_airport_codes or TARGET_AIRPORT_IATA_CODES)[:limit]
    target_codes = [code.upper() for code in target_codes]

    raw_root.mkdir(parents=True, exist_ok=True)
    normalized_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)

    ourairports_raw_ref = str(Path("raw") / "ourairports" / f"airports-{run_id}.csv")
    if us_airports:
        log(f"[OurAirports] Fetching airport CSV and selecting {limit} US scheduled-service airports.")
        raw_csv, airports, airport_warnings = fetch_us_airports_from_ourairports(
            limit=limit,
            fetched_at=fetched_at,
            raw_ref=ourairports_raw_ref,
            user_agent=user_agent,
            scheduled_only=us_scheduled_only,
        )
    else:
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
    restaurant_evidence: list[dict[str, object]] = []
    if restaurant_source in {"official", "official-plus-osm"}:
        official_restaurants, restaurant_evidence, official_warnings = fetch_official_restaurants_for_airports(
            airports,
            fetched_at=fetched_at,
            raw_root=raw_root,
            user_agent=user_agent,
            delay_ms=delay_ms,
            logger=log,
        )
        restaurants.extend(official_restaurants)
        warnings.extend(official_warnings)
    elif restaurant_source == "none":
        warnings.append("Restaurant fetch skipped by --restaurant-source none.")
    elif restaurant_source == "osm":
        warnings.append("Using scalable OSM restaurant mode; records are not official airport tenant confirmation.")
    elif restaurant_source == "osm-radius":
        warnings.append("Using legacy OSM radius restaurant mode; records are not official airport tenant confirmation.")

    should_fetch_osm = restaurant_source in {"official-plus-osm", "osm", "osm-radius"} and not skip_overpass
    effective_osm_association_mode = "radius-only" if restaurant_source == "osm-radius" else osm_association_mode
    if skip_overpass and restaurant_source in {"official-plus-osm", "osm", "osm-radius"}:
        warnings.append("Overpass restaurant fetch skipped by --skip-overpass.")
    elif should_fetch_osm:
        restaurants.extend(
            fetch_osm_restaurants(
                airports,
                fetched_at=fetched_at,
                run_id=run_id,
                output_root=output_root,
                user_agent=user_agent,
                overpass_endpoint=overpass_endpoint,
                radius_meters=radius_meters,
                delay_ms=delay_ms,
                association_mode=effective_osm_association_mode,
                max_retries=overpass_max_retries,
                retry_backoff_ms=overpass_retry_backoff_ms,
                warnings=warnings,
                logger=log,
            )
        )

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
        warnings.extend(web_evidence_warnings(web_evidence))
    else:
        warnings.append("Official web evidence crawl skipped. Use --include-web-evidence after source review.")
        web_evidence = []

    card_raw_ref = None
    if card_benefits_file is not None:
        card_raw_ref = str(Path("raw") / "card-benefits" / f"reviewed-card-benefits-{run_id}.json")
        write_text_file(output_root / card_raw_ref, card_benefits_file.read_text(encoding="utf-8"))
    card_products, benefits, card_manifest_entry, card_warnings = load_reviewed_card_benefits(
        card_benefits_file,
        fetched_at=fetched_at,
        raw_ref=card_raw_ref,
    )
    warnings.extend(card_warnings)
    warnings.extend(resolve_benefit_restaurant_matches(benefits, restaurants))

    payment_acceptance_raw_ref = None
    if payment_acceptance_file is not None:
        payment_acceptance_raw_ref = str(Path("raw") / "payment-acceptance" / f"reviewed-payment-acceptance-{run_id}.json")
        write_text_file(output_root / payment_acceptance_raw_ref, payment_acceptance_file.read_text(encoding="utf-8"))
    reviewed_payment_acceptance, payment_acceptance_manifest_entry, payment_warnings = load_reviewed_payment_acceptance(
        payment_acceptance_file,
        restaurants,
        fetched_at=fetched_at,
        raw_ref=payment_acceptance_raw_ref,
        allowed_methods=PAYMENT_ACCEPTANCE_METHODS,
    )
    warnings.extend(payment_warnings)

    restaurant_detail_payment_acceptance: list[dict[str, object]] = []
    restaurant_detail_payment_manifest = restaurant_detail_payment_manifest_entry(enabled=False, record_count=0)
    if restaurant_detail_payment_pages:
        restaurant_detail_payment_acceptance, restaurant_detail_payment_manifest = fetch_restaurant_detail_payment_acceptance(
            restaurants,
            fetched_at=fetched_at,
            run_id=run_id,
            output_root=output_root,
            user_agent=user_agent,
            delay_ms=delay_ms,
            allowed_methods=PAYMENT_ACCEPTANCE_METHODS,
            max_pages=restaurant_detail_limit,
            warnings=warnings,
            logger=log,
        )

    google_payment_acceptance: list[dict[str, object]] = []
    google_places_manifest_entry = google_places_payment_manifest_entry(enabled=False, record_count=0)
    if google_places_payment_options:
        google_key = google_places_api_key or os.environ.get("GOOGLE_PLACES_API_KEY")
        if not google_key:
            warnings.append("Google Places payment-options enrichment requested but GOOGLE_PLACES_API_KEY is not set.")
            google_places_manifest_entry = google_places_payment_manifest_entry(
                enabled=True,
                record_count=0,
                missing_api_key=True,
            )
        else:
            google_payment_acceptance, google_places_manifest_entry = fetch_google_places_payment_options(
                restaurants,
                fetched_at=fetched_at,
                run_id=run_id,
                output_root=output_root,
                api_key=google_key,
                user_agent=user_agent,
                delay_ms=delay_ms,
                allowed_methods=PAYMENT_ACCEPTANCE_METHODS,
                max_restaurants=google_places_limit,
                warnings=warnings,
                logger=log,
            )

    payment_acceptance = merge_payment_acceptance_records(
        build_payment_acceptance_records(restaurants),
        [*restaurant_detail_payment_acceptance, *google_payment_acceptance, *reviewed_payment_acceptance],
    )

    errors, validation_warnings = validate_dataset(
        airports=airports,
        restaurants=restaurants,
        payment_acceptance=payment_acceptance,
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
    write_json_file(normalized_root / "payment_acceptance.json", payment_acceptance)
    write_csv_file(normalized_root / "payment_acceptance.csv", flatten_rows(payment_acceptance), PAYMENT_ACCEPTANCE_COLUMNS)
    write_json_file(normalized_root / "card_products.json", card_products)
    write_csv_file(normalized_root / "card_products.csv", flatten_rows(card_products), CARD_PRODUCT_COLUMNS)
    write_json_file(normalized_root / "benefits.json", benefits)
    write_csv_file(normalized_root / "benefits.csv", flatten_rows(benefits), BENEFIT_COLUMNS)
    write_json_file(manifest_root / "web-evidence.json", web_evidence)
    write_json_file(manifest_root / "official-restaurants.json", restaurant_evidence)

    log("[Output] Writing normalized JSON/CSV and source manifest.")
    coverage = build_coverage_report(
        airports=airports,
        restaurants=restaurants,
        payment_acceptance=payment_acceptance,
        restaurant_evidence=restaurant_evidence,
    )
    readiness_report = build_readiness_report(
        coverage=coverage,
        product_readiness=product_readiness,
        min_official_airport_coverage_percent=min_official_airport_coverage_percent,
        min_restaurant_terminal_coverage_percent=min_restaurant_terminal_coverage_percent,
        min_card_network_coverage_percent=min_card_network_coverage_percent,
    )
    source_manifest = build_source_manifest(
        fetched_at=fetched_at,
        run_id=run_id,
        airports=airports,
        restaurants=restaurants,
        payment_acceptance=payment_acceptance,
        card_products=card_products,
        benefits=benefits,
        web_evidence=web_evidence,
        restaurant_evidence=restaurant_evidence,
        warnings=warnings,
        card_manifest_entry=card_manifest_entry,
        payment_acceptance_manifest_entry=payment_acceptance_manifest_entry,
        payment_enrichment_manifest_entries=[restaurant_detail_payment_manifest, google_places_manifest_entry],
        skip_overpass=skip_overpass,
        include_web_evidence=include_web_evidence,
        restaurant_source=restaurant_source,
        osm_association_mode=effective_osm_association_mode,
        us_airports=us_airports,
        coverage=coverage,
        readiness_report=readiness_report,
    )
    write_json_file(manifest_root / "source-manifest.json", source_manifest)

    if product_readiness and readiness_report["status"] == "failed":
        raise RuntimeError("Product readiness failed after writing outputs:\n" + "\n".join(readiness_report["errors"]))

    return {
        "runId": run_id,
        "outputRoot": str(output_root),
        "airportCount": len(airports),
        "restaurantCount": len(restaurants),
        "paymentAcceptanceCount": len(payment_acceptance),
        "cardProductCount": len(card_products),
        "benefitCount": len(benefits),
        "warningCount": len(warnings),
        "warnings": warnings,
        "coverage": coverage,
        "readiness": readiness_report,
    }


def build_payment_acceptance_records(restaurants: list[dict[str, object]]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for restaurant in restaurants:
        restaurant_id = clean_match_text(restaurant.get("id"))
        airport_iata = clean_match_text(restaurant.get("airportIata"))
        restaurant_name = clean_match_text(restaurant.get("name"))
        if not restaurant_id or not airport_iata or not restaurant_name:
            continue

        methods = {
            clean_match_text(method)
            for method in restaurant.get("paymentMethods", [])
            if clean_match_text(method) and clean_match_text(method) != "unknown"
        }
        evidence_type = clean_match_text(restaurant.get("paymentEvidence")) or "not_provided_by_source"
        raw_payment_tags = restaurant.get("rawPaymentTags") if isinstance(restaurant.get("rawPaymentTags"), dict) else {}
        has_explicit_payment_source = evidence_type == "explicit_source_tag" and bool(methods)

        for method in PAYMENT_ACCEPTANCE_METHODS:
            accepted = has_explicit_payment_source and method in methods
            status = "accepted" if accepted else "unknown"
            method_evidence = payment_evidence_value(raw_payment_tags, method) if accepted else "not_provided_by_source"
            source = restaurant.get("source") if isinstance(restaurant.get("source"), dict) else {}
            records.append(
                {
                    "id": f"payment_acceptance:{slugify_key(restaurant_id)}:{method}",
                    "restaurantId": restaurant_id,
                    "airportIata": airport_iata,
                    "restaurantName": restaurant_name,
                    "paymentMethod": method,
                    "acceptanceStatus": status,
                    "evidenceType": evidence_type if accepted else "not_provided_by_source",
                    "evidenceValue": method_evidence,
                    "reviewedAt": None,
                    "reviewedBy": None,
                    "legalBasis": None,
                    "source": {
                        "sourceName": source.get("sourceName"),
                        "sourceType": source.get("sourceType"),
                        "sourceUrl": restaurant_source_url(restaurant),
                        "licenseStatus": source.get("licenseStatus"),
                        "attributionRequired": source.get("attributionRequired"),
                        "fetchedAt": source.get("fetchedAt"),
                        "rawRef": source.get("rawRef"),
                        "confidenceScore": min(float(source.get("confidenceScore") or 0.0), 0.85) if accepted else 0.0,
                        "notes": [
                            "This row represents one payment method at one restaurant.",
                            "accepted is emitted only from explicit source payment tags; unknown means the source did not publish that method, not that the method is rejected.",
                        ],
                    },
                }
            )
    return sorted(records, key=lambda record: (str(record["airportIata"]), str(record["restaurantName"]), str(record["paymentMethod"])))


def merge_payment_acceptance_records(
    base_records: list[dict[str, object]],
    reviewed_records: list[dict[str, object]],
) -> list[dict[str, object]]:
    by_id = {clean_match_text(record.get("id")): record for record in base_records if record.get("id")}
    for record in reviewed_records:
        record_id = clean_match_text(record.get("id"))
        if record_id:
            by_id[record_id] = record
    return sorted(
        by_id.values(),
        key=lambda record: (
            str(record.get("airportIata")),
            str(record.get("restaurantName")),
            str(record.get("paymentMethod")),
        ),
    )


def payment_evidence_value(raw_payment_tags: dict[object, object], method: str) -> str:
    matches = [
        f"{tag}={value}"
        for tag, value in raw_payment_tags.items()
        if PAYMENT_TAG_MAP.get(str(tag)) == method
    ]
    return ";".join(matches) if matches else "explicit_source_tag"


def fetch_osm_restaurants(
    airports: list[dict[str, object]],
    *,
    fetched_at: str,
    run_id: str,
    output_root: Path,
    user_agent: str,
    overpass_endpoint: str,
    radius_meters: int,
    delay_ms: int,
    association_mode: str,
    max_retries: int,
    retry_backoff_ms: int,
    warnings: list[str],
    logger: Callable[[str], None],
) -> list[dict[str, object]]:
    restaurants: list[dict[str, object]] = []
    for index, airport in enumerate(airports, start=1):
        airport_iata = str(airport["iataCode"])
        raw_ref = str(Path("raw") / "overpass" / f"{airport_iata}-{run_id}.json")
        logger(f"[Overpass] {index}/{len(airports)} fetching restaurant/payment tags for {airport_iata} ({association_mode}).")
        attempts = 0
        while True:
            try:
                raw_json, airport_restaurants = fetch_restaurants_for_airport(
                    airport,
                    fetched_at=fetched_at,
                    raw_ref=raw_ref,
                    user_agent=user_agent,
                    endpoint=overpass_endpoint,
                    radius_meters=radius_meters,
                    association_mode=association_mode,
                )
                restaurants.extend(airport_restaurants)
                write_json_file(output_root / raw_ref, raw_json)
                logger(f"[Overpass] {airport_iata} normalized {len(airport_restaurants)} restaurant-like amenities.")
                break
            except Exception as error:
                attempts += 1
                if should_retry_overpass(error) and attempts <= max_retries:
                    wait_ms = retry_backoff_ms * attempts
                    warning = f"Overpass rate-limited {airport_iata}; retrying in {wait_ms}ms (attempt {attempts}/{max_retries})."
                    warnings.append(warning)
                    logger(f"[Overpass] {warning}")
                    sleep_ms(wait_ms)
                    continue

                warning = f"Overpass fetch failed for {airport_iata}: {message_from_error(error)}"
                warnings.append(warning)
                logger(f"[Overpass] {airport_iata} failed: {message_from_error(error)}")
                if should_stop_overpass(error):
                    warnings.append(
                        "Stopping further Overpass requests because the public API returned a rate-limit or access-control response."
                    )
                    logger("[Overpass] Stopping further requests to respect public API limits.")
                    return restaurants
                break

        sleep_ms(delay_ms)
    return restaurants


def web_evidence_warnings(web_evidence: list[dict[str, object]]) -> list[str]:
    warnings: list[str] = []
    for record in web_evidence:
        status = str(record.get("status") or "")
        if status in {"fetched", "ok"}:
            continue
        airport_iata = str(record.get("airportIata") or "unknown airport")
        notes = record.get("notes") if isinstance(record.get("notes"), list) else []
        detail = f": {compact_warning_detail(notes[0])}" if notes else "."
        warnings.append(f"Official web evidence for {airport_iata} {status}{detail}")
    return warnings


def compact_warning_detail(value: object, *, max_length: int = 220) -> str:
    detail = re.sub(r"\s+", " ", str(value or "")).strip()
    detail = re.sub(r":\s*<(?:!doctype|html)\b[\s\S]*$", ".", detail, flags=re.IGNORECASE)
    if len(detail) > max_length:
        return detail[: max_length - 3].rstrip() + "..."
    return detail


def resolve_benefit_restaurant_matches(
    benefits: list[dict[str, object]],
    restaurants: list[dict[str, object]],
) -> list[str]:
    warnings: list[str] = []
    restaurants_by_id = {str(restaurant.get("id")): restaurant for restaurant in restaurants if restaurant.get("id")}
    restaurants_by_airport_name: dict[tuple[str, str], list[dict[str, object]]] = {}

    for restaurant in restaurants:
        airport_iata = clean_match_text(restaurant.get("airportIata")).upper()
        name_key = normalized_restaurant_name(restaurant.get("name"))
        if airport_iata and name_key:
            restaurants_by_airport_name.setdefault((airport_iata, name_key), []).append(restaurant)

    for benefit in benefits:
        benefit_id = clean_match_text(benefit.get("id")) or "unknown benefit"
        restaurant_id = clean_match_text(benefit.get("restaurantId"))
        restaurant_name = clean_match_text(benefit.get("restaurantName"))
        airport_iata = clean_match_text(benefit.get("airportIata")).upper()

        if not restaurant_id and not restaurant_name:
            benefit["restaurantMatchStatus"] = "not_restaurant_specific"
            benefit["restaurantMatchConfidence"] = 0
            benefit["matchedRestaurantSourceUrl"] = None
            benefit["matchedRestaurantAssociationScope"] = None
            continue

        if restaurant_id:
            matched_restaurant = restaurants_by_id.get(restaurant_id)
            if matched_restaurant is None:
                benefit["restaurantMatchStatus"] = "unmatched_restaurant_id"
                benefit["restaurantMatchConfidence"] = 0
                benefit["matchedRestaurantSourceUrl"] = None
                benefit["matchedRestaurantAssociationScope"] = None
                warnings.append(f"Benefit {benefit_id} references restaurantId {restaurant_id}, but that restaurant is not in this run.")
                continue

            matched_airport = clean_match_text(matched_restaurant.get("airportIata")).upper()
            if airport_iata and airport_iata != matched_airport:
                benefit["restaurantMatchStatus"] = "restaurant_airport_mismatch"
                benefit["restaurantMatchConfidence"] = 0
                benefit["matchedRestaurantSourceUrl"] = restaurant_source_url(matched_restaurant)
                benefit["matchedRestaurantAssociationScope"] = matched_restaurant.get("associationScope")
                warnings.append(
                    f"Benefit {benefit_id} references {restaurant_id} at {airport_iata}, but the matched restaurant belongs to {matched_airport}."
                )
                continue

            apply_restaurant_match(benefit, matched_restaurant, status="matched_by_id", confidence=1.0)
            warn_if_non_official_match(benefit, matched_restaurant, warnings)
            continue

        if not airport_iata:
            benefit["restaurantMatchStatus"] = "missing_airport_for_restaurant_name"
            benefit["restaurantMatchConfidence"] = 0
            benefit["matchedRestaurantSourceUrl"] = None
            benefit["matchedRestaurantAssociationScope"] = None
            warnings.append(f"Benefit {benefit_id} names restaurant {restaurant_name!r} but does not include airportIata.")
            continue

        candidates = restaurants_by_airport_name.get((airport_iata, normalized_restaurant_name(restaurant_name)), [])
        if len(candidates) == 1:
            apply_restaurant_match(benefit, candidates[0], status="matched_by_exact_name", confidence=0.98)
            warn_if_non_official_match(benefit, candidates[0], warnings)
        elif len(candidates) > 1:
            benefit["restaurantMatchStatus"] = "ambiguous_restaurant_name"
            benefit["restaurantMatchConfidence"] = 0
            benefit["matchedRestaurantSourceUrl"] = None
            benefit["matchedRestaurantAssociationScope"] = None
            candidate_ids = ", ".join(str(candidate.get("id")) for candidate in candidates)
            warnings.append(
                f"Benefit {benefit_id} names restaurant {restaurant_name!r} at {airport_iata}, but multiple official rows match. Use restaurantId; candidates: {candidate_ids}."
            )
        else:
            benefit["restaurantMatchStatus"] = "unmatched_restaurant_name"
            benefit["restaurantMatchConfidence"] = 0
            benefit["matchedRestaurantSourceUrl"] = None
            benefit["matchedRestaurantAssociationScope"] = None
            warnings.append(f"Benefit {benefit_id} names restaurant {restaurant_name!r} at {airport_iata}, but no fetched restaurant matches exactly.")

    return warnings


def apply_restaurant_match(
    benefit: dict[str, object],
    restaurant: dict[str, object],
    *,
    status: str,
    confidence: float,
) -> None:
    benefit["restaurantId"] = restaurant.get("id")
    benefit["restaurantName"] = restaurant.get("name")
    benefit["airportIata"] = restaurant.get("airportIata")
    benefit["restaurantMatchStatus"] = status
    benefit["restaurantMatchConfidence"] = confidence
    benefit["matchedRestaurantSourceUrl"] = restaurant_source_url(restaurant)
    benefit["matchedRestaurantAssociationScope"] = restaurant.get("associationScope")


def warn_if_non_official_match(
    benefit: dict[str, object],
    restaurant: dict[str, object],
    warnings: list[str],
) -> None:
    if restaurant.get("associationScope") == "official_airport_directory":
        return
    warnings.append(
        f"Benefit {benefit.get('id')} matched restaurant {restaurant.get('id')} from {restaurant.get('associationScope')}; treat it as enrichment, not official terminal inventory."
    )


def restaurant_source_url(restaurant: dict[str, object]) -> str | None:
    source = restaurant.get("source") if isinstance(restaurant.get("source"), dict) else {}
    value = source.get("sourceUrl") or restaurant.get("officialSourcePath")
    return clean_match_text(value) or None


def clean_match_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalized_restaurant_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_match_text(value).lower()).strip()


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
    payment_acceptance: list[dict[str, object]],
    card_products: list[dict[str, object]],
    benefits: list[dict[str, object]],
    web_evidence: list[dict[str, object]],
    restaurant_evidence: list[dict[str, object]],
    warnings: list[str],
    card_manifest_entry: dict[str, object],
    payment_acceptance_manifest_entry: dict[str, object],
    payment_enrichment_manifest_entries: list[dict[str, object]],
    skip_overpass: bool,
    include_web_evidence: bool,
    restaurant_source: str,
    osm_association_mode: str,
    us_airports: bool,
    coverage: dict[str, object],
    readiness_report: dict[str, object],
) -> dict[str, object]:
    sources = []
    area_restaurant_count = sum(1 for restaurant in restaurants if restaurant.get("associationScope") == "inside_osm_airport_area")
    radius_restaurant_count = sum(1 for restaurant in restaurants if restaurant.get("associationScope") == "near_airport_radius")
    osm_restaurant_count = area_restaurant_count + radius_restaurant_count
    official_restaurant_count = sum(
        1 for restaurant in restaurants if restaurant.get("associationScope") == "official_airport_directory"
    )
    for entry in base_source_manifest_entries():
        entry = dict(entry)
        if entry["key"] == "ourairports-airports-csv":
            entry["recordCount"] = len(airports)
        elif entry["key"] == "openstreetmap-overpass":
            entry["recordCount"] = osm_restaurant_count
            entry["insideAirportAreaCount"] = area_restaurant_count
            entry["radiusFallbackCount"] = radius_restaurant_count
            entry["associationMode"] = osm_association_mode
            entry["skipped"] = restaurant_source not in {"official-plus-osm", "osm", "osm-radius"} or skip_overpass
        elif entry["key"] == "official-airport-restaurant-directories":
            entry["recordCount"] = official_restaurant_count
            entry["sourceEvidenceCount"] = len(restaurant_evidence)
            entry["skipped"] = restaurant_source not in {"official", "official-plus-osm"}
        elif entry["key"] == "official-airport-web-evidence":
            entry["recordCount"] = len(web_evidence)
            entry["skipped"] = not include_web_evidence
        sources.append(entry)

    return {
        "project": "SesameKiller-Compass",
        "runId": run_id,
        "generatedAt": fetched_at,
        "legalMode": "conservative-public-sources-only",
        "restaurantSourceMode": restaurant_source,
        "airportSelectionMode": "us-airports" if us_airports else "target-list",
        "overpassAssociationMode": osm_association_mode,
        "accuracyPolicy": "No source-backed field is guessed. Official airport directory records are treated as restaurant inventory only for supported reviewed adapters. Payment acceptance is a separate fact table: accepted/not_accepted requires explicit source evidence; unknown is not treated as rejected. Generic Google Places paymentOptions can enrich credit/debit/contactless/cash facts, but card-network acceptance remains unknown unless explicitly sourced. OSM area and radius matches are optional scalable discovery records and not official tenant confirmation.",
        "coverage": coverage,
        "readiness": readiness_report,
        "outputs": [
            {"path": "data/normalized/airports.json", "rows": len(airports), "canonical": True},
            {"path": "data/normalized/airports.csv", "rows": len(airports), "canonical": False},
            {"path": "data/normalized/restaurants.json", "rows": len(restaurants), "canonical": True},
            {"path": "data/normalized/restaurants.csv", "rows": len(restaurants), "canonical": False},
            {"path": "data/normalized/payment_acceptance.json", "rows": len(payment_acceptance), "canonical": True},
            {"path": "data/normalized/payment_acceptance.csv", "rows": len(payment_acceptance), "canonical": False},
            {"path": "data/normalized/card_products.json", "rows": len(card_products), "canonical": True},
            {"path": "data/normalized/card_products.csv", "rows": len(card_products), "canonical": False},
            {"path": "data/normalized/benefits.json", "rows": len(benefits), "canonical": True},
            {"path": "data/normalized/benefits.csv", "rows": len(benefits), "canonical": False},
            {"path": "data/manifests/official-restaurants.json", "rows": len(restaurant_evidence), "canonical": False},
            {"path": "data/manifests/web-evidence.json", "rows": len(web_evidence), "canonical": False},
        ],
        "sources": [*sources, *payment_enrichment_manifest_entries, card_manifest_entry, payment_acceptance_manifest_entry],
        "warnings": warnings,
    }


def build_coverage_report(
    *,
    airports: list[dict[str, object]],
    restaurants: list[dict[str, object]],
    payment_acceptance: list[dict[str, object]],
    restaurant_evidence: list[dict[str, object]],
) -> dict[str, object]:
    airport_codes = sorted(clean_match_text(airport.get("iataCode")) for airport in airports if airport.get("iataCode"))
    official_restaurants = [
        restaurant for restaurant in restaurants if restaurant.get("associationScope") == "official_airport_directory"
    ]
    osm_restaurants = [
        restaurant
        for restaurant in restaurants
        if restaurant.get("associationScope") in {"inside_osm_airport_area", "near_airport_radius"}
    ]
    area_osm_restaurants = [
        restaurant for restaurant in osm_restaurants if restaurant.get("associationScope") == "inside_osm_airport_area"
    ]
    radius_osm_restaurants = [
        restaurant for restaurant in osm_restaurants if restaurant.get("associationScope") == "near_airport_radius"
    ]
    official_airports = sorted({clean_match_text(restaurant.get("airportIata")) for restaurant in official_restaurants})
    osm_airports = sorted({clean_match_text(restaurant.get("airportIata")) for restaurant in osm_restaurants})
    area_osm_airports = sorted({clean_match_text(restaurant.get("airportIata")) for restaurant in area_osm_restaurants})
    restaurant_airports = sorted({clean_match_text(restaurant.get("airportIata")) for restaurant in restaurants})
    unsupported_airports = [code for code in airport_codes if code not in official_airports]
    no_discovery_airports = [code for code in airport_codes if code not in restaurant_airports]
    accepted_payment_rows = [row for row in payment_acceptance if row.get("acceptanceStatus") == "accepted"]
    known_payment_rows = [row for row in payment_acceptance if row.get("acceptanceStatus") in {"accepted", "not_accepted"}]
    card_network_rows = [row for row in payment_acceptance if row.get("paymentMethod") in CARD_PAYMENT_METHODS]
    known_card_network_rows = [row for row in card_network_rows if row.get("acceptanceStatus") in {"accepted", "not_accepted"}]
    restaurants_with_known_payment = sorted({clean_match_text(row.get("restaurantId")) for row in known_payment_rows})
    restaurants_with_known_card_network = sorted({clean_match_text(row.get("restaurantId")) for row in known_card_network_rows})
    evidence_by_status: dict[str, int] = {}
    for entry in restaurant_evidence:
        status = clean_match_text(entry.get("status")) or "unknown"
        evidence_by_status[status] = evidence_by_status.get(status, 0) + 1

    terminal_count = count_present(official_restaurants, "terminal")
    gate_count = count_present(official_restaurants, "gate")
    coordinate_count = sum(
        1
        for restaurant in official_restaurants
        if restaurant.get("latitude") is not None and restaurant.get("longitude") is not None
    )

    return {
        "targetAirportCount": len(airport_codes),
        "officialRestaurantAirportCoverage": {
            "coveredAirportCount": len(official_airports),
            "totalAirportCount": len(airport_codes),
            "percent": percent(len(official_airports), len(airport_codes)),
            "coveredAirports": official_airports,
            "uncoveredAirports": unsupported_airports,
            "evidenceStatusCounts": evidence_by_status,
        },
        "officialRestaurantFieldCoverage": {
            "restaurantCount": len(official_restaurants),
            "withTerminalCount": terminal_count,
            "withTerminalPercent": percent(terminal_count, len(official_restaurants)),
            "withGateCount": gate_count,
            "withGatePercent": percent(gate_count, len(official_restaurants)),
            "withCoordinatesCount": coordinate_count,
            "withCoordinatesPercent": percent(coordinate_count, len(official_restaurants)),
        },
        "restaurantDiscoveryAirportCoverage": {
            "coveredAirportCount": len(restaurant_airports),
            "totalAirportCount": len(airport_codes),
            "percent": percent(len(restaurant_airports), len(airport_codes)),
            "coveredAirports": restaurant_airports,
            "uncoveredAirports": no_discovery_airports,
            "policy": "Counts any restaurant row from official adapters or OSM discovery. This is discovery coverage, not official tenant confirmation.",
        },
        "osmRestaurantCoverage": {
            "coveredAirportCount": len(osm_airports),
            "totalAirportCount": len(airport_codes),
            "percent": percent(len(osm_airports), len(airport_codes)),
            "coveredAirports": osm_airports,
            "insideAirportAreaAirportCount": len(area_osm_airports),
            "insideAirportAreaAirports": area_osm_airports,
            "restaurantCount": len(osm_restaurants),
            "insideAirportAreaRestaurantCount": len(area_osm_restaurants),
            "radiusFallbackRestaurantCount": len(radius_osm_restaurants),
            "policy": "OSM rows are source-backed open-data discovery records under ODbL. They are not official airport-directory tenant records.",
        },
        "paymentAcceptanceCoverage": {
            "methodRows": len(payment_acceptance),
            "knownRows": len(known_payment_rows),
            "knownRowsPercent": percent(len(known_payment_rows), len(payment_acceptance)),
            "acceptedRows": len(accepted_payment_rows),
            "acceptedRowsPercent": percent(len(accepted_payment_rows), len(payment_acceptance)),
            "cardNetworkRows": len(card_network_rows),
            "knownCardNetworkRows": len(known_card_network_rows),
            "knownCardNetworkRowsPercent": percent(len(known_card_network_rows), len(card_network_rows)),
            "restaurantsWithKnownPaymentCount": len(restaurants_with_known_payment),
            "restaurantsWithKnownPaymentPercent": percent(len(restaurants_with_known_payment), len(restaurants)),
            "restaurantsWithKnownCardNetworkCount": len(restaurants_with_known_card_network),
            "restaurantsWithKnownCardNetworkPercent": percent(len(restaurants_with_known_card_network), len(restaurants)),
            "policy": "unknown means no explicit source evidence for that method; it is not a negative acceptance claim.",
        },
    }


def build_readiness_report(
    *,
    coverage: dict[str, object],
    product_readiness: bool,
    min_official_airport_coverage_percent: float | None,
    min_restaurant_terminal_coverage_percent: float | None,
    min_card_network_coverage_percent: float | None,
) -> dict[str, object]:
    default_threshold = 90.0 if product_readiness else 0.0
    thresholds = {
        "officialRestaurantAirportCoveragePercent": threshold_or_default(
            min_official_airport_coverage_percent,
            default_threshold,
        ),
        "restaurantTerminalCoveragePercent": threshold_or_default(
            min_restaurant_terminal_coverage_percent,
            default_threshold,
        ),
        "cardNetworkKnownRowsPercent": threshold_or_default(
            min_card_network_coverage_percent,
            default_threshold,
        ),
    }
    actuals = {
        "officialRestaurantAirportCoveragePercent": nested_percent(
            coverage,
            "officialRestaurantAirportCoverage",
            "percent",
        ),
        "restaurantTerminalCoveragePercent": nested_percent(
            coverage,
            "officialRestaurantFieldCoverage",
            "withTerminalPercent",
        ),
        "cardNetworkKnownRowsPercent": nested_percent(
            coverage,
            "paymentAcceptanceCoverage",
            "knownCardNetworkRowsPercent",
        ),
    }
    errors = [
        f"{label} is {actuals[label]}%, below required {required}%"
        for label, required in thresholds.items()
        if actuals[label] < required
    ]
    return {
        "mode": "product" if product_readiness else "demo",
        "status": "failed" if errors else "passed",
        "thresholds": thresholds,
        "actuals": actuals,
        "errors": errors,
        "policy": "Product mode fails when coverage is below the configured thresholds; demo mode reports coverage without claiming product readiness.",
    }


def threshold_or_default(value: float | None, default: float) -> float:
    return float(value) if value is not None else default


def nested_percent(report: dict[str, object], section: str, key: str) -> float:
    value = report.get(section)
    if not isinstance(value, dict):
        return 0.0
    raw = value.get(key)
    return float(raw) if isinstance(raw, (int, float)) else 0.0

def count_present(rows: list[dict[str, object]], key: str) -> int:
    return sum(1 for row in rows if clean_match_text(row.get(key)))


def percent(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def slugify_key(value: object) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", clean_match_text(value).lower()).strip("-")
    return slug or "unknown"


def should_retry_overpass(error: object) -> bool:
    return isinstance(error, FetchHttpError) and error.status == 429


def should_stop_overpass(error: object) -> bool:
    return isinstance(error, FetchHttpError) and error.status in {403, 429}


def sleep_ms(delay_ms: int) -> None:
    time.sleep(delay_ms / 1000)


def message_from_error(error: object) -> str:
    return str(error)

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote
import json
import re
import time

from data_fetcher.http_client import FetchHttpError, fetch_text
from data_fetcher.io_utils import write_json_file

GOOGLE_PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_PLACES_PAYMENT_FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.paymentOptions"
GOOGLE_GENERIC_PAYMENT_FIELDS = {
    "acceptsCreditCards": "credit_cards",
    "acceptsDebitCards": "debit_cards",
    "acceptsNfc": "contactless",
}


def fetch_google_places_payment_options(
    restaurants: list[dict[str, object]],
    *,
    fetched_at: str,
    run_id: str,
    output_root: Path,
    api_key: str,
    user_agent: str,
    delay_ms: int,
    allowed_methods: list[str],
    max_restaurants: int | None = None,
    warnings: list[str],
    logger: Callable[[str], None],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    restaurants_to_fetch = [restaurant for restaurant in restaurants if should_query_google_places(restaurant)]
    if max_restaurants is not None:
        restaurants_to_fetch = restaurants_to_fetch[:max_restaurants]

    records: list[dict[str, object]] = []
    raw_refs: list[str] = []
    for index, restaurant in enumerate(restaurants_to_fetch, start=1):
        restaurant_id = clean_text(restaurant.get("id"))
        query = google_places_query(restaurant)
        raw_ref = str(
            Path("raw")
            / "google-places-payment"
            / f"{clean_text(restaurant.get('airportIata')).upper()}-{slugify(restaurant_id)}-{run_id}.json"
        )
        logger(
            f"[Google Places] {index}/{len(restaurants_to_fetch)} checking generic payment options for {restaurant.get('airportIata')} {restaurant.get('name')}."
        )
        try:
            payload = fetch_google_places_text_search(query, api_key=api_key, user_agent=user_agent)
            write_json_file(output_root / raw_ref, payload)
            raw_refs.append(raw_ref)
            place = exact_name_place_match(payload.get("places"), restaurant)
            if not place:
                warnings.append(
                    f"Google Places payment options skipped for {restaurant.get('id')}: no exact display-name match for {restaurant.get('name')!r}."
                )
            else:
                records.extend(
                    payment_rows_from_google_place(
                        restaurant,
                        place,
                        fetched_at=fetched_at,
                        raw_ref=raw_ref,
                        query=query,
                        allowed_methods=allowed_methods,
                    )
                )
        except Exception as error:
            warning = f"Google Places payment-options fetch failed for {restaurant.get('id')}: {message_from_error(error)}"
            warnings.append(warning)
            logger(f"[Google Places] {message_from_error(error)}")
            if should_stop_google_places(error):
                warnings.append("Stopping Google Places payment enrichment after a rate-limit or access-control response.")
                break
        sleep_ms(delay_ms)

    return records, google_places_payment_manifest_entry(
        enabled=True,
        record_count=len(records),
        raw_refs=raw_refs,
        queried_restaurant_count=len(restaurants_to_fetch),
    )


def fetch_google_places_text_search(query: str, *, api_key: str, user_agent: str) -> dict[str, object]:
    response = fetch_text(
        GOOGLE_PLACES_TEXT_SEARCH_URL,
        method="POST",
        data=json.dumps({"textQuery": query, "maxResultCount": 5, "languageCode": "en", "regionCode": "US"}).encode(
            "utf-8"
        ),
        user_agent=user_agent,
        timeout_seconds=30,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": GOOGLE_PLACES_PAYMENT_FIELD_MASK,
        },
    )
    parsed = json.loads(response.body)
    if not isinstance(parsed, dict):
        raise RuntimeError("Google Places Text Search returned a non-object JSON response")
    if parsed.get("error"):
        raise RuntimeError(f"Google Places Text Search returned error: {parsed.get('error')}")
    return parsed


def payment_rows_from_google_place(
    restaurant: dict[str, object],
    place: dict[str, object],
    *,
    fetched_at: str,
    raw_ref: str,
    query: str,
    allowed_methods: list[str],
) -> list[dict[str, object]]:
    payment_options = place.get("paymentOptions") if isinstance(place.get("paymentOptions"), dict) else {}
    if not payment_options:
        return []

    allowed = set(allowed_methods)
    rows_by_method: dict[str, dict[str, object]] = {}
    for field_name, method in GOOGLE_GENERIC_PAYMENT_FIELDS.items():
        if method not in allowed:
            continue
        value = payment_options.get(field_name)
        if isinstance(value, bool):
            rows_by_method[method] = google_payment_row(
                restaurant,
                place,
                method=method,
                status="accepted" if value else "not_accepted",
                evidence_value=f"paymentOptions.{field_name}={str(value).lower()}",
                fetched_at=fetched_at,
                raw_ref=raw_ref,
                query=query,
            )

    cash_only = payment_options.get("acceptsCashOnly")
    if cash_only is True:
        if "cash" in allowed:
            rows_by_method["cash"] = google_payment_row(
                restaurant,
                place,
                method="cash",
                status="accepted",
                evidence_value="paymentOptions.acceptsCashOnly=true",
                fetched_at=fetched_at,
                raw_ref=raw_ref,
                query=query,
            )
        for method in ["credit_cards", "debit_cards"]:
            if method in allowed:
                rows_by_method[method] = google_payment_row(
                    restaurant,
                    place,
                    method=method,
                    status="not_accepted",
                    evidence_value="paymentOptions.acceptsCashOnly=true",
                    fetched_at=fetched_at,
                    raw_ref=raw_ref,
                    query=query,
                )

    return sorted(rows_by_method.values(), key=lambda row: str(row["paymentMethod"]))


def google_payment_row(
    restaurant: dict[str, object],
    place: dict[str, object],
    *,
    method: str,
    status: str,
    evidence_value: str,
    fetched_at: str,
    raw_ref: str,
    query: str,
) -> dict[str, object]:
    restaurant_id = clean_text(restaurant.get("id"))
    restaurant_name = clean_text(restaurant.get("name"))
    airport_iata = clean_text(restaurant.get("airportIata"))
    place_id = clean_text(place.get("id"))
    return {
        "id": f"payment_acceptance:{slugify(restaurant_id)}:{method}",
        "restaurantId": restaurant_id,
        "airportIata": airport_iata,
        "restaurantName": restaurant_name,
        "paymentMethod": method,
        "acceptanceStatus": status,
        "evidenceType": "google_places_payment_options",
        "evidenceValue": evidence_value,
        "reviewedAt": None,
        "reviewedBy": None,
        "legalBasis": "Google Places API paymentOptions field under Google Maps Platform terms; generic payment methods only.",
        "source": {
            "sourceName": "Google Places API paymentOptions",
            "sourceType": "google-places-payment-options",
            "sourceUrl": f"https://www.google.com/maps/place/?q=place_id:{quote(place_id)}" if place_id else GOOGLE_PLACES_TEXT_SEARCH_URL,
            "licenseStatus": "api-key-and-google-maps-platform-terms-required",
            "attributionRequired": True,
            "fetchedAt": fetched_at,
            "rawRef": raw_ref,
            "confidenceScore": 0.72 if status == "accepted" else 0.68,
            "notes": [
                "Google Places paymentOptions exposes generic payment methods, not Visa/Mastercard/Amex network acceptance.",
                f"Text Search query: {query}",
                f"Matched Google place display name: {google_display_name(place)}",
            ],
        },
    }


def exact_name_place_match(places: object, restaurant: dict[str, object]) -> dict[str, object] | None:
    if not isinstance(places, list):
        return None
    restaurant_name = normalized_text(restaurant.get("name"))
    for place in places:
        if not isinstance(place, dict):
            continue
        if normalized_text(google_display_name(place)) == restaurant_name:
            return place
    return None


def google_places_query(restaurant: dict[str, object]) -> str:
    parts = [
        clean_text(restaurant.get("name")),
        clean_text(restaurant.get("airportIata")),
        "airport",
        clean_text(restaurant.get("terminal")),
        clean_text(restaurant.get("gate")),
    ]
    return " ".join(part for part in parts if part)


def should_query_google_places(restaurant: dict[str, object]) -> bool:
    return (
        clean_text(restaurant.get("associationScope")) == "official_airport_directory"
        and bool(clean_text(restaurant.get("id")))
        and bool(clean_text(restaurant.get("name")))
        and bool(clean_text(restaurant.get("airportIata")))
    )


def google_display_name(place: dict[str, object]) -> str:
    display = place.get("displayName")
    if isinstance(display, dict):
        return clean_text(display.get("text"))
    return clean_text(display)


def google_places_payment_manifest_entry(
    *,
    enabled: bool,
    record_count: int,
    raw_refs: list[str] | None = None,
    queried_restaurant_count: int = 0,
    missing_api_key: bool = False,
) -> dict[str, object]:
    return {
        "key": "google-places-payment-options",
        "sourceName": "Google Places API paymentOptions",
        "sourceType": "google-places-payment-options",
        "sourceUrl": GOOGLE_PLACES_TEXT_SEARCH_URL if enabled else "not-configured",
        "licenseStatus": "api-key-and-google-maps-platform-terms-required",
        "attributionRequired": True,
        "legalBasis": "Google Places API can return generic paymentOptions fields when used with a valid Google Maps Platform key and current terms.",
        "allowedUse": "Optional enrichment of generic payment methods such as credit cards, debit cards, cash-only, and NFC/contactless for exact-name place matches.",
        "restrictions": [
            "Do not infer Visa, Mastercard, American Express, Discover, JCB, UnionPay, or Diners Club acceptance from generic credit-card acceptance.",
            "Respect Google Maps Platform terms, billing, field masks, attribution, and retention restrictions before production use.",
            "Do not call this adapter without a local GOOGLE_PLACES_API_KEY; never commit API keys or raw credentials.",
        ],
        "evidenceUrls": ["https://developers.google.com/maps/documentation/places/web-service/op-overview"],
        "recordCount": record_count,
        "queriedRestaurantCount": queried_restaurant_count,
        "rawRefs": raw_refs or [],
        "skipped": (not enabled) or missing_api_key,
    }


def should_stop_google_places(error: object) -> bool:
    return isinstance(error, FetchHttpError) and error.status in {403, 429}


def sleep_ms(delay_ms: int) -> None:
    time.sleep(delay_ms / 1000)


def message_from_error(error: object) -> str:
    return str(error)


def normalized_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_text(value).lower()).strip()


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def slugify(value: object) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", clean_text(value).lower()).strip("-")
    return slug or "unknown"

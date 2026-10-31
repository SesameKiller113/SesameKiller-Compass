from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
import json
import re

ACCEPTANCE_STATUSES = {"accepted", "not_accepted"}
SOURCE_TYPE = "reviewed-payment-acceptance"


def load_reviewed_payment_acceptance(
    path: Path | None,
    restaurants: list[dict[str, object]],
    *,
    fetched_at: str,
    raw_ref: str | None,
    allowed_methods: list[str],
) -> tuple[list[dict[str, object]], dict[str, object], list[str]]:
    if path is None:
        return [], reviewed_payment_acceptance_manifest_entry(record_count=0, source_path=None), [
            "No reviewed payment acceptance file configured; network-specific restaurant card acceptance remains unknown unless a source explicitly provides it."
        ]

    if not path.exists():
        raise FileNotFoundError(f"Reviewed payment acceptance file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Reviewed payment acceptance file must contain a JSON object.")

    reviewed_at = required_text(payload, "reviewedAt", context="root")
    reviewed_by = clean_text(payload.get("reviewedBy")) or None
    legal_basis = required_text(payload, "legalBasis", context="root")
    rows_payload = payload.get("paymentAcceptance")
    if not isinstance(rows_payload, list):
        raise ValueError("Reviewed payment acceptance file must contain paymentAcceptance as a list.")

    allowed_method_set = set(allowed_methods)
    restaurants_by_id, restaurants_by_airport_name = build_restaurant_indexes(restaurants)
    rows: list[dict[str, object]] = []
    warnings: list[str] = []

    for index, item in enumerate(rows_payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"paymentAcceptance item {index} must be an object.")

        payment_method = clean_text(item.get("paymentMethod")).lower()
        if payment_method not in allowed_method_set:
            raise ValueError(f"paymentAcceptance item {index} has unsupported paymentMethod {payment_method!r}.")

        status = clean_text(item.get("acceptanceStatus") or "accepted").lower()
        if status not in ACCEPTANCE_STATUSES:
            raise ValueError(
                f"paymentAcceptance item {index} has unsupported acceptanceStatus {status!r}; use accepted or not_accepted."
            )

        source_url = required_https_url(item.get("sourceUrl"), context=f"paymentAcceptance item {index}")
        row_reviewed_at = clean_text(item.get("reviewedAt")) or reviewed_at
        row_reviewed_by = clean_text(item.get("reviewedBy")) or reviewed_by
        row_legal_basis = clean_text(item.get("legalBasis")) or legal_basis
        restaurant = match_restaurant(item, restaurants_by_id, restaurants_by_airport_name, index=index)
        restaurant_id = clean_text(restaurant.get("id"))
        airport_iata = clean_text(restaurant.get("airportIata"))
        restaurant_name = clean_text(restaurant.get("name"))

        evidence_type = clean_text(item.get("evidenceType")) or "reviewed_source"
        evidence_value = clean_text(item.get("evidenceValue")) or f"{status} in reviewed source"
        confidence = 0.95 if status == "accepted" else 0.9
        rows.append(
            {
                "id": f"payment_acceptance:{slugify(restaurant_id)}:{payment_method}",
                "restaurantId": restaurant_id,
                "airportIata": airport_iata,
                "restaurantName": restaurant_name,
                "paymentMethod": payment_method,
                "acceptanceStatus": status,
                "evidenceType": evidence_type,
                "evidenceValue": evidence_value,
                "reviewedAt": row_reviewed_at,
                "reviewedBy": row_reviewed_by,
                "legalBasis": row_legal_basis,
                "source": {
                    "sourceName": clean_text(item.get("sourceName")) or f"Reviewed payment source: {restaurant_name}",
                    "sourceType": SOURCE_TYPE,
                    "sourceUrl": source_url,
                    "licenseStatus": "manual-review-required",
                    "attributionRequired": True,
                    "fetchedAt": fetched_at,
                    "rawRef": raw_ref,
                    "confidenceScore": confidence,
                    "reviewedAt": row_reviewed_at,
                    "legalBasis": row_legal_basis,
                    "notes": [
                        "Payment acceptance is loaded only from a locally reviewed file or licensed feed export.",
                        "This row applies to one exact restaurant and one payment method; no other card networks are inferred.",
                    ],
                },
            }
        )

    if not rows:
        warnings.append("Reviewed payment acceptance file contained no paymentAcceptance records.")

    return rows, reviewed_payment_acceptance_manifest_entry(record_count=len(rows), source_path=str(path)), warnings


def build_restaurant_indexes(
    restaurants: list[dict[str, object]],
) -> tuple[dict[str, dict[str, object]], dict[tuple[str, str], list[dict[str, object]]]]:
    restaurants_by_id: dict[str, dict[str, object]] = {}
    restaurants_by_airport_name: dict[tuple[str, str], list[dict[str, object]]] = {}
    for restaurant in restaurants:
        restaurant_id = clean_text(restaurant.get("id"))
        airport_iata = clean_text(restaurant.get("airportIata")).upper()
        name_key = normalized_text(restaurant.get("name"))
        if restaurant_id:
            restaurants_by_id[restaurant_id] = restaurant
        if airport_iata and name_key:
            restaurants_by_airport_name.setdefault((airport_iata, name_key), []).append(restaurant)
    return restaurants_by_id, restaurants_by_airport_name


def match_restaurant(
    item: dict[str, object],
    restaurants_by_id: dict[str, dict[str, object]],
    restaurants_by_airport_name: dict[tuple[str, str], list[dict[str, object]]],
    *,
    index: int,
) -> dict[str, object]:
    restaurant_id = clean_text(item.get("restaurantId"))
    if restaurant_id:
        restaurant = restaurants_by_id.get(restaurant_id)
        if restaurant is None:
            raise ValueError(f"paymentAcceptance item {index} references unknown restaurantId {restaurant_id}.")
        return restaurant

    airport_iata = clean_text(item.get("airportIata")).upper()
    restaurant_name = clean_text(item.get("restaurantName"))
    if not airport_iata or not restaurant_name:
        raise ValueError(
            f"paymentAcceptance item {index} must include restaurantId, or both airportIata and restaurantName."
        )

    matches = restaurants_by_airport_name.get((airport_iata, normalized_text(restaurant_name)), [])
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(
            f"paymentAcceptance item {index} names {restaurant_name!r} at {airport_iata}, but no fetched restaurant matches exactly."
        )
    candidate_ids = ", ".join(clean_text(match.get("id")) for match in matches)
    raise ValueError(
        f"paymentAcceptance item {index} names {restaurant_name!r} at {airport_iata}, but multiple rows match. Use restaurantId; candidates: {candidate_ids}."
    )


def reviewed_payment_acceptance_manifest_entry(*, record_count: int, source_path: str | None) -> dict[str, object]:
    return {
        "key": "reviewed-payment-acceptance",
        "sourceName": "Reviewed payment acceptance input file",
        "sourceType": SOURCE_TYPE,
        "sourceUrl": source_path or "not-configured",
        "licenseStatus": "manual-review-required",
        "attributionRequired": True,
        "legalBasis": "Exact merchant payment acceptance must come from explicit merchant/airport statements, OSM payment tags, licensed processor/acquirer data, or manual review with evidence URLs.",
        "allowedUse": "Normalize reviewed restaurant-payment-method facts into JSON/CSV for local demo and product-readiness checks.",
        "restrictions": [
            "Do not infer Visa, Mastercard, Amex, or other network acceptance from generic credit-card acceptance.",
            "Do not store PAN, cardholder data, authorization records, or payment credentials.",
            "Every reviewed row must include sourceUrl, reviewedAt, and legalBasis.",
        ],
        "evidenceUrls": [
            "https://developers.google.com/maps/documentation/places/web-service/op-overview",
            "https://docs.foursquare.com/fsq-developers-places/reference/places-api-overview",
        ],
        "recordCount": record_count,
        "skipped": source_path is None,
    }


def required_text(payload: dict[str, object], key: str, *, context: str) -> str:
    value = clean_text(payload.get(key))
    if not value:
        raise ValueError(f"{context} is missing required field {key}.")
    return value


def required_https_url(value: object, *, context: str) -> str:
    url = clean_text(value)
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{context} must include an https source URL.")
    return url


def normalized_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_text(value).lower()).strip()


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def slugify(value: object) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", clean_text(value).lower()).strip("-")
    return slug or "unknown"

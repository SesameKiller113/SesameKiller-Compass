from __future__ import annotations

from urllib.parse import urlencode
import json

from data_fetcher.http_client import fetch_text
from data_fetcher.sources import DEFAULT_OVERPASS_ENDPOINT

PAYMENT_TAG_MAP = {
    "payment:visa": "visa",
    "payment:mastercard": "mastercard",
    "payment:american_express": "american_express",
    "payment:amex": "american_express",
    "payment:discover_card": "discover",
    "payment:discover": "discover",
    "payment:cash": "cash",
    "payment:credit_cards": "credit_cards",
    "payment:cards": "credit_cards",
    "payment:debit_cards": "debit_cards",
    "payment:contactless": "contactless",
    "payment:apple_pay": "apple_pay",
    "payment:google_pay": "google_pay",
}
POSITIVE_PAYMENT_VALUES = {"yes", "true", "1", "accepted", "only"}


def fetch_restaurants_for_airport(
    airport: dict[str, object],
    *,
    fetched_at: str,
    raw_ref: str,
    user_agent: str,
    endpoint: str = DEFAULT_OVERPASS_ENDPOINT,
    radius_meters: int = 1500,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    query = build_restaurant_query(airport, radius_meters=radius_meters)
    encoded = urlencode({"data": query}).encode("utf-8")
    response = fetch_text(
        endpoint,
        method="POST",
        data=encoded,
        user_agent=user_agent,
        timeout_seconds=45,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        },
    )
    raw = json.loads(response.body)
    elements = raw.get("elements") if isinstance(raw, dict) else []
    return raw, normalize_overpass_restaurants(airport, elements or [], fetched_at=fetched_at, raw_ref=raw_ref)


def build_restaurant_query(airport: dict[str, object], *, radius_meters: int) -> str:
    amenity_pattern = "restaurant|cafe|fast_food|bar|pub|food_court"
    latitude = airport["latitude"]
    longitude = airport["longitude"]
    return "\n".join(
        [
            "[out:json][timeout:25];",
            "(",
            f'  node(around:{radius_meters},{latitude},{longitude})["amenity"~"{amenity_pattern}"];',
            f'  way(around:{radius_meters},{latitude},{longitude})["amenity"~"{amenity_pattern}"];',
            f'  relation(around:{radius_meters},{latitude},{longitude})["amenity"~"{amenity_pattern}"];',
            ");",
            "out center tags;",
        ]
    )


def normalize_overpass_restaurants(
    airport: dict[str, object],
    elements: list[dict[str, object]],
    *,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    airport_iata = str(airport["iataCode"])

    for element in elements:
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        name = str(tags.get("name") or "").strip()
        if not name:
            continue

        element_type = str(element.get("type") or "")
        element_id = element.get("id")
        record_id = f"osm:{element_type}:{element_id}"
        if record_id in seen:
            continue
        seen.add(record_id)

        payment = normalize_payment_tags(tags)
        latitude, longitude = element_coordinates(element)
        records.append(
            {
                "id": record_id,
                "airportIata": airport_iata,
                "name": name,
                "category": tags.get("amenity") or "restaurant",
                "associationScope": "near_airport_radius",
                "latitude": latitude,
                "longitude": longitude,
                "terminal": None,
                "paymentMethods": payment["paymentMethods"],
                "paymentEvidence": payment["paymentEvidence"],
                "rawPaymentTags": payment["rawPaymentTags"],
                "osmType": element_type,
                "osmId": element_id,
                "source": {
                    "sourceName": "OpenStreetMap via Overpass API",
                    "sourceType": "openstreetmap-overpass",
                    "sourceUrl": f"https://www.openstreetmap.org/{element_type}/{element_id}",
                    "licenseStatus": "odbl",
                    "attributionRequired": True,
                    "fetchedAt": fetched_at,
                    "rawRef": raw_ref,
                    "confidenceScore": 0.7,
                    "notes": [
                        "OSM is crowd-sourced and licensed under ODbL.",
                        f"Associated with {airport_iata} by coordinate radius, not by official airport tenant confirmation.",
                        "Payment methods are copied only from explicit OSM payment tags; missing tags are exported as unknown.",
                    ],
                },
            }
        )

    return sorted(records, key=lambda record: str(record["name"]))


def normalize_payment_tags(tags: dict[str, object]) -> dict[str, object]:
    raw_payment_tags = {
        key: str(value)
        for key, value in tags.items()
        if key.startswith("payment:")
    }
    methods = {
        method
        for tag_name, method in PAYMENT_TAG_MAP.items()
        if str(tags.get(tag_name) or "").lower() in POSITIVE_PAYMENT_VALUES
    }
    return {
        "paymentMethods": sorted(methods) if methods else ["unknown"],
        "paymentEvidence": "explicit_source_tag" if raw_payment_tags else "not_provided_by_source",
        "rawPaymentTags": raw_payment_tags,
    }


def element_coordinates(element: dict[str, object]) -> tuple[float | None, float | None]:
    center = element.get("center") if isinstance(element.get("center"), dict) else {}
    latitude = element.get("lat", center.get("lat"))
    longitude = element.get("lon", center.get("lon"))
    return coerce_float(latitude), coerce_float(longitude)


def coerce_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

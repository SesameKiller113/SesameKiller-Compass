from __future__ import annotations

import json
from urllib.parse import urlencode

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
RESTAURANT_AMENITIES = {"restaurant", "cafe", "fast_food", "bar", "pub", "food_court"}
OSM_ASSOCIATION_MODES = {"area-first", "area-only", "radius-only"}


def fetch_restaurants_for_airport(
    airport: dict[str, object],
    *,
    fetched_at: str,
    raw_ref: str,
    user_agent: str,
    endpoint: str = DEFAULT_OVERPASS_ENDPOINT,
    radius_meters: int = 1500,
    association_mode: str = "area-first",
) -> tuple[dict[str, object], list[dict[str, object]]]:
    if association_mode not in OSM_ASSOCIATION_MODES:
        raise ValueError(f"association_mode must be one of {sorted(OSM_ASSOCIATION_MODES)}")

    if association_mode == "radius-only":
        raw = fetch_overpass_json(
            build_radius_restaurant_query(airport, radius_meters=radius_meters),
            endpoint=endpoint,
            user_agent=user_agent,
        )
        return raw, normalize_overpass_restaurants(
            airport,
            raw.get("elements", []) if isinstance(raw.get("elements"), list) else [],
            fetched_at=fetched_at,
            raw_ref=raw_ref,
            association_scope="near_airport_radius",
            association_note=f"Associated with {airport['iataCode']} by coordinate radius, not by official airport tenant confirmation.",
            confidence_score=0.7,
        )

    area_raw = fetch_overpass_json(
        build_airport_area_restaurant_query(airport),
        endpoint=endpoint,
        user_agent=user_agent,
    )
    area_restaurants = normalize_overpass_restaurants(
        airport,
        area_raw.get("elements", []) if isinstance(area_raw.get("elements"), list) else [],
        fetched_at=fetched_at,
        raw_ref=raw_ref,
        association_scope="inside_osm_airport_area",
        association_note=(
            f"Associated with {airport['iataCode']} by OSM aerodrome area tags, not by official airport tenant confirmation."
        ),
        confidence_score=0.78,
    )
    if area_restaurants or association_mode == "area-only":
        return area_raw, area_restaurants

    radius_raw = fetch_overpass_json(
        build_radius_restaurant_query(airport, radius_meters=radius_meters),
        endpoint=endpoint,
        user_agent=user_agent,
    )
    radius_restaurants = normalize_overpass_restaurants(
        airport,
        radius_raw.get("elements", []) if isinstance(radius_raw.get("elements"), list) else [],
        fetched_at=fetched_at,
        raw_ref=raw_ref,
        association_scope="near_airport_radius",
        association_note=f"Associated with {airport['iataCode']} by coordinate radius fallback, not by official airport tenant confirmation.",
        confidence_score=0.65,
    )
    return {
        "strategy": "area-first",
        "areaQuery": area_raw,
        "radiusFallbackQuery": radius_raw,
        "selectedAssociationScope": "near_airport_radius",
    }, radius_restaurants


def fetch_overpass_json(query: str, *, endpoint: str, user_agent: str) -> dict[str, object]:
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
    return raw if isinstance(raw, dict) else {}


def build_radius_restaurant_query(airport: dict[str, object], *, radius_meters: int) -> str:
    amenity_pattern = restaurant_amenity_pattern()
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


def build_airport_area_restaurant_query(airport: dict[str, object]) -> str:
    amenity_pattern = restaurant_amenity_pattern()
    iata_code = str(airport.get("iataCode") or "").upper()
    ident = str(airport.get("ident") or "").upper()
    area_filters = [
        f'area["aeroway"="aerodrome"]["iata"="{iata_code}"];',
        f'area["aeroway"="aerodrome"]["iata_code"="{iata_code}"];',
        f'area["aeroway"="aerodrome"]["ref"="{iata_code}"];',
    ]
    if ident:
        area_filters.extend(
            [
                f'area["aeroway"="aerodrome"]["icao"="{ident}"];',
                f'area["aeroway"="aerodrome"]["icao_code"="{ident}"];',
                f'area["aeroway"="aerodrome"]["ref"="{ident}"];',
            ]
        )
    return "\n".join(
        [
            "[out:json][timeout:25];",
            "(",
            *[f"  {line}" for line in area_filters],
            ")->.airportAreas;",
            "(",
            f'  node(area.airportAreas)["amenity"~"{amenity_pattern}"];',
            f'  way(area.airportAreas)["amenity"~"{amenity_pattern}"];',
            f'  relation(area.airportAreas)["amenity"~"{amenity_pattern}"];',
            ");",
            "out center tags;",
        ]
    )


def restaurant_amenity_pattern() -> str:
    return "|".join(sorted(RESTAURANT_AMENITIES))


def normalize_overpass_restaurants(
    airport: dict[str, object],
    elements: list[dict[str, object]],
    *,
    fetched_at: str,
    raw_ref: str,
    association_scope: str = "near_airport_radius",
    association_note: str | None = None,
    confidence_score: float = 0.7,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    airport_iata = str(airport["iataCode"])

    for element in elements:
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        amenity = str(tags.get("amenity") or "")
        if amenity not in RESTAURANT_AMENITIES:
            continue
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
                "category": amenity,
                "associationScope": association_scope,
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
                    "confidenceScore": confidence_score,
                    "notes": [
                        "OSM is crowd-sourced and licensed under ODbL.",
                        association_note
                        or f"Associated with {airport_iata} by coordinate radius, not by official airport tenant confirmation.",
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

from __future__ import annotations


def validate_dataset(
    *,
    airports: list[dict[str, object]],
    restaurants: list[dict[str, object]],
    card_products: list[dict[str, object]],
    benefits: list[dict[str, object]],
    payment_acceptance: list[dict[str, object]] | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    airport_codes = {str(airport.get("iataCode")) for airport in airports}
    restaurant_ids = {str(restaurant.get("id")) for restaurant in restaurants}
    card_product_ids = {str(card_product.get("id")) for card_product in card_products}
    osm_associated_restaurants = 0
    payment_acceptance = payment_acceptance or []

    for airport in airports:
        label = f"airport {airport.get('iataCode')}"
        validate_source(label, airport.get("source"), errors)
        iata_code = str(airport.get("iataCode") or "")
        if len(iata_code) != 3:
            errors.append(f"Airport {airport.get('id')} has invalid IATA code.")

    for restaurant in restaurants:
        label = f"restaurant {restaurant.get('id')}"
        validate_source(label, restaurant.get("source"), errors)
        airport_iata = str(restaurant.get("airportIata") or "")
        if airport_iata not in airport_codes:
            errors.append(f"Restaurant {restaurant.get('id')} references unknown airport {airport_iata}.")
        payment_methods = restaurant.get("paymentMethods")
        if not isinstance(payment_methods, list) or not payment_methods:
            errors.append(
                f"Restaurant {restaurant.get('id')} has no payment method marker; use unknown when the source is silent."
            )
        if restaurant.get("associationScope") in {"inside_osm_airport_area", "near_airport_radius"}:
            osm_associated_restaurants += 1
        if restaurant.get("associationScope") == "official_airport_directory" and not restaurant.get("officialSourcePath"):
            errors.append(f"Official restaurant {restaurant.get('id')} is missing officialSourcePath.")

    if osm_associated_restaurants:
        warnings.append(
            f"{osm_associated_restaurants} restaurant records are OSM-associated; do not present them as official terminal inventory."
        )

    for payment_row in payment_acceptance:
        label = f"payment acceptance {payment_row.get('id')}"
        validate_source(label, payment_row.get("source"), errors)
        restaurant_id = str(payment_row.get("restaurantId") or "")
        if restaurant_id not in restaurant_ids:
            errors.append(f"Payment acceptance {payment_row.get('id')} references unknown restaurant {restaurant_id}.")
        airport_iata = str(payment_row.get("airportIata") or "")
        if airport_iata not in airport_codes:
            errors.append(f"Payment acceptance {payment_row.get('id')} references unknown airport {airport_iata}.")
        status = str(payment_row.get("acceptanceStatus") or "")
        if status not in {"accepted", "not_accepted", "unknown"}:
            errors.append(f"Payment acceptance {payment_row.get('id')} has unsupported status {status}.")
        if status in {"accepted", "not_accepted"}:
            if payment_row.get("evidenceType") == "not_provided_by_source":
                errors.append(f"Payment acceptance {payment_row.get('id')} is known but has no evidenceType.")
            require_payment_review_metadata(payment_row, label, errors)

    for card_product in card_products:
        validate_source(f"card product {card_product.get('id')}", card_product.get("source"), errors)
        require_review_metadata(card_product, f"card product {card_product.get('id')}", errors)

    for benefit in benefits:
        validate_source(f"benefit {benefit.get('id')}", benefit.get("source"), errors)
        require_review_metadata(benefit, f"benefit {benefit.get('id')}", errors)
        card_product_id = str(benefit.get("cardProductId") or "")
        if card_product_id not in card_product_ids:
            errors.append(f"Benefit {benefit.get('id')} references unknown card product {card_product_id}.")
        airport_iata = str(benefit.get("airportIata") or "")
        if airport_iata and airport_iata not in airport_codes:
            errors.append(f"Benefit {benefit.get('id')} references unknown airport {airport_iata}.")
        if not benefit.get("termsUrl"):
            errors.append(f"Benefit {benefit.get('id')} is missing termsUrl.")
        validate_restaurant_match(benefit, errors)
        source = benefit.get("source") if isinstance(benefit.get("source"), dict) else {}
        if source.get("sourceType") == "reviewed-card-benefit":
            warnings.append(f"Benefit {benefit.get('id')} is manually reviewed; re-review before production use.")

    return errors, warnings


RESTAURANT_MATCH_ERROR_STATUSES = {
    "unmatched_restaurant_id",
    "unmatched_restaurant_name",
    "ambiguous_restaurant_name",
    "missing_airport_for_restaurant_name",
    "restaurant_airport_mismatch",
}


def validate_restaurant_match(benefit: dict[str, object], errors: list[str]) -> None:
    has_restaurant_reference = bool(benefit.get("restaurantId") or benefit.get("restaurantName"))
    if not has_restaurant_reference:
        return

    status = str(benefit.get("restaurantMatchStatus") or "")
    if not status:
        errors.append(f"Benefit {benefit.get('id')} references a restaurant but was not match-checked.")
    elif status in RESTAURANT_MATCH_ERROR_STATUSES:
        errors.append(f"Benefit {benefit.get('id')} has unresolved restaurant match status {status}.")
    elif status not in {"matched_by_id", "matched_by_exact_name"}:
        errors.append(f"Benefit {benefit.get('id')} has unsupported restaurant match status {status}.")


def validate_source(label: str, source: object, errors: list[str]) -> None:
    if not isinstance(source, dict):
        errors.append(f"{label} is missing source metadata.")
        return

    if not source.get("sourceUrl"):
        errors.append(f"{label} is missing sourceUrl.")
    if not source.get("fetchedAt"):
        errors.append(f"{label} is missing fetchedAt.")

    confidence = source.get("confidenceScore")
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        errors.append(f"{label} has invalid confidenceScore.")


def require_payment_review_metadata(row: dict[str, object], label: str, errors: list[str]) -> None:
    source = row.get("source") if isinstance(row.get("source"), dict) else {}
    if source.get("sourceType") != "reviewed-payment-acceptance":
        return
    for key in ["reviewedAt", "legalBasis"]:
        if not row.get(key):
            errors.append(f"{label} is missing {key}.")


def require_review_metadata(row: dict[str, object], label: str, errors: list[str]) -> None:
    source = row.get("source") if isinstance(row.get("source"), dict) else {}
    if source.get("sourceType") != "reviewed-card-benefit":
        return
    for key in ["reviewedAt", "legalBasis"]:
        if not row.get(key):
            errors.append(f"{label} is missing {key}.")

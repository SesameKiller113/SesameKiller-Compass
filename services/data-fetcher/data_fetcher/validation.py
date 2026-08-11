from __future__ import annotations


def validate_dataset(
    *,
    airports: list[dict[str, object]],
    restaurants: list[dict[str, object]],
    card_products: list[dict[str, object]],
    benefits: list[dict[str, object]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    airport_codes = {str(airport.get("iataCode")) for airport in airports}
    radius_associated_restaurants = 0

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
        if restaurant.get("associationScope") == "near_airport_radius":
            radius_associated_restaurants += 1

    if radius_associated_restaurants:
        warnings.append(
            f"{radius_associated_restaurants} restaurant records are radius-associated; do not present them as official terminal inventory."
        )

    for card_product in card_products:
        validate_source(f"card product {card_product.get('id')}", card_product.get("source"), errors)

    for benefit in benefits:
        validate_source(f"benefit {benefit.get('id')}", benefit.get("source"), errors)
        source = benefit.get("source") if isinstance(benefit.get("source"), dict) else {}
        if source.get("sourceType") == "manual":
            warnings.append(f"Benefit {benefit.get('id')} is manual; production needs issuer/API/legal review.")

    return errors, warnings


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

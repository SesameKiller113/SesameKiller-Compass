from __future__ import annotations

import unittest

from data_fetcher.validation import validate_dataset

SOURCE = {
    "sourceName": "fixture",
    "sourceType": "manual",
    "sourceUrl": "https://example.test/source",
    "licenseStatus": "unknown",
    "attributionRequired": False,
    "fetchedAt": "2026-08-11T00:00:00Z",
    "confidenceScore": 1,
    "notes": [],
}
AIRPORT = {
    "id": "airport:JFK",
    "iataCode": "JFK",
    "ident": "KJFK",
    "type": "large_airport",
    "name": "John F Kennedy International Airport",
    "municipality": "New York",
    "regionCode": "US-NY",
    "countryCode": "US",
    "latitude": 40.6413,
    "longitude": -73.7781,
    "scheduledService": True,
    "officialWebsite": "https://www.jfkairport.com/",
    "source": SOURCE,
}


def restaurant(record_id: str) -> dict[str, object]:
    return {
        "id": record_id,
        "airportIata": "JFK",
        "name": record_id,
        "category": "restaurant",
        "associationScope": "near_airport_radius",
        "latitude": 40.64,
        "longitude": -73.77,
        "terminal": None,
        "paymentMethods": ["unknown"],
        "paymentEvidence": "not_provided_by_source",
        "rawPaymentTags": {},
        "source": SOURCE,
    }


class ValidationTest(unittest.TestCase):
    def test_osm_association_warnings_are_aggregated(self) -> None:
        errors, warnings = validate_dataset(
            airports=[AIRPORT],
            restaurants=[restaurant("one"), restaurant("two")],
            card_products=[],
            benefits=[],
        )

        self.assertEqual(errors, [])
        self.assertEqual(
            warnings,
            ["2 restaurant records are OSM-associated; do not present them as official terminal inventory."],
        )


    def test_restaurant_specific_benefit_must_have_resolved_match(self) -> None:
        card_product = {
            "id": "card:test:visa",
            "network": "visa",
            "issuer": "Test Bank",
            "productName": "Test Visa",
            "termsUrl": "https://issuer.example/terms",
            "reviewedAt": "2026-08-11",
            "legalBasis": "Manual official terms review.",
            "source": {**SOURCE, "sourceType": "reviewed-card-benefit"},
        }
        benefit = {
            "id": "benefit:test:missing-restaurant",
            "cardProductId": "card:test:visa",
            "airportIata": "JFK",
            "restaurantId": "official:jfk:panynj:missing",
            "benefitType": "dining_credit",
            "termsUrl": "https://issuer.example/terms",
            "reviewedAt": "2026-08-11",
            "legalBasis": "Manual official terms review.",
            "restaurantMatchStatus": "unmatched_restaurant_id",
            "source": {**SOURCE, "sourceType": "reviewed-card-benefit"},
        }

        errors, _warnings = validate_dataset(
            airports=[AIRPORT],
            restaurants=[],
            card_products=[card_product],
            benefits=[benefit],
        )

        self.assertIn(
            "Benefit benefit:test:missing-restaurant has unresolved restaurant match status unmatched_restaurant_id.",
            errors,
        )


if __name__ == "__main__":
    unittest.main()

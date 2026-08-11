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
    def test_radius_association_warnings_are_aggregated(self) -> None:
        errors, warnings = validate_dataset(
            airports=[AIRPORT],
            restaurants=[restaurant("one"), restaurant("two")],
            card_products=[],
            benefits=[],
        )

        self.assertEqual(errors, [])
        self.assertEqual(
            warnings,
            ["2 restaurant records are radius-associated; do not present them as official terminal inventory."],
        )


if __name__ == "__main__":
    unittest.main()

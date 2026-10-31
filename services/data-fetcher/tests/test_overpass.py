from __future__ import annotations

import unittest

from data_fetcher.adapters.overpass import (
    build_airport_area_restaurant_query,
    normalize_overpass_restaurants,
    normalize_payment_tags,
)

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
    "source": {
        "sourceName": "fixture",
        "sourceType": "manual",
        "sourceUrl": "https://example.test",
        "licenseStatus": "unknown",
        "attributionRequired": False,
        "fetchedAt": "2026-08-11T00:00:00Z",
        "confidenceScore": 1,
        "notes": [],
    },
}


class OverpassTest(unittest.TestCase):
    def test_missing_payment_tags_are_unknown(self) -> None:
        self.assertEqual(
            normalize_payment_tags({"name": "Cafe"}),
            {
                "paymentMethods": ["unknown"],
                "paymentEvidence": "not_provided_by_source",
                "rawPaymentTags": {},
            },
        )

    def test_only_positive_payment_tags_become_methods(self) -> None:
        self.assertEqual(
            normalize_payment_tags(
                {
                    "payment:visa": "yes",
                    "payment:mastercard": "no",
                    "payment:cash": "accepted",
                }
            ),
            {
                "paymentMethods": ["cash", "visa"],
                "paymentEvidence": "explicit_source_tag",
                "rawPaymentTags": {
                    "payment:visa": "yes",
                    "payment:mastercard": "no",
                    "payment:cash": "accepted",
                },
            },
        )


    def test_area_query_uses_airport_iata_and_ident(self) -> None:
        query = build_airport_area_restaurant_query(AIRPORT)

        self.assertIn('["iata"="JFK"]', query)
        self.assertIn('["icao"="KJFK"]', query)
        self.assertIn('node(area.airportAreas)', query)

    def test_normalizer_filters_non_restaurant_elements(self) -> None:
        records = normalize_overpass_restaurants(
            AIRPORT,
            [
                {
                    "type": "way",
                    "id": 1,
                    "center": {"lat": 40.64, "lon": -73.77},
                    "tags": {"aeroway": "aerodrome", "name": "JFK Airport"},
                },
                {
                    "type": "node",
                    "id": 2,
                    "lat": 40.64,
                    "lon": -73.77,
                    "tags": {"amenity": "cafe", "name": "Terminal Cafe"},
                },
            ],
            fetched_at="2026-08-11T00:00:00Z",
            raw_ref="raw/overpass/JFK.json",
            association_scope="inside_osm_airport_area",
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "Terminal Cafe")
        self.assertEqual(records[0]["associationScope"], "inside_osm_airport_area")

    def test_restaurant_records_keep_odbl_provenance(self) -> None:
        records = normalize_overpass_restaurants(
            AIRPORT,
            [
                {
                    "type": "node",
                    "id": 123,
                    "lat": 40.64,
                    "lon": -73.77,
                    "tags": {
                        "amenity": "restaurant",
                        "name": "Source Backed Cafe",
                        "payment:visa": "yes",
                    },
                }
            ],
            fetched_at="2026-08-11T00:00:00Z",
            raw_ref="raw/overpass/JFK.json",
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["associationScope"], "near_airport_radius")
        self.assertEqual(records[0]["paymentMethods"], ["visa"])
        self.assertEqual(records[0]["source"]["licenseStatus"], "odbl")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from data_fetcher.pipeline import (
    PAYMENT_ACCEPTANCE_METHODS,
    build_coverage_report,
    build_payment_acceptance_records,
    build_readiness_report,
    merge_payment_acceptance_records,
)

SOURCE = {
    "sourceName": "fixture",
    "sourceType": "openstreetmap-overpass",
    "sourceUrl": "https://www.openstreetmap.org/node/1",
    "licenseStatus": "odbl",
    "attributionRequired": True,
    "fetchedAt": "2026-08-11T00:00:00Z",
    "rawRef": "raw/test.json",
    "confidenceScore": 0.7,
    "notes": [],
}


def restaurant(**overrides: object) -> dict[str, object]:
    row = {
        "id": "osm:node:1",
        "airportIata": "JFK",
        "name": "Source Cafe",
        "associationScope": "near_airport_radius",
        "terminal": None,
        "gate": None,
        "latitude": 40.0,
        "longitude": -73.0,
        "paymentMethods": ["visa"],
        "paymentEvidence": "explicit_source_tag",
        "rawPaymentTags": {"payment:visa": "yes"},
        "source": SOURCE,
    }
    row.update(overrides)
    return row


class PipelineTest(unittest.TestCase):
    def test_payment_acceptance_records_do_not_infer_missing_networks(self) -> None:
        records = build_payment_acceptance_records([restaurant()])
        self.assertEqual(len(records), len(PAYMENT_ACCEPTANCE_METHODS))
        by_method = {record["paymentMethod"]: record for record in records}
        self.assertEqual(by_method["visa"]["acceptanceStatus"], "accepted")
        self.assertEqual(by_method["visa"]["evidenceValue"], "payment:visa=yes")
        self.assertEqual(by_method["american_express"]["acceptanceStatus"], "unknown")
        self.assertEqual(by_method["american_express"]["source"]["confidenceScore"], 0.0)


    def test_reviewed_payment_acceptance_overrides_exact_method_only(self) -> None:
        base_records = build_payment_acceptance_records([restaurant()])
        reviewed_record = {
            **next(record for record in base_records if record["paymentMethod"] == "american_express"),
            "acceptanceStatus": "accepted",
            "evidenceType": "reviewed_source",
            "evidenceValue": "merchant statement",
            "reviewedAt": "2026-08-11",
            "legalBasis": "Manual official source review.",
            "source": {**SOURCE, "sourceType": "reviewed-payment-acceptance", "confidenceScore": 0.95},
        }
        merged = merge_payment_acceptance_records(base_records, [reviewed_record])
        by_method = {record["paymentMethod"]: record for record in merged}
        self.assertEqual(by_method["american_express"]["acceptanceStatus"], "accepted")
        self.assertEqual(by_method["mastercard"]["acceptanceStatus"], "unknown")

    def test_product_readiness_fails_below_real_coverage(self) -> None:
        restaurants = [restaurant(associationScope="official_airport_directory", terminal="Terminal 1", gate="Gate 1")]
        payment_acceptance = build_payment_acceptance_records(restaurants)
        report = build_coverage_report(
            airports=[{"iataCode": "JFK"}, {"iataCode": "LAX"}],
            restaurants=restaurants,
            payment_acceptance=payment_acceptance,
            restaurant_evidence=[{"airportIata": "JFK", "status": "ok"}, {"airportIata": "LAX", "status": "unsupported"}],
        )
        readiness = build_readiness_report(
            coverage=report,
            product_readiness=True,
            min_official_airport_coverage_percent=None,
            min_restaurant_terminal_coverage_percent=None,
            min_card_network_coverage_percent=None,
        )
        self.assertEqual(readiness["status"], "failed")
        self.assertTrue(any("officialRestaurantAirportCoveragePercent" in error for error in readiness["errors"]))
        self.assertTrue(any("cardNetworkKnownRowsPercent" in error for error in readiness["errors"]))

    def test_coverage_report_separates_airport_and_payment_coverage(self) -> None:
        restaurants = [restaurant(associationScope="official_airport_directory", terminal="Terminal 1", gate="Gate 1")]
        payment_acceptance = build_payment_acceptance_records(restaurants)
        report = build_coverage_report(
            airports=[{"iataCode": "JFK"}, {"iataCode": "LAX"}],
            restaurants=restaurants,
            payment_acceptance=payment_acceptance,
            restaurant_evidence=[{"airportIata": "JFK", "status": "ok"}, {"airportIata": "LAX", "status": "unsupported"}],
        )
        self.assertEqual(report["officialRestaurantAirportCoverage"]["percent"], 50.0)
        self.assertEqual(report["restaurantDiscoveryAirportCoverage"]["percent"], 50.0)
        self.assertEqual(report["officialRestaurantFieldCoverage"]["withGatePercent"], 100.0)
        self.assertLess(report["paymentAcceptanceCoverage"]["acceptedRowsPercent"], 100.0)

    def test_coverage_report_counts_osm_discovery_separately(self) -> None:
        restaurants = [
            restaurant(airportIata="JFK", associationScope="inside_osm_airport_area"),
            restaurant(id="osm:node:2", airportIata="LAX", associationScope="near_airport_radius"),
        ]
        payment_acceptance = build_payment_acceptance_records(restaurants)
        report = build_coverage_report(
            airports=[{"iataCode": "JFK"}, {"iataCode": "LAX"}, {"iataCode": "SFO"}],
            restaurants=restaurants,
            payment_acceptance=payment_acceptance,
            restaurant_evidence=[],
        )

        self.assertEqual(report["officialRestaurantAirportCoverage"]["percent"], 0.0)
        self.assertEqual(report["restaurantDiscoveryAirportCoverage"]["percent"], 66.67)
        self.assertEqual(report["osmRestaurantCoverage"]["percent"], 66.67)
        self.assertEqual(report["osmRestaurantCoverage"]["insideAirportAreaRestaurantCount"], 1)
        self.assertEqual(report["osmRestaurantCoverage"]["radiusFallbackRestaurantCount"], 1)


if __name__ == "__main__":
    unittest.main()

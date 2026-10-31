from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from data_fetcher.adapters.card_benefits import load_reviewed_card_benefits
from data_fetcher.pipeline import resolve_benefit_restaurant_matches, web_evidence_warnings


class CardBenefitTests(unittest.TestCase):
    def test_load_reviewed_card_benefits(self) -> None:
        payload = {
            "reviewedAt": "2026-08-11",
            "reviewedBy": "Tester",
            "legalBasis": "Manual official terms review.",
            "cardProducts": [
                {
                    "id": "card:test:visa",
                    "network": "visa",
                    "issuer": "Test Bank",
                    "productName": "Test Visa",
                    "sourceUrl": "https://issuer.example/card",
                    "termsUrl": "https://issuer.example/card/terms",
                    "benefits": [
                        {
                            "benefitType": "dining_credit",
                            "description": "Reviewed dining credit.",
                            "restaurantId": "official:jfk:panynj:42",
                            "termsUrl": "https://issuer.example/card/terms",
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "benefits.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            cards, benefits, manifest, warnings = load_reviewed_card_benefits(
                path,
                fetched_at="2026-08-11T00:00:00Z",
                raw_ref="raw/card-benefits/test.json",
            )
        self.assertEqual(len(cards), 1)
        self.assertEqual(len(benefits), 1)
        self.assertEqual(benefits[0]["cardProductId"], "card:test:visa")
        self.assertEqual(benefits[0]["source"]["sourceType"], "reviewed-card-benefit")
        self.assertEqual(manifest["recordCount"], 1)
        self.assertEqual(warnings, [])



    def test_web_evidence_warnings_surface_non_fetch_statuses(self) -> None:
        warnings = web_evidence_warnings(
            [
                {"airportIata": "JFK", "status": "fetched", "notes": []},
                {"airportIata": "DEN", "status": "skipped_robots_unavailable", "notes": ["robots unavailable"]},
            ]
        )

        self.assertEqual(warnings, ["Official web evidence for DEN skipped_robots_unavailable: robots unavailable"])

    def test_web_evidence_warnings_trim_html_previews(self) -> None:
        warnings = web_evidence_warnings(
            [
                {
                    "airportIata": "DEN",
                    "status": "fetch_failed",
                    "notes": ["Fetch failed after robots.txt allowed the path: GET/POST https://example.test failed with HTTP 403: <!DOCTYPE html><html>noisy</html>"],
                }
            ]
        )

        self.assertEqual(
            warnings,
            ["Official web evidence for DEN fetch_failed: Fetch failed after robots.txt allowed the path: GET/POST https://example.test failed with HTTP 403."],
        )

    def test_resolves_reviewed_benefit_by_exact_restaurant_name(self) -> None:
        restaurants = [
            {
                "id": "official:jfk:panynj:4004714",
                "airportIata": "JFK",
                "name": "Air Bar",
                "associationScope": "official_airport_directory",
                "source": {"sourceUrl": "https://www.jfkairport.com/dine-shop-relax/food/detail?poiId=4004714"},
            }
        ]
        benefits = [
            {
                "id": "benefit:test:air-bar",
                "airportIata": "JFK",
                "restaurantName": "air bar",
            }
        ]

        warnings = resolve_benefit_restaurant_matches(benefits, restaurants)

        self.assertEqual(warnings, [])
        self.assertEqual(benefits[0]["restaurantId"], "official:jfk:panynj:4004714")
        self.assertEqual(benefits[0]["restaurantName"], "Air Bar")
        self.assertEqual(benefits[0]["restaurantMatchStatus"], "matched_by_exact_name")
        self.assertEqual(benefits[0]["matchedRestaurantAssociationScope"], "official_airport_directory")

    def test_unmatched_restaurant_id_is_marked(self) -> None:
        benefits = [{"id": "benefit:test:missing", "airportIata": "JFK", "restaurantId": "official:jfk:panynj:missing"}]

        warnings = resolve_benefit_restaurant_matches(benefits, restaurants=[])

        self.assertEqual(benefits[0]["restaurantMatchStatus"], "unmatched_restaurant_id")
        self.assertEqual(benefits[0]["restaurantMatchConfidence"], 0)
        self.assertIn("not in this run", warnings[0])

    def test_rejects_missing_https_source(self) -> None:
        payload = {
            "reviewedAt": "2026-08-11",
            "legalBasis": "Manual official terms review.",
            "cardProducts": [
                {
                    "network": "visa",
                    "issuer": "Test Bank",
                    "productName": "Test Visa",
                    "sourceUrl": "http://issuer.example/card",
                    "termsUrl": "https://issuer.example/card/terms",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "benefits.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_reviewed_card_benefits(path, fetched_at="2026-08-11T00:00:00Z", raw_ref=None)


if __name__ == "__main__":
    unittest.main()

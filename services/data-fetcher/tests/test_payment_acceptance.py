from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from data_fetcher.adapters.payment_acceptance import load_reviewed_payment_acceptance
from data_fetcher.pipeline import PAYMENT_ACCEPTANCE_METHODS


RESTAURANT = {
    "id": "official:jfk:panynj:42",
    "airportIata": "JFK",
    "name": "Example Bagels",
}


class ReviewedPaymentAcceptanceTest(unittest.TestCase):
    def test_load_reviewed_payment_acceptance_matches_by_restaurant_id(self) -> None:
        payload = {
            "reviewedAt": "2026-08-11",
            "reviewedBy": "qa",
            "legalBasis": "Manual official source review.",
            "paymentAcceptance": [
                {
                    "restaurantId": "official:jfk:panynj:42",
                    "paymentMethod": "american_express",
                    "acceptanceStatus": "accepted",
                    "sourceUrl": "https://merchant.example/payments",
                    "evidenceType": "official_merchant_statement",
                    "evidenceValue": "Amex accepted at this location.",
                }
            ],
        }
        path = write_temp_json(payload)
        try:
            rows, manifest, warnings = load_reviewed_payment_acceptance(
                path,
                [RESTAURANT],
                fetched_at="2026-08-11T00:00:00Z",
                raw_ref="raw/payment-acceptance/test.json",
                allowed_methods=PAYMENT_ACCEPTANCE_METHODS,
            )
        finally:
            path.unlink()

        self.assertEqual(warnings, [])
        self.assertEqual(manifest["recordCount"], 1)
        self.assertEqual(rows[0]["restaurantId"], "official:jfk:panynj:42")
        self.assertEqual(rows[0]["paymentMethod"], "american_express")
        self.assertEqual(rows[0]["acceptanceStatus"], "accepted")
        self.assertEqual(rows[0]["source"]["sourceType"], "reviewed-payment-acceptance")

    def test_load_reviewed_payment_acceptance_rejects_unmatched_restaurant(self) -> None:
        payload = {
            "reviewedAt": "2026-08-11",
            "legalBasis": "Manual official source review.",
            "paymentAcceptance": [
                {
                    "airportIata": "JFK",
                    "restaurantName": "Missing Cafe",
                    "paymentMethod": "visa",
                    "sourceUrl": "https://merchant.example/payments",
                }
            ],
        }
        path = write_temp_json(payload)
        try:
            with self.assertRaisesRegex(ValueError, "no fetched restaurant matches"):
                load_reviewed_payment_acceptance(
                    path,
                    [RESTAURANT],
                    fetched_at="2026-08-11T00:00:00Z",
                    raw_ref="raw/payment-acceptance/test.json",
                    allowed_methods=PAYMENT_ACCEPTANCE_METHODS,
                )
        finally:
            path.unlink()


def write_temp_json(payload: dict[str, object]) -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    with handle:
        json.dump(payload, handle)
    return Path(handle.name)


if __name__ == "__main__":
    unittest.main()

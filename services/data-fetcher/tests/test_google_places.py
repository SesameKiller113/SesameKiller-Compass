from __future__ import annotations

import unittest

from data_fetcher.adapters.google_places import (
    exact_name_place_match,
    google_places_query,
    payment_rows_from_google_place,
)
from data_fetcher.pipeline import PAYMENT_ACCEPTANCE_METHODS


RESTAURANT = {
    "id": "official:jfk:panynj:42",
    "airportIata": "JFK",
    "name": "Example Bagels",
    "associationScope": "official_airport_directory",
    "terminal": "Terminal 4",
    "gate": "Gate B22",
}


class GooglePlacesPaymentOptionsTest(unittest.TestCase):
    def test_payment_options_create_generic_rows_only(self) -> None:
        place = {
            "id": "places/example",
            "displayName": {"text": "Example Bagels"},
            "paymentOptions": {
                "acceptsCreditCards": True,
                "acceptsDebitCards": False,
                "acceptsNfc": True,
                "acceptsCashOnly": False,
            },
        }
        rows = payment_rows_from_google_place(
            RESTAURANT,
            place,
            fetched_at="2026-08-11T00:00:00Z",
            raw_ref="raw/google.json",
            query=google_places_query(RESTAURANT),
            allowed_methods=PAYMENT_ACCEPTANCE_METHODS,
        )
        by_method = {row["paymentMethod"]: row for row in rows}
        self.assertEqual(set(by_method), {"contactless", "credit_cards", "debit_cards"})
        self.assertEqual(by_method["credit_cards"]["acceptanceStatus"], "accepted")
        self.assertEqual(by_method["debit_cards"]["acceptanceStatus"], "not_accepted")
        self.assertNotIn("american_express", by_method)
        self.assertNotIn("visa", by_method)

    def test_cash_only_marks_cards_not_accepted_without_network_inference(self) -> None:
        place = {
            "id": "places/cash",
            "displayName": {"text": "Example Bagels"},
            "paymentOptions": {"acceptsCashOnly": True},
        }
        rows = payment_rows_from_google_place(
            RESTAURANT,
            place,
            fetched_at="2026-08-11T00:00:00Z",
            raw_ref="raw/google.json",
            query="Example Bagels JFK airport",
            allowed_methods=PAYMENT_ACCEPTANCE_METHODS,
        )
        by_method = {row["paymentMethod"]: row for row in rows}
        self.assertEqual(by_method["cash"]["acceptanceStatus"], "accepted")
        self.assertEqual(by_method["credit_cards"]["acceptanceStatus"], "not_accepted")
        self.assertNotIn("mastercard", by_method)

    def test_exact_name_match_is_required(self) -> None:
        places = [
            {"id": "places/other", "displayName": {"text": "Example Cafe"}, "paymentOptions": {"acceptsCreditCards": True}},
            {"id": "places/right", "displayName": {"text": "Example Bagels"}, "paymentOptions": {"acceptsCreditCards": True}},
        ]
        self.assertEqual(exact_name_place_match(places, RESTAURANT)["id"], "places/right")
        self.assertIsNone(exact_name_place_match(places[:1], RESTAURANT))


if __name__ == "__main__":
    unittest.main()

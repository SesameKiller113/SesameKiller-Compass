from __future__ import annotations

import unittest

from data_fetcher.adapters.restaurant_detail_payments import (
    detail_page_candidates,
    extract_payment_mentions,
    mentions_for_restaurant,
    payment_rows_from_mentions,
)


SOURCE = {
    "sourceName": "Airport dining directory",
    "sourceType": "official-airport-directory-html",
    "sourceUrl": "https://airport.example/restaurants/example-cafe",
    "licenseStatus": "official-public-page",
    "attributionRequired": True,
    "fetchedAt": "2026-08-11T00:00:00Z",
    "rawRef": "raw/test.html",
    "confidenceScore": 0.9,
    "notes": [],
}


def restaurant(**overrides: object) -> dict[str, object]:
    row = {
        "id": "official:jfk:test:1",
        "airportIata": "JFK",
        "name": "Example Cafe",
        "associationScope": "official_airport_directory",
        "officialSourcePath": "https://airport.example/restaurants/example-cafe#details",
        "source": SOURCE,
    }
    row.update(overrides)
    return row


class RestaurantDetailPaymentTests(unittest.TestCase):
    def test_extract_payment_mentions_requires_payment_context(self) -> None:
        html = """
        <h1>Example Cafe</h1>
        <p>Payment types: Visa, American Express, Euro/Mastercard, JCB, Union Pay, Apple Pay, Google Pay.</p>
        <p>Travel visa services are available elsewhere.</p>
        """
        mentions = extract_payment_mentions(
            html,
            allowed_methods=[
                "visa",
                "mastercard",
                "american_express",
                "jcb",
                "unionpay",
                "apple_pay",
                "google_pay",
            ],
        )
        methods = {mention["paymentMethod"] for mention in mentions}
        self.assertEqual(methods, {"visa", "mastercard", "american_express", "jcb", "unionpay", "apple_pay", "google_pay"})

    def test_cashless_text_marks_cash_not_accepted_without_card_network_guessing(self) -> None:
        mentions = extract_payment_mentions(
            "<p>This location is cashless and accepts credit cards.</p>",
            allowed_methods=["cash", "credit_cards", "visa", "mastercard"],
        )
        by_method = {mention["paymentMethod"]: mention for mention in mentions}
        self.assertEqual(by_method["cash"]["acceptanceStatus"], "not_accepted")
        self.assertEqual(by_method["credit_cards"]["acceptanceStatus"], "accepted")
        self.assertNotIn("visa", by_method)
        self.assertNotIn("mastercard", by_method)

    def test_payment_rows_from_mentions_apply_to_one_exact_method(self) -> None:
        mentions = extract_payment_mentions("<p>Payment methods accepted: Visa.</p>", allowed_methods=["visa", "mastercard"])
        rows = payment_rows_from_mentions(
            restaurant(),
            mentions,
            fetched_at="2026-08-11T00:00:00Z",
            raw_ref="raw/detail.html",
            source_url="https://airport.example/restaurants/example-cafe",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["paymentMethod"], "visa")
        self.assertEqual(rows[0]["acceptanceStatus"], "accepted")

    def test_shared_page_mentions_must_name_restaurant(self) -> None:
        mentions = extract_payment_mentions(
            "<p>Example Cafe payment types: Visa.</p><p>Other Cafe payment types: Mastercard.</p>",
            allowed_methods=["visa", "mastercard"],
        )
        example_mentions = mentions_for_restaurant(restaurant(name="Example Cafe"), mentions, shared_page=True)
        other_mentions = mentions_for_restaurant(restaurant(name="Silent Cafe"), mentions, shared_page=True)
        self.assertEqual({mention["paymentMethod"] for mention in example_mentions}, {"visa"})
        self.assertEqual(other_mentions, [])

    def test_detail_page_candidates_skip_third_party_detail_urls(self) -> None:
        rows = [
            restaurant(),
            restaurant(
                id="official:den:test:2",
                name="Brand Cafe",
                officialSourcePath="https://brand.example/airport-location",
                source={**SOURCE, "sourceUrl": "https://airport.example/dining"},
            ),
        ]
        candidates = detail_page_candidates(rows)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].url, "https://airport.example/restaurants/example-cafe")


if __name__ == "__main__":
    unittest.main()

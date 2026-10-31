from __future__ import annotations

import unittest

from data_fetcher.adapters.ourairports import normalize_ourairports_rows, select_us_airport_codes


class OurAirportsTests(unittest.TestCase):
    def test_select_us_airport_codes_filters_and_orders_deterministically(self) -> None:
        rows = [
            {"iata_code": "bbb", "iso_country": "US", "type": "medium_airport", "scheduled_service": "yes"},
            {"iata_code": "AAA", "iso_country": "US", "type": "small_airport", "scheduled_service": "yes"},
            {"iata_code": "ZZZ", "iso_country": "US", "type": "large_airport", "scheduled_service": "no"},
            {"iata_code": "CCC", "iso_country": "US", "type": "large_airport", "scheduled_service": "yes"},
            {"iata_code": "YYZ", "iso_country": "CA", "type": "large_airport", "scheduled_service": "yes"},
            {"iata_code": "", "iso_country": "US", "type": "large_airport", "scheduled_service": "yes"},
        ]
        self.assertEqual(select_us_airport_codes(rows, limit=3), ["CCC", "BBB", "AAA"])
        self.assertEqual(select_us_airport_codes(rows, limit=3, scheduled_only=False), ["CCC", "ZZZ", "BBB"])

    def test_normalize_ourairports_rows_keeps_requested_order(self) -> None:
        rows = [
            {
                "iata_code": "SFO",
                "iso_country": "US",
                "ident": "KSFO",
                "type": "large_airport",
                "name": "San Francisco International Airport",
                "municipality": "San Francisco",
                "iso_region": "US-CA",
                "latitude_deg": "37.61899948120117",
                "longitude_deg": "-122.375",
                "scheduled_service": "yes",
                "home_link": "https://www.flysfo.com/",
            },
            {
                "iata_code": "JFK",
                "iso_country": "US",
                "ident": "KJFK",
                "type": "large_airport",
                "name": "John F Kennedy International Airport",
                "municipality": "New York",
                "iso_region": "US-NY",
                "latitude_deg": "40.63980103",
                "longitude_deg": "-73.77890015",
                "scheduled_service": "yes",
                "home_link": "https://www.jfkairport.com/",
            },
        ]
        airports = normalize_ourairports_rows(rows, ["JFK", "SFO"], fetched_at="2026-08-11T00:00:00Z", raw_ref="raw.csv")
        self.assertEqual([airport["iataCode"] for airport in airports], ["JFK", "SFO"])
        self.assertEqual(airports[0]["countryCode"], "US")


if __name__ == "__main__":
    unittest.main()

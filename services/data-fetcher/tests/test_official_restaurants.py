from __future__ import annotations

import json
import unittest

import data_fetcher.adapters.official_restaurants as official_restaurants
from data_fetcher.http_client import FetchHttpError
from data_fetcher.adapters.official_restaurants import (
    OFFICIAL_RESTAURANT_SOURCES,
    check_robots_or_raise,
    compress_to_encoded_uri_component,
    extract_las_next_action_id,
    gate_from_text,
    enrich_panynj_records_from_locuslabs_payloads,
    normalize_las_display_pois,
    normalize_locuslabs_pois,
    parse_atl_restaurantweek_page,
    parse_den_eatden_cards,
    parse_las_display_pois_payload,
    normalize_panynj_dining_records,
    parse_clt_next_data_restaurants,
    next_msp_vendor_page,
    next_phl_directory_page,
    parse_dtw_concessions_dining,
    parse_iah_next_flight_restaurants,
    parse_lax_drupal_tenants,
    parse_msp_food_offering_gate_hints,
    enrich_msp_records_with_gate_hints,
    parse_msp_vendor_cards,
    parse_phl_foodshops_cards,
    parse_phx_food_cards,
    parse_sea_explore_dining_cards,
    parse_sfo_dining_cards,
)


class OfficialRestaurantTests(unittest.TestCase):

    def test_parse_atl_restaurantweek_page_splits_locations(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["ATL"]
        html = """
        <ul>
          <li>Asian Chao &#8211; A3, B Center &amp; D7</li>
          <li>Gift Shop &#8211; Atrium</li>
        </ul>
        """
        records = parse_atl_restaurantweek_page(
            html,
            source=source,
            fetched_at="2026-08-11T00:00:00Z",
            raw_ref="raw/test.html",
            page_url="https://www.atl.com/restaurantweek/grab_go/",
            category_slug="grab_go",
        )
        self.assertEqual(len(records), 4)
        asian = [record for record in records if record["name"] == "Asian Chao"]
        self.assertEqual(len(asian), 3)
        self.assertIn("Gate A3", {record["gate"] for record in asian})
        self.assertIn("Concourse B", {record["terminal"] for record in asian})
        self.assertIn("Gate D7", {record["gate"] for record in asian})

    def test_parse_den_eatden_cards_splits_multi_concourse_rows(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["DEN"]
        html = """
        <section id="comp-test" class="foo wixui-column-strip">
          <a href="https://www.eatden.com/shake-shack-food"><img src="/shake.jpg" /></a>
          <h1 style="font-size:37px">Shake Shack</h1>
          <h1 style="font-size:26px">Burgers, fries, shakes.<br />Concourse A &amp; B</h1>
        </section>
        """
        records = parse_den_eatden_cards(html, source=source, fetched_at="2026-08-11T00:00:00Z", raw_ref="raw/test.html")
        self.assertEqual(len(records), 2)
        self.assertEqual({record["terminal"] for record in records}, {"Concourse A", "Concourse B"})
        self.assertTrue(all(record["name"] == "Shake Shack" for record in records))
        self.assertIn("Burgers", records[0]["description"])

    def test_parse_las_display_pois_payload_filters_dining(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["LAS"]
        payload = [
            {
                "id": "168",
                "name": "Burger King",
                "category": "dining",
                "image": "/image.jpg",
                "keywords": ["burger", "quick"],
                "location": {"terminal": "1", "gate": "Gate D6", "landmark": "Near Gate D6", "isAfterSecurity": True},
                "operationHours": "Mo-Su 06:00-22:00",
            },
            {"id": "200", "name": "News Shop", "category": "shopping", "location": {"terminal": "3"}},
        ]
        body = "0:{}\n1:" + json.dumps(payload)
        parsed = parse_las_display_pois_payload(body)
        records = normalize_las_display_pois(parsed, source=source, fetched_at="2026-08-11T00:00:00Z", raw_ref="raw/test.txt")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "Burger King")
        self.assertEqual(records[0]["terminal"], "Terminal 1")
        self.assertEqual(records[0]["securityArea"], "Post-Security")
        self.assertEqual(records[0]["gate"], "Gate D6")


    def test_normalize_locuslabs_pois_maps_floor_and_filters_vending(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["DFW"]
        pois_payload = {
            "restaurant": {
                "poiId": "dfw-101",
                "name": "Example Tacos",
                "category": "eat",
                "description": "Tacos near Gate D12.",
                "isAfterSecurity": True,
                "position": {"floorId": "dfw-terminald-departures", "latitude": 32.89, "longitude": -97.04},
                "nearbyLandmark": "Near Gate D12",
                "images": ["example.png"],
                "keywords": [
                    {"name": "mexican", "isDisplayed": True},
                    {"name": "hidden-search", "isDisplayed": False},
                ],
            },
            "coffee": {
                "poiId": "dfw-102",
                "name": "Example Coffee",
                "category": "eat.coffee",
                "position": {"floorId": "dfw-terminala-departures"},
            },
            "vending": {
                "poiId": "dfw-103",
                "name": "Snack Vending",
                "category": "eat.vending",
                "position": {"floorId": "dfw-terminala-departures"},
            },
            "shop": {"poiId": "dfw-104", "name": "News Shop", "category": "shop"},
        }
        venue_payload = {
            "dfw": {
                "structures": {
                    "terminal-a": {
                        "name": "Terminal A",
                        "levels": {"dfw-terminala-departures": {"name": "Departures"}},
                    },
                    "terminal-d": {
                        "name": "Terminal D",
                        "levels": {"dfw-terminald-departures": {"name": "Departures"}},
                    },
                }
            }
        }

        records = normalize_locuslabs_pois(
            pois_payload,
            venue_payload,
            source=source,
            fetched_at="2026-08-11T00:00:00Z",
            raw_ref="raw/test.json",
        )

        self.assertEqual({record["name"] for record in records}, {"Example Coffee", "Example Tacos"})
        tacos = next(record for record in records if record["name"] == "Example Tacos")
        self.assertEqual(tacos["terminal"], "Terminal D")
        self.assertEqual(tacos["gate"], "Gate D12")
        self.assertEqual(tacos["securityArea"], "Post-Security")
        self.assertEqual(tacos["latitude"], 32.89)
        self.assertIn("mexican", tacos["featureTags"])
        self.assertNotIn("hidden-search", tacos["featureTags"])
        self.assertTrue(tacos["imageUrls"][0].startswith("https://img.locuslabs.com/resize/"))

    def test_extract_las_next_action_id_reads_public_chunk(self) -> None:
        chunk = 'x=createServerReference("00f8b7d4ec84aa668028fa01b5ada67dab524523fa",null,null,"getDisplayPois")'
        self.assertEqual(extract_las_next_action_id(chunk), "00f8b7d4ec84aa668028fa01b5ada67dab524523fa")

    def test_parse_sfo_dining_cards(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["SFO"]
        html = """
        <a href="/passengers/shop-dine-relax/example-cafe" class="card-view--card">
          <div class="card-view--card__title">Example Cafe</div>
          <div class="field field--name-field-tags field--type-entity-reference field--label-hidden field__items">
            <div class="field__item tag--open-past-10pm"> Open Past 10PM</div>
          </div>
          <div class="card-view--card__terminal"><div class="field field--name-field-terminal field--type-entity-reference field--label-hidden field__item">Terminal 2</div></div>
          <div class="vendor-status has-hours" data-node-id="12345"></div>
        </a>
        """
        records = parse_sfo_dining_cards(html, source=source, fetched_at="2026-08-11T00:00:00Z", raw_ref="raw/test.html")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], "official:sfo:flysfo:12345")
        self.assertEqual(records[0]["name"], "Example Cafe")
        self.assertEqual(records[0]["terminal"], "Terminal 2")
        self.assertEqual(records[0]["associationScope"], "official_airport_directory")
        self.assertEqual(records[0]["paymentMethods"], ["unknown"])

    def test_normalize_panynj_dining_records(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["JFK"]
        records = normalize_panynj_dining_records(
            [
                {
                    "id": "42",
                    "name": "Example Bagels",
                    "description": "Breakfast.",
                    "category": "eat.coffee",
                    "structureName": "Terminal 4",
                    "floorName": "Level 2",
                    "nearbyLandmark": "Gate B22",
                    "mapUrl": "http://maps.jfkairport.com?poiId=42",
                    "images": ["https://example.com/image.jpg"],
                }
            ],
            source=source,
            fetched_at="2026-08-11T00:00:00Z",
            raw_ref="raw/test.json",
        )
        self.assertEqual(records[0]["id"], "official:jfk:panynj:42")
        self.assertEqual(records[0]["gate"], "Gate B22")
        self.assertEqual(records[0]["officialCategory"], "eat.coffee")
        self.assertIn("poiId=42", records[0]["officialSourcePath"])


    def test_panynj_gate_parsing_handles_nearby_and_plural_gate_text(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["LGA"]
        records = normalize_panynj_dining_records(
            [
                {
                    "id": "61",
                    "name": "Food Hall Cafe",
                    "category": "eat",
                    "structureName": "Terminal B",
                    "floorName": "Level 2",
                    "nearbyLandmark": "Food Hall near Gate 61",
                    "mapUrl": "http://maps.laguardiaairport.com?poiId=61",
                }
            ],
            source=source,
            fetched_at="2026-08-11T00:00:00Z",
            raw_ref="raw/test.json",
        )
        self.assertEqual(records[0]["gate"], "Gate 61")
        self.assertEqual(gate_from_text("Gates A3 & A5"), "Gates A3 & A5")
        self.assertEqual(gate_from_text("Gate A 6"), "Gate A6")

    def test_panynj_locuslabs_enrichment_adds_coordinates_by_poi_id(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["LGA"]
        records = normalize_panynj_dining_records(
            [
                {
                    "id": "151",
                    "name": "CIBO Express Gourmet Markets",
                    "category": "eat",
                    "structureName": "Terminal C",
                    "floorName": "Level 2",
                    "nearbyLandmark": "Food Hall near Gate 61",
                    "mapUrl": "http://maps.laguardiaairport.com?poiId=151",
                }
            ],
            source=source,
            fetched_at="2026-08-11T00:00:00Z",
            raw_ref="raw/test.json",
        )
        pois_payload = {
            "151": {
                "poiId": "151",
                "name": "CIBO Express Gourmet Markets",
                "category": "eat",
                "nearbyLandmark": "Food Hall near Gate 61",
                "position": {"floorId": "lga-tc-2", "latitude": 40.771603, "longitude": -73.86575},
            }
        }
        venue_payload = {
            "lga": {
                "structures": {
                    "terminal-c": {
                        "name": "Terminal C",
                        "levels": {"lga-tc-2": {"name": "Level 2"}},
                    }
                }
            }
        }
        enriched = enrich_panynj_records_from_locuslabs_payloads(records, pois_payload, venue_payload, source=source)
        self.assertEqual(enriched[0]["latitude"], 40.771603)
        self.assertEqual(enriched[0]["longitude"], -73.86575)
        self.assertEqual(enriched[0]["gate"], "Gate 61")
        self.assertIn("official airport-map POI ID", enriched[0]["source"]["notes"][-1])



    def test_parse_sea_explore_dining_cards_keeps_gate_and_concourse(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["SEA"]
        html = """
        <div class="single-tile beer-cocktails-wine restaurants-sit-down gate-b" data-concept-name="rel'lish burger lounge">
          <a href="https://exploresea.org/concept/rellish-burger-lounge/">
            <img src="https://exploresea.org/image.jpg" alt="Rel'lish" />
            Rel'lish Burger Lounge
          </a>
          <p>Pacific Northwest burgers.</p>
          <p>Near Gate B4</p>
        </div>
        """
        records = parse_sea_explore_dining_cards(html, source=source, fetched_at="2026-08-11T00:00:00Z", raw_ref="raw/test.html")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "Rel'lish Burger Lounge")
        self.assertEqual(records[0]["terminal"], "Concourse B")
        self.assertEqual(records[0]["gate"], "Gate B4")
        self.assertEqual(records[0]["associationScope"], "official_airport_directory")
        self.assertEqual(records[0]["paymentMethods"], ["unknown"])

    def test_parse_phx_food_cards_keeps_terminal_and_gate_range(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["PHX"]
        html = """
        <div class="col-lg-4" data-terminal="T4" data-location="Post-Security" data-concourse="D" data-gates="D1-D8" data-primary="local favorites,dine-in" data-secondary="vegetarian">
          <div class="element--poi-card">
            <a href="/at-the-airport/food-drinks/barrio-cafe-428/" class="thumb-href"><img src="/image.jpg" /></a>
            <h3 class="notranslate"><a href="/at-the-airport/food-drinks/barrio-cafe-428/">Barrio Cafe</a></h3>
          </div>
        </div>
        """
        records = parse_phx_food_cards(html, source=source, fetched_at="2026-08-11T00:00:00Z", raw_ref="raw/test.html")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["terminal"], "Terminal 4")
        self.assertEqual(records[0]["securityArea"], "Post-Security")
        self.assertEqual(records[0]["gate"], "Gates D1-D8")
        self.assertIn("Concourse D", records[0]["locationDescription"])

    def test_parse_clt_next_data_restaurants_filters_food_pois(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["CLT"]
        payload = {
            "props": {
                "pageProps": {
                    "pois": [
                        {
                            "category": "eat",
                            "description": "Near Gate A4",
                            "nearbyLandmark": "Concourse A",
                            "name": "The Taproom",
                            "poiId": "19",
                            "position": {"latitude": 35.22, "longitude": -80.94},
                            "terminal": "Concourse A",
                            "tags": ["dine", "bar"],
                        },
                        {"category": "shop", "name": "News Stand", "poiId": "20"},
                    ]
                }
            }
        }
        html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'
        records = parse_clt_next_data_restaurants(html, source=source, fetched_at="2026-08-11T00:00:00Z", raw_ref="raw/test.html")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "The Taproom")
        self.assertEqual(records[0]["gate"], "Gate A4")
        self.assertEqual(records[0]["latitude"], 35.22)

    def test_parse_iah_next_flight_restaurants_filters_vending(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["IAH"]
        restaurant = {
            "additionalAttributes": {"grabUrl": None},
            "category": "eat",
            "description": "Tacos near the gate.",
            "nearbyLandmark": "Gate C33",
            "name": "Agave Taqueria",
            "poiId": "42",
            "position": {"floorId": "iah-tc-2", "latitude": 29.98, "longitude": -95.33},
            "terminal": "Terminal C",
            "tags": [{"name": "dine"}],
            "operationHours": "Mo-Su 06:00-22:00",
        }
        vending = {**restaurant, "category": "eat.vending", "name": "Vending", "poiId": "43"}
        html = json.dumps(restaurant).replace('"', '\\"') + json.dumps(vending).replace('"', '\\"')
        records = parse_iah_next_flight_restaurants(html, source=source, fetched_at="2026-08-11T00:00:00Z", raw_ref="raw/test.html")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "Agave Taqueria")
        self.assertEqual(records[0]["gate"], "Gate C33")

    def test_parse_dtw_concessions_dining_marks_terminal_level_rows(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["DTW"]
        html = """
        <h2>McNamara Terminal Dining</h2>
        <p><a href="https://www.metroairport.com/terminals/maps/mcnamara-terminal?assetview=1976"><strong>Starbucks (Gate A20):</strong> <strong>- Coffee, Pastries</strong></a></p>
        <h2>McNamara Terminal Shopping</h2>
        <h2>Evans Terminal Dining</h2>
        <p><a href="https://www.metroairport.com/terminals/maps/evans-terminal?assetview=1967"><strong>Air Margaritaville</strong></a></p>
        <h2>Evans Terminal Shopping</h2>
        """
        records = parse_dtw_concessions_dining(html, source=source, fetched_at="2026-08-11T00:00:00Z", raw_ref="raw/test.html")
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["terminal"], "Evans Terminal")
        starbucks = next(record for record in records if record["name"] == "Starbucks")
        self.assertEqual(starbucks["gate"], "Gate A20")
        self.assertEqual(starbucks["terminal"], "McNamara Terminal")


    def test_parse_lax_drupal_tenants_filters_food_and_keeps_location(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["LAX"]
        payload = {
            "tenants": [
                {
                    "CompanyLocationID": "1682",
                    "CompanyName": "800 Degrees Pizza",
                    "CompanyLocationDescription": "Pizza in the food court.",
                    "Categories": "FOOD AND BEVERAGE FACILITIES",
                    "Terminal": "Terminal B",
                    "Location": "Great Hall - Food Court",
                    "securitycheckpoint": "1",
                    "Lat": "33.94385039",
                    "Long": "-118.41019519",
                    "displayTags": "pizza, beer",
                    "MediaImageLogoURL": "https://media.flylax.com/concessions/logo.png",
                },
                {
                    "CompanyLocationID": "1888",
                    "CompanyName": "Gift Shop",
                    "Categories": "GIFT SHOPS AND NEWS STANDS",
                },
            ]
        }
        html = '<script type="application/json" data-drupal-selector="drupal-settings-json">' + json.dumps(payload) + "</script>"
        records = parse_lax_drupal_tenants(html, source=source, fetched_at="2026-08-11T00:00:00Z", raw_ref="raw/test.html")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "800 Degrees Pizza")
        self.assertEqual(records[0]["terminal"], "Terminal B")
        self.assertEqual(records[0]["securityArea"], "Post-Security")
        self.assertEqual(records[0]["latitude"], 33.94385039)
        self.assertIn("pizza", records[0]["featureTags"])

    def test_parse_msp_vendor_cards_filters_eat_category(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["MSP"]
        html = """
        <div class="vendor-list__item vendor-list__item--card">
          <a href="/airport/eat-shop-relax/angel-food-bakery" class="entity--type-node vendor-card">
            <h4 class="vendor-list__item-title">Angel Food Bakery</h4>
            <div class="vendor-list__item-category"><span about="/taxonomy/term/101">Eat</span><span about="/taxonomy/term/102">Bakery</span></div>
            <div class="vendor-list__item-hours"><img src="/clock.svg" /> 5:00 am - 8:00 pm</div>
            <div class="vendor-list__item-terminals"><span class="vendor-list__item-terminal">Terminal 1</span> <span class="vendor-list__item-course">Concourse E</span></div>
          </a>
        </div>
        <div class="vendor-list__item vendor-list__item--card">
          <a href="/airport/eat-shop-relax/shop" class="entity--type-node vendor-card">
            <h4 class="vendor-list__item-title">Shop</h4>
            <div class="vendor-list__item-category"><span about="/taxonomy/term/241">Shop</span></div>
          </a>
        </div>
        """
        records = parse_msp_vendor_cards(html, source=source, fetched_at="2026-08-11T00:00:00Z", raw_ref="raw/test.html")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "Angel Food Bakery")
        self.assertEqual(records[0]["terminal"], "Terminal 1")
        self.assertIn("Concourse E", records[0]["locationDescription"])
        self.assertIn("Eat", records[0]["featureTags"])

    def test_msp_food_offering_gate_hints_enrich_matching_concourse(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["MSP"]
        html = """
        <div class="field-freeform-content"><h3><a href="/airport/eat-shop-relax/starbucks">Starbucks</a></h3>
        <h4>By Gates C13, G16, and the Airport Mall</h4></div>
        <div class="field-freeform-content"><h3>MSP MKT</h3><h4>By Gate H5</h4></div>
        """
        hints = parse_msp_food_offering_gate_hints(html, page_url="https://www.mspairport.com/terminal-1-food-offerings")
        self.assertEqual(hints[0]["gates"], ["Gate C13", "Gate G16"])

        records = [
            {
                "name": "Starbucks",
                "terminal": "Terminal 1",
                "gate": None,
                "locationDescription": "Terminal 1, Concourse G",
                "source": {"notes": []},
            },
            {
                "name": "MSP MKT",
                "terminal": "Terminal 2",
                "gate": None,
                "locationDescription": "Terminal 2, Concourse H",
                "source": {"notes": []},
            },
        ]
        enriched = enrich_msp_records_with_gate_hints(records, hints)
        self.assertEqual(enriched[0]["gate"], "Gate G16")
        self.assertEqual(enriched[1]["gate"], "Gate H5")
        self.assertIn("official terminal food-offerings", enriched[0]["source"]["notes"][-1])


    def test_parse_phl_foodshops_cards_keeps_terminal_and_tags(self) -> None:
        source = OFFICIAL_RESTAURANT_SOURCES["PHL"]
        html = """
        <div data-elementor-type="loop-item" class="elementor e-loop-item e-loop-item-12488 post-12488 directory_category-dine directory_tag-breakfast directory_tag-pizza">
          <h3 class="elementor-heading-title elementor-size-default"><a href="https://www.phlfoodandshops.com/directory/aldo-lamberti-trattoria/">Aldo Lamberti Trattoria</a></h3>
          <img src="https://www.phlfoodandshops.com/image.png" alt="Aldo" />
          <span>Terminal C</span>
        </div>
        <div data-elementor-type="loop-item" class="elementor e-loop-item post-999 directory_category-shop">
          <h3 class="elementor-heading-title"><a href="https://example.test/shop/">Shop</a></h3>
          <span>Terminal B</span>
        </div>
        """
        records = parse_phl_foodshops_cards(html, source=source, fetched_at="2026-08-11T00:00:00Z", raw_ref="raw/test.html")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], "official:phl:phl-foodshops-html:12488")
        self.assertEqual(records[0]["terminal"], "Terminal C")
        self.assertIn("breakfast", records[0]["featureTags"])

    def test_directory_pagination_helpers_extract_public_next_links(self) -> None:
        self.assertEqual(
            next_phl_directory_page('<div data-next-page="https://www.phlfoodandshops.com/directory/page/2/?_directory_filter=dine"></div>', "https://www.phlfoodandshops.com/directory/"),
            "https://www.phlfoodandshops.com/directory/page/2/?_directory_filter=dine",
        )
        self.assertEqual(
            next_msp_vendor_page('<a class="button" href="?page=1" title="Load more items" rel="next">Load More</a>', "https://www.mspairport.com/airport/eat-shop-relax"),
            "https://www.mspairport.com/airport/eat-shop-relax?page=1",
        )
        self.assertIsNone(
            next_phl_directory_page('<link rel="next" href="https://www.phlfoodandshops.com/directory/page/5/" />', "https://www.phlfoodandshops.com/directory/page/4/?_directory_filter=dine")
        )
        self.assertIsNone(
            next_phl_directory_page('<div data-page="4" data-max-page="4" data-next-page="https://www.phlfoodandshops.com/directory/page/5/?_directory_filter=dine"></div>', "https://www.phlfoodandshops.com/directory/page/4/?_directory_filter=dine")
        )

    def test_robots_missing_rules_4xx_are_treated_as_no_restrictions(self) -> None:
        original_fetch_text = official_restaurants.fetch_text

        for status in (403, 404):
            official_restaurants.ROBOTS_TXT_CACHE.clear()

            def fake_fetch_text(url: str, **_kwargs: object) -> object:
                raise FetchHttpError(url, status, "")

            official_restaurants.fetch_text = fake_fetch_text
            try:
                check_robots_or_raise("https://example.test/public", "SesameKiller-CompassBot/0.1")
            finally:
                official_restaurants.fetch_text = original_fetch_text
                official_restaurants.ROBOTS_TXT_CACHE.clear()


    def test_robots_access_challenge_is_blocking(self) -> None:
        original_fetch_text = official_restaurants.fetch_text
        official_restaurants.ROBOTS_TXT_CACHE.clear()

        class FakeResponse:
            body = "<html><title>Just a moment...</title>challenge-platform cloudflare</html>"

        def fake_fetch_text(url: str, **_kwargs: object) -> object:
            return FakeResponse()

        official_restaurants.fetch_text = fake_fetch_text
        try:
            with self.assertRaisesRegex(RuntimeError, "access challenge"):
                check_robots_or_raise("https://example.test/public", "SesameKiller-CompassBot/0.1")
        finally:
            official_restaurants.fetch_text = original_fetch_text
            official_restaurants.ROBOTS_TXT_CACHE.clear()

    def test_lz_string_compression_is_deterministic(self) -> None:
        body = json.dumps({"operationName": "Ping", "variables": {}, "query": "query Ping { ping }"}, separators=(",", ":"))
        self.assertEqual(compress_to_encoded_uri_component(body), compress_to_encoded_uri_component(body))
        self.assertTrue(compress_to_encoded_uri_component(body))


if __name__ == "__main__":
    unittest.main()

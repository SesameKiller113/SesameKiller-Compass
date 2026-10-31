# Legal Data Policy

This is an engineering compliance note for SesameKiller-Compass, not legal advice. The fetcher is designed to be conservative: use public/open data where the source permits it, keep provenance with every record, respect robots.txt, and do not guess missing facts.

## Sources Allowed In This Demo

| Source | Use | Evidence | Guardrails |
| --- | --- | --- | --- |
| OurAirports `airports.csv` | Airport identity, location, official website URL | OurAirports says its data is public domain: https://ourairports.com/data/ and documents the CSV fields at https://ourairports.com/help/data-dictionary.html | Keep source URL, fetch time, and raw snapshot. Do not treat source data as guaranteed correct. |
| Official airport dining directories | Official airport restaurant inventory for reviewed adapters, plus source-backed gate/coordinate enrichment where the airport publishes map/detail data | Robots.txt guidance: https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt. Reviewed source URLs: JFK, LGA, EWR, SFO, SEA, PHX, CLT, IAH, DTW, LAX, ATL, DEN, LAS, ORD, DFW, MSP, and PHL official dining/concession pages listed in `source-manifest.json` | Check robots.txt before each source path, use public pages/endpoints only, keep raw evidence, and do not infer payment methods when the source is silent. PANYNJ coordinates are matched by POI ID from public airport map data; MSP gates are enriched only from official terminal food-offerings pages. If a reviewed URL later returns a bot/access challenge, the run must skip it and lower live coverage. |
| Official restaurant detail payment pages | Optional explicit payment-method text on official restaurant/airport detail pages | Examples of airports that publish explicit fields include Frankfurt Airport pages with `Payment types` sections. For this project, detail pages are fetched only from the same airport/operator source host already used for restaurant inventory. | Check robots.txt for every detail URL, use public pages only, write raw evidence, and apply a payment fact only when the page explicitly names that method. Shared directory-page text is not copied to every restaurant unless the evidence snippet names the restaurant. |
| OpenStreetMap through Overpass API | Scalable restaurant-like amenities and explicit `payment:*` tags inside OSM airport areas, with radius fallback when needed | OSM copyright/license page: https://www.openstreetmap.org/copyright/no. OSM attribution guidance: https://osmfoundation.org/wiki/Licence/Attribution_Guidelines. OSM operations API policy: https://operations.osmfoundation.org/policies/api/ | Use a named user agent, low request rate, no bulk abuse, keep ODbL attribution, and label OSM matches as `inside_osm_airport_area` or `near_airport_radius` rather than official tenant records. Use a dedicated endpoint, OSM extract, or commercial OSM provider for repeated 2000+ airport ingestion. |
| Google Places API `paymentOptions` | Optional generic payment acceptance enrichment for exact-name restaurant matches | Google Places payment-options overview: https://developers.google.com/maps/documentation/places/web-service/op-overview | Requires a local API key, current Google Maps Platform terms/billing review, field-mask use, attribution, and retention compliance. Only generic payment methods are exported; no card-network acceptance is inferred. |
| Reviewed card-benefit JSON | Card products and benefits from official terms, approved APIs, or licensed feeds | Visa VCES docs: https://developer.visa.com/capabilities/vces/docs-getting-started and https://developer.visa.com/capabilities/vces/reference. Visa Developer terms: https://developer.visa.com/terms | No automated scraping of Visa or issuer pages. No production card-network API calls until approval/certification/agreement. Every row needs source URL, terms URL, review date, and legal basis. |
| Reviewed payment-acceptance JSON | Exact restaurant-payment-method facts from merchant/airport statements, OSM tags, approved APIs, or licensed feeds | Google Places docs: https://developers.google.com/maps/documentation/places/web-service/op-overview. Foursquare docs: https://docs.foursquare.com/fsq-developers-places/reference/places-api-overview | Do not infer network acceptance from generic credit-card acceptance. Do not store PAN/cardholder data. Every known row needs source URL, review date, and legal basis. |

## Accuracy Policy

Public/open sources cannot give a true 100% correctness guarantee. The project should therefore say "source-backed" instead of "guaranteed correct". Every normalized record includes source name, source URL, license status, fetch time, raw snapshot reference, confidence score, and notes.

The fetcher follows these rules:

- If a payment method is missing from the source, output `unknown`.
- If OSM says `payment:visa=yes`, output `visa`; if OSM is silent, do not infer Visa support.
- If an official restaurant detail page explicitly lists `Visa`, output `visa`; if it says only `credit cards`, output generic `credit_cards` and do not infer Visa, Mastercard, or Amex.
- If Google Places says `acceptsCreditCards=true`, output generic `credit_cards`; do not infer Visa, Mastercard, or Amex.
- If a restaurant is found inside an OSM aerodrome area or by coordinate radius, do not present it as confirmed inside a terminal unless an official source also confirms it.
- If a card benefit references a restaurant, resolve it by official `restaurantId` or a single exact normalized name match for that airport; otherwise fail validation.
- If robots.txt returns 401, 403, 404, or 410, treat it as no available robots rules under standard crawler handling; if it returns 429, 5xx, network errors, or disallow rules, skip the source path.
- If a source returns a bot-protection challenge, do not bypass it.
- If a source requires approval, credentials, or a license, the demo writes schema-only files or requires a reviewed local input instead of scraping.

## Current Official Restaurant Coverage

Reviewed official adapters currently cover these first-20 demo airports:

```text
JFK, LGA, EWR, SFO, SEA, PHX, CLT, IAH, DTW, LAX, ATL, DEN, LAS, ORD, DFW, MSP, PHL
```

Coverage is measured in `data/manifests/source-manifest.json` after each run. The August 11, 2026 live validation covers 17 of the first 20 target airports, below the 18 airports required for 90% official coverage. Reaching 90% official airport coverage requires reviewed adapters or licensed/approved sources for at least 18 airports. BOS is skipped because its public page returns a bot-protection challenge, MCO is skipped because the content API host disallows crawling in robots.txt, and MIA needs permission review for the commerce API powering its public web app. Scalable OSM enrichment can improve discovery and payment-tag evidence, but it must not be counted as official airport-terminal coverage.

## Card And Payment Boundaries

Card benefits and merchant card acceptance are different facts:

- `benefits.*` answers: "Does this card have an offer, credit, lounge, or dining benefit here?"
- `payment_acceptance.*` answers: "Does this exact restaurant have source-backed acceptance evidence for this payment method?"

Do not connect these facts unless both sides are independently source-backed. For example, an Amex dining credit does not prove the restaurant accepts American Express; an OSM `payment:american_express=yes` tag does not prove any card has a benefit there.

## Data Not Allowed Yet

- Visa, Mastercard, Amex, or issuer card-benefit scraping.
- Logged-in, paywalled, CAPTCHA-protected, private, or undocumented API data.
- Personal cardholder data, PAN values, or payment credentials.
- Bulk Nominatim geocoding. Nominatim has its own policy at https://operations.osmfoundation.org/policies/nominatim/ and is not used by this fetcher by default.

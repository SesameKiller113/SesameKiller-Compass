# Data Fetcher

The data fetcher is the first production-shaped ingestion slice for SesameKiller-Compass. JSON is the canonical normalized format. CSV is exported beside it so the next Neo4j/MongoDB importer can load the same facts easily.

## Why JSON plus CSV

JSON keeps nested provenance, source notes, raw payment tags, image URLs, and future schema changes clean. CSV is useful for Neo4j `LOAD CSV`, spreadsheet review, and manual QA. The fetcher writes both from the same normalized records.

## Restaurant Strategy

The default restaurant mode is official-only:

```bash
npm run fetch:data -- --limit 20 --restaurant-source official
```

Official-only means a restaurant is exported only when a reviewed adapter can read an airport-operated public dining directory. Current reviewed adapters are:

- JFK, LGA, EWR: Port Authority public dining data through the same public GraphQL endpoint used by the official dining pages.
- SFO: SFO official dining-filtered `Shop/Dine/Relax` HTML.
- SEA: SEA Airport Dining and Retail public dining cards with concourse/gate values when present.
- PHX: Phoenix Sky Harbor official `Food & Drinks` HTML cards with terminal, security area, concourse, and gate range when present.
- CLT: Charlotte Douglas official `Shop, Dine & Relax` Next.js data with food POIs, concourse/location, coordinates, and gate when source text includes it.
- IAH: Houston Airports official IAH `Shop, Dine & Relax` page payload with food POIs, terminal, gate, and coordinates; vending machines are excluded from restaurant inventory.
- DTW: Detroit Metro official concessions contacts dining lists by terminal, with gate only when the source text includes it.
- LAX: LAX official Drupal tenant payload filtered to `FOOD AND BEVERAGE FACILITIES`, with terminal, security side, location text, coordinates, and images when present.
- ATL: Hartsfield-Jackson Atlanta official restaurant-week category pages. These are official, but the live validator currently skips them when ATL returns a Cloudflare access challenge.
- DEN: Denver International Airport Eat DEN public dining directory, with one normalized row per listed concourse when a concept appears in multiple concourses.
- LAS: Harry Reid International Airport official Shop, Dine, and More directory through the public page's server action, filtered to `category=dining`.
- ORD: Chicago O'Hare official Eat/Shop/More page backed by public LocusLabs/Atrius map POIs, filtered to non-vending dining categories.
- DFW: Dallas Fort Worth official Shop, Dine, Services page backed by public LocusLabs/Atrius map POIs, filtered to non-vending dining categories.
- MSP: MSP Airport official `Eat, Shop, Relax` vendor cards, including public load-more pages, filtered to source category `Eat`.
- PHL: PHL Food & Shops dining-filtered concession directory, including public paginated directory pages, linked from Philadelphia International Airport passenger dining information.

The other target airports remain in `airports.json`, and the manifest records unsupported official restaurant coverage for them. That is intentional: missing data is better than pretending a nearby restaurant is inside a terminal.

OSM/Overpass is the scalable restaurant discovery baseline:

```bash
npm run fetch:data -- --us-airports --limit 200 --restaurant-source osm --osm-association-mode area-first --delay-ms 3000
```

The `osm` mode is generic, so it does not require one adapter per airport. It first looks for food amenities inside OSM aerodrome areas and labels those rows `inside_osm_airport_area`. If that returns no food places for an airport, it falls back to coordinate radius and labels rows `near_airport_radius`. Neither label is the same as `official_airport_directory`; OSM can improve discovery and payment-tag coverage, but it does not prove official terminal tenancy.

For repeated 2000+ airport jobs, use `OVERPASS_ENDPOINT` pointed at a dedicated Overpass endpoint, an OSM extract pipeline, or a commercial OSM provider. The public Overpass API is useful for testing and modest runs, but it is not the right infrastructure for heavy recurring ingestion.

## Payment Acceptance Strategy

Restaurant inventory and payment acceptance are separate facts. The fetcher now writes `payment_acceptance.json` and `payment_acceptance.csv` with one row per restaurant per supported method:

```text
visa, mastercard, american_express, discover, diners_club, jcb, unionpay,
credit_cards, debit_cards, contactless, apple_pay, google_pay, cash
```

A row is `accepted` or `not_accepted` only when a source explicitly provides that method fact. That can come from OSM `payment:*` tags in OSM-enabled modes, official restaurant detail pages with explicit payment text, Google Places generic `paymentOptions`, or from a reviewed/licensed payment-acceptance input file. If the source is silent, the row is `unknown`. Unknown is not a negative claim.

This lets the app answer questions like "does this restaurant support my Amex?" safely:

- If exact restaurant + `american_express=accepted`: answer yes and cite the source.
- If exact restaurant + `american_express=unknown`: answer that we do not have source-backed evidence yet.
- If only generic `credit_cards=accepted`: do not infer Amex/Visa/Mastercard network acceptance.

## Card Benefit Strategy

The fetcher does not scrape Visa, Mastercard, Amex, or issuer card pages. Real card products and benefits must come from one of these approved paths:

- Reviewed local JSON from official issuer/card-network terms.
- Approved card-network APIs, for example Visa VCES/VMORC after Visa approval and certification.
- Mastercard developer/partner offer or benefits APIs after approval.
- Licensed affiliate, issuer, or processor feeds whose terms allow storage and product use.
- Manual admin review workflow that records `sourceUrl`, `termsUrl`, `reviewedAt`, `reviewedBy`, and `legalBasis`.

Start from the template:

```bash
cp services/data-fetcher/examples/reviewed_card_benefits.example.json data/manual/card_benefits.local.json
```

Then edit `data/manual/card_benefits.local.json` locally and run:

```bash
npm run fetch:data -- --airports JFK,SFO --card-benefits-file data/manual/card_benefits.local.json
```

Real files in `data/manual/` are ignored by git. Restaurant-specific benefits are match-checked against restaurants fetched in the same run. Use `restaurantId` when possible. If you only have a restaurant name, include `airportIata`; the pipeline accepts exactly one normalized name match and writes `restaurantMatchStatus`, `restaurantMatchConfidence`, `matchedRestaurantSourceUrl`, and `matchedRestaurantAssociationScope`. Unmatched or ambiguous restaurant references fail validation.

## Coverage Targets

The manifest writes multiple coverage measurements:

- Official restaurant airport coverage: how many target airports have reviewed official restaurant adapters with records.
- Restaurant discovery airport coverage: how many target airports have any restaurant rows from official adapters or OSM discovery.
- OSM restaurant coverage: how many target airports have OSM restaurant rows, split into `inside_osm_airport_area` and `near_airport_radius` counts.
- Restaurant field coverage: terminal, gate, and coordinate coverage inside official restaurant records.
- Payment acceptance coverage: how many method rows have explicit accepted evidence instead of unknown.

For the first 20-airport demo, true 90% official airport coverage means at least 18 of 20 airports need reviewed official directory adapters or an approved/licensed airport-directory source. The August 11, 2026 live validation covers 17/20 target airports, or 85%, with BOS, MCO, and MIA still unsupported until a legally usable public directory, API, or licensed source is available. PANYNJ map-data enrichment now adds source-backed coordinates for JFK/LGA/EWR by matching official dining POI IDs to the airport map dataset, and MSP food-offerings pages can enrich a small set of gate values. The code reports the real percentage after each run; do not count bot-challenge pages, robots-disallowed APIs, unsupported commerce APIs, or OSM radius rows as official coverage. OSM can supplement data but should not be counted as official terminal coverage.

## Commands

The fetcher uses only the Python standard library. You can run it through npm convenience scripts from the repo root, or directly with `PYTHONPATH=services/data-fetcher python3 -m data_fetcher.cli`.

Fast no-restaurant smoke test:

```bash
npm run fetch:data -- --limit 20 --restaurant-source none
```

Live public-data fetch for the first 20 airports with official restaurant sources and slower public-source pacing:

```bash
npm run fetch:data:live
```

Select 200 US scheduled-service airports from OurAirports:

```bash
npm run fetch:data:us200
```

That command writes airport JSON/CSV only. To measure current official restaurant adapter coverage across the same 200-airport selection:

```bash
npm run fetch:data:us200:official
```

To get scalable OSM restaurant discovery for 200 US airports:

```bash
npm run fetch:data:us200:osm
```

To try the same shape for 2000 US airports, including non-scheduled airports when needed:

```bash
npm run fetch:data:us2000:osm
```

The 2000-airport command is intentionally slow against the public Overpass endpoint and includes polite retry/backoff controls for `429` rate limits. For real repeated ingestion, set `OVERPASS_ENDPOINT` to your own endpoint/provider or move to an OSM extract pipeline.

The `--us-airports` selector is deterministic: it uses US airports with IATA codes from OurAirports, keeps scheduled-service airports by default, and orders by airport type (`large_airport`, then `medium_airport`, then `small_airport`) and IATA code. OurAirports does not provide passenger-rank ordering, so this is a broad US coverage sample, not a top-passenger-volume ranking.

Useful narrower run while testing:

```bash
npm run fetch:data -- --airports JFK,LGA,EWR,SFO,PHX,CLT,IAH,DTW,LAX,ORD,DFW,MSP,PHL --restaurant-source official --delay-ms 3000
```

Optional official plus OSM enrichment:

```bash
npm run fetch:data -- --airports JFK,SFO --restaurant-source official-plus-osm --osm-association-mode area-first --delay-ms 3000
```

Legacy radius-only comparison:

```bash
npm run fetch:data -- --airports JFK,SFO --restaurant-source osm-radius --delay-ms 3000
```

Optional official restaurant detail-page payment scan:

```bash
npm run fetch:data -- --airports SFO,PHL,MSP --restaurant-detail-payment-pages --restaurant-detail-limit 50 --delay-ms 3000
```

This visits official restaurant detail pages after robots.txt checks and writes raw snapshots to `data/raw/restaurant-detail-payments/`. It only emits payment rows when the page explicitly names a method, such as `Visa`, `American Express`, `Apple Pay`, `cashless`, or `credit cards`. On shared directory pages, it applies a fact only when the evidence snippet names the restaurant, so one generic page sentence is not copied to every tenant. Many US airport restaurant pages are silent about payment methods; in that case coverage remains `unknown`.

Full first-20 detail scan:

```bash
npm run fetch:data:payment-pages
```

Optional Google Places generic payment enrichment:

```bash
export GOOGLE_PLACES_API_KEY=your_local_key
npm run fetch:data -- --airports JFK --google-places-payment-options --google-places-limit 25 --delay-ms 3000
```

This can add source-backed generic rows such as `credit_cards`, `debit_cards`, `contactless`, and `cash` when Google returns `paymentOptions` for an exact display-name match. It still does not prove Visa, Mastercard, Amex, Discover, JCB, UnionPay, or Diners Club acceptance.

Reviewed or licensed payment acceptance input:

```bash
cp services/data-fetcher/examples/reviewed_payment_acceptance.example.json data/manual/payment_acceptance.local.json
npm run fetch:data -- --airports JFK --payment-acceptance-file data/manual/payment_acceptance.local.json
```

Product-readiness gate for 90% thresholds:

```bash
npm run fetch:data -- --limit 20 --restaurant-source official --product-readiness
```

Product mode writes outputs and the manifest first, then fails if official airport coverage, restaurant terminal coverage, or known card-network row coverage is below the threshold. Today that failure is expected unless you provide reviewed/licensed payment acceptance coverage.

## Outputs

Generated files are intentionally ignored by git:

```text
data/raw/ourairports/*.csv
data/raw/official-restaurants/*.{json,html}
data/raw/overpass/*.json
data/raw/google-places-payment/*.json
data/raw/restaurant-detail-payments/*.html
data/raw/web-evidence/*.html
data/raw/card-benefits/*.json
data/normalized/airports.json
data/normalized/airports.csv
data/normalized/restaurants.json
data/normalized/restaurants.csv
data/normalized/payment_acceptance.json
data/normalized/payment_acceptance.csv
data/normalized/card_products.json
data/normalized/card_products.csv
data/normalized/benefits.json
data/normalized/benefits.csv
data/manifests/source-manifest.json
data/manifests/official-restaurants.json
data/manifests/web-evidence.json
```

The first 20 airport target list is in `services/data-fetcher/data_fetcher/sources.py`.

## Environment

```bash
DATA_FETCHER_USER_AGENT="SesameKiller-CompassBot/0.1 (+https://github.com/SesameKiller113/SesameKiller-Compass)"
OVERPASS_ENDPOINT="https://overpass-api.de/api/interpreter"
OSM_ASSOCIATION_MODE=area-first
OVERPASS_MAX_RETRIES=2
OVERPASS_RETRY_BACKOFF_MS=30000
FETCH_DELAY_MS=3000
```

Optional future API credentials belong only in local `.env`, never in git or chat:

```bash
FOURSQUARE_API_KEY=
GOOGLE_PLACES_API_KEY=
GOOGLE_PLACES_LIMIT=
VISA_API_KEY=
VISA_SHARED_SECRET=
MASTERCARD_CONSUMER_KEY=
MASTERCARD_KEYSTORE_PATH=
CARD_BENEFITS_FILE=data/manual/card_benefits.local.json
```

The fetcher does not need MongoDB or Neo4j yet; the importer will use those connection strings in the next step.

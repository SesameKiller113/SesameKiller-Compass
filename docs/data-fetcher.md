# Data Fetcher

The data fetcher is the first production-shaped ingestion slice for SesameKiller-Compass. JSON is the canonical normalized format. CSV is exported beside it so the next Graph2Neo4j/MongoDB importer can load the same facts easily.

## Why JSON plus CSV

JSON keeps nested provenance, source notes, raw payment tags, and future schema changes clean. CSV is useful for Neo4j `LOAD CSV`, spreadsheet review, and manual QA. The fetcher writes both from the same normalized records.

## Commands

The fetcher itself currently uses only the Python standard library. You can run it through npm convenience scripts from the repo root, or directly with `PYTHONPATH=services/data-fetcher python3 -m data_fetcher.cli`.

Fast airport-only smoke test:

```bash
npm run fetch:data -- --limit 20 --skip-overpass
```

Live public-data fetch for the first 20 airports:

```bash
npm run fetch:data:live
```

If Overpass returns HTTP 429 or 403, the fetcher stops further Overpass requests immediately and writes a manifest warning. If Overpass returns a transient 504 for one airport, that airport is skipped and the run continues.

Useful narrower run while testing:

```bash
npm run fetch:data -- --airports JFK,SFO,LAX --include-web-evidence --delay-ms 3000 --radius-meters 1500
```

## Outputs

Generated files are intentionally ignored by git:

```text
data/raw/ourairports/*.csv
data/raw/overpass/*.json
data/raw/web-evidence/*.html
data/normalized/airports.json
data/normalized/airports.csv
data/normalized/restaurants.json
data/normalized/restaurants.csv
data/normalized/card_products.json
data/normalized/card_products.csv
data/normalized/benefits.json
data/normalized/benefits.csv
data/manifests/source-manifest.json
data/manifests/web-evidence.json
```

The first 20 airport target list is in `services/data-fetcher/data_fetcher/sources.py`. OSM restaurant records are `near_airport_radius` records, not official terminal inventory, until an official airport source confirms them.

## Environment

```bash
DATA_FETCHER_USER_AGENT="SesameKiller-CompassBot/0.1 (+https://github.com/SesameKiller113/SesameKiller-Compass)"
OVERPASS_ENDPOINT="https://overpass-api.de/api/interpreter"
FETCH_DELAY_MS=3000
```

Do not put MongoDB Atlas, Neo4j AuraDB, Visa, or issuer secrets in chat. Add them to `.env` locally. The fetcher does not need MongoDB or Neo4j yet; the importer will use those connection strings in the next step.

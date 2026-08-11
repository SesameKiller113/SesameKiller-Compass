# Legal Data Policy

This is an engineering compliance note for SesameKiller-Compass, not legal advice. The fetcher is designed to be conservative: use public/open data where the source permits it, keep provenance with every record, respect robots.txt, and do not guess missing facts.

## Sources allowed in this demo

| Source | Use | Legal evidence | Guardrails |
| --- | --- | --- | --- |
| OurAirports `airports.csv` | Airport identity, location, official website URL | OurAirports says its data is public domain: https://ourairports.com/data/ and documents the CSV fields at https://ourairports.com/help/data-dictionary.html | Keep source URL, fetch time, and raw snapshot. Do not treat source data as guaranteed correct. |
| OpenStreetMap through Overpass API | Restaurant-like amenities and explicit `payment:*` tags near airport coordinates | OSM copyright/license page: https://www.openstreetmap.org/copyright/no. OSM attribution guidance: https://osmfoundation.org/wiki/Licence/Attribution_Guidelines. Overpass API docs/fair-use context: https://wiki.openstreetmap.org/wiki/Overpass_API | Use a named user agent, low request rate, no bulk abuse, keep ODbL attribution, and label radius matches as `near_airport_radius` rather than official tenant records. |
| Official airport public homepages | Robots-aware evidence snapshots only | Robots.txt guidance based on the Robots Exclusion Protocol: https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt | Fetch only public homepages from OurAirports `home_link`, check robots.txt first, do not bypass access controls, and do not parse restaurant/payment claims until each airport site is reviewed. |
| Visa Developer / issuer-approved sources | Future card/benefit validation only | Visa VCES docs: https://developer.visa.com/capabilities/vces/docs-getting-started and https://developer.visa.com/capabilities/vces/reference. Visa Developer terms: https://developer.visa.com/terms | No scraping Visa or issuer benefit pages. No production API calls until approval/certification/agreement. No PAN or cardholder data storage. |

## Accuracy policy

Public/open sources cannot give a true 100% correctness guarantee. The project should therefore say "source-backed" instead of "guaranteed correct". Every normalized record includes source name, source URL, license status, fetch time, raw snapshot reference, confidence score, and notes.

The fetcher follows these rules:

- If a payment method is missing from the source, output `unknown`.
- If OSM says `payment:visa=yes`, output `visa`; if OSM is silent, do not infer Visa support.
- If a restaurant is found by coordinate radius, do not present it as confirmed inside a terminal.
- If robots.txt is unavailable, conservative demo mode skips that official website.
- If a source requires approval, credentials, or a license, the demo writes schema-only files and a manifest warning instead of scraping.

## Data not allowed yet

- Visa or issuer card-benefit scraping.
- Logged-in, paywalled, CAPTCHA-protected, private, or undocumented API data.
- Personal cardholder data, PAN values, or payment credentials.
- Bulk Nominatim geocoding. Nominatim has its own policy at https://operations.osmfoundation.org/policies/nominatim/ and is not used by this fetcher by default.

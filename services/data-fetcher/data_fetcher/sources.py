from __future__ import annotations

TARGET_AIRPORT_IATA_CODES = [
    "JFK",
    "LGA",
    "EWR",
    "BOS",
    "ATL",
    "LAX",
    "SFO",
    "SEA",
    "ORD",
    "DFW",
    "DEN",
    "LAS",
    "MIA",
    "MCO",
    "PHX",
    "IAH",
    "CLT",
    "MSP",
    "DTW",
    "PHL",
]

OUR_AIRPORTS_DATA_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
OUR_AIRPORTS_LICENSE_URL = "https://ourairports.com/data/"
OUR_AIRPORTS_DICTIONARY_URL = "https://ourairports.com/help/data-dictionary.html"

DEFAULT_OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
OSM_COPYRIGHT_URL = "https://www.openstreetmap.org/copyright/no"
OSM_ATTRIBUTION_GUIDELINES_URL = "https://osmfoundation.org/wiki/Licence/Attribution_Guidelines"
OVERPASS_API_POLICY_URL = "https://wiki.openstreetmap.org/wiki/Overpass_API"

ROBOTS_SPEC_URL = "https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt"
NOMINATIM_POLICY_URL = "https://operations.osmfoundation.org/policies/nominatim/"

VISA_DEVELOPER_GETTING_STARTED_URL = "https://developer.visa.com/capabilities/vces/docs-getting-started"
VISA_DEVELOPER_REFERENCE_URL = "https://developer.visa.com/capabilities/vces/reference"
VISA_DEVELOPER_TERMS_URL = "https://developer.visa.com/terms"


def base_source_manifest_entries() -> list[dict[str, object]]:
    return [
        {
            "key": "ourairports-airports-csv",
            "sourceName": "OurAirports airports.csv",
            "sourceType": "ourairports",
            "sourceUrl": OUR_AIRPORTS_DATA_URL,
            "licenseStatus": "public-domain",
            "attributionRequired": False,
            "legalBasis": "OurAirports states that its data is public domain and can be used without permission or credit.",
            "allowedUse": "Fetch airport metadata from the published CSV file and keep source timestamps with exported records.",
            "restrictions": [
                "OurAirports does not guarantee accuracy.",
                "Use source attribution in this project even when credit is not required, so downstream users can audit the data.",
            ],
            "evidenceUrls": [OUR_AIRPORTS_LICENSE_URL, OUR_AIRPORTS_DICTIONARY_URL],
        },
        {
            "key": "openstreetmap-overpass",
            "sourceName": "OpenStreetMap via public Overpass API",
            "sourceType": "openstreetmap-overpass",
            "sourceUrl": DEFAULT_OVERPASS_ENDPOINT,
            "licenseStatus": "odbl",
            "attributionRequired": True,
            "legalBasis": "OpenStreetMap data is available under the Open Data Commons Open Database License and requires attribution.",
            "allowedUse": "Fetch OSM amenities around target airports at a slow rate, store OSM IDs and ODbL attribution, and mark missing payment data as unknown.",
            "restrictions": [
                "Do not exceed public Overpass fair-use limits.",
                "Do not remove OSM attribution from product or export views that use OSM-derived data.",
                "OSM records are community maintained and cannot prove official airport tenant status unless an official source confirms it.",
            ],
            "evidenceUrls": [OSM_COPYRIGHT_URL, OSM_ATTRIBUTION_GUIDELINES_URL, OVERPASS_API_POLICY_URL],
        },
        {
            "key": "official-airport-web-evidence",
            "sourceName": "Official airport public web pages",
            "sourceType": "official-web-crawl",
            "sourceUrl": "airport home_link from OurAirports",
            "licenseStatus": "official-public-page",
            "attributionRequired": True,
            "legalBasis": "The crawler only requests public pages, checks robots.txt first, uses a named user agent, and stores evidence snapshots without bypassing access controls.",
            "allowedUse": "Collect conservative evidence metadata from official airport pages where robots.txt permits crawling.",
            "restrictions": [
                "No login pages, paywalled pages, CAPTCHAs, private APIs, or bot-protection bypassing.",
                "Do not extract restaurant or payment claims from arbitrary HTML until a per-site source review is added.",
                "Respect robots.txt and stop crawling when robots.txt is unavailable in this conservative demo mode.",
            ],
            "evidenceUrls": [ROBOTS_SPEC_URL],
        },
        {
            "key": "visa-card-benefits",
            "sourceName": "Visa Developer VCES and issuer-approved benefit sources",
            "sourceType": "visa-developer",
            "sourceUrl": VISA_DEVELOPER_GETTING_STARTED_URL,
            "licenseStatus": "api-approval-required",
            "attributionRequired": True,
            "legalBasis": "Visa Developer documentation allows sandbox exploration, but production use requires Visa review/approval and applicable agreements.",
            "allowedUse": "Keep schemas and compliance notes only until approved API credentials, issuer data, or a licensed benefit feed is available.",
            "restrictions": [
                "Do not scrape Visa or issuer card-benefit pages for production data.",
                "Do not store PAN or other cardholder data in MongoDB, Neo4j, logs, or raw snapshots.",
                "Do not call production Visa APIs until the app has passed the required approval/certification process.",
            ],
            "evidenceUrls": [VISA_DEVELOPER_GETTING_STARTED_URL, VISA_DEVELOPER_REFERENCE_URL, VISA_DEVELOPER_TERMS_URL],
        },
    ]

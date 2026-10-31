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
OVERPASS_API_POLICY_URL = "https://operations.osmfoundation.org/policies/api/"

ROBOTS_SPEC_URL = "https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt"
NOMINATIM_POLICY_URL = "https://operations.osmfoundation.org/policies/nominatim/"

PANYNJ_JFK_DINING_URL = "https://www.jfkairport.com/dine-shop-relax/food"
PANYNJ_LGA_DINING_URL = "https://www.laguardiaairport.com/dine-shop-relax/food"
PANYNJ_EWR_DINING_URL = "https://www.newarkairport.com/dine-shop-relax/food"
PANYNJ_GRAPHQL_URL_PATTERN = "https://{airport_domain}/api/graphql"
SFO_DINING_URL = "https://www.flysfo.com/passengers/shop-dine-relax?content_type=dining"
SEA_DINING_URL = "https://exploresea.org/dining/"
PHX_DINING_URL = "https://www.skyharbor.com/at-the-airport/food-drinks/"
CLT_DINING_URL = "https://www.cltairport.com/en/shop-dine-and-relax/?filters=dine"
IAH_DINING_URL = "https://www.fly2houston.com/iah/shop-dine-relax/?query=restaurants"
DTW_CONCESSIONS_URL = "https://www.metroairport.com/about-us/contact-us/concessions-contacts"
LAX_DINING_URL = "https://www.flylax.com/lax-dining-and-shopping"
MSP_DINING_URL = "https://www.mspairport.com/airport/eat-shop-relax"
PHL_FOODSHOPS_URL = "https://www.phlfoodandshops.com/directory/?_directory_filter=dine"
ATL_RESTAURANTWEEK_URL = "https://www.atl.com/restaurantweek/"
DEN_EATDEN_URL = "https://www.eatden.com/"
LAS_DINING_URL = "https://www.harryreidairport.com/dine-shop-and-more?category=dining"
ORD_DINING_URL = "https://www.flychicago.com/ohare/eatshopmore/eat/Pages/default.aspx"
DFW_DINING_URL = "https://www.dfwairport.com/shop-dine-services/?terminal=all+terminals"

GOOGLE_PLACES_PAYMENT_OPTIONS_URL = "https://developers.google.com/maps/documentation/places/web-service/op-overview"
VISA_VMORC_DOCS_URL = "https://developer.visa.com/capabilities/vmorc/docs"
VISA_OFFERS_NETWORK_TERMS_URL = "https://developer.visa.com/capabilities/visa-offers-network/product-terms"
AMEX_DEVELOPER_DOCS_URL = "https://developer.americanexpress.com/documentation"
MASTERCARD_DEVELOPERS_URL = "https://www.mastercard.com/us/en/innovation/build-with-us/mastercard-developers.html"

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
            "key": "official-airport-restaurant-directories",
            "sourceName": "Reviewed official airport dining directories",
            "sourceType": "official-airport-directory",
            "sourceUrl": "source-specific official dining URLs",
            "licenseStatus": "official-public-page",
            "attributionRequired": True,
            "legalBasis": "The fetcher only uses public airport-operated dining directories after checking robots.txt and stores raw evidence with each run.",
            "allowedUse": "Fetch official restaurant inventory for airports with reviewed adapters and keep source URLs per restaurant.",
            "restrictions": [
                "No login pages, paywalled pages, CAPTCHAs, private APIs, or access-control bypassing.",
                "Do not infer payment methods when the official source is silent.",
                "Only airports with source-specific adapter review are exported as official restaurant inventory.",
            ],
            "evidenceUrls": [
                ROBOTS_SPEC_URL,
                PANYNJ_JFK_DINING_URL,
                PANYNJ_LGA_DINING_URL,
                PANYNJ_EWR_DINING_URL,
                SFO_DINING_URL,
                SEA_DINING_URL,
                PHX_DINING_URL,
                CLT_DINING_URL,
                IAH_DINING_URL,
                DTW_CONCESSIONS_URL,
                LAX_DINING_URL,
                MSP_DINING_URL,
                PHL_FOODSHOPS_URL,
                ATL_RESTAURANTWEEK_URL,
                DEN_EATDEN_URL,
                LAS_DINING_URL,
                ORD_DINING_URL,
                DFW_DINING_URL,
            ],
        },
        {
            "key": "openstreetmap-overpass",
            "sourceName": "OpenStreetMap via public Overpass API",
            "sourceType": "openstreetmap-overpass",
            "sourceUrl": DEFAULT_OVERPASS_ENDPOINT,
            "licenseStatus": "odbl",
            "attributionRequired": True,
            "legalBasis": "OpenStreetMap data is available under the Open Data Commons Open Database License and requires attribution.",
            "allowedUse": "Fetch OSM food amenities inside OSM aerodrome areas, with radius fallback when needed, store OSM IDs and ODbL attribution, and mark missing payment data as unknown.",
            "restrictions": [
                "Do not exceed public Overpass fair-use limits; use a dedicated Overpass endpoint, OSM extract, or commercial OSM provider for repeated 2000+ airport jobs.",
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
                "Respect robots.txt and stop crawling when robots.txt is unavailable in conservative demo mode.",
            ],
            "evidenceUrls": [ROBOTS_SPEC_URL],
        },
        {
            "key": "visa-card-benefits",
            "sourceName": "Visa Developer VCES/VMORC and issuer-approved benefit sources",
            "sourceType": "visa-developer",
            "sourceUrl": VISA_DEVELOPER_GETTING_STARTED_URL,
            "licenseStatus": "api-approval-required",
            "attributionRequired": True,
            "legalBasis": "Visa Developer documentation allows sandbox exploration for eligible APIs, but production benefit/offer use requires Visa review, approval, certification, and applicable agreements. Amex and Mastercard developer resources also require account access and product-specific terms before production use.",
            "allowedUse": "Keep schemas and compliance notes until approved API credentials, issuer data, or a licensed benefit feed is available.",
            "restrictions": [
                "Do not scrape Visa or issuer card-benefit pages for production data.",
                "Do not store PAN or other cardholder data in MongoDB, Neo4j, logs, or raw snapshots.",
                "Do not call production Visa APIs until the app has passed the required approval/certification process.",
            ],
            "evidenceUrls": [
                VISA_DEVELOPER_GETTING_STARTED_URL,
                VISA_DEVELOPER_REFERENCE_URL,
                VISA_DEVELOPER_TERMS_URL,
                VISA_VMORC_DOCS_URL,
                VISA_OFFERS_NETWORK_TERMS_URL,
                AMEX_DEVELOPER_DOCS_URL,
                MASTERCARD_DEVELOPERS_URL,
                GOOGLE_PLACES_PAYMENT_OPTIONS_URL,
            ],
        },
    ]

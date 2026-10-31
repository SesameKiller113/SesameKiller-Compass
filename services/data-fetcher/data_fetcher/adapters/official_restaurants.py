from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse
import json
import re
import time

from data_fetcher.http_client import FetchHttpError, fetch_text
from data_fetcher.io_utils import write_json_file, write_text_file
from data_fetcher.robots import is_path_allowed_by_robots

PANYNJ_DINE_POIS_QUERY = """query GetDinePOIs($airportCode: String!, $options: EnhancedFilterOptions) {
  getDinePOIs(airportCode: $airportCode, options: $options) {
    availableLocations
    availableTerminalAreas
    returnedFilters {
      label
      value
      count
      isAvailable
    }
    results {
      id
      images
      name
      description
      category
      structureName
      floorName
      nearbyLandmark
      mapUrl
    }
    pagination {
      totalResults
      endIndex
      hasNextPage
    }
  }
}
"""

PANYNJ_PAGE_SIZE = 12
LZ_STRING_URI_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-$"
ATL_RESTAURANTWEEK_PATHS = [
    "grab_go",
    "wine_dine",
    "sips_spirits",
    "georgia_grown",
    "unique_delights",
    "famous_favorites",
]
LAS_DINE_SHOP_NEXT_ACTION_NAME = "getDisplayPois"
MSP_FOOD_OFFERING_URLS = [
    "https://www.mspairport.com/terminal-1-food-offerings",
    "https://www.mspairport.com/terminal-2-food-offerings",
]
ROBOTS_TXT_CACHE: dict[str, str | None] = {}


@dataclass(frozen=True)
class OfficialRestaurantSource:
    airport_iata: str
    source_name: str
    directory_url: str
    source_type: str
    parser: str
    graphql_url: str | None = None
    locuslabs_account_id: str | None = None
    locuslabs_venue_id: str | None = None


OFFICIAL_RESTAURANT_SOURCES: dict[str, OfficialRestaurantSource] = {
    "JFK": OfficialRestaurantSource(
        airport_iata="JFK",
        source_name="JFK Airport official dining directory",
        directory_url="https://www.jfkairport.com/dine-shop-relax/food",
        source_type="official-airport-directory-graphql",
        parser="panynj-dine-graphql",
        graphql_url="https://www.jfkairport.com/api/graphql",
        locuslabs_account_id="A119NSPH8JLU80",
        locuslabs_venue_id="jfk",
    ),
    "LGA": OfficialRestaurantSource(
        airport_iata="LGA",
        source_name="LaGuardia Airport official dining directory",
        directory_url="https://www.laguardiaairport.com/dine-shop-relax/food",
        source_type="official-airport-directory-graphql",
        parser="panynj-dine-graphql",
        graphql_url="https://www.laguardiaairport.com/api/graphql",
        locuslabs_account_id="A119NSPH8JLU80",
        locuslabs_venue_id="lga",
    ),
    "EWR": OfficialRestaurantSource(
        airport_iata="EWR",
        source_name="Newark Liberty International Airport official dining directory",
        directory_url="https://www.newarkairport.com/dine-shop-relax/food",
        source_type="official-airport-directory-graphql",
        parser="panynj-dine-graphql",
        graphql_url="https://www.newarkairport.com/api/graphql",
        locuslabs_account_id="A119NSPH8JLU80",
        locuslabs_venue_id="ewr",
    ),
    "SFO": OfficialRestaurantSource(
        airport_iata="SFO",
        source_name="San Francisco International Airport official dining directory",
        directory_url="https://www.flysfo.com/passengers/shop-dine-relax?content_type=dining",
        source_type="official-airport-directory-html",
        parser="sfo-dining-html",
    ),
    "SEA": OfficialRestaurantSource(
        airport_iata="SEA",
        source_name="SEA Airport Dining and Retail public dining directory",
        directory_url="https://exploresea.org/dining/",
        source_type="official-airport-concession-directory-html",
        parser="sea-explore-dining-html",
    ),
    "PHX": OfficialRestaurantSource(
        airport_iata="PHX",
        source_name="Phoenix Sky Harbor official food and drinks directory",
        directory_url="https://www.skyharbor.com/at-the-airport/food-drinks/",
        source_type="official-airport-directory-html",
        parser="phx-food-html",
    ),
    "CLT": OfficialRestaurantSource(
        airport_iata="CLT",
        source_name="Charlotte Douglas official shop, dine, and relax directory",
        directory_url="https://www.cltairport.com/en/shop-dine-and-relax/?filters=dine",
        source_type="official-airport-directory-next-data",
        parser="clt-next-data",
    ),
    "IAH": OfficialRestaurantSource(
        airport_iata="IAH",
        source_name="Houston Airports IAH official shop, dine, and relax directory",
        directory_url="https://www.fly2houston.com/iah/shop-dine-relax/?query=restaurants",
        source_type="official-airport-directory-next-data",
        parser="iah-next-flight",
    ),
    "DTW": OfficialRestaurantSource(
        airport_iata="DTW",
        source_name="Detroit Metro official concessions contacts dining list",
        directory_url="https://www.metroairport.com/about-us/contact-us/concessions-contacts",
        source_type="official-airport-directory-html",
        parser="dtw-concessions-html",
    ),
    "LAX": OfficialRestaurantSource(
        airport_iata="LAX",
        source_name="Los Angeles International Airport official dining and shopping directory",
        directory_url="https://www.flylax.com/lax-dining-and-shopping",
        source_type="official-airport-directory-drupal-json",
        parser="lax-drupal-tenants",
    ),
    "ORD": OfficialRestaurantSource(
        airport_iata="ORD",
        source_name="Chicago O'Hare official Eat/Shop/More dining directory",
        directory_url="https://www.flychicago.com/ohare/eatshopmore/eat/Pages/default.aspx",
        source_type="official-airport-directory-locuslabs-public-map-data",
        parser="locuslabs-pois",
        locuslabs_account_id="A1UY6J33FTHAJ8",
        locuslabs_venue_id="ord",
    ),
    "DFW": OfficialRestaurantSource(
        airport_iata="DFW",
        source_name="Dallas Fort Worth official Shop, Dine, Services directory",
        directory_url="https://www.dfwairport.com/shop-dine-services/?terminal=all+terminals",
        source_type="official-airport-directory-locuslabs-public-map-data",
        parser="locuslabs-pois",
        locuslabs_account_id="A1GKNNFXZEQW1J",
        locuslabs_venue_id="dfw",
    ),
    "ATL": OfficialRestaurantSource(
        airport_iata="ATL",
        source_name="Hartsfield-Jackson Atlanta International Airport official restaurant week dining pages",
        directory_url="https://www.atl.com/restaurantweek/",
        source_type="official-airport-directory-html",
        parser="atl-restaurantweek-html",
    ),
    "DEN": OfficialRestaurantSource(
        airport_iata="DEN",
        source_name="Denver International Airport Eat DEN public dining directory",
        directory_url="https://www.eatden.com/",
        source_type="official-airport-directory-html",
        parser="den-eatden-html",
    ),
    "LAS": OfficialRestaurantSource(
        airport_iata="LAS",
        source_name="Harry Reid International Airport official Shop, Dine, and More directory",
        directory_url="https://www.harryreidairport.com/dine-shop-and-more?category=dining",
        source_type="official-airport-directory-next-action",
        parser="las-next-display-pois",
    ),
    "MSP": OfficialRestaurantSource(
        airport_iata="MSP",
        source_name="Minneapolis-St. Paul Airport official Eat, Shop, Relax directory",
        directory_url="https://www.mspairport.com/airport/eat-shop-relax",
        source_type="official-airport-directory-html",
        parser="msp-vendor-cards",
    ),
    "PHL": OfficialRestaurantSource(
        airport_iata="PHL",
        source_name="PHL Food & Shops dining directory linked from Philadelphia International Airport",
        directory_url="https://www.phlfoodandshops.com/directory/?_directory_filter=dine",
        source_type="official-airport-concession-directory-html",
        parser="phl-foodshops-html",
    ),
}


def fetch_official_restaurants_for_airports(
    airports: list[dict[str, object]],
    *,
    fetched_at: str,
    raw_root: Path,
    user_agent: str,
    delay_ms: int,
    logger: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    restaurants: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    warnings: list[str] = []
    log = logger or (lambda _message: None)

    for index, airport in enumerate(airports, start=1):
        airport_iata = str(airport.get("iataCode") or "").upper()
        source = OFFICIAL_RESTAURANT_SOURCES.get(airport_iata)
        if not source:
            warning = f"No reviewed official restaurant source adapter configured for {airport_iata}."
            warnings.append(warning)
            evidence.append(
                {
                    "airportIata": airport_iata,
                    "status": "unsupported",
                    "recordCount": 0,
                    "warning": warning,
                }
            )
            continue

        log(f"[Official restaurants] {index}/{len(airports)} fetching {airport_iata} from {source.source_name}.")
        try:
            if source.parser == "panynj-dine-graphql":
                source_records, source_evidence = fetch_panynj_dining_directory(
                    source,
                    fetched_at=fetched_at,
                    raw_root=raw_root,
                    user_agent=user_agent,
                    delay_ms=delay_ms,
                )
            elif source.parser == "sfo-dining-html":
                source_records, source_evidence = fetch_sfo_dining_directory(
                    source,
                    fetched_at=fetched_at,
                    raw_root=raw_root,
                    user_agent=user_agent,
                )
            elif source.parser == "phl-foodshops-html":
                source_records, source_evidence = fetch_phl_foodshops_directory(
                    source,
                    fetched_at=fetched_at,
                    raw_root=raw_root,
                    user_agent=user_agent,
                    delay_ms=delay_ms,
                )
            elif source.parser == "atl-restaurantweek-html":
                source_records, source_evidence = fetch_atl_restaurantweek_directory(
                    source,
                    fetched_at=fetched_at,
                    raw_root=raw_root,
                    user_agent=user_agent,
                    delay_ms=delay_ms,
                )
            elif source.parser == "las-next-display-pois":
                source_records, source_evidence = fetch_las_display_pois_directory(
                    source,
                    fetched_at=fetched_at,
                    raw_root=raw_root,
                    user_agent=user_agent,
                )
            elif source.parser == "msp-vendor-cards":
                source_records, source_evidence = fetch_msp_vendor_directory(
                    source,
                    fetched_at=fetched_at,
                    raw_root=raw_root,
                    user_agent=user_agent,
                    delay_ms=delay_ms,
                )
            elif source.parser == "locuslabs-pois":
                source_records, source_evidence = fetch_locuslabs_poi_directory(
                    source,
                    fetched_at=fetched_at,
                    raw_root=raw_root,
                    user_agent=user_agent,
                )
            elif source.parser in {
                "phx-food-html",
                "clt-next-data",
                "iah-next-flight",
                "dtw-concessions-html",
                "lax-drupal-tenants",
                "sea-explore-dining-html",
                "den-eatden-html",
            }:
                source_records, source_evidence = fetch_single_page_dining_directory(
                    source,
                    fetched_at=fetched_at,
                    raw_root=raw_root,
                    user_agent=user_agent,
                )
            else:
                raise RuntimeError(f"Unsupported official restaurant parser {source.parser}")

            restaurants.extend(source_records)
            evidence.append(source_evidence)
            if source_evidence.get("status") == "partial":
                partial_warning = f"Official restaurant fetch partial for {airport_iata}: {source_evidence.get('warning')}"
                warnings.append(partial_warning)
                log(f"[Official restaurants] {airport_iata} partial: {source_evidence.get('warning')}")
            log(f"[Official restaurants] {airport_iata} normalized {len(source_records)} official dining records.")
        except Exception as error:
            warning = f"Official restaurant fetch failed for {airport_iata}: {error}"
            warnings.append(warning)
            evidence.append(
                {
                    "airportIata": airport_iata,
                    "sourceUrl": source.directory_url,
                    "sourceType": source.source_type,
                    "status": "failed",
                    "recordCount": 0,
                    "warning": str(error),
                }
            )
            log(f"[Official restaurants] {airport_iata} failed: {error}")

        sleep_ms(delay_ms)

    return sorted(restaurants, key=lambda record: (str(record["airportIata"]), str(record["name"]))), evidence, warnings


def fetch_panynj_dining_directory(
    source: OfficialRestaurantSource,
    *,
    fetched_at: str,
    raw_root: Path,
    user_agent: str,
    delay_ms: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    assert source.graphql_url is not None
    check_robots_or_raise(source.directory_url, user_agent)
    check_robots_or_raise(source.graphql_url, user_agent)

    records: list[dict[str, object]] = []
    raw_refs: list[str] = []
    offset = 1
    page_number = 1
    has_next_page = True

    while has_next_page:
        raw_ref = str(Path("raw") / "official-restaurants" / f"{source.airport_iata}-panynj-page-{page_number}-{safe_timestamp(fetched_at)}.json")
        raw_json = fetch_panynj_graphql_page(
            source.graphql_url,
            source.airport_iata,
            offset=offset,
            page_size=PANYNJ_PAGE_SIZE,
            user_agent=user_agent,
            referer=source.directory_url,
        )
        write_json_file(raw_root.parent / raw_ref, raw_json)
        raw_refs.append(raw_ref)

        payload = raw_json.get("data", {}).get("getDinePOIs") if isinstance(raw_json, dict) else None
        if not isinstance(payload, dict):
            raise RuntimeError("PANYNJ GraphQL response did not contain data.getDinePOIs")

        page_results = payload.get("results")
        if not isinstance(page_results, list):
            raise RuntimeError("PANYNJ GraphQL response did not contain a results list")

        records.extend(
            normalize_panynj_dining_records(
                page_results,
                source=source,
                fetched_at=fetched_at,
                raw_ref=raw_ref,
            )
        )

        pagination = payload.get("pagination") if isinstance(payload.get("pagination"), dict) else {}
        has_next_page = bool(pagination.get("hasNextPage"))
        end_index = int(pagination.get("endIndex") or 0)
        offset = end_index + 1 if end_index else offset + PANYNJ_PAGE_SIZE
        page_number += 1
        if has_next_page:
            sleep_ms(delay_ms)

    enrichment_warning = None
    enrichment_manifest_url = None
    if source.locuslabs_account_id and source.locuslabs_venue_id:
        try:
            records, enrichment_raw_refs, enrichment_manifest_url = enrich_panynj_records_with_locuslabs(
                records,
                source=source,
                fetched_at=fetched_at,
                raw_root=raw_root,
                user_agent=user_agent,
            )
            raw_refs.extend(enrichment_raw_refs)
        except Exception as error:
            enrichment_warning = f"PANYNJ map-data enrichment skipped: {error}"

    normalized = dedupe_restaurants(records)
    return normalized, {
        "airportIata": source.airport_iata,
        "sourceName": source.source_name,
        "sourceType": source.source_type,
        "sourceUrl": source.directory_url,
        "graphqlUrl": source.graphql_url,
        "dataManifestUrl": enrichment_manifest_url,
        "status": "partial" if enrichment_warning else "ok",
        "recordCount": len(normalized),
        "warning": enrichment_warning,
        "rawRefs": raw_refs,
    }


def fetch_panynj_graphql_page(
    graphql_url: str,
    airport_iata: str,
    *,
    offset: int,
    page_size: int,
    user_agent: str,
    referer: str,
) -> dict[str, object]:
    request_body = {
        "operationName": "GetDinePOIs",
        "variables": {
            "airportCode": airport_iata,
            "options": {
                "offset": offset,
                "pageSize": page_size,
            },
        },
        "query": PANYNJ_DINE_POIS_QUERY,
    }
    compressed_body = compress_to_encoded_uri_component(json.dumps(request_body, separators=(",", ":")))
    response = fetch_text(
        graphql_url,
        method="POST",
        data=compressed_body.encode("utf-8"),
        user_agent=user_agent,
        timeout_seconds=30,
        headers={
            "Accept": "application/json, application/graphql-response+json, */*",
            "Content-Type": "text/plain",
            "Referer": referer,
            "x-airport-code": airport_iata,
        },
    )
    try:
        parsed = json.loads(response.body)
    except json.JSONDecodeError as error:
        preview = response.body[:180].replace("\n", " ")
        raise RuntimeError(f"PANYNJ GraphQL returned non-JSON response: {preview}") from error
    if not isinstance(parsed, dict):
        raise RuntimeError("PANYNJ GraphQL returned a non-object JSON response")
    if parsed.get("errors"):
        raise RuntimeError(f"PANYNJ GraphQL returned errors: {parsed.get('errors')}")
    return parsed


def fetch_sfo_dining_directory(
    source: OfficialRestaurantSource,
    *,
    fetched_at: str,
    raw_root: Path,
    user_agent: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    check_robots_or_raise(source.directory_url, user_agent)
    raw_ref = str(Path("raw") / "official-restaurants" / f"{source.airport_iata}-sfo-dining-{safe_timestamp(fetched_at)}.html")
    response = fetch_text(source.directory_url, user_agent=user_agent, timeout_seconds=30)
    write_text_file(raw_root.parent / raw_ref, response.body)
    records = parse_sfo_dining_cards(response.body, source=source, fetched_at=fetched_at, raw_ref=raw_ref)
    return records, {
        "airportIata": source.airport_iata,
        "sourceName": source.source_name,
        "sourceType": source.source_type,
        "sourceUrl": source.directory_url,
        "status": "ok",
        "recordCount": len(records),
        "rawRefs": [raw_ref],
    }



def fetch_single_page_dining_directory(
    source: OfficialRestaurantSource,
    *,
    fetched_at: str,
    raw_root: Path,
    user_agent: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    check_robots_or_raise(source.directory_url, user_agent)
    raw_ref = str(
        Path("raw")
        / "official-restaurants"
        / f"{source.airport_iata}-{slugify(source.parser)}-{safe_timestamp(fetched_at)}.html"
    )
    response = fetch_text(source.directory_url, user_agent=user_agent, timeout_seconds=45)
    if looks_like_access_challenge(response.body):
        raise RuntimeError("source returned an access challenge; skipping because bypassing bot protection is not allowed")
    write_text_file(raw_root.parent / raw_ref, response.body)

    if source.parser == "phx-food-html":
        records = parse_phx_food_cards(response.body, source=source, fetched_at=fetched_at, raw_ref=raw_ref)
    elif source.parser == "clt-next-data":
        records = parse_clt_next_data_restaurants(response.body, source=source, fetched_at=fetched_at, raw_ref=raw_ref)
    elif source.parser == "iah-next-flight":
        records = parse_iah_next_flight_restaurants(response.body, source=source, fetched_at=fetched_at, raw_ref=raw_ref)
    elif source.parser == "dtw-concessions-html":
        records = parse_dtw_concessions_dining(response.body, source=source, fetched_at=fetched_at, raw_ref=raw_ref)
    elif source.parser == "lax-drupal-tenants":
        records = parse_lax_drupal_tenants(response.body, source=source, fetched_at=fetched_at, raw_ref=raw_ref)
    elif source.parser == "msp-vendor-cards":
        records = parse_msp_vendor_cards(response.body, source=source, fetched_at=fetched_at, raw_ref=raw_ref)
    elif source.parser == "sea-explore-dining-html":
        records = parse_sea_explore_dining_cards(response.body, source=source, fetched_at=fetched_at, raw_ref=raw_ref)
    elif source.parser == "den-eatden-html":
        records = parse_den_eatden_cards(response.body, source=source, fetched_at=fetched_at, raw_ref=raw_ref)
    else:
        raise RuntimeError(f"Unsupported single-page parser {source.parser}")

    return records, {
        "airportIata": source.airport_iata,
        "sourceName": source.source_name,
        "sourceType": source.source_type,
        "sourceUrl": source.directory_url,
        "status": "ok",
        "recordCount": len(records),
        "rawRefs": [raw_ref],
    }


def fetch_atl_restaurantweek_directory(
    source: OfficialRestaurantSource,
    *,
    fetched_at: str,
    raw_root: Path,
    user_agent: str,
    delay_ms: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    records: list[dict[str, object]] = []
    raw_refs: list[str] = []
    page_failures: list[str] = []

    for page_slug in ATL_RESTAURANTWEEK_PATHS:
        page_url = urljoin(source.directory_url, f"{page_slug}/")
        try:
            check_robots_or_raise(page_url, user_agent)
            raw_ref = str(
                Path("raw")
                / "official-restaurants"
                / f"{source.airport_iata}-atl-{slugify(page_slug)}-{safe_timestamp(fetched_at)}.html"
            )
            response = fetch_text(page_url, user_agent=user_agent, timeout_seconds=45)
            if looks_like_access_challenge(response.body):
                page_failures.append(f"{page_url}: source returned an access challenge")
                continue
            write_text_file(raw_root.parent / raw_ref, response.body)
            raw_refs.append(raw_ref)
            records.extend(
                parse_atl_restaurantweek_page(
                    response.body,
                    source=source,
                    fetched_at=fetched_at,
                    raw_ref=raw_ref,
                    page_url=page_url,
                    category_slug=page_slug,
                )
            )
        except FetchHttpError as error:
            page_failures.append(f"{page_url}: HTTP {error.status}")
        except Exception as error:
            page_failures.append(f"{page_url}: {error}")
        sleep_ms(delay_ms)

    normalized = dedupe_restaurants(records)
    if not normalized:
        failure_detail = "; ".join(page_failures) or "no restaurant rows parsed"
        raise RuntimeError(f"ATL restaurant-week pages produced no rows: {failure_detail}")

    status = "partial" if page_failures else "ok"
    warning = f"Skipped {len(page_failures)} ATL restaurant-week pages: {'; '.join(page_failures)}" if page_failures else None
    return normalized, {
        "airportIata": source.airport_iata,
        "sourceName": source.source_name,
        "sourceType": source.source_type,
        "sourceUrl": source.directory_url,
        "status": status,
        "recordCount": len(normalized),
        "warning": warning,
        "pageFailures": page_failures,
        "rawRefs": raw_refs,
    }


def fetch_las_display_pois_directory(
    source: OfficialRestaurantSource,
    *,
    fetched_at: str,
    raw_root: Path,
    user_agent: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    check_robots_or_raise(source.directory_url, user_agent)
    raw_refs: list[str] = []
    page_ref = str(
        Path("raw")
        / "official-restaurants"
        / f"{source.airport_iata}-las-directory-page-{safe_timestamp(fetched_at)}.html"
    )
    page_response = fetch_text(source.directory_url, user_agent=user_agent, timeout_seconds=45)
    if looks_like_access_challenge(page_response.body):
        raise RuntimeError("source returned an access challenge; skipping because bypassing bot protection is not allowed")
    write_text_file(raw_root.parent / page_ref, page_response.body)
    raw_refs.append(page_ref)

    action_id = extract_las_next_action_id(page_response.body)
    for script_src in las_next_page_script_urls(page_response.body, source.directory_url):
        if action_id:
            break
        check_robots_or_raise(script_src, user_agent)
        chunk_ref = str(
            Path("raw")
            / "official-restaurants"
            / f"{source.airport_iata}-las-page-chunk-{safe_timestamp(fetched_at)}.js"
        )
        chunk_response = fetch_text(script_src, user_agent=user_agent, timeout_seconds=45)
        write_text_file(raw_root.parent / chunk_ref, chunk_response.body)
        raw_refs.append(chunk_ref)
        action_id = extract_las_next_action_id(chunk_response.body)

    if not action_id:
        raise RuntimeError("Harry Reid directory page did not expose the public getDisplayPois server action id")

    rsc_ref = str(
        Path("raw")
        / "official-restaurants"
        / f"{source.airport_iata}-las-display-pois-{safe_timestamp(fetched_at)}.txt"
    )
    response = fetch_text(
        source.directory_url,
        method="POST",
        data=b"[]",
        user_agent=user_agent,
        timeout_seconds=45,
        headers={
            "Accept": "text/x-component, */*",
            "Content-Type": "text/plain;charset=UTF-8",
            "Next-Action": action_id,
            "RSC": "1",
            "Referer": source.directory_url,
        },
    )
    write_text_file(raw_root.parent / rsc_ref, response.body)
    raw_refs.append(rsc_ref)
    pois = parse_las_display_pois_payload(response.body)
    records = normalize_las_display_pois(pois, source=source, fetched_at=fetched_at, raw_ref=rsc_ref)
    return records, {
        "airportIata": source.airport_iata,
        "sourceName": source.source_name,
        "sourceType": source.source_type,
        "sourceUrl": source.directory_url,
        "status": "ok",
        "recordCount": len(records),
        "rawRefs": raw_refs,
    }


def fetch_locuslabs_poi_directory(
    source: OfficialRestaurantSource,
    *,
    fetched_at: str,
    raw_root: Path,
    user_agent: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if not source.locuslabs_account_id or not source.locuslabs_venue_id:
        raise RuntimeError("LocusLabs source is missing account or venue id")

    check_robots_or_raise(source.directory_url, user_agent)
    manifest_url = f"https://a.locuslabs.com/accounts/{source.locuslabs_account_id}/v5.json"
    check_robots_or_raise(manifest_url, user_agent)

    raw_refs: list[str] = []
    manifest_ref = str(
        Path("raw")
        / "official-restaurants"
        / f"{source.airport_iata}-locuslabs-manifest-{safe_timestamp(fetched_at)}.json"
    )
    manifest_response = fetch_text(manifest_url, user_agent=user_agent, timeout_seconds=45, headers={"Referer": source.directory_url})
    manifest = parse_json_object(manifest_response.body, "LocusLabs manifest")
    write_json_file(raw_root.parent / manifest_ref, manifest)
    raw_refs.append(manifest_ref)

    venue_manifest = manifest.get(source.locuslabs_venue_id)
    if not isinstance(venue_manifest, dict):
        raise RuntimeError(f"LocusLabs manifest did not contain venue {source.locuslabs_venue_id}")
    files = venue_manifest.get("files") if isinstance(venue_manifest.get("files"), dict) else {}
    pois_url = clean_text(files.get("pois"))
    venue_data_url = clean_text(files.get("venueData"))
    if not pois_url or not venue_data_url:
        raise RuntimeError("LocusLabs manifest did not expose POI and venueData files")

    pois_ref = str(
        Path("raw")
        / "official-restaurants"
        / f"{source.airport_iata}-locuslabs-pois-{safe_timestamp(fetched_at)}.json"
    )
    pois_response = fetch_text(pois_url, user_agent=user_agent, timeout_seconds=60, headers={"Referer": source.directory_url})
    pois_payload = parse_json_object(pois_response.body, "LocusLabs POIs")
    write_json_file(raw_root.parent / pois_ref, pois_payload)
    raw_refs.append(pois_ref)

    venue_ref = str(
        Path("raw")
        / "official-restaurants"
        / f"{source.airport_iata}-locuslabs-venueData-{safe_timestamp(fetched_at)}.json"
    )
    venue_response = fetch_text(venue_data_url, user_agent=user_agent, timeout_seconds=60, headers={"Referer": source.directory_url})
    venue_payload = parse_json_object(venue_response.body, "LocusLabs venueData")
    write_json_file(raw_root.parent / venue_ref, venue_payload)
    raw_refs.append(venue_ref)

    records = normalize_locuslabs_pois(
        pois_payload,
        venue_payload,
        source=source,
        fetched_at=fetched_at,
        raw_ref=pois_ref,
    )
    return records, {
        "airportIata": source.airport_iata,
        "sourceName": source.source_name,
        "sourceType": source.source_type,
        "sourceUrl": source.directory_url,
        "dataManifestUrl": manifest_url,
        "status": "ok",
        "recordCount": len(records),
        "rawRefs": raw_refs,
    }


def parse_atl_restaurantweek_page(
    html_text: str,
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_ref: str,
    page_url: str,
    category_slug: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    body_start = html_text.lower().find("</head>")
    body_text = html_text[body_start + len("</head>") :] if body_start >= 0 else html_text
    for list_item in re.findall(r"<li[^>]*>(.*?)</li>", body_text, flags=re.IGNORECASE | re.DOTALL):
        text = html_to_text(list_item)
        parts = re.split(r"\s+(?:-|\u2013|\u2014)\s+", text, maxsplit=1)
        if len(parts) != 2:
            continue
        name = clean_text(parts[0])
        if not is_probable_restaurant_name(name) or "vending" in name.lower():
            continue
        for location in split_atl_locations(parts[1]):
            terminal = atl_terminal_from_location(location)
            gate = atl_gate_from_location(location)
            if not terminal and not gate and "atrium" not in location.lower():
                continue
            location_description = ", ".join(part for part in [terminal, location] if part)
            source_id = f"{slugify(name)}-{slugify(location)}"
            detail_url = f"{page_url}#{quote(slugify(name))}-{quote(slugify(location))}"
            records.append(
                official_restaurant_record(
                    source=source,
                    source_id=source_id,
                    name=name,
                    fetched_at=fetched_at,
                    raw_ref=raw_ref,
                    official_source_path=detail_url,
                    source_url=page_url,
                    official_category=category_slug.replace("_", " "),
                    terminal=terminal,
                    gate=gate,
                    location_description=location_description,
                    feature_tags=[category_slug.replace("_", " ")],
                    confidence_score=0.86,
                    notes=[
                        "Restaurant is listed on ATL's official public restaurant-week dining category pages.",
                        "ATL category pages are official but may be category/event-oriented rather than a complete passenger directory.",
                    ],
                )
            )
    return dedupe_restaurants(records)


def parse_den_eatden_cards(
    html_text: str,
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    blocks = split_top_level_blocks(html_text, r'<section id="[^"]+"[^>]+wixui-column-strip')
    if not blocks:
        raise RuntimeError("Eat DEN page did not contain Wix restaurant sections")

    records: list[dict[str, object]] = []
    for block in blocks:
        title_candidates = [
            html_to_text(value)
            for value in re.findall(r"<h1[^>]*font-size:\s*37px[^>]*>.*?</h1>", block, flags=re.IGNORECASE | re.DOTALL)
        ]
        name = next((candidate for candidate in title_candidates if is_probable_restaurant_name(candidate)), "")
        if not name:
            continue

        location_text = " ".join(
            html_to_text(value)
            for value in re.findall(r"<h1[^>]*font-size:\s*26px[^>]*>.*?</h1>", block, flags=re.IGNORECASE | re.DOTALL)
        )
        terminals = den_terminals_from_text(location_text)
        if not terminals:
            continue
        description = den_description_from_location_text(location_text)
        href = first_group(r'<a[^>]+href="([^"]+)"', block)
        detail_url = urljoin(source.directory_url, unescape(href)) if href else f"{source.directory_url}#{slugify(name)}"
        image_urls = [urljoin(source.directory_url, unescape(value)) for value in re.findall(r'<img[^>]+src="([^"]+)"', block)]

        for terminal in terminals:
            source_id = f"{slugify(name)}-{slugify(terminal)}"
            records.append(
                official_restaurant_record(
                    source=source,
                    source_id=source_id,
                    name=name,
                    fetched_at=fetched_at,
                    raw_ref=raw_ref,
                    official_source_path=detail_url,
                    source_url=source.directory_url,
                    official_category="dining",
                    description=description,
                    terminal=terminal,
                    location_description=", ".join(part for part in [terminal, description] if part),
                    image_urls=image_urls[:3],
                    confidence_score=0.9,
                    notes=[
                        "Restaurant is listed on Denver International Airport's public Eat DEN dining directory.",
                        "When the source lists multiple concourses for one concept, the fetcher emits one row per concourse.",
                    ],
                )
            )
    return dedupe_restaurants(records)


def parse_las_display_pois_payload(body: str) -> list[object]:
    for line in body.splitlines():
        if line.startswith("1:["):
            payload = json.loads(line[2:])
            if not isinstance(payload, list):
                raise RuntimeError("Harry Reid display POIs response line 1 was not a list")
            return payload
    match = re.search(r"(?m)^1:(\[.*\])$", body, flags=re.DOTALL)
    if match:
        payload = json.loads(match.group(1))
        if isinstance(payload, list):
            return payload
    raise RuntimeError("Harry Reid display POIs response did not contain a JSON POI list")


def normalize_las_display_pois(
    pois: list[object],
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for item in pois:
        if not isinstance(item, dict):
            continue
        if clean_text(item.get("category")).lower() != "dining":
            continue
        name = clean_text(item.get("name"))
        poi_id = clean_text(item.get("id"))
        if not name or not poi_id or "vending" in name.lower():
            continue
        location = item.get("location") if isinstance(item.get("location"), dict) else {}
        terminal = normalize_las_terminal(location.get("terminal"))
        landmark = clean_text(location.get("landmark")) or None
        gate = gate_from_text(location.get("gate")) or gate_from_text(landmark)
        security_area = las_security_area(location.get("isAfterSecurity"))
        detail_url = f"{source.directory_url}#poi-{quote(poi_id)}"
        image_url = clean_text(item.get("image"))
        operation_hours = optional_source_text(item.get("operationHours"))
        tags = clean_tag_list(item.get("keywords"))
        if operation_hours:
            tags.append(f"hours: {operation_hours}")
        records.append(
            official_restaurant_record(
                source=source,
                source_id=poi_id,
                name=name,
                fetched_at=fetched_at,
                raw_ref=raw_ref,
                official_source_path=detail_url,
                source_url=source.directory_url,
                official_category="dining",
                terminal=terminal,
                security_area=security_area,
                gate=gate,
                location_description=", ".join(part for part in [terminal, landmark, gate] if part),
                image_urls=[urljoin(source.directory_url, image_url)] if image_url else [],
                feature_tags=tags,
                confidence_score=0.93,
                notes=[
                    "Restaurant is returned by Harry Reid International Airport's public Shop, Dine, and More directory data.",
                    "Only source category=dining records are exported; payment acceptance remains unknown unless separately sourced.",
                ],
            )
        )
    return dedupe_restaurants(records)



def normalize_locuslabs_pois(
    pois_payload: dict[str, object],
    venue_payload: dict[str, object],
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    venue = venue_payload.get(source.locuslabs_venue_id or "") if isinstance(venue_payload, dict) else None
    floor_lookup = locuslabs_floor_lookup(venue if isinstance(venue, dict) else {})
    records: list[dict[str, object]] = []

    for item in pois_payload.values():
        if not isinstance(item, dict):
            continue
        official_category = clean_text(item.get("category")).lower()
        if not official_category.startswith("eat") or official_category.startswith("eat.vending"):
            continue
        name = clean_text(item.get("name"))
        poi_id = clean_text(item.get("poiId") or item.get("id"))
        if not name or not poi_id or "vending" in name.lower():
            continue

        position = item.get("position") if isinstance(item.get("position"), dict) else {}
        floor_id = clean_text(position.get("floorId"))
        terminal, floor_name = floor_lookup.get(floor_id, (locuslabs_terminal_from_floor_id(floor_id), None))
        nearby_landmark = clean_text(item.get("nearbyLandmark")) or None
        description = clean_text(item.get("description")) or None
        operation_hours = optional_source_text(item.get("operationHours"))
        security_area = locuslabs_security_area(item.get("isAfterSecurity"))
        gate = gate_from_text(nearby_landmark) or gate_from_text(description)
        source_path = f"{source.directory_url}#poi-{quote(poi_id)}"

        tags = locuslabs_keyword_tags(item.get("keywords"))
        if operation_hours:
            tags.append(f"hours: {operation_hours}")

        records.append(
            official_restaurant_record(
                source=source,
                source_id=poi_id,
                name=name,
                fetched_at=fetched_at,
                raw_ref=raw_ref,
                official_source_path=source_path,
                source_url=source.directory_url,
                official_category=official_category,
                description=description,
                terminal=terminal,
                security_area=security_area,
                gate=gate,
                location_description=", ".join(part for part in [terminal, floor_name, nearby_landmark, gate] if part),
                latitude=coerce_float(position.get("latitude")),
                longitude=coerce_float(position.get("longitude")),
                map_url=clean_text(item.get("mapUrl")) or None,
                image_urls=locuslabs_image_urls(item, source=source),
                feature_tags=tags,
                confidence_score=0.93,
                notes=[
                    "Restaurant is listed in the airport's official public directory map data loaded by the airport dining page.",
                    "Vending-machine POIs are excluded from restaurant inventory; payment acceptance remains unknown unless separately sourced.",
                ],
            )
        )

    return dedupe_restaurants(records)


def normalize_panynj_dining_records(
    page_results: list[object],
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for item in page_results:
        if not isinstance(item, dict):
            continue
        poi_id = clean_text(item.get("id"))
        name = clean_text(item.get("name"))
        if not poi_id or not name:
            continue
        terminal = clean_text(item.get("structureName")) or None
        nearby_landmark = clean_text(item.get("nearbyLandmark")) or None
        floor_name = clean_text(item.get("floorName")) or None
        category = clean_text(item.get("category")) or "eat"
        gate = gate_from_text(nearby_landmark) or gate_from_text(floor_name)
        detail_path = build_panynj_detail_path(source.directory_url, poi_id, name, terminal)
        records.append(
            {
                "id": f"official:{source.airport_iata.lower()}:panynj:{poi_id}",
                "airportIata": source.airport_iata,
                "name": name,
                "category": "restaurant",
                "officialCategory": category,
                "description": clean_text(item.get("description")) or None,
                "associationScope": "official_airport_directory",
                "latitude": None,
                "longitude": None,
                "terminal": terminal,
                "securityArea": None,
                "gate": gate,
                "locationDescription": ", ".join(part for part in [terminal, floor_name, nearby_landmark, gate] if part),
                "paymentMethods": ["unknown"],
                "paymentEvidence": "not_provided_by_source",
                "rawPaymentTags": {},
                "officialSourceId": poi_id,
                "officialSourcePath": detail_path,
                "mapUrl": clean_text(item.get("mapUrl")) or None,
                "imageUrls": item.get("images") if isinstance(item.get("images"), list) else [],
                "osmType": None,
                "osmId": None,
                "source": {
                    "sourceName": source.source_name,
                    "sourceType": source.source_type,
                    "sourceUrl": detail_path or source.directory_url,
                    "licenseStatus": "official-public-page",
                    "attributionRequired": True,
                    "fetchedAt": fetched_at,
                    "rawRef": raw_ref,
                    "confidenceScore": 0.96,
                    "notes": [
                        "Restaurant is returned by the airport operator's public dining directory.",
                        "Payment methods remain unknown unless the source gives an explicit per-restaurant or reviewed general claim.",
                    ],
                },
            }
        )
    return records


def enrich_panynj_records_with_locuslabs(
    records: list[dict[str, object]],
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_root: Path,
    user_agent: str,
) -> tuple[list[dict[str, object]], list[str], str]:
    if not source.locuslabs_account_id or not source.locuslabs_venue_id:
        return records, [], ""

    manifest_url = f"https://a.locuslabs.com/accounts/{source.locuslabs_account_id}/v5.json"
    check_robots_or_raise(manifest_url, user_agent)
    raw_refs: list[str] = []

    manifest_ref = str(
        Path("raw")
        / "official-restaurants"
        / f"{source.airport_iata}-panynj-locuslabs-manifest-{safe_timestamp(fetched_at)}.json"
    )
    manifest_response = fetch_text(manifest_url, user_agent=user_agent, timeout_seconds=45, headers={"Referer": source.directory_url})
    manifest = parse_json_object(manifest_response.body, "PANYNJ LocusLabs manifest")
    write_json_file(raw_root.parent / manifest_ref, manifest)
    raw_refs.append(manifest_ref)

    venue_manifest = manifest.get(source.locuslabs_venue_id)
    if not isinstance(venue_manifest, dict):
        raise RuntimeError(f"LocusLabs manifest did not contain venue {source.locuslabs_venue_id}")
    files = venue_manifest.get("files") if isinstance(venue_manifest.get("files"), dict) else {}
    pois_url = clean_text(files.get("pois"))
    venue_data_url = clean_text(files.get("venueData"))
    if not pois_url or not venue_data_url:
        raise RuntimeError("LocusLabs manifest did not expose POI and venueData files")

    pois_ref = str(
        Path("raw")
        / "official-restaurants"
        / f"{source.airport_iata}-panynj-locuslabs-pois-{safe_timestamp(fetched_at)}.json"
    )
    pois_response = fetch_text(pois_url, user_agent=user_agent, timeout_seconds=60, headers={"Referer": source.directory_url})
    pois_payload = parse_json_object(pois_response.body, "PANYNJ LocusLabs POIs")
    write_json_file(raw_root.parent / pois_ref, pois_payload)
    raw_refs.append(pois_ref)

    venue_ref = str(
        Path("raw")
        / "official-restaurants"
        / f"{source.airport_iata}-panynj-locuslabs-venueData-{safe_timestamp(fetched_at)}.json"
    )
    venue_response = fetch_text(venue_data_url, user_agent=user_agent, timeout_seconds=60, headers={"Referer": source.directory_url})
    venue_payload = parse_json_object(venue_response.body, "PANYNJ LocusLabs venueData")
    write_json_file(raw_root.parent / venue_ref, venue_payload)
    raw_refs.append(venue_ref)

    return (
        enrich_panynj_records_from_locuslabs_payloads(records, pois_payload, venue_payload, source=source),
        raw_refs,
        manifest_url,
    )


def enrich_panynj_records_from_locuslabs_payloads(
    records: list[dict[str, object]],
    pois_payload: dict[str, object],
    venue_payload: dict[str, object],
    *,
    source: OfficialRestaurantSource,
) -> list[dict[str, object]]:
    venue = venue_payload.get(source.locuslabs_venue_id or "") if isinstance(venue_payload, dict) else None
    floor_lookup = locuslabs_floor_lookup(venue if isinstance(venue, dict) else {})
    pois_by_id: dict[str, dict[str, object]] = {}
    for item in pois_payload.values():
        if not isinstance(item, dict):
            continue
        poi_id = clean_text(item.get("poiId") or item.get("id"))
        if poi_id:
            pois_by_id[poi_id] = item

    enriched_records: list[dict[str, object]] = []
    for record in records:
        next_record = dict(record)
        source_record = dict(record.get("source") if isinstance(record.get("source"), dict) else {})
        source_notes = list(source_record.get("notes") if isinstance(source_record.get("notes"), list) else [])
        poi = pois_by_id.get(clean_text(record.get("officialSourceId")))
        if poi is None:
            enriched_records.append(next_record)
            continue

        position = poi.get("position") if isinstance(poi.get("position"), dict) else {}
        latitude = coerce_float(position.get("latitude"))
        longitude = coerce_float(position.get("longitude"))
        if latitude is not None and longitude is not None:
            next_record["latitude"] = latitude
            next_record["longitude"] = longitude

        floor_id = clean_text(position.get("floorId"))
        terminal_from_floor, floor_name = floor_lookup.get(floor_id, (locuslabs_terminal_from_floor_id(floor_id), None))
        if not next_record.get("terminal") and terminal_from_floor:
            next_record["terminal"] = terminal_from_floor

        nearby_landmark = clean_text(poi.get("nearbyLandmark")) or None
        description = clean_text(poi.get("description")) or None
        gate = clean_text(next_record.get("gate")) or gate_from_text(nearby_landmark) or gate_from_text(description)
        if gate:
            next_record["gate"] = gate

        map_url = clean_text(poi.get("mapUrl"))
        if map_url:
            next_record["mapUrl"] = map_url

        location_parts = [next_record.get("terminal"), floor_name, nearby_landmark, gate]
        next_record["locationDescription"] = ", ".join(dedupe_text_parts(location_parts)) or next_record.get("locationDescription")

        if "Coordinates are matched by official airport-map POI ID from PANYNJ's public map data." not in source_notes:
            source_notes.append("Coordinates are matched by official airport-map POI ID from PANYNJ's public map data.")
        source_record["notes"] = source_notes
        next_record["source"] = source_record
        enriched_records.append(next_record)

    return enriched_records


def parse_sfo_dining_cards(
    html_text: str,
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    cards = re.finditer(
        r'<a\s+href="([^"]+)"\s+class="card-view--card"[^>]*>(.*?)</a>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    records: list[dict[str, object]] = []
    for card in cards:
        href = unescape(card.group(1))
        block = card.group(2)
        title = first_group(r'card-view--card__title">(.*?)</div>', block)
        name = html_to_text(title)
        if not name:
            continue
        terminal = html_to_text(
            first_group(r'field--name-field-terminal.*?field__item">(.*?)</div>', block)
        ) or None
        tags = [html_to_text(value) for value in re.findall(r'<div class="field__item tag-[^"]*">(.*?)</div>', block, re.DOTALL)]
        tags = [tag for tag in tags if tag]
        node_id = first_group(r'data-node-id="([^"]+)"', block)
        detail_url = urljoin(source.directory_url, href)
        slug = slugify(Path(urlparse(href).path).name or name)
        source_id = node_id or slug
        records.append(
            {
                "id": f"official:sfo:flysfo:{source_id}",
                "airportIata": source.airport_iata,
                "name": name,
                "category": "restaurant",
                "officialCategory": "dining",
                "description": None,
                "associationScope": "official_airport_directory",
                "latitude": None,
                "longitude": None,
                "terminal": terminal,
                "securityArea": None,
                "gate": None,
                "locationDescription": terminal,
                "paymentMethods": ["unknown"],
                "paymentEvidence": "not_provided_by_source",
                "rawPaymentTags": {},
                "officialSourceId": source_id,
                "officialSourcePath": detail_url,
                "mapUrl": None,
                "imageUrls": [],
                "featureTags": tags,
                "osmType": None,
                "osmId": None,
                "source": {
                    "sourceName": source.source_name,
                    "sourceType": source.source_type,
                    "sourceUrl": detail_url,
                    "licenseStatus": "official-public-page",
                    "attributionRequired": True,
                    "fetchedAt": fetched_at,
                    "rawRef": raw_ref,
                    "confidenceScore": 0.95,
                    "notes": [
                        "Restaurant is listed on SFO's official dining-filtered Shop/Dine/Relax page.",
                        "Payment methods remain unknown because the listing card does not publish payment acceptance.",
                    ],
                },
            }
        )
    return dedupe_restaurants(records)


def parse_phx_food_cards(
    html_text: str,
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    starts = [match.start() for match in re.finditer(r'<div class="col-lg-4"', html_text)]
    starts.append(len(html_text))
    by_location: dict[tuple[str, str, str, str, str], dict[str, object]] = {}

    for index, start in enumerate(starts[:-1]):
        block = html_text[start : starts[index + 1]]
        attrs = parse_attrs(first_group(r'<div class="col-lg-4"([^>]*)>', block))
        title_match = re.search(r'<h3[^>]*>\s*<a href="([^"]+)">(.*?)</a>', block, flags=re.IGNORECASE | re.DOTALL)
        if not title_match:
            continue
        href = unescape(title_match.group(1))
        name = html_to_text(title_match.group(2))
        if not name:
            continue

        terminal = normalize_phx_terminal(attrs.get("data-terminal"))
        security_area = clean_text(attrs.get("data-location")) or None
        concourse = clean_text(attrs.get("data-concourse"))
        gate_range = clean_text(attrs.get("data-gates"))
        gate = normalize_gate_range(gate_range)
        location_parts = [terminal, security_area]
        if concourse:
            location_parts.append(f"Concourse {concourse}")
        if gate:
            location_parts.append(gate)

        detail_url = urljoin(source.directory_url, href)
        source_id = slugify(Path(urlparse(href).path.rstrip("/")).name or name)
        image_urls = [urljoin(source.directory_url, unescape(value)) for value in re.findall(r'<img[^>]+src="([^"]+)"', block)]
        tags = clean_tag_list((attrs.get("data-primary") or "").split(",") + (attrs.get("data-secondary") or "").split(","))
        key = (normalized_text(name), terminal or "", security_area or "", concourse, gate_range)
        record = official_restaurant_record(
            source=source,
            source_id=source_id,
            name=name,
            fetched_at=fetched_at,
            raw_ref=raw_ref,
            official_source_path=detail_url,
            source_url=detail_url,
            official_category="food-drinks",
            terminal=terminal,
            security_area=security_area,
            gate=gate,
            location_description=", ".join(part for part in location_parts if part),
            image_urls=image_urls,
            feature_tags=tags,
            confidence_score=0.95,
            notes=[
                "Restaurant is listed on Phoenix Sky Harbor's official Food & Drinks directory page.",
                "Terminal, security area, concourse, and gate range are copied from directory card data attributes when present.",
            ],
        )
        existing = by_location.get(key)
        if existing is None or "menu-example" in str(existing.get("officialSourcePath") or ""):
            by_location[key] = record

    return dedupe_restaurants(list(by_location.values()))


def parse_clt_next_data_restaurants(
    html_text: str,
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    data = extract_next_data_json(html_text)
    pois = data.get("props", {}).get("pageProps", {}).get("pois") if isinstance(data, dict) else None
    if not isinstance(pois, list):
        raise RuntimeError("CLT Next.js data did not contain props.pageProps.pois")

    records: list[dict[str, object]] = []
    for item in pois:
        if not isinstance(item, dict):
            continue
        official_category = clean_text(item.get("category"))
        if not official_category.startswith("eat") or official_category.startswith("eat.vending"):
            continue
        name = clean_text(item.get("name"))
        poi_id = clean_text(item.get("poiId"))
        if not name or not poi_id:
            continue
        position = item.get("position") if isinstance(item.get("position"), dict) else {}
        terminal = clean_text(item.get("terminal")) or None
        nearby_landmark = clean_text(item.get("nearbyLandmark")) or None
        description = clean_text(item.get("description")) or None
        gate = gate_from_text(nearby_landmark) or gate_from_text(description)
        source_path = f"{source.directory_url}#poi-{quote(poi_id)}"
        records.append(
            official_restaurant_record(
                source=source,
                source_id=poi_id,
                name=name,
                fetched_at=fetched_at,
                raw_ref=raw_ref,
                official_source_path=source_path,
                source_url=source.directory_url,
                official_category=official_category,
                description=description,
                terminal=terminal,
                gate=gate,
                location_description=", ".join(part for part in [terminal, nearby_landmark, gate] if part),
                latitude=coerce_float(position.get("latitude")),
                longitude=coerce_float(position.get("longitude")),
                image_urls=[],
                feature_tags=clean_tag_list(item.get("tags")),
                confidence_score=0.93,
                notes=[
                    "Restaurant is embedded in Charlotte Douglas International Airport's official Shop, Dine & Relax directory data.",
                    "The directory provides concourse/location fields; exact gate is used only when present in the source text.",
                ],
            )
        )
    return dedupe_restaurants(records)


def parse_iah_next_flight_restaurants(
    html_text: str,
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    encoded_objects = re.findall(r'\{\\"additionalAttributes\\".*?\\"operationHours\\"\s*:\s*\\"[^\\"]*\\"\}', html_text)
    if not encoded_objects:
        raise RuntimeError("IAH Next.js flight payload did not contain POI objects")

    records: list[dict[str, object]] = []
    for encoded in encoded_objects:
        decoded = encoded.replace('\\"', '"')
        try:
            item = json.loads(decoded)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        official_category = clean_text(item.get("category"))
        if not official_category.startswith("eat") or official_category.startswith("eat.vending"):
            continue
        name = clean_text(item.get("name"))
        poi_id = clean_text(item.get("poiId"))
        if not name or not poi_id:
            continue
        position = item.get("position") if isinstance(item.get("position"), dict) else {}
        nearby_landmark = clean_text(item.get("nearbyLandmark")) or None
        terminal = clean_text(item.get("terminal")) or terminal_from_iah_floor_id(clean_text(position.get("floorId")))
        gate = gate_from_text(nearby_landmark)
        source_path = f"{source.directory_url}#poi-{quote(poi_id)}"
        records.append(
            official_restaurant_record(
                source=source,
                source_id=poi_id,
                name=name,
                fetched_at=fetched_at,
                raw_ref=raw_ref,
                official_source_path=source_path,
                source_url=source.directory_url,
                official_category=official_category,
                description=clean_text(item.get("description")) or None,
                terminal=terminal,
                gate=gate,
                location_description=", ".join(part for part in [terminal, nearby_landmark] if part),
                latitude=coerce_float(position.get("latitude")),
                longitude=coerce_float(position.get("longitude")),
                image_urls=[],
                feature_tags=clean_tag_list([tag.get("name") for tag in item.get("tags", []) if isinstance(tag, dict)]),
                confidence_score=0.93,
                notes=[
                    "Restaurant is embedded in Houston Airports' public IAH Shop, Dine & Relax page payload.",
                    "Vending machines are excluded from restaurant inventory; lounges are excluded unless categorized as dining by the source.",
                ],
            )
        )
    return dedupe_restaurants(records)


def parse_dtw_concessions_dining(
    html_text: str,
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for heading, terminal in [
        ("McNamara Terminal Dining", "McNamara Terminal"),
        ("Evans Terminal Dining", "Evans Terminal"),
    ]:
        heading_match = re.search(rf'<h2>\s*{re.escape(heading)}', html_text, flags=re.IGNORECASE)
        if not heading_match:
            continue
        next_heading = re.search(r'<h2>', html_text[heading_match.end() :], flags=re.IGNORECASE)
        end = heading_match.end() + next_heading.start() if next_heading else len(html_text)
        block = html_text[heading_match.start() : end]
        for link in re.finditer(r'<a href="([^"]+)">(.*?)</a>', block, flags=re.IGNORECASE | re.DOTALL):
            href = unescape(link.group(1))
            text = html_to_text(link.group(2))
            if not text:
                continue
            gate = gate_from_text(text)
            name = strip_location_hint_from_name(text)
            if not name:
                continue
            source_id = first_group(r'assetview=([0-9]+)', href) or f"{slugify(terminal)}-{slugify(name)}"
            records.append(
                official_restaurant_record(
                    source=source,
                    source_id=source_id,
                    name=name,
                    fetched_at=fetched_at,
                    raw_ref=raw_ref,
                    official_source_path=href,
                    source_url=href,
                    official_category="dining-contact-list",
                    terminal=terminal,
                    gate=gate,
                    location_description=", ".join(part for part in [terminal, gate] if part),
                    map_url=href,
                    feature_tags=["terminal-level-directory"],
                    confidence_score=0.88,
                    notes=[
                        "Restaurant is listed on Detroit Metro's official concessions contacts dining page.",
                        "This source is terminal-level for most rows; gate is copied only when included in the listing text.",
                    ],
                )
            )
    return dedupe_restaurants(records)


def fetch_msp_vendor_directory(
    source: OfficialRestaurantSource,
    *,
    fetched_at: str,
    raw_root: Path,
    user_agent: str,
    delay_ms: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    check_robots_or_raise(source.directory_url, user_agent)

    records: list[dict[str, object]] = []
    raw_refs: list[str] = []
    next_url: str | None = source.directory_url
    page_number = 1
    max_pages = 8
    seen_urls: set[str] = set()

    while next_url and page_number <= max_pages and next_url not in seen_urls:
        seen_urls.add(next_url)
        check_robots_or_raise(next_url, user_agent)
        raw_ref = str(
            Path("raw")
            / "official-restaurants"
            / f"{source.airport_iata}-msp-vendors-page-{page_number}-{safe_timestamp(fetched_at)}.html"
        )
        response = fetch_text(next_url, user_agent=user_agent, timeout_seconds=45)
        if looks_like_access_challenge(response.body):
            raise RuntimeError("source returned an access challenge; skipping because bypassing bot protection is not allowed")
        write_text_file(raw_root.parent / raw_ref, response.body)
        raw_refs.append(raw_ref)
        records.extend(parse_msp_vendor_cards(response.body, source=source, fetched_at=fetched_at, raw_ref=raw_ref))
        next_url = next_msp_vendor_page(response.body, next_url)
        page_number += 1
        if next_url:
            sleep_ms(delay_ms)

    enrichment_warnings: list[str] = []
    if source.airport_iata == "MSP":
        records, supplemental_refs, enrichment_warnings = fetch_and_apply_msp_food_offering_gate_hints(
            records,
            source=source,
            fetched_at=fetched_at,
            raw_root=raw_root,
            user_agent=user_agent,
            delay_ms=delay_ms,
        )
        raw_refs.extend(supplemental_refs)

    normalized = dedupe_restaurants(records)
    return normalized, {
        "airportIata": source.airport_iata,
        "sourceName": source.source_name,
        "sourceType": source.source_type,
        "sourceUrl": source.directory_url,
        "status": "partial" if enrichment_warnings else "ok",
        "recordCount": len(normalized),
        "warning": "; ".join(enrichment_warnings) if enrichment_warnings else None,
        "rawRefs": raw_refs,
    }


def fetch_and_apply_msp_food_offering_gate_hints(
    records: list[dict[str, object]],
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_root: Path,
    user_agent: str,
    delay_ms: int,
) -> tuple[list[dict[str, object]], list[str], list[str]]:
    raw_refs: list[str] = []
    warnings: list[str] = []
    hints: list[dict[str, object]] = []
    for page_url in MSP_FOOD_OFFERING_URLS:
        try:
            check_robots_or_raise(page_url, user_agent)
            raw_ref = str(
                Path("raw")
                / "official-restaurants"
                / f"{source.airport_iata}-msp-food-offerings-{slugify(Path(urlparse(page_url).path).name)}-{safe_timestamp(fetched_at)}.html"
            )
            response = fetch_text(page_url, user_agent=user_agent, timeout_seconds=45)
            if looks_like_access_challenge(response.body):
                warnings.append(f"{page_url}: source returned an access challenge")
                continue
            write_text_file(raw_root.parent / raw_ref, response.body)
            raw_refs.append(raw_ref)
            hints.extend(parse_msp_food_offering_gate_hints(response.body, page_url=page_url))
        except Exception as error:
            warnings.append(f"{page_url}: {error}")
        sleep_ms(delay_ms)

    return enrich_msp_records_with_gate_hints(records, hints), raw_refs, warnings


def parse_msp_food_offering_gate_hints(html_text: str, *, page_url: str) -> list[dict[str, object]]:
    hints: list[dict[str, object]] = []
    for match in re.finditer(
        r"<h3[^>]*>(.*?)</h3>\s*<h4[^>]*>(.*?)</h4>",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        raw_name, raw_location = match.groups()
        name = html_to_text(raw_name)
        location_text = html_to_text(raw_location)
        gates = gate_values_from_text(location_text)
        if not name or not gates:
            continue
        hints.append(
            {
                "name": name,
                "locationText": location_text,
                "gates": gates,
                "sourceUrl": page_url,
            }
        )
    return hints


def enrich_msp_records_with_gate_hints(
    records: list[dict[str, object]],
    hints: list[dict[str, object]],
) -> list[dict[str, object]]:
    hints_by_name: dict[str, list[dict[str, object]]] = {}
    for hint in hints:
        hints_by_name.setdefault(normalized_text(hint.get("name")), []).append(hint)

    enriched: list[dict[str, object]] = []
    for record in records:
        if record.get("gate"):
            enriched.append(record)
            continue
        next_record = dict(record)
        selected_gate = None
        selected_hint = None
        for hint in hints_by_name.get(normalized_text(record.get("name")), []):
            gate = choose_msp_gate_for_record(record, hint)
            if gate:
                selected_gate = gate
                selected_hint = hint
                break
        if selected_gate:
            next_record["gate"] = selected_gate
            next_record["locationDescription"] = ", ".join(
                dedupe_text_parts([record.get("locationDescription"), selected_gate])
            )
            source_record = dict(record.get("source") if isinstance(record.get("source"), dict) else {})
            source_notes = list(source_record.get("notes") if isinstance(source_record.get("notes"), list) else [])
            note = "Gate was enriched from MSP's official terminal food-offerings page by restaurant name and concourse/terminal match."
            if note not in source_notes:
                source_notes.append(note)
            source_record["notes"] = source_notes
            if selected_hint and selected_hint.get("sourceUrl"):
                source_record["sourceUrl"] = selected_hint.get("sourceUrl")
            next_record["source"] = source_record
        enriched.append(next_record)
    return enriched


def choose_msp_gate_for_record(record: dict[str, object], hint: dict[str, object]) -> str | None:
    gates = [clean_text(gate) for gate in hint.get("gates", []) if clean_text(gate)]
    if not gates:
        return None
    location = clean_text(record.get("locationDescription") or record.get("terminal")).lower()
    matched_by_concourse = [gate for gate in gates if f"concourse {gate_letter(gate).lower()}" in location]
    if matched_by_concourse:
        return join_gate_values(matched_by_concourse)
    if "terminal 2" in location and all(gate_letter(gate) == "H" for gate in gates):
        return join_gate_values(gates)
    if len(gates) == 1:
        return gates[0]
    return None


def fetch_phl_foodshops_directory(
    source: OfficialRestaurantSource,
    *,
    fetched_at: str,
    raw_root: Path,
    user_agent: str,
    delay_ms: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    check_robots_or_raise(source.directory_url, user_agent)

    records: list[dict[str, object]] = []
    raw_refs: list[str] = []
    next_url: str | None = source.directory_url
    page_number = 1
    max_pages = 8
    seen_urls: set[str] = set()

    while next_url and page_number <= max_pages and next_url not in seen_urls:
        seen_urls.add(next_url)
        check_robots_or_raise(next_url, user_agent)
        raw_ref = str(
            Path("raw")
            / "official-restaurants"
            / f"{source.airport_iata}-phl-foodshops-page-{page_number}-{safe_timestamp(fetched_at)}.html"
        )
        response = fetch_text(next_url, user_agent=user_agent, timeout_seconds=45)
        if looks_like_access_challenge(response.body):
            raise RuntimeError("source returned an access challenge; skipping because bypassing bot protection is not allowed")
        write_text_file(raw_root.parent / raw_ref, response.body)
        raw_refs.append(raw_ref)
        records.extend(parse_phl_foodshops_cards(response.body, source=source, fetched_at=fetched_at, raw_ref=raw_ref))
        next_url = next_phl_directory_page(response.body, next_url)
        page_number += 1
        if next_url:
            sleep_ms(delay_ms)

    normalized = dedupe_restaurants(records)
    return normalized, {
        "airportIata": source.airport_iata,
        "sourceName": source.source_name,
        "sourceType": source.source_type,
        "sourceUrl": source.directory_url,
        "status": "ok",
        "recordCount": len(normalized),
        "rawRefs": raw_refs,
    }


def parse_lax_drupal_tenants(
    html_text: str,
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    settings = extract_drupal_settings_json(html_text)
    tenants = settings.get("tenants") if isinstance(settings, dict) else None
    if not isinstance(tenants, list):
        raise RuntimeError("LAX Drupal settings did not contain a tenants list")

    records: list[dict[str, object]] = []
    for tenant in tenants:
        if not isinstance(tenant, dict):
            continue
        categories = clean_text(tenant.get("Categories")).upper()
        if "FOOD AND BEVERAGE" not in categories:
            continue
        name = clean_text(tenant.get("CompanyName"))
        source_id = clean_text(tenant.get("CompanyLocationID") or tenant.get("mPOID") or tenant.get("LocusLabPOID"))
        if not name or not source_id:
            continue
        terminal = clean_text(tenant.get("Terminal")) or None
        location = clean_text(tenant.get("Location")) or None
        gate = gate_from_text(tenant.get("gate")) or gate_from_text(location)
        security_area = security_area_from_lax_value(tenant.get("securitycheckpoint"))
        latitude = coerce_float(tenant.get("Lat")) or coerce_float(tenant.get("LocusLabLat"))
        longitude = coerce_float(tenant.get("Long")) or coerce_float(tenant.get("LocusLabLong"))
        tags = clean_tag_list((clean_text(tenant.get("displayTags")) or clean_text(tenant.get("tags"))).split(","))
        image_urls = [
            value
            for value in [
                clean_text(tenant.get("MediaImageLogoURL")),
                clean_text(tenant.get("MediaImageStoreFrontURL")),
                clean_text(tenant.get("urlLogoImage")),
                clean_text(tenant.get("urlFrontImage")),
            ]
            if value
        ]
        source_path = f"{source.directory_url}#tenant-{quote(source_id)}"
        records.append(
            official_restaurant_record(
                source=source,
                source_id=source_id,
                name=name,
                fetched_at=fetched_at,
                raw_ref=raw_ref,
                official_source_path=source_path,
                source_url=source.directory_url,
                official_category="food-and-beverage-facilities",
                description=clean_text(tenant.get("CompanyLocationDescription") or tenant.get("CompanyDescription")) or None,
                terminal=terminal,
                security_area=security_area,
                gate=gate,
                location_description=", ".join(part for part in [terminal, location, gate] if part),
                latitude=latitude,
                longitude=longitude,
                map_url=clean_text(tenant.get("OrderURL")) or None,
                image_urls=image_urls,
                feature_tags=tags,
                confidence_score=0.94,
                notes=[
                    "Restaurant is listed in LAX's official dining and shopping Drupal tenant payload.",
                    "Only FOOD AND BEVERAGE FACILITIES tenant records are exported as restaurant inventory.",
                ],
            )
        )
    return dedupe_restaurants(records)


def parse_msp_vendor_cards(
    html_text: str,
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    blocks = split_top_level_blocks(html_text, r'<div class="vendor-list__item(?=[\s"])')
    if not blocks:
        raise RuntimeError("MSP vendor list did not contain vendor cards")

    for block in blocks:
        categories = [html_to_text(value) for value in re.findall(r'<span[^>]*about="/taxonomy/term/[^"]+"[^>]*>(.*?)</span>', block, flags=re.IGNORECASE | re.DOTALL)]
        categories = [category for category in categories if category]
        if not any(category.lower() == "eat" for category in categories):
            continue
        name = html_to_text(first_group(r'<h4 class="vendor-list__item-title"[^>]*>(.*?)</h4>', block))
        href = first_group(r'<a\s+href="([^"]+)"[^>]*class="[^"]*vendor-card', block)
        if not name or not href:
            continue
        detail_url = urljoin(source.directory_url, unescape(href))
        source_id = slugify(Path(urlparse(href).path).name or name)
        terminal = html_to_text(first_group(r'class="vendor-list__item-terminal">(.*?)</span>', block)) or None
        course = html_to_text(first_group(r'class="vendor-list__item-course">(.*?)</span>', block)) or None
        hours = html_to_text(first_group(r'<div class="vendor-list__item-hours"[^>]*>(.*?)</div>', block))
        gate = gate_from_text(course) or gate_from_text(html_to_text(block))
        image_urls = [urljoin(source.directory_url, unescape(value)) for value in re.findall(r'<img[^>]+src=(?:"([^"]+)"|([^\s>]+))', block) for value in value if value]
        records.append(
            official_restaurant_record(
                source=source,
                source_id=source_id,
                name=name,
                fetched_at=fetched_at,
                raw_ref=raw_ref,
                official_source_path=detail_url,
                source_url=detail_url,
                official_category="eat",
                terminal=terminal,
                gate=gate,
                location_description=", ".join(part for part in [terminal, course] if part),
                image_urls=image_urls,
                feature_tags=[*categories, *([f"hours: {hours}"] if hours else [])],
                confidence_score=0.92,
                notes=[
                    "Restaurant is listed on MSP Airport's official Eat, Shop, Relax directory page.",
                    "Rows are included only when the source category list contains Eat.",
                ],
            )
        )
    return dedupe_restaurants(records)


def parse_phl_foodshops_cards(
    html_text: str,
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    blocks = split_top_level_blocks(html_text, r'<div data-elementor-type="loop-item"')
    if not blocks:
        raise RuntimeError("PHL Food & Shops page did not contain directory cards")

    for block in blocks:
        class_attr = first_group(r'<div data-elementor-type="loop-item"[^>]+class="([^"]+)"', block)
        if "directory_category-dine" not in class_attr:
            continue
        match = re.search(r'<h3[^>]*class="[^"]*elementor-heading-title[^"]*"[^>]*>\s*<a href="([^"]+)">(.*?)</a>', block, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        detail_url = unescape(match.group(1))
        name = html_to_text(match.group(2))
        if not name:
            continue
        source_id = first_group(r'\be-loop-item-(\d+)\b', class_attr) or first_group(r'\bpost-(\d+)\b', class_attr) or slugify(Path(urlparse(detail_url).path).name or name)
        text = html_to_text(block)
        terminal = first_terminal_from_text(text)
        image_url = first_group(r'<img[^>]+src="([^"]+)"', block)
        tags = [token.replace("directory_tag-", "").replace("-", " ") for token in class_attr.split() if token.startswith("directory_tag-")]
        records.append(
            official_restaurant_record(
                source=source,
                source_id=source_id,
                name=name,
                fetched_at=fetched_at,
                raw_ref=raw_ref,
                official_source_path=detail_url,
                source_url=detail_url,
                official_category="dine",
                terminal=terminal,
                location_description=terminal,
                image_urls=[unescape(image_url)] if image_url else [],
                feature_tags=clean_tag_list(tags),
                confidence_score=0.9,
                notes=[
                    "Restaurant is listed on the PHL Food & Shops dining-filtered concession directory.",
                    "The page is linked from Philadelphia International Airport's passenger dining information.",
                ],
            )
        )
    return dedupe_restaurants(records)


def parse_sea_explore_dining_cards(
    html_text: str,
    *,
    source: OfficialRestaurantSource,
    fetched_at: str,
    raw_ref: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    blocks = split_top_level_blocks(html_text, r'<div class="single-tile')
    if not blocks:
        raise RuntimeError("SEA dining page did not contain single-tile cards")

    for block in blocks:
        attrs = parse_attrs(first_group(r'<div class="single-tile([^"]*)"([^>]*)>', block))
        class_attr = "single-tile" + first_group(r'<div class="single-tile([^"]*)"', block)
        data_concept = first_group(r'data-concept-name="([^"]+)"', block)
        link_match = re.search(r'<a\s+href="([^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]+)', block, flags=re.IGNORECASE | re.DOTALL)
        href = unescape(link_match.group(1)) if link_match else ""
        name = html_to_text(link_match.group(2)) if link_match else clean_text(data_concept).title()
        name = name or clean_text(data_concept).title()
        if not name:
            continue

        text = html_to_text(block)
        gate = gate_from_text(text)
        terminal = sea_terminal_from_classes(class_attr) or sea_terminal_from_gate(gate)
        detail_url = urljoin(source.directory_url, href) if href else f"{source.directory_url}#{slugify(name)}"
        source_id = slugify(Path(urlparse(detail_url).path).name or data_concept or name)
        image_urls = [urljoin(source.directory_url, unescape(value)) for value in re.findall(r'<img[^>]+src="([^"]+)"', block)]
        tags = [
            token.replace("-", " ")
            for token in class_attr.split()
            if token not in {"single-tile"} and not token.startswith("gate-")
        ]
        description = next(
            (
                html_to_text(value)
                for value in re.findall(r'<p[^>]*>(.*?)</p>', block, flags=re.IGNORECASE | re.DOTALL)
                if html_to_text(value) and not html_to_text(value).lower().startswith("near gate")
            ),
            None,
        )
        records.append(
            official_restaurant_record(
                source=source,
                source_id=source_id,
                name=name,
                fetched_at=fetched_at,
                raw_ref=raw_ref,
                official_source_path=detail_url,
                source_url=detail_url,
                official_category="dining",
                description=description,
                terminal=terminal,
                gate=gate,
                location_description=", ".join(part for part in [terminal, gate] if part),
                image_urls=image_urls,
                feature_tags=clean_tag_list(tags),
                confidence_score=0.91,
                notes=[
                    "Restaurant is listed on SEA Airport Dining and Retail's public dining directory.",
                    "Gate and concourse values are copied only when present in the source card text or card classes.",
                ],
            )
        )
    return dedupe_restaurants(records)


def extract_drupal_settings_json(html_text: str) -> dict[str, object]:
    match = re.search(
        r'<script type="application/json" data-drupal-selector="drupal-settings-json">(.*?)</script>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise RuntimeError("Drupal settings JSON script was not found")
    parsed = json.loads(unescape(match.group(1)))
    if not isinstance(parsed, dict):
        raise RuntimeError("Drupal settings JSON was not an object")
    return parsed


def split_top_level_blocks(html_text: str, start_pattern: str) -> list[str]:
    starts = [match.start() for match in re.finditer(start_pattern, html_text, flags=re.IGNORECASE)]
    starts.append(len(html_text))
    return [html_text[start:starts[index + 1]] for index, start in enumerate(starts[:-1])]


def next_phl_directory_page(html_text: str, current_url: str) -> str | None:
    next_attr = first_group(r'data-next-page="([^"]+)"', html_text)
    if not next_attr:
        return None
    page = parse_int(first_group(r'data-page="(\d+)"', html_text))
    max_page = parse_int(first_group(r'data-max-page="(\d+)"', html_text))
    if page is not None and max_page is not None and page >= max_page:
        return None
    return unescape(next_attr)


def next_msp_vendor_page(html_text: str, current_url: str) -> str | None:
    href = first_group(r'<a class="button" href="([^"]+)" title="Load more items" rel="next">', html_text)
    return urljoin(current_url, unescape(href)) if href else None


def parse_int(value: object) -> int | None:
    try:
        return int(clean_text(value))
    except (TypeError, ValueError):
        return None


def security_area_from_lax_value(value: object) -> str | None:
    text = clean_text(value)
    if text == "1":
        return "Post-Security"
    if text == "0":
        return "Pre-Security"
    return None


def first_terminal_from_text(value: object) -> str | None:
    text = clean_text(value)
    match = re.search(r'\bTerminal\s+(?:[A-Z]|\d+)(?:\s*-\s*(?:East|West))?\b', text, flags=re.IGNORECASE)
    return clean_text(match.group(0)) if match else None


def sea_terminal_from_classes(class_attr: object) -> str | None:
    classes = set(clean_text(class_attr).lower().split())
    for code, label in [
        ("gate-a", "Concourse A"),
        ("gate-b", "Concourse B"),
        ("gate-c", "Concourse C"),
        ("gate-d", "Concourse D"),
        ("gate-n", "N Gates"),
        ("gate-s", "S Gates"),
        ("gate-central", "Central Terminal"),
        ("gate-ticketing", "Ticketing"),
        ("gate-baggage", "Baggage Claim"),
    ]:
        if code in classes:
            return label
    return None


def sea_terminal_from_gate(gate: object) -> str | None:
    text = clean_text(gate).upper()
    match = re.search(r"GATE\s+([A-Z])", text)
    if not match:
        return None
    code = match.group(1)
    if code in {"A", "B", "C", "D"}:
        return f"Concourse {code}"
    if code == "N":
        return "N Gates"
    if code == "S":
        return "S Gates"
    return None


def split_atl_locations(value: object) -> list[str]:
    text = clean_text(value)
    text = re.sub(
        r"\s+(?:&|and)\s+(?=(?:[A-FT]\s*\d+|[A-FT]\s+(?:Center|Mezzanine|Food Court)|Atrium|Domestic|International))",
        ", ",
        text,
        flags=re.IGNORECASE,
    )
    return [clean_text(part.strip(" .;")) for part in re.split(r"\s*,\s*", text) if clean_text(part.strip(" .;"))]


def atl_terminal_from_location(value: object) -> str | None:
    text = clean_text(value)
    if "atrium" in text.lower():
        return "Domestic Terminal Atrium"
    match = re.search(r"\b([A-FT])\s*(?:\d+|Center|Mezzanine|Food Court)?\b", text, flags=re.IGNORECASE)
    if match:
        return f"Concourse {match.group(1).upper()}"
    if "international" in text.lower():
        return "International Terminal"
    if "domestic" in text.lower():
        return "Domestic Terminal"
    return None


def atl_gate_from_location(value: object) -> str | None:
    match = re.search(r"\b([A-FT])\s*(\d{1,2})\b", clean_text(value), flags=re.IGNORECASE)
    return f"Gate {match.group(1).upper()}{match.group(2)}" if match else None


def den_terminals_from_text(value: object) -> list[str]:
    terminals: list[str] = []
    for match in re.finditer(r"\bConcourse\s+([ABC](?:\s*(?:&|and|,)\s*[ABC])*)", clean_text(value), flags=re.IGNORECASE):
        for code in re.findall(r"[ABC]", match.group(1).upper()):
            terminal = f"Concourse {code}"
            if terminal not in terminals:
                terminals.append(terminal)
    return terminals


def den_description_from_location_text(value: object) -> str | None:
    text = clean_text(value)
    text = re.sub(r"\bConcourse\s+[ABC](?:\s*(?:&|and|,)\s*[ABC])*", " ", text, flags=re.IGNORECASE)
    return clean_text(text.strip(" ,-")) or None


def las_next_page_script_urls(html_text: str, base_url: str) -> list[str]:
    urls: list[str] = []
    for src in re.findall(r'src="([^"]*/_next/static/chunks/app/dine-shop-and-more/page-[^"]+\.js[^"]*)"', html_text):
        url = urljoin(base_url, unescape(src))
        if url not in urls:
            urls.append(url)
    return urls


def extract_las_next_action_id(text: str) -> str | None:
    name_index = text.find(LAS_DINE_SHOP_NEXT_ACTION_NAME)
    if name_index < 0:
        return None
    window = text[max(0, name_index - 800) : name_index + 200]
    match = re.search(r'createServerReference[^\"]*\"([0-9a-f]{32,80})\"', window)
    return match.group(1) if match else None


def normalize_las_terminal(value: object) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if text.lower().startswith("terminal"):
        return text
    return f"Terminal {text.upper()}"


def las_security_area(value: object) -> str | None:
    if value is True:
        return "Post-Security"
    if value is False:
        return "Pre-Security"
    return None


def optional_source_text(value: object) -> str | None:
    text = clean_text(value)
    return None if not text or text == "$undefined" else text


def locuslabs_floor_lookup(venue: dict[str, object]) -> dict[str, tuple[str | None, str | None]]:
    lookup: dict[str, tuple[str | None, str | None]] = {}
    structures = venue.get("structures") if isinstance(venue.get("structures"), dict) else {}
    for structure in structures.values():
        if not isinstance(structure, dict):
            continue
        structure_name = clean_text(structure.get("name")) or None
        levels = structure.get("levels") if isinstance(structure.get("levels"), dict) else {}
        for level_id, level in levels.items():
            level_name = clean_text(level.get("name")) if isinstance(level, dict) else None
            lookup[str(level_id)] = (structure_name, level_name or None)
            if isinstance(level, dict):
                explicit_id = clean_text(level.get("id"))
                if explicit_id:
                    lookup[explicit_id] = (structure_name, level_name or None)
    return lookup


def locuslabs_terminal_from_floor_id(floor_id: object) -> str | None:
    text = clean_text(floor_id).lower()
    match = re.search(r"(?:^|-)terminal([a-z0-9]+)", text)
    if not match:
        return None
    return f"Terminal {match.group(1).upper()}"


def locuslabs_security_area(value: object) -> str | None:
    if value is True:
        return "Post-Security"
    if value is False:
        return "Pre-Security"
    return None


def locuslabs_keyword_tags(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for item in value:
        if isinstance(item, dict):
            if item.get("isDisplayed") is False:
                continue
            tag = clean_text(item.get("name") or item.get("value") or item.get("tag"))
        else:
            tag = clean_text(item)
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def locuslabs_image_urls(item: dict[str, object], *, source: OfficialRestaurantSource) -> list[str]:
    image_values: list[str] = []
    for key in ("images", "fullImages"):
        value = item.get(key)
        if isinstance(value, list):
            image_values.extend(clean_text(entry) for entry in value)
        else:
            image_values.append(clean_text(value))
    attributes = item.get("additionalAttributes") if isinstance(item.get("additionalAttributes"), dict) else {}
    image_values.append(clean_text(attributes.get("logoUrl")))

    urls: list[str] = []
    for value in image_values:
        if not value:
            continue
        if value.startswith("http://") or value.startswith("https://"):
            url = value
        else:
            url = f"https://img.locuslabs.com/resize/{source.locuslabs_account_id}/png/transparent/351x197contain/poi/{quote(value)}"
        if url not in urls:
            urls.append(url)
    return urls[:5]


def parse_json_object(body: str, label: str) -> dict[str, object]:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as error:
        preview = body[:180].replace("\n", " ")
        raise RuntimeError(f"{label} returned non-JSON response: {preview}") from error
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{label} returned a non-object JSON response")
    return parsed


def is_probable_restaurant_name(value: object) -> bool:
    text = clean_text(value)
    if not text or len(text) > 90:
        return False
    lowered = text.lower()
    blocked = {
        "all",
        "bars",
        "coffee",
        "quick eats",
        "sit down",
        "menu",
        "restaurants",
        "dining",
        "atl restaurant week",
        "den dining",
        "grab & go",
        "sips & spirits",
        "wine & dine",
        "unique delights",
        "famous favorites",
    }
    return lowered not in blocked and not lowered.startswith("concourse ")



def official_restaurant_record(
    *,
    source: OfficialRestaurantSource,
    source_id: str,
    name: str,
    fetched_at: str,
    raw_ref: str,
    official_source_path: str,
    source_url: str,
    official_category: str,
    description: str | None = None,
    terminal: str | None = None,
    security_area: str | None = None,
    gate: str | None = None,
    location_description: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    map_url: str | None = None,
    image_urls: list[str] | None = None,
    feature_tags: list[str] | None = None,
    confidence_score: float = 0.92,
    notes: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": f"official:{source.airport_iata.lower()}:{slugify(source.parser)}:{source_id}",
        "airportIata": source.airport_iata,
        "name": name,
        "category": "restaurant",
        "officialCategory": official_category,
        "description": description,
        "associationScope": "official_airport_directory",
        "latitude": latitude,
        "longitude": longitude,
        "terminal": clean_text(terminal) or None,
        "securityArea": clean_text(security_area) or None,
        "gate": clean_text(gate) or None,
        "locationDescription": clean_text(location_description) or clean_text(terminal) or None,
        "paymentMethods": ["unknown"],
        "paymentEvidence": "not_provided_by_source",
        "rawPaymentTags": {},
        "officialSourceId": source_id,
        "officialSourcePath": official_source_path,
        "mapUrl": map_url,
        "imageUrls": image_urls or [],
        "featureTags": clean_tag_list(feature_tags or []),
        "osmType": None,
        "osmId": None,
        "source": {
            "sourceName": source.source_name,
            "sourceType": source.source_type,
            "sourceUrl": source_url,
            "licenseStatus": "official-public-page",
            "attributionRequired": True,
            "fetchedAt": fetched_at,
            "rawRef": raw_ref,
            "confidenceScore": confidence_score,
            "notes": [
                *(notes or []),
                "Payment methods remain unknown because this source does not publish per-restaurant card-network acceptance.",
            ],
        },
    }


def extract_next_data_json(html_text: str) -> dict[str, object]:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise RuntimeError("Next.js __NEXT_DATA__ script was not found")
    parsed = json.loads(unescape(match.group(1)))
    if not isinstance(parsed, dict):
        raise RuntimeError("Next.js __NEXT_DATA__ was not a JSON object")
    return parsed


def parse_attrs(value: str) -> dict[str, str]:
    return {key: unescape(raw_value) for key, raw_value in re.findall(r'([\w:-]+)="([^"]*)"', value)}


def normalize_phx_terminal(value: object) -> str | None:
    text = clean_text(value)
    match = re.fullmatch(r"T(\d+)", text.upper())
    if match:
        return f"Terminal {match.group(1)}"
    return text or None


def normalize_gate_range(value: object) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return f"Gates {text}" if any(separator in text for separator in ["-", ",", "&"]) else f"Gate {text}"


def gate_from_text(value: object) -> str | None:
    text = clean_text(value)
    match = re.search(
        r"\bGates?\s+(?:[A-Z]\s*)?-?\d+[A-Z]?(?:\s*(?:&|and|-|/)\s*(?:[A-Z]\s*)?-?\d+[A-Z]?)*",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    gate = clean_text(match.group(0))
    return re.sub(r"\b(Gates?)\s+([A-Z])\s+(\d)", r"\1 \2\3", gate, flags=re.IGNORECASE)


def dedupe_text_parts(values: list[object]) -> list[str]:
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_text(value)
        key = text.lower()
        if text and key not in seen:
            parts.append(text)
            seen.add(key)
    return parts


def gate_values_from_text(value: object) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    values: list[str] = []
    for letter, number in re.findall(r"\b([A-Z])\s*(\d{1,3})\b", text, flags=re.IGNORECASE):
        gate = f"Gate {letter.upper()}{number}"
        if gate not in values:
            values.append(gate)
    if values:
        return values
    gate = gate_from_text(text)
    return [gate] if gate else []


def gate_letter(value: object) -> str:
    match = re.search(r"\bGate\s+([A-Z])", clean_text(value), flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def join_gate_values(values: list[str]) -> str:
    unique = [value for index, value in enumerate(values) if value and value not in values[:index]]
    if not unique:
        return ""
    if len(unique) == 1:
        return unique[0]
    return "Gates " + ", ".join(value.replace("Gate ", "", 1) for value in unique)


def terminal_from_iah_floor_id(value: object) -> str | None:
    match = re.search(r"iah-t([a-e])-", clean_text(value).lower())
    return f"Terminal {match.group(1).upper()}" if match else None


def strip_location_hint_from_name(value: object) -> str:
    text = clean_text(value)
    text = re.sub(r"\s*\(Gate[^)]*\)\s*:?.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\(Central Link\)\s*:?.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+[-:]\s+(Coffee|Pastries|Travel Store|Gifts|Cosmetics).*$", "", text, flags=re.IGNORECASE)
    return text.strip(" :-")


def clean_tag_list(values: object) -> list[str]:
    tags: list[str] = []
    if isinstance(values, dict):
        iterable = values.values()
    elif isinstance(values, (list, tuple, set)):
        iterable = values
    else:
        iterable = [values]
    for value in iterable:
        tag = clean_text(value)
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def normalized_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_text(value).lower()).strip()


def coerce_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def looks_like_access_challenge(html_text: str) -> bool:
    lowered = html_text[:5000].lower()
    cloudflare_challenge = "just a moment" in lowered and "challenge" in lowered and "cloudflare" in lowered
    incapsula_challenge = "incapsula incident id" in lowered or "request unsuccessful" in lowered and "incapsula" in lowered
    return cloudflare_challenge or incapsula_challenge


def build_panynj_detail_path(directory_url: str, poi_id: str, name: str, terminal: str | None) -> str:
    query = f"poiId={quote(poi_id)}&name={quote(name)}"
    if terminal:
        query += f"&location={quote(terminal)}"
    return f"{directory_url.rstrip('/')}/detail?{query}"


def check_robots_or_raise(url: str, user_agent: str) -> None:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    path_with_search = parsed.path or "/"
    if parsed.query:
        path_with_search += f"?{parsed.query}"

    if robots_url in ROBOTS_TXT_CACHE:
        robots_body = ROBOTS_TXT_CACHE[robots_url]
    else:
        try:
            robots = fetch_text(robots_url, user_agent=user_agent, timeout_seconds=15)
            robots_body = robots.body
            if looks_like_access_challenge(robots_body):
                raise RuntimeError("robots.txt returned an access challenge")
            ROBOTS_TXT_CACHE[robots_url] = robots_body
        except FetchHttpError as error:
            if error.status in {401, 403, 404, 410}:
                ROBOTS_TXT_CACHE[robots_url] = None
                return
            raise RuntimeError(f"robots.txt unavailable for {robots_url}; skipping in conservative mode: {error}") from error
        except Exception as error:
            raise RuntimeError(f"robots.txt unavailable for {robots_url}; skipping in conservative mode: {error}") from error

    if robots_body is None:
        return
    if not is_path_allowed_by_robots(path_with_search, robots_body, user_agent):
        raise RuntimeError(f"robots.txt disallows {path_with_search} on {parsed.netloc}")


def compress_to_encoded_uri_component(uncompressed: str) -> str:
    if uncompressed is None:
        return ""
    return _compress(uncompressed, 6, lambda value: LZ_STRING_URI_ALPHABET[value])


def _compress(uncompressed: str, bits_per_char: int, get_char_from_int: Callable[[int], str]) -> str:
    if uncompressed == "":
        return ""
    dictionary: dict[str, int] = {}
    dictionary_to_create: dict[str, bool] = {}
    dictionary_size = 3
    num_bits = 2
    enlarge_in = 2
    data: list[str] = []
    data_value = 0
    data_position = 0
    w = ""

    def write_bit(bit: int) -> None:
        nonlocal data_value, data_position
        data_value = (data_value << 1) | bit
        if data_position == bits_per_char - 1:
            data_position = 0
            data.append(get_char_from_int(data_value))
            data_value = 0
        else:
            data_position += 1

    def write_value(value: int, bit_count: int) -> None:
        for _ in range(bit_count):
            write_bit(value & 1)
            value >>= 1

    for c in uncompressed:
        if c not in dictionary:
            dictionary[c] = dictionary_size
            dictionary_size += 1
            dictionary_to_create[c] = True

        wc = w + c
        if wc in dictionary:
            w = wc
            continue

        if w in dictionary_to_create:
            char_code = ord(w[0])
            if char_code < 256:
                write_value(0, num_bits)
                write_value(char_code, 8)
            else:
                write_value(1, num_bits)
                write_value(char_code, 16)
            enlarge_in -= 1
            if enlarge_in == 0:
                enlarge_in = 2 ** num_bits
                num_bits += 1
            del dictionary_to_create[w]
        else:
            write_value(dictionary[w], num_bits)

        enlarge_in -= 1
        if enlarge_in == 0:
            enlarge_in = 2 ** num_bits
            num_bits += 1

        dictionary[wc] = dictionary_size
        dictionary_size += 1
        w = c

    if w:
        if w in dictionary_to_create:
            char_code = ord(w[0])
            if char_code < 256:
                write_value(0, num_bits)
                write_value(char_code, 8)
            else:
                write_value(1, num_bits)
                write_value(char_code, 16)
            enlarge_in -= 1
            if enlarge_in == 0:
                enlarge_in = 2 ** num_bits
                num_bits += 1
            del dictionary_to_create[w]
        else:
            write_value(dictionary[w], num_bits)
        enlarge_in -= 1
        if enlarge_in == 0:
            num_bits += 1

    write_value(2, num_bits)
    while True:
        data_value <<= 1
        if data_position == bits_per_char - 1:
            data.append(get_char_from_int(data_value))
            break
        data_position += 1
    return "".join(data)


def dedupe_restaurants(records: list[dict[str, object]]) -> list[dict[str, object]]:
    by_id: dict[str, dict[str, object]] = {}
    for record in records:
        by_id[str(record["id"])] = record
    return sorted(by_id.values(), key=lambda record: str(record["name"]))


def first_group(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else ""


def html_to_text(value: object) -> str:
    text = clean_text(re.sub(r"<[^>]+>", " ", str(value or "")))
    return text


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def safe_timestamp(timestamp: str) -> str:
    return timestamp.replace(":", "-").replace(".", "-")


def sleep_ms(delay_ms: int) -> None:
    time.sleep(delay_ms / 1000)

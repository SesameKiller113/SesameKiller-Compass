from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import sys

from data_fetcher.http_client import DEFAULT_USER_AGENT
from data_fetcher.adapters.overpass import OSM_ASSOCIATION_MODES
from data_fetcher.pipeline import RESTAURANT_SOURCE_MODES, default_output_root, run_data_fetcher
from data_fetcher.provider_access import build_provider_access_report
from data_fetcher.sources import DEFAULT_OVERPASS_ENDPOINT, TARGET_AIRPORT_IATA_CODES


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.provider_access_report:
        print(json.dumps(build_provider_access_report(os.environ), indent=2))
        return 0

    if args.limit > len(TARGET_AIRPORT_IATA_CODES) and not args.airports and not args.us_airports:
        parser.error(f"--limit cannot exceed {len(TARGET_AIRPORT_IATA_CODES)} without --airports or --us-airports")

    out = Path(args.out)
    output_root = out if out.is_absolute() else default_output_root().parent / out
    target_airports = None
    if args.airports:
        target_airports = [code.strip().upper() for code in args.airports.split(",") if code.strip()]

    card_benefits_file = resolve_local_path(args.card_benefits_file)
    payment_acceptance_file = resolve_local_path(args.payment_acceptance_file)

    result = run_data_fetcher(
        limit=args.limit,
        output_root=output_root,
        target_airport_codes=target_airports,
        us_airports=args.us_airports,
        us_scheduled_only=not args.include_non_scheduled_us_airports,
        restaurant_source=args.restaurant_source,
        skip_overpass=args.skip_overpass,
        include_web_evidence=args.include_web_evidence,
        delay_ms=args.delay_ms,
        radius_meters=args.radius_meters,
        user_agent=os.environ.get("DATA_FETCHER_USER_AGENT") or DEFAULT_USER_AGENT,
        overpass_endpoint=os.environ.get("OVERPASS_ENDPOINT") or DEFAULT_OVERPASS_ENDPOINT,
        osm_association_mode=args.osm_association_mode,
        overpass_max_retries=args.overpass_max_retries,
        overpass_retry_backoff_ms=args.overpass_retry_backoff_ms,
        card_benefits_file=card_benefits_file,
        payment_acceptance_file=payment_acceptance_file,
        google_places_payment_options=args.google_places_payment_options,
        google_places_api_key=os.environ.get("GOOGLE_PLACES_API_KEY"),
        google_places_limit=args.google_places_limit,
        restaurant_detail_payment_pages=args.restaurant_detail_payment_pages,
        restaurant_detail_limit=args.restaurant_detail_limit,
        product_readiness=args.product_readiness,
        min_official_airport_coverage_percent=args.min_official_airport_coverage_percent,
        min_restaurant_terminal_coverage_percent=args.min_restaurant_terminal_coverage_percent,
        min_card_network_coverage_percent=args.min_card_network_coverage_percent,
        logger=lambda message: print(message, file=sys.stderr),
    )
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch legal public airport, official restaurant, and reviewed benefit data.")
    parser.add_argument("--limit", type=positive_int, default=20, help="number of target airports to fetch")
    parser.add_argument("--airports", help="comma-separated IATA override, for example JFK,SFO,LAX")
    parser.add_argument(
        "--us-airports",
        action="store_true",
        help="select US airports from OurAirports instead of the curated target list; deterministic by airport type and IATA",
    )
    parser.add_argument(
        "--include-non-scheduled-us-airports",
        action="store_true",
        help="with --us-airports, include US airports even when OurAirports scheduled_service is not yes",
    )
    parser.add_argument(
        "--provider-access-report",
        action="store_true",
        help="print payment/card provider onboarding status and exit without fetching data",
    )
    parser.add_argument("--out", default="data", help="output folder relative to repo root, default: data")
    parser.add_argument(
        "--restaurant-source",
        choices=sorted(RESTAURANT_SOURCE_MODES),
        default="official",
        help="restaurant source mode; official is the conservative default",
    )
    parser.add_argument(
        "--skip-overpass",
        action="store_true",
        help="legacy flag: skip OSM when --restaurant-source uses OSM enrichment",
    )
    parser.add_argument(
        "--osm-association-mode",
        choices=sorted(OSM_ASSOCIATION_MODES),
        default=os.environ.get("OSM_ASSOCIATION_MODE", "area-first"),
        help="how OSM restaurants are associated to airports; area-first tries OSM aerodrome areas before radius fallback",
    )
    parser.add_argument(
        "--include-web-evidence",
        action="store_true",
        help="crawl official airport homepages after robots.txt check",
    )
    parser.add_argument(
        "--card-benefits-file",
        help="path to a locally reviewed card-benefits JSON file; real files should stay out of git",
    )
    parser.add_argument(
        "--payment-acceptance-file",
        help="path to a locally reviewed payment-acceptance JSON file or licensed feed export; real files should stay out of git",
    )
    parser.add_argument(
        "--google-places-payment-options",
        action="store_true",
        help="opt in to Google Places paymentOptions enrichment for generic payment methods; requires GOOGLE_PLACES_API_KEY",
    )
    parser.add_argument(
        "--google-places-limit",
        type=positive_int,
        default=positive_int(os.environ["GOOGLE_PLACES_LIMIT"]) if os.environ.get("GOOGLE_PLACES_LIMIT") else None,
        help="optional max official restaurant rows to check with Google Places paymentOptions",
    )
    parser.add_argument(
        "--restaurant-detail-payment-pages",
        action="store_true",
        help="scan official restaurant detail pages for explicit payment-method text after robots.txt checks",
    )
    parser.add_argument(
        "--restaurant-detail-limit",
        type=positive_int,
        default=positive_int(os.environ["RESTAURANT_DETAIL_PAYMENT_LIMIT"]) if os.environ.get("RESTAURANT_DETAIL_PAYMENT_LIMIT") else None,
        help="optional max official restaurant detail pages to scan for payment text",
    )
    parser.add_argument(
        "--product-readiness",
        action="store_true",
        help="fail after writing outputs unless official airport, terminal, and card-network coverage meet thresholds",
    )
    parser.add_argument(
        "--min-official-airport-coverage-percent",
        type=percentage_float,
        help="override product-readiness minimum official airport restaurant coverage percent",
    )
    parser.add_argument(
        "--min-restaurant-terminal-coverage-percent",
        type=percentage_float,
        help="override product-readiness minimum terminal field coverage percent",
    )
    parser.add_argument(
        "--min-card-network-coverage-percent",
        type=percentage_float,
        help="override product-readiness minimum known card-network acceptance row coverage percent",
    )
    parser.add_argument(
        "--delay-ms",
        type=positive_int,
        default=int(os.environ.get("FETCH_DELAY_MS", "3000")),
        help="delay between external requests, default: 3000",
    )
    parser.add_argument(
        "--radius-meters",
        type=positive_int,
        default=1500,
        help="OSM search radius around airport coordinates when OSM mode is enabled, default: 1500",
    )
    parser.add_argument(
        "--overpass-max-retries",
        type=non_negative_int,
        default=non_negative_int(os.environ.get("OVERPASS_MAX_RETRIES", "2")),
        help="number of polite retries after Overpass HTTP 429 rate limits, default: 2",
    )
    parser.add_argument(
        "--overpass-retry-backoff-ms",
        type=positive_int,
        default=positive_int(os.environ.get("OVERPASS_RETRY_BACKOFF_MS", "30000")),
        help="base backoff before retrying Overpass after HTTP 429, default: 30000",
    )
    return parser


def resolve_local_path(value: str | None) -> Path | None:
    if not value:
        return None
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else Path.cwd() / candidate


def percentage_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0 or parsed > 100:
        raise argparse.ArgumentTypeError("must be between 0 and 100")
    return parsed


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or a positive integer")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())

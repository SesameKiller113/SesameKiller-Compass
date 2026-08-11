from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import sys

from data_fetcher.http_client import DEFAULT_USER_AGENT
from data_fetcher.pipeline import default_output_root, run_data_fetcher
from data_fetcher.sources import DEFAULT_OVERPASS_ENDPOINT, TARGET_AIRPORT_IATA_CODES


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.limit > len(TARGET_AIRPORT_IATA_CODES) and not args.airports:
        parser.error(f"--limit cannot exceed {len(TARGET_AIRPORT_IATA_CODES)} without --airports")

    out = Path(args.out)
    output_root = out if out.is_absolute() else default_output_root().parent / out
    target_airports = None
    if args.airports:
        target_airports = [code.strip().upper() for code in args.airports.split(",") if code.strip()]

    result = run_data_fetcher(
        limit=args.limit,
        output_root=output_root,
        target_airport_codes=target_airports,
        skip_overpass=args.skip_overpass,
        include_web_evidence=args.include_web_evidence,
        delay_ms=args.delay_ms,
        radius_meters=args.radius_meters,
        user_agent=os.environ.get("DATA_FETCHER_USER_AGENT") or DEFAULT_USER_AGENT,
        overpass_endpoint=os.environ.get("OVERPASS_ENDPOINT") or DEFAULT_OVERPASS_ENDPOINT,
        logger=lambda message: print(message, file=sys.stderr),
    )
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch legal public airport, restaurant, and evidence data.")
    parser.add_argument("--limit", type=positive_int, default=20, help="number of target airports to fetch")
    parser.add_argument("--airports", help="comma-separated IATA override, for example JFK,SFO,LAX")
    parser.add_argument("--out", default="data", help="output folder relative to repo root, default: data")
    parser.add_argument("--skip-overpass", action="store_true", help="fetch airports only, no OSM restaurant calls")
    parser.add_argument(
        "--include-web-evidence",
        action="store_true",
        help="crawl official airport homepages after robots.txt check",
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
        help="OSM search radius around airport coordinates, default: 1500",
    )
    return parser


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())

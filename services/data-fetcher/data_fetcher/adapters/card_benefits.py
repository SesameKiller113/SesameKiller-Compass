from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
import json
import re

from data_fetcher.sources import (
    VISA_DEVELOPER_GETTING_STARTED_URL,
    VISA_DEVELOPER_REFERENCE_URL,
    VISA_DEVELOPER_TERMS_URL,
)


def load_reviewed_card_benefits(
    path: Path | None,
    *,
    fetched_at: str,
    raw_ref: str | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object], list[str]]:
    if path is None:
        return [], [], reviewed_card_benefit_manifest_entry(record_count=0, benefit_count=0, source_path=None), [
            "No reviewed card benefit file configured; card_products and benefits exports are intentionally empty."
        ]

    if not path.exists():
        raise FileNotFoundError(f"Reviewed card benefit file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Reviewed card benefit file must contain a JSON object.")

    reviewed_at = required_text(payload, "reviewedAt", context="root")
    reviewed_by = clean_text(payload.get("reviewedBy")) or None
    legal_basis = required_text(payload, "legalBasis", context="root")
    products_payload = payload.get("cardProducts")
    if not isinstance(products_payload, list):
        raise ValueError("Reviewed card benefit file must contain cardProducts as a list.")

    card_products: list[dict[str, object]] = []
    benefits: list[dict[str, object]] = []
    warnings: list[str] = []

    for product in products_payload:
        if not isinstance(product, dict):
            raise ValueError("Each cardProducts item must be an object.")
        product_id = clean_text(product.get("id")) or f"card:{slugify(required_text(product, 'issuer', context='card product'))}:{slugify(required_text(product, 'productName', context='card product'))}"
        network = required_text(product, "network", context=product_id).lower()
        issuer = required_text(product, "issuer", context=product_id)
        product_name = required_text(product, "productName", context=product_id)
        source_url = required_https_url(product.get("sourceUrl"), context=product_id)
        terms_url = required_https_url(product.get("termsUrl") or source_url, context=product_id)
        product_reviewed_at = clean_text(product.get("reviewedAt")) or reviewed_at
        product_reviewed_by = clean_text(product.get("reviewedBy")) or reviewed_by
        product_legal_basis = clean_text(product.get("legalBasis")) or legal_basis

        card_products.append(
            {
                "id": product_id,
                "network": network,
                "issuer": issuer,
                "productName": product_name,
                "productUrl": source_url,
                "termsUrl": terms_url,
                "reviewedAt": product_reviewed_at,
                "reviewedBy": product_reviewed_by,
                "legalBasis": product_legal_basis,
                "source": reviewed_source(
                    source_name=f"Reviewed card source: {issuer} {product_name}",
                    source_url=source_url,
                    fetched_at=fetched_at,
                    raw_ref=raw_ref,
                    reviewed_at=product_reviewed_at,
                    legal_basis=product_legal_basis,
                ),
            }
        )

        product_benefits = product.get("benefits", [])
        if not isinstance(product_benefits, list):
            raise ValueError(f"Benefits for {product_id} must be a list.")
        for index, benefit in enumerate(product_benefits, start=1):
            if not isinstance(benefit, dict):
                raise ValueError(f"Benefit {index} for {product_id} must be an object.")
            benefit_type = required_text(benefit, "benefitType", context=product_id)
            description = required_text(benefit, "description", context=product_id)
            benefit_source_url = required_https_url(benefit.get("sourceUrl") or terms_url, context=f"{product_id} benefit")
            benefit_terms_url = required_https_url(benefit.get("termsUrl") or benefit_source_url, context=f"{product_id} benefit")
            benefit_reviewed_at = clean_text(benefit.get("reviewedAt")) or product_reviewed_at
            benefit_reviewed_by = clean_text(benefit.get("reviewedBy")) or product_reviewed_by
            benefit_legal_basis = clean_text(benefit.get("legalBasis")) or product_legal_basis
            benefit_id = clean_text(benefit.get("id")) or f"{product_id}:benefit:{slugify(benefit_type)}:{index}"

            benefits.append(
                {
                    "id": benefit_id,
                    "cardProductId": product_id,
                    "airportIata": clean_text(benefit.get("airportIata")) or None,
                    "restaurantId": clean_text(benefit.get("restaurantId")) or None,
                    "restaurantName": clean_text(benefit.get("restaurantName")) or None,
                    "benefitType": benefit_type,
                    "description": description,
                    "paymentNetwork": clean_text(benefit.get("paymentNetwork")) or network,
                    "termsUrl": benefit_terms_url,
                    "offerUrl": clean_text(benefit.get("offerUrl")) or None,
                    "validFrom": clean_text(benefit.get("validFrom")) or None,
                    "validTo": clean_text(benefit.get("validTo")) or None,
                    "requiresEnrollment": bool(benefit.get("requiresEnrollment", False)),
                    "reviewedAt": benefit_reviewed_at,
                    "reviewedBy": benefit_reviewed_by,
                    "legalBasis": benefit_legal_basis,
                    "source": reviewed_source(
                        source_name=f"Reviewed benefit source: {issuer} {product_name}",
                        source_url=benefit_source_url,
                        fetched_at=fetched_at,
                        raw_ref=raw_ref,
                        reviewed_at=benefit_reviewed_at,
                        legal_basis=benefit_legal_basis,
                    ),
                }
            )

    if not card_products:
        warnings.append("Reviewed card benefit file contained no cardProducts records.")

    manifest_entry = reviewed_card_benefit_manifest_entry(
        record_count=len(card_products),
        benefit_count=len(benefits),
        source_path=str(path),
    )
    return card_products, benefits, manifest_entry, warnings


def reviewed_source(
    *,
    source_name: str,
    source_url: str,
    fetched_at: str,
    raw_ref: str | None,
    reviewed_at: str,
    legal_basis: str,
) -> dict[str, object]:
    return {
        "sourceName": source_name,
        "sourceType": "reviewed-card-benefit",
        "sourceUrl": source_url,
        "licenseStatus": "manual-review-required",
        "attributionRequired": True,
        "fetchedAt": fetched_at,
        "rawRef": raw_ref,
        "confidenceScore": 0.85,
        "reviewedAt": reviewed_at,
        "legalBasis": legal_basis,
        "notes": [
            "Card benefits are loaded only from a locally reviewed JSON file with official source URLs.",
            "The fetcher does not scrape Visa or issuer pages and does not store PAN or cardholder data.",
        ],
    }


def reviewed_card_benefit_manifest_entry(
    *,
    record_count: int,
    benefit_count: int,
    source_path: str | None,
) -> dict[str, object]:
    return {
        "key": "reviewed-card-benefits",
        "sourceName": "Reviewed card benefit input file",
        "sourceType": "reviewed-card-benefit",
        "sourceUrl": source_path or "not-configured",
        "licenseStatus": "manual-review-required",
        "attributionRequired": True,
        "legalBasis": "Card benefit records must come from issuer-approved APIs, licensed feeds, or manual review of official issuer/card-network terms.",
        "allowedUse": "Normalize reviewed card-product and benefit facts into JSON/CSV for local demo import.",
        "restrictions": [
            "Do not scrape Visa or issuer pages automatically.",
            "Do not store PAN, cardholder data, or payment credentials.",
            "Every card and benefit row must include an official sourceUrl and review metadata.",
        ],
        "evidenceUrls": [
            VISA_DEVELOPER_GETTING_STARTED_URL,
            VISA_DEVELOPER_REFERENCE_URL,
            VISA_DEVELOPER_TERMS_URL,
        ],
        "recordCount": record_count,
        "benefitCount": benefit_count,
        "skipped": source_path is None,
    }


def required_text(payload: dict[str, object], key: str, *, context: str) -> str:
    value = clean_text(payload.get(key))
    if not value:
        raise ValueError(f"{context} is missing required field {key}.")
    return value


def required_https_url(value: object, *, context: str) -> str:
    url = clean_text(value)
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{context} must include an https source/terms URL.")
    return url


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"

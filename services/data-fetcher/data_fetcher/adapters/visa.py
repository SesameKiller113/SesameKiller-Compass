from __future__ import annotations

from data_fetcher.sources import (
    VISA_DEVELOPER_GETTING_STARTED_URL,
    VISA_DEVELOPER_REFERENCE_URL,
    VISA_DEVELOPER_TERMS_URL,
)


def empty_visa_benefit_dataset() -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    return (
        [],
        [],
        {
            "key": "visa-card-benefits-runtime-status",
            "sourceName": "Visa card benefit data",
            "sourceType": "visa-developer",
            "sourceUrl": VISA_DEVELOPER_GETTING_STARTED_URL,
            "licenseStatus": "api-approval-required",
            "attributionRequired": True,
            "legalBasis": "No Visa card benefit data is fetched until an approved Visa/issuer API or licensed feed is configured.",
            "allowedUse": "Schema-only output for local demo testing.",
            "restrictions": [
                "No scraping of Visa or issuer pages.",
                "No production Visa API calls without Solution Approval/certification and applicable agreement.",
                "No PAN, cardholder, or sensitive payment data is stored.",
            ],
            "evidenceUrls": [
                VISA_DEVELOPER_GETTING_STARTED_URL,
                VISA_DEVELOPER_REFERENCE_URL,
                VISA_DEVELOPER_TERMS_URL,
            ],
            "recordCount": 0,
        },
    )

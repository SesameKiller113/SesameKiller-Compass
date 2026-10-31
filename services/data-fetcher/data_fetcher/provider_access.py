from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ProviderCatalogEntry:
    key: str
    name: str
    category: str
    exact_payment_methods: tuple[str, ...]
    credential_env_vars: tuple[str, ...]
    application_url: str
    docs_url: str
    license_status: str
    setup_action: str
    use_in_project: str
    limitations: tuple[str, ...]
    priority: int


PROVIDER_CATALOG: tuple[ProviderCatalogEntry, ...] = (
    ProviderCatalogEntry(
        key="visa-merchant-search",
        name="Visa Merchant Search",
        category="exact-payment-acceptance",
        exact_payment_methods=("visa",),
        credential_env_vars=(
            "VISA_MERCHANT_SEARCH_USER_ID",
            "VISA_MERCHANT_SEARCH_PASSWORD",
            "VISA_MERCHANT_SEARCH_CERT_PATH",
            "VISA_MERCHANT_SEARCH_KEY_PATH",
        ),
        application_url="https://developer.visa.com/capabilities/merchant_search/docs",
        docs_url="https://developer.visa.com/capabilities/merchant_search/reference",
        license_status="production-contract-required",
        setup_action="Create a Visa Developer project, contact Visa for real production data access, then configure mutual TLS credentials.",
        use_in_project="Use for Visa-accepting merchant/location lookup and merchant identity matching.",
        limitations=(
            "Sandbox data is dummy data and is not useful for real airport restaurant coverage.",
            "This proves Visa acceptance only; it does not prove Mastercard or American Express acceptance.",
        ),
        priority=1,
    ),
    ProviderCatalogEntry(
        key="mastercard-places",
        name="Mastercard Places API",
        category="exact-payment-acceptance",
        exact_payment_methods=("mastercard",),
        credential_env_vars=(
            "MASTERCARD_CONSUMER_KEY",
            "MASTERCARD_KEYSTORE_PATH",
            "MASTERCARD_KEYSTORE_PASSWORD",
            "MASTERCARD_SIGNING_KEY_ALIAS",
        ),
        application_url="https://developer.mastercard.com/products",
        docs_url="https://www.postman.com/mastercard/mastercard-developers/documentation/bb2n2yi/mastercard-places-api",
        license_status="developer-account-and-product-approval-required",
        setup_action="Create a Mastercard Developers account/project and request Places API access with production terms.",
        use_in_project="Use for Mastercard merchant locations and attributes such as NFC/contactless where licensed.",
        limitations=(
            "Mastercard product access and redistribution rights must be approved for this app.",
            "This proves Mastercard-side merchant data only; it does not prove Visa or Amex acceptance.",
        ),
        priority=1,
    ),
    ProviderCatalogEntry(
        key="mastercard-merchant-identifier",
        name="Mastercard Merchant Identifier API",
        category="merchant-identity-match",
        exact_payment_methods=("mastercard",),
        credential_env_vars=(
            "MASTERCARD_CONSUMER_KEY",
            "MASTERCARD_KEYSTORE_PATH",
            "MASTERCARD_KEYSTORE_PASSWORD",
            "MASTERCARD_SIGNING_KEY_ALIAS",
        ),
        application_url="https://developer.mastercard.com/products",
        docs_url="https://www.postman.com/mastercard/mastercard-developers/documentation/uqxt08w/mastercard-merchant-identifier-api",
        license_status="developer-account-and-product-approval-required",
        setup_action="Request Mastercard Merchant Identifier access and confirm if airport merchant records can be stored/displayed.",
        use_in_project="Use to match merchant descriptors or card acceptor IDs to normalized restaurant identities.",
        limitations=(
            "Usually strongest when you already have transaction descriptors or card acceptor IDs.",
            "It is not a public restaurant directory replacement.",
        ),
        priority=2,
    ),
    ProviderCatalogEntry(
        key="amex-enabled",
        name="American Express partner / AMEX Enabled path",
        category="exact-payment-acceptance",
        exact_payment_methods=("american_express",),
        credential_env_vars=("AMEX_PARTNER_ACCOUNT_ID", "AMEX_API_KEY"),
        application_url="https://network.americanexpress.com/globalnetwork/v4/partners/service-providers/",
        docs_url="https://developer.americanexpress.com/",
        license_status="partnership-or-contract-required",
        setup_action="Register or contact American Express for a partner path that permits merchant acceptance data use.",
        use_in_project="Use for Amex acceptance only after Amex grants an appropriate merchant/network data feed.",
        limitations=(
            "There is no self-serve public API that safely proves every restaurant accepts Amex.",
            "Public Amex offers are often personalized and must not be scraped from logged-in accounts.",
        ),
        priority=1,
    ),
    ProviderCatalogEntry(
        key="openstreetmap-payment-tags",
        name="OpenStreetMap payment:* tags",
        category="crowdsourced-payment-acceptance",
        exact_payment_methods=("visa", "mastercard", "american_express", "discover", "diners_club", "jcb", "unionpay"),
        credential_env_vars=("OVERPASS_ENDPOINT",),
        application_url="https://wiki.openstreetmap.org/wiki/Key:payment",
        docs_url="https://wiki.openstreetmap.org/wiki/Key:payment",
        license_status="odbl-attribution-required",
        setup_action="Already supported by --restaurant-source osm, official-plus-osm, or osm-radius; keep ODbL attribution visible.",
        use_in_project="Use as low-cost supplemental evidence when OSM has explicit payment network tags.",
        limitations=(
            "Coverage is usually sparse and crowdsourced.",
            "A missing OSM tag means unknown, not not accepted.",
            "OSM area and radius matches are not official terminal tenant confirmation.",
        ),
        priority=3,
    ),
    ProviderCatalogEntry(
        key="google-places-payment-options",
        name="Google Places paymentOptions",
        category="generic-payment-enrichment",
        exact_payment_methods=("credit_cards", "debit_cards", "cash", "contactless"),
        credential_env_vars=("GOOGLE_PLACES_API_KEY",),
        application_url="https://console.cloud.google.com/google/maps-apis",
        docs_url="https://developers.google.com/maps/documentation/places/web-service/op-overview",
        license_status="api-key-billing-and-google-terms-required",
        setup_action="Enable Places API (New), set billing/quotas, then set GOOGLE_PLACES_API_KEY locally.",
        use_in_project="Use for generic payment options on exact-name place matches.",
        limitations=(
            "Generic credit_cards does not prove Visa, Mastercard, Amex, Discover, JCB, UnionPay, or Diners Club.",
            "Google attribution, retention, and billing terms must be followed.",
        ),
        priority=4,
    ),
    ProviderCatalogEntry(
        key="processor-or-pos-feed",
        name="Processor/POS authorized merchant feeds",
        category="exact-payment-acceptance",
        exact_payment_methods=("visa", "mastercard", "american_express", "discover", "diners_club", "jcb", "unionpay"),
        credential_env_vars=(
            "STRIPE_API_KEY",
            "SQUARE_ACCESS_TOKEN",
            "TOAST_CLIENT_ID",
            "TOAST_CLIENT_SECRET",
        ),
        application_url="https://doc.toasttab.com/doc/devguide/apiPartnerIntegrationOverview.html",
        docs_url="https://docs.stripe.com/terminal/payments/collect-card-payment/supported-card-brands",
        license_status="merchant-authorization-or-partner-approval-required",
        setup_action="Pursue Stripe/Square/Toast/Clover/Adyen/Worldpay/Shift4 only where merchants or airport concessionaires authorize access.",
        use_in_project="Best path to high-confidence per-location acceptance when restaurants opt in or the airport/concessionaire provides a feed.",
        limitations=(
            "Processor docs prove what an integrated merchant can accept, not what a specific airport tenant has enabled.",
            "Needs merchant authorization or a partner agreement.",
        ),
        priority=2,
    ),
    ProviderCatalogEntry(
        key="kard",
        name="Kard",
        category="card-linked-offers-benefits",
        exact_payment_methods=(),
        credential_env_vars=("KARD_CLIENT_ID", "KARD_CLIENT_SECRET", "KARD_ORGANIZATION_ID"),
        application_url="https://www.getkard.com/docs/quickstart",
        docs_url="https://docs.getkard.com/home",
        license_status="sandbox-access-and-commercial-agreement-required",
        setup_action="Request sandbox access from Kard for card-linked rewards/offers.",
        use_in_project="Use for card-linked offers and offer locations, not as proof of general card-network acceptance.",
        limitations=("Offer eligibility is not the same fact as restaurant payment acceptance.",),
        priority=5,
    ),
    ProviderCatalogEntry(
        key="fidel-api",
        name="Fidel API",
        category="card-linked-offers-benefits",
        exact_payment_methods=(),
        credential_env_vars=("FIDEL_API_KEY", "FIDEL_PROGRAM_ID"),
        application_url="https://docs.fidelapi.com/home",
        docs_url="https://docs.fidelapi.com/docs/oaas",
        license_status="commercial-access-required",
        setup_action="Apply for Fidel Select Transactions or Offers as a Service depending on the product path.",
        use_in_project="Use for transaction-backed loyalty/offers where enrolled cards and merchant programs are authorized.",
        limitations=("Does not replace a public all-restaurant acceptance feed.",),
        priority=5,
    ),
    ProviderCatalogEntry(
        key="offer-love",
        name="Offer.love API",
        category="card-offer-aggregation",
        exact_payment_methods=(),
        credential_env_vars=("OFFERLOVE_API_KEY",),
        application_url="https://offer.love/api-docs/",
        docs_url="https://offer.love/terms/",
        license_status="api-key-and-terms-review-required",
        setup_action="Create an Offer.love API key and confirm terms allow this use case.",
        use_in_project="Use only for offer discovery/prototyping; always verify important offers with issuing banks.",
        limitations=(
            "Terms say offer information may not always be current or accurate.",
            "Not a payment acceptance feed.",
        ),
        priority=6,
    ),
)


def build_provider_access_report(env: Mapping[str, str]) -> dict[str, object]:
    providers = [provider_status(entry, env) for entry in sorted(PROVIDER_CATALOG, key=lambda item: (item.priority, item.key))]
    exact_ready = [provider for provider in providers if provider["category"] == "exact-payment-acceptance" and provider["status"] == "credentials_configured"]
    exact_contract_needed = [provider for provider in providers if provider["category"] == "exact-payment-acceptance" and provider["status"] != "credentials_configured"]
    return {
        "goal": "Build source-backed payment acceptance and card-offer coverage without scraping or guessing.",
        "legalRule": "Only accepted/not_accepted facts from explicit source evidence may overwrite unknown; generic credit-card support must not be converted into Visa/Mastercard/Amex acceptance.",
        "exactPaymentAcceptanceReadyCount": len(exact_ready),
        "exactPaymentAcceptanceNeedsAccessCount": len(exact_contract_needed),
        "providers": providers,
        "recommendedOrder": [
            "Visa Merchant Search for Visa acceptance and merchant IDs.",
            "Mastercard Places and Merchant Identifier for Mastercard merchant/location coverage.",
            "American Express partner or merchant-authorized evidence for Amex acceptance.",
            "Processor/POS feeds where restaurants, airports, or concessionaires authorize exact per-location acceptance.",
            "OSM and Google Places only as supplemental evidence with their legal limits respected.",
            "Kard/Fidel/Offer.love for offers/benefits, not exact payment acceptance.",
        ],
    }


def provider_status(entry: ProviderCatalogEntry, env: Mapping[str, str]) -> dict[str, object]:
    configured = [name for name in entry.credential_env_vars if env.get(name)]
    missing = [name for name in entry.credential_env_vars if not env.get(name)]
    if entry.key == "openstreetmap-payment-tags":
        status = "available_without_private_key"
    elif entry.credential_env_vars and not missing:
        status = "credentials_configured"
    elif entry.category in {"exact-payment-acceptance", "merchant-identity-match"}:
        status = "apply_or_contract_required"
    else:
        status = "optional_credentials_missing"
    return {
        "key": entry.key,
        "name": entry.name,
        "category": entry.category,
        "priority": entry.priority,
        "status": status,
        "exactPaymentMethods": list(entry.exact_payment_methods),
        "configuredEnvVars": configured,
        "missingEnvVars": missing,
        "applicationUrl": entry.application_url,
        "docsUrl": entry.docs_url,
        "licenseStatus": entry.license_status,
        "setupAction": entry.setup_action,
        "useInProject": entry.use_in_project,
        "limitations": list(entry.limitations),
    }

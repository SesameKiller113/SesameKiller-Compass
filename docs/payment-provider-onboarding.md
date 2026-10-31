# Payment Provider Onboarding

This project separates three different facts:

- Restaurant inventory: which airport has which restaurant.
- Payment acceptance: which exact restaurant accepts Visa, Mastercard, Amex, cash, NFC, and other methods.
- Card benefits/offers: which card product has a travel, lounge, dining, or merchant offer.

Do not merge these facts unless the source explicitly supports it. A card benefit does not prove a restaurant accepts that card network. Generic credit-card acceptance does not prove Visa, Mastercard, or Amex.

## Run The Provider Report

```bash
npm run fetch:providers
```

The report reads only environment-variable presence. It does not call provider APIs, print secrets, or fetch restricted data.


## Hard Requirement For 90% Exact Card-Network Coverage

A free public crawler is not enough for 90% exact Visa/Mastercard/Amex acceptance. The current legal route is:

1. Use Visa Merchant Search production access for Visa acceptance. Visa's sandbox is dummy data, so it cannot be used for real coverage.
2. Use Mastercard Places production/product access for Mastercard merchant-location coverage.
3. Use an American Express partner/feed path or merchant/processor authorization for Amex.
4. Add processor/POS or airport-concessionaire feeds when a venue can provide store-level acceptance across all networks.
5. Keep OSM and Google Places as supplemental evidence only: OSM can prove a tagged network when present; Google can prove generic credit/debit/NFC/cash only, not Visa/Mastercard/Amex.

Until at least one exact-acceptance provider is approved and credentials are configured, `knownCardNetworkRowsPercent` should stay 0.0%. Raising that number without source evidence would make the product less accurate, not more ready.

## Exact Payment Acceptance Priority

| Priority | Provider | What It Can Prove | How To Apply | Project Env Vars |
| --- | --- | --- | --- | --- |
| 1 | Visa Merchant Search | Visa-accepting merchant/location evidence | https://developer.visa.com/capabilities/merchant_search/docs | `VISA_MERCHANT_SEARCH_USER_ID`, `VISA_MERCHANT_SEARCH_PASSWORD`, `VISA_MERCHANT_SEARCH_CERT_PATH`, `VISA_MERCHANT_SEARCH_KEY_PATH` |
| 1 | Mastercard Places | Mastercard merchant/location data and selected attributes | https://developer.mastercard.com/products | `MASTERCARD_CONSUMER_KEY`, `MASTERCARD_KEYSTORE_PATH`, `MASTERCARD_KEYSTORE_PASSWORD`, `MASTERCARD_SIGNING_KEY_ALIAS` |
| 1 | American Express partner path | Amex acceptance only if Amex grants a permitted feed | https://network.americanexpress.com/globalnetwork/v4/partners/service-providers/ | `AMEX_PARTNER_ACCOUNT_ID`, `AMEX_API_KEY` |
| 2 | Processor/POS authorized feeds | Exact per-location card network acceptance when restaurants/airports authorize it | Start with Toast partner docs: https://doc.toasttab.com/doc/devguide/apiPartnerIntegrationOverview.html | `STRIPE_API_KEY`, `SQUARE_ACCESS_TOKEN`, `TOAST_CLIENT_ID`, `TOAST_CLIENT_SECRET` |
| 3 | OpenStreetMap payment tags | Crowdsourced explicit tags such as `payment:visa=yes` | https://wiki.openstreetmap.org/wiki/Key:payment | `OVERPASS_ENDPOINT` |

## Generic Payment Enrichment

Google Places `paymentOptions` can provide generic payment options like credit cards, debit cards, cash-only, and NFC. It does not prove card-network acceptance. Use it for rows such as `credit_cards=accepted`, never for `visa=accepted` or `american_express=accepted`.

Apply and configure:

```bash
GOOGLE_PLACES_API_KEY=your_key
npm run fetch:data -- --airports JFK --restaurant-source official --google-places-payment-options --google-places-limit 25
```

Docs: https://developers.google.com/maps/documentation/places/web-service/op-overview

## Card Offers And Benefits

These help answer "which card has a benefit?" They do not answer "does this exact restaurant accept this network?"

| Provider | Use | Apply |
| --- | --- | --- |
| Kard | Card-linked offers and user/location offer eligibility | https://www.getkard.com/docs/quickstart |
| Fidel API | Card-linked offers and transaction-backed loyalty programs | https://docs.fidelapi.com/home |
| Offer.love | Offer discovery prototype and API-backed offer search | https://offer.love/api-docs/ |
| Visa VMORC | Visa merchant offer repository after approved access | https://developer.visa.com/capabilities/vmorc/docs |
| Mastercard Offers for Publishers | Card-linked merchant-funded offers | https://www.mastercard.com/global/en/business/consumer-acquisition-and-engagement/mastercard-commerce-media/solutions/offers-publishers.html |

## What To Ask Providers

When applying, ask these questions before integrating:

- Does the license allow storing merchant/payment acceptance facts in MongoDB and Neo4j?
- Does it allow showing these facts to end users in a consumer app?
- Does it cover airport concessionaires and store-level locations, not only brand-level merchants?
- Does it include exact network acceptance: Visa, Mastercard, American Express, Discover, JCB, UnionPay, Diners Club?
- Are refresh, cache, attribution, and deletion requirements compatible with this app?
- Can we match by merchant name plus terminal/location, or do we need transaction descriptors/card acceptor IDs?
- Are sandbox records dummy data or real testable merchant data?

## Implementation Rule

Provider data should enter this app through `payment_acceptance.json` rows only when the provider response explicitly states the method and exact restaurant/location. Otherwise the row remains `unknown`.

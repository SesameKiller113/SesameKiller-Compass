# Card API Strategy

This project needs two separate card-related datasets.

## 1. Merchant Payment Acceptance

Question answered: "Does this exact restaurant accept Amex/Visa/Mastercard/etc.?"

Safe source options:

- Explicit restaurant/airport source statement, if published.
- Official restaurant detail pages scanned with `--restaurant-detail-payment-pages`, when the page explicitly names the method.
- OSM `payment:*` tags through Overpass, with ODbL attribution and `unknown` when tags are missing.
- A licensed merchant/processor/acquirer feed whose terms allow storage and product use.
- Manual review/admin entry that records the exact evidence URL, reviewer, and review date.

Useful but not enough by itself:

- Google Places can expose generic `paymentOptions` such as credit cards or NFC. The fetcher supports this with `--google-places-payment-options`, but it does not prove specific card-network acceptance and has Google Maps Platform terms, attribution, retention, and billing restrictions.
- Foursquare is useful for POI identity matching and categories, but its standard place fields should not be treated as Amex/Visa/Mastercard acceptance proof.

Product rule: generic `credit_cards=accepted` does not imply Visa, Mastercard, or American Express. Network-specific acceptance stays `unknown` unless a source says that network. The fetcher now supports official detail-page scans, `--payment-acceptance-file` for reviewed/licensed exact acceptance rows, and `--product-readiness` to fail below 90% known card-network coverage. To reach high coverage for exact restaurant-card acceptance, use a licensed merchant/acquirer feed or a reviewed airport/merchant disclosure source; detail-page crawling only helps when the airport/restaurant pages actually publish payment fields. Google/Foursquare-style POI APIs can help identity matching, but they are not enough to prove Amex/Visa/Mastercard acceptance by themselves.

## 2. Card Benefits And Offers

Question answered: "Does this card have a benefit at this airport, restaurant, lounge, or merchant?"

Safe source options:

- Approved Visa Developer APIs, such as VCES/VMORC, after approval/certification and contract review.
- Approved Mastercard APIs or partner feeds for benefits, offers, places, or experiences.
- Issuer-provided files/API exports whose terms allow storage and user-facing display.
- Licensed affiliate/offer feeds with explicit redistribution/storage rights.
- Manual review from official issuer terms using `data/manual/card_benefits.local.json`.

Not allowed:

- Scraping logged-in Amex Offers, issuer dashboards, Visa pages, Mastercard pages, or personalized offers.
- Storing PAN, cardholder data, or payment credentials.
- Treating sandbox sample APIs as production data.

## API Shortlist

Use these only after checking terms, billing, and approval for the production use case:

- Google Places API: implemented as optional generic payment enrichment for exact-name matches. Useful for place identity, sub-location clues, and generic `paymentOptions` such as credit cards, debit cards, cash-only, or NFC. It is not enough to prove Visa, Mastercard, Amex, Discover, JCB, UnionPay, or Diners Club acceptance.
- Foursquare Places API: useful for POI identity matching, categories, and venue normalization. Treat it as matching/enrichment unless a contracted field explicitly supports the payment fact needed.
- Visa Developer VCES/VON: useful for Visa benefit eligibility and offer flows after Visa review, certification, and agreements. Do not put PAN/cardholder data into this project database.
- Mastercard Developers: evaluate Benefits Content/Eligibility, Offers for Publishers, Places, Merchant Identifier, and related products after account/project access. Treat product catalog visibility as a lead, not permission to store or redistribute production data.
- Licensed merchant/acquirer/processor feed: best path for high-coverage exact merchant network acceptance, because restaurant directories and generic POI APIs rarely publish card-network acceptance.

## Recommended Build Order

1. Keep the reviewed local JSON loader as the baseline for card products and benefits.
2. Add an admin/review UI before adding production card APIs, so every benefit can be approved with source metadata.
3. Use OSM payment tags as a low-cost payment-acceptance enrichment path, clearly marked as crowdsourced.
4. Use Google Places `paymentOptions` only for generic payment methods after API key, terms, billing, attribution, and retention review.
5. Use Foursquare or Google Places for restaurant identity matching only if their current terms and billing are acceptable.
6. Apply for Visa/Mastercard production access when the data model and compliance review process are stable.

This keeps the demo legally conservative while still letting the graph answer exact questions with source-backed confidence.

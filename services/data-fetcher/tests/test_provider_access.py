from __future__ import annotations

import unittest

from data_fetcher.provider_access import build_provider_access_report


class ProviderAccessTest(unittest.TestCase):
    def test_report_marks_exact_providers_missing_without_credentials(self) -> None:
        report = build_provider_access_report({})
        providers = {provider["key"]: provider for provider in report["providers"]}

        self.assertEqual(providers["visa-merchant-search"]["status"], "apply_or_contract_required")
        self.assertIn("visa", providers["visa-merchant-search"]["exactPaymentMethods"])
        self.assertEqual(providers["openstreetmap-payment-tags"]["status"], "available_without_private_key")
        self.assertEqual(report["exactPaymentAcceptanceReadyCount"], 0)

    def test_report_detects_configured_visa_credentials(self) -> None:
        report = build_provider_access_report(
            {
                "VISA_MERCHANT_SEARCH_USER_ID": "user",
                "VISA_MERCHANT_SEARCH_PASSWORD": "password",
                "VISA_MERCHANT_SEARCH_CERT_PATH": "/secure/cert.pem",
                "VISA_MERCHANT_SEARCH_KEY_PATH": "/secure/key.pem",
            }
        )
        providers = {provider["key"]: provider for provider in report["providers"]}

        self.assertEqual(providers["visa-merchant-search"]["status"], "credentials_configured")
        self.assertEqual(
            sorted(providers["visa-merchant-search"]["configuredEnvVars"]),
            [
                "VISA_MERCHANT_SEARCH_CERT_PATH",
                "VISA_MERCHANT_SEARCH_KEY_PATH",
                "VISA_MERCHANT_SEARCH_PASSWORD",
                "VISA_MERCHANT_SEARCH_USER_ID",
            ],
        )
        self.assertEqual(report["exactPaymentAcceptanceReadyCount"], 1)


if __name__ == "__main__":
    unittest.main()

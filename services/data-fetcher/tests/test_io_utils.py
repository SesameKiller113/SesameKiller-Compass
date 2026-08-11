from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from data_fetcher.io_utils import write_csv_file
from data_fetcher.pipeline import flatten_rows


class IoUtilsTest(unittest.TestCase):
    def test_flattened_source_rows_write_csv(self) -> None:
        rows = flatten_rows(
            [
                {
                    "id": "osm:node:1",
                    "paymentMethods": ["visa", "cash"],
                    "rawPaymentTags": {"payment:visa": "yes"},
                    "source": {
                        "sourceName": "fixture",
                        "sourceType": "manual",
                        "sourceUrl": "https://example.test",
                        "licenseStatus": "unknown",
                        "attributionRequired": False,
                        "fetchedAt": "2026-08-11T00:00:00Z",
                        "rawRef": "raw/example.json",
                        "confidenceScore": 1,
                        "notes": ["kept"],
                    },
                }
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.csv"
            write_csv_file(path, rows, ["id", "paymentMethods", "rawPaymentTags", "sourceName"])
            csv_text = path.read_text(encoding="utf-8")

        self.assertIn("visa;cash", csv_text)
        self.assertIn('"{""payment:visa"":""yes""}"', csv_text)
        self.assertIn("fixture", csv_text)


if __name__ == "__main__":
    unittest.main()

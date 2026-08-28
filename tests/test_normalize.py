import unittest

from nomura_tracker.normalize import build_snapshot, normalize_nav_list


class NormalizeTest(unittest.TestCase):
    def test_same_date_snapshot_and_typed_fund_values(self):
        nav = normalize_nav_list(
            [{"DataDT": "2026/08/27", "Nav": "16.09", "ClosingPrice": "15.92", "PremiumDiscount": "-0.17", "PremiumDiscountRatio": "-1.06%"}]
        )[0]
        assets = {
            "Data": {
                "FundAsset": {"Aum": "8611689275", "Units": "535340000", "Nav": "16.09", "NavDate": "2026/08/27"},
                "Table": [{"TableTitle": "股票", "NavDate": "2026/08/27", "Columns": [{"Name": "股票代號"}, {"Name": "權重(%)"}], "Rows": [["AEM CN", "5.68"]]}],
            }
        }

        snapshot = build_snapshot("009821", nav, assets, "2026-08-28T00:00:00+00:00")

        self.assertEqual(snapshot["data_date"], "2026-08-27")
        self.assertEqual(snapshot["fund"]["aum_twd"], 8611689275)
        self.assertEqual(snapshot["portfolio_tables"][0]["rows"][0]["股票代號"], "AEM CN")


if __name__ == "__main__":
    unittest.main()

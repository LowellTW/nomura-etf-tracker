import unittest
from datetime import date

from nomura_tracker.__main__ import previous_business_day
from nomura_tracker.normalize import build_snapshot, normalize_nav_list


class NormalizeTest(unittest.TestCase):
    def test_previous_taiwan_business_day_skips_holidays_and_weekend(self):
        holidays = {date(2026, 9, 25), date(2026, 9, 28)}
        self.assertEqual(
            previous_business_day(date(2026, 9, 29), holidays),
            date(2026, 9, 24),
        )

    def test_same_date_snapshot_and_typed_fund_values(self):
        nav = normalize_nav_list(
            [
                {"DataDT": "2026/08/27", "Nav": "16.09", "ClosingPrice": "15.92", "PremiumDiscount": "-0.17", "PremiumDiscountRatio": "-1.06%"},
                {"DataDT": "2026/08/26", "Nav": "15.92", "ClosingPrice": "16.09", "PremiumDiscount": "0.17", "PremiumDiscountRatio": "1.07%"},
            ]
        )
        assets = {
            "Data": {
                "FundAsset": {"Aum": "8611689275", "Units": "535340000", "Nav": "16.09", "NavDate": "2026/08/27"},
                "Table": [{"TableTitle": "股票", "NavDate": "2026/08/27", "Columns": [{"Name": "股票代號"}, {"Name": "權重(%)"}], "Rows": [["AEM CN", "5.68"]]}],
            }
        }

        snapshot = build_snapshot("009821", nav[0], nav[1], assets, "2026-08-28T00:00:00+00:00")

        self.assertEqual(snapshot["data_date"], "2026-08-27")
        self.assertEqual(snapshot["fund"]["aum_twd"], 8611689275)
        self.assertEqual(snapshot["previous_nav"], {"date": "2026-08-26", "value": 15.92})
        self.assertEqual(snapshot["nav"]["change"], 0.17)
        self.assertEqual(snapshot["nav"]["change_percent"], 1.07)
        self.assertEqual(snapshot["portfolio_tables"][0]["rows"][0]["股票代號"], "AEM CN")


if __name__ == "__main__":
    unittest.main()

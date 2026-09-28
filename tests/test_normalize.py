import unittest
import json
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from urllib.error import URLError

from nomura_tracker.__main__ import (
    all_funds_current,
    fetch_twse_holidays,
    main,
    previous_business_day,
    update_fund,
)
from nomura_tracker.normalize import build_snapshot, normalize_nav_list


class NormalizeTest(unittest.TestCase):
    def test_late_scheduled_run_skips_before_loading_files(self):
        with patch.dict("os.environ", {"GITHUB_EVENT_NAME": "schedule"}), patch(
            "nomura_tracker.__main__.datetime"
        ) as clock, patch(
            "sys.argv", ["nomura_tracker", "--funds", "__missing__.json"]
        ), patch("builtins.print") as output:
            clock.now.return_value = datetime(2026, 9, 28, 10, 0)
            main()
            output.assert_called_once_with(
                "Scheduled update skipped at 10:00 Asia/Taipei (cutoff 10:00)"
            )

    def test_missing_fund_nav_date_is_not_a_failed_update(self):
        with TemporaryDirectory() as directory:
            output_dir = Path(directory)
            fund_dir = output_dir / "009821"
            fund_dir.mkdir()
            latest_path = fund_dir / "latest.json"
            latest_path.write_text(
                json.dumps({"data_date": "2026-09-23"}), encoding="utf-8"
            )

            client = Mock()
            client.post.return_value = [{"DataDT": "2026/09/23", "Nav": "13.98"}]
            with patch("builtins.print"):
                result = update_fund(
                    client,
                    "009821",
                    output_dir,
                    today=date(2026, 9, 25),
                )
            self.assertIsNone(result)
            self.assertEqual(client.post.call_count, 1)
            self.assertEqual(
                json.loads(latest_path.read_text(encoding="utf-8"))["data_date"],
                "2026-09-23",
            )

            client.post.side_effect = lambda endpoint, payload: (
                [
                    {"DataDT": "2026/09/29", "Nav": "14.20"},
                    {"DataDT": "2026/09/23", "Nav": "13.98"},
                ]
                if endpoint == "GetFundNAVList"
                else {"Data": {"FundAsset": {"NavDate": "2026/09/29", "Nav": "14.20"}}}
            )
            snapshot = update_fund(
                client, "009821", output_dir, today=date(2026, 9, 30)
            )
            self.assertEqual(snapshot["data_date"], "2026-09-29")
            self.assertEqual(snapshot["previous_nav"]["date"], "2026-09-23")

    def test_all_funds_current_requires_every_latest_snapshot(self):
        with TemporaryDirectory() as directory:
            output_dir = Path(directory)
            for fund_id, data_date in (("one", "2026-09-21"), ("two", "2026-09-20")):
                (output_dir / fund_id).mkdir()
                (output_dir / fund_id / "latest.json").write_text(
                    json.dumps({"data_date": data_date}), encoding="utf-8"
                )

            self.assertFalse(
                all_funds_current(
                    ["one", "two"], output_dir, date(2026, 9, 21)
                )
            )
            self.assertTrue(
                all_funds_current(["one"], output_dir, date(2026, 9, 21))
            )

    def test_holiday_calendar_falls_back_to_latest_cache(self):
        with TemporaryDirectory() as directory:
            cache_dir = Path(directory)
            (cache_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "snapshot_date": "2026-09-18",
                        "entries": [{"Name": "中秋節", "Date": "1150925"}],
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "nomura_tracker.__main__.urllib.request.urlopen",
                side_effect=URLError("offline"),
            ), patch("builtins.print"):
                holidays = fetch_twse_holidays(cache_dir, date(2026, 9, 21))

        self.assertEqual(holidays, {date(2026, 9, 25)})

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

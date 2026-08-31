import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .client import NomuraClient, NomuraError
from .normalize import build_snapshot, normalize_nav_detail, normalize_nav_list


TWSE_HOLIDAYS_URL = "https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule"


def fetch_twse_holidays():
    request = urllib.request.Request(
        TWSE_HOLIDAYS_URL,
        headers={"Accept": "application/json", "User-Agent": "nomura-etf-tracker/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            rows = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise NomuraError(f"TWSE holiday calendar: {error}") from error

    holidays = set()
    for row in rows:
        name, value = row.get("Name", ""), row.get("Date", "")
        if len(value) == 7 and not any(word in name for word in ("開始交易", "最後交易")):
            holidays.add(date(int(value[:3]) + 1911, int(value[3:5]), int(value[5:7])))
    return holidays


def previous_business_day(today, holidays):
    candidate = today - timedelta(days=1)
    while candidate.weekday() >= 5 or candidate in holidays:
        candidate -= timedelta(days=1)
    return candidate


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def update_fund(client, fund_id, output_dir, today=None, holidays=None):
    today = today or datetime.now(ZoneInfo("Asia/Taipei")).date()
    target_date = previous_business_day(today, holidays or set())
    start = today - timedelta(days=45)
    period = {
        "FundNo": fund_id,
        "SDate": f"{start.isoformat()}T00:00:00",
        "EDate": f"{today.isoformat()}T23:59:59",
    }
    navs = normalize_nav_list(
        client.post("GetFundNAVList", {**period, "IsPreview": False})
    )
    used_nav_detail = False
    if not navs:
        navs = normalize_nav_detail(client.post("GetFundNAV", period))
        used_nav_detail = True
    if not navs:
        raise NomuraError(f"{fund_id}: no NAV found between {start} and {today}")

    index = next(
        (index for index, nav in enumerate(navs) if nav["date"] == target_date.isoformat()),
        None,
    )
    if index is None:
        raise NomuraError(f"{fund_id}: NAV for {target_date} is not available yet")

    nav = navs[index]
    assets = client.post(
        "GetFundAssets",
        {"FundID": fund_id, "SearchDate": nav["date"]},
    )
    previous_nav = navs[index + 1] if index + 1 < len(navs) else None
    snapshot = build_snapshot(fund_id, nav, previous_nav, assets)
    if used_nav_detail:
        snapshot["source"]["endpoints"].append("GetFundNAV")
    fund_dir = output_dir / fund_id
    _atomic_json(fund_dir / "history" / f"{nav['date']}.json", snapshot)
    _atomic_json(fund_dir / "latest.json", snapshot)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description="Update Nomura ETF snapshots")
    parser.add_argument("--funds", default="funds.json", type=Path)
    parser.add_argument("--output", default="data", type=Path)
    args = parser.parse_args()
    fund_ids = json.loads(args.funds.read_text(encoding="utf-8"))
    if not isinstance(fund_ids, list) or not fund_ids:
        raise SystemExit("funds.json must contain a non-empty JSON array")

    client = NomuraClient()
    holidays = fetch_twse_holidays()
    for fund_id in fund_ids:
        snapshot = update_fund(client, str(fund_id), args.output, holidays=holidays)
        print(f"{fund_id}: {snapshot['data_date']}")


if __name__ == "__main__":
    main()

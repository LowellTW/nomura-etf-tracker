import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .client import NomuraClient, NomuraError
from .normalize import build_snapshot, normalize_nav_detail, normalize_nav_list


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def update_fund(client, fund_id, output_dir, today=None):
    today = today or date.today()
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

    for index, nav in enumerate(navs):
        try:
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
        except (NomuraError, KeyError, TypeError, ValueError):
            continue
    raise NomuraError(f"{fund_id}: no same-date NAV and holdings found")


def main():
    parser = argparse.ArgumentParser(description="Update Nomura ETF snapshots")
    parser.add_argument("--funds", default="funds.json", type=Path)
    parser.add_argument("--output", default="data", type=Path)
    args = parser.parse_args()
    fund_ids = json.loads(args.funds.read_text(encoding="utf-8"))
    if not isinstance(fund_ids, list) or not fund_ids:
        raise SystemExit("funds.json must contain a non-empty JSON array")

    client = NomuraClient()
    for fund_id in fund_ids:
        snapshot = update_fund(client, str(fund_id), args.output)
        print(f"{fund_id}: {snapshot['data_date']}")


if __name__ == "__main__":
    main()

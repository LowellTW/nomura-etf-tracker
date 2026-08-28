from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP


def _number(value, number_type=float):
    if value in (None, ""):
        return None
    return number_type(str(value).replace(",", "").replace("%", ""))


def _iso_date(value):
    return datetime.strptime(value, "%Y/%m/%d").date().isoformat()


def normalize_nav_list(entries):
    return sorted(
        (
            {
                "date": _iso_date(row["DataDT"]),
                "value": _number(row.get("Nav")),
                "closing_price": _number(row.get("ClosingPrice")),
                "premium_discount": _number(row.get("PremiumDiscount")),
                "premium_discount_percent": _number(row.get("PremiumDiscountRatio")),
            }
            for row in entries or []
            if row.get("DataDT")
        ),
        key=lambda row: row["date"],
        reverse=True,
    )


def normalize_nav_detail(entries):
    return normalize_nav_list(
        {
            "DataDT": row.get("CDataDt"),
            "Nav": row.get("CNetValue"),
            "ClosingPrice": row.get("CClosingPrice"),
            "PremiumDiscount": row.get("CPremiumDiscount"),
            "PremiumDiscountRatio": row.get("CPremiumDiscountRatio"),
        }
        for row in (entries or {}).get("NAVs", [])
    )


def build_snapshot(fund_id, nav, previous_nav, assets, fetched_at=None):
    data = assets["Data"]
    fund_asset = data["FundAsset"]
    tables = []
    for table in data.get("Table") or []:
        column_names = [column["Name"] for column in table.get("Columns") or []]
        tables.append(
            {
                "title": table.get("TableTitle", ""),
                "date": _iso_date(table["NavDate"]),
                "columns": column_names,
                "rows": [dict(zip(column_names, row)) for row in table.get("Rows") or []],
            }
        )

    data_date = _iso_date(fund_asset["NavDate"])
    if nav["date"] != data_date:
        raise ValueError(f"NAV date {nav['date']} != holdings date {data_date}")

    previous = (
        {"date": previous_nav["date"], "value": previous_nav["value"]}
        if previous_nav
        else None
    )
    change = (
        Decimal(str(nav["value"])) - Decimal(str(previous_nav["value"]))
        if previous_nav and nav["value"] is not None and previous_nav["value"] is not None
        else None
    )
    nav = {
        **nav,
        "change": float(change) if change is not None else None,
        "change_percent": (
            float(
                (change / Decimal(str(previous_nav["value"])) * 100).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            )
            if change is not None and previous_nav["value"] != 0
            else None
        ),
    }

    return {
        "schema_version": "1.1",
        "fund_id": fund_id,
        "data_date": data_date,
        "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fund": {
            "aum_twd": _number(fund_asset.get("Aum"), int),
            "units": _number(fund_asset.get("Units"), int),
            "nav": _number(fund_asset.get("Nav")),
        },
        "nav": nav,
        "previous_nav": previous,
        "portfolio_tables": tables,
        "source": {
            "provider": "Nomura Asset Management Taiwan",
            "api_base": "https://www.nomurafunds.com.tw/API/ETFAPI/api/Fund/",
            "endpoints": ["GetFundAssets", "GetFundNAVList"],
        },
    }

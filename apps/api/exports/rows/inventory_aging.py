AGING_HEADERS = [
    "item_name",
    "item_sku",
    "branch_name",
    "quantity_on_hand",
    "age_days",
    "last_receipt_at",
    "latest_unit_cost",
    "latest_valuation",
    "average_unit_cost",
    "average_valuation",
]


def _fmt_decimal(val):
    if val is None:
        return ""
    from decimal import Decimal
    d = Decimal(str(val))
    return format(d.normalize(), "f")


def to_aging_csv_row(row_dict):
    """row_dict is the dict produced by queries.aging_to_row."""
    ts = row_dict.get("last_receipt_at")
    return [
        row_dict.get("item_name", ""),
        row_dict.get("item_sku", ""),
        row_dict.get("branch_name", ""),
        _fmt_decimal(row_dict.get("quantity_on_hand")),
        "" if row_dict.get("age_days") is None else str(row_dict["age_days"]),
        ts.isoformat() if ts else "",
        _fmt_decimal(row_dict.get("latest_unit_cost")),
        _fmt_decimal(row_dict.get("latest_valuation")),
        _fmt_decimal(row_dict.get("average_unit_cost")),
        _fmt_decimal(row_dict.get("average_valuation")),
    ]

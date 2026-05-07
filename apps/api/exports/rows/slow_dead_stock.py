SLOW_DEAD_HEADERS = [
    "item_name",
    "item_sku",
    "branch_name",
    "quantity_on_hand",
    "status",
    "inactive_days",
    "last_outbound_at",
    "latest_unit_cost",
    "latest_valuation",
]


def _fmt_decimal(val):
    if val is None:
        return ""
    from decimal import Decimal
    d = Decimal(str(val))
    return format(d.normalize(), "f")


def to_slow_dead_csv_row(row_dict):
    """row_dict is the dict produced by queries.slow_dead_to_row."""
    ts = row_dict.get("last_outbound_at")
    return [
        row_dict.get("item_name", ""),
        row_dict.get("item_sku", ""),
        row_dict.get("branch_name", ""),
        _fmt_decimal(row_dict.get("quantity_on_hand")),
        row_dict.get("status", ""),
        str(row_dict.get("inactive_days", "")),
        ts.isoformat() if ts else "",
        _fmt_decimal(row_dict.get("latest_unit_cost")),
        _fmt_decimal(row_dict.get("latest_valuation")),
    ]

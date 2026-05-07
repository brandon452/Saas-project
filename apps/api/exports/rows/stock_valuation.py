HEADERS = [
    "item_name",
    "item_sku",
    "branch_name",
    "quantity_on_hand",
    "latest_unit_cost",
    "latest_valuation",
    "average_unit_cost",
    "average_valuation",
]


def _fmt_decimal(val):
    """Format a Decimal/float for CSV: strip trailing zeros."""
    if val is None:
        return ""
    from decimal import Decimal
    d = Decimal(str(val))
    normalized = d.normalize()
    # normalize() may produce '1E+1' for 10; force fixed-point representation
    return format(normalized, "f")


def to_row(row_dict):
    """row_dict is the formatted row dict produced by reports.queries formatters."""
    return [
        row_dict.get("item_name", ""),
        row_dict.get("item_sku", ""),
        row_dict.get("branch_name", ""),
        _fmt_decimal(row_dict.get("quantity_on_hand")),
        _fmt_decimal(row_dict.get("latest_unit_cost")),
        _fmt_decimal(row_dict.get("latest_valuation")),
        _fmt_decimal(row_dict.get("average_unit_cost")),
        _fmt_decimal(row_dict.get("average_valuation")),
    ]

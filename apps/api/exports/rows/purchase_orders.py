from datetime import timezone as dt_timezone

HEADERS = [
    "po_number",
    "status",
    "supplier",
    "branch",
    "created_at",
    "notes",
]


def to_row(po):
    created_at = po.created_at.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")
    return [
        po.po_number,
        po.status,
        po.supplier.display_name if po.supplier_id else "",
        po.branch.name if po.branch_id else "",
        created_at,
        po.notes,
    ]

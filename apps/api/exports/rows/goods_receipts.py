from datetime import timezone as dt_timezone

HEADERS = [
    "id",
    "receipt_type",
    "branch",
    "supplier",
    "po_number",
    "received_at",
    "notes",
]


def to_row(gr):
    received_at = gr.received_at.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")
    return [
        str(gr.id),
        gr.receipt_type,
        gr.branch.name if gr.branch_id else "",
        gr.supplier.display_name if gr.supplier_id else "",
        gr.purchase_order.po_number if gr.purchase_order_id else "",
        received_at,
        gr.notes,
    ]

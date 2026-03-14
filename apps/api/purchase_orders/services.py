from django.db import transaction

from .models import PurchaseOrder


@transaction.atomic
def generate_po_number(organization):
    last = (
        PurchaseOrder.all_objects
        .select_for_update()
        .filter(organization=organization)
        .order_by("-po_number")
        .first()
    )

    last_seq = 0
    if last and last.po_number:
        try:
            last_seq = int(last.po_number.split("-")[1])
        except (IndexError, ValueError):
            last_seq = 0

    next_seq = last_seq + 1
    return f"PO-{next_seq:04d}"

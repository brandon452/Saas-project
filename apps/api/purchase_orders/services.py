import re

from django.db import transaction

from .models import PurchaseOrder

PO_NUMBER_PATTERN = re.compile(r"^PO-(\d+)$")


@transaction.atomic
def generate_po_number(organization):
    po_numbers = (
        PurchaseOrder.all_objects
        .select_for_update()
        .filter(organization=organization)
        .values_list("po_number", flat=True)
    )

    max_seq = 0
    for po_number in po_numbers:
        if not po_number:
            continue
        match = PO_NUMBER_PATTERN.match(po_number)
        if not match:
            continue
        seq = int(match.group(1))
        if seq > max_seq:
            max_seq = seq

    next_seq = max_seq + 1
    return f"PO-{next_seq:04d}"

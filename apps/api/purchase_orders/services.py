import re

from django.db import transaction

from .models import PurchaseOrder


def _number_pattern(prefix):
    return re.compile(rf"^{re.escape(prefix)}-(\d+)$")


@transaction.atomic
def generate_po_number(organization):
    prefix = organization.purchase_order_prefix
    pattern = _number_pattern(prefix)
    po_numbers = (
        PurchaseOrder.all_objects
        .select_for_update()
        .filter(organization=organization)
        .values_list("po_number", flat=True)
    )

    max_seq = max(organization.purchase_order_next_number - 1, 0)
    for po_number in po_numbers:
        if not po_number:
            continue
        match = pattern.match(po_number)
        if not match:
            continue
        seq = int(match.group(1))
        if seq > max_seq:
            max_seq = seq

    next_seq = max_seq + 1
    return f"{prefix}-{next_seq:04d}"


def sync_purchase_order_next_number(organization, po_number):
    match = _number_pattern(organization.purchase_order_prefix).match(po_number or "")
    if not match:
        return

    next_number = int(match.group(1)) + 1
    if next_number > organization.purchase_order_next_number:
        organization.purchase_order_next_number = next_number
        organization.save(update_fields=["purchase_order_next_number"])

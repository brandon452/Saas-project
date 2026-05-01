from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from inventory.models import StockLedger
from inventory.services import assert_inventory_period_open, record_stock_movement

from .models import QuickSale, QuickSaleLine


@transaction.atomic
def create_quick_sale(
    org,
    branch,
    lines,
    *,
    customer_name="",
    notes="",
    occurred_at=None,
    performed_by=None,
):
    effective_at = occurred_at or timezone.now()
    if effective_at > timezone.now():
        raise ValidationError("Sale date and time cannot be in the future.")

    sale = QuickSale.objects.create(
        organization=org,
        branch=branch,
        customer_name=customer_name,
        notes=notes,
        occurred_at=effective_at,
        sold_by=performed_by,
        status=QuickSale.STATUS_CONFIRMED,
    )

    for line_data in lines:
        ledger, _ = record_stock_movement(
            org=org,
            branch=branch,
            item=line_data["item"],
            quantity=-line_data["quantity"],
            movement_type=StockLedger.MOVEMENT_ISSUE,
            performed_by=performed_by,
            reference_type="QUICK_SALE",
            reference_id=str(sale.id),
            occurred_at=effective_at,
        )
        QuickSaleLine.objects.create(
            sale=sale,
            item=line_data["item"],
            quantity=line_data["quantity"],
            unit_price=line_data["unit_price"],
            unit_cost=ledger.unit_cost,
        )

    return sale


@transaction.atomic
def void_quick_sale(org, quick_sale, *, performed_by=None):
    quick_sale = QuickSale.objects.select_for_update().get(pk=quick_sale.pk)
    if quick_sale.status != QuickSale.STATUS_CONFIRMED:
        raise ValidationError("Only a CONFIRMED sale can be voided.")

    voided_at = timezone.now()
    assert_inventory_period_open(org, voided_at)

    for line in quick_sale.lines.select_related("item").all():
        record_stock_movement(
            org=org,
            branch=quick_sale.branch,
            item=line.item,
            quantity=line.quantity,
            movement_type=StockLedger.MOVEMENT_ADJUSTMENT,
            performed_by=performed_by,
            reference_type="QUICK_SALE_VOID",
            reference_id=str(quick_sale.id),
            _force_unit_cost=line.unit_cost,
            occurred_at=voided_at,
        )

    quick_sale.status = QuickSale.STATUS_VOIDED
    quick_sale.voided_by = performed_by
    quick_sale.voided_at = voided_at
    quick_sale.save(update_fields=["status", "voided_by", "voided_at"])

    return quick_sale

import logging

from django.core.exceptions import ValidationError
from django.db import transaction

from inventory.models import StockLedger
from inventory.services import assert_inventory_period_open, record_stock_movement
from purchase_orders.models import PurchaseOrder, PurchaseOrderLine

from .models import GoodsReceiptLine

logger = logging.getLogger(__name__)


@transaction.atomic
def post_po_receipt(receipt, lines_data, performed_by, organization):
    po = PurchaseOrder.objects.select_for_update().get(pk=receipt.purchase_order_id)
    branch = receipt.branch

    # Re-check status under row lock to prevent races with concurrent PO state changes
    # (e.g., cancellation after request validation but before receipt posting).
    if po.status not in (PurchaseOrder.SUBMITTED, PurchaseOrder.PARTIALLY_RECEIVED):
        raise ValidationError(
            f"Cannot receive against a purchase order with status {po.status}."
        )

    assert_inventory_period_open(organization, receipt.received_at)

    po_line_ids = [line_data["po_line"].pk for line_data in lines_data]
    po_lines_locked = {
        pl.pk: pl
        for pl in PurchaseOrderLine.objects.select_for_update().filter(pk__in=po_line_ids)
    }

    # --- Phase 1: validate all lines before writing anything ---
    seen_po_line_ids = set()
    validated_lines = []

    for line_data in lines_data:
        po_line = po_lines_locked.get(line_data["po_line"].pk)
        quantity_received = line_data["quantity_received"]

        if po_line is None:
            raise ValidationError("One or more PO lines could not be locked for receipt posting.")

        if po_line.pk in seen_po_line_ids:
            raise ValidationError(f"PO line {po_line.pk} appears more than once in this receipt.")
        seen_po_line_ids.add(po_line.pk)

        if po_line.purchase_order_id != po.pk:
            raise ValidationError(
                f"PO line {po_line.pk} does not belong to purchase order {po.po_number}."
            )

        if quantity_received <= 0:
            raise ValidationError("quantity_received must be greater than zero.")

        remaining = po_line.ordered_quantity - po_line.received_quantity
        if quantity_received > remaining:
            raise ValidationError(
                f"quantity_received ({quantity_received}) exceeds remaining "
                f"quantity ({remaining}) on PO line {po_line.pk}."
            )

        unit_cost = line_data.get("unit_cost") or po_line.unit_price
        validated_lines.append((po_line, quantity_received, unit_cost))

    # --- Phase 2: write only after all lines pass validation ---
    for po_line, quantity_received, unit_cost in validated_lines:
        record_stock_movement(
            org=organization,
            branch=branch,
            item=po_line.item,
            quantity=quantity_received,
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=unit_cost,
            performed_by=performed_by,
        )

        GoodsReceiptLine.objects.create(
            receipt=receipt,
            po_line=po_line,
            item=None,
            quantity_received=quantity_received,
            unit_cost=unit_cost,
        )

        po_line.received_quantity += quantity_received
        po_line.save(update_fields=["received_quantity"])

    all_lines = po.lines.all()
    if all(line.received_quantity >= line.ordered_quantity for line in all_lines):
        po.status = PurchaseOrder.FULLY_RECEIVED
    else:
        po.status = PurchaseOrder.PARTIALLY_RECEIVED

    po.save(update_fields=["status", "updated_at"])
    logger.info(
        "PO receipt posted for PO %s by user %s (%d lines)",
        po.po_number,
        performed_by,
        len(validated_lines),
    )


@transaction.atomic
def post_direct_receipt(receipt, lines_data, performed_by, organization):
    branch = receipt.branch

    assert_inventory_period_open(organization, receipt.received_at)

    # --- Phase 1: validate all lines before writing anything ---
    seen_item_ids = set()
    validated_lines = []

    for line_data in lines_data:
        item = line_data["item"]
        quantity_received = line_data["quantity_received"]
        unit_cost = line_data["unit_cost"]

        if item.pk in seen_item_ids:
            raise ValidationError(f"Item {item.pk} appears more than once in this receipt.")
        seen_item_ids.add(item.pk)

        if quantity_received <= 0:
            raise ValidationError("quantity_received must be greater than zero.")

        if item.organization != organization:
            raise ValidationError(f"Item {item.pk} does not belong to this organisation.")

        validated_lines.append((item, quantity_received, unit_cost))

    # --- Phase 2: write only after all lines pass validation ---
    for item, quantity_received, unit_cost in validated_lines:
        record_stock_movement(
            org=organization,
            branch=branch,
            item=item,
            quantity=quantity_received,
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=unit_cost,
            performed_by=performed_by,
        )

        GoodsReceiptLine.objects.create(
            receipt=receipt,
            po_line=None,
            item=item,
            quantity_received=quantity_received,
            unit_cost=unit_cost,
        )

    logger.info(
        "Direct receipt %s posted by user %s (%d lines)",
        receipt.pk,
        performed_by,
        len(validated_lines),
    )

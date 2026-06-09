import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from inventory import signals as inventory_signals
from inventory.api import (
    assert_inventory_period_open,
    create_goods_receipt_line_lot_allocation,
    create_stock_movement_lot_allocation,
    get_or_create_lot,
    increment_lot_balance,
    MOVEMENT_RECEIPT,
    record_stock_movement,
    validate_allocations_sum,
)
from purchase_orders.models import PurchaseOrder, PurchaseOrderLine

from .models import GoodsReceiptLine

logger = logging.getLogger(__name__)


def _emit_goods_receipt_posted(*, receipt, organization_id, actor_user_id):
    transaction.on_commit(
        lambda: inventory_signals.goods_receipt_posted.send(
            sender=_emit_goods_receipt_posted,
            organization_id=str(organization_id),
            actor_user_id=str(actor_user_id),
            receipt_id=str(receipt.id),
            receipt_type=receipt.receipt_type,
            branch_id=str(receipt.branch_id) if receipt.branch_id else "",
            supplier_id=str(receipt.supplier_id) if receipt.supplier_id else "",
            line_count=receipt.lines.count(),
        )
    )


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

    lot_enabled = getattr(settings, "LOT_TRACKING_RECEIPTS_ENABLED", False)

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
        lot_allocs = line_data.get("lot_allocations") or []

        if lot_enabled and po_line.item.is_lot_tracked:
            if not lot_allocs:
                raise ValidationError(
                    f"Item '{po_line.item.sku}' is lot-tracked. "
                    "Provide lot_allocations for this receipt line."
                )
            validate_allocations_sum(lot_allocs, quantity_received)

        validated_lines.append((po_line, quantity_received, unit_cost, lot_allocs))

    # --- Phase 2: write only after all lines pass validation ---
    for po_line, quantity_received, unit_cost, lot_allocs in validated_lines:
        ledger, _ = record_stock_movement(
            org=organization,
            branch=branch,
            item=po_line.item,
            quantity=quantity_received,
            movement_type=MOVEMENT_RECEIPT,
            unit_cost=unit_cost,
            performed_by=performed_by,
        )

        gr_line = GoodsReceiptLine.objects.create(
            receipt=receipt,
            po_line=po_line,
            item=None,
            quantity_received=quantity_received,
            unit_cost=unit_cost,
        )

        if lot_enabled and po_line.item.is_lot_tracked and lot_allocs:
            _apply_receipt_lot_allocations(
                org=organization,
                branch=branch,
                org_item=po_line.item,
                gr_line=gr_line,
                ledger=ledger,
                lot_allocs=lot_allocs,
            )

        po_line.received_quantity += quantity_received
        po_line.save(update_fields=["received_quantity"])

    all_lines = po.lines.all()
    if all(line.received_quantity >= line.ordered_quantity for line in all_lines):
        po.status = PurchaseOrder.FULLY_RECEIVED
    else:
        po.status = PurchaseOrder.PARTIALLY_RECEIVED

    po.save(update_fields=["status", "updated_at"])
    _emit_goods_receipt_posted(
        receipt=receipt,
        organization_id=organization.id,
        actor_user_id=performed_by.id,
    )
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

    lot_enabled = getattr(settings, "LOT_TRACKING_RECEIPTS_ENABLED", False)

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

        lot_allocs = line_data.get("lot_allocations") or []

        if lot_enabled and item.is_lot_tracked:
            if not lot_allocs:
                raise ValidationError(
                    f"Item '{item.sku}' is lot-tracked. "
                    "Provide lot_allocations for this receipt line."
                )
            validate_allocations_sum(lot_allocs, quantity_received)

        validated_lines.append((item, quantity_received, unit_cost, lot_allocs))

    # --- Phase 2: write only after all lines pass validation ---
    for item, quantity_received, unit_cost, lot_allocs in validated_lines:
        ledger, _ = record_stock_movement(
            org=organization,
            branch=branch,
            item=item,
            quantity=quantity_received,
            movement_type=MOVEMENT_RECEIPT,
            unit_cost=unit_cost,
            performed_by=performed_by,
        )

        gr_line = GoodsReceiptLine.objects.create(
            receipt=receipt,
            po_line=None,
            item=item,
            quantity_received=quantity_received,
            unit_cost=unit_cost,
        )

        if lot_enabled and item.is_lot_tracked and lot_allocs:
            _apply_receipt_lot_allocations(
                org=organization,
                branch=branch,
                org_item=item,
                gr_line=gr_line,
                ledger=ledger,
                lot_allocs=lot_allocs,
            )

    _emit_goods_receipt_posted(
        receipt=receipt,
        organization_id=organization.id,
        actor_user_id=performed_by.id,
    )
    logger.info(
        "Direct receipt %s posted by user %s (%d lines)",
        receipt.pk,
        performed_by,
        len(validated_lines),
    )


# ---------------------------------------------------------------------------
# Internal lot helpers
# ---------------------------------------------------------------------------

def _apply_receipt_lot_allocations(*, org, branch, org_item, gr_line, ledger, lot_allocs):
    """
    For each lot allocation in *lot_allocs* (list of dicts with keys:
    lot_code, quantity, expiry_date?, manufacture_date?):
      - get_or_create the InventoryLotBalance
      - increment the lot balance
      - create GoodsReceiptLineLotAllocation
      - create StockMovementLotAllocation
    """
    from decimal import Decimal

    for alloc in lot_allocs:
        lot_code = alloc["lot_code"]
        qty = Decimal(str(alloc["quantity"]))
        expiry_date = alloc.get("expiry_date")
        manufacture_date = alloc.get("manufacture_date")

        lot, _ = get_or_create_lot(
            org=org,
            branch=branch,
            org_item=org_item,
            lot_code=lot_code,
            expiry_date=expiry_date,
            manufacture_date=manufacture_date,
        )
        increment_lot_balance(lot, qty)

        create_goods_receipt_line_lot_allocation(
            receipt_line=gr_line,
            lot=lot,
            quantity=qty,
        )
        create_stock_movement_lot_allocation(
            ledger=ledger,
            lot=lot,
            quantity=qty,
        )

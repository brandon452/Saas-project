import logging
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from inventory import signals as inventory_signals
from inventory.api import (
    allocate_lots_fefo_fifo,
    assert_inventory_period_open,
    create_branch_transfer_dispatch_lot_allocation,
    create_branch_transfer_receive_lot_allocation,
    create_stock_movement_lot_allocation,
    deplete_lot_balance,
    find_lot_balance_by_code,
    get_dispatch_lot_allocations,
    get_inventory_cost_state_for_update,
    get_or_create_lot,
    get_or_create_recipient_branch_item,
    get_or_create_recipient_item,
    increment_lot_balance,
    MOVEMENT_ISSUE,
    MOVEMENT_RECEIPT,
    record_stock_movement,
)

from .models import BranchTransfer, BranchTransferLine

logger = logging.getLogger(__name__)


@transaction.atomic
def dispatch_transfer(transfer, performed_by, idempotency_key=None):
    transfer = BranchTransfer.objects.select_for_update().get(pk=transfer.pk)

    if not transfer.can_transition_to(BranchTransfer.IN_TRANSIT):
        # Already dispatched — idempotent replay
        if transfer.status == BranchTransfer.IN_TRANSIT and idempotency_key is not None:
            logger.info(
                "dispatch_transfer idempotent replay for transfer %s (key=%s)",
                transfer.pk,
                idempotency_key,
            )
            return
        raise ValidationError(f"Cannot dispatch a transfer with status {transfer.status}.")

    lines = list(
        BranchTransferLine.objects.select_for_update().filter(transfer=transfer)
    )
    if not lines:
        raise ValidationError("Cannot dispatch a transfer with no lines.")

    assert_inventory_period_open(transfer.organization, timezone.now())

    lot_enabled = getattr(settings, "LOT_TRACKING_TRANSFERS_ENABLED", False)

    for line in lines:
        sku = line.item.sku
        name = line.item.display_name
        cost_state = get_inventory_cost_state_for_update(
            organization=transfer.organization,
            branch=transfer.from_branch,
            item=line.item,
        )
        if cost_state is None:
            raise ValidationError(
                f"No cost state found for {sku} ({name}) in source branch. Post a receipt first."
            )
        if cost_state.average_unit_cost is None:
            raise ValidationError(
                f"No AVCO found for {sku} ({name}) in source branch. Post a receipt first."
            )
        line.dispatched_unit_cost = cost_state.average_unit_cost.quantize(Decimal("0.0001"))
        line.save(update_fields=["dispatched_unit_cost"])

        ikey = f"{idempotency_key}:line:{line.pk}" if idempotency_key is not None else None
        try:
            ledger, _ = record_stock_movement(
                org=transfer.organization,
                item=line.item,
                branch=transfer.from_branch,
                quantity=-line.quantity_sent,
                movement_type=MOVEMENT_ISSUE,
                performed_by=performed_by,
                idempotency_key=ikey,
            )
        except ValidationError as exc:
            raise ValidationError(
                f"Cannot dispatch line for {sku} ({name}): " + " ".join(exc.messages)
            )

        # Lot tracking: auto-allocate via FEFO/FIFO and deplete source lots
        if lot_enabled and line.item.is_lot_tracked:
            try:
                lot_allocations = allocate_lots_fefo_fifo(
                    org=transfer.organization,
                    branch=transfer.from_branch,
                    item=line.item,
                    quantity=Decimal(str(line.quantity_sent)),
                )
            except ValidationError as exc:
                raise ValidationError(
                    f"Lot allocation failed for {sku} ({name}): " + " ".join(exc.messages)
                )
            for lot, alloc_qty in lot_allocations:
                deplete_lot_balance(lot, alloc_qty)
                create_branch_transfer_dispatch_lot_allocation(
                    transfer_line=line,
                    lot=lot,
                    quantity=alloc_qty,
                )
                create_stock_movement_lot_allocation(
                    ledger=ledger,
                    lot=lot,
                    quantity=alloc_qty,
                )

    transfer.status = BranchTransfer.IN_TRANSIT
    transfer.dispatched_by = performed_by
    transfer.dispatched_at = timezone.now()
    transfer.save(update_fields=["status", "dispatched_by", "dispatched_at", "updated_at"])
    transaction.on_commit(
        lambda: inventory_signals.branch_transfer_dispatched.send(
            sender=dispatch_transfer,
            organization_id=str(transfer.organization_id),
            actor_user_id=str(performed_by.id),
            transfer_id=str(transfer.id),
            before_status=BranchTransfer.APPROVED,
            after_status=transfer.status,
        )
    )
    logger.info("Transfer %s dispatched by user %s", transfer.pk, performed_by)


@transaction.atomic
def receive_transfer(transfer, lines_data, performed_by, receive_notes="", idempotency_key=None,
                     lot_override=False, lot_override_reason=""):
    transfer = BranchTransfer.objects.select_for_update().get(pk=transfer.pk)

    if transfer.status != BranchTransfer.IN_TRANSIT:
        # Idempotent replay: already received
        if transfer.status in (
            BranchTransfer.RECEIVED_COMPLETE,
            BranchTransfer.RECEIVED_WITH_VARIANCE,
        ) and idempotency_key is not None:
            logger.info(
                "receive_transfer idempotent replay for transfer %s (key=%s)",
                transfer.pk,
                idempotency_key,
            )
            return
        raise ValidationError(f"Cannot receive a transfer with status {transfer.status}.")

    assert_inventory_period_open(transfer.to_organization, timezone.now())

    lot_enabled = getattr(settings, "LOT_TRACKING_TRANSFERS_ENABLED", False)

    all_transfer_lines = list(
        BranchTransferLine.objects.select_for_update().filter(transfer=transfer)
    )
    all_line_ids = {line.pk for line in all_transfer_lines}
    payload_line_ids = {line_data["line_id"] for line_data in lines_data}

    if payload_line_ids != all_line_ids:
        missing = all_line_ids - payload_line_ids
        extra = payload_line_ids - all_line_ids
        raise ValidationError(
            f"Receive payload must include every transfer line exactly once. "
            f"Missing: {missing}. Extra: {extra}."
        )

    lines_locked = {line.pk: line for line in all_transfer_lines}

    for line_data in lines_data:
        line = lines_locked[line_data["line_id"]]
        quantity_received = line_data["quantity_received"]

        if quantity_received < 0:
            raise ValidationError(f"quantity_received cannot be negative on line {line.pk}.")
        if quantity_received > line.quantity_sent:
            raise ValidationError(
                f"quantity_received ({quantity_received}) exceeds quantity_sent "
                f"({line.quantity_sent}) on line {line.pk}."
            )

        if quantity_received > 0:
            if line.dispatched_unit_cost is None:
                raise ValidationError(
                    f"Transfer line {line.pk} is missing dispatch cost snapshot. "
                    "Redispatch or backfill dispatched_unit_cost before receiving."
                )
            recipient_item = get_or_create_recipient_item(
                master_item=line.item.master_item,
                to_organization=transfer.to_organization,
            )
            get_or_create_recipient_branch_item(
                org_item=recipient_item,
                branch=transfer.to_branch,
            )
            ikey = f"{idempotency_key}:line:{line.pk}" if idempotency_key is not None else None
            ledger, _ = record_stock_movement(
                org=transfer.to_organization,
                item=recipient_item,
                branch=transfer.to_branch,
                quantity=quantity_received,
                movement_type=MOVEMENT_RECEIPT,
                unit_cost=line.dispatched_unit_cost,
                is_transfer_receive=True,
                performed_by=performed_by,
                idempotency_key=ikey,
            )

            # Lot tracking: preserve lot identity from dispatch allocations
            if lot_enabled and line.item.is_lot_tracked:
                _apply_receive_lot_allocations(
                    transfer=transfer,
                    line=line,
                    recipient_item=recipient_item,
                    ledger=ledger,
                    quantity_received=Decimal(str(quantity_received)),
                    lot_override=lot_override,
                    lot_override_reason=lot_override_reason,
                )

        line.quantity_received = quantity_received
        line.save(update_fields=["quantity_received"])

    # Reuse the already-locked lines list — no second queryset fetch
    if all(line.quantity_received == line.quantity_sent for line in all_transfer_lines):
        new_status = BranchTransfer.RECEIVED_COMPLETE
    else:
        new_status = BranchTransfer.RECEIVED_WITH_VARIANCE

    transfer.status = new_status
    transfer.received_by = performed_by
    transfer.received_at = timezone.now()
    transfer.receive_notes = receive_notes or ""
    transfer.save(
        update_fields=[
            "status",
            "received_by",
            "received_at",
            "receive_notes",
            "updated_at",
        ]
    )
    transaction.on_commit(
        lambda: inventory_signals.branch_transfer_received.send(
            sender=receive_transfer,
            organization_id=str(transfer.to_organization_id),
            actor_user_id=str(performed_by.id),
            transfer_id=str(transfer.id),
            before_status=BranchTransfer.IN_TRANSIT,
            after_status=transfer.status,
        )
    )
    logger.info(
        "Transfer %s received by user %s with status %s",
        transfer.pk,
        performed_by,
        new_status,
    )


# ---------------------------------------------------------------------------
# Internal lot helpers
# ---------------------------------------------------------------------------

def _apply_receive_lot_allocations(
    *, transfer, line, recipient_item, ledger, quantity_received,
    lot_override=False, lot_override_reason=""
):
    """
    At receive time, look up the dispatch lot allocations and create
    matching destination lot balances.

    If a destination lot with the same lot_code exists but has conflicting
    expiry_date / manufacture_date, raises ValidationError unless lot_override=True.
    """
    dispatch_allocs = get_dispatch_lot_allocations(transfer_line=line)

    if not dispatch_allocs:
        logger.warning(
            "Lot-tracked item %s on transfer line %s has no dispatch lot allocations.",
            line.item_id,
            line.pk,
        )
        return

    # Scale allocations to quantity_received (partial receives possible)
    total_dispatched = sum(a.quantity for a in dispatch_allocs)
    ratio = quantity_received / total_dispatched if total_dispatched else Decimal("1")

    for dispatch_alloc in dispatch_allocs:
        source_lot = dispatch_alloc.lot
        alloc_qty = (dispatch_alloc.quantity * ratio).quantize(Decimal("0.0001"))

        if alloc_qty <= 0:
            continue

        # Try to find an existing lot at destination with same lot_code
        existing_lot = find_lot_balance_by_code(
            organization=transfer.to_organization,
            branch=transfer.to_branch,
            org_item=recipient_item,
            lot_code=source_lot.lot_code,
        )

        if existing_lot is not None:
            # Check for conflicting metadata
            conflict = (
                existing_lot.expiry_date != source_lot.expiry_date
                or existing_lot.manufacture_date != source_lot.manufacture_date
            )
            if conflict and not lot_override:
                raise ValidationError(
                    f"Lot '{source_lot.lot_code}' already exists at destination branch with "
                    f"conflicting expiry/manufacture dates. "
                    "Provide lot_override=True with a reason to proceed."
                )
            if conflict:
                logger.warning(
                    "Lot override applied for lot '%s' on transfer %s: %s",
                    source_lot.lot_code,
                    transfer.pk,
                    lot_override_reason,
                )
            dest_lot = existing_lot
        else:
            dest_lot, _ = get_or_create_lot(
                org=transfer.to_organization,
                branch=transfer.to_branch,
                org_item=recipient_item,
                lot_code=source_lot.lot_code,
                expiry_date=source_lot.expiry_date,
                manufacture_date=source_lot.manufacture_date,
            )

        increment_lot_balance(dest_lot, alloc_qty)

        create_branch_transfer_receive_lot_allocation(
            transfer_line=line,
            lot=dest_lot,
            quantity=alloc_qty,
        )
        create_stock_movement_lot_allocation(
            ledger=ledger,
            lot=dest_lot,
            quantity=alloc_qty,
        )

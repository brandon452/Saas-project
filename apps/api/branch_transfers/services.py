import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from inventory.models import BranchItem, InventoryCostState, OrgItem, StockLedger
from inventory.services import assert_inventory_period_open, record_stock_movement

from .models import BranchTransfer, BranchTransferLine

logger = logging.getLogger(__name__)


def _get_or_create_recipient_item(master_item, to_organization):
    org_item, created = OrgItem.objects.get_or_create(
        organization=to_organization,
        master_item=master_item,
        defaults={
            "name": "",
            "is_active": True,
        },
    )
    if not created and not org_item.is_active:
        org_item.is_active = True
        org_item.save(update_fields=["is_active"])
    return org_item


def _get_or_create_recipient_branch_item(org_item, branch):
    branch_item, created = BranchItem.objects.get_or_create(
        org_item=org_item,
        branch=branch,
        defaults={
            "is_active": True,
        },
    )
    if not created and not branch_item.is_active:
        branch_item.is_active = True
        branch_item.save(update_fields=["is_active"])
    return branch_item


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

    for line in lines:
        sku = line.item.sku
        name = line.item.display_name
        try:
            cost_state = InventoryCostState.objects.select_for_update().get(
                organization=transfer.organization,
                branch=transfer.from_branch,
                item=line.item,
            )
        except InventoryCostState.DoesNotExist:
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
            record_stock_movement(
                org=transfer.organization,
                item=line.item,
                branch=transfer.from_branch,
                quantity=-line.quantity_sent,
                movement_type=StockLedger.MOVEMENT_ISSUE,
                performed_by=performed_by,
                idempotency_key=ikey,
            )
        except ValidationError as exc:
            raise ValidationError(
                f"Cannot dispatch line for {sku} ({name}): " + " ".join(exc.messages)
            )

    transfer.status = BranchTransfer.IN_TRANSIT
    transfer.dispatched_by = performed_by
    transfer.dispatched_at = timezone.now()
    transfer.save(update_fields=["status", "dispatched_by", "dispatched_at", "updated_at"])
    logger.info("Transfer %s dispatched by user %s", transfer.pk, performed_by)


@transaction.atomic
def receive_transfer(transfer, lines_data, performed_by, receive_notes="", idempotency_key=None):
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
            recipient_item = _get_or_create_recipient_item(
                master_item=line.item.master_item,
                to_organization=transfer.to_organization,
            )
            _get_or_create_recipient_branch_item(
                org_item=recipient_item,
                branch=transfer.to_branch,
            )
            ikey = f"{idempotency_key}:line:{line.pk}" if idempotency_key is not None else None
            record_stock_movement(
                org=transfer.to_organization,
                item=recipient_item,
                branch=transfer.to_branch,
                quantity=quantity_received,
                movement_type=StockLedger.MOVEMENT_RECEIPT,
                unit_cost=line.dispatched_unit_cost,
                is_transfer_receive=True,
                performed_by=performed_by,
                idempotency_key=ikey,
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
    logger.info(
        "Transfer %s received by user %s with status %s",
        transfer.pk,
        performed_by,
        new_status,
    )

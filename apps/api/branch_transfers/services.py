from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from inventory.models import BranchItem, OrgItem, StockLedger
from inventory.services import record_stock_movement

from .models import BranchTransfer, BranchTransferLine


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
def dispatch_transfer(transfer, performed_by):
    transfer = BranchTransfer.objects.select_for_update().get(pk=transfer.pk)

    if not transfer.can_transition_to(BranchTransfer.IN_TRANSIT):
        raise ValidationError(f"Cannot dispatch a transfer with status {transfer.status}.")

    lines = list(
        BranchTransferLine.objects.select_for_update().filter(transfer=transfer)
    )
    if not lines:
        raise ValidationError("Cannot dispatch a transfer with no lines.")

    for line in lines:
        record_stock_movement(
            org=transfer.organization,
            item=line.item,
            branch=transfer.from_branch,
            quantity=-line.quantity_sent,
            movement_type=StockLedger.MOVEMENT_ISSUE,
            performed_by=performed_by,
        )

    transfer.status = BranchTransfer.IN_TRANSIT
    transfer.dispatched_at = timezone.now()
    transfer.save(update_fields=["status", "dispatched_at", "updated_at"])


@transaction.atomic
def receive_transfer(transfer, lines_data, performed_by, receive_notes=""):
    transfer = BranchTransfer.objects.select_for_update().get(pk=transfer.pk)

    if transfer.status != BranchTransfer.IN_TRANSIT:
        raise ValidationError(f"Cannot receive a transfer with status {transfer.status}.")

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
            record_stock_movement(
                org=transfer.to_organization,
                item=recipient_item,
                branch=transfer.to_branch,
                quantity=quantity_received,
                movement_type=StockLedger.MOVEMENT_RECEIPT,
                performed_by=performed_by,
            )

        line.quantity_received = quantity_received
        line.save(update_fields=["quantity_received"])

    all_lines = list(transfer.lines.all())
    if all(line.quantity_received == line.quantity_sent for line in all_lines):
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

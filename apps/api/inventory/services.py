from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import BranchItem, StockLedger, StockOnHand, StockTake, StockTakeLine


@transaction.atomic
def record_stock_movement(
    org,
    branch,
    item,
    quantity,
    movement_type,
    *,
    performed_by=None,
    reference_type=None,
    reference_id=None,
    reason=None,
    occurred_at=None,
    idempotency_key=None,
):
    """
    Concurrency-safe, idempotency-aware stock update.

    Returns: (ledger, created)
      created=True  -> new movement applied
      created=False -> duplicate detected, existing row returned
    """
    effective_occurred_at = occurred_at or timezone.now()

    if quantity == 0:
        raise ValidationError("Movement quantity cannot be zero.")

    if idempotency_key is not None:
        existing = StockLedger.objects.for_org(org).filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing, False

    stock_qs = StockOnHand.objects
    if hasattr(stock_qs, "for_org"):
        stock_qs = stock_qs.for_org(org)

    stock_on_hand = None
    if quantity < 0:
        stock_on_hand = (
            stock_qs
            .select_for_update()
            .filter(organization=org, branch=branch, item=item)
            .first()
        )
        current_quantity = stock_on_hand.quantity if stock_on_hand else 0
        if current_quantity + quantity < 0:
            raise ValidationError(
                f"Insufficient stock. Available: {current_quantity}, requested: {abs(quantity)}."
            )
    else:
        try:
            stock_on_hand = (
                stock_qs
                .select_for_update()
                .get(organization=org, branch=branch, item=item)
            )
        except StockOnHand.DoesNotExist:
            try:
                # Use an inner savepoint so concurrent create races do not
                # poison the outer transaction state.
                with transaction.atomic():
                    stock_on_hand = StockOnHand.objects.create(
                        organization=org,
                        branch=branch,
                        item=item,
                        quantity=0,
                    )
            except IntegrityError:
                stock_on_hand = (
                    stock_qs
                    .select_for_update()
                    .get(organization=org, branch=branch, item=item)
                )

    stock_on_hand.quantity += quantity
    stock_on_hand.save(update_fields=["quantity"])

    ledger = StockLedger.objects.create(
        organization=org,
        branch=branch,
        item=item,
        quantity=quantity,
        movement_type=movement_type,
        performed_by=performed_by,
        reference_type=reference_type,
        reference_id=reference_id,
        reason=reason,
        occurred_at=effective_occurred_at,
        idempotency_key=idempotency_key,
    )

    return ledger, True


@transaction.atomic
def start_stock_take(stock_take, performed_by):
    if not stock_take.can_transition_to(StockTake.IN_PROGRESS):
        raise ValidationError(f"Cannot start a stock take with status {stock_take.status}.")

    stock_take = StockTake.objects.select_for_update().get(pk=stock_take.pk)
    if not stock_take.can_transition_to(StockTake.IN_PROGRESS):
        raise ValidationError(f"Cannot start a stock take with status {stock_take.status}.")

    branch_items = (
        BranchItem.objects.filter(
            branch=stock_take.branch,
            is_active=True,
            org_item__organization=stock_take.organization,
            org_item__is_active=True,
        )
        .select_related("org_item")
    )
    if not branch_items.exists():
        raise ValidationError(
            "No active items found for this branch. "
            "Set up the branch item catalog before starting a count."
        )

    stock_on_hand_map = {
        stock_on_hand.item_id: stock_on_hand.quantity
        for stock_on_hand in StockOnHand.objects.filter(
            organization=stock_take.organization,
            branch=stock_take.branch,
        )
    }
    lines = [
        StockTakeLine(
            stock_take=stock_take,
            org_item=branch_item.org_item,
            snapshot_quantity=stock_on_hand_map.get(branch_item.org_item_id, Decimal("0")),
            counted_quantity=None,
        )
        for branch_item in branch_items
    ]
    StockTakeLine.objects.bulk_create(lines)

    stock_take.status = StockTake.IN_PROGRESS
    stock_take.started_by = performed_by
    stock_take.started_at = timezone.now()
    stock_take.save(update_fields=["status", "started_by", "started_at", "updated_at"])


@transaction.atomic
def submit_stock_take(stock_take, performed_by):
    if not stock_take.can_transition_to(StockTake.PENDING_APPROVAL):
        raise ValidationError(f"Cannot submit a stock take with status {stock_take.status}.")

    stock_take = StockTake.objects.select_for_update().get(pk=stock_take.pk)
    if not stock_take.can_transition_to(StockTake.PENDING_APPROVAL):
        raise ValidationError(f"Cannot submit a stock take with status {stock_take.status}.")

    all_lines = StockTakeLine.objects.select_for_update().filter(stock_take=stock_take)
    if all_lines.exists() and not all_lines.filter(counted_quantity__isnull=False).exists():
        raise ValidationError(
            "Cannot submit a stock take where no items have been counted. "
            "Enter at least one counted quantity before submitting."
        )

    stock_take.status = StockTake.PENDING_APPROVAL
    stock_take.submitted_by = performed_by
    stock_take.submitted_at = timezone.now()
    stock_take.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])


@transaction.atomic
def reopen_stock_take(stock_take, performed_by):
    del performed_by

    if not stock_take.can_transition_to(StockTake.IN_PROGRESS):
        raise ValidationError(f"Cannot reopen a stock take with status {stock_take.status}.")

    stock_take = StockTake.objects.select_for_update().get(pk=stock_take.pk)
    if not stock_take.can_transition_to(StockTake.IN_PROGRESS):
        raise ValidationError(f"Cannot reopen a stock take with status {stock_take.status}.")

    stock_take.status = StockTake.IN_PROGRESS
    stock_take.submitted_by = None
    stock_take.submitted_at = None
    stock_take.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])


@transaction.atomic
def approve_stock_take(stock_take, performed_by):
    if not stock_take.can_transition_to(StockTake.COMPLETED):
        raise ValidationError(f"Cannot approve a stock take with status {stock_take.status}.")

    stock_take = StockTake.objects.select_for_update().get(pk=stock_take.pk)
    if not stock_take.can_transition_to(StockTake.COMPLETED):
        raise ValidationError(f"Cannot approve a stock take with status {stock_take.status}.")

    lines = list(
        StockTakeLine.objects.select_for_update()
        .filter(stock_take=stock_take)
        .select_related("org_item")
    )
    stock_on_hand_map = {
        stock_on_hand.item_id: stock_on_hand.quantity
        for stock_on_hand in StockOnHand.objects.select_for_update().filter(
            organization=stock_take.organization,
            branch=stock_take.branch,
        )
    }

    for line in lines:
        if line.counted_quantity is None:
            continue

        live_quantity = stock_on_hand_map.get(line.org_item_id, Decimal("0"))
        adjustment = line.counted_quantity - live_quantity
        if adjustment == 0:
            continue

        record_stock_movement(
            org=stock_take.organization,
            branch=stock_take.branch,
            item=line.org_item,
            quantity=adjustment,
            movement_type=StockLedger.MOVEMENT_ADJUSTMENT,
            performed_by=performed_by,
            reference_type="STOCK_TAKE",
            reference_id=str(stock_take.id),
        )

    stock_take.status = StockTake.COMPLETED
    stock_take.approved_by = performed_by
    stock_take.approved_at = timezone.now()
    stock_take.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])


@transaction.atomic
def cancel_stock_take(stock_take, performed_by):
    if not stock_take.can_transition_to(StockTake.CANCELLED):
        raise ValidationError(f"Cannot cancel a stock take with status {stock_take.status}.")

    stock_take = StockTake.objects.select_for_update().get(pk=stock_take.pk)
    if not stock_take.can_transition_to(StockTake.CANCELLED):
        raise ValidationError(f"Cannot cancel a stock take with status {stock_take.status}.")

    stock_take.status = StockTake.CANCELLED
    stock_take.cancelled_by = performed_by
    stock_take.cancelled_at = timezone.now()
    stock_take.save(update_fields=["status", "cancelled_by", "cancelled_at", "updated_at"])

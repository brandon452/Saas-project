import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    BranchItem, InventoryClosePeriod, InventoryCostState, InventoryCloseSnapshot,
    StockLedger, StockOnHand, StockTake, StockTakeLine,
)

logger = logging.getLogger(__name__)


def assert_inventory_period_open(org, effective_at):
    # Must be called BEFORE any StockOnHand locks to avoid deadlocks with close_period()
    ts = effective_at or timezone.now()
    conflict = InventoryClosePeriod.objects.select_for_update().filter(
        organization=org,
        status__in=[InventoryClosePeriod.CLOSING, InventoryClosePeriod.CLOSED],
        start_date__lte=ts.date(),
        end_date__gte=ts.date(),
    ).first()
    if conflict:
        if conflict.status == InventoryClosePeriod.CLOSING:
            raise ValidationError(
                f"Period {conflict.start_date}–{conflict.end_date} is currently closing. Try again shortly."
            )
        raise ValidationError(f"Period {conflict.start_date}–{conflict.end_date} is closed.")


@transaction.atomic
def record_stock_movement(
    org,
    branch,
    item,
    quantity,
    movement_type,
    *,
    unit_cost=None,
    _force_unit_cost=None,
    is_transfer_receive=False,
    performed_by=None,
    reference_type=None,
    reference_id=None,
    reason=None,
    occurred_at=None,
    idempotency_key=None,
):
    """
    Concurrency-safe, idempotency-aware stock update with perpetual AVCO costing.

    Returns: (ledger, created)
      created=True  -> new movement applied
      created=False -> duplicate detected, existing row returned
    """
    effective_occurred_at = occurred_at or timezone.now()

    if quantity == 0:
        raise ValidationError("Movement quantity cannot be zero.")

    # Step 1 — period check before any lock
    # Must be called BEFORE any StockOnHand locks to avoid deadlocks with close_period()
    assert_inventory_period_open(org, occurred_at)

    # Sign validation
    if movement_type == StockLedger.MOVEMENT_RECEIPT and quantity <= 0:
        raise ValidationError("RECEIPT quantity must be positive.")
    if movement_type == StockLedger.MOVEMENT_ISSUE and quantity >= 0:
        raise ValidationError("ISSUE quantity must be negative.")

    if idempotency_key is not None:
        existing = (
            StockLedger.objects.for_org(org)
            .select_for_update()
            .filter(idempotency_key=idempotency_key)
            .first()
        )
        if existing:
            return existing, False

    # Step 2 — Lock StockOnHand
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
            stock_on_hand = stock_qs.select_for_update().get(organization=org, branch=branch, item=item)
        except StockOnHand.DoesNotExist:
            try:
                with transaction.atomic():
                    stock_on_hand = StockOnHand.objects.create(
                        organization=org, branch=branch, item=item, quantity=0,
                    )
            except IntegrityError:
                stock_on_hand = stock_qs.select_for_update().get(organization=org, branch=branch, item=item)

    # Step 3 — Race-safe InventoryCostState get/create
    try:
        cost_state = InventoryCostState.objects.select_for_update().get(
            organization=org, branch=branch, item=item)
    except InventoryCostState.DoesNotExist:
        try:
            with transaction.atomic():
                cost_state = InventoryCostState.objects.create(
                    organization=org, branch=branch, item=item,
                    average_unit_cost=None, latest_unit_cost=None,
                )
        except IntegrityError:
            cost_state = InventoryCostState.objects.select_for_update().get(
                organization=org, branch=branch, item=item)

    # Step 4 — Resolve cost by movement type
    Q4 = Decimal("0.0001")
    if movement_type == StockLedger.MOVEMENT_RECEIPT:
        if unit_cost is None:
            raise ValidationError("unit_cost is required for RECEIPT movements.")
        unit_cost = unit_cost.quantize(Q4)
        old_qty = stock_on_hand.quantity
        old_avg = (cost_state.average_unit_cost or Decimal("0")).quantize(Q4)
        new_total_qty = old_qty + quantity
        if new_total_qty <= 0:
            raise ValidationError(
                "Invalid stock state: total quantity cannot be zero or negative after receipt."
            )
        new_avg = (old_avg * old_qty + unit_cost * quantity) / new_total_qty
        cost_state.average_unit_cost = new_avg.quantize(Q4)
        cost_state.latest_unit_cost = unit_cost
        if not is_transfer_receive:
            cost_state.last_receipt_at = effective_occurred_at
        cost_state.save()
    elif movement_type == StockLedger.MOVEMENT_ISSUE:
        if unit_cost is not None:
            raise ValidationError(
                "unit_cost must not be provided for ISSUE movements; cost is derived from AVCO."
            )
        if cost_state.average_unit_cost is None:
            raise ValidationError("No cost basis for this item. Post a receipt first.")
        unit_cost = cost_state.average_unit_cost
    elif movement_type == StockLedger.MOVEMENT_ADJUSTMENT:
        if unit_cost is not None and _force_unit_cost is None:
            raise ValidationError(
                "unit_cost must not be provided for ADJUSTMENT movements; cost is derived from AVCO."
            )
        if _force_unit_cost is not None:
            unit_cost = _force_unit_cost.quantize(Q4)
            if quantity > 0:
                old_qty = stock_on_hand.quantity
                old_avg = (cost_state.average_unit_cost or Decimal("0")).quantize(Q4)
                new_total_qty = old_qty + quantity
                if new_total_qty > 0:
                    new_avg = (old_avg * old_qty + unit_cost * quantity) / new_total_qty
                    cost_state.average_unit_cost = new_avg.quantize(Q4)
                    cost_state.save(update_fields=["average_unit_cost", "updated_at"])
        else:
            if cost_state.average_unit_cost is None:
                if quantity > 0:
                    raise ValidationError(
                        "Positive stock additions require a cost basis. "
                        "Use a direct receipt to introduce costed stock, or wait for the opening-balance flow."
                    )
                raise ValidationError("No cost basis for this item. Post a receipt first.")
            unit_cost = cost_state.average_unit_cost

    # Step 5 — Update StockOnHand and write ledger
    stock_on_hand.quantity += quantity
    stock_on_hand.save(update_fields=["quantity"])

    ledger_unit_cost = unit_cost.quantize(Q4) if unit_cost is not None else None
    value_delta = (unit_cost * quantity).quantize(Q4) if unit_cost is not None else None

    ledger = StockLedger.objects.create(
        organization=org,
        branch=branch,
        item=item,
        quantity=quantity,
        movement_type=movement_type,
        unit_cost=ledger_unit_cost,
        value_delta=value_delta,
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

    # DB-level uniqueness (unique_in_progress_stock_take_per_branch) enforces this
    # at the constraint level. The existence check below guards the user-facing
    # error message; the constraint catches any concurrent race that bypasses it.
    if StockTake.objects.filter(
        organization=stock_take.organization,
        branch=stock_take.branch,
        status=StockTake.IN_PROGRESS,
    ).exclude(pk=stock_take.pk).exists():
        logger.warning(
            "start_stock_take blocked: IN_PROGRESS stock take already exists for branch %s",
            stock_take.branch_id,
        )
        raise ValidationError(
            "A stock take is already in progress for this branch. "
            "Complete or cancel it before starting a new one."
        )

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

    now = timezone.now()
    stock_take.status = StockTake.IN_PROGRESS
    stock_take.started_by = performed_by
    stock_take.started_at = now
    stock_take.snapshot_taken_at = now
    stock_take.save(update_fields=["status", "started_by", "started_at", "snapshot_taken_at", "updated_at"])


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
    if not stock_take.can_transition_to(StockTake.IN_PROGRESS):
        raise ValidationError(f"Cannot reopen a stock take with status {stock_take.status}.")

    stock_take = StockTake.objects.select_for_update().get(pk=stock_take.pk)
    if not stock_take.can_transition_to(StockTake.IN_PROGRESS):
        raise ValidationError(f"Cannot reopen a stock take with status {stock_take.status}.")

    stock_take.status = StockTake.IN_PROGRESS
    stock_take.submitted_by = None
    stock_take.submitted_at = None
    stock_take.reopened_by = performed_by
    stock_take.reopened_at = timezone.now()
    stock_take.save(update_fields=["status", "submitted_by", "submitted_at", "reopened_by", "reopened_at", "updated_at"])


@transaction.atomic
def approve_stock_take(stock_take, performed_by):
    if not stock_take.can_transition_to(StockTake.COMPLETED):
        raise ValidationError(f"Cannot approve a stock take with status {stock_take.status}.")

    stock_take = StockTake.objects.select_for_update().get(pk=stock_take.pk)
    if not stock_take.can_transition_to(StockTake.COMPLETED):
        raise ValidationError(f"Cannot approve a stock take with status {stock_take.status}.")

    assert_inventory_period_open(stock_take.organization, timezone.now())

    lines = list(
        StockTakeLine.objects.select_for_update()
        .filter(stock_take=stock_take)
        .select_related("org_item")
    )

    # Pre-validate AVCO exists for all lines with a non-zero variance
    stock_on_hand_map = {
        soh.item_id: soh.quantity
        for soh in StockOnHand.objects.filter(
            organization=stock_take.organization,
            branch=stock_take.branch,
        )
    }
    cost_map = {
        cs.item_id: cs
        for cs in InventoryCostState.objects.filter(
            organization=stock_take.organization,
            branch=stock_take.branch,
        )
    }
    missing_cost = []
    for line in lines:
        if line.counted_quantity is None:
            continue
        live_qty = stock_on_hand_map.get(line.org_item_id, Decimal("0"))
        if line.counted_quantity - live_qty == 0:
            continue
        cs = cost_map.get(line.org_item_id)
        if cs is None or cs.average_unit_cost is None:
            missing_cost.append(line.org_item.sku)
    if missing_cost:
        cap = 20
        skus = ", ".join(missing_cost[:cap])
        suffix = f" (and {len(missing_cost) - cap} more)" if len(missing_cost) > cap else ""
        raise ValidationError(
            f"{len(missing_cost)} item(s) have no AVCO cost basis. "
            f"Post a receipt before approving: {skus}{suffix}"
        )

    stock_on_hand_map = {
        stock_on_hand.item_id: stock_on_hand.quantity
        for stock_on_hand in StockOnHand.objects.select_for_update().filter(
            organization=stock_take.organization,
            branch=stock_take.branch,
        )
    }

    any_adjustments = False
    for line in lines:
        if line.counted_quantity is None:
            continue

        live_quantity = stock_on_hand_map.get(line.org_item_id, Decimal("0"))
        adjustment = line.counted_quantity - live_quantity
        if adjustment == 0:
            continue

        any_adjustments = True
        try:
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
        except ValidationError as exc:
            sku = line.org_item.master_item.sku
            name = line.org_item.display_name
            raise ValidationError(
                f"Cannot apply adjustment for {sku} ({name}): "
                + " ".join(exc.messages)
            )

    final_status = StockTake.COMPLETED_WITH_VARIANCES if any_adjustments else StockTake.COMPLETED
    stock_take.status = final_status
    stock_take.approved_by = performed_by
    stock_take.approved_at = timezone.now()
    stock_take.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    logger.info(
        "Stock take %s completed with status %s by user %s",
        stock_take.pk,
        final_status,
        performed_by,
    )


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


@transaction.atomic
def close_period(period, closed_by):
    # Step 1 — Lock period row
    period = InventoryClosePeriod.objects.select_for_update().get(pk=period.pk)
    if period.status != InventoryClosePeriod.OPEN:
        raise ValidationError("Only an OPEN period can be closed.")

    # Step 2 — Defensive overlap re-check (also enforced at create time)
    if InventoryClosePeriod.objects.filter(
        organization=period.organization,
        start_date__lte=period.end_date,
        end_date__gte=period.start_date,
    ).exclude(pk=period.pk).exists():
        raise ValidationError("Period overlaps an existing period.")

    # Step 3 — Transition to CLOSING — blocks new movements immediately
    period.status = InventoryClosePeriod.CLOSING
    period.save(update_fields=["status"])

    # Step 4 — Lock all positive StockOnHand rows.
    #   Zero-on-hand rows excluded — no value, no AVCO requirement.
    #   Missing snapshot row = qty=0 for consumers.
    on_hand_rows = list(
        StockOnHand.objects.select_for_update()
        .filter(organization=period.organization, quantity__gt=0)
        .select_related("branch", "item")
    )

    # Step 5 — Read InventoryCostState for locked (branch, item) pairs.
    #   No separate lock needed — concurrent movements are serialized by their
    #   locked StockOnHand rows. close_period() is read-only on InventoryCostState.
    locked_pairs = [(r.branch_id, r.item_id) for r in on_hand_rows]
    cost_map = {
        (c.branch_id, c.item_id): c
        for c in InventoryCostState.objects.filter(
            organization=period.organization,
            branch_id__in={p[0] for p in locked_pairs},
            item_id__in={p[1] for p in locked_pairs},
        )
    }

    # Step 6 — Validate AVCO, surface up to 20 SKUs
    missing = [
        r for r in on_hand_rows
        if not cost_map.get((r.branch_id, r.item_id))
        or cost_map[(r.branch_id, r.item_id)].average_unit_cost is None
    ]
    if missing:
        cap = 20
        skus = ", ".join(r.item.sku for r in missing[:cap])
        suffix = f" (and {len(missing) - cap} more)" if len(missing) > cap else ""
        raise ValidationError(
            f"{len(missing)} item(s) have no AVCO. Correct before closing: {skus}{suffix}"
        )

    # Step 7 — Write snapshots, all decimals quantized to 4dp
    Q = Decimal("0.0001")
    snapshots = []
    for r in on_hand_rows:
        cs = cost_map[(r.branch_id, r.item_id)]
        avg = cs.average_unit_cost.quantize(Q)
        latest = cs.latest_unit_cost.quantize(Q) if cs.latest_unit_cost is not None else None
        snapshots.append(InventoryCloseSnapshot(
            period=period,
            organization=period.organization,
            branch=r.branch,
            item=r.item,
            quantity_on_hand=r.quantity,
            average_unit_cost=avg,
            latest_unit_cost=latest,
            average_valuation=(avg * r.quantity).quantize(Q),
            latest_valuation=(latest * r.quantity).quantize(Q) if latest is not None else None,
            valuation_basis="AVCO",
        ))
    # Replace any prior snapshots if this period was previously closed and reopened.
    InventoryCloseSnapshot.objects.filter(period=period).delete()
    InventoryCloseSnapshot.objects.bulk_create(snapshots)

    # Step 8 — Mark closed
    period.status = InventoryClosePeriod.CLOSED
    period.closed_at = timezone.now()
    period.closed_by = closed_by
    period.save(update_fields=["status", "closed_at", "closed_by"])
    logger.info(
        "Inventory period %s (%s – %s) closed by user %s",
        period.pk,
        period.start_date,
        period.end_date,
        closed_by,
    )


@transaction.atomic
def reopen_period(period, reopened_by):
    period = InventoryClosePeriod.objects.select_for_update().get(pk=period.pk)
    if period.status != InventoryClosePeriod.CLOSED:
        raise ValidationError(
            "Only a CLOSED period can be reopened. "
            "A period in CLOSING state will complete or roll back automatically."
        )
    period.status = InventoryClosePeriod.OPEN
    period.reopened_at = timezone.now()
    period.reopened_by = reopened_by
    period.save(update_fields=["status", "reopened_at", "reopened_by"])

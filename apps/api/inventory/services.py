import logging
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from django.conf import settings

from . import signals
from .models import (
    BranchItem, InventoryClosePeriod, InventoryCostState, InventoryCloseSnapshot,
    InventoryLotBalance, OrgItem, StockLedger, StockMovementLotAllocation,
    StockOnHand, StockTake, StockTakeLine, StockTakeLineLotAllocation,
)

logger = logging.getLogger(__name__)

CYCLE_INTERVAL_DAYS = {
    BranchItem.CLASS_A: 7,
    BranchItem.CLASS_B: 30,
    BranchItem.CLASS_C: 90,
}


def get_org_local_today(org):
    tz_name = getattr(org, "default_timezone", None) or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return timezone.now().astimezone(tz).date()


def assert_inventory_period_open(org, effective_at):
    # Must be called BEFORE any StockOnHand locks to avoid deadlocks with close_period()
    ts = effective_at or timezone.now()
    conflict = InventoryClosePeriod.objects.select_for_update().filter(
        organization=org,
        start_date__lte=ts.date(),
        end_date__gte=ts.date(),
    ).first()
    if conflict:
        if conflict.status == InventoryClosePeriod.CLOSING:
            raise ValidationError(
                f"Period {conflict.start_date}-{conflict.end_date} is currently closing. Try again shortly."
            )
        if conflict.status == InventoryClosePeriod.CLOSED:
            raise ValidationError(f"Period {conflict.start_date}-{conflict.end_date} is closed.")


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
    if idempotency_key is not None:
        existing = (
            StockLedger.objects.for_org(org)
            .select_for_update()
            .filter(idempotency_key=idempotency_key)
            .first()
        )
        if existing:
            return existing, False

    assert_inventory_period_open(org, occurred_at)

    # Sign validation
    if movement_type == StockLedger.MOVEMENT_RECEIPT and quantity <= 0:
        raise ValidationError("RECEIPT quantity must be positive.")
    if movement_type == StockLedger.MOVEMENT_ISSUE and quantity >= 0:
        raise ValidationError("ISSUE quantity must be negative.")

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
        if current_quantity + quantity < 0 and not org.allow_negative_stock:
            raise ValidationError(
                f"Insufficient stock. Available: {current_quantity}, requested: {abs(quantity)}."
            )
        if stock_on_hand is None:
            try:
                with transaction.atomic():
                    stock_on_hand = StockOnHand.objects.create(
                        organization=org, branch=branch, item=item, quantity=0,
                    )
            except IntegrityError:
                stock_on_hand = stock_qs.select_for_update().get(organization=org, branch=branch, item=item)
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

    transaction.on_commit(
        lambda: signals.stock_movement_recorded.send(
            sender=record_stock_movement,
            organization_id=str(org.id),
            branch_id=str(branch.id),
            item_id=str(item.id),
            movement_id=str(ledger.id),
            movement_type=movement_type,
            quantity=str(quantity),
            reference_type=reference_type,
            reference_id=reference_id,
        )
    )

    return ledger, True


@transaction.atomic
def start_stock_take(stock_take, performed_by):
    if not stock_take.can_transition_to(StockTake.IN_PROGRESS):
        raise ValidationError(f"Cannot start a stock take with status {stock_take.status}.")

    stock_take = StockTake.objects.select_for_update().get(pk=stock_take.pk)
    if not stock_take.can_transition_to(StockTake.IN_PROGRESS):
        raise ValidationError(f"Cannot start a stock take with status {stock_take.status}.")

    # DB-level uniqueness constraints enforce this
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

    if (
        stock_take.stock_take_type == StockTake.TYPE_FULL
        and StockTake.objects.filter(
            organization=stock_take.organization,
            branch=stock_take.branch,
            status=StockTake.IN_PROGRESS,
            stock_take_type=StockTake.TYPE_CYCLE,
        ).exclude(pk=stock_take.pk).exists()
    ):
        raise ValidationError(
            "Cannot start a FULL stock take while a CYCLE stock take is in progress for this branch."
        )

    if stock_take.stock_take_type == StockTake.TYPE_CYCLE:
        if not StockTakeLine.objects.filter(stock_take=stock_take).exists():
            raise ValidationError(
                "Cycle stock take has no generated line items. Generate a cycle count first."
            )
    else:
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

    if stock_take.stock_take_type == StockTake.TYPE_CYCLE:
        cycle_lines = list(
            StockTakeLine.objects.filter(stock_take=stock_take).select_related("org_item")
        )
        for line in cycle_lines:
            line.counted_quantity = None

        stock_on_hand_map = {
            stock_on_hand.item_id: stock_on_hand.quantity
            for stock_on_hand in StockOnHand.objects.filter(
                organization=stock_take.organization,
                branch=stock_take.branch,
            )
        }
        for line in cycle_lines:
            line.snapshot_quantity = stock_on_hand_map.get(line.org_item_id, Decimal("0"))
        StockTakeLine.objects.bulk_update(cycle_lines, ["counted_quantity", "snapshot_quantity"])

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
    if not all_lines.exists():
        raise ValidationError(
            "Cannot submit a stock take with no line items. Start the stock take to generate lines first."
        )
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

    lot_enabled = getattr(settings, "LOT_TRACKING_STOCK_TAKE_ENABLED", False)

    # Pre-validate lot allocations for lot-tracked items with non-zero variance
    if lot_enabled:
        for line in lines:
            if line.counted_quantity is None:
                continue
            live_qty = stock_on_hand_map.get(line.org_item_id, Decimal("0"))
            adjustment = line.counted_quantity - live_qty
            if adjustment == 0:
                continue
            if not line.org_item.is_lot_tracked:
                continue

            lot_alloc_qs = StockTakeLineLotAllocation.objects.filter(stock_take_line=line)
            if not lot_alloc_qs.exists():
                sku = line.org_item.sku
                raise ValidationError(
                    f"Item '{sku}' is lot-tracked and has a non-zero variance "
                    "but no lot allocations have been submitted. "
                    "Submit lot allocations before approving."
                )

            # Validate direction / sum consistency
            direction = StockTakeLineLotAllocation.INCREASE if adjustment > 0 else StockTakeLineLotAllocation.DECREASE
            allocs = list(lot_alloc_qs)
            for alloc in allocs:
                if alloc.direction != direction:
                    raise ValidationError(
                        f"Lot allocation direction mismatch for item '{line.org_item.sku}'. "
                        f"Expected {direction} (variance={adjustment})."
                    )
            total_alloc = sum(a.quantity for a in allocs)
            expected = abs(adjustment)
            if total_alloc != expected:
                raise ValidationError(
                    f"Lot allocations for '{line.org_item.sku}' sum to {total_alloc} "
                    f"but variance magnitude is {expected}."
                )

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
            ledger, _ = record_stock_movement(
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

        # Apply lot balance adjustments for lot-tracked items
        if lot_enabled and line.org_item.is_lot_tracked:
            _apply_stock_take_lot_adjustments(
                org=stock_take.organization,
                branch=stock_take.branch,
                org_item=line.org_item,
                line=line,
                ledger=ledger,
                adjustment=adjustment,
            )

    final_status = StockTake.COMPLETED_WITH_VARIANCES if any_adjustments else StockTake.COMPLETED
    if stock_take.stock_take_type == StockTake.TYPE_CYCLE:
        update_cycle_due_dates(stock_take, as_of_date=get_org_local_today(stock_take.organization))
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
    # Step 1 - Lock period row
    period = InventoryClosePeriod.objects.select_for_update().get(pk=period.pk)
    if period.status != InventoryClosePeriod.OPEN:
        raise ValidationError("Only an OPEN period can be closed.")

    # Step 2 - Defensive overlap re-check (also enforced at create time)
    if InventoryClosePeriod.objects.filter(
        organization=period.organization,
        start_date__lte=period.end_date,
        end_date__gte=period.start_date,
    ).exclude(pk=period.pk).exists():
        raise ValidationError("Period overlaps an existing period.")

    # Step 3 - Transition to CLOSING - blocks new movements immediately
    period.status = InventoryClosePeriod.CLOSING
    period.save(update_fields=["status"])

    # Step 4 - build period-end balances from the immutable ledger.
    cutoff = _period_end_cutoff(period.end_date)
    balance_rows = list(
        StockLedger.objects.for_org(period.organization)
        .filter(occurred_at__lte=cutoff)
        .values("branch_id", "item_id")
        .annotate(
            quantity_on_hand=Sum("quantity"),
            average_valuation=Sum("value_delta"),
        )
        .filter(quantity_on_hand__gt=0)
    )

    # Step 5 - latest costed positive movement per branch/item
    branch_ids = {r["branch_id"] for r in balance_rows}
    item_ids = {r["item_id"] for r in balance_rows}
    latest_cost_map = {}
    if balance_rows:
        latest_rows = (
            StockLedger.objects.for_org(period.organization)
            .filter(
                occurred_at__lte=cutoff,
                branch_id__in=branch_ids,
                item_id__in=item_ids,
                movement_type=StockLedger.MOVEMENT_RECEIPT,
                quantity__gt=0,
                unit_cost__isnull=False,
            )
            .order_by("branch_id", "item_id", "-occurred_at", "-created_at")
            .values("branch_id", "item_id", "unit_cost")
        )
        for row in latest_rows:
            latest_cost_map.setdefault((row["branch_id"], row["item_id"]), row["unit_cost"])

    # Step 6 - validate AVCO
    missing = [r for r in balance_rows if r["average_valuation"] is None]
    if missing:
        sku_map = {
            item.pk: item.sku
            for item in OrgItem.objects.filter(pk__in=[r["item_id"] for r in missing])
        }
        cap = 20
        skus = ", ".join(str(sku_map.get(r["item_id"], r["item_id"])) for r in missing[:cap])
        suffix = f" (and {len(missing) - cap} more)" if len(missing) > cap else ""
        raise ValidationError(
            f"{len(missing)} item(s) have no AVCO. Correct before closing: {skus}{suffix}"
        )

    # Step 7 - write snapshots
    quant = Decimal("0.0001")
    snapshots = []
    for r in balance_rows:
        quantity = r["quantity_on_hand"].quantize(quant)
        average_valuation = r["average_valuation"].quantize(quant)
        avg = (average_valuation / quantity).quantize(quant)
        latest_cost = latest_cost_map.get((r["branch_id"], r["item_id"]))
        latest = latest_cost.quantize(quant) if latest_cost is not None else None
        snapshots.append(
            InventoryCloseSnapshot(
                period=period,
                organization=period.organization,
                branch_id=r["branch_id"],
                item_id=r["item_id"],
                quantity_on_hand=quantity,
                average_unit_cost=avg,
                latest_unit_cost=latest,
                average_valuation=average_valuation,
                latest_valuation=(latest * quantity).quantize(quant) if latest is not None else None,
                valuation_basis="AVCO",
            )
        )
    InventoryCloseSnapshot.objects.filter(period=period).delete()
    InventoryCloseSnapshot.objects.bulk_create(snapshots)

    # Step 8 - Mark closed
    period.status = InventoryClosePeriod.CLOSED
    period.closed_at = timezone.now()
    period.closed_by = closed_by
    period.save(update_fields=["status", "closed_at", "closed_by"])
    logger.info(
        "Inventory period %s (%s - %s) closed by user %s",
        period.pk,
        period.start_date,
        period.end_date,
        closed_by,
    )


def update_cycle_due_dates(stock_take, as_of_date):
    if stock_take.stock_take_type != StockTake.TYPE_CYCLE:
        return

    counted_item_ids = list(
        StockTakeLine.objects.filter(
            stock_take=stock_take,
            counted_quantity__isnull=False,
        ).values_list("org_item_id", flat=True)
    )
    if not counted_item_ids:
        return

    branch_items = BranchItem.objects.select_for_update().filter(
        branch=stock_take.branch,
        org_item_id__in=counted_item_ids,
        item_class=stock_take.cycle_item_class,
    )
    days = CYCLE_INTERVAL_DAYS.get(stock_take.cycle_item_class)
    if not days:
        return
    next_due = as_of_date + timedelta(days=days)
    branch_items.update(next_cycle_count_date=next_due)


@transaction.atomic
def generate_cycle_count(*, org, branch, cycle_item_class, scheduled_for, performed_by):
    if StockTake.objects.filter(
        organization=org,
        branch=branch,
        status=StockTake.IN_PROGRESS,
        stock_take_type=StockTake.TYPE_FULL,
    ).exists():
        raise ValidationError(
            "Cannot generate a CYCLE stock take while a FULL stock take is in progress for this branch."
        )

    existing = StockTake.objects.select_for_update().filter(
        organization=org,
        branch=branch,
        stock_take_type=StockTake.TYPE_CYCLE,
        cycle_item_class=cycle_item_class,
        scheduled_for=scheduled_for,
    ).first()

    if existing:
        if existing.status == StockTake.CANCELLED:
            existing.status = StockTake.DRAFT
            existing.started_by = None
            existing.started_at = None
            existing.submitted_by = None
            existing.submitted_at = None
            existing.approved_by = None
            existing.approved_at = None
            existing.cancelled_by = None
            existing.cancelled_at = None
            existing.reopened_by = None
            existing.reopened_at = None
            existing.snapshot_taken_at = None
            existing.save(
                update_fields=[
                    "status",
                    "started_by",
                    "started_at",
                    "submitted_by",
                    "submitted_at",
                    "approved_by",
                    "approved_at",
                    "cancelled_by",
                    "cancelled_at",
                    "reopened_by",
                    "reopened_at",
                    "snapshot_taken_at",
                    "updated_at",
                ]
            )
            existing.lines.all().delete()
            stock_take = existing
        else:
            stock_take = existing

        if existing.status != StockTake.DRAFT:
            raise ValidationError(
                "A cycle stock take already exists for this branch, class, and date and is no longer Draft."
            )
        if stock_take is existing and existing.status == StockTake.DRAFT and stock_take.lines.exists():
            return stock_take, False, 0

    if not existing:
        stock_take = StockTake.objects.create(
            organization=org,
            branch=branch,
            stock_take_type=StockTake.TYPE_CYCLE,
            cycle_item_class=cycle_item_class,
            scheduled_for=scheduled_for,
            status=StockTake.DRAFT,
            created_by=performed_by,
        )

    due_branch_items = list(
        BranchItem.objects.select_related("org_item").filter(
            branch=branch,
            is_active=True,
            item_class=cycle_item_class,
            org_item__organization=org,
            org_item__is_active=True,
        ).filter(
            Q(next_cycle_count_date__isnull=True) | Q(next_cycle_count_date__lte=scheduled_for)
        )
    )

    if not due_branch_items:
        return stock_take, True, 0

    stock_on_hand_map = {
        stock_on_hand.item_id: stock_on_hand.quantity
        for stock_on_hand in StockOnHand.objects.filter(
            organization=org,
            branch=branch,
        )
    }

    lines = [
        StockTakeLine(
            stock_take=stock_take,
            org_item=branch_item.org_item,
            snapshot_quantity=stock_on_hand_map.get(branch_item.org_item_id, Decimal("0")),
            counted_quantity=None,
        )
        for branch_item in due_branch_items
    ]
    StockTakeLine.objects.bulk_create(lines)
    return stock_take, True, len(lines)
def _period_end_cutoff(end_date):
    cutoff = datetime.combine(end_date, time.max)
    if timezone.is_naive(cutoff):
        cutoff = timezone.make_aware(cutoff, timezone.get_current_timezone())
    return cutoff


def _apply_stock_take_lot_adjustments(*, org, branch, org_item, line, ledger, adjustment):
    """
    After a stock-take adjustment ledger row is created, apply lot balance
    changes for each StockTakeLineLotAllocation on the given line.

    - INCREASE allocations: increment lot balances
    - DECREASE allocations: deplete lot balances (with select_for_update lock)

    Also creates StockMovementLotAllocation rows for audit.
    """
    from .lot_services import deplete_lot_balance, get_or_create_lot, increment_lot_balance

    allocs = list(
        StockTakeLineLotAllocation.objects.select_for_update().filter(stock_take_line=line)
    )
    for alloc in allocs:
        if alloc.lot_id:
            lot = InventoryLotBalance.objects.select_for_update().get(pk=alloc.lot_id)
        else:
            # New lot: create from draft fields
            lot, _ = get_or_create_lot(
                org=org,
                branch=branch,
                org_item=org_item,
                lot_code=alloc.lot_code,
                expiry_date=alloc.expiry_date,
                manufacture_date=alloc.manufacture_date,
            )
            lot = InventoryLotBalance.objects.select_for_update().get(pk=lot.pk)

        if alloc.direction == StockTakeLineLotAllocation.INCREASE:
            increment_lot_balance(lot, alloc.quantity)
        else:
            deplete_lot_balance(lot, alloc.quantity, select_for_update=False)

        StockMovementLotAllocation.objects.create(
            ledger=ledger,
            lot=lot,
            quantity=alloc.quantity,
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


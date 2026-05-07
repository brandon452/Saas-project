"""
Lot / Batch + Expiry tracking service layer.

All functions operate within the caller's transaction.  The caller is responsible
for wrapping operations in @transaction.atomic where needed.
"""

import logging
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError

from .models import InventoryLotBalance
from tenancy.permissions import ROLE_POLICY, get_member_role

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# FEFO / FIFO allocation
# ---------------------------------------------------------------------------

def allocate_lots_fefo_fifo(org, branch, item, quantity):
    """
    Allocate *quantity* across available lots using FEFO then FIFO ordering.

    Ordering:
      1. expiry_date ASC NULLS LAST  (lots with expiry consumed before non-expiry)
      2. received_at ASC             (FIFO within same expiry bucket)
      3. id ASC                      (stable tie-break)

    Returns a list of (InventoryLotBalance, allocated_qty: Decimal) tuples.
    Raises ValidationError if there is insufficient lot stock in total.

    NOTE: Rows are NOT locked here; the caller must call deplete_lot_balance
    (which does select_for_update) to actually deduct.
    """
    quantity = Decimal(str(quantity))
    if quantity <= _ZERO:
        raise ValidationError("allocate_lots_fefo_fifo: quantity must be positive.")

    lots = list(
        InventoryLotBalance.objects.filter(
            organization=org,
            branch=branch,
            org_item=item,
            available_qty__gt=_ZERO,
        ).order_by(
            # NULL expiry_dates sort last in PostgreSQL by default for ASC,
            # but we make it explicit via raw ordering trick:
            # Django doesn't support NULLS LAST natively pre-5.0 so we use
            # a workaround: use nulls_last=True when available, fall back to
            # separate annotation for older Django.
            "expiry_date",  # NULLs will sort before non-NULL in some DBs,
            "received_at",  # so we post-process below
            "id",
        )
    )

    # Re-sort in Python to guarantee NULLS LAST for expiry_date across all DB backends
    lots.sort(key=lambda lot: (
        (0, lot.expiry_date) if lot.expiry_date is not None else (1, None),
        lot.received_at,
        lot.id,
    ))

    allocations = []
    remaining = quantity

    for lot in lots:
        if remaining <= _ZERO:
            break
        take = min(lot.available_qty, remaining)
        if take > _ZERO:
            allocations.append((lot, take))
            remaining -= take

    if remaining > _ZERO:
        raise ValidationError(
            f"Insufficient lot stock for item '{item}'. "
            f"Requested: {quantity}, available: {quantity - remaining}."
        )

    return allocations


# ---------------------------------------------------------------------------
# Balance mutation helpers
# ---------------------------------------------------------------------------

def deplete_lot_balance(lot, quantity, *, select_for_update=True):
    """
    Decrement lot.available_qty by *quantity*.

    If select_for_update=True (default), re-fetches the lot under a row lock
    before decrementing (prevents concurrent overselling).

    Raises ValidationError if the deduction would make available_qty negative.
    """
    quantity = Decimal(str(quantity))
    if quantity <= _ZERO:
        raise ValidationError("deplete_lot_balance: quantity must be positive.")

    if select_for_update:
        lot = InventoryLotBalance.objects.select_for_update().get(pk=lot.pk)

    if lot.available_qty - quantity < _ZERO:
        raise ValidationError(
            f"Lot '{lot.lot_code}' has insufficient stock. "
            f"Available: {lot.available_qty}, requested: {quantity}."
        )

    lot.available_qty -= quantity
    lot.save(update_fields=["available_qty"])
    return lot


def increment_lot_balance(lot, quantity):
    """Increment lot.available_qty by *quantity*."""
    quantity = Decimal(str(quantity))
    if quantity <= _ZERO:
        raise ValidationError("increment_lot_balance: quantity must be positive.")

    lot.available_qty += quantity
    lot.save(update_fields=["available_qty"])
    return lot


# ---------------------------------------------------------------------------
# Lot identity
# ---------------------------------------------------------------------------

def get_or_create_lot(org, branch, org_item, lot_code, *, expiry_date=None, manufacture_date=None):
    """
    Get or create an InventoryLotBalance row for the given identity.

    Returns (lot, created).
    """
    lot, created = InventoryLotBalance.objects.get_or_create(
        organization=org,
        branch=branch,
        org_item=org_item,
        lot_code=lot_code,
        defaults={
            "expiry_date": expiry_date,
            "manufacture_date": manufacture_date,
            "available_qty": _ZERO,
        },
    )
    return lot, created


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_allocations_sum(allocations, expected_qty):
    """
    Ensure the sum of quantities in *allocations* equals *expected_qty*.

    allocations: iterable of dicts with key 'quantity', or (lot, qty) tuples.
    Raises ValidationError on mismatch.
    """
    expected_qty = Decimal(str(expected_qty))
    total = _ZERO
    for item in allocations:
        if isinstance(item, dict):
            total += Decimal(str(item["quantity"]))
        else:
            # (lot, qty) tuple
            total += Decimal(str(item[1]))

    if total != expected_qty:
        raise ValidationError(
            f"Allocation quantities sum to {total} but expected {expected_qty}."
        )


def check_lot_override_permission(request):
    """
    Raises PermissionDenied unless the requesting user has the lot_override
    permission (OWNER only per ROLE_POLICY).
    """
    allowed_roles = ROLE_POLICY.get("lot_tracking", {}).get("lot_override", set())
    role = get_member_role(request)
    if role not in allowed_roles:
        raise PermissionDenied(
            "You do not have permission to override lot tracking conflicts. "
            "Only an OWNER can perform lot overrides."
        )

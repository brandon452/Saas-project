from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import StockLedger, StockOnHand


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

    with transaction.atomic():
        if idempotency_key is not None:
            existing = StockLedger.objects.for_org(org).filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing, False

        try:
            stock_on_hand = (
                StockOnHand.objects.for_org(org)
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
                    StockOnHand.objects.for_org(org)
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

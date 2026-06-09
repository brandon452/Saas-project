"""
Shared query-building logic for reports.

Both paginated views and export views call these functions so filter/sort
semantics are never duplicated.
"""
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.db.models import (
    Case,
    DecimalField,
    Exists,
    ExpressionWrapper,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from branches.models import Branch
from inventory.models import (
    BranchItem,
    InventoryClosePeriod,
    InventoryCloseSnapshot,
    InventoryCostState,
    StockLedger,
    StockOnHand,
)
from inventory.services import get_org_local_today


def _parse_pk(value, model, field_name):
    try:
        return model._meta.pk.to_python(value)
    except (TypeError, ValueError, DjangoValidationError):
        raise ValidationError({field_name: "Enter a valid ID."})


def resolve_period(period_id, org):
    """
    Validate and return an InventoryClosePeriod for snapshot mode.
    Raises ValidationError for missing, open, or closing periods.
    """
    try:
        period = InventoryClosePeriod.objects.get(pk=period_id, organization=org)
    except (InventoryClosePeriod.DoesNotExist, DjangoValidationError, ValueError):
        raise ValidationError({"period_id": "Period not found or does not belong to this organisation."})

    if period.status == InventoryClosePeriod.OPEN:
        raise ValidationError({"detail": "Period has not been closed; no authoritative snapshot exists."})
    if period.status == InventoryClosePeriod.CLOSING:
        raise ValidationError({"detail": "Period is currently closing."})

    return period


def live_queryset(request):
    """Annotated StockOnHand queryset with latest/average cost columns."""
    cost_subquery_base = InventoryCostState.objects.filter(
        organization=request.org,
        branch=OuterRef("branch"),
        item=OuterRef("item"),
    )

    soh_qs = (
        StockOnHand.objects
        .for_org(request.org)
        .filter(quantity__gt=0)
        .select_related("item__master_item", "branch")
        .annotate(
            _latest_unit_cost=Subquery(cost_subquery_base.values("latest_unit_cost")[:1]),
            _average_unit_cost=Subquery(cost_subquery_base.values("average_unit_cost")[:1]),
        )
    )

    branch_id = request.query_params.get("branch")
    if branch_id:
        branch_id = _parse_pk(branch_id, Branch, "branch")
        soh_qs = soh_qs.filter(branch_id=branch_id)

    search = request.query_params.get("search", "").strip()
    if search:
        soh_qs = soh_qs.filter(
            models.Q(item__master_item__name__icontains=search)
            | models.Q(item__master_item__sku__icontains=search)
            | models.Q(item__name__icontains=search)
        )

    soh_qs = soh_qs.annotate(
        _has_latest=Case(
            When(_latest_unit_cost__isnull=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        _sort_val=ExpressionWrapper(
            F("quantity") * Coalesce(F("_latest_unit_cost"), Value(Decimal("0"))),
            output_field=DecimalField(max_digits=30, decimal_places=4),
        ),
    ).order_by("_has_latest", F("_sort_val").desc(), "pk")

    return soh_qs


def snapshot_queryset(request, period):
    """Filtered InventoryCloseSnapshot queryset for a closed period."""
    qs = (
        InventoryCloseSnapshot.objects
        .filter(organization=request.org, period=period, quantity_on_hand__gt=0)
        .select_related("item__master_item", "branch")
    )

    branch_id = request.query_params.get("branch")
    if branch_id:
        branch_id = _parse_pk(branch_id, Branch, "branch")
        qs = qs.filter(branch_id=branch_id)

    search = request.query_params.get("search", "").strip()
    if search:
        qs = qs.filter(
            models.Q(item__master_item__name__icontains=search)
            | models.Q(item__master_item__sku__icontains=search)
            | models.Q(item__name__icontains=search)
        )

    qs = qs.annotate(
        _has_latest=Case(
            When(latest_unit_cost__isnull=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        _sort_val=ExpressionWrapper(
            F("quantity_on_hand") * Coalesce(F("latest_unit_cost"), Value(Decimal("0"))),
            output_field=DecimalField(max_digits=30, decimal_places=4),
        ),
    ).order_by("_has_latest", F("_sort_val").desc(), "pk")

    return qs


Q2 = Decimal("0.01")


def soh_to_row(soh):
    return {
        "item_id": soh.item_id,
        "item_name": soh.item.display_name,
        "item_sku": soh.item.master_item.sku,
        "branch_id": soh.branch_id,
        "branch_name": soh.branch.name,
        "quantity_on_hand": soh.quantity,
        "latest_unit_cost": soh._latest_unit_cost,
        "average_unit_cost": soh._average_unit_cost,
    }


def snapshot_to_row(snap):
    return {
        "item_id": snap.item_id,
        "item_name": snap.item.display_name,
        "item_sku": snap.item.master_item.sku,
        "branch_id": snap.branch_id,
        "branch_name": snap.branch.name,
        "quantity_on_hand": snap.quantity_on_hand,
        "latest_unit_cost": snap.latest_unit_cost,
        "average_unit_cost": snap.average_unit_cost,
    }


def format_row(row):
    """Apply Decimal rounding and compute derived valuation columns."""
    qty = row["quantity_on_hand"]
    latest_cost = row["latest_unit_cost"]
    avg_cost = row["average_unit_cost"]
    latest_val = (qty * latest_cost).quantize(Q2) if latest_cost is not None else None
    avg_val = (qty * avg_cost).quantize(Q2) if avg_cost is not None else None
    return {
        "item_id": row["item_id"],
        "item_name": row["item_name"],
        "item_sku": row["item_sku"],
        "branch_id": row["branch_id"],
        "branch_name": row["branch_name"],
        "quantity_on_hand": qty,
        "latest_unit_cost": latest_cost.quantize(Q2) if latest_cost is not None else None,
        "latest_valuation": latest_val,
        "average_unit_cost": avg_cost.quantize(Q2) if avg_cost is not None else None,
        "average_valuation": avg_val,
    }


# ---------------------------------------------------------------------------
# Inventory Aging
# ---------------------------------------------------------------------------

SLOW_THRESHOLD_DAYS = 90
DEAD_THRESHOLD_DAYS = 180


def _get_org_tz(org):
    tz_name = getattr(org, "default_timezone", None) or "UTC"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def aging_queryset(request):
    """
    Annotated StockOnHand queryset for the Inventory Aging report.

    Filters to active BranchItems with quantity > 0.
    Annotates _last_receipt_at, _latest_unit_cost, _average_unit_cost from
    InventoryCostState via Subquery (same pattern as live_queryset).
    Sorts oldest receipt first (nulls last), then item name, branch name.
    """
    org = request.org

    active_branch_item = BranchItem.objects.filter(
        org_item=OuterRef("item"),
        branch=OuterRef("branch"),
        is_active=True,
    )

    cost_state_base = InventoryCostState.objects.filter(
        organization=org,
        branch=OuterRef("branch"),
        item=OuterRef("item"),
    )

    soh_qs = (
        StockOnHand.objects.for_org(org)
        .filter(quantity__gt=0)
        .filter(Exists(active_branch_item))
        .select_related("item__master_item", "branch")
        .annotate(
            _last_receipt_at=Subquery(cost_state_base.values("last_receipt_at")[:1]),
            _latest_unit_cost=Subquery(cost_state_base.values("latest_unit_cost")[:1]),
            _average_unit_cost=Subquery(cost_state_base.values("average_unit_cost")[:1]),
        )
    )

    branch_id = request.query_params.get("branch")
    if branch_id:
        branch_id = _parse_pk(branch_id, Branch, "branch")
        soh_qs = soh_qs.filter(branch_id=branch_id)

    search = request.query_params.get("search", "").strip()
    if search:
        soh_qs = soh_qs.filter(
            models.Q(item__master_item__name__icontains=search)
            | models.Q(item__master_item__sku__icontains=search)
            | models.Q(item__name__icontains=search)
        )

    soh_qs = soh_qs.order_by(
        F("_last_receipt_at").asc(nulls_last=True),
        "item__master_item__name",
        "branch__name",
        "pk",
    )

    return soh_qs


def aging_to_row(soh, today_local, org_tz):
    """
    Convert an annotated StockOnHand row to a dict for the Inventory Aging report.
    today_local (date) and org_tz (ZoneInfo) must be pre-computed by the caller.
    """
    ts = soh._last_receipt_at
    age_days = (today_local - ts.astimezone(org_tz).date()).days if ts else None

    qty = soh.quantity
    latest_cost = soh._latest_unit_cost
    avg_cost = soh._average_unit_cost

    return {
        "item_id": soh.item_id,
        "item_name": soh.item.display_name,
        "item_sku": soh.item.master_item.sku,
        "branch_id": soh.branch_id,
        "branch_name": soh.branch.name,
        "quantity_on_hand": qty,
        "last_receipt_at": ts,
        "age_days": age_days,
        "latest_unit_cost": latest_cost.quantize(Q2) if latest_cost is not None else None,
        "latest_valuation": (qty * latest_cost).quantize(Q2) if latest_cost is not None else None,
        "average_unit_cost": avg_cost.quantize(Q2) if avg_cost is not None else None,
        "average_valuation": (qty * avg_cost).quantize(Q2) if avg_cost is not None else None,
    }


# ---------------------------------------------------------------------------
# Slow / Dead Stock
# ---------------------------------------------------------------------------

def slow_dead_queryset(request):
    """
    Annotated StockOnHand queryset for the Slow/Dead Stock report.

    Annotates three timestamp sources (_last_outbound_at, _last_receipt_at,
    _branch_item_created_at) and a Coalesce _effective_ts used for DB-side
    filtering and sorting.

    Thresholds are computed in org-local time so boundary dates match what
    the Python-side slow_dead_to_row formatter will compute.
    """
    org = request.org
    today_local = get_org_local_today(org)
    org_tz = _get_org_tz(org)

    active_branch_item = BranchItem.objects.filter(
        org_item=OuterRef("item"),
        branch=OuterRef("branch"),
        is_active=True,
    )

    cost_state_base = InventoryCostState.objects.filter(
        organization=org,
        branch=OuterRef("branch"),
        item=OuterRef("item"),
    )

    last_issue_base = (
        StockLedger.objects.filter(
            organization=org,
            branch=OuterRef("branch"),
            item=OuterRef("item"),
            movement_type=StockLedger.MOVEMENT_ISSUE,
        )
        .order_by("-occurred_at")
    )

    branch_item_base = BranchItem.objects.filter(
        org_item=OuterRef("item"),
        branch=OuterRef("branch"),
    )

    soh_qs = (
        StockOnHand.objects.for_org(org)
        .filter(quantity__gt=0)
        .filter(Exists(active_branch_item))
        .select_related("item__master_item", "branch")
        .annotate(
            _last_outbound_at=Subquery(last_issue_base.values("occurred_at")[:1]),
            _last_receipt_at=Subquery(cost_state_base.values("last_receipt_at")[:1]),
            _branch_item_created_at=Subquery(branch_item_base.values("created_at")[:1]),
            _latest_unit_cost=Subquery(cost_state_base.values("latest_unit_cost")[:1]),
        )
        .annotate(
            _effective_ts=Coalesce(
                "_last_outbound_at", "_last_receipt_at", "_branch_item_created_at"
            )
        )
    )

    # Mandatory prefilter: rows with no timestamp source at all get inactive_days=0
    # in the formatter and would never pass classification, but exclude them here
    # so they never pollute pagination counts.
    soh_qs = soh_qs.filter(
        Q(_last_outbound_at__isnull=False)
        | Q(_last_receipt_at__isnull=False)
        | Q(_branch_item_created_at__isnull=False)
    )

    # Convert threshold day counts to UTC-aware datetime boundaries.
    # effective_ts < start_of(today - (N-1) days in org_tz) ↔ inactive_days >= N.
    dead_cutoff = timezone.make_aware(
        datetime.combine(today_local - timedelta(days=DEAD_THRESHOLD_DAYS - 1), time.min),
        org_tz,
    )
    slow_cutoff = timezone.make_aware(
        datetime.combine(today_local - timedelta(days=SLOW_THRESHOLD_DAYS - 1), time.min),
        org_tz,
    )

    status = request.query_params.get("status", "all")
    if status == "all":
        soh_qs = soh_qs.filter(_effective_ts__lt=slow_cutoff)
    elif status == "slow":
        soh_qs = soh_qs.filter(_effective_ts__gte=dead_cutoff, _effective_ts__lt=slow_cutoff)
    elif status == "dead":
        soh_qs = soh_qs.filter(_effective_ts__lt=dead_cutoff)
    else:
        raise ValidationError({"status": "Must be one of: slow, dead, all."})

    branch_id = request.query_params.get("branch")
    if branch_id:
        branch_id = _parse_pk(branch_id, Branch, "branch")
        soh_qs = soh_qs.filter(branch_id=branch_id)

    search = request.query_params.get("search", "").strip()
    if search:
        soh_qs = soh_qs.filter(
            models.Q(item__master_item__name__icontains=search)
            | models.Q(item__master_item__sku__icontains=search)
            | models.Q(item__name__icontains=search)
        )

    # Sort oldest effective_ts first (= highest inactive_days first), then deterministic.
    soh_qs = soh_qs.order_by("_effective_ts", "item__master_item__name", "branch__name", "pk")

    return soh_qs


def slow_dead_to_row(soh, today_local, org_tz):
    """
    Convert an annotated StockOnHand row to a dict for the Slow/Dead Stock report.
    today_local (date) and org_tz (ZoneInfo) must be pre-computed by the caller.
    """
    ts = soh._last_outbound_at or soh._last_receipt_at or soh._branch_item_created_at
    # ts=None cannot reach here: slow_dead_queryset enforces a non-null timestamp
    # prefilter. inactive_days=0 is a safe sentinel — the SLOW/DEAD classification
    # check would exclude such rows anyway, but they never enter pagination.
    inactive_days = (today_local - ts.astimezone(org_tz).date()).days if ts else 0

    status = "DEAD" if inactive_days >= DEAD_THRESHOLD_DAYS else "SLOW"

    qty = soh.quantity
    latest_cost = soh._latest_unit_cost

    return {
        "item_id": soh.item_id,
        "item_name": soh.item.display_name,
        "item_sku": soh.item.master_item.sku,
        "branch_id": soh.branch_id,
        "branch_name": soh.branch.name,
        "quantity_on_hand": qty,
        "last_outbound_at": soh._last_outbound_at,
        "inactive_days": inactive_days,
        "status": status,
        "latest_unit_cost": latest_cost.quantize(Q2) if latest_cost is not None else None,
        "latest_valuation": (qty * latest_cost).quantize(Q2) if latest_cost is not None else None,
    }

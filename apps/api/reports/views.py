from datetime import date, datetime, time, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.db.models import Case, Count, DecimalField, ExpressionWrapper, F, IntegerField, OuterRef, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from django_ratelimit.core import is_ratelimited
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from branches.models import Branch
from exports.audit import log_export_event
from exports.config import get_csv_rate
from exports.filenames import csv_filename
from exports.rows.inventory_aging import AGING_HEADERS, to_aging_csv_row
from exports.rows.slow_dead_stock import SLOW_DEAD_HEADERS, to_slow_dead_csv_row
from exports.rows.stock_valuation import HEADERS, to_row as valuation_to_csv_row
from exports.streaming import enforce_row_cap, stream_csv
from goods_receipts.models import GoodsReceiptLine
from inventory.models import (
    InventoryClosePeriod,
    InventoryCloseSnapshot,
    InventoryCostState,
    OrgItem,
    StockOnHand,
)
from inventory.services import get_org_local_today
from suppliers.models import Supplier
from tenancy.models import Organization
from tenancy.permissions import IsOrgOwnerOrAdmin, IsParentMember, get_parent_membership

from .queries import (
    DEAD_THRESHOLD_DAYS,
    SLOW_THRESHOLD_DAYS,
    _get_org_tz,
    aging_queryset,
    aging_to_row,
    format_row,
    live_queryset,
    resolve_period,
    slow_dead_queryset,
    slow_dead_to_row,
    snapshot_queryset,
    snapshot_to_row,
    soh_to_row,
)
from .serializers import (
    CostTrendPointSerializer,
    InventoryAgingRowSerializer,
    InventoryAgingSummarySerializer,
    SlowDeadStockRowSerializer,
    SlowDeadStockSummarySerializer,
    StockValuationRowSerializer,
    StockValuationSummarySerializer,
)


class StockValuationPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class StockValuationView(APIView):
    Q2 = Decimal("0.01")
    pagination_class = StockValuationPagination

    @property
    def paginator(self):
        if not hasattr(self, "_paginator"):
            self._paginator = self.pagination_class()
        return self._paginator

    def get_permissions(self):
        if get_parent_membership(self.request):
            return [IsAuthenticated(), IsParentMember()]
        return [IsAuthenticated(), IsOrgOwnerOrAdmin()]

    def initial(self, request, *args, **kwargs):
        org_id = self.kwargs.get("org_id")
        try:
            request.org = Organization.objects.get(pk=org_id, is_active=True)
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")

        parent_membership = get_parent_membership(request)
        request.parent_role = parent_membership.role if parent_membership else None
        super().initial(request, *args, **kwargs)

    def _empty_response(self):
        return Response({
            "summary": StockValuationSummarySerializer({
                "total_latest_valuation": None,
                "total_average_valuation": None,
                "item_count": 0,
                "branch_count": 0,
            }).data,
            "count": 0,
            "next": None,
            "previous": None,
            "results": [],
        })

    def _live_summary(self, qs):
        result = qs.aggregate(
            total_latest=Sum(
                ExpressionWrapper(
                    F("quantity") * F("_latest_unit_cost"),
                    output_field=DecimalField(max_digits=30, decimal_places=4),
                )
            ),
            total_average=Sum(
                ExpressionWrapper(
                    F("quantity") * F("_average_unit_cost"),
                    output_field=DecimalField(max_digits=30, decimal_places=4),
                )
            ),
            item_count=Count("item_id", distinct=True),
            branch_count=Count("branch_id", distinct=True),
        )
        return {
            "total_latest_valuation": result["total_latest"].quantize(self.Q2) if result["total_latest"] else None,
            "total_average_valuation": result["total_average"].quantize(self.Q2) if result["total_average"] else None,
            "item_count": result["item_count"],
            "branch_count": result["branch_count"],
        }

    def _snapshot_summary(self, qs):
        result = qs.aggregate(
            total_latest=Sum(
                ExpressionWrapper(
                    F("quantity_on_hand") * F("latest_unit_cost"),
                    output_field=DecimalField(max_digits=30, decimal_places=4),
                )
            ),
            total_average=Sum(
                ExpressionWrapper(
                    F("quantity_on_hand") * F("average_unit_cost"),
                    output_field=DecimalField(max_digits=30, decimal_places=4),
                )
            ),
            item_count=Count("item_id", distinct=True),
            branch_count=Count("branch_id", distinct=True),
        )
        return {
            "total_latest_valuation": result["total_latest"].quantize(self.Q2) if result["total_latest"] else None,
            "total_average_valuation": result["total_average"].quantize(self.Q2) if result["total_average"] else None,
            "item_count": result["item_count"],
            "branch_count": result["branch_count"],
        }

    def _paginate_and_respond(self, request, queryset, row_fn, summary_fn):
        summary = summary_fn(queryset)
        if summary["item_count"] == 0:
            return self._empty_response()

        page = self.paginator.paginate_queryset(queryset, request, view=self)
        formatted = [format_row(row_fn(obj)) for obj in page]
        serialized = StockValuationRowSerializer(formatted, many=True).data

        paginated = self.paginator.get_paginated_response(serialized)
        paginated.data["summary"] = StockValuationSummarySerializer(summary).data
        return paginated

    def get(self, request, org_id=None, *args, **kwargs):
        period_id = request.query_params.get("period_id")
        if period_id:
            period = resolve_period(period_id, request.org)
            return self._paginate_and_respond(
                request,
                snapshot_queryset(request, period),
                snapshot_to_row,
                self._snapshot_summary,
            )

        return self._paginate_and_respond(
            request,
            live_queryset(request),
            soh_to_row,
            self._live_summary,
        )


class StockValuationExportView(APIView):

    def get_permissions(self):
        if get_parent_membership(self.request):
            return [IsAuthenticated(), IsParentMember()]
        return [IsAuthenticated(), IsOrgOwnerOrAdmin()]

    def initial(self, request, *args, **kwargs):
        org_id = self.kwargs.get("org_id")
        try:
            request.org = Organization.objects.get(pk=org_id, is_active=True)
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")

        parent_membership = get_parent_membership(request)
        request.parent_role = parent_membership.role if parent_membership else None
        super().initial(request, *args, **kwargs)

    def get(self, request, org_id=None, *args, **kwargs):
        if is_ratelimited(request, group="valuation_export_csv", key="user", rate=get_csv_rate(), method="GET", increment=True):
            return Response(
                {"detail": "Too many export requests. Please wait before exporting again."},
                status=429,
            )

        period_id = request.query_params.get("period_id")
        if period_id:
            period = resolve_period(period_id, request.org)
            qs = snapshot_queryset(request, period)
            row_fn = snapshot_to_row
        else:
            qs = live_queryset(request)
            row_fn = soh_to_row

        row_count = enforce_row_cap(qs)

        log_export_event(
            organization=request.org,
            actor_user=request.user,
            resource="stock_valuation",
            format="csv",
            filters=dict(request.query_params),
            row_count=row_count,
        )

        def _iter_rows():
            for obj in qs.iterator(chunk_size=500):
                yield valuation_to_csv_row(format_row(row_fn(obj)))

        return stream_csv(HEADERS, _iter_rows(), csv_filename("stock-valuation"))


class PurchaseCostTrendView(APIView):
    MAX_POINTS = 500

    def get_permissions(self):
        if get_parent_membership(self.request):
            return [IsAuthenticated(), IsParentMember()]
        return [IsAuthenticated(), IsOrgOwnerOrAdmin()]

    def initial(self, request, *args, **kwargs):
        org_id = self.kwargs.get("org_id")
        try:
            request.org = Organization.objects.get(pk=org_id, is_active=True)
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")

        parent_membership = get_parent_membership(request)
        request.parent_role = parent_membership.role if parent_membership else None
        super().initial(request, *args, **kwargs)

    def _parse_date(self, value):
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValidationError({"detail": "Invalid date format. Use YYYY-MM-DD."})

    def _parse_pk(self, value, model, field_name):
        try:
            return model._meta.pk.to_python(value)
        except (TypeError, ValueError, DjangoValidationError):
            raise ValidationError({field_name: "Enter a valid ID."})

    def get(self, request, org_id=None, *args, **kwargs):
        item_id = request.query_params.get("item")
        if not item_id:
            raise ValidationError({"item": "This field is required."})

        try:
            item = OrgItem.objects.get(pk=item_id, organization=request.org)
        except (OrgItem.DoesNotExist, DjangoValidationError, ValueError):
            raise ValidationError(
                {"item": "Item not found or does not belong to this organisation."}
            )

        today = timezone.now().date()
        from_date = today - timedelta(days=365)
        to_date = today

        from_date_param = request.query_params.get("from_date")
        if from_date_param:
            from_date = self._parse_date(from_date_param)

        to_date_param = request.query_params.get("to_date")
        if to_date_param:
            to_date = self._parse_date(to_date_param)

        if from_date > to_date:
            raise ValidationError({"detail": "from_date must not be after to_date."})

        from_dt = timezone.make_aware(datetime.combine(from_date, time.min))
        to_dt = timezone.make_aware(datetime.combine(to_date, time.max))

        qs = (
            GoodsReceiptLine.objects.filter(
                receipt__organization=request.org,
                receipt__received_at__gte=from_dt,
                receipt__received_at__lte=to_dt,
                unit_cost__isnull=False,
            )
            .filter(models.Q(po_line__item=item) | models.Q(item=item))
            .select_related(
                "receipt__branch",
                "receipt__supplier",
                "receipt__purchase_order__supplier",
            )
            .order_by("receipt__received_at", "receipt_id", "id")
        )

        supplier_id = request.query_params.get("supplier")
        if supplier_id:
            supplier_id = self._parse_pk(supplier_id, Supplier, "supplier")
            qs = qs.filter(
                models.Q(receipt__supplier_id=supplier_id)
                | models.Q(receipt__purchase_order__supplier_id=supplier_id)
            )

        branch_id = request.query_params.get("branch")
        if branch_id:
            branch_id = self._parse_pk(branch_id, Branch, "branch")
            qs = qs.filter(receipt__branch_id=branch_id)

        total_count = qs.count()
        if total_count == 0:
            return Response({
                "results": [],
                "truncated": False,
                "total_count": 0,
                "limit": self.MAX_POINTS,
            })

        truncated = total_count > self.MAX_POINTS
        if truncated:
            qs = qs[: self.MAX_POINTS]

        results = []
        for line in qs:
            receipt = line.receipt

            if receipt.supplier_id:
                supplier_id_val = receipt.supplier_id
                supplier_name = receipt.supplier.name if receipt.supplier else None
            elif receipt.purchase_order_id and receipt.purchase_order.supplier_id:
                supplier_id_val = receipt.purchase_order.supplier_id
                supplier_name = receipt.purchase_order.supplier.name
            else:
                supplier_id_val = None
                supplier_name = None

            results.append(
                {
                    "date": receipt.received_at,
                    "unit_cost": line.unit_cost,
                    "quantity_received": line.quantity_received,
                    "supplier_id": supplier_id_val,
                    "supplier_name": supplier_name,
                    "branch_id": receipt.branch_id,
                    "branch_name": receipt.branch.name,
                    "receipt_id": receipt.id,
                    "receipt_type": receipt.receipt_type,
                }
            )

        serializer = CostTrendPointSerializer(results, many=True)
        return Response({
            "results": serializer.data,
            "truncated": truncated,
            "total_count": total_count,
            "limit": self.MAX_POINTS,
        })


# ---------------------------------------------------------------------------
# Shared mixin for org resolution + permissions (DRY for new report views)
# ---------------------------------------------------------------------------

class _OrgReportMixin:
    """Mixin that handles org resolution and owner/admin permission check."""

    def get_permissions(self):
        if get_parent_membership(self.request):
            return [IsAuthenticated(), IsParentMember()]
        return [IsAuthenticated(), IsOrgOwnerOrAdmin()]

    def initial(self, request, *args, **kwargs):
        org_id = self.kwargs.get("org_id")
        try:
            request.org = Organization.objects.get(pk=org_id, is_active=True)
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")
        parent_membership = get_parent_membership(request)
        request.parent_role = parent_membership.role if parent_membership else None
        super().initial(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Inventory Aging
# ---------------------------------------------------------------------------

class InventoryAgingPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class InventoryAgingView(_OrgReportMixin, APIView):
    Q2 = Decimal("0.01")
    pagination_class = InventoryAgingPagination

    @property
    def paginator(self):
        if not hasattr(self, "_paginator"):
            self._paginator = self.pagination_class()
        return self._paginator

    def _summary(self, qs, today_local, org_tz):
        from django.db.models import Min

        result = qs.aggregate(
            total_latest=Sum(
                ExpressionWrapper(
                    F("quantity") * F("_latest_unit_cost"),
                    output_field=DecimalField(max_digits=30, decimal_places=4),
                )
            ),
            total_average=Sum(
                ExpressionWrapper(
                    F("quantity") * F("_average_unit_cost"),
                    output_field=DecimalField(max_digits=30, decimal_places=4),
                )
            ),
            item_count=Count("item_id", distinct=True),
            branch_count=Count("branch_id", distinct=True),
            oldest_receipt=Min("_last_receipt_at"),
        )
        oldest_ts = result["oldest_receipt"]
        oldest_age_days = (
            (today_local - oldest_ts.astimezone(org_tz).date()).days
            if oldest_ts else None
        )
        return {
            "total_latest_valuation": result["total_latest"].quantize(self.Q2) if result["total_latest"] else None,
            "total_average_valuation": result["total_average"].quantize(self.Q2) if result["total_average"] else None,
            "item_count": result["item_count"],
            "branch_count": result["branch_count"],
            "oldest_age_days": oldest_age_days,
        }

    def get(self, request, org_id=None, *args, **kwargs):
        today_local = get_org_local_today(request.org)
        org_tz = _get_org_tz(request.org)
        qs = aging_queryset(request)

        summary = self._summary(qs, today_local, org_tz)
        if summary["item_count"] == 0:
            return Response({
                "summary": InventoryAgingSummarySerializer({
                    "total_latest_valuation": None,
                    "total_average_valuation": None,
                    "item_count": 0,
                    "branch_count": 0,
                    "oldest_age_days": None,
                }).data,
                "count": 0,
                "next": None,
                "previous": None,
                "results": [],
            })

        page = self.paginator.paginate_queryset(qs, request, view=self)
        rows = [aging_to_row(obj, today_local, org_tz) for obj in page]
        serialized = InventoryAgingRowSerializer(rows, many=True).data

        paginated = self.paginator.get_paginated_response(serialized)
        paginated.data["summary"] = InventoryAgingSummarySerializer(summary).data
        return paginated


class InventoryAgingExportView(_OrgReportMixin, APIView):

    def get(self, request, org_id=None, *args, **kwargs):
        if is_ratelimited(request, group="aging_export_csv", key="user", rate=get_csv_rate(), method="GET", increment=True):
            return Response(
                {"detail": "Too many export requests. Please wait before exporting again."},
                status=429,
            )

        today_local = get_org_local_today(request.org)
        org_tz = _get_org_tz(request.org)
        qs = aging_queryset(request)
        row_count = enforce_row_cap(qs)

        log_export_event(
            organization=request.org,
            actor_user=request.user,
            resource="inventory_aging",
            format="csv",
            filters=dict(request.query_params),
            row_count=row_count,
        )

        def _iter_rows():
            for obj in qs.iterator(chunk_size=500):
                yield to_aging_csv_row(aging_to_row(obj, today_local, org_tz))

        return stream_csv(AGING_HEADERS, _iter_rows(), csv_filename("inventory-aging"))


# ---------------------------------------------------------------------------
# Slow / Dead Stock
# ---------------------------------------------------------------------------

class SlowDeadStockPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class SlowDeadStockView(_OrgReportMixin, APIView):
    Q2 = Decimal("0.01")
    pagination_class = SlowDeadStockPagination

    @property
    def paginator(self):
        if not hasattr(self, "_paginator"):
            self._paginator = self.pagination_class()
        return self._paginator

    def _summary(self, qs, today_local, org_tz):
        dead_cutoff = timezone.make_aware(
            datetime.combine(today_local - timedelta(days=DEAD_THRESHOLD_DAYS - 1), time.min),
            org_tz,
        )
        slow_cutoff = timezone.make_aware(
            datetime.combine(today_local - timedelta(days=SLOW_THRESHOLD_DAYS - 1), time.min),
            org_tz,
        )

        result = qs.aggregate(
            slow_count=Count(
                Case(
                    When(_effective_ts__gte=dead_cutoff, _effective_ts__lt=slow_cutoff, then=Value(1)),
                    output_field=IntegerField(),
                )
            ),
            dead_count=Count(
                Case(
                    When(_effective_ts__lt=dead_cutoff, then=Value(1)),
                    output_field=IntegerField(),
                )
            ),
            total_slow_val=Sum(
                Case(
                    When(
                        _effective_ts__gte=dead_cutoff,
                        _effective_ts__lt=slow_cutoff,
                        then=ExpressionWrapper(
                            F("quantity") * F("_latest_unit_cost"),
                            output_field=DecimalField(max_digits=30, decimal_places=4),
                        ),
                    ),
                    output_field=DecimalField(max_digits=30, decimal_places=4),
                )
            ),
            total_dead_val=Sum(
                Case(
                    When(
                        _effective_ts__lt=dead_cutoff,
                        then=ExpressionWrapper(
                            F("quantity") * F("_latest_unit_cost"),
                            output_field=DecimalField(max_digits=30, decimal_places=4),
                        ),
                    ),
                    output_field=DecimalField(max_digits=30, decimal_places=4),
                )
            ),
        )
        return {
            "slow_count": result["slow_count"] or 0,
            "dead_count": result["dead_count"] or 0,
            "total_slow_valuation": result["total_slow_val"].quantize(self.Q2) if result["total_slow_val"] else None,
            "total_dead_valuation": result["total_dead_val"].quantize(self.Q2) if result["total_dead_val"] else None,
        }

    def get(self, request, org_id=None, *args, **kwargs):
        today_local = get_org_local_today(request.org)
        org_tz = _get_org_tz(request.org)
        qs = slow_dead_queryset(request)

        total = qs.count()
        if total == 0:
            return Response({
                "summary": SlowDeadStockSummarySerializer({
                    "slow_count": 0,
                    "dead_count": 0,
                    "total_slow_valuation": None,
                    "total_dead_valuation": None,
                }).data,
                "count": 0,
                "next": None,
                "previous": None,
                "results": [],
            })

        summary = self._summary(qs, today_local, org_tz)
        page = self.paginator.paginate_queryset(qs, request, view=self)
        rows = [slow_dead_to_row(obj, today_local, org_tz) for obj in page]
        serialized = SlowDeadStockRowSerializer(rows, many=True).data

        paginated = self.paginator.get_paginated_response(serialized)
        paginated.data["summary"] = SlowDeadStockSummarySerializer(summary).data
        return paginated


class SlowDeadStockExportView(_OrgReportMixin, APIView):

    def get(self, request, org_id=None, *args, **kwargs):
        if is_ratelimited(request, group="slow_dead_export_csv", key="user", rate=get_csv_rate(), method="GET", increment=True):
            return Response(
                {"detail": "Too many export requests. Please wait before exporting again."},
                status=429,
            )

        today_local = get_org_local_today(request.org)
        org_tz = _get_org_tz(request.org)
        qs = slow_dead_queryset(request)
        row_count = enforce_row_cap(qs)

        log_export_event(
            organization=request.org,
            actor_user=request.user,
            resource="slow_dead_stock",
            format="csv",
            filters=dict(request.query_params),
            row_count=row_count,
        )

        def _iter_rows():
            for obj in qs.iterator(chunk_size=500):
                yield to_slow_dead_csv_row(slow_dead_to_row(obj, today_local, org_tz))

        return stream_csv(SLOW_DEAD_HEADERS, _iter_rows(), csv_filename("slow-dead-stock"))

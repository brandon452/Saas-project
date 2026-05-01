from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.db.models import Case, Count, DecimalField, ExpressionWrapper, F, IntegerField, OuterRef, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from goods_receipts.models import GoodsReceiptLine
from inventory.models import (
    InventoryClosePeriod,
    InventoryCloseSnapshot,
    InventoryCostState,
    OrgItem,
    StockOnHand,
)
from tenancy.models import Organization
from tenancy.permissions import IsOrgOwnerOrAdmin, IsParentMember, get_parent_membership

from .serializers import CostTrendPointSerializer, StockValuationRowSerializer, StockValuationSummarySerializer


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

    def _format_row(self, row):
        qty = row["quantity_on_hand"]
        latest_cost = row["latest_unit_cost"]
        avg_cost = row["average_unit_cost"]
        latest_val = (qty * latest_cost).quantize(self.Q2) if latest_cost is not None else None
        avg_val = (qty * avg_cost).quantize(self.Q2) if avg_cost is not None else None
        return {
            "item_id": row["item_id"],
            "item_name": row["item_name"],
            "item_sku": row["item_sku"],
            "branch_id": row["branch_id"],
            "branch_name": row["branch_name"],
            "quantity_on_hand": qty,
            "latest_unit_cost": latest_cost.quantize(self.Q2) if latest_cost is not None else None,
            "latest_valuation": latest_val,
            "average_unit_cost": avg_cost.quantize(self.Q2) if avg_cost is not None else None,
            "average_valuation": avg_val,
        }

    def _live_queryset(self, request):
        """Return an annotated StockOnHand queryset with cost data."""
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
                _latest_unit_cost=Subquery(
                    cost_subquery_base.values("latest_unit_cost")[:1]
                ),
                _average_unit_cost=Subquery(
                    cost_subquery_base.values("average_unit_cost")[:1]
                ),
            )
        )

        branch_id = request.query_params.get("branch")
        if branch_id:
            soh_qs = soh_qs.filter(branch_id=branch_id)

        search = request.query_params.get("search", "").strip()
        if search:
            soh_qs = soh_qs.filter(
                models.Q(item__master_item__name__icontains=search)
                | models.Q(item__master_item__sku__icontains=search)
                | models.Q(item__name__icontains=search)
            )

        # Sort at DB level using the previous report semantics:
        # rows with a latest valuation first, then highest latest valuation.
        soh_qs = soh_qs.annotate(
            _has_latest=Case(
                When(_latest_unit_cost__isnull=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            _sort_val=ExpressionWrapper(
                F("quantity") * Coalesce(F("_latest_unit_cost"), Value(Decimal("0"))),
                output_field=DecimalField(max_digits=30, decimal_places=4),
            )
        ).order_by(
            "_has_latest",
            F("_sort_val").desc(),
        )

        return soh_qs

    def _soh_to_row(self, soh):
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

    def _snapshot_queryset(self, request, period):
        qs = (
            InventoryCloseSnapshot.objects
            .filter(organization=request.org, period=period, quantity_on_hand__gt=0)
            .select_related("item__master_item", "branch")
        )

        branch_id = request.query_params.get("branch")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                models.Q(item__master_item__name__icontains=search)
                | models.Q(item__master_item__sku__icontains=search)
                | models.Q(item__name__icontains=search)
            )

        # Sort at DB level using the previous report semantics:
        # rows with a latest valuation first, then highest latest valuation.
        qs = qs.annotate(
            _has_latest=Case(
                When(latest_unit_cost__isnull=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            _sort_val=ExpressionWrapper(
                F("quantity_on_hand") * Coalesce(F("latest_unit_cost"), Value(Decimal("0"))),
                output_field=DecimalField(max_digits=30, decimal_places=4),
            )
        ).order_by(
            "_has_latest",
            F("_sort_val").desc(),
        )

        return qs

    def _snapshot_to_row(self, snap):
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

    def _paginate_and_respond(self, request, queryset, row_fn, summary_fn):
        summary = summary_fn(queryset)
        if summary["item_count"] == 0:
            return self._empty_response()

        page = self.paginator.paginate_queryset(queryset, request, view=self)
        formatted = [self._format_row(row_fn(obj)) for obj in page]
        serialized = StockValuationRowSerializer(formatted, many=True).data

        paginated = self.paginator.get_paginated_response(serialized)
        paginated.data["summary"] = StockValuationSummarySerializer(summary).data
        return paginated

    def get(self, request, org_id=None, *args, **kwargs):
        period_id = request.query_params.get("period_id")
        if period_id:
            try:
                period = InventoryClosePeriod.objects.get(
                    pk=period_id,
                    organization=request.org,
                )
            except (InventoryClosePeriod.DoesNotExist, DjangoValidationError, ValueError):
                raise ValidationError({"period_id": "Period not found or does not belong to this organisation."})

            if period.status == InventoryClosePeriod.OPEN:
                raise ValidationError({"detail": "Period has not been closed; no authoritative snapshot exists."})
            if period.status == InventoryClosePeriod.CLOSING:
                raise ValidationError({"detail": "Period is currently closing."})

            return self._paginate_and_respond(
                request,
                self._snapshot_queryset(request, period),
                self._snapshot_to_row,
                self._snapshot_summary,
            )

        return self._paginate_and_respond(
            request,
            self._live_queryset(request),
            self._soh_to_row,
            self._live_summary,
        )


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
            qs = qs.filter(
                models.Q(receipt__supplier_id=supplier_id)
                | models.Q(receipt__purchase_order__supplier_id=supplier_id)
            )

        branch_id = request.query_params.get("branch")
        if branch_id:
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

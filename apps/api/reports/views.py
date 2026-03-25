from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from goods_receipts.models import GoodsReceiptLine
from inventory.models import OrgItem, StockOnHand
from tenancy.models import Organization
from tenancy.permissions import IsOrgOwnerOrAdmin, IsParentMember, get_parent_membership

from .serializers import CostTrendPointSerializer, StockValuationRowSerializer, StockValuationSummarySerializer


class StockValuationView(APIView):
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
        soh_qs = (
            StockOnHand.objects
            .for_org(request.org)
            .filter(quantity__gt=0)
            .select_related("item__master_item", "branch")
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

        soh_list = list(soh_qs)
        relevant_item_ids = {soh.item_id for soh in soh_list}
        relevant_branch_ids = {soh.branch_id for soh in soh_list}

        if not soh_list:
            return Response({
                "summary": StockValuationSummarySerializer({
                    "total_latest_valuation": None,
                    "total_average_valuation": None,
                    "item_count": 0,
                    "branch_count": 0,
                }).data,
                "results": [],
            })

        receipt_lines = (
            GoodsReceiptLine.objects
            .filter(
                receipt__organization=request.org,
                unit_cost__isnull=False,
                receipt__branch_id__in=relevant_branch_ids,
            )
            .filter(
                models.Q(po_line__item_id__in=relevant_item_ids)
                | models.Q(item_id__in=relevant_item_ids)
            )
            .values(
                "receipt__branch_id",
                "po_line__item_id",
                "item_id",
                "quantity_received",
                "unit_cost",
                "receipt__received_at",
            )
        )

        avco_numerator = defaultdict(Decimal)
        avco_denominator = defaultdict(Decimal)
        latest_cost_map = {}

        for line in receipt_lines:
            item_id = line["po_line__item_id"] or line["item_id"]
            b_id = line["receipt__branch_id"]
            key = (str(item_id), str(b_id))
            qty = Decimal(str(line["quantity_received"]))
            cost = Decimal(str(line["unit_cost"]))
            received_at = line["receipt__received_at"]

            avco_numerator[key] += qty * cost
            avco_denominator[key] += qty

            if key not in latest_cost_map or received_at > latest_cost_map[key][0]:
                latest_cost_map[key] = (received_at, cost)

        avco_map = {
            key: (avco_numerator[key] / avco_denominator[key]).quantize(Decimal("0.01"))
            for key in avco_numerator
            if avco_denominator[key] > 0
        }

        latest_map = {key: val[1] for key, val in latest_cost_map.items()}

        results = []
        total_latest = Decimal("0")
        total_average = Decimal("0")
        has_latest = False
        has_average = False
        item_ids = set()
        branch_ids = set()

        for soh in soh_list:
            key = (str(soh.item_id), str(soh.branch_id))
            qty = soh.quantity

            latest_cost = latest_map.get(key)
            avg_cost = avco_map.get(key)

            latest_val = (qty * latest_cost).quantize(Decimal("0.01")) if latest_cost is not None else None
            avg_val = (qty * avg_cost).quantize(Decimal("0.01")) if avg_cost is not None else None

            if latest_val is not None:
                total_latest += latest_val
                has_latest = True
            if avg_val is not None:
                total_average += avg_val
                has_average = True

            item_ids.add(soh.item_id)
            branch_ids.add(soh.branch_id)

            results.append({
                "item_id": soh.item_id,
                "item_name": soh.item.display_name,
                "item_sku": soh.item.master_item.sku,
                "branch_id": soh.branch_id,
                "branch_name": soh.branch.name,
                "quantity_on_hand": qty,
                "latest_unit_cost": latest_cost,
                "latest_valuation": latest_val,
                "average_unit_cost": avg_cost,
                "average_valuation": avg_val,
            })

        results.sort(
            key=lambda r: (
                r["latest_valuation"] is None,
                -(r["latest_valuation"] or Decimal("0")),
            )
        )

        summary = {
            "total_latest_valuation": total_latest if has_latest else None,
            "total_average_valuation": total_average if has_average else None,
            "item_count": len(item_ids),
            "branch_count": len(branch_ids),
        }

        return Response({
            "summary": StockValuationSummarySerializer(summary).data,
            "results": StockValuationRowSerializer(results, many=True).data,
        })


class PurchaseCostTrendView(APIView):
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
            .order_by("receipt__received_at")
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

        if not results:
            return Response([])

        serializer = CostTrendPointSerializer(results, many=True)
        return Response(serializer.data)

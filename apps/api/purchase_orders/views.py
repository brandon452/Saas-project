import logging

from datetime import timezone as dt_timezone
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.timezone import now
from django_ratelimit.core import is_ratelimited
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from audit.services import log_audit_event
from exports.audit import log_export_event
from exports.config import get_csv_rate, get_pdf_rate
from exports.filenames import csv_filename, pdf_filename
from exports.rows.purchase_orders import HEADERS, to_row
from exports.streaming import enforce_row_cap, stream_csv
from tenancy.mixins import OrgScopedViewSetMixin
from tenancy.permissions import IsOrgOperationalUser, RolePolicyMixin, get_org_membership

logger = logging.getLogger(__name__)

from .models import PurchaseOrder
from .serializers import (
    PurchaseOrderCreateSerializer,
    PurchaseOrderLineSerializer,
    PurchaseOrderLineWriteSerializer,
    PurchaseOrderSerializer,
    PurchaseOrderUpdateSerializer,
)
from .services import generate_po_number, sync_purchase_order_next_number


def _po_line_warnings(po, line):
    from suppliers.models import SupplierItem
    has_link = SupplierItem.objects.filter(
        supplier=po.supplier, org_item=line.item, is_active=True
    ).exists()
    if has_link:
        return []
    return [f"'{line.item.display_name}' has no catalog link to this supplier."]


def _html_to_pdf(html_string: str) -> bytes:
    from weasyprint import HTML  # lazy — avoids module-load failure on Windows dev
    return HTML(string=html_string).write_pdf()


class PurchaseOrderViewSet(RolePolicyMixin, OrgScopedViewSetMixin, ModelViewSet):
    permission_resource = "purchase_orders"
    queryset = PurchaseOrder.all_objects.none()
    permission_classes = OrgScopedViewSetMixin.permission_classes + [IsOrgOperationalUser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed("DELETE")

    def get_queryset(self):
        qs = (
            PurchaseOrder.objects
            .for_org(self.request.org)
            .select_related("supplier", "branch", "created_by")
            .prefetch_related("lines__item__master_item", "receipts__lines")
        )

        params = self.request.query_params

        status_filter = params.get("status")
        if status_filter:
            statuses = [s.strip() for s in status_filter.split(",") if s.strip()]
            qs = qs.filter(status__in=statuses) if len(statuses) > 1 else qs.filter(status=statuses[0])

        supplier_id = params.get("supplier")
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)

        branch_id = params.get("branch")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)

        search = params.get("search")
        if search:
            qs = qs.filter(po_number__icontains=search)

        created_at_after = params.get("created_at_after")
        if created_at_after:
            qs = qs.filter(created_at__date__gte=created_at_after)

        created_at_before = params.get("created_at_before")
        if created_at_before:
            qs = qs.filter(created_at__date__lte=created_at_before)

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return PurchaseOrderCreateSerializer
        if self.action in ("update", "partial_update"):
            return PurchaseOrderUpdateSerializer
        return PurchaseOrderSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        get_org_membership(self.request)
        branch = serializer.validated_data.get("branch")
        if branch is not None and branch.organization_id != self.request.org.id:
            logger.warning(
                "PO creation blocked: branch %s does not belong to org %s (user %s)",
                branch.pk,
                self.request.org.pk,
                self.request.user,
            )
            raise DRFValidationError({"detail": "Branch does not belong to this organisation."})
        for _ in range(5):
            po_number = generate_po_number(self.request.org)
            try:
                purchase_order = serializer.save(
                    organization=self.request.org,
                    created_by=self.request.user,
                    po_number=po_number,
                )
                sync_purchase_order_next_number(self.request.org, purchase_order.po_number)
                return
            except IntegrityError as exc:
                # Retry on rare sequence race collisions.
                if "unique_po_number_per_org" not in str(exc):
                    raise
                continue

        raise DRFValidationError({"detail": "Could not allocate a unique PO number. Please retry."})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        response_serializer = PurchaseOrderSerializer(
            serializer.instance, context={"request": request}
        )
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=["post"], url_path="submit")
    @transaction.atomic
    def submit(self, request, *args, **kwargs):
        po = self.get_object()
        po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)

        if not po.can_transition_to(PurchaseOrder.SUBMITTED):
            return Response(
                {"detail": f"Cannot submit a purchase order with status {po.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not po.lines.exists():
            return Response(
                {"detail": "Cannot submit a purchase order with no line items."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        po.status = PurchaseOrder.SUBMITTED
        po.save(update_fields=["status", "updated_at"])
        log_audit_event(
            organization=self.request.org,
            actor_user=request.user,
            event_type="po.submitted",
            resource_type="purchase_order",
            resource_id=po.id,
            summary=f"Purchase order {po.po_number} submitted",
            diff_json={"status": {"before": PurchaseOrder.DRAFT, "after": PurchaseOrder.SUBMITTED}},
            metadata_json={
                "po_number": po.po_number,
                "supplier_id": str(po.supplier_id),
                "branch_id": str(po.branch_id),
            },
        )
        return Response(PurchaseOrderSerializer(po).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    @transaction.atomic
    def cancel(self, request, *args, **kwargs):
        po = self.get_object()
        po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)

        if not po.can_transition_to(PurchaseOrder.CANCELLED):
            return Response(
                {"detail": f"Cannot cancel a purchase order with status {po.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous_status = po.status
        po.status = PurchaseOrder.CANCELLED
        po.save(update_fields=["status", "updated_at"])
        log_audit_event(
            organization=self.request.org,
            actor_user=request.user,
            event_type="po.cancelled",
            resource_type="purchase_order",
            resource_id=po.id,
            summary=f"Purchase order {po.po_number} cancelled",
            diff_json={"status": {"before": previous_status, "after": PurchaseOrder.CANCELLED}},
            metadata_json={
                "po_number": po.po_number,
                "supplier_id": str(po.supplier_id),
                "branch_id": str(po.branch_id),
            },
        )
        return Response(PurchaseOrderSerializer(po).data)

    @action(detail=True, methods=["post"], url_path="reconcile-status")
    @transaction.atomic
    def reconcile_status(self, request, *args, **kwargs):
        po = PurchaseOrder.objects.select_for_update().get(pk=self.get_object().pk)
        if po.status not in (PurchaseOrder.PARTIALLY_RECEIVED, PurchaseOrder.SUBMITTED):
            return Response(
                {"detail": "Only SUBMITTED or PARTIALLY_RECEIVED orders can be reconciled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        all_lines = list(po.lines.all())
        if not all_lines:
            return Response({"detail": "PO has no lines."}, status=status.HTTP_400_BAD_REQUEST)
        new_status = (
            PurchaseOrder.FULLY_RECEIVED
            if all(line.received_quantity >= line.ordered_quantity for line in all_lines)
            else PurchaseOrder.PARTIALLY_RECEIVED
        )
        po.status = new_status
        po.save(update_fields=["status", "updated_at"])
        return Response(PurchaseOrderSerializer(po).data)

    @action(detail=True, methods=["get"], url_path="lines")
    def lines(self, request, *args, **kwargs):
        po = self.get_object()
        serializer = PurchaseOrderLineSerializer(po.lines.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="lines/add")
    def add_line(self, request, *args, **kwargs):
        po = self.get_object()

        if po.status != PurchaseOrder.DRAFT:
            return Response(
                {"detail": "Line items can only be added to Draft purchase orders."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PurchaseOrderLineWriteSerializer(
            data=request.data,
            context={"request": request, "purchase_order": po},
        )
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(purchase_order=po)
        except IntegrityError as exc:
            if "unique_item_per_po" in str(exc):
                raise DRFValidationError({"item": ["This item already exists on the purchase order."]})
            raise
        line = serializer.instance
        response_data = PurchaseOrderLineSerializer(line).data
        response_data["warnings"] = _po_line_warnings(po, line)
        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path=r"lines/(?P<line_id>[^/.]+)")
    def update_line(self, request, line_id=None, *args, **kwargs):
        po = self.get_object()

        if po.status != PurchaseOrder.DRAFT:
            return Response(
                {"detail": "Line items can only be edited on Draft purchase orders."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        line = po.lines.filter(pk=line_id).first()
        if not line:
            return Response(
                {"detail": "Line item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PurchaseOrderLineWriteSerializer(
            line,
            data=request.data,
            partial=True,
            context={"request": request, "purchase_order": po},
        )
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except IntegrityError as exc:
            if "unique_item_per_po" in str(exc):
                raise DRFValidationError({"item": ["This item already exists on the purchase order."]})
            raise
        line = serializer.instance
        response_data = PurchaseOrderLineSerializer(line).data
        response_data["warnings"] = _po_line_warnings(po, line)
        return Response(response_data)

    @action(detail=False, methods=["get"], url_path="export/csv")
    def export_csv(self, request, *args, **kwargs):
        if is_ratelimited(request, group="po_export_csv", key="user", rate=get_csv_rate(), method="GET", increment=True):
            return Response(
                {"detail": "Too many export requests. Please wait before exporting again."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        qs = self.get_queryset().select_related("supplier", "branch")
        row_count = enforce_row_cap(qs)
        log_export_event(
            organization=request.org,
            actor_user=request.user,
            resource="purchase_order",
            format="csv",
            filters=dict(request.query_params),
            row_count=row_count,
        )
        return stream_csv(HEADERS, (to_row(po) for po in qs.iterator(chunk_size=500)), csv_filename("purchase-orders"))

    @action(detail=True, methods=["get"], url_path="export/pdf")
    def export_pdf(self, request, org_id=None, pk=None):
        if is_ratelimited(request, group="po_export_pdf", key="user", rate=get_pdf_rate(), method="GET", increment=True):
            return Response(
                {"detail": "Rate limit exceeded. Try again shortly."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        po = self.get_object()

        lines_with_totals = []
        grand_total = Decimal("0")
        for line in po.lines.select_related("item__master_item").order_by("id"):
            line_total = line.ordered_quantity * line.unit_price
            grand_total += line_total
            lines_with_totals.append({
                "item_name": line.item.display_name,
                "sku": line.item.sku,
                "ordered_quantity": line.ordered_quantity,
                "received_quantity": line.received_quantity,
                "unit_price": line.unit_price,
                "line_total": line_total,
            })

        context = {
            "organization": request.org,
            "po": po,
            "lines_with_totals": lines_with_totals,
            "grand_total": grand_total,
            "generated_at": now().astimezone(dt_timezone.utc),
        }

        html_string = render_to_string("purchase_orders/po_pdf.html", context)
        pdf_bytes = _html_to_pdf(html_string)

        log_export_event(
            organization=request.org,
            actor_user=request.user,
            resource="purchase_order",
            format="pdf",
            filters={},
            document_id=po.id,
        )

        filename = pdf_filename("po", po.po_number)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=["delete"], url_path=r"lines/(?P<line_id>[^/.]+)/remove")
    def remove_line(self, request, line_id=None, *args, **kwargs):
        po = self.get_object()

        if po.status != PurchaseOrder.DRAFT:
            return Response(
                {"detail": "Line items can only be removed from Draft purchase orders."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        line = po.lines.filter(pk=line_id).first()
        if not line:
            return Response(
                {"detail": "Line item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        line.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

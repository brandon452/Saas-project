import logging

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

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
from .services import generate_po_number


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
            qs = qs.filter(status=status_filter)

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
                serializer.save(
                    organization=self.request.org,
                    created_by=self.request.user,
                    po_number=po_number,
                )
                return
            except IntegrityError as exc:
                # Retry on rare sequence race collisions.
                if "unique_po_number_per_org" not in str(exc):
                    raise
                continue

        raise DRFValidationError({"detail": "Could not allocate a unique PO number. Please retry."})

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

        po.status = PurchaseOrder.CANCELLED
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
        serializer.save(purchase_order=po)
        return Response(
            PurchaseOrderLineSerializer(serializer.instance).data,
            status=status.HTTP_201_CREATED,
        )

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
        serializer.save()
        return Response(PurchaseOrderLineSerializer(serializer.instance).data)

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

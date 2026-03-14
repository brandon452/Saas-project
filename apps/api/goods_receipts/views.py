from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from tenancy.mixins import OrgScopedViewSetMixin
from tenancy.permissions import IsOrgOperationalUser, RolePolicyMixin, RolePolicyPermission

from .models import GoodsReceipt
from .serializers import (
    DirectReceiptCreateSerializer,
    GoodsReceiptCreateSerializer,
    GoodsReceiptSerializer,
)
from .services import post_direct_receipt, post_po_receipt


class GoodsReceiptViewSet(RolePolicyMixin, OrgScopedViewSetMixin, ModelViewSet):
    permission_resource = "goods_receipts"
    queryset = GoodsReceipt.all_objects.none()
    permission_classes = OrgScopedViewSetMixin.permission_classes + [IsOrgOperationalUser]
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        permissions = [permission() for permission in self.permission_classes]
        if self.action not in ("update", "partial_update", "destroy"):
            permissions.append(RolePolicyPermission())
        return permissions

    def get_queryset(self):
        return (
            GoodsReceipt.objects
            .for_org(self.request.org)
            .select_related("purchase_order", "branch", "supplier", "received_by")
            .prefetch_related("lines__po_line__item", "lines__item")
        )

    def get_serializer_class(self):
        if self.action == "create":
            receipt_type = self.request.data.get("receipt_type", GoodsReceipt.PO_RECEIPT)
            if receipt_type == GoodsReceipt.DIRECT_RECEIPT:
                return DirectReceiptCreateSerializer
            return GoodsReceiptCreateSerializer
        return GoodsReceiptSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        out = GoodsReceiptSerializer(serializer.instance, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def perform_create(self, serializer):
        receipt_type = self.request.data.get("receipt_type", GoodsReceipt.PO_RECEIPT)

        if receipt_type == GoodsReceipt.DIRECT_RECEIPT:
            receipt = serializer.save(
                organization=self.request.org,
                receipt_type=GoodsReceipt.DIRECT_RECEIPT,
                received_by=self.request.user,
            )
            try:
                post_direct_receipt(
                    receipt=receipt,
                    lines_data=serializer.validated_data["lines"],
                    performed_by=self.request.user,
                    organization=self.request.org,
                )
            except DjangoValidationError as exc:
                raise DRFValidationError({"detail": exc.messages})
        else:
            po = serializer.validated_data["purchase_order"]
            receipt = serializer.save(
                organization=self.request.org,
                receipt_type=GoodsReceipt.PO_RECEIPT,
                branch=po.branch,
                received_by=self.request.user,
            )
            try:
                post_po_receipt(
                    receipt=receipt,
                    lines_data=serializer.validated_data["lines"],
                    performed_by=self.request.user,
                    organization=self.request.org,
                )
            except DjangoValidationError as exc:
                raise DRFValidationError({"detail": exc.messages})

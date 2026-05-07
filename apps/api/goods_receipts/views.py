from datetime import date, datetime, time

from django.db.models import Q

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django_ratelimit.core import is_ratelimited
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from exports.audit import log_export_event
from exports.config import get_csv_rate
from exports.filenames import csv_filename
from exports.rows.goods_receipts import HEADERS, to_row
from exports.streaming import enforce_row_cap, stream_csv
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

    def _parse_date(self, value):
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            raise DRFValidationError({"detail": "Invalid date format. Use YYYY-MM-DD."})

    def get_queryset(self):
        qs = (
            GoodsReceipt.objects
            .for_org(self.request.org)
            .select_related("purchase_order", "purchase_order__supplier", "branch", "supplier", "received_by")
            .prefetch_related("lines__po_line__item__master_item", "lines__item__master_item")
        )

        receipt_type = self.request.query_params.get("receipt_type")
        if receipt_type:
            qs = qs.filter(receipt_type=receipt_type)

        branch = self.request.query_params.get("branch")
        if branch:
            qs = qs.filter(branch=branch)

        supplier = self.request.query_params.get("supplier")
        if supplier:
            qs = qs.filter(Q(supplier=supplier) | Q(purchase_order__supplier=supplier))

        date_after_param = self.request.query_params.get("date_after")
        date_before_param = self.request.query_params.get("date_before")

        date_after = self._parse_date(date_after_param) if date_after_param else None
        date_before = self._parse_date(date_before_param) if date_before_param else None

        if date_after and date_before and date_after > date_before:
            raise DRFValidationError({"detail": "date_after must not be after date_before."})

        if date_after:
            qs = qs.filter(received_at__gte=timezone.make_aware(datetime.combine(date_after, time.min)))

        if date_before:
            qs = qs.filter(received_at__lte=timezone.make_aware(datetime.combine(date_before, time.max)))

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            receipt_type = self.request.data.get("receipt_type", GoodsReceipt.PO_RECEIPT)
            if receipt_type == GoodsReceipt.DIRECT_RECEIPT:
                return DirectReceiptCreateSerializer
            return GoodsReceiptCreateSerializer
        return GoodsReceiptSerializer

    def create(self, request, *args, **kwargs):
        if is_ratelimited(request, group="goods_receipt_create", key="user", rate="60/m", method="POST", increment=True):
            return Response(
                {"detail": "Too many requests. Please wait before posting another receipt."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        serializer_context = self.get_serializer_context()
        if request.data.get("receipt_type") == GoodsReceipt.DIRECT_RECEIPT:
            branch_id = request.data.get("branch")
            if branch_id:
                from branches.models import Branch
                branch = Branch.objects.filter(pk=branch_id, organization=request.org).first()
                serializer_context["branch"] = branch

        serializer = self.get_serializer(data=request.data, context=serializer_context)
        serializer.is_valid(raise_exception=True)
        idempotency_key = serializer.validated_data.get("idempotency_key")

        if idempotency_key:
            existing = GoodsReceipt.objects.for_org(request.org).filter(idempotency_key=idempotency_key).first()
            if existing is not None:
                out = GoodsReceiptSerializer(existing, context={"request": request})
                return Response(out.data, status=status.HTTP_200_OK)

        try:
            self.perform_create(serializer)
        except IntegrityError:
            if idempotency_key:
                existing = GoodsReceipt.objects.for_org(request.org).filter(idempotency_key=idempotency_key).first()
                if existing is not None:
                    out = GoodsReceiptSerializer(existing, context={"request": request})
                    return Response(out.data, status=status.HTTP_200_OK)
            raise

        out = GoodsReceiptSerializer(serializer.instance, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="export/csv")
    def export_csv(self, request, *args, **kwargs):
        if is_ratelimited(request, group="gr_export_csv", key="user", rate=get_csv_rate(), method="GET", increment=True):
            return Response(
                {"detail": "Too many export requests. Please wait before exporting again."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        qs = self.get_queryset().select_related("branch", "supplier", "purchase_order", "purchase_order__supplier")
        row_count = enforce_row_cap(qs)
        log_export_event(
            organization=request.org,
            actor_user=request.user,
            resource="goods_receipt",
            format="csv",
            filters=dict(request.query_params),
            row_count=row_count,
        )
        return stream_csv(HEADERS, (to_row(gr) for gr in qs.iterator(chunk_size=500)), csv_filename("goods-receipts"))

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

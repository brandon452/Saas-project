from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from tenancy.mixins import OrgScopedViewSetMixin
from tenancy.permissions import IsOrgOperationalUser, RolePolicyMixin

from .models import QuickSale
from .serializers import QuickSaleCreateSerializer, QuickSaleSerializer
from .services import create_quick_sale, void_quick_sale


class QuickSaleViewSet(RolePolicyMixin, OrgScopedViewSetMixin, viewsets.GenericViewSet):
    permission_classes = OrgScopedViewSetMixin.permission_classes + [IsOrgOperationalUser]
    permission_resource = "quick_sales"
    serializer_class = QuickSaleSerializer
    http_method_names = ["get", "post", "head", "options"]
    queryset = QuickSale.all_objects.none()

    def get_queryset(self):
        qs = (
            QuickSale.objects.for_org(self.request.org)
            .select_related("branch", "sold_by", "voided_by")
            .prefetch_related("lines__item__master_item")
        )

        branch = self.request.query_params.get("branch")
        status_param = self.request.query_params.get("status")
        from_date = self.request.query_params.get("from_date")
        to_date = self.request.query_params.get("to_date")

        if branch:
            qs = qs.filter(branch_id=branch)
        if status_param:
            qs = qs.filter(status=status_param)
        if from_date:
            qs = qs.filter(occurred_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(occurred_at__date__lte=to_date)

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return QuickSaleCreateSerializer
        return QuickSaleSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        serializer = QuickSaleSerializer(
            page if page is not None else queryset,
            many=True,
            context={"request": request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        sale = self.get_object()
        return Response(QuickSaleSerializer(sale, context={"request": request}).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        lines = [
            {
                "item": line["item"],
                "quantity": line["quantity"],
                "unit_price": line["unit_price"],
            }
            for line in data["lines"]
        ]

        idempotency_key = data.get("idempotency_key") or None

        if idempotency_key:
            try:
                existing = QuickSale.objects.for_org(request.org).get(
                    idempotency_key=idempotency_key
                )
                return Response(
                    QuickSaleSerializer(existing, context={"request": request}).data,
                    status=status.HTTP_200_OK,
                )
            except QuickSale.DoesNotExist:
                pass

        try:
            sale = create_quick_sale(
                org=request.org,
                branch=data["branch"],
                lines=lines,
                customer_name=data.get("customer_name", ""),
                notes=data.get("notes", ""),
                occurred_at=data.get("occurred_at"),
                performed_by=request.user,
                idempotency_key=idempotency_key,
            )
        except DjangoValidationError as exc:
            raise DRFValidationError({"detail": exc.messages})

        return Response(
            QuickSaleSerializer(sale, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def void(self, request, *args, **kwargs):
        sale = self.get_object()
        try:
            sale = void_quick_sale(
                org=request.org,
                quick_sale=sale,
                performed_by=request.user,
            )
        except DjangoValidationError as exc:
            raise DRFValidationError({"detail": exc.messages})

        return Response(QuickSaleSerializer(sale, context={"request": request}).data)

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from tenancy.mixins import BranchScopedMixin, OrgScopedViewSetMixin
from tenancy.permissions import IsOrgOperationalUser, RolePolicyMixin

from .models import Item, StockLedger, StockOnHand
from .serializers import ItemSerializer, StockLedgerSerializer, StockMovementSerializer, StockOnHandSerializer
from .services import record_stock_movement


@extend_schema_view(
    list=extend_schema(description="Requires STAFF, ADMIN, or OWNER role."),
    retrieve=extend_schema(description="Requires STAFF, ADMIN, or OWNER role."),
    create=extend_schema(description="Requires ADMIN or OWNER role."),
    partial_update=extend_schema(description="Requires ADMIN or OWNER role."),
    update=extend_schema(description="Requires ADMIN or OWNER role."),
    destroy=extend_schema(description="Requires ADMIN or OWNER role."),
)
class ItemViewSet(RolePolicyMixin, OrgScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ItemSerializer
    queryset = Item.all_objects.none()
    permission_resource = "items"
    permission_classes = OrgScopedViewSetMixin.permission_classes + [IsOrgOperationalUser]

    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "sku"]
    ordering_fields = ["name", "sku", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        qs = Item.objects.for_org(self.request.org)

        is_active = self.request.query_params.get("is_active")
        if is_active is None:
            qs = qs.filter(is_active=True)
        else:
            qs = qs.filter(is_active=is_active.lower() == "true")

        return qs

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


@extend_schema_view(
    list=extend_schema(description="Requires STAFF, ADMIN, or OWNER role."),
    retrieve=extend_schema(description="Requires STAFF, ADMIN, or OWNER role."),
)
class StockOnHandViewSet(RolePolicyMixin, OrgScopedViewSetMixin, BranchScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = StockOnHandSerializer
    queryset = StockOnHand.all_objects.none()
    permission_resource = "stock_on_hand"

    filter_backends = [OrderingFilter]
    ordering_fields = ["quantity", "item__name", "branch__name"]
    ordering = ["item__name"]

    def get_queryset(self):
        qs = StockOnHand.objects.for_org(self.request.org).select_related("branch", "item")

        if self.request.branch:
            qs = qs.filter(branch=self.request.branch)

        branch_id = self.request.query_params.get("branch")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)

        item_id = self.request.query_params.get("item")
        if item_id:
            qs = qs.filter(item_id=item_id)

        is_active = self.request.query_params.get("is_active")
        if is_active is None:
            qs = qs.filter(item__is_active=True)
        else:
            qs = qs.filter(item__is_active=is_active.lower() == "true")

        return qs


@extend_schema_view(
    list=extend_schema(description="Requires STAFF, ADMIN, or OWNER role."),
    create=extend_schema(description="Requires STAFF, ADMIN, or OWNER role."),
)
class StockMovementViewSet(RolePolicyMixin, OrgScopedViewSetMixin, BranchScopedMixin, viewsets.GenericViewSet):
    queryset = StockLedger.all_objects.none()
    permission_resource = "movements"
    permission_classes = OrgScopedViewSetMixin.permission_classes + [IsOrgOperationalUser]

    filter_backends = [OrderingFilter]
    ordering_fields = ["occurred_at", "created_at"]
    ordering = ["-occurred_at"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.action == "create":
            if not getattr(request, "branch", None):
                raise DRFValidationError({"detail": "X-BRANCH-ID header required"})
            self._validate_branch_org(request)

    def _validate_branch_org(self, request):
        if request.branch and request.branch.organization_id != request.org.id:
            raise PermissionDenied("Branch does not belong to the current organization.")

    def get_serializer_class(self):
        if self.action == "create":
            return StockMovementSerializer
        return StockLedgerSerializer

    def get_queryset(self):
        qs = StockLedger.objects.for_org(self.request.org).select_related("branch", "item", "performed_by")

        if self.request.branch:
            qs = qs.filter(branch=self.request.branch)

        branch_id = self.request.query_params.get("branch")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)

        item_id = self.request.query_params.get("item")
        if item_id:
            qs = qs.filter(item_id=item_id)

        movement_type = self.request.query_params.get("movement_type")
        if movement_type:
            qs = qs.filter(movement_type=movement_type)

        reference_type = self.request.query_params.get("reference_type")
        if reference_type:
            qs = qs.filter(reference_type=reference_type)

        from_date = self.request.query_params.get("from_date")
        if from_date:
            qs = qs.filter(occurred_at__date__gte=from_date)

        to_date = self.request.query_params.get("to_date")
        if to_date:
            qs = qs.filter(occurred_at__date__lte=to_date)

        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item = serializer.validated_data["item"]
        idempotency_key = serializer.validated_data["idempotency_key"]

        try:
            ledger, created = record_stock_movement(
                org=request.org,
                branch=request.branch,
                item=item,
                quantity=serializer.validated_data["quantity"],
                movement_type=serializer.validated_data["movement_type"],
                performed_by=request.user,
                reference_type=serializer.validated_data["reference_type"],
                reference_id=serializer.validated_data["reference_id"],
                reason=serializer.validated_data["reason"],
                occurred_at=serializer.validated_data["occurred_at"],
                idempotency_key=idempotency_key,
            )
        except IntegrityError:
            ledger = StockLedger.objects.for_org(request.org).get(idempotency_key=idempotency_key)
            created = False
        except DjangoValidationError as exc:
            raise DRFValidationError({"detail": exc.messages})

        out = StockLedgerSerializer(ledger, context={"request": request})
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(out.data, status=status_code)

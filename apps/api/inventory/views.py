from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import BooleanField, Case, Count, F, IntegerField, OuterRef, Q, Subquery, Value, When
from django_ratelimit.core import is_ratelimited
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework import status, viewsets
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from branches.models import Branch
from tenancy.mixins import BranchScopedMixin, OrgScopedViewSetMixin
from tenancy.models import Organization
from tenancy.permissions import (
    IsOrgOperationalUser,
    IsOrgOwnerOrAdmin,
    IsOrgOwnerOrAdminOrParentAdmin,
    IsOrgOwnerOrParentAdmin,
    IsParentAdmin,
    IsParentMember,
    RolePolicyMixin,
    get_parent_membership,
)

from .models import (
    BranchItem, InventoryClosePeriod,
    MasterItem, OrgItem, StockLedger, StockOnHand, StockTake, StockTakeLine,
)
from .serializers import (
    BranchItemBulkActivateSerializer,
    InventoryCloseSnapshotSerializer,
    InventoryClosePeriodSerializer,
    InventoryClosePeriodCreateSerializer,
    BranchItemBulkDeactivateSerializer,
    BranchItemCatalogSerializer,
    BranchItemCreateSerializer,
    BranchItemSerializer,
    MasterItemSerializer,
    OrgItemCreateSerializer,
    OrgItemSerializer,
    OrgMasterItemSerializer,
    StockLedgerSerializer,
    StockMovementSerializer,
    StockOnHandSerializer,
    StockTakeCreateSerializer,
    StockTakeDetailSerializer,
    StockTakeLineBulkUpdateSerializer,
    StockTakeLineSerializer,
    StockTakeLineUpdateSerializer,
    StockTakeListSerializer,
    StockTakeNotesUpdateSerializer,
)
from .services import (
    approve_stock_take,
    cancel_stock_take,
    close_period,
    record_stock_movement,
    reopen_period,
    reopen_stock_take,
    start_stock_take,
    submit_stock_take,
)


@extend_schema_view(
    list=extend_schema(description="Requires STAFF, ADMIN, or OWNER role."),
    retrieve=extend_schema(description="Requires STAFF, ADMIN, or OWNER role."),
    create=extend_schema(description="Requires ADMIN or OWNER role."),
    partial_update=extend_schema(description="Requires ADMIN or OWNER role."),
    update=extend_schema(description="Requires ADMIN or OWNER role."),
    destroy=extend_schema(description="Requires ADMIN or OWNER role."),
)
class OrgItemViewSet(RolePolicyMixin, OrgScopedViewSetMixin, BranchScopedMixin, viewsets.ModelViewSet):
    serializer_class = OrgItemSerializer
    queryset = OrgItem.all_objects.none()
    permission_resource = "items"
    permission_classes = OrgScopedViewSetMixin.permission_classes + [IsOrgOperationalUser]

    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "master_item__name", "master_item__sku"]
    ordering_fields = ["name", "master_item__sku", "created_at"]
    ordering = ["master_item__name"]

    def get_serializer_class(self):
        if self.action == "create":
            return OrgItemCreateSerializer
        return OrgItemSerializer

    def get_queryset(self):
        qs = OrgItem.objects.for_org(self.request.org).select_related("master_item")

        is_active = self.request.query_params.get("is_active")
        if is_active is None:
            qs = qs.filter(is_active=True)
        else:
            qs = qs.filter(is_active=is_active.lower() == "true")

        branch = getattr(self.request, "branch", None)
        if branch is not None:
            qs = qs.filter(
                branch_items__branch=branch,
                branch_items__is_active=True,
            )

        return qs

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org, is_active=True)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(organization=request.org, is_active=True)
        output = OrgItemSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(output.data)
        was_reactivated = getattr(serializer, "_existing_inactive", None) is not None
        status_code = status.HTTP_200_OK if was_reactivated else status.HTTP_201_CREATED
        return Response(output.data, status=status_code, headers=headers)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class MasterItemViewSet(viewsets.ModelViewSet):
    serializer_class = MasterItemSerializer
    queryset = MasterItem.objects.none()
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "sku"]
    ordering_fields = ["name", "sku", "created_at"]
    ordering = ["name"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), IsParentMember()]
        return [IsAuthenticated(), IsParentAdmin()]

    def get_queryset(self):
        parent = get_parent_membership(self.request)
        if not parent:
            return MasterItem.objects.none()
        return MasterItem.objects.filter(parent_company=parent.parent_company)

    def perform_create(self, serializer):
        parent = get_parent_membership(self.request)
        serializer.save(parent_company=parent.parent_company)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class OrgMasterItemView(APIView):
    permission_classes = [IsAuthenticated, IsOrgOwnerOrAdmin]

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
        activated_master_ids = OrgItem.objects.filter(
            organization=request.org,
        ).values_list("master_item_id", flat=True)

        available = MasterItem.objects.filter(
            parent_company=request.org.parent_company,
            is_active=True,
        ).exclude(
            id__in=activated_master_ids,
        ).order_by("name")

        serializer = OrgMasterItemSerializer(available, many=True)
        return Response(serializer.data)


class BranchItemCatalogView(APIView):
    permission_classes = [IsAuthenticated, IsOrgOwnerOrAdmin]

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
        branch_id = request.query_params.get("branch")
        if not branch_id:
            raise DRFValidationError({"branch": "This field is required."})

        try:
            branch = Branch.objects.get(pk=branch_id, organization=request.org)
        except Branch.DoesNotExist:
            raise DRFValidationError(
                {"branch": "Branch not found or does not belong to this organisation."}
            )

        branch_item_subquery = BranchItem.objects.filter(
            org_item=OuterRef("pk"),
            branch=branch,
            is_active=True,
        ).values("id")[:1]

        queryset = (
            OrgItem.objects.for_org(request.org)
            .filter(is_active=True)
            .select_related("master_item")
            .annotate(
                branch_item_id=Subquery(
                    branch_item_subquery,
                    output_field=IntegerField(),
                )
            )
            .annotate(
                is_enabled=Case(
                    When(branch_item_id__isnull=False, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                )
            )
            .order_by("master_item__name")
        )

        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(master_item__name__icontains=search)
                | Q(master_item__sku__icontains=search)
            )

        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = BranchItemCatalogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class BranchItemBulkActivateView(APIView):
    permission_classes = [IsAuthenticated, IsOrgOwnerOrAdmin]

    def initial(self, request, *args, **kwargs):
        org_id = self.kwargs.get("org_id")
        try:
            request.org = Organization.objects.get(pk=org_id, is_active=True)
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")

        parent_membership = get_parent_membership(request)
        request.parent_role = parent_membership.role if parent_membership else None
        super().initial(request, *args, **kwargs)

    @transaction.atomic
    def post(self, request, org_id=None, *args, **kwargs):
        serializer = BranchItemBulkActivateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        branch = serializer.validated_data["branch"]
        org_items = serializer.validated_data["org_items"]

        existing = {
            bi.org_item_id: bi
            for bi in BranchItem.objects.filter(
                branch=branch,
                org_item__in=org_items,
            )
        }

        to_create = []
        to_reactivate_ids = []
        already_active = 0

        for org_item in org_items:
            bi = existing.get(org_item.id)
            if bi is None:
                to_create.append(BranchItem(org_item=org_item, branch=branch, is_active=True))
            elif bi.is_active:
                already_active += 1
            else:
                to_reactivate_ids.append(bi.id)

        if to_create:
            BranchItem.objects.bulk_create(to_create)

        if to_reactivate_ids:
            BranchItem.objects.filter(id__in=to_reactivate_ids).update(is_active=True)

        activated = len(to_create) + len(to_reactivate_ids)

        return Response(
            {
                "activated": activated,
                "already_active": already_active,
                "total": len(org_items),
            },
            status=status.HTTP_200_OK,
        )


class BranchItemBulkDeactivateView(APIView):
    permission_classes = [IsAuthenticated, IsOrgOwnerOrAdmin]

    def initial(self, request, *args, **kwargs):
        org_id = self.kwargs.get("org_id")
        try:
            request.org = Organization.objects.get(pk=org_id, is_active=True)
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")

        parent_membership = get_parent_membership(request)
        request.parent_role = parent_membership.role if parent_membership else None
        super().initial(request, *args, **kwargs)

    @transaction.atomic
    def post(self, request, org_id=None, *args, **kwargs):
        serializer = BranchItemBulkDeactivateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        branch_items = serializer.validated_data["branch_items"]

        active_ids = [bi.id for bi in branch_items if bi.is_active]
        already_inactive = len(branch_items) - len(active_ids)

        if active_ids:
            BranchItem.objects.filter(id__in=active_ids).update(is_active=False)

        return Response(
            {
                "deactivated": len(active_ids),
                "already_inactive": already_inactive,
                "total": len(branch_items),
            },
            status=status.HTTP_200_OK,
        )


class BranchItemViewSet(RolePolicyMixin, OrgScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = BranchItemSerializer
    queryset = BranchItem.objects.none()
    permission_resource = "branch_items"
    permission_classes = OrgScopedViewSetMixin.permission_classes + [IsOrgOperationalUser]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = [
        "org_item__name",
        "org_item__master_item__name",
        "org_item__master_item__sku",
    ]
    ordering_fields = ["org_item__master_item__name", "created_at"]
    ordering = ["org_item__master_item__name"]

    def get_serializer_class(self):
        if self.action == "create":
            return BranchItemCreateSerializer
        return BranchItemSerializer

    def get_queryset(self):
        qs = BranchItem.objects.filter(
            org_item__organization=self.request.org,
        ).select_related(
            "org_item__master_item",
            "branch",
        )
        branch_id = self.request.query_params.get("branch")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        is_active = self.request.query_params.get("is_active")
        if is_active is None:
            qs = qs.filter(is_active=True)
        else:
            qs = qs.filter(is_active=is_active.lower() == "true")
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        out = BranchItemSerializer(instance, context=self.get_serializer_context())
        was_reactivated = getattr(serializer, "_existing_inactive", None) is not None
        status_code = status.HTTP_200_OK if was_reactivated else status.HTTP_201_CREATED
        return Response(out.data, status=status_code)

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
    ordering_fields = ["quantity", "item__name", "item__master_item__name", "branch__name"]
    ordering = ["item__master_item__name"]

    def get_queryset(self):
        qs = StockOnHand.objects.for_org(self.request.org).select_related("branch", "item__master_item")

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

    def filter_queryset(self, queryset):
        qs = super().filter_queryset(queryset)
        ordering_param = self.request.query_params.get("ordering", "")
        field = ordering_param.lstrip("-")
        if field == "occurred_at" or not ordering_param:
            desc = not ordering_param or ordering_param.startswith("-")
            expr = F("occurred_at").desc(nulls_last=True) if desc else F("occurred_at").asc(nulls_last=True)
            return qs.order_by(expr, "-created_at" if desc else "created_at")
        return qs

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
        qs = StockLedger.objects.for_org(self.request.org).select_related("branch", "item__master_item", "performed_by")

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
        if is_ratelimited(request, group="stock_movement_create", key="user", rate="60/m", method="POST", increment=True):
            return Response(
                {"detail": "Too many requests. Please wait before posting another movement."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
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
                unit_cost=serializer.validated_data["unit_cost"],
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


class StockTakeViewSet(RolePolicyMixin, OrgScopedViewSetMixin, viewsets.ModelViewSet):
    permission_resource = "stock_takes"
    queryset = StockTake.all_objects.none()
    permission_classes = OrgScopedViewSetMixin.permission_classes + [IsOrgOperationalUser]
    filter_backends = [OrderingFilter]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return StockTakeCreateSerializer
        if self.action == "partial_update":
            return StockTakeNotesUpdateSerializer
        if self.action == "retrieve":
            return StockTakeDetailSerializer
        return StockTakeListSerializer

    def get_queryset(self):
        queryset = StockTake.objects.for_org(self.request.org).select_related(
            "branch",
            "created_by",
            "started_by",
            "submitted_by",
            "approved_by",
            "cancelled_by",
            "reopened_by",
        ).annotate(
            total_lines_count=Count("lines", distinct=True),
            counted_lines_count=Count(
                "lines",
                filter=Q(lines__counted_quantity__isnull=False),
                distinct=True,
            ),
        )
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("lines__org_item__master_item")
        return queryset

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return super().partial_update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.org,
            created_by=self.request.user,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = StockTakeDetailSerializer(serializer.instance, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)

    def _run_transition(self, request, service_fn):
        stock_take = self.get_object()
        try:
            service_fn(stock_take, performed_by=request.user)
        except DjangoValidationError as exc:
            raise DRFValidationError({"detail": exc.messages})

        stock_take.refresh_from_db()
        return Response(StockTakeDetailSerializer(stock_take, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, *args, **kwargs):
        return self._run_transition(request, start_stock_take)

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, *args, **kwargs):
        return self._run_transition(request, submit_stock_take)

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, *args, **kwargs):
        return self._run_transition(request, reopen_stock_take)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, *args, **kwargs):
        return self._run_transition(request, approve_stock_take)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, *args, **kwargs):
        return self._run_transition(request, cancel_stock_take)

    @action(detail=True, methods=["get"], url_path="lines")
    def lines(self, request, *args, **kwargs):
        stock_take = self.get_object()
        queryset = stock_take.lines.select_related("org_item__master_item").all()
        serializer = StockTakeLineSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["patch"], url_path="lines/bulk-update")
    @transaction.atomic
    def bulk_update_lines(self, request, *args, **kwargs):
        stock_take = self.get_object()

        if stock_take.status != StockTake.IN_PROGRESS:
            raise DRFValidationError(
                {"detail": "Lines can only be edited while the stock take is In Progress."}
            )

        serializer = StockTakeLineBulkUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        incoming = serializer.validated_data["lines"]

        # Fetch all lines for this stock take in one query
        incoming_ids = [item["id"] for item in incoming]
        line_map = {
            line.id: line
            for line in StockTakeLine.objects.filter(
                stock_take=stock_take, id__in=incoming_ids
            )
        }

        # Reject any IDs that don't belong to this stock take
        missing = [item["id"] for item in incoming if item["id"] not in line_map]
        if missing:
            raise DRFValidationError(
                {"detail": f"Line IDs not found on this stock take: {missing}"}
            )

        # Process entries in request order.
        # If duplicate IDs appear, the final occurrence determines the saved value.
        for item in incoming:
            line = line_map[item["id"]]
            line.counted_quantity = item["counted_quantity"]

        StockTakeLine.objects.bulk_update(
            line_map.values(), ["counted_quantity"]
        )

        all_lines = (
            stock_take.lines
            .select_related("org_item__master_item")
            .all()
        )
        return Response(StockTakeLineSerializer(all_lines, many=True).data)

    @action(detail=True, methods=["patch"], url_path=r"lines/(?P<line_pk>[0-9]+)")
    def update_line(self, request, line_pk=None, *args, **kwargs):
        stock_take = self.get_object()
        try:
            line = stock_take.lines.select_related("stock_take", "org_item__master_item").get(pk=line_pk)
        except StockTakeLine.DoesNotExist:
            raise NotFound("Line not found.")

        serializer = StockTakeLineUpdateSerializer(line, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(StockTakeLineSerializer(line, context={"request": request}).data)


class ClosePeriodViewSet(OrgScopedViewSetMixin, viewsets.GenericViewSet):
    queryset = InventoryClosePeriod.objects.none()

    def get_permissions(self):
        base = OrgScopedViewSetMixin.permission_classes
        if self.action in ("create", "close", "reopen"):
            return [p() for p in base + [IsOrgOwnerOrParentAdmin]]
        return [p() for p in base + [IsOrgOwnerOrAdminOrParentAdmin]]

    def get_queryset(self):
        return InventoryClosePeriod.objects.filter(
            organization=self.request.org
        ).order_by("-start_date")

    def list(self, request, *args, **kwargs):
        serializer = InventoryClosePeriodSerializer(self.get_queryset(), many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        period = self.get_object()
        return Response(InventoryClosePeriodSerializer(period).data)

    def create(self, request, *args, **kwargs):
        serializer = InventoryClosePeriodCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        period = serializer.save(organization=request.org, status=InventoryClosePeriod.OPEN)
        return Response(InventoryClosePeriodSerializer(period).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, *args, **kwargs):
        period = self.get_object()
        try:
            close_period(period, closed_by=request.user)
        except DjangoValidationError as exc:
            raise DRFValidationError({"detail": exc.messages})
        period.refresh_from_db()
        return Response(InventoryClosePeriodSerializer(period).data)

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, *args, **kwargs):
        period = self.get_object()
        try:
            reopen_period(period, reopened_by=request.user)
        except DjangoValidationError as exc:
            raise DRFValidationError({"detail": exc.messages})
        period.refresh_from_db()
        return Response(InventoryClosePeriodSerializer(period).data)

    @action(detail=True, methods=["get"], url_path="snapshots")
    def snapshots(self, request, *args, **kwargs):
        period = self.get_object()
        qs = period.snapshots.select_related("branch", "item__master_item").all()
        return Response(InventoryCloseSnapshotSerializer(qs, many=True).data)

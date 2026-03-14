from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from tenancy.mixins import OrgScopedViewSetMixin
from tenancy.permissions import RolePolicyMixin, get_org_membership, get_parent_membership

from .models import Supplier
from .serializers import SupplierDeactivateSerializer, SupplierSerializer, SupplierWriteSerializer


class SupplierViewSet(
    RolePolicyMixin,
    OrgScopedViewSetMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    permission_resource = "suppliers"
    queryset = Supplier.all_objects.none()
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = Supplier.objects.for_org(self.request.org)

        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)

        is_active = self.request.query_params.get("is_active")

        parent = get_parent_membership(self.request)
        if parent:
            if is_active == "false":
                return qs.none()
            return qs.filter(is_active=True)

        membership = get_org_membership(self.request)
        role = membership.role if membership else None

        if role in ("OWNER", "ADMIN"):
            if is_active in ("true", "false"):
                qs = qs.filter(is_active=(is_active == "true"))
        else:
            if is_active == "false":
                return qs.none()
            qs = qs.filter(is_active=True)

        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return SupplierWriteSerializer
        if self.action == "deactivate":
            return SupplierDeactivateSerializer
        return SupplierSerializer

    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.org,
            created_by=self.request.user,
        )

    @action(detail=True, methods=["patch"], url_path="deactivate")
    def deactivate(self, request, *args, **kwargs):
        supplier = self.get_object()
        serializer = self.get_serializer(
            supplier,
            data={"is_active": False},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(SupplierSerializer(supplier).data)

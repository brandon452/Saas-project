from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter
from rest_framework.views import APIView

from tenancy.mixins import BranchScopedMixin, OrgScopedViewSetMixin
from tenancy.permissions import IsOrgOperationalUser, RolePolicyMixin
from tenancy.models import Organization

from .models import Branch
from .serializers import BranchSerializer, NetworkBranchSerializer


@extend_schema_view(
    list=extend_schema(description="Requires STAFF, ADMIN, or OWNER role."),
    retrieve=extend_schema(description="Requires STAFF, ADMIN, or OWNER role."),
    create=extend_schema(description="Requires ADMIN or OWNER role."),
    partial_update=extend_schema(description="Requires ADMIN or OWNER role."),
)
class BranchViewSet(RolePolicyMixin, OrgScopedViewSetMixin, BranchScopedMixin, viewsets.ModelViewSet):
    serializer_class = BranchSerializer
    queryset = Branch.all_objects.none()
    permission_resource = "branches"
    permission_classes = OrgScopedViewSetMixin.permission_classes + [IsOrgOperationalUser]
    http_method_names = ["get", "post", "patch", "head", "options"]

    filter_backends = [OrderingFilter]
    ordering_fields = ["name", "code"]
    ordering = ["name"]

    def get_queryset(self):
        qs = Branch.objects.for_org(self.request.org)

        membership = getattr(self.request, "org_membership", None)
        if self.action in ("retrieve", "update", "partial_update", "destroy"):
            if membership and membership.role in ("OWNER", "ADMIN"):
                return qs

        if self.request.branch:
            qs = qs.filter(pk=self.request.branch.pk)
        return qs

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)


class NetworkBranchView(APIView):
    """
    GET orgs/{org_id}/network-branches/

    Returns all branches from all active organizations in the parent
    company network. No exclusions. No pagination. Read-only.

    IsOrgOperationalUser allows all authenticated users on GET.

    org_id is used only for access control context; the returned branch
    set is global across the parent company network.
    """

    permission_classes = [IsAuthenticated, IsOrgOperationalUser]

    def get(self, request, org_id=None, *args, **kwargs):
        active_org_ids = Organization.objects.filter(is_active=True).values_list("pk", flat=True)
        branches = (
            Branch.objects.filter(organization__in=active_org_ids)
            .select_related("organization")
            .order_by("organization__name", "name")
        )

        serializer = NetworkBranchSerializer(branches, many=True)
        return Response(serializer.data)

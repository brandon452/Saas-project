from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter
from rest_framework.views import APIView

from tenancy.mixins import BranchScopedMixin, OrgScopedViewSetMixin
from tenancy.permissions import IsOrgMemberOrParent, IsOrgOperationalUser, RolePolicyMixin, get_parent_membership
from tenancy.models import Organization

from .api import Branch, branches_for_org, network_branches_for_org
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
        qs = branches_for_org(self.request.org)

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

    org_id is resolved to request.org in initial() and used for access control.
    Returned branches are restricted to active organizations in the same
    parent company as request.org.
    """

    permission_classes = [IsAuthenticated, IsOrgMemberOrParent, IsOrgOperationalUser]

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
        branches = network_branches_for_org(request.org)

        serializer = NetworkBranchSerializer(branches, many=True)
        return Response(serializer.data)

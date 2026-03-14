from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated

from .models import Organization, OrganizationMember
from .permissions import IsOrgMemberOrParent, get_parent_membership


class OrgScopedViewSetMixin:
    permission_classes = [IsAuthenticated, IsOrgMemberOrParent]

    def initial(self, request, *args, **kwargs):
        self._resolve_org(request)
        super().initial(request, *args, **kwargs)

    def _resolve_org(self, request):
        org_id = self.kwargs.get("org_id")
        if not org_id:
            raise NotFound("Organization context is required.")

        try:
            org = Organization.objects.get(pk=org_id, is_active=True)
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")

        request.org = org

        parent_membership = get_parent_membership(request)
        if parent_membership:
            request.parent_role = parent_membership.role
            request.org_membership = None
            request.branch = None
            return

        request.parent_role = None

    def get_queryset(self):
        base_queryset = super().get_queryset()
        return base_queryset.model.objects.for_org(self.request.org)


class BranchScopedMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self._enforce_branch_scope(request)

    def _enforce_branch_scope(self, request):
        if not request.user or not request.user.is_authenticated:
            return

        if get_parent_membership(request):
            request.branch = None
            request.org_membership = None
            return

        org = getattr(request, "org", None)
        if not org:
            return

        try:
            membership = OrganizationMember.objects.select_related("assigned_branch__organization").get(
                user=request.user,
                organization=org,
                is_active=True,
            )
        except OrganizationMember.DoesNotExist:
            return

        request.org_membership = membership
        role = membership.role

        if role in (OrganizationMember.ROLE_OWNER, OrganizationMember.ROLE_ADMIN):
            if request.branch and request.branch.organization_id != org.id:
                raise PermissionDenied("Branch does not belong to the current organization.")
            return

        if role == OrganizationMember.ROLE_STAFF:
            if not membership.assigned_branch:
                raise PermissionDenied(
                    "Your account has no branch assigned. Contact your organization owner to assign a branch."
                )

            if membership.assigned_branch.organization_id != org.id:
                raise PermissionDenied(
                    "Assigned branch does not belong to the current organization. Contact your organization owner."
                )

            request.branch = membership.assigned_branch

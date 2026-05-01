from rest_framework.permissions import BasePermission

from .models import OrganizationMember, ParentCompanyMember

ROLE_POLICY = {
    "items": {
        "list": {"OWNER", "ADMIN", "STAFF"},
        "retrieve": {"OWNER", "ADMIN", "STAFF"},
        "create": {"OWNER", "ADMIN"},
        "update": {"OWNER", "ADMIN"},
        "partial_update": {"OWNER", "ADMIN"},
        "destroy": {"OWNER", "ADMIN"},
    },
    "branches": {
        "list": {"OWNER", "ADMIN", "STAFF"},
        "retrieve": {"OWNER", "ADMIN", "STAFF"},
        "create": {"OWNER", "ADMIN"},
        "update": {"OWNER", "ADMIN"},
        "partial_update": {"OWNER", "ADMIN"},
        "destroy": {"OWNER", "ADMIN"},
    },
    "branch_items": {
        "list": {"OWNER", "ADMIN", "STAFF"},
        "retrieve": {"OWNER", "ADMIN", "STAFF"},
        "create": {"OWNER", "ADMIN"},
        "destroy": {"OWNER", "ADMIN"},
    },
    "stock_on_hand": {
        "list": {"OWNER", "ADMIN", "STAFF"},
        "retrieve": {"OWNER", "ADMIN", "STAFF"},
    },
    "movements": {
        "list": {"OWNER", "ADMIN", "STAFF"},
        "create": {"OWNER", "ADMIN", "STAFF"},
    },
    "stock_takes": {
        "list": {"OWNER", "ADMIN", "STAFF"},
        "retrieve": {"OWNER", "ADMIN", "STAFF"},
        "create": {"OWNER", "ADMIN"},
        "partial_update": {"OWNER", "ADMIN"},
        "start": {"OWNER", "ADMIN"},
        "submit": {"OWNER", "ADMIN"},
        "reopen": {"OWNER", "ADMIN"},
        "approve": {"OWNER", "ADMIN"},
        "cancel": {"OWNER", "ADMIN"},
        "lines": {"OWNER", "ADMIN", "STAFF"},
        "update_line": {"OWNER", "ADMIN", "STAFF"},
        "bulk_update_lines": {"OWNER", "ADMIN", "STAFF"},
    },
    "members": {
        "list": {"OWNER", "ADMIN"},
        "retrieve": {"OWNER", "ADMIN"},
        "create": {"OWNER"},
        "partial_update": {"OWNER"},
        "destroy": {"OWNER"},
    },
    "suppliers": {
        "list": {"OWNER", "ADMIN", "STAFF"},
        "retrieve": {"OWNER", "ADMIN", "STAFF"},
        "create": {"OWNER", "ADMIN"},
        "update": {"OWNER", "ADMIN"},
        "partial_update": {"OWNER", "ADMIN"},
        "deactivate": {"OWNER", "ADMIN"},
        "reactivate": {"OWNER", "ADMIN"},
        "list_contacts": {"OWNER", "ADMIN", "STAFF"},
        "add_contact": {"OWNER", "ADMIN"},
        "update_contact": {"OWNER", "ADMIN"},
        "deactivate_contact": {"OWNER", "ADMIN"},
        "reactivate_contact": {"OWNER", "ADMIN"},
        "delete_contact": {"OWNER", "ADMIN"},
        "set_primary_contact": {"OWNER", "ADMIN"},
    },
    "purchase_orders": {
        "list": {"OWNER", "ADMIN", "STAFF"},
        "retrieve": {"OWNER", "ADMIN", "STAFF"},
        "create": {"OWNER", "ADMIN"},
        "update": {"OWNER", "ADMIN"},
        "partial_update": {"OWNER", "ADMIN"},
        "destroy": {"OWNER", "ADMIN", "STAFF"},
        "submit": {"OWNER", "ADMIN"},
        "cancel": {"OWNER"},
        "lines": {"OWNER", "ADMIN", "STAFF"},
        "add_line": {"OWNER", "ADMIN"},
        "update_line": {"OWNER", "ADMIN"},
        "remove_line": {"OWNER", "ADMIN"},
    },
    "goods_receipts": {
        "list": {"OWNER", "ADMIN", "STAFF"},
        "retrieve": {"OWNER", "ADMIN", "STAFF"},
        "create": {"OWNER", "ADMIN", "STAFF"},
    },
    "branch_transfers": {
        "list": {"OWNER", "ADMIN", "STAFF"},
        "retrieve": {"OWNER", "ADMIN", "STAFF"},
        "create": {"OWNER", "ADMIN"},
        "approve": {"OWNER", "ADMIN"},
        "dispatch": {"OWNER", "ADMIN"},
        "receive": {"OWNER", "ADMIN", "STAFF"},
        "cancel": {"OWNER", "ADMIN"},
        "update": set(),
        "partial_update": set(),
        "destroy": set(),
    },
    "quick_sales": {
        "list": {"OWNER", "ADMIN", "STAFF"},
        "retrieve": {"OWNER", "ADMIN", "STAFF"},
        "create": {"OWNER", "ADMIN", "STAFF"},
        "void": {"OWNER", "ADMIN"},
    },
}


def get_parent_membership(request):
    if hasattr(request, "_cached_parent_membership"):
        return request._cached_parent_membership

    if not request.user or not request.user.is_authenticated:
        request._cached_parent_membership = None
        return None

    try:
        membership = ParentCompanyMember.objects.select_related("parent_company").get(
            user=request.user,
            is_active=True,
            parent_company__is_active=True,
        )
    except ParentCompanyMember.DoesNotExist:
        membership = None

    request._cached_parent_membership = membership
    return membership


def get_org_membership(request):
    """
    Returns the active OrganizationMember for request.user in request.org.
    Uses request-scoped caching.

    Returns None for:
    - parent users
    - unauthenticated users
    - requests without request.org

    Intended for viewsets that do NOT use BranchScopedMixin.
    """

    if hasattr(request, "_cached_org_membership"):
        return request._cached_org_membership

    if not request.user or not request.user.is_authenticated:
        request._cached_org_membership = None
        return None

    parent = get_parent_membership(request)
    if parent:
        request._cached_org_membership = None
        return None

    org = getattr(request, "org", None)
    if not org:
        request._cached_org_membership = None
        return None

    try:
        membership = OrganizationMember.objects.get(
            user=request.user,
            organization=org,
            is_active=True,
        )
    except OrganizationMember.DoesNotExist:
        membership = None

    request._cached_org_membership = membership
    return membership


def get_member_role(request):
    if not request.user or not request.user.is_authenticated:
        return None
    if not getattr(request, "org", None):
        return None

    cache_key = "_cached_member_role"
    if hasattr(request, cache_key):
        return getattr(request, cache_key)

    try:
        member = OrganizationMember.objects.get(
            user=request.user,
            organization=request.org,
            is_active=True,
        )
        role = member.role
    except OrganizationMember.DoesNotExist:
        role = None

    setattr(request, cache_key, role)
    return role


class IsOrgMember(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if not hasattr(request, "org") or request.org is None:
            return False

        return OrganizationMember.objects.filter(
            user=request.user,
            organization=request.org,
            is_active=True,
        ).exists()


class IsOrgMemberOrParent(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if not hasattr(request, "org") or request.org is None:
            return False

        parent = get_parent_membership(request)
        if parent and parent.parent_company_id == request.org.parent_company_id:
            return True

        return OrganizationMember.objects.filter(
            user=request.user,
            organization=request.org,
            is_active=True,
        ).exists()


class IsOrgOperationalUser(BasePermission):
    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

    def has_permission(self, request, view):
        if request.method in self.SAFE_METHODS:
            return True

        parent = get_parent_membership(request)
        if not parent:
            return True

        resource = getattr(view, "permission_resource", None)
        if (
            resource == "branches"
            and getattr(request, "org", None)
            and parent.parent_company_id == request.org.parent_company_id
            and parent.role == ParentCompanyMember.PARENT_ADMIN
        ):
            return True

        return False


class IsParentAdmin(BasePermission):
    def has_permission(self, request, view):
        parent = get_parent_membership(request)
        return bool(parent and parent.role == ParentCompanyMember.PARENT_ADMIN)


class IsParentMember(BasePermission):
    """
    Allows PARENT_ADMIN and PARENT_VIEWER.
    Blocks org members and unauthenticated users.
    Used for read-only parent-level endpoints accessible to all parent roles.
    """

    def has_permission(self, request, view):
        parent = get_parent_membership(request)
        return bool(parent and parent.is_active and parent.parent_company.is_active)


class IsOrgOwnerOrAdmin(BasePermission):
    """
    Allows OWNER and ADMIN org members only.
    Blocks STAFF, parent members, and unauthenticated users.
    Used for org-scoped endpoints that must exclude STAFF.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        role = get_member_role(request)
        return role in {"OWNER", "ADMIN"}


class IsOrgOwnerOrParentAdmin(BasePermission):
    """
    Allows org OWNER or PARENT_ADMIN.
    Used for operations (like period close/reopen) that must be
    restricted from ADMIN but accessible to platform admins.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        parent = get_parent_membership(request)
        if parent and parent.parent_company_id == request.org.parent_company_id:
            return parent.role == ParentCompanyMember.PARENT_ADMIN
        role = get_member_role(request)
        return role == "OWNER"


class IsOrgOwnerOrAdminOrParentAdmin(BasePermission):
    """
    Allows OWNER, ADMIN, and PARENT_ADMIN.
    Used for read-only close period operations (list, retrieve, snapshots)
    where ADMINs should have visibility but not the ability to mutate.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        parent = get_parent_membership(request)
        if parent and parent.parent_company_id == request.org.parent_company_id:
            return parent.role == ParentCompanyMember.PARENT_ADMIN
        role = get_member_role(request)
        return role in {"OWNER", "ADMIN"}


class RolePolicyPermission(BasePermission):
    def has_permission(self, request, view):
        resource = getattr(view, "permission_resource", None)
        action = getattr(view, "action", None)

        if not resource or not action:
            return True

        resource_policy = ROLE_POLICY.get(resource, {})
        allowed_roles = resource_policy.get(action)

        if allowed_roles is None:
            return False

        parent = get_parent_membership(request)
        if parent and parent.parent_company_id == request.org.parent_company_id:
            if resource == "branches" and parent.role == ParentCompanyMember.PARENT_ADMIN:
                return action in {"list", "retrieve", "create", "update", "partial_update"}
            return request.method in ("GET", "HEAD", "OPTIONS")

        role = get_member_role(request)
        return role in allowed_roles


class RolePolicyMixin:
    permission_resource = None

    def get_permissions(self):
        permissions = super().get_permissions()
        permissions.append(RolePolicyPermission())
        return permissions

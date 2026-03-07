from rest_framework.permissions import BasePermission

from .models import OrganizationMember


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
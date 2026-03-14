from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter

from .mixins import OrgScopedViewSetMixin
from .models import OrganizationMember
from .permissions import RolePolicyMixin
from .serializers import MemberCreateSerializer, MemberSerializer, MemberUpdateSerializer


@extend_schema_view(
    list=extend_schema(
        description=(
            "Requires ADMIN or OWNER role. Returns all members by default, "
            "including inactive members. Filter with ?is_active=true/false."
        )
    ),
    retrieve=extend_schema(description="Requires ADMIN or OWNER role."),
    create=extend_schema(
        description=(
            "Requires OWNER role. Links an existing user account to this org. "
            "Does not create new users."
        )
    ),
    partial_update=extend_schema(
        description=(
            "Requires OWNER role. Updates role and/or is_active, including "
            "reactivation via is_active=true."
        )
    ),
    destroy=extend_schema(
        description="Requires OWNER role. Soft deactivation only (is_active=false)."
    ),
)
class MemberViewSet(RolePolicyMixin, OrgScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = OrganizationMember.all_objects.none()
    permission_resource = "members"
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    filter_backends = [OrderingFilter]
    ordering_fields = ["role", "is_active"]
    ordering = ["role"]

    def get_queryset(self):
        qs = OrganizationMember.objects.for_org(self.request.org).select_related("user", "assigned_branch")
        is_active = self.request.query_params.get("is_active")
        if is_active is None:
            return qs
        return qs.filter(is_active=is_active.lower() == "true")

    def get_serializer_class(self):
        if self.action == "create":
            return MemberCreateSerializer
        if self.action == "partial_update":
            return MemberUpdateSerializer
        return MemberSerializer

    def perform_create(self, serializer):
        if getattr(self.request, "parent_role", None) == "PARENT_ADMIN":
            if serializer.validated_data.get("role") != OrganizationMember.ROLE_OWNER:
                raise PermissionDenied("Parent admin can only create OWNER memberships.")
        serializer.save(organization=self.request.org)

    def perform_destroy(self, instance):
        if getattr(self.request, "parent_role", None) == "PARENT_ADMIN" and instance.role != OrganizationMember.ROLE_OWNER:
            raise PermissionDenied("Parent admin can only manage OWNER memberships.")

        if instance.user == self.request.user:
            raise PermissionDenied("You cannot deactivate your own membership.")

        if instance.role == OrganizationMember.ROLE_OWNER:
            active_owner_count = OrganizationMember.objects.for_org(self.request.org).filter(
                role=OrganizationMember.ROLE_OWNER,
                is_active=True,
            ).count()
            if active_owner_count <= 1:
                raise PermissionDenied("You cannot deactivate the last active OWNER in this organization.")

        instance.is_active = False
        instance.save(update_fields=["is_active"])

    def perform_update(self, serializer):
        instance = self.get_object()
        new_role = serializer.validated_data.get("role", instance.role)
        new_is_active = serializer.validated_data.get("is_active", instance.is_active)

        if getattr(self.request, "parent_role", None) == "PARENT_ADMIN":
            if instance.role != OrganizationMember.ROLE_OWNER or new_role != OrganizationMember.ROLE_OWNER:
                raise PermissionDenied("Parent admin can only manage OWNER memberships.")

        if instance.user == self.request.user and not new_is_active:
            raise PermissionDenied("You cannot deactivate your own membership.")

        if (
            instance.user == self.request.user
            and instance.role == OrganizationMember.ROLE_OWNER
            and new_role != OrganizationMember.ROLE_OWNER
        ):
            raise PermissionDenied("You cannot remove your own OWNER role.")

        if instance.role == OrganizationMember.ROLE_OWNER and new_role != OrganizationMember.ROLE_OWNER:
            active_owner_count = OrganizationMember.objects.for_org(self.request.org).filter(
                role=OrganizationMember.ROLE_OWNER,
                is_active=True,
            ).count()
            if active_owner_count <= 1:
                raise PermissionDenied("You cannot demote the last active OWNER in this organization.")

        if instance.role == OrganizationMember.ROLE_OWNER and not new_is_active:
            active_owner_count = OrganizationMember.objects.for_org(self.request.org).filter(
                role=OrganizationMember.ROLE_OWNER,
                is_active=True,
            ).count()
            if active_owner_count <= 1:
                raise PermissionDenied("You cannot deactivate the last active OWNER in this organization.")

        serializer.save()

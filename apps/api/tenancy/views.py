from django.contrib.auth import get_user_model
from django_ratelimit.core import is_ratelimited
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import log_audit_event

from .mixins import OrgScopedViewSetMixin
from .models import Organization, OrganizationMember, ParentCompanyMember
from .permissions import IsOrgMemberOrParent, RolePolicyMixin, get_member_role, get_parent_membership
from .serializers import MemberCreateSerializer, MemberSerializer, MemberUpdateSerializer, UserSearchSerializer

User = get_user_model()


def _branch_display(branch):
    if branch is None:
        return None
    return {
        "id": str(branch.id),
        "code": branch.code,
        "name": branch.name,
    }


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

    def create(self, request, *args, **kwargs):
        if is_ratelimited(request, group="member_create", key="user", rate="10/m", method="POST", increment=True):
            return Response(
                {"detail": "Too many requests. Please wait before adding another member."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return super().create(request, *args, **kwargs)

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

        previous_active = instance.is_active
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        if previous_active != instance.is_active:
            log_audit_event(
                organization=self.request.org,
                actor_user=self.request.user,
                event_type="member.status.changed",
                resource_type="organization_member",
                resource_id=instance.id,
                summary="Member status changed",
                diff_json={"is_active": {"before": previous_active, "after": instance.is_active}},
                metadata_json={"user_id": str(instance.user_id), "role": instance.role},
            )

    def perform_update(self, serializer):
        instance = self.get_object()
        old_role = instance.role
        old_is_active = instance.is_active
        old_assigned_branch_id = instance.assigned_branch_id
        old_assigned_branch = instance.assigned_branch
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

        updated = serializer.save()

        if old_role != updated.role:
            log_audit_event(
                organization=self.request.org,
                actor_user=self.request.user,
                event_type="member.role.changed",
                resource_type="organization_member",
                resource_id=updated.id,
                summary="Member role changed",
                diff_json={"role": {"before": old_role, "after": updated.role}},
                metadata_json={"user_id": str(updated.user_id)},
            )

        if old_is_active != updated.is_active:
            log_audit_event(
                organization=self.request.org,
                actor_user=self.request.user,
                event_type="member.status.changed",
                resource_type="organization_member",
                resource_id=updated.id,
                summary="Member status changed",
                diff_json={"is_active": {"before": old_is_active, "after": updated.is_active}},
                metadata_json={"user_id": str(updated.user_id), "role": updated.role},
            )

        if old_assigned_branch_id != updated.assigned_branch_id:
            log_audit_event(
                organization=self.request.org,
                actor_user=self.request.user,
                event_type="member.branch.changed",
                resource_type="organization_member",
                resource_id=updated.id,
                summary="Member branch assignment changed",
                diff_json={
                    "assigned_branch": {
                        "before": str(old_assigned_branch_id) if old_assigned_branch_id else None,
                        "after": str(updated.assigned_branch_id) if updated.assigned_branch_id else None,
                    }
                },
                metadata_json={
                    "user_id": str(updated.user_id),
                    "branch_display": {
                        "before": _branch_display(old_assigned_branch),
                        "after": _branch_display(updated.assigned_branch),
                    },
                },
            )


class MemberSearchView(APIView):
    permission_classes = [IsAuthenticated, IsOrgMemberOrParent]

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
        if get_member_role(request) != OrganizationMember.ROLE_OWNER:
            raise PermissionDenied("You do not have permission to perform this action.")

        email = request.query_params.get("email", "").strip()
        if len(email) < 3:
            return Response([])

        users = User.objects.filter(email__iexact=email)

        active_member_user_ids = OrganizationMember.objects.filter(
            organization=request.org,
            is_active=True,
        ).values_list("user_id", flat=True)
        parent_member_user_ids = ParentCompanyMember.objects.values_list("user_id", flat=True)

        users = users.exclude(id__in=active_member_user_ids)
        users = users.exclude(id__in=parent_member_user_ids)

        serializer = UserSearchSerializer(users, many=True)
        return Response(serializer.data)

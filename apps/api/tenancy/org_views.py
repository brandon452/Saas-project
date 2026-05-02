from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import changed_field_diff, log_audit_event

from .models import Organization, OrganizationMember
from .permissions import IsOrgOwnerOrAdminOrParentAdmin, IsParentAdmin, get_parent_membership
from .serializers import OrganizationSerializer, OrganizationSettingsSerializer


class OrgCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["name", "slug", "is_active"]


class OrgGovernanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["name", "is_active"]

    def validate_is_active(self, value):
        if value:
            raise serializers.ValidationError("Org reactivation is not available through this endpoint.")
        return value


class OrgListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        parent = get_parent_membership(request)
        if parent:
            orgs = Organization.objects.filter(
                parent_company=parent.parent_company,
                is_active=True,
            ).order_by("name")
            return Response(OrganizationSerializer(orgs, many=True).data)

        org_ids = OrganizationMember.objects.filter(
            user=request.user,
            is_active=True,
        ).values_list("organization_id", flat=True)

        orgs = Organization.objects.filter(
            pk__in=org_ids,
            is_active=True,
        ).order_by("name")

        serializer = OrganizationSerializer(orgs, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not IsParentAdmin().has_permission(request, self):
            return Response({"detail": "You do not have permission to perform this action."}, status=403)

        serializer = OrgCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parent = get_parent_membership(request)
        org = serializer.save(parent_company=parent.parent_company)
        return Response(OrganizationSerializer(org).data, status=status.HTTP_201_CREATED)


class OrgGovernanceView(APIView):
    permission_classes = [IsAuthenticated, IsParentAdmin]

    def patch(self, request, org_id):
        try:
            parent = get_parent_membership(request)
            org = Organization.objects.get(pk=org_id, parent_company=parent.parent_company)
        except Organization.DoesNotExist:
            return Response({"detail": "Organization not found."}, status=404)

        serializer = OrgGovernanceSerializer(org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(OrganizationSerializer(updated).data)


class OrgSettingsView(APIView):
    permission_classes = [IsAuthenticated, IsOrgOwnerOrAdminOrParentAdmin]

    def initial(self, request, *args, **kwargs):
        self._resolve_org(request, kwargs.get("org_id"))
        super().initial(request, *args, **kwargs)

    def _resolve_org(self, request, org_id):
        try:
            request.org = Organization.objects.select_related("parent_company").get(
                pk=org_id,
                is_active=True,
            )
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")

    def get(self, request, org_id):
        serializer = OrganizationSettingsSerializer(request.org)
        return Response(serializer.data)

    def patch(self, request, org_id):
        audited_fields = [
            "name",
            "default_currency",
            "default_timezone",
            "allow_negative_stock",
            "purchase_order_prefix",
            "branch_transfer_approval_required",
            "stock_take_approval_required",
        ]
        before = {field: getattr(request.org, field) for field in audited_fields}
        serializer = OrganizationSettingsSerializer(request.org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        after = {field: getattr(updated, field) for field in audited_fields}
        diff = changed_field_diff(before, after, audited_fields)
        if diff:
            log_audit_event(
                organization=request.org,
                actor_user=request.user,
                event_type="org.settings.updated",
                resource_type="organization",
                resource_id=request.org.id,
                summary="Organization settings updated",
                diff_json=diff,
                metadata_json={},
            )
        return Response(OrganizationSettingsSerializer(updated).data)

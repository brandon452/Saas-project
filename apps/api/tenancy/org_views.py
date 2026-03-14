from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Organization, OrganizationMember
from .permissions import IsParentAdmin, get_parent_membership
from .serializers import OrganizationSerializer


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
            orgs = Organization.objects.filter(is_active=True).order_by("name")
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
        org = serializer.save()
        return Response(OrganizationSerializer(org).data, status=status.HTTP_201_CREATED)


class OrgGovernanceView(APIView):
    permission_classes = [IsAuthenticated, IsParentAdmin]

    def patch(self, request, org_id):
        try:
            org = Organization.objects.get(pk=org_id)
        except Organization.DoesNotExist:
            return Response({"detail": "Organization not found."}, status=404)

        serializer = OrgGovernanceSerializer(org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(OrganizationSerializer(updated).data)

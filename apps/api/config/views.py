from django.db import connection
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tenancy.models import OrganizationMember
from tenancy.serializers import OrganizationSerializer


class HealthView(APIView):
    permission_classes = []

    def get(self, request):
        db_status = "ok"
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            db_status = "down"

        org = getattr(request, "org", None)
        return Response(
            {
                "status": "ok",
                "organization": org.slug if org else None,
                "db": db_status,
            }
        )


class MyOrganizationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = OrganizationMember.objects.filter(
            user=request.user,
            is_active=True,
            organization__is_active=True,
        ).select_related("organization")
        organizations = [membership.organization for membership in memberships]
        data = OrganizationSerializer(organizations, many=True).data
        return Response(data)

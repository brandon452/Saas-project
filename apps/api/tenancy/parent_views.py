from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from .models import ParentCompanyMember
from .permissions import IsParentAdmin
from .serializers import ParentMemberCreateSerializer, ParentMemberSerializer, ParentMemberUpdateSerializer


class ParentMemberViewSet(viewsets.ModelViewSet):
    queryset = ParentCompanyMember.all_objects.none()
    permission_classes = [IsAuthenticated, IsParentAdmin]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return ParentCompanyMember.objects.select_related("user", "created_by")

    def get_serializer_class(self):
        if self.action == "create":
            return ParentMemberCreateSerializer
        if self.action == "partial_update":
            return ParentMemberUpdateSerializer
        return ParentMemberSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        if instance.user_id == self.request.user.id:
            raise PermissionDenied("You cannot deactivate your own parent membership.")
        instance.is_active = False
        instance.save(update_fields=["is_active"])

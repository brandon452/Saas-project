from rest_framework import viewsets

from tenancy.mixins import OrgScopedViewSetMixin

from .models import Branch
from .serializers import BranchSerializer


class BranchViewSet(OrgScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = BranchSerializer
    queryset = Branch.all_objects.none()

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)


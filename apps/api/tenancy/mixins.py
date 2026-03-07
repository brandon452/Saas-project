from rest_framework.permissions import IsAuthenticated

from .permissions import IsOrgMember


class OrgScopedViewSetMixin:
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get_queryset(self):
        base_queryset = super().get_queryset()
        return base_queryset.model.objects.for_org(self.request.org)


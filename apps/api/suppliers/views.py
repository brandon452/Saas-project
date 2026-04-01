from django.db import transaction
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from tenancy.mixins import OrgScopedViewSetMixin
from tenancy.permissions import RolePolicyMixin, get_org_membership, get_parent_membership

from .models import Supplier, SupplierContact
from .serializers import (
    SupplierContactSerializer,
    SupplierContactWriteSerializer,
    SupplierDeactivateSerializer,
    SupplierReactivateSerializer,
    SupplierSerializer,
    SupplierWriteSerializer,
)


class SupplierViewSet(
    RolePolicyMixin,
    OrgScopedViewSetMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    permission_resource = "suppliers"
    queryset = Supplier.all_objects.none()
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = Supplier.objects.for_org(self.request.org).prefetch_related("contacts")

        search = self.request.query_params.get("search", "").strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(display_name__icontains=search)
                | Q(legal_name__icontains=search)
                | Q(code__icontains=search)
            )

        is_active = self.request.query_params.get("is_active")

        parent = get_parent_membership(self.request)
        if parent:
            if is_active == "false":
                return qs.none()
            return qs.filter(is_active=True)

        membership = get_org_membership(self.request)
        role = membership.role if membership else None

        if role in ("OWNER", "ADMIN"):
            if is_active in ("true", "false"):
                qs = qs.filter(is_active=(is_active == "true"))
        else:
            if is_active == "false":
                return qs.none()
            qs = qs.filter(is_active=True)

        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return SupplierWriteSerializer
        if self.action == "deactivate":
            return SupplierDeactivateSerializer
        if self.action == "reactivate":
            return SupplierReactivateSerializer
        return SupplierSerializer

    def _generate_supplier_code(self, org):
        """Return the next available SUP-NNNN code for the org, race-safe."""
        import re
        with transaction.atomic():
            existing = (
                Supplier.objects.select_for_update()
                .filter(organization=org)
                .exclude(code="")
                .values_list("code", flat=True)
            )
            max_suffix = 0
            for code in existing:
                match = re.match(r"^SUP-(\d+)$", code)
                if match:
                    max_suffix = max(max_suffix, int(match.group(1)))
            return f"SUP-{max_suffix + 1:04d}"

    def perform_create(self, serializer):
        org = self.request.org
        serializer.save(
            organization=org,
            created_by=self.request.user,
            code=self._generate_supplier_code(org),
        )

    @action(detail=True, methods=["patch"], url_path="deactivate")
    def deactivate(self, request, *args, **kwargs):
        supplier = self.get_object()
        serializer = self.get_serializer(
            supplier,
            data={"is_active": False},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        supplier.contacts.filter(is_active=True).update(is_active=False)
        supplier.refresh_from_db()
        return Response(SupplierSerializer(supplier, context={"request": request}).data)

    @action(detail=True, methods=["patch"], url_path="reactivate")
    def reactivate(self, request, *args, **kwargs):
        supplier = self.get_object()
        serializer = self.get_serializer(
            supplier,
            data={"is_active": True},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        supplier.refresh_from_db()
        return Response(SupplierSerializer(supplier, context={"request": request}).data)

    # -------------------------------------------------------------------------
    # Contact sub-resource
    # -------------------------------------------------------------------------

    def _get_supplier_contacts_qs(self, supplier):
        """Return the active contact queryset for a supplier, respecting role."""
        membership = get_org_membership(self.request)
        role = membership.role if membership else None
        qs = supplier.contacts.all()
        if role not in ("OWNER", "ADMIN"):
            qs = qs.filter(is_active=True)
        return qs

    @action(detail=True, methods=["get"], url_path="contacts")
    def list_contacts(self, request, *args, **kwargs):
        supplier = self.get_object()
        contacts = self._get_supplier_contacts_qs(supplier)
        serializer = SupplierContactSerializer(contacts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="contacts/add")
    def add_contact(self, request, *args, **kwargs):
        supplier = self.get_object()
        serializer = SupplierContactWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        has_active_primary = supplier.contacts.filter(is_active=True, is_primary=True).exists()
        contact = serializer.save(supplier=supplier, is_primary=not has_active_primary)
        return Response(SupplierContactSerializer(contact).data, status=status.HTTP_201_CREATED)

    def _get_contact(self, supplier, contact_id):
        """Fetch a contact belonging to this supplier or raise 404."""
        from rest_framework.exceptions import NotFound
        try:
            return supplier.contacts.get(pk=contact_id)
        except SupplierContact.DoesNotExist:
            raise NotFound()

    @action(detail=True, methods=["patch"], url_path="contacts/(?P<contact_id>[0-9]+)")
    def update_contact(self, request, contact_id=None, *args, **kwargs):
        supplier = self.get_object()
        contact = self._get_contact(supplier, contact_id)
        serializer = SupplierContactWriteSerializer(contact, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(SupplierContactSerializer(contact).data)

    @action(detail=True, methods=["patch"], url_path="contacts/(?P<contact_id>[0-9]+)/deactivate")
    def deactivate_contact(self, request, contact_id=None, *args, **kwargs):
        supplier = self.get_object()
        contact = self._get_contact(supplier, contact_id)
        contact.is_active = False
        contact.save(update_fields=["is_active", "updated_at"])
        return Response(SupplierContactSerializer(contact).data)

    @action(detail=True, methods=["patch"], url_path="contacts/(?P<contact_id>[0-9]+)/reactivate")
    def reactivate_contact(self, request, contact_id=None, *args, **kwargs):
        supplier = self.get_object()
        contact = self._get_contact(supplier, contact_id)
        contact.is_active = True
        contact.save(update_fields=["is_active", "updated_at"])
        return Response(SupplierContactSerializer(contact).data)

    @action(detail=True, methods=["delete"], url_path="contacts/(?P<contact_id>[0-9]+)/delete")
    def delete_contact(self, request, contact_id=None, *args, **kwargs):
        supplier = self.get_object()
        contact = self._get_contact(supplier, contact_id)
        contact.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["patch"], url_path="contacts/(?P<contact_id>[0-9]+)/set-primary")
    def set_primary_contact(self, request, contact_id=None, *args, **kwargs):
        supplier = self.get_object()
        contact = self._get_contact(supplier, contact_id)

        with transaction.atomic():
            # Step 1: clear any existing active primary for this supplier.
            supplier.contacts.filter(is_primary=True, is_active=True).update(is_primary=False)
            # Step 2: set the target contact as active primary.
            contact.is_primary = True
            contact.is_active = True
            contact.save(update_fields=["is_primary", "is_active", "updated_at"])

        return Response(SupplierContactSerializer(contact).data)

from django.db import IntegrityError, transaction
from django_ratelimit.core import is_ratelimited
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from audit.services import changed_field_diff, log_audit_event
from exports.rows.suppliers import HEADERS, to_row
from exports.service import ExportConfig, ExportService
from tenancy.mixins import OrgScopedViewSetMixin
from tenancy.models import Organization
from tenancy.permissions import RolePolicyMixin, get_org_membership, get_parent_membership

from .models import Supplier, SupplierContact, SupplierItem
from .serializers import (
    SupplierContactSerializer,
    SupplierContactWriteSerializer,
    SupplierDeactivateSerializer,
    SupplierItemSerializer,
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
    SUPPLIER_AUDIT_FIELDS = [
        "display_name",
        "code",
        "legal_name",
        "email",
        "phone",
        "payment_terms_days",
        "default_lead_time_days",
        "currency",
        "tax_id",
        "address_line1",
        "address_line2",
        "city",
        "state",
        "postal_code",
        "country",
        "notes",
    ]
    permission_resource = "suppliers"
    queryset = Supplier.all_objects.none()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

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
            # Lock the org row so "first supplier in org" creation cannot race.
            Organization.objects.select_for_update().get(pk=org.pk)
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

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            raise DRFValidationError(
                {"detail": ["Could not allocate a unique supplier code. Please retry."]}
            )

    def perform_create(self, serializer):
        org = self.request.org
        supplier = serializer.save(
            organization=org,
            created_by=self.request.user,
            code=self._generate_supplier_code(org),
        )
        log_audit_event(
            organization=org,
            actor_user=self.request.user,
            event_type="supplier.created",
            resource_type="supplier",
            resource_id=supplier.id,
            summary=f"Created supplier {supplier.display_name}",
            metadata_json={
                "supplier_id": str(supplier.id),
                "display_name": supplier.display_name,
                "code": supplier.code,
            },
            diff_json=None,
        )

    def perform_update(self, serializer):
        before = {field: getattr(serializer.instance, field) for field in self.SUPPLIER_AUDIT_FIELDS}
        supplier = serializer.save()
        after = {field: getattr(supplier, field) for field in self.SUPPLIER_AUDIT_FIELDS}
        diff = changed_field_diff(before, after, self.SUPPLIER_AUDIT_FIELDS)
        if diff:
            log_audit_event(
                organization=self.request.org,
                actor_user=self.request.user,
                event_type="supplier.updated",
                resource_type="supplier",
                resource_id=supplier.id,
                summary=f"Updated supplier {supplier.display_name}",
                metadata_json={"supplier_id": str(supplier.id)},
                diff_json=diff,
            )

    @action(detail=False, methods=["get"], url_path="export/csv")
    def export_csv(self, request, *args, **kwargs):
        qs = self.get_queryset().order_by("display_name", "pk")
        config = ExportConfig(
            headers=HEADERS,
            filename_prefix="suppliers",
            rate_group="supplier_export_csv",
            audit_resource="supplier",
            filters_provider=lambda req: dict(req.query_params),
            require_ordering=True,
        )
        return ExportService.export_stream(
            request=request,
            queryset=qs,
            config=config,
            row_iter=(to_row(s) for s in qs.iterator(chunk_size=500)),
            organization=request.org,
            rate_limiter=is_ratelimited,
        )

    @action(detail=True, methods=["patch"], url_path="deactivate")
    def deactivate(self, request, *args, **kwargs):
        supplier = self.get_object()
        before_active = supplier.is_active
        serializer = self.get_serializer(
            supplier,
            data={"is_active": False},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        supplier.contacts.filter(is_active=True).update(is_active=False)
        supplier.refresh_from_db()
        log_audit_event(
            organization=request.org,
            actor_user=request.user,
            event_type="supplier.deactivated",
            resource_type="supplier",
            resource_id=supplier.id,
            summary=f"Deactivated supplier {supplier.display_name}",
            metadata_json={"supplier_id": str(supplier.id)},
            diff_json={"is_active": {"before": before_active, "after": supplier.is_active}},
        )
        return Response(SupplierSerializer(supplier, context={"request": request}).data)

    @action(detail=True, methods=["patch"], url_path="reactivate")
    def reactivate(self, request, *args, **kwargs):
        supplier = self.get_object()
        before_active = supplier.is_active
        serializer = self.get_serializer(
            supplier,
            data={"is_active": True},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        supplier.refresh_from_db()
        log_audit_event(
            organization=request.org,
            actor_user=request.user,
            event_type="supplier.reactivated",
            resource_type="supplier",
            resource_id=supplier.id,
            summary=f"Reactivated supplier {supplier.display_name}",
            metadata_json={"supplier_id": str(supplier.id)},
            diff_json={"is_active": {"before": before_active, "after": supplier.is_active}},
        )
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

    # -------------------------------------------------------------------------
    # Catalog (SupplierItem) sub-resource
    # -------------------------------------------------------------------------

    def _check_can_mutate_catalog(self, request):
        from rest_framework.exceptions import PermissionDenied
        from tenancy.models import ParentCompanyMember
        parent = get_parent_membership(request)
        if parent and parent.role == ParentCompanyMember.PARENT_ADMIN:
            return
        membership = get_org_membership(request)
        if not membership or membership.role not in ("OWNER", "ADMIN"):
            raise PermissionDenied("Only OWNER or ADMIN can manage the supplier catalog.")

    def _get_supplier_item(self, supplier, supplier_item_id):
        from rest_framework.exceptions import NotFound
        try:
            return SupplierItem.objects.get(pk=supplier_item_id, supplier=supplier, is_active=True)
        except SupplierItem.DoesNotExist:
            raise NotFound()

    @action(detail=True, methods=["get", "post"], url_path="items")
    def catalog_items(self, request, *args, **kwargs):
        supplier = self.get_object()

        if request.method == "GET":
            qs = SupplierItem.objects.filter(supplier=supplier, is_active=True).select_related(
                "org_item__master_item"
            )
            serializer = SupplierItemSerializer(
                qs, many=True, context={"request": request, "supplier": supplier}
            )
            return Response(serializer.data)

        # POST — add item to catalog
        self._check_can_mutate_catalog(request)
        serializer = SupplierItemSerializer(
            data=request.data, context={"request": request, "supplier": supplier}
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(organization=request.org)
        resp_status = (
            status.HTTP_200_OK if getattr(serializer, "_reactivated", False) else status.HTTP_201_CREATED
        )
        return Response(
            SupplierItemSerializer(instance, context={"request": request, "supplier": supplier}).data,
            status=resp_status,
        )

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"items/(?P<supplier_item_id>[0-9]+)",
    )
    def catalog_item_detail(self, request, supplier_item_id=None, *args, **kwargs):
        self._check_can_mutate_catalog(request)
        supplier = self.get_object()
        item = self._get_supplier_item(supplier, supplier_item_id)

        if request.method == "DELETE":
            item.is_active = False
            item.save(update_fields=["is_active", "updated_at"])
            return Response(status=status.HTTP_204_NO_CONTENT)

        # PATCH
        serializer = SupplierItemSerializer(
            item,
            data=request.data,
            partial=True,
            context={"request": request, "supplier": supplier},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            SupplierItemSerializer(item, context={"request": request, "supplier": supplier}).data
        )

from django.db import IntegrityError, transaction
from rest_framework import serializers

from inventory.models import OrgItem
from inventory.serializers import ItemSummarySerializer

from .models import Supplier, SupplierContact, SupplierItem


class SupplierContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierContact
        fields = [
            "id",
            "full_name",
            "role",
            "email",
            "phone",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SupplierContactWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierContact
        fields = ["full_name", "role", "email", "phone"]

    def validate_full_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Full name cannot be blank.")
        return value


class SupplierSerializer(serializers.ModelSerializer):
    # Phase 1: return both display_name and name alias so existing clients keep working.
    name = serializers.CharField(source="display_name", read_only=True)
    contacts = SupplierContactSerializer(many=True, read_only=True)

    class Meta:
        model = Supplier
        fields = [
            "id",
            "display_name",
            "name",  # Phase 1 alias — remove in Phase 3
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
            "is_active",
            "contacts",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "created_at", "updated_at"]


class SupplierWriteSerializer(serializers.ModelSerializer):
    # Phase 1: accept either `name` or `display_name`; both map to display_name.
    name = serializers.CharField(required=False, write_only=True)
    display_name = serializers.CharField(required=False)

    class Meta:
        model = Supplier
        fields = [
            "name",
            "display_name",
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

    def validate(self, attrs):
        if "is_active" in self.initial_data:
            raise serializers.ValidationError(
                {"is_active": "Use the deactivate or reactivate endpoint to change supplier status."}
            )

        name_val = attrs.pop("name", None)
        display_name_val = attrs.get("display_name", None)

        if name_val is not None and display_name_val is not None:
            if name_val.strip() != display_name_val.strip():
                raise serializers.ValidationError(
                    {"display_name": "Conflicting values for 'name' and 'display_name'. Provide only one."}
                )
            # Both provided and equal — use display_name as-is.
        elif name_val is not None:
            attrs["display_name"] = name_val

        final_name = attrs.get("display_name", "").strip()

        if not final_name:
            if not self.instance:
                raise serializers.ValidationError(
                    {"display_name": "A supplier name is required."}
                )
        else:
            # Uniqueness check runs here so it covers both the `name` and
            # `display_name` input paths.
            self._check_display_name_unique(final_name)

        return attrs

    def validate_display_name(self, value):
        return value.strip()

    def _check_display_name_unique(self, value):
        org = self.context["request"].org
        qs = Supplier.objects.for_org(org).filter(display_name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {"display_name": "A supplier with this name already exists in this organisation."}
            )


class SupplierItemSerializer(serializers.ModelSerializer):
    org_item = ItemSummarySerializer(read_only=True)
    org_item_id = serializers.PrimaryKeyRelatedField(
        queryset=OrgItem.objects.none(),
        source="org_item",
        write_only=True,
    )

    class Meta:
        model = SupplierItem
        fields = [
            "id",
            "org_item",
            "org_item_id",
            "is_preferred",
            "unit_cost",
            "lead_time_days",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "org_item", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request:
            self.fields["org_item_id"].queryset = OrgItem.objects.filter(
                organization=request.org
            )

    def create(self, validated_data):
        supplier = self.context["supplier"]
        org_item = validated_data["org_item"]

        # Reactivate soft-deleted row instead of inserting a duplicate
        existing = SupplierItem.all_objects.filter(
            supplier=supplier, org_item=org_item
        ).first()
        if existing and not existing.is_active:
            for field, value in validated_data.items():
                if field != "org_item":
                    setattr(existing, field, value)
            existing.is_active = True
            self._demote_preferred_if_needed(org_item, existing)
            existing.save()
            self.instance = existing
            self._reactivated = True
            return existing

        with transaction.atomic():
            self._demote_preferred_if_needed(org_item, None)
            try:
                return super().create({**validated_data, "supplier": supplier})
            except IntegrityError as exc:
                if "unique_preferred_supplier_per_item" in str(exc):
                    raise serializers.ValidationError(
                        {"is_preferred": "Another supplier is already preferred for this item."}
                    )
                raise

    def update(self, instance, validated_data):
        with transaction.atomic():
            self._demote_preferred_if_needed(instance.org_item, instance)
            try:
                return super().update(instance, validated_data)
            except IntegrityError as exc:
                if "unique_preferred_supplier_per_item" in str(exc):
                    raise serializers.ValidationError(
                        {"is_preferred": "Another supplier is already preferred for this item."}
                    )
                raise

    def _demote_preferred_if_needed(self, org_item, current_instance):
        if not self.validated_data.get("is_preferred", False):
            return
        qs = SupplierItem.objects.filter(org_item=org_item, is_preferred=True, is_active=True)
        if current_instance and current_instance.pk:
            qs = qs.exclude(pk=current_instance.pk)
        qs.update(is_preferred=False)


class SupplierDeactivateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["is_active"]

    def validate_is_active(self, value):
        if value is True:
            raise serializers.ValidationError(
                "Use the reactivate endpoint to reactivate a supplier."
            )
        return value


class SupplierReactivateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["is_active"]

    def validate_is_active(self, value):
        if value is False:
            raise serializers.ValidationError(
                "Use the deactivate endpoint to deactivate a supplier."
            )
        return value

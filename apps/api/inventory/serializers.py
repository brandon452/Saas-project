from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from branches.api import Branch, get_branch_for_org

from .models import (
    BranchItem,
    InventoryClosePeriod,
    InventoryCloseSnapshot,
    MasterItem,
    OrgItem,
    StockLedger,
    StockOnHand,
    StockTake,
    StockTakeLine,
)

User = get_user_model()


class BranchSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class ItemSummarySerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="master_item.sku", read_only=True)
    name = serializers.SerializerMethodField()

    class Meta:
        model = OrgItem
        fields = ["id", "name", "sku"]
        read_only_fields = ["id", "name", "sku"]

    def get_name(self, obj):
        return obj.display_name


class PerformedBySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]
        read_only_fields = ["id", "username"]


class MasterItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MasterItem
        fields = ["id", "name", "sku", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_sku(self, value):
        request = self.context.get("request")
        parent = getattr(request, "_cached_parent_membership", None) if request else None
        if parent is None and request:
            from tenancy.permissions import get_parent_membership

            parent = get_parent_membership(request)

        if parent is None:
            return value

        queryset = MasterItem.objects.filter(
            parent_company=parent.parent_company,
            sku=value,
        )
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Master item SKU already exists for this parent company.")
        return value


class OrgItemSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="master_item.sku", read_only=True)
    name = serializers.SerializerMethodField()
    name_override = serializers.CharField(source="name", read_only=True)  # raw override, blank if none set
    preferred_supplier = serializers.SerializerMethodField()

    class Meta:
        model = OrgItem
        fields = [
            "id",
            "organization",
            "master_item",
            "name",          # resolved display_name — read only
            "name_override", # raw override stored on OrgItem — blank string if no override
            "sku",
            "is_active",
            "created_at",
            "preferred_supplier",
        ]
        read_only_fields = ["id", "organization", "sku", "created_at", "name", "name_override", "preferred_supplier"]

    def get_name(self, obj):
        return obj.display_name

    def get_preferred_supplier(self, obj):
        # Relies on Prefetch(to_attr="active_supplier_items") set in OrgItemViewSet.get_queryset.
        # Falls back gracefully to None on retrieval paths without that prefetch (e.g. create).
        for si in getattr(obj, "active_supplier_items", []):
            if si.is_preferred:
                return {"id": si.supplier.id, "display_name": si.supplier.display_name}
        return None


class OrgItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgItem
        fields = ["master_item", "name"]

    def validate_master_item(self, value):
        if not value.is_active:
            raise serializers.ValidationError("Cannot activate an inactive master item.")
        request = self.context["request"]
        if value.parent_company_id != request.org.parent_company_id:
            raise serializers.ValidationError("Master item does not belong to this parent company.")
        return value

    def validate(self, attrs):
        request = self.context["request"]
        master_item = attrs.get("master_item")
        existing = OrgItem.objects.filter(
            organization=request.org,
            master_item=master_item,
        ).first()
        if existing and existing.is_active:
            raise serializers.ValidationError(
                {"master_item": "This item has already been activated for this organisation."}
            )
        self._existing_inactive = existing if (existing and not existing.is_active) else None
        return attrs

    def create(self, validated_data):
        existing = getattr(self, "_existing_inactive", None)
        if existing:
            existing.is_active = True
            fields_to_update = ["is_active"]
            if "name" in validated_data:
                existing.name = validated_data["name"]
                fields_to_update.append("name")
            existing.save(update_fields=fields_to_update)
            return existing
        return OrgItem.objects.create(**validated_data)


class OrgMasterItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MasterItem
        fields = ["id", "name", "sku", "is_active", "created_at"]
        read_only_fields = ["id", "name", "sku", "is_active", "created_at"]


class BranchItemBulkActivateSerializer(serializers.Serializer):
    branch = serializers.UUIDField()
    org_items = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=500,
    )

    def validate_branch(self, value):
        request = self.context["request"]
        try:
            return get_branch_for_org(branch_id=value, organization=request.org)
        except Branch.DoesNotExist:
            raise serializers.ValidationError(
                "Branch not found or does not belong to this organisation."
            )

    def validate_org_items(self, value):
        request = self.context["request"]
        unique_ids = list(dict.fromkeys(value))
        items = list(
            OrgItem.objects.filter(
                id__in=unique_ids,
                organization=request.org,
                is_active=True,
            )
        )
        found_ids = {item.id for item in items}
        missing = [str(uid) for uid in unique_ids if uid not in found_ids]
        if missing:
            raise serializers.ValidationError(
                f"Some items were not found or do not belong to this organisation: {', '.join(missing)}"
            )
        return items


class BranchItemBulkDeactivateSerializer(serializers.Serializer):
    branch = serializers.UUIDField()
    branch_items = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=500,
    )

    def validate_branch(self, value):
        request = self.context["request"]
        try:
            return get_branch_for_org(branch_id=value, organization=request.org)
        except Branch.DoesNotExist:
            raise serializers.ValidationError(
                "Branch not found or does not belong to this organisation."
            )

    def validate_branch_items(self, value):
        request = self.context["request"]
        # Dedupe preserving order — single source of truth for deduplication
        unique_ids = list(dict.fromkeys(value))
        # Only fetch active items; already-inactive ones are silently counted by the view
        items = list(
            BranchItem.objects.filter(
                id__in=unique_ids,
                branch__organization=request.org,
                is_active=True,
            )
        )
        # Validate all submitted IDs exist and belong to this org (active or not)
        all_items_in_org = set(
            BranchItem.objects.filter(
                id__in=unique_ids,
                branch__organization=request.org,
            ).values_list("id", flat=True)
        )
        missing = [str(uid) for uid in unique_ids if uid not in all_items_in_org]
        if missing:
            raise serializers.ValidationError(
                f"Some branch items were not found or do not belong to this organisation: {', '.join(missing)}"
            )
        # Store the deduplicated total so the view can compute already_inactive
        self._unique_ids_count = len(unique_ids)
        return items


class OrgItemBulkActivateSerializer(serializers.Serializer):
    master_items = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=500,
    )

    def validate_master_items(self, value):
        request = self.context["request"]
        unique_ids = list(dict.fromkeys(value))
        items = list(
            MasterItem.objects.filter(
                id__in=unique_ids,
                parent_company=request.org.parent_company,
                is_active=True,
            )
        )
        found_ids = {item.id for item in items}
        missing = [str(uid) for uid in unique_ids if uid not in found_ids]
        if missing:
            raise serializers.ValidationError(
                f"Some items were not found, inactive, or do not belong to this organisation: {', '.join(missing)}"
            )
        return items

    def validate(self, attrs):
        branch = attrs.get("branch")
        branch_items = attrs.get("branch_items", [])
        if branch:
            wrong_branch = [bi for bi in branch_items if bi.branch_id != branch.id]
            if wrong_branch:
                raise serializers.ValidationError(
                    {"branch_items": "Some branch items do not belong to the specified branch."}
                )
        return attrs


class BranchItemCatalogSerializer(serializers.Serializer):
    """
    OrgItem row for the branch catalog management page.

    active_branch_items is populated via prefetch_related in the view
    (unique_together guarantees at most one entry per branch+org_item pair).
    """

    id = serializers.UUIDField()
    name = serializers.SerializerMethodField()
    sku = serializers.CharField(source="master_item.sku")
    is_enabled = serializers.SerializerMethodField()
    branch_item_id = serializers.SerializerMethodField()
    item_class = serializers.SerializerMethodField()

    def _active_bi(self, obj):
        items = getattr(obj, "active_branch_items", [])
        return items[0] if items else None

    def get_name(self, obj):
        return obj.display_name

    def get_is_enabled(self, obj):
        return self._active_bi(obj) is not None

    def get_branch_item_id(self, obj):
        bi = self._active_bi(obj)
        return bi.id if bi else None

    def get_item_class(self, obj):
        bi = self._active_bi(obj)
        return bi.item_class if bi else None


class BranchItemSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="org_item.master_item.sku", read_only=True)
    name = serializers.SerializerMethodField()

    class Meta:
        model = BranchItem
        fields = [
            "id",
            "org_item",
            "branch",
            "name",
            "sku",
            "item_class",
            "next_cycle_count_date",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "name", "sku", "created_at"]

    def get_name(self, obj):
        return obj.org_item.display_name


class BranchItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchItem
        fields = ["org_item", "branch", "item_class", "next_cycle_count_date"]
        validators = []

    def validate_org_item(self, value):
        request = self.context["request"]
        if value.organization != request.org:
            raise serializers.ValidationError("Item does not belong to this organisation.")
        if not value.is_active:
            raise serializers.ValidationError("Cannot enable an inactive item at a branch.")
        return value

    def validate_branch(self, value):
        request = self.context["request"]
        if value.organization != request.org:
            raise serializers.ValidationError("Branch does not belong to this organisation.")
        return value


class StockOnHandSerializer(serializers.ModelSerializer):
    branch = BranchSummarySerializer(read_only=True)
    item = ItemSummarySerializer(read_only=True)

    class Meta:
        model = StockOnHand
        fields = ["id", "organization", "branch", "item", "quantity"]
        read_only_fields = ["id", "organization", "branch", "item", "quantity"]


class StockLedgerSerializer(serializers.ModelSerializer):
    branch = BranchSummarySerializer(read_only=True)
    item = ItemSummarySerializer(read_only=True)
    performed_by = PerformedBySerializer(read_only=True)

    class Meta:
        model = StockLedger
        fields = [
            "id",
            "organization",
            "branch",
            "item",
            "quantity",
            "movement_type",
            "reference_type",
            "reference_id",
            "reason",
            "performed_by",
            "occurred_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "branch",
            "item",
            "quantity",
            "movement_type",
            "reference_type",
            "reference_id",
            "reason",
            "performed_by",
            "occurred_at",
            "created_at",
        ]


class StockMovementSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=OrgItem.objects.none())
    quantity = serializers.DecimalField(max_digits=12, decimal_places=4)
    movement_type = serializers.ChoiceField(choices=["RECEIPT", "ISSUE", "ADJUSTMENT"])
    unit_cost = serializers.DecimalField(
        max_digits=12,
        decimal_places=4,
        required=False,
        allow_null=True,
        default=None,
    )
    reference_type = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    reference_id = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    occurred_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    idempotency_key = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and getattr(request, "org", None):
            self.fields["item"].queryset = OrgItem.objects.for_org(request.org).filter(is_active=True)

    def validate(self, data):
        request = self.context["request"]
        branch = getattr(request, "branch", None)

        if branch and branch.organization_id != request.org.id:
            raise serializers.ValidationError(
                {"branch": "Branch does not belong to the current organization."}
            )

        membership = getattr(request, "org_membership", None)
        if membership is None:
            raise serializers.ValidationError("Active membership not found for this organization.")

        if membership.role == "STAFF":
            if branch != membership.assigned_branch:
                raise serializers.ValidationError(
                    {"branch": "You can only post movements to your assigned branch."}
                )

        item = data.get("item")
        if item is not None and branch is not None:
            branch_item_enabled = BranchItem.objects.filter(
                org_item=item,
                branch=branch,
                is_active=True,
            ).exists()
            if not branch_item_enabled:
                raise serializers.ValidationError(
                    {"item": "This item is not enabled for the selected branch."}
                )

        unit_cost = data.get("unit_cost")
        if unit_cost is not None and unit_cost <= 0:
            raise serializers.ValidationError({"unit_cost": "unit_cost must be greater than zero."})

        return data


class StockTakeLineSerializer(serializers.ModelSerializer):
    variance_preview = serializers.SerializerMethodField()
    item_name = serializers.CharField(source="org_item.display_name", read_only=True)
    item_sku = serializers.CharField(source="org_item.master_item.sku", read_only=True)

    class Meta:
        model = StockTakeLine
        fields = [
            "id",
            "org_item",
            "item_name",
            "item_sku",
            "snapshot_quantity",
            "counted_quantity",
            "variance_preview",
        ]
        read_only_fields = [
            "id",
            "org_item",
            "item_name",
            "item_sku",
            "snapshot_quantity",
            "variance_preview",
        ]

    def get_variance_preview(self, obj):
        variance_preview = obj.variance_preview
        return str(variance_preview) if variance_preview is not None else None


class StockTakeLineUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockTakeLine
        fields = ["counted_quantity"]

    def validate_counted_quantity(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("counted_quantity cannot be negative.")
        return value

    def validate(self, attrs):
        stock_take = self.instance.stock_take
        if stock_take.status != StockTake.IN_PROGRESS:
            raise serializers.ValidationError(
                "Lines can only be edited while the stock take is In Progress."
            )
        return attrs


class StockTakeListSerializer(serializers.ModelSerializer):
    counted_lines_count = serializers.SerializerMethodField()
    total_lines_count = serializers.SerializerMethodField()
    created_by = PerformedBySerializer(read_only=True)
    started_by = PerformedBySerializer(read_only=True)
    submitted_by = PerformedBySerializer(read_only=True)
    approved_by = PerformedBySerializer(read_only=True)
    cancelled_by = PerformedBySerializer(read_only=True)
    reopened_by = PerformedBySerializer(read_only=True)

    class Meta:
        model = StockTake
        fields = [
            "id",
            "branch",
            "status",
            "stock_take_type",
            "cycle_item_class",
            "scheduled_for",
            "notes",
            "total_lines_count",
            "counted_lines_count",
            "created_by",
            "started_by",
            "submitted_by",
            "approved_by",
            "cancelled_by",
            "reopened_by",
            "started_at",
            "submitted_at",
            "approved_at",
            "cancelled_at",
            "reopened_at",
            "snapshot_taken_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "total_lines_count",
            "counted_lines_count",
            "created_by",
            "started_by",
            "submitted_by",
            "approved_by",
            "cancelled_by",
            "reopened_by",
            "started_at",
            "submitted_at",
            "approved_at",
            "cancelled_at",
            "reopened_at",
            "snapshot_taken_at",
            "created_at",
            "updated_at",
        ]

    def get_counted_lines_count(self, obj):
        if hasattr(obj, "counted_lines_count"):
            return obj.counted_lines_count
        return obj.lines.filter(counted_quantity__isnull=False).count()

    def get_total_lines_count(self, obj):
        if hasattr(obj, "total_lines_count"):
            return obj.total_lines_count
        return obj.lines.count()


class StockTakeDetailSerializer(serializers.ModelSerializer):
    lines = StockTakeLineSerializer(many=True, read_only=True)
    counted_lines_count = serializers.SerializerMethodField()
    total_lines_count = serializers.SerializerMethodField()
    created_by = PerformedBySerializer(read_only=True)
    started_by = PerformedBySerializer(read_only=True)
    submitted_by = PerformedBySerializer(read_only=True)
    approved_by = PerformedBySerializer(read_only=True)
    cancelled_by = PerformedBySerializer(read_only=True)
    reopened_by = PerformedBySerializer(read_only=True)

    class Meta:
        model = StockTake
        fields = [
            "id",
            "branch",
            "status",
            "stock_take_type",
            "cycle_item_class",
            "scheduled_for",
            "notes",
            "lines",
            "total_lines_count",
            "counted_lines_count",
            "created_by",
            "started_by",
            "submitted_by",
            "approved_by",
            "cancelled_by",
            "reopened_by",
            "started_at",
            "submitted_at",
            "approved_at",
            "cancelled_at",
            "reopened_at",
            "snapshot_taken_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "lines",
            "total_lines_count",
            "counted_lines_count",
            "created_by",
            "started_by",
            "submitted_by",
            "approved_by",
            "cancelled_by",
            "reopened_by",
            "started_at",
            "submitted_at",
            "approved_at",
            "cancelled_at",
            "reopened_at",
            "snapshot_taken_at",
            "created_at",
            "updated_at",
        ]

    def get_counted_lines_count(self, obj):
        if hasattr(obj, "counted_lines_count"):
            return obj.counted_lines_count
        return obj.lines.filter(counted_quantity__isnull=False).count()

    def get_total_lines_count(self, obj):
        if hasattr(obj, "total_lines_count"):
            return obj.total_lines_count
        return obj.lines.count()


class StockTakeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockTake
        fields = ["branch", "notes", "stock_take_type", "cycle_item_class", "scheduled_for"]

    def validate(self, attrs):
        stock_take_type = attrs.get("stock_take_type", StockTake.TYPE_FULL)
        cycle_item_class = attrs.get("cycle_item_class")
        scheduled_for = attrs.get("scheduled_for")
        if stock_take_type == StockTake.TYPE_FULL:
            if cycle_item_class is not None:
                raise serializers.ValidationError(
                    {"cycle_item_class": "cycle_item_class must be null for FULL stock takes."}
                )
            if scheduled_for is not None:
                raise serializers.ValidationError(
                    {"scheduled_for": "scheduled_for must be null for FULL stock takes."}
                )
        if stock_take_type == StockTake.TYPE_CYCLE:
            if not cycle_item_class:
                raise serializers.ValidationError(
                    {"cycle_item_class": "cycle_item_class is required for CYCLE stock takes."}
                )
            if scheduled_for is None:
                raise serializers.ValidationError(
                    {"scheduled_for": "scheduled_for is required for CYCLE stock takes."}
                )
        return attrs

    def validate_branch(self, value):
        request = self.context["request"]
        if value.organization != request.org:
            raise serializers.ValidationError("Branch does not belong to this organisation.")
        return value


class StockTakeGenerateCycleSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    cycle_item_class = serializers.ChoiceField(
        choices=[BranchItem.CLASS_A, BranchItem.CLASS_B, BranchItem.CLASS_C]
    )
    scheduled_for = serializers.DateField(required=False)

    def validate_branch_id(self, value):
        request = self.context["request"]
        try:
            branch = get_branch_for_org(branch_id=value, organization=request.org)
        except Branch.DoesNotExist:
            raise serializers.ValidationError(
                "Branch not found or does not belong to this organisation."
            )
        return branch


class StockTakeLineBulkUpdateItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    counted_quantity = serializers.DecimalField(
        max_digits=12, decimal_places=4, allow_null=True
    )

    def validate_counted_quantity(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("counted_quantity cannot be negative.")
        return value


class StockTakeLineBulkUpdateSerializer(serializers.Serializer):
    lines = StockTakeLineBulkUpdateItemSerializer(many=True)

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("This list may not be empty.")
        if len(value) > 1000:
            raise serializers.ValidationError(
                "Ensure this field has no more than 1000 elements."
            )
        return value


class InventoryCloseSnapshotSerializer(serializers.ModelSerializer):
    branch = BranchSummarySerializer(read_only=True)
    item   = ItemSummarySerializer(read_only=True)

    class Meta:
        model = InventoryCloseSnapshot
        fields = [
            "id", "branch", "item", "quantity_on_hand",
            "average_unit_cost", "latest_unit_cost",
            "average_valuation", "latest_valuation", "valuation_basis",
        ]


class InventoryClosePeriodSerializer(serializers.ModelSerializer):
    closed_by   = PerformedBySerializer(read_only=True)
    reopened_by = PerformedBySerializer(read_only=True)

    class Meta:
        model = InventoryClosePeriod
        fields = [
            "id", "start_date", "end_date", "status", "notes",
            "closed_at", "closed_by", "reopened_at", "reopened_by",
        ]
        read_only_fields = ["id", "status", "closed_at", "closed_by", "reopened_at", "reopened_by"]


class InventoryClosePeriodCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryClosePeriod
        fields = ["start_date", "end_date", "notes"]

    def validate(self, data):
        if data["start_date"] > data["end_date"]:
            raise serializers.ValidationError("start_date must be on or before end_date.")
        if data["end_date"] > timezone.now().date():
            raise serializers.ValidationError("end_date cannot be in the future.")
        org = self.context["request"].org
        overlap = InventoryClosePeriod.objects.filter(
            organization=org,
            start_date__lte=data["end_date"],
            end_date__gte=data["start_date"],
        ).first()
        if overlap:
            raise serializers.ValidationError(
                f"Period overlaps existing period {overlap.start_date}–{overlap.end_date}."
            )
        return data


class StockTakeNotesUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockTake
        fields = ["notes"]

    def to_internal_value(self, data):
        extra_fields = set(data.keys()) - {"notes"}
        if extra_fields:
            raise serializers.ValidationError({"detail": "Only the notes field may be updated."})
        return super().to_internal_value(data)

    def validate(self, attrs):
        if self.instance.status not in StockTake.EDITABLE_STATUSES:
            raise serializers.ValidationError(
                "Notes can only be edited in Draft or In Progress status."
            )
        return attrs

from rest_framework import serializers

from goods_receipts.serializers import POReceiptSummarySerializer
from inventory.models import BranchItem
from inventory.serializers import ItemSummarySerializer

from .models import PurchaseOrder, PurchaseOrderLine


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    item = ItemSummarySerializer(read_only=True)

    class Meta:
        model = PurchaseOrderLine
        fields = [
            "id",
            "item",
            "ordered_quantity",
            "unit_price",
            "received_quantity",
        ]
        read_only_fields = ["id", "item", "received_quantity"]


class PurchaseOrderLineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderLine
        fields = ["item", "ordered_quantity", "unit_price"]

    def validate_ordered_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Ordered quantity must be greater than zero.")
        return value

    def validate_unit_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Unit price must be greater than zero.")
        return value

    def validate_item(self, value):
        request = self.context["request"]
        if value.organization != request.org:
            raise serializers.ValidationError("Item does not belong to this organisation.")
        branch = getattr(request, "branch", None)
        if branch is not None:
            if not BranchItem.objects.filter(
                org_item=value,
                branch=branch,
                is_active=True,
            ).exists():
                raise serializers.ValidationError("Item is not enabled at this branch.")
        return value

    def validate(self, attrs):
        po = self.context["purchase_order"]
        item = attrs.get("item", getattr(self.instance, "item", None))

        if item:
            qs = po.lines.filter(item=item)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"item": "This item already exists on the purchase order."}
                )

        return attrs


class PurchaseOrderSerializer(serializers.ModelSerializer):
    lines = PurchaseOrderLineSerializer(many=True, read_only=True)
    receipts = POReceiptSummarySerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "po_number",
            "supplier",
            "branch",
            "status",
            "notes",
            "lines",
            "receipts",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "po_number",
            "status",
            "lines",
            "receipts",
            "created_by",
            "created_at",
            "updated_at",
        ]


class PurchaseOrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrder
        fields = ["supplier", "branch", "notes"]

    def validate_supplier(self, value):
        request = self.context["request"]
        if value.organization != request.org:
            raise serializers.ValidationError("Supplier does not belong to this organisation.")
        if not value.is_active:
            raise serializers.ValidationError("Supplier is inactive.")
        return value

    def validate_branch(self, value):
        request = self.context["request"]
        if value.organization != request.org:
            raise serializers.ValidationError("Branch does not belong to this organisation.")
        return value


class PurchaseOrderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrder
        fields = ["supplier", "branch", "notes"]

    def validate_supplier(self, value):
        request = self.context["request"]
        if value.organization != request.org:
            raise serializers.ValidationError("Supplier does not belong to this organisation.")
        if not value.is_active:
            raise serializers.ValidationError("Supplier is inactive.")
        return value

    def validate_branch(self, value):
        request = self.context["request"]
        if value.organization != request.org:
            raise serializers.ValidationError("Branch does not belong to this organisation.")
        return value

    def validate(self, attrs):
        if self.instance.status != PurchaseOrder.DRAFT:
            raise serializers.ValidationError("Only Draft purchase orders can be edited.")
        return attrs

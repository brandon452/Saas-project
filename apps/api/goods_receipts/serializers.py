from decimal import Decimal

from rest_framework import serializers

from inventory.models import Item
from suppliers.models import Supplier

from .models import GoodsReceipt, GoodsReceiptLine


class GoodsReceiptLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoodsReceiptLine
        fields = ["id", "po_line", "item", "quantity_received", "unit_cost"]
        read_only_fields = ["id"]


class GoodsReceiptLineWriteSerializer(serializers.ModelSerializer):
    unit_cost = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = GoodsReceiptLine
        fields = ["po_line", "quantity_received", "unit_cost"]

    def validate_quantity_received(self, value):
        if value <= 0:
            raise serializers.ValidationError("quantity_received must be greater than zero.")
        return value

    def validate_unit_cost(self, value):
        if value is not None and value <= Decimal("0"):
            raise serializers.ValidationError("unit_cost must be greater than zero.")
        return value

    def validate_po_line(self, value):
        remaining = value.ordered_quantity - value.received_quantity
        if remaining <= 0:
            raise serializers.ValidationError("This PO line has already been fully received.")
        return value


class GoodsReceiptSerializer(serializers.ModelSerializer):
    lines = GoodsReceiptLineSerializer(many=True, read_only=True)

    class Meta:
        model = GoodsReceipt
        fields = [
            "id",
            "receipt_type",
            "purchase_order",
            "branch",
            "supplier",
            "source_reference",
            "received_by",
            "received_at",
            "notes",
            "lines",
        ]
        read_only_fields = [
            "id",
            "received_by",
            "received_at",
            "lines",
        ]


class GoodsReceiptCreateSerializer(serializers.ModelSerializer):
    lines = GoodsReceiptLineWriteSerializer(many=True)

    class Meta:
        model = GoodsReceipt
        fields = ["purchase_order", "notes", "lines"]

    def validate_purchase_order(self, value):
        request = self.context["request"]

        if value.organization != request.org:
            raise serializers.ValidationError("Purchase order does not belong to this organisation.")
        if value.status not in (value.SUBMITTED, value.PARTIALLY_RECEIVED):
            raise serializers.ValidationError(
                f"Cannot receive against a purchase order with status {value.status}."
            )
        if not value.lines.exists():
            raise serializers.ValidationError("Cannot receive against a purchase order with no line items.")
        return value

    def validate(self, attrs):
        po = attrs.get("purchase_order")
        lines = attrs.get("lines", [])

        if not lines:
            raise serializers.ValidationError({"lines": "A goods receipt must have at least one line."})

        for line in lines:
            if line["po_line"].purchase_order_id != po.pk:
                raise serializers.ValidationError(
                    {"lines": "One or more PO lines do not belong to the referenced purchase order."}
                )

        po_line_ids = [line["po_line"].pk for line in lines]
        if len(po_line_ids) != len(set(po_line_ids)):
            raise serializers.ValidationError(
                {"lines": "Duplicate PO lines in the same receipt are not allowed."}
            )

        for line in lines:
            po_line = line["po_line"]
            remaining = po_line.ordered_quantity - po_line.received_quantity
            if line["quantity_received"] > remaining:
                raise serializers.ValidationError(
                    {
                        "lines": (
                            f"quantity_received ({line['quantity_received']}) exceeds "
                            f"remaining quantity ({remaining}) on PO line {po_line.pk}."
                        )
                    }
                )

        return attrs

    def create(self, validated_data):
        validated_data.pop("lines", [])
        return GoodsReceipt.objects.create(**validated_data)


class DirectReceiptLineWriteSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=Item.objects.all())
    quantity_received = serializers.IntegerField(min_value=1)
    unit_cost = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    def validate_unit_cost(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("unit_cost must be greater than zero.")
        return value

    def validate_item(self, value):
        request = self.context["request"]
        if value.organization != request.org:
            raise serializers.ValidationError("Item does not belong to this organisation.")
        return value


class DirectReceiptCreateSerializer(serializers.ModelSerializer):
    lines = DirectReceiptLineWriteSerializer(many=True)
    supplier = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = GoodsReceipt
        fields = ["branch", "supplier", "source_reference", "notes", "lines"]

    def validate_branch(self, value):
        request = self.context["request"]
        if value.organization != request.org:
            raise serializers.ValidationError("Branch does not belong to this organisation.")
        return value

    def validate_supplier(self, value):
        if value is None:
            return value
        request = self.context["request"]
        if value.organization != request.org:
            raise serializers.ValidationError("Supplier does not belong to this organisation.")
        if not value.is_active:
            raise serializers.ValidationError("Supplier is inactive.")
        return value

    def validate(self, attrs):
        lines = attrs.get("lines", [])

        if not lines:
            raise serializers.ValidationError({"lines": "A goods receipt must have at least one line."})

        item_ids = [line["item"].pk for line in lines]
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError(
                {"lines": "Duplicate items in the same receipt are not allowed."}
            )

        return attrs

    def create(self, validated_data):
        validated_data.pop("lines", [])
        return GoodsReceipt.objects.create(**validated_data)

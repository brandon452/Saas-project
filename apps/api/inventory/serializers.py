from rest_framework import serializers

from .models import Item, StockLedger, StockOnHand


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "name", "sku", "is_active", "organization"]
        read_only_fields = ["organization"]


class StockOnHandSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockOnHand
        fields = ["id", "organization", "branch", "item", "quantity"]
        read_only_fields = ["organization"]


class StockLedgerSerializer(serializers.ModelSerializer):
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
            "idempotency_key",
            "created_at",
        ]
        read_only_fields = ["organization", "branch", "performed_by", "created_at"]


class StockMovementSerializer(serializers.Serializer):
    item = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=4)
    movement_type = serializers.ChoiceField(choices=["RECEIPT", "ISSUE", "ADJUSTMENT"])
    reference_type = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)
    reference_id = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    occurred_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    idempotency_key = serializers.CharField(max_length=255, required=False, allow_null=True, default=None)
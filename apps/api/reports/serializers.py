from rest_framework import serializers


class StockValuationSummarySerializer(serializers.Serializer):
    total_latest_valuation = serializers.DecimalField(
        max_digits=20, decimal_places=2, allow_null=True
    )
    total_average_valuation = serializers.DecimalField(
        max_digits=20, decimal_places=2, allow_null=True
    )
    item_count = serializers.IntegerField()
    branch_count = serializers.IntegerField()


class StockValuationRowSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    item_name = serializers.CharField()
    item_sku = serializers.CharField()
    branch_id = serializers.UUIDField()
    branch_name = serializers.CharField()
    quantity_on_hand = serializers.DecimalField(max_digits=12, decimal_places=4)
    latest_unit_cost = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True
    )
    latest_valuation = serializers.DecimalField(
        max_digits=20, decimal_places=2, allow_null=True
    )
    average_unit_cost = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True
    )
    average_valuation = serializers.DecimalField(
        max_digits=20, decimal_places=2, allow_null=True
    )


class CostTrendPointSerializer(serializers.Serializer):
    """
    One purchase cost trend point.
    Each point represents one goods receipt line with a non-null unit cost.
    """

    date = serializers.DateTimeField()
    unit_cost = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity_received = serializers.IntegerField()
    supplier_id = serializers.UUIDField(allow_null=True)
    supplier_name = serializers.CharField(allow_null=True)
    branch_id = serializers.UUIDField()
    branch_name = serializers.CharField()
    receipt_id = serializers.UUIDField()
    receipt_type = serializers.CharField()

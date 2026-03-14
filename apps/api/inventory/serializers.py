from django.contrib.auth import get_user_model
from rest_framework import serializers

from branches.models import Branch

from .models import Item, StockLedger, StockOnHand

User = get_user_model()


class BranchSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class ItemSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "name", "sku"]
        read_only_fields = ["id", "name", "sku"]


class PerformedBySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]
        read_only_fields = ["id", "username"]


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "organization", "name", "sku", "is_active", "created_at"]
        read_only_fields = ["id", "organization", "created_at"]


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
    item = serializers.PrimaryKeyRelatedField(queryset=Item.objects.none())
    quantity = serializers.DecimalField(max_digits=12, decimal_places=4)
    movement_type = serializers.ChoiceField(choices=["RECEIPT", "ISSUE", "ADJUSTMENT"])
    reference_type = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    reference_id = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    occurred_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    idempotency_key = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and getattr(request, "org", None):
            self.fields["item"].queryset = Item.objects.for_org(request.org)

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

        return data

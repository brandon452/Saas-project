from decimal import Decimal

from rest_framework import serializers
from django.utils import timezone

from branches.models import Branch
from inventory.models import BranchItem, OrgItem
from inventory.serializers import (
    BranchSummarySerializer,
    ItemSummarySerializer,
    PerformedBySerializer,
)
from tenancy.permissions import get_org_membership

from .models import QuickSale, QuickSaleLine


class QuickSaleLineWriteSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=OrgItem.objects.none())
    quantity = serializers.DecimalField(max_digits=12, decimal_places=4, min_value=Decimal("0.0001"))
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=4, min_value=Decimal("0"))


class QuickSaleCreateSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.none())
    customer_name = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    occurred_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None, max_length=255)
    lines = QuickSaleLineWriteSerializer(many=True, allow_empty=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request, "org"):
            org = request.org
            self.fields["branch"].queryset = Branch.objects.filter(organization=org)
            item_qs = OrgItem.objects.for_org(org).filter(is_active=True)
            self.fields["lines"].child.fields["item"].queryset = item_qs

    def validate(self, data):
        request = self.context.get("request")
        if not request:
            return data

        branch = data.get("branch")
        occurred_at = data.get("occurred_at")
        if branch and branch.organization_id != request.org.id:
            raise serializers.ValidationError(
                {"branch": "Branch does not belong to this organisation."}
            )

        if occurred_at and occurred_at > timezone.now():
            raise serializers.ValidationError(
                {"occurred_at": "Sale date and time cannot be in the future."}
            )

        membership = get_org_membership(request)
        if membership and membership.role == "STAFF" and membership.assigned_branch_id:
            if str(branch.id) != str(membership.assigned_branch_id):
                raise serializers.ValidationError(
                    {"branch": "You can only record sales for your assigned branch."}
                )

        for index, line in enumerate(data.get("lines", [])):
            item = line["item"]
            if not BranchItem.objects.filter(
                branch=branch,
                org_item=item,
                is_active=True,
            ).exists():
                raise serializers.ValidationError(
                    {f"lines[{index}].item": f"{item.display_name} is not enabled for this branch."}
                )

        return data


class QuickSaleLineSerializer(serializers.ModelSerializer):
    item = ItemSummarySerializer(read_only=True)

    class Meta:
        model = QuickSaleLine
        fields = ["id", "item", "quantity", "unit_price", "unit_cost"]


class QuickSaleSerializer(serializers.ModelSerializer):
    branch = BranchSummarySerializer(read_only=True)
    sold_by = PerformedBySerializer(read_only=True)
    voided_by = PerformedBySerializer(read_only=True)
    lines = QuickSaleLineSerializer(many=True, read_only=True)
    total_value = serializers.SerializerMethodField()

    class Meta:
        model = QuickSale
        fields = [
            "id",
            "branch",
            "customer_name",
            "notes",
            "sold_by",
            "sold_at",
            "occurred_at",
            "status",
            "voided_by",
            "voided_at",
            "total_value",
            "lines",
        ]

    def get_total_value(self, obj):
        total = sum((line.quantity * line.unit_price for line in obj.lines.all()), Decimal("0"))
        return str(total.quantize(Decimal("0.0001")))

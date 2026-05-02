from rest_framework import serializers

from inventory.models import BranchItem
from inventory.serializers import ItemSummarySerializer, PerformedBySerializer
from .models import BranchTransfer, BranchTransferLine


class BranchTransferLineSerializer(serializers.ModelSerializer):
    item = ItemSummarySerializer(read_only=True)

    class Meta:
        model = BranchTransferLine
        fields = ["id", "item", "quantity_sent", "quantity_received"]
        read_only_fields = ["id", "item", "quantity_received"]


class BranchTransferLineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchTransferLine
        fields = ["item", "quantity_sent"]

    def validate_quantity_sent(self, value):
        if value <= 0:
            raise serializers.ValidationError("quantity_sent must be greater than zero.")
        return value

    def validate_item(self, value):
        request = self.context["request"]
        if value.organization != request.org:
            raise serializers.ValidationError("Item does not belong to the sending organisation.")
        from_branch = self.context.get("from_branch")
        branch = from_branch
        if branch is not None:
            if not BranchItem.objects.filter(
                org_item=value,
                branch=branch,
                is_active=True,
            ).exists():
                raise serializers.ValidationError("Item is not enabled at the sending branch.")
        return value


class BranchTransferReceiveLineSerializer(serializers.Serializer):
    line_id = serializers.IntegerField()
    quantity_received = serializers.IntegerField(min_value=0)


class BranchTransferSerializer(serializers.ModelSerializer):
    lines = BranchTransferLineSerializer(many=True, read_only=True)
    created_by = PerformedBySerializer(read_only=True)
    approved_by = PerformedBySerializer(read_only=True)
    dispatched_by = PerformedBySerializer(read_only=True)
    received_by = PerformedBySerializer(read_only=True)

    class Meta:
        model = BranchTransfer
        fields = [
            "id",
            "organization",
            "from_branch",
            "to_branch",
            "to_organization",
            "status",
            "notes",
            "receive_notes",
            "lines",
            "created_by",
            "approved_by",
            "dispatched_by",
            "dispatched_at",
            "received_by",
            "received_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "to_organization",
            "status",
            "lines",
            "created_by",
            "approved_by",
            "dispatched_by",
            "dispatched_at",
            "received_by",
            "received_at",
            "created_at",
            "updated_at",
        ]


class BranchTransferCreateSerializer(serializers.ModelSerializer):
    lines = BranchTransferLineWriteSerializer(many=True)

    class Meta:
        model = BranchTransfer
        fields = ["from_branch", "to_branch", "notes", "lines"]

    def validate_from_branch(self, value):
        request = self.context["request"]
        if value.organization != request.org:
            raise serializers.ValidationError("from_branch does not belong to this organisation.")
        return value

    def validate_to_branch(self, value):
        request = self.context["request"]
        sending_org = request.org
        receiving_org = value.organization

        if not self._orgs_share_parent(sending_org, receiving_org):
            raise serializers.ValidationError(
                "to_branch must belong to an organisation under the same parent company."
            )
        return value

    def _orgs_share_parent(self, org_a, org_b):
        if org_a == org_b:
            return True
        return (
            org_a.is_active
            and org_b.is_active
            and org_a.parent_company_id == org_b.parent_company_id
        )

    def validate(self, attrs):
        from_branch = attrs.get("from_branch")
        if from_branch == attrs.get("to_branch"):
            raise serializers.ValidationError("from_branch and to_branch must be different.")

        lines = attrs.get("lines", [])
        if not lines:
            raise serializers.ValidationError({"lines": "A transfer must have at least one line."})

        item_ids = [line["item"].pk for line in lines]
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError(
                {"lines": "Duplicate items in the same transfer are not allowed."}
            )

        for line in lines:
            if not BranchItem.objects.filter(
                org_item=line["item"],
                branch=from_branch,
                is_active=True,
            ).exists():
                raise serializers.ValidationError(
                    {"lines": f"Item {line['item'].pk} is not enabled at the sending branch."}
                )

        return attrs

    def create(self, validated_data):
        validated_data.pop("lines", [])
        return BranchTransfer.objects.create(**validated_data)


class BranchTransferReceiveSerializer(serializers.Serializer):
    lines = BranchTransferReceiveLineSerializer(many=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("At least one line must be provided.")
        line_ids = [line["line_id"] for line in value]
        if len(line_ids) != len(set(line_ids)):
            raise serializers.ValidationError("Duplicate line IDs in receive payload are not allowed.")
        return value

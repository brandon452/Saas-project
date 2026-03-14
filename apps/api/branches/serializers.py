from rest_framework import serializers

from .models import Branch


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "code", "organization"]
        read_only_fields = ["organization"]


class NetworkBranchSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    org_id = serializers.UUIDField(source="organization_id")
    org_name = serializers.CharField(source="organization.name")

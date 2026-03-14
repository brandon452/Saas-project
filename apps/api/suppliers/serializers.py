from rest_framework import serializers

from .models import Supplier


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id",
            "name",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


class SupplierWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["name"]

    def validate(self, attrs):
        if "is_active" in self.initial_data:
            raise serializers.ValidationError(
                {"is_active": "Reactivation is not permitted via API."}
            )
        return attrs

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError("Name cannot be blank.")

        org = self.context["request"].org
        qs = Supplier.objects.for_org(org).filter(name__iexact=value)

        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                "A supplier with this name already exists in this organisation."
            )

        return value


class SupplierDeactivateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["is_active"]

    def validate_is_active(self, value):
        if value is True:
            raise serializers.ValidationError(
                "Use this endpoint to deactivate only. Reactivation is not permitted via API."
            )
        return value

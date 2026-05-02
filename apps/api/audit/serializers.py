from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import AuditEvent

User = get_user_model()


class AuditActorSerializer(serializers.Serializer):
    id = serializers.CharField(allow_null=True)
    type = serializers.CharField()
    email = serializers.CharField(allow_blank=True)
    name = serializers.CharField(allow_blank=True)


class AuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "occurred_at",
            "event_type",
            "resource_type",
            "resource_id",
            "summary",
            "metadata_json",
            "diff_json",
            "actor",
        ]

    def get_actor(self, obj: AuditEvent):
        return {
            "id": str(obj.actor_user_id) if obj.actor_user_id else None,
            "type": obj.actor_type,
            "email": obj.actor_email_snapshot or "",
            "name": obj.actor_name_snapshot or "",
        }

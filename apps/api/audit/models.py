import uuid

from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    ACTOR_TYPE_USER = "user"
    ACTOR_TYPE_SYSTEM = "system"
    ACTOR_TYPE_CHOICES = [
        (ACTOR_TYPE_USER, "User"),
        (ACTOR_TYPE_SYSTEM, "System"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "tenancy.Organization",
        on_delete=models.CASCADE,
        related_name="audit_events",
    )
    occurred_at = models.DateTimeField(auto_now_add=True)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    actor_type = models.CharField(max_length=10, choices=ACTOR_TYPE_CHOICES, default=ACTOR_TYPE_USER)
    actor_email_snapshot = models.CharField(max_length=255, blank=True, default="")
    actor_name_snapshot = models.CharField(max_length=255, blank=True, default="")
    event_type = models.CharField(max_length=64)
    resource_type = models.CharField(max_length=64)
    resource_id = models.CharField(max_length=64)
    summary = models.CharField(max_length=255)
    metadata_json = models.JSONField(default=dict, blank=True)
    diff_json = models.JSONField(default=dict, blank=True, null=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["organization", "-occurred_at"], name="audit_org_occ_idx"),
            models.Index(fields=["organization", "event_type", "-occurred_at"], name="audit_org_evt_occ_idx"),
            models.Index(
                fields=["organization", "resource_type", "resource_id", "-occurred_at"],
                name="audit_org_res_occ_idx",
            ),
        ]

    def __str__(self):
        return f"{self.organization_id}:{self.event_type}:{self.resource_type}:{self.resource_id}"

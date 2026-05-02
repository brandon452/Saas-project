from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "organization", "event_type", "resource_type", "resource_id", "actor_type")
    search_fields = ("event_type", "resource_type", "resource_id", "summary", "actor_email_snapshot")
    list_filter = ("event_type", "resource_type", "actor_type")

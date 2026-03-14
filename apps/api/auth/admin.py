from django.contrib import admin

from .models import AuthAuditLog


@admin.register(AuthAuditLog)
class AuthAuditLogAdmin(admin.ModelAdmin):
    list_display = ("event", "username", "ip_address", "occurred_at")
    list_filter = ("event", "occurred_at")
    search_fields = ("username", "ip_address", "reason")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

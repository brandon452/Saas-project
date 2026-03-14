from django.contrib import admin

from .models import Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "is_active", "created_at"]
    list_filter = ["is_active", "organization"]
    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at", "created_by"]

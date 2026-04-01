from django.contrib import admin

from .models import Supplier, SupplierContact


class SupplierContactInline(admin.TabularInline):
    model = SupplierContact
    extra = 0
    readonly_fields = ["created_at", "updated_at"]
    fields = ["full_name", "role", "email", "phone", "is_primary", "is_active", "created_at", "updated_at"]


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["display_name", "code", "organization", "is_active", "created_at"]
    list_filter = ["is_active", "organization"]
    search_fields = ["display_name", "code", "legal_name"]
    readonly_fields = ["code", "created_at", "updated_at", "created_by"]
    inlines = [SupplierContactInline]
    fieldsets = [
        (None, {
            "fields": ["display_name", "code", "legal_name", "is_active", "organization", "created_by"],
        }),
        ("Contact details", {
            "fields": ["email", "phone"],
        }),
        ("Purchasing", {
            "fields": ["payment_terms_days", "default_lead_time_days", "currency", "tax_id"],
        }),
        ("Address", {
            "fields": ["address_line1", "address_line2", "city", "state", "postal_code", "country"],
            "classes": ["collapse"],
        }),
        ("Notes", {
            "fields": ["notes"],
        }),
        ("Audit", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

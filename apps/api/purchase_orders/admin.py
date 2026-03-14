from django.contrib import admin

from .models import PurchaseOrder, PurchaseOrderLine


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0
    readonly_fields = ["received_quantity"]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = [
        "po_number",
        "organization",
        "supplier",
        "branch",
        "status",
        "created_at",
    ]
    list_filter = ["status", "organization"]
    search_fields = ["po_number", "supplier__name"]
    readonly_fields = ["po_number", "created_at", "updated_at", "created_by"]
    inlines = [PurchaseOrderLineInline]

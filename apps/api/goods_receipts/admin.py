from django.contrib import admin

from .models import GoodsReceipt, GoodsReceiptLine


class GoodsReceiptLineInline(admin.TabularInline):
    model = GoodsReceiptLine
    extra = 0
    readonly_fields = ["po_line", "quantity_received"]


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "organization",
        "purchase_order",
        "received_by",
        "received_at",
    ]
    list_filter = ["organization"]
    search_fields = ["purchase_order__po_number"]
    readonly_fields = ["purchase_order", "received_by", "received_at"]
    inlines = [GoodsReceiptLineInline]

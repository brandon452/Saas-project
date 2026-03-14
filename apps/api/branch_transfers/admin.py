from django.contrib import admin

from .models import BranchTransfer, BranchTransferLine


class BranchTransferLineInline(admin.TabularInline):
    model = BranchTransferLine
    extra = 0
    readonly_fields = ["item", "quantity_sent", "quantity_received"]


@admin.register(BranchTransfer)
class BranchTransferAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "organization",
        "from_branch",
        "to_branch",
        "to_organization",
        "status",
        "created_at",
    ]
    list_filter = ["status", "organization"]
    search_fields = ["id", "from_branch__name", "to_branch__name"]
    readonly_fields = [
        "organization",
        "to_organization",
        "created_by",
        "approved_by",
        "received_by",
        "dispatched_at",
        "received_at",
        "receive_notes",
        "created_at",
        "updated_at",
    ]
    inlines = [BranchTransferLineInline]

import uuid

from django.conf import settings
from django.db import models

from tenancy.models import TenantModel


class GoodsReceipt(TenantModel):
    PO_RECEIPT = "PO_RECEIPT"
    DIRECT_RECEIPT = "DIRECT_RECEIPT"

    RECEIPT_TYPE_CHOICES = [
        (PO_RECEIPT, "PO Receipt"),
        (DIRECT_RECEIPT, "Direct Receipt"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_type = models.CharField(
        max_length=20,
        choices=RECEIPT_TYPE_CHOICES,
        default=PO_RECEIPT,
    )
    purchase_order = models.ForeignKey(
        "purchase_orders.PurchaseOrder",
        on_delete=models.PROTECT,
        related_name="receipts",
        null=True,
        blank=True,
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    supplier = models.ForeignKey(
        "suppliers.Supplier",
        on_delete=models.PROTECT,
        related_name="goods_receipts",
        null=True,
        blank=True,
    )
    source_reference = models.TextField(blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="goods_receipts",
    )
    received_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        if self.purchase_order_id:
            return f"PO Receipt {self.purchase_order.po_number} at {self.received_at:%Y-%m-%d}"
        return f"Direct Receipt {self.id} at {self.received_at:%Y-%m-%d}"


class GoodsReceiptLine(models.Model):
    receipt = models.ForeignKey(
        GoodsReceipt,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    po_line = models.ForeignKey(
        "purchase_orders.PurchaseOrderLine",
        on_delete=models.PROTECT,
        related_name="receipt_lines",
        null=True,
        blank=True,
    )
    item = models.ForeignKey(
        "inventory.OrgItem",
        on_delete=models.PROTECT,
        related_name="direct_receipt_lines",
        null=True,
        blank=True,
    )
    quantity_received = models.PositiveIntegerField()
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["receipt", "po_line"],
                name="unique_po_line_per_receipt",
                condition=models.Q(po_line__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["receipt", "item"],
                name="unique_item_per_direct_receipt",
                condition=models.Q(item__isnull=False),
            ),
            models.CheckConstraint(
                check=(
                    (models.Q(po_line__isnull=False) & models.Q(item__isnull=True))
                    | (models.Q(po_line__isnull=True) & models.Q(item__isnull=False))
                ),
                name="goods_receipt_line_exactly_one_source",
            )
        ]

    def __str__(self):
        if self.po_line_id:
            return f"{self.receipt} - PO line {self.po_line_id} - qty {self.quantity_received}"
        return f"{self.receipt} - item {self.item_id} - qty {self.quantity_received}"

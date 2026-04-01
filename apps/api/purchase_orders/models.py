import uuid

from django.conf import settings
from django.db import models

from tenancy.models import TenantModel


class PurchaseOrder(TenantModel):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    FULLY_RECEIVED = "FULLY_RECEIVED"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (SUBMITTED, "Submitted"),
        (PARTIALLY_RECEIVED, "Partially Received"),
        (FULLY_RECEIVED, "Fully Received"),
        (CANCELLED, "Cancelled"),
    ]

    VALID_TRANSITIONS = {
        DRAFT: {SUBMITTED, CANCELLED},
        SUBMITTED: {CANCELLED, PARTIALLY_RECEIVED, FULLY_RECEIVED},
        PARTIALLY_RECEIVED: {PARTIALLY_RECEIVED, FULLY_RECEIVED},
        FULLY_RECEIVED: set(),
        CANCELLED: set(),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po_number = models.CharField(max_length=20, blank=True)
    supplier = models.ForeignKey(
        "suppliers.Supplier",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_purchase_orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "po_number"],
                name="unique_po_number_per_org",
            )
        ]

    def __str__(self):
        return f"{self.po_number} - {self.supplier} - {self.status}"

    def can_transition_to(self, new_status):
        return new_status in self.VALID_TRANSITIONS.get(self.status, set())


class PurchaseOrderLine(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item = models.ForeignKey(
        "inventory.OrgItem",
        on_delete=models.PROTECT,
        related_name="purchase_order_lines",
    )
    ordered_quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    received_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_order", "item"],
                name="unique_item_per_po",
            ),
            models.CheckConstraint(
                check=models.Q(received_quantity__lte=models.F("ordered_quantity")),
                name="po_line_received_lte_ordered",
            ),
        ]

    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.item}"

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from branches.models import Branch
from tenancy.models import TenantModel


class Item(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("organization", "sku")]
        indexes = [models.Index(fields=["organization", "sku"])]

    def __str__(self):
        return self.sku


class StockOnHand(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    class Meta:
        unique_together = [("organization", "branch", "item")]
        indexes = [models.Index(fields=["organization", "branch", "item"])]


class StockLedger(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    MOVEMENT_RECEIPT = "RECEIPT"
    MOVEMENT_ISSUE = "ISSUE"
    MOVEMENT_ADJUSTMENT = "ADJUSTMENT"

    MOVEMENT_CHOICES = [
        (MOVEMENT_RECEIPT, "Receipt"),
        (MOVEMENT_ISSUE, "Issue"),
        (MOVEMENT_ADJUSTMENT, "Adjustment"),
    ]

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_CHOICES)
    reference_type = models.CharField(max_length=100, null=True, blank=True)
    reference_id = models.CharField(max_length=255, null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements",
    )
    occurred_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "branch", "item"]),
            models.Index(fields=["organization", "reference_type", "reference_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                condition=Q(idempotency_key__isnull=False),
                name="unique_org_idempotency_key",
            )
        ]

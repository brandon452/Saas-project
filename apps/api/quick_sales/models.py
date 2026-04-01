import uuid

from django.conf import settings
from django.db import models

from tenancy.models import TenantModel


class QuickSale(TenantModel):
    STATUS_CONFIRMED = "CONFIRMED"
    STATUS_VOIDED = "VOIDED"

    STATUS_CHOICES = [
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_VOIDED, "Voided"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("branches.Branch", on_delete=models.PROTECT)
    customer_name = models.CharField(max_length=255, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    occurred_at = models.DateTimeField(db_index=True)
    sold_at = models.DateTimeField(auto_now_add=True)
    sold_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quick_sales_sold",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_CONFIRMED,
    )
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quick_sales_voided",
    )
    voided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-occurred_at"]


class QuickSaleLine(models.Model):
    sale = models.ForeignKey(
        QuickSale,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item = models.ForeignKey("inventory.OrgItem", on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)

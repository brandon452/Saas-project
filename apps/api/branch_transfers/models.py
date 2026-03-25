import uuid

from django.conf import settings
from django.db import models

from tenancy.models import TenantModel


class BranchTransfer(TenantModel):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    IN_TRANSIT = "IN_TRANSIT"
    RECEIVED_COMPLETE = "RECEIVED_COMPLETE"
    RECEIVED_WITH_VARIANCE = "RECEIVED_WITH_VARIANCE"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (APPROVED, "Approved"),
        (IN_TRANSIT, "In Transit"),
        (RECEIVED_COMPLETE, "Received Complete"),
        (RECEIVED_WITH_VARIANCE, "Received With Variance"),
        (CANCELLED, "Cancelled"),
    ]

    VALID_TRANSITIONS = {
        DRAFT: {APPROVED, CANCELLED},
        APPROVED: {IN_TRANSIT, CANCELLED},
        IN_TRANSIT: {RECEIVED_COMPLETE, RECEIVED_WITH_VARIANCE},
        RECEIVED_COMPLETE: set(),
        RECEIVED_WITH_VARIANCE: set(),
        CANCELLED: set(),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="outbound_transfers",
    )
    to_branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="inbound_transfers",
    )
    to_organization = models.ForeignKey(
        "tenancy.Organization",
        on_delete=models.PROTECT,
        related_name="inbound_transfers",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=DRAFT)
    notes = models.TextField(blank=True)
    receive_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_transfers",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_transfers",
    )
    dispatched_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="received_transfers",
    )
    received_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Transfer {self.pk} {self.from_branch} -> {self.to_branch} [{self.status}]"

    def can_transition_to(self, new_status):
        return new_status in self.VALID_TRANSITIONS.get(self.status, set())


class BranchTransferLine(models.Model):
    transfer = models.ForeignKey(
        BranchTransfer,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item = models.ForeignKey(
        "inventory.OrgItem",
        on_delete=models.PROTECT,
        related_name="transfer_lines",
    )
    quantity_sent = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["transfer", "item"],
                name="unique_item_per_transfer",
            )
        ]

    def __str__(self):
        return f"Transfer {self.transfer_id} - {self.item} - sent {self.quantity_sent}"

import uuid

from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models
from django.db.models import Q

from branches.models import Branch
from tenancy.models import TenantModel


class MasterItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.sku} - {self.name}"


class OrgItem(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    master_item = models.ForeignKey(
        MasterItem,
        on_delete=models.PROTECT,
        related_name="org_items",
    )
    name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("organization", "master_item")]
        indexes = [
            models.Index(
                fields=["organization", "master_item"],
                name="inv_orgitem_org_master_idx",
            )
        ]

    @property
    def sku(self):
        return self.master_item.sku

    @property
    def display_name(self):
        return self.name or self.master_item.name

    def __str__(self):
        return f"{self.sku} - {self.display_name}"


class BranchItem(models.Model):
    org_item = models.ForeignKey(
        OrgItem,
        on_delete=models.PROTECT,
        related_name="branch_items",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="branch_items",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("branch", "org_item")]
        indexes = [
            models.Index(
                fields=["branch", "org_item"],
                name="inv_branchitem_branch_org_idx",
            )
        ]

    def clean(self):
        if self.branch_id and self.org_item_id:
            if self.branch.organization_id != self.org_item.organization_id:
                raise ValidationError("Branch and OrgItem must belong to the same organisation.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.branch} - {self.org_item}"


class StockOnHand(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    item = models.ForeignKey(OrgItem, on_delete=models.PROTECT)
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
    item = models.ForeignKey(OrgItem, on_delete=models.PROTECT)
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


class StockTake(TenantModel):
    """
    A physical inventory count session for a specific branch.
    Lines are created on start from active BranchItems.
    Notes editable in DRAFT and IN_PROGRESS only via PATCH.
    No PUT - PATCH only.
    Adjustments posted on approval using current live StockOnHand quantities.
    Only one IN_PROGRESS stock take is permitted per branch at a time.
    """

    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_VARIANCES = "COMPLETED_WITH_VARIANCES"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (IN_PROGRESS, "In Progress"),
        (PENDING_APPROVAL, "Pending Approval"),
        (COMPLETED, "Completed"),
        (COMPLETED_WITH_VARIANCES, "Completed with Variances"),
        (CANCELLED, "Cancelled"),
    ]

    VALID_TRANSITIONS = {
        DRAFT: {IN_PROGRESS, CANCELLED},
        IN_PROGRESS: {PENDING_APPROVAL, CANCELLED},
        PENDING_APPROVAL: {IN_PROGRESS, COMPLETED, COMPLETED_WITH_VARIANCES, CANCELLED},
        COMPLETED: set(),
        COMPLETED_WITH_VARIANCES: set(),
        CANCELLED: set(),
    }
    EDITABLE_STATUSES = {DRAFT, IN_PROGRESS}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="stock_takes",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=DRAFT,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_stock_takes",
    )
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="started_stock_takes",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_stock_takes",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_stock_takes",
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cancelled_stock_takes",
    )
    reopened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reopened_stock_takes",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    reopened_at = models.DateTimeField(null=True, blank=True)
    snapshot_taken_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When snapshot quantities were captured. Not updated on reopen.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.branch_id and self.organization_id:
            if self.branch.organization_id != self.organization_id:
                raise ValidationError("Branch must belong to the same organisation as this stock take.")

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is None or "branch" in update_fields or "organization" in update_fields:
            self.full_clean()
        return super().save(*args, **kwargs)

    def can_transition_to(self, new_status):
        return new_status in self.VALID_TRANSITIONS.get(self.status, set())

    def __str__(self):
        return f"StockTake {self.id} [{self.branch}] [{self.status}]"


class StockTakeLine(models.Model):
    """
    One line per BranchItem-enabled item in the count.
    Created on start. snapshot_quantity taken from StockOnHand or Decimal("0").
    counted_quantity entered by staff during IN_PROGRESS.
    variance_preview is a computed property for display during review.
    Adjustment on approval uses current live StockOnHand, not snapshot.
    """

    stock_take = models.ForeignKey(
        StockTake,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    org_item = models.ForeignKey(
        OrgItem,
        on_delete=models.PROTECT,
        related_name="stock_take_lines",
    )
    snapshot_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        help_text="System quantity at time of start. Not updated on reopen.",
    )
    counted_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Physical count entered by staff. Null means not yet counted.",
    )

    class Meta:
        unique_together = [("stock_take", "org_item")]

    @property
    def variance_preview(self):
        if self.counted_quantity is None:
            return None
        return self.counted_quantity - self.snapshot_quantity

    def __str__(self):
        return f"StockTakeLine {self.stock_take_id} - {self.org_item}"

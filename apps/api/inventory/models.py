import uuid

from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models
from django.db.models import Q

from branches.models import Branch
from tenancy.models import ParentCompany, TenantModel, get_default_parent_company


class MasterItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent_company = models.ForeignKey(
        ParentCompany,
        on_delete=models.PROTECT,
        related_name="master_items",
    )
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["parent_company", "sku"],
                name="unique_master_item_sku_per_parent_company",
            )
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.parent_company_id:
            self.parent_company = get_default_parent_company()
        return super().save(*args, **kwargs)


class OrgItem(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    master_item = models.ForeignKey(
        MasterItem,
        on_delete=models.PROTECT,
        related_name="org_items",
    )
    name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_lot_tracked = models.BooleanField(default=False)
    is_expiry_tracked = models.BooleanField(default=False)
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
    CLASS_A = "A"
    CLASS_B = "B"
    CLASS_C = "C"
    ITEM_CLASS_CHOICES = [
        (CLASS_A, "A"),
        (CLASS_B, "B"),
        (CLASS_C, "C"),
    ]

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
    item_class = models.CharField(
        max_length=1,
        choices=ITEM_CLASS_CHOICES,
        null=True,
        blank=True,
    )
    next_cycle_count_date = models.DateField(null=True, blank=True)
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
        if not self.pk:  # cross-org check only needed at creation; branch/org_item are immutable after that
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
    unit_cost   = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    value_delta = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
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
    TYPE_FULL = "FULL"
    TYPE_CYCLE = "CYCLE"
    STOCK_TAKE_TYPE_CHOICES = [
        (TYPE_FULL, "Full"),
        (TYPE_CYCLE, "Cycle"),
    ]
    CYCLE_CLASS_A = "A"
    CYCLE_CLASS_B = "B"
    CYCLE_CLASS_C = "C"
    CYCLE_ITEM_CLASS_CHOICES = [
        (CYCLE_CLASS_A, "A"),
        (CYCLE_CLASS_B, "B"),
        (CYCLE_CLASS_C, "C"),
    ]

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
    stock_take_type = models.CharField(
        max_length=10,
        choices=STOCK_TAKE_TYPE_CHOICES,
        default=TYPE_FULL,
    )
    cycle_item_class = models.CharField(
        max_length=1,
        choices=CYCLE_ITEM_CLASS_CHOICES,
        null=True,
        blank=True,
    )
    scheduled_for = models.DateField(null=True, blank=True)
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
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "branch"],
                condition=Q(status="IN_PROGRESS", stock_take_type="FULL"),
                name="unique_in_progress_full_stock_take_per_branch",
            ),
            models.UniqueConstraint(
                fields=["organization", "branch", "cycle_item_class"],
                condition=Q(status="IN_PROGRESS", stock_take_type="CYCLE"),
                name="unique_in_progress_cycle_stock_take_per_branch_class",
            ),
            models.UniqueConstraint(
                fields=["organization", "branch", "cycle_item_class", "scheduled_for"],
                condition=Q(stock_take_type="CYCLE"),
                name="unique_cycle_stock_take_per_branch_class_scheduled_for",
            ),
        ]

    def clean(self):
        if self.branch_id and self.organization_id:
            if self.branch.organization_id != self.organization_id:
                raise ValidationError("Branch must belong to the same organisation as this stock take.")
        if self.stock_take_type == self.TYPE_FULL:
            if self.cycle_item_class is not None:
                raise ValidationError("cycle_item_class must be null for FULL stock takes.")
            if self.scheduled_for is not None:
                raise ValidationError("scheduled_for must be null for FULL stock takes.")
        if self.stock_take_type == self.TYPE_CYCLE:
            if not self.cycle_item_class:
                raise ValidationError("cycle_item_class is required for CYCLE stock takes.")
            if self.scheduled_for is None:
                raise ValidationError("scheduled_for is required for CYCLE stock takes.")

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


class InventoryCostState(TenantModel):
    branch            = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="cost_states")
    item              = models.ForeignKey(OrgItem, on_delete=models.PROTECT, related_name="cost_states")
    average_unit_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    latest_unit_cost  = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    last_receipt_at   = models.DateTimeField(null=True, blank=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("organization", "branch", "item")]


class InventoryClosePeriod(TenantModel):
    OPEN    = "OPEN"
    CLOSING = "CLOSING"
    CLOSED  = "CLOSED"

    STATUS_CHOICES = [
        (OPEN, "Open"),
        (CLOSING, "Closing"),
        (CLOSED, "Closed"),
    ]

    start_date  = models.DateField()
    end_date    = models.DateField()
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default=OPEN, db_index=True)
    closed_at   = models.DateTimeField(null=True, blank=True)
    closed_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="closed_periods",
    )
    reopened_at = models.DateTimeField(null=True, blank=True)
    reopened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reopened_periods",
    )
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [("organization", "start_date", "end_date")]
        indexes = [
            models.Index(fields=["organization", "start_date"], name="inv_closeperiod_org_start_idx"),
            models.Index(fields=["organization", "end_date"],   name="inv_closeperiod_org_end_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(status__in=["OPEN", "CLOSING", "CLOSED"]),
                name="inventory_close_period_valid_status",
            )
        ]


class InventoryLotBalance(TenantModel):
    """
    Per-lot stock balance for lot/batch tracked items.
    One row per (organization, branch, org_item, lot_code).
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="lot_balances")
    org_item = models.ForeignKey(OrgItem, on_delete=models.PROTECT, related_name="lot_balances")
    lot_code = models.CharField(max_length=100)
    expiry_date = models.DateField(null=True, blank=True)
    manufacture_date = models.DateField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    available_qty = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "branch", "org_item", "lot_code"],
                name="unique_lot_balance_per_org_branch_item_code",
            ),
            models.CheckConstraint(
                check=Q(available_qty__gte=0),
                name="lot_balance_non_negative_qty",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "branch", "org_item", "expiry_date", "received_at"],
                name="inv_lotbal_fefo_idx",
            ),
        ]

    def __str__(self):
        return f"Lot {self.lot_code} | {self.org_item} | {self.branch} | qty={self.available_qty}"


class GoodsReceiptLineLotAllocation(models.Model):
    """Child allocation linking a goods receipt line to a lot balance."""

    receipt_line = models.ForeignKey(
        "goods_receipts.GoodsReceiptLine",
        on_delete=models.CASCADE,
        related_name="lot_allocations",
    )
    lot = models.ForeignKey(
        InventoryLotBalance,
        on_delete=models.PROTECT,
        related_name="receipt_allocations",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=4)

    def __str__(self):
        return f"GRLotAlloc receipt_line={self.receipt_line_id} lot={self.lot_id} qty={self.quantity}"


class BranchTransferLineDispatchLotAllocation(models.Model):
    """Child allocation linking a dispatch line to a lot depleted at source."""

    transfer_line = models.ForeignKey(
        "branch_transfers.BranchTransferLine",
        on_delete=models.CASCADE,
        related_name="dispatch_lot_allocations",
    )
    lot = models.ForeignKey(
        InventoryLotBalance,
        on_delete=models.PROTECT,
        related_name="transfer_dispatch_allocations",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=4)

    def __str__(self):
        return f"DispatchLotAlloc line={self.transfer_line_id} lot={self.lot_id} qty={self.quantity}"


class BranchTransferLineReceiveLotAllocation(models.Model):
    """Child allocation linking a receive line to a lot incremented at destination."""

    transfer_line = models.ForeignKey(
        "branch_transfers.BranchTransferLine",
        on_delete=models.CASCADE,
        related_name="receive_lot_allocations",
    )
    lot = models.ForeignKey(
        InventoryLotBalance,
        on_delete=models.PROTECT,
        related_name="transfer_receive_allocations",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=4)

    def __str__(self):
        return f"ReceiveLotAlloc line={self.transfer_line_id} lot={self.lot_id} qty={self.quantity}"


class StockMovementLotAllocation(models.Model):
    """Links a StockLedger row to a lot (unsigned magnitude)."""

    ledger = models.ForeignKey(
        StockLedger,
        on_delete=models.CASCADE,
        related_name="lot_allocations",
    )
    lot = models.ForeignKey(
        InventoryLotBalance,
        on_delete=models.PROTECT,
        related_name="movement_allocations",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=4)

    def __str__(self):
        return f"MovementLotAlloc ledger={self.ledger_id} lot={self.lot_id} qty={self.quantity}"


class StockTakeLineLotAllocation(models.Model):
    """
    Lot-level variance allocation for stock-take lines.
    Submitted during PENDING_APPROVAL, applied during approval.
    """

    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    DIRECTION_CHOICES = [(INCREASE, "Increase"), (DECREASE, "Decrease")]

    stock_take_line = models.ForeignKey(
        StockTakeLine,
        on_delete=models.CASCADE,
        related_name="lot_allocations",
    )
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)

    # Points to an existing lot (nullable — new lots are created from draft fields)
    lot = models.ForeignKey(
        InventoryLotBalance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_take_allocations",
    )

    # Draft lot fields for new-lot creation
    lot_code = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    manufacture_date = models.DateField(null=True, blank=True)

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_take_lot_allocations",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return (
            f"STLineLotAlloc line={self.stock_take_line_id} "
            f"direction={self.direction} qty={self.quantity}"
        )


class InventoryCloseSnapshot(TenantModel):
    period            = models.ForeignKey(InventoryClosePeriod, on_delete=models.CASCADE, related_name="snapshots")
    branch            = models.ForeignKey(Branch, on_delete=models.PROTECT)
    item              = models.ForeignKey(OrgItem, on_delete=models.PROTECT)
    quantity_on_hand  = models.DecimalField(max_digits=12, decimal_places=4)
    average_unit_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    latest_unit_cost  = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    average_valuation = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    latest_valuation  = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    valuation_basis   = models.CharField(
        max_length=10, default="AVCO",
        choices=[("AVCO", "AVCO"), ("LATEST", "Latest")],
    )

    class Meta:
        unique_together = [("period", "branch", "item")]
        indexes = [
            models.Index(fields=["period", "branch"], name="inv_snap_period_branch_idx"),
            models.Index(fields=["period", "item"],   name="inv_snap_period_item_idx"),
        ]

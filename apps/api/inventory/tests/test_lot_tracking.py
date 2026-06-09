"""
Tests for Lot/Batch + Expiry Tracking.

Covers:
- Unit tests: FEFO, FIFO, allocation sum validation, permission, feature-flag bypass
- Integration tests: goods receipts, transfer dispatch/receive (including conflict/override),
  quick sales (fractional), stock-take lot allocation workflow
- Regression tests: non-lot items unchanged, existing record_stock_movement callers
- Backfill management command
"""

from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase, override_settings

from branches.models import Branch
from goods_receipts.models import GoodsReceipt, GoodsReceiptLine
from goods_receipts.services import post_direct_receipt
from branch_transfers.models import BranchTransfer, BranchTransferLine
from branch_transfers.services import dispatch_transfer, receive_transfer
from inventory.lot_services import (
    allocate_lots_fefo_fifo,
    validate_allocations_sum,
    check_lot_override_permission,
)
from inventory.models import (
    BranchItem,
    BranchTransferLineDispatchLotAllocation,
    BranchTransferLineReceiveLotAllocation,
    GoodsReceiptLineLotAllocation,
    InventoryLotBalance,
    MasterItem,
    OrgItem,
    StockLedger,
    StockMovementLotAllocation,
    StockOnHand,
    StockTake,
    StockTakeLineLotAllocation,
)
from inventory.services import (
    approve_stock_take,
    record_stock_movement,
    start_stock_take,
    submit_stock_take,
)
from quick_sales.services import create_quick_sale
from tenancy.models import Organization, OrganizationMember

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_org_item(org, name, sku, *, is_lot_tracked=False, is_expiry_tracked=False):
    master = MasterItem.objects.create(name=name, sku=sku)
    return OrgItem.objects.create(
        organization=org,
        master_item=master,
        is_lot_tracked=is_lot_tracked,
        is_expiry_tracked=is_expiry_tracked,
    )


def _make_lot(org, branch, org_item, lot_code, *, available_qty=Decimal("0"),
              expiry_date=None, manufacture_date=None, received_at=None):
    """Create an InventoryLotBalance row directly."""
    lot = InventoryLotBalance.objects.create(
        organization=org,
        branch=branch,
        org_item=org_item,
        lot_code=lot_code,
        available_qty=available_qty,
        expiry_date=expiry_date,
        manufacture_date=manufacture_date,
    )
    if received_at is not None:
        # Override auto_now_add by using update()
        InventoryLotBalance.objects.filter(pk=lot.pk).update(received_at=received_at)
        lot.refresh_from_db()
    return lot


def _post_receipt_for_item(org, branch, item, qty, unit_cost, user):
    """Create a stock movement so the item has an AVCO cost basis and SOH."""
    ledger, _ = record_stock_movement(
        org=org, branch=branch, item=item,
        quantity=qty,
        movement_type=StockLedger.MOVEMENT_RECEIPT,
        unit_cost=unit_cost,
        performed_by=user,
    )
    return ledger


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class FEFOOrderingTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Lot Org", slug="lot-org")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Main", code="MAIN"
        )
        self.item = _make_org_item(self.org, "Widget", "WID-001", is_lot_tracked=True)

    def test_earlier_expiry_depleted_first(self):
        """FEFO: lot with earlier expiry_date should be allocated first."""
        from datetime import date
        _make_lot(self.org, self.branch, self.item, "LOT-A",
                  available_qty=Decimal("5"), expiry_date=date(2025, 6, 1))
        _make_lot(self.org, self.branch, self.item, "LOT-B",
                  available_qty=Decimal("5"), expiry_date=date(2025, 12, 31))

        allocs = allocate_lots_fefo_fifo(self.org, self.branch, self.item, Decimal("6"))
        # Should take all 5 from LOT-A, then 1 from LOT-B
        self.assertEqual(len(allocs), 2)
        self.assertEqual(allocs[0][0].lot_code, "LOT-A")
        self.assertEqual(allocs[0][1], Decimal("5"))
        self.assertEqual(allocs[1][0].lot_code, "LOT-B")
        self.assertEqual(allocs[1][1], Decimal("1"))

    def test_null_expiry_sorted_last(self):
        """Lots without expiry_date come after lots with an expiry_date."""
        from datetime import date
        _make_lot(self.org, self.branch, self.item, "LOT-NOEXP",
                  available_qty=Decimal("10"))
        _make_lot(self.org, self.branch, self.item, "LOT-EXP",
                  available_qty=Decimal("10"), expiry_date=date(2025, 9, 1))

        allocs = allocate_lots_fefo_fifo(self.org, self.branch, self.item, Decimal("5"))
        # Should prefer lot_with_expiry first
        self.assertEqual(allocs[0][0].lot_code, "LOT-EXP")

    def test_insufficient_stock_raises(self):
        """Raises ValidationError when requested quantity exceeds available lots."""
        _make_lot(self.org, self.branch, self.item, "LOT-SMALL", available_qty=Decimal("2"))

        with self.assertRaises(ValidationError) as ctx:
            allocate_lots_fefo_fifo(self.org, self.branch, self.item, Decimal("10"))
        self.assertIn("Insufficient lot stock", str(ctx.exception))


class FIFOOrderingTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="FIFO Org", slug="fifo-org")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Main", code="MAIN"
        )
        self.item = _make_org_item(self.org, "Sprocket", "SPR-001", is_lot_tracked=True)

    def test_earlier_received_at_depleted_first_when_no_expiry(self):
        """FIFO: when no expiry_date, earlier received_at is consumed first."""
        from datetime import datetime, timezone as dt_tz
        t1 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=dt_tz.utc)
        t2 = datetime(2024, 6, 1, 0, 0, 0, tzinfo=dt_tz.utc)

        # Create in reverse order so DB insertion order doesn't help
        _make_lot(self.org, self.branch, self.item, "LOT-NEW",
                  available_qty=Decimal("10"), received_at=t2)
        _make_lot(self.org, self.branch, self.item, "LOT-OLD",
                  available_qty=Decimal("10"), received_at=t1)

        allocs = allocate_lots_fefo_fifo(self.org, self.branch, self.item, Decimal("5"))
        self.assertEqual(allocs[0][0].lot_code, "LOT-OLD")


class AllocationSumValidationTest(TestCase):
    def test_matching_sum_passes(self):
        allocs = [{"quantity": "3"}, {"quantity": "7"}]
        validate_allocations_sum(allocs, Decimal("10"))  # should not raise

    def test_mismatched_sum_raises(self):
        allocs = [{"quantity": "3"}, {"quantity": "5"}]
        with self.assertRaises(ValidationError) as ctx:
            validate_allocations_sum(allocs, Decimal("10"))
        self.assertIn("sum to 8", str(ctx.exception))

    def test_tuple_form_works(self):
        allocs = [(object(), Decimal("4")), (object(), Decimal("6"))]
        validate_allocations_sum(allocs, Decimal("10"))  # should not raise


class LotOverridePermissionTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Perm Org", slug="perm-org")
        self.owner_user = User.objects.create_user(username="lt_owner", password="pass")
        self.staff_user = User.objects.create_user(username="lt_staff", password="pass")
        OrganizationMember.objects.create(
            user=self.owner_user, organization=self.org, role="OWNER", is_active=True
        )
        OrganizationMember.objects.create(
            user=self.staff_user, organization=self.org, role="STAFF", is_active=True
        )

    def _mock_request(self, role):
        """Build a mock request that get_member_role will see correctly."""
        request = mock.Mock()
        request.user = mock.Mock()
        request.user.is_authenticated = True
        request.org = self.org
        # Pre-populate the cache key that get_member_role checks
        request._cached_member_role = role
        # Ensure get_parent_membership returns None (not a parent member)
        request._cached_parent_membership = None
        return request

    def test_owner_allowed(self):
        request = self._mock_request("OWNER")
        # Should not raise
        check_lot_override_permission(request)

    def test_staff_denied(self):
        request = self._mock_request("STAFF")
        with self.assertRaises(PermissionDenied):
            check_lot_override_permission(request)


class FeatureFlagBypassTest(TestCase):
    """When feature flags are off, lot enforcement is skipped."""

    def setUp(self):
        self.org = Organization.objects.create(name="Flag Org", slug="flag-org")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Main", code="MAIN"
        )
        self.user = User.objects.create_user(username="flag_user", password="pass")
        self.item = _make_org_item(self.org, "FlagItem", "FLAG-1", is_lot_tracked=True)

    @override_settings(LOT_TRACKING_RECEIPTS_ENABLED=False)
    def test_receipt_no_lot_required_when_flag_off(self):
        """Direct receipt succeeds without lot_allocations when flag is off."""
        receipt = GoodsReceipt.objects.create(
            organization=self.org,
            branch=self.branch,
            receipt_type=GoodsReceipt.DIRECT_RECEIPT,
            received_by=self.user,
        )
        # Should not raise even though item is lot-tracked
        post_direct_receipt(
            receipt=receipt,
            lines_data=[{"item": self.item, "quantity_received": 10, "unit_cost": Decimal("5")}],
            performed_by=self.user,
            organization=self.org,
        )


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class GoodsReceiptLotIntegrationTest(TransactionTestCase):
    @override_settings(LOT_TRACKING_RECEIPTS_ENABLED=True)
    def setUp(self):
        self.org = Organization.objects.create(name="GR Lot Org", slug="gr-lot-org")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Main", code="MAIN"
        )
        self.user = User.objects.create_user(username="gr_lot_user", password="pass")
        self.item = _make_org_item(self.org, "GR Item", "GR-001", is_lot_tracked=True)

    @override_settings(LOT_TRACKING_RECEIPTS_ENABLED=True)
    def test_multi_lot_direct_receipt(self):
        """Multi-lot receipt: correct lot balances, GRLineLotAllocation, StockMovementLotAllocation."""
        receipt = GoodsReceipt.objects.create(
            organization=self.org,
            branch=self.branch,
            receipt_type=GoodsReceipt.DIRECT_RECEIPT,
            received_by=self.user,
        )
        lot_allocs = [
            {"lot_code": "LOT-A", "quantity": "6", "expiry_date": "2025-12-01"},
            {"lot_code": "LOT-B", "quantity": "4"},
        ]
        post_direct_receipt(
            receipt=receipt,
            lines_data=[{
                "item": self.item,
                "quantity_received": 10,
                "unit_cost": Decimal("5"),
                "lot_allocations": lot_allocs,
            }],
            performed_by=self.user,
            organization=self.org,
        )

        # Check GoodsReceiptLine was created
        gr_line = GoodsReceiptLine.objects.get(receipt=receipt)
        self.assertEqual(gr_line.quantity_received, 10)

        # Check lot balances
        lot_a = InventoryLotBalance.objects.get(
            organization=self.org, branch=self.branch, org_item=self.item, lot_code="LOT-A"
        )
        lot_b = InventoryLotBalance.objects.get(
            organization=self.org, branch=self.branch, org_item=self.item, lot_code="LOT-B"
        )
        self.assertEqual(lot_a.available_qty, Decimal("6"))
        self.assertEqual(lot_b.available_qty, Decimal("4"))

        # Check allocation child records
        gr_allocs = GoodsReceiptLineLotAllocation.objects.filter(receipt_line=gr_line)
        self.assertEqual(gr_allocs.count(), 2)

        # Check StockMovementLotAllocation
        ledger = StockLedger.objects.get(organization=self.org, item=self.item)
        sm_allocs = StockMovementLotAllocation.objects.filter(ledger=ledger)
        self.assertEqual(sm_allocs.count(), 2)

    @override_settings(LOT_TRACKING_RECEIPTS_ENABLED=True)
    def test_missing_lot_allocations_raises(self):
        """Lot-tracked item without lot_allocations raises ValidationError."""
        receipt = GoodsReceipt.objects.create(
            organization=self.org,
            branch=self.branch,
            receipt_type=GoodsReceipt.DIRECT_RECEIPT,
            received_by=self.user,
        )
        with self.assertRaises(ValidationError) as ctx:
            post_direct_receipt(
                receipt=receipt,
                lines_data=[{
                    "item": self.item,
                    "quantity_received": 5,
                    "unit_cost": Decimal("5"),
                    # no lot_allocations
                }],
                performed_by=self.user,
                organization=self.org,
            )
        self.assertIn("lot-tracked", str(ctx.exception))

    @override_settings(LOT_TRACKING_RECEIPTS_ENABLED=True)
    def test_allocation_sum_mismatch_raises(self):
        """Allocation quantities that don't sum to quantity_received raises ValidationError."""
        receipt = GoodsReceipt.objects.create(
            organization=self.org,
            branch=self.branch,
            receipt_type=GoodsReceipt.DIRECT_RECEIPT,
            received_by=self.user,
        )
        with self.assertRaises(ValidationError) as ctx:
            post_direct_receipt(
                receipt=receipt,
                lines_data=[{
                    "item": self.item,
                    "quantity_received": 10,
                    "unit_cost": Decimal("5"),
                    "lot_allocations": [{"lot_code": "LOT-X", "quantity": "3"}],  # only 3, not 10
                }],
                performed_by=self.user,
                organization=self.org,
            )
        self.assertIn("sum to 3", str(ctx.exception))


class TransferDispatchLotTest(TransactionTestCase):
    @override_settings(LOT_TRACKING_TRANSFERS_ENABLED=True)
    def setUp(self):
        self.org = Organization.objects.create(name="Tx Org", slug="tx-org")
        self.src_branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Source", code="SRC"
        )
        self.dst_branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Dest", code="DST"
        )
        self.user = User.objects.create_user(username="tx_lot_user", password="pass")
        self.item = _make_org_item(self.org, "Transfer Item", "TX-001", is_lot_tracked=True)

        # Give item stock + cost state
        _post_receipt_for_item(self.org, self.src_branch, self.item, 20, Decimal("10"), self.user)

        # Give lots at source
        self.lot_a = _make_lot(self.org, self.src_branch, self.item, "TX-LOT-A",
                               available_qty=Decimal("10"))
        self.lot_b = _make_lot(self.org, self.src_branch, self.item, "TX-LOT-B",
                               available_qty=Decimal("10"))

    @override_settings(LOT_TRACKING_TRANSFERS_ENABLED=True)
    def test_dispatch_depletes_source_lots_fefo(self):
        """Dispatch auto-allocates via FEFO/FIFO and depletes source lots."""
        transfer = BranchTransfer.objects.create(
            organization=self.org,
            from_branch=self.src_branch,
            to_branch=self.dst_branch,
            to_organization=self.org,
            status=BranchTransfer.APPROVED,
        )
        BranchItem.objects.create(branch=self.src_branch, org_item=self.item, is_active=True)
        line = BranchTransferLine.objects.create(
            transfer=transfer,
            item=self.item,
            quantity_sent=15,
        )

        dispatch_transfer(transfer, performed_by=self.user)

        self.lot_a.refresh_from_db()
        self.lot_b.refresh_from_db()

        # Should have depleted 10 from lot_a and 5 from lot_b
        self.assertEqual(self.lot_a.available_qty, Decimal("0"))
        self.assertEqual(self.lot_b.available_qty, Decimal("5"))

        # Check dispatch lot allocations created
        dispatch_allocs = BranchTransferLineDispatchLotAllocation.objects.filter(transfer_line=line)
        self.assertEqual(dispatch_allocs.count(), 2)

        # Check StockMovementLotAllocation created
        ledger = StockLedger.objects.filter(
            organization=self.org, branch=self.src_branch, item=self.item,
            movement_type=StockLedger.MOVEMENT_ISSUE,
        ).first()
        self.assertIsNotNone(ledger)
        sm_allocs = StockMovementLotAllocation.objects.filter(ledger=ledger)
        self.assertEqual(sm_allocs.count(), 2)


class TransferReceiveLotTest(TransactionTestCase):
    @override_settings(LOT_TRACKING_TRANSFERS_ENABLED=True)
    def _setup_dispatched_transfer(self, lot_code="RX-LOT-A", qty_dispatched=10):
        self.org = Organization.objects.create(name="Rx Org", slug="rx-org")
        self.src_branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Source", code="SRC"
        )
        self.dst_branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Dest", code="DST"
        )
        self.user = User.objects.create_user(username="rx_lot_user", password="pass")
        self.item = _make_org_item(self.org, "Rx Item", "RX-001", is_lot_tracked=True)
        _post_receipt_for_item(self.org, self.src_branch, self.item, qty_dispatched, Decimal("10"), self.user)
        self.src_lot = _make_lot(self.org, self.src_branch, self.item, lot_code,
                                  available_qty=Decimal(str(qty_dispatched)))

        transfer = BranchTransfer.objects.create(
            organization=self.org,
            from_branch=self.src_branch,
            to_branch=self.dst_branch,
            to_organization=self.org,
            status=BranchTransfer.APPROVED,
        )
        BranchItem.objects.create(branch=self.src_branch, org_item=self.item, is_active=True)
        self.line = BranchTransferLine.objects.create(
            transfer=transfer,
            item=self.item,
            quantity_sent=qty_dispatched,
        )
        dispatch_transfer(transfer, performed_by=self.user)
        transfer.refresh_from_db()
        self.transfer = transfer
        return transfer

    @override_settings(LOT_TRACKING_TRANSFERS_ENABLED=True)
    def test_receive_increments_destination_lot(self):
        """Receive creates destination lot with correct lot identity."""
        transfer = self._setup_dispatched_transfer(lot_code="RX-LOT-A", qty_dispatched=10)

        receive_transfer(
            transfer,
            lines_data=[{"line_id": self.line.pk, "quantity_received": 10}],
            performed_by=self.user,
        )

        # Check destination lot created and incremented
        dest_lot = InventoryLotBalance.objects.filter(
            organization=self.org,
            branch=self.dst_branch,
            lot_code="RX-LOT-A",
        ).first()
        self.assertIsNotNone(dest_lot)
        self.assertEqual(dest_lot.available_qty, Decimal("10"))

        # Check BranchTransferLineReceiveLotAllocation created
        rx_allocs = BranchTransferLineReceiveLotAllocation.objects.filter(transfer_line=self.line)
        self.assertEqual(rx_allocs.count(), 1)

    @override_settings(LOT_TRACKING_TRANSFERS_ENABLED=True)
    def test_receive_conflict_rejected_by_default(self):
        """
        Receive raises ValidationError by default when destination lot exists
        with conflicting expiry / manufacture dates.
        """
        from datetime import date
        transfer = self._setup_dispatched_transfer(lot_code="CONFLICT-LOT", qty_dispatched=5)

        # Pre-create conflicting destination lot
        InventoryLotBalance.objects.create(
            organization=self.org,
            branch=self.dst_branch,
            org_item=self.item,
            lot_code="CONFLICT-LOT",
            expiry_date=date(2025, 1, 1),  # different from source (None)
            available_qty=Decimal("1"),
        )

        with self.assertRaises(ValidationError) as ctx:
            receive_transfer(
                transfer,
                lines_data=[{"line_id": self.line.pk, "quantity_received": 5}],
                performed_by=self.user,
            )
        self.assertIn("conflicting", str(ctx.exception))

    @override_settings(LOT_TRACKING_TRANSFERS_ENABLED=True)
    def test_receive_conflict_passes_with_lot_override(self):
        """Conflict is allowed when lot_override=True."""
        from datetime import date
        transfer = self._setup_dispatched_transfer(lot_code="OVERRIDE-LOT", qty_dispatched=5)

        InventoryLotBalance.objects.create(
            organization=self.org,
            branch=self.dst_branch,
            org_item=self.item,
            lot_code="OVERRIDE-LOT",
            expiry_date=date(2025, 1, 1),
            available_qty=Decimal("1"),
        )

        # Should not raise
        receive_transfer(
            transfer,
            lines_data=[{"line_id": self.line.pk, "quantity_received": 5}],
            performed_by=self.user,
            lot_override=True,
            lot_override_reason="Manager approved discrepancy.",
        )

        dest_lot = InventoryLotBalance.objects.get(
            organization=self.org,
            branch=self.dst_branch,
            lot_code="OVERRIDE-LOT",
        )
        # Balance should be 1 (pre-existing) + 5 = 6
        self.assertEqual(dest_lot.available_qty, Decimal("6"))


class QuickSaleLotFractionalTest(TransactionTestCase):
    @override_settings(LOT_TRACKING_QUICK_SALES_ENABLED=True)
    def setUp(self):
        self.org = Organization.objects.create(name="QS Lot Org", slug="qs-lot-org")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Main", code="MAIN"
        )
        self.user = User.objects.create_user(username="qs_lot_user", password="pass")
        self.item = _make_org_item(self.org, "QS Item", "QS-001", is_lot_tracked=True)
        _post_receipt_for_item(self.org, self.branch, self.item, Decimal("10"), Decimal("3"), self.user)
        self.lot = _make_lot(self.org, self.branch, self.item, "QS-LOT",
                             available_qty=Decimal("10"))

    @override_settings(LOT_TRACKING_QUICK_SALES_ENABLED=True)
    def test_fractional_lot_depletion(self):
        """Quick sale with fractional quantity correctly depletes lot balance."""
        create_quick_sale(
            self.org,
            self.branch,
            lines=[{
                "item": self.item,
                "quantity": Decimal("3.5"),
                "unit_price": Decimal("5"),
            }],
            performed_by=self.user,
        )

        self.lot.refresh_from_db()
        self.assertEqual(self.lot.available_qty, Decimal("6.5"))

        # Check StockMovementLotAllocation created
        ledger = StockLedger.objects.filter(
            organization=self.org, branch=self.branch, item=self.item,
            movement_type=StockLedger.MOVEMENT_ISSUE,
        ).first()
        sm_allocs = StockMovementLotAllocation.objects.filter(ledger=ledger)
        self.assertEqual(sm_allocs.count(), 1)
        self.assertEqual(sm_allocs.first().quantity, Decimal("3.5"))


class StockTakeLotWorkflowTest(TransactionTestCase):
    @override_settings(LOT_TRACKING_STOCK_TAKE_ENABLED=True)
    def setUp(self):
        self.org = Organization.objects.create(name="ST Lot Org", slug="st-lot-org")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Main", code="MAIN"
        )
        self.user = User.objects.create_user(username="st_lot_user", password="pass")
        self.item = _make_org_item(self.org, "ST Item", "ST-001", is_lot_tracked=True)
        BranchItem.objects.create(branch=self.branch, org_item=self.item, is_active=True)

        # Give stock + cost basis
        _post_receipt_for_item(self.org, self.branch, self.item, 10, Decimal("5"), self.user)
        self.lot = _make_lot(self.org, self.branch, self.item, "ST-LOT",
                             available_qty=Decimal("10"))

    def _create_pending_stock_take(self, counted_qty):
        """Helper: create a stock take in PENDING_APPROVAL state with a counted line."""
        stock_take = StockTake.objects.create(
            organization=self.org,
            branch=self.branch,
            status=StockTake.DRAFT,
        )
        start_stock_take(stock_take, performed_by=self.user)
        stock_take.refresh_from_db()

        line = stock_take.lines.get(org_item=self.item)
        line.counted_quantity = counted_qty
        line.save(update_fields=["counted_quantity"])

        submit_stock_take(stock_take, performed_by=self.user)
        stock_take.refresh_from_db()
        return stock_take, line

    @override_settings(LOT_TRACKING_STOCK_TAKE_ENABLED=True)
    def test_approve_blocks_if_no_lot_allocation_submitted(self):
        """Approval raises ValidationError if no lot allocations submitted for lot-tracked variance."""
        stock_take, line = self._create_pending_stock_take(counted_qty=Decimal("8"))
        # Variance = 8 - 10 = -2 (DECREASE), but no StockTakeLineLotAllocation submitted

        with self.assertRaises(ValidationError) as ctx:
            approve_stock_take(stock_take, performed_by=self.user)
        self.assertIn("lot allocations", str(ctx.exception))

    @override_settings(LOT_TRACKING_STOCK_TAKE_ENABLED=True)
    def test_approve_rejects_stale_allocation_sum_mismatch(self):
        """Approval raises ValidationError if lot allocation sum != |variance|."""
        stock_take, line = self._create_pending_stock_take(counted_qty=Decimal("8"))
        # Variance = -2 → need 2 of DECREASE

        StockTakeLineLotAllocation.objects.create(
            stock_take_line=line,
            direction=StockTakeLineLotAllocation.DECREASE,
            quantity=Decimal("1"),  # wrong — only 1, not 2
            lot=self.lot,
        )

        with self.assertRaises(ValidationError) as ctx:
            approve_stock_take(stock_take, performed_by=self.user)
        self.assertIn("sum to 1", str(ctx.exception))

    @override_settings(LOT_TRACKING_STOCK_TAKE_ENABLED=True)
    def test_approve_succeeds_and_depletes_lot(self):
        """Approval succeeds and correctly depletes lot balance for DECREASE variance."""
        stock_take, line = self._create_pending_stock_take(counted_qty=Decimal("8"))
        # Variance = 8 - 10 = -2 → DECREASE 2 from lot

        StockTakeLineLotAllocation.objects.create(
            stock_take_line=line,
            direction=StockTakeLineLotAllocation.DECREASE,
            quantity=Decimal("2"),
            lot=self.lot,
        )

        approve_stock_take(stock_take, performed_by=self.user)

        self.lot.refresh_from_db()
        self.assertEqual(self.lot.available_qty, Decimal("8"))

        stock_take.refresh_from_db()
        self.assertEqual(stock_take.status, StockTake.COMPLETED_WITH_VARIANCES)

    @override_settings(LOT_TRACKING_STOCK_TAKE_ENABLED=True)
    def test_approve_increase_variance_increments_lot(self):
        """Approval correctly increments lot balance for INCREASE variance (surplus)."""
        stock_take, line = self._create_pending_stock_take(counted_qty=Decimal("13"))
        # Variance = 13 - 10 = +3 → INCREASE 3

        StockTakeLineLotAllocation.objects.create(
            stock_take_line=line,
            direction=StockTakeLineLotAllocation.INCREASE,
            quantity=Decimal("3"),
            lot=self.lot,
        )

        approve_stock_take(stock_take, performed_by=self.user)

        self.lot.refresh_from_db()
        self.assertEqual(self.lot.available_qty, Decimal("13"))


# ---------------------------------------------------------------------------
# Regression tests
# ---------------------------------------------------------------------------

class NonLotItemRegressionTest(TransactionTestCase):
    """Non-lot items through all flows should be unchanged."""

    def setUp(self):
        self.org = Organization.objects.create(name="Reg Org", slug="reg-org")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Main", code="MAIN"
        )
        self.user = User.objects.create_user(username="reg_user", password="pass")
        # is_lot_tracked defaults to False
        self.item = _make_org_item(self.org, "Regular Item", "REG-001")

    @override_settings(LOT_TRACKING_RECEIPTS_ENABLED=True)
    def test_non_lot_direct_receipt_no_allocations_needed(self):
        """Non-lot item receipt works without lot_allocations even when flag is ON."""
        receipt = GoodsReceipt.objects.create(
            organization=self.org,
            branch=self.branch,
            receipt_type=GoodsReceipt.DIRECT_RECEIPT,
            received_by=self.user,
        )
        post_direct_receipt(
            receipt=receipt,
            lines_data=[{"item": self.item, "quantity_received": 5, "unit_cost": Decimal("10")}],
            performed_by=self.user,
            organization=self.org,
        )
        self.assertEqual(GoodsReceiptLine.objects.filter(receipt=receipt).count(), 1)
        # No lot balances should be created
        self.assertEqual(InventoryLotBalance.objects.filter(org_item=self.item).count(), 0)

    def test_record_stock_movement_backward_compatible(self):
        """record_stock_movement still works without any lot args."""
        ledger, created = record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=self.item,
            quantity=10,
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal("5"),
            performed_by=self.user,
        )
        self.assertTrue(created)
        self.assertIsNotNone(ledger.pk)

    @override_settings(LOT_TRACKING_QUICK_SALES_ENABLED=True)
    def test_non_lot_quick_sale_unchanged(self):
        """Quick sale for non-lot item works normally even with flag on."""
        _post_receipt_for_item(self.org, self.branch, self.item, 10, Decimal("5"), self.user)
        sale = create_quick_sale(
            self.org,
            self.branch,
            lines=[{"item": self.item, "quantity": Decimal("2"), "unit_price": Decimal("8")}],
            performed_by=self.user,
        )
        self.assertIsNotNone(sale.pk)
        self.assertEqual(InventoryLotBalance.objects.filter(org_item=self.item).count(), 0)


class BackfillCommandTest(TransactionTestCase):
    """Tests for the backfill_lot_opening management command."""

    def setUp(self):
        self.org = Organization.objects.create(name="BF Org", slug="bf-org")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Main", code="MAIN"
        )
        self.user = User.objects.create_user(username="bf_user", password="pass")
        self.lot_item = _make_org_item(self.org, "BF Item", "BF-001", is_lot_tracked=True)
        self.non_lot_item = _make_org_item(self.org, "Regular", "REG-BF")

    def _give_stock(self, item, qty):
        _post_receipt_for_item(self.org, self.branch, item, qty, Decimal("1"), self.user)

    def test_backfill_creates_opening_lots(self):
        """Command creates opening lot for lot-tracked item with positive SOH."""
        self._give_stock(self.lot_item, 15)

        out = StringIO()
        call_command("backfill_lot_opening", stdout=out)

        lots = InventoryLotBalance.objects.filter(
            organization=self.org, org_item=self.lot_item
        )
        self.assertEqual(lots.count(), 1)
        self.assertEqual(lots.first().available_qty, Decimal("15"))

    def test_backfill_idempotent(self):
        """Running backfill twice does not create duplicate lots."""
        self._give_stock(self.lot_item, 10)

        call_command("backfill_lot_opening")
        call_command("backfill_lot_opening")  # run again

        lots = InventoryLotBalance.objects.filter(
            organization=self.org, org_item=self.lot_item
        )
        self.assertEqual(lots.count(), 1)

    def test_backfill_skips_non_lot_items(self):
        """Non-lot items are not affected by the backfill command."""
        self._give_stock(self.non_lot_item, 5)
        call_command("backfill_lot_opening")
        self.assertEqual(
            InventoryLotBalance.objects.filter(org_item=self.non_lot_item).count(), 0
        )

    def test_backfill_dry_run_does_not_create(self):
        """--dry-run flag prevents any DB writes."""
        self._give_stock(self.lot_item, 7)
        call_command("backfill_lot_opening", dry_run=True)
        self.assertEqual(InventoryLotBalance.objects.filter(org_item=self.lot_item).count(), 0)

    def test_backfill_skips_negative_soh_items(self):
        """Items with negative SOH are skipped with a warning."""
        # Manually force negative SOH (outside normal flow)
        StockOnHand.objects.create(
            organization=self.org,
            branch=self.branch,
            item=self.lot_item,
            quantity=Decimal("-5"),
        )
        out = StringIO()
        call_command("backfill_lot_opening", stdout=out)
        self.assertIn("WARNING", out.getvalue())
        # No lots should be created for negative SOH
        # (positive from receipt not given here, so only the negative row)
        lots = InventoryLotBalance.objects.filter(org_item=self.lot_item)
        self.assertEqual(lots.count(), 0)

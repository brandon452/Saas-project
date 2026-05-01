from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from branches.models import Branch
from goods_receipts.models import GoodsReceipt, GoodsReceiptLine
from inventory.models import (
    BranchItem,
    InventoryClosePeriod,
    InventoryCloseSnapshot,
    InventoryCostState,
    MasterItem,
    OrgItem,
    StockLedger,
    StockOnHand,
    StockTake,
)
from inventory.services import approve_stock_take, close_period, record_stock_movement, reopen_period, start_stock_take, submit_stock_take
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


class ClosePeriodServiceTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="close-user", password="Passw0rd!")
        self.org = Organization.objects.create(name="Acme", slug="close-acme")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="MAIN",
        )
        self.item = OrgItem.objects.create(
            organization=self.org,
            master_item=MasterItem.objects.create(name="Widget", sku="CLOSE-1"),
            name="",
        )

    def _seed_stock(self, quantity="8.0000", unit_cost="11.2500"):
        return record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=self.item,
            quantity=Decimal(quantity),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal(unit_cost),
            performed_by=self.user,
            idempotency_key=f"seed-{quantity}-{unit_cost}",
        )

    def test_close_reopen_and_reclose_replace_snapshots(self):
        self._seed_stock()
        period = InventoryClosePeriod.objects.create(
            organization=self.org,
            start_date=timezone.now().date().replace(day=1),
            end_date=timezone.now().date(),
            status=InventoryClosePeriod.OPEN,
        )

        close_period(period, closed_by=self.user)
        period.refresh_from_db()
        self.assertEqual(period.status, InventoryClosePeriod.CLOSED)
        self.assertEqual(period.closed_by, self.user)
        snapshot = InventoryCloseSnapshot.objects.get(period=period, branch=self.branch, item=self.item)
        self.assertEqual(snapshot.quantity_on_hand, Decimal("8.0000"))
        self.assertEqual(snapshot.average_unit_cost, Decimal("11.2500"))
        self.assertEqual(snapshot.average_valuation, Decimal("90.0000"))

        reopen_period(period, reopened_by=self.user)
        period.refresh_from_db()
        self.assertEqual(period.status, InventoryClosePeriod.OPEN)
        self.assertEqual(period.reopened_by, self.user)

        record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=self.item,
            quantity=Decimal("-3.0000"),
            movement_type=StockLedger.MOVEMENT_ISSUE,
            performed_by=self.user,
            idempotency_key="close-issue",
        )
        close_period(period, closed_by=self.user)
        period.refresh_from_db()
        self.assertEqual(period.status, InventoryClosePeriod.CLOSED)
        self.assertEqual(InventoryCloseSnapshot.objects.filter(period=period).count(), 1)
        snapshot = InventoryCloseSnapshot.objects.get(period=period, branch=self.branch, item=self.item)
        self.assertEqual(snapshot.quantity_on_hand, Decimal("5.0000"))
        self.assertEqual(snapshot.average_valuation, Decimal("56.2500"))

    def test_close_historical_period_uses_period_end_ledger_balance(self):
        period_start = timezone.now() - timezone.timedelta(days=10)
        period_end = timezone.now() - timezone.timedelta(days=5)
        after_period = timezone.now() - timezone.timedelta(days=2)

        record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=self.item,
            quantity=Decimal("10.0000"),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal("8.0000"),
            performed_by=self.user,
            occurred_at=period_start,
            idempotency_key="historical-seed",
        )
        record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=self.item,
            quantity=Decimal("-4.0000"),
            movement_type=StockLedger.MOVEMENT_ISSUE,
            performed_by=self.user,
            occurred_at=after_period,
            idempotency_key="after-period-issue",
        )

        period = InventoryClosePeriod.objects.create(
            organization=self.org,
            start_date=period_start.date(),
            end_date=period_end.date(),
            status=InventoryClosePeriod.OPEN,
        )

        close_period(period, closed_by=self.user)

        snapshot = InventoryCloseSnapshot.objects.get(period=period, branch=self.branch, item=self.item)
        self.assertEqual(snapshot.quantity_on_hand, Decimal("10.0000"))
        self.assertEqual(snapshot.average_unit_cost, Decimal("8.0000"))
        self.assertEqual(snapshot.average_valuation, Decimal("80.0000"))

    def test_approve_stock_take_blocks_missing_avco(self):
        second_item = OrgItem.objects.create(
            organization=self.org,
            master_item=MasterItem.objects.create(name="No AVCO", sku="CLOSE-2"),
            name="",
        )
        record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=self.item,
            quantity=Decimal("4.0000"),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal("5.0000"),
            performed_by=self.user,
            idempotency_key="take-seed",
        )
        StockOnHand.objects.create(
            organization=self.org,
            branch=self.branch,
            item=second_item,
            quantity=Decimal("2.0000"),
        )
        InventoryCostState.objects.create(
            organization=self.org,
            branch=self.branch,
            item=second_item,
            average_unit_cost=None,
            latest_unit_cost=None,
        )
        BranchItem.objects.create(branch=self.branch, org_item=self.item, is_active=True)
        BranchItem.objects.create(branch=self.branch, org_item=second_item, is_active=True)
        stock_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.user)
        start_stock_take(stock_take, self.user)
        stock_take.refresh_from_db()
        stock_take.lines.get(org_item=second_item).counted_quantity = Decimal("1.0000")
        stock_take.lines.filter(org_item=second_item).update(counted_quantity=Decimal("1.0000"))
        submit_stock_take(stock_take, self.user)
        stock_take.refresh_from_db()

        with self.assertRaisesMessage(ValidationError, "have no AVCO cost basis"):
            approve_stock_take(stock_take, self.user)


class ClosePeriodApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="close-owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="close-admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="close-staff", password="Passw0rd!")
        self.parent_admin = User.objects.create_user(username="close-parent", password="Passw0rd!")

        self.org = Organization.objects.create(name="Acme", slug="close-api")
        OrganizationMember.objects.create(user=self.owner, organization=self.org, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.admin, organization=self.org, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.staff, organization=self.org, role="STAFF", is_active=True)
        ParentCompanyMember.objects.create(
            user=self.parent_admin,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
        )

        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="MAIN",
        )
        self.item = OrgItem.objects.create(
            organization=self.org,
            master_item=MasterItem.objects.create(name="Widget", sku="API-CLOSE-1"),
            name="",
        )
        record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=self.item,
            quantity=Decimal("6.0000"),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal("9.5000"),
            performed_by=self.owner,
            idempotency_key="api-close-seed",
        )

    def _host(self):
        return f"{self.org.slug}.localhost:8000"

    def _base_url(self):
        return f"/api/orgs/{self.org.id}/close-periods/"

    def test_owner_can_create_close_reopen_and_parent_admin_can_read(self):
        self.client.force_authenticate(self.owner)
        create_response = self.client.post(
            self._base_url(),
            {
                "start_date": str(timezone.now().date().replace(day=1)),
                "end_date": str(timezone.now().date()),
                "notes": "Month end",
            },
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(create_response.status_code, 201)
        period_id = create_response.data["id"]
        self.assertEqual(create_response.data["status"], InventoryClosePeriod.OPEN)

        overlap = self.client.post(
            self._base_url(),
            {
                "start_date": str(timezone.now().date().replace(day=1)),
                "end_date": str(timezone.now().date()),
            },
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(overlap.status_code, 400)

        close_response = self.client.post(
            f"{self._base_url()}{period_id}/close/",
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(close_response.status_code, 200)
        self.assertEqual(close_response.data["status"], InventoryClosePeriod.CLOSED)

        snapshots = self.client.get(
            f"{self._base_url()}{period_id}/snapshots/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(snapshots.status_code, 200)
        self.assertEqual(len(snapshots.data), 1)

        reopen_response = self.client.post(
            f"{self._base_url()}{period_id}/reopen/",
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(reopen_response.status_code, 200)
        self.assertEqual(reopen_response.data["status"], InventoryClosePeriod.OPEN)

        self.client.force_authenticate(self.parent_admin)
        list_response = self.client.get(self._base_url(), HTTP_HOST=self._host())
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data[0]["id"], period_id)

    def test_staff_cannot_mutate_periods(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            self._base_url(),
            {
                "start_date": str(timezone.now().date().replace(day=1)),
                "end_date": str(timezone.now().date()),
            },
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 403)

    def test_create_rejects_future_end_date(self):
        self.client.force_authenticate(self.owner)
        future = timezone.now().date() + timezone.timedelta(days=1)
        response = self.client.post(
            self._base_url(),
            {
                "start_date": str(timezone.now().date()),
                "end_date": str(future),
            },
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("end_date cannot be in the future", str(response.data))


class BackfillCostStateCommandTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="backfill-user", password="Passw0rd!")
        self.org = Organization.objects.create(name="Acme", slug="backfill-acme")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="MAIN",
        )
        self.receipt_only_item = OrgItem.objects.create(
            organization=self.org,
            master_item=MasterItem.objects.create(name="Receipt Only", sku="BF-1"),
            name="",
        )
        self.mixed_item = OrgItem.objects.create(
            organization=self.org,
            master_item=MasterItem.objects.create(name="Mixed", sku="BF-2"),
            name="",
        )
        self.no_receipt_item = OrgItem.objects.create(
            organization=self.org,
            master_item=MasterItem.objects.create(name="No Receipt", sku="BF-3"),
            name="",
        )

        early = GoodsReceipt.objects.create(
            organization=self.org,
            receipt_type=GoodsReceipt.DIRECT_RECEIPT,
            branch=self.branch,
            received_by=self.user,
        )
        GoodsReceipt.objects.filter(pk=early.pk).update(received_at=timezone.now() - timezone.timedelta(days=5))
        early.refresh_from_db()
        late = GoodsReceipt.objects.create(
            organization=self.org,
            receipt_type=GoodsReceipt.DIRECT_RECEIPT,
            branch=self.branch,
            received_by=self.user,
        )
        GoodsReceipt.objects.filter(pk=late.pk).update(received_at=timezone.now() - timezone.timedelta(days=1))
        late.refresh_from_db()

        GoodsReceiptLine.objects.create(
            receipt=early,
            item=self.receipt_only_item,
            quantity_received=4,
            unit_cost=Decimal("10.00"),
        )
        GoodsReceiptLine.objects.create(
            receipt=late,
            item=self.receipt_only_item,
            quantity_received=6,
            unit_cost=Decimal("12.00"),
        )

        GoodsReceiptLine.objects.create(
            receipt=early,
            item=self.mixed_item,
            quantity_received=5,
            unit_cost=Decimal("7.00"),
        )
        GoodsReceiptLine.objects.create(
            receipt=late,
            item=self.mixed_item,
            quantity_received=5,
            unit_cost=Decimal("9.00"),
        )
        StockLedger.objects.create(
            organization=self.org,
            branch=self.branch,
            item=self.mixed_item,
            quantity=Decimal("-1.0000"),
            movement_type=StockLedger.MOVEMENT_ISSUE,
            occurred_at=timezone.now() - timezone.timedelta(days=3),
        )
        StockOnHand.objects.create(
            organization=self.org,
            branch=self.branch,
            item=self.no_receipt_item,
            quantity=Decimal("2.0000"),
        )

    def test_dry_run_reports_counts_without_writing(self):
        stdout = StringIO()
        call_command("backfill_cost_state", "--dry-run", stdout=stdout)
        output = stdout.getvalue()

        self.assertIn("Items bootstrapped: 1", output)
        self.assertIn("Items left null: 1", output)
        self.assertIn("Items with no receipt history: 1", output)
        self.assertFalse(InventoryCostState.objects.exists())

    def test_command_bootstraps_and_is_idempotent(self):
        call_command("backfill_cost_state")
        receipt_state = InventoryCostState.objects.get(
            organization=self.org,
            branch=self.branch,
            item=self.receipt_only_item,
        )
        mixed_state = InventoryCostState.objects.get(
            organization=self.org,
            branch=self.branch,
            item=self.mixed_item,
        )
        no_receipt_state = InventoryCostState.objects.get(
            organization=self.org,
            branch=self.branch,
            item=self.no_receipt_item,
        )

        self.assertEqual(receipt_state.average_unit_cost, Decimal("11.2000"))
        self.assertEqual(receipt_state.latest_unit_cost, Decimal("12.0000"))
        self.assertIsNone(mixed_state.average_unit_cost)
        self.assertIsNone(no_receipt_state.average_unit_cost)

        call_command("backfill_cost_state")
        self.assertEqual(InventoryCostState.objects.count(), 3)

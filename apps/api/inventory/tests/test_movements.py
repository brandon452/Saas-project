from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import BranchItem, InventoryClosePeriod, InventoryCostState, MasterItem, OrgItem, StockLedger, StockOnHand
from inventory.services import record_stock_movement
from tenancy.models import Organization, OrganizationMember


class StockMovementServiceTests(TransactionTestCase):
    reset_sequences = True

    def _create_org_item(self, organization, name, sku):
        master_item = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.for_org(organization).create(
            organization=organization,
            master_item=master_item,
            name="",
        )

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="svc_user", password="Passw0rd!")

        self.org = Organization.objects.create(name="Acme", slug="acme")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="MAIN",
        )
        self.item = self._create_org_item(self.org, "Lavender Oil", "ACME-001")
        BranchItem.objects.create(org_item=self.item, branch=self.branch, is_active=True)

    def _receipt(self, quantity, *, unit_cost="10.0000", item=None, occurred_at=None, idempotency_key=None):
        return record_stock_movement(
            self.org,
            self.branch,
            item or self.item,
            Decimal(quantity),
            StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal(unit_cost),
            performed_by=self.user,
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
        )

    def test_receipt_issue_and_zero_stock_retention_follow_avco_rules(self):
        first, _ = self._receipt("10.0000", unit_cost="10.0000", idempotency_key="r1")
        second, _ = self._receipt("10.0000", unit_cost="20.0000", idempotency_key="r2")
        issue, _ = record_stock_movement(
            self.org,
            self.branch,
            self.item,
            Decimal("-5.0000"),
            StockLedger.MOVEMENT_ISSUE,
            performed_by=self.user,
            idempotency_key="i1",
        )
        drain, _ = record_stock_movement(
            self.org,
            self.branch,
            self.item,
            Decimal("-15.0000"),
            StockLedger.MOVEMENT_ISSUE,
            performed_by=self.user,
            idempotency_key="i2",
        )

        cost_state = InventoryCostState.objects.get(
            organization=self.org,
            branch=self.branch,
            item=self.item,
        )
        self.assertEqual(first.unit_cost, Decimal("10.0000"))
        self.assertEqual(first.value_delta, Decimal("100.0000"))
        self.assertEqual(second.unit_cost, Decimal("20.0000"))
        self.assertEqual(second.value_delta, Decimal("200.0000"))
        self.assertEqual(issue.unit_cost, Decimal("15.0000"))
        self.assertEqual(issue.value_delta, Decimal("-75.0000"))
        self.assertEqual(drain.unit_cost, Decimal("15.0000"))
        self.assertEqual(drain.value_delta, Decimal("-225.0000"))
        self.assertEqual(cost_state.average_unit_cost, Decimal("15.0000"))
        self.assertEqual(cost_state.latest_unit_cost, Decimal("20.0000"))
        self.assertEqual(
            StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item).quantity,
            Decimal("0.0000"),
        )

        reseed, _ = self._receipt("4.0000", unit_cost="7.5000", idempotency_key="r3")
        cost_state.refresh_from_db()
        self.assertEqual(reseed.unit_cost, Decimal("7.5000"))
        self.assertEqual(cost_state.average_unit_cost, Decimal("7.5000"))
        self.assertEqual(cost_state.latest_unit_cost, Decimal("7.5000"))

    def test_positive_adjustment_requires_existing_avco(self):
        with self.assertRaises(ValidationError) as ctx:
            record_stock_movement(
                self.org,
                self.branch,
                self.item,
                Decimal("3.0000"),
                StockLedger.MOVEMENT_ADJUSTMENT,
                performed_by=self.user,
            )
        self.assertIn("Positive stock additions require a cost basis", str(ctx.exception))

    def test_issue_and_adjustment_reject_caller_unit_cost(self):
        self._receipt("5.0000", unit_cost="9.0000", idempotency_key="seed")

        with self.assertRaises(ValidationError) as issue_ctx:
            record_stock_movement(
                self.org,
                self.branch,
                self.item,
                Decimal("-1.0000"),
                StockLedger.MOVEMENT_ISSUE,
                unit_cost=Decimal("1.0000"),
                performed_by=self.user,
            )
        self.assertIn("must not be provided for ISSUE", str(issue_ctx.exception))

        with self.assertRaises(ValidationError) as adjustment_ctx:
            record_stock_movement(
                self.org,
                self.branch,
                self.item,
                Decimal("-1.0000"),
                StockLedger.MOVEMENT_ADJUSTMENT,
                unit_cost=Decimal("1.0000"),
                performed_by=self.user,
            )
        self.assertIn("must not be provided for ADJUSTMENT", str(adjustment_ctx.exception))

    def test_sign_validation_messages(self):
        with self.assertRaisesMessage(ValidationError, "RECEIPT quantity must be positive."):
            record_stock_movement(
                self.org,
                self.branch,
                self.item,
                Decimal("-1.0000"),
                StockLedger.MOVEMENT_RECEIPT,
                unit_cost=Decimal("5.0000"),
                performed_by=self.user,
            )

        self._receipt("5.0000", unit_cost="5.0000", idempotency_key="seed-2")
        with self.assertRaisesMessage(ValidationError, "ISSUE quantity must be negative."):
            record_stock_movement(
                self.org,
                self.branch,
                self.item,
                Decimal("1.0000"),
                StockLedger.MOVEMENT_ISSUE,
                performed_by=self.user,
            )

    def test_period_close_blocks_movements_for_its_dates(self):
        period = InventoryClosePeriod.objects.create(
            organization=self.org,
            start_date=timezone.now().date(),
            end_date=timezone.now().date(),
            status=InventoryClosePeriod.CLOSED,
        )

        with self.assertRaisesMessage(ValidationError, f"Period {period.start_date}"):
            self._receipt("1.0000", unit_cost="5.0000", idempotency_key="blocked")

    def test_idempotent_retry_returns_original_row(self):
        first, created_first = self._receipt("3.0000", unit_cost="8.0000", idempotency_key="same-key")
        second, created_second = self._receipt("9.0000", unit_cost="99.0000", idempotency_key="same-key")

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(
            StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item).quantity,
            Decimal("3.0000"),
        )

    def test_idempotent_retry_returns_original_row_after_period_closes(self):
        occurred_at = timezone.now()
        first, created_first = self._receipt(
            "3.0000",
            unit_cost="8.0000",
            occurred_at=occurred_at,
            idempotency_key="closed-retry",
        )
        InventoryClosePeriod.objects.create(
            organization=self.org,
            start_date=occurred_at.date(),
            end_date=occurred_at.date(),
            status=InventoryClosePeriod.CLOSED,
        )

        second, created_second = self._receipt(
            "9.0000",
            unit_cost="99.0000",
            occurred_at=occurred_at,
            idempotency_key="closed-retry",
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(
            StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item).quantity,
            Decimal("3.0000"),
        )


class StockMovementApiTests(APITestCase):
    def _create_org_item(self, organization, name, sku):
        master_item = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.for_org(organization).create(
            organization=organization,
            master_item=master_item,
            name="",
        )

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="api_user", password="Passw0rd!")
        self.org = Organization.objects.create(name="Acme", slug="acme")
        OrganizationMember.objects.create(user=self.user, organization=self.org, role="ADMIN", is_active=True)

        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="MAIN",
        )
        self.item = self._create_org_item(self.org, "Lavender Oil", "ACME-001")
        BranchItem.objects.create(org_item=self.item, branch=self.branch, is_active=True)

    def _url(self):
        return f"/api/orgs/{self.org.id}/inventory/movements/"

    def test_list_rejects_invalid_item_filter_uuid(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(
            f"{self._url()}?item=not-a-uuid",
            HTTP_HOST="acme.localhost:8000",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["item"][0], "Enter a valid UUID.")

    def _post(self, payload):
        self.client.force_authenticate(self.user)
        return self.client.post(
            self._url(),
            payload,
            format="json",
            HTTP_HOST="acme.localhost:8000",
            HTTP_X_BRANCH_ID=str(self.branch.id),
        )

    def test_receipt_requires_unit_cost(self):
        response = self._post(
            {
                "item": str(self.item.id),
                "quantity": "1.0000",
                "movement_type": "RECEIPT",
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("unit_cost is required for RECEIPT movements.", response.data["detail"][0])

    def test_receipt_with_unit_cost_is_idempotent(self):
        payload = {
            "item": str(self.item.id),
            "quantity": "2.0000",
            "movement_type": "RECEIPT",
            "unit_cost": "11.2500",
            "idempotency_key": "api-idem-key",
        }
        first = self._post(payload)
        second = self._post(payload)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["id"], second.data["id"])

    def test_receipt_rejects_non_positive_unit_cost(self):
        response = self._post(
            {
                "item": str(self.item.id),
                "quantity": "1.0000",
                "movement_type": "RECEIPT",
                "unit_cost": "0.0000",
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["unit_cost"][0], "unit_cost must be greater than zero.")

    def test_list_rejects_invalid_from_date(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(
            f"{self._url()}?from_date=not-a-date",
            HTTP_HOST="acme.localhost:8000",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["from_date"][0], "Date has wrong format. Use YYYY-MM-DD.")

    def test_list_rejects_invalid_to_date(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(
            f"{self._url()}?to_date=2026-99-99",
            HTTP_HOST="acme.localhost:8000",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["to_date"][0], "Date has wrong format. Use YYYY-MM-DD.")

    def test_create_rejects_inactive_item(self):
        self.item.is_active = False
        self.item.save(update_fields=["is_active"])
        response = self._post(
            {
                "item": str(self.item.id),
                "quantity": "1.0000",
                "movement_type": "RECEIPT",
                "unit_cost": "1.0000",
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("item", response.data)

    def test_create_rejects_item_not_enabled_for_branch(self):
        BranchItem.objects.filter(org_item=self.item, branch=self.branch).delete()
        response = self._post(
            {
                "item": str(self.item.id),
                "quantity": "1.0000",
                "movement_type": "RECEIPT",
                "unit_cost": "1.0000",
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["item"][0], "This item is not enabled for the selected branch.")

    def test_create_rejects_item_with_inactive_branch_item(self):
        branch_item = BranchItem.objects.get(org_item=self.item, branch=self.branch)
        branch_item.is_active = False
        branch_item.save(update_fields=["is_active"])
        response = self._post(
            {
                "item": str(self.item.id),
                "quantity": "1.0000",
                "movement_type": "RECEIPT",
                "unit_cost": "1.0000",
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["item"][0], "This item is not enabled for the selected branch.")

    def test_create_accepts_item_with_active_branch_item(self):
        response = self._post(
            {
                "item": str(self.item.id),
                "quantity": "1.0000",
                "movement_type": "RECEIPT",
                "unit_cost": "1.0000",
            }
        )
        self.assertEqual(response.status_code, 201)

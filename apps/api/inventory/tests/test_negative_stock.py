from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import BranchItem, MasterItem, OrgItem, StockOnHand
from inventory.services import record_stock_movement
from tenancy.models import Organization, OrganizationMember


class NegativeStockTestDataMixin:
    def _create_org_item(self, organization, name, sku, *, item_name=""):
        master_item = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.for_org(organization).create(
            organization=organization,
            master_item=master_item,
            name=item_name,
        )

    def setUp(self):
        User = get_user_model()
        suffix = uuid4().hex[:8]
        self.user = User.objects.create_user(username=f"negative_stock_user_{suffix}", password="Passw0rd!")
        self.org = Organization.objects.create(name=f"Acme {suffix}", slug=f"acme-negative-{suffix}")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="MAIN",
        )
        self.item = self._create_org_item(self.org, "Lavender Oil", "NEG-001")

    def _record(self, quantity, movement_type="ADJUSTMENT"):
        kwargs = {}
        if movement_type == "RECEIPT":
            kwargs["unit_cost"] = Decimal("10.0000")
        return record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=self.item,
            quantity=Decimal(quantity),
            movement_type=movement_type,
            performed_by=self.user,
            **kwargs,
        )


class NegativeStockServiceTests(NegativeStockTestDataMixin, TestCase):
    def test_stock_out_within_available_quantity_succeeds(self):
        self._record("5.0000", movement_type="RECEIPT")

        ledger, created = self._record("-3.0000")

        self.assertTrue(created)
        self.assertEqual(ledger.quantity, Decimal("-3.0000"))
        self.assertEqual(
            StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item).quantity,
            Decimal("2.0000"),
        )

    def test_stock_out_exactly_equal_to_available_succeeds(self):
        self._record("5.0000", movement_type="RECEIPT")

        self._record("-5.0000")

        self.assertEqual(
            StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item).quantity,
            Decimal("0.0000"),
        )

    def test_stock_out_exceeding_available_is_rejected(self):
        self._record("5.0000", movement_type="RECEIPT")

        with self.assertRaisesMessage(
            ValidationError,
            "Insufficient stock. Available: 5.0000, requested: 6.0000.",
        ):
            self._record("-6.0000")

        self.assertEqual(
            StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item).quantity,
            Decimal("5.0000"),
        )

    def test_stock_out_exceeding_available_succeeds_when_org_allows_negative_stock(self):
        self._record("5.0000", movement_type="RECEIPT")
        self.org.allow_negative_stock = True
        self.org.save(update_fields=["allow_negative_stock"])

        ledger, created = self._record("-6.0000")

        self.assertTrue(created)
        self.assertEqual(ledger.quantity, Decimal("-6.0000"))
        self.assertEqual(
            StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item).quantity,
            Decimal("-1.0000"),
        )

    def test_stock_out_without_stock_on_hand_row_is_rejected(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Insufficient stock. Available: 0, requested: 1.0000.",
        ):
            self._record("-1.0000")

        self.assertFalse(StockOnHand.objects.for_org(self.org).filter(branch=self.branch, item=self.item).exists())

    def test_stock_in_movement_always_succeeds(self):
        ledger, created = self._record("7.0000", movement_type="RECEIPT")

        self.assertTrue(created)
        self.assertEqual(ledger.quantity, Decimal("7.0000"))
        self.assertEqual(
            StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item).quantity,
            Decimal("7.0000"),
        )

    def test_zero_quantity_is_rejected_before_stock_check(self):
        with patch("inventory.services.StockOnHand.objects.for_org") as for_org:
            with self.assertRaisesMessage(ValidationError, "Movement quantity cannot be zero."):
                self._record("0.0000")

        for_org.assert_not_called()

    def test_record_stock_movement_is_transactional(self):
        self.assertIsNotNone(getattr(record_stock_movement, "__wrapped__", None))

    def test_negative_quantity_uses_select_for_update(self):
        self._record("5.0000", movement_type="RECEIPT")
        stock = StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item)

        with patch("inventory.services.StockOnHand.objects.for_org") as for_org:
            queryset = for_org.return_value
            locked = queryset.select_for_update.return_value
            locked.filter.return_value.first.return_value = stock

            self._record("-1.0000")

        queryset.select_for_update.assert_called_once_with()
        locked.filter.assert_called_once_with(organization=self.org, branch=self.branch, item=self.item)

class NegativeStockConcurrencyTests(NegativeStockTestDataMixin, TransactionTestCase):
    reset_sequences = True

    def test_concurrent_stock_out_prevents_negative_inventory(self):
        self._record("5.0000", movement_type="RECEIPT")

        results = []

        def worker():
            close_old_connections()
            try:
                ledger, created = self._record("-4.0000")
                results.append(("success", ledger.id, created))
            except ValidationError as exc:
                results.append(("error", exc.messages))
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(lambda _: worker(), range(2)))
        close_old_connections()
        connections.close_all()

        successes = [row for row in results if row[0] == "success"]
        errors = [row for row in results if row[0] == "error"]

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("Insufficient stock. Available: 1.0000, requested: 4.0000.", errors[0][1])
        self.assertEqual(
            StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item).quantity,
            Decimal("1.0000"),
        )


class NegativeStockApiTests(NegativeStockTestDataMixin, APITestCase):
    def setUp(self):
        User = get_user_model()
        suffix = uuid4().hex[:8]
        self.user = User.objects.create_user(username=f"negative_stock_api_{suffix}", password="Passw0rd!")
        self.org = Organization.objects.create(name=f"Acme Api {suffix}", slug=f"acme-negative-api-{suffix}")
        OrganizationMember.objects.create(user=self.user, organization=self.org, role="ADMIN", is_active=True)
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="MAIN",
        )
        self.item = self._create_org_item(self.org, "Lavender Oil", "NEG-API-001")
        BranchItem.objects.create(org_item=self.item, branch=self.branch, is_active=True)
        self.client.force_authenticate(self.user)

    def _url(self):
        return f"/api/orgs/{self.org.id}/inventory/movements/"

    def _post(self, quantity, movement_type="ADJUSTMENT"):
        return self.client.post(
            self._url(),
            {
                "item": str(self.item.id),
                "quantity": quantity,
                "movement_type": movement_type,
            },
            format="json",
            HTTP_HOST=f"{self.org.slug}.localhost:8000",
            HTTP_X_BRANCH_ID=str(self.branch.id),
        )

    def test_negative_stock_violation_returns_http_400_with_detail(self):
        record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=self.item,
            quantity=Decimal("5.0000"),
            movement_type="RECEIPT",
            unit_cost=Decimal("10.0000"),
            performed_by=self.user,
        )

        response = self._post("-6.0000")

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)
        self.assertIn("Available: 5.0000", response.data["detail"][0])
        self.assertIn("requested: 6.0000", response.data["detail"][0])

    def test_zero_quantity_returns_http_400_with_detail(self):
        response = self._post("0.0000")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], ["Movement quantity cannot be zero."])

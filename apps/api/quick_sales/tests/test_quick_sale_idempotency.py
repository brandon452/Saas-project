from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import BranchItem, MasterItem, OrgItem, StockLedger
from inventory.services import record_stock_movement
from quick_sales.models import QuickSale
from tenancy.models import Organization, OrganizationMember


class QuickSaleIdempotencyTests(APITestCase):
    def _create_org_item(self, organization, name, sku):
        master = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.for_org(organization).create(
            organization=organization, master_item=master
        )

    def _receipt(self, item, qty, cost, key):
        record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=item,
            quantity=Decimal(qty),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal(cost),
            performed_by=self.owner,
            idempotency_key=key,
        )

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="qsi_owner", password="Passw0rd!")

        self.org = Organization.objects.create(name="QSIOrg", slug="qsi-org")
        self.other_org = Organization.objects.create(name="QSIOther", slug="qsi-other-org")

        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Main", code="MAIN"
        )
        self.other_branch = Branch.objects.for_org(self.other_org).create(
            organization=self.other_org, name="Other", code="OTH"
        )

        OrganizationMember.objects.create(
            user=self.owner, organization=self.org, role="OWNER", is_active=True
        )

        self.item = self._create_org_item(self.org, "Widget", "QSI-W")
        BranchItem.objects.create(branch=self.branch, org_item=self.item, is_active=True)
        self._receipt(self.item, "10", "5.00", "setup-receipt")

        self.other_owner = User.objects.create_user(username="qsi_other_owner", password="Passw0rd!")
        OrganizationMember.objects.create(
            user=self.other_owner, organization=self.other_org, role="OWNER", is_active=True
        )
        self.other_item = self._create_org_item(self.other_org, "Other Widget", "QSI-O")
        BranchItem.objects.create(branch=self.other_branch, org_item=self.other_item, is_active=True)
        record_stock_movement(
            org=self.other_org,
            branch=self.other_branch,
            item=self.other_item,
            quantity=Decimal("10"),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal("5.00"),
            performed_by=self.other_owner,
            idempotency_key="other-setup-receipt",
        )

    def _url(self):
        return f"/api/orgs/{self.org.id}/quick-sales/"

    def _payload(self, *, idempotency_key=None):
        p = {
            "branch": str(self.branch.id),
            "customer_name": "",
            "notes": "",
            "lines": [{"item": str(self.item.id), "quantity": "1", "unit_price": "9.99"}],
        }
        if idempotency_key is not None:
            p["idempotency_key"] = idempotency_key
        return p

    def test_create_without_idempotency_key_returns_201(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.post(self._url(), self._payload(), format="json")
        self.assertEqual(resp.status_code, 201)

    def test_create_with_idempotency_key_returns_201(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.post(self._url(), self._payload(idempotency_key="idem-001"), format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertIsNotNone(resp.json()["id"])

    def test_replay_same_idempotency_key_returns_200(self):
        self.client.force_authenticate(user=self.owner)
        first = self.client.post(self._url(), self._payload(idempotency_key="idem-002"), format="json")
        self.assertEqual(first.status_code, 201)

        second = self.client.post(self._url(), self._payload(idempotency_key="idem-002"), format="json")
        self.assertEqual(second.status_code, 200)

    def test_replay_returns_same_sale_id(self):
        self.client.force_authenticate(user=self.owner)
        first = self.client.post(self._url(), self._payload(idempotency_key="idem-003"), format="json")
        second = self.client.post(self._url(), self._payload(idempotency_key="idem-003"), format="json")
        self.assertEqual(first.json()["id"], second.json()["id"])

    def test_replay_does_not_create_duplicate_sale(self):
        self.client.force_authenticate(user=self.owner)
        self.client.post(self._url(), self._payload(idempotency_key="idem-004"), format="json")
        self.client.post(self._url(), self._payload(idempotency_key="idem-004"), format="json")
        count = QuickSale.objects.filter(organization=self.org, idempotency_key="idem-004").count()
        self.assertEqual(count, 1)

    def test_replay_does_not_create_duplicate_stock_movement(self):
        self.client.force_authenticate(user=self.owner)
        before = StockLedger.objects.filter(organization=self.org, item=self.item).count()
        self.client.post(self._url(), self._payload(idempotency_key="idem-005"), format="json")
        self.client.post(self._url(), self._payload(idempotency_key="idem-005"), format="json")
        after = StockLedger.objects.filter(organization=self.org, item=self.item).count()
        # Only 1 movement from receipt setup + 1 from sale = 2 total, not 3
        self.assertEqual(after - before, 1)

    def test_different_idempotency_keys_create_separate_sales(self):
        self.client.force_authenticate(user=self.owner)
        r1 = self.client.post(self._url(), self._payload(idempotency_key="idem-a"), format="json")
        r2 = self.client.post(self._url(), self._payload(idempotency_key="idem-b"), format="json")
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertNotEqual(r1.json()["id"], r2.json()["id"])

    def test_idempotency_key_scoped_to_org(self):
        """Same idempotency key in two orgs should not clash."""
        self.client.force_authenticate(user=self.owner)
        r1 = self.client.post(self._url(), self._payload(idempotency_key="shared-key"), format="json")
        self.assertEqual(r1.status_code, 201)

        self.client.force_authenticate(user=self.other_owner)
        other_payload = {
            "branch": str(self.other_branch.id),
            "customer_name": "",
            "notes": "",
            "idempotency_key": "shared-key",
            "lines": [{"item": str(self.other_item.id), "quantity": "1", "unit_price": "9.99"}],
        }
        r2 = self.client.post(
            f"/api/orgs/{self.other_org.id}/quick-sales/", other_payload, format="json"
        )
        self.assertEqual(r2.status_code, 201)
        self.assertNotEqual(r1.json()["id"], r2.json()["id"])

    def test_null_idempotency_key_treated_as_no_key(self):
        """Explicitly passing null should behave like omitting the key."""
        self.client.force_authenticate(user=self.owner)
        r1 = self.client.post(
            self._url(), self._payload(idempotency_key=None), format="json"
        )
        r2 = self.client.post(
            self._url(), self._payload(idempotency_key=None), format="json"
        )
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertNotEqual(r1.json()["id"], r2.json()["id"])

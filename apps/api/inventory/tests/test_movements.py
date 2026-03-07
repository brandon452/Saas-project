from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import Item, StockLedger, StockOnHand
from inventory.services import record_stock_movement
from tenancy.models import Organization, OrganizationMember


class StockMovementServiceTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="svc_user", password="Passw0rd!")

        self.org = Organization.objects.create(name="Acme", slug="acme")
        self.other_org = Organization.objects.create(name="Globex", slug="globex")

        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="MAIN",
        )
        self.other_branch = Branch.objects.for_org(self.other_org).create(
            organization=self.other_org,
            name="Other",
            code="OTH",
        )

        self.item = Item.objects.for_org(self.org).create(
            organization=self.org,
            name="Lavender Oil",
            sku="ACME-001",
        )
        self.other_item = Item.objects.for_org(self.org).create(
            organization=self.org,
            name="Tea Tree Oil",
            sku="ACME-002",
        )
        self.item_other_org = Item.objects.for_org(self.other_org).create(
            organization=self.other_org,
            name="Globex Item",
            sku="GLOBEX-001",
        )

    def test_audit_metadata_persistence(self):
        occurred_at = timezone.now() - timezone.timedelta(days=1)
        ledger, created = record_stock_movement(
            self.org,
            self.branch,
            self.item,
            Decimal("-2.0000"),
            "ADJUSTMENT",
            performed_by=self.user,
            reference_type="STOCK_COUNT",
            reference_id="count_2026_03_06_001",
            reason="Cycle count variance",
            occurred_at=occurred_at,
            idempotency_key="acme-adjustment-1",
        )

        self.assertTrue(created)
        self.assertEqual(ledger.performed_by_id, self.user.id)
        self.assertEqual(ledger.reference_type, "STOCK_COUNT")
        self.assertEqual(ledger.reference_id, "count_2026_03_06_001")
        self.assertEqual(ledger.reason, "Cycle count variance")
        self.assertEqual(ledger.occurred_at, occurred_at)
        self.assertEqual(ledger.idempotency_key, "acme-adjustment-1")

    def test_occurred_at_default_and_explicit(self):
        before = timezone.now()
        ledger_default, _ = record_stock_movement(
            self.org,
            self.branch,
            self.item,
            Decimal("1.0000"),
            "RECEIPT",
        )
        after = timezone.now()
        self.assertIsNotNone(ledger_default.occurred_at)
        self.assertGreaterEqual(ledger_default.occurred_at, before)
        self.assertLessEqual(ledger_default.occurred_at, after)

        explicit_time = timezone.now() - timezone.timedelta(days=2)
        ledger_explicit, _ = record_stock_movement(
            self.org,
            self.branch,
            self.item,
            Decimal("1.0000"),
            "RECEIPT",
            occurred_at=explicit_time,
        )
        self.assertEqual(ledger_explicit.occurred_at, explicit_time)

    def test_idempotent_retry_single_apply(self):
        key = "idem-retry-1"
        first, created1 = record_stock_movement(
            self.org,
            self.branch,
            self.item,
            Decimal("3.0000"),
            "RECEIPT",
            idempotency_key=key,
        )
        second, created2 = record_stock_movement(
            self.org,
            self.branch,
            self.item,
            Decimal("999.0000"),
            "RECEIPT",
            idempotency_key=key,
        )

        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(first.id, second.id)
        soh = StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item)
        self.assertEqual(soh.quantity, Decimal("3.0000"))
        self.assertEqual(
            StockLedger.objects.for_org(self.org).filter(idempotency_key=key).count(),
            1,
        )

    def test_concurrent_idempotent_requests(self):
        key = "idem-concurrent-1"

        def worker():
            close_old_connections()
            try:
                record_stock_movement(
                    self.org,
                    self.branch,
                    self.item,
                    Decimal("2.0000"),
                    "RECEIPT",
                    idempotency_key=key,
                )
            except Exception:
                pass
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as ex:
            list(ex.map(lambda _: worker(), range(2)))

        self.assertEqual(StockLedger.objects.for_org(self.org).filter(idempotency_key=key).count(), 1)
        soh = StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item)
        self.assertEqual(soh.quantity, Decimal("2.0000"))

    def test_idempotency_key_is_org_scoped(self):
        key = "same-key-different-org"
        l1, _ = record_stock_movement(
            self.org,
            self.branch,
            self.item,
            Decimal("1.0000"),
            "RECEIPT",
            idempotency_key=key,
        )
        l2, _ = record_stock_movement(
            self.other_org,
            self.other_branch,
            self.item_other_org,
            Decimal("1.0000"),
            "RECEIPT",
            idempotency_key=key,
        )
        self.assertNotEqual(l1.organization_id, l2.organization_id)

    def test_no_idempotency_key_allows_multiple_writes(self):
        record_stock_movement(self.org, self.branch, self.item, Decimal("1.0000"), "RECEIPT")
        record_stock_movement(self.org, self.branch, self.item, Decimal("1.0000"), "RECEIPT")
        soh = StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item)
        self.assertEqual(soh.quantity, Decimal("2.0000"))
        self.assertEqual(StockLedger.objects.for_org(self.org).filter(item=self.item).count(), 2)

    def test_key_reuse_returns_original_movement_unchanged(self):
        key = "reuse-key"
        first, _ = record_stock_movement(
            self.org,
            self.branch,
            self.item,
            Decimal("4.0000"),
            "RECEIPT",
            idempotency_key=key,
        )
        second, created_second = record_stock_movement(
            self.org,
            self.branch,
            self.other_item,
            Decimal("9.0000"),
            "ADJUSTMENT",
            idempotency_key=key,
        )

        self.assertFalse(created_second)
        self.assertEqual(first.id, second.id)
        soh = StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item)
        self.assertEqual(soh.quantity, Decimal("4.0000"))

    def test_stock_consistency_without_idempotency_still_holds(self):
        def worker():
            close_old_connections()
            try:
                record_stock_movement(
                    self.org,
                    self.branch,
                    self.item,
                    Decimal("1.0000"),
                    "RECEIPT",
                )
            finally:
                connections.close_all()

        runs = 20
        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(lambda _: worker(), range(runs)))

        soh = StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item)
        self.assertEqual(soh.quantity, Decimal("20.0000"))


class StockMovementApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="api_user", password="Passw0rd!")
        self.other_user = User.objects.create_user(username="other_user", password="Passw0rd!")

        self.org = Organization.objects.create(name="Acme", slug="acme")
        self.other_org = Organization.objects.create(name="Globex", slug="globex")

        OrganizationMember.objects.create(user=self.user, organization=self.org, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.other_user, organization=self.other_org, role="ADMIN", is_active=True)

        self.branch = Branch.objects.for_org(self.org).create(organization=self.org, name="Main", code="MAIN")
        self.other_branch = Branch.objects.for_org(self.other_org).create(
            organization=self.other_org,
            name="Other",
            code="OTH",
        )

        self.item = Item.objects.for_org(self.org).create(
            organization=self.org,
            name="Lavender Oil",
            sku="ACME-001",
        )

    def _url(self):
        return "/api/inventory/movements/"

    def test_validation_takes_priority_over_idempotency(self):
        self.client.force_authenticate(self.user)
        key = "known-key"
        payload = {
            "item": str(self.item.id),
            "quantity": "1.0000",
            "movement_type": "RECEIPT",
            "idempotency_key": key,
        }
        first = self.client.post(
            self._url(),
            payload,
            format="json",
            HTTP_HOST="acme.localhost:8000",
            HTTP_X_BRANCH_ID=str(self.branch.id),
        )
        self.assertEqual(first.status_code, 201)

        invalid_payload = {
            "movement_type": "RECEIPT",
            "idempotency_key": key,
        }
        second = self.client.post(
            self._url(),
            invalid_payload,
            format="json",
            HTTP_HOST="acme.localhost:8000",
            HTTP_X_BRANCH_ID=str(self.branch.id),
        )
        self.assertEqual(second.status_code, 400)

    def test_performed_by_cannot_be_spoofed(self):
        self.client.force_authenticate(self.user)
        payload = {
            "item": str(self.item.id),
            "quantity": "1.0000",
            "movement_type": "RECEIPT",
            "idempotency_key": "spoof-key",
            "performed_by": self.other_user.id,
        }
        res = self.client.post(
            self._url(),
            payload,
            format="json",
            HTTP_HOST="acme.localhost:8000",
            HTTP_X_BRANCH_ID=str(self.branch.id),
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["performed_by"], self.user.id)

    def test_deduplicated_request_returns_200(self):
        self.client.force_authenticate(self.user)
        payload = {
            "item": str(self.item.id),
            "quantity": "2.0000",
            "movement_type": "RECEIPT",
            "idempotency_key": "api-idem-key",
        }
        first = self.client.post(
            self._url(),
            payload,
            format="json",
            HTTP_HOST="acme.localhost:8000",
            HTTP_X_BRANCH_ID=str(self.branch.id),
        )
        second = self.client.post(
            self._url(),
            payload,
            format="json",
            HTTP_HOST="acme.localhost:8000",
            HTTP_X_BRANCH_ID=str(self.branch.id),
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["id"], second.data["id"])

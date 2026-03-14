from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import Item, StockLedger, StockOnHand
from inventory.services import record_stock_movement
from tenancy.models import Organization, OrganizationMember


class InventoryPhase3ApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.acme_user = User.objects.create_user(username="acme_user", password="Passw0rd!")
        self.globex_user = User.objects.create_user(username="globex_user", password="Passw0rd!")
        self.no_membership_user = User.objects.create_user(username="stranger", password="Passw0rd!")

        self.acme = Organization.objects.create(name="Acme", slug="acme")
        self.globex = Organization.objects.create(name="Globex", slug="globex")

        OrganizationMember.objects.create(user=self.acme_user, organization=self.acme, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.globex_user, organization=self.globex, role="ADMIN", is_active=True)

        self.acme_branch = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Main",
            code="MAIN",
        )
        self.acme_branch_2 = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Outlet",
            code="OUT",
        )
        self.globex_branch = Branch.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Main",
            code="GLOBEX-MAIN",
        )

        self.acme_item_1 = Item.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Item A",
            sku="ACME-A",
        )
        self.acme_item_2 = Item.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Item B",
            sku="ACME-B",
        )
        self.globex_item = Item.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Item",
            sku="GLOBEX-A",
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _host(self, org_slug):
        return f"{org_slug}.localhost:8000"

    def _movement_payload(self, item_id, key):
        return {
            "item": str(item_id),
            "quantity": "2.0000",
            "movement_type": "RECEIPT",
            "reference_type": "",
            "reference_id": "",
            "reason": "",
            "idempotency_key": key,
        }

    def test_item_isolation(self):
        self._auth(self.acme_user)
        response = self.client.get(
            f"/api/orgs/{self.acme.id}/inventory/items/",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(response.status_code, 200)
        returned_ids = {row["id"] for row in response.data["results"]}
        self.assertIn(str(self.acme_item_1.id), returned_ids)
        self.assertNotIn(str(self.globex_item.id), returned_ids)

    def test_soft_delete_and_is_active_filter(self):
        self._auth(self.acme_user)
        delete_response = self.client.delete(
            f"/api/orgs/{self.acme.id}/inventory/items/{self.acme_item_1.id}/",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(delete_response.status_code, 204)
        self.acme_item_1.refresh_from_db()
        self.assertFalse(self.acme_item_1.is_active)

        default_list = self.client.get(f"/api/orgs/{self.acme.id}/inventory/items/", HTTP_HOST=self._host("acme"))
        default_ids = {row["id"] for row in default_list.data["results"]}
        self.assertNotIn(str(self.acme_item_1.id), default_ids)

        inactive_list = self.client.get(
            f"/api/orgs/{self.acme.id}/inventory/items/?is_active=false",
            HTTP_HOST=self._host("acme"),
        )
        inactive_ids = {row["id"] for row in inactive_list.data["results"]}
        self.assertIn(str(self.acme_item_1.id), inactive_ids)

    def test_stock_accuracy_and_filters(self):
        record_stock_movement(
            org=self.acme,
            branch=self.acme_branch,
            item=self.acme_item_1,
            quantity=Decimal("3.0000"),
            movement_type="RECEIPT",
            performed_by=self.acme_user,
            idempotency_key="stock-a-1",
        )
        record_stock_movement(
            org=self.acme,
            branch=self.acme_branch,
            item=self.acme_item_2,
            quantity=Decimal("4.0000"),
            movement_type="RECEIPT",
            performed_by=self.acme_user,
            idempotency_key="stock-b-1",
        )
        record_stock_movement(
            org=self.acme,
            branch=self.acme_branch_2,
            item=self.acme_item_1,
            quantity=Decimal("5.0000"),
            movement_type="RECEIPT",
            performed_by=self.acme_user,
            idempotency_key="stock-c-1",
        )

        self._auth(self.acme_user)
        response = self.client.get(f"/api/orgs/{self.acme.id}/inventory/stock/", HTTP_HOST=self._host("acme"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)
        quantities = {(r["branch"]["id"], r["item"]["id"]): r["quantity"] for r in response.data["results"]}
        self.assertEqual(quantities[(str(self.acme_branch.id), str(self.acme_item_1.id))], "3.0000")
        self.assertEqual(quantities[(str(self.acme_branch.id), str(self.acme_item_2.id))], "4.0000")
        self.assertEqual(quantities[(str(self.acme_branch_2.id), str(self.acme_item_1.id))], "5.0000")

        by_branch = self.client.get(
            f"/api/orgs/{self.acme.id}/inventory/stock/?branch={self.acme_branch.id}",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(by_branch.data["count"], 2)

        by_item = self.client.get(
            f"/api/orgs/{self.acme.id}/inventory/stock/?item={self.acme_item_2.id}",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(by_item.data["count"], 1)

        self.acme_item_2.is_active = False
        self.acme_item_2.save(update_fields=["is_active"])
        active_default = self.client.get(f"/api/orgs/{self.acme.id}/inventory/stock/", HTTP_HOST=self._host("acme"))
        active_item_ids = {r["item"]["id"] for r in active_default.data["results"]}
        self.assertNotIn(str(self.acme_item_2.id), active_item_ids)

        inactive_only = self.client.get(
            f"/api/orgs/{self.acme.id}/inventory/stock/?is_active=false",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(inactive_only.data["count"], 1)
        self.assertEqual(inactive_only.data["results"][0]["item"]["id"], str(self.acme_item_2.id))

    def test_movement_get_filters_ordering_and_pagination(self):
        self._auth(self.acme_user)
        for i in range(55):
            record_stock_movement(
                org=self.acme,
                branch=self.acme_branch if i % 2 == 0 else self.acme_branch_2,
                item=self.acme_item_1 if i % 3 == 0 else self.acme_item_2,
                quantity=Decimal("1.0000"),
                movement_type="RECEIPT" if i % 2 == 0 else "ISSUE",
                performed_by=self.acme_user,
                reference_type="PO" if i % 2 == 0 else "SO",
                reference_id=f"ref-{i}",
                idempotency_key=f"mov-{i}",
            )

        response = self.client.get(
            f"/api/orgs/{self.acme.id}/inventory/movements/?movement_type=RECEIPT&reference_type=PO&ordering=occurred_at",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)
        self.assertLessEqual(len(response.data["results"]), 50)

        page_2 = self.client.get(f"/api/orgs/{self.acme.id}/inventory/movements/?page=2", HTTP_HOST=self._host("acme"))
        self.assertEqual(page_2.status_code, 200)
        self.assertGreater(page_2.data["count"], 50)

    def test_movement_post_idempotent_semantics(self):
        self._auth(self.acme_user)
        payload = self._movement_payload(self.acme_item_1.id, "idem-phase3-1")
        first = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/movements/",
            payload,
            format="json",
            HTTP_HOST=self._host("acme"),
            HTTP_X_BRANCH_ID=str(self.acme_branch.id),
        )
        second = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/movements/",
            payload,
            format="json",
            HTTP_HOST=self._host("acme"),
            HTTP_X_BRANCH_ID=str(self.acme_branch.id),
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["id"], second.data["id"])

    def test_branch_header_enforcement(self):
        self._auth(self.acme_user)
        payload = self._movement_payload(self.acme_item_1.id, "missing-header")
        missing_header = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/movements/",
            payload,
            format="json",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(missing_header.status_code, 400)

        list_response = self.client.get(f"/api/orgs/{self.acme.id}/inventory/movements/", HTTP_HOST=self._host("acme"))
        self.assertEqual(list_response.status_code, 200)

    def test_cross_org_item_rejected_at_serializer_validation(self):
        self._auth(self.acme_user)
        payload = self._movement_payload(self.globex_item.id, "cross-org-item")
        response = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/movements/",
            payload,
            format="json",
            HTTP_HOST=self._host("acme"),
            HTTP_X_BRANCH_ID=str(self.acme_branch.id),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("item", response.data)
        self.assertEqual(StockLedger.objects.for_org(self.acme).count(), 0)

    def test_idempotency_key_absent_from_read_responses(self):
        self._auth(self.acme_user)
        payload = self._movement_payload(self.acme_item_1.id, "no-idempotency-in-response")
        create_response = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/movements/",
            payload,
            format="json",
            HTTP_HOST=self._host("acme"),
            HTTP_X_BRANCH_ID=str(self.acme_branch.id),
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertNotIn("idempotency_key", create_response.data)

        list_response = self.client.get(f"/api/orgs/{self.acme.id}/inventory/movements/", HTTP_HOST=self._host("acme"))
        self.assertEqual(list_response.status_code, 200)
        self.assertNotIn("idempotency_key", list_response.data["results"][0])

    def test_nested_field_shapes(self):
        self._auth(self.acme_user)
        payload = self._movement_payload(self.acme_item_1.id, "nested-shapes-1")
        create_response = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/movements/",
            payload,
            format="json",
            HTTP_HOST=self._host("acme"),
            HTTP_X_BRANCH_ID=str(self.acme_branch.id),
        )
        self.assertEqual(create_response.status_code, 201)
        row = create_response.data
        self.assertEqual(set(row["branch"].keys()), {"id", "name", "code"})
        self.assertEqual(set(row["item"].keys()), {"id", "name", "sku"})
        self.assertEqual(set(row["performed_by"].keys()), {"id", "username"})

    def test_pagination_shape_on_all_list_endpoints(self):
        self._auth(self.acme_user)
        urls = [
            f"/api/orgs/{self.acme.id}/inventory/items/",
            f"/api/orgs/{self.acme.id}/inventory/stock/",
            f"/api/orgs/{self.acme.id}/inventory/movements/",
            f"/api/orgs/{self.acme.id}/branches/",
        ]
        for url in urls:
            response = self.client.get(url, HTTP_HOST=self._host("acme"))
            self.assertEqual(response.status_code, 200, msg=f"failed url={url}")
            self.assertEqual(set(response.data.keys()), {"count", "next", "previous", "results"})

    def test_auth_enforcement(self):
        unauth = self.client.get(f"/api/orgs/{self.acme.id}/inventory/items/", HTTP_HOST=self._host("acme"))
        self.assertEqual(unauth.status_code, 401)

        self._auth(self.no_membership_user)
        forbidden = self.client.get(f"/api/orgs/{self.acme.id}/inventory/items/", HTTP_HOST=self._host("acme"))
        self.assertEqual(forbidden.status_code, 403)

    def test_n_plus_one_prevention(self):
        self._auth(self.acme_user)
        for i in range(15):
            record_stock_movement(
                org=self.acme,
                branch=self.acme_branch if i % 2 == 0 else self.acme_branch_2,
                item=self.acme_item_1 if i % 3 == 0 else self.acme_item_2,
                quantity=Decimal("1.0000"),
                movement_type="RECEIPT",
                performed_by=self.acme_user,
                idempotency_key=f"nplus1-{i}",
            )

        with CaptureQueriesContext(connection) as stock_ctx:
            stock_response = self.client.get(f"/api/orgs/{self.acme.id}/inventory/stock/", HTTP_HOST=self._host("acme"))
        self.assertEqual(stock_response.status_code, 200)
        self.assertLessEqual(len(stock_ctx.captured_queries), 10)

        with CaptureQueriesContext(connection) as movement_ctx:
            movement_response = self.client.get(f"/api/orgs/{self.acme.id}/inventory/movements/", HTTP_HOST=self._host("acme"))
        self.assertEqual(movement_response.status_code, 200)
        self.assertLessEqual(len(movement_ctx.captured_queries), 10)


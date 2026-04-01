from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from branch_transfers.models import BranchTransfer
from branch_transfers.services import receive_transfer
from branches.models import Branch
from inventory.models import MasterItem, OrgItem, StockOnHand
from inventory.services import record_stock_movement
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


class MasterItemApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.parent_admin = User.objects.create_user(username="master_parent_admin", password="Passw0rd!")
        self.parent_viewer = User.objects.create_user(username="master_parent_viewer", password="Passw0rd!")
        self.owner = User.objects.create_user(username="master_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="master_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="master_staff", password="Passw0rd!")

        ParentCompanyMember.objects.create(
            user=self.parent_admin,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
        )
        ParentCompanyMember.objects.create(
            user=self.parent_viewer,
            role=ParentCompanyMember.PARENT_VIEWER,
            is_active=True,
        )

        self.acme = Organization.objects.create(name="Acme", slug="master-acme")
        self.globex = Organization.objects.create(name="Globex", slug="master-globex")

        OrganizationMember.objects.create(user=self.owner, organization=self.acme, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.admin, organization=self.acme, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.staff, organization=self.acme, role="STAFF", is_active=True)

        self.acme_branch = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Main",
            code="ACME-MAIN",
        )
        self.globex_branch = Branch.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Main",
            code="GLOBEX-MAIN",
        )

        self.master_a = MasterItem.objects.create(name="Widget A", sku="MASTER-A")
        self.master_b = MasterItem.objects.create(name="Widget B", sku="MASTER-B")
        self.inactive_master = MasterItem.objects.create(name="Inactive Widget", sku="MASTER-X", is_active=False)
        self.acme_item = OrgItem.objects.create(
            organization=self.acme,
            master_item=self.master_a,
            name="",
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _host(self, slug):
        return f"{slug}.localhost:8000"

    def test_parent_admin_crud_and_parent_viewer_read_only(self):
        self._auth(self.parent_admin)
        list_response = self.client.get("/api/parent/master-items/")
        self.assertEqual(list_response.status_code, 200)

        create_response = self.client.post(
            "/api/parent/master-items/",
            {"name": "Created By Parent", "sku": "MASTER-C"},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)

        item_id = create_response.data["id"]
        retrieve_response = self.client.get(f"/api/parent/master-items/{item_id}/")
        self.assertEqual(retrieve_response.status_code, 200)

        update_response = self.client.patch(
            f"/api/parent/master-items/{item_id}/",
            {"name": "Updated By Parent"},
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)

        delete_response = self.client.delete(f"/api/parent/master-items/{item_id}/")
        self.assertEqual(delete_response.status_code, 204)
        self.assertTrue(MasterItem.objects.filter(id=item_id, is_active=False).exists())

        duplicate_response = self.client.post(
            "/api/parent/master-items/",
            {"name": "Duplicate SKU", "sku": "MASTER-A"},
            format="json",
        )
        self.assertEqual(duplicate_response.status_code, 400)

        self._auth(self.parent_viewer)
        self.assertEqual(self.client.get("/api/parent/master-items/").status_code, 200)
        self.assertEqual(
            self.client.post(
                "/api/parent/master-items/",
                {"name": "Blocked", "sku": "MASTER-D"},
                format="json",
            ).status_code,
            403,
        )

    def test_parent_endpoint_blocks_org_members_and_unauthenticated(self):
        self._auth(self.owner)
        self.assertEqual(self.client.get("/api/parent/master-items/").status_code, 403)

        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/parent/master-items/").status_code, 401)

    def test_org_master_item_browse_filters_permissions_and_activation_state(self):
        self._auth(self.owner)
        owner_response = self.client.get(
            f"/api/orgs/{self.acme.id}/master-items/",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(owner_response.status_code, 200)
        owner_ids = {row["id"] for row in owner_response.data}
        self.assertIn(str(self.master_b.id), owner_ids)
        self.assertNotIn(str(self.master_a.id), owner_ids)
        self.assertNotIn(str(self.inactive_master.id), owner_ids)

        self._auth(self.admin)
        self.assertEqual(
            self.client.get(
                f"/api/orgs/{self.acme.id}/master-items/",
                HTTP_HOST=self._host(self.acme.slug),
            ).status_code,
            200,
        )

        self._auth(self.staff)
        self.assertEqual(
            self.client.get(
                f"/api/orgs/{self.acme.id}/master-items/",
                HTTP_HOST=self._host(self.acme.slug),
            ).status_code,
            403,
        )

        self._auth(self.parent_admin)
        self.assertEqual(
            self.client.get(
                f"/api/orgs/{self.acme.id}/master-items/",
                HTTP_HOST=self._host(self.acme.slug),
            ).status_code,
            403,
        )

    def test_org_item_activation_requires_master_item_and_preserves_shape(self):
        self._auth(self.owner)
        create_response = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/items/",
            {"master_item": str(self.master_b.id), "name": ""},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(
            set(create_response.data.keys()),
            {
                "id",
                "organization",
                "master_item",
                "name",
                "name_override",
                "sku",
                "is_active",
                "created_at",
            },
        )
        self.assertEqual(create_response.data["name"], "Widget B")
        self.assertEqual(create_response.data["name_override"], "")
        self.assertEqual(create_response.data["sku"], "MASTER-B")
        self.assertTrue(create_response.data["is_active"])

        duplicate_response = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/items/",
            {"master_item": str(self.master_b.id), "name": "Custom Name"},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(duplicate_response.status_code, 400)

        inactive_response = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/items/",
            {"master_item": str(self.inactive_master.id), "name": "Blocked"},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(inactive_response.status_code, 400)

        override_master = MasterItem.objects.create(name="Override Widget", sku="MASTER-OVR")
        override_response = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/items/",
            {"master_item": str(override_master.id), "name": "Override Name", "is_active": False},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(override_response.status_code, 201)
        self.assertEqual(override_response.data["name"], "Override Name")
        self.assertEqual(override_response.data["name_override"], "Override Name")
        created = OrgItem.objects.get(id=override_response.data["id"])
        self.assertEqual(created.name, "Override Name")
        self.assertTrue(created.is_active)

        self._auth(self.staff)
        self.assertEqual(
            self.client.post(
                f"/api/orgs/{self.acme.id}/inventory/items/",
                {"master_item": str(MasterItem.objects.create(name='Staff Blocked', sku='MASTER-S').id), "name": ""},
                format="json",
                HTTP_HOST=self._host(self.acme.slug),
            ).status_code,
            403,
        )

    def test_receive_transfer_auto_creates_and_reuses_recipient_org_item(self):
        transfer = BranchTransfer.objects.for_org(self.acme).create(
            organization=self.acme,
            from_branch=self.acme_branch,
            to_branch=self.globex_branch,
            to_organization=self.globex,
            status=BranchTransfer.IN_TRANSIT,
            created_by=self.owner,
        )
        transfer.lines.create(item=self.acme_item, quantity_sent=3)

        record_stock_movement(
            org=self.acme,
            branch=self.acme_branch,
            item=self.acme_item,
            quantity=Decimal("5.0000"),
            movement_type="RECEIPT",
            unit_cost=Decimal("5.0000"),
            performed_by=self.owner,
            idempotency_key="master-transfer-seed",
        )
        transfer.lines.update(dispatched_unit_cost=Decimal("5.0000"))

        receive_transfer(
            transfer=transfer,
            lines_data=[{"line_id": transfer.lines.first().id, "quantity_received": 2}],
            performed_by=self.owner,
        )

        recipient_item = OrgItem.objects.for_org(self.globex).get(master_item=self.master_a)
        self.assertTrue(recipient_item.is_active)
        self.assertEqual(recipient_item.master_item, self.master_a)
        stock = StockOnHand.objects.for_org(self.globex).get(branch=self.globex_branch, item=recipient_item)
        self.assertEqual(stock.quantity, Decimal("2.0000"))

        transfer_two = BranchTransfer.objects.for_org(self.acme).create(
            organization=self.acme,
            from_branch=self.acme_branch,
            to_branch=self.globex_branch,
            to_organization=self.globex,
            status=BranchTransfer.IN_TRANSIT,
            created_by=self.owner,
        )
        transfer_two.lines.create(item=self.acme_item, quantity_sent=1)
        transfer_two.lines.update(dispatched_unit_cost=Decimal("5.0000"))
        receive_transfer(
            transfer=transfer_two,
            lines_data=[{"line_id": transfer_two.lines.first().id, "quantity_received": 1}],
            performed_by=self.owner,
        )

        self.assertEqual(OrgItem.objects.for_org(self.globex).filter(master_item=self.master_a).count(), 1)

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, APITestCase

from branch_transfers.models import BranchTransfer
from branch_transfers.serializers import BranchTransferLineWriteSerializer
from branch_transfers.services import receive_transfer
from branches.models import Branch
from goods_receipts.serializers import DirectReceiptLineWriteSerializer
from inventory.models import BranchItem, MasterItem, OrgItem, StockOnHand
from purchase_orders.models import PurchaseOrder
from purchase_orders.serializers import PurchaseOrderLineWriteSerializer
from suppliers.models import Supplier
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


class BranchItemApiTests(APITestCase):
    def _create_org_item(self, organization, name, sku, *, item_name="", is_active=True):
        master_item = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.create(
            organization=organization,
            master_item=master_item,
            name=item_name,
            is_active=is_active,
        )

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="branch_item_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="branch_item_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="branch_item_staff", password="Passw0rd!")
        self.outsider = User.objects.create_user(username="branch_item_outsider", password="Passw0rd!")
        self.parent_admin = User.objects.create_user(username="branch_item_parent", password="Passw0rd!")

        self.acme = Organization.objects.create(name="Acme", slug="branch-item-acme")
        self.globex = Organization.objects.create(name="Globex", slug="branch-item-globex")

        self.branch_a = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Branch A",
            code="A",
        )
        self.branch_b = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Branch B",
            code="B",
        )
        self.globex_branch = Branch.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Branch",
            code="GB",
        )

        OrganizationMember.objects.create(user=self.owner, organization=self.acme, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.admin, organization=self.acme, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(
            user=self.staff,
            organization=self.acme,
            role="STAFF",
            is_active=True,
            assigned_branch=self.branch_a,
        )
        ParentCompanyMember.objects.create(
            user=self.parent_admin,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
        )

        self.item_a = self._create_org_item(self.acme, "Acme A", "BR-A")
        self.item_b = self._create_org_item(self.acme, "Acme B", "BR-B")
        self.item_c = self._create_org_item(self.acme, "Acme C", "BR-C")
        self.globex_item = self._create_org_item(self.globex, "Globex Item", "GBR-1")
        self.inactive_org_item = self._create_org_item(self.acme, "Inactive Org Item", "BR-X", is_active=False)

        self.branch_item_a = BranchItem.objects.create(org_item=self.item_a, branch=self.branch_a)
        self.branch_item_b = BranchItem.objects.create(org_item=self.item_b, branch=self.branch_b)

        self.supplier = Supplier.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Supplier",
            created_by=self.owner,
        )
        self.purchase_order = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-1000",
            supplier=self.supplier,
            branch=self.branch_a,
            created_by=self.owner,
        )
        self.factory = APIRequestFactory()

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _host(self, slug):
        return f"{slug}.localhost:8000"

    def _base_url(self):
        return f"/api/orgs/{self.acme.id}/branch-items/"

    def test_branch_item_management_permissions_and_soft_delete(self):
        for user in (self.owner, self.admin, self.staff):
            self._auth(user)
            response = self.client.get(self._base_url(), HTTP_HOST=self._host(self.acme.slug))
            self.assertEqual(response.status_code, 200)

        branch = Branch.objects.for_org(self.acme).create(organization=self.acme, name="Branch C", code="C")
        org_item = self._create_org_item(self.acme, "Acme D", "BR-D")

        for user in (self.owner, self.admin):
            self._auth(user)
            response = self.client.post(
                self._base_url(),
                {"org_item": str(org_item.id), "branch": str(branch.id)},
                format="json",
                HTTP_HOST=self._host(self.acme.slug),
            )
            self.assertEqual(response.status_code, 201 if user == self.owner else 400)

        self._auth(self.staff)
        staff_create = self.client.post(
            self._base_url(),
            {"org_item": str(self.item_a.id), "branch": str(self.branch_a.id)},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(staff_create.status_code, 403)

        target = BranchItem.objects.create(org_item=org_item, branch=self.branch_b)
        for user, expected in ((self.owner, 204), (self.admin, 204), (self.staff, 403)):
            target.is_active = True
            target.save()
            self._auth(user)
            response = self.client.delete(
                f"{self._base_url()}{target.id}/",
                HTTP_HOST=self._host(self.acme.slug),
            )
            self.assertEqual(response.status_code, expected)
            target.refresh_from_db()
            if expected == 204:
                self.assertFalse(target.is_active)

        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self._base_url(), HTTP_HOST=self._host(self.acme.slug)).status_code, 401)

    def test_branch_item_create_reactivation_validation_and_filters(self):
        inactive = BranchItem.objects.create(org_item=self.item_c, branch=self.branch_a, is_active=False)

        self._auth(self.owner)
        duplicate = self.client.post(
            self._base_url(),
            {"org_item": str(self.item_a.id), "branch": str(self.branch_a.id)},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(duplicate.status_code, 400)

        reactivate = self.client.post(
            self._base_url(),
            {"org_item": str(self.item_c.id), "branch": str(self.branch_a.id)},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(reactivate.status_code, 200)
        inactive.refresh_from_db()
        self.assertTrue(inactive.is_active)

        inactive_org = self.client.post(
            self._base_url(),
            {"org_item": str(self.inactive_org_item.id), "branch": str(self.branch_a.id)},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(inactive_org.status_code, 400)

        cross_org_item = self.client.post(
            self._base_url(),
            {"org_item": str(self.globex_item.id), "branch": str(self.branch_a.id)},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(cross_org_item.status_code, 400)

        cross_org_branch = self.client.post(
            self._base_url(),
            {"org_item": str(self.item_a.id), "branch": str(self.globex_branch.id)},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(cross_org_branch.status_code, 400)

        BranchItem.objects.create(org_item=self.item_c, branch=self.branch_b, is_active=False)
        default_list = self.client.get(self._base_url(), HTTP_HOST=self._host(self.acme.slug))
        self.assertEqual(default_list.data["count"], 3)

        branch_filtered = self.client.get(
            f"{self._base_url()}?branch={self.branch_b.id}",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(branch_filtered.data["count"], 1)

        inactive_only = self.client.get(
            f"{self._base_url()}?is_active=false",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(inactive_only.data["count"], 1)

    def test_branch_item_clean_enforces_org_match(self):
        mismatch = BranchItem(org_item=self.item_a, branch=self.globex_branch)
        with self.assertRaises(ValidationError):
            mismatch.save()

    def test_org_item_branch_scoping_and_reactivation(self):
        BranchItem.objects.create(org_item=self.item_b, branch=self.branch_a, is_active=False)
        BranchItem.objects.create(org_item=self.item_c, branch=self.branch_a, is_active=True)
        self.item_c.is_active = False
        self.item_c.save(update_fields=["is_active"])

        self._auth(self.staff)
        staff_response = self.client.get(
            f"/api/orgs/{self.acme.id}/inventory/items/",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(staff_response.status_code, 200)
        staff_ids = {row["id"] for row in staff_response.data["results"]}
        self.assertIn(str(self.item_a.id), staff_ids)
        self.assertNotIn(str(self.item_b.id), staff_ids)
        self.assertNotIn(str(self.item_c.id), staff_ids)

        self._auth(self.owner)
        owner_branch = self.client.get(
            f"/api/orgs/{self.acme.id}/inventory/items/",
            HTTP_HOST=self._host(self.acme.slug),
            HTTP_X_BRANCH_ID=str(self.branch_a.id),
        )
        owner_branch_ids = {row["id"] for row in owner_branch.data["results"]}
        self.assertEqual(owner_branch_ids, {str(self.item_a.id)})

        owner_org = self.client.get(
            f"/api/orgs/{self.acme.id}/inventory/items/",
            HTTP_HOST=self._host(self.acme.slug),
        )
        owner_org_ids = {row["id"] for row in owner_org.data["results"]}
        self.assertIn(str(self.item_a.id), owner_org_ids)
        self.assertIn(str(self.item_b.id), owner_org_ids)

        self.item_b.is_active = False
        self.item_b.save(update_fields=["is_active"])
        reactivate = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/items/",
            {"master_item": str(self.item_b.master_item_id), "name": "Reactivated Name"},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(reactivate.status_code, 200)
        self.item_b.refresh_from_db()
        self.assertTrue(self.item_b.is_active)
        self.assertEqual(self.item_b.name, "Reactivated Name")

        active_duplicate = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/items/",
            {"master_item": str(self.item_a.master_item_id), "name": ""},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(active_duplicate.status_code, 400)

    def test_branch_item_validate_item_checks(self):
        request = self.factory.post("/")
        request.user = self.owner
        request.org = self.acme
        request.branch = self.branch_a

        direct = DirectReceiptLineWriteSerializer(
            data={"item": str(self.item_b.id), "quantity_received": 1, "unit_cost": "2.00"},
            context={"request": request},
        )
        self.assertFalse(direct.is_valid())
        self.assertEqual(direct.errors["item"][0], "Item is not enabled at this branch.")

        transfer = BranchTransferLineWriteSerializer(
            data={"item": str(self.item_b.id), "quantity_sent": 1},
            context={"request": request},
        )
        self.assertFalse(transfer.is_valid())
        self.assertEqual(transfer.errors["item"][0], "Item is not enabled at the sending branch.")

        po = PurchaseOrderLineWriteSerializer(
            data={"item": str(self.item_b.id), "ordered_quantity": 1, "unit_price": "5.00"},
            context={"request": request, "purchase_order": self.purchase_order},
        )
        self.assertFalse(po.is_valid())
        self.assertEqual(po.errors["item"][0], "Item is not enabled at this branch.")

        BranchItem.objects.create(org_item=self.item_b, branch=self.branch_a)
        direct_ok = DirectReceiptLineWriteSerializer(
            data={"item": str(self.item_b.id), "quantity_received": 1, "unit_cost": "2.00"},
            context={"request": request},
        )
        transfer_ok = BranchTransferLineWriteSerializer(
            data={"item": str(self.item_b.id), "quantity_sent": 1},
            context={"request": request},
        )
        po_ok = PurchaseOrderLineWriteSerializer(
            data={"item": str(self.item_b.id), "ordered_quantity": 1, "unit_price": "5.00"},
            context={"request": request, "purchase_order": self.purchase_order},
        )
        self.assertTrue(direct_ok.is_valid(), direct_ok.errors)
        self.assertTrue(transfer_ok.is_valid(), transfer_ok.errors)
        self.assertTrue(po_ok.is_valid(), po_ok.errors)

        request_no_branch = self.factory.post("/")
        request_no_branch.user = self.owner
        request_no_branch.org = self.acme
        request_no_branch.branch = None
        po_no_branch = PurchaseOrderLineWriteSerializer(
            data={"item": str(self.item_c.id), "ordered_quantity": 1, "unit_price": "5.00"},
            context={"request": request_no_branch, "purchase_order": self.purchase_order},
        )
        self.assertTrue(po_no_branch.is_valid(), po_no_branch.errors)

    def test_receive_transfer_branch_item_auto_create_and_reactivate(self):
        transfer = BranchTransfer.objects.for_org(self.acme).create(
            organization=self.acme,
            from_branch=self.branch_a,
            to_branch=self.globex_branch,
            to_organization=self.globex,
            status=BranchTransfer.IN_TRANSIT,
            created_by=self.owner,
        )
        transfer.lines.create(item=self.item_a, quantity_sent=2)

        receive_transfer(
            transfer=transfer,
            lines_data=[{"line_id": transfer.lines.first().id, "quantity_received": 2}],
            performed_by=self.owner,
        )

        recipient_org_item = OrgItem.objects.for_org(self.globex).get(master_item=self.item_a.master_item)
        recipient_branch_item = BranchItem.objects.get(org_item=recipient_org_item, branch=self.globex_branch)
        self.assertTrue(recipient_branch_item.is_active)
        stock = StockOnHand.objects.for_org(self.globex).get(branch=self.globex_branch, item=recipient_org_item)
        self.assertEqual(stock.quantity, Decimal("2.0000"))

        recipient_org_item.is_active = False
        recipient_org_item.save(update_fields=["is_active"])
        recipient_branch_item.is_active = False
        recipient_branch_item.save(update_fields=["is_active"])

        transfer_two = BranchTransfer.objects.for_org(self.acme).create(
            organization=self.acme,
            from_branch=self.branch_a,
            to_branch=self.globex_branch,
            to_organization=self.globex,
            status=BranchTransfer.IN_TRANSIT,
            created_by=self.owner,
        )
        transfer_two.lines.create(item=self.item_a, quantity_sent=1)

        receive_transfer(
            transfer=transfer_two,
            lines_data=[{"line_id": transfer_two.lines.first().id, "quantity_received": 1}],
            performed_by=self.owner,
        )

        recipient_org_item.refresh_from_db()
        recipient_branch_item.refresh_from_db()
        self.assertTrue(recipient_org_item.is_active)
        self.assertTrue(recipient_branch_item.is_active)
        self.assertEqual(
            BranchItem.objects.filter(org_item=recipient_org_item, branch=self.globex_branch).count(),
            1,
        )

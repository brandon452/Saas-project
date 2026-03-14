from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import Item
from purchase_orders.models import PurchaseOrder
from purchase_orders.services import generate_po_number
from suppliers.models import Supplier
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


class PurchaseOrderNumberTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="po_number_user", password="Passw0rd!")
        self.acme = Organization.objects.create(name="Acme", slug="acme-po-numbers")
        self.globex = Organization.objects.create(name="Globex", slug="globex-po-numbers")
        self.branch = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Main",
            code="MAIN",
        )
        self.supplier = Supplier.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Supplier",
            created_by=self.user,
        )
        self.globex_branch = Branch.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Main",
            code="GLOBEX-MAIN",
        )
        self.globex_supplier = Supplier.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Supplier",
            created_by=self.user,
        )

    def test_generate_po_number_sequences_and_org_isolation(self):
        self.assertEqual(generate_po_number(self.acme), "PO-0001")

        PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0001",
            supplier=self.supplier,
            branch=self.branch,
            created_by=self.user,
        )
        self.assertEqual(generate_po_number(self.acme), "PO-0002")

        self.assertEqual(generate_po_number(self.globex), "PO-0001")
        PurchaseOrder.objects.for_org(self.globex).create(
            organization=self.globex,
            po_number="PO-0001",
            supplier=self.globex_supplier,
            branch=self.globex_branch,
            created_by=self.user,
        )
        self.assertEqual(generate_po_number(self.globex), "PO-0002")

    def test_malformed_po_number_falls_back_to_zero(self):
        PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="BAD-VALUE",
            supplier=self.supplier,
            branch=self.branch,
            created_by=self.user,
        )

        self.assertEqual(generate_po_number(self.acme), "PO-0001")


class PurchaseOrderApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="po_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="po_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="po_staff", password="Passw0rd!")
        self.outsider = User.objects.create_user(username="po_outsider", password="Passw0rd!")
        self.parent_admin_user = User.objects.create_user(username="po_parent_admin", password="Passw0rd!")
        self.parent_viewer_user = User.objects.create_user(username="po_parent_viewer", password="Passw0rd!")

        self.acme = Organization.objects.create(name="Acme", slug="acme-po")
        self.globex = Organization.objects.create(name="Globex", slug="globex-po")

        OrganizationMember.objects.create(user=self.owner, organization=self.acme, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.admin, organization=self.acme, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.staff, organization=self.acme, role="STAFF", is_active=True)

        ParentCompanyMember.objects.create(
            user=self.parent_admin_user,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
        )
        ParentCompanyMember.objects.create(
            user=self.parent_viewer_user,
            role=ParentCompanyMember.PARENT_VIEWER,
            is_active=True,
        )

        self.branch = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Main",
            code="MAIN",
        )
        self.other_branch = Branch.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Other",
            code="OTH",
        )

        self.supplier = Supplier.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Supplier",
            created_by=self.owner,
        )
        self.inactive_supplier = Supplier.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Inactive Supplier",
            is_active=False,
            created_by=self.owner,
        )
        self.other_supplier = Supplier.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Supplier",
        )

        self.item_a = Item.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Item A",
            sku="PO-A",
        )
        self.item_b = Item.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Item B",
            sku="PO-B",
        )
        self.other_item = Item.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Item",
            sku="GPO-1",
        )

        self.globex_po = PurchaseOrder.objects.for_org(self.globex).create(
            organization=self.globex,
            po_number="PO-0001",
            supplier=self.other_supplier,
            branch=self.other_branch,
            notes="Globex only",
            created_by=self.owner,
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _host(self, slug="acme-po"):
        return f"{slug}.localhost:8000"

    def _base_url(self, org_id=None):
        target_org = org_id or self.acme.id
        return f"/api/orgs/{target_org}/purchase-orders/"

    def _detail_url(self, po_id, suffix="", org_id=None):
        return f"{self._base_url(org_id=org_id)}{po_id}/{suffix}"

    def _create_payload(self, **overrides):
        payload = {
            "supplier": str(self.supplier.id),
            "branch": str(self.branch.id),
            "notes": "Draft notes",
        }
        payload.update(overrides)
        return payload

    def _create_po(self, user=None, **overrides):
        if user:
            self._auth(user)
        response = self.client.post(
            self._base_url(),
            self._create_payload(**overrides),
            format="json",
            HTTP_HOST=self._host(),
        )
        return response

    def _add_line(self, po_id, user, **overrides):
        self._auth(user)
        payload = {
            "item": str(self.item_a.id),
            "ordered_quantity": 2,
            "unit_price": "12.50",
        }
        payload.update(overrides)
        return self.client.post(
            self._detail_url(po_id, "lines/add/"),
            payload,
            format="json",
            HTTP_HOST=self._host(),
        )

    def test_create_permissions_and_server_side_fields(self):
        cases = [
            (self.owner, 201),
            (self.admin, 201),
            (self.staff, 403),
            (self.parent_admin_user, 403),
            (self.parent_viewer_user, 403),
        ]

        for index, (user, expected_status) in enumerate(cases, start=1):
            self._auth(user)
            response = self.client.post(
                self._base_url(),
                self._create_payload(
                    notes=f"PO {index}",
                    organization=str(self.globex.id),
                    created_by=999999,
                    po_number="PO-9999",
                    status=PurchaseOrder.CANCELLED,
                ),
                format="json",
                HTTP_HOST=self._host(),
            )
            self.assertEqual(response.status_code, expected_status)

        created = PurchaseOrder.objects.for_org(self.acme).order_by("created_at").first()
        self.assertIsNotNone(created)
        self.assertEqual(created.organization, self.acme)
        self.assertEqual(created.created_by, self.owner)
        self.assertEqual(created.status, PurchaseOrder.DRAFT)
        self.assertEqual(created.po_number, "PO-0001")

    def test_create_validation_for_supplier_and_branch_scoping(self):
        self._auth(self.owner)

        supplier_cross_org = self._create_po(supplier=str(self.other_supplier.id))
        self.assertEqual(supplier_cross_org.status_code, 400)
        self.assertIn("supplier", supplier_cross_org.data)

        inactive_supplier = self._create_po(supplier=str(self.inactive_supplier.id))
        self.assertEqual(inactive_supplier.status_code, 400)
        self.assertIn("supplier", inactive_supplier.data)

        branch_cross_org = self._create_po(branch=str(self.other_branch.id))
        self.assertEqual(branch_cross_org.status_code, 400)
        self.assertIn("branch", branch_cross_org.data)

    def test_update_header_permissions_and_draft_only_rule(self):
        po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0001",
            supplier=self.supplier,
            branch=self.branch,
            notes="Old",
            created_by=self.owner,
        )

        cases = [
            (self.owner, 200),
            (self.admin, 200),
            (self.staff, 403),
            (self.parent_admin_user, 403),
        ]

        for user, expected_status in cases:
            self._auth(user)
            response = self.client.patch(
                self._detail_url(po.id),
                {"notes": f"updated-by-{user.username}"},
                format="json",
                HTTP_HOST=self._host(),
            )
            self.assertEqual(response.status_code, expected_status)

        po.refresh_from_db()
        self.assertEqual(po.notes, "updated-by-po_admin")

        po.status = PurchaseOrder.SUBMITTED
        po.save(update_fields=["status", "updated_at"])
        self._auth(self.owner)
        submitted_response = self.client.patch(
            self._detail_url(po.id),
            {"notes": "blocked"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(submitted_response.status_code, 400)

        po.status = PurchaseOrder.CANCELLED
        po.save(update_fields=["status", "updated_at"])
        cancelled_response = self.client.patch(
            self._detail_url(po.id),
            {"notes": "still blocked"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(cancelled_response.status_code, 400)

    def test_submit_rules_and_permissions(self):
        po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0001",
            supplier=self.supplier,
            branch=self.branch,
            created_by=self.owner,
        )

        self._auth(self.owner)
        no_lines = self.client.post(
            self._detail_url(po.id, "submit/"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(no_lines.status_code, 400)

        add_line = self._add_line(po.id, self.owner)
        self.assertEqual(add_line.status_code, 201)

        self._auth(self.owner)
        owner_submit = self.client.post(
            self._detail_url(po.id, "submit/"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(owner_submit.status_code, 200)
        po.refresh_from_db()
        self.assertEqual(po.status, PurchaseOrder.SUBMITTED)

        self._auth(self.admin)
        already_submitted = self.client.post(
            self._detail_url(po.id, "submit/"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(already_submitted.status_code, 400)

        po_cancelled = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0002",
            supplier=self.supplier,
            branch=self.branch,
            status=PurchaseOrder.CANCELLED,
            created_by=self.owner,
        )
        self._auth(self.owner)
        cancelled_submit = self.client.post(
            self._detail_url(po_cancelled.id, "submit/"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(cancelled_submit.status_code, 400)

        for user in (self.staff, self.parent_admin_user):
            ready_po = PurchaseOrder.objects.for_org(self.acme).create(
                organization=self.acme,
                po_number=f"PO-00{10 + len(user.username)}",
                supplier=self.supplier,
                branch=self.branch,
                created_by=self.owner,
            )
            ready_po.lines.create(item=self.item_a, ordered_quantity=1, unit_price=Decimal("2.00"))
            self._auth(user)
            response = self.client.post(
                self._detail_url(ready_po.id, "submit/"),
                {},
                format="json",
                HTTP_HOST=self._host(),
            )
            self.assertEqual(response.status_code, 403)

        admin_po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0040",
            supplier=self.supplier,
            branch=self.branch,
            created_by=self.owner,
        )
        admin_po.lines.create(item=self.item_a, ordered_quantity=1, unit_price=Decimal("3.00"))
        self._auth(self.admin)
        admin_submit = self.client.post(
            self._detail_url(admin_po.id, "submit/"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(admin_submit.status_code, 200)
        admin_po.refresh_from_db()
        self.assertEqual(admin_po.status, PurchaseOrder.SUBMITTED)

    def test_cancel_rules_and_permissions(self):
        draft_po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0001",
            supplier=self.supplier,
            branch=self.branch,
            created_by=self.owner,
        )
        submitted_po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0002",
            supplier=self.supplier,
            branch=self.branch,
            status=PurchaseOrder.SUBMITTED,
            created_by=self.owner,
        )
        fully_received_po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0003",
            supplier=self.supplier,
            branch=self.branch,
            status=PurchaseOrder.FULLY_RECEIVED,
            created_by=self.owner,
        )

        self._auth(self.owner)
        cancel_draft = self.client.post(
            self._detail_url(draft_po.id, "cancel/"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(cancel_draft.status_code, 200)
        draft_po.refresh_from_db()
        self.assertEqual(draft_po.status, PurchaseOrder.CANCELLED)

        cancel_submitted = self.client.post(
            self._detail_url(submitted_po.id, "cancel/"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(cancel_submitted.status_code, 200)
        submitted_po.refresh_from_db()
        self.assertEqual(submitted_po.status, PurchaseOrder.CANCELLED)

        cancel_fully_received = self.client.post(
            self._detail_url(fully_received_po.id, "cancel/"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(cancel_fully_received.status_code, 400)

        cancel_again = self.client.post(
            self._detail_url(draft_po.id, "cancel/"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(cancel_again.status_code, 400)

        for user in (self.admin, self.staff, self.parent_admin_user):
            po = PurchaseOrder.objects.for_org(self.acme).create(
                organization=self.acme,
                po_number=f"PO-X-{user.username}",
                supplier=self.supplier,
                branch=self.branch,
                created_by=self.owner,
            )
            self._auth(user)
            response = self.client.post(
                self._detail_url(po.id, "cancel/"),
                {},
                format="json",
                HTTP_HOST=self._host(),
            )
            self.assertEqual(response.status_code, 403)

    def test_add_line_validation_and_permissions(self):
        po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0001",
            supplier=self.supplier,
            branch=self.branch,
            created_by=self.owner,
        )

        self.assertEqual(self._add_line(po.id, self.owner).status_code, 201)
        self.assertEqual(self._add_line(po.id, self.admin, item=str(self.item_b.id)).status_code, 201)
        self.assertEqual(self._add_line(po.id, self.staff, item=str(self.item_b.id)).status_code, 403)
        self.assertEqual(self._add_line(po.id, self.parent_admin_user, item=str(self.item_b.id)).status_code, 403)

        duplicate = self._add_line(po.id, self.owner)
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.data["item"][0], "This item already exists on the purchase order.")

        item_cross_org = self._add_line(po.id, self.owner, item=str(self.other_item.id))
        self.assertEqual(item_cross_org.status_code, 400)
        self.assertIn("item", item_cross_org.data)

        zero_quantity = self._add_line(po.id, self.owner, item=str(self.item_b.id), ordered_quantity=0)
        self.assertEqual(zero_quantity.status_code, 400)
        self.assertIn("ordered_quantity", zero_quantity.data)

        negative_quantity = self._add_line(po.id, self.owner, item=str(self.item_b.id), ordered_quantity=-1)
        self.assertEqual(negative_quantity.status_code, 400)
        self.assertIn("ordered_quantity", negative_quantity.data)

        zero_price = self._add_line(po.id, self.owner, item=str(self.item_b.id), unit_price="0.00")
        self.assertEqual(zero_price.status_code, 400)
        self.assertIn("unit_price", zero_price.data)

        negative_price = self._add_line(po.id, self.owner, item=str(self.item_b.id), unit_price="-1.00")
        self.assertEqual(negative_price.status_code, 400)
        self.assertIn("unit_price", negative_price.data)

        po.status = PurchaseOrder.SUBMITTED
        po.save(update_fields=["status", "updated_at"])
        submitted_add = self._add_line(po.id, self.owner, item=str(self.item_b.id))
        self.assertEqual(submitted_add.status_code, 400)

    def test_update_line_rules(self):
        po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0001",
            supplier=self.supplier,
            branch=self.branch,
            created_by=self.owner,
        )
        line_a = po.lines.create(item=self.item_a, ordered_quantity=2, unit_price=Decimal("4.00"))
        line_b = po.lines.create(item=self.item_b, ordered_quantity=3, unit_price=Decimal("5.00"))

        for user, expected_status in (
            (self.owner, 200),
            (self.admin, 200),
            (self.staff, 403),
            (self.parent_admin_user, 403),
        ):
            self._auth(user)
            response = self.client.patch(
                self._detail_url(po.id, f"lines/{line_a.id}/"),
                {"ordered_quantity": 9},
                format="json",
                HTTP_HOST=self._host(),
            )
            self.assertEqual(response.status_code, expected_status)

        line_a.refresh_from_db()
        self.assertEqual(line_a.ordered_quantity, 9)

        self._auth(self.owner)
        duplicate_item = self.client.patch(
            self._detail_url(po.id, f"lines/{line_a.id}/"),
            {"item": str(line_b.item_id)},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(duplicate_item.status_code, 400)
        self.assertIn("item", duplicate_item.data)

        same_item = self.client.patch(
            self._detail_url(po.id, f"lines/{line_a.id}/"),
            {"item": str(line_a.item_id)},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(same_item.status_code, 200)

        po.status = PurchaseOrder.SUBMITTED
        po.save(update_fields=["status", "updated_at"])
        submitted_update = self.client.patch(
            self._detail_url(po.id, f"lines/{line_a.id}/"),
            {"ordered_quantity": 10},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(submitted_update.status_code, 400)

    def test_remove_line_rules_and_base_destroy_block(self):
        po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0001",
            supplier=self.supplier,
            branch=self.branch,
            created_by=self.owner,
        )
        line = po.lines.create(item=self.item_a, ordered_quantity=2, unit_price=Decimal("4.00"))

        self._auth(self.owner)
        missing_line = self.client.delete(
            self._detail_url(po.id, "lines/999999/remove/"),
            HTTP_HOST=self._host(),
        )
        self.assertEqual(missing_line.status_code, 404)

        self._auth(self.staff)
        staff_remove = self.client.delete(
            self._detail_url(po.id, f"lines/{line.id}/remove/"),
            HTTP_HOST=self._host(),
        )
        self.assertEqual(staff_remove.status_code, 403)

        self._auth(self.parent_admin_user)
        parent_remove = self.client.delete(
            self._detail_url(po.id, f"lines/{line.id}/remove/"),
            HTTP_HOST=self._host(),
        )
        self.assertEqual(parent_remove.status_code, 403)

        self._auth(self.admin)
        admin_remove = self.client.delete(
            self._detail_url(po.id, f"lines/{line.id}/remove/"),
            HTTP_HOST=self._host(),
        )
        self.assertEqual(admin_remove.status_code, 204)

        line = po.lines.create(item=self.item_a, ordered_quantity=2, unit_price=Decimal("4.00"))
        po.status = PurchaseOrder.SUBMITTED
        po.save(update_fields=["status", "updated_at"])
        self._auth(self.owner)
        submitted_remove = self.client.delete(
            self._detail_url(po.id, f"lines/{line.id}/remove/"),
            HTTP_HOST=self._host(),
        )
        self.assertEqual(submitted_remove.status_code, 400)

        destroy_response = self.client.delete(
            self._detail_url(po.id),
            HTTP_HOST=self._host(),
        )
        self.assertEqual(destroy_response.status_code, 405)

    def test_read_access_and_parent_read_only_behavior(self):
        acme_po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0001",
            supplier=self.supplier,
            branch=self.branch,
            notes="Visible to Acme",
            created_by=self.owner,
        )
        acme_po.lines.create(item=self.item_a, ordered_quantity=2, unit_price=Decimal("4.00"))

        for user in (self.owner, self.admin, self.staff):
            self._auth(user)
            list_response = self.client.get(self._base_url(), HTTP_HOST=self._host())
            self.assertEqual(list_response.status_code, 200)
            ids = {row["id"] for row in list_response.data["results"]}
            self.assertIn(str(acme_po.id), ids)
            self.assertNotIn(str(self.globex_po.id), ids)

        self._auth(self.parent_viewer_user)
        parent_list = self.client.get(self._base_url(), HTTP_HOST=self._host())
        self.assertEqual(parent_list.status_code, 200)
        parent_ids = {row["id"] for row in parent_list.data["results"]}
        self.assertIn(str(acme_po.id), parent_ids)

        parent_retrieve = self.client.get(self._detail_url(acme_po.id), HTTP_HOST=self._host())
        self.assertEqual(parent_retrieve.status_code, 200)
        self.assertEqual(len(parent_retrieve.data["lines"]), 1)
        self.assertEqual(parent_retrieve.data["lines"][0]["ordered_quantity"], 2)
        self.assertEqual(parent_retrieve.data["created_by"], self.owner.id)

        parent_cross_org = self.client.get(
            self._base_url(org_id=self.globex.id),
            HTTP_HOST=self._host("globex-po"),
        )
        self.assertEqual(parent_cross_org.status_code, 200)
        globex_ids = {row["id"] for row in parent_cross_org.data["results"]}
        self.assertIn(str(self.globex_po.id), globex_ids)

        parent_lines = self.client.get(
            self._detail_url(acme_po.id, "lines/"),
            HTTP_HOST=self._host(),
        )
        self.assertEqual(parent_lines.status_code, 200)
        self.assertEqual(len(parent_lines.data), 1)

        parent_create = self.client.post(
            self._base_url(),
            self._create_payload(),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(parent_create.status_code, 403)

    def test_non_member_and_cross_org_access_are_blocked(self):
        acme_po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0001",
            supplier=self.supplier,
            branch=self.branch,
            created_by=self.owner,
        )

        self._auth(self.outsider)
        outsider_list = self.client.get(self._base_url(), HTTP_HOST=self._host())
        self.assertEqual(outsider_list.status_code, 403)

        self._auth(self.owner)
        hidden_cross_org = self.client.get(self._detail_url(self.globex_po.id), HTTP_HOST=self._host())
        self.assertEqual(hidden_cross_org.status_code, 404)

        own_retrieve = self.client.get(self._detail_url(acme_po.id), HTTP_HOST=self._host())
        self.assertEqual(own_retrieve.status_code, 200)

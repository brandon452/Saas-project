from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import BranchItem, MasterItem, OrgItem, StockLedger
from inventory.services import record_stock_movement
from tenancy.models import Organization, OrganizationMember


class BranchScopingTests(APITestCase):
    def _create_org_item(self, organization, name, sku, *, item_name=""):
        master_item = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.for_org(organization).create(
            organization=organization,
            master_item=master_item,
            name=item_name,
        )

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="b_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="b_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="b_staff", password="Passw0rd!")

        self.org = Organization.objects.create(name="Acme", slug="acme")
        self.other_org = Organization.objects.create(name="Globex", slug="globex")

        self.branch_a = Branch.objects.for_org(self.org).create(organization=self.org, name="A", code="A")
        self.branch_b = Branch.objects.for_org(self.org).create(organization=self.org, name="B", code="B")
        self.other_branch = Branch.objects.for_org(self.other_org).create(
            organization=self.other_org,
            name="Other",
            code="O",
        )

        OrganizationMember.objects.create(user=self.owner, organization=self.org, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.admin, organization=self.org, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(
            user=self.staff,
            organization=self.org,
            role="STAFF",
            is_active=True,
            assigned_branch=self.branch_a,
        )

        self.item = self._create_org_item(self.org, "Item", "ITM-1")
        BranchItem.objects.create(org_item=self.item, branch=self.branch_a, is_active=True)
        BranchItem.objects.create(org_item=self.item, branch=self.branch_b, is_active=True)

        record_stock_movement(
            org=self.org,
            branch=self.branch_a,
            item=self.item,
            quantity=Decimal("2.0000"),
            movement_type="RECEIPT",
            unit_cost=Decimal("10.0000"),
            performed_by=self.owner,
            idempotency_key="scope-a-1",
        )
        record_stock_movement(
            org=self.org,
            branch=self.branch_b,
            item=self.item,
            quantity=Decimal("3.0000"),
            movement_type="RECEIPT",
            unit_cost=Decimal("10.0000"),
            performed_by=self.owner,
            idempotency_key="scope-b-1",
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _url(self, path):
        return f"/api/orgs/{self.org.id}/{path}"

    def test_branch_resolution_per_role(self):
        self._auth(self.owner)
        owner_no_header = self.client.get(self._url("inventory/stock/"))
        owner_with_header = self.client.get(self._url("inventory/stock/"), HTTP_X_BRANCH_ID=str(self.branch_a.id))
        self.assertEqual(owner_no_header.status_code, 200)
        self.assertGreater(owner_no_header.data["count"], owner_with_header.data["count"])

        self._auth(self.admin)
        admin_with_header = self.client.get(self._url("inventory/stock/"), HTTP_X_BRANCH_ID=str(self.branch_b.id))
        self.assertEqual(admin_with_header.status_code, 200)
        self.assertEqual(admin_with_header.data["count"], 1)

        self._auth(self.staff)
        staff_ignored_header = self.client.get(
            self._url("inventory/stock/"),
            HTTP_X_BRANCH_ID=str(self.branch_b.id),
        )
        self.assertEqual(staff_ignored_header.status_code, 200)
        self.assertEqual(staff_ignored_header.data["count"], 1)
        self.assertEqual(staff_ignored_header.data["results"][0]["branch"]["id"], str(self.branch_a.id))

    def test_staff_without_assigned_branch_blocked_on_branch_scoped_only(self):
        OrganizationMember.objects.for_org(self.org).filter(user=self.staff).update(assigned_branch=None)
        self._auth(self.staff)

        stock = self.client.get(self._url("inventory/stock/"))
        movements = self.client.get(self._url("inventory/movements/"))
        branches = self.client.get(self._url("branches/"))
        items = self.client.get(self._url("inventory/items/"))

        self.assertEqual(stock.status_code, 403)
        self.assertEqual(movements.status_code, 403)
        self.assertEqual(branches.status_code, 403)
        self.assertEqual(items.status_code, 403)

    def test_owner_admin_unrestricted_detail_update_with_active_header(self):
        self._auth(self.owner)
        owner_retrieve_other = self.client.get(
            self._url(f"branches/{self.branch_b.id}/"),
            HTTP_X_BRANCH_ID=str(self.branch_a.id),
        )
        owner_patch_other = self.client.patch(
            self._url(f"branches/{self.branch_b.id}/"),
            {"name": "B-updated"},
            format="json",
            HTTP_X_BRANCH_ID=str(self.branch_a.id),
        )
        self.assertEqual(owner_retrieve_other.status_code, 200)
        self.assertEqual(owner_patch_other.status_code, 200)

        self._auth(self.admin)
        admin_retrieve_other = self.client.get(
            self._url(f"branches/{self.branch_b.id}/"),
            HTTP_X_BRANCH_ID=str(self.branch_a.id),
        )
        self.assertEqual(admin_retrieve_other.status_code, 200)

    def test_staff_branch_detail_restricted(self):
        self._auth(self.staff)
        own = self.client.get(self._url(f"branches/{self.branch_a.id}/"))
        other = self.client.get(self._url(f"branches/{self.branch_b.id}/"))
        self.assertEqual(own.status_code, 200)
        self.assertEqual(other.status_code, 404)

    def test_movement_writes_staff_restricted_owner_admin_unrestricted(self):
        self._auth(self.owner)
        owner_other_branch = self.client.post(
            self._url("inventory/movements/"),
            {
                "item": str(self.item.id),
                "quantity": "1.0000",
                "movement_type": "RECEIPT",
                "unit_cost": "5.0000",
                "idempotency_key": "owner-any-branch",
            },
            format="json",
            HTTP_X_BRANCH_ID=str(self.branch_b.id),
        )
        self.assertEqual(owner_other_branch.status_code, 201)

        self._auth(self.admin)
        admin_other_branch = self.client.post(
            self._url("inventory/movements/"),
            {
                "item": str(self.item.id),
                "quantity": "1.0000",
                "movement_type": "RECEIPT",
                "unit_cost": "5.0000",
                "idempotency_key": "admin-any-branch",
            },
            format="json",
            HTTP_X_BRANCH_ID=str(self.branch_b.id),
        )
        self.assertEqual(admin_other_branch.status_code, 201)

        self._auth(self.staff)
        staff_attempt_other_branch = self.client.post(
            self._url("inventory/movements/"),
            {
                "item": str(self.item.id),
                "quantity": "1.0000",
                "movement_type": "RECEIPT",
                "unit_cost": "5.0000",
                "idempotency_key": "staff-header-ignored",
            },
            format="json",
            HTTP_X_BRANCH_ID=str(self.branch_b.id),
        )
        self.assertEqual(staff_attempt_other_branch.status_code, 201)
        ledger = StockLedger.objects.for_org(self.org).get(id=staff_attempt_other_branch.data["id"])
        self.assertEqual(ledger.branch_id, self.branch_a.id)

    def test_cross_org_branch_header_denied_for_owner_admin(self):
        self._auth(self.owner)
        owner = self.client.get(self._url("inventory/stock/"), HTTP_X_BRANCH_ID=str(self.other_branch.id))
        self.assertEqual(owner.status_code, 403)

        self._auth(self.admin)
        admin = self.client.get(self._url("inventory/stock/"), HTTP_X_BRANCH_ID=str(self.other_branch.id))
        self.assertEqual(admin.status_code, 403)

    def test_member_create_update_assigned_branch_rules(self):
        User = get_user_model()
        target = User.objects.create_user(username="branch_target", password="Passw0rd!")
        self._auth(self.owner)

        staff_missing = self.client.post(
            self._url("members/"),
            {"user_id": target.id, "role": "STAFF"},
            format="json",
        )
        self.assertEqual(staff_missing.status_code, 400)

        staff_valid = self.client.post(
            self._url("members/"),
            {"user_id": target.id, "role": "STAFF", "assigned_branch": str(self.branch_a.id)},
            format="json",
        )
        self.assertEqual(staff_valid.status_code, 201)
        member_id = OrganizationMember.objects.for_org(self.org).get(user=target).id

        owner_with_branch = self.client.post(
            self._url("members/"),
            {
                "user_id": self.admin.id,
                "role": "OWNER",
                "assigned_branch": str(self.branch_a.id),
            },
            format="json",
        )
        self.assertEqual(owner_with_branch.status_code, 400)

        set_admin_without_clearing_branch = self.client.patch(
            self._url(f"members/{member_id}/"),
            {"role": "ADMIN"},
            format="json",
        )
        self.assertEqual(set_admin_without_clearing_branch.status_code, 400)

        set_admin_with_clearing_branch = self.client.patch(
            self._url(f"members/{member_id}/"),
            {"role": "ADMIN", "assigned_branch": None},
            format="json",
        )
        self.assertEqual(set_admin_with_clearing_branch.status_code, 200)

    def test_branch_deleted_staff_blocked_and_owner_admin_unaffected(self):
        temp_branch = Branch.objects.for_org(self.org).create(organization=self.org, name="Temp", code="TMP")
        OrganizationMember.objects.for_org(self.org).filter(user=self.staff).update(assigned_branch=temp_branch)
        temp_branch.delete()

        self._auth(self.staff)
        blocked = self.client.get(self._url("inventory/stock/"))
        allowed_items = self.client.get(self._url("inventory/items/"))
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(allowed_items.status_code, 403)

        self._auth(self.owner)
        owner_ok = self.client.get(self._url("inventory/stock/"))
        self.assertEqual(owner_ok.status_code, 200)

    def test_request_org_membership_cached_on_branch_scoped_endpoints(self):
        self._auth(self.owner)
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.post(
                self._url("inventory/movements/"),
                {
                    "item": str(self.item.id),
                    "quantity": "1.0000",
                    "movement_type": "RECEIPT",
                    "unit_cost": "5.0000",
                    "idempotency_key": "membership-cache-check",
                },
                format="json",
                HTTP_X_BRANCH_ID=str(self.branch_a.id),
            )
        self.assertEqual(response.status_code, 201)
        self.assertLessEqual(len(ctx.captured_queries), 18)

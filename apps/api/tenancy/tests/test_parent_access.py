from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import MasterItem, OrgItem
from inventory.services import record_stock_movement
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


class ParentAccessTests(APITestCase):
    def _create_org_item(self, organization, name, sku, *, item_name=""):
        master_item = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.for_org(organization).create(
            organization=organization,
            master_item=master_item,
            name=item_name,
        )

    def setUp(self):
        User = get_user_model()
        self.parent_admin_user = User.objects.create_user(username="parent_admin", password="Passw0rd!")
        self.parent_viewer_user = User.objects.create_user(username="parent_viewer", password="Passw0rd!")
        self.org_owner_user = User.objects.create_user(username="org_owner", password="Passw0rd!")
        self.org_staff_user = User.objects.create_user(username="org_staff", password="Passw0rd!")
        self.target_user = User.objects.create_user(username="target_parent", password="Passw0rd!")

        self.acme = Organization.objects.create(name="Acme", slug="acme")
        self.globex = Organization.objects.create(name="Globex", slug="globex")
        self.inactive = Organization.objects.create(name="Inactive", slug="inactive", is_active=False)

        self.acme_branch_a = Branch.objects.for_org(self.acme).create(organization=self.acme, name="A", code="A")
        self.acme_branch_b = Branch.objects.for_org(self.acme).create(organization=self.acme, name="B", code="B")

        OrganizationMember.objects.create(user=self.org_owner_user, organization=self.acme, role="OWNER", is_active=True)
        OrganizationMember.objects.create(
            user=self.org_staff_user,
            organization=self.acme,
            role="STAFF",
            is_active=True,
            assigned_branch=self.acme_branch_a,
        )

        self.parent_admin = ParentCompanyMember.objects.create(
            user=self.parent_admin_user,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
            created_by=self.parent_admin_user,
        )
        self.parent_viewer = ParentCompanyMember.objects.create(
            user=self.parent_viewer_user,
            role=ParentCompanyMember.PARENT_VIEWER,
            is_active=True,
            created_by=self.parent_admin_user,
        )

        self.item_a = self._create_org_item(self.acme, "I1", "I1")
        record_stock_movement(
            org=self.acme,
            branch=self.acme_branch_a,
            item=self.item_a,
            quantity=Decimal("1.0000"),
            movement_type="RECEIPT",
            performed_by=self.org_owner_user,
            idempotency_key="parent-seed-a",
        )
        record_stock_movement(
            org=self.acme,
            branch=self.acme_branch_b,
            item=self.item_a,
            quantity=Decimal("1.0000"),
            movement_type="RECEIPT",
            performed_by=self.org_owner_user,
            idempotency_key="parent-seed-b",
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _org_url(self, org_id, path):
        return f"/api/orgs/{org_id}/{path}"

    def test_parent_membership_one_to_one_enforced(self):
        with self.assertRaises(IntegrityError):
            ParentCompanyMember.objects.create(
                user=self.parent_admin_user,
                role=ParentCompanyMember.PARENT_VIEWER,
                is_active=True,
            )

    def test_parent_org_resolution_and_inactive_org(self):
        self._auth(self.parent_viewer_user)
        ok = self.client.get(self._org_url(self.acme.id, "inventory/items/"))
        self.assertEqual(ok.status_code, 200)

        inactive = self.client.get(self._org_url(self.inactive.id, "inventory/items/"))
        self.assertEqual(inactive.status_code, 404)

    def test_parent_branch_context_ignored(self):
        self._auth(self.parent_viewer_user)
        all_rows = self.client.get(self._org_url(self.acme.id, "inventory/stock/"))
        with_header = self.client.get(
            self._org_url(self.acme.id, "inventory/stock/"),
            HTTP_X_BRANCH_ID=str(self.acme_branch_a.id),
        )
        self.assertEqual(all_rows.status_code, 200)
        self.assertEqual(with_header.status_code, 200)
        self.assertEqual(all_rows.data["count"], with_header.data["count"])

    def test_org_list_for_parent_returns_all_active_orgs(self):
        self._auth(self.parent_viewer_user)
        response = self.client.get("/api/orgs/")
        self.assertEqual(response.status_code, 200)
        org_ids = {row["id"] for row in response.data}
        self.assertIn(str(self.acme.id), org_ids)
        self.assertIn(str(self.globex.id), org_ids)
        self.assertNotIn(str(self.inactive.id), org_ids)

    def test_governance_endpoints(self):
        self._auth(self.parent_admin_user)
        create_org = self.client.post(
            "/api/orgs/",
            {"name": "New Org", "slug": "new-org", "is_active": True},
            format="json",
        )
        self.assertEqual(create_org.status_code, 201)

        deactivate = self.client.patch(
            self._org_url(self.globex.id, "governance/"),
            {"is_active": False},
            format="json",
        )
        self.assertEqual(deactivate.status_code, 200)

        reactivate_blocked = self.client.patch(
            self._org_url(self.globex.id, "governance/"),
            {"is_active": True},
            format="json",
        )
        self.assertEqual(reactivate_blocked.status_code, 400)

        self._auth(self.parent_viewer_user)
        viewer_blocked = self.client.post(
            "/api/orgs/",
            {"name": "Nope", "slug": "nope"},
            format="json",
        )
        self.assertEqual(viewer_blocked.status_code, 403)

    def test_parent_cannot_perform_operational_writes(self):
        self._auth(self.parent_admin_user)

        item_write = self.client.post(
            self._org_url(self.acme.id, "inventory/items/"),
            {
                "master_item": str(MasterItem.objects.create(name="Parent Write", sku="P-1").id),
                "name": "Parent Write",
            },
            format="json",
        )
        self.assertEqual(item_write.status_code, 403)

        movement_write = self.client.post(
            self._org_url(self.acme.id, "inventory/movements/"),
            {
                "item": str(self.item_a.id),
                "quantity": "1.0000",
                "movement_type": "RECEIPT",
                "idempotency_key": "parent-write-block",
            },
            format="json",
            HTTP_X_BRANCH_ID=str(self.acme_branch_a.id),
        )
        self.assertEqual(movement_write.status_code, 403)

        branch_write = self.client.patch(
            self._org_url(self.acme.id, f"branches/{self.acme_branch_a.id}/"),
            {"name": "rename"},
            format="json",
        )
        self.assertEqual(branch_write.status_code, 403)

    def test_parent_member_management_and_self_deactivate_block(self):
        self._auth(self.parent_admin_user)

        create = self.client.post(
            "/api/parent/members/",
            {"user_id": self.target_user.id, "role": ParentCompanyMember.PARENT_VIEWER},
            format="json",
        )
        self.assertEqual(create.status_code, 201)
        created_id = ParentCompanyMember.objects.get(user=self.target_user).id

        deactivate = self.client.delete(f"/api/parent/members/{created_id}/")
        self.assertEqual(deactivate.status_code, 204)

        self_deactivate = self.client.delete(f"/api/parent/members/{self.parent_admin.id}/")
        self.assertEqual(self_deactivate.status_code, 403)

    def test_dual_role_prohibition(self):
        self._auth(self.parent_admin_user)

        create_parent_for_org_member = self.client.post(
            "/api/parent/members/",
            {"user_id": self.org_owner_user.id, "role": ParentCompanyMember.PARENT_VIEWER},
            format="json",
        )
        self.assertEqual(create_parent_for_org_member.status_code, 400)

        self._auth(self.org_owner_user)
        create_org_member_for_parent_user = self.client.post(
            self._org_url(self.acme.id, "members/"),
            {"user_id": self.parent_viewer_user.id, "role": "OWNER"},
            format="json",
        )
        self.assertEqual(create_org_member_for_parent_user.status_code, 400)

        # Reactivation path with org memberships must be blocked
        temp_parent_user = get_user_model().objects.create_user(username="temp_parent", password="Passw0rd!")
        inactive_parent = ParentCompanyMember.objects.create(
            user=temp_parent_user,
            role=ParentCompanyMember.PARENT_VIEWER,
            is_active=False,
            created_by=self.parent_admin_user,
        )
        OrganizationMember.objects.create(
            user=temp_parent_user,
            organization=self.acme,
            role="OWNER",
            is_active=False,
        )
        self._auth(self.parent_admin_user)
        reactivate = self.client.patch(
            f"/api/parent/members/{inactive_parent.id}/",
            {"is_active": True},
            format="json",
        )
        self.assertEqual(reactivate.status_code, 400)

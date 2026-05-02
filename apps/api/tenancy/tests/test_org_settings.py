from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from branches.models import Branch
from tenancy.models import Organization, OrganizationMember, ParentCompany, ParentCompanyMember


class OrgSettingsTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="staff", password="Passw0rd!")
        self.outsider = User.objects.create_user(username="outsider", password="Passw0rd!")
        self.parent_admin_user = User.objects.create_user(username="parent_admin", password="Passw0rd!")
        self.other_parent_admin_user = User.objects.create_user(username="other_parent_admin", password="Passw0rd!")

        self.org = Organization.objects.create(name="Acme", slug="acme")
        self.other_parent = ParentCompany.objects.create(name="Other Parent", slug="other-parent")
        self.other_org = Organization.objects.create(
            parent_company=self.other_parent,
            name="Other Org",
            slug="other-org",
        )
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="MAIN",
        )

        OrganizationMember.objects.create(user=self.owner, organization=self.org, role="OWNER")
        OrganizationMember.objects.create(user=self.admin, organization=self.org, role="ADMIN")
        OrganizationMember.objects.create(
            user=self.staff,
            organization=self.org,
            role="STAFF",
            assigned_branch=self.branch,
        )
        ParentCompanyMember.objects.create(
            user=self.parent_admin_user,
            role=ParentCompanyMember.PARENT_ADMIN,
        )
        ParentCompanyMember.objects.create(
            user=self.other_parent_admin_user,
            parent_company=self.other_parent,
            role=ParentCompanyMember.PARENT_ADMIN,
        )

    def _url(self, org_id=None):
        return f"/api/orgs/{org_id or self.org.id}/settings/"

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_owner_can_read_and_update_org_settings(self):
        self._auth(self.owner)

        read = self.client.get(self._url())
        self.assertEqual(read.status_code, 200)
        self.assertEqual(read.data["name"], "Acme")
        self.assertEqual(read.data["slug"], "acme")
        self.assertEqual(read.data["default_currency"], "USD")
        self.assertEqual(read.data["default_timezone"], "UTC")
        self.assertFalse(read.data["allow_negative_stock"])
        self.assertEqual(read.data["purchase_order_prefix"], "PO")
        self.assertEqual(read.data["purchase_order_next_number"], 1)
        self.assertTrue(read.data["branch_transfer_approval_required"])
        self.assertTrue(read.data["stock_take_approval_required"])
        self.assertIn("parent_company_name", read.data)

        update = self.client.patch(
            self._url(),
            {
                "name": "Acme Holdings",
                "default_currency": "sgd",
                "default_timezone": "Asia/Singapore",
                "allow_negative_stock": True,
                "purchase_order_prefix": "sg-po",
                "purchase_order_next_number": 42,
                "branch_transfer_approval_required": False,
                "stock_take_approval_required": False,
            },
            format="json",
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.data["name"], "Acme Holdings")
        self.assertEqual(update.data["default_currency"], "SGD")
        self.assertEqual(update.data["purchase_order_prefix"], "SG-PO")

        self.org.refresh_from_db()
        self.assertEqual(self.org.name, "Acme Holdings")
        self.assertEqual(self.org.default_currency, "SGD")
        self.assertEqual(self.org.default_timezone, "Asia/Singapore")
        self.assertTrue(self.org.allow_negative_stock)
        self.assertEqual(self.org.purchase_order_prefix, "SG-PO")
        self.assertEqual(self.org.purchase_order_next_number, 1)
        self.assertFalse(self.org.branch_transfer_approval_required)
        self.assertFalse(self.org.stock_take_approval_required)

    def test_admin_can_update_org_settings(self):
        self._auth(self.admin)
        response = self.client.patch(self._url(), {"name": "Acme Admin"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Acme Admin")

    def test_staff_and_outsider_are_blocked(self):
        for user in (self.staff, self.outsider):
            self._auth(user)
            read = self.client.get(self._url())
            update = self.client.patch(self._url(), {"name": "Blocked"}, format="json")

            self.assertEqual(read.status_code, 403)
            self.assertEqual(update.status_code, 403)

    def test_parent_admin_access_is_scoped_to_parent_company(self):
        self._auth(self.parent_admin_user)
        response = self.client.patch(self._url(), {"name": "Parent Rename"}, format="json")
        self.assertEqual(response.status_code, 200)

        self._auth(self.other_parent_admin_user)
        foreign = self.client.get(self._url())
        own = self.client.get(self._url(self.other_org.id))

        self.assertEqual(foreign.status_code, 403)
        self.assertEqual(own.status_code, 200)

    def test_read_only_fields_are_not_updated(self):
        self._auth(self.owner)
        response = self.client.patch(
            self._url(),
            {"name": "Renamed", "slug": "changed", "is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.slug, "acme")
        self.assertTrue(self.org.is_active)

    def test_operational_settings_are_validated(self):
        self._auth(self.owner)

        response = self.client.patch(
            self._url(),
            {
                "default_currency": "US",
                "default_timezone": "Mars/Base",
                "purchase_order_prefix": "PO!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("default_currency", response.data)
        self.assertIn("default_timezone", response.data)
        self.assertIn("purchase_order_prefix", response.data)

    def test_purchase_order_next_number_is_read_only(self):
        self._auth(self.owner)
        response = self.client.patch(
            self._url(),
            {"purchase_order_next_number": 999},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.purchase_order_next_number, 1)

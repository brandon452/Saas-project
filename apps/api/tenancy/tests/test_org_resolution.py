from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import Resolver404, resolve
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import BranchItem, MasterItem, OrgItem
from tenancy.models import Organization, OrganizationMember
from tenancy.permissions import IsOrgMember


class OrgResolutionTests(APITestCase):
    def _create_org_item(self, organization, name, sku, *, item_name=""):
        master_item = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.for_org(organization).create(
            organization=organization,
            master_item=master_item,
            name=item_name,
        )

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="org_user", password="Passw0rd!")
        self.non_member = User.objects.create_user(username="other_org_user", password="Passw0rd!")

        self.acme = Organization.objects.create(name="Acme", slug="acme")
        self.globex = Organization.objects.create(name="Globex", slug="globex")
        self.inactive_org = Organization.objects.create(name="Inactive", slug="inactive", is_active=False)

        OrganizationMember.objects.create(user=self.user, organization=self.acme, role="ADMIN", is_active=True)

        self.acme_branch = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Main",
            code="MAIN",
        )
        self.globex_branch = Branch.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Main",
            code="GLOBEX-MAIN",
        )
        self.acme_item = self._create_org_item(self.acme, "Item", "ITEM-1")
        BranchItem.objects.create(org_item=self.acme_item, branch=self.acme_branch, is_active=True)

    def test_org_resolution_from_url(self):
        self.client.force_authenticate(self.user)
        ok = self.client.get(f"/api/orgs/{self.acme.id}/inventory/items/", HTTP_HOST="random.host")
        self.assertEqual(ok.status_code, 200)

        self.client.force_authenticate(self.non_member)
        forbidden = self.client.get(f"/api/orgs/{self.acme.id}/inventory/items/", HTTP_HOST="random.host")
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_authenticate(self.user)
        not_found = self.client.get("/api/orgs/00000000-0000-0000-0000-000000000000/inventory/items/")
        self.assertEqual(not_found.status_code, 404)

        inactive = self.client.get(f"/api/orgs/{self.inactive_org.id}/inventory/items/")
        self.assertEqual(inactive.status_code, 404)

    def test_request_org_set_before_permission_check(self):
        self.client.force_authenticate(self.user)
        original = IsOrgMember.has_permission

        def wrapped(permission_self, request, view):
            self.assertIsNotNone(getattr(request, "org", None))
            return original(permission_self, request, view)

        with patch.object(IsOrgMember, "has_permission", autospec=True, side_effect=wrapped):
            response = self.client.get(f"/api/orgs/{self.acme.id}/inventory/items/")
        self.assertEqual(response.status_code, 200)

    def test_org_list_endpoint(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/orgs/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(str(response.data[0]["id"]), str(self.acme.id))

        self.client.force_authenticate(self.non_member)
        empty = self.client.get("/api/orgs/")
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.data, [])

    def test_nested_routes_and_old_flat_routes(self):
        self.client.force_authenticate(self.user)
        nested = self.client.get(f"/api/orgs/{self.acme.id}/inventory/items/")
        self.assertEqual(nested.status_code, 200)

        with self.assertRaises(Resolver404):
            resolve("/api/inventory/items/")

    def test_branch_context_and_cross_org_validation(self):
        self.client.force_authenticate(self.user)

        ok = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/movements/",
            {
                "item": str(self.acme_item.id),
                "quantity": "1.0000",
                "movement_type": "RECEIPT",
                "unit_cost": "5.0000",
                "idempotency_key": "org-rev-a-1",
            },
            format="json",
            HTTP_X_BRANCH_ID=str(self.acme_branch.id),
        )
        self.assertEqual(ok.status_code, 201)

        wrong_org_branch = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/movements/",
            {
                "item": str(self.acme_item.id),
                "quantity": "1.0000",
                "movement_type": "RECEIPT",
                "unit_cost": "5.0000",
                "idempotency_key": "org-rev-a-2",
            },
            format="json",
            HTTP_X_BRANCH_ID=str(self.globex_branch.id),
        )
        self.assertEqual(wrong_org_branch.status_code, 403)

        no_branch_header = self.client.get(f"/api/orgs/{self.acme.id}/inventory/movements/")
        self.assertEqual(no_branch_header.status_code, 200)

    def test_old_subdomain_middleware_removed(self):
        self.assertNotIn("tenancy.middleware.TenantMiddleware", settings.MIDDLEWARE)

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import BranchItem, MasterItem, OrgItem
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


class BranchItemCatalogApiTests(APITestCase):
    def _create_org_item(self, organization, master_name, sku, *, item_name="", is_active=True):
        master_item = MasterItem.objects.create(name=master_name, sku=sku)
        return OrgItem.objects.create(
            organization=organization,
            master_item=master_item,
            name=item_name,
            is_active=is_active,
        )

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="branch_catalog_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="branch_catalog_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="branch_catalog_staff", password="Passw0rd!")
        self.parent_admin = User.objects.create_user(username="branch_catalog_parent", password="Passw0rd!")

        self.acme = Organization.objects.create(name="Acme", slug="branch-catalog-acme")
        self.globex = Organization.objects.create(name="Globex", slug="branch-catalog-globex")

        self.branch_a = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Branch A",
            code="ACA",
        )
        self.branch_b = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Branch B",
            code="ACB",
        )
        self.globex_branch = Branch.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Branch",
            code="GLO",
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

        self.enabled_item = self._create_org_item(
            self.acme,
            "Enabled Master",
            "CAT-ENABLED",
            item_name="Enabled Override",
        )
        self.no_branch_item = self._create_org_item(self.acme, "Loose Master", "CAT-LOOSE")
        self.inactive_branch_only = self._create_org_item(self.acme, "Inactive Branch Master", "CAT-INACTIVE")
        self.inactive_org_item = self._create_org_item(
            self.acme,
            "Inactive Org Master",
            "CAT-ORG-INACTIVE",
            is_active=False,
        )
        self.other_org_item = self._create_org_item(self.globex, "Globex Searchable", "CAT-GLOBEX")

        self.active_branch_item = BranchItem.objects.create(
            org_item=self.enabled_item,
            branch=self.branch_a,
            is_active=True,
        )
        BranchItem.objects.create(
            org_item=self.inactive_branch_only,
            branch=self.branch_a,
            is_active=False,
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _host(self, slug):
        return f"{slug}.localhost:8000"

    def _url(self):
        return f"/api/orgs/{self.acme.id}/branch-items/catalog/"

    def test_access_control(self):
        for user in (self.owner, self.admin):
            self._auth(user)
            response = self.client.get(
                f"{self._url()}?branch={self.branch_a.id}",
                HTTP_HOST=self._host(self.acme.slug),
            )
            self.assertEqual(response.status_code, 200)

        self._auth(self.staff)
        self.assertEqual(
            self.client.get(
                f"{self._url()}?branch={self.branch_a.id}",
                HTTP_HOST=self._host(self.acme.slug),
            ).status_code,
            403,
        )

        self._auth(self.parent_admin)
        self.assertEqual(
            self.client.get(
                f"{self._url()}?branch={self.branch_a.id}",
                HTTP_HOST=self._host(self.acme.slug),
            ).status_code,
            403,
        )

        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(
                f"{self._url()}?branch={self.branch_a.id}",
                HTTP_HOST=self._host(self.acme.slug),
            ).status_code,
            401,
        )

    def test_branch_validation(self):
        self._auth(self.owner)

        missing_branch = self.client.get(self._url(), HTTP_HOST=self._host(self.acme.slug))
        self.assertEqual(missing_branch.status_code, 400)
        self.assertEqual(missing_branch.data["branch"], "This field is required.")

        wrong_org_branch = self.client.get(
            f"{self._url()}?branch={self.globex_branch.id}",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(wrong_org_branch.status_code, 400)
        self.assertEqual(
            wrong_org_branch.data["branch"],
            "Branch not found or does not belong to this organisation.",
        )

    def test_response_shape_and_content_rules(self):
        self._auth(self.owner)
        response = self.client.get(
            f"{self._url()}?branch={self.branch_a.id}",
            HTTP_HOST=self._host(self.acme.slug),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data.keys()), {"count", "next", "previous", "results"})

        results = response.data["results"]
        result_map = {row["id"]: row for row in results}

        self.assertEqual(response.data["count"], 3)
        self.assertNotIn(str(self.inactive_org_item.id), result_map)
        self.assertNotIn(str(self.other_org_item.id), result_map)

        enabled_row = result_map[str(self.enabled_item.id)]
        self.assertEqual(
            set(enabled_row.keys()),
            {"id", "name", "sku", "is_enabled", "branch_item_id"},
        )
        self.assertEqual(enabled_row["name"], self.enabled_item.display_name)
        self.assertEqual(enabled_row["sku"], self.enabled_item.master_item.sku)
        self.assertTrue(enabled_row["is_enabled"])
        self.assertEqual(enabled_row["branch_item_id"], self.active_branch_item.id)

        no_branch_row = result_map[str(self.no_branch_item.id)]
        self.assertFalse(no_branch_row["is_enabled"])
        self.assertIsNone(no_branch_row["branch_item_id"])

        inactive_branch_row = result_map[str(self.inactive_branch_only.id)]
        self.assertFalse(inactive_branch_row["is_enabled"])
        self.assertIsNone(inactive_branch_row["branch_item_id"])

    def test_multiple_inactive_historical_rows_still_disabled(self):
        self._auth(self.owner)
        historical_item = self._create_org_item(self.acme, "History Master", "CAT-HISTORY")
        BranchItem.objects.create(org_item=historical_item, branch=self.branch_b, is_active=False)
        BranchItem.objects.create(org_item=historical_item, branch=self.branch_a, is_active=False)

        response = self.client.get(
            f"{self._url()}?branch={self.branch_a.id}",
            HTTP_HOST=self._host(self.acme.slug),
        )

        self.assertEqual(response.status_code, 200)
        row = next(item for item in response.data["results"] if item["id"] == str(historical_item.id))
        self.assertFalse(row["is_enabled"])
        self.assertIsNone(row["branch_item_id"])

    def test_search_matches_org_item_name_master_name_and_sku(self):
        self._auth(self.owner)

        name_match = self.client.get(
            f"{self._url()}?branch={self.branch_a.id}&search=override",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(name_match.status_code, 200)
        self.assertEqual([row["id"] for row in name_match.data["results"]], [str(self.enabled_item.id)])

        master_name_match = self.client.get(
            f"{self._url()}?branch={self.branch_a.id}&search=loose master",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(master_name_match.status_code, 200)
        self.assertEqual([row["id"] for row in master_name_match.data["results"]], [str(self.no_branch_item.id)])

        sku_match = self.client.get(
            f"{self._url()}?branch={self.branch_a.id}&search=cat-inactive",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(sku_match.status_code, 200)
        self.assertEqual([row["id"] for row in sku_match.data["results"]], [str(self.inactive_branch_only.id)])

        tenant_isolated = self.client.get(
            f"{self._url()}?branch={self.branch_a.id}&search=globex",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(tenant_isolated.status_code, 200)
        self.assertEqual(tenant_isolated.data["count"], 0)

    def test_pagination_page_two_and_total_count(self):
        self._auth(self.owner)
        for index in range(60):
            self._create_org_item(self.acme, f"Paginated {index:02d}", f"CAT-PAGE-{index:02d}")

        response = self.client.get(
            f"{self._url()}?branch={self.branch_a.id}&page=2",
            HTTP_HOST=self._host(self.acme.slug),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 63)
        self.assertEqual(len(response.data["results"]), 13)
        self.assertIsNotNone(response.data["previous"])

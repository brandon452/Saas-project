from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from suppliers.models import Supplier
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember
from tenancy.permissions import get_org_membership


class SupplierApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="supplier_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="supplier_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="supplier_staff", password="Passw0rd!")
        self.outsider = User.objects.create_user(username="supplier_outsider", password="Passw0rd!")
        self.parent_admin_user = User.objects.create_user(username="supplier_parent_admin", password="Passw0rd!")
        self.parent_viewer_user = User.objects.create_user(username="supplier_parent_viewer", password="Passw0rd!")

        self.acme = Organization.objects.create(name="Acme", slug="acme")
        self.globex = Organization.objects.create(name="Globex", slug="globex")

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

        self.active_supplier = Supplier.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Supplies",
            created_by=self.owner,
        )
        self.inactive_supplier = Supplier.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Dormant Vendor",
            is_active=False,
            created_by=self.owner,
        )
        self.globex_supplier = Supplier.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Supplier",
        )

    def _host(self, slug="acme"):
        return f"{slug}.localhost:8000"

    def _url(self, supplier_id=None, suffix=""):
        base = f"/api/orgs/{self.acme.id}/suppliers/"
        if supplier_id is None:
            return f"{base}{suffix}"
        return f"{base}{supplier_id}/{suffix}"

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_model_exact_uniqueness_and_org_scoping(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Supplier.objects.for_org(self.acme).create(
                    organization=self.acme,
                    name="Acme Supplies",
                )

        duplicate_other_org = Supplier.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Acme Supplies",
        )
        self.assertEqual(duplicate_other_org.name, "Acme Supplies")

    def test_get_org_membership_caches_and_short_circuits_parent(self):
        request = self.client.get(self._url(), HTTP_HOST=self._host()).wsgi_request
        request.user = self.admin
        request.org = self.acme

        with CaptureQueriesContext(connection) as ctx:
            first = get_org_membership(request)
            second = get_org_membership(request)

        self.assertEqual(first.role, "ADMIN")
        self.assertEqual(second.role, "ADMIN")
        self.assertEqual(len(ctx.captured_queries), 2)

        parent_request = self.client.get(self._url(), HTTP_HOST=self._host()).wsgi_request
        parent_request.user = self.parent_admin_user
        parent_request.org = self.acme
        self.assertIsNone(get_org_membership(parent_request))

    def test_list_visibility_and_search_filtering(self):
        cases = [
            (self.owner, True, {"Acme Supplies", "Dormant Vendor"}),
            (self.admin, True, {"Acme Supplies", "Dormant Vendor"}),
            (self.staff, False, {"Acme Supplies"}),
            (self.parent_admin_user, False, {"Acme Supplies"}),
            (self.parent_viewer_user, False, {"Acme Supplies"}),
        ]

        for user, can_include_inactive, expected_names in cases:
            self._auth(user)
            response = self.client.get(self._url(), HTTP_HOST=self._host())
            self.assertEqual(response.status_code, 200)
            actual_names = {row["name"] for row in response.data["results"]}

            if can_include_inactive:
                self.assertEqual(actual_names, expected_names)
            else:
                self.assertEqual(actual_names, {"Acme Supplies"})

            search_response = self.client.get(
                f"{self._url()}?search=suppl",
                HTTP_HOST=self._host(),
            )
            self.assertEqual(search_response.status_code, 200)
            self.assertEqual({row["name"] for row in search_response.data["results"]}, {"Acme Supplies"})

            inactive_query = f"{self._url()}?is_active=false"
            inactive_response = self.client.get(inactive_query, HTTP_HOST=self._host())
            self.assertEqual(inactive_response.status_code, 200)
            inactive_names = {row["name"] for row in inactive_response.data["results"]}

            if can_include_inactive:
                self.assertEqual(inactive_names, {"Dormant Vendor"})
            else:
                self.assertEqual(inactive_names, set())

            active_query = f"{self._url()}?is_active=true"
            active_response = self.client.get(active_query, HTTP_HOST=self._host())
            self.assertEqual(active_response.status_code, 200)
            self.assertEqual({row["name"] for row in active_response.data["results"]}, {"Acme Supplies"})

    def test_retrieve_visibility_rules_for_inactive(self):
        visible_users = (self.owner, self.admin)
        hidden_users = (self.staff, self.parent_admin_user, self.parent_viewer_user)

        for user in visible_users:
            self._auth(user)
            response = self.client.get(
                self._url(self.inactive_supplier.id),
                HTTP_HOST=self._host(),
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["name"], "Dormant Vendor")

        for user in hidden_users:
            self._auth(user)
            response = self.client.get(
                self._url(self.inactive_supplier.id),
                HTTP_HOST=self._host(),
            )
            self.assertEqual(response.status_code, 404)

    def test_create_sets_org_and_created_by_server_side(self):
        self._auth(self.owner)
        response = self.client.post(
            self._url(),
            {
                "name": "  New Supplier  ",
                "organization": str(self.globex.id),
                "created_by": 999999,
            },
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 201)

        supplier = Supplier.objects.for_org(self.acme).get(name="New Supplier")
        self.assertEqual(supplier.organization, self.acme)
        self.assertEqual(supplier.created_by, self.owner)

    def test_create_and_update_name_validation(self):
        self._auth(self.owner)

        blank_response = self.client.post(
            self._url(),
            {"name": "   "},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(blank_response.status_code, 400)
        self.assertIn("name", blank_response.data)

        duplicate_response = self.client.post(
            self._url(),
            {"name": "acme supplies"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(duplicate_response.status_code, 400)
        self.assertIn("name", duplicate_response.data)

        unique_other_org_response = self.client.post(
            f"/api/orgs/{self.globex.id}/suppliers/",
            {"name": "Acme Supplies"},
            format="json",
            HTTP_HOST=self._host("globex"),
        )
        self.assertEqual(unique_other_org_response.status_code, 403)

        update_response = self.client.patch(
            self._url(self.active_supplier.id),
            {"name": " dormant vendor "},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(update_response.status_code, 400)
        self.assertIn("name", update_response.data)

    def test_role_matrix_for_create_update_and_deactivate(self):
        create_cases = [
            (self.owner, 201),
            (self.admin, 201),
            (self.staff, 403),
            (self.parent_admin_user, 403),
            (self.parent_viewer_user, 403),
        ]

        for user, expected_status in create_cases:
            self._auth(user)
            response = self.client.post(
                self._url(),
                {"name": f"Supplier {user.username}"},
                format="json",
                HTTP_HOST=self._host(),
            )
            self.assertEqual(response.status_code, expected_status)

        patch_cases = [
            (self.owner, 200),
            (self.admin, 200),
            (self.staff, 403),
            (self.parent_admin_user, 403),
            (self.parent_viewer_user, 403),
        ]

        for user, expected_status in patch_cases:
            supplier = Supplier.objects.for_org(self.acme).create(
                organization=self.acme,
                name=f"Patch {user.username}",
                created_by=self.owner,
            )
            self._auth(user)
            response = self.client.patch(
                self._url(supplier.id),
                {"name": f"Renamed {user.username}"},
                format="json",
                HTTP_HOST=self._host(),
            )
            self.assertEqual(response.status_code, expected_status)

        for user, expected_status in patch_cases:
            supplier = Supplier.objects.for_org(self.acme).create(
                organization=self.acme,
                name=f"Deactivate {user.username}",
                created_by=self.owner,
            )
            self._auth(user)
            response = self.client.patch(
                self._url(supplier.id, "deactivate/"),
                {},
                format="json",
                HTTP_HOST=self._host(),
            )
            self.assertEqual(response.status_code, expected_status)

    def test_deactivate_marks_inactive_without_deleting(self):
        self._auth(self.owner)
        response = self.client.patch(
            self._url(self.active_supplier.id, "deactivate/"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)
        self.active_supplier.refresh_from_db()
        self.assertFalse(self.active_supplier.is_active)
        self.assertTrue(Supplier.all_objects.filter(pk=self.active_supplier.pk).exists())

    def test_reactivation_not_allowed_via_api(self):
        self._auth(self.owner)
        response = self.client.patch(
            self._url(self.inactive_supplier.id),
            {"is_active": True},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("is_active", response.data)

    def test_delete_not_supported_and_cross_org_hidden(self):
        self._auth(self.owner)
        delete_response = self.client.delete(
            self._url(self.active_supplier.id),
            HTTP_HOST=self._host(),
        )
        self.assertEqual(delete_response.status_code, 405)

        hidden_response = self.client.get(
            self._url(self.globex_supplier.id),
            HTTP_HOST=self._host(),
        )
        self.assertEqual(hidden_response.status_code, 404)

    def test_non_member_blocked(self):
        self._auth(self.outsider)
        response = self.client.get(self._url(), HTTP_HOST=self._host())
        self.assertEqual(response.status_code, 403)

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from suppliers.models import Supplier, SupplierContact
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember
from tenancy.permissions import get_org_membership


# ---------------------------------------------------------------------------
# Shared setUp mixin
# ---------------------------------------------------------------------------

class SupplierTestBase(APITestCase):
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

        self.active_supplier = Supplier.objects.create(
            organization=self.acme,
            display_name="Acme Supplies",
            created_by=self.owner,
        )
        self.inactive_supplier = Supplier.objects.create(
            organization=self.acme,
            display_name="Dormant Vendor",
            is_active=False,
            created_by=self.owner,
        )
        self.globex_supplier = Supplier.objects.create(
            organization=self.globex,
            display_name="Globex Supplier",
        )

    def _url(self, supplier_id=None, suffix=""):
        base = f"/api/orgs/{self.acme.id}/suppliers/"
        if supplier_id is None:
            return f"{base}{suffix}"
        return f"{base}{supplier_id}/{suffix}"

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _host(self, slug="acme"):
        return f"{slug}.localhost:8000"


# ---------------------------------------------------------------------------
# Model-level tests
# ---------------------------------------------------------------------------

class SupplierModelTests(TestCase):
    def setUp(self):
        self.acme = Organization.objects.create(name="Acme", slug="acme-model")
        self.globex = Organization.objects.create(name="Globex", slug="globex-model")

    def test_display_name_uniqueness_per_org(self):
        Supplier.objects.create(organization=self.acme, display_name="Alpha")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Supplier.objects.create(organization=self.acme, display_name="Alpha")

    def test_display_name_unique_across_orgs_is_allowed(self):
        Supplier.objects.create(organization=self.acme, display_name="Alpha")
        s = Supplier.objects.create(organization=self.globex, display_name="Alpha")
        self.assertEqual(s.display_name, "Alpha")

    def test_code_uniqueness_per_org(self):
        Supplier.objects.create(organization=self.acme, display_name="A", code="SUP-0001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Supplier.objects.create(organization=self.acme, display_name="B", code="SUP-0001")

    def test_code_unique_across_orgs_is_allowed(self):
        Supplier.objects.create(organization=self.acme, display_name="A", code="SUP-0001")
        s = Supplier.objects.create(organization=self.globex, display_name="A", code="SUP-0001")
        self.assertEqual(s.code, "SUP-0001")

    def test_name_property_returns_display_name(self):
        s = Supplier(display_name="Test Supplier")
        self.assertEqual(s.name, "Test Supplier")

    def test_str_returns_display_name(self):
        s = Supplier(display_name="Test Supplier")
        self.assertEqual(str(s), "Test Supplier")

    def test_ordering_is_by_display_name(self):
        Supplier.objects.create(organization=self.acme, display_name="Zebra Corp")
        Supplier.objects.create(organization=self.acme, display_name="Alpha Ltd")
        names = list(Supplier.objects.filter(organization=self.acme).values_list("display_name", flat=True))
        self.assertEqual(names, sorted(names))

    def test_contact_primary_partial_unique_constraint(self):
        supplier = Supplier.objects.create(organization=self.acme, display_name="Contact Co")
        SupplierContact.objects.create(supplier=supplier, full_name="Alice", is_primary=True, is_active=True)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SupplierContact.objects.create(supplier=supplier, full_name="Bob", is_primary=True, is_active=True)

    def test_contact_deactivated_primary_releases_constraint_slot(self):
        supplier = Supplier.objects.create(organization=self.acme, display_name="Contact Co 2")
        c1 = SupplierContact.objects.create(supplier=supplier, full_name="Alice", is_primary=True, is_active=True)
        c1.is_active = False
        c1.save()
        # Now a new active primary should be allowed.
        c2 = SupplierContact.objects.create(supplier=supplier, full_name="Bob", is_primary=True, is_active=True)
        self.assertTrue(c2.is_primary)

    def test_contact_belongs_to_supplier_implicitly_scoped_to_org(self):
        supplier = Supplier.objects.create(organization=self.acme, display_name="Scoped Co")
        contact = SupplierContact.objects.create(supplier=supplier, full_name="Alice")
        self.assertEqual(contact.supplier.organization, self.acme)


class SupplierCodeBackfillTests(TestCase):
    """
    Verify the backfill logic mirrors what the RunPython migration step does.
    These tests exercise the same algorithm manually.
    """
    def setUp(self):
        self.acme = Organization.objects.create(name="Acme", slug="acme-backfill")

    def _simulate_backfill(self):
        import re
        suppliers = list(
            Supplier.objects.filter(organization=self.acme, code="").select_for_update().order_by("id")
        )
        existing = list(
            Supplier.objects.filter(organization=self.acme).exclude(code="").values_list("code", flat=True)
        )
        max_suffix = 0
        for code in existing:
            match = re.match(r"^SUP-(\d+)$", code)
            if match:
                max_suffix = max(max_suffix, int(match.group(1)))
        counter = max_suffix + 1
        for s in suppliers:
            s.code = f"SUP-{counter:04d}"
            s.save(update_fields=["code"])
            counter += 1

    def test_backfill_generates_sequential_codes(self):
        Supplier.objects.create(organization=self.acme, display_name="A")
        Supplier.objects.create(organization=self.acme, display_name="B")
        with transaction.atomic():
            self._simulate_backfill()
        codes = set(Supplier.objects.filter(organization=self.acme).values_list("code", flat=True))
        self.assertEqual(codes, {"SUP-0001", "SUP-0002"})

    def test_backfill_skips_existing_codes(self):
        Supplier.objects.create(organization=self.acme, display_name="A", code="SUP-0007")
        Supplier.objects.create(organization=self.acme, display_name="B")
        with transaction.atomic():
            self._simulate_backfill()
        codes = set(Supplier.objects.filter(organization=self.acme).values_list("code", flat=True))
        self.assertIn("SUP-0007", codes)
        self.assertIn("SUP-0008", codes)
        self.assertNotIn("SUP-0001", codes)

    def test_backfill_per_org_is_independent(self):
        globex = Organization.objects.create(name="Globex", slug="globex-backfill")
        Supplier.objects.create(organization=self.acme, display_name="A Acme")
        Supplier.objects.create(organization=globex, display_name="A Globex")
        with transaction.atomic():
            self._simulate_backfill()
            # Simulate for globex too
            import re
            for s in Supplier.objects.filter(organization=globex, code="").order_by("id"):
                s.code = "SUP-0001"
                s.save(update_fields=["code"])
        acme_codes = set(Supplier.objects.filter(organization=self.acme).values_list("code", flat=True))
        globex_codes = set(Supplier.objects.filter(organization=globex).values_list("code", flat=True))
        self.assertEqual(acme_codes, {"SUP-0001"})
        self.assertEqual(globex_codes, {"SUP-0001"})


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

class SupplierApiTests(SupplierTestBase):

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

    def test_list_visibility_and_status_filtering(self):
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
            actual_names = {row["display_name"] for row in response.data["results"]}

            if can_include_inactive:
                self.assertEqual(actual_names, expected_names)
            else:
                self.assertEqual(actual_names, {"Acme Supplies"})

            inactive_response = self.client.get(f"{self._url()}?is_active=false", HTTP_HOST=self._host())
            self.assertEqual(inactive_response.status_code, 200)
            inactive_names = {row["display_name"] for row in inactive_response.data["results"]}
            if can_include_inactive:
                self.assertEqual(inactive_names, {"Dormant Vendor"})
            else:
                self.assertEqual(inactive_names, set())

    def test_search_matches_display_name_legal_name_and_code(self):
        Supplier.objects.create(
            organization=self.acme,
            display_name="Widget World",
            legal_name="Widget World Pty Ltd",
            code="SUP-9001",
        )
        self._auth(self.owner)

        # Match by display_name
        r = self.client.get(f"{self._url()}?search=widget", HTTP_HOST=self._host())
        names = {row["display_name"] for row in r.data["results"]}
        self.assertIn("Widget World", names)

        # Match by legal_name
        r = self.client.get(f"{self._url()}?search=Pty", HTTP_HOST=self._host())
        names = {row["display_name"] for row in r.data["results"]}
        self.assertIn("Widget World", names)

        # Match by code
        r = self.client.get(f"{self._url()}?search=9001", HTTP_HOST=self._host())
        names = {row["display_name"] for row in r.data["results"]}
        self.assertIn("Widget World", names)

        # No cross-org leakage
        r = self.client.get(f"{self._url()}?search=globex", HTTP_HOST=self._host())
        self.assertEqual(r.data["results"], [])

    def test_read_response_includes_both_display_name_and_name_alias(self):
        self._auth(self.owner)
        response = self.client.get(self._url(self.active_supplier.id), HTTP_HOST=self._host())
        self.assertEqual(response.status_code, 200)
        self.assertIn("display_name", response.data)
        self.assertIn("name", response.data)
        self.assertEqual(response.data["display_name"], response.data["name"])

    def test_retrieve_visibility_rules_for_inactive(self):
        visible_users = (self.owner, self.admin)
        hidden_users = (self.staff, self.parent_admin_user, self.parent_viewer_user)

        for user in visible_users:
            self._auth(user)
            response = self.client.get(self._url(self.inactive_supplier.id), HTTP_HOST=self._host())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["display_name"], "Dormant Vendor")

        for user in hidden_users:
            self._auth(user)
            response = self.client.get(self._url(self.inactive_supplier.id), HTTP_HOST=self._host())
            self.assertEqual(response.status_code, 404)

    def test_create_using_legacy_name_field(self):
        self._auth(self.owner)
        response = self.client.post(
            self._url(),
            {"name": "Legacy Name Supplier"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Supplier.objects.filter(organization=self.acme, display_name="Legacy Name Supplier").exists())

    def test_create_using_display_name_field(self):
        self._auth(self.owner)
        response = self.client.post(
            self._url(),
            {"display_name": "Display Name Supplier"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Supplier.objects.filter(organization=self.acme, display_name="Display Name Supplier").exists())

    def test_create_conflicting_name_and_display_name_rejected(self):
        self._auth(self.owner)
        response = self.client.post(
            self._url(),
            {"name": "Name A", "display_name": "Name B"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("display_name", response.data)

    def test_create_equal_name_and_display_name_accepted(self):
        self._auth(self.owner)
        response = self.client.post(
            self._url(),
            {"name": "Same Name", "display_name": "Same Name"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 201)

    def test_create_sets_org_and_created_by_server_side(self):
        self._auth(self.owner)
        response = self.client.post(
            self._url(),
            {"display_name": "New Supplier", "organization": str(self.globex.id), "created_by": 999999},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 201)
        supplier = Supplier.objects.get(organization=self.acme, display_name="New Supplier")
        self.assertEqual(supplier.organization, self.acme)
        self.assertEqual(supplier.created_by, self.owner)

    def test_uniqueness_validation_uses_display_name_lookup(self):
        self._auth(self.owner)

        # Exact case duplicate
        r = self.client.post(self._url(), {"display_name": "Acme Supplies"}, format="json", HTTP_HOST=self._host())
        self.assertEqual(r.status_code, 400)
        self.assertIn("display_name", r.data)

        # Case-insensitive duplicate
        r = self.client.post(self._url(), {"name": "acme supplies"}, format="json", HTTP_HOST=self._host())
        self.assertEqual(r.status_code, 400)
        self.assertIn("name", r.data)

    def test_create_name_blank_rejected(self):
        self._auth(self.owner)
        r = self.client.post(self._url(), {"display_name": "   "}, format="json", HTTP_HOST=self._host())
        self.assertEqual(r.status_code, 400)

    def test_update_using_display_name(self):
        self._auth(self.owner)
        r = self.client.patch(
            self._url(self.active_supplier.id),
            {"display_name": "Updated Name"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(r.status_code, 200)
        self.active_supplier.refresh_from_db()
        self.assertEqual(self.active_supplier.display_name, "Updated Name")

    def test_update_duplicate_display_name_rejected(self):
        self._auth(self.owner)
        r = self.client.patch(
            self._url(self.active_supplier.id),
            {"display_name": "dormant vendor"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(r.status_code, 400)

    def test_role_matrix_for_create_update_deactivate(self):
        write_cases = [(self.owner, 201), (self.admin, 201), (self.staff, 403)]
        for user, expected in write_cases:
            self._auth(user)
            r = self.client.post(
                self._url(), {"display_name": f"Supplier {user.username}"}, format="json", HTTP_HOST=self._host()
            )
            self.assertEqual(r.status_code, expected)

        patch_cases = [(self.owner, 200), (self.admin, 200), (self.staff, 403)]
        for user, expected in patch_cases:
            s = Supplier.objects.create(
                organization=self.acme, display_name=f"Patch {user.username}", created_by=self.owner
            )
            self._auth(user)
            r = self.client.patch(
                self._url(s.id), {"display_name": f"Renamed {user.username}"}, format="json", HTTP_HOST=self._host()
            )
            self.assertEqual(r.status_code, expected)

        for user, expected in patch_cases:
            s = Supplier.objects.create(
                organization=self.acme, display_name=f"Deact {user.username}", created_by=self.owner
            )
            self._auth(user)
            r = self.client.patch(self._url(s.id, "deactivate/"), {}, format="json", HTTP_HOST=self._host())
            self.assertEqual(r.status_code, expected)

    def test_deactivate_marks_inactive_without_deleting(self):
        self._auth(self.owner)
        r = self.client.patch(self._url(self.active_supplier.id, "deactivate/"), {}, format="json", HTTP_HOST=self._host())
        self.assertEqual(r.status_code, 200)
        self.active_supplier.refresh_from_db()
        self.assertFalse(self.active_supplier.is_active)
        self.assertTrue(Supplier.all_objects.filter(pk=self.active_supplier.pk).exists())

    def test_reactivate_marks_active(self):
        self._auth(self.owner)
        r = self.client.patch(self._url(self.inactive_supplier.id, "reactivate/"), {}, format="json", HTTP_HOST=self._host())
        self.assertEqual(r.status_code, 200)
        self.inactive_supplier.refresh_from_db()
        self.assertTrue(self.inactive_supplier.is_active)

    def test_is_active_in_write_payload_rejected(self):
        self._auth(self.owner)
        r = self.client.patch(
            self._url(self.inactive_supplier.id),
            {"is_active": True},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("is_active", r.data)

    def test_delete_not_supported_and_cross_org_hidden(self):
        self._auth(self.owner)
        r = self.client.delete(self._url(self.active_supplier.id), HTTP_HOST=self._host())
        self.assertEqual(r.status_code, 405)

        r = self.client.get(self._url(self.globex_supplier.id), HTTP_HOST=self._host())
        self.assertEqual(r.status_code, 404)

    def test_non_member_blocked(self):
        self._auth(self.outsider)
        r = self.client.get(self._url(), HTTP_HOST=self._host())
        self.assertEqual(r.status_code, 403)


# ---------------------------------------------------------------------------
# Contact API tests
# ---------------------------------------------------------------------------

class SupplierContactApiTests(SupplierTestBase):

    def _contact_url(self, supplier_id, contact_id=None, suffix=""):
        base = f"/api/orgs/{self.acme.id}/suppliers/{supplier_id}/contacts/"
        if contact_id is not None:
            return f"/api/orgs/{self.acme.id}/suppliers/{supplier_id}/contacts/{contact_id}/{suffix}"
        return f"{base}{suffix}"

    def test_list_contacts_visible_to_all_roles(self):
        contact = SupplierContact.objects.create(
            supplier=self.active_supplier, full_name="Alice", is_active=True
        )
        for user in (self.owner, self.admin, self.staff):
            self._auth(user)
            r = self.client.get(self._contact_url(self.active_supplier.id), HTTP_HOST=self._host())
            self.assertEqual(r.status_code, 200)
            self.assertEqual(len(r.data), 1)
            self.assertEqual(r.data[0]["full_name"], "Alice")

    def test_staff_cannot_see_inactive_contacts(self):
        SupplierContact.objects.create(
            supplier=self.active_supplier, full_name="Active Contact", is_active=True
        )
        SupplierContact.objects.create(
            supplier=self.active_supplier, full_name="Inactive Contact", is_active=False
        )
        self._auth(self.staff)
        r = self.client.get(self._contact_url(self.active_supplier.id), HTTP_HOST=self._host())
        self.assertEqual(r.status_code, 200)
        names = {c["full_name"] for c in r.data}
        self.assertEqual(names, {"Active Contact"})

    def test_add_contact(self):
        self._auth(self.owner)
        r = self.client.post(
            self._contact_url(self.active_supplier.id, suffix="add"),
            {"full_name": "Bob", "role": "Accounts", "email": "bob@example.com"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["full_name"], "Bob")
        self.assertTrue(SupplierContact.objects.filter(supplier=self.active_supplier, full_name="Bob").exists())

    def test_add_contact_staff_forbidden(self):
        self._auth(self.staff)
        r = self.client.post(
            self._contact_url(self.active_supplier.id, suffix="add"),
            {"full_name": "Charlie"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(r.status_code, 403)

    def test_update_contact(self):
        contact = SupplierContact.objects.create(supplier=self.active_supplier, full_name="Old Name")
        self._auth(self.owner)
        r = self.client.patch(
            self._contact_url(self.active_supplier.id, contact.id),
            {"full_name": "New Name"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(r.status_code, 200)
        contact.refresh_from_db()
        self.assertEqual(contact.full_name, "New Name")

    def test_deactivate_contact(self):
        contact = SupplierContact.objects.create(supplier=self.active_supplier, full_name="Dave", is_active=True)
        self._auth(self.owner)
        r = self.client.patch(
            self._contact_url(self.active_supplier.id, contact.id, suffix="deactivate"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(r.status_code, 200)
        contact.refresh_from_db()
        self.assertFalse(contact.is_active)

    def test_reactivate_contact(self):
        contact = SupplierContact.objects.create(supplier=self.active_supplier, full_name="Eve", is_active=False)
        self._auth(self.owner)
        r = self.client.patch(
            self._contact_url(self.active_supplier.id, contact.id, suffix="reactivate"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(r.status_code, 200)
        contact.refresh_from_db()
        self.assertTrue(contact.is_active)

    def test_set_primary_clears_old_primary_first(self):
        c1 = SupplierContact.objects.create(
            supplier=self.active_supplier, full_name="First", is_primary=True, is_active=True
        )
        c2 = SupplierContact.objects.create(
            supplier=self.active_supplier, full_name="Second", is_primary=False, is_active=True
        )
        self._auth(self.owner)
        r = self.client.patch(
            self._contact_url(self.active_supplier.id, c2.id, suffix="set-primary"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(r.status_code, 200)
        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertFalse(c1.is_primary)
        self.assertTrue(c2.is_primary)
        self.assertTrue(c2.is_active)

    def test_set_primary_on_deactivated_contact_reactivates_it(self):
        c1 = SupplierContact.objects.create(
            supplier=self.active_supplier, full_name="Active Primary", is_primary=True, is_active=True
        )
        c2 = SupplierContact.objects.create(
            supplier=self.active_supplier, full_name="Inactive", is_primary=False, is_active=False
        )
        self._auth(self.owner)
        r = self.client.patch(
            self._contact_url(self.active_supplier.id, c2.id, suffix="set-primary"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(r.status_code, 200)
        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertFalse(c1.is_primary)
        self.assertTrue(c2.is_primary)
        self.assertTrue(c2.is_active)

    def test_contact_not_accessible_across_orgs(self):
        globex_supplier = Supplier.objects.create(organization=self.globex, display_name="Globex Co")
        contact = SupplierContact.objects.create(supplier=globex_supplier, full_name="Cross Org")
        self._auth(self.owner)
        # Acme owner tries to access a contact on a Globex supplier via the acme URL
        r = self.client.get(
            f"/api/orgs/{self.acme.id}/suppliers/{globex_supplier.id}/contacts/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(r.status_code, 404)

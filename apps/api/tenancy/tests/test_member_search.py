from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from branches.models import Branch
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


class MemberSearchTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner_user = User.objects.create_user(
            username="search_owner",
            email="owner@example.com",
            password="Passw0rd!",
            first_name="Owner",
            last_name="User",
        )
        self.admin_user = User.objects.create_user(
            username="search_admin",
            email="admin@example.com",
            password="Passw0rd!",
        )
        self.staff_user = User.objects.create_user(
            username="search_staff",
            email="staff@example.com",
            password="Passw0rd!",
        )
        self.parent_admin_user = User.objects.create_user(
            username="search_parent_admin",
            email="parentadmin@example.com",
            password="Passw0rd!",
        )
        self.parent_viewer_user = User.objects.create_user(
            username="search_parent_viewer",
            email="parentviewer@example.com",
            password="Passw0rd!",
        )
        self.outsider_user = User.objects.create_user(
            username="search_outsider",
            email="outsider@example.com",
            password="Passw0rd!",
        )
        self.available_user = User.objects.create_user(
            username="available_user",
            email="john@example.com",
            password="Passw0rd!",
            first_name="John",
            last_name="",
        )
        self.blank_name_user = User.objects.create_user(
            username="blank_name_user",
            email="blank@example.com",
            password="Passw0rd!",
            first_name="",
            last_name="",
        )
        self.active_same_org_user = User.objects.create_user(
            username="active_same_org",
            email="active.same@example.com",
            password="Passw0rd!",
        )
        self.inactive_same_org_user = User.objects.create_user(
            username="inactive_same_org",
            email="inactive.same@example.com",
            password="Passw0rd!",
        )
        self.other_org_active_user = User.objects.create_user(
            username="other_org_active",
            email="other.org@example.com",
            password="Passw0rd!",
        )
        self.parent_active_user = User.objects.create_user(
            username="parent_active_user",
            email="parent.active@example.com",
            password="Passw0rd!",
        )
        self.parent_inactive_user = User.objects.create_user(
            username="parent_inactive_user",
            email="parent.inactive@example.com",
            password="Passw0rd!",
        )

        self.acme = Organization.objects.create(name="Acme", slug="acme")
        self.globex = Organization.objects.create(name="Globex", slug="globex")

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

        OrganizationMember.objects.create(
            user=self.owner_user,
            organization=self.acme,
            role=OrganizationMember.ROLE_OWNER,
            is_active=True,
        )
        OrganizationMember.objects.create(
            user=self.admin_user,
            organization=self.acme,
            role=OrganizationMember.ROLE_ADMIN,
            is_active=True,
        )
        OrganizationMember.objects.create(
            user=self.staff_user,
            organization=self.acme,
            role=OrganizationMember.ROLE_STAFF,
            is_active=True,
            assigned_branch=self.acme_branch,
        )
        OrganizationMember.objects.create(
            user=self.active_same_org_user,
            organization=self.acme,
            role=OrganizationMember.ROLE_STAFF,
            is_active=True,
            assigned_branch=self.acme_branch,
        )
        OrganizationMember.objects.create(
            user=self.inactive_same_org_user,
            organization=self.acme,
            role=OrganizationMember.ROLE_STAFF,
            is_active=False,
            assigned_branch=self.acme_branch,
        )
        OrganizationMember.objects.create(
            user=self.other_org_active_user,
            organization=self.globex,
            role=OrganizationMember.ROLE_STAFF,
            is_active=True,
            assigned_branch=self.globex_branch,
        )

        ParentCompanyMember.objects.create(
            user=self.parent_admin_user,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
            created_by=self.parent_admin_user,
        )
        ParentCompanyMember.objects.create(
            user=self.parent_viewer_user,
            role=ParentCompanyMember.PARENT_VIEWER,
            is_active=True,
            created_by=self.parent_admin_user,
        )
        ParentCompanyMember.objects.create(
            user=self.parent_active_user,
            role=ParentCompanyMember.PARENT_VIEWER,
            is_active=True,
            created_by=self.parent_admin_user,
        )
        ParentCompanyMember.objects.create(
            user=self.parent_inactive_user,
            role=ParentCompanyMember.PARENT_VIEWER,
            is_active=False,
            created_by=self.parent_admin_user,
        )

    def _url(self, org_id):
        return f"/api/orgs/{org_id}/members/search/"

    def _search(self, user, email=None, **extra_params):
        self.client.force_authenticate(user=user)
        params = {}
        if email is not None:
            params["email"] = email
        params.update(extra_params)
        return self.client.get(self._url(self.acme.id), params)

    def test_access_control(self):
        owner_response = self._search(self.owner_user, "john@example.com")
        self.assertEqual(owner_response.status_code, 200)

        admin_response = self._search(self.admin_user, "john@example.com")
        self.assertEqual(admin_response.status_code, 403)

        staff_response = self._search(self.staff_user, "john@example.com")
        self.assertEqual(staff_response.status_code, 403)

        parent_response = self._search(self.parent_admin_user, "john@example.com")
        self.assertEqual(parent_response.status_code, 403)

        self.client.force_authenticate(user=None)
        unauthenticated = self.client.get(self._url(self.acme.id), {"email": "john@example.com"})
        self.assertEqual(unauthenticated.status_code, 401)

    def test_exact_case_insensitive_match_and_flat_response_shape(self):
        response = self._search(self.owner_user, "John@Example.com")

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)
        self.assertNotIsInstance(response.data, dict)

        row = response.data[0]
        self.assertEqual(set(row.keys()), {"id", "email", "first_name", "last_name"})
        self.assertEqual(row["email"], "john@example.com")
        self.assertEqual(row["first_name"], "John")
        self.assertEqual(row["last_name"], "")

    def test_whitespace_is_stripped_before_lookup(self):
        response = self._search(self.owner_user, "  john@example.com  ")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["email"], "john@example.com")

    def test_no_match_short_input_and_missing_email_return_empty_list(self):
        no_match = self._search(self.owner_user, "nomatch@example.com")
        self.assertEqual(no_match.status_code, 200)
        self.assertEqual(no_match.data, [])

        too_short = self._search(self.owner_user, "ab")
        self.assertEqual(too_short.status_code, 200)
        self.assertEqual(too_short.data, [])

        missing = self._search(self.owner_user)
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(missing.data, [])

    def test_excludes_active_member_in_same_org_including_owner_self(self):
        active_member = self._search(self.owner_user, "active.same@example.com")
        self.assertEqual(active_member.status_code, 200)
        self.assertEqual(active_member.data, [])

        owner_self = self._search(self.owner_user, "owner@example.com")
        self.assertEqual(owner_self.status_code, 200)
        self.assertEqual(owner_self.data, [])

    def test_includes_inactive_same_org_member_and_active_member_in_other_org(self):
        inactive_same_org = self._search(self.owner_user, "inactive.same@example.com")
        self.assertEqual(inactive_same_org.status_code, 200)
        self.assertEqual(len(inactive_same_org.data), 1)
        self.assertEqual(inactive_same_org.data[0]["email"], "inactive.same@example.com")

        other_org_active = self._search(self.owner_user, "other.org@example.com")
        self.assertEqual(other_org_active.status_code, 200)
        self.assertEqual(len(other_org_active.data), 1)
        self.assertEqual(other_org_active.data[0]["email"], "other.org@example.com")

    def test_excludes_parent_members_regardless_of_active_status(self):
        active_parent = self._search(self.owner_user, "parent.active@example.com")
        self.assertEqual(active_parent.status_code, 200)
        self.assertEqual(active_parent.data, [])

        inactive_parent = self._search(self.owner_user, "parent.inactive@example.com")
        self.assertEqual(inactive_parent.status_code, 200)
        self.assertEqual(inactive_parent.data, [])

    def test_blank_name_fields_are_returned_as_blank_strings(self):
        response = self._search(self.owner_user, "blank@example.com", ignored="value")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["first_name"], "")
        self.assertEqual(response.data[0]["last_name"], "")

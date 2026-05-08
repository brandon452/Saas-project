from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from branches.models import Branch
from tenancy.models import Organization, OrganizationMember, ParentCompany, ParentCompanyMember


class NetworkBranchesApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner_user = User.objects.create_user(username="network_owner", password="Passw0rd!")
        self.admin_user = User.objects.create_user(username="network_admin", password="Passw0rd!")
        self.staff_user = User.objects.create_user(username="network_staff", password="Passw0rd!")
        self.parent_admin_user = User.objects.create_user(username="network_parent_admin", password="Passw0rd!")
        self.parent_viewer_user = User.objects.create_user(username="network_parent_viewer", password="Passw0rd!")
        self.other_parent_admin_user = User.objects.create_user(
            username="network_other_parent_admin",
            password="Passw0rd!",
        )
        self.other_org_admin_user = User.objects.create_user(
            username="network_other_org_admin",
            password="Passw0rd!",
        )

        self.parent_a = ParentCompany.objects.create(name="Parent A", slug="parent-a")
        self.parent_b = ParentCompany.objects.create(name="Parent B", slug="parent-b")

        self.beta_org = Organization.objects.create(name="Beta Org", slug="beta-org", parent_company=self.parent_a)
        self.alpha_org = Organization.objects.create(name="Alpha Org", slug="alpha-org", parent_company=self.parent_a)
        self.inactive_org = Organization.objects.create(
            name="Dormant Org",
            slug="dormant-org",
            parent_company=self.parent_a,
            is_active=False,
        )
        self.gamma_org = Organization.objects.create(name="Gamma Org", slug="gamma-org", parent_company=self.parent_b)

        OrganizationMember.objects.create(
            user=self.owner_user,
            organization=self.beta_org,
            role=OrganizationMember.ROLE_OWNER,
            is_active=True,
        )
        OrganizationMember.objects.create(
            user=self.admin_user,
            organization=self.beta_org,
            role=OrganizationMember.ROLE_ADMIN,
            is_active=True,
        )
        self.beta_staff_branch = Branch.objects.for_org(self.beta_org).create(
            organization=self.beta_org,
            name="Receiving",
            code="REC",
        )
        OrganizationMember.objects.create(
            user=self.staff_user,
            organization=self.beta_org,
            role=OrganizationMember.ROLE_STAFF,
            is_active=True,
            assigned_branch=self.beta_staff_branch,
        )
        OrganizationMember.objects.create(
            user=self.other_org_admin_user,
            organization=self.gamma_org,
            role=OrganizationMember.ROLE_ADMIN,
            is_active=True,
        )

        ParentCompanyMember.objects.create(
            user=self.parent_admin_user,
            parent_company=self.parent_a,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
            created_by=self.parent_admin_user,
        )
        ParentCompanyMember.objects.create(
            user=self.parent_viewer_user,
            parent_company=self.parent_a,
            role=ParentCompanyMember.PARENT_VIEWER,
            is_active=True,
            created_by=self.parent_admin_user,
        )
        ParentCompanyMember.objects.create(
            user=self.other_parent_admin_user,
            parent_company=self.parent_b,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
            created_by=self.other_parent_admin_user,
        )

        self.alpha_a = Branch.objects.for_org(self.alpha_org).create(
            organization=self.alpha_org,
            name="A Branch",
            code="A",
        )
        self.alpha_z = Branch.objects.for_org(self.alpha_org).create(
            organization=self.alpha_org,
            name="Z Branch",
            code="Z",
        )
        self.beta_hq = Branch.objects.for_org(self.beta_org).create(
            organization=self.beta_org,
            name="Head Office",
            code="HQ",
        )
        self.beta_receiving = Branch.objects.for_org(self.beta_org).create(
            organization=self.beta_org,
            name="Receiving Dock",
            code="RDC",
        )
        self.inactive_branch = Branch.objects.for_org(self.inactive_org).create(
            organization=self.inactive_org,
            name="Should Not Appear",
            code="SNA",
        )
        self.gamma_branch = Branch.objects.for_org(self.gamma_org).create(
            organization=self.gamma_org,
            name="Gamma Branch",
            code="GAM",
        )

    def _url(self, org_id):
        return f"/api/orgs/{org_id}/network-branches/"

    def test_network_branches_access_for_same_parent_roles(self):
        cases = [
            ("OWNER", self.owner_user),
            ("ADMIN", self.admin_user),
            ("STAFF", self.staff_user),
            ("PARENT_ADMIN", self.parent_admin_user),
            ("PARENT_VIEWER", self.parent_viewer_user),
        ]

        for label, user in cases:
            with self.subTest(role=label):
                self.client.force_authenticate(user=user)
                response = self.client.get(self._url(self.beta_org.id))
                self.assertEqual(response.status_code, 200)

        self.client.force_authenticate(user=None)
        unauthenticated = self.client.get(self._url(self.beta_org.id))
        self.assertEqual(unauthenticated.status_code, 401)

    def test_network_branches_denies_cross_parent_access(self):
        for label, user in [
            ("PARENT_ADMIN_OTHER_PARENT", self.other_parent_admin_user),
            ("ORG_ADMIN_OTHER_PARENT", self.other_org_admin_user),
        ]:
            with self.subTest(role=label):
                self.client.force_authenticate(user=user)
                response = self.client.get(self._url(self.beta_org.id))
                self.assertEqual(response.status_code, 403)

    def test_network_branches_returns_only_same_parent_active_branches(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(self._url(self.beta_org.id))

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual(
            [item["name"] for item in response.data],
            ["A Branch", "Z Branch", "Head Office", "Receiving", "Receiving Dock"],
        )

        ids = {item["id"] for item in response.data}
        self.assertIn(str(self.beta_hq.id), ids)
        self.assertIn(str(self.beta_receiving.id), ids)
        self.assertIn(str(self.beta_staff_branch.id), ids)
        self.assertIn(str(self.alpha_a.id), ids)
        self.assertIn(str(self.alpha_z.id), ids)
        self.assertNotIn(str(self.inactive_branch.id), ids)
        self.assertNotIn(str(self.gamma_branch.id), ids)

        first = response.data[0]
        self.assertEqual(set(first.keys()), {"id", "name", "org_id", "org_name"})
        self.assertEqual(first["org_id"], str(self.alpha_a.organization_id))
        self.assertEqual(first["org_name"], self.alpha_a.organization.name)

        branch_by_id = {item["id"]: item for item in response.data}
        self.assertEqual(branch_by_id[str(self.beta_hq.id)]["org_id"], str(self.beta_org.id))
        self.assertEqual(branch_by_id[str(self.beta_hq.id)]["org_name"], self.beta_org.name)

    def test_network_branches_returns_only_single_org_branches_when_only_one_active_org_exists(self):
        self.alpha_org.is_active = False
        self.alpha_org.save(update_fields=["is_active"])
        self.beta_org.is_active = False
        self.beta_org.save(update_fields=["is_active"])
        self.inactive_org.is_active = False
        self.inactive_org.save(update_fields=["is_active"])

        solo_org = Organization.objects.create(
            name="Solo Org",
            slug="solo-org",
            parent_company=self.parent_a,
        )
        solo_branch_a = Branch.objects.for_org(solo_org).create(
            organization=solo_org,
            name="Main",
            code="MAIN",
        )
        solo_branch_b = Branch.objects.for_org(solo_org).create(
            organization=solo_org,
            name="Overflow",
            code="OVERFLOW",
        )
        OrganizationMember.objects.create(
            user=self.admin_user,
            organization=solo_org,
            role=OrganizationMember.ROLE_ADMIN,
            is_active=True,
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self._url(solo_org.id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.data],
            [str(solo_branch_a.id), str(solo_branch_b.id)],
        )

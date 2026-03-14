from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from branches.models import Branch
from tenancy.models import Organization, OrganizationMember


class BranchApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.acme_user = User.objects.create_user(username="acme_br_user", password="Passw0rd!")
        self.globex_user = User.objects.create_user(username="globex_br_user", password="Passw0rd!")

        self.acme = Organization.objects.create(name="Acme", slug="acme")
        self.globex = Organization.objects.create(name="Globex", slug="globex")

        OrganizationMember.objects.create(user=self.acme_user, organization=self.acme, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.globex_user, organization=self.globex, role="ADMIN", is_active=True)

        self.acme_branch = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Main",
            code="MAIN",
        )
        self.globex_branch = Branch.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Main",
            code="MAIN",
        )

    def _host(self, slug):
        return f"{slug}.localhost:8000"

    def test_branch_isolation(self):
        self.client.force_authenticate(self.acme_user)
        response = self.client.get(f"/api/orgs/{self.acme.id}/branches/", HTTP_HOST=self._host("acme"))
        self.assertEqual(response.status_code, 200)
        branch_ids = {row["id"] for row in response.data["results"]}
        self.assertIn(str(self.acme_branch.id), branch_ids)
        self.assertNotIn(str(self.globex_branch.id), branch_ids)

    def test_put_and_delete_are_405(self):
        self.client.force_authenticate(self.acme_user)
        put_response = self.client.put(
            f"/api/orgs/{self.acme.id}/branches/{self.acme_branch.id}/",
            {"name": "Renamed", "code": "REN"},
            format="json",
            HTTP_HOST=self._host("acme"),
        )
        delete_response = self.client.delete(
            f"/api/orgs/{self.acme.id}/branches/{self.acme_branch.id}/",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(put_response.status_code, 405)
        self.assertEqual(delete_response.status_code, 405)


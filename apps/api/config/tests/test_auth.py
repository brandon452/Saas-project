from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from tenancy.models import Organization, OrganizationMember


class TenantLoginTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.acme_user = User.objects.create_user(username="acme_login", password="Passw0rd!")
        self.globex_user = User.objects.create_user(username="globex_login", password="Passw0rd!")

        self.acme = Organization.objects.create(name="Acme", slug="acme")
        self.globex = Organization.objects.create(name="Globex", slug="globex")

        OrganizationMember.objects.create(user=self.acme_user, organization=self.acme, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.globex_user, organization=self.globex, role="ADMIN", is_active=True)

    def _token_url(self):
        return "/api/token/"

    def test_login_succeeds_for_member_on_matching_tenant(self):
        response = self.client.post(
            self._token_url(),
            {"username": "acme_login", "password": "Passw0rd!"},
            format="json",
            HTTP_HOST="acme.localhost:8000",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_not_tied_to_host_after_url_based_org_resolution(self):
        response = self.client.post(
            self._token_url(),
            {"username": "acme_login", "password": "Passw0rd!"},
            format="json",
            HTTP_HOST="globex.localhost:8000",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

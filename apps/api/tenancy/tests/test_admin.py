from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from tenancy.models import ParentCompanyMember


class AdminSmokeTests(APITestCase):
    def test_parent_company_member_registered_in_admin(self):
        self.assertIn(ParentCompanyMember, admin.site._registry)

    def test_superuser_can_authenticate_for_admin(self):
        User = get_user_model()
        user = User.objects.create_superuser(
            username="admin_smoke",
            email="admin_smoke@example.com",
            password="Passw0rd!",
        )

        self.assertTrue(self.client.login(username="admin_smoke", password="Passw0rd!"))
        self.assertEqual(reverse("admin:index"), "/admin/")

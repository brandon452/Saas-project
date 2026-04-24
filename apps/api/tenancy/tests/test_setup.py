from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from tenancy.models import ParentCompany, ParentCompanyMember


class FirstRunSetupTests(APITestCase):
    def test_status_and_first_run_setup_create_parent_admin(self):
        status_response = self.client.get("/api/setup/status/")
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_response.data["setup_required"])

        setup_response = self.client.post(
            "/api/setup/first-run/",
            {
                "parent_company_name": "Acme Holdings",
                "parent_company_slug": "acme-holdings",
                "first_name": "Ada",
                "last_name": "Admin",
                "email": "ada@example.com",
                "password": "StrongPassw0rd!",
            },
            format="json",
        )
        self.assertEqual(setup_response.status_code, 201)
        self.assertTrue(ParentCompany.objects.filter(slug="acme-holdings").exists())
        self.assertTrue(
            ParentCompanyMember.objects.filter(
                user__email="ada@example.com",
                role=ParentCompanyMember.PARENT_ADMIN,
                parent_company__slug="acme-holdings",
            ).exists()
        )
        self.assertIn("access", setup_response.cookies)

        second_setup = self.client.post(
            "/api/setup/first-run/",
            {
                "parent_company_name": "Second",
                "parent_company_slug": "second",
                "first_name": "Ben",
                "last_name": "Blocked",
                "email": "ben@example.com",
                "password": "StrongPassw0rd!",
            },
            format="json",
        )
        self.assertEqual(second_setup.status_code, 409)

    def test_first_run_validates_password_strength(self):
        response = self.client.post(
            "/api/setup/first-run/",
            {
                "parent_company_name": "Weak Co",
                "parent_company_slug": "weak-co",
                "first_name": "Weak",
                "last_name": "Admin",
                "email": "weak@example.com",
                "password": "password",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)


class OperatorParentCompanyTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(
            username="operator",
            email="operator@example.com",
            password="StrongPassw0rd!",
        )
        self.regular_user = User.objects.create_user(username="regular", password="StrongPassw0rd!")

    def test_superuser_can_create_additional_parent_company(self):
        self.client.force_authenticate(user=self.superuser)

        response = self.client.post(
            "/api/operator/parent-companies/",
            {
                "parent_company_name": "Beta Holdings",
                "parent_company_slug": "beta-holdings",
                "first_name": "Bea",
                "last_name": "Boss",
                "email": "bea@example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["parent_company"]["slug"], "beta-holdings")
        self.assertIn("set_password_url", response.data)
        self.assertTrue(
            ParentCompanyMember.objects.filter(
                user__email="bea@example.com",
                role=ParentCompanyMember.PARENT_ADMIN,
                parent_company__slug="beta-holdings",
            ).exists()
        )

        list_response = self.client.get("/api/operator/parent-companies/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data[0]["slug"], "beta-holdings")

    def test_operator_endpoint_blocks_non_superusers(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get("/api/operator/parent-companies/")
        self.assertEqual(response.status_code, 403)

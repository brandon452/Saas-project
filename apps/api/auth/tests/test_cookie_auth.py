from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.test import override_settings
from django.urls import clear_url_caches
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from auth.authentication import CookieJWTAuthentication
from auth.models import AuthAuditLog, PasswordSetToken
from branches.models import Branch
from inventory.models import MasterItem, OrgItem
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    RATELIMIT_USE_CACHE="default",
)
class CookieAuthTests(APITestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        caches["default"].clear()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="cookie_user",
            password="Passw0rd!",
            email="a@b.com",
            first_name="Cookie",
            last_name="User",
        )
        self.org = Organization.objects.create(name="Acme", slug="acme")
        self.membership = OrganizationMember.objects.create(
            user=self.user,
            organization=self.org,
            role=OrganizationMember.ROLE_ADMIN,
            is_active=True,
        )
        self.branch = Branch.objects.create(organization=self.org, name="Main", code="MAIN")
        self.master_item = MasterItem.objects.create(name="Widget", sku="W-1")
        self.item = OrgItem.objects.create(organization=self.org, master_item=self.master_item, name="")

    def _login(self, username="cookie_user", password="Passw0rd!"):
        return self.client.post(
            "/api/auth/login/",
            {"username": username, "password": password},
            format="json",
        )

    def _csrf_header(self):
        token = self.client.cookies.get("csrftoken")
        return {"HTTP_X_CSRFTOKEN": token.value if token else ""}

    def _create_password_set_token(self):
        User = get_user_model()
        invited_user = User.objects.create_user(
            username="invite_user",
            email="invite@example.com",
            first_name="Invite",
            last_name="User",
            password=None,
        )
        invited_user.set_unusable_password()
        invited_user.save(update_fields=["password"])
        token = PasswordSetToken.objects.create(
            user=invited_user,
            organization=self.org,
            expires_at=timezone.now() + timedelta(days=1),
        )
        return invited_user, token

    def test_login_sets_auth_and_csrf_cookies(self):
        response = self._login()
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.cookies)
        self.assertIn("refresh", response.cookies)
        self.assertIn("csrftoken", self.client.cookies)

    def test_invalid_login_creates_audit_failure(self):
        response = self._login(password="wrong")
        self.assertEqual(response.status_code, 401)
        self.assertFalse("access" in response.cookies)
        self.assertTrue(AuthAuditLog.objects.filter(event=AuthAuditLog.LOGIN_FAILURE, username="cookie_user").exists())

    def test_cookie_auth_invalid_cookie_hard_fails(self):
        self.client.cookies["access"] = "invalid"
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_cookie_auth_header_fallback_works(self):
        token = AccessToken.for_user(self.user)
        response = self.client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {str(token)}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "a@b.com")
        self.assertEqual(response.data["first_name"], "Cookie")
        self.assertEqual(response.data["last_name"], "User")
        self.assertEqual(len(response.data["memberships"]), 1)
        self.assertEqual(response.data["memberships"][0]["org_id"], str(self.org.id))
        self.assertEqual(response.data["memberships"][0]["org_name"], "Acme")
        self.assertEqual(response.data["memberships"][0]["role"], OrganizationMember.ROLE_ADMIN)
        self.assertIsNone(response.data["memberships"][0]["branch_id"])
        self.assertIsNone(response.data["memberships"][0]["branch_name"])

    def test_cookie_auth_no_cookie_no_header_returns_none(self):
        auth = CookieJWTAuthentication()
        request = self.client.get("/api/health/").wsgi_request
        self.assertIsNone(auth.authenticate(request))

    def test_refresh_requires_csrf(self):
        self._login()
        response = self.client.post("/api/auth/refresh/", {})
        self.assertEqual(response.status_code, 403)

    def test_refresh_rotates_and_blacklists_old_token(self):
        self._login()
        old_refresh = self.client.cookies["refresh"].value

        response = self.client.post("/api/auth/refresh/", {}, format="json", **self._csrf_header())
        self.assertEqual(response.status_code, 200)
        self.assertIn("refresh", response.cookies)

        self.client.cookies["refresh"] = old_refresh
        reuse = self.client.post("/api/auth/refresh/", {}, format="json", **self._csrf_header())
        self.assertEqual(reuse.status_code, 401)

    def test_logout_requires_csrf(self):
        self._login()
        response = self.client.post("/api/auth/logout/", {})
        self.assertEqual(response.status_code, 403)

    def test_logout_clears_cookies_and_logs(self):
        self._login()
        response = self.client.post("/api/auth/logout/", {}, format="json", **self._csrf_header())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.cookies["access"].value, "")
        self.assertEqual(response.cookies["refresh"].value, "")
        self.assertTrue(AuthAuditLog.objects.filter(event=AuthAuditLog.LOGOUT).exists())

    def test_me_view_parent_context(self):
        User = get_user_model()
        parent_user = User.objects.create_user(username="parent1", password="Passw0rd!")
        ParentCompanyMember.objects.create(user=parent_user, role=ParentCompanyMember.PARENT_ADMIN, is_active=True)
        token = AccessToken.for_user(parent_user)

        response = self.client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {str(token)}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_parent_member"])
        self.assertEqual(response.data["parent_role"], ParentCompanyMember.PARENT_ADMIN)
        self.assertEqual(response.data["memberships"], [])

    def test_me_view_includes_assigned_branch_for_staff_membership(self):
        self.membership.role = OrganizationMember.ROLE_STAFF
        self.membership.assigned_branch = self.branch
        self.membership.save(update_fields=["role", "assigned_branch"])

        token = AccessToken.for_user(self.user)
        response = self.client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {str(token)}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["memberships"][0]["branch_id"], str(self.branch.id))
        self.assertEqual(response.data["memberships"][0]["branch_name"], self.branch.name)

    def test_movement_post_without_csrf_is_blocked(self):
        self._login()
        response = self.client.post(
            f"/api/orgs/{self.org.id}/inventory/movements/",
            {
                "item": str(self.item.id),
                "quantity": "1.0000",
                "movement_type": "RECEIPT",
                "unit_cost": "5.0000",
            },
            format="json",
            HTTP_X_BRANCH_ID=str(self.branch.id),
        )
        self.assertEqual(response.status_code, 403)

    def test_login_rate_limit_returns_429(self):
        clear_url_caches()
        caches["default"].clear()
        for _ in range(10):
            self._login(password="wrong")
        response = self._login(password="wrong")
        self.assertEqual(response.status_code, 429)

    def test_allowany_refresh_with_expired_access_cookie_still_works(self):
        self._login()
        expired = AccessToken.for_user(self.user)
        expired.set_exp(from_time=timezone.now() - timedelta(minutes=30))
        self.client.cookies["access"] = str(expired)

        response = self.client.post("/api/auth/refresh/", {}, format="json", **self._csrf_header())
        self.assertEqual(response.status_code, 200)

    def test_allowany_logout_with_expired_access_cookie_still_works(self):
        self._login()
        expired = AccessToken.for_user(self.user)
        expired.set_exp(from_time=timezone.now() - timedelta(minutes=30))
        self.client.cookies["access"] = str(expired)

        response = self.client.post("/api/auth/logout/", {}, format="json", **self._csrf_header())
        self.assertEqual(response.status_code, 200)

    def test_set_password_consumes_token_and_rejects_reuse(self):
        invited_user, token = self._create_password_set_token()

        response = self.client.post(
            f"/api/auth/set-password/{token.token}/accept/",
            {"password": "Str0ngPassw0rd!"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        invited_user.refresh_from_db()
        token.refresh_from_db()
        self.assertTrue(invited_user.has_usable_password())
        self.assertIsNotNone(token.used_at)

        reuse = self.client.post(
            f"/api/auth/set-password/{token.token}/accept/",
            {"password": "An0therStrongPass!"},
            format="json",
        )
        self.assertEqual(reuse.status_code, 400)
        self.assertEqual(reuse.data["detail"], "This link has already been used.")

    def test_set_password_accept_locks_token_row_before_consuming(self):
        _, token = self._create_password_set_token()

        with patch(
            "auth.views.PasswordSetToken.objects.select_for_update",
            wraps=PasswordSetToken.objects.select_for_update,
        ) as select_for_update:
            response = self.client.post(
                f"/api/auth/set-password/{token.token}/accept/",
                {"password": "Str0ngPassw0rd!"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        select_for_update.assert_called_once()

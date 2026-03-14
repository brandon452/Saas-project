from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from branches.models import Branch
from inventory.models import Item
from inventory.services import record_stock_movement
from tenancy.models import Organization, OrganizationMember
from tenancy.permissions import RolePolicyPermission, get_member_role


class RolePolicyTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner_user", password="Passw0rd!")
        self.admin = User.objects.create_user(username="admin_user", password="Passw0rd!")
        self.staff = User.objects.create_user(username="staff_user", password="Passw0rd!")
        self.outsider = User.objects.create_user(username="outsider_user", password="Passw0rd!")
        self.new_user = User.objects.create_user(username="new_member", password="Passw0rd!")

        self.acme = Organization.objects.create(name="Acme", slug="acme")
        self.globex = Organization.objects.create(name="Globex", slug="globex")

        self.acme_branch = Branch.objects.for_org(self.acme).create(organization=self.acme, name="Main", code="MAIN")
        self.globex_branch = Branch.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Main",
            code="GLOB-MAIN",
        )

        OrganizationMember.objects.create(user=self.owner, organization=self.acme, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.admin, organization=self.acme, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(
            user=self.staff,
            organization=self.acme,
            role="STAFF",
            is_active=True,
            assigned_branch=self.acme_branch,
        )

        self.globex_owner = User.objects.create_user(username="globex_owner", password="Passw0rd!")
        OrganizationMember.objects.create(user=self.globex_owner, organization=self.globex, role="OWNER", is_active=True)

        self.acme_item = Item.objects.for_org(self.acme).create(organization=self.acme, name="Acme Item", sku="ACME-1")
        self.globex_item = Item.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Item",
            sku="GLOB-1",
        )

        record_stock_movement(
            org=self.acme,
            branch=self.acme_branch,
            item=self.acme_item,
            quantity=Decimal("5.0000"),
            movement_type="RECEIPT",
            performed_by=self.owner,
            idempotency_key="seed-stock-1",
        )

    def _host(self, slug):
        return f"{slug}.localhost:8000"

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_item_role_matrix(self):
        roles = [(self.owner, 201, 200, 204), (self.admin, 201, 200, 204), (self.staff, 403, 403, 403)]
        for user, create_status, patch_status, delete_status in roles:
            item = Item.objects.for_org(self.acme).create(
                organization=self.acme,
                name=f"I-{user.username}",
                sku=f"SKU-{user.username}",
            )
            self._auth(user)
            list_res = self.client.get(f"/api/orgs/{self.acme.id}/inventory/items/", HTTP_HOST=self._host("acme"))
            retrieve_res = self.client.get(f"/api/orgs/{self.acme.id}/inventory/items/{item.id}/", HTTP_HOST=self._host("acme"))
            create_res = self.client.post(
                f"/api/orgs/{self.acme.id}/inventory/items/",
                {"name": "N", "sku": f"N-{user.username}"},
                format="json",
                HTTP_HOST=self._host("acme"),
            )
            patch_res = self.client.patch(
                f"/api/orgs/{self.acme.id}/inventory/items/{item.id}/",
                {"name": "Updated"},
                format="json",
                HTTP_HOST=self._host("acme"),
            )
            delete_res = self.client.delete(f"/api/orgs/{self.acme.id}/inventory/items/{item.id}/", HTTP_HOST=self._host("acme"))

            self.assertEqual(list_res.status_code, 200)
            self.assertEqual(retrieve_res.status_code, 200)
            self.assertEqual(create_res.status_code, create_status)
            self.assertEqual(patch_res.status_code, patch_status)
            self.assertEqual(delete_res.status_code, delete_status)

    def test_branch_role_matrix(self):
        roles = [(self.owner, 201, 200), (self.admin, 201, 200), (self.staff, 403, 403)]
        for user, create_status, patch_status in roles:
            self._auth(user)
            list_res = self.client.get(f"/api/orgs/{self.acme.id}/branches/", HTTP_HOST=self._host("acme"))
            retrieve_res = self.client.get(f"/api/orgs/{self.acme.id}/branches/{self.acme_branch.id}/", HTTP_HOST=self._host("acme"))
            create_res = self.client.post(
                f"/api/orgs/{self.acme.id}/branches/",
                {"name": f"B-{user.username}", "code": f"B-{user.username}"},
                format="json",
                HTTP_HOST=self._host("acme"),
            )
            patch_res = self.client.patch(
                f"/api/orgs/{self.acme.id}/branches/{self.acme_branch.id}/",
                {"name": "Renamed"},
                format="json",
                HTTP_HOST=self._host("acme"),
            )

            self.assertEqual(list_res.status_code, 200)
            self.assertEqual(retrieve_res.status_code, 200)
            self.assertEqual(create_res.status_code, create_status)
            self.assertEqual(patch_res.status_code, patch_status)

    def test_stock_and_movement_role_matrix(self):
        for user in (self.owner, self.admin, self.staff):
            self._auth(user)
            stock_list = self.client.get(f"/api/orgs/{self.acme.id}/inventory/stock/", HTTP_HOST=self._host("acme"))
            stock_retrieve = self.client.get(
                f"/api/orgs/{self.acme.id}/inventory/stock/{stock_list.data['results'][0]['id']}/",
                HTTP_HOST=self._host("acme"),
            )
            movement_list = self.client.get(f"/api/orgs/{self.acme.id}/inventory/movements/", HTTP_HOST=self._host("acme"))
            movement_create = self.client.post(
                f"/api/orgs/{self.acme.id}/inventory/movements/",
                {
                    "item": str(self.acme_item.id),
                    "quantity": "1.0000",
                    "movement_type": "RECEIPT",
                    "idempotency_key": f"mov-{user.username}",
                },
                format="json",
                HTTP_HOST=self._host("acme"),
                HTTP_X_BRANCH_ID=str(self.acme_branch.id),
            )

            self.assertEqual(stock_list.status_code, 200)
            self.assertEqual(stock_retrieve.status_code, 200)
            self.assertEqual(movement_list.status_code, 200)
            self.assertEqual(movement_create.status_code, 201)

    def test_member_role_matrix(self):
        self._auth(self.owner)
        create_res = self.client.post(
            f"/api/orgs/{self.acme.id}/members/",
            {"user_id": self.new_user.id, "role": "STAFF", "assigned_branch": str(self.acme_branch.id)},
            format="json",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(create_res.status_code, 201)
        member_id = OrganizationMember.objects.for_org(self.acme).get(user=self.new_user).id

        owner_list = self.client.get(f"/api/orgs/{self.acme.id}/members/", HTTP_HOST=self._host("acme"))
        owner_get = self.client.get(f"/api/orgs/{self.acme.id}/members/{member_id}/", HTTP_HOST=self._host("acme"))
        owner_patch = self.client.patch(
            f"/api/orgs/{self.acme.id}/members/{member_id}/",
            {"role": "ADMIN", "assigned_branch": None},
            format="json",
            HTTP_HOST=self._host("acme"),
        )
        owner_delete = self.client.delete(f"/api/orgs/{self.acme.id}/members/{member_id}/", HTTP_HOST=self._host("acme"))

        self.assertEqual(owner_list.status_code, 200)
        self.assertEqual(owner_get.status_code, 200)
        self.assertEqual(owner_patch.status_code, 200)
        self.assertEqual(owner_delete.status_code, 204)

        self._auth(self.admin)
        admin_list = self.client.get(f"/api/orgs/{self.acme.id}/members/", HTTP_HOST=self._host("acme"))
        admin_create = self.client.post(
            f"/api/orgs/{self.acme.id}/members/",
            {"user_id": self.new_user.id, "role": "STAFF"},
            format="json",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(admin_list.status_code, 200)
        self.assertEqual(admin_create.status_code, 403)

        self._auth(self.staff)
        staff_list = self.client.get(f"/api/orgs/{self.acme.id}/members/", HTTP_HOST=self._host("acme"))
        self.assertEqual(staff_list.status_code, 403)

    def test_members_list_filtering(self):
        inactive_member = OrganizationMember.objects.create(
            user=self.new_user,
            organization=self.acme,
            role="STAFF",
            is_active=False,
            assigned_branch=self.acme_branch,
        )
        self._auth(self.owner)

        all_res = self.client.get(f"/api/orgs/{self.acme.id}/members/", HTTP_HOST=self._host("acme"))
        active_res = self.client.get(
            f"/api/orgs/{self.acme.id}/members/?is_active=true",
            HTTP_HOST=self._host("acme"),
        )
        inactive_res = self.client.get(
            f"/api/orgs/{self.acme.id}/members/?is_active=false",
            HTTP_HOST=self._host("acme"),
        )

        all_ids = {row["id"] for row in all_res.data["results"]}
        active_ids = {row["id"] for row in active_res.data["results"]}
        inactive_ids = {row["id"] for row in inactive_res.data["results"]}

        self.assertIn(inactive_member.id, all_ids)
        self.assertNotIn(inactive_member.id, active_ids)
        self.assertIn(inactive_member.id, inactive_ids)

    def test_role_sourced_from_member_not_body_or_jwt_claim(self):
        self._auth(self.staff)
        body_spoof = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/items/",
            {"name": "Spoof", "sku": "SPOOF-1", "role": "OWNER"},
            format="json",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(body_spoof.status_code, 403)

        token = AccessToken.for_user(self.staff)
        token["role"] = "OWNER"
        jwt_spoof = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/items/",
            {"name": "Spoof2", "sku": "SPOOF-2"},
            format="json",
            HTTP_HOST=self._host("acme"),
            HTTP_AUTHORIZATION=f"Bearer {str(token)}",
        )
        self.assertEqual(jwt_spoof.status_code, 403)

    def test_403_vs_404_consistency(self):
        self._auth(self.staff)
        same_org_forbidden = self.client.post(
            f"/api/orgs/{self.acme.id}/inventory/items/",
            {"name": "Denied", "sku": "DENIED"},
            format="json",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(same_org_forbidden.status_code, 403)

        cross_org_hidden = self.client.get(
            f"/api/orgs/{self.acme.id}/inventory/items/{self.globex_item.id}/",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(cross_org_hidden.status_code, 404)

    def test_non_member_and_inactive_member_blocked(self):
        self._auth(self.outsider)
        outsider_res = self.client.get(f"/api/orgs/{self.acme.id}/inventory/items/", HTTP_HOST=self._host("acme"))
        self.assertEqual(outsider_res.status_code, 403)

        OrganizationMember.objects.for_org(self.acme).filter(user=self.staff).update(is_active=False)
        self._auth(self.staff)
        inactive_res = self.client.get(f"/api/orgs/{self.acme.id}/inventory/items/", HTTP_HOST=self._host("acme"))
        self.assertEqual(inactive_res.status_code, 403)

    def test_self_and_last_owner_protections(self):
        self._auth(self.owner)
        owner_member = OrganizationMember.objects.for_org(self.acme).get(user=self.owner)
        self_deactivate = self.client.delete(f"/api/orgs/{self.acme.id}/members/{owner_member.id}/", HTTP_HOST=self._host("acme"))
        self.assertEqual(self_deactivate.status_code, 403)

        self_patch_deactivate = self.client.patch(
            f"/api/orgs/{self.acme.id}/members/{owner_member.id}/",
            {"is_active": False},
            format="json",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(self_patch_deactivate.status_code, 403)

        self_demote = self.client.patch(
            f"/api/orgs/{self.acme.id}/members/{owner_member.id}/",
            {"role": "ADMIN"},
            format="json",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(self_demote.status_code, 403)

        second_owner_user = get_user_model().objects.create_user(username="owner_two", password="Passw0rd!")
        second_owner = OrganizationMember.objects.create(
            user=second_owner_user,
            organization=self.acme,
            role="OWNER",
            is_active=True,
        )
        demote_second = self.client.patch(
            f"/api/orgs/{self.acme.id}/members/{second_owner.id}/",
            {"role": "ADMIN"},
            format="json",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(demote_second.status_code, 200)

    def test_duplicate_membership_and_reactivation(self):
        self._auth(self.owner)
        active_dup = self.client.post(
            f"/api/orgs/{self.acme.id}/members/",
            {"user_id": self.admin.id, "role": "STAFF"},
            format="json",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(active_dup.status_code, 400)

        inactive = OrganizationMember.objects.create(
            user=self.new_user,
            organization=self.acme,
            role="STAFF",
            is_active=False,
            assigned_branch=self.acme_branch,
        )
        inactive_dup = self.client.post(
            f"/api/orgs/{self.acme.id}/members/",
            {"user_id": self.new_user.id, "role": "STAFF"},
            format="json",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(inactive_dup.status_code, 400)

        reactivate = self.client.patch(
            f"/api/orgs/{self.acme.id}/members/{inactive.id}/",
            {"is_active": True},
            format="json",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(reactivate.status_code, 200)
        inactive.refresh_from_db()
        self.assertTrue(inactive.is_active)

    def test_unique_constraint_enforced(self):
        with self.assertRaises(IntegrityError):
            OrganizationMember.objects.create(
                user=self.owner,
                organization=self.acme,
                role="OWNER",
                is_active=True,
            )

    def test_user_id_scope_existing_user_only(self):
        self._auth(self.owner)
        response = self.client.post(
            f"/api/orgs/{self.acme.id}/members/",
            {"user_id": 9999999, "role": "STAFF"},
            format="json",
            HTTP_HOST=self._host("acme"),
        )
        self.assertEqual(response.status_code, 400)

    def test_request_scoped_role_cache_and_default_deny(self):
        request = self.client.get(f"/api/orgs/{self.acme.id}/inventory/items/", HTTP_HOST=self._host("acme")).wsgi_request
        request.user = self.owner
        request.org = self.acme

        with CaptureQueriesContext(connection) as ctx:
            first = get_member_role(request)
            second = get_member_role(request)

        self.assertEqual(first, "OWNER")
        self.assertEqual(second, "OWNER")
        self.assertEqual(len(ctx.captured_queries), 1)

        class DummyView:
            permission_resource = "items"
            action = "archive"

        permission = RolePolicyPermission()
        self.assertFalse(permission.has_permission(request, DummyView()))

    def test_member_endpoint_query_efficiency(self):
        User = get_user_model()
        for i in range(15):
            user = User.objects.create_user(username=f"muser_{i}", password="Passw0rd!")
            OrganizationMember.objects.create(
                user=user,
                organization=self.acme,
                role="STAFF",
                is_active=True,
                assigned_branch=self.acme_branch,
            )

        self._auth(self.owner)
        with CaptureQueriesContext(connection) as list_ctx:
            list_res = self.client.get(f"/api/orgs/{self.acme.id}/members/", HTTP_HOST=self._host("acme"))
        self.assertEqual(list_res.status_code, 200)
        self.assertLessEqual(len(list_ctx.captured_queries), 8)

        member_id = list_res.data["results"][0]["id"]
        with CaptureQueriesContext(connection) as retrieve_ctx:
            retrieve_res = self.client.get(f"/api/orgs/{self.acme.id}/members/{member_id}/", HTTP_HOST=self._host("acme"))
        self.assertEqual(retrieve_res.status_code, 200)
        self.assertLessEqual(len(retrieve_ctx.captured_queries), 5)


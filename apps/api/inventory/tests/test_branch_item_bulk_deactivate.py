from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from audit.models import AuditEvent
from branches.models import Branch
from inventory.models import BranchItem, MasterItem, OrgItem
from tenancy.models import Organization, OrganizationMember


class BranchItemBulkDeactivateApiTests(APITestCase):
    def _create_org_item(self, organization, master_name, sku):
        master_item = MasterItem.objects.create(name=master_name, sku=sku)
        return OrgItem.objects.create(
            organization=organization,
            master_item=master_item,
            name="",
            is_active=True,
        )

    def _create_branch_item(self, org_item, branch, *, is_active=True):
        return BranchItem.objects.create(
            org_item=org_item, branch=branch, is_active=is_active
        )

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="bulk_deact_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="bulk_deact_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="bulk_deact_staff", password="Passw0rd!")

        self.acme = Organization.objects.create(name="BulkDeactAcme", slug="bulk-deact-acme")
        self.other_org = Organization.objects.create(name="BulkDeactOther", slug="bulk-deact-other")

        self.branch_a = Branch.objects.for_org(self.acme).create(
            organization=self.acme, name="Branch A", code="BDA"
        )
        self.branch_b = Branch.objects.for_org(self.acme).create(
            organization=self.acme, name="Branch B", code="BDB"
        )
        self.other_branch = Branch.objects.for_org(self.other_org).create(
            organization=self.other_org, name="Other Branch", code="BDO"
        )

        OrganizationMember.objects.create(
            user=self.owner, organization=self.acme, role="OWNER", is_active=True
        )
        OrganizationMember.objects.create(
            user=self.admin, organization=self.acme, role="ADMIN", is_active=True
        )
        OrganizationMember.objects.create(
            user=self.staff,
            organization=self.acme,
            role="STAFF",
            is_active=True,
            assigned_branch=self.branch_a,
        )

        self.item1 = self._create_org_item(self.acme, "Item One", "DEACT-01")
        self.item2 = self._create_org_item(self.acme, "Item Two", "DEACT-02")
        self.item3 = self._create_org_item(self.acme, "Item Three", "DEACT-03")
        self.other_item = self._create_org_item(self.other_org, "Other Item", "DEACT-OTHER")

        self.bi1 = self._create_branch_item(self.item1, self.branch_a)
        self.bi2 = self._create_branch_item(self.item2, self.branch_a)
        self.bi3 = self._create_branch_item(self.item3, self.branch_a)
        self.bi1_branch_b = self._create_branch_item(self.item1, self.branch_b)
        self.other_bi = self._create_branch_item(self.other_item, self.other_branch)

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _url(self):
        return f"/api/orgs/{self.acme.id}/branch-items/bulk-deactivate/"

    def _post(self, payload):
        return self.client.post(self._url(), payload, format="json")

    # ── Access control ────────────────────────────────────────────────────────

    def test_owner_can_access(self):
        self._auth(self.owner)
        response = self._post({"branch": str(self.branch_a.id), "branch_items": [self.bi1.id]})
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access(self):
        self._auth(self.admin)
        response = self._post({"branch": str(self.branch_a.id), "branch_items": [self.bi1.id]})
        self.assertEqual(response.status_code, 200)

    def test_staff_forbidden(self):
        self._auth(self.staff)
        response = self._post({"branch": str(self.branch_a.id), "branch_items": [self.bi1.id]})
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_401(self):
        self.client.force_authenticate(user=None)
        response = self._post({"branch": str(self.branch_a.id), "branch_items": [self.bi1.id]})
        self.assertEqual(response.status_code, 401)

    # ── Validation — strict fail ──────────────────────────────────────────────

    def test_missing_branch_400(self):
        self._auth(self.owner)
        response = self._post({"branch_items": [self.bi1.id]})
        self.assertEqual(response.status_code, 400)

    def test_missing_branch_items_400(self):
        self._auth(self.owner)
        response = self._post({"branch": str(self.branch_a.id)})
        self.assertEqual(response.status_code, 400)

    def test_empty_branch_items_400(self):
        self._auth(self.owner)
        response = self._post({"branch": str(self.branch_a.id), "branch_items": []})
        self.assertEqual(response.status_code, 400)

    def test_branch_items_exceeds_500_400(self):
        self._auth(self.owner)
        response = self._post({"branch": str(self.branch_a.id), "branch_items": list(range(1, 502))})
        self.assertEqual(response.status_code, 400)

    def test_nonexistent_id_strict_fail_400(self):
        self._auth(self.owner)
        response = self._post({"branch": str(self.branch_a.id), "branch_items": [999999]})
        self.assertEqual(response.status_code, 400)

    def test_mixed_valid_and_invalid_ids_strict_fail_400(self):
        """Canonical strict-fail test: one valid ID plus one nonexistent ID → 400 with nonexistent named."""
        self._auth(self.owner)
        response = self._post({
            "branch": str(self.branch_a.id),
            "branch_items": [self.bi1.id, 999999],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("999999", str(response.data))

    def test_branch_item_from_other_org_strict_fail_400(self):
        self._auth(self.owner)
        response = self._post({
            "branch": str(self.branch_a.id),
            "branch_items": [self.other_bi.id],
        })
        self.assertEqual(response.status_code, 400)

    def test_branch_item_from_wrong_branch_strict_fail_400(self):
        """ID from correct org but different branch than submitted → 400."""
        self._auth(self.owner)
        response = self._post({
            "branch": str(self.branch_a.id),
            "branch_items": [self.bi1_branch_b.id],
        })
        self.assertEqual(response.status_code, 400)

    def test_branch_from_other_org_400(self):
        self._auth(self.owner)
        response = self._post({
            "branch": str(self.other_branch.id),
            "branch_items": [self.bi1.id],
        })
        self.assertEqual(response.status_code, 400)

    # ── Content correctness ───────────────────────────────────────────────────

    def test_deactivates_active_branch_items(self):
        self._auth(self.owner)
        response = self._post({
            "branch": str(self.branch_a.id),
            "branch_items": [self.bi1.id, self.bi2.id],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["deactivated"], 2)
        self.assertEqual(response.data["already_inactive"], 0)
        self.assertEqual(response.data["total"], 2)
        self.assertFalse(BranchItem.objects.get(pk=self.bi1.id).is_active)
        self.assertFalse(BranchItem.objects.get(pk=self.bi2.id).is_active)

    def test_already_inactive_items_skipped_not_double_counted(self):
        self.bi2.is_active = False
        self.bi2.save(update_fields=["is_active"])

        self._auth(self.owner)
        response = self._post({
            "branch": str(self.branch_a.id),
            "branch_items": [self.bi1.id, self.bi2.id],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["deactivated"], 1)
        self.assertEqual(response.data["already_inactive"], 1)
        self.assertEqual(response.data["total"], 2)

    def test_all_already_inactive_returns_200(self):
        self.bi1.is_active = False
        self.bi1.save(update_fields=["is_active"])

        self._auth(self.owner)
        response = self._post({
            "branch": str(self.branch_a.id),
            "branch_items": [self.bi1.id],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["deactivated"], 0)
        self.assertEqual(response.data["already_inactive"], 1)
        self.assertEqual(response.data["total"], 1)

    def test_duplicate_ids_deduplicated(self):
        self._auth(self.owner)
        response = self._post({
            "branch": str(self.branch_a.id),
            "branch_items": [self.bi1.id, self.bi1.id, self.bi1.id],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["deactivated"], 1)

    def test_other_branch_items_not_affected(self):
        """Deactivating bi1 at branch_a must not affect bi1_branch_b."""
        self._auth(self.owner)
        self._post({
            "branch": str(self.branch_a.id),
            "branch_items": [self.bi1.id],
        })
        self.assertTrue(BranchItem.objects.get(pk=self.bi1_branch_b.id).is_active)

    # ── Audit logging ─────────────────────────────────────────────────────────

    def test_audit_event_created_on_success(self):
        self._auth(self.owner)
        before = AuditEvent.objects.filter(
            organization=self.acme, event_type="branch_item.bulk_deactivated"
        ).count()
        self._post({"branch": str(self.branch_a.id), "branch_items": [self.bi1.id]})
        after = AuditEvent.objects.filter(
            organization=self.acme, event_type="branch_item.bulk_deactivated"
        ).count()
        self.assertEqual(after, before + 1)

    def test_no_audit_event_on_validation_failure(self):
        self._auth(self.owner)
        before = AuditEvent.objects.filter(
            organization=self.acme, event_type="branch_item.bulk_deactivated"
        ).count()
        self._post({"branch": str(self.branch_a.id), "branch_items": []})
        after = AuditEvent.objects.filter(
            organization=self.acme, event_type="branch_item.bulk_deactivated"
        ).count()
        self.assertEqual(after, before)

    def test_no_audit_event_on_permission_failure(self):
        self._auth(self.staff)
        before = AuditEvent.objects.filter(
            organization=self.acme, event_type="branch_item.bulk_deactivated"
        ).count()
        self._post({"branch": str(self.branch_a.id), "branch_items": [self.bi1.id]})
        after = AuditEvent.objects.filter(
            organization=self.acme, event_type="branch_item.bulk_deactivated"
        ).count()
        self.assertEqual(after, before)

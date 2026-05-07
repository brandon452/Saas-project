from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from audit.models import AuditEvent
from branches.models import Branch
from inventory.models import BranchItem, MasterItem, OrgItem
from tenancy.models import Organization, OrganizationMember


class BranchItemBulkActivateApiTests(APITestCase):
    def _create_org_item(self, organization, master_name, sku, *, is_active=True):
        master_item = MasterItem.objects.create(name=master_name, sku=sku)
        return OrgItem.objects.create(
            organization=organization,
            master_item=master_item,
            name="",
            is_active=is_active,
        )

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="bulk_act_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="bulk_act_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="bulk_act_staff", password="Passw0rd!")

        self.acme = Organization.objects.create(name="BulkActAcme", slug="bulk-act-acme")
        self.other_org = Organization.objects.create(name="BulkActOther", slug="bulk-act-other")

        self.branch_a = Branch.objects.for_org(self.acme).create(
            organization=self.acme, name="Branch A", code="BAA"
        )
        self.branch_b = Branch.objects.for_org(self.acme).create(
            organization=self.acme, name="Branch B", code="BAB"
        )
        self.other_branch = Branch.objects.for_org(self.other_org).create(
            organization=self.other_org, name="Other Branch", code="BAO"
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

        self.item1 = self._create_org_item(self.acme, "Item One", "BULK-01")
        self.item2 = self._create_org_item(self.acme, "Item Two", "BULK-02")
        self.item3 = self._create_org_item(self.acme, "Item Three", "BULK-03")
        self.inactive_item = self._create_org_item(self.acme, "Inactive Item", "BULK-INACT", is_active=False)
        self.other_item = self._create_org_item(self.other_org, "Other Item", "BULK-OTHER")

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _url(self):
        return f"/api/orgs/{self.acme.id}/branch-items/bulk-activate/"

    def _post(self, payload):
        return self.client.post(self._url(), payload, format="json")

    # ── Access control ────────────────────────────────────────────────────────

    def test_owner_can_access(self):
        self._auth(self.owner)
        response = self._post({"branch": str(self.branch_a.id), "org_items": [str(self.item1.id)]})
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access(self):
        self._auth(self.admin)
        response = self._post({"branch": str(self.branch_a.id), "org_items": [str(self.item1.id)]})
        self.assertEqual(response.status_code, 200)

    def test_staff_forbidden(self):
        self._auth(self.staff)
        response = self._post({"branch": str(self.branch_a.id), "org_items": [str(self.item1.id)]})
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_401(self):
        self.client.force_authenticate(user=None)
        response = self._post({"branch": str(self.branch_a.id), "org_items": [str(self.item1.id)]})
        self.assertEqual(response.status_code, 401)

    # ── Validation ────────────────────────────────────────────────────────────

    def test_missing_branch_400(self):
        self._auth(self.owner)
        response = self._post({"org_items": [str(self.item1.id)]})
        self.assertEqual(response.status_code, 400)

    def test_missing_org_items_400(self):
        self._auth(self.owner)
        response = self._post({"branch": str(self.branch_a.id)})
        self.assertEqual(response.status_code, 400)

    def test_empty_org_items_400(self):
        self._auth(self.owner)
        response = self._post({"branch": str(self.branch_a.id), "org_items": []})
        self.assertEqual(response.status_code, 400)

    def test_org_items_exceeds_500_400(self):
        self._auth(self.owner)
        import uuid
        fake_ids = [str(uuid.uuid4()) for _ in range(501)]
        response = self._post({"branch": str(self.branch_a.id), "org_items": fake_ids})
        self.assertEqual(response.status_code, 400)

    def test_branch_from_other_org_400(self):
        self._auth(self.owner)
        response = self._post({"branch": str(self.other_branch.id), "org_items": [str(self.item1.id)]})
        self.assertEqual(response.status_code, 400)

    def test_item_from_other_org_400(self):
        self._auth(self.owner)
        response = self._post({"branch": str(self.branch_a.id), "org_items": [str(self.other_item.id)]})
        self.assertEqual(response.status_code, 400)

    def test_inactive_org_item_400(self):
        self._auth(self.owner)
        response = self._post({"branch": str(self.branch_a.id), "org_items": [str(self.inactive_item.id)]})
        self.assertEqual(response.status_code, 400)

    # ── Content correctness ───────────────────────────────────────────────────

    def test_activates_new_branch_items(self):
        self._auth(self.owner)
        response = self._post({
            "branch": str(self.branch_a.id),
            "org_items": [str(self.item1.id), str(self.item2.id)],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["activated"], 2)
        self.assertEqual(response.data["already_active"], 0)
        self.assertEqual(response.data["total"], 2)
        self.assertTrue(BranchItem.objects.filter(org_item=self.item1, branch=self.branch_a, is_active=True).exists())
        self.assertTrue(BranchItem.objects.filter(org_item=self.item2, branch=self.branch_a, is_active=True).exists())

    def test_all_newly_created_branch_items_are_active(self):
        self._auth(self.owner)
        self._post({
            "branch": str(self.branch_a.id),
            "org_items": [str(self.item1.id), str(self.item2.id), str(self.item3.id)],
        })
        for item in (self.item1, self.item2, self.item3):
            bi = BranchItem.objects.get(org_item=item, branch=self.branch_a)
            self.assertTrue(bi.is_active)

    def test_reactivates_existing_inactive_branch_item(self):
        # Create an inactive BranchItem
        BranchItem.objects.create(org_item=self.item1, branch=self.branch_a, is_active=False)

        self._auth(self.owner)
        response = self._post({
            "branch": str(self.branch_a.id),
            "org_items": [str(self.item1.id)],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["activated"], 1)
        self.assertEqual(response.data["already_active"], 0)
        self.assertEqual(response.data["total"], 1)

        bi = BranchItem.objects.get(org_item=self.item1, branch=self.branch_a)
        self.assertTrue(bi.is_active)
        # Ensure no duplicate was created
        self.assertEqual(BranchItem.objects.filter(org_item=self.item1, branch=self.branch_a).count(), 1)

    def test_skips_already_active_items(self):
        BranchItem.objects.create(org_item=self.item1, branch=self.branch_a, is_active=True)

        self._auth(self.owner)
        response = self._post({
            "branch": str(self.branch_a.id),
            "org_items": [str(self.item1.id)],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["activated"], 0)
        self.assertEqual(response.data["already_active"], 1)
        self.assertEqual(response.data["total"], 1)

    def test_all_already_active_returns_200(self):
        BranchItem.objects.create(org_item=self.item1, branch=self.branch_a, is_active=True)
        BranchItem.objects.create(org_item=self.item2, branch=self.branch_a, is_active=True)

        self._auth(self.owner)
        response = self._post({
            "branch": str(self.branch_a.id),
            "org_items": [str(self.item1.id), str(self.item2.id)],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["activated"], 0)
        self.assertEqual(response.data["already_active"], 2)
        self.assertEqual(response.data["total"], 2)

    def test_activated_equals_created_plus_reactivated(self):
        # item1: new (will be created)
        # item2: inactive (will be reactivated)
        # item3: already active (will be skipped)
        BranchItem.objects.create(org_item=self.item2, branch=self.branch_a, is_active=False)
        BranchItem.objects.create(org_item=self.item3, branch=self.branch_a, is_active=True)

        self._auth(self.owner)
        response = self._post({
            "branch": str(self.branch_a.id),
            "org_items": [str(self.item1.id), str(self.item2.id), str(self.item3.id)],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["activated"], 2)   # 1 created + 1 reactivated
        self.assertEqual(response.data["already_active"], 1)
        self.assertEqual(response.data["total"], 3)

    def test_duplicate_ids_deduplicated_in_total(self):
        self._auth(self.owner)
        response = self._post({
            "branch": str(self.branch_a.id),
            "org_items": [str(self.item1.id), str(self.item1.id), str(self.item1.id)],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["activated"], 1)
        # No duplicate BranchItem records
        self.assertEqual(BranchItem.objects.filter(org_item=self.item1, branch=self.branch_a).count(), 1)

    def test_audit_event_created_on_success(self):
        self._auth(self.owner)
        before = AuditEvent.objects.filter(
            organization=self.acme, event_type="branch_item.bulk_activated"
        ).count()
        self._post({"branch": str(self.branch_a.id), "org_items": [str(self.item1.id)]})
        after = AuditEvent.objects.filter(
            organization=self.acme, event_type="branch_item.bulk_activated"
        ).count()
        self.assertEqual(after, before + 1)

    def test_no_audit_event_on_validation_failure(self):
        self._auth(self.owner)
        before = AuditEvent.objects.filter(
            organization=self.acme, event_type="branch_item.bulk_activated"
        ).count()
        self._post({"branch": str(self.branch_a.id), "org_items": []})
        after = AuditEvent.objects.filter(
            organization=self.acme, event_type="branch_item.bulk_activated"
        ).count()
        self.assertEqual(after, before)

    def test_branch_items_at_other_branch_not_affected(self):
        # item1 is active at branch_b — should not be touched
        BranchItem.objects.create(org_item=self.item1, branch=self.branch_b, is_active=True)

        self._auth(self.owner)
        self._post({
            "branch": str(self.branch_a.id),
            "org_items": [str(self.item1.id)],
        })

        # branch_b item still active and not duplicated
        self.assertEqual(
            BranchItem.objects.filter(org_item=self.item1, branch=self.branch_b).count(), 1
        )
        self.assertTrue(
            BranchItem.objects.get(org_item=self.item1, branch=self.branch_b).is_active
        )

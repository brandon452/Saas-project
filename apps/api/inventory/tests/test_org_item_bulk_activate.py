import uuid

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from audit.models import AuditEvent
from inventory.models import MasterItem, OrgItem
from tenancy.models import Organization, OrganizationMember, ParentCompany, ParentCompanyMember


class OrgItemBulkActivateApiTests(APITestCase):
    def _create_master(self, name, sku, *, is_active=True, parent_company=None):
        kwargs = {"name": name, "sku": sku, "is_active": is_active}
        if parent_company:
            kwargs["parent_company"] = parent_company
        return MasterItem.objects.create(**kwargs)

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="oi_bulk_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="oi_bulk_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="oi_bulk_staff", password="Passw0rd!")
        self.parent_admin_user = User.objects.create_user(username="oi_bulk_padmin", password="Passw0rd!")
        self.parent_viewer_user = User.objects.create_user(username="oi_bulk_pviewer", password="Passw0rd!")

        self.acme = Organization.objects.create(name="BulkOrgAcme", slug="bulk-org-acme")

        OrganizationMember.objects.create(user=self.owner, organization=self.acme, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.admin, organization=self.acme, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.staff, organization=self.acme, role="STAFF", is_active=True)

        ParentCompanyMember.objects.create(
            user=self.parent_admin_user,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
        )
        ParentCompanyMember.objects.create(
            user=self.parent_viewer_user,
            role=ParentCompanyMember.PARENT_VIEWER,
            is_active=True,
        )

        self.master1 = self._create_master("Bulk Item One", "BI-01")
        self.master2 = self._create_master("Bulk Item Two", "BI-02")
        self.master3 = self._create_master("Bulk Item Three", "BI-03")
        self.inactive_master = self._create_master("Bulk Inactive", "BI-INACT", is_active=False)

        # Second parent company with a master item that should not be activatable for acme
        self.other_parent = ParentCompany.objects.create(name="Other Parent Co", slug="other-parent-co")
        self.other_master = self._create_master("Other Item", "BI-OTHER", parent_company=self.other_parent)

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _url(self):
        return f"/api/orgs/{self.acme.id}/inventory/items/bulk-activate/"

    def _post(self, payload):
        return self.client.post(self._url(), payload, format="json")

    # ── Access control ────────────────────────────────────────────────────────

    def test_owner_can_activate(self):
        self._auth(self.owner)
        response = self._post({"master_items": [str(self.master1.id)]})
        self.assertEqual(response.status_code, 200)

    def test_admin_can_activate(self):
        self._auth(self.admin)
        response = self._post({"master_items": [str(self.master1.id)]})
        self.assertEqual(response.status_code, 200)

    def test_staff_forbidden(self):
        self._auth(self.staff)
        response = self._post({"master_items": [str(self.master1.id)]})
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_401(self):
        self.client.force_authenticate(user=None)
        response = self._post({"master_items": [str(self.master1.id)]})
        self.assertEqual(response.status_code, 401)

    def test_parent_admin_can_activate(self):
        self._auth(self.parent_admin_user)
        response = self._post({"master_items": [str(self.master1.id)]})
        self.assertEqual(response.status_code, 200)

    def test_parent_viewer_forbidden(self):
        self._auth(self.parent_viewer_user)
        response = self._post({"master_items": [str(self.master1.id)]})
        self.assertEqual(response.status_code, 403)

    # ── Validation ────────────────────────────────────────────────────────────

    def test_missing_master_items_400(self):
        self._auth(self.owner)
        response = self._post({})
        self.assertEqual(response.status_code, 400)

    def test_empty_master_items_400(self):
        self._auth(self.owner)
        response = self._post({"master_items": []})
        self.assertEqual(response.status_code, 400)

    def test_master_items_exceeds_500_400(self):
        self._auth(self.owner)
        fake_ids = [str(uuid.uuid4()) for _ in range(501)]
        response = self._post({"master_items": fake_ids})
        self.assertEqual(response.status_code, 400)

    def test_inactive_master_item_400(self):
        self._auth(self.owner)
        response = self._post({"master_items": [str(self.inactive_master.id)]})
        self.assertEqual(response.status_code, 400)

    def test_master_item_from_other_parent_company_400(self):
        # other_master belongs to self.other_parent, not acme's parent company
        self._auth(self.owner)
        response = self._post({"master_items": [str(self.other_master.id)]})
        self.assertEqual(response.status_code, 400)

    # ── Content correctness ───────────────────────────────────────────────────

    def test_creates_new_org_items(self):
        self._auth(self.owner)
        response = self._post({"master_items": [str(self.master1.id), str(self.master2.id)]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["activated"], 2)
        self.assertEqual(response.data["already_active"], 0)
        self.assertEqual(response.data["total"], 2)
        self.assertTrue(OrgItem.objects.filter(organization=self.acme, master_item=self.master1, is_active=True).exists())
        self.assertTrue(OrgItem.objects.filter(organization=self.acme, master_item=self.master2, is_active=True).exists())

    def test_newly_created_org_items_have_empty_name(self):
        self._auth(self.owner)
        self._post({"master_items": [str(self.master1.id)]})
        item = OrgItem.objects.get(organization=self.acme, master_item=self.master1)
        self.assertEqual(item.name, "")

    def test_reactivates_inactive_org_item(self):
        OrgItem.all_objects.create(organization=self.acme, master_item=self.master1, name="", is_active=False)
        self._auth(self.owner)
        response = self._post({"master_items": [str(self.master1.id)]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["activated"], 1)
        self.assertEqual(response.data["already_active"], 0)
        self.assertEqual(response.data["total"], 1)
        item = OrgItem.all_objects.get(organization=self.acme, master_item=self.master1)
        self.assertTrue(item.is_active)
        self.assertEqual(OrgItem.all_objects.filter(organization=self.acme, master_item=self.master1).count(), 1)

    def test_skips_already_active_org_items(self):
        OrgItem.objects.create(organization=self.acme, master_item=self.master1, name="", is_active=True)
        self._auth(self.owner)
        response = self._post({"master_items": [str(self.master1.id)]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["activated"], 0)
        self.assertEqual(response.data["already_active"], 1)
        self.assertEqual(response.data["total"], 1)

    def test_activated_equals_created_plus_reactivated(self):
        # master1: new, master2: inactive (reactivate), master3: already active (skip)
        OrgItem.all_objects.create(organization=self.acme, master_item=self.master2, name="", is_active=False)
        OrgItem.objects.create(organization=self.acme, master_item=self.master3, name="", is_active=True)

        self._auth(self.owner)
        response = self._post({
            "master_items": [str(self.master1.id), str(self.master2.id), str(self.master3.id)]
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["activated"], 2)
        self.assertEqual(response.data["already_active"], 1)
        self.assertEqual(response.data["total"], 3)

    def test_duplicate_ids_deduplicated(self):
        self._auth(self.owner)
        response = self._post({
            "master_items": [str(self.master1.id), str(self.master1.id), str(self.master1.id)]
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["activated"], 1)
        self.assertEqual(OrgItem.objects.filter(organization=self.acme, master_item=self.master1).count(), 1)

    def test_audit_event_created_on_success(self):
        self._auth(self.owner)
        before = AuditEvent.objects.filter(
            organization=self.acme, event_type="org_item.bulk_activated"
        ).count()
        self._post({"master_items": [str(self.master1.id)]})
        after = AuditEvent.objects.filter(
            organization=self.acme, event_type="org_item.bulk_activated"
        ).count()
        self.assertEqual(after, before + 1)

    def test_no_audit_event_on_validation_failure(self):
        self._auth(self.owner)
        before = AuditEvent.objects.filter(
            organization=self.acme, event_type="org_item.bulk_activated"
        ).count()
        self._post({"master_items": []})
        after = AuditEvent.objects.filter(
            organization=self.acme, event_type="org_item.bulk_activated"
        ).count()
        self.assertEqual(after, before)

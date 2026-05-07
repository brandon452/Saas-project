import csv
import io
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from audit.models import AuditEvent
from branches.models import Branch
from inventory.models import BranchItem, InventoryClosePeriod, MasterItem, OrgItem, StockTake
from suppliers.models import Supplier
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


class AuditEventsTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="audit_owner",
            password="Passw0rd!",
            first_name="Audit",
            last_name="Owner",
            email="owner@example.com",
        )
        self.admin = User.objects.create_user(username="audit_admin", password="Passw0rd!", email="admin@example.com")
        self.staff = User.objects.create_user(username="audit_staff", password="Passw0rd!", email="staff@example.com")
        self.parent_admin = User.objects.create_user(
            username="audit_parent_admin",
            password="Passw0rd!",
            email="parent@example.com",
        )

        self.org = Organization.objects.create(name="Audit Org", slug="audit-org")
        self.branch_a = Branch.objects.for_org(self.org).create(organization=self.org, name="A", code="A")
        self.branch_b = Branch.objects.for_org(self.org).create(organization=self.org, name="B", code="B")

        OrganizationMember.objects.create(user=self.owner, organization=self.org, role="OWNER")
        self.admin_member = OrganizationMember.objects.create(user=self.admin, organization=self.org, role="ADMIN")
        self.staff_member = OrganizationMember.objects.create(
            user=self.staff,
            organization=self.org,
            role="STAFF",
            assigned_branch=self.branch_a,
        )
        ParentCompanyMember.objects.create(
            user=self.parent_admin,
            parent_company=self.org.parent_company,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _url(self):
        return f"/api/orgs/{self.org.id}/audit-events/"

    def _export_url(self):
        return f"/api/orgs/{self.org.id}/audit-events/export/"

    def test_settings_patch_creates_settings_audit_event(self):
        self._auth(self.owner)
        response = self.client.patch(
            f"/api/orgs/{self.org.id}/settings/",
            {"name": "Audit Org Updated", "default_currency": "SGD"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        event = AuditEvent.objects.filter(organization=self.org, event_type="org.settings.updated").first()
        self.assertIsNotNone(event)
        self.assertIn("name", event.diff_json)
        self.assertEqual(event.diff_json["default_currency"]["after"], "SGD")
        self.assertEqual(event.actor_email_snapshot, "owner@example.com")
        self.assertEqual(event.actor_name_snapshot, "Audit Owner")

    def test_member_updates_create_role_status_and_branch_events(self):
        self._auth(self.owner)
        response = self.client.patch(
            f"/api/orgs/{self.org.id}/members/{self.staff_member.id}/",
            {"role": "ADMIN", "assigned_branch": None, "is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        events = AuditEvent.objects.filter(organization=self.org, resource_id=str(self.staff_member.id))
        event_types = set(events.values_list("event_type", flat=True))
        self.assertIn("member.role.changed", event_types)
        self.assertIn("member.status.changed", event_types)
        self.assertIn("member.branch.changed", event_types)

        branch_event = events.get(event_type="member.branch.changed")
        self.assertEqual(branch_event.diff_json["assigned_branch"]["before"], str(self.branch_a.id))
        self.assertIsNone(branch_event.diff_json["assigned_branch"]["after"])
        self.assertIsNotNone(branch_event.metadata_json["branch_display"]["before"])
        self.assertIsNone(branch_event.metadata_json["branch_display"]["after"])

    def test_audit_list_permissions_and_filters(self):
        AuditEvent.objects.create(
            organization=self.org,
            actor_user=self.owner,
            actor_type="user",
            actor_email_snapshot="owner@example.com",
            actor_name_snapshot="Audit Owner",
            event_type="org.settings.updated",
            resource_type="organization",
            resource_id=str(self.org.id),
            summary="Updated settings",
            diff_json={"name": {"before": "Old", "after": "New"}},
            metadata_json={},
        )
        AuditEvent.objects.create(
            organization=self.org,
            actor_user=self.owner,
            actor_type="user",
            actor_email_snapshot="owner@example.com",
            actor_name_snapshot="Audit Owner",
            event_type="member.status.changed",
            resource_type="organization_member",
            resource_id=str(self.admin_member.id),
            summary="Changed status",
            diff_json={"is_active": {"before": True, "after": False}},
            metadata_json={},
        )

        self._auth(self.owner)
        allowed = self.client.get(self._url())
        self.assertEqual(allowed.status_code, 200)
        self.assertGreaterEqual(allowed.data["count"], 2)

        filtered = self.client.get(self._url(), {"event_type": "member.status.changed"})
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.data["results"][0]["event_type"], "member.status.changed")
        filtered_resource = self.client.get(self._url(), {"resource_id": str(self.admin_member.id)})
        self.assertEqual(filtered_resource.status_code, 200)
        self.assertEqual(filtered_resource.data["results"][0]["resource_id"], str(self.admin_member.id))
        filtered_q = self.client.get(self._url(), {"q": "Changed status"})
        self.assertEqual(filtered_q.status_code, 200)
        self.assertEqual(filtered_q.data["results"][0]["summary"], "Changed status")

        self._auth(self.staff)
        denied = self.client.get(self._url())
        self.assertEqual(denied.status_code, 403)

        self._auth(self.parent_admin)
        parent_allowed = self.client.get(self._url())
        self.assertEqual(parent_allowed.status_code, 200)

    def test_export_csv_returns_expected_columns_and_json_payloads(self):
        self._auth(self.owner)
        AuditEvent.objects.create(
            organization=self.org,
            actor_user=self.owner,
            actor_type="user",
            actor_email_snapshot="owner@example.com",
            actor_name_snapshot="Audit Owner",
            event_type="supplier.created",
            resource_type="supplier",
            resource_id="supplier-1",
            summary="Created supplier",
            diff_json=None,
            metadata_json={"supplier_id": "supplier-1", "display_name": "ACME", "code": "SUP-0001"},
        )
        response = self.client.get(self._export_url())
        self.assertEqual(response.status_code, 200)
        payload = b"".join(response.streaming_content).decode("utf-8")
        rows = list(csv.reader(io.StringIO(payload)))
        self.assertEqual(rows[0][0], "occurred_at")
        self.assertEqual(rows[1][1], "supplier.created")
        self.assertEqual(rows[1][3], "supplier-1")
        self.assertEqual(rows[1][9], "null")
        self.assertEqual(json.loads(rows[1][10])["code"], "SUP-0001")

    def test_supplier_events_creation_update_and_lifecycle(self):
        self._auth(self.owner)
        create_resp = self.client.post(
            f"/api/orgs/{self.org.id}/suppliers/",
            {"display_name": "Vendor One", "email": "v1@example.com"},
            format="json",
        )
        self.assertEqual(create_resp.status_code, 201)
        supplier_id = str(Supplier.objects.get(organization=self.org, display_name="Vendor One").id)

        created_event = AuditEvent.objects.filter(event_type="supplier.created", resource_id=supplier_id).first()
        self.assertIsNotNone(created_event)
        self.assertIsNone(created_event.diff_json)
        self.assertEqual(created_event.metadata_json["supplier_id"], supplier_id)

        update_resp = self.client.patch(
            f"/api/orgs/{self.org.id}/suppliers/{supplier_id}/",
            {"email": "new@example.com"},
            format="json",
        )
        self.assertEqual(update_resp.status_code, 200)
        updated_event = AuditEvent.objects.filter(event_type="supplier.updated", resource_id=supplier_id).latest("occurred_at")
        self.assertIn("email", updated_event.diff_json)
        self.assertNotIn("is_active", updated_event.diff_json)

        deactivate_resp = self.client.patch(f"/api/orgs/{self.org.id}/suppliers/{supplier_id}/deactivate/", format="json")
        self.assertEqual(deactivate_resp.status_code, 200)
        reactivate_resp = self.client.patch(f"/api/orgs/{self.org.id}/suppliers/{supplier_id}/reactivate/", format="json")
        self.assertEqual(reactivate_resp.status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(event_type="supplier.deactivated", resource_id=supplier_id).exists())
        self.assertTrue(AuditEvent.objects.filter(event_type="supplier.reactivated", resource_id=supplier_id).exists())

    def test_stock_take_and_close_period_events(self):
        master = MasterItem.objects.create(parent_company=self.org.parent_company, name="Item 1", sku="SKU-1")
        org_item = OrgItem.objects.create(organization=self.org, master_item=master, is_active=True)
        BranchItem.objects.create(org_item=org_item, branch=self.branch_a, is_active=True)

        self._auth(self.owner)
        create_take = self.client.post(
            f"/api/orgs/{self.org.id}/stock-takes/",
            {"branch": str(self.branch_a.id), "notes": "Cycle count"},
            format="json",
        )
        self.assertEqual(create_take.status_code, 201)
        stock_take_id = create_take.data["id"]
        stock_take = StockTake.objects.get(pk=stock_take_id)

        start_resp = self.client.post(f"/api/orgs/{self.org.id}/stock-takes/{stock_take_id}/start/")
        self.assertEqual(start_resp.status_code, 200)
        line_id = start_resp.data["lines"][0]["id"]
        self.client.patch(
            f"/api/orgs/{self.org.id}/stock-takes/{stock_take_id}/lines/{line_id}/",
            {"counted_quantity": "0"},
            format="json",
        )
        submit_resp = self.client.post(f"/api/orgs/{self.org.id}/stock-takes/{stock_take_id}/submit/")
        self.assertEqual(submit_resp.status_code, 200)
        approve_resp = self.client.post(f"/api/orgs/{self.org.id}/stock-takes/{stock_take_id}/approve/")
        self.assertEqual(approve_resp.status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(event_type="stock_take.started", resource_id=stock_take_id).exists())
        self.assertTrue(AuditEvent.objects.filter(event_type="stock_take.submitted", resource_id=stock_take_id).exists())
        self.assertTrue(AuditEvent.objects.filter(event_type="stock_take.completed", resource_id=stock_take_id).exists())

        end = timezone.now().date() - timedelta(days=1)
        start = end - timedelta(days=1)
        create_period = self.client.post(
            f"/api/orgs/{self.org.id}/close-periods/",
            {"start_date": start.isoformat(), "end_date": end.isoformat(), "notes": "Month-end"},
            format="json",
        )
        self.assertEqual(create_period.status_code, 201)
        period_id = create_period.data["id"]
        close_resp = self.client.post(f"/api/orgs/{self.org.id}/close-periods/{period_id}/close/")
        self.assertEqual(close_resp.status_code, 200)
        reopen_resp = self.client.post(f"/api/orgs/{self.org.id}/close-periods/{period_id}/reopen/")
        self.assertEqual(reopen_resp.status_code, 200)
        closed_event = AuditEvent.objects.filter(event_type="close_period.closed", resource_id=period_id).first()
        self.assertIsNotNone(closed_event)
        self.assertEqual(closed_event.diff_json["status"]["before"], InventoryClosePeriod.OPEN)
        self.assertEqual(closed_event.diff_json["status"]["after"], InventoryClosePeriod.CLOSED)

    @override_settings(USE_EVENT_AUDIT_GOODS_RECEIPTS=True)
    def test_goods_receipt_created_event_has_required_metadata_and_null_diff(self):
        master = MasterItem.objects.create(parent_company=self.org.parent_company, name="Receipt Item", sku="REC-1")
        org_item = OrgItem.objects.create(organization=self.org, master_item=master, is_active=True)
        BranchItem.objects.create(org_item=org_item, branch=self.branch_a, is_active=True)

        self._auth(self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/orgs/{self.org.id}/goods-receipts/",
                {
                    "receipt_type": "DIRECT_RECEIPT",
                    "branch": str(self.branch_a.id),
                    "lines": [{"item": str(org_item.id), "quantity_received": 2, "unit_cost": "5.00"}],
                },
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        receipt_id = response.data["id"]
        event = AuditEvent.objects.filter(event_type="goods_receipt.created", resource_id=receipt_id).first()
        self.assertIsNotNone(event)
        self.assertIsNone(event.diff_json)
        self.assertEqual(event.metadata_json["receipt_id"], receipt_id)
        self.assertEqual(event.metadata_json["line_count"], 1)

    def test_branch_transfer_approval_and_cancel_and_auto_approval_events(self):
        master = MasterItem.objects.create(parent_company=self.org.parent_company, name="Transfer Item", sku="TR-1")
        org_item = OrgItem.objects.create(organization=self.org, master_item=master, is_active=True)
        BranchItem.objects.create(org_item=org_item, branch=self.branch_a, is_active=True)
        BranchItem.objects.create(org_item=org_item, branch=self.branch_b, is_active=True)

        self._auth(self.owner)
        create_response = self.client.post(
            f"/api/orgs/{self.org.id}/branch-transfers/",
            {
                "from_branch": str(self.branch_a.id),
                "to_branch": str(self.branch_b.id),
                "lines": [{"item": str(org_item.id), "quantity_sent": 1}],
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        transfer_id = create_response.data["id"]

        approve_response = self.client.post(f"/api/orgs/{self.org.id}/branch-transfers/{transfer_id}/approve/")
        self.assertEqual(approve_response.status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(event_type="branch_transfer.approved", resource_id=transfer_id).exists())

        cancel_response = self.client.post(f"/api/orgs/{self.org.id}/branch-transfers/{transfer_id}/cancel/")
        self.assertEqual(cancel_response.status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(event_type="branch_transfer.cancelled", resource_id=transfer_id).exists())

        self.org.branch_transfer_approval_required = False
        self.org.save(update_fields=["branch_transfer_approval_required"])
        auto_response = self.client.post(
            f"/api/orgs/{self.org.id}/branch-transfers/",
            {
                "from_branch": str(self.branch_a.id),
                "to_branch": str(self.branch_b.id),
                "lines": [{"item": str(org_item.id), "quantity_sent": 1}],
            },
            format="json",
        )
        self.assertEqual(auto_response.status_code, 201)
        auto_transfer_id = auto_response.data["id"]
        auto_event = AuditEvent.objects.filter(event_type="branch_transfer.approved", resource_id=auto_transfer_id).first()
        self.assertIsNotNone(auto_event)
        self.assertTrue(auto_event.metadata_json["auto_approved"])

    @override_settings(USE_EVENT_AUDIT_QUICK_SALES=True)
    def test_quick_sale_events_created_and_voided(self):
        master = MasterItem.objects.create(parent_company=self.org.parent_company, name="Quick Sale Item", sku="QS-1")
        org_item = OrgItem.objects.create(organization=self.org, master_item=master, is_active=True)
        BranchItem.objects.create(org_item=org_item, branch=self.branch_a, is_active=True)

        from inventory.api import record_stock_movement
        from inventory.models import StockLedger

        record_stock_movement(
            org=self.org,
            branch=self.branch_a,
            item=org_item,
            quantity=Decimal("1.0000"),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal("10.0000"),
            performed_by=self.owner,
            idempotency_key="audit-qs-seed",
        )

        self._auth(self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            create_resp = self.client.post(
                f"/api/orgs/{self.org.id}/quick-sales/",
                {
                    "branch": str(self.branch_a.id),
                    "lines": [{"item": str(org_item.id), "quantity": "1.0000", "unit_price": "12.0000"}],
                },
                format="json",
            )
        self.assertEqual(create_resp.status_code, 201)
        sale_id = create_resp.data["id"]
        self.assertTrue(AuditEvent.objects.filter(event_type="quick_sale.created", resource_id=sale_id).exists())

        with self.captureOnCommitCallbacks(execute=True):
            void_resp = self.client.post(f"/api/orgs/{self.org.id}/quick-sales/{sale_id}/void/", {}, format="json")
        self.assertEqual(void_resp.status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(event_type="quick_sale.voided", resource_id=sale_id).exists())

    def test_retention_cleanup_command_batches(self):
        now = timezone.now()
        keep_event = AuditEvent.objects.create(
            organization=self.org,
            actor_user=self.owner,
            actor_type="user",
            actor_email_snapshot="owner@example.com",
            actor_name_snapshot="Audit Owner",
            event_type="org.settings.updated",
            resource_type="organization",
            resource_id=str(self.org.id),
            summary="Keep",
        )
        AuditEvent.objects.filter(id=keep_event.id).update(occurred_at=now)
        old_events = []
        for idx in range(3):
            event = AuditEvent.objects.create(
                organization=self.org,
                actor_user=self.owner,
                actor_type="user",
                actor_email_snapshot="owner@example.com",
                actor_name_snapshot="Audit Owner",
                event_type="org.settings.updated",
                resource_type="organization",
                resource_id=f"old-{idx}",
                summary=f"Old {idx}",
            )
            AuditEvent.objects.filter(id=event.id).update(occurred_at=now - timedelta(days=800))
            old_events.append(event)

        call_command("cleanup_audit_events", batch_size=2)
        self.assertTrue(AuditEvent.objects.filter(id=keep_event.id).exists())
        self.assertFalse(AuditEvent.objects.filter(id__in=[e.id for e in old_events]).exists())

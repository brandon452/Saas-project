"""
Tests for CSV list export endpoints:
  - Purchase Orders
  - Goods Receipts
  - Branch Transfers
  - Suppliers
  - Stock Valuation
"""
import csv
import io
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from audit.models import AuditEvent
from branches.models import Branch
from goods_receipts.models import GoodsReceipt
from inventory.models import (
    BranchItem,
    InventoryCostState,
    MasterItem,
    OrgItem,
    StockOnHand,
)
from purchase_orders.models import PurchaseOrder
from suppliers.models import Supplier
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember

User = get_user_model()

RATELIMIT_OFF = {"RATELIMIT_ENABLE": False}


def _parse_csv(response):
    content = b"".join(response.streaming_content).decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


# ---------------------------------------------------------------------------
# Shared setUp mixin
# ---------------------------------------------------------------------------

class ExportTestMixin:
    """
    Sets up a two-org environment with owner, admin, staff, outsider,
    and parent_admin users. Subclasses add domain objects as needed.
    """

    def _setup_users_and_orgs(self):
        self.owner = User.objects.create_user(username="exp_owner", password="x", email="owner@exp.test")
        self.admin = User.objects.create_user(username="exp_admin", password="x", email="admin@exp.test")
        self.staff = User.objects.create_user(username="exp_staff", password="x", email="staff@exp.test")
        self.outsider = User.objects.create_user(username="exp_outsider", password="x", email="out@exp.test")
        self.parent_admin = User.objects.create_user(username="exp_parent", password="x", email="parent@exp.test")

        self.org = Organization.objects.create(name="Export Org", slug="export-org")
        self.other_org = Organization.objects.create(name="Other Org", slug="other-org")

        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Main Branch", code="MAIN"
        )

        OrganizationMember.objects.create(user=self.owner, organization=self.org, role="OWNER")
        OrganizationMember.objects.create(user=self.admin, organization=self.org, role="ADMIN")
        OrganizationMember.objects.create(
            user=self.staff, organization=self.org, role="STAFF", assigned_branch=self.branch
        )

        ParentCompanyMember.objects.create(
            user=self.parent_admin,
            parent_company=self.org.parent_company,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)


# ---------------------------------------------------------------------------
# Purchase Order CSV exports
# ---------------------------------------------------------------------------

@override_settings(**RATELIMIT_OFF)
class PurchaseOrderExportTests(ExportTestMixin, APITestCase):
    def setUp(self):
        self._setup_users_and_orgs()
        self.supplier = Supplier.objects.for_org(self.org).create(
            organization=self.org, display_name="Test Supplier", created_by=self.owner
        )
        self.other_supplier = Supplier.objects.for_org(self.other_org).create(
            organization=self.other_org, display_name="Other Supplier"
        )
        self.po1 = PurchaseOrder.objects.for_org(self.org).create(
            organization=self.org,
            po_number="PO-0001",
            supplier=self.supplier,
            branch=self.branch,
            status=PurchaseOrder.SUBMITTED,
            created_by=self.owner,
        )
        self.po2 = PurchaseOrder.objects.for_org(self.org).create(
            organization=self.org,
            po_number="PO-0002",
            supplier=self.supplier,
            branch=self.branch,
            status=PurchaseOrder.DRAFT,
            created_by=self.owner,
        )
        # Belongs to other org — must never appear
        self.other_po = PurchaseOrder.objects.for_org(self.other_org).create(
            organization=self.other_org,
            po_number="PO-9999",
            supplier=self.other_supplier,
            branch=Branch.objects.for_org(self.other_org).create(
                organization=self.other_org, name="Other Branch", code="OTH"
            ),
            status=PurchaseOrder.DRAFT,
        )

    def _url(self):
        return f"/api/orgs/{self.org.id}/purchase-orders/export/csv/"

    def test_owner_can_export(self):
        self._auth(self.owner)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("purchase-orders-", response["Content-Disposition"])

    def test_admin_can_export(self):
        self._auth(self.admin)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_staff_can_export(self):
        self._auth(self.staff)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_denied(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 401)

    def test_outsider_denied(self):
        self._auth(self.outsider)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 403)

    def test_csv_headers(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url()))
        self.assertEqual(list(rows[0].keys()), ["po_number", "status", "supplier", "branch", "created_at", "notes"])

    def test_csv_row_count_matches_org(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url()))
        self.assertEqual(len(rows), 2)

    def test_org_scoping_no_cross_org_leak(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url()))
        po_numbers = [r["po_number"] for r in rows]
        self.assertNotIn("PO-9999", po_numbers)

    def test_status_filter_parity(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url(), {"status": "SUBMITTED"}))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["po_number"], "PO-0001")

    def test_supplier_filter_parity(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url(), {"supplier": str(self.supplier.id)}))
        self.assertEqual(len(rows), 2)

    def test_row_cap_raises_validation_error(self):
        self._auth(self.owner)
        with override_settings(EXPORT_MAX_ROWS=1):
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 400)
        self.assertIn("Too many rows", str(response.data))

    def test_audit_event_created_on_export(self):
        self._auth(self.owner)
        before_count = AuditEvent.objects.filter(
            organization=self.org, event_type="purchase_order.exported"
        ).count()
        self.client.get(self._url())
        after_count = AuditEvent.objects.filter(
            organization=self.org, event_type="purchase_order.exported"
        ).count()
        self.assertEqual(after_count, before_count + 1)

    def test_parent_admin_can_export(self):
        self._auth(self.parent_admin)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    @override_settings(EXPORT_CSV_SERVICE_ENABLED=True, EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={})
    def test_global_enable_uses_service_path(self):
        self._auth(self.owner)
        with patch("purchase_orders.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()

    @override_settings(
        EXPORT_CSV_SERVICE_ENABLED=False,
        EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={"purchase_orders": True},
    )
    def test_explicit_purchase_order_override_uses_service_path(self):
        self._auth(self.owner)
        with patch("purchase_orders.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()

    @override_settings(
        EXPORT_CSV_SERVICE_ENABLED=True,
        EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={"purchase_orders": False},
    )
    def test_explicit_purchase_order_false_override_still_uses_service_path(self):
        self._auth(self.owner)
        with patch("purchase_orders.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()


# ---------------------------------------------------------------------------
# Goods Receipt CSV exports
# ---------------------------------------------------------------------------

@override_settings(**RATELIMIT_OFF)
class GoodsReceiptExportTests(ExportTestMixin, APITestCase):
    def setUp(self):
        self._setup_users_and_orgs()
        self.supplier = Supplier.objects.for_org(self.org).create(
            organization=self.org, display_name="GR Supplier", created_by=self.owner
        )
        self.po = PurchaseOrder.objects.for_org(self.org).create(
            organization=self.org,
            po_number="PO-GR-001",
            supplier=self.supplier,
            branch=self.branch,
            status=PurchaseOrder.SUBMITTED,
            created_by=self.owner,
        )
        self.gr1 = GoodsReceipt.objects.for_org(self.org).create(
            organization=self.org,
            receipt_type=GoodsReceipt.PO_RECEIPT,
            purchase_order=self.po,
            branch=self.branch,
            received_by=self.owner,
        )
        self.gr2 = GoodsReceipt.objects.for_org(self.org).create(
            organization=self.org,
            receipt_type=GoodsReceipt.DIRECT_RECEIPT,
            branch=self.branch,
            supplier=self.supplier,
            received_by=self.owner,
        )

    def _url(self):
        return f"/api/orgs/{self.org.id}/goods-receipts/export/csv/"

    def test_owner_can_export(self):
        self._auth(self.owner)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")

    def test_unauthenticated_denied(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 401)

    def test_outsider_denied(self):
        self._auth(self.outsider)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 403)

    def test_csv_headers(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url()))
        self.assertEqual(list(rows[0].keys()), ["id", "receipt_type", "branch", "supplier", "po_number", "received_at", "notes"])

    def test_csv_row_count(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url()))
        self.assertEqual(len(rows), 2)

    def test_receipt_type_filter_parity(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url(), {"receipt_type": "DIRECT_RECEIPT"}))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["receipt_type"], "DIRECT_RECEIPT")

    def test_date_range_validation_parity(self):
        """date_after > date_before must return 400, same as list endpoint."""
        self._auth(self.owner)
        response = self.client.get(self._url(), {"date_after": "2025-06-01", "date_before": "2025-01-01"})
        self.assertEqual(response.status_code, 400)

    def test_row_cap_raises_validation_error(self):
        self._auth(self.owner)
        with override_settings(EXPORT_MAX_ROWS=1):
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 400)

    def test_audit_event_created_on_export(self):
        self._auth(self.owner)
        self.client.get(self._url())
        self.assertTrue(
            AuditEvent.objects.filter(organization=self.org, event_type="goods_receipt.exported").exists()
        )

    @override_settings(EXPORT_CSV_SERVICE_ENABLED=True, EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={})
    def test_global_enable_uses_service_path(self):
        self._auth(self.owner)
        with patch("goods_receipts.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()

    @override_settings(
        EXPORT_CSV_SERVICE_ENABLED=False,
        EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={"goods_receipts": True},
    )
    def test_explicit_goods_receipts_override_uses_service_path(self):
        self._auth(self.owner)
        with patch("goods_receipts.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()

    @override_settings(
        EXPORT_CSV_SERVICE_ENABLED=True,
        EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={"goods_receipts": False},
    )
    def test_explicit_goods_receipts_false_override_still_uses_service_path(self):
        self._auth(self.owner)
        with patch("goods_receipts.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()


# ---------------------------------------------------------------------------
# Branch Transfer CSV exports
# ---------------------------------------------------------------------------

@override_settings(**RATELIMIT_OFF)
class BranchTransferExportTests(ExportTestMixin, APITestCase):
    def setUp(self):
        self._setup_users_and_orgs()
        self.other_branch = Branch.objects.for_org(self.other_org).create(
            organization=self.other_org, name="Other Branch", code="OTH"
        )
        OrganizationMember.objects.create(user=self.owner, organization=self.other_org, role="OWNER")

        from branch_transfers.models import BranchTransfer
        self.transfer1 = BranchTransfer.objects.create(
            organization=self.org,
            to_organization=self.other_org,
            from_branch=self.branch,
            to_branch=self.other_branch,
            status=BranchTransfer.DRAFT,
            created_by=self.owner,
        )
        self.transfer2 = BranchTransfer.objects.create(
            organization=self.org,
            to_organization=self.other_org,
            from_branch=self.branch,
            to_branch=self.other_branch,
            status=BranchTransfer.APPROVED,
            created_by=self.owner,
        )

    def _url(self):
        return f"/api/orgs/{self.org.id}/branch-transfers/export/csv/"

    def test_owner_can_export(self):
        self._auth(self.owner)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_denied(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 401)

    def test_outsider_denied(self):
        self._auth(self.outsider)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 403)

    def test_csv_headers(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url()))
        self.assertEqual(
            list(rows[0].keys()),
            ["id", "status", "from_branch", "to_branch", "from_org", "to_org", "created_at", "notes"],
        )

    def test_csv_row_count(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url()))
        self.assertEqual(len(rows), 2)

    def test_status_filter_parity(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url(), {"status": "APPROVED"}))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "APPROVED")

    def test_receiver_org_visibility(self):
        """Receiving org can also see the transfer in its export."""
        receiver = User.objects.create_user(username="recv_user", password="x")
        OrganizationMember.objects.create(user=receiver, organization=self.other_org, role="OWNER")
        self._auth(receiver)
        rows = _parse_csv(self.client.get(f"/api/orgs/{self.other_org.id}/branch-transfers/export/csv/"))
        transfer_ids = [r["id"] for r in rows]
        self.assertIn(str(self.transfer1.id), transfer_ids)

    def test_row_cap_raises_validation_error(self):
        self._auth(self.owner)
        with override_settings(EXPORT_MAX_ROWS=1):
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 400)

    def test_audit_event_created_on_export(self):
        self._auth(self.owner)
        self.client.get(self._url())
        self.assertTrue(
            AuditEvent.objects.filter(organization=self.org, event_type="branch_transfer.exported").exists()
        )

    @override_settings(EXPORT_CSV_SERVICE_ENABLED=True, EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={})
    def test_global_enable_uses_service_path(self):
        self._auth(self.owner)
        with patch("branch_transfers.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()

    @override_settings(
        EXPORT_CSV_SERVICE_ENABLED=False,
        EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={"branch_transfers": True},
    )
    def test_explicit_branch_transfers_override_uses_service_path(self):
        self._auth(self.owner)
        with patch("branch_transfers.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()

    @override_settings(
        EXPORT_CSV_SERVICE_ENABLED=True,
        EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={"branch_transfers": False},
    )
    def test_explicit_branch_transfers_false_override_still_uses_service_path(self):
        self._auth(self.owner)
        with patch("branch_transfers.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()


# ---------------------------------------------------------------------------
# Supplier CSV exports
# ---------------------------------------------------------------------------

@override_settings(**RATELIMIT_OFF)
class SupplierExportTests(ExportTestMixin, APITestCase):
    def setUp(self):
        self._setup_users_and_orgs()
        self.s1 = Supplier.objects.for_org(self.org).create(
            organization=self.org, display_name="Alpha Supplier", is_active=True, created_by=self.owner
        )
        self.s2 = Supplier.objects.for_org(self.org).create(
            organization=self.org, display_name="Beta Supplier", is_active=False, created_by=self.owner
        )
        self.s_other = Supplier.objects.for_org(self.other_org).create(
            organization=self.other_org, display_name="Other Org Supplier"
        )

    def _url(self):
        return f"/api/orgs/{self.org.id}/suppliers/export/csv/"

    def test_owner_exports_all_including_inactive(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url()))
        names = [r["display_name"] for r in rows]
        self.assertIn("Alpha Supplier", names)
        self.assertIn("Beta Supplier", names)
        self.assertNotIn("Other Org Supplier", names)

    def test_staff_sees_only_active(self):
        self._auth(self.staff)
        rows = _parse_csv(self.client.get(self._url()))
        names = [r["display_name"] for r in rows]
        self.assertIn("Alpha Supplier", names)
        self.assertNotIn("Beta Supplier", names)

    def test_is_active_false_filter_owner(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url(), {"is_active": "false"}))
        names = [r["display_name"] for r in rows]
        self.assertEqual(names, ["Beta Supplier"])

    def test_search_filter_parity(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url(), {"search": "Alpha"}))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["display_name"], "Alpha Supplier")

    def test_unauthenticated_denied(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 401)

    def test_outsider_denied(self):
        self._auth(self.outsider)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 403)

    def test_csv_headers(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url()))
        expected = ["code", "display_name", "legal_name", "email", "phone",
                    "payment_terms_days", "default_lead_time_days", "currency", "country", "is_active"]
        self.assertEqual(list(rows[0].keys()), expected)

    def test_row_cap_raises_validation_error(self):
        self._auth(self.owner)
        with override_settings(EXPORT_MAX_ROWS=1):
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 400)

    def test_audit_event_created_on_export(self):
        self._auth(self.owner)
        self.client.get(self._url())
        self.assertTrue(
            AuditEvent.objects.filter(organization=self.org, event_type="supplier.exported").exists()
        )

    @override_settings(EXPORT_CSV_SERVICE_ENABLED=True, EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={})
    def test_global_enable_uses_service_path(self):
        self._auth(self.owner)
        with patch("suppliers.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()

    @override_settings(
        EXPORT_CSV_SERVICE_ENABLED=False,
        EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={"suppliers": True},
    )
    def test_explicit_suppliers_override_uses_service_path(self):
        self._auth(self.owner)
        with patch("suppliers.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()

    @override_settings(
        EXPORT_CSV_SERVICE_ENABLED=True,
        EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={"suppliers": False},
    )
    def test_explicit_suppliers_false_override_still_uses_service_path(self):
        self._auth(self.owner)
        with patch("suppliers.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()


# ---------------------------------------------------------------------------
# Stock Valuation CSV exports
# ---------------------------------------------------------------------------

@override_settings(**RATELIMIT_OFF)
class StockValuationExportTests(ExportTestMixin, APITestCase):
    def setUp(self):
        self._setup_users_and_orgs()
        master = MasterItem.objects.create(name="Widget", sku="WGT-001")
        self.item = OrgItem.objects.for_org(self.org).create(
            organization=self.org, master_item=master, name="Widget"
        )
        self.bi = BranchItem.objects.create(branch=self.branch, org_item=self.item, is_active=True)
        self.soh = StockOnHand.objects.create(
            organization=self.org, branch=self.branch, item=self.item, quantity=10
        )
        InventoryCostState.objects.create(
            organization=self.org,
            branch=self.branch,
            item=self.item,
            latest_unit_cost=Decimal("5.00"),
            average_unit_cost=Decimal("4.50"),
        )

    def _url(self):
        return f"/api/orgs/{self.org.id}/reports/stock-valuation/export/csv/"

    def test_owner_can_export(self):
        self._auth(self.owner)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("stock-valuation-", response["Content-Disposition"])

    def test_admin_can_export(self):
        self._auth(self.admin)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_staff_denied(self):
        """Valuation export uses IsOrgOwnerOrAdmin — staff should be denied."""
        self._auth(self.staff)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_denied(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 401)

    def test_outsider_denied(self):
        self._auth(self.outsider)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 403)

    def test_csv_headers(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url()))
        expected = [
            "item_name", "item_sku", "branch_name",
            "quantity_on_hand", "latest_unit_cost", "latest_valuation",
            "average_unit_cost", "average_valuation",
        ]
        self.assertEqual(list(rows[0].keys()), expected)

    def test_csv_row_values(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url()))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["item_name"], "Widget")
        self.assertEqual(rows[0]["quantity_on_hand"], "10")
        # Decimal normalization strips trailing zeros: 5.00 → 5, 50.00 → 50
        self.assertEqual(rows[0]["latest_unit_cost"], "5")
        self.assertEqual(rows[0]["latest_valuation"], "50")

    def test_full_filtered_dataset_not_page_slice(self):
        """Export must return ALL matching rows regardless of pagination."""
        for i in range(3):
            master = MasterItem.objects.create(name=f"Item {i}", sku=f"SKU-{i:03d}")
            item = OrgItem.objects.for_org(self.org).create(
                organization=self.org, master_item=master, name=f"Item {i}"
            )
            StockOnHand.objects.create(
                organization=self.org, branch=self.branch, item=item, quantity=5
            )
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url()))
        # Should have all 4 rows (1 original + 3 new), not just a page of 1
        self.assertEqual(len(rows), 4)

    def test_search_filter_parity(self):
        self._auth(self.owner)
        rows = _parse_csv(self.client.get(self._url(), {"search": "Widget"}))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["item_name"], "Widget")

    def test_row_cap_raises_validation_error(self):
        self._auth(self.owner)
        with override_settings(EXPORT_MAX_ROWS=0):
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 400)
        self.assertIn("Too many rows", str(response.data))

    def test_snapshot_mode_invalid_period(self):
        self._auth(self.owner)
        response = self.client.get(self._url(), {"period_id": "00000000-0000-0000-0000-000000000000"})
        self.assertEqual(response.status_code, 400)

    def test_audit_event_created_on_export(self):
        self._auth(self.owner)
        self.client.get(self._url())
        self.assertTrue(
            AuditEvent.objects.filter(organization=self.org, event_type="stock_valuation.exported").exists()
        )

    def test_parent_admin_can_export(self):
        self._auth(self.parent_admin)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    @override_settings(EXPORT_CSV_SERVICE_ENABLED=True, EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={})
    def test_global_enable_uses_service_path(self):
        self._auth(self.owner)
        with patch("reports.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()

    @override_settings(
        EXPORT_CSV_SERVICE_ENABLED=False,
        EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={"stock_valuation": True},
    )
    def test_explicit_stock_valuation_override_uses_service_path(self):
        self._auth(self.owner)
        with patch("reports.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()

    @override_settings(
        EXPORT_CSV_SERVICE_ENABLED=True,
        EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={"stock_valuation": False},
    )
    def test_explicit_stock_valuation_false_override_still_uses_service_path(self):
        self._auth(self.owner)
        with patch("reports.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()


# ---------------------------------------------------------------------------
# Inventory Aging CSV exports
# ---------------------------------------------------------------------------

@override_settings(**RATELIMIT_OFF)
class InventoryAgingExportTests(ExportTestMixin, APITestCase):
    def setUp(self):
        self._setup_users_and_orgs()
        master = MasterItem.objects.create(name="Aging Widget", sku="AGE-001")
        self.item = OrgItem.objects.for_org(self.org).create(
            organization=self.org, master_item=master, name="Aging Widget"
        )
        BranchItem.objects.create(branch=self.branch, org_item=self.item, is_active=True)
        StockOnHand.objects.create(
            organization=self.org, branch=self.branch, item=self.item, quantity=10
        )
        InventoryCostState.objects.create(
            organization=self.org,
            branch=self.branch,
            item=self.item,
            latest_unit_cost=Decimal("5.00"),
            average_unit_cost=Decimal("4.50"),
            last_receipt_at=timezone.now() - timedelta(days=30),
        )

    def _url(self):
        return f"/api/orgs/{self.org.id}/reports/inventory-aging/export/csv/"

    def test_owner_can_export(self):
        self._auth(self.owner)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("inventory-aging-", response["Content-Disposition"])

    @override_settings(EXPORT_CSV_SERVICE_ENABLED=True, EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={})
    def test_global_enable_uses_service_path(self):
        self._auth(self.owner)
        with patch("reports.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()

    @override_settings(
        EXPORT_CSV_SERVICE_ENABLED=False,
        EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={"inventory_aging": True},
    )
    def test_explicit_inventory_aging_override_uses_service_path(self):
        self._auth(self.owner)
        with patch("reports.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()

    @override_settings(
        EXPORT_CSV_SERVICE_ENABLED=True,
        EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={"inventory_aging": False},
    )
    def test_explicit_inventory_aging_false_override_still_uses_service_path(self):
        self._auth(self.owner)
        with patch("reports.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()


# ---------------------------------------------------------------------------
# Slow / Dead Stock CSV exports
# ---------------------------------------------------------------------------

@override_settings(**RATELIMIT_OFF)
class SlowDeadStockExportTests(ExportTestMixin, APITestCase):
    def setUp(self):
        self._setup_users_and_orgs()
        master = MasterItem.objects.create(name="Slow Widget", sku="SLOW-001")
        self.item = OrgItem.objects.for_org(self.org).create(
            organization=self.org, master_item=master, name="Slow Widget"
        )
        BranchItem.objects.create(branch=self.branch, org_item=self.item, is_active=True)
        StockOnHand.objects.create(
            organization=self.org, branch=self.branch, item=self.item, quantity=10
        )
        InventoryCostState.objects.create(
            organization=self.org,
            branch=self.branch,
            item=self.item,
            latest_unit_cost=Decimal("5.00"),
            last_receipt_at=timezone.now() - timedelta(days=120),
        )

    def _url(self):
        return f"/api/orgs/{self.org.id}/reports/slow-dead-stock/export/csv/"

    def test_owner_can_export(self):
        self._auth(self.owner)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("slow-dead-stock-", response["Content-Disposition"])

    @override_settings(EXPORT_CSV_SERVICE_ENABLED=True, EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={})
    def test_global_enable_uses_service_path(self):
        self._auth(self.owner)
        with patch("reports.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()

    @override_settings(
        EXPORT_CSV_SERVICE_ENABLED=False,
        EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={"slow_dead_stock": True},
    )
    def test_explicit_slow_dead_stock_override_uses_service_path(self):
        self._auth(self.owner)
        with patch("reports.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()

    @override_settings(
        EXPORT_CSV_SERVICE_ENABLED=True,
        EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES={"slow_dead_stock": False},
    )
    def test_explicit_slow_dead_stock_false_override_still_uses_service_path(self):
        self._auth(self.owner)
        with patch("reports.views.ExportService.export_stream") as export_stream:
            export_stream.return_value = HttpResponse("ok", content_type="text/csv")
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        export_stream.assert_called_once()


# ---------------------------------------------------------------------------
# Rate limit tests
# ---------------------------------------------------------------------------

@override_settings(RATELIMIT_USE_CACHE="default", EXPORT_CSV_RATE_LIMIT="1/m")
class RateLimitExportTests(ExportTestMixin, APITestCase):
    def setUp(self):
        self._setup_users_and_orgs()
        Supplier.objects.for_org(self.org).create(
            organization=self.org, display_name="RL Supplier", created_by=self.owner
        )

    def _url(self):
        return f"/api/orgs/{self.org.id}/suppliers/export/csv/"

    def test_rate_limit_triggers_429(self):
        self._auth(self.owner)
        # First request should succeed
        r1 = self.client.get(self._url())
        self.assertEqual(r1.status_code, 200)
        # Second request within the same minute should be rate-limited
        r2 = self.client.get(self._url())
        self.assertEqual(r2.status_code, 429)


# ---------------------------------------------------------------------------
# Streaming helper unit tests
# ---------------------------------------------------------------------------

class StreamingHelpersTests(TestCase):
    def test_echo_buffer_returns_value(self):
        from exports.streaming import _Echo
        echo = _Echo()
        self.assertEqual(echo.write("hello"), "hello")

    def test_stream_csv_content_type(self):
        from exports.streaming import stream_csv
        headers = ["a", "b"]
        rows = [["1", "2"], ["3", "4"]]
        response = stream_csv(headers, iter(rows), "test.csv")
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("test.csv", response["Content-Disposition"])
        content = b"".join(response.streaming_content).decode()
        reader = csv.reader(io.StringIO(content))
        parsed = list(reader)
        self.assertEqual(parsed[0], ["a", "b"])
        self.assertEqual(parsed[1], ["1", "2"])

    def test_enforce_row_cap_passes_under_limit(self):
        from exports.streaming import enforce_row_cap
        from unittest.mock import MagicMock
        qs = MagicMock()
        qs.count.return_value = 5
        with override_settings(EXPORT_MAX_ROWS=10):
            count = enforce_row_cap(qs)
        self.assertEqual(count, 5)

    def test_enforce_row_cap_raises_over_limit(self):
        from exports.streaming import enforce_row_cap
        from rest_framework.exceptions import ValidationError
        from unittest.mock import MagicMock
        qs = MagicMock()
        qs.count.return_value = 11
        with override_settings(EXPORT_MAX_ROWS=10):
            with self.assertRaises(ValidationError):
                enforce_row_cap(qs)

    def test_csv_filename_format(self):
        from exports.filenames import csv_filename
        name = csv_filename("purchase-orders")
        self.assertRegex(name, r"^purchase-orders-\d{4}-\d{2}-\d{2}\.csv$")

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from branches.models import Branch
from goods_receipts.models import GoodsReceipt, GoodsReceiptLine
from inventory.models import MasterItem, OrgItem
from purchase_orders.models import PurchaseOrder, PurchaseOrderLine
from suppliers.models import Supplier
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


class PurchaseCostTrendApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="trend_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="trend_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="trend_staff", password="Passw0rd!")
        self.outsider = User.objects.create_user(username="trend_outsider", password="Passw0rd!")
        self.parent_admin = User.objects.create_user(username="trend_parent_admin", password="Passw0rd!")
        self.parent_viewer = User.objects.create_user(
            username="trend_parent_viewer",
            password="Passw0rd!",
        )

        self.acme = Organization.objects.create(name="Acme", slug="trend-acme")
        self.globex = Organization.objects.create(name="Globex", slug="trend-globex")

        self.branch_a = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Branch A",
            code="ACA",
        )
        self.branch_b = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Branch B",
            code="ACB",
        )
        self.globex_branch = Branch.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Branch",
            code="GLO",
        )

        OrganizationMember.objects.create(user=self.owner, organization=self.acme, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.admin, organization=self.acme, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.staff, organization=self.acme, role="STAFF", is_active=True)

        ParentCompanyMember.objects.create(
            user=self.parent_admin,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
        )
        ParentCompanyMember.objects.create(
            user=self.parent_viewer,
            role=ParentCompanyMember.PARENT_VIEWER,
            is_active=True,
        )

        self.supplier_a = Supplier.objects.for_org(self.acme).create(
            organization=self.acme,
            display_name="Acme Supplier A",
            created_by=self.owner,
        )
        self.supplier_b = Supplier.objects.for_org(self.acme).create(
            organization=self.acme,
            display_name="Acme Supplier B",
            created_by=self.owner,
        )
        self.globex_supplier = Supplier.objects.for_org(self.globex).create(
            organization=self.globex,
            display_name="Globex Supplier",
        )

        self.item = self._create_org_item(self.acme, "Tracked Item", "TREND-ITEM")
        self.other_item = self._create_org_item(self.acme, "Other Item", "TREND-OTHER")
        self.other_org_item = self._create_org_item(self.globex, "Globex Item", "TREND-GLOBEX")

        self.po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            supplier=self.supplier_a,
            branch=self.branch_a,
            status=PurchaseOrder.SUBMITTED,
            created_by=self.owner,
        )
        self.po_line = PurchaseOrderLine.objects.create(
            purchase_order=self.po,
            item=self.item,
            ordered_quantity=20,
            unit_price=Decimal("10.00"),
        )
        self.other_po_line = PurchaseOrderLine.objects.create(
            purchase_order=self.po,
            item=self.other_item,
            ordered_quantity=5,
            unit_price=Decimal("7.00"),
        )

        now = timezone.now()
        self.old_inside_date = now - timedelta(days=300)
        self.new_inside_date = now - timedelta(days=30)
        self.default_boundary_date = now - timedelta(days=365)
        self.outside_default_date = now - timedelta(days=366)

        self.po_receipt = self._create_receipt(
            receipt_type=GoodsReceipt.PO_RECEIPT,
            branch=self.branch_a,
            purchase_order=self.po,
            received_at=self.old_inside_date,
        )
        self.po_line_receipt = GoodsReceiptLine.objects.create(
            receipt=self.po_receipt,
            po_line=self.po_line,
            quantity_received=5,
            unit_cost=Decimal("9.75"),
        )

        self.direct_receipt = self._create_receipt(
            receipt_type=GoodsReceipt.DIRECT_RECEIPT,
            branch=self.branch_b,
            supplier=self.supplier_b,
            received_at=self.new_inside_date,
        )
        self.direct_line_receipt = GoodsReceiptLine.objects.create(
            receipt=self.direct_receipt,
            item=self.item,
            quantity_received=3,
            unit_cost=Decimal("12.40"),
        )

        self.none_cost_receipt = self._create_receipt(
            receipt_type=GoodsReceipt.DIRECT_RECEIPT,
            branch=self.branch_a,
            supplier=self.supplier_b,
            received_at=now - timedelta(days=20),
        )
        GoodsReceiptLine.objects.create(
            receipt=self.none_cost_receipt,
            item=self.item,
            quantity_received=4,
            unit_cost=None,
        )

        self.outside_range_receipt = self._create_receipt(
            receipt_type=GoodsReceipt.DIRECT_RECEIPT,
            branch=self.branch_a,
            supplier=self.supplier_b,
            received_at=self.outside_default_date,
        )
        GoodsReceiptLine.objects.create(
            receipt=self.outside_range_receipt,
            item=self.item,
            quantity_received=2,
            unit_cost=Decimal("13.10"),
        )

        self.boundary_receipt = self._create_receipt(
            receipt_type=GoodsReceipt.DIRECT_RECEIPT,
            branch=self.branch_a,
            supplier=self.supplier_b,
            received_at=self.default_boundary_date,
        )
        self.boundary_line = GoodsReceiptLine.objects.create(
            receipt=self.boundary_receipt,
            item=self.item,
            quantity_received=6,
            unit_cost=Decimal("11.00"),
        )

        self.other_item_receipt = self._create_receipt(
            receipt_type=GoodsReceipt.DIRECT_RECEIPT,
            branch=self.branch_a,
            supplier=self.supplier_a,
            received_at=now - timedelta(days=10),
        )
        GoodsReceiptLine.objects.create(
            receipt=self.other_item_receipt,
            item=self.other_item,
            quantity_received=1,
            unit_cost=Decimal("4.00"),
        )

    def _create_org_item(self, organization, master_name, sku):
        master_item = MasterItem.objects.create(name=master_name, sku=sku)
        return OrgItem.objects.create(
            organization=organization,
            master_item=master_item,
            name=master_name,
            is_active=True,
        )

    def _create_receipt(
        self,
        *,
        receipt_type,
        branch,
        received_at,
        purchase_order=None,
        supplier=None,
    ):
        receipt = GoodsReceipt.objects.for_org(self.acme if branch.organization_id == self.acme.id else self.globex).create(
            organization=branch.organization,
            receipt_type=receipt_type,
            branch=branch,
            purchase_order=purchase_order,
            supplier=supplier,
        )
        GoodsReceipt.objects.filter(pk=receipt.pk).update(received_at=received_at)
        receipt.refresh_from_db()
        return receipt

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _host(self, slug="trend-acme"):
        return f"{slug}.localhost:8000"

    def _url(self, org_id=None):
        target_org_id = org_id or self.acme.id
        return f"/api/orgs/{target_org_id}/reports/purchase-cost-trend/"

    def test_access_control(self):
        cases = [
            (self.owner, 200),
            (self.admin, 200),
            (self.staff, 403),
            (self.parent_admin, 200),
            (self.parent_viewer, 200),
        ]

        for user, expected_status in cases:
            self._auth(user)
            response = self.client.get(
                f"{self._url()}?item={self.item.id}",
                HTTP_HOST=self._host(),
            )
            self.assertEqual(response.status_code, expected_status)

        self.client.force_authenticate(user=None)
        response = self.client.get(
            f"{self._url()}?item={self.item.id}",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 401)

    def test_validation_errors(self):
        self._auth(self.owner)

        missing_item = self.client.get(self._url(), HTTP_HOST=self._host())
        self.assertEqual(missing_item.status_code, 400)
        self.assertEqual(missing_item.data["item"], "This field is required.")

        wrong_org_item = self.client.get(
            f"{self._url()}?item={self.other_org_item.id}",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(wrong_org_item.status_code, 400)
        self.assertEqual(
            wrong_org_item.data["item"],
            "Item not found or does not belong to this organisation.",
        )

        invalid_date = self.client.get(
            f"{self._url()}?item={self.item.id}&from_date=2026/01/01",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(invalid_date.status_code, 400)
        self.assertEqual(
            invalid_date.data["detail"],
            "Invalid date format. Use YYYY-MM-DD.",
        )

        reversed_dates = self.client.get(
            f"{self._url()}?item={self.item.id}&from_date=2026-03-01&to_date=2026-02-01",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(reversed_dates.status_code, 400)
        self.assertEqual(
            reversed_dates.data["detail"],
            "from_date must not be after to_date.",
        )

    def test_response_shape_ordering_and_content(self):
        self._auth(self.owner)
        response = self.client.get(
            f"{self._url()}?item={self.item.id}",
            HTTP_HOST=self._host(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 3)

        expected_keys = {
            "date",
            "unit_cost",
            "quantity_received",
            "supplier_id",
            "supplier_name",
            "branch_id",
            "branch_name",
            "receipt_id",
            "receipt_type",
        }
        self.assertEqual(set(response.data[0].keys()), expected_keys)

        dates = [row["date"] for row in response.data]
        self.assertEqual(dates, sorted(dates))

        receipt_map = {row["receipt_id"]: row for row in response.data}
        po_row = receipt_map[str(self.po_receipt.id)]
        direct_row = receipt_map[str(self.direct_receipt.id)]
        boundary_row = receipt_map[str(self.boundary_receipt.id)]

        self.assertEqual(po_row["receipt_type"], GoodsReceipt.PO_RECEIPT)
        self.assertEqual(po_row["supplier_id"], str(self.supplier_a.id))
        self.assertEqual(po_row["supplier_name"], self.supplier_a.name)
        self.assertEqual(po_row["quantity_received"], 5)
        self.assertEqual(po_row["unit_cost"], "9.75")

        self.assertEqual(direct_row["receipt_type"], GoodsReceipt.DIRECT_RECEIPT)
        self.assertEqual(direct_row["supplier_id"], str(self.supplier_b.id))
        self.assertEqual(direct_row["supplier_name"], self.supplier_b.name)
        self.assertEqual(direct_row["branch_id"], str(self.branch_b.id))
        self.assertEqual(direct_row["branch_name"], self.branch_b.name)

        self.assertEqual(boundary_row["receipt_id"], str(self.boundary_receipt.id))

        returned_ids = {row["receipt_id"] for row in response.data}
        self.assertNotIn(str(self.none_cost_receipt.id), returned_ids)
        self.assertNotIn(str(self.outside_range_receipt.id), returned_ids)
        self.assertNotIn(str(self.other_item_receipt.id), returned_ids)

    def test_empty_match_returns_empty_list(self):
        self._auth(self.owner)
        response = self.client.get(
            f"{self._url()}?item={self.item.id}&branch={self.globex_branch.id}",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_default_date_range_is_last_365_days(self):
        self._auth(self.owner)
        response = self.client.get(
            f"{self._url()}?item={self.item.id}",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)

        receipt_ids = [row["receipt_id"] for row in response.data]
        self.assertIn(str(self.boundary_receipt.id), receipt_ids)
        self.assertNotIn(str(self.outside_range_receipt.id), receipt_ids)

    def test_supplier_filter_matches_direct_and_po_paths(self):
        self._auth(self.owner)

        po_response = self.client.get(
            f"{self._url()}?item={self.item.id}&supplier={self.supplier_a.id}",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(po_response.status_code, 200)
        self.assertEqual([row["receipt_id"] for row in po_response.data], [str(self.po_receipt.id)])

        direct_response = self.client.get(
            f"{self._url()}?item={self.item.id}&supplier={self.supplier_b.id}",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(direct_response.status_code, 200)
        self.assertEqual(
            [row["receipt_id"] for row in direct_response.data],
            [str(self.boundary_receipt.id), str(self.direct_receipt.id)],
        )

    def test_branch_filter_matches_receipt_branch(self):
        self._auth(self.owner)

        branch_a_response = self.client.get(
            f"{self._url()}?item={self.item.id}&branch={self.branch_a.id}",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(branch_a_response.status_code, 200)
        self.assertEqual(
            [row["receipt_id"] for row in branch_a_response.data],
            [str(self.boundary_receipt.id), str(self.po_receipt.id)],
        )

        branch_b_response = self.client.get(
            f"{self._url()}?item={self.item.id}&branch={self.branch_b.id}",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(branch_b_response.status_code, 200)
        self.assertEqual([row["receipt_id"] for row in branch_b_response.data], [str(self.direct_receipt.id)])

    def test_explicit_date_filters_narrow_results(self):
        self._auth(self.owner)
        from_date = (timezone.now().date() - timedelta(days=60)).isoformat()
        to_date = (timezone.now().date() - timedelta(days=1)).isoformat()

        response = self.client.get(
            f"{self._url()}?item={self.item.id}&from_date={from_date}&to_date={to_date}",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["receipt_id"] for row in response.data], [str(self.direct_receipt.id)])

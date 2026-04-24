from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connections, transaction
from django.test import TransactionTestCase
from rest_framework.test import APITestCase

from branches.models import Branch
from goods_receipts.models import GoodsReceipt, GoodsReceiptLine
from goods_receipts.services import post_po_receipt
from inventory.models import MasterItem, OrgItem, StockLedger, StockOnHand
from inventory.services import record_stock_movement
from purchase_orders.models import PurchaseOrder
from suppliers.models import Supplier
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


class GoodsReceiptApiTests(APITestCase):
    def _create_org_item(self, organization, name, sku, *, item_name=""):
        master_item = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.for_org(organization).create(
            organization=organization,
            master_item=master_item,
            name=item_name,
        )

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="gr_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="gr_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="gr_staff", password="Passw0rd!")
        self.outsider = User.objects.create_user(username="gr_outsider", password="Passw0rd!")
        self.parent_admin_user = User.objects.create_user(username="gr_parent_admin", password="Passw0rd!")

        self.acme = Organization.objects.create(name="Acme", slug="acme-gr")
        self.globex = Organization.objects.create(name="Globex", slug="globex-gr")

        OrganizationMember.objects.create(user=self.owner, organization=self.acme, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.admin, organization=self.acme, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.staff, organization=self.acme, role="STAFF", is_active=True)

        ParentCompanyMember.objects.create(
            user=self.parent_admin_user,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
        )

        self.branch = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Main",
            code="MAIN",
        )
        self.other_branch = Branch.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Other",
            code="OTH",
        )

        self.supplier = Supplier.objects.for_org(self.acme).create(
            organization=self.acme,
            display_name="Acme Supplier",
            created_by=self.owner,
        )
        self.other_supplier = Supplier.objects.for_org(self.globex).create(
            organization=self.globex,
            display_name="Globex Supplier",
        )

        self.item_a = self._create_org_item(self.acme, "Item A", "GR-A")
        self.item_b = self._create_org_item(self.acme, "Item B", "GR-B")
        self.other_item = self._create_org_item(self.globex, "Globex Item", "GR-G")

        self.submitted_po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0001",
            supplier=self.supplier,
            branch=self.branch,
            status=PurchaseOrder.SUBMITTED,
            created_by=self.owner,
        )
        self.line_a = self.submitted_po.lines.create(
            item=self.item_a,
            ordered_quantity=5,
            unit_price=Decimal("10.00"),
        )
        self.line_b = self.submitted_po.lines.create(
            item=self.item_b,
            ordered_quantity=3,
            unit_price=Decimal("12.50"),
        )

        self.partial_po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0002",
            supplier=self.supplier,
            branch=self.branch,
            status=PurchaseOrder.PARTIALLY_RECEIVED,
            created_by=self.owner,
        )
        self.partial_line = self.partial_po.lines.create(
            item=self.item_a,
            ordered_quantity=5,
            unit_price=Decimal("9.99"),
            received_quantity=2,
        )

        self.draft_po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0003",
            supplier=self.supplier,
            branch=self.branch,
            status=PurchaseOrder.DRAFT,
            created_by=self.owner,
        )
        self.draft_po.lines.create(
            item=self.item_a,
            ordered_quantity=1,
            unit_price=Decimal("1.00"),
        )

        self.full_po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0004",
            supplier=self.supplier,
            branch=self.branch,
            status=PurchaseOrder.FULLY_RECEIVED,
            created_by=self.owner,
        )
        self.full_line = self.full_po.lines.create(
            item=self.item_a,
            ordered_quantity=2,
            unit_price=Decimal("1.00"),
            received_quantity=2,
        )

        self.cancelled_po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0005",
            supplier=self.supplier,
            branch=self.branch,
            status=PurchaseOrder.CANCELLED,
            created_by=self.owner,
        )
        self.cancelled_po.lines.create(
            item=self.item_b,
            ordered_quantity=2,
            unit_price=Decimal("2.00"),
        )

        self.empty_po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            po_number="PO-0006",
            supplier=self.supplier,
            branch=self.branch,
            status=PurchaseOrder.SUBMITTED,
            created_by=self.owner,
        )

        self.other_po = PurchaseOrder.objects.for_org(self.globex).create(
            organization=self.globex,
            po_number="PO-0001",
            supplier=self.other_supplier,
            branch=self.other_branch,
            status=PurchaseOrder.SUBMITTED,
            created_by=self.owner,
        )
        self.other_line = self.other_po.lines.create(
            item=self.other_item,
            ordered_quantity=4,
            unit_price=Decimal("7.00"),
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _host(self, slug="acme-gr"):
        return f"{slug}.localhost:8000"

    def _base_url(self, org_id=None):
        target_org = org_id or self.acme.id
        return f"/api/orgs/{target_org}/goods-receipts/"

    def _detail_url(self, receipt_id, org_id=None):
        return f"{self._base_url(org_id=org_id)}{receipt_id}/"

    def _payload(self, po=None, lines=None, **overrides):
        payload = {
            "purchase_order": str((po or self.submitted_po).id),
            "notes": "Receipt notes",
            "lines": [{"po_line": self.line_a.id, "quantity_received": 2}] if lines is None else lines,
        }
        payload.update(overrides)
        return payload

    def _post(self, user=None, po=None, lines=None, org_id=None, host=None, **overrides):
        if user:
            self._auth(user)
        return self.client.post(
            self._base_url(org_id=org_id),
            self._payload(po=po, lines=lines, **overrides),
            format="json",
            HTTP_HOST=host or self._host(),
        )

    def _direct_payload(self, lines=None, **overrides):
        payload = {
            "receipt_type": GoodsReceipt.DIRECT_RECEIPT,
            "branch": self.branch.id,
            "notes": "Direct receipt",
            "lines": (
                [{"item": self.item_a.id, "quantity_received": 2, "unit_cost": "3.50"}]
                if lines is None
                else lines
            ),
        }
        payload.update(overrides)
        return payload

    def _post_direct(self, user=None, org_id=None, host=None, lines=None, **overrides):
        if user:
            self._auth(user)
        return self.client.post(
            self._base_url(org_id=org_id),
            self._direct_payload(lines=lines, **overrides),
            format="json",
            HTTP_HOST=host or self._host(),
        )

    def test_create_access_rules(self):
        for user, expected_status in (
            (self.owner, 201),
            (self.admin, 201),
            (self.staff, 201),
            (self.parent_admin_user, 403),
        ):
            po = PurchaseOrder.objects.for_org(self.acme).create(
                organization=self.acme,
                po_number=f"PO-X-{user.username}",
                supplier=self.supplier,
                branch=self.branch,
                status=PurchaseOrder.SUBMITTED,
                created_by=self.owner,
            )
            line = po.lines.create(item=self.item_a, ordered_quantity=2, unit_price=Decimal("4.00"))
            response = self._post(user=user, po=po, lines=[{"po_line": line.id, "quantity_received": 1}])
            self.assertEqual(response.status_code, expected_status)

        self.client.force_authenticate(user=None)
        unauthenticated = self.client.post(
            self._base_url(),
            self._payload(),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(unauthenticated.status_code, 401)

    def test_purchase_order_validation_rules(self):
        self._auth(self.owner)

        cross_org = self._post(po=self.other_po)
        self.assertEqual(cross_org.status_code, 400)
        self.assertIn("purchase_order", cross_org.data)

        draft = self._post(po=self.draft_po)
        self.assertEqual(draft.status_code, 400)

        fully_received = self._post(po=self.full_po, lines=[{"po_line": self.full_line.id, "quantity_received": 1}])
        self.assertEqual(fully_received.status_code, 400)

        cancelled = self._post(po=self.cancelled_po)
        self.assertEqual(cancelled.status_code, 400)

        empty = self._post(po=self.empty_po, lines=[{"po_line": self.line_a.id, "quantity_received": 1}])
        self.assertEqual(empty.status_code, 400)
        self.assertIn("purchase_order", empty.data)

        partial_allowed = self._post(
            po=self.partial_po,
            lines=[{"po_line": self.partial_line.id, "quantity_received": 1}],
        )
        self.assertEqual(partial_allowed.status_code, 201)

    def test_cancelled_under_lock_is_rejected_during_post(self):
        self._auth(self.owner)

        with patch("goods_receipts.services.PurchaseOrder.objects.select_for_update") as mocked_lock:
            mocked_lock.return_value.get.return_value = self.cancelled_po
            response = self._post(po=self.submitted_po)

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)
        self.assertIn("status CANCELLED", str(response.data["detail"]))

    def test_line_validation_rules(self):
        self._auth(self.owner)

        no_lines = self._post(lines=[])
        self.assertEqual(no_lines.status_code, 400)
        self.assertIn("lines", no_lines.data)

        duplicate = self._post(
            lines=[
                {"po_line": self.line_a.id, "quantity_received": 1},
                {"po_line": self.line_a.id, "quantity_received": 1},
            ]
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("lines", duplicate.data)

        wrong_po_line = self._post(
            lines=[{"po_line": self.other_line.id, "quantity_received": 1}]
        )
        self.assertEqual(wrong_po_line.status_code, 400)
        self.assertIn("lines", wrong_po_line.data)

        zero_qty = self._post(lines=[{"po_line": self.line_a.id, "quantity_received": 0}])
        self.assertEqual(zero_qty.status_code, 400)
        self.assertIn("quantity_received", zero_qty.data["lines"][0])

        negative_qty = self._post(lines=[{"po_line": self.line_a.id, "quantity_received": -1}])
        self.assertEqual(negative_qty.status_code, 400)
        self.assertIn("quantity_received", negative_qty.data["lines"][0])

        exceeds_remaining = self._post(lines=[{"po_line": self.line_a.id, "quantity_received": 6}])
        self.assertEqual(exceeds_remaining.status_code, 400)
        self.assertIn("lines", exceeds_remaining.data)

        exact_remaining = self._post(lines=[{"po_line": self.line_a.id, "quantity_received": 5}])
        self.assertEqual(exact_remaining.status_code, 201)

        fully_received_line = self._post(
            po=self.partial_po,
            lines=[{"po_line": self.partial_line.id, "quantity_received": 3}],
        )
        self.assertEqual(fully_received_line.status_code, 201)

        fully_received_again = self._post(
            po=self.partial_po,
            lines=[{"po_line": self.partial_line.id, "quantity_received": 1}],
        )
        self.assertEqual(fully_received_again.status_code, 400)

    def test_po_receipt_unit_cost_defaults_and_validation(self):
        self._auth(self.owner)

        default_cost = self._post(
            po=self.submitted_po,
            lines=[{"po_line": self.line_a.id, "quantity_received": 1}],
        )
        self.assertEqual(default_cost.status_code, 201)
        default_line = GoodsReceiptLine.objects.get(receipt_id=default_cost.data["id"], po_line=self.line_a)
        self.assertEqual(default_line.unit_cost, self.line_a.unit_price)

        provided_cost = self._post(
            po=self.submitted_po,
            lines=[{"po_line": self.line_b.id, "quantity_received": 1, "unit_cost": "15.25"}],
        )
        self.assertEqual(provided_cost.status_code, 201)
        provided_line = GoodsReceiptLine.objects.get(receipt_id=provided_cost.data["id"], po_line=self.line_b)
        self.assertEqual(provided_line.unit_cost, Decimal("15.25"))

        zero_cost = self._post(
            po=self.partial_po,
            lines=[{"po_line": self.partial_line.id, "quantity_received": 1, "unit_cost": "0.00"}],
        )
        self.assertEqual(zero_cost.status_code, 400)

        negative_cost = self._post(
            po=self.partial_po,
            lines=[{"po_line": self.partial_line.id, "quantity_received": 1, "unit_cost": "-1.00"}],
        )
        self.assertEqual(negative_cost.status_code, 400)

    def test_po_receipt_idempotency_reuses_existing_receipt(self):
        self._auth(self.owner)

        payload_key = "gr-po-idem-1"
        first = self._post(
            po=self.submitted_po,
            idempotency_key=payload_key,
            lines=[{"po_line": self.line_a.id, "quantity_received": 2}],
        )
        self.assertEqual(first.status_code, 201)

        second = self._post(
            po=self.submitted_po,
            idempotency_key=payload_key,
            # Intentionally different payload to verify key-level dedupe semantics.
            lines=[{"po_line": self.line_a.id, "quantity_received": 1}],
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["id"], first.data["id"])

        self.line_a.refresh_from_db()
        self.assertEqual(self.line_a.received_quantity, 2)
        self.assertEqual(
            GoodsReceipt.objects.for_org(self.acme).filter(idempotency_key=payload_key).count(),
            1,
        )

    def test_direct_receipt_idempotency_reuses_existing_receipt(self):
        self._auth(self.owner)

        payload_key = "gr-direct-idem-1"
        first = self._post_direct(
            idempotency_key=payload_key,
            lines=[{"item": self.item_a.id, "quantity_received": 2, "unit_cost": "4.25"}],
        )
        self.assertEqual(first.status_code, 201)

        second = self._post_direct(
            idempotency_key=payload_key,
            lines=[{"item": self.item_a.id, "quantity_received": 1, "unit_cost": "4.25"}],
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["id"], first.data["id"])

        stock = StockOnHand.objects.for_org(self.acme).get(branch=self.branch, item=self.item_a)
        self.assertEqual(stock.quantity, Decimal("2.0000"))
        self.assertEqual(
            GoodsReceipt.objects.for_org(self.acme).filter(idempotency_key=payload_key).count(),
            1,
        )

    def test_direct_receipt_create_access_rules(self):
        for user, expected_status in (
            (self.owner, 201),
            (self.admin, 201),
            (self.staff, 201),
            (self.parent_admin_user, 403),
        ):
            response = self._post_direct(
                user=user,
                lines=[{"item": self.item_a.id, "quantity_received": 1, "unit_cost": "4.50"}],
            )
            self.assertEqual(response.status_code, expected_status)

    def test_direct_receipt_validation_rules(self):
        self._auth(self.owner)

        missing_branch = self._post_direct(branch=None)
        self.assertEqual(missing_branch.status_code, 400)
        self.assertIn("branch", missing_branch.data)

        wrong_branch = self._post_direct(branch=self.other_branch.id)
        self.assertEqual(wrong_branch.status_code, 400)
        self.assertIn("branch", wrong_branch.data)

        wrong_supplier = self._post_direct(supplier=self.other_supplier.id)
        self.assertEqual(wrong_supplier.status_code, 400)
        self.assertIn("supplier", wrong_supplier.data)

        self.supplier.is_active = False
        self.supplier.save(update_fields=["is_active"])
        inactive_supplier = self._post_direct(supplier=self.supplier.id)
        self.assertEqual(inactive_supplier.status_code, 400)
        self.assertIn("supplier", inactive_supplier.data)
        self.supplier.is_active = True
        self.supplier.save(update_fields=["is_active"])

        no_lines = self._post_direct(lines=[])
        self.assertEqual(no_lines.status_code, 400)
        self.assertIn("lines", no_lines.data)

        duplicate_items = self._post_direct(
            lines=[
                {"item": self.item_a.id, "quantity_received": 1, "unit_cost": "4.00"},
                {"item": self.item_a.id, "quantity_received": 2, "unit_cost": "4.00"},
            ]
        )
        self.assertEqual(duplicate_items.status_code, 400)
        self.assertIn("lines", duplicate_items.data)

        other_org_item = self._post_direct(
            lines=[{"item": self.other_item.id, "quantity_received": 1, "unit_cost": "4.00"}]
        )
        self.assertEqual(other_org_item.status_code, 400)
        self.assertIn("item", other_org_item.data["lines"][0])

        zero_qty = self._post_direct(
            lines=[{"item": self.item_a.id, "quantity_received": 0, "unit_cost": "4.00"}]
        )
        self.assertEqual(zero_qty.status_code, 400)
        self.assertIn("quantity_received", zero_qty.data["lines"][0])

        missing_unit_cost = self._post_direct(lines=[{"item": self.item_a.id, "quantity_received": 1}])
        self.assertEqual(missing_unit_cost.status_code, 400)
        self.assertIn("unit_cost", missing_unit_cost.data["lines"][0])

        zero_unit_cost = self._post_direct(
            lines=[{"item": self.item_a.id, "quantity_received": 1, "unit_cost": "0.00"}]
        )
        self.assertEqual(zero_unit_cost.status_code, 400)
        self.assertIn("unit_cost", zero_unit_cost.data["lines"][0])

        negative_unit_cost = self._post_direct(
            lines=[{"item": self.item_a.id, "quantity_received": 1, "unit_cost": "-2.00"}]
        )
        self.assertEqual(negative_unit_cost.status_code, 400)
        self.assertIn("unit_cost", negative_unit_cost.data["lines"][0])

    def test_direct_receipt_creation_and_stock_posting(self):
        self._auth(self.owner)

        response = self._post_direct(
            supplier=self.supplier.id,
            source_reference="DEL-123",
            lines=[
                {"item": self.item_a.id, "quantity_received": 2, "unit_cost": "4.25"},
                {"item": self.item_b.id, "quantity_received": 1, "unit_cost": "8.75"},
            ],
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["lines"][0]["item"]["id"], str(self.item_a.id))
        self.assertEqual(response.data["lines"][0]["item"]["name"], self.item_a.display_name)
        self.assertEqual(response.data["lines"][0]["item"]["sku"], self.item_a.master_item.sku)

        receipt = GoodsReceipt.objects.for_org(self.acme).get(pk=response.data["id"])
        self.assertEqual(receipt.receipt_type, GoodsReceipt.DIRECT_RECEIPT)
        self.assertIsNone(receipt.purchase_order)
        self.assertEqual(receipt.branch, self.branch)
        self.assertEqual(receipt.supplier, self.supplier)
        self.assertEqual(receipt.source_reference, "DEL-123")
        self.assertEqual(receipt.lines.count(), 2)

        line_a = receipt.lines.get(item=self.item_a)
        line_b = receipt.lines.get(item=self.item_b)
        self.assertEqual(line_a.unit_cost, Decimal("4.25"))
        self.assertEqual(line_b.unit_cost, Decimal("8.75"))
        self.assertIsNone(line_a.po_line)

        stock_a = StockOnHand.objects.for_org(self.acme).get(branch=self.branch, item=self.item_a)
        stock_b = StockOnHand.objects.for_org(self.acme).get(branch=self.branch, item=self.item_b)
        self.assertEqual(stock_a.quantity, Decimal("2.0000"))
        self.assertEqual(stock_b.quantity, Decimal("1.0000"))

    def test_receipt_retrieve_returns_nested_item_summary(self):
        self._auth(self.owner)
        created = self._post_direct(
            supplier=self.supplier.id,
            lines=[{"item": self.item_a.id, "quantity_received": 2, "unit_cost": "4.25"}],
        )
        self.assertEqual(created.status_code, 201)

        response = self.client.get(
            self._detail_url(created.data["id"]),
            HTTP_HOST=self._host(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["lines"][0]["item"]["id"], str(self.item_a.id))
        self.assertEqual(response.data["lines"][0]["item"]["name"], self.item_a.display_name)
        self.assertEqual(response.data["lines"][0]["item"]["sku"], self.item_a.master_item.sku)

    def test_direct_receipt_optional_supplier_and_source_reference_blank(self):
        self._auth(self.owner)
        response = self._post_direct()
        self.assertEqual(response.status_code, 201)
        receipt = GoodsReceipt.objects.for_org(self.acme).get(pk=response.data["id"])
        self.assertIsNone(receipt.supplier)
        self.assertEqual(receipt.source_reference, "")

    def test_direct_receipt_serializer_requires_branch_and_model_requires_non_null_branch(self):
        self._auth(self.owner)
        response = self.client.post(
            self._base_url(),
            {
                "receipt_type": GoodsReceipt.DIRECT_RECEIPT,
                "notes": "No branch",
                "lines": [{"item": self.item_a.id, "quantity_received": 1, "unit_cost": "2.00"}],
            },
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("branch", response.data)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GoodsReceipt.objects.create(
                    organization=self.acme,
                    receipt_type=GoodsReceipt.DIRECT_RECEIPT,
                    purchase_order=None,
                    received_by=self.owner,
                )

    def test_stock_posting_and_status_updates(self):
        self._auth(self.owner)
        with patch("goods_receipts.services.record_stock_movement", wraps=record_stock_movement) as mocked_record:
            response = self._post(
                po=self.submitted_po,
                lines=[
                    {"po_line": self.line_a.id, "quantity_received": 2},
                    {"po_line": self.line_b.id, "quantity_received": 3},
                ],
            )

        self.assertEqual(response.status_code, 201)
        receipt = GoodsReceipt.objects.for_org(self.acme).get(pk=response.data["id"])
        self.assertEqual(receipt.received_by, self.owner)
        self.assertEqual(receipt.lines.count(), 2)
        self.assertEqual(mocked_record.call_count, 2)
        self.assertEqual(mocked_record.call_args_list[0].kwargs["branch"], self.branch)
        self.assertEqual(mocked_record.call_args_list[0].kwargs["movement_type"], StockLedger.MOVEMENT_RECEIPT)

        self.line_a.refresh_from_db()
        self.line_b.refresh_from_db()
        self.submitted_po.refresh_from_db()
        self.assertEqual(self.line_a.received_quantity, 2)
        self.assertEqual(self.line_b.received_quantity, 3)
        self.assertEqual(self.submitted_po.status, PurchaseOrder.PARTIALLY_RECEIVED)

        stock_a = StockOnHand.objects.for_org(self.acme).get(branch=self.branch, item=self.item_a)
        stock_b = StockOnHand.objects.for_org(self.acme).get(branch=self.branch, item=self.item_b)
        self.assertEqual(stock_a.quantity, Decimal("2.0000"))
        self.assertEqual(stock_b.quantity, Decimal("3.0000"))
        self.assertEqual(
            StockLedger.objects.for_org(self.acme).filter(branch=self.branch, movement_type=StockLedger.MOVEMENT_RECEIPT).count(),
            2,
        )
        self.assertEqual(mocked_record.call_args_list[0].kwargs["unit_cost"], self.line_a.unit_price)
        self.assertEqual(mocked_record.call_args_list[1].kwargs["unit_cost"], self.line_b.unit_price)

    def test_direct_receipt_checks_period_before_posting(self):
        self._auth(self.owner)
        with patch("goods_receipts.services.assert_inventory_period_open") as mocked_period_check:
            response = self._post_direct(
                lines=[{"item": self.item_a.id, "quantity_received": 1, "unit_cost": "4.25"}],
            )

        self.assertEqual(response.status_code, 201)
        mocked_period_check.assert_called_once()

    def test_purchase_order_status_reaches_fully_received(self):
        self._auth(self.owner)
        response = self._post(
            po=self.submitted_po,
            lines=[
                {"po_line": self.line_a.id, "quantity_received": 5},
                {"po_line": self.line_b.id, "quantity_received": 3},
            ],
        )
        self.assertEqual(response.status_code, 201)
        self.submitted_po.refresh_from_db()
        self.assertEqual(self.submitted_po.status, PurchaseOrder.FULLY_RECEIVED)

    def test_second_receipt_updates_status_correctly(self):
        self._auth(self.owner)
        first = self._post(
            po=self.submitted_po,
            lines=[{"po_line": self.line_a.id, "quantity_received": 2}],
        )
        self.assertEqual(first.status_code, 201)
        self.submitted_po.refresh_from_db()
        self.assertEqual(self.submitted_po.status, PurchaseOrder.PARTIALLY_RECEIVED)

        second_partial = self._post(
            po=self.submitted_po,
            lines=[{"po_line": self.line_a.id, "quantity_received": 1}],
        )
        self.assertEqual(second_partial.status_code, 201)
        self.submitted_po.refresh_from_db()
        self.assertEqual(self.submitted_po.status, PurchaseOrder.PARTIALLY_RECEIVED)

        final = self._post(
            po=self.submitted_po,
            lines=[
                {"po_line": self.line_a.id, "quantity_received": 2},
                {"po_line": self.line_b.id, "quantity_received": 3},
            ],
        )
        self.assertEqual(final.status_code, 201)
        self.submitted_po.refresh_from_db()
        self.assertEqual(self.submitted_po.status, PurchaseOrder.FULLY_RECEIVED)

    def test_atomic_rollback_when_posting_fails(self):
        self._auth(self.owner)

        with patch(
            "goods_receipts.services.record_stock_movement",
            side_effect=ValidationError("forced failure"),
        ):
            response = self._post(
                po=self.submitted_po,
                lines=[{"po_line": self.line_a.id, "quantity_received": 2}],
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(GoodsReceipt.objects.for_org(self.acme).count(), 0)
        self.assertEqual(GoodsReceiptLine.objects.count(), 0)
        self.assertFalse(StockOnHand.objects.for_org(self.acme).exists())
        self.line_a.refresh_from_db()
        self.assertEqual(self.line_a.received_quantity, 0)
        self.submitted_po.refresh_from_db()
        self.assertEqual(self.submitted_po.status, PurchaseOrder.SUBMITTED)

    def test_immutability_and_read_access(self):
        self._auth(self.owner)
        create_response = self._post(
            po=self.submitted_po,
            lines=[{"po_line": self.line_a.id, "quantity_received": 2}],
        )
        self.assertEqual(create_response.status_code, 201)
        receipt_id = create_response.data["id"]

        patch_response = self.client.patch(
            self._detail_url(receipt_id),
            {"notes": "nope"},
            format="json",
            HTTP_HOST=self._host(),
        )
        delete_response = self.client.delete(
            self._detail_url(receipt_id),
            HTTP_HOST=self._host(),
        )
        self.assertEqual(patch_response.status_code, 405)
        self.assertEqual(delete_response.status_code, 405)

        other_receipt = GoodsReceipt.objects.for_org(self.globex).create(
            organization=self.globex,
            receipt_type=GoodsReceipt.PO_RECEIPT,
            purchase_order=self.other_po,
            branch=self.other_branch,
            received_by=self.owner,
            notes="Globex receipt",
        )
        other_receipt.lines.create(
            po_line=self.other_line,
            quantity_received=1,
            unit_cost=self.other_line.unit_price,
        )

        for user in (self.owner, self.admin, self.staff):
            self._auth(user)
            list_response = self.client.get(self._base_url(), HTTP_HOST=self._host())
            self.assertEqual(list_response.status_code, 200)
            ids = {row["id"] for row in list_response.data["results"]}
            self.assertIn(str(receipt_id), ids)
            self.assertNotIn(str(other_receipt.id), ids)

        self._auth(self.parent_admin_user)
        parent_list = self.client.get(self._base_url(), HTTP_HOST=self._host())
        self.assertEqual(parent_list.status_code, 200)
        self.assertIn(str(receipt_id), {row["id"] for row in parent_list.data["results"]})

        parent_cross_org = self.client.get(
            self._base_url(org_id=self.globex.id),
            HTTP_HOST=self._host("globex-gr"),
        )
        self.assertEqual(parent_cross_org.status_code, 200)
        self.assertIn(str(other_receipt.id), {row["id"] for row in parent_cross_org.data["results"]})

        parent_post = self._post(
            user=self.parent_admin_user,
            po=self.submitted_po,
            lines=[{"po_line": self.line_b.id, "quantity_received": 1}],
        )
        self.assertEqual(parent_post.status_code, 403)

        retrieve_response = self.client.get(self._detail_url(receipt_id), HTTP_HOST=self._host())
        self.assertEqual(retrieve_response.status_code, 200)
        self.assertEqual(len(retrieve_response.data["lines"]), 1)


class GoodsReceiptConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def _create_org_item(self, organization, name, sku, *, item_name=""):
        master_item = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.for_org(organization).create(
            organization=organization,
            master_item=master_item,
            name=item_name,
        )

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="gr_concurrency_user", password="Passw0rd!")
        self.org = Organization.objects.create(name="Concurrency Org", slug="concurrency-gr")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="MAIN",
        )
        self.supplier = Supplier.objects.for_org(self.org).create(
            organization=self.org,
            display_name="Concurrency Supplier",
            created_by=self.user,
        )

        self.item = self._create_org_item(self.org, "Concurrent Item", "CON-GR")
        self.po = PurchaseOrder.objects.for_org(self.org).create(
            organization=self.org,
            po_number="PO-0001",
            supplier=self.supplier,
            branch=self.branch,
            status=PurchaseOrder.SUBMITTED,
            created_by=self.user,
        )
        self.po_line = self.po.lines.create(
            item=self.item,
            ordered_quantity=5,
            unit_price=Decimal("10.00"),
        )

    def test_concurrent_receipts_do_not_over_receive(self):
        results = []

        def worker():
            close_old_connections()
            try:
                with transaction.atomic():
                    receipt = GoodsReceipt.objects.create(
                        organization=self.org,
                        receipt_type=GoodsReceipt.PO_RECEIPT,
                        purchase_order=self.po,
                        branch=self.branch,
                        received_by=self.user,
                    )
                    post_po_receipt(
                        receipt=receipt,
                        lines_data=[{"po_line": self.po_line, "quantity_received": 4}],
                        performed_by=self.user,
                        organization=self.org,
                    )
                results.append(("success", receipt.id))
            except ValidationError as exc:
                results.append(("error", exc.messages))
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(lambda _: worker(), range(2)))

        self.po_line.refresh_from_db()
        self.po.refresh_from_db()

        successes = [row for row in results if row[0] == "success"]
        errors = [row for row in results if row[0] == "error"]

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("exceeds remaining quantity (1)", errors[0][1][0])
        self.assertEqual(self.po_line.received_quantity, 4)
        self.assertEqual(self.po.status, PurchaseOrder.PARTIALLY_RECEIVED)
        self.assertEqual(GoodsReceipt.objects.for_org(self.org).count(), 1)
        self.assertEqual(
            StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item).quantity,
            Decimal("4.0000"),
        )

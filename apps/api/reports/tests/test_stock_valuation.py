from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from branches.models import Branch
from goods_receipts.models import GoodsReceipt, GoodsReceiptLine
from inventory.models import MasterItem, OrgItem, StockOnHand
from purchase_orders.models import PurchaseOrder, PurchaseOrderLine
from suppliers.models import Supplier
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


class StockValuationApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="sv_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="sv_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="sv_staff", password="Passw0rd!")
        self.parent_admin = User.objects.create_user(username="sv_parent_admin", password="Passw0rd!")
        self.parent_viewer = User.objects.create_user(username="sv_parent_viewer", password="Passw0rd!")

        self.acme = Organization.objects.create(name="SV Acme", slug="sv-acme")
        self.other_org = Organization.objects.create(name="SV Other", slug="sv-other")

        self.branch_a = Branch.objects.for_org(self.acme).create(
            organization=self.acme, name="Branch A", code="SVA"
        )
        self.branch_b = Branch.objects.for_org(self.acme).create(
            organization=self.acme, name="Branch B", code="SVB"
        )
        self.other_branch = Branch.objects.for_org(self.other_org).create(
            organization=self.other_org, name="Other Branch", code="SVO"
        )

        OrganizationMember.objects.create(user=self.owner, organization=self.acme, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.admin, organization=self.acme, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.staff, organization=self.acme, role="STAFF", is_active=True)

        ParentCompanyMember.objects.create(
            user=self.parent_admin, role=ParentCompanyMember.PARENT_ADMIN, is_active=True
        )
        ParentCompanyMember.objects.create(
            user=self.parent_viewer, role=ParentCompanyMember.PARENT_VIEWER, is_active=True
        )

        self.supplier = Supplier.objects.for_org(self.acme).create(
            organization=self.acme, name="Supplier", created_by=self.owner
        )

        # Create items
        self.item_a = self._create_org_item(self.acme, "Alpha Widget", "SKU-ALPHA")
        self.item_b = self._create_org_item(self.acme, "Beta Gadget", "SKU-BETA")
        self.item_no_receipt = self._create_org_item(self.acme, "Gamma Thing", "SKU-GAMMA")
        self.other_item = self._create_org_item(self.other_org, "Other Item", "SKU-OTHER")

        # Stock on hand
        self.soh_a_branchA = self._create_soh(self.acme, self.item_a, self.branch_a, Decimal("10"))
        self.soh_a_branchB = self._create_soh(self.acme, self.item_a, self.branch_b, Decimal("5"))
        self.soh_b_branchA = self._create_soh(self.acme, self.item_b, self.branch_a, Decimal("3"))
        self.soh_no_receipt = self._create_soh(self.acme, self.item_no_receipt, self.branch_a, Decimal("7"))
        # Zero-stock row — should be excluded
        self._create_soh(self.acme, self.item_b, self.branch_b, Decimal("0"))

        # Receipt lines for item_a at branch_a: two receipts at different times
        now = timezone.now()
        self.old_receipt = self._create_receipt(self.acme, self.branch_a, received_at=now.replace(year=now.year - 1))
        GoodsReceiptLine.objects.create(
            receipt=self.old_receipt,
            item=self.item_a,
            quantity_received=4,
            unit_cost=Decimal("10.00"),
        )
        self.new_receipt = self._create_receipt(self.acme, self.branch_a, received_at=now)
        GoodsReceiptLine.objects.create(
            receipt=self.new_receipt,
            item=self.item_a,
            quantity_received=6,
            unit_cost=Decimal("12.00"),
        )

        # Receipt line for item_a at branch_b
        self.receipt_branchB = self._create_receipt(self.acme, self.branch_b, received_at=now)
        GoodsReceiptLine.objects.create(
            receipt=self.receipt_branchB,
            item=self.item_a,
            quantity_received=5,
            unit_cost=Decimal("11.00"),
        )

        # Receipt line for item_b at branch_a (via PO line)
        self.po = PurchaseOrder.objects.for_org(self.acme).create(
            organization=self.acme,
            supplier=self.supplier,
            branch=self.branch_a,
            status=PurchaseOrder.SUBMITTED,
            created_by=self.owner,
        )
        self.po_line_b = PurchaseOrderLine.objects.create(
            purchase_order=self.po,
            item=self.item_b,
            ordered_quantity=10,
            unit_price=Decimal("8.00"),
        )
        self.receipt_b = self._create_receipt(self.acme, self.branch_a, received_at=now, purchase_order=self.po)
        GoodsReceiptLine.objects.create(
            receipt=self.receipt_b,
            po_line=self.po_line_b,
            quantity_received=3,
            unit_cost=Decimal("8.00"),
        )

        # Receipt line for other_org's item at other_branch — must be excluded
        self.other_receipt = self._create_receipt(self.other_org, self.other_branch, received_at=now)
        GoodsReceiptLine.objects.create(
            receipt=self.other_receipt,
            item=self.other_item,
            quantity_received=10,
            unit_cost=Decimal("99.00"),
        )

    def _create_org_item(self, org, name, sku):
        master = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.create(organization=org, master_item=master, name=name, is_active=True)

    def _create_soh(self, org, item, branch, quantity):
        soh = StockOnHand.objects.for_org(org).create(organization=org, item=item, branch=branch)
        StockOnHand.objects.filter(pk=soh.pk).update(quantity=quantity)
        soh.refresh_from_db()
        return soh

    def _create_receipt(self, org, branch, *, received_at, purchase_order=None, supplier=None):
        receipt = GoodsReceipt.objects.for_org(org).create(
            organization=org,
            receipt_type=GoodsReceipt.PO_RECEIPT if purchase_order else GoodsReceipt.DIRECT_RECEIPT,
            branch=branch,
            purchase_order=purchase_order,
            supplier=supplier or (self.supplier if org == self.acme else None),
        )
        GoodsReceipt.objects.filter(pk=receipt.pk).update(received_at=received_at)
        receipt.refresh_from_db()
        return receipt

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _url(self, org_id=None):
        target = org_id or self.acme.id
        return f"/api/orgs/{target}/reports/stock-valuation/"

    # ── Access control ────────────────────────────────────────────────────────

    def test_access_owner(self):
        self._auth(self.owner)
        self.assertEqual(self.client.get(self._url()).status_code, 200)

    def test_access_admin(self):
        self._auth(self.admin)
        self.assertEqual(self.client.get(self._url()).status_code, 200)

    def test_access_staff_forbidden(self):
        self._auth(self.staff)
        self.assertEqual(self.client.get(self._url()).status_code, 403)

    def test_access_parent_admin(self):
        self._auth(self.parent_admin)
        self.assertEqual(self.client.get(self._url()).status_code, 200)

    def test_access_parent_viewer(self):
        self._auth(self.parent_viewer)
        self.assertEqual(self.client.get(self._url()).status_code, 200)

    def test_access_unauthenticated(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self._url()).status_code, 401)

    # ── Response shape ────────────────────────────────────────────────────────

    def test_response_has_summary_and_results(self):
        self._auth(self.owner)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("summary", response.data)
        self.assertIn("results", response.data)

    def test_summary_has_all_fields(self):
        self._auth(self.owner)
        summary = self.client.get(self._url()).data["summary"]
        for field in ("total_latest_valuation", "total_average_valuation", "item_count", "branch_count"):
            self.assertIn(field, summary)

    def test_result_rows_have_all_fields(self):
        self._auth(self.owner)
        results = self.client.get(self._url()).data["results"]
        self.assertTrue(len(results) > 0)
        expected_keys = {
            "item_id", "item_name", "item_sku", "branch_id", "branch_name",
            "quantity_on_hand", "latest_unit_cost", "latest_valuation",
            "average_unit_cost", "average_valuation",
        }
        self.assertEqual(set(results[0].keys()), expected_keys)

    # ── Content correctness ───────────────────────────────────────────────────

    def test_only_positive_stock_included(self):
        self._auth(self.owner)
        results = self.client.get(self._url()).data["results"]
        for row in results:
            self.assertGreater(Decimal(row["quantity_on_hand"]), 0)

    def test_zero_stock_excluded(self):
        """item_b at branch_b has quantity=0 — must not appear."""
        self._auth(self.owner)
        results = self.client.get(self._url()).data["results"]
        for row in results:
            if str(row["item_id"]) == str(self.item_b.id):
                self.assertNotEqual(str(row["branch_id"]), str(self.branch_b.id))

    def test_latest_cost_is_most_recent_receipt(self):
        """item_a at branch_a had two receipts; latest cost must be 12.00."""
        self._auth(self.owner)
        results = self.client.get(self._url()).data["results"]
        row = next(
            r for r in results
            if str(r["item_id"]) == str(self.item_a.id) and str(r["branch_id"]) == str(self.branch_a.id)
        )
        self.assertEqual(Decimal(row["latest_unit_cost"]), Decimal("12.00"))

    def test_average_cost_is_weighted_avco(self):
        """item_a at branch_a: (4*10 + 6*12) / 10 = 11.20."""
        self._auth(self.owner)
        results = self.client.get(self._url()).data["results"]
        row = next(
            r for r in results
            if str(r["item_id"]) == str(self.item_a.id) and str(r["branch_id"]) == str(self.branch_a.id)
        )
        self.assertEqual(Decimal(row["average_unit_cost"]), Decimal("11.20"))

    def test_latest_valuation_equals_qty_times_latest_cost(self):
        self._auth(self.owner)
        results = self.client.get(self._url()).data["results"]
        for row in results:
            if row["latest_unit_cost"] is not None:
                expected = (Decimal(row["quantity_on_hand"]) * Decimal(row["latest_unit_cost"])).quantize(Decimal("0.01"))
                self.assertEqual(Decimal(row["latest_valuation"]), expected)

    def test_average_valuation_equals_qty_times_avg_cost(self):
        self._auth(self.owner)
        results = self.client.get(self._url()).data["results"]
        for row in results:
            if row["average_unit_cost"] is not None:
                expected = (Decimal(row["quantity_on_hand"]) * Decimal(row["average_unit_cost"])).quantize(Decimal("0.01"))
                self.assertEqual(Decimal(row["average_valuation"]), expected)

    def test_no_receipt_history_gives_null_costs(self):
        """item_no_receipt has stock but no receipt lines — costs must be null."""
        self._auth(self.owner)
        results = self.client.get(self._url()).data["results"]
        row = next(
            r for r in results
            if str(r["item_id"]) == str(self.item_no_receipt.id)
        )
        self.assertIsNone(row["latest_unit_cost"])
        self.assertIsNone(row["latest_valuation"])
        self.assertIsNone(row["average_unit_cost"])
        self.assertIsNone(row["average_valuation"])

    def test_null_cost_rows_counted_in_summary(self):
        """item_no_receipt must contribute to item_count and branch_count."""
        self._auth(self.owner)
        summary = self.client.get(self._url()).data["summary"]
        # We have 3 unique items: item_a, item_b, item_no_receipt
        self.assertEqual(summary["item_count"], 3)

    def test_null_cost_rows_not_in_totals(self):
        """Totals must exclude rows with no receipt history."""
        self._auth(self.owner)
        results = self.client.get(self._url()).data["results"]
        computed_latest = sum(
            Decimal(r["latest_valuation"]) for r in results if r["latest_valuation"] is not None
        )
        computed_avg = sum(
            Decimal(r["average_valuation"]) for r in results if r["average_valuation"] is not None
        )
        summary = self.client.get(self._url()).data["summary"]
        self.assertEqual(Decimal(summary["total_latest_valuation"]), computed_latest)
        self.assertEqual(Decimal(summary["total_average_valuation"]), computed_avg)

    def test_summary_totals_match_non_null_rows(self):
        """Explicit check: total_latest = sum of non-null latest_valuation."""
        self._auth(self.owner)
        data = self.client.get(self._url()).data
        results = data["results"]
        expected_latest = sum(
            Decimal(r["latest_valuation"]) for r in results if r["latest_valuation"] is not None
        )
        self.assertEqual(Decimal(data["summary"]["total_latest_valuation"]), expected_latest)

    # ── Sorting ───────────────────────────────────────────────────────────────

    def test_results_sorted_by_latest_valuation_descending_null_last(self):
        self._auth(self.owner)
        results = self.client.get(self._url()).data["results"]
        valuations = [
            Decimal(r["latest_valuation"]) if r["latest_valuation"] is not None else None
            for r in results
        ]
        non_null = [v for v in valuations if v is not None]
        null_count = sum(1 for v in valuations if v is None)
        # All non-null values appear before nulls
        null_start = len(valuations) - null_count
        self.assertTrue(all(v is None for v in valuations[null_start:]))
        # Non-null portion is sorted descending
        self.assertEqual(non_null, sorted(non_null, reverse=True))

    # ── Filters ───────────────────────────────────────────────────────────────

    def test_branch_filter(self):
        self._auth(self.owner)
        response = self.client.get(f"{self._url()}?branch={self.branch_b.id}")
        self.assertEqual(response.status_code, 200)
        results = response.data["results"]
        for row in results:
            self.assertEqual(str(row["branch_id"]), str(self.branch_b.id))

    def test_search_filter_by_name(self):
        self._auth(self.owner)
        response = self.client.get(f"{self._url()}?search=Alpha")
        self.assertEqual(response.status_code, 200)
        results = response.data["results"]
        self.assertTrue(len(results) > 0)
        for row in results:
            self.assertEqual(str(row["item_id"]), str(self.item_a.id))

    def test_search_filter_by_sku(self):
        self._auth(self.owner)
        response = self.client.get(f"{self._url()}?search=SKU-BETA")
        self.assertEqual(response.status_code, 200)
        results = response.data["results"]
        self.assertTrue(len(results) > 0)
        for row in results:
            self.assertEqual(str(row["item_id"]), str(self.item_b.id))

    def test_filter_summary_reflects_filtered_results(self):
        self._auth(self.owner)
        response = self.client.get(f"{self._url()}?branch={self.branch_b.id}")
        results = response.data["results"]
        expected_latest = sum(
            Decimal(r["latest_valuation"]) for r in results if r["latest_valuation"] is not None
        )
        summary = response.data["summary"]
        self.assertEqual(Decimal(summary["total_latest_valuation"]), expected_latest)
        self.assertEqual(summary["branch_count"], 1)

    def test_empty_filter_returns_200_empty(self):
        """Filtering to a branch with no stock returns empty results and null totals."""
        self._auth(self.owner)
        response = self.client.get(f"{self._url()}?branch={self.other_branch.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])
        self.assertIsNone(response.data["summary"]["total_latest_valuation"])
        self.assertIsNone(response.data["summary"]["total_average_valuation"])
        self.assertEqual(response.data["summary"]["item_count"], 0)
        self.assertEqual(response.data["summary"]["branch_count"], 0)

    # ── Scoping / isolation ───────────────────────────────────────────────────

    def test_other_org_receipts_excluded(self):
        """Receipt lines from other_org must not affect Acme cost calculations."""
        self._auth(self.owner)
        results = self.client.get(self._url()).data["results"]
        for row in results:
            # No row should reference the other org's item
            self.assertNotEqual(str(row["item_id"]), str(self.other_item.id))

    def test_branch_scoped_receipt_lines(self):
        """
        item_a at branch_a must use only receipts for branch_a.
        The receipt at branch_b (cost 11.00) must not bleed into branch_a AVCO.
        branch_a AVCO = (4*10 + 6*12) / 10 = 11.20, not involving 11.00.
        """
        self._auth(self.owner)
        results = self.client.get(self._url()).data["results"]
        row = next(
            r for r in results
            if str(r["item_id"]) == str(self.item_a.id) and str(r["branch_id"]) == str(self.branch_a.id)
        )
        self.assertEqual(Decimal(row["average_unit_cost"]), Decimal("11.20"))

from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import BranchItem, MasterItem, OrgItem, StockOnHand, StockTake, StockTakeLine
from inventory.services import start_stock_take, submit_stock_take
from tenancy.models import Organization, OrganizationMember


class StockTakeBulkUpdateTests(APITestCase):
    def _create_org_item(self, organization, name, sku, *, item_name="", is_active=True):
        master_item = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.create(
            organization=organization,
            master_item=master_item,
            name=item_name,
            is_active=is_active,
        )

    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="bulk_owner", password="Passw0rd!")
        self.admin = user_model.objects.create_user(username="bulk_admin", password="Passw0rd!")
        self.staff = user_model.objects.create_user(username="bulk_staff", password="Passw0rd!")
        self.other = user_model.objects.create_user(username="bulk_other", password="Passw0rd!")

        self.org = Organization.objects.create(name="BulkCo", slug="bulk-co")
        self.other_org = Organization.objects.create(name="OtherCo", slug="bulk-other-co")

        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="BMAIN",
        )
        self.branch_two = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Second",
            code="BSEC",
        )
        self.other_branch = Branch.objects.for_org(self.other_org).create(
            organization=self.other_org,
            name="Other",
            code="BOTH",
        )

        OrganizationMember.objects.create(user=self.owner, organization=self.org, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.admin, organization=self.org, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(
            user=self.staff,
            organization=self.org,
            role="STAFF",
            is_active=True,
            assigned_branch=self.branch,
        )
        OrganizationMember.objects.create(user=self.other, organization=self.other_org, role="ADMIN", is_active=True)

        self.item_a = self._create_org_item(self.org, "Bulk Item A", "BLK-A", item_name="A Display")
        self.item_b = self._create_org_item(self.org, "Bulk Item B", "BLK-B")

        BranchItem.objects.create(branch=self.branch, org_item=self.item_a, is_active=True)
        BranchItem.objects.create(branch=self.branch, org_item=self.item_b, is_active=True)
        BranchItem.objects.create(branch=self.branch_two, org_item=self.item_a, is_active=True)

        StockOnHand.objects.create(
            organization=self.org,
            branch=self.branch,
            item=self.item_a,
            quantity=Decimal("8.0000"),
        )
        StockOnHand.objects.create(
            organization=self.org,
            branch=self.branch,
            item=self.item_b,
            quantity=Decimal("3.0000"),
        )
        StockOnHand.objects.create(
            organization=self.org,
            branch=self.branch_two,
            item=self.item_a,
            quantity=Decimal("1.0000"),
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _host(self):
        return f"{self.org.slug}.localhost:8000"

    def _base_url(self):
        return f"/api/orgs/{self.org.id}/stock-takes/"

    def _bulk_url(self, stock_take_id):
        return f"{self._base_url()}{stock_take_id}/lines/bulk-update/"

    def _make_in_progress_stock_take(self):
        stock_take = StockTake.objects.create(
            organization=self.org, branch=self.branch, created_by=self.owner
        )
        start_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()
        return stock_take

    # --- Access tests ---

    def test_owner_can_bulk_update(self):
        stock_take = self._make_in_progress_stock_take()
        line = stock_take.lines.first()
        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line.id, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_can_bulk_update(self):
        stock_take = self._make_in_progress_stock_take()
        line = stock_take.lines.first()
        self._auth(self.admin)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line.id, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)

    def test_staff_same_branch_can_bulk_update(self):
        stock_take = self._make_in_progress_stock_take()
        line = stock_take.lines.first()
        self._auth(self.staff)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line.id, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_gets_401(self):
        stock_take = self._make_in_progress_stock_take()
        line = stock_take.lines.first()
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line.id, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 401)

    def test_other_org_member_cannot_access(self):
        stock_take = self._make_in_progress_stock_take()
        line = stock_take.lines.first()
        self._auth(self.other)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line.id, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertIn(response.status_code, (403, 404))

    # --- Content tests ---

    def test_updates_counted_quantity_for_submitted_line_ids(self):
        stock_take = self._make_in_progress_stock_take()
        line_a = stock_take.lines.get(org_item=self.item_a)
        line_b = stock_take.lines.get(org_item=self.item_b)
        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {
                "lines": [
                    {"id": line_a.id, "counted_quantity": "5.0000"},
                    {"id": line_b.id, "counted_quantity": "2.0000"},
                ]
            },
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)
        line_a.refresh_from_db()
        line_b.refresh_from_db()
        self.assertEqual(line_a.counted_quantity, Decimal("5.0000"))
        self.assertEqual(line_b.counted_quantity, Decimal("2.0000"))

    def test_accepts_null_counted_quantity_clears_count(self):
        stock_take = self._make_in_progress_stock_take()
        line_a = stock_take.lines.get(org_item=self.item_a)
        line_a.counted_quantity = Decimal("5.0000")
        line_a.save(update_fields=["counted_quantity"])
        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line_a.id, "counted_quantity": None}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)
        line_a.refresh_from_db()
        self.assertIsNone(line_a.counted_quantity)
        row = next(r for r in response.data if r["id"] == line_a.id)
        self.assertIsNone(row["counted_quantity"])

    def test_accepts_zero_counted_quantity(self):
        stock_take = self._make_in_progress_stock_take()
        line_a = stock_take.lines.get(org_item=self.item_a)
        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line_a.id, "counted_quantity": "0.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)
        line_a.refresh_from_db()
        self.assertEqual(line_a.counted_quantity, Decimal("0.0000"))

    def test_returns_all_lines_not_just_submitted(self):
        stock_take = self._make_in_progress_stock_take()
        line_a = stock_take.lines.get(org_item=self.item_a)
        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line_a.id, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_response_lines_in_same_order_as_detail_endpoint(self):
        stock_take = self._make_in_progress_stock_take()
        line_a = stock_take.lines.get(org_item=self.item_a)
        self._auth(self.owner)

        detail_response = self.client.get(
            f"{self._base_url()}{stock_take.id}/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(detail_response.status_code, 200)
        detail_ids = [r["id"] for r in detail_response.data["lines"]]

        bulk_response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line_a.id, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(bulk_response.status_code, 200)
        bulk_ids = [r["id"] for r in bulk_response.data]

        self.assertEqual(bulk_ids, detail_ids)

    def test_response_includes_updated_counted_quantity_and_variance(self):
        stock_take = self._make_in_progress_stock_take()
        line_a = stock_take.lines.get(org_item=self.item_a)
        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line_a.id, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)
        row = next(r for r in response.data if r["id"] == line_a.id)
        self.assertEqual(row["counted_quantity"], "5.0000")
        self.assertEqual(row["variance_preview"], "-3.0000")

    def test_subset_of_line_ids_only_updates_those_lines(self):
        stock_take = self._make_in_progress_stock_take()
        line_a = stock_take.lines.get(org_item=self.item_a)
        line_b = stock_take.lines.get(org_item=self.item_b)
        line_b.counted_quantity = Decimal("2.0000")
        line_b.save(update_fields=["counted_quantity"])

        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line_a.id, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)
        line_b.refresh_from_db()
        self.assertEqual(line_b.counted_quantity, Decimal("2.0000"))

    def test_duplicate_line_ids_last_occurrence_wins(self):
        stock_take = self._make_in_progress_stock_take()
        line_a = stock_take.lines.get(org_item=self.item_a)
        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {
                "lines": [
                    {"id": line_a.id, "counted_quantity": "3.0000"},
                    {"id": line_a.id, "counted_quantity": "7.0000"},
                ]
            },
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)
        line_a.refresh_from_db()
        self.assertEqual(line_a.counted_quantity, Decimal("7.0000"))

    def test_line_id_not_on_this_stock_take_returns_400(self):
        stock_take = self._make_in_progress_stock_take()
        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": 999999, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)

    def test_line_id_from_different_stock_take_same_org_returns_400(self):
        stock_take = self._make_in_progress_stock_take()
        # Use a different branch so the concurrent guard doesn't fire
        other_take = StockTake.objects.create(
            organization=self.org, branch=self.branch_two, created_by=self.owner
        )
        start_stock_take(other_take, self.owner)
        other_take.refresh_from_db()
        other_line = other_take.lines.first()
        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": other_line.id, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)

    def test_negative_counted_quantity_returns_400(self):
        stock_take = self._make_in_progress_stock_take()
        line_a = stock_take.lines.get(org_item=self.item_a)
        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line_a.id, "counted_quantity": "-1.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)

    def test_empty_lines_returns_400(self):
        stock_take = self._make_in_progress_stock_take()
        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": []},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)

    def test_lines_exceeds_1000_returns_400(self):
        stock_take = self._make_in_progress_stock_take()
        line_a = stock_take.lines.first()
        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line_a.id, "counted_quantity": "1.0000"}] * 1001},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)

    def test_draft_stock_take_returns_400(self):
        stock_take = StockTake.objects.create(
            organization=self.org, branch=self.branch, created_by=self.owner
        )
        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": 1, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("In Progress", str(response.data["detail"]))

    def test_pending_approval_stock_take_returns_400(self):
        stock_take = self._make_in_progress_stock_take()
        line = stock_take.lines.first()
        line.counted_quantity = Decimal("1.0000")
        line.save(update_fields=["counted_quantity"])
        submit_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()

        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line.id, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("In Progress", str(response.data["detail"]))

    def test_completed_stock_take_returns_400(self):
        stock_take = self._make_in_progress_stock_take()
        line = stock_take.lines.first()
        stock_take.status = StockTake.COMPLETED
        stock_take.save(update_fields=["status", "updated_at"])

        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line.id, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("In Progress", str(response.data["detail"]))

    def test_cancelled_stock_take_returns_400(self):
        stock_take = self._make_in_progress_stock_take()
        line = stock_take.lines.first()
        stock_take.status = StockTake.CANCELLED
        stock_take.save(update_fields=["status", "updated_at"])

        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {"lines": [{"id": line.id, "counted_quantity": "5.0000"}]},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("In Progress", str(response.data["detail"]))

    def test_transaction_invalid_id_no_lines_updated(self):
        stock_take = self._make_in_progress_stock_take()
        line_a = stock_take.lines.get(org_item=self.item_a)
        line_b = stock_take.lines.get(org_item=self.item_b)
        original_a = line_a.counted_quantity
        original_b = line_b.counted_quantity

        self._auth(self.owner)
        response = self.client.patch(
            self._bulk_url(stock_take.id),
            {
                "lines": [
                    {"id": line_a.id, "counted_quantity": "9.0000"},
                    {"id": 999999, "counted_quantity": "5.0000"},
                ]
            },
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)
        line_a.refresh_from_db()
        line_b.refresh_from_db()
        self.assertEqual(line_a.counted_quantity, original_a)
        self.assertEqual(line_b.counted_quantity, original_b)

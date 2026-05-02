from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import BranchItem, MasterItem, OrgItem, StockLedger, StockOnHand, StockTake, StockTakeLine
from inventory.services import (
    approve_stock_take,
    cancel_stock_take,
    record_stock_movement,
    reopen_stock_take,
    start_stock_take,
    submit_stock_take,
)
from tenancy.models import Organization, OrganizationMember


class StockTakeApiTests(APITestCase):
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
        self.owner = user_model.objects.create_user(username="stocktake_owner", password="Passw0rd!")
        self.admin = user_model.objects.create_user(username="stocktake_admin", password="Passw0rd!")
        self.staff = user_model.objects.create_user(username="stocktake_staff", password="Passw0rd!")
        self.other = user_model.objects.create_user(username="stocktake_other", password="Passw0rd!")

        self.org = Organization.objects.create(name="Acme", slug="stocktake-acme")
        self.other_org = Organization.objects.create(name="Globex", slug="stocktake-globex")

        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="MAIN",
        )
        self.branch_two = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Outlet",
            code="OUT",
        )
        self.other_branch = Branch.objects.for_org(self.other_org).create(
            organization=self.other_org,
            name="Other",
            code="OTH",
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

        self.item_a = self._create_org_item(self.org, "Item A", "ST-A", item_name="A Display")
        self.item_b = self._create_org_item(self.org, "Item B", "ST-B")
        self.item_c = self._create_org_item(self.org, "Item C", "ST-C")
        self.inactive_item = self._create_org_item(self.org, "Inactive", "ST-X", is_active=False)
        self.other_org_item = self._create_org_item(self.other_org, "Other Org", "OT-1")

        self.branch_item_a = BranchItem.objects.create(branch=self.branch, org_item=self.item_a, is_active=True)
        self.branch_item_b = BranchItem.objects.create(branch=self.branch, org_item=self.item_b, is_active=True)
        BranchItem.objects.create(branch=self.branch, org_item=self.inactive_item, is_active=True)
        BranchItem.objects.create(branch=self.branch_two, org_item=self.item_c, is_active=True)
        BranchItem.objects.create(branch=self.branch, org_item=self.item_c, is_active=False)

        record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=self.item_a,
            quantity=Decimal("8.0000"),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal("5.0000"),
            performed_by=self.owner,
            idempotency_key="stock-take-seed-a",
        )
        record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=self.item_b,
            quantity=Decimal("3.0000"),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal("7.0000"),
            performed_by=self.owner,
            idempotency_key="stock-take-seed-b",
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _host(self, slug=None):
        return f"{slug or self.org.slug}.localhost:8000"

    def _base_url(self):
        return f"/api/orgs/{self.org.id}/stock-takes/"

    def _create_stock_take(self, *, user=None, branch=None, notes=None):
        self._auth(user or self.owner)
        payload = {"branch": str((branch or self.branch).id)}
        if notes is not None:
            payload["notes"] = notes
        return self.client.post(self._base_url(), payload, format="json", HTTP_HOST=self._host())

    def _start_stock_take(self, stock_take, *, user=None):
        self._auth(user or self.owner)
        return self.client.post(
            f"{self._base_url()}{stock_take.id}/start/",
            format="json",
            HTTP_HOST=self._host(),
        )

    def _submit_stock_take(self, stock_take, *, user=None):
        self._auth(user or self.owner)
        return self.client.post(
            f"{self._base_url()}{stock_take.id}/submit/",
            format="json",
            HTTP_HOST=self._host(),
        )

    def _reopen_stock_take(self, stock_take, *, user=None):
        self._auth(user or self.owner)
        return self.client.post(
            f"{self._base_url()}{stock_take.id}/reopen/",
            format="json",
            HTTP_HOST=self._host(),
        )

    def _approve_stock_take(self, stock_take, *, user=None):
        self._auth(user or self.owner)
        return self.client.post(
            f"{self._base_url()}{stock_take.id}/approve/",
            format="json",
            HTTP_HOST=self._host(),
        )

    def _cancel_stock_take(self, stock_take, *, user=None):
        self._auth(user or self.owner)
        return self.client.post(
            f"{self._base_url()}{stock_take.id}/cancel/",
            format="json",
            HTTP_HOST=self._host(),
        )

    def test_create_permissions_and_defaults(self):
        owner_response = self._create_stock_take(user=self.owner, notes="Cycle count")
        self.assertEqual(owner_response.status_code, 201)
        self.assertEqual(owner_response.data["status"], StockTake.DRAFT)
        self.assertEqual(owner_response.data["notes"], "Cycle count")
        self.assertEqual(owner_response.data["created_by"]["id"], self.owner.id)

        admin_response = self._create_stock_take(user=self.admin)
        self.assertEqual(admin_response.status_code, 201)
        self.assertEqual(admin_response.data["notes"], "")

        self._auth(self.staff)
        staff_response = self.client.post(
            self._base_url(),
            {"branch": str(self.branch.id)},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(staff_response.status_code, 403)

    def test_create_rejects_branch_from_different_org(self):
        self._auth(self.owner)
        response = self.client.post(
            self._base_url(),
            {"branch": str(self.other_branch.id)},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["branch"][0], "Branch does not belong to this organisation.")

    def test_patch_notes_only_in_editable_statuses(self):
        stock_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.owner)

        self._auth(self.owner)
        draft_response = self.client.patch(
            f"{self._base_url()}{stock_take.id}/",
            {"notes": "Draft notes"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(draft_response.status_code, 200)

        start_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()
        progress_response = self.client.patch(
            f"{self._base_url()}{stock_take.id}/",
            {"notes": "In progress notes"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(progress_response.status_code, 200)

        line = stock_take.lines.first()
        line.counted_quantity = Decimal("1.0000")
        line.save(update_fields=["counted_quantity"])
        submit_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()
        pending_response = self.client.patch(
            f"{self._base_url()}{stock_take.id}/",
            {"notes": "Blocked"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(pending_response.status_code, 400)

        stock_take.status = StockTake.COMPLETED
        stock_take.save(update_fields=["status", "updated_at"])
        completed_response = self.client.patch(
            f"{self._base_url()}{stock_take.id}/",
            {"notes": "Still blocked"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(completed_response.status_code, 400)

        self._auth(self.staff)
        forbidden = self.client.patch(
            f"{self._base_url()}{stock_take.id}/",
            {"notes": "Staff"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_patch_notes_rejects_extra_fields(self):
        stock_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.owner)

        self._auth(self.owner)
        response = self.client.patch(
            f"{self._base_url()}{stock_take.id}/",
            {"notes": "Valid", "status": StockTake.COMPLETED},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["detail"]), "Only the notes field may be updated.")

    def test_start_creates_lines_and_sets_snapshot_quantities(self):
        response = self._create_stock_take(user=self.owner)
        stock_take = StockTake.objects.get(pk=response.data["id"])

        start_response = self._start_stock_take(stock_take, user=self.owner)
        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(start_response.data["status"], StockTake.IN_PROGRESS)
        self.assertEqual(start_response.data["started_by"]["id"], self.owner.id)
        self.assertIsNotNone(start_response.data["started_at"])

        lines = list(
            StockTakeLine.objects.filter(stock_take=stock_take)
            .order_by("org_item__master_item__sku")
            .select_related("org_item__master_item")
        )
        self.assertEqual([line.org_item_id for line in lines], [self.item_a.id, self.item_b.id])
        self.assertEqual(lines[0].snapshot_quantity, Decimal("8.0000"))
        self.assertEqual(lines[1].snapshot_quantity, Decimal("3.0000"))

        # Cancel the first take so the concurrent guard allows a second start on the same branch
        cancel_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()

        BranchItem.objects.filter(pk=self.branch_item_b.pk).delete()
        BranchItem.objects.create(branch=self.branch, org_item=self.item_b, is_active=True)
        other_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.owner)
        StockOnHand.objects.filter(branch=self.branch, item=self.item_b).delete()
        second_start = self._start_stock_take(other_take, user=self.admin)
        self.assertEqual(second_start.status_code, 200)
        line_b = StockTakeLine.objects.get(stock_take=other_take, org_item=self.item_b)
        self.assertEqual(line_b.snapshot_quantity, Decimal("0"))

    def test_start_rejects_invalid_cases_and_permissions(self):
        empty_branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Empty",
            code="EMP",
        )
        empty_take = StockTake.objects.create(organization=self.org, branch=empty_branch, created_by=self.owner)
        empty_response = self._start_stock_take(empty_take, user=self.owner)
        self.assertEqual(empty_response.status_code, 400)
        self.assertEqual(
            empty_response.data["detail"][0],
            "No active items found for this branch. Set up the branch item catalog before starting a count.",
        )

        active_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.owner)
        self._auth(self.staff)
        forbidden = self.client.post(
            f"{self._base_url()}{active_take.id}/start/",
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(forbidden.status_code, 403)

        active_take.status = StockTake.IN_PROGRESS
        active_take.save(update_fields=["status", "updated_at"])
        invalid_response = self._start_stock_take(active_take, user=self.owner)
        self.assertEqual(invalid_response.status_code, 400)

        active_take.status = StockTake.COMPLETED
        active_take.save(update_fields=["status", "updated_at"])
        completed_response = self._start_stock_take(active_take, user=self.owner)
        self.assertEqual(completed_response.status_code, 400)

    def test_submit_requires_counts_and_sets_metadata(self):
        stock_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.owner)

        self._auth(self.owner)
        draft_response = self.client.post(
            f"{self._base_url()}{stock_take.id}/submit/",
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(draft_response.status_code, 400)

        start_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()

        empty_submit = self._submit_stock_take(stock_take, user=self.owner)
        self.assertEqual(empty_submit.status_code, 400)
        self.assertEqual(
            empty_submit.data["detail"][0],
            "Cannot submit a stock take where no items have been counted. Enter at least one counted quantity before submitting.",
        )

        line = stock_take.lines.first()
        line.counted_quantity = Decimal("7.0000")
        line.save(update_fields=["counted_quantity"])

        submit_response = self._submit_stock_take(stock_take, user=self.admin)
        self.assertEqual(submit_response.status_code, 200)
        self.assertEqual(submit_response.data["status"], StockTake.PENDING_APPROVAL)
        self.assertEqual(submit_response.data["submitted_by"]["id"], self.admin.id)
        self.assertIsNotNone(submit_response.data["submitted_at"])

        self._auth(self.staff)
        forbidden = self.client.post(
            f"{self._base_url()}{stock_take.id}/submit/",
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_reopen_preserves_lines_and_clears_submission_fields(self):
        stock_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.owner)
        start_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()
        line = stock_take.lines.get(org_item=self.item_a)
        line.counted_quantity = Decimal("9.0000")
        line.save(update_fields=["counted_quantity"])
        submit_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()

        reopen_response = self._reopen_stock_take(stock_take, user=self.admin)
        self.assertEqual(reopen_response.status_code, 200)
        self.assertEqual(reopen_response.data["status"], StockTake.IN_PROGRESS)
        self.assertIsNone(reopen_response.data["submitted_by"])
        self.assertIsNone(reopen_response.data["submitted_at"])

        line.refresh_from_db()
        self.assertEqual(line.counted_quantity, Decimal("9.0000"))
        self.assertEqual(line.snapshot_quantity, Decimal("8.0000"))

        invalid_response = self._reopen_stock_take(stock_take, user=self.owner)
        self.assertEqual(invalid_response.status_code, 400)

        self._auth(self.staff)
        forbidden = self.client.post(
            f"{self._base_url()}{stock_take.id}/reopen/",
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_approve_posts_adjustments_using_live_stock(self):
        stock_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.owner)
        start_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()

        line_a = stock_take.lines.get(org_item=self.item_a)
        line_b = stock_take.lines.get(org_item=self.item_b)
        line_a.counted_quantity = Decimal("9.0000")
        line_a.save(update_fields=["counted_quantity"])
        line_b.counted_quantity = Decimal("3.0000")
        line_b.save(update_fields=["counted_quantity"])

        StockOnHand.objects.filter(branch=self.branch, item=self.item_a).update(quantity=Decimal("12.0000"))
        submit_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()

        approve_response = self._approve_stock_take(stock_take, user=self.admin)
        self.assertEqual(approve_response.status_code, 200)
        # line_a has a -3 adjustment (counted 9, live 12), so variances were posted
        self.assertEqual(approve_response.data["status"], StockTake.COMPLETED_WITH_VARIANCES)
        self.assertEqual(approve_response.data["approved_by"]["id"], self.admin.id)
        self.assertIsNotNone(approve_response.data["approved_at"])

        ledgers = list(StockLedger.objects.for_org(self.org).filter(reference_type="STOCK_TAKE"))
        self.assertEqual(len(ledgers), 1)
        ledger = ledgers[0]
        self.assertEqual(ledger.item_id, self.item_a.id)
        self.assertEqual(ledger.quantity, Decimal("-3.0000"))
        self.assertEqual(ledger.movement_type, StockLedger.MOVEMENT_ADJUSTMENT)
        self.assertEqual(ledger.reference_id, str(stock_take.id))
        self.assertEqual(ledger.performed_by_id, self.admin.id)

        item_a_soh = StockOnHand.objects.get(organization=self.org, branch=self.branch, item=self.item_a)
        item_b_soh = StockOnHand.objects.get(organization=self.org, branch=self.branch, item=self.item_b)
        self.assertEqual(item_a_soh.quantity, Decimal("9.0000"))
        self.assertEqual(item_b_soh.quantity, Decimal("3.0000"))

        no_submit_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.owner)
        start_stock_take(no_submit_take, self.owner)
        no_submit_take.refresh_from_db()
        invalid_response = self._approve_stock_take(no_submit_take, user=self.owner)
        self.assertEqual(invalid_response.status_code, 400)

        self._auth(self.staff)
        forbidden = self.client.post(
            f"{self._base_url()}{stock_take.id}/approve/",
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_cancel_valid_statuses_and_permissions(self):
        draft_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.owner)
        draft_response = self._cancel_stock_take(draft_take, user=self.owner)
        self.assertEqual(draft_response.status_code, 200)
        self.assertEqual(draft_response.data["status"], StockTake.CANCELLED)
        self.assertEqual(draft_response.data["cancelled_by"]["id"], self.owner.id)
        self.assertIsNotNone(draft_response.data["cancelled_at"])

        progress_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.owner)
        start_stock_take(progress_take, self.owner)
        progress_take.refresh_from_db()
        progress_response = self._cancel_stock_take(progress_take, user=self.admin)
        self.assertEqual(progress_response.status_code, 200)

        pending_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.owner)
        start_stock_take(pending_take, self.owner)
        pending_take.refresh_from_db()
        pending_line = pending_take.lines.first()
        pending_line.counted_quantity = Decimal("1.0000")
        pending_line.save(update_fields=["counted_quantity"])
        submit_stock_take(pending_take, self.owner)
        pending_take.refresh_from_db()
        pending_response = self._cancel_stock_take(pending_take, user=self.owner)
        self.assertEqual(pending_response.status_code, 200)

        completed_take = StockTake.objects.create(
            organization=self.org,
            branch=self.branch,
            status=StockTake.COMPLETED,
            created_by=self.owner,
        )
        completed_response = self._cancel_stock_take(completed_take, user=self.owner)
        self.assertEqual(completed_response.status_code, 400)

        completed_variances_take = StockTake.objects.create(
            organization=self.org,
            branch=self.branch,
            status=StockTake.COMPLETED_WITH_VARIANCES,
            created_by=self.owner,
        )
        completed_variances_response = self._cancel_stock_take(completed_variances_take, user=self.owner)
        self.assertEqual(completed_variances_response.status_code, 400)

        self._auth(self.staff)
        forbidden = self.client.post(
            f"{self._base_url()}{draft_take.id}/cancel/",
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_lines_endpoints_and_variance_shapes(self):
        stock_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.owner)
        start_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()
        line = stock_take.lines.get(org_item=self.item_a)
        line.counted_quantity = Decimal("9.5000")
        line.save(update_fields=["counted_quantity"])

        self._auth(self.staff)
        list_response = self.client.get(self._base_url(), HTTP_HOST=self._host())
        self.assertEqual(list_response.status_code, 200)
        self.assertNotIn("lines", list_response.data["results"][0])

        retrieve_response = self.client.get(
            f"{self._base_url()}{stock_take.id}/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(retrieve_response.status_code, 200)
        self.assertIn("lines", retrieve_response.data)

        lines_response = self.client.get(
            f"{self._base_url()}{stock_take.id}/lines/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(lines_response.status_code, 200)
        self.assertEqual(len(lines_response.data), 2)
        first_line = next(row for row in lines_response.data if str(row["org_item"]) == str(self.item_a.id))
        self.assertEqual(first_line["item_name"], "A Display")
        self.assertEqual(first_line["item_sku"], "ST-A")
        self.assertEqual(first_line["snapshot_quantity"], "8.0000")
        self.assertEqual(first_line["counted_quantity"], "9.5000")
        self.assertEqual(first_line["variance_preview"], "1.5000")

        second_line = next(row for row in lines_response.data if str(row["org_item"]) == str(self.item_b.id))
        self.assertIsNone(second_line["counted_quantity"])
        self.assertIsNone(second_line["variance_preview"])

    def test_staff_access_is_branch_scoped(self):
        branch_one_take = StockTake.objects.create(
            organization=self.org,
            branch=self.branch,
            created_by=self.owner,
        )
        branch_two_take = StockTake.objects.create(
            organization=self.org,
            branch=self.branch_two,
            created_by=self.owner,
        )

        self._auth(self.staff)
        list_response = self.client.get(self._base_url(), HTTP_HOST=self._host())
        self.assertEqual(list_response.status_code, 200)
        ids = {row["id"] for row in list_response.data["results"]}
        self.assertIn(str(branch_one_take.id), ids)
        self.assertNotIn(str(branch_two_take.id), ids)

        own_branch_retrieve = self.client.get(
            f"{self._base_url()}{branch_one_take.id}/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(own_branch_retrieve.status_code, 200)

        other_branch_retrieve = self.client.get(
            f"{self._base_url()}{branch_two_take.id}/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(other_branch_retrieve.status_code, 404)

    def test_update_line_permissions_and_validation(self):
        stock_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.owner)
        start_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()
        line = stock_take.lines.get(org_item=self.item_a)

        for user in (self.owner, self.admin, self.staff):
            self._auth(user)
            response = self.client.patch(
                f"{self._base_url()}{stock_take.id}/lines/{line.id}/",
                {"counted_quantity": "11.0000"},
                format="json",
                HTTP_HOST=self._host(),
            )
            self.assertEqual(response.status_code, 200)

        negative = self.client.patch(
            f"{self._base_url()}{stock_take.id}/lines/{line.id}/",
            {"counted_quantity": "-1.0000"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(negative.status_code, 400)
        self.assertEqual(negative.data["counted_quantity"][0], "counted_quantity cannot be negative.")

        clear = self.client.patch(
            f"{self._base_url()}{stock_take.id}/lines/{line.id}/",
            {"counted_quantity": None},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(clear.status_code, 200)
        self.assertIsNone(clear.data["counted_quantity"])

        line.refresh_from_db()
        line.counted_quantity = Decimal("2.0000")
        line.save(update_fields=["counted_quantity"])
        submit_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()
        pending = self.client.patch(
            f"{self._base_url()}{stock_take.id}/lines/{line.id}/",
            {"counted_quantity": "5.0000"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(pending.status_code, 400)

        stock_take.status = StockTake.COMPLETED
        stock_take.save(update_fields=["status", "updated_at"])
        completed = self.client.patch(
            f"{self._base_url()}{stock_take.id}/lines/{line.id}/",
            {"counted_quantity": "5.0000"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(completed.status_code, 400)

        missing = self.client.patch(
            f"{self._base_url()}{stock_take.id}/lines/not-an-int/",
            {"counted_quantity": "5.0000"},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(missing.status_code, 404)


class StockTakeServiceTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="svc_stocktake", password="Passw0rd!")
        self.org = Organization.objects.create(name="Svc Org", slug="svc-stocktake")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Svc Branch",
            code="SVC",
        )
        OrganizationMember.objects.create(user=self.user, organization=self.org, role="OWNER", is_active=True)

        self.item_a = OrgItem.objects.create(
            organization=self.org,
            master_item=MasterItem.objects.create(name="Svc A", sku="SVC-A"),
            name="",
            is_active=True,
        )
        self.item_b = OrgItem.objects.create(
            organization=self.org,
            master_item=MasterItem.objects.create(name="Svc B", sku="SVC-B"),
            name="",
            is_active=True,
        )
        BranchItem.objects.create(branch=self.branch, org_item=self.item_a, is_active=True)
        BranchItem.objects.create(branch=self.branch, org_item=self.item_b, is_active=True)
        record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=self.item_a,
            quantity=Decimal("4.0000"),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal("6.0000"),
            performed_by=self.user,
            idempotency_key="svc-stock-take-seed-a",
        )

    def test_start_submit_reopen_cancel_and_approve_use_row_locks(self):
        stock_take = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.user)

        with mock.patch(
            "inventory.services.StockTake.objects.select_for_update",
            wraps=StockTake.objects.select_for_update,
        ) as stock_take_lock:
            start_stock_take(stock_take, self.user)
        self.assertTrue(stock_take_lock.called)

        stock_take.refresh_from_db()
        stock_take.lines.filter(org_item=self.item_a).update(counted_quantity=Decimal("5.0000"))

        with mock.patch(
            "inventory.services.StockTake.objects.select_for_update",
            wraps=StockTake.objects.select_for_update,
        ) as stock_take_lock, mock.patch(
            "inventory.services.StockTakeLine.objects.select_for_update",
            wraps=StockTakeLine.objects.select_for_update,
        ) as line_lock:
            submit_stock_take(stock_take, self.user)
        self.assertTrue(stock_take_lock.called)
        self.assertTrue(line_lock.called)

        stock_take.refresh_from_db()
        with mock.patch(
            "inventory.services.StockTake.objects.select_for_update",
            wraps=StockTake.objects.select_for_update,
        ) as stock_take_lock:
            reopen_stock_take(stock_take, self.user)
        self.assertTrue(stock_take_lock.called)

        stock_take.refresh_from_db()
        with mock.patch(
            "inventory.services.StockTake.objects.select_for_update",
            wraps=StockTake.objects.select_for_update,
        ) as stock_take_lock:
            cancel_stock_take(stock_take, self.user)
        self.assertTrue(stock_take_lock.called)

        approvable = StockTake.objects.create(organization=self.org, branch=self.branch, created_by=self.user)
        start_stock_take(approvable, self.user)
        approvable.refresh_from_db()
        approvable.lines.filter(org_item=self.item_a).update(counted_quantity=Decimal("6.0000"))
        submit_stock_take(approvable, self.user)
        approvable.refresh_from_db()

        with mock.patch(
            "inventory.services.StockTake.objects.select_for_update",
            wraps=StockTake.objects.select_for_update,
        ) as stock_take_lock, mock.patch(
            "inventory.services.StockTakeLine.objects.select_for_update",
            wraps=StockTakeLine.objects.select_for_update,
        ) as line_lock, mock.patch(
            "inventory.services.StockOnHand.objects.select_for_update",
            wraps=StockOnHand.objects.select_for_update,
        ) as soh_lock:
            approve_stock_take(approvable, self.user)
        self.assertTrue(stock_take_lock.called)
        self.assertTrue(line_lock.called)
        self.assertTrue(soh_lock.called)

    def test_submit_rejects_stock_take_with_no_lines(self):
        stock_take = StockTake.objects.create(
            organization=self.org,
            branch=self.branch,
            created_by=self.user,
            status=StockTake.IN_PROGRESS,
        )
        with self.assertRaisesMessage(
            ValidationError,
            "Cannot submit a stock take with no line items. Start the stock take to generate lines first.",
        ):
            submit_stock_take(stock_take, self.user)

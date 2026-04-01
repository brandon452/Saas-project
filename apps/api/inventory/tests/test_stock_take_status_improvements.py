"""
Tests for stock take status improvements:
  1. reopened_by / reopened_at audit fields
  2. Concurrent stock take guard (one IN_PROGRESS per branch)
  3. snapshot_taken_at timestamp
  4. counted_lines_count / total_lines_count in API responses
  5. Approval error enrichment with item context
  6. save() skips full_clean() for partial field updates
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import BranchItem, InventoryCostState, MasterItem, OrgItem, StockOnHand, StockTake
from inventory.services import (
    approve_stock_take,
    cancel_stock_take,
    reopen_stock_take,
    start_stock_take,
    submit_stock_take,
)
from tenancy.models import Organization, OrganizationMember


class StockTakeImprovementsTests(APITestCase):
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
        self.owner = user_model.objects.create_user(username="imp_owner", password="Passw0rd!")
        self.admin = user_model.objects.create_user(username="imp_admin", password="Passw0rd!")

        self.org = Organization.objects.create(name="ImpCo", slug="imp-co")

        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Main", code="IMPMAIN"
        )
        self.branch_two = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Second", code="IMPSEC"
        )

        OrganizationMember.objects.create(
            user=self.owner, organization=self.org, role="OWNER", is_active=True
        )
        OrganizationMember.objects.create(
            user=self.admin, organization=self.org, role="ADMIN", is_active=True
        )

        self.item_a = self._create_org_item(self.org, "Imp Item A", "IMP-A")
        self.item_b = self._create_org_item(self.org, "Imp Item B", "IMP-B", item_name="B Display")

        BranchItem.objects.create(branch=self.branch, org_item=self.item_a, is_active=True)
        BranchItem.objects.create(branch=self.branch, org_item=self.item_b, is_active=True)
        BranchItem.objects.create(branch=self.branch_two, org_item=self.item_a, is_active=True)

        StockOnHand.objects.create(
            organization=self.org, branch=self.branch, item=self.item_a, quantity=Decimal("10.0000")
        )
        StockOnHand.objects.create(
            organization=self.org, branch=self.branch, item=self.item_b, quantity=Decimal("5.0000")
        )
        StockOnHand.objects.create(
            organization=self.org, branch=self.branch_two, item=self.item_a, quantity=Decimal("2.0000")
        )

        InventoryCostState.objects.create(
            organization=self.org, branch=self.branch, item=self.item_a,
            average_unit_cost=Decimal("10.0000"), latest_unit_cost=Decimal("10.0000"),
        )
        InventoryCostState.objects.create(
            organization=self.org, branch=self.branch, item=self.item_b,
            average_unit_cost=Decimal("10.0000"), latest_unit_cost=Decimal("10.0000"),
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _host(self):
        return f"{self.org.slug}.localhost:8000"

    def _base_url(self):
        return f"/api/orgs/{self.org.id}/stock-takes/"

    def _make_stock_take(self, branch=None):
        return StockTake.objects.create(
            organization=self.org,
            branch=branch or self.branch,
            created_by=self.owner,
        )

    def _make_in_progress(self, branch=None):
        st = self._make_stock_take(branch=branch)
        start_stock_take(st, self.owner)
        st.refresh_from_db()
        return st

    # -----------------------------------------------------------------------
    # 1. reopened_by / reopened_at audit fields
    # -----------------------------------------------------------------------

    def test_reopen_sets_reopened_by_and_reopened_at(self):
        st = self._make_in_progress()
        line = st.lines.first()
        line.counted_quantity = Decimal("1.0000")
        line.save(update_fields=["counted_quantity"])
        submit_stock_take(st, self.owner)
        st.refresh_from_db()

        before = timezone.now()
        reopen_stock_take(st, self.admin)
        after = timezone.now()

        st.refresh_from_db()
        self.assertEqual(st.reopened_by_id, self.admin.id)
        self.assertIsNotNone(st.reopened_at)
        self.assertGreaterEqual(st.reopened_at, before)
        self.assertLessEqual(st.reopened_at, after)

    def test_reopen_response_includes_reopened_fields(self):
        st = self._make_in_progress()
        line = st.lines.first()
        line.counted_quantity = Decimal("1.0000")
        line.save(update_fields=["counted_quantity"])
        submit_stock_take(st, self.owner)
        st.refresh_from_db()

        self._auth(self.admin)
        response = self.client.post(
            f"{self._base_url()}{st.id}/reopen/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["reopened_by"]["id"], self.admin.id)
        self.assertIsNotNone(response.data["reopened_at"])

    def test_reopen_clears_submission_and_sets_reopen_fields(self):
        st = self._make_in_progress()
        line = st.lines.first()
        line.counted_quantity = Decimal("1.0000")
        line.save(update_fields=["counted_quantity"])
        submit_stock_take(st, self.owner)
        st.refresh_from_db()

        reopen_stock_take(st, self.admin)
        st.refresh_from_db()

        self.assertIsNone(st.submitted_by)
        self.assertIsNone(st.submitted_at)
        self.assertIsNotNone(st.reopened_by)
        self.assertIsNotNone(st.reopened_at)

    def test_fresh_stock_take_has_null_reopened_fields(self):
        st = self._make_stock_take()
        self.assertIsNone(st.reopened_by)
        self.assertIsNone(st.reopened_at)

    def test_list_serializer_includes_reopened_fields(self):
        self._make_stock_take()
        self._auth(self.owner)
        response = self.client.get(self._base_url(), HTTP_HOST=self._host())
        self.assertEqual(response.status_code, 200)
        first = response.data["results"][0]
        self.assertIn("reopened_by", first)
        self.assertIn("reopened_at", first)

    # -----------------------------------------------------------------------
    # 2. Concurrent stock take guard
    # -----------------------------------------------------------------------

    def test_cannot_start_second_stock_take_while_one_in_progress(self):
        self._make_in_progress()  # first take is IN_PROGRESS on self.branch

        second = self._make_stock_take()
        self._auth(self.owner)
        response = self.client.post(
            f"{self._base_url()}{second.id}/start/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("already in progress", response.data["detail"][0])

    def test_can_start_after_cancelling_in_progress_take(self):
        first = self._make_in_progress()
        cancel_stock_take(first, self.owner)

        second = self._make_stock_take()
        self._auth(self.owner)
        response = self.client.post(
            f"{self._base_url()}{second.id}/start/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)

    def test_can_start_after_completing_in_progress_take(self):
        first = self._make_in_progress()
        line = first.lines.first()
        line.counted_quantity = Decimal("5.0000")
        line.save(update_fields=["counted_quantity"])
        submit_stock_take(first, self.owner)
        first.refresh_from_db()
        approve_stock_take(first, self.owner)

        second = self._make_stock_take()
        self._auth(self.owner)
        response = self.client.post(
            f"{self._base_url()}{second.id}/start/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)

    def test_draft_on_same_branch_does_not_block_start(self):
        self._make_stock_take()  # DRAFT, not IN_PROGRESS

        second = self._make_stock_take()
        self._auth(self.owner)
        response = self.client.post(
            f"{self._base_url()}{second.id}/start/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)

    def test_in_progress_on_different_branch_does_not_block_start(self):
        self._make_in_progress(branch=self.branch_two)

        second = self._make_stock_take(branch=self.branch)
        self._auth(self.owner)
        response = self.client.post(
            f"{self._base_url()}{second.id}/start/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)

    # -----------------------------------------------------------------------
    # 3. snapshot_taken_at timestamp
    # -----------------------------------------------------------------------

    def test_start_sets_snapshot_taken_at(self):
        st = self._make_stock_take()
        self.assertIsNone(st.snapshot_taken_at)

        before = timezone.now()
        start_stock_take(st, self.owner)
        after = timezone.now()

        st.refresh_from_db()
        self.assertIsNotNone(st.snapshot_taken_at)
        self.assertGreaterEqual(st.snapshot_taken_at, before)
        self.assertLessEqual(st.snapshot_taken_at, after)

    def test_reopen_does_not_update_snapshot_taken_at(self):
        st = self._make_in_progress()
        st.refresh_from_db()
        original_snapshot_taken_at = st.snapshot_taken_at

        line = st.lines.first()
        line.counted_quantity = Decimal("1.0000")
        line.save(update_fields=["counted_quantity"])
        submit_stock_take(st, self.owner)
        st.refresh_from_db()
        reopen_stock_take(st, self.admin)
        st.refresh_from_db()

        self.assertEqual(st.snapshot_taken_at, original_snapshot_taken_at)

    def test_start_response_includes_snapshot_taken_at(self):
        st = self._make_stock_take()
        self._auth(self.owner)
        response = self.client.post(
            f"{self._base_url()}{st.id}/start/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["snapshot_taken_at"])

    def test_list_response_includes_snapshot_taken_at(self):
        self._make_stock_take()
        self._auth(self.owner)
        response = self.client.get(self._base_url(), HTTP_HOST=self._host())
        self.assertEqual(response.status_code, 200)
        self.assertIn("snapshot_taken_at", response.data["results"][0])

    # -----------------------------------------------------------------------
    # 4. counted_lines_count / total_lines_count
    # -----------------------------------------------------------------------

    def test_list_includes_line_counts(self):
        self._make_stock_take()
        self._auth(self.owner)
        response = self.client.get(self._base_url(), HTTP_HOST=self._host())
        self.assertEqual(response.status_code, 200)
        first = response.data["results"][0]
        self.assertIn("total_lines_count", first)
        self.assertIn("counted_lines_count", first)

    def test_draft_has_zero_line_counts(self):
        self._make_stock_take()
        self._auth(self.owner)
        response = self.client.get(self._base_url(), HTTP_HOST=self._host())
        self.assertEqual(response.status_code, 200)
        first = response.data["results"][0]
        self.assertEqual(first["total_lines_count"], 0)
        self.assertEqual(first["counted_lines_count"], 0)

    def test_line_counts_after_start(self):
        st = self._make_in_progress()
        self._auth(self.owner)
        response = self.client.get(
            f"{self._base_url()}{st.id}/", HTTP_HOST=self._host()
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_lines_count"], 2)
        self.assertEqual(response.data["counted_lines_count"], 0)

    def test_counted_lines_count_increments_as_lines_are_counted(self):
        st = self._make_in_progress()
        line_a = st.lines.get(org_item=self.item_a)
        line_a.counted_quantity = Decimal("3.0000")
        line_a.save(update_fields=["counted_quantity"])

        self._auth(self.owner)
        response = self.client.get(
            f"{self._base_url()}{st.id}/", HTTP_HOST=self._host()
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_lines_count"], 2)
        self.assertEqual(response.data["counted_lines_count"], 1)

    def test_line_counts_in_list_and_detail_are_consistent(self):
        st = self._make_in_progress()
        line = st.lines.first()
        line.counted_quantity = Decimal("1.0000")
        line.save(update_fields=["counted_quantity"])

        self._auth(self.owner)
        list_response = self.client.get(self._base_url(), HTTP_HOST=self._host())
        detail_response = self.client.get(
            f"{self._base_url()}{st.id}/", HTTP_HOST=self._host()
        )
        list_row = next(r for r in list_response.data["results"] if str(r["id"]) == str(st.id))
        self.assertEqual(list_row["total_lines_count"], detail_response.data["total_lines_count"])
        self.assertEqual(list_row["counted_lines_count"], detail_response.data["counted_lines_count"])

    # -----------------------------------------------------------------------
    # 5. Approval error enrichment
    # -----------------------------------------------------------------------

    def test_approval_error_includes_item_sku_and_name(self):
        from django.core.exceptions import ValidationError as DjangoValidationError

        st = self._make_in_progress()
        line_a = st.lines.get(org_item=self.item_a)
        line_a.counted_quantity = Decimal("5.0000")
        line_a.save(update_fields=["counted_quantity"])
        submit_stock_take(st, self.owner)
        st.refresh_from_db()

        with mock.patch(
            "inventory.services.record_stock_movement",
            side_effect=DjangoValidationError("Insufficient stock. Available: 0, requested: 5."),
        ):
            with self.assertRaises(DjangoValidationError) as ctx:
                approve_stock_take(st, self.owner)

        message = " ".join(ctx.exception.messages)
        self.assertIn("IMP-A", message)

    def test_approval_success_not_affected_by_enrichment(self):
        st = self._make_in_progress()
        line_a = st.lines.get(org_item=self.item_a)
        line_b = st.lines.get(org_item=self.item_b)
        line_a.counted_quantity = Decimal("10.0000")
        line_b.counted_quantity = Decimal("5.0000")
        line_a.save(update_fields=["counted_quantity"])
        line_b.save(update_fields=["counted_quantity"])
        submit_stock_take(st, self.owner)
        st.refresh_from_db()

        approve_stock_take(st, self.owner)
        st.refresh_from_db()
        # counted matches live exactly — no adjustments → COMPLETED (no variances)
        self.assertEqual(st.status, StockTake.COMPLETED)

    # -----------------------------------------------------------------------
    # COMPLETED vs COMPLETED_WITH_VARIANCES
    # -----------------------------------------------------------------------

    def test_approve_with_variances_sets_completed_with_variances(self):
        st = self._make_in_progress()
        line_a = st.lines.get(org_item=self.item_a)
        # counted=7, live=10 → adjustment=-3
        line_a.counted_quantity = Decimal("7.0000")
        line_a.save(update_fields=["counted_quantity"])
        submit_stock_take(st, self.owner)
        st.refresh_from_db()

        approve_stock_take(st, self.owner)
        st.refresh_from_db()
        self.assertEqual(st.status, StockTake.COMPLETED_WITH_VARIANCES)

    def test_approve_without_variances_sets_completed(self):
        st = self._make_in_progress()
        line_a = st.lines.get(org_item=self.item_a)
        line_b = st.lines.get(org_item=self.item_b)
        # counted matches live exactly
        line_a.counted_quantity = Decimal("10.0000")
        line_b.counted_quantity = Decimal("5.0000")
        line_a.save(update_fields=["counted_quantity"])
        line_b.save(update_fields=["counted_quantity"])
        submit_stock_take(st, self.owner)
        st.refresh_from_db()

        approve_stock_take(st, self.owner)
        st.refresh_from_db()
        self.assertEqual(st.status, StockTake.COMPLETED)

    def test_approve_response_reflects_correct_status(self):
        st = self._make_in_progress()
        line_a = st.lines.get(org_item=self.item_a)
        line_a.counted_quantity = Decimal("7.0000")  # variance
        line_a.save(update_fields=["counted_quantity"])
        submit_stock_take(st, self.owner)
        st.refresh_from_db()

        self._auth(self.owner)
        response = self.client.post(
            f"{self._base_url()}{st.id}/approve/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], StockTake.COMPLETED_WITH_VARIANCES)

    def test_completed_with_variances_is_terminal_cannot_cancel(self):
        from inventory.models import StockTake as ST
        st = ST.objects.create(
            organization=self.org,
            branch=self.branch,
            status=ST.COMPLETED_WITH_VARIANCES,
            created_by=self.owner,
        )
        self._auth(self.owner)
        response = self.client.post(
            f"{self._base_url()}{st.id}/cancel/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)

    def test_completed_with_variances_cannot_be_started_again(self):
        from inventory.models import StockTake as ST
        other = ST.objects.create(
            organization=self.org,
            branch=self.branch,
            status=ST.COMPLETED_WITH_VARIANCES,
            created_by=self.owner,
        )
        # Starting a new stock take on same branch should be fine (prior is terminal)
        new_take = self._make_stock_take()
        self._auth(self.owner)
        response = self.client.post(
            f"{self._base_url()}{new_take.id}/start/",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 200)
        _ = other  # referenced to confirm it exists

    # -----------------------------------------------------------------------
    # 6. save() skips full_clean() for partial field updates
    # -----------------------------------------------------------------------

    def test_partial_save_does_not_call_full_clean(self):
        st = self._make_stock_take()
        with mock.patch.object(StockTake, "full_clean") as mock_clean:
            st.save(update_fields=["notes", "updated_at"])
        mock_clean.assert_not_called()

    def test_full_save_still_calls_full_clean(self):
        st = self._make_stock_take()
        with mock.patch.object(StockTake, "full_clean") as mock_clean:
            st.save()
        mock_clean.assert_called_once()

    def test_save_with_branch_in_update_fields_calls_full_clean(self):
        st = self._make_stock_take()
        with mock.patch.object(StockTake, "full_clean") as mock_clean:
            st.save(update_fields=["branch", "updated_at"])
        mock_clean.assert_called_once()

    def test_save_with_organization_in_update_fields_calls_full_clean(self):
        st = self._make_stock_take()
        with mock.patch.object(StockTake, "full_clean") as mock_clean:
            st.save(update_fields=["organization", "updated_at"])
        mock_clean.assert_called_once()

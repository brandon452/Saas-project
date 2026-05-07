from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import BranchItem, MasterItem, OrgItem, StockTake
from inventory.services import (
    approve_stock_take,
    generate_cycle_count,
    get_org_local_today,
    start_stock_take,
    submit_stock_take,
)
from tenancy.models import Organization, OrganizationMember


class CycleCountTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="cycle_owner", password="Passw0rd!")
        self.admin = user_model.objects.create_user(username="cycle_admin", password="Passw0rd!")
        self.staff = user_model.objects.create_user(username="cycle_staff", password="Passw0rd!")

        self.org = Organization.objects.create(name="Cycle Org", slug="cycle-org")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="CYC",
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

        self.item_a = OrgItem.objects.create(
            organization=self.org,
            master_item=MasterItem.objects.create(name="Cycle A", sku="CYC-A"),
            is_active=True,
        )
        self.item_b = OrgItem.objects.create(
            organization=self.org,
            master_item=MasterItem.objects.create(name="Cycle B", sku="CYC-B"),
            is_active=True,
        )

        self.branch_item_a = BranchItem.objects.create(
            branch=self.branch,
            org_item=self.item_a,
            is_active=True,
            item_class=BranchItem.CLASS_A,
        )
        self.branch_item_b = BranchItem.objects.create(
            branch=self.branch,
            org_item=self.item_b,
            is_active=True,
            item_class=BranchItem.CLASS_A,
        )

    def _host(self):
        return f"{self.org.slug}.localhost:8000"

    def _generate_url(self):
        return f"/api/orgs/{self.org.id}/stock-takes/generate-cycle/"

    def _stock_takes_url(self):
        return f"/api/orgs/{self.org.id}/stock-takes/"

    def _generate_payload(self):
        return {
            "branch_id": str(self.branch.id),
            "cycle_item_class": BranchItem.CLASS_A,
        }

    def test_generate_cycle_create_then_idempotent(self):
        self.client.force_authenticate(user=self.owner)

        first = self.client.post(
            self._generate_url(),
            self._generate_payload(),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(first.status_code, 201)
        self.assertTrue(first.data["created"])
        self.assertEqual(first.data["generated_line_count"], 2)

        stock_take_id = first.data["id"]
        first_line_ids = sorted(line["id"] for line in first.data["lines"])

        second = self.client.post(
            self._generate_url(),
            self._generate_payload(),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.data["created"])
        self.assertEqual(second.data["generated_line_count"], 0)
        self.assertEqual(second.data["id"], stock_take_id)
        second_line_ids = sorted(line["id"] for line in second.data["lines"])
        self.assertEqual(first_line_ids, second_line_ids)

    def test_generate_cycle_returns_400_for_existing_non_draft(self):
        self.client.force_authenticate(user=self.owner)
        created = self.client.post(
            self._generate_url(),
            self._generate_payload(),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(created.status_code, 201)

        stock_take = StockTake.objects.get(pk=created.data["id"])
        start_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()
        stock_take.refresh_from_db()

        replay = self.client.post(
            self._generate_url(),
            self._generate_payload(),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(replay.status_code, 400)

    def test_generate_cycle_reuses_cancelled_cycle_as_new_draft(self):
        self.client.force_authenticate(user=self.owner)
        created = self.client.post(
            self._generate_url(),
            self._generate_payload(),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(created.status_code, 201)
        stock_take = StockTake.objects.get(pk=created.data["id"])
        stock_take.status = StockTake.CANCELLED
        stock_take.save(update_fields=["status", "updated_at"])

        regenerated = self.client.post(
            self._generate_url(),
            self._generate_payload(),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(regenerated.status_code, 201)
        self.assertEqual(regenerated.data["id"], created.data["id"])
        self.assertTrue(regenerated.data["created"])
        self.assertEqual(regenerated.data["status"], StockTake.DRAFT)

    def test_generate_cycle_forbidden_for_staff(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            self._generate_url(),
            self._generate_payload(),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 403)

    def test_generate_cycle_blocked_when_full_in_progress(self):
        self.client.force_authenticate(user=self.owner)
        full_create = self.client.post(
            self._stock_takes_url(),
            {"branch": str(self.branch.id)},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(full_create.status_code, 201)
        full_take = StockTake.objects.get(pk=full_create.data["id"])
        start_stock_take(full_take, self.owner)

        response = self.client.post(
            self._generate_url(),
            self._generate_payload(),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)

    def test_cycle_approval_advances_due_dates_for_counted_lines_only(self):
        self.client.force_authenticate(user=self.owner)
        created = self.client.post(
            self._generate_url(),
            self._generate_payload(),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(created.status_code, 201)

        stock_take = StockTake.objects.get(pk=created.data["id"])
        start_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()

        line_a = stock_take.lines.get(org_item=self.item_a)
        line_b = stock_take.lines.get(org_item=self.item_b)
        line_a.counted_quantity = Decimal("0.0000")
        line_a.save(update_fields=["counted_quantity"])
        line_b.counted_quantity = None
        line_b.save(update_fields=["counted_quantity"])

        submit_stock_take(stock_take, self.owner)
        stock_take.refresh_from_db()
        approve_stock_take(stock_take, self.owner)

        self.branch_item_a.refresh_from_db()
        self.branch_item_b.refresh_from_db()

        expected_due = timezone.now().date() + timedelta(days=7)
        self.assertEqual(self.branch_item_a.next_cycle_count_date, expected_due)
        self.assertIsNone(self.branch_item_b.next_cycle_count_date)

    def test_generate_cycle_when_no_items_due_creates_empty_cycle_stock_take(self):
        self.branch_item_a.next_cycle_count_date = timezone.now().date() + timedelta(days=5)
        self.branch_item_b.next_cycle_count_date = timezone.now().date() + timedelta(days=5)
        self.branch_item_a.save(update_fields=["next_cycle_count_date"])
        self.branch_item_b.save(update_fields=["next_cycle_count_date"])

        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            self._generate_url(),
            self._generate_payload(),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["created"])
        self.assertEqual(response.data["generated_line_count"], 0)
        self.assertEqual(response.data["lines"], [])

    def test_generate_cycle_filters_due_items_by_item_class(self):
        self.branch_item_b.item_class = BranchItem.CLASS_B
        self.branch_item_b.save(update_fields=["item_class"])

        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            self._generate_url(),
            self._generate_payload(),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["generated_line_count"], 1)
        line_item_ids = {str(line["org_item"]) for line in response.data["lines"]}
        self.assertEqual(line_item_ids, {str(self.item_a.id)})

    def test_get_org_local_today_uses_org_timezone_boundary(self):
        self.org.default_timezone = "Asia/Singapore"
        self.org.save(update_fields=["default_timezone"])
        mocked_now = datetime(2026, 1, 1, 16, 30, tzinfo=dt_timezone.utc)
        with patch("inventory.services.timezone.now", return_value=mocked_now):
            local_day = get_org_local_today(self.org)
        self.assertEqual(str(local_day), "2026-01-02")


class CycleCountConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="cycle_owner_conc", password="Passw0rd!")
        self.org = Organization.objects.create(name="Cycle Conc Org", slug="cycle-conc-org")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="CYC-CONC",
        )
        OrganizationMember.objects.create(user=self.owner, organization=self.org, role="OWNER", is_active=True)
        self.item_a = OrgItem.objects.create(
            organization=self.org,
            master_item=MasterItem.objects.create(name="Cycle Conc A", sku="CYCC-A"),
            is_active=True,
        )
        self.item_b = OrgItem.objects.create(
            organization=self.org,
            master_item=MasterItem.objects.create(name="Cycle Conc B", sku="CYCC-B"),
            is_active=True,
        )
        BranchItem.objects.create(
            branch=self.branch,
            org_item=self.item_a,
            is_active=True,
            item_class=BranchItem.CLASS_A,
        )
        BranchItem.objects.create(
            branch=self.branch,
            org_item=self.item_b,
            is_active=True,
            item_class=BranchItem.CLASS_A,
        )

    def test_concurrent_generate_cycle_returns_single_created(self):
        scheduled_for = timezone.now().date()
        results = []

        def worker():
            close_old_connections()
            try:
                try:
                    stock_take, created, generated_line_count = generate_cycle_count(
                        org=self.org,
                        branch=self.branch,
                        cycle_item_class=BranchItem.CLASS_A,
                        scheduled_for=scheduled_for,
                        performed_by=self.owner,
                    )
                except (ValidationError, IntegrityError):
                    stock_take = StockTake.objects.get(
                        organization=self.org,
                        branch=self.branch,
                        stock_take_type=StockTake.TYPE_CYCLE,
                        cycle_item_class=BranchItem.CLASS_A,
                        scheduled_for=scheduled_for,
                    )
                    created = False
                    generated_line_count = 0
                results.append((str(stock_take.id), created, generated_line_count))
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(lambda _: worker(), range(2)))
        close_old_connections()
        connections.close_all()

        self.assertEqual(len(results), 2)
        ids = {row[0] for row in results}
        self.assertEqual(len(ids), 1)
        created_count = sum(1 for _, created, _ in results if created)
        self.assertEqual(created_count, 1)
        line_counts = sorted(row[2] for row in results)
        self.assertEqual(line_counts, [0, 2])

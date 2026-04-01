from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import InventoryClosePeriod, InventoryCloseSnapshot, InventoryCostState, MasterItem, OrgItem, StockOnHand
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


class StockValuationApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="sv_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="sv_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="sv_staff", password="Passw0rd!")
        self.parent_admin = User.objects.create_user(username="sv_parent_admin", password="Passw0rd!")
        self.parent_viewer = User.objects.create_user(username="sv_parent_viewer", password="Passw0rd!")

        self.org = Organization.objects.create(name="SV Acme", slug="sv-acme")
        OrganizationMember.objects.create(user=self.owner, organization=self.org, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.admin, organization=self.org, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.staff, organization=self.org, role="STAFF", is_active=True)
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

        self.branch_a = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Branch A",
            code="SVA",
        )
        self.branch_b = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Branch B",
            code="SVB",
        )
        self.item_a = self._create_item("Alpha Widget", "SKU-ALPHA")
        self.item_b = self._create_item("Beta Gadget", "SKU-BETA")
        self.item_null = self._create_item("Gamma Thing", "SKU-GAMMA")

        StockOnHand.objects.create(
            organization=self.org,
            branch=self.branch_a,
            item=self.item_a,
            quantity=Decimal("10.0000"),
        )
        StockOnHand.objects.create(
            organization=self.org,
            branch=self.branch_b,
            item=self.item_b,
            quantity=Decimal("5.0000"),
        )
        StockOnHand.objects.create(
            organization=self.org,
            branch=self.branch_a,
            item=self.item_null,
            quantity=Decimal("2.0000"),
        )

        InventoryCostState.objects.create(
            organization=self.org,
            branch=self.branch_a,
            item=self.item_a,
            average_unit_cost=Decimal("11.2000"),
            latest_unit_cost=Decimal("12.0000"),
        )
        InventoryCostState.objects.create(
            organization=self.org,
            branch=self.branch_b,
            item=self.item_b,
            average_unit_cost=Decimal("8.0000"),
            latest_unit_cost=Decimal("9.5000"),
        )
        InventoryCostState.objects.create(
            organization=self.org,
            branch=self.branch_a,
            item=self.item_null,
            average_unit_cost=None,
            latest_unit_cost=None,
        )

        self.closed_period = InventoryClosePeriod.objects.create(
            organization=self.org,
            start_date="2026-03-01",
            end_date="2026-03-31",
            status=InventoryClosePeriod.CLOSED,
        )
        InventoryCloseSnapshot.objects.create(
            organization=self.org,
            period=self.closed_period,
            branch=self.branch_a,
            item=self.item_a,
            quantity_on_hand=Decimal("7.0000"),
            average_unit_cost=Decimal("10.0000"),
            latest_unit_cost=Decimal("11.0000"),
            average_valuation=Decimal("70.0000"),
            latest_valuation=Decimal("77.0000"),
            valuation_basis="AVCO",
        )

    def _create_item(self, name, sku):
        return OrgItem.objects.create(
            organization=self.org,
            master_item=MasterItem.objects.create(name=name, sku=sku),
            name=name,
            is_active=True,
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _url(self):
        return f"/api/orgs/{self.org.id}/reports/stock-valuation/"

    def test_access_rules(self):
        for user, expected in (
            (self.owner, 200),
            (self.admin, 200),
            (self.staff, 403),
            (self.parent_admin, 200),
            (self.parent_viewer, 200),
        ):
            self._auth(user)
            response = self.client.get(self._url())
            self.assertEqual(response.status_code, expected)

    def test_live_valuation_reads_inventory_cost_state(self):
        self._auth(self.owner)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("summary", response.data)
        self.assertIn("results", response.data)

        row = next(r for r in response.data["results"] if str(r["item_id"]) == str(self.item_a.id))
        self.assertEqual(Decimal(row["average_unit_cost"]), Decimal("11.20"))
        self.assertEqual(Decimal(row["latest_unit_cost"]), Decimal("12.00"))
        self.assertEqual(Decimal(row["average_valuation"]), Decimal("112.00"))
        self.assertEqual(Decimal(row["latest_valuation"]), Decimal("120.00"))

        null_row = next(r for r in response.data["results"] if str(r["item_id"]) == str(self.item_null.id))
        self.assertIsNone(null_row["average_unit_cost"])
        self.assertIsNone(null_row["latest_unit_cost"])

    def test_closed_period_returns_authoritative_snapshot(self):
        self._auth(self.owner)
        response = self.client.get(f"{self._url()}?period_id={self.closed_period.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        row = response.data["results"][0]
        self.assertEqual(Decimal(row["quantity_on_hand"]), Decimal("7.0000"))
        self.assertEqual(Decimal(row["average_unit_cost"]), Decimal("10.00"))
        self.assertEqual(Decimal(row["latest_unit_cost"]), Decimal("11.00"))
        self.assertEqual(Decimal(row["average_valuation"]), Decimal("70.00"))
        self.assertEqual(Decimal(row["latest_valuation"]), Decimal("77.00"))

    def test_open_and_closing_periods_return_400(self):
        self._auth(self.owner)
        open_period = InventoryClosePeriod.objects.create(
            organization=self.org,
            start_date="2026-04-01",
            end_date="2026-04-30",
            status=InventoryClosePeriod.OPEN,
        )
        closing_period = InventoryClosePeriod.objects.create(
            organization=self.org,
            start_date="2026-05-01",
            end_date="2026-05-31",
            status=InventoryClosePeriod.CLOSING,
        )

        open_response = self.client.get(f"{self._url()}?period_id={open_period.id}")
        self.assertEqual(open_response.status_code, 400)
        self.assertEqual(
            open_response.data["detail"],
            "Period has not been closed; no authoritative snapshot exists.",
        )

        closing_response = self.client.get(f"{self._url()}?period_id={closing_period.id}")
        self.assertEqual(closing_response.status_code, 400)
        self.assertEqual(closing_response.data["detail"], "Period is currently closing.")

    def test_branch_and_search_filters_apply(self):
        self._auth(self.owner)
        branch_response = self.client.get(f"{self._url()}?branch={self.branch_b.id}")
        self.assertEqual(branch_response.status_code, 200)
        self.assertEqual(len(branch_response.data["results"]), 1)
        self.assertEqual(branch_response.data["results"][0]["branch_id"], str(self.branch_b.id))

        search_response = self.client.get(f"{self._url()}?search=SKU-ALPHA")
        self.assertEqual(search_response.status_code, 200)
        self.assertEqual(len(search_response.data["results"]), 1)
        self.assertEqual(search_response.data["results"][0]["item_id"], str(self.item_a.id))

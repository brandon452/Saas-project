from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import (
    BranchItem,
    InventoryClosePeriod,
    InventoryCostState,
    MasterItem,
    OrgItem,
    StockLedger,
    StockOnHand,
)
from inventory.services import record_stock_movement
from quick_sales.models import QuickSale
from quick_sales.services import create_quick_sale, void_quick_sale
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


class QuickSaleServiceTests(TransactionTestCase):
    reset_sequences = True

    def _create_org_item(self, organization, name, sku):
        master_item = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.for_org(organization).create(
            organization=organization,
            master_item=master_item,
        )

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="qs_service_user", password="Passw0rd!")
        self.org = Organization.objects.create(name="Quick Sale Org", slug="quick-sale-org")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="MAIN",
        )
        self.item_a = self._create_org_item(self.org, "Item A", "QS-A")
        self.item_b = self._create_org_item(self.org, "Item B", "QS-B")
        BranchItem.objects.create(branch=self.branch, org_item=self.item_a, is_active=True)
        BranchItem.objects.create(branch=self.branch, org_item=self.item_b, is_active=True)

    def _receipt(self, item, quantity, unit_cost, *, key, occurred_at=None):
        record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=item,
            quantity=Decimal(quantity),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal(unit_cost),
            performed_by=self.user,
            occurred_at=occurred_at,
            idempotency_key=key,
        )

    def test_create_quick_sale_reduces_stock_and_captures_unit_cost(self):
        self._receipt(self.item_a, "10.0000", "5.0000", key="seed-a")
        self._receipt(self.item_b, "4.0000", "7.5000", key="seed-b")

        sale = create_quick_sale(
            org=self.org,
            branch=self.branch,
            lines=[
                {"item": self.item_a, "quantity": Decimal("2.0000"), "unit_price": Decimal("8.0000")},
                {"item": self.item_b, "quantity": Decimal("1.0000"), "unit_price": Decimal("10.0000")},
            ],
            performed_by=self.user,
        )

        self.assertEqual(
            StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item_a).quantity,
            Decimal("8.0000"),
        )
        self.assertEqual(
            StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item_b).quantity,
            Decimal("3.0000"),
        )
        self.assertEqual(sale.lines.get(item=self.item_a).unit_cost, Decimal("5.0000"))
        self.assertEqual(sale.lines.get(item=self.item_b).unit_cost, Decimal("7.5000"))

    def test_create_quick_sale_rolls_back_if_any_line_fails(self):
        self._receipt(self.item_a, "1.0000", "5.0000", key="seed")

        with self.assertRaises(ValidationError):
            create_quick_sale(
                org=self.org,
                branch=self.branch,
                lines=[
                    {"item": self.item_a, "quantity": Decimal("1.0000"), "unit_price": Decimal("8.0000")},
                    {"item": self.item_b, "quantity": Decimal("1.0000"), "unit_price": Decimal("8.0000")},
                ],
                performed_by=self.user,
            )

        self.assertFalse(QuickSale.objects.for_org(self.org).exists())
        self.assertEqual(
            StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item_a).quantity,
            Decimal("1.0000"),
        )

    def test_create_quick_sale_requires_cost_basis_and_closed_period_blocks(self):
        StockOnHand.objects.create(
            organization=self.org,
            branch=self.branch,
            item=self.item_a,
            quantity=Decimal("2.0000"),
        )
        with self.assertRaises(ValidationError) as missing_cost:
            create_quick_sale(
                org=self.org,
                branch=self.branch,
                lines=[
                    {"item": self.item_a, "quantity": Decimal("1.0000"), "unit_price": Decimal("5.0000")},
                ],
                performed_by=self.user,
            )
        self.assertIn("No cost basis", str(missing_cost.exception))

        older = timezone.now() - timedelta(days=5)
        self._receipt(self.item_a, "5.0000", "5.0000", key="seed-closed", occurred_at=older)
        closed_date = timezone.now().date()
        InventoryClosePeriod.objects.create(
            organization=self.org,
            start_date=closed_date,
            end_date=closed_date,
            status=InventoryClosePeriod.CLOSED,
        )

        with self.assertRaises(ValidationError):
            create_quick_sale(
                org=self.org,
                branch=self.branch,
                lines=[
                    {"item": self.item_a, "quantity": Decimal("1.0000"), "unit_price": Decimal("5.0000")},
                ],
                occurred_at=timezone.now(),
                performed_by=self.user,
            )

    def test_create_quick_sale_defaults_occurred_at_to_now(self):
        self._receipt(self.item_a, "5.0000", "5.0000", key="seed-now")
        before = timezone.now()
        sale = create_quick_sale(
            org=self.org,
            branch=self.branch,
            lines=[
                {"item": self.item_a, "quantity": Decimal("1.0000"), "unit_price": Decimal("5.0000")},
            ],
            performed_by=self.user,
        )
        after = timezone.now()

        self.assertGreaterEqual(sale.occurred_at, before)
        self.assertLessEqual(sale.occurred_at, after)

    def test_create_quick_sale_rejects_future_occurred_at(self):
        self._receipt(self.item_a, "5.0000", "5.0000", key="seed-future")
        future_time = timezone.now() + timedelta(hours=2)

        with self.assertRaises(ValidationError):
            create_quick_sale(
                org=self.org,
                branch=self.branch,
                lines=[
                    {"item": self.item_a, "quantity": Decimal("1.0000"), "unit_price": Decimal("5.0000")},
                ],
                occurred_at=future_time,
                performed_by=self.user,
            )

    def test_void_quick_sale_restores_stock_preserves_cost_and_recomputes_avco(self):
        self._receipt(self.item_a, "10.0000", "10.0000", key="seed-1")
        sale = create_quick_sale(
            org=self.org,
            branch=self.branch,
            lines=[
                {"item": self.item_a, "quantity": Decimal("4.0000"), "unit_price": Decimal("15.0000")},
            ],
            performed_by=self.user,
        )
        self._receipt(self.item_a, "4.0000", "20.0000", key="seed-2")

        before_void = InventoryCostState.objects.get(
            organization=self.org,
            branch=self.branch,
            item=self.item_a,
        )
        self.assertEqual(before_void.average_unit_cost, Decimal("14.0000"))
        self.assertEqual(before_void.latest_unit_cost, Decimal("20.0000"))

        voided = void_quick_sale(self.org, sale, performed_by=self.user)

        self.assertEqual(voided.status, QuickSale.STATUS_VOIDED)
        self.assertEqual(
            StockOnHand.objects.for_org(self.org).get(branch=self.branch, item=self.item_a).quantity,
            Decimal("14.0000"),
        )

        reversal = (
            StockLedger.objects.for_org(self.org)
            .filter(reference_type="QUICK_SALE_VOID", reference_id=str(sale.id))
            .latest("created_at")
        )
        self.assertEqual(reversal.unit_cost, Decimal("10.0000"))
        self.assertEqual(reversal.value_delta, Decimal("40.0000"))

        after_void = InventoryCostState.objects.get(
            organization=self.org,
            branch=self.branch,
            item=self.item_a,
        )
        self.assertEqual(after_void.average_unit_cost, Decimal("12.8571"))
        self.assertEqual(after_void.latest_unit_cost, Decimal("20.0000"))

    def test_void_quick_sale_rejects_repeated_void_and_closed_today(self):
        self._receipt(self.item_a, "5.0000", "10.0000", key="seed-repeat")
        sale = create_quick_sale(
            org=self.org,
            branch=self.branch,
            lines=[
                {"item": self.item_a, "quantity": Decimal("1.0000"), "unit_price": Decimal("12.0000")},
            ],
            performed_by=self.user,
        )
        void_quick_sale(self.org, sale, performed_by=self.user)

        with self.assertRaises(ValidationError):
            void_quick_sale(self.org, sale, performed_by=self.user)

        sale_two = create_quick_sale(
            org=self.org,
            branch=self.branch,
            lines=[
                {"item": self.item_a, "quantity": Decimal("1.0000"), "unit_price": Decimal("12.0000")},
            ],
            performed_by=self.user,
        )
        today = timezone.now().date()
        InventoryClosePeriod.objects.create(
            organization=self.org,
            start_date=today,
            end_date=today,
            status=InventoryClosePeriod.CLOSED,
        )

        with self.assertRaises(ValidationError):
            void_quick_sale(self.org, sale_two, performed_by=self.user)


class QuickSaleApiTests(APITestCase):
    def _create_org_item(self, organization, name, sku):
        master_item = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.for_org(organization).create(
            organization=organization,
            master_item=master_item,
        )

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="qs_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="qs_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="qs_staff", password="Passw0rd!")
        self.parent = User.objects.create_user(username="qs_parent", password="Passw0rd!")

        self.org = Organization.objects.create(name="Quick Sale API", slug="quick-sale-api")
        self.other_org = Organization.objects.create(name="Other Quick Sale API", slug="other-quick-sale-api")
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Main",
            code="MAIN",
        )
        self.other_branch = Branch.objects.for_org(self.org).create(
            organization=self.org,
            name="Second",
            code="SECOND",
        )
        self.foreign_branch = Branch.objects.for_org(self.other_org).create(
            organization=self.other_org,
            name="Foreign",
            code="FOREIGN",
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
        ParentCompanyMember.objects.create(
            user=self.parent,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
        )

        self.item = self._create_org_item(self.org, "Quick Sale Item", "QS-ITEM")
        self.foreign_item = self._create_org_item(self.other_org, "Foreign Item", "QS-FOREIGN")
        BranchItem.objects.create(branch=self.branch, org_item=self.item, is_active=True)
        BranchItem.objects.create(branch=self.other_branch, org_item=self.item, is_active=False)
        record_stock_movement(
            org=self.org,
            branch=self.branch,
            item=self.item,
            quantity=Decimal("8.0000"),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal("10.0000"),
            performed_by=self.owner,
            idempotency_key="quick-sale-api-seed",
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _host(self, slug=None):
        return f"{slug or self.org.slug}.localhost:8000"

    def _base_url(self, org_id=None):
        return f"/api/orgs/{org_id or self.org.id}/quick-sales/"

    def _detail_url(self, sale_id, suffix="", org_id=None):
        return f"{self._base_url(org_id)}{sale_id}/{suffix}"

    def _payload(self, **overrides):
        payload = {
            "branch": str(self.branch.id),
            "customer_name": "",
            "notes": "",
            "lines": [
                {
                    "item": str(self.item.id),
                    "quantity": "1.0000",
                    "unit_price": "15.0000",
                }
            ],
        }
        payload.update(overrides)
        return payload

    def test_permissions_and_staff_branch_rule(self):
        for user, expected_status in (
            (self.owner, 201),
            (self.admin, 201),
            (self.staff, 201),
            (self.parent, 403),
        ):
            self._auth(user)
            response = self.client.post(
                self._base_url(),
                self._payload(),
                format="json",
                HTTP_HOST=self._host(),
            )
            self.assertEqual(response.status_code, expected_status)

        self._auth(self.staff)
        other_branch_response = self.client.post(
            self._base_url(),
            self._payload(branch=str(self.other_branch.id)),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(other_branch_response.status_code, 400)
        self.assertEqual(
            other_branch_response.data["branch"][0],
            "You can only record sales for your assigned branch.",
        )

    def test_api_rejects_future_occurred_at(self):
        self._auth(self.owner)
        future_time = (timezone.now() + timedelta(hours=2)).isoformat()
        response = self.client.post(
            self._base_url(),
            self._payload(occurred_at=future_time),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["occurred_at"][0],
            "Sale date and time cannot be in the future.",
        )

    def test_serializer_rejects_cross_org_item_and_disabled_branch_item(self):
        self._auth(self.owner)

        foreign_branch_response = self.client.post(
            self._base_url(),
            self._payload(branch=str(self.foreign_branch.id)),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(foreign_branch_response.status_code, 400)
        self.assertIn("branch", foreign_branch_response.data)

        foreign_item_response = self.client.post(
            self._base_url(),
            self._payload(
                lines=[{"item": str(self.foreign_item.id), "quantity": "1.0000", "unit_price": "10.0000"}]
            ),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(foreign_item_response.status_code, 400)
        self.assertIn("item", foreign_item_response.data["lines"][0])

        disabled_branch_item_response = self.client.post(
            self._base_url(),
            self._payload(branch=str(self.other_branch.id)),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(disabled_branch_item_response.status_code, 400)
        self.assertIn("lines[0].item", disabled_branch_item_response.data)

    def test_parent_can_list_and_retrieve_and_filters_apply(self):
        self._auth(self.owner)
        first = self.client.post(
            self._base_url(),
            self._payload(occurred_at="2026-01-15T10:00:00Z"),
            format="json",
            HTTP_HOST=self._host(),
        )
        second = self.client.post(
            self._base_url(),
            self._payload(occurred_at="2026-01-20T10:00:00Z"),
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        void_response = self.client.post(
            self._detail_url(second.data["id"], "void/"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(void_response.status_code, 200)

        self._auth(self.parent)
        filtered = self.client.get(
            f"{self._base_url()}?branch={self.branch.id}&status=VOIDED&from_date=2026-01-19&to_date=2026-01-21",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.data["count"], 1)
        self.assertEqual(filtered.data["results"][0]["id"], second.data["id"])

        retrieve = self.client.get(self._detail_url(first.data["id"]), HTTP_HOST=self._host())
        self.assertEqual(retrieve.status_code, 200)

    def test_void_permissions_and_api_does_not_expose_force_cost(self):
        self._auth(self.owner)
        created = self.client.post(
            self._base_url(),
            self._payload(),
            format="json",
            HTTP_HOST=self._host(),
        )
        sale_id = created.data["id"]

        self._auth(self.staff)
        staff_void = self.client.post(
            self._detail_url(sale_id, "void/"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(staff_void.status_code, 403)

        self._auth(self.admin)
        admin_void = self.client.post(
            self._detail_url(sale_id, "void/"),
            {},
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(admin_void.status_code, 200)
        self.assertEqual(admin_void.data["status"], QuickSale.STATUS_VOIDED)

        self._auth(self.owner)
        payload = self._payload(
            lines=[
                {
                    "item": str(self.item.id),
                    "quantity": "1.0000",
                    "unit_price": "10.0000",
                    "_force_unit_cost": "1.0000",
                }
            ]
        )
        response = self.client.post(
            self._base_url(),
            payload,
            format="json",
            HTTP_HOST=self._host(),
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["lines"][0]["unit_cost"], "10.0000")

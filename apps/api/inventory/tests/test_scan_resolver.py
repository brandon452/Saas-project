
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from branches.models import Branch
from inventory.models import (
    BranchItem,
    MasterItem,
    OrgItem,
    StockTake,
    StockTakeLine,
)
from inventory.services import start_stock_take
from tenancy.models import Organization, OrganizationMember


class ScanResolveViewTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="scan_owner", password="Passw0rd!")
        self.other_user = User.objects.create_user(username="scan_other", password="Passw0rd!")

        self.org = Organization.objects.create(name="ScanOrg", slug="scan-org")
        self.other_org = Organization.objects.create(name="OtherOrg", slug="scan-other-org")

        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Main", code="MAIN"
        )
        self.branch_b = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Outlet", code="OUT"
        )
        self.other_branch = Branch.objects.for_org(self.other_org).create(
            organization=self.other_org, name="Other", code="OTH"
        )

        OrganizationMember.objects.create(
            user=self.owner, organization=self.org, role="OWNER", is_active=True
        )
        OrganizationMember.objects.create(
            user=self.other_user, organization=self.other_org, role="OWNER", is_active=True
        )

        self.master = MasterItem.objects.create(name="Widget", sku="WGT-001")
        self.org_item = OrgItem.objects.create(
            organization=self.org,
            master_item=self.master,
            is_active=True,
            is_lot_tracked=False,
            is_expiry_tracked=False,
        )
        self.branch_item = BranchItem.objects.create(
            branch=self.branch, org_item=self.org_item, is_active=True
        )

    def _url(self, **params):
        base = f"/api/orgs/{self.org.id}/inventory/items/resolve-scan/"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            return f"{base}?{qs}"
        return base

    def _auth(self, user=None):
        self.client.force_authenticate(user=user or self.owner)

    # --- branch_required contract ---

    def test_missing_branch_id_returns_400_with_machine_code(self):
        self._auth()
        resp = self.client.get(self._url(code="WGT-001"))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "branch_required")

    def test_empty_branch_id_returns_400(self):
        self._auth()
        resp = self.client.get(self._url(code="WGT-001", branch_id=""))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "branch_required")

    # --- authentication ---

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self._url(code="WGT-001", branch_id=str(self.branch.id)))
        self.assertEqual(resp.status_code, 401)

    # --- not_found outcomes ---

    def test_unknown_sku_returns_not_found(self):
        self._auth()
        resp = self.client.get(self._url(code="DOES-NOT-EXIST", branch_id=str(self.branch.id)))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["outcome"], "not_found")
        self.assertIsNone(resp.json()["item"])

    def test_empty_code_returns_not_found(self):
        self._auth()
        resp = self.client.get(self._url(code="", branch_id=str(self.branch.id)))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["outcome"], "not_found")

    def test_sku_from_another_orgs_parent_returns_not_found(self):
        MasterItem.objects.create(
            name="Other Widget",
            sku="OTHER-SKU",
            parent_company=self.other_org.parent_company,
        )
        self._auth()
        resp = self.client.get(self._url(code="OTHER-SKU", branch_id=str(self.branch.id)))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["outcome"], "not_found")

    def test_item_inactive_in_org_returns_not_found(self):
        self.org_item.is_active = False
        self.org_item.save(update_fields=["is_active"])
        self._auth()
        resp = self.client.get(self._url(code="WGT-001", branch_id=str(self.branch.id)))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["outcome"], "not_found")

    def test_branch_from_other_org_returns_not_found(self):
        self._auth()
        resp = self.client.get(self._url(code="WGT-001", branch_id=str(self.other_branch.id)))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["outcome"], "not_found")

    # --- not_enabled_at_branch ---

    def test_no_branch_item_returns_not_enabled_at_branch(self):
        self._auth()
        resp = self.client.get(self._url(code="WGT-001", branch_id=str(self.branch_b.id)))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["outcome"], "not_enabled_at_branch")
        self.assertIsNone(resp.json()["item"])

    def test_inactive_branch_item_returns_not_enabled_at_branch(self):
        self.branch_item.is_active = False
        self.branch_item.save(update_fields=["is_active"])
        self._auth()
        resp = self.client.get(self._url(code="WGT-001", branch_id=str(self.branch.id)))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["outcome"], "not_enabled_at_branch")

    # --- matched ---

    def test_matched_returns_correct_item_data(self):
        self._auth()
        resp = self.client.get(self._url(code="WGT-001", branch_id=str(self.branch.id)))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["outcome"], "matched")
        item = data["item"]
        self.assertEqual(item["org_item_id"], str(self.org_item.id))
        self.assertEqual(item["sku"], "WGT-001")
        self.assertEqual(item["name"], "Widget")
        self.assertFalse(item["is_lot_tracked"])
        self.assertFalse(item["is_expiry_tracked"])
        self.assertEqual(item["branch_item_id"], self.branch_item.id)

    def test_matched_is_case_insensitive(self):
        self._auth()
        for code in ("wgt-001", "Wgt-001", "WGT-001"):
            resp = self.client.get(self._url(code=code, branch_id=str(self.branch.id)))
            self.assertEqual(resp.json()["outcome"], "matched", msg=f"Failed for code: {code}")

    def test_matched_normalises_whitespace(self):
        self._auth()
        resp = self.client.get(self._url(code="  WGT-001  ", branch_id=str(self.branch.id)))
        self.assertEqual(resp.json()["outcome"], "matched")

    # --- stock-take context ---

    def _make_in_progress_stock_take(self):
        st = StockTake.objects.create(
            organization=self.org,
            branch=self.branch,
            status=StockTake.DRAFT,
        )
        start_stock_take(st, performed_by=self.owner)
        st.refresh_from_db()
        return st

    def test_stock_take_id_not_provided_no_line_data_in_response(self):
        self._auth()
        resp = self.client.get(self._url(code="WGT-001", branch_id=str(self.branch.id)))
        self.assertEqual(resp.json()["outcome"], "matched")
        self.assertNotIn("stock_take_line_id", resp.json()["item"])

    def test_not_in_count_when_item_absent_from_stock_take(self):
        st = self._make_in_progress_stock_take()
        # Remove the line so item is not in this take
        StockTakeLine.objects.filter(stock_take=st, org_item=self.org_item).delete()
        self._auth()
        resp = self.client.get(
            self._url(code="WGT-001", branch_id=str(self.branch.id), stock_take_id=str(st.id))
        )
        self.assertEqual(resp.json()["outcome"], "not_in_count")
        self.assertIsNotNone(resp.json()["item"])

    def test_matched_with_stock_take_line_data_when_item_in_take(self):
        st = self._make_in_progress_stock_take()
        line = StockTakeLine.objects.get(stock_take=st, org_item=self.org_item)
        self._auth()
        resp = self.client.get(
            self._url(code="WGT-001", branch_id=str(self.branch.id), stock_take_id=str(st.id))
        )
        data = resp.json()
        self.assertEqual(data["outcome"], "matched")
        self.assertEqual(data["item"]["stock_take_line_id"], line.id)
        self.assertIn("snapshot_quantity", data["item"])
        self.assertIn("counted_quantity", data["item"])

    def test_invalid_stock_take_id_returns_not_found(self):
        import uuid
        self._auth()
        resp = self.client.get(
            self._url(
                code="WGT-001",
                branch_id=str(self.branch.id),
                stock_take_id=str(uuid.uuid4()),
            )
        )
        self.assertEqual(resp.json()["outcome"], "not_found")

    def test_stock_take_from_other_org_returns_not_found(self):
        other_st = StockTake.objects.create(
            organization=self.other_org,
            branch=self.other_branch,
            status=StockTake.DRAFT,
        )
        self._auth()
        resp = self.client.get(
            self._url(
                code="WGT-001",
                branch_id=str(self.branch.id),
                stock_take_id=str(other_st.id),
            )
        )
        self.assertEqual(resp.json()["outcome"], "not_found")

    # --- org isolation ---

    def test_other_org_member_cannot_resolve_items_in_this_org(self):
        self.client.force_authenticate(user=self.other_user)
        resp = self.client.get(
            f"/api/orgs/{self.other_org.id}/inventory/items/resolve-scan/"
            f"?code=WGT-001&branch_id={self.branch.id}"
        )
        # other_branch belongs to other_org, so branch lookup fails → not_found
        self.assertEqual(resp.json()["outcome"], "not_found")

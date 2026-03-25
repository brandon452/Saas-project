from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase

from branch_transfers.models import BranchTransfer
from branches.models import Branch
from inventory.models import MasterItem, OrgItem, StockLedger, StockOnHand
from inventory.services import record_stock_movement
from suppliers.models import Supplier
from tenancy.models import Organization, OrganizationMember, ParentCompanyMember


class BranchTransferApiTests(APITestCase):
    def _create_org_item(self, organization, name, sku, *, item_name=""):
        master_item = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.for_org(organization).create(
            organization=organization,
            master_item=master_item,
            name=item_name,
        )

    def setUp(self):
        User = get_user_model()
        self.sender_owner = User.objects.create_user(username="bt_sender_owner", password="Passw0rd!")
        self.sender_admin = User.objects.create_user(username="bt_sender_admin", password="Passw0rd!")
        self.sender_staff = User.objects.create_user(username="bt_sender_staff", password="Passw0rd!")
        self.receiver_owner = User.objects.create_user(username="bt_receiver_owner", password="Passw0rd!")
        self.receiver_admin = User.objects.create_user(username="bt_receiver_admin", password="Passw0rd!")
        self.receiver_staff = User.objects.create_user(username="bt_receiver_staff", password="Passw0rd!")
        self.other_owner = User.objects.create_user(username="bt_other_owner", password="Passw0rd!")
        self.parent_admin_user = User.objects.create_user(username="bt_parent_admin", password="Passw0rd!")

        self.acme = Organization.objects.create(name="Acme", slug="acme-bt")
        self.globex = Organization.objects.create(name="Globex", slug="globex-bt")
        self.initech = Organization.objects.create(name="Initech", slug="initech-bt")

        OrganizationMember.objects.create(user=self.sender_owner, organization=self.acme, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.sender_admin, organization=self.acme, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.sender_staff, organization=self.acme, role="STAFF", is_active=True)
        OrganizationMember.objects.create(user=self.receiver_owner, organization=self.globex, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.receiver_admin, organization=self.globex, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.receiver_staff, organization=self.globex, role="STAFF", is_active=True)
        OrganizationMember.objects.create(user=self.other_owner, organization=self.initech, role="OWNER", is_active=True)

        ParentCompanyMember.objects.create(
            user=self.parent_admin_user,
            role=ParentCompanyMember.PARENT_ADMIN,
            is_active=True,
        )

        self.acme_from_branch = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Main",
            code="ACME-MAIN",
        )
        self.acme_other_branch = Branch.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Outlet",
            code="ACME-OUT",
        )
        self.globex_branch = Branch.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Main",
            code="GLOBEX-MAIN",
        )
        self.initech_branch = Branch.objects.for_org(self.initech).create(
            organization=self.initech,
            name="Initech Main",
            code="INI-MAIN",
        )

        self.acme_supplier = Supplier.objects.for_org(self.acme).create(
            organization=self.acme,
            name="Acme Supplier",
            created_by=self.sender_owner,
        )
        self.globex_supplier = Supplier.objects.for_org(self.globex).create(
            organization=self.globex,
            name="Globex Supplier",
            created_by=self.receiver_owner,
        )

        self.acme_item_a = self._create_org_item(self.acme, "Acme Item A", "BT-A")
        self.acme_item_b = self._create_org_item(self.acme, "Acme Item B", "BT-B")
        self.globex_item = self._create_org_item(self.globex, "Globex Item", "GBT-1")

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _host(self, slug):
        return f"{slug}.localhost:8000"

    def _base_url(self, org_id):
        return f"/api/orgs/{org_id}/branch-transfers/"

    def _detail_url(self, org_id, transfer_id, suffix=""):
        return f"{self._base_url(org_id)}{transfer_id}/{suffix}"

    def _create_payload(self, **overrides):
        payload = {
            "from_branch": str(self.acme_from_branch.id),
            "to_branch": str(self.globex_branch.id),
            "notes": "Transfer notes",
            "lines": [
                {"item": str(self.acme_item_a.id), "quantity_sent": 3},
                {"item": str(self.acme_item_b.id), "quantity_sent": 2},
            ],
        }
        payload.update(overrides)
        return payload

    def _create_transfer(self, user=None, **overrides):
        if user:
            self._auth(user)
        return self.client.post(
            self._base_url(self.acme.id),
            self._create_payload(**overrides),
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )

    def _seed_sender_stock(self, qty_a=5, qty_b=5):
        record_stock_movement(
            org=self.acme,
            branch=self.acme_from_branch,
            item=self.acme_item_a,
            quantity=Decimal(f"{qty_a}.0000"),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            performed_by=self.sender_owner,
            idempotency_key=f"seed-a-{qty_a}",
        )
        record_stock_movement(
            org=self.acme,
            branch=self.acme_from_branch,
            item=self.acme_item_b,
            quantity=Decimal(f"{qty_b}.0000"),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            performed_by=self.sender_owner,
            idempotency_key=f"seed-b-{qty_b}",
        )

    def _make_transfer(self, status=BranchTransfer.DRAFT):
        transfer = BranchTransfer.objects.for_org(self.acme).create(
            organization=self.acme,
            from_branch=self.acme_from_branch,
            to_branch=self.globex_branch,
            to_organization=self.globex,
            status=status,
            created_by=self.sender_owner,
        )
        transfer.lines.create(item=self.acme_item_a, quantity_sent=3)
        transfer.lines.create(item=self.acme_item_b, quantity_sent=2)
        return transfer

    def test_create_rules_and_server_side_fields(self):
        for user, expected_status in (
            (self.sender_owner, 201),
            (self.sender_admin, 201),
            (self.sender_staff, 403),
        ):
            response = self._create_transfer(user=user)
            self.assertEqual(response.status_code, expected_status)
            if expected_status == 201:
                self.assertEqual(response.data["lines"][0]["item"]["id"], str(self.acme_item_a.id))
                self.assertEqual(response.data["lines"][0]["item"]["name"], self.acme_item_a.display_name)
                self.assertEqual(response.data["lines"][0]["item"]["sku"], self.acme_item_a.master_item.sku)

        created = BranchTransfer.objects.for_org(self.acme).order_by("created_at").first()
        self.assertIsNotNone(created)
        self.assertEqual(created.to_organization, self.globex)
        self.assertEqual(created.created_by, self.sender_owner)
        self.assertEqual(created.status, BranchTransfer.DRAFT)

        self._auth(self.sender_owner)
        self.assertEqual(
            self._create_transfer(from_branch=str(self.globex_branch.id)).status_code,
            400,
        )

        with patch(
            "branch_transfers.serializers.BranchTransferCreateSerializer._orgs_share_parent",
            return_value=False,
        ):
            different_parent = self._create_transfer(user=self.sender_owner)
        self.assertEqual(different_parent.status_code, 400)
        self.assertIn("to_branch", different_parent.data)

        same_branch = self._create_transfer(user=self.sender_owner, to_branch=str(self.acme_from_branch.id))
        self.assertEqual(same_branch.status_code, 400)

        no_lines = self._create_transfer(user=self.sender_owner, lines=[])
        self.assertEqual(no_lines.status_code, 400)

        duplicate_items = self._create_transfer(
            user=self.sender_owner,
            lines=[
                {"item": str(self.acme_item_a.id), "quantity_sent": 1},
                {"item": str(self.acme_item_a.id), "quantity_sent": 2},
            ],
        )
        self.assertEqual(duplicate_items.status_code, 400)

        foreign_item = self._create_transfer(
            user=self.sender_owner,
            lines=[{"item": str(self.globex_item.id), "quantity_sent": 1}],
        )
        self.assertEqual(foreign_item.status_code, 400)

        zero_quantity = self._create_transfer(
            user=self.sender_owner,
            lines=[{"item": str(self.acme_item_a.id), "quantity_sent": 0}],
        )
        self.assertEqual(zero_quantity.status_code, 400)

        negative_quantity = self._create_transfer(
            user=self.sender_owner,
            lines=[{"item": str(self.acme_item_a.id), "quantity_sent": -1}],
        )
        self.assertEqual(negative_quantity.status_code, 400)

    def test_retrieve_returns_nested_item_summary(self):
        transfer = self._make_transfer()

        self._auth(self.sender_owner)
        response = self.client.get(
            self._detail_url(self.acme.id, transfer.id),
            HTTP_HOST=self._host(self.acme.slug),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["lines"][0]["item"]["id"], str(self.acme_item_a.id))
        self.assertEqual(response.data["lines"][0]["item"]["name"], self.acme_item_a.display_name)
        self.assertEqual(response.data["lines"][0]["item"]["sku"], self.acme_item_a.master_item.sku)

    def test_approve_rules(self):
        transfer = self._make_transfer()

        for user, expected_status in (
            (self.sender_owner, 200),
            (self.sender_admin, 200),
        ):
            transfer.status = BranchTransfer.DRAFT
            transfer.approved_by = None
            transfer.save(update_fields=["status", "approved_by", "updated_at"])
            self._auth(user)
            response = self.client.post(
                self._detail_url(self.acme.id, transfer.id, "approve/"),
                {},
                format="json",
                HTTP_HOST=self._host(self.acme.slug),
            )
            self.assertEqual(response.status_code, expected_status)
            transfer.refresh_from_db()
            self.assertEqual(transfer.status, BranchTransfer.APPROVED)
            self.assertEqual(transfer.approved_by, user)

        self._auth(self.receiver_owner)
        self.assertEqual(
            self.client.post(
                self._detail_url(self.globex.id, transfer.id, "approve/"),
                {},
                format="json",
                HTTP_HOST=self._host(self.globex.slug),
            ).status_code,
            403,
        )

        self._auth(self.sender_staff)
        self.assertEqual(
            self.client.post(
                self._detail_url(self.acme.id, transfer.id, "approve/"),
                {},
                format="json",
                HTTP_HOST=self._host(self.acme.slug),
            ).status_code,
            403,
        )

        transfer.status = BranchTransfer.IN_TRANSIT
        transfer.save(update_fields=["status", "updated_at"])
        self._auth(self.sender_owner)
        self.assertEqual(
            self.client.post(
                self._detail_url(self.acme.id, transfer.id, "approve/"),
                {},
                format="json",
                HTTP_HOST=self._host(self.acme.slug),
            ).status_code,
            400,
        )

        transfer.status = BranchTransfer.CANCELLED
        transfer.save(update_fields=["status", "updated_at"])
        self.assertEqual(
            self.client.post(
                self._detail_url(self.acme.id, transfer.id, "approve/"),
                {},
                format="json",
                HTTP_HOST=self._host(self.acme.slug),
            ).status_code,
            400,
        )

    def test_dispatch_rules_and_stock_effects(self):
        transfer = self._make_transfer(status=BranchTransfer.APPROVED)
        self._seed_sender_stock()

        with patch("branch_transfers.services.record_stock_movement", wraps=record_stock_movement) as mocked_record:
            self._auth(self.sender_owner)
            response = self.client.post(
                self._detail_url(self.acme.id, transfer.id, "dispatch/"),
                {},
                format="json",
                HTTP_HOST=self._host(self.acme.slug),
            )

        self.assertEqual(response.status_code, 200)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, BranchTransfer.IN_TRANSIT)
        self.assertIsNotNone(transfer.dispatched_at)
        self.assertEqual(mocked_record.call_count, 2)
        self.assertEqual(mocked_record.call_args_list[0].kwargs["movement_type"], StockLedger.MOVEMENT_ISSUE)
        self.assertEqual(mocked_record.call_args_list[0].kwargs["branch"], self.acme_from_branch)

        stock_a = StockOnHand.objects.for_org(self.acme).get(branch=self.acme_from_branch, item=self.acme_item_a)
        stock_b = StockOnHand.objects.for_org(self.acme).get(branch=self.acme_from_branch, item=self.acme_item_b)
        self.assertEqual(stock_a.quantity, Decimal("2.0000"))
        self.assertEqual(stock_b.quantity, Decimal("3.0000"))

        insufficient = self._make_transfer(status=BranchTransfer.APPROVED)
        self._auth(self.sender_owner)
        bad_response = self.client.post(
            self._detail_url(self.acme.id, insufficient.id, "dispatch/"),
            {},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(bad_response.status_code, 400)
        insufficient.refresh_from_db()
        self.assertEqual(insufficient.status, BranchTransfer.APPROVED)

        self._auth(self.receiver_owner)
        receiver_dispatch = self.client.post(
            self._detail_url(self.globex.id, transfer.id, "dispatch/"),
            {},
            format="json",
            HTTP_HOST=self._host(self.globex.slug),
        )
        self.assertEqual(receiver_dispatch.status_code, 403)

        draft = self._make_transfer(status=BranchTransfer.DRAFT)
        self._auth(self.sender_owner)
        self.assertEqual(
            self.client.post(
                self._detail_url(self.acme.id, draft.id, "dispatch/"),
                {},
                format="json",
                HTTP_HOST=self._host(self.acme.slug),
            ).status_code,
            400,
        )

        cancelled = self._make_transfer(status=BranchTransfer.CANCELLED)
        self.assertEqual(
            self.client.post(
                self._detail_url(self.acme.id, cancelled.id, "dispatch/"),
                {},
                format="json",
                HTTP_HOST=self._host(self.acme.slug),
            ).status_code,
            400,
        )

    def test_receive_rules_and_stock_effects(self):
        transfer = self._make_transfer(status=BranchTransfer.IN_TRANSIT)

        with patch("branch_transfers.services.record_stock_movement", wraps=record_stock_movement) as mocked_record:
            self._auth(self.receiver_owner)
            response = self.client.post(
                self._detail_url(self.globex.id, transfer.id, "receive/"),
                {
                    "notes": "all good",
                    "lines": [
                        {"line_id": transfer.lines.all()[0].id, "quantity_received": 3},
                        {"line_id": transfer.lines.all()[1].id, "quantity_received": 2},
                    ],
                },
                format="json",
                HTTP_HOST=self._host(self.globex.slug),
            )

        self.assertEqual(response.status_code, 200)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, BranchTransfer.RECEIVED_COMPLETE)
        self.assertEqual(transfer.received_by, self.receiver_owner)
        self.assertIsNotNone(transfer.received_at)
        self.assertEqual(transfer.receive_notes, "all good")
        self.assertEqual(mocked_record.call_count, 2)
        self.assertEqual(mocked_record.call_args_list[0].kwargs["movement_type"], StockLedger.MOVEMENT_RECEIPT)
        self.assertEqual(mocked_record.call_args_list[0].kwargs["branch"], self.globex_branch)

        recipient_item_a = OrgItem.objects.for_org(self.globex).get(master_item=self.acme_item_a.master_item)
        recipient_item_b = OrgItem.objects.for_org(self.globex).get(master_item=self.acme_item_b.master_item)
        receiver_stock_a = StockOnHand.objects.for_org(self.globex).get(branch=self.globex_branch, item=recipient_item_a)
        receiver_stock_b = StockOnHand.objects.for_org(self.globex).get(branch=self.globex_branch, item=recipient_item_b)
        self.assertEqual(receiver_stock_a.quantity, Decimal("3.0000"))
        self.assertEqual(receiver_stock_b.quantity, Decimal("2.0000"))
        self.assertEqual(recipient_item_a.master_item, self.acme_item_a.master_item)
        self.assertEqual(recipient_item_b.master_item, self.acme_item_b.master_item)
        self.assertTrue(recipient_item_a.is_active)
        self.assertTrue(recipient_item_b.is_active)

        for user in (self.receiver_admin, self.receiver_staff):
            transfer2 = self._make_transfer(status=BranchTransfer.IN_TRANSIT)
            line_ids = list(transfer2.lines.values_list("id", flat=True))
            self._auth(user)
            allowed = self.client.post(
                self._detail_url(self.globex.id, transfer2.id, "receive/"),
                {
                    "lines": [
                        {"line_id": line_ids[0], "quantity_received": 0},
                        {"line_id": line_ids[1], "quantity_received": 1},
                    ]
                },
                format="json",
                HTTP_HOST=self._host(self.globex.slug),
            )
            self.assertEqual(allowed.status_code, 200)
            transfer2.refresh_from_db()
            self.assertEqual(transfer2.status, BranchTransfer.RECEIVED_WITH_VARIANCE)

        sender_cannot_receive = self.client.post(
            self._detail_url(self.acme.id, transfer.id, "receive/"),
            {
                "lines": [
                    {"line_id": transfer.lines.all()[0].id, "quantity_received": 1},
                    {"line_id": transfer.lines.all()[1].id, "quantity_received": 1},
                ]
            },
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(sender_cannot_receive.status_code, 403)

        draft = self._make_transfer(status=BranchTransfer.DRAFT)
        self._auth(self.receiver_owner)
        self.assertEqual(
            self.client.post(
                self._detail_url(self.globex.id, draft.id, "receive/"),
                {"lines": [{"line_id": draft.lines.first().id, "quantity_received": 1}]},
                format="json",
                HTTP_HOST=self._host(self.globex.slug),
            ).status_code,
            400,
        )

        approved = self._make_transfer(status=BranchTransfer.APPROVED)
        self.assertEqual(
            self.client.post(
                self._detail_url(self.globex.id, approved.id, "receive/"),
                {"lines": [{"line_id": approved.lines.first().id, "quantity_received": 1}]},
                format="json",
                HTTP_HOST=self._host(self.globex.slug),
            ).status_code,
            400,
        )

    def test_receive_payload_validation(self):
        transfer = self._make_transfer(status=BranchTransfer.IN_TRANSIT)
        lines = list(transfer.lines.order_by("id"))
        self._auth(self.receiver_owner)

        negative = self.client.post(
            self._detail_url(self.globex.id, transfer.id, "receive/"),
            {"lines": [{"line_id": lines[0].id, "quantity_received": -1}]},
            format="json",
            HTTP_HOST=self._host(self.globex.slug),
        )
        self.assertEqual(negative.status_code, 400)

        exceeds = self.client.post(
            self._detail_url(self.globex.id, transfer.id, "receive/"),
            {
                "lines": [
                    {"line_id": lines[0].id, "quantity_received": 4},
                    {"line_id": lines[1].id, "quantity_received": 2},
                ]
            },
            format="json",
            HTTP_HOST=self._host(self.globex.slug),
        )
        self.assertEqual(exceeds.status_code, 400)

        missing = self.client.post(
            self._detail_url(self.globex.id, transfer.id, "receive/"),
            {"lines": [{"line_id": lines[0].id, "quantity_received": 1}]},
            format="json",
            HTTP_HOST=self._host(self.globex.slug),
        )
        self.assertEqual(missing.status_code, 400)

        extra = self.client.post(
            self._detail_url(self.globex.id, transfer.id, "receive/"),
            {
                "lines": [
                    {"line_id": lines[0].id, "quantity_received": 1},
                    {"line_id": lines[1].id, "quantity_received": 1},
                    {"line_id": 999999, "quantity_received": 1},
                ]
            },
            format="json",
            HTTP_HOST=self._host(self.globex.slug),
        )
        self.assertEqual(extra.status_code, 400)

        duplicate = self.client.post(
            self._detail_url(self.globex.id, transfer.id, "receive/"),
            {
                "lines": [
                    {"line_id": lines[0].id, "quantity_received": 1},
                    {"line_id": lines[0].id, "quantity_received": 1},
                ]
            },
            format="json",
            HTTP_HOST=self._host(self.globex.slug),
        )
        self.assertEqual(duplicate.status_code, 400)

    def test_cancel_rules(self):
        for initial_status, expected_status in (
            (BranchTransfer.DRAFT, 200),
            (BranchTransfer.APPROVED, 200),
        ):
            transfer = self._make_transfer(status=initial_status)
            self._auth(self.sender_owner)
            response = self.client.post(
                self._detail_url(self.acme.id, transfer.id, "cancel/"),
                {},
                format="json",
                HTTP_HOST=self._host(self.acme.slug),
            )
            self.assertEqual(response.status_code, expected_status)
            transfer.refresh_from_db()
            self.assertEqual(transfer.status, BranchTransfer.CANCELLED)

        for user in (self.sender_admin, self.receiver_owner):
            transfer = self._make_transfer(status=BranchTransfer.DRAFT)
            self._auth(user)
            response = self.client.post(
                self._detail_url(self.acme.id if user == self.sender_admin else self.globex.id, transfer.id, "cancel/"),
                {},
                format="json",
                HTTP_HOST=self._host(self.acme.slug if user == self.sender_admin else self.globex.slug),
            )
            self.assertEqual(response.status_code, 403)

        for status_value in (
            BranchTransfer.IN_TRANSIT,
            BranchTransfer.RECEIVED_COMPLETE,
            BranchTransfer.CANCELLED,
        ):
            transfer = self._make_transfer(status=status_value)
            self._auth(self.sender_owner)
            response = self.client.post(
                self._detail_url(self.acme.id, transfer.id, "cancel/"),
                {},
                format="json",
                HTTP_HOST=self._host(self.acme.slug),
            )
            self.assertEqual(response.status_code, 400)

    def test_queryset_visibility_and_parent_global_read(self):
        transfer = self._make_transfer()

        self._auth(self.sender_owner)
        sender_list = self.client.get(self._base_url(self.acme.id), HTTP_HOST=self._host(self.acme.slug))
        self.assertEqual(sender_list.status_code, 200)
        self.assertIn(str(transfer.id), {row["id"] for row in sender_list.data["results"]})

        self._auth(self.receiver_owner)
        receiver_list = self.client.get(self._base_url(self.globex.id), HTTP_HOST=self._host(self.globex.slug))
        self.assertEqual(receiver_list.status_code, 200)
        self.assertIn(str(transfer.id), {row["id"] for row in receiver_list.data["results"]})

        self._auth(self.other_owner)
        other_list = self.client.get(self._base_url(self.initech.id), HTTP_HOST=self._host(self.initech.slug))
        self.assertEqual(other_list.status_code, 200)
        self.assertNotIn(str(transfer.id), {row["id"] for row in other_list.data["results"]})

        self._auth(self.parent_admin_user)
        parent_sender_url = self.client.get(self._base_url(self.acme.id), HTTP_HOST=self._host(self.acme.slug))
        parent_receiver_url = self.client.get(self._base_url(self.globex.id), HTTP_HOST=self._host(self.globex.slug))
        self.assertIn(str(transfer.id), {row["id"] for row in parent_sender_url.data["results"]})
        self.assertIn(str(transfer.id), {row["id"] for row in parent_receiver_url.data["results"]})

        parent_mutation = self.client.post(
            self._detail_url(self.acme.id, transfer.id, "approve/"),
            {},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(parent_mutation.status_code, 403)

    def test_immutability(self):
        transfer = self._make_transfer()
        self._auth(self.sender_owner)
        patch_response = self.client.patch(
            self._detail_url(self.acme.id, transfer.id),
            {"notes": "nope"},
            format="json",
            HTTP_HOST=self._host(self.acme.slug),
        )
        delete_response = self.client.delete(
            self._detail_url(self.acme.id, transfer.id),
            HTTP_HOST=self._host(self.acme.slug),
        )
        self.assertEqual(patch_response.status_code, 405)
        self.assertEqual(delete_response.status_code, 405)

    def test_atomicity_on_dispatch_and_receive_failures(self):
        self._seed_sender_stock()
        transfer = self._make_transfer(status=BranchTransfer.APPROVED)

        call_count = {"count": 0}

        def fail_on_second_dispatch(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 2:
                raise ValidationError("forced dispatch failure")
            return record_stock_movement(*args, **kwargs)

        self._auth(self.sender_owner)
        with patch("branch_transfers.services.record_stock_movement", side_effect=fail_on_second_dispatch):
            dispatch_response = self.client.post(
                self._detail_url(self.acme.id, transfer.id, "dispatch/"),
                {},
                format="json",
                HTTP_HOST=self._host(self.acme.slug),
            )

        self.assertEqual(dispatch_response.status_code, 400)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, BranchTransfer.APPROVED)
        self.assertEqual(
            StockOnHand.objects.for_org(self.acme).get(branch=self.acme_from_branch, item=self.acme_item_a).quantity,
            Decimal("5.0000"),
        )

        transfer.status = BranchTransfer.IN_TRANSIT
        transfer.save(update_fields=["status", "updated_at"])
        call_count["count"] = 0

        def fail_on_second_receive(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 2:
                raise ValidationError("forced receive failure")
            return record_stock_movement(*args, **kwargs)

        line_ids = list(transfer.lines.order_by("id").values_list("id", flat=True))
        self._auth(self.receiver_owner)
        with patch("branch_transfers.services.record_stock_movement", side_effect=fail_on_second_receive):
            receive_response = self.client.post(
                self._detail_url(self.globex.id, transfer.id, "receive/"),
                {
                    "lines": [
                        {"line_id": line_ids[0], "quantity_received": 1},
                        {"line_id": line_ids[1], "quantity_received": 1},
                    ]
                },
                format="json",
                HTTP_HOST=self._host(self.globex.slug),
            )

        self.assertEqual(receive_response.status_code, 400)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, BranchTransfer.IN_TRANSIT)
        self.assertFalse(StockOnHand.objects.for_org(self.globex).exists())
        self.assertTrue(all(line.quantity_received is None for line in transfer.lines.all()))

    def test_receive_reuses_existing_recipient_org_item(self):
        existing = OrgItem.objects.for_org(self.globex).create(
            organization=self.globex,
            master_item=self.acme_item_a.master_item,
            name="Receiver Alias",
        )
        transfer = self._make_transfer(status=BranchTransfer.IN_TRANSIT)
        line_ids = list(transfer.lines.order_by("id").values_list("id", flat=True))

        self._auth(self.receiver_owner)
        response = self.client.post(
            self._detail_url(self.globex.id, transfer.id, "receive/"),
            {
                "lines": [
                    {"line_id": line_ids[0], "quantity_received": 1},
                    {"line_id": line_ids[1], "quantity_received": 0},
                ]
            },
            format="json",
            HTTP_HOST=self._host(self.globex.slug),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            OrgItem.objects.for_org(self.globex).filter(master_item=self.acme_item_a.master_item).count(),
            1,
        )
        stock = StockOnHand.objects.for_org(self.globex).get(branch=self.globex_branch, item=existing)
        self.assertEqual(stock.quantity, Decimal("1.0000"))

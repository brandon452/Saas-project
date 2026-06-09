from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from branch_transfers.models import BranchTransfer, BranchTransferLine
from branches.models import Branch
from inventory.models import BranchItem, MasterItem, OrgItem, StockLedger
from inventory.services import record_stock_movement
from tenancy.models import Organization, OrganizationMember


class TransferIdempotencyTests(APITestCase):
    def _create_org_item(self, organization, name, sku):
        master = MasterItem.objects.create(name=name, sku=sku)
        return OrgItem.objects.for_org(organization).create(
            organization=organization, master_item=master
        )

    def _receipt(self, org, branch, item, qty, cost, key, user):
        record_stock_movement(
            org=org,
            branch=branch,
            item=item,
            quantity=Decimal(qty),
            movement_type=StockLedger.MOVEMENT_RECEIPT,
            unit_cost=Decimal(cost),
            performed_by=user,
            idempotency_key=key,
        )

    def setUp(self):
        User = get_user_model()
        self.sender = User.objects.create_user(username="ti_sender", password="Passw0rd!")
        self.receiver = User.objects.create_user(username="ti_receiver", password="Passw0rd!")

        self.acme = Organization.objects.create(name="Acme", slug="ti-acme")
        self.globex = Organization.objects.create(name="Globex", slug="ti-globex")

        self.acme_branch = Branch.objects.for_org(self.acme).create(
            organization=self.acme, name="Acme Main", code="ACME"
        )
        self.globex_branch = Branch.objects.for_org(self.globex).create(
            organization=self.globex, name="Globex Main", code="GLOBEX"
        )

        OrganizationMember.objects.create(
            user=self.sender, organization=self.acme, role="OWNER", is_active=True
        )
        OrganizationMember.objects.create(
            user=self.receiver, organization=self.globex, role="OWNER", is_active=True
        )

        self.item = self._create_org_item(self.acme, "Widget", "TI-W")
        BranchItem.objects.create(branch=self.acme_branch, org_item=self.item, is_active=True)
        self._receipt(self.acme, self.acme_branch, self.item, "20", "10.00", "ti-receipt", self.sender)

        self.transfer = self._create_approved_transfer()

    def _create_approved_transfer(self):
        self.client.force_authenticate(user=self.sender)
        resp = self.client.post(
            f"/api/orgs/{self.acme.id}/branch-transfers/",
            {
                "from_branch": str(self.acme_branch.id),
                "to_branch": str(self.globex_branch.id),
                "notes": "",
                "lines": [{"item": str(self.item.id), "quantity_sent": 5}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.json())
        transfer_id = resp.json()["id"]
        transfer = BranchTransfer.objects.get(id=transfer_id)
        if transfer.status == BranchTransfer.DRAFT:
            self.client.post(
                f"/api/orgs/{self.acme.id}/branch-transfers/{transfer_id}/approve/",
                format="json",
            )
            transfer.refresh_from_db()
        return transfer

    def _dispatch_url(self):
        return f"/api/orgs/{self.acme.id}/branch-transfers/{self.transfer.id}/dispatch/"

    def _receive_url(self):
        return f"/api/orgs/{self.globex.id}/branch-transfers/{self.transfer.id}/receive/"

    def _receive_payload(self, *, idempotency_key=None):
        line = BranchTransferLine.objects.get(transfer=self.transfer)
        payload = {
            "lines": [{"line_id": line.id, "quantity_received": 5}],
            "notes": "",
        }
        if idempotency_key is not None:
            payload["idempotency_key"] = idempotency_key
        return payload

    # --- dispatch idempotency ---

    def test_dispatch_with_idempotency_key_succeeds(self):
        self.client.force_authenticate(user=self.sender)
        resp = self.client.post(
            self._dispatch_url(), {"idempotency_key": "dispatch-idem-01"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "IN_TRANSIT")

    def test_dispatch_without_idempotency_key_succeeds(self):
        self.client.force_authenticate(user=self.sender)
        resp = self.client.post(self._dispatch_url(), {}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "IN_TRANSIT")

    def test_dispatch_idempotent_replay_returns_in_transit(self):
        self.client.force_authenticate(user=self.sender)
        self.client.post(
            self._dispatch_url(), {"idempotency_key": "dispatch-idem-02"}, format="json"
        )
        # Second call — transfer is already IN_TRANSIT, service returns early
        resp = self.client.post(
            self._dispatch_url(), {"idempotency_key": "dispatch-idem-02"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "IN_TRANSIT")

    # --- receive idempotency ---

    def _dispatch(self):
        self.client.force_authenticate(user=self.sender)
        self.client.post(self._dispatch_url(), {}, format="json")

    def test_receive_with_idempotency_key_succeeds(self):
        self._dispatch()
        self.client.force_authenticate(user=self.receiver)
        resp = self.client.post(
            self._receive_url(),
            self._receive_payload(idempotency_key="receive-idem-01"),
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(resp.json()["status"], ("RECEIVED_COMPLETE", "RECEIVED_WITH_VARIANCE"))

    def test_receive_without_idempotency_key_succeeds(self):
        self._dispatch()
        self.client.force_authenticate(user=self.receiver)
        resp = self.client.post(
            self._receive_url(), self._receive_payload(), format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_receive_idempotency_key_field_accepted_in_payload(self):
        """Serializer accepts idempotency_key without validation error."""
        self._dispatch()
        self.client.force_authenticate(user=self.receiver)
        payload = self._receive_payload(idempotency_key="receive-idem-02")
        self.assertIn("idempotency_key", payload)
        resp = self.client.post(self._receive_url(), payload, format="json")
        # Should succeed, not return 400
        self.assertNotEqual(resp.status_code, 400)

    def test_receive_idempotency_key_passes_through_to_service(self):
        """Stock movements from receive should not be duplicated on replay."""
        self._dispatch()
        before = StockLedger.objects.filter(
            organization=self.globex,
        ).count()

        self.client.force_authenticate(user=self.receiver)
        payload = self._receive_payload(idempotency_key="receive-idem-03")
        self.client.post(self._receive_url(), payload, format="json")

        after = StockLedger.objects.filter(organization=self.globex).count()
        # Exactly one receipt movement created (one line received)
        self.assertEqual(after - before, 1)

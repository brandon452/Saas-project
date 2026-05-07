from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from audit.models import AuditEvent
from branches.models import Branch
from purchase_orders.models import PurchaseOrder
from suppliers.models import Supplier
from tenancy.models import Organization, OrganizationMember

User = get_user_model()
RATELIMIT_OFF = {"RATELIMIT_ENABLE": False}
PDF_DUMMY = b"%PDF-1.4 dummy"


class PDFExportTestMixin:
    """
    Minimal org/user setup for PDF export tests.
    Copied from ExportTestMixin pattern — avoids cross-module test dependency.
    Two orgs created upfront so cross-org tests use self.other_org without
    ad-hoc creation. other_org shares parent_company with org (explicit) to
    avoid any same-parent constraint enforcement.
    """

    def _setup_org_and_users(self):
        self.owner = User.objects.create_user(username="pdf_owner", password="Passw0rd!")
        self.admin = User.objects.create_user(username="pdf_admin", password="Passw0rd!")
        self.staff = User.objects.create_user(username="pdf_staff", password="Passw0rd!")
        self.outsider = User.objects.create_user(username="pdf_outsider", password="Passw0rd!")
        self.org = Organization.objects.create(name="PDF Org", slug="pdf-org")
        # Explicit same parent_company as self.org — safe against same-parent constraints
        self.other_org = Organization.objects.create(
            name="PDF Other",
            slug="pdf-other",
            parent_company=self.org.parent_company,
        )
        OrganizationMember.objects.create(user=self.owner, organization=self.org, role="OWNER", is_active=True)
        OrganizationMember.objects.create(user=self.admin, organization=self.org, role="ADMIN", is_active=True)
        OrganizationMember.objects.create(user=self.staff, organization=self.org, role="STAFF", is_active=True)
        self.branch = Branch.objects.for_org(self.org).create(
            organization=self.org, name="Main", code="MAIN"
        )
        self.other_branch = Branch.objects.for_org(self.other_org).create(
            organization=self.other_org, name="Other Main", code="OTHMAIN"
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)


@override_settings(**RATELIMIT_OFF)
class POPdfExportTests(PDFExportTestMixin, APITestCase):
    def setUp(self):
        self._setup_org_and_users()
        self.supplier = Supplier.objects.for_org(self.org).create(
            organization=self.org, display_name="Test Supplier", created_by=self.owner
        )
        self.po = PurchaseOrder.objects.for_org(self.org).create(
            organization=self.org,
            po_number="PO-0001",
            supplier=self.supplier,
            branch=self.branch,
            created_by=self.owner,
        )

    def _url(self, po_id=None):
        pk = po_id or self.po.id
        return f"/api/orgs/{self.org.id}/purchase-orders/{pk}/export/pdf/"

    @patch("purchase_orders.views._html_to_pdf", return_value=PDF_DUMMY)
    def test_returns_pdf_response(self, mock_html):

        self._auth(self.owner)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    @patch("purchase_orders.views._html_to_pdf", return_value=PDF_DUMMY)
    def test_content_disposition_filename(self, mock_html):

        self._auth(self.owner)
        response = self.client.get(self._url())
        self.assertIn(f'filename="po-{self.po.po_number}.pdf"', response["Content-Disposition"])

    @patch("purchase_orders.views._html_to_pdf", return_value=PDF_DUMMY)
    def test_audit_event_created_on_export(self, mock_html):

        self._auth(self.owner)
        before = AuditEvent.objects.filter(
            organization=self.org, event_type="purchase_order.exported"
        ).count()
        self.client.get(self._url())
        after = AuditEvent.objects.filter(
            organization=self.org, event_type="purchase_order.exported"
        ).count()
        self.assertEqual(after, before + 1)

    @patch("purchase_orders.views._html_to_pdf", return_value=PDF_DUMMY)
    def test_null_creator_returns_200(self, mock_html):

        self.po.created_by = None
        self.po.save(update_fields=["created_by"])
        self._auth(self.owner)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    @patch("purchase_orders.views._html_to_pdf", return_value=PDF_DUMMY)
    def test_notes_not_in_html_when_blank(self, mock_render):
        self.po.notes = ""
        self.po.save(update_fields=["notes"])
        self._auth(self.owner)
        self.client.get(self._url())
        html_input = mock_render.call_args.args[0]
        self.assertNotIn('id="notes-section"', html_input)

    @patch("purchase_orders.views._html_to_pdf", return_value=PDF_DUMMY)
    def test_notes_present_in_html_when_set(self, mock_render):
        self.po.notes = "Please deliver to the back entrance."
        self.po.save(update_fields=["notes"])
        self._auth(self.owner)
        self.client.get(self._url())
        html_input = mock_render.call_args.args[0]
        self.assertIn('id="notes-section"', html_input)

    @patch("purchase_orders.views._html_to_pdf", return_value=PDF_DUMMY)
    def test_admin_can_export(self, mock_html):

        self._auth(self.admin)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    @patch("purchase_orders.views._html_to_pdf", return_value=PDF_DUMMY)
    def test_staff_can_export(self, mock_html):

        self._auth(self.staff)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_denied(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 401)

    def test_outsider_denied(self):
        self._auth(self.outsider)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 403)

    @patch("purchase_orders.views._html_to_pdf", return_value=PDF_DUMMY)
    def test_cross_org_po_returns_404(self, mock_html):

        other_supplier = Supplier.objects.for_org(self.other_org).create(
            organization=self.other_org, display_name="Other Supplier"
        )
        other_po = PurchaseOrder.objects.for_org(self.other_org).create(
            organization=self.other_org,
            po_number="PO-9999",
            supplier=other_supplier,
            branch=self.other_branch,
        )
        self._auth(self.owner)
        response = self.client.get(self._url(po_id=other_po.id))
        self.assertEqual(response.status_code, 404)


@override_settings(RATELIMIT_USE_CACHE="default", EXPORT_PDF_RATE_LIMIT="1/m")
class POPdfRateLimitTests(PDFExportTestMixin, APITestCase):
    def setUp(self):
        self._setup_org_and_users()
        self.supplier = Supplier.objects.for_org(self.org).create(
            organization=self.org, display_name="RL Supplier", created_by=self.owner
        )
        self.po = PurchaseOrder.objects.for_org(self.org).create(
            organization=self.org,
            po_number="PO-RL",
            supplier=self.supplier,
            branch=self.branch,
            created_by=self.owner,
        )

    def _url(self):
        return f"/api/orgs/{self.org.id}/purchase-orders/{self.po.id}/export/pdf/"

    @patch("purchase_orders.views._html_to_pdf", return_value=PDF_DUMMY)
    def test_rate_limit_triggers_429(self, mock_html):

        self._auth(self.owner)
        r1 = self.client.get(self._url())
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.get(self._url())
        self.assertEqual(r2.status_code, 429)

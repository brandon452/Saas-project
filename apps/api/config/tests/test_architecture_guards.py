from pathlib import Path

from django.test import SimpleTestCase


class ArchitectureGuardTests(SimpleTestCase):
    def test_targeted_services_import_inventory_api(self):
        project_root = Path(__file__).resolve().parents[4]
        targets = [
            project_root / "apps/api/goods_receipts/services.py",
            project_root / "apps/api/branch_transfers/services.py",
            project_root / "apps/api/quick_sales/services.py",
        ]
        for path in targets:
            content = path.read_text(encoding="utf-8")
            self.assertIn("from inventory.api import", content)
            self.assertNotIn("from inventory.services import", content)

    def test_goods_receipts_view_no_manual_audit_call(self):
        project_root = Path(__file__).resolve().parents[4]
        path = project_root / "apps/api/goods_receipts/views.py"
        content = path.read_text(encoding="utf-8")
        self.assertNotIn("log_audit_event(", content)

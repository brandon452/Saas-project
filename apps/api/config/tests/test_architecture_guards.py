import ast
import json
import re
from pathlib import Path

from django.test import SimpleTestCase


class ArchitectureGuardTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_root = Path(__file__).resolve().parents[4]

    def test_targeted_services_import_inventory_api(self):
        targets = self._paths(
            [
                "apps/api/goods_receipts/services.py",
                "apps/api/branch_transfers/services.py",
                "apps/api/quick_sales/services.py",
            ]
        )
        for path in targets:
            content = path.read_text(encoding="utf-8")
            rel_path = self._rel(path)
            self.assertIn(
                "from inventory.api import",
                content,
                msg=f"{rel_path} must import inventory facade methods through inventory.api",
            )

    def test_goods_receipts_view_no_manual_audit_call(self):
        path = self.project_root / "apps/api/goods_receipts/views.py"
        content = path.read_text(encoding="utf-8")
        self.assertNotIn("log_audit_event(", content)

    def test_api_and_service_modules_do_not_import_forbidden_inventory_internals(self):
        violations = []
        for path in self._api_and_service_paths():
            rel_path = self._rel(path)
            if rel_path == "apps/api/inventory/api.py":
                continue
            content = path.read_text(encoding="utf-8")
            for forbidden in ("inventory.services", "inventory.lot_services"):
                if forbidden in content:
                    violations.append(f"{rel_path}: import {forbidden} through inventory.api")

        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_inventory_model_import_baseline_does_not_grow(self):
        baseline_path = self.project_root / "docs/inventory-model-import-baseline.json"
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline_paths = set(baseline["baseline_paths"])
        current_paths = set(self._inventory_model_import_paths())
        new_paths = sorted(current_paths - baseline_paths)

        self.assertLessEqual(
            len(current_paths),
            baseline["baseline_count"],
            msg=f"inventory.models import count increased: current={len(current_paths)} baseline={baseline['baseline_count']}",
        )
        self.assertEqual(
            new_paths,
            [],
            msg="New inventory.models import paths require arch-baseline-update-approved and a slice log entry:\n"
            + "\n".join(new_paths),
        )

    def test_scoped_services_do_not_import_inventory_models(self):
        targets = self._paths(
            [
                "apps/api/goods_receipts/services.py",
                "apps/api/branch_transfers/services.py",
                "apps/api/quick_sales/services.py",
            ]
        )
        violations = [
            self._rel(path)
            for path in targets
            if self._imports_module(path, "inventory.models")
        ]

        self.assertEqual(
            violations,
            [],
            msg="Scoped service modules must use inventory.api instead of inventory.models:\n"
            + "\n".join(violations),
        )

    def test_frontend_boundary_exception_manifest_schema(self):
        manifest_path = self.project_root / "apps/web/components/boundary-exceptions.json"
        exceptions = json.loads(manifest_path.read_text(encoding="utf-8"))
        required = {"path", "owner", "expiry_date", "reason", "ticket"}
        errors = []
        for index, entry in enumerate(exceptions):
            missing = sorted(required - set(entry))
            if missing:
                errors.append(f"entry {index} missing fields: {missing}")
                continue
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", entry["expiry_date"]):
                errors.append(f"entry {index} expiry_date must be YYYY-MM-DD")
            for field in required - {"expiry_date"}:
                if not isinstance(entry[field], str) or not entry[field].strip():
                    errors.append(f"entry {index} {field} must be a non-empty string")

        self.assertEqual(errors, [], msg="\n".join(errors))

    def test_phase3c_frontend_boundary_exceptions_are_removed(self):
        manifest_path = self.project_root / "apps/web/components/boundary-exceptions.json"
        exceptions = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(exceptions, [], msg="Phase 3C requires no active frontend boundary exceptions")

    def test_phase3c_no_legacy_export_resolver_usage(self):
        violations = []
        for path in (self.project_root / "apps/api").rglob("*.py"):
            rel_path = self._rel(path)
            if rel_path.startswith("apps/api/exports/tests/"):
                continue
            if rel_path == "apps/api/config/tests/test_architecture_guards.py":
                continue
            if "resolve_export_csv_service_enabled" in path.read_text(encoding="utf-8-sig"):
                violations.append(rel_path)

        self.assertEqual(
            violations,
            [],
            msg="Phase 3C removes legacy export fallback routing:\n" + "\n".join(violations),
        )

    def _paths(self, rel_paths):
        return [self.project_root / rel_path for rel_path in rel_paths]

    def _api_and_service_paths(self):
        paths = []
        for pattern in ("api.py", "services.py"):
            paths.extend((self.project_root / "apps/api").glob(f"*/{pattern}"))
        return sorted(paths)

    def _inventory_model_import_paths(self):
        paths = []
        for path in (self.project_root / "apps/api").rglob("*.py"):
            rel_path = self._rel(path)
            if rel_path.startswith("apps/api/inventory/"):
                continue
            if self._imports_module(path, "inventory.models"):
                paths.append(rel_path)
        return sorted(paths)

    def _imports_module(self, path, module):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        return any(
            (
                isinstance(node, ast.ImportFrom)
                and node.module == module
            )
            or (
                isinstance(node, ast.Import)
                and any(alias.name == module for alias in node.names)
            )
            for node in ast.walk(tree)
        )

    def _rel(self, path):
        return path.relative_to(self.project_root).as_posix()

from unittest.mock import MagicMock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from exports.config import parse_export_csv_endpoint_overrides
from exports.service import ExportConfig, ExportService


class ExportConfigParserTests(SimpleTestCase):
    def test_empty_values_parse_to_empty_map(self):
        self.assertEqual(parse_export_csv_endpoint_overrides("", production=False), {})
        self.assertEqual(parse_export_csv_endpoint_overrides(None, production=False), {})

    def test_json_map_parses_bool_values(self):
        parsed = parse_export_csv_endpoint_overrides('{"purchase_orders": true}', production=False)
        self.assertEqual(parsed, {"purchase_orders": True})

    def test_non_prod_invalid_json_fails_fast(self):
        with self.assertRaises(ValueError):
            parse_export_csv_endpoint_overrides("{bad-json", production=False)

    def test_prod_invalid_json_falls_back_empty(self):
        self.assertEqual(parse_export_csv_endpoint_overrides("{bad-json", production=True), {})

    def test_invalid_shape_fails_fast(self):
        with self.assertRaises(ValueError):
            parse_export_csv_endpoint_overrides('{"purchase_orders": "true"}', production=False)


class ExportServiceTests(SimpleTestCase):
    def test_export_service_is_importable(self):
        config = ExportConfig(
            headers=["id"],
            filename_prefix="items",
            rate_group="items_export_csv",
            audit_resource="item",
        )
        self.assertEqual(config.headers, ["id"])
        self.assertTrue(config.require_ordering)
        self.assertTrue(hasattr(ExportService, "export_stream"))

    def test_unordered_queryset_is_rejected_by_default(self):
        request = MagicMock()
        request.query_params = {}
        request.user = None
        queryset = MagicMock()
        queryset.ordered = False
        config = ExportConfig(
            headers=["id"],
            filename_prefix="items",
            rate_group="items_export_csv",
            audit_resource="item",
        )

        with self.assertRaises(ImproperlyConfigured):
            ExportService.export_stream(
                request=request,
                queryset=queryset,
                config=config,
                row_iter=iter([]),
                organization=None,
            )

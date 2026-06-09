from django.test import SimpleTestCase


class BackendFacadeTests(SimpleTestCase):
    def test_inventory_api_exports_lot_facade_methods(self):
        from inventory import api

        for name in (
            "get_or_create_lot",
            "increment_lot_balance",
            "validate_allocations_sum",
            "allocate_lots_fefo_fifo",
            "deplete_lot_balance",
        ):
            self.assertTrue(callable(getattr(api, name)))

    def test_backend_api_modules_are_importable(self):
        import audit.api
        import goods_receipts.api
        import purchase_orders.api
        import quick_sales.api

        self.assertTrue(callable(audit.api.log_audit_event))
        self.assertTrue(callable(goods_receipts.api.post_direct_receipt))
        self.assertTrue(callable(purchase_orders.api.generate_po_number))
        self.assertTrue(callable(quick_sales.api.create_quick_sale))

from django.dispatch import Signal

# Technical event for telemetry/non-audit consumers.
stock_movement_recorded = Signal()

# Business events for audit consumers.
goods_receipt_posted = Signal()
branch_transfer_dispatched = Signal()
branch_transfer_received = Signal()
quick_sale_created = Signal()
quick_sale_voided = Signal()

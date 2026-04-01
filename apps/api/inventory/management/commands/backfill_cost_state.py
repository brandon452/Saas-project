from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from goods_receipts.models import GoodsReceiptLine
from inventory.models import InventoryCostState, StockLedger, StockOnHand


Q4 = Decimal("0.0001")


class Command(BaseCommand):
    help = "Bootstrap InventoryCostState from historical goods receipts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Calculate results and print counts without writing changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        receipt_groups = defaultdict(list)
        for line in (
            GoodsReceiptLine.objects
            .filter(unit_cost__isnull=False)
            .select_related("receipt", "po_line__item", "item")
            .order_by("receipt__received_at", "pk")
        ):
            item = line.po_line.item if line.po_line_id else line.item
            if item is None:
                continue
            key = (line.receipt.organization_id, line.receipt.branch_id, item.id)
            receipt_groups[key].append(line)

        candidate_keys = set(receipt_groups.keys())
        candidate_keys.update(
            StockOnHand.objects.values_list("organization_id", "branch_id", "item_id")
        )

        bootstrapped = 0
        left_null = 0
        no_receipt_history = 0

        if dry_run:
            for key in sorted(candidate_keys):
                outcome = self._classify_key(key, receipt_groups.get(key, []))
                if outcome == "bootstrapped":
                    bootstrapped += 1
                elif outcome == "left_null":
                    left_null += 1
                else:
                    no_receipt_history += 1
        else:
            with transaction.atomic():
                for key in sorted(candidate_keys):
                    outcome = self._apply_key(key, receipt_groups.get(key, []))
                    if outcome == "bootstrapped":
                        bootstrapped += 1
                    elif outcome == "left_null":
                        left_null += 1
                    else:
                        no_receipt_history += 1

        mode = "DRY RUN" if dry_run else "APPLIED"
        self.stdout.write(self.style.SUCCESS(f"backfill_cost_state {mode}"))
        self.stdout.write(f"Items bootstrapped: {bootstrapped}")
        self.stdout.write(f"Items left null: {left_null}")
        self.stdout.write(f"Items with no receipt history: {no_receipt_history}")

    def _classify_key(self, key, receipt_lines):
        if not receipt_lines:
            return "no_receipt_history"
        if self._has_mixed_history(key, receipt_lines):
            return "left_null"
        return "bootstrapped"

    def _apply_key(self, key, receipt_lines):
        organization_id, branch_id, item_id = key
        outcome = self._classify_key(key, receipt_lines)

        defaults = {
            "average_unit_cost": None,
            "latest_unit_cost": None,
            "last_receipt_at": None,
        }

        if outcome == "bootstrapped":
            numerator = Decimal("0")
            denominator = Decimal("0")
            latest_line = receipt_lines[-1]
            for line in receipt_lines:
                qty = Decimal(str(line.quantity_received))
                unit_cost = Decimal(str(line.unit_cost)).quantize(Q4)
                numerator += qty * unit_cost
                denominator += qty

            defaults = {
                "average_unit_cost": (numerator / denominator).quantize(Q4),
                "latest_unit_cost": Decimal(str(latest_line.unit_cost)).quantize(Q4),
                "last_receipt_at": latest_line.receipt.received_at,
            }

        InventoryCostState.objects.update_or_create(
            organization_id=organization_id,
            branch_id=branch_id,
            item_id=item_id,
            defaults=defaults,
        )
        return outcome

    def _has_mixed_history(self, key, receipt_lines):
        organization_id, branch_id, item_id = key
        first_receipt_at = receipt_lines[0].receipt.received_at
        last_receipt_at = receipt_lines[-1].receipt.received_at
        return StockLedger.objects.filter(
            organization_id=organization_id,
            branch_id=branch_id,
            item_id=item_id,
            occurred_at__gte=first_receipt_at,
            occurred_at__lte=last_receipt_at,
        ).exclude(movement_type=StockLedger.MOVEMENT_RECEIPT).exists()

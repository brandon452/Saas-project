"""
Management command: backfill_lot_opening

Creates synthetic opening lots for lot-tracked items that have existing positive
StockOnHand but no InventoryLotBalance rows yet.

Usage:
  python manage.py backfill_lot_opening
  python manage.py backfill_lot_opening --org <org-id>
  python manage.py backfill_lot_opening --dry-run
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import InventoryLotBalance, OrgItem, StockOnHand


class Command(BaseCommand):
    help = "Create synthetic opening lots for lot-tracked items with existing stock but no lot balances."

    def add_arguments(self, parser):
        parser.add_argument(
            "--org",
            dest="org_id",
            help="Restrict to a specific organisation UUID.",
            default=None,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Preview what would be created without writing anything.",
        )

    def handle(self, *args, **options):
        org_id = options.get("org_id")
        dry_run = options.get("dry_run", False)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be written."))

        # Filter lot-tracked OrgItems
        org_item_qs = OrgItem.objects.filter(is_lot_tracked=True).select_related(
            "organization", "master_item"
        )
        if org_id:
            org_item_qs = org_item_qs.filter(organization_id=org_id)

        today_str = date.today().strftime("%Y-%m-%d")
        created_count = 0
        skipped_count = 0
        warning_count = 0

        # Gather all positive StockOnHand rows for lot-tracked items
        soh_rows = StockOnHand.objects.filter(
            item__is_lot_tracked=True,
        ).select_related("branch", "item__organization")

        if org_id:
            soh_rows = soh_rows.filter(organization_id=org_id)

        for soh in soh_rows:
            if soh.quantity < 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"WARNING: Negative SOH for {soh.item.sku} at branch {soh.branch.name} "
                        f"({soh.quantity}) — skipping."
                    )
                )
                warning_count += 1
                continue

            if soh.quantity == 0:
                continue

            lot_code = f"OPENING-{today_str}-{soh.branch.pk}"

            # Idempotent: skip if lot already exists
            already_exists = InventoryLotBalance.objects.filter(
                organization=soh.organization,
                branch=soh.branch,
                org_item=soh.item,
                lot_code=lot_code,
            ).exists()

            if already_exists:
                skipped_count += 1
                continue

            self.stdout.write(
                f"{'[DRY RUN] Would create' if dry_run else 'Creating'} opening lot: "
                f"item={soh.item.sku}, branch={soh.branch.name}, "
                f"lot_code={lot_code}, qty={soh.quantity}"
            )

            if not dry_run:
                with transaction.atomic():
                    InventoryLotBalance.objects.get_or_create(
                        organization=soh.organization,
                        branch=soh.branch,
                        org_item=soh.item,
                        lot_code=lot_code,
                        defaults={
                            "available_qty": soh.quantity,
                            "expiry_date": None,
                            "manufacture_date": None,
                        },
                    )
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {created_count}, "
                f"Already existed (skipped): {skipped_count}, "
                f"Warnings (negative SOH): {warning_count}."
            )
        )

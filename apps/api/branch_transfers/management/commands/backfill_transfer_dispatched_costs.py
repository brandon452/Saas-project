from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from branch_transfers.models import BranchTransfer, BranchTransferLine
from inventory.api import get_inventory_cost_state_for_update


class Command(BaseCommand):
    help = (
        "Backfill missing branch transfer line dispatched_unit_cost for IN_TRANSIT transfers "
        "using source branch AVCO."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--transfer-id",
            dest="transfer_id",
            help="Optional transfer UUID to scope the backfill.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview updates without writing changes.",
        )

    def handle(self, *args, **options):
        transfer_id = options.get("transfer_id")
        dry_run = bool(options.get("dry_run"))

        transfers = BranchTransfer.objects.filter(status=BranchTransfer.IN_TRANSIT)
        if transfer_id:
            transfers = transfers.filter(pk=transfer_id)

        updated = 0
        skipped = 0
        scanned = 0

        for transfer in transfers.iterator():
            with transaction.atomic():
                lines = BranchTransferLine.objects.select_for_update().filter(
                    transfer=transfer,
                    dispatched_unit_cost__isnull=True,
                )
                for line in lines:
                    scanned += 1
                    cost_state = get_inventory_cost_state_for_update(
                        organization=transfer.organization,
                        branch=transfer.from_branch,
                        item=line.item,
                    )
                    average_cost = (
                        cost_state.average_unit_cost
                        if cost_state is not None
                        else None
                    )
                    if average_cost is None:
                        skipped += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipped line {line.pk} on transfer {transfer.pk}: "
                                "missing source AVCO."
                            )
                        )
                        continue

                    quantized = Decimal(average_cost).quantize(Decimal("0.0001"))
                    if dry_run:
                        self.stdout.write(
                            f"[dry-run] Would set line {line.pk} on transfer {transfer.pk} "
                            f"to dispatched_unit_cost={quantized}"
                        )
                    else:
                        line.dispatched_unit_cost = quantized
                        line.save(update_fields=["dispatched_unit_cost"])
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Updated line {line.pk} on transfer {transfer.pk} "
                                f"to dispatched_unit_cost={quantized}"
                            )
                        )
                        updated += 1

        self.stdout.write(
            f"Backfill complete. scanned={scanned} updated={updated} skipped={skipped} dry_run={dry_run}"
        )

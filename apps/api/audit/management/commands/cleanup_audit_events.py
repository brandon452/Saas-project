import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from audit.models import AuditEvent

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Delete audit events older than retention threshold in batches."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Rows deleted per batch iteration.",
        )

    def handle(self, *args, **options):
        retention_days = int(getattr(settings, "AUDIT_RETENTION_DAYS", 365))
        batch_size = max(1, int(options["batch_size"]))
        threshold = timezone.now() - timedelta(days=retention_days)
        total_deleted = 0

        while True:
            with transaction.atomic():
                ids = list(
                    AuditEvent.objects.filter(occurred_at__lt=threshold)
                    .order_by("occurred_at")
                    .values_list("id", flat=True)[:batch_size]
                )
                if not ids:
                    break
                deleted, _ = AuditEvent.objects.filter(id__in=ids).delete()
            total_deleted += deleted

        message = (
            f"Audit cleanup completed. threshold={threshold.isoformat()} "
            f"batch_size={batch_size} deleted={total_deleted}"
        )
        logger.info(message)
        self.stdout.write(self.style.SUCCESS(message))

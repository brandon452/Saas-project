from django.db import migrations, models
from django.db.models import Count
from django.db.models import Q


EVENT_TYPES = [
    "goods_receipt.created",
    "branch_transfer.dispatched",
    "branch_transfer.received_complete",
    "branch_transfer.received_with_variance",
    "quick_sale.created",
    "quick_sale.voided",
]


def dedupe_audit_events(apps, schema_editor):
    AuditEvent = apps.get_model("audit", "AuditEvent")
    duplicates = (
        AuditEvent.objects.filter(event_type__in=EVENT_TYPES)
        .values("organization_id", "event_type", "resource_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )
    for dup in duplicates.iterator():
        rows = AuditEvent.objects.filter(
            organization_id=dup["organization_id"],
            event_type=dup["event_type"],
            resource_id=dup["resource_id"],
        ).order_by("occurred_at", "id")
        keep = rows.first()
        if keep is None:
            continue
        rows.exclude(id=keep.id).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0002_alter_auditevent_diff_json"),
    ]

    operations = [
        migrations.RunPython(dedupe_audit_events, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="auditevent",
            constraint=models.UniqueConstraint(
                fields=("organization", "event_type", "resource_id"),
                condition=Q(event_type__in=EVENT_TYPES),
                name="audit_unique_org_event_resource_event_audit",
            ),
        ),
    ]

import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tenancy", "0006_organization_operational_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                ("actor_type", models.CharField(choices=[("user", "User"), ("system", "System")], default="user", max_length=10)),
                ("actor_email_snapshot", models.CharField(blank=True, default="", max_length=255)),
                ("actor_name_snapshot", models.CharField(blank=True, default="", max_length=255)),
                ("event_type", models.CharField(max_length=64)),
                ("resource_type", models.CharField(max_length=64)),
                ("resource_id", models.CharField(max_length=64)),
                ("summary", models.CharField(max_length=255)),
                ("metadata_json", models.JSONField(blank=True, default=dict)),
                ("diff_json", models.JSONField(blank=True, default=dict)),
                (
                    "actor_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="audit_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(on_delete=models.CASCADE, related_name="audit_events", to="tenancy.organization"),
                ),
            ],
            options={
                "ordering": ["-occurred_at"],
            },
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["organization", "-occurred_at"], name="audit_org_occ_idx"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["organization", "event_type", "-occurred_at"], name="audit_org_evt_occ_idx"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(
                fields=["organization", "resource_type", "resource_id", "-occurred_at"],
                name="audit_org_res_occ_idx",
            ),
        ),
    ]

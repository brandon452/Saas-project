import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0006_branch_item"),
        ("branches", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StockTake",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                (
                    "organization",
                    models.ForeignKey(
                        to="tenancy.organization",
                        on_delete=django.db.models.deletion.PROTECT,
                        db_index=True,
                    ),
                ),
                (
                    "branch",
                    models.ForeignKey(
                        to="branches.branch",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="stock_takes",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("DRAFT", "Draft"),
                            ("IN_PROGRESS", "In Progress"),
                            ("PENDING_APPROVAL", "Pending Approval"),
                            ("COMPLETED", "Completed"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="DRAFT",
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL,
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_stock_takes",
                    ),
                ),
                (
                    "started_by",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL,
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="started_stock_takes",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL,
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="submitted_stock_takes",
                    ),
                ),
                (
                    "approved_by",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL,
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_stock_takes",
                    ),
                ),
                (
                    "cancelled_by",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL,
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cancelled_stock_takes",
                    ),
                ),
                ("started_at", models.DateTimeField(null=True, blank=True)),
                ("submitted_at", models.DateTimeField(null=True, blank=True)),
                ("approved_at", models.DateTimeField(null=True, blank=True)),
                ("cancelled_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="StockTakeLine",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "stock_take",
                    models.ForeignKey(
                        to="inventory.stocktake",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lines",
                    ),
                ),
                (
                    "org_item",
                    models.ForeignKey(
                        to="inventory.orgitem",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="stock_take_lines",
                    ),
                ),
                ("snapshot_quantity", models.DecimalField(max_digits=12, decimal_places=4)),
                (
                    "counted_quantity",
                    models.DecimalField(
                        max_digits=12,
                        decimal_places=4,
                        null=True,
                        blank=True,
                    ),
                ),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="stocktakeline",
            unique_together={("stock_take", "org_item")},
        ),
    ]

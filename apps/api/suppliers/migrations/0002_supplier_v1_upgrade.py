import re

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_supplier_codes(apps, schema_editor):
    """
    Generate SUP-XXXX codes for suppliers that don't have one yet.
    Sequence per org starts from the highest existing numeric suffix + 1,
    preventing collisions with any manually assigned codes.
    """
    Supplier = apps.get_model("suppliers", "Supplier")
    db_alias = schema_editor.connection.alias

    org_ids = (
        Supplier.objects.using(db_alias)
        .filter(code="")
        .values_list("organization_id", flat=True)
        .distinct()
    )

    for org_id in org_ids:
        # Lock all suppliers for this org to prevent race conditions.
        suppliers_without_code = (
            Supplier.objects.using(db_alias)
            .select_for_update()
            .filter(organization_id=org_id, code="")
            .order_by("id")
        )

        # Compute the starting sequence from existing codes in this org.
        existing_codes = (
            Supplier.objects.using(db_alias)
            .filter(organization_id=org_id)
            .exclude(code="")
            .values_list("code", flat=True)
        )
        max_suffix = 0
        for code in existing_codes:
            match = re.match(r"^SUP-(\d+)$", code)
            if match:
                max_suffix = max(max_suffix, int(match.group(1)))

        counter = max_suffix + 1
        for supplier in suppliers_without_code:
            supplier.code = f"SUP-{counter:04d}"
            supplier.save(update_fields=["code"])
            counter += 1


def reverse_backfill_supplier_codes(apps, schema_editor):
    # Reversing the backfill would remove all codes, which is safe for rollback.
    Supplier = apps.get_model("suppliers", "Supplier")
    Supplier.objects.using(schema_editor.connection.alias).update(code="")


class Migration(migrations.Migration):

    dependencies = [
        ("suppliers", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Rename the name column to display_name.
        migrations.RenameField(
            model_name="supplier",
            old_name="name",
            new_name="display_name",
        ),

        # 2. Drop the old name-based uniqueness constraint.
        migrations.RemoveConstraint(
            model_name="supplier",
            name="unique_supplier_name_per_org",
        ),

        # 3. Add the new display_name uniqueness constraint.
        migrations.AddConstraint(
            model_name="supplier",
            constraint=models.UniqueConstraint(
                fields=["organization", "display_name"],
                name="unique_supplier_display_name_per_org",
            ),
        ),

        # 4. Fix Meta.ordering to reference the renamed column.
        migrations.AlterModelOptions(
            name="supplier",
            options={"ordering": ["display_name"]},
        ),

        # 5. Add the new optional business fields (all nullable/blank in Phase 1).
        migrations.AddField(
            model_name="supplier",
            name="code",
            field=models.CharField(max_length=20, blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="supplier",
            name="legal_name",
            field=models.CharField(max_length=255, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="email",
            field=models.EmailField(blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="phone",
            field=models.CharField(max_length=50, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="payment_terms_days",
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="default_lead_time_days",
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="currency",
            field=models.CharField(max_length=3, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="tax_id",
            field=models.CharField(max_length=50, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="address_line1",
            field=models.CharField(max_length=255, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="address_line2",
            field=models.CharField(max_length=255, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="city",
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="state",
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="postal_code",
            field=models.CharField(max_length=20, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="country",
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="notes",
            field=models.TextField(blank=True),
        ),

        # 6. Backfill codes for all existing suppliers before adding the constraint.
        migrations.RunPython(
            backfill_supplier_codes,
            reverse_code=reverse_backfill_supplier_codes,
        ),

        # 7. Now add the org-scoped unique constraint on code (safe after backfill).
        migrations.AddConstraint(
            model_name="supplier",
            constraint=models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_supplier_code_per_org",
            ),
        ),

        # 8. Create the SupplierContact table.
        migrations.CreateModel(
            name="SupplierContact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=255)),
                ("role", models.CharField(max_length=100, blank=True)),
                ("email", models.EmailField(blank=True)),
                ("phone", models.CharField(max_length=50, blank=True)),
                ("is_primary", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contacts",
                        to="suppliers.supplier",
                    ),
                ),
            ],
        ),

        # 9. Add the partial unique index for active primary contact.
        migrations.AddConstraint(
            model_name="suppliercontact",
            constraint=models.UniqueConstraint(
                fields=["supplier"],
                condition=models.Q(is_primary=True, is_active=True),
                name="unique_active_primary_contact_per_supplier",
            ),
        ),
    ]

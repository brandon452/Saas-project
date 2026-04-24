import uuid

import django.db.models.deletion
from django.db import migrations, models


DEFAULT_PARENT_COMPANY_SLUG = "default-parent-company"


def backfill_parent_company(apps, schema_editor):
    ParentCompany = apps.get_model("tenancy", "ParentCompany")
    Organization = apps.get_model("tenancy", "Organization")
    ParentCompanyMember = apps.get_model("tenancy", "ParentCompanyMember")

    parent_company, _ = ParentCompany.objects.get_or_create(
        slug=DEFAULT_PARENT_COMPANY_SLUG,
        defaults={"name": "Default Parent Company", "is_active": True},
    )
    Organization.objects.filter(parent_company__isnull=True).update(parent_company=parent_company)
    ParentCompanyMember.objects.filter(parent_company__isnull=True).update(parent_company=parent_company)


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0004_parentcompanymember"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParentCompany",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(db_index=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Parent Company",
                "verbose_name_plural": "Parent Companies",
            },
        ),
        migrations.AddField(
            model_name="organization",
            name="parent_company",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="organizations",
                to="tenancy.parentcompany",
            ),
        ),
        migrations.AddField(
            model_name="parentcompanymember",
            name="parent_company",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="members",
                to="tenancy.parentcompany",
            ),
        ),
        migrations.RunPython(backfill_parent_company, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="organization",
            name="parent_company",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="organizations",
                to="tenancy.parentcompany",
            ),
        ),
        migrations.AlterField(
            model_name="parentcompanymember",
            name="parent_company",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="members",
                to="tenancy.parentcompany",
            ),
        ),
    ]

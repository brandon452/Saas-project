from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("suppliers", "0002_supplier_v1_upgrade"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="supplier",
            name="unique_supplier_code_per_org",
        ),
        migrations.AddConstraint(
            model_name="supplier",
            constraint=models.UniqueConstraint(
                fields=("organization", "code"),
                condition=~models.Q(code=""),
                name="unique_supplier_code_per_org",
            ),
        ),
    ]

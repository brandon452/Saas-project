from django.conf import settings
from django.db import models

from tenancy.models import TenantModel


class Supplier(TenantModel):
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_suppliers",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="unique_supplier_name_per_org",
            )
        ]

    def __str__(self):
        return self.name

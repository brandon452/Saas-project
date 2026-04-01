from django.conf import settings
from django.db import models

from tenancy.models import TenantModel


class Supplier(TenantModel):
    display_name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, blank=True)
    legal_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    payment_terms_days = models.PositiveIntegerField(null=True, blank=True)
    default_lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
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
        ordering = ["display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "display_name"],
                name="unique_supplier_display_name_per_org",
            ),
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_supplier_code_per_org",
            ),
        ]

    def __str__(self):
        return self.display_name

    # Phase 1 backward-compatibility alias — remove in Phase 3
    @property
    def name(self):
        return self.display_name


class SupplierContact(models.Model):
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Partial unique index: at most one active primary contact per supplier.
        # Enforced at DB level; service layer must clear the old primary before
        # setting a new one (see set_primary action).
        constraints = [
            models.UniqueConstraint(
                fields=["supplier"],
                condition=models.Q(is_primary=True, is_active=True),
                name="unique_active_primary_contact_per_supplier",
            ),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.supplier})"

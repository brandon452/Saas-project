import uuid

from django.conf import settings
from django.db import models

from .managers import TenantManager


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class TenantModel(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, db_index=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True


class OrganizationMember(models.Model):
    ROLE_OWNER = "OWNER"
    ROLE_ADMIN = "ADMIN"
    ROLE_STAFF = "STAFF"

    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_STAFF, "Staff"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("user", "organization")]

    def __str__(self):
        return f"{self.user_id}:{self.organization_id}:{self.role}"

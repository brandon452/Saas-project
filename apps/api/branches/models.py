import uuid

from django.db import models

from tenancy.models import TenantModel


class Branch(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)

    class Meta:
        unique_together = [("organization", "code")]
        indexes = [models.Index(fields=["organization", "code"])]

    def __str__(self):
        return f"{self.code} ({self.name})"

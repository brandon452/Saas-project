import uuid

from django.conf import settings
from django.db import models

from .managers import OrganizationMemberManager, TenantManager


DEFAULT_PARENT_COMPANY_SLUG = "default-parent-company"


def get_default_parent_company():
    return ParentCompany.objects.get_or_create(
        slug=DEFAULT_PARENT_COMPANY_SLUG,
        defaults={"name": "Default Parent Company"},
    )[0]


class ParentCompany(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Parent Company"
        verbose_name_plural = "Parent Companies"

    def __str__(self):
        return self.name


class Organization(models.Model):
    DEFAULT_CURRENCY = "USD"
    DEFAULT_TIMEZONE = "UTC"
    DEFAULT_PURCHASE_ORDER_PREFIX = "PO"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent_company = models.ForeignKey(
        ParentCompany,
        on_delete=models.PROTECT,
        related_name="organizations",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    default_currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    default_timezone = models.CharField(max_length=64, default=DEFAULT_TIMEZONE)
    allow_negative_stock = models.BooleanField(default=False)
    purchase_order_prefix = models.CharField(max_length=12, default=DEFAULT_PURCHASE_ORDER_PREFIX)
    purchase_order_next_number = models.PositiveIntegerField(default=1)
    branch_transfer_approval_required = models.BooleanField(default=True)
    stock_take_approval_required = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.parent_company_id:
            self.parent_company = get_default_parent_company()
        return super().save(*args, **kwargs)


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
    assigned_branch = models.ForeignKey(
        "branches.Branch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_members",
        help_text=(
            "Required for STAFF. Must be null for OWNER and ADMIN. "
            "Restricts the STAFF member to this branch only. "
            "Must belong to the same organization as this membership."
        ),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    objects = OrganizationMemberManager()
    all_objects = models.Manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"],
                name="uniq_org_member_user_org",
            )
        ]

    def __str__(self):
        return f"{self.user_id}:{self.organization_id}:{self.role}"


class ParentCompanyMember(models.Model):
    PARENT_ADMIN = "PARENT_ADMIN"
    PARENT_VIEWER = "PARENT_VIEWER"

    ROLE_CHOICES = [
        (PARENT_ADMIN, "Parent Admin"),
        (PARENT_VIEWER, "Parent Viewer"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_membership",
    )
    parent_company = models.ForeignKey(
        ParentCompany,
        on_delete=models.PROTECT,
        related_name="members",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_parent_members",
    )
    objects = models.Manager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = "Parent Company Member"
        verbose_name_plural = "Parent Company Members"

    def __str__(self):
        return f"{self.user} - {self.role}"

    def save(self, *args, **kwargs):
        if not self.parent_company_id:
            self.parent_company = get_default_parent_company()
        return super().save(*args, **kwargs)

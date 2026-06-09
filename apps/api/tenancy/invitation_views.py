from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.timezone import now
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth.models import PasswordSetToken
from branches.api import Branch, get_branch_for_org
from django.conf import settings
from django.utils.text import slugify

from .models import Organization, OrganizationMember, ParentCompany, ParentCompanyMember, get_default_parent_company
from .permissions import IsOrgMemberOrParent, get_member_role, get_parent_membership

User = get_user_model()

INVITE_EXPIRY_DAYS = 7

# Roles that can be assigned via the org create-user endpoint (excludes parent roles)
ASSIGNABLE_ORG_ROLES = {
    OrganizationMember.ROLE_OWNER,
    OrganizationMember.ROLE_ADMIN,
    OrganizationMember.ROLE_STAFF,
}

# Which org roles each requester level may assign
ROLE_CAN_ASSIGN = {
    "PARENT_ADMIN": {OrganizationMember.ROLE_OWNER, OrganizationMember.ROLE_ADMIN, OrganizationMember.ROLE_STAFF},
    OrganizationMember.ROLE_OWNER: {OrganizationMember.ROLE_ADMIN, OrganizationMember.ROLE_STAFF},
}


def _build_set_password_url(token):
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return f"{frontend_url}/set-password/{token}"


def _validate_new_user_email(email):
    """Raise ValidationError if email or derived username already exists."""
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({"email": "An account with this email already exists."})
    if User.objects.filter(username__iexact=email).exists():
        raise ValidationError({"email": "An account with this username already exists."})


def _create_password_set_token(user, organization, created_by):
    """Invalidate prior unused tokens and create a new one."""
    PasswordSetToken.objects.filter(
        user=user,
        organization=organization,
        used_at__isnull=True,
    ).update(used_at=now())

    return PasswordSetToken.objects.create(
        user=user,
        organization=organization,
        created_by=created_by,
        expires_at=now() + timedelta(days=INVITE_EXPIRY_DAYS),
    )


class CreateUserView(APIView):
    """
    POST /api/orgs/{orgId}/create-user/
    Creates a new user account + org membership and returns a one-time
    set-password link. Accessible by OWNER or PARENT_ADMIN only.
    """

    permission_classes = [IsAuthenticated, IsOrgMemberOrParent]

    def initial(self, request, *args, **kwargs):
        org_id = self.kwargs.get("org_id")
        try:
            request.org = Organization.objects.get(pk=org_id, is_active=True)
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")

        parent_membership = get_parent_membership(request)
        request.parent_role = parent_membership.role if parent_membership else None
        super().initial(request, *args, **kwargs)

    def post(self, request, org_id=None):
        parent_role = request.parent_role
        org_role = get_member_role(request)

        # Only OWNER or PARENT_ADMIN may create accounts
        if parent_role == "PARENT_ADMIN":
            requester_level = "PARENT_ADMIN"
        elif org_role == OrganizationMember.ROLE_OWNER:
            requester_level = OrganizationMember.ROLE_OWNER
        else:
            raise PermissionDenied("Only OWNER or PARENT_ADMIN can create user accounts.")

        email = (request.data.get("email") or "").strip().lower()
        first_name = (request.data.get("first_name") or "").strip()
        last_name = (request.data.get("last_name") or "").strip()
        role = (request.data.get("role") or "").strip().upper()
        assigned_branch_id = request.data.get("assigned_branch") or None

        # Basic field validation
        if not email:
            raise ValidationError({"email": "This field is required."})
        if not first_name:
            raise ValidationError({"first_name": "This field is required."})
        if not last_name:
            raise ValidationError({"last_name": "This field is required."})
        if role not in ASSIGNABLE_ORG_ROLES:
            raise ValidationError({"role": f"Must be one of: {', '.join(sorted(ASSIGNABLE_ORG_ROLES))}."})

        # Hierarchy check
        allowed_roles = ROLE_CAN_ASSIGN.get(requester_level, set())
        if role not in allowed_roles:
            raise PermissionDenied(f"You cannot assign the {role} role.")

        # Role/branch validation
        assigned_branch = None
        if role in (OrganizationMember.ROLE_OWNER, OrganizationMember.ROLE_ADMIN):
            if assigned_branch_id:
                raise ValidationError({"assigned_branch": "OWNER and ADMIN must not have an assigned branch."})
        elif role == OrganizationMember.ROLE_STAFF:
            if not assigned_branch_id:
                raise ValidationError({"assigned_branch": "STAFF must have an assigned branch."})
            try:
                assigned_branch = get_branch_for_org(branch_id=assigned_branch_id, organization=request.org)
            except Branch.DoesNotExist:
                raise ValidationError({"assigned_branch": "Branch not found in this organization."})

        # Email/username uniqueness
        _validate_new_user_email(email)

        # Defensive: no existing active membership
        if OrganizationMember.objects.for_org(request.org).filter(
            user__email__iexact=email, is_active=True
        ).exists():
            raise ValidationError({"email": "An active member with this email already exists in this organization."})

        with transaction.atomic():
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=None,
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])

            OrganizationMember.objects.create(
                user=user,
                organization=request.org,
                role=role,
                assigned_branch=assigned_branch,
            )

            token = _create_password_set_token(user, request.org, request.user)

        return Response(
            {
                "user_id": user.id,
                "email": user.email,
                "set_password_url": _build_set_password_url(token.token),
            },
            status=status.HTTP_201_CREATED,
        )


class CreateParentMemberView(APIView):
    """
    POST /api/parent/create-parent-member/
    Superuser-only operator bootstrap endpoint. Creates a new user account
    + ParentCompanyMember (PARENT_ADMIN or PARENT_VIEWER) and returns a
    one-time set-password link. No app UI — call via Postman/curl.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied("Only Django superusers can create parent members.")

        email = (request.data.get("email") or "").strip().lower()
        first_name = (request.data.get("first_name") or "").strip()
        last_name = (request.data.get("last_name") or "").strip()
        role = (request.data.get("role") or "").strip().upper()
        parent_company_name = (request.data.get("parent_company_name") or "").strip()
        parent_company_slug = (request.data.get("parent_company_slug") or "").strip()

        valid_roles = {ParentCompanyMember.PARENT_ADMIN, ParentCompanyMember.PARENT_VIEWER}

        if not email:
            raise ValidationError({"email": "This field is required."})
        if not first_name:
            raise ValidationError({"first_name": "This field is required."})
        if not last_name:
            raise ValidationError({"last_name": "This field is required."})
        if role not in valid_roles:
            raise ValidationError({"role": "Must be PARENT_ADMIN or PARENT_VIEWER."})

        _validate_new_user_email(email)

        # Defensive: no existing parent membership
        if ParentCompanyMember.objects.filter(user__email__iexact=email).exists():
            raise ValidationError({"email": "A parent member with this email already exists."})

        with transaction.atomic():
            if parent_company_name:
                slug = parent_company_slug or slugify(parent_company_name)
                parent_company, _ = ParentCompany.objects.get_or_create(
                    slug=slug,
                    defaults={"name": parent_company_name},
                )
            else:
                parent_company = get_default_parent_company()

            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=None,
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])

            ParentCompanyMember.objects.create(
                user=user,
                parent_company=parent_company,
                role=role,
                created_by=request.user,
            )

            token = _create_password_set_token(user, organization=None, created_by=request.user)

        return Response(
            {
                "user_id": user.id,
                "email": user.email,
                "parent_company_id": parent_company.id,
                "parent_company_name": parent_company.name,
                "role": role,
                "set_password_url": _build_set_password_url(token.token),
            },
            status=status.HTTP_201_CREATED,
        )

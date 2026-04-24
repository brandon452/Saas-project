from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from auth.mixins import AuthCookieMixin

from .invitation_views import _build_set_password_url, _create_password_set_token, _validate_new_user_email
from .models import ParentCompany, ParentCompanyMember
from .serializers import ParentCompanySerializer

User = get_user_model()


def _setup_required():
    return not ParentCompanyMember.objects.filter(
        is_active=True,
        role=ParentCompanyMember.PARENT_ADMIN,
        parent_company__is_active=True,
    ).exists()


def _validate_parent_company_payload(data):
    name = (data.get("parent_company_name") or "").strip()
    slug = (data.get("parent_company_slug") or "").strip() or slugify(name)
    if not name:
        raise ValidationError({"parent_company_name": "This field is required."})
    if not slug:
        raise ValidationError({"parent_company_slug": "This field is required."})
    if ParentCompany.objects.filter(slug=slug).exists():
        raise ValidationError({"parent_company_slug": "A parent company with this slug already exists."})
    return name, slug


def _validate_admin_payload(data, *, require_password):
    email = (data.get("email") or "").strip().lower()
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    password = data.get("password") or ""

    if not email:
        raise ValidationError({"email": "This field is required."})
    if not first_name:
        raise ValidationError({"first_name": "This field is required."})
    if not last_name:
        raise ValidationError({"last_name": "This field is required."})
    if require_password and not password:
        raise ValidationError({"password": "This field is required."})

    _validate_new_user_email(email)

    if require_password:
        probe_user = User(username=email, email=email, first_name=first_name, last_name=last_name)
        try:
            validate_password(password, user=probe_user)
        except DjangoValidationError as exc:
            raise ValidationError({"password": list(exc.messages)})

    return email, first_name, last_name, password


class SetupStatusView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"setup_required": _setup_required()})


@method_decorator(csrf_exempt, name="dispatch")
class FirstRunSetupView(AuthCookieMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not _setup_required():
            return Response(
                {"detail": "First-run setup has already been completed."},
                status=status.HTTP_409_CONFLICT,
            )

        company_name, company_slug = _validate_parent_company_payload(request.data)
        email, first_name, last_name, password = _validate_admin_payload(
            request.data,
            require_password=True,
        )

        with transaction.atomic():
            parent_company = ParentCompany.objects.create(name=company_name, slug=company_slug)
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
            )
            ParentCompanyMember.objects.create(
                user=user,
                parent_company=parent_company,
                role=ParentCompanyMember.PARENT_ADMIN,
                created_by=user,
            )

        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                "detail": "Setup complete.",
                "parent_company": ParentCompanySerializer(parent_company).data,
            },
            status=status.HTTP_201_CREATED,
        )
        self.set_auth_cookies(response, refresh.access_token, refresh)
        get_token(request)
        return response


class OperatorParentCompanyView(APIView):
    permission_classes = [IsAuthenticated]

    def _require_superuser(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied("Only Django superusers can manage parent companies.")

    def get(self, request):
        self._require_superuser(request)
        parent_companies = ParentCompany.objects.order_by("name")
        return Response(ParentCompanySerializer(parent_companies, many=True).data)

    def post(self, request):
        self._require_superuser(request)
        company_name, company_slug = _validate_parent_company_payload(request.data)
        email, first_name, last_name, _password = _validate_admin_payload(
            request.data,
            require_password=False,
        )

        with transaction.atomic():
            parent_company = ParentCompany.objects.create(name=company_name, slug=company_slug)
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
                role=ParentCompanyMember.PARENT_ADMIN,
                created_by=request.user,
            )
            token = _create_password_set_token(user, organization=None, created_by=request.user)

        return Response(
            {
                "parent_company": ParentCompanySerializer(parent_company).data,
                "admin_email": user.email,
                "set_password_url": _build_set_password_url(token.token),
            },
            status=status.HTTP_201_CREATED,
        )

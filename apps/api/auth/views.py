import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from tenancy.models import OrganizationMember
from tenancy.permissions import get_parent_membership

from .mixins import AuthCookieMixin
from .models import AuthAuditLog, PasswordSetToken

logger = logging.getLogger(__name__)
User = get_user_model()


def enforce_csrf_or_403(request):
    check = CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise PermissionDenied(f"CSRF Failed: {reason}")


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=False), name="dispatch")
class LoginView(AuthCookieMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if getattr(request, "limited", False):
            self.log_auth_event(request, AuthAuditLog.RATE_LIMITED, reason="Login rate limit exceeded")
            return Response({"detail": "Too many requests."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")

        if not username or not password:
            return Response(
                {"detail": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)

        if user is None or not user.is_active:
            self.log_auth_event(
                request,
                AuthAuditLog.LOGIN_FAILURE,
                username=username,
                reason="Invalid credentials or inactive user",
            )
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        response = Response({"detail": "Login successful."})
        self.set_auth_cookies(response, access, refresh)
        get_token(request)

        self.log_auth_event(request, AuthAuditLog.LOGIN_SUCCESS, username=username)
        return response


@method_decorator(ratelimit(key="ip", rate="30/m", method="POST", block=False), name="dispatch")
class TokenRefreshView(AuthCookieMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        enforce_csrf_or_403(request)

        if getattr(request, "limited", False):
            self.log_auth_event(request, AuthAuditLog.RATE_LIMITED, reason="Refresh rate limit exceeded")
            return Response({"detail": "Too many requests."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        raw_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if not raw_refresh:
            return Response({"detail": "Refresh token not found."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            old_refresh = RefreshToken(raw_refresh)
            user_id = old_refresh["user_id"]
            user = User.objects.get(pk=user_id, is_active=True)
            old_refresh.blacklist()
            new_refresh = RefreshToken.for_user(user)
            new_access = new_refresh.access_token
        except (TokenError, InvalidToken):
            self.log_auth_event(
                request,
                AuthAuditLog.REFRESH_FAILURE,
                reason="Invalid or expired refresh token",
            )
            response = Response(
                {"detail": "Session expired. Please log in again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            self.clear_auth_cookies(response)
            return response
        except User.DoesNotExist:
            self.log_auth_event(request, AuthAuditLog.REFRESH_FAILURE, reason="User not found or inactive")
            response = Response({"detail": "User not found."}, status=status.HTTP_401_UNAUTHORIZED)
            self.clear_auth_cookies(response)
            return response

        response = Response({"detail": "Token refreshed."})
        self.set_auth_cookies(response, new_access, new_refresh)
        self.log_auth_event(request, AuthAuditLog.TOKEN_REFRESH, username=user.username)
        return response


class LogoutView(AuthCookieMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        enforce_csrf_or_403(request)

        username = ""
        raw_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)

        if raw_refresh:
            try:
                refresh = RefreshToken(raw_refresh)
                username = str(
                    User.objects.filter(pk=refresh["user_id"]).values_list("username", flat=True).first() or ""
                )
                refresh.blacklist()
            except Exception:
                logger.error("Error blacklisting refresh token during logout", exc_info=True)

        response = Response({"detail": "Logged out."})
        self.clear_auth_cookies(response)
        self.log_auth_event(request, AuthAuditLog.LOGOUT, username=username)
        return response


class PasswordSetDetailView(APIView):
    """
    GET /api/auth/set-password/{token}/
    Validates a password-set token and returns context for the set-password page.
    Unauthenticated token-based endpoint.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token=None):
        try:
            pst = PasswordSetToken.objects.select_related(
                "user", "organization"
            ).get(token=token)
        except PasswordSetToken.DoesNotExist:
            raise NotFound("This link is invalid.")

        if pst.used_at is not None:
            raise NotFound("This link has already been used.")

        if pst.expires_at < now():
            raise NotFound("This link has expired.")

        org_name = pst.organization.name if pst.organization_id else None

        # Derive parent_role from user's ParentCompanyMember if org is null
        parent_role = None
        parent_company_name = None
        if org_name is None:
            from tenancy.models import ParentCompanyMember
            try:
                pm = ParentCompanyMember.objects.select_related("parent_company").get(user=pst.user)
                parent_role = pm.role
                parent_company_name = pm.parent_company.name
            except ParentCompanyMember.DoesNotExist:
                pass

        return Response({
            "email": pst.user.email,
            "first_name": pst.user.first_name,
            "org_name": org_name,
            "parent_role": parent_role,
            "parent_company_name": parent_company_name,
        })


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=False), name="dispatch")
class PasswordSetAcceptView(AuthCookieMixin, APIView):
    """
    POST /api/auth/set-password/{token}/accept/
    Accepts a password-set token, sets the user's password, and issues JWT cookies.
    Unauthenticated token-based endpoint — @csrf_exempt for the same reason as
    LoginView: no session yet, token in URL is the auth factor, single-use +
    expiring + rate-limited.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, token=None):
        if getattr(request, "limited", False):
            return Response({"detail": "Too many requests."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        password = request.data.get("password", "")
        first_name = (request.data.get("first_name") or "").strip()
        last_name = (request.data.get("last_name") or "").strip()
        if not password:
            return Response({"detail": "Password is required."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                pst = (
                    PasswordSetToken.objects.select_for_update()
                    .select_related("user")
                    .get(token=token)
                )
            except PasswordSetToken.DoesNotExist:
                return Response({"detail": "This link is invalid."}, status=status.HTTP_400_BAD_REQUEST)

            if pst.used_at is not None:
                return Response({"detail": "This link has already been used."}, status=status.HTTP_400_BAD_REQUEST)

            if pst.expires_at < now():
                return Response({"detail": "This link has expired."}, status=status.HTTP_400_BAD_REQUEST)

            user = pst.user

            if user.has_usable_password():
                return Response(
                    {"detail": "Password has already been set for this account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                validate_password(password, user=user)
            except DjangoValidationError as exc:
                return Response({"detail": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

            # Lock the token row so only one request can consume it.
            user.set_password(password)
            update_fields = ["password"]
            if first_name:
                user.first_name = first_name
                update_fields.append("first_name")
            if last_name:
                user.last_name = last_name
                update_fields.append("last_name")
            user.save(update_fields=update_fields)
            pst.used_at = now()
            pst.save(update_fields=["used_at"])

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        response = Response({"detail": "Password set successfully."})
        self.set_auth_cookies(response, access, refresh)
        self.log_auth_event(request, AuthAuditLog.LOGIN_SUCCESS, username=user.username)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        parent_membership = get_parent_membership(request)
        memberships = (
            OrganizationMember.objects.filter(user=request.user, is_active=True)
            .select_related("organization", "assigned_branch")
            .order_by("organization__name")
        )

        return Response(
            {
                "id": request.user.id,
                "email": request.user.email,
                "first_name": request.user.first_name,
                "last_name": request.user.last_name,
                "is_superuser": request.user.is_superuser,
                "is_parent_member": parent_membership is not None,
                "parent_role": parent_membership.role if parent_membership else None,
                "parent_company_id": str(parent_membership.parent_company_id) if parent_membership else None,
                "parent_company_name": parent_membership.parent_company.name if parent_membership else None,
                "memberships": [
                    {
                        "org_id": str(membership.organization_id),
                        "org_name": membership.organization.name,
                        "role": membership.role,
                        "branch_id": str(membership.assigned_branch_id)
                        if membership.assigned_branch_id
                        else None,
                        "branch_name": membership.assigned_branch.name
                        if membership.assigned_branch
                        else None,
                    }
                    for membership in memberships
                ],
            }
        )

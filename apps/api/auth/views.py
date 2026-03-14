from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from django_ratelimit.decorators import ratelimit
from rest_framework.authentication import CSRFCheck
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from tenancy.models import OrganizationMember
from tenancy.permissions import get_parent_membership

from .mixins import AuthCookieMixin
from .models import AuthAuditLog

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
                pass

        response = Response({"detail": "Logged out."})
        self.clear_auth_cookies(response)
        self.log_auth_event(request, AuthAuditLog.LOGOUT, username=username)
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
                "is_parent_member": parent_membership is not None,
                "parent_role": parent_membership.role if parent_membership else None,
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

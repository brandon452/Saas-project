from django.conf import settings


class AuthCookieMixin:
    """Shared cookie and audit helpers for auth views."""

    def set_auth_cookies(self, response, access_token, refresh_token):
        response.set_cookie(
            key=settings.AUTH_COOKIE_ACCESS,
            value=str(access_token),
            max_age=settings.AUTH_COOKIE_ACCESS_MAX_AGE,
            secure=settings.AUTH_COOKIE_SECURE,
            httponly=settings.AUTH_COOKIE_HTTPONLY,
            samesite=settings.AUTH_COOKIE_SAMESITE,
            path=settings.AUTH_COOKIE_PATH,
            domain=settings.AUTH_COOKIE_DOMAIN,
        )
        response.set_cookie(
            key=settings.AUTH_COOKIE_REFRESH,
            value=str(refresh_token),
            max_age=settings.AUTH_COOKIE_REFRESH_MAX_AGE,
            secure=settings.AUTH_COOKIE_SECURE,
            httponly=settings.AUTH_COOKIE_HTTPONLY,
            samesite=settings.AUTH_COOKIE_SAMESITE,
            path=settings.AUTH_COOKIE_PATH,
            domain=settings.AUTH_COOKIE_DOMAIN,
        )

    def clear_auth_cookies(self, response):
        response.delete_cookie(
            key=settings.AUTH_COOKIE_ACCESS,
            path=settings.AUTH_COOKIE_PATH,
            domain=settings.AUTH_COOKIE_DOMAIN,
            samesite=settings.AUTH_COOKIE_SAMESITE,
        )
        response.delete_cookie(
            key=settings.AUTH_COOKIE_REFRESH,
            path=settings.AUTH_COOKIE_PATH,
            domain=settings.AUTH_COOKIE_DOMAIN,
            samesite=settings.AUTH_COOKIE_SAMESITE,
        )

    def log_auth_event(self, request, event, username="", reason=""):
        from .models import AuthAuditLog

        AuthAuditLog.objects.create(
            event=event,
            username=username,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            reason=reason,
        )

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

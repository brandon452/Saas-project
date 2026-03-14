from django.conf import settings
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class CookieJWTAuthentication(JWTAuthentication):
    """
    Cookie-first JWT authentication with Authorization header fallback.
    """

    def authenticate(self, request):
        raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)

        if raw_token is not None:
            try:
                validated_token = self.get_validated_token(raw_token)
            except (InvalidToken, TokenError):
                raise AuthenticationFailed("Access token is invalid or expired. Refresh your session.")
            self.enforce_csrf(request)
            return self.get_user(validated_token), validated_token

        return super().authenticate(request)

    def enforce_csrf(self, request):
        check = CSRFCheck(lambda req: None)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise PermissionDenied(f"CSRF Failed: {reason}")

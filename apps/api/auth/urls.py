from django.urls import path

from .views import LoginView, LogoutView, MeView, PasswordSetAcceptView, PasswordSetDetailView, TokenRefreshView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("set-password/<uuid:token>/", PasswordSetDetailView.as_view(), name="set-password-detail"),
    path("set-password/<uuid:token>/accept/", PasswordSetAcceptView.as_view(), name="set-password-accept"),
]

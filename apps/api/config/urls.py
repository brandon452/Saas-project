from django.contrib import admin
from django.urls import include, path, re_path

from config.views import FrontendView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("auth.urls")),
    path("api/", include("config.api_urls")),
    re_path(r"^(?!api/).*$", FrontendView.as_view(), name="frontend"),
]

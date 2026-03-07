from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from branches.views import BranchViewSet
from config.views import HealthView, MyOrganizationsView
from inventory.views import ItemViewSet, StockMovementViewSet, StockOnHandViewSet

router = DefaultRouter()
router.register("branches", BranchViewSet, basename="branch")
router.register("items", ItemViewSet, basename="item")
router.register("stock-on-hand", StockOnHandViewSet, basename="stock-on-hand")
router.register("stock-movements", StockMovementViewSet, basename="stock-movement")

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("me/orgs/", MyOrganizationsView.as_view(), name="my-orgs"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path(
        "inventory/movements/",
        StockMovementViewSet.as_view({"post": "create"}),
        name="inventory-movements-create",
    ),
    path("", include(router.urls)),
]

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from branches.views import BranchViewSet, NetworkBranchView
from config.views import HealthView
from branch_transfers.views import BranchTransferViewSet
from goods_receipts.views import GoodsReceiptViewSet
from inventory.views import ItemViewSet, StockMovementViewSet, StockOnHandViewSet
from purchase_orders.views import PurchaseOrderViewSet
from suppliers.views import SupplierViewSet
from tenancy.org_views import OrgGovernanceView, OrgListCreateView
from tenancy.parent_views import ParentMemberViewSet
from tenancy.views import MemberViewSet

org_router = DefaultRouter()
org_router.register("inventory/items", ItemViewSet, basename="item")
org_router.register("inventory/stock", StockOnHandViewSet, basename="stock")
org_router.register("inventory/movements", StockMovementViewSet, basename="movement")
org_router.register("branches", BranchViewSet, basename="branch")
org_router.register("members", MemberViewSet, basename="member")
org_router.register("suppliers", SupplierViewSet, basename="supplier")
org_router.register("purchase-orders", PurchaseOrderViewSet, basename="purchase-order")
org_router.register("goods-receipts", GoodsReceiptViewSet, basename="goods-receipt")
org_router.register("branch-transfers", BranchTransferViewSet, basename="branch-transfer")

parent_router = DefaultRouter()
parent_router.register("members", ParentMemberViewSet, basename="parent-member")

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("orgs/", OrgListCreateView.as_view(), name="org-list"),
    path("orgs/<uuid:org_id>/governance/", OrgGovernanceView.as_view(), name="org-governance"),
    path("orgs/<uuid:org_id>/network-branches/", NetworkBranchView.as_view(), name="network-branches"),
    path("orgs/<uuid:org_id>/", include(org_router.urls)),
    path("parent/", include(parent_router.urls)),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

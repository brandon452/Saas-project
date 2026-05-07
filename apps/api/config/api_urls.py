from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from branches.views import BranchViewSet, NetworkBranchView
from audit.views import AuditEventExportView, AuditEventListView
from config.views import HealthView
from branch_transfers.views import BranchTransferViewSet
from goods_receipts.views import GoodsReceiptViewSet
from inventory.views import (
    BranchItemBulkActivateView,
    BranchItemBulkDeactivateView,
    BranchItemCatalogView,
    BranchItemViewSet,
    ClosePeriodViewSet,
    MasterItemViewSet,
    OrgItemBulkActivateView,
    OrgItemViewSet,
    OrgMasterItemView,
    ScanResolveView,
    StockMovementViewSet,
    StockOnHandViewSet,
    StockTakeViewSet,
)
from purchase_orders.views import PurchaseOrderViewSet
from quick_sales.views import QuickSaleViewSet
from reports.views import (
    InventoryAgingExportView,
    InventoryAgingView,
    PurchaseCostTrendView,
    SlowDeadStockExportView,
    SlowDeadStockView,
    StockValuationExportView,
    StockValuationView,
)
from suppliers.views import SupplierViewSet
from tenancy.invitation_views import CreateParentMemberView, CreateUserView
from tenancy.org_views import OrgGovernanceView, OrgListCreateView, OrgSettingsView
from tenancy.parent_views import ParentMemberViewSet
from tenancy.setup_views import FirstRunSetupView, OperatorParentCompanyView, SetupStatusView
from tenancy.views import MemberSearchView, MemberViewSet

org_router = DefaultRouter()
org_router.register("inventory/items", OrgItemViewSet, basename="item")
org_router.register("branch-items", BranchItemViewSet, basename="branch-item")
org_router.register("inventory/stock", StockOnHandViewSet, basename="stock")
org_router.register("inventory/movements", StockMovementViewSet, basename="movement")
org_router.register("stock-takes", StockTakeViewSet, basename="stock-take")
org_router.register("close-periods", ClosePeriodViewSet, basename="close-period")
org_router.register("branches", BranchViewSet, basename="branch")
org_router.register("members", MemberViewSet, basename="member")
org_router.register("suppliers", SupplierViewSet, basename="supplier")
org_router.register("purchase-orders", PurchaseOrderViewSet, basename="purchase-order")
org_router.register("goods-receipts", GoodsReceiptViewSet, basename="goods-receipt")
org_router.register("branch-transfers", BranchTransferViewSet, basename="branch-transfer")
org_router.register("quick-sales", QuickSaleViewSet, basename="quick-sale")

parent_router = DefaultRouter()
parent_router.register("members", ParentMemberViewSet, basename="parent-member")
parent_router.register("master-items", MasterItemViewSet, basename="master-item")

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("setup/status/", SetupStatusView.as_view(), name="setup-status"),
    path("setup/first-run/", FirstRunSetupView.as_view(), name="setup-first-run"),
    path("operator/parent-companies/", OperatorParentCompanyView.as_view(), name="operator-parent-companies"),
    path("orgs/", OrgListCreateView.as_view(), name="org-list"),
    path("orgs/<uuid:org_id>/governance/", OrgGovernanceView.as_view(), name="org-governance"),
    path("orgs/<uuid:org_id>/settings/", OrgSettingsView.as_view(), name="org-settings"),
    path("orgs/<uuid:org_id>/audit-events/", AuditEventListView.as_view(), name="org-audit-events"),
    path("orgs/<uuid:org_id>/audit-events/export/", AuditEventExportView.as_view(), name="org-audit-events-export"),
    path("orgs/<uuid:org_id>/network-branches/", NetworkBranchView.as_view(), name="network-branches"),
    path("orgs/<uuid:org_id>/master-items/", OrgMasterItemView.as_view(), name="org-master-items"),
    path("orgs/<uuid:org_id>/members/search/", MemberSearchView.as_view(), name="member-search"),
    path("orgs/<uuid:org_id>/create-user/", CreateUserView.as_view(), name="create-user"),
    path("parent/create-parent-member/", CreateParentMemberView.as_view(), name="create-parent-member"),
    path(
        "orgs/<uuid:org_id>/reports/purchase-cost-trend/",
        PurchaseCostTrendView.as_view(),
        name="purchase-cost-trend",
    ),
    path(
        "orgs/<uuid:org_id>/reports/stock-valuation/",
        StockValuationView.as_view(),
        name="stock-valuation",
    ),
    path(
        "orgs/<uuid:org_id>/reports/stock-valuation/export/csv/",
        StockValuationExportView.as_view(),
        name="stock-valuation-export-csv",
    ),
    path(
        "orgs/<uuid:org_id>/reports/inventory-aging/",
        InventoryAgingView.as_view(),
        name="inventory-aging",
    ),
    path(
        "orgs/<uuid:org_id>/reports/inventory-aging/export/csv/",
        InventoryAgingExportView.as_view(),
        name="inventory-aging-export-csv",
    ),
    path(
        "orgs/<uuid:org_id>/reports/slow-dead-stock/",
        SlowDeadStockView.as_view(),
        name="slow-dead-stock",
    ),
    path(
        "orgs/<uuid:org_id>/reports/slow-dead-stock/export/csv/",
        SlowDeadStockExportView.as_view(),
        name="slow-dead-stock-export-csv",
    ),
    path(
        "orgs/<uuid:org_id>/branch-items/catalog/",
        BranchItemCatalogView.as_view(),
        name="branch-items-catalog",
    ),
    path(
        "orgs/<uuid:org_id>/branch-items/bulk-activate/",
        BranchItemBulkActivateView.as_view(),
        name="branch-items-bulk-activate",
    ),
    path(
        "orgs/<uuid:org_id>/branch-items/bulk-deactivate/",
        BranchItemBulkDeactivateView.as_view(),
        name="branch-items-bulk-deactivate",
    ),
    path(
        "orgs/<uuid:org_id>/inventory/items/bulk-activate/",
        OrgItemBulkActivateView.as_view(),
        name="org-items-bulk-activate",
    ),
    path(
        "orgs/<uuid:org_id>/inventory/items/resolve-scan/",
        ScanResolveView.as_view(),
        name="scan-resolve",
    ),
    path("orgs/<uuid:org_id>/", include(org_router.urls)),
    path("parent/", include(parent_router.urls)),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
